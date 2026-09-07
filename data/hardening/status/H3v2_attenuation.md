# H3v2 — attenuation re-measurement on the REPAIRED (rubric v1.2) student

**Campaign:** owner-ratified 2026-08-27 (`HANDOFF.md` §3, 2026-08-27 entry,
item 4). Re-run H3's labeler-attenuation measurement on the v1.2 epoch-2
student so the G1 ruling can read v1.2 retention beside H3's v1.1 numbers.

**This file has three sections**, exactly like `H3_attenuation.md`.
Section 1 (implementation / staging) is DONE, 2026-08-27, by the
finetune-engineer. Section 2 (the run) is appended by the MAIN SESSION.
Section 3 (the comparison) is appended by quant-modeler.
**Do not treat the item as done until all three exist.**

Cost: **$0**, zero Anthropic API calls (HANDOFF §5). All compute is local MLX.

**H3's v1.1 artifacts are a ruled record and were not touched.** Every output
below lands in `data/hardening/h3v2/` with a `_v12` filename suffix. Re-verified
after this work: `data/hardening/e1_relabel_student.parquet`
`5de9230bed706b92…`, journal `fc5f06a95b8bc132…`, `data/labels.parquet`
`c3531f03cda602bc…`, `data/labels_v12.parquet` `ca373b953504535b…` — all
unchanged.

---

## 1. Implementation / staging — DONE 2026-08-27

**No GPU work was done here.** The v1.2 epoch-2 training was running on this
machine throughout (`finetune/runs/2026-08-27-v12-epoch2/`), so not a single
token was generated, no model was loaded, and no MLX import was executed. Every
check below is offline: pandas/pyarrow/stdlib only. The 10-row smoke is the
main session's job, in its own GPU slot (§1.5).

### 1.1 What changed

