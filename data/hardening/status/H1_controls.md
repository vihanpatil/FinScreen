# H1 — POSITIVE CONTROLS (T1 + T2). Completion report.

**Phase F2.5 hardening, item H1** (`HARDENING_PROGRESS.md`). Written
2026-08-25 by the quant-modeler session that built `controls.py` and
`test_controls.py`. Every number below was produced by the single run
recorded in `data/hardening/controls_results.json`; none is hand-carried
from any earlier corpus or report.

**Charter position, restated because this file contains return numbers.**
Nothing here places, queues, recommends or evaluates a trade. There is no
expected-return figure and no "beats the market" framing anywhere. The one
table in return units (§4c) describes what an already-realized announcement
session did, sorted by information that was public at that same moment; it
is a description of an event, not a forecast and not achievable by anyone.

**E1/E2 comparability.** No number in this file is comparable to any number
in `data/backtest_report.md` or `data/diagnosis_report.md`. Those use E1's
25-name self-inclusive benchmark; this file uses E2's proposed
membership-dated, self-excluding benchmark (`EXPANSION_PLAN.md` §3.3), which
is **not yet ratified** — gate G3 owns it. If G3 ratifies a different
benchmark these controls must be re-run under it.

---

## 1. Verdicts, up front

| control | what it asks | pre-declared verdict | headline (CORE stratum, dedup basis) |
|---|---|---|---|
| **T1** | does the announcement-window return track the earnings surprise? | **FAIL at the pre-declared bar** — but positive, significant, and diagnosed | mean per-quarter Spearman IC **+0.0643**, SE 0.0205, **t = +3.13**, 29/41 quarters positive (70.7%), block-bootstrap 95% CI **[+0.0263, +0.1046]**, n = 3,466 |
| **T2a** | does PEAD appear at the harness's own 63-session forward window and benchmark? | **AMBIGUOUS** (pre-declared as the modal expectation) | mean IC **+0.0279**, SE 0.0254, t = +1.10, 22/40 positive, CI **[−0.0204, +0.0764]**, n = 3,368 |
| **T2b** | does 12-1 momentum? | **AMBIGUOUS** | mean IC **+0.0287**, SE 0.0393, t = +0.73, 23/40 positive, CI **[−0.0481, +0.1034]**, n = 3,879 |
| **T0** | does a zero-information placebo produce nothing? | **PASS** (both arms) | announcement −0.0044 (t = −0.26); forward +0.0010 (t = +0.06) |

**Implausibility tripwire: none fired.** No control produced |mean IC| > 0.15.

**The one-sentence read.** T1's *plumbing* — the PIT / membership / price /
session-alignment stack — is empirically verified to be correct (§4b), and
the surprise→announcement-return relationship is unambiguously present in
the right direction, but the pre-declared "strongly positive" bar was set to
the literature's effect size rather than to what a GAAP-XBRL time-series
surprise proxy can deliver in this universe, and it was missed.

---

## 2. Pre-declaration, and an honest note about it

Every threshold, window and pass/fail rule lives in `SPEC` inside
`controls.py` and was written before the module was executed. `SPEC` is
hashed into the results JSON:

```
spec_sha256  5e38839836c250c349b33192cc53e7b52258eab2b2488ac5d48449caa2199f18
```

**Full disclosure on that hash.** An earlier hash
(`80546840ab27164a…`) was computed from the same SPEC before the first
execution attempt. That attempt crashed on an out-of-bounds `9999-12-31`
membership sentinel before producing any statistic; fixing it changed one
descriptive SPEC string and therefore the hash. **No control result existed
at either point.** A hash is provenance, not proof of ordering; the honest
statement is that the author had seen no T1, T2 or T0 outcome number when
the thresholds were chosen.

