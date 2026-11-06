# DISCLOSURE: E2 predictive-validity line (builder, 2026-11-05)

Brief: replace the "E2: not run" carry-over in `PREDICTIVE_VALIDITY_TEMPLATE` with the
E2 bounded-null sentence, mirroring the E1 constant-plus-pinned-test pattern. Not committed.
The previous pass's plain-English lead (DISCLOSURE_summary_2026-11-05.md) is left in place.

## Rendered sentence (verbatim, from `disclosure_html(load_disclosure(), None)`)

    <li><b>Predictive validity.</b> E1 (25 companies): no fold-robust text signal (+0.0177 raw / -0.0097 dedup IC delta); E2 (139 companies, 33 walk-forward quarters, pre-registered, run 2026-11-05): bounded null — +0.0011 mean per-fold dedup IC delta, 90% CI [-0.0234, +0.0256], inside the ratified 0.04 margin; text is not used as a signal</li>

## Source verified

- `data/f5/F6_E2_RESULT.md` sha256 `06b86611a44021f40e9a0c901c1edf287d883592578a33d1f67c75aacebf66ba` (computed; matches the brief).
- §1.1 table rows: `| mean per-fold dedup IC delta | **+0.0011** |` and
  `| 90% CI (normal reference) | **[−0.0234, +0.0256]** |`. The CI minus is U+2212; the test normalises it to ASCII before float().

## Changes

`report_filing.py`
- L326-333 `PREDICTIVE_VALIDITY_TEMPLATE`: "E2: not run" is replaced by the E2 sentence. The figures are format fields
  `{e2}`, `{e2_lo}`, `{e2_hi}` (`:+.4f`). The study identifiers (139 companies, 33 quarters, 2026-11-05) and the ratified
  margin 0.04 are literals.
- L343-348: new `E2_IC_DELTA_DEDUP = 0.0011`, `E2_IC_CI_LO = -0.0234`, `E2_IC_CI_HI = 0.0256`, with a comment beside the E1
  constants. The module does not name `F6_E2_RESULT` and opens no outcome artifact.
- L571-572 `load_disclosure()`: the new fields are passed to `.format()`.

`test_report_filing.py`
- L790 `test_disclosure_header_renders_every_ruled_number`: "E2: not run" is replaced by "+0.0011", "-0.0234", "+0.0256", "bounded null".
- L981-1004: new `E2_RESULT_WRITE_UP(_SHA256)` and `test_e2_ic_numbers_match_the_f6_write_up_they_came_from`. It pins the sha,
  regexes the two headline rows (anchored with `^...$`), and asserts the values equal the three constants.
- L1009: `test_the_module_never_names_the_backtest_report` also asserts that "F6_E2_RESULT" does not appear in the module source.
- L1020-1024 `test_predictive_validity_is_one_replaceable_constant`: formats with the E2 fields, then checks
  `endswith("text is not used as a signal")`, "E1 (25 companies)" and "E2 (139 companies".
- The banned-vocabulary test for the plain-English lead already scans only `<p class="plain">` (`_plain_paragraph`), so it was
  not changed. The lead does not mention E2.

## Tests (run 2026-11-05)

- `python3 -m pytest -q -p no:cacheprovider test_report_filing.py test_finscreen_cli.py test_app_store.py -k "not under_ten_seconds"`
  gave **210 passed, 2 deselected, 0 failed, 0 skipped** (82.7 s).
- Root suite `-k "disclosure or predictive or ic_delta or e2_ic"` gave **19 passed, 1842 deselected, 0 failed**.
- `grep -rl "E2: not run\|PREDICTIVE_VALIDITY" --include=*.py` matches only report_filing.py and test_report_filing.py,
  so no other test pins the old string.

## "E2: not run" elsewhere

- README.md, MODEL_CARD.md, LIMITATIONS.md, HANDOFF.md, RESUME_HERE.md: **no hits**, so nothing was edited.
- Historical status files only (left as dated records): data/app/status/DISCLOSURE_summary_2026-11-05.md:71,
  data/app/status/L2_1_report_filing.md:199,711, data/f5/status/COUNCIL_ADVISORY_personal_use_2026-09-10.md:40
  (the last one specifies that the string is "replaced by the F6 branch sentence verbatim", which this change does).

## Not done / notes

- Already-rendered HTML under data/app/reports/ still shows the old line until it is re-rendered. Those files were not touched,
  because a labeling chain was alive (pid 13311/13312, label_filing.py on store 796343).
- `git diff --stat` also shows `data/app/run_watchlist.sh` modified. That change is not from this pass.