`finetune/relabel_e1.py` was **extended, not forked**. H3's invocation is
byte-compatible: every new path is a *default*, and omitting all of them
reproduces the 2026-08-25 run exactly (pinned by two tests, one of which
rebuilds H3's shipped parquet byte-for-byte — §1.9).

| | H3 (v1.1) | H3v2 (v1.2) |
|---|---|---|
| flag | *(none)* | **`--v12`** |
| rendered data | `finetune/mlx_data/` | `finetune/mlx_data_v12/` |
| teacher (schema + agreement comparand) | `data/labels.parquet` | `data/labels_v12.parquet` |
| adapter | `checkpoints/…-lora-mlx-epoch2` | `checkpoints/…-lora-mlx-v12-epoch2` |
| training manifest | `runs/2026-08-21-epoch2/manifest.json` | `runs/2026-08-27-v12-epoch2/manifest.json` |
| reference eval | `runs/2026-08-22-eval-epoch2/predictions.jsonl` | `runs/2026-08-28-v12-eval-epoch2/predictions.jsonl` |
| out-dir | `data/hardening/` | `data/hardening/h3v2/` |
| filename suffix | *(none)* | `_v12` |
| run id / `batch_id` | `H3-e1-relabel-epoch2` | `H3v2-e1-relabel-v12-epoch2` |

**One flag flips all eight together.** That is deliberate: a hand-typed set of
eight paths is eight chances to pair a v1.1 adapter with v1.2 data, and the
resulting artifact would look valid. Each value is still individually
overridable (`--adapter-path`, `--train-manifest`, `--reference-predictions`,
`--mlx-data-dir`, `--labels-parquet`, `--out-dir`, `--name-suffix`, `--run-id`),
which is what a kill-segmented epoch 2 needs (§1.10, trap 2). The resolved set
is printed to stderr on **every** invocation and re-recorded, with sha256s, in
the run manifest.

Everything else is unchanged: same 6,746 chunks, same frozen canonical row
order, same greedy decoding at `temp 0.0` / `max_tokens 520`, same
journal/resume/finalize machinery, same three-mode structure
(`--write-sidecar` → generate → `--finalize-only`), same two interpreters
(system `python3` for the parquet steps, `.mlx_venv` for the GPU step).

Files touched: `finetune/relabel_e1.py` (sha256
`383a0222a44608b7ade9c5df4a53af4769ca14c312bb6e5b4f59f9936a4f8e6c`),
`finetune/test_relabel_e1.py` (`9f3f38604dce0dec381e4f11c7b1c8841edb5e3f5826261292a90263c78f5b75`).
Nothing else in the repo was edited — not `eval.py`, not `convert_to_mlx.py`,
not `features.py`, not any ledger.

### 1.2 The exact MAIN-SESSION commands (copy-paste)

```bash
FS=/Users/vihanpatil/personal/projects/FinScreen
OUT=$FS/data/hardening/h3v2
```

#### step 0 — sidecar (SYSTEM python3, ~10 s, no GPU, safe to run any time)

```bash
cd $FS
python3 finetune/relabel_e1.py --v12 --write-sidecar
```

Expected last line, exactly:

```
  6746 rows in corpus order · 6694 passages identical to corpus text · 52 head-truncated · 0 non-prefix
```

Writes `$OUT/e1_relabel_sidecar_v12.json` (and creates `$OUT`). See §1.6 for
what it verifies and §1.7 for why it does **not** read a training manifest.

#### step 1 — 10-row SMOKE (GPU slot; ~1 min; run this BEFORE the full run)

Requires the v1.2 epoch-2 eval to have finished, because the smoke's whole
point is the verify-artifact check against its predictions.

```bash
mkdir -p $OUT/smoke
caffeinate -dims $FS/finetune/.mlx_venv/bin/python $FS/finetune/relabel_e1.py \
  --v12 --split eval --limit 10 \
  --out-dir  $OUT/smoke \
  --sidecar  $OUT/e1_relabel_sidecar_v12.json \
  >> $OUT/smoke/smoke.log 2>&1

python3 $FS/finetune/relabel_e1.py --v12 --finalize-only \
  --out-dir  $OUT/smoke \
  --sidecar  $OUT/e1_relabel_sidecar_v12.json \
  --split eval --limit 10 --allow-partial
```

**All of these must hold before launching the full run** (they are printed by
the finalize step and written to `$OUT/smoke/e1_relabel_manifest_v12.json`):

| check | required value | where |
|---|---|---|
| rows generated | **10/10**, exit 0 | `smoke.log` tail |
| finish reasons | `{"stop": 10}` — **zero `length`** | `segments[0].finish_reasons` |
| parse failures / schema violations | **0 / 0** | `parquet.*` |
| **reproduction check** | **10/10 byte-identical**, `verified: true` | `reproduction_check` |
| adapter cross-check | `adapter_sha256_matches_reference_eval: true` | `data.*` |
| data cross-check | `sha_matches_train_manifest: true` | `data.*` |
| instruction | `ebc45a856bff58a5…`, `..._matches_reference_eval: true` | `data.*` |
| parquet shape | **10 rows × 40 cols** | `parquet.n_columns` |
| is it a real relabel? | some rows must DISAGREE with the teacher | eyeball the parquet |
| throughput | ~1,200–1,500 chunks/h | `segments[0].chunks_per_hour` |

**If the reproduction check is not 10/10, STOP and report it** — that means the
prompt, the adapter or the decoding moved, and the full run would produce an
artifact that is not the artifact the eval tested (HANDOFF §7). If it says
`MISSING_REFERENCE — THE VERIFY-ARTIFACT CHECK DID NOT RUN`, see trap 1.
n=10 agreement rates are **not** a result; the only thing the smoke measures is
mechanics.

#### step 2 — THE FULL RUN (main-session BACKGROUND task; ~4.7 h)

```bash
ps aux | grep -E 'mlx_lm|eval\.py|train_qlora' | grep -v grep    # MUST be empty

caffeinate -dims \
  $FS/finetune/.mlx_venv/bin/python \
  $FS/finetune/relabel_e1.py --v12 \
  >> $FS/data/hardening/h3v2/e1_relabel_v12.log 2>&1
```

Use `>> … 2>&1`, **never `| tee`** — a pipe hands back tee's exit status and the
resume chain could not tell "done" (0) from "resume me" (2). Live progress:
`tail -f $OUT/e1_relabel_v12.log`.

Never launch this from a subagent shell (HANDOFF §4).

#### step 3 — finalize (SYSTEM python3, ~30 s, loads no model)

```bash
cd $FS
python3 finetune/relabel_e1.py --v12 --finalize-only
```

Produces `$OUT/e1_relabel_student_v12.parquet` (the deliverable),
`$OUT/e1_relabel_manifest_v12.json`, and the agreement sanity block.
Idempotent: re-running gives an identical parquet sha.

### 1.3 Resume semantics — unchanged from H3, restated

- **Exit 0** = every target row is in the journal → go to step 3.
  **Exit 2** = partial → **re-run the identical step-2 command**. Finished rows
  are skipped; nothing is regenerated.
- Every row is `write` + `flush` + `fsync` to
  `$OUT/e1_relabel_student_v12.jsonl` before the next row starts. A SIGTERM or
  `kill -9` at any instant loses **at most the in-flight row** (~2.5 s).
- A torn final line is ignored on read **and terminated with a newline before
  the next append** (`ensure_trailing_newline`) — without that repair a resume
  silently loses one good row per kill (the bug H3's resume smoke caught).
- Every journal row stores the sha256 of the exact prompt token sequence it was
  generated from. If the data or the rendering moved under a resume, the run
  **stops hard** rather than mixing two prompt versions into one artifact.
- Labels are **resume-invariant** (verified in H3); per-row telemetry
  (`latency_s`, `labeled_at`) is not, so the parquet sha is a provenance stamp
  of the run, not a content hash of the labels.
- `--max-rows-per-segment N` exists if voluntary segment exits are preferred;
  default 0 = run until done or killed. Cost per extra segment: one model load
  (~1.5 s warm) plus the prompt re-render pre-pass (12.3 s for all 6,746,
  measured in H3).
- Re-running after completion is a no-op: it never loads the model.

### 1.4 Projected wall-clock — from H3's MEASURED throughput, not a model

H3 ran this identical machinery over these identical 6,746 chunks on this
machine: **16,694.8 s = 4.64 h, 1,454.7 chunks/h**, single segment, 0 kills,
mean 33.9 generated tokens/row, all 6,746 `finish_reason=stop`.

The v1.2 workload is the same size to within a rounding error:

| | E1 (H3, measured) | v1.2 | delta |
|---|---|---|---|
| prompt tokens, whole corpus | 6,636,538 | **6,636,238** | −300 (**−0.005%**) |
| target tokens/row, mean (train / eval) | 37.0 / 42.3 | 37.4 / 42.8 | **+1.1%** |

Prefill work is identical. Decode is ~1.1% more if the student's generations
scale with its targets, which moves the total by roughly +0.6%.

### **Point estimate ≈ 4.7 h (4.64 h × 1.006). Quote the band 4.6–5.6 h** (H3 §1.4).

At ~1,450 chunks/h a one-hour kill window covers ~1,450 rows; each kill costs
≤1 row plus a ~1.5 s reload plus a 12 s re-render pre-pass. H3 needed 0
segments; plan for a handful anyway.

**Stop the run and report it as the finding** if progress lines start showing
`finish=length` with `gen_tok` near 520 — that is a non-terminating model, not
a slow one, and it would be a real difference between the v1.1 and v1.2
students.

### 1.5 What was and was not executed here

**Executed (offline, no GPU, no model, no network):** the v1.2 sidecar build
against the real artifacts, a synthetic-journal parquet build against the real
v1.2 schema, the agreement scorer against real v1.2 gold, the full CLI in both
modes into a scratch directory, and a byte-for-byte rebuild of H3's shipped
parquet. `python3 -m pytest finetune/test_relabel_e1.py -q` → **36 passed**
(20 before this work, 16 new), 7.7 s, no model/GPU/network in any of them.

**Not executed:** the 10-row smoke and the 6,746-chunk run. Long compute is a
main-session auto-resume chain (HANDOFF §4) and the GPU was busy with the
epoch-2 training the whole time.

### 1.6 Provenance chain — all verified at RELABEL time, before a token is generated

1. `mlx_data_v12/{train,valid}.jsonl` sha256 == the **v1.2 epoch-2 training
   manifest's** — else hard stop. Pinned values `396aef131bec0e5c…` /
   `b74efdb326e9b862…`.
2. The same shas == the sidecar's — else hard stop (the data moved after the
   corpus verification, or a sidecar from the other campaign was supplied).
3. Sidecar: the 6,746 rendered rows all carry a usable `labels_v12.parquet`
   label; the row count is exactly the frozen 6,746 (train 5,736 / eval 1,010);
   the one teacher row outside the split is `CHK-8e69547e0900a8dd`; and **every
   rendered passage is a head-prefix of its `labeling_corpus.parquet` text** —
   6,694 identical, 52 head-truncated to fit 2,048, **0 non-prefix**.
4. Adapter: `eval._adapter_provenance` re-reads `adapter_config.json` and
   refuses a different base model, a non-LoRA type or a different
   `max_seq_length`; it hashes `adapters.safetensors` and every numbered
   checkpoint.
5. **NEW in H3v2 — the adapter cross-check.** The adapter about to label 6,746
   chunks is compared against the adapter the **reference eval actually ran**
   (`runs/2026-08-28-v12-eval-epoch2/manifest.json` → `adapter.adapters_sha256`).
   A mismatch is a `SystemExit` before any model load, naming both paths and
   both hashes. This is the guard for the kill-segmented-training trap
   (§1.10 trap 2): if the wrong adapter were used, the reproduction check could
   not pass, and it is better to learn that in 3 seconds than in 4.7 hours.
6. Instruction sha256 `ebc45a856bff58a5…` — asserted byte-identical across all
   6,746 rows and compared to the reference eval manifest's.
7. Base weights `86110f368236b53c…` (from the training manifest).
8. If the reference predictions are absent at generate time, a loud stderr
   warning fires; at finalize time it is recorded as
   `STATUS: MISSING_REFERENCE — THE VERIFY-ARTIFACT CHECK DID NOT RUN`,
   `verified: false`, never as a silent skip.

**Prompt-rendering exactness** is by construction, not restatement: rows are
the rendered records the v1.2 trainer consumed, and the prompt is
`eval.render_prompt_token_ids` → `convert_to_mlx.to_messages()` +
`convert_to_mlx.render()`, sliced at the generation-prompt offset. Per row it
re-asserts that `to_messages(instruction, passage, answer)` reproduces the
stored messages. system=instruction / user=passage, nothing appended.
Look-ahead-safe: the prompt contains only the passage; no ticker, date or
outcome enters. Decoding is greedy (`temp 0.0` → argmax), `max_tokens 520` —
identical to the v1.2 epoch-2 eval (`generation.max_tokens: 520`,
`decoding: greedy (temperature 0.0 -> argmax sampler)`).

**Measured and recorded, not hidden — the v1.2 vs E1 prompt delta.** Over all
6,746 rows, with the rendered artifacts themselves: the **system turn is
byte-identical on 6,746/6,746**, and the passage differs on **14** rows
(**2 train / 12 eval**), each a strict head-prefix relation in one direction or
the other, −505 to +33 characters. That is the answer-length-dependent head
truncation `convert_to_mlx.py` applies to fit 2,048 tokens *including* the
answer (`G1_repair_dataset.md` §3). It is pinned by a test
(`test_v12_prompts_differ_from_e1_only_by_the_documented_head_truncation`) and
it belongs in the G1 read, not in a footnote: 1.19% of the eval prompts are not
literally the prompts the v1.1 student saw.

### 1.7 Output schema — and the three ways v1.2's teacher parquet differs

`$OUT/e1_relabel_student_v12.parquet`, chunk_id-keyed, in
`labeling_corpus.parquet` row order, **40 columns** (H3's was 37).

**Columns 1–34 are `data/labels_v12.parquet`'s arrow schema, copied from the
file itself rather than re-declared** (`pq.read_schema`), exactly as H3 copied
from `data/labels.parquet`. The schema copy works — but v1.2's schema is **not**
v1.1's, and the differences are recorded rather than papered over:

| # | difference vs v1.1's 31-column schema | how H3v2 handles it |
|---|---|---|
| 1 | **34 fields, not 31**: adds `rubric_version`, `system_prompt_sha256`, `completion_batch_id` | filled explicitly, see below; every fill recorded in `parquet.teacher_only_columns_filled_for_the_student` |
| 2 | **different field ORDER** (the label-provenance block is reshuffled: `stop_reason, output_tokens, batch_id, max_tokens_used, labeling_config, rubric_version, system_prompt_sha256, labeled_at, completion_batch_id`) | irrelevant — columns are selected by name; the output simply carries v1.2's order |
| 3 | **`parse_error` is typed `null`**, because every v1.2 teacher row parsed | **widened to `string`.** A null-typed arrow column cannot hold the student's parse-failure message, so an un-repaired copy would either crash or lose the diagnosis on the first failed row. Recorded in `parquet.null_typed_columns_widened_to_string`; pinned by a test that round-trips a real parse failure. **This is the only field that differs from the teacher's schema.** |
| 4 | `output_tokens` is `double`, not `int64` | carried as-is (the student's int casts losslessly); noted so nobody reads `20.0` as a bug |

The three v1.2-only columns, and why they are what they are:

- `rubric_version` = **`"v1.2"`** — the rubric revision of the *targets this
  student was trained on*, read from the teacher parquet itself.
- `system_prompt_sha256` = **`ebc45a856bff58a5…`**, the **training
  instruction** — i.e. the student's actual system turn. It is deliberately
  **not** the teacher's labeling prompt `30605197ca56c231…`: those are two
  distinct artifacts (`G1_repair_dataset.md` §4, 1,825 chars vs 9,521), and
  copying the teacher's value here would be false provenance.
- `completion_batch_id` = **null** — one local pass, one labeler, no completion
  batch.

Repurposed provenance columns (same names, student values):
`api_result_type='student_local_mlx'`, `batch_id='H3v2-e1-relabel-v12-epoch2'`,
`stop_reason`=MLX finish_reason, `output_tokens`=generation tokens,
`max_tokens_used=520`,
`labeling_config='student=qwen2.5-7b-finscreen-lora-mlx-v12-epoch2,backend=mlx,decoding=greedy(temp=0.0),max_tokens=520'`,
`raw_label_json`=the model's raw text.

**6 student-only columns appended** (unchanged from H3): `split`,
`passage_was_head_truncated`, `prompt_tokens`, `prompt_sha256`, `latency_s`,
`schema_issues`.

`distress_tier` is **uniformly empty** — never a training target (HANDOFF §7);
the column exists only so the schema is drop-in. Do not compare it.
Out-of-taxonomy categories/modalities are dropped from `red_flags` and recorded
in `schema_issues`; parse failures keep the row with `parse_ok=false` and null
labels, never silently dropped.

The downstream join is still a path swap: `features.py` reads `chunk_id`,
`section_type`, `sentiment`, `guidance_direction`, `red_flags` and filters
`parse_ok`, and all five behave identically here.

### 1.8 Caveats that must travel into section 3 (all of them are in the manifest)

Carried unchanged from H3 §1.8:

1. **85.0% of these rows (5,736/6,746) are the student's own TRAINING rows.**
   Their teacher-agreement is inflated by memorization, so any retention ρ or
   IC-delta over the pooled corpus is **optimistic** — an upper bound on
   retention, not an estimate of it. The `split` column exists so the
   comparison is reported **pooled AND eval-only** (n=1,010, the only unbiased
   slice). Feature re-derivation needs all 6,746 (a filing's features aggregate
   over every attributed chunk), so: pooled = the feature-level comparison with
   a named optimistic bias; eval-only = the unbiased chunk-level bound.
2. Every rate is **agreement with the teacher, not accuracy.** A perfectly
   agreeing student has reproduced the teacher including its errors.
3. `red_flags` must be reported on **both** bases — exact-set and per-category.
   The finalize step computes both, via `eval.score_red_flags` verbatim.
4. **8K_BODY (n=8, 2 tickers) and WITHDRAWN (n=1, in train) are not evaluable**
   and are excluded from the headline agreement tables, reported separately.
5. `guidance_direction` is stored **raw**; the missing→NONE post-rule is
   PROPOSED, NOT ADOPTED (gate G1). It is a no-op for the feature join —
   `features.py` maps both `"NONE"` and null to NaN — and both figures appear in
   the manifest.
6. E1's `data/labels.parquet` is frozen and untouched; this artifact is a
   second labeler's output, never a replacement.

**New for H3v2** (also appended to the manifest's `caveats` — 9 entries, not 6):

7. **The comparison teacher is `data/labels_v12.parquet` (rubric v1.2)**, not
   E1's v1.1 labels. Every agreement and retention number in section 3 is
   against the v1.2 teacher.
8. **Cross-rubric comparison is INSTRUMENT-VS-INSTRUMENT, never like-for-like.**
   H3's v1.1 numbers and H3v2's v1.2 numbers are each measured against their
   *own* teacher. The question they jointly answer is "does the repaired
   student track its own teacher better than the old student tracked its own
   teacher?" — not "is the student more accurate", because the target moved:
   rubric v1.2 changed `red_flags` on **27.48% of rows (exact-set) / 5.86%
   per-category**, sentiment on 4.59%, guidance on 1.19%
   (`data/hardening/LABEL_SHIFT_v11_v12.md`). A retention ρ that rises could
   reflect an easier teacher as much as a better student; say which is being
   claimed, and note that the two teachers also differ in difficulty per
   category (`MARGIN_COST_PRESSURE` +294 rows, `LEGAL_REGULATORY_ACTION`
   300 HYP→REAL flips).
9. **14 of the 6,746 prompts are not token-identical to E1's** (2 train /
   12 eval, head-truncation length only, §1.6). On the eval side that is
   **12/1,010 = 1.19%**.

Two more that section 3 must not re-learn the hard way:

10. **The teacher-side feature table must be re-derived from
    `data/labels_v12.parquet`.** `data/features.parquet` is the frozen
    v1.1-derived table; an H3v2 teacher arm built from v1.2 labels will
    **not** reproduce it, and that is correct, not a bug. H3's verification #1
    ("teacher re-derivation reproduces the frozen artifact exactly") therefore
    has no H3v2 analogue — the analogue is "the v1.1 re-derivation still
    reproduces `data/features.parquet`", i.e. the harness is unchanged.
11. **Row order is load-bearing.** `h3_features.build_with_labels` preserves
    `features.py`'s build order deliberately: `backtest.load_modeling_frame()`
    sorts by `filing_date` alone with a non-stable quicksort over 630 rows with
    298 distinct dates, and a permutation of tied rows moved the headline IC
    delta by +0.050 during H3 (`H3_attenuation.md` §3.0a). Keep that property.

### 1.9 Tests — 36 passed (20 → 36), all offline

`python3 -m pytest finetune/test_relabel_e1.py -q` → **36 passed in 7.7 s**.
No model, no GPU, no network, no Anthropic import, $0.

The 20 H3 tests are unchanged and still green. The 16 new ones:

| what it pins | why it matters |
|---|---|
| E1's resolved defaults with no flags | H3's invocation must be byte-compatible after the extension |
| `--v12`'s eight resolved paths | the ratified path set, in code, not in prose |
| explicit flags beat the profile | a kill-segmented epoch 2 must be overridable without losing the rest |
| output names never collide with H3's four filenames | H3's artifacts are a ruled record |
| `mlx_data_v12` shas == the v1.2 training manifests' | the student labels what it was trained on |
| the v1.2 sidecar chain (6,746 rows, 52 truncated, 0 non-prefix, 6,747 labeled, refusal chunk excluded, instruction `ebc45a85…`) | the whole run rests on this |
| v1.2 and E1 render the same chunk_ids in the same order | the split is frozen |
| **the 14-row prompt delta** (2 train / 12 eval, head-prefix, −505..+33) | the honest caveat, measured rather than quoted |
| the v1.2 schema copy: 40 cols, exactly one field differs (`parse_error`), 3 fills named | "verify the schema copy still works" |
| **a parse failure round-trips through the widened `parse_error`** | the load-bearing consequence of the null-typed column |
| run_id / labeling_config / empty `distress_tier` in the artifact | provenance and HANDOFF §7 |
| `labels_v12.parquet` untouched by a build | frozen artifact |
| the agreement scorer follows `--mlx-data-dir` (v1.2 gold fed back = 1.0; same outputs vs v1.1 gold < 1.0) | proves the teacher swap is real, and demonstrates caveat 8 |
| a missing reference reads as `MISSING_REFERENCE / verified:false`, never a quiet pass | the brief's hard-and-loud requirement |
| the v1.2 caveat block names the teacher, the instrument-vs-instrument framing, 27.48%, and the 14 rows | caveats travel with the artifact |
| **`build_parquet` over H3's real 6,746-row journal still hashes to `5de9230bed706b92…`** | the strongest regression proof available: the extended runner reproduces the ruled H3 artifact byte-for-byte |

### 1.10 Traps the main session must know before launching

1. **The reference-eval directory name.** `--v12` expects
   `finetune/runs/2026-08-28-v12-eval-epoch2/predictions.jsonl`, which is the
   name `runs/2026-08-26-v12-epoch1/RUN_COMMANDS.md` §5 pins. Epoch 2 finishes
   on **2026-08-27**, so it is easy to name the eval directory `2026-08-27-…`
   instead. If that happens, pass
   `--reference-predictions <that dir>/predictions.jsonl` on **both** the smoke
   and the finalize, or the verify-artifact check will read
   `MISSING_REFERENCE … DID NOT RUN` and the artifact will be correctly, and
   uselessly, marked unverified.
2. **A kill-segmented epoch 2.** If the training run was killed and resumed, the
   final adapter is in the **last segment's** checkpoint dir and its manifest is
   the last segment's, not `runs/2026-08-27-v12-epoch2/manifest.json`. Read both
   out of the eval that was actually run —
   `runs/2026-08-28-v12-eval-epoch2/manifest.json` → `.adapter.path` and
   `.train_manifest.path` — and pass `--adapter-path` / `--train-manifest`.
   The new adapter cross-check (§1.6 step 5) turns this from a silent
   4.7-hour waste into a 3-second `SystemExit`, but only if the reference
   predictions exist, so trap 1 comes first.
3. **Run the smoke in its own GPU slot, before the full run.** It is ~1 minute
   and it is the only thing that proves the whole chain end to end.
4. **`>> log 2>&1`, never `| tee`** — a pipe destroys the exit code the resume
   chain reads.
5. **Never launch step 2 from an agent shell** (HANDOFF §4). Background
   main-session task; every kill notification is a resume trigger.
6. **Nothing else on the GPU.** H3v2 is slotted last (after F3 P2); check
   `ps aux | grep -E 'mlx_lm|eval\.py|train_qlora'` is empty first.
7. **`data/hardening/h3v2/` will not exist until step 0 runs**, and the step-2
   redirect needs it. Run step 0 first.
8. **The sidecar is campaign-specific.** Pairing H3's sidecar with v1.2 data
   (or vice versa) hard-stops on the sha check with a message naming the
   sidecar's recorded data directory — it cannot silently mix.

### 1.11 What was deliberately NOT done

- **No GPU work of any kind**, including the smoke. The epoch-2 training owned
  the GPU for the whole task.
- **No launch of the relabel.** Long compute is a main-session auto-resume
  chain (HANDOFF §4); a subagent must never spawn it.
- **No comparison, no feature re-derivation, no backtest, no retention ρ** —
  that is quant-modeler's section 3. The manifest's `agreement_summary` is a
  sanity block, explicitly not the H3v2 result.
- **`data/hardening/h3_features.py` was not touched.** Its `STUDENT_LABELS`
  (`data/hardening/e1_relabel_student.parquet`) and `FROZEN_LABELS`
  (`data/labels.parquet`) are hardcoded, and `FROZEN_FEATURES`
  (`data/features.parquet`) is the v1.1 teacher table. Section 3 needs all
  three re-pointed (see caveat 10) — that is quant-modeler's module and its
  call, not a change to make blind from here.
- **No ledger edits.** `HARDENING_PROGRESS.md`, `HANDOFF.md`, `F3_PROGRESS.md`
  and `RESUME_HERE.md` are the main session's; none were opened for writing.
- **No third-epoch or re-label recommendation.** G1 is the owner's.

---

## 2. The run — DONE 2026-08-27

**Every number below is read from
`data/hardening/h3v2/e1_relabel_manifest_v12.json` (and the log); nothing is
hand-carried from §1's projections.** Smoke (10 rows) ran first in its own
GPU slot at ~13:03 CDT and passed every §1.2 check, including a 10/10
reproduction check, before the full launch.

| item | value |
|---|---|
| run id | `H3v2-e1-relabel-v12-epoch2` |
| start / end (UTC) | 2026-08-27 17:58:48 → 22:32:43 |
| segments / kills | **1 segment, 0 kills** — completed in a single pass |
| journal | **6,746 / 6,746**, `complete: true` |
| finish reasons | `{"stop": 6746}` — zero `length` truncations |
| parse / schema | **0 failures / 0 violations** |
| **reproduction check** | **1,010/1,010 byte-identical** to `runs/2026-08-28-v12-eval-epoch2/predictions.jsonl`, `verified: true` |
| provenance | `sha_matches_train_manifest: true` · `adapter_sha256_matches_reference_eval: true` (adapter `cadca849…`) · `instruction_sha256_matches_reference_eval: true` |
| wall clock | 16,434.3 s = **4.57 h** (§1's band 4.6–5.6 h, at the optimistic edge — F3 P3/P4 agents shared the CPU for part of it) |
| throughput | **1,477.7 chunks/h** |
| parquet | `data/hardening/h3v2/e1_relabel_student_v12.parquet` — 6,746 rows × 40 cols, sha `3dbfba64f3320d04…` |
| eval-slice sanity (NOT the H3v2 result) | sentiment 0.8362 · red_flags exact-set 0.6307 — equal to the epoch-2 eval's, as the byte-identity requires |
| cost | **$0 / 0 Anthropic API calls** |

## 3. The comparison — DONE 2026-08-27, quant-modeler

**Gate G1 is the owner's ruling on this result.** §1.8's eleven caveats apply to
everything below and are re-attached inline where they bite.

**THE FRAMING RULE, stated once here and repeated wherever the two campaigns'
numbers meet: each student is measured against ITS OWN teacher. This is
instrument-vs-instrument, not two scores on one yardstick.** The v1.2 teacher's
own labels moved — `red_flags` 27.48% exact-set / 5.86% per-category, sentiment
4.59%, guidance 1.19% (`data/hardening/LABEL_SHIFT_v11_v12.md`). §3.4 measures
how much of the H3 → H3v2 move is the teacher rather than the student, and the
answer is: **about half of it, and for two named features essentially all of
it.**

### 3.0 How this was produced, and what was verified before anything was read

| # | Deliverable | Path |
|---|---|---|
| 1 | v1.2 feature re-derivation + per-feature retention + the four pre-verifications | `data/hardening/h3v2/h3v2_features.py` → `h3v2_retention_2026-08-27_H3v2.json` (`d0d3048f…`) |
| 2 | filing-clustered bootstrap CIs on v1.2 retention | `data/hardening/h3v2/h3v2_retention_ci.py` → `h3v2_retention_ci_2026-08-27_H3v2.json` (`0dcd6ade…`) |
| 3 | matched-composition control (thinness vs memorization) | `data/hardening/h3v2/h3v2_composition_control.py` → `h3v2_composition_control_2026-08-27_H3v2.json` (`769fa644…`) |
| 4 | the evaluation-bug hunt: wrapper-reproduces-H3, the 2×2 cross-pairing, chunk-level per-section mechanism, NaN patterns | `data/hardening/h3v2/h3v2_diagnostics.py` → `h3v2_diagnostics_2026-08-27_H3v2.json` (`4fd04bb0…`) |
| 5 | PAIRED filing-clustered bootstrap on the v1.1→v1.2 delta and its teacher/student attribution | `data/hardening/h3v2/h3v2_paired_delta_ci.py` → `h3v2_paired_delta_ci_2026-08-27_H3v2.json` (`5ed26133…`) |

Derived v1.2 feature tables, all under `data/hardening/h3v2/`:
`features_teacher_v12_2026-08-27_H3v2.parquet` (`3a644ca0…`),
`features_student_v12_2026-08-27_H3v2.parquet` (`a6de482f…`),
`features_teacher_evalchunks_v12_2026-08-27_H3v2.parquet` (`17bf1fab…`),
`features_student_evalchunks_v12_2026-08-27_H3v2.parquet` (`ec7b0fe7…`).

**Machinery.** `features.build_feature_table()` is used verbatim — same
every-occurrence attribution, same backward-flow assertion, same three-group
NaN-vs-0 policy, same numeric/target joins. The **only** thing swapped is which
labels frame it consumes. Per §1.11, `h3_features.py`, `h3_retention_ci.py` and
`h3_composition_control.py` were **imported, not edited**: their v1.1
`STUDENT_LABELS` / `FROZEN_LABELS` / `FROZEN_FEATURES` constants are untouched
and the five new scripts are thin wrappers that reuse `build_with_labels`,
`retention_row`, `retention_table`, `bootstrap`, `_corr` and `text_table`.
`features.py`, `backtest.py`, `spec.py` and `diagnose.py` were **not edited**.
Zero network calls, no GPU, no MLX import, all compute local, $0.

**Row order is preserved**, per §1.8 caveat 11: `build_with_labels` does not
re-sort, so all six builds carry `features.py`'s build order. H3 §3.0a's
row-order defect was worth +0.050 on the headline IC delta; it cannot recur
here.

**Population.** `data/labels_v12.parquet` carries **6,747** `parse_ok` rows; the
student carries **6,746**. The extra row is E1's safety-refusal chunk
`CHK-8e69547e0900a8dd`, which labeled under v1.2 but is outside the FROZEN split
(§1.6 step 3). The teacher is restricted to the student's 6,746 chunk_ids so the
two arms are chunk-for-chunk; otherwise a feature difference could be that one
extra chunk rather than the labeler. Verified: the v1.1 and v1.2 students carry
**byte-identical splits** — the same 1,010 eval `chunk_id`s, the same 5,736
train, in the same row order — so §3.4's cross-campaign comparison is
like-for-like *on the slice*, whatever else differs.

**Six verifications passed before any comparison number was read.**

1. **V1 — HARNESS UNCHANGED.** Re-running the pipeline on `data/labels.parquet`
   still reproduces all 630 rows × (10 numeric + 22 text + target) of
   `data/features.parquet`, same row order, `allclose(..., equal_nan=True)` →
   **True**. This is the H3v2 analogue of H3's verification 1 (§1.8 caveat 10):
   the harness that produced H3's ruled numbers is the harness producing these.
2. **V2 — DETERMINISM.** The pipeline run **twice** on `data/labels_v12.parquet`
   gives bit-identical tables, values and row order, for both the teacher and
   the student arm → **True / True**.
3. **Expected-FALSE, recorded rather than silently skipped.** The v1.2 teacher
   table does **not** reproduce `data/features.parquet` — **1,670 text cells
   differ** across the 630 × 22 text block. That is correct, not a bug: it is
   the frozen v1.1-derived table (§1.8 caveat 10).
4. **V3 — WIRING.** The five label-independent composition features
   (`n_text_chunks_attributed`, four `share_chunks_*`) come back at retention
   **exactly 1.0000** in **all four** slices (pooled all-rows, pooled
   modeling-rows, eval-only all-rows, eval-only modeling-rows). `section_type`
   is a corpus column, not a model output, so anything else would have meant a
   broken join and a hard stop.
5. **V4 — the guidance no-op still holds.** `features.GUIDANCE_MAP` has no
   `"NONE"` key and nulls map to NaN, so `"NONE"` and missing are identical to
   the feature layer. §1.8 caveat 5's "PROPOSED, NOT ADOPTED" post-rule remains
   a genuine no-op for every feature in this section (it is **not** a no-op for
   the chunk-level guidance agreement rate — see §3.3).
6. **V5 — the wrapper reproduces H3.** Running *this section's* code path over
   the **v1.1** artifacts (v1.1 student vs v1.1 teacher) returns 0.6694 /
   0.5922 / 0.8343 / 0.1145 / 0.2145 / 0.6223 — **bit-identical to H3's machine
   record** `h3_retention_2026-08-25.json` on all six headline values (H3 §3.1's
   prose quotes them to 3 dp; `redflag_DEMAND_WEAKNESS_rate_mda` is 0.2145,
   printed there as 0.215). So the wrapper is not the reason the v1.2 numbers
   are higher.

**Numeric arm is label-independent**, asserted across all six builds: the 10
numeric features and `target_excess_return` are `allclose` identical
everywhere. Only the text arm moves.

**Frozen artifacts re-hashed after every script and unchanged:**
`data/labels.parquet` `c3531f03cda602bc…`, `data/features.parquet`
`dbc1be09b560a144…`, `data/labels_v12.parquet` `ca373b953504535b…`,
`data/hardening/e1_relabel_student.parquet` `5de9230bed706b92…`,
`data/hardening/h3v2/e1_relabel_student_v12.parquet` `3dbfba64f3320d04…`.
H3's three modules are also byte-unchanged (`h3_features.py`
`c3f31cce…`, `h3_retention_ci.py` `7a257a08…`, `h3_composition_control.py`
`30c0bf1a…`).

### 3.0a "If it looks too good, assume an evaluation bug first" — the hunt, and what it found

The v1.2 eval-only numbers came in **far** above H3's while the **chunk-level**
held-out agreement barely moved. Side by side, from the two run manifests
(`agreement_summary.eval_ONLY_UNBIASED_SLICE`, n=1,002 evaluable rows):

| chunk-level, EVAL slice | v1.1 student | v1.2 student | Δ |
|---|---|---|---|
| `red_flags` micro F1 | 0.787 | 0.795 | +0.008 |
| `red_flags` macro F1 | 0.793 | 0.802 | +0.009 |
| `red_flags` exact-set (category+modality) | 0.6487 | **0.6307** | **−0.018** |
| `red_flags` exact-set (category only) | 0.6587 | 0.6597 | +0.001 |
| sentiment exact match | 0.8351 | 0.8362 | +0.001 |
| sentiment NEGATIVE recall | 0.487 | 0.529 | +0.042 |
| `guidance_direction` exact match | 0.5877 | **0.5211** | **−0.067** |

Against that, the filing-level 12-flag family retention rose **0.669 → 0.808**.
A +0.14 correlation move out of a +0.008 F1 move is the shape of an evaluation
bug, so it was chased before anything was reported (HANDOFF §7). Four things
were checked; **no bug was found, and the hunt produced §3.4, which is the most
important thing in this section.**

- **V5 above** rules out the wrapper.
- **The support is identical feature-for-feature.** Every eval-only feature has
  exactly the same `n_both_defined` in both campaigns — 630 / 207 / 166 / 50 /
  29 / 11 — so the section composition, the join and the NaN pattern are the
  same objects in both.
- **Retention and mean-absolute-difference move together, in both directions.**
  The features that gained retention lost MAD and the features that lost
  retention gained it: `redflag_DEMAND_WEAKNESS_rate_risk_factors` MAD
  0.1481 → 0.0692 with ρ 0.433 → 0.902; `redflag_MARGIN_COST_PRESSURE_rate_mda`
  MAD 0.1213 → 0.0948 with ρ 0.115 → 0.600; and against the trend
  `redflag_SUPPLY_INPUT_CONSTRAINT_rate_risk_factors` MAD 0.0283 → 0.0591 with
  ρ 0.976 → 0.919, `redflag_TRADE_POLICY_EXPOSURE_rate_mda` MAD 0.0223 → 0.0399
  with ρ 0.881 → 0.791. A join artifact does not produce that coherence.
- **Why chunk F1 and filing-level ρ can diverge, mechanically.** Pearson ρ over
  filing-level *rates* is invariant to a constant bias and is driven by whether
  the error is filing-dependent, not by how much error there is. The per-section
  chunk table (`h3v2_diagnostics_…json` → `M_chunk_level_eval_per_section`)
  shows exactly that: per-category F1 is genuinely mixed — RISK_FACTORS 1 up /
  5 down, MDA 1 up / 5 down, EX99_PRESS_RELEASE 4 up / 2 down — while the
  *net rate bias* (predicted minus support) shrinks where retention rose
  (RISK_FACTORS `DEMAND_WEAKNESS` −9 → −2; press `DEMAND_WEAKNESS` −29 → −18;
  press `__ANY__` −56 → −42). **Chunk-level F1 is not the statistic the features
  are made of, and this campaign is a clean demonstration of that.**

The hunt's real output was the question it forced: *if the student's chunk-level
skill barely moved, what did?* §3.4 answers it.

### 3.1 Retention, v1.2 student vs v1.2 teacher — pooled vs eval-only

Retention = correlation between the **student-derived** and **teacher-derived**
value of the same filing-level feature, over the 630-row E1 feature table, both
sides built by the same verbatim `features.py` machinery.

95% intervals are a **filing-clustered bootstrap, 4,000 draws, `seed=0`**,
resampling the feature table's rows (the unit the features live on) — the same
procedure, module and seed as H3. The red-flag family figure is the mean of the
12 per-feature correlations recomputed **within** each resample, so its interval
carries the cross-feature correlation.

| feature family | POOLED, n=630 rows / 6,746 chunks — **UPPER BOUND, 85.0% memorized** | EVAL-ONLY, n=630 rows / 1,010 held-out chunks — **the only unbiased slice** |
|---|---|---|
| `sentiment_negative_share` | **0.8126** P [0.6997, 0.9020] · **0.8278** S [0.7815, 0.8688] | **0.7833** P [0.6130, 0.8935] · **0.7311** S [0.6358, 0.8115] |
| `sentiment_mean_score` | **0.9137** P [0.8838, 0.9386] · **0.8887** S [0.8584, 0.9140] | **0.8696** P [0.8153, 0.9109] · **0.8032** S [0.7279, 0.8613] |
| 12 × `redflag_*_rate_*` (mean) | **0.8721** P [0.8402, 0.9060] · **0.8874** S [0.8648, 0.9045] | **0.8078** P [0.7503, 0.8528] · **0.7844** S [0.7075, 0.8377] |
| `redflag_any_rate_press` | 0.9126 P [0.8689, 0.9457] · 0.9147 S | 0.8744 P [0.8293, 0.9118] · 0.8661 S |
| `guidance_signed_mean` (n=56 / 11 defined rows) | **0.6248** P [0.3271, 0.8776] · 0.6322 S — **a real regression, see below** | 0.9359 P [0.7455, 1.0000] · 0.9069 S — **n=11, not a measurement** |
| `guidance_any_present` | 0.8610 P [0.7866, 0.9242] · 0.8610 S | 0.7534 P [0.5356, 0.9114] · 0.7534 S |
| 5 × composition features | **1.0000** (wiring check V3) | **1.0000** (wiring check V3) |

**All 12 red-flag features, eval-only, Pearson [95% CI]:**

| RISK_FACTORS (n=29 filings) | | MDA (n=50 filings) | |
|---|---|---|---|
| `IMPAIRMENT_WRITEDOWN` | 0.9744 [0.9381, 1.0000] | `IMPAIRMENT_WRITEDOWN` | 0.9275 [0.8549, 0.9790] |
| `TRADE_POLICY_EXPOSURE` | 0.9698 [0.9469, 0.9918] | `LEGAL_REGULATORY_ACTION` | 0.8077 [0.7093, 0.8896] |
| `SUPPLY_INPUT_CONSTRAINT` | 0.9189 [0.7546, 0.9702] | `TRADE_POLICY_EXPOSURE` | 0.7909 [0.5882, 0.9069] |
| `LEGAL_REGULATORY_ACTION` | 0.9159 [0.7972, 0.9590] | `SUPPLY_INPUT_CONSTRAINT` | 0.7187 [0.4858, 0.8952] |
| `DEMAND_WEAKNESS` | 0.9019 [0.8141, 0.9616] | **`MARGIN_COST_PRESSURE`** | **0.6000 [0.3515, 0.7664]** |
| `MARGIN_COST_PRESSURE` | 0.7443 [0.5444, 0.9421] | **`DEMAND_WEAKNESS`** | **0.4238 [0.1041, 0.6934]** |

**Zero of the twelve has a CI that includes zero** (H3 had two). The spread is
still wide — 0.424 to 0.974 — so **the family mean still hides the members**, and
H3 §3.5's hand-off item 3 (E2's report must carry per-feature retention, not a
family mean) stands unchanged.

**Four features retained *worse* than under v1.1**, and they are named rather
than averaged away: `redflag_SUPPLY_INPUT_CONSTRAINT_rate_mda` 0.8435 → 0.7187
(−0.125), `redflag_TRADE_POLICY_EXPOSURE_rate_mda` 0.8812 → 0.7909 (−0.090),
`redflag_SUPPLY_INPUT_CONSTRAINT_rate_risk_factors` 0.9764 → 0.9189 (−0.058),
`redflag_IMPAIRMENT_WRITEDOWN_rate_risk_factors` 0.9888 → 0.9744 (−0.014).

**`guidance_signed_mean` is a real pooled regression: 0.8884 → 0.6248
[0.3271, 0.8776].** Cause, measured: the v1.2 student omits the
`guidance_direction` field on **385** chunks against v1.1's **321** (manifest
`guidance_direction.failure_attribution.__MISSING_FIELD__`), and chunk-level
guidance exact match falls 0.7028 → 0.6473 pooled and 0.5877 → 0.5211 on the
eval slice. The feature-level damage is bounded because only 56 of 630 filings
have a defined `guidance_signed_mean` at all, and the eval-slice figure rests on
**11 filings and is not a measurement**. This is the one place where §1.8 caveat
5 has teeth: the missing→NONE post-rule is a no-op for the *features* (V4) but
the underlying field-omission rate got **worse**, and if that post-rule is ever
adopted it would convert 385 omissions into asserted `NONE`s.

**NaN patterns barely move, exactly as in H3.** For every feature except
`guidance_signed_mean` the defined/undefined pattern is **identical** between
the v1.2 teacher and the v1.2 student in both slices. `guidance_signed_mean`
flips on 3 teacher-only + 4 student-only rows of 630 on the eval slice (v1.1:
4 + 4) and 7 + 9 pooled (v1.1: 7 + 8).

### 3.2 Which slice should the owner believe? The matched-composition control, re-run on v1.2

Pooled is optimistic (memorization). Eval-only could in principle be pessimistic
for a different reason: its 1,010 chunks spread thinly over 630 filings, so each
rate is a mean over fewer chunks and per-filing sampling noise inflates on
**both** sides, dragging the correlation down. As in H3, that objection was
tested, not assumed.

Control, H3 §3.2's procedure exactly: draw from the student's **train** chunks a
sample matched to the eval split's per-`section_type` counts
(`{8K_BODY: 8, EX99_PRESS_RELEASE: 570, MDA: 297, RISK_FACTORS: 135}` → 1,002 of
1,010; all 8 `8K_BODY` chunks are in eval so none are available, and `8K_BODY`
is non-evaluable anyway, §1.8 caveat 4), **5 seeds**. That sample is **thin like
eval and memorized like the bulk of the corpus**, so it isolates the thinness.

| feature | pooled (thick, 85% memorized) | matched-train (thin, memorized) | eval (thin, unmemorized) | attributable to thinness | attributable to non-memorization |
|---|---|---|---|---|---|
| 12 × `redflag_*` mean | 0.8721 | **0.8452** | 0.8078 | **−0.0269** | **−0.0374** |
| `sentiment_negative_share` | 0.8126 | **0.8884** | 0.7833 | **+0.0758** | **−0.1051** |
| `sentiment_mean_score` | 0.9137 | **0.9173** | 0.8696 | +0.0036 | −0.0477 |
| `redflag_any_rate_press` | 0.9126 | **0.9357** | 0.8744 | +0.0231 | −0.0613 |
| `guidance_any_present` | 0.8610 | **0.9118** | 0.7534 | +0.0508 | −0.1584 |

**The conclusion is the same as H3's, and the magnitude is much smaller.** Thin
composition does not explain the eval-only drop: for four of the five families it
works in the *opposite* direction, and for the red-flag family it accounts for
0.027 of a 0.064 gap. But the gap itself has collapsed — **the red-flag family's
memorization penalty is 0.037 for the v1.2 student against H3's 0.174 for the
v1.1 student.** The pooled/eval bracket is now [0.808, 0.872] where H3's was
[0.669, 0.867]. **The eval-only column remains the honest estimate**, and it is
now close enough to pooled that the choice of slice no longer drives the answer
for the red-flag family — though it still does for `guidance_any_present`
(0.861 → 0.753) and `sentiment_negative_share` (0.813 → 0.783).

The price of the unbiased slice is still width: **29 filings** carry a
RISK_FACTORS rate and **50** carry an MDA rate, which is why every eval-only
number above ships with its interval.

H3 §3.2 also published an "indicative bridge" (Fisher-z composition of the two
effects). **It is deliberately not reproduced here.** H3 flagged it as false in a
known direction for the two press-driven features, and §3.4 below supersedes it
with a measured decomposition of the thing the owner actually needs to know.

### 3.3 THE COMPARISON TABLE — v1.2 eval-only beside H3's ruled v1.1 values

**FRAMING RULE (repeated, per §1.8 caveat 8): each column is a student measured
against ITS OWN teacher.** The two columns are not two scores on one yardstick.
Both slices are the same 630 filings and the same 1,010 held-out chunks (the
split is byte-identical, §3.0), and both intervals are the same filing-clustered
bootstrap, 4,000 draws, seed 0 — so the *procedure* is like-for-like even though
the *estimand* is not.

| feature / family, EVAL-ONLY (Pearson) | H3 v1.1 (ruled) | H3v2 v1.2 | Δ (paired, §3.4) |
|---|---|---|---|
| 5 × composition | 1.000 | **1.0000** [exact] | 0 — label-independent |
| `sentiment_mean_score` | 0.834 [0.773, 0.886] | **0.8696** [0.8153, 0.9109] | +0.0354 [−0.0122, +0.0879] |
| `sentiment_negative_share` | 0.592 [0.408, 0.759] | **0.7833** [0.6130, 0.8935] | **+0.1911** [+0.0394, +0.3566] |
| 12 × `redflag_*_rate_*` (mean) | 0.669 [0.586, 0.742] | **0.8078** [0.7503, 0.8528] | **+0.1385** [+0.0747, +0.2000] |
| `redflag_any_rate_press` | 0.622 [0.461, 0.767] | **0.8744** [0.8293, 0.9118] | **+0.2521** [+0.1050, +0.4139] |
| worst member — `MARGIN_COST_PRESSURE_rate_mda` | 0.115 [−0.109, 0.386] | **0.6000** [0.3515, 0.7664] | **+0.4855** [+0.1928, +0.6895] |
| worst member — `DEMAND_WEAKNESS_rate_mda` | 0.215 [−0.075, 0.518] | **0.4238** [0.1041, 0.6934] | +0.2094 [−0.0260, +0.4124] |
| # of 12 red-flag features with CI including 0 | **2** | **0** | — |
| pooled upper bound, 12 × `redflag_*` | 0.867 | 0.8721 | — |

The Δ column is a **paired** filing-clustered bootstrap: the *same* 4,000 filing
resamples are applied to both campaigns' feature tables, which removes the
shared filing-level sampling noise that two marginal intervals cannot. Comparing
the marginal CIs instead is valid but far more conservative — on that reading
only the 12-flag family and `redflag_any_rate_press` separate, while
`sentiment_negative_share`, `sentiment_mean_score`, `MARGIN_mda` and
`DEMAND_mda` all overlap.

### 3.4 What actually moved: the 2×2 teacher/student decomposition

The +0.1385 family gain has two candidate explanations and §1.8 caveat 8 says to
name which is being claimed: **a better student, or an easier teacher.** Both
were measured, on the same 630 filings, by crossing the two students with the
two teachers (`h3v2_diagnostics.py` → `X_cross_pairing_2x2`) and bootstrapping
each contrast on the same 4,000 resamples (`h3v2_paired_delta_ci.py`).

**Levels, eval-only Pearson, 12-flag family mean [95% CI]:**

| | v1.1 teacher | v1.2 teacher |
|---|---|---|
| **v1.1 student** | 0.6694 [0.5857, 0.7420] *(= H3)* | 0.7597 [0.6666, 0.8220] |
| **v1.2 student** | 0.7611 [0.6987, 0.8254] | **0.8078** [0.7503, 0.8528] *(= H3v2)* |

**The single most consequential number in this section: the OLD v1.1 student
tracks the NEW v1.2 teacher (0.7597) better than it tracks its own teacher
(0.6694).** The rubric change alone, with the model held completely fixed, is
worth **+0.0904 [+0.0274, +0.1401]** on the 12-flag family.

**Paired deltas, eval-only, Pearson [95% CI], P(>0) over 4,000 draws:**

| | 12-flag family | `sentiment_negative_share` | `sentiment_mean_score` | `redflag_any_rate_press` | `MARGIN_mda` | `DEMAND_mda` |
|---|---|---|---|---|---|---|
| **TOTAL** v1.2 − v1.1 | +0.1385 [+0.0747, +0.2000] | +0.1911 [+0.0394, +0.3566] | +0.0354 [−0.0122, +0.0879] | +0.2521 [+0.1050, +0.4139] | +0.4855 [+0.1928, +0.6895] | +0.2094 [−0.0260, +0.4124] |
| **TEACHER arm**, student held at v1.1 | +0.0904 [+0.0274, +0.1401] | +0.0344 [−0.0264, +0.1282] | −0.0039 [−0.0274, +0.0191] | +0.2347 [+0.0904, +0.3973] | +0.4197 [+0.0936, +0.6531] | +0.1362 [−0.1080, +0.3506] |
| **STUDENT arm**, teacher held at v1.1 | +0.0917 [+0.0449, +0.1516] | +0.1374 [+0.0099, +0.2924] | +0.0330 [−0.0086, +0.0818] | −0.0158 [−0.0592, +0.0279] | +0.3279 [+0.1315, +0.5803] | −0.0086 [−0.1108, +0.1097] |
| **TEACHER arm**, student held at v1.2 | +0.0467 [−0.0206, +0.1024] | +0.0537 [−0.0135, +0.1594] | +0.0024 [−0.0220, +0.0293] | +0.2679 [+0.1290, +0.4200] | +0.1575 [−0.1890, +0.4124] | +0.2180 [+0.0201, +0.3970] |
| **STUDENT arm**, teacher held at v1.2 | **+0.0481** [+0.0096, +0.1015] | **+0.1566** [+0.0287, +0.3143] | +0.0392 [−0.0033, +0.0881] | +0.0174 [−0.0231, +0.0648] | +0.0657 [−0.0453, +0.1891] | +0.0732 [−0.0106, +0.2043] |

**How to read it.** The arms are not orthogonal and do not sum to TOTAL: each
factor's marginal effect on the 12-flag family is ≈+0.09 when applied first and
≈+0.05 when applied second. The honest summary is that **the rubric repair and
the student repair are worth roughly the same amount, about half each, and they
overlap.** Per feature:

- **12-flag family.** The repaired student's own contribution, with the teacher
  held fixed at v1.2 — the configuration an E2 labeler would actually run in —
  is **+0.0481 [+0.0096, +0.1015]**. Real, distinguishable from zero, and
  **about one third of the +0.1385 headline move.**
- **`sentiment_negative_share` is the clean student win.** +0.1566
  [+0.0287, +0.3143] from the student at the v1.2 teacher; the teacher arm
  (+0.0537 [−0.0135, +0.1594]) is not distinguishable from zero. The feature H3
  singled out as the weakest is the one the repair most improved.
- **`redflag_any_rate_press` is entirely the teacher.** Teacher arm +0.2679
  [+0.1290, +0.4200]; student arm **+0.0174 [−0.0231, +0.0648]**, indistinguish-
  able from zero, and *negative* (−0.0158) at the v1.1 teacher. The 0.622 → 0.874
  headline is a property of rubric v1.2's press-release labels, **not** of the
  repaired student. Corroboration: the two teachers' own press feature correlate
  at only **0.6481 [0.4754, 0.8007]** with each other — i.e. **the two rubrics
  disagree with each other on this feature more than the v1.2 student disagrees
  with the v1.2 teacher (0.8744).**
- **`MARGIN_COST_PRESSURE_rate_mda`, H3's most-destroyed feature, recovers
  mostly for teacher reasons.** Teacher arm at the v1.1 student +0.4197
  [+0.0936, +0.6531]; student arm at the v1.2 teacher +0.0657
  [−0.0453, +0.1891], not distinguishable from zero. Mechanism named in advance
  by the label shift: v1.2 added **+294 rows / +16.9%** to
  `MARGIN_COST_PRESSURE` (`LABEL_SHIFT_v11_v12.md` §2), and the chunk-level MDA
  recall for that category actually **fell** 0.746 → 0.681. **Reporting
  "0.115 → 0.600, the repair fixed the worst feature" would have been wrong.**
- **`DEMAND_WEAKNESS_rate_mda`** stays the weakest member (0.4238
  [0.1041, 0.6934]); neither arm is distinguishable from zero at the other
  factor's v1.2 level.
- **`sentiment_mean_score` did not move** on any arm — TOTAL +0.0354
  [−0.0122, +0.0879] includes zero.

**Scale for reading all of the above:** teacher-v1.1 vs teacher-v1.2 retention
on the eval slice — how far the rubric alone moved the *teacher-derived* feature
table — is 12-flag family **0.8642**, `sentiment_negative_share` **0.9034**,
`sentiment_mean_score` **0.9588**, `redflag_any_rate_press` **0.6481**,
`MARGIN_mda` **0.5398**, `DEMAND_mda` **0.8307**. Wherever that number is low,
the two campaigns are furthest from measuring the same thing.

### 3.5 The kill-criterion-2 read

**Is kill-criterion 2's band (materially below ρ≈0.57 sentiment / ρ≈0.81
red-flag family) breached on the unbiased slice?** H5 leaves the numeric
threshold to the G1 ruling; measured against the band as written, per family,
CI-vs-band, **pooled never used to clear a gate**:

