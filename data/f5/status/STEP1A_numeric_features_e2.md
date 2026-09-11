# STEP 1A — `numeric_features_e2.py` (the NUMERIC side of the E2 feature table)

Written 2026-09-10 by the quant-modeler session executing F5_PLAN §2 Step 1.
Every number below was measured by the run that produced
`data/f5/numeric_features_e2_manifest.json`; nothing is carried from a prior
corpus or a prior session's prose.

**Freeze compliance (F5_PLAN §1):** this module and its test file compute no
information coefficient, no correlation and no feature-versus-outcome
association of any kind. No return, target or outcome column is read anywhere
in either file. The manifest records `computed_associations_with_returns: 0`
and `network_calls: 0` ($0, no API, no network).

---

## 1. What was built

| artifact | rows / size | sha256 |
|---|---|---|
| `data/f5/numeric_features_e2.parquet` | 18,300 rows × 39 cols, key `(cik, accession_number)` | `23f2ef2ec405…` (manifest `output.sha256`) |
| `data/f5/numeric_features_e2_manifest.json` | input shas, per-feature coverage by year and by sector, UNRESOLVED census, re-derived constants | — |
| `data/f5/numeric_unresolved_e2.csv` | 146 `(cik, family)` pairs | — |
| `data/f5/numeric_staleness_discards_e2.csv` | 1,868 discarded facts (guard log) | — |
| `numeric_features_e2.py`, `test_numeric_features_e2.py` | new sibling modules | module `816b308c1ff4…` (recorded in the manifest as `module_sha256`; the 2026-09-10 red-team fix pass added the second price-censoring counter, so this sha supersedes the first run's `435014e351c6…`) |

**Row universe:** every filing of a **core-stratum** member filed inside that
member's own membership spell — 18,300 rows, 175 distinct CIKs (the core
stratum has 176 CIKs; one has no in-spell filing), forms 8-K 14,258 / 10-Q
3,055 / 10-K 987, filing dates 2016-07-01 → 2026-08-24. `report_date` is never
selected from the DB and never referenced in executable code (test-enforced).

**Features (13):** the 10 E1 numeric features imported by name from the frozen
`features.NUMERIC_FEATURE_NAMES` — `log_total_assets`,
`leverage_liabilities_to_assets`, `equity_to_assets`, `cash_to_assets`,
`net_margin`, `operating_margin`, `operating_cashflow_to_revenue`,
`revenue_yoy_growth`, `net_income_yoy_growth`, `eps_diluted_yoy_growth` — plus
the three EXPANSION_PLAN §8 item 4 baseline factors `momentum_126`,
`realized_vol_63`, `book_to_market`.

**Valuation ratio — the gap check came back positive.** A shares-outstanding
concept DOES exist in `fundamentals_e2`: family `shares_outstanding` =
`dei:EntityCommonStockSharesOutstanding`, 13,793 rows, resolved for 151 of the
176 core CIKs. `book_to_market = total equity / (shares × close at
pre_session)` is therefore built rather than skipped; the 24 core CIKs whose
`shares_outstanding` is UNRESOLVED in the row universe are NaN and listed in
`numeric_unresolved_e2.csv`. The multi-class dimensioned-facts gap that F2
parked (`ingest_fundamentals.py`, family comment) is the reason most of those
24 fail and is carried forward as open question Q5.

**Provenance columns also written per row:** `form`, `sector`, `stratum`,
`filing_date`, `acceptance_datetime`, `info_date`, `post_close`,
`news_session`, `pre_session`, the resolved tag actually used for each of the
10 families (`tag_<family>`), the accounting-period length of each flow fact
used (`period_days_revenue|net_income|operating_income|operating_cash_flow`),
and `fx_currency`.

---

## 2. Assertions enforced, each with its measured value

