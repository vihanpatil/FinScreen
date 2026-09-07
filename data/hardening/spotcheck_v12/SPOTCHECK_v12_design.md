# v1.2 TEACHER SPOT-CHECK — pre-registered design

**Council condition 1** (`data/hardening/status/G1_council_advisory.md` §6 item 1,
§7 item 1), owner-ratified 2026-08-27 evening with **B1 sequencing**: this pass
completes before F4's first overnight.

**Status: PRE-REGISTERED 2026-08-27. Written before any rater verdict exists.**
The draw is fixed (`build_draw_v12.py`, seed 20260827), the batch files are
written, and the analysis is fixed *in code* (`analyze_v12.py`) — estimators,
Wilson convention, the `unsure` rule, the integer kill-threshold and the
owner-probe draw are all pinned before data. Any change after the first verdict
lands is a new pre-registration with a named reason, not an edit.

**Provenance rule (HANDOFF §3, §7).** Everything this pass produces is
*model-consensus agreement with owner rulings on the escalated subset*. It is
**not** human validation of ground truth. Both raters are the same model family
as the teacher, so **shared bias is invisible to this design** and the measured
error is plausibly biased **low**. That asymmetry is load-bearing for the kill
rule and is restated in §6.4.

---

## 1. The estimand, and why it exists

`H3v2_attenuation.md` reports student-vs-teacher retention (12-flag family
0.8078 [0.7503, 0.8528]) against a teacher whose own error is **unmeasured**
(H3v2 §3.7 caveat 3). The v1.1 constants that travel in v1.2 manifests —
36.6% sample-pooled, ~25% Tier C, 7.5% per-category — are properties of a
*different rubric's* labels and must stop traveling (advisory §6 condition 4).

**Estimand (primary):** the probability that a chunk drawn uniformly from the
6,747-row v1.2-labeled corpus carries a stored `red_flags` set — as a set of
(category, modality) pairs — that an adjudicated independent re-rating rules
**incorrect** under rubric v1.2.

Same definition as v1.1's exact-set rate, so the two are comparable in
*construction*. They are not comparable in *target* (§5.3).

Not the estimand: student error, E2 labeling error, or any statement about the
E2 corpus. This measures the teacher, on E1 chunks, under v1.2.

---

## 2. The draw

### 2.1 Frame — all 6,747 rows of `data/labels_v12.parquet`

Verified: `parse_ok`, `schema_valid`, `api_result_type='succeeded'` and
`rubric_version='v1.2'` on **all 6,747** rows; zero null `red_flags`.

- **`CHK-8e69547e0900a8dd` is IN frame.** E1's v1.1 safety-refusal row labeled
  successfully under v1.2 (`stop_reason=end_turn`, two REALIZED flags). Its
  exclusion from the frozen fine-tune split is irrelevant here: the estimand is
  teacher error over the labeled corpus.
- **No train/eval weighting**, for the same reason. Split membership carries no
  information about teacher error, and the v1.1→v1.2 churn rates on the two
  sides are indistinguishable (27.39% train vs 28.02% eval,
  `LABEL_SHIFT_v11_v12.md` §4).

### 2.2 n = 200, stratified proportionally by `section_type`

| stratum | corpus | share | drawn |
|---|---|---|---|
| MDA | 3,962 | 58.72% | **117** |
| RISK_FACTORS | 1,606 | 23.80% | **48** |
| EX99_PRESS_RELEASE | 1,171 | 17.36% | **35** |
| 8K_BODY | 8 | 0.119% | **0** |

Hamilton (largest-remainder) allocation, seed **20260827**, one child RNG
stream per stratum so the draw is independent of iteration order. Batches are a
seeded permutation of the 200 (§7.1), so no batch is section-homogeneous —
rater drift cannot be confounded with section.

**Why stratify at all**, given that "base-rate-representative" only requires an
SRS: (i) it removes sampling noise from the section mix, which matters because
RISK_FACTORS was the weakest section in v1.1 (59.2% red-flag agreement,
71/120) and churned hardest v1.1→v1.2 (41.59% of rows changed); (ii) under
proportional allocation Var(p̂) = Σ W_h p_h(1−p_h)/n ≤ p(1−p)/n, so **the
binomial Wilson interval used as the primary analysis is conservative by
construction** — it can only be too wide, never too narrow.