**Why this cannot pre-empt gate G3.** No model is fitted anywhere in this
module. Every signal (SUE, momentum, placebo) is a fixed formula with zero
estimated parameters, so there is no training set, no test set, and no
train/test split to choose. The calendar-quarter grouping exists only to
report per-period spreads, which is a standing requirement, and is **not a
fold structure and not a G3 proposal**.

**Post-hoc material is fenced.** §4b–§4d were written *after* T1 came in
under its bar, to identify which component fell short. They are labelled
post-hoc in the code and in the JSON, they do not enter `verdicts`, and any
spec change they motivate must be pre-registered at G3 before a confirmatory
run uses it.

---

## 3. Population, conventions, and what was dropped

Reproduced exactly from the frozen artifacts; matches the lens report's
measured 5,552 (`data/reevaluation_2026-08-25/alternatives.md` §1).

| quantity | value |
|---|---|
| item-2.02 8-Ks inside their own membership spell | **5,903** (242 CIKs) |
| …of which the CIK has price data → the control panel | **5,552** (211 CIKs) |
| dropped: member CIKs with no price series at all | **351 events / 31 CIKs** |
| events with a buildable SUE | **4,854** (87.4%) |
| events with a 1-session announcement excess return | 5,535 |
| events with a complete 63-session forward excess return | 5,394 |
| events with 12-1 momentum history | 5,535 |
| near-duplicate events removed by the shipped dedup rule (gap 5 d, form-aware) | 64 of 5,552 |
| reporting quarters (T1 / T2) | **41 (2016Q3–2026Q3) / 40 (2016Q3–2026Q2)**, median ~87 core events per quarter |
| benchmark members used per event | median **130**, range 113–136 |
| member-cells excluded from a benchmark for missing price coverage | 2,097 (announcement) / 2,099 (forward) — ~0.4 per event |

### PIT conventions actually implemented

* **`filing_date`, never `report_date`.** `report_date` is not read anywhere
  in `controls.py`. `period_end` is used only as a fiscal-calendar label to
  line quarter *q* up with quarter *q−4*; availability is governed solely by
  the `filed` column.
* **Post-close acceptance, handled and then verified.**
  `data/F2_INGESTION_REPORT.md` §3.3 measured 45% of the 45,545-filing corpus
  accepted after 16:00 ET while carrying that day's `filing_date`. On this
  earnings-8-K subset the share is **39.2% (2,178 of 5,552)**. The rule
  applied is:
  `info_date = max(filing_date, acceptance_date_ET)`;
  `post_close = acceptance hour (ET) ≥ 16`;
  `news_session` = first session **≥** `info_date` if pre-close, **>**
  `info_date` if post-close; `pre_session` = the session before it. The
  forward (T2) window opens at `news_session + 1` — i.e. the entry close
  always post-dates the session that impounded the news, which for pre-close
  filings equals the shipped `features.py` rule and for post-close filings is
  one session **later** than it. §4b shows the data agrees with this rule.
* **The Salesforce anomaly is covered by construction.** `max()` means a
  filing whose `filing_date` precedes its acceptance (two such filings,
  by 344 and 633 days) is dated from acceptance. Zero events in this panel
  had acceptance after `filing_date` at the date level, so the rule bites
  nowhere here — but it is tested (`test_acceptance_after_filing_date_wins_the_salesforce_case`).
* **The surprise numerator is contemporaneous; every scaling input is
  strictly prior.** SUE = (EPS_q − EPS_{q−4}) / sd(seasonal differences over
  the trailing 8 quarters, ddof=1, min 6). EPS_q is the as-originally-reported
  figure (earliest `filed` row for that (cik, period_end)) — never a
  restatement — and was public in the release at `info_date`. EPS_{q−4} and
  every quarter entering the scaler are **required to have been filed
  strictly before the event date**; this is unit-tested.
* **Benchmark members are membership-dated, self-excluded, and never
  imputed.** Prices are forward-filled only inside each CIK's own
  [first, last] observation window; outside it they are NaN. This
  deliberately differs from `features.py::_asof_price()`, which returns the
  last known price for any later date and would contribute a fabricated 0%
  return for a name whose history has ended (the EA case,
  `methodology_audit.md` C5). Unit-tested.
