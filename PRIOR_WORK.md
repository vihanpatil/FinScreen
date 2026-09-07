# PRIOR_WORK — where FinScreen sits in the literature

**Written 2026-08-25** as item H6 of the F2.5 hardening package
(`HARDENING_PROGRESS.md`). It exists because the re-evaluation's
alternatives lens grepped the whole markdown corpus for `Loughran`,
`McDonald`, `FinBERT`, `prior work`, `literature`, `related work` and found
**zero hits** outside a SIC-code row naming McDonald's the restaurant
(`data/reevaluation_2026-08-25/alternatives.md` §2c). A project this
careful about measurement had never once positioned itself against the
field it is re-testing.

---

## 0. Read this before using anything below

**Provenance, stated plainly: this document was written from the
re-evaluation lens's recalled literature summary, not from fresh
retrieval.** No source below was fetched, opened, or checked against a
publisher this session or in the lens's own session. The lens says so
itself (`alternatives.md` §7): *"all literature in §2 [is] recalled, not
verified in this pass. Directions and existence are high-confidence; exact
magnitudes, years, and journal placements should be re-checked before
anything is published on their basis."* **Verify every citation before any
external use.** Treat years, journals, and effect sizes as unconfirmed;
treat the *direction* of each finding as the lens's stated
high-confidence recollection.

**These are model judgments.** The literature summary is one model's
recall, and the four re-evaluation lens verdicts are model judgments
(HANDOFF §3, 2026-08-25). Nothing here is human validation of anything.
The same clause governs FinScreen's own label-quality numbers quoted
below: agreement rates over model-adjudicated fields measure model
consensus, not ground truth.

**The lens's own coverage gap:** its knowledge cutoff means the 2025–2026
LLM-on-filings literature and product landscape are under-represented, so
§2's picture of how crowded this space is is more likely understated than
overstated.

**Non-goals are unchanged and unconditional** (`HANDOFF.md` §1): not a
trading bot, not investment advice, no live capital, no return
guarantees. Nothing in this file is a performance claim, and every
FinScreen number quoted carries the scheme that produced it in the same
sentence or paragraph.

---

## 1. What the field already knows

One line each, as the lens recorded them. Citations unverified (§0).

**Tone and dictionaries**
- **Loughran & McDonald (2011, *Journal of Finance*)** — built
  finance-specific word lists because general-purpose sentiment
  dictionaries misclassify finance vocabulary. Return results from this
  family are real but small, short-horizon, and have decayed.
- **Tetlock (2007)**; **Tetlock, Saar-Tsechansky & Macskassy (2008)** —
  media/news tone predicts returns weakly and mean-reverts within days.
- **Feldman, Govindaraj, Livnat & Segal (2010)** — MD&A tone *change*
  around earnings carries incremental information over the accounting
  surprise.
- **Huang, Teoh & Zhang** and the tone-management literature — managers
  manage tone strategically, which is a mechanism for why tone-*level*
  features attenuate out of sample.
- **Loughran & McDonald (2014)** — 10-K file size as a readability proxy;
  the complexity/length feature family.

**Risk language and uncertainty**
- **Kravet & Muslu (2013)** and **Campbell et al.** on risk-factor
  disclosure — risk language predicts **volatility and uncertainty**, and
  does so far more reliably than it predicts **return direction**. *(The
  lens records "Campbell et al." without initials or year; complete this
  citation before external use.)*

**Distress**
- **Mayew, Sethuraman & Venkatachalam (2015)** — MD&A language predicts
  going-concern / bankruptcy incrementally over financial ratios.

**The surviving text→return result**
- **Cohen, Malloy & Nguyen, "Lazy Prices" (2020, *Journal of Finance*)** —
  the strongest surviving text→return effect is *not* tone. It is
  **year-over-year textual change** in 10-K/10-Q: firms that change their
  filings underperform firms that don't. The lens calls this the effect in
  this literature that has best survived replication.

**Model-era filing NLP**
- **FinBERT** (Araci 2019; Huang, Wang & Yang, *Contemporary Accounting
  Research*) — domain-pretrained transformers for financial text.