**8K_BODY gets zero, and that is the representative answer.** The stratum is
0.119% of the corpus; drawing even one row would over-represent it ~4×. Its
error is unmeasured and cannot move the pooled estimate by more than 0.12 pts.
Stated, not hidden.

**No FPC.** 1 − 200/6,747 → the finite-population correction would narrow the
interval by 1.5%. Omitted, i.e. conservative.

**No clustering correction on the primary.** A design effect arises from
*cluster sampling*, not from an SRS of elements drawn from a clustered
population; the chunk-level Wilson interval is correct as-is. Separately
verified against the HANDOFF near-duplicate hard rule: **0 of 28,378 paragraphs
appear in more than one chunk** (dedup is already enforced at chunk
construction), 0 exact-duplicate chunk texts, 9 normalized-duplicate texts out
of 6,747. The near-duplicate 8-K/10-Q multiplicity problem is handled upstream,
not assumed away. Clustering *does* bite the per-category-decision rate, where
the chunk is the cluster — handled in §6.2 (S2).

### 2.3 Realized composition of the drawn 200 — including what went wrong

| property | draw | corpus | verdict |
|---|---|---|---|
| flag-present rows | 65.0% | 66.90% | in line |
| mean flags/chunk | 1.115 | 1.177 | in line |
| v1.1→v1.2 changed rows | 55 (27.5%) | 27.48% | essentially exact |
| distinct tickers | 25 of 25 | — | full spread (max 27 rows/ticker) |

| category | drawn | expected | note |
|---|---|---|---|
| MARGIN_COST_PRESSURE | 65 | 60.2 | — |
| LEGAL_REGULATORY_ACTION | 68 | 65.7 | — |
| TRADE_POLICY_EXPOSURE | 27 | 20.8 | +1.4σ |
| IMPAIRMENT_WRITEDOWN | 24 | 30.5 | −1.3σ |
| DEMAND_WEAKNESS | **27** | 38.9 | **−2.1σ**, P(≤27) ≈ 0.033 |
| SUPPLY_INPUT_CONSTRAINT | **8** | 16.8 | **−2.2σ**, P(≤8) ≈ 0.020 |

**Disclosed, not repaired.** The draw machinery was verified unbiased (300
alternative seeds reproduce the theoretical means, 16.74 vs 16.81 and 38.21 vs
38.92); this particular draw is a genuine ~2–3% lower tail on two categories.
Re-drawing on a different seed *after seeing the composition* would be
seed-shopping — a post-hoc design choice of exactly the kind §7 of the charter
forbids. The seed was fixed by rule (the design date), before inspection.

Consequence, stated up front: the **primary estimator is unaffected** — under
stratified SRS it is unbiased and this variability is already inside the Wilson
interval. The **S4 per-category secondary for SUPPLY_INPUT_CONSTRAINT is
effectively dead** (n=8, ≈ ±30 pts) and DEMAND_WEAKNESS is degraded (n=27,
≈ ±16 pts). Those two rows will be reported with their counts and their useless
intervals, not quietly dropped.

---

## 3. Power — what n=200 can and cannot adjudicate

### 3.1 Precision (Wilson, 95%, half-width in points)

| n | p=0.20 | p=0.25 | p=0.35 |
|---|---|---|---|
| 36 (**v1.1 Tier C**) | ±12.6 | **±13.7** | ±15.0 |
| 150 | ±6.4 | ±6.9 | ±7.5 |
| **200** | **±5.5** | **±6.0** | **±6.6** |
| 250 | ±4.9 | ±5.3 | ±5.9 |
| 300 | ±4.5 | ±4.9 | ±5.4 |

The council's "n≈200 gives roughly ±6–7 pts" is **verified**: ±6.0 at 25%
error, ±6.6 at 35%. n=200 shrinks the v1.1 Tier C interval by a factor
√(200/36) = 2.36.

### 3.2 The kill rule's operating characteristic

Rule (advisory §7 item 1): **demote iff the Wilson lower bound on exact-set
error is strictly greater than 0.35.**

| n | k* (smallest error count that demotes) | p̂* | LB at k* |
|---|---|---|---|
| 150 | 64 | 0.4267 | 0.3503 |
| **200** | **84** | **0.4200** | **0.3537** |
| 250 | 103 | 0.4120 | 0.3528 |
| 300 | 122 | 0.4067 | 0.3526 |

