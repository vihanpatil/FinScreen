# F6: the E2 negative result and its failure taxonomy

**Status: F6 write-up, 2026-11-05, main-session document; reviewer pass applied 2026-11-05 (REVIEW_f6); Gate G4 given 2026-11-05 (owner, verbatim: "accept g4"; HANDOFF §3). E2 closed.**

This is a private research record. It quotes only universe-level scorecard numbers (the block committed as `results_head1.json` `scorecard_summary`), and no per-company row appears here. Nothing in it is advice, a forecast or a return claim. It is not public copy: the legal copy rules in `site/STORYBOARD.md` ("Legal baseline") govern every public surface, and "call" below is only the pre-registered §14 term for a tercile label. Two standing rules apply to every line. First, model-rater agreement is **model consensus, not human validation of ground truth** (`G3_PREREGISTRATION.md` §11, "Model-rater epistemics"). Second, *"E1 and E2 backtest numbers are numerically incomparable: E2's benchmark is the membership-dated equal-weighted average over that date's members excluding self"* (`results_head1.json` `scope.e1_e2_incomparable`). E1 appears below only as a cause in the taxonomy, never as a number set against E2's.

Source tags: **[R1]** `data/f5/results_head1.json` · **[R2]** `data/f5/results_head2.json` · **[R3]** `data/f5/results_head3.json` · **[PR]** `data/f5/G3_PREREGISTRATION.md` · **[REV]** `data/f5/status/REVIEW_g3_run_2026-11-05.md` · **[CEN]** `data/f5/census_e2.json` and `data/f5/status/STEP2_census_e2.md` · **[SC]** `data/f5/head1_scorecard.md` lines 1–34 · **[D11]** `data/f5/sensitivity_decision11.json` · **[G2]** `data/f4/g2/G2_FINAL_REPORT.md` · **[REV6]** `data/f5/status/REVIEW_f6_2026-11-05.md` · **[F6A]** `data/f5/status/F6A_code_2026-11-05.md`. Where a number is my own arithmetic on a file's values, the line says "(arithmetic here)".

## §0 What was asked, what came back, what the rule does with it

E2 asked one question. Take 139 large US companies (GLD excluded), 33 walk-forward test quarters (2018Q1–2026Q1) and 4,481 deduplicated test filings. Does adding features read from the companies' SEC filings by the local labeler (sentiment, guidance, year-over-year novelty, document embeddings) improve how well a fitted model ranks the companies by their 63-session return in excess of their peers, compared with the same model fitted on numeric fundamentals alone? [R1 `frame`, `folds`; REV §2]. The pre-registration fixed the form of the answer before any fit ran. The primary metric is the cross-fold mean of the per-fold deduplicated Spearman IC delta (text+numeric minus numeric-only). The equivalence margin is the smallest of 0.03 / 0.04 / 0.05 that the measured SE supports (SE ≤ Δ/2.487); if none qualifies, the result is UNPOWERED. §13 then maps the outcome to a branch [PR §1, §13]. The owner ratified the document with the word *"ratify"* on 2026-11-05 (HANDOFF §3, 2026-11-05), and the run started at 22:13:24 UTC that day [R1 `run`]. It came back with a mean delta of **+0.0011**, SE 0.0149 and 90% CI **[−0.0234, +0.0256]**. The margin selected was **0.04** (0.03 was not supportable), status **POWERED**, TOST equivalence inside ±0.04 (p 0.0045) at seed 0, though about 32 of 100 nuisance seeds would not reach equivalence (an approximate count; every seed closes identically, §1.4), honest MDE **0.0416** [R1 `margin`]. The ratified §13 maps this to the **Bounded null** row: *"text is not used as a signal; the study is written up and closed (F6 negative result + failure taxonomy; pipeline archived as asset)"*. Option 1 adds *"proceed to app direction"* [PR §13]. That outcome-map row is built on the owner's 2026-09-11 sentence, *"A positive proceeds to the signal program and null should not be used as signal. I agree with this."* [PR §13] marks that reading ⚠ INTERPRETED, and the 2026-11-05 "ratify" confirmed it. This document is the write-up the row names, and nothing in it moves the branch. In plain words: in this universe, through this labeler and these features, adding the text did not detectably change ranking quality. An improvement of 0.04 IC or more lies outside the 90% interval. The smallest effect the design could reliably detect is 0.0416, and even that is a lower bound (§1.1). This is not a finding that filing text carries no information in general (§3).

## §1 The result

### 1.1 The margin ladder [R1 `margin`]

| quantity | value |
|---|---|
| folds | 33 (2018Q1–2026Q1); 4,481 dedup test rows, 118–161 per fold |
| mean per-fold dedup IC delta | **+0.0011** |
| measured lag-1 autocorrelation of fold deltas → block length | −0.0418 → 1 (`ceil_k13_ac1`) |
| SE, block bootstrap (4,000 resamples, seed 0) | 0.01487 (Newey–West alternative 0.01489; `std/√k` 0.01512, "never used for inference") |
| rung 0.03 | needs SE ≤ 0.01206: **not satisfied** |
| rung 0.04 | needs SE ≤ 0.01608: satisfied → **selected** |
| 90% CI (normal reference) | **[−0.0234, +0.0256]** |
| TOST at ±0.04 | equivalence true at seed 0; p_lower 0.0029, p_upper 0.0045. About 32 of 100 nuisance seeds would not reach equivalence (approximate); all close identically (§1.4) |
| status; honest MDE (2.8 × SE) | **POWERED; 0.0416**, KC3 branch |