- **Kim, Muhn & Nikolaev (2024)** on LLM financial-statement analysis and
  "bloated disclosure"; **Lopez-Lira & Tang (2023)** on LLM headline
  forecasting.

**The field's answer to FinScreen's own question.** Does LLM-labeled
filing sentiment / guidance / red-flag content beat a numeric baseline for
cross-sectional quarterly returns in large caps? The lens's verdict:
*"barely, and less every year"* — and large caps are the most efficiently
priced, most-analyst-covered slice, i.e. the worst place to look for a
text edge. **E1's null was the expected result; a null at E2 is the modal
expected outcome.**

## 1a. The tooling is crowded too

Free/academic: SEC EDGAR full-text search; SEC DERA Financial Statement
Data Sets; the Loughran-McDonald 10-X summary files; WRDS SEC Analytics
Suite; `edgartools` / `sec-edgar-downloader`; FinBERT. Commercial:
AlphaSense (absorbed Sentieo), Bloomberg document search, S&P/Kensho,
Hebbia, Daloopa, Calcbench, Intrinio, sec-api.io. "Point an LLM at a 10-K
and extract structured signals" is, in the lens's words, a 2023–2024
commodity in 2026. As a *capability* it is not novel.

---

## 2. What FinScreen replicates — and at what power

E1's feature families — sentiment, guidance, red-flag rates, section-mix —
are the 2011–2015 tone-and-counts generation, applied with a modern
labeler. That is a replication, not an extension.

**The E1 result, with its method attached.** Over 6 quarterly expanding
walk-forward folds (sorted by public filing-availability date, expanding
window, 6-quarter burn-in; 581 of 630 filing-level observations with a
complete 63-trading-day forward window; target = forward excess return vs
the 25-stock universe average, filing-date aligned), an XGBoost
text-plus-numeric model was compared against a **numeric-fundamentals-only
baseline on the same folds and the same target**. Cross-fold mean
deduplicated Spearman IC delta: **−0.0097 (std 0.0677, 2 of 6 folds
positive)**; the raw (non-deduplicated) column disagrees in sign at
**+0.0177 (3 of 6)**. Family-level (`data/diagnosis_report.md`; HANDOFF
§2a): guidance is the only family positive on the full-sample grid
(**+0.0345 dedup, 5/6 folds**) and flips negative under 10-Q/10-K form
control (**−0.0125, 2/6**); section-mix is strongly negative once
form-confounding is controlled (**−0.0841**). Verdict as written:
**no family, category, or company shows a fold-robust contribution.**

**And it was underpowered against the literature's own effect sizes.**
E1's design has a minimum detectable cross-fold mean IC delta of **~0.077
(95%/80%)** — larger than any text delta ever observed in the data
(`EXPANSION_PLAN.md` §2a). A literature whose surviving effects are
"small and decaying" cannot be tested at that threshold. E1 therefore
replicates the field's *conclusion* without having replicated its
*measurement precision*.

**One number that cuts the other way.** The numeric-only baseline's own
cross-fold mean deduplicated IC over those same 6 folds is **+0.0972 (4 of
6 folds positive; sample std 0.187)** — re-derived by the lens from
`data/diagnosis_report.md` §1a. The "text adds nothing" finding is a
difference measured against a baseline that is itself not established as
robust at 6 folds. That is the strongest honest argument E2 has, and it is
an argument for more folds rather than for more text.

**E2's power, and a caveat on quoting it.** `EXPANSION_PLAN.md` §2a states
an MDE bracket of **0.019–0.037** at 136 members × ~26 test folds.
Hardening item H2 is in flight to restate that bracket honestly and
append a dated amendment (`HARDENING_PROGRESS.md` §H2) — **quote the
amended §2a, not this line, once H2 lands.**

**E1 and E2 backtest numbers are numerically incomparable.** E2 redefines
the benchmark (equal-weighted average over that reconstitution date's
members, excluding self, membership-dated) and regenerates all targets
[OWNER-GATE G3, `EXPANSION_PLAN.md` §3.3]. Wherever an E1 and an E2 number
appear together, that sentence has to appear with them.

