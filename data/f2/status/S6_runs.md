# S6 runs — live log (started 2026-08-24)

The four ingestion segments from `data/f2/F2_SPEC.md` §7, run as
**main-session background tasks in an auto-resume chain** (HANDOFF §4).
Every command is idempotent and cache-first: killed and re-run, it
completes without redoing network work. **If you are a fresh session
resuming: check `ps aux | grep -E "ingest_(metadata|fundamentals|prices)"`
for a live run first; if none, re-run the current segment's exact command
below — repeats are cheap.**

Full-suite gate before segment 1: **614 passed / 5 skipped / 0 failed**
(2026-08-24, main session, 62 s).

Segments 1→2 strictly ordered; 3 and 4 need segment 1 only.
Each segment: `caffeinate -is` wrapper (no sleep mid-run), stdout+stderr
to its named log file (durable, inspectable by any session).

| # | segment | command (run from repo root) | expected | status |
|---|---|---|---|---|
| 1 | metadata | `caffeinate -is python3 ingest_metadata.py --stage metadata --db data/filings_metadata_e2.db > data/f2/s6_segment1_metadata_attempt2.log 2>&1` | (see completion entries) | **DONE 2026-08-24, attempt 2, exit 0** |
| 2 | documents | `caffeinate -is python3 ingest_metadata.py --stage documents --db data/filings_metadata_e2.db > data/f2/s6_segment2_documents.log 2>&1` | ~20,523 GETs, ~26 GB (18–40), 1–2.5 h | NOT STARTED (after 1) |
| 3 | fundamentals | `caffeinate -is python3 ingest_fundamentals.py --db data/filings_metadata_e2.db > data/f2/s6_segment3_fundamentals.log 2>&1` | 244 GETs, ~1.1 GB, 15–25 min; writes `data/fundamentals_e2.parquet` + `data/f2/concept_resolution.csv`; BLOCKER report read by main session | NOT STARTED (after 1; may parallel 4) |
| 4 | prices | `caffeinate -is python3 ingest_prices.py --db data/filings_metadata_e2.db > data/f2/s6_segment4_prices.log 2>&1` | 213 Yahoo GETs, ~0.2 GB, 6–12 min; writes `data/prices_e2.parquet`; expect 213 fetched / 31 censored (27 core / 4 extension) | NOT STARTED (after 1; may parallel 3) |

## Per-segment completion entries (appended as they finish)

- **Segment 1, attempt 1 (2026-08-24 12:56 → ~13:5x): ingestion COMPLETE,
  exit 1 by design — the post-ingestion FATAL guard fired.** Enumerated
  45,632 filings (10 more than the S1 measurement — new filings since;
  observed max filing_date 2026-08-24 vs freeze 2026-08-31); `filings`
  45,545 + `co_registrant_filings` 87 (3 pairs, keeper=lowest CIK, as
  ruled); distress_events: item-1.03 2/1, Form 25 37/30, 25-NSE 510/131
  (noisy, stored as such), Form 15 119/67; 20,218/45,632 filings outside
  every membership spell (BY DESIGN — full-window ruling; F5 joins on
  universe_membership); EX99 audit written; §4.4 manual-read worklist:
  72 CIKs, capped print at worst 20, 52 uncovered (stated honestly).
  **FATAL: `earnings_doc_unresolved` 400/10,569 (3.78%) > 1% ceiling** —
  the predicted new-filer-dialect cost. Diagnosis+fix delegated
  (brief: `S6_seg1_ex99_brief.md`); segment 1 will be re-run cache-warm
  (~0-GET fast) after the fix. Rows are written; the corpus is NOT to be
  consumed until the re-run clears the guard.
