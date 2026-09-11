# G3 — the ruling packet (plain English)

**RULINGS RECEIVED 2026-09-11** — the owner ruled all 23 (verbatim + readings:
`data/f5/G3_OWNER_RULINGS_2026-09-11.md`). The sentence below that "nothing
REPORTS a per-company score" is superseded by §14 of the pre-registration under
the owner's core value statement; the rest of this packet is the historical
record of what was asked. **One measured number in it is also superseded: the
0.487 NEGATIVE recall quoted below (decision 12's head-2 disclosure line) is the v1.1
adapter's eval; the adapter that actually labeled this corpus is v1.2
(`cadca849…`), whose own held-out eval measures 0.529 (64/121), and that is the
number the pre-registration and every scorecard page carry (red-team NF-1).**
The stored-NEGATIVE precision quoted beside it, 25/49, is unchanged.

**G3 is the moment the experiment's rules get frozen, before any answer exists.**
The machinery is built and tested: feature tables, the price target, three
"heads" (the main return comparison, an earnings-volatility study, an
exit-prediction study). What has *not* happened — enforced in code, not by
promise — is any calculation of whether the text features predict anything. The
runners physically refuse to fit a model until `data/f5/G3_RATIFIED.json` exists
and matches the pre-registration document. **No number about text-versus-returns
has been computed for E2. Zero.** That is the point: rules written after seeing
the answer make the answer meaningless. So the rules get written first, by you.

**How to rule.** Read the 23 decisions below, in four groups. **A** — five that
genuinely change what the study measures. **B** — two data-source ratifications
only you can make. **C** — fourteen with obvious defaults you can wave through in
one line. **D** — two pre-commitments only you can discharge (18, 19); a
Group-C wave-through does not reach them. Reply in chat with the decision
numbers — e.g.
*"Defaults for everything except 4: alternative, 8: ratify"* is a complete
ruling (decision 8 has no default — it is ratify-or-refuse, so it must be named
either way). The main session then edits the DRAFT rules in
`data/f5/G3_PREREGISTRATION.md` into ratified rules, computes the document's
sha256, pins it into `data/f5/G3_RATIFIED.json`, and records the ruling in
HANDOFF §3. **Only then can any head run.** Your 14-day clock (your own ruling,
2026-09-11) starts when you receive this packet; if it lapses, the council
re-convenes to close E2 on the record as "not run, documented" rather than let
it drift.

**Three things this run cannot give you.** These follow from **HANDOFF §1's four
contractual non-goals** — not a trading bot; not investment advice; no live
capital, in any phase; no return-guarantee or "beats the market" language, every
performance number reported with exactly how it was measured, next to it.
**(1) not a trading signal** — nothing places, queues or recommends a trade; a
positive would be a research finding, never an instruction to act; **(2) not a
return estimate** — the number is a rank-correlation *difference* between two
screening scores, not a return, not a P&L; **(3) not a per-company score** —
outputs are per-fold tables over a whole universe, and **nothing REPORTS a
per-company score: scores exist only inside a fold, as the input to a rank
correlation, and are never written out, ranked, or shown for any company.**

*Separately, and from a different ruling:* the app lane you ruled on 2026-09-11
(HANDOFF §3, that date) carries its own boundary sentence — *"The tool may show
the owner what a filing says, how a labeler with disclosed error read it, and
what changed since last time — it may never rank, score, compare, or suggest
what to do, even when the only reader is the owner."* That sentence binds the
report layer; it is not one of the §1 non-goals and is cited here so the two are
not conflated.

**The fixed scope sentence every claim out of this run must carry, verbatim:**
*No text-vs-numeric IC improvement of economically relevant size is detectable in
this universe through this labeling schema, these features, this labeler, and
this feature specification.* Note what it does **not** say: never "no effect
exists", never "text does not predict returns".

---

# A. The five that genuinely change the science

### 3 — what counts as "the text features", and the headline number

The headline asks: does adding text features to a numeric-only screening score
improve its rank correlation with next quarter's excess return? **Default:**
headline = deduplicated Spearman IC delta, raw version reported beside it,
10-K/10-Q-only version as the honest secondary; the confirmatory text block =
**8 legacy features + 2 novelty features + 16 embedding components**; the 13
red-flag columns stay **exploratory only** (already forced by the v1.2 teacher
spot-check, 42.00% error [35.37, 48.93]); specification = trailing ranks primary,
raw levels secondary, always as a pair. **Alternative:** putting red flags back
in the confirmatory block reverses a demotion you already ratified; dropping the
embeddings shrinks the block from 26 columns to 10 and moves the detection
threshold. **Measured fact that matters:** the *reason* ranks were made primary
did not survive re-measurement. On E2, `log_total_assets` has an identity-ICC of
**0.9453 [0.933, 0.957]** raw vs **0.9420** ranked, and ranking *raises* the ICC
of **nine of thirteen** features, sharply for six. All nine, raw → ranked:
`operating_margin` 0.383 → 0.761, `net_margin` 0.329 → 0.661, `realized_vol_63`
0.265 → 0.483, `cash_to_assets` 0.625 → 0.801,
`operating_cashflow_to_revenue` 0.355 → 0.528, `book_to_market` 0.683 → 0.835
(those six rise by ≥ 0.15), then `revenue_yoy_growth` 0.128 → 0.217,
`eps_diluted_yoy_growth` −0.012 → 0.060, `net_income_yoy_growth` 0.001 → 0.059.
Four fall, all slightly. Ranks do not strip company identity. The draft keeps the
pre-registered pair anyway — changing it after measurement would be the post-hoc
move this gate exists to prevent — and rewrites the justification honestly.

One open sub-question sits inside this decision, and it needs **two numbers that
are not the same number**: **4.53%** of chunks (14,342 of 316,291) touched the
labeler's training split, while **80.2%** of the 7,405 modeling rows (5,938)
contain *at least one* such chunk. These answer different questions — how much of
the text is contaminated, versus how many filings carry any contamination — and
the census's standing warning applies: **never quote one as the other.** Both are
**lower bounds** (CIK-level exposure is 15.85%). Under the "any" rule the
"without overlap" arm scores only ~1,467 rows, with the fit unchanged. Whether
that arm should also drop those filings from *training*, or use a share threshold
instead of "any", is part of this ruling.

**A coverage hole you should see before ruling what "the text features" are:**
**145 periodic filings from 10 companies were never extracted**, and they are not
random — Citigroup **100%** of its periodic filings (41), Morgan Stanley **93%**
(38), US Bancorp **81%** (26), Colgate-Palmolive 64% (16), BNY Mellon 56% (9),
Wells Fargo 24% (10), then AIG, Intel, PNC and Texas Instruments (1 each).
**Seven of the ten are financials.** For the three largest losses those companies
enter the text arm on 8-K press releases essentially alone across the decade, so
`share_chunks_risk_factors`, `share_chunks_mda` and the Item 1A / Item 7 novelty
family carry a **sector-shaped hole**, and any sector-level reading of the result
must say so. Nothing in this packet fixes it; ruling the default means accepting
it as a disclosed limitation (it is carried in the pre-registration, §11).
**RULE: default / alternative / other**

### 4 — how many folds, and where the study starts

**Default:** six-quarter burn-in, first test quarter **2018Q1**, last **2026Q1**
(the last quarter whose 63-session windows all close before the price snapshot's
last session, 2026-08-24) → **33 folds**. The mandatory "post-2019" arm starts
**2019Q1** → 29 folds, and it is **not a second study**: it takes the *same 33
fits* and reports the subset of test folds from 2019Q1 onward. Nothing is
refitted; the training sets still contain the 2016–2018 cohort. It asks "does the
headline survive dropping the four most-censored test quarters?", not "what would
a 29-fold study have found?". **Alternative:** 26 folds starting 2019Q4 — under
it the post-2019 arm is the primary run relabelled, so the censoring check tests
nothing. The default deliberately buys the four 2018 folds from the most censored
cohort, which is what makes that check meaningful.

**Measured (counts):** 119–161 deduplicated rows per fold (mean 136.3) over 82–99
companies; the 2018Q1 fold loses **16 of a would-be 98-company panel (16.3%)** to
companies with no price data at all, decaying to zero by 2025Q3. A second,
unrelated reason the panel is thinner than the universe: the **145 never-extracted
periodic filings from 10 companies, seven of them financials**, described under
decision 3 — that hole is in the *text* arm and no fold choice repairs it.

**Projected (from E1's noise anchor; E2's own SE is measured at Step 4):**
like-for-like at the measured per-fold sample, 33 folds versus the 26-fold
alternative, the detection threshold is **0.0303 vs 0.0338** if folds are
independent and **0.0408 vs 0.0455** at the assumed fold autocorrelation — the
seven extra folds buy about **10.3–10.6%**. A *different* comparison, often
confused with it: against the planning number published in H2 (26 folds at 158
rows per fold: 0.0315 / 0.0424) the whole bracket moves only about **3.8–4.1%**,
because the measured per-fold sample is **136**, not 158. The extra folds help;
the smaller-than-planned folds take most of it back.

**A word needs pinning:** "post-2019" in plain English means 2020Q1, which gives
25 folds and loses the tightest margin rung; the draft pins 2019Q1 because that
is the only reading consistent with the "29 folds" already written into the plan.
**RULE: default / alternative / other**

### 13 — head 3: what counts as a company "exiting"

**Default:** count only `delisting_form_25` and `deregistration_form_15`; drop
the large exchange-transfer channel and the bankruptcy channel. Horizon 4
quarters, metric AUC, folds past the observation cut reported censored and not
scored, claim scope **"exit", never "distress"**. **Alternative:** all four event
kinds, screen still on — **129 positives instead of ~54**. (What the code did
before today, with no screen at all, was score **480 exit rows as 480
positives**, roughly three in four of them **wrong**; that is no longer on the
table and is the reason the screen exists.) **Measured:** of the 480 exit rows on the core
panel, **351 (73.1%) are followed by the same company still filing in-membership
a year later** — those are exchange transfers and share-class deregistrations,
not exits; only **129** plausibly end membership. By channel: exchange-filed Form
25 **79.2% non-exits**, Form 15 53.8%, plain Form 25 56.0%, and **both**
bankruptcy rows are non-exits, so that channel gives **zero** usable positives.
M&A cannot be separated from distress at all (`items` is NULL on 666 of 668
rows). The default lifts **label precision — how often a row marked "exit" really
is one — from ~27% to ~46%**; it says nothing about how well a model predicts
them, which is what "precision" usually means and is not measured anywhere in
this packet.

**What changed today, and it changes this decision:** the still-filing screen is
now implemented (`head3.exit_screen`), so the 129-row set the census called
unreachable *is* reachable — it is simply all four kinds with the screen on. So
the live trade-off is **two kinds + screen → ~54 positives** (the default,
kind-pure) versus **four kinds + screen → 129 positives**, the extra 75 coming
from the exchange-transfer channel whose rows the screen nonetheless says ended
membership. At 30 scored folds more positives is worth something for an AUC; a
channel where four raw rows in five are not exits is a noisier source even after
screening. The default takes purity. Say so if you want the count instead.

**What the "still filing a year later" screen cannot see:** **31 of the 480 rows
were filed within a year of the panel's last date (2026-08-24)**, so the company
never had a chance to be observed still filing — those rows are **unobservable,
not negative**. **6 of the 31 fall inside the pinned two-kind set** (2 plain Form
25 + 4 Form 15) and all 6 survive the screen into the ~54 positives on absence of
evidence. Two counters travel with every head-3 positive count so this stays
visible: `exit_rows_dropped_by_screen` (64 of the 118) and
`exit_rows_unscreenable_within_365d_of_panel_end` (6). Three of the 33 folds are
censored by the observation cut, leaving 30 scored.
**RULE: default / alternative / other**

### 15 — the equivalence margin (how we may say "no effect")

If the study finds nothing, we want to say something stronger than "nothing" —
"any effect bigger than Δ is excluded". You already ratified (2026-08-26) that we
pre-register the *procedure*, not the value. **Default:** Δ = the smallest rung
of {0.03, 0.04, 0.05} whose power requirement (SE ≤ Δ/2.487) is met by the
standard error measured from E2's own folds; never above 0.05; if no rung is
met, the result prints **UNPOWERED** and no equivalence claim is made, ever. The
whole procedure runs inside the runner and Δ is written to the results file
*before any per-fold number is printed*, so no human sees a delta before Δ is
fixed. **Alternative:** removing the UNPOWERED branch, or adding a rung above
0.05, would let a weak design claim "no meaningful effect" when it could not have
detected one. **Projected (from E1's noise anchor; E2's own SE is measured at
Step 4), with the warning:** at 33 folds the detection threshold is **0.0303**
(no variance floor, independent folds), **0.0408** at the assumed
autocorrelation, and **0.0570 / 0.0770** if the floor is real — and **every
"floor is real" branch is UNPOWERED at 33, 29 and 26 folds.** Whether that floor
exists is unknown: E1's six folds could not resolve it (χ² p = 0.13 and 0.16 in
both directions). E2's 33 folds give the **first chance to measure it**, before
any delta is read; **whether they resolve it is not established** — that is
itself one of the things Step 4 finds out. Two projections are knife-edge
(missing a rung by 1.3% and 0.2% of the cap), so read them as "unsettled", not as
a forecast. Standing caveats on all of these: they
are **lower bounds** (folds are not independent), the noise anchor was measured
on E1's 2025–26 mega-cap folds, per-feature thresholds scale ~0.4×–2.4×, and the
old published 0.019–0.037 bracket is superseded and must not be quoted.
**RULE: default / alternative / other**