* **No shuffling anywhere.** Every panel is time-ordered by the public date.
* **Hard leakage assertions run on every execution** (`assert_no_lookahead`):
  news session never precedes the info date; the post-close correction is
  actually applied; the forward window never opens on or before the news
  session; no fiscal quarter ending on or after the event date is used.

### Known biases carried into these numbers, not netted out

* Prices are split-adjusted but **not dividend-adjusted**
  (`data/PRICES_NOTES.md` §1). This is near-immaterial for T1's 1-session
  window and is a real cross-sectional-yield bias in T2's 63-session window:
  high-yield names show a systematically lower price return than the
  equal-weighted benchmark.
* The price source is Yahoo's keyless chart endpoint, whose robots.txt
  disallows automated access and which has no published terms for this use —
  the standing owner-attention item (`HANDOFF.md` §2a).
* Delisted-price censoring is present but small in this panel: 351 events
  lost entirely, ~0.4 benchmark member-cells lost per event.

---

## 4. T1 — contemporaneous announcement response

### 4a. The pre-declared arm

Pre-declared bar: **mean IC > 0 AND t ≥ 4.0 AND ≥ 75% of quarters positive.**

| arm (CORE stratum) | basis | mean IC | sd (ddof=1) | SE | t | positive quarters | bootstrap 95% CI | n |
|---|---|---|---|---|---|---|---|---|
| **primary — 1-session, benchmark-adjusted** | dedup | **+0.0643** | 0.1315 | 0.0205 | **+3.13** | **29/41 (70.7%)** | [+0.0263, +0.1046] | 3,466 |
| same | raw | +0.0644 | — | 0.0199 | +3.25 | 29/41 | — | 3,517 |
| secondary — 2-session window | dedup | +0.0764 | 0.1269 | 0.0198 | +3.85 | 29/41 | [+0.0392, +0.1157] | 3,466 |
| secondary — 1-session, **raw return** (no benchmark) | dedup | +0.0604 | 0.1280 | 0.0200 | +3.02 | 27/41 | [+0.0227, +0.1000] | 3,466 |
| pooled core+extension | dedup | +0.0559 | 0.1154 | 0.0180 | +3.10 | 29/41 | [+0.0221, +0.0911] | 4,777 |
| extension stratum alone | dedup | +0.0197 | 0.2093 | 0.0327 | +0.60 | 24/41 | [−0.0427, +0.0841] | 1,311 |

Per-quarter spread, primary arm: min **−0.231** (2018Q3), max **+0.367**
(2024Q1); no single quarter drives the mean; the full 41-quarter series is in
the results JSON.

**Verdict: FAIL at the bar** — t = 3.13 < 4.0 and 70.7% < 75%. The sign,
the significance and the bootstrap interval (which excludes zero) are all as
expected; the *magnitude* is not.

**Extension-stratum note.** The extension arm is a secondary by the
2026-08-21 amendment and is not promoted here. Its IC is indistinguishable
from zero with roughly 1.6× the per-quarter dispersion of core — consistent
with a thinner, more heterogeneous set of filers, and a data point the owner
may want beside gate G2's promotion decision.

### 4b. POST-HOC DIAGNOSTIC — the plumbing itself is verified correct