- **ρ≈0.57 (sentiment) — NOT breached, and now cleared with margin.**
  `sentiment_negative_share` eval-only **0.7833**, 95% CI **[0.6130, 0.8935]**,
  which lies **entirely above 0.57**. Under v1.1 the point estimate was 0.592
  with a CI [0.408, 0.759] that *straddled* the band; under v1.2 the band is
  excluded from below. `sentiment_mean_score` 0.8696 [0.8153, 0.9109] is far
  above it. Attribution (§3.4): this one is **the student**, +0.1566
  [+0.0287, +0.3143] with the teacher held fixed.
- **ρ≈0.81 (red flags) — NOT breached, but NOT cleared either: the estimate sits
  ON the band.** 12-flag family eval-only **0.8078**, 95% CI
  **[0.7503, 0.8528]**, which **contains 0.81**; the point estimate is 0.0022
  *below* the band. The correct statement is *not distinguishable from ρ=0.81 in
  either direction* on 630 filings. Under v1.1 the CI [0.586, 0.742] **excluded**
  0.81 and the criterion was breached. Spearman gives the same reading: 0.7844
  [0.7075, 0.8377], contains 0.81. The pooled figure (0.8721 [0.8402, 0.9060])
  is the 85%-memorized upper bound and **is not used to clear this gate.**
  Attribution (§3.4): roughly half the move to the band is the rubric, not the
  student — with the teacher held at v1.2 the student is worth **+0.0481
  [+0.0096, +0.1015]**, and the *old* student against the *new* teacher already
  scores 0.7597 [0.6666, 0.8220], whose CI also contains 0.81.
