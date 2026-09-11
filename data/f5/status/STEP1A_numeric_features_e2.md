# STEP 1A — `numeric_features_e2.py` (the NUMERIC side of the E2 feature table)

> **2026-09-11: §6 supersedes the shas and the flow-feature numbers in §1–§5.**
> The period-identity defect (F5_PLAN §3 decision 22) was fixed and the table
> rebuilt. Sections 1–5 are the 2026-09-10 build as written; every number in
> them that §6 lists as changed is superseded by §6. Nothing else moved.

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
| `data/f5/numeric_features_e2.parquet` | 18,300 rows × 39 cols, key `(cik, accession_number)` | `23f2ef2ec405…` on 2026-09-10; **now `079715054f59…`** after the §6 fix (manifest `output.sha256`) |
| `data/f5/numeric_features_e2_manifest.json` | input shas, per-feature coverage by year and by sector, UNRESOLVED census, re-derived constants | — |
| `data/f5/numeric_unresolved_e2.csv` | 146 `(cik, family)` pairs | — |
| `data/f5/numeric_staleness_discards_e2.csv` | 1,868 discarded facts (guard log) | — |
| `numeric_features_e2.py`, `test_numeric_features_e2.py` | new sibling modules | module `816b308c1ff4…` on 2026-09-10, **now `cf29212c5956…`** after the §6 fix (recorded in the manifest as `module_sha256`; the 2026-09-10 red-team fix pass added the second price-censoring counter, so `816b308c…` superseded the first run's `435014e351c6…`) |

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
| A19 | **(added 2026-09-11, §6)** A fiscal-year fact and a fourth-quarter fact sharing one `period_end`, filed the same day in the same accession, resolve by DURATION and not by row order; the preference never moves the period; instant facts are untouched | `value_as_of_duration_aware()`, 8 tests | annual preference returns the year, quarterly preference returns the quarter, reversing the frame changes neither; 4,242 family-level resolutions over 1,485 built rows moved to the annual fact (§6) |

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

**Byte-identical reproduction, asserted (2026-09-10 red-team fix pass; the
2026-09-11 rebuild is re-checked the same way in §6, and the build now takes
475-476 s because the duration disambiguation adds a second
`pit.value_as_of` call per colliding flow-family lookup).** The
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

**Updated 2026-09-11 (§6) — these are the numbers G3 should read.** After the
period-identity fix the same counts are **7,603 / 18,300 (41.5%) on
`operating_cash_flow`, 20 (0.1%) on `operating_income` and 135 (0.7%) on
`net_income`** (from 8,433 / 402 / 198). The fix repaired 909 / 385 / 167
mismatched rows and introduced 79 / 3 / 104: it repairs every case where a
filer's annual flow was being divided by its own fourth-quarter revenue, and
it introduces cases where the two families' freshest knowable periods are
genuinely different dates (e.g. CIK 64803 at 2019-05-01: Q1-2019 revenue from
that day's 10-Q against FY-2018 net income, whose tag has no 2019Q1 fact).
Those introduced rows were *already* mismatched in period — 2019Q1 revenue
over 2018Q4 net income — but passed a counter that compares DURATIONS only
(89 days vs 91). The residual 41.5% is the year-to-date-versus-quarter
question this row asks and is untouched by the fix.

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

---

## 6. Period-end fix — 2026-09-11 (F5_PLAN §3 decision 22 DEFECT)

Written 2026-09-11 by the quant-modeler session that applied the fix. Every
number here was measured by the rebuild that produced parquet
`079715054f59…` / module `cf29212c5956…`, or by a direct comparison against
the superseded `23f2ef2ec405…`. **The freeze holds: this session computed no
IC, no correlation and no feature-versus-outcome association, made no network
call, and did not create `data/f5/G3_RATIFIED.json`.**

### 6.1 The defect

`pit.value_as_of` groups candidate facts by `period_end` **alone**. Its own
docstring names the consequence — the "period-identity caveat" — and says
explicitly that telling an annual amount from a fourth-quarter amount on the
same end date is the caller's feature-engineering decision, not pit's. A filer
that tags the fiscal year **and** the fourth quarter with the same end date,
in the same filing, on the same day hands that rule two facts on which every
tiebreak ties (same `period_end`, same `filed`, same `accession_number`), so
which one is returned falls through to **row order in the frame**.

Found by the app lane on ten un-curated external companies
(`data/app/status/L2_3_external_fundamentals.md` §5.3): **2 of 43 resolved
panel cells were the quarter, not the year** — CIK 1494259's revenue
(241.09 m instead of 906.98 m) and CIK 1438943's net income (15.91 m instead
of 19.17 m) — while two other companies in the same draw tag only the year and
showed it. The same column therefore meant a year for one company and a
quarter for another. The research numeric features take the identical resolver
path (`numeric_features_e2.resolve_family_value` → `pit.value_as_of`), so they
carried the identical defect.

`pit.py` is **not** edited — it is frozen and E1's known-answer tests depend on
it, and its contract ("the freshest knowable row, or None") is correct at its
own scope. The whole fix lives in `numeric_features_e2.py`, applied
pre-ratification exactly as decision 22 directs it: *"a bug fix, not a
specification choice, so it is applied pre-ratification and disclosed."*

### 6.2 The rule now

New `value_as_of_duration_aware()`, which `resolve_family_value()` calls once
per family tag:

1. **`pit.value_as_of` picks the period, unchanged**, from the unfiltered
   candidates. As-of semantics stay exactly pit's; this module chooses no
   filed date and no period of its own.
2. If more than one **duration bucket** is knowable at that `period_end`
   (buckets = `ingest_fundamentals.DURATION_BUCKET_DAYS`, and the classifier
   itself, imported — not retyped), the candidates are **pre-filtered to one
   bucket** and `pit.value_as_of` is called again on that frame. The fact that
   comes back is then chosen by duration instead of by row order.
3. Which bucket is `prefer_duration`:
   * **`"annual"` — the default, and what all 13 features use:** the FY fact
     wins when one exists at that `period_end`.
   * **`"quarterly"`:** the shortest bucket wins — the single most recent
     incremental period. This is the setting a caller wanting a quarterly flow
     asks for, and it is what the prior-period side of `yoy_growth_family()`
     has always done (E1's `features.value_for_target_period` matches the
     CURRENT fact's duration to ±20 days). The fix makes the current-period
     side as duration-aware as the prior-period side already was.
   * With **no FY fact** at that `period_end` — every mid-year 10-Q, where the
     collision is a quarter against a year-to-date figure — **both settings
     fall through to the shortest bucket.**
4. It **never moves the period**: if the pre-filtered call returns nothing, or
   a row at a different `period_end`, the unfiltered row stands.
5. **Instant (balance-sheet) facts are untouched** — the function returns
   before a bucket is computed.

**Why "annual" is the default and not "longest available".** At a fiscal year
end the annual figure is the only fact **73%** of the year-end rows have at
all (revenue: 2,533 rows resolve at a `period_end` carrying an FY fact and
nothing else, 951 carry both FY and Q4), so preferring it makes the column mean
the same thing for every filer on the same date instead of depending on which
of the two a filer happened to tag. Away from a fiscal year end there is no FY
fact and the rule falls through to the quarter — **which is what row order
already returned on every one of the 18,300 rows**: the rebuild moved the used
fact on exactly the rows where an FY fact was present (951 / 1,380 / 543 / 105
/ 1,263 by family, equal to the `rows_annual_preferred` counter in every case),
and on no mid-year row. The year-to-date-versus-quarter question is G3
decision 21 / open question Q1 above, and this fix deliberately does not touch
it.

**Where the rule reaches** (manifest `counters.period_identity_by_family`,
counted per built row, not per cached lookup):

| family | rows with >1 duration knowable at the winning `period_end` | rows the annual preference moved | duration of the fact actually used |
|---|---|---|---|
| revenue | 9,446 | **951** | Q 12,858 · FY 3,484 · H1 1 |
| net_income | 10,710 | **1,380** | Q 14,092 · FY 4,043 · H1 1 |
| eps_diluted | 10,412 | **1,263** | Q 13,834 · FY 3,843 · H1 1 |
| operating_income | 6,686 | **543** | Q 9,357 · FY 2,571 |
| operating_cash_flow | 484 | **105** | Q 4,833 · 9M 4,564 · H1 3,767 · FY 3,793 |
| assets · liabilities · equity · cash · shares_outstanding | 0 | 0 | instant only |

The gap between the two numeric columns is the mid-year quarter-versus-YTD
collision, which the rule leaves exactly where it found it.

The preference applies WITHIN one tag; the cross-tag rule (freshest
`period_end`, ties by `filed`) is E1's and is untouched. In principle two alias
tags of one MIGRATION family could tie on `period_end` carrying different
durations, which no rule here would arbitrate. MEASURED over the 27 multi-tag
`(cik, family)` pairs in scope, across every lookup the build makes: that
happens **zero** times, so no cross-tag rule was invented for it.

### 6.3 What changed in the table

18,300 rows × 39 columns before and after; same key, same row order, same
column list. **1,485 rows (8.1%) have at least one changed feature**, over 95
CIKs — 8-K 1,121 / 10-K 325 / 10-Q 39; consumer 472 · healthcare 356 ·
financials 239 · tech 216 · energy 202; concentrated in the weeks after a
fiscal year end (February 397, April 350, March 313 of the 1,485).

| feature | non-null before | non-null after | cells changed | NaN → value |
|---|---|---|---|---|
| `net_margin` | 16,207 | 16,207 | **1,133** | 0 |
| `operating_margin` | 10,322 | 10,322 | **733** | 0 |
| `operating_cashflow_to_revenue` | 15,296 | 15,296 | **992** | 0 |
| `revenue_yoy_growth` | 16,316 | 16,316 | **950** | 0 |
| `net_income_yoy_growth` | 18,136 | 18,136 | **1,380** | 0 |
| `eps_diluted_yoy_growth` | 17,646 | 17,658 | **1,251** | **12** |
| `log_total_assets` | 18,185 | 18,185 | 0 | 0 |
| `leverage_liabilities_to_assets` | 13,072 | 13,072 | 0 | 0 |
| `equity_to_assets` | 18,186 | 18,186 | 0 | 0 |
| `cash_to_assets` | 17,314 | 17,314 | 0 | 0 |
| `momentum_126` | 16,785 | 16,785 | 0 | 0 |
| `realized_vol_63` | 16,785 | 16,785 | 0 | 0 |
| `book_to_market` | 14,229 | 14,229 | 0 | 0 |

**Every changed cell reconciles to a moved fact, with nothing left over.**
`revenue_yoy_growth`: 951 revenue facts moved, 950 growth values changed, the
one remainder is a row whose YoY was NaN before and after.
`net_income_yoy_growth`: 1,380 = 1,380. `eps_diluted_yoy_growth`: 1,251 + 12 =
1,263 = the eps flips exactly. The three ratios change wherever **either** leg
moved and both legs are non-null: `net_margin` 1,469 rows with a moved leg →
1,133 non-null → 1,133 changed; `operating_margin` 1,149 → 733 → 733;
`operating_cashflow_to_revenue` 1,056 → 992 → 992.

Only one coverage figure moves: `eps_diluted_yoy_growth` 0.9643 → **0.9649**
(12 rows whose prior-year ANNUAL EPS was knowable where the prior Q4 was not).
Every other coverage number in §2 stands.

Distribution tails move the way a scale artifact does when it is removed:
`operating_margin` p99 1.0545 → **0.6634** and max 1.9183 → **1.4590**; rows
with an operating margin above 1.0 fall from **107 to 6**. `net_margin` p99
0.6423 → 0.5949; `eps_diluted_yoy_growth` p99 14.6 → 12.14.

### 6.4 What did not change

* `data/f5/numeric_unresolved_e2.csv` — byte-identical (146 pairs, 113 CIKs).
* `data/f5/numeric_staleness_discards_e2.csv` — byte-identical (1,868
  discards); accepted facts still 163,825, median 65 / p99 139 / max 200. The
  guard cannot move: the disambiguation never changes `period_end`, and
  staleness is measured against `period_end`.
* Input shas (A1), the row universe, sessions, both price-censoring channels,
  the UNRESOLVED census, `yoy_cross_tag` (46), the FX block (108 rows).
* Every instant-fact feature and both price factors — 0 cells.

### 6.5 Evidence the value that comes back now is the right one

* **Worked example, real facts.** CIK 804328, 8-K filed 2016-11-02
  (`info_date` 2016-11-02). Its FY-2016 10-K, accession
  `0001234452-16-000552`, filed the same day, tags `Revenues` twice with
  `period_end` 2016-09-25: 23.554 bn over 363 days and 6.184 bn over 90 days;
  `NetIncomeLoss` likewise (5.705 bn / 1.599 bn). Same filed date, same
  accession — every tiebreak ties. Before: the quarter (`period_days_revenue`
  90, `net_margin` 0.2586, `revenue_yoy_growth` +0.1334). After: the year
  (363, 0.2422, −0.0683, the prior-year fact being the FY figure that E1's
  duration-matched prior lookup now selects).
* **A repaired scale artifact.** CIK 1800's FY-2018 10-K row (filed
  2019-02-22) divided a **364-day** operating income by a **91-day** revenue
  and reported `operating_margin` 0.4701. Both legs are now 364 days and the
  margin is 0.1194. This is why the >1.0 operating-margin count collapses from
  107 to 6.
* **Cross-family duration agreement improves** (manifest
  `counters.flow_duration_mismatch_vs_revenue`, rows whose flow period differs
  from the revenue period by more than 20 days): `operating_income` 402 → 20,
  `net_income` 198 → 135, `operating_cash_flow` 8,433 → 7,603. Honest both
  ways: 909 / 385 / 167 rows repaired, 79 / 3 / 104 introduced — the
  introduced ones are rows where the two families' freshest knowable periods
  are genuinely different dates (Q1 revenue against an FY figure whose tag has
  no Q1 fact); they were already mismatched in PERIOD and merely passed a
  counter that compares durations only. See the updated Q1 above.
* **Row order no longer decides**: reversing the fixture frame changes neither
  the annual nor the quarterly answer (test).

### 6.6 Tests, re-runs and refusals

| what | result |
|---|---|
| `python3 -m pytest -q test_numeric_features_e2.py test_backtest_e2.py test_heads_e2.py` | **152 passed** (19.7 s) — `test_numeric_features_e2.py` is now **33 tests**, 24 before + **9 new**: annual-and-quarterly from one colliding `period_end`, row-order independence, the mid-year fall-through, instant untouched, the period is never moved, as-of still governs inside the preferred bucket, YoY follows the annual fact (0.1) while the quarterly preference gives 0.2, the buckets are F2's own, an unknown preference raises |
| `python3 -m pytest -q test_pit.py test_phase_c_leakage.py test_ingest_fundamentals.py test_features_e2.py test_target_e2.py` | **196 passed** (62 s) — the as-of suite and E1's frozen path are green |
| `python3 numeric_features_e2.py` | 18,300 rows, 146 unresolved pairs, **475.3 s** on the final build (476.2 s on the first; was 250.4 s pre-fix — each flow-family lookup that collides now costs a second `pit.value_as_of` on the pre-filtered frame) |
| `python3 backtest_e2.py --census` | 7,405 rows, 40 candidate quarters, mean n_dedup 134.6 — **identical to the pre-fix census**; only the recorded input sha and the timestamp moved |
| `python3 heads_e2.py --census` | head-2 usable events 3,996 / 41 clusters, head-3 panel rows 4,056 — **identical**; only the sha and timestamp moved |
| `python3 backtest_e2.py` | **exit 2**, "BLOCKED: … G3_RATIFIED.json does not exist" |
| `python3 heads_e2.py --all` | **exit 2**, same refusal |

The censuses being unchanged is the expected result and worth stating: the fix
changed feature VALUES, not which rows or folds exist.

**Byte-identical reproduction, asserted again.** The table was built **three
times** on 2026-09-11 — the fix build, an independent second build written to
a scratch path (so the committed artifact was never in flight), and a final
build after two docstring-only edits — and all three produced parquet sha256
`079715054f590515cdc119606aa65126777cfe557d1f9fb5d584e053498059bb`. The
committed manifest is the final build's, so its `module_sha256`
(`cf29212c5956…`) is the sha of the file on disk. The build is deterministic
and the docstring edits are provably output-neutral.

### 6.7 What this makes stale elsewhere (not this session's files)

Every artifact that pinned `23f2ef2ec405…` and was not regenerated here:
`data/f5/census_e2.json` (Step 2, `census_e2.py`),
`data/f5/status/STEP1B_backtest_e2.md` §A1, `data/f5/status/STEP1B_heads_e2.md`
§A2, `data/f5/status/STEP2_census_e2.md`, and HANDOFF §3's F5 entry. Any G3
text quoting the pre-fix `operating_cashflow_to_revenue` mismatch (46.1%) or
the pre-fix `eps_diluted_yoy_growth` coverage (0.9643) needs regenerating from
the new manifest, per the standing rule that report prose is regenerated from
run diagnostics and never hand-carried. Two further consequences a re-run has
to pick up: `census_e2.py` RECORDS the numeric sha rather than asserting it,
so re-running Step 2 refreshes `census_e2.json` without breaking anything; and
the feature-versus-company-identity ICCs that F5_PLAN §3 decision 3 and
`STEP2_census_e2.md` quote for the flow features (`net_margin` 0.31 → 0.65,
`operating_margin` 0.36 → 0.72, `operating_cashflow_to_revenue` 0.34 → 0.51)
were measured on the pre-fix columns and will move a little — they are
feature-vs-identity, not feature-vs-outcome, so re-measuring them is allowed
before G3.

**One test in the app lane now fails, by design of its own tripwire.**
`test_report_filing.py::test_no_outcome_layer_function_is_reachable_from_a_render`
asserts an EXACT set of modules reachable from a render, and
`resolve_family_value` now CALLS `ingest_fundamentals`'s duration classifier,
so `ingest_fundamentals` joins that set (`report_filing.py` already imported
the module for `DURATION_BUCKET_DAYS`; what is new is a call, not a
dependency). The property the test exists to protect — that no `controls` or
`backtest` function is reachable from a render — is untouched. Adding
`"ingest_fundamentals"` to that expected set is a one-word change in a file
this session does not own, and is left to the app lane to rule on rather than
made here. 102 of its 103 tests pass.
