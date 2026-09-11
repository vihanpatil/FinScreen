# STEP1A — `features_e2.py` (E2 TEXT feature table)

Generated from run diagnostics (`data/f5/text_features_e2_manifest.json`,
sha of this run's artifact `f9084e95c5fa030c…`); no number below is
hand-carried from a previous session or document.

**Freeze status: clean.** No information coefficient, correlation, or any
feature-versus-outcome association is computed in `features_e2.py`, in
`test_features_e2.py`, or in producing this report (F5_PLAN §1). No target
column was read, joined, or constructed. No network call, no API call, $0.

## 1. What was built

| artifact | sha256 | rows |
|---|---|---|
| `data/f5/text_features_e2.parquet` | `f9084e95c5fa030cdea961733645970a5bb12cbbc4a54b06bb33319aae59d55c` | 14446 |
| `data/f5/feature_dictionary_e2.json` | `c24d80a6b8f5f52fc5fcfbddf6a27aded435c4fb6892ad08f2f7852e81db20c1` | 28 column entries |
| `data/f5/text_features_e2_manifest.json` | (this run) | 57 assertions |

One row per **(cik, accession_number)** — CIK is the company key end to end
(E2 labels carry no ticker; E1's accession→ticker 1:1 map has no E2 analogue).
Columns: `cik`, `accession_number`, `filing_date`, `form`, the 4 section
shares, `n_text_chunks_attributed`, the 4 sentiment/guidance features, the 13
red-flag columns, 3 section chunk counts, `train_overlap_share`,
`selfid_share`, `cross_cik_share`.

Population: **14446 filings**, **176 core CIKs**,
`2015-07-02` → `2026-08-20`; occurrence rows
854,933 over the 316,291-row frame
(corpus 317,081 minus 790 8K_BODY chunks).
Every chunk is `home_stratum == core`; the extension stratum is unlabeled and
absent by construction.

**Feature partition** (F5_PLAN §3 decision 3 / owner ruling 2026-08-27):
confirmatory = 8 legacy non-red-flag columns;
exploratory = 13 red-flag columns;
dropped = `share_chunks_8k_body` (identically 0.0, measured);
diagnostic = 6 columns that are not features.
The two zero-labeling families (YoY novelty, pooled embeddings) and the numeric
baseline are **not** in this artifact — separate modules.

**Every-occurrence attribution.** The baked parallel arrays
(`source_accession_numbers` / `source_filing_dates` / `source_forms` from
either parquet, `source_ciks` from `chunks_v1`) **are the primitive**: there is
no E2 occurrence map, so unlike E1 they cannot be re-derived from a second
artifact. `chunk_id` is set- and order-identical across the two parquets and the three
arrays both carry (`source_accession_numbers`, `source_filing_dates`,
`source_forms`) were compared element-for-element across all
317,081 rows — 0 mismatches; `source_tickers` (a deduplicated,
non-parallel list) is never read.

**Caveat constants** (regenerated from the two measurement files, never E1's):
teacher-side, v1.2 spot-check red-flag exact-set error
**84/200 = 42.00% [35.37, 48.93]**;
student-side G2, sentiment **293/337 = 86.9%
[82.9, 90.1] INDETERMINATE**, guidance
**115/119 = 96.6% [91.7, 98.7] PASS**
with its mandatory escorts — active precision
**68.67% [58.17, 77.55]**
(n=100, n_eff=84.77) and false-NONE rate
**0/80 = 0.0% [0.0, 4.58]**.
All are model-consensus agreement with owner rulings on the escalated subset —
NOT human validation of ground truth.

## 2. Census, as measured

| quantity | measured |
|---|---|
| corpus rows / frame rows / 8K_BODY excluded | 317,081 / 316,291 / 790 |
| sentiment values masked on RISK_FACTORS | 4,177 (NEUTRAL 3,452 / NEGATIVE 688 / POSITIVE 37) |
| guidance values masked on MDA + RISK_FACTORS | 2,826 = 2,803 MDA + 23 RISK_FACTORS |
| of those, ACTIVE values GUIDANCE_MAP would have scored | 230 |
| guidance-applicable rows (frame / corpus) | 94,545 / 95,335 |
| imputed NONEs (frame / corpus) | 48,293 = 51.08% of applicable / 48,790 = 51.18% |
| guidance-enum nulls left null (applicable, not imputed) | 17 |
| schema violations (disclosure only) | 23 = 17 guidance-enum + 4 red-flag-category + 2 red-flag-modality |
| rows scored for sentiment / active guidance | 263,808 / 6,479 |
| `train_overlap` chunks on the frame | 14,342 (4.534%) |
| overlap channels (frame) | home accession 10,442 · any source accession 14,341 · normalized text 487 · union 14,342 |
| overlap channels (whole corpus, incl. 8K_BODY) | home 10,442 · source 14,346 · text 487 · union 14,347 |
| `selfid` chunks on the frame | 146,958 (46.46%) |
| occurrence rows / filings / CIKs | 854,933 / 14,446 / 176 |
| occurrence rows attaching to a DIFFERENT CIK than the chunk's home | 99,636 (11.65%) |
| frame chunks with >1 distinct source CIK | 5,706 (1.80%) |
| largest occurrence set for one chunk | 6,220 filings |
| occurrence forms | 10-Q 439,376 · 10-K 234,464 · 8-K 181,093 |

`train_overlap` and `selfid` reproduce `build_draw_g2.py` / `analyze_g2.py`
exactly (14,342 and 146,958) — a third
independent implementation of the §10.1 definitions, written from the design
text, not imported from `data/f4/`. The accession-channel figure is a **lower
bound** on memorization exposure (home-CIK exposure is 15.85%, G2 §2.5), and a
paragraph-id join is structurally 0 and is never used.

## 3. Every assertion enforced, with its measured value

All 57 assertions are enforced inside the build
(`_check` records the measured value, then raises). Every one passed on this run.

| assertion | measured | expected | |
|---|---|---|---|
| `sha256:labels_e2_v1.parquet` | `f236f421096c665b373addb9ffdbb6cf45454027761838361cf179cbb7b538df` | `f236f421096c665b373addb9ffdbb6cf45454027761838361cf179cbb7b538df` | PASS |
| `sha256:chunks_v1.parquet` | `d67395ece6126045e851e05f4b8fe5c8c49bd69069c44a08b9ee8f9d67bf0857` | `d67395ece6126045e851e05f4b8fe5c8c49bd69069c44a08b9ee8f9d67bf0857` | PASS |
| `sha256:finetune/splits_v12/train.parquet` | `5e56076e3948cf9598b6cf61ad7307961735c19af2a0932f981ea6ee3dd4cb10` | `5e56076e3948cf9598b6cf61ad7307961735c19af2a0932f981ea6ee3dd4cb10` | PASS |
| `campaign_manifest_COMPLETE` | `True` | `True` | PASS |
| `campaign_manifest_rows` | `317081` | `317081` | PASS |
| `corpus_rows` | `[317081,317081]` | `[317081,317081]` | PASS |
| `chunk_id_unique` | `True` | `True` | PASS |
| `chunk_id_set_and_order_equal` | `True` | `True` | PASS |
| `section_type_agrees_across_parquets` | `True` | `True` | PASS |
| `parse_ok_all` | `True` | `True` | PASS |
| `home_stratum_all_core` | `["core"]` | `["core"]` | PASS |
| `source_arrays_identical:source_accession_numbers` | `0` | `0` | PASS |
| `source_arrays_identical:source_filing_dates` | `0` | `0` | PASS |
| `source_arrays_identical:source_forms` | `0` | `0` | PASS |
| `train_split_rows` | `5736` | `5736` | PASS |
| `text_stream_covers_corpus` | `317081` | `317081` | PASS |
| `train_overlap_channels_frame` | `{"home_accession": 10442,"any_source_accession": 14341,"normalized_text": 487,"union": 14342}` | `{"home_accession": 10442,"any_source_accession": 14341,"normalized_text": 487,"union": 14342}` | PASS |
| `frame_8k_body_excluded` | `790` | `790` | PASS |
| `frame_rows` | `316291` | `316291` | PASS |
| `frame_section_counts` | `{"MDA": 172098,"EX99_PRESS_RELEASE": 94545,"RISK_FACTORS": 49648}` | `{"MDA": 172098,"EX99_PRESS_RELEASE": 94545,"RISK_FACTORS": 49648}` | PASS |
| `train_overlap_frame_count` | `14342` | `14342` | PASS |
| `selfid_frame_count` | `146958` | `146958` | PASS |
| `mask_sentiment_on_risk_factors` | `4177` | `4177` | PASS |
| `mask_guidance_on_mda_and_risk_factors` | `2826` | `2826` | PASS |
| `mask_guidance_by_section` | `{"MDA": 2803,"RISK_FACTORS": 23}` | `{"MDA": 2803,"RISK_FACTORS": 23}` | PASS |
| `mask_guidance_active_values` | `230` | `230` | PASS |
| `guidance_applicable_frame` | `94545` | `94545` | PASS |
| `guidance_outside_applicable_after_mask` | `0` | `0` | PASS |
| `guidance_enum_nulls_left_null` | `17` | `17` | PASS |
| `imputed_nones_stored_as_NONE` | `48293` | `48293` | PASS |
| `schema_invalid_red_flag_drops` [^issue] | `{"bad_enum:red_flag_category": 4,"bad_enum:red_flag_modality": 2}` | `{"bad_enum:red_flag_category": 4,"bad_enum:red_flag_modality": 2}` | PASS |
| `n_source_filings_matches_array_lengths` | `0` | `0` | PASS |
| `occurrence_rows` | `854933` | `854933` | PASS |
| `no_backward_flow` | `0` | `0` | PASS |
| `every_occurrence_has_a_cik` | `0` | `0` | PASS |
| `no_accession_maps_to_multiple_ciks` | `0` | `0` | PASS |
| `filing_date_and_form_unique_per_key` | `{"multi_date": 0,"multi_form": 0}` | `0` | PASS |
| `section_shares_sum_to_one` | `1` | `1` | PASS |
| `share_chunks_8k_body_identically_zero` | `0` | `0` | PASS |
| `output_key_unique` | `0` | `0` | PASS |
| `in_unit_interval:redflag_DEMAND_WEAKNESS_rate_risk_factors` | `[0.0,1.0]` | `[0, 1]` | PASS |
| `in_unit_interval:redflag_IMPAIRMENT_WRITEDOWN_rate_risk_factors` | `[0.0,1.0]` | `[0, 1]` | PASS |
| `in_unit_interval:redflag_LEGAL_REGULATORY_ACTION_rate_risk_factors` | `[0.0,1.0]` | `[0, 1]` | PASS |
| `in_unit_interval:redflag_MARGIN_COST_PRESSURE_rate_risk_factors` | `[0.0,1.0]` | `[0, 1]` | PASS |
| `in_unit_interval:redflag_SUPPLY_INPUT_CONSTRAINT_rate_risk_factors` | `[0.0,1.0]` | `[0, 1]` | PASS |
| `in_unit_interval:redflag_TRADE_POLICY_EXPOSURE_rate_risk_factors` | `[0.0,1.0]` | `[0, 1]` | PASS |
| `in_unit_interval:redflag_DEMAND_WEAKNESS_rate_mda` | `[0.0,1.0]` | `[0, 1]` | PASS |
| `in_unit_interval:redflag_IMPAIRMENT_WRITEDOWN_rate_mda` | `[0.0,1.0]` | `[0, 1]` | PASS |
| `in_unit_interval:redflag_LEGAL_REGULATORY_ACTION_rate_mda` | `[0.0,1.0]` | `[0, 1]` | PASS |
| `in_unit_interval:redflag_MARGIN_COST_PRESSURE_rate_mda` | `[0.0,1.0]` | `[0, 1]` | PASS |
| `in_unit_interval:redflag_SUPPLY_INPUT_CONSTRAINT_rate_mda` | `[0.0,1.0]` | `[0, 1]` | PASS |
| `in_unit_interval:redflag_TRADE_POLICY_EXPOSURE_rate_mda` | `[0.0,1.0]` | `[0, 1]` | PASS |
| `in_unit_interval:redflag_any_rate_press` | `[0.0,1.0]` | `[0, 1]` | PASS |
| `in_unit_interval:train_overlap_share` | `[0.0,1.0]` | `[0, 1]` | PASS |
| `in_unit_interval:selfid_share` | `[0.0,1.0]` | `[0, 1]` | PASS |
| `in_unit_interval:cross_cik_share` | `[0.0,1.0]` | `[0, 1]` | PASS |
| `in_unit_interval:sentiment_negative_share` | `[0.0,1.0]` | `[0, 1]` | PASS |

[^issue]: The measured column above shows **only the two subkeys the assertion
    actually tests**. `features_e2.py` passes the whole `issue_counts` dict as
    the measured payload (so the manifest's assertion log carries a third key,
    `"bad_enum:guidance_direction": 17`) while asserting equality on
    `bad_enum:red_flag_category` and `bad_enum:red_flag_modality` alone —
    printing the full dict beside a two-key expected made a PASS look like a
    mismatch. The guidance-enum count is not unasserted: it is the
    `guidance_enum_nulls_left_null` row above (17, PASS). The assertion in
    `features_e2.py` was not changed.

## 4. Tests

`python3 -m pytest -q test_features_e2.py` → **31 passed** (20.4 s), 4 warnings
(`PytestUnknownMarkWarning` for `@pytest.mark.slow`: the repo has no pytest
config registering custom marks and this session may not create one — the mark
is declarative only, the slow tests always run).

Synthetic fixtures cover: sentiment masked on RISK_FACTORS and the masked value
never reaching the aggregate; guidance masked on MDA/RISK_FACTORS with the
would-have-scored check; the explicit `guidance_applicable` filter;
`schema_valid` is never the branch (a schema-invalid row with a usable stored
value scores normally); null guidance enums stay null; imputed NONE counts as
NONE (no score, no presence, no dilution of the signed mean); WITHDRAWN = −1;
every-occurrence explosion under CIK keys including a filing that owns no home
chunk; occurrence-count integrity and a desynchronised-length rejection;
no-backward-flow both directions; the E1 aggregation definitions (section
shares, negative-share denominator, per-section red-flag rates, NaN when the
section is absent, no modality-split feature); provenance shares; the 22 E1
feature names; the 8/13/1 partition; the normalization and distinctive-token
definitions; and two freeze guards (the module names no association statistic
and opens no price/fundamental/DB row).

Slow real-data tests re-derive the mask/applicable census from
`data/f4/labels_e2_v1.parquet` independently of the module, run the full build
and check every pinned census number, check the on-disk artifact against this
module's sha, and assert the dictionary carries the E2 constants and **never**
the E1 strings.

Pre-existing suite subset touching what this module imports
(`test_phase_c_leakage.py test_controls.py test_spec.py test_diagnose.py
test_pit.py`) → **142 passed** (56.3 s). `features.py`, `controls.py`,
`spec.py`, `pit.py`, `backtest.py`, `diagnose.py` are byte-unmodified
(`git status` shows only new files).

## 5. Runtimes

| step | wall |
|---|---|
| full build `python3 features_e2.py` | 19.2 s (peak RSS ≈ 1.6 GB; the 788 MB text column is streamed in 20k-row batches for the provenance flags and never held as a frame) |
| new test file | 20.4 s |
| pre-existing subset (142 tests) | 56.3 s |

## 6. Open questions for G3

1. **Union-over-paragraphs attribution across companies.** A chunk's occurrence
   set is the union over its paragraphs, so a company-specific passage that
   also contains one widely-shared boilerplate paragraph inherits that
   paragraph's entire occurrence set. Measured: 5,706
   frame chunks (1.80%) occur under >1 CIK, and
   99,636 of 854,933 occurrence rows
   (11.65%) attach a chunk to another company's filing; the
   largest single chunk reaches 6,220 of 14,446 filings across 169 CIKs
   (a Wells Fargo press-release chunk carrying a generic forward-looking-
   statements sentence). E1 recorded one such case and ruled every-occurrence
   attribution on that basis. Built as specified and disclosed via
   `cross_cik_share`; whether the E1 ruling extends unchanged to this scale is
   not a decision this module takes.
2. **`share_chunks_8k_body` disposition.** Written and measured identically
   0.0 under decision 9's default (exclude). Kept in the table, tagged
   `dropped`, in neither analysis block. If decision 9 moves to pilot/caveat,
   the frame changes and this artifact must be rebuilt.
3. **`n_text_chunks_attributed` is not section-normalized** and section shares
   are shares of *attributed chunks' home sections*, not of the filing's own
   sections (E1 semantics). A 10-K can therefore carry
   `share_chunks_ex99_press_release > 0`. Measured consequence:
   `guidance_any_present` is non-zero on 8.6% of 10-Ks and 7.0% of 10-Qs even
   though guidance is scored only on guidance-applicable EX99 chunks.
4. **WITHDRAWN = −1 (n = 66 on E2)** is kept at E1's `GUIDANCE_MAP` value for
   comparability; decision 11 (evaluable + one sensitivity row excluding it) is
   the owner's.
5. **Labeler anachronism.** The student is a fixed artifact fine-tuned on E1
   filings and applied to 2015–2026 E2 text; `train_overlap_share` is the
   per-filing measure of that exposure and the accession channel is a lower
   bound on it. The plan's with/without-overlap reporting is the mechanism;
   whether any additional arm is wanted is a G3 question.
6. **`acceptance_datetime` is not in this table.** Text features are dated at
   `filing_date` and every attributed chunk's text is physically present in the
   filing it is attributed to (0 backward-flow violations), so nothing dated
   after a filing's own filing date enters its text features. `info_date =
   max(filing_date, acceptance_datetime)` and the post-close session rule live
   in `target_e2.py`; the join key `(cik, accession_number)` is identical in
   both tables.
7. **Nothing here has been red-teamed yet**, and no IC exists for any of it.