- **Per-feature worst members — materially better, still not uniform.** No
  red-flag feature retains nothing: **0 of 12 have CIs including zero**, against
  H3's 2 of 12. The weakest are `redflag_DEMAND_WEAKNESS_rate_mda` **0.4238
  [0.1041, 0.6934]** and `redflag_MARGIN_COST_PRESSURE_rate_mda` **0.6000
  [0.3515, 0.7664]**, and both of their CIs still overlap H3's for the same
  feature. The family mean of 0.8078 spans members from 0.424 to 0.974.
- **The chunk-level instrument disagrees with the feature-level one, and this is
  reported rather than reconciled away.** Held-out `red_flags` micro F1 moved
  +0.008 and exact-set (category+modality) moved **−0.018**; `guidance_direction`
  exact match moved **−0.067**. The features improved; the chunk-level labels
  did not. §3.0a explains the mechanism (Pearson over rates is blind to constant
  bias). **Whichever instrument G1 weights, it should be named explicitly,
  because they point different ways.**

### 3.6 What was deliberately NOT run: the IC-delta backtest arm

**The E1 backtest was not re-run on the v1.2 labels, and this is a decision, not
an omission.** H3 §3.4 measured that E1's 6-fold design cannot see attenuation
at all: sweeping XGBoost's `random_state` over 100 values on identical frames,
folds and dedup mask, the paired student-minus-teacher dedup-IC-delta is centred
at −0.0044 (primary spec) / +0.0136 (secondary) with a **nuisance SD of 0.028**
and it changes sign on 44% / 25% of seeds, while the entire between-labeler
difference was ≤0.029 and H2's honest MDE for the design is **0.032–0.085**. A
v1.2 re-run would produce another draw from that same nuisance distribution and
**would add no G1 information in either direction** — an absence of IC-delta
degradation is not evidence the labeler is fit for purpose, and a presence of it
would not be distinguishable from the seed. H3 §3.4 also noted the perverse
direction: noisier text makes the full model resemble the numeric-only model,
shrinking the delta's sampling noise, so the IC delta is the wrong instrument
for reading attenuation.

