# LENS 1 — THE KILL CASE

**Brief:** build the strongest honest case that continuing FinScreen is a
mistake, then judge whether it survives.
**Written:** 2026-08-25. Read-only pass; no pipeline file was edited, no
network call made. Every number below is either quoted from a repo document
with its source named, or re-derived here from repo artifacts with the
computation shown.

**Verdict up front: the kill case does NOT win as "stop the project."
It DOES win as "the current trajectory is aimed at the wrong deliverable."**
Full reasoning in §7. Read §1 and §5 first if you read nothing else.

---

## 0. What I checked, so you can discount me correctly

Documents read in full or in the sections named by the brief: `HANDOFF.md`
§§1, 2a, 3, 5, 6, 7; `EXPANSION_PLAN.md` (all); `data/diagnosis_report.md`
(all); `data/F2_INGESTION_REPORT.md` §§0–4; `F2_PROGRESS.md` §§5–7;
`RED_FLAGS_LIMITATION.md`; `LIMITATIONS.md` (structure + §2);
`finetune/runs/2026-08-22-eval-epoch2/eval_report.md` (all); `ROADMAP.md`
Phase F + Money; `data/expansion_recon_2026-08-20.json` `power` block (all);
`TEAM.md`.

Computations I ran myself against artifacts (read-only pandas/sqlite):

| # | Check | Result |
|---|---|---|
| C1 | E1 feature-table shape and text-feature sparsity (`data/features.parquet`) | 630 rows × 48 cols; 22 text features, 10 numeric fundamentals; **52.2% of observations have neither Risk-Factors nor MDA text**; `guidance_signed_mean` is NaN on 90.2% of rows |
| C2 | Simulated the fine-tuned student's measured confusion matrix onto E1's own filing-level sentiment composition | `sentiment_negative_share` retains only **ρ=0.57 Pearson / 0.64 Spearman**; `sentiment_mean_score` retains ρ=0.87 |
| C3 | Same, for the 12 red-flag rate features using per-category P/R from the epoch-2 eval | mean retention **ρ=0.81 Pearson / 0.86 Spearman** |
| C4 | E2's actual achievable per-fold panel (`filings_metadata_e2.db` × `price_ticker_map.csv`) | **mean 96.1 usable core companies/quarter (min 84) across 30 quarters 2019Q1–2026Q2** — the power design's "100co × 26 folds" is real, not aspirational |
| C5 | Extension stratum's share of the labeling burden | **5,741 of 20,521 text-bearing filings = 28.0%** |
| C6 | Corpus scale factor E1→E2 | 20,521 text-bearing filings vs E1's 884 sections = **23.2×** |
| C7 | Repo volume | 18,769 lines first-party Python, 10,536 lines first-party tests, **20,396 lines of Markdown**, 13 agent definitions, 43 GB of cached documents — in 15 elapsed days |

Where I am extrapolating rather than measuring, I say so inline.

---

## 1. (a) The realistic outcome distribution for E2

### 1.1 The power design is sound and I verified it

This is the part of the kill case that fails, and it should be said first
so the rest is read fairly.

E1's design could not have detected anything. `expansion_recon`'s power
block anchors on the observed per-fold delta std of 0.0677 at dedup n≈39.5,
giving MDE(5%, 80%) = 2.8 × 0.0677/√6 = **0.077** — larger than every family
mean delta ever observed in the data. That is not a rationalization written
after a null; it is arithmetic, and it is correct. E1's null was structurally
near-inevitable.

E2's fix is the right fix. And **C4 confirms E2 can actually deliver it**:
joining `universe_membership` against `price_ticker_map.has_usable_prices`
and 10-Q/10-K filing activity, the core stratum yields a mean of **96.1
price-usable companies per quarter, minimum 84**, over the 30 quarters
2019Q1–2026Q2. The recon assumed 100 companies × 26 folds. The panel is
there. At k=30 the bracket recomputes to MDE ≈ **0.018 (no regime floor) to
0.035 (all floor)** — essentially the ratified 0.019–0.037.

So: the experiment is not vapor. If the question is worth answering, E2 is a
competently designed way to answer it.

