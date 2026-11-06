# REVIEW: disclosure lead, E2 line, guard regex, watchlist refresh (2026-11-05)

Reviewer (Opus), uncommitted working tree as of 2026-11-05. Read-only: I edited nothing except this file, ran no `bin/fs report`, labeler or ingest, and did not touch `data/app/companies|reports`, `WATCHLIST_DONE.tsv` or `WATCHLIST_BUILD.log`.

## What I checked, and what I re-derived

- **Artifact shas, recomputed:** `results_g2.json` d146e5e4…, `metrics.json` (v1.2 eval) 21c3360f… and `F6_E2_RESULT.md` 06b86611… all match their pins.
- **Plain-English lead, figures recomputed:**
  - sentiment: 293/337 = 86.94% → 87
  - NEGATIVE recall: 64/121 = 0.529, so 1 − recall = 47.1% → 47
  - guidance: 115/119 = 96.64% → 97
  - active precision: 0.6867 → 69

  The arithmetic is correct. The problems are in what the words around the figures say (below).
- **E2 line, recomputed from `results_head1.json`:**
  - mean of the 33 per-fold deltas = 0.0010936
  - 90% CI = mean ± 1.6449 × 0.014874 = [−0.02337, +0.02556]
  - TOST: `equivalence: true` at margin 0.04
  - 139 CIKs in the dedup test set and 33 folds, matching F6 §0 and REVIEW_g3 (the modeling frame has 143/144 CIKs; the scored set has 139).

  All correct.
- **Renderer opens no outcome artifact:** imports are clean. The existing source scan bans `data/f5` and `/data/f5/` (test_report_filing.py:72,94), and the new test bans the `F6_E2_RESULT` stem. Confirmed.
- **Guard regex, live:** `pgrep -fl` with the new ERE matches both running labeler processes: the Xcode-framework `…/MacOS/Python …/label_filing.py` and the Homebrew 3.11 `…/MacOS/Python …/label_filing.py --generate`. It did not match my own shells, whose text contains the pattern.
- **Guard regex, other launch forms** (checked with Python `re`):
  - match: `nohup nice python3 label_filing.py`, `caffeinate -dims <venv>/python …/label_e2.py`, `python3 "$FS/finetune/label_e2.py"` (run_campaign_chain.sh)
  - miss: `python3 -u`, `python -m label_filing`, a path containing a space. No launch form in the repo uses any of these.
- **plist:** `plutil -lint` OK.
- **Tests:** `pytest -q -p no:cacheprovider test_report_filing.py test_finscreen_cli.py test_run_watchlist.py test_app_store.py` → **225 passed, 0 failed, 0 skipped in 240 s**. Both `under_ten_seconds` tests passed, even with the labeler busy.

## Findings (ranked)

1. **MUST-FIX** (definite) — The refresh does not ingest new filings.
   - Where: finscreen.py:109-111; data/app/launchd/README.md:7; data/app/run_watchlist.sh:6-7; HANDOFF.md §3 entry 2026-11-05/06 ("a run with nothing new labels nothing").
   - Why: `cmd_report` skips `ingest_one.py --per-form` whenever the store already has `per_form == 2`, so `--refresh` never fetches a newly filed 10-Q/10-K/8-K for any of the 30 existing stores.
   - What it actually does: refreshes fundamentals (companyfacts, 24 h cache) and re-renders the old filings.
   - What it breaks: ruling F's post-earnings refresh does nothing for filings, while three documents say it does.
   - Proposal: make `--refresh` force the per-form ingest (e.g. a `bin/fs report --refetch` flag that `run_watchlist.sh --refresh` passes), then correct the README/script/HANDOFF wording.
2. **MUST-FIX** (definite) — The lead breaks the owner's ruled escort rule.
   - Where: report_filing.py:404-407, the guidance sentence of `PLAIN_ENGLISH_TEMPLATE`.
   - The rule (G2_FINAL_REPORT.md §1, owner-ruled 2026-09-07): guidance is "**never quoted without** `guidance_active_precision` … and `guidance_false_none_rate` 0/80 …, **and §0 above**". HANDOFF 2026-09-11 adds that §0 "travels with `guidance_active_precision` wherever it is quoted".
   - What the lead does: it quotes 97% and 69% with no false-NONE rate and no §0. The builder's report says it added the 69% "because G2 §0 requires" it, but §0 is the escort of the 69%, not a reason to quote it.
   - Proposal: carry both escorts plus a short §0 clause in the lead, or drop the guidance figures from the lead and point to the detailed list.
3. **SHOULD** (definite) — "On a held-out check" mislabels the G2 figures.
   - Where: report_filing.py:400.
   - The 87%, 97% and 69% come from G2. G2 is a draw over the whole E2 labelled corpus, and its frame includes 14,342 train-overlap rows (`frame_checks.train_overlap_rows`). It is not held out.
   - Only the 47% comes from the held-out v1.2 eval, with teacher (Claude) labels as reference.
   - The sentence also merges two different measurements and references ("a reference rater" vs "a reference model") into one "check". That breaks rule 4 (every number with how it was measured).
