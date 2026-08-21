# Ingestion Notes — Week 1

Covers `edgar_client.py`, `ingest_metadata.py`, `data/universe.csv`, and
`data/filings_metadata.db`. Read alongside `DISCOVERY.md` (§1 Data Sourcing,
§3 MVP Scope, §5 Evaluation Design) and `ROADMAP.md` (Week 1).

**Updated post-Week-1** after an Opus-tier review of two narrow findings
(the XOM CIK override and the exhibit-filename-unreliable fix) surfaced a
bigger underlying gap: nothing in the pipeline verified that a resolved
CIK's data was actually *complete*. That review is what finding #3 below,
the filing-count table, the `validate_universe()` section, and the
`filing_documents` section now reflect. The original (wrong) version of
finding #3 claimed `filings.recent` covered back far enough for every
company "based on an aggregate average" -- that average hid a real
3-company shortfall; see finding #3 for the corrected version.

## Universe: how it was chosen

25 companies (within the 20–30 mandated range), 5 per sector across the 5
buckets `DISCOVERY.md` §3 names: tech, financials, healthcare, energy,
consumer.

- **Tech:** AAPL, MSFT, GOOGL, NVDA, CSCO
- **Financials:** JPM, BAC, GS, MA, V
- **Healthcare:** JNJ, UNH, PFE, ABBV, MRK
- **Energy:** XOM, CVX, COP, SLB, OXY
- **Consumer:** PG, KO, WMT, HD, MCD

Selection heuristic: well-known, decades-listed large-caps, chosen so each
name is virtually certain to have a complete, unbroken 10-K/10-Q/8-K filing
history across the 3-year lookback window. This was a deliberate convenience
choice, and it is explicitly **not** a fix for the survivorship-bias risk
`DISCOVERY.md` §5/§6 already flags: this list is built from companies that
are large and prominent *today*. A company that was similarly prominent in
2023–2024 but has since been acquired, delisted, or gone through distress
would not appear here by construction. That bias is inherited by every
downstream result trained on this universe. It is restated (not solved) in
this doc and should be restated again in the Week 7 limitations write-up —
see the comment in `ingest_metadata.py`'s module docstring for the same note
next to the code.

The universe is locked in `data/universe.csv` (ticker, cik, sector,
company_name) and is not expanded past this list without an explicit
decision logged in project docs, per the "no silent scope expansion"
non-negotiable.

## Caching / staleness policy

All raw EDGAR responses are cached under `data/raw/` (excluded from git —
see `.gitignore` for the reasoning) and are never re-fetched unless stale:

| Endpoint | Cache location | Staleness policy |
|---|---|---|
| `company_tickers.json` | `data/raw/company_tickers.json` | Re-fetch if >24h old (SEC republishes this ~daily) |
| `submissions/CIK##########.json` | `data/raw/submissions/` | Re-fetch if >24h old (near-real-time as new filings post; a same-day cache hit is safe, a multi-day-old one risks missing a very recent filing) |
| `submissions/CIK##########-submissions-NNN.json` (pagination chunks, `filings.files[]`) | `data/raw/submissions/` | Same 24h staleness policy as the main submissions.json, not "cache forever" — these describe a closed historical date range so in practice they shouldn't change, but nothing documented guarantees SEC never corrects an entry near a chunk boundary, so this doesn't assume immutability without confirming it |
| `{accession}-index.html` (per-filing document index) | `data/raw/filing_index/` | **Never re-fetched once cached** — an already-filed accession's document list is immutable; there's no "stale" state for it |

`ingest_metadata.py` re-derives the SQLite tables from whatever's in the
local cache every run — that recomputation is cheap and local (no network),
so re-running the script is always safe. The network calls inside
`EdgarClient` are the only thing gated by staleness.

**Verified idempotent (original Week 1 pass):** ran `ingest_metadata.py`
three times against the same universe. Run 1 made 331 network requests (25
`submissions.json` + ~306 filing-index HTML fetches for 8-Ks with a `2.02`
item code). Run 2 (before the exhibit-type-detection fix, see below) made 0.
After changing exhibit detection to use a different endpoint (new cache
keys, so a legitimate re-fetch), run 3 made 0 network requests and
reproduced identical filing counts by form type (`10-K: 69, 10-Q: 206, 8-K:
854`).

