# F4 — implementation prep: the E2 labeling campaign tooling

**Stage:** F4, authorised by HANDOFF §3 2026-08-27 (G1 accepted with B1
satisfied; F4 config ruled and re-confirmed post-demotion: **W1-core window
rule + full `reflow_v1` + guidance missing→NONE at the labeling writer with an
audit flag**). **Agent:** finetune-engineer (Opus). **Date:** 2026-08-28.
**Status: DONE — nothing launched.**

**Discipline.** **Zero GPU work**: no model was loaded, no MLX import executed,
not one token generated. **Zero network. Zero Anthropic API calls. $0.** The
only non-stdlib compute was pandas/pyarrow (offline) and one CPU-only tokenizer
load for the prompt-token census. Every frozen artifact — E1's set, the v1.2
dataset artifacts, H3/H3v2's outputs, `spotcheck_v12`, the P2–P5 audit record —
was opened READ-ONLY and re-hashed unchanged. **No ledger was edited.**

**Writes:** `finetune/build_f4_chunks.py`, `finetune/label_e2.py`,
`finetune/test_build_f4_chunks.py`, `finetune/test_label_e2.py`,
`finetune/test_label_e2_prompt.py`, `data/f4/**`, and this file.

---

## 0. Headline

| | |
|---|---|
| **recomputed scale** | **317,081 chunks** (W1-core × full reflow_v1). P3 §8's 314,211 is stale by **+2,870 (+0.91%)** — it predates P5's +197 sections. |
| chunk table | `data/f4/chunks_v1.parquet` — sha256 `d67395ece6126045e851e05f4b8fe5c8c49bd69069c44a08b9ee8f9d67bf0857` (400,928,730 B) |
| built from | `data/filings_e2_v2.parquet` `15853e9f…` + audit `207f392a…`, both sha-pinned and hard-failing |
| determinism | **two full builds, byte-identical sha.** 55 s per build |
| E1 collision | **0** of 317,081 chunk_ids collide with E1's frozen `labeling_corpus.parquet`; ids are unique |
| **answer-token reserve** | **256** (prompt budget 1,792 of 2,048) → **0.700%** of rows head-truncated, measured |
| runner | `finetune/label_e2.py` — a **sibling** importing `relabel_e1.py`, which is byte-unchanged (`383a0222…`) |
| segmentation | **24 nights**, 12,492–13,349 rows each, cut on filing boundaries, chronological |
| projected wall clock | **~225 labeling hours** (band 215–297) → **24 nights** at the plan's segment size |
| tests | **69 new** (22 + 40 pytest, 7 in the MLX venv). `relabel_e1`'s 36 still green → **98 pytest passed** |
| cost | **$0**, 0 API calls, 0 GPU seconds |

---

## 1. The chunk table — `finetune/build_f4_chunks.py`

### 1.1 What it implements

`reflow_v1` applied to P5's corpus → global exact-dedup → `chunk.py`'s window
packing → W1-core, written as a deterministic sha-pinned parquet.

- **W1 core** = `stratum == "core"` (20,982 of 29,097 sections), **full
  2015-07-02 → 2026-08-20 window, no date filter** — exactly `p3_scale.py`'s
  `W1_full_core` rule.
- **The window rule is applied BEFORE dedup**, because restricting the corpus
  changes which occurrence is "home". This is P3's method and it is why W1-core
  is a full rebuild rather than a filter on W1-full.
- **`reflow_v1` is productionised, not reinvented**: a test replays 200 random
  line-shape cases against P3's own `p3_qa/p3_scale.py::prose_lines_reflow` and
  requires line-for-line equality.
- `chunk.py`'s `MIN_PROSE_WORDS` / `TARGET_WINDOW_WORDS` / `MIN_FLUSH_WORDS` and
  `normalize_paragraph` are **imported**, never re-declared.
- Declared deviation, exactly the one P3 named: `ticker` is NULL at E2 scale, so
  the home tie-break uses `cik` zero-padded to 10 characters in the slot
  `chunk.py` gives `ticker`.

### 1.2 The proof that the packing is `chunk.py`'s

