# H2 — specification pre-registration + honest MDE — COMPLETION REPORT

**Item:** H2 of phase F2.5 (`HARDENING_PROGRESS.md`).
**Executor:** research-statistician (Opus). **Date:** 2026-08-25.
**Status: DONE.** Spec source: `data/reevaluation_2026-08-25/methodology_audit.md`
§(a) defects 1–4 and §(e) E1/E2.

Everything below was **re-derived from frozen artifacts**, never copied from
the audit. Zero network calls. `data/backtest_report.md`,
`data/diagnosis_report.md`, `data/features.parquet`, `data/labels.parquet`
and `data/expansion_recon_2026-08-20.json` were **not modified** — verified
by `git status` after every run. Re-derived numbers live in new dated files
(below). `controls.py` was not touched (H1 owns it);
`HARDENING_PROGRESS.md` was not edited.

---

## 1. What shipped

| # | Deliverable | Where |
|---|---|---|
| 1 | ddof=0 → ddof=1 at the five named sites (each verified before editing) | `diagnose.py:222`; `backtest.py:513, 689, 693, 781` (pre-edit line numbers) |
| 2 | PIT trailing cross-sectional percentile-rank transform as the PRIMARY feature specification; raw levels as the mandatory reported SECONDARY | new `spec.py`; wired into `backtest.py` (`ACTIVE_SPEC`, `build_spec_frames`) and `diagnose.py` |
| 3 | Two standing zero-information benchmark rows in **every** generated report | `spec.zero_information_benchmarks()` → `backtest.standing_section_lines()`, called by both generators |
| 4 | Within-fold bootstrap noise anchor as a standing report section (one per specification) | `spec.bootstrap_noise_anchor()` / `spec.bootstrap_section_lines()` |
| 5 | Honest MDE restatement, appended (never rewritten) as a dated amendment | `EXPANSION_PLAN.md` §2a → "AMENDMENT 2026-08-25 — honest MDE restatement" |
| 6 | Label-embargo census (a fold-structure convention nobody had measured) | `spec.embargo_census()`, standing section |
| 7 | Offline tests for every code change | new `test_spec.py` (48); updated `test_diagnose.py` (+1) |

**New / changed files:**
`/Users/vihanpatil/personal/projects/FinScreen/spec.py` (new),
`/Users/vihanpatil/personal/projects/FinScreen/test_spec.py` (new),
`/Users/vihanpatil/personal/projects/FinScreen/backtest.py`,
`/Users/vihanpatil/personal/projects/FinScreen/diagnose.py`,
`/Users/vihanpatil/personal/projects/FinScreen/test_diagnose.py`,
`/Users/vihanpatil/personal/projects/FinScreen/EXPANSION_PLAN.md`.

**New dated artifacts (re-derivations, not gate files):**
`/Users/vihanpatil/personal/projects/FinScreen/data/hardening/backtest_report_2026-08-25_H2.md`,
`/Users/vihanpatil/personal/projects/FinScreen/data/hardening/diagnosis_report_2026-08-25_H2.md`.

**Re-run command (both accept `--out`, so the frozen reports cannot be
clobbered by accident):**

```
python3 backtest.py  --out data/hardening/backtest_report_2026-08-25_H2.md
python3 diagnose.py  --out data/hardening/diagnosis_report_2026-08-25_H2.md
python3 -m pytest test_spec.py test_diagnose.py test_phase_c_leakage.py -q
```

---

## 2. The pre-registered specification (this is the artifact G3 ratifies)

`spec.pit_trailing_rank_frame(df, feature_cols, window_days=180,
min_comparators=2, include_same_day=True)`.

For row *i* at `filing_date` *t*, each feature is replaced by its percentile
within a comparison set of one observation per ticker — that ticker's LAST
observation with `filing_date ∈ [t−180d, t]` — with the subject row always
representing its own ticker. Percentile = (#strictly below + 0.5·#ties) /
#non-null comparators. NaN in → NaN out (missingness is preserved, never
imputed). Fewer than 2 non-null comparators → NaN. No row with
`filing_date > t` can enter any comparison set (pinned by
`test_spec.py::test_future_rows_cannot_change_a_past_percentile`).

- **PRIMARY** `pit_trailing_rank`; **SECONDARY (mandatory, always reported)**
  `raw_levels`. Both are reported on every run, as a pair; neither may be
  selected after the fact.