Two caveats from the results file travel with this line. The KC3 note: *"the selected margin is above the ladder's floor, so the honest MDE (0.0416) is printed beside it and no equivalence claim is read as tighter than that."* The non-independence note: *"Every MDE here is a LOWER bound: expanding-window training sets are nested and 63-session target windows straddle fold boundaries, so effective k < nominal k."* So the honest reading is this: the margin is 0.04, the run can detect about 0.042 at best, and the true detection limit is somewhat higher by an amount this run does not measure. For context, the pre-run census projected SE 0.0108 (MDE 0.0303) for uncorrelated fold deltas and 0.0146 (MDE 0.0409) at an assumed fold correlation of 0.3 [CEN `section_2_mde_decision_15_KC3.at_measured_n_dd.default_33`]. The measured SE landed near the second projection, even though the measured lag-1 autocorrelation was close to zero. Every implied-floor projection was UNPOWERED [PR §13, KC3 note], and the run did not land on any of them. The reviewer reproduced the mean, the SE to the last digit, the ladder, the CI and the p-values. Bootstrap seeds 1–50 give SEs of 0.01467–0.01520, and every one selects 0.04 [REV §2, "Margin"].

### 1.2 Per-fold deltas, all 33 [R1 `per_fold_primary_delta_dedup`; `standing.zero_information_per_fold`]

These use the primary spec (`pit_trailing_rank`) on dedup rows. The last two columns are the pre-registered zero-information benchmarks on the same rows, with no model and no text: the rank of log total assets, and each company's own training-period mean target.

| test quarter | n dedup | IC numeric-only | IC text+numeric | delta | zero-info: size rank | zero-info: ticker training mean |
|---|---|---|---|---|---|---|
| 2018Q1 | 144 | +0.0140 | -0.0568 | -0.0708 | -0.1755 | +0.2074 |
| 2018Q2 | 118 | -0.1539 | -0.1664 | -0.0125 | -0.1220 | -0.1954 |
| 2018Q3 | 123 | -0.3819 | -0.3737 | +0.0082 | +0.0558 | -0.2486 |
| 2018Q4 | 122 | -0.1080 | +0.0125 | +0.1205 | -0.2686 | +0.0932 |
| 2019Q1 | 149 | +0.0732 | +0.1079 | +0.0347 | +0.1249 | +0.1385 |
| 2019Q2 | 119 | +0.1583 | +0.1800 | +0.0217 | -0.1105 | +0.2182 |
| 2019Q3 | 125 | +0.0458 | -0.0064 | -0.0522 | +0.2487 | +0.0584 |
| 2019Q4 | 128 | +0.1425 | +0.1559 | +0.0134 | -0.1396 | +0.2531 |
| 2020Q1 | 152 | -0.0977 | +0.1227 | +0.2204 | -0.3074 | +0.1849 |
| 2020Q2 | 130 | +0.2698 | +0.3019 | +0.0321 | -0.0009 | +0.2364 |
| 2020Q3 | 127 | +0.2163 | +0.1945 | -0.0218 | +0.0040 | +0.2519 |
| 2020Q4 | 129 | -0.2310 | -0.1660 | +0.0651 | +0.2174 | -0.1847 |
| 2021Q1 | 161 | -0.1645 | -0.1685 | -0.0040 | +0.2518 | -0.1424 |
| 2021Q2 | 131 | +0.1517 | +0.3014 | +0.1497 | -0.1303 | +0.2460 |
| 2021Q3 | 125 | +0.1806 | +0.1142 | -0.0664 | +0.0013 | +0.0707 |
| 2021Q4 | 130 | -0.3385 | -0.3298 | +0.0087 | +0.1698 | -0.4375 |
| 2022Q1 | 160 | -0.2394 | -0.4025 | -0.1630 | +0.0086 | -0.4506 |
| 2022Q2 | 128 | +0.0329 | +0.1324 | +0.0995 | +0.0892 | -0.0836 |
| 2022Q3 | 134 | +0.2595 | +0.1869 | -0.0726 | +0.0973 | +0.0721 |
| 2022Q4 | 137 | -0.1389 | -0.1177 | +0.0212 | -0.2390 | -0.1240 |
| 2023Q1 | 159 | -0.0555 | -0.0650 | -0.0095 | -0.1156 | +0.0684 |
| 2023Q2 | 130 | -0.0443 | +0.0705 | +0.1147 | +0.0717 | +0.2611 |
| 2023Q3 | 131 | -0.1236 | -0.0983 | +0.0253 | -0.1617 | +0.0789 |
| 2023Q4 | 135 | +0.2580 | +0.3868 | +0.1287 | +0.0880 | +0.2663 |
| 2024Q1 | 154 | +0.0649 | -0.0120 | -0.0770 | +0.0703 | +0.2064 |
| 2024Q2 | 126 | +0.1211 | +0.1011 | -0.0199 | +0.1085 | -0.0508 |
| 2024Q3 | 130 | +0.1523 | +0.1320 | -0.0203 | +0.0893 | -0.0073 |
| 2024Q4 | 136 | +0.0259 | -0.0434 | -0.0693 | +0.1119 | -0.0016 |
| 2025Q1 | 156 | -0.0829 | -0.0286 | +0.0543 | -0.0222 | +0.0532 |
| 2025Q2 | 131 | +0.2789 | +0.1530 | -0.1259 | +0.2015 | +0.1775 |
| 2025Q3 | 134 | +0.2487 | +0.1981 | -0.0506 | +0.2787 | +0.1336 |
| 2025Q4 | 132 | -0.0130 | -0.1303 | -0.1173 | +0.0564 | -0.3048 |
| 2026Q1 | 155 | +0.3062 | +0.1772 | -0.1290 | +0.0800 | +0.1489 |

16 of 33 deltas are positive. The range runs from −0.1630 (2022Q1) to +0.2204 (2020Q1) (arithmetic here; it matches REV N3).

### 1.3 Every sensitivity arm beside the primary [R1]

Each value is the mean of per-fold dedup deltas over 33 folds, unless stated otherwise. No arm is a selectable primary, and no arm has its own SE or margin.

