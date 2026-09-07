# H3 — labeler attenuation check

**Item:** `HARDENING_PROGRESS.md` H3. **This file has three sections.**
Section 1 (implementation) is DONE, 2026-08-25, by the finetune-engineer.
Section 2 (the run) is appended by the MAIN SESSION when the overnight
finishes. Section 3 (the comparison) is appended by quant-modeler.
**Do not treat the item as done until all three exist.**

Cost: **$0**, zero Anthropic API calls (HANDOFF §5). All compute is local MLX.

---

## 1. Implementation — DONE 2026-08-25

### 1.1 What was built

| Path | Role |
|---|---|
| `/Users/vihanpatil/personal/projects/FinScreen/finetune/relabel_e1.py` | the segmented, resumable relabel runner (3 modes: `--write-sidecar`, generate, `--finalize-only`) |
| `/Users/vihanpatil/personal/projects/FinScreen/finetune/test_relabel_e1.py` | 20 offline tests — no model, no GPU, no network. `python3 -m pytest finetune/test_relabel_e1.py -q` → **20 passed** |
| `/Users/vihanpatil/personal/projects/FinScreen/data/hardening/e1_relabel_sidecar.json` | written; the corpus↔mlx_data verification + the frozen canonical row order (6,746 chunk_ids) |
| `/Users/vihanpatil/personal/projects/FinScreen/data/hardening/smoke/` | the 10-chunk smoke (journal + parquet + manifest) |
| `/Users/vihanpatil/personal/projects/FinScreen/data/hardening/smoke_resume/` | the resume smoke (torn journal → resumed to 10/10) |

Not yet existing (the run produces them):
`data/hardening/e1_relabel_student.jsonl` (journal),
`data/hardening/e1_relabel_student.parquet` (the deliverable),
`data/hardening/e1_relabel_manifest.json`, `data/hardening/e1_relabel.log`.

Nothing in `finetune/eval.py`, `finetune/convert_to_mlx.py`, `features.py`,
`backtest.py` or any frozen artifact was edited. `data/labels.parquet` is
opened **read-only** and its sha256 was re-verified unchanged after the smoke
(`c3531f03cda602bc…`, pinned by a test).

### 1.2 The exact run command (MAIN SESSION only, HANDOFF §4)

Three steps. Step 0 is already done; step 1 is the overnight; step 2 takes
seconds and loads no model.

```bash
# step 0 — sidecar (system python3; DONE 2026-08-25, re-run only if a
#          frozen artifact ever moves)
cd /Users/vihanpatil/personal/projects/FinScreen
python3 finetune/relabel_e1.py --write-sidecar

# step 1 — GENERATE. Main-session BACKGROUND task (run_in_background).
#          Never launched from a subagent shell.
caffeinate -dims \
  /Users/vihanpatil/personal/projects/FinScreen/finetune/.mlx_venv/bin/python \
  /Users/vihanpatil/personal/projects/FinScreen/finetune/relabel_e1.py \
  >> /Users/vihanpatil/personal/projects/FinScreen/data/hardening/e1_relabel.log 2>&1

# step 2 — FINALIZE (system python3; journal -> parquet + manifest, no GPU)
cd /Users/vihanpatil/personal/projects/FinScreen
python3 finetune/relabel_e1.py --finalize-only
```

No flags are needed: the defaults are the epoch-2 adapter
(`finetune/checkpoints/qwen2.5-7b-finscreen-lora-mlx-epoch2`), the epoch-2
training manifest (`finetune/runs/2026-08-21-epoch2/manifest.json`),
`--max-tokens 520`, greedy, `--out-dir data/hardening`.

Use the `>> … 2>&1` redirect, **not** `| tee`: a pipe would hand back tee's
exit status and the chain could not tell "done" from "resume me". Live
progress: `tail -f data/hardening/e1_relabel.log`.

**Before launching:** `ps aux | grep mlx_lm | grep -v grep` must be empty —
nothing else may be on the GPU.

### 1.3 Resume semantics (this is the load-bearing ops property)

- **Exit 0** = every target row is in the journal → go to step 2.
  **Exit 2** = partial → **re-run the identical step-1 command**. Finished rows
  are skipped; nothing is regenerated.
- Every row is `write` + `flush` + `fsync` to
  `data/hardening/e1_relabel_student.jsonl` before the next row starts. A
  SIGTERM/`kill -9` at any instant loses **at most the in-flight row** (~2.7 s).
- A torn final line from a `kill -9` is ignored on read **and terminated with a
  newline before the next append** — see the bug in §1.5; without that repair a
  resume silently loses one good row per kill.
- Every journal row stores the sha256 of the exact prompt token sequence it was
  generated from. If the data or the rendering ever changed under a resume, the
  run **stops hard** rather than mixing two prompt versions into one artifact
  (`eval.select_rows_to_generate`, reused verbatim; pinned by a test).
- The labels are **resume-invariant**: verified byte-identical across a
  single-pass run and a resumed run (§1.5). Per-row telemetry (`latency_s`,
  `labeled_at`) is not, so the parquet's sha256 is a provenance stamp of the
  run, not a content hash of the labels.
- `--max-rows-per-segment N` exists if the main session prefers voluntary
  segment exits over waiting for a kill; default 0 = run until done or killed.
  Cost per extra segment: one model load (1.3–1.5 s warm) + the prompt
  re-render pre-pass, **measured at 12.3 s for all 6,746 rows**.
- Re-running after completion is a no-op: it never loads the model.

### 1.4 Projected wall-clock

Measured inputs (not guessed): epoch-2 eval manifest — prefill **841.5 tok/s**,
decode **28.1 tok/s**, generation **36.3 tokens/row** mean, overhead factor
**1.033** (2,718.8 s actual vs 2,632 s modelled on 1,010 rows). Prompt tokens
for the full corpus are exact from the conversion report: train
5,732,033 − 212,117 = **5,519,916** + eval **1,116,622** = **6,636,538** —
independently re-measured by rendering all 6,746 prompts with the real
tokenizer: **6,636,538 exactly** (12.3 s, no GPU, no generation).

