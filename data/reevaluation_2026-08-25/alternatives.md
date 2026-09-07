# LENS 4 — Alternatives and upside scout

**Written 2026-08-25.** One of four lenses in the owner-commissioned
re-evaluation. Scope: given the asset base actually on disk, map the
highest-value directions from here, price them honestly, and answer
directly whether this work is duplicative of existing tools and literature.

**Method.** Read-only. Every artifact claim below was re-derived from the
files, not taken from a report's self-description; the derivations are shown
inline. No network calls, no edits to any pipeline file. Literature claims
are recalled from training knowledge and are **not** verified against live
sources in this pass — they are flagged as such and should be spot-checked
before anything is published on their basis.

**Framing note.** This lens is deliberately opportunity-seeking. It is not
the risk lens and not the verdict lens. Where I think the current plan is
wrong I say so, but the synthesis should weight this document as "what else
is on the table," not "what to do."

---

## 1. The asset base, verified

Not the docs' description of the assets — what I found on disk.

| Asset | Verified measurement | How I checked |
|---|---|---|
| PIT filing metadata at scale | `filings` = **45,545** rows (8-K 35,591 / 10-Q 7,509 / 10-K 2,445), 2015–2026, ~3.6–4.5k filings/yr every year | `sqlite3 data/filings_metadata_e2.db` counts |
| Dated survivorship-safe membership panel | **244** CIKs, **299** spells, 136 members × 11 annual reconstitution dates = 1,496 member-date cells | `universe_membership` table |
| Document corpus | 20,521 primary-document targets cached, **42 GB** under `data/raw/documents/`; 129,249 exhibit rows inventoried across 10,569 earnings 8-Ks | `du -sh`, `filing_documents` |
| Fundamentals | **622,661** rows, 30 tags / 14 concept families, 244 companyfacts docs | `data/fundamentals_e2.parquet` shape |
| Prices | **1,960,738** daily rows, **213** CIKs, ~52k rows/yr 2015→2025 | `data/prices_e2.parquet` |
| EDGAR-native exit events | **86 of 244 CIKs (35.2%)** have a Form 25, Form 15, or 8-K item 1.03; 3–17 distinct CIKs per year, every year 2015–2026 | `distress_events` grouped |
| Earnings-announcement events, usable | **5,552** item-2.02 8-Ks that fall inside their own membership spell *and* whose CIK has price data | join `filings` × `universe_membership` × `prices_e2` |
| Local labeler | Qwen2.5-7B-4bit + MLX QLoRA, 2 epochs, **0.00%** parse/schema failure, **1,337 chunks/h** measured on the owner's machine | `finetune/runs/2026-08-22-eval-epoch2/eval_report.md` |
| E1 frozen labeled corpus | 6,747 chunks (6,746 labeled) from 630 filings / 884 sections, 3-rater adjudicated on a 400-chunk sample (1,222 judgments) | `labels.parquet`, `filings.parquet`, spotcheck |
| Leakage-tested harness | `features.py` / `backtest.py` / 55-test leakage suite; form-controlled ablation; company-quarter dedup; PIT staleness guard | Phase C record |
| Methods trail | HANDOFF / LIMITATIONS / RED_FLAGS_LIMITATION / F2 report with 21 red-team findings and three self-confessed corpus defects | read |

**This is a serious asset base.** The infrastructure half of it — a
survivorship-safe, point-in-time, float-ranked, sector-stratified 244-company
× 11-year EDGAR panel with a per-filer earnings-exhibit selection audit, an
automated XBRL alias/migration classifier, and a fully documented censoring
census — is scarce. It is the part of financial-text research that most
people skip, buy (WRDS/Compustat), or get wrong. It cost $0 and it exists.

