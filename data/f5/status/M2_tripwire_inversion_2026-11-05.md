# M2 — tripwire inversion after the G3 pin (2026-11-05)

Builder report. Brief: reviewer finding M2 (`data/f5/status/REVIEW_g3_run_2026-11-05.md`).
Not committed. Only test files changed: no change to `pin_g3.py`, `backtest_e2.py`,
`heads_e2.py` or any other non-test file. No test deleted. The real `data/f5/G3_RATIFIED.json`
and `data/f5/G3_PREREGISTRATION.md` were only read; their sha256 was checked before and
after every run (both OK).

## What was red, and why

The three named files had **12** failures, not 5. All had the same cause: the pin now exists
and the real document is the pinned one.
- 5 tests asserted the pin was absent (the reviewer's list, plus `test_backtest_e2.py:710` and `:892`).
- 6 `test_pin_g3.py` procedure tests copied the real (now pinned) document as their
  "unpinned" scratch, so substitution (a) matched 0 times.
- The full suite found a 13th of the same kind, outside the three files:
  `test_scorecard_e2.py::test_scorecard_is_written_after_the_margin_block` asserted that
  `data/f5/head1_scorecard.md` and `head1_oof_predictions.parquet` were absent. The real run
  wrote them, and they are **git-excluded**, so an agent that "fixed" the test by deleting
  them would lose real head-1 output that git cannot restore. I inverted it the same way (see
  below) and am flagging it because the brief did not name it.

Every inverted assertion uses this failure message: *"data/f5/G3_RATIFIED.json is the
owner's G3 ratification (word 'ratify', HANDOFF §3 2026-11-05). It and
data/f5/G3_PREREGISTRATION.md must NEVER be deleted, edited or re-written: re-pinning is
forbidden (it would be a new pre-registration). If this fails, restore both files from git
commit fa9f5d9 and stop -- do not 'fix' this test."*

The shared invariant, `assert_real_pin_intact()` (defined in `test_backtest_e2.py` and in
`test_heads_e2.py`, and inline in `test_pin_g3.py`), checks:
- the pin exists;
- `doc_sha256` equals the literal `6b99f65e…` (this catches a re-pin);
- `doc_sha256` equals the measured sha256 of the document (this catches an edit);
- `owner_word == "ratify"`;
- `handoff_entry == "2026-11-05"`.

## Tests changed (old assertion → new)

### `test_backtest_e2.py`
1. `test_real_run_refuses_today` is renamed `test_real_pin_is_intact_and_an_unpinned_main_refuses`.
   - Old: `assert not G3_RATIFIED_PATH.exists()`, then `main([]) == 2` at the real paths.
   - New: `assert_real_pin_intact()`, and `require_g3()` at the real paths returns `6b99f65e…`.
   - The pre-pin refusal is kept. `E.load_g3_params` is monkeypatched to the real document plus
     an absent tmp pin, then `main([]) == 2`, "BLOCKED" and "no IC was computed".
   - `load_analysis_frame` and `run_head1` are booby-trapped (they raise if reached), so a
     guard that wrongly passes cannot touch real data. A monkeypatched path constant alone
     would not work here: the default arguments are bound when the function is defined.
2. `test_selftest_writes_nothing_into_the_repo_data_dir` (`:710`).
   - Old: `assert not G3_RATIFIED_PATH.exists()`.
   - New: the pin's bytes are identical before and after `selftest`, plus `assert_real_pin_intact()`.
     The `data/f5` listing check (before == after) is unchanged.
3. `test_a_fabricated_guard_dict_cannot_reach_a_fit` (`:892`).
   - Old: `assert not G3_RATIFIED_PATH.exists()`, then the forged guard is refused at the real
     paths because no pin exists.
   - New: `assert_real_pin_intact()`, then the forged guard is refused at the real paths because
     its sha differs from the real pin's. The test also asserts the message says "not a
     ratification".

### `test_heads_e2.py`
4. `test_the_real_repo_has_no_ratified_document_today` (`:201`) is renamed
   `test_the_real_pin_is_intact_and_an_unpinned_cli_refuses`.
   - Old: `assert not RATIFIED_PATH.exists()`, then `main([flag]) == 2` at the real paths.
   - New: `assert_real_pin_intact()`, and `load_ratified_params()` at the real paths returns `6b99f65e…`.
   - The pre-pin refusal is kept. `PREREG_PATH` points at a tmp copy of the real document and
     `RATIFIED_PATH` at an absent tmp file. The results and run-log paths go to tmp.
     `run_head2` and `run_head3` are booby-trapped. Then `main([flag]) == 2` for
     `--head2`, `--head3` and `--all`.
5. and 6. `test_the_runners_refuse_against_the_real_paths_today[run_head2|run_head3]` (`:1084`)
   are renamed `test_a_forged_sha_is_refused_against_the_real_pin[...]`.
   - Old: `assert not RATIFIED_PATH.exists()`, then the runner with `"0"*64` refuses.
   - New: `assert_real_pin_intact()`, then the runner with `"0"*64` at the real paths refuses,
     with "BLOCKED" and "not a ratification" in the message. `called == []` is kept.
   - The module docstring now says the pin is read (read-only) and must never be deleted.

### `test_pin_g3.py`
7. `test_the_real_ratification_file_is_absent_and_the_real_document_untouched` (`:219`) is
   renamed `test_the_real_ratification_is_intact_and_pins_the_ratified_text`.
   - Old: `assert not REAL_RATIFIED.exists()`, the real document still carries residue, and
     real document == scratch.
   - New: the pin exists. `doc_sha256` is `6b99f65e…` and matches the measured sha.
     `params_sha256` is `9ac47981…`. `owner_word` is "ratify" and `handoff_entry` is
     "2026-11-05". The path constants are unchanged, and the real document has **no** residue.
   - The new test also checks that `pinned_text(pre-pin text, "2026-11-05")` equals the real
     document byte for byte. In other words, the real document is exactly the eight declared
     substitutions applied to the reviewed draft.
8. The `scratch` fixture used to copy `REAL_DOC`, which is now pinned. It now writes the
   **pre-pin** document, which it reads offline from the local git object
   (`git show 41829ad:data/f5/G3_PREREGISTRATION.md`) and checks against sha `42348bfc…`.
   41829ad and 7608d43 (the commit just before the pin) hold the same blob.
   - This fixes, with no change to their logic: `test_the_substitution_set_leaves_no_residue`,
     `test_pin_without_an_explicit_date_refuses`, `test_pinned_scratch_copy_is_accepted_by_every_guard`,
     `test_show_is_read_only` and `test_a_bad_date_and_a_moved_document_both_refuse`.
   - I chose this over a committed fixture file so the repo has no second copy of the
     pre-registration that could be mistaken for the real one.
   - The module docstring was updated. The test still never passes `--pin` at the real paths.
     I wrote, then removed, a `PG.pin(REAL_DOC, REAL_RATIFIED, …)` "refuses to overwrite"
     check. The overwrite refusal is already covered on scratch by
     `test_an_existing_ratification_is_not_overwritten`.

### `test_scorecard_e2.py` (outside the brief's three files)
9. `test_scorecard_is_written_after_the_margin_block`.
   - Old: `assert not (F5_DIR/head1_scorecard.md).exists()` and the same for the OOF parquet.
   - New: a module fixture `repo_scorecard_before` takes the sha256 of the real
     `head1_scorecard.md`, `.json` and `head1_oof_predictions.parquet`. `head1_run` depends
     on it, so the snapshot is taken before the synthetic run. After the run the test asserts
     the three files are byte-unchanged.
   - Added `import hashlib`. The `head1_run` docstring no longer says "the repo has no
     ratification".

## Tripwires checked against damage (tmp copies only; the real files were never touched)
Each case was simulated by pointing the module path constant at a tmp file:
- pin deleted: fires in all three invariants;
- `doc_sha256` re-pinned: fires;
- `owner_word` wrong: fires;
- `handoff_entry` wrong: fires;
- `params_sha256` wrong (test_pin_g3): fires;
- document edited (heads helper): fires.

Every failure carried the NEVER-delete message. The healthy state passes.

## Commands and counts (interpreter `/Library/Developer/CommandLineTools/usr/bin/python3`)
- `python3 -m pytest -q -p no:cacheprovider test_backtest_e2.py test_pin_g3.py test_heads_e2.py`
  - before: **12 failed, 122 passed** (134);
  - after: **134 passed, 0 failed, 0 skipped**.
- Root suite, `python3 -m pytest -q -p no:cacheprovider --ignore=finetune`
  - first run, after the three files were fixed: **1 failed, 1600 passed** (the scorecard test, item 9);
  - final: **1601 passed, 0 failed, 0 skipped, 1 warning** (a pre-existing numpy RuntimeWarning
    in `test_ingest_prices.py::test_zero_or_negative_close_is_fatal`), 292 s.
- The test count is unchanged at 1,601: tests were renamed or inverted, none removed.
- `shasum -a 256 -c` on `G3_RATIFIED.json` and `G3_PREREGISTRATION.md` before and after: OK.

## Not done / for the main session
- Not committed (per brief). Changed: `test_backtest_e2.py`, `test_heads_e2.py`,
  `test_pin_g3.py`, `test_scorecard_e2.py`.
- `test_pin_g3.py` now needs git object `41829ad` in the local repo. In a checkout without
  history it fails loudly, naming the commit; it does not skip.
- Logging this as a main-session decision in HANDOFF §3, as the reviewer recommends, is for
  the main session.