| arm (results key) | mean delta |
|---|---|
| **primary**: PIT trailing ranks, dedup | **+0.0011** |
| primary spec, raw (non-dedup) rows (`…pit_trailing_rank__raw__text_and_numeric`) | +0.0050 |
| `raw_levels` mandatory secondary, dedup / raw rows | −0.0013 / +0.0072 |
| no same-day comparators (`include_same_day=False`), dedup / raw rows | +0.0081 / +0.0087 |
| no-overlap (evaluation-side: test rows with no labeler-training overlap, 2,694 rows), dedup | −0.0061 |
| no-overlap under `raw_levels` / under no-same-day | −0.0103 / −0.0002 |
| rolling 8-quarter / 16-quarter training window (`per_fold_delta__rolling_8q/16q`) | +0.0008 / −0.0039 |
| GLD restored as a subject, 8 rows (`per_fold_delta__gld_included`) | −0.0046 |
| form-controlled ablation, 10-K/10-Q only, 3,497 rows (`form_controlled_ablation`) | +0.0061 |
| censoring arm: post-2019 sub-window, 29 folds from 2019Q1, same fits (`censoring_arms`) | −0.0003 |

The confirmatory-block arm means span −0.0103 to +0.0087 (arithmetic here), so every arm sits well inside ±0.04. The pre-registration says the ranks-primary rationale *"fails re-measurement"*, so raw levels carry equal weight in this write-up [PR §1], and raw levels are null too. The exploratory block is discussed in §3(c).

### 1.4 Seed band [R1 `seed_band`; REV S1]

The primary uses model seed 0, as pre-registered. Across 100 nuisance seeds (1–100), the per-seed means run from −0.0141 to +0.0347 (sd 0.0096, median +0.0106), and 84 of the 100 sit above seed 0 (arithmetic here; it matches REV). In the results file's words, the band is *"a spread of the SAME estimand, not a sampling distribution and not a confidence interval."* At the run's SE, equivalence at ±0.04 needs |mean| < 0.0155. **32 of 100 seeds would fail that test** and land in the ambiguous-inside-MDE branch. This count is approximate: per-seed SEs are not stored, so the seed-0 SE is assumed for every seed. **No seed reaches the MDE** (max 0.0347 < 0.0416). §13 says the ambiguous branch is *"CLOSED identically to the null"*, so every seed leads to "text is not used as a signal". The closure holds across seeds. The word "equivalence" does not.

### 1.5 Leave-one-company-out [R1 `loco`; REV N2, N4]

This is descriptive only (*"no per-CIK inference at this fold count (decision 14)"*). It covers six folds (2018Q1, 2019Q3, 2021Q2, 2022Q4, 2024Q3, 2026Q1) and 1,426 refits. The pre-registration's "1,438" counted GLD's rows [REV N2]. Removing a single company moves a fold's delta across a span of up to about 0.41 within one fold (2024Q3: −0.1633 to +0.2495; 2019Q3: −0.3140 to +0.0789). Across all six folds the LOCO deltas run from −0.3140 to +0.3568. The LOCO medians do not sit on the primary fold delta: for 2021Q2 the median is +0.2133 against a primary of +0.1497, and for 2024Q3 it is +0.0840 against −0.0203. This run does not determine why. Adding GLD's 8 rows moves per-fold deltas by a mean |Δ| of 0.055, with a maximum of 0.160 [REV N4]. Individual fold deltas are therefore not interpretable, and the cross-fold SE already carries this variance.

### 1.6 One-fold fragility [REV N3]

2020Q1 contributes +0.2204. Without that fold the mean is −0.0058 over 32 folds (arithmetic here; it matches REV). "+0.0011" must not be read as weakly positive.

### 1.7 Zero-information benchmarks [R1 `standing.zero_information_summary`, `noise_floor_h1`]

| | mean dedup IC, 33 folds | folds positive |
|---|---|---|
| fitted numeric-only | +0.0251 | 19 |
| fitted text+numeric | +0.0262 | 18 |
| zero-info: size rank | +0.0191 | 21 |
| zero-info: ticker training mean | +0.0362 | 21 |

The fitted-block rows are arithmetic here over `per_fold_primary_delta_dedup`. Fold by fold, text+numeric exceeds the ticker-mean benchmark in 16 of 33 folds, and numeric-only does so in 14 (arithmetic here). The H1 zero-information noise floor printed beside every IC is |IC| 0.0466–0.0488 (2.8 × the T0 placebo cross-period SE). Neither fitted block's mean IC exceeds the ticker-mean benchmark, and both sit below the noise floor. E2's question was the delta, not the level, and no test of the levels was pre-registered. Still, a reader should know where the levels sit.

### 1.8 Decision-11 arm: WITHDRAWN guidance excluded [D11]

The file's label, verbatim: *"EXECUTED AFTER THE PRIMARY WAS SEEN (2026-11-05); pre-registered arm run late; can never be selected as the primary."* **The 43-row definition is a POST-HOC operationalization.** The ratified row states the count as *"35 of 7,389 rows"* [PR, WITHDRAWN-guidance row], and the pre-registration says *"Any amendment after the first E2 IC exists is labelled **POST-HOC** here and in HANDOFF §3"* [PR §0, post-hoc labeling row]. The 43-row set was chosen after the primary existed; the ratified count is 35. The file's statement that the definition was *"Fixed before the arm was run"* cannot be verified: both definitions live in one script, written after the primary was seen and committed once (`3b4abd4`) [REV6 S2]. The file's own label says only "pre-registered arm run late". It ran at 2026-11-05T23:02:20Z from `data/f5/sensitivity_decision11.py` (sha `5504cca7…`). It used the pinned doc and params shas and the same `backtest_e2.py` sha as the head-1 run, and it reproduces the primary exactly (max |diff| 0.0). The file reports two definitions:

| definition (file key) | rows removed (CIKs) | mean delta |
|---|---|---|
| `sensitivity` (**POST-HOC operationalization**): every same-CIK filing that carries a scored WITHDRAWN chunk | 43 (26); 25 of them filed in 2020Q2 | −0.0052 |
| `home_key_reconciliation`: home filing only, the census rule behind the ratified count "35 of 7,389" | 35 (25) | +0.0177 |

