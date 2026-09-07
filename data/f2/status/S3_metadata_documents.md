# S3 completion report — metadata + documents ingestion at scale

**Stage:** S3. **Agent:** data-engineer (Opus). **Date:** 2026-08-24.
**Status: DONE.** Brief: `data/f2/status/S3_brief.md`.
**Scope implemented:** `data/f2/F2_SPEC.md` §4 (all of §4.1–§4.6) plus the
§8.2 "S3" test block, in a new test file.

**Network: ZERO live GETs.** Every measurement below was computed from files
already on disk through a cache-only `EdgarClient` subclass whose `_get()`
RAISES instead of fetching (`client.request_count == 0` printed at the end of
every harness run). No Anthropic API use. The one real-world test fixture is a
byte-identical copy of a file the S1 probe already cached — nothing was
re-fetched to build it.

**E1's frozen record is untouched:** `data/universe.csv` (Aug 10),
`data/labels.parquet` (Aug 11), `data/filings_metadata.db` (Aug 18) all carry
their pre-session mtimes. `data/universe.csv` is now *read* (read-only) for one
purpose: the `new_filer` flag in the EX-99 audit.

**Parallel-run coordination honoured:** `F2_PROGRESS.md` not edited;
`ingest_fundamentals.py`, `ingest_prices.py`, `price_client.py`,
`test_ingest_fundamentals.py`, `test_ingest_prices.py` not touched (they show
as modified in `git status` — that is S4/S5 working concurrently); the full
pytest suite was NOT run.

---

## 1. Test counts (exact)