### 20 — whether one company's boilerplate may label another company's filing

A labeled passage is attributed to every filing it appears in (your 2026-08-11
ruling). At E2 scale, shared boilerplate carries a label across company lines.
**Default:** restrict attribution to occurrences **under the same company**,
report the cross-company share, keep the E1 rule as a named sensitivity.
**Alternative:** keep E1's rule unchanged. **Measured:** 5,706 chunks (1.80%)
occur under more than one company; **99,636 of 854,933 occurrence rows (11.65%)**
attach a chunk to a *different* company; one Wells Fargo chunk reaches **6,220
filings across 169 companies**. Adopting the default rebuilds
`text_features_e2.parquet` (~19 seconds) and moves every text feature slightly.
This extends a ruling you made, on evidence that did not exist when you made it.
**RULE: default / alternative / other**

---

# B. Data-source ratifications (only you can make these)

### 7 — converting non-US-dollar figures

One core member (Enbridge) reports in Canadian dollars. You ruled the direction
on 2026-08-25, verbatim: *"Convert to USD as standard in future for all companies
in case not USD."* What is ratified now is the **mechanism**: a dated FX series
from the price provider we already use (zero new providers), converted at the
rate **as of the feature date** so it stays point-in-time safe, with a second
non-USD reporter converted and logged — **not** treated as fatal (the council's
draft said FATAL; that contradicts your instruction and is not adopted).
**Honest catch:** as built there is **no conversion at all** — 108 rows are
currency-blocked and two features are simply NaN for that company. Ratifying the
default means an ingest, a rebuild and a new test before head 1 runs, not just a
document edit. Leaving them NaN and disclosed is a cheaper, legitimate
alternative that contradicts nothing except your stated preference.
**RULE: default (convert) / alternative (leave NaN and disclose) / other**

