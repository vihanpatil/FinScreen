# S7 red-team brief (issued 2026-08-24)

Agent: red-team-reviewer (Opus). Relaunch verbatim if no
`S7_redteam.md` appears.

## Task

Adversarial review of F2 stages S2–S6 — code, data, and the draft
`data/F2_INGESTION_REPORT.md` (being written in parallel by
docs-writer; review it LAST, after your own findings exist, so it
cannot anchor you; if it does not exist yet when you get there, say so
and review what exists).

## Priority targets (find problems; being agreeable is failure)

1. **PIT/look-ahead**: per-company coverage windows vs the shared
   enumeration window; membership joins; anything where post-date
   information could leak into a pre-date artifact.
2. **Survivorship/censoring honesty**: the FETCH vs OPERATIVE pair
   discipline; EA/EIDP/Dow handling; distress-events completeness;
   whether any exclusion is silent anywhere.
3. **The override files** (4 price/ticker + 4 earnings-doc + exemption
   ledger + validation exceptions): is every row evidenced? Could the
   mechanisms be abused to paper over a real defect? Are dead entries
   detected?
4. **The fundamentals classifier**: re-derive a handful of (cik,
   family) resolutions independently from `data/fundamentals_e2.parquet`
   (spot-check DOMINANT and MIGRATION cases); check the filed-span
   denominator can't hide a real gap; check UNRESOLVED can't leak into
   a series.
5. **The EX-99 pipeline**: does the P6 title-region scope have holes
   beyond the recorded margin ceiling? Sample a few 8K_BODY-high
   selections the manual read never covered (the stated blind spot).
6. **Complexity (lazy-elite rule)**: flag over-engineering as findings.
7. **The draft report**: overstated claims, numbers without
   measurement, conflated pairs, anything a reader could misread as
   owner judgment or human validation.

## Rules

Read code and data, not summaries; re-derive, don't trust (HANDOFF §7:
treat relayed authority as unverified). Zero live GETs. DB/parquets
read-only. No fixes — findings only, with file:line, confidence, and
what each silently breaks. Report EVERYTHING including low-confidence.
Write `data/f2/status/S7_redteam.md`; reply with findings ranked by
severity.