Power (exact binomial, P(k ≥ k*)) at true error:

| n | 0.30 | 0.35 | 0.40 | **0.45** | 0.50 |
|---|---|---|---|---|---|
| 150 | 0.001 | 0.031 | 0.279 | 0.744 | 0.970 |
| **200** | **0.000** | **0.024** | **0.306** | **0.822** | **0.990** |
| 250 | 0.000 | 0.024 | 0.372 | 0.898 | 0.998 |
| 300 | 0.000 | 0.024 | 0.428 | 0.942 | 1.000 |

**The honest one-line power statement, to be quoted with the result every
time:** *n=200 has 82% power to trigger demotion if the v1.2 teacher's true
exact-set error is 45%, 99% at 50%, and only 31% at 40%; the false-demote rate
when true error is exactly at the 35% bar is 2.4%.*

**Why 200 and not more.** n=250 buys +7.6 power points at true error 0.45 for
+25% campaign cost and ~+12 owner rulings; n=300 buys +12.0 points for +50%
cost. n=150 loses 7.8 points. 200 is the knee, and the binding currency is
owner adjudication attention, not machine time (§6.3).

### 3.3 What a non-trigger does and does not mean

A non-trigger is **not** a clearance. Pre-registered wording for the report:

> The spot-check did not trigger the demotion rule. Measured teacher exact-set
> error is p̂ [LB, UB] (n, model-consensus reference, plausibly biased low).
> The design had 82% power against a true error of 45% and 31% against 40%, so
> teacher error anywhere in roughly 0.30–0.42 is **not excluded** by this
> result. Every E2 red-flag number carries this figure as its denominator.

### 3.4 No oversample arm — the arithmetic

The brief asked whether a pre-registered flag-present oversample is needed for
category-level power. It is not worth it, and the numbers say why:

- Flag presence is dominated by the two common categories. A **+40-row
  flag-present oversample** would add ≈ 5 SUPPLY_INPUT_CONSTRAINT rows and ≈ 11
  DEMAND_WEAKNESS rows — it does not fix the categories that are actually thin.
- An arm that *would* fix them is a v1.1-style per-category quota (25 rows ×
  3 thin categories): **+75 chunks (+37% campaign), ~+25 owner rulings**, for a
  secondary metric that **cannot trigger the kill rule** and would have to be
  reported un-pooled anyway.
- The category-level question is better answered by the estimator that already
  has precision: **S2**, the per-category-decision rate over n×6 = 1,200
  decisions (≈ ±2 pts at 7–8% error, cluster-corrected). That is the "is any
  single category call right" question; S4 answers "is this category's rate
  right" and gets honest wide intervals.

Decision: **one draw, no oversample arm.**

---

## 4. Scope — `red_flags` only

The auditors judge **`red_flags` (category + modality) and nothing else.**
`sentiment`, `guidance_direction` and `distress_tier` are not judged.

Justification:

1. The council scoped it red-flags-focused (advisory §6 item 1); red-flag
   features are the ones whose retention numbers lack a denominator.
2. **Rubric v1.2 changed nothing in §2 (sentiment) or §3 (guidance)** — the
   revision log is explicit that all three changes are in the red-flag/modality
   half — and the teacher's labels barely moved: sentiment changed on 4.59% of
   applicable rows, guidance on 1.19% (`LABEL_SHIFT_v11_v12.md` §1). The v1.1
   measurements (sentiment 94.6% [91.3, 96.7]; guidance 95.2% [90.4, 97.6])
   therefore remain the best available estimates and **transport with a stated
   caveat**: *"measured under rubric v1.1; §2/§3 unchanged in v1.2 and 4.6% /
   1.2% of labels moved, so the estimate is carried forward, not
   re-measured."* This is the one place where a v1.1 constant may still travel,
   and only with that sentence attached.
3. `distress_tier` is excluded from every headline metric by standing hard rule
   (HANDOFF §7), so re-measuring it cannot feed a gate.
4. Scope is the **largest available lever on owner attention** (§6.3): in v1.1,
   30 of the 104 owner rulings were on non-red-flag fields.

---

## 5. Blindness — one real change from the v1.1 protocol

### 5.1 True blindness, mechanical comparison

