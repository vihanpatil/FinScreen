# E2 head 1 -- report addendum (render-only; review S4 + S5)

Rendered 2026-11-05T23:06:13+00:00 by `data/f5/render_head1_addendum.py` from `results_head1.json` (sha256 `6836fb90487508d7aceb354fbc08de95538a81b6ba0c4cdd9c60d0c0abf390db`). It adds to `report_head1.md` (sha256 `9a51bb4e94d1f45be3da742f2720ab25340f6383dc5c5ab2b49b857a960a1ee7`), which is left untouched; no model was fitted. Every number below is read from an artifact. Where this addendum and the report disagree, this addendum governs.

## A. Every always-reported arm beside the primary (mean of per-fold dedup Spearman IC deltas, text+numeric minus numeric-only)

| arm | k folds | mean fold delta | folds > 0 | source key in results_head1.json |
|---|---|---|---|---|
| PRIMARY: pit_trailing_rank, dedup (the estimand) | 33 | +0.0011 | 16 | `per_fold_primary_delta_dedup` |
| secondary (mandatory): raw_levels, dedup | 33 | -0.0013 | 18 | `per_fold_delta__raw_levels__dedup__text_and_numeric` |
| sensitivity: include_same_day=False, dedup | 33 | +0.0081 | 18 | `per_fold_delta__pit_trailing_rank_no_same_day__dedup__text_and_numeric` |
| overlap arm: dedup, no train-overlap rows | 33 | -0.0061 | 15 | `per_fold_delta__pit_trailing_rank__dedup_no_overlap__text_and_numeric` |
| raw (non-dedup) evaluation set | 33 | +0.0050 | 15 | `per_fold_delta__pit_trailing_rank__raw__text_and_numeric` |
| form-controlled ablation (10-Q/10-K only), dedup | 33 | +0.0061 | 20 | `form_controlled_ablation.per_fold_delta_dedup` |
| rolling 8-quarter training window, dedup | 33 | +0.0008 | 16 | `per_fold_delta__rolling_8q.records` |
| rolling 16-quarter training window, dedup | 33 | -0.0039 | 17 | `per_fold_delta__rolling_16q.records` |
| GLD-included frame, dedup | 33 | -0.0046 | 15 | `per_fold_delta__gld_included.records` |
| decision 11, the 2020Q2 sensitivity (WITHDRAWN rows excluded, n = 43) -- EXECUTED AFTER THE PRIMARY WAS SEEN (2026-11-05); pre-registered arm run late; can never be selected as the primary | 33 | -0.0052 | 17 | `sensitivity_decision11.json` |
| decision 11 reconciliation: the census's home-filing rule (n = 35, the prereg's measured count) -- same label | 33 | +0.0177 | 20 | `sensitivity_decision11.json` |

Only the first row drives §13 (decision 15). Every other row is a sensitivity or a mandatory secondary: reported beside the primary, never selected in its place. A mean of per-fold deltas carries no SE here; the margin procedure applies to the primary alone.

Decision 11's row removes the 43 rows whose `guidance_signed_mean` contains a WITHDRAWN label under the features' own same-CIK attribution; the prereg's measured count (35) matched only each chunk's home filing. Both rows are shown; neither can be selected. Its 2020Q2 fold loses 25 test rows.

## B. §11 instrument escorts (these travel with every result above)

