# LENS 2 — METHODOLOGY AUDIT (E2 design, end-to-end)

*Written 2026-08-25 for the owner-commissioned four-lens re-evaluation.
Read-only pass: no pipeline file was edited, no network call was made. Every
number below is either quoted from a repo artifact with its file named, or
re-derived by me from frozen artifacts with the computation described. My
replication of `data/backtest_report.md` / `data/diagnosis_report.md`
reproduces the published per-fold deltas **exactly** (−0.1275, −0.0078,
−0.0399, 0.0183, −0.0004, 0.0992; mean −0.0097; dedup fold sizes
44/40/39/37/45/32), so where I disagree with a published number below, the
disagreement is about method, not about arithmetic.*

---

## 0. Bottom line, up front

The **infrastructure** in this repo is better than most professional
sell-side and a large fraction of published academic work: point-in-time
fundamentals with restatements preserved, expanding-window walk-forward
sorted by filing date, explicit near-duplicate deduplication with a
form-aware tie-break, a form-controlled ablation, every-occurrence label
attribution, a pre-committed acceptable null, and a censoring census that
refuses to silently drop anything. F2's catch that **45% of filings are
accepted after 16:00 ET while carrying that day's `filing_date`**
(`data/F2_INGESTION_REPORT.md` §3.3) is a first-class find that most
practitioners never make.

The **estimand** is the problem. E2 is a higher-powered rerun of a
measurement whose dominant component is not text and not fundamentals but
**company identity**. I verified this directly:

| predictor | cross-fold mean dedup Spearman IC (2025Q1–2026Q2) |
|---|---|
| rank by `log_total_assets` alone (one near-constant-per-company variable) | **0.224** |
| rank by the ticker's *training-window* mean excess return (zero features) | **0.187** |
| the shipped **numeric-only XGBoost** (10 fundamentals) | **0.097** |
| the shipped **text+numeric XGBoost** (32 features) | **0.088** |

The entire modeling apparatus is beaten by sorting 25 stocks by size. Both
arms of the comparison are dominated by the same company-persistence
component (I measure their per-fold prediction correlation at Pearson
0.63–0.92, mean 0.83), so the estimand — the text-minus-numeric delta — is a
small residual riding on a large shared term. That is why it is so noisy,
why it flips sign fold to fold, and why more folds and more companies will
buy a *more precise measurement of a confounded quantity* unless the
specification changes.

The single most damaging fact I found: **one routine, defensible,
look-ahead-free preprocessing choice moves the headline delta by 0.056** —
from −0.0097 (raw levels, as shipped) to +0.0467 (PIT trailing
cross-sectional percentile ranks) — which is roughly **three times E2's
entire optimistic MDE of 0.019**. E2's designed precision is smaller than
its own unpre-registered specification sensitivity. Neither result is
statistically distinguishable from zero; that is exactly the point.

E2 is not a waste. It is under-specified in the places that decide whether
either outcome is believable, and those places are cheap to fix — days, not
weeks, and mostly before F3 rather than after F5.

---

## (a) The power analysis: is the 0.019–0.037 MDE bracket credible, and is the bounded null honest?

### What the power work gets right

`data/expansion_recon_2026-08-20.json` `power.method` is a genuinely good
piece of work. It runs a real simulation (20,000 reps/cell, verified against
the analytic 1/√(n−1) SE), it constructs an honest optimistic/pessimistic
**bracket** rather than a fake point estimate, it names the identification
failure out loud ("the two-point c/n+floor fit is infeasible (floor =
−0.016)... identification behind any single point inside them is close to
zero"), and caveat (3) states the correct target — that the design question
is *what MDE makes the null meaningful*, not *how do we find an effect*.
The framing "a null at MDE m bounds the true delta within roughly ±m/1.4" is
the right logic and is applied correctly.

I found four defects. Three make the bracket **too optimistic**; one is
good news the recon left on the table.

### Defect 1 — the noise anchor uses a population std over 6 numbers (ddof=0)

`diagnose.py:222` computes `std_delta_dedup_vs_numeric` as
`d_dedup.std(ddof=0)`. `backtest.py:513, 689, 693, 781` do the same. The
published anchor **0.0677** is therefore the *population* std of the six
fold deltas. The unbiased sample std is **0.0742**.

Every MDE in `EXPANSION_PLAN.md` §2a inherits a **√(5/6) = 0.913** factor:
the 0.019–0.037 bracket should read **0.021–0.041** on this correction
alone. Small, but it is a systematic optimism in the exact number the owner
is being asked to accept a null against.

### Defect 2 — the anchor's own sampling error is ignored, and it is enormous

The anchor is a standard deviation estimated from **5 degrees of freedom**.
Its 95% chi-square confidence interval is:

```
95% CI on the noise anchor:  [0.0463, 0.1820]   (point estimate 0.0742)
```

A **3.9× range**. The recon's caveat list covers the structural floor, fold
non-independence, estimand shift and per-family scaling — it does not cover
the fact that the number everything is anchored to is known only to within
a factor of four. Propagating it through the pessimistic (all-floor,
26-fold) endpoint:

| anchor value | MDE at 26 folds, all-floor endpoint |
|---|---|
| 0.0463 (CI low) | 0.025 |
| 0.0742 (point) | 0.041 |
| 0.1820 (CI high) | 0.100 |

So the honest bracket, propagating anchor uncertainty, is roughly
**0.012–0.100**, not 0.019–0.037. The published bracket is a
structural-model bracket presented as if the anchor were known.

### Defect 3 — the "rho ≈ 0.92 explains the noise" inference was never checked against data

The recon back-solved the model-model correlation from the observed std:
*"the OBSERVED 0.0677 is fully explainable as pure sampling noise at
rho~0.92-0.93."* I measured rho directly, refitting both models on the real
folds and correlating their predictions on the dedup test rows:

| fold | n_dedup | Pearson ρ(numeric, full) | Spearman ρ |
|---|---|---|---|
| 2025Q1 | 44 | 0.856 | 0.825 |
| 2025Q2 | 40 | 0.853 | 0.839 |
| 2025Q3 | 39 | 0.917 | 0.928 |
| 2025Q4 | 37 | 0.922 | 0.919 |
| 2026Q1 | 45 | 0.790 | 0.828 |
| 2026Q2 | 32 | 0.628 | 0.567 |
| **mean** | | **0.828** | **0.818** |

Under the recon's own simulated scaling (SE(δ) ∝ √(2(1−ρ))), ρ = 0.828 at
n ≈ 40 implies SE(δ) ≈ **0.106**, not 0.068. The observed 0.0677/0.0742 is
*below* what pure sampling noise produces at the measured correlation —
which is a 6-observation fluke, not evidence of a low-noise regime. The
recon's inference was directionally right (sampling noise dominates) but
the specific calibration is not supported by the data.

### Defect 4 (the good news) — the "floor may dominate" question IS identifiable, cheaply, and the answer favours E2

The recon's headline worry is caveat (1): if the 0.0677 is mostly a
market-regime **floor**, more companies buy nothing and only more folds
help. It concludes identification is "essentially nil" because the two
available points (full sample n≈39.5; form-controlled n≈24.33) are
confounded by feature regime, not just by n.

That is true of *that* estimator. It is not true of the problem. A
**within-fold bootstrap** identifies the 1/n component directly: hold each
fold's fitted predictions fixed, resample the dedup test rows with
replacement, recompute the delta. That isolates test-set sampling noise
with ~40 rows × 4,000 resamples per fold instead of 6 numbers. I ran it:

| fold | n_dedup | fold delta | bootstrap SD of delta |
|---|---|---|---|
| 2025Q1 | 44 | −0.1275 | 0.0930 |
| 2025Q2 | 40 | −0.0078 | 0.0962 |
| 2025Q3 | 39 | −0.0399 | 0.0574 |
| 2025Q4 | 37 | 0.0183 | 0.0707 |
| 2026Q1 | 45 | −0.0004 | 0.0986 |
| 2026Q2 | 32 | 0.0992 | 0.2090 |
| **mean** | 39.5 | | **0.1041** |

```
mean within-fold bootstrap SD of the delta   = 0.1041
observed cross-fold std of the 6 fold deltas = 0.0742
implied regime/training floor = sqrt(max(0, 0.0742^2 - 0.1041^2)) = 0.0000
```

**The floor is not detectable. Sampling noise fully accounts for the
observed spread, with nothing left over.** This resolves the recon's single
biggest stated worry **in E2's favour**: expanding to 100 companies does buy
power, and the pessimistic "100co × 6 folds buys nothing" scenario is not
the world we are in. Cost of this analysis: about two minutes of compute on
frozen artifacts. It should have been in the recon and it should be in the
G3 pre-registration.

### The honest E2 MDE, recomputed

The bootstrap is a far better anchor than a 6-number std (it uses ~40
observations × 4,000 resamples per fold rather than 5 degrees of freedom).
Anchoring on it:

```
per-fold SD of delta at n_dd = 39.5 (25 companies)   : 0.1041     [bootstrap]
E2 core stratum = 100 companies; E1 ratio 39.5/25 = 1.58 dedup rows/company/fold
=> E2 per-fold n_dd ≈ 158
scale 1/sqrt(n):  0.1041 * sqrt(39.5/158)             = 0.0521
SE of the 26-fold mean:      0.0521 / sqrt(26)        = 0.0102
MDE (2.8 x SE, two-sided 5%, 80% power)               = 0.0286
95% null bound (1.96 x SE)                            = +/- 0.0200
```

Now apply the two discounts the recon named but never quantified:

- **Effective fold count.** Expanding-window training sets are nested (fold
  26's model contains fold 25's training data), and 63-trading-day forward
  windows on filings near quarter boundaries straddle folds. If fold deltas
  carry lag-1 autocorrelation ρ_f ≈ 0.3 (my assumption — **unmeasured, and
  measurable at E2's 26 folds**), Var(mean) inflates ≈1.86×, SE ×1.36:
  **MDE ≈ 0.039, null bound ±0.027.**
- **Labeler attenuation.** See §(b): the E2 text block is produced by the
  Qwen student, not by Claude. Reliability of the aggregated red-flag rate
  features is ≈0.8–0.9, so the *measured* delta is an attenuated version of
  the delta a noise-free labeler would produce. In true-construct units the
  MDE is **≈0.036–0.049**.

| quantity | published (`EXPANSION_PLAN.md` §2a) | my recomputation |
|---|---|---|
| MDE, E2 (100co × 26 folds) | **0.019–0.037** | **≈0.029** (bootstrap anchor) → **≈0.039** (with ρ_f=0.3) |
| null bound on \|δ\| | ±0.013–0.027 | **±0.020 → ±0.027** |
| same, in true-construct (noise-free-label) units | not stated | **±0.025 → ±0.034** |

### Is the bounded-null framing statistically honest?

**Structurally, yes — and that is genuinely to the project's credit.** The
outcome is pre-committed *before* the data exists, the "what does a null
buy" logic is correct, and the recon explicitly says "the realistic outcome
of the bigger experiment is confirming ~zero." That is how equivalence
testing should be set up and it is rarer than it should be.

**Numerically and verbally, it overreaches in three specific ways:**

1. **The bracket is optimistic by ~1.5×** (defects 1–3). The pre-committed
   claim is that a null supports *"no text-vs-numeric IC improvement of
   economically relevant size (|δ| ≳ 0.03) exists in this universe."* At the
   honest MDE the 95% null bound is ±0.027 before fold-dependence and ±0.027
   after — i.e. the claim sits **exactly at** E2's detection limit, not
   comfortably inside it. One unlucky draw on effective fold count and the
   pre-committed sentence is not supportable by the data that produced it.
   This must be corrected *before* G3, because at G3 the owner is being
   asked to accept a bound whose width is currently misstated.

2. **The scope of the claim is wrong.** "No improvement of economically
   relevant size **exists in this universe**" is a statement about text.
   What E2 can support is a statement about *this pipeline*: "no
   improvement... **detectable through this labeling schema, these 22
   features, and this labeler**." Those are different claims and the
   difference is not pedantic — §(b) and §(d) show the schema is a ~20-bit
   bottleneck and the labeler is at its teacher's noise ceiling.

3. **Equivalence testing is not the same as failing to reject.** A bounded
   null needs a TOST-style procedure or an explicit CI, with the bound
   stated as an interval, not "we didn't find anything and our MDE was
   small." The plan's language is close to this but never names the test.
   Name it at G3.

**Two minor points, for completeness.** The 2.8 multiplier is the correct
normal approximation (1.96 + 0.84); at k = 26 a t-correction gives 2.92, a
+4% effect — negligible, unlike at k = 6 where the recon correctly notes it
should be ~3.4. And the fold budget: `data/filings_metadata_e2.db` shows
member-window filings spanning 2016Q3–2026Q3 = **41 quarters**, with 132–136
members filing in every single one, so 26 test folds is a conservative
budget, not a stretch. That is fine — just note that if the burn-in is set
short you get up to ~35 folds and the MDE improves by √(35/26) = 1.16×.

---

## (b) Label-noise propagation: what ~25–37% red-flag error does to feature SNR, and whether any red-flag result can be read

### The two-stage noise chain

**Stage 1 — teacher (Claude) vs adjudicated judgement.** From
`RED_FLAGS_LIMITATION.md` and `HANDOFF.md` §2a: set-level error 36.6%
sample-pooled; base-rate-representative **25.0%** (Tier C, n=36, 95% CI on
error [13.8, 41.1]); per-category **7.5%** (180 corrections / 2,394
chunk-category decisions), decomposing into 61 spurious / 76 missed / 43
wrong-modality. Also — and this matters more than the level — the errors are
**systematic**: `HANDOFF.md` §2 records that the disabled/4000 config
produced *more* flags in every single category versus the adaptive config
(LEGAL +211, MARGIN +203, DEMAND +138, IMPAIRMENT +51, SUPPLY +35, TRADE
+27).

**Stage 2 — student (Qwen 7B) vs teacher.**
`finetune/runs/2026-08-22-eval-epoch2/eval_report.md`: exact-set 64.87% vs
the teacher's own 63.4% reproducibility — the student is **at the ceiling**,
exactly as the report says. Per-category micro P = 0.848, R = 0.734
(TP = 843, FP = 151, FN = 305). The student's false-positive rate on true
negatives is 151/(6012 − 1148) = **3.1%**.

### What this does to an aggregated rate feature (worked)

Features like `redflag_MARGIN_COST_PRESSURE_rate_mda` are *rates over m
chunks*, so independent per-chunk error averages down. Let the true count be
T of m chunks, recall R = 0.734, per-negative false-positive rate f = 0.031:

```
E[p_student | p_teacher] = f + (R - f) * p_teacher        slope = 0.703
Var(p_s | T)   = [T*R(1-R) + (m-T)*f(1-f)] / m^2
reliability = corr(p_s, p_t)
```

At a corpus base rate p̄ ≈ 0.25 and cross-filing SD(p_t) ≈ 0.15:

| chunks per section, m | reliability corr(student rate, teacher rate) |
|---|---|
| 30 | **0.91** |
| 10 | **0.78** |
| 5 | ~0.68 |

Chaining stage 1 (teacher reliability ≈ 0.9 at m ≈ 30 on the same algebra)
with stage 2 gives a student-vs-truth reliability of roughly **0.82** where
sections are long, and **0.60–0.70** where they are short. Cross-sectional
rank IC attenuates by approximately that factor.

**Consequence for the estimand:** E2's measured MDE of ≈0.029–0.039
corresponds to a true-construct effect of **≈0.036–0.049**. E2 is
approximately as powerful, in true-text-signal units, as the plan claims it
is in measured units — the labeler downgrade eats most of the paper gain
from the pessimistic-to-optimistic bracket correction.

### The much bigger problem: the features are structurally missing, not just noisy

This is the finding I did not expect and it dwarfs the noise arithmetic. I
measured `data/features.parquet` directly (630 rows):

| feature family | rows where it is **NaN** |
|---|---|
| all six `redflag_*_rate_risk_factors` | **75.6%** (476 / 630) |
| all six `redflag_*_rate_mda` | **52.2%** (329 / 630) |
| `redflag_any_rate_press` | 40.2% |
| **`guidance_signed_mean`** | **90.2%** |
| `sentiment_mean_score` | 4.0% |

`guidance_any_present` is 0 on 90.2% of rows; `guidance_signed_mean` takes
**12 distinct values across 630 observations**. Median chunk counts are
`n_chunks_risk_factors = 0` and `n_chunks_mda = 0` — the 75th percentile of
risk-factor chunks is also 0.

And the missingness is **near-collinear with SEC form type**:

| form | mean text chunks | mean RF chunks | mean MDA chunks | n |
|---|---|---|---|---|
| 10-K | 65.2 | 27.5 | 37.4 | 75 |
| 10-Q | 36.1 | 4.6 | 30.6 | 224 |
| 8-K | 6.8 | **0.0** | **0.01** | 331 |

More than half the observations are 8-Ks, which structurally cannot carry a
risk-factor or MD&A chunk. So when XGBoost is handed a mostly-NaN column it
learns a default direction — which is *a form-type indicator*, not a text
signal.

**This dissolves the one apparently positive result in the whole E1
diagnosis.** `data/diagnosis_report.md` §1a reports
`numeric_plus_guidance` at **+0.0345 dedup, 5/6 positive folds** — the only
family positive on the full-sample grid. That family is built from a feature
that is present on **9.8% of rows**, whose presence is essentially "this
filing is an earnings press release." Under form control (10-Q/10-K only,
§1b) it flips to **−0.0125, 2/6 folds**. The diagnosis names the
form-confound in words; it never states that the guidance feature is 90%
missing, which is what makes the confound total rather than partial.