### 8 — the price source

Every return in this study comes from Yahoo Finance's free keyless endpoint. It
was never ratified — it was a fallback when the originally ratified source turned
out to be bot-gated, and Yahoo's robots.txt disallows automated access with no
published terms for this use. It is the only major unratified input in the
project. **Ratify or refuse**; refusing means no head runs until a replacement is
ratified and the snapshot rebuilt. **Measured:** snapshot sha `744e1cc5…`,
**3,179 sessions 2014-01-02 → 2026-08-24, 213 priced companies**;
**split-adjusted only, not dividend-adjusted** — that caveat travels with every
price-derived number, including head 2's outcome, which an ex-dividend day inside
its window inflates. Also note what is missing: 27 of 176 core companies have no
price column, 31 universe members never enter the benchmark, and **324 modeling
rows have a complete window but no subject price** (the counter
`n_complete_window_missing_subject_price`; **the cause is not separately
measured**, so they are not "delistings"). The direction of the bias is the
point: dropping dead names removes the worst outcomes from the scored set and
removes dying members from the benchmark denominator.
**RULE: ratify / refuse / other**

---

# C. Clear defaults you can wave through

A single line — *"defaults on all of Group C"* — rules all fourteen. (Decisions 18 and 19 used to sit here; they are pre-commitments only you can discharge, so they moved to Group D and a Group-C wave-through does **not** cover them.)

