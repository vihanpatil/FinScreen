# G2 — E2 student-label spot-check — results (owner_ratified)

generated 2026-09-07T19:03:27Z | option C | seed 20260906 | drawn 580 | rated 580 | bars {"sentiment": 0.85, "guidance_direction": 0.85}

api_calls 0 | gpu_seconds 0 | network_calls 0

## 0. Completeness

> PROVENANCE: model-consensus agreement (blind rater + adjudicator, both Claude-family) with owner rulings superseding on the escalated subset; NOT human validation of ground truth (HANDOFF §3).
> A non-FAIL is not a clearance (§6.6); red_flags is exploratory / disclosure-only (owner ruling 2026-08-27); this pass cannot change it.


- every pre-registered input is present
- no batch was re-run (failed_batches.json is empty or absent, §11.3)

## 1. Primaries — gate-bearing, one bar each

> PROVENANCE: model-consensus agreement (blind rater + adjudicator, both Claude-family) with owner rulings superseding on the escalated subset; NOT human validation of ground truth (HANDOFF §3).
> A non-FAIL is not a clearance (§6.6); red_flags is exploratory / disclosure-only (owner ruling 2026-08-27); this pass cannot change it.


### `sentiment` — bar 0.85
293/337 = 86.94%  95% Wilson [82.93%, 90.13%]  (+-3.60%) -> **INDETERMINATE**
- PASS needs k >= 300; DECISIVE FAIL needs k <= 273; observed k = 293 of n = 337
- non-evaluable 0 (unsure 0, unadjudicated 0); omission-pinned errors 3
- unsure/unruled sensitivity: all-error [82.93%, 90.13%] vs all-agree [82.93%, 90.13%] — **VACUOUS**: the two-sided bracket is degenerate because this field has 0 non-evaluable rows (the adjudicator emitted 0 'unsure' verdicts in 314 rulings). It is NOT evidence of robustness; there was nothing for it to be robust to.
- caveat: Chunk-level label accuracy under the §1.2 applicability mask (MDA + EX99_PRESS_RELEASE). Omitted stored values are scored as errors (§1.3); S-OMIT restates the rate with them excluded. This is NOT EXPANSION_PLAN §2a's feature-level reliability lambda and must not be used as one (§6.5).

### `guidance_direction` — bar 0.85
guidance_agreement_base_rate 115/119 = 96.64%  95% Wilson [91.68%, 98.69%]  (+-3.51%) -> PASS at bar 0.85  ||  guidance_active_precision 68.67% 95% Wilson [58.17%, 77.55%] (corpus-re-weighted; n_eff 84.8 of nominal n 100)  ||  guidance_false_none_rate 0/80 = 0.00%  95% Wilson [0.00%, 4.58%]  (+-2.29%)
- PASS needs k >= 109; DECISIVE FAIL needs k <= 93; observed k = 115 of n = 119
- non-evaluable 0 (unsure 0, unadjudicated 0); omission-pinned errors 0
- unsure/unruled sensitivity: all-error [91.68%, 98.69%] vs all-agree [91.68%, 98.69%] — **VACUOUS**: the two-sided bracket is degenerate because this field has 0 non-evaluable rows (the adjudicator emitted 0 'unsure' verdicts in 314 rulings). It is NOT evidence of robustness; there was nothing for it to be robust to.
- caveat: A PASS on guidance-P is a statement about the NONE mass only. Of the 119 EX99 rows in P (realized draw), 60 are guidance_imputed_none=true rows scored AS NONE by the §1.3 writer rule and only 9 carry an active direction, so the bar can be cleared almost entirely by the writer rule being right about the NONE mass. It is NOT evidence about the RAISED / LOWERED / MAINTAINED / WITHDRAWN calls that drive guidance_signed_mean. G-A's active precision (pooled, corpus-re-weighted) and G-N's false-NONE rate must be quoted in every table where the guidance verdict appears, and no headline may cite the guidance verdict alone.