### Can any red-flag-family result be interpreted at all?

**In the null direction: yes, with a caveat.** Classical measurement error
attenuates toward zero; it does not manufacture cross-sectional rank
correlation with forward returns. So "red-flag features add nothing" is a
conclusion label noise **protects** rather than threatens. E2's bounded null
on the red-flag family is legitimate — provided the bound is inflated by
1/λ ≈ 1.2–1.4 before it is quoted.

**In the positive direction: no.** Two reasons, both structural rather than
statistical:

1. The errors are systematic and correlated with section type and form
   (stage-1 config sensitivity is category-wide and unidirectional; stage-2
   FN = 305 vs FP = 151 is a systematic under-emission). Systematic error
   that tracks document structure produces exactly the section-mix confound
   `data/diagnosis_report.md` already measures at **−0.0841** form-controlled
   — the strongest single number in the whole diagnosis, and it is a
   confound, not a signal.
2. The features are 52–76% structurally absent, so any positive coefficient
   is at least partly a form indicator.

**Guidance in E2 will be worse than guidance in E1.** `F2_PROGRESS.md` §6
records that under the proposed `missing → NONE` post-rule the student
reaches 98.4% — but *"the 98.4% is majority-class-carried (11/17 = 64.7% on
the 17 real-guidance rows); epoch-1 post-rule is ALSO 561/570, so epoch 2
bought zero guidance semantics."* A labeler that is 64.7% correct on the
rare non-NONE guidance calls, feeding a feature that is ~90% missing, cannot
support any guidance-family claim in either direction. That is worth saying
plainly at G1, because G1 is currently being decided on sentiment.

---

## (c) Censoring and look-ahead residuals: fatal vs must-caveat

My triage, as a hostile-but-fair referee would rank them.

### FATAL if unfixed (but all are fixable, and two are already queued)