### 1.2 Three things the power calculation does not include

**(i) Labeler attenuation — measured here, and it was explicitly assumed
away.** The recon's own honest-caveat (5) reads: *"new Qwen-labeled features
have no measured delta std yet — these projections assume the new labeler's
noise profile resembles the bootstrap LLM's."* That assumption is now
testable, and it is false in the wrong direction. The recon is dated
2026-08-20; the epoch-1 eval landed 2026-08-21 and epoch-2 on 2026-08-22.
**The entire MDE bracket predates the only evidence about the labeler that
will actually build E2's features.**

I measured the size of the gap (C2/C3). Taking the student's own confusion
matrix from `eval_report.md` §2 and §5 and applying it stochastically to
E1's reconstructed per-filing chunk composition:

| feature | retention vs Claude-labeled version (Pearson) |
|---|---|
| `sentiment_negative_share` | **0.566** |
| `sentiment_mean_score` | 0.874 |
| 12 × `redflag_*_rate_*` (mean) | 0.808 |

The red-flag block survives aggregation reasonably well — flags are counted
over many chunks and errors partly average out. The **negative-sentiment
share does not**: the student's NEGATIVE recall is 0.487, i.e. it misses
half of all negative-sentiment chunks, and that feature retains barely more
than half its identity.

Honest bounding of this finding in both directions:
- It is **optimistic** for E2, twice over. The eval split is E1-distribution
  text (2023–2026 mega-caps); E2 labels 2016-era text and three sectors
  (industrials, utilities, materials/real-estate) the student never saw.
  And the simulation treats student errors as independent across chunks,
  whereas real model errors are systematically correlated (same phrasing →
  same mistake), which does not average out and would attenuate further.
- It is **pessimistic** in one way: a noisier text block makes the full model
  more similar to the numeric-only model, which raises model-model
  correlation and *shrinks* the delta's sampling noise. So the naive
  "divide the MDE by 0.8" overstates the harm. The net effect is a real but
  modest power haircut, not a project-killer on its own.

Net honest read: **~15–25% effective power loss, unmodelled, on top of a
bracket whose pessimistic end already exceeds every effect ever observed in
this data.**

**(ii) The window extension buys folds and regime heterogeneity together.**
The pessimistic endpoint of the bracket exists because a market-regime
variance floor in the delta cannot be ruled out. E2 buys its extra folds by
reaching back to 2019/2016 — which means COVID, the 2022 rate shock, and
pre-iXBRL disclosure regimes enter the sample. If a regime component in the
delta is real, extending backward adds exactly the variance the pessimistic
endpoint is worried about. The recon flags this as caveat (4) "estimand
shift" but does not propagate it into the bracket.

**(iii) Fold non-independence makes every MDE a floor.** The recon says this
plainly (caveat 2) and it is right: the same ~96 companies recur in all 30
folds, so SE_mean = std/√k overstates the effective k.

### 1.3 The three noise layers E2 does not touch

E1's null has at least four candidate causes. E2 addresses **one**.

| Cause | E2's effect |
|---|---|
| Insufficient power | **Fixed** — 0.077 → ~0.018–0.035 |
| Teacher label error: `red_flags` fails the project's own 0.70 bar (63.4% exact-set pooled; ~25% error on the base-rate-representative Tier C) | **Unchanged.** Rubric v1.2 is explicitly out of scope (`EXPANSION_PLAN` §7); the student was trained on the flawed labels and will reproduce them |
| Student labeler degradation | **Made worse** (C2/C3) |
| Feature representation: 22 hand-designed rate features, 52.2% of observations carrying no MDA/RF text at all, guidance NaN on 90.2% of rows (C1) | **Unchanged.** E2 scales the sample, not the representation |

That last row is the one I want to press hardest, because it is the most
direct answer to your word *"outdated."* The entire text signal in this
project is: three section-mix shares, two sentiment aggregates, two guidance
aggregates, twelve red-flag rates, one press-release flag rate. That is a
2018-vintage NLP feature design executed with 2026 tooling. There is no
document embedding, no learned text representation, no similarity-to-prior-
filing measure (the single best-documented effect in this literature is
year-over-year *change* in 10-K language, and this pipeline does not compute
it). `diagnosis_report.md` §5 is scrupulously clear that it cannot
distinguish "no signal in filing text" from "no signal in these features" —
and E2 will not distinguish them either. It will answer the same narrow
question with a tighter confidence interval.