- **Segment 1, attempt 2 (2026-08-24, post EX-99 fixes): exit 0 — the
  guard CLEARED.** 351 GETs total. Validation 0 FATAL / 5 WARN / 29
  INFO; the 5 WARNs are exactly the pre-measured fiscal-calendar gap
  quirks (PepsiCo ×2, Gen Digital 266 d, Discover, Kraft Heinz), all
  under the 300-day FATAL bar; exceptions file empty as predicted.
  `earnings_doc_unresolved`: no FATAL (was 400/10,569). 8K_BODY benign
  class now uniformly labeled: 227 filings across 62 CIKs, named in the
  audit report and kept on the §4.4 read list. Manual-read worklist: 71
  CIKs. Same corpus shape as attempt 1 (45,632 enumerated; 20,218
  outside-membership BY DESIGN; max filing_date 2026-08-24).
- **Segment 2 (documents) STARTED 2026-08-24** right after attempt 2
  cleared — log `data/f2/s6_segment2_documents.log`; segment 3 waits for
  it (SEC politeness: never two EDGAR walkers at once); segment 4 waits
  for the S5 AEP follow-up to land.
- **Segment 4 (prices) STARTED 2026-08-24, overlapping segment 2** —
  safe: Yahoo host only, resolution runs off the fresh submissions
  cache with zero SEC GETs. Launched after the S5 AEP follow-up landed
  (override file = 2 evidenced rows; EIDP correctly stays censored —
  see F2_PROGRESS §5). Log `data/f2/s6_segment4_prices.log`. Expect 213
  fetched / 31 censored (27 core / 4 extension), `data/prices_e2.parquet`.
- **Segment 4 DONE 2026-08-24, exit 0.** 213 fetched / 31 censored
  exactly as pinned; 1,960,738 rows → `data/prices_e2.parquet`
  (41.3 MB); census reconciliation vs F1 exactly the pre-registration;
  0 FATAL / 3,003 WARN (dominated by full-history return outliers —
  real market events: 1987, March 2020, CEG 2024). **Two tripwire
  findings, both real:** (1) EA fetched but Yahoo purged its delisted
  history (6 rows, all post-take-private) → RULED: new
  `resolved_no_coverage` class; operative no-usable-prices pair =
  **32 (28 core / 4 extension)** beside the fetch pair 213/31, both
  always distinguished (F2_PROGRESS §5). (2) GLD (SPDR Gold Trust,
  instrumentType=ETF) is a CORE-financials member → OWNER finding,
  queued for the F2 report read (membership is owner territory).
- **Segment 2 DONE 2026-08-24, exit 0.** 20,523 targets: 19,883
  fetched + 640 already cached, **0 FAILED**; 19,896 GETs this run;
  `data/raw/documents/` now 42 GB (top of the 18–40 GB estimate; 341 GB
  free at start — no constraint). F3's `extract.py` now runs at 0 GETs.
- **Segment 3 (fundamentals) STARTED 2026-08-24** immediately after
  segment 2 released the SEC walker — log
  `data/f2/s6_segment3_fundamentals.log`. Expect 244 companyfacts GETs
  (~1.1 GB), `data/fundamentals_e2.parquet` +
  `data/f2/concept_resolution.csv`; the 244-scale sector-BLOCKER report
  is the output the main session must READ, not skim.