**1 Benchmark.** Equal-weighted average of that date's universe members
**excluding the company itself**, membership-dated; member set = the whole
universe, both strata (median 128 priced members/session). Core-only would
rebuild the target table. E1 and E2 numbers declared incomparable. *RULE:
default / alternative*

**2 GLD (the gold trust).** Excluded from the benchmark average and from IC rows
in all heads, with one sensitivity row including it. 8 modeling rows, 6 inside
the 33 folds. *RULE: default / alternative*

**5 Label purge.** Drop training rows whose 63-session outcome window closes on
or after the test quarter starts; no extra buffer. Measured: 6,194 instances
purged, 6.17% average, worst 16.57% in 2018Q1 (E1 had no purge and 12.9% of its
training labels resolved inside their test quarter). *RULE: default /
alternative*

**6 Same-day comparisons.** Keep same-day peers in the ranking comparison set as
primary and run the stricter version beside it as a mandatory named arm — on E1
the two differed by 0.0515 in the headline, so it is reported as a pair, never
chosen. (1,751 filings were accepted the prior evening after 17:30; the rule
opens 1,717 of them one to two sessions late — conservative.) *RULE: default /
alternative*

**9 The 8K_BODY register.** Exclude (790 chunks; the labeler saw zero training
examples of that section type). *RULE: default / alternative*

