# FIXES: disclosure lead, E2 line, watchlist refresh (2026-11-05)

Builder (Opus), applying the main session's dispositions of `REVIEW_disclosure_refresh_2026-11-05.md`.
Finding numbers below are the reviewer's. Nothing is committed. I did not run `bin/fs report`, `label_filing.py` or `ingest_one.py`, and did not touch `data/app/companies/`, `data/app/reports/`, `WATCHLIST_DONE.tsv`, `WATCHLIST_BUILD.log`, `HANDOFF.md` or `RESUME_HERE.md`. The chain (pid 22969) was alive throughout. It still reads the old script inode 38946315; the new script is inode 39021263, put in place with a `.new` file and `mv`.

## Result

`/Library/Developer/CommandLineTools/usr/bin/python3 -m pytest -q -p no:cacheprovider test_report_filing.py test_finscreen_cli.py test_run_watchlist.py test_app_store.py`
→ **233 passed, 0 failed, 0 skipped in 219.96 s** (was 225 before this pass).

`plutil -lint data/app/launchd/com.finscreen.watchlist-refresh.plist` → OK.

### Rendered lead, verbatim

From `disclosure_html(load_disclosure(), None)`. **139 words**; the test bound is 80–140.

> Every label on this page was written by a small model the owner runs locally; no person read these passages. In a 337-passage spot-check its sentiment labels agreed with a model-consensus reference about 87% of the time, a level the pre-registered check rated indeterminate (agreement between models, not a human check); on its own held-out evaluation it missed about 47% of the passages that evaluation's reference marked negative. Most passages give no guidance at all; the model's guidance-direction figures and the caveats that must travel with them are in the list below. Red flags are experimental: do not rely on them. These labels have not been shown to say anything about future stock prices, and nothing here is a recommendation to buy, sell or hold. Warnings specific to this company and this filing, if any, follow in the list.

### Rendered predictive-validity sentence, verbatim

> E1 (25 companies): no fold-robust text signal (+0.0177 raw / -0.0097 dedup IC delta); E2 (139 companies, 33 walk-forward quarters, pre-registered, run 2026-11-05): bounded null — +0.0011 mean per-fold dedup IC delta, 90% CI [-0.0234, +0.0256], equivalent to zero at the 0.04 margin the ratified ladder reached (honest MDE 0.0416; equivalence not reached under about 32 of 100 nuisance seeds); text is not used as a signal; the study is written up and closed. E1 and E2 deltas are not numerically comparable.

## Where I departed from the brief's wording

1. **The lead says "that evaluation's reference", not "the reference".** "The reference" right after "a model-consensus reference" reads as the same rater. That is exactly the merger finding 3 flagged: the 47% is measured against the v1.2 eval's teacher labels.
2. **The verdict is read from the artifact.** The lead renders `{verdict}`, which is `d["sentiment"]["verdict"].lower()` and comes out as "indeterminate". It is not typed as a literal, so the template holds no ruled word that could drift from `results_g2.json`.
3. **I dropped "This page is a reading aid for the owner's own research." from the lead.** With the mandated sentences added, the lead came to 150 words and broke the 140-word bound. That sentence repeats the identity line printed directly above the lead ("A personal filing-reading aid for one user …"). Without it the lead is 139 words. I did not raise the bound.
4. **The E2 line says "about 32 of 100".** F6 marks the count as approximate, in both the table row ("About 32 of 100 … (approximate)") and §1.4, so the line keeps the "about" (rule 4).
5. **The stale-lock command is `rm -r data/app/status/.chain.lock`, not `rmdir`.** The lock directory holds a `pid` file, so a bare `rmdir` would fail.

## What changed, file by file

### `finscreen.py`: MUST-FIX 1
- Line 6: usage docstring line for `--refresh`.
- Lines 111-115: comment, plus `if not a.refresh and …` on the per-form skip.
- Lines 256-257: the `--refresh` argparse flag.
- Labeling still skips when the chunks sha equals the labels sha (`labels_fresh`, unchanged).

