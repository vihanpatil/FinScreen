# Builder brief — 2026-11-09 — three app-lane changes (main-session decisions, no owner word needed)

Read `CLAUDE.md` first. Interpreter: `/Library/Developer/CommandLineTools/usr/bin/python3`. Nothing frozen is
touched; no labeler runs (rule 6: never start one; nothing is alive now); $0; no network except none.
Write your completion report to `data/app/status/SCORECARD_PAGES_2026-11-09.md` before returning.

Why: the owner's stated value (2026-09-11, verbatim in RESUME_HERE.md) is the per-company, per-quarter
historical scorecard. It exists — `data/f5/head1_scorecard.json` (ratified G3 run, 139 companies, 4,481 filings,
git-ignored) — but only as a 567 KB markdown nobody opens. 24 of the 30 watchlist companies (Apple, Google,
Microsoft, Amazon, Meta, Nvidia, …) are in it. Meanwhile Apple's rendered page says it is "outside the
244-company research universe", which is false, and there is no landing page: the owner has to know a CIK.

## Change 1 — the false disclosure line (`report_filing.py`)

`OUTSIDE_UNIVERSE_LINE` is emitted whenever `ACTIVE_STORE is not None` (≈ line 1559), i.e. on every store page.
Membership truth: `data/filings_metadata_e2.db`, table `universe_membership` (244 distinct `cik`; Apple 320193 is
one). Fix: a small cached reader `universe_member_ciks()` (sqlite, read-only, one query); emit the OUTSIDE line
only when the store's CIK is not a member. For a member emit instead one sentence, e.g. `IN_UNIVERSE_LINE =
"This company is in the 244-company research universe; the passages on this page were ingested and labeled now,
outside the sealed corpus, and were not themselves spot-checked"`. If the db is absent (unit tests, another
machine) keep today's behaviour (emit OUTSIDE) — conservative, never silent. Tests in `test_report_filing.py`:
member → IN line and no OUTSIDE line; non-member → OUTSIDE line; db absent → OUTSIDE line (monkeypatch the path
or the reader). Do NOT re-run ingest or the labeler to re-render; re-render Apple's index page directly:
`python3 report_filing.py --store data/app/companies/320193 --index` and confirm the line changed.

## Change 2 — the landing page (`finscreen.py`)

`bin/fs index` (cmd_index) additionally writes `data/app/reports/index.html` (the directory is git-ignored):
one table of every store that has a rendered `<cik>/index.html`, **sorted alphabetically by ticker, never by any
label- or scorecard-derived quantity**; columns: ticker, company name, CIK, pages rendered, link "labeled
filings" → `<cik>/index.html`, and — only when `<cik>/scorecard.html` exists — a link "historical scorecard
(personal use only)". No number from the scorecard appears on the landing page (it may be shown as a demo under
ruling C; scorecards may not — see change 3). Reuse `report_filing.page`, `CSS`, `esc`, `FOOTER_LINE`. `bin/fs
report` calls the same writer after its pages are written so the landing page is always current; `bin/fs
index` prints its path. Tests in `test_finscreen_cli.py` with a tmp REPORTS/COMPANIES (alphabetical order;
scorecard link only when the file exists; no digits-with-percent from a scorecard).

## Change 3 — scorecard pages (new small module `scorecard_page.py`, app lane)

Reads ONLY `data/f5/head1_scorecard.json` (structure: `universe{generated_utc, blocks{text_and_numeric,
numeric_only, size_only}, n_filings_scored, n_companies, n_test_quarters, outcome_mix_positive_excess,
outcome_mix_label, chance_sentence, call_rule, tie_rule, correct_rule, ci, scope_sentence, inference_sentence,
prices_sentence, arm, eval_set, min_calls_for_company_hit_rate, disclosures{8 keys}, margin{status,
delta_selected, note}, files}`, `companies[139]{cik, name, ticker|null, summary{n_rows, n_calls, n_correct,
n_outperform, n_underperform, hit_rate|null, wilson_lo, wilson_hi, n_no_call, n_tied_no_call, n_unresolved,
chance_sentence, denominator, outcome_mix, n_filings, min_calls_for_hit_rate, block}, rows[]{test_quarter,
form, filing_date, accession_number, excess_return_pct, text_and_numeric_call, text_and_numeric_result,
numeric_only_call, numeric_only_result, size_only_call, size_only_result}}`).
**It computes nothing. Every number on a page is copied from the JSON; no counting, no averaging, no sorting by
a number.** Never opens the parquet. Prints the JSON's sha256 on every page as provenance (the E1 pattern).

