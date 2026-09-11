# STEP 2 — the pre-run census (`data/f5/census_e2.json`)

Written 2026-09-11 by the `research-statistician` session executing **F5_PLAN
§2 Step 2**. This file is the human table; `data/f5/census_e2.json` is the
machine-readable original and every number below is keyed to a path inside it.
Generator: `data/f5/census_e2.py` (the only new code; 1.0 s wall, `$0`, zero
network calls).

**Freeze status (F5_PLAN §1): clean.** No information coefficient, correlation,
model fit or feature-versus-outcome association was computed on E2 data.
`target_excess_63` was read only to **count** completeness and censoring
(`.isna()` / `.notna()`), never correlated, ranked or regressed against a
feature. The §G ICCs are **feature-versus-company-identity** statistics, which
the brief and the freeze both allow. `data/f5/G3_PREREGISTRATION.md` and
`data/f5/G3_RATIFIED.json` **do not exist and were not created**.

**Reuse, not recomputation.** The per-quarter row/dedup/CIK/purge counts come
from `data/f5/census_head1.json` (Step 1b, 40 candidate quarters); heads 2 and 3
from `data/f5/census_heads.json`; the text families from
`data/f5/text_families_e2_manifest.json`; the mask/enum/overlap counts from
`data/f5/status/STEP1A_features_e2.md`; the censoring cohort profile from
`data/F2_INGESTION_REPORT.md` §0(c) and `data/f5/status/STEP1A_target_e2.md` §3;
the MDE algebra and its constants from `data/hardening/status/H2_spec.md` §4 and
`EXPANSION_PLAN.md` §2a's 2026-08-25 amendment; the zero-information noise floor
from `data/hardening/controls_results.json`.

**Genuinely new here:** the per-fold populations for the three fold options
(decision 4); the **two-channel per-fold price-censoring count** (the part
F5_PLAN §2 names as unmeasured); the **MDE re-derivation at k = 33 on the
measured n_dd**; the **ladder feasibility** for decision 15; the ten named CIKs
whose periodic filings were never extracted; the **E2 ICCs against company
identity**; and the WITHDRAWN per-year distribution with its frame footprint.

---

## A. Master table — one row per G3 decision, in F5_PLAN §3 order

| # | decision | measured population (this census) | where in `census_e2.json` |
|---|---|---|---|
| 1 | Benchmark (whole-universe, exclude-self) | benchmark members used on complete in-membership rows: median **128**, min 113, max 135; **31** universe member CIKs never appear in the price matrix (invisible to `n_benchmark_unpriced`); 10,926 member-cells counted unpriced | quoted from `STEP1A_target_e2.md` §3 |
| 2 | GLD analysis-side treatment | **8 modeling rows**, 1 CIK, 6× 10-Q + 2× 10-K, one per quarter in 2017Q3–2018Q2 and 2023Q3–2024Q2; **6 of the 8 fall inside the 33 default folds**; 65 scoped / 14 in-membership target rows | `.section_5….gld` |
| 3 | Primary metric, spec, confirmatory block | frame **7,405** modeling rows / 144 CIKs; dedup **5,383** (72.7%) at gap 5; 10-K/10-Q rows 3,508 (47.4%); **ICCs vs company identity in §G — the PIT-rank spec does NOT reduce them** (log_total_assets 0.945 raw → 0.942 ranked; six of thirteen features rise) | `.section_6…` |
| 4 | Fold structure | three options with exact quarter lists in **§B**; default **k = 33** (2018Q1–2026Q1), n_dd 119–161 mean **136.3**; alt **k = 26** (2019Q4–2026Q1), n_dd mean 138.2; post-2019 arm **k = 29** under the plan's own arithmetic (see the flag in §B) | `.section_1_fold_options_decision_4` |
| 5 | Label purge | over the 33 default folds **6,194** (row, fold) training instances purged; per-fold share mean **6.17%**, max 16.57% (2018Q1), min 2.89% (2026Q1); monotone decreasing. E1 comparator: 313/2,425 = 12.9% | `.section_1…per_fold[*].share_train_purged` |
| 6 | C1 / `include_same_day` | 17,623 of 29,271 scoped rows (60.2%) treated post-close under the ported rule; **1,751** rows whose ET acceptance date precedes `filing_date`, of which **1,717** open one-to-two sessions late (conservative) | quoted from `STEP1A_target_e2.md` §3 |
| 7 | FX PIT | population unchanged: **1 CAD float fact** (Enbridge, CIK 895728, core/energy) + **13** fundamentals series; `fx_currency` is a materialized column on `numeric_features_e2` | `F2_INGESTION_REPORT` §0(d) |
| 8 | Yahoo price source | snapshot `744e1cc5…`, **3,179 sessions 2014-01-02 → 2026-08-24, 213 priced CIKs**; **27 of 176 core CIKs have no column at all** (energy 10, consumer 5, healthcare 5, tech 5, financials 2) | `.section_1b…summary` |
| 9 | 8K_BODY register | **790** chunks in the corpus, excluded from the 316,291-row feature frame; **85** 8K_BODY sections were nonetheless embedded by family B (decision 23d) | `.section_5….masks_and_enums_quoted_from_STEP1A`, `.section_8….decision_23d…` |
| 10 | Section masks | sentiment masked on RISK_FACTORS **4,177** (NEUTRAL 3,452 / NEGATIVE 688 / POSITIVE 37); guidance masked **2,826** = 2,803 MDA + 23 RISK_FACTORS, of which **230 active**; imputed NONE **48,790** corpus (51.18% of applicable) / 48,293 frame; 17 guidance-enum nulls left null; schema violations **23 = 17 + 4 + 2** | `.section_5….masks_and_enums…` |
| 11 | WITHDRAWN guidance | **71** in the corpus → **66** on the feature frame (−1 8K_BODY, −4 MDA-masked), reproducing the plan's n = 66 exactly. **52 of 66 are 2020, 41 of those a single quarter (2020Q2).** They touch only **35 of 7,405 modeling rows (0.47%)**, 25 of which sit in one fold | `.section_5….withdrawn` |
| 12 | Head 2 predictor + DV | core earnings 8-Ks 4,374 → **3,996 usable** over 41 clusters incl. the partial 2026Q3; ending at the last COMPLETE quarter gives **40 clusters / 3,904 events**; 2026Q3 contributes 92 against an 83–107 complete-quarter range (mean 97.6); 320 events dropped for no price column, 17 for incomplete prices, 3 past the snapshot, 38 without text features | `.section_7….head2` |
| 13 | Head 3 sample/horizon/metric | 668 exit rows / 144 CIKs total; **480 rows on the core panel, of which 351 (73.1%) are followed by the same company still filing in-membership a year later** — only **129** rows plausibly end membership. Both 8-K item-1.03 rows are non-exits by this test. Panel: `latest_in_quarter` 4,056 rows with **70.0% carrying no text**; `latest_in_quarter_with_text` 4,042 rows with 0% missing. Candidate label cut 2026-08-17 censors 5 of 41 quarters | `.section_7….head3` |
| 14 | LOCO budget | 6 folds at indices 0, 6, 13, 19, 26, 32 = 2018Q1, 2019Q3, 2021Q2, 2022Q4, 2024Q3, 2026Q1; training members 96, 101, 115, 127, 136, 144 → **1,438 refits** | quoted from `STEP1B_backtest_e2.md` §2 |
| 15 | Equivalence-margin ladder | **§C** (the MDE re-derivation) and **§D** (the feasibility of each rung). Headline: floor-free branches reach Δ = 0.03–0.04; **every implied-floor branch is UNPOWERED at every k considered** | `.section_2…`, `.section_3…` |
| 16 | Extension spot-check timing | not a census quantity; nothing measured here bears on it | — |
| 17 | §13 stopping rule | not a census quantity | — |
| 18 | KC1 disposition | H1's E2-measured zero-information floor re-derived here from `controls_results.json`: 2.8 × T0 placebo SEs 0.016639 / 0.017439 = **0.0466 / 0.0488** | `data/hardening/controls_results.json` |
| 19 | KC6 carve-out | not exercised. This census computed no IC of any kind, H1's included | `.freeze_statement` |
| 20 | Every-occurrence attribution | 5,706 chunks (1.80%) under >1 CIK; 99,636 of 854,933 occurrence rows (11.65%) cross-company; frame mean `cross_cik_share` **0.1043** | `.section_5….cross_cik_attribution` |
| 21 | `operating_cashflow_to_revenue` period mismatch | 8,433 of 18,300 numeric rows (46.1%); the feature's ICC vs identity is 0.342 raw / 0.509 ranked | `STEP1A_numeric_features_e2.md`; `.section_6…` |
| 22 | Fundamentals staleness guard | 1,868 discards over 99 (CIK, family) pairs; accepted facts p99 = 139 days, 47 above 180 | quoted from `STEP1A_numeric_features_e2.md` |
| 23 | Zero-labeling families | **§I** — novelty coverage 43.5% / 46.8%, prior-gap medians 91 d (both sections), RISK_FACTORS stubs 1,309/3,357 = 39.0%, 855 exact zeros / 516 exact ones, window cap bit 1,888 of 11,020 sections (17.1%) dropping 21.4% of windows, pooled embedding L2 norm mean **0.689** (min 0.559) | `.section_8…` |

