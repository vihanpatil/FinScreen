# S7 — red-team findings, F2 stages S2–S6

**Written 2026-08-24 by red-team-reviewer (Opus).** Brief:
`data/f2/status/S7_brief_redteam.md`. Everything below was re-derived from
code and artifacts on disk; no agent self-report was taken at face value.
Zero live GETs; DB and parquets opened read-only (`mode=ro`).
The draft `data/F2_INGESTION_REPORT.md` was read LAST, after every
finding below already existed.

Ranked by severity. Each finding: what is wrong, file:line, what it
silently breaks, confidence.

---

## Section A — what I verified as SOUND (re-derived, not trusted)

Stating these first so the findings are read in proportion.

1. **Fundamentals classifier reproduces exactly.** I reimplemented the
   six-state classifier from the spec text (families, preference order,
   0.75 bar, staleness anchor, migration overlap rule, filed-span
   denominator) and ran it over all 244 companies from
   `data/fundamentals_e2.parquet` + `companies.coverage_*`. Against
   `data/f2/concept_resolution.csv`, all **3,416** pairs agree:
   **0 state disagreements, 0 resolved-tag disagreements, 0 coverage
   disagreements >0.005.** State counts SINGLE 2,355 / DOMINANT 489 /
   MIGRATION 75 / OVERLAP 8 / ABSENT 342 / PARTIAL 147 = 497 UNRESOLVED,
   matching the report.
2. **Enumeration is complete; nothing was silently dropped.** Re-enumerated
   10-K/10-Q/8-K in `[2015-07-01, 2026-08-31]` for all 244 CIKs directly
   from `data/raw/submissions/` (recent block + every cached pagination
   chunk): **45,632** target filings. `filings` holds 45,545 and the
   per-CIK accession sets match exactly except for 3 CIKs — 1483096 (16),
   1751788 (67), 1868275 (4) — which are precisely the 87
   `co_registrant_filings` rows. 45,545 + 87 = 45,632.
3. **The 160 uncached pagination chunks are safe.** Every one has
   `filingTo` before 2013-01-01 (max 2012-12-02); none intersects the
   window.
4. **Universe artifacts verified by independent re-hash.** All 7 sha256
   entries in `hybrid136_checksums.json` match the files on disk.
   `universe_membership` (299 rows) is byte-faithful to
   `hybrid136.parquet` on (cik, sector, stratum, member_from, member_to).
5. **Membership PIT is clean.** `hybrid136_panel.parquet`: 0 of 1,496
   rows have `float_filed >= recon_date`; the latest float filing before
   each of the 11 recon dates is 3–11 days prior. 136 members at every
   date.
6. **Censoring is explained on the EDGAR side.** All 29
   `member_stopped_filing` members and all 31 censored members have at
   least one `distress_events` row. 0 unexplained disappearances.
7. **EA is genuinely the sole no-coverage member.** Joining
   `prices_e2.parquet` to each company's own coverage window: EA is the
   only fetched CIK with 0 in-window rows; the next-smallest is 539. No
   boundary case, and no fetched member's series ends >30 days early.
8. **P5 and P6 reproduce.** Recomputed from the 10,568 cached selected
   documents: 50 thin (<1,500 chars) / 12 empty (<100) — matches the DB's
   50 `ex99_thin_exhibit` rows. P6: 10,549 measured, 0 uncached, Netflix
   25/47 = 53%, exactly one flagged CIK — matches the shipped WARN.
9. **All four earnings-doc overrides fired**; the AT&T exclusion is
   recorded at INFO (`earnings_doc_excluded_by_override`), not a silent
   NULL. 10,569 earnings 8-Ks, 10,568 selections, 1 excluded.
10. **Test gate is real.** I re-ran the suite: **731 passed, 5 skipped,
    0 failed** in 61 s.
11. **Mitigating fact the report does not state:** 0 of the 87
    co-registrant accessions is an earnings 8-K, so the accession-keyed
    PK costs the *text* corpus nothing.

---

## Section B — findings