Non-decisional bars (k* boundaries only — p-hat and its CI do not depend on the bar and are NOT reprinted; NO verdict word):
- `sentiment` at 0.9: clearing it would need k >= 315 of n = 337 (p-hat >= 93.47%); a decisive failure would need k <= 292 — non-decisional; no verdict is defined at this bar. Only the k* boundaries move with the bar — p_hat and its Wilson interval do not, so they are NOT reprinted here
- `guidance_direction` at 0.9: clearing it would need k >= 114 of n = 119 (p-hat >= 95.80%); a decisive failure would need k <= 100 — non-decisional; no verdict is defined at this bar. Only the k* boundaries move with the bar — p_hat and its Wilson interval do not, so they are NOT reprinted here

## 2. Guidance arms (never quote the base rate alone)

> PROVENANCE: model-consensus agreement (blind rater + adjudicator, both Claude-family) with owner rulings superseding on the escalated subset; NOT human validation of ground truth (HANDOFF §3).
> A non-FAIL is not a clearance (§6.6); red_flags is exploratory / disclosure-only (owner ruling 2026-08-27); this pass cannot change it.


guidance_agreement_base_rate 115/119 = 96.64%  95% Wilson [91.68%, 98.69%]  (+-3.51%) -> PASS at bar 0.85  ||  guidance_active_precision 68.67% 95% Wilson [58.17%, 77.55%] (corpus-re-weighted; n_eff 84.8 of nominal n 100)  ||  guidance_false_none_rate 0/80 = 0.00%  95% Wilson [0.00%, 4.58%]  (+-2.29%)

- G-A estimand: P(adjudicated reference == the stored active value | stored is that active value), re-weighted to the corpus direction shares w_d = N_d/6479 because G-A is a QUOTA arm after the owner's 2026-09-07 ruling (vi): LOWERED is 11.7% of the corpus and 15% of the arm, WITHDRAWN 1.0% and 15%. The unweighted pooled proportion would answer a different question (§14.4).
- G-A weights w_d (corpus shares, re-derived from the frame): RAISED 0.573545, MAINTAINED 0.299429, LOWERED 0.116839, WITHDRAWN 0.010187; nominal n 100, n_eff 84.8 — the quota's cost in effective rows.
- G-A per direction (DISCLOSURE ONLY, no bar, no verdict — rulings (iv), (vi)):
  - RAISED (corpus weight 0.573545): 32/46 = 69.57%  95% Wilson [55.19%, 80.92%]  (+-12.86%) [bar: None]
  - MAINTAINED (corpus weight 0.299429): 16/24 = 66.67%  95% Wilson [46.71%, 82.03%]  (+-17.66%) [bar: None]
  - LOWERED (corpus weight 0.116839): 10/15 = 66.67%  95% Wilson [41.71%, 84.82%]  (+-21.56%) [bar: None]
  - WITHDRAWN (corpus weight 0.010187): 15/15 = 100.00%  95% Wilson [79.61%, 100.00%]  (+-10.19%) [bar: None]
  - disclosure only; no bar (owner rulings 2026-09-07 items (iv) and (vi)). Per-direction Wilson half-widths at p_hat=0.80 are +-11.3 (RAISED), +-15.4 (MAINTAINED), +-19.1 (LOWERED), +-19.1 (WITHDRAWN) points — the quota buys that the value GUIDANCE_MAP sends to -1 stops being literally unmeasured, NOT that it becomes resolved (§14.3). No per-direction number satisfies §6.3's binding caveat; only the pooled re-weighted estimate does.
- G-N estimand: false-NONE rate r = P(adjudicated reference is an active direction | stored is an imputed NONE); an active call is missed on 0.511 * r of guidance-applicable rows
- G-N anchors: holding the labeler fixed, guidance-key omission worsens 33.08% (E1) -> 51.18% (E2), +18.1 pts — a behavioural/corpus response, which is the hypothesis G-N exists to test (§3.3)

## 3. Secondaries — none of them can move a gate

> PROVENANCE: model-consensus agreement (blind rater + adjudicator, both Claude-family) with owner rulings superseding on the escalated subset; NOT human validation of ground truth (HANDOFF §3).
> A non-FAIL is not a clearance (§6.6); red_flags is exploratory / disclosure-only (owner ruling 2026-08-27); this pass cannot change it.


