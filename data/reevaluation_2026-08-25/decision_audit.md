# LENS 3 — DECISION AUDIT

**Written 2026-08-25.** Commissioned by the owner as one of four lenses in a
brutally honest re-evaluation. Scope: every owner ratification in
`HANDOFF.md` §3 (2026-08-10 → 2026-08-25) and every main-session build
ruling in `F2_PROGRESS.md` §5, graded **SOUND / DEFENSIBLE-BUT-DEBATABLE /
SHOULD-REVISIT**; then the three most consequential decisions still ahead;
then the decisions nobody has flagged.

**Method.** Read-only. Every doc in the assigned read order was read. Where
a claim could be checked against artifacts on disk, it was checked — nine
independent measurements were run over `data/*.parquet`,
`data/raw/companyfacts/`, `data/raw/filing_index/` and `data/f2/*.csv`.
Those measurements are marked **[MEASURED TODAY]** and each states its
method. Nothing was edited; no network call was made.

**Bottom line up front.** The decision record is unusually good. Almost
every ratification was made after a measurement rather than before one, the
provenance discipline (model verdicts never recorded as the owner's) held
through 1,222 judgments and ~15 build rulings, and the two decisions that
mattered most — spot-checking the labels, and diagnosing E1's null instead
of believing it — are the reason this project knows anything true about
itself. Three things are wrong, and all three are wrong in the same
direction: **the project keeps buying statistical power while its
measurement instrument gets quietly worse, and no decision has ever been
made about that trade.** Everything below is in service of that sentence.

---

## PART 1 — HANDOFF §3 owner ratifications, graded

### 1.1 — 2026-08-10 · Rubric v1.1: `section_type` never appears as prompt text; applicability enforced via JSON schema shape
**SOUND.** This closed a real confound before it could form: had the section
type been named in the prompt, every "text signal" measured downstream would
have been partly a signal about SEC form type — precisely the confound that
later showed up anyway as `backtest.py` MAJOR #4 (`share_chunks_*` are
near-perfect form proxies). Deciding it stricter than v1 on day one was
cheap then and unaffordable later.
**Consequence, now measured:** it forced the model to infer applicability
from register alone, which is the direct cause of the student's
`__MISSING_FIELD__` behaviour (guidance field-presence agreement 76.75%,
226 `NONE→__MISSING_FIELD__` errors). That is a cost of a correct decision,
not evidence against it.

### 1.2 — 2026-08-10 · Sync rule: `labeling_rubric.md` is authoritative; `SYSTEM_PROMPT` is hand-synced
**DEFENSIBLE-BUT-DEBATABLE.** The rule is right and was honoured. It is now
partly obsolete in a way nobody has recorded: **the labeling spec of record
for E2 is no longer a document — it is a set of LoRA weights.** The student
encodes rubric v1.1 *as the teacher applied it*, including the ~36.6%
exact-set red-flag error the owner personally ruled incorrect. No sync rule
governs that artifact. If rubric v1.2 is ever ratified, the sync rule will
faithfully update two files that no longer control what gets labeled.
**Fix (cheap, F4-scoped):** extend the sync rule with one clause — any
rubric change requires either a retrain or an explicit written statement
that the deployed labeler does *not* implement the change.

### 1.3 — 2026-08-11 · Label-to-filing attribution: a label attaches to every filing its paragraph occurs in
**SOUND.** Justified by a measured coverage gap (17% of filing-sections, and
46.5% of Risk Factors sections, have no home chunks of their own), and PIT
safety is preserved because every occurrence carries its own filing date.
**[MEASURED TODAY]** — I checked the risk this rule could have created:
smearing a label across companies. Over all 28,504 canonical paragraphs in
`data/paragraph_occurrence_map.parquet`, **exactly 1 paragraph occurs under
more than one ticker.** Attribution is therefore ~100% within-company. The
rule does what it claimed and creates no cross-company leakage channel.