The corpus is 628 MB of text and 2.17M canonical paragraphs, so the packing is
re-expressed over numpy arrays rather than `chunk.CanonicalParagraph` objects.
That re-expression is not trusted on assertion:

1. **`test_streaming_packer_reproduces_chunk_pack_windows`** — a synthetic
   corpus with deliberate cross-section duplicates is packed both ways;
   chunk_ids, texts, word counts, paragraph_ids and source counts must match.
2. **The E1 regression.** `e1_regression_config()` points the same code at
   `data/filings.parquet` with as-is lines, the ticker tie-break and E1's
   `CHK-`/`P-` prefixes. Result: **6,747 chunks, 28,504 canonical paragraphs of
   42,577 occurrences — E1's exact numbers** — with `chunk_id`, `text`,
   `word_count`, `n_paragraphs`, `paragraph_ids`, `home_*` and
   `n_source_filings` **identical row for row** to the frozen
   `data/labeling_corpus.parquet`.

   One honest residual, pinned as a test rather than hidden: the ORDER of the
   `source_accession_numbers` list differs on **1 of 6,747** chunks. `chunk.py`
   sorts by `(filing_date, ticker)` with Python's stable sort, so ties keep dict
   insertion order; this builder sorts fully by `(filing_date, cik, accession)`.
   The **sets are identical on all 6,747**, and the
   `accession → (filing_date, form)` mapping is identical on all 6,747 — which
   is everything `features.py::explode_label_occurrences` reads.

### 1.3 Measured, from the real corpus

| | |
|---|---|
| sections (W1-core) | 20,982 |
| reflowed lines | 3,007,084 |
| canonical paragraphs | 2,170,417 (**27.82%** duplicate) |
| **chunks** | **317,081** |
| sections producing zero chunks | 2,824 |
| by section type | MDA 172,098 · EX99_PRESS_RELEASE 94,545 · RISK_FACTORS 49,648 · 8K_BODY 790 |
| by sector | financials 98,418 · tech 63,276 · consumer 54,471 · healthcare 52,404 · energy 48,512 |
| by extraction status | OK 276,026 · FLAGGED 41,055 |
| by era | pre-2019 107,715 · 2019+ 209,366 |
| word count | mean 389.6 · p50 377 · p95 501 · p99 648 · max 1,992 |
| source filings per chunk | mean 2.71 · max 6,220 |
| filings covered | 14,510 distinct home accessions |

P3's stale row for comparison: 20,832 sections → 2,150,145 canonical → 314,211
chunks → 2,815 zero-chunk sections. The deltas are P5's +150 core sections and
its text fixes.

### 1.4 Output order: chronological, on purpose

The F3 corpus is grouped by FORM, so emitting in corpus order would have made
every night section-type-homogeneous. The table is sorted into
`(filing_date, cik, accession, section_type, in-section position)` order, which
buys two things:

1. a campaign **stopped early is a complete TIME PREFIX** rather than "every
   MD&A and Risk Factors chunk and not one press release" (i.e. no
   guidance-applicable rows at all). HANDOFF §4's standing lesson is that any
   long run gets killed;
2. **per-night wall clock becomes comparable**, because MD&A passages are much
   longer than press-release passages.

Every home accession's chunks stay contiguous (verified: 14,510 accessions, 0
non-contiguous), which is what lets segments be cut on filing boundaries.

### 1.5 Schema (31 columns)

`chunk_id`, `section_type`, `text`, `word_count`, `n_paragraphs`,
`paragraph_ids`, `home_{cik,accession_number,form,filing_date}`,
`source_{ciks,accession_numbers,filing_dates,forms}`, `n_source_filings`,
`home_{company_name,sector,stratum,report_date,extraction_status,
extraction_confidence,extraction_method,flags}`, `in_member_spell`,
`in_member_spell_plus12m`, `window_rule`, `line_rule`, `guidance_applicable`.

`in_member_spell*` are triage columns from the PIT membership table — **never
conditioning variables in a walk-forward** (P4 §5.1 / P5 §8.2 carried forward).

### 1.6 chunk_id scheme

Same construction as E1, different namespace:

