# S6 EX-99 manual-read brief (issued 2026-08-24)

Agent: extraction-qa-engineer (Opus). Relaunch with this brief verbatim
if no `S6_ex99_manual_read.md` appears beside it.

## Task — F2_SPEC §4.4 item 4, the mandatory manual read

Segment 1 (attempt 2) produced the worklist: **71 CIKs** with any
low-confidence EX-99 selection or any 8K_BODY fallback, capped at the
**worst 20 by low-confidence count** for the read (the cap and the
unread remainder are reported honestly, never implied as full
coverage). Sources: `data/f2/ex99_selection_audit.csv`, the worklist
print in `data/f2/s6_segment1_metadata_attempt2.log`, selections in
`data/filings_metadata_e2.db` (READ-ONLY — open with
`file:...?mode=ro`).

For each of the worst-20 CIKs:

1. Pick one representative flagged filing (prefer a low-confidence
   selection; else an 8K_BODY fallback).
2. Read the actual cached filing index (`data/raw/filing_index/`) and
   the selected cached document (`data/raw/documents/`) — enough of it
   to judge. **Zero live GETs; everything is cached.**
3. Verdict per CIK: CORRECT (selected doc is the earnings release /
   8K_BODY genuinely has no exhibit), WRONG (a better document was
   present and missed — name it), or AMBIGUOUS (say why).
4. Note anything that looks like a NEW dialect worth a handler — as a
   proposal, not a fix (no code changes in this task).

Also verify and report: the 8-sector high-confidence coverage
assertion's result in the segment-1 attempt-2 log (each sector must
have ≥1 high-confidence EX99_PRESS_RELEASE selection).

## Deliverables (BOTH before returning)

1. `data/f2/status/S6_ex99_manual_read.md` — the verdict table (20
   rows: cik, name, filing read, selection, verdict, note), the
   uncovered-remainder statement (51 CIKs unread), the sector-coverage
   check result, and any proposed handlers.
2. Your final reply: verdict tally (CORRECT/WRONG/AMBIGUOUS), the
   WRONG list if any, sector coverage result.

## Constraints

Read-only task: NO code edits, NO DB writes, NO live GETs, no
F2_PROGRESS.md edits. If you find a WRONG selection, that is a finding
for the main session to rule on — do not fix it.