### 1.4 Calibrated outcome distribution

For E2's primary confirmatory result (core stratum, dedup IC delta,
~30 folds), what a calibrated observer should expect:

| Outcome | P | What it yields the owner |
|---|---|---|
| **Bounded null** — CI contains 0, \|point\| below MDE | **60%** | The pre-committed acceptable result. A genuine, defensible statement: "no text-vs-numeric IC improvement of economically relevant size exists in this universe, for these features, with this labeler." Real closure — *if* a stopping rule was written down first. |
| **Small / ambiguous** — point 0.02–0.04, marginal, not fold-robust (sign flips on drop-one-fold, or full-sample and form-controlled disagree) | **22%** | **The worst outcome.** No closure, no usable tool, and maximum temptation to run E3. Note E1 already produced exactly this shape at lower power: guidance +0.0345 / 5-of-6 folds full-sample, flipping to −0.0125 / 2-of-6 under form control. |
| **Meaningful + robust** — \|point\| ≥ 0.04, survives drop-one-fold and form control | **6%** | A genuinely interesting finding — that collides immediately with the charter, which forbids acting on it. See §2. |
| **Invalidated / materially revised by red-team or leak discovery before the owner reads it** | **12%** | Weeks lost, methodology vindicated. Grounded, not hypothetical: F2's own red-team found three corpus-invalidating defects *after* the report was drafted (B1, Pioneer, PSEG's 45-of-45 slide decks), forcing a full corpus regeneration. `F2_INGESTION_REPORT` §3.3 names three *still-unresolved* point-in-time conventions, including that **20,715 of 45,545 filings (45%) are accepted after the 16:00 ET close while carrying that day's `filing_date`** — a live one-day look-ahead on nearly half the corpus if F5 dates features to `filing_date`. |

The modal outcome, at 60%, is a null. That is not a criticism — a null at
this power is the pre-committed acceptable result and it is worth something.
It is a criticism only if no decision rule exists for it, which brings us to
§3 and §6.

---

## 2. (b) What "useful" can mean under a charter that forbids trading and advice

`HANDOFF.md` §1 is unambiguous and contractual: not a trading bot, not
investment advice, no live capital in any phase, no performance claims. §5
adds hard $0 API spend. So take each E2 outcome and ask who is served.

**Bounded null.** Served: the owner, with closure and a demonstrated
capacity to run and accept a negative result. Served: nobody else, unless
written up — and there is no publication plan in any repo document. This is
real value but it is *self-directed* value, and most of it (the skill, the
method, the discipline) is already banked regardless of E2's outcome. See
§4.2.

**Small/ambiguous.** Served: nobody. It is precisely the outcome that
generates another experiment rather than a decision.

**Meaningful + robust.** Served: intellectually, the owner. Practically,
nobody — because the charter forbids the only action the finding implies.
Worth being blunt: **a positive result is the outcome the charter is least
equipped to absorb.** The honest position under the charter is "I found a
statistical association and I will not act on it," which is a coherent
research stance but is not what most people mean when they say "useful."
There is no document in this repo that says what happens if E2 succeeds.
G4 is described as "final read" — not a decision rule.

**The thing the charter *does* permit, and which nothing in the plan builds.**
Under "research and screening tool," a screening tool is explicitly in
scope. A screening tool that helps its owner read filings faster — what
changed in this quarter's Risk Factors, which companies newly flagged margin
pressure, which MDA turned negative — is fully charter-compliant, needs no
return prediction, no benchmark ratification, no fold structure, no price
data, and no statistical power at all. It needs the corpus (built), the
extraction (F3, needed anyway), and the local labeler (built, and by its own
eval numbers *good enough*: 0.00% parse failure, 0.00% schema violation,
92.42% per-category red-flag agreement, 1,337 chunks/hour, $0).

