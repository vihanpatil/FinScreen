# S6 — F2_SPEC §4.4 item 4: the mandatory manual EX-99 read

**Agent:** extraction-qa-engineer (Opus). **Date:** 2026-08-24.
**Brief:** `data/f2/status/S6_ex99_read_brief.md`.
**Mode:** strictly read-only. **Zero live network GETs.** No code edits, no
DB writes (`data/filings_metadata_e2.db` opened `file:...?mode=ro` only), no
`F2_PROGRESS.md` edits. Everything below came from
`data/raw/filing_index/`, `data/raw/documents/`,
`data/f2/ex99_selection_audit.csv`, and
`data/f2/s6_segment1_metadata_attempt2.log`.

---

## 0. Headline

**17 CORRECT / 2 WRONG / 1 AMBIGUOUS** over the worst-20 CIKs.

The two WRONG selections are **not** noise, and neither is the kind of thing
the low-confidence flag reliably catches:

- **Prologis (CIK 1045609) — systematically picks the wrong exhibit.**
  EX-99.1 is the *Supplemental Information* data package; the press release
  is EX-99.2. Measured over the filer's own cached documents: **39 of 45
  Prologis earnings-8-K selections contain no press-release text at all**,
  and **37 of those 39 are HIGH confidence**. Only 2 were flagged low — the
  read caught this by luck, not by design.
- **NVIDIA (CIK 1045810), 2019-11-14 — a filer type-string typo defeats the
  policy.** The release is `q3fy20pr.htm`, typed `EX-95.1` (transposed from
  EX-99.1) and described "Q3FY20 PRESS RELEASE". The policy skipped it and
  took `EX-99.2` = "Q3FY20 CFO COMMENTARY". n=1.

The 8-sector high-confidence coverage assertion **PASSED, 0 problems** —
independently re-derived, not taken from the log (§4).

---

## 1. What I actually read

Per §4.4 and the standing "report what you read, not just counts" rule.

**By eye, in full or in substantial part (28 documents):** the cached filing
index HTML plus the cached selected document for each of the 20
representative filings in §2, plus 8 extra documents pulled in while
chasing findings — J&J `0000200406-19-000063` (EX-99.2 schedules-only 8-K),
Prologis `0000950170-23-013170` and `0001564590-16-011971` (to date the
Supplemental/Release split), AT&T's sibling-accession index rows, and the
near-empty exhibits from Linde `0001654954-19-012971`, Cigna
`0000950159-22-000107`, PNC `0001193125-16-556144`, MetLife
`0001099219-23-000041` (§5.3).

**By script, read-only, over cached bytes (no network):**

- content screen of **all 9,981 cached selected `EX99_PRESS_RELEASE`
  documents** for press-release language (361 selections have no cached
  document and were skipped, counted, and are excluded from every rate
  below);
- index-metadata screen of **all 10,569 earnings 8-Ks** for "a non-selected
  document whose index description says press/news/earnings release";
- a length screen for near-empty selected documents;
- a same-day duplicate-8-K screen.

Screens are triage, not verdicts. Every claim in §3 is backed by a document
I read, not by a screen hit.

**Filing choice rule:** one representative per CIK, preferring a
low-confidence selection over an 8K_BODY fallback (brief item 1), and
preferring a pre-2019 filing where the CIK had one — 11 of the 20 are
2015–2019, which is where E2's new dialect risk lives.

---

## 2. Verdict table (20 rows)

Ordered as the log's worklist prints them: the 10 CIKs with ≥1
low-confidence selection first (descending count), then the 10
highest-CIK-ordered `8K_BODY`-only filers that fill the cap.

| # | CIK | Name | Sector / stratum | Filing read (accession, date) | Selection | Conf | Verdict | Note |
|---|---|---|---|---|---|---|---|---|
| 1 | 200406 | JOHNSON & JOHNSON | healthcare / core | `0000200406-17-000002`, 2017-01-24 | `a8k2016q4exhibit9915.htm` (EX-99.15) | low | **CORRECT** | J&J types the release `EX-99.15` and the 2.5 MB financial schedules `EX-99.2O` (letter O). The picked file opens "Johnson & Johnson Reports 2016 Fourth-Quarter Results". Low confidence is a true "I don't recognise this type" — the right behaviour, wrong-looking outcome. |
| 2 | 1032208 | SEMPRA | utilities / **extension** | `0000086521-16-000118`, 2016-08-04 | `exhibit991.htm` (bare EX-99) | low | **CORRECT** | Two bare `EX-99` rows; the index *description* column carries "EXHIBIT 99.1" / "EXHIBIT 99.2". Picked file opens "NEWS RELEASE … SECOND-QUARTER 2016 EARNINGS". |
| 3 | 1045609 | Prologis, Inc. | materials_realestate / **extension** | `0000950123-18-006811`, 2018-07-17 | `pld-ex991_6.htm` (bare EX-99, desc "EX-99.1") | low | **WRONG** | Picked document is "Prologis Supplemental Information Second Quarter 2018 Unaudited" — a table-of-contents + metrics package, 10,088 chars, zero press-release language. **Better document present and missed: `pld-ex992_7.htm` (EX-99.2).** See §3.1 — this is systematic, not per-filing. |
| 4 | 80661 | PROGRESSIVE CORP/OH/ | financials / core | `0000080661-17-000023`, 2017-04-18 | `exhibit99march2017earnings.htm` (EX-99.0) | low | **CORRECT** | Sole EX-99-family row in the filing; opens "NEWS RELEASE / The Progressive Corporation". `EX-99.0` is unrecognised by design (diagnosis §2.3), so it fell to low. |
| 5 | 106535 | WEYERHAEUSER CO | materials_realestate / **extension** | `0000950170-23-015328`, 2023-04-27 | `wy-ex99_1.htm` (bare EX-99, desc "EX-99.1") | low | **CORRECT** | Opens "Weyerhaeuser Reports First Quarter Results … SEATTLE, April 27, 2023 – … today reported". |
| 6 | 732717 | AT&T INC. | utilities / **extension** | `0000732717-19-000048`, 2019-10-28 | `ex99_1.htm` (typed **EX-99.2**) | low | **AMBIGUOUS** | This filing genuinely contains **no** press release: its only exhibits are EX-99.2 "SELECTED FINANCIAL STATEMENTS AND OPERATING DATA" (the pick — 31,348 chars of pure tables, zero narrative) and EX-99.3 "DISCUSSION AND RECONCILIATION OF NON-GAAP MEASURES". No better in-filing document exists, so it is not a mis-pick; but typing it `EX99_PRESS_RELEASE` is a **silent mis-label**. The real Q3-2019 release is in the same-day sibling accession `0000732717-19-000049` (EX-99.1 "AT&T INC. 3RD QUARTER 2019 PRESS RELEASE"), already resolved at high confidence — so the corpus loses nothing by failing this row, and gains a garbage "press release" by keeping it. |
| 7 | 766704 | WELLTOWER INC. | materials_realestate / **extension** | `0000766704-16-000051`, 2016-02-18 | `Ex-99.1.htm` (bare EX-99, desc "EX-99.1") | low | **CORRECT** | Opens "FOR IMMEDIATE RELEASE / February 18, 2016". (Welltower is the one CIK on the worklist for *both* triggers; its 8K_BODY filing `0001193125-19-013531` has no EX-99 row in the cached index at all — checked.) |
| 8 | 1035267 | INTUITIVE SURGICAL INC | healthcare / core | `0001035267-25-000005`, 2025-01-15 | `q424ex-991q4prexreleaseq4o.htm` (bare EX-99, desc "EX-99.1") | low | **CORRECT** | Opens "INTUITIVE ANNOUNCES PRELIMINARY FOURTH QUARTER AND FULL YEAR 2024 RESULTS". (It is the *preliminary* pre-JPM-conference release, which is what this 8-K is; the full Q4 release is a separate later 8-K.) |
| 9 | 1045810 | NVIDIA CORP | tech / core | `0001045810-19-000168`, 2019-11-14 | `q3fy20cfocommentary.htm` (EX-99.2) | low | **WRONG** | Picked document is "CFO Commentary on Third Quarter Fiscal 2020 Results". **Better document present and missed: `q3fy20pr.htm`, index description "Q3FY20 PRESS RELEASE", typed `EX-95.1`** — a filer typo for EX-99.1 that put the release outside the policy's type family. See §3.2. |
| 10 | 1364742 | BlackRock Finance, Inc. | financials / core | `0000950123-17-006151`, 2017-07-17 | `blk-ex991_6.htm` (bare EX-99, desc "EX-99.1") | low | **CORRECT** | Opens "BlackRock Reports Second Quarter 2017 Diluted EPS of $5.22…". |
| 11 | 32604 | EMERSON ELECTRIC CO | industrials / **extension** | `0000032604-19-000022`, 2019-07-29 | `fy2019orders8-kjulyrelease.htm` | 8K_BODY / high | **CORRECT** | Index has exactly one Document-Format row (EDGAR header "Documents: 1"); no EX-99 string anywhere in the cached index. Body carries real Item 2.02 / Item 7.01 content (June-2019 orders + Q3 EPS commentary). |
| 12 | 33213 | EQT Corp | energy / core | `0001104659-22-078814`, 2022-07-11 | `tm2220702d2_8k.htm` | 8K_BODY / high | **CORRECT** | Only the 8-K body + iXBRL data files; no exhibit. Body carries the Item 2.02 disclosure (a preliminary derivatives-loss table). Genuine 8K_BODY, but see §5.4 — this is an item-2.02 8-K that is not a quarterly earnings release. |
| 13 | 45012 | HALLIBURTON CO | energy / core | `0000045012-16-000268`, 2016-01-25 | `hal_12312015-er8k.htm` | 8K_BODY / high | **CORRECT** | Single document, index description "Q4 2015 8-K EARNINGS RELEASE", 47,377 chars containing the full release and tables. This is the pre-2020 lean-index class the segment-1 fix recovered (diagnosis §1.2) — recovered correctly. |
| 14 | 49071 | HUMANA INC | healthcare / core | `0000049071-15-000072`, 2015-07-06 | `humana8-k07062015.htm` | 8K_BODY / high | **CORRECT** | "Documents: 1", no exhibit. Body carries the Item 2.02 guidance update filed alongside the Aetna deal announcement. |
| 15 | 51143 | INTERNATIONAL BUSINESS MACHINES CORP | tech / core | `0001104659-15-051905`, 2015-07-20 | `a15-15649_28k.htm` | 8K_BODY / high | **CORRECT** | No exhibit rows; **IBM embeds the release inside the 8-K body as "ATTACHMENT I — IBM REPORTS 2015 SECOND-QUARTER RESULTS"** (64,016 chars). 8K_BODY is exactly right here and the text is the release. |
| 16 | 59478 | ELI LILLY & Co | healthcare / core | `0000059478-22-000117`, 2022-04-14 | `lly-20220414.htm` | 8K_BODY / high | **CORRECT** | No exhibit. Body is an Item 2.02 non-GAAP-presentation-change notice. See §5.4. |
| 17 | 64803 | CVS HEALTH Corp | consumer / core | `0000064803-22-000002`, 2022-01-11 | `cvs-20220111.htm` | 8K_BODY / high | **CORRECT** | No exhibit. Body carries an Item 2.02 FY2021/FY2022 EPS-guidance raise. |
| 18 | 70858 | BANK OF AMERICA CORP /DE/ | financials / core | `0000070858-24-000006`, 2024-01-08 | `bac-20240108.htm` | 8K_BODY / high | **CORRECT** | No exhibit. Item 2.02 incorporates Item 8.01 (BSBY-cessation accounting impact) by reference. |
| 19 | 72903 | XCEL ENERGY INC | utilities / **extension** | `0000072903-18-000003`, 2018-01-11 | `a8-ktaxreformjan2018.htm` | 8K_BODY / high | **CORRECT** | "Documents: 1", no exhibit. Item 2.02 incorporates the Item 7.01 Tax-Cuts-and-Jobs-Act impact disclosure for FY2017. |
| 20 | 72971 | WELLS FARGO & COMPANY/MN | financials / core | `0000072971-16-000967`, 2016-02-03 | `form8k232016.htm` | 8K_BODY / high | **CORRECT** | "Documents: 1", no exhibit. Item 2.02 restates 2015 results down for a $200 m FHA legal accrual. |