**One number the docs undersell.** E1's *numeric-only* baseline has a
cross-fold mean deduplicated IC of **+0.0972** (std 0.187, 4/6 folds
positive; re-derived from `data/diagnosis_report.md` §1a's numeric_only rows).
The whole "text adds nothing" finding is a difference measured against a
baseline that is itself not established as robust at 6 folds. That is an
argument *for* more folds, and it is the strongest honest argument E2 has.

---

## 2. Is this duplicative? Direct answer, with names

*(All literature below is recalled, not re-verified in this pass. Confidence
is high on the existence and direction of these results, moderate on exact
magnitudes and dates.)*

### 2a. The research question is heavily trodden and the answer is known

The question E1 asked and E2 re-asks — *does LLM-labeled filing sentiment /
guidance / red-flag content beat a numeric baseline for cross-sectional
quarterly returns in large caps?* — sits in a literature that is ~15 years
deep and has largely converged:

- **Loughran & McDonald (2011, *Journal of Finance*)** built finance-specific
  word lists precisely because general-purpose sentiment dictionaries
  misclassify finance vocabulary. Their and successors' return results are
  real but small, short-horizon, and have decayed.
- **Tetlock (2007)**; **Tetlock, Saar-Tsechansky & Macskassy (2008)** —
  media/news tone predicts returns weakly and mean-reverts within days.
- **Feldman, Govindaraj, Livnat & Segal (2010)** — MD&A tone *change* around
  earnings carries incremental information over the accounting surprise.
- **Loughran & McDonald (2014)** — 10-K file size as a readability proxy;
  the "complexity/length" family of features.
- **Huang, Teoh & Zhang** and the tone-management literature — managers
  strategically manage tone, which is precisely why tone-level features
  attenuate out of sample.
- **Kravet & Muslu (2013)**, **Campbell et al.** on risk-factor disclosure —
  risk language predicts **volatility and uncertainty**, and does so far more
  reliably than it predicts **return direction**.
- **Mayew, Sethuraman & Venkatachalam (2015)** — MD&A language predicts
  going-concern/bankruptcy incrementally over financial ratios.
- **Cohen, Malloy & Nguyen ("Lazy Prices," 2020, *JF*)** — the strongest
  surviving text→return result is *not* tone. It is **year-over-year textual
  change** in 10-K/10-Q: firms that change their filings underperform firms
  that don't.

**Verdict on the question:** asking again, at 136 large caps and a quarterly
horizon, with tone/flag-rate features, is asking a question the field has
answered "barely, and less every year." Large caps are the most efficiently
priced, most-analyst-covered slice of the market — the single worst place to
look for a text edge. **E1's null was the expected result and E2's null is
the modal expected result.** That is not a reason not to run it, but it is a
reason not to expect the run to produce external value.

### 2b. The tooling is also crowded

Free/academic: SEC EDGAR full-text search; SEC DERA Financial Statement Data
Sets; the Loughran-McDonald 10-X summary files (widely used, free); WRDS SEC
Analytics Suite; `edgartools`/`sec-edgar-downloader`; FinBERT (Araci 2019;
Huang, Wang & Yang in *Contemporary Accounting Research*). Commercial:
AlphaSense (absorbed Sentieo), Bloomberg document search, S&P/Kensho,
Hebbia, Daloopa, Calcbench, Intrinio, sec-api.io. Modern LLM-on-filings
research: Kim, Muhn & Nikolaev (2024) on LLM financial-statement analysis and
on "bloated disclosure"; Lopez-Lira & Tang (2023) on LLM headline forecasting.

**Verdict on the tooling:** "point an LLM at a 10-K and extract structured
signals" is a 2023–2024 commodity in 2026. As a *capability* it is not novel.

### 2c. Where the genuine, non-duplicative value actually is

Three places, none of which is the backtest:

1. **The survivorship-safe PIT universe panel and its censoring census.**
   The free ecosystem gives you filings and XBRL. It does not give you a
   *dated, float-ranked, sector-stratified membership table reconstituted
   from pre-date filings only*, with a measured outcome-censoring profile in
   membership-time (14.0%/16.2%/12.5% of member-date cells in the 2016/17/18
   cohorts, decaying to 0% by 2026). Most published finance-NLP quietly uses
   a survivor universe. This project didn't, and measured what that costs.
   **This is the most externally valuable artifact in the repo.**

2. **The failure taxonomy for building an EDGAR corpus.** PSEG's 45-of-45
   conference-call slide decks stored as earnings releases. The B1 class:
   15 filings that stored the 8-K cover page. Prologis's 42-of-45 supplemental
   packages. Float mis-scaling ($316.7B MedEquities). Dead tickers that
   resolve on Yahoo to *different live companies* (APC→ARKO, EMC→ETF). And the
   line that makes it valuable: **"each was found by a human read or a screen
   built after one, never by the confidence label"** — plus the honest
   residue that 37 of 57 worklist CIKs were never read and "every filer below
   the watch-list bar is unmeasured for these classes, not clean."
   Nobody writes this down. It would be read.

3. **The distillation-with-a-noise-ceiling evaluation pattern.** Reporting a
   student model against *the teacher's own reproducibility* (red_flags
   exact-set 64.87% student vs 63.4% teacher-vs-auditor) rather than against
   100%, and reporting exact-set and per-category rates side by side because
   they differ by ~28 points and answer different questions. This is a clean,
   teachable methodological move that most distillation write-ups get wrong.