That is the sharpest single sentence in this report:

> **The most valuable asset this project has built — a $0, 1,337
> chunks/hour, zero-parse-failure local financial-text labeler running over
> a 20,521-document point-in-time corpus — is currently being spent, in its
> entirety, on producing one number (an IC delta) that the charter forbids
> acting on.**

---

## 3. (c) Product vs research: what each framing demands, and where the work serves neither

**The tension is real and it is dated.** The charter (2026-08-10 era, restated
in `HANDOFF` §1) says *research and screening tool, not a product with
users*. The commissioning message for this review says *"making a product
that is not really useful."* Those are different projects with different
success criteria, and no document in the repo reconciles them.

**A research framing demands:** a pre-registered question; adequate power
(E2 has it); honest reporting (this project is genuinely excellent at it);
and — critically — **a stop when the answer arrives**. It does not demand
43 GB of cached documents, a 3,675-line metadata ingester, a 13-agent org
chart, or a model card for a model nobody will deploy.

**A product framing demands:** a user (the owner), a repeated use, an
interface, and a value proposition that survives a null result. It does not
need the excess-return target, the price ingestion, the benchmark
re-ratification at G3, the fold pre-registration, the LOCO analysis, or E2's
statistical power.

**Where the current work serves neither:**

| Artifact / activity | Research value | Product value |
|---|---|---|
| Extension stratum (industrials, utilities, materials/RE) — 68 CIKs, **28.0% of the labeling corpus** (C5) | **Zero to the primary analysis** by the owner's own binding rule: primary confirmatory analysis is core-only; extension is a secondary arm promoted only if G2 clears | Real — broader coverage is exactly what a screening tool wants |
| 43 GB document cache, `ingest_metadata.py` at 3,675 lines | Only the core stratum's 14,780 filings are needed | Real, reusable |
| Price ingestion (1.96M rows, 213 CIKs, Yahoo ToS exposure) | Required | **Zero** |
| Benchmark ratification, fold pre-registration, LOCO, form-controlled ablations | Required | **Zero** |
| 20,396 lines of Markdown | Partly required (methods record) | Low |
| 13 agent definitions + TEAM.md org chart | Zero | Zero |

The extension stratum is the cleanest instance. It was ratified 2026-08-21
with the owner's verbatim reason: *"i do not want to exclude a third of US
economy."* That is a **coverage** reason — a product reason — attached to a
**power** experiment, and the same ratification simultaneously bound it out
of the primary analysis. It is 28.0% of the labeling burden buying 0% of the
primary MDE. It is a good decision under a product framing and a poor one
under a research framing, and it was made without the framing being decided.

---

## 4. (d) The cost side, and what has already been irreversibly gained

### 4.1 Costs remaining

Cash: **$0**, genuinely. The spend freeze at $33.51 is real and enforced;
agent work is subscription-covered; the fine-tune and labeling are local.
This is the strongest single fact against the kill case and it should not be
minimised.

Machine: F4 labeling. The eval report's own throughput table says 57–78
hours (5.7–7.8 overnights) for 76,746–104,746 chunks. Extrapolating E1's
chunking yield (6,747 chunks over 884 sections = 7.6 chunks/section) onto
E2's ~23,000 expected sections suggests **~150k–175k chunks, i.e. ~10–14
overnights**, not 6–8. The plan's own §2b band ("11–16 overnights worst
case" for the hybrid) is consistent with my higher number; the eval report's
table is the optimistic one. Two unused free levers (prefix cache, batching)
could claw back 2–4×. Call it **6–14 resumable overnights**, uncertain.