| component | seconds | hours |
|---|---|---|
| prefill 6,636,538 tok @ 841.5 tok/s | 7,887 | 2.19 |
| decode 6,746 × 36.3 tok @ 28.1 tok/s | 8,715 | 2.42 |
| × 1.033 measured overhead | 17,150 | **4.76** |

### **Point estimate ≈ 4.8 h. Band 4.6–5.6 h.**

Sensitivity: decode at 25 tok/s → 5.1 h; answers 45 tok instead of 36.3 →
5.4 h; the naive 6,746 / 1,337.4 chunks-per-hour anchor → 5.04 h (conservative,
because train prompts are shorter than eval prompts: 962 vs 1,106 tokens).
At ~1,300 chunks/h a one-hour kill window covers ~1,300 rows, so expect
**roughly 5–6 segments**; each kill costs ≤1 row plus a ~1.5 s model reload.

Stop the run and report it as the finding if progress lines start showing
`finish=length` with `gen_tok` near 520 — that is a non-terminating model, not
a slow one.

### 1.5 Smoke-test result (the only compute run here: 14 rows total)

`--split eval --limit 10`, into `data/hardening/smoke/`:

- **10/10 rows generated**, all `finish_reason=stop`, 0 parse failures,
  0 schema violations, 1,242 chunks/h in-segment, model load 1.5 s.
- **10/10 raw outputs byte-identical to `finetune/runs/2026-08-22-eval-epoch2/predictions.jsonl`.**
  This is the verify-artifact check (HANDOFF §7): the runner reproduces the
  artifact that was actually tested at the epoch-2 eval, prompt-for-prompt and
  token-for-token. It is computed automatically on every finalize
  (`reproduction_check` in the manifest) and will cover all 1,010 eval rows on
  the real run.
- Parquet built: **10 rows × 37 columns**, first 31 columns byte-compatible
  with `data/labels.parquet`'s arrow schema; a `features.py`-shaped read
  (filter `parse_ok`, iterate `red_flags`) works over it.
- The student's labels genuinely differ from the teacher's — 6 of the 10 rows
  differ on sentiment and/or red_flags — so this is a real relabel, not a copy.
  (n=10: the smoke's agreement rates are **not** a result.)
- Finalize is idempotent: run twice, identical parquet sha
  (`403004775b9949c3…`).

**Resume smoke** (`data/hardening/smoke_resume/`): truncated the journal to 6
rows and appended a torn fragment, then re-ran the identical command.

- **A real bug surfaced and was fixed.** The first attempt finished 9/10, not
  10/10: `load_predictions` ignores a torn final line on *read*, but appending
  onto a fragment with no trailing newline **glues the next good record to it**,
  so the resume lost one finished row per kill. Fix:
  `relabel_e1.ensure_trailing_newline()` terminates the fragment before the
  first append (idempotent on a healthy journal), pinned by a test. Re-run:
  **10/10, exit 0.**
- **Resume-invariance verified: 10/10 raw outputs byte-identical** to the
  single-pass run, and 10/10 prompt shas identical.
- **Latent issue flagged, not fixed:** `finetune/eval.py::mlx_generate` has the
  same append-after-torn-line pattern (eval.py line ~1424). Its campaign is
  over and its artifacts are complete, so it was deliberately **not** edited —
  editing the evaluator of record would disturb a tested artifact. If eval.py
  is ever re-run under a kill-prone chain, port the two-line repair.

### 1.6 Provenance chain (all verified before a token is generated)

1. `mlx_data/{train,valid}.jsonl` sha256 == the **epoch-2 training manifest's**
   (`d4dc4ec8…`, `deb63b76…`) — else hard stop.
2. The same shas == the sidecar's — else hard stop (the data moved after the
   corpus verification).
3. Sidecar: the 6,746 rendered rows are **exactly** `labels.parquet`'s labeled
   set (`parse_ok`), the one excluded chunk is `CHK-8e69547e0900a8dd`, and
   **every rendered passage is a head-prefix of its `labeling_corpus.parquet`
   text** — 6,695 identical, 51 head-truncated to fit 2,048, **0 non-prefix**.
4. Adapter: `eval._adapter_provenance` re-reads `adapter_config.json` and
   refuses a different base model, a non-LoRA type or a different
   `max_seq_length`; hashes `adapters.safetensors`
   (`9c08e3cb3f1f917c…`, the epoch-2 adapter) and all 57 numbered checkpoints.
5. Instruction sha256 `ebc45a856bff58a5…` — identical across all 6,746 rows and
   equal to the epoch-2 eval manifest's.
6. Base weights `86110f368236b53c…` (from the training manifest).

**Prompt-rendering exactness** is by construction, not by restatement: rows are
the rendered records the trainer consumed, and the prompt is
`eval.render_prompt_token_ids` → `convert_to_mlx.to_messages()` +
`convert_to_mlx.render()`, sliced at the generation-prompt offset. Per row it
re-asserts that `to_messages(instruction, passage, answer)` reproduces the
stored messages. system=instruction / user=passage, nothing appended.
Look-ahead-safe: the prompt contains only the passage; no ticker, date, or
outcome enters. Decoding is greedy (temp 0.0 → argmax), `max_tokens 520` —
identical to the epoch-2 eval.

**Why rows come from `mlx_data` rather than being re-rendered from
`labeling_corpus.parquet`:** 51 passages were head-truncated at conversion time
to fit `max_seq_length 2048`. Re-rendering with a different truncation budget
would put exactly the longest rows outside the length regime the student was
trained in and would break byte-identity with the epoch-2 eval. The corpus
provenance is therefore **verified** (step 3 above) rather than bypassed. Small
documented residual: for those 51 rows the kept passage length depended on the
teacher answer's token count at conversion time; that affects how much text is
kept, never the student's prompt content. An E2/F4 labeler over unlabeled text
will need a fixed answer-token reserve instead — a small documented extension
point, deliberately not built here (YAGNI).