**C1. Post-close acceptance dating — 45% of filings.**
`data/F2_INGESTION_REPORT.md` §3.3: *"20,715 of 45,545 filings (45%) are
accepted at 20:00–21:00 UTC — 16:00–17:00 ET, i.e. after the close — while
carrying that day's `filing_date`."* If F5 starts the 63-day forward window
on `filing_date`, that is a **one-trading-day look-ahead on nearly half the
observations**, and day-0-to-day-1 post-filing drift is precisely where
filing-text alpha is supposed to live. A referee stops reading at this. It
is the single highest-severity item in the corpus and also the cheapest to
fix: window start = next trading open after `max(filing_date,
acceptance_date)`. **F2 already found it and queued it for G3 —
excellent. The only failure mode left is forgetting.** Pin it with a test,
not a convention.

**C2. Naive restatement joins — 7.3% of period-cells.** §3.3: *"20,027 of
273,268 (cik, concept, unit, period) groups (7.3%) carry more than one
distinct value across filings."* The parquet is PIT-capable and `pit.py`
exists; the risk is entirely that some F5 join uses a latest-value
groupby. Fatal if it happens, zero-cost to prevent. Make it a leakage-suite
assertion over `data/fundamentals_e2.parquet`, not a sentence in a doc.

### MUST-CAVEAT, but a caveat alone is not enough

**C3. Membership-time censoring, 14–16% of early cohorts, outcome-correlated.**
§0c: 14.0% / 16.2% / 12.5% of member-date cells censored in 2016 / 2017 /
2018, decaying to 0.0% by 2026; energy 16.4%, core 7.7% vs extension 2.5%.
The report's own diagnosis is exactly right: *"time-decaying and
outcome-correlated, so it can make early folds differ from late folds for a
non-alpha reason."*

Where I go further: **the cross-fold mean weights biased and unbiased folds
equally.** Averaging 26 fold deltas where the first 6 are drawn from a
population that has had its acquisitions and take-privates deleted, and the
last 10 are clean, is not a caveat — it is a specification decision.
Minimum acceptable treatment, pre-registered at G3: (i) primary result on
the full window; (ii) mandatory sensitivity on the post-2019 sub-window
where censoring is <9%; (iii) report the two side by side always. A
referee will not call this fatal, but will call an unweighted 26-fold mean
over a censoring gradient *careless*.

**C4. Current-SIC assignment reaching into membership.** §9 item 12 is the
most intellectually honest paragraph in the repo: *"the bucket a company
competes in at 2016-07-01, and therefore whether it makes that date's top-K
at all, is decided by its 2026 SIC code... The magnitude is unmeasured — the
artifacts carry only the current SIC."*

Referee verdict: **must-caveat, not fatal** — it distorts *which* firms are
sampled, not *when* information becomes available, so it cannot manufacture
predictability. But "unmeasured" is the wrong resting place when it is
cheaply measurable: EDGAR filing-index headers carry the assigned SIC **as
of each filing**, and `data/raw/documents/` is already 42 GB of cached
filings at 0 GETs. Recovering historical SIC for the 244 member CIKs is a
parsing job on cached bytes, not a network job. Even a coarse "N of 244
members changed SIC division during the window" turns an unbounded
limitation into a bounded one. If the answer is "3 of 244," the caveat
shrinks to a footnote; if it is "40 of 244," the primary analysis needs a
robustness arm. Not knowing is the only unacceptable state.

**C5. Yahoo purged EA's delisted history.** §2: EA (CIK 712515), a core tech
member 2017–2021, returns 6 rows all dated 2026-07-17 → 2026-08-10 flatlined
at the take-private price, zero inside its coverage window. n = 1, next
smallest in-window row count is 539, and the tripwire is two-sided. Not
fatal. But it converts EXPANSION_PLAN §2c's *hypothetical* outcome-side
censoring into an **evidenced** one, which strengthens rather than weakens
the project's honesty — and it means the caveat must be written in the
indicative, not the conditional.

**C6. Split adjustment as of fetch date.** §9 item 4 correctly assesses this
as a level-side look-ahead that leaves returns unaffected. I agree; no action.

**C7. Salesforce filings whose `filing_date` precedes acceptance by 344 and
633 days.** n = 2, flagged, needs a general rule. Correctly triaged.

**C8. Self-inclusion in the E1 benchmark.** `data/features.parquet` shows
`target_n_universe_constituents = 25` for all 581 usable rows — the universe
average *includes the subject*, shrinking each excess return by (1 − 1/25)
and inducing a −1/24 cross-correlation among the 25 targets within a
quarter. Small, and `EXPANSION_PLAN.md` §3.3 already proposes
exclude-self for E2. Fixed by plan; the E1↔E2 incomparability statement
already required is the right consequence.

### Not on anyone's list, and it is the one I would lead a referee report with

**C9. Company identity is recoverable from the numeric features, and both
model arms exploit it.** Intraclass correlation (between-company variance ÷
total variance) on `data/features.parquet`:

| feature | ICC |
|---|---|
| `log_total_assets` | **0.987** |
| `leverage_liabilities_to_assets` | **0.986** |
| `equity_to_assets` | **0.984** |
| `cash_to_assets` | 0.838 |
| `operating_margin` | 0.819 |
| `net_margin` | 0.691 |
| `revenue_yoy_growth` | 0.652 |
| `net_income_yoy_growth` | 0.075 |
| `eps_diluted_yoy_growth` | 0.078 |

`log_total_assets` per-company means are separated by many within-company
standard deviations (KO: 25.348 ± 0.031; PG: 25.545 ± 0.025 — eight SDs
apart). A depth-3, 100-tree XGBoost can partition the 25 companies exactly
and then fit each company's in-sample mean excess return.

This is **not** look-ahead in the walk-forward sense — training dates
strictly precede test dates, and `test_phase_c_leakage.py` is correct to
pass. It is worse in a subtler way: it means the reported IC levels (~0.09
to 0.22) are **cross-sectional persistence, not predictive skill**, and the
sign flips fold to fold not because "the market regime changed" but because
mega-cap leadership rotated in 2025Q4. My two null-feature benchmarks above
(company training-mean IC 0.187; size-only IC 0.224, both beating the fitted
models) are the proof. A referee who spots this reads every IC in
`data/backtest_report.md` and `data/diagnosis_report.md` as uninterpretable.

E2 mitigates this only partially — 136 names weaken exact identification —
and does not remove it. `EXPANSION_PLAN.md` §5's F5 workplan changes the
benchmark, the fold structure, the alt-tag handling and the caveat
constants. **It does not change one thing about the feature specification.**

---

## (d) Is the stack outdated or sound for 2026?

### Sound and current — do not change these

- **LLM-bootstrap-then-distil-to-a-local-small-model** is standard 2023–2026
  practice, not a relic. The execution here is *better* than typical: parse-
  and schema-failure rates as first-class metrics, per-category P/R/F1 rather
  than a single accuracy, and — critically — every student number reported
  against the teacher's own reproducibility ceiling rather than against 100%.
  The eval report's opening line ("this measures AGREEMENT WITH THE TEACHER,
  not accuracy") is the correct epistemics and most teams get it wrong.
- **GBDT on small tabular data** is not outdated. In 2026, gradient-boosted
  trees remain competitive with or ahead of tabular deep learning at n in the
  hundreds-to-thousands. Keep XGBoost; the problem is the features, not the
  learner. (One tuning note: `max_depth=3`, 100 trees, 10–32 features on
  ~300–550 training rows is over-parameterised; a ranking-oriented linear or
  ridge model would have materially lower variance and is worth including as
  a second, pre-registered specification.)
- **Walk-forward with expanding windows, filing-date sorting, PIT
  fundamentals, near-duplicate dedup, form-controlled ablation.** Textbook
  correct and better executed than most published work.

### Outdated or missing versus 2026 practice

**D1 — The schema is a ~20-bit bottleneck.** Each ~350-word passage is
compressed to ≤6 binary flags × 2 modalities + one of 3 sentiments + one of
5 guidance values, then averaged to 22 filing-level numbers. Current practice
would put **passage/document embeddings** into the model — a local encoder
(300M–1B params, MLX or sentence-transformers) over ~100k chunks is hours on
the M5 at $0 — reduced by PCA to top-k components, or fed to a linear probe.
This preserves orders of magnitude more of the text than the schema does, and
it costs **less machine time than the labeling campaign already budgeted**
(57.4–78.3 hours per the epoch-2 throughput probe).

**D2 — No textual-change / novelty features. This is the biggest content
gap.** The most robustly replicated filing-text return predictor in the
literature is *year-over-year change in filing language* (the "Lazy Prices"
family: cosine/Jaccard similarity between consecutive 10-K/10-Q Item 1A and
Item 7). FinScreen has **zero** change features — every text feature is a
level (a rate, a mean, a share). E2 gives each company ~10 years of
consecutive filings, which is precisely the panel this signal needs, and it
requires **no labeling at all**. A design that spends 60–80 machine-hours
labeling levels while ignoring changes has its effort allocated backwards.

**D3 — No direct-LLM-scoring arm.** The obvious 2026 control: ask the local
fine-tuned model (which will already have read all ~100k chunks) for a
continuous forward-looking score per filing, and evaluate it as a feature
alongside the schema labels. Zero incremental data, near-zero incremental
compute, and it is the direct head-to-head test of "did the schema throw the
signal away?" Without it, a null on the schema features cannot distinguish
"text has no signal" from "our 22 numbers lost it."

**D4 — The numeric baseline is not a quant baseline.** The 10 numeric
features are `log_total_assets`, leverage, equity/assets, cash/assets, net
margin, operating margin, OCF/revenue, and three YoY growth rates. There is
**no valuation ratio** (no E/P, B/P, EV/EBITDA), **no momentum**, **no
volatility**, **no market cap** — no price information on the right-hand side
at all. Two consequences: (i) as a *research* claim, "text adds nothing over
numerics" is weak because the numeric arm is weak (though this also makes the
null *conservative*, which is in the project's favour); (ii) as a *screening
tool*, the pipeline is missing exactly the factors that are known to work.
Momentum and realised volatility are free from `data/prices_e2.parquet`
(already ingested, 41 MB); B/P and E/P are free from
`data/fundamentals_e2.parquet` × price, subject to the 16 members with
unresolved multi-class `shares_outstanding` (§9 item 8).