Owner attention — **this is the binding constraint, not compute:**
- **G2 requires a second full spot-check**, from scratch, over Qwen labels
  (`EXPANSION_PLAN` §3.7 — the E1 error constants "would be silent
  misinformation" if carried over). E1's spot-check cost 400 sampled chunks,
  400 auditor verdicts, 174 adjudications, and **104 personal owner
  rulings**, and the owner's own words at the time were *"0 idea where to
  start"*. That cost is being paid again, and only the owner can pay it.
- **G3 requires ratifying** the benchmark, the fold structure, the primary
  metric, the FX conversion semantics, and now three unresolved PIT
  conventions (after-close acceptance, the two Salesforce acceptance
  anomalies, restatement as-of rules on 7.3% of period-cells).
- **F3 is the phase the plan itself calls the "wall-clock elephant"** —
  extraction QA over 11× the text, new filer HTML dialects, pre-2019
  filings, manual spot-reads. `extract.py`'s calibrations are all fit on 25
  mega-caps' 2023–2026 filings.
- Then F5, F6, G4.

Calendar, extrapolating from observed cadence (F0→F2 consumed 2026-08-20 to
2026-08-24 with a full corpus regeneration mid-flight): **F3–F6 realistically
3–6 weeks**, with G2's adjudication the irreducible human cost.

### 4.2 What is already irreversibly gained — and it is a lot

This matters more than anything else in answering *"have I wasted this."*
The answer is emphatically **no**, and the reason is that the durable gains
do not depend on E2's outcome:

1. **The owner personally ran a research program end to end** — pre-registration, power analysis, blind second-rating, third-rater adjudication, red-teaming, and then *accepted a null instead of massaging it*. That is rarer than it sounds and it does not decay.
2. **A working local fine-tune pipeline**: MLX QLoRA, checkpointed, resumable, hash-verified provenance, an eval harness that refuses to report non-evaluable classes and separates exact-set from per-category bases.
3. **A point-in-time-correct EDGAR stack**: dated membership reconstitution, a five-state fundamentals alias/migration classifier that fails loudly, distress-event ingestion, co-registrant handling.
4. **A demonstrated capacity to find own errors**: the `run_full()` incident, form-aware dedup, the PSEG 45-of-45 defect, the B-series red-team findings — all of which made results *worse*, and were shipped anyway.
5. **Honest-methods documentation practice** at a level most working professionals never reach. `diagnosis_report.md` §5 ("what this cannot conclude") and `eval_report.md`'s "read this before quoting any number" are, unironically, better epistemic hygiene than most published financial ML.

**These are already banked. That is exactly why continuing is a question
rather than an obligation** — the argument "we've come too far to stop" has
no force here, because the thing most worth having has already arrived.

---

## 5. (e) Sunk-cost and momentum: the specific signs in this repo

I looked for momentum substituting for direction. I found it. I also found
strong counter-evidence, which is in §5.2 and is not decorative.

### 5.1 The signs

**S1 — The gate inversion. This is the most important one.**
The 2026-08-11 ratification reads: *"Fine-tuning happens **only if** the
Week 5 go/no-go shows real text signal over the numeric-only baseline."*
Week 5 showed no signal (2026-08-18 diagnosis: no fold-robust contribution
from any family, category, or company). The fine-tune launched **2026-08-20
anyway**, re-justified as E2's labeling enabler. And `HANDOFF` §3 records
that the same 2026-08-20 walkthrough included *"an explicit recommendation
AGAINST fine-tuning absent a bigger experiment"* — to which the response was
to authorize the bigger experiment.

The new justification is legitimate on its own merits (a $0 local labeler is
genuinely the only way to label 150k chunks under the spend freeze). But the
*shape* of the move — **a gate designed to stop an activity became the
reason to expand it** — is the canonical sunk-cost signature, and it is the
single thing in this repo most worth the owner re-examining personally.

**S2 — Scope grew twice in 24 hours, once for a non-power reason.**
25 companies → 100 (2026-08-20, power-justified, correctly) → hybrid136 /
244 CIKs (2026-08-21, justified verbatim as *"i do not want to exclude a
third of US economy"*). Measured cost of the second expansion: **5,741 of
20,521 text-bearing filings = 28.0%** of the labeling corpus (C5), for zero
contribution to the primary confirmatory analysis by the same ratification's
own binding rule.

**S3 — Prose has outpaced results.** 20,396 lines of Markdown against 18,769
lines of first-party Python (C7), in 15 elapsed days, supporting exactly
**one** modeling result (630 rows × 48 columns × 6 folds). Six documents
exceed 25 KB; `HANDOFF.md` is 80 KB. The documentation is a genuine strength
— but the ratio is a signal that the artifact being produced is increasingly
*the record of the work* rather than the work.

**S4 — Institutional scaffolding ahead of the institution.** 13 agent
definitions, a TEAM.md "TIGER team" org chart, and a model-tiering policy —
created **2026-08-24, mid-F2**, for a solo project with one experiment
behind it. Org design is a comfortable, legible substitute for the
uncomfortable question of whether the experiment is worth finishing.

**S5 — Complexity contradicts the owner's own philosophy, ratified the same
day.** "Lazy-elite engineering — no over-engineering, minimal correct work"
was ratified 2026-08-24. `ingest_metadata.py` is **3,675 lines** with a
2,984-line scale-test beside it, for fetching EDGAR metadata for 244
companies. Segment 1 of F2 required **eleven attempts** and a full corpus
regeneration after the red-team pass. Whatever else is true, that is not
minimal correct work.

**S6 — G1 has been open since 2026-08-21** — the gate that decides whether
the student is good enough to be E2's labeler, i.e. whether E2's text
features are worth building at all. The re-eval completed 2026-08-22 and is
still unread on 2026-08-25, while all of F2 proceeded. Formally correct
sequencing (F2 doesn't depend on G1). Practically, the decision that most
determines E2's value has been deferred behind four days of ingestion.

**S7 — 43 GB fetched before extraction was validated at scale.** F3
(extract at scale + QA) comes *after* F2's fetch. Mitigated — the cache is
reusable and re-extraction is free — but it is fetch-first, validate-later.

### 5.2 The counter-evidence, which is strong

I would be misleading you if I stopped at §5.1.

- The project **pre-committed that a null was acceptable, then produced one and published it in its own documents without spin.** It did not p-hack E1 into a positive. That is the single best predictor of a healthy research process and this project has it.
- It ran a **real power analysis before expanding**, and that analysis told the owner plainly that E1 could not have detected anything at its design. The expansion is a response to a diagnosed cause, not to disappointment.
- The red-team pass found defects that made results **worse** (PSEG, form-aware dedup, B1/B4/B8/B10/B16/B20) and they were fixed and reported anyway.
- The documents state limits **harder than an advocate would** — including several (§0c's membership-time censoring profile, §3.3's unresolved PIT conventions) that actively undermine the project's own forthcoming results.
- Forward cash is genuinely $0.

**Conclusion for §5:** this is not a project drifting on sentiment. It is a
methodologically serious project that has developed a **scope-growth habit**
and has never been forced to write down what it would do with an answer.

---

## 6. (f) The conditions under which stopping or pivoting NOW is rational

Stated as criteria the owner can check in ten minutes, not as opinions.

**STOP (or hard-pivot) if ANY of these is true:**

**K1 — The decision-value test.** The owner cannot state, in one sentence
each and *without consulting the plan*, what they would do differently under
(a) a bounded null, (b) a small ambiguous effect, (c) a meaningful robust
effect. If all three answers are "keep going," the experiment has no
decision value and the 3–6 weeks buy nothing.

**K2 — The stopping-rule test.** The owner is unwilling to pre-commit, in
writing at G3 and in `HANDOFF` §3, that a bounded null **ends the alpha line
of work** — no E3, no mid-cap arm, no "one more feature family." Note the
mid-cap arm is already parked in `EXPANSION_PLAN` §7 as "revisit only after
E2's F6 read." That is a pre-built ramp to E3 and it should be closed, not
left open.

**K3 — The framing test.** The owner's real goal is a tool they use, not a
verdict they read. Their own commissioning word was *"product."* If that is
the true goal, the backtest is a detour: re-aim F3/F4 at a screening
deliverable and run the backtest as a cheap by-product on the core stratum.

**K4 — The price test.** 3–6 weeks of calendar, 6–14 machine overnights, and
a **second full owner-adjudicated spot-check at G2** exceed what the owner
would pay for an answer the charter forbids them from acting on.

**K5 — The power-honesty test.** A pre-G3 sensitivity check, incorporating
labeler attenuation (§1.2) and fold non-independence, shows the achievable
MDE is no better than ~0.035 — i.e. E2 can only deliver "not economically
large," which the owner arguably already believes. If E2 cannot beat the
belief it is testing, it is not an experiment.

**PIVOT rather than stop if:** the assets are worth more as a tool than as
an experiment. On the evidence in §2 and §3, I believe they are.

---

## 7. Does the kill case win?

**CONDITIONAL NO.**

**Why it loses as "stop the project":**

1. **Forward cash is $0** and forward machine cost is overnight-and-resumable. The classic kill-case argument — "this is burning money" — is simply absent.
2. **The diagnosed cause of E1's null is real, and E2 genuinely fixes it.** I verified independently (C4) that the panel delivers ~96 usable core companies × 30 quarters. The power design is not aspirational.
3. **The heaviest and least reusable cost is already sunk.** F1–F2 (universe construction, 45,632-filing enumeration, 43 GB of documents, 622,661 fundamentals rows, 1.96M price rows) is done. The remaining phases produce reusable assets regardless of outcome.
4. **A bounded null at \|δ\| ≲ 0.03 is a real answer**, not a consolation prize — and it is the 60%-likely outcome.

**Why it wins on a narrower and more important claim:**

**The project's current trajectory optimizes for the wrong deliverable.**
The evidence:
- The charter forbids acting on the one thing E2 measures (§2), and no document says what happens if E2 succeeds.
- The owner's own language has moved to "product," and the two framings demand different work (§3).
- Measurable effort serves neither framing: 28.0% of the labeling corpus is in a stratum bound out of the primary analysis; a 3,675-line ingester and a 13-agent org chart contradict the owner's own dated engineering philosophy; 20,396 lines of prose support one experiment.
- There is **no pre-registered decision rule for the 22%-likely ambiguous outcome**, which is the outcome most likely to generate E3.
- E2 scales the sample but not the *representation* — 22 hand-designed rate features, 52.2% of observations carrying no MDA/RF text, guidance NaN on 90.2% of rows, and no measure of year-over-year language change at all. This is the honest core of the owner's word "outdated," and E2 does not address it.

**Therefore: continue, but only after three cheap conditions are met this
week. If any cannot be met, stop or pivot.**

**Condition 1 — Close G1 in writing, with the attenuation number in hand.**
It has been open four days and it is the gate that determines whether E2's
text features are worth building. Close it against the labeler-attenuation
figures in §1.2 (ρ≈0.57 on negative-sentiment share, ρ≈0.81 mean on
red-flag rates), not just the raw agreement rates — those rates flatter the
student because red-flag exact-set agreement is being compared to a teacher
that fails its own quality bar.

**Condition 2 — Pre-register a decision rule for all three outcomes at G3,
including "no E3."** Write it into `HANDOFF` §3 before F5 runs, and close
the mid-cap ramp in `EXPANSION_PLAN` §7 while you are there.

**Condition 3 — Resolve product-vs-research in writing before F3 starts.**
One paragraph in `HANDOFF` §1. If the answer is "research," drop or defer
the extension stratum's labeling (28% of the critical path, zero primary
value — the data is already ingested, so deferring costs nothing and is
reversible). If the answer is "product," re-aim F3/F4 at a screening
deliverable and treat the backtest as a by-product.

**One addition worth more than anything else in E2's remaining budget:**
before or alongside F5, add **one non-hand-designed text feature family** —
document embeddings of MDA/Risk-Factors, or a year-over-year
language-change measure against the prior filing. It is $0 and local, it
runs on the corpus already on disk, it does not depend on the labeler at
all, and it is the only thing on the table that could distinguish "there is
no signal in filing text" from "there is no signal in *these 22 features*."
Right now E2 cannot tell those apart, and that is the difference between a
result and a bounded restatement of E1's.

---

*Prepared as Lens 1 of a four-lens re-evaluation. This lens was briefed to
argue against continuation; its §5.2 and §7 corrections against its own case
are part of the deliverable, not hedging. No number in this file should be
quoted without the computation note beside it.*