In v1.1 the `label-auditor` agent was handed the **stored labels** and asked to
form its own first and then self-report agree/disagree (agent spec, Input +
binding rule 3). That is anchor-resistant self-report, not blindness, and it
biases agreement **up**.

For v1.2: **the batch files contain `{chunk_id, text}` and nothing else.**
Verified by assertion in `build_draw_v12.py` — no stored label, no
`section_type`, no ticker, no filing date. The rater emits its own label set;
**agreement is computed mechanically by `analyze_v12.py`**, never self-reported.
This removes the "agreeing to be agreeable" failure mode structurally instead
of instructing against it.

Withholding `section_type` is also required for symmetry: rubric §8.2 forbids
`section_type` from appearing as prompt text for the teacher, so a rater that
saw it would be operating on strictly more information than the labeler it is
auditing. `red_flags` is asked on all four section types, so the applicability
matrix needs nothing from it.

Residual risk: the rater agents hold `Read`/`Grep`/`Glob`. The launch prompt
(§7.2) forbids reading anything outside its batch file. `draw_v12.csv` is
**label-free by design** so that even reading it cannot break blindness; stored
labels are joined only at analysis time.

### 5.2 The v1.1 asymmetry this design corrects

Recomputed from `spotcheck/combined_judgments.csv` (2026-08-27):

- 399 evaluable `red_flags` judgments → **148 contested** by the auditor.
- Of those 148, adjudication ruled the **stored label wrong in 146** and right
  in **2**. Uphold rate **98.6%**.
- Owner rulings overturned the model adjudicator on **2 of 74** rows (2.7%).
- Contested rate ≈ final error rate in every tier: A 41.4% vs 40.7%, B 30.5% vs
  30.5%, C 25.0% vs 25.0%, D 48.3% vs 46.7%.

Two consequences. (i) **The adjudication stage barely moved the number** (0.5
pts) — it buys legitimacy and briefs, not accuracy. (ii) More seriously, the
design is **one-directional**: only auditor-disagreements were ever checked, so
the pipeline can lower the error estimate but never raise it. Rows where both
the teacher and the auditor are wrong the same way are structurally invisible.

Fix, cheap: **S8, a 20-row owner-read probe of the uncontested set** (§6.4).
It is the only arm not made of model consensus.

### 5.3 Comparability with v1.1's Tier C

The v1.1 base-rate-representative arm is **Tier C: 9/36 = 25.0% [13.8, 41.1]**.
Its frame was the *residual* pool after the exhaustive strata were removed, so
it is not literally an SRS of the corpus. Quantified rather than waved at: the
only strata removed exhaustively were all 162 distress positives (2.40% of the
corpus, tier error 40.7%) and all 83 non-NONE guidance rows (1.23%, 30.5%);
B3/D removed only 60 rows each from much larger pools. Re-weighting gives a
frame-corrected v1.1 corpus estimate of **25.45%, a +0.45 pt bias** — negligible
inside its own ±13.7 pt interval.

So the frame difference is **not** the reason the two numbers are
incomparable. The reason is that **the rubric changed**: a v1.1 label judged
under v1.1 and a v1.2 label judged under v1.2 are answers to different
questions. The comparison row is computed (Newcombe interval for the
difference) and is marked **DESCRIPTIVE ONLY — no decision reads it.**

---

## 6. Pre-registered analysis (`analyze_v12.py`)

### 6.1 P1 — the primary estimator and the decision

Per chunk, the reference set is built deterministically:

| situation | reference | error |
|---|---|---|
| rater set == stored set | stored | 0 |
| contested, adjudicator/owner verdict `disagree` | `correct_label` | 1 |
| contested, verdict `agree` | stored | 0 |
| contested, verdict `unsure` (or unruled) | — | **non-evaluable** |

Owner rulings supersede model adjudications on the rows the owner rules.

p̂ = errors / n_evaluable; **95% Wilson, z = 1.96, no continuity correction, no
FPC.**

**Decision, operationally.** At n_evaluable = 200: **demote iff k ≥ 84**
(p̂ ≥ 0.4200 → LB = 0.3537). At k = 83, p̂ = 0.4150 → LB = 0.3492 → **no
demote**. The rule is a **strict** inequality: LB exactly 0.35 does not demote.
If n_evaluable ≠ 200, k* is recomputed by the same pinned function
(`kstar()`), never by judgement.