---

## B. Fold options for decision 4, with exact quarter lists

All options end at **2026Q1**, the last quarter all of whose 63-session forward
windows close on or before the sha-pinned snapshot (`prices_e2.parquet`
`744e1cc5…`, last session **2026-08-24**). 2026Q2 is 327 complete / 124
incomplete and 2026Q3 is 0/264 (`STEP1A_target_e2.md` §3), so scoring 2026Q2
would score the subset of its filings whose windows happened to close.

| option | quarter list | k | modeling rows | n_dd mean [min, max] | CIKs [min, max] | purge share mean | target complete | channel-A CIKs first → last fold |
|---|---|---|---|---|---|---|---|---|
| **default** | 2018Q1 … 2026Q1 | **33** | 6,204 | **136.30** [119, 161] | [82, 99] | 6.17% | 99.535% | **16 → 0** |
| default, post-2019 arm | 2019Q1 … 2026Q1 | **29** | 5,534 | 137.52 [120, 161] | [85, 99] | 5.15% | 99.640% | 10 → 0 |
| *(alternative reading of "post-2019")* | 2020Q1 … 2026Q1 | 25 | 4,836 | 138.60 [125, 161] | [89, 99] | 4.53% | 99.752% | 8 → 0 |
| **alternative** | 2019Q4 … 2026Q1 | **26** | 5,015 | 138.19 [125, 161] | [89, 99] | 4.66% | 99.722% | 9 → 0 |
| alternative, post-2019 arm | 2019Q4 … 2026Q1 | 26 | 5,015 | identical to the primary | — | — | — | **vacuous** |

Exact lists are in `.section_1_fold_options_decision_4.<option>.quarter_list`.

> **Flag for G3 (definition, not a recommendation).** F5_PLAN decision 4 states
> "post-2019 sub-window = 29 folds". 29 folds is arithmetically consistent
> **only** with a first test quarter of **2019Q1**; the plain-English reading
> "post-2019" (first test 2020Q1) gives **25**. The census reports both so the
> owner can pin one word. It matters: at 25 folds the floor-free ρ_f = 0 branch
> loses the Δ = 0.03 rung (§D).

> **Flag: the alternative's censoring arm is vacuous.** Under k = 26 the
> mandatory post-2019 sensitivity (H5 §7) is the primary run re-labelled. The
> default's four 2018 folds are exactly what makes the arm non-vacuous — and
> they are also the folds carrying 12–16 censored CIKs.

### The 33 default folds, per fold

`censA` = **channel A** price censoring: core CIKs that are members in that
quarter and have a text × numeric row in it, but have **no column in the price
snapshot**, so `target_e2.py` never wrote a row for them. These are invisible to
the joined frame and to `n_benchmark_unpriced`; measuring them required going
around the target table (text × numeric under the membership spells is
price-independent by construction). `null-t` = **channel B**: rows that joined
but whose 63-session target is unresolvable.