### B1. HIGH — 14 filings store the 8-K cover page instead of the press release, at HIGH confidence, silently

**What.** `ingest_metadata.py:1268-1271` returns the 8-K primary document
as `("8K_BODY", "high")` **unconditionally** whenever no document typed
`EX-99` or `EX-99.<digits>` was found — with no check that the filing
index still holds an unselected candidate.

`_EX99_FAMILY_RE` (`ingest_metadata.py:2329`) is `^EX-99(\.\d+)?$`, and
`_canonical_exhibit_type` (`ingest_metadata.py:1080-1100`) deliberately
leaves every malformed variant unrecognised. That decision is *pinned by
a test*: `test_ingest_metadata_scale.py:1907-1912`
(`test_double_dot_type_is_still_outside_the_ex99_family`), justified as
"the override resolves this ONE filing; it does NOT widen the type
family, which is how a typo would become a silent mis-pick generator."
The measurement says the opposite: **not** widening it is what produced
the silent mis-picks.

**Measured.** 38 earnings filings carry a non-canonical 99-ish exhibit
type (`EX-99..1` ×5, `EX-99.2O` ×17, `EX-99.1PRE` ×6, `EX-99.(A)`/`EX-99.A`
×3, `EX-99.` , `EX-99..02`, `EX-99.1(A)`, `EX-99.Q120 EARNINGS`, …).
Of the 225 `8K_BODY`/high selections, **19 have an unselected non-8-K,
non-graphic document row**, and **14 of those rows are release-shaped**:

| CIK | accession | date | unselected exhibit |
|---|---|---|---|
| 315293 Aon | 0001628280-15-005672 | 2015-07-31 | `EX-99..1` ex991pressreleaseq22015.htm |
| 1110803 Illumina | 0001110803-16-000185 | 2016-05-03 | `EX-1` a1q16earningsrelease.htm |
| 1110803 Illumina | 0001110803-16-000194 | 2016-07-26 | `EX-1` a2q16earningsrelease.htm |
| 875045 Biogen | 0000875045-17-000014 | 2017-04-25 | `EX-99..1` q12017pressrelease.htm |
| 1038357 Pioneer | 0001038357-17-000063 | 2017-08-01 | `EX-99..1` pxdq22017earningsreleaseex.htm |
| 1645590 HPE | 0001645590-17-000006 | 2017-11-21 | `EX-1`/`EX-2` pressrelease112117.htm |
| 1692819 Vistra | 0001193125-17-174537 | 2017-05-18 | `EX-99.(A)` |
| 1692819 Vistra | 0001193125-17-248214 | 2017-08-04 | `EX-99.A` |
| 1692819 Vistra | 0001193125-18-057237 | 2018-02-26 | `EX-99.(A)` |
| 1038357 Pioneer | 0001193125-18-111008 | 2018-04-09 | `EX-99.1(A)` (investor deck — arguably correct) |
| 1637459 Kraft Heinz | 0001637459-19-000050 | 2019-06-07 | `EX-1` a6719exhibit991.htm |
| 1585521 Zoom | 0001585521-19-000057 | 2019-12-05 | `EX-99..1` zm-20191205ex991.htm |
| 97476 Texas Instruments | 0000097476-20-000006 | 2020-01-22 | `EX-99.` q42019txnex99-8xker.htm |
| 1596532 | 0001628280-20-006442 | 2020-05-05 | `EX-99.Q120 EARNINGS` ex991q120-earningsrelease.htm |

Three verified by reading the stored document itself — the stored "earnings
document" is the SEC Form 8-K cover page whose own Item 2.02 says the
release is elsewhere:

- Aon `0001628280-15-005672` (2,260 chars): *"Aon plc issued a press
  release … A copy of the Press Release is attached hereto as Exhibit
  99.1."*
- Illumina `0001110803-16-000185` (2,827 chars): *"The full text of the
  Company's press release is attached hereto as Exhibit 99.1."*
- HPE `0001645590-17-000006` (4,231 chars): *"A copy of the press release
  is attached hereto as Exhibit 99.1."*