- **Named sensitivity variant:** `include_same_day=False` (the conservative
  reading under the unresolved post-close acceptance issue, audit C1).
- **Rationale is a-priori, not results-driven:** raw levels encode company
  identity almost exactly (ICC 0.987 `log_total_assets`), so both arms of
  the text-vs-numeric comparison ride the same company-persistence term.
- **Contamination warning, inherited by every E1 number under this spec:**
  these were computed *after* the specification sensitivity was observed.
  They are diagnostic, never confirmatory. The pre-registration binds E2,
  whose data does not exist yet.
- **Inherited, not introduced:** the transform uses `filing_date` day
  granularity and therefore carries audit item C1 (45% of filings accepted
  after 16:00 ET carrying that day's `filing_date`), queued for G3.

---

## 3. Re-derived numbers (all from `data/hardening/backtest_report_2026-08-25_H2.md`)

**Replication check.** The `raw_levels` arm reproduces E1's published
per-fold dedup deltas **exactly** (−0.1275, −0.0078, −0.0399, 0.0183,
−0.0004, 0.0992; mean −0.0097): the harness is byte-identical, so every
disagreement below is about method, not arithmetic.

### 3.1 Zero-information benchmarks (standing rows)

| benchmark | cross-fold mean dedup IC | sample std (ddof=1) | positive folds |
|---|---|---|---|
| `size_only_rank` (rank by `log_total_assets`) | **0.2240** | 0.2871 | 5/6 |
| `ticker_training_mean_rank` (ticker's training-window mean excess return) | **0.1868** | 0.3111 | 4/6 |
| shipped numeric-only (raw levels) | 0.0972 | — | — |
| shipped text+numeric (raw levels) | 0.0875 | — | — |

Independently reproduces the audit's 0.224 / 0.187 / 0.097 / 0.088. **Both
zero-information predictors beat both fitted models on E1's own folds.**
Note the std column: at 6 folds neither benchmark is distinguishable from
zero either — the benchmarks are a *scale* for reading ICs, not a claim that
size predicts returns.

### 3.2 Bootstrap noise anchor + the floor

| specification | cross-fold sample std (ddof=1) | 95% chi² CI | bootstrap SD (mean / RMS) | implied floor | chi² p |
|---|---|---|---|---|---|
| `raw_levels` | 0.0742 | [0.0463, 0.1819] | 0.1046 / 0.1154 | **0.0000** | p(spread<sampling)=0.160 |
| `pit_trailing_rank` | 0.1549 | [0.0967, 0.3800] | 0.1149 / 0.1190 | **0.0992** | p(spread>sampling)=0.132 |

Published anchor was 0.0677 (ddof=0). 4,000 resamples/fold,
`default_rng(seed_base 0 + fold index)`, fitted predictions held fixed,
only dedup test rows resampled; 0 degenerate resamples in any fold.

### 3.3 Label-embargo census (previously unmeasured)

**313 of 2,425 training labels (12.9%)** resolve on or after their fold's
test quarter begins — 52–53 per fold, i.e. the entire final training
quarter. Not feature look-ahead (`assert_no_fold_leakage()` is right to
pass), but there is no embargo/purge and the convention had never been
stated. Whether to embargo is a G3 decision; H2 only measures it.

### 3.4 Implementation-variant sweep (E1, dedup, same folds/dedup/XGB params)

| # | variant | mean IC numeric | mean IC full | **mean delta** | std (ddof=1) | pos folds |
|---|---|---|---|---|---|---|
| — | raw levels (E1 as shipped) | 0.0972 | 0.0875 | −0.0097 | 0.0742 | 2/6 |
| **A** | **PRE-REGISTERED PRIMARY** — last-per-ticker, subject included, same-day peers included, 581-row frame | 0.1148 | 0.1056 | **−0.0093** | 0.1549 | 2/6 |
| B | as A but the subject's ticker dropped from its own comparison set | 0.1154 | 0.1505 | +0.0351 | 0.1086 | 4/6 |
| C | every row in the window (no last-per-ticker collapse) | 0.0590 | 0.0418 | −0.0172 | 0.0496 | 2/6 |
| D | as A but ranked against the 630-row artifact, then subset to 581 | 0.0621 | 0.0909 | +0.0288 | 0.1220 | 4/6 |
| F | as A but applied to the 10 numeric features only | 0.1148 | 0.1007 | −0.0141 | 0.0735 | 3/6 |
| G | as B but ranked against the 630-row artifact | 0.0552 | 0.0549 | −0.0003 | 0.1519 | 3/6 |
| **H** | **NAMED SENSITIVITY ARM** — `include_same_day=False` (no same-day rows at all; subject's own prior filing still counts) | 0.0847 | 0.1268 | **+0.0422** | 0.1173 | 3/6 |
| — | audit's reported figure (`methodology_audit.md` §(e) E1) | 0.0783 | 0.1250 | +0.0467 | 0.1668 | 4/6 |

Span across the seven measured variants: **[−0.0172, +0.0422] = 0.059**
in the headline estimand and **[0.0496, 0.1549] = 3.1×** in the noise
anchor. **The audit's +0.0467 could not be reproduced exactly** from its
stated recipe (Appendix B); H is the closest arm. Only A and H are reachable
from `spec.py`; the rest were exploratory diagnostics and their recipes are
stated above so they are re-derivable.

---

## 4. Honest MDE restatement (the numbers the amendment carries)

E2 core stratum = 100 companies → n_dd ≈ 158 at E1's measured 1.58 dedup
rows/company/fold; 26 test folds; MDE = 2.8 × SE (two-sided 5%, 80% power);
ρ_f = 0.3 applied as the finite-k AR(1) inflation 1 + 2Σ(1−l/k)ρ^l = 1.810
(SE ×1.345).

| specification | branch | SE(mean δ) | **MDE** | 95% null bound |
|---|---|---|---|---|
| `raw_levels` | floor-free, ρ_f=0 | 0.0103 | **0.029** | ±0.020 |
| `raw_levels` | floor-free, ρ_f=0.3 | 0.0138 | **0.039** | ±0.027 |
| **`pit_trailing_rank`** | floor-free, ρ_f=0 | 0.0113 | **0.032** | ±0.022 |
| **`pit_trailing_rank`** | floor-free, ρ_f=0.3 | 0.0152 | **0.043** | ±0.030 |
| **`pit_trailing_rank`** | implied floor, ρ_f=0 | 0.0225 | **0.063** | ±0.044 |
| **`pit_trailing_rank`** | implied floor, ρ_f=0.3 | 0.0303 | **0.085** | ±0.059 |

True-construct (noise-free-label) units at labeler reliability λ ≈ 0.8:
**0.036 → 0.107** (λ ≈ 0.6–0.7 where sections are short would be worse).

**Published `EXPANSION_PLAN.md` §2a: 0.019–0.037, null bound ±0.013–0.027.
Honest: 0.029–0.085 measured / 0.036–0.107 true-construct, null bound
±0.020 → ±0.059.**

The brief's target figures (~0.029 / ~0.039 / ~0.036–0.049) are reproduced
**exactly**, but they belong to `raw_levels` — now the SECONDARY
specification. Under the PRIMARY spec that E2 will actually run, the same
three figures are **0.032 / 0.043 / 0.039–0.053**, and the floor branch
pushes the pessimistic endpoint to **0.085 / 0.107**.

Minor items: at k=26 a t-correction raises the multiplier 2.802 → 2.916
(+4%), folded into none of the above. 41 member-window quarters exist, so a
shorter burn-in buys up to ~35 folds (×0.86 on every MDE); pooling the
extension stratum (136 vs 100) multiplies the **sampling** component by 0.86
and the floor component by 1.00.

### Corrected scope of the bounded null

Published: *"no text-vs-numeric IC improvement of economically relevant size
(|δ| ≳ 0.03) exists in this universe."* Corrected:

> "No text-vs-numeric IC improvement of economically relevant size is
> **detectable in this universe through this labeling schema, these 22
> features, this labeler, and this feature specification.**"

### Named equivalence procedure

TOST at α = 0.05 on the cross-fold mean dedup IC delta against a margin ±Δ
fixed at G3; equivalently, declare equivalence iff the **90% CI** (mean ±
1.645·SE) lies entirely inside ±Δ. Report the interval always, including
when equivalence fails. SE from a **block bootstrap over folds** (block
length from the *measured* lag-1 autocorrelation, measurable for the first
time at 26 folds) or Newey–West — never std/√k.

Power requirement, stated up front: **SE ≤ Δ/(z₀.₉₅+z₀.₈₀) = Δ/2.487**;
at Δ = 0.03 that is **SE ≤ 0.0121**. E2's achievable SE spans
0.0103–0.0303, so **Δ = 0.03 is powered only in the floor-free,
independent-folds corner**; Δ = 0.05 (SE ≤ 0.0201) is met in every
floor-free branch. **If the rank-spec floor is real, no company count helps:
a Δ = 0.03 TOST would need k ≥ 68 folds (ρ_f=0) or k ≥ 125 (ρ_f=0.3) — 17
to 31 years of quarters.** Choosing Δ after seeing the realized SE is a
post-hoc design choice and is prohibited.

---

## 5. Three findings that go beyond the audit (for G3 / the owner)

1. **The audit's "defect 4 is good news" does not survive the specification
   change.** Implied floor = 0.0000 under raw levels but 0.0992 under the
   pre-registered primary spec, on the same folds. Chi-square p = 0.16 and
   0.13 respectively: **neither direction is resolved at 6 folds.** Recon
   caveat (1) — "more companies may buy nothing" — therefore still stands,
   and the E2 bracket must carry the floor endpoint. Both generators now
   print both tails next to the point estimate so the floor can never again
   be quoted as settled.
2. **Implementation sensitivity (0.059) dominates specification sensitivity
   (0.0004).** Two pinned implementations differ by 0.0004, which reads as
   reassurance and is not: seven look-ahead-free implementations of the same
   *named* transform span 0.059. G3 must pre-register **a function and its
   arguments**, not a transform's name. The generated report says this
   explicitly next to the small number.
3. **No embargo/purge, 12.9% of training labels.** Previously unstated. Not
   fatal (the excess-return target differences out the market-wide component
   of the overlap), but it is a fold-structure convention and belongs in the
   G3 conventions list with its measured population.

Plus the standing one: **both zero-information predictors beat both fitted
models** (0.224 / 0.187 vs 0.097 / 0.088). Every IC in every future report
is now printed beside them.

---

## 6. Tests

| suite | count | note |
|---|---|---|
| `test_spec.py` (new) | **48** | offline; transform (incl. 3 look-ahead pins), benchmarks, bootstrap (pinned against `scipy.stats.spearmanr` incl. ties), chi² CI (reproduces the audit's [0.0463, 0.1820] at k=6), embargo census, report sections, ddof pins |
| `test_diagnose.py` | **22** (was 21; +1 new) | smoke test now exercises the standing path; new test asserts a report generated WITHOUT the standing inputs prints "NOT COMPUTED" rather than silently omitting the sections |
| `test_phase_c_leakage.py` | **35** | unchanged, all pass |
| **total** | **105 passed** | `python3 -m pytest test_spec.py test_diagnose.py test_phase_c_leakage.py -q` → 105 passed in ~69 s |

`test_pit.py` (5) also re-run clean. Two source-level regression pins:
`std(ddof=0)` can no longer appear in either generator, and both generators
must render every standing section (or an explicit NOT COMPUTED notice).

---

## 7. Open items owned by others

- **H5 (`data/hardening/status/H5_stopping_rule.md`) quotes
  "~0.029 / ~0.039 / ~0.036–0.049" as the honest MDE.** Those are correct
  for `raw_levels`. Under the now-primary spec they are **0.032 / 0.043 /
  0.039–0.053**, with a floor branch at 0.063–0.085. The stopping-rule
  draft needs reconciling before the owner ratifies it, and its Δ must be
  chosen knowing that Δ = 0.03 is powered only in the best corner.
- **Stale bracket still quoted in** `HANDOFF.md:690`, `ROADMAP.md:305`,
  `PRIOR_WORK.md:152`, `.claude/agents/research-statistician.md:22`. Not
  edited here (H2's brief scoped the restatement to `EXPANSION_PLAN.md`
  §2a); each needs a pointer to the amendment.
- **G3 conventions list** should carry: the pinned transform + its
  arguments; the embargo decision (12.9% measured); the equivalence margin
  Δ and the SE estimator; the same-day/post-close (C1) rule, which is the
  same decision as `include_same_day`.
- **E2 must measure, not assume:** the lag-1 autocorrelation of fold deltas
  and the floor — both identifiable at 26 folds, neither at 6.