| # | assertion | enforced where | measured |
|---|---|---|---|
| A1 | Input sha256 of `prices_e2.parquet`, `fundamentals_e2.parquet`, `filings_metadata_e2.db` match the committed record (`data/hardening/controls_results.json` `provenance.inputs`) before a byte is read; mismatch is fatal | `assert_input_shas()`, test | 3/3 match: `744e1cc5…`, `f6064adf…`, `61dcefaa…`; `concept_resolution.csv` = `5b8e5136…` |
| A2 | Fundamentals are read only through `pit.value_as_of` — a latest-value groupby is prohibited | `resolve_family_value()`; AST test bans `.tail`, `keep=`, `report_date` in executable code | 4 synthetic as-of tests green |
| A3 | A restatement filed AFTER `info_date` is invisible; the same restatement IS used once filed and inside the guard | synthetic fixture | as-of before the restatement returns 100, as-of after returns 999; the prohibited latest-value groupby returns 999 at BOTH as-of dates |
| A4 | Restatement prevalence justifying A2/A3 on the real artifact | test over `fundamentals_e2.parquet` | 20,027 / 273,268 = **7.33%** of `(cik, concept, unit, period_start, period_end)` groups are multi-valued |
| A5 | Pre-slicing per `(cik, tag)` changes no semantics (performance only) | test | identical value from full frame and slice |
| A6 | The CIK-keyed/taxonomy-aware resolver agrees with the frozen E1 `features.resolve_concept_family` where E1 can express the case | test | same tag and value (`ProfitLoss`, 6.0) |
| A7 | Staleness guard (`features.STALENESS_MAX_DAYS`, imported = 200) discards rather than returns an ancient fact, and logs it | `resolve_family_value()`, test | boundary exact: accepted at 200 days, discarded + logged at 201 |
| A8 | YoY is period- AND duration-matched, prior value must be knowable at the same as-of | tests | +0.2 against the quarter, never against a same-`period_end` annual fact; prior filed after as-of → NaN |
| A9 | Every price window ends STRICTLY before the news session | `price_factors()`, test poisoning all sessions ≥ news session with 1e9 | features bit-identical |
| A10 | Window lengths as specified | test | momentum uses `close[pre]/close[pre−126]−1`; vol uses exactly 63 log returns, `ddof=1` |
| A11 | Session rule = `controls.resolve_sessions` imported verbatim (`info_date = max(filing_date, acceptance_ET_date)`, acceptance ≥ 16:00 ET pushes one session, `pre = news − 1`) | test + build | pre-close 09:30 → same-day news session; post-close 16:30 → next session; `pre_session < news_session` on 18,300/18,300 rows |
| A12 | Sessions agree with the sibling `target_e2.py` implementation of the same rule | cross-check on the two tables | 16,859 common `(cik, accession)` rows: **0** disagreements on `info_date`, `post_close`, `news_session`; the 1,441 numeric-only rows are exactly the unpriced CIKs |
| A13 | `(cik, accession_number)` is unique | `load_row_universe()`, test | 0 duplicates |
| A14 | An UNRESOLVED `(cik, family)` nulls every feature that needs it, for every row of that CIK, and is written to the CSV | build + smoke test | 146 pairs over 113 CIKs; per-pair null check green |
| A15 | No hand-typed per-company alt tags anywhere | code review + design | no company identifier selects a tag anywhere; the only CIK literal in the file is in the docstring naming the CAD reporter. Resolution is entirely `data/f2/concept_resolution.csv` |
| A16 | No fact dated after `info_date` reaches a built row, and no used fact exceeds the staleness guard | `test_smoke_no_fact_dated_after_info_date_reaches_a_row`, which re-resolves every used `(row, family)` pair of the smoke sample and asserts, per pair, `filed ≤ info_date` **and** `info_date − period_end ≤ features.STALENESS_MAX_DAYS`, plus `checked > 500` so the check cannot pass vacuously | **1,808** (row, family) re-checks over the 200-row stride sample, **0** violations |
| A17 | Ratio features never mix currencies | `ratio()` | 0 mixed-currency ratios emitted |
| A18 | No network, no API | module | `network_calls: 0` in the manifest; no client is imported |

### Coverage (non-null share over the 18,300 rows)

`log_total_assets` 0.9937 · `leverage_liabilities_to_assets` 0.7143 ·
`equity_to_assets` 0.9938 · `cash_to_assets` 0.9461 · `net_margin` 0.8856 ·
`operating_margin` 0.5640 · `operating_cashflow_to_revenue` 0.8358 ·
`revenue_yoy_growth` 0.8916 · `net_income_yoy_growth` 0.9910 ·
`eps_diluted_yoy_growth` 0.9643 · `momentum_126` 0.9172 ·
`realized_vol_63` 0.9172 · `book_to_market` 0.7775.

Per-year and per-sector coverage for all 13 features is in the manifest
(`coverage_by_year`, `coverage_by_sector`), as is a per-feature
min/p01/median/p99/max summary (`feature_summary`).

### UNRESOLVED census (146 pairs, 113 CIKs)

`liabilities` 51 · `operating_income` 46 · `shares_outstanding` 24 ·
`revenue` 12 · `eps_diluted` 7 · `cash` 3 · `equity` 1 · `net_income` 1 ·
`operating_cash_flow` 1. Each row of `numeric_unresolved_e2.csv` carries the
classifier state (ABSENT / PARTIAL / OVERLAP), its coverage, the tags seen,
the features it nulls and the number of rows affected.