**Why every guard missed it.** P5's thin-exhibit floor is 1,500 chars —
these are 2,260–4,231. P3 requires the *description* to say "press
release"; these say `EXHIBIT 99..1`, `EX-99.1`, `EXHIBIT 1`. P6 is a
per-CIK majority test. The confidence label is `high` by construction.
The 1% `earnings_doc_unresolved` FATAL ceiling counts a cover-page pick
as *resolved*, so "0.00% unresolved" cannot see this class.

**What it silently breaks.** 14 F3/F4 inputs whose "earnings text" is SEC
form boilerplate — long enough to survive a word-count floor, so the
labeler will emit sentiment / guidance / red_flags for a checkbox page.
Also a new dialect (`EX-1`/`EX-2`, 4 filings) covered by no handler and no
override row.

**Confidence:** DEFINITE for the mechanism and for the 3 read in full;
HIGH for all 14. Owner: data-engineer (S3 metadata code).

### B2. HIGH — the ratified "8K_BODY tail is benign" prior is falsified by one query

`data/F2_INGESTION_REPORT.md:405-414` offers, as a prior, that the unread
8K_BODY tail is "probably fine (all ten read had zero `EX-99` strings in
their index)". `F2_PROGRESS.md:47-49` calls it the "8K_BODY benign class",
and the ratified segment-1 diagnosis
(`data/f2/status/S6_seg1_ex99_diagnosis.md`, quoted at
`F2_PROGRESS.md:240`) concludes "**0 genuine selection failures**".

**Measured:** 19 of 225 have an unselected non-8-K document row; 14 are
release-shaped (B1). The prior is not weak — it is wrong, and it was
checkable offline in seconds.

**What it breaks:** the report tells the owner the unread tail is a
low-risk residual. It is where the defect lives.
**Confidence:** DEFINITE. Owner: docs-writer + main session (the ruling).

### B3. HIGH — the XOM price override IS the APC trap shape, and code + docs both assert it is not

**Facts, re-derived.** `data/raw/company_tickers.json` maps
`XOM → CIK 2115436 "ExxonMobil Holdings Corp"`. The member CIK is
**34088**, which is **absent** from the bulk map. This is the same
signature as `APC → CIK 2080921 "ARKO Petroleum Corp."` (member 773910),
the trap the entire dead-ticker rule exists to prevent.

**Three problems, in order:**

1. **The override file's own comment is false about the row beneath it.**
   `data/f2/price_ticker_overrides.csv` (comment block, "THE TWO CASE
   CLASSES ON FILE"): *"the APC trap is the opposite, where the symbol
   points at a DIFFERENT cik, and that case is still censored, never
   overridden."* The 34088 row directly below is exactly that case.
   `data/F2_INGESTION_REPORT.md:461-464` repeats the same false safety
   property verbatim.
2. **No code checks it.** `ingest_prices.py:414-418` applies an override
   whenever `status == "censored"`, regardless of *why* — including a
   bulk-map contradiction (`ingest_prices.py:325-329`). Nothing anywhere
   cross-checks the override's ticker against the bulk map.
3. **The warning fires on the wrong one.** `ticker_wobble_issues`
   (`ingest_prices.py:465`) skips any CIK with no bulk symbols mapping to
   it. 34088 has none, so **XOM produces no WARN on any run**; 4904 (AEP),
   where the bulk map *agrees* with our CIK — the safe direction — WARNs
   every run. Exactly backwards.

**The evidence field is also weak for the claim it makes.** It cites (a)
E1's `universe.csv` already using XOM→34088 (a prior decision, not
evidence about a later reorganisation), (b) "still filing", (c) F1's
census. Nothing establishes price-series continuity. There is *no* cached
`submissions` for CIK 2115436 in the repo to corroborate the holdco story.

**Corroborating evidence that the mapping is probably right, which the
row does not cite and no code checks:** the fetched XOM series is 14,282
rows from 1970-01-02 with no discontinuity flagged — a reassigned symbol
would have a short history.

