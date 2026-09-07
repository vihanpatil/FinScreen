# F2 — the E2 ingestion report

**Written 2026-08-24, at the close of F2 (E2 phase: ingestion at scale).**
This file is meant to stand alone: what was ingested, how it was checked,
what is queued for you, and every caveat that has to travel with the E2
corpus from here on.

**Scope.** F2 fetched and stored data. It built no features, ran no
backtest, produced no model results, and makes **no performance claim of
any kind** — there is nothing here to claim performance about yet. The
benchmark definition, the fold structure and the label-quality bar are
gates G3 and G2 and are untouched by F2 (`EXPANSION_PLAN.md` §4).

**Provenance, stated once and binding.** Every decision recorded in this
report is a **main-session build ruling** made inside the design you
already ratified on 2026-08-20 / 2026-08-21 (`HANDOFF.md` §3). **None of
them is your ruling**, and none should ever be cited as such
(`HANDOFF.md` §7). The items in §0 are the only things in F2 that are
yours to decide.

**Status of the numbers in this report: FINAL.** An independent red-team
pass over S2–S6 (`data/f2/status/S7_redteam.md`), and the ordered reads it
triggered, found three earnings-document selection defects after this
report was first drafted — 15 filings storing the 8-K cover page (finding
B1), one filing mis-labelled by the fix for B1 (Pioneer), and **PSEG, whose
45 of 45 earnings selections were conference-call slide decks**. **All
three are fixed and the corpus has been regenerated**: segment 1 re-ran to
**attempt 11**, segment 2's **delta 4** fetched the newly selected
documents, segment 3 re-ran with the S4-side fixes, and the full test suite
gates at **815 passed / 5 skipped / 0 failed**. Every figure below is the
post-fix figure with its source named. The red-team's Section A
independently re-derived — from the artifacts, not from any agent's
self-report — the 45,632 enumeration and its 45,545 + 87 split, all 3,416
fundamentals resolutions, the EA sole-instance result and both censoring
pairs, and found no disagreement; those were unaffected by the fixes and
are unchanged.

---

## 0. Queued for you

### (a) SPDR Gold Trust (CIK 1222333) — is it a member?

GLD is a hybrid136 member in the **core financials** stratum (SIC 6221,
spells 2017–18 and 2023–24). Segment 4's instrument-type tripwire caught
it: Yahoo returns `meta.instrumentType='ETF'`, not `EQUITY`
(`data/f2/s6_segment4_prices.log:491`).

It is a passive commodity trust, not an operating company. Its "float" is
trust asset value; its filings describe gold custody; it filed 65 filings
in the window and **zero** item-2.02 earnings 8-Ks, so it is the one
member absent from the EX-99 audit (243 of 244 CIKs are in it —
`data/f2/status/S6_ex99_manual_read.md` §4).

Membership is your territory, not the build's. The choice is: exclude it
under a new evidenced *entity-type-eligibility* rule class (the same shape
as the `float_integrity_2026-08-21` rules), or deliberately retain it and
say why. **F2 treats it as an ordinary member meanwhile** — its rows are
in `data/prices_e2.parquet` and it is counted in both price pairs below.

Context from the same scan, so you can see where the line would fall: the
energy MLPs (Enterprise Products, Williams Partners, Energy Transfer
entities, Magellan, MPLX) and Digital Realty (a REIT) are genuine
operating companies — known, defensible consequences of the float rule
you ratified. **GLD is the only anomaly of this kind found.**

### (b) The epoch-2 eval read — gate G1's conditional acceptance

Not an F2 item, but it is queued behind F2 and F4 depends on it. On
2026-08-21 you ruled: *"I want to accept the student as E2's labeler, but
let's keep it conditional on the epoch-2 re-eval."* The re-eval is
complete and unread:
`finetune/runs/2026-08-22-eval-epoch2/eval_report.md` (1,010 rows).

Its headline numbers, each **an agreement rate between the fine-tuned
student model and the Claude teacher labels** — a model-vs-model
comparison, not human validation of either:

Headline metrics run over 1,002 of the 1,010 generated rows — the 8
`8K_BODY` rows are excluded as not evaluable (n=8, from only 2 tickers),
per `HANDOFF.md` §7, and shown separately in the report for completeness.

| measure (student vs teacher, 2026-08-22 eval) | epoch 2 | epoch 1 |
|---|---|---|
| parse-failure / schema-violation rate | **0.00% / 0.00%** | 0.00% |
| sentiment exact-match | **83.5%** (724/867) | 81.7% |
| sentiment NEGATIVE recall | **0.487** | 0.425 |
| guidance_direction exact-match, raw | **58.8%** (335/570) | 47.7% |
| red_flags exact-set match | **64.87%** (650/1,002) | 62.8% |
| red_flags per-category agreement | **92.42%** (456 wrong of 6,012 decisions) | 91.6% |
| measured throughput | **1,337 chunks/hour** | 1,068 |

Read those against the **teacher's own reproducibility**, which is itself
a model-consensus number from E1's spot-check, not ground truth:
sentiment 94.6%, guidance 95.2%, red_flags exact-set 63.4% pooled,
per-category 92.5% (`HANDOFF.md` §2a). So red_flags now sits *at or just
above* the level at which the teacher's own labels reproduce, and
sentiment is still ~11 points below the teacher.

**One gap in the report, and it is the one your G1 ruling asked for.** The
ruling required guidance to be reported both raw and under the proposed
`missing → NONE` post-rule. The report omits the post-ruled line.
Derived from the report's own confusion table (`F2_PROGRESS.md` §6):
**561/570 = 98.4%**, because 226 of the 235 errors are
`NONE → __MISSING_FIELD__`. That derivation is a build-side reading of the
report, not a regenerated metric — **a patch is queued** with
finetune-engineer to regenerate the report with the post-ruled line before
you read it. F2 does not depend on this; F4 does.

### (c) An owner-read item: what the censoring actually costs, in membership-time

Not a decision, but do not skip it — it changes how E2's per-fold results
should be read.

The report elsewhere quotes the censoring as a **CIK count**: 32 of 244
members have no usable prices. That is 13% and it invites reading the loss
as a flat haircut. It is not flat. Re-derived by the red-team (finding
**B4**) by joining `price_ticker_map.has_usable_prices` onto the 1,496
membership-panel cells:

| reconstitution date | member-date cells with NO usable prices |
|---|---|
| 2016-07-01 | 19 / 136 = **14.0%** |
| 2017-07-01 | 22 / 136 = **16.2%** |
| 2018-07-01 | 17 / 136 = **12.5%** |
| 2019-07-01 | 12 / 136 = 8.8% |
| 2020-07-01 | 7 / 136 = 5.1% |
| 2021 → 2025 | 5 / 3 / 5 / 4 / 1 |
| 2026-07-01 | **0** |
| **all dates pooled** | 95 / 1,496 = **6.35%** |

By sector: energy **16.4%**, healthcare 7.3%, tech 6.4%,
materials_realestate 5.3%, financials 4.5%, consumer 4.1%, industrials
2.3%, utilities **0%**. By stratum: **core 7.7% vs extension 2.5%**.

**Why this matters, plainly.** The deletion is (a) **monotonically
decaying in time** — 14–16% of the earliest cohorts, zero by 2026 — and
(b) **outcome-correlated**, because these are acquisitions and
take-privates, not random gaps. That is exactly the shape that makes early
folds look different from late folds **for a non-alpha reason**. Anyone
reading an E2 walk-forward result and seeing early folds behave
differently must consider this before considering signal.

**Both numbers travel with every E2 result**: the CIK pair (§2) *and* this
panel profile. Neither substitutes for the other.

### (d) A second owner-read item: Enbridge reports in Canadian dollars

**Enbridge (CIK 895728, core / energy) is the universe's only non-USD
reporter** — all **13** of its resolved fundamentals families come out in
`CAD` (12 in `CAD`, one in `CAD/shares`), none mixed, while its price
series is in USD (`s6_segment3_fundamentals_attempt3.log:786-798`;
`F2_SPEC.md` §11 amendment A11). F2 **converts nothing**: the resolution
CSV now carries the unit per family and a standing
`fundamentals_non_usd_reporting` WARN fires for each one, so any
fundamentals-to-price ratio for Enbridge (P/E, P/B, earnings yield) is
wrong by the exchange rate until F5 converts. That part is handled — it is
loud, and F5 owns it.

**The part that is yours:** Enbridge sits in the **core** stratum because
of F1's float ranking, and its `dei:EntityPublicFloat` is presumably filed
in CAD too. Whether F1 compared a CAD-denominated float against USD floats
without converting is the same currency question one level up — and if it
did, Enbridge's *core placement itself* rests on an unconverted number.
This is a membership question, so it is yours, not the build's. F1's
artifacts stay frozen meanwhile and F2 changes nothing about it
(`F2_PROGRESS.md` §6, newest entry).

### Three visibility items (not decisions, no gate)

1. **Yahoo is now the default price source** (`--price-source yahoo`).
   Your 2026-08-18 target ratification named Stooq by example; Stooq has
   been bot-gated site-wide since that same day, so trying it 213 times to
   fail 213 times would be the wrong default. The Stooq path is intact,
   one flag away. Full provenance caveat in §6 below.