### Price censoring — TWO channels, counted separately (never a silent drop)

Both channels leave `momentum_126`, `realized_vol_63` and `book_to_market` NaN
and both keep the row; they are different defects and the manifest now reports
them side by side (`counters` block) rather than reporting only the first.

| channel | manifest keys | measured |
|---|---|---|
| (a) the CIK has **no column at all** in `prices_e2` | `ciks_without_price_coverage`, `rows_without_price_coverage` | **27 of the 175 CIKs → 1,441 rows (7.9%)** |
| (b) the CIK **has a column** but it carries no usable history inside the row's window (no close at the pre-session, or a gap/non-positive close inside the 126/63-session look-back), so the factors are NaN for want of real prices rather than for want of a ticker | `ciks_with_price_column_but_no_usable_history`, `rows_with_price_column_but_no_usable_history` | **1 CIK → 74 rows (0.4%)** |

Channel (b) is one company, CIK 712515 (tech, core spell 2017-07-01 →
2021-07-01): its price column exists but holds only 17 valid sessions, all of
them 2026-07-17 → 2026-08-10, i.e. none inside its membership spell, so all 74
of its in-spell filings have no pre-session close. Whether that column is a
coverage hole or a mis-mapped series is a price-ingestion question this module
does not answer; it reports the rows rather than absorbing them into channel
(a)'s count. 1,441 + 74 = 1,515 rows = exactly the 8.28% NaN share of
`momentum_126` / `realized_vol_63` in the coverage block above. Those 74 are
the SAME 74 filings (identical accession set, checked) that
`STEP1A_target_e2.md` §3 counts as "in-membership complete rows whose subject
price is missing at an endpoint (CIK priced, coverage gap)" — the two tables
see one defect, not two.

Separately, 0 rows failed for a short price history at the calendar's left edge
(`rows_with_pre_session_before_momentum_window` = 0; the calendar starts
2014-01-02, the first filing is 2016-07-01). `book_to_market` carries
additional, non-price NaN causes (UNRESOLVED `shares_outstanding` or `equity`,
and the FX block) — those are Q3/Q5 below, not price censoring.

---

## 3. Constants: ported unchanged, re-measured on E2

All three tuned constants are IMPORTED from the frozen `features.py` rather
than re-typed, and re-measured here. None was retuned — retuning a
pre-registration input is G3's call.