**D5 — Evaluation reports IC only, with a √k standard error.** No portfolio
sort as the headline (`quintile_spread` is computed but not primary), no
HAC/Newey-West or block-bootstrap SE over folds, no multiple-testing control
across the 6 families × 2 dedup bases × 2 form subsets grid — 24 numbers, of
which ~1 crosses p<0.05 by chance. The G3 pre-registration of a single
primary metric is the right fix for multiplicity and is already planned; it
should also name the **SE estimator**, not just the metric.

**D6 — No panel / fixed-effect specification.** Given C9, a 2026 referee
would demand the delta re-estimated with company and quarter fixed effects
(or, equivalently in a ranking framework, cross-sectionally demeaned or
rank-normalised features). That is recommendation E1 below.

### What a stronger 2026 design at comparable cost looks like

Keep the expensive part — the PIT ingestion, membership panel, censoring
census, dedup and walk-forward machinery are the hard-won assets and they
are good. Change the cheap part:

- **Text arm:** filing-change/novelty cosine features + pooled embeddings
  (top-k PCs) + one direct-LLM continuous score, **alongside** (not instead
  of) the schema labels, all cross-sectionally rank-normalised PIT.
- **Numeric arm:** add momentum (1m, 12m−1m), realised volatility, and E/P
  or B/P from data already on disk.
- **Evaluation:** one pre-registered primary (dedup IC delta), block-bootstrap
  SE, TOST-style equivalence bound, quintile spread reported beside it,
  everything else explicitly labelled exploratory.
- **Specification:** primary = PIT cross-sectional ranks; secondary = raw
  levels; both reported, always, as a mandatory pair.

---

## (e) The three highest-leverage changes

Ranked by (credibility gained) ÷ (cost). All three land **before F3**, which
is the current decision point — none requires re-running F1 or F2.

### E1. Pre-register the feature transformation; make PIT cross-sectional ranks the primary specification. (~1 day)

**Why it is first.** I re-ran the full walk-forward with a strictly
look-ahead-free transformation: for each row at date *t*, rank each feature
against every ticker's most recent observation with `filing_date ≤ t`
(180-day window, no future rows). Nothing else changed — same folds, same
dedup, same XGB params, same targets.

| specification | mean IC numeric | mean IC full | **mean delta** | std(delta) | positive folds |
|---|---|---|---|---|---|
| raw levels (as shipped) | 0.0972 | 0.0875 | **−0.0097** | 0.0742 | 2 / 6 |
| PIT trailing cross-sectional percentile ranks | 0.0783 | 0.1250 | **+0.0467** | 0.1668 | 4 / 6 |

**A 0.056 swing in the headline estimand from one defensible, unpre-registered
preprocessing choice — roughly 3× E2's entire optimistic MDE of 0.019.**

To be explicit about what this is *not*: +0.0467 with SE ≈ 0.068 is t ≈ 0.69.
**This is not evidence of signal.** It is evidence that E2's designed
precision is smaller than its own specification sensitivity, which means the
pre-committed bounded null is not defensible until the specification is
frozen and the specification-uncertainty is reported.

**Mechanism** (C9): raw levels carry company identity — `log_total_assets`
ICC 0.987 — and both arms exploit it, so the delta is a residual on a large
shared term. Rank-normalisation strips the level and forces the model onto
relative variation.

**Do:** at G3, pre-register the transformation alongside the benchmark, the
fold structure and the primary metric. Make the PIT cross-sectional rank the
primary and raw levels the mandatory reported secondary. Add the two null-
feature benchmarks (size-only rank; company training-mean rank) as permanent
report rows, so every future IC is read against what a zero-information
predictor achieves on the same folds.

### E2. Replace the 6-number noise anchor with a within-fold bootstrap; use block/HAC standard errors over folds. (~half a day, on frozen artifacts)

**Why.** Everything the owner will be asked to accept at G3 — "a null bounds
|δ| within ±0.013–0.027" — rests on `diagnose.py:222`'s `std(ddof=0)` over
six numbers, whose own 95% CI is [0.046, 0.182]. The within-fold bootstrap I
ran (§a, defect 4) is a strictly better estimator, and it delivers two things
at once: it **resolves the recon's biggest caveat in E2's favour** (implied
regime floor = 0, so 100 companies genuinely buy power), and it shows the
anchor is ~1.5× too small (per-fold SD 0.104, not 0.068).