---

## 3. What FinScreen adds that the literature does not supply

The lens's answer, and mine: **not the backtest.** Three things, none of
which is a return result.

**(a) The survivorship-safe point-in-time membership panel and its
censoring census.** The free ecosystem gives you filings and XBRL. It does
not give you a *dated, float-ranked, sector-stratified membership table
reconstituted from pre-date filings only*: 244 CIKs, 299 membership
spells, 136 members × 11 annual reconstitution dates = 1,496 member-date
cells, with membership at each date decided from filings public before
that date (`EXPANSION_PLAN.md` §1; `data/E2_UNIVERSE_REPORT.md`). Attached
to it is a measured outcome-censoring profile in membership-time —
**14.0% / 16.2% / 12.5% of member-date cells in the 2016 / 2017 / 2018
cohorts, 6.35% pooled over 1,496 cells, decaying to 0.0% by 2026**
(`data/F2_INGESTION_REPORT.md` §9). Most published finance-NLP quietly
uses a survivor universe. This one doesn't, and measured what that costs.
The lens calls it the most externally valuable artifact in the repo.

**(b) The failure taxonomy for building an EDGAR corpus.** Three
high-confidence earnings-document selection error classes, all fixed,
re-run and content-verified: **Prologis (42 of 45 filings — the
supplemental package instead of the release)**, the **B1 class (15 filings
storing the 8-K cover page)**, and **PSEG (45 of 45 — conference-call
slide decks)**. Plus float mis-scaling (**MedEquities, $316.7B**,
`data/E2_UNIVERSE_REPORT.md`) and the dead-ticker trap where SEC's bulk
symbol map points at a *different* live CIK (the APC/EMC shape; the XOM
case that never WARNed while the safe direction did,
`data/F2_INGESTION_REPORT.md`). The line that makes the taxonomy worth
publishing is the confession, not the fixes: **"each was found by a human
read or a screen built after one, never by the confidence label,"** and
the residue — **51 of 71 flagged CIKs were never manually read, the final
worklist of 57 still has 37 uncovered, PSEG was never on that worklist at
all, and every filer below the watch-list bar is unmeasured for these
classes, not clean** (§9 of the same report). Nobody writes this down.