| j | test q | rows | n_dd | CIKs | 10-K/Q | overlap rows | train | purged | purge % | null-t | censA CIKs | censA rows | censA share of the would-be CIK panel |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 2018Q1 | 168 | 146 | 82 | 75 | 126 | 1,014 | 168 | 16.57% | 2 | **16** | 37 | **16.3%** |
| 1 | 2018Q2 | 163 | 119 | 82 | 77 | 126 | 1,182 | 169 | 14.30% | 2 | 16 | 32 | 16.3% |
| 2 | 2018Q3 | 168 | 123 | 85 | 80 | 136 | 1,345 | 166 | 12.34% | 3 | 13 | 28 | 13.3% |
| 3 | 2018Q4 | 171 | 122 | 85 | 80 | 138 | 1,513 | 169 | 11.17% | 2 | 12 | 24 | 12.4% |
| 4 | 2019Q1 | 176 | 150 | 85 | 79 | 133 | 1,684 | 171 | 10.15% | 2 | 10 | 20 | 10.5% |
| 5 | 2019Q2 | 168 | 120 | 85 | 79 | 129 | 1,860 | 176 | 9.46% | 2 | 9 | 18 | 9.6% |
| 6 | 2019Q3 | 175 | 125 | 88 | 84 | 138 | 2,028 | 170 | 8.38% | 2 | 10 | 20 | 10.2% |
| 7 | 2019Q4 | 179 | 128 | 89 | 84 | 135 | 2,203 | 175 | 7.94% | 2 | 9 | 19 | 9.2% |
| 8 | 2020Q1 | 182 | 154 | 89 | 85 | 137 | 2,382 | 179 | 7.51% | 2 | 8 | 15 | 8.2% |
| 9 | 2020Q2 | 188 | 131 | 89 | 87 | 146 | 2,564 | 182 | 7.10% | 2 | 8 | 15 | 8.2% |
| 10 | 2020Q3 | 190 | 127 | 93 | 91 | 149 | 2,752 | 188 | 6.83% | 2 | 5 | 11 | 5.1% |
| 11 | 2020Q4 | 193 | 129 | 93 | 91 | 150 | 2,942 | 191 | 6.49% | 2 | 5 | 12 | 5.1% |
| 12 | 2021Q1 | 194 | 161 | 93 | 89 | 153 | 3,135 | 194 | 6.19% | 2 | 4 | 9 | 4.1% |
| 13 | 2021Q2 | 188 | 131 | 92 | 89 | 149 | 3,329 | 195 | 5.86% | 2 | 4 | 8 | 4.2% |
| 14 | 2021Q3 | 188 | 125 | 95 | 92 | 156 | 3,517 | 190 | 5.40% | 0 | 5 | 11 | 5.0% |
| 15 | 2021Q4 | 190 | 130 | 95 | 92 | 158 | 3,705 | 190 | 5.13% | 0 | 5 | 11 | 5.0% |
| 16 | 2022Q1 | 191 | 160 | 95 | 91 | 158 | 3,895 | 192 | 4.93% | 0 | 5 | 11 | 5.0% |
| 17 | 2022Q2 | 195 | 130 | 95 | 92 | 160 | 4,086 | 193 | 4.72% | 0 | 5 | 11 | 5.0% |
| 18 | 2022Q3 | 197 | 134 | 97 | 94 | 165 | 4,281 | 195 | 4.56% | 0 | 3 | 7 | 3.0% |
| 19 | 2022Q4 | 197 | 137 | 97 | 94 | 167 | 4,478 | 197 | 4.40% | 0 | 3 | 7 | 3.0% |
| 20 | 2023Q1 | 194 | 159 | 97 | 93 | 168 | 4,675 | 198 | 4.24% | 0 | 3 | 7 | 3.0% |
| 21 | 2023Q2 | 196 | 131 | 97 | 95 | 166 | 4,869 | 194 | 3.98% | 0 | 3 | 7 | 3.0% |
| 22 | 2023Q3 | 191 | 132 | 95 | 92 | 157 | 5,065 | 196 | 3.87% | 0 | 5 | 11 | 5.0% |
| 23 | 2023Q4 | 193 | 136 | 95 | 92 | 158 | 5,256 | 192 | 3.65% | 0 | 4 | 8 | 4.0% |
| 24 | 2024Q1 | 194 | 155 | 95 | 91 | 164 | 5,449 | 194 | 3.56% | 0 | 4 | 9 | 4.0% |
| 25 | 2024Q2 | 191 | 128 | 95 | 93 | 160 | 5,643 | 194 | 3.44% | 0 | 4 | 8 | 4.0% |
| 26 | 2024Q3 | 192 | 130 | 95 | 94 | 162 | 5,834 | 191 | 3.27% | 0 | 3 | 6 | 3.1% |
| 27 | 2024Q4 | 198 | 136 | 96 | 94 | 173 | 6,026 | 192 | 3.19% | 0 | 2 | 4 | 2.0% |
| 28 | 2025Q1 | 194 | 156 | 96 | 93 | 172 | 6,224 | 198 | 3.18% | 0 | 2 | 4 | 2.0% |
| 29 | 2025Q2 | 197 | 132 | 96 | 94 | 168 | 6,418 | 194 | 3.02% | 0 | 2 | 4 | 2.0% |
| 30 | 2025Q3 | 201 | 134 | 99 | 96 | 171 | 6,615 | 197 | 2.98% | 0 | 0 | 0 | 0.0% |
| 31 | 2025Q4 | 202 | 132 | 99 | 97 | 172 | 6,816 | 201 | 2.95% | 0 | 0 | 0 | 0.0% |
| 32 | 2026Q1 | 200 | 155 | 99 | 95 | 167 | 7,018 | 203 | 2.89% | 0 | 0 | 0 | 0.0% |

Three readings this table forces:

1. **Channel-A censoring is a fold-level gradient, not a flat haircut.** The
   first fold loses **16 of a would-be 99-CIK panel (16.3%)**; the last three
   lose none. This is `F2_INGESTION_REPORT` §0(c)'s cohort profile
   (14.0/16.2/12.5% for 2016/17/18, 6.35% pooled, energy 16.4%) restated on the
   actual fold axis, and the deletions are acquisitions and take-privates — 
   **outcome-correlated and monotonically decaying**. Early folds will differ
   from late folds for this reason before any signal is considered.
2. **Channel B is small and bounded inside the fold window**: 27 rows across
   2018Q1–2021Q2 (2–3 per quarter, the coverage-gap filings), zero thereafter.
   Under the default fold list the snapshot causes **no** censoring; all 229
   dropped null-target rows outside the window are 2026Q2/Q3.
3. **n_dd is seasonal.** Q1 folds run 146–161; Q2–Q4 folds run 119–137. Per-fold
   power is not constant across the year, and the LOCO index rule
   (`round(j·32/5)`) happens to start on a Q1 fold.

---

## C. THE MDE RE-DERIVATION at k = 33 on the measured n_dd

### C.1 The algebra, step by step

Recovered from `H2_spec.md` §4 / `EXPANSION_PLAN` §2a amendment and checked
against their published table before being used (see C.2).

```
step 1   sigma_samp(fold j) = sigma_boot * sqrt(n_ref / n_dd(j))
step 2   sigma_tot(j)^2     = sigma_samp(j)^2 + implied_floor^2     [floor branch only]
step 3   SE(mean delta)     = sqrt( sum_j sigma_tot(j)^2 ) / k  *  sqrt(1 + 2*sum_{l=1}^{k-1} (1 - l/k) * rho_f^l)
step 4   MDE = 2.8 * SE     95% null bound = 1.96 * SE     true-construct = MDE / lambda
```

Inputs, each quoted from its source, none invented here:

| symbol | value | source |
|---|---|---|
| `sigma_boot` (within-fold bootstrap SD, mean over folds, 4,000 resamples/fold) | 0.1149 `pit_trailing_rank` · 0.1046 `raw_levels` | H2 §3.2 |
| `n_ref` (the n_dd that SD was measured at) | 39.5 | H2 §3.2 / §2a amendment |
| `implied_floor` | **0.0992** `pit_trailing_rank` · 0.0000 `raw_levels` | H2 §3.2 — **unresolved at 6 folds**, χ² p = 0.13 / 0.16 in both directions |
| `rho_f` | 0 and 0.3 | H2 §4's assumption; measured for the first time at Step 4 |
| multiplier | 2.8 (two-sided 5%, 80% power) | H2 §4 |
| λ (labeler reliability) | ≈ 0.8 | `methodology_audit.md` §(b) |
| `n_dd(j)` | **the measured per-fold dedup counts of §B** | `census_head1.json` |