**Tally: CORRECT 17 · WRONG 2 · AMBIGUOUS 1.**

**WRONG list: CIK 1045609 (Prologis) · CIK 1045810 (NVIDIA).**

A cross-check on all ten 8K_BODY picks (rows 11–20, plus Welltower's
`0001193125-19-013531`): I grepped each cached index HTML for any `EX-99`
substring. **All eleven returned zero hits** — the 8K_BODY fallback fired
only where no EX-99 exhibit exists, which is the definition of CORRECT for
this class.

---

## 3. The two WRONG findings, in detail

These are findings for the main session to rule on. **Nothing was fixed.**

### 3.1 Prologis (CIK 1045609) — EX-99.1 is the Supplemental; the release is EX-99.2

**What the picked document is.** Both flagged filings resolve to a document
that is self-titled "Prologis Supplemental Information &lt;quarter&gt;
Unaudited" and consists of a table of contents plus operating/financial
metrics. Full-text search of the 2018 and 2023 picks finds **zero** hits for
"press release", "news release", "earnings release", "today reported",
"Investor Relations", or "conference call".

**Evidence that EX-99.2 is the release** (I could not read EX-99.2 itself —
only the *selected* document per filing is cached, and I may not fetch):

1. **The filer's own index says so.** In Prologis's 2019-10-15 earnings 8-K
   (`0001564590-19-036903`, high confidence), the EX-99.2 row's description is
   literally `PRESS RELEASE, DATED OCTOBER 15, 2019.` — while EX-99.1's
   description is the generic `EX-99.1`, and EX-99.1 is again the
   Supplemental.
2. **The title changed exactly when the split happened.** Through
   2016-04-19 the EX-99.1 is titled "**Earnings Release and** Supplemental
   Information" and contains a "Press Release" entry in its own table of
   contents (2016-01-26 pick: 127,343 chars, hit on "press release"). From
   2016-07-19 onward the title drops "Earnings Release and", and the picked
   documents shrink to ~7k–16k chars with no release language.
3. **Sizes agree.** 2023-04-18: EX-99.1 = 27,830 bytes, EX-99.2 = 111,180
   bytes.

**Blast radius, measured on cached bytes.** Of Prologis's 45 earnings-8-K
selections (all 45 documents cached), **39 contain no press-release
language**: 2016-07-19 through 2026-07-16 continuously, except the two
2018-01-23 / 2018-04-17 filings whose picks do carry release language. **37
of the 39 are `high` confidence.** Only the 2 that happened to be typed
bare `EX-99` instead of `EX-99.1` reached this read.

**Why this matters beyond Prologis.** It is the one finding here that
falsifies an implicit assumption: *the confidence label tracks correctness.*
For this dialect it does not, at all. Any decision to treat "high
confidence" as "no need to look" should be taken knowing that.

### 3.2 NVIDIA (CIK 1045810), 2019-11-14 — release typed `EX-95.1`

The index has exactly three Document-Format rows:

```
seq 1  8-K       FORM 8-K              form8-kq3fy20.htm
seq 2  EX-95.1   Q3FY20 PRESS RELEASE  q3fy20pr.htm        446,146 bytes
seq 3  EX-99.2   Q3FY20 CFO COMMENTARY q3fy20cfocommentary.htm
```

`EX-95.1` is a filer typo (EX-95 is the mine-safety exhibit). The selection
policy searches the EX-99.* family, found only EX-99.2, and took it. The
picked document opens "CFO Commentary on Third Quarter Fiscal 2020 Results"
— a real, useful document, but not the release, and mislabelled as one.