### 1.7 Output schema — designed for a trivial downstream join

`data/hardening/e1_relabel_student.parquet`, chunk_id-keyed, in
`labeling_corpus.parquet` row order, **37 columns**:

- **Columns 1–31 are `data/labels.parquet`'s arrow schema, copied from the file
  itself rather than re-declared** (`pq.read_schema(LABELS_PARQUET)`), so the
  types match field-for-field — including
  `red_flags: list<struct<category,modality>>`. The 16 corpus columns are
  identical values to `labels.parquet`'s (verified). The feature join is a path
  swap: `features.py` reads `chunk_id`, `section_type`, `sentiment`,
  `guidance_direction`, `red_flags` and filters `parse_ok`, and all five behave
  the same here.
- Repurposed provenance columns (same names, student values):
  `api_result_type='student_local_mlx'`, `batch_id='H3-e1-relabel-epoch2'`,
  `stop_reason`=MLX finish_reason, `output_tokens`=generation tokens,
  `max_tokens_used=520`, `labeling_config='student=qwen2.5-7b-finscreen-lora-mlx-epoch2,backend=mlx,decoding=greedy(temp=0.0),max_tokens=520'`,
  `raw_label_json`=the model's raw text.
- **6 student-only columns appended:** `split` (train/eval),
  `passage_was_head_truncated`, `prompt_tokens`, `prompt_sha256`, `latency_s`,
  `schema_issues`.

`distress_tier` is **uniformly empty** — it was never a training target
(HANDOFF §7); the column exists only so the schema is drop-in. Do not compare
it. Out-of-taxonomy categories/modalities the model may emit are dropped from
`red_flags` and recorded in `schema_issues` (inventing a category to keep would
corrupt the downstream counts); parse failures keep the row with
`parse_ok=false` and null labels, never silently dropped.

### 1.8 Caveats that must travel into section 3 (also in the manifest)