**Re-verified after the pagination + `filing_documents` corrective pass**
(see finding #3 and the two new sections below): ran `ingest_metadata.py`
three times again against the corrected pipeline and a freshly rebuilt DB
(schema gained new columns/tables, so the DB was regenerated from the
existing local cache rather than migrated in place — no network cost, since
`ingest_metadata.py` always recomputes SQLite rows from cache). Run 1 made
25 `submissions.json`/chunk-fetch requests (0, since already cached from the
JPM/BAC/GS fix work) plus 25 new `-index.html` fetches for earnings 8-Ks
that only became visible in-window once JPM/BAC/GS's pagination was fixed.
Runs 2 and 3 made **0** network requests and reproduced identical filing
counts (`10-K: 75, 10-Q: 224, 8-K: 972`) and **zero duplicate
`accession_number` values** across 1,271 total filing rows. A 5-company spot
check (JPM, AAPL, XOM, MCD, OXY) of 10-K accession numbers/filing dates
against a live, uncached `data.sec.gov/submissions/...` fetch matched
exactly.

## What's stored, and the point-in-time discipline

`data/filings_metadata.db` (SQLite) has four tables:

- `companies` — cik, ticker, sector, company_name (mirrors `universe.csv`).
- `filings` — one row per accession number, with:
  - `filing_date` — **EDGAR's own recorded public filing date**
    (`filingDate` from `submissions.json`, or from a `filings.files[]`
    pagination chunk when the filing is old enough to require one — see
    "filings.files[] pagination" below). This is the point-in-time field
    every downstream walk-forward split must sort on.
  - `report_date` — the fiscal period end date, stored for reference only.
    **Never** to be used as a point-in-time timestamp — a 10-Q for a quarter
    ending in March is routinely filed 4–6 weeks later; using `report_date`
    instead of `filing_date` anywhere downstream would reintroduce exactly
    the look-ahead bias `DISCOVERY.md` §5 calls out.
  - `acceptance_datetime` — EDGAR's more granular acceptance timestamp,
    kept in case future work needs sub-day precision.
  - `accession_number` (primary key — verified no duplicates), `form`,
    `primary_document`.
  - For 8-Ks: `items` (raw item codes, e.g. `"2.02,9.01"`),
    `has_earnings_item` (true if item `2.02` — Results of Operations and
    Financial Condition — is present, the standard trigger for an
    EX-99.1 earnings press release; matched by splitting `items` on `,` and
    comparing exactly, not a substring check — see "Two small fixes" below),
    `ex99_1_document` (the resolved EX-99.x exhibit filename ONLY — `NULL`
    if no exhibit exists for this filing), `exhibit_lookup_done`, and the
    four `earnings_doc_*` columns (`earnings_doc_filename`,
    `earnings_doc_relative_path`, `earnings_doc_section_type`,
    `earnings_doc_selection_confidence`) — the *general* resolved earnings
    document, which also covers the "no exhibit, fall back to the 8-K body"
    case. See "`filing_documents` + the earnings-document selection policy"
    below for how these are derived. Extracting the document *text* itself
    is Week 2's job (`extract.py`); this week only records enough to locate
    it without re-deriving anything.
- `filing_documents` — one row per document listed on an earnings 8-K's
  index page (`accession_number, seq, doc_type, description, filename,
  relative_path, source_table`), materialized from the already-cached
  index-page HTML. See below.
- `universe_validation_problems` — populated only when `ingest_metadata.py`
  is run with `--allow-incomplete-universe`; every problem
  `validate_universe()` found (not just FATALs), keyed by run date. See
  below.

## Filing window

12 quarters (~3 years) back from 2026-08-10, i.e. filings with
`filing_date >= 2023-08-14`. Pulled counts across the 25-company universe
**after the pagination fix (see finding #3)**:

| Form | Count |
|---|---|
| 10-K | 75 |
| 10-Q | 224 |
| 8-K | 972 |

(10-K = exactly 3/company across all 25 companies — the expected ~3 annual
filings in a 3-year window; 10-Q = 8–9/company depending on exact
quarter-end alignment with the cutoff; 8-K count is high and expected, since
8-Ks cover far more than earnings — executive changes, material agreements,
debt issuances, etc. — and JPM/BAC/GS in particular file *far* more 8-Ks
than the rest of the universe, e.g. structured-note/debt-program
supplements, which is expected for large banks, not a bug.)

These are the **corrected** counts, post-pagination-fix — see finding #3
below for the original (wrong) Week 1 numbers and why they were wrong.

Of the 972 8-Ks, 331 have item `2.02` (an earnings-related 8-K); 327 of
those resolved to a specific EX-99.1 (or EX-99.x) exhibit filename via the
selection policy in "`filing_documents` + the earnings-document selection
policy" below. The other 4 (`BAC` 2024-01-08, `GS` 2026-01-08, `CVX`
2026-04-09, `CVX` 2024-01-02) resolved to `section_type='8K_BODY'` — checked
manually against their filing index, they genuinely have no `EX-99.x`
attached (item 2.02 disclosed in the 8-K body itself, no separate press
release document filed). Not a parsing bug. (The BAC case is new versus
Week 1's original 3-filing list — it only became visible once JPM/BAC/GS's
filing history was actually complete; Week 1's report of "3 unresolved
filings" was itself downstream of the same truncation bug finding #3
describes, since BAC's fuller earnings-8-K history wasn't in the DB yet to
even check.)

## EDGAR-behavior findings — corrections/confirmations for `DISCOVERY.md` §1

`DISCOVERY.md`'s open item said the rate-limit/User-Agent facts were
corroborated by secondary sources but not directly confirmed (the direct
fetch of `sec.gov/about/developer-resources` 403'd in that research
session). Confirmed directly this session, with a properly-headered request:

1. **User-Agent requirement is real and strictly enforced, exactly as
   documented.** A request to `data.sec.gov/submissions/...` *without* a
   `User-Agent` header returns **HTTP 403** immediately. The identical
   request *with* `"FinScreen Research vihanpatil7@gmail.com"` set returns
   200. This matches DISCOVERY.md's claim exactly — no discrepancy, just
   now empirically confirmed rather than secondhand.
2. **`sec.gov/about/developer-resources`'s earlier 403 was indeed a
   bot-check unrelated to policy**, as DISCOVERY.md speculated — it returns
   200 with a normal `User-Agent` header set. Confirms the "not a policy
   signal" read was correct.
3. **`submissions.json`'s `filings.recent` array is not a fixed time
   window — it's the most recent ~1000 filings of *any* type**, sorted
   newest-first, and this DID cause real missing data for 3 of 25
   companies. **This corrects the original version of this finding**, which
   claimed "for every company in this universe, `filings.recent` covered
   back to at least 2015 ... so this wasn't a real problem here" — that
   claim was wrong. It was based on an aggregate/spot-check impression, not
   a per-company check of the actual minimum date reached, and it hid a
   real shortfall for **JPM, BAC, and GS**: high-filing-volume banks (large
   volumes of Section 16 filings, structured-note/debt-program 8-Ks, etc.)
   whose most-recent-~1000-filings window only reached back to
   **2025-08-08** — about 12 months, not the 3 years this pipeline needs.
   Concretely, before the fix, these 3 companies showed only 1 10-K and 3
   10-Qs each in the DB (vs. 3 and 8–9 for the other 22 companies) —
   real, silently truncated data, not an artifact of anything else.

   **Fixed** by `EdgarClient.get_effective_recent()`: for any company where
   `min(filingDate in filings.recent) > cutoff` and `filings.files[]` is
   non-empty, it fetches `filings.files[]` chunk files
   (`data.sec.gov/submissions/CIK...-submissions-NNN.json`, same shape as
   `filings.recent`, same 24h staleness cache policy) — newest chunk first,
   stopping once a chunk's range reaches back past the cutoff — and merges
   them into an effective "recent" set before any filtering happens.
   `ingest_metadata.py` now calls this instead of reading
   `submissions["filings"]["recent"]` directly. **After the fix, all three
   companies land at the expected 3 10-Ks and 9 10-Qs** (see the Filing
   window table above) -- **correction (Week 2 corrective pass): this was
   originally written as "matching every other company in the universe,"
   which overstated it.** 10-Q count across the universe genuinely ranges
   8-9/company depending on exact quarter-end alignment with the lookback
   cutoff (stated correctly in the Filing window table itself) -- UNH, for
   example, has 8 10-Qs, not 9, and always did; that's normal, expected
   variance, not a JPM/BAC/GS-style truncation bug. The corrected claim is
   just: JPM/BAC/GS now reach the same *plausible* range (3 10-Ks, 8-9
   10-Qs) as every other company, not literally "9 10-Qs for everyone."
   `validate_universe()` (below) now also hard-fails on this condition
   going forward, as a regression guard, rather than relying on it being
   independently rediscovered.
4. **NEW, not previously flagged anywhere: `company_tickers.json`'s
   ticker→CIK mapping is not always the entity with full filing history.**
   XOM currently maps (per `company_tickers.json`, fetched live) to CIK
   `2115436` ("ExxonMobil Holdings Corp"), which has exactly **one** filing
   ever (a 2026-08-03 10-Q) — evidently a very recently created successor/
   holding-company entity from a corporate restructuring. The full,
   continuous 30+ year Exxon filing history — including everything in our
   3-year window — lives under the legacy CIK `34088` ("Exxon Mobil Corp"),
   which is *not* what `company_tickers.json` currently points `XOM` at.
   **`data/universe.csv` uses CIK 34088 for XOM, overriding the
   `company_tickers.json` mapping**, after manually confirming this via
   `data.sec.gov/submissions/CIK0000034088.json`. This directly contradicts
   the roadmap's assumption ("use company_tickers.json instead of
   hand-typing CIKs") for at least this one company — the bulk ticker map is
   a good *starting point* for CIK lookup but isn't reliable as the sole
   source of truth when a company has undergone a recent corporate
   restructuring. Worth a permanent code comment (added in
   `ingest_metadata.py` and `universe.csv`) rather than a silent one-off fix,
   since this could recur for other companies in future universe changes.
5. **Exhibit filenames don't reliably encode the exhibit type.** The
   original implementation tried to identify EX-99.1 exhibits by regex-
   matching `"ex99"`/`"ex-99"` in filenames from the filing's document index.
   This failed for XOM (`livef8k1q26991.htm` — "99.1" encoded as an
   unlabeled `991` suffix), Procter & Gamble (`fy2526q4amj8-kexhibit991.htm`
   — "exhibit991", no "ex99" substring), and UnitedHealth
   (`earningsrelease2q26_7152.htm` — no numeric reference to 99 at all). 3
   of the first 5 companies spot-checked hit this. **Fixed** by fetching the
   EDGAR `{accession}-index.html` page instead, which has an authoritative
   `Type` column (e.g. literal string `"EX-99.1"`) sourced from the filer's
   own SEC-HEADER document tags — not inferred from filenames. **Confirmed
   as the permanent approach** in the corrective pass — see "`filing_documents`
   + the earnings-document selection policy" below for the full selection
   policy now built on top of this (multiple/zero-exhibit filings, the MCD
   dual-"8-K"-typed-row hazard, HTML-entity-unescaping). Week 2's
   `extract.py` reuses `filing_documents` and does not re-resolve exhibits.
6. **NEW: `data.sec.gov` and `www.sec.gov` are both up and behaving as
   documented; no discrepancy found during the corrective pass.** All new
   pagination-chunk and index-HTML fetches used the same `User-Agent`,
   returned normal 200s, and never triggered a 429 across this pass's ~65
   additional requests (38 chunk fetches for JPM/BAC/GS + 25 index-HTML
   fetches for newly-visible earnings 8-Ks + 1 `company_tickers.json`
   refetch + 1 `submissions.json` force-refresh during manual verification).
   Nothing here contradicts `DISCOVERY.md` §1.

None of the above are rate-limit or throttling surprises — 10 req/sec was
never approached (client caps well under it) and no 429s were observed
across either the original Week 1 pass (~640 total requests) or this
corrective pass (~65 additional requests).

## `validate_universe()` — hard-fail pass before any DB write

`ingest_metadata.py` runs `validate_universe()` against all 25 companies'
submissions data (cached where possible; fetches happen and get cached like
any other `EdgarClient` call otherwise) **before the ingestion loop writes
anything to the DB**. This exists directly because of finding #3 above:
two narrow one-off patches (the XOM CIK override and the exhibit-filename
fix) turned out to both be symptoms of the same gap — nothing checked that
a resolved CIK's data was actually *complete*. Rather than wait to
rediscover that the same way again, this is now a standing, per-run check.

Per company, per run:

| Check | Severity | What it catches |
|---|---|---|
| Entity resolves | FATAL | `submissions.json` fetch fails, or has no `filings.recent` key |
| History reaches cutoff | FATAL | `min(filing date)` doesn't reach the lookback cutoff even after `get_effective_recent()`'s pagination-chunk fetch — this is the exact JPM/BAC/GS bug from finding #3, now a regression guard |
| Plausible filing counts | FATAL if 10-K < 2 or 10-Q < 7 (hard floor); WARN if 10-K < 3 or 10-Q < 8 (expected-but-not-alarming) | truncation that isn't a total failure — e.g. a partial pagination fetch |
| No large filing gap | FATAL if >135 days between consecutive in-window 10-K/10-Q filings | calibrated off the 22 already-healthy companies; UNH's real max gap is 125 days, so 135 leaves headroom without being toothless |
| Recent activity (any form) — `recent_activity_any_form` | **WARN** if most recent filing of any form is >80 days old *(Week 2 corrective pass: raised from 45 and downgraded from FATAL — see below)* | an ordinary quiet filing period, most of the time — not reliable enough on its own to hard-fail a run |
| Recent activity (10-K/10-Q) — `recent_activity_10k_10q` | **FATAL** if most recent 10-K/10-Q is >135 days old | the check that actually detects a stopped-filing entity (e.g. a successor-entity migration); unaffected by the threshold change above |
| Current ticker matches | WARN | universe.csv's ticker isn't in `submissions["tickers"]` for that CIK |
| CIK map agreement | WARN | `company_tickers.json`'s CIK for a ticker disagrees with `universe.csv`'s — both values are reported, neither is silently preferred |

**Week 2 corrective pass — the 45-day "any filing" threshold was
miscalibrated, and `--allow-incomplete-universe` had a real scoping bug:**

1. **Threshold recalibration.** The original 45-day "any form" staleness
   threshold wasn't calibrated against the real inter-filing-gap
   distribution — it fired on HD 2 days over the line for an ordinary quiet
   period (see the HD writeup below), and checking the real 3-year gap
   distribution across all 25 companies found this isn't a one-off: the
   real max observed any-form gap is **70 days (SLB)**, meaning 45 days
   would misfire on roughly 10% of possible run-dates. Raised to **80 days**
   (max-observed + ~15% headroom — the same calibration discipline already
   used for `MAX_FILING_GAP_DAYS`/the 135-day 10-K/10-Q check) and
   **downgraded from FATAL to WARN**, split into its own check name
   (`recent_activity_any_form`, distinct from `recent_activity_10k_10q`)
   specifically so it can never be scope-matched together with the check
   that actually matters. The 135-day 10-K/10-Q-specific check is
   unaffected and stays FATAL — it's the one that reliably detects a
   genuinely stopped-filing entity, and a 135-day gap with literally nothing
   filed is a much stronger signal than an 80-day gap with nothing of *any*
   type filed.
2. **`--allow-incomplete-universe` was a blanket override, not a scoped
   one — fixed.** The original flag was a bare boolean: passing it
   downgraded *every* FATAL finding for the run, not just the one the
   caller intended to accept. Concretely: using it on 2026-08-10 to accept
   HD's (since-recalibrated) staleness FATAL also silently downgraded the
   JPM/BAC/GS-class `history_reaches_cutoff` regression guard for that same
   run, with no way for anyone to notice if a real regression had also
   fired that day. Now `--allow-incomplete-universe` takes an explicit,
   comma-separated list of check names to downgrade (e.g.
   `--allow-incomplete-universe=history_reaches_cutoff`) — any FATAL that
   fires on a check NOT named is still a hard failure, and every downgraded
   check is printed loudly (a `!`-bordered block), not just written to
   `universe_validation_problems`. See `parse_allow_incomplete_universe_arg()`
   and `run()` in `ingest_metadata.py`.

Every problem across all 25 companies is collected, printed as one
consolidated `ticker | severity | check | message` block, and the run
`sys.exit(1)`s if any FATAL remains outside the explicitly-scoped override
set. `--allow-incomplete-universe=<checks>` downgrades only the named
FATALs to WARN and, when used, writes *every* problem (not just FATALs) to
`universe_validation_problems(run_date, ticker, check_name, severity,
message)` instead of just printing — feeding the eventual limitations doc
rather than getting lost in run output.

**Verification done on this pass:**
- **Confirmed it catches the real (pre-fix) JPM/BAC/GS bug:** re-running the
  `history_reaches_cutoff` check's logic against the raw
  `submissions["filings"]["recent"]` array directly (i.e. skipping
  `get_effective_recent()`'s pagination merge, exactly what Week 1's
  original code did) reproduces `min_date = 2025-08-08 > cutoff =
  2023-08-14` for all three companies — the same FATAL `validate_universe()`
  would raise pre-fix.
- **Confirmed XOM produces a WARN, not a FATAL, not silence**, on both the
  `cik_map_agreement` check (`company_tickers.json` maps XOM to CIK
  `2115436`; `universe.csv` uses `34088`) and, newly noticed running this
  check for the first time, `current_ticker_matches` — CIK `34088`'s own
  `submissions.json` currently reports an **empty** `tickers` list (not just
  "wrong ticker" — no ticker at all), consistent with the ongoing
  holdco-restructuring picture in finding #4, where EDGAR appears to have
  moved the live ticker association to the new CIK while the legacy CIK
  still holds the actual filing history. Flagged here as a WARN, not
  silently accepted either direction, matching the design intent.
- **A genuine (not simulated) FATAL fired on the original Week 1 run: HD.**
  Home Depot's most recent filing of *any* form was `2026-06-24` (an `11-K`
  employee stock plan annual report), **47 days** before the `2026-08-10`
  run date — 2 days over the then-45-day threshold. Confirmed via a live,
  uncached `data.sec.gov` fetch (not a stale-cache artifact) that this is
  real: HD simply had no Form 4s, 8-Ks, or anything else file in that
  window, most likely an ordinary quiet period between its Q1 10-Q (filed
  2026-05-27) and whatever comes next. This is **not** the "entity stopped
  filing" failure mode the check is designed for (contrast with XOM's
  genuine holdco migration) — it's a healthy company with an unlucky
  run-date. That run used `--allow-incomplete-universe` to proceed.
  **Resolved in the Week 2 corrective pass** (see the recalibration writeup
  above): re-running `validate_universe()` with the 80-day/WARN threshold,
  HD's 47-day gap no longer produces any problem at all (47 < 80) — no
  override needed. Re-verified directly: a fresh `ingest_metadata.py` run
  against the current cache produces **zero** FATALs and only the two
  known XOM WARNs (`cik_map_agreement`, `current_ticker_matches`).