- **Segment 3, attempt 1 DONE 2026-08-24, exit 0 — read in full, one
  more calibration pass ruled.** 244 companyfacts fetched; 619,597 rows
  → `data/fundamentals_e2.parquet`; 3,416 pairs (SINGLE 2,192 /
  DOMINANT 456 / MIGRATION 75 / OVERLAP 8 / ABSENT 353 / PARTIAL 332),
  693 UNRESOLVED, 18 surviving BLOCKERs. Main session read the blocker
  table and ruled four calibrations (F2_PROGRESS §5, "244-scale
  classifier calibration"): filed-span denominator (AZEK artifact), MLP
  partnership-tag broadening, exemptions for ("*","liabilities") +
  ("*","operating_income") with F5 notes, OVERLAP/multi-class left
  firing and listed. S4 is implementing; **segment 3 re-runs after
  (0 GETs, companyfacts cached, same command)** and the parquet +
  concept_resolution.csv regenerate. Current parquet/CSV are attempt-1
  artifacts — do not consume until the re-run.
- **Segment 3, attempt 2 DONE 2026-08-24, exit 0 — prediction verified
  exactly.** 0 GETs (fully cache-warm); 622,661 rows →
  `data/fundamentals_e2.parquet` (regenerated; +3,064 rows from the 3
  new MLP tags); actual resolution profile matches the pre-committed
  prediction on ALL 3,416 pairs (0 differing rows): SINGLE 2,355 /
  DOMINANT 489 / MIGRATION 75 / OVERLAP 8 / ABSENT 342 / PARTIAL 147 =
  497 UNRESOLVED, all per-pair-loud; **sector-BLOCKER table: EMPTY**
  (4 exemptions, none dead). Segment 3 artifacts are now final for F2.
  ALL FOUR NETWORK SEGMENTS COMPLETE.
- **§4.4 manual EX-99 read DONE 2026-08-24**
  (`S6_ex99_manual_read.md`): worst-20 read → 17 CORRECT / 2 WRONG /
  1 AMBIGUOUS; 51 of 71 flagged CIKs honestly unread (all low-confidence
  CIKs covered; 8K_BODY tail mostly unread). Sector coverage: PASSED,
  verified three ways. **The Prologis WRONG is systematic (~39 of 45
  picks, 37 at high confidence)** → main session ruled the six-part fix
  package (F2_PROGRESS §5); metadata-code owner implementing; **segment
  1 attempt 3 required after it** (cache-warm), then targeted
  re-verification of Prologis/NVIDIA/AT&T. Full-suite gate as of the
  calibration re-run: 664 passed / 5 skipped / 0 failed (will re-run
  after the fix package).
- **EX-99 fix package COMPLETE 2026-08-24** (S3 owner, three passes;
  trail in F2_PROGRESS §5): Prologis handler (content-confirmed, 41
  corrected picks), 4-row evidenced `earnings_doc_overrides.csv`
  (NVIDIA + ONEOK + Micron select_document, AT&T exclude — all typo/
  no-release cases found by the new P3 outside-EX-99 WARN), P1
  confidence fix, P5 thin-exhibit WARN, P6 release-language screen
  in-pipeline. **Segment 1 attempt 3** (0 GETs): 4/4 overrides fired,
  0 dead; unresolved 0/10,569. **Segment 2 delta**: 44/44 fetched,
  0 failed. **Attempt 4 P6 re-screen** (0 GETs): all 10,549 measured,
  Prologis CLEAN, sole flag = Netflix (reported-benign shareholder
  letters, threshold not moved). Final selection distribution: 10,308
  high EX99 / 225 8K_BODY high / 19 low / 16 medium / 1 excluded.
  Stale migration-delta test repointed to the enduring zero-drift
  invariant with negative-control verification. **Full-suite gate: 722
  passed / 5 skipped / 0 failed.** Awaiting only the extraction-qa
  content re-verification of the five ruled filers → then S6 DONE.
- **Content re-verification PASS + final residual fixes (2026-08-24,
  closing entries):** all five ruled filers confirmed on real bytes
  (§V of `S6_ex99_manual_read.md`); two residuals ruled and fixed —
  Prologis split → 2016-04-19 (42/45) and the P6 title-region scope
  fix (TITLE_REGION_CHARS=200, margin measured, Netflix unchanged).
  Closing chain: attempt 5 (0 GETs, regen) → delta 2 (exactly 1 GET,
  0 failed) → attempt 6 (0 GETs): unresolved 0.00%, all 10,549
  measured, sole flag Netflix, 4/4 overrides fired 0 dead.
  **S6 DONE 2026-08-24. Final full-suite gate: 731 passed / 5 skipped /
  0 failed.** → S7 launched (red-team + F2 ingestion report).
- **S7 red-team fix cycle (2026-08-24, post-S6 entries — the corpus was
  reopened and re-closed under the B-findings; full trail F2_PROGRESS
  §5):**
  - **Attempt 7** (metadata, 0 GETs): B1 conditional-fallback + A8/A9
    fixes stored; drift pin re-armed.
  - **Delta 3** (documents): 20,522 targets — **15 fetched / 20,507
    cached / 0 FAILED** (the corrected picks).
  - **Attempt 8** (metadata, 0 GETs): unresolved **0/10,569 = 0.00%**
    reached through 4 printed refusals then 8/8 override rows fired
    0 dead; distribution 10,312 EX99-high / 27 medium / 19 low / 210
    8K_BODY-high (55 CIKs) / 1 excluded; P6: 10,549 measured, 0
    uncached, 1 flag (Netflix); in-pipeline WATCH LIST: Pioneer 48.1%,
    PSEG 46.7%; §4.4 worklist now 57 CIKs / 20 named / 37 uncovered.
  - **Fundamentals attempt 3** (0 GETs): 622,661 rows; resolution
    states unchanged (0 diffs); CSV 8 → 11 columns (unit, units_mixed,
    duration_mix); validation 497 FATAL (the per-pair UNRESOLVED rows)
    / 14 WARN / 21 INFO incl. `companyfacts_tail_lag` (Citigroup WARN
    + 21 one-quarter INFO) and `fundamentals_non_usd_reporting`
    (Enbridge, sole non-USD member).
  - **Full-suite gate after the cycle: 797 passed / 5 skipped / 0
    failed** (main-session pytest run, 64.9 s — this entry is the
    on-disk source the F2 report cites).
  - 15-pick content verification (§W of `S6_ex99_manual_read.md`):
    14 CORRECT / 1 mis-labelled → Pioneer 2018-04-09 ruled an
    `exclude` row (9th); one PSEG watch-list read ordered. Final 0-GET
    regeneration + gate follow, then S7 closes.
- **Pioneer + PSEG closing cycle (2026-08-24, late):**
  - **Attempt 9** (0 GETs): Pioneer exclusion stored — 9/9 override
    rows fired 0 dead, 2 exclusions, unresolved 0.00%. Gate: **801
    passed / 5 skipped / 0 failed.**
  - **PSEG defect ruled + fixed** (the ordered watch-list read found
    ALL 45 PSEG selections were conference-call decks, release
    unselected at bare EX-99 — F2_PROGRESS §5): per-filer handler +
    deck-title screen (measured corroboration; Danaher false positive
    excluded by it) + two-candidate census (roster: PSEG fixed;
    ConocoPhillips true-negative — the empirical no-blanket-flip case).
  - **Attempt 10** (0 GETs) → **Delta 4**: 20,521 targets — **45
    fetched / 0 FAILED** (the PSEG releases, first time cached) →
    **Attempt 11** (0 GETs): unresolved **0.00%**; P6 10,548 measured /
    0 uncached / sole flag Netflix; **DECK-SHAPED selections: 0 across
    0 CIKs**; 9/9 overrides fired.
  - **Final full-suite gate: 815 passed / 5 skipped / 0 failed.**
  - Remaining: extraction-qa content read of 4–5 cached PSEG releases
    (S7's last read) + the report's final micro-update → **S7 CLOSE**.

## After segment 4 (before S6 is declared DONE)

1. F2_SPEC §4.4's **mandatory manual EX-99 read** (low-confidence /
   8K_BODY / CANARY CIKs, capped at worst 20, cap reported honestly) +
   the 8-sector high-confidence coverage assertion.
2. F2_SPEC §5.3 sector-BLOCKER review at 244 scale (exemption ledger
   printed; new cells go to a human).
3. §4.2's outside-membership filing count + observed max `filing_date`
   vs the 2026-08-31 freeze constant, stated in the F2 report.
4. Then S7: red-team pass + F2 ingestion report + owner read.