**Blast radius:** n=1. The index-metadata screen over all 10,569 earnings
8-Ks found only 36 filings where a *non-selected* document's description
says press/news/earnings release, across 16 CIKs; I read the shape of all
36 and **33 are benign** (the 8-K cover row is routinely *described*
"…EARNINGS RELEASE 8-K" while the real release is the correctly-picked
EX-99.1 — AvalonBay, Arista, Nucor, ONEOK, Twitter, RTX, Pioneer, Zoetis,
AZEK, Prudential, Lilly; JPMorgan's EX-99.2 is the "Earnings Release
Financial Supplement"; BAC's EX-99.4 is a *buyback* release). The 3 real
hits are NVIDIA 2019-11-14, AT&T 2019-10-28, and Prologis 2019-10-15 — the
first two are rows 9 and 6 of the table, the third is §3.1's smoking gun.
Note the limit of this screen: it can only see defects the filer itself
*labelled*, so it bounds NVIDIA's blast radius at n=1 but says nothing
about Prologis's other 38, whose EX-99.2 descriptions are all generic.

---

## 4. The 8-sector high-confidence coverage assertion — **PASSED (0 problems)**

`check_ex99_sector_coverage()` (ingest_metadata.py:1876) writes
`ex99_sector_coverage` rows into `universe_validation_problems` and prints
nothing when clean — which is why the attempt-2 log contains no "sector"
line. I verified the result three ways rather than reading a silence:

1. **The check ran.** It is called unconditionally at
   `ingest_metadata.py:2533`, before
   `write_validation_problems(..., stage="metadata")`, which rewrites the
   whole `(run_date, stage)` slice. That slice exists for
   `run_date='2026-08-24'` with **37 rows** = 3 `co_registrant_filing`
   (WARN) + 29 `member_stopped_filing` (INFO) + 5 `no_large_filing_gap`
   (WARN). **Zero `ex99_sector_coverage` rows, zero
   `earnings_doc_unresolved` rows.**
2. **Re-derived from the audit CSV, independently of the DB.** All 8
   sectors carry ≥1 `EX99_PRESS_RELEASE` / `high`:

| Sector | Stratum | EX99 high | EX99 med | EX99 low | 8K_BODY high |
|---|---|---:|---:|---:|---:|
| consumer | core | 1,447 | 0 | 0 | 6 |
| energy | core | 1,202 | 0 | 0 | 130 |
| financials | core | 1,706 | 0 | 2 | 21 |
| healthcare | core | 1,367 | 0 | 19 | 31 |
| tech | core | 1,705 | 0 | 1 | 21 |
| **industrials** | **extension** | **835** | 0 | 0 | 7 |
| **utilities** | **extension** | **900** | 16 | 6 | 7 |
| **materials_realestate** | **extension** | **1,132** | 0 | 4 | 4 |

   The three **extension** sectors — the ones E1's policy had never seen —
   are the *lowest* three counts but still clear the bar by 3 orders of
   magnitude. Neither FATAL arm ("earnings 8-Ks seen but zero high-conf")
   nor WARN arm ("zero earnings 8-Ks at all") can fire.
3. **The universe really has 8 sectors** (`companies` and
   `universe_membership` agree: consumer 33, energy 32, financials 37,
   healthcare 32, industrials 19, materials_realestate 28, tech 42,
   utilities 21 = 244 members), so "8 sectors" is the right denominator.

**Caveat on what this assertion proves.** It is a *coverage* assertion, not
a *correctness* one: it asks whether the policy produced high-confidence
picks in every sector, not whether those picks are right. Prologis is a
materials_realestate member with 37 high-confidence wrong picks and the
sector still passes with 1,132 high-confidence selections. The assertion did
its job; it just is not evidence about §3.1.

Two reconciliations while I was in the CSV, both benign: the audit covers
**243 of 244** members — the missing one is CIK 1222333 **SPDR GOLD TRUST**,
which filed 65 filings and **zero** item-2.02 8-Ks (an ETF trust; nothing to
select from). And the worklist's 71 = 10 low-confidence CIKs ∪ 62 8K_BODY
CIKs, overlapping in exactly one member, **CIK 766704 Welltower**, which
carries both triggers.

---

## 5. Coverage honesty — what this read does NOT cover

### 5.1 51 of the 71 flagged CIKs were not read

The worklist is **71 CIKs**; the read is capped at the **20 worst by
low-confidence count**; **51 CIKs remain unread and are not covered by any
verdict in this document.** Nothing here should be quoted as clearance of
the flagged population. Concretely, the 20 read cover **all 10** CIKs with
any low-confidence selection (so all 32 low-confidence filings are
represented by 10 read filings), and **10 of the 62** `8K_BODY` CIKs — so
**52 of the 62 8K_BODY CIKs and 217 of the 227 8K_BODY filings are
unread**.

Evidence that the unread 8K_BODY remainder is *probably* fine, offered as
prior, not as verification: all ten 8K_BODY filings I did read had zero
`EX-99` strings in the cached index, and the class was already
characterised uniformly in the segment-1 diagnosis (§1.2, all 64 recovered
filings with an identical 2-row shape).

### 5.2 The worklist trigger has a blind spot: `medium` confidence

The §4.4 trigger is "any low-confidence selection **or** any 8K_BODY
fallback". **`medium` is not a trigger.** There are **16 medium-confidence
`EX99_PRESS_RELEASE` selections, all at CIK 72741 EVERSOURCE ENERGY**
(utilities, extension) — Eversource files the release, the financial report
and the slide deck all as bare `EX-99`, separated only by description
(diagnosis §2.4). Eversource is **not on the 71-CIK worklist at all** and
therefore could not be read here. Flagging the gap; not proposing a rule
change.

### 5.3 A class the flags miss entirely: selected documents with no extractable text

Screening all 9,981 cached selected `EX99_PRESS_RELEASE` documents by
length: **44 have fewer than 1,500 characters of extractable text, and 12
have fewer than 100.** All are `high` confidence. Two distinct causes, both
read directly:

- **Image-only exhibits** — the EX-99.1 HTML is a wrapper around slide
  JPEGs, so tag-stripping yields nothing. Linde `0001654954-19-012971`
  (13,058 bytes, **14 `<img>`, 48 chars of text**), PNC ×7 (2016–2019,
  58–77 chars), MetLife `0001099219-23-000041` (67 chars), Ford
  `0000037996-19-000005` (78 chars), Digital Realty `0001297996-16-000203`
  (574 chars).
- **A genuinely empty exhibit at the source** — Cigna
  `0000950159-22-000107`'s `ex99-1.htm` is **454 bytes total**, no images,
  body content is two `&nbsp;` paragraphs and the string "Exhibit 99.1".
  This is what EDGAR holds; it is not a cache defect.

The selection is *defensible* in each case (it is the only EX-99 present),
but the resulting section will be empty or near-empty. **This is exactly
what F3's `MIN_SECTION_WORDS` floor should catch and FAIL loudly** — and it
is a concrete reason not to lower that floor to make failures disappear:
these 44 rows *should* fail. Naming them now so a future recalibration has
to argue past them rather than around them.

### 5.4 Not every item-2.02 8-K is a quarterly earnings release

Of the 20 filings read, **6 are item-2.02 8-Ks that are not quarterly
earnings releases**: EQT (derivatives-loss preliminary table), Emerson
(monthly orders), Lilly (non-GAAP presentation change), CVS (guidance raise
at an investor webcast), BAC (BSBY-cessation accounting), Xcel (tax-reform
impact), Wells Fargo (FHA legal accrual restating prior-quarter results).
The selection is right in all six; the *corpus assumption* that
`has_earnings_item=1` ≈ "quarterly earnings release" is what is loose.
Also measured: **61 (CIK, filing_date) pairs hold more than one earnings
8-K — 122 filings** (PNC 29, Digital Realty 8, PPL 4, Allergan 3,
MercadoLibre 2, then singletons incl. AT&T and IBM). Both facts are F3/F5
inputs (dedup grain, section labelling), not selection defects.

### 5.5 Things I could not check

- **Rival documents are not cached.** `data/raw/documents/` holds only the
  *selected* document per filing, so for every "a better document was
  present" claim I could read the index row (type, description, size) but
  not the rival's text. The Prologis conclusion therefore rests on the
  evidence chain in §3.1, not on reading `pld-ex99_2.htm`. Confirming it
  costs one cached-index-free GET, which is the main session's call, not
  mine.
- **361 selections have no cached document** and were skipped by every
  content screen. They are not "clean"; they are unmeasured.
- I did not verify the 51 unread CIKs, the 16 Eversource medium rows, or
  any filing outside the 20 + 8 documents named in §1.

---

## 6. Proposed dialect handlers — PROPOSALS ONLY, nothing implemented

No code was changed. Each is deliberately small, named, and single-purpose
per the lazy-elite rule; each is stated with the evidence that motivates it
and with what it must **not** do.

**P1 — `_exhibit_number_from_description()` (confidence only, never the
pick).** When `doc_type` is a bare `EX-99`, parse the sub-number out of the
index *description* (`EXHIBIT 99.1`, `EX-99.1`) and use it exactly as if it
had been in the type column. Evidence: rows 2, 5, 7, 10 above (Sempra,
Weyerhaeuser, Welltower, BlackRock) are all correct picks demoted to `low`
purely because the number lives one column over. Would convert ~11 of the
32 remaining low-confidence filings to high **with no change of file**.
Must not: invent a number where the description has none (Prologis's
generic `EX-99.1` description would still be parsed as 99.1 — see P2, which
is why P1 alone is *not* enough).

**P2 — `PROLOGIS_SUPPLEMENTAL` per-filer handler (changes the pick — needs
an owner ruling).** For CIK 1045609, filings from 2016-07-19 onward: prefer
`EX-99.2` over `EX-99.1`. This is the one proposal that changes a document
selection, on ~39 filings, and I am deliberately *not* proposing a clever
general rule ("prefer the exhibit whose text looks like a release") — that
would re-open every one of the 9,981 currently-correct picks. One named
filer handler, dated, with the 2019-10-15 index description quoted in its
docstring as the evidence. **Blocked on confirming EX-99.2's content**
(§5.5).

**P3 — `_press_release_by_description_outside_ex99()` (fail-loud, not
fix-quietly).** When no EX-99.* candidate exists but some other
Document-Format row's description matches `/press release/i`, do **not**
silently take an unrelated EX-99.x. Either name that row as the pick at
`low` confidence, or emit a FAIL row with the reason. Evidence: NVIDIA's
`EX-95.1` typo (n=1 measured). Given n=1, the FAIL variant is the honest
default; a section that fails loudly beats a CFO-commentary document
labelled as a press release.

**P4 — `EX99_FINANCIAL_SCHEDULES` as a distinct `section_type` (typing, not
selection).** Today a filing whose only EX-99 is a tables-and-schedules
exhibit gets typed `EX99_PRESS_RELEASE` and looks clean. Measured
instances: AT&T `0000732717-19-000048` (row 6), J&J
`0000200406-19-000063` (an Item 2.02/7.01 re-filing whose only exhibit is
EX-99.2 "Condensed Consolidated Statement of Earnings" — J&J's real
Q3-2019 release is in `0000200406-19-000061`, resolved high). Both are
supplemental siblings of a same-day release that the corpus already holds,
so the cost of typing them honestly is zero and the benefit is that F3 never
runs a press-release extractor over a table dump. Cheap discriminator that
does not need an LLM: no `<p>`-level narrative and a numeric-token share
above ~0.5.

**P5 — an image-only / empty-exhibit detector at *ingest* time, reported not
suppressed.** Count `<img>` tags and extractable characters for the selected
document and record it; ≥N images with <100 chars of text is an
`ex99_image_only_exhibit` WARN. Evidence: §5.3's 12 documents. This is not
a fix — the pick is already the only option — it exists so the class is
**counted and named** at the point of selection rather than rediscovered as
anonymous length-floor failures in F3.

**Explicitly not proposed:** loosening any threshold, widening the EX-99
type family (that is how P3's typo would become a silent mis-pick
generator), or a universal "pick the exhibit that reads like a release"
scorer.

---

## 7. Resume state

This document is the deliverable; nothing is partial. No repo file other
than this one was created or modified. The throwaway read-only helper used
for the reads lives in the session scratchpad at
`/private/tmp/claude-501/-Users-vihanpatil-personal-projects-FinScreen/56426783-64ca-4155-8fbf-a11a57913516/scratchpad/peek.py`
(prints a cached filing index + a cached document's text, given an
accession); it is ~100 lines and trivially re-derivable from §1's
description. The DB was opened read-only and not written to.

---
---

# VERIFICATION PASS — 2026-08-24 (later), post-fix-package

Requested by the main session after the six-part fix package + four-row
`data/f2/earnings_doc_overrides.csv` were ruled (`F2_PROGRESS.md` §5, three
dated entries from "EX-99 manual-read fix package"; implementation
`S3_metadata_documents.md` §11–§12), segment 1 re-ran (attempts 3–4), and
the newly-selected documents were cached by the segment-2 delta.

**Task:** content-verify the five ruled filers by reading the *actual*
newly-cached documents, and spot-confirm the final selection distribution.
**Mode:** read-only, unchanged. **Zero live GETs** — every document below
was read from `data/raw/documents/`. No code edits, no DB writes, no
`F2_PROGRESS.md` edits. `ingest_metadata.py` was read (handler + screen
definitions) but not modified.

**Overall: PASS, with one narrow residual defect (n=1) found — §V.3.**

## V.1 Per-filer verdicts (5 rows)

| # | Filer | What was verified | Verdict |
|---|---|---|---|
| 1 | **Prologis** (1045609) | 8 of the 41 corrected EX-99.2 picks read in full across the required spread — 2016-07-19, 2016-10-20, 2019-01-22, 2019-10-15, 2022-04-19, 2023-04-18, 2025-04-16, 2026-07-16. **Every one opens "FOR IMMEDIATE RELEASE / Prologis Reports &lt;quarter&gt; … Results / SAN FRANCISCO (&lt;filing date&gt;) – Prologis, Inc. (NYSE: PLD) … today reported"**, with the dateline matching the filing date in all 8. Then widened to **all 45** Prologis selections (all 45 cached, 0 missing): 43 match a narrow release-language regex; **both non-matches were then read by eye** — 2016-01-26 does contain the release (my regex was too narrow) and 2016-04-19 does not (§V.3). | **CONFIRMED** — all 41 corrected picks are genuinely the earnings press release; 3 of the 4 deliberately-unchanged pre-split picks are correct as-is, the 4th is §V.3. |
| 2 | **NVIDIA** `0001045810-19-000168` → `q3fy20pr.htm` | 17,385 chars. Opens "FOR IMMEDIATE RELEASE: NVIDIA Announces Financial Results for Third Quarter Fiscal 2020 / SANTA CLARA, Calif.- Nov. 14, 2019 - NVIDIA (NASDAQ: NVDA) today reported revenue for the third quarter ended Oct. 27, 2019, of $3.01 billion…", with the Jensen Huang quote. Selection now `EX99_PRESS_RELEASE`/`high`. | **CONFIRMED** — is the Q3 FY20 earnings release. |
| 3 | **ONEOK** `0001039684-15-000073` → `okeq32015earningsreleasenr.htm` | 55,429 chars. Document's own body reads "**Exhibit 99.1** / November 3, 2015 / … ONEOK Announces Third-quarter 2015 Results / TULSA, Okla. - Nov. 3, 2015 - ONEOK, Inc. (NYSE: OKE) today announced third-quarter 2015 financial results." The `EX-95.1` type is confirmed a filer typo **by the document itself**, which is stronger evidence than the index-metadata standard the override row was written to. Replaces the previous pick, the 3,179-char 8-K cover page. | **CONFIRMED** |
| 4 | **Micron** `0000723125-19-000172` → `a2020q1exhibit991-pres.htm` | 19,730 chars. Body reads "**Exhibit 99.1** / FOR IMMEDIATE RELEASE / … MICRON TECHNOLOGY, INC. REPORTS RESULTS FOR THE FIRST QUARTER OF FISCAL 2020 / BOISE, Idaho, December 18, 2019 – Micron Technology, Inc. (Nasdaq: MU) today announced results…". The `EX-99..1` double-dot is likewise confirmed a typo by the document's own self-label. Replaces the previous 3,499-char cover page. | **CONFIRMED** |
| 5 | **AT&T** `0000732717-19-000048` (exclusion) | Exclusion is recorded in **both** places: `ex99_selection_audit.csv` carries one `EXCLUDED_BY_OVERRIDE` / `override` row for CIK 732717, `n_filings=1`, `first_seen_year=2019` (the only such row in the file); `universe_validation_problems` carries one `earnings_doc_excluded_by_override` **INFO** row naming the accession and quoting the reason. The DB row's `earnings_doc_*` columns are NULL — the exclusion is evidenced, not a silent NULL. AT&T's remaining **47** selections are all `EX99_PRESS_RELEASE`/`high` (47 + 1 excluded = 48 earnings 8-Ks ✓), release-language 47/47 measured, 0 missing. **Sibling `0000732717-19-000049` re-read in full**: `ex99_1.htm`, 13,425 chars, index description "AT&T INC. 3RD QUARTER 2019 PRESS RELEASE", body "DALLAS, October 28, 2019 — AT&T Inc. (NYSE:T) announced…" with a "Third-Quarter Results" block (Diluted EPS $0.50, Adjusted EPS $0.94, Consolidated Revenues $44.6 billion) — AT&T combined Q3 results and 3-year guidance in one release that morning. | **CONFIRMED** — exclusion correctly recorded; sibling selection remains correct. |

## V.2 Final selection distribution — matches, and the deltas fully reconcile

Re-derived independently from `data/f2/ex99_selection_audit.csv` (307 rows,
243 CIKs, `sum(n_filings)` = **10,569** = the earnings-8-K total):

| section_type / confidence | audit CSV | attempt-4 log | match |
|---|---:|---:|---|
| `EX99_PRESS_RELEASE` / high | **10,308** | 10,308 | ✓ |
| `8K_BODY` / high | **225** | 225 | ✓ |
| `EX99_PRESS_RELEASE` / low | **19** | 19 | ✓ |
| `EX99_PRESS_RELEASE` / medium | **16** | 16 | ✓ |
| `EXCLUDED_BY_OVERRIDE` / override | **1** | 1 | ✓ |

**No discrepancy.** The movement from the attempt-2 distribution accounts
exactly, with no residue:

- `low` 32 → 19 (−13) = **11** P1 exhibit-number-from-description promotions
  (Sempra 5, Prologis 2, Weyerhaeuser 1, Welltower 1, Intuitive Surgical 1,
  BlackRock 1 — exactly the 11 §6/P1 predicted, no pick changed) + NVIDIA
  (→ override-selected, high) + AT&T (→ excluded).
- `8K_BODY` 227 → 225 (−2) = ONEOK + Micron, both leaving the cover-page
  fallback for a real release.
- `high` 10,294 → 10,308 (+14) = 11 + 1 + 2. ✓
- `excluded` 0 → 1. ✓ Net 10,569 unchanged.
- Remaining 19 low = J&J 18 + Progressive 1 — both verdicted **CORRECT** in
  the read above, both correctly still flagged because their type strings
  (`EX-99.15`, `EX-99.0`) stay deliberately unrecognised.

**Sector coverage re-checked on the new audit: still 8 of 8** with ≥1
high-confidence `EX99_PRESS_RELEASE` (industrials 835 remains the floor;
materials_realestate 1,132 → 1,136 and utilities 900 → 905 from the P1
promotions). Zero `ex99_sector_coverage` rows in the DB.

**P6 in-pipeline screen:** 10,549 selections measured (= 10,568 with a
filename − 19 low, since P6 measures only high/medium), **0 uncached**;
exactly **one** flagged CIK, **1065280 Netflix** (47 measured, 25 missing,
53%) — the case my own §3-era screen reported benign (shareholder letters,
correct picks). **Prologis: 45 measured, 0 missing, flag False — clean.**
Confirmed the threshold was not moved to hide Netflix.

## V.3 The one discrepancy — Prologis 2016-04-19, a boundary residual (n=1)

`PROLOGIS_SUPPLEMENTAL_SPLIT` is set to **2016-07-19**
(`ingest_metadata.py:984`), so the handler leaves the four earlier filings
on EX-99.1. Its docstring states those four "genuinely contain the release
('…today reported…', the webcast/conference-call block)". **That is true for
three of them and false for the fourth.**

`0001564590-16-016339` (2016-04-19) still selects `pld-ex991_6.htm`
(138,004 bytes, 113,158 chars). Read in full, plus a raw-HTML scan with
tags stripped *without* substituting spaces so that tag-split words still
match:

| marker | 2015-07-21 | 2015-10-20 | 2016-01-26 | **2016-04-19** |
|---|---|---|---|---|
| "Prologis Reports … Results" | ✓ | ✓ | ✓ | **0** |
| "Press Release" entry in its own table of contents | ✓ | ✓ | ✓ | **0** |
| "today reported" / "FOR IMMEDIATE RELEASE" | ✓ | ✓ | ✓ | **0** |
| "conference call" / "webcast" | ✓ | ✓ | ✓ | **0** |

The document's title *is* "Prologis Earnings Release and Supplemental
Information Unaudited First Quarter 2016" — but that is a leftover template
header; the body is supplemental-only, its TOC runs straight from
"Highlights" to "Company Profile" with no release section, and it contains
no dateline. The filing does carry `pld-ex992_7.htm` (EX-99.2, 71,762
bytes), which is **not cached** (never selected), so by the same
index-metadata standard the ONEOK and Micron override rows were written to,
that is the release.

**Consequence: the corrected blast radius is 42 of 45, not 41**, and the
split constant should be **2016-04-19**, not 2016-07-19. Scope is exactly
one filing; the 41 corrections are unaffected and verified good.

**Why two independent guards both passed it — worth recording, because both
are now standing infrastructure:**

1. The handler's content-confirmation generalised from the **title string**
   ("self-titled 'Earnings Release and Supplemental Information' …
   genuinely contains the release"). The title is precisely the unreliable
   signal in this filing.
2. **P6 cleared it on the same string.** `RELEASE_LANGUAGE_MARKERS`
   includes `"earnings release"`, and the only marker this document matches
   is its own title: `"prologis earnings release and supplemental
   information unaudited first quarter 2016"`. So P6 reports Prologis
   45/45 clean. This is a real, narrow blind spot in the tripwire — *a
   document whose title names a release passes even with an empty release
   body* — not a reason to distrust P6's corpus-level result (it caught the
   systematic pattern by design, and 1 flagged CIK is the right order of
   magnitude). Recording it, not proposing a threshold change: the honest
   fix is to exclude the leading title/self-label region from the P6 match
   window, which is a one-line scope change, not a threshold move.

Both items are findings for the main session. **Nothing was fixed.**

## V.4 Two corrections to my own earlier numbers in this file

Found while re-measuring; the earlier figures were conservative, not wrong
in direction, but they should not be quoted as-is.

- **"361 selections have no cached document" (§1, §5.5) was an artifact of
  my filename reconstruction, not a real gap.** I rebuilt cache paths as
  `Archives_edgar_data_{filer_cik}_{accession}_{filename}`; for accessions
  filed under a different archive directory (agent- or co-registrant-filed)
  the real path uses that other CIK. Keying on
  `filings.earnings_doc_relative_path` instead: **10,568 of 10,568
  selections have a cached document, 0 missing.** The pipeline's own screen
  agrees ("0 not cached"). My §3/§5 content screens therefore covered ~94%,
  not 100%, of selections — every conclusion in them stands, but they were
  measured on a slightly smaller base than the pipeline's.
- **"44 thin selections, 12 under 100 chars" (§5.3) is now 49 and 12** over
  the complete 10,568. The DB carries **50** `ex99_thin_exhibit` WARNs; the
  ±1 against my 49 is a boundary case from the pipeline's extra `.strip()`
  in `screen_selected_document()`, not a defect.

## V.5 Verdict

**PASS** on the fix package as ruled: all five ruled filers content-verified
against the real cached documents, the final distribution matches the
attempt-4 log exactly with every delta accounted for, the AT&T exclusion is
evidenced in both the audit and the DB, sector coverage still 8/8, and P6
reports one flagged CIK which is the known-benign Netflix. The single
residual (§V.3) is a one-quarter-late boundary on one filer, n=1, plus the
title-string blind spot that let two guards agree on it.

---
---

# VERIFICATION PASS 2 — 2026-08-24 (S7), the B1 conditional-fallback fix

Requested by the main session after the S7 red-team's **B1** (HIGH, corpus
content) produced a conditional-fallback fix plus four more evidenced
override rows (trail: `F2_PROGRESS.md` §5 S7 triage entry;
`S3_metadata_documents.md` §12.8–§12.9; the now-8-row
`data/f2/earnings_doc_overrides.csv`). Regeneration through segment-1
attempt 8 + segment-2 delta 3 is done.