- S-SEC `sentiment` (naive binomial, ignores company clustering): EX99_PRESS_RELEASE 101/119 84.9%; MDA 192/218 88.1%
- S-SECTOR `sentiment` (naive binomial, ignores company clustering): consumer 53/62 85.5%; energy 44/53 83.0%; financials 97/111 87.4%; healthcare 52/55 94.5%; tech 47/56 83.9%
- S-ERA `sentiment` (naive binomial, ignores company clustering): 2019+ 193/226 85.4%; pre-2019 100/111 90.1%
- S-OVERLAP `sentiment` (naive binomial, ignores company clustering): False 269/311 86.5%; True 24/26 92.3%
- S-SELFID `sentiment` (naive binomial, ignores company clustering): False 156/173 90.2%; True 137/164 83.5%
- S-SEC `guidance_direction` (naive binomial, ignores company clustering): EX99_PRESS_RELEASE 115/119 96.6%
- S-SECTOR `guidance_direction` (naive binomial, ignores company clustering): consumer 25/25 100.0%; energy 21/21 100.0%; financials 29/30 96.7%; healthcare 20/22 90.9%; tech 20/21 95.2%
- S-ERA `guidance_direction` (naive binomial, ignores company clustering): 2019+ 78/79 98.7%; pre-2019 37/40 92.5%
- S-OVERLAP `guidance_direction` (naive binomial, ignores company clustering): False 112/116 96.6%; True 3/3 100.0%
- S-SELFID `guidance_direction` (naive binomial, ignores company clustering): False 38/39 97.4%; True 77/80 96.2%
- S-ERR `sentiment` error structure — stored (student) -> reference (adjudicated), P arm, n = 334 scored + 3 omission-pinned nulls: NEGATIVE->NEGATIVE 25; NEGATIVE->NEUTRAL 24; NEUTRAL->NEUTRAL 215; NEUTRAL->POSITIVE 2; POSITIVE->NEUTRAL 15; POSITIVE->POSITIVE 53
  - precision on each STORED value (k/n = rows the reference upheld): NEGATIVE 25/49 = 51.0%; NEUTRAL 215/217 = 99.1%; POSITIVE 53/68 = 77.9%
  - READ THIS BESIDE THE HEADLINE: 39 of the 44 sentiment errors are the student asserting a DIRECTION on a passage the reference calls NEUTRAL. NEUTRAL is 217/334 = 65% of the SCORED stored base and is upheld 215/217 = 99.1% of the time, so the pooled agreement figure is carried by the NEUTRAL mass — structurally the same NONE-mass problem the G-A arm was bought to expose for guidance (§6.3). The two surviving E2 sentiment features are `sentiment_mean_score` and `sentiment_negative_share`; the second consumes exactly the stored-NEGATIVE quantity measured at 25/49 = 51.0% precision.
  - share of reference-NEGATIVE rows whose stored value was NEGATIVE: 25/25. NOT recall against an independent NEGATIVE ground truth. One-directional verification: only disagreements are ever re-checked, so the reference-NEGATIVE set is built from contested rows and this denominator is definitionally near the stored-NEGATIVE-and-upheld set — a value at or near 1.0 is near-structural, not a measurement of NEGATIVE detection.
