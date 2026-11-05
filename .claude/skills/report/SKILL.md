---
name: report
description: Produce FinScreen's reading-aid report for one company — any US SEC filer by ticker — end to end (EDGAR ingest, point-in-time fundamentals, local labeler, HTML pages) and open it. Use when the user names a ticker or company and wants its report, or says "run it on X".
---

Usage: `/report TICKER` (the argument is the ticker; resolve a company name to its ticker
first if the user gave a name).

1. `pgrep -fl "label_filing|label_e2"` — if a labeling process is alive, wait; never run
   two.
2. `bin/fs report TICKER --open` (the wrapper runs `ingest_one.py --per-form 2`, then
   `--fundamentals`, then `label_filing.py`, then `report_filing.py --store … --index` and
   `--latest 10-K / 10-Q / 8-K`). Labeling takes roughly 2 s per passage; a typical company
   is 3–6 minutes. Run it in the background if the shell timeout is shorter.
3. Report the pages written, the wall clock, and every failure verbatim (a company with
   no earnings 8-K or a filer dialect the extractor misses is a recorded fact, not
   something to hide). Remind the reader that the labels carry the G2 model-consensus
   error and no spot-check for companies outside the research universe — the page's own
   disclosure block says so.
4. Never add a score, rank, price or recommendation to what the page shows.