**Task:** content-verify all **15** stored pick changes against the cached
bytes, with special attention to HPE; spot-confirm the final distribution.
**Mode:** read-only, unchanged. **Zero live GETs.** No code edits, no DB
writes, no `F2_PROGRESS.md` edits. `ingest_metadata.py` and the S3/F2
ledgers were read, not modified.

**Overall: PASS, with one mis-labelled filing found — §W.3 (Pioneer
2018-04-09).** 14 of 15 picks are the right document; the 15th is the only
candidate in its filing but is not a press release.

## W.1 The 15 verdicts (one line each)

Located independently of the brief's list: the 27 `medium` selections in the
DB are 16 Eversource (pre-existing) + **the 11 candidate-screen picks**, and
the 4 override accessions resolve to `high`. That reproduces the brief's 15
exactly, with no extra and none missing.

| # | Filer / filing | Selected document (type in index) | Opening line read from the cached bytes | Verdict |
|---|---|---|---|---|
| 1 | **Aon** 2015-07-31 `0001628280-15-005672` | `ex991pressreleaseq22015.htm` (`EX-99..1`) | "Investor Relations News from Aon / **Aon Reports Second Quarter 2015 Results** / Total revenue was $2.8 billion…" | **CORRECT** — Q2 2015 release |
| 2 | **Biogen** 2017-04-25 `0000875045-17-000014` | `q12017pressrelease.htm` (`EX-99..1`) | "**BIOGEN REPORTS FIRST QUARTER 2017 REVENUES OF $2.8 BILLION**" + media/investor contacts | **CORRECT** — Q1 2017 release |
| 3 | **Vistra** 2017-05-18 `0001193125-17-174537` | `d382227dex99a.htm` (`EX-99.(A)`) | "**NEWS RELEASE** / Vistra Energy Reports First Quarter 2017 Results / May 18, 2017 DALLAS – … today reported" | **CORRECT** — Q1 2017 release |
| 4 | **Vistra** 2017-08-04 `0001193125-17-248214` | `d418076dex99a.htm` (`EX-99.A`) | "Vistra Energy Reports Second Quarter 2017 Results and Reaffirms 2017 Guidance / August 4, 2017 IRVING – … today reported" | **CORRECT** — Q2 2017 release |
| 5 | **Vistra** 2018-02-26 `0001193125-18-057237` | `d536429dex99a.htm` (`EX-99.(A)`) | "Vistra Energy Reports 2017 Results Above Midpoint of Guidance / IRVING, Texas, Feb. 26, 2018" + FY2017 summary table | **CORRECT** — FY2017 annual release |
| 6 | **Pioneer** 2017-08-01 `0001038357-17-000063` | `pxdq22017earningsreleaseex.htm` (`EX-99..1`) | "**News Release** / Pioneer Natural Resources Company Reports Second Quarter 2017 Financial and Operating Results / Dallas, Texas, August 1, 2017 … today reported" | **CORRECT** — Q2 2017 release |
| 7 | **Pioneer** 2018-04-09 `0001193125-18-111008` | `d564737dex991a.htm` (`EX-99.1(A)`) | "**IPAA Oil & Gas Investment Symposium April 10, 2018** / Exhibit 99.1A / Forward-Looking Statements…" | **MIS-LABELLED — see §W.3** |
| 8 | **Zoom** 2019-12-05 `0001585521-19-000057` | `zm-20191205ex991.htm` (`EX-99..1`) | "Zoom Video Communications Reports Third Quarter Results for Fiscal Year 2020 / San Jose, California – December 5, 2019" | **CORRECT** — Q3 FY2020 release |
| 9 | **Texas Instruments** 2020-01-22 `0000097476-20-000006` | `q42019txnex99-8xker.htm` (`EX-99.`) | "TI reports Q4 2019 and 2019 financial results and shareholder returns / DALLAS (January 22, 2020) … today reported" | **CORRECT** — Q4 2019 release |
| 10 | **Arista** 2020-05-05 `0001628280-20-006442` | `ex991q120-earningsrelease.htm` (`EX-99.Q120 EARNINGS`) | "Arista Networks, Inc. Reports First Quarter 2020 Financial Results / SANTA CLARA, Calif.- May 5, 2020 … today announced" | **CORRECT** — Q1 2020 release |
| 11 | **Linde** 2022-04-28 `0001654954-22-005503` | `lin_ex991.htm` (`EX-95.1`, described `EX-99.1`) | "Exhibit 99.1 / **Linde Reports First-Quarter 2022 Results** / Sales $8.2 billion, up 13%…" (34,203 chars) | **CORRECT** — Q1 2022 release. This is §12.8's "15th case B1's table did not list", and it is real. |
| 12 | **Illumina** `0001110803-16-000185` (2016-05-03) | `a1q16earningsrelease.htm` (`EX-1`) | "Illumina Reports Financial Results for First Quarter of Fiscal Year 2016 / San Diego -- (BUSINESS WIRE) - May 3, 2016 … today announced" | **CORRECT** — Q1 FY2016 release |
| 13 | **Illumina** `0001110803-16-000194` (2016-07-26) | `a2q16earningsrelease.htm` (`EX-1`) | "Illumina Reports Financial Results for Second Quarter of Fiscal Year 2016 / … July 26, 2016 … today announced" | **CORRECT** — Q2 FY2016 release |
| 14 | **HPE** `0001645590-17-000006` (2017-11-21) | `ex-991x10312017x8k.htm` (`EX-1`; body self-labels "Exhibit 99.1") | "**News Release** / **HPE Reports Fiscal 2017 Full-Year and Fourth Quarter Results** • Q417 combined net revenue of $7.8 billion…" (87,249 chars) | **CORRECT** — Q4/FY2017 release. **See §W.2.** |
| 15 | **Kraft Heinz** `0001637459-19-000050` (2019-06-07) | `a6719exhibit991.htm` (`EX-1`; body self-labels "Exhibit 99.1") | "Exhibit 99.1 / Kraft Heinz Files Annual Report for Fiscal Year 2018 / … PITTSBURGH & CHICAGO - June 7, 2019 … today announced … **Restated Financial Statements**" | **CORRECT, with a scope caveat** — it is unambiguously this filing's Item 2.02 press release and is genuinely results-of-operations content (restated FY2016–FY2018 financials, quantified at <1% of net income), but it is **not a quarterly earnings release**. Same category as the Wells Fargo FHA-accrual and Xcel tax-reform 8-Ks verified in §2 rows 19–20. |