**One structural gap worth naming: there is no prior-work section anywhere in
this repo.** I grepped the entire markdown corpus for Loughran, McDonald,
FinBERT, "prior work," "literature," "related work" — **zero hits** outside a
coincidental SIC-code row mentioning McDonald's the restaurant. A project
this methodologically careful that has never positioned itself against the
literature is at risk of two failure modes at once: re-deriving known results
and believing them novel, and missing the known-positive results (Lazy
Prices, risk-language→volatility) that its own corpus supports better than
the one it chose to test.

---

## 3. Direction map

Costs use three currencies: **overnights** (owner's machine, unattended),
**weeks** (owner attention + agent sessions), **tokens** (Max-subscription
budget; F2 needed a dedicated resume ledger because it threatened session
limits, so this is a real constraint, not a footnote).

### D1 — Finish E2 exactly as planned (F3 → F6)

**Yields.** A pre-registered answer at real power: MDE bracket 0.019–0.037,
~26 test folds. Either a small positive text delta, or — most likely — a
*bounded* null: "no text-vs-numeric improvement of economically relevant size
(|δ| ≳ 0.03) exists in this universe." Also closes the E1-numeric-baseline
question (is +0.097 real at 26 folds?), which is genuinely worth knowing.

**Cost.** F3 extraction + QA over 20,521 documents spanning 244 filers and
11 years, where `extract.py`'s calibrations were all fit on 25 mega-caps'
2023–2026 filings — the F2 report calls extraction/QA "the wall-clock
elephant" and its own evidence is that confidence scoring caught *none* of
three whole error classes. **Estimate: 2–4 weeks of attention, and plausibly
the most token-expensive phase in the project — more than F2, which already
needed a resume ledger.** F4 labeling: see the correction in §5 below —
**7–17 overnights**, not the plan's 5.7–7.8. F5+F6: 1–2 weeks. **Total
realistic: 5–9 weeks of attention, 10–20 overnights.**

**Charter fit.** Perfect. It is the ratified plan, with a pre-committed
acceptable null.

**Competes/complements.** F3 and F4 are *shared infrastructure* for almost
everything else on this list. So "finish E2" partly means "build the thing
every other direction also needs." The part that is genuinely E2-specific and
genuinely optional is **F5's choice of target and the G3 benchmark work.**

**Honest risk.** The most likely output is a private negative result on a
question the literature already answered, at a cost of 5–9 weeks. If the
owner's anxiety is about producing something *useful*, D1 is the option that
best satisfies the charter and worst satisfies the anxiety.

---

### D2 — Same corpus, different targets

#### D2a — Corporate-exit / distress screening

**Yields.** A classification target with an EDGAR-native label: 86 of 244
CIKs (35.2%) have a Form 25, Form 15, or 8-K item 1.03, spread 3–17 CIKs per
year across every year 2015–2026. The elegant part: **because the label is a
filing, not a price, the delisted-price censoring that damages the return
target does not touch this target at all.** E1's fatal `GOING_CONCERN n=0`
problem is also solved — E2's universe contains real exits.

**Honest correction to my own idea, which matters.** Form 25 and Form 15 fire
for *acquisitions and take-privates* as much as for distress. The universe
has exactly **one** bankruptcy-8K CIK (Expand Energy, ex-Chesapeake). So:
*corporate-exit prediction* is well-powered and interesting; *financial-
distress prediction* is **not viable in this universe**, because large caps
don't go bankrupt. That is the same cap-tier survivorship problem E1 had, and
**the 2026-08-20 "no mid-cap arm" ruling is exactly what preserves it.** If
distress screening ever becomes the goal, the mid-cap arm has to come back.

**Cost.** Needs F3 + F4 anyway. Marginal cost over D1 at F5: ~1 week (a second
target head, plus the M&A-vs-distress separation, which is doable from stored
8-K items but is real work).

**Charter fit.** Excellent — arguably *better* than alpha. The charter's own
one-line description of FinScreen names "red flags / distress" as a purpose.

**Competes/complements.** Pure complement. Same F3/F4, different head at F5.

#### D2b — Guidance-revision prediction

**Yields.** 10,569 earnings 8-Ks over 11 years is a genuine guidance panel;
scaling E1's rates gives roughly 700 RAISED / 700 MAINTAINED / 280 LOWERED —
evaluable, where E1's 34/34/14/1 was not.

**Blocker, and it is serious.** The guidance head is the *weakest* part of
the student model, and its headline number hides that. Epoch-2 raw guidance
agreement is 58.8%; the ~98.4% "post-ruled" figure comes entirely from
mapping a missing field to NONE — i.e. the student's good score is achieved by
*declining to emit the field*, and NONE recall is 0.586. The non-NONE classes
have eval support of **n=7 / 7 / 3**. The classes that carry all the signal
are effectively **unvalidated**. Running D2b on this labeler without first
fixing and re-measuring the guidance head would be building on sand.

**Cost.** F3 + F4 + a guidance-head retrain/re-eval (~1 overnight + 1 week).
**Charter fit.** Fine. **Competes/complements.** Complements, but gated on a
labeler fix that nobody has scheduled.

#### D2c — Filing-change detection (needs no labels at all)

**Yields.** Year-over-year and quarter-over-quarter textual similarity between
a company's consecutive 10-K/10-Q filings. This is the **Lazy Prices** feature
family — the single text→return effect in this literature that has best
survived replication. It requires **F3 (extraction) but not F4 (labeling)**:
no LLM, no labels, no overnights. Cosine/Jaccard/embedding distance between
consecutive same-section texts.

**Cost.** F3 + ~3–5 days. **Zero labeling overnights.**

**Charter fit.** Perfect — a research feature, no advice, no capital.

**Competes/complements.** Strongly complements, and it does something nothing
else on this list does: **it is a known-positive-effect benchmark.** See §4.

---

### D3 — Public methods write-up / open-source release as the primary deliverable

**Yields.** Depends entirely on what is written up.

- **The honest-null paper, on its own: low value.** A negative result on a
  well-trodden question, from a solo project with one universe and no
  identification strategy, is not publishable and will not be widely read.
  I should be blunt: "we ran the standard thing and got nothing" is the
  default outcome of the field, not news.
- **The infrastructure + failure-taxonomy write-up: genuinely valuable.**
  §2c items 1–3 are scarce content. A post along the lines of *"Everything
  that silently corrupts an EDGAR research corpus, measured"* — with PSEG,
  the cover pages, the float mis-scalings, the dead-ticker remapping trap,
  the two-censoring-numbers discipline, and the confession that confidence
  scoring caught none of it — would be read, shared, and cited more than any
  backtest result this project can produce. The null becomes the *epilogue*
  of that piece, not its thesis, and in that position it lands well.

**Hard constraints on any release, verified from the docs:**
- `data/prices_e2.parquet` is **not redistributable** — Yahoo's keyless chart
  endpoint, robots.txt disallows automated access, no published terms. Ship a
  fetch script, never the price data.
- EDGAR documents are public domain; redistributing 42 GB is a bandwidth
  problem, not a legal one. The *derived index* (membership panel, concept
  resolution map, EX-99 selection audit) is the valuable and shippable part.
- Financial PhraseBank / FiQA licensing is unresolved (`LIMITATIONS.md` §3.7)
  — neither is currently ingested, so this only binds future work.

**Cost.** 1–2 weeks. Can be done **today**, on E1 + F1 + F2 alone. It does not
require E2 to finish, and it gets better if E2 does.

**Charter fit.** Compatible — no advice, no performance claims, no capital.
But it is the first step from "private research" toward "public artifact,"
which is where §6's tension becomes live.

---

### D4 — Pipeline/labeler as the product; backtest demoted to one application

**Yields.** A reframe that I think is simply *more accurate than the current
one*: FinScreen is a PIT EDGAR research-corpus builder plus a local $0
filing-text labeler with measured quality. The return backtest is one query
against that asset — and it came up null. Three applications (screening/
retrieval, exit prediction, disclosure-informativeness) instead of one bet.

**Cost.** Near-zero as a *framing* change: rewrite README + MODEL_CARD around
the pipeline, demote the backtest to §N. 3–5 days. As *distribution* (making
it runnable by others): +1–2 weeks for CLI/config/docs.

**Charter fit.** Framing: fine. Distribution: this is exactly where the
charter says "not a product with users," and the practical costs are real —
support burden, the Yahoo ToS problem becoming other people's problem, and
"screening score" being harder to keep on the right side of "not advice" when
strangers hold it.

**Competes/complements.** Complements everything. Costs almost nothing.
**This is the cheapest correct thing on the list.**

---

### D5 — Directions nobody has named

#### D5a — Add a positive control. *(Highest value-per-cost item in this document.)*

**The gap.** E1 tested a hypothesis, got a null, and diagnosed the null. E2 is
a higher-powered rerun of the same test. **Nowhere in the plan is there a
known-positive effect that the harness is required to recover.** Without one,
a null is uninterpretable: you cannot distinguish "there is no text signal"
from "this harness, universe, horizon, benchmark, and target cannot detect
*any* signal." Given how many non-alpha sources of fold heterogeneity the F2
report already documents (time-decaying outcome-correlated censoring; a
current-SIC look-ahead that reaches into membership composition; three
unresolved PIT conventions; 497 of 3,416 unresolved fundamentals families),
this is not a hypothetical concern.

**Three tiers, cheapest first:**

- **T1 — plumbing check, runnable this week, needs no F3/F4 at all.** Do the
  5,552 in-membership earnings 8-Ks with price coverage show the expected
  contemporaneous relationship between the announcement-window return and the
  earnings surprise computed from the already-ingested fundamentals? This must
  be strongly positive. If it is not, there is a bug in the PIT/join/date
  alignment stack and E2 is dead before F3 starts. **Cost: 1–2 days. Uses only
  `fundamentals_e2.parquet` + `prices_e2.parquet` + `filings`.**
- **T2 — a documented (if decayed) numeric anomaly** at the actual backtest
  configuration: PEAD at ~60 days, or 12-1 momentum, in this universe. Both
  are weak in large caps post-2000, so the honest expectation is "small and
  positive." A flat zero here is a red flag about the configuration, not about
  text. **Cost: 2–3 days, same data.**
- **T3 — the text-side benchmark: D2c's filing-change features.** A documented
  text→return effect, on this corpus, with no labeling. **Cost: F3 + 3–5 days.**

**Why this reorders the whole plan.** T1 and T2 cost under a week, need
*nothing* that isn't already ingested, and can invalidate or validate the
entire E2 enterprise before a single extraction session is spent. Running them
before F3 is close to strictly dominant.

#### D5b — The volatility / informativeness pivot. *(The experiment I'd rather run than E2.)*

Every dollar of E2's expansion bought **cross-section** (25→136 names) and
**calendar** (6→26 folds), leaving the *hypothesis* and the *horizon*
untouched. But the literature's finding is that risk/filing language predicts
**uncertainty and volatility**, not **return direction** — and does so at
**short horizons around the filing**, not over a quarter.

The corpus supports that test today and supports it far better:

- **n = 5,552 events** (in-membership earnings 8-Ks with prices), against
  E2's 26 folds × ~136 names. That is a different order of statistical power.
- The dependent variable (|return| or realized vol in a ±k-day window) is
  **immune to the benchmark-definition problem** that gate G3 has to solve,
  largely immune to the delisted-price censoring profile, and immune to the
  missing dividend adjustment (short windows).
- It tests a hypothesis the field says is **true**, so a null is informative
  about the pipeline and a positive is a real result.
- It is fully inside the charter: it measures *disclosure informativeness*.
  No return prediction, no advice, no capital.

**Cost.** F3 (text) + ~1 week. Or, in a text-free first cut, ~2 days with what
is already on disk (does filing *presence/timing/length* move realized vol?).

**This is the strongest single idea in this document.** It reuses the whole
asset base, it is cheaper than E2's back half, and it is aimed at an effect
that plausibly exists.

#### D5c — Screening-as-retrieval: drop prediction, keep usefulness

The charter word is **screening**, not forecasting. A screening tool does not
need to predict returns; it needs to **surface passages a human should read.**
"Show me every filing this quarter where `LEGAL_REGULATORY_ACTION` flipped
HYPOTHETICAL→REALIZED" or "rank this quarter's MD&As by margin-pressure
language relative to the same company's own trailing four quarters" is a
useful, honest, evaluable tool with **zero return claims**. Evaluation is
precision@k under a human read — and this project already owns best-in-class
machinery for exactly that (the 400-chunk stratified sample, blind second
rater, third-rater adjudication, Wilson intervals).

**Cost.** F3 + F4 + ~1 week of query layer. **Charter fit: perfect.** And
critically: **it is the version of FinScreen that is useful to the owner
whether or not alpha exists.** Every other direction's usefulness is
conditional on a statistical result.

#### D5d — Scope-cut E2 rather than run it whole

The 2026-08-21 amendment already binds the **primary confirmatory analysis to
the core stratum**, with the extension arm as a secondary that is *promoted
only if gate G2 clears*. So labeling the extension stratum's 68 CIKs (~28% of
the work) before G2 is buying an arm that G2 might not promote. **Deferring
extension-stratum labeling until after G2 is a plan-consistent scope cut, not
a deviation** — it changes no pre-registered analysis and saves roughly a
quarter of the F3/F4 cost. Worth ratifying explicitly rather than discovering
at overnight 12.