## `filing_documents` + the earnings-document selection policy

Replaces the old single `resolve_ex99_1()` (which returned a single
best-guess filename inline) with two separated concerns:

1. **`filing_documents`** — one row per document listed on an earnings
   8-K's index page (`accession_number, seq, doc_type, description,
   filename, relative_path, source_table`), parsed from the same
   already-cached `-index.html` (zero new network requests versus Week 1's
   approach). Populated from **both** index tables ("Document Format
   Files" and "Data Files" — `source_table` records which), not just the
   exhibits table.
2. **`select_earnings_document()`** — a standalone function over
   `filing_documents` rows, not inline in the parser, so the policy can be
   tested/reasoned about independently of HTML parsing.

**Selection policy** (first match wins): exactly one `EX-99.1` → take it
(high confidence). More than one `EX-99.1` → take lowest `seq`, confidence
`low`, log loudly as a canary (didn't occur across the real 331 earnings
8-Ks in this universe — verified with a synthetic test instead). No
`EX-99.1`, exactly one bare `EX-99` → take it (high confidence). No
`EX-99.1`/`EX-99` but `EX-99.2`/`.3`/etc. present → score descriptions
(`PRESS RELEASE`/`NEWS RELEASE`/`EARNINGS RELEASE` beat
`PRESENTATION`/`SUPPLEMENTAL`/`COMMENTARY`/`DATA SUMMARY`); a unique
positive-scoring winner is taken at medium confidence, otherwise lowest
`seq` at low confidence. No `EX-99.x` at all → fall back to
`filings.primary_document` (from `submissions.json`, always populated),
`section_type='8K_BODY'` — **never** by scanning the index for a row typed
`"8-K"`, since MCD's index pages carry two such rows (the real iXBRL
primary document at `seq=1` and a scanned PDF copy at a later `seq`),
confirmed directly against MCD's `0000063908-26-000067` index page during
this pass.

**Real-data results, all 331 earnings 8-Ks:** 327 resolved to
`EX99_PRESS_RELEASE` at **high** confidence (exact `EX-99.1` or bare
`EX-99` match — no `low`/`medium`-confidence cases occurred in this
universe/window); 4 resolved to `8K_BODY` (`BAC` 2024-01-08, `GS`
2026-01-08, `CVX` 2026-04-09, `CVX` 2024-01-02 — see the Filing window
section above). The multi-exhibit/no-clear-winner/MCD-dual-8-K-row edge
cases were all exercised with synthetic unit-style checks since they don't
occur in this real universe, confirming the code paths behave as specified
even though they're untested by the real data.

**Parser hardening added in this pass:**
- Cell text is `html.unescape()`d, not just tag-stripped, before any
  comparison — the "Complete submission text file" row's `Type` cell is the
  literal markup `&nbsp;`, which a tag-strip-only parse leaves as a
  non-empty garbage string rather than recognizing it as blank.
- After parsing an index page, the parse asserts the filing's
  `primary_document` (from `submissions.json`) appears among the parsed
  filenames, and asserts at least 3 total rows were parsed across both
  tables — both raise loudly on failure rather than risk a future EDGAR
  layout change silently reading as "no exhibit found," which looks
  identical to the legitimate no-exhibit case downstream.
- `relative_path` (not just a basename) is stored, so Week 2's `extract.py`
  doesn't need to reconstruct archive URLs itself, and `source_table` makes
  explicit that both index tables are read, not just an exhibits-only
  assumption.

**Two small related fixes, same pass:**
- The old `ON CONFLICT ... ex99_1_document=COALESCE(excluded.ex99_1_document,
  filings.ex99_1_document)` upsert could never clear a previously-stored
  value even when a re-resolution correctly determined there's no exhibit.
  Replaced with a plain `excluded.ex99_1_document` assignment (no
  `COALESCE`), and the exhibit/`earnings_doc_*` columns are now entirely
  omitted from the `UPDATE SET` clause on rows where exhibit lookup wasn't
  attempted (or failed) this run, rather than relying on `COALESCE` to
  protect them. Verified with an in-memory SQLite reproduction: a stale
  exhibit filename from a simulated bad first run is correctly overwritten
  by a `NULL`/`8K_BODY` result on a simulated corrected second run.
- `has_earnings_item` now splits `items` on `,` and compares exactly to
  `"2.02"`, instead of a substring check — removes a theoretical
  false-positive (e.g. a hypothetical future item code containing `"2.02"`
  as a substring of a longer code). Verified with a synthetic `"12.02,9.01"`
  items string, which the old substring check would have wrongly flagged.
- `EdgarClient.get_filing_index()` (the `index.json` variant, superseded by
  `get_filing_index_html()` back in finding #5) had no remaining callers —
  deleted outright rather than left around for something to reach for by
  autocomplete later.

## Known limitations / judgment calls for the project owner

- **Survivorship bias, restated (not solved):** see "Universe" section
  above.
- **XOM CIK override:** flagged above; worth a periodic re-check if
  `company_tickers.json` is ever relied on again for CIK lookups on a
  company that's undergone a recent restructuring (holdco conversions,
  spin-offs, redomiciliations — SLB/Schlumberger changed *names* multiple
  times but kept one CIK throughout, so this isn't universal; XOM's case
  looks like an in-progress transition where two CIKs are live in parallel,
  and — newly noticed this pass — the legacy CIK's own `tickers` list is
  now empty, which is itself a small piece of evidence the migration is
  further along on EDGAR's side than "two CIKs quietly coexisting").
- **`filings.recent`'s ~1000-entry cap** was a real, not just latent,
  limitation — see finding #3's corrected writeup. Fixed via
  `filings.files[]` pagination; `validate_universe()` now guards against a
  regression.
- **The 4 unresolved-to-exhibit earnings 8-Ks** (BAC, GS, CVX×2) are
  genuine "no exhibit filed" cases, not a bug — confirmed by manual
  inspection of their filing index pages, and by the parser's own
  `primary_document`-presence assertion not raising for any of them.
- **HD's `recent_activity` FATAL (original Week 1 threshold)** was a real,
  non-buggy finding (a healthy company having an ordinary quiet filing
  period, not an entity that's stopped filing) that happened to land 2 days
  over the then-45-day threshold — see the `validate_universe()` section
  above. **Resolved in the Week 2 corrective pass:** threshold recalibrated
  to 80 days off the real 3-year gap distribution (max observed 70 days,
  SLB) and downgraded to WARN; HD no longer trips anything under the new
  threshold, and no override is needed for it.
- **`--allow-incomplete-universe` blanket-override bug (Week 2 corrective
  pass):** the flag used to downgrade every FATAL for a run, not just the
  one the caller intended to accept — fixed to take an explicit,
  comma-separated list of check names; see the `validate_universe()`
  section above.
- **Scope check:** this pull stayed within 25 companies / 12 quarters, both
  inside the `DISCOVERY.md` §3 bounds (20–30 companies, 8–12 quarters). No
  expansion was made or considered necessary. The pagination fix pulls in
  *more history for the same 3 companies*, not more companies or a longer
  window — not a scope expansion.

---

# Ingestion Notes — Week 2 (`extract.py`)

Covers `extract.py` and `data/filings.parquet`. Read alongside `DISCOVERY.md`
(§1, §3, §5), `ROADMAP.md` (Week 2), and the Week 1 notes above (this
module reuses `filings`/`filing_documents` from Week 1 without re-resolving
anything). This section was written retroactively during the Week 2
corrective pass (see "MD&A 'incorporated by reference' stub bug" below) —
`extract.py`'s module docstring already pointed here before this section
existed; that's fixed now.

## Why TOC anchors, not a heading regex, are the primary location strategy

The first approach tried was the obvious one: regex-match "Item 7." /
"Item 1A." as a heading, then take the span up to the next item heading. It
produced badly wrong results on real filings and was abandoned as the
*primary* strategy (kept only as a last-resort fallback, see below) for a
specific, confirmed reason: **forward-looking-statements boilerplate and
other prose elsewhere in the document contains full cross-reference
sentences that a loose heading regex happily matches.** For example, "...as
described in Item 7 of this Form 10-K under the heading 'Management's
Discussion and Analysis'..." appears in ordinary risk-factor or business
prose, and a naive "longest span to the next heading-looking match" approach
can pick this false match over the real section if an unrelated large
section (e.g. Risk Factors) happens to sit between the false match and the
real one, making the false match's span look longer.

The fix: **modern EDGAR HTML filings almost universally include an
anchor-linked table of contents** — `<a href="#some_id">Item 7.</a>` near
the top of the document, and `<div id="some_id">`/`<a id="some_id">` (or
`name=`) immediately before the real heading, later in the document. This is
the exact mechanism the EDGAR web viewer itself uses for in-page navigation,
so it's filer/vendor-HTML-style-agnostic in a way pattern-matching heading
text is not. `find_toc_item_anchors()` walks every internal `<a
href="#...">` in the document, checks whether its enclosing table row (or
the previous sibling row, for filers that split the item number and title
across two rows — see the JPM/GS notes below) looks like a TOC entry, and
`locate_item_section_by_anchor()` takes the span from the first entry
matching the target item number to the next TOC entry with a *different*
item number. The tightly-scoped heading regex
(`locate_item_section_by_heading_regex`, gap between "Item N" and the
expected title capped at ~20 characters of whitespace/punctuation only —
enough for "Item 7.    Management's Discussion..." but not enough for a
prose cross-reference with several words in between) is kept as a fallback
for the minority of documents with no usable anchor-linked TOC at all
(confirmed real cause on COP/CVX/JNJ 10-Ks before the bare-number TOC row
fix below: those filers' TOC rows read "7. Management's Discussion..."
without the word "Item").

## The `lxml`-silently-returns-empty-text trap

`BeautifulSoup(..., "lxml")` was tried first for speed. It **silently
produces empty `.get_text()` output** for HTML fragments that start with a
dangling/orphan closing tag or an otherwise-malformed opening fragment —
which is *exactly* what the anchor-based slicing approach produces by
construction, since it deliberately cuts the raw HTML string starting right
after a marker `<div id="...">` tag, not at a well-formed document
boundary. `lxml`'s parser is strict enough to give up cleanly rather than
recover, and returns an empty tree instead of raising an exception.

This was **not caught by any exception** — it was caught by
`MIN_SECTION_CHARS`'s empty-text safety net silently rejecting every single
anchor-based extraction attempt and falling back to the lower-confidence
regex path, on every document, which looked like "the anchor strategy just
doesn't work" rather than "the parser is silently failing." Switching to
stdlib `"html.parser"` (no extra dependency, and confirmed to handle the
same malformed fragments correctly by recovering and treating the dangling
tag as a no-op) fixed it immediately. Kept as `_PARSER = "html.parser"` at
the top of `extract.py` with a comment, specifically so a future
speed-motivated switch back to `lxml` doesn't silently reintroduce this.

## UNH false-match: "Note 2. Investments" mistaken for "Item 2. MD&A"

UNH's Notes-to-Financial-Statements sub-index numbers each note "1.", "2.",
"3." etc. **with no "Note" prefix** — in exactly the same bare
`"N. Title ... pagenum"` shape as a real Item TOC row (`_ITEM_LABEL_BARE_NUM_RE`
matches both). This sub-index appears **before** the real "Item 2.
Management's Discussion and Analysis" entry in document order (nested under
Item 1 Financial Statements in a 10-Q). Without a keyword check, "first TOC
entry with `item_no == '2'`" silently matched **"2. Investments"** — a
balance-sheet footnote, not MD&A — and returned it as a confident,
high-confidence "MD&A" extraction. This was **not caught by any automated
check**; it surfaced only when the owner's sample review (10-15 extracted
sections) happened to include a UNH row and the content obviously wasn't
MD&A prose.

Fix: `locate_item_section_by_anchor()` takes an optional `required_keywords`
tuple and additionally requires the matched TOC entry's row text to contain
at least one of them (case- and whitespace-insensitive on both sides — see
the JNJ letter-spacing note below for why whitespace-insensitivity matters
too) — `("discussion and analysis",)` for MDA, `("risk factor",)` for Risk
Factors. This is **not optional** for numeric-only item numbers like `"2"`
specifically because of this exact UNH case; item numbers with a letter
suffix (`"1A"`, `"7A"`) are far less likely to collide with a footnote
index, but the keyword check is applied unconditionally rather than only
for numeric-only items, since there's no guarantee some other filer doesn't
have an equivalent collision for a lettered item too.

## GS (3-row split title) and JNJ (letter-spacing markup) TOC edge cases

- **Goldman Sachs splits a single TOC entry across up to three consecutive
  table rows**, with the actual `<a href="#...">` living on the *middle*
  row: `"Item 7"` / `"Management's Discussion and Analysis of Financial
  Condition"` / `"and Results of Operations 62"`. A title-keyword check
  against only the anchor's own row text would see "Item 7" with no title
  words at all, and wrongly reject a perfectly real entry. Fixed by widening
  each `TocEntry`'s `row_text` to include up to `_TOC_CONTEXT_ROWS_AFTER`
  (3) *following* sibling rows, not just the matched row itself, before the
  keyword check runs.