**Tally: 14 CORRECT (1 with a scope caveat) · 1 mis-labelled.**

## W.2 HPE double-check — CONFIRMED from primary source, both halves

I did not take §12.9's account on trust. **The 8-K cover body
`hpe-q4fy2017x8k.htm` is itself cached** (39,449 bytes — it is the document
this filing used to store as the `8K_BODY` pick), so the filer's own exhibit
mapping is readable offline. Verbatim:

> **Item 2.02** … "On November 21, 2017, Hewlett Packard Enterprise Company
> ("HPE") issued a press release relating to **segment results for its
> fiscal quarter ended October 31, 2017**. A copy of the press release is
> attached hereto as **Exhibit 99.1**…"
>
> **Item 5.02** … "HPE today announced that it has appointed **Antonio
> Neri** … A copy of the press release announcing the appointment of
> Mr. Neri is furnished as **Exhibit 99.2** to this Form 8-K."

The index has exactly two candidate rows: seq 2 `EX-1` "EXHIBIT 1" =
`ex-991x10312017x8k.htm` (1,123,235 bytes) and seq 3 `EX-2` "EXHIBIT 2" =
`pressrelease112117.htm` (13,043 bytes). Mapping the cover's own words onto
them: **Exhibit 99.1 → the selected file; Exhibit 99.2 (Neri) → the
unselected file.**