**(c) The distillation-with-a-noise-ceiling evaluation pattern.**
Reporting the local student against *the teacher's own reproducibility*
rather than against 100%: red_flags exact-set **64.87% student** (650/1,002
held-out rows, greedy decoding, adapter and eval-row SHAs pinned in the
report's provenance table) against the teacher's **63.4%**
teacher-vs-auditor exact-set rate; per-category **92.42% student** against
the teacher's 92.5% (7.5% per-category error)
(`finetune/runs/2026-08-22-eval-epoch2/eval_report.md`; HANDOFF §2a). And
reporting both bases side by side every time, because they differ by ~28
points and answer different questions. Two honest qualifiers travel with
this pattern: these are **agreement-with-the-teacher rates, not accuracy**
— a student that agrees perfectly has reproduced the teacher including its
errors — and the student's own weak heads are stated, not smoothed
(sentiment 83.5% against the teacher's 94.6%, NEGATIVE recall 0.487;
guidance raw 58.8%, and the 98.4% "post-ruled" figure is a *proposed,
not adopted* missing→NONE rule that is carried by the majority class —
on the 17 held-out rows where the teacher recorded real guidance the
student is right on 11).

---

## 4. The three F5 heads against the literature

F5 runs three heads (owner ruling 2026-08-25, HANDOFF §3;
`EXPANSION_PLAN.md` §8.5). What the recalled literature says about each:

| F5 head | What it tests | Literature's verdict (recalled, §0) | Honest expectation and caveat |
|---|---|---|---|
| **1. Pre-registered return target** — cross-sectional forward excess return, quarterly horizon, 136 large caps | The tone/flag-rate generation of finance NLP | **Closest to settled — but "settled small and decaying," not "settled zero."** Loughran-McDonald and Tetlock-family return effects are real, small, short-horizon, and have decayed; tone management (Huang/Teoh/Zhang) is a named mechanism for out-of-sample attenuation; large caps are the worst place to look | A bounded null is the modal outcome and is a pre-committed acceptable result (`DISCOVERY.md` §5; `EXPANSION_PLAN.md` §2a). **Partial move toward the known-positive family:** E2 adds year-over-year filing-change/novelty (Item 1A / Item 7 similarity) and pooled document embeddings as zero-labeling text families (`EXPANSION_PLAN.md` §8.4) — the **Lazy Prices** change-based feature, which is the one text→return effect the lens says best survived replication. That family, not the tone features, is where this head's plausible signal is |
| **2. Volatility / informativeness event study** — ~5,552 in-membership earnings 8-Ks with price coverage | Whether filing/risk language moves realized volatility and uncertainty around the event | **Real, per the literature the lens names** — Kravet & Muslu (2013) and Campbell et al.: risk language predicts volatility/uncertainty far more reliably than return direction | Tests a hypothesis the field says is true, so a null here is informative about the *pipeline*, and a positive is a real result. Also structurally cleaner: the dependent variable is immune to the benchmark-definition problem G3 has to settle, largely immune to the delisted-price censoring profile, and immune to the missing dividend adjustment at short windows. Charter-safe: it measures disclosure informativeness, not return prediction |
| **3. Exit prediction** — 86 of 244 CIKs (35.2%) with a Form 25, Form 15, or 8-K item 1.03 | Whether filing text anticipates a corporate exit | **Mixed, and the mapping is imperfect.** Mayew et al. (2015) supports *distress/going-concern* prediction from MD&A language — but this universe's exits are dominated by acquisitions and take-privates, and it contains **exactly one bankruptcy-8K CIK (Expand Energy, ex-Chesapeake)** | **Do not present this head as a replication of Mayew et al.** As constituted it is corporate-*exit* prediction (well-powered, M&A-heavy), not financial-distress prediction — which the lens judges **not viable in this universe**, because large caps don't go bankrupt. The M&A-vs-distress separation from stored 8-K items is required work, not a footnote. Compensating strength: the label is a *filing*, not a price, so the delisted-price censoring that damages head 1 does not touch it |

**Positive controls, which the literature makes possible and the plan
previously lacked.** Nowhere in E2 was there a known-positive effect the
harness must recover, which makes any null uninterpretable — "there is no
text signal" is not separable from "this harness cannot detect any
signal." Hardening item H1 is running exactly that: T1, the
contemporaneous earnings-surprise / announcement-window relationship over
the ~5,552 usable events; T2, a documented numeric anomaly (PEAD at ~60
days and/or 12-1 momentum) at the actual backtest configuration — both
weak in large caps post-2000, so the honest expectation is "small and
positive," and a flat zero is a red flag about the configuration rather
than about text (`HARDENING_PROGRESS.md` §H1; `alternatives.md` §D5a).
The text-side control is the Lazy-Prices change family in head 1.

---

## 5. Limitations that bind any comparison to published work

These are the standing limitations, restated here because they are what
stops a FinScreen number from being read alongside a published one.
Canonical records: `LIMITATIONS.md`, `RED_FLAGS_LIMITATION.md`,
`data/F2_INGESTION_REPORT.md` §9.

- **The red-flag labels fail this project's own quality bar.** Agreement
  **63.4% [58.6, 68.0]** over 399 evaluable chunks of the 400-chunk
  spot-check sample, against a pre-registered 0.70 lower-bound bar — the
  *upper* bound is below the bar. It is an **exact-set-match** rate and is
  not comparable to the single-value sentiment (94.6%) or guidance (95.2%)
  rates printed beside it. The sample deliberately oversamples rare and
  contested text, so the base-rate-representative figure is **Tier C:
  75.0% agreement / 25.0% exact-set error, n=36, 95% Wilson CI
  [58.9, 86.2]**, and the per-category error is 7.5% (180/2,394). Quote
  the basis with the number, always.
- **Those agreement rates are model consensus, not human validation.** Of
  1,222 (chunk, field) judgments, **1,023 came from a second-rater model,
  95 from a third-rater model, and 104 were the owner's own** — that is
  the entire human input (HANDOFF §3 epistemics clause; `LIMITATIONS.md`
  §2.3).
- **Red-flag labels are config-sensitive: 22.2% (935/4,219 chunks)** of
  red-flag sets changed between two full-corpus labeling passes of the
  *same* chunks under different model configurations (sentiment 3.6%,
  guidance 0.9%, distress 0.7%). Red-flag counts are partly a function of
  how the model was asked, not only of what the filing says. The
  instability was invisible at 50-chunk canary scale.
- **~27–46% of chunks name their own company** (26.8% strict / 46.0% loose
  measurement, `REDTEAM_WEEK3.md` finding #2) — an open look-ahead channel
  mitigated only by a prompt instruction. How often it was *exploited* is
  unmeasured.
- **Price provenance is an unresolved exception, not a licensed feed.**
  Yahoo's keyless chart endpoint; `robots.txt` disallows automated access
  and there are no published terms for this use (Stooq, the ratified
  example source, is bot-gated). Split-adjusted, **not** dividend-adjusted
  (`data/PRICES_NOTES.md` §1–§2). Any external release ships a fetch
  script, never the price data.
- **E2's outcome-side censoring residual is not fixed and cannot be**
  (`EXPANSION_PLAN.md` §2c). Selection is survivorship-free; the *outcome*
  right-censors at delisting, informatively. Operative census: **32
  members with no usable prices (28 core / 4 extension)**, alongside the
  membership-time profile in §3(a) — time-decaying and outcome-correlated,
  so it can make early folds differ from late folds for a non-alpha
  reason.
- **The labeler-contamination flag** (`EXPANSION_PLAN.md` §3.2): the
  student was trained on E1 text, so on E1-era chunks it partly replays
  memorized labels and on new ones it generalizes. Every E2 chunk carries
  a train-overlap-vs-novel provenance flag and key results are reported
  with and without the overlap set.
- **A mixed result stays mixed.** The pre-committed honesty rule
  (`DISCOVERY.md` §5): if the text-augmented model does not beat the
  numeric-only baseline by more than fold noise, the conclusion is stated
  as *"the text signal didn't help here"* — not hedged into something that
  reads as success.

---

## 6. Citation status, and what to do before publishing

| Claim class | Status | Action before external use |
|---|---|---|
| Every author/year/journal in §1 | Recalled by the lens, not retrieved | Fetch and verify each; correct or drop what doesn't hold |
| "Campbell et al." | Incomplete citation — no initials, no year | Complete it or remove the name |
| Effect directions ("tone effects small and decayed"; "risk language → volatility"; "Lazy Prices is the surviving text→return effect") | Lens's high-confidence recall, magnitudes explicitly not | Verify direction; never quote a magnitude from this file |
| The 2025–2026 LLM-on-filings landscape | Under-represented (lens cutoff) | Re-survey; expect the space to be *more* crowded than §1a says |
| "Nobody writes the failure taxonomy down" / "it would be read" | The lens flags audience demand as **speculation**, believed on the merits with no evidence | Present as a judgment, never as an established fact |
| Every FinScreen number in §2–§5 | Traceable to a named repo file, quoted with its measurement | Keep the measurement attached; re-check against the file, since several are regenerated by later phases |

**Where this leaves the project, in one paragraph.** The question E2 asks
has been asked for fifteen years and answered "barely, and less every
year," in the least favorable universe for finding a text edge. That is a
reason to hold the return head to a pre-registered, bounded-null
standard — not a reason to skip it. The parts of this repo with the least
literature overlap are the point-in-time membership panel with its
censoring census, the EDGAR corpus failure taxonomy, and the
teacher-ceiling evaluation pattern; two of the three F5 heads test effects
the field says are real. Positioning the work honestly means saying both:
the backtest replicates a settled question at last-generation feature
design, and the infrastructure and methods trail around it are the durable
contribution.