Rebuilt by `backtest_e2.build_disclosures` from the artifacts the scorecard page reads (G2 results, the labeler's own eval, census_e2, the target manifest) and verified verbatim against the scorecard page's disclosure block.

- **Label quality.** These labels are model-produced, not human ground truth. G2 (model-consensus with owner rulings): sentiment agreement 86.94% [82.93%, 90.13%], n = 337 -- INDETERMINATE; sentiment NEGATIVE recall 0.529 (64/121) on this labeler's own held-out eval, and G2 stored-NEGATIVE precision 25/49 (51%) -- the share of chunks STORED NEGATIVE whose reference value was also NEGATIVE, summed from secondaries.S-ERR.sentiment.confusion_stored_x_reference -- is one-directional verification of contested rows and is NOT recall against independent ground truth. Guidance agreement 96.64% [91.68%, 98.69%], n = 119 is a statement about the NONE mass only and travels with ACTIVE precision 68.67% [58.17%, 77.55%], and its false-NONE rate is 0.00% (0/80) [0.00%, 4.58%] -- see G2_FINAL_REPORT.md §0 (the owner's binding interpretation: NONE may hide newly issued guidance). Red flags: exact-set error 28.00% [23.83%, 32.59%], n = 400, and the block is exploratory / disclosure-only (owner ruling 2026-08-27); this pass cannot change it -- measured on top of a v1.2 TEACHER spot-check exact-set error of 42.00% (84/200). Source: data/f4/g2/results_g2.json, sha256 d146e5e43586.
- **Train overlap.** Three different questions, all stated: chunk level, 4.53% of 316,291 labeled chunks overlap the labeler's own fine-tuning split (G2 census); filing level, 34.28% of the 7,381 filings in this analysis frame carry at least one such chunk (train_overlap_share > 0); company level, 108 of 143 companies (75.5%) carry at least one overlapping chunk. A chunk-level share, a filing-level share and a company-level share are not the same quantity and none of them bounds the others.
- **Extraction coverage.** 10 universe CIKs have no extracted periodic sections at all (148 10-K/10-Q filings never extracted), 7 of them financials -- a sector-concentrated hole, not a random one (census_e2.json, never_extracted_periodic).
- **Currency (the CAD exception).** Enbridge (CIK 895728) reports in Canadian dollars and enters this run UNCONVERTED -- the disclosed exception of decision 7 (owner 2026-09-11); no FX code path exists yet, and 48 of the filings in this frame are that company's.
- **Missing embeddings.** 25 of the rows this scorecard scores sit on filings with no embedding vector, and 19 of them received a published call (44 rows on the modeling frame carry none, 45 on the three-way join before the null-target drop); those rows are fitted and scored with NaN embedding components under XGBoost's missing-value handling -- numeric plus the legacy text columns only.
- **Price censoring (survivorship direction).** 31 of 244 universe members have no usable prices (counts from the target manifest); the cause is not separately measured, so they are not described as delistings; the direction is that dead-name exclusion understates downside dispersion and overstates the benchmark.
- **What these returns are.** Price return only -- dividends not included; no transaction costs, taxes, slippage or position sizing; out-of-fold, backtested, no money invested.
- **Peer benchmark.** The peer benchmark is the equal-weighted average of all universe members, both strata, GLD excluded, excluding the company itself; 8 GLD rows were removed from this analysis frame before any fold (decision 2).
- **Two unruled ratios.** `net_margin`, `operating_margin` stay on the ported definition (numeric manifest `counters.ocf_to_revenue_duration_match.unruled_ratios_left_as_ported`); a main-session scope boundary, not the owner's ruling (G3 §11).
- **Model consensus.** Every G2 agreement rate is model consensus over model-adjudicated fields, not human validation of ground truth (G3 §11).

## C. Override: stale E1-era sentences in report_head1.md

The report carries boilerplate written for E1 by frozen `spec.py`. These sentences are stale and are overridden here:

- "there is no embargo/purge, and the population has never been stated"
- "Whether to embargo is a G3 pre-registration decision; this report only measures it."
- "exactly the same non-embargoed-label property the fitted models have"
- "at k = 6 neither tail is anywhere near significant"
- "At E2's ~26 folds"
- "the standard deviation of six numbers"

The ratified purge (`purge_rule` = `target_window_close_on_or_after_test_quarter_start`) applied to every fold: per the report's own label-embargo table, **0 of 123,180 training labels** resolve on or after their fold's test quarter begins. Training labels are purged, not non-embargoed, and that holds for the `ticker_training_mean_rank` benchmark too (it is built on the same purged folds). The run has **k = 33 folds**, not 6 and not ~26, and its lag-1 autocorrelation was measured: -0.0418.

The noise-anchor section headed **PRIMARY** is not computed on the primary's feature block. The run's own scope note (`standing.bootstrap_anchor_scope`), quoted:

> The frozen spec.bootstrap_noise_anchor takes ONE frame, not per-fold frames, so the anchor is computed on the confirmatory block WITHOUT the per-fold embedding components. Stated, not silently absorbed.

So that section's `fold_delta_dedup` column is a different quantity from §2's primary deltas. Examples: 2018Q1 -0.0237 (anchor) vs -0.0708 (primary), and the widest gap, 2022Q1, is -0.0144 vs -0.1630. Quote §2, never the anchor table, for a per-fold primary delta.
