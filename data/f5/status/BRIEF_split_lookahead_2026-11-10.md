# Builder brief — 2026-11-10 — census of the book-to-market split look-ahead, and its disclosure on the scorecard pages

Read `CLAUDE.md`, then `data/f5/status/REVIEW_p5_packet_2026-11-10.md` (finding M3 and the main-session
verification). Interpreter `/Library/Developer/CommandLineTools/usr/bin/python3`. **No model is fit, no runner is
run, nothing frozen or ratified is modified** (`numeric_features_e2.py`, its parquet, the G3 pin and outputs stay
byte-identical — the defect is recorded and disclosed, not patched). No network, no labeler. No commit. Report to
`data/f5/status/SPLIT_LOOKAHEAD_2026-11-10.md` before returning.

## A. `data/f5/census_split_lookahead.py` (new, read-only) → `data/f5/split_lookahead_census.json` (tracked)
Prototype (main session, verified against real splits): `/private/tmp/claude-501/-Users-vihanpatil-personal-projects-FinScreen/b1acb085-fa23-49b9-a362-5eb82a8604f6/scratchpad/split_census.py`.
Method: from `data/f5/numeric_features_e2.parquet` and `data/prices_e2.parquet`, shares-as-used = equity /
book_to_market / close at `pre_session` (equity = `equity_to_assets` × exp(`log_total_assets`)); one value per
(cik, filing_date) (median); a ratio ≥ 1.8 or ≤ 1/1.8 between consecutive filing dates of a company is a
split-like event; a row is "before a later event" when the product of the ratios of events dated after its filing
date is ≥ 1.8 or ≤ 1/1.8. Count over the deduplicated rows of `data/f5/head1_oof_predictions.parquet` (`in_dedup`,
per block). The JSON holds: method text, threshold, input sha256s, the events (cik, filing date first showing it,
ratio), `n_rows`, `n_rows_before_later_event`, `n_companies`, `n_companies_affected`, and per affected CIK its
row count. **It holds no call, no outcome and no hit rate** (the repository is public; legal baseline #4). A
`--show-private` flag prints, to stdout only, the calls and hit rate on affected versus other rows per block.
Main-session numbers to confirm or dispute (report a difference, never tune toward them): 15 events in 12
companies; 251 of 4,481 rows; 11 of 139 companies.
Test `test_census_split_lookahead.py`: synthetic unit tests of the event detection and the later-factor rule
(forward split, reverse split, two splits, a row after the last split is not counted); and, when the real
artifacts are on disk (skip otherwise), the JSON on disk equals a fresh computation.

## B. `scorecard_page.py`: the pages must stop claiming what is now known to be false
- Identity paragraph: replace "using fundamentals and prices as they were public at that filing date" with
  "using fundamentals and prices dated on or before that filing date (with one known exception, the
  book-to-market defect stated below)".
- Directly after the identity paragraph and its self-identification sentence (not down in the list), on every
  company page and the universe page, a paragraph from a module template filled from the census JSON:
  "Known defect, found 2026-11-10. One input, book-to-market, multiplied the share count as reported at the time
  by a closing price that the price source later adjusted for every stock split up to 2026-08-24. For a filing
  made before a split, that input is therefore too large by the split factor and reflects an event that was not
  public at the filing date. Both fitted columns (the model and numeric only) were trained and evaluated with it.
  {n} of the {total} rows in this run ({k} of {K} companies) were filed before a later split of 1.8-for-1 or more;
  the count is a lower bound. How much this moved any figure on this page has not been measured; the run is
  ratified and is not re-run." On a company page whose CIK is in the census: add "This company is one of them:
  {m} of its rows below were filed before a later split."
- The module reads the census JSON beside the scorecard JSON, prints its sha256 in the provenance line, and
  refuses to render (SystemExit, loud) when it is missing. The module's vocabulary test must still pass.
- Tests in `test_scorecard_page.py`: fixture census; the paragraph and its numbers on both page types; the
  "one of them" sentence only on an affected company; missing census → refusal; identity wording.
## Finish
Run the census, `bin/fs scorecard`, the targeted tests and the full root suite; report counts, the exact
paragraph Apple's page now carries, and anything undone.
