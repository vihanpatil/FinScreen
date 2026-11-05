# E2 head 1 -- walk-forward text-vs-numeric screening comparison

Generated from the run's own diagnostics (2026-11-05T22:13:24+00:00 UTC, params_sha256 `9ac479818785b6fc...`, doc_sha256 `6b99f65ea1da42e8...`). No number below is hand-typed.

**Scope sentence.** No text-vs-numeric IC improvement of economically relevant size is detectable in this universe through this labeling schema, these features, this labeler, and this feature specification.

**E1 and E2 backtest numbers are numerically incomparable: E2's benchmark is the membership-dated equal-weighted average over that date's members excluding self.**

**Validation of every number below:** quarterly expanding-window walk-forward, time-ordered by public filing date, never a shuffle; training rows whose 63-session target window closes on or after the test quarter's first session are purged; company-quarter deduplicated Spearman IC is primary and the raw IC is reported beside it; per-fold values are published, never a lone point estimate.

## 1. Equivalence margin (decision 15) -- written before any per-fold delta

- status: **POWERED**, Delta = **0.04** (ladder [0.03, 0.04, 0.05], power requirement SE <= Delta/2.487)
- k = 33 folds; measured lag-1 autocorrelation of the fold deltas = -0.0418; moving-block length 1 (ceil_k13_ac1)
- SE = **0.0149** (moving-block bootstrap, 4000 resamples, seed 0); Newey-West alternative 0.0149; std/sqrt(k) = 0.0151 is recorded only to be labelled never used for inference
- implied MDE (2.8 x SE) = **0.0416**; KC3 branch: the selected margin is above the ladder's floor, so the honest MDE (0.0416) is printed beside it and no equivalence claim is read as tighter than that.
- mean fold delta (dedup) = 0.0011; 90% CI [-0.0234, 0.0256] (always printed); TOST p = 0.0045 at alpha 0.05; equivalence = True
- Every MDE here is a LOWER bound: expanding-window training sets are nested and 63-session target windows straddle fold boundaries, so effective k < nominal k.

**Zero-information noise floor (H1, re-derived on E2): |IC| ~ 0.0466-0.0488.** Read every IC below against it and against the two standing zero-information rows in §4.

## 2. Per-fold deltas, primary specification (dedup)

| test_quarter | n_test | ic_baseline | ic_block | delta |
|---|---|---|---|---|
| 2018Q1 | 144 | 0.0140 | -0.0568 | -0.0708 |
| 2018Q2 | 118 | -0.1539 | -0.1664 | -0.0125 |
| 2018Q3 | 123 | -0.3819 | -0.3737 | 0.0082 |
| 2018Q4 | 122 | -0.1080 | 0.0125 | 0.1205 |
| 2019Q1 | 149 | 0.0732 | 0.1079 | 0.0347 |
| 2019Q2 | 119 | 0.1583 | 0.1800 | 0.0217 |
| 2019Q3 | 125 | 0.0458 | -0.0064 | -0.0522 |
| 2019Q4 | 128 | 0.1425 | 0.1559 | 0.0134 |
| 2020Q1 | 152 | -0.0977 | 0.1227 | 0.2204 |
| 2020Q2 | 130 | 0.2698 | 0.3019 | 0.0321 |
| 2020Q3 | 127 | 0.2163 | 0.1945 | -0.0218 |
| 2020Q4 | 129 | -0.2310 | -0.1660 | 0.0651 |
| 2021Q1 | 161 | -0.1645 | -0.1685 | -0.0040 |
| 2021Q2 | 131 | 0.1517 | 0.3014 | 0.1497 |
| 2021Q3 | 125 | 0.1806 | 0.1142 | -0.0664 |
| 2021Q4 | 130 | -0.3385 | -0.3298 | 0.0087 |
| 2022Q1 | 160 | -0.2394 | -0.4025 | -0.1630 |
| 2022Q2 | 128 | 0.0329 | 0.1324 | 0.0995 |
| 2022Q3 | 134 | 0.2595 | 0.1869 | -0.0726 |
| 2022Q4 | 137 | -0.1389 | -0.1177 | 0.0212 |
| 2023Q1 | 159 | -0.0555 | -0.0650 | -0.0095 |
| 2023Q2 | 130 | -0.0443 | 0.0705 | 0.1147 |
| 2023Q3 | 131 | -0.1236 | -0.0983 | 0.0253 |
| 2023Q4 | 135 | 0.2580 | 0.3868 | 0.1287 |
| 2024Q1 | 154 | 0.0649 | -0.0120 | -0.0770 |
| 2024Q2 | 126 | 0.1211 | 0.1011 | -0.0199 |
| 2024Q3 | 130 | 0.1523 | 0.1320 | -0.0203 |
| 2024Q4 | 136 | 0.0259 | -0.0434 | -0.0693 |
| 2025Q1 | 156 | -0.0829 | -0.0286 | 0.0543 |
| 2025Q2 | 131 | 0.2789 | 0.1530 | -0.1259 |
| 2025Q3 | 134 | 0.2487 | 0.1981 | -0.0506 |
| 2025Q4 | 132 | -0.0130 | -0.1303 | -0.1173 |
| 2026Q1 | 155 | 0.3062 | 0.1772 | -0.1290 |