**10 Section masks.** Mask sentiment on Risk Factors and guidance on MD&A / Risk
Factors before aggregating — the G2 deliverable. Declining puts 4,177 sentiment
and 2,826 guidance off-matrix rows (230 active) back in scope and needs a new
pre-registration. *RULE: default / alternative*

**11 WITHDRAWN guidance (n = 66).** Keep evaluable, mapped to −1, one sensitivity
row excluding it. Worth knowing what that row is: 52 of 66 are 2020 and 41 are
one quarter (2020Q2), touching 35 of 7,405 rows. **It is a 2020Q2 sensitivity and
will be labelled as one.** *RULE: default / alternative*

**12 Head 2 (earnings-volatility study).** Predictor = share of negative-sentiment
chunks, direction pre-registered positive; outcome = average absolute daily move
over sessions +1 to +5 divided by the trailing 60-session average (benchmark-free,
so decisions 1–2 do not propagate); wild-cluster bootstrap over event quarters,
few-clusters limitation stated every time. Default ends at the last **complete**
quarter (40 clusters / 3,904 events): partial 2026Q3 contributes 92 events
against a complete-quarter range of 83–107, so it *looks* full-sized — a trap
that does not announce itself. Permanent disclosures: the predictor is the field
G2 ruled **INDETERMINATE** (86.94% [82.93, 90.13]), stored-NEGATIVE precision
25/49, teacher NEGATIVE recall 0.487. **Flag: "last complete quarter" has no
parameter key in the code yet — adopting it is a small code change before head 2
can run.** *RULE: default / alternative*

**14 LOCO budget.** Six folds at fixed indices (2018Q1, 2019Q3, 2021Q2, 2022Q4,
2024Q3, 2026Q1), 1,438 refits, **descriptive only** — no per-company inference at
six folds. *RULE: default / alternative*

**16 Extension spot-check timing.** Run it only when a branch actually consumes
the extension arm, or earlier if you want the arm characterized regardless. Until
it runs, extension labels are not promoted and nothing in G2 may be quoted as
speaking to those three sectors. *RULE: default / alternative*

**17 The stopping rule.** Sign and date the Option 1 text, reproduced verbatim in
§13 of the pre-registration: all three outcomes close the alpha line; a positive
earns only the pre-registered robustness suite plus the extension replication,
then stops; no E3 without a new ratification naming what changed. **Your
signature on §13 is the freeze.** *RULE: sign / amend*

**21 A cash-flow ratio's period mismatch.** `operating_cashflow_to_revenue`
divides year-to-date cash flow by *quarterly* revenue on **7,603 of 18,300 rows
(41.5%, after the period-end fix; 8,433 = 46.1% before)**. Default: duration-match both sides and disclose (a numeric rebuild).
*RULE: default / keep ported / drop the feature*

**22 Fundamentals staleness guard.** Keep the 200-day cap and disclose. It no
longer sits in an empty band: accepted facts reach p99 = 139 days with 47 above
180, and discards begin continuously at 201 (1,868 discards over 99
company-family pairs). *RULE: default / family-specific guards*