**What it breaks if wrong:** a mega-cap core member's entire return series
is another company's. **Confidence:** DEFINITE that the guard is missing
and the documentation is false; MEDIUM-LOW that the mapping itself is
wrong. Owner: data-engineer (S5) + main session (the ruling).

### B4. HIGH — the censoring pair is quoted as a CIK count; in membership-time it is 4× larger in the earliest cohorts and concentrated in energy

`data/F2_INGESTION_REPORT.md:166-169, 592-595` instruct that "OPERATIVE
32 members with no usable prices (28 core / 4 extension)" accompany every
result. That is 13% of CIKs and it is the wrong denominator for a
walk-forward backtest.

Re-derived by joining `price_ticker_map.has_usable_prices` onto the 1,496
panel cells:

| recon date | cells with NO usable prices |
|---|---|
| 2016-07-01 | 19 / 136 = **14.0%** |
| 2017-07-01 | 22 / 136 = **16.2%** |
| 2018-07-01 | 17 / 136 = 12.5% |
| 2019-07-01 | 12 / 136 = 8.8% |
| 2020-07-01 | 7 / 136 = 5.1% |
| 2021→2025 | 5 / 3 / 5 / 4 / 1 |
| 2026-07-01 | **0** |
| **all** | 95 / 1,496 = **6.35%** |

By sector: energy **16.4%**, healthcare 7.3%, tech 6.4%, materials 5.3%,
financials 4.5%, consumer 4.1%, industrials 2.3%, utilities **0%**.
By stratum: core 7.7% vs extension 2.5%.

**What it breaks.** A deletion that is (a) monotonically decreasing in
time and (b) outcome-correlated (these are acquisitions and take-privates)
is precisely the shape that makes early folds look different from late
folds for a non-alpha reason. Quoting "32 of 244" invites a reader to
treat it as a flat 13% haircut. The report already says outcome censoring
is unfixable — the missing thing is its *time and sector profile*.
**Confidence:** DEFINITE (measurement). Owner: docs-writer / F5.

### B5. MEDIUM — the filed-span denominator makes a truncated fundamentals tail structurally unobservable

`ingest_fundamentals.py:727-731` trims `target_qs` to
`[min(data_quarters), max(data_quarters)]` — the company's own data — and
`ingest_fundamentals.py:610-614` anchors staleness on
`last_data_quarter`, also the company's own data. Both ends of the check
are defined by the thing being checked, so a truncated companyfacts pull
scores **100% coverage with zero alarm**.

**Measured.** 22 members have ≥1 in-window 10-K/10-Q filed *after* their
last fundamentals fact (23 filings). Worst case: **Citigroup (831001)** —
last fact filed 2026-02-20 across all 796 us-gaap concepts, but 10-Qs
filed 2026-05-07 and 2026-08-06 inside its window; it scores 0.9767 with
12 of 14 families resolved. **EIDP (30554)** is the extreme shape: facts
stop 2019-05-08 while it files 10-Qs through 2026-07-31 — a 2,641-day
truncation, invisible for the same reason (it escapes only because its
window closes in 2019).

The leading edge is clean (0 in-window periodic filings before a member's
first fact), so this is a tail-only hole.

**What it breaks.** The one failure mode this classifier was built for —
"a series that silently freezes" (its own docstring,
`ingest_fundamentals.py:465-471`) — is undetectable at the corpus tail.
No check compares last fact-filed against last in-window periodic filing.
**Confidence:** DEFINITE for the mechanism; magnitude today is small.
Owner: data-engineer (S4).

### B6. MEDIUM — P6 is a per-CIK majority test, so 373 of 398 release-language-missing selections are never named, and three CIKs sit just under the bar

`ingest_metadata.py:2396-2400` and `2523-2527`: flag iff
`missing/measured > 0.5` with `measured >= 4`.

Independently recomputed over all 10,549 high/medium selections:
**398 have no release-language marker beyond the 200-char title region.**
Only Netflix's 25 are reported. The near-misses:

| CIK | | missing/measured | share |
|---|---|---|---|
| 1065280 Netflix | flagged | 25/47 | 53.2% |
| 1038357 Pioneer Natural Resources | **not flagged** | 38/77 | **49.4%** |
| 788784 PSEG | not flagged | 21/45 | 46.7% |
| 713676 PNC | not flagged | 36/91 | 39.6% |

Pioneer is **one filing** from flagging — and Pioneer is independently
implicated in B1 (2 of its selections are cover pages). A systematic
mis-picker that is wrong on a large *minority* of its filings is invisible
by design.

Secondary weakness: `RELEASE_LANGUAGE_MARKERS`
(`ingest_metadata.py:2384-2388`) includes `"conference call"`,
`"investor relations"`, `"webcast"` — boilerplate that appears in
supplemental packages and financial-schedule exhibits, so a P6 *pass* is
weak evidence.

`data/F2_INGESTION_REPORT.md:390` reports "exactly 1 flagged CIK" with no
near-miss line, while §7 item 3 proposes a just-below-threshold line for
the *blocker* table. The same argument applies here and was not made.
**Confidence:** DEFINITE. Owner: data-engineer (S3) + docs-writer.

### B7. MEDIUM — P3's docstring presents its own trigger's hit count as the size of the defect class

`ingest_metadata.py:2298-2326`; the trigger is
`_PRESS_RELEASE_DESC_RE = \b(press|news|earnings)\s+release\b`
(`:2291`) matched against the index row's **description**. Its docstring
(`:2308-2313`) says "MEASURED over all 10,569 earnings 8-Ks (2026-08-24,
offline): 3 hits."

That is 3 hits *for this trigger*, not 3 instances of the defect. The
defect class — an earnings exhibit whose type string falls outside
`^EX-99(\.\d+)?$` — is **38 filings**; P3 sees only those whose filer
happened to write a descriptive description. The 14 in B1 all have
descriptions like `EXHIBIT 99..1` / `EX-99.1` / `EXHIBIT 1`.

`data/F2_INGESTION_REPORT.md:360-362` inherits the framing ("It found
ONEOK and Micron within minutes of existing. It stays armed for future
instances") — armed against one narrow shape, not the class.
**Confidence:** DEFINITE. Owner: data-engineer (S3) + docs-writer.

### B8. MEDIUM — no point-in-time rule is pinned for the three places the corpus is PIT-capable but ambiguous

F2 stores the right raw material and then stops. HANDOFF's
"`filing_date`, never `report_date`" is necessary and not sufficient.

**(a) Post-close acceptance.** `acceptance_datetime` is stored (UTC).
**20,715 of 45,545 filings (45%)** are accepted at 20:00–21:00 UTC —
16:00–17:00 ET, i.e. **after the close** — while carrying the same
`filing_date`. Nothing states whether the tradable date is `filing_date`
or `filing_date + 1`. A feature dated `filing_date` matched to a return
starting `filing_date` is a one-day look-ahead on nearly half the corpus.

**(b) Two filings whose `filing_date` predates their acceptance by
1–2 years**, both **Salesforce (CIK 1108524), a core member**:
`0001108524-22-000007` (10-Q, filing_date 2020-06-01, accepted
2022-02-24, +633 d) and `0001108524-22-000008` (10-K, filing_date
2021-03-17, accepted 2022-02-24, +344 d). No check asserts
`acceptance_datetime >= filing_date`. Whatever the EDGAR-side cause, the
bytes now served under those accessions were not public on their
`filing_date`.

**(c) Restatements.** **20,027 of 273,268 (cik, concept, unit, period)
groups (7.3%)** carry more than one distinct `value` across filings.
`extract_concept_facts` (`ingest_fundamentals.py:320-355`) correctly keeps
every filed occurrence with its `filed` date — the parquet *is*
PIT-capable — but neither `concept_resolution.csv` nor the report pins the
as-of selection rule. A naive latest-value join is look-ahead on 7.3% of
period-cells.

**What it breaks.** All three are downstream (F5) failures that F2 makes
possible and does not close off. The report's caveat list (§9) contains
none of them. **Confidence:** DEFINITE for the measurements; the *harm*
depends on F5. Owner: docs-writer (caveats) + F5.

### B9. MEDIUM — current-SIC sector is not "confined to the sector label"; it decides membership

`data/F2_INGESTION_REPORT.md:623-625` (§9 item 10): *"Sector labels come
from current SIC codes — a small, stated look-ahead confined to the sector
label, not to membership."*

Re-derived from `hybrid136_panel.parquet`: membership is a **fixed
per-sector quota** — 20/20/20/20/12/12/20/12 = 136 at **every one of the
11 reconstitution dates**. And `sector` is constant per CIK across all 11
dates (0 CIKs with >1 sector, 0 with >1 SIC), i.e. assigned once from the
current SIC.

Therefore the bucket a company competes in at 2016-07-01 — and so whether
it makes the top-20 there — is decided by its **2026** SIC code. The
look-ahead propagates into membership, not merely the label.

I cannot measure how many members actually reclassified (the artifacts
carry only the current SIC), which is itself the point: the claim is
asserted, not measured. **Confidence:** DEFINITE that the mechanism
contradicts the sentence; UNMEASURED magnitude. Owner: docs-writer, and
possibly an owner-visible item.

### B10. MEDIUM — the §3.1 bankruptcy justification is factually wrong on two counts

`data/F2_INGESTION_REPORT.md:214-217`: *"clipping would have silently lost
the corpus's only bankruptcy (CIK 895126 first qualifies as a member at
2026-07-01, so its 2020-06-28 item-1.03 filing sits outside its own
coverage window)."*