| constant | E1 value and E1 justification | measured on E2 by this run |
|---|---|---|
| `STALENESS_MAX_DAYS` | 200; on E1's 25 mega-caps the largest legitimate case was 198 days and the first broken case 208, a clean gap | 163,825 accepted facts: median 65, p99 139, p99.9 155, **max 200 (the cap itself binds)**, 232 accepted above 150 days, 47 above 180. 1,868 facts discarded (99 distinct `(cik, family)`): min 201, median 1,129.5, max 3,219 — **but 63 discards sit at 201–207 days and 234 at 201–260**, i.e. E1's clean 198/208 gap does NOT reproduce at E2 scale; the cut is now a soft boundary. Discards by family: operating_cash_flow 1,032, revenue 296, eps_diluted 179, cash 121, net_income 106, equity 76, liabilities 44, assets 7, operating_income 6, shares_outstanding 1 |
| `end_tolerance_days` = 45, `duration_tolerance_days` = 20 (YoY match) | E1 defaults inside `features.value_for_target_period`, used verbatim | YoY resolved for 89.2% (revenue) / 99.1% (net income) / 96.4% (EPS) of rows; 46 YoY values took their prior-year figure from a different tag of the same MIGRATION family (E1's single-tag search would have returned NaN for those) |
| allowed fundamentals forms | E1: `{10-K, 10-Q, 8-K}` exactly | this module uses `ingest_fundamentals.is_operating_form` (the same three forms **plus their `/A` amendments`**) — E2's own ratified rule, the one the committed classifier's coverage decisions were made under. Stated as a deviation from E1's literal set |
| momentum 126 sessions, vol 63 sessions, `ddof=1` | new at E2 (EXPANSION_PLAN §8 item 4) | pinned in the module and in the manifest's `constants` block; not tuned |

---

## 4. Runtimes

| step | wall clock |
|---|---|
| full build, 18,300 rows (`python3 numeric_features_e2.py`) | **250.4 s** on the 2026-09-10 rebuild (~4m10s end-to-end including parquet + manifest write; the first run measured 243.8 s) |
| `python3 -m pytest -q test_numeric_features_e2.py` (24 tests, incl. the 200-row stride smoke) | 7.2 s |
| `python3 -m pytest -q test_pit.py test_controls.py test_phase_c_leakage.py` (72 tests) | 44.1 s |
| `python3 -m pytest -q test_ingest_fundamentals.py test_diagnose.py test_spec.py` (177 tests) | 14.1 s |
| `python3 -m pytest -q test_target_e2.py test_features_e2.py test_numeric_features_e2.py` (73 tests: 18 + 31 + 24) | 27.9 s |

**Byte-identical reproduction, asserted (2026-09-10 red-team fix pass).** The
only code change in that pass was the second price-censoring counter, which
touches the manifest and nothing else — no feature value, no column, no row
order. The table was rebuilt from scratch afterwards and reproduced
byte-identically: sha256
`23f2ef2ec4056898018eb170ca42e3b34489d558cc06368dd38f64061a3c950d`, equal to
the pre-change sha in §1 and to the rebuilt manifest's own `output.sha256`.
Across the three builds now run (two pre-change, one post-change) the parquet
sha has never moved, so the build is deterministic and the new counter is
manifest-only.

---

## 5. Open questions for G3 (no recommendations attached)

**Q1 — year-to-date flow periods inside the ported ratios.** E1's definition
pairs whatever period each concept's as-of lookup returns. On E2 the
accounting periods disagree with revenue's period by more than 20 days for
**8,433 / 18,300 rows (46.1%) on `operating_cash_flow`**, 402 (2.2%) on
`operating_income` and 198 (1.1%) on `net_income` — dominantly the standard
10-Q presentation of cash flow as year-to-date (e.g. a 272-day OCF over a
91-day revenue). `operating_cashflow_to_revenue` is therefore scale-mismatched
on roughly half its non-null rows under the ported definition. This run
changed no definition; it materialized `period_days_*` per row so the choice
is visible and rulable. G3 decides whether the confirmatory feature set uses
the ported form, a duration-matched form, or drops the feature.

**Q2 — `STALENESS_MAX_DAYS` at E2 scale.** The E1 justification (a clean empty
band between 198 and 208 days) does not reproduce: accepted facts reach the
200-day cap and discards begin continuously at 201 (63 in 201–207). Whether
200 stays, moves, or becomes family-specific is a pre-registration input.

**Q3 — FX (G3 decision 7).** One core member reports in CAD (CIK 895728, 13
resolved families). Ratios and growth rates are currency-invariant and are
computed with a same-currency assertion (0 mixed-currency ratios emitted). The
two currency-sensitive columns, `log_total_assets` and `book_to_market`, are
NaN for **108 rows**; no rate was fabricated (no network, and the mechanism is
unratified). G3 ratifies the dated FX source before those 108 rows can carry a
level.

**Q4 — `leverage_liabilities_to_assets` and `operating_margin` coverage.**
`us-gaap:Liabilities` is UNRESOLVED (mostly ABSENT — filers that present no
total-liabilities line) for 51 core CIKs, leaving the feature at 71.4%
coverage; `operating_income` is UNRESOLVED for 46, leaving 56.4%. F2 ruled
that pre-tax income is a different line and must not be silently substituted
(`ingest_fundamentals.py`, `pretax_income` comment), and `liabilities_and_equity`
minus `equity` is a derivation this module did not make. Whether F5 carries
either feature at that coverage, or uses an explicitly-ruled derivation, is
G3's.

**Q5 — `book_to_market` denominator quality.** `shares_outstanding` is the
`dei` cover-page fact, which is undimensioned; F2 parked the multi-class
dimensioned-facts gap (30 members universe-wide) unfixed, and 24 core CIKs are
UNRESOLVED here. Cover-page shares are also as-of the cover date, not the
period end. Both caveats travel with the column.

**Q6 — row-universe scope versus `target_e2`.** This table is membership-scoped
(18,300 in-spell rows); the sibling `data/f5/target_e2.parquet` carries 29,271
rows including out-of-membership filings behind an `in_membership` flag and
excludes unpriced CIKs. The join for head 1 is therefore 16,859 rows as the
two tables stand. Which scope is the analysis frame is a fold/population
decision, not this module's.

**Q7 — STRUCK, the claim was false** (2026-09-10 red-team fix pass):
`git check-ignore -v data/f5/*.parquet` reports
`.gitignore:146:data/f5/**/*.parquet`, so the feature tables are already
git-excluded exactly as F5_PLAN §6 wants, and the two diagnostic CSVs
(`numeric_unresolved_e2.csv`, `numeric_staleness_discards_e2.csv`) are readable
diagnostics and are versioned.
