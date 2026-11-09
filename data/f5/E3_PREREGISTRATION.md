# E3 — numeric-families pre-registration (DRAFT, not ratified)

**STATUS: DRAFT 2026-11-06, red-teamed once (`data/f5/status/REVIEW_e3_prereg_2026-11-06.md`;
dispositions in `data/f5/status/E3_CENSUS_2026-11-06.md` §H) — awaiting the owner's rulings
on `E3_OWNER_PACKET.md`, then the Step-3 build, then the owner's word "ratify". No sha is
pinned. `data/f5/E3_RATIFIED.json` does not exist.** Structure follows `G3_PREREGISTRATION.md`
(§0–§14). Every measured population is a re-derivation from `data/f5/census_e3.json`
(generated 2026-11-06T07:35:18Z, sha256 `4bc57d855c7d171abe07fbbbf3e59785167ea191347cba05908a3d973fdaaf39`;
human table `data/f5/status/E3_CENSUS_2026-11-06.md`). **Every rule below is a model's
judgment — the side session's design under the low-touch policy — until the owner rules.**
Rules the owner is asked about carry **⚠ OWNER (packet n)**; rules the side session decided
and logged under the low-touch policy, which the owner may veto by naming them, carry
**⚠ MODEL JUDGMENT (logged; veto by name)**; rules inherited unchanged from the ratified G3
document carry *inherited (G3 §n)* and are not re-asked.

**The question.** Do the well-documented numeric factor families — momentum, value,
profitability, low volatility — implemented point-in-time on the E2 core universe of about
100 large US filers at a time, carry detectable rank information about the 63-session forward
excess return of the company's periodic filings; and, company by company, quarter by quarter,
what would a fixed, sign-only composite of them have said and was it right? The product's
job is to implement known factors honestly and record what they would have said — not to
claim novelty (PRODUCT_PLAN P3 item 2).

**What changed since E2 (the §13 E3 policy's condition (a)).** The question (numeric
known factors, not text), the estimand (the *level* IC of a no-fit, sign-fixed composite
against zero, not a text-minus-numeric *delta*), the unit (one periodic filing per
company-quarter: frame A), and the instrument (no labeler is in the loop, so labeler error,
train-overlap and the seven-financials extraction hole do not apply). Nothing here says
"maybe E2 was underpowered"; E2's text question is closed and stays closed.

**The fixed scope sentence every claim out of this run must carry, verbatim:** *No numeric
factor-family IC of the pre-registered margin or larger is detectable in this universe through
these features, this point-in-time construction and this composite rule.* Never "no effect
exists"; never "value / momentum do not work". (The sentence names the margin, not
"economically relevant size", because §1's ladder is capped at 0.05 and no claim below that
cap is made — red-team M3.)

**No money metric anywhere.** The owner's words on 2026-11-05 were, verbatim, **"B. No"**, in
answer to the EODHD subscription question (HANDOFF §3 "PACKET ITEMS B–F RULED"). *"No new
spend, prices stay the 2026-08-24 snapshot, and the numeric-families program reports no money
metric until the owner reverses this"* is the **main session's reading** of those two words
(HANDOFF §3, same entry), applied here: this run reports rank correlations, hit rates and each
row's realized excess return as its outcome label. It reports no portfolio return, Sharpe,
drawdown, P&L, dollar or percentage-return aggregate, and no "what you would have made".
**The frozen per-fold helper also emits `quintile_spread` (top-minus-bottom quintile mean
realized excess return, `backtest.quintile_spread`); E3 suppresses that column everywhere**
(params `suppressed_outputs`; red-team S3). **⚠ OWNER (packet 4b):** the owner confirms the
reading and the per-row-label exception, or says otherwise.

---

## §0 Provenance & freeze