Removing 35–43 of 7,381 rows changes 24 of the 33 fold deltas under each definition, mostly through the training sets, and the two definitions give means of opposite sign (arithmetic here over `per_fold`). The file says *"A mean of per-fold deltas, one fit per fold at seed 0. No SE, no TOST, no branch"* and *"this row can change no branch, no label and no scorecard."* Both means lie inside ±0.04 and below the MDE. They also sit inside the 100-seed nuisance band [−0.0141, +0.0347] (§1.4), and the mean |per-fold change| against the primary is 0.040 (43 rows) and 0.050 (35 rows), the same fit instability as §1.5, so the opposite signs are not interpretable [F6A, M1]. "Excluding it" was read as removing the rows from the frame before folds, purge, dedup, PIT ranks and fits, so they leave the training, test and trailing-rank pools [D11 `definition.removal`]. The other reading, recoding the WITHDRAWN value and keeping the rows, was not run. The ratified count of 35 is a census undercount: `census_e2.withdrawn_census` matches only each chunk's home filing, and 8 more frame rows are later same-CIK filings that re-attach a WITHDRAWN chunk (80 attributed against 54 home filings) [D11 `definition`, `frame`; F6A]. The file was on disk with sha `3256cce7…` when this document was written.

## §2 The scorecard [SC lines 1–34; PR §14]

The universe block, verbatim:

| block | n calls | n outperform | n underperform | n correct | hit rate | 95% Wilson interval | chance (from call counts) | no call (of which tied) | unresolved |
|---|---|---|---|---|---|---|---|---|---|
| the model (`text_and_numeric`) | 2992 | 1496 | 1496 | 1552 | 0.5187 | [0.5008, 0.5366] | 0.500 | 1489 (0) | 0 |
| numeric only (`numeric_only`) | 2991 | 1496 | 1495 | 1525 | 0.5099 | [0.4919, 0.5278] | 0.500 | 1490 (2) | 0 |
| size only (`size_only`) | 2933 | 1479 | 1454 | 1425 | 0.4859 | [0.4678, 0.5039] | 0.500 | 1548 (115) | 0 |

> Chance under this call rule: 0.50 when the calls are balanced; computed from the call counts: 0.500.
>
> Outcome mix (share of scored filings with positive excess): 0.4751. This is what the period did, not a benchmark the hit rate is measured against.

The inference sentence is printed on every page. Verbatim: *"Hit rates are descriptive. The inference is the pre-registered IC margin ladder (§1, decision 15); a per-company hit rate over at most 33 quarters has a wide interval and proves nothing on its own."*

**Why hit rates cannot overturn §13.** The pre-registration said so before the run: *"The scorecard cannot change the §13 outcome: if the IC margin comes back bounded-null or UNPOWERED, the text arm is closed regardless of how the hit rates read."* [PR §11, §13, §14]. The calls are terciles of the same out-of-fold scores that produced the IC (the reviewer found 0 mismatches [REV §2]). They are a coarser function of the same out-of-fold scores. The margin is a delta between two blocks; a hit rate speaks to the level of one block, which the margin does not measure. The calls cannot move §13 because the pre-registration bars them from it [PR §14], not because they carry no information. A call is a within-quarter relative statement and is *"NOT reproducible in real time — the tercile boundary depends on filings published later in the same quarter"* [PR §14]. The owner packet's phrases "from data public at that minute" and "the base rate" were wrong and have been corrected (REV S10; HANDOFF §3, 2026-11-05).

**Reviewer S3: the intervals assume independent calls.** The Wilson interval treats the 2,992 calls as independent, and they are not. One company can carry several calls per quarter with overlapping 63-session windows, and outcomes within a quarter are cross-sectionally correlated. The reviewer re-derived the interval (not pre-registered, context only): a quarter-cluster bootstrap gives [0.481, 0.556] for the model's hit rate and a company-cluster bootstrap gives [0.498, 0.540]. **Both include 0.50.** Per company, 12 of 113 rated intervals exclude 0.50 (9 above, 3 below), against about 5.7 expected at 95% under independence. That is 113 intervals across 3 blocks with no multiplicity control [REV S3]. The model's Wilson lower bound (0.5008) sits 0.0008 above 0.50. It must not be read as "beat chance". The model's and numeric-only's intervals overlap.

## §3 Failure taxonomy

This section asks why the answer is null, and whether any cause could be hiding an effect of the pre-registered size (an IC delta of 0.04). The causes fall into three groups: the world, the instrument and the design. "Cannot be determined from this run" means exactly that.

### (a) The world

| item | what it is, and how it was measured | could it hide a 0.04 effect? |
|---|---|---|
| Prior work | `PRIOR_WORK.md` §1. This is recalled literature; its §0 says the citations are unverified, so it gives directions only, never magnitudes. Tone and dictionary return effects are *"real but small, short-horizon, and have decayed"*. Managers manage tone strategically, which explains out-of-sample attenuation. Risk language predicts volatility *"far more reliably than it predicts return direction"*. The text→return effect that best survived replication is year-over-year textual change ("Lazy Prices"). The field's verdict on this question: *"barely, and less every year"*. Large caps are *"the worst place to look"*, and *"a null at E2 is the modal expected outcome."* | This is the expected explanation, not a measured one. If true effects in large caps are below 0.04, this run is consistent with them and cannot see them. YoY novelty (family A) was in head 1's confirmatory block; whether its construction matches the one the literature found to work is not determined here. Head 2 (§4) asks about volatility, not return, and its predictor is negative-sentiment share (`sentiment_negative_share`) with sentiment nulled on RISK_FACTORS (`features_e2.score_labels`), so it tests no risk-factor language. |
| Known effects at this horizon (positive controls) | `data/hardening/status/H1_controls.md` §1, §5c. T1 (earnings surprise → announcement return): IC +0.0643, t 3.13, positive in 29 of 41 quarters (70.7%): **FAIL at the pre-declared bar** (t 3.13 < 4.0; 70.7% < 75%). The statement that the date/price/session plumbing works rests on a POST-HOC diagnostic (H1 §4b), not on the pre-declared test. T2a, PEAD at the harness's own 63-session window: +0.0279, AMBIGUOUS, MDE 0.071. T2b, momentum: +0.0287, AMBIGUOUS, MDE 0.110. T0 placebo: PASS. These ran on the earnings-8-K grid, not E2's filing frame. | Well-documented return effects at this horizon and panel size are themselves below what about 40 quarters can resolve. That is consistent with a small text effect being invisible here. Cannot be determined from this run. |
| E1, the earlier run | `data/backtest_report.md`: 25 mega-caps, 6 folds, no fold-robust text signal. The raw and dedup means disagree in sign; the report reads this as "fragility, not a direction". `data/diagnosis_report.md` §5: 25 tickers and 6 folds cannot support per-family or per-ticker claims. | E1 is listed only as the prior that set expectations. Its numbers are not comparable with E2's (different benchmark, universe and labels). |