1. **85.0% of these rows (5,736/6,746) are the student's own TRAINING rows.**
   Their teacher-agreement is inflated by memorization, so any retention ρ or
   IC-delta computed over the pooled corpus is **optimistic** — it is closer to
   an upper bound on retention than to an estimate of it. The `split` column
   exists precisely so the comparison is reported **pooled AND eval-only**
   (n=1,010, the only unbiased slice). Feature re-derivation needs all 6,746
   (a filing's features aggregate over every attributed chunk), so the honest
   framing is: pooled = the feature-level comparison with a named optimistic
   bias; eval-only = the unbiased chunk-level agreement that bounds it.
2. Every rate is **agreement with the teacher, not accuracy**. The teacher's own
   red_flags carry ~36.6% set-level error (sample-pooled) / ~25%
   base-rate-representative (Tier C) / 7.5% per-category.
3. `red_flags` must be reported on **both** bases (exact-set and per-category).
   The finalize step computes both, via `eval.score_red_flags` verbatim.
4. **8K_BODY (n=8, 2 tickers) and WITHDRAWN (n=1, in train) are not evaluable**
   and are excluded from the headline agreement tables, reported separately.
5. `guidance_direction` is stored **raw**; the missing→NONE post-rule is
   PROPOSED, NOT ADOPTED (gate G1). It is a no-op for the feature join —
   `features.py` maps both `"NONE"` and null to NaN — and both figures are
   reported in the manifest.
6. E1's `data/labels.parquet` is frozen and untouched; this artifact is a
   second labeler's output, never a replacement.

### 1.9 What was deliberately NOT done

- **The full 6,746-chunk campaign was not run here.** Long compute is a
  main-session auto-resume chain (HANDOFF §4); a subagent must never spawn it.
  Only the 14-row smoke was executed.
- No comparison, no feature re-derivation, no backtest, no retention ρ — that is
  quant-modeler's follow-up over the parquet. The manifest's
  `agreement_summary` is a sanity block, explicitly not the H3 result.
- `HARDENING_PROGRESS.md` was not edited.

---

## 2. The run — DONE 2026-08-25/26

**Every number in this section is read from
`/Users/vihanpatil/personal/projects/FinScreen/data/hardening/e1_relabel_manifest.json`
(sha256 `8fd1872daac9c7a2…`) and
`/Users/vihanpatil/personal/projects/FinScreen/data/hardening/e1_relabel.log`.
Nothing here is hand-carried from §1's projections.**

| item | manifest field | value |
|---|---|---|
| run id | `run_id` | `H3-e1-relabel-epoch2` |
| start / end | `segments[0].started_utc` / `.ended_utc` | 2026-08-25 20:14:45 UTC → 2026-08-26 00:53:00 UTC |
| segments / kills | `len(segments)` / `.torn_final_line_repaired_before_append` | **1 segment, 0 kills, 0 torn-line repairs** — the run completed in a single pass |
| exit codes | log tail | generation exited 0 (`GENERATION COMPLETE — 6746/6746 rows.`); `--finalize-only` then ran clean |
| journal rows | `journal.n_rows` / `.complete` | **6,746 / 6,746 (100.0%)**, `complete: true`, sha256 `fc5f06a95b8bc132…` |
| reproduction check | `reproduction_check` | **1,010 / 1,010 byte-identical** to `finetune/runs/2026-08-22-eval-epoch2/predictions.jsonl`, 0 differing |
| parse failures | `parquet.parse_failures` | **0** |
| schema violations | `parquet.schema_violations` | **0** |
| finish reasons | `totals.finish_reasons` | `{"stop": 6746}` — **zero `length` truncations** |
| wall clock | `segments[0].wall_seconds` | 16,694.8 s = **4.64 h** (model load 1.4 s) |
| throughput | `segments[0].chunks_per_hour` | **1,454.7 chunks/h** |
| tokens | `totals` | 6,636,538 prompt / 228,865 generated |
| parquet | `parquet.sha256` | **`5de9230bed706b92edb361bbd371c3538ccad85c5918b440924e4259f8a9adbd`**, 6,746 rows × 37 cols, train 5,736 / eval 1,010 |
| cost | `cost_usd` / `anthropic_api_calls` | **$0.00 / 0** |

**Versus the §1.4 projection.** Point estimate 4.76 h, band 4.6–5.6 h; measured
**4.64 h** — inside the band, at its optimistic edge. Throughput 1,454.7 vs the
1,337/h anchor (+8.8%). The §1.4 sensitivity worry (`finish=length` with
`gen_tok` near 520) never occurred: all 6,746 rows stopped naturally, mean
33.9 generated tokens/row vs the 36.3 modelled. Expected "roughly 5–6 segments"
— actual **1**, because the machine was never interrupted; the resume machinery
was therefore exercised only by the §1.5 resume smoke, not by this run.

**Provenance re-verified at run time** (`manifest.data`, `manifest.adapter`):
`mlx_data/{train,valid}.jsonl` shas match the epoch-2 training manifest
(`d4dc4ec8…`, `deb63b76…`, `sha_matches_train_manifest: true`); adapter
`9c08e3cb3f1f917c…`; base weights `86110f368236b53c…`; instruction
`ebc45a856bff58a5…` (`instruction_sha256_matches_epoch2_eval: true`); corpus
verification 6,695 identical / 51 head-truncated / **0 non-prefix**.
`data/labels.parquet` sha256 `c3531f03cda602bc…` — unchanged, opened read-only.

---

## 3. The comparison — DONE 2026-08-25, quant-modeler

**Gate G1 is the owner's ruling on this result.** §1.8's six caveats apply to
everything below and are re-attached inline where they bite.

### 3.0 How this was produced, and what was verified before anything was read

| # | Deliverable | Path |
|---|---|---|
| 1 | feature re-derivation + per-feature retention | `data/hardening/h3_features.py` → `data/hardening/h3_retention_2026-08-25.json` |
| 2 | thin-composition vs memorization decomposition | `data/hardening/h3_composition_control.py` → `data/hardening/h3_composition_control_2026-08-25.json` |
| 3 | filing-clustered bootstrap CIs on retention | `data/hardening/h3_retention_ci.py` → `data/hardening/h3_retention_ci_2026-08-25.json` |
| 4 | E1 backtest, teacher vs student, both specs | `data/hardening/h3_backtest.py` → `data/hardening/h3_backtest_2026-08-25.json` + `data/hardening/backtest_report_2026-08-25_H3_student.md` |
| 5 | harness seed-nuisance sweep | `data/hardening/h3_seed_sensitivity.py` → `data/hardening/h3_seed_sensitivity_2026-08-25.json` |

Derived feature tables (all new, all under `data/hardening/`):
`features_student_2026-08-25_H3.parquet` (`024ebe7262833dde…`),
`features_student_evalchunks_2026-08-25_H3.parquet` (`d08bc1498c465980…`),
`features_teacher_evalchunks_2026-08-25_H3.parquet` (`66af8542649df480…`).

**Machinery.** `features.build_feature_table()` is used verbatim — same
every-occurrence attribution, same backward-flow assertion, same three-group
NaN-vs-0 policy, same numeric/target joins. The **only** thing swapped is which
labels frame it consumes. `features.py`, `backtest.py`, `spec.py` and
`diagnose.py` were **not edited**. Zero network calls, all compute local.

**Four verifications passed before any comparison number was read:**

1. **Teacher re-derivation reproduces the frozen artifact exactly.** Re-running
   the pipeline on `data/labels.parquet` reproduces all 630 rows × (10 numeric +
   22 text + target) of `data/features.parquet`, same row order, `allclose(...,
   equal_nan=True)` → `True`. So every difference below is the labeler, not the
   harness.
2. **Wiring check.** The five label-independent composition features
   (`n_text_chunks_attributed`, four `share_chunks_*`) come back at retention
   **exactly 1.0000** in every slice — `section_type` is a corpus column, not a
   model output, so anything other than 1.0 would have meant a broken join.
3. **Numeric arm is bit-identical.** Per-fold numeric-only dedup ICs are
   identical to 6 dp between the teacher and student runs
   (`0.232919, 0.329190, 0.192105, −0.177335, −0.016931, 0.023281` under
   `raw_levels`). This is a **paired** comparison: only the text arm moves.
4. **Zero-information benchmarks are identical** across both runs
   (size-only rank dedup IC **0.2240**, ticker-training-mean **0.1868**), as
   they must be — they depend on the target and size only. They also still
   **beat every fitted model in this section**, teacher or student.
5. **Frozen artifacts unchanged**, re-hashed after every script:
   `data/features.parquet` `dbc1be09b560a144…`, `data/labels.parquet`
   `c3531f03cda602bc…`.

### 3.0a A real evaluation defect found and fixed mid-run — read this before the numbers

The first pass of the backtest showed the student **numeric-only** mean dedup IC
at 0.1448 against the teacher's 0.0972 — with the numeric columns bit-for-bit
identical. That is impossible on the merits, so it was chased before anything
else was reported (HANDOFF §7: *if a result looks too good, assume an
evaluation bug first*).

**Cause.** The first pass wrote the student feature table in a different
**on-disk row order**. `backtest.load_modeling_frame()` sorts by `filing_date`
alone using pandas' default **non-stable** quicksort, and the 630 rows carry
only **298 distinct filing_dates** (largest tie group 8), so tied rows permute.
XGBoost's `subsample=0.8` / `colsample_bytree=0.8` then draw different rows
under the same `random_state=42`.

**Measured size of the artifact:** numeric-only mean dedup IC 0.0972 → 0.1448,
and the primary-spec text delta **+0.0195 → +0.0694** — *with the features
unchanged*. The spurious +0.0694 would have been the largest text-vs-numeric
delta this project has ever produced, and it was pure row order.

**Fix:** preserve `features.py`'s build order in every derived table
(`h3_features.build_with_labels`, docstringed there). All §3 numbers below are
post-fix. **G3 item raised:** the pre-registration must pin a deterministic row
order (stable sort or an explicit tiebreak key) as a reproducibility
convention; §3.4 quantifies the residual.

### 3.1 Retention — predicted vs measured, pooled vs eval-only

Retention = correlation between the **student-derived** and **teacher-derived**
value of the same filing-level feature, over the 630-row E1 feature table.
Predictions are `data/reevaluation_2026-08-25/kill_case.md` C2/C3 (the confusion
matrix applied stochastically, errors assumed independent across chunks).

95% intervals are a **filing-clustered bootstrap**, 4,000 draws, `seed=0`,
resampling the feature table's rows (the unit the features live on). The
red-flag family figure is the mean of the 12 per-feature correlations recomputed
**within** each resample, so its interval carries the cross-feature correlation.

| feature family | predicted (C2/C3) | POOLED, n=630 rows / 6,746 chunks — **UPPER BOUND, 85.0% memorized** | EVAL-ONLY, n=630 rows / 1,010 chunks — **the only unbiased slice** |
|---|---|---|---|
| `sentiment_negative_share` | ρ 0.566 P / 0.642 S | **0.729** P [0.625, 0.822] · **0.766** S [0.716, 0.813] | **0.592** P [0.408, 0.759] · **0.606** S [0.491, 0.704] |
| `sentiment_mean_score` | ρ 0.874 P | **0.900** P [0.867, 0.928] · **0.879** S [0.850, 0.904] | **0.834** P [0.773, 0.886] · **0.796** S [0.721, 0.856] |
| 12 × `redflag_*_rate_*` (mean) | ρ 0.808 P / 0.858 S | **0.867** P [0.835, 0.902] · **0.890** S [0.866, 0.908] | **0.669** P [0.586, 0.742] · **0.655** S [0.560, 0.729] |
| `redflag_any_rate_press` | not simulated | 0.816 P [0.746, 0.877] · 0.808 S | 0.622 P [0.461, 0.767] · 0.628 S |
| `guidance_signed_mean` (n=55 / 11 defined rows) | not simulated | 0.888 P [0.779, 0.970] · 0.885 S | 0.920 P [0.685, 1.000] · 0.878 S — **n=11, not a measurement** |
| `guidance_any_present` | not simulated | 0.867 P [0.794, 0.929] · 0.867 S | 0.727 P [0.512, 0.887] · 0.727 S |
| 5 × composition features | n/a (label-independent) | **1.0000** (wiring check) | **1.0000** (wiring check) |

**Prediction vs measured, stated plainly:**

- `sentiment_negative_share` — **the simulation was right, and slightly
  pessimistic.** Predicted 0.566 P; measured **0.592** on the unbiased slice
  (CI [0.408, 0.759] contains 0.566). Spearman came in **below** prediction
  (0.606 vs 0.642). This is the feature the kill case singled out and it behaves
  as advertised: the student's NEGATIVE recall is 0.487 on held-out chunks
  (0.802 on memorized ones — manifest `agreement_summary`), i.e. it misses half
  of all negative-sentiment chunks it has not seen, and the feature keeps ~⅗ of
  its identity.
- `sentiment_mean_score` — **measured below prediction.** Predicted 0.874;
  measured **0.834** [0.773, 0.886] unbiased, 0.900 pooled. Aggregating over
  ±1/0 scores does absorb error, but not as much as independence implied.
- **The 12 red-flag rates are the finding that moves.** Predicted 0.808 P /
  0.858 S. Measured on the unbiased slice: **0.669 P [0.586, 0.742] / 0.655 S
  [0.560, 0.729]** — the 95% interval **excludes** the predicted 0.808. Pooled
  gives 0.867/0.890, i.e. *above* prediction. **The prediction sits outside the
  unbiased interval and inside the memorization-inflated one**, which is exactly
  the shape §1.8 caveat 1 said to expect. The kill case named the reason in
  advance: it treated student errors as independent across chunks, whereas real
  model errors are correlated ("same phrasing → same mistake") and do not
  average out.
- **Mechanism check, not a coincidence.** The two categories with the worst
  held-out recall — `DEMAND_WEAKNESS` 0.604 and `MARGIN_COST_PRESSURE` 0.669
  (manifest `eval_ONLY_UNBIASED_SLICE.red_flags.per_category`) — are precisely
  the four worst-retaining features: `redflag_MARGIN_COST_PRESSURE_rate_mda`
  **0.115** [−0.109, 0.386], `redflag_DEMAND_WEAKNESS_rate_mda` **0.215**
  [−0.075, 0.518], `redflag_DEMAND_WEAKNESS_rate_risk_factors` **0.433**
  [0.080, 0.691], `redflag_MARGIN_COST_PRESSURE_rate_risk_factors` **0.567**
  [0.335, 0.753]. **Two of the twelve red-flag features have unbiased-slice
  retention intervals that include zero.** At the other end,
  `IMPAIRMENT_WRITEDOWN`/`SUPPLY_INPUT_CONSTRAINT`/`TRADE_POLICY_EXPOSURE` in
  RISK_FACTORS all retain ≥0.969. The attenuation is **strongly
  feature-specific**, not a uniform haircut — a family mean hides it.

Full 22-feature tables (both slices, both correlation types, n-defined counts,
NaN-flip counts, means and mean-absolute-differences) are in
`data/hardening/h3_retention_2026-08-25.json`.

**NaN patterns barely move**: for every feature except `guidance_signed_mean`
the defined/undefined pattern is identical between teacher and student (the
switch is section composition, not the label). `guidance_signed_mean` flips on
7 rows teacher-only + 8 rows student-only out of 630, caused by the student
omitting the `guidance_direction` field on 320 chunks (`NONE→__MISSING_FIELD__`
in the manifest confusion). §1.8 caveat 5 holds: `features.py` maps `"NONE"` and
null identically to NaN, so the missing→NONE post-rule is a genuine no-op here.

### 3.2 Which slice should the owner believe? A measured decomposition

Pooled is optimistic (memorization). Eval-only could in principle be pessimistic
for a different reason: its 1,010 chunks spread thinly over 630 filings, so each
rate is a mean over fewer chunks and per-filing sampling noise inflates on
**both** sides, dragging the correlation down. **That objection was tested, not
assumed.**

Control: draw from the student's **train** chunks a sample matched to the eval
split's per-`section_type` counts (1,002 of 1,010 — all 8 `8K_BODY` chunks are
in eval, so none are available; `8K_BODY` is non-evaluable anyway, §1.8 caveat
4), 5 seeds. That sample is **thin like eval and memorized like the bulk of the
corpus**, so it isolates the thinness.