If it triggers: the E2 red-flag feature family is demoted to
exploratory/disclosure-only in G3, **regardless of sunk F4 overnights**
(advisory §7 item 1). Sentiment and composition features are unaffected.

**`unsure` rule, pinned now:** unsure rows are non-evaluable, removed from
numerator and denominator, counted in the report, and bracketed by a
pre-registered two-sided sensitivity (all non-evaluable as error / all as
agree). v1.1 ran 7 unsure of 148 contested (4.7%), so expect ~2–4 rows and a
bracket of ≈ ±2 pts.

### 6.2 Secondaries — **none of them can trigger the kill rule**

- **S1 category-set-only error** (modality ignored). P1 − S1 is the share of
  exact-set error that is purely modality. Pre-named because v1.2's dominant
  change was modality: 300 LEGAL_REGULATORY_ACTION HYP→REAL, and the corpus
  REALIZED share moved 54.48% → 60.16%.
- **S2 per-category-decision error** over n×6 = 1,200 decisions, with a
  **chunk-clustered bootstrap CI** (10,000 resamples of chunks, seed 20260827).
  The naive binomial interval is printed beside it and explicitly labeled
  anti-conservative. *Correction to standing practice:* v1.1's per-category
  figure **7.5% [91.4, 93.5] over 2,394 decisions was the naive interval** —
  the 6 decisions inside a chunk are not independent, so that interval is too
  narrow. The v1.2 number will not repeat the error, and any side-by-side
  quote must say which basis each interval uses.
- **S3 per-section error** (MDA n=117 ≈ ±7.7 pts; RISK_FACTORS n=48 ≈ ±11.9;
  EX99 n=35 ≈ ±14.0). RISK_FACTORS is the pre-named focus.
- **S4 per-category error**, on two bases reported separately: rows where the
  *stored* label carries the category (precision-like) and rows where the
  *reference* does (recall-like). Intervals are wide by construction; SUPPLY is
  dead at n=8 (§2.3).
- **S5 error split by v1.1→v1.2 changed (55 rows) vs unchanged (145)** —
  whether the repair fixed or churned. ±10 / ±7 pts. Declared secondary;
  neither subgroup can trigger anything.
- **S6 error-mode decomposition** into spurious / missed / wrong-modality
  category-level corrections, the v1.1 taxonomy. Descriptive counts, no CI.
- **S7 rater-noise arm**: batch 1 (n=40) is re-rated by a **second independent**
  `label-auditor` instance. Reports rater-vs-rater exact-set agreement, which
  bounds how much of P1 is rater noise rather than teacher error. **Rater A is
  the primary rater for all 200; this arm never feeds P1.** Zero owner load.
- **Comparison row** vs v1.1 Tier C with a Newcombe difference interval,
  carrying the §5.3 caveats. Descriptive only.

### 6.3 Owner-adjudication load

Model, calibrated on v1.1: contested ≈ error rate; needs_human ≈ 50% of
contested (74/148); owner rules the needs_human set.

| if true error is | contested | needs_human (~50%) | + S8 probe | **owner items** |
|---|---|---|---|---|
| 25% (v1.1 Tier C) | ~50 | ~25 | 20 | **~45** |
| 30% | ~60 | ~30 | 20 | **~50** |
| 35% | ~70 | ~35 | 20 | **~55** |
| 42% (at the threshold) | ~84 | ~42 | 20 | **~62** |

**~45–62 owner-visible items**, against v1.1's 104 and the council's 50–100
estimate — at the low end of the council's band. The saving comes from scope
(§4), not from cutting verification.

Honest note on pattern-block ratification: v1.1's adjudicator emitted **90
distinct pattern slugs across 148 contested chunks, 58 of them singletons**
(≈1.6 chunks per pattern). Blocking by pattern reduces *reading* effort but is
not a large lever on item count. It is still used — the owner rules once per
pattern where a pattern repeats.

**Sequencing note for B1.** The owner is not the critical path for the number.
In v1.1 the owner overturned 2 of 74 adjudications (2.7%), moving the headline
by 0.5 pts. So `analyze_v12.py` produces two labeled estimates: a
**model-consensus estimate** (adjudicator-final, zero owner load, available as
soon as adjudication lands) and an **owner-ratified estimate** (owner rulings
superseding on the escalated subset). The kill rule reads the latest available
one at G3 ratification, and both are reported with their provenance. Expected
gap < 1 pt on the v1.1 record. B1 sequencing therefore does not require the
owner's full attention before F4's first overnight — only before G3.