### `report_filing.py`
- **E2 line (findings 8, 9, 10).** `PREDICTIVE_VALIDITY_TEMPLATE` (326-334) now carries the honest MDE, the seed count, the rest of the §13 branch row ("the study is written up and closed") and the E1/E2 incomparability sentence. New constants `E2_HONEST_MDE = 0.0416`, `E2_SEEDS_NOT_EQUIVALENT = 32` and `E2_SEEDS_N = 100` (351-357), with a comment. The format call is at 582-585.
- **Lead (MUST-FIX 2, findings 3, 4, 5, 7).** `PLAIN_ENGLISH_TEMPLATE` (403-422) has the new sentiment sentence, the qualitative guidance sentence (no `{guid}` or `{active}`), and the closing warnings sentence. A comment states why it quotes no guidance figure. The format call (1572-1574) now passes `n`, `sent`, `verdict` and `miss`.

### `test_report_filing.py`
- **Header test (786-793).** `test_disclosure_header_renders_every_ruled_number` adds the tokens "honest MDE 0.0416", "about 32 of 100 nuisance seeds" and "E1 and E2 deltas are not numerically comparable".
- **Figures test (861-878).** `…figures_are_read_from_the_artifacts` checks the n, sentiment pct, verdict and missed-negatives (n=337, 87%, indeterminate, 47%). It checks that they move when the dict moves, and that no literal digit remains in the template once every field form is stripped.
- **New test (881-893).** `…lead_quotes_no_guidance_figure` checks:
  - neither 96.6/97 nor 68.7/69 appears in the lead;
  - there is no `{guid`/`{active` in the template;
  - the qualitative sentence and the warnings sentence are present.
- **Banned-word test (896-).** "accuracy" is added to the list. It asserts "model-consensus reference" and "agreement between models, not a human check", and that "held-out" appears exactly once, after "spot-check".
- **F6 pin test (1005-1033).** `test_e2_ic_numbers_match_the_f6_write_up_they_came_from` uses regexes on the exact F6 rows: `| status; honest MDE (2.8 × SE) | **POWERED; 0.0416**` and `| TOST at ±0.04 | … About 32 of 100 nuisance seeds would not reach equivalence (approximate)`. The pins are against the same sha `06b86611…`, which is unchanged.
- **One-constant test (1041-1055).** `test_predictive_validity_is_one_replaceable_constant` now requires the line to end with `not numerically comparable.` and to contain the full §13 clause.

### `test_finscreen_cli.py`
- **Lines 131-141.** New `test_report_refresh_reingests_a_current_store`. On a store with `per_form == 2` and labels marked current, `report SIRI --refresh` runs `ingest_one --ticker SIRI --per-form 2` and then `--fundamentals`, and still does not label. On the old code it fails: argparse rejects `--refresh`.

### `data/app/run_watchlist.sh`
Replaced via `.new` + `mv`.
- Header comment lines 6-11 now describe what happens.
- Usage check: anything other than no argument or `--refresh` logs `REFUSED: usage: …` to stderr and the log, and exits 2.
- `mkdir data/app/status/.chain.lock` lock: on refusal it logs the holder's pid from `.chain.lock/pid` and exits 2. A `trap` removes the lock on EXIT, and is set only after our own `mkdir` succeeds, so a refused run never removes someone else's lock.
- `REFRESH_FLAG` is passed through: `bin/fs report "$T" $REFRESH_FLAG … < /dev/null`.
- Order: usage → bin/fs check → lock → process guard → archive → loop.

### `test_run_watchlist.py`
- The refresh test asserts `stub fs report AAA --refresh`; the plain run asserts no `--refresh`.
- New tests:
  - `test_a_held_lock_refuses_and_runs_no_ticker`: exit 2, logged pid, no ticker run, the foreign lock untouched.
  - `test_the_lock_is_gone_after_a_normal_run`.
  - `test_an_unknown_argument_is_a_usage_error`: 3 cases.
  - `test_a_ticker_run_cannot_swallow_the_watchlist`: a stub `bin/fs` that runs `cat`.