| feature | pooled (thick, 85% memorized) | matched-train (thin, memorized) | eval (thin, unmemorized) | attributable to thinness | attributable to non-memorization |
|---|---|---|---|---|---|
| 12 × `redflag_*` mean | 0.867 | **0.843** | 0.669 | **−0.024** | **−0.174** |
| `sentiment_negative_share` | 0.729 | **0.845** | 0.592 | **+0.116** | **−0.253** |
| `sentiment_mean_score` | 0.900 | **0.923** | 0.834 | +0.023 | −0.089 |
| `redflag_any_rate_press` | 0.816 | **0.900** | 0.622 | +0.084 | −0.278 |
| `guidance_any_present` | 0.867 | **0.917** | 0.727 | +0.050 | −0.190 |

**Thin composition does not explain the eval-only drop.** For four of the five
families it works in the *opposite* direction, and for the red-flag family it
accounts for 0.024 of a 0.198 gap (12%). The eval slice also has *thicker*
per-filing support than the control where it matters (its 135 RISK_FACTORS
chunks sit in 29 filings = 4.7/filing; the control's sit in 86 = 1.6/filing), so
if anything the control understates eval's advantage on that axis. **The gap is
memorization, and the eval-only column is the honest estimate.**

The price of the unbiased slice is width: 29 filings carry a RISK_FACTORS rate
and 50 carry an MDA rate, which is why every eval-only number above ships with
its interval and why the two per-category zeros are reported as
interval-includes-zero rather than as point claims.

**Indicative bridge, explicitly not a measurement.** Composing the two effects
in Fisher-z (eval-only, adjusted by pooled−matched) estimates what
*full-composition, unmemorized* retention would be: red-flag family **≈0.72**,
`sentiment_mean_score` **≈0.79**, `sentiment_negative_share` **≈0.35**,
`redflag_any_rate_press` **≈0.38**. This assumes composition and memorization do
not interact, which is **false in a known direction**: press-release chunks are
48.7% eval / 51.3% train, so the "memorized" control over-states memorization
for the press-heavy mix and the two press-driven bridges (negative-share,
press-rate) are the least trustworthy of the five. Treat the bridge as a
direction-of-travel check on the two measured columns, never as a headline. The
measured bracket **[eval-only, pooled]** is the reportable object.

### 3.3 IC-delta correspondence: E1 backtest on student labels, both specs

**Validation, stated next to the numbers, every time:** walk-forward
expanding-window, time-ordered by public `filing_date`, 6 quarterly test folds
(2025Q1–2026Q2) after a 2023Q3–2024Q4 burn-in; **never a shuffle**;
`assert_no_fold_leakage()` passes on every run; company-quarter dedup mask
computed once and shared (454 kept rows of 581; per-fold dedup n = 44/40/39/37/
45/32); XGBoost `random_state=42, n_jobs=1` (deterministic given row order —
see §3.0a); primary metric = **cross-fold mean dedup Spearman IC delta**
(text+numeric minus numeric-only), `std` is `ddof=1`. Folds and metric were
fixed by H2 **before** these labels existed.

**E1 benchmark, as shipped. E2 will use a different benchmark (equal-weighted
excl-self, membership-dated), so E1 and E2 backtest numbers are NUMERICALLY
INCOMPARABLE. Everything in this section is E1-on-E1.**

#### PRIMARY specification — `pit_trailing_rank` (H2 pre-registered)

| | 2025Q1 | 2025Q2 | 2025Q3 | 2025Q4 | 2026Q1 | 2026Q2 | mean | std (ddof=1) | pos folds |
|---|---|---|---|---|---|---|---|---|---|
| **teacher** dedup delta | −0.1167 | −0.2126 | −0.0057 | −0.0140 | +0.2428 | +0.0506 | **−0.0093** | 0.1549 | 2/6 |
| **student** dedup delta | −0.0643 | −0.2458 | +0.1065 | +0.0408 | +0.1497 | +0.1301 | **+0.0195** | 0.1514 | 4/6 |
| student − teacher | +0.0524 | −0.0332 | +0.1121 | +0.0548 | −0.0930 | +0.0795 | **+0.0288** | — | 4/6 same sign |
| **teacher** raw (non-dedup) delta | −0.0597 | −0.1270 | −0.0413 | −0.0083 | +0.1954 | +0.0857 | **+0.0075** | 0.1155 | 2/6 |
| **student** raw (non-dedup) delta | −0.0356 | −0.2248 | +0.0174 | +0.0698 | +0.1678 | +0.1492 | **+0.0240** | 0.1442 | 4/6 |

Levels: mean dedup IC numeric-only **+0.1148** (identical both runs, by
construction); text+numeric **+0.1056** teacher vs **+0.1343** student.
Per-fold across-fold correlation of the two labelers' delta series: **r = 0.875**.
Naive t on the student's mean (0.0195 / (0.1514/√6)) = **+0.32**.
Form-controlled (10-Q/10-K only, n=275, honest secondary): teacher **−0.0894**
(2/6 positive), student **−0.0484** (2/6).

#### SECONDARY specification — `raw_levels` (mandatory paired report)

| | 2025Q1 | 2025Q2 | 2025Q3 | 2025Q4 | 2026Q1 | 2026Q2 | mean | std (ddof=1) | pos folds |
|---|---|---|---|---|---|---|---|---|---|
| **teacher** dedup delta | −0.1275 | −0.0078 | −0.0399 | +0.0183 | −0.0004 | +0.0992 | **−0.0097** | 0.0742 | 2/6 |
| **student** dedup delta | −0.0312 | −0.0050 | +0.0142 | −0.1228 | −0.0065 | +0.2033 | **+0.0087** | 0.1069 | 2/6 |
| student − teacher | +0.0963 | +0.0028 | +0.0540 | −0.1411 | −0.0061 | +0.1041 | **+0.0184** | — | 4/6 same sign |
| **teacher** raw (non-dedup) delta | −0.0661 | −0.0157 | −0.0260 | +0.0519 | +0.0330 | +0.1289 | **+0.0177** | 0.0690 | 3/6 |
| **student** raw (non-dedup) delta | −0.0266 | −0.0128 | +0.0147 | −0.0463 | +0.0331 | +0.1474 | **+0.0182** | 0.0694 | 3/6 |

Levels: numeric-only **+0.0972** (identical both runs); text+numeric **+0.0875**
teacher vs **+0.1059** student. Across-fold r = 0.551. Form-controlled: teacher
**+0.0190** (4/6), student **+0.0720** (5/6).

**The teacher arm reproduces H2 exactly** — `raw_levels` per-fold
−0.1275/−0.0078/−0.0399/+0.0183/−0.0004/+0.0992, mean −0.0097, std 0.0742,
implied floor 0.0000; `pit_trailing_rank` mean −0.0093, std 0.1549, floor
0.0992 (H2 §3.4 variant A). Same harness, so every difference is the labeler.

#### Standing zero-information benchmark rows (H2, mandatory, both runs)

| benchmark | cross-fold mean dedup IC | sample std (ddof=1) | positive folds |
|---|---|---|---|
| `size_only_rank` | **0.2240** | 0.2871 | 5/6 |
| `ticker_training_mean_rank` | **0.1868** | 0.3111 | 4/6 |
| teacher text+numeric (primary spec) | 0.1056 | — | — |
| student text+numeric (primary spec) | 0.1343 | — | — |
| teacher / student numeric-only (primary spec) | 0.1148 | — | — |

Identical in both runs (they are properties of the folds and the target).
**Both zero-information predictors still beat every fitted model on both sides
of this comparison.** Neither benchmark is distinguishable from zero at 6 folds
either — they are a scale for reading ICs, not a claim that size predicts
returns.

Within-fold bootstrap noise anchor (4,000 resamples/fold): mean within-fold SD
0.1149 teacher / 0.1100 student under the primary spec, 0.1046 / 0.0887 under
raw levels. Implied regime floor 0.0992 teacher / 0.0281 student (primary),
0.0000 / 0.0532 (raw) — still unresolved at 6 folds in both directions, exactly
as H2 found; the floor moving this much between two labelings of the same
corpus is further evidence it is not identified at k=6.

### 3.4 The harness's own nuisance spread — why §3.3 does not say "the student is better"

`+0.0288` (primary) and `+0.0184` (secondary) look like the student beating the
teacher. They are not distinguishable from the harness's own noise. Sweeping
XGBoost's `random_state` over **100 values** on the identical frames, folds and
dedup mask (`h3_seed_sensitivity.py`):

| specification | arm | shipped seed 42 | mean over 100 seeds | SD across seeds | 95% range | fraction > 0 |
|---|---|---|---|---|---|---|
| `pit_trailing_rank` | teacher | −0.0093 | +0.0211 | 0.0283 | [−0.025, +0.074] | 0.71 |
| `pit_trailing_rank` | student | +0.0195 | +0.0167 | 0.0289 | [−0.037, +0.074] | 0.72 |
| `pit_trailing_rank` | **student − teacher** | **+0.0288** | **−0.0044** | **0.0275** | **[−0.054, +0.046]** | **0.44** |
| `raw_levels` | teacher | −0.0097 | −0.0026 | 0.0287 | [−0.056, +0.050] | 0.43 |
| `raw_levels` | student | +0.0087 | +0.0110 | 0.0263 | [−0.046, +0.062] | 0.71 |
| `raw_levels` | **student − teacher** | **+0.0184** | **+0.0136** | **0.0274** | **[−0.043, +0.061]** | **0.75** |

**Read this row by row.** The paired student-minus-teacher difference is
centred at **−0.004** (primary) and **+0.014** (secondary) with an SD of ~0.028,
and it changes sign on 44%/25% of seeds. The shipped-seed values (+0.029 /
+0.018) are ordinary draws from that distribution. Both are also below H2's
honest MDE for this design (0.032 floor-free ρ_f=0 → 0.085 floor branch,
primary spec) and inside H2's measured implementation-sensitivity span (0.059).

**The correct statement is therefore: the student-labeled and teacher-labeled E1
backtests produce text-vs-numeric IC deltas that are statistically
indistinguishable from each other and, individually, indistinguishable from
zero.** Reporting "+0.0288, the student adds signal" would have been the same
class of error as §3.0a's row-order artifact — a seed-level fact dressed as a
labeler-level one.

**This is not evidence that attenuation is harmless.** It is evidence that
**E1's backtest cannot see attenuation at all**: the quantity being compared has
a nuisance SD (0.028) and a between-labeler difference (≤0.029) of the same
order, at 6 folds, where H2 already showed the MDE exceeds every effect this
data has ever produced. **The IC-delta correspondence is uninformative for G1 in
both directions.** The retention measurements in §3.1–3.2 are the informative
part, and they are measured directly rather than inferred through a 6-fold
backtest.

Also note that a *lower*-retention feature block is not monotonically worse for
a delta: noisier text makes the full model resemble the numeric-only model,
which raises model-model correlation and shrinks the delta's sampling noise.
The kill case flagged this ("pessimistic in one way"); it is one more reason the
IC delta is the wrong instrument for reading attenuation.

### 3.5 Bottom line for gate G1

**How much of the text-feature signal survives the student, on the only
unbiased slice (n=1,010 held-out chunks, 630 filings, 95% filing-clustered
bootstrap CIs):**

| block | eval-only retention (Pearson) | pooled upper bound | verdict vs the C2/C3 prediction |
|---|---|---|---|
| section composition (5 features) | **1.000** | 1.000 | label-independent — survives fully |
| `sentiment_mean_score` | **0.834** [0.773, 0.886] | 0.900 | below the 0.874 prediction |
| `sentiment_negative_share` | **0.592** [0.408, 0.759] | 0.729 | **matches** the 0.566 prediction |
| 12 × `redflag_*_rate_*` (mean) | **0.669** [0.586, 0.742] | 0.867 | **below** the 0.808 prediction; CI excludes it |
| worst 2 red-flag features (`MARGIN_COST_PRESSURE`/`DEMAND_WEAKNESS` in MDA) | **0.115 / 0.215** — CIs include 0 | 0.610 / 0.821 | **not simulated; effectively destroyed** |
| `redflag_any_rate_press` | **0.622** [0.461, 0.767] | 0.816 | not simulated |

**Is kill-criterion 2's band (materially below ρ≈0.57/0.81) breached?**
H5 leaves the numeric threshold to the G1 ruling; measured against the band as
written, the honest answer is **split, and it splits along the axis §1.8
predicted**:

- **ρ≈0.57 (sentiment) — NOT breached.** Eval-only 0.592, CI [0.408, 0.759]
  straddles 0.57; pooled 0.729. The negative-sentiment share is as attenuated as
  the simulation said, no worse. It was already the weakest feature in the set.
- **ρ≈0.81 (red flags) — BREACHED on the unbiased slice.** Eval-only 0.669 with
  a 95% CI of [0.586, 0.742] that **excludes 0.81**; the composition control
  shows only 0.024 of the 0.198 gap is thin-sample artifact. It is **not**
  breached on the pooled slice (0.867), which is the memorization-inflated upper
  bound and should not be used to clear a gate. The sub-family detail is worse
  than the mean: 2 of 12 red-flag features retain nothing distinguishable from
  zero.
- **IC-delta correspondence — cannot adjudicate the criterion either way.**
  §3.4: the between-labeler difference (+0.029 primary / +0.018 secondary) is
  smaller than the harness's own 100-seed nuisance SD (0.028) and far below
  H2's honest MDE (0.032–0.085). E1's 6-fold design has no power to detect
  attenuation of any plausible size, so an *absence* of IC-delta degradation is
  **not** evidence that the labeler is fit for purpose.

**One-paragraph summary for the owner.** The student reproduces the teacher's
filing-level text features well where the label is easy and structural, and
poorly where the label carries the discriminating information: composition
features survive exactly (1.000, by construction), `sentiment_mean_score`
retains 0.834 [0.773, 0.886], `sentiment_negative_share` retains 0.592
[0.408, 0.759] — matching the simulation's 0.566 — and the 12 red-flag rates
retain only **0.669 [0.586, 0.742]** against a predicted 0.808, with the
prediction outside the interval and two of the twelve features (MDA
`MARGIN_COST_PRESSURE` 0.115 and `DEMAND_WEAKNESS` 0.215) retaining nothing
distinguishable from zero; the pooled figures (0.900 / 0.729 / 0.867) are 85%
memorized and are an upper bound, and a matched-composition control shows the
gap between the two slices is memorization, not thin sampling (0.024 of 0.198).
The re-run E1 backtest cannot adjudicate this: under both pre-registered specs
the student's text-vs-numeric dedup IC delta (+0.0195 primary / +0.0087
secondary) differs from the teacher's (−0.0093 / −0.0097) by less than the
harness's own 100-seed nuisance SD of 0.028 — and a row-order defect found and
fixed during this run was worth +0.050 on the same metric, larger than the
entire between-labeler difference — while both zero-information benchmarks
(0.2240 / 0.1868) still beat every fitted model on both sides. So kill-criterion
2 is **breached for the red-flag block on the only unbiased evidence and not
breached for sentiment**, the IC-delta arm is uninformative rather than
reassuring, and the G1 decision reduces to a judgement the owner alone can make:
whether an E2 text block whose largest feature family retains ~⅔ of its identity
(and whose two weakest members retain none) is an instrument worth spending
F3–F6 on, given that the red-flag labels being attenuated are themselves the
ones already carrying ~25–36.6% teacher error (§1.8 caveat 2) — i.e. this is
attenuation of an already-noisy target, and the two errors compound rather than
cancel.

**Three items this section hands to G3 (not decided here):**
1. Pin a deterministic row order / stable sort in the modeling frame — §3.0a,
   worth 0.050 in the headline estimand.
2. Report the primary metric with a **seed-nuisance band**, measured, beside
   every point estimate — §3.4, measured SD 0.028 at 6 folds.
3. If the student is accepted, E2's report must carry per-feature retention, not
   a family mean — §3.1 shows the family mean hides two destroyed features.

**Not done here, deliberately:** `HARDENING_PROGRESS.md` was not edited; no
E2-labeler decision was made (that is G1, the owner's); no third-epoch or
re-label recommendation is made (H5 kill-criterion 2 routes that to the owner);
`data/features.parquet`, `data/labels.parquet` and every other frozen artifact
are untouched and re-verified by sha256.