*(Written after §4a's result. Diagnostic only; does not change the verdict.)*

Two checks isolate "is the date/join/PIT stack right?" from "is the surprise
proxy good?".

**D1 — event-date alignment, independent of any surprise proxy.** Median
absolute session return divided by that CIK's own median absolute return over
sessions t−30…t−10 (n = 5,535 events):

| session | all events | post-close events | pre-close events |
|---|---|---|---|
| pre_session | 1.07× | 1.14× | 1.03× |
| **news_session** | **2.82×** | **3.02×** | **2.67×** |
| news_session + 1 | 1.31× | 1.19× | 1.39× |

The volatility spike is large and **sharply localized to exactly the session
the code calls the announcement session**, in both the post-close and
pre-close subsets. A misaligned join, a wrong membership filter, an off-by-one
calendar, or a broken post-close rule could not produce this.

**D2 — the post-close convention, measured rather than assumed.** For each
event, the return of session *D* (= the first session ≥ `info_date`, i.e.
what a harness ignoring acceptance time would use) and of session *D+1*,
correlated with SUE:

| subset | SUE vs session *D* | SUE vs session *D+1* |
|---|---|---|
| post-close events (n = 1,539) | **−0.019** (p = 0.46) | **+0.073** (p = 0.004) |
| pre-close events (n = 1,978) | **+0.058** (p = 0.010) | +0.033 (p = 0.15) |

The surprise tracks *D+1* for post-close filings and *D* for pre-close
filings, exactly as the correction predicts. **This is direct empirical
confirmation of the F2 post-close finding and of the fix for it**, and it
should go into the G3 pre-registration as evidence, not as an assumption.
(Pooled p-values here are unadjusted for event clustering and are
anti-conservative; the direction and the reversal between subsets are the
content, not the p-values.)

### 4c. POST-HOC DIAGNOSTIC — effect size in return units

*(Descriptive. Contemporaneous, already realized, in-sample. Not a forecast,
not an expected return, not achievable. No equivalent table is produced for
T2's forward window, deliberately.)*

Within-quarter SUE quintiles, core stratum, 1-session announcement excess
response:

| SUE quintile | mean | median | n |
|---|---|---|---|
| 0 (most negative surprise) | **−0.94%** | −0.77% | 710 |
| 1 | −0.04% | −0.08% | 684 |
| 2 | +0.32% | +0.28% | 684 |
| 3 | +0.00% | +0.06% | 684 |
| 4 (most positive surprise) | +0.06% | +0.25% | 704 |
| **top − bottom** | **+1.00 pp** | | |

The response is **asymmetric**: the bottom quintile is cleanly and strongly
negative while the top four are flat and non-monotone. That pattern is what a
GAAP-XBRL time-series surprise proxy would be expected to produce — a large
negative seasonal difference usually *is* a bad print, whereas a positive
seasonal difference is a poor proxy for beating a consensus nobody in this
pipeline has.

### 4d. POST-HOC DIAGNOSTIC — one real construction defect in the SPEC

`SPEC` picks the announced quarter as the largest `period_end` in
[event − 120 d, event − 5 d]. Many filers never tag a 90-day **Q4** fact (they
tag the fiscal year only), so a Q4 earnings 8-K silently matches the **stale
Q3** surprise, which was already public months earlier.

* Affected: **393 of 4,854 SUE events = 8.1%.**
* Those events' pooled announcement IC is +0.020 (p = 0.73) — i.e. noise, as
  expected of a surprise the market absorbed a quarter ago.
* Removing them: T1 core mean IC **+0.0768**, SE 0.0182, **t = +4.22**,
  **31/41 (75.6%) positive**, bootstrap CI [+0.0417, +0.1124], n = 3,158.

**Both of the pre-declared T1 criteria would be met with those events
removed.** This is stated for completeness and for G3; it is **not** the T1
verdict. The verdict is the one computed from the pre-declared arm. Matching
an announcement to a quarter that was already public months earlier is wrong
under any reading — so this is a defect to fix and pre-register, not a knob
that was tuned — but it was found by looking at the data, and treating a
post-hoc repair as the confirmatory result is exactly the failure mode the
pre-registration discipline exists to prevent.

---

## 5. T2 — known numeric anomalies at the harness configuration

Configuration: the harness's own 63-trading-session forward window, E2's
proposed membership-dated self-excluding benchmark, the shipped dedup rule
(imported read-only from `backtest.py`), per-quarter Spearman IC with
cross-quarter mean, ddof=1 SE and a whole-quarter block bootstrap.

### 5a. T2a — post-earnings-announcement drift (SUE → forward 63-session excess return)

| arm | basis | mean IC | sd | SE | t | positive | bootstrap 95% CI | n |
|---|---|---|---|---|---|---|---|---|
| **core (pre-declared primary)** | dedup | **+0.0279** | 0.1604 | 0.0254 | **+1.10** | 22/40 | [−0.0204, +0.0764] | 3,368 |
| core | raw | +0.0243 | — | 0.0250 | +0.97 | 22/40 | — | 3,419 |
| core, skip-one-session entry | dedup | +0.0267 | 0.1619 | 0.0256 | +1.04 | 23/40 | [−0.0224, +0.0762] | 3,365 |
| core, strict-PIT subsample¹ | dedup | +0.0331 | 0.2171 | 0.0343 | +0.97 | 23/40 | [−0.0333, +0.0988] | 1,199 |
| pooled core+extension | dedup | +0.0183 | 0.1375 | 0.0217 | +0.84 | 21/40 | [−0.0235, +0.0607] | 4,645 |
| core, stale-quarter matches removed (post-hoc) | dedup | +0.0437 | — | 0.0277 | +1.58 | 25/40 | [−0.0102, +0.0971] | 3,075 |

¹ events whose announced-quarter EPS was itself first filed on or before the
event date (n = 1,978 of 4,854 SUE events) — the subsample where the XBRL
record cannot differ from what was public at the announcement.

**Verdict: AMBIGUOUS.** Point estimate positive in every arm, in the
direction the literature predicts, and not distinguishable from zero.

### 5b. T2b — 12-1 momentum (→ same forward window and target)

| arm | basis | mean IC | sd | SE | t | positive | bootstrap 95% CI | n |
|---|---|---|---|---|---|---|---|---|
| **core (pre-declared primary)** | dedup | **+0.0287** | 0.2484 | 0.0393 | **+0.73** | 23/40 | [−0.0481, +0.1034] | 3,879 |
| core | raw | +0.0259 | — | 0.0393 | +0.66 | 22/40 | — | 3,933 |
| pooled | dedup | +0.0248 | 0.2358 | 0.0373 | +0.66 | 23/40 | [−0.0481, +0.0962] | 5,330 |

**Verdict: AMBIGUOUS.** Per-quarter dispersion is enormous (sd 0.248, range
−0.635 to +0.641) — which is itself the documented behaviour of momentum, and
this sample spans both the 2020 and the 2022 momentum reversals.

### 5c. What T2's ambiguity does and does not mean — read this before quoting it

The honest constraint is **power, not sign**. At the measured per-quarter
dispersion over 40 quarters, the minimum detectable |IC| at two-sided 5% /
80% power (2.8 × SE) is:

| control | SE | **MDE** |
|---|---|---|
| T2a PEAD, core | 0.0254 | **0.071** |
| T2b momentum, core | 0.0393 | **0.110** |
| T1 announcement, core | 0.0205 | 0.058 |
| T0 placebo (noise floor) | 0.0166–0.0174 | 0.047–0.049 |

Documented PEAD and momentum in post-2000 large caps are widely reported as
decayed, and are very plausibly **below** these detection limits. So T2's
ambiguity is largely a statement about what 40 quarters of ~87 large-cap
events can resolve — it is **weak evidence about the configuration in either
direction**, and it must never be quoted as "the harness cannot find known
effects."

---

## 6. T0 — the zero-information placebo

A deterministic uniform signal from `sha256("H1-placebo|<cik>|<date>")`,
independent of every price and every fundamental by construction, pushed
through the identical panel, target, grouping, dedup and IC machinery.

| arm | mean IC | SE | t | positive quarters | bootstrap 95% CI |
|---|---|---|---|---|---|
| announcement window | **−0.0044** | 0.0166 | −0.26 | 17/41 | [−0.0360, +0.0276] |
| forward 63-session window | **+0.0010** | 0.0174 | +0.06 | 21/40 | [−0.0322, +0.0349] |

**Verdict: PASS, both arms.** The machinery does not manufacture correlation.
It also fixes the noise floor: **an |IC| of roughly 0.047–0.049 is what this
panel cannot distinguish from nothing.**

---

## 7. What a failure would have meant — stated explicitly

* **T1 catastrophic failure (IC ≈ 0 *and* no announcement-session volatility
  spike).** The PIT / join / date-alignment / benchmark stack would be
  broken, every E1 and E2 IC ever computed would be uninterpretable, and F3
  must not start until it is fixed. **This did not happen.** D1's 2.82×
  localized volatility spike and D2's clean post-close reversal rule it out
  affirmatively, not by absence of evidence.
* **T1 miss-at-the-bar with the plumbing intact (what did happen).** The
  measurement instrument works; the *surprise proxy* is weak. A
  seasonal-random-walk SUE built from GAAP XBRL EPS is a poor stand-in for
  the market's expectation in exactly this universe — large, heavily
  covered firms where analyst consensus, not a time-series model, is the
  benchmark expectation, and where GAAP EPS carries one-off items the release
  presents as adjusted. The consequence for E2 is a **calibration** one: it
  tells us the size of relationship this panel can actually surface, and
  ~0.06–0.08 for one of the strongest known effects in accounting is the
  right yardstick against which to read any text delta.
* **T1 significantly *negative*.** A sign error in the target, the benchmark,
  or the session alignment. Ruled out.
* **T2 significantly negative (|t| ≥ 2 wrong way).** A configuration defect —
  sign, window, or benchmark. Ruled out; both point estimates are positive.
* **T2 exactly zero.** Would have been a soft warning about the
  configuration, explicitly pre-declared as *not* proof of a bug because
  both anomalies are decayed in large caps. Both came in positive but
  under-powered, which is the pre-declared modal expectation.
* **T0 showing signal.** Every other number in this file would be void.
  Ruled out.
* **Any control at |IC| > 0.15.** Pre-declared as a suspected evaluation bug
  to investigate before reporting. None fired.

---

## 8. Findings the G3 pre-registration should absorb

1. **The post-close acceptance rule is empirically confirmed, not merely
   prudent** (§4b, D2). Pre-register `info_date = max(filing_date,
   acceptance_date_ET)` with a 16:00 ET cutoff, and pin it with a test rather
   than a convention — F2 already asked for this; H1 now supplies the
   evidence.
2. **Benchmark members must not be price-forward-filled past their coverage
   window.** `features.py::_asof_price()`'s behaviour would inject
   fabricated 0% returns for ended series. Pre-register the coverage-window
   rule and report the count of excluded member-cells (here: ~0.4 per event).
3. **The announcement-session volatility ratio (D1) is a cheap standing
   harness assertion.** It requires no labels, no model and no fold
   structure, and it would catch a date-alignment regression instantly.
   Worth adopting as a permanent tripwire.
4. **Quote the noise floor beside every IC.** This panel's zero-information
   floor is |IC| ≈ 0.047–0.049, and T2's MDEs are 0.071 (PEAD) and 0.110
   (momentum). This is the same discipline H2 is adding as standing
   zero-information benchmark rows, measured here on E2 data.
5. **If SUE is ever used again** (e.g. as an E2 numeric feature or in the F5
   volatility head), pre-register the Q4 fix: require the matched
   `period_end` to be within ~100 days of the event, or resolve Q4 from the
   annual fact minus the first three quarters. 8.1% of events are currently
   mismatched.
6. **The extension stratum behaves visibly worse than core even on a control
   with no labels in it** (+0.020, t = 0.60, dispersion 1.6× core). That is
   relevant context for gate G2's promotion decision, and it is not a label-
   quality effect.

---

## 9. Limitations of these controls

* **T2's event grid is the earnings-8-K grid, not E2's eventual full filing
  grid** (which will also carry 10-Qs and 10-Ks). Momentum in particular is
  usually measured on a calendar rebalance, not an announcement grid. The
  windows, benchmark, dedup and IC machinery are the harness's; the
  observation grid is a documented subset of it.
* **T2 inherits the missing dividend adjustment** over 63 sessions
  (cross-sectional yield bias). T1 essentially does not.
* **The surprise is a time-series SUE, not an analyst-consensus surprise.**
  No analyst data exists in this project and none may be acquired. This is
  the single largest reason T1's magnitude is modest, and it is not fixable
  from the current asset base.
* **A control validates the harness on a *numeric* signal.** It says nothing
  about whether the *text* pipeline (extraction → chunking → labels →
  features) preserves signal. The lens's T3 (filing-change features) remains
  the only proposed text-side positive control and is not built here.
* **These are single-run numbers on a frozen corpus**, not a stability study
  across corpus versions. The corpus tripwire tests pin the population so a
  silent corpus change is caught rather than absorbed.

---

## 10. Reproduction

Exact commands, from the repo root. Zero network calls; frozen artifacts are
read-only; the only file written is
`data/hardening/controls_results.json`.

```bash
cd /Users/vihanpatil/personal/projects/FinScreen

# the controls themselves (~5 s)
python3 controls.py

# the offline test suite (32 tests, ~1 s)
python3 -m pytest test_controls.py -q

# confirms nothing here perturbed the shipped harness (35 tests, ~45 s)
python3 -m pytest test_phase_c_leakage.py -q
```

Provenance recorded inside the results JSON under `provenance`:

```
spec_sha256                   5e38839836c250c349b33192cc53e7b52258eab2b2488ac5d48449caa2199f18
controls_py_sha256            b44358c389134dd9f5fc80b9a0d00be624d829b67d3d7f10d7e5e636c71dc32c
imported_dedup_source_sha256  4c989b7cc60c780db650b3debada19a1170da0be6731943c00068a6f9f46b5f4
filings_metadata_e2.db        61dcefaae43ce05c3edbc0a3106339b34ef2f6c6e1f97ac6e7d6d107c29734a7
prices_e2.parquet             744e1cc5ccc2bfad9640f51962edbb87bbd4d7076491262d650cfee70d5e6343
fundamentals_e2.parquet       f6064adfdf30dd21330fb13df40eca67f8a88256885be051c887a6e85abe517e
```

**Determinism was verified by running twice.** Every statistic in the results
JSON is bit-identical across the two runs. Exactly one field moved:
`backtest_py_sha256` (`1893b46e…` → `ea15a86f…`), because item H2 edited
`backtest.py` between them. `imported_dedup_source_sha256` did **not** move —
which is precisely why the dedup rule is pinned by the sha of the **function
source** rather than of the whole file: it demonstrates, rather than assumes,
that H2's concurrent edits touched nothing this item depends on. The
file-level `backtest_py_sha256` is informational only and is expected to
churn while H2 is in flight. `backtest.py` and `diagnose.py` were **not**
modified by this item; H2 owns them.

## 11. Files

| path | role |
|---|---|
| `/Users/vihanpatil/personal/projects/FinScreen/controls.py` | new; the controls, the SPEC, the leakage assertions, the post-hoc diagnostics |
| `/Users/vihanpatil/personal/projects/FinScreen/test_controls.py` | new; 32 offline tests |
| `/Users/vihanpatil/personal/projects/FinScreen/data/hardening/controls_results.json` | new; the run this report is generated from |
| `/Users/vihanpatil/personal/projects/FinScreen/data/hardening/status/H1_controls.md` | this file |

**A red-team pass has not been run on this work.** Per the standing rule it
precedes the owner's read and substitutes for neither.