**The owner can order it separately**; the machinery exists
(`data/hardening/h3_backtest.py`, `h3_seed_sensitivity.py`) and would need only
the two v1.2 feature tables this section already wrote. Anything it produced
would have to carry the seed-nuisance band beside the point estimate (H3 §3.5
hand-off item 2), and — separately — **E1 and E2 backtest numbers are
numerically incomparable** (different benchmark: E2 uses equal-weighted
excl-self, membership-dated), which must be stated wherever both appear.

Also not run, deliberately: `distress_tier` was never compared (§1.7 — never a
training target, uniformly empty in the student artifact); `8K_BODY` (n=8, all
in eval, 2 tickers) and `guidance_direction=WITHDRAWN` (n=1, in train) carry no
evaluable per-class estimate (§1.8 caveat 4) and appear in no headline table
here — `share_chunks_8k_body` appears only as a wiring check, and its
matched-composition control row is undefined by construction because all 8
chunks are in eval.

### 3.7 Carried caveats, attached where they bite

1. **Pooled is an upper bound, not an estimate.** 5,736/6,746 = **85.0%** of
   pooled chunks are the student's own training rows. Every pooled figure in
   §3.1–3.2 is labelled as such, and no pooled figure is used to clear a gate
   in §3.5.
2. **Retention and agreement are vs the teacher, NOT accuracy.** A perfectly
   agreeing student has reproduced the teacher including its errors.