#### D5e — Release the corpus builder, not the research

The sharpest version of D3+D4: the single most valuable shippable artifact is
`build_universe_e2.py` + the membership panel + the XBRL concept-resolution
classifier + the EX-99 selection audit — an **"SEC research corpus builder."**
It makes no performance claim of any kind, so it carries no charter tension at
all, and it is precisely the component with the least literature overlap.
The backtest can stay private forever and this still has external value.

---

## 4. Cost realism — three corrections to the current plan

**(a) F4 labeling is 7–17 overnights, not 5.7–7.8.** Derived, not asserted:
E1's measured per-form section word counts (10-K MDA 15,727 / 10-K RF 10,843 /
10-Q MDA 13,775 / 10-Q RF 1,702 / EX-99 5,184 words on average) applied to
E2's document inventory (2,445 10-K / 7,509 10-Q / 10,567 earnings docs)
project **~236M raw section words**. E1 compressed 7.09M raw section words into
6,747 canonical chunks (1,050 words/chunk *after* its dedup). At the same
compression that is **~225k chunks = 168 h = 17 overnights** at the measured
1,337 chunks/h. The plan's 5.7–7.8 overnights implicitly assumes E2's
cross-company dedup is **2.5–3× more aggressive** than E1's. That is
*plausible* — 244 companies share far more boilerplate than 25 — but it is
**unverified**, and the whole estimate hangs on it. Sensitivity: 1.5× dedup →
150k chunks → 11 overnights; 2.0× → 112k → 8.4; 2.5× → 90k → 6.7.
**Cheap fix: measure the dedup ratio on one sector's extraction output before
committing to the F4 schedule.**