### 6.4 S8 — the 20-row owner probe of the *uncontested* set

The one arm that is not model consensus, and the fix for §5.2's
one-directional verification.

- `analyze_v12.py` writes `probe_ids.json`: **20 chunks drawn seeded
  (20260827) from the rows where the rater matched the stored label.** Drawn
  after rating, by pinned code, so it cannot be curated.
- The owner reads text + the (agreed) label and rules agree/disagree.
- Reported as k/20 with a Wilson interval on **hidden shared error**. At 0/20
  the 95% upper bound is 16.1% — a weak but honest bound, and 0.65 × 16.1% ≈
  10 pts is the most the uncontested mass could be hiding. That sentence ships
  with the result.
- **Pre-committed extension (the only one):** if **≥ 2 of 20** are overturned,
  every uncontested row goes to the adjudicator **once**, and P1 is recomputed
  with that correction. Under a true hidden-error rate of 5% this fires with
  probability 0.26; under 15%, 0.82. It costs ~4 more adjudicator agent runs
  ($0) and no new sampling.

---

## 7. Ops — what the main session executes

### 7.1 Files (all under `data/hardening/spotcheck_v12/`)

```
build_draw_v12.py          the draw (already run; reproducible, seed 20260827)
draw_v12.csv               200 rows: rank, batch, chunk_id, section_type,
                           home_ticker, word_count   <- LABEL-FREE
draw_manifest.json         seed + source sha256 + allocation + counts
batches/batch_01..05.json  5 x 40 chunks, {chunk_id, text} only
batches/batch_01_replicate.json   same 40 as batch 1, for S7
build_adjudicator_batches_v12.py  contested rows -> adjudicator batches
analyze_v12.py             the pre-registered analysis
--- produced by the campaign ---
verdicts/rater_a_batch0N.json     one per auditor agent, then concatenated to
verdicts/rater_a.json             (all 200)
verdicts/rater_b_batch01.json     the S7 replicate
adjudications/adjudications.json  concatenated adjudicator output
owner_rulings.json                owner verdicts (supersede)
probe_ids.json / probe_rulings.json   S8
results_v12.json                  every pre-registered number
```

Batch load: 40 chunks, 15.7k–18.0k words each (~21–24k tokens) — comfortably
one opus agent per batch.

### 7.2 Agents

**6 `label-auditor` runs** (5 batches + 1 replicate of batch 1), each a
separate agent instance so the rating is independent. The batch file contradicts
the agent's own Input section (which expects stored labels); the launch prompt
overrides it explicitly:

> Read `labeling_rubric.md` in full, then read
> `data/hardening/spotcheck_v12/batches/batch_0N.json`. **This is the BLIND
> variant of the protocol: the batch contains no stored labels, no section
> type, no ticker and no dates, by design — there is nothing to compare
> against and nothing to agree with.** Your job is to produce your OWN
> `red_flags` label for each of the 40 chunks under rubric v1.2 §4 and §6
> (category + modality). Judge `red_flags` only — do not label sentiment,
> guidance_direction or distress_tier. **Do not read any other file under
> `data/`** (in particular no `labels*.parquet` and no other file in
> `spotcheck_v12/`); your batch file is self-contained. Return, as your final
> message, one JSON array and no prose:
> `[{"chunk_id": "...", "red_flags": [["CATEGORY","MODALITY"], ...],
> "reason": "one sentence citing the passage's own decisive words"}]`
> — empty list where the passage carries no flag. A `reason` is required on
> every chunk, including empty ones; it becomes the adjudicator's input.

(If the main session prefers, a sibling `label-rater-blind` agent whose spec
matches this prompt is equivalent and tidier. The load-bearing property is the
batch file, not the agent name — and that property is asserted in code.)

**`label-adjudicator` runs:** `build_adjudicator_batches_v12.py` emits ~2–3
batches of ≤ 40 contested rows (expected 50–70 contested). Existing agent, used
as specified 2026-08-18; input carries chunk text, stored label, rater label +
reason, and `high_stakes=false` throughout (there is no distress arm here).

**Owner:** the needs_human set + the 20 S8 probe rows (§6.3, §6.4). Reuse
`spotcheck/build_adjudication_view.py` if a rendered view is wanted.

