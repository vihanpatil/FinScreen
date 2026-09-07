# F4 — the E2 labeling campaign: the exact MAIN-SESSION commands

**Prepared 2026-08-28 by the finetune-engineer. Nothing on a GPU was executed.**
The chunk table IS built and verified; the runner, its plan and its tests are
done. Only the GPU work is left, and per `HANDOFF.md` §4/§7 the main session
runs it, never an agent.

**Cost: $0. Zero Anthropic API calls. Zero network.** Local MLX only.

```bash
FS=/Users/vihanpatil/personal/projects/FinScreen
F4=$FS/data/f4
VP=$FS/finetune/.mlx_venv/bin/python
```

---

## 0. What is pinned, and what happens if it moved

Every one of these is checked in code and is a **hard stop**, not a warning.

| artifact | sha256 | checked by |
|---|---|---|
| `data/filings_e2_v2.parquet` (P5's corpus, 29,097 sections) | `15853e9f54902a933f0372869209a353ab3f052cb5c7dc1f897297f75b53f417` | `build_f4_chunks.assert_sha`, then `label_e2.build_plan` via the chunk manifest |
| `data/f3/v2/extraction_audit.parquet` | `207f392aa54c5151015093ecb34e5c57319f17e1ce22a3375ec1ac7f18e81eef` | `build_f4_chunks.main` |
| **`data/f4/chunks_v1.parquet`** (317,081 chunks, 400,928,730 B) | `d67395ece6126045e851e05f4b8fe5c8c49bd69069c44a08b9ee8f9d67bf0857` | `label_e2.build_plan`, every night |
| adapter `checkpoints/…-lora-mlx-v12-epoch2/adapters.safetensors` | `cadca8499b66b2e7d60a161f2021a5c5dac51ddd3a0bccea52d055cefb159de3` | `label_e2.preflight`, **twice**: against the reference eval's manifest AND against the pinned G1 adapter |
| training instruction (the system turn) | `ebc45a856bff58a562535867e5a1f4173519fe77c58a47b16bfa28e6eea8efe2` | `label_e2.preflight`, against the plan and the reference eval |
| base weights | `86110f368236b53cf4c2336f991a85703b17bcc60bb75f292b4002ec0219f071` | training manifest, recorded per segment |
| `finetune/mlx_data_v12/{train,valid}.jsonl` | `396aef131bec0e5c…` / `b74efdb326e9b862…` | `label_e2.preflight`, against `runs/2026-08-27-v12-epoch2/manifest.json` |

If any of them mismatches, the run refuses to start and names both hashes. A
legitimately moved artifact is a new owner decision, not a constant to edit.

**Reference eval** = `finetune/runs/2026-08-28-v12-eval-epoch2/` (the epoch-2
v1.2 eval gate G1 was ruled on). Its `manifest.json` supplies the adapter and
instruction cross-checks; its `predictions.jsonl` is what the repro canary
reproduces.

---

## 1. The configuration, and where it came from

| knob | value | why |
|---|---|---|
| window rule | **W1 core** (`stratum == "core"`, full 2015-07 → 2026-08 window) | owner, HANDOFF §3 2026-08-27, re-confirmed post-demotion |
| line rule | **full `reflow_v1`** | same ruling; P3's exact implementation, productionised and pinned against it by test |
| guidance `missing → NONE` | **applied at the writer**, scoped to guidance-applicable section types, every imputed row flagged `guidance_imputed_none = true` | same ruling + eval report `2026-08-22-eval-epoch2` A.7 |
| `red_flags` | produced under **EXPLORATORY / DISCLOSURE-ONLY** status | the ratified DEMOTE pre-commitment fired 2026-08-27 (teacher exact-set error 42.00% [35.37, 48.93]) |
| decoding | greedy, `temp 0.0` → argmax; `max_tokens 520` | identical to the epoch-2 eval and to H3/H3v2 |
| **answer token reserve** | **256** → prompt budget **1,792** of 2,048 | see §2 |
| segment size | 24 segments of 12,492–13,349 rows, cut on filing boundaries | ~9.4 h of labeling per night at the projected rate |

---

## 2. The answer-token reserve, and why 256

At training time `convert_to_mlx.fit_passage` head-truncated the passage so
that instruction + passage + **the real answer** fit `max_seq_length 2048`. At
labeling time there is no answer, so a fixed reserve replaces it (the extension
point `H3_attenuation.md` §1.6 deliberately did not build).

Measured, on this machine, with this adapter:

| source | n | mean gen tokens | p99.9 | max |
|---|---|---|---|---|
| H3v2 relabel journal (v1.2 student, all of E1) | 6,746 | 34.83 | 130 | **151** |
| v1.2 epoch-2 eval (`manifest.json` → throughput) | 1,010 | 36.7 | ~121 (p99) | **151** |
| v1.2 training targets' own loss-bearing region | 6,746 | 37.4 (train) | — | **152** |

**256 is 1.68× the largest answer ever generated or trained on.** Its cost,
measured over a seeded 5,000-chunk sample of the real F4 chunk table
(`--limit 5000`, seed 20260828, tokenized with the real tokenizer, no GPU):

| reserve | prompt budget | rows head-truncated |
|---|---|---|
| 0 | 2,048 | 0.220% |
| 160 | 1,888 | 0.360% |
| 192 | 1,856 | 0.420% |
| **256** | **1,792** | **0.700%** (≈ 2,220 of 317,081) |
| 384 | 1,664 | 1.360% |
| 520 (= `max_tokens`) | 1,528 | 3.020% |

So 256 costs ~890 extra truncated rows versus 192 and buys 1.7× headroom;
520 would quadruple truncation to guard a case that has never occurred in
7,756 measured generations and cannot occur under the training distribution.

**The reserve is a length-REGIME guarantee, not a cap.** Generation still runs
to `max_tokens 520`; an answer longer than 256 tokens is produced in full, it
just extends past position 2,048. That is exactly why the reserve is set well
clear of the observed maximum rather than at it.

Truncation drops **only the passage tail** (binary search on the passage's own
token prefix — `convert_to_mlx.fit_passage`'s method), the instruction is never
touched, and every truncated row carries `passage_was_head_truncated = true`
plus `passage_chars_kept`.

---

## 3. Pre-flight (free, ~3 minutes, run all of it)

```bash
# a. the chunk table is reproducible and is the pinned artifact
shasum -a 256 $F4/chunks_v1.parquet
#   expect d67395ece6126045e851e05f4b8fe5c8c49bd69069c44a08b9ee8f9d67bf0857
python3 $FS/finetune/build_f4_chunks.py --verify-only | head -20
#   expect n_chunks 317081 · chunk_ids_unique true · n_colliding_with_E1… 0

# b. offline test suites
python3 -m pytest $FS/finetune/test_build_f4_chunks.py \
                  $FS/finetune/test_label_e2.py \
                  $FS/finetune/test_relabel_e1.py -q
#   expect 98 passed (22 + 40 + 36) — relabel_e1's 36 MUST still be green

# c. the tokenizer-dependent half, in the MLX venv (no GPU, no model weights)
$VP $FS/finetune/test_label_e2_prompt.py
#   expect 7 passed, 0 failed, 0 skipped

# d. the campaign plan (idempotent; re-verifies every sha above)
python3 $FS/finetune/label_e2.py --plan
#   expect: chunks 317081 rows · segments 24 · adapter cadca849… · instruction ebc45a85…

# e. nothing else is on the GPU
ps aux | grep -E 'mlx_lm|eval\.py|train_qlora|relabel_e1|label_e2' | grep -v grep
#   expect no output
```

`build_f4_chunks.py` only needs re-running if the chunk table is missing; it
takes 55 s and is byte-deterministic (proved by two full builds).

---

## 4. The 10-row SMOKE (GPU slot; ~3 min; run this BEFORE the first night)

Two parts. **Both must pass before any night launches.**

### 4a. The repro canary — F4's verify-artifact check

```bash
$VP $FS/finetune/label_e2.py --repro-canary 10
```

Re-generates 10 rows of the frozen v1.2 **eval** split through the F4 code path
(F4's own no-answer prompt renderer, F4's decoding) and compares them, byte for
byte, to `runs/2026-08-28-v12-eval-epoch2/predictions.jsonl`.

| check | required |
|---|---|
| `n_identical / n_compared` | **10 / 10** |
| `verified` | **true** |
| `prompt_renderer_matches_eval_path` | **true** (asserted per row; a mismatch is a `SystemExit`) |

Output: `data/f4/repro_canary.json`. **If this is not 10/10, STOP.** It means
the prompt, the adapter or the decoding moved, and 317,081 chunks would be
labeled by something other than the artifact gate G1 was ruled on
(`HANDOFF.md` §7). `n_eval_rows_skipped_as_too_long_for_the_F4_budget` is
expected to be small and non-zero — those rows are ones where F4's fixed
reserve legitimately truncates and the eval's answer-fitted truncation did not,
so they are excluded rather than counted as mismatches.

### 4b. Ten real F4 rows

```bash
SMOKE=$F4/smoke
mkdir -p $SMOKE
python3 $FS/finetune/label_e2.py --prepare-segment 1 --out-dir $SMOKE

caffeinate -dims $VP $FS/finetune/label_e2.py \
  --segment 1 --limit 10 --out-dir $SMOKE >> $SMOKE/smoke.log 2>&1

python3 $FS/finetune/label_e2.py --finalize-segment 1 --limit 10 \
  --out-dir $SMOKE --allow-partial
```

Pass checklist (printed by the finalize step and written to
`$SMOKE/manifest.json`):

| check | required value | where |
|---|---|---|
| rows generated | **10/10**, exit 0 | `smoke.log` tail |
| finish reasons | `{"stop": 10}` — **zero `length`** | `segments[0].finish_reasons` |
| parse failures / schema violations | **0 / 0** | `parquet.*` |
| adapter cross-check | `adapter_sha256_matches_reference_eval: true` **and** `adapter_sha256_matches_pinned_G1_adapter: true` | `data.*` |
| instruction | `ebc45a85…`, `..._matches_reference_eval: true` | `data.*` |
| chunk table | `chunks_parquet.sha256 == d67395ec…` | `data.*` |
| parquet shape | **10 rows × 43 cols** | `parquet.n_columns` |
| guidance audit | `guidance.n_imputed_none` ≤ `guidance.n_applicable`, and every imputed row has `guidance_direction == "NONE"` | `parquet.guidance` |
| truncation | `head_truncation.answer_token_reserve == 256`, `prompt_token_budget == 1792` | `parquet.head_truncation` |
| throughput | ~**1,300–1,500 chunks/h** | `segments[0].chunks_per_hour` |
| sanity, by eye | the labels are not all identical; sentiment varies; `distress_tier` is empty everywhere | open the parquet |

n=10 label rates are **not** a result. The smoke measures mechanics only.

Delete `$F4/smoke` afterwards, or leave it — it is outside the campaign
directories and is never read by the campaign.

---

## 5. A labeling night

**One segment = one night = one run directory.** 24 of them, `seg-001` …
`seg-024`, in chronological order (`seg-001` is 2015-07 onward). Each is
accession-aligned, so a completed segment always contains **whole filings**,
and each carries a full section-type mix — a campaign stopped early is a
usable time prefix, not "every MD&A and no press release".

```bash
SEG=seg-007                      # <- the night's segment

# step 1 — materialise its rows (SYSTEM python3, ~20 s, no GPU, safe any time)
python3 $FS/finetune/label_e2.py --prepare-segment $SEG

# step 2 — GENERATE (main-session BACKGROUND task; ~9.4 h)
ps aux | grep -E 'mlx_lm|eval\.py|train_qlora|relabel_e1' | grep -v grep   # MUST be empty

caffeinate -dims $VP $FS/finetune/label_e2.py --segment $SEG \
  >> $F4/segments/$SEG/seg.log 2>&1

# step 3 — finalize (SYSTEM python3, ~30 s, loads no model)
python3 $FS/finetune/label_e2.py --finalize-segment $SEG
```

Use `>> … 2>&1`, **never `| tee`** — a pipe hands back tee's exit status and
the resume chain could not tell "done" (0) from "resume me" (2).
Live progress: `tail -f $F4/segments/$SEG/seg.log`.

**Never launch step 2 from a subagent shell** (HANDOFF §4). It is a
main-session background task and every kill notification is a resume trigger.

### Resume recipe

- **Exit 0** = every row of the segment is in the journal → go to step 3.
  **Exit 2** = partial → **re-run the identical step-2 command**. Finished rows
  are skipped; nothing is regenerated.
- Every row is `write` + `flush` + `fsync` to
  `$F4/segments/$SEG/labels.jsonl` before the next row starts. A SIGTERM or
  `kill -9` at any instant loses **at most the in-flight row** (~2.5 s).
- A torn final line is ignored on read **and terminated with a newline before
  the next append** — without that repair a resume silently loses one good row
  per kill (the bug H3's resume smoke caught). Same function, imported.
- Every journal row stores a hash of its prompt INPUTS (instruction sha +
  passage bytes) and of the rendered token sequence. If the chunk table or the
  instruction moved under a resume, the run **stops hard** rather than mixing
  two prompt versions into one artifact. The segment's `rows.jsonl` sha is
  compared against the one the segment's first process recorded, for the same
  reason.
- Re-running a finished segment is a no-op: it never loads the model.
- `--max-rows-per-segment N` exists if voluntary exits are preferred; default
  0 = run until done or killed. Cost per extra process: one model load (~1.5 s
  warm). There is **no** prompt re-render pre-pass, unlike `relabel_e1.py`, so
  a resume costs essentially nothing.

### If a night is short

Nothing special. Kill it, and re-run the identical command the next night; it
picks up where it stopped. A segment does not have to fit in one slot.

---

## 6. Projected wall clock — banded honestly

The corpus is **317,081 chunks** (recomputed; P3 §8's 314,211 predates P5's
+197 sections and is stale by +0.91%).

The rate is **not** simply H3v2's measured 1,477.7 chunks/h, because F4's
prompts are longer than E1's: mean **1,069.4** prompt tokens (seeded 5,000-row
sample of the real chunk table) against E1's 983.7. Calibrating H3v2's own
measurement — prefill 879.1 tok/s, decode 30.2 tok/s, and a measured 0.164 s/row
of residual overhead that reproduces its 2.436 s/row exactly — and using the
F4 section-type mix's expected answer length (35.33 tokens, from the per-section
H3v2 means weighted by F4's mix):

    1069.4/879.1 + 35.33/30.2 + 0.164 = 2.550 s/row  ->  1,412 chunks/h

| scenario | chunks/h | total hours | nights @ 10 h |
|---|---|---|---|
| optimistic (H3v2's measured E1 rate, shorter prompts) | 1,477.7 | **214.6** | 21.5 |
| **projected (F4's own prompt length + answer mix)** | **1,412** | **224.6** | **22.5** |
| conservative (P3's quoted epoch-1 rate) | 1,068 | **296.9** | 29.7 |

**Plan on 24 nights** (the plan's 24 segments, ~9.4 h each at the projected
rate, 8.9 h at the optimistic one, 12.4 h at the conservative one — the last
case simply needs one resume per night). That sits inside the 21–29 overnights
the owner was quoted at ratification.

Per-night expectations, from the plan:

| | value |
|---|---|
| segments | 24 (`seg-001` … `seg-024`) |
| rows per segment | 12,492 – 13,349 |
| filings per segment | ~500 – 800 |
| section mix per segment | every segment carries MDA / RISK_FACTORS / EX99_PRESS_RELEASE, press releases 15–35% |
| disk per segment | ~33 MB `rows.jsonl` + ~9 MB journal + ~17 MB parquet |
| disk, whole campaign | ~1.5 GB on top of the 0.4 GB chunk table |

**Stop the run and report it as the finding** if progress lines start showing
`finish=length` with `gen_tok` near 520 — that is a non-terminating model, not
a slow one, and it would be a real difference from every measurement above.

---

## 7. Closing the campaign

```bash
python3 $FS/finetune/label_e2.py --finalize-campaign
```

Concatenates every finalized segment into `data/f4/labels_e2_v1.parquet` and
writes `data/f4/campaign_manifest.json` with per-night provenance (journal sha,
parquet sha, process count, wall seconds, chunks/h) and the accumulated totals.

It is safe to run **at any time**: with segments outstanding it writes a
`COMPLETE: false` manifest that names every missing segment and the row
shortfall, rather than a partial parquet that looks complete. Exit 0 only when
all 24 are in.

---

## 8. What the output looks like

`data/f4/labels_e2_v1.parquet` — 317,081 rows × **43 columns**, chunk_id-keyed.

- **Columns 1–34 are `data/labels_v12.parquet`'s own arrow schema**, copied
  from the file rather than re-declared, so the downstream `features.py` join
  is a path swap. `data/labels_v12.parquet` is a **schema template only** — it
  is not a teacher for these rows and was opened read-only.
  - `parse_error` is widened `null` → `string` (the teacher had no failures;
    the student's must be storable).
  - `home_ticker` is null and `source_tickers` is empty: E2 filings are
    CIK-keyed, and inventing a ticker would be false provenance. `home_cik` and
    `source_accession_numbers` carry the real identity.
- **9 F4 columns appended**: `segment_id`, `passage_was_head_truncated`,
  `passage_chars_kept`, `prompt_tokens`, `prompt_sha256`, `latency_s`,
  `schema_issues`, `guidance_applicable`, **`guidance_imputed_none`**.
- Parquet **schema metadata** carries `f4_red_flags_status` (the demotion, with
  its number), `f4_labeler` (the adapter sha), `f4_guidance_rule` and
  `f4_teacher` ("NONE — these are STUDENT labels").
- `distress_tier` is uniformly empty by construction (HANDOFF §7).
- Parse failures keep their row with `parse_ok = false` and null labels — never
  dropped. Out-of-taxonomy red-flag categories/modalities are dropped from
  `red_flags` and recorded in `schema_issues`.

The companion `data/f4/chunks_v1.parquet` holds the fuller corpus provenance
per chunk (sector, stratum, extraction status/confidence/method, flags,
`in_member_spell` / `in_member_spell_plus12m`, `window_rule`, `line_rule`),
joinable on `chunk_id`.

---

## 9. Traps

1. **`--prepare-segment` before `--segment`.** The GPU interpreter has no
   pandas/pyarrow, so it cannot read the chunk parquet. If `rows.jsonl` is
   missing the run exits with the exact command to fix it.
2. **Two interpreters.** `--plan` / `--prepare-segment` / `--finalize-*` are
   SYSTEM `python3`; `--segment` / `--repro-canary` are `.mlx_venv/bin/python`.
   Getting it backwards fails loudly and immediately.
3. **The plan must be regenerated if `--segment-rows` changes**, and the
   segment ids shift with it. Do not mix a plan written at one segment size
   with run directories created under another — the `chunk_id_list_sha256`
   check catches it, but it is easier not to.
4. **`>> log 2>&1`, never `| tee`** — a pipe destroys the exit code the resume
   chain reads.
5. **Nothing else on the GPU.** Check `ps aux` first, every night.
6. **`red_flags` is exploratory.** Every artifact says so; do not let a
   downstream summary quietly promote it. Sentiment and composition features
   are unaffected.
7. **8K_BODY is 790 chunks here and was 8 in E1.** The student has essentially
   no supervision for it. Do not report a per-class metric on it (HANDOFF §7).
8. **W1-core means the extension stratum is unlabeled.** A chunk's
   `source_*` back-references cover core-stratum sections only; labeling the
   extension later is a separate campaign with its own home selection, not an
   append to this one.