**(b) E2's power gain is partly cancelled by a labeler downgrade that the MDE
never accounted for.** The MDE bracket 0.019–0.037 was computed on E1's
noise structure — i.e. under **Claude's** label quality. E2's labels come from
the student, whose sentiment agreement with the teacher is **83.5%** with
**NEGATIVE recall 0.487**. Chunk-level noise partly averages out at the
filing-feature level, but a *systematic* under-detection of NEGATIVE does not
average out — it **compresses the dynamic range of the single feature most
likely to carry signal**. Net effect: E2 has more statistical power against a
**more attenuated measured effect**, and **nobody has computed the net.**
This should be quantified before G3, not discovered at G4. A cheap version:
re-run E1's backtest on E1's 6,746 chunks **re-labeled by the student**, and
compare the feature distributions and the IC delta to the Claude-labeled run.
That is one 5-hour overnight (the eval report's own E1-relabel line) and it
directly measures the attenuation.

**(c) F3 is the token elephant, and its cost profile is manual.** The F2
report's own testimony: three whole error classes, "each found by a human read
or a screen built after one, never by the confidence label," and a residue
where "37 of 57 [worklist CIKs] are uncovered," "the 26 medium-confidence
picks are on no worklist," and "every filer below the watch-list bar is
unmeasured for these classes, not clean." F3 runs `extract.py` — calibrated on
25 mega-caps' 2023–2026 filings — across 244 filers (MLPs, REITs, utilities, a
gold trust) and 11 years including pre-iXBRL 2015–2019 HTML. Expect the same
pattern: automated confidence will under-report, and the real cost will be
human/agent reads. **Budget F3 as ≥ F2, and F2 needed a resume ledger.**

