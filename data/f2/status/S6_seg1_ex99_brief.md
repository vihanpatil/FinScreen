# S6 segment-1 EX-99 diagnosis brief (issued 2026-08-24)

Agent: data-engineer (Opus). Relaunch with this brief verbatim if no
`S6_seg1_ex99_diagnosis.md` appears beside it.

## Situation

S6 segment 1 (`ingest_metadata.py --stage metadata --db
data/filings_metadata_e2.db`) completed ingestion but exited 1 on the
designed post-ingestion FATAL: **400 of 10,569 earnings 8-Ks (3.78%)
`earnings_doc_unresolved`**, above the 1% ceiling. Full log:
`data/f2/s6_segment1_metadata.log`. Per-case WARNs are in
`universe_validation_problems` (run_date=2026-08-24, stage=metadata) in
`data/filings_metadata_e2.db`; the selection audit is
`data/f2/ex99_selection_audit.csv`. Also relevant: 72 CIKs carry
low-confidence selections, heavily clustered (896878: 53, 72903: 43,
849399: 43, 92122: 40 — filer-dialect shaped).

## Task

1. **Triage all 400 failures** by CIK / year / index format from the DB +
   audit CSV + the cached filing indices under `data/raw/filing_index/`
   (cache-forever; ZERO live GETs — everything you need is on disk).
   Produce a failure taxonomy: how many are (a) parser/selection-policy
   gaps on real earnings exhibits (fixable), (b) genuinely
   exhibit-less earnings 8-Ks that should fall back to 8K_BODY or be
   classified benign, (c) anything else.
2. **Fix what the taxonomy says to fix**, minimally (lazy-elite):
   extend `select_earnings_document()` / the index parser with small,
   named, per-dialect handlers; never a clever universal regex; never
   weaken the 1% check itself without taxonomy evidence that a benign
   class is being miscounted — and if you do reclassify a benign class,
   it must be counted and named in the run summary, not dropped.
3. **Tests**: fixture per new dialect handler (sliced from cached
   indices into `data/f2/fixtures/`), offline; extend
   `test_ingest_metadata_scale.py`; re-run your targeted files + S2's
   universe suite.
4. **Estimate the post-fix failure rate** by running your fixed
   selection over the cached indices for all 400 failing accessions
   (offline replay — no GETs, no DB write). Report the expected new
   rate; the main session re-runs segment 1 for real (cache-warm,
   cheap).

## Constraints

No live GETs. No F2_PROGRESS.md edits. Do not re-run segment 1 or write
to `data/filings_metadata_e2.db` (read-only for you). E1 artifacts
untouched. If the taxonomy shows the 1% ceiling itself is wrongly
calibrated for the real corpus, PROPOSE the recalibration with evidence
— the main session rules on it; do not change the threshold yourself.

## Deliverables (BOTH before returning)

1. Code + tests green (exact counts).
2. `data/f2/status/S6_seg1_ex99_diagnosis.md`: taxonomy table (counts by
   cause and by CIK), what was fixed and how, offline-replay post-fix
   rate over the 400, any proposed check recalibration with evidence,
   resume instructions if partial.
