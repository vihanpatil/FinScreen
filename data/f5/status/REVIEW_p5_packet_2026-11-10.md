# REVIEW: P5 forward-loop owner packet (DRAFT 2026-11-10) — and a look-ahead defect in a ratified feature

Reviewer (Opus) red-team of `data/f5/P5_OWNER_PACKET.md`, saved by the main session from the agent's hand-back
(condensed; every finding kept). The reviewer modified nothing, used no network, ran no runner. Verdict: **the
page must not go to the owner as written** — 7 MUST-FIX, 9 SHOULD, 6 NOTE. Main-session verification of M3 and
dispositions are at the end.

## MUST-FIX
- **M1. Universe.** The 136 current members are 100 core + 36 extension; all 139 scored companies are core; the
  extension stratum was never fitted or scored (G3_PREREGISTRATION.md:70 "unpromoted"). Running on 136 is a changed
  procedure, not "continued unchanged".
- **M2. Filing set.** The ratified frame is an inner join of target, text features and numeric features
  (`backtest_e2.py:144`, `:859`); only filings with attributed text chunks entered it (10,608 in-membership 8-K
  targets in the 33 fold quarters, 1,567 8-K rows scored). "Each new 10-K, 10-Q or 8-K" changes the population,
  the tercile cut points and the rows per quarter. An eligibility rule that reproduces the text join without the
  labeler is needed, or the change must be declared.