---

## 5. The charter / "product" tension — this is a finding, not a premise

`HANDOFF.md` §1 is unambiguous: *"a solo-owner research and screening tool,
not a product with users."* The commissioning language is: *"making a product
that is not really useful, outdated and just a waste of code and tokens."*

**These describe two different projects, and the direction choice depends
entirely on which one is real.**

- **If FinScreen is a personal research instrument**, then a well-measured
  null is a *success*, the effort is not wasted, and the only genuine waste
  would be abandoning the question at 80% completion. **D1 is correct** and
  the anxiety is misplaced.
- **If the owner wants a thing that exists in the world and is useful**, then
  **D1 is the worst option on this list** — its most likely output is a private
  negative result on a settled question, at 5–9 weeks and a large token cost,
  with near-zero external value.

The anxiety in the commissioning language is *product* anxiety applied to a
*research* charter. That mismatch, not the E2 design, is the thing to resolve
first — and the good news is that resolving it does not require choosing.
**D3, D4, D5c and D5e all convert the same asset base into something with
external value without violating a single non-goal**, because none of them
makes a performance claim, recommends a trade, or touches capital. The charter
does not forbid usefulness; it forbids advice and execution.

**On "outdated," directly and specifically:**

- **Outdated:** the *feature design*. Tone counts, flag rates, and section-mix
  shares are the 2011–2015 generation of finance NLP. The modern versions —
  change-based features (D2c), embedding distances, passage-level retrieval
  (D5c) — come from the same corpus at low marginal cost.