- S-ERR `guidance_direction` error modes: NONE_to_active 1; active_to_NONE 3; omitted 0
- S-ERR `red_flags` category-level corrections on error rows (disclosure-only): missed_flags 59; spurious_flags 74; wrong_modality 17
- S-CONF `sentiment` by extraction confidence (naive binomial, ignores company clustering): high 247/283 87.3%; low 11/14 78.6%; medium 35/40 87.5%
- S-CONF `sentiment` by extraction status (naive binomial, ignores company clustering): FLAGGED 42/50 84.0%; OK 251/287 87.5%
- S-CONF `guidance_direction` by extraction confidence (naive binomial, ignores company clustering): high 87/91 95.6%; medium 28/28 100.0%
- S-CONF `guidance_direction` by extraction status (naive binomial, ignores company clustering): FLAGGED 28/28 100.0%; OK 87/91 95.6%
- S-GNDEC guidance-key omission, P arm (base-rate-representative): 60/119 = 50.4% 95% Wilson [41.6%, 59.2%] (naive binomial). 'omission' here = the guidance key was not emitted (guidance_imputed_none OR stored null). The P arm is the only base-rate-representative arm, so the omission rate is computed there; the false-NONE split is computed inside G-N.
- S-OVERLAP: powered = False. discharges EXPANSION_PLAN §3 item 2 ('with and without the overlap set'). NOT POWERED AT ANY n THIS PROJECT WILL BUY: ~14 overlap rows of 300 carry a +-18.2 pt Wilson half-width at p_hat=0.85, and no overlap-vs-novel difference of any plausible size is detectable. The 4.53% accession-level figure is a LOWER BOUND on memorization exposure — company-level exposure is 15.85% and boilerplate recurs near-verbatim (§2.5). The headline therefore pools memorized and novel chunks.
- S-OMIT: 'omission' = the student did not emit a value (stored null). The guidance_imputed_none rows are NOT omissions here — the writer rule is adopted and 'NONE' IS the stored label (§1.3); their count is reported separately and arm G-N tests them directly.
  - `sentiment` omission rate 3/337; omission-EXCLUDED agreement 293/334 = 87.72%  95% Wilson [83.77%, 90.82%]  (+-3.53%)
  - `guidance_direction` omission rate 0/119; omission-EXCLUDED agreement 115/119 = 96.64%  95% Wilson [91.68%, 98.69%]  (+-3.51%)
- S-MASK off-matrix census: sentiment on RISK_FACTORS 4177, guidance on MDA 2803, on RISK_FACTORS 23, of which 230 are active values that GUIDANCE_MAP would map to +-1/0
  - REQUIRED F5 CHANGE, filed as a G2 finding (design §3.4): features.py must null sentiment on RISK_FACTORS and guidance_direction on MDA/RISK_FACTORS BEFORE aggregation, with an assertion that the masked count matches this census. Sites: features.py:596 sentiment_mean_score, :602 sentiment_negative_share, :603 guidance_signed_mean, :604 guidance_any_present (all four aggregate with no section filter), and the now-false property statement at features.py:1159.
- S-NOISE ceiling arm: batches ['batch_01', 'batch_02', 'batch_03'] (rated ['batch_01', 'batch_02', 'batch_03'], missing []); 120 rows pooled from ['batch_01', 'batch_02', 'batch_03']
- S-NOISE ceiling `sentiment`: 107/110 = 97.27%  95% Wilson [92.29%, 99.07%]  (+-3.39%) (n 110 of 120 pooled rows after the applicability mask; realized-from-draw 110, §14.5 planned 107) — upper bound BELOW the bar 0.85: False; lower bound clears the bar: True; clearing it needs p_hat >= 91.82%
- S-NOISE ceiling `guidance_direction`: 64/65 = 98.46%  95% Wilson [91.79%, 99.73%]  (+-3.97%) (n 65 of 120 pooled rows after the applicability mask; realized-from-draw 65, §14.5 planned 62) — upper bound BELOW the bar 0.85: False; lower bound clears the bar: True; clearing it needs p_hat >= 93.85%
  - the ceiling is reported beside every bar and CANNOT move any bar or any decision (§5.4). No noise-normalised criterion was adopted and none may be adopted now that the ceiling is known.
  - byte-identical to the originals INCLUDING row order, so raters A and B share any ordering/context effect; this ceiling is UPPER-biased and the true two-rater ceiling is at most this (§14.9, magnitude unmeasured)
- ADJUDICATION LAYER (descriptive; no bar, moves nothing): the adjudicator sided with the blind rater AGAINST the stored student label on 271/314 = 86.3% of contested rows — guidance_direction 31/32 = 96.9%; red_flags 169/193 = 87.6%; sentiment 71/89 = 79.8%. Confidence mix {'high': 53, 'low': 10, 'medium': 251}; 0 'unsure' verdicts in 314 rulings.
  - 'sided_with_rater_against_stored' = the adjudicator overturned the stored student label on a contested (chunk, field) row. Both the blind rater and the adjudicator are Claude-family; the student is Qwen. A high rate is consistent with either a correct student-error finding or with within-family agreement, and this design cannot separate the two (§12.1). Disclosure only — it moves nothing.
