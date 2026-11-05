# G3 run 2026-11-05 — the owner's read (head 1 per-fold table, universe scorecard block, heads 2–3)

Pinned document sha `6b99f65ea1da42e8…`; run started 2026-11-05T22:13:24+00:00; mode `real`.
Everything below is copied or re-derived from `data/f5/results_head1.json`, `results_head2.json`, `results_head3.json`
and `data/f5/head1_scorecard.md` (the per-company pages are in that file, git-excluded, 139 companies). Nothing here is
interpreted beyond what the ratified pre-registration (§13) maps a result to.

## 1. Head 1 — the pre-registered margin ladder (§1 / §13), mechanically applied

| quantity | value |
|---|---|
| folds (test quarters) | 33 (2018Q1–2026Q1) |
| mean per-fold dedup IC delta, text+numeric minus numeric-only | +0.0011 |
| SE (block bootstrap, block length 1, 4000 resamples, seed 0) | 0.0149 (Newey–West alternative 0.0149) |
| 90% CI | [-0.0234, +0.0256] |
| ladder [0.03, 0.04, 0.05] → selected margin | 0.04 (0.03 not satisfied: SE required 0.0121 < measured) |
| power status | POWERED; honest MDE printed beside it: 0.0416 (KC3 branch) |
| TOST equivalence inside ±0.04 | True (p = 0.0045) |

**What the ratified §13 maps this to (quoted, `G3_PREREGISTRATION.md` §13 outcome map row):** *"Bounded null — text is not used as a signal; the study is written up and closed (F6 negative result + failure taxonomy; pipeline archived as asset)."* And §14: *"The scorecard cannot change the §13 outcome: if the IC margin comes back bounded-null or UNPOWERED, the text arm is closed regardless of how the hit rates read."*

Caveats that travel with it (from the results file): every MDE is a lower bound (nested expanding windows, 63-session windows straddle fold boundaries, so effective k < 33); the bootstrap noise anchor is computed without the per-fold embedding components (stated, not absorbed).

### Per-fold primary deltas (dedup), all 33

| test quarter | n dedup | IC numeric-only | IC text+numeric | delta |
|---|---|---|---|---|
| 2018Q1 | 144 | +0.0140 | -0.0568 | -0.0708 |
| 2018Q2 | 118 | -0.1539 | -0.1664 | -0.0125 |
| 2018Q3 | 123 | -0.3819 | -0.3737 | +0.0082 |
| 2018Q4 | 122 | -0.1080 | +0.0125 | +0.1205 |
| 2019Q1 | 149 | +0.0732 | +0.1079 | +0.0347 |
| 2019Q2 | 119 | +0.1583 | +0.1800 | +0.0217 |
| 2019Q3 | 125 | +0.0458 | -0.0064 | -0.0522 |
| 2019Q4 | 128 | +0.1425 | +0.1559 | +0.0134 |
| 2020Q1 | 152 | -0.0977 | +0.1227 | +0.2204 |
| 2020Q2 | 130 | +0.2698 | +0.3019 | +0.0321 |
| 2020Q3 | 127 | +0.2163 | +0.1945 | -0.0218 |
| 2020Q4 | 129 | -0.2310 | -0.1660 | +0.0651 |
| 2021Q1 | 161 | -0.1645 | -0.1685 | -0.0040 |
| 2021Q2 | 131 | +0.1517 | +0.3014 | +0.1497 |
| 2021Q3 | 125 | +0.1806 | +0.1142 | -0.0664 |
| 2021Q4 | 130 | -0.3385 | -0.3298 | +0.0087 |
| 2022Q1 | 160 | -0.2394 | -0.4025 | -0.1630 |
| 2022Q2 | 128 | +0.0329 | +0.1324 | +0.0995 |
| 2022Q3 | 134 | +0.2595 | +0.1869 | -0.0726 |
| 2022Q4 | 137 | -0.1389 | -0.1177 | +0.0212 |
| 2023Q1 | 159 | -0.0555 | -0.0650 | -0.0095 |
| 2023Q2 | 130 | -0.0443 | +0.0705 | +0.1147 |
| 2023Q3 | 131 | -0.1236 | -0.0983 | +0.0253 |
| 2023Q4 | 135 | +0.2580 | +0.3868 | +0.1287 |
| 2024Q1 | 154 | +0.0649 | -0.0120 | -0.0770 |
| 2024Q2 | 126 | +0.1211 | +0.1011 | -0.0199 |
| 2024Q3 | 130 | +0.1523 | +0.1320 | -0.0203 |
| 2024Q4 | 136 | +0.0259 | -0.0434 | -0.0693 |
| 2025Q1 | 156 | -0.0829 | -0.0286 | +0.0543 |
| 2025Q2 | 131 | +0.2789 | +0.1530 | -0.1259 |
| 2025Q3 | 134 | +0.2487 | +0.1981 | -0.0506 |
| 2025Q4 | 132 | -0.0130 | -0.1303 | -0.1173 |
| 2026Q1 | 155 | +0.3062 | +0.1772 | -0.1290 |