```
paragraph_id = "E2P-"   + sha1(normalize_paragraph(line)).hexdigest()[:16]
chunk_id     = "E2CHK-" + sha1("|".join(paragraph_ids)).hexdigest()[:16]
```

The prefixes make collision with E1 impossible by construction; it is also
verified empirically (0 of 317,081), because E1's 25 mega-caps are E2 universe
members and byte-identical boilerplate across the two corpora is expected.

---

## 2. The reserve choice: 256, and the numbers behind it

At training time `convert_to_mlx.fit_passage` fitted 2,048 tokens including the
**real** answer. F4 has no answer, so a fixed reserve replaces it — the
extension point `H3_attenuation.md` §1.6 deliberately left unbuilt.

Measured maxima for this exact student: H3v2's 6,746-row relabel **max 151**
generated tokens (mean 34.83, p99.9 130); the v1.2 epoch-2 eval **max 151**
(mean 36.7); the v1.2 training targets' own loss-bearing region **max 152**.

Cost of the reserve, measured on a seeded 5,000-chunk sample of the real chunk
table (seed 20260828, real tokenizer, CPU only): 0 → 0.220% truncated · 160 →
0.360% · 192 → 0.420% · **256 → 0.700%** · 384 → 1.360% · 520 → 3.020%.

**256 = 1.68× the largest answer ever generated or trained on, for ~890 extra
truncated rows over a 192-token reserve.** A 520-token reserve (never truncate
any conceivable generation) would quadruple truncation to guard a case that has
not occurred in 7,756 measured generations.

The reserve is a **length-regime guarantee, not a cap**: `max_tokens` stays 520,
so a longer answer is produced in full — it merely extends past position 2,048.
That is precisely why the reserve sits well clear of the maximum rather than at
it. Truncation drops only the passage TAIL (binary search on the passage's own
token prefix), the instruction is never touched, and every affected row carries
`passage_was_head_truncated` + `passage_chars_kept`.

Context, for scale: the instruction alone renders to **425** prompt tokens
(pinned by test); F4's mean prompt is **1,069.4** tokens.

---

## 3. The runner — `finetune/label_e2.py`, and why a sibling not an `--f4` flag

`relabel_e1.py --v12` swaps eight PATHS while every function keeps its shape.
F4 changes the shapes in four ways, each of which would need a branch inside a
module whose 36 tests pin a **ruled** record (H3/H3v2) byte-for-byte — one of
them rebuilds H3's shipped parquet to the byte:

1. **No gold answer.** `read_mlx_rows`, `write_sidecar` and `load_rows` all
   require `[system, user, assistant]` records; `eval.render_prompt_token_ids`
   asserts the stored messages. F4 renders from raw corpus text with a fixed
   reserve.
2. **No teacher.** No agreement summary; no same-row reproduction check.
3. **`TARGET_ROWS = 6746` is asserted.** F4 is 317,081 rows over 24 nights.
4. **missing→NONE is ADOPTED at F4's writer.** In `relabel_e1.py` the identical
   rule is explicitly "PROPOSED, NOT ADOPTED" and the raw value is stored.
   Flipping that inside the shared function is exactly how a ruled artifact
   gets silently rewritten.

So `relabel_e1.py` is **imported and reused**, not forked:
`ensure_trailing_newline` (the torn-journal repair), `update_manifest`,
`journal_progress`, `totals_from_journal`, `student_label_row` (the
taxonomy-safe label mapping), `teacher_schema` (the arrow-schema copy),
`artifact_name`, `utcnow` — plus `eval.py`'s `load_predictions`,
`append_prediction`, `parse_model_output`, `validate_schema`, `sha256_*`,
`_adapter_provenance`. **`relabel_e1.py`, `eval.py`, `convert_to_mlx.py` and
`chunk.py` are byte-unchanged** (`relabel_e1.py` re-hashes to H3v2's recorded
`383a0222a44608b7…`).

### 3.1 The prompt, and the one thing that could have gone wrong

`render_prompt_ids(tokenizer, instruction, passage)` calls
`convert_to_mlx.to_messages()` + `convert_to_mlx.render()` with an empty
assistant slot and returns `all_ids[:prompt_offset]` — the offset is computed
from `messages[:-1] + add_generation_prompt`, so the assistant content cannot
reach the prompt.