- S-PROBE: 20 ids written to probe_ids.json (realized {'G-A': 4, 'P': 12, 'G-N': 4}); ruled 20, overturned 0; escalation_triggered False
  - at this result the agreed mass could be hiding at most 12.53% of the gate-bearing-applicable rows (Wilson upper bound scaled by the uncontested share 77.76%)

## 4. red_flags — DISCLOSURE-ONLY

> PROVENANCE: model-consensus agreement (blind rater + adjudicator, both Claude-family) with owner rulings superseding on the escalated subset; NOT human validation of ground truth (HANDOFF §3).
> A non-FAIL is not a clearance (§6.6); red_flags is exploratory / disclosure-only (owner ruling 2026-08-27); this pass cannot change it.


status: exploratory / disclosure-only (owner ruling 2026-08-27); this pass cannot change it.
- S-RF1 exact-set ERROR: 112/400 = 28.00%  95% Wilson [23.83%, 32.59%]  (+-4.38%)
- S-RF2 per-category-decision ERROR: 150/2400 = 6.25% chunk-clustered bootstrap [5.21%, 7.38%] (naive binomial printed in results_g2.json is ANTI-CONSERVATIVE)
- rewritten RED_FLAG_CAVEAT: E2 red-flag labels are exploratory / disclosure-only (owner ruling 2026-08-27); this pass cannot change it. Measured E2 student exact-set (category+modality) error on a base-rate-representative G2 draw: 112/400 = 28.0% [95% Wilson 23.8%, 32.6%], model-consensus reference, no owner ratification. The E1 constants 36.6%/63.4% were measured on Claude BOOTSTRAP labels and do not describe these labels. This number is disclosure, not evidence for re-promotion; only the owner can revisit the 2026-08-27 demotion.

## 5. Comparison rows — DESCRIPTIVE ONLY, no decision reads them

> PROVENANCE: model-consensus agreement (blind rater + adjudicator, both Claude-family) with owner rulings superseding on the escalated subset; NOT human validation of ground truth (HANDOFF §3).
> A non-FAIL is not a clearance (§6.6); red_flags is exploratory / disclosure-only (owner ruling 2026-08-27); this pass cannot change it.


- epoch-2 eval, sentiment exact match (student vs TEACHER, E1 eval split): other {'k': 725, 'n': 867, 'point': 0.8362168396770473} | G2 {'p_hat': 0.8694362017804155, 'n': 337, 'scale': 'agreement'} [interpretable: False]
- epoch-2 eval, guidance raw exact match (student vs TEACHER, E1 eval split): other {'k': 297, 'n': 570, 'point': 0.5210526315789473} | G2 {'p_hat': 0.9663865546218487, 'n': 119, 'scale': 'agreement'} [interpretable: False]
- epoch-2 eval, red-flag exact-set agreement (student vs TEACHER, E1): other {'point': 0.6307} | G2 {'p_hat': 0.28, 'n': 400, 'scale': 'error'} [interpretable: False]
- H3v2 retention, sentiment_mean_score (filing-level Pearson, n=630 filings): other {'point': 0.8696, 'ci': [0.8153, 0.9109]} | G2 {'p_hat': 0.8694362017804155, 'n': 337, 'scale': 'agreement'} [interpretable: False]
- H3v2 retention, guidance_any_present (filing-level Pearson, n=630 filings): other {'point': 0.7534, 'ci': [0.5356, 0.9114]} | G2 {'p_hat': 0.9663865546218487, 'n': 119, 'scale': 'agreement'} [interpretable: False]
- v1.2 TEACHER spot-check, owner-ratified exact-set ERROR (P1): other {'k': 84, 'n': 200, 'point': 0.42, 'ci': [0.3537, 0.4893]} | G2 {'p_hat': 0.28, 'n': 400, 'scale': 'error'} [interpretable: False]
- DESCRIPTIVE ONLY. Different reference (teacher / feature vector / different labeler), different corpus, different protocol, and in the H3v2 rows a different UNIT (filing-level correlation vs chunk-level proportion). No difference interval is computed — newcombe() is struck (design §7).

## 6. What a non-FAIL does not mean