- **Outdated:** the *chunk → label → aggregate* architecture is
  pre-long-context. In 2026 a long-context model reads a whole 10-K without
  chunking, and structured extraction at this quality is closer to a commodity.
- **Not outdated, and should be claimed rather than apologized for:** a
  **frozen, local, $0, reproducible** labeler is a *better research
  instrument* than an API model that silently changes underneath you. Every
  number in this project can be re-derived in five years. That is a feature.
- **Not outdated at all:** the PIT membership discipline, the survivorship-safe
  selection, filing-date alignment, the form-controlled ablation, the
  censoring census. This is the part most people skip, and it does not decay.

---

## 6. Ranked recommendation for a solo owner on Max who loves the idea

Ordered by (value × probability) ÷ cost. This is a *sequence*, not a menu —
each step is cheap and each one informs the next.

1. **T1 + T2 positive controls (D5a). 3–5 days. No new ingestion, no F3, no
   F4.** Uses only what is on disk. Either the harness recovers a known
   contemporaneous relationship and E2 becomes worth its cost, or it doesn't
   and the owner just saved 5–9 weeks. **Do this before anything else.**
2. **The E1-relabel attenuation check (§4b). One ~5-hour overnight.** Re-label
   E1's 6,746 chunks with the student, re-run E1's backtest, and measure how
   much the labeler downgrade moves the features and the IC. This retires the
   largest unexamined threat to E2's headline power claim, and it is already
   scoped in the eval report's own throughput table.