**That is asserted, not argued.** `test_label_e2_prompt.py` renders 40 real
v1.2 eval rows both ways and requires
`render_prompt_ids(...) == eval.render_prompt_token_ids(...)` **token for
token**, and separately proves the assistant slot is sliced away by rendering
with the literal string `"SECRET ANSWER"` and comparing prefixes. The same
check runs again, per row, inside the GPU repro canary.

Look-ahead safety is unchanged from E1: system = the frozen instruction, user =
the passage, nothing else. No ticker, CIK, company name, filing date,
`section_type` string or outcome enters. (The residual self-identification
channel — passages that name their own company — is the known documented risk,
REDTEAM finding #2, not something F4 changes.)

### 3.2 The writer: missing→NONE with its audit flag

```
on a GUIDANCE-APPLICABLE passage, if the student's JSON omits the
guidance_direction key entirely, persist "NONE" and set
guidance_imputed_none = True.
```

Scope limits, enforced in code and pinned by six tests:

- **Applicability comes from the corpus's own `section_type`**, mirroring the
  teacher's per-section JSON schema. Measured from the frozen v1.2 training
  targets, not guessed: `EX99_PRESS_RELEASE` (1,171 rows) and `8K_BODY` (8) are
  the only section types whose targets ever carry the key; `MDA` (3,961) and
  `RISK_FACTORS` (1,606) never do. A test re-derives that partition from
  `mlx_data_v12` and requires it to equal the constant. **It is a WRITER-side
  rule — `section_type` never enters a prompt** (rubric v1.1, HANDOFF §3
  2026-08-10).
- It rewrites **only** the omitted-key case. An unparseable row, an
  out-of-taxonomy value (`"SIDEWAYS"`), and every wrong value stay exactly as
  emitted, with their `schema_issues`.
- An **explicitly emitted** `NONE` carries `guidance_imputed_none = false`. The
  flag distinguishes the two, so the choice is auditable and reversible.
- It touches nothing else — a test compares every other field against
  `relabel_e1.student_label_row`'s output.
- On a non-applicable passage an omission stays **NULL**. Imputing there would
  invent a label the teacher never asked for.

Disclosed with the rule, every time: the underlying omission rate **worsened**
between epochs (321 → 385 of 6,746 on E1), and `guidance_signed_mean` pooled
retention regressed to 0.6248 [0.3271, 0.8776].

### 3.3 Output parquet — 43 columns

Columns **1–34 are `data/labels_v12.parquet`'s own arrow schema**, copied from
the file (`relabel_e1.teacher_schema`) rather than re-declared, so the
`features.py` join stays a path swap. `labels_v12.parquet` is a **schema
template only** — never a teacher for these rows, opened read-only.

- `parse_error` widened `null` → `string` (the teacher had no failures; the
  student's must be storable). Round-tripped by test.
- `home_ticker` null and `source_tickers` empty — E2 filings are CIK-keyed and
  inventing a ticker would be false provenance. Both fills are recorded in the
  segment manifest.
- **9 F4 columns appended**: `segment_id`, `passage_was_head_truncated`,
  `passage_chars_kept`, `prompt_tokens`, `prompt_sha256`, `latency_s`,
  `schema_issues`, `guidance_applicable`, **`guidance_imputed_none`**.
- **Parquet schema metadata** carries the ratified demotion verbatim
  (`f4_red_flags_status`, including the 42.00% [35.37, 48.93] figure), the
  labeler and adapter sha, the guidance rule, and `f4_teacher = "NONE — these
  are STUDENT labels, not Claude labels"`. It travels with the file, not only
  with the manifest.
- `distress_tier` uniformly empty by construction (HANDOFF §7). Parse failures
  keep their row with `parse_ok = false`. Out-of-taxonomy red-flag
  categories/modalities are dropped and recorded in `schema_issues`.
- The segment manifest additionally counts guidance emitted on a
  **non-applicable** section and sentiment emitted on RISK_FACTORS — both are
  stored as emitted, never silently edited, and both are real measurements F5
  will want.

### 3.4 Provenance preflight (all before a token is generated)

1. `chunks_v1.parquet` sha == the pin, and its manifest's corpus sha == P5's.
2. `rows.jsonl` chunk_id-list sha == the plan's; `rows.jsonl` file sha == the
   sha this segment's first process recorded (the passages cannot change under
   a resume).
3. `mlx_data_v12/{train,valid}.jsonl` shas == the v1.2 epoch-2 training
   manifest's, and == the plan's.
4. Instruction sha == `ebc45a85…` == the plan's == the reference eval's.
5. `eval._adapter_provenance` (base model, LoRA type, rank/keys) + the adapter
   `adapters.safetensors` sha checked **twice**: against the reference eval's
   manifest AND against the pinned G1 adapter `cadca849…`. Either mismatch is a
   `SystemExit` naming both hashes.
6. Base weights sha recorded from the training manifest.

Rehearsed under `.mlx_venv` with no model load: all three cross-checks return
`true`.

### 3.5 The verify-artifact substitute: `--repro-canary`

F4 labels unlabeled text, so it has no reference of its own. The canary
regenerates N rows of the frozen v1.2 **eval** split through the F4 code path
and compares byte-for-byte to
`runs/2026-08-28-v12-eval-epoch2/predictions.jsonl`. Greedy decoding on a
token-identical prompt with the same adapter is deterministic, so 10/10 proves
the prompt renderer, the adapter and the decoding are the ones gate G1 was
ruled on. Rows whose untruncated prompt exceeds F4's 1,792-token budget are
skipped and **counted** — there F4's fixed reserve legitimately truncates where
the eval's answer-fitted truncation did not, and a mismatch would be the policy
working, not a defect.

### 3.6 Segmentation and resume

One **segment = one night = one run directory** with its own `rows.jsonl`,
journal, manifest and parquet.

- 24 segments, contiguous row ranges cut on `home_accession_number` boundaries,
  so **a completed segment always contains whole filings** — filing-level
  features aggregate over every chunk attributed to a filing, so a partially
  labeled filing is a silently biased filing.
- Per-segment journals, not one campaign journal: 317k records in one file
  would be re-parsed and held in RAM on every resume beside a ~5 GB model on a
  16 GB box. A segment journal is ~13k records.
- Per-row `write` + `flush` + `fsync`; a kill loses at most the in-flight row.
  Resume by re-running the identical command. Exit 0 = complete, 2 = partial.
- H3's torn-final-line repair is carried over verbatim (imported), with its own
  test: without it a resume silently loses one good row per kill.
- Drift guard: each journal row stores `prompt_input_sha256` (instruction sha +
  passage bytes) and the rendered token sha. A changed passage or instruction
  under a resume is a **hard stop**. This replaces `relabel_e1`'s full
  pre-render pass — same protection, but a resume costs no re-rendering, which
  matters because F4's fixed-reserve fit binary-searches the long rows.
- `--finalize-campaign` streams the finished segment parquets into
  `labels_e2_v1.parquet` and accumulates per-night provenance. Run at any time:
  with segments outstanding it writes `COMPLETE: false` naming every missing
  one, never a partial parquet that looks complete.

---

## 4. Projected wall clock, banded honestly

Not simply H3v2's measured 1,477.7 chunks/h — F4's prompts are longer. Mean
prompt **1,069.4** tokens (seeded 5,000-row sample of the real chunk table)
against E1's 983.7. Calibrating on H3v2's own measurement (prefill 879.1 tok/s,
decode 30.2 tok/s, plus a residual 0.164 s/row that reproduces its 2.436 s/row
exactly) and using the F4 section-mix's expected answer length (35.33 tokens,
from H3v2's per-section means weighted by F4's mix):

    1069.4/879.1 + 35.33/30.2 + 0.164 = 2.550 s/row  ->  1,412 chunks/h