- The plist test expects caffeinate and no `ProcessType`.
- Mutation check: a copy of the script without `< /dev/null` fails the stdin test, and a copy without the `$REFRESH_FLAG` pass-through fails the refresh test.

### `data/app/launchd/com.finscreen.watchlist-refresh.plist`: finding 12
- `ProgramArguments` = `/usr/bin/caffeinate -dims /bin/bash …/run_watchlist.sh --refresh`.
- `ProcessType` removed.
- `plutil -lint` OK.

### `data/app/launchd/README.md`
- **Lines 3-15.** The refresh paragraph now says what happens:
  - `--refresh` re-ingests, keeping the newest two per form, with submissions cached at most 24 h;
  - it refreshes fundamentals;
  - it labels only if the chunk table changed, and the journal skips passages already labeled;
  - the store is a rolling window;
  - the lock refusal is described.
- **Lines 36-38.** These keep only "If the Mac is asleep at 03:00, launchd runs the job at the next wake …".
- **Lines 40-45.** New lock paragraph, ending in the hand-removal command.

### `.gitignore`
- Lines 157-160, in the App lane block: a comment plus `data/app/status/launchd.*.log` and `data/app/status/.chain.lock/`. Checked with `git check-ignore -v`.

## MUST-FIX 1: is `ingest_one.py` idempotent? Yes.

What re-ingesting an existing store does:
- `write_metadata_db` unlinks `metadata.db` and rebuilds it. Rows use `INSERT OR REPLACE` on a fresh DB, so nothing is duplicated.
- `sections.parquet` and `chunks.parquet` are rewritten whole.
- `manifest.json` is rewritten, and the previous `fundamentals` block is carried forward (ingest_one.py ~995-1000).
- Submissions use a 24 h TTL cache (`edgar_client.get_submissions`), and documents are cached forever, so an unchanged company costs only the submissions fetch.

Checked: is the chunk sha byte-deterministic? I rebuilt store 764630's chunks from its own `sections.parquet` into the scratchpad with `ingest_one.build_chunks`. The sha came out `2eb5d897c140ed49…`, equal to the manifest's sha, and the sections sha also matched the manifest. So with unchanged sections, labeling is skipped. Not verified: that extraction is byte-deterministic across a re-ingest. I found no timestamp in the extract path.

What a new filing costs: `label_filing` resumes from the store's journal keyed by `chunk_id`, a content hash of the paragraph ids, so only new passages are generated. If nothing is left to do, it returns before loading the model.

Residual risk, a loud failure rather than silent corruption: `chunk_id` hashes normalized paragraph text, but the prompt hashes the raw passage. If a rolling window moves a paragraph's home occurrence to a filing whose raw text differs only in whitespace, `label_e2.select_rows_to_generate` hard-stops with "Move the journal aside". That ticker would then log a non-zero exit in the refresh. I have not seen it happen.

Rolling window: a filing that drops out of the newest two leaves the store. Its old HTML under `data/app/reports/` stays on disk, and the README says so.

## Not done / for the main session

- `HANDOFF.md` §3's 2026-11-05/06 entry ("a run with nothing new labels nothing") was not edited, as instructed. It should now say that refresh passes `--refresh`, which re-ingests.
- CLAUDE.md:45 and RESUME_HERE.md:91 still give the bare pgrep pattern (finding 19); those are main-session doc edits.
- "Most passages give no guidance at all" is the brief's qualitative wording and has no measurement beside it in the lead. The list below carries the NONE-mass and imputation figures.
- The NOTE items the brief said to log only (14, 15, 18, 20-23) were left as they are. `FS_SKIP_PROCESS_GUARD` is unchanged.
- The currently running chain (old inode) holds no lock. The lock protects only chains started from the new script.