**Do:** (i) change `ddof=0` → `ddof=1` in `diagnose.py:222` and
`backtest.py:513, 689, 693, 781`; (ii) add the within-fold bootstrap of the
delta as a standing report section; (iii) at 26 folds, **measure** the lag-1
autocorrelation of fold deltas (E1 could not — 6 points; E2 can) and report a
block-bootstrap or Newey–West SE of the cross-fold mean instead of
std/√k; (iv) restate the E2 MDE and the null bound honestly in
`EXPANSION_PLAN.md` §2a **before** the owner rules at G3. Expected honest
figures: MDE ≈ 0.029 (bootstrap anchor, ρ_f = 0), ≈ 0.039 at ρ_f = 0.3,
≈ 0.036–0.049 in true-construct units after labeler attenuation.

### E3. Add the two zero-labeling feature families — and the missing numeric factors — before F4 commits 60–80 machine-hours to labeling. (~2–3 days)

**Why.** F4's labeling campaign is 57.4–78.3 hours of the owner's machine at
the measured 1,337 chunks/h, producing 22 numbers per filing whose red-flag
component sits at its teacher's reproducibility ceiling and whose guidance
component is ~90% structurally missing. Two families that cost **zero
labeling** are currently absent and are, on the published evidence, more
likely to carry signal:

- **Filing-change / novelty** (D2): cosine or Jaccard between a company's
  consecutive Item 1A / Item 7 texts. Computable from `data/raw/documents/`
  (42 GB, already cached, 0 GETs) plus F3's extraction output. This is the
  most replicated filing-text predictor in the literature and the pipeline
  has none of it.
- **Pooled passage embeddings** (D1): local encoder → mean-pool per section →
  top-k PCs. Hours on the M5, $0, and it tests directly whether the
  hand-designed schema is the bottleneck.

And from data already on disk, at essentially no cost: **momentum, realised
volatility, and E/P or B/P** into the numeric arm (D4), so that the
comparison is against a real baseline and — separately — so that the
*screening tool* the owner actually wants contains the features that are
known to work.

**Sequencing note:** doing this before F4 rather than after F5 means the
labeling campaign runs once against a final feature design, instead of
running now and being re-run later when the text arm is revised.

---

## Appendix A — charter vs "product": what the methodology can and cannot deliver

The brief flags a tension between `HANDOFF.md` §1 ("a solo-owner research and
screening tool, not a product with users") and the owner's recent "product"
language. From the methodology lens the tension is real and resolvable:

**E2 is correctly designed to answer a research question and will answer it.**
Every artifact — the pre-committed null, the bracket-not-point MDE, the
"never conflate the two censoring numbers" discipline, the refusal to quote
teacher error constants onto student labels — is the discipline of a study,
and it is good discipline.

**None of E2's planned outputs is a usable screen, and no amount of extra
folds makes it one.** Concretely, a product would additionally need: a price
source whose terms permit the use (`data/PRICES_NOTES.md` §1 — Yahoo's
robots.txt disallows automated access, and F2 grows that exposure ~4–5×);
dividend-adjusted returns (currently split-adjusted only); a reproducible
incremental data path (`data/F2_INGESTION_REPORT.md` §10: *"the corpus is not
yet reproducible across days"*); a deployable feature transform (E1 above);
and a feature set containing value/momentum/quality (D4). The first two are
blockers of a kind that no methodology fix addresses.

The honest framing for the owner: **if the goal is the research answer,
finish E2 with E1–E3 applied and the null will be worth having. If the goal
is a screen you would actually use, the highest-value pivot is not more folds
— it is the numeric/price feature set plus a licensed data source, and that
is a different project that reuses about 70% of what is already built.**

## Appendix B — how the numbers in this report were produced

- Replication of `data/backtest_report.md` / `data/diagnosis_report.md`:
  `data/features.parquet` → 581 rows with non-null `target_excess_return`,
  quarterly expanding folds from `BURN_IN_END = 2025-01-01`, 5-day same-ticker
  dedup clusters with a 10-Q/10-K-first same-day tie-break, `XGB_PARAMS` from
  `backtest.py:159`, feature lists from `features.NUMERIC_FEATURE_NAMES` /
  `TEXT_FEATURE_NAMES_NON_REDFLAG` / `RED_FLAG_FEATURE_NAMES`. Reproduces the
  published dedup fold sizes (44/40/39/37/45/32) and per-fold deltas exactly.
- Bootstrap: 4,000 resamples per fold, `numpy` default_rng(0), fitted
  predictions held fixed, resampling only the dedup test rows.
- ICC: between-company sum of squares ÷ total variance, per feature, over
  non-null rows.
- PIT rank transform: for row *i* at date *t*, the comparison set is the last
  observation of each ticker with `filing_date ∈ [t − 180d, t]`; percentile =
  fraction strictly below + half the ties. No row with `filing_date > t`
  enters any comparison set.
- E2 scale figures: `data/filings_metadata_e2.db`, `universe_membership`
  (299 spell rows → 136 members at each of 11 reconstitution dates, core =
  100) joined to `filings` clipped to membership spells.
- Nothing in this report was written to disk except this file. No pipeline
  file, artifact, or test was modified.