3. **Reframe to D4 while those run. 3–5 days.** Rewrite README/MODEL_CARD so
   the pipeline is the asset and the backtest is one application. Costs
   almost nothing, is more accurate than the current framing, and makes every
   later decision easier.
4. **Then F3 — but scope-cut (D5d): core stratum first, extension deferred to
   post-G2.** Consistent with the ratified analysis rule; saves ~28% of the
   F3/F4 cost; changes no pre-registration.
5. **At F5, run three heads, not one:** the pre-registered return target (D1),
   the **volatility/informativeness event study (D5b)** on 5,552 events, and
   the **exit-prediction target (D2a)** on 86 exit CIKs. The expensive work
   (F3/F4) is already paid for; a second and third head is ~1 week each and
   two of the three test hypotheses the literature says are *true*.
6. **Ship the write-up (D3/D5e) whatever the result.** The infrastructure and
   failure-taxonomy piece is the highest-external-value artifact this project
   can produce, it is publishable today, and the E2 null — bounded at MDE
   0.02 — is a strong epilogue rather than a weak thesis.
7. **Keep D5c (screening-as-retrieval) as the standing deliverable.** It is
   the only version of FinScreen whose usefulness is not conditional on a
   statistical result, and it is the one the charter's own word — *screening* —
   actually describes.

**What I would drop or defer:** D2b (guidance prediction) until the guidance
head is fixed and re-measured; the extension stratum's labeling until G2; and
any framing in which the quarterly cross-sectional return backtest is the
project's headline deliverable.

**The one-sentence version:** the backtest was always the least valuable thing
this project would produce, the infrastructure and the methods trail were
always the most valuable, and the cheapest correct move is to stop treating
the null as the verdict on the project and start treating the corpus as the
product.

---

## 7. Confidence

**High confidence (re-derived from artifacts this session):** every number in
§1; the E1 numeric-only baseline of +0.0972; the 5,552 usable earnings events;
the 86/244 exit-CIK base; the 236M-word / 225k-chunk projection and its dedup
sensitivity; the absence of any literature reference in the repo; the
guidance-head weakness (n=7/7/3 support, NONE recall 0.586).

**Moderate confidence:** the F4 overnight band (depends on an unmeasured dedup
ratio); that F3 will cost ≥ F2 (extrapolation from the F2 report's own failure
pattern, not a measurement); the label-noise attenuation magnitude (the
*direction* is certain, the size is not — which is why §4b proposes measuring
it rather than asserting it).

**Recalled, not verified in this pass:** all literature in §2. Directions and
existence are high-confidence; exact magnitudes, years, and journal placements
should be re-checked before anything is published on their basis. My knowledge
cutoff means the 2025–2026 LLM-on-filings literature and product landscape are
likely under-represented here — if anything, that biases §2 toward
*understating* how crowded the space now is.

**Speculation, flagged as such:** that the infrastructure/failure-taxonomy
write-up would find an audience. I believe it strongly on the merits — content
of that specificity is rare — but I have no evidence about demand.

**What this lens did not assess:** whether E2's statistical design is
*correct* (Lens 2/3's job); whether the pipeline code is sound; whether the
owner has the appetite for 5–9 more weeks. I priced the options; I did not
audit the plan.
