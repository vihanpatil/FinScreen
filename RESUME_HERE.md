# RESUME_HERE — state as of 2026-11-10 (LOW-TOUCH MODE)

**Fresh session: read `CLAUDE.md` (incl. "How we work from 2026-11-10"), then this block; or run `/resume`.**
This block is rewritten, never appended (CLAUDE.md rule 2). History: `HANDOFF.md` §3 (dated, owner words verbatim).

**What works today (owner commands).** `bin/fs open` — the private home page: one sortable table of point-in-time
XBRL facts for every rendered company (31 on 2026-11-10: latest filing, revenue, revenue YoY, net income, net margin,
operating cash flow, total assets, equity) with links to each company's labeled filings and private scorecard.
`bin/fs report TICKER --open` — any US filer, end to end (labeling 5–30 min). `bash data/app/run_watchlist.sh
--refresh` (background) — re-ingest and re-label the 30-ticker watchlist (`data/app/watchlist.txt`), hours.
`bin/fs doctor` — environment. Pages are git-ignored; stores under `data/app/companies/` are committed.

**Research state.** E2 text signal: bounded null, closed at every gate (2026-11-05); the scorecard is a coin flip at the
universe level (0.519 [0.501, 0.537]) and its pages say so. E3 (numeric families) deferred by the owner 2026-11-09.
**Known defect (found 2026-11-10 by the parallel session; LIMITATIONS §3.5a):** `book_to_market` mixed an as-reported
share count with a split-adjusted close, so pre-split filings carry it inflated (251 of 4,481 scored rows, 11 of 139
companies); effect on E2 and the scorecard UNMEASURED; nothing ratified was re-run. The home page carries filed facts
only and does not inherit it. The P5 forward-loop packet is WITHDRAWN (failed review); do not put it to the owner.

**Owner owes (touchpoint c).** Yes/no: run a POST-HOC sensitivity arm under the existing pin (share count
split-adjusted, or `book_to_market` dropped) to measure the defect's effect. Optional: install the launchd refresh
agent (`data/app/launchd/README.md`).

**IN FLIGHT:** nothing. Standing rules: NEVER re-pin; never re-run a head on a model reading; rule 6 before any labeler.
**Next work (no owner word needed):** whatever the owner reports missing after using `bin/fs open`.

---
History lives in `HANDOFF.md` §3 (dated entries, owner words verbatim). Earlier versions of this file, including the
2026-09-06 stopping point and the 2026-11-05 to 2026-11-10 session blocks, are in git history (commit fc83c69 and before).