3. **The v1.2 teacher's own error rate is UNMEASURED.** The second-rater
   spot-check (2026-08-18) was run against **rubric v1.1** labels; its constants
   — 36.6% set-level / ~25% base-rate / 7.5% per-category / sentiment 94.6% /
   guidance 95.2% — are **v1.1 figures**. `e1_relabel_manifest_v12.json` copies
   that `teacher_noise_floor` block forward verbatim; **it is not a measurement
   of the v1.2 teacher and must not be quoted as one.** Rubric v1.2 changed
   `red_flags` on 27.48% of rows, so the v1.1 error rate does not transfer in
   either direction. §3.4's finding compounds this: the two rubrics' teacher
   feature tables correlate at 0.6481 on `redflag_any_rate_press` and 0.5398 on
   `MARGIN_mda`, so at least one of the two teachers is substantially wrong on
   those features and nothing here says which.
4. **8K_BODY (n=8, 2 tickers) and WITHDRAWN (n=1, in train) are not evaluable** —
   §3.6.
5. **The guidance missing→NONE post-rule is PROPOSED, NOT ADOPTED**, and is
   verified (V4) to remain a no-op for every feature. It is **not** a no-op for
   the chunk-level guidance rate, and the underlying omission count got worse
   (321 → 385 chunks) — §3.1.
