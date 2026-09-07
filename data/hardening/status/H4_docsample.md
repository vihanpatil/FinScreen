# H4 — Doc-selection Tier-C sample (extraction-qa-engineer)

**Status: DONE 2026-08-25.** Brief: `HARDENING_PROGRESS.md` §H4. Source
finding: `data/reevaluation_2026-08-25/decision_audit.md` §2.1 ("the EX-99
arc is SHOULD-REVISIT as a class") and §PART-4's hard deadline row
("EX-99 selection error rate never estimated … hard deadline: F3 start").

**Zero network calls.** Every document read came from `data/raw/documents/`
and every index row from `data/raw/filing_index/` or the read-only
`data/filings_metadata_e2.db` (`mode=ro` URI). No re-downloads.

---

## 0. Headline

| Quantity | Estimate | 95% Wilson CI |
|---|---|---|
| **Selection error — pre-specified base-rate SRS, n=80** | **5.00% (4/80)** | **[1.96, 12.16]** |
| Same, post-stratified by confidence class over all 10,567 | 5.21% | see §5 |
| Same, post-stratified by quarter-multiplicity (lower variance, §6a) | 3.32% (≈350 filings) | [1.82, 8.26] |
| **Wrong-document rate (policy picked a worse doc than one present)** | **0.00% (0/155 read)** | [0.00, 2.42] over all 155 |
| Strict rate (also counting partial/preliminary pre-announcements) | 10.00% (8/80) | [5.15, 18.51] |

The pre-specified SRS figure is the headline; the two post-stratified
figures are reported beside it, never in place of it (§6a explains why the
smaller one is probably closer to the truth and why it does not get to be
the headline).

**Every error found is the same kind, and it is not the kind the EX-99 fix
arc was fixing.** The document-selection *policy*
(`ingest_metadata.select_earnings_document`) did not mis-pick once in 155
hand-read filings. What it does wrong is inherited from upstream: the
corpus treats `has_earnings_item = 1` as "this 8-K is an earnings release,"
and roughly one in twenty of those 8-Ks is not one. The selected document
is then the best (often only) document in a filing that should not have
been in the earnings population at all.

**Bar for F3: the corpus clears it, conditionally.** See §7 — the condition
is one cheap, named screen, not a re-ingest.

---

## 1. Population and sampling design (seeded, reproducible)

Population = every row of `filings` with `earnings_doc_filename IS NOT
NULL`: **10,567** selections, all form 8-K, 243 CIKs, 2015-07-02 →
2026-08-20.
(10,569 filings carry `has_earnings_item=1`; two are the ratified
`exclude` rows in `data/f2/earnings_doc_overrides.csv` — Pioneer
2018-04-09 and AT&T 2019-10 — so the difference is expected, not a gap.)
Class sizes: `EX99_PRESS_RELEASE/high` 10,312 · `8K_BODY/high` 210 ·
`EX99_PRESS_RELEASE/medium` 26 · `EX99_PRESS_RELEASE/low` 19.

Scripts archived at `data/hardening/h4_sample.py`, `h4_cards.py`,
`h4_deep.py`, `h4_verdicts.py`; the drawn sample is frozen in
`data/hardening/h4_manifest.json`; **all 155 per-row verdicts are in
`data/hardening/h4_verdict_ledger.csv`** (accession, tier, filer, items,
section_type, confidence, selected document, extracted word count,
quarter-cell size, verdict, note). Re-running `h4_sample.py` reproduces
the identical draw from the seeds.

| Tier | Draw | n | Purpose |
|---|---|---|---|
| **PRIMARY** | `random.Random(20260825).sample(range(10567), 80)` over the population **sorted by `accession_number`**, **no stratification** | 80 | The base-rate-representative estimate. This is the number to quote. |
| SUPP-A | **census** of all 26 medium + 19 low selections | 45 | Exact rate for the confidence classes the primary draw cannot reach (expected 0.2 and 0.14 rows). Reported separately, never pooled into the headline. |
| SUPP-B | `random.Random(20260826).sample(range(210), 30)` over `8K_BODY/high` | 30 | Same reason: primary draws ~1.6 of these. Reported separately. |

No overlap between tiers (verified programmatically: both intersections
empty). **155 distinct documents read.**

**Why not stratify the primary draw.** The brief says "stratified only by
nothing — this is the Tier-C protocol applied to selection," and the
project's own §2a base-rate caveat is the reason: a stratified or
worst-of draw estimates the strata, not the corpus. The supplementary
tiers exist only so the *decomposition* the brief asks for has any power;
they are the Tier-A/B analogue and are kept out of the headline exactly as
`spotcheck/` keeps Tiers A/B/D out of Tier C.

**Balance check** (not a stratification — evidence the unstratified draw
landed representative):

| | Population | Primary n=80 |
|---|---|---|
| filing year 2015–2019 / 2020–2026 | 40.8% / 59.2% | 42.5% / 57.5% |
| core / extension stratum | 72.5% / 27.5% | 75.0% / 25.0% |
| distinct CIKs | 243 | 67 |
| sector spread | 8 sectors | all 8 present |

Across all 155: **84 of 243 CIKs**, every year 2015–2026 present
(min 4 rows in 2026, max 21 in 2017/2018/2019).

---

## 2. Verdict definitions (fixed before reading; applied uniformly)

The brief's three-way verdict, made operational. The boundary between "an
earnings release" and "an item-2.02 disclosure that isn't one" is genuinely
fuzzy, so the middle case is broken out rather than silently absorbed into
either side, and **both** rates are reported.

- **A — correct earnings text.** The selected document's primary purpose is
  disclosing the filer's own results for a period: a press release, a
  shareholder letter, or (for `8K_BODY`) the release text embedded in the
  8-K body. Counted CORRECT.
- **B — partial / preliminary results pre-announcement.** Real results
  content for the just-ended period, but one or a few line items rather
  than a release: derivative gain/loss, realized prices, strategic-
  investment marks, preliminary revenue/EPS, unit deliveries. Counted
  CORRECT in the headline, counted as an error in the strict sensitivity.
- **C — not results content.** The document does not disclose the filer's
  own results for a period at all: strategy/analyst-day material, a
  transaction announcement, tax-law analysis, a restructuring plan, recast
  or re-furnished historical schedules, a *third party's* results, or an
  empty/image-only exhibit. **Counted as the error.**
- **WRONG** — a better document demonstrably existed in the same filing and
  was not selected. **This is the class the EX-99 fix arc addressed.**

Text was extracted with `extract.py`'s own
`strip_sgml_document_wrapper()` → `html_fragment_to_text()`, so what I read
is byte-for-byte what F3 will extract, iXBRL hidden-block stripping and
all.

---

## 3. What I actually read (not just counts)

For each of the 155 filings I read an evidence card containing: the filing
metadata and `items`, the **full document-format index** for the accession
(so unselected siblings were visible by type/description/seq), byte/char/
word counts and `<img>` count, and the first ~1,100 characters plus a
mid-document slice of the extracted text. Every card was read
individually. Eleven filings got a second, deeper pass (full-text keyword
walks, the cached SEC index page, sibling-accession queries) because the
card was ambiguous — those are named in §4 with what the deeper read
showed.

Things I confirmed by reading, worth recording:

- **`8K_BODY` is not automatically a cover-page failure.** Halliburton's
  and IBM's bodies carry the release verbatim — HAL `0000045012-17-000154`
  reads *"On July 24, 2017, registrant issued a press release entitled
  'Halliburton Announces Second Quarter 2017 Results.' The text of the
  Press Release is as follows:"* followed by the whole release. 11 of 31
  sampled `8K_BODY` rows are this shape. The S7-B1 conditional fallback did
  its job.
- **The Netflix P6 flag really is benign.** `0001065280-22-000256` and
  `0001628280-17-000276` are shareholder letters ("Fellow shareholders,")
  with the full quarterly table — no "press release" language because
  Netflix does not write one. Correct selections; the release-language
  screen is measuring dialect, not error.
- **The exotic exhibit dialects all resolve correctly.** Read and verified:
  `EX-99.01` (Xcel, Intuit, Gen Digital), bare `EX-99` (TI, Corning),
  `EX-99.` (TI 2020), `EX-99..1` double-dot (Biogen, Pioneer, Zoom, Aon),
  `EX-99.(A)` / `EX-99.A` (Vistra ×3), `EX-99.0` (Progressive),
  `EX-99.Q120 EARNINGS` (Arista), `EX-99.15` vs `EX-99.2O` (JNJ ×17),
  and `EX-95.1`-typed-but-described-99.1 (Linde, caught by the P3
  outside-EX-99 screen at medium). **All correct.**
- **Filenames lie; content doesn't.** Citigroup `0001104659-25-034974`
  (filed 2025-04-15) selects `c-20240712xex99d1.htm` with the filer's own
  typo description `'ECHIBIT 99.1'` — the document opens *"April 15, 2025 /
  FIRST QUARTER 2025 RESULTS AND KEY METRICS."* Correct. DuPont
  `0001666700-19-000016` selects `exhibit991enrschedules1q19.htm` from an
  8-K named `enr8-k1q19.htm`; the content is "DowDuPont Reports First
  Quarter 2019 Results." Correct. Any screen that reasons from filenames
  would flag both.
- **One document is 74% not-the-release and still a correct pick.** Simon
  Property `0001104659-21-013702`: the EX-99.1 is a combined "EARNINGS
  RELEASE & SUPPLEMENTAL INFORMATION" book. The release narrative is
  present (FFO $3.237B / $9.11 per diluted share found at char ~3.6k, ending
  near char ~28k against a 96,506-char document). The filing contains no
  separate release, so the pick is right — but ~74% of the extracted text
  is property-level supplemental tables. That is an F3 chunking problem,
  not a selection error, and it is filed as one.

---

## 4. The errors — every C row, with what should have been picked

Nine C rows across 155 filings, **9 distinct CIKs, one occurrence each.**
This diffuseness is the whole finding (contrast §6).

| # | Accession | Filer | Filed | Class | What the document actually is | What should have been picked |
|---|---|---|---|---|---|---|
| 1 | `0001193125-16-496516` | EXXON MOBIL (34088) | 2016-03-08 | EX99/high | **2016 Analyst Meeting presentation + CEO Q&A transcript**, 21,009 words (Tillerson answering "a hypothetical question: it's 2017, and the sanctions have been removed against the Russian Federation…"). Zero results-headline/EPS/revenue markers. | **Nothing in this filing.** Its siblings are EX-99.2 "SLIDE PRESENTATION" and EX-99.3 "FREQUENTLY USED TERMS". XOM's Q4/FY2015 release is a *different* accession, `0000034088-16-000053` (2016-02-02), already in the corpus at high confidence. This filing should not be in the earnings population. |
| 2 | `0001193125-16-623725` | CHUBB (896159) | 2016-06-16 | EX99/high | **Pro-forma recast segment tables** for the ACE/Chubb merger — 4,482 words, 52% numeric tokens, 25 prose lines total, all footnotes ("2015 Pro forma results: Legacy ACE plus Legacy Chubb historical results"). | Nothing — the filing has exactly 2 documents (8-K + this EX-99.1), verified from the cached index. Not an earnings release; should not be in the population. |
| 3 | `0001193125-16-792454` | HOWMET/Arconic (4281) | 2016-12-14 | EX99/high | **Non-GAAP reconciliation appendix**, 761 words, no narrative ("Reconciliation of Global Rolled Products Adjusted EBITDA … 2008 2009 2010 …"). An investor-day filing: 84 documents, 80 of them GRAPHIC slide images. | Nothing better is verifiable. EX-99.2 (92 KB, the image-backed deck) is not a release either. **Caveat:** EX-99.2 is not cached, so I can only read its index row — I am not claiming it is worse, only that neither is a release. |
| 4 | `0001645590-18-000004` | HPE (1645590) | 2018-02-13 | EX99/high | **Revised FY2016 segment schedules** after a segment reorg. Its own text: *"These changes had no impact on Hewlett Packard Enterprise's previously reported consolidated net revenue, earnings from operations, net earnings or net earnings per share."* | **Nothing in this filing.** HPE's actual Q1 FY2018 release is `0001645590-18-000006` (2018-02-22), already in the corpus. |
| 5 | `0000200406-19-000063` | JOHNSON & JOHNSON (200406) | 2019-10-23 | EX99/**low** | **Re-furnished Q3-19 condensed financial statements** (EX-99.2 only; cached index shows 8-K + one exhibit, no EX-99.1). Tables, no narrative. | **Nothing in this filing.** The Q3-2019 release is `0000200406-19-000061` (2019-10-15, `a2019q3exhibit991.htm`, high confidence), already in the corpus. |
| 6 | `0000072903-18-000003` | XCEL ENERGY (72903) | 2018-01-11 | 8K_BODY/high | **Tax Cuts and Jobs Act impact analysis** + 2018 guidance reaffirmation. No completed-period result is stated. | Nothing — no exhibits. Should not be in the population. (S6 §5.4 already named this filing type; it was never counted.) |
| 7 | `0001140361-20-008805` | KKR (1404912) | 2020-04-14 | 8K_BODY/high | **Debt-offering business/COVID update**, whose own item 2.02 says *"we have not completed preparation of our financial results for the quarter ended March 31, 2020."* | Nothing — no exhibits. Item 2.02 here incorporates item 8.01 by reference. |
| 8 | `0001104659-22-112514` | INTERCONTINENTAL EXCHANGE (1571949) | 2022-10-28 | 8K_BODY/high | **A third party's results.** Item 2.02 reads: *"Bakkt Holdings, Inc., an equity method investee of Intercontinental Exchange, Inc., filed a Current Report on Form 8-K announcing that for the three months ended Sept…"* 602 words, 83% SEC cover-page boilerplate. | Nothing — no exhibits. This one is worth naming loudly: attributed to ICE, the *results text is not ICE's*. |
| 9 | `0000950103-21-015731` | EMERSON ELECTRIC (32604) | 2021-10-12 | 8K_BODY/high | **AspenTech transaction agreement 8-K** (Item 1.01 dominant, 4,406 words of merger/S-4 legalese). The item-2.02 block is a ~200-word FY21 guidance reaffirmation buried at char ~15k. | Nothing — the only exhibit is EX-2.1, the Transaction Agreement. |

**Zero WRONG rows.** Two independent corroborations of that:

1. **Hand-read**: for all 155, the full index was on the card; no sampled
   filing contained an unselected exhibit that a reader would prefer.
2. **Mechanical sibling screen** over all 155 (`h4_verdicts.py` companion
   query): for every unselected `EX-99%` row, does its description read
   more release-like (`press|news|earnings release`) than the selected
   row's, without a disqualifier (`presentation|slide|supplement|
   statistic|financial report|broker|deck|transcript|prepared remarks`)?
   **0 hits / 155 filings.**
   *Limitation, stated because S6 §5.5 states it:* `data/raw/documents/`
   caches only the **selected** document, so a "better sibling" claim can
   be made from index metadata but not from rival bytes. The screen is
   therefore evidence, not proof. Under a zero-GET constraint this is the
   ceiling of what is knowable, and it is the same standard the ratified
   override rows use ("Confirmation is by index metadata, the same standard
   as the NVIDIA row").

### The B rows (correct in the headline, flagged for F3)

19 rows, 14 CIKs. Two recurring shapes, both real disclosures and both
*short*:

- **Oil-and-gas derivative / realized-price pre-announcements** — Pioneer
  ×3, EQT ×3, Diamondback ×1. Filed ~2 weeks before the release; typically
  1,300–1,800 words of which ~2,000 characters are SEC cover page.
- **Single-line-item marks** — PayPal ×2 ("expects to report a pre-tax gain
  of $218 million … +$0.14 per share"), Occidental, Chevron's Q1-26 timing-
  effects table, CVS's FY22-vs-guidance statement, Allergan's Q4-17
  restructuring charge, Western Digital's preliminary FQ2, Illumina's
  earnings-call clarification Q&A, Intuitive's preliminary Q4,
  Freeport's Q2-20 update, KKR's monetization update (384 words), and
  Tesla's Q1-22 production & deliveries release (**276 words, no dollar
  figure anywhere**).

---

## 5. Decomposition, as the brief requires

### By confidence label

| Class | N in corpus | n read | C errors | Error rate | 95% Wilson CI | Strict (+B) |
|---|---|---|---|---|---|---|
| `EX99_PRESS_RELEASE/high` | 10,312 | 79 | 4 | **5.06%** | [2.00, 12.30] | 10.1% |
| `EX99_PRESS_RELEASE/medium` | 26 | **26 (census)** | 0 | **0.00%** | [0.00, 12.9] | 0.0% |
| `EX99_PRESS_RELEASE/low` | 19 | **19 (census)** | 1 | **5.26%** | [0.94, 24.6] | 5.3% |
| `8K_BODY/high` | 210 | 31 | 4 | **12.90%** | [5.13, 28.9] | 61.3% |
| **Post-stratified corpus** | 10,567 | 155 | — | **5.21%** | — | **11.11%** |

The post-stratified figure weights each class rate by its true class size;
it agrees with the unstratified primary estimate (5.00%) to within 0.2 pp,
which is the reassurance you want that the primary draw was not unlucky.

**The confidence label carries almost no information about this error.**
Medium and low are *censuses*, not samples: `medium` has zero errors in all
26, `low` has one in all 19. High confidence carries every remaining error.
This reproduces, on a measured basis, decision_audit §2.1's indictment —
*"each was found by a human read or a screen built after one, never by the
confidence label."* The label is a statement about **how unambiguous the
exhibit-type evidence was**, and it is well-calibrated for that. It says
nothing about whether the 8-K was an earnings release, because nothing in
the selection policy ever looks at that.

### By section_type

| section_type | n read | A | B | C | headline err | strict err |
|---|---|---|---|---|---|---|
| `EX99_PRESS_RELEASE` | 124 | 115 | 4 | 5 | **4.03%** [1.73, 9.09] | 7.26% [3.87, 13.22] |
| `8K_BODY` | 31 | 12 | 15 | 4 | **12.90%** [5.13, 28.9] | **61.29%** [43.8, 76.3] |

(The fifth `EX99_PRESS_RELEASE` C row is JNJ `0000200406-19-000063`, which
is section_type `EX99_PRESS_RELEASE` at `low` confidence — it appears in
both this table and the low-confidence row above.)

`8K_BODY` is ~3× worse on the headline metric and ~8× worse on the strict
one, on 2.0% of the corpus (210 of 10,567). Its 210 filings are highly
concentrated: **the top 5 CIKs are 109 of 210 (52%)** — Pioneer 38,
Halliburton 32, EQT 16, Diamondback 14, IBM 9 — and my n=30 sample hit four
of those five. The class is structurally *bimodal*: Halliburton/IBM put the
whole release in the body (A), Pioneer/EQT/Diamondback/PayPal put a
derivative pre-announcement there (B), and the residue is the C tail.

---

## 6. Against the three known fixed error classes — the actual point

| | Prologis | B1 cover pages | PSEG | **This residual** |
|---|---|---|---|---|
| Within-filer density | 41 of 45 (F2_PROGRESS §5; decision_audit says 42/45 — I did not re-derive) | 14–15 filings across ~2 filers | **45 of 45** | **1 per filer, 9 filers, no repeats** |
| Corpus share | ~0.4% | ~0.14% | ~0.4% | **~5.2%** |
| Detectable by | one human read of one filer | a screen built after a human read | one human read of one filer | **only by sampling — no screen fires** |
| Fix shape | named per-filer handler | conditional fallback + UNRESOLVED | named per-filer handler | **not per-filer at all** |
| Fixed? | yes | yes | yes | **not addressed; not previously measured** |

The three fixed classes total roughly **101–102 filings ≈ 0.96%** of the
corpus and were each ~90–100% dense inside a single filer — which is
exactly why a human read found them and why a per-filer handler fixed them.
The residual is **five times larger and structurally invisible to that
method**: it is one bad filing per filer per few years, in filers whose
other selections are all correct. Exxon, Chubb, HPE, JNJ, Xcel, KKR, ICE and
Emerson are all *good* filers in this corpus; each contributes exactly one
bad row.

**This vindicates the decision_audit's recommendation and its one-line
amendment to the lazy-elite rule.** Patching filers could not have found
this, no matter how many filers were patched, because the defect does not
live in filers. It lives in the population definition. Measuring the class
was the only way to see it — *measuring an error rate is never
over-engineering.*

### 6a. A lower-variance secondary estimate — and the honest caveat on the headline

The headline 5.00% is the **pre-specified estimator** (unstratified SRS,
one seed, no auxiliary information) and stays the headline. But an
auxiliary variable is known for the *entire* population — whether a
selection is the sole earnings 8-K in its (CIK, calendar quarter) — and
post-stratifying on it is strictly more efficient. Measured on the sample:

| Group | Corpus share | n read | C rows | P(C \| group) | 95% Wilson CI |
|---|---|---|---|---|---|
| sole earnings 8-K in its quarter | 9,048 = **85.63%** | 116 | **0** | 0.00% | [0.00, 3.21] |
| in a multi-filing quarter cell | 1,519 = **14.37%** | 39 | **9** | **23.08%** | [12.65, 38.34] |

- Point estimate: 0.1437 × 0.2308 = **3.32% ≈ 350 filings.**
- Bracket carrying both conditional CIs: **1.82% – 8.26%** (≈192 – 872).

**Why it is lower than 5.00%, stated plainly:** the primary draw happened
to pull **17 of 80 (21.3%)** multi-cell rows against a population share of
14.37% — about 1.8 standard errors high. That is ordinary sampling noise
(binomial sd ≈ 3.9 pp at n=80), not a defect in the draw, and it inflates
the unstratified estimate. Both figures sit comfortably inside the
headline's own CI [1.96, 12.16], so nothing here is contradicted.

**Reported both ways on purpose.** Swapping the headline for the smaller
number after seeing it would be exactly the move this hardening phase
exists to prevent. The pre-specified estimate is **5.00% [1.96, 12.16]**;
the better-conditioned estimate is **~3.3% [1.8, 8.3]**; the honest
one-line summary is *"a few per cent, almost certainly under 10%, and
entirely confined to filings that are not the only earnings 8-K of their
quarter."*

**Independent corpus-wide corroboration of the ~5%.** If the error is
"extra item-2.02 8-Ks that are not the quarter's release," it should show
up structurally. It does: **790 of 10,567 selections (7.5%) are "extra"
filings beyond one per (CIK, calendar quarter)** — 729 quarter-cells hold
more than one earnings 8-K (672 hold 2, 54 hold 3, 3 hold 4–5). All nine C
rows are such extras. 7.5% is the right *upper* bracket, since some extras
are legitimate (PNC files 29 same-day pairs; AT&T/IBM file release +
supplement). A measured 5.2% sitting just inside a 7.5% structural ceiling
is a coherent picture, derived two independent ways.

---

## 7. Does the corpus clear a reasonable bar for F3?

**Yes, conditionally — and the condition is cheap.**

The case for yes:
- **The selection policy is sound.** 0/155 wrong picks, corroborated
  mechanically. The dialect handling (nine exotic exhibit typings, all
  correct), the description tie-break (Eversource ×16, all correct), the
  P3 outside-EX-99 screen (Linde), and the conditional `8K_BODY` fallback
  (HAL/IBM) all work on real bytes. Nothing here argues for re-running
  ingestion.
- **3–5% of documents (upper bound ~12%) being the wrong *kind* of
  item-2.02 filing is survivable for a research corpus, and it is smaller
  than errors the project already accepts and documents.** The labeler's
  own measured base-rate error is ~25% (Tier C, HANDOFF §2a); the student
  labeler's is roughly double the teacher's. A ~5% document-composition
  error does not dominate that, and unlike the labeler error it is
  *removable* by a screen rather than only quotable as a limitation.
- **It is not silent.** After this report it is a documented, quantified,
  bounded limitation with a named population — which is the standard
  `RED_FLAGS_LIMITATION.md` set.

The condition — **one screen, F3-side, before extraction**:

> **Emit a FAIL/WARN row, do not silently extract, when an earnings
> selection sits in a multi-filing (CIK, calendar-quarter) cell AND its
> text lacks a results-announcement signature.**

Measured properties of that screen on this sample (§6a):

- **Recall 9/9 = 100%.** Every C row found is in a multi-filing cell. The
  85.63% of the corpus that is the sole earnings 8-K of its quarter
  produced **0 errors in 116 reads** [0.00, 3.21].
- **Trigger population 1,519 filings (14.4%)**, before the text
  signature narrows it; **precision ~23% for C alone, ~67% (26/39) for
  C-or-B** — i.e. two thirds of what it flags is genuinely not a full
  quarterly release.
- Cost: one `GROUP BY` and one regex, both already written in
  `data/hardening/h4_verdicts.py`.

Adding the text signature (any of "today reported / announced results /
per diluted share / quarterly results" absent) should cut the flag list
well below 1,519 without touching recall — but I have **not** measured that
narrowed screen's recall, and it must be measured on this same 155-row
ledger before it is trusted, not assumed.

This satisfies the hard rule *"a section that extracts wrong is worse than
one that fails loudly."* Nine documents in my sample — including a
21,000-word CEO Q&A transcript and another company's earnings — are
currently on track to enter F3 labelled `EX99_PRESS_RELEASE` with no flag
at all. That is the "plausible-looking garbage" case, and it is the one
thing here that must not stay silent.

I am **not** recommending: a re-ingest, a policy change to
`select_earnings_document`, deleting the 790 extras, or any per-filer
handler. Per-filer handlers are the wrong shape for this defect (§6), and
the extras include real second releases.

---

## 8. Handoff to F3 — measured inputs, not opinions

1. **`MIN_SECTION_WORDS` evidence from the earnings side.** Word counts of
   all 155 extracted selections: class **A** min 1,129 / p10 1,670 / median
   4,076 / max 15,719. Class **B** min 276 / median 888 / max 2,004. Class
   **C** min 602 / median 2,189 / max 21,009.
   **Only 2 of 155 fall under 400 words** — Tesla's P&D release (276) and
   KKR's monetization update (384), *both genuine disclosures*. A floor
   anywhere in 400–1,100 words would separate class A cleanly from most of
   B and would fail those two real documents. **Do not set the earnings
   floor above ~400 words without arguing past these two rows by name.**
   Length is a poor discriminator here: the largest document in the whole
   sample (21,009 words) is an error, and the smallest (276) is not.
2. **S6 §5.3's 44 thin/12 near-empty EX-99 selections stand as named
   should-fail rows.** None landed in this random draw (expected ~0.3 of
   80), which is consistent, not contradictory. They remain the strongest
   argument against lowering any floor.
3. **`8K_BODY` carries a fixed boilerplate prefix.** Characters before the
   first "Item 2.02" in the 30 sampled bodies: min 1,121, median 1,975, max
   14,938 — a median **16%** of the whole extracted document, and **>50%**
   for five of them (EQT ×3, PayPal ×2). F3 should slice `8K_BODY` sections
   from the item-2.02 heading, not from the top of the file, or every one
   of these 210 sections leads with SEC cover-page furniture ("Check the
   appropriate box below…").
4. **Combined release+supplemental documents dilute badly.** Simon Property
   is 74% supplemental tables inside one EX-99.1. REITs are the likely
   population (AvalonBay's EX-99.1/99.2 split is the clean alternative
   shape). Worth a chunk-level look in F3, not a selection change.
5. **The `EX99_PRESS_RELEASE` label is wrong for 210 + ~550 rows** — the
   `8K_BODY` class is honestly typed, but every C row is stored as
   `EX99_PRESS_RELEASE` while being something else. If F5 conditions on
   `section_type`, that is the join to be careful about.

## 9. What this report does not cover

- **Rival bytes.** Only the selected document per filing is cached, so
  every "nothing better existed" claim rests on index metadata (§4
  limitation). Confirming any one of them costs one GET and is the main
  session's call.
- **Extraction quality.** I verdicted *which document was selected*, not
  what F3's slicing will do to it. Items 1–4 of §8 are inputs to that
  question, not answers.
- **The 159 CIKs not in the sample.** 84 of 243 CIKs are represented. The
  estimate is corpus-wide by construction (random draw), but no individual
  unsampled filer is cleared.
- **A second rater.** These are one Opus reader's verdicts, recorded as
  such. Per HANDOFF §7 they are model judgments, not the owner's, and not
  human validation of ground truth. The A/B boundary in particular is a
  judgment call — which is why both rates are published side by side and
  every B and C row is named so anyone can re-bucket them.