Writes, deterministic (no wall clock; quote `generated_utc`):
(a) `data/app/reports/<cik>/scorecard.html` for EVERY company in the JSON (139; create the directory when no
store exists). Order on the page: (1) header — title "<name> (<ticker>) — historical scorecard, E2 head 1"
(ticker from the JSON, else from the store manifest `data/app/companies/<cik>/manifest.json` key `ticker` if
present, else none); one identity paragraph true of the page: what the ratified E2 model would have said about
each past filing using only data public at that filing date, what the stock then did over the next 63 sessions
relative to the equal-weighted universe peers, and whether the call was right; out-of-fold, backtested,
hypothetical, price return only, no money invested, descriptive only; then verbatim `scope_sentence`,
`inference_sentence`, `prices_sentence`, `margin.note`, and the E2 outcome sentence — import the pinned
constants from `report_filing` (`PREDICTIVE_VALIDITY_TEMPLATE` and its figures) rather than retyping. (2) the
summary from `summary`: rows, calls, correct, hit rate with the Wilson interval, `chance_sentence`,
`denominator`, outcome mix; when `hit_rate` is null print "no hit rate: N calls, fewer than the 6 the
pre-registration requires" (6 from `min_calls_for_hit_rate`). (3) the per-filing table in the JSON's row order:
quarter, form, filing date, excess return (%, 2 dp, signed), the model, numeric only, size only — each cell
"<call> (<result>)" or "no call", as `head1_scorecard.md` prints them; link the accession to
`<accession>.html` only when that file exists in the same directory. (4) the 8 disclosures verbatim from
`universe.disclosures`, non-collapsible, under "Disclosures — these travel with every number on this page".
(5) footer `SCORECARD_FOOTER_LINE = "Rendered for the author's personal use only. Not for sharing, not even as
a demonstration: a per-company historical scorecard stays off every shared surface until the items in
data/legal/ are cleared."`
(b) `data/app/reports/scorecard.html` — the universe page: the three blocks from `universe.blocks` as a table
(n calls, outperform, underperform, correct, hit rate, interval, chance, no call (tied), unresolved), the
universe `chance_sentence`, outcome mix with its label; then ALL 139 companies **alphabetical by name**, one row
each: name, ticker, CIK, n calls, n correct, hit rate [lo, hi] or "no hit rate (N calls < 6)", link to the
company page; one sentence that 139 of the 244 universe companies appear and the rest are absent for
outcome-correlated reasons stated in the disclosures (price censoring 31 of 244 — quote from `prices_sentence`;
never invent a further decomposition); then the 8 disclosures; then the footer.
CLI: `python3 scorecard_page.py` renders everything, `--cik N` one company; `bin/fs scorecard` subcommand runs
it (add to the `finscreen.py` usage text). Reuse `page`, `CSS`, `esc` from `report_filing`.
Vocabulary: the module's OWN strings never contain advice, recommend, buy, sell, should, signal, predict,
rank, score (a test asserts this over the module's constants; the JSON's verbatim disclosures are exempt).
Tests `test_scorecard_page.py`: a 2-company fixture JSON (one with hit_rate null) → both pages + universe page
render; the hit-rate string equals the fixture's value to 4 dp; null → the "no hit rate" text; company order
alphabetical by name; all 8 disclosure texts present on every page; footer present; the sha256 line matches the
fixture file; accession linked only when the file exists; vocabulary test. One test that, if the real JSON is
on disk (skip otherwise), renders Apple and finds "20" correct of "28" calls and "0.7143".

## Finish
Run `python3 -m pytest -q -p no:cacheprovider test_report_filing.py test_finscreen_cli.py test_scorecard_page.py`,
then the full root suite (`-m pytest -q -p no:cacheprovider`, ~5 min; report the count). Render everything:
`python3 scorecard_page.py`, `bin/fs index`. Report: files changed, tests added/passed, the exact lines
Apple's page now carries, paths of the pages, anything you left undone. No commit (the main session commits).