6. **`data/labels.parquet` is frozen and untouched**; both relabel artifacts are
   second labelers' outputs, never replacements. Re-verified by sha256 after
   every script (§3.0).
7. **The comparison teacher is `data/labels_v12.parquet`** throughout §3.1–3.2
   and §3.5; §3.3–3.4 are explicit about which teacher each number uses.
8. **Cross-rubric comparison is INSTRUMENT-VS-INSTRUMENT** — the framing rule at
   the top, and the whole reason §3.4 exists.
9. **14 of the 6,746 prompts are not token-identical to E1's** (2 train / 12
   eval = **1.19% of the eval slice**), head-truncation length only (§1.6). Not
   corrected for anywhere below; it is small relative to every interval here but
   it is a real, unmodelled difference between the two campaigns' eval slices.
10. **The v1.2 teacher arm does not reproduce `data/features.parquet`** and must
    not — verified as expected-FALSE (§3.0, 1,670 text cells differ).
11. **Row order preserved** in all six builds (§3.0).

### 3.8 Bottom line for gate G1

On the only unbiased slice (n=1,010 held-out chunks over 630 filings, 95%
filing-clustered bootstrap CIs, 4,000 draws, seed 0, same procedure as H3), the
repaired v1.2 student retains **0.8078 [0.7503, 0.8528]** of its teacher's
12-feature red-flag block, **0.7833 [0.6130, 0.8935]** of
`sentiment_negative_share`, **0.8696 [0.8153, 0.9109]** of
`sentiment_mean_score`, and **1.0000** of the five composition features
(label-independent by construction). No red-flag feature retains nothing: 0 of
12 CIs include zero, against H3's 2 of 12, with the weakest members
`DEMAND_WEAKNESS_rate_mda` **0.4238 [0.1041, 0.6934]** and
`MARGIN_COST_PRESSURE_rate_mda` **0.6000 [0.3515, 0.7664]**. The pooled figures
(0.8721 / 0.8126 / 0.9137) are 85% memorized and are an upper bound; a
matched-composition control (5 seeds, eval-matched section counts) shows the
pooled/eval gap for the red-flag family is 0.027 thinness and 0.037
memorization, against H3's 0.024 and 0.174 — **the memorization penalty
collapsed by a factor of ~4.7.**