- **JNJ's real 10-K TOC renders with letter-spacing markup** — the text
  literally reads `"management's d iscussion and a nalysis"`, with stray
  spaces inserted mid-word (an artifact of how JNJ's filing-generation
  vendor renders letter-spaced headings in HTML/CSS). A plain substring
  check for `"discussion and analysis"` never matches text with spaces
  injected mid-word. Fixed by comparing with **all whitespace stripped from
  both sides** of the comparison (`re.sub(r"\s+", "", ...)` on both the
  candidate row text and each required keyword) — `"discussionandanalysis"`
  matches `"discussionandanalysis"`-shaped text regardless of where the
  stray spaces landed.
- Separately (not JNJ-specific, but discovered alongside it): **JNJ's real
  10-K also drops the trailing period inconsistently within the same
  document** — "1A. Risk factors 9" keeps the period, but "7 Management's
  discussion... 22" drops it for the plain-numbered item specifically. This
  is why `_ITEM_LABEL_BARE_NUM_RE`'s period is optional (`\.?`) rather than
  required.

## 45 genuine Item 1A omissions — filer practice, not an extraction bug

45 of 299 10-Qs (**ABBV, GS, JNJ, MRK, XOM — 9 quarters each**) genuinely
have no Item 1A Risk Factors section in the document at all.
`extract_item_section()` correctly returns `None` for these rather than
guessing — confirmed by reading the raw filings directly, not inferred from
the extraction failing: these filers cross-reference the prior 10-K's Risk
Factors ("no material changes from the risk factors disclosed in our [year]
Form 10-K") or omit the item entirely when there's nothing new to disclose,
which Reg S-K explicitly permits. This is **normal, compliant filer
practice, not an extraction failure**, and is reported as such — per
company, not folded into a single pass/fail coverage percentage that would
misrepresent these as broken extractions. See `ROADMAP.md`'s Week 2 DoD for
the same reasoning.

A related, actively-dangerous failure mode was found and avoided while
building this: falling back to the heading regex when the anchor-linked TOC
exists but simply doesn't list Item 1A is **not safe**, even though it
sounds like a reasonable "try harder" fallback. On XOM's 2023-10-31 10-Q,
the *only* "Item 1A" text in the whole document was a compact
cross-reference sentence ("...Item 1A. Risk Factors of ExxonMobil's 2022
Form 10-K.") immediately followed, in the same paragraph, by the start of
the unrelated Item 1 Legal Proceedings text. The heading regex would have
silently merged the two into a single plausible-looking but wrong "Risk
Factors" section. `extract_item_section()` explicitly returns `None` in
this case (a working, non-empty TOC that just doesn't list the target item)
rather than falling through to the regex — better to correctly report "not
present" than to return confidently-wrong merged content.

A related, but NOT buggy, short-content case surfaced during the Week 2
corrective pass's general length-floor check (see below): several
companies (**MA, OXY, COP, MCD, ...**) satisfy 10-Q Item 1A with a single
short, fully compliant sentence — *"For a discussion of our risk factors,
see Part I, Item 1A - Risk Factors of our 2024 Form 10-K."* (24-31 words).
This is genuinely different from the 45 omissions above (there the section
is *absent*; here it's *present but points at a different, earlier filing*)
and is also genuinely different from the MD&A stub bug below (there the
reference points at content in the *same* document, recoverable; here it
points at a *different* filing, nothing to recover). Both are legitimate,
Reg-S-K-permitted filer practice — flagged by the new length floor for
visibility, not treated as a bug to fix.

## MD&A "incorporated by reference" stub bug, and its resolution (Week 2 corrective pass)

**The bug (found by a second Opus-tier review, not by the original Week 2
sample review):** CVX, XOM, and JPM's 10-Ks don't write Item 7 inline —
each writes a **one-sentence pointer** instead, and the real, substantive
MD&A text lives elsewhere in the *same* primary document:

- CVX: *"The index to Management's Discussion and Analysis of Financial
  Condition and Results of Operations is presented in the **Financial Table
  of Contents**."*
- XOM: *"Reference is made to the section entitled 'Management's Discussion
  and Analysis of Financial Condition and Results of Operations' in the
  **Financial Section** of this report."*
- JPM: *"Management's discussion and analysis ... entitled 'Management's
  discussion and analysis,' appears on **pages 46–160**."*

The anchor-based extractor correctly located the Item 7 → Item 7A span and
correctly extracted exactly what's there — it had no way to know from the
anchor match alone that "what's there" is a pointer, not the content. The
result (242–395 characters, 36–53 words) cleared `MIN_SECTION_CHARS` (30)
easily and was stored as `extraction_method='anchor',
extraction_confidence='high'` — confidently wrong on both counts. 9 of 75
10-K MD&A rows (3 companies × 3 years) were affected; those 3 companies had
**zero usable MD&A text** for fine-tuning/labeling purposes going into
Week 3, which is why this was fixed before Week 3's labeling corpus is
built, not left for later.

**The fix, in two parts:**

1. **Stub detection.** A 10-K MD&A extraction is treated as a stub
   candidate — never trusted as `high` confidence at face value — when it's
   both short (`< MDA_STUB_WORD_CEILING = 1,500` words; the smallest
   genuine 10-K MD&A anywhere in this universe is 2,441 words, AAPL, so
   1,500 leaves a wide margin on both sides of the 36-53-word real stubs)
   **and** contains reference-language phrasing (`"incorporated by
   reference"`, `"reference is made to"`, `"is presented in"`, `"appears on
   page(s)"`, `"the index to"` — `STUB_REFERENCE_LANGUAGE_RE`).
2. **Real-content resolution**, tried in order (`resolve_incorporated_by_reference_mda()`
   in `extract.py`):
   - **Strategy 1 — anchor hop** (`resolve_mda_via_anchor_hop`): CVX's and
     XOM's most recent filing format embed an actual `<a href="#...">`
     inside the pointer sentence. Following it lands either directly on the
     real heading (XOM's newest filing) or on a **secondary** "Financial
     Table of Contents"/"Financial Section" index page that itself links to
     the real heading (CVX, all 3 years — a second-level TOC, separate from
     the document's main Item-number TOC, listing sub-headings like "Key
     Financial Results", "Results of Operations", "Liquidity and Capital
     Resources"). Handled by hopping up to 3 anchor references deep, at
     each hop checking whether the landing region still looks like another
     index (has its own further MD&A-labeled link) or real content (starts
     with the MD&A heading text).
   - **Strategy 2 — text heuristic** (`resolve_mda_via_text_heuristic`),
     used only when strategy 1 finds no hyperlink at all in the pointer
     sentence — confirmed real case: XOM's 2024/2025 10-Ks and all 3 of
     JPM's, where the pointer is a bare page-number reference with no link.
     Scans the whole document's plain text for a standalone MD&A heading
     line, excluding both the Item 7 stub occurrence itself and any
     TOC-listing row (heading immediately followed by a bare page number).
     **A real false-positive this had to be excluded, found while
     building/testing this:** CVX's Item 1 Business section contains the
     sentence *"...some of which are also discussed in the section
     Management's Discussion and Analysis of Financial Condition and
     Results of Operations, are presented below."* — same heading words,
     but a grammatically-continuing mid-sentence clause, not a real
     heading. Excluded via `_prev_line_looks_like_heading_boundary()`,
     which requires the line immediately preceding a heading candidate to
     be blank, a lone running-header page number, or the end of an
     unrelated sentence (terminal punctuation) — the false-positive's
     preceding line ends mid-clause with no terminal punctuation, so it's
     correctly rejected. (CVX resolves via strategy 1 in practice and never
     reaches this fallback, but the guard is written generally rather than
     assuming a future similar filer will always have a hyperlink to hop
     through.)
   - **End boundary, both strategies:** `_slice_to_next_audit_report_heading()`
     scans forward from the resolved start for the first *real* "Report of
     Independent Registered Public Accounting Firm" heading (a near-
     universal 10-K heading immediately preceding the financial
     statements, distinguished from a TOC-listing mention of the same
     phrase by checking the text immediately following it for
     audit-opinion language like "To the Board of Directors"). Confirmed
     present, in this exact position, in all 9 known stub filings.
   - Successful resolution: `extraction_method='incorporated_by_reference_resolved'`,
     `extraction_confidence='medium'` (not `'high'` — this is a
     heuristic-located secondary section, not the same TOC-anchor-verified
     certainty as a normal `anchor` extraction, even though the content
     itself was manually verified as real and substantive for all 9
     filings — see the outcome table below).
   - If resolution fails: the original short stub text is **kept**, but
     marked `extraction_method='incorporated_by_reference_unresolved'`,
     `extraction_confidence='low'` — never silently left at `'high'`. (Did
     not occur for any of the 9 known filings after the fix; documented as
     the explicit fallback in case a future filing hits it.)

**Outcome (re-ran extraction after the fix, all 9 previously-stub filings):**

| Ticker | Filing | Words (real) | Method |
|---|---|---|---|
| CVX | FY2023 10-K | ~14,900 | `incorporated_by_reference_resolved` (anchor hop) |
| CVX | FY2024 10-K | ~15,600 | `incorporated_by_reference_resolved` (anchor hop) |
| CVX | FY2025 10-K | ~15,300 | `incorporated_by_reference_resolved` (anchor hop) |
| XOM | FY2023 10-K | ~17,700 | `incorporated_by_reference_resolved` (text heuristic) |
| XOM | FY2024 10-K | ~18,200 | `incorporated_by_reference_resolved` (text heuristic) |
| XOM | FY2025 10-K | ~17,700 | `incorporated_by_reference_resolved` (anchor hop) |
| JPM | FY2023 10-K | ~64,600 | `incorporated_by_reference_resolved` (text heuristic) |
| JPM | FY2024 10-K | ~60,800 | `incorporated_by_reference_resolved` (text heuristic) |
| JPM | FY2025 10-K | ~59,800 | `incorporated_by_reference_resolved` (text heuristic) |

All 9 resolved to real, substantive content (manually spot-checked: each
starts with the genuine MD&A heading and, for CVX/XOM, "Key Financial
Results"/"Forward-Looking Statements" content, and ends at the CEO/CFO
internal-controls-certification signature block that immediately precedes
each company's real audit report). **Zero unresolved** — CVX, XOM, and JPM
all now have real MD&A text for all 3 of their 10-Ks; the "3 companies with
zero usable MD&A" gap going into Week 3 is closed.

## General length-floor plausibility check (the class of bug this was one instance of)

`MIN_SECTION_CHARS = 30` catches a *literally empty* extraction, but a
242-character stub sentence clears it trivially — the actual bug class is
"a short extraction that superficially looks successful (non-empty, above
the char floor, matched via the normal anchor path) but isn't the real
content." The general fix: a per-`(form_type, section_type)` minimum
**word** count floor (`MIN_SECTION_WORDS` in `extract.py`), calibrated off
the real word-count distribution across the whole universe (not guessed),
below which an extraction is **flagged for review** (a `below_length_floor`
column in `data/filings.parquet` and a dedicated report at the end of
`extract.py`'s `run()`) rather than silently trusted. This is a visibility
mechanism, not a rejection — see the 10-Q Risk Factors note above for a
case where "below floor" turned out to be legitimate on inspection, not a
bug, and was documented as such rather than "fixed" (there's nothing to
fix; nothing is being incorporated by reference from within the same
document there).

---

# Ingestion Notes — Week 3 (`chunk.py`)

> **⚠️ Written retrospectively on 2026-08-18, not during Week 3.** The Week 1
> and Week 2 sections above were written while (or immediately after) that
> work happened; this one was not. It reconstructs Week 3 from the artifacts
> that survive — `chunk.py`'s code and module docstring, the two output
> parquets, `REDTEAM_WEEK3.md`'s independent queries against them, and
> `HANDOFF.md` §3's dated decision log. Treat it as an accurate summary of
> *what the code does and what was later found*, not as a contemporaneous
> record of what was tried and discarded in the moment. Where a number
> exists only as a runtime `print()` and was never written down anywhere,
> it is flagged as unrecorded below rather than reconstructed.
>
> This section was added 2026-08-18 to close a gap that `README.md` and
> `HANDOFF.md` §8 had both flagged — this notebook covered Weeks 1–2 only
> and had no `chunk.py` section (those flags were removed once this section
> landed, so grepping for their wording finds nothing). It also exists
> because `chunk.py`'s own docstring points at "the chunking report" for
> verification numbers — **a file that does not exist in this repo.** That
> dangling reference is a real gap, recorded here rather than quietly
> papered over.

Covers `chunk.py`, `data/labeling_corpus.parquet`, and
`data/paragraph_occurrence_map.parquet`. Read alongside `DISCOVERY.md` §2
(labeling strategy) and §5 (evaluation design + the 2026-08-11
label-attribution amendment), `ROADMAP.md`'s "History (Weeks 1–3)" section
(the roadmap was rewritten into a Phase A–E structure on 2026-08-11 and no
longer has week-numbered sections), and the Week 2 notes above (this module
consumes `data/filings.parquet` and re-derives nothing from EDGAR — no
network calls at all).

## What `chunk.py` does, in four stages

Input: `data/filings.parquet` (884 rows, one per (company, filing,
section)). Output: ~350-word prose windows suitable as a single labeling
unit. Constants live at the top of the file: `MIN_PROSE_WORDS = 40`,
`TARGET_WINDOW_WORDS = 350`, `MIN_FLUSH_WORDS = 100`.

1. **Prose filter.** Split each section's text on `\n` — `extract.py` emits
   one paragraph/table-cell/bullet per line — and keep only lines with
   **≥ 40 words**. This is the table-noise filter: `get_text()` explodes
   HTML tables into one-word-per-line fragments, and a word-count floor
   drops that cleanly without needing table-structure parsing. (The
   docstring says this threshold was verified against real data, "see the
   chunking report" — that report does not exist; the verification numbers
   behind the choice of 40 are **unrecorded**.)

2. **Global exact dedup, with a deterministic "home" occurrence.** Each
   prose paragraph is normalized (whitespace-collapse + lowercase, in
   `normalize_paragraph()`) and deduplicated **across the entire corpus**,
   not within a filing. Every unique normalized paragraph becomes one
   `CanonicalParagraph` with a stable id `P-<sha1(normalized)[:16]>`.

   Exactly one occurrence is designated the **home** — the one actually
   packed into a window and therefore the one that gets labeled — chosen by
   a fixed, documented sort key: `(filing_date, ticker, accession_number,
   section_type, position)`, i.e. **earliest filing date wins**. Every
   other occurrence is still recorded in the occurrence list.

   The motivation is cost and non-duplication: a piece of boilerplate that
   recurs across three years of 10-Ks is labeled once, not three times. The
   consequence is the coverage gap two sections below.

3. **Window packing.** Within each (accession, section_type) instance, walk
   *that section's home paragraphs* in original document order and
   accumulate until the running word count reaches 350, then flush a chunk.
   A single paragraph longer than 350 words becomes its own chunk
   immediately. A leftover partial window at section end is flushed only if
   it has **≥ 100 words**; anything smaller is **dropped and never
   labeled**. Each chunk gets a content-derived id
   `CHK-<sha1("|".join(paragraph_ids))[:16]>`, so both id spaces are
   reproducible from content alone — re-running `chunk.py` on the same
   input regenerates identical ids.

4. **Output**, two files:
   - **`data/labeling_corpus.parquet` — 6,747 chunks.** One row per chunk:
     `chunk_id`, `section_type`, `text`, `word_count`, `n_paragraphs`,
     `paragraph_ids`, the `home_*` provenance columns (ticker, cik,
     accession, form, filing_date), and list columns `source_tickers` /
     `source_accession_numbers` / `source_filing_dates` / `source_forms` /
     `n_source_filings` — the union of every filing any constituent
     paragraph appears in anywhere in the corpus. Those `source_*` columns
     are the raw material for every-occurrence attribution, written at this
     stage specifically so a later step *could* expand a chunk back across
     every filing that contains its text.
   - **`data/paragraph_occurrence_map.parquet` — 28,504 rows.** Grain: one
     row per **canonical (deduplicated) paragraph**, each carrying
     `n_occurrences` and the full `occurrence_tickers` /
     `occurrence_accession_numbers` lists — see `build_paragraph_map_df()`.
     **The 42,577 total occurrences live inside those list columns**
     (`sum(n_occurrences)`), not as rows: **explode before joining**, or
     attributions under-count 42,577 → 28,504. `HANDOFF.md` §2's table
     states the same grain and the same two numbers. `REDTEAM_WEEK3.md`
     finding #3, querying the file directly, calls the same 28,504
     "canonical paragraphs" and reports **5,029** of them with
     `n_occurrences > 1`.
   - **Unrecorded:** the raw pre-dedup occurrence total and the corpus-wide
     dedup rate are printed by `run()` at execution time but were never
     captured in any file in this repo. Do not infer them from 28,504 —
     that is the post-dedup count.

**Output composition (labeled rows; derived from existing records, not a
fresh measurement):** `data/full_run_report.md`'s FINAL section gives
sentiment-by-section counts summing to MDA 3,961 / EX99_PRESS_RELEASE
1,171 / 8K_BODY 8, and `HANDOFF.md` §2 records 1,606 RISK_FACTORS rows that
carry no sentiment by design (RISK_FACTORS is never asked for sentiment,
per the applicability matrix). Those add to the 6,746 labeled rows; the
6,747th is the excluded refusal chunk. `8K_BODY`'s n=8 comes from only 2 of
25 tickers (BAC, CVX) — a direct consequence of the Week 1 finding that
only 4 earnings 8-Ks in this universe have no EX-99.x exhibit.

## The coverage gap the dedup design created, and the decision it forced

`REDTEAM_WEEK3.md` finding #3 measured the downstream effect of "label the
home occurrence only," joining `data/filings.parquet` against
`data/labeling_corpus.parquet` on `(accession_number, section_type)`:

```
total filing-sections:            884
sections with >=1 home chunk:     734
sections with ZERO home chunks:   150   (17.0%)

  RISK_FACTORS:        118/254 = 46.5%
  8K_BODY:               1/4   = 25.0%
  EX99_PRESS_RELEASE:   29/327 =  8.9%
  MDA:                   2/299 =  0.7%
```

Nearly half of all Risk Factors filing-sections contribute no chunk
anchored to their own filing date — not because the filer said nothing, but
because that year's risk-factor language was identical (after
normalization) to an earlier filing's and was therefore attributed to the
earlier filing.

Two things about this were checked rather than assumed:

- **It is not a look-ahead leak.** Home is always the *earliest* occurrence,
  verified empirically: across all 5,029 multi-occurrence paragraphs, the
  home occurrence's date equals the true minimum occurrence date — **0
  mismatches**. So labeled text never post-dates a filing it recurs in; the
  direction of information flow is safe. The red-team explicitly confirmed
  the mechanism is genuinely earliest-by-date, not "first encountered in
  iteration order" by accident.
- **It is a coverage bias with a real Phase C failure mode.** A naive join on
  `home_accession_number` / `home_filing_date` would make ~46% of Risk
  Factors sections silently show "no risk-factors signal," which reads as
  missing data or (worse) gets imputed as "no red flags," when the correct
  reading is "same boilerplate as last year."

**Decision it forced — owner-ratified 2026-08-11 (`HANDOFF.md` §3;
`DISCOVERY.md` §5 amendment): every-occurrence label attribution.** A
paragraph's label attributes to *every* filing it appears in, not only its
home filing, implemented against
`data/paragraph_occurrence_map.parquet`. Point-in-time safety is preserved
because each occurrence carries its own real filing date and a filing
receives the label only from its own public-availability date onward — no
information flows backward. This is a coverage fix, not a look-ahead
shortcut, and it is binding on `features.py`.

Worth stating plainly, since it is the whole reason this section matters:
the coverage gap was **not** discovered by `chunk.py`'s own output checks.
It was found by an independent red-team query against the artifacts a week
later. Nothing in the chunking step reported "150 of your 884 sections
produced zero chunks," and it should have.

## Other Week 3 red-team findings that touch chunking

Full text in `REDTEAM_WEEK3.md`; summarized here because they are
properties of the *corpus this file builds*, not of the labeling step.

- **Finding #2 — residual self-identification (open).** Measured against
  `data/labeling_corpus.parquet` itself: the chunk text names its own
  company in **26.8%** of chunks by a strict method (full/near-full legal
  name as a phrase; exact whole-word ticker, excluding ambiguous
  1–2-letter tickers V/MA/GS) and **46.0%** by a loose one (company-name
  first token or bare ticker anywhere). Section breakdown, strict method:
  8K_BODY 75.0 / EX99_PRESS_RELEASE 59.2 / MDA 19.9 / RISK_FACTORS 19.9.
  Both figures are cited together on purpose, so no later doc picks one and
  implies the other was wrong. Chunking cannot close this channel — full
  redaction of identifying language was considered and deliberately not
  attempted for the MVP (nontrivial, and a real risk of corrupting content
  the way earlier naive text-surgery attempts did). Mitigated only by the
  rubric's §0 instruction not to use recognized identity; watched, not
  solved.
- **Finding #4 — red-flag modality is confounded with `section_type`
  (open, forward-looking).** RISK_FACTORS skews HYPOTHETICAL, MDA skews
  REALIZED, by large margins. This is a property of what each section type
  *is*, and it means a raw "count of red flags in this filing" feature
  would substantially measure how much Risk Factors boilerplate a filer
  includes — near-constant per filer, not a time-varying signal.
  **Caveat on that finding's numbers:** they are **pre-relabel** (they
  match `data/labels_pre_relabel.parquet`). The current post-relabel counts
  are RISK_FACTORS HYPOTHETICAL 2,049 / REALIZED 706 and MDA HYPOTHETICAL
  958 / REALIZED 2,733 (`HANDOFF.md` §6 Step 3). Recompute against the
  final corpus before use, and normalize red-flag features by section
  composition rather than pooling raw counts across section types.
- **Finding #7 — `8K_BODY` (n=8, 2 tickers) is not evaluable.** A corpus
  composition fact, inherited straight from the 4 no-exhibit earnings 8-Ks
  in the Week 1 notes above. Exclude it from headline metrics and say why.
- **Checked and found fine:** no ticker/company_name/filing_date and no
  literal `section_type` text leaks into the labeling requests built from
  this corpus (0 hits across all 6,747 requests) — the only identity
  channel is the organic one in finding #2.

## Known limitations / judgment calls for the project owner (Week 3)

- **Sub-100-word section remainders are silently dropped**
  (`MIN_FLUSH_WORDS = 100`). How much text this discards corpus-wide was
  never measured or recorded. Small by construction (at most one remainder
  per section instance), but unquantified.
- **Dedup is exact-match after whitespace/case normalization only.**
  Near-duplicate boilerplate that changed by one word between years is
  treated as two distinct paragraphs and labeled twice. No near-duplicate
  or fuzzy matching was attempted. The direction of this is conservative
  (over-labeling, not under-attribution), but it means the dedup rate
  understates how much of this corpus is effectively repeated text.
- **The 40-word prose floor is uncalibrated in the record.** It works — the
  table-fragment noise it targets is real and confirmed — but unlike
  `extract.py`'s length floors (calibrated off the observed distribution
  and written down), the evidence behind 40 was never captured in a file.
- **`chunk.py`'s docstring cites a "chunking report" that does not exist.**
  Either it was never written or never committed; this section is the
  closest thing to it, written retrospectively from the artifacts.
- **No automated output plausibility check.** `extract.py` gained a length
  floor and a review report after the stub bug; `chunk.py` has no
  equivalent — no per-section coverage report, no "did any section produce
  zero chunks" assertion. That absence is exactly what let the 17% / 46.5%
  coverage gap go unnoticed until an outside review looked for it.
