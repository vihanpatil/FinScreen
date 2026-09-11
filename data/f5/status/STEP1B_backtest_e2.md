# STEP 1B — `backtest_e2.py` + `test_backtest_e2.py` (the HEAD-1 runner)

Written 2026-09-10 by the quant-modeler session executing F5_PLAN §2 Step 1.
Every number below was measured by a command run in this session; nothing is
carried from a previous corpus or a prior session's prose.

**Amended 2026-09-10 (same day), after a red-team pass, by the session that
applied its findings.** Five changes to this runner, each with its own test:
(1) the `raw_levels` secondary arm no longer inherits the embedding PCA
PIT-rank transform — that parameter now governs the PIT-ranked arms only;
(2) a ratified `embedding.pca_k > 0` with no usable `emb` column, and any fold
realizing fewer than `pca_k` components, are REFUSALS; (3) `run_head1`
re-measures the ratified document itself and refuses a `guard` dict whose
`doc_sha256` does not match; (4) `ResultsWriter.add_header` refuses any payload
carrying a `delta`/`_ic`/`spearman` key before the margin block exists;
(5) an AST call-graph tripwire proves the census path cannot reach a fitting
function. The census was **re-run** afterwards (`text_families_e2.parquet` now
exists), so the numbers below are from that run; the population is unchanged.

**Freeze status (F5_PLAN §1): clean.** No information coefficient, correlation,
model fit or feature-versus-outcome association was computed on E2 data — in
code paths that can run, in tests, or interactively. The real run REFUSED today
(the refusal transcript is §7, and is the last thing in this report). The only
model fits that happened anywhere in this session were on the in-process
SYNTHETIC frame (`--selftest`) and inside the test file's synthetic fixtures.
`data/f5/G3_PREREGISTRATION.md` and `data/f5/G3_RATIFIED.json` do **not** exist
and were not created.

E1 and E2 backtest numbers are numerically incomparable (different benchmark);
the runner prints that sentence into every report it generates.

---

## 1. What was built

| artifact | size | sha256 (first 16) |
|---|---|---|
| `/Users/vihanpatil/personal/projects/FinScreen/backtest_e2.py` | 2,260 lines | `8525538003b6e385` |
| `/Users/vihanpatil/personal/projects/FinScreen/test_backtest_e2.py` | 943 lines, 53 tests | `110545fbdf660e98` |
| `/Users/vihanpatil/personal/projects/FinScreen/data/f5/G3_PARAMS_SCHEMA.json` | 43 required keys + 1 optional | — |
| `/Users/vihanpatil/personal/projects/FinScreen/data/f5/census_head1.json` | 40 candidate quarters, all **four** inputs pinned | `e475baa0b6096489` |

Three modes:

- `--census` — no fitting, no association of any kind; per-candidate-quarter row
  counts, usable CIKs, target completeness, purge counts, per-quarter dedup n.
  Allowed before ratification; writes `data/f5/census_head1.json`.
- `--selftest` — end-to-end over an in-process seeded SYNTHETIC frame,
  exercising guard → params → folds → purge → per-fold PCA → margin → TOST →
  arms → standing rows → LOCO → seed band → results JSON → report → run log.
