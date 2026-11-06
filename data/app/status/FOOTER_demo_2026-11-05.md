# FOOTER_LINE: demonstration sharing (owner ruling C, 2026-11-05)

Ruling quoted verbatim from HANDOFF §3 "PACKET ITEMS B–F RULED":
> C. If sharing is problematic, keep it personal for me. Yes to only sharing for demonstration, no hosting.

## What changed
`report_filing.py` only, one constant (`FOOTER_LINE`, line 378). No other file touched; not committed.

```diff
 FOOTER_LINE = (
     "Not investment advice. No recommendation. No live capital. "
-    "Personal use only. Not for distribution."
+    "Rendered for the author’s personal use; shared only as a demonstration. "
+    "Not for redistribution."
 )
```

**One deviation from the brief's text: the apostrophe in "author’s" is U+2019 (’), not ASCII `'`.**
The ASCII version broke two tests. `esc()` (html.escape, quote=True) renders `'` as `&#x27;`, so
`assert RF.FOOTER_LINE in html` failed in test_disclosure_header_renders_every_ruled_number and
test_disclosure_block_is_the_only_allow_listed_region, and the visible-length pin would have been
off by 5. U+2019 is left alone by html.escape (`esc(FOOTER_LINE) == FOOTER_LINE`), pages declare
`<meta charset="utf-8">`, and IDENTITY_LINE already uses a non-ASCII em-dash. The visible text is
otherwise exactly as briefed. len(FOOTER_LINE) = 154.

Legal-baseline words: none of "advice tool", "should I invest", "calls", "top companies",
"beats the market", "accuracy" appear. Note that STORYBOARD's list also bars bare "advice"
on *public* surfaces. "Not investment advice" was already in the footer before this change,
and the brief calls it the ruled disclaimer form. These pages are private demonstrations, not a
public surface, so I left the phrase as it was.

## Commands and results
`/Library/Developer/CommandLineTools/usr/bin/python3 -m pytest -q -p no:cacheprovider test_report_filing.py test_finscreen_cli.py`

- Run 1 (ASCII apostrophe): `4 failed, 112 passed in 406.44s (0:06:46)`. The failures were the 2 escape
  failures above plus 2 timing failures.
- Run 2 (final, U+2019): `2 failed, 114 passed in 323.99s (0:05:23)`. Remaining failures:
  - test_report_filing.py::test_real_filing_renders_under_ten_seconds[0000320193-24-000123]
  - test_report_filing.py::test_real_filing_renders_under_ten_seconds[0000320193-25-000007] (13.9s)

These timing failures are environmental, not caused by the footer. A labeling chain was running
(pids 94237/94238, `label_filing.py --store data/app/companies/1326801`), with load average 3.9–5.5.
In a scratch script (one process, AAPL 10-K render, constant swapped), the old and new footers
took: old 6.9/8.4s, new 9.1/11.9s; then in reversed order new 6.4/16.9s, old 8.7/9.2s. Same-constant
runs vary by more than 2x, so the timing is noise. Re-run those two tests when the labeler is idle.

## Noticed, not changed
- Pages already rendered under data/app/reports/ (e.g. 320193/index.html,
  320193/0000320193-24-000123.html, 2071489/0001493152-26-030051.html) still carry
  "Not for distribution". They pick up the new footer the next time they are rendered. I did not
  touch data/ or run bin/fs report.
- "Personal use only." still appears in non-rendered strings: the argparse description at
  report_filing.py:1863, the ingest_one.py:1092 argparse description, and the finscreen.py
  docstring. These are not page text and were out of scope.