> PROVENANCE: model-consensus agreement (blind rater + adjudicator, both Claude-family) with owner rulings superseding on the escalated subset; NOT human validation of ground truth (HANDOFF §3).
> A non-FAIL is not a clearance (§6.6); red_flags is exploratory / disclosure-only (owner ruling 2026-08-27); this pass cannot change it.


The G2 spot-check did not trigger a decisive failure for `sentiment`. Measured agreement is 86.94% [82.93%, 90.13%] (n = 337, bar 0.85, model-consensus reference with owner rulings on the escalated subset; NOT human validation of ground truth). At this n the design would have declared a decisive failure with probability 0.18 if true agreement were 0.83 and 0.03 if it were 0.85 — those two numbers are the whole of what this result excludes on the low side, and a true value below the bar is made less likely at those rates, not ruled out. For the gate-bearing fields this estimate is plausibly optimistic (§12.1): the rater's family is the teacher's family, so teacher error the student memorized is invisible to it, biasing measured error low. This is a chunk-level label-accuracy figure; it is NOT the feature-level reliability lambda of EXPANSION_PLAN §2a (§6.5) and must not be used as one. Every E2 feature derived from `sentiment` carries this figure as a stated caveat.

The G2 spot-check did not trigger a decisive failure for `guidance_direction`. Measured agreement is 96.64% [91.68%, 98.69%] (n = 119, bar 0.85, model-consensus reference with owner rulings on the escalated subset; NOT human validation of ground truth). At this n the design would have declared a decisive failure with probability 0.10 if true agreement were 0.83 and 0.03 if it were 0.85 — those two numbers are the whole of what this result excludes on the low side, and a true value below the bar is made less likely at those rates, not ruled out. For the gate-bearing fields this estimate is plausibly optimistic (§12.1): the rater's family is the teacher's family, so teacher error the student memorized is invisible to it, biasing measured error low. This is a chunk-level label-accuracy figure; it is NOT the feature-level reliability lambda of EXPANSION_PLAN §2a (§6.5) and must not be used as one. Every E2 feature derived from `guidance_direction` carries this figure as a stated caveat. Binding, ruling (vii): this number is a base rate over the NONE mass and is never quoted alone — guidance_active_precision 68.67% 95% Wilson [58.17%, 77.55%] (corpus-re-weighted; n_eff 84.8 of nominal n 100); guidance_false_none_rate 0/80 = 0.00%  95% Wilson [0.00%, 4.58%]  (+-2.29%).

## 7. Frame re-derivation and limits

> PROVENANCE: model-consensus agreement (blind rater + adjudicator, both Claude-family) with owner rulings superseding on the escalated subset; NOT human validation of ground truth (HANDOFF §3).
> A non-FAIL is not a clearance (§6.6); red_flags is exploratory / disclosure-only (owner ruling 2026-08-27); this pass cannot change it.


- n_frame: observed 316291 vs design 316291 -> match True
- section_counts: observed {'MDA': 172098, 'EX99_PRESS_RELEASE': 94545, 'RISK_FACTORS': 49648} vs design {'MDA': 172098, 'EX99_PRESS_RELEASE': 94545, 'RISK_FACTORS': 49648} -> match True
- ga_frame: observed 6479 vs design 6479 -> match True
- gn_frame: observed 48293 vs design 48293 -> match True
- train_overlap_rows: observed 14342 vs design 14342 -> match True
- selfid_share: observed 0.4646290915644138 vs design 0.4646 -> match True
- manifest_arm_frames: observed {'G-A': 6479, 'G-N': 48293, 'P': 316291} vs design {'P': 316291, 'G-A': 6479, 'G-N': 48293} -> match True
- 8K_BODY (790 chunks, 0.249%) is excluded by predicate; bounded influence <= 0.25 pts all-section, <= 0.30 sentiment, <= 0.83 guidance (§2.3)
- the occurrence-weighted estimand is out of reach (Kish n_eff ~ 8.9 at n=300); features consume a weighted rate this design cannot estimate (§2.4)
- the extension stratum was never labeled; the 2026-08-21 'unseen sectors' promotion clause is DEFERRED, not satisfied (§7)
- G2 supplies chunk-level label accuracy ONLY. It does not supply EXPANSION_PLAN §2a's feature-level reliability lambda (§6.5).