Sensitivity arms (mean per-fold dedup delta): rolling 8-quarter window +0.0008; rolling 16-quarter -0.0039; GLD included -0.0046; form-controlled ablation 0.006130.

## 2. The scorecard — universe block (copied from `head1_scorecard.md`)

## Universe

| block | n calls | n outperform | n underperform | n correct | hit rate | 95% Wilson interval | chance (from call counts) | no call (of which tied) | unresolved |
|---|---|---|---|---|---|---|---|---|---|
| the model (`text_and_numeric`) | 2992 | 1496 | 1496 | 1552 | 0.5187 | [0.5008, 0.5366] | 0.500 | 1489 (0) | 0 |
| numeric only (`numeric_only`) | 2991 | 1496 | 1495 | 1525 | 0.5099 | [0.4919, 0.5278] | 0.500 | 1490 (2) | 0 |
| size only (`size_only`) | 2933 | 1479 | 1454 | 1425 | 0.4859 | [0.4678, 0.5039] | 0.500 | 1548 (115) | 0 |

Chance under this call rule: 0.50 when the calls are balanced; computed from the call counts: 0.500.

Outcome mix (share of scored filings with positive excess): 0.4751. This is what the period did, not a benchmark the hit rate is measured against.

The per-company pages (139 companies, each filing's call, what the stock did, right/wrong, Wilson intervals, withheld below 6 calls) are in `data/f5/head1_scorecard.md`. They are descriptive; the inference sentence on every page applies.

## 3. Head 2 — volatility / informativeness event study

**Direction, stated:** the pre-registered hypothesis was a POSITIVE slope; the measured slope is −0.165 (wild-cluster SE 0.088), one-sided p for the pre-registered direction 0.974, two-sided p 0.0465. Read as: no evidence for the pre-registered direction; the two-sided value is reported because the pre-registration reports both, not as support.

`{"few_clusters_limitation": "40 clusters (event quarters). The wild-cluster bootstrap is approximate in this regime; the SE and p-values are reported with this limitation attached, never alone.", "intercept": 1.1622125891145847, "n_clusters": 40, "n_draws": 2000, "n_obs": 3891, "p_one_sided_positive": 0.974, "p_two_sided": 0.0465, "se_wild_cluster": 0.08763202564286716, "seed": 0, "slope": -0.1652974418593817}`

40 clusters (event quarters). The wild-cluster bootstrap is approximate in this regime; the SE and p-values are reported with this limitation attached, never alone.

## 4. Head 3 — exit prediction (scored 20 folds, censored 3, never drops a company)

| test quarter | status | n test | positives | AUC |
|---|---|---|---|---|
| 2018Q1 | SCORED | 99 | 5 | 0.711 |
| 2018Q2 | SCORED | 99 | 6 | 0.694 |
| 2018Q3 | SCORED | 99 | 4 | 0.671 |
| 2018Q4 | SCORED | 98 | 4 | 0.790 |
| 2019Q1 | SCORED | 96 | 3 | 0.792 |
| 2019Q2 | SCORED | 95 | 2 | 0.403 |
| 2019Q3 | SCORED | 99 | 4 | 0.487 |
| 2019Q4 | SCORED | 99 | 4 | 0.684 |
| 2020Q1 | SCORED | 98 | 4 | 0.758 |
| 2020Q2 | SCORED | 98 | 4 | 0.976 |
| 2020Q3 | SCORED | 99 | 1 | 0.980 |
| 2020Q4 | SCORED | 99 | 1 | 1.000 |
| 2021Q1 | NOT SCORED: the test fold has one class only (AUC undefined); prevalence reported instead. | 98 | 0 | — |
| 2021Q2 | NOT SCORED: the test fold has one class only (AUC undefined); prevalence reported instead. | 97 | 0 | — |
| 2021Q3 | NOT SCORED: the test fold has one class only (AUC undefined); prevalence reported instead. | 100 | 0 | — |
| 2021Q4 | NOT SCORED: the test fold has one class only (AUC undefined); prevalence reported instead. | 100 | 0 | — |
| 2022Q1 | NOT SCORED: the test fold has one class only (AUC undefined); prevalence reported instead. | 100 | 0 | — |
| 2022Q2 | NOT SCORED: the test fold has one class only (AUC undefined); prevalence reported instead. | 100 | 0 | — |
| 2022Q3 | NOT SCORED: the test fold has one class only (AUC undefined); prevalence reported instead. | 100 | 0 | — |
| 2022Q4 | NOT SCORED: the test fold has one class only (AUC undefined); prevalence reported instead. | 100 | 0 | — |
| 2023Q1 | NOT SCORED: the test fold has one class only (AUC undefined); prevalence reported instead. | 100 | 0 | — |
| 2023Q2 | NOT SCORED: the test fold has one class only (AUC undefined); prevalence reported instead. | 100 | 0 | — |
| 2023Q3 | SCORED | 100 | 2 | 0.520 |
| 2023Q4 | SCORED | 99 | 2 | 0.784 |
| 2024Q1 | SCORED | 99 | 2 | 0.706 |
| 2024Q2 | SCORED | 99 | 2 | 0.675 |
| 2024Q3 | SCORED | 98 | 3 | 0.600 |
| 2024Q4 | SCORED | 98 | 2 | 0.917 |
| 2025Q1 | SCORED | 98 | 4 | 0.819 |
| 2025Q2 | SCORED | 98 | 5 | 0.720 |
| 2025Q3 | CENSORED: the 4-quarter outcome window of 2025Q3 closes after the label cut 2026-08-17; counted, not scored (decision 13). | 85 | 2 | — |
| 2025Q4 | CENSORED: the 4-quarter outcome window of 2025Q4 closes after the label cut 2026-08-17; counted, not scored (decision 13). | 0 | 0 | — |
| 2026Q1 | CENSORED: the 4-quarter outcome window of 2026Q1 closes after the label cut 2026-08-17; counted, not scored (decision 13). | 0 | 0 | — |

## 5. Where everything is

`data/f5/results_head1.json` · `results_head2.json` · `results_head3.json` · `run_log.jsonl` (shas of every output) ·
`status/g3_chain_log.jsonl` · `status/PIN_SHOW_2026-11-05.txt` (the pin diff) · `head1_scorecard.md` / `.json` (private, git-excluded) ·
reviewer report `status/REVIEW_g3_run_2026-11-05.md` — DONE: pin, shas, margin, folds, purge, dedup, scorecard and heads all reproduce exactly; 2 must-fix (M1 the ratified decision-11 WITHDRAWN-guidance sensitivity arm was never built or run — recorded as a DEVIATION, to be run post-hoc-labelled in F6; M2 five tripwire tests inverted so no agent deletes the pin), 11 should (seed sensitivity: 32 of 100 nuisance seeds fail equivalence at ±0.04 though none reaches the MDE; the scorecard's Wilson interval assumes independent calls and clustered bootstraps include 0.50; head-2 direction; head-3 aggregate and screen; report_head1.md gaps; heads 2/3 missing the NEGATIVE-recall escorts), 9 notes — all carried into F6.
