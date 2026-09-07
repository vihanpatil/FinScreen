# S7 report brief — the F2 ingestion report (issued 2026-08-24)

Agent: docs-writer (Opus). Relaunch verbatim if no
`data/F2_INGESTION_REPORT.md` + `S7_report_note.md` appear.

## Task

Write `data/F2_INGESTION_REPORT.md` — the owner-facing record of what F2
ingested, how it was verified, and every caveat that must travel with
the E2 corpus. The owner reads THIS file at gate; it must stand alone.

## Sources (read in this order; every number traceable to one of these)

`F2_PROGRESS.md` (stage table + §5 decisions + §6 owner items) →
`data/f2/status/S6_runs.md` → `data/f2/F2_SPEC.md` §11 amendments →
the stage completion reports in `data/f2/status/` → the run logs
(`data/f2/s6_*.log`) for any number needing a primary source.

## Must contain (checklist)

1. What was ingested: 45,632 filings (45,545 + 87 co-registrant), 42 GB
   documents (20,522 cached, 0 failed), 622,661 fundamentals rows
   (30 tags / 14 families), 1,960,738 price rows; window
   2015-07-01→2026-08-31 (fixed); observed max filing_date 2026-08-24.
2. The two censoring pairs, labeled and never conflated: FETCH 213/31;
   OPERATIVE **32 with no usable prices (28 core / 4 extension)** incl.
   EA (fetched-but-purged, distress-events-visible). This pair must
   accompany every E2 result.
3. Outside-membership count (20,218/45,632, BY DESIGN — F5 joins on
   universe_membership); co-registrant rule (absence from `filings` ≠
   did-not-file).
4. Fundamentals resolution profile (SINGLE 2,355 / DOMINANT 489 /
   MIGRATION 75 / OVERLAP 8 / ABSENT 342 / PARTIAL 147 = 497 UNRESOLVED,
   all per-pair loud; blocker table empty under the 4-entry exemption
   ledger, each exemption stated with its reason; F5 notes: liabilities
   derivable, operating_income non-universal, UNRESOLVED pairs never
   become series).
5. EX-99 quality story, honestly: the manual read found a systematic
   Prologis error (42/45) invisible to confidence scoring; the fix
   package + P6 screen + 4 evidenced overrides; final unresolved 0.00%;
   Netflix = the one benign flag; the read's coverage cap (20 of 71
   CIKs; 8K_BODY tail mostly unread) stated as a limitation.
6. Yahoo provenance caveat restated (PRICES_NOTES.md §1; Stooq one flag
   away); the AEP submissions-wobble story + override evidence.
7. OWNER DECISIONS QUEUED: (a) SPDR Gold Trust core-financials
   membership (the one entity-type anomaly; MLPs/REITs defensible);
   (b) epoch-2 eval read for G1 conditional acceptance (separate from
   F2 but queued). Parked proposals list (P4 section_type → F3;
   interleaved-substitutes stitching; just-below-threshold line).
8. Verification statement: final gate 731/0/5; every stage's
   completion report named; model-vs-owner provenance per HANDOFF §7
   (all rulings here are main-session build rulings, none are the
   owner's).

Style: docs-writer rules apply (numbers next to their measurement, no
laundering, plain prose). Also write `data/f2/status/S7_report_note.md`
(one page: what you wrote, sources used, anything you could not trace).
