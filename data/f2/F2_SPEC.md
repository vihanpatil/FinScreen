# F2_SPEC — implementation spec for F2 stages S2–S6

**Written 2026-08-24 by the S1 data-engineer pass.** This is the plan of
record for F2's code stages. It sits under `EXPANSION_PLAN.md` (§3 rulings,
§4 phases, §5 coupling) and `F2_PROGRESS.md` (the stage ledger); where it
adds detail it does not override either. Nothing here changes membership,
the fold structure, the benchmark, or any owner-gated item.

**Everything numeric in this file is labelled either MEASURED (computed
this session from files on disk / a 2-GET live probe) or ESTIMATE (with its
basis).** No number here is carried over from a prior session's summary.

**S1 verification results (verify-artifact rule, HANDOFF §7):**

- `option_record_checksums.json` → **all 8 sha256 MATCH** the shipped
  `continuity5*/broad8*` files. The option record is intact.
- That file deliberately does **not** cover `hybrid136*` (it guards the
  pre-rules option record only). S1 therefore re-derived hybrid136's own
  invariants directly from the parquet: **244 distinct CIKs / 299
  membership spells / 1,496 panel rows / exactly 136 members at each of 11
  reconstitution dates 2016-07-01…2026-07-01 / 176 core + 68 extension /
  0 rows with `float_filed >= recon_date`** (PIT re-assertion clean).
  Section 1 below adds a checksum file for hybrid136 so S2+ can verify it
  in code instead of by hand.

---

## 1. Canonical membership artifact + adoption path

### 1.1 The artifact

The pipeline's universe input becomes
`data/universe_e2_candidates/hybrid136.parquet` (the **spells** table),
read **in place** — not copied to a new path. Copying invites two files
that can drift; F1's build script owns that directory and F2 only reads it.