- default (the real run) — **refuses** unless `data/f5/G3_RATIFIED.json` exists
  and its `doc_sha256` equals `sha256(data/f5/G3_PREREGISTRATION.md)`, then
  reads **every** pinned parameter from the single fenced ```` ```json g3-params ````
  block inside that document. The module holds no default for any of them; the
  only hard-coded parameter values are `SELFTEST_PARAMS`, and a test proves that
  name never appears inside `run_head1`.

**Frozen modules are imported, never edited or copied** (`git status` shows only
new files; `spec.py` `e8396d8e0fb295b4`, `backtest.py` `9183753177d87ea8`,
`controls.py` `b44358c389134dd9`, `features.py` `cfa0352a7f0f66af`,
`target_e2.py` `233fb1c2d7da81c9`, `features_e2.py` `877dea17a9f3136c`,
`numeric_features_e2.py` `816b308c1ff4e083`, all byte-unmodified):

- key-agnostic, imported as-is: `spec.pit_trailing_rank_frame`,
  `spec.zero_information_benchmarks` / `zero_information_summary`
  (`ticker_col` is a parameter → `"cik"`), `spec.bootstrap_noise_anchor`
  (fit callable injected), `spec.embargo_census`, `spec._spearman_or_nan`,
  `backtest.build_walk_forward_folds`, `assert_no_fold_leakage`,
  `fit_predict`, `quintile_spread`, `standing_section_lines`,
  `backtest.XGB_PARAMS` / `FORM_ABLATION_FORMS` /
  `COMPANY_QUARTER_DEDUP_GAP_DAYS`, `controls.mde_from_se`;
- ticker-keyed, **wrapped** (never copied): `company_quarter_dedup_keep_mask` —
  the frame is handed to the frozen function with `ticker` bound to the CIK
  string, so the frozen clustering, later-filing rule and form-aware same-day
  tiebreak are exactly the published ones (a test asserts the wrapper's output
  equals the frozen call's, cluster for cluster);
- **not callable, not copied, documented as such**: `backtest.run_backtest` /
  `run_form_controlled_ablation` bind E1's module-global feature lists and E1's
  `TARGET_COL`, so the form ablation here reuses the frozen
  `FORM_ABLATION_FORMS` ruleset and the frozen fold builder and runs the same
  per-fold loop on the restricted rows; `backtest.fit_predict` fixes
  `random_state` inside the frozen params, so `fit_predict_seeded(seed=None)`
  calls it verbatim and the seeded path rebuilds the SAME estimator with only
  `random_state` moved (pinned bit-for-bit by a test).

The E2 target column `target_excess_63` is carried under `backtest.TARGET_COL`
as well, so no frozen module needed an edit; the two columns are asserted equal
on every build.

---

## 2. Every assertion, with its measured value

| # | assertion | where | measured |
|---|---|---|---|
| A1 | input sha256s equal the `data/f5/*_manifest.json` records before a byte is used (`controls.py` `_sha256_file` pattern) | `assert_input_shas`, every real/census load | 4/4 match on the re-run census: target `c35956b7…`, text `f9084e95…`, numeric `23f2ef2e…`, families `acc2712e…`. **`text_families_e2.parquet` now exists, so the families arm has been exercised on real data**: 7,723 family rows join LEFT onto the 7,634-row frame and `n_emb_missing = 0` — every modeling row carries a 384-d pooled embedding |
| A2 | the real run refuses without `G3_RATIFIED.json` | `require_g3`, `main` | measured today: exit code **2**, nothing fitted (§7) |
| A3 | the real run refuses when the document's sha ≠ the ratified `doc_sha256` | `require_g3` | test: a one-line edit after ratification raises `G3Refusal` |
| A4 | exactly one ```` ```json g3-params ```` block; 0 or 2 is a refusal | `extract_params_block` | tests for 0, 1, 2 blocks |
| A5 | 43 required parameter paths present and correctly typed; unimplemented named rules (`purge_rule`, `se.method`, `se.block_length_rule`, `se.alternative`, `tost.reference_distribution`, `spec.secondary`, `loco.index_rule`) are refusals | `validate_params` | tests; schema file lists the same 43 paths (asserted equal to `REQUIRED_PARAMS`) |
| A6 | `SELFTEST_PARAMS` cannot reach the real run | source-scan test over `run_head1`'s body | 0 occurrences |
| A7 | analysis frame = inner join on `(cik, accession_number)`, `in_membership` only | `join_frames` | **7,634** joined rows (independently equal to F5_PLAN §3 decision 4's stated 7,634), 229 with a null target → **7,405 modeling rows**, **144 CIKs**, `filing_date` 2016-07-05 → 2026-05-21; forms 8-K 3,897 / 10-Q 2,637 / 10-K 871 |
| A8 | the target alias equals the E2 target column | `join_frames` assert | holds on every build |
| A9 | rows are sorted ascending by `filing_date` (required by `spec.pit_trailing_rank_frame`), ties broken by `(cik, accession)` for a reproducible row order | `join_frames` | monotone on the real frame and in tests |
| A10 | company-quarter dedup keeps exactly one row per near-duplicate cluster, on the CIK key | `dedup_keep_mask_cik` | real frame: **5,383 of 7,405 rows kept (72.7%)** at `gap_days = 5`; test re-derives cluster-by-cluster and checks the later filing is the survivor |
| A11 | folds come from the ratified quarter list; expanding; no walk-forward leakage | `build_folds` + frozen `assert_no_fold_leakage` | the default list 2018Q1–2026Q1 yields **K = 33 folds** (matching decision 4's stated 33); a quarter with no usable fold is a refusal |
| A12 | purge: training rows whose 63-session window closes on/after the test quarter's first session are dropped | `build_folds` | over the 33 default folds: **6,194 (row, fold) training instances purged**, per-fold share mean **6.17%**, min 2.89% (2026Q1), max 16.57% (2018Q1) |
| A13 | the purge's calendar-start comparison selects exactly the rows a first-session comparison would (because `window_close_session` is always a session) | test `test_purge_calendar_start_equals_first_session` | identical accession sets; the fixture's boundary row closes on 2018-01-02, the first session after the 2018-01-01 holiday |
| A14 | the embedding PCA is fit on TRAINING rows only | `pca_project` + test | perturbing every test row by N(0, 50) leaves the training rows' components identical to 1e-12, while the test rows' components do move (the check is not vacuous); NaN embeddings are excluded from the fit and emitted as NaN, never imputed |
| A15 | a per-fold delta cannot be serialized or printed before the margin block | `ResultsWriter` + 3 tests | `add_delta_payload` raises `OrderingViolation` before `set_margin`; `margin` is the **first key** of the results JSON in the selftest artifact; `set_margin` may be called once |
| A16 | the ladder selects the smallest satisfying margin, else UNPOWERED with no equivalence claim | `margin_procedure` + tests | tight synthetic deltas → Δ = 0.03, `kc3_branch` false; wide deltas → **UNPOWERED**, `delta_selected = None`, `equivalence = None`, CI still published. Selftest run: SE 0.0723 > 0.05/2.487 = 0.0201 → UNPOWERED |
| A17 | SE is a moving-block bootstrap with the block length from the MEASURED lag-1 autocorrelation; std/√k is recorded only to be labelled unused | `margin_procedure` | test asserts the block-bootstrap SE ≠ std/√k and that the naive value is stored under `se_std_over_sqrt_k_never_used_for_inference`; Newey–West reported beside it |
| A18 | TOST known answers at α = 0.05 with the 90% CI always printed | `tost` + test | mean 0 / SE 0.01 / Δ 0.05 → equivalence True, CI ±0.01645; mean at the margin → `p_upper = 0.5`, equivalence False; SE 0.10 → CI escapes ±Δ; the `t` reference is wider than the normal |
| A19 | seeded fit == frozen fit at the frozen seed | test | `np.array_equal` true for both `seed=None` and `seed=42` against `backtest.fit_predict` |
| A20 | census computes no association | source-scan tripwire over `run_census`'s body | none of `spearman`, `pearson`, `corrcoef`, `.corr(`, `polyfit`, `fit_predict`, `XGB` appear |
| A21 | H1's E2 zero-information floor is re-derived, not quoted from prose | `h1_noise_floor` | 2.8 × the T0 placebo SEs in `data/hardening/controls_results.json` (0.016639, 0.017439) = **0.0466–0.0488**, reproducing H1's published 0.047–0.049; a test pins the arithmetic on a synthetic controls file |
| A22 | the G2 caveats are read from `data/f4/g2/results_g2.json`, never hand-typed | `load_g2_caveats` | the file's sha is recorded with the values; E1's 36.6%/63.4% constants appear nowhere in the module |
| A23 | every run appends exactly `{utc, doc_sha256, params_sha256, results_sha256}` | `append_run_log` + test | key set asserted equal; selftest wrote one line |
| A24 | the selftest writes nothing into `data/f5` | test | the `data/f5` listing is byte-identical before and after, and the real G3 paths still do not exist |
| A25 | LOCO's index rule must match its own fold budget | `validate_params` | the literal `round(j*(K-1)/5)` with `n_folds ≠ 6` is a refusal; the applied formula is recorded per run |
| A26 | the `raw_levels` secondary arm carries the UNTRANSFORMED PCA projection even when `embedding.rank_transform_components` is true | `run_head1` (the flag is gated on the arm) | test: with the flag on, every fold of the secondary arm's frame equals `pca_project(...)` exactly (`assert_array_equal`), while the primary arm's components differ; a second test pins that the flag still bites on the PIT-ranked arms |
| A27 | a ratified `embedding.pca_k > 0` with no usable `emb` column is a refusal, and so is any fold realizing fewer than `pca_k` components | `run_head1` / `assert_pinned_components` | tests: a families frame without `emb` refuses ("silently dropped"); `pca_k = 99` against a 6-wide synthetic embedding refuses naming the per-fold `k_effective` |
| A28 | `run_head1` re-measures the ratified document itself; a fabricated `guard` dict cannot reach a fit | `run_head1` (defence in depth) | tests: a forged `doc_sha256` against a real synthetic pair refuses ("not a ratification"), and the same forgery against the repo's real paths refuses because nothing is ratified; no results file is written in either case |
| A29 | a delta/IC/Spearman-keyed payload cannot enter the results document through `add_header` either | `ResultsWriter.add_header` | test: `{"spearman_ic": …}`, a nested `mean_fold_delta_dedup`, and a `per_fold_delta__*` header key are all `OrderingViolation` before `set_margin`; provenance-shaped headers (`run`, `params`, `folds`) pass unchanged |

### Measured population of the head-1 frame (census, `data/f5/census_head1.json`)

- 40 candidate test quarters (2016Q3 … 2026Q2); rows per quarter **161–202**
  (mean 185.1) over **82–99 CIKs**.
- **Dedup rows per quarter, over the 33 ratified folds (2018Q1–2026Q1): 119–161,
  mean 136.3** — the plan's working assumption was ≈ 158. This is the range that
  sizes the confirmatory arm.
- Over all **40** candidate quarters — i.e. including the seven the default
  fold list excludes (six pre-burn-in, 2016Q3–2017Q4, plus 2026Q2) — the range
  is **118–161, mean 134.6**; the 118 minimum is a tie between **2017Q3**
  (pre-burn-in) and **2026Q2** (the partial terminal quarter of open question
  1). Neither is in the ratified fold list.
- Rows with `train_overlap_share > 0`: **5,938 of 7,405 = 80.19%** (per quarter
  117–170). The "without overlap" arm therefore scores about a fifth of the
  frame.
- 10-K/10-Q rows (the form-controlled ablation's observation set): **3,508 =
  47.37%**.
- Null-target rows dropped at the join: 229 = 180 (all of 2026Q3) + 16 (2026Q2)
  + 33 spread over 2017Q3–2021Q2 (2–3 per quarter — the 74 coverage-gap filings
  `STEP1A_numeric_features_e2.md` §2 already counts).
- GLD rows present in the frame: **8**.
- LOCO budget at the ratified default (6 folds at indices 0, 6, 13, 19, 26, 32 =
  2018Q1, 2019Q3, 2021Q2, 2022Q4, 2024Q3, 2026Q1; training members 96, 101, 115,
  127, 136, 144): **1,438 refits**. The seed band at seeds 1–100 is
  100 × 33 × 2 = **6,600 fits**.

---

## 3. Runtimes (M5, single process)

| step | wall |
|---|---|
| `python3 backtest_e2.py --census` (real frame, 4 sha assertions incl. the families table, 40 quarters) | **1.2 s** |
| `python3 backtest_e2.py --selftest` (672 synthetic rows, 10 folds, 3 spec arms, 3 blocks, PCA, ablation, LOCO, 3-seed band, anchor) | **3.4 s** |
| `python3 -m pytest -q test_backtest_e2.py` | **8.8 s — 53 passed, 0 failed, 0 skipped** (44 before the red-team pass, +9) |
| `python3 -m pytest -q test_backtest_e2.py test_heads_e2.py test_text_families_e2.py -m "not slow"` | 9.6 s — **142 passed, 1 deselected** |
| `python3 -m pytest -q test_spec.py test_controls.py test_diagnose.py test_pit.py test_phase_c_leakage.py test_target_e2.py test_features_e2.py test_numeric_features_e2.py` | 105 s — **215 passed** (4 pre-existing `PytestUnknownMarkWarning`s) |

No test was deleted or weakened. The real run's cost is not measured (it cannot
run): the fit count is ≈ 3 arms × 33 folds × 3 blocks (297) + anchor (2 × 33 × 2
= 132 refits plus 4,000 resamples/fold) + 6,600 seed-band + 1,438 LOCO ≈ 8,500
XGBoost fits.

---

## 4. Open questions for G3 (no recommendation attached)

1. **Last test quarter.** 2026Q2 survives into the candidate list with 187 rows
   only because its 16 unresolved-target rows were dropped; 2026Q3 is entirely
   unresolved (180/180 null). Scoring 2026Q2 would score the subset of its
   filings whose windows happened to close before the snapshot. The default
   fold list (2018Q1–2026Q1) avoids it and measures K = 33; the runner takes no
   position — it reads the quarter list.
2. **`train_overlap` at the filing level is 80.19%, not 4.5%.** The 4.53%
   figure is the CHUNK-level accession-channel share (`STEP1A_features_e2.md`);
   at the filing level, four rows in five contain at least one chunk that
   touches the v1.2 training split. The with/without-overlap arm as implemented
   is an EVALUATION-side restriction (the fit is unchanged, the scored set
   shrinks to ~1,467 rows). Whether the without-overlap arm should also drop
   those filings from training — and whether a 20%-of-frame arm is informative —
   is not a decision this module takes.
3. **Embedding block and the standing anchor.** The per-fold PCA parameter
   `embedding.rank_transform_components` is implemented both ways because
   whether the components should pass through the PIT-rank transform is a
   pre-registration choice, not an analysis choice. Separately, the frozen
   `spec.bootstrap_noise_anchor` takes one frame rather than per-fold frames, so
   the standing anchor is computed on the confirmatory block WITHOUT the
   per-fold embedding components; the results JSON says so in
   `standing.bootstrap_anchor_scope`. **The families path has now been exercised
   on real data** (the re-run census loads, sha-asserts and joins
   `text_families_e2.parquet`: 7,723 rows, `n_emb_missing = 0` on the 7,634-row
   frame) — what has never run on real data is the FIT, which the freeze
   forbids. Since the red-team pass, `rank_transform_components` governs the
   PIT-ranked arms only (the `raw_levels` arm keeps the untransformed
   projection), and a pinned `pca_k` that the data cannot realize is a refusal
   rather than a narrower block.
4. **Measured n_dd is 118–161 per quarter (mean 136.3), not ≈ 158.** Every
   published MDE bracket predates this measurement; Step 2 re-derives it at
   K = 33 and at this n_dd.
5. **Purge rule, stated exactly.** Training rows whose `window_close_session`
   is on or after the test quarter's first session are dropped (6.17% of
   training rows on average, 16.57% in 2018Q1). Rows with an unknown close date
   are kept by the rule, and are in any case absent from the modeling frame
   because their target is null. No additional embargo buffer is applied.
6. **Exploratory red-flag row.** It is run on every spec arm and every
   evaluation set and is tagged `text_and_numeric_exploratory` in every table;
   whether G3 wants it restricted to the primary arm is open.
7. **GLD.** Eight `is_gld` rows sit in the analysis frame today (decision 2
   governs both their IC rows and their benchmark membership; the benchmark side
   would require a target rebuild).
8. **One document, two runners.** `heads_e2.py` (built in parallel this session)
   reads the same single ```` ```json g3-params ```` block; the four shared keys
   are `fold_quarters`, `columns.numeric`, `columns.confirmatory_text`,
   `embedding.pca_k`, and the head-2/3 key names this runner validates
   (`head2.event_window_sessions`, `head2.trailing_sessions`,
   `head3.horizon_quarters`, `head3.metric`) are a subset of the ones
   `heads_e2.py` requires. The ratified document must satisfy both key sets.
9. **Block-length rule.** `ceil_k13_ac1` (L = 1 when the measured lag-1
   autocorrelation ≤ 0, else ⌈k^{1/3}(2ρ/(1−ρ))^{2/3}⌉, capped at k) is the one
   implemented mapping from the measured autocorrelation to a block length;
   Newey–West is reported as the stated alternative. A different named rule is a
   refusal, not a fallback.
10. **Nothing here has been red-teamed by anyone else**, and no E2 IC exists
    for any of it.

---

## 5. What this module deliberately does NOT do

- It never produces an expected-return figure, a "beats the market" framing, or
  anything resembling investment advice; the results JSON and the generated
  report both carry the fixed scope sentence and the not-a-trading-signal line.
- It never chooses or adjusts folds, margins, seeds or column lists after seeing
  a result: all of them come from the ratified document, and the run log records
  `{doc_sha256, params_sha256, results_sha256}` so a second run is visible.
- It quotes no single point estimate without its per-fold table, its
  zero-information rows, the H1 noise floor and the bootstrap anchor.

---

## 6. Files this session created or edited

Created: `backtest_e2.py`, `test_backtest_e2.py`,
`data/f5/G3_PARAMS_SCHEMA.json`, `data/f5/census_head1.json`,
`data/f5/status/STEP1B_backtest_e2.md`. Re-written by the same-day red-team
follow-up: those same five files (the schema by `--write-schema`, the census by
a `--census` re-run now that `text_families_e2.parquet` exists).
**No module and no `data/f4` or `data/hardening` artifact was touched** — no
frozen module, no E1 module, no Step-1a module, no root doc. Other `data/f5`
artifacts are written by their own modules and are outside this report's
scope.

---

## 7. The refusal, verbatim (2026-09-10)

```
$ python3 backtest_e2.py
BLOCKED: /Users/vihanpatil/personal/projects/FinScreen/data/f5/G3_RATIFIED.json does not exist. The G3 pre-registration has not been owner-ratified, so no model may be fit and no IC may be computed on E2 data (F5_PLAN §1). Allowed today: --census and --selftest.
Nothing was fitted and no IC was computed. Allowed today: `python3 backtest_e2.py --census` and `python3 backtest_e2.py --selftest`.
$ echo $?
2
```