### (b) The instrument

| item | what it is, and how it was measured | could it hide a 0.04 effect? |
|---|---|---|
| Sentiment labels | G2 agreement 293/337 = **86.94%** [82.93, 90.13], **INDETERMINATE** at the 0.85 bar. Labeler NEGATIVE recall **0.529** (64/121), from the v1.2 adapter's own held-out eval. Stored-NEGATIVE precision 25/49, which is one-directional verification of contested rows and not recall. G2 is model consensus (blind rater + adjudicator, both Claude-family) with owner rulings on 59 escalated and probe rows [G2 §1; R1 `g2_caveats`; PR §11]. | Label noise attenuates a feature's contribution, and the labeler misses about half the NEGATIVE chunks on its own eval. A chunk proportion is never used as feature reliability (G2 §6.5 box). The feature-level size is in the attenuation row below; beyond that, cannot be determined from this run. |
| Guidance labels | G2 **PASS** 115/119 = 96.64% [91.68, 98.69], a statement about the NONE mass only: 60 of the 119 rows are imputed NONEs scored as NONE, and 9 carry an active direction. Active precision **68.67%** [58.17, 77.55] (n_eff 84.8). False-NONE rate 0/80 [0.00, 4.58]. The owner's binding reading [G2 §0]: *"Do not interpret the 68.67% active-guidance precision as evidence that the model usually hallucinates the existence of guidance. A substantial share of those errors arise because the current guidance_direction label set has no representation for newly issued, directionless guidance."* Imputed NONE covers 48,293 = 51.08% of guidance-applicable frame chunks (48,790 = 51.18% of the corpus) [CEN `section_5`]. `guidance_signed_mean` is present on only **27.99%** of the 7,381 run-time filings [CEN `section_1c…confirmatory_column_coverage_ex_gld_run_time`]. | In principle, yes. About 3 in 10 active directions disagree with the reference, newly issued guidance maps to NONE, and the main guidance feature is read on roughly a quarter of filings. The size cannot be determined from this run. |
| Red-flag labels | The DEMOTE rule fired. The v1.2 teacher's exact-set error is 84/200 = **42.00%** [35.37, 48.93], with k exactly at the boundary. The student's exact-set error is 112/400 = 28.0% [23.8, 32.6] against model consensus. The family is exploratory / disclosure-only (owner ruling 2026-08-27) [PR §11; R1 `g2_caveats`]. E1's 63.4% agreement (`RED_FLAGS_LIMITATION.md`, disposition table) was measured on Claude bootstrap labels and does not describe these. | Red flags are not in the confirmatory block, so they can neither cause nor hide the primary result. They feed the exploratory block (§3(c)). |
| Attenuation | H3v2 retention is the correlation between student-derived and teacher-derived features over E1's 630-row feature table, from a filing-clustered bootstrap (4,000 draws, seed 0), reported **per feature, never a family mean** [PR §11]. The confirmatory labeler-derived features, eval-only slice unless stated: `sentiment_negative_share` **0.7833** [0.6130, 0.8935]; `sentiment_mean_score` **0.8696** [0.8153, 0.9109]; `guidance_any_present` **0.7534** [0.5356, 0.9114]; `guidance_signed_mean` **0.6248** [0.3271, 0.8776] **pooled** (n = 56 defined rows), which the file calls *"a real regression"*. Its eval-only figure, 0.9359 [0.7455, 1.0000], rests on n = 11 and is the one the file says is *"not a measurement"* (the pooled column is labelled an upper bound, 85.0% memorized). The composition features retain 1.0000 (a wiring check). Novelty and embeddings are zero-labeling families and are not labeler-derived (`feature_dictionary_e2.json` `partition_basis`). Red flags, outside the confirmatory block: family mean 0.8078 [0.7503, 0.8528], members 0.4238 to 0.9744. On the red-flag family's 0.669 → 0.808 move, H3v2 says the rubric repair and the student repair are worth *"roughly the same amount, about half each, and they overlap"*; the arms do not sum, and "+0.0904 rubric / +0.0481 student" is one ordering (rubric applied first) (`data/hardening/status/H3v2_attenuation.md` §3.1, §3.4, §3.8; PR §11). This is model against model on E1 filings, not against ground truth. | Plausibly, at the margin, under a convention. The census convention takes measured ≈ λ × true at λ ≈ 0.8 [CEN `MDE_true_construct_lambda_0.8` = MDE / 0.8; PR §11 λ row]. A true effect of 0.04 in teacher units would then show as about 0.032 (0.04 × 0.8). That is above the primary's CI upper bound (0.0256) but inside the seed band (max 0.0347) and below the MDE. In teacher units the CI upper bound becomes about 0.032 (0.0256 / 0.8) and the MDE about 0.052 (0.0416 / 0.8) (arithmetic here; the census bracket at k = 33 is 0.038 → 0.096 [PR §1, "Honest MDE"]). One λ for the IC delta of a multi-feature fit is a convention, not a measurement, and the measured `guidance_signed_mean` retention (0.62 pooled) is worse than the convention. Attenuation against the truth, rather than against the teacher, is not measured. |
| Labeler-training overlap | Chunk level: 14,342 = 4.53% of 316,291 labeled chunks overlap the labeler's fine-tuning split. Filing level: 2,530 = 34.28% of the 7,381 run-time filings. Company level: 108 of 143 (75.5%). These are three different questions and all are lower bounds. The `any_source_accession` channel over-flags because it is not strictly point-in-time [PR §11; SC]. | The no-overlap arm (2,694 rows) is also null at −0.0061 (§1.3). Whether overlap masks or inflates anything cannot be determined from this run. |
| Seven-financials extraction hole | 148 periodic filings from 10 CIKs carry no text row: Citigroup 100% (41), Morgan Stanley 93% (38), US Bancorp 88% (28), Colgate-Palmolive 64%, BNY Mellon 63%, Wells Fargo 24%, AIG 10%, and one each for Intel, PNC and Texas Instruments. Seven of the ten are financials, so those companies enter the text arm on 8-K press releases alone [PR §11; CEN `section_4…never_extracted_periodic`]. | It is a sector-shaped hole and could hide a financials-specific effect. Whether it hides a universe-level 0.04 effect cannot be determined from this run. |
| Missing embeddings | 45 rows on the 7,618-row join and 44 on the 7,389-row modeling frame have no embedding. 25 of them are scored dedup rows, and 19 of those received a call. They are fitted with NaN embedding components [R1 `frame`, `missing_embedding_calls`]. | That is 25 of 4,481 scored rows. The effect is not measured. |
| CAD exception | Enbridge (CIK 895728) enters unconverted (decision 7). 108 of its rows are `fx_blocked`, and `log_total_assets` and `book_to_market` are NaN for that CIK; it has 48 filings in the frame [PR §11; SC]. | That is 48 of 7,381 frame rows. The effect is not measured. |
| Price censoring | 31 of 244 universe members have no usable prices, and 27 of 176 core CIKs have no price column. 324 modeling rows have a complete window but no subject price. Channel A (core members with no price column) by fold: 2018Q1–Q2 16 CIKs (16.3% of the would-be 2018Q1 panel), 2018Q3 13, Q4 12, 2019Q1 10, Q2 9, Q3 10, Q4 9, 2020Q1–Q2 8, Q3–Q4 5, 2021Q1–Q2 4, 2021Q3–2022Q2 5, 2022Q3–2023Q2 3, 2023Q3 5, 2023Q4–2024Q2 4, 2024Q3 3, 2024Q4–2025Q2 2, 2025Q3–2026Q1 0 ([CEN] STEP2 §B per-fold table; carried here per REV S11d). Channel B is 29 rows over 2018Q1–2021Q2: the per-fold column sums to 29 and [PR §7] agrees, while the STEP2 prose says 27. The cause is not separately measured, so these companies are not described as delistings. The direction: dead-name exclusion understates downside dispersion and overstates the benchmark, most strongly in the early folds [PR §11]. | Cannot be determined from this run. The post-2019 arm, which drops the four most-censored test quarters, is also null at −0.0003. |
| Prices: provenance and dividends | Prices come from the stored Yahoo snapshot of 2026-08-24 (sha `744e1cc5…`, 213 priced CIKs). The source is a free keyless endpoint under a robots.txt disallow, with no published terms for this use. It was ratified for this run only, and no new fetch is made. The series is split-adjusted only, with no dividends [PR §12]. Over 63 sessions the missing dividends act as a cross-sectional yield bias (H1 §9). | Cannot be determined from this run. |