- **M3. `book_to_market` carries future stock splits.** `numeric_features_e2.py:844`:
  `equity / (shares * pre_close)`; the share count is as reported on the cover page, the close is from a Yahoo
  series adjusted retroactively for every split up to the fetch date. Every filing before a split has B/M
  inflated by the split factor (ratio across the split filing: NVDA 2024 0.116, NVDA 2021 0.257, AMZN 2022 0.044,
  AAPL 2020 0.241, NFLX 0.105, WMT 2024 0.346; TSLA likewise). Consequences: (a) the historical numeric_only and
  text_and_numeric rows contain a look-ahead feature (an inflated value encodes "this company will split before
  2026-08-24", and splits follow run-ups); (b) forward rows would not be inflated — train/serve skew; (c) every
  later split re-adjusts history on the next fetch, so training-row B/M changes between refits.
- **M4. "Calls that provably existed before the outcome" is false for the call.** Only the raw output is logged
  early; the tercile is assigned at quarter close, when most of a 63-session window has passed for early-quarter
  filings. No outcome leaks into the call, but the call does not precede the outcome and conflicts with
  PRODUCT_PLAN.md:248 ("written to an append-only log before prices are known").
- **M5. Legal memo mischaracterised.** Q5 rated a one-time cached fetch ("a few hundred requests", "no new fetch")
  low exposure; it never assessed a recurring scheduled fetch; it did not say "nothing derived from it should go
  public"; the packet omits "Yahoo's terms do prohibit scraping". Reconvene `legal-reviewer` on the recurring facts
  before the owner rules on prices.
- **M6. "No new Yahoo fetch" is ratified text** (G3_PREREGISTRATION.md:201, scoped "for this run"), not only a
  reading; and `OWNER_DECISIONS_2026-11-05.md:48-49` told the owner the paid feed "is needed … for any forward
  paper period" before the owner answered "B. No". The packet must say both. The two owner quotes are verbatim.
- **M7. Ratified §14** (G3_PREREGISTRATION.md:273): the scorecard is "not a forecast … no row is generated for a
  filing whose window has not closed". A forward table is a separate artifact under its own pre-registration.

## SHOULD
- **S1.** The "0.086 if independent" inference is too strong: rows come from ~92.5 companies a quarter (1.47
  filings per company-quarter, near-identical windows), so effective n ≤ ~92 (0.105) before sector shocks. Honest
  statement: observed sd is about twice independent noise; the excess is an unseparable mix of regime change and
  within-quarter dependence; widening helps less than √N by an unknown amount.
- **S2.** 0.184 (k=8) and 0.091 (k=33) reproduce but are lower bounds: 2.8 is the repo's multiplier for bootstrap
  SEs of the text-minus-numeric gap, not for a level IC; t-based 0.215 at k=8; lag-1 autocorrelation 0.15. The
  owner reads hit rates: ~7 calls per company in 8 quarters, Wilson ≈ ±0.3.
- **S3.** Gap rows need point-in-time membership (13 members left 2026-07-01); the reconstitution rule must be
  pinned now (PRODUCT_PLAN §1.5); state whether unresolved rows enter the tercile pool.
- **S4.** Dedup keeps the later filing in a 5-day chain (`backtest.py:311-340`), so a quarter-close call can be
  dropped later; assign at close + 5 days or pin the rule; pin late rows' and gap rows' pool membership.
- **S5.** Alternatives incomplete: `PRICE_SOURCE_OPTIONS_2026-09-11.md:97-99` lists Massive (ex-Polygon) at $0 for
  2 years of history under a personal non-commercial licence, and Sharadar 5-year at $99/yr; "which you have ruled
  against" stretches "B. No" (EODHD) to all paid feeds; prices in that document are two months old.
- **S6.** Charter: say whether completing the loop counts as the charter's paper period; "frozen" read as "frozen
  procedure" is a reading; "evidence accrues" contradicts "a record, not a test"; name "Defer E3"; no stopping or
  maximum length is given though §1.5 requires one.
- **S7.** The position-disclosure / blackout rule and the personal trade log (PRODUCT_PLAN.md:243-247, legal Q4)
  are missing; include or defer with the reason. "Never shared" must cover forward rows explicitly.
- **S8.** The public hash is oversold: commit dates are author-settable; say "evidence against later editing";
  a chain or byte length is needed to verify; daily pushes need credentials in the job.
- **S9. Simpler design.** Calls are assigned at quarter close anyway: a quarterly batch 5–10 days after quarter
  close gives the same calls with ~4 price fetches a year instead of ~250, no daily job, no install step, no
  conflict with the labeler guard.

## NOTE
N1 size-only needs no prices (`log_total_assets`). N2 the EDGAR fetches, fair-access headers and the frozen
`concept_resolution.csv` (new tags become NaN) are unmentioned. N3 "Draft it" and the 2026-11-09 chat statement
are not on disk. N4 P5 says "published either way"; "never shared" departs from it and should say so; the P4
status line is missing. N5 the pages call text_and_numeric "the model"; a numeric-only forward table needs its own
label. N6 8-K bodies were excluded historically (decision 9).

## Verified correct by the reviewer
No fitted model is saved; last test quarter 2026Q1, prices end 2026-08-24 (shas match pin and run log); §13 quoted
correctly; numeric_only mean IC 0.0251, sd 0.1861 on 4,481 dedup rows; 136 current members all priced to the
snapshot end; "no earlier than 64 sessions" matches `target_e2.py`; both owner quotes verbatim.

## Main-session verification of M3 (2026-11-10; no model fit)
Code read at `numeric_features_e2.py:839-844`: confirmed. Independent census from `numeric_features_e2.parquet` +
`prices_e2.parquet` (script in the session scratchpad; the committed version is `data/f5/census_split_lookahead.py`):
shares-as-used = equity / book_to_market / pre-session close; a jump ≥ 1.8× either way between consecutive filing
dates is a split-like event. **15 events in 12 companies** (14 forward, 1 reverse), matching real splits by date and
ratio (NVDA 4.01 and 9.97, AAPL 3.98, AMZN 20.03, TSLA 5.2 and 3.02, WMT 2.99, NFLX 9.96). **251 of the 4,481
scored deduplicated rows (5.6%), 11 of 139 companies**, were filed before a later split-like event; watchlist names
among them: AAPL, AMZN, AVGO, NFLX, NVDA, TSLA, WMT. A descriptive subset comparison of calls on those rows against the rest was reported to the owner in chat; it is not recorded in this tracked file (an 11-company subset figure is treated like a per-company table, legal baseline #4) and is reproducible with `census_split_lookahead.py --show-private`. Splits follow run-ups and the training rows carried the feature too, so no subset is clean. **The effect on the E2
primary (a difference between two arms that both carry the feature) and on every scorecard figure is UNMEASURED.**
The census is a lower bound (threshold 1.8; splits where B/M is NaN are invisible and also harmless).

## Main-session dispositions (decisions, not owner rulings)
- The packet is **WITHDRAWN** (header rewritten; body kept for the record). It is redrafted only after M3 is
  resolved, on the reviewer's simpler shape: quarterly batch (S9), core stratum (M1), a stated eligibility rule
  (M2), a corrected or dropped B/M (M3), the call's timing stated plainly (M4), prices put with the ratified text
  and the 2026-11-05 context (M6), the free licensed tier re-verified and the `legal-reviewer` reconvened first
  (M5, S5), as a separate artifact from the §14 scorecard (M7), not a charter paper period (S6), with the
  disclosure rule and stopping rule in the pre-registration (S6, S7).
- M3 is recorded as a defect in the ratified G3 numeric features (HANDOFF §3, §4 lesson; LIMITATIONS). G3 is
  never re-pinned or re-run. The scorecard pages gain a known-defect disclosure and the identity paragraph stops
  claiming prices were as public at the filing date without exception. Whether to run a POST-HOC sensitivity arm
  (as F6-A did for decision 11) is put to the owner.
