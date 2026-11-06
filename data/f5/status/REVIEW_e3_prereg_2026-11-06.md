# REVIEW — E3 Steps 1–2 (census + DRAFT pre-registration + owner packet), 2026-11-06

Reviewer: `reviewer` (Opus), adversarial pass. Nothing was fixed. No IC, correlation or fit against
`target_excess_63` was computed by the reviewer; the outcome column was read only via `.notna()`. Means
of already-committed per-fold IC numbers in `results_head1.json` were read (the same operation the census
performs in `prior_exposure`) to size a disclosure gap.

Grades: **DEFINITE** = definitely a defect; **LIKELY** = probably a defect; **LOOK** = worth a look.
Dispositions: **must-fix** (before the packet goes to the owner) / **should** / **note**.

## 0. What was checked, and how

- **Re-run.** `data/f5/census_e3.py --data-root <main>/data` under the CLT 3.9 interpreter. Output is
  identical to the committed `census_e3.json` except `generated_utc` and runtimes. The committed JSON
  (sha `7774de1b…`) was backed up and restored byte-exact, so the artifact under review is unchanged.
- **Independent re-derivation** from the parquets, written separately from the census code (scratchpad
  script). It covers the frame chain 29,271 → 16,859 → 16,859 → 16,397 (462 null) → 16,383 (14 GLD),
  and A = 3,642 / 143 CIKs (10-Q 2,732, 10-K 910). B = 7,381 (8-K 3,884 / 10-Q 2,629 / 10-K 868), which
  reproduces census_e2 `section_1b_ratified_folds_ex_gld` (6,184 / 4,481 / 135.79 / 118 / 161 / 139 / 6,173).
  It also covers A's in-fold count of 3,053 with n_dd 80–100 and mean 92.52, the sectors, fx 24/48/112,
  every family any/all coverage on A/B/C, the ≥3 and all-4 shares (98.5% / 74.2% overall; 3,040 = 99.6%
  and 2,438 = 79.9% in folds), the early-fold profitability rank coverage 0.450 / 0.543 / 0.788 / 0.929 and
  ≥ 0.969 from 2019Q1, value 0.804–0.867, ≥3-of-4 per fold 74–100, 2018Q1 all-4 = 30 of 80, rank loss ≤ 1
  per column, and purge 418 → 3,354 at 16.2% → 2.9%. **All match**, except the items in N1 and N5.
- **MDE table.** All 24 rows were recomputed from the four anchors read independently from
  `results_head1.json` and `controls_results.json`. The AR(1) multiplier at ρ = 0.3, k = 33 is 1.3491,
  checked by the full-matrix variance, not by the census formula. The Holm worst-case multiplier is
  z(0.99375) + z(0.80) = 3.3393. The independence bounds come out at 0.0182 / 0.0151 / 0.0104, and the
  ladder picks match. The SE caps Δ/2.487 are 0.0161 / 0.0201 / 0.0241 / 0.0322 / 0.0402. **All match.**
- **Dating, feature-only.** On all 3,763 in-membership 10-K/10-Q rows, `pre_session` < `news_session` <
  `window_open_session` and `window_open` > `info_date` (100%), and the news sessions and info dates of
  the target and numeric tables agree (100%). No price factor touches the target window.
- **Freeze.** `git status` shows only the six new untracked files. `backtest_e2.py` `746389ae`,
  `backtest.py` `91837531`, `spec.py` `e8396d8e`, `numeric_features_e2.py` `0334c23c` and `scorecard_e2.py`
  `6b5263ed` match the G3 run record and F6 §6. `head1_oof_predictions.parquet` measured `378b0b71…` = the
  `run_log.jsonl` `oof_predictions_sha256`. `E3_RATIFIED.json` is absent. `test_census_e3.py` and
  `test_census_e2.py`: 9 passed.
- **Spend, licences, charter.** No API or network path in the census, no new service and no new EDGAR
  fetch. The Yahoo provenance is stated in §11. A scan of the three E3 documents for advice, "beats",
  return or alpha language found none.
- **Sign contamination.** `results_head1.json` and the f5 reports carry no feature importances or
  per-feature ICs, so no pre-registered sign could have been read off a G3 output.

---

## MUST-FIX

