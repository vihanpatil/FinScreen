# RESUME_HERE — state as of 2026-11-05 (owner back after two months; LOW-TOUCH MODE)

**If you are a fresh session: read `CLAUDE.md`, then this block, then `OWNER_DECISIONS_2026-11-05.md`.**
Or run the `/resume` skill, which does exactly that.

**What happened 2026-11-05.** The owner resumed (last activity 2026-09-11) and said, verbatim:
*"I cannot be too hands on. Please automate what you can, and create or update the agentic team
with more modern skills and keep the team as concise and tight and efficient as possible. For
ultimate, critical decisions loop me in."* The main session (Fable) did the following, all
committed on main:
- **Environment re-verified.** `/usr/bin/python3` refuses to start (macOS update reset the
  Xcode licence; owner fix `sudo xcodebuild -license accept`); the same interpreter works
  directly at `/Library/Developer/CommandLineTools/usr/bin/python3` (pandas 2.2.3, xgboost,
  pytest). MLX venv healthy (mlx_lm 0.31.3, Metal). Adapter sha matches the campaign manifest.
  Root suite **1,588 passed** (4 min 57 s). `backtest_e2.py` still exits 2 (no pin). No process
  running. Filings and prices on disk end 2026-08-24; `ingest_one.py` fetches current filings
  on demand, so the reading aid is current for any ticker.
- **`CLAUDE.md`** written: the operating brief every session and agent loads (interpreters,
  commands, condensed hard rules, the **owner-touchpoint policy**: ask the owner only for money,
  anything public/shared, the word "ratify" + their read, direction/charter changes,
  destructive ops; everything else is a logged main-session decision).
- **Team 15 → 7** (`TEAM.md`): `builder` (Opus), `reviewer` (Opus), `scribe` (Sonnet) absorb
  eleven retired files (`docs/retired_agents/`); `legal-reviewer`, `tech-council`,
  `label-rater-blind`, `label-adjudicator` kept. Skills `/resume`, `/report TICKER`, `/g3-run`.
- **One-command product:** `bin/fs` (interpreter-selecting wrapper) + `finscreen.py`
  (`doctor`, `report TICKER [--open]`, `index`, `g3 --date D --owner-word ratify`) +
  `test_finscreen_cli.py` (13 tests). Built by the builder agent; report
  `data/app/status/CLI_wrapper_2026-11-05.md`.
- **Owner packet** `OWNER_DECISIONS_2026-11-05.md`: A "ratify" (recommended), B EODHD, C friends
  scope (recommended: private reading-aid pages only), D confirm low-touch mode, E xcode licence +
  git push (main was 29 ahead), F optional watchlist.

**G3 RATIFIED AND RUN 2026-11-05 (owner typed "ratify"; HANDOFF §3).** Pin `data/f5/G3_RATIFIED.json`
(doc sha `6b99f65e…`), chain `bin/fs g3` ran 9 min 5 s: head 1 + scorecard, heads 2 and 3, all outputs on disk
and sha-logged in `data/f5/run_log.jsonl`. **Result, mechanically per the ratified §13: mean per-fold dedup IC
delta +0.0011, SE 0.0149, 90% CI [−0.023, +0.026], margin 0.04 POWERED (honest MDE 0.0416), TOST equivalence
TRUE → "Bounded null — text is not used as a signal; the study is written up and closed."** Scorecard universe
block: model 1552/2992 = 0.5187 [0.5008, 0.5366], numeric-only 0.5099, size-only 0.4859, chance 0.500. The
owner's read file is `data/f5/status/G3_RUN_2026-11-05_owner_read.md` (per-fold table, universe block, heads
2–3); per-company pages in `data/f5/head1_scorecard.md` (git-excluded). Reviewer pass DONE (`data/f5/status/REVIEW_g3_run_2026-11-05.md`: everything reproduces; M1 = decision-11
sensitivity arm never built → recorded DEVIATION, run post-hoc-labelled in F6; M2 = tripwires inverted, suite 1,601
green, `data/f5/status/M2_tripwire_inversion_2026-11-05.md`; the rest → F6 list in HANDOFF §3). **F6 DONE 2026-11-05 (HANDOFF §3 "F6 EXECUTED"). NOTHING IN FLIGHT. The owner closed the session ("once you
are done, wrap up this session. i will resume in a new session").** E2 is closed as a bounded null; the write-up
`data/f5/F6_E2_RESULT.md` (reviewer-corrected) **passed Gate G4 on 2026-11-05 (owner, verbatim: "accept g4";
HANDOFF §3). E2 is closed at every gate.** At that resume `main` was found equal to `origin/main` (the owner had
pushed between sessions; fact, not ruling), so packet item G is moot unless the owner says "strip". Still open for
the owner, all in `OWNER_DECISIONS_2026-11-05.md`: **B** (EODHD, money), **C** (friends scope), **D** (confirm
low-touch mode), **E1** (xcode licence), **F** (watchlist tickers). The product work
that needs no owner word: the reading aid is live (`bin/fs report TICKER`); next engineering under the null branch
is the numeric-families signal program (PRODUCT_PLAN P3 item 2), which needs decision B (EODHD) before any money
metric; a shorter plain-English disclosure block on the report pages (non-collapsible stays) is a builder task the
main session proposed and the owner did not object to.
NEXT (no owner word needed): shorter plain-English disclosure block on the report pages (`builder`; the
non-collapsible block stays), then the numeric-families signal program (PRODUCT_PLAN P3 item 2; money metrics
wait on decision B). Decisions B, C, D, E1, F still open. NEVER re-pin; never re-run a head on a model reading. On "ratify": follow
`.claude/skills/g3-run/SKILL.md`. On a watchlist: `bin/fs report T` per ticker, then a scheduled
refresh. On "share with friends — yes": add the legal-baseline footer line to shared pages
(builder), nothing else changes.

---

# (previous) RESUME_HERE — stopping point set 2026-09-06

**If you are a fresh session: read this file first** (then `HANDOFF.md`
for depth). **STATE AS OF 2026-09-06 ~15:30 — handoff written by the main session at the
owner's request (owner returns in a few hours).**

**THE OWNER'S CORE VALUE STATEMENT (2026-09-11, verbatim, all caps theirs; overrides
any narrower framing in this file):** *"I NEED THIS TO BE A PERSONAL INVESTMENT TOOL THAT OTHERS CAN USE. I NEED YOU TO EMPHASIZE TESTING PREVIOUSLY PUBLISHED REPORTS FOR A COMPANY AND EVALUATING HOW THOSE STOCKS DID FOR THOSE CERTAIN QUARTERS (for example, if Google published reports in 2018, what would my model evaluate their stock to do, and historically, what did their stock do? Was my model correct or wrong? Do that for many many many companies. THIS IS THE VALUE!)"*
**What it means for the work:** (1) the product's centrepiece is the per-company,
per-quarter historical SCORECARD — for each past filing, what the model would have
said using only data public at that time, what the stock then did over the following
quarter(s), and whether the call was right — across as many companies as possible;
head 1's walk-forward already produces those per-row predictions inside each fold, so
the change is to REPORT them per company (pre-registered scoring rule for "correct":
to be pinned) rather than only the aggregate IC; (2) "others can use it" means
distribution is INTENDED — PRODUCT_PLAN decision E's default (explainer only) is
superseded by the owner's intent; the legal review (§1.3) moves EARLIER, before any
public tool, not "never"; (3) honesty rules unchanged: no claim before its evidence,
paper before live, disclosed error on every page. Website direction 2026-09-11: the
city stays but MORE MINIMALIST, a distinct 3D model per pipeline stage, smoother,
explained for someone with no prior understanding, and it must show the goal (a
personal investment advice tool with historical scorecards) — see `site/STORYBOARD.md`
v1 feedback. **The owner asked that nothing be built until they rule; decisions A–F
(PRODUCT_PLAN §4) and the 23 G3 decisions (data/f5/G3_OWNER_PACKET.md) were explained
to them in chat on 2026-09-11.**