- **Selected document is the Q4 FY2017 segment-results release: CONFIRMED.**
  Read directly — "HPE Reports Fiscal 2017 Full-Year and Fourth Quarter
  Results", Q417 combined net revenue $7.8 bn, 87,249 chars of narrative and
  segment tables. Fiscal Q4 ended 2017-10-31, which the filename encodes.
- **The Neri document was correctly NOT picked: CONFIRMED.**
  `pressrelease112117.htm` is the Item 5.02 CEO-appointment release
  (Exhibit 99.2 per the cover). It is not cached — never selected, so never
  fetched — so this half rests on the cover's explicit mapping plus the size
  argument (13 KB cannot be a full quarterly results release with segment
  tables; the real one is 86× larger). That is primary-source index +
  filer-text evidence, the same standard the override rows were written to.
- **The red-team's B1 table did name the wrong file**, and §12.9's
  correction is right. Had `pressrelease112117.htm` been taken as "the sole
  unselected candidate", the corpus would carry a CEO-appointment
  announcement as HPE's Q4 FY2017 earnings text — the same defect class B1
  exists to fix.

## W.3 The one finding — Pioneer 2018-04-09 is an investor deck, not a release

`0001193125-18-111008` now stores `d564737dex991a.htm` as
`EX99_PRESS_RELEASE` / `medium`. Read in full (36,579 chars): it is the
**IPAA Oil & Gas Investment Symposium** conference presentation — a
corporate-strategy slide deck (acreage, 10-year plan, CAGR targets,
breakeven curves). Marker counts in the document: "first quarter 2018" **0**,
"1Q18" **0**, "today reported" **0**, "press release" **0**, "news release"
**0**, "preliminary" **0**. It reports no quarter's results.

**The filer says so itself.** The cover body `d564737d8k.htm` is cached, and
its Item 2.02 reads:

> "Pioneer Natural Resources Company hereby furnishes **the portions, if
> any**, of the **Investor Presentation** titled 'IPAA Oil & Gas Investment
> Symposium', which is attached hereto as Exhibit 99.1 (the
> 'Presentation'), that constitute material non-public information regarding
> the Company's results of operations or financial condition for a completed
> quarterly period."

A conditional "the portions, if any" — this is a Regulation-FD deck posting
(Item 7.01 is the substantive item) with a defensive Item 2.02 wrapper.

**It is not a mis-pick.** The filing has exactly one non-body candidate row,
so the conditional fallback had no better choice available. It is a
**mis-label**: `EX99_PRESS_RELEASE` is a false claim about this document,
and F3 will extract a slide deck as press-release text. This is the same
class as AT&T `0000732717-19-000048` (§2 row 6), which the main session
resolved with an evidenced `exclude` row — **the same mechanism fits here,
and the evidence is stronger** (the filer's own words name it a
Presentation). Note also that this filing arguably got *less* honest, not
more: pre-fix it claimed `8K_BODY` (true — a cover page); post-fix it claims
a press release (false). **Finding for the main session; nothing fixed.**

Pioneer is independently the worst entry on the new B6 **watch list**
(37/77 = 48.1% of picks lacking release language, one filing under the 50%
bar), and this filing is one of the 37 — the watch list is already pointing
at exactly the right filer. The log's 37/77 versus §12.8's 38/77 is not a
discrepancy: the 2017-08-01 pick change moved one filing from
missing→present, 38 → 37.

## W.4 B1 regression test — the defect population is drained

The precise B1 shape is "an `8K_BODY` pick while an unselected non-body
candidate row exists". Re-derived over **all 210** remaining `8K_BODY`
selections (all 210 documents cached, 0 unmeasured), ignoring the body,
graphics and XBRL data files:

**5 of 210 still have any unselected non-body row — and they are exactly the
five §12.8 said the narrow candidate rule would deliberately leave alone:**

| CIK | Filer | Unselected rows |
|---|---|---|
| 32604 | Emerson | `EX-2.1` (merger agreement) |
| 313616 | Danaher | `EX-3.1` (certificate of elimination) |
| 715957 | Dominion Energy | `EX-1.1`, `EX-4.2`, `EX-5.1` (underwriting / indenture / legal opinion) |
| 1510295 | Marathon Petroleum | `EX-10.1`, `EX-10.2` (material contracts) |
| 1552000 | MPLX | `EX-10.1` |

Every one is a sub-numbered securities/corporate exhibit; none is
release-shaped. **Zero remaining `8K_BODY` picks have a release-shaped
unselected candidate.** The conditional fallback did what it was ruled to
do, and it did it without widening `_EX99_FAMILY_RE` — verified by reading
the code, which is unchanged in that respect.

For completeness: 27 of the 210 `8K_BODY` picks are under 6,000 chars with
no release language. That is **not** residual B1 — several were verified
genuine in §2 (EQT 2022-07-11's derivatives table, Wells Fargo 2016-02-03's
FHA accrual), and they are short because the Item 2.02 disclosure itself is
short. Concentrations worth an eye at F3, not a defect: Concho 6, EQT 5,
PayPal 3.

## W.5 Final distribution — matches attempt 8 exactly

Re-derived independently from `data/f2/ex99_selection_audit.csv` (310 rows,
243 CIKs, `sum(n_filings)` = **10,569**):

| section_type / confidence | audit CSV | attempt-8 log | match |
|---|---:|---:|---|
| `EX99_PRESS_RELEASE` / high | **10,312** | 10,312 | ✓ |
| `8K_BODY` / high | **210** | 210 | ✓ |
| `EX99_PRESS_RELEASE` / low | **19** | 19 | ✓ |
| `EX99_PRESS_RELEASE` / medium | **27** | 27 | ✓ |
| `EXCLUDED_BY_OVERRIDE` / override | **1** | 1 | ✓ |

**No discrepancy**, and the movement from attempt 4 accounts exactly with no
residue: `8K_BODY` 225 → 210 (**−15**, the 15 pick changes) = **+11 medium**
(16 → 27, the candidate-screen picks) **+4 high** (the four override
conversions); `low` and `excluded` unchanged; net 10,569 constant.
**Zero newly unresolved** — §12.9's "15 resolved / 0 unresolved, not 19" is
confirmed in the stored data.

**Sector coverage: still 8 of 8** with ≥1 high-confidence
`EX99_PRESS_RELEASE` (industrials 835 remains the floor; healthcare
1,368 → 1,370, tech 1,707 → 1,708, consumer 1,447 → 1,448, energy
1,203 unchanged). Zero `ex99_sector_coverage` rows in the DB.

**B6 watch list** (new): 2 CIKs at ≥40% but under the 50% flag bar —
**788784 PUBLIC SERVICE ENTERPRISE GROUP** 21/45 = 46.7% (utilities,
extension; **not previously examined by any pass — unread**) and **1038357
Pioneer** 37/77 = 48.1% (§W.3). Netflix remains the single flagged CIK at
53.2%, still reported-benign. Confirmed the flag threshold was not moved.

## W.6 Verdict

**PASS.** All 15 pick changes content-verified against real cached bytes;
14 are the right document, 13 of them unambiguously that quarter's earnings
release and one (Kraft Heinz) the filing's genuine Item 2.02 restatement
release. The HPE trap is confirmed avoided from the filer's own exhibit
mapping. The B1 defect population is drained to zero release-shaped
candidates, with the five documented securities-exhibit exclusions intact.
The distribution matches attempt 8 exactly with every delta accounted for.
The one finding — Pioneer 2018-04-09 typed as a press release when the filer
calls it an Investor Presentation — is a mis-label of the same class already
ruled once (AT&T), n=1, handed back to the main session unfixed.

---

## §W ADDENDUM — 2026-08-24 (final read of S7): PSEG, the watch list's next-worst name

Requested by the main session after §W was accepted and the Pioneer
exclusion was ruled (9th override row). **PSEG — CIK 788784, Public Service
Enterprise Group, utilities / extension stratum — 21/45 = 46.7%
release-language-missing, never examined by any prior pass.** Read-only,
**zero live GETs**, DB read-only, no code edits.

### Verdict: a REAL, SYSTEMATIC MIS-PICK — not Netflix-benign, not Pioneer-class. 45 of 45 filings, all at `high` confidence.

### The three representative filings read

Chosen across the span, one per distinct document-title era:

| # | Filing | Selected doc | What it actually is (read from the cached bytes) | Verdict |
|---|---|---|---|---|
| 1 | **2015-07-31** `0001193125-15-272287` (Q2 2015) | `d17140dex991.htm`, EX-99.1, 24,195 chars | Opens: *"Public Service Enterprise Group **PSEG Earnings Conference Call 2nd Quarter 2015** July 31, 2015 EXHIBIT 99.1"* → straight into *"Forward-Looking Statement • adverse changes in the demand for or the price of the capacity and energy…"*. A **slide deck** — the index carries 37 per-slide `…ex99_1s<N>gbgd.jpg` GRAPHIC rows for it. | **MIS-PICK** |
| 2 | **2018-02-23** `0001193125-18-054974` (Q4/FY2017) | `d532537dex991.htm`, EX-99.1, 30,202 chars | Opens: *"**PSEG Earnings Conference Call 4 Quarter & Full Year 2017** February 23, 2018 … EXHIBIT 99.1"* → *"Forward-Looking Statements…"*. Same deck shape, 46 per-slide GRAPHIC rows. | **MIS-PICK** |
| 3 | **2020-10-30** `0001193125-20-281836` (Q3 2020) | `d31763dex991.htm`, EX-99.1, 35,974 chars | Opens: *"**PSEG Earnings Conference Call 3rd Quarter 2020** October 30, 2020 EXHIBIT 99.1"* → *"Certain of the matters discussed in **this presentation**…"*. The filer's own word is "presentation". 39 per-slide GRAPHIC rows. | **MIS-PICK** |

None of the three is an earnings press release. Each is the **earnings-call
presentation deck**.

### The better document is present in every one of the 45 filings

Every PSEG earnings 8-K has exactly the same two-candidate shape — verified
across **all 45**, no exceptions:

```
seq 1   8-K       "FORM 8-K"    d…d8k.htm
seq 2   EX-99     "EX-99"       d…dex99.htm     <-- NOT selected
seq 3   EX-99.1   "EX-99.1"     d…dex991.htm    <-- selected: the slide deck
```

`{('EX-99', 'EX-99.1'): 45}` — the shape is uniform from 2015-07-31 to
2026-08-04. The unselected bare **`EX-99` at seq 2 is the press release**.
Evidence, all offline:

1. **The selected sibling is provably the deck, in all 45** — not just the 3
   read in full. Every one of the 45 carries a deck signal in its first
   1,200 characters: *"Earnings Conference Call"* (2015→2021) or
   *"Financial Results Presentation"* (2022→2026), each immediately followed
   by forward-looking-statement boilerplate. The release must therefore be
   the other row.
2. **Size**: the bare `EX-99` is larger than the `EX-99.1` in **42 of 45**
   filings (e.g. 318,098 vs 273,723 bytes in 2015; 388,095 vs 325,267 in
   2018; 362,250 vs 52,462 in 2020). The three exceptions are near-ties
   (2016-04-29, 2017-02-24, 2019-07-30, all within 6%).
3. **Every filing is `items=2.02,7.01,9.01`** — the standard utility pattern
   is release under Item 2.02, call deck furnished under Item 7.01. PSEG
   files both, and the policy took the 7.01 artifact.

**Caveat, stated plainly:** the bare `EX-99` documents are **not cached** —
they were never selected, so never fetched, and I may not fetch them. This
finding therefore rests on the evidence chain above, not on reading the
release. That is the identical standard on which the Prologis finding was
raised in §3.1, and which the bytes later confirmed exactly (§V.1).

### Root cause — and why it is *not* a new defect class

The exhibit ladder prefers a sub-numbered `EX-99.1` over a bare `EX-99`.
For PSEG that preference is exactly backwards. `_best_by_description()`
cannot break the tie because both descriptions are content-free — literally
`"EX-99"` and `"EX-99.1"`. This is **the Prologis shape** (EX-99.1 = the
presentation/supplemental artifact, the release is the other exhibit),
differing only in that Prologis's release sat at a *higher* sub-number
(EX-99.2) while PSEG's sits at a *lower*, unnumbered one. Scope 45/45 vs
Prologis's 41/45, and — again — **every one is `high` confidence**. Third
independent confirmation that selection confidence does not track
correctness.