| scenario | chunks/h | hours | nights @10 h |
|---|---|---|---|
| optimistic (H3v2's measured E1 rate) | 1,477.7 | 214.6 | 21.5 |
| **projected** | **1,412** | **224.6** | **22.5** |
| conservative (P3's quoted epoch-1 rate) | 1,068 | 296.9 | 29.7 |

**Plan on 24 nights** at the plan's segment size (~9.4 h/night projected, 8.9 h
optimistic, 12.4 h conservative — the last simply needs one resume per night).
Inside the 21–29 overnights the owner was quoted at ratification.

---

## 5. Tests — 69 new, all offline, 98 pytest passed

| file | n | interpreter |
|---|---|---|
| `finetune/test_build_f4_chunks.py` | **22** | system python3 |
| `finetune/test_label_e2.py` | **40** | system python3 |
| `finetune/test_label_e2_prompt.py` | **7** | `.mlx_venv/bin/python` (its own runner; the venv has no pytest) |
| `finetune/test_relabel_e1.py` (unchanged) | 36 | system python3 — **still green** |

What they pin, by theme:

- **reflow_v1**: additivity; the glue rule; the trailing-run drop; equality with
  P3's own implementation over 200 random line shapes; the below-floor flush
  wrinkle (§7 item 1).
- **packing**: equality with `chunk.pack_windows` on a synthetic corpus; the
  per-filing (not per-section) source union; the **E1 regression** (3 tests).
- **determinism**: two builds → identical sha.
- **ids**: the construction; E2/E1 prefix disjointness; uniqueness and
  zero-collision on the shipped 317,081.
- **preflight guards**: corpus sha, chunk-table sha, chunk-manifest corpus sha,
  instruction sha, adapter sha (both cross-checks), rows-list sha.
- **reserve/truncation**: no-op when it fits; tail-only truncation; budget
  respected; bigger reserve keeps less; refusal when the instruction alone
  overflows; the reserve clears every measured generation length.
- **writer**: missing→NONE on applicable / NOT on non-applicable / NOT on
  invalid enum / NOT on parse failure; explicit NONE unflagged; nothing but
  guidance touched; `distress_tier` empty; out-of-taxonomy dropped.
- **schema**: 34 + 9 = 43; `parse_error` widening round-trips a real failure;
  metadata carries the demotion and the labeler.
- **resume**: finished rows skipped; hard stop on a changed passage; hard stop
  on a changed instruction; torn-line repair + idempotence.
- **segmentation**: full coverage, no split filing, balance, single-segment
  edge; the on-disk plan covers every chunk exactly once; every night carries a
  full section-type mix.
- **campaign**: two segments concatenate with accumulated provenance; missing
  segments reported rather than looking complete; `cost_usd == 0`.
- **W1-core membership edges**: the shipped table is core-only, chronological,
  spans the full window, and never splits a filing.
- **applicability**: `GUIDANCE_APPLICABLE_SECTION_TYPES` re-derived from the
  frozen v1.2 training targets and required to match.

---

## 6. Artifacts

| path | sha256 | what |
|---|---|---|
| `data/f4/chunks_v1.parquet` | `d67395ece6126045…` | 317,081 chunks × 31 cols |
| `data/f4/chunks_v1_manifest.json` | `b90d81b516b5db59…` | build provenance + census |
| `data/f4/campaign_plan.json` | (timestamped) | 24 segments, per-segment chunk_id-list shas |
| `data/f4/RUN_COMMANDS.md` | — | the main session's commands, smoke checklist, resume recipe |
| `finetune/build_f4_chunks.py` | `3208b491a121ebef…` | the chunk builder |
| `finetune/label_e2.py` | `177001a053befcf0…` | the labeling runner |
| `finetune/test_build_f4_chunks.py` | `035bab1e09db51dc…` | 22 tests |
| `finetune/test_label_e2.py` | `02293014e058f87d…` | 40 tests |
| `finetune/test_label_e2_prompt.py` | `f3f241fb812438bf…` | 7 tokenizer tests |

Frozen artifacts re-hashed after all work and unchanged: `data/labels.parquet`
`c3531f03cda602bc…`, `data/labels_v12.parquet` `ca373b953504535b…`,
`data/filings.parquet` `5e09a749f97d932b…`,
`data/filings_e2_v2.parquet` `15853e9f54902a93…`,
`data/f3/v2/extraction_audit.parquet` `207f392aa54c5151…`,
`finetune/relabel_e1.py` `383a0222a44608b7…`.

---

## 7. Traps for the main session

1. **`reflow_v1` emits some below-floor paragraphs, by design, and I did not
   "fix" it.** A run of short lines that has NOT reached 40 words is still
   flushed when the next long line arrives. Corpus-scale: 629,050 of 3,007,084
   reflowed lines (20.9%) are below the floor, carrying 5.5% of the words;
   after dedup and packing, **13.57% of the shipped chunk table's paragraphs
   are below-floor, carrying 4.95% of its words**, and exactly **2** of 317,081
   chunks consist only of them. This is P3's ratified implementation and the one
   the owner's 314,211-chunk scope was quoted from — changing it would silently
   move the ruled scope. It is pinned by a test and documented in the
   function's docstring.
2. **41,055 chunks (12.9%) come from `FLAGGED` sections, and the ~6 known
   garbled rows are among them.** P5 shipped the garble screen as a FLAG, not a
   filter, so Ford's two font-map exhibits (5,942 words of `prose_word_share =
   1.0` garbage) will be labeled. No exclusion was ruled, so none was applied —
   but `home_extraction_status`, `home_extraction_confidence` and `home_flags`
   are on every chunk row, so filtering them post-hoc costs a join, not a
   rebuild.
3. **8K_BODY: 790 chunks here, 8 in E1 training.** The student has effectively
   no supervision for this section type. HANDOFF §7's "not evaluable" applies
   with more force at E2 scale, not less.
4. **`--prepare-segment` must run before `--segment`**, with the SYSTEM python3:
   the MLX venv has neither pandas nor pyarrow and cannot read the chunk
   parquet. The runner exits with the exact fixing command.
5. **The plan must be regenerated if `--segment-rows` changes**, and segment ids
   shift with it. Do not mix a plan written at one segment size with run
   directories created under another (the chunk_id-list sha catches it, but
   cleanly avoiding it is better).
6. **Chronological order is load-bearing for early stopping**, not cosmetic. If
   anyone re-orders the chunk table, a stopped campaign stops being a usable
   time prefix.
7. **`red_flags` is EXPLORATORY / disclosure-only** in every artifact — parquet
   metadata, segment manifest, campaign manifest. Do not let a downstream
   summary promote it back. Sentiment and composition features are unaffected.
8. **W1-core means the extension stratum is unlabeled**, and a chunk's
   `source_*` back-references therefore cover core-stratum sections only.
   Labeling the extension later is a separate campaign with its own home
   selection — an append would be wrong, because adding sections changes which
   occurrence is home.
9. **`in_member_spell*` and the F3 population-gate columns are not
   point-in-time** (P4 §5.1, P5 §8.2). Triage only, never conditioning in a
   walk-forward.
10. **The repro canary is the only verify-artifact check F4 has.** If it is not
    10/10, stop — do not "try the smoke anyway".

---

## 8. What was deliberately NOT done

- **No GPU work of any kind**, including the 10-row smoke and the canary. Long
  compute is a main-session auto-resume chain (HANDOFF §4).
- **No labeling launched.** Not one E2 chunk carries a label.
- **No edits to `relabel_e1.py`, `eval.py`, `convert_to_mlx.py` or `chunk.py`.**
  All four re-hash unchanged.
- **No ledger edits** — `HANDOFF.md`, `F3_PROGRESS.md`, `HARDENING_PROGRESS.md`
  and `RESUME_HERE.md` were not opened for writing.
- **No re-litigation of the ruled config.** W1-core, full reflow_v1 and
  missing→NONE-at-the-writer are the owner's; the recomputed 317,081 is
  reported as a scale correction, not as a reason to revisit scope.
- **No extension-stratum work, no D2 fetch, no corpus edit.**
- **No paragraph-occurrence-map artifact.** `features.py` reads the per-chunk
  `source_*` arrays, not `paragraph_occurrence_map.parquet` directly (its own
  docstring says the two are equivalent), so the map would have been a second
  ~2.2M-row file nobody reads.
