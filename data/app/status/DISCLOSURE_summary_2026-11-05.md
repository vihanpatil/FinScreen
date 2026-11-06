# Disclosure block: plain-English lead (RESUME_HERE next-work item 4), 2026-11-05

Builder completion report. This was a main-session decision; no owner ruling was involved. Nothing was committed.

## What changed

`report_filing.py`
- Lines 385-401: new constant `PLAIN_ENGLISH_TEMPLATE`. It is a format string whose only figures are the
  fields `{sent}`, `{miss}`, `{guid}` and `{active}`, each written `:.0f`. No ruled constant was touched.
- Line 1344: one CSS rule, `.plain { font-size:15px; font-weight:400; margin-bottom:14px; }`.
- Lines 1548-1551 (in `disclosure_html`): the template is filled from the same `d` dict the detailed list
  uses. The fields are `s["pct"]`, `g["pct"]`, `g["active_precision_pct"]` and
  `(1 - s["negative_recall"]) * 100`, and the result goes through `esc()`.
- Lines 1556-1557: `<h2>In plain English</h2>` and `<p class="plain">…</p>` sit after the identity line
  and before the `<ul>`. The detailed list is unchanged and still not collapsible.

`test_report_filing.py`
- Line 125: added `PLAIN_ENGLISH_TEMPLATE` to `DISCLOSURE_CONSTANT_NAMES`. The module-literal scan
  (`test_module_chrome_carries_no_action_vocabulary`) checks every string literal for buy/sell/hold/recommendation.
  So a "not a recommendation to buy, sell or hold" sentence can only exist as an exempt disclosure
  constant, which is the same way `IDENTITY_LINE` and `FOOTER_LINE` carry "recommendation". This is the
  only change to the allow-list.
- Lines 843-891, section 5: a helper `_plain_paragraph` and three tests.
  - `test_disclosure_plain_english_lead_renders_before_the_detailed_list` checks the order
    h1 < identity < plain < `<ul>`, and that the text is 80-140 words.
  - `test_disclosure_plain_english_figures_are_read_from_the_artifacts` checks:
    - every rounded figure matches `d`;
    - today's values (87/97/69/47) are pinned;
    - changing `d` changes the rendered text;
    - the template has no literal digit.
  - `test_disclosure_plain_english_lead_carries_no_banned_vocabulary` rejects advice, call(s),
    recommend(s), signal(s), predict(s), prediction(s), score, rank and summary. "recommendation" may
    appear only as "nothing here is a recommendation". The text must say "another model" and "not accuracy".

## Rendered text (in-process `disclosure_html(load_disclosure(), None)`, writes nothing; 135 words)

> Every label on this page was written by a small model the owner runs locally; no person read these passages. On a held-out check its sentiment labels matched a reference rater about 87% of the time (the rater is another model, so this is agreement, not accuracy), and it misses about 47% of the passages a reference model marked negative. Its guidance-direction labels matched about 97% of the time, mostly by agreeing that a passage gives no guidance; when it names a direction, that direction matched about 69% of the time. Red flags are experimental: do not rely on them. These labels have not been shown to say anything about future stock prices, and nothing here is a recommendation to buy, sell or hold. This page is a reading aid for the owner's own research.

(The apostrophe in "owner's" renders as U+2019, matching FOOTER_LINE.)

## Departures from the brief, each small

1. The text adds the active-value precision (about 69%) next to the 97% guidance figure. Without it, the 97%
   reads as "right 97% of the time", but it is measured on the NONE mass only, and G2 §0 requires the
   interpretation to travel with the figure.
2. The text says "about 47%" (read from `d`) where the brief said "roughly half". The detailed list keeps
   its own "Roughly half".
3. Point (4) is worded "have not been shown to say anything about future stock prices" rather than "has
   not been tested against stock prices". The research arms were tested (E1 null; G3 2026-11-05 bounded
   null), so "not tested" would be false. "Not shown" is true either way and needs no outcome artifact
   (the renderer may not read `data/f5`).
4. The text uses "marked negative", not "called negative", to stay clear of "call".

## Commands and results

- `/Library/Developer/CommandLineTools/usr/bin/python3 -m pytest -q -p no:cacheprovider test_report_filing.py test_finscreen_cli.py -k "not under_ten_seconds"`
  gave **117 passed, 0 failed, 0 skipped, 2 deselected** in 172s. The 2 deselected are
  `test_real_filing_renders_under_ten_seconds[...]`.
- `... -m pytest -q -p no:cacheprovider test_app_store.py` gave **92 passed**. This run covers store
  renders and the in-block outside-universe line, all on tmp_path.
- Every pre-existing disclosure test passed without changes, including
  `test_disclosure_header_renders_every_ruled_number`, `test_every_disclosure_number_comes_from_its_artifact`,
  `test_disclosure_source_shas_are_pinned` and `test_disclosure_header_is_not_collapsible`.

## Not done / flagged

- No page was rendered under `data/app/`, because the labeling chain is alive. The check was in-process
  only. Existing report HTML in `data/app/reports/` and the store pages will show the lead after their
  next re-render.
- The full root suite (~1,800 tests) was not run, only the files named above.
- Flag for the main session: `PREDICTIVE_VALIDITY_TEMPLATE` still renders "E2: not run", but G3 ran on
  2026-11-05 (bounded null). It is a ruled disclosure string, pinned by
  `test_disclosure_header_renders_every_ruled_number`, so I left it alone. It needs a main-session
  decision and a re-pin.
