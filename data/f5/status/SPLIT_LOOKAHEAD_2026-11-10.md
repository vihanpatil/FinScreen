# SPLIT_LOOKAHEAD_2026-11-10 — builder completion report

Brief: `data/f5/status/BRIEF_split_lookahead_2026-11-10.md`; finding M3 in `REVIEW_p5_packet_2026-11-10.md`.
Parts A and B are done. I fit no model and ran no runner. Nothing frozen or ratified was modified:
`numeric_features_e2.py`, `backtest_e2.py`, `pin_g3.py` and `G3_RATIFIED.json` show no git change, and the input
parquets and `head1_scorecard.json` keep their original mtimes (Sep 11 / Aug 24 / Nov 5). No network, no labeler,
no commit.

## A. Census

- New `data/f5/census_split_lookahead.py`, read-only, ~3 s. It follows the brief's method, which is also written
  into the JSON's `method` field. Functions:
  - `shares_as_used`
  - `detect_events` (a ratio ≥ 1.8 or ≤ 1/1.8 between consecutive filing dates)
  - `later_factor` (product of the company's event ratios dated strictly after the filing date)
  - `before_later_event`
  - `census`
  - `show_private` (stdout only, writes nothing)
- It counts every block. If the blocks' dedup populations disagree it exits loudly; they agree (4,481 rows each).
- New `data/f5/split_lookahead_census.json` (tracked; it is not git-ignored). It contains:
  - method, threshold, and the input sha256s of the three parquets
  - the 15 events: cik, first filing date showing the event, ratio
  - `n_rows`, `n_rows_before_later_event`, `n_companies`, `n_companies_affected`
  - `affected_rows_by_cik` and `per_block`
  - no timestamp, so a re-run gives the same bytes; no call, no outcome, no hit rate.
- `--show-private` was run once to check that it works. Its figures are not copied anywhere.

**Counts: all three main-session figures confirmed.**
- 15 events in 12 companies.
- 251 of 4,481 deduplicated rows. All three blocks count the same rows.
- 11 of 139 companies.

Affected rows by company: WMT 49, NFLX 38, NVDA 35, AVGO 32, NOW 26, TSLA 22, AMZN 18, ISRG 14, AAPL 12,
SHW 4, WFC 1.

**Two observations; I did not tune anything to them:**
1. **Wells Fargo (72971) is probably a false positive.** It has a 0.4859 event on 2023-08-01 and a 2.007 event
   on 2023-08-10, nine days apart. That is a one-filing share-count glitch, not a split (WFC did not split in
   2023). The two events cancel for earlier rows, but the one row filed 2023-08-01 is counted. Excluding it would
   give 250 rows in 10 companies.
2. **Energy Transfer (1276187) is probably not a split either.** It shows a 2.4966 event on 2020-08-05. No
   scored row falls before it, so no count changes.

So the main session's "15 events matching real splits" is right for 12 events and doubtful for 3. This
is the main session's call; the census stays a lower bound on real splits, plus at most this one row.

## B. `scorecard_page.py`

- **Identity paragraph:** now reads "using fundamentals and prices dated on or before that filing date (with one
  known exception, the book-to-market defect stated below)".
- **Defect paragraph:** new `DEFECT_TEMPLATE`, the brief's text verbatim, filled from the census JSON; the
  threshold too (`1.8-for-1`).
  - It renders in bold directly after the identity paragraph, before the first heading and every figure, on all
    139 company pages and the universe page.
  - Placement: since my last pass, someone has moved the self-identification sentence down to the caveats at the
    foot. "Directly after the identity paragraph and its self-identification sentence" therefore became directly
    after the identity paragraph. I did not move the self-identification sentence back.
- **Affected companies:** `DEFECT_COMPANY_TEMPLATE` adds "This company is one of them: {m} of its rows below were
  filed before a later split." It appears on exactly the 11 affected company pages.
- **Census file handling:** `load_census()` reads `split_lookahead_census.json` beside the scorecard JSON. It
  exits loudly (SystemExit) when the file is missing or a key is missing. The census sha256 is printed in the
  provenance line on every page.
- The module docstring now names the second input. The module's vocabulary test still passes.
- `bin/fs scorecard` → 140 pages written, then the landing page. Of the 140 pages, 140 carry the defect paragraph
  and 11 carry the "one of them" sentence.

### Apple's page now carries

> For each past filing of this company: what the ratified E2 model would have said, using fundamentals and prices
> dated on or before that filing date (with one known exception, the book-to-market defect stated below), and text
> labels from a labeler trained in 2026; what the stock then did over the next 63 trading sessions relative to the
> equal-weighted average of its universe peers; and whether that call was right. Out-of-fold, backtested and
> hypothetical; price return only; no money invested; descriptive only.
>
> **Known defect, found 2026-11-10. One input, book-to-market, multiplied the share count as reported at the time
> by a closing price that the price source later adjusted for every stock split up to 2026-08-24. For a filing made
> before a split, that input is therefore too large by the split factor and reflects an event that was not public
> at the filing date. Both fitted columns (the model and numeric only) were trained and evaluated with it. 251 of
> the 4481 rows in this run (11 of 139 companies) were filed before a later split of 1.8-for-1 or more; the count
> is a lower bound. How much this moved any figure on this page has not been measured; the run is ratified and is
> not re-run. This company is one of them: 12 of its rows below were filed before a later split.**

Provenance line addition: "Book-to-market census: data/f5/split_lookahead_census.json, sha256
3fac8f2457c0ef5ac146450a56c81d454ba265d076b111db111ce6bcd27b1a6c."

## Tests

- New `test_census_split_lookahead.py`: 7 tests, 7 passed.
  - synthetic: forward split, reverse split, two splits multiplying, cancelling events, a row after the last split
    and a sub-threshold move not counted, other CIK, the `shares_as_used` inversion
  - real: the JSON on disk equals a fresh `census()`; the JSON holds no call, outcome or hit-rate field
- `test_scorecard_page.py`: 25 passed.
  - existing tests now write a fixture census beside the fixture JSON
  - identity wording updated
  - new: the defect paragraph and its numbers on both page types, placed before the first `<h2>`; "one of them"
    only on the affected company; census sha in provenance; missing census → refusal (and no page written);
    incomplete census → refusal; the real Apple page carries the real census counts and 12
- Combined run of `test_report_filing.py`, `test_finscreen_cli.py`, `test_scorecard_page.py` and
  `test_census_split_lookahead.py`: 170 passed, 2 failed.
  - Both failures are `test_real_filing_renders_under_ten_seconds` (Apple 10-K and 8-K), the wall-clock timing
    test.
  - The machine was at load average ~8: another session's `pytest test_report_filing.py test_app_store.py` and a
    docker simulator were running at the same time.
  - I did not touch `report_filing.py` today. See the full-suite line below.
- Full root suite (`python3 -m pytest -q -p no:cacheprovider`), run after the combined run: **1928 passed,
  0 failed, 0 skipped, 1 warning** (the existing numpy warning), 471 s. The two timing tests passed in this run.

## Not done / for the main session

- The Wells Fargo row (and the Energy Transfer event) are probably not splits; details in A above. Should the
  page say 250 / 10 instead? That is your decision. Changing it means adding a rule for event pairs that cancel,
  and I added none because the brief says never tune.
- The template copies the 2026-08-24 snapshot date and the 1.8 threshold as the brief wrote them, but the
  threshold is filled from the census JSON. Row counts print without a thousands separator ("4481"), because they
  are copied from the JSON as they are.
- `HANDOFF.md`, `LIMITATIONS.md` and `CLAUDE.md` show modifications in git status. They are not mine (the main
  session's).