### M1 — §12 "prior exposure" omits the G3 result computed on (almost exactly) frame A — DEFINITE
`data/f5/E3_PREREGISTRATION.md:170-184`; `data/f5/census_e3.py:407-458`; `data/f5/E3_OWNER_PACKET.md:25-29`.
`results_head1.json .form_controlled_ablation` holds per-fold ICs of G3's fitted `numeric_only` block on
the **10-K/10-Q rows of the E2 frame (3,497 rows = 96% of frame A's 3,642)**, ranked within that
periodic-only pool, exactly as the census ranks A. The committed per-fold numbers read as follows:

- `numeric_only`, dedup: **+0.0250, 20/33 folds positive**
- `text_and_numeric`: +0.0311
- fitted `size_only`: −0.0001
- `dedup_no_overlap`: +0.0339

Further omissions:
- `per_fold_ic__raw_levels` `numeric_only` dedup: +0.0207.
- `per_fold_ic__pit_trailing_rank_no_same_day` `numeric_only` dedup: **+0.0220**. E3 runs this exact
  same-day arm (§7.1).
- The per-fold `quintile_spread` of every block.
- The G3 scorecard's `numeric_only` hit rate, 0.5099 [0.4919, 0.5278] (and per-company rows on disk).

The census `prior_exposure` block reads only the `pit_trailing_rank` arm. The packet's "+0.025 on these
same rows" is the frame-B number. The frame-A-relevant number is the form-ablation +0.0250. The values
happen to coincide, but the claim is wrong as sourced.

**What it breaks:** the §12 "nothing is hidden" claim and §0's "Prior exposure disclosed" row. The owner
would rule without knowing that the proposed primary frame has already been scored by a fitted model on
the same features. **Disposition: must-fix.** Add the form-ablation, raw-levels and no-same-day rows
(and the scorecard line) to §12, the census block and the packet.

### M2 — The primary test's level is stated two incompatible ways — DEFINITE
`E3_PREREGISTRATION.md:60` ("Two-sided test against 0"), `:131` ("two-sided test at α = 0.05"),
`:274` (`"two_sided_alpha": 0.05`). Against these, `:203`'s positive branch reads "90% CI excludes 0 in
the pre-registered direction", which is a one-sided 5% test (two-sided 10%). The MDE uses 2.8 = z.975 +
z.80 (two-sided 5%); the 90% CI corresponds to 2.487. A point estimate between 1.645·SE and 1.96·SE is
"positive" under §13 and "not significant" under §1.

**What it breaks:** `backtest_e3.py` cannot implement the primary decision from the params block
unambiguously, and the two readings give different branches. **Disposition: must-fix.** Pick one: (a) a
two-sided 95% CI excludes 0 for the positive branch, with the 90% CI kept for TOST; or (b) one-sided 5%,
with the MDE multiplier made 2.487. Then put that one rule in the params.

### M3 — The ladder to 0.10 makes the likely outcome a "bounded null" the document itself calls empty — DEFINITE (design coherence)
`E3_PREREGISTRATION.md:63, 204, 29-31, 279`; `E3_OWNER_PACKET.md:49-51`. G3's ratified rule was
`Δ = min{d ∈ [0.03, 0.04, 0.05]} … never above 0.05` (`G3_PREREGISTRATION.md:92`). E3 extends the ladder
to {0.04 … 0.10}. On the measured size anchor (SE 0.027, Δ = 0.08), a bounded null fires whenever
|point| < 0.08 − 1.645 × 0.027 ≈ **0.036**. That is the modal outcome for a ~100-name large-cap factor
composite. Three things then follow:

1. The bounded-null branch "closes" the numeric families (`:204`).
2. The mandated scope sentence says no IC "of economically relevant size is detectable" (`:29-31`).
3. The same document says *"a bound at Δ ≥ 0.08 excludes nothing a documented factor is expected to
   show"* (`:63`).

Packet item 4 calls this "the G3 rule". It is G3's procedure, with G3's 0.05 cap removed.

**What it breaks:** the most probable branch yields a null label, and a scope sentence that the
pre-registration knows to be false at that Δ. A later write-up will read "E3: bounded null". This is the
"maybe underpowered" problem in reverse. **Disposition: must-fix (the owner chooses the remedy).**
Either cap the ladder at 0.05 as G3 did, so that the honest expectation reads UNPOWERED, or map any
Δ > 0.05 bound to the UNPOWERED or ambiguous branch with its own sentence. Either way, the packet must say
that this departs from the ratified G3 cap.

---

## SHOULD

### S1 — Survivorship is invisible in the E3 census, and the G3 censoring arm was dropped — LIKELY
`census_e3.py:122-142`; `E3_PREREGISTRATION.md:118-125, 163`.
- `target_e2.parquet` carries **149 CIKs**. The 27 never-priced core CIKs (G3 §7: 16 CIKs = 16.3% of the
  2018Q1 panel → 0 by 2025Q3) never enter any E3 frame, and the census counts them nowhere.
- G3 §7's per-fold channel-A count ("reported every time, never silently dropped") and its **mandatory
  post-2019 censoring arm** are not carried to E3 §7. Yet the 2018 folds are both the most censored and
  the ones with the thinnest profitability coverage (0.45–0.93).
- The null-target rows are dropped **before** ranking, so the comparator pool is conditioned on
  price availability: one CIK, 61 in-fold rows, 14 of them periodic.
- The survivorship direction differs by family. Dropping dead high-vol / low-momentum losers biases the
  low-vol and momentum ICs down, while dropping dead distressed high-B/M names biases value up. The
  inherited generic sentence ("understates downside dispersion") does not say this.

**What it breaks:** "censoring counted, never dropped" on the primary frame, and the reader's ability to
tell a 2018-driven result from a survivorship artifact. **Disposition: should.** Count the per-fold
channel A on A, add the post-2019 arm (2019Q1+, the same scores), and state the per-family direction.

### S2 — The packet attributes the main session's reading to the owner — DEFINITE
`E3_OWNER_PACKET.md:31`: "**No money metric** (your ruling B, 2026-11-05: no EODHD, no spend)". The
owner typed only "**B. No**" (`HANDOFF.md:1801`) in answer to "subscribe to EODHD?"
(`OWNER_DECISIONS_2026-11-05.md:45`). "No money metric until reversed" is the main-session reading
(`HANDOFF.md:1809-1811`). The pre-registration header (`:34`) labels it correctly; the packet does not.
Decision 9 also bundles (a) the contamination disclosure and (b) an exception to that reading into one
"yes".

**What it breaks:** CLAUDE.md rule 2 (quote verbatim before interpreting; never record a model judgment
as the owner's). **Disposition: should.** Quote "B. No", label the rest as a reading, and split 9(b) into
its own yes/no.

### S3 — The reused helpers will emit a return aggregate the pre-registration forbids — LIKELY
`backtest_e2.py:1293-1306` writes `quintile_spread` (`backtest.py:357`: the top-quintile minus
bottom-quintile **mean realized excess return**) into every per-fold IC row. That is a
percentage-return aggregate (a long-short spread), which `E3_PREREGISTRATION.md:36-37` excludes. The
params entry `money_metrics` (`:304`) does not name it.

**What it breaks:** ruling-B compliance the moment Step 3 reuses the per-fold scoring helper.
**Disposition: should.** Name `quintile_spread` in the params as suppressed (or as owner-ruled), and add a
test.

### S4 — "`scorecard_e2.py` runs unchanged" is false — DEFINITE
`E3_PREREGISTRATION.md:216`.
- `scorecard_e2.BLOCK_LABELS` (`scorecard_e2.py:106-110`) knows only `text_and_numeric` / `numeric_only`
  / `size_only`. `make_calls` raises on `composite_4_family` and `size_only_rank` (`:292-298`).
- `scope_sentence()` (`:222-229`) returns the E2 text-vs-numeric sentence.
- `INFERENCE_SENTENCE` (`:115-119`) cites G3's "§1, decision 15".

`scorecard_e2.py`'s sha is in F6's file index, so editing it changes a G3-run module.

**What it breaks:** Step 3 cannot satisfy §14 as written. An "unchanged" run would print the E2 scope
sentence on an E3 page. **Disposition: should.** State a wrapper or new module, with its own block labels
and the E3 scope sentence.

### S5 — The project-wide Holm-11 column cannot be computed as specified, and departs from its cited source — DEFINITE
`E3_PREREGISTRATION.md:133, 284-288`.
- G3 head 3 has **no** pre-registered aggregate or p-value (F6 §4: "No aggregate was pre-registered").
- Head 1's primary is a TOST equivalence, so it is unclear which p enters.
- Head 2 carries one-sided 0.974 and two-sided 0.0465.
- H1 T1 has five variants.

PRODUCT_PLAN P2 (`PRODUCT_PLAN.md:177-181`), which the doc invokes, seeds the family with **E1's 22
features, H1 T2a / T2b, E2's confirmatory block and the three baseline factors**. The doc's 11 drops
E1's 22 and adds T1 and the three G3 heads without saying so.

**What it breaks:** the disclosure column is not reproducible, and its family is not the plan's.
**Disposition: should.** Define which p per member, or drop the column. Name the deviation from P2's
list.

### S6 — The comparator pool for frame-A ranks is unspecified — LIKELY
`E3_PREREGISTRATION.md:62, 247-254`. The census ranks A against **A-only** rows, as G3's form ablation
did (`backtest_e2.py:2345-2351`). "Inherited (G3 §1)", though, is ambiguous between ranking within A and
ranking on C, then subsetting.

**What it breaks:** every composite value and the scorecard calls. Two faithful implementations would
diverge. **Disposition: should.** Add `"rank_pool": "primary_frame_rows_only"` (or the chosen
alternative) to the params.

### S7 — Outcome map: a wrong-sign significant result is mislabelled, and there is no precedence rule — LIKELY
`E3_PREREGISTRATION.md:203-205`.
- A CI wholly below 0 lands in "CI excludes 0 but point below floor" and is reported as *"not resolvable
  at this design's power"*. It is resolvable; it is the wrong sign.
- A CI that excludes 0 while sitting inside ±Δ satisfies both "bounded null" and "positive" or
  "ambiguous", and no precedence is given. Re-derived: given smallest-rung selection on A and the
  independence floor (SE ≥ 0.0182), that overlap is reachable only in the sliver SE ∈ (0.0241, 0.0243]
  at Δ = 0.08. It is practically empty, but a stopping rule should not rely on that arithmetic.
- There is no gap: every CI maps to at least one branch.

**Disposition: should.** Add a "wrong-sign" row (reported as such, no action) and a one-line precedence.

### S8 — The tripwire repeats the G3 M2 anti-pattern — DEFINITE
`test_census_e3.py:90` asserts `E3_RATIFIED.json` does not exist, so the test goes red at the pin and
invites deleting the pin. That is the failure F6 §5 records as M2, inverted by `builder` for G3.
`:65-68` is a dead loop that checks nothing.

**Disposition: should.** Invert the check (absent, or pinned to the doc sha), and delete the dead loop.

### S9 — The pin procedure repeats the S9 deviation risk — LIKELY
`E3_OWNER_PACKET.md:83-93` promises "It shows you the exact diff first" and lists `--show` and `--pin`
back to back. In G3 the two ran 1.9 s apart inside one command, and the owner never saw the diff (F6 §5
S9). The packet also describes the behaviour of `pin_e3.py`, which does not exist yet, as fact.

**Disposition: should.** Require the `--show` output to be delivered in chat **before** "ratify" is
requested, and phrase `pin_e3.py`'s refusals as "will".

### S10 — The scorecard files are not git-ignored, though the doc says they are — DEFINITE
`E3_PREREGISTRATION.md:226`. `git check-ignore` reports `data/f5/e3_scorecard.md` and `.json` as
**NOT IGNORED**; only the parquet is caught, by `data/f5/**/*.parquet`. G3's `head1_scorecard.md` has its
own `.gitignore:161` line.

**What it breaks:** legal baseline #4. A `git add data/f5/` would commit per-company calls.
**Disposition: should** (a Step-3 build item, but state it as not yet enforced).

### S11 — The MDE anchors understate A's dispersion, and the headline picks the kindest anchor — LIKELY
`E3_CENSUS_2026-11-06.md:133-134` says "The anchors do not depend on the frame". The size and ticker
anchors were measured at frame B's n_dd of 135.8; A's is 92.5. Swapping the 1/(n−1) sampling component
gives a size anchor of **0.165** rather than 0.154, SE 0.0288, MDE **0.081** rather than 0.075. The ladder
pick is unchanged (0.08 / 0.10). §1 (`:60`) quotes the most favourable of the four anchors as "the" MDE.

**Disposition: should.** Correct the sentence, quote the range (§11 already does), and print the
n-adjusted row.

---

## NOTES

- **N1** (DEFINITE, minor). "One row per member company per quarter" is false in 2 folds: 2018Q2, CIK
  109198 (10-K 2018-04-04 + 10-Q 2018-06-01), and 2025Q4, CIK 320187 (10-Qs 2025-10-01 and 2025-12-30).
  Companies per quarter run **80–99**, not 80–100. Affected text: status note `:97-98`, pre-registration
  `:59`, packet `:38`. Dedup is still the identity (minimum same-CIK gap 56 d).
- **N2** (LOOK). PIT trailing ranks on A compare each firm with other firms' values up to 180 d old: the
  median comparator age per row is **34 d**, p90 84 d. For momentum, volatility and B/M this mixes
  market-wide drift into the "cross-sectional" rank. That is not look-ahead, but it is not the
  contemporaneous sort the textbook signs were established on.
- **N3** (LOOK). Construct vs citation (`:95-97`):
  - profitability = revenue-scaled margins, not Fama–French OP/BE;
  - `momentum_126` has no skip month, so it contains the 1-month reversal;
  - negative-book-equity handling of `book_to_market` is unstated.
- **N4** (DEFINITE, minor). "8-K rows repeat the last periodic values" (status `:51-53`). Measured share
  identical per fundamental column: 88.6–93.3%, not all rows.
- **N5** (DEFINITE, minor). `operating_margin` 20.4% for financials is the 18,300-row manifest figure; on
  frame A it is **26.1%** (pre-registration `:89, :161`; status `:79-81`).
- **N6** (DEFINITE, minor). Packet `:53` says "2016–17 fundamentals cover only 58% of rows". That is
  `net_margin` only; `log_total_assets` 100%, equity/assets 99%, B/M 70% (manifest `coverage_by_year`).
- **N7** (LOOK). The binding floor of 0.0466 is H1's event-panel placebo MDE (41 periods). On A the
  analogous pure-noise MDE is 0.051. The floor binds only if SE < 0.0238. `params` names it symbolically
  (`h1_noise_floor_lo`) without the min-over-arms rule.
- **N8** (LOOK). The "zero-information comparators … on these folds" values (`:64`) are frame-B numbers.
  The decision rule never asks the composite to beat them; F6 used exactly that comparison to discount
  `numeric_only`.
- **N9** (DEFINITE, minor). Internal inconsistencies:
  - §6 purge "applies to the fitted secondary of §9" (`:114`), but §9 fits nothing.
  - The census `purge_note` (`census_e3.py:257`) says A's purge figures describe G3's `numeric_only`,
    which was fit on B.
  - `:113` says "Reported beside: a 37-fold arm is **not** run".
  - The status note `:33` says backtest_e2 matches `frozen_module_sha256`; it matches `run.module_sha256`.
- **N10** (LOOK, lazy-elite). Machinery the expected-UNPOWERED, no-fit run does not need:
  - the frame-C arm (the doc's own words: "adds little");
  - a per-sector per-fold IC table at a median of **17–20 rows per sector-fold** (SE ≈ 0.24, pure
    forking-path material);
  - exploratory-family ICs;
  - the Holm-11 column (S5);
  - a `size` entry in `families` that duplicates `spec.zero_information_benchmarks`.
- **N11** (LOOK). The packet is 1,011 words, about two pages against CLAUDE.md's one page. Under the
  low-touch policy, decisions 2–8 and 10 are design choices the main session may decide and log. The
  owner's required touches are "ratify", 9 (an interpretation of their own ruling), and arguably 1.
- **N12** (note). `census_e3.json`'s sha (`7774de1b…`) is recorded in neither the pre-registration nor the
  status note, so it cannot be pinned at ratification. `census_e3.py:518` hard-codes 16,859 despite the
  "constants quoted, never invented" header.
- **N13** (LOOK). The G3 OOF predictions exist for **2,914 periodic dedup rows** of B, i.e. A ∩ B. A
  same-rows fitted comparator on the primary frame is possible at zero cost. §14's "frame-B arm only
  … third column" is ambiguous about whether a whole frame-B scorecard is produced.
- **N14** (note). Sector labels are as of the build, not PIT (G3 §12 SIC drift ≈ 1.6%). This matters only
  for the per-sector table.
- **N15** (note). The test name `test_margin_is_selected_before_any_ic_is_read` cannot be literally true,
  because the SE is a function of the per-fold ICs. Use G3's "before any IC is serialized or printed".

## Contamination verdict (brief item 2)
The primary **is** a different estimand: a level IC of a sign-fixed, no-fit composite, never computed.
The signs are textbook and no per-feature G3 output exists that could have suggested them. `min_families
= 3` was chosen from feature-only coverage, and the fold list is unchanged. Choosing frame A shows no
sign of selection: the form-ablation `numeric_only` reads +0.0250 against B's +0.0251. Two choices were
plausibly influenced by outcome-derived quantities:
- the ladder's extension to 0.10, set after the census showed which rung the outcome-derived anchor SDs
  would select (M3);
- the decision to keep `momentum_126` over 12-1, which the doc itself flags.

§12 is honest in what it says but incomplete (M1).

## Ruling-B verdict (brief item 5)
The owner's words forbid nothing beyond the EODHD subscription; "no money metric" is a main-session
reading. The per-row realized excess return is G3 §14's ratified outcome column, so treating it as an
outcome label is defensible. Under the low-touch policy the main session could decide it, and asking is
harmless, provided the packet stops calling the restriction "your ruling" (S2). The real ruling-B exposure
is `quintile_spread` (S3).
