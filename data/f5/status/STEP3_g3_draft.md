# STEP 3 — G3 pre-registration DRAFT + owner packet

Written 2026-09-11 by the `research-statistician` session executing **F5_PLAN §2
Step 3**. Two files produced. **Amended the same day by a second
`research-statistician` pass applying a red-team review** (items A2–A3, B1–B7,
C1–C5, D1–D4, E1–E7); that pass edited only `G3_PREREGISTRATION.md`,
`G3_OWNER_PACKET.md` and this file, and the numbers below are the post-fix ones.

**Freeze status (F5_PLAN §1): clean.** No IC, delta, correlation, model fit or
feature-versus-outcome association was computed. `data/f5/G3_RATIFIED.json` was
**not** created and does not exist; `python3 heads_e2.py --head2` still exits **2**
with the refusal, re-verified after the fix pass landed. No network. The fix pass
re-derived counts only — the exit-screen numbers below were recomputed by calling
`heads_e2.load_exit_events()` / `build_head3_panel()` and counting rows, which is
the same census-class arithmetic §2 Step 2 already ran; nothing was fitted.

## Files

| file | what it is | size |
|---|---|---|
| `/Users/vihanpatil/personal/projects/FinScreen/data/f5/G3_PREREGISTRATION.md` | the H5 §6 skeleton §0–§13 instantiated as a fill-in table (convention · measured population · DRAFT rule + decision number · enforcing test), plus the single `json g3-params` parameter block | 248 lines; **6,399 words**, 85% of them inside four-column table cells |
| `/Users/vihanpatil/personal/projects/FinScreen/data/f5/G3_OWNER_PACKET.md` | plain-English ruling packet: opener, the fixed scope sentence, 23 decisions in **four** groups (A: 3, 4, 13, 15, 20 · B: 7, 8 · C: the fourteen wave-throughs · **D: 18, 19, the pre-commitments only the owner can discharge**), each with a one-line RULE, the three things the run cannot give, and a cost-of-defaults paragraph | 419 lines, **4,184 words**, no tables |

## Length — honest page bands, and the constraint that is broken

Two estimates, both stated so the band can be argued with rather than trusted.

| document | prose-density floor (450–550 words/page) | four-column layout model | **honest band** |
|---|---|---|---|
| `G3_PREREGISTRATION.md` (6,399 words) | 12–14 pages | 19–25 pages | **~13–19 rendered pages** (floor 12, ceiling ~25) |
| `G3_OWNER_PACKET.md` (4,184 words) | 8–9 pages | 8–11 pages | **~8–10 rendered pages** |

*Layout model:* 11 pt, US-Letter, 1 in margins → a ~95-character text column and
40–52 body lines per page; a table row is as tall as its tallest cell, with each
column given a share of the 95 characters proportional to that column's 90th-
percentile cell length. Prose density is a **floor** for the pre-registration,
not an estimate: in a four-column row whose "DRAFT rule" cell runs 200 words, the
other three columns sit mostly empty for the full height of the row. The packet
is pure prose, so the two models agree there.

**The CTO's constraint is broken, and by more than the last version said.** H5 §2
(CTO seat) asks for "≤ ~3 pages, a fill-in table, not a treatise". At ~13–19
pages the pre-registration exceeds it by roughly **4–6×**. The previous version of
this file claimed "≈ 4–5 rendered pages" for a 5,009-word document — that implied
~1,000–1,250 words per page and was simply wrong; the red-team's own re-estimate
of that draft was 9–13 pages, and this fix pass added ~1,390 words to the
pre-registration and ~1,350 to the packet (the ICC list, the like-for-like MDE
comparison, the exit-screen blind spot, the parameter-block scope map, decisions
16 and 18, the seven-financials hole, the cost-of-defaults paragraph).

**Why the content was kept anyway.** Every line of the overrun is a measured fact
the brief requires to be in the pinned document: §1 pins each transform as a
function plus arguments (H2's finding that seven implementations of one *name*
spanned 0.059 in the headline — a named transform pre-registers nothing), and §11
carries every instrument disclosure F5_PLAN Step 3 enumerates. Cutting to three
pages means deleting measured facts from the artifact whose whole purpose is to
be un-amendable after the answer exists. No prose essays were added to the
pre-registration: every §0–§13 row is still a table cell. The packet is the
document the owner actually reads end-to-end, and it is 8–10 pages, not 3.

## §13 — cell-by-cell diff against `H5_stopping_rule.md` §3: **0 differences**