## 3. Censoring arms and the training-window sensitivity, side by side

- full window: k = 33, mean fold delta 0.0011
- post-2019Q1 sub-window: k = 29, mean fold delta -0.0003
- rolling 8-quarter training window: k = 33, mean fold delta 0.0008 -- sensitivity arm, decision 4 (owner 2026-09-11): reported beside the expanding primary, never selected
- rolling 16-quarter training window: k = 33, mean fold delta -0.0039 -- sensitivity arm, decision 4 (owner 2026-09-11): reported beside the expanding primary, never selected
- GLD-included arm: k = 33, mean fold delta -0.0046 over a frame carrying the 8 gold-ETF rows the primary excludes -- sensitivity arm, decision 2 (owner 2026-09-11): reported beside the primary, never selected

The primary training window is the EXPANDING one declared before the run; the rolling arms above are sensitivities (decision 4) and are never selected in its place. The GLD-included arm is decision 2's sensitivity and is never selected either.

## 4. Standing sections

## Zero-information benchmarks (STANDING -- read every IC above against these)

- **`size_only_rank`** -- rank by `log_total_assets` alone (one near-constant-per-company variable, zero fitting, zero text).
- **`ticker_training_mean_rank`** -- rank by the ticker's mean realized excess return over that fold's TRAINING rows (zero features; pure company persistence). Tickers unseen in training fall back to the overall training mean.

Both are computed on the RAW frame, on the SAME folds and the SAME dedup mask as the fitted models, so they are comparable across feature specifications. They are the measurement of `methodology_audit.md` §(c) C9: if a fitted model does not beat them, its IC is cross-sectional persistence, not predictive skill.

Cross-fold summary (std is the SAMPLE std, ddof=1):

| benchmark | n_folds | mean_ic_raw | std_ic_raw | mean_ic_dedup | std_ic_dedup | positive_folds_dedup |
|---|---|---|---|---|---|---|
| size_only_rank | 33 | 0.0134 | 0.1392 | 0.0191 | 0.1543 | 21 |
| ticker_training_mean_rank | 33 | 0.0436 | 0.2112 | 0.0362 | 0.2016 | 21 |

Per fold:

| benchmark | test_quarter | n_test | spearman_ic | n_test_dedup | spearman_ic_dedup |
|---|---|---|---|---|---|
| size_only_rank | 2018Q1 | 166 | -0.1884 | 144 | -0.1755 |
| ticker_training_mean_rank | 2018Q1 | 166 | 0.2664 | 144 | 0.2074 |
| size_only_rank | 2018Q2 | 162 | -0.1124 | 118 | -0.1220 |
| ticker_training_mean_rank | 2018Q2 | 162 | -0.1324 | 118 | -0.1954 |
| size_only_rank | 2018Q3 | 168 | 0.0754 | 123 | 0.0558 |
| ticker_training_mean_rank | 2018Q3 | 168 | -0.2008 | 123 | -0.2486 |
| size_only_rank | 2018Q4 | 170 | -0.2651 | 122 | -0.2686 |
| ticker_training_mean_rank | 2018Q4 | 170 | 0.1600 | 122 | 0.0932 |
| size_only_rank | 2019Q1 | 175 | 0.1502 | 149 | 0.1249 |
| ticker_training_mean_rank | 2019Q1 | 175 | 0.1457 | 149 | 0.1385 |
| size_only_rank | 2019Q2 | 167 | -0.0812 | 119 | -0.1105 |
| ticker_training_mean_rank | 2019Q2 | 167 | 0.2477 | 119 | 0.2182 |
| size_only_rank | 2019Q3 | 175 | 0.2043 | 125 | 0.2487 |
| ticker_training_mean_rank | 2019Q3 | 175 | 0.0653 | 125 | 0.0584 |
| size_only_rank | 2019Q4 | 179 | -0.1504 | 128 | -0.1396 |
| ticker_training_mean_rank | 2019Q4 | 179 | 0.2557 | 128 | 0.2531 |
| size_only_rank | 2020Q1 | 180 | -0.2358 | 152 | -0.3074 |
| ticker_training_mean_rank | 2020Q1 | 180 | 0.2339 | 152 | 0.1849 |
| size_only_rank | 2020Q2 | 187 | 0.0035 | 130 | -0.0009 |
| ticker_training_mean_rank | 2020Q2 | 187 | 0.2316 | 130 | 0.2364 |
| size_only_rank | 2020Q3 | 190 | -0.0005 | 127 | 0.0040 |
| ticker_training_mean_rank | 2020Q3 | 190 | 0.2564 | 127 | 0.2519 |
| size_only_rank | 2020Q4 | 193 | 0.1962 | 129 | 0.2174 |
| ticker_training_mean_rank | 2020Q4 | 193 | -0.2160 | 129 | -0.1847 |
| size_only_rank | 2021Q1 | 194 | 0.2137 | 161 | 0.2518 |
| ticker_training_mean_rank | 2021Q1 | 194 | -0.1859 | 161 | -0.1424 |
| size_only_rank | 2021Q2 | 188 | -0.1772 | 131 | -0.1303 |
| ticker_training_mean_rank | 2021Q2 | 188 | 0.2643 | 131 | 0.2460 |
| size_only_rank | 2021Q3 | 188 | -0.0464 | 125 | 0.0013 |
| ticker_training_mean_rank | 2021Q3 | 188 | -0.0047 | 125 | 0.0707 |
| size_only_rank | 2021Q4 | 190 | 0.1832 | 130 | 0.1698 |
| ticker_training_mean_rank | 2021Q4 | 190 | -0.4464 | 130 | -0.4375 |
| size_only_rank | 2022Q1 | 191 | -0.0271 | 160 | 0.0086 |
| ticker_training_mean_rank | 2022Q1 | 191 | -0.4585 | 160 | -0.4506 |
| size_only_rank | 2022Q2 | 193 | 0.0846 | 128 | 0.0892 |
| ticker_training_mean_rank | 2022Q2 | 193 | -0.0513 | 128 | -0.0836 |
| size_only_rank | 2022Q3 | 197 | 0.0570 | 134 | 0.0973 |
| ticker_training_mean_rank | 2022Q3 | 197 | 0.0772 | 134 | 0.0721 |
| size_only_rank | 2022Q4 | 196 | -0.2358 | 137 | -0.2390 |
| ticker_training_mean_rank | 2022Q4 | 196 | -0.1465 | 137 | -0.1240 |
| size_only_rank | 2023Q1 | 194 | -0.0304 | 159 | -0.1156 |
| ticker_training_mean_rank | 2023Q1 | 194 | 0.1264 | 159 | 0.0684 |
| size_only_rank | 2023Q2 | 195 | 0.0276 | 130 | 0.0717 |
| ticker_training_mean_rank | 2023Q2 | 195 | 0.2774 | 130 | 0.2611 |
| size_only_rank | 2023Q3 | 190 | -0.0788 | 131 | -0.1617 |
| ticker_training_mean_rank | 2023Q3 | 190 | 0.1275 | 131 | 0.0789 |
| size_only_rank | 2023Q4 | 192 | 0.0397 | 135 | 0.0880 |
| ticker_training_mean_rank | 2023Q4 | 192 | 0.2776 | 135 | 0.2663 |
| size_only_rank | 2024Q1 | 193 | 0.0769 | 154 | 0.0703 |
| ticker_training_mean_rank | 2024Q1 | 193 | 0.1911 | 154 | 0.2064 |
| size_only_rank | 2024Q2 | 189 | 0.0604 | 126 | 0.1085 |
| ticker_training_mean_rank | 2024Q2 | 189 | -0.1182 | 126 | -0.0508 |
| size_only_rank | 2024Q3 | 192 | 0.0964 | 130 | 0.0893 |
| ticker_training_mean_rank | 2024Q3 | 192 | -0.0393 | 130 | -0.0073 |
| size_only_rank | 2024Q4 | 198 | 0.0704 | 136 | 0.1119 |
| ticker_training_mean_rank | 2024Q4 | 198 | 0.0481 | 136 | -0.0016 |
| size_only_rank | 2025Q1 | 194 | -0.0105 | 156 | -0.0222 |
| ticker_training_mean_rank | 2025Q1 | 194 | 0.0358 | 156 | 0.0532 |
| size_only_rank | 2025Q2 | 195 | 0.1753 | 131 | 0.2015 |
| ticker_training_mean_rank | 2025Q2 | 195 | 0.1776 | 131 | 0.1775 |
| size_only_rank | 2025Q3 | 201 | 0.2469 | 134 | 0.2787 |
| ticker_training_mean_rank | 2025Q3 | 201 | 0.1395 | 134 | 0.1336 |
| size_only_rank | 2025Q4 | 202 | 0.0278 | 132 | 0.0564 |
| ticker_training_mean_rank | 2025Q4 | 202 | -0.3206 | 132 | -0.3048 |
| size_only_rank | 2026Q1 | 200 | 0.0929 | 155 | 0.0800 |
| ticker_training_mean_rank | 2026Q1 | 200 | 0.1525 | 155 | 0.1489 |