Because σ_samp(j) ∝ n_dd(j)^(−½), step 3's exact sum is governed by the
**harmonic** mean of n_dd (135.23 over the 33 default folds), not the arithmetic
mean (136.30). The gap is 0.4% on the SE — n_dd is homogeneous enough across the
33 folds that the heterogeneous and the homogeneous computations agree to three
decimals. Both are in the JSON (`SE` and `SE_homogeneous_at_mean_n_dd`).

### C.2 Reproduction check against H2's published table (k = 26, n_dd = 158)

| spec | branch | ρ_f | SE here | SE published |
|---|---|---|---|---|
| `raw_levels` | floor-free | 0 | 0.01026 | 0.0103 |
| `raw_levels` | floor-free | 0.3 | 0.01380 | 0.0138 |
| `pit_trailing_rank` | floor-free | 0 | 0.01127 | 0.0113 |
| `pit_trailing_rank` | floor-free | 0.3 | 0.01516 | 0.0152 |
| `pit_trailing_rank` | implied floor | 0 | 0.02248 | 0.0225 |
| `pit_trailing_rank` | implied floor | 0.3 | 0.03025 | 0.0303 |

Every SE reproduces to 4 dp; the AR(1) variance inflation reproduces H2's
**1.810** (SE × 1.3454) at k = 26, ρ = 0.3. H2's printed MDEs multiply the
*rounded* SE by 2.8 (0.0152 × 2.8 = 0.043) where the unrounded chain gives
0.0424; the 1-unit third-decimal gaps are that rounding path, not a
disagreement.

### C.3 The re-derived MDE (primary spec `pit_trailing_rank`, measured n_dd)

| option | k | n_dd mean | branch | ρ_f | SE | **MDE** | true-construct (λ 0.8) | 95% null bound |
|---|---|---|---|---|---|---|---|---|
| **default** | **33** | **136.30** | floor-free | 0 | 0.01081 | **0.0303** | 0.0378 | ±0.0212 |
| | | | floor-free | 0.3 | 0.01458 | **0.0408** | 0.0510 | ±0.0286 |
| | | | implied floor | 0 | 0.02037 | **0.0570** | 0.0713 | ±0.0399 |
| | | | implied floor | 0.3 | 0.02748 | **0.0770** | 0.0962 | ±0.0539 |
| **default, post-2019 arm** | **29** | 137.52 | floor-free | 0 | 0.01148 | **0.0321** | 0.0402 | ±0.0225 |
| | | | floor-free | 0.3 | 0.01546 | **0.0433** | 0.0541 | ±0.0303 |
| | | | implied floor | 0 | 0.02170 | **0.0608** | 0.0760 | ±0.0425 |
| | | | implied floor | 0.3 | 0.02924 | **0.0819** | 0.1023 | ±0.0573 |
| *(post-2019 read as 2020Q1+)* | 25 | 138.60 | floor-free | 0 | 0.01231 | 0.0345 | 0.0431 | ±0.0241 |
| | | | implied floor | 0.3 | 0.03140 | 0.0879 | 0.1099 | ±0.0615 |
| **alternative** | **26** | 138.19 | floor-free | 0 | 0.01209 | **0.0338** | 0.0423 | ±0.0237 |
| | | | floor-free | 0.3 | 0.01626 | **0.0455** | 0.0569 | ±0.0319 |
| | | | implied floor | 0 | 0.02290 | **0.0641** | 0.0802 | ±0.0449 |
| | | | implied floor | 0.3 | 0.03082 | **0.0863** | 0.1079 | ±0.0604 |

Secondary spec `raw_levels` at k = 33: SE 0.00984 / 0.01328, MDE **0.0276 /
0.0372** (ρ_f = 0 / 0.3). Full rows including every per-family scaling are in
`.section_2_mde_decision_15_KC3.at_measured_n_dd`.

**The honest headline: the extra seven folds buy almost nothing, because the
measured n_dd is smaller than the planning assumption.** The fold-count factor
is √(26/33) = 0.888; the n_dd factor is √(158/136.3) = 1.077. They very nearly
cancel: the primary-spec floor-free ρ_f = 0 MDE moves from H2's published
**0.032** to **0.0303** — a 5% improvement, not the 11% that k alone suggests.
At the ratified k = 33 the honest primary-spec bracket is **0.030 → 0.077
measured**, **0.038 → 0.096 true-construct**, with the null bound **±0.021 →
±0.054**.

### C.4 Caveats that attach to every number in C.3, every time

- **Every MDE above is a LOWER BOUND.** Folds are not independent; ρ_f = 0.3 is
  H2's *assumption*, not a measurement, and ρ_f is measured for the first time at
  Step 4. H5 kill-criterion 4 governs what happens if it exceeds 0.3: publish the
  degraded bound, never re-window.
- **Pure 1/√k rescaling is an upper bound on any gain from more folds.** Two
  reasons, both visible in §B: the early folds run on **82–89 usable CIKs**
  against 95–99 late (and on a would-be panel 12–16% of which has no price
  column at all), so they are not exchangeable draws from the same population;
  and n_dd is seasonal (Q1 146–161 vs Q2–Q4 119–137), so the per-fold variances
  the rescaling averages are not equal. The heterogeneous computation in C.1
  captures the second effect (worth +0.4% on the SE) but **not** the first — no
  arithmetic here can, because "the same estimand measured on a different and
  more censored company set" is a bias question, not a variance question.
- **The noise anchor was estimated on E1's 2025–2026 mega-cap folds** and may not
  transfer to 2016-era folds. Everything above inherits that.
- **Per-family MDEs scale ≈ 0.4× – 2.4×** around the full-model numbers
  (EXPANSION_PLAN §2a). At k = 33, floor-free ρ_f = 0.3, that is **0.016 →
  0.098** depending on the family.
- **True-construct units divide by λ ≈ 0.8**; λ ≈ 0.6–0.7 where sections are
  short, which is worse. λ for G3 must be sourced per the G2 §6.5 box (H3v2
  retention or the m-chunk composition with m stated) — **never** a G2 chunk
  proportion.
- **The variance floor is the whole ballgame and it is unresolved.** χ² p = 0.13
  (spread > sampling) and 0.16 (spread < sampling) at 6 E1 folds: a measured
  0.0992 does not establish the floor's presence and a measured 0.0000 does not
  establish its absence. E2's 33 folds can resolve it — at Step 4, before any
  delta is read.