2. **The censoring pairs** (§2) **and their membership-time profile**
   (§0c). Both must accompany every E2 result.
3. **The current-SIC sector look-ahead reaches further than previously
   stated** — into membership composition, not just the sector label. This
   is a property of the universe rule you ratified, not a build error, and
   it is not fixable without re-ratifying that rule. Detail in §9 item 12;
   it is listed here because the earlier framing understated it.

---

## 1. What was ingested

All four network segments completed. Fixed corpus window
**2015-07-01 → 2026-08-31** for metadata and documents (the floor is 12
months before the first reconstitution date so trailing-four-quarter
features are complete at first membership); fundamentals and prices are
full available history, with point-in-time selection downstream.

| artifact | measured | where |
|---|---|---|
| filings enumerated | **45,632** (8-K 35,648 / 10-Q 7,532 / 10-K 2,452) | `s6_segment1_metadata_attempt6.log:334` |
| …stored in `filings` | **45,545** rows (keyed on accession) | same log, line 335 |
| …plus `co_registrant_filings` | **87** rows → 45,545 + 87 = 45,632 | same |
| earnings 8-Ks (item 2.02) | **10,569** | log:289 |
| documents cached | **20,521** targets (10,567 earnings docs + 7,509 10-Q + 2,445 10-K), **0 FAILED** — final delta: 45 fetched (PSEG's releases), 20,476 already cached. The earnings-doc count is 10,569 filings − 2 evidenced exclusions. | `s6_segment2_documents_delta4.log:3, 91` |
| document cache size | **42 GB** under `data/raw/documents/` | `data/f2/status/S6_runs.md` |
| fundamentals rows | **622,661** (30 tags across 14 concept families, 244 companyfacts documents) | `s6_segment3_fundamentals_attempt2.log:248` |
| price rows | **1,960,738** across 213 CIKs (41.3 MB) | `s6_segment4_prices.log:269` |
| observed max `filing_date` | **2026-08-24** (freeze constant 2026-08-31) | log:344 |

**Enumerated vs stored — say which, every time.** "45,632" is the
**enumerated** count. The `filings` table holds **45,545** rows, because it
is keyed on accession and 87 accessions carry two member registrants each;
those 87 attributions live in `co_registrant_filings` (§3.2). 45,545 + 87
= 45,632. Any per-company query must say which base it is on — the
red-team's finding **B20** is that the ledger (`F2_PROGRESS.md`) and
`S6_runs.md` quote "45,632 filings" flatly, conflating the two.

One reconciliation worth knowing so nobody reads it as drift: the spec's
plan-of-record count is **45,622**, measured offline from the cache before
the run. The real run enumerated **45,632** — ten filings that were filed
between the two measurements (observed max `filing_date` 2026-08-24, the
day of the run). Every other spec-measured count reproduced exactly.

**And a correction to the spec's own reproducibility claim (S7 finding
B16).** `F2_SPEC.md` §2 justifies the fixed `CORPUS_WINDOW_END =
2026-08-31` on the grounds that "a re-run in October yields the same
corpus." **That is not true yet**: the freeze date is in the *future*
relative to the run (max `filing_date` 2026-08-24), so companies are still
filing into the window and a re-run today already differs from the spec's
own offline measurement — 45,622 → 45,632 is exactly that happening.
**Reproducibility holds only once 2026-08-31 has passed.** Until then, any
re-run may enumerate slightly more filings, and a re-run's counts should be
diffed rather than assumed identical.

Universe: **244 distinct member CIKs** (176 core / 68 extension), 299
membership spells, exactly 136 members at each of 11 annual reconstitution
dates 2016-07-01 … 2026-07-01, all seven universe artifacts sha256-verified
before use (`data/f2/status/S2_membership.md` §2).

By sector (from `companies` and `universe_membership`, which agree):
consumer 33, energy 32, financials 37, healthcare 32, industrials 19,
materials_realestate 28, tech 42, utilities 21 = 244.

Distress events, ingested at zero extra network cost — this is
`EXPANSION_PLAN.md` §2c's mandatory mitigation, so censored names stay
visible on the EDGAR side:

| event | filings / CIKs |
|---|---|
| 8-K item 1.03 (bankruptcy) | **2 filings / 1 CIK** — CIK 895126 (Expand Energy, ex-Chesapeake): `0001104659-20-077745` filed **2020-06-29** and `0000895126-21-000016` filed **2021-01-19**. (An earlier draft of this report, `F2_SPEC.md` §11's first amendment and `F2_PROGRESS.md` all named a single filing dated 2020-06-28; **no such filing exists** — S7 finding **B10**. All three are now corrected: F2_SPEC by a dated note in amendment A12, `F2_PROGRESS.md` §5, and here.) |
| Form 25 (delisting) | 37 / 30 |
| Form 25-NSE (exchange-filed delisting) | 510 / 131 — **noisy by construction**: filed by the exchange, fires for preferreds and notes too. Stored as-is, labelled as such. |
| Form 15 (deregistration) | 119 / 67 |

Output artifacts: `data/filings_metadata_e2.db`,
`data/fundamentals_e2.parquet`, `data/prices_e2.parquet`,
`data/f2/concept_resolution.csv`, `data/f2/ex99_selection_audit.csv`,
`data/f2/price_ticker_map.csv`. **E1's artifacts were not touched** —
`data/labels.parquet`, `data/universe.csv`, `data/filings_metadata.db`,
`data/fundamentals.parquet`, `data/prices.parquet` all keep their
pre-session state, and the code refuses E1's paths by name.

---

## 2. The two censoring numbers — never conflate them

There are **two** price-censoring pairs. They answer different questions
and they differ. Both are printed on every run under explicit labels, and
both must appear wherever either appears.

| pair | value | the question it answers |
|---|---|---|
| **FETCH** | **213 fetched / 31 unfetchable** (27 core / 4 extension) | Did a CIK-verified ticker exist to ask for? An *ingestion* fact. |
| **OPERATIVE** | **212 usable / 32 with NO usable prices** (**28 core** / 4 extension) | Does the member have prices inside the window it was actually a member? **This is the pair every E2 result, benchmark and stratified claim quotes.** |

**Both of these are CIK counts, and a CIK count is the wrong denominator
for a walk-forward backtest.** In membership-time the same censoring is
14.0% / 16.2% / 12.5% of member-date cells in the 2016 / 2017 / 2018
cohorts, decaying to 0.0% by 2026, 6.35% pooled, concentrated in energy
(16.4%) and in the core stratum (7.7% vs 2.5%) — the full table is in
**§0c**, and it must be quoted alongside the pair, never instead of it
(S7 finding **B4**).

32 = 31 unfetchable + 1 fetched-but-unusable. The one extra is **EA
(Electronic Arts, CIK 712515)**, a *core* tech member from 2017-07 to
2021-07. Yahoo returned 6 rows for it, all 2026-07-17 → 2026-08-10,
flatlined at the ~$209.70 take-private price with volume 0 and
`firstTradeDate` reset to 2026-07-17: it is the right company, but Yahoo
**purged the delisted name's history**. Zero of its 6 rows fall inside its
own coverage window (`data/f2/status/S5_prices.md` §8.1).

This is exactly the outcome-side censoring residual `EXPANSION_PLAN.md`
§2c pre-registered as **not fully fixable**, now real for a core member.
Selection stayed survivorship-free — EA is in the universe on the dates it
qualified — but its *outcome* is censored, and no price vendor can fix
that because the history no longer exists to buy.

EA is the sole instance and it is not a threshold artifact: among the
other 212 fetched members the next-smallest in-window row count is **539**.
The pin is two-sided — a second such member raises a FATAL naming it, and
EA *regaining* history also raises a FATAL. Its delisting is visible in
`distress_events` as designed: `25-NSE` filed 2026-08-04
(`0001354457-26-000757`) and `15-12G` filed 2026-08-14
(`0001140361-26-032929`), and the pipeline WARNs if a no-coverage member
ever has *no* EDGAR-side explanation.

**Reconciliation with F1's census.** F1's headline was 29. F2 censors 31,
and the difference is fully pre-registered: −{34088} (Exxon, resolved via
the one evidenced successor override) and +{30554} (EIDP, preferred-series
listings only). Of the 31 censored, 29 have stopped filing — F1's
delisting-censored population exactly — and 2 are still filing: CIK 29915
(Dow Chemical, deliberately censored: today's `DOW` is Dow Inc, a 2019
spin-off whose price history is a different company) and CIK 30554. The
census diff is a **fetch-side** comparison; EA is a new axis, not a census
delta.

---

## 3. What "in the corpus" does not mean

Two facts that will silently corrupt any downstream per-company query if
they are forgotten.

**3.1 — 20,218 of the 45,632 *enumerated* filings fall outside every
membership spell of their own CIK. This is BY DESIGN.** On the **stored**
base the same measurement is **20,165 of 45,545 = 44.3%** (the red-team's
re-derivation over the `filings` table alone, finding **B20**); the two
differ by the 87 co-registrant rows, and the pipeline prints the
enumerated version. Quote whichever you like — **but say which**, because
neither log line labels its base today.

F2 ingests the full window for every CIK that is ever a member rather than
clipping to membership spells: a member at date *t* needs pre-*t* filings
for trailing features, and clipping would have silently lost the corpus's
**only bankruptcy — CIK 895126 (Expand Energy), whose two 8-K item-1.03
filings are dated 2020-06-29 and 2021-01-19.** That CIK's coverage window
is 2024-07-01 → 2026-08-31, so **both** filings sit outside it; the
argument for the shared window is therefore stronger than the version
previously written here and in `F2_SPEC.md` §11, which named one filing on
a date that does not exist (S7 finding **B10**). Measured against the three
candidate enumeration windows, only the shared window reproduces the plan
of record (`data/f2/F2_SPEC.md` §11, first amendment).

**Binding consequence: presence in `filings` is NOT membership.** F5 must
join on `universe_membership`, never on presence in `filings`. Ingestion
breadth never implies membership, so point-in-time safety is unaffected.

**3.2 — Absence from `filings` is NEVER evidence a company did not
file.** EDGAR lists co-registrants on a single accession — a parent and a
subsidiary file one 8-K together. `filings` is keyed on
`accession_number`, so when both filers are members the second CIK's
attribution has nowhere to go. Measured: **87 of the 45,632 enumerated
filings (0.19%)**, across exactly three pairs — Dow Chemical (29915)/Dow Inc (1751788) 67,
Williams Companies (107263)/Williams Partners (1483096) 16, Exelon
(1109357)/Constellation (1868275) 4; by form 57 8-K, 23 10-Q, 7 10-K.

Re-keying the table was rejected as over-engineering for 0.19% of rows
(it would ripple into `filing_documents` and F3's extraction grain).
Instead every dropped attribution is stored in the side table
`co_registrant_filings(accession_number, kept_cik, co_cik, form,
filing_date)`, with a deterministic keeper rule (the numerically **lowest**
member CIK keeps the `filings` row, guaranteed by the loop, pinned by
tests). **Any per-company filing or coverage question must consult
`filings` ∪ `co_registrant_filings`**, and F5's accession → company
attribution must yield *both* member CIKs for these 87 accessions.

**One mitigating fact, measured by the red-team and worth knowing before
anyone spends effort here (S7 Section A, item 11): none of the 87
co-registrant accessions is an earnings 8-K.** So the accession-keyed
primary key costs the **text** corpus nothing — every affected row is a
periodic filing or a non-earnings 8-K. The rule above still binds for
filing-count and coverage questions; it just is not a text-coverage
problem.

### 3.3 — Point-in-time conventions F2 leaves open (pre-register these at G3)

F2 stores the right raw material and deliberately stops there. "Use
`filing_date`, never `report_date`" (HANDOFF §7) is necessary and **not
sufficient**. Three facts are measured, unresolved by design, and are F5
decisions to be pre-registered at gate G3 rather than discovered later
(S7 finding **B8**):

| fact, measured | the convention that has to be chosen |
|---|---|
| **20,715 of 45,545 filings (45%) are accepted at 20:00–21:00 UTC — 16:00–17:00 ET, i.e. after the close** — while carrying that day's `filing_date`. `acceptance_datetime` is stored. | Is the tradable date `filing_date` or `filing_date + 1`? Dating a feature to `filing_date` and matching it to a return window starting the same day is a one-day look-ahead on nearly half the corpus. |
| **Two filings whose `filing_date` precedes their acceptance by 344 and 633 days**, both Salesforce (CIK 1108524, a core member): `0001108524-22-000007` (10-Q, filing_date 2020-06-01, accepted 2022-02-24) and `0001108524-22-000008` (10-K, filing_date 2021-03-17, accepted 2022-02-24). No check asserts `acceptance_datetime >= filing_date`. | Whatever the EDGAR-side cause, the bytes served under those accessions were **not public on their `filing_date`**. F5 needs a rule for the general case, not just these two. |
| **20,027 of 273,268 (cik, concept, unit, period) groups (7.3%) carry more than one distinct value across filings** — restatements. The parquet keeps every filed occurrence with its `filed` date, so it *is* PIT-capable. | The as-of selection rule must be `pit.value_as_of()`'s filed-date semantics, stated in writing. A naive latest-value join is look-ahead on 7.3% of period-cells. |

None of these is a defect in F2 — the data is stored correctly and
completely. They are conventions nobody has written down yet, and the
place to write them down is the G3 pre-registration, next to the benchmark
and the fold structure.

---

## 4. Fundamentals: what resolves, what fails loudly, what F5 must know

E1's three hand-curated per-ticker maps are gone. E2 ingests **30 tags
across 14 concept families** and runs a five-state classifier per
(company, family) pair. Resolution is deliberately conservative: a pair
that cannot be resolved **fails loudly and never becomes a series**.

Final profile over **3,416 (cik, family) pairs** (segment 3, attempt 3 —
0 GETs, fully cache-warm; identical to attempt 2, which had already matched
the pre-committed prediction on all 3,416 pairs with 0 differing rows.
Attempt 3 added the S4-side red-team fixes below and **changed zero
resolution states**):

| state | pairs | resolved? |
|---|---|---|
| SINGLE | 2,355 | yes |
| DOMINANT | 489 | yes |
| MIGRATION | 75 | yes |
| OVERLAP | 8 | **no** — genuine ambiguity |
| ABSENT | 342 | **no** |
| PARTIAL | 147 | **no** — union below the 75% coverage bar |
| **UNRESOLVED total** | **497 of 3,416 (14.5%)** | each emitted as its own FATAL row |

Every one of the 497 is a per-pair FATAL row naming the company, the
family, the reportable-quarter span, the per-tag coverage and the reason
(`validate_universe(): 532 problem(s) found — 497 FATAL / 14 WARN / 21
INFO`, `s6_segment3_fundamentals_attempt3.log:285`; the full table is
`data/f2/concept_resolution.csv`). They do not stop the run — the parquet
is written and the resolution CSV is what F5 must consult before building
any series.

**Three things the resolution CSV now records that it did not before**
(added after the red-team pass; `F2_SPEC.md` §11 amendment A11 — the CSV
goes from 8 to **11 columns**, and **no resolution state changed**):

- **`unit` and `units_mixed`** — the dominant unit of the rows each
  resolution points at. This is what surfaced Enbridge (§0d): **one member,
  13 families in CAD**, with a standing `fundamentals_non_usd_reporting`
  WARN each. Detection is an ISO-4217 *shape* test, so an unknown
  three-letter code warns rather than passing quietly.
- **`duration_mix`** — quarter bucketing is by `period_end` alone, so an
  annual or year-to-date fact counts toward the quarter it ends in. That
  semantics is unchanged (coverage asks whether a concept was disclosed for
  a period, not at what frequency), but each row now carries its
  `instant / Q / H1 / 9M / FY` profile and the docstring states that a
  resolution promises **neither a unit nor a duration**. Measured at 244
  scale, zero resolved pairs lack a quarterly-length or instant fact.
- **`companyfacts_tail_lag`, a new independent check** — the coverage
  denominator and the staleness anchor are both defined by the company's
  own data, so a companyfacts document truncated at the tail would score
  100% with no alarm. The new check counts in-window 10-K/10-Q filings
  filed *after* a member's last fundamentals fact: **WARN at ≥2 behind,
  INFO at exactly one.** Measured: **1 WARN — Citigroup (831001), 2
  filings / 167 days behind while scoring 0.9767** — and **21 INFO**, the
  ordinary 82–92-day propagation lag of the most recent quarter. It changes
  no state; it makes the blind spot loud. **Re-fetch companyfacts before
  trusting Citigroup's latest quarters.**

**The sector-concentration BLOCKER table is EMPTY** — no (sector, family)
cell is above 20% UNRESOLVED once the exemption ledger is applied. That
deserves a deliberate read rather than relief: **four exemptions suppress
27 cells**, so four of the fourteen families can no longer raise a
blocker at all, and the alarm's remaining value rests on someone reading
the ledger and the 497 per-pair rows. The ledger is printed under the
(empty) table on every run, whether or not it fires, with each entry's
reason. All four fire; none is dead.

| exemption | cells suppressed | worst cell | reason (measured) |
|---|---|---|---|
| `(*, liabilities)` | 6 | energy 18/32 = 56% | Total liabilities is ABSENT-dominated for 21–56% of members in 7 of 8 sectors — a filer-taxonomy choice, not a gap. **F5 note: derivable as `liabilities_and_equity − equity`**, both of which resolve far more widely. That derivation is F5's call, made in the open, which is why the tags stay in separate families. |
| `(*, minority_interest)` | 8 | tech 34/42 = 81% | `MinorityInterest` exists only for a filer with non-wholly-owned subsidiaries; its absence is company structure, not a gap. |
| `(*, net_income_to_common)` | 8 | industrials 17/19 = 89% | Differs from net income only when preferred dividends exist; most filers have none. |
| `(*, operating_income)` | 5 | financials 23/37 = 62% | E1's HANDOFF §2a trap (a) generalises well past banks — MEASURED at 244 scale: energy 31%, materials_realestate 29%, healthcare 25%, industrials 21%. **F5 note: treat `operating_income` as a NON-UNIVERSAL feature**; `pretax_income` is the resolving fallback family. |

Nearest cells to the 20% line, all below it and all still loud per pair:
`tech`/`financials` `shares_outstanding` at 19%, `consumer` 18%,
`materials_realestate` `pretax_income` 18%.

**Left unfixed and firing, deliberately:**

- **The 8 OVERLAP cases** — Apache (revenue), Becton Dickinson (operating
  cash flow), General Dynamics (revenue), Halliburton (cash), Intel
  (cash), Weyerhaeuser (equity), Fiserv (revenue), Crown Castle (pretax
  income). Six of the eight are a filer *alternating* between two tags
  quarter by quarter rather than migrating: the union is complete, but
  neither tag is continuous. A stitching rule would resolve them; it is a
  new rule, so it is parked as a proposal (§7), not slipped in.
- **Multi-class `shares_outstanding`** — 16 members UNRESOLVED, 12 of them
  with zero in-window rows (Alphabet, Meta, Visa, Mastercard, Berkshire,
  Comcast, Ford, CME, Estée Lauder, Snap, Block, Zoom, Palantir, LinkedIn,
  AZEK). Cause: companyfacts publishes only undimensioned facts, and a
  multi-class filer tags its cover-page share count per class. **Not
  fixable by re-fetching** — it needs XBRL dimensional data, which is out
  of F2's scope. Parked, loud, and certain to recur.
- **Three members have a filed span under 8 quarters** (EMC 4, LinkedIn 5,
  Spectra Energy 7 — all acquired mid-window). Their families resolve at
  100% *of a very short span*, which is honest but thin: F5 should read a
  resolution's coverage alongside its span.

---

## 5. Earnings-document (EX-99) selection: the honest version

This is the part of F2 where a real, systematic error was found, and it
was found by a human read, not by the pipeline's own confidence scoring.

**What happened.** The mandatory manual read of the worst-20 flagged CIKs
returned **17 CORRECT / 2 WRONG / 1 AMBIGUOUS**
(`data/f2/status/S6_ex99_manual_read.md`). One of the two WRONG was not
noise:

> **Prologis (CIK 1045609) picked the wrong exhibit systematically.** Its
> EX-99.1 is the *Supplemental Information* data package; the press
> release is EX-99.2. The read measured **39 of its 45 earnings-8-K
> selections with no press-release language at all — and 37 of those were
> HIGH confidence.** Only 2 had been flagged low; the read caught this by
> luck, not by design.

That falsifies the implicit assumption that the confidence label tracks
correctness. **Anything downstream that reads "high confidence" as "no
need to look" is wrong.** After content re-verification the corrected blast
radius is **42 of 45** (the split date moved one filing earlier, to
2016-04-19, because that filing's "Earnings Release and Supplemental
Information" title turned out to be a template leftover: one
release-language hit in 113,158 characters, and it was the title itself).

**What was done about it (six changes, all main-session build rulings):**

1. A single **named per-filer handler** for Prologis (EX-99.2 from
   2016-04-19), deliberately *not* a general "prefer the exhibit that
   reads like a release" scorer — that would re-open all ~10,500
   currently-correct picks.
2. A new evidenced, load-time-validated override file
   `data/f2/earnings_doc_overrides.csv` — **4 rows at this stage, 9 by the
   end** (the four B1 singletons and the Pioneer exclusion joined it; final
   state: 9 rows, 9 fired, 0 dead, of which 2 are exclusions):
   NVIDIA `0001045810-19-000168` (release typed `EX-95.1` by filer typo),
   ONEOK `0001039684-15-000073` (`EX-95.1`), Micron `0000723125-19-000172`
   (`EX-99..1`, double dot) → select the real release; AT&T
   `0000732717-19-000048` → exclude (the filing genuinely contains no
   release; the real one is in the same-day sibling accession). ONEOK's
   and Micron's pre-override picks were the **8-K cover page** — 3,179 and
   3,499 characters of SEC boilerplate — at HIGH confidence, invisible to
   every prior trigger. The EX-99 type family was **not** widened; that is
   how one filer's typo becomes a corpus-wide silent mis-pick generator.
3. **P3**, a loud WARN when an index row *described* as a press release is
   typed outside the EX-99 family. It found ONEOK and Micron within minutes
   of existing. **Its reach is narrower than its own docstring implies**
   (S7 finding **B7**): its 3 hits are 3 hits *for that trigger*, not 3
   instances of the defect class. The class — an earnings exhibit whose
   type string falls outside `^EX-99(\.\d+)?$` — is **38 filings**; P3 sees
   only the ones whose filer happened to write a descriptive description.
   The 14 filings in the B1 defect below have descriptions like
   `EXHIBIT 99..1` / `EX-99.1` / `EXHIBIT 1`, so P3 is blind to all of them.
4. **P1**, a confidence-only fix (read the exhibit sub-number out of the
   description column): 11 low-confidence rows upgraded, **0 pick changes**.
5. **P5**, a thin-exhibit WARN: **50 `ex99_thin_exhibit` rows in the DB
   over 49 distinct documents** under 1,500 characters of extractable text,
   **12 of them under 100** (the ±1 is a boundary case from an extra
   `.strip()` in the pipeline screen, explained in
   `S6_ex99_manual_read.md` §V.4; the red-team's independent recount over
   the 10,568 cached documents returns 50/12, matching the DB). **Measured
   before the B1 fix and not re-measured after it** — the 15 changed picks
   were cover pages of 2,260–4,231 characters replaced by longer releases,
   so none of them was in the thin class either way, but the count itself
   is the pre-fix one. Contents: image-only slide wrappers
   (Linde, PNC ×7, MetLife, Ford, Digital Realty) and one genuinely empty
   exhibit at the source (Cigna, 454 bytes). The selections are defensible
   (they are the only EX-99 present) but the resulting sections will be
   empty or near-empty. **These SHOULD fail F3's `MIN_SECTION_WORDS`
   floor** — named here so a future recalibration has to argue past them
   rather than around them.
6. **P6**, the generalisation of what caught Prologis: a corpus-wide,
   per-CIK release-language screen flagging any CIK whose high/medium
   picks mostly lack release language. This is the check that would have
   caught Prologis without a manual read. Its scope was later narrowed to
   ignore the leading 200 characters (a document whose only release
   language is its own title must not pass) — a **scope change, not a
   threshold move**.

**Where it landed — FINAL.** Segment 1, attempt 11, 0 GETs
(`s6_segment1_metadata_attempt11.log:292-330`), reconciled against
`data/f2/ex99_selection_audit.csv`:

| | final |
|---|---|
| earnings 8-Ks seen | **10,569** |
| **unresolved** | **0 (0.00%)** — was 400/10,569 (3.78%) at attempt 1, which correctly tripped the 1% FATAL ceiling. Reached here *through* four printed refusals that evidenced override rows then resolved (below), not by lowering a bar. **Still read the metric narrowly:** it counts a filing as resolved whenever a document was picked, so on its own it can never see a wrong-document class — B1 and PSEG were both invisible to it. |
| excluded by evidenced override | **2** (AT&T, Pioneer 2018-04-09 — INFO, kept out of the unresolved rate and the sector-coverage denominator) |
| `EX99_PRESS_RELEASE` high / medium / low | **10,312 / 26 / 19** |
| `8K_BODY` high | **210, across 55 CIKs** (was 225 across 60 — the 15 B1 filings left this class) |
| earnings-document overrides | **9 rows, 9 fired, 0 DEAD** — 7 `select_document`, 2 `exclude` |
| P6 release-language screen | **10,548 measured, 0 uncached**; **379** selections lack release language; **1 flagged CIK** (Netflix) |
| deck-title screen (new) | **0 deck-shaped selections across 0 CIKs** |

Totals reconcile: 10,312 + 26 + 19 + 210 + 2 excluded = **10,569**.

**The one P6 flag is Netflix (CIK 1065280), 25 of 47 = 53%, and it is
benign — reported, not suppressed.** Every Netflix selection is the
correctly picked EX-99.1 "LETTER TO SHAREHOLDERS" (25k–37k characters,
opening "Fellow shareholders,"). Netflix simply does not write
press-release prose. **The threshold was deliberately not moved to hide
it**, and it did not move under the P6 scope fix in either direction.
Prologis is clean post-fix: **45 measured, 0 missing** (an earlier draft
said "0 of 44", which was the pre-regeneration base — S7 finding **B20**).

**But "1 flagged CIK" overstates what P6 clears, and the run now says so
itself.** P6 is a per-CIK *majority* test, so a filer wrong on a large
minority of its filings is invisible by design: **379 of the 10,548
measured selections carry no release-language marker**, and only Netflix's
25 are named by the flag. After S7 finding **B6**, the audit CSV carries
`release_language_missing_share` for **every** CIK rather than only the
flagged one, and the run prints a **WATCH LIST** of CIKs at or above 40%
but under the 50% bar, each labelled *"not flagged, one systematic
mis-picker can sit here indefinitely"*. **The flag threshold was never
moved** to catch them; the just-below-threshold reporting line this report
proposed for the fundamentals blocker table (§7 item 3) exists for P6
instead — and it paid for itself immediately, because **reading the watch
list in order is how the PSEG defect was found** (below).

The list now holds **one name: Pioneer Natural Resources, 37/76 = 48.7%**
(`…attempt11.log:300-301`) — ruled on above but not otherwise re-read.
PSEG left the list by being fixed, not by being re-scored. And after PSEG,
a P6 pass is not weak evidence so much as **no evidence**: a filer can pass
on contact-slide boilerplate while being 45/45 wrong.

Content re-verification (extraction-qa, on real cached bytes, 0 GETs):
**PASS**. All five ruled filers confirmed by reading the actual documents;
the final distribution reconciles with the run log with zero residue;
10,568 of 10,568 selections have a cached document.

**The unread `8K_BODY` tail is where a real defect was hiding (S7 findings
B1/B2).** An earlier draft of this report offered, as a prior, that the
unread tail was "probably fine" because all ten `8K_BODY` filings that were
read had no `EX-99` string in their index. **That prior is wrong, and it
was checkable offline in seconds.** The red-team ran the check:

> **19 of the 225 `8K_BODY`/high selections have an unselected, non-8-K,
> non-graphic document row in their own filing index, and 14 of those rows
> are release-shaped.** In those 14 filings the stored "earnings document"
> is the **SEC Form 8-K cover page** — long enough (2,260–4,231 characters)
> to survive F3's word-count floor, so the labeler would emit sentiment,
> guidance and red-flag labels for a checkbox page.

Three were verified by reading the stored document itself, and each one's
own Item 2.02 says the release is elsewhere: Aon `0001628280-15-005672`
(2,260 chars, *"A copy of the Press Release is attached hereto as Exhibit
99.1"*), Illumina `0001110803-16-000185` (2,827 chars), HPE
`0001645590-17-000006` (4,231 chars). The affected filers are Aon,
Illumina ×2, Biogen, Pioneer ×2, HPE, Vistra ×3, Kraft Heinz, Zoom, Texas
Instruments, and CIK 1596532.

**Why every guard missed it:** P5's floor is 1,500 characters and these are
above it; P3 needs the *description* to say "press release" and these say
`EXHIBIT 99..1` / `EX-99.1` / `EXHIBIT 1`; P6 is a per-CIK majority test;
the confidence label is `high` by construction; and the 1%
`earnings_doc_unresolved` ceiling counts a cover-page pick as *resolved*.
The class also includes a dialect no handler covers (`EX-1`/`EX-2`, 4
filings).

**How it was fixed, and how it ended.** The fix is a **conditional
fallback, not a widening of the EX-99 type family**: the malformed types
still never win the normal selection ladder; what changed is what happens
*before* settling for the 8-K body. The policy now looks at unselected
candidate rows, takes one **only on index/description evidence**, and
otherwise **refuses and counts the filing as unresolved**. The candidate
rule is deliberately narrow — a sub-numbered securities exhibit (`EX-1.1`,
`EX-2.1`, `EX-10.1`) is not a candidate — so Dominion, Emerson, Danaher,
Marathon and MPLX keep their `8K_BODY` picks untouched.

**Result: 15 pick changes, and 0 filings left unresolved**
(`S3_metadata_documents.md` §12.8–§12.9, `F2_SPEC.md` §11 amendment A9):

| how it resolved | n | who |
|---|---|---|
| **candidate screen**, at **medium** confidence (the index confirmed which row was the release) | **11** | Aon 2015-07-31, Biogen 2017-04-25, Vistra ×3 (2017-05-18 / 2017-08-04 / 2018-02-26), Pioneer ×2 (2017-08-01 / 2018-04-09), Zoom 2019-12-05, Texas Instruments 2020-01-22, Arista 2020-05-05, Linde 2022-04-28 |
| **evidenced override row**, at high confidence (the index did *not* confirm — each was refused first) | **4** | Illumina ×2 (`0001110803-16-000185`, `0001110803-16-000194`), HPE `0001645590-17-000006`, Kraft Heinz `0001637459-19-000050` |

Those four all describe their release row `EXHIBIT 1` — no self-label as
exhibit 99, no release-shaped wording — so nothing in the index could
confirm the pick. **The final run still prints the refusal for each one**
(`s6_segment1_metadata_attempt8.log:211-277`: *"Refusing to fall back to
the 8-K body at high confidence"*) and the evidenced override then supplies
the document. That is the sequence worth seeing: the screen refuses, a
human ruled, and the override file carries the ruling — which is why the
counted rate reads 0/10,569 without anything having been guessed. A 15th
case the red-team's own table had missed also turned up and is now
resolved: Linde `0001654954-22-005503`, typed `EX-95.1`, described
`EX-99.1`.

**The HPE case is why override rows must verify the exhibit map, not the
count.** S3 declined to take "the sole unselected candidate" on faith —
and HPE has **two** candidates, with **the red-team's table naming the
wrong one**: `pressrelease112117.htm` is the **Item 5.02** document, the
Antonio Neri CEO-appointment announcement. The cover page maps its own
exhibits: Item 2.02 attaches the segment-results release as **Exhibit
99.1** (`ex-991x10312017x8k.htm`), Item 5.02 furnishes the Neri release as
Exhibit 99.2. Taking the named filename would have stored a management
announcement as the earnings text — the same defect class B1 exists to fix
— and a test now pins that the pick is not the Neri document
(`S3_metadata_documents.md` §12.9).

Two consequences worth stating plainly: the ONEOK and Micron override rows
are now **redundant for selection** (the general screen reaches the same
documents at medium; the rows still fire and carry them to high, and they
hold the content verification, so they stay); and **future filings of this
shape stay loud-UNRESOLVED** — the mechanism absorbed four measured
singletons, the policy did not change, and a test pins that.

**And one of those 11 resolutions was itself wrong — Pioneer 2018-04-09,
now the 9th override row and the 2nd exclusion.** The content check found
that `0001193125-18-111008` resolves to an **IPAA Oil & Gas Investment
Symposium slide deck** (36,577 characters, zero hits for "first quarter
2018", "1Q18", "today reported" or "press release"), furnished under a
conditional Regulation-FD Item 2.02 wrapper — *"the portions, **if any**,
of the Investor Presentation"* — with Item 7.01 carrying the substance.
Stated in the override's own reason, in those words: **the fix made this
one filing less honest.** Pre-fix it claimed `8K_BODY`, which is true of a
cover page; post-fix it claimed `EX99_PRESS_RELEASE`, which is false of a
slide deck. It is not a mis-pick — the filing has no better candidate — so
the disposition is an evidenced exclusion, not a policy change, and a test
pins that the policy still resolves it, so the exclusion is visibly a human
ruling layered on top (`S3_metadata_documents.md` §12.10; `F2_SPEC.md` §11
amendment A13).

### The PSEG defect — the capstone of the manual-read arc

The watch list that came out of the P6 scope fix was then read in order,
and its next-worst unexamined name turned out to be **the largest
single-filer content defect in F2**.

> **PSEG (CIK 788784, utilities / extension): all 45 of its earnings
> selections were the earnings *conference-call slide deck*, every one at
> HIGH confidence.** The documents open *"PSEG Earnings Conference Call
> &lt;quarter&gt;"* (2015–2021) or *"Financial Results Presentation"*
> (2022–2026) straight into forward-looking-statement boilerplate, with
> 37–46 per-slide GRAPHIC rows in the index. **The real press release sits
> unselected at bare `EX-99` in every one of the 45.**

Root cause is the same shape as Prologis, one rung lower: the exhibit
ladder prefers a sub-numbered `EX-99.1` over a bare `EX-99`, and the
description tie-break cannot help because both descriptions are
content-free — literally `"EX-99"` and `"EX-99.1"`. Every filing is
`items=2.02,7.01,9.01`, the standard utility pattern (release under 2.02,
call deck furnished under 7.01), and the policy took the 7.01 artifact.
This is the **third independent confirmation that selection confidence does
not track correctness** (`S6_ex99_manual_read.md` §W ADDENDUM).

What was ruled and built in response — the arc is worth seeing, because it
is how a spot read is supposed to end:

1. **A named per-filer handler**, not a blanket rule. The tempting fix is
   to flip the ladder's bare-vs-sub-numbered preference corpus-wide. The
   census below shows that would have been a gamble: **ConocoPhillips has
   the same two-candidate index shape and is already correct** — it selects
   its bare `EX-99`, whose bytes open *"ConocoPhillips Reports First-Quarter
   2017 Results"*. **The shape alone is not the defect**, so a blanket flip
   would have broken a correct pick to fix a wrong one. Replay: exactly 45
   pick changes, PSEG only.
2. **A deck-title screen**, generalising what the read measured: a title
   naming a conference-call deck flags the selection regardless of body
   text, with no majority test and no minimum sample, because unlike
   missing release language there is no benign share of decks. Its markers
   are measured, not guessed — a generic `"conference call"` marker was
   **tested and rejected** (93 hits across 11 CIKs, including 45 Texas
   Instruments releases that merely name the call), and the corroboration
   requirement exists because of a **real false positive**: Danaher
   `0000313616-20-000081` is a genuine release headlined *"… AND SCHEDULES
   FIRST QUARTER EARNINGS CONFERENCE CALL"*. Title-only flags
   `{PSEG 45, Danaher 1}`; title-plus-deck-boilerplate flags `{PSEG 45}`
   exactly. **Corpus result now: 0 deck-shaped selections across 0 CIKs.**
3. **A two-candidate-shape census, so the class is enumerated rather than
   sampled.** Roster: 2 filers, 46 filings — PSEG 45 (fixed) and
   ConocoPhillips 1 (true negative, no action). A methodology note worth
   keeping: the census was run two ways and they disagreed — keyed on the
   description-aware exhibit type it finds 1 filer, keyed on what the
   ladder *actually* orders on it finds 2. **The second is the correct
   denominator**, and a single-pass census would have missed ConocoPhillips
   and reported a cleaner roster than the truth.

The build trail for all three is `S3_metadata_documents.md` §12.11 and
`F2_SPEC.md` §11 amendment A14; the read that started it is
`S6_ex99_manual_read.md` §W ADDENDUM.

Post-fix, PSEG's release-language-missing share falls from **21/45 (46.7%)
to 3/45 (6.7%)** and it leaves the watch list entirely
(`ex99_selection_audit.csv:128`). The newly selected releases were fetched
by segment 2's delta 4 (45 documents, 0 failed) and go to extraction-qa for
content verification on real bytes, the same standard every other ruled
filer met.

**The caveat this defect leaves behind, and it is the important one: the
watch-list share is a FLOOR, not an estimate.** All 24 PSEG filings that
"passed" the release-language screen passed on the marker
`"investor relations"` alone — a contact slide deep in the deck, not
release prose. A 46.7% missing share understated a 45/45 defect. **Every
filer below the watch-list bar is unmeasured for this class, not clean.**

**What the manual read does NOT cover — state this, don't imply coverage:**

- The read was **capped at the worst 20 of 71 flagged CIKs; 51 were not
  read** and are not cleared by anything in this report. It covered all 10
  CIKs carrying any low-confidence selection, but only 10 of the 62
  `8K_BODY` CIKs — so **52 of 62 8K_BODY CIKs and 217 of 227 8K_BODY
  filings were unread**. **The final worklist is 57 CIKs, of which the run
  log names the 20 worst and 37 stay uncovered**
  (`…attempt11.log:309-330`). The unread tail is not a low-risk residual:
  it is where B1's 15 filings lived, and it has still not been read. Note
  also that **PSEG was never on this worklist at all** — its 45 wrong picks
  were `EX99_PRESS_RELEASE`/high, which no §4.4 trigger looks at. Three
  passes of spot-reads do not add up to coverage.
- **`medium` confidence is not a worklist trigger, and there are 26 of
  them.** 16 belong to one filer (CIK 72741 Eversource, which files the
  release, the financial report and the slide deck all as bare `EX-99`);
  the other 10 are the surviving B1 candidate-screen resolutions (the 11th
  became the Pioneer exclusion). None of the 26 is on the §4.4 worklist.
  The Eversource 16 have never been read by anyone; the 10 were verified in
  the post-B1 content pass.
- The 8-sector high-confidence **coverage** assertion passed (verified
  three ways, 0 problems), but it is a coverage assertion, not a
  correctness one: Prologis sat inside a sector that passed with over a
  thousand high-confidence selections while making 42 wrong picks.
- **Not every item-2.02 8-K is a quarterly earnings release.** Six of the
  20 filings read are item-2.02 8-Ks that are something else (monthly
  orders, a guidance raise, a non-GAAP presentation change, a
  tax-reform impact, a legal accrual). Selection was right in all six; the
  loose thing is the corpus assumption. Also measured: **61 (CIK,
  filing_date) pairs hold more than one earnings 8-K — 122 filings.** Both
  are F3/F5 inputs (dedup grain, section labelling), not selection defects.

---

## 6. Price provenance, and the AEP wobble

**The Yahoo caveat, restated in full** (canonical write-up:
`data/PRICES_NOTES.md` §1; raised in chat 2026-08-24 as
`EXPANSION_PLAN.md` §6 requires): every price row in
`data/prices_e2.parquet` comes from Yahoo Finance's free, keyless chart
endpoint — the same one `yfinance` uses. Stooq, which your 2026-08-18
target ratification named by example, has been bot-gated site-wide since
that day (a JavaScript proof-of-work challenge plus `Disallow: /` in
robots.txt); solving that challenge was deliberately not attempted.
**Yahoo's robots.txt also disallows automated access and it has no
published terms for this use.** E2 grows the exposure roughly 4–5× over
E1 (213 tickers vs 25), though volume stays modest and cached. The parquet
schema is source-agnostic (`source` column), so swapping providers later
costs only a re-ingest.

**Two adjustment caveats, not one.** Prices are split-adjusted, **not**
dividend-adjusted — E1's residual cross-sectional-yield limitation carries
into E2 unchanged. And the split adjustment is applied **as of the fetch
date**, which is a level-side look-ahead (S7 finding **B14**): a 2016 close
in this parquet is restated by every split that happened *after* 2016.
Returns are invariant to this, so return features are unaffected — but any
**level-based** screen (absolute price bands, price thresholds,
penny-stock-style filters) would be retroactively informed by the future.
Do not build one on these levels without saying so.

**The AEP wobble, and why it needed a ruling.** During segment 1's cache
refresh, EDGAR's `submissions.json` for CIK 4904 (American Electric Power)
dropped to an empty `tickers[]`/`exchanges[]`. The submissions-only rule
censored it, and two pinned count tests failed — **the tripwire doing its
job, not a regression.** A live single-GET probe from the main session
confirmed EDGAR has not self-healed, while SEC's own bulk
`company_tickers.json` maps `AEP → 4904` and AEP is a listed,
actively-filing current member. Ruling: a second evidenced override row
(4904 → `AEP`), because censoring a live mega-cap over an upstream data
wobble would be the larger error.

Note the direction of the evidence, which is the safety argument **for
this row**: the bulk symbol points at **our** CIK (agreement). The APC/EMC
trap is the opposite — the symbol points at a **different** CIK.

**A false safety property was retracted, and the gap is now closed (S7
finding B3 — CLOSED).** An earlier draft of this report, the override
file's own comment block and `F2_SPEC.md` amendment A3 all said that the
different-CIK case "is still censored, never overridden." **That was not
true of the other override row.** `company_tickers.json` maps `XOM` → CIK
**2115436** ("ExxonMobil Holdings Corp") while our member is **34088**,
which is absent from the bulk map — structurally the same shape as the APC
trap. Worse, no code checked *why* a member had censored before applying an
override, and the wobble WARN skipped CIKs with no bulk symbols of their
own, so **XOM never WARNed while AEP — the safe direction — WARNed every
run.** Backwards.

The corrected rule, now enforced in code and stated in all three places
(`S5_prices.md` §9; `F2_SPEC.md` §11 amendment A10):

> bulk-symbol-maps-elsewhere is the trap **signature**, not a
> disqualifier by itself. An override over it requires (a) a ratified
> `successor_reorg=true` marker on the row, (b) a series-continuity check
> against the fetched prices, and (c) a standing per-run WARN. Absent any
> of the three, the member stays censored.

Measured outcomes: **XOM now WARNs on every run**
(`override_symbol_bulk_maps_elsewhere`, naming both CIKs and quoting the
row's evidence) and AEP keeps its own WARN; the continuity check passes
with the numbers printed rather than asserted — **14,282 rows,
1970-01-02 → 2026-08-24, largest gap 7 calendar days, zero gaps over 10
days**, against failure shapes of 6 rows (EA's purged stub) and a late
start (ARKO begins 2020 while Anadarko was a member from 2016). No count
moved: both pairs are unchanged.

**What is still not established, recorded rather than papered over:** there
is **no cached `submissions` document for CIK 2115436** in this repo, so
the holding-company story itself rests on SEC's bulk map plus the
continuity measurement — not on a primary filing. E1's prior
`universe.csv` mapping is corroboration, never evidence about the
reorganisation. The evidence row now says exactly that.

A related surface stays open and is stated, not implied safe (S7 **B12**):
"absence from the bulk map never censors" is the residual APC path.
Exactly one member ever took it — EA — and it was caught by a *coverage*
tripwire, not an identity one; a reassigned symbol with a long history
would have passed `meta.symbol`, `instrumentType` and the late-start check.
The new continuity check closes this **only** for successor-reorg
overrides. And (S7 **B13**) the parquet stores full history with no
per-CIK validity floor — DuPont (CIK 1666700) carries `DD` back to
1972-06-01, history belonging to the old E. I. du Pont — so **every
downstream price read must clip to `[coverage_start, coverage_end]`.**

A new WARN
(`submissions_ticker_missing_but_bulk_has`) now names every member of this
shape on every run, *including one already covered by an override*, so the
wobble stays visible rather than disappearing behind its fix.

Exactly **two** members are wobble-shaped, and only one was actioned:

| CIK | member | disposition |
|---|---|---|
| 4904 | American Electric Power | **override added** (evidenced) |
| 30554 | EIDP, Inc. | **stays censored — correct.** Every symbol SEC maps to it is a preferred series (`CTA-PA`/`CTA-PB`); it has had no public common equity since the DowDuPont reorg. An override would pull a preferred-share series into an equity-return backtest. |

No third case exists. Rule-level counts are 211 resolved / 33 censored
with 2 evidenced overrides (XOM, AEP); the **fetch pair is unchanged at
213 / 31**, and the census delta is still exactly the pre-registered
−{34088}/+{30554}.

Price validation ran **0 FATAL / 3,003 WARN / 0 INFO**. The WARNs are
dominated by full-history return outliers that are real market events
(October 1987, March 2020, Constellation Energy 2024) — the series go back
decades, and a 15% daily-move bound fires on genuine history. The two
tripwire findings that were *not* noise are EA (§2) and GLD (§0a).

---

## 7. Parked proposals — deliberately not implemented

Each of these was measured, argued, and left alone. They are proposals for
a later ruling, not defects, and nothing depends on them.

1. **P4 — a distinct `EX99_FINANCIAL_SCHEDULES` section type.** Today a
   filing whose only EX-99 is a tables-and-schedules exhibit gets typed
   `EX99_PRESS_RELEASE` and looks clean. Ruled OUT for F2 and **parked to
   the F3 handoff**, because a section-type taxonomy change touches F4
   labeling applicability, which `EXPANSION_PLAN.md` §5 says is extended
   only deliberately.
2. **Stitching interleaved substitutes** — would resolve 6 of the 8
   OVERLAP cases (filers alternating between two tags rather than
   migrating). A genuinely new rule, so it is a proposal, not an edit.
3. **A "cells just below threshold" report line.** Ruling 4 of the
   244-scale calibration expected the multi-class `shares_outstanding`
   blockers to keep firing; measurement says they no longer clear 20%
   (19% / 19% / 18%). No blocker was manufactured to match the
   expectation. If those cells should stay visible at run level, the
   honest mechanism is a just-below-threshold line, **not** moving the
   threshold.
4. **A thin-span flag** for members whose filed span is under ~8 quarters
   (§4). Recoverable today from the FATAL messages and the run report.

Also parked, and listed rather than papered over: the dimensioned-facts
gap behind multi-class `shares_outstanding` (§4).

---

## 8. How this was verified

**Final full test-suite gate: 815 passed / 0 failed / 5 skipped**
(2026-08-24, main session, after every red-team fix and the final
regeneration; the 5 skips are pre-existing. Predecessors: 731 mid-F2, 797
after the B1 round. **Note:** the 815 figure was reported by the main
session at the close of the final regeneration; `data/f2/status/S6_runs.md`
still ends at the 731 gate, and its closing entries are being written.)
The suite grew from a measured 399-collected baseline at S1 through every
stage; tripwires were re-pinned, never deleted, and no test was weakened to
make a suite pass — where the red-team fixes broke existing tests they were
**repaired through the gate, not around it** (S2's eight synthetic
exception-row tests now ratify exactly the pairs they write, and the
"malformed types stay outside the family" test was rewritten to assert both
halves of the corrected rule). Per-stage targeted counts at each completion
report: S2 +45 (suite 444 collected / 439 passed), S3 **258 passed**, S4
100 passed then extended for the A11 additions, S5 **104 passed**.

Discipline that held throughout: every stage's code work ran with **zero
live network GETs** (cache-only clients that raise on a cache miss), all
network traffic happened in main-session background tasks as an
auto-resume chain, and every command is idempotent and cache-first — the
final segment-1 re-runs cost 0 GETs and the segment-3 re-run cost 0 GETs.

**Validation results, as run:**

| check set | result |
|---|---|
| universe / metadata (`validate_universe`, 244 members) | **0 FATAL / 5 WARN / 29 INFO** |
| — the 5 WARNs | fiscal-calendar filing gaps: PepsiCo ×2 (139 d, 136 d), Gen Digital 266 d, Kraft Heinz 217 d, Discover 145 d — all under the 300-day FATAL bar |
| — the 29 INFOs | `member_stopped_filing` — exactly F1's independently derived 29 delisting/acquisition exits. **Expected states, not failures.** |
| evidenced exceptions file | **ships empty**, as predicted; there is no blanket override — every FATAL hard-fails the run |
| fundamentals | **497 FATAL** (one per UNRESOLVED pair) / **14 WARN** (13 Enbridge non-USD families + Citigroup's companyfacts tail lag) / **21 INFO** (one-filing tail lag); sector-BLOCKER table empty under a 4-entry ledger |
| prices | 0 FATAL / 3,003 WARN / 0 INFO at the segment-4 run; the post-fix offline re-run reports 0 FATAL / 3 WARN / 2 INFO on the resolution side (XOM's new trap-signature WARN, AEP, EIDP; XOM's continuity INFO, EA's distress INFO) |
| EX-99 earnings-doc resolution | **0 unresolved (0.00%)** against a 1% FATAL ceiling that was left untouched, reached through 4 printed refusals resolved by evidenced override rows — **but this metric counts a picked 8-K cover page as resolved**, which is why it was blind to the B1 class (§5) |

**Every stage's completion report** (each states what was done, what was
verified, exact paths touched, and how to re-run):

| stage | report |
|---|---|
| S1 — recon + spec | `data/f2/status/S1_recon.md` → `data/f2/F2_SPEC.md` (+ §11 amendments **A1–A14**, a clean unique sequence — three of them carry a dated note recording that the main session renumbered them off a duplicate label taken by two agents concurrently; A9 and A10 sit out of numeric order in the file) |
| S2 — membership, window constants, validation redesign | `data/f2/status/S2_membership.md` |
| S3 — metadata + documents at scale | `data/f2/status/S3_metadata_documents.md` |
| S4 — fundamentals classifier | `data/f2/status/S4_fundamentals.md` |
| S5 — prices at scale | `data/f2/status/S5_prices.md` |
| S6 — the four ingestion runs | `data/f2/status/S6_runs.md` (+ `S6_seg1_ex99_diagnosis.md`, which now carries a dated correction scoping its "0 genuine selection failures" claim to the 400 filings it examined, and `S6_ex99_manual_read.md`). **Its per-segment entries stop at the pre-red-team state**; the final runs are the logs themselves — `s6_segment1_metadata_attempt11.log`, `s6_segment2_documents_delta4.log`, `s6_segment3_fundamentals_attempt3.log` |
| S7 — independent red-team pass over S2–S6 | `data/f2/status/S7_redteam.md` — **complete; read it alongside this report** |

Raw run logs, durable and inspectable: `data/f2/s6_segment*.log`.

**What the red-team pass changed in this report.** It re-derived every
headline from the artifacts rather than trusting any agent's self-report,
and confirmed as sound: the 45,632 enumeration and its 45,545 + 87 split,
all 3,416 fundamentals resolutions (0 disagreements against a from-scratch
reimplementation of the classifier), the universe checksums and membership
PIT cleanliness, EA as the sole no-coverage member, P5/P6 reproducing, all
four earnings-doc overrides firing, and the 731/5/0 test gate re-run in
61 s. It also found two HIGH defects — **both now fixed and re-run**: the
cover-page selections (B1/B2, §5, closed by the conditional fallback plus
evidenced override rows) and the XOM override's missing guard (B3, §6,
closed by the successor-reorg marker, the continuity check and a standing
WARN). Its B6 fix — the per-CIK watch list — then led directly to the
PSEG defect and its handler, deck screen and census (§5), which is the
largest content correction in F2 and would not have been found without it.
Beyond those it flagged a set of places where a number travelled without
its measurement or a claim outran its evidence — the panel-time censoring profile (B4, §0c), the
current-SIC look-ahead reaching membership (B9, §9 item 12), the
bankruptcy dates (B10, §1/§3.1), the point-in-time conventions (B8, §3.3),
the split-level look-ahead (B14, §6), the reproducibility rationale (B16,
§1), the XOM override's false safety property (B3, §6) and several
enumerated-vs-stored base mismatches (B20). All are corrected above and
attributed by finding ID. Its remaining findings are code-side items for
their stage owners; the four that also constrain how the corpus may be
consumed are carried as caveats in §9 item 13, and the rest (B12, B13,
B17, B18, B19) are in `S7_redteam.md`.

**What F2 does not establish, stated plainly:**

- **No performance number of any kind exists yet for E2.** F2 ingested
  data; features and the walk-forward backtest are F5, behind gate G3.
- **When E2 backtest numbers do exist, they will be numerically
  incomparable with E1's** — a different benchmark (E1: average over 25
  fixed mega-caps; E2: a membership-dated, churning universe, definition
  still to be ratified at G3). That has to be said wherever both appear.
- **E1's label-quality constants do not transfer to E2.** The 22.2%
  red-flag config-sensitivity, the 63.4% pooled / 75.0% Tier C
  base-rate-representative red-flag agreement, and the ~25% corpus-wide
  red-flag error were all measured on **Claude bootstrap labels** in E1,
  and every one of them is a **model-consensus** measurement (model
  auditor + model adjudicator, with owner judgment concentrated on a
  104-case shortlist) — **not human validation of ground truth**
  (`HANDOFF.md` §3, `RED_FLAGS_LIMITATION.md`). E2's labels will come from
  the fine-tuned student, and **gate G2 re-measures label quality from
  scratch**; carrying E1's constants onto Qwen labels would be silent
  misinformation.
- **The labeler-contamination flag is still owed.** The student was trained
  on E1 text, so on E1-era chunks it will partly replay memorised labels
  and on new ones it will generalise. Every E2 chunk gets a train-overlap
  vs novel provenance flag, and E2 results get reported with and without
  the overlap set (`EXPANSION_PLAN.md` §3.2). That is F4/F5 work; F2 only
  had to not destroy the ability to compute it, and did not.

---

## 9. The caveats that travel with the E2 corpus

Short list, each with its measurement, for anyone quoting E2 results later.

1. **Two censoring numbers, never conflated**: FETCH 213 fetched / 31
   unfetchable (27 core / 4 extension); **OPERATIVE 32 members with no
   usable prices (28 core / 4 extension)** — quote the operative pair with
   every result, benchmark and stratified claim.
2. **…and in membership-time the same censoring is not flat**: 14.0% /
   16.2% / 12.5% of member-date cells in the 2016 / 2017 / 2018 cohorts,
   decaying to 0.0% by 2026; 6.35% pooled over 1,496 cells; energy 16.4%,
   utilities 0%; core 7.7% vs extension 2.5% (§0c). Time-decaying and
   outcome-correlated, so it can make early folds differ from late folds
   for a non-alpha reason. **Quote this beside the CIK pair, always.**
3. **Outcome-side censoring is not fixed and cannot be** (EXPANSION_PLAN
   §2c). EA is the concrete instance: selection stayed survivorship-free,
   the outcome is gone. Delisting remains visible only through
   `distress_events`.
4. **Price provenance**: Yahoo's keyless chart endpoint, robots.txt
   disallows automated access, no published terms for this use; Stooq
   bot-gated since 2026-08-18 and one flag away. Split-adjusted **as of the
   fetch date** (a level-side look-ahead — returns are unaffected, absolute
   price levels are not), and **not** dividend-adjusted.
5. **20,218 of the 45,632 enumerated filings — equivalently 20,165 of the
   45,545 stored `filings` rows (44.3%) — sit outside their CIK's
   membership spells by design.** Say which base you are on; join on
   `universe_membership`, never on presence in `filings`.
6. **87 co-registrant attributions live in a side table** — absence from
   `filings` is not evidence of non-filing. None of the 87 is an earnings
   8-K, so the text corpus is unaffected.
7. **Three point-in-time conventions are unresolved and must be
   pre-registered at G3** (§3.3): the post-close acceptance rule (45% of
   filings are accepted after 16:00 ET on their `filing_date`), the two
   Salesforce filing-date-precedes-acceptance anomalies, and the
   restatement as-of rule (7.3% of (cik, concept, unit, period) groups
   carry more than one value; only `pit.value_as_of()`'s filed-date
   semantics resolve them correctly).
8. **497 of 3,416 (company, family) fundamentals pairs are UNRESOLVED and
   never become series**; `operating_income` is non-universal (use
   `pretax_income`), `liabilities` is derivable but not directly tagged for
   many filers, and multi-class `shares_outstanding` is missing for 16
   members for a reason no re-fetch can fix.
9. **Earnings-document selection has had three high-confidence error
   classes, and confidence scoring caught none of them.** Prologis (42 of
   45, the supplemental package instead of the release), the B1 class (15
   filings storing the 8-K cover page), and **PSEG (45 of 45,
   conference-call slide decks)**. All three are fixed, re-run and
   content-verified — and each was found by a human read or a screen built
   after one, never by the confidence label. The residue: **51 of 71
   flagged CIKs were never manually read and the final worklist of 57 still
   has 37 uncovered**; PSEG was never on that worklist at all; the 26
   medium-confidence picks are on no worklist; the deck screen now reports
   0 across 0 CIKs but is one filing-shape wide; and **the P6 watch-list
   share is a floor, not an estimate** — PSEG passed the screen on 24 of 45
   filings via contact-slide boilerplate while being wrong on all 45. Every
   filer below the watch-list bar is **unmeasured for these classes, not
   clean**.
10. **50 `ex99_thin_exhibit` WARN rows over 49 distinct near-empty selected
    documents** (12 under 100 characters) — they should fail F3's
    word-count floor rather than have the floor lowered to admit them.
    Measured before the B1 fix and not re-measured after it.
11. **E1's label-quality numbers are E1's** (see §8), measured over
    model-adjudicated fields; E2 re-measures at G2.
12. **Sector assignment uses current SIC codes, and the look-ahead is NOT
    confined to the label** (S7 finding **B9**, correcting an earlier
    draft). Membership is a fixed per-sector quota — 20/20/20/20/12/12/20/12
    = 136 at every one of the 11 reconstitution dates — and `sector` is
    constant per CIK across all 11 dates (0 CIKs carry more than one sector
    or SIC), i.e. assigned once from the *current* SIC. So the bucket a
    company competes in at 2016-07-01, and therefore whether it makes that
    date's top-K at all, is decided by its **2026** SIC code. This is a
    design property of the universe rule ratified 2026-08-21, not a build
    error, and it cannot be fixed without re-ratifying that rule. **The
    magnitude is unmeasured** — the artifacts carry only the current SIC, so
    nobody can say how many members reclassified during the window; that
    unmeasurability is itself part of the limitation.
13. **Four fundamentals-consumption caveats, now all surfaced in the
    artifacts** (they were red-team findings B11/B5/B15/B21; the fixes are
    `F2_SPEC.md` §11 amendment A11 and **changed zero resolution states**):
    **currency** — Enbridge's 13 families are CAD against a USD price
    series, carried in the CSV's new `unit`/`units_mixed` columns and a
    standing WARN each; F2 converts nothing (§0d); **tail truncation** —
    the coverage denominator and the staleness anchor are both defined by
    the company's own data, so a truncated companyfacts tail would score
    100% silently; the new `companyfacts_tail_lag` check makes it loud
    (Citigroup WARNs at 2 filings / 167 days behind while scoring 0.9767;
    21 members INFO at one filing behind); **duration** — annual and YTD
    facts count toward the quarter they end in, unchanged by design, now
    recorded per row in `duration_mix`, and a resolution promises neither a
    unit nor a duration; **8-K sourcing** — 12,172 fact rows come from
    8-Ks and are admitted **deliberately** (an earnings release is a real
    dated disclosure of the same GAAP fact), now stated in the code rather
    than implied; measured, zero resolved flow-family pairs depend on them.

---

## 10. Where things are, and how to re-run

| what | path |
|---|---|
| metadata DB (filings, membership, distress events, co-registrants, validation) | `data/filings_metadata_e2.db` |
| documents cache (42 GB; F3 runs at 0 GETs) | `data/raw/documents/` |
| fundamentals | `data/fundamentals_e2.parquet` + `data/f2/concept_resolution.csv` |
| prices | `data/prices_e2.parquet` + `data/f2/price_ticker_map.csv` |
| earnings-doc audit + overrides | `data/f2/ex99_selection_audit.csv`, `data/f2/earnings_doc_overrides.csv` |
| price-ticker overrides (2 evidenced rows) | `data/f2/price_ticker_overrides.csv` |
| validation exceptions (empty by design) | `data/f2/validation_exceptions.csv` |
| the spec and its amendments | `data/f2/F2_SPEC.md` (§11 = A1–A8) |
| the resume ledger | `F2_PROGRESS.md` |

Re-running is cheap and idempotent; the exact per-segment commands are in
`data/f2/status/S6_runs.md`. With the caches warm, segments 1 and 3 cost
**0 network GETs** and simply regenerate their artifacts. The final state
on disk is segment 1 **attempt 11**, segment 2 **delta 4**, segment 3
**attempt 3**, segment 4 unchanged. One thing to know before re-running:
**the corpus is not yet reproducible across days** — the freeze date
2026-08-31 is still in the future, so a re-run may enumerate filings that
did not exist at the last run (§1). Diff the counts; do not assume they
match.

**Known documentation debt, flagged not hidden:** `INGESTION_NOTES.md` and
`README.md` still describe E1's command shapes (including the deleted
`--allow-incomplete-universe`), and `data/PRICES_NOTES.md` §1 still
describes E1's Stooq-first behaviour and its 25-ticker run. All three are
accurate about E1 and stale about E2; they were left for a deliberate docs
pass rather than quietly rewritten mid-ingestion.

---

## §0 OUTCOMES — appended 2026-08-25 (main session, recording the owner's in-chat rulings)

The owner read this report and ruled (canonical record: `HANDOFF.md` §3,
2026-08-25 entry): **(a)** SPDR Gold Trust IS a member — deliberate
retention, entity-type anomaly accepted and documented; **(b)** the
epoch-2 eval-report patch (post-ruled guidance line) ordered executed
before the owner's G1 read — G1 acceptance still pending; **(c)** the
censoring-profile and SIC-look-ahead read-items acknowledged, no action;
**(d)** non-USD fundamentals (Enbridge today) convert to USD as standard
at the feature/analysis layer — FX source and PIT semantics to be
specified and ratified at F5/G3. F3 begins after the owner-commissioned
foundations re-evaluation completes.