### The P6 watch list worked, and it still understates this filer

Two things worth recording:

- **The title-region scope fix put PSEG on the watch list.** Reproducing the
  pipeline exactly (importing `screen_selected_document`, `TITLE_REGION_CHARS
  = 200`) gives 21/45 — matching the audit CSV and the attempt-8 log to the
  filing. Under the *pre-fix* screen PSEG scored 0/45 missing, because
  "conference call" appears at character 58–89, inside the title. The fix
  proposed in §V.3 and shipped in §12.7 is what surfaced this filer at all.
  It earned its keep on the first corpus it ran against.
- **21/45 understates it; the true rate is 45/45.** All 24 filings that
  "pass" the screen pass on **`"investor relations"` alone** — a contact
  slide deep in the deck (character ~9,548 in the 2020 filing), not release
  prose. `{('investor relations',): 24}`. So the watch-list share is a
  floor, not an estimate. Not a reason to change the marker list — a reason
  not to read a sub-50% share as "half fine".

### What I am NOT claiming

The remaining watch-list and unread-tail names stay **honestly unread**.
This addendum covers PSEG only. Netflix (1065280, 53.2%, flagged) remains
reported-benign on the earlier read; Pioneer (1038357, 48.1%) is ruled; and
the §5.1 statement stands unchanged — the capped read has never covered the
full flagged population, and three passes of spot-reads do not convert it
into full coverage. **Every filer below the watch-list bar is unmeasured for
this defect class, not clean.**

**Handed to the main session as a finding. Nothing was fixed, no override
row was written, no threshold was touched.**

---

## §W ADDENDUM 2 — 2026-08-24 (S7's last read): PSEG handler verification

The PSEG handler is implemented and regenerated (trail:
`S3_metadata_documents.md` §12.11, F2_SPEC **A14**; segment-1 attempt 11 +
segment-2 delta 4, which fetched exactly **45** documents / 0 failed).
Read-only, **zero live GETs from this session**, DB read-only, no code
edits.

### Verdict: PASS. All 45 PSEG selections are now the earnings press release.

### The five newly-cached documents, read across the era

| # | Filing (quarter) | Selected doc | Opening text read from the cached bytes | Verdict |
|---|---|---|---|---|
| 1 | **2015-07-31** `0001193125-15-272287` (Q2 2015) | `d17140dex99.htm`, 29,601 chars | "**Investor News** NYSE: PEG … Kathleen A. Lally, VP – Investor Relations … **PSEG ANNOUNCES 2015 SECOND QUARTER RESULTS** $0.68 PER SHARE OF NET INCOME … **July 31, 2015 (Newark, NJ)** … reported Second Quarter 2015 Net Income of $345 million or $0.68 per share" | **CORRECT** — Q2 2015 release |
| 2 | **2018-02-23** `0001193125-18-054974` (Q4/FY2017) | `d532537dex99.htm`, 37,805 chars | "Investor News NYSE: PEG … **PSEG ANNOUNCES 2017 RESULTS** NET INCOME OF $3.10 PER SHARE … **(February 23, 2018 – Newark, NJ)** … reported 2017 Net Income of $1,574 million, or $3.10 per share" | **CORRECT** — FY2017 release |
| 3 | **2020-10-30** `0001193125-20-281836` (Q3 2020) | `d31763dex99.htm`, 36,561 chars | "Investor Relations … CONTACT: Media Relations / Investor Relations … **PSEG ANNOUNCES 2020 THIRD QUARTER RESULTS** $1.14 PER SHARE OF NET INCOME … **(October 30, 2020 – Newark, NJ)**" | **CORRECT** — Q3 2020 release |
| 4 | **2023-05-02** `0001193125-23-131492` (Q1 2023) | `d449942dex99.htm`, 26,474 chars | "CONTACTS: Media Relations / Investor Relations … **PSEG Announces First Quarter 2023 Results** $2.58 Per Share Net Income … **(NEWARK, N.J. – May 2, 2023)** … reported first quarter 2023 Net Income of $1,287 million" | **CORRECT** — Q1 2023 release |
| 5 | **2026-05-05** `0001193125-26-205254` (Q1 2026) | `d63722dex99.htm`, 20,541 chars | "**PSEG ANNOUNCES FIRST QUARTER 2026 RESULTS** $1.48 PER SHARE NET INCOME … **(NEWARK, N.J. – May 5, 2026)** … reported the following results for the first quarter 2026" + comparative results table | **CORRECT** — Q1 2026 release |

**5 of 5 CORRECT.** In every one the dateline equals the filing date and the
quarter named equals the filing's fiscal quarter — the two things a mis-pick
of this class would break. All five carry the press-release furniture the
decks never had: "Investor News" / media + IR contact block, headline, city
dateline, narrative first paragraph.

### Generalised past the sample: 45 of 45

Not inferred from five. Every one of the **45** PSEG selections was read and
**all 45 open with "PSEG ANNOUNCES … RESULTS" / "PSEG Announces … Results"
within the first 900 characters.** The pre-fix deck signature
("Earnings Conference Call" / "Financial Results Presentation" followed by
forward-looking boilerplate), which was present in 45/45 before, is now
present in **0/45**. The defect is fully inverted, not partially.

### Audit state at attempt 11 — confirmed, independently re-derived

**PSEG's selections.** All 45 now resolve to the bare `EX-99` row: joining
each stored `earnings_doc_filename` back to its own `filing_documents` row,
**0 of 45 have an index type other than `EX-99`**. Confidence:
`{('EX99_PRESS_RELEASE','high'): 45}` — the handler's confidence, and the
same bucket the decks occupied, which is why the corpus distribution does
not move.

**Deck screen post-fix = 0, re-derived rather than read off the log.** I
imported the pipeline's own `screen_selected_document` and swept **all
10,567** stored post-fix picks:

```
CORPUS DECK SWEEP: 10,567 measured, 0 uncached
DECK-SHAPED selections: 0 across 0 CIK(s)
```

Matching the attempt-11 log line ("DECK-SHAPED selections … 0 across 0
CIK(s)"), the audit CSV's new `n_deck_shaped` column (total **0**, no
`deck_shaped_flag` CIK), and the DB (zero `ex99_deck_shaped_selection`
rows).

**Distribution matches attempt 11 exactly** (audit CSV: 311 rows, 243 CIKs,
`sum(n_filings)` = 10,569):

| section_type / confidence | audit CSV | attempt-11 log |
|---|---:|---:|
| `EX99_PRESS_RELEASE` / high | **10,312** | 10,312 |
| `8K_BODY` / high | **210** | 210 |
| `EX99_PRESS_RELEASE` / low | **19** | 19 |
| `EX99_PRESS_RELEASE` / medium | **26** | 26 |
| `EXCLUDED_BY_OVERRIDE` / override | **2** | 2 |

The only movement since attempt 8 is **medium −1 / excluded +1** — the ruled
Pioneer exclusion (§W.3). The 45 PSEG changes are high→high and therefore
invisible in the distribution, exactly as §12.11 predicted. Sector coverage
**8 of 8** unchanged.

**PSEG's watch-list exit is real, and its residual 3 are benign — checked,
not assumed.** PSEG's audit row is now `rel_missing 3 / 45 = 6.7%, flag
False, deck 0` (was 21/45 = 46.7%). I read all three misses
(2016-10-31, 2020-05-04, 2020-07-31): **all three are genuine releases** —
each opens with the "PSEG ANNOUNCES … RESULTS" headline. They miss P6 only
because their IR/media contact block runs *before* the headline, putting
their sole `"investor relations"` marker inside the 200-character title
region. Same benign false-miss shape as Prologis 2016-01-26 (§V.3). Nothing
to act on; recorded so 6.7% is not mistaken for a residue of the defect.

The remaining watch list is **1 CIK — 1038357 Pioneer at 37/76 (48.7%)**,
whose one ruled filing is already excluded; Netflix (1065280) remains the
single flagged CIK and stays reported-benign.

### Standing caveat, unchanged

This closes PSEG only. **§5.1 stands exactly as written**: the §4.4 read has
never covered the full flagged population, and five passes of spot-reads do
not convert it into full coverage. Every filer below the watch-list bar
remains **unmeasured for this defect class, not clean** — and §12.11's own
note that a P6 *pass* can rest on contact-slide boilerplate is the reason
that sentence should survive into the F2 report verbatim.

### Verdict

**PASS.** 5 of 5 documents read are genuinely that quarter's press release;
generalised to 45 of 45 by headline; the deck screen independently
re-derives to 0 across the whole corpus with 0 uncached; PSEG's 45 selections
are the bare `EX-99` at `high`; the audit distribution matches attempt 11 to
the filing with the single expected Pioneer delta. No code edits, no DB
writes, no override rows, no thresholds touched by this pass.