**`ticker_training_mean_rank` uses training-row targets**, which are 63-trading-day forward windows that resolve after the train/test boundary -- exactly the same non-embargoed-label property the fitted models have. It is not cleaner than they are, and the comparison is like-for-like on that axis.

## Within-fold bootstrap noise anchor (STANDING) -- PRIMARY -- PIT trailing cross-sectional percentile ranks (180d window)

Each fold's fitted predictions are held FIXED and only that fold's deduplicated test rows are resampled with replacement (4000 resamples/fold, `numpy.random.default_rng`, seed base 0); the delta is recomputed on each resample. This estimates the sampling component of the delta from ~40 rows x thousands of resamples per fold, instead of from the standard deviation of six numbers.

| test_quarter | n_test_dedup | fold_delta_dedup | bootstrap_sd_of_delta | n_degenerate_resamples |
|---|---|---|---|---|
| 2018Q1 | 144 | -0.0237 | 0.0460 | 0 |
| 2018Q2 | 118 | 0.0050 | 0.0607 | 0 |
| 2018Q3 | 123 | -0.0646 | 0.0498 | 0 |
| 2018Q4 | 122 | 0.0604 | 0.0624 | 0 |
| 2019Q1 | 149 | 0.0189 | 0.0587 | 0 |
| 2019Q2 | 119 | 0.0509 | 0.0631 | 0 |
| 2019Q3 | 125 | -0.0117 | 0.0588 | 0 |
| 2019Q4 | 128 | 0.0938 | 0.0560 | 0 |
| 2020Q1 | 152 | 0.0862 | 0.0613 | 0 |
| 2020Q2 | 130 | -0.0194 | 0.0650 | 0 |
| 2020Q3 | 127 | -0.1585 | 0.0768 | 0 |
| 2020Q4 | 129 | -0.0403 | 0.0470 | 0 |
| 2021Q1 | 161 | 0.0372 | 0.0607 | 0 |
| 2021Q2 | 131 | 0.0745 | 0.0747 | 0 |
| 2021Q3 | 125 | 0.0752 | 0.0774 | 0 |
| 2021Q4 | 130 | 0.1492 | 0.0612 | 0 |
| 2022Q1 | 160 | -0.0144 | 0.0605 | 0 |
| 2022Q2 | 128 | -0.0083 | 0.0692 | 0 |
| 2022Q3 | 134 | -0.0519 | 0.0773 | 0 |
| 2022Q4 | 137 | 0.0072 | 0.0530 | 0 |
| 2023Q1 | 159 | -0.0034 | 0.0398 | 0 |
| 2023Q2 | 130 | 0.0962 | 0.0956 | 0 |
| 2023Q3 | 131 | 0.1713 | 0.0594 | 0 |
| 2023Q4 | 135 | 0.1865 | 0.0631 | 0 |
| 2024Q1 | 154 | 0.0116 | 0.0575 | 0 |
| 2024Q2 | 126 | 0.0367 | 0.0748 | 0 |
| 2024Q3 | 130 | 0.0149 | 0.0646 | 0 |
| 2024Q4 | 136 | -0.0543 | 0.0638 | 0 |
| 2025Q1 | 156 | 0.0225 | 0.0588 | 0 |
| 2025Q2 | 131 | -0.0478 | 0.0683 | 0 |
| 2025Q3 | 134 | -0.0769 | 0.0919 | 0 |
| 2025Q4 | 132 | 0.0284 | 0.0745 | 0 |
| 2026Q1 | 155 | -0.1159 | 0.0560 | 0 |