4. **SHOULD** (definite) — The lead drops the sentiment verdict.
   - Where: report_filing.py:400-402.
   - The ruled ladder says sentiment proceeds as **INDETERMINATE** at the 0.85 bar, with its error "beside every number derived from it" (G2 §1). The lead gives "about 87%" with no verdict, n or interval.
   - A reader who stops at the lead sees a figure that reads as a pass.
5. **SHOULD** (definite) — The lead says the same thing on every page, even where the detailed list says otherwise.
   - Where: report_filing.py:1559-1568 versus the `{outside}`/`{banner}` lines at 1570 and 1575.
   - On store pages the list says "outside the 244-company research universe; its labels have no spot-check". On overlap pages it says "Read every label … as a memorized fit, not as a held-out prediction". The lead, placed above both, still says "On a held-out check … matched about 87%".
   - The lead contradicts the list on exactly the pages the app lane renders most.
6. **SHOULD** (definite) — The lead attributes writer-imputed labels to the model.
   - Where: report_filing.py:404-405, "Its guidance-direction labels matched about 97%".
   - Per the G2 caveat, 60 of the 119 rows are writer-imputed NONE (the §1.3 writer rule, not the model), and only 9 carry an active direction.
   - "mostly by agreeing that a passage gives no guidance" understates this: about half of the 97% is the writer default being right, not the model.
7. **SHOULD** (definite) — The lead uses words the legal baseline bars from shared pages.
   - Where: report_filing.py:402 and test_report_filing.py:882.
   - "accuracy" is on the legal baseline's "Words never used publicly" list (site/STORYBOARD.md:83-84), and pages are now shared as demonstrations (ruling C; CLAUDE.md rule 9 says "anything shared").
   - The lead adds a new instance ("agreement, not accuracy"), and the banned-word test omits "accuracy". "Agreement, not human validation" says the same thing within the rule.
   - SENTIMENT_ESTIMAND and FOOTER_LINE ("advice") already break the rule; flag them for the legal-reviewer, not this pass.
8. **SHOULD** (definite) — The E2 line drops the caveats that travel with it.
   - Where: report_filing.py:329-333.
   - It says "inside the ratified 0.04 margin" but omits:
     - the honest MDE 0.0416, which exceeds the margin. The KC3 note says "no equivalence claim is read as tighter than that", and F6 §1.1 says these caveats "travel with this line".
     - that about 32 of 100 nuisance seeds do not reach equivalence.
   - Also, "ratified 0.04" is loose wording: the ladder (0.03/0.04/0.05) was ratified, and 0.04 was selected by its rule.
9. **SHOULD** (definite) — E1 and E2 IC deltas sit side by side without the incomparability rule.
   - Where: report_filing.py:327-333.
   - The line puts E1's +0.0177/−0.0097 next to E2's +0.0011 with no "numerically incomparable" sentence. That sentence is the standing rule (`results_head1.json` `scope.e1_e2_incomparable`; F6 preamble).
10. **SHOULD** (worth a look) — The E2 line is not the council's "verbatim" branch sentence.
    - Where: report_filing.py:326-333.
    - The binding Q4 text (owner, 2026-09-11: "as drafted") says the E2 carry-over is "replaced by the F6 branch sentence verbatim". The §13 row is "text is not used as a signal; the study is written up and closed (F6 negative result + failure taxonomy; pipeline archived as asset)". The template carries only the first clause, plus composed prose.
    - Proposal: either append the remainder of the row, or log a main-session decision that the composed line discharges "verbatim".
11. **SHOULD** (definite) — Nothing stops two chains, or a chain and a manual report, from running two labelers at once.
    - Where: data/app/run_watchlist.sh:17 and finscreen.py:105.
    - The guard sees only live labeler/ingest interpreters. A second chain (for example the 1st/15th launchd run landing on a manual chain or a `bin/fs report` session) passes whenever the first is in `finscreen.py`, `report_filing.py` render, or between tickers.
    - `cmd_report` checks only at entry, and `label_filing.py` does not refuse a sibling `label_filing.py` (label_filing.py:133 skips them). Two labelers can then overlap, breaking CLAUDE.md rule 6.
    - The scheduled job makes this more likely. Proposal: a `mkdir` lock or a `pgrep -f run_watchlist.sh` (excluding `$$`) check.
12. **SHOULD** (worth a look) — The refresh job can stall or be put to sleep mid-run.
    - Where: data/app/launchd/com.finscreen.watchlist-refresh.plist:39-40, plus no `caffeinate`.
    - `ProcessType Background` applies background CPU/IO throttling to an hours-long MLX/pandas run.
    - Nothing holds a power assertion, so idle sleep can suspend the run. The F4 chain uses `caffeinate -dims` for this reason (data/f4/run_campaign_chain.sh:43).
    - Proposal: `ProcessType Standard` (or omit it) and `caffeinate -i` in ProgramArguments.