Against H3's ruled v1.1 values — **each student measured against its own
teacher, not two scores on one yardstick** — the 12-flag family moved
**0.669 → 0.808**, paired Δ +0.1385 [+0.0747, +0.2000];
`sentiment_negative_share` **0.592 → 0.783**, Δ +0.1911 [+0.0394, +0.3566]; and
kill-criterion 2 flips from **breached** to **not breached** for the red-flag
family. But the 2×2 decomposition says the credit is split: with the teacher
held fixed at v1.2, **the repaired student is worth +0.0481 [+0.0096, +0.1015]
on the family** — about a third of the headline move — while the *unchanged
v1.1 student* already scores 0.7597 [0.6666, 0.8220] against the v1.2 teacher.
`redflag_any_rate_press`'s 0.622 → 0.874 is **entirely** the rubric (student arm
+0.0174 [−0.0231, +0.0648]), and `MARGIN_COST_PRESSURE_rate_mda`'s 0.115 → 0.600
is **mostly** the rubric (student arm +0.0657 [−0.0453, +0.1891]) — for that
category v1.2 added +294 rows and the student's chunk-level MDA recall actually
*fell* 0.746 → 0.681. `sentiment_negative_share` is the one clean student win
(+0.1566 [+0.0287, +0.3143]). And at the chunk level the student barely moved at
all: held-out `red_flags` micro F1 +0.008, exact-set category+modality **−0.018**,
`guidance_direction` exact match **−0.067**.

So the G1 decision reduces to a judgement the owner alone can make, now with the
confound measured rather than assumed: **the E2 text block's largest feature
family sits at ρ=0.81 — on the band, its CI containing it, not distinguishable
from it in either direction — and roughly half of the improvement that put it
there came from the rubric moving the target rather than from the student
tracking it better.** The IC-delta arm was deliberately not re-run because H3
§3.4 showed E1's 6-fold design cannot see attenuation of any plausible size
(nuisance SD 0.028 vs MDE 0.032–0.085); it can be ordered separately. And the
attenuation is still attenuation of a target whose own error is **unmeasured
under rubric v1.2** — the 36.6%/25%/7.5% teacher-noise constants belong to v1.1
and are carried forward in the manifest without having been re-measured.

**Three items this section hands forward (not decided here):**
1. H3 §3.5's three G3 items stand unchanged — pin a deterministic row order,
   report the primary metric with a measured seed-nuisance band, and carry
   **per-feature** retention rather than a family mean (0.424 to 0.974 here).
2. **New: any cross-rubric retention claim must ship its teacher-arm control.**
   The v1.1-student × v1.2-teacher cell is cheap (no new labeling, no GPU) and
   it is the difference between "the repair worked" and "the target moved."
3. **New: the v1.2 teacher has no second-rater error estimate.** If red-flag
   retention against it is going to carry a gate, the spot-check that produced
   §3.7 caveat 3's constants needs a v1.2 re-run, or the constants need to stop
   travelling with v1.2 artifacts.

**Not done here, deliberately:** `HARDENING_PROGRESS.md`, `HANDOFF.md`,
`F3_PROGRESS.md` and `RESUME_HERE.md` were not edited; sections 1 and 2 of this
file were not touched; no E2-labeler decision was made (that is G1, the
owner's); no third-epoch or re-label recommendation is made; `features.py`,
`backtest.py`, `spec.py`, H3's three analysis modules and every frozen artifact
are untouched and re-verified by sha256.