- **The t-correction is not applied** (as in H2). It would raise the multiplier
  from 2.802 to **2.890** at k = 33, 2.903 at k = 29, 2.916 at k = 26 (+3.1% /
  +3.6% / +4.1% on every MDE). Add it for the conservative read.
- **EXPANSION_PLAN §2a's published 0.019–0.037 bracket is SUPERSEDED** by the
  2026-08-25 H2 amendment. Quote the amendment.

---

## D. Margin-ladder feasibility (decision 15)

Rule: Δ = the smallest rung of {0.03, 0.04, 0.05} with **SE ≤ Δ/2.487**; if none
satisfies it the result is **UNPOWERED** — no equivalence claim, ever reported as
equivalent. SE caps: **0.03 → 0.012063 · 0.04 → 0.016084 · 0.05 → 0.020105**.

**These rows are projections, not a selection.** The SE used here is the ex-ante
projection of §C, built from E1's bootstrap SD and E1's implied floor. The
ladder executes at Step 4 on the **E2-measured block-bootstrap SE**, inside the
runner, before any delta is printed. This census cannot and does not select Δ;
choosing Δ from these projections would be exactly the post-hoc design choice
decision 15 exists to forbid.

| option | k | branch | ρ_f | projected SE | rungs satisfied | projected verdict | implied MDE (2.8·SE) | KC3 branch |
|---|---|---|---|---|---|---|---|---|
| **default** | 33 | floor-free | 0 | 0.01081 | 0.03, 0.04, 0.05 | **Δ = 0.03** | 0.0303 | no |
| | 33 | floor-free | 0.3 | 0.01458 | 0.04, 0.05 | **Δ = 0.04** | 0.0408 | **yes** |
| | 33 | implied floor | 0 | 0.02037 | — | **UNPOWERED** | — | — |
| | 33 | implied floor | 0.3 | 0.02748 | — | **UNPOWERED** | — | — |
| post-2019 arm | 29 | floor-free | 0 | 0.01148 | 0.03, 0.04, 0.05 | Δ = 0.03 | 0.0321 | no |
| | 29 | floor-free | 0.3 | 0.01546 | 0.04, 0.05 | Δ = 0.04 | 0.0433 | yes |
| | 29 | implied floor | 0 | 0.02170 | — | **UNPOWERED** | — | — |
| | 29 | implied floor | 0.3 | 0.02924 | — | **UNPOWERED** | — | — |
| **alternative** | 26 | floor-free | 0 | 0.01209 | 0.04, 0.05 | **Δ = 0.04** | 0.0338 | **yes** |
| | 26 | floor-free | 0.3 | 0.01626 | 0.05 | **Δ = 0.05** | 0.0455 | **yes** |
| | 26 | implied floor | 0 | 0.02290 | — | **UNPOWERED** | — | — |
| | 26 | implied floor | 0.3 | 0.03082 | — | **UNPOWERED** | — | — |

**The one-line answer.** Under the primary spec, **every implied-floor branch is
UNPOWERED at k = 33, k = 29 and k = 26** — no rung of the ratified ladder is
reachable if the rank-spec variance floor is real, which is precisely H5
kill-criterion 3 live in the floor branch. The floor-free branches reach Δ = 0.03
(ρ_f = 0) and Δ = 0.04 (ρ_f = 0.3) at k = 33, and one rung worse at k = 26.

**Two near-misses the owner must see, because they make the projected verdict
fragile rather than informative:**

- k = 33, implied floor, ρ_f = 0: SE 0.020373 against a 0.020105 cap — it misses
  Δ = 0.05 by **+0.00027, i.e. 1.3% of the cap**. A slightly smaller floor
  estimate flips UNPOWERED to "Δ = 0.05 with an implied MDE of 0.057".
- k = 26, floor-free, ρ_f = 0: SE 0.012089 against a 0.012063 cap — it misses
  Δ = 0.03 by **+0.000026, 0.2% of the cap**. This is a tie, not a finding.

