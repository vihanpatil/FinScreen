# SCORECARD_PAGES_2026-11-09 — builder completion report

Brief: `data/app/status/BRIEF_scorecard_pages_2026-11-09.md`. Status: all three changes DONE and rendered.
Nothing committed (the main session commits). Nothing frozen touched. No labeler or ingest started (rule-6 check
empty before every render); no network; $0; backtest_e2.py / heads_e2.py never run.

## Files changed

- `report_filing.py` (change 1, plus one small helper)
  - `IN_UNIVERSE_LINE` (the brief's wording, verbatim), `UNIVERSE_DB = data/filings_metadata_e2.db`,
    `universe_member_ciks()` (read-only sqlite, one `SELECT DISTINCT cik FROM universe_membership`, cached per
    path with lru_cache; returns None when the db is absent), `store_universe_line()` (IN only when the store
    manifest's cik is a member; OUTSIDE otherwise, including when the db is absent).
  - `disclosure_html` now emits `store_universe_line()` where it used to emit `OUTSIDE_UNIVERSE_LINE` (still only
    when a store is active; the research-corpus path is unchanged).
  - `predictive_validity_sentence()`: the existing `PREDICTIVE_VALIDITY_TEMPLATE.format(...)` call moved out of
    `load_disclosure` into a function so `scorecard_page.py` imports the E2 outcome sentence instead of copying it.
    Output is the same.
  - Module docstring and the `--store` help text updated so they describe the IN/OUTSIDE behaviour.
- `scorecard_page.py` (NEW, change 3). Reads only `data/f5/head1_scorecard.json`; copies every number from it;
  rows stay in JSON order; the only ordering it applies is alphabetical by company name. Prints the JSON's full
  sha256 and `generated_utc` on every page; uses no wall clock. Reuses `RF.page/esc/CSS`,
  `RF.predictive_validity_sentence()`, `scorecard_e2.DISCLOSURE_ORDER` (the 8 disclosure labels), and
  `controls.HOLDING_DAYS` (63) for the identity paragraph, so neither number is typed into the module. Exits loudly
  if the JSON is missing, if any of the 8 disclosures is missing, or if `prices_sentence` no longer contains
  "N of M universe members without usable prices" (the universe page quotes that clause instead of typing 244/31).
  Ticker: from the JSON, else from the store manifest, else none. When `hit_rate` is null (26 companies) a
  company page prints only "no hit rate: N calls, fewer than the 6 the pre-registration requires", plus the
  denominator and outcome mix. Like the md it has no numerator and no chance line, because the chance line would
  give away the withheld rate. CLI: `python3 scorecard_page.py [--cik N]`.
- `finscreen.py` (change 2): `write_landing()` writes `data/app/reports/index.html`: one row per store with a
  rendered `<cik>/index.html`, sorted by ticker; columns ticker, company, CIK, pages (html files excluding
  scorecard.html), links "labeled filings" and, only when `<cik>/scorecard.html` exists, "historical scorecard
  (personal use only)". When `reports/scorecard.html` exists there is one extra link to it (no number). The page
  reuses `RF.IDENTITY_LINE` and `RF.FOOTER_LINE`. `report_filing` is imported lazily so `doctor` does not need
  pandas. `cmd_index` and `cmd_report` both call it and print its path. New `bin/fs scorecard [--cik N]` runs
  `scorecard_page.py` as a subprocess and then refreshes the landing page. The usage docstring was updated.
- `test_report_filing.py`: +4 tests (member → IN and no OUTSIDE; non-member → OUTSIDE; db absent → OUTSIDE and
  reader returns None; real db has 244 members including 320193, skipped if the db is absent).
- `test_finscreen_cli.py`: +4 tests (landing page sorted by ticker, store with no pages not listed, scorecard
  link only when the file exists, no `\d%` and no `\d.\d\d` number in the page body; `index` writes it; `report`
  refreshes it; `scorecard` runs the writer).
- `test_scorecard_page.py` (NEW): 13 tests (all 3 pages render, manifest ticker fallback; hit rate to 4 dp on the
  company and universe pages; null → the no-hit-rate text and no chance line; alphabetical by name; all 8
  disclosures inside a non-`<details>` section plus the footer on every page; the run's sentences and the E2
  outcome sentence quoted verbatim; sha256 line equals the fixture's sha; accession linked only when its page
  exists; signed 2-dp excess return and cell format; deterministic re-render; a missing disclosure refuses; a
  vocabulary scan with AST over every string literal in the module; real-JSON Apple check: "20 of 28 calls
  right" and "0.7143").

## Commands run and output

- `python3 report_filing.py --store data/app/companies/320193 --index`: the page is written. A diff against the
  old copy changes exactly one line (OUTSIDE → IN).
- I also re-rendered every other existing page of the 28 member stores with `report_filing.py --store ...
  --index` and `--accession <acc>`, one process per page, no labeler or ingest. That is 104 pages. For every page
  the diff against the old copy was exactly that one line. The brief named only Apple's index page; I did the
  rest so 26 other member companies would not keep the false line. The 16 non-member stores still carry OUTSIDE,
  which is correct. Every store's manifest `in_research_universe` agrees with the db.
- `python3 scorecard_page.py` → "140 pages written" (139 `data/app/reports/<cik>/scorecard.html` + universe
  `data/app/reports/scorecard.html`, ~1 s).
- `bin/fs index` → table + "landing page: .../data/app/reports/index.html"; 31 rows; 24 company scorecard links
  + 1 universe link; no number found by the regex check in the body.
- Targeted tests: `pytest test_report_filing.py test_finscreen_cli.py test_scorecard_page.py` → **150 passed**.
- Full root suite: `python3 -m pytest -q -p no:cacheprovider` → **1903 passed, 0 failed, 0 skipped, 1 warning**
  (the existing numpy RuntimeWarning in test_ingest_prices), 327 s.

## Apple's pages now carry

- Store pages (index + labeled filings), disclosure block: "This company is in the 244-company research universe;
  the passages on this page were ingested and labeled now, outside the sealed corpus, and were not themselves
  spot-checked."
- `data/app/reports/320193/scorecard.html` summary: "The model: 20 of 28 calls right (26 outperform peers, 2
  underperform peers) over 34 rows; hit rate 0.7143, 95% Wilson interval [0.5294, 0.8475]." plus the JSON's
  chance sentence (0.622 from call counts), denominator and outcome mix 0.6176 over 34 filings. The 8 disclosures
  appear verbatim under "Disclosures — these travel with every number on this page", and the footer is
  SCORECARD_FOOTER_LINE.

## Not done / for the main session

- Two orphan Apple pages, `data/app/reports/320193/0000320193-24-000123.html` and `0000320193-25-000007.html`,
  are no longer labeled filings in the store, so `report_filing` refuses to re-render them ("not a labeled filing
  of CIK 320193"). They still carry the old OUTSIDE line, and the Apple scorecard page links 24-000123 because
  the file exists. I did not delete them because deleting is irreversible. The decision belongs to the main
  session. My recommendation: delete both; they are git-ignored outputs.
- `label_filing.py`'s `OUTSIDE_UNIVERSE_CAVEAT` (written into label manifests) still says "outside" for every
  store. The brief scoped only `report_filing.py`, so I left it alone.
- Possible identity problem: store `XOM` is CIK 2115436, which is not in the universe; ExxonMobil's historical
  CIK is 34088. It may be a new holding-company CIK or a wrong-company resolution. Worth checking with the
  dead-member ticker rule in mind. I did not investigate.

## Fix pass (2026-11-09, after REVIEW_scorecard_pages_2026-11-09.md)

Applied only the items the main session marked FIX: MF1, MF2, S3–S7, N8–N10. N11–N15 are untouched. Nothing
committed; no labeler or ingest started (rule-6 check empty); no network.

- MF1 `scorecard_page.py`: the identity paragraph now reads "using fundamentals and prices as they were public at
  that filing date, and text labels from a labeler trained in 2026". It is followed by `SELFID_TEMPLATE`, built
  from the imported `RF.SELFID_STRICT_TEXT`, `RF.SELFID_LOOSE_TEXT` and `RF.SELFID_SUBJECT` (26.8% / 46.0%, E1,
  not re-measured on E2), and states that the look-ahead channel exists and that how often it was used is not
  known.
- MF2: `COVERAGE_TEMPLATE` uses the coordinator's wording. Price censoring is quoted from `prices_sentence`; the
  extraction-coverage cause is named; the sentence says the rest are not decomposed here. No new count.
- S3: `CALL_RULE_TEMPLATE` is a new paragraph above the filing table. I checked it against
  `scorecard_e2.make_calls` and the session chain in `target_e2.py`. It covers: the top and bottom thirds of that
  quarter's out-of-fold outputs, per block; the middle third and straddling tie groups are "no call" and leave the
  denominator; a zero excess is never right; info date = max(filing date, acceptance date in ET); the news session
  is the first session on or after it, or after it when acceptance was at or after 16:00 ET; the window opens one
  session AFTER the news session and runs 63 sessions (`controls.HOLDING_DAYS`, imported); it is a within-quarter
  statement relative to peers, never a real-time one.
  - Correction to the coordinator's paraphrase: the window does not open "on the first session after the filing
    was public". It opens one session after the news session (`window_open = news_session + 1`).
  - Wording constraint: the text says "model output" rather than "prediction", because the module's
    vocabulary test refuses predict*/score*.
- S4 `report_filing.py`: `IN_UNIVERSE_LINE` = "This company is or was a member of the 244-company point-in-time
  research universe; the passages on this page were ingested and labeled now, outside the sealed corpus, and were
  not themselves spot-checked". The member test asserts that wording.
- S5 `finscreen.py`: the landing page no longer uses `RF.IDENTITY_LINE`. It now carries `LANDING_IDENTITY`: "The
  owner's private home page for FinScreen. Only the per-company reading-aid pages ("labeled filings") may be shown
  to someone else, as a demonstration (ruling C); the historical scorecard pages are for the owner's personal use
  only and are never shown." Its footer is `scorecard_page.SCORECARD_FOOTER_LINE`, imported lazily. The links are
  kept.
- S6: every company page now has "Universe, for comparison" (`blocks_html`) plus the universe chance sentence,
  placed between the summary and the filing table.
- S7 tests: the fixture gives each block its own call/result on every row and its own universe-block figures. The
  test now asserts per-column cell order, so a column swap fails. Fixture CIKs are 222 (Zeta) and 333 (Alpha), so
  CIK order and JSON order are both opposite to name order. The dead `n/a` branch in `cell()` is removed.
- N8: `LINKED_PAGES_LINE` sits above the table: "A linked accession opens a reading-aid page whose labels were
  produced now (2026-11) for the reading aid, not the sealed-corpus labels this run used." I wrote "used" rather
  than "scored" because of the vocabulary test.
- N9: `calls()` pluralises; the pages now read "no hit rate: 1 call, …" and "(1 call < 6)".
- N10: the sqlite connection now uses `Path(db).resolve().as_uri() + "?mode=ro"`.
- New tests in `test_scorecard_page.py`: universe blocks on every page; call-rule paragraph and linked-pages line;
  identity scope and self-identification; coverage wording; singular "call". `test_finscreen_cli.py` now checks
  the landing identity and footer. `test_report_filing.py` checks the "is or was" wording.

Re-render and test results:
- `python3 scorecard_page.py` → 140 pages.
- Re-rendered all 104 existing pages of the 26 member stores (index and accession pages, `report_filing.py --store
  …`) with 0 failures. 104 pages carry "is or was a member"; 0 carry the old "is in" wording. The 16 non-member
  stores keep OUTSIDE.
- `bin/fs index` → landing page: 31 rows, 24 company scorecard links + 1 universe link, no number in the body.
- Targeted: 155 passed.
- Full root suite: **1908 passed, 0 failed, 0 skipped, 1 warning** (322 s). This run came before a one-clause
  wording fix to S3 (news session = "first session on or after that date"). After that fix the scorecard pages
  were re-rendered and the targeted suite re-ran with 155 passed.

Correction to the first report: there are 26 member stores, not 28. The main session has archived the two
orphan Apple pages.