- mean within-fold bootstrap SD of the delta = **0.0639** (RMS, the variance-decomposition-correct anchor = **0.0649**)
- cross-fold SAMPLE std of the 33 fold deltas (ddof=1) = **0.0760**; 95% chi-square CI [0.0612, 0.1006]
- the same quantity under the PUBLISHED population convention (ddof=0), for continuity with pre-2026-08-25 reports = 0.0749
- implied regime/training floor SD = sqrt(max(0, cross_var - mean within-fold var)) = **0.0396**
- cross-fold variance / within-fold bootstrap variance = 1.371; one-sided chi-square p(spread > sampling) = 0.079, p(spread < sampling) = 0.921
- naive SE of the cross-fold mean (std/sqrt(k), assumes independent folds) = 0.0132

**How to read the floor.** A floor of 0 would mean the observed fold-to-fold spread is fully accounted for by test-set sampling noise, with nothing left over for a market-regime component -- i.e. adding COMPANIES buys power. A floor above 0 means part of the spread is NOT sampling and is divided down only by more TEST QUARTERS, never by more companies (`data/expansion_recon_2026-08-20.json` caveat (1)). **Read the chi-square p-values above before reading the point estimate.** It is a truncated-at-zero estimator resting on a cross-fold std with k-1 degrees of freedom; at k = 6 neither tail is anywhere near significant, so a measured floor of 0.0000 does NOT establish that the floor is absent and a measured floor of ~0.10 does NOT establish that it is present. On E1 the two pre-registered specifications give 0.0000 and 0.0992 on the same folds -- which is the honest answer: at 6 folds the floor is unidentified, and recon caveat (1) is NOT resolved by this estimator once the feature specification is allowed to vary.