The Option 1 row of H5 §3's options table has **7 cells**. Each was compared to
§13 of the pre-registration as an exact substring, after restoring the dropped
clause **", via the E3 policy"** at the end of the mid-cap cell (item A2) and
splitting the title so `**1 (RECOMMENDED)**` and `**Hard top + price annex**`
survive as the two separate cells they are in H5:

| H5 §3 Option-1 cell | length | verbatim in §13 |
|---|---|---|
| `#` | 19 ch | yes |
| Option | 26 ch | yes |
| Bounded null | 162 ch | yes |
| Above-MDE positive | 267 ch | yes |
| Ambiguous-inside-MDE | 193 ch | yes |
| E3 policy | 244 ch | yes |
| Mid-cap ramp (§7) | 195 ch | yes |

**0 differences.** Stronger than substring containment: §13's quoted paragraph is
a **byte-exact reconstruction** of `"> " + cell1 + " · " + cell2 + ". "` followed
by each remaining cell prefixed with its own H5 column header (`**Bounded
null:** `, `**Above-MDE positive:** `, `**Ambiguous-inside-MDE:** `, `**E3
policy:** `, `**Mid-cap ramp (§7):** `) and joined by `". "` — nothing else was
inserted, nothing was dropped. The **cross-head clause** is byte-verbatim as
well. Re-runnable from the two files with no other input.

## Checker results (run against the draft document directly; the guard was NOT used)

```
backtest_e2.extract_params_block(doc)      OK   -- exactly one ```json g3-params block,
                                                valid JSON, 22 top-level keys
backtest_e2.validate_params(params)        PASS -- 43/43 required paths present and
                                                correctly typed; params_version matches;
                                                every named rule implemented; fold_quarters
                                                and margin.ladder non-empty; the
                                                loco.index_rule/n_folds consistency check passes