`distress_events` holds **two** item-1.03 rows for CIK 895126:
`0001104659-20-077745` (**2020-06-29**) and `0000895126-21-000016`
(2021-01-19). The report's own §1 table says "2 / 1". **No filing dated
2020-06-28 exists.** Also, 895126's coverage window is
2024-07-01 → 2026-08-31, so *both* filings are outside it — the argument
is stronger than stated, but the facts quoted to support the ratified
shared-window ruling are wrong. The same wrong singular appears in
`data/f2/F2_SPEC.md` §11 (first amendment) and `F2_PROGRESS.md:191-194`.
**Confidence:** DEFINITE. Owner: docs-writer + main session.

### B11. MEDIUM — a core member reports 100% of its fundamentals in CAD and nothing records it

CIK **895728 (Enbridge, core / energy)**: 2,413 `CAD` + 209 `CAD/shares`
rows and **zero USD rows** for any monetary concept. It is the only
non-USD reporter in the corpus.

`classify_universe` builds `quarters_by_tag` grouping by `concept` alone
(`ingest_fundamentals.py:702-705`) — `unit` is never consulted — and
`concept_resolution.csv` has no unit column. Enbridge resolves cleanly and
its price series (`ENB`, NYSE) is USD.

**What it breaks.** Any fundamentals-to-price quantity for Enbridge
(P/E, P/B, market-cap-to-book, EPS yield) is wrong by the CAD/USD rate,
silently, with no marker anywhere. The same blind spot would mix currencies
within one series for any future filer that switches reporting currency.
Also worth an owner note: F1's float ranking that placed Enbridge in the
**core** stratum rests on the same currency question.
**Confidence:** DEFINITE (measurement); harm is F5-conditional.

### B12. LOW — "absence never censors" is the residual APC surface, and its one live instance was caught by luck