That fragility is an argument *for* the ratified design ("pre-register the
procedure, not the value") and against reading any projected Δ as a
pre-commitment. KC3's standing re-cut applies: any selected Δ > 0.03 prints
beside its implied MDE and is flagged as the KC3 branch; Δ = 0.05 admits an
honest MDE up to **0.0563**.

---

## E. The three-way joined frame

```
29,271  target rows written (149 core CIKs with price coverage)
16,859  in-membership (info_date inside a core spell) — 148 CIKs
 7,634  three-way join on (cik, accession_number): target x text x numeric
 7,634  after the LEFT join of text_families (n_emb_missing = 0)
   229  dropped: target_excess_63 null
 7,405  MODELING ROWS — 144 CIKs, 2016-07-05 … 2026-05-21
 5,383  after company-quarter dedup at gap_days = 5 (72.7%)
```

**The 9,225 in-membership rows that do not join, by form:**

| form | rows without a text row | rows without a numeric row |
|---|---|---|
| 8-K | **9,080** | 0 |
| 10-Q | **104** | 0 |
| 10-K | **41** | 0 |
| total | **9,225** | **0** |

`numeric_features_e2` covers **all** 16,859 in-membership rows, so every join
loss is a **text** loss. The 9,080 8-Ks are non-earnings-bearing (F3/F4
extracted text only for earnings-bearing 8-Ks — by design). The 145 periodic
filings are the never-extracted set, and they are **not** random:

| CIK | company | sector | missing (10-K / 10-Q) | of that CIK's in-membership periodic filings | span |
|---|---|---|---|---|---|
| 831001 | CITIGROUP INC | financials | **41** (10 / 31) | **41 — 100%** | 2016-08-01 … 2026-08-06 |
| 895421 | MORGAN STANLEY | financials | **38** (9 / 29) | 41 — 93% | 2017-05-04 … 2026-08-04 |
| 36104 | US BANCORP \DE\ | financials | **26** (8 / 18) | 32 — 81% | 2016-11-04 … 2024-02-20 |
| 21665 | COLGATE PALMOLIVE CO | consumer | **16** (0 / 16) | 25 — 64% | 2016-07-28 … 2026-07-31 |
| 72971 | WELLS FARGO & COMPANY/MN | financials | **10** (10 / 0) | 41 — 24% | 2017-03-01 … 2026-02-24 |
| 1390777 | Bank of New York Mellon Corp | financials | **9** (3 / 6) | 16 — 56% | 2017-02-28 … 2019-11-07 |
| 5272 | AMERICAN INTERNATIONAL GROUP, INC. | financials | **2** (0 / 2) | 20 — 10% | 2016-08-02 … 2016-11-03 |
| 50863 | INTEL CORP | tech | **1** (1 / 0) | 40 — 2% | 2018-02-16 |
| 713676 | PNC FINANCIAL SERVICES GROUP, INC. | financials | **1** (0 / 1) | 28 — 4% | 2017-05-03 |
| 97476 | TEXAS INSTRUMENTS INC | tech | **1** (0 / 1) | 41 — 2% | 2019-04-30 |

**Seven of ten are financials**, and the three largest losses (Citigroup 100%,
Morgan Stanley 93%, US Bancorp 81%) mean those companies enter the text arm on
8-K press releases essentially alone, across the whole decade. That is a
sector-shaped hole in `share_chunks_risk_factors` / `share_chunks_mda` /
the Item 1A–Item 7 novelty family, and it is a disclosure G3 §11 should carry.
It is not a leakage or dating defect — those rows are simply absent from both
arms.

**Per quarter, the modeling frame** spans 40 quarters at **161–202 rows over
82–99 CIKs** (mean 185.1). Note the bookkeeping: F5_PLAN decision 4 quotes
"7,634 rows today, 161–202 per quarter over 82–99 CIKs" — 7,634 is the joined
frame *before* the null-target drop, while 161–202 / 82–99 is the 7,405-row
modeling frame. The joined frame's per-quarter range is 163–203.

**One more gap worth a sentence:** `text_families_e2` holds 7,723 rows
(in-membership filings with ≥ 1 **corpus** section) against 7,634 joined rows
(filings with ≥ 1 attributed **labeled** chunk) — **89 filings** have corpus text
but no attributed labeled chunk. The left join keeps the frame at 7,634 and
`n_emb_missing = 0`, so nothing is silently dropped.

---

## F. Label-purge, provenance and instrument census

| quantity | value | base | source |
|---|---|---|---|
| training rows purged, 33 default folds | **6,194** (row, fold) instances | expanding training sets | `census_head1.json` |
| purge share per fold | mean **6.17%**, max 16.57% (2018Q1), min 2.89% (2026Q1) | — | ″ |
| E1 comparator (no purge existed) | 313 / 2,425 = **12.9%** | E1 training labels | H2 §3.3 |
| `train_overlap`, **chunk level** | **14,342 = 4.534%** (home 10,442 · any-source 14,341 · text 487 · union 14,342) | 316,291-row feature frame | `STEP1A_features_e2.md` |
| `train_overlap`, **filing level** | **5,938 = 80.19%** | 7,405 modeling rows | measured here |
| — the "without overlap" arm as built | scores **1,467** rows; the fit is unchanged | evaluation-side restriction | `STEP1B_backtest_e2.md` §4 |
| `selfid`, chunk level | **146,958 = 46.46%**; frame mean `selfid_share` **0.5643** | 316,291 / 7,405 | `STEP1A` / here |
| `cross_cik_share`, frame mean | **0.1043**; 5,706 chunks (1.80%) under > 1 CIK; 99,636 / 854,933 occurrence rows (11.65%) cross-company | — | decision 20 |
| sentiment masked (RISK_FACTORS) | **4,177** — NEUTRAL 3,452 / NEGATIVE 688 / POSITIVE 37 | corpus | `STEP1A` |
| guidance masked (MDA + RISK_FACTORS) | **2,826** = 2,803 + 23, of which **230 active** | corpus | ″ |
| imputed NONE | **48,790** corpus = 51.18% of applicable; 48,293 frame = 51.08% | applicable chunks | ″ |
| schema-invalid, disclosure only | **23 = 17** guidance-enum + **4** red-flag-category + **2** red-flag-modality | corpus | ″ |
| 8K_BODY chunks excluded | **790** (corpus 317,081 → frame 316,291) | — | ″ |
| **WITHDRAWN** | **71** corpus → **66** on the feature frame | see below | measured here |
| GLD | **8** modeling rows, 1 CIK, 6 × 10-Q + 2 × 10-K | 7,405 | measured here |

**Two of these are different questions and must never be quoted as one another.**
4.53% is the **chunk-level** accession-channel share; 80.19% is the share of
**modeling rows** containing at least one such chunk. Both are lower bounds on
labeler exposure: the accession channel misses CIK-level exposure, which is
15.85%.

### WITHDRAWN, n = 66 (decision 11)

Derivation, which reproduces the plan's figure exactly: **71** corpus chunks
− 1 in 8K_BODY (decision 9 excludes the register) − 4 in MDA (decision 10 masks
guidance there) = **66**, all in EX99_PRESS_RELEASE, over 54 distinct filings and
38 CIKs.

| year | 2015 | 2020 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| chunks | 2 | **52** | 1 | 2 | 5 | 4 |

| quarter | 2015Q4 | 2020Q1 | **2020Q2** | 2020Q3 | 2020Q4 | 2022Q2 | 2023Q4 | 2024Q4 | 2025Q2 |
|---|---|---|---|---|---|---|---|---|---|
| chunks | 2 | 2 | **41** | 6 | 3 | 1 | 2 | 5 | 4 |

**The population is a COVID event cluster.** 52 of 66 are 2020 and 41 of those
are a single quarter. On the head-1 frame they touch only **35 of 7,405 modeling
rows (0.47%)**, distributed 2020Q2 **25** · 2020Q3 5 · 2020Q4 3 · 2024Q4 2. So
decision 11's "one sensitivity row excluding WITHDRAWN" is, in practice, a
**one-fold sensitivity on 2020Q2** — worth running and worth labelling as such,
but it cannot move a 33-fold mean materially in either direction. The gap between
54 filings carrying a WITHDRAWN chunk and 35 modeling rows is the usual one:
membership, the 2015 pre-window filings, and the target join.

---

## G. E2 ICCs against company identity (the H2 §2 identification argument)

One-way random-effects ICC(1) = (MSB − MSW)/(MSB + (n₀−1)·MSW) with the
unequal-group-size correction n₀ and the exact F-based 95% CI. Grouping variable
is `cik`. **No outcome column enters this computation.** Two bases are reported,
as standing practice: the 7,405-row modeling frame and the 5,383-row dedup frame.

| feature | n | companies | **ICC raw levels** [95% CI] | ICC PIT-ranked | ICC raw, dedup base |
|---|---|---|---|---|---|
| `log_total_assets` | 7,356 | 143 | **0.9453** [0.933, 0.957] | 0.9420 | 0.9540 |
| `leverage_liabilities_to_assets` | 5,214 | 105 | **0.9097** [0.886, 0.931] | 0.9008 | 0.9147 |
| `equity_to_assets` | 7,346 | 143 | **0.9003** [0.878, 0.921] | 0.8890 | 0.9065 |
| `book_to_market` | 6,229 | 122 | 0.6826 [0.628, 0.739] | **0.8352** | 0.7079 |
| `cash_to_assets` | 6,988 | 141 | 0.6247 [0.570, 0.682] | **0.8008** | 0.6429 |
| `operating_margin` | 4,441 | 95 | 0.3554 [0.294, 0.432] | **0.7228** | 0.3869 |
| `operating_cashflow_to_revenue` | 6,268 | 134 | 0.3423 [0.290, 0.405] | **0.5092** | 0.3293 |
| `net_margin` | 6,459 | 134 | 0.3141 [0.265, 0.375] | **0.6492** | 0.3587 |
| `realized_vol_63` | 7,405 | 144 | 0.2647 [0.222, 0.318] | **0.4829** | 0.2705 |
| `revenue_yoy_growth` | 6,522 | 135 | 0.1279 [0.101, 0.164] | 0.2171 | 0.1172 |
| `momentum_126` | 7,405 | 144 | 0.0771 [0.059, 0.101] | 0.0739 | 0.0756 |
| `net_income_yoy_growth` | 7,319 | 143 | 0.0006 [−0.003, 0.006] | 0.0593 | −0.0085 |
| `eps_diluted_yoy_growth` | 7,153 | 139 | −0.0115 [−0.013, −0.009] | 0.0598 | −0.0232 |

The PIT-rank column is `spec.pit_trailing_rank_frame(window_days=180,
min_comparators=2, include_same_day=True, ticker_col="cik")` — the ratified
primary transform, the frozen pure function, applied to the same frame. Its n
differs from the raw n by **at most one row** per feature (0 or 1: the frame's
first row has no trailing comparator set), so the two columns are computed on
materially the same observations and the movement below is the transform, not a
change of sample.

**Three readings, offered as measurement, not as a proposal to re-cut anything:**

1. **E1's 0.987 does not carry to E2.** `log_total_assets` ICC is **0.945
   [0.933, 0.957]** on the E2 modeling frame — still very high, and the CI
   excludes 0.987. The E2 panel is 144 churning companies over a decade, not
   E1's 25 over three years; company identity explains slightly less.
2. **The PIT-rank transform does not decorrelate features from company
   identity.** For the three levels-like features it leaves the ICC essentially
   where it was (0.945 → 0.942, 0.910 → 0.901, 0.900 → 0.889); for six of the
   thirteen it **raises** it, sharply (`net_margin` 0.314 → 0.649,
   `operating_margin` 0.355 → 0.723, `cash_to_assets` 0.625 → 0.801,
   `book_to_market` 0.683 → 0.835, `realized_vol_63` 0.265 → 0.483). The
   transform re-expresses a feature on a common trailing cross-sectional scale
   and thereby strips the *time-varying common* component; what remains is
   company persistence, which is what an ICC measures.
3. **Therefore H2 §2's stated a-priori rationale should be re-read before it is
   ratified.** H2 §2 justifies making ranks the PRIMARY spec with: *"raw levels
   encode company identity almost exactly (ICC 0.987 `log_total_assets`), so
   both arms of the text-vs-numeric comparison ride the same company-persistence
   term."* The E2 measurement says **both specifications ride that term**, and
   the ranked spec rides it at least as hard for the ratio features. This does
   **not** invalidate the pre-registration — the spec pair was fixed at H2 and
   the two arms are still reported as a pair, which is what protects the
   comparison — but the *reason sentence* in G3 §1 should say what is true on
   E2 rather than restate an E1 number. That is a wording decision for the owner
   at decision 3, and it is raised **before** any result exists, which is the
   only time raising it is legitimate.

---

## H. Heads 2 and 3

### Head 2 (decision 12)

| quantity | value |
|---|---|
| earnings 8-Ks, all strata / core | 5,903 over 242 CIKs / **4,374** over 174 core CIKs |
| usable for head 2 | **3,996** over **41** event-quarter clusters (2016Q3 … 2026Q3) |
| dropped: no price column | **320** events (27 core CIKs) |
| dropped: incomplete prices / window past snapshot / off-calendar | 17 / 3 / 0 |
| events with no text-feature row | **38** |
| events with a text row but a null predictor | 0 |
| events with a flat session inside [+1, +5] | 81 |
| events with a zero trailing denominator | 0 |

**The partial-quarter finding, restated.** 2026Q3 contributes **92** usable
events against a complete-quarter range of **83–107** (mean 97.6) — it looks
almost full-sized because a 5-session window closes quickly, which is exactly
why it is a trap: it is a partial quarter that does not announce itself in the
count. Ending at the last **complete** quarter (2026Q2, symmetric with decision
4) gives **40 clusters / 3,904 events**. Both are in the JSON.

With 40 clusters, the wild-cluster bootstrap over event quarters is the honest
statistic; a pooled p-value would be anti-conservative because earnings cluster
in seasons (the same non-independence H1 flagged).

The predictor is the field G2 ruled **INDETERMINATE**: owner-ratified sentiment
agreement **293/337 = 86.94%, Wilson 95% CI [82.93, 90.13]**, against the 0.85
bar — the CI straddles it, which is what INDETERMINATE means
(`G2_FINAL_REPORT.md` §0). Two escorts travel with it and belong on this row:
`sentiment_negative_share` rests on a stored-NEGATIVE **precision of 25/49 =
51.0%**, and the teacher-side NEGATIVE **recall is 0.487**. And the standing
epistemic caveat (HANDOFF §3): that 86.94% is **model consensus over
model-adjudicated fields — agreement between a student and an adjudicating
model, not human validation of ground truth.** The DV is separately not
dividend-immune, because prices are split-adjusted only.

### Head 3 (decision 13) — exit kinds

`distress_events` holds 668 rows over 144 CIKs; **480** rows sit on the core
panel. The test "is the same company still filing in-membership a year later?"
is what separates a real membership-ending exit from an exchange transfer or a
deregistration of one class:

| event kind | rows on panel CIKs | still filing in-membership a year later | **share that are NOT exits** | rows that do end membership |
|---|---|---|---|---|
| `delisting_form_25_nse_exchange_filed` | 360 | 285 | **79.2%** | 75 |
| `deregistration_form_15` | 93 | 50 | **53.8%** | 43 |
| `delisting_form_25` | 25 | 14 | **56.0%** | 11 |
| `bankruptcy_8k_item_1_03` | 2 | 2 | **100%** | 0 |
| **pooled** | **480** | **351** | **73.1%** | **129** |

**Under the default `exit_event_kinds`, roughly three in four positives are not
exits.** The ratified set must be the one that actually ends membership; on this
measurement the honest positive population is ~129 rows, not 480, and the
bankruptcy channel contributes **zero** usable positives (both item-1.03 rows are
followed by continued in-membership filing). M&A cannot be separated from
distress at all: `items` is NULL on 666 of 668 rows, which is why decision 13's
claim scope is "exit", never "distress".

Other head-3 populations: `latest_in_quarter` gives 4,056 panel rows over 175
CIKs with **70.0% carrying no text features**; `latest_in_quarter_with_text`
gives 4,042 rows with 0% missing but dates features earlier in the quarter.
Candidate label cut 2026-08-17 (max `distress_events.filing_date`, a candidate
with no ratified source) censors **5 of 41** panel quarters; last uncensored
quarter 2025Q2.

---

## I. Text families (decision 23)

From `data/f5/text_families_e2_manifest.json` (build: 7,723 rows, 148 CIKs,
25.6 min, peak RSS 3.75 GB).

| item | measured |
|---|---|
| coverage | 7,723 of 16,859 in-membership target rows; 9,136 without corpus text |
| novelty present: RISK_FACTORS / MDA | 3,357 (**43.5%**) / 3,615 (**46.8%**) |
| (a) prior-gap median, RISK_FACTORS | **91 d** overall — 10-K 110.5 d, 10-Q 91 d; p25–p75 87–98, max 379 |
| (a) prior-gap median, MDA | **91 d** overall — 10-K 108 d, 10-Q 91 d; p25–p75 86.5–97, max 375 |
| (b) RISK_FACTORS stubs | **1,309 of 3,357 pairs (39.0%)** have a side under 50 shingles; **855 exact zeros**, **516 exact ones**; median min-shingles **86** |
| (b) MDA, for contrast | 82 of 3,615 (2.3%) stubs; 10 exact zeros, 28 exact ones; median min-shingles **6,697** |
| (c) prior-candidate pool | whole corpus for the CIK (back to 2015-07), not restricted to in-membership |
| (d) 8K_BODY sections embedded | **85** (in scope for family B though excluded from label features) |
| (e) filing pooling | unweighted mean over section vectors, sections weighted equally |
| (f) window cap | 64/section; **1,888 of 11,020 sections (17.1%)** hit it; 377,542 of an uncapped 480,070 windows were kept → **21.4% of windows dropped** |
| (g) embedding norms | pooled `emb` L2 norm mean **0.6893**, min **0.5587**, max 1.0000, width 384, `n_emb_missing = 0` on the frame |
| (h) model | `sentence-transformers/all-MiniLM-L6-v2`, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, weights sha `53aa5117…`, Apache-2.0, cached outside the repo |
| novelty distributions | RISK_FACTORS mean 0.4916 / median 0.3144; MDA mean 0.5340 / median 0.5097 |

Two things this census wants on the record for decision 23, both arithmetic:

- **The `_yoy` names are not year-over-year.** The prior-gap medians are **91
  days** for both sections — a quarter, not a year — because the prior is "most
  recent prior filing of the same section", so a 10-K's prior is the preceding
  10-Q (10-K medians 108–110 days confirm it). Pinning the prior-year filing of
  the same form (the plan's default) changes what the feature measures, not just
  its name.
- **RISK_FACTORS novelty is a stub detector as built.** 39.0% of its pairs have a
  side under 50 shingles and the median minimum-side length is 86 shingles
  against MDA's 6,697; 855 exact zeros and 516 exact ones are 40.9% of the
  non-null values sitting on the two boundary points. Whatever the minimum-length
  filter is set to, the stub count has to be disclosed beside the feature.
- **The pooled embedding is not unit-norm** (mean 0.689): filing pooling averages
  section vectors and does not renormalize, so ‖emb‖ is itself a measure of
  within-filing section dispersion, and a PCA on these vectors is a PCA on
  unnormalized means. Whether that is wanted is decision 23(e)/(g).

---

## J. What this census cannot say

This census contains **no information coefficient, no IC delta, no per-fold
delta, no fold-delta autocorrelation, no block-bootstrap SE — and therefore no
selected equivalence margin.** Every SE and MDE in §C and §D is an *ex-ante
projection* built from E1's within-fold bootstrap SD and E1's implied regime
floor, rescaled to E2's measured per-fold n_dd; the real SE is a block bootstrap
over E2's own fold deltas and is measured for the first time at Step 4, inside
the runner, before any delta is printed. The ladder rows say what the design
could plausibly deliver, not what Δ will be — selecting Δ from these projections,
or from any realized SE, would be the post-hoc design choice decision 15 exists
to forbid. The census cannot say whether the rank-spec variance floor is real
(unresolved at 6 E1 folds, χ² p = 0.13/0.16 in both directions), cannot say
whether fold non-independence exceeds ρ_f = 0.3, cannot say what a labeled
feature's true-construct reliability λ is on E2, and says **nothing whatever**
about whether any text feature carries information about returns. Every
population count above describes the *instrument*; none of them is evidence
about the *world*.

---

## K. Runtimes (M5, single process)

| step | seconds |
|---|---|
| read the existing Step 1a/1b census artifacts | 0.0002 |
| `backtest_e2.load_analysis_frame` (4 sha assertions + the three-way join) | 0.080 |
| price-censoring census (membership spells × text × numeric × price snapshot) | 0.231 |
| fold options (3 + 2 variants, 33/29/25/26 folds) | 0.003 |
| MDE table + ladder feasibility | 0.001 |
| frame decomposition + the 10 named CIKs | 0.048 |
| instrument census incl. the WITHDRAWN scan of `labels_e2_v1.parquet` | 0.028 |
| ICC census (13 features × 3 bases, incl. the PIT-rank transform) | 0.449 |
| heads + families restatement | 0.00003 |
| **total** | **1.04** |

Command: `python3 data/f5/census_e2.py` from the repo root. `$0`, zero network
calls, writes exactly one file (`data/f5/census_e2.json`, 205 KB).

---

## L. Flags carried forward to Step 3 (each is a wording or definition question
the owner rules, not a finding)

1. **"post-2019 = 29 folds" is only true if the first test quarter is 2019Q1.**
   The plain reading (2020Q1) gives 25 and costs the Δ = 0.03 rung. Pin the word.
2. **The ladder verdict is fragile at two points** (§D): 1.3% and 0.2% of the
   respective SE caps. Read as "the projections do not settle this", not as a Δ.
3. **H2 §2's rationale sentence for the primary spec does not survive
   re-measurement on E2** (§G). The spec pair itself is unaffected; the
   justification in G3 §1 should be restated from the E2 numbers.
4. **The never-extracted periodic filings are 70% financials** and remove
   Citigroup's, Morgan Stanley's and US Bancorp's periodic text essentially
   entirely (§E) — a §11 disclosure, and a caveat on any sector-level reading.
5. **The default `exit_event_kinds` are 73% non-exits** (§H); decision 13's
   ratified set should be named from the 129-row population, and the bankruptcy
   channel yields zero usable positives.
6. **WITHDRAWN is one COVID quarter** (§F): the decision-11 sensitivity row is a
   2020Q2 sensitivity, and should be labelled that way when it is reported.
7. **`text_families` is 89 rows wider than the label-derived frame** (§E); the
   left join handles it and `n_emb_missing = 0`, but the two scopes are different
   populations and G3 §1 should say which one the zero-labeling families are
   pre-registered over.