**Fold non-independence is NOT in any of these numbers.** The naive SE assumes independent fold deltas; expanding-window training sets are nested and 63-trading-day target windows straddle fold boundaries, so effective k < nominal k and every MDE derived from this anchor is a LOWER BOUND. At E2's ~26 folds the lag-1 autocorrelation of fold deltas becomes measurable for the first time and must be measured, not assumed.

## Within-fold bootstrap noise anchor (STANDING) -- SECONDARY (mandatory) -- raw levels, as shipped in E1

Each fold's fitted predictions are held FIXED and only that fold's deduplicated test rows are resampled with replacement (4000 resamples/fold, `numpy.random.default_rng`, seed base 0); the delta is recomputed on each resample. This estimates the sampling component of the delta from ~40 rows x thousands of resamples per fold, instead of from the standard deviation of six numbers.

| test_quarter | n_test_dedup | fold_delta_dedup | bootstrap_sd_of_delta | n_degenerate_resamples |
|---|---|---|---|---|
| 2018Q1 | 144 | -0.0462 | 0.0563 | 0 |
| 2018Q2 | 118 | 0.0104 | 0.0611 | 0 |
| 2018Q3 | 123 | -0.0529 | 0.0433 | 0 |
| 2018Q4 | 122 | -0.0419 | 0.0648 | 0 |
| 2019Q1 | 149 | -0.0352 | 0.0548 | 0 |
| 2019Q2 | 119 | -0.0282 | 0.0671 | 0 |
| 2019Q3 | 125 | 0.0230 | 0.0607 | 0 |
| 2019Q4 | 128 | -0.1095 | 0.0524 | 0 |
| 2020Q1 | 152 | -0.0243 | 0.0422 | 0 |
| 2020Q2 | 130 | -0.0583 | 0.0710 | 0 |
| 2020Q3 | 127 | -0.1151 | 0.0791 | 0 |
| 2020Q4 | 129 | -0.1303 | 0.0622 | 0 |
| 2021Q1 | 161 | -0.0219 | 0.0651 | 0 |
| 2021Q2 | 131 | -0.0246 | 0.0639 | 0 |
| 2021Q3 | 125 | 0.0896 | 0.0478 | 0 |
| 2021Q4 | 130 | 0.0107 | 0.0612 | 0 |
| 2022Q1 | 160 | -0.0563 | 0.0551 | 0 |
| 2022Q2 | 128 | 0.0078 | 0.0510 | 0 |
| 2022Q3 | 134 | 0.1035 | 0.0645 | 0 |
| 2022Q4 | 137 | -0.0051 | 0.0549 | 0 |
| 2023Q1 | 159 | 0.0671 | 0.0498 | 0 |
| 2023Q2 | 130 | 0.0251 | 0.0868 | 0 |
| 2023Q3 | 131 | 0.0249 | 0.0756 | 0 |
| 2023Q4 | 135 | -0.0036 | 0.0480 | 0 |
| 2024Q1 | 154 | 0.0026 | 0.0602 | 0 |
| 2024Q2 | 126 | -0.0208 | 0.0626 | 0 |
| 2024Q3 | 130 | -0.0575 | 0.0674 | 0 |
| 2024Q4 | 136 | 0.1484 | 0.0696 | 0 |
| 2025Q1 | 156 | 0.0031 | 0.0585 | 0 |
| 2025Q2 | 131 | -0.0243 | 0.0820 | 0 |
| 2025Q3 | 134 | -0.0323 | 0.0677 | 0 |
| 2025Q4 | 132 | -0.0176 | 0.0521 | 0 |
| 2026Q1 | 155 | -0.0807 | 0.0519 | 0 |