`ingest_prices.py:330-334`: if the chosen symbol is absent from
`company_tickers.json`, the resolution proceeds ("absence never
censors"). Exactly **one** member took that branch — **EA (712515)**, a
delisted member whose ticker survived in `submissions.json` but not in the
bulk map. It was fetched and returned a 6-row post-take-private stub.

It was caught by `missing_in_window` (`ingest_prices.py:1125-1136`), a
*coverage* tripwire, not by the identity rule. Had Yahoo returned a long
series for a reassigned `EA`, nothing would have fired:
`starts_after_coverage_start` (`:1154`) only triggers on a *late* start,
which a reassigned long-history symbol would not have; `meta_symbol` would
match; `instrumentType` would be EQUITY.
**Confidence:** DEFINITE for the gap; no live wrong-series instance found.

### B13. LOW — the price parquet has no per-CIK validity floor, and at least one series predates its own registrant

`prices_e2.parquet` stores full history with no marker of when the CIK's
security began. **DuPont de Nemours (CIK 1666700)** carries `DD` back to
**1972-06-01** — a series that belongs to the old E.I. du Pont, whose CIK
(30554) is itself censored in this corpus. Today it is out of window
(coverage_start 2018-07-02), so there is no live defect; nothing prevents
a downstream query that does not clip to the coverage window from reading
another company's history under this CIK.
**Confidence:** DEFINITE that the floor is absent; no current harm.

### B14. LOW — split-adjusted-as-of-fetch levels are a level-side look-ahead, unstated

`price_client.parse_yahoo_chart` (`price_client.py:380-400`) stores
split-adjusted, non-dividend-adjusted OHLC. Returns are invariant, so this
is harmless for return features. But the *levels* are adjusted using
splits that happen **after** any historical date, so any level-based
screen (price thresholds, "penny-stock" filters, absolute price bands) is
retroactively informed by the future. `data/F2_INGESTION_REPORT.md:446-448`
states the dividend caveat and not this one.

### B15. LOW — YTD/annual durations count as quarterly coverage; the resolution CSV carries no duration rule

`_quarter_bucket` (`ingest_fundamentals.py:1166-1170`) buckets on
`period_end` only, so a 12-month or 9-month fact "covers" the quarter it
ends in. Measured on `Revenues` in 10-Qs: 11,999 quarterly-length /
4,055 H1 / 3,942 9M / 20 FY. Exactly one member — **CIK 32604 Emerson
Electric** — never reports a ~quarterly `Revenues` duration in a 10-Q, yet
resolves `SINGLE / Revenues`. `ConceptResolution`'s docstring
(`ingest_fundamentals.py:516-526`) promises `tags` is "the resolution
itself — the tag … a downstream consumer should build the series from",
which carries no duration or unit rule.

### B16. LOW — the corpus is not reproducible in the sense the spec claims

`data/f2/F2_SPEC.md:167-171` justifies the fixed `CORPUS_WINDOW_END =
2026-08-31` as *"reproducibility … a re-run in October yields the same
corpus."* The freeze date is **in the future** relative to the run
(observed max `filing_date` 2026-08-24), so a re-run today already differs
from the spec's own offline measurement: 45,622 → 45,632. The report's §1
reconciliation paragraph handles this honestly; the spec's rationale is
false until 2026-08-31 passes.

### B17. LOW — `validation_exceptions.csv` lacks the code-side ratification gate its two sibling override files have

`load_validation_exceptions` (`ingest_metadata.py:1438-1504`) validates
columns, check names, mandatory reason/evidence, the PIT guard
(`evidence_filed < effective_from`) and duplicates — but there is **no
`RATIFIED_*` set** requiring a deliberate code edit, unlike
`RATIFIED_OVERRIDE_CIKS` (`ingest_prices.py:168`) and
`RATIFIED_EARNINGS_DOC_OVERRIDES`. The file's own header claims
`cik … Must be a member` — not enforced in code. The file ships empty, so
nothing is live; the asymmetry is the finding.

### B18. LOW (lazy-elite) — eleven pinned count constants for one stage, most algebraically redundant

`ingest_prices.py:134-138, 153-161, 168, 198-199` define
`EXPECTED_RESOLVED`, `EXPECTED_OVERRIDES_APPLIED`, `EXPECTED_FETCHABLE`,
`EXPECTED_CENSORED`, `EXPECTED_CENSORED_BY_STRATUM`, `EXPECTED_FETCHED`,
`EXPECTED_UNFETCHABLE`, `EXPECTED_NO_USABLE_PRICES`,
`EXPECTED_NO_USABLE_BY_STRATUM`, `EXPECTED_NO_COVERAGE_CIKS`,
`CENSUS_EXPECTED_{RESOLVED,CENSORED}_BY_E2`. Three identities hold by
construction:
`EXPECTED_FETCHABLE == EXPECTED_FETCHED == EXPECTED_RESOLVED + EXPECTED_OVERRIDES_APPLIED`;
`EXPECTED_CENSORED == EXPECTED_UNFETCHABLE`;
`EXPECTED_NO_USABLE_PRICES == EXPECTED_UNFETCHABLE + len(EXPECTED_NO_COVERAGE_CIKS)`.
An editor who updates one and not its twin gets either a contradictory
FATAL or a set of constants that agree with each other and not with the
data. One independent pin plus derived values would carry the same
tripwire value.

### B19. LOW (lazy-elite) — ceremony around the override files, minus the one check that mattered

The 2-row `price_ticker_overrides.csv` is guarded by
`RATIFIED_OVERRIDE_CIKS`, `MIN_OVERRIDE_EVIDENCE_CHARS = 80`,
`OVERRIDE_COLUMNS`, `DELIBERATELY_CENSORED_CIKS`,
`EXPECTED_OVERRIDES_APPLIED`, a fired/DEAD report
(`ingest_prices.py:846-860`) and a ~40-line CSV comment header — while the
single check that would have caught B3 (does the override's symbol map to
a *different* CIK in `company_tickers.json`?) is one line and absent. Same
shape in `ingest_metadata.py` for the 4-row earnings override file.

### B20. LOW — ledger/report numbers that disagree with the artifacts

- `F2_PROGRESS.md:403-404` says "thin = 49". DB and my recomputation say
  **50** (`universe_validation_problems` `ex99_thin_exhibit` = 50). The
  report §5 says 50 — the ledger is the stale one.
- `data/F2_INGESTION_REPORT.md:398` "Prologis is clean post-fix (0 of 44
  missing)". Measured: **45 measured, 0 missing**.
