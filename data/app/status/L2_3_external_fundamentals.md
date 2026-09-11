# L2.3 — point-in-time fundamentals for any CIK

**What this is.** PRODUCT_PLAN §3 P1a's follow-up **P1a.2**, and the closing of
the second finding in `L2_2_external_companies.md` §4 ("Fundamentals are blank
for every external company") and its §5 bullet ("per-company XBRL concept
resolution at ingest time, so the fundamentals panel is not blank outside the
research universe"). L2.2 said the fix was *"real work, not a flag"*; this is
that work, measured on the same ten un-curated companies from the same sealed
draw, with every failure recorded and none removed.

Under the §0.5 real-data-first rule, **every number below comes from the ten
real companies in `data/app/status/external_draw.json`.** The synthetic
fixtures in `test_app_store.py` test plumbing and nothing anybody reads.

**Cost.** $0. **9 EDGAR requests** for the whole run (one companyfacts
document per company; TGLS's was already warm from an earlier run of the same
code). No API, no GPU, no price data.

---

## 1. What was built

**`ingest_one.py --fundamentals` (step 7).** One company's XBRL companyfacts
fetched through the existing rate-limited `edgar_client.get_companyfacts` and
cached under `data/raw/companyfacts/CIK##########.json` — the same cache and
the same 24-hour staleness policy F2 filled for the 244 research CIKs — then
parsed and classified by **`ingest_fundamentals`'s own code, imported and
called**, not re-expressed:

| what | whose code |
|---|---|
| every fact of every family tag, every filed occurrence, never deduplicated | `IF.build_fundamentals` → `IF.extract_concept_facts` over `IF.CONCEPTS` |
| the 14 concept families and their preference order | `IF.CONCEPT_FAMILIES` |
| the six-state alias/migration classifier (SINGLE / MIGRATION / DOMINANT / OVERLAP / PARTIAL / ABSENT), its 75% coverage bar, its 2-quarter staleness rule and its filed-span denominator | `IF.classify_universe` → `IF.classify_family` |
| the CSV record | `IF.write_concept_resolution` |
| the reason an UNRESOLVED pair failed, verbatim | `IF.resolution_problems` |

It writes two files into `data/app/companies/<cik>/`:

* **`fundamentals.parquet`** — the same arrow schema as
  `data/fundamentals_e2.parquet`, read off that file and applied, so "same
  schema" is a comparison and not a claim (`test_store_fundamentals_schema_-
  equals_the_research_schema`);
* **`concept_resolution.csv`** — the same eleven columns as
  `data/f2/concept_resolution.csv` (`test_store_concept_resolution_columns_-
  equal_f2s`), one row per (cik, family), **UNRESOLVED pairs included and
  marked UNRESOLVED**.

Both shas, the window, the per-family verdict and the classifier's own reason
for each failure go into the store's `manifest.json` under `fundamentals`.

**`report_filing.py --store` now reads them.** The panel resolver is unchanged
and is still `numeric_features_e2.resolve_family_value` → `pit.value_as_of`;
what `--store` changes is only *which file* the two loaders open, through a
context manager that rebinds `numeric_features_e2`'s two path constants for
the length of one call and restores them in `finally`
(`test_the_redirect_is_put_back_even_when_the_load_raises`). That is
deliberate: writing store-shaped copies of `load_fundamentals` and
`load_resolution` would create two more places where a company outside the
universe could be read differently from one inside it, which is the whole
thing this work exists to remove. `numeric_features_e2.py`, `pit.py` and
`ingest_fundamentals.py` are not edited.

**What is NOT written.** `data/fundamentals_e2.parquet`,
`data/f2/concept_resolution.csv` and `data/filings_metadata_e2.db` are F2's
committed records. Step 7 opens the first read-only (for the schema) and never
touches the other two; `IF.run()`, the function that writes all three, is
never called. Pinned at runtime by
`test_f2s_committed_records_are_never_written`, which records every path
written during a step-7 run and asserts they all lie inside the store.

**The classification window, and why it is what it is.** A research member is
scored over its membership spell (F2_SPEC §3.4). An external company has no
spell, so its window is **its own XBRL life**: from the earliest date that
appears anywhere in its facts to today. The window is non-clipping by
construction — `classify_universe` already trims the coverage *denominator* to
the company's own filed span (F2_SPEC §5.7 A5.1), so any window that clips
nothing yields the same denominator, and this is the widest such window. It
deliberately does not use `CORPUS_WINDOW_END` (2026-08-31), which would hide
the facts of a filing made this month — precisely the filings a store exists
to read. **This choice has a measured consequence; see §7.**

---

## 2. What was fetched, and what resolved

One companyfacts document per company. "families resolved" is out of the 14
`CONCEPT_FAMILIES`, not the 5 the panel shows.

| # | ticker | CIK | facts stored | families resolved | classification window (reportable quarters) | EDGAR | wall |
|---|---|---|---|---|---|---|---|
| 1 | SIRI | 908937 | 2,598 | 10/14 | 2007-12-31 .. 2026-09-11 (75) | 1 | 0.48 s |
| 2 | CBKM | 1006830 | 2,213 | 12/14 | 2009-06-30 .. 2026-09-11 (69) | 1 | 0.18 s |
| 3 | TGLS | 1534675 | 2,537 | 12/14 | 2011-09-20 .. 2026-09-11 (60) | 0 (warm) | 0.04 s |
| 4 | CARG | 1494259 | 1,614 | 11/14 | 2014-12-31 .. 2026-09-11 (47) | 1 | 0.39 s |
| 5 | RNGE | 1438943 | 2,183 | 8/14 | 2007-06-30 .. 2026-09-11 (77) | 1 | 0.14 s |
| 6 | AETN | 764630 | 1,854 | 9/14 | 2010-02-28 .. 2026-09-11 (66) | 1 | 0.45 s |
| 7 | STC | 94344 | 2,630 | 11/14 | 2008-12-31 .. 2026-09-11 (71) | 1 | 0.69 s |
| 8 | YSGL | 2071489 | 157 | 5/14 | 2024-06-30 .. 2026-09-11 (9) | 1 | 0.25 s |
| 9 | REAL | 1573221 | 1,269 | 12/14 | 2016-12-31 .. 2026-09-11 (39) | 1 | 0.15 s |
| 10 | ODYS | 1577445 | 1,423 | 8/14 | 2013-03-31 .. 2026-09-11 (54) | 1 | 0.31 s |

The **CROX pilot store** (CIK 1334036, L2.2 §1, not one of the ten) was topped
up by the same command for consistency — 2,595 facts, 12/14 families, one more
EDGAR request — and is excluded from every count in this file.

**Totals.** 18,478 fact rows; **98 of 140 (cik, family) pairs resolved**;
9 EDGAR requests; **3.1 seconds of wall clock for all ten companies**, of
which 2.9 s is fetch+parse and 0.06 s is the classifier. Ingesting a company's
whole XBRL history costs about a third of a second and one HTTP request — two
orders of magnitude less than labeling the same company's text, which is what
dominates an on-demand run (`L2_2` §2: 87–221 s).

### The whole resolution matrix

Panel families are marked `*`. `PARTIA` = PARTIAL, `MIGRAT` = MIGRATION,
`DOMINA` = DOMINANT, `OVERLA` = OVERLAP — all six states are the classifier's
own; the last three are UNRESOLVED.

```
family                     SIRI   CBKM   TGLS   CARG   RNGE   AETN    STC   YSGL   REAL   ODYS
assets                *  SINGLE SINGLE SINGLE SINGLE SINGLE SINGLE SINGLE PARTIA SINGLE SINGLE
revenue               *  PARTIA SINGLE MIGRAT SINGLE PARTIA PARTIA SINGLE SINGLE SINGLE PARTIA
net_income            *  SINGLE SINGLE SINGLE DOMINA SINGLE SINGLE DOMINA SINGLE SINGLE SINGLE
operating_cash_flow   *  MIGRAT SINGLE SINGLE SINGLE MIGRAT SINGLE SINGLE PARTIA SINGLE SINGLE
equity                *  SINGLE SINGLE SINGLE SINGLE SINGLE SINGLE DOMINA PARTIA SINGLE SINGLE
cash                     SINGLE SINGLE SINGLE DOMINA OVERLA SINGLE SINGLE PARTIA SINGLE SINGLE
eps_diluted              SINGLE SINGLE SINGLE SINGLE MIGRAT SINGLE SINGLE SINGLE MIGRAT MIGRAT
liabilities              SINGLE SINGLE SINGLE SINGLE SINGLE SINGLE SINGLE PARTIA SINGLE PARTIA
liabilities_and_equity   SINGLE SINGLE SINGLE SINGLE SINGLE SINGLE SINGLE PARTIA SINGLE SINGLE
minority_interest        PARTIA ABSENT PARTIA ABSENT PARTIA ABSENT SINGLE ABSENT ABSENT ABSENT
net_income_to_common     PARTIA SINGLE PARTIA PARTIA PARTIA ABSENT PARTIA SINGLE SINGLE ABSENT
operating_income         SINGLE ABSENT SINGLE SINGLE SINGLE SINGLE ABSENT SINGLE SINGLE PARTIA
pretax_income            PARTIA MIGRAT SINGLE SINGLE PARTIA PARTIA SINGLE ABSENT SINGLE PARTIA
shares_outstanding       SINGLE SINGLE SINGLE ABSENT PARTIA PARTIA PARTIA PARTIA PARTIA SINGLE
```

Two rows of that table are **structurally expected and are exempt from F2's
own sector-concentration BLOCKER aggregation** for exactly this reason
(`IF.BLOCKER_EXEMPT_CELLS`): `minority_interest` exists only for a filer with
non-wholly-owned subsidiaries, and `net_income_to_common` differs from net
income only when preferred dividends exist. `operating_income` and
`liabilities` are exempt too. Their failures here are the companies'
structure, not a gap in this work — and none of the four is a panel family.

Two rows are the classifier doing the job it was built for on companies
nobody curated:

* **CBKM's revenue resolves to `InterestAndDividendIncomeOperating`** — the
  bank/broker-dealer top line, a family member since F2 S4. A community bank
  the draw handed us gets its revenue from the bank tag, with no ticker named
  anywhere and no override map.
* **SIRI, RNGE, ODYS `operating_cash_flow` / `eps_diluted` resolve as
  MIGRATION**, recording the switch quarter, rather than silently freezing on
  the predecessor tag. That freezing is the E1 red-team BLOCKER this
  classifier exists to prevent.

---

## 3. The five panel values, as rendered for each company's latest 10-K

These are the numbers on the page: `report_filing --store --latest 10-K`,
resolved point-in-time as of that filing's own filing date.

| ticker | 10-K filed | Total assets | Revenue | Net income | Operating cash flow | Total equity |
|---|---|---|---|---|---|---|
| SIRI | 2026-02-05 | 27.24 bn USD | **unresolved** | 805.00 m USD | 1.90 bn USD | 11.56 bn USD |
| CBKM | 2026-09-10 | 1.28 bn USD | 59.43 m USD | 11.16 m USD | 11.19 m USD | 89.89 m USD |
| TGLS | 2026-03-02 | 1.26 bn USD | 983.61 m USD | 159.57 m USD | 135.75 m USD | 763.97 m USD |
| CARG | 2026-02-19 | 661.90 m USD | 241.09 m USD † | 155.90 m USD | 295.28 m USD | 374.20 m USD |
| RNGE | 2026-03-31 | 123.24 m USD | **unresolved** | 15.91 m USD † | 123.03 k USD | 21.46 m USD |
| AETN | 2026-03-31 | 54.56 k USD | **unresolved** | -337.09 k USD | -2.96 k USD | -2.00 m USD |
| STC | 2026-02-27 | 3.25 bn USD | 2.92 bn USD | 115.53 m USD | 205.69 m USD | 1.64 bn USD |
| YSGL | 2026-06-25 | **unresolved** | 40.67 k USD | -10.83 k USD | **unresolved** | **unresolved** |
| REAL | 2026-02-26 | 409.03 m USD | 692.85 m USD | -41.80 m USD | 37.01 m USD | -415.52 m USD |
| ODYS | 2026-03-19 | 28.98 m USD | **unresolved** | -17.04 m USD | -13.70 m USD | 25.43 m USD |

**43 of 50 panel cells carry a number.** Before this work all 50 read
*"UNRESOLVED for this company in F2's concept resolution"*.

† **2 of the 43 resolved cells are a QUARTER, not a year** — CARG's revenue and
RNGE's net income. The page says so in its Period column; the cause, and why
it is not silently corrected, is §5.3.

### The provenance behind every resolved cell

The XBRL tag the classifier chose, the period the fact actually covers, and
the filing it came from. Everything here renders on the page.

| ticker | family | concept | period the fact covers | fact filed | form |
|---|---|---|---|---|---|
| SIRI | Total assets | `Assets` | as at 2025-12-31 | 2026-02-05 | 10-K |
| SIRI | Net income | `NetIncomeLoss` | 12 months ending 2025-12-31 | 2026-02-05 | 10-K |
| SIRI | Operating cash flow | `NetCashProvidedByUsedInOperatingActivities` | 12 months ending 2025-12-31 | 2026-02-05 | 10-K |
| SIRI | Total equity | `StockholdersEquity` | as at 2025-12-31 | 2026-02-05 | 10-K |
| CBKM | Total assets | `Assets` | as at 2026-06-30 | 2026-09-10 | 10-K |
| CBKM | Revenue | `InterestAndDividendIncomeOperating` | 12 months ending 2026-06-30 | 2026-09-10 | 10-K |
| CBKM | Net income | `NetIncomeLoss` | 12 months ending 2026-06-30 | 2026-09-10 | 10-K |
| CBKM | Operating cash flow | `NetCashProvidedByUsedInOperatingActivities` | 12 months ending 2026-06-30 | 2026-09-10 | 10-K |
| CBKM | Total equity | `StockholdersEquity` | as at 2026-06-30 | 2026-09-10 | 10-K |
| TGLS | Total assets | `Assets` | as at 2025-12-31 | 2026-03-02 | 10-K |
| TGLS | Revenue | `RevenueFromContractWithCustomerExcludingAssessedTax` | 12 months ending 2025-12-31 | 2026-03-02 | 10-K |
| TGLS | Net income | `NetIncomeLoss` | 12 months ending 2025-12-31 | 2026-03-02 | 10-K |
| TGLS | Operating cash flow | `NetCashProvidedByUsedInOperatingActivities` | 12 months ending 2025-12-31 | 2026-03-02 | 10-K |
| TGLS | Total equity | `StockholdersEquity` | as at 2025-09-30 | 2025-11-07 | 10-Q |
| CARG | Total assets | `Assets` | as at 2025-12-31 | 2026-02-19 | 10-K |
| CARG | Revenue | `RevenueFromContractWithCustomerExcludingAssessedTax` | **3 months ending 2025-12-31** † | 2026-02-19 | 10-K |
| CARG | Net income | `NetIncomeLoss` | 12 months ending 2025-12-31 | 2026-02-19 | 10-K |
| CARG | Operating cash flow | `NetCashProvidedByUsedInOperatingActivities` | 12 months ending 2025-12-31 | 2026-02-19 | 10-K |
| CARG | Total equity | `StockholdersEquity` | as at 2025-12-31 | 2026-02-19 | 10-K |
| RNGE | Total assets | `Assets` | as at 2025-12-31 | 2026-03-31 | 10-K |
| RNGE | Net income | `NetIncomeLoss` | **3 months ending 2025-12-31** † | 2026-03-31 | 10-K |
| RNGE | Operating cash flow | `NetCashProvidedByUsedInOperatingActivities` | 12 months ending 2025-12-31 | 2026-03-31 | 10-K |
| RNGE | Total equity | `StockholdersEquity` | as at 2025-12-31 | 2026-03-31 | 10-K |
| AETN | Total assets | `Assets` | as at 2025-12-31 | 2026-03-31 | 10-K |
| AETN | Net income | `NetIncomeLoss` | 12 months ending 2025-12-31 | 2026-03-31 | 10-K |
| AETN | Operating cash flow | `NetCashProvidedByUsedInOperatingActivities` | 12 months ending 2025-12-31 | 2026-03-31 | 10-K |
| AETN | Total equity | `StockholdersEquity` | as at 2025-12-31 | 2026-03-31 | 10-K |
| STC | Total assets | `Assets` | as at 2025-12-31 | 2026-02-27 | 10-K |
| STC | Revenue | `Revenues` | 12 months ending 2025-12-31 | 2026-02-27 | 10-K |
| STC | Net income | `NetIncomeLoss` | 12 months ending 2025-12-31 | 2026-02-27 | 10-K |
| STC | Operating cash flow | `NetCashProvidedByUsedInOperatingActivities` | 12 months ending 2025-12-31 | 2026-02-27 | 10-K |
| STC | Total equity | `StockholdersEquity` | as at 2025-12-31 | 2026-02-27 | 10-K |
| YSGL | Revenue | `RevenueFromContractWithCustomerIncludingAssessedTax` | 12 months ending 2026-03-31 | 2026-06-25 | 10-K |
| YSGL | Net income | `NetIncomeLoss` | 12 months ending 2026-03-31 | 2026-06-25 | 10-K |
| REAL | Total assets | `Assets` | as at 2025-12-31 | 2026-02-26 | 10-K |
| REAL | Revenue | `RevenueFromContractWithCustomerExcludingAssessedTax` | 12 months ending 2025-12-31 | 2026-02-26 | 10-K |
| REAL | Net income | `NetIncomeLoss` | 12 months ending 2025-12-31 | 2026-02-26 | 10-K |
| REAL | Operating cash flow | `NetCashProvidedByUsedInOperatingActivities` | 12 months ending 2025-12-31 | 2026-02-26 | 10-K |
| REAL | Total equity | `StockholdersEquity` | as at 2025-12-31 | 2026-02-26 | 10-K |
| ODYS | Total assets | `Assets` | as at 2025-12-31 | 2026-03-19 | 10-K |
| ODYS | Net income | `NetIncomeLoss` | 12 months ending 2025-12-31 | 2026-03-19 | 10-K |
| ODYS | Operating cash flow | `NetCashProvidedByUsedInOperatingActivities` | 12 months ending 2025-12-31 | 2026-03-19 | 10-K |
| ODYS | Total equity | `StockholdersEquity` | as at 2025-12-31 | 2026-03-19 | 10-K |

**Two rows are the point-in-time rule visibly working, not a bug.**

* **TGLS's Total equity is the 10-Q's 2025-09-30 figure, filed 2025-11-07, 153
  days before the 10-K.** The 10-K itself carries no `StockholdersEquity` fact
  for 2025-12-31. The panel shows the freshest figure that was *knowable* and
  prints the filing it came from, rather than reaching for a different tag —
  which is what the resolution forbids. (It is inside the 200-day staleness
  guard `features.STALENESS_MAX_DAYS`; past that the row would read
  unresolved-because-stale.)
* **CBKM's numbers are as at 2026-06-30**, not 2025-12-31: Consumers Bancorp
  has a June fiscal year end and filed its 10-K on 2026-09-10.

**No restatement moved a number on any of these ten pages.** Checked, not
assumed: for every resolved cell, the set of values knowable for that
(concept, period) as of the filing date was enumerated, and only two cells
carried more than one — both of them the same-day FY-versus-Q4 collision of
§5.3, not a restatement. Every resolved cell is the figure as originally
filed. The machinery that *would* show a restatement is pinned on synthetic
facts instead
(`test_the_panel_is_point_in_time_and_shows_the_restatement`: the same period
reads 100.00 m before the restatement's filed date and 90.00 m after, with the
filed date beside it saying which).

---

## 4. Every UNRESOLVED panel cell, with the classifier's reason

Seven of fifty. Each of these renders on the page as `unresolved` with this
sentence beside it — the classifier's own FATAL message, carried through the
store manifest, never a blank.

* **SIRI · Revenue** — `PARTIAL over 75 reportable quarters --
  RevenueFromContractWithCustomerExcludingAssessedTax 39/75 (52%, last
  2026Q2), Revenues 18/75 (24%, last 2018Q1); union 68%. the tags' union does
  not reach the 75% coverage bar, so any series built from them would be
  silently gapped.`
* **RNGE · Revenue** — `PARTIAL over 77 reportable quarters -- Revenues 30/77
  (39%, last 2018Q4), RevenueFromContractWithCustomerExcludingAssessedTax
  19/77 (25%, last 2026Q2); union 62%. …`
* **AETN · Revenue** — `PARTIAL over 66 reportable quarters -- Revenues 27/66
  (41%, last 2019Q4), RevenueFromContractWithCustomerExcludingAssessedTax
  17/66 (26%, last 2026Q1); union 67%. …`
* **ODYS · Revenue** — `PARTIAL over 54 reportable quarters --
  RevenueFromContractWithCustomerExcludingAssessedTax 31/54 (57%, last
  2026Q2), Revenues 2/54 (4%, last 2022Q3); union 57%. …`
* **YSGL · Total assets** — `PARTIAL over 9 reportable quarters -- Assets 6/9
  (67%, last 2026Q2); union 67%. …`
* **YSGL · Operating cash flow** — `PARTIAL over 9 reportable quarters --
  NetCashProvidedByUsedInOperatingActivities 6/9 (67%, last 2026Q2); union
  67%. …`
* **YSGL · Total equity** — `PARTIAL over 9 reportable quarters --
  StockholdersEquity 6/9 (67%, last 2026Q2); union 67%. …`

They are **two failure shapes, not seven**:

1. **The ASC 606 revenue switch across a long history (4 of 4 revenue
   failures).** `Revenues` dies around 2018–2019, `RevenueFromContractWith-
   Customer…` takes over, and over the company's *whole* XBRL life the two
   together cover 57–68% of its reportable quarters — under the 75% bar, and
   with more than one quarter of overlap, so it is not a clean MIGRATION
   either. Each of these four companies plainly reports revenue today; the
   classifier refuses because the *series* is gapped, which is the question it
   was built to answer. Whether the panel should be asking that question at
   all is §7.
2. **A company too young to clear a coverage bar (YSGL, 3 of 3).** Yellowstone
   Group is a 2025 registrant: 157 facts in its entire history, 6 quarters of
   balance-sheet data inside a 9-quarter span, 67% — eight points short of the
   bar. Nothing is wrong with the data; there is not enough of it yet.

---

## 5. Every failure, with its cause

### 5.1 Ingestion: none

Ten of ten companies fetched, parsed, classified and written. No companyfacts
fetch failed, no schema pin failed (`schema_pin_error: null` on all ten), no
company came back with zero facts. The two failure paths that exist are
recorded rather than raised — a companyfacts document with no fact under any
family tag is written as an empty table with every family ABSENT
(`test_a_company_with_no_xbrl_facts_is_absent_everywhere_not_a_crash`), and a
fetch that fails is raised as a named `IngestError("companyfacts_fetch_-
failed", …)` — and **neither fired on this draw**. They are untested against
real failures, which is stated, not hidden.

### 5.2 Panel: 7 of 50 cells unresolved

Listed in full in §4, with the classifier's reason for each. None was worked
around. No fallback tag was picked for any of them.

### 5.3 The one real defect this run found — CARG's revenue is a quarter

`pit.value_as_of` selects a fact by grouping candidates on **`period_end`
alone**. Its own docstring names the consequence and calls it the
"period-identity caveat": a filer that tags both the full year and Q4 with the
same end date presents two facts the rule cannot tell apart.

**MEASURED on this draw: 2 of the 43 resolved cells, in 2 of the 10
companies.** Both are a filer tagging the annual and the fourth-quarter figure
with the same `period_end`, in the same filing, on the same day:

| ticker | family | the year | the quarter | filed | what the panel returned |
|---|---|---|---|---|---|
| CARG | revenue (`RevenueFromContractWithCustomerExcludingAssessedTax`) | 906,980,000 (2025-01-01..2025-12-31) | 241,094,000 (2025-10-01..2025-12-31) | both 2026-02-19, same accession | the **quarter** |
| RNGE | net_income (`NetIncomeLoss`) | 19,167,678 (2025-01-01..2025-12-31) | 15,909,889 (2025-10-01..2025-12-31) | both 2026-03-31, same accession | the **quarter** |

Every tiebreak in the rule (latest `filed`, then largest `accession_number`)
is a tie, so which one is returned falls through to row order. TGLS and STC
tag only the year and show the year. **So the same column can be a year for
one company and a quarter for another** — and before this change nothing on
the page said so.

`pit.py` says explicitly that disambiguating this is the caller's job and a
feature-engineering decision; `pit.py` and `numeric_features_e2.py` are frozen
for this work. So `report_filing` does the one thing it can do honestly: the
Period column now spells out **how long each fact's own period is** — "12
months ending 2025-12-31", "3 months ending 2025-12-31", "as at 2025-12-31" —
using `ingest_fundamentals.DURATION_BUCKET_DAYS`, the same buckets the concept
resolution reports its `duration_mix` in, imported rather than retyped. A
reader is never shown a quarter under a heading that implies a year.

**This is a mitigation, not a fix, and it is an owner question** (§8): the
selection is still arbitrary between the two facts, and it affects the
research path identically — `numeric_features_e2` resolves revenue through the
same call for all 244 companies.

### 5.4 Renders

Every one of the ten companies was re-rendered after its fundamentals were
ingested: `report_filing.py --store data/app/companies/<cik> --latest 10-K`
and `--latest 8-K`, cache rebuilt each time. **18 of 20 renders produced a
page, in 6.3 seconds total** (0.3–0.6 s each; the panel adds no measurable
time, because it reads a 1,300–2,600-row store table instead of the
622,661-row research one).

| ticker | 10-K | 8-K | both renders (s) |
|---|---|---|---|
| SIRI | yes | yes | 0.7 |
| CBKM | yes | yes | 0.6 |
| TGLS | yes | yes | 0.7 |
| CARG | yes | yes | 1.0 |
| RNGE | yes | yes | 0.7 |
| AETN | yes | **NO** | 0.3 |
| STC | yes | yes | 0.7 |
| YSGL | yes | **NO** | 0.3 |
| REAL | yes | yes | 0.7 |
| ODYS | yes | yes | 0.7 |

**The two failures are the two L2.2 already recorded, unchanged and not
re-diagnosed here:** AETN has filed no 8-K carrying Item 2.02 and YSGL has
filed no 8-K at all, so `--latest 8-K` exits 1 with *"has no labeled 8-K in
the corpus"*. Both are the acceptance test's own step failing on a company
that has nothing to render, not a defect, and neither has anything to do with
fundamentals — **both companies' 10-K pages render, with their fundamentals
panels on them.**

**CBKM's 10-K now renders**, which it did not in L2.2 (§3: extraction produced
zero words, `no_toc_and_no_heading_match`). That is not this work — a parallel
change to the app lane's document reader fixed the filer dialect, and this run
simply benefited from it. What belongs here is that CBKM's page now carries
all five fundamentals, revenue included, resolved to the bank top line.

**Across every store page on disk for these ten companies — 28 of them, the
10-Q pages included — 123 of 140 family cells carry a number.** Every page
carries the panel; none is blank; the 17 unresolved cells all print the
classifier's reason.

*A scheduling note, since it cost real time and would cost it again.* The
first render pass failed on 18 of 20 with
`ValueError: operands could not be broadcast together with shapes (173,) (100,)`
— a store whose `chunks.parquet` had been rebuilt while its `labels.parquet`
had not. That was a parallel re-ingest/re-label of the same ten stores in
flight, not a fault in this work; the renders were held until every store's
chunk and label counts agreed again and then all ran clean. A store is only
renderable when those two counts match, and nothing currently checks that
before trying.

---

## 6. What this proves, and what it does not

**Proved.**

* A ticker outside the research universe now gets **real point-in-time
  fundamentals** on its page: 43 of 50 panel cells, resolved by F2's own
  classifier over the company's own XBRL history, point-in-time through
  `pit.value_as_of`, with the chosen XBRL tag, the period it covers, the date
  it was filed and the accession it came from printed beside every number.
* The resolution is **mechanical and per-company**. No ticker is named
  anywhere, no override map exists, and the bank top line, the ASC 606
  migration and the partnership tags are all ordinary family members.
* An **UNRESOLVED family stays unresolved**. Seven cells refuse, each with the
  classifier's own reason on the page. `resolved_tags` is empty by
  construction for an UNRESOLVED pair, and the panel is pinned never to put a
  number beside one (`test_an_unresolved_family_is_never_handed_a_tag`).
* It is **cheap**: 0.31 s and one EDGAR request per company, against 87–221 s
  for labeling the same company's text. Fundamentals do not change the
  feasibility of the live-demo path L2.2 measured.
* **F2's committed records are untouched**, enforced at runtime rather than by
  prose.

**Not proved, and stated plainly.**

1. **No number here has been checked against the filing it came from.** The
   values are what SEC's own XBRL says, resolved by a rule; nobody opened
   CarGurus' 10-K and compared. The one case where that would have caught
   something (§5.3) was caught by inspecting the *shape* of the data, not by
   reading a filing.
2. **The panel is five families of fourteen.** The other nine are ingested,
   classified and recorded in the store, and nothing reads them yet.
3. **Resolution is not correctness.** The classifier resolves on *disclosure
   coverage*. It does not check the unit (a non-USD reporter resolves exactly
   as cleanly — none of these ten is one, and the WARN that would say so fired
   zero times), it does not check the frequency, and it makes no claim that
   the tag means what its name suggests.
4. **The window rule is mine, not the owner's.** See §7. It was chosen to be
   non-clipping and is recorded in every manifest, but it is the one judgment
   call in this work that moves numbers, and the alternative is measured
   below rather than argued about.
5. **Four of ten companies show no revenue.** That is honest and it is also
   the single most visible hole on these pages.

---

## 7. The one open question: the classification window

The window this run used (**A**, the company's own XBRL life) gives external
companies a classification window of **39–77 reportable quarters**. A research
member's window is its membership spell inside the E2 corpus window
(2015-07-01 .. 2026-08-31), at most **45**. The 75% coverage bar, the
2-quarter staleness rule and the 1-quarter MIGRATION overlap allowance were
measured and ratified on windows of that length; applying them over 19 years
of a company's history asks a harder question than F2 ever asked of the 244.

The alternative (**B**) is to start the window at `IF.CORPUS_WINDOW_START`
(2015-07-01) — the corpus's own ratified constant, not a new number — and run
it to today, so an external company is scored on the same calendar window as a
research member. The fact table is unwindowed either way, so **B hides no fact
from `pit.value_as_of`**; it changes only what the classifier is asked.

**MEASURED on these ten, offline, from the tables already written:**

| ticker | quarters A | quarters B | families resolved A | B | panel cells A | B | what changed |
|---|---|---|---|---|---|---|---|
| SIRI | 75 | 44 | 10 | 12 | 4 | 5 | revenue PARTIAL→SINGLE, pretax_income PARTIAL→SINGLE, cash SINGLE→DOMINANT, operating_cash_flow MIGRATION→SINGLE |
| CBKM | 69 | 44 | 12 | 12 | 5 | 5 | — |
| TGLS | 60 | 44 | 12 | 12 | 5 | 5 | revenue MIGRATION→SINGLE, net_income/equity/cash SINGLE→DOMINANT |
| CARG | 47 | 43 | 11 | 11 | 5 | 5 | — |
| RNGE | 77 | 44 | 8 | 10 | 4 | 4 | cash OVERLAP→SINGLE, operating_cash_flow MIGRATION→SINGLE, shares_outstanding PARTIAL→SINGLE |
| AETN | 66 | 44 | 9 | 9 | 4 | 4 | — |
| STC | 71 | 44 | 11 | 12 | 5 | 5 | cash SINGLE→DOMINANT, shares_outstanding PARTIAL→SINGLE |
| YSGL | 9 | 9 | 5 | 5 | 2 | 2 | — |
| REAL | 39 | 39 | 12 | 12 | 5 | 5 | — |
| ODYS | 54 | 44 | 8 | 8 | 4 | 4 | cash SINGLE→DOMINANT |
| **total** | | | **98/140** | **103/140** | **43/50** | **44/50** | |

**B resolves five more families and exactly one more panel cell** (SIRI's
revenue). RNGE, AETN and ODYS keep their revenue failures under either window,
and YSGL is unaffected — it has no history to clip.

**A was shipped, deliberately**, on two grounds: it can only make the
classifier *stricter* (it never resolves something B refuses), and it
introduces no new constant. But B is the window under which the ratified
constants were measured, and the gain is real if small. **This is an owner
call, recorded here rather than made quietly.** Changing it is a one-line
change in `ingest_one.fundamentals_window` plus a re-run — 9 EDGAR requests,
3 seconds.

---

## 8. Follow-up work this run identified

* **The FY-versus-Q4 period collision (§5.3)** — it affects the research
  path's revenue feature identically, not just this page. Resolving it means a
  period-length filter in `numeric_features_e2.resolve_family_value` (or a
  `pit` helper that takes a duration), both of which are frozen modules and
  neither of which is this lane's to change.
* **The window question (§7)** — owner ruling wanted.
* **Nine ingested families render nowhere.** `eps_diluted`, `liabilities`,
  `cash`, `pretax_income` and `operating_income` all resolve for most of these
  ten companies and cost nothing more to show.
* **The non-USD WARN has never fired.** `IF.non_usd_problems` is wired into
  the store manifest's `warnings` block and produced zero rows across ten
  companies (all ten report in USD). It is untested against a real non-USD
  external filer; F2 has one (CIK 895728, CAD).
* **No fundamentals number has been checked against a filing** (§6 item 1).
  A ten-cell hand-check against the filings' own statements would cost an hour
  and would be the first real accuracy evidence this panel has.

---

## 9. How to reproduce

```bash
# one company (the store must already exist; ingest_one builds it if not)
python3 ingest_one.py --cik 1534675 --fundamentals

# all ten, from the sealed draw
python3 - <<'PY'
import json; from pathlib import Path
import ingest_one as IO
from edgar_client import EdgarClient
client = EdgarClient(verbose=False)
for r in json.loads(Path("data/app/status/external_draw.json").read_text())["drawn"]:
    IO.add_fundamentals(cik=int(r["cik"]), client=client)
PY

# the page
python3 report_filing.py --store data/app/companies/1534675 --latest 10-K
```

The draw is sealed and **must not be redrawn**. Re-running `--fundamentals` on
a labeled store is safe and touches no section, chunk or label: it rewrites
`fundamentals.parquet`, `concept_resolution.csv` and the `fundamentals` key of
`manifest.json`, and nothing else. On a warm companyfacts cache (< 24 h) it
makes zero EDGAR requests.

Each store's `manifest.json` carries the whole record under `fundamentals`:
the companyfacts cache path and sha, both output shas, the window and its
rule, the coverage bar and staleness threshold in force, and one row per
family with its state, tags, alternates, coverage, unit, duration mix and —
for a failure — the classifier's verbatim reason.

---

## 10. Tests

`python3 -m pytest -q test_report_filing.py test_app_store.py` — **green**.
This work adds **23 test functions (27 collected cases)** to
`test_app_store.py`, all synthetic-fixture only per §0.5; every number in this
file came from the ten real companies.

What they pin, briefly: both files are written; the parquet's arrow schema
*equals* `data/fundamentals_e2.parquet`'s and the CSV's columns *equal*
`data/f2/concept_resolution.csv`'s; every filed occurrence is kept and a
restatement is a new row; every family gets a row, resolved or not; the six
states are the classifier's own; an UNRESOLVED pair is never handed a tag and
never gets a number on the page; F2's three committed records are never
written (recorded at runtime, not asserted in prose); the window is the
company's own XBRL life; a company with no XBRL facts is ABSENT everywhere
rather than a crash; the panel resolves from the store's own files; it is
point-in-time in both directions (a fact filed after the as-of date is
invisible; a restatement filed before it wins, with its filed date shown); the
period column says how long each fact's period is; the `--store` redirect
covers exactly the two new readers, is restored even when the load raises, and
leaves the research path reading F2's own records.