13. **NOTE** — The README contradicts itself about sleep.
    - Where: data/app/launchd/README.md:31.
    - "The Mac must be awake at 03:00" is followed by "If it is asleep, launchd runs the job at the next wake". The second sentence is the correct launchd behaviour (missed intervals are coalesced on wake; skipped if powered off). Drop the first.
14. **NOTE** — The production script carries a test-only bypass of rule 6.
    - Where: data/app/run_watchlist.sh:8,17.
    - `FS_SKIP_PROCESS_GUARD=1` is a knob that disables the guard. A stub `pgrep` first on PATH in the test would give the same coverage with no bypass in production (lazy-elite).
15. **NOTE** — The `bin/fs` existence check adds little.
    - Where: data/app/run_watchlist.sh:14-16.
    - Without it, every ticker would log exit 127 and stay not-done, which is still resumable. It is harmless.
16. **NOTE** — The loop's stdin is the watchlist pipe.
    - Where: data/app/run_watchlist.sh:33 (pre-existing).
    - `bin/fs report` inherits the `while read` pipe as stdin, so any child that reads stdin would swallow the remaining tickers. The previous run reached all 30 lines, so nothing does today. `</dev/null` on line 33 closes the gap.
17. **NOTE** — A mistyped flag fails silently.
    - Where: data/app/run_watchlist.sh:20.
    - An unknown or mistyped argument (e.g. `--refesh`) silently runs plain mode, and the log echoes the typo as if it were honoured.
18. **NOTE** — Guard regex: known misses and remaining false positives.
    - Where: finscreen.py:40.
    - Misses: `python3 -u …`, `python -m label_filing`, a path with a space. No repo launch form uses these today.
    - Still matches non-processes: any shell whose text contains `python3 label_filing.py`, e.g. `bash -c 'grep -n "python3 label_filing.py" RESUME_HERE.md'` matched in my probe. The false-positive class is narrowed, not eliminated.
    - The parity test (test_finscreen_cli.py:148-162) checks Python `re`, not `pgrep`. Live parity was confirmed only by hand (here and by the builder).
19. **NOTE** — The documented manual check still uses the old pattern.
    - Where: CLAUDE.md:45; RESUME_HERE.md:91.
    - Rule 6 still tells agents to run the bare `pgrep -fl "label_filing|label_e2|ingest_one"`. That is the pattern whose shells triggered the incident, and it now disagrees with `bin/fs`. Updating it is a main-session doc edit.
20. **NOTE** — The lead's reference description is incomplete.
    - Where: report_filing.py:402.
    - "the rater is another model": the G2 reference is two Claude-family models (rater + adjudicator), with owner rulings superseding on 59 escalated/probe rows. That is not wrong as "agreement", but it is incomplete; "model consensus" is the ruled term.
21. **NOTE** — The lead rounds numbers the ruling says are verbatim.
    - Where: report_filing.py:398-410.
    - The binding disclosure ruling says "numbers verbatim from results_g2.json…". The lead rounds 96.64 to "about 97%", which also sits beside the owner's own §0 use of "96.7%" as the *rejected*, inflated counterfactual. A reader may conflate the two.
22. **NOTE** — The lead adds an instruction.
    - Where: report_filing.py:407-408.
    - "do not rely on them" is about red-flag labels, not an investment action. It does not break the boundary sentence, but it is the only instruction to the reader in the block.
23. **NOTE** — The incident date is written two ways.
    - Where: finscreen.py:38 and test_finscreen_cli.py:148.
    - The incident is dated "2026-11-06" (UTC), while HANDOFF says "2026-11-05/06". Trivial.
24. **NOTE** — New launchd log paths are not in `.gitignore`.
    - Where: data/app/launchd/com.finscreen.watchlist-refresh.plist:42,44.
    - `data/app/status/launchd.{out,err}.log` will show as untracked after the first run.

## Verdict

The arithmetic is right. Every figure in the lead and the E2 line recomputes exactly from its pinned artifact, the renderer still opens nothing under `data/f5`, the new guard matches the two real labeler processes live without matching agent shells, the plist lints, and 225/225 tests pass.

Two findings block shipping. The headline feature of the refresh pass does not work: `--refresh` cannot fetch a new filing for any existing store, because `cmd_report` skips per-form ingest whenever `per_form` matches. The README, the script header and the HANDOFF entry all say it does. And the new plain-English lead re-quotes the guidance figure without the owner-ruled escorts (false-NONE 0/80 and §0).

The lead also needs one rewrite pass:
- it calls G2 a "held-out check" and merges two different measurements;
- it hides the INDETERMINATE sentiment verdict;
- it credits writer-imputed NONE to the model;
- it ignores the outside-universe and overlap lines printed below it;
- it uses "accuracy" on a shared page.

The E2 line is correct but drops the honest-MDE caveat and the E1/E2 incomparability rule that are meant to travel with it.

Proposed: fix 1-2 before commit; fix 3-12 in the same pass (all small text or two-line shell changes); log 13-24 as notes.