### 1.4 — 2026-08-11 · Spot-check = blind second rater + concentrated human triage
**SOUND — the single highest-yield decision in the project.** It is the only
reason anyone knows `red_flags` fails its own 0.70 bar, that REALIZED
LIQUIDITY_STRESS is empty corpus-wide, and that the labels are the weak
link. Concentrating owner judgment where it is most informative rather than
spreading it evenly was the right economy, and the epistemic clause ("model
agreement is not human validation") was written into the ratification
itself rather than bolted on afterwards.
**One residual, carried to G2 below:** the only base-rate-representative
slice is Tier C, n=36, 95% CI [58.9, 86.2]. A 27-point-wide interval is the
project's corpus-wide label-quality estimate.

### 1.5 — 2026-08-11 · Backtest before fine-tune
**SOUND, and vindicated.** E1 produced a diagnosed null. Had the order been
reversed, ~15–39 h of the owner's machine would have been spent producing a
labeler for an experiment that then failed. The fine-tune happened anyway,
but as E2's *enabler* under a new and explicit ratification — a
repurposing, not a contradiction of this rule.

### 1.6 — 2026-08-11 · Fine-tune method: local MLX 4-bit QLoRA at $0; GPU rental not pre-approved
**SOUND.** Delivered exactly what it promised: two epochs, 0.00% parse and
schema failure, 1,337 chunks/h measured. The "very minimal GPU budget as a
non-pre-approved fallback" wording is a good pattern — it names a fallback
without authorising it.

### 1.7 — 2026-08-18 · Adjudication delegation (third-rater model + owner shortlist)
**DEFENSIBLE-BUT-DEBATABLE.** The mechanism was well built and the
provenance is exemplary (1,222 judgments: 1,023 model-auditor / 95
model-adjudicator / 104 owner, none imputed). The debatable part is what the
output became: a **model-consensus** number is now the load-bearing quality
constant of the entire project. It is quoted in `features.py`,
`diagnose.py`, the eval report, `RED_FLAGS_LIMITATION.md` and the model
card, and it will set the reference point for G2's bar on the Qwen labels.
The verdict "red_flags fails the bar" is robust on every basis. The
*magnitude* carried forward is not: 36.6% (sample-pooled), 25.0% (Tier C,
n=36), 7.5% (per-category) are three different numbers for "how wrong are
these labels," and the one that is base-rate-representative is the one with
n=36.
**Better alternative, and it is naturally scheduled:** G2 re-measures label
quality on the student's labels anyway. Size G2's base-rate stratum so it
alone yields a usable CI (n≈150 gives roughly ±7 points instead of ±14).
**Switching cost now:** zero — it is a design parameter of a gate that has
not been designed yet. **At the next natural gate:** if G2 reuses E1's
400/36 shape, the project inherits a second 27-point-wide interval and the
extension-stratum promotion decision rests on a handful of rows per sector.

### 1.8 — 2026-08-18 · Step 4 go/no-go: "GO, diagnosis-scoped"
**SOUND.** Faced with a result whose raw and deduplicated IC deltas
disagreed in sign, the owner chose neither "it worked" nor "abandon" but
"find out why" — and scoped it explicitly away from depth-for-its-own-sake.
The diagnosis then produced the correct and useful verdict: the design's MDE
(0.077) was larger than any effect ever observed in the data, so the null
was near-inevitable and uninformative. That is exactly what a diagnosis is
for.

### 1.9 — 2026-08-18 · Bulk ratification of adjudications; `labels.parquet` stays frozen
**DEFENSIBLE-BUT-DEBATABLE.** Freezing the corpus while recording
corrections separately is defensible for audit integrity, and a re-label was
blocked by the spend freeze regardless. The consequence, which is real and
under-stated: **the fine-tune's training targets include the 146 chunk
label-sets and the 9 REALIZED-liquidity labels the owner personally ruled
incorrect.** The corrections were on disk in
`spotcheck/combined_judgments.csv` and were free to apply to the training
split before `split.py` ran. Nobody did.
**Honest calibration:** the yield would have been small — ~400 of 5,736
training rows, most of them in the eval split anyway. This is a missed
tidy-up, not a design error. It is graded DEBATABLE rather than
SHOULD-REVISIT because the fix is now expensive (retrain) and the gain is
small. The larger version of this issue is §1.10.

### 1.10 — 2026-08-18 (standing) · Spend freeze: "no further Anthropic API spend, period"
**SHOULD-REVISIT — and this is the decision with the steepest cost of
delay in the project.**

The freeze was set at $33.51 when $16.49 of the original $50 ceiling
remained. As a discipline device it has worked perfectly: $0 spent since,
and it forced the local-MLX path that turned out to be the right
architecture. That is genuine.

What has changed is *what it now binds on*. In August it bound on a nice-to-
have re-label. Today it binds on the single highest-leverage input in the
entire pipeline: the bootstrap labels are the training targets for the
labeler that will label an estimated 120k–220k E2 chunks (§3.3), and no
amount of additional statistical power fixes label noise.

**[MEASURED TODAY]** — the price of the thing the freeze forbids, from the
project's own spend table: the re-label of 4,219 rows cost $10.06, i.e.
**$2.38 per 1,000 rows**. A full-corpus re-label of all 6,747 rows under
rubric v1.2 costs **≈ $16.09** — inside the original, superseded ceiling.
The v1.2 revision that would be applied is already drafted, and its three
principles (P1 realized-controls-modality, P2 liquidity threshold, P3
boilerplate mining depth) are **already owner-ratified**; they directly
target the measured error modes (43 modality corrections, 26 of them
LEGAL_REGULATORY_ACTION; 61 spurious flags; 76 missed flags).

**The honest counter-arguments, stated in full:**
1. A v1.2 re-label is **unproven** to improve agreement. It would need its
   own spot-check to know, and that spot-check would itself be model-based.
2. It would break the frozen-corpus comparison that the entire E1 audit
   trail rests on. E1's numbers would no longer be reproducible from the
   current artifact.
3. The freeze is not only a budget — it is the rule that produced this
   project's best engineering. Re-opening it re-opens a decision the owner
   deliberately made irreversible.
4. It would require a retrain (≈2 overnights) and a re-eval before F4.

**Switching cost NOW:** ≈$16 + ~2 nights of retrain + a fresh spot-check
(agent time, $0) + a re-freeze. **Switching cost at the next natural gate:**
once F4 labels 120k+ chunks, changing the labeler means discarding and
redoing the entire labeling campaign — 9 to 17 overnights of the owner's
machine. **The cost of revisiting this rises by roughly an order of
magnitude the day F4 starts.**

I am not recommending the spend — that is the owner's call and the charter
is the owner's. I am recording that **the freeze has never been priced
against what it now buys, and it is about to become much more expensive to
revisit.** A deliberate "no, and here is why, knowing it costs $16 and the
labeler is the bottleneck" is a fine outcome. Drifting past the decision
because it was settled in a different context is not.

### 1.11 — 2026-08-18 · Backtest target: forward excess return vs universe average, filing-date aligned; authorises one free daily-price provider
**DEFENSIBLE-BUT-DEBATABLE**, with one **SHOULD-REVISIT** sub-item.

The target itself is right for a screening study — cross-sectional, filing-
date-aligned, no absolute-return claim, chosen explicitly over a
fundamentals-derived target. Its self-referential benchmark (each company's
excess return measured against an average that includes itself) is a known
flaw already queued for G3 with the correct fix (equal-weighted,
exclude-self, membership-dated).

**SHOULD-REVISIT — the provider substitution.** The ratification named a
"Stooq-class CSV download" by example. Stooq was bot-gated the same day.
The de-facto standing source is now Yahoo Finance's keyless chart endpoint,
whose robots.txt disallows automated access and which publishes no terms
for this use. F2 scaled that exposure ~5× (25 tickers → 213). Every layer of
this project has ratified provenance obsessively; this is the one input
where the *actual* source has never been ratified, only inherited from a
fallback taken under time pressure.
**Better alternative:** a one-line explicit ratification (or refusal) of
Yahoo-at-E2-scale as the standing source, recorded in §3 like everything
else — the schema is already source-agnostic, so a later swap costs only a
re-ingest. **Cost now:** one owner sentence. **Cost later:** the exposure is
baked into every E2 result and into whatever F6 publishes.

### 1.12 — 2026-08-20 · Diagnosis read + "I want to do a bigger experiment"
**SOUND.** The diagnosis said the design could not have detected any
plausible effect (MDE 0.077 vs a largest-observed family delta of +0.0345).
"More power" is the logically correct response to *that specific* diagnosis,
and the recommendation against fine-tuning absent a bigger experiment was
made and honoured.

### 1.13 — 2026-08-20 · E2 scope: 100 companies × 10 years
**SOUND.** The recon's power table is honest — it says out loud that
company-only expansion (100×6 folds, MDE 0.039–0.077) "may buy nothing" if a
regime-variance floor dominates, because a floor divides only by folds. The
ratified config is the only one whose *pessimistic* endpoint (0.037) reaches
the best alternative's optimistic one. Expanding both axes was the right
call for the right stated reason.
**[MEASURED TODAY]** — the power model assumed `per_fold_n_independent =
n_companies = 100`. F2 then measured that price censoring is **not flat in
time**: 14.0% / 16.2% / 12.5% of member-date cells in the 2016 / 2017 / 2018
cohorts have no usable prices, decaying to 0% by 2026 (6.35% pooled over
1,496 cells). Early folds will therefore run on ~84–88 names, not 100, and
the loss is outcome-correlated (acquisitions and take-privates, not random
gaps). The MDE bracket has never been re-derived against measured coverage.
That is a G3 preparation item, not a fault in the original ratification.
**[MEASURED TODAY]** — one design property worth stating plainly because it
is *good*: `hybrid136_panel.parquet` contains exactly **100 core members at
every one of the 11 reconstitution dates** (and 36 extension). The hybrid
amendment did not dilute the ratified power design; the primary confirmatory
stratum is exactly the 100-company universe that was costed.

### 1.14 — 2026-08-20 · Universe rule: sector-stratified top-K by `EntityPublicFloat`, annual PIT reconstitution
**SOUND on selection; SHOULD-REVISIT the claim wording.** The rule
explicitly rejects the tempting look-ahead ("continuous filing across the
window") and makes membership at each date depend only on pre-date filings.
That is real survivorship-free selection and it is the most technically
impressive thing in the E2 design.

The flaw surfaced at F2 and is correctly characterised there as a property
of the ratified rule, not a build error: sector is assigned **once, from the
current SIC**, and quotas are fixed per sector, so which bucket a company
competes in at 2016-07-01 — and therefore whether it makes that date's top-K
at all — is decided by its 2026 SIC.

**[MEASURED TODAY] — and here `F2_INGESTION_REPORT.md` §9 item 12 is
factually wrong.** It says "The magnitude is unmeasured — the artifacts
carry only the current SIC, so nobody can say how many members reclassified
during the window; that unmeasurability is itself part of the limitation."
The historical SIC is already on disk. Every one of the **10,875 cached
filing-index pages** in `data/raw/filing_index/` carries the filer's SIC
**as submitted with that filing**. Parsing them (0 network GETs, ~40
seconds) gives:

- **10 of 243 members (4.1%) changed SIC during the window**, and the
  changes are cleanly time-ordered (Equinix 4813→6798 in Oct 2015; SBA
  Communications 4899→6798 in Feb 2017; Uber 7372→7389 in Nov 2019).
- **At least 4 of those cross a sector bucket** under this project's own
  map: Equinix and SBA Communications move telecom/utilities →
  `materials_realestate` (both are REIT conversions); Uber and Fiserv move
  tech-coded SICs → the SIC now mapped to `financials`; Booking Holdings
  moves 4700 (industrials) ↔ 7389.
- This is a **lower bound**: only earnings-8-K index pages are cached
  (10,569 of 45,545 filings) and GLD has none, so 243 of 244 members are
  covered and intra-window changes on non-earnings filings are invisible.

So the limitation is measurable, its magnitude is small (≈1.6% of CIKs cross
a bucket), and it is concentrated in exactly the two smallest quotas (K=12
extension buckets). **Switching cost now:** one measurement pass, $0, plus a
corrected sentence in the report — the limitation goes from "unquantifiable"
to "quantified and small," which is strictly better for the eventual write-
up. **Cost at G4:** the report ships a limitation stated as unmeasurable
when the data to measure it was sitting in the cache the whole time; that is
the kind of claim a red-team catches, and it undercuts the credibility of
the twelve genuinely-honest limitations next to it.

### 1.15 — 2026-08-21 · E2 universe amended to hybrid136 ("do both")
**DEFENSIBLE-BUT-DEBATABLE.** The engineering response to a vague owner
preference was excellent: core stratum = continuity5 exactly (so the
labeler stays in-distribution and the ratified power design is untouched),
extension = 3 new sectors at K=12, every row stratum-tagged, primary
confirmatory analysis bound to core, extension promoted only on a G2
sector-stratified quality check. That is how to say yes to "do both" without
contaminating a confirmatory test.

The debatable part is cost/benefit. The extension buys ~36% more labeling
(now, per §3.3, likely 3–6 extra overnights) for an arm that is (a)
secondary by construction, (b) out of the labeler's training distribution,
(c) conditional on a gate that has not been designed, and (d) not part of
any pre-registered hypothesis. If G2 fails on the unseen sectors, that
compute is spent and the arm is reported as "not promoted." The owner asked
for economic breadth and got it honestly — but the extension is the first
thing to cut if F4's real scale (§3.3) turns out to be at the top of the
bracket.

### 1.16 — 2026-08-21 · Gate G1 ruled: conditional acceptance of the student, epoch 2 first
**SOUND as a ruling, and the conditionality was exactly right.** Epoch 1
showed sentiment 81.7% with NEGATIVE recall 0.425 — refusing to accept on
that and asking for a second epoch was correct.
**The condition has now come due and it is not obviously satisfied.** See
§2.1 and §3.2; the epoch-2 numbers are in and the owner has not ruled.

### 1.17 — 2026-08-20 · Fine-tune LAUNCH ratified ("Yes — launch, 1 epoch first")
**SOUND.** The bound discipline (implement → timed probe → smoke → one epoch
→ held-out eval → owner review before more epochs) is textbook, and it
survived three SIGTERMs by converting the incident into a standing rule
(auto-resume chain, checkpoint every ~10 min of work) rather than a
workaround. That rule then pre-emptively protected F2's ingestion runs and
is already binding on F4. This is the best incident-to-rule conversion in
the log.

### 1.18 — 2026-08-25 (a) · GLD retained as a core financials member
**DEFENSIBLE-BUT-DEBATABLE.** It is the owner's territory, it was ruled
explicitly and documented as an accepted anomaly — process-perfect. The
substantive consequence is now quantified.
**[MEASURED TODAY]** — GLD holds **2 of 1,100 core member-date seats**
(rank 20 at 2017-07-01, rank 18 at 2023-07-01, i.e. it displaces the 21st
financial at those two dates only). It filed **zero item-2.02 earnings
8-Ks**, so it contributes essentially **no text chunks**; 7 of its 14
fundamentals families resolve ABSENT. Its price series is bullion, not
equity.
So GLD enters E2 as (i) a non-equity return inside the equal-weighted
benchmark at 2 of 11 dates, and (ii) a row whose text features are
structurally empty — a row on which the text model and the numeric model are
identical by construction, mildly diluting the measured delta. At 2/1,100
seats that is negligible, but it is not zero and it is not automatic:
**F5/G3 must decide explicitly whether GLD rows enter the benchmark average
and the IC computation.** The ruling itself anticipated this ("any
analysis-side sensitivity treatment is a G3/F5 question"), so the ruling is
complete; the follow-through is a G3 checklist item.

### 1.19 — 2026-08-25 (d) · "Convert to USD as standard in future for all companies in case not USD"
**SOUND as a principle. The implementation must be tiny, and the F2 report's
framing of the open question is answerable today.**

Converting non-USD fundamentals before forming price ratios is
unambiguously correct — an unconverted P/E for Enbridge is wrong by the
exchange rate. Deferring FX source and PIT semantics to F5/G3 is the right
sequencing, and choosing Yahoo FX pairs keeps the zero-new-provider
property.

**[MEASURED TODAY] — the open owner-read question (§0d) has a definite
answer.** The report asks whether Enbridge's *core placement* rests on an
unconverted CAD float. Scanning `dei:EntityPublicFloat` across all 244
cached companyfacts files: **4,672 float facts are denominated USD and
exactly 1 is CAD** — Enbridge, instant 2022-06-30, CAD 85.6B, filed
2023-02-10, which is the value used at the **2023-07-01** reconstitution
date only. Enbridge's other 15 float facts are USD (2023-06-30 → USD 75.1B,
2024-06-30 → 77.5B, 2025-06-30 → 98.8B). Converting the single CAD figure at
the mid-2022 rate (~0.78) gives ≈ USD 66–67B, which would rank it **4th or
5th** in energy core against EOG's 64.6B — **inside K=20 either way.**
**Membership impact: none.** The question can be closed rather than carried.

**Lazy-elite warning attached to the ruling:** the phrase "all companies in
case not USD" invites a general multi-currency framework. The measured
population is **one company and thirteen series**. The correct build is a
handful of lines converting Enbridge's fundamentals at the PIT-correct rate
plus a loud FATAL if a second non-USD reporter ever appears — not an FX
subsystem.

### 1.20 — Standing policy · Model tiering (Fable = plan/orchestrate/verify; Opus = execute; Sonnet = simplest)
**DEFENSIBLE-BUT-DEBATABLE in effect.** Throughput-wise it plainly worked:
F2 went from kickoff to a red-teamed 45,545-filing corpus with an 815-test
green suite in about a day.

The observable side-effect is a role collision. `F2_PROGRESS.md` §5 contains
~15 main-session rulings, several of which are domain-technical judgments —
a 75% dominance threshold, a filed-span denominator, an exemption ledger,
`us-gaap:Cash` at lowest preference. The mitigation that makes them
acceptable is real: **every one of them was measured before it was ruled.**
The residual risk is that the same session decides, executes-by-proxy, and
verifies. The clearest instance: the S7 red-team's own findings triggered
three fix cycles (B1's 15 cover pages, Pioneer, PSEG's 45/45 decks) that the
red-team never saw. The report discloses this honestly and defers to F6 —
but it means **the corpus as it stands on disk has never been adversarially
reviewed in its final form.**
**Better alternative, cheap:** for any ruling that changes a measured
number, require an independent re-derivation by a different agent before the
ruling closes. That is what S7 Section A did and it worked. **Cost now:** one
extra agent call per ruling. **Cost later:** F6 finds it, after F3–F5 have
been built on top.

### 1.21 — Standing policy · Lazy-elite engineering
**SOUND as a policy, with one identified failure mode.** It produced the
project's best calls: the co-registrant side-table instead of re-keying
`filings` for 0.19% of rows; refusing a blanket bare-EX-99 preference flip
in favour of a measured per-filer handler; refusing to reproduce E1's SLB
"migration" hand-map because it papered over a real concept change.

The failure mode: the policy distinguishes "minimal work to be correct" but
not "minimal work to be **measured** as correct." Throughout the EX-99 saga,
the lazy-elite reading ("patch this filer, don't build a general screen")
repeatedly won over "measure the class" — and the class kept being larger
than the patch. **Suggested one-line amendment: measuring an error rate is
never over-engineering.**

---

## PART 2 — `F2_PROGRESS.md` §5 build rulings, graded

These are main-session build rulings, correctly not presented as owner
decisions. Graded for engineering judgment.

| # | Ruling (dated 2026-08-24 unless noted) | Grade | One-line reasoning |
|---|---|---|---|
| 1 | Full-window ingestion, no spell clipping; floor 2015-07-01, end 2026-08-31 | **SOUND** | Measured cost (+5.0% filings), and clipping would have silently lost the corpus's only bankruptcy (CIK 895126, both item-1.03 filings outside its own spell). |
| 2 | Shared-window enumeration vs per-company windows (spec self-contradiction) | **SOUND** | Resolved by measurement — only the shared window reproduces every plan-of-record count — and validation still uses per-company windows. Enumeration ≠ validation is the right separation. |
| 3 | `hybrid136` read in place under a new checksum file; universe pin `== 244`; new `filings_metadata_e2.db` (E1 DB frozen) | **SOUND** | Tripwire re-pinned rather than deleted; E1's record untouched. |
| 4 | `--allow-incomplete-universe` deleted in favour of evidenced per-(cik, check) exceptions | **SOUND** | Replaced a blanket override with an evidenced exception path — and then measured that the exceptions file ships **empty** (0 FATAL / 5 WARN / 29 INFO). Best structural fix in F2. |
| 5 | "Substitutes-only families + explicit dominance" amendment | **SOUND** | The first pass measured 86/250 UNRESOLVED on E1's *own* 25 companies with MIGRATION never firing — correctly diagnosed as a spec defect rather than a data problem. Deliberately not reproducing SLB's hand-map is the right instinct. |
| 6 | Co-registrant side-table instead of re-keying `filings` (87 of 45,632 = 0.19%) | **SOUND** | Textbook lazy-elite. Later strengthened by the measurement that none of the 87 is an earnings 8-K, so the text corpus is unaffected. |
| 7 | `us-gaap:Cash` at lowest preference; `BLOCKER_EXEMPT_CELLS` | **SOUND** | Both apply the crying-wolf lesson explicitly: a provenance-tracked series beats a manufactured gap, and an alarm carrying 10 structurally-expected cells trains people to ignore the real ones. Exemptions print whether or not they fire. |
| 8 | 244-scale classifier calibration (filed-span denominator, MLP tag broadening, 2 exemption additions, 8 OVERLAPs left firing) | **SOUND** | Read from a real run, not predicted; the unfixed cases stay loud and individually listed rather than being papered over. |
| 9 | Price rulings: XOM + AEP evidenced overrides, EIDP deliberately not overridden, Dow Chemical censored, EA `resolved_no_coverage` | **SOUND** | Each evidenced, each two-sided-pinned (a second EA FATALs *and* EA regaining history FATALs). Declining the EIDP override — a preferred-only listing would have pulled a preferred series into an equity backtest — is the best judgment call in F2. |
| 10 | The EX-99 fix arc: P1–P6 screens, Prologis/PSEG per-filer handlers, 4-row override file, Pioneer exclusion | **SHOULD-REVISIT (as a class, not per fix)** | See below. |
| 11 | S7 red-team triage B1–B21 | **SOUND, with a disclosed hole** | Foundations survived full independent re-derivation (3,416/3,416 resolutions, enumeration to the accession). The hole is disclosed: the red-team predates the fix cycles its own findings triggered. |
| 12 | S2 implementation clarifications (exclusive `member_to`, filed-span denominator, gap WARN count, inert 135-day threshold) | **SOUND** | "The artifact wins over the prose" is the right tie-break, and each clarification was measured (e.g. the 135-day threshold is *inert* — same 29 members fire at any threshold from 135 to 250). |

### 2.1 — Why the EX-99 arc is SHOULD-REVISIT
Every individual fix is correct and evidenced. The *class* was never
decided. The report's own §9 item 9 is the indictment, and it is admirably
honest: three high-confidence error classes (Prologis 42/45, B1's 15 cover
pages, PSEG 45/45), and **"each was found by a human read or a screen built
after one, never by the confidence label."** Residue as shipped: 51 of 71
flagged CIKs never manually read; 37 of the final 57-name worklist
uncovered; the 26 medium-confidence picks on no worklist; PSEG never on the
worklist at all; and the P6 watch-list share explicitly "a floor, not an
estimate."

**[MEASURED TODAY]** from `data/f2/ex99_selection_audit.csv`: 10,312 filings
sit under `EX99_PRESS_RELEASE / high` across 243 CIK-rows, plus **210
filings stored as `8K_BODY` at high confidence** across 55 CIK-rows. The
release-language-missing share has a mean of 3.7% but a max of 53.2%
(Netflix, reported-benign) with PNC (91 filings), AbbVie (65), Tesla (93)
and Occidental (58) between 20% and 40%. Those are *screens*, not
measurements of correctness.

**The decision that was never made: what earnings-document selection error
rate is acceptable, and how is it estimated rather than sampled?** This
project already invented the right protocol for exactly this problem — Tier
C, a base-rate-representative random draw with a Wilson CI. It applied it to
labels and never applied it to document selection, even though the selected
document *is the entire text corpus*.

**Concrete better alternative:** a random (not worst-of) sample of ~60–100
selections, stratified by filer shape and era, read by `extraction-qa-
engineer`, reported as a corpus-wide selection-accuracy rate with a CI.
**Switching cost NOW:** one agent pass, $0, roughly half a day, and it is the
natural companion to F3's own manual spot-read. **Switching cost at the next
natural gate:** after F3 extracts and F4 labels, a selection error is baked
into 120k+ chunks; correcting it means re-extracting and re-labeling — 9 to
17 overnights. **F3 start is the hard deadline.**

---

## PART 3 — The three most consequential decisions still AHEAD

Ranked by irreversibility × blast radius. Gate G1 is listed inside #2
because it is genuinely pending and is the precondition for G2.

### 3.1 — #1: G3 pre-registration (benchmark, folds, metric — and four things not yet on the list)
**Why it is first.** It is the only decision in the project that is
*definitionally* worthless if made late. A pre-registration made after
anyone has seen an E2 IC is not a pre-registration, and G3 governs the
number the whole project exists to produce.

**Failure mode of deciding it lazily.** Ratify the three named items
(exclude-self benchmark, fold structure, dedup IC delta as primary) and stop
there. Then:
- The **post-close acceptance convention** is discovered later: 20,715 of
  45,545 filings (**45%**) are accepted 16:00–17:00 ET while carrying that
  day's `filing_date`. Dating a feature to `filing_date` and starting the
  return window the same day is a **one-day look-ahead on nearly half the
  corpus**. Found after the backtest runs, the only honest fix is to re-run
  — and the fold structure has now been seen.
- The **restatement as-of rule** goes unstated: 20,027 of 273,268 (cik,
  concept, unit, period) groups (7.3%) carry more than one filed value. A
  naive latest-value join is look-ahead on 7.3% of period-cells.
- The **two Salesforce anomalies** (filing_date preceding acceptance by 344
  and 633 days) have no general rule.
- **FX PIT semantics** for the USD-conversion ruling are improvised at
  implementation time — spot-at-fetch is look-ahead.
- **The MDE is never re-derived** against F2's measured coverage (early
  folds at ~85 names, not 100).
- **Worst: the null's interpretation is never pre-registered.** See §4.1.

**Preparation that makes it good.** One G3 document, written before any E2
IC exists, that lists every convention with its **measured population** next
to it (45%, 7.3%, 2 filings, 1 company, 6.35% pooled censoring), states the
chosen rule for each, re-derives the MDE bracket against measured coverage,
and — the load-bearing clause — states in advance **what a null does and
does not bound**, given a labeler whose measured error is roughly double the
teacher's (§3.2). Every input for this already exists in
`F2_INGESTION_REPORT.md` §3.3 and §9; it needs assembling, not researching.

### 3.2 — #2: G1 acceptance of the student, and G2's label-quality bar
**Why it is second.** The labeler is the measuring instrument. Every E2
number is a measurement made through it, and it cannot be replaced after F4
without redoing the campaign.

**The pending fact nobody has ruled on.** `EXPANSION_PLAN.md` §4 proposed
the G1 floor as "sentiment and guidance ≥ ~0.90 exact-match on eval;
red-flags reported against the teacher's own noise level." The epoch-2
result: **red_flags clears its stated test** (exact-set 64.87% vs teacher
reproducibility 63.4%; per-category 92.42% vs 92.5%) and **guidance clears
it under the post-rule** (98.4% derived, patch queued). **Sentiment does
not: 83.5%, about 6.5 points below the proposed floor and ~11 points below
the teacher.** And the shape of the miss matters more than the level:
**NEGATIVE recall is 0.487** — the student misses more than half the
negative sentiment the teacher found. Recall is similarly soft on
`DEMAND_WEAKNESS` (0.604) and `MARGIN_COST_PRESSURE` (0.669).

**Compounded label error, computed here because nobody has computed it.**
Agreement with the teacher is not accuracy; the teacher's own adjudicated
error must be composed with the student's disagreement rate. Bracketing the
two extremes (perfectly correlated errors → the max; independent errors →
the union):

| field | teacher error vs adjudication | student↔teacher disagreement | student error vs adjudication (bracket) |
|---|---|---|---|
| sentiment | 5.4% | 16.5% | **16.5% – 20.1%** (teacher: 5.4%) |
| red_flags, per-category | 7.5% | 7.58% | **7.6% – 14.5%** (teacher: 7.5%) |

So E2's sentiment labels are wrong roughly **3–4× as often** as E1's, and
its red-flag category calls up to **2× as often** — and the errors are
**directional** (systematic under-recall of negatives), not symmetric noise.
A screening tool whose labeler is half-blind to negative sentiment is
attenuated on exactly the dimension it exists to detect.

**Failure mode of deciding it lazily.** Accept the student because
"red_flags is at the teacher's ceiling and throughput is great," then design
G2 as a copy of E1's spot-check (400 chunks, Tier C n=36). Consequences: the
corpus-wide quality estimate again has a ±14-point interval; the extension-
stratum promotion decision — which the hybrid amendment explicitly bound to
G2 — rests on a handful of rows per unseen sector; and, critically, **G2 has
no defined failure branch.** Under the spend freeze there is no re-label
path, so "the bar failed" currently has no consequence attached to it. A
gate with no failure branch is not a gate; it is a checkpoint that always
passes.

**Preparation that makes it good.**
1. **Rule G1 explicitly against the stated floor**, including the sentiment
   miss, rather than letting the red_flags result carry the whole decision.
   Either lower the floor with a reason, or state that sentiment features
   enter E2 with a declared attenuation caveat, or train a third epoch
   (~1 night; epoch 1→2 moved NEGATIVE recall 0.425→0.487, so the trend is
   real but slow).
2. **Pre-commit G2's bar before seeing any rate** — this is the same
   discipline as G3, applied to labels.
3. **Size the base-rate stratum for a usable CI** (n≈150 → ±7 points).
4. **Stratify by section_type as well as sector.** The student is measurably
   worst where E1's labels were also worst: RISK_FACTORS red_flags exact-set
   **54.1%** vs EX99 67.5%. RISK_FACTORS is ~24% of E1's chunks.
5. **Define the failure branch in advance.** If a category fails: drop it
   from the primary analysis? report it with a bounded-attenuation caveat?
   revisit §1.10? Decide before the number exists.
6. **[MEASURED TODAY] Handle the `8K_BODY` register.** E1's corpus contains
   exactly **8** `8K_BODY` chunks, and the eval report states all 8 landed
   in the **eval** split — so the student was trained on **zero** examples
   of that register. F2's audit shows **210 filings** whose earnings
   document is stored as `8K_BODY`. The student will be asked to label a
   register it has never seen, and since `section_type` is never in the
   prompt, field applicability is inferred from register alone. Either
   exclude `8K_BODY` from E2 labeling, or pilot it explicitly, or accept it
   with a stated caveat — but decide.

### 3.3 — #3: F4 labeling-campaign scale and config
**Why it is third.** It is 9–17 nights of the owner's only machine, it is
the point of no return for the labeler choice, and its planned size does not
match the corpus that F2 actually built.

**[MEASURED TODAY] — the planned scale is stale and low.** `EXPANSION_PLAN`
costed "~70k new chunks," amended to "~98k" for hybrid136; the eval report's
own table uses 76,746–104,746 chunks → 57–78 h → 5.7–7.8 overnights. Two
independent re-derivations from measured artifacts disagree with that:

*Method.* From `data/paragraph_occurrence_map.parquet` joined to
`data/filings.parquet` filing dates, the cumulative count of *canonical*
(deduplicated) paragraphs by first-seen quarter reaches steady state after
the initial 10-K load and then grows at **≈86 new canonical paragraphs per
company-quarter** (17,264 new paragraphs over the 8 quarters 2024Q2→2026Q2,
25 companies). E1's packing ratio is 6,747 chunks / 28,504 canonical
paragraphs = **0.237 chunks per canonical paragraph**, i.e. **≈20.4 chunks
per company-quarter**. Back-check: 20.4 × 300 company-quarters = 6,130 vs
E1's actual 6,747 (the gap is the front-loaded first 10-K), so the rate is
mildly conservative.

- **Member-spell-only labeling:** 136 members × 11 years × 4 = 5,984
  member-quarters → **≈122,000 chunks** → **91 h ≈ 9 overnights**.
- **Full ingested corpus** (what `EXPANSION_PLAN` §3.1's "label ALL chunks"
  literally says, and what F2's shared-window ingestion produced): 45,545
  filings ÷ E1's 4.24 filings-per-company-quarter = 10,750 company-quarters
  → **≈220,000 chunks** → **164 h ≈ 16 overnights**.

That is **1.2× to 2.1× the planned worst case**, i.e. the difference between
one long week and two and a half.

**[MEASURED TODAY] — and no scale discount is available.** The obvious hope
is that boilerplate dedups harder across 244 companies than across 25. It
does not: **exactly 1 of 28,504 canonical paragraphs occurs under more than
one ticker.** All observed deduplication is *within*-company repetition,
which the steady-state per-company-quarter rate already captures. Adding 219
companies adds their paragraphs essentially linearly.
*(Caveats on my estimate: it assumes E1's mega-cap, 2023–2026 novelty rate
transfers to 2015-era filings and to smaller members; pre-2019 filings and
different filer styles could move it either way. The point is not that
220,000 is the right number — it is that **nobody has re-derived the number
against the corpus that now exists**, and the planned figure predates it.)*

**Same measurement corrects a stated premise.** `EXPANSION_PLAN` §3.1
justifies the full rebuild partly with "boilerplate is shared across
companies." Measured, it is not. The ruling's *conclusion* still stands for
a different and stronger reason — homes are earliest-occurrence within a
company's own history, and E2 extends the window back to 2015, so every
company's earliest occurrence moves — but the stated reason should be
corrected before it is cited again.

**Failure mode of deciding it lazily.** Start the campaign on the 98k
estimate and discover at night 8 that it is half done; or label the full
11-year window for every CIK when only 55.7% of enumerated filings fall
inside any membership spell, burning ~45% of 164 hours on rows F5 will never
join; or fail to pin the adapter hash, decoding params and prompt sha, and
end up with 120k labels that cannot be reproduced or attributed to a
configuration.

**Preparation that makes it good.**
1. **Re-derive the chunk count from F3's actual section output** before
   committing — after F3 it is exact, not extrapolated.
2. **Decide full-window vs member-spell-plus-margin explicitly.** Trailing
   features need ~4 quarters of history, not 11 years: labeling
   member-spells + a 1-year pre-spell margin plausibly captures everything
   F5 uses at roughly half the compute of the full window. This is the
   single largest lever on the campaign's length and it has never been
   costed.
3. **Pin the run manifest** — adapter sha256, base weights sha256, decoding
   config, prompt sha. The epoch-2 eval report already does exactly this;
   reuse its provenance table verbatim.
4. **Per-row append checkpointing + resume-on-kill**, per the standing
   incident rule (this is already written into HANDOFF §4 — honour it).
5. **Compute the train-overlap provenance flag at label time**, not
   retrospectively. **[MEASURED TODAY]** all 25 E1 companies are hybrid136
   members, so contamination is confined to 25 of 244 CIKs and to their
   2023Q3–2026Q3 filings — a clean, small, flaggable set.
6. **Run a 500-chunk pilot on extension-sector and pre-2019 text first**,
   measuring parse-failure and field-presence rates outside the training
   distribution, before committing 90–165 hours.

---

## PART 4 — Decisions nobody has flagged

### 4.1 — THE unflagged decision: there is no ratified response to E2's own pre-committed outcomes
**This is the one the owner is actually asking about when they say "going
down a hole."**

`EXPANSION_PLAN.md` §2a states the pre-committed acceptable outcome
carefully: at E2's power a null bounds the true dedup IC delta within
roughly ±0.013–0.027, supporting "no text-vs-numeric improvement of
economically relevant size exists in this universe." `ROADMAP.md` Phase F
ends at "G4 (owner): final read." **And that is where the plan stops.**

Nowhere in `HANDOFF.md` §3, `EXPANSION_PLAN.md`, `ROADMAP.md` or
`F2_PROGRESS.md` is there a ratified statement of what happens *after* each
outcome. There is no stopping rule.

Why that is dangerous here specifically: **the project has already run this
loop once.** E1 produced a null; the null was correctly diagnosed as
underpowered; the response was a 10× bigger experiment. That was the right
call for E1. But the same reasoning is available again — E2 nulls, the
diagnosis notes the regime-variance floor was never identified, or that
label noise attenuated the effect, or that mid-caps were excluded, and E3
follows. Each step is locally justified. The ladder has no top because
nobody built one.

**What would fix it, and it costs one paragraph:** ratify, at G3 and before
any E2 result exists, the response to each pre-committed outcome. For
example — and these are illustrations, not recommendations, because the
outcomes are the owner's to choose:
- **Bounded null** → the project's scientific question is answered in the
  negative at the stated power; F6 writes it up as a finished negative
  result and the pipeline is archived rather than expanded.
- **Positive delta above the MDE** → what specifically follows? A robustness
  suite? A mid-cap arm? A stopping point?
- **Ambiguous** (delta inside the MDE, signs unstable) → the pre-committed
  reading is "underpowered again," which is the trapdoor. Decide *now*
  whether that outcome licenses a third experiment or closes the question.

A pre-registered stopping rule is the difference between a research
programme and a hole. Everything else in this audit is a detail beside it.

### 4.2 — The charter says "not a product with users"; the owner's own language says "product"
`HANDOFF.md` §1 is unambiguous: "a **solo-owner research and screening
tool**, not a product with users," with contractual non-goals. The
commissioning message says "making a **product** that is not really
useful." No ratification has ever changed the charter, and no agent should
change it — but the drift deserves to be surfaced rather than silently
resolved in either direction, because **the two framings want opposite
things from E2**:
- As a **research question**, E2 is well designed: a null is a real result,
  power is the right thing to buy, and the honest-limitations discipline is
  the deliverable.
- As a **product**, E2 is the wrong vehicle entirely: a product needs
  something a user can do, and the current plan's best realistic outcome is
  a well-bounded "no." Nothing in F0–F6 produces a usable screening
  interface, a maintained data feed, or an output anyone consumes.

This is not a finding that the charter is wrong. It is a finding that
**which of the two the owner wants determines whether the next six months
are well spent**, and that question has never been put in §3. It should be
answered before G3, because it changes what "success" means in the stopping
rule of §4.1.

### 4.3 — A limitation declared unmeasurable is measurable from data already on disk
Covered in §1.14. `F2_INGESTION_REPORT.md` §9 item 12 states the SIC
look-ahead's magnitude is unmeasurable; **[MEASURED TODAY]** the cached
filing-index pages carry submission-time SIC, giving 10/243 members with a
SIC change and ≥4 crossing sector buckets, at 0 network cost. Flagged here
as well because a *false* claim of unmeasurability inside an otherwise
scrupulous limitations list is the kind of thing that costs the whole list
its credibility with an external reader.

### 4.4 — The residual self-identification channel has never been re-examined for the distilled labeler
`HANDOFF.md` §7 keeps this as a standing documented risk: 27–46% of chunks
name their own company, mitigated only by prompt instruction. That analysis
was done for the Claude teacher, which was stateless per request and had no
project-specific memory of these companies.

The student is different in kind: a 7B model **fine-tuned on those very
chunks**, for two epochs. It has had the opportunity to memorise
company-specific label patterns, and in E2 it will label 244 companies
including the 25 whose text it trained on. The `EXPANSION_PLAN` §3.2
provenance flag (train-overlap vs novel) is the right instrument and it
exists — but it was designed to detect *label replay on boilerplate*, not
*identity-conditioned labeling on novel text from a known company*. Nobody
has stated which of those the flag actually measures, or checked whether the
student's per-company behaviour differs between its 25 training companies
and the other 219. **A cheap check at G2: stratify the spot-check by
train-company vs novel-company and compare agreement.**

### 4.5 — "497 UNRESOLVED fundamentals pairs" reads worse than it is, and nobody has said so
**[MEASURED TODAY]** from `data/f2/concept_resolution.csv`: the 497
unresolved (cik, family) pairs are heavily concentrated in optional families
— `net_income_to_common` 158, `minority_interest` 114, `liabilities` 78,
`operating_income` 59. The families a numeric baseline actually needs are
near-complete across all 244 members: **assets 244/244, equity 242, cash
241, net_income 240, eps_diluted 234, revenue 224, shares_outstanding 214.**
The report is honest but the headline figure ("497 pairs never become
series," "224 of 244 CIKs have ≥1 unresolved") will be read as a coverage
crisis by anyone skimming. It is not one. Worth a single calibrating
sentence in the F5/G4 write-up — under-stating your own data quality is a
smaller sin than over-stating it, but it still misleads.

### 4.6 — Smaller items, listed without elaboration
- The Yahoo price-source substitution has never been ratified as such
  (§1.11) — it is the only major input in the project running on an
  inherited fallback rather than a decision.
- `MODEL_CARD.md` and `LIMITATIONS.md` still describe E1 only, and F2's own
  §10 flags `INGESTION_NOTES.md`, `README.md` and `PRICES_NOTES.md` as
  E1-accurate/E2-stale. Documentation debt is disclosed, which is good — but
  the count of stale docs is now five and growing one phase at a time.
- The `rubric v1.2` proposal has sat unratified since 2026-08-18. Under the
  spend freeze it changes nothing today, but it is a live decision recorded
  as pending in three documents, which is a small ongoing tax on every
  reader.

---

## PART 5 — Summary tables

### 5.1 — Grades at a glance

**SOUND (14):** rubric v1.1 · every-occurrence attribution · spot-check
design · backtest-before-fine-tune · local-MLX-at-$0 · Step-4 GO
diagnosis-scoped · diagnosis read → bigger experiment · E2 scope 100×10 ·
PIT reconstitution rule (selection side) · G1 conditional ruling ·
fine-tune launch discipline · USD-conversion principle · lazy-elite as
policy · and 9 of the 12 F2 build rulings.

**DEFENSIBLE-BUT-DEBATABLE (7):** sync rule (now partly obsolete) ·
adjudication delegation (thin base-rate stratum) · frozen labels (known-bad
targets in the training split) · backtest target (self-referential
benchmark, deferred to G3) · hybrid136 amendment (extension arm's
cost/benefit) · GLD retention (bounded, quantified, G3 follow-through
required) · model tiering (decider = verifier).

**SHOULD-REVISIT (3):**
| Item | Better alternative | Cost now | Cost at next natural gate |
|---|---|---|---|
| **Spend freeze, unpriced against what it now binds** (§1.10) | Price it explicitly: ≈$16.09 buys a rubric-v1.2 re-label of the training corpus; decide yes or no with the number in hand | ≈$16 + ~2 nights retrain + a fresh spot-check ($0) | After F4: discarding and re-running a 9–17-overnight labeling campaign — roughly 10× |
| **EX-99 selection error rate never estimated** (§2.1) | A random, base-rate-representative sample of ~60–100 selections with a Wilson CI — the Tier-C protocol the project already invented, applied to document selection | One `extraction-qa-engineer` pass, $0, ~half a day | After F3+F4: re-extract and re-label 120k+ chunks. **Hard deadline: F3 start** |
| **Yahoo as unratified standing price source** (§1.11) | One explicit owner ratification (or refusal) of Yahoo-at-E2-scale, recorded in §3 like every other input | One owner sentence | Baked into every E2 result and into whatever F6 publishes |

### 5.2 — Everything measured today, with method

| Claim | Method | Result |
|---|---|---|
| Cross-company paragraph sharing | `paragraph_occurrence_map.parquet`, distinct tickers per canonical paragraph | **1 of 28,504** |
| Core stratum size per date | `hybrid136_panel.parquet` groupby | **100 core + 36 extension at all 11 dates**; 244 distinct CIKs (176/68) |
| Non-USD float facts | scan `dei:EntityPublicFloat` units across all 244 cached companyfacts | **4,672 USD / 1 CAD** (Enbridge 2022-06-30, used at 2023-07-01 only) |
| Enbridge core placement under conversion | energy core ranks at 2023-07-01 | CAD 85.6B ≈ USD 66–67B → rank 4–5 vs K=20 → **membership unchanged** |
| GLD's footprint | panel + `concept_resolution.csv` + EX-99 audit | **2 of 1,100 core seats**; 0 earnings 8-Ks; 7/14 families ABSENT |
| Historical SIC availability | parse `SIC=` from 10,875 cached `filing_index/*.html` | **10 of 243 members changed SIC**; ≥4 cross a sector bucket; changes cleanly time-ordered |
| `8K_BODY` training exposure | `labels.parquet` section_type counts vs EX-99 audit | E1: **8 chunks, all in eval → 0 in training**; E2: **210 filings** |
| E2 chunk-scale | steady-state canonical-paragraph novelty (86/company-quarter) × packing ratio (0.237) | **≈122k** (member-spell) to **≈220k** (full window) vs planned 98–105k |
| Re-label price | project spend table, $10.06 / 4,219 rows | **$2.38 per 1,000 rows** → **$16.09** for all 6,747 |
| Fundamentals coverage on load-bearing families | `concept_resolution.csv` | assets 244, equity 242, cash 241, net_income 240, eps_diluted 234, revenue 224, shares 214 (of 244) |
| Compounded labeler error | teacher adjudicated error ⊕ student↔teacher disagreement, bracketed | sentiment **16.5–20.1%** (teacher 5.4%); red_flags/category **7.6–14.5%** (teacher 7.5%) |

---

*Lens 3 of 4. This document grades decisions; it makes none. Every number
above states how it was measured. Nothing in this file is an owner ruling,
and nothing in it authorises spend, a charter change, or a gate outcome.*