| convention | measured population | DRAFT rule | enforcement (Step 3 builds these) |
|---|---|---|---|
| Doc sha pinned at ratification | — | `E3_RATIFIED.json.doc_sha256` = sha256 of this file, **and `census_sha256` = sha256 of `census_e3.json` as it stood when the owner read it** (red-team N12), written **only** by `data/f5/pin_e3.py --pin --owner-word ratify --date YYYY-MM-DD` on the owner's literal word. **The `--show` diff is delivered to the owner in chat and acknowledged before the word "ratify" is requested** — never `--show` and `--pin` in one command (F6 §5 S9; red-team S9). Editing after the pin is a new pre-registration. *inherited (G3 §0)* | `test_pin_e3.py` (to write); `test_census_e3.py::test_pin_is_absent_or_matches_the_document` (exists: absent today, or matching — never "must be absent", the G3 M2 lesson) |
| No E3 IC before ratification | **0 E3 ICs exist** (census `freeze_statement`) | `backtest_e3.py` refuses (exit 2) without `E3_RATIFIED.json` matching this file's sha — the `backtest_e2.require_g3` pattern, no override. *inherited (G3 §0)* | `test_backtest_e3.py::test_real_run_refuses_today` |
| One unambiguous parameter source | — | exactly one fenced block ```` ```json e3-params ```` below; every parameter read from it, none hard-coded | `test_backtest_e3.py::test_params_block_is_the_only_source` |
| Inputs sha-asserted | `target_e2.parquet` `ef6befb2…`, `numeric_features_e2.parquet` `01fcaf4b…`, `text_features_e2.parquet` `143dd720…`, `head1_oof_predictions.parquet` `378b0b71…` (= `run_log.jsonl` `oof_predictions_sha256`) | asserted against the committed manifests / run log before a byte is used; a changed frame is a new pre-registration *inherited (G3 §12)* | `backtest_e2.assert_input_shas` (reused) |
| Prior exposure disclosed | §12 | the pre-registration states what has already been observed about these features against this target, **including the G3 result on the 10-K/10-Q rows that are 96% of the primary frame** (red-team M1) | §12 is quoted on the result page |
| Suppressed outputs | — | `quintile_spread` is never written, printed or serialized (header) | `test_backtest_e3.py::test_no_return_aggregate_is_serialized` |
| Post-hoc labelling | — | any amendment after the first E3 IC exists is labelled **POST-HOC** here and in HANDOFF §3 *inherited (G3 §0)* | HANDOFF §3 |

## §1 Estimand & primary metric

| convention | measured population | DRAFT rule | enforcement |
|---|---|---|---|
| **Primary frame** | **A: 3,642 10-K/10-Q rows, 143 CIKs; 3,053 rows inside the 33 folds over 80–99 companies a quarter (n_test = n_dd, mean 92.52). In 2 of 33 folds one company has two periodic filings (2018Q2 CIK 109198; 2025Q4 CIK 320187), so the unit is "periodic filing", which equals "company-quarter" on 3,051 of 3,053 rows** (census §A, §C; red-team N1) | **⚠ OWNER (packet 1):** frame A (periodic filings only). Reason: the company-quarter is the owner's unit, 8-K rows mostly repeat the last periodic fundamentals (88.6–93.3% of 8-K rows identical per fundamental column — reviewer N4), and dedup is the identity here so raw = dedup. Frame B (the E2 run-time frame, 7,381 rows) runs as the **one universe sensitivity arm**; frame C (all forms, 16,383 rows) is censused but **not run** (lazy-elite; red-team N10) | `test_backtest_e3.py::test_primary_frame_is_periodic_only` |
| **Rank pool** | the census ranks each frame within its own rows; G3's form ablation did the same (red-team S6) | **⚠ MODEL JUDGMENT (logged):** `spec.rank_pool = "primary_frame_rows_only"` — frame A's trailing ranks are computed over frame A's rows; frame B's over frame B's. Never "rank on C, then subset" | `test_backtest_e3.py::test_rank_pool_is_the_frame_itself` |
| **Primary metric** | k = 33 folds; honest MDE for one test **0.069–0.163 across the measured anchors (size-rank anchor adjusted to A's per-fold size: 0.081)**; independence lower bound on A 0.051 (census §D; red-team S11) | **⚠ MODEL JUDGMENT (logged):** mean over the 33 fold quarters of the per-fold Spearman rank correlation between the **composite score** (§4) and `target_excess_63` on that quarter's scored dedup test rows. **One two-sided test at α = 0.05 against 0; the positive branch requires the two-sided 95% CI to exclude 0 on the pre-registered (positive) side** (red-team M2). SE by moving block bootstrap (G3 method: block length `ceil_k13_ac1`, 4,000 resamples, seed 0), Newey–West beside it. The **90% CI is used only for TOST** at the ladder margin. Normal reference, as G3 | `test_backtest_e3.py::test_primary_is_mean_of_fold_ics`, `test_positive_branch_uses_the_95_ci` |
| **Composite score (the "model")** | rows with ≥ 3 of 4 confirmatory families present: **3,040 of 3,053 (99.6%)** in A's folds; all four: 2,438 (79.9%) (census §C) | **⚠ MODEL JUDGMENT (logged):** no fit, no weights, no training set. For each confirmatory family, the family score is the mean over its *available* members of the signed PIT trailing percentile (sign +1: the rank; sign −1: one minus the rank). The composite is the mean of the available family scores, requiring **≥ 3 of 4** families; a row with fewer is **unscored** (counted and printed per fold, never imputed). "All 4 required" runs as a sensitivity arm | `test_backtest_e3.py::test_composite_has_no_fit_and_fixed_signs` |
| Specification | PIT trailing ranks lose ≤ 1 row per column to the comparator floor (census §B). **Comparators in the trailing window are a median 34 days old (p90 84 days) on A** — reviewer N2, measured 2026-11-06 — so the "cross-sectional" rank of a price factor mixes in up to six months of market drift; not look-ahead, but not the contemporaneous sort the textbook signs were established on | **primary = `spec.pit_trailing_rank_frame`** (180 d, ≥ 2 comparators, same-day in), *inherited (G3 §1)*. The `include_same_day = False` arm runs beside it *inherited (G3 §1)*. There is no raw-levels secondary: a composite of raw levels on different scales is not defined | `test_spec.py` (frozen) |
| **Margin ladder** | SE caps Δ/2.487: **0.0121 / 0.0161 / 0.0201**; the independence lower bound on A (SE 0.0182 at ρ=0) reaches 0.05; **every measured anchor (SE 0.0246–0.0583) reaches no rung** (census §D) | **G3's ratified ladder, inherited unchanged: {0.03, 0.04, 0.05}, Δ = the smallest rung with measured SE ≤ Δ/2.487, chosen by the run before any IC is serialized or printed; never above 0.05; none → UNPOWERED** (red-team M3: an earlier draft widened the ladder to 0.10, which would have turned the modal outcome into a "bounded null" the document itself called empty; withdrawn). Any Δ > 0.03 prints beside the honest MDE 2.8 × SE (KC3). **The honest expectation, stated before the run: UNPOWERED.** *inherited (G3 §1, decision 15)* | `test_backtest_e3.py::test_margin_is_selected_before_any_ic_is_serialized` |
| Zero-information comparators | size rank +0.0191, ticker mean +0.0362 mean dedup IC on frame B's folds (census §E; frame-B numbers, reviewer N8) | the two standing zero-information predictors (`spec.zero_information_benchmarks`) are recomputed on frame A and printed beside the composite, with the H1 floor. **The decision rule does not ask the composite to beat them**; the §13 positive branch asks it to clear the H1 floor *inherited (G3 §1)* | `spec.py` (frozen) |
| Rows scored, dedup vs raw | A: raw = dedup (3,053); B: 6,184 → 4,481 (census §C) | dedup primary, raw beside it, on both frames *inherited (G3 §6)* | `backtest_e2.dedup_keep_mask_cik` (reused) |

## §2 Event dating (C1) — *inherited (G3 §2)*

Window opens the session after `info_date = max(filing_date, acceptance_datetime ET date)`;
post-close acceptance pushes the news session forward one; price factors end at
`pre_session`. The reviewer re-checked on all 3,763 in-membership periodic rows that
`pre_session < news_session < window_open_session` and `window_open > info_date` (100%).

## §3 Fundamentals PIT — *inherited (G3 §3)*

`pit.value_as_of` as-of `info_date`, duration-aware period identity, 200-day staleness
guard, decision-21 duration match on `operating_cashflow_to_revenue` only (`net_margin` 135
rows and `operating_margin` 20 rows stay on the ported definition — a main-session scope
boundary, G3 §11, carried here). The fundamentals history is thin before 2019 for the flow
items: `net_margin` coverage 0.579 (2016), 0.575 (2017), 0.707 (2018), 0.969 (2019) (numeric
manifest `coverage_by_year`; balance-sheet items are 99–100% throughout — reviewer N6), which
is why profitability covers 45% of 2018Q1's test rows and ≥ 97% from 2019Q1 (census §C).
Disclosed, not repaired.

## §4 Families

| family | tier | members (sign) | coverage in A, any / all | DRAFT rule |
|---|---|---|---|---|
| momentum | confirmatory | `momentum_126` (+) | 1.000 | **⚠ MODEL JUDGMENT (logged); ⚠ OWNER (packet 3) on the 12-1 build.** 126-session price momentum ending at `pre_session`, **with no skip month, so it contains the one-month reversal** (reviewer N3). P3 names 12-1; the artifact does not carry it (§5) |
| value | confirmatory | `book_to_market` (+) | 0.839 (financials 0.692) | ⚠ MODEL JUDGMENT (logged). Book equity / (shares × pre-session close); **negative book equity gives a negative ratio with no special handling and ranks at the bottom** (`numeric_features_e2.py` `rec["book_to_market"] = equity / (shares * pre_close)`). Earnings yield not in the artifact (§5) |
| profitability | confirmatory | `net_margin` (+), `operating_margin` (+), `operating_cashflow_to_revenue` (+) | 0.888 / 0.309 | ⚠ MODEL JUDGMENT (logged). **Revenue-scaled margins, not Fama–French operating profitability over book equity** (reviewer N3). On frame A, financials: `net_margin` 0.932, `operating_margin` **0.261**, so a financials profitability score is mostly `net_margin` (census §B; reviewer N5) |
| low_volatility | confirmatory | `realized_vol_63` (−) | 1.000 | ⚠ MODEL JUDGMENT (logged). Sign negative = the low-volatility anomaly |
| growth | **not tested in E3** | `revenue_yoy_growth`, `net_income_yoy_growth`, `eps_diluted_yoy_growth` | 1.000 / 0.852 | ⚠ MODEL JUDGMENT (logged): no pre-registered sign exists, so no IC is computed (an earlier draft ran them as "exploratory"; dropped as forking-path material — red-team N10). Coverage is censused for a later E |
| balance_sheet | **not tested in E3** | `leverage_liabilities_to_assets`, `equity_to_assets`, `cash_to_assets` | 1.000 / 0.669 | same |
| size | comparator | `log_total_assets` | 0.993 | the zero-information yardstick (`spec.zero_information_benchmarks` size rank), not a family under test *inherited (G3 §1)* |

Signs are the textbook directions (Jegadeesh–Titman momentum; Fama–French value and
profitability as to *direction*, not construct; Ang et al. low volatility) fixed before any
E3 number exists. They are not fitted and cannot flip after the run; a family whose IC comes
back with the wrong sign is reported as such (§13) and is not "re-signed". The reviewer
checked that no G3 output carries feature importances or per-feature ICs from which a sign
could have been read.

## §5 What is not on the artifact, and what Step 3 may build

| construct | status | DRAFT rule |
|---|---|---|
| 12-1 momentum | not built; `momentum_126` is what exists | **⚠ OWNER (packet 3): use `momentum_126` as built (recommended).** Building a 12-1 column is price-only and PIT by construction, but it adds a feature chosen after seeing H1 T2b's 12-1 result on the event panel (§12); if the owner chooses to build it, it joins momentum as a second member with sign + and is so labelled |
| earnings yield | not built | candidate for a later E; not in this run |
| accruals | not built; operating cash flow 42–45% covered | not in this run |
| PEAD / SUE | `controls.py` computes it for H1 at earnings 8-Ks; not in the feature table; H1 T2a already observed (+0.028, AMBIGUOUS) | not in this run; if ever ported it is exploratory, because its E2 association is already on disk |

## §6 Fold structure

| convention | measured population | DRAFT rule | enforcement |
|---|---|---|---|
| Fold list | the ratified 33 (2018Q1–2026Q1) on A: n_dd 80–100, mean 92.52, 139 distinct CIKs (census §C) | **⚠ MODEL JUDGMENT (logged): the same 33 quarters E2 used**, read from the G3 block. The composite has no training set, so no burn-in is needed beyond the 180-day rank window and the list *could* start at 2017Q1 (k = 37); not done, because the 2016–2017 flow-item coverage is 58% and because the E2 scorecard is on these 33 quarters. A 37-fold arm is not run (it would be a different pre-registration) | `backtest_e2.build_folds` (reused) |
| Training sets and purge | A: 418 → 3,354 rows, purge 16.2% → 2.9% (census §C) | **no E3 arm fits anything, so no E3 arm has a training set**; `build_folds` still computes the purge and the figures are recorded for comparability with G3 only (red-team N9) | `backtest_e2.build_folds` |
| Dedup | gap 5 on CIK; identity on A *inherited (G3 §6)* | dedup primary, raw beside it | `backtest_e2.dedup_keep_mask_cik` |
| GLD | 14 GLD rows removed from C before anything (census §A) | excluded in every arm *inherited (G3 decision 2)* | `backtest_e2.exclude_gld_rows` |

## §7 Censoring and sensitivity arms (reported beside the primary, never in its place)

| arm | measured population | DRAFT rule |
|---|---|---|
| **Price-censoring channel A, per fold** | **27 of 176 core CIKs have no price column at all and never enter any E3 frame** (`target_e2.parquet` carries 149 CIKs); channel-A members per fold **16 (2018Q1) → 0 (from 2025Q3)**, carried from census_e2's per-quarter count, same membership, same quarters (census §4b; red-team S1) | printed per fold on every result page, never silently dropped *inherited (G3 §7)* |
| **Post-2019 censoring arm** | 2019Q1 … 2026Q1 = 29 of the 33 folds; channel A 10 → 0 | the same composite scores restricted to test folds from `post_2019_first_quarter = "2019Q1"`; no recomputation of scores *inherited (G3 §7)*. **The 2018 folds are both the most censored and the thinnest in profitability coverage (0.45–0.93), so this arm is the one that separates a 2018-driven result from a survivorship artifact** |
| `include_same_day = False` | — | *inherited (G3 §1)* |
| Frame B (the E2 run-time frame) | 4,481 dedup rows in folds | the one universe arm; also where the two zero-information predictors have already been reported |
| "All 4 families required" | 2,438 of 3,053 rows on A | §1 |
| Per-family ICs | 4 | §9 |
| One-fold-out influence table | 33 rows | each fold removed in turn, the mean recomputed — the F6 N3 fragility check; descriptive |

Dropped from an earlier draft as machinery the run does not need (red-team N10): the frame-C
arm, a per-sector per-fold IC table (17–20 rows per sector-fold), exploratory-family ICs.
Per-sector **coverage** stays a disclosure (§11). No arm can change the §13 branch.

## §8 Multiplicity

| level | count | DRAFT rule |
|---|---|---|
| primary | 1 | the composite's two-sided test at α = 0.05; no correction |
| secondaries | 4 | **⚠ MODEL JUDGMENT (logged):** the four confirmatory families, Holm at α = 0.05 across the four; a family "positive" also requires the pre-registered sign. The census's Holm worst-case MDE is 3.34 × SE = **0.090–0.195** on the measured anchors |
| prior confirmatory tests on this data | disclosure only | **⚠ MODEL JUDGMENT (logged):** no project-wide adjusted p is computed (an earlier draft's "Holm-11 column" was not computable — G3 head 3 has no pre-registered p, head 1's primary is an equivalence test; red-team S5). Instead every result page lists the confirmatory tests already run on E2 data — H1 T1 / T2a / T2b (2026-08-25), G3 head 1 / head 2 / head 3 (2026-11-05) — beside E3's 1 + 4, so a reader can count. **This departs from PRODUCT_PLAN P2's seeded family (E1's 22 features, H1 T2a/T2b, E2's confirmatory block, the three baseline factors) and says so; P2's own pre-registration, if it is ever written, defines that family** |

## §9 Secondaries and the fitted comparator

- **Per-family ICs** (four, Holm; §8). Each family score alone, same folds, same rows.
- **Fitted numeric block, read from disk, zero new fits:** G3's `numeric_only` out-of-fold
  predictions exist for every row of the E2 frame (`data/f5/head1_oof_predictions.parquet`,
  git-excluded, sha `378b0b71…` in `run_log.jsonl`). **3,497 of frame A's 3,642 rows also lie
  in frame B** (census `section_1_reproduction_checks.n_frame_A_rows_also_in_frame_B`; the
  in-fold dedup subset is counted by Step 3 — the reviewer measured 2,914). **⚠ MODEL
  JUDGMENT (logged; red-team N13):** on those same rows of the primary frame, G3's
  `numeric_only` prediction is *read* and printed beside the composite as a comparator — no
  XGBoost fit runs in E3, and no separate frame-B scorecard is produced. The comparator is
  descriptive and never enters the §13 branch.

## §10 Cross-arm hierarchy

The secondaries, the fitted comparator and the arms cannot rescue the primary (the G3 §13
cross-head clause, inherited): a positive family under a null or unpowered composite licenses
write-up and disclosure, nothing more; and a positive composite with no positive family is
reported exactly so.

## §11 Instrument disclosures (each travels with every result)

| disclosure | measured value | source |
|---|---|---|
| **Power** | honest MDE one test 0.069–0.163 across the measured anchors (size-rank anchor n-adjusted to A: 0.081); Holm-4 0.090–0.195; independence lower bound on A 0.051; **expected branch UNPOWERED** | census §D |
| **Prior exposure** | §12 table | census §E |
| **Survivorship, with its direction by family** | 27 of 176 core CIKs never priced (energy 10, consumer 5, healthcare 5, tech 5, financials 2); 3,016 core filings excluded for missing subject prices; 324 rows with a complete window but no subject price; channel A 16 → 0 CIKs across the folds. **Direction differs by family:** dropping dead high-volatility / low-momentum losers biases the low-volatility and momentum ICs *down*; dropping dead distressed high-book-to-market names biases the value IC *up*; profitability ambiguous. The cause is not separately measured, so none of this is called delisting *(G3 §11)* | census §4b; `target_e2_manifest.json` |
| **Fundamentals thinness before 2019** | profitability covers 45% of 2018Q1 rows, 54% 2018Q2, 79% 2018Q3, 93% 2018Q4, ≥ 97% after | census §C; numeric manifest `coverage_by_year` |
| **Value hole for financials** | `book_to_market` 0.692 covered in financials vs 0.84–0.90 elsewhere (A) | census §B |
| **Profitability is sector-heterogeneous and is not FF profitability** | `operating_margin` 26.1% covered for financials on A (20.4% on the whole table); ocf/revenue 42–45% after the decision-21 match; margins are revenue-scaled | census §B; numeric manifest |
| **Comparator age inside the trailing ranks** | median 34 d, p90 84 d (reviewer N2) | `REVIEW_e3_prereg_2026-11-06.md` |
| **Unconverted CAD reporter** | 24 `fx_blocked` rows in A | census §A; G3 §11 |
| **Price snapshot** | Yahoo, 2026-08-24, `744e1cc5…`, split-adjusted only, not dividend-adjusted; 31 of 244 members absent from the price matrix | `target_e2_manifest.json`; G3 §11 *inherited* |
| **Fold non-independence** | every MDE is a lower bound (nested windows, common regimes); ρ assumed 0.3, measured −0.042 for the E2 delta (a different statistic) | census §D caveats |
| **The H1 floor is borrowed** | 0.0466–0.0488 is H1's event-panel placebo MDE (41 / 40 periods); the analogous pure-noise MDE on A's own per-fold size is 0.051 (reviewer N7); the §13 rule uses the **minimum over the two T0 arms** | census §D; `controls_results.json` |
| **Sector labels are as of the build, not PIT** | SIC drift ≈ 1.6% (G3 §12) | matters only for per-sector coverage |
| **Two unruled ratios** | `net_margin` 135 rows / `operating_margin` 20 rows on the ported definition | G3 §11 *inherited* |
| **The scorecard is descriptive** | the E3 inference sentence (§14), printed verbatim from `scorecard_e3`'s constant, never retyped | §14 |
| **No money metric; `quintile_spread` suppressed** | header | params `suppressed_outputs` |
| **E1/E2 incomparability** | *inherited (G3 §11)* | — |

## §12 Prior exposure (what is already known, read from committed files)

| what | value | source |
|---|---|---|
| **G3 form-controlled ablation — the fitted blocks on the 10-K/10-Q rows of the E2 frame (3,497 rows = 96% of frame A, ranked within that periodic pool, as E3 ranks A)**: `numeric_only` dedup | mean IC **+0.0250, 20/33 positive** (raw +0.0250); `text_and_numeric` +0.0311; fitted `size_only` −0.0001 | `results_head1.json .form_controlled_ablation.per_fold_ic` (red-team M1) |
| G3 `numeric_only` block on the whole E2 frame (XGBoost on all 13 features, PIT ranks), dedup, 33 folds | +0.0251, 19/33 positive (raw +0.0162) | `results_head1.json .per_fold_ic__pit_trailing_rank`; F6 §1.7 |
| G3 `numeric_only`, raw-levels spec, dedup | +0.0207 | `.per_fold_ic__raw_levels` |
| G3 `numeric_only`, `include_same_day = False` arm, dedup (an arm E3 also runs) | +0.0220 | `.per_fold_ic__pit_trailing_rank_no_same_day` |
| G3 `size_only` fitted block, dedup | −0.0289 | same |
| zero-information size rank / ticker mean, dedup (frame B) | +0.0191 / +0.0362 | `.standing.zero_information_summary` |
| G3 scorecard, universe block (frame B): `numeric_only` / `size_only` / `text_and_numeric` hit rate | 0.510 [0.492, 0.528] / 0.486 [0.468, 0.504] / 0.519 [0.501, 0.537] | `.scorecard_summary.blocks` |
| every G3 per-fold row also carries `quintile_spread` for every block | exists on disk; suppressed in E3 | `results_head1.json` |
| H1 T2b 12-1 momentum at earnings 8-Ks | +0.0287, CI95 [−0.048, +0.103], MDE 0.110, AMBIGUOUS | `controls_results.json` |
| H1 T2a PEAD (SUE) at earnings 8-Ks | +0.0279, CI95 [−0.020, +0.076], MDE 0.071, AMBIGUOUS | same |
| F6 §4 | *"Nothing here is evidence for them."* | `F6_E2_RESULT.md` |

These are prior knowledge when the owner rules. E3's primary is a different estimand (a
no-fit, sign-fixed composite's level IC) and has not been computed; the pre-registration is
nonetheless written **after** a pooled fit of these same features was scored on 96% of the
primary frame's rows, and says so. **⚠ OWNER (packet 4a):** accepted as a disclosed
limitation rather than a reason not to run. The reviewer's contamination verdict: the primary
is a different estimand; the signs, `min_families = 3` and the fold list show no sign of
outcome influence; the frame choice shows none (form-ablation +0.0250 against B's +0.0251);
two choices were plausibly shaped by outcome-derived quantities — the ladder widening (since
withdrawn, M3) and keeping `momentum_126` over 12-1 (packet 3).

## §13 The stopping rule, outcome map and E4 policy

**The E2 paragraph this document quotes and supersedes *only as regards licensing this E3*
(the text-arm closure it pronounces is untouched):**

> *"**E3 policy:** No E3 without a NEW owner ratification that (a) names what changed — "maybe underpowered" is inadmissible, E2 *was* the powered answer to that; (b) states its own MDE, cost, and stopping rule; (c) quotes and explicitly supersedes this paragraph."* (G3 §13, ratified 2026-11-05)

(a) is the header's "What changed since E2". (b): **MDE** — census §D, one test 0.069–0.163
on the measured anchors, Holm-4 0.090–0.195, independence bound 0.051 on A; **cost** — $0 API
spend, no new service, no labeler run, minutes of CPU (no fit), one builder session for Step
3 (`backtest_e3.py` + `pin_e3.py` + `scorecard_e3.py` wrapper + tests, reusing `backtest_e2`
helpers) and one reviewer pass; **stopping rule** — below. (c): this paragraph.

**⚠ MODEL JUDGMENT (logged) — outcome map, Option-1 shape (G3 §13), evaluated in this order
(red-team S7):**

| order | branch | rule | what follows |
|---|---|---|---|
| 1 | **Bounded null** | a rung Δ ∈ {0.03, 0.04, 0.05} is selected (SE ≤ Δ/2.487) **and** the 90% CI lies inside ±Δ — whether or not it excludes 0 | the numeric families are **not used as a signal**; written up and closed with the CI; the numbers stay in the reading aid as information; the scorecard is still produced |
| 2 | **Above-MDE positive** | not 1; the two-sided 95% CI excludes 0 on the positive side **and** the point estimate ≥ the H1 floor (min over the two T0 arms, 0.0466) | run only the §7 arms; write up with the §12 table; **STOP**. The composite's calls go to the §14 scorecard (every branch). Nothing is acted on; no portfolio simulator and no money metric until the owner reverses the reading of "B. No" and a new pre-registration exists |
| 3 | **Wrong-sign significant** | not 1; the 95% CI lies wholly below 0 | reported as **"significant in the direction opposite to the pre-registered sign"** — never as "not resolvable", never as a positive; the sign is not flipped; no action |
| 4 | **UNPOWERED / ambiguous** | everything else: no rung satisfies SE ≤ Δ/2.487; or the CI straddles 0 and is not inside ±Δ; or the 95% CI excludes 0 on the positive side but the point estimate is below the floor | reported as **"not resolvable at this design's power"** with the CI, the floor and the MDE beside it; never as a null and never as a positive; no action. **This is the branch the census expects** |

**E4 policy:** identical to the E3 policy quoted above — no E4 without a new owner
ratification that names what changed, states its own MDE, cost and stopping rule, and quotes
and supersedes this paragraph. Secondaries and arms never license an E4.

**Signature:** *(blank until the owner rules in chat; the owner's words are quoted here
verbatim before any reading of them.)*

## §14 Scorecard — per-company, per-quarter historical calls (G3 §14 rules, E3 wrapper)

**⚠ MODEL JUDGMENT (logged; red-team S4):** `scorecard_e2.py` is a G3-run module (its sha is
in F6's file index) and its block labels, scope sentence and inference sentence are E2's, so
it is **not** edited and does not "run unchanged". Step 3 writes **`scorecard_e3.py`, a thin
wrapper** that imports `scorecard_e2`'s call, tie, correct-flag, chance-line and Wilson
functions and supplies its own block labels (`composite_4_family`, `size_only_rank`,
`g3_numeric_only_oof`), its own scope sentence (the header's, verbatim) and its own inference
sentence: *"Hit rates are descriptive. The inference is the pre-registered IC test and margin
ladder of E3_PREREGISTRATION §1; a per-company hit rate over at most 33 quarters has a wide
interval and proves nothing on its own."* The rules are G3 §14's: "the model" = the
composite score on frame A's 3,053 dedup test rows; terciles within the test quarter by
average rank; the straddle-tie rule; **correct** = sign match with a non-zero excess; per
company a hit rate with a Wilson 95% interval only at ≥ 6 calls (the nine withheld keys below
that); the call-count-matched chance line computed, never a constant; `n_no_call`,
`n_tied_no_call`, `n_unresolved` each with their denominator. Comparators on the same rows:
`size_only_rank` (zero-information) on every row; G3's `numeric_only` out-of-fold prediction,
read from disk, on the 3,497 A∩B rows (§9). Written inside the guarded run, after the margin
block (`build_scorecard` takes the margin block as a required argument).
`data/f5/e3_scorecard.md` / `.json` / `e3_oof_scores.parquet` are **git-ignored — enforced
now by `.gitignore` lines 165–167** (red-team S10; legal baseline #4); only the universe block
is committed. A call is a within-quarter relative statement drawn after the quarter, not a
real-time call (G3 §14, N1). **The scorecard cannot change the §13 outcome**, and the §13
branch is never restated as a hit rate.

---

*Parameter block — exactly one, to be parsed by `backtest_e3.py` (Step 3). DRAFT: values
change only through the owner's rulings; after the pin, never.*

```json e3-params
{
  "params_version": "e3-params-1",
  "draft_status": "DRAFT 2026-11-06 -- red-teamed once; not ratified; no sha pinned",
  "frame": {
    "primary": "A_periodic_10K_10Q",
    "primary_forms": ["10-K", "10-Q"],
    "sensitivity": ["B_e2_run_time_frame"]
  },
  "fold_quarters": ["2018Q1", "2018Q2", "2018Q3", "2018Q4", "2019Q1", "2019Q2", "2019Q3", "2019Q4", "2020Q1", "2020Q2", "2020Q3", "2020Q4", "2021Q1", "2021Q2", "2021Q3", "2021Q4", "2022Q1", "2022Q2", "2022Q3", "2022Q4", "2023Q1", "2023Q2", "2023Q3", "2023Q4", "2024Q1", "2024Q2", "2024Q3", "2024Q4", "2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1"],
  "post_2019_first_quarter": "2019Q1",
  "purge_rule": "target_window_close_on_or_after_test_quarter_start",
  "spec": {
    "window_days": 180,
    "min_comparators": 2,
    "include_same_day": true,
    "same_day_sensitivity_arm": true,
    "rank_pool": "primary_frame_rows_only",
    "ticker_col": "cik",
    "date_col": "filing_date"
  },
  "families": {
    "momentum":       {"members": {"momentum_126": 1}},
    "value":          {"members": {"book_to_market": 1}},
    "profitability":  {"members": {"net_margin": 1, "operating_margin": 1, "operating_cashflow_to_revenue": 1}},
    "low_volatility": {"members": {"realized_vol_63": -1}}
  },
  "not_tested": {"growth": ["revenue_yoy_growth", "net_income_yoy_growth", "eps_diluted_yoy_growth"],
                 "balance_sheet": ["leverage_liabilities_to_assets", "equity_to_assets", "cash_to_assets"]},
  "composite": {
    "family_score": "mean_of_available_signed_member_ranks",
    "rule": "mean_of_available_family_scores",
    "min_families": 3,
    "all_four_required_arm": true,
    "fit": "none"
  },
  "primary": {
    "metric": "mean_per_fold_spearman_ic_dedup",
    "direction": "positive",
    "two_sided_alpha": 0.05,
    "positive_ci_level": 0.95,
    "positive_requires_point_estimate_at_or_above": "min_h1_noise_floor_over_t0_arms"
  },
  "dedup": {"gap_days": 5},
  "gld": {"exclude_from_analysis": true},
  "margin": {"ladder": [0.03, 0.04, 0.05], "power_divisor": 2.487, "mde_multiplier": 2.8, "kc3_flag_above": 0.03},
  "se": {"method": "moving_block_bootstrap", "block_length_rule": "ceil_k13_ac1", "n_resamples": 4000, "seed": 0, "alternative": "newey_west"},
  "tost": {"alpha": 0.05, "ci_level": 0.9, "reference_distribution": "normal"},
  "outcome_map_order": ["bounded_null", "positive", "wrong_sign_significant", "unpowered_or_ambiguous"],
  "noise_floor": {"source": "data/hardening/controls_results.json", "arms": ["T0_placebo_announcement_core", "T0_placebo_forward_core"], "rule": "min_over_arms"},
  "secondaries": {"per_family_holm_alpha": 0.05, "n_tests": 4},
  "prior_tests_disclosed": ["H1_T1", "H1_T2a", "H1_T2b", "G3_head1_primary", "G3_head2", "G3_head3"],
  "sensitivity_arms": ["channel_A_per_fold", "post_2019", "no_same_day", "frame_B", "all_four_required", "per_family", "one_fold_out"],
  "fitted_comparator": {"source": "data/f5/head1_oof_predictions.parquet", "block": "numeric_only", "rows": "primary_frame_rows_also_in_frame_B", "refit": false},
  "scorecard": {
    "module": "scorecard_e3 (wrapper over scorecard_e2 call/tie/correct/chance/wilson functions; own labels and sentences)",
    "arm": "pit_trailing_rank",
    "eval_set": "dedup",
    "model_block": "composite_4_family",
    "comparators": ["size_only_rank", "g3_numeric_only_oof"],
    "call_rule": "tercile_within_test_quarter",
    "tie_rule": "average_rank_straddle_no_call",
    "outcome_col": "target_excess_63",
    "correct_rule": "sign_match_nonzero",
    "min_calls_for_company_hit_rate": 6,
    "ci": "wilson_95"
  },
  "suppressed_outputs": ["quintile_spread"],
  "money_metrics": "none -- main-session reading of the owner's 'B. No' (2026-11-05); per-row realized excess return is an outcome label",
  "pin": {"file": "data/f5/E3_RATIFIED.json", "also_pins": ["census_sha256"], "show_before_ask": true},
  "cost": {"api_spend_usd": 0, "new_services": 0, "labeler_runs": 0, "compute": "minutes, no model fit"}
}
```