**23 The two new text families.** Eight sub-choices, all defaulted: **(a)** the
"year-over-year" novelty feature is currently quarter-over-quarter (median gap
**91 days** — a 10-K's prior is the preceding 10-Q), so pin the prior-year filing
of the **same form** and rebuild (18 s); **(b)** Risk-Factors novelty is dominated
by short "no material changes" stubs (39.0% of pairs have a side under 50
shingles; 855 exact zeros, 516 exact ones) — apply a minimum-length filter and
disclose the stub count; **(c)** keep the whole-corpus prior pool; **(d)** exclude
8K_BODY sections from the embedding family for symmetry with decision 9 (25-min
rebuild); **(e)** keep equal weighting of sections when pooling a filing;
**(f)** note the 64-window cap bit 17.1% of sections and dropped 21.4% of
windows; **(g)** 16 principal components, rank-transformed on the primary arm
only; **(h)** the embedding model is a third-party artifact pinned by name,
revision `1110a243…`, weights sha `53aa5117…`, Apache-2.0. *RULE: defaults / name
the exceptions*


---

# D. Pre-commitments only you can discharge

**Two decisions, no wave-through.** Both are kill-criteria you ratified on
2026-08-26. A model can read the evidence and say what it thinks; per HANDOFF §7
that reading is never your ruling, which is exactly why these are not in Group C.

**18 KC1 — did the positive controls fail?** H5 §5 kill-criterion 1 says that if
H1's positive controls fail, the whole three-branch stopping rule is **VOID** and
must be re-drafted rather than mechanically carried. So this is the switch that
decides whether §13 means anything. **Main-session reading, flagged as a
reading:** control T1 **failed its own pre-declared bar** — t = **3.13** against a
declared 4.0, and **70.7%** of quarters against a declared 75% — while the
relation it tests is present (bootstrap CI **[+0.026, +0.105]**) and the stack is
affirmatively verified (a 2.82× announcement-day volatility spike, post-close D+1
dating confirmed). **T2a and T2b are AMBIGUOUS**, both CIs containing zero.
**Correction (2026-09-11, red-team):** removing the diagnosed stale-Q4 matching
defect **raises** T1 to **t = 4.22 with 75.6% of quarters positive — both
pre-declared bars met** (`controls_results.json` → `D3_stale_quarter_arm`,
`T1_core_stale_removed`; `H1_controls.md` §4d). An earlier draft said "drops to
1.58"; that figure belongs to T2a's stale-removed arm, not T1. For scale: the
announcement-window relation T1 measures registers ~0.06–0.08 IC in this
universe against a ~0.047 zero-information floor; measured post-earnings drift
(T2a) is +0.028 [−0.020, +0.076]. **Default: not triggered by the letter** — the taxonomy
stands, and the stale-Q4 defect is repaired only if that variable enters a head,
which it does not. *RULE: default (not triggered) / triggered*

**19 KC6 carve-out.** Allow reproducing H1's already-published control as a
plumbing check *before* ratification (no text feature enters it). The ratified
wording of kill-criterion 6 says "any E2 IC", and only you can narrow your own
freeze. *RULE: default / alternative (after ratification)*

---

**What ruling "defaults everywhere" actually costs.** Most defaults are free —
they describe what the artifacts already are. Five are not, and they run *before*
head 1 can run. **Rebuilds:** decision 20 (same-company attribution) rebuilds the
text features, **~19 s**; decision 21 (duration-matched cash-flow ratio) rebuilds
the numeric features, **~4 min**; decisions 23a/23b (year-over-year prior +
minimum-length filter) rebuild novelty family A, **~18 s**; decision 23d (drop
8K_BODY from the embedding family) re-embeds, **~25 min**; decision 7 (convert
non-USD) is the expensive one — an FX ingest, a rebuild, and a **new test**,
because no FX code path or FX test exists anywhere today. **Code changes:**
decisions 12 and 13 need two new parameter keys and the logic behind them
(`head2.last_event_quarter` to stop at the last complete quarter,
`head3.exit_screen` for the still-filing screen and its two counters) — **written
2026-09-11, before you rule**, precisely so that ruling the default is not
blocked on engineering. Both keys are now required by the runners, so a document
that fails to pin them is a refusal, never a silent fallback. Everything above is local CPU and **$0**; the API spend
freeze is untouched. Total machine time if you default on all five: **well under
an hour**, plus the FX work.

**One-line ruling template**

> *G3: defaults on all 23 except — 4: ____ · 8: ____ · 13: ____ · (others) ____.
> 18: ____ · 19: ____ · §13 signed.*

Anything not named is taken as the default. Anything not named anywhere in the
pre-registration is **exploratory by default** and can never carry a headline.