**AUTO-RESUME PROTOCOL (owner, 2026-09-11: "auto-resume once usage resets; keep
docs and memory updated so resuming is seamless").** A session cron fired every
~2 h with a resume prompt until the owner cancelled it on 2026-09-11 ("You may kill
auto-resume, I will not run out of 5-hour usage anymore"); no cron is armed now. On ANY resume (cron or fresh session): (1) read this
block and the IN FLIGHT table; (2) `pgrep -fl "label_filing|ingest_one|label_e2"`
— never start a second labeling process while one is alive; (3) for each IN
FLIGHT item whose expected output is missing and whose agent is not running,
relaunch it exactly as described (never hand-build in the main session); (4)
after any action, update this block, HANDOFF §3 and memory BEFORE the next
agent launch; (5) commit ledgers after each milestone (the owner pushes). Be
frugal: if nothing is missing, do nothing.

**OWNER RULED A–F AND ALL 23 G3 DECISIONS (chat, 2026-09-11 afternoon) — verbatim +
readings in `data/f5/G3_OWNER_RULINGS_2026-09-11.md` (READ IT FIRST). Pre-registration is
being edited DRAFT → RATIFICATION-READY; sha is pinned into `data/f5/G3_RATIFIED.json`
ONLY when the owner replies "ratify" to that file's §4 list. Owner also killed the
auto-resume cron ("I will not run out of 5-hour usage anymore") — no cron is armed; the
protocol below still applies to any fresh session.**

**IN FLIGHT (launched 2026-09-11 afternoon; every launch listed here):**
| item | launched as | expected output | if missing on resume |
|---|---|---|---|
| QM: scorecard + rolling-window arms + size_only block + OOF export in `backtest_e2.py`, new `scorecard_e2.py`, schema regenerated, tests | quant-modeler Opus agent | `scorecard_e2.py` exists; `data/f5/G3_PARAMS_SCHEMA.json` lists `scorecard.*` and `fold_sensitivity.train_window_quarters`; `python3 -m pytest test_backtest_e2.py test_scorecard_e2.py -q` green; `python3 backtest_e2.py` still exits 2 | relaunch with "check what already landed in backtest_e2.py / scorecard_e2.py before editing; spec = G3_OWNER_RULINGS §3 item 2" |
| DOC: `data/f5/G3_PREREGISTRATION.md` DRAFT → RATIFICATION-READY (§14 scorecard, decision-4 family, §13 signature, params block keys), packet banner | general-purpose Opus agent | header says RATIFICATION-READY; §14 exists; block parses with the new keys | relaunch with "diff the file against the spec in G3_OWNER_RULINGS §3 item 1; finish only what is missing" |
| LEGAL: baseline memo (decision E) | legal-reviewer agent (fable) | `data/legal/LEGAL_REVIEW_baseline_2026-09-11.md` (main session saves the agent's memo) | relaunch the review; nothing else depends on it |
| MAIN: charter amendment (decision F) in HANDOFF §1 / README / LIMITATIONS / MODEL_CARD / two agent files; PRODUCT_PLAN §4 + §1; F5_PLAN §3 rulings block; HANDOFF §3 entry; memory; commit | main session | the files say "amended 2026-09-11" | do it in the main session |
**Round 1 DONE (all four rows above; commits f9fee22, 0972add, 3be52ca; suite 1,787 green). RED-TEAM VERDICT
2026-09-11: NOT SAFE TO ASK FOR RATIFICATION YET** (`data/f5/status/REDTEAM_g3_package_2026-09-11.md`;
freeze + folds sound; document launders readings as rulings; six ratified rules not built into the
feature tables; scorecard page defects). **Round 2 IN FLIGHT (launched 2026-09-11 evening):**
| item | launched as | expected output | if missing on resume |
|---|---|---|---|
| A: scorecard/backtest fixes M1 M3 M4 M5 S4 S5 S6 N2 N4 + decision-2 analysis-side GLD exclusion + `gld_included` sensitivity arm + `columns.exploratory_novelty_seq` in the exploratory block; new required keys `gld.exclude_from_analysis`, `gld.included_sensitivity_arm`, `scorecard.tie_rule` | quant-modeler Opus | tests `test_company_below_min_calls_has_no_rate`, `test_tie_group_straddling_a_boundary_is_no_call`, `test_chance_line_is_half_by_construction`, `test_scorecard_page_carries_the_disclosure_block` pass; schema regenerated | relaunch "check what already landed before editing; spec = REDTEAM file Disposition + this row" |
| B1: decision 2 benchmark half (`target_e2.py` excludes GLD from the peer average), decision 20 (`features_e2.py` same-CIK attribution + `cross_cik_share`), decision 21 (`numeric_features_e2.py` duration-matched `operating_cashflow_to_revenue`); rebuild target → text features → numeric; manifests + tests | quant-modeler Opus | manifests carry new shas + a "rebuilt 2026-09-11 (G3 rulings)" note; STEP1A status files updated | relaunch "check each manifest's note before rebuilding" |
| B2: decisions 23a/23b/23d + seq novelty in `text_families_e2.py` (YoY same-form prior, min 50 shingles, 8K_BODY out of the embedding, `novelty_*_seq` exploratory); re-embed (~25 min, background); manifest + tests | quant-modeler Opus | `data/f5/text_families_e2.parquet` rebuilt, manifest note; columns `novelty_risk_factors_seq`, `novelty_mda_seq` present | relaunch "check the manifest note; re-embed only if 8K_BODY is still in it" |
| C: pre-registration + rulings-file fixes B1 M6 M7 M8 M9 S1 S2 S3 S4 N1 N5 N6 N7 (⚠ marks, §4 rows, pinning text, header wording); NOT M2 (measured cells refresh AFTER B1/B2) | general-purpose Opus | §14 rows and 23(b)–(h) marked ⚠; rulings §4 has rows for §14, 23(b)–(h), 13, 17, 22, "extend the corpus or 33 folds"; block has the new keys | relaunch "diff against the REDTEAM Disposition; finish only what is missing" |
**Round 2 A/B1/B2/C DONE 2026-09-11 evening** (commits 2019acc, 1387113; suite 1,811 green; three censuses re-run;
`python3 backtest_e2.py` exits 2; no G3_RATIFIED.json). Rebuild facts: frame 7,618 joined / 7,389 modeling / 144 CIKs
(was 7,634 / 7,405); GLD 8 modeling rows excluded at run time (sensitivity arm adds them back); `n_emb_missing` 45;
OCF/revenue coverage 0.84 → 0.42 under duration matching; novelty prior gap median 91 → 364 d.
**Measured-cell refresh DONE 2026-09-11 evening** (commit ed457e2; 31 cells moved, each with its "(was X)" note;
scorecard scores 4,481 rows over 33 folds / 139 CIKs ex-GLD; run-time frame 7,381 / 143). **Second red-team pass DONE 2026-09-11 evening: still NOT safe** (22 of 24 first-pass items resolved; six new MUST-FIX —
NEGATIVE recall 0.487 → 0.529 (v1.2 adapter's own eval), overlap arm scores ~2,694 rows in folds not 4,859, CIK-level overlap on
the frame 75.0% not 15.85%, a forbidden "delisted names" sentence on the scorecard page, the OCF coverage cell unrefreshed,
four ⚠ with no §4 row; details + disposition appended to `data/f5/status/REDTEAM_g3_package_2026-09-11.md`).
**Round 3 IN FLIGHT:**
| item | launched as | expected output | if missing on resume |
|---|---|---|---|
| A3: census additions (ex-GLD fold census, overlap-arm rows in folds, CIK-level overlap, set differences, per-column coverage, v1.2 NEGATIVE recall read not typed), disclosure wording, chance line from counts, false-NONE + §0 citation, `loco.max_ciks_per_fold` required, `data/f5/pin_g3.py` (full pin substitution set; `--show` diff; `--pin --owner-word ratify`), stale partial parquet removed; censuses re-run | quant-modeler Opus | `data/f5/pin_g3.py` + `test_pin_g3.py` exist; census JSONs carry `section_1b_ratified_folds_ex_gld`; suites green; exit 2 | relaunch "check what landed first; spec = REDTEAM file second-pass Disposition" |
| C3 (after A3): document refresh for NF-1..NF-21 from the new census keys; §0 names `pin_g3.py` and the full substitution set | general-purpose Opus | no "0.487", "4,859", "15.85%" (unqualified) left in the pre-registration; §4 has the 23a-window and decision-21-scope rows | relaunch with the same brief |
**Round 3 DONE (commits 1f625ad, ed2b100; suite 1,819 green). Third red-team pass DONE: NO BLOCKER, 24 of 24 refreshed numbers
re-derived exactly, pin audited line by line; six small MUST-FIX (two stale census strings, chance line leaking the withheld
rate below 6 calls, 25/25 vs the mandated 25/49 stored-NEGATIVE precision on the page, three ⚠ without §4 rows, §4 omitting
the coverage consequences of 23a/23b and 20, pin command without an explicit --date). Record + disposition appended to
`data/f5/status/REDTEAM_g3_package_2026-09-11.md`.**
**Round 4 IN FLIGHT:** one general-purpose Opus agent applying MF-1…MF-6, SH-1…SH-8, N-a/e/f/g (census strings, scorecard
withholding, disclosure label, pin --date required, docstring/letters, §4 rows + consequences paragraph, thin-columns list,
packet banner, `test_census_e2.py` AST tripwire). Expected: those tests green; census JSON free of "4859" / unqualified
"15.85"; if missing on resume, relaunch with the third-pass Disposition as the spec.
**Round 4 DONE 2026-09-11 night — every item verified by the main session (tests + grep): suite 1,826 green; exit 2 holds;
no G3_RATIFIED.json; pin --show fires 8 rules / 21 lines / no residue; §13 Option 1 byte-identical since 0972add.**
**NOTHING IN FLIGHT. NEXT = THE OWNER'S WORD.** The owner reads `data/f5/G3_OWNER_RULINGS_2026-09-11.md` §4 (the ⚠ list,
the "what the owner should see before ratifying" paragraph, the consequences paragraph) and replies "ratify" (or corrects
a line). On "ratify": (1) HANDOFF §3 entry dated that day; (2) `python3 data/f5/pin_g3.py --show --date <that day>` and keep
the diff; (3) `python3 data/f5/pin_g3.py --pin --owner-word ratify --date <that day>`; (4) `python3 backtest_e2.py` (head 1 +
scorecard; `data/f5/head1_scorecard.md` is git-excluded — only the universe block in the results is committed); (5)
`python3 heads_e2.py --all`; (6) the owner reads the per-fold tables and the scorecard personally; (7) F6 write-up per the
§13 branch. Never pin or run on a model reading. Owner action items unchanged: EODHD subscription + token; the EODHD
written question about derived numbers before any public scorecard.
**Then (main session):** second red-team pass on the diffs → commit → ask the owner for "ratify" (showing the exact two
lines that change at the pin) → pin sha → run heads → scorecard. Never pin or run on a model reading.

**PREVIOUS IN FLIGHT: nothing (as of 2026-09-11 ~12:15 PT). The table below is that day's record; every row is DONE.**
| item | launched as | expected output | if missing on resume |
|---|---|---|---|
| P1a.2 fundamentals for arbitrary CIKs: `ingest_one.py --fundamentals` pulls the CIK's companyfacts via edgar_client, runs F2's concept-resolution classifier (`ingest_fundamentals.py`) for that CIK, writes `fundamentals.parquet` + `concept_resolution.csv` into the store; `report_filing.py --store` renders the PIT panel from the store | general-purpose Opus agent | `data/app/status/L2_3_external_fundamentals.md` with a 10-company coverage table | relaunch with "resume from existing stores; do not re-ingest what exists" |
| ~~P1a.3~~ DONE 2026-09-11 ~10:20 PT (`data/app/status/L2_4_diff_and_extraction.md`) — was: diff + extractor case + imputation line: `ingest_one.py --per-form 2` (prior same-form filing so the diff works on externals), the em-dash / split-possessive heading case handled in the APP-LANE extraction path only (never `extract.py`), the guidance-imputation share printed in the disclosure block; re-run the 10 companies at per-form 2 | general-purpose Opus agent | `data/app/status/L2_4_diff_and_extraction.md` with CBKM re-tested and per-company diff counts | relaunch with "resume; re-label only filings without a labels.parquet" |
| ~~F5 fix~~ DONE 2026-09-11 ~12:00 PT (numeric table rebuilt, sha `07971505…`; censuses re-run, counts identical; runners refuse) — was: `pit` period-end ambiguity (F5_PLAN §3 decision 22 DEFECT): a duration-aware resolver in `numeric_features_e2.py` (pit.py untouched so E1 known-answers hold), rebuild `numeric_features_e2.parquet`, re-run `backtest_e2.py --census` and `heads_e2.py --census`, red-team note | quant-modeler Opus agent | `data/f5/status/STEP1A_numeric_features_e2.md` §"period-end fix 2026-09-11" + rebuilt manifest shas | relaunch with "check whether the resolver change is already in the file before editing" |
P1a.2 DONE 2026-09-11 ~09:10 PT (`data/app/status/L2_3_external_fundamentals.md`).
Never run both labeling processes at once: P1a.3 labels; the others do not — if a resume finds a `label_filing` process alive, wait.

**P1a DONE 2026-09-11 (auto-resume relaunch finished it):** `ingest_one.py`,
`label_filing.py`, `report_filing.py --store`, `test_app_store.py`; sealed
seed-20260911 draw of 10 companies outside the universe, all attempted:
9 of 10 rendered a 10-K, 7 of 10 an earnings 8-K; **1 real extraction
failure** (CBKM: em-dash TOC "Item 7—" and a split possessive in the heading
defeat both extractor paths; `extract.py` is frozen for the E2 corpus, so it
is recorded, not patched); 2 companies had no earnings 8-K to render. 21.6
min total, 129 s per company (labeling 1.7–2.4 s/chunk), $0. Independent
containment check on SIRI: 0 of 481 rendered paragraphs outside the store's
own text. Record: `data/app/status/L2_2_external_companies.md`. Findings for
the owner: fundamentals are blank on every external company (F2 concept
resolution covers only the 244 CIKs); 55% of guidance labels on externals are
the missing→NONE imputation; no diff on externals at `--per-form 1`.

**DONE 2026-09-11 (all committed on main; owner pushes):** G3 packet delivered
(clock due 2026-09-25; decision-18 evidence corrected and re-sent); PRODUCT_PLAN.md
with §0.5 real-data-first rule, P1a, P-S, decisions A–F; Filing City prototype
published (artifact c5703ae7…; `site/prototype_city.html`; owner chose the
city + kinetic tone; next = owner picks the variant, then free-roam + living-
skyline interior); price-source comparison for decision A
(`data/app/status/PRICE_SOURCE_OPTIONS_2026-09-11.md`, recommendation ~$25/mo
Sharadar, nothing purchased). **OWNER-PENDING:** G3's 23 rulings; decisions A–F;
prototype direction. **NOT STARTED:** P2 portfolio simulator (needs decision A),
Track X extension labeling (needs wrapper lock fix), video/site build-out.

**STATE AS OF 2026-09-10 — F5 STEP 1a DONE (HANDOFF §3 entry of this date):
`target_e2.py`, `features_e2.py`, `numeric_features_e2.py` built, tested
(+73 tests, suite 1,401 green), red-teamed, freeze verified (no E2 IC exists
anywhere). Tables under `data/f5/` (git-excluded; shas in manifests; rebuild
with `python3 target_e2.py` 1 s / `features_e2.py` 19 s /
`numeric_features_e2.py` 4 min). Analysis frame after the three-way join is
7,634 rows (161–202 per quarter) — Step 2 must use that, not 16,859. Four
new G3 decisions (20–22 + benchmark member set) in `F5_PLAN.md` §3. NEXT =
**Step 1b DONE 2026-09-11** (HANDOFF §3): `backtest_e2.py`, `heads_e2.py`,
`text_families_e2.py` built + 143 tests, red-teamed, fix pass applied; both
runners refuse (exit 2) until `data/f5/G3_RATIFIED.json` matches
sha256(`data/f5/G3_PREREGISTRATION.md`) — neither exists; no E2 IC exists.
Suite 1,555 green. **NEXT = Step 2 census (`data/f5/census_e2.json`) then the
G3 packet (23 decisions in `F5_PLAN.md` §3).** **RULED 2026-09-11 (owner: "Adopt all three
defaults, record it, start the app lane" — HANDOFF §3):** sequence B
(interleave), scope + refusal list + disclosure block BINDING, 14-day G3
deadline from packet receipt. **APP LANE STARTED 2026-09-11:** L2.1 =
`report_filing.py` (per-filing HTML report over already-labeled E2
companies; ledger `data/app/status/`; outputs `data/app/reports/`,
git-excluded). **Step 2 census DONE 2026-09-11** (`data/f5/census_e2.json`; MDE at k=33 =
0.030–0.077 by branch; implied-floor branches UNPOWERED at any k). **Step 3
DRAFTED 2026-09-11 and red-teamed:** `data/f5/G3_PREREGISTRATION.md` (DRAFT,
not ratified, no sha pinned) + `data/f5/G3_OWNER_PACKET.md` (23 decisions);
parameter block validates against both runners; heads_e2 gained
`head2.last_event_quarter` and `head3.exit_screen`. **The packet has NOT been
delivered and the 14-day clock has NOT started**, because the owner's
2026-09-11 message ("can it tell me if I should invest / top companies /
marketable product / accurate advice") triggered KC5 (product pivot); the
council re-convened (`data/f5/status/COUNCIL_ADVISORY_product_truth_2026-09-11.md`)
and **the owner's charter ruling is pending** (HANDOFF §3 2026-09-11, last
entry). **App lane L2.1 DONE and red-teamed:** `report_filing.py` (98 tests;
containment of every rendered paragraph in the filing's own text verified
independently by the main session); reports under `data/app/reports/`.
**RULED 2026-09-11 (later the same day): the owner REAFFIRMED the
investing-product goal ("REFACTOR") — see HANDOFF §3 last entry and
`PRODUCT_PLAN.md`. G3 packet DELIVERED 2026-09-11; 14-day clock running (due
2026-09-25). Next: owner rules G3 (23 decisions) and PRODUCT_PLAN §4 A–D;
main session starts P2 (portfolio simulator) design, which needs decision A
(price source/budget) before money-metrics can be honest.** Gate G2 was RULED 2026-09-07
(proceed under the ladder; 2(b) extend). Repo committed on main; owner
pushes. LICENSE = MIT (owner-confirmed 2026-09-10).**

**PREVIOUS STATE (2026-09-07 ~20:30):** GATE G2 RULED "PROCEED UNDER THE LADDER";
2(b) RULED "EXTEND (promotion waits on own spot-check)". Plan in `F5_PLAN.md`.
Read `data/f4/g2/G2_FINAL_REPORT.md` §1.
- Owner ruled all 39 Part A + 20 Part B rows in chat 2026-09-07 (HANDOFF
  §3 "G2 OWNER ROW RULINGS RECORDED"); files `data/f4/g2/owner_rulings.json`
  + `probe_rulings.json`; analyzer re-run once → `results_g2.json` /
  `report_g2.md` stage `owner_ratified` (19 assertions, 0 API calls).
- `sentiment` 293/337 = 86.94% [82.93, 90.13] → INDETERMINATE at 0.85
  (k* PASS 300 / FAIL 273; A39 moved k 292→293).
- `guidance_direction` 115/119 = 96.64% [91.68, 98.69] → PASS at 0.85,
  never quotable without `guidance_active_precision` 68.67% [58.17, 77.55]
  (n_eff 84.8), `guidance_false_none_rate` 0/80 [0, 4.58], AND the owner's
  interpretation paragraph (`G2_FINAL_REPORT.md` §0: the 68.67% is partly
  directional-label precision under a rubric with no value for newly
  issued guidance — not evidence of hallucinated guidance).
- Probe 0/20 overturned → no sweep. `red_flags` 28.0% exploratory, unchanged.
- **Binding Rule 9 (owner):** new quantified guidance with no direction
  established relative to PRIOR guidance = NONE (`G2_FINAL_REPORT.md` §3).
- **RULED 2026-09-07 evening (HANDOFF §3):** Gate G2 = proceed under the
  ladder (no demotion); 2(b) = extend — extension labeling runs on nights
  AFTER the wrapper lock fix, and its labels are promoted into F5 only after
  their own spot-check. Rubric v1.3 change (ISSUED/INITIATED or
  `guidance_present`) recommended, not scheduled.
  DO NOT re-run any rater/adjudicator, the draw, or the analyzer
  (design §11; the owner-ratified stage is final).
- After the gate: F5 is blocked on design §3.4 (`features.py` must mask
  sentiment on RISK_FACTORS and guidance on MDA/RISK_FACTORS before
  aggregation) — not started.

**1. F4 — COMPLETE, integrity red-team-verified.** `data/f4/labels_e2_v1.parquet`
(317,081 rows, sha `f236f421…`), manifest `data/f4/campaign_manifest.json`.
Corrected close-out: `data/f4/status/F4_campaign.md` — read its §2 (the same
adapter behaves differently on E2 than on E1: flag incidence −9/−14/−7 pts by
section, guidance key omitted 33%→51%, sentiment emitted on 8.4% of
RISK_FACTORS) and §4 (seg-013 wrapper race, data intact; **2,826 rows carry
guidance on non-applicable sections → always filter `guidance_applicable`**).
Offline tests 118 green.

**2. G2 — OWNER-RATIFIED STAGE 2026-09-07 (see the STATE block above; gate pronouncement pending). The package below was built 09-06 and ratified 09-07; historical detail:** `data/f4/g2/`:
`G2_SPOTCHECK_design.md` (§13 = the owner menu), `build_draw_g2.py` (already
ran PROVISIONALLY at Option B → 420 chunks = P 300 + G-A 60 + G-N 60, seed
20260906, 11 blind batches + replicate; `draw_manifest.json.parameters_status
= PROVISIONAL_UNRATIFIED`), `analyze_g2.py` (selftest 59 checks; **exits 2
"BLOCKED" until `ratified_bars` is written — anti bar-shopping, do not
"fix"**), `finetune/test_g2_spotcheck.py` (20 tests).

**3. OWNER RULED 2026-09-07 (HANDOFF §3): Option C + direction floor + 15-row WITHDRAWN quota; bar 0.85 both fields; ladder ratified; no floors; ceiling n=120; guidance framing Option 1; council §7-3 "does not fire"; extension DEFERRED until G2 passes on core. Brief: data/f4/g2/G2_OWNER_BRIEF.md.**

**4. (HISTORICAL — this whole chain COMPLETED 2026-09-07; every file named below exists; do NOT re-run any step, design §11. Kept as the record of the planned order.) THEN, in order (design §10.3):** the redraw at Option C (re-running
`python3 data/f4/g2/build_draw_g2.py` for Option C; re-running at B is
pointless and mutates the manifest's `outputs` list — avoid) is being done
by the 2026-09-07 workflow; write the
rulings into `draw_manifest.json` per §10.2.3 → ship
`.claude/agents/label-rater-blind.md` (shipped 2026-09-07; body = design
§10.4 verbatim, ~30 lines; do NOT use `label-auditor`, its schema leaks
applicability) → write `data/f4/g2/build_adjudicator_batches_g2.py` (shipped 2026-09-07; mirror `data/hardening/spotcheck_v12/build_adjudicator_batches_v12.py`)
→ one blind rater per batch (11, plus batch_01_replicate as rater_b) →
`data/f4/g2/verdicts/rater_a_batchNN.json` → adjudicator →
`adjudications/adjudications.json` → `python3 data/f4/g2/analyze_g2.py`
(model-consensus estimate + `probe_ids.json`) → owner rules needs_human + the
20 probe rows → re-run analyze → owner-ratified estimate → **Gate G2**.

**5. DO NOT:** run `label_e2.py --segment` (nothing to label); launch any
rater before the §13 rulings; call any API (freeze re-sealed); quote the
manifest's 1,506.5 chunks/h (wrong — 1,455–1,461, see close-out §1). Lanes:
Fable plans/verifies, Opus executes (agent frontmatter already set), Sonnet
for ledger chores.

**UPDATE 2026-08-27 00:18: owner ruled epoch-2 GO and F3-P2 GO
(HANDOFF §3 2026-08-27). EPOCH 2 IS RUNNING** (run dir
`finetune/runs/2026-08-27-v12-epoch2/`, launched 00:18, ~9.2 h; on a
kill resume per `runs/2026-08-26-v12-epoch1/RESUME_RECIPE.md`, same
shape, tag `v12-epoch2-from-<N>`). **STATE AS OF 2026-08-27 ~13:10:** epoch 2 DONE (clean, val loss
0.076) · eval e2 DONE (sanity green — `runs/2026-08-28-v12-eval-epoch2/`,
red-flag macro F1 0.802) · **F3 P2 DONE 12:56** (28,900 sections, all
invariants held — `data/f3/status/P2_runs.md`) · **H3v2 full relabel
RUNNING** (~4.7 h from 13:05, log `data/hardening/h3v2/e1_relabel_v12.log`,
smoke passed 10/10 repro; resume = identical `relabel_e1.py --v12`
command; then `--v12 --finalize-only`) · **P3 QA agent IN FLIGHT**.
**OVERNIGHT CHAIN COMPLETE 2026-08-27 ~18:15. NOTHING RUNNING.
Everything is on disk awaiting the owner:**
- **G1 ruling package**: eval e2 `runs/2026-08-28-v12-eval-epoch2/`
  (beside `runs/2026-08-22-eval-epoch2/`); retention
  `data/hardening/status/H3v2_attenuation.md` §3 (family 0.6694 →
  0.8078 [0.7503, 0.8528], band inside CI; ~⅔ of the gain is the
  rubric per the 2×2; v1.2 teacher error UNMEASURED); council
  advisory `data/hardening/status/G1_council_advisory.md`
  (ACCEPT-WITH-CONDITIONS 5–0, sequencing split 3–2, §7
  pre-commitments proposed). Read LABEL_SHIFT first, as before.
- **F3 COMPLETE P0–P4** (`F3_PROGRESS.md`): corpus
  `data/filings_e2.parquet` 28,900 sections; P4's 2 blocking
  owner-visible items (`data/f3/status/P4_redteam.md` §11) are F4
  inputs, not G1 inputs.
- **RULED 2026-08-27 evening (HANDOFF §3): G1 = accept-with-
  conditions, B1; F4 config = W1-core + full reflow + missing→NONE
  at writer (≈314k chunks, 21–29 overnights).**
- **SPOTCHECK v1.2 COMPLETE AND OWNER-RULED same night: final P1 =
  84/200 = 42.00% [35.37, 48.93] — k exactly at the boundary →
  DEMOTE FIRED per the ratified pre-commitment. The E2 red-flag
  feature family is exploratory/disclosure-only in G3.** Sentiment/
  composition unaffected. Owner's 8 binding annotation-policy rules:
  `data/hardening/spotcheck_v12/OWNER_POLICY_RULINGS.md`. Probe
  0/20 overturns; campaign closed per its stopping rule. **B1
  SATISFIED. F4 scope RE-CONFIRMED post-demotion (owner, same
  night): KEEP W1-core + full reflow (~314k chunks, 21–29 nights).**
  **P5 DONE + verified. F4 PREP DONE + verified 2026-08-28 ~01:30**
  (105 tests green main-session-re-run; chunk table
  `data/f4/chunks_v1.parquet` sha `d67395ec…` — **317,081 chunks, 24
  accession-aligned chronological segments**; answer reserve 256;
  runner = `finetune/label_e2.py`, a sibling importing the
  byte-unchanged `relabel_e1.py`). **SMOKE PASSED ~01:40**: repro
  canary **10/10 byte-identical** to the G1 eval + all checklist
  items. **(HISTORICAL — campaign finished 2026-09-06)** **F4 CAMPAIGN IN PROGRESS — SELF-DRIVING since 2026-08-31 18:30:
  `data/f4/run_campaign_chain.sh` (a zero-model-turn shell loop,
  launched by the main session under the owner's Fable-outage
  continuity order) owns the chain for seg-011 → seg-024: it waits
  for the live segment process, then finalize→prepare→generate→
  finalize sequentially, resume-on-nonzero (5-attempt cap, halts
  safely), log `data/f4/campaign_chain.log`. CRITICAL: while the
  wrapper runs, NO ONE (model or human) may launch `label_e2.py
  --segment` manually — double-driving a segment corrupts its
  journal. If the wrapper died (`pgrep -f run_campaign_chain`),
  re-running the script resumes everything safely. Owner's phrase to
  restore normal supervision: "resume Fable operations."**
  Continuous chaining per owner ruling (nights-only hold offered,
  declined). Loop per
  `data/f4/RUN_COMMANDS.md` §5: prepare → background generate →
  finalize → next; resume = identical command; never from a
  subagent. **Progress: check `data/f4/segments/seg-0NN/manifest.json`
  (finalized = done) — seg-001 DONE 2026-08-28 08:50 (13,227/13,227,
  0 parse fails, 1 benign out-of-taxonomy enum recorded, 1,621.6
  ch/h → ~8 days continuous / ~20 nights at measured rate); seg-002
  launched 08:55.** Traps in `F4_prep.md`:
  chronological order is load-bearing; 12.9% of chunks come from
  FLAGGED sections (filterable by join, no exclusion ruled); 8K_BODY
  (790 chunks) not evaluable. **G1 is ruled by the owner
on the eval-e2 report + the H3v2 retention numbers** (beside
`runs/2026-08-21-eval-epoch1/` + `runs/2026-08-22-eval-epoch2/`;
read `data/hardening/LABEL_SHIFT_v11_v12.md` first).
Epoch-1 record + numbers: `HARDENING_PROGRESS.md`.
**OVERNIGHT AUTONOMY GRANTED (HANDOFF §3 2026-08-27 item 5):** the
chain above runs unattended to completion, incl. a tech-council G1
advisory and P4 after P3 if time allows. NOT delegated: the G1
ruling, API calls, live fetches, F4, epoch 3. A fresh session
resuming mid-chain: find the running/last task via `ps aux | grep -E
'mlx_lm|eval.py|extract.py|relabel_e1'` + each run dir's log, then
continue the sequence exactly as written here.

## State in one screen

- **E2 corpus: COMPLETE and verified** (F2 + F2.5 hardening). 45,632
  filings / 42 GB documents / 622,661 fundamentals rows / 1.96M price
  rows. Ledgers: `F2_PROGRESS.md`, `HARDENING_PROGRESS.md`.
- **G1 repair: labels bought, dataset staged, retrain epoch 1 RUNNING
  (launched 2026-08-26 12:07 on the owner's command).**
  Rubric v1.2 re-label complete — `data/labels_v12.parquet`,
  **6,747/6,747, zero gaps** (cost ~$24.92 + $0.0014; account has ~$5
  loaded; **spend freeze RE-SEALED** — any API call needs a new owner
  ratification). v1.2 splits/MLX data/configs all built and sha-pinned;
  label-shift record at `data/hardening/LABEL_SHIFT_v11_v12.md`.
- **F3 extraction: code DONE (P1), runs (P2) NOT started.** Ledger:
  `F3_PROGRESS.md`.
- **Stopping rule: RATIFIED** (Option 1 + margin procedure — HANDOFF §3
  2026-08-26). **Gate G1: HELD** — ruled by the owner after the
  retrain's re-eval.

## Campaign 1 — the v1.2 RETRAIN (launch on the owner's command)

**The entire campaign is copy-paste from
`finetune/runs/2026-08-26-v12-epoch1/RUN_COMMANDS.md`** (sections 0–6:
pre-flight with expected test counts → epoch 1 → eval 1 → OWNER READ →
epoch 2 → eval 2 → OWNER RULES G1). ~9.2 h per epoch + ~57 min per
eval ≈ 20.2 h machine time total, $0, zero API calls.

Non-negotiables baked into the runbook: training runs as a
MAIN-SESSION background auto-resume chain (HANDOFF §4 — never from a
subagent; on a kill, re-run the identical command; if segmented, point
`--train-manifest` at the LAST segment's manifest — the one real trap,
documented in RUN_COMMANDS §8). The training instruction is FROZEN at
E1's (`ebc45a85…`) — the v1.2 change is the LABELS ONLY (single-axis;
see `data/hardening/status/G1_repair_dataset.md` for why the
instruction must not be swapped).

**For the owner's G1 read** (after eval 2): put the new reports beside
`runs/2026-08-21-eval-epoch1/` + `runs/2026-08-22-eval-epoch2/` — same
epochs, same frozen 1,010 rows, same instruction, different rubric.
Read `data/hardening/LABEL_SHIFT_v11_v12.md` first; note especially
that the REALIZED liquidity-stress class the owner emptied at the E1
spot-check repopulated to 15 under v1.2 (P2 was deliberately not
encoded — flagged in `labeling_rubric.md` §9).

## Campaign 2 — F3 P2 extraction runs (also awaiting go)

Four commands, in `F3_PROGRESS.md` + `data/f3/status/P1_impl.md`:
`extract.py --segment earnings` (~21 min) → `--segment 10-K` (~45–75)
→ `--segment 10-Q` (~55–90) → `--merge`. Main-session background
tasks, resume = identical command, `cache_miss` must be 0 (nonzero =
FATAL stop, never a fetch). **Do NOT run concurrently with training**
— both compete for the same 16 GB M5; sequence them (extraction fits
easily before or after a training night).

## Owner decisions pending (nothing else blocks)

1. ~~Go for Campaign 1~~ — **GIVEN 2026-08-26; epoch 1 running.** The
   epoch-1 → epoch-2 step remains its own owner gate (RUN_COMMANDS §4).
2. After its re-eval: **the G1 ruling** on the repaired labeler.
3. Go for Campaign 2 (F3 P2) — sequenced around training.

## Standing constraints (verify at HANDOFF §4/§5/§7 before acting)

No Anthropic API calls (freeze re-sealed; ~$5 balance is NOT
authorization). Long compute = main-session chain only. E1 artifacts
frozen (incl. `data/labels.parquet`, `finetune/splits/`,
`data/filings_metadata.db`). Model tiering: Fable orchestrates, Opus
executes, Sonnet simplest. Lazy-elite engineering. Every ledger flip
needs its on-disk completion report.

## Ledger map

`HANDOFF.md` (charter + decision log §3) · `EXPANSION_PLAN.md` (+§8
amendments) · `REEVALUATION_2026-08-25.md` (the honest verdict) ·
`HARDENING_PROGRESS.md` (F2.5 + G1 repair campaign) · `F2_PROGRESS.md`
· `F3_PROGRESS.md` · `TEAM.md` (agent roster; `tech-council` for
big decisions) · `PRIOR_WORK.md` (citations unverified) · run docs in
`finetune/runs/2026-08-26-v12-epoch1/`.