- `F2_PROGRESS.md:82` states "final: 45,632 filings" flatly. 45,632 is the
  *enumerated* count; `filings` holds 45,545 and the remaining 87 are
  co-registrant attributions. The report distinguishes them correctly
  (§1); the ledger conflates them.
- `data/f2/status/S6_runs.md:33-34` "20,218/45,632 filings outside every
  membership spell". Re-derived over the `filings` table alone:
  **20,165 / 45,545 = 44.3%**. The two denominators differ by the 87
  co-registrant rows; neither is labelled as which.

### B21. LOW — 8-K-sourced facts count toward fundamentals coverage

`OPERATING_FORMS` (`ingest_fundamentals.py:494`) admits `8-K`. 12,172
parquet rows come from 8-Ks (plus 345 DEF 14A, 343 40-F, 245 6-K, 20 PRE
14A, 6 20-F, 5 DEFR14A which are correctly excluded from the classifier).
So a family can clear the 75% bar on earnings-release facts rather than
periodic-filing facts. Defensible, but the constant's docstring only
argues the DEF 14A exclusion (HANDOFF §2a trap (c)) and never states that
8-K facts are admitted deliberately.

---

## Section C — how to reproduce

Every measurement above came from read-only queries against
`data/filings_metadata_e2.db` (`file:…?mode=ro`),
`data/fundamentals_e2.parquet`, `data/prices_e2.parquet`,
`data/universe_e2_candidates/hybrid136{,_panel}.parquet`,
`data/f2/*.csv`, `data/raw/submissions/`, `data/raw/companyfacts/` and
`data/raw/documents/`. No file was modified. No network request was made.
The classifier re-derivation is a standalone reimplementation from the
spec text (families + preference order read from
`ingest_fundamentals.CONCEPT_FAMILIES`, algorithm written independently);
it agrees with the shipped CSV on all 3,416 pairs.