### 7.3 Order of operations

1. `python3 data/hardening/spotcheck_v12/build_draw_v12.py` — done; re-run only
   to verify byte-identity.
2. Launch 6 auditor agents; write each result to
   `verdicts/rater_a_batch0N.json` (and `verdicts/rater_b_batch01.json`);
   concatenate the five A batches into `verdicts/rater_a.json`.
3. `python3 .../build_adjudicator_batches_v12.py` → `adjudicator_batches/`.
4. Launch the adjudicator agents; concatenate into
   `adjudications/adjudications.json`.
5. `python3 .../analyze_v12.py` → model-consensus estimate + `probe_ids.json`.
6. Owner rules the needs_human set and the 20 probe rows →
   `owner_rulings.json`, `probe_rulings.json`.
7. Re-run `analyze_v12.py` → owner-ratified estimate; if S8 fired, run the one
   pre-committed extension and re-run once more.

---

## 8. Stopping rule for the campaign

Pre-committed now, so no future self can extend the sample toward a
threshold:

1. **One draw. n=200. Seed 20260827. No re-draws, no top-ups, no adaptive n.**
   If the result lands near k*=84, that is the answer.
2. The **only** extension is S8's escalation (≥2/20 overturned → adjudicate all
   uncontested rows once, recompute P1). It fires at most **once** and adds no
   new chunks.
3. A **failed batch** (agent error, malformed output) is re-run on the **same
   chunk ids**, up to twice. Re-running a batch is not a re-draw. If a batch
   still cannot be completed, its chunks are reported non-evaluable and n is
   restated — **never replaced with fresh chunks**, because replacement is a
   selection channel.
4. If `labels_v12.parquet` changes, `build_draw_v12.py` **fails its sha256
   assertion**. A changed frame requires a new pre-registration.
5. The campaign is complete when steps 7.3.1–7.3.7 have run once. Anything
   further is a new, named, ratified measurement.

---

## 9. What this design cannot show

1. **It is model consensus.** Two instances of the same model family plus an
   adjudicator of that family. Shared bias is invisible; the estimate is
   plausibly biased **low**. The 20-row owner probe bounds this weakly (±~10 pts
   of hidden mass at 0/20) and is the only non-model check.
2. **A non-trigger is not a clearance** (§3.3). Error in 0.30–0.42 is not
   excluded.
3. **It measures the teacher, not the student, and not E2.** Nothing here
   licenses a statement about E2 labeling quality; it supplies the denominator
   that H3v2's retention numbers currently lack.
4. **The v1.1 comparison is descriptive.** The rubric moved; the two numbers
   answer different questions (§5.3). "The repair worked" is still forbidden
   without the +0.0904 / +0.0481 teacher-arm split beside it (advisory §6
   condition 3).
5. **8K_BODY is unmeasured** (0.12% of corpus, bounded influence ≤ 0.12 pts).
6. **Per-category precision is weak by design**, and this particular draw made
   SUPPLY_INPUT_CONSTRAINT (n=8) and DEMAND_WEAKNESS (n=27) weaker still
   (§2.3). Those are exactly the two categories where the student is also
   weakest (DEMAND_mda retention 0.4238) — so the "weak feature" story will
   remain partly unresolved after this pass. Named now, so it is not
   rediscovered as a surprise later.

---

## 10. Provenance

| item | value |
|---|---|
| `data/labels_v12.parquet` sha256 | `ca373b953504535b2f35ee374a6b6c1a6360000261748db365ee23c231e475e7` |
| `labeling_rubric.md` sha256 | `46dea3c886846849c82ae2b65d8e29ef95016dece706cd19a2e00b8d99c30b25` |
| seed | 20260827 (draw, batching, bootstrap, probe) |
| API calls | **0** — agent lane, subscription, spend freeze untouched |
| authority | advisory §6 condition 1 / §7 item 1; owner ratification 2026-08-27 evening, B1 sequencing |
| sources re-derived for this design | `spotcheck/combined_judgments.csv`, `spotcheck/adjudicator_verdicts.json`, `spotcheck/README.md`, `RED_FLAGS_LIMITATION.md`, `data/hardening/LABEL_SHIFT_v11_v12.md`, `labeling_rubric.md` v1.2, `data/labels_v12.parquet`, `data/labels.parquet` |