### (c) The design

| item | what it is, and how it was measured | could it hide a 0.04 effect? |
|---|---|---|
| Power | MDE 0.0416 against the ladder [0.03, 0.04, 0.05]. The 0.03 rung was not supportable (SE 0.01487 > 0.01206) [R1 `margin`]. | An effect below 0.04 is, by construction, not what was tested. An effect of exactly 0.04 is at the edge of detection, and its measured-unit version lies outside the 90% CI. |
| Fold non-independence | Training windows are nested and the 63-session windows straddle fold boundaries, so effective k < 33. The measured lag-1 autocorrelation is −0.042 [R1 `margin`]. | It makes the printed precision optimistic. The true detection limit is above 0.0416 by an unmeasured amount. |
| 63-session horizon | The window opens at the first session after the filing is public and runs 63 sessions [PR §14, "The outcome"]. | Prior work says tone effects are short-horizon, and an effect that resolves within days would be diluted over 63 sessions. Head 1 has no short-horizon return arm; head 2's 5-session window measures volatility, not return. Cannot be determined from this run. |
| Equal-weight universe benchmark | Peers are the membership-dated equal-weighted average of all universe members, both strata, *including the unpromoted extension stratum G2 never validated*, with GLD and the company itself excluded. No index ETF series exists; SPY is a P2 item [PR §5, §14(g)]. (That clause is missing from the scorecard page, REV N6, and is carried here.) | Not measured. Cannot be determined from this run. |
| Exploratory block above the primary | This block adds red flags and the `_seq` novelty pair. Its dedup mean is **+0.0145**, against the primary's +0.0011. Under other specs: raw +0.0192, no-same-day +0.0210, no-overlap +0.0199, but `raw_levels` dedup −0.0056 and `raw_levels` no-overlap −0.0188 [R1 `per_fold_delta__*_exploratory`]. | **It does not count.** It was pre-registered as exploratory / disclosure-only (DEMOTE fired; under decision 23, `_seq` is never confirmatory). No SE, margin or branch is computed for it. Its sign flips with the spec, it is below the MDE under every spec, and its red-flag inputs carry 28% student and 42% teacher exact-set error. Quoting it as the headline would be post-hoc selection [REV N5]. |

**What the taxonomy adds up to.** Labeler noise, attenuation, power and fold dependence all push the same way: toward under-reading a true effect, or toward a wider true interval than the one printed. Power is the MDE itself (0.0416, a lower bound, §1.1). Fold dependence raises the true detection limit by an unmeasured amount. Labeler noise has no feature-level size beyond the attenuation row. Attenuation has a size only under the census convention λ ≈ 0.8, and under it a true 0.04 effect would show as about 0.032, not as +0.0011. The other causes have no measured size. So the run supports closure at the ratified margin. It does not show that text effects are absent. Under the same convention, the 90% CI's upper bound is about 0.032 in teacher units and the MDE about 0.052 (arithmetic here), so no equivalence claim is read as tighter than about 0.052 in teacher units.

## §4 What survives, and what is an asset