- mean within-fold bootstrap SD of the delta = **0.0609** (RMS, the variance-decomposition-correct anchor = **0.0618**)
- cross-fold SAMPLE std of the 33 fold deltas (ddof=1) = **0.0592**; 95% chi-square CI [0.0476, 0.0783]
- the same quantity under the PUBLISHED population convention (ddof=0), for continuity with pre-2026-08-25 reports = 0.0583
- implied regime/training floor SD = sqrt(max(0, cross_var - mean within-fold var)) = **0.0000**
- cross-fold variance / within-fold bootstrap variance = 0.917; one-sided chi-square p(spread > sampling) = 0.602, p(spread < sampling) = 0.398
- naive SE of the cross-fold mean (std/sqrt(k), assumes independent folds) = 0.0103

**How to read the floor.** A floor of 0 would mean the observed fold-to-fold spread is fully accounted for by test-set sampling noise, with nothing left over for a market-regime component -- i.e. adding COMPANIES buys power. A floor above 0 means part of the spread is NOT sampling and is divided down only by more TEST QUARTERS, never by more companies (`data/expansion_recon_2026-08-20.json` caveat (1)). **Read the chi-square p-values above before reading the point estimate.** It is a truncated-at-zero estimator resting on a cross-fold std with k-1 degrees of freedom; at k = 6 neither tail is anywhere near significant, so a measured floor of 0.0000 does NOT establish that the floor is absent and a measured floor of ~0.10 does NOT establish that it is present. On E1 the two pre-registered specifications give 0.0000 and 0.0992 on the same folds -- which is the honest answer: at 6 folds the floor is unidentified, and recon caveat (1) is NOT resolved by this estimator once the feature specification is allowed to vary.

**Fold non-independence is NOT in any of these numbers.** The naive SE assumes independent fold deltas; expanding-window training sets are nested and 63-trading-day target windows straddle fold boundaries, so effective k < nominal k and every MDE derived from this anchor is a LOWER BOUND. At E2's ~26 folds the lag-1 autocorrelation of fold deltas becomes measurable for the first time and must be measured, not assumed.

## Label-embargo census (fold-structure convention, measured not assumed)

The walk-forward split is on `filing_date` only, so training rows filed shortly before a fold boundary carry 63-trading-day forward labels that RESOLVE inside the test quarter. That is not feature look-ahead -- no test-row feature or test-row label enters training, and `assert_no_fold_leakage()` is correct to pass -- but there is no embargo/purge, and the population has never been stated. It is stated here:

| test_quarter | n_train | n_train_labels_resolving_in_or_after_test_quarter | share_non_embargoed |
|---|---|---|---|
| 2018Q1 | 844 | 0 | 0.0000 |
| 2018Q2 | 1010 | 0 | 0.0000 |
| 2018Q3 | 1174 | 0 | 0.0000 |
| 2018Q4 | 1338 | 0 | 0.0000 |
| 2019Q1 | 1507 | 0 | 0.0000 |
| 2019Q2 | 1677 | 0 | 0.0000 |
| 2019Q3 | 1850 | 0 | 0.0000 |
| 2019Q4 | 2019 | 0 | 0.0000 |
| 2020Q1 | 2194 | 0 | 0.0000 |
| 2020Q2 | 2373 | 0 | 0.0000 |
| 2020Q3 | 2553 | 0 | 0.0000 |
| 2020Q4 | 2739 | 0 | 0.0000 |
| 2021Q1 | 2929 | 0 | 0.0000 |
| 2021Q2 | 3122 | 0 | 0.0000 |
| 2021Q3 | 3315 | 0 | 0.0000 |
| 2021Q4 | 3503 | 0 | 0.0000 |
| 2022Q1 | 3691 | 0 | 0.0000 |
| 2022Q2 | 3881 | 0 | 0.0000 |
| 2022Q3 | 4074 | 0 | 0.0000 |
| 2022Q4 | 4267 | 0 | 0.0000 |
| 2023Q1 | 4463 | 0 | 0.0000 |
| 2023Q2 | 4660 | 0 | 0.0000 |
| 2023Q3 | 4854 | 0 | 0.0000 |
| 2023Q4 | 5048 | 0 | 0.0000 |
| 2024Q1 | 5238 | 0 | 0.0000 |
| 2024Q2 | 5431 | 0 | 0.0000 |
| 2024Q3 | 5624 | 0 | 0.0000 |
| 2024Q4 | 5813 | 0 | 0.0000 |
| 2025Q1 | 6005 | 0 | 0.0000 |
| 2025Q2 | 6203 | 0 | 0.0000 |
| 2025Q3 | 6397 | 0 | 0.0000 |
| 2025Q4 | 6592 | 0 | 0.0000 |
| 2026Q1 | 6792 | 0 | 0.0000 |