`data/universe.csv` (E1's 25 tickers) stays on disk, untouched, as E1's
frozen record. It is no longer any E2 code path's input.

**Verify-artifact in code, not by hand.** Add a new sibling file
`data/universe_e2_candidates/hybrid136_checksums.json` (same shape and
spirit as `option_record_checksums.json`, separate file so the option
record's guard is not disturbed), pinned to the hashes S1 measured today:

```
hybrid136.csv              e72ea9040f79186e2ddc72fd3fc5d625ecb3c3f30f4656df2792eb61d0fc09c7
hybrid136.parquet          8a026f250627a74835e218e25755e0e49dfd825bf6d10d76fb32d53db5a4f135
hybrid136_panel.csv        15dd2218b44391270c6409eed56546db97c680aefd6079010681cd9b60178e3d
hybrid136_panel.parquet    14851a0d76f07bdca7e7e6d6ca27e553c63bb07f91ff4bd68a89e2f36de53dd1
manual_exclusions.csv      19299c262335fb4d09f10f6bed75de4d70b16aa1b42ac4299dacf560bff50bad
price_censoring_census.csv 525d41291676d7a2bc570c130abc297feee6514ae65ba40b23615c9b7672a26e
price_censoring_census.parquet 5a5e4a61dcf85405fc7590378e15dceb793176f8fc5b9ead2846ebf11965a8d6
```

`load_universe()` verifies these on **every** load and raises on any
mismatch. If F1 is ever legitimately re-run, the hashes are re-pinned by a
deliberate edit — never auto-rebaselined.

### 1.2 Schema contract (MEASURED from the parquet)

`hybrid136.parquet` — one row per **membership spell**, 299 rows:

| column | dtype | contract |
|---|---|---|
| `cik` | int64 | the join key for the entire E2 pipeline. Never `ticker`. |
| `name` | str | EDGAR registrant name at build time |
| `tickers` | str | comma-joined EDGAR `submissions.tickers[]`; **may be empty** (34 spells / 31 CIKs) and may hold preferreds/notes. Not a price key — see §6. |
| `sector` | str | one of 8 |
| `stratum` | str | `core` \| `extension` |
| `sic` | int64 | current SIC (stated look-ahead, F1 §1) |
| `member_from` | str `YYYY-MM-DD` | first reconstitution date of the spell |
| `member_to` | str `YYYY-MM-DD` or `''` | last reconstitution date; **`''` = still a member at 2026-07-01** (136 spells) |
| `n_reconstitutions`, `entry_sector_rank`, `exit_sector_rank`, `median_sector_rank`, `median_float_usd`, `all_dates` | — | descriptive, not consumed by F2 |

`hybrid136_panel.parquet` — one row per `(recon_date, cik)`, 1,496 rows,
carrying the float provenance (`float_filed`, `float_accn`, …). F2 does not
need the panel except to re-assert PIT; F5 will need it for
membership-dated benchmarks.

**Derived contract F2 code uses** (computed in `load_universe()`, not
stored):

- `coverage_start(cik) = max(CORPUS_WINDOW_START, min(member_from) − 730 days)`
  — 730 days because hybrid136's own eligibility rule already guarantees
  ≥1 10-K/10-Q in each of the 8 calendar quarters before every
  reconstitution date, so this is the interval the company is *known* to
  have filed across.
- `coverage_end(cik) = CORPUS_WINDOW_END` for a current member
  (`member_to == ''`), else `min(CORPUS_WINDOW_END, member_to + 400 days)`
  — 400 days ≈ one annual reporting cycle past the last date the company
  was a member, so its final 10-K is inside the window.
- `is_current_member(cik) = any(member_to == '')`.

### 1.3 `ingest_metadata.load_universe()` changes

```
def load_universe() -> pd.DataFrame       # returns one row per CIK
def load_membership() -> pd.DataFrame     # returns one row per spell
```

- reads the parquet, verifies checksums, asserts the schema columns above;
- collapses spells → one row per CIK for the ingestion loop (`cik`, `name`,
  `sector`, `stratum`, `coverage_start`, `coverage_end`,
  `is_current_member`), keeping the spells available separately;
- **the `20 <= len(df) <= 30` bound is deliberately removed.** It is
  replaced by `assert len(df) == 244` — not a range, an exact pin re-derived
  from the ratified table, with the same "refuse to proceed silently on a
  scope change" intent. `test_ingest_metadata_universe.py` pins 244/299/136
  and fails loudly if F1's artifact moves.
- `ticker` is no longer required and no longer a key. Every call site that
  used `row["ticker"]` uses `int(row["cik"])`.

### 1.4 SQLite schema changes (`data/filings_metadata.db`)

E1's DB is keyed on `ticker TEXT NOT NULL` in `filings`. That breaks on the
31 member CIKs with no ticker and on shared-CIK multi-class names. Changes,
all additive-or-widening:

- `companies`: `cik` stays PK; `ticker` becomes **nullable**; add
  `sector`, `stratum`, `coverage_start`, `coverage_end`,
  `is_current_member`.
- new `universe_membership(cik, sector, stratum, member_from, member_to,
  PRIMARY KEY(cik, member_from))` — the spells, so downstream can join
  membership without re-reading the parquet.
- `filings`: `ticker` becomes nullable and is **informational only**;
  `cik` gains a NOT NULL constraint and is the join key. All existing
  indices kept; add `idx_filings_cik_date`.
- new `distress_events(cik, accession_number, form, filing_date, items,
  event_kind)` — see §4.5. Zero extra network cost.
- `universe_validation_problems`: replace `ticker TEXT` with
  `cik INTEGER NOT NULL` + nullable `ticker`, and add a `stage` column
  (`metadata` / `documents`) so the two S6 segments can't stomp each other.

E1's DB is not migrated in place. S6 writes a **new** database file
`data/filings_metadata_e2.db`; `data/filings_metadata.db` stays frozen as
E1's record (same discipline as `data/labels.parquet`). All E2 modules take
`--db` with the E2 path as the default.

---

## 2. Fixed window dates

All four literals become module-level constants in one place —
`ingest_metadata.py` — and every other module imports them. Nothing is
computed from `date.today()` anywhere in F2 (E1's
`lookback_cutoff(today, 12 quarters)` is deleted, not parameterised).

```python
CORPUS_WINDOW_START = date(2015, 7, 1)   # documents/metadata enumeration floor
CORPUS_WINDOW_END   = date(2026, 8, 31)  # E2 corpus freeze date
FUNDAMENTALS_HISTORY = "full"            # no window; companyfacts full history kept
PRICES_HISTORY       = "full"            # no window; period1=0, as E1
```

**Why 2015-07-01, not 2016-01-01** (an amendment to `F2_PROGRESS.md` §5's
second proposal, argued not assumed): the first reconstitution date is
2016-07-01. A trailing-four-quarter text feature evaluated at a company's
first membership date needs that company's filings back to ~2015-07-01. A
2016-01-01 floor would leave the first two membership years' trailing
features half-populated for reasons invisible downstream.

MEASURED cost of the extra six months, over all 244 member CIKs from the
cached submissions: **45,622 target filings vs 43,445** (+2,177, +5.0%) and
**10,569 earnings 8-Ks vs 10,092** (+477, +4.7%). That is a rounding error
against §4's totals and buys a clean first fold.

**Why 2026-08-31 as a fixed end:** reproducibility. Enumeration filters
`filing_date <= CORPUS_WINDOW_END`, so a re-run in October yields the same
corpus. The F2 ingestion report must state the **observed** max
`filing_date` alongside the constant, so the gap between the freeze date and
the actual run is visible rather than assumed to be zero.

**These dates are a superset, not a fold structure.** Membership starts
2016-07-01; the earliest fold G3 could pre-register is bounded by
membership, not by ingestion. G3 remains untouched by F2.

---

## 3. Per-company-window validation redesign (EXPANSION_PLAN §3.6)

E1's `validate_universe()` assumes 25 currently-active always-filing
companies over one shared 12-quarter window. Every threshold is re-derived
below **against the real 244-member × 11-year distribution**, computed this
session from the cached submissions with no network.

### 3.1 Checks, re-scoped per company

Each check now runs over `[coverage_start(cik), coverage_end(cik)]`.

| check | E1 | E2 | rationale |
|---|---|---|---|
| `entity_resolves` | FATAL | FATAL, per CIK | unchanged |
| `history_reaches_cutoff` | FATAL vs one global cutoff | FATAL vs `coverage_start(cik)` | MEASURED: **0 of 244** members' EDGAR history starts after their own `coverage_start` — the check is expected to fire on nothing, which is what a regression guard should do |
| `plausible_filing_counts` | FATAL <2 10-K / <7 10-Q | FATAL if periodic filings per coverage-year < **3.5**; WARN < **3.9** | MEASURED distribution over 244 members: min **3.91**, p5 4.04, median 4.07, max 4.51. 3.5 = min-observed −10%, same calibration discipline E1 used |
| `no_large_filing_gap` | FATAL >135 d | **WARN >135 d, FATAL >300 d**, gaps measured only *inside* the coverage window | MEASURED max-gap distribution: median 115, p90 125, p95 126, p99 170, **max 266**. >135 fires on **5** members (largest: CIK 849399 Gen Digital 266 d, 1637459 217 d, 769397 Autodesk 189 d — all fiscal-calendar quirks, not truncation); **0** members exceed 300 d. The FATAL arm's real job is catching a silently truncated `filings.files[]` fetch (the JPM/BAC/GS bug), which shows up as ≥3 missed quarters |
| `recent_activity_10k_10q` | FATAL for everyone | FATAL **only if `is_current_member`**; otherwise `member_stopped_filing` at **INFO** | a delisted member that stopped filing is an expected state (EXPANSION_PLAN §2c). MEASURED: **29** of 244 members' last periodic filing is >200 d before the freeze date — exactly F1's 29 delisting-censored count |
| `recent_activity_any_form` | WARN | WARN, current members only | unchanged in spirit |
| `current_ticker_matches` | WARN | **removed** — replaced by §6's price-mapping report | the universe no longer carries an authoritative ticker |
| `cik_map_agreement` | WARN | WARN, kept as a contradiction detector | MEASURED: **0** contradictions across 244 members under §6's rule (plus the one reviewed XOM override) |
| `earnings_doc_unresolved` | *(none — failures only printed)* | new: WARN per failure, **FATAL if the failure rate >1%** of earnings 8-Ks | §4.4 |

### 3.2 Fixing the override design flaw

E1's `--allow-incomplete-universe=check1,check2` downgrades a check for the
**whole run**. With 244 companies that is exactly the bug it was built to
avoid, one level up: accepting a known-OK finding for one delisted member
would disarm that check for all 243 others.

**Fix (EXPANSION_PLAN §3.6: fixed, not worked around):** delete the CLI
flag entirely and replace it with an evidenced, per-`(cik, check_name)`
exceptions file, `data/f2/validation_exceptions.csv`, modelled column-for-
column on `manual_exclusions.csv`:

```
cik,check_name,reason,effective_from,effective_to,evidence_filed,evidence,added
```

Semantics, deliberately identical to F1's exclusions mechanism so there is
one pattern to learn:

1. An exception downgrades FATAL → WARN for **exactly one (cik, check)**
   pair; it can never widen.
2. A dated exception (`effective_from` set) is **rejected at load time**
   unless `evidence_filed < effective_from` — the same point-in-time guard
   F1 put on dated exclusions.
3. Every exception is printed loudly in the run report, whether it fired or
   not; an exception that never fires is reported as dead and is a bug in
   the file, not a harmless leftover.
4. There is no blanket switch and no CLI escape hatch. A new FATAL means
   either the data is wrong or the check is wrong; both get fixed, not
   overridden.

**Expected initial contents: empty.** MEASURED: under §3.1's per-company
windows, all 244 members pass `history_reaches_cutoff`, all pass
`plausible_filing_counts` at 3.5/yr, none exceeds the 300-day FATAL gap, and
staleness FATALs only apply to current members. If S6 produces a FATAL, that
is new information and must be read, not overridden.

### 3.3 Two latent bugs to fix while here

- **`write_validation_problems()` is only called when the override flag was
  passed** (`ingest_metadata.py:863` — `if allow_incomplete_universe is not
  None:`). A normal run's validation findings are printed and then thrown
  away, contradicting the flag's own help text. Fix: always persist.
- `validate_universe()` and the ingestion loop each call
  `get_effective_recent()` per company. Harmless (cached, 0 extra GETs) but
  at 244 companies it doubles the JSON parse cost; pass the already-fetched
  dict through. Optional; do it only if S3 measures it as material.

### 3.4 Fundamentals-side validation

`validate_fundamentals()` gets the same per-company treatment: the coverage
denominator becomes the company's own reportable quarters between
`coverage_start` and `coverage_end`, not a shared 12. `CORPUS_WINDOW_START/
END` stop being fundamentals-local literals and are imported from §2.

---

## 4. S3 — metadata + documents at scale

### 4.1 Enumeration

Unchanged in mechanism (this is E1 code that works): per CIK,
`get_effective_recent(cik, coverage_start(cik))` → filter to
`TARGET_FORMS = {10-K, 10-Q, 8-K}` and
`coverage_start <= filing_date <= CORPUS_WINDOW_END`.

MEASURED over the 244 members from the cached submissions, window
2015-07-01 → 2026-08-31:

| | count |
|---|---|
| 10-K | 2,452 |
| 10-Q | 7,532 |
| 8-K | 35,638 |
| **total target filings** | **45,622** |
| 8-K with item 2.02 (earnings) | 10,569 |
| CIKs needing `filings.files[]` pagination for this window | 168 |
| pagination chunk documents required | 351 (all 351 already cached) |

### 4.2 Confirmation of `F2_PROGRESS.md` §5's first proposal

**CONFIRM: ingest the full E2 window for every CIK that is ever a member;
do not clip fetches to membership spells.** Reasons, in order of weight:

1. Clipping is not merely simpler-to-skip, it is **wrong for the data we
   need**: a member at date *t* needs pre-*t* filings for trailing-window
   text features and pre-*t* fundamentals/prices for any PIT lookup. A
   spell-clipped fetch would have to re-derive that lookback anyway.
2. Spells are non-contiguous (299 spells over 244 CIKs — 55 CIKs re-enter),
   so clipping means per-CIK multi-interval logic in the enumerator: pure
   bug surface for no benefit.
3. Storage is cheap and MEASURED (§4.6): ~26 GB against **341 GB free** on
   the owner's disk.
4. PIT safety is unaffected — ingestion breadth never implies membership;
   the membership join happens downstream.

**One binding condition attached to the confirmation:** because the ingested
corpus is deliberately wider than the universe, the F2 report must state the
count of ingested filings whose `filing_date` falls **outside every**
membership spell of their CIK, so nobody downstream mistakes "in the corpus"
for "in the universe." F5 joins on `universe_membership`, never on "present
in `filings`."

### 4.3 Cache layout under `data/raw/`

No new conventions; existing directories only.

| dir | policy | E2 role |
|---|---|---|
| `submissions/` | 24 h TTL | 244 CIK docs + 351 chunk docs |
| `filing_index/` | cache forever | 1 doc per earnings 8-K (10,569) |
| `documents/` | cache forever | 10-K/10-Q primary docs + EX-99 exhibits |
| `companyfacts/` | 24 h TTL | 244 docs (§5) |
| `prices/yahoo/` | 20 h TTL | 213 docs (§6) |
| `frames/`, `companyconcept/` | — | F1's; F2 does not touch them |

**Idempotency note (states the real property, not an aspiration):** within
one campaign (< 24 h) a killed-and-resumed run re-fetches nothing — the TTL
caches are still fresh and the cache-forever caches are hits. A re-run
*days* later re-downloads submissions + companyfacts (~1.2 GB, ~10 min),
because that TTL exists for correctness. To make a deliberate cheap re-run
possible, add an optional `max_age_hours` argument to
`EdgarClient.get_submissions/get_submissions_chunk/get_companyfacts`
(`_is_stale()` already supports it) exposed as `--cache-max-age-hours`,
default unchanged at 24. This is the only change to `edgar_client.py`.

### 4.4 EX-99 earnings-exhibit selection audit (per new filer)

219 of the 244 member CIKs are filers E1's selection policy has never seen,
and three sectors (industrials, utilities, materials/real-estate) are new
entirely. The policy in `select_earnings_document()` is not changed
speculatively; it is **audited on real output**:

1. Every earnings 8-K's selection is recorded as today
   (`earnings_doc_section_type`, `earnings_doc_selection_confidence`).
2. New: failures are **counted**. Today an index-parse failure prints a WARN
   and continues, leaving the columns untouched and the failure untracked.
   S3 collects them into `universe_validation_problems` with
   `check_name='earnings_doc_unresolved'`, WARN per case, and **FATAL if the
   aggregate failure rate exceeds 1%** of the 10,569 earnings 8-Ks.
3. New: `data/f2/ex99_selection_audit.csv` — one row per CIK ×
   `section_type` × `selection_confidence`, plus `first_seen_year`, plus a
   `new_filer` flag (not one of E1's 25).
4. **Mandatory manual read before S6 is declared done:** every CIK with any
   `low`-confidence selection, any `8K_BODY` fallback, or any CANARY line in
   the run log — read one filing per such CIK against its EDGAR index page.
   Cap the read at the 20 worst filers by low-confidence count if the list is
   longer; report the cap and the untouched remainder honestly.
5. Sector coverage assertion: the audit must show ≥1 high-confidence
   `EX99_PRESS_RELEASE` selection in **each of the 8 sectors**; a sector with
   none is a blocker, not a footnote.

MEASURED live probe (2 GETs, rate-limited, project User-Agent): CAT
(CIK 18230, an extension-stratum filer E1 never touched), 8-K
`0000018230-16-000702` filed 2016-10-25 → index parsed to 6 document rows,
selection `cat_exx991xq3x2016xearning.htm`, `EX99_PRESS_RELEASE`,
confidence **high**. The 2016-era index format and the E1 policy work
unmodified on a new filer, a new sector, and a pre-iXBRL vintage.

### 4.5 Distress events — free, and mandatory

EXPANSION_PLAN §2c makes ingesting EDGAR-native distress outcomes
**mandatory** so censored names stay visible. They are already inside the
submissions JSON F2 parses, so this costs **zero extra network requests**
and ~20 lines: while enumerating, also emit rows for forms
`25`, `25-NSE`, `15-12B`, `15-12G`, `15-15D`, `15F-12B`, `15F-12G` and for
8-Ks carrying item `1.03`, into `distress_events`.

MEASURED over the 244 members in-window:

| event | filings | distinct CIKs |
|---|---|---|
| Form 25 (delisting) | 37 | 30 |
| Form 25-NSE (exchange-filed) | 510 | 131 |
| Form 15-12B | 65 | 42 |
| Form 15-12G | 22 | 21 |
| Form 15-15D | 32 | 13 |
| 8-K item 1.03 (bankruptcy) | 2 | 1 (CIK 895126, Expand Energy / Chesapeake) |

`25-NSE` is filed by the exchange and fires for preferreds and notes too —
it is stored but must be reported as the noisy series it is; Form 25 +
Form 15 + item 1.03 are the meaningful ones.

### 4.6 Documents: a separate, prefetch-only segment

F3 runs `extract.py`, which today fetches each document lazily. Mixing a
multi-hour network walk into the extraction pass makes both harder to
resume. **Add `--stage {metadata,documents,all}` to `ingest_metadata.py`**
(no new module, no framework). `--stage documents` reads the `filings`
table and calls `EdgarClient.get_archive_document()` for:

- every 10-K / 10-Q primary document → `/Archives/edgar/data/{cik}/
  {accession_nodash}/{primary_document}` (9,984 documents), and
- every resolved `earnings_doc_relative_path` (10,569 documents).

It parses nothing and stores nothing but the cache; F3's `extract.py` then
runs at **0 GETs**. The module docstring's "no filing text is downloaded
here" line is updated deliberately, with the reason.

MEASURED inputs to the size estimate: E1's `data/raw/documents/` holds 639
files / 1.20 GB (mean 1.88 MB; non-EX-99 mean 2.27 MB, EX-99 mean 0.52 MB);
a live probe of CAT's 2016 10-K primary document returned **7.90 MB**, so
pre-iXBRL 10-Ks are not smaller than modern ones.

**ESTIMATE (basis: those measured means, applied to §4.1's counts):**

| | count | ~MB each | ~GB |
|---|---|---|---|
| 10-K primary | 2,452 | 4.0 | 9.8 |
| 10-Q primary | 7,532 | 1.5 | 11.3 |
| EX-99 / 8-K body | 10,569 | 0.5 | 5.3 |
| **total** | **20,553** | | **~26 GB** (range 18–40) |

341 GB free — not a constraint, but the number belongs in the runbook.

---

## 5. S4 — fundamentals, systematic (EXPANSION_PLAN §3.5)

### 5.1 The key economic fact

`companyfacts` returns **every** concept a company ever tagged in one
document. Broadening the concept set therefore costs **zero additional
network requests and zero additional bytes** — only parse time. E1's
13-concept list was a scope choice, not a cost constraint. E2 should be
generous.

### 5.2 Concept families replace the flat CONCEPTS list

Replace `CONCEPTS: list[tuple[str, str]]` with
`CONCEPT_FAMILIES: dict[str, list[tuple[str, str]]]` — a logical concept
mapped to an ordered list of acceptable tags (preference order used only for
reporting, never to silently pick one). Every tag in every family is
ingested and stored **as-is under its own tag name**; no unification happens
in the ingestion layer (that boundary is unchanged).

MEASURED availability across the 25 cached companyfacts documents (`n/25`
companies where the tag exists at all) — every proposed tag is real:

| family | tags | measured |
|---|---|---|
| `revenue` | Revenues · RevenueFromContractWithCustomerExcludingAssessedTax · RevenueFromContractWithCustomerIncludingAssessedTax · RevenuesNetOfInterestExpense · InterestAndDividendIncomeOperating | 24 · 17 · 1 · 2 · 3 |
| `net_income` | NetIncomeLoss · **ProfitLoss** · NetIncomeLossAvailableToCommonStockholdersBasic | 25 · **19** · 13 |
| `operating_income` | OperatingIncomeLoss · IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest | 16 · 23 |
| `assets` | Assets | 25 |
| `liabilities` | Liabilities · LiabilitiesAndStockholdersEquity | 19 · — |
| `equity` | StockholdersEquity · **StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest** · MinorityInterest | 24 · **17** · 16 |
| `cash` | CashAndCashEquivalentsAtCarryingValue · **CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents** · CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsIncludingDisposalGroupAndDiscontinuedOperations · **CashAndDueFromBanks** | 25 · **24** · 4 · **3** |
| `operating_cash_flow` | NetCashProvidedByUsedInOperatingActivities · NetCashProvidedByUsedInOperatingActivitiesContinuingOperations | 25 · 14 |
| `eps_diluted` | EarningsPerShareDiluted · EarningsPerShareBasicAndDiluted | 24 · 0 |
| `shares_outstanding` | dei:EntityCommonStockSharesOutstanding | 25 |

The bolded tags are exactly the four HANDOFF §2a trap (b) named as
documented-but-not-ingested. `EarningsPerShareBasicAndDiluted` is 0/25 in
E1's mega-caps and is kept anyway — it is common among single-class filers,
and it is free.

**E1's hand-curated per-ticker maps are superseded and deleted**:
`BANK_TICKERS_MISSING_INDUSTRIAL_CONCEPTS`, `BANK_EXEMPT_CONCEPTS`, and
`KNOWN_MIDWINDOW_MIGRATIONS` all disappear. Every case they encoded (JPM/
BAC/GS cash → `CashAndDueFromBanks`; MA/OXY/SLB → `ProfitLoss`; CVX →
restricted-cash) becomes an ordinary family member that the classifier
resolves mechanically. They are deleted from code and **preserved verbatim
in the S4 completion report** as the record of what the automated classifier
had to reproduce — and reproducing them is S4's acceptance test (§8).

### 5.3 The alias / migration classifier

Per `(cik, family)`, over the company's own coverage window, using only
rows from operating forms (`10-K`, `10-Q`, `8-K`, and their `/A`
amendments — this is HANDOFF §2a trap (c): MA's only in-window
`NetIncomeLoss` rows are DEF 14A compensation tables), classify into exactly
one state:

| state | condition | severity |
|---|---|---|
| `SINGLE` | exactly one tag has coverage ≥ 75% of the company's reportable quarters | resolved |
| `MIGRATION` | ≥2 tags, and their covered-quarter sets are disjoint (allowing ≤1 quarter of overlap), and their union covers ≥ 75% | resolved; the switch quarter is recorded |
| `OVERLAP` | ≥2 tags covering the same quarters, union ≥75% | **UNRESOLVED** |
| `PARTIAL` | union coverage in [40%, 75%) | **UNRESOLVED** |
| `ABSENT` | no tag in the family has any in-window row | **UNRESOLVED** |

**UNRESOLVED never resolves stale.** It emits a
`fundamentals_alias_unresolved` FATAL row per `(cik, family)` naming the
tags seen, their per-quarter coverage, and the exact reason. There is no
fallback to "the tag with the most rows," and no per-ticker override map.
The output artifact `data/f2/concept_resolution.csv`
(`cik, family, state, tags, switch_quarter, coverage, severity`) is what F5
consumes to build a series — F5 must refuse to build a feature from an
UNRESOLVED pair.

**Concentrated missingness is a blocker (EXPANSION_PLAN §3.5).** After
classification, aggregate UNRESOLVED by `(sector, family)`; any cell above
**20% of that sector's members** is reported as a BLOCKER at the top of the
F2 report, not buried in a per-company list. Rationale for 20%: a family
that fails for one in five of a sector's members is a taxonomy mismatch, not
per-filer noise, and would silently bias any sector-stratified E2 result.

`ABSENT` is genuinely expected for some families in some sectors (banks have
no `OperatingIncomeLoss` in any form). The classifier does **not** encode
that expectation — it reports it, the sector aggregation surfaces it, and a
human rules on it once in the S4 report. That is the difference between the
E1 hand-map and a classifier.

### 5.4 Volume

ESTIMATE (basis: E1's 42,158 rows / 25 companies / 13 concepts, scaled by
244 companies and ~24 tags, discounted for the shorter histories of newer
registrants): **600k–1.0M rows**, parquet ~25–60 MB. Network: 244
companyfacts GETs, MEASURED mean 4.46 MB / max 7.89 MB per document in the
25 cached ones → **~1.1 GB**.

### 5.5 AMENDMENT A1 — "substitutes-only families + explicit dominance" (2026-08-24)

*Appended, not a rewrite: §5.2 and §5.3 above are S1's original text and stay
as the record of what was ratified first. Where this block and the text above
disagree, this block wins. Ruling: main session, `F2_PROGRESS.md` §5,
2026-08-24. Evidence: `data/f2/status/S4_fundamentals.md` (both passes) and
`data/f2/concept_resolution_preview_25.csv`.*

**Why.** S4's first pass implemented §5.2/§5.3 faithfully and MEASURED
**86/250 (cik, family) pairs UNRESOLVED** on E1's own 25 companies, with
`MIGRATION` never firing once and 22 sector BLOCKERs. Cause: §5.2's families
grouped tags that are not economic substitutes (`Liabilities` with
`LiabilitiesAndStockholdersEquity`, which is total *assets*; parent-share with
NCI-inclusive income; balance-sheet cash with the ASU-2016-18 cash-flow
total), and §5.3 read legitimate co-reporting as ambiguity.

**A1.1 Families are substitutes-only.** A family may contain only tags that
are alternative representations of ONE logical series — true aliases or
migration successors. Related-but-distinct concepts get their own single-tag
family: still ingested, trivially resolved, and available to F5, which
decides any proxy use in the open. §5.2's table is replaced by
`CONCEPT_FAMILIES` in `ingest_fundamentals.py`: **14 families over 26 tags**
(§5.2's 25 regrouped, plus
`IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments`,
a measured membership adjustment — the variant §5.2 carried exists for 23/25
companies but is thinly covered: MSFT 24/44 quarters vs 31, JNJ 24 vs 29, MA
12 vs 43). New single-tag families: `net_income_to_common`,
`liabilities_and_equity`, `minority_interest`, `pretax_income`.
`operating_income` is `OperatingIncomeLoss` alone — pre-tax income never
stands in for it silently.

**A1.2 Preference order is resolution semantics.** New resolved state
**`DOMINANT`**: when ≥2 tags of one family clear the coverage bar, the
highest-preference tag that is not stale wins, and the co-reported alternates
are recorded in a new `alternates` column on `concept_resolution.csv` (now 8
columns; §5.3's 7 are unchanged and keep their meaning). `OVERLAP` therefore
now means genuine ambiguity only: ≥2 current tags, none clearing the bar.

**A1.3 A tag must be current, not merely covered.** A tag can clear a 75% bar
computed over an 11-year window and still have died years ago; resolving to
it is precisely how E1 froze JNJ's operating income at 2015. A tag is STALE
when its last covered quarter is more than `STALE_TAIL_MAX_QUARTERS = 2`
quarters before the company's own last quarter with any fundamentals data
(anchored on the company, not the calendar, so a delisted member does not go
stale in every family for having stopped filing). A family whose every
bar-clearing tag is stale is `PARTIAL`-UNRESOLVED. MEASURED calibration over
the 25 cached companies: of 371 at-bar (company, family, tag) instances, 366
have a zero-quarter gap, 2 have 1, **none has 2**, and the only larger gaps
are three genuinely dead tags (SLB `OperatingIncomeLoss` 9, OXY
`NetIncomeLoss` 9, GOOGL `RevenueFromContractWithCustomerExcludingAssessedTax`
5).

**A1.4 `MIGRATION` covers hand-offs, not just disjoint switches.** With
substitutes-only families, a filer that co-reported two tags for years and
then dropped one still leaves an unambiguous chronological series. MIGRATION
fires when the union clears the bar, the newest tag is current, and either
the sets are disjoint (≤1 shared quarter) or exactly one tag is still live.
Tags are ordered by LAST covered quarter, so `tags[-1]` is always the current
one, and `switch_quarter` is where the successor takes over — its first
quarter after its predecessor's last.

**A1.5 SLB supersedes §8.2's prediction.** §8.2 predicted SLB
`operating_income` → `MIGRATION` to `ProfitLoss`. That is wrong twice:
`ProfitLoss` is a net-income tag, and E1's hand-map papered over a real
concept change (SLB stopped reporting a GAAP operating-income line in 2024).
The ruled-correct outcome is **loud `PARTIAL`** — 35/44 = 80% coverage, STALE
by 9 quarters — and it is pinned by an acceptance test.

**Unchanged by A1:** the 75% coverage bar, the 40% PARTIAL floor, the
operating-forms-only rule (trap (c)), "UNRESOLVED never resolves stale", the
per-`(cik, family)` FATAL row, and the 20% sector-BLOCKER rule.

**MEASURED effect** (25 cached companyfacts, E2 windows, offline): UNRESOLVED
**86/250 (34%) → 57/350 (16%)**; on the ten pre-amendment families alone,
**86/250 → 23/250 (9%)**. `OVERLAP` **22 → 0** — no genuine ambiguity remains
in E1's universe. `MIGRATION` **0 → 13**. Sector BLOCKERs **22 → 17**, all 17
individually justified in the S4 report and 15 of them ABSENT-only cells
(the concept does not exist for those filers). Every E1 hand-map case now
lands in a deliberate documented state.

### 5.6 AMENDMENT A2 — the two S4 second-pass items, ruled (2026-08-24)

*Appended, same discipline as A1. Ruling: main session, `F2_PROGRESS.md` §5
("S4 second-pass items"), 2026-08-24. Evidence:
`data/f2/status/S4_fundamentals.md` §10.*

**A2.1 `us-gaap:Cash` joins the `cash` family at LOWEST preference.** For a
filer that never tags any broader cash line, plain `Cash` is that filer's
balance-sheet cash representation; dominance (A1.2) guarantees it can never
displace a proper tag, and `concept_resolution.csv` records which tag won, so
the definitional caveat — `Cash` excludes cash equivalents — travels with the
data. Provenance-tracked coverage beats a manufactured gap at 244 scale, and
a consumer needing cash-with-equivalents strictly can filter on the resolved
tag name. The caveat is written into the family definition's comment.
MEASURED on the 25 cached companyfacts: **a strict addition — exactly one
resolution changed.** SLB `cash` PARTIAL/UNRESOLVED → **SINGLE on `Cash`**
(44/44, vs 52% for the best proper tag); no other company's state, resolved
tag, alternates or switch quarter moved, and no other company carries `Cash`
even as an alternate. Family count 26 → **27 tags**. Preview UNRESOLVED
57/350 → **56/350**.

**A2.2 `BLOCKER_EXEMPT_CELLS` — one mechanism, three entries.** A dict of
`(sector or "*", family) → one-line reason`, exempting a cell **only** from
the sector-BLOCKER aggregation. Binding semantics:

1. Per-`(cik, family)` UNRESOLVED rows are **never** silenced — every failure
   is still counted, named and emitted as a FATAL
   `fundamentals_alias_unresolved`. `resolution_problems()` does not know the
   dict exists.
2. Every exemption is printed in the run report whether it fired or not, with
   its reason and the cells it suppressed; one that fires on nothing is
   reported as **DEAD** — a bug in the dict, not a harmless leftover. Same
   discipline as `data/f2/validation_exceptions.csv` (§3.2).
3. Entries are added **by ruling only**. A cell that measurement suggests
   belongs here goes into the stage report as PROPOSED-not-exempted.

Ruled-in entries: `("*", "minority_interest")` — exists only for filers with
non-controlling interests; `("*", "net_income_to_common")` — differs from net
income only with preferred stock; `("financials", "operating_income")` — the
E1-documented HANDOFF §2a trap (a) fact that banks have no GAAP
operating-income line. Rationale, recorded in the code comment: HANDOFF §4's
crying-wolf lesson — an aggregate alarm that always carries
structurally-expected cells trains its reader to skim past the real one.

MEASURED: preview BLOCKERs **17 → 6** (all three exemptions fire, none dead;
11 cells suppressed), with the 56 per-pair FATAL rows unchanged — including
all 15 `minority_interest` failures. The six survivors are `energy
operating_income` 5/5, `consumer liabilities` 3/5, `healthcare
operating_income` 3/5, `consumer pretax_income` 2/5, `financials
shares_outstanding` 2/5, `healthcare liabilities` 2/5.

**Unchanged by A2:** the 20% threshold itself, every classifier state and
threshold, and every per-pair reporting rule.

---

## 6. S5 — prices at scale

### 6.1 CIK-verified ticker resolution (the APC→ARKO / EMC→ETF rule, in code)

The trap: `company_tickers.json` maps `APC` → CIK 2080921 and has no entry
for `EMC` at all (MEASURED from the cached map). A dead member's former
symbol has been reassigned. The rule is therefore: **the only admissible
source of a member's ticker is EDGAR's own `submissions.json` for that CIK**,
which is CIK-keyed by construction.

```
candidates = submissions(cik)["tickers"]            # EDGAR's own, current
candidates = [t for t in candidates if not NON_COMMON.search(t)]
NON_COMMON = re.compile(r"-(P[A-Z]?|WT[A-Z]?|RI|U|W)$")   # preferreds, warrants, rights, units
chosen = candidates[0] if candidates else None      # EDGAR's own ordering
if chosen and bulk_map.get(chosen) not in (None, cik): reject → censored
if chosen is None: censored
```

Note the two deliberate asymmetries:

- `-A` / `-B` suffixes are **kept** (they are share classes, not
  preferreds) — this is what lets Berkshire resolve to `BRK-B`, and Yahoo
  uses the same dash convention.
- The bulk map is a **contradiction detector only**, never a requirement.
  MEASURED: `AEP` (CIK 4904) and `EA` (CIK 712515) are simply absent from
  the cached `company_tickers.json`; requiring presence would censor two
  live large caps for an SEC file's gap.

MEASURED result of running exactly this rule over all 244 members:

| | count |
|---|---|
| CIK-verified ticker chosen | **212** |
| censored (no admissible ticker) | **32** |
| contradicted by the bulk map | **0** |
| of the censored: no ticker at all in submissions | 31 |
| of the censored: preferreds only (CIK 30554, EIDP — correct) | 1 |

Regression against E1: the rule reproduces all 25 E1 ticker↔CIK pairs
**except XOM**, which it censors (CIK 34088's submissions carry no ticker;
`XOM` maps to successor CIK 2115436).

### 6.2 The successor-CIK override — exactly one row, evidenced

`data/f2/price_ticker_overrides.csv`
(`cik, ticker, reason, evidence, added`), same discipline as
`manual_exclusions.csv`: every row is primary-source-evidenced and printed
in the run report whether or not it fires.

**It contains exactly one row: CIK 34088 → `XOM`.** Justification: this is
the same reviewed override `data/universe.csv` already carries; the ticker
migrated to a holding CIK in a reorganisation with no economic
discontinuity, and E1 already fetched and validated XOM's series under this
symbol.

**CIK 29915 (Dow Chemical Co /DE/) is deliberately NOT overridden**, even
though F1 flags it as the other still-filing no-ticker member. Today's `DOW`
is Dow Inc (CIK 1751788), a 2019 spin-off whose price history does not
contain Dow Chemical's pre-2019 series. Mapping 29915 → `DOW` would be
precisely the F1 trap. It is censored and counted.

Final: **213 tickers fetched, 31 member CIKs censored (27 core / 4
extension).** That pair — never the union — is what accompanies any
stratified E2 result, per the F1 stratum analysis rule.

### 6.3 Reconciliation with `price_censoring_census`

S5 re-derives the census at fetch time and **diffs against F1's**
(`price_censoring_census.parquet`, 247 rows / 9 columns). Expected diff,
pre-registered here so an unexpected one is visible: F1's 31 no-current-
ticker members, **minus** XOM (overridden), **plus** EIDP (preferreds only,
which F1's `has_current_ticker` counted as resolvable) = 31. Any other delta
is a finding and is reported, not reconciled away. Output:
`data/f2/price_ticker_map.csv` (`cik, name, stratum, chosen_ticker,
all_candidates, status ∈ {resolved, override, censored}, reason`).

### 6.4 Fetch changes

- `load_universe()` in `ingest_prices.py` is replaced by the map above;
  the parquet gains a **`cik` column** and keeps `ticker` — the join key
  downstream is `cik`.
- **Stooq is no longer attempted by default.** It has been bot-gated
  site-wide since 2026-08-18 and its robots.txt disallows automated access;
  attempting it 213 times to fail 213 times is both wasteful and impolite.
  Add `--price-source {yahoo,stooq-first}` defaulting to `yahoo`; the Stooq
  code path stays intact and one flag away, so the ratified "Stooq-class"
  option is preserved rather than deleted. This is a build-level ruling
  (§9), flagged for owner visibility because the owner's 2026-08-18
  ratification named Stooq by example.
- Full history retained (`period1=0`), as E1. The `source` column stays and
  is the provenance record; every row will read `yahoo_finance_chart` for
  this run.
- New sanity tripwire at parse time, free: compare the Yahoo response's
  `meta.symbol` to the requested symbol and `meta.instrumentType` to
  `EQUITY`; mismatch → WARN naming the CIK. Cheap defence against a symbol
  silently resolving to a different instrument.
- `validate_prices()`: `missing_entirely` becomes FATAL only for a
  **resolved** ticker. A censored CIK is not a price failure — it is a
  counted exclusion and appears in the censoring report, never as a FATAL
  and never silently.
- The universe-average return benchmark is **not** built here (that is F5
  and gate G3). S5 only notes that the benchmark will be computed over
  membership-dated, price-resolved members and that 31 members contribute
  none.

ESTIMATE: 213 requests at the client's 1.5 s minimum interval ≈ **6 min**;
~1.5–2.0 M rows; parquet ~40–80 MB (basis: E1's 271,372 rows / 25 tickers,
scaled with a discount for younger registrants).

---

## 7. S6 runbook skeleton

Four segments, strictly ordered, each a **single idempotent command**. Run
as main-session background tasks in an auto-resume chain (HANDOFF §4): any
task can be SIGTERMed at any time; on a kill notification, re-run the same
command — the cache makes the repeat cheap. Never launch these from inside a
subagent. `data/f2/status/S6_runs.md` is updated per segment with start
time, end time, exit status, GET count and the observed max `filing_date`.

| # | segment | command | GETs (MEASURED counts) | bytes | ESTIMATE wall-clock |
|---|---|---|---|---|---|
| 1 | metadata | `python3 ingest_metadata.py --stage metadata --db data/filings_metadata_e2.db` | 244 submissions + 351 chunks + ≤10,569 index (640 already cached) ≈ **11,164** | ~0.6 GB | **30–50 min** |
| 2 | documents | `python3 ingest_metadata.py --stage documents --db data/filings_metadata_e2.db` | **20,553** | **~26 GB** | **1–2.5 h** |
| 3 | fundamentals | `python3 ingest_fundamentals.py --db data/filings_metadata_e2.db` | **244** | ~1.1 GB | **15–25 min** |
| 4 | prices | `python3 ingest_prices.py --db data/filings_metadata_e2.db` | **213** | ~0.2 GB | **6–12 min** |

**Total: ~32,174 EDGAR GETs + 213 Yahoo GETs, ~28 GB, ~2–4 h wall-clock.**

Basis for the wall-clock estimates: a live 2-GET probe measured an index GET
at 8.3 KB / 0.15 s and a 7.90 MB document at 0.19 s (≈40 MB/s). Bandwidth is
**not** the binding constraint; per-request round-trip is, at an effective
4–7 req/s against the client's 10 req/s cap. Segment 2's range is the
per-request floor (20,553 / 7 ≈ 49 min) to a conservative 2.5 h allowing for
slower SEC responses and disk writes.

Resume properties, stated exactly:

- Segments 1 and 2 re-run at ~0 network cost within 24 h of each other:
  `filing_index/` and `documents/` are cache-forever, and `submissions/` is
  still inside its 24 h TTL. Only a re-run **days** later re-pays the
  submissions/companyfacts TTL (~1.2 GB, ~10 min) — or use
  `--cache-max-age-hours` (§4.3).
- Segment 2 is the only one long enough to be killed mid-flight in practice.
  It has no partial-write failure mode: each document is a separate
  cache-forever file, and the re-run's skip scan over ~20k paths is seconds.
- Segment 3 rebuilds the parquet from cache every run by design (E1
  behaviour, kept).
- Segments 3 and 4 may run in parallel with each other; both need segment 1
  only for the universe/DB, not for documents.

Before segment 1: full pytest green (MEASURED baseline today: **399
collected**; `F2_PROGRESS.md`'s "394" is the 2026-08-21 figure).
After segment 4: the F2 ingestion report + the §4.4 manual EX-99 read + the
§5.3 sector-blocker check, then S7's red-team pass.

---

## 8. Tests

**Everything offline.** No test may open a socket; the existing suites'
fixture style (synthetic dicts/DataFrames, monkeypatched clients) is the
pattern to extend.

### 8.1 Pinned tripwires that break, and what re-pins them

| test | breaks because | re-pinned to |
|---|---|---|
| `test_ingest_prices.py::test_load_universe_returns_all_25_tickers` | `load_universe()` is replaced by the CIK-keyed map | new `test_price_ticker_map_resolves_212_and_censors_32`, asserting the counts in §6.1 and the 25 E1 CIK↔ticker pairs (XOM via the override row) |
| `ingest_metadata.load_universe()`'s `20 <= len(df) <= 30` | deliberately removed (EXPANSION_PLAN §5) | `assert len(df) == 244`, plus new pins on 299 spells / 136 members per date / 11 dates |
| `test_ingest_fundamentals.py` — 7 tests parameterised over `CORE_NON_REVENUE_CONCEPTS`, plus `test_bank_exemption_downgrades_to_warn` (asserts `exempt_checks == BANK_EXEMPT_CONCEPTS`) and `test_known_midwindow_migration_is_warn_not_fatal` | those constants are deleted (§5.2) | rewritten against `CONCEPT_FAMILIES` + the classifier's five states; the bank and migration cases become **classifier acceptance tests** (below) rather than exemption tests |
| `test_diagnose.py::test_universe_csv_tickers_match_features_parquet_tickers` (`assert len(universe_df) == 25`) | E1-scoped | **left alone** — it guards E1's frozen artifacts, which E2 does not rebuild. Note it in the S2 report so a future reader does not "fix" it |

Nothing is deleted to make a suite pass. Every removed assertion is replaced
by a stricter one derived from the ratified table.

### 8.2 New tests per stage

**S2 — membership + windows + validation**
- `hybrid136_checksums.json` mismatch raises (tamper a temp copy).
- `load_universe()` returns 244 rows / 299 spells / 136 per date / 11 dates.
- `coverage_start` = `member_from − 730 d` clipped at `CORPUS_WINDOW_START`;
  `coverage_end` = `member_to + 400 d` clipped, or the window end for a
  current member.
- A synthetic late-IPO member (first filing after `CORPUS_WINDOW_START`,
  `member_from` 2024) produces **no** `history_reaches_cutoff` FATAL.
- A synthetic delisted member (last 10-Q 2019, `member_to` 2019-07-01)
  produces `member_stopped_filing` INFO and **no** FATAL; the same shape
  with `member_to == ''` produces a FATAL.
- Gap thresholds: 200-day gap → WARN not FATAL; 350-day gap → FATAL.
- `plausible_filing_counts` at 3.4/yr → FATAL, 3.6/yr → WARN, 4.1/yr → clean.
- Exceptions file: a `(cik, check)` exception downgrades **only** that pair
  and leaves the same check FATAL for a different CIK; an exception whose
  `evidence_filed >= effective_from` is **rejected at load**; a never-firing
  exception is reported as dead.
- Regression: validation problems are persisted on a run with **no**
  exceptions file (the §3.3 bug).

**S3 — metadata + documents**
- Enumeration respects per-company `[coverage_start, coverage_end]`.
- `distress_events` extraction from a synthetic submissions dict covering
  each of the 7 forms + item 1.03, and **not** firing on an ordinary 8-K.
- `earnings_doc_unresolved` accounting: 1 failure in 200 → WARN only;
  3 in 200 → FATAL (the >1% rule).
- `--stage documents` requests each expected relative path exactly once and
  **zero** times for an already-cached path (monkeypatched client).
- `parse_index_html_documents` on a saved 2016-era index fixture (CAT's,
  captured by the S1 probe) yields 6 rows and a high-confidence EX-99.1.

**S4 — fundamentals**
- One synthetic company per classifier state → the right state and severity.
- **Acceptance tests reproducing the deleted hand-maps** (this is the proof
  the classifier supersedes them): JPM/BAC/GS `cash` → `MIGRATION`/`SINGLE`
  on `CashAndDueFromBanks`, not `ABSENT`; MA/OXY `net_income` → `MIGRATION`
  to `ProfitLoss`; SLB `operating_income` → `MIGRATION` to `ProfitLoss`;
  CVX `cash` → `MIGRATION` to the restricted-cash tag. Run against small
  fixtures sliced from the cached companyfacts, not live.
- DEF 14A rows are excluded from the classifier's coverage counts (the MA
  trap (c) case).
- Sector aggregation: a synthetic sector with 21% UNRESOLVED in one family
  emits a BLOCKER; 19% does not.
- An UNRESOLVED pair never yields a resolved tag from any code path.

**S5 — prices**
- The ticker rule on synthetic submissions: preferreds-only → censored;
  `BRK-B`/`BRK-A` → `BRK-B`; a bulk-map contradiction → censored; a bulk-map
  **absence** → still resolved.
- The APC/EMC trap directly: a dead member whose former symbol maps to a
  different CIK is never fetched.
- The override file resolves 34088 → `XOM` and **only** 34088; a second
  undocumented row fails the file's own load-time validation.
- `missing_entirely` is not FATAL for a censored CIK, and the censored count
  appears in the report.
- Yahoo `meta.symbol` / `instrumentType` mismatch → WARN.

---

## 9. Decisions

### 9.1 Build-level rulings for the main session to ratify

1. **`F2_PROGRESS.md` §5 proposal 1 — full-window ingestion for every
   member CIK, no spell clipping: CONFIRM**, with the binding condition in
   §4.2 (the F2 report must count filings outside every membership spell,
   and F5 joins on `universe_membership`).
2. **`F2_PROGRESS.md` §5 proposal 2 — fixed generous window: CONFIRM with
   one amendment.** Document/metadata floor **2015-07-01**, not
   2016-01-01 (12 months before the first reconstitution date, so
   trailing-four-quarter features are complete at first membership;
   MEASURED cost +5.0% filings). Fixed end **2026-08-31**.
   Fundamentals/prices remain full available history, as E1.
3. **Canonical universe = `hybrid136.parquet` read in place**, guarded by a
   new `hybrid136_checksums.json`; `data/universe.csv` frozen; the 20–30
   size bound replaced by an exact `== 244` pin.
4. **E2 writes a new `data/filings_metadata_e2.db`**; E1's DB is frozen.
5. **`--allow-incomplete-universe` is deleted**, replaced by the evidenced
   per-`(cik, check)` `data/f2/validation_exceptions.csv`, expected empty.
6. **Concept families + automated classifier replace the three hand-curated
   maps**, which are deleted from code and preserved in the S4 report; the
   classifier must reproduce every case they encoded (§8.2).
7. **Price ticker resolution is CIK-verified from `submissions.json` only**,
   with exactly one evidenced successor override (34088 → `XOM`) and
   CIK 29915 deliberately censored.
8. **Yahoo becomes the default price source** (`--price-source yahoo`),
   Stooq retained as a one-flag path. *Flagged for owner visibility, not a
   gate* — the 2026-08-18 target ratification named Stooq by example, and
   Stooq has been bot-gated site-wide since 2026-08-18.
9. **Distress events (Form 25 / Form 15 / 8-K item 1.03) are ingested in
   S3** at zero network cost, discharging EXPANSION_PLAN §2c's mandatory
   mitigation.
10. **Documents become their own S6 segment** via
    `ingest_metadata.py --stage documents`, so F3's `extract.py` runs at
    0 GETs.

### 9.2 Items that genuinely need the OWNER

**None.** Every decision above is a build-level implementation choice inside
an already-ratified design. The three things that would need the owner —
the benchmark definition, the fold structure, and the label-quality bar —
are gates G3 and G2 and are untouched by F2.

Two items are flagged for owner **visibility** in the F2 report (neither
blocks S6):

- The price-source default change (§9.1 item 8), because the ratification
  named Stooq by example.
- The final censoring pair, **31 member CIKs with no price series at all
  (27 core / 4 extension)** — the number that must accompany every E2
  result, and slightly different from F1's headline 29 for two documented
  reasons (§6.3).

---

## 10. Explicitly out of F2's scope

- Anything owner-gated: benchmark (G3), fold structure (G3), label quality
  (G2).
- `extract.py`'s `MIN_SECTION_WORDS` / `MDA_STUB_WORD_CEILING`
  recalibration and new per-filer TOC dialects — F3, on the new
  distribution.
- Chunking, `chunk_id` regeneration, occurrence maps, labelling — F4.
- `features.py` / `backtest.py` constants, LOCO budgeting, caveat-constant
  regeneration — F5.
- Any edit to E1's frozen artifacts (`data/labels.parquet`, the finetune
  split, the spot-check record, `data/universe.csv`,
  `data/filings_metadata.db`) or to the `continuity5`/`broad8` option
  record.

---

## 11. AMENDMENTS (appended — the sections above are S1's text, unrewritten)

Each entry is dated, names who ruled it, and states exactly which sentence
above it supersedes. Nothing above this line was edited; where an amendment
and the original disagree, the amendment wins.

### 2026-08-24 — Enumeration window: the SHARED corpus window, not per-company coverage windows

**Ruled by the main session** (F2_PROGRESS.md §5, dated entry) on S3's
measured finding. **Supersedes:** §4.1's prose sentence
`coverage_start <= filing_date <= CORPUS_WINDOW_END` and its
`get_effective_recent(cik, coverage_start(cik))` call shape, and the §8.2 S3
test line "Enumeration respects per-company `[coverage_start, coverage_end]`".

**The rule:** the ingestion loop enumerates every member CIK over the shared
`[CORPUS_WINDOW_START, CORPUS_WINDOW_END]` = `[2015-07-01, 2026-08-31]`, and
passes `CORPUS_WINDOW_START` as the `filings.files[]` pagination cutoff.
Per-company `coverage_start`/`coverage_end` continue to govern **§3.1
validation only**, unchanged, and are still written to `companies`.
In one line: **enumeration = shared window; validation = per-company windows.**

**Why** (the sections above already said this; only §4.1's prose and §8.2's
test line disagreed):

- §9.1 ruling 1 / §4.2 — "ingest the full E2 window for every CIK that is ever
  a member; do not clip fetches to membership spells".
- §2 names `CORPUS_WINDOW_START` the "documents/metadata **enumeration
  floor**".
- Every MEASURED count in §4.1 and §4.5, and §7's runbook budget, was computed
  on the shared window. S3 re-measured all three candidate readings offline
  against the real 244 members (cache-only, 0 GETs):

  | enumeration filter | 10-K | 10-Q | 8-K | total | earnings 8-K | 8-K item 1.03 |
  |---|---|---|---|---|---|---|
  | **shared window (ratified)** | 2,452 | 7,532 | 35,638 | **45,622** | **10,569** | **2** |
  | `[coverage_start, coverage_end]` | 1,883 | 5,830 | 27,936 | 35,649 | 8,242 | 0 |
  | `[coverage_start, CORPUS_WINDOW_END]` | 2,138 | 6,601 | 31,138 | 39,877 | 9,247 | 0 |

  Only the shared window reproduces §4.1's table.
- Decisive case: CIK 895126 (Expand Energy, ex-Chesapeake) first qualifies as
  a member at 2026-07-01, so its `coverage_start` is 2024-07-01 and its
  **2020-06-28 8-K item 1.03** — the corpus's only bankruptcy, which
  EXPANSION_PLAN §2c makes mandatory to ingest — falls outside its own
  coverage window. Clipping loses it silently.

§4.2's binding condition is unaffected and is now printed on every run
(MEASURED: 20,216 of 45,622 ingested filings fall outside every membership
spell of their own CIK). PIT safety is unaffected: ingestion breadth never
implies membership, and F5 joins on `universe_membership`.

### 2026-08-24 — Co-registrant filings: a side table, and a new binding downstream rule

**Ruled by the main session** (F2_PROGRESS.md §5, dated entry) on S3's
measured finding. **Adds to** §1.4's schema list; supersedes nothing.

**The finding (MEASURED, offline):** EDGAR lists co-registrants on a single
accession — a parent and its subsidiary file one 8-K together. `filings` is
keyed on `accession_number` (E1's schema, which §1.4 does not change), so when
BOTH filers are hybrid136 members the second one's `cik` attribution has
nowhere to go. **87 of 45,622 filings (0.19%)**, across exactly three pairs:
Dow Chemical (29915) / Dow Inc (1751788) **67**, Williams Companies (107263) /
Williams Partners (1483096) **16**, Exelon (1109357) / Constellation
(1868275) **4**. By form: 57 8-K, 23 10-Q, 7 10-K. E1's 25 unrelated mega-caps
never hit this.

**The ruling:** do **not** re-key `filings` on `(accession_number, cik)` — it
would ripple into `filing_documents`' parent key and F3's extraction grain for
0.19% of rows. Instead add

```sql
co_registrant_filings(accession_number, kept_cik, co_cik, form, filing_date)
PRIMARY KEY (accession_number, co_cik)
```

populated during metadata enumeration at **zero** network cost, one row per
dropped attribution (87 expected on the real universe), plus an index on
`co_cik`. The existing per-pair `co_registrant_filing` WARNs and the
stored-vs-enumerated run-summary line stay on top of it.

**Keeper rule (deterministic, pinned by test):** the `filings` row is kept
under the numerically **lowest** member CIK on the accession. Guaranteed by
construction — the ingestion loop iterates the universe CIK-ascending
(explicitly re-sorted, not relying on the caller) and the upsert never
rewrites `cik`.

**BINDING DOWNSTREAM RULE (restate in the F2 report and at F5):** absence from
`filings` alone is **never** evidence a company did not file. Any per-company
filing or coverage question consults `filings` ∪ `co_registrant_filings`, and
F5's accession → company attribution must yield **both** member CIKs for these
accessions.

### 2026-08-24 — AEP (CIK 4904): a second evidenced price-ticker override, and a wobble WARN

*Third amendment in this section (A3). The first two are S3's, above.*

**Ruled by the main session** (F2_PROGRESS.md §5, dated entry), on evidence
from a live 1-GET probe plus S5's own offline re-measurement.
**Supersedes:** §6.1's MEASURED table (212 / 32), §6.2's "It contains exactly
one row", §6.3's "212 resolved + 1 override", and the §8.1 row-1 re-pin name
`test_price_ticker_map_resolves_212_and_censors_32`.
**Does NOT change:** the §6.1 rule itself, the §6.2 ruling that CIK 29915 stays
censored, the §6.3 pre-registered census delta, or the final censoring pair.

**What happened.** During S6 segment 1's TTL refresh, EDGAR's
`submissions.json` for CIK 4904 (AMERICAN ELECTRIC POWER CO INC) dropped to
empty `tickers[]`/`exchanges[]`. The submissions-only rule therefore censored
it, and S5's two count tests failed against the refreshed cache — the tripwire
doing exactly its job. A live main-session probe confirmed EDGAR has not
self-healed; SEC's own `company_tickers.json` maps **AEP → 4904**, and AEP is a
listed, actively-filing **current** member.

**The ruling: a second evidenced override row, 4904 → `AEP`.** Note the
direction of the bulk-map evidence — the symbol points at **our** CIK
(agreement), which is the safe case. The APC trap is the opposite: the symbol
points at a **different** CIK, and that case is still censored, never
overridden. Censoring a live listed mega-cap over an upstream data wobble would
be the larger error, and the evidenced override file is the designed exception
path for exactly this.

> **CORRECTED BY A10 (S7 finding B3).** The sentence above — "that case is
> still censored, never overridden" — is **false about the XOM row that was
> already on file**: `XOM` bulk-maps to CIK 2115436 while the member is 34088.
> Bulk-symbol-maps-elsewhere is the trap **signature**, not an automatic
> disqualifier; overriding it now requires a ratified `successor_reorg` marker,
> a series-continuity check, and a standing per-run WARN. See A10. Everything
> else in this amendment (the AEP ruling and its counts) stands.

**New check (`submissions_ticker_missing_but_bulk_has`, WARN, adds to §6.4):**
every member whose submissions carry no admissible ticker while the bulk map
maps some symbol to that same CIK is named on every run — including one already
covered by an override, so the wobble stays visible rather than disappearing
behind the fix. Bulk symbols are **never** auto-adopted; the only remedy is a
hand-added evidenced row. The WARN distinguishes an admissible bulk symbol
(AEP-shaped) from bulk symbols that are all non-common (EIDP-shaped, where
censoring is correct).

**MEASURED 2026-08-24 on the post-refresh cache (cache-only, 0 GETs):**

| | pre-refresh (S5, 12:22) | post-refresh (amended) |
|---|---|---|
| resolved by the rule alone | 212 | **211** |
| censored by the rule alone | 32 | **33** |
| evidenced overrides applied | 1 (XOM) | **2 (XOM, AEP)** |
| **fetchable** | 213 | **213 — unchanged** |
| **censored** | 31 (27 core / 4 extension) | **31 (27 core / 4 extension) — unchanged** |
| census delta vs F1 | −{34088}, +{30554} | **identical** |

Of the 33 rule-censored CIKs, **exactly two are wobble-shaped** (a bulk symbol
maps to their own CIK): **4904 (AEP** — admissible symbol, override-covered)
and **30554 (EIDP** — only `CTA-PA`/`CTA-PB`, both non-common, so censoring is
correct and no override is added). Both are live filers; a third of this shape
would be a finding for the main session, not a self-service override.

Also re-measured, and worth recording because the two SEC files swapped roles:
pre-refresh, AEP was *absent from the bulk map* and present in submissions;
post-refresh it is present in the bulk map and absent from submissions. Only
**EA (CIK 712515)** is now resolved-but-absent-from-the-bulk-map, so §6.1's
"absence never censors" asymmetry is still load-bearing for one live member.

**Re-pins:** `EXPECTED_RESOLVED = 211`, `EXPECTED_OVERRIDES_APPLIED = 2`,
`RATIFIED_OVERRIDE_CIKS = {34088, 4904}` in `ingest_prices.py`;
`test_price_ticker_map_resolves_211_and_censors_33` replaces the §8.1 row-1
test name. `EXPECTED_FETCHABLE`, `EXPECTED_CENSORED` and
`EXPECTED_CENSORED_BY_STRATUM` are untouched.

### 2026-08-24 — EA (CIK 712515): `resolved_no_coverage`, and TWO censoring numbers reported separately

*Fourth amendment in this section (A4).*

**Ruled by the main session** (F2_PROGRESS.md §5, dated entry) on segment 4's
real run — which otherwise hit every S5 pin exactly (213 fetched / 31
unfetchable, reconciliation clean, 1,960,738 rows).
**Supersedes:** §6.3's single "213 tickers fetched, 31 member CIKs censored"
framing and §9.2's "the final censoring pair" bullet **as the number an E2
*result* quotes** — the fetch-side numbers themselves are unchanged and still
correct as fetch-side facts.
**Adds to:** §6.4's validation list and §6.3's output columns.

**What segment 4 caught.** `missing_in_window` fired on **EA (CIK 712515**,
core/tech, member 2017-07 → 2021-07): Yahoo returned **6 rows**, all
2026-07-17 → 2026-08-10, flatlined at the ~$209.70 take-private price with
volume 0, `meta.firstTradeDate` reset to 2026-07-17. It *is* Electronic Arts
(`longName` confirms) — Yahoo purged the delisted name's history after the
take-private. So a member can be **fetched and still have nothing usable**:
EXPANSION_PLAN §2c's outcome-censoring residual, materialised for a **core**
member. Verified: **0 of EA's 6 rows** fall inside its
`[2015-07-02, 2022-08-05]` coverage window.

**The rule.** `ingest_prices.py` gains a fourth status,
**`resolved_no_coverage`**: a member that was resolved and fetched but whose
series has **zero rows inside its own coverage window**. It **keeps its fetch
record** (its rows stay in `prices_e2.parquet`, it stays in the FETCH pair) and
**joins the operative censoring accounting**. Classification happens after the
fetch (`apply_no_coverage_status()`), so the map is written twice — once before
the fetch, once after, with the operative statuses.

**Two numbers, reported separately, everywhere, forever:**

| | pair | value | what it answers |
|---|---|---|---|
| **FETCH** | fetched / unfetchable | **213 / 31** (27 core / 4 extension) | did a CIK-verified symbol exist to ask for? — an *ingestion* fact |
| **OPERATIVE** | usable / **no usable prices** | 212 / **32** (**28 core** / 4 extension) | does the member have prices inside the window it was a member? — **the pair every E2 result quotes** |

32 = 31 unfetchable + 1 fetched-but-zero-coverage. Every printed line names
which pair it is; `price_ticker_map.csv` gains `fetched` and
`has_usable_prices` columns (so the two populations can be selected without
inferring either from the other), giving
`cik, name, stratum, chosen_ticker, all_candidates, status, fetched,
has_usable_prices, reason`.

**§6.3 reconciliation addendum (dated, printed on every run):** the census diff
is **FETCH-side** — it compares ticker resolvability, the question F1's census
asked, and is silent on whether a fetched series covers its window. It stays
clean at −{34088}/+{30554}; EA is a *new axis*, not a census delta.

**MEASURED, read-only, from `data/prices_e2.parquet` (1,960,738 rows / 213
CIKs) — EA is the sole instance:** the next smallest in-window row count among
the other 212 fetched members is **539**. A second such member is a FATAL
`unexpected_no_coverage_member` naming it, and EA *recovering* its history is a
FATAL `expected_no_coverage_member_missing` — the pin is two-sided.

**§2c cross-reference, in code:** every `resolved_no_coverage` member is
cross-referenced (read-only, `--db`) against S3's `distress_events`. EA's
delisting is fully covered: **`25-NSE` filed 2026-08-04**
(`0001354457-26-000757`, `delisting_form_25_nse_exchange_filed`) and **`15-12G`
filed 2026-08-14** (`0001140361-26-032929`, `deregistration_form_15`), both
cited in the run report. A no-coverage member with *no* distress events would
WARN — the price gap would then have no EDGAR-side explanation.

**New pins:** `EXPECTED_FETCHED = 213`, `EXPECTED_UNFETCHABLE = 31`,
`EXPECTED_NO_USABLE_PRICES = 32`,
`EXPECTED_NO_USABLE_BY_STRATUM = {core: 28, extension: 4}`,
`EXPECTED_NO_COVERAGE_CIKS = {712515}`. `EXPECTED_RESOLVED` (211),
`EXPECTED_OVERRIDES_APPLIED` (2) and the censored pins are unchanged and now
count the immutable `fetch_status`, so they survive the post-fetch
reclassification.

### 2026-08-24 — AMENDMENT A5: the 244-scale classifier calibration (S4 fourth pass)

**Ruled by the main session** (`F2_PROGRESS.md` §5, "244-scale classifier
calibration") after reading segment 3's real run: 3,416 pairs, 693 UNRESOLVED,
18 surviving BLOCKERs. **Supersedes** §5.3's window-based denominator and the
`("financials", "operating_income")` entry added by A2.2; **extends** §5.2's
family table. Everything else in §5, A1 and A2 stands. Evidence:
`data/f2/status/S4_fundamentals.md` §11 and
`data/f2/concept_resolution_prediction_244.csv`.

**A5.1 Denominator = the company's own filed span, not its window.**
Reportable quarters for every `(cik, family)` are the quarters between the
first and last quarter in which that COMPANY reported any in-window
operating-form fundamentals — the same filed-span rule S2 already applied to
`plausible_filing_counts`. The span is trimmed only at the ends, so interior
holes still count. Evidence: AZEK (CIK 1782754, IPO 2020, acquired 2025) is
fully covered for its actual life and was scored 11/16 = 69% PARTIAL on **all
14 families**, because the window contains quarters that predate its
existence and postdate its death. The STALE-tail check (A1.3) is unchanged
and stays anchored on the company's own last data quarter — the two rules are
orthogonal, and MEASURED they stay so: Walgreens (CIK 1618921) `eps_diluted`
is still `PARTIAL`/STALE afterwards (13/16 = 81% coverage, last 2018Q3 vs its
own last data quarter 2019Q2).

**A5.2 Partnership tags join three families — measured, not assumed.**
Partnership issuers represent the same logical series under per-unit /
partners-capital tags. Added, corporate tags first, with MEASURED user counts
over the 244 cached companyfacts:

| family | tag added | users |
|---|---|---|
| `equity` | `PartnersCapital` | **12** |
| `equity` | `PartnersCapitalIncludingPortionAttributableToNoncontrollingInterest` | **8** |
| `eps_diluted` | `NetIncomeLossNetOfTaxPerOutstandingLimitedPartnershipUnitDiluted` | **8** |

Deliberately **not** added, each with its measurement:
`LimitedPartnersCapitalAccount` (7 users) and `GeneralPartnersCapitalAccount`
(4) are capital COMPONENTS, like `MinorityInterest`, and add zero coverage —
every member reporting them also reports a partners-capital total;
`NetIncomeLossPerOutstandingLimitedPartnershipUnitBasicNetOfTax` (8) and
`IncomeLossFromContinuingOperations…PerOutstandingLimitedPartnershipUnit…`
(4) are basic / continuing-ops measures that add zero coverage over the
diluted tag; the weighted-average unit tags are period averages, not
point-in-time counts. **`shares_outstanding` gets NO partnership tag**: of the
30 members unresolved on it, **zero** report any unit-count tag in-window —
the partnerships use the ordinary dei cover-page fact, and all 30 are the
multi-class dimensioned-facts gap (A5.4). **`pretax_income` gets none
either**: partnerships are pass-through entities with no income-tax subtotal,
so there is no partnership variant to add and ABSENT is the economically
correct answer. Total ingested tags 27 → **30**.

**A5.3 Two exemption-ledger additions, and one supersession.**
`("*", "liabilities")` — ABSENT-dominated for 21–56% of members in 7 of 8
sectors; the F5 note that total liabilities is derivable as
`liabilities_and_equity − equity` is attached to the reason string, so it
travels into the run report. `("*", "operating_income")` — E1's trap (a)
generalises past banks (MEASURED: energy 31%, materials_realestate 29%,
healthcare 25%, industrials 21%, financials 62%); presenting a GAAP
operating-income line is a sector-correlated reporting style, so F5 must treat
`operating_income` as a **non-universal** feature with `pretax_income` as the
resolving fallback. This entry **supersedes and replaces**
`("financials", "operating_income")`, which is deleted rather than kept beside
its own generalisation. Ledger: **4 entries**, all `("*", …)`. Per-pair FATAL
rows are untouched for both families, as always.

**A5.4 Two things stay unfixed and listed.** The 8 `OVERLAP` cases and the
multi-class `shares_outstanding` failures are enumerated individually in the
S4 report and left firing per-pair; the dimensioned-facts gap (companyfacts
omits per-share-class facts) is parked, not papered over.

**MEASURED effect** (offline replay of the classifier over the 244 cached
companyfacts + the three new tags, 0 GETs, no DB or parquet written):
UNRESOLVED **693 → 497 of 3,416**; PARTIAL **332 → 147**; ABSENT 353 → 342;
SINGLE 2,192 → 2,355; DOMINANT 456 → 489; MIGRATION 75 and OVERLAP 8
unchanged. **196 pairs improved, 0 regressed.** Surviving BLOCKERs **18 → 0**,
with all four exemptions firing and none dead (27 cells suppressed). The
nearest cells to the line are `tech`/`financials` `shares_outstanding` at 19%
and `consumer` at 18% — below threshold, still loud per pair.

### 2026-08-24 — AMENDMENT A6: the EX-99 manual-read fix package (S6 §4.4 read)

**Ruled by the main session** (F2_PROGRESS.md §5, dated entry "the EX-99
manual-read fix package") on the mandatory §4.4 manual read
(`data/f2/status/S6_ex99_manual_read.md`: 17 CORRECT / 2 WRONG / 1 AMBIGUOUS
over the worst-20 CIKs). **Adds to** §4.4; supersedes no ratified rule. All
counts below are MEASURED offline over the cached corpus, 0 GETs.

**The finding that drove it:** the Prologis (CIK 1045609) selection error is
*systematic*, and **37 of its wrong picks were HIGH confidence** — falsifying
the implicit assumption that the confidence label tracks correctness. Anything
downstream that reads "high confidence" as "no need to look" is wrong.

**Six changes, all in `ingest_metadata.py`:**

1. **P2 — one named per-filer handler** (`_prologis_earnings_document`,
   registered in `PER_FILER_EARNINGS_HANDLERS`). For CIK 1045609 from
   **2016-07-19**, take EX-99.2, not EX-99.1. Deliberately NOT a general
   "prefer the exhibit that reads like a release" scorer, which would re-open
   all ~10,500 currently-correct picks.
   **CONTENT-CONFIRMED across all 45 of the filer's cached earnings 8-Ks**
   before implementing: through 2016-04-19 (4 filings) the EX-99.1 is
   self-titled "Earnings Release **and** Supplemental Information" and contains
   the release; from 2016-07-19 (41 filings, continuously to 2026-07-16) the
   title drops "Earnings Release and" and none contains release narrative.
   The two 2018 filings the read reported as carrying release language are
   Supplemental documents whose guidance footnote merely *cites* "the Press
   Release dated January 17, 2018" — so the corrected blast radius is **41,
   not 39**. The rival EX-99.2 bytes are not cached and were not fetched;
   the confirmation is by complement plus the filer's own label
   (`0001564590-19-036903`'s EX-99.2 description is literally "PRESS RELEASE,
   DATED OCTOBER 15, 2019.").
2. **A new evidenced override file**, `data/f2/earnings_doc_overrides.csv`
   (`accession_number, action, document, reason, evidence, added`), loaded and
   validated exactly like `price_ticker_overrides.csv`: a row naming an
   accession outside `RATIFIED_EARNINGS_DOC_OVERRIDES` is REFUSED at load, every
   row is printed fired-or-DEAD, and a stale `select_document` row RAISES rather
   than resolving to nothing. Two actions: `select_document` and `exclude`.
   **Exactly two rows** — NVIDIA `0001045810-19-000168` (release typed
   `EX-95.1` by filer typo) and AT&T `0000732717-19-000048` (no release in the
   filing; the real one is the same-day sibling accession). An `exclude` is an
   **evidenced exclusion, not a failure**: INFO (`earnings_doc_excluded_by_
   override`), counted in the audit CSV under `section_type=
   EXCLUDED_BY_OVERRIDE`, kept OUT of the `earnings_doc_unresolved` rate and
   out of the sector-coverage denominator, and the DB columns stay NULL.
3. **P3 — `press_release_typed_outside_ex99()`, a loud WARN, never an
   auto-pick.** An index row DESCRIBED as a press release whose TYPE is outside
   the EX-99 family. Trusting descriptions would make every filer's prose part
   of the selection policy; the override file is the resolution path.
   MEASURED: **3 hits** over all 10,569 earnings 8-Ks (raw 18, of which 15 are
   news-release *header images*, excluded as non-document rows).
4. **P1 — `_exhibit_number_from_description()`, confidence only.** When bare
   `EX-99` rows carry the sub-number in the description column, and the row
   described "EX-99.1" is the one lowest-seq **already** chose, relabel it
   high. MEASURED in isolation: **11 of the 32 low-confidence selections
   upgraded, 0 pick changes.**
5. **P5 — `ex99_thin_exhibit` WARN** for a selected document with <1,500
   characters of extractable text, distinguishing IMAGE-ONLY (an `<img>`
   wrapper) from EMPTY AT SOURCE. MEASURED: **50 selections, 12 of them under
   100 characters.** These SHOULD fail F3's `MIN_SECTION_WORDS` floor; naming
   them here means a future recalibration has to argue past them.
6. **P6 — the Prologis detector** (`screen_selected_documents()` +
   `ex99_release_language_missing` WARN). A per-CIK screen of every **cached**
   selected document for release language; a CIK whose high/medium-confidence
   picks *mostly* (>50%, minimum 4 measured) lack it is flagged, into both the
   audit CSV (three new columns) and a WARN. This is the check that would have
   caught Prologis without a manual read. Selections with no cached document
   are counted **unmeasured, never clean**.

**Ruled OUT and NOT implemented:** P4's new `EX99_FINANCIAL_SCHEDULES`
`section_type` (a section-type taxonomy change touches F4 labeling
applicability — EXPANSION_PLAN §5's "APPLICABILITY extended only
deliberately"; parked to the F3 handoff), and any threshold loosening.

**Net effect, MEASURED by replaying the policy over every cached index:**
**43 pick changes, and exactly three filers move** — Prologis 41, NVIDIA 1,
AT&T 1 (to excluded). Confidence: low 32 → 19, high 10,521 → 10,533, medium 16
unchanged. Pinned by
`test_fix_package_changes_exactly_the_intended_picks_on_the_real_corpus`.

**Two NEW findings the P3 WARN surfaced, reported for ratification, NOT
auto-fixed** (they are not in the override file):

- **ONEOK `0001039684-15-000073`** (2015-11-03): the release is typed
  `EX-95.1` — the NVIDIA typo again — and because no EX-99 row exists at all
  the policy fell back to `8K_BODY` and selected the **8-K cover page, 3,179
  characters of SEC boilerplate**. The read binned this CIK benign.
- **Micron `0000723125-19-000172`** (2019-12-18): the release is typed
  `EX-99..1` (double dot), same outcome — an 8-K cover page of 3,499
  characters. This filing was not in the read's 36-filing screen at all.

Both were invisible to the low-confidence trigger (they are `8K_BODY`/high) and
to the §4.4 worklist ordering. NVIDIA's blast radius is therefore **n=1 for
that filer** but the *typo class* is n≥3 corpus-wide.

**One more P6 flag, benign and reported rather than suppressed:** **Netflix
(CIK 1065280), 25 of 47** high-confidence selections lack release language.
Read directly: every one is the correctly-picked EX-99.1 "LETTER TO
SHAREHOLDERS" (25k–37k characters, opening "Fellow shareholders,"). The picks
are right; Netflix simply does not write press-release prose. The threshold was
**not** loosened to hide it — that is exactly the threshold-loosening the
ruling forbids.

### 2026-08-24 — AMENDMENT A7: ONEOK + Micron join the earnings-doc override file

**Ruled by the main session** (F2_PROGRESS.md §5, dated entry "ONEOK + Micron
join the earnings-doc override file"), on the two new defects **A6's own P3
WARN surfaced within minutes of existing**. Appended rather than edited into
A6, so the record shows what was known when: A6 reported these two as findings
for ratification; this amendment is the ratification.

**Supersedes three figures in A6** (nothing else): "**Exactly two rows**" in
item 2 → **four rows**; "**43 pick changes, and exactly three filers move**"
→ **45 pick changes across five filers**; and A6's closing "reported for
ratification, NOT auto-fixed" for ONEOK and Micron → both are now evidenced
override rows.

**Two new `select_document` rows**, same mechanism, same evidence standard as
the NVIDIA row (confirmation by the index row's own press-release description
plus the P3 WARN that surfaced it; the documents themselves are
content-verified by the extraction-qa re-verification pass once segment 2
caches them):

| accession | filer | typed | the real release | what the policy did instead |
|---|---|---|---|---|
| `0001039684-15-000073` | ONEOK, 2015-11-03 | `EX-95.1` | `okeq32015earningsreleasenr.htm` | fell through to `8K_BODY` and took the **8-K cover page**, 3,179 chars of SEC boilerplate, at HIGH confidence |
| `0000723125-19-000172` | Micron, 2019-12-18 | `EX-99..1` (double dot) | `a2020q1exhibit991-pres.htm` | same fallback, **3,499-char cover page**, HIGH confidence |

Both were invisible to the low-confidence trigger and to the §4.4 worklist
precisely because they are `8K_BODY`/high. The **typo class is n=3
corpus-wide** (NVIDIA, ONEOK, Micron); `press_release_typed_outside_ex99()`
stays as the permanent tripwire for future instances.

**The type family was NOT widened.** `EX-95.1` and `EX-99..1` remain outside
`_EX99_FAMILY_RE` and outside `_canonical_exhibit_type()`'s normalisation —
pinned by `test_double_dot_type_is_still_outside_the_ex99_family`. Widening it
is how one filer's typo becomes a silent mis-pick generator across 10,569
filings; an evidenced per-accession row is the deliberately non-scaling
resolution.

**Re-measured net effect** (replay over every cached index, 0 GETs):
**45 pick changes** — Prologis **41**, NVIDIA **1**, ONEOK **1**, Micron **1**,
AT&T **1** (to excluded) — and **no other filer moves**. Confidence is
unchanged from A6's measurement (low 32 → 19, high 10,521 → 10,533, medium 16,
excluded 1), because both new rows replace a HIGH-confidence pick with a
HIGH-confidence one. **P3 WARNs remaining on a re-run: 0** — every hit it found
now carries an evidenced resolution, which is the tripwire working as designed,
not the tripwire being disarmed.

**Also accepted into the record** (no code change): A6's Prologis correction
of **41 of 45, not the read's 39**, and the P6 Netflix flag (25/47, 53%) as
**REPORTED-BENIGN** — correctly-picked "LETTER TO SHAREHOLDERS" exhibits, with
the threshold deliberately NOT moved to hide it.

### 2026-08-24 — AMENDMENT A8: the 2016-04-19 boundary and the P6 title-region scope fix

**Ruled by the main session** (F2_PROGRESS.md §5, newest entry) on the content
re-verification of the fix package (`S6_ex99_manual_read.md` §V: overall PASS,
one narrow n=1 residual). **Supersedes two figures in A6/A7** — Prologis blast
radius **42 of 45, not 41**, and `PROLOGIS_SUPPLEMENTAL_SPLIT` **2016-04-19,
not 2016-07-19** — and narrows A6's P6 marker scope. Nothing else changes; the
41 corrections A7 recorded are re-verified good.

**1. The split date moves by exactly one filing.** `0001564590-16-016339`
(2016-04-19) carries the same "Prologis Earnings Release and Supplemental
Information" title as the three genuinely-combined pre-split filings, but the
title is a **template leftover**: re-verified against raw bytes, its sole
release-language hit across **113,158 characters** is that title (offset 64) —
zero "Prologis Reports", "today reported", "FOR IMMEDIATE RELEASE", "press
release", "conference call", "webcast", and a ToC running straight from
Highlights to Company Profile. Its `pld-ex992_7.htm` is the release. The
handler docstring previously claimed all four pre-split filings "genuinely
contain the release"; that was true of **three** and is now corrected to name
the exception.

**Why both guards missed it, recorded because both are standing
infrastructure:** the handler's content-confirmation and P6 *both keyed on the
document's own title string*. Neither read its body. A self-description is not
evidence about content.

**2. P6 scope fix — markers count only outside the title region.** New
`TITLE_REGION_CHARS = 200`; `screen_selected_document()` looks for release
language only beyond it. **This is a scope change, not a threshold move**
(`P6_MISSING_RELEASE_SHARE` 0.5 and `P6_MIN_MEASURED_SELECTIONS` 4 are
untouched).

An offset rule was measured and **rejected as impossible**: first-marker
offsets are **27–89 for genuine releases and 64 for the false positive**, so
they interleave and no cut separates them. The working discriminator is
whether any marker survives the title region:

| class | hits beyond char 200 |
|---|---:|
| the 2016-04-19 false positive | **0** (flags — correct) |
| 41 cached Prologis EX-99.2 releases | **≥3** |
| NVIDIA / ONEOK / Micron override releases | 10 / 11 / 8 |
| 3 genuine pre-split combined EX-99.1 docs | 11 / 9 / **1** |

200 carries that margin explicitly, and the **ceiling is recorded**: at 400 the
weakest genuine document (2016-01-26) falls to 0 and would false-flag, so the
boundary must stay ≤ ~300.

**MEASURED consequences** (offline replay, 0 GETs):

- **Pick delta vs the stored corpus: exactly 1** — the 2016-04-19 filing,
  `pld-ex991_6.htm` → `pld-ex992_7.htm`. Nothing else moves.
- **P6 flags exactly one CIK, Netflix (25/47, 53%)** — unchanged by the scope
  fix in either direction, and still REPORTED-BENIGN (shareholder letters,
  correct picks). Prologis is clean either way: 1/45 on stored selections, 0/44
  on post-fix ones.
- Post-fix Prologis has **1 uncached** selection — the newly-picked
  `pld-ex992_7.htm` — counted UNMEASURED, never clean. That is the **1-GET
  segment-2 delta**.
- `test_stored_selections_match_current_policy_exactly` correctly reports
  `{1045609: 1}` drift until segment 1 regenerates; the regeneration re-arms it
  with no edit.

### 2026-08-24 — AMENDMENT A10: the successor-reorg guard (S7 finding B3), and two LOW notes

**Ruled by the main session** on S7's red-team finding **B3 (HIGH)**; S5 owner.
**Supersedes:** the safety property asserted in A3's ruling paragraph, in
`data/f2/price_ticker_overrides.csv`'s comment block, and in
`data/F2_INGESTION_REPORT.md` (≈lines 461-464, docs owner) — all three said a
symbol that bulk-maps to a **different** CIK "is still censored, never
overridden", while the XOM row on file was exactly that case.
**Does not change:** any count. Both pairs are untouched — FETCH 213/31
(27 core / 4 extension), OPERATIVE 32 (28 core / 4 extension).

**The finding, re-derived.** `company_tickers.json` maps
`XOM → CIK 2115436 "ExxonMobil Holdings Corp"`; the member is **34088**, absent
from the bulk map. Structurally identical to `APC → 2080921` while Anadarko is
773910. Three defects, all real: the file's own comment denied it; no code
checked *why* a member censored before applying an override; and
`ticker_wobble_issues` skipped CIKs with no bulk symbols, so **XOM never
WARNed** while AEP — where the bulk map *agrees* with our CIK, the safe
direction — WARNed every run. Backwards.

**The honest rule, now enforced in code and stated in all three places:**

> bulk-symbol-maps-elsewhere is the trap **SIGNATURE**. An override over it
> requires (a) an explicit `successor_reorg=true` marker on the row, itself
> ratified in `RATIFIED_SUCCESSOR_REORG_CIKS`; (b) a **series-continuity
> check** against the fetched prices; (c) a **standing per-run WARN**. Absent
> any of the three, the member stays censored.

**What changed**

1. **New required column `successor_reorg`** in `price_ticker_overrides.csv`.
   `validate_overrides_against_bulk_map()` (called on every run from
   `resolve_universe_tickers()`, and from `load_ticker_overrides(bulk_map=…)`)
   **raises** on an unmarked override whose symbol maps elsewhere. The marker is
   refused for any CIK outside `RATIFIED_SUCCESSOR_REORG_CIKS = {34088}`, and a
   non-boolean value raises. XOM carries it; **AEP does not need it** (AEP
   bulk-maps to its own CIK), and a spurious marker on 4904 is refused.
2. **`override_symbol_bulk_maps_elsewhere` (WARN, every run)** — arm 2 of
   `ticker_wobble_issues`, keyed on the new `TickerResolution.chosen_bulk_cik`
   rather than on bulk symbols *for* the member, which is what made arm 1 skip
   34088. It names the member CIK, the bulk-map CIK, and quotes the row's own
   evidence. **MEASURED: XOM now WARNs on every run; AEP still WARNs via arm 1.**
3. **`successor_continuity_issues()`** — for every successor-reorg override:
   FATAL `successor_series_too_short` below `SUCCESSOR_MIN_SERIES_ROWS = 1250`
   bars (EA's purged stub is 6; the smallest genuine series here is 604), FATAL
   `successor_series_starts_late` if the first bar post-dates the member's
   coverage window by >45 d (the reassigned-symbol shape: ARKO starts 2020 while
   Anadarko was a member from 2016), FATAL `successor_series_missing` if nothing
   was fetched, else INFO `successor_series_continuous` **stating the measured
   numbers** so the report carries the corroboration instead of asserting it.
4. **The evidence field now cites the measurement.** Re-derived read-only from
   `data/prices_e2.parquet`: XOM = **14,282 rows, 1970-01-02 → 2026-08-24,
   largest gap 7 calendar days, zero gaps > 10 days**, ~2,520 rows per full
   decade, 252.2 rows/yr over 56.6 years — reproducing the red-team's figure
   exactly. The row also records what is **not** verified: there is no cached
   `submissions` document for CIK 2115436 in this repo, so the holdco
   relationship rests on the bulk map plus this continuity measurement, not on a
   primary filing. E1's prior `universe.csv` mapping is cited as corroboration
   only, never as evidence about the reorganisation.

**Two LOW notes recorded, no code (S7 B12 / B13):**

- **B12** — "absence never censors" is the residual APC surface. Exactly one
  member took that branch (EA, 712515), and it was caught by a *coverage*
  tripwire, not an identity one; a reassigned symbol with a long history would
  have passed `meta_symbol`, `instrumentType` and `starts_after_coverage_start`.
  The new continuity check closes this only for successor-reorg overrides — the
  general absent-from-bulk-map case is unchanged and stays a known surface.
- **B13** — the parquet has no per-CIK validity floor: DuPont (1666700) carries
  `DD` back to 1972-06-01, history belonging to the old E. I. du Pont (CIK
  30554, itself censored here). Out of window today (coverage_start 2018-07-02)
  so no live defect, but any downstream query that does not clip to the coverage
  window can read another company's history. **Binding downstream note: always
  clip price reads to `[coverage_start, coverage_end]`.**

### 2026-08-24 — AMENDMENT A9: the conditional 8K_BODY fallback (S7 red-team B1/B2/B6/B7/B17)

**Ruled by the main session** (F2_PROGRESS.md §5, S7 triage entry) on red-team
findings B1 (HIGH, corpus content), B2, B6, B7 and B17. **Adds to** §4.4;
supersedes no ratified rule. All counts MEASURED offline, 0 GETs.

**B1 — the defect.** The `8K_BODY` fallback returned `("8K_BODY", "high")`
**unconditionally** whenever nothing matched `^EX-99(\.\d+)?$`, never checking
whether the index still held an unselected candidate. MEASURED: **20 of the
225** `8K_BODY`/high selections had one, and **15 were release-shaped**. In
those filings the stored "earnings document" is the SEC Form 8-K **cover
page**, whose own Item 2.02 text says the release is attached as Exhibit 99.1
— verified in the stored bytes (Aon 2,260 chars; Illumina 2,827; HPE 4,231).

**Why every guard missed it, recorded because all of them are standing
infrastructure:** P5's floor is 1,500 chars and these are 2,260–4,231; P3 needs
a release-shaped DESCRIPTION and these say "EXHIBIT 99..1"/"EXHIBIT 1"; P6 is a
per-CIK majority; the confidence was `high` by construction; and **the 1%
`earnings_doc_unresolved` ceiling counted a cover-page pick as RESOLVED**, so
"0.00% unresolved" was structurally blind to the class.

**The fix — a conditional fallback, NOT family-regex widening** (which stays
prohibited; `_EX99_FAMILY_RE` and `_canonical_exhibit_type()` are untouched and
a malformed type still never wins the normal ladder):

1. `earnings_candidate_rows()` — unselected, non-body document rows that could
   plausibly be the release: description or type self-labels **exhibit 99** in
   any malformation, **or** a **bare `EX-<n>`** type with no sub-number (the
   Illumina/HPE/Kraft Heinz shape), **or** a release-shaped description.
   Deliberately narrow: a sub-numbered securities exhibit (Dominion `EX-1.1`,
   Emerson `EX-2.1`, Danaher `EX-3.1`, Marathon/MPLX `EX-10.1`) is **not** a
   candidate and those filings keep `8K_BODY` unchanged.
2. `confirmable_release_candidate()` — selects a **specific** candidate only on
   index/description evidence (the standard the NVIDIA/ONEOK/Micron override
   rows were written to). Type is deliberately not evidence; neither is
   filename. Returns None when nothing — or more than one thing — is
   confirmable: ambiguity is loud, never guessed. Selected at **medium**
   confidence, never high.
3. Candidates present but none confirmable → **UNRESOLVED**, counted against
   the 1% ceiling. A genuine exhibit-less 8-K (no candidates) keeps the
   `8K_BODY` fallback at high, unchanged.

**MEASURED corpus effect: 15 pick changes.**

| disposition | n | filers |
|---|---:|---|
| resolved to a real release (medium) | **11** | Aon, Biogen, Vistra ×3, Pioneer ×2, Zoom, TI, Arista, Linde |
| newly **UNRESOLVED** (loud, counted) | **4** | Illumina ×2, HPE, Kraft Heinz — all describe the release row "EXHIBIT 1"/"EXHIBIT 2", so nothing in the index confirms it |

New unresolved rate **4/10,569 = 0.038%** against the 1% ceiling → WARN only,
no FATAL. Confidence distribution moves high 10,529→10,518, medium 16→27.

Two notes for the record: the fix **subsumes the ONEOK and Micron override
rows** for selection (the general screen now reaches the same documents on
description evidence, at medium; the rows still fire and carry them to high) —
the rows stay, they are ratified and evidenced. And the 15 include **Linde
`0001654954-22-005503`**, an `EX-95.1`-typed row described `EX-99.1` that B1's
own table did not list.

**B2** — the ratified segment-1 diagnosis' "0 genuine selection failures" and
"benign `8K_BODY` class" are **scoped to the 400 filings examined**; a dated
correction is appended to `data/f2/status/S6_seg1_ex99_diagnosis.md`. The
unread remainder of that class is where the defect lived.

**B6** — the per-CIK release-language **share is now emitted for every CIK**
(new `release_language_missing_share` audit column), and CIKs at or above
`P6_WATCH_SHARE = 0.40` but under the flag bar are printed as a named **WATCH
LIST**. Pioneer at 38/77 = 49.4% is one filing from flagging and is
independently implicated in B1. **No threshold was moved** — `P6_MISSING_
RELEASE_SHARE` stays 0.5.

**B7** — `press_release_typed_outside_ex99()`'s docstring stated its own
trigger's 3 hits as though it were the class size. Corrected: the class is
**38 filings**; P3 sees only descriptive-description instances, and the
fallback candidate screen is what covers the class.

**B17** — `load_validation_exceptions()` gains
`RATIFIED_VALIDATION_EXCEPTIONS`, the code-side gate its two sibling override
files already had: an unratified row is now refused at load. The set ships
**empty** (measured: all 244 members pass every FATAL check).

### 2026-08-24 — AMENDMENT A11: the S4 half of the S7 red-team fixes (B5, B11, B15, B21)

*(Renumbered by the main session from a duplicate "A9" — two agents took
the same next-free number concurrently; `S4_fundamentals.md` §12 refers
to this section as A9. Content unchanged.)*

**Ruled by the main session** (`F2_PROGRESS.md` §5, S7 triage entry) on
findings B5/B11/B15/B21 of `data/f2/status/S7_redteam.md`. **Adds to** §5.3
and A5; **supersedes nothing** — every change is an additional column, an
additional check, or a docstring statement. **MEASURED: zero of the 3,416
resolution states change.** Evidence:
`data/f2/status/S4_fundamentals.md` §12 and
`data/f2/concept_resolution_prediction_244.csv`.

**A9.1 (B5) `companyfacts_tail_lag` — an independent tail check.** The
coverage denominator (A5.1) and the staleness anchor (A1.3) are both defined
by the data being checked, so a companyfacts document truncated at the tail
scores 100% with no alarm. New check, run against S3's filing metadata read
**read-only** (`file:…?mode=ro`): per member, count the in-window 10-K/10-Q
filings filed after its last fundamentals fact. **WARN at ≥ 2** filings
behind, **INFO at exactly one**. It changes no resolution state — it makes the
blind spot loud. If the `filings` table is unreadable the run reports
`NOT CHECKED` at WARN rather than passing silently. MEASURED: **1 WARN**
(Citigroup 831001, 2 filings / 167 days behind, scoring 0.9767) and **21
INFO** (82–92 days, one filing — the ordinary propagation lag of the most
recent quarter). Scoped to each member's own coverage window, like every other
check here, so EIDP (30554) — complete within its 2019 window, 29 filings
behind over the corpus window — is reported in the run summary rather than
alarmed on.

**A9.2 (B11) reporting currency is recorded and warned.** `unit` was stored
per fact and never consulted. `concept_resolution.csv` gains **`unit`** (the
dominant unit of the rows the resolution points at) and **`units_mixed`**, and
a new `fundamentals_non_usd_reporting` **WARN** fires per resolved
`(cik, family)` whose dominant unit is a non-USD currency. Currency detection
is an ISO-4217 *shape* test, so an unknown three-letter code warns rather than
passing. Nothing is converted anywhere in F2. MEASURED over the 244: **one
member — Enbridge (895728, core/energy) — 13 resolved families, 12 in `CAD`
and one in `CAD/shares`, none mixed**; its price series is USD, so any
fundamentals-to-price ratio is wrong by the exchange rate until F5 converts.
No other member reports a non-USD currency (the only other non-USD units in
the corpus are two `BillionsCubicFeet` rows and one `segment` row, both
non-monetary and neither dominant).

**A9.3 (B15) duration mix is recorded; coverage semantics unchanged.**
`_quarter_bucket()` buckets on `period_end` alone, so an annual or
year-to-date fact counts toward the quarter it ends in. That stays — coverage
asks whether a concept was disclosed for a period, not at what frequency — but
the row now carries **`duration_mix`** (`instant` / `Q` / `H1` / `9M` / `FY`
profile) and `ConceptResolution`'s docstring states explicitly that `tags`
promises neither a unit nor a duration. **No semantics change is proposed**,
because MEASURED at 244 scale the defect class is empty: **zero** resolved
pairs have no quarterly-length or instant fact. (B15's Emerson example does
not reproduce as a resolved pair — CIK 32604 `revenue` is `ABSENT` in both the
shipped CSV and the replay, because its coverage window closes before its
`Revenues` rows; the underlying tag-level observation — Emerson never tags a
quarterly-length `Revenues` duration in a 10-Q — is correct.)

**A9.4 (B21) 8-K sourcing is stated.** `OPERATING_FORMS`' comment now says
that 8-K facts are admitted **deliberately** (an earnings release is a real
dated disclosure of the same GAAP fact; excluding it would drop 12,172 parquet
rows), alongside the DEF 14A exclusion it already argued. MEASURED: **zero**
resolved flow-family pairs depend on 8-K-sourced quarterly facts, so the
admission changes no resolution today.

**Schema note:** `concept_resolution.csv` goes from 8 to **11 columns**
(`unit`, `units_mixed`, `duration_mix` appended). Column order and every
existing column's meaning are unchanged.

### 2026-08-24 — AMENDMENT A12: the four bare-EX-<n> singletons, and a dated correction to §11's bankruptcy instance

*(Renumbered by the main session from a duplicate "A10" — the second of
two concurrent-numbering collisions today (see A11's note);
`S3_metadata_documents.md` §12.9 refers to this section as A10. Content
unchanged.)*

**Ruled by the main session** (F2_PROGRESS.md §5). Two items, neither changing
a ratified rule.

**1. The four S7-B1 unresolved filings are absorbed by the RATIFIED MECHANISM,
not by a new policy route.** A9 left four filings loud-UNRESOLVED because their
release row is typed `EX-1`/`EX-2` and described "EXHIBIT 1"/"EXHIBIT 2" — it
self-labels neither as exhibit 99 nor as a release, so nothing in the index
confirms it. The stored cover page's own body text *would* resolve all four,
but a third evidence route for 4 filings fails lazy-elite and is **NOT
adopted**. Instead `data/f2/earnings_doc_overrides.csv` grows **4 → 8 rows**
(seven `select_document`, one `exclude`), each carrying (a) the cover page's
Item 2.02 quote verbatim and (b) the candidate-row fact, with content
verification deferred to the extraction-qa pass post-delta per the NVIDIA
standard.

| accession | filer | selected document |
|---|---|---|
| `0001110803-16-000185` | Illumina Q1 2016 | `a1q16earningsrelease.htm` |
| `0001110803-16-000194` | Illumina Q2 2016 | `a2q16earningsrelease.htm` |
| `0001645590-17-000006` | HPE Q4 FY2017 | `ex-991x10312017x8k.htm` |
| `0001637459-19-000050` | Kraft Heinz 2019-06-07 | `a6719exhibit991.htm` |

**FUTURE INSTANCES OF THIS SHAPE STAY LOUD-UNRESOLVED** — the mechanism
absorbs measured singletons; the policy is unchanged and is pinned by
`test_future_instances_of_the_bare_ex_shape_stay_loud_unresolved`.

**A correction to S7 B1's own table, found while writing the evidence:** B1
named HPE's release `pressrelease112117.htm`. That is the **Item 5.02**
document — the Antonio Neri CEO-appointment announcement. HPE's cover page maps
its exhibits explicitly: Item 2.02 attaches the segment-results release as
**Exhibit 99.1** (`ex-991x10312017x8k.htm`, whose filename encodes both
`ex-99.1` and the 10/31/2017 fiscal quarter end), while Item 5.02 furnishes the
Neri release as Exhibit 99.2. The override names Exhibit 99.1. HPE is also the
only one of the four with **two** unselected candidates, not one.

**MEASURED replay against the attempt-5 stored corpus: 15 pick changes, 0 new
unresolved.** Not 19: the four filings were **already inside** A9's 15 (they
were changing from the stored cover page to UNRESOLVED), so these rows
*convert* four of the fifteen from unresolved to resolved rather than adding
to the count. Composition is now 15 resolved / 0 unresolved, against 11/4
before.

**2. Dated correction to §11's shared-window amendment (docs pass).** The
enumeration-window entry above (line ~1002) cites "the **2020-06-28** 8-K item
1.03 — the corpus's **only** bankruptcy". Both details are stale: the corpus
holds **TWO** item-1.03 filings for CIK 895126, filed **2020-06-29** and
**2021-01-19**. Per the append-never-rewrite rule the original text stands;
this note is the correction. **The amendment's conclusion is unchanged and if
anything strengthened** — both filings fall outside CIK 895126's own membership
spell (it first qualifies at 2026-07-01, coverage_start 2024-07-01), so
per-company clipping would lose *both*, and the shared enumeration window is
what keeps them.

### 2026-08-24 — AMENDMENT A13: Pioneer 2018-04-09 excluded (a candidate-screen resolution that was a mis-label)

*(Renumbered by the main session from a duplicate "A11" — third
concurrent-numbering collision today; `S3_metadata_documents.md` §12.10
refers to this section as A11. Content unchanged. Future amendments:
take the number AFTER the highest in this file at write time, and grep
first.)*

**Ruled by the main session** (F2_PROGRESS.md §5) on the content verification's
one finding (`S6_ex99_manual_read.md` §W.3: 14 of the 15 new picks CORRECT, 1
mis-labelled). **Supersedes one figure in A9/A10** — the override file is
**9 rows**, not 8 — and removes one filing from A9's resolved set.

**The finding, re-verified here against the cached bytes.** A9's candidate
screen resolved `0001193125-18-111008` to `d564737dex991a.htm` at medium,
because its sole candidate row is described `EX-99.1(A)`, which self-labels as
exhibit 99.1. The document is the **IPAA Oil & Gas Investment Symposium**
conference slide deck (36,577 chars, opening "IPAA Oil & Gas Investment
Symposium April 10, 2018 / Exhibit 99.1A / Forward-Looking Statements"), with
**zero** hits for "first quarter 2018", "1Q18", "today reported", "press
release", "news release" or "preliminary". The filer says so itself — the cover
body's Item 2.02 is a conditional Regulation-FD wrapper:

> "…hereby furnishes the portions, **if any**, of the **Investor Presentation**
> titled 'IPAA Oil & Gas Investment Symposium', which is attached hereto as
> Exhibit 99.1 (the 'Presentation'), that constitute material non-public
> information regarding the Company's results of operations…"

with Item 7.01 carrying the substance ("the Company will post the Presentation
on the Company's website").

**This is a MIS-LABEL, not a mis-pick** — the filing has no better candidate,
so the conditional fallback had nothing else to choose. And it is the one place
where A9's fix made a filing **less** honest: pre-fix it claimed `8K_BODY`,
which is true of a cover page; post-fix it claimed `EX99_PRESS_RELEASE`, which
is false of a slide deck. Resolved by the same evidenced `exclude` mechanism as
AT&T, and the evidence here is stronger (the filer's own words name it a
Presentation).

**MEASURED replay against the regenerated corpus: exactly 1 pick change, and
the distribution moves exactly as ruled** — `medium` **27 → 26**, excluded
**1 → 2**; `high` 10,522 and `low` 19 unchanged; **0** new unresolved. The
override file is now **9 rows: seven `select_document`, two `exclude`.**

**Audit accounting.** Both exclusions surface as `EXCLUDED_BY_OVERRIDE` rows in
`ex99_selection_audit.csv` and as `earnings_doc_excluded_by_override` **INFO**
problems, and both stay out of the `earnings_doc_unresolved` rate and the
sector-coverage denominator — a human ruling that no release exists is not the
policy failing to resolve one.

**One measurement worth recording against B6.** This deck **passes** the P6
release-language screen, and it passes on a single boilerplate hit —
"investor relations" inside a mailing-address line ("…Irving, Texas 75039,
Attention: Investor Relations…"). That is B6's stated secondary weakness
(`"conference call"` / `"investor relations"` / `"webcast"` are boilerplate, so
a P6 **pass** is weak evidence) demonstrated on a real document. No threshold
or marker set was changed here; recording it so the next reader of a P6 pass
knows what it is worth. §W.3's note that this filing is one of Pioneer's 37
release-language-missing picks is therefore not accurate for the post-A9 state
— it passes, on boilerplate; Pioneer's watch-list position is unaffected.

### 2026-08-24 — AMENDMENT A14: the PSEG handler, the deck-title screen, and the two-candidate census

*(Number checked by grep at write time per A13's note: A13 was the highest in
this file, so this is A14.)*

**Ruled by the main session** (F2_PROGRESS.md §5) on the ordered PSEG watch-list
read (`S6_ex99_manual_read.md` §W ADDENDUM). **Adds to** A6/A8; supersedes no
ratified rule. All counts MEASURED offline, 0 GETs.

**The defect — F2's largest single-filer content defect.** All **45** of PSEG's
(CIK 788784, utilities/extension) earnings selections were the earnings
**conference-call slide deck**, every one at `high` confidence. Re-verified here
independently: the index shape is `{('EX-99', 'EX-99.1'): 45}`, uniform
2015-07-31 → 2026-08-04 with no exceptions; all 45 filings are
`items=2.02,7.01,9.01` (release under 2.02, deck furnished under 7.01 — the
policy took the 7.01 artifact); and all 45 selected documents carry deck titles
("PSEG Earnings Conference Call …" 2015→2021, "… Financial Results
Presentation" 2022→2026, and "Financial Results and Conference Call" for
2021-11-02 / 2022-02-24) followed by forward-looking boilerplate.

**Root cause:** the ladder prefers a sub-numbered `EX-99.1` over a bare
`EX-99`, and `_best_by_description()` cannot break the tie because both
descriptions are content-free — literally `"EX-99"` and `"EX-99.1"`. This is the
Prologis shape one rung lower. **Third independent confirmation that selection
confidence does not track correctness.**

**1. A PSEG per-filer handler** (`_pseg_earnings_document`, Prologis pattern):
on the two-candidate shape, take the bare `EX-99`. Same evidence standard as
Prologis — the complement is proven (all 45 selected siblings are decks), and
the bare `EX-99` bytes are **not cached** (never selected), so they are
content-verified post-delta by extraction-qa. **A blanket bare-before-
sub-numbered preference flip is explicitly NOT made**, and the census below
shows why: ConocoPhillips `0001157523-17-001334` has the same shape and its
existing pick is CORRECT.
**MEASURED replay: exactly 45 pick changes, PSEG only.** The confidence
distribution is unchanged (high 10,522 / medium 26 / low 19 / excluded 2) —
PSEG's picks were high before and after.

**2. A deck-title screen**, generalising what caught it. A selection is
`deck_shaped` when its TITLE region names it a call deck **and** the deck's own
boilerplate corroborates within 1,500 chars. Both halves are MEASURED, not
speculative:

| marker (title region) | title-only hits | CIKs |
|---|---:|---|
| `earnings conference call` | 26 | PSEG 25, **Danaher 1** |
| `financial results presentation` | 18 | PSEG only |
| `financial results and conference call` | 2 | PSEG only |

25 + 18 + 2 = 45 = all of PSEG. The generic phrase `"conference call"` was
measured and **REJECTED** (93 hits / 11 CIKs, incl. Texas Instruments 45 and
Nike 12 whose releases merely name the call). The corroboration requirement
exists for one measured false positive: Danaher `0000313616-20-000081` is a
genuine release headlined "… AND SCHEDULES FIRST QUARTER EARNINGS CONFERENCE
CALL". Title-only flags `{PSEG 45, Danaher 1}`; title+corroboration flags
`{PSEG 45}` exactly.

The screen is **independent of P6 and of confidence** — PSEG scored 21/45
release-language-missing and sat *under* the P6 bar, because all 24 "passers"
passed on `"investor relations"` from a contact slide. It flags on **any**
deck-shaped selection, with no majority test and no minimum sample: unlike
release-language-missing there is no benign share of decks-as-press-releases.
Feeds `n_deck_shaped` / `deck_shaped_flag` in the audit CSV plus an
`ex99_deck_shaped_selection` WARN.

**Corpus sweep over all 10,567 cached selections (0 uncached):**

| sweep | flagged CIKs |
|---|---|
| pre-fix stored picks | **1 — PSEG 45/45** |
| post-fix picks | **0** |

Acceptance met in all four directions: PSEG-pre-fix flags 45/45; PSEG-post-fix
does not (its 45 new picks are uncached → **unmeasured, never clean**, and are
the segment-2 delta); Prologis-post-fix does not (45 seen, 0 deck); Netflix does
not (47 seen, 0 deck).

**3. Two-candidate-shape census** — the class enumerated, not sampled. Over
every cached earnings index, filers carrying a bare `EX-99` **and** an
`EX-99.x` in the same filing:

| CIK | filer | sector/stratum | filings | shape | disposition |
|---|---|---|---|---:|---|
| 788784 | Public Service Enterprise Group | utilities / extension | **45** | `('EX-99','EX-99.1')` | **fixed by the handler** |
| 1163165 | ConocoPhillips | energy / core | **1** | `('EX-99','EX-99.2')` | **true negative — no action** |

ConocoPhillips's single instance (`0001157523-17-001334`, 2017-05-02) selects
its bare `EX-99` already — described "EXHIBIT 99.1", and its bytes open
"ConocoPhillips Reports First-Quarter 2017 Results; … HOUSTON--(BUSINESS
WIRE)". It is the release. Per the ruling no other filer is auto-fixed; this
one needed no read beyond the characterisation above, and the roster is
otherwise empty — **the two-candidate class is 2 filers / 46 filings, and only
PSEG is defective.**

**Also recorded from §W (no code change):** a P6 *pass* can rest on
contact-slide boilerplate, so the watch-list share is a **floor, not an
estimate** — PSEG's 21/45 understated a 45/45 defect.