- **The point-in-time pipeline.** The reviewer independently rebuilt the join, folds, purge and dedup and found them equal fold for fold. For every fold, training filing dates and window closes precede the test start. For all 4,481 scored rows, the window opens strictly after both `info_date` and the news session [REV §2]. After the purge, 0 training labels resolve in or after their test quarter [R1 `standing.embargo_census_post_purge`]. H1's T1 failed its pre-declared bar; the date/price/session stack was verified by a POST-HOC diagnostic [H1 §1, §4b]. The guarded runners refuse without the pin (CLAUDE.md). Scope: the reviewer did not independently re-derive feature-side PIT (numeric price features ending before the news session, the PIT rank frame); that rests on the pinned tests `test_price_windows_never_touch_the_news_session` and `test_spec.py::test_future_rows_cannot_change_a_past_percentile` [REV N9].
- **The reading aid.** `bin/fs report TICKER` (CLAUDE.md). PRODUCT_PLAN P1 says the text family *"stays in the reading aid as information"*. The measured label error travels with it.
- **The scorecard machinery.** The reviewer recomputed it with independent code: 0 call, straddle or correct-flag mismatches, the below-6-call withholding leaked nothing, and the disclosure block is present [REV §2]. Still owed on the page: the S3 independence and multiplicity line, the N6 clause, and tickers (N8). It stays off public surfaces (legal baseline finding #4). Forward (P5) calls need their own real-time rule [PR §14].
- **The numeric families.** PRODUCT_PLAN P1 says that under a null *"the product continues on the numeric signal families."* This run did not test them as a signal. Numeric-only's mean IC of +0.0251 sits below the ticker-mean benchmark (+0.0362) and the H1 noise floor (§1.7). Nothing here is evidence for them.
- **Head 3, exit prediction [R3; REV S7, S8].** Per-fold AUCs run from 0.403 to 1.000 over 20 scored folds. 10 folds (2021Q1–2023Q2) have no test positives and are not scored, and 3 folds (2025Q3–2026Q1) are censored. The pre-registration expected 30 scored folds. The 64 positive rows are **20 distinct exits at 20 companies**, each counted in up to 4 consecutive folds. No aggregate was pre-registered, so any mean is POST-HOC. There is no text-free comparator, so nothing here can be attributed to text. The claim is "exit", never "distress". One look-ahead is known (S8): the exit screen labels a *training* exit as a non-exit using the company's filings ≥ 1 year later, so training labels at fold q use filings dated after q. Its effect on AUC is unmeasured, and fixing it would be a new pre-registration. The asset is the panel and the machinery, not the AUCs.
- **Head 2, volatility event study [R2; REV S2, S6].** The pre-registered direction was **positive**. The measured slope is **−0.165** (wild-cluster SE 0.088), with one-sided p **0.974** for the pre-registered direction: no support. The two-sided p of 0.0465 is reported only because the pre-registration reports both. It runs opposite to the registered direction, is exploratory only, rests on 40 clusters (an approximate regime) and has no multiplicity control. The DV is not dividend-immune. The null-draw 2.5–97.5% band is [−0.166, +0.160]. The escorts the head-2 file lacks (S6): the predictor is sentiment, rated INDETERMINATE (86.94%); labeler NEGATIVE recall is 0.529 (64/121); stored-NEGATIVE precision is 25/49; and all of these are model consensus, not human validation. Cross-head clause: *"Heads may not rescue each other"* [PR §13].

## §5 Deviations, limitations, and what the E3 policy requires

**M1, a recorded deviation.** The ratified decision-11 arm (*"one sensitivity row excluding it, labelled as the 2020Q2 sensitivity it is"* [PR §10]) was not built into the guarded run. HANDOFF §3 (2026-11-05) records this as a DEVIATION from the ratified document. The arm ran late as a separate script, with no edit to `backtest_e2.py`, and its result is in §1.8. Its 43-row definition is a **POST-HOC operationalization** (43 against the ratified count 35) [PR §0, post-hoc labeling row; REV6 S2].

**S9, a process deviation.** `pin_g3.py --show` and `--pin` ran 1.9 s apart inside one command, so the owner saw the §4 description of the diff, not the diff itself. The diff is at `data/f5/status/PIN_SHOW_2026-11-05.txt`, and the reviewer verified it byte-exact against the eight declared substitutions [REV S9]. There was no re-pin. The diff belongs in the owner's next read.

**Standing limitations (all in force).** Red-flag labels are exploratory and config-sensitive. Model-rater agreement is model consensus. Prices come from Yahoo (provenance above, split-adjusted only). The extraction holes stand (the seven financials). E1 and E2 numbers are not comparable. The cause of the price censoring is unmeasured. Two ratios (`net_margin`, 135 rows; `operating_margin`, 20 rows) remain on the ported definition; that boundary was set by the main session, not by an owner ruling [PR §11].

**The reviewer's findings [REV §1]: disposition "carried here"** (with any action HANDOFF §3 records):

| # | finding | carried at |
|---|---|---|
| M1 | decision-11 arm never run | §5 deviation; §1.8 result |
| M2 | five tripwires red post-pin; their text invited deleting the pin | carried here; HANDOFF §3: inverted by `builder` (commit `fe54fe2`) |
| S1 | equivalence label is seed-dependent (32/100 fail; none reaches the MDE) | §1.4 |
| S2 | head-2 slope opposite to the pre-registration; two-sided p quoted bare | §4; HANDOFF §3: fixed the same hour |
| S3 | Wilson assumes independence; clustered intervals include 0.50 | §2 |
| S4 | `report_head1.md` omits mandatory arms and §11 escorts | §1.3, §3(b). `report_head1.md` itself is unchanged; F6-A's `data/f5/report_head1_addendum.md` (sha `36ddc878…`) now carries the arms, the §11 escorts and an override, except H3v2 per-feature retention and the unruled-ratio counts (135 / 20 rows) [F6A] |
| S5 | stale E1 boilerplate in the report; anchor scope unstated | carried here; the addendum's §C also overrides the stale phrases and quotes the anchor scope [F6A]. [R1 `standing.bootstrap_anchor_scope`]: *"the anchor is computed on the confirmatory block WITHOUT the per-fold embedding components. Stated, not silently absorbed."* |
| S6 | heads 2/3 lack the sentiment escorts | §4 (carried in this document). `heads_e2.py` now builds them (F6-A), but `results_head2.json` / `results_head3.json` on disk predate the change and still lack them; the change affects future renders only [F6A] |
| S7 | head 3: no aggregate; 20 scored folds, 20 events | §4 |
| S8 | head-3 exit screen uses later filings for training labels | §4. `heads_e2.py` `head_disclosures()["validation"]` still says head 3 *"trains only on quarters strictly before the test quarter"*, unchanged; a fix there is a render-only wording change and needs no re-run [REV6 S6] |
| S9 | owner not shown the pin diff | §5 deviation |
| S10 | owner packet misdescribed the scorecard | §2; HANDOFF §3: corrected |
| S11 | heads 2/3 shas missing from run_log; report unhashed; channel-A table not in outputs | §6 (shas measured); §3(b) (channel A) |
| N1 | chain ran under the Xcode python path (same 3.9.6) | carried here |
| N2 | LOCO cell "1,438" stale (the run's 1,426 is the ex-GLD rule) | §1.5 |
| N3 | 2020Q1 carries +0.22; mean without it −0.0058 | §1.6 |
| N4 | fit instability (GLD Δ 0.055 mean; LOCO spans ~0.41) | §1.5 |
| N5 | exploratory block +0.0145 must never be the headline | §3(c) |
| N6 | scorecard benchmark line drops the extension-stratum clause | §3(c) |
| N7 | GLD has 8 rows in the head-3 panel; scope of decision 2 ambiguous | carried here |
| N8 | only 25 of 139 scorecard companies carry a ticker | carried here |
| N9 | feature-side PIT not independently re-derived by the reviewer | §4 (scope sentence) |
| D11 count | the ratified "35 of 7,389 rows" undercounts the WITHDRAWN-touched rows: 43 under same-CIK attribution (80 attributed against 54 home filings) | §1.8; the 43-row definition is labelled POST-HOC [REV6 S2; F6A] |

**The F6 review [REV6]** was applied to this document on 2026-11-05 for MF1 and S1–S7. MF2 (public-surface status) is outside this document's edits and sits with the main session; N1–N11 are not applied here.

**The E3 policy, quoted from §13 [PR]:** *"**E3 policy:** No E3 without a NEW owner ratification that (a) names what changed — "maybe underpowered" is inadmissible, E2 *was* the powered answer to that; (b) states its own MDE, cost, and stopping rule; (c) quotes and explicitly supersedes this paragraph."* Nothing in this document is such a ratification, and the causes in §3 are not "what changed".

## §6 File index

Shas from `data/f5/run_log.jsonl` unless marked "measured", which means computed with `shasum -a 256` while this was written (2026-11-05). While this document was being written, F6-A appended S11 backfill lines to `run_log.jsonl` (uncommitted at the time). Every one checked matches the measured value below.

| file | sha256 (first 16) | note |
|---|---|---|
| `data/f5/G3_PREREGISTRATION.md` | `6b99f65ea1da42e8` | pinned document (run_log `doc_sha256`) |
| params block | `9ac479818785b6fc` | run_log `params_sha256` |
| `data/f5/G3_RATIFIED.json` | `f27141e529088bbe` | measured |
| `data/f5/results_head1.json` | `6836fb90487508d7` | run_log; committed |
| `data/f5/head1_oof_predictions.parquet` | `378b0b711ae81752` | run_log; git-excluded |
| `data/f5/head1_scorecard.json` / `.md` | `028f34f5f5f57a6c` / `59cc29c0dbd7348e` | run_log; git-excluded (legal baseline #4) |
| `data/f5/results_head2.json` | `2c14f6fb1a07bc72` | measured; the run's own line has no sha (S11); F6-A's backfill line (23:07:26Z, uncommitted at write time) carries the same value |
| `data/f5/results_head3.json` | `e9335637ff5ce4a9` | measured; same as above (S11 backfill matches) |
| `data/f5/report_head1.md` | `9a51bb4e94d1f45b` | measured; untracked (S11); F6-A backfill line matches |
| `data/f5/sensitivity_decision11.json` / `.py` | `3256cce7ecf3190a` / `5504cca784d81f06` | measured; F6-A, post-hoc label; F6-A run_log lines match |
| `data/f5/census_e2.json` | `2a7dd0d27c8244d0` | measured |
| `data/f5/status/PIN_SHOW_2026-11-05.txt` | `1aeb7c14d46b833a` | measured; the pin diff |
| `data/f5/status/g3_chain_log.jsonl` | `de735f8bea4271a3` | measured |
| `data/f4/g2/results_g2.json` | `d146e5e435864030` | measured; equals [R1 `g2_caveats.sha256`] |
| `backtest_e2.py` | `746389ae0f903565` | measured; equals [R1 `run.module_sha256`] |
| `heads_e2.py` (as run) | `0bd3bac1340214f1` | measured at commits `41829ad` and `0b549cb` [REV S11c]; the working copy carried uncommitted edits (`06dfba50…`) when this was written |
| `scorecard_e2.py` | `6b5263eded13d35e` | measured; matches [REV S11c] |
| inputs: `target_e2` / `text_features_e2` / `numeric_features_e2` / `text_families_e2` parquets | `ef6befb2…` / `143dd720…` / `01fcaf4b…` / `3cee6564…` | [R1 `frame.input_sha256`] |
| `data/prices_e2.parquet` | `744e1cc5ccc2bfad` | [R2 `inputs`]; [PR §12] |

Also read for this write-up, with no sha recorded: `data/f5/status/G3_RUN_2026-11-05_owner_read.md`, `data/f5/status/STEP2_census_e2.md`, `data/f4/g2/G2_FINAL_REPORT.md` §0–§1, `data/hardening/status/H3v2_attenuation.md` §3, `data/hardening/status/H1_controls.md`, `data/backtest_report.md`, `data/diagnosis_report.md` §5, `PRIOR_WORK.md` §0–§1, `RED_FLAGS_LIMITATION.md` (disposition table), `PRODUCT_PLAN.md` P1, `HANDOFF.md` §3 entries of 2026-11-05, `site/STORYBOARD.md` (legal baseline).