| suite | result |
|---|---|
| `test_ingest_metadata_scale.py` (**new**, all S3) | **54 passed** |
| `test_ingest_metadata_universe.py` (S2's, re-run) | **45 passed** |
| `test_edgar_client_companyfacts.py` (suite for a file I changed) | **7 passed** |
| **total run** | **106 passed / 0 failed** |

`pyflakes` clean on all four changed/new Python files. No test opens a socket.
Nothing was deleted or weakened to make a suite pass — the four S2 assertions
that moved are all *widened pins on S3's own additions*, listed in §4.

## 2. Files touched

**New**

| path | what / why |
|---|---|
| `test_ingest_metadata_scale.py` | 54 offline tests: the §8.2 S3 block plus the enumeration-window reconciliation, distress extraction/idempotency, the EX-99 audit artifact + sector-coverage arms, co-registrant accounting, the whole `--stage` split, `document_cache_path` agreement with the client, and every `max_age_hours` path. |
| `data/f2/fixtures/filing_index_CIK0000018230_0000018230-16-000702.html` | The §8.2 CAT 2016 index fixture (8.4 KB). **Byte-identical copy** of `data/raw/filing_index/18230_000001823016000702.html` (sha256 `582488d3aad791b104b908b81493dcc6d7844cbfb527681bf7218e3f4a63e654`), captured by S1's probe, copied out of the gitignored cache so the test survives a cache clear. A test asserts the two stay identical (skips if the cache is gone). Lives in the same `data/f2/fixtures/` dir S4 is using; distinct filename, no collision. |

**Modified**

| path | what / why |
|---|---|
| `ingest_metadata.py` | All of S3. Module docstring rewritten around the `--stage` split (the E1 "no filing text is downloaded here" line is now scoped to `--stage metadata`, with the reason). `run()` split into `run()` (dispatch) + `run_metadata_stage()` + `run_documents_stage()`; `--stage {metadata,documents,all}` and `--cache-max-age-hours` added. New: `extract_distress_events()`, `write_distress_events()`, `summarize_distress_events()`, `load_e1_ciks()`, `build_ex99_audit()`, `write_ex99_audit()`, `earnings_doc_unresolved_problems()`, `check_ex99_sector_coverage()`, `coregistrant_problems()`, `print_ex99_audit_report()`, `archive_document_path()`, `document_cache_path()`, `document_prefetch_targets()`, `_spell_intervals()`/`_inside_any_spell()`. `select_earnings_document`/`resolve_earnings_document`'s `ticker=` parameter renamed to `subject=` (S2 flagged it; a ticker is not a key in E2). `validate_universe()` gained `max_age_hours`. Enumeration window reconciled to the shared corpus window — see §5. |
| `edgar_client.py` | **Only** the §4.3 passthrough: optional `max_age_hours` on `get_submissions`, `get_submissions_chunk`, `get_companyfacts`, and `get_effective_recent` (which threads it into both underlying reads, or the flag could not affect an enumeration pass). Default unchanged at 24 h; `filing_index/` and `documents/` stay cache-forever, pinned by a test. |
| `test_ingest_metadata_universe.py` | Four minimal edits, all forced by S3's own additions, all preserving the original intent — see §4. |

## 3. What was MEASURED this session (cache-only, 0 network GETs)

`run_metadata_stage()` was run end-to-end over the **real 244 members**
against a scratch DB with a raise-on-network client.

**Enumeration reproduces F2_SPEC §4.1's MEASURED table exactly:**

| | spec §4.1 | this run |
|---|---|---|
| 10-K | 2,452 | **2,452** |
| 10-Q | 7,532 | **7,532** |
| 8-K | 35,638 | **35,638** |
| total | 45,622 | **45,622** |
| 8-K with item 2.02 | 10,569 | **10,569** |

**Distress events reproduce §4.5's MEASURED table exactly:**

| event | spec | this run |
|---|---|---|
| Form 25 | 37 / 30 CIKs | **37 / 30** |
| Form 25-NSE | 510 / 131 | **510 / 131** |
| Form 15 (12B+12G+15D) | 65+22+32 = 119 | **119 / 67 CIKs** |
| 8-K item 1.03 | 2 / 1 (CIK 895126) | **2 / 1** |

Other real numbers from that run: 244 companies + 299 membership spells
written; observed max `filing_date` **2026-08-20** (vs the 2026-08-31 freeze
constant); ingested filings outside every membership spell of their own CIK
**20,216 of 45,622** (§4.2's binding condition — printed every run); the
pre-ingestion validation findings are unchanged from S2's (29 INFO
`member_stopped_filing`, 5 WARN `no_large_filing_gap`, 0 FATAL).

`--stage documents` target derivation against that DB and the real cache:
**10,289 unique targets** (2,445 10-K + 7,509 10-Q + 335 earnings docs),
**640 already cached → 9,649 would fetch**, 0 network GETs to compute. The
earnings-doc figure is low only because the harness could not fetch the ~9,929
uncached filing indices; a real S6 segment-1 run resolves ~10,569 of them.

Two harness-only artifacts of the raise-on-network client, *not* code faults:
10,234 `earnings_doc_unresolved` WARNs + the aggregate FATAL (only 335 of
10,569 filing indices are cached), 2 `ex99_sector_coverage` FATALs (same
cause), and 1 `cik_map_fetch` WARN (`company_tickers.json` is >24 h old and
`get_company_tickers()` deliberately has no TTL override — §4.3 names only the
three other endpoints).

## 4. The four edits to S2's test file, and why each was unavoidable

None weakens a check; each widens a pin onto S3's own additions.

1. `FakeClient.get_submissions` / `.get_effective_recent` gained
   `max_age_hours=None` — the §4.3 passthrough is now passed on every call.
2. `test_allow_incomplete_universe_flag_is_gone` pinned `run()`'s exact
   parameter set; `stage`, `max_age_hours` and `ex99_audit_path` were added.
   The load-bearing assertion (`allow_incomplete_universe` absent) is intact.
3. The same test pinned `FATAL_CHECK_NAMES` exactly; `ex99_sector_coverage`
   was added (§4.4 item 5).
4. `_fake_run()` now passes `ex99_audit_path=tmp_path/...`, and
   `test_validation_problems_are_persisted_with_no_exceptions_file` now scopes
   its exact-set assertion to the member's own rows. Both because S3 writes
   post-ingestion findings into the same `(run_date, stage)` slice — and
   because **a test must never overwrite the real
   `data/f2/ex99_selection_audit.csv`**, which is a real run's output. That
   path is now a parameter, and a test asserts a run never touches the repo
   copy.

## 5. Deviation from spec — ONE, argued and measured

**The enumeration window is the shared `[CORPUS_WINDOW_START,
CORPUS_WINDOW_END]`, not per-company `[coverage_start, coverage_end]`.**

F2_SPEC contains an internal contradiction on this point and I resolved it by
re-measurement rather than by picking the nearest sentence:

- **Against per-company clipping:** ruling §9.1(1)/§4.2 — *"ingest the full E2
  window for every CIK that is ever a member; do not clip fetches to
  membership spells"*; §2 names `CORPUS_WINDOW_START` the *"documents/metadata
  enumeration floor"*; every MEASURED count in §4.1 and §4.5; and §7's whole
  runbook budget (9,984 periodic primaries = 2,452 + 7,532).
- **For per-company clipping:** one prose sentence in §4.1
  (`coverage_start <= filing_date <= CORPUS_WINDOW_END`) and one line in
  §8.2's S3 test list. S2 implemented the clipped reading.

Measured both, on the real 244 members:

| enumeration filter | 10-K | 10-Q | 8-K | total | earnings 8-K | item 1.03 |
|---|---|---|---|---|---|---|
| **shared window** | 2,452 | 7,532 | 35,638 | **45,622** | **10,569** | **2** |
| `[coverage_start, coverage_end]` | 1,883 | 5,830 | 27,936 | 35,649 | 8,242 | **0** |
| `[coverage_start, CORPUS_WINDOW_END]` | 2,138 | 6,601 | 31,138 | 39,877 | 9,247 | **0** |

Only the shared window reproduces the plan of record — and the decisive item
is not the count, it is the **bankruptcy**: CIK 895126 (Expand Energy,
ex-Chesapeake) first qualifies as a member at 2026-07-01, so its
`coverage_start` is 2024-07-01 and its 2020-06-28 item-1.03 filing falls
outside its own window. Clipping loses the single most meaningful distress
event in the corpus, which EXPANSION_PLAN §2c makes it mandatory to ingest.
Clipping would also have made every S6 number disagree with F2_SPEC's own
tables — an S7 red-team blocker that costs a multi-hour re-run to fix, versus
+14% of already-budgeted GETs to be wide.

Per-company coverage windows are **unchanged everywhere else**: they still
govern all of §3.1's validation checks, are still written to `companies`, and
are printed beside the enumeration window on every per-company line. PIT safety
is unaffected (breadth never implies membership), and the §4.2 binding
condition is implemented and printed every run. Reverting is a two-argument
edit at one call site, and the reasoning is written into the
`CORPUS_WINDOW_START` comment block so nobody has to re-derive it.

## 6. New finding: 87 co-registrant filings (needs a ratification, not a fix now)

EDGAR lists **co-registrants on one accession** — a parent and its subsidiary
file a single 8-K together. `filings.accession_number` is the PRIMARY KEY
(E1's schema, which F2_SPEC §1.4 does not change), so when both filers are
members the second one's `cik` attribution is lost.

MEASURED over the real universe: **87 of 45,622 filings (0.19%)**, across
exactly three pairs — Dow Chemical (29915) / Dow Inc (1751788) **67**,
Williams Companies (107263) / Williams Partners (1483096) **16**, Exelon
(1109357) / Constellation (1868275) **4**. 30 of the 87 are 10-K/10-Q, which
is why the real document-prefetch budget is ~30 below §4.6's 20,553.

E1 never hit this (25 unrelated mega-caps). S3 does **not** change the key —
re-keying `filings` on `(accession_number, cik)` changes `filing_documents`'
parent key and F3's extraction grain, which is beyond S3's scope. Instead the
loss is now **counted and named**: one `co_registrant_filing` WARN per pair
(filed against the CIK whose attribution was lost, naming the keeper and a
sample accession), plus a run-summary line stating rows-stored vs
filings-enumerated. Behaviour is deterministic (the lowest CIK keeps the row,
because the universe iterates CIK-ascending). **For the main session / S7 to
rule on:** whether F5 may read a missing row as "this company did not file".

## 7. Deliberately NOT done, with the measurement behind it

- **F2_SPEC §3.3's second bullet (the doubled `get_effective_recent()`
  parse).** The spec conditions it on "only if S3 measures it as material".
  MEASURED 2026-08-24: 244 submissions documents = 0.05 GB / **0.2 s** to
  parse, plus 1,042 cached pagination chunks = 0.25 GB / **0.9 s** — about
  **1 second** against a 30–50 min segment, and **0 extra network requests**
  either way. Not material; left alone rather than changing
  `validate_universe()`'s contract for it. The measurement is recorded in that
  function's docstring so it is not re-litigated.
- **Re-keying `filings`** (§6 above) — reported, not decided.
- **The §4.4 item-4 manual EX-99 read** — that is an S6 human task by the
  brief's own scoping. What S3 built is the artifact plus the worklist: the run
  prints how many CIKs need the read and names the 20 worst by low-confidence
  count, stating the cap and the untouched remainder honestly.
- **Docs** (`INGESTION_NOTES.md`, `README.md`) still describe the E1 command
  shape. Flagged for the F2 report / S7, not rewritten here.

## 8. Interface changes S4/S5/S6/F3 must know

- `ingest_metadata.run(force_refresh, db_path, exceptions_path, stage,
  max_age_hours, ex99_audit_path)`; `stage` defaults to **`metadata`**, so a
  bare `python3 ingest_metadata.py` costs what it always did and the ~26 GB
  document walk is opt-in. F2_SPEC §7's runbook names the stage explicitly
  anyway, so no runbook line changes.
- `run_metadata_stage(client, conn, run_date, ...)` and
  `run_documents_stage(client, conn, run_date, force_refresh=False,
  progress_every=500) -> list[ValidationProblem]` are separately callable.
- `EdgarClient.get_submissions / get_submissions_chunk / get_companyfacts /
  get_effective_recent` take `max_age_hours` (default 24 h). **S4 can use it
  on `get_companyfacts` for a cheap re-run;** there is deliberately no
  `--cache-max-age-hours` on `ingest_fundamentals.py` — that file is S4's.
- `select_earnings_document(..., subject=...)` / `resolve_earnings_document(...,
  subject=...)` — the parameter was `ticker`.
- New DB content: `distress_events` is populated; `universe_validation_problems`
  carries `stage='documents'` rows and the new check names
  `earnings_doc_unresolved`, `ex99_sector_coverage`, `co_registrant_filing`,
  `document_fetch_failed`.
- New artifact: `data/f2/ex99_selection_audit.csv`
  (`cik, name, sector, stratum, new_filer, section_type,
  selection_confidence, n_filings, first_seen_year`). It does **not** exist
  yet — it is a real run's output, written by S6 segment 1. Nothing in the test
  suite writes to that path.
- A metadata run can now exit 1 *after* writing filings, on a post-ingestion
  FATAL (`earnings_doc_unresolved` >1%, or `ex99_sector_coverage`). The message
  says so explicitly: the rows ARE written, the corpus is just not fit to
  consume as-is, and re-running is cheap and idempotent.

## 9. Resume instructions

**Nothing is left partial.** To re-verify from scratch (all offline):

```bash
cd /Users/vihanpatil/personal/projects/FinScreen
python3 -m pytest test_ingest_metadata_scale.py -q          # expect 54 passed
python3 -m pytest test_ingest_metadata_universe.py -q       # expect 45 passed
python3 -m pytest test_edgar_client_companyfacts.py -q      # expect 7 passed
python3 ingest_metadata.py --help                           # --stage, --cache-max-age-hours
```

To re-derive §3's real-data numbers with **zero** network requests, run
`run_metadata_stage()` against a scratch DB with a subclass of `EdgarClient`
whose `_get()` raises, `max_age_hours=None`, and `ex99_audit_path` pointed at
scratch. That harness is ~20 lines and was deliberately kept out of the repo —
it is a measurement tool, not pipeline code.

**Operational note for S6 segment 1:** `data/raw/submissions/` is past its 24 h
TTL, so segment 1 will legitimately re-fetch 244 submissions documents plus
their pagination chunks (~0.5 GB, ~10 min) before doing anything else — F2_SPEC
§4.3's documented behaviour. `--cache-max-age-hours 168` is now the lever if a
cheaper re-run is ever wanted, at the cost of accepting the corpus as of the
cached fetch (sound, because the corpus window is fixed).

---

## 10. Follow-up — 2026-08-24 (after the main session's two rulings)

Both items S3 raised were ruled on in `F2_PROGRESS.md` §5 (two dated
2026-08-24 entries). Read them, then did the following. **Still zero live
network GETs**; no sibling files touched; `F2_PROGRESS.md` not edited.

### 10.1 Window deviation — RATIFIED as implemented, no code change

The shared `[2015-07-01, 2026-08-31]` enumeration window stands; per-company
coverage windows continue to govern §3.1 validation only. No code changed.

**Recorded in the spec:** `data/f2/F2_SPEC.md` gained a new appended
**§11 "AMENDMENTS"** section (lines 824+; the original 823 lines are
byte-unchanged — verified, S1's text was never rewritten). Its first entry
names exactly what is superseded: §4.1's
`coverage_start <= filing_date <= CORPUS_WINDOW_END` prose and its
`get_effective_recent(cik, coverage_start(cik))` call shape, plus §8.2's S3
test line "Enumeration respects per-company `[coverage_start, coverage_end]`".
It carries the three-variant measurement table and the CIK 895126 bankruptcy
case, so a future reader does not have to re-derive the ruling.

### 10.2 Co-registrant finding — side table implemented

**New table** (in `init_db()`, so it exists in every E2 DB):

```sql
co_registrant_filings(accession_number, kept_cik, co_cik, form, filing_date)
PRIMARY KEY (accession_number, co_cik)          -- + index on co_cik
```

Populated during metadata enumeration, **one row per dropped attribution**
(not per pair), written per company right before that company's commit so a
killed run resumes consistently. `write_co_registrant_filings()` is
INSERT OR REPLACE, so re-running is idempotent. **Zero network cost** — the
data is a by-product of the same enumeration pass. The three per-pair
`co_registrant_filing` WARNs and the stored-vs-enumerated summary line are
unchanged and stay on top of it; the summary line now also names the side
table, the row count, the keeper rule, and the binding downstream rule.

**Keeper rule (deterministic, documented in a DDL comment + a loop comment +
pinned by two tests): the `filings` row is kept under the numerically LOWEST
member CIK on the accession.** This is the rule that was already in effect
(first-writer-wins over a CIK-ascending universe); it is now a *guarantee*
rather than an accident, because the ingestion loop explicitly iterates
`universe.sort_values("cik")` instead of trusting its caller's row order, and
the upsert never rewrites `cik`. `test_keeper_is_the_lowest_member_cik_
regardless_of_universe_row_order` feeds the universe HIGH-CIK-first and proves
the keeper is unchanged; `test_load_universe_is_cik_ascending` pins the source
ordering too.

**Side-table row count expectation on real data: exactly 87 rows**, re-measured
this session over the real 244 members (cache-only harness, `request_count ==
0`), and fully reconciled:

| check | result |
|---|---|
| `co_registrant_filings` rows | **87** |
| distinct accessions in it | 87 (each accession has exactly 2 member registrants) |
| by pair | 29915→1751788 **67**, 107263→1483096 **16**, 1109357→1868275 **4** |
| by form | 8-K **57**, 10-Q **23**, 10-K **7** |
| `filings` rows + side-table rows | 45,535 + 87 = **45,622** = the full enumeration |
| `kept_cik < co_cik` on every row | **true** (the keeper rule, on real data) |
| every `(accession, kept_cik)` present in `filings` | **true** (no dangling side-table row) |

**BINDING DOWNSTREAM RULE — restated here as required, and written into the
DDL comment, `coregistrant_problems()`'s docstring, the run-summary line, and
F2_SPEC §11:** absence from `filings` alone is **never** evidence a company
did not file. Any per-company filing or coverage question must consult
`filings` ∪ `co_registrant_filings`, and F5's accession → company attribution
must yield **both** member CIKs for these 87 accessions. That attribution work
is F5's; S3's job was only to make the relation exist, which it now does.
`test_side_table_and_filings_together_answer_the_coverage_question` encodes
the contrast directly: the naive `filings`-only query returns "did not file"
for the co-registrant, the UNION query finds the filing.

### 10.3 Test counts after the follow-up

| suite | before | after |
|---|---|---|
| `test_ingest_metadata_scale.py` | 54 | **60** (+6) |
| `test_ingest_metadata_universe.py` | 45 | **45** |
| `test_edgar_client_companyfacts.py` | 7 | **7** |
| **total** | 106 | **112 passed / 0 failed** |

The six new tests: one-filings-row-plus-one-side-table-row for a synthetic
two-member co-registered accession; the keeper rule under a reversed universe
row order; zero side-table rows (and zero WARNs) for single-registrant
accessions; the `filings` ∪ `co_registrant_filings` coverage query; side-table
write idempotency; and `load_universe()` CIK-ascending. `pyflakes` clean.

### 10.4 Files touched in the follow-up

| path | what |
|---|---|
| `ingest_metadata.py` | `co_registrant_filings` DDL + `co_cik` index; `write_co_registrant_filings()`; per-company population in the enumeration loop; explicit `sort_values("cik")` to make the keeper rule a loop property; keeper-rule and binding-rule comments; summary line extended. |
| `test_ingest_metadata_scale.py` | +6 tests (§10.3). |
| `data/f2/F2_SPEC.md` | **Appended** §11 AMENDMENTS with both dated rulings. Original 823 lines byte-unchanged. |
| `data/f2/status/S3_metadata_documents.md` | This §10. |

---

## 11. Follow-up — 2026-08-24 (the EX-99 manual-read fix package)

Implemented the six items the main session ruled IN (`F2_PROGRESS.md` §5,
"the EX-99 manual-read fix package"), after reading
`data/f2/status/S6_ex99_manual_read.md` in full. **Zero live network GETs**;
segment 1 was NOT re-run and the E2 DB was opened `mode=ro` only; no sibling
files touched; `F2_PROGRESS.md` not edited.

### 11.1 Step 1 — Prologis EX-99.2 content-confirmation: CONFIRMED, and cleaner than the read suggested

Scanned **all 45** Prologis earnings 8-Ks offline: every cached filing index
(45/45) plus every cached selected document (45/45).

| era | filings | EX-99.1 self-title | release language | handler fires? |
|---|---|---|---|---|
| 2015-07-21 … 2016-04-19 | 4 | "**Earnings Release and** Supplemental Information" | YES (all 4) | **no** |
| 2016-07-19 … 2026-07-16 | 41 | "Prologis Supplemental Information &lt;quarter&gt; Unaudited" | NO (all 41) | **yes** |

The split is a clean, dated title change at **2016-07-19**, not a size or
dialect drift. The read's "39 of 45" is **41 of 45**: its screen counted the
2018-01-23 and 2018-04-17 picks as carrying release language, and both, read in
context, are Supplemental documents whose guidance footnote merely *cites* "the
Press Release dated January 17, 2018". Every one of the 41 has an EX-99.2 row.

**Limit of the confirmation, stated plainly:** `data/raw/documents/` caches
only the *selected* document, so no EX-99.2 byte was read and none was fetched
(zero-GET constraint). The confirmation is by complement (the EX-99.1 is
provably not the release for all 41) plus the filer's own label
(`0001564590-19-036903`'s EX-99.2 description is literally "PRESS RELEASE,
DATED OCTOBER 15, 2019.", while EX-99.1's is the generic "EX-99.1"). Nothing
here was murkier than the read suggested, so I proceeded.

### 11.2 Expected pick-change count: **43, across exactly three filers**

Measured by replaying the new policy over every cached earnings-8-K index
(10,569 filings, 0 GETs) and diffing against the attempt-2 corpus:

| filer | changes | why |
|---|---|---|
| Prologis 1045609 | **41** | P2 handler: EX-99.1 → EX-99.2 |
| NVIDIA 1045810 | **1** | evidenced override → `q3fy20pr.htm` (the EX-95.1 typo) |
| AT&T 732717 | **1** | evidenced override → excluded (no release in the filing) |
| **everyone else** | **0** | P1 is confidence-only; P3/P5/P6 never pick |

Confidence: low **32 → 19**, high **10,521 → 10,533**, medium **16**
unchanged, excluded **1**. Decomposition of the 13 cleared low rows: 9 by P1
alone, 2 Prologis rows claimed by P2 (also P1-eligible), 1 NVIDIA and 1 AT&T by
override. P1 measured **in isolation** clears **11 of 32 with 0 pick changes**,
exactly as the ruling states.

### 11.3 P6 screen over the current corpus: **2 CIKs flag pre-fix**

10,537 selections measured, 0 uncached (segment 2 has run), 243 CIKs.

| CIK | name | high/medium picks lacking release language | verdict |
|---|---|---|---|
| **1045609** | Prologis | **37 / 43 (86%)** | **the real defect** — the acceptance case, and note 37 of them are HIGH confidence |
| **1065280** | Netflix | **25 / 47 (53%)** | **benign, reported not suppressed** |

Netflix was read directly before reporting: every selection is the correctly
picked EX-99.1 "LETTER TO SHAREHOLDERS" (25k–37k chars, opening "Fellow
shareholders,"). The picks are right; Netflix does not write press-release
prose. The threshold was **not** loosened to hide it — that is the
threshold-loosening the ruling forbids. A human reads it once and moves on;
that is what a WARN is for.

### 11.4 TWO NEW DEFECTS the P3 WARN surfaced — reported, NOT auto-fixed

P3 fires **3 times** over all 10,569 earnings 8-Ks (raw 18, of which 15 are
news-release *header images*). One is the known NVIDIA case. The other two are
new, and both are **worse in outcome** than NVIDIA's:

- **ONEOK `0001039684-15-000073`** (2015-11-03): release typed `EX-95.1`; no
  EX-99 row exists at all, so the policy fell back to `8K_BODY` and selected
  the **8-K cover page — 3,179 characters of SEC boilerplate**. The manual read
  binned ONEOK benign.
- **Micron `0000723125-19-000172`** (2019-12-18): release typed `EX-99..1`
  (double dot); same fallback, **3,499-character cover page**. Not in the
  read's 36-filing screen at all.

Both are `8K_BODY`/**high** confidence, so neither the low-confidence trigger
nor the §4.4 worklist could have surfaced them. NVIDIA's blast radius stays
**n=1 for that filer**, but the *typo class* is **n ≥ 3 corpus-wide**.
I did not add override rows: the ruling says exactly two, and adding a third
and fourth is a ratification, not an implementation detail. **They need a
ruling** — the same `select_document` override shape resolves both.

### 11.5 P5: 50 thin selections (12 under 100 chars)

The read predicted 44/12. My implementation measures **50/12** over the same
population; the 12-under-100 figure matches exactly. The difference in the
1,500-char band is extraction detail — this screen HTML-entity-unescapes before
counting, so `&nbsp;`-heavy wrappers score lower than a tag-strip-only pass.
All 50 are `EX99_PRESS_RELEASE` selections. Reported as measured, not
reconciled to the read's number.

### 11.6 Files touched

| path | what |
|---|---|
| `ingest_metadata.py` | P1 `_exhibit_number_from_description()`/`_effective_exhibit_type()` + the confidence upgrade inside `resolve_duplicates`; P2 `_prologis_earnings_document()` + `PER_FILER_EARNINGS_HANDLERS` + `cik`/`filing_date` params on `select_earnings_document`/`resolve_earnings_document`; the override loader/applier/reporter + `RATIFIED_EARNINGS_DOC_OVERRIDES` + `earnings_doc_excluded_problems()`; P3 `press_release_typed_outside_ex99()` + its problems builder; P5/P6 `screen_selected_document()`/`screen_selected_documents()`/`release_language_problems()`; three new audit columns; exclusions removed from the unresolved rate and the sector-coverage denominator. |
| `data/f2/earnings_doc_overrides.csv` | **New.** Two evidenced rows, header comment carrying the columns, the actions and the why-this-file-is-tiny rule. |
| `data/f2/fixtures/` | **6 new index fixtures**, byte-identical copies of cached indices (Prologis ×3 spanning the split, NVIDIA, AT&T, ONEOK), verified against the cache by a test. |
| `test_ingest_metadata_scale.py` | +78 tests (§11.7). |
| `test_ingest_metadata_universe.py` | One line: `run()`'s parameter pin gains `overrides_path`; `_fake_run` routes overrides to a nonexistent tmp path so S2's tests stay hermetic. |
| `data/f2/F2_SPEC.md` | **Appended** AMENDMENT **A6**. Original text unrewritten. |

### 11.7 Test counts

| suite | before | after |
|---|---|---|
| `test_ingest_metadata_scale.py` | 60 | **138** (+78) |
| `test_ingest_metadata_universe.py` | 45 | **45** |
| `test_edgar_client_companyfacts.py` | 7 | **7** |
| **total** | 112 | **190 passed / 0 failed** |

Coverage per ruled item: P1 11 tests (incl. the zero-pick-change guarantee in
both directions), P2 7 (both sides of the 2016-07-19 boundary, the bare-EX-99
interaction with P1, scoped-to-Prologis-only, declines without an EX-99.2,
degrades safely without `cik`/`filing_date`), the override file 13 (every
load-time refusal, stale-override RAISE, dead-row report, end-to-end exclusion
through `run()`), P3 6, P5 5, P6 9, plus
`test_fix_package_changes_exactly_the_intended_picks_on_the_real_corpus` —
a real-corpus replay asserting the pick-change set is *exactly*
`{1045609: 41, 1045810: 1, 732717: 1}` and low 32 → 19 (skips if the
gitignored cache/DB are absent; runs in 2.4 s). `pyflakes` clean.

### 11.8 What the main session should know before segment 1 attempt 3

- The 43 pick changes mean **41 Prologis EX-99.2 documents and NVIDIA's
  `q3fy20pr.htm` are not in `data/raw/documents/` yet** — segment 2 will fetch
  ~42 new documents (and the 43 now-unselected ones stay cached, harmlessly).
- Because those documents are uncached at attempt 3, **P6 will report Prologis
  as UNMEASURED, not clean**, until segment 2 re-runs. That is the designed
  behaviour and is printed as such; the post-fix "does not flag" property is
  pinned by fixture tests, not by the attempt-3 log.
- `earnings_doc_unresolved` is unaffected (the AT&T exclusion is deliberately
  not counted in it), so the >1% FATAL arm still cannot fire on it.
- ONEOK and Micron (§11.4) will produce two `press_release_typed_outside_ex99`
  WARNs on every run until they are ruled on. That is intended: they are real
  defects, and a WARN that keeps firing is the correct state for an unresolved
  finding.

---

## 12. Follow-up — 2026-08-24 (ONEOK + Micron join the override file)

The two defects §11.4 reported were ruled IN (`F2_PROGRESS.md` §5, "ONEOK +
Micron join the earnings-doc override file"). **Zero live network GETs**;
segment 1 not re-run; E2 DB read-only; no sibling files; `F2_PROGRESS.md` not
edited. No other scope touched.

### 12.1 Final override file row count: **4**

`data/f2/earnings_doc_overrides.csv`, all four load-time validated against
`RATIFIED_EARNINGS_DOC_OVERRIDES`:

| accession | filer | action | document |
|---|---|---|---|
| `0001045810-19-000168` | NVIDIA | `select_document` | `q3fy20pr.htm` |
| `0001039684-15-000073` | ONEOK | `select_document` | `okeq32015earningsreleasenr.htm` |
| `0000723125-19-000172` | Micron | `select_document` | `a2020q1exhibit991-pres.htm` |
| `0000732717-19-000048` | AT&T | `exclude` | — |

Three typo-class `select_document` rows + one `exclude`. Each new row's
`evidence` field quotes both index rows verbatim (the cover page that WAS
selected and the release that was missed) and states that content verification
is the extraction-qa pass's job once segment 2 caches the document — the same
standard as the NVIDIA row, written into the row rather than assumed.

**The EX-99 type family was not widened.** `EX-95.1` and `EX-99..1` still fail
`_EX99_FAMILY_RE` and `_canonical_exhibit_type()`; a new test pins that.
Widening it would turn one filer's typo into a corpus-wide silent mis-pick
generator, which is the whole reason P3 is a WARN and the override file is the
resolution path.

### 12.2 Re-measured pick-change count: **45** (was 43)

Replay over every cached earnings-8-K index, 0 GETs:

| filer | changes |
|---|---|
| Prologis 1045609 | 41 |
| NVIDIA 1045810 | 1 |
| ONEOK 1039684 | 1 |
| Micron 723125 | 1 |
| AT&T 732717 | 1 (to excluded) |
| everyone else | **0** |

Confidence distribution is **unchanged** from the 43-change measurement — low
32 → 19, high 10,521 → 10,533, medium 16, excluded 1 — because both new rows
replace a HIGH-confidence pick with a HIGH-confidence one. Pinned by
`test_fix_package_changes_exactly_the_intended_picks_on_the_real_corpus`, which
now asserts the exact five-filer dict and `sum == 45`.

**P3 WARNs remaining on a re-run: 0.** All three hits it found now carry an
evidenced resolution, and the WARN is suppressed exactly where an override
applies. The tripwire stays armed for future instances — this is it working,
not it being disarmed.

### 12.3 Test counts

| suite | before | after |
|---|---|---|
| `test_ingest_metadata_scale.py` | 138 | **141** (+3) |
| `test_ingest_metadata_universe.py` | 45 | **45** |
| `test_edgar_client_companyfacts.py` | 7 | **7** |
| **total** | 190 | **193 passed / 0 failed** |

New/changed: `test_oneok_override_replaces_an_8k_cover_page_with_the_real_release`
and `test_micron_override_handles_the_double_dot_type_string` (each asserts the
pre-override defect — cover page, `8K_BODY`, HIGH confidence — *and* the fixed
pick), `test_double_dot_type_is_still_outside_the_ex99_family`, plus the
four-row pins in `test_shipped_overrides_file_has_exactly_the_four_ratified_rows`
and `test_dead_override_is_reported`, and the 45-change replay pin.
`pyflakes` clean.

### 12.4 Files touched

| path | what |
|---|---|
| `data/f2/earnings_doc_overrides.csv` | +2 evidenced `select_document` rows (2 → 4). |
| `ingest_metadata.py` | `RATIFIED_EARNINGS_DOC_OVERRIDES` 2 → 4, grouped by defect class with a comment. **No logic change.** |
| `data/f2/fixtures/filing_index_CIK0000723125_0000723125-19-000172.html` | New, byte-identical copy of the cached Micron index (verified by test). |
| `test_ingest_metadata_scale.py` | +3 tests, 3 pins re-pinned. |
| `data/f2/F2_SPEC.md` | **Appended** AMENDMENT **A7**, naming the three A6 figures it supersedes (2 rows → 4, 43 changes → 45, ONEOK/Micron reported → ratified). A6 left as the record of what was known then. |
| `data/f2/status/S3_metadata_documents.md` | This §12. |

### 12.5 Updated note for segment 1 attempt 3

Supersedes §11.8's first two bullets: the delta is now **45** changed picks, so
**~44 newly-selected documents** are not yet in `data/raw/documents/` (41
Prologis EX-99.2 + NVIDIA + ONEOK + Micron). Segment 2's delta fetch is that
size. Until it runs, P6 reports Prologis as **UNMEASURED, not clean** — by
design, and the post-fix quiet property is pinned by fixture tests rather than
by the attempt-3 log. Everything else in §11.8 stands.

### 12.6 2026-08-24 (later) — the real-corpus pin was re-pointed at the enduring invariant

**Full-suite gate finding, ruled by the main session; premise re-verified here
before changing anything.** `test_fix_package_changes_exactly_the_intended_
picks_on_the_real_corpus` pinned a **migration delta** — "replaying the policy
must move exactly 45 picks across 5 filers" — which was only ever true against
the *pre-fix attempt-2* database. Segment 1 attempts 3+4 regenerated the stored
selections under the fixed policy, so the delta is now correctly `{}`. **The
test's premise was stale, not the code.**

Re-measured independently before editing (cache-only, DB read-only, 0 GETs):
**0 replay-vs-stored differences across all 10,569 earnings 8-Ks**, 0 indices
missing, stored confidence high 10,533 / medium 16 / low 19 / 1 NULL (the AT&T
exclusion) — matching the replay exactly.

**Renamed to `test_stored_selections_match_current_policy_exactly`** and
re-pointed at the enduring invariant: *replaying the current policy over every
cached index must reproduce the stored selections exactly* (`changed_by_cik ==
{}`). That makes it a **standing tripwire against silent policy/DB
divergence** — either the policy changed without a segment-1 re-run, or the DB
was written by a policy no longer in the tree. It also now compares the
confidence column (mapping the exclusion's stored NULL to "no selection", so a
NULL-vs-string mismatch cannot pass unnoticed) and asserts no cached index is
missing.

**Verified it can actually fail** (a guard that cannot fail is worthless), by
two in-process negative controls: removing the Prologis handler trips it with
"41 stored selection(s) across 1 CIK(s)", emptying the override file trips it
with "4 across 4"; unperturbed, it passes.

**No pre-fix DB was reconstructed and nothing was deleted.** The historical
45-change measurement stays the record it is — F2_SPEC amendments A6/A7 carry
the numbers, and each pre-override defect is still pinned individually against
a cached fixture (`test_prologis_*`, `test_nvidia_override_*`,
`test_oneok_override_*`, `test_micron_override_*`, `test_att_override_*`), all
of which assert the defect **and** the corrected pick. Those regressions
therefore stay guarded without depending on a database snapshot that no longer
exists — which is why re-pointing this one test loses no coverage.

Test counts unchanged at **141 / 45 / 7 = 193 passed**; the rewritten test
replaced the old one one-for-one. `pyflakes` clean.

### 12.7 2026-08-24 (final) — the 2016-04-19 boundary + the P6 title-region scope fix

Two ruled fixes from the content re-verification (`F2_PROGRESS.md` §5 newest
entry; findings in `S6_ex99_manual_read.md` §V.3). **Zero GETs, DB read-only,
no ledger edits.**

**Premise re-verified against raw bytes before changing the constant**, because
it contradicts my own §11.1 claim. Across the whole 113,158-character
`pld-ex991_6.htm` (2016-04-19) there is **exactly one** release-language hit,
at character offset **64**, inside the title "Prologis Earnings Release and
Supplemental Information"; zero hits for "Prologis Reports", "today reported",
"FOR IMMEDIATE RELEASE", "press release", "conference call" or "webcast", and
its ToC runs Highlights → Company Profile with no release entry. The 2016-01-26
comparator does carry "Prologis Reports" and a "Press Release" ToC entry.
**The re-reader is right and my §11.1 "all four pre-split filings contain the
release" was wrong on the fourth** — it generalised from the title string,
which is exactly the signal this filing breaks. `PROLOGIS_SUPPLEMENTAL_SPLIT`
is now **2016-04-19**; blast radius **42 of 45**; the handler docstring names
the exception instead of claiming all four.

**Replay-confirmed pick delta vs the stored DB: exactly 1** —
`0001564590-16-016339`, `pld-ex991_6.htm` → `pld-ex992_7.htm`. No other filing
in the corpus moves.

**P6 scope fix — and why it could not be an offset rule.** Markers now count
only beyond the leading `TITLE_REGION_CHARS = 200`. A "first marker must be
late" rule is impossible here: MEASURED first-marker offsets are **27–89 for
genuine releases and 64 for the false positive** — they interleave. What
separates them is whether any marker *survives* the title region:

| document class | hits beyond char 200 |
|---|---|
| the 2016-04-19 false positive | **0** → flags (correct) |
| 41 cached Prologis EX-99.2 releases | **≥ 3** |
| NVIDIA / ONEOK / Micron override releases | 10 / 11 / 8 |
| the 3 genuine pre-split combined EX-99.1 docs | 11 / 9 / **1** |

200 is chosen with that margin visible, and the ceiling is recorded: at a
400-char cut the weakest genuine document (2016-01-26) drops to 0 and would
false-flag, so the boundary must stay ≤ ~300. Threshold (0.5) and minimum
sample (4) are untouched — this narrows *where* markers count, nothing else.

**P6 corpus result under the scope fix: exactly 1 flagged CIK — Netflix
(25/47, 53%).** Measured both ways:

| selection set | Prologis | Netflix | flagged CIKs |
|---|---|---|---|
| stored (pre-regeneration) | 1/45 missing, flag **False** | 25/47, flag True | **1** |
| post-fix replay | 0/44 missing, flag **False** | 25/47, flag True | **1** |

**Netflix's flag status did not change either way under the scope fix** — same
25/47, same 53%. Reported, not tuned, as instructed. Prologis stays clean in
both: the newly-correct 2016-04-19 count of 1 missing is 2% of 45, far below
the 50% bar.

Post-fix Prologis shows **44 measured, 1 uncached** — the uncached one is the
newly-selected `/Archives/edgar/data/1045609/000156459016016339/pld-ex992_7.htm`,
which is **the 1-GET segment-2 delta** in the main session's plan. It is
counted UNMEASURED, never clean, exactly as designed.

**Test counts: 149 + 45 + 7 = 201 passed, 1 deselected.** `pyflakes` clean.
+8 tests. Five pre-existing tests were repaired rather than weakened, all for
the same two ruled reasons: `test_prologis_pre_split_keeps_ex99_1` now dates
its filing 2016-01-26 (2016-04-19 is no longer pre-split) and says why in its
docstring; four synthetic P6 inputs had their release marker moved into the
document body, because a marker in a 60-character synthetic "document" now
correctly sits inside the title region.

**The one deselected test is expected and is the tripwire working.**
`test_stored_selections_match_current_policy_exactly` fails with
`policy/corpus DRIFT: 1 stored selection(s) across 1 CIK(s) ... {1045609: 1}.
Either re-run segment 1, or the policy changed in a way nobody re-ingested.`
That is precisely true right now: the policy changed and the DB has not been
regenerated. **Attempt 5 re-arms it** — after regeneration the delta returns to
`{}` and the test passes with no edit. Its failure message is self-explanatory
by design, so the final gate reads it as pre-regeneration state rather than a
defect.

**Files:** `ingest_metadata.py` (split constant + docstring, `TITLE_REGION_CHARS`
+ `screen_selected_document` scope), two new cache-derived fixtures in
`data/f2/fixtures/` (`p6_real_release_prologis_2019-10-15_ex99-2.htm`, a
byte-identical 68 KB copy; `p6_title_only_prologis_2016-04-19_ex99-1.prefix.htm`,
a byte-exact 3 KB prefix of a 138 KB document, sliced only for repo weight and
provenance-tested), `test_ingest_metadata_scale.py`, this §12.7, and F2_SPEC
amendment A8.

### 12.8 2026-08-24 (S7 red-team) — B1 conditional fallback, + B2/B6/B7/B17

Five ruled fixes from the S7 red-team (`data/f2/status/S7_redteam.md`; triage
in `F2_PROGRESS.md` §5). **Zero GETs, DB read-only, no ledger edits.**

**B1 is a real defect in my code and the red-team's diagnosis is exactly
right.** I re-derived it before changing anything: 20 of the 225 `8K_BODY`/high
selections still had an unselected non-body candidate row, and the stored
"earnings document" in those filings is the SEC Form 8-K cover page — Aon
(2,260 chars), Illumina (2,827), HPE (4,231) — each of whose own Item 2.02 text
reads *"attached hereto as Exhibit 99.1"*. The root cause is exactly as stated:
the fallback returned `("8K_BODY", "high")` unconditionally.

**The fix is a conditional fallback, not family widening.** `_EX99_FAMILY_RE`
and `_canonical_exhibit_type()` are untouched; a malformed type still never
wins the normal ladder. What changed is only what happens *before settling for
the body*: look at unselected candidates, select a specific one **only on
index/description evidence**, and otherwise return UNRESOLVED. The candidate
rule is deliberately narrow — a sub-numbered securities exhibit (`EX-1.1`,
`EX-2.1`, `EX-3.1`, `EX-10.1`) is not a candidate, so Dominion, Emerson,
Danaher, Marathon and MPLX keep `8K_BODY` untouched.

**Replay — 15 pick changes, 4 new unresolved:**

| disposition | n | filers |
|---|---:|---|
| resolved to a real release (medium) | **11** | Aon 2015-07-31, Biogen 2017-04-25, Vistra 2017-05-18 / 2017-08-04 / 2018-02-26, Pioneer 2017-08-01 / 2018-04-09, Zoom 2019-12-05, TI 2020-01-22, Arista 2020-05-05, Linde 2022-04-28 |
| newly **UNRESOLVED** | **4** | Illumina `0001110803-16-000185`, Illumina `0001110803-16-000194`, HPE `0001645590-17-000006`, Kraft Heinz `0001637459-19-000050` |

The four unresolved all describe their release row `EXHIBIT 1` / `EXHIBIT 2` —
no self-label as exhibit 99, no release-shaped description — so nothing in the
index confirms which row is the release. Ruled disposition: loud and counted,
resolvable by an evidenced override row after a human reads them.
**New unresolved rate 4/10,569 = 0.038%** against the 1% ceiling → **WARN only,
no FATAL**. Confidence moves high 10,529→10,518, medium 16→27.

**Two findings beyond the brief, reported not acted on:**

1. **The fix subsumes the ONEOK and Micron override rows for selection.** Their
   descriptions ("…EARNINGS RELEASE NEWS RELEASE", "…EXHIBIT 99.1 PRESS
   RELEASE") are confirmable, so the general screen now reaches the same
   documents at medium; the override rows still fire and carry them to high.
   The rows stay — they are ratified and evidenced, and they hold the content
   verification. Flagging it so nobody reads the redundancy as a bug.
2. **A 15th release-shaped case B1's table did not list:** Linde
   `0001654954-22-005503`, typed `EX-95.1`, described `EX-99.1`. Same class,
   now resolved.

Also measured and **not** implemented: the stored cover page's own body text
("attached hereto as Exhibit 99.1") is a decisive third evidence route that
would resolve all four unresolved filings. It is not one of the two ruled
routes (index/description), so I did not add it — flagged for ratification.

**B2** — dated correction appended to `S6_seg1_ex99_diagnosis.md` scoping its
"0 genuine selection failures" and "benign class" claims to the 400 examined,
citing B1 and naming the three cover pages read in the bytes.

**B6** — new `release_language_missing_share` audit column, emitted for
**every** CIK rather than only the flagged; plus a printed **WATCH LIST** of
CIKs at or above `P6_WATCH_SHARE = 0.40` but under the bar (Pioneer 38/77 =
49.4%, one filing from flagging and independently implicated in B1). The flag
threshold was **not** moved.

**B7** — P3's docstring corrected: 3 hits is *its trigger's* count; the defect
class is **38 filings**, and the fallback candidate screen is what covers it.

**B17** — `RATIFIED_VALIDATION_EXCEPTIONS` added, matching the gate both
sibling override files already had; an unratified row is refused at load. Ships
empty. This correctly broke 8 S2 tests that wrote synthetic exception rows —
**repaired through the gate, not around it**: `_write_exceptions()` now ratifies
exactly the pairs each test writes, so the gate stays live for everything else.

**Test counts: 183 + 45 + 7 = 235 passed, 1 deselected.** `pyflakes` clean.
+29 tests. Repaired rather than weakened: the ONEOK and Micron override tests
now assert the *new* pre-override behaviour (candidate screen reaches the same
document at medium) alongside the override's high-confidence result, and
`test_double_dot_type_is_still_outside_the_ex99_family` →
`test_malformed_types_stay_outside_the_family_but_are_now_candidates`. The
red-team was right that its old docstring had the reasoning backwards: it
claimed non-recognition prevented "a silent mis-pick generator" when
non-recognition is precisely what produced 14 silent mis-picks. The repaired
test asserts both halves — still outside the family for the ladder, *and*
reachable as a fallback candidate.

**The deselected test is the drift pin, expected.** The main session's attempt
5 regenerated the DB at 17:41 (the A8 Prologis change is now stored), so the
pin's only remaining delta is these 15 B1 changes. It re-arms itself on the
next regeneration with no edit.

**Files:** `ingest_metadata.py` (candidate screen + conditional fallback, P3
docstring, B17 gate, B6 audit column + watch list), four new cache-copied index
fixtures (Aon, Illumina, HPE, Marathon), `test_ingest_metadata_scale.py`,
`test_ingest_metadata_universe.py` (gate-aware helper), the B2 correction in
`S6_seg1_ex99_diagnosis.md`, this §12.8, and F2_SPEC amendment **A9**.

### 12.9 2026-08-24 (final) — the four B1 singletons join the override file

Ruled: the third evidence route (stored cover-page body text) is **NOT**
adopted as policy — for 4 filings it fails lazy-elite. The ratified
per-accession mechanism absorbs them instead. **Zero GETs, DB read-only.**

**Final override row count: 8** (seven `select_document`, one `exclude`).

| accession | filer | selected document |
|---|---|---|
| `0001110803-16-000185` | Illumina Q1 2016 | `a1q16earningsrelease.htm` |
| `0001110803-16-000194` | Illumina Q2 2016 | `a2q16earningsrelease.htm` |
| `0001645590-17-000006` | HPE Q4 FY2017 | `ex-991x10312017x8k.htm` |
| `0001637459-19-000050` | Kraft Heinz 2019-06-07 | `a6719exhibit991.htm` |

Each row's evidence carries (a) the stored cover page's Item 2.02 sentence
verbatim and (b) the candidate-row fact, and states that content verification
happens post-delta by the extraction-qa pass, per the NVIDIA standard.

**I did not take "the sole unselected candidate" on faith for HPE — and it is
a good thing.** HPE has **two** candidates, and **S7 B1's own table named the
wrong one**: `pressrelease112117.htm` is the **Item 5.02** document, the
Antonio Neri CEO-appointment announcement. The cover page maps its exhibits
explicitly — Item 2.02 attaches the segment-results release as **Exhibit 99.1**
(`ex-991x10312017x8k.htm`, filename encoding both `ex-99.1` and the 10/31/2017
quarter end); Item 5.02 furnishes the Neri release as Exhibit 99.2. Taking B1's
filename would have stored a management announcement as the earnings text —
the same class of defect B1 exists to fix. The override names Exhibit 99.1 and
a test pins that it is not the Neri document.

**Replay: 15 pick changes, 0 new unresolved — not 19.** The four filings were
**already inside** §12.8's 15 (they were changing from the stored cover page to
UNRESOLVED), so these rows *convert* four of the fifteen rather than adding to
them. Composition moves from 11 resolved / 4 unresolved → **15 resolved / 0
unresolved**. Reporting the true recount rather than the projected 19.

**Future instances of this shape stay loud-UNRESOLVED** — the mechanism
absorbed four measured singletons, the policy is unchanged, and
`test_future_instances_of_the_bare_ex_shape_stay_loud_unresolved` pins it.

**Also fixed (docs pass):** F2_SPEC §11's shared-window amendment cited "the
2020-06-28 8-K item 1.03 — the corpus's only bankruptcy". Both details were
stale: there are **two** item-1.03 filings for CIK 895126, **2020-06-29** and
**2021-01-19**. Appended as a dated correction in AMENDMENT **A10** rather than
rewritten. The amendment's conclusion is unchanged and slightly strengthened —
both filings sit outside the CIK's own spell, so clipping would lose both.

**Test counts: 188 + 45 + 7 = 240 passed, 1 deselected.** `pyflakes` clean.
+5 tests; the 4→8 load-time pins updated. The deselected test is the drift pin,
expected until the main session's final regeneration; its 15-change delta is
exactly the set above.

**Files:** `data/f2/earnings_doc_overrides.csv` (+4 rows),
`ingest_metadata.py` (`RATIFIED_EARNINGS_DOC_OVERRIDES` 4 → 8, grouped by
defect class), one new cache-copied Kraft Heinz index fixture,
`test_ingest_metadata_scale.py`, F2_SPEC amendment **A10**, and this §12.9.

### 12.10 2026-08-24 (final) — Pioneer 2018-04-09 excluded: a resolution of mine that was wrong

The content verification found one of my 11 candidate-screen resolutions was a
mis-label. **I re-verified it against the cached bytes before acting** — the
finding is correct. **Zero GETs, DB read-only.**

**Final override row count: 9** — seven `select_document`, **two** `exclude`.

`0001193125-18-111008` resolved to `d564737dex991a.htm` because its sole
candidate row is described `EX-99.1(A)`, which self-labels as exhibit 99.1. The
document is the **IPAA Oil & Gas Investment Symposium** slide deck (36,577
chars, opening "IPAA Oil & Gas Investment Symposium April 10, 2018 / Exhibit
99.1A / Forward-Looking Statements") with **zero** hits for "first quarter
2018", "1Q18", "today reported", "press release", "news release", "preliminary".
The filer's own Item 2.02 is a conditional Regulation-FD wrapper — "furnishes
the portions, **if any**, of the **Investor Presentation** titled 'IPAA Oil &
Gas Investment Symposium'" — with Item 7.01 carrying the substance.

**Worth stating plainly: my fix made this one filing less honest.** Pre-fix it
claimed `8K_BODY`, which is true of a cover page. Post-fix it claimed
`EX99_PRESS_RELEASE`, which is false of a slide deck. It is not a mis-pick —
there is no better candidate in the filing — so the right disposition is the
`exclude` mechanism, not a policy change, and the policy still resolves it (a
test pins that, so the exclusion is visibly a human ruling layered on top).

**Replay delta confirmed exactly as ruled:**

| | stored (18:29 regeneration) | after row 9 |
|---|---:|---:|
| high | 10,522 | **10,522** |
| medium | 27 | **26** |
| low | 19 | **19** |
| excluded | 1 | **2** |
| new unresolved | — | **0** |

**Exactly 1 pick change, zero others.**

**Audit accounting:** both exclusions surface as `EXCLUDED_BY_OVERRIDE` audit
rows and `earnings_doc_excluded_by_override` INFO problems, and both stay out of
the unresolved rate and the sector-coverage denominator.

**One measurement recorded against B6, not acted on:** this deck **passes** the
P6 screen — on a single boilerplate hit, "investor relations" inside a mailing
address ("…Irving, Texas 75039, Attention: Investor Relations…"). That is
exactly B6's stated secondary weakness demonstrated on a real document: a P6
*pass* is weak evidence. No marker set or threshold was touched. It also means
§W.3's note that this filing is one of Pioneer's 37 missing picks is not
accurate post-A9 — it passes, on boilerplate. Pioneer's watch-list position is
unaffected either way.

**Test counts: 192 + 45 + 7 = 244 passed, 1 deselected.** `pyflakes` clean.
+4 tests, 8→9 pins updated. The deselected test is the drift pin, expected: its
delta is now exactly this one filing, and it re-arms on the final regeneration.

**Files:** `data/f2/earnings_doc_overrides.csv` (+1 row),
`ingest_metadata.py` (`RATIFIED_EARNINGS_DOC_OVERRIDES` 8 → 9, grouped by
disposition), one new cache-copied Pioneer index fixture,
`test_ingest_metadata_scale.py`, F2_SPEC amendment **A11**, and this §12.10.

### 12.11 2026-08-24 — PSEG (45/45 decks), the deck-title screen, and the census

The ordered PSEG watch-list read found my pipeline's largest content defect.
**I re-verified all three claims against the cached bytes before implementing.**
Zero GETs, DB read-only, no ledger edits.

**The defect, independently confirmed.** All **45** PSEG earnings selections
were the earnings **conference-call slide deck**, all at `high`. Index shape
`{('EX-99','EX-99.1'): 45}` — uniform 2015-07-31 → 2026-08-04, no exceptions;
all 45 filings `items=2.02,7.01,9.01`; all 45 selected documents carry deck
titles. Root cause is mine: the ladder prefers sub-numbered over bare, and
`_best_by_description()` cannot break the tie because both descriptions are
content-free ("EX-99" / "EX-99.1"). The Prologis shape one rung lower, and the
third confirmation that confidence does not track correctness.

**1. PSEG handler — replay: exactly 45 pick changes, PSEG only.** Distribution
unchanged (high 10,522 / medium 26 / low 19 / excluded 2); PSEG was high before
and after. No blanket bare-before-sub-numbered flip — and the census below
shows that would have been a gamble.

**2. Deck-title screen — corpus sweep results.**

| sweep (all 10,567 cached selections, 0 uncached) | flagged CIKs |
|---|---|
| **pre-fix stored picks** | **1 — CIK 788784 PSEG, 45/45** |
| **post-fix picks** | **0** |

All four acceptance directions met: PSEG-pre-fix 45/45 flags; PSEG-post-fix does
not (its new picks are uncached → **unmeasured, never clean** — that is the
segment-2 delta); Prologis-post-fix 45 seen / 0 deck; Netflix 47 seen / 0 deck.

Every marker is measured, none speculative. Generic `"conference call"` was
**measured and rejected** — 93 hits over 11 CIKs including TI 45 and Nike 12,
whose releases just name the call. And the corroboration requirement exists for
a real false positive I found: **Danaher `0000313616-20-000081`** is a genuine
release headlined "… AND SCHEDULES FIRST QUARTER EARNINGS CONFERENCE CALL".
Title-only flags `{PSEG 45, Danaher 1}`; title + deck boilerplate flags
`{PSEG 45}` exactly. It flags on ANY deck selection — no majority, no minimum
sample — because unlike release-language-missing there is no benign share.

**3. Two-candidate-shape census — the roster (2 filers, 46 filings):**

| CIK | filer | sector/stratum | filings | shape | disposition |
|---|---|---|---|---:|---|
| 788784 | Public Service Enterprise Group | utilities / extension | **45** | `('EX-99','EX-99.1')` | fixed by the handler |
| 1163165 | ConocoPhillips | energy / core | **1** | `('EX-99','EX-99.2')` | **true negative — no action** |

ConocoPhillips already selects its bare `EX-99` (described "EXHIBIT 99.1"), and
its bytes open "ConocoPhillips Reports First-Quarter 2017 Results; … HOUSTON--
(BUSINESS WIRE)" — it is the release. **This is the empirical case for the
no-blanket-flip ruling: the shape alone is not the defect.** No other filer is
auto-fixed and the roster is otherwise empty.

**A methodology note worth keeping.** I ran the census two ways and they
disagree: on `_effective_exhibit_type` (description-aware) it finds 1 filer;
on `_canonical_exhibit_type` — what the ladder actually keys on — it finds 2.
The second is the correct denominator for "which filings could the ladder
mis-order", and it is the one reported. A single-pass census would have missed
ConocoPhillips and reported a cleaner roster than the truth.

**Also recorded (no code change):** a P6 *pass* can rest on contact-slide
boilerplate — all 24 PSEG "passers" passed on `"investor relations"` alone — so
**the watch-list share is a floor, not an estimate.** PSEG's 21/45 understated a
45/45 defect. Every filer below the watch-list bar remains unmeasured for this
class, not clean.

**Test counts: 206 + 45 + 7 = 258 passed, 1 deselected.** `pyflakes` clean.
+14 tests; one pin updated (`PER_FILER_EARNINGS_HANDLERS` now holds two
filers). The deselected test is the drift pin — its delta is exactly these 45,
and it re-arms on the final regeneration.

**Files:** `ingest_metadata.py` (PSEG handler + registry, `DECK_TITLE_MARKERS` /
`DECK_BODY_CORROBORATION` / `deck_shaped` signal, per-CIK deck aggregation,
`deck_shaped_problems`, two audit columns, run-summary line), three new
cache-derived fixtures (PSEG index, a PSEG deck prefix, the Danaher release),
`test_ingest_metadata_scale.py`, F2_SPEC amendment **A14**, and this §12.11.