Pooled across folds: **0 of 123180 training labels (0.0%)** resolve on or after their fold's test quarter begins. The target is an EXCESS return against a same-window universe average, which differences out the market-wide component of that overlap but not a company-specific one. Whether to embargo is a G3 pre-registration decision; this report only measures it.

## 5. Nuisance seed band and LOCO

- seed band over 100 nuisance seeds: cross-fold mean delta in [-0.0141, 0.0347] (sd 0.0096). Nuisance band over the model seed only; it is a spread of the SAME estimand, not a sampling distribution and not a confidence interval.
- LOCO: 1426 refits over folds [0, 6, 13, 19, 26, 32] (DESCRIPTIVE ONLY -- no per-CIK inference at this fold count (decision 14).)

## 6. Label-quality caveats (G2, read from results_g2.json)

Provenance: model-consensus agreement (blind rater + adjudicator, both Claude-family) with owner rulings superseding on the escalated subset; NOT human validation of ground truth (HANDOFF §3).

- **sentiment**: 0.8694 [0.8293, 0.9013] (n = 337) -- INDETERMINATE
- **guidance_direction**: 0.9664 [0.9168, 0.9869] (n = 119) -- PASS
- guidance ACTIVE precision (mandatory escort): 0.6867 [0.5817, 0.7755] (n_eff 84.77)
- guidance false-NONE rate: 0.0000 [0.0000, 0.0458] (n = 80)
- red flags: exploratory / disclosure-only (owner ruling 2026-08-27); this pass cannot change it.

## 7. Historical scorecard (decision 3, pre-registration §14)

Built from this run's own out-of-fold predictions on the `pit_trailing_rank` arm's `dedup` rows: 4481 filings, 139 companies, 33 test quarters. Call rule `tercile_within_test_quarter`, tie rule `average_rank_straddle_no_call`. Full page: `data/f5/head1_scorecard.md`.

| block | n_calls | n_outperform | n_underperform | n_correct | hit_rate | wilson_lo | wilson_hi | chance_from_call_counts | n_no_call | n_tied_no_call | n_unresolved |
|---|---|---|---|---|---|---|---|---|---|---|---|
| text_and_numeric | 2992 | 1496 | 1496 | 1552 | 0.5187 | 0.5008 | 0.5366 | 0.5000 | 1489 | 0 | 0 |
| numeric_only | 2991 | 1496 | 1495 | 1525 | 0.5099 | 0.4919 | 0.5278 | 0.5000 | 1490 | 2 | 0 |
| size_only | 2933 | 1479 | 1454 | 1425 | 0.4859 | 0.4678 | 0.5039 | 0.4999 | 1548 | 115 | 0 |

Chance under this call rule: 0.50 when the calls are balanced; computed from the call counts: 0.500.

Outcome mix (share of scored filings with positive excess): 0.4751 -- what the period did, NOT the yardstick the hit rate is read against.

**Hit rates are descriptive. The inference is the pre-registered IC margin ladder (§1, decision 15); a per-company hit rate over at most 33 quarters has a wide interval and proves nothing on its own.**

Prices: the 2026-08-24 Yahoo snapshot, split-adjusted only, 31 of 244 universe members without usable prices; peers = the equal-weighted universe average excluding the company. Not advice; no trade is recommended; owner's own use.

_Research screening only; no expected return, no trade._