heads_e2.check_required(REQUIRED_HEAD2)    PASS -- 11/11 keys + SUPPORTED value checks
heads_e2.check_required(REQUIRED_HEAD3)    PASS -- 15/15 keys + SUPPORTED value checks
```

**The two new keys pass, and the reason is that the parallel code change landed
first.** The brief expected `head2.last_event_quarter` / `head3.exit_screen` to
*fail* `check_required` until then. They do not, as of this run:
`REQUIRED_HEAD2` now holds **11** paths including `head2.last_event_quarter`;
`REQUIRED_HEAD3` holds **15** including `head3.exit_screen`; and
`SUPPORTED["head3.exit_screen"] == ("none", "no_in_membership_filing_within_1y")`,
so the pinned value is an implemented rule rather than a name. Two consequences
were written back into the documents rather than left stale:

1. §8 and §9 no longer say "NOT EXPRESSIBLE / NOT YET IMPLEMENTED"; they cite the
   new tests (`test_head2_ends_at_the_pinned_last_event_quarter`,
   `test_a_missing_last_event_quarter_is_a_refusal`,
   `test_the_exit_screen_drops_rows_whose_cik_keeps_filing`,
   `test_rows_the_exit_screen_cannot_judge_are_counted_not_dropped`,
   `test_an_unimplemented_exit_screen_is_a_refusal`,
   `test_run_head3_applies_the_pinned_exit_screen`).
2. **A claim in the packet went false and was corrected.** Decision 13 said the
   clean 129-row exit population "needs a code change and therefore a new
   pre-registration". With the screen implemented it is simply *all four kinds
   with the screen on*, so the live trade-off is now **two kinds + screen → ~54
   positives** (the default) versus **four kinds + screen → 129**. Leaving the old
   sentence would have hidden a real option from the owner.

Additional checks run beside the four checkers:

- `G3_PARAMS_SCHEMA.json.required_keys` and `backtest_e2.REQUIRED_PARAMS` are the
  same **43**-path set; 0 required head-1 paths missing from the block.
- Every pinned column exists in the real tables: `columns.numeric +
  confirmatory_text + family_novelty + exploratory_red_flags + size_col +
  overlap.column` → **0 absent** from the union of
  `target/text/numeric/families`.
- **108 test names** are cited in the enforcement column; all 108 resolve to a
  `def test_...` in the file their prefix (BT/HE/TG/FE/NF) or their explicit
  `file.py::name` path names. **0 unresolved.**
- The block gained 6 keys and stays valid because `validate_params` checks
  presence and type, not closure: `spec.ticker_col`, `spec.date_col`,
  `families.novelty_prior_rule`, `families.novelty_min_shingles` (documentation),
  plus `head2.last_event_quarter` and `head3.exit_screen` (now required by the
  runners). `post_2019_fold_quarters` gained a sibling `_note` marking it
  documentation-only — the runner reads `post_2019_first_quarter`.
- **Document sha256 (post-fix):
  `ad710936b242a79fe41b52095865641555e4c2a50097f74d2128d361a886b329`**
  (was `714e22d2dea0e90f5b524b54c32b2fba50bfa1d0f102c9dc82c6f6cee721f40f` before
  this pass). Packet sha256
  `c231fe324149bb99e62f54795ac5fa5fe2d2f79ccb645affe95074a01ba4a6da`. Recorded
  here as a session fact only; **nothing is pinned, and both will change again
  when the owner's rulings are edited in.**

## What the fix pass changed, with the re-derivation behind it

| item | change | re-derived from |
|---|---|---|
| A2 | §13 restored to byte-verbatim Option 1 (`, via the E3 policy`) | `H5_stopping_rule.md` §3, 7 cells, 0 differences |
| A3 | "324 subjects delist mid-window" → **324 modeling rows with a complete window but no subject price**, cause not separately measured | `target_e2_manifest.json .row_counts.n_complete_window_missing_subject_price` = 324 |
| B1 | ICC claim corrected to **9 of 13 raised, 6 sharply**, all nine named | `census_e2.json .section_6… .rows[]`, recomputed row by row |
| B2 | Channel B **27 → 29 rows**, over 14 folds 2018Q1–2021Q2 | sum of `censor_B_n_rows_priced_no_usable_target` across `section_1….default_33.per_fold` |
| B3 | would-be panel **99 → 98** companies (16/98 = 16.3%) | `…default_33.per_fold[0].would_be_cik_panel` |
| B4 | "~5%, not 11%" replaced by two separate comparisons | `section_2….at_measured_n_dd`: k=33 **0.0303/0.0408** vs k=26 **0.0338/0.0455** → **10.58% / 10.33%**; vs published k=26@n_dd 158 (**0.0315/0.0424**) → **4.06% / 3.79%** |
| B5 | MDE/threshold headers relabelled **"Projected (from E1's noise anchor; E2's own SE is measured at Step 4)"**; "Measured" kept for counts | `section_2….these_are_projections` |
| B6 | exit-screen blind spot + the two counter names | recomputed: **31 of 480** exit rows filed within 365 d of panel end 2026-08-24; **6** of them in the pinned two-kind set (2 Form 25 + 4 Form 15); screen drops **64** of 118, keeps **54** |
| B7 | TOST `t` multiplier **+3.1% → +3.2%**; 60.2% qualified as a rule outcome; per-family range labelled | 2.889932 / 2.8 = 1.0321; `n_rows_treated_post_close_under_ported_rule`; floor-free ρ_f 0.3 **0.016–0.098** beside implied-floor **0.031–0.185** |
| C1 | §7 rows retagged (4, not 7); §0 and §10 retagged as H5 conventions, not 17; §1 overlap arm tagged (3); §8 DV already carried (12) and was left | F5_PLAN §3 decision list; H5 §§0, 7, 10 |
| C2 | decisions **16** and **18** added as §0 pre-commitment rows | F5_PLAN §3 rows 16/18; H5 §5 KC1; Track X4 |
| C3 | §12 embedding model → **"DRAFT: to be ratified as a third-party artifact (23h)"** | nothing is ratified while the document is DRAFT |
| C4 | §1 Family A now pins the **default** (`prior_year_same_form`, `min_shingles = 50`) as function + arguments and describes the as-built quarter-over-quarter table as the thing a rebuild replaces | `section_8…decision_23a/23b`; **50** is the threshold the census already measured at, below the RISK_FACTORS min-shingle median (86) and two orders below MDA's (6,697) |
| C5 | `spec.ticker_col` / `spec.date_col` added to the block, with a note that `run_head1` supplies them from `CIK_COL` / `FILING_DATE_COL` | `backtest_e2.run_head1` `spec_kwargs` |
| D1 | post-2019 arm stated as a **restriction of the same 33 fits, no refit**, training still 2016–2018; `post_2019_fold_quarters` marked documentation-only | `run_head1` reads `post_2019_first_quarter` only |
| D2 | §11 train-overlap now cites FE `test_real_build_reproduces_every_pinned_census_number` | that test pins `N_TRAIN_OVERLAP = 14342` and the three channels (10,442 / 14,341 / 487) |
| D4 | §0 "one unambiguous parameter source" now maps honestly which decisions the block expresses (3, 4, 5, 6, 12, 13, 14, 15, 23g) and which are enforced by module constants, by a rebuild, or not at all | `REQUIRED_PARAMS` vs the decision list |
| E1–E7 | packet: non-goal (3) rewritten to "nothing REPORTS a per-company score", HANDOFF §1 and the 2026-09-11 boundary sentence cited separately; 18/19 moved to Group D; cost-of-defaults paragraph; seven-financials hole; 4.53% beside 80.2% with the never-quote-one-as-the-other warning; the floor softened to "first chance to measure it"; "480 exit rows (not positives)", "label precision, not classifier precision", `8: ratify`, and the fixed scope sentence added | HANDOFF §1 / §3 (2026-09-11); census §E; rebuild runtimes 19 s / 250 s / 18 s / 1,514 s |

## Rows that remain NOT YET ENFORCED

Two of the three old categories survive; the third is closed.

**(a) Governance conventions with no testable surface** — post-hoc amendment
labeling and the sha-pin (§0); the two new pre-commitment rows, decisions 16 and
18 (§0); "one primary per head / heads cannot rescue each other" (§10);
model-rater epistemics, F4 drift, the λ sourcing rule, the teacher-arm control,
H3v2 per-feature retention, the labeler adapter sha, the seven-financials
extraction hole, the survivorship direction (§11); SIC drift and the embedding
artifact's weights sha (§12); the ranks-primary rationale and the honest-MDE
constants (§1). These are report contents, not code paths.

**(b) DRAFT defaults that differ from the artifact on disk — adopting them is a
rebuild, not a document edit.** decision **7** (FX: no code path, no test, 108
currency-blocked rows — ingest + rebuild + new test); decision **20** (same-CIK
attribution; `text_features_e2.parquet`, ~19 s); decision **21**
(duration-match; numeric rebuild, ~4 min); decisions **23a/23b** (family A is
quarter-over-quarter with no stub filter, ~18 s); decision **23d** (85 8K_BODY
sections are embedded, ~25 min); decision **2** (GLD's analysis-side exclusion
has no test — only the target-layer flag does).

**(c) CLOSED.** The two rows that were "NOT EXPRESSIBLE in the parameter schema"
are expressible as of 2026-09-11: `head2.last_event_quarter` and
`head3.exit_screen` are required keys with implemented behaviour and their own
tests. What is *not* closed: the screen is a **proxy**, not a corporate record —
it infers "this row ended membership" from the absence of a later in-membership
filing, which is why the 6 unscreenable rows inside the pinned set are counted
and never scored as clean.

Still carried as flags, not findings: **§7's per-fold channel-A censoring count**
and the rule that **both censoring arms appear in the results** have no test;
`post_2019_first_quarter` is enforced only as a required key.

## Known inconsistency outside these three files (not edited — flag only)

`data/f5/status/STEP2_census_e2.md` §A and §G say ranking "raises the ICC of six
of thirteen features". The census JSON it summarizes shows **nine of thirteen
rise; six rise sharply (≥ 0.15)**. `F5_PLAN.md` §3 decision 3 has it right ("nine
of thirteen, sharply for six"). The pre-registration and packet now both carry the
nine. The STEP2 status file should be corrected by whoever owns it next; this
session's brief limited edits to the three G3 files.

## Deliberate non-actions

`data/f5/G3_RATIFIED.json` not created; no IC, delta or feature-versus-outcome
statistic computed; no file outside the three named ones edited (`F5_PLAN.md`,
`HANDOFF.md`, `census_e2.json`, every module and test untouched by this session —
`heads_e2.py` / `test_heads_e2.py` were changed by the parallel code session, not
this one); the guard was never invoked to "test" the draft — the checkers were
called directly on the document text.

## Next

Owner reads `data/f5/G3_OWNER_PACKET.md` (the 14-day clock starts at receipt,
owner ruling 2026-09-11) and rules the 23 decisions in chat — Group D (18, 19) is
**not** covered by a Group-C wave-through. The main session then edits the DRAFT
rules into ratified rules, re-runs the four checkers, computes the sha256 of the
edited document, writes it into `data/f5/G3_RATIFIED.json`, and records the
ratification in HANDOFF §3. The remaining (b) rebuilds must run and be reviewed
against the ratified document before head 1 — never as a silent fallback.
