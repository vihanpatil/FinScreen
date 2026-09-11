# PRODUCT PLAN — from research pipeline to a validated personal investing tool (written 2026-09-11 on the owner's reaffirmed goal)

**Owner's goal, verbatim (chat, 2026-09-11, reaffirmed after the main session and the
tech council raised their concerns):** *"to have product be useful and amazing, that if
one looks at my portfolio, may ask to use as well. I know I cannot compete with huge
tech firms and investment banks and their resources, but this should genuinely be
useful and give accurate advice. Ensure that this is tested on older company reports
which are then verified with real life stock market prices and how they moved up and
down throughout. That should test and actually verify that the advice has and would
have worked in the past (factor in when reports are reported and if they would help at
the proper times). Then once everything is verified to have worked, I can test on
modern and upcoming data to see if I make profit."* Then: *"REFACTOR."*

**Status of this document:** the owner's decision supersedes the 2026-09-11 identity
line ("never a score or a recommendation") and amends the charter's "not investment
advice" non-goal **for the owner's own use**. The council's 2026-09-11 advisory
(`data/f5/status/COUNCIL_ADVISORY_product_truth_2026-09-11.md`) stands on the record
as dissent. The conditions in §1 are the main session's execution conditions; the owner
may strike any of them in writing.

---

## 0. What "accurate advice" can honestly mean here

Nobody can promise accurate advice. What can be built is a recommendation whose
**historical track record is measured properly and shown beside it**: generated only
from information public at the time, tested out of sample over many years, reported
with confidence intervals, drawdowns, and costs, paper-traded forward before use, and
re-validated continuously. That is what "verified with real stock prices at the proper
times" means when done right, and it is what this plan builds. The honest expectation,
stated once and not hidden: filing text alone is unlikely to be a large edge for the
biggest US companies; the product's real advantages are discipline, point-in-time
correctness, and transparency, and any edge found will be modest. If the evidence says a
signal does not work, the product says so and does not use it.

## 0.5 The real-data-first rule (owner's lesson, 2026-09-11)

The owner lost days and millions of tokens on another project (a resume matcher)
whose evaluation was built on synthetic jobs and CVs; on real CVs nothing worked and
everything was scrapped. **Rule for FinScreen, binding on every phase below:**

1. **Synthetic data is for unit tests only.** It never stands in for evaluation,
   never produces a number anyone reads, never appears in a demo.
2. **Every feature is proven on real, un-curated inputs before it is called done.**
   "Un-curated" means companies the builder did not choose: the owner names them,
   or a seeded random draw from the SEC ticker list picks them, and the failures are
   reported, not filtered out. The first such test is P1a below.
3. **Where this project already carries the same risk, it is named, not hidden:**
   the labeler was trained on model-generated (Claude) labels of 25 large companies
   and every accuracy number is model-consensus, not human truth (G2 §0); its behaviour
   shifted measurably on the larger corpus (F4 §2). Mitigation: the reading aid puts
   every label beside its passage so the owner sees errors directly; the owner's own
   reading of real reports is the human check; any new universe (mid-caps, arbitrary
   tickers) gets its own label spot-check before its labels count.
4. **The demo is a live run on a company the viewer names**, not a curated example.
5. **No marketing claim precedes its evidence.** The site may explain what the tool
   does today and what it is testing; it may not state or imply returns until P5 has
   a record.

## 1. Execution conditions (main session; owner may strike in writing)

1. **Paper before live.** Any signal is paper-traded forward, pre-registered, for a
   stated number of quarters before it informs a real position. No live-capital hook
   exists in the code in any phase.
2. **No claim without out-of-sample evidence.** A recommendation surface shows its own
   backtested and paper record, with costs, or it does not exist.
3. **Distribution requires legal review.** Personal use is the owner's business.
   Letting others use it (or sharing rankings) is regulated territory; a lawyer reviews
   before anyone else touches it. Until then: personal use only.
4. **No new API spend without owner sign-off** (unchanged). A licensed price feed is
   new recurring spend and is the owner's decision (§4, decision A).
5. **Everything pre-registered.** Signals, costs, universe, rebalance rule, and stopping
   rules are written before the data is seen, as the whole repository has done so far.

## 2. Where we are (what has been done) and why it is the right foundation

| built and verified | why it matters for the goal |
|---|---|
| Point-in-time ingestion of 45,632 filings, 244 companies, 2016–2026; fundamentals that never leak restatements; filing dates that respect after-hours acceptance | this is exactly "factor in when reports are reported" and most retail backtests get it wrong |
| A local labeler (Qwen 2.5 7B student) that reads filings at $0 with measured error | the text signal family, if any, comes from here |
| A walk-forward harness with a 63-session excess-return target, expanding folds, dedup, purge rule, and a pre-registration gate | this is the first version of "verify the advice would have worked" |
| E1 result: no fold-robust text signal on 25 companies | the honest prior |
| The reading aid (`report_filing.py`) | the product's front end for reading a company |

## 3. The plan, in order

### P1 — Finish E2 (the first validation of the text signal). 14 days.
The G3 packet (`data/f5/G3_OWNER_PACKET.md`) is delivered with this plan; the owner
rules its 23 decisions, the three heads run, the owner reads the per-fold tables. Under
the re-ratified goal, the branch consequences change: a **positive** proceeds to P3/P5
instead of "write up and stop"; a **null or unpowered** result means the text family is
not used as a signal (it stays in the reading aid as information) and the product
continues on the numeric signal families. The rest of the F5 plan (freeze, guard,
margin procedure, disclosures) is unchanged — it is what makes the result believable.

### P1a — Any-ticker on demand, proven on un-curated companies. 3–4 sessions. **First milestone.**
`ingest_one.py` (ticker → CIK → EDGAR metadata → documents → extract → chunk) and
`label_filing.py` (the same v1.2 adapter, same prompt, a 10-row repro canary against the
G1 eval before the first real label), feeding `report_filing.py`. Acceptance test, the
real-data-first rule made concrete: **10 companies outside the 244-company universe,
chosen by a seeded random draw from the SEC ticker list (the owner may add or replace
any), each rendered end to end; every failure recorded in
`data/app/status/L2_2_external_companies.md` with its cause.** Nothing is called done
until that table is honest. This is also the demo's backbone (§P-S).

### P-S — Show: demo, video, website. In parallel from P1a; owner directs.
- **Demo:** a live run — the viewer names a ticker, the tool fetches, labels and
  renders the report in minutes. No curated examples.
- **Video:** a screen-captured narrative of the live run plus the pipeline story
  (storyboard in `site/STORYBOARD.md`; the owner records or approves narration).
- **Website:** a scroll-driven explainer in `site/` (static, deployable to GitHub
  Pages): the filing's journey — EDGAR → extraction → the local labeler → point-in-time
  joins → the walk-forward test → the evidence panel — told as a 3D/animated flow the
  viewer scrolls through, in the spirit of the supply-chain site the owner described.
  The owner leads direction. Content rule: §0.5 item 5 (no return claims); the site
  invites interest, it does not give advice; a waitlist is fine, a recommendation is
  not (P6).

### P2 — Build the missing half of the validation: a portfolio simulator. 3–4 sessions.
The harness measures rank correlation. The owner's question is about money. New module
`portfolio_sim.py`, pre-registered, consuming the same point-in-time frame:
- long-only portfolio rules (equal-weight top decile / top N, quarterly and monthly
  rebalance), with transaction costs (bid-ask + commission model, pinned), turnover,
  and position limits;
- total-return prices including dividends and delisting returns (needs decision A);
- benchmark = S&P 500 total return and the equal-weight universe;
- outputs per strategy: cumulative return, annualized return, volatility, Sharpe,
  max drawdown, hit rate, per-year table, bootstrap confidence bands, and the
  **"what this would have done"** panel: for every historical recommendation, the
  price path after it at the proper date;
- multiple-testing control: every signal tried is logged and the family-wise error is
  reported (otherwise the best of many backtests is noise).

### P3 — Signal research program, pre-registered. 4–6 sessions + GPU nights.
Candidate families, each with a one-page pre-registration and its own walk-forward
result in P2's simulator:
1. **Text** (from E2): guidance-direction changes, year-over-year novelty ("lazy
   prices"), sentiment shifts. Used only if E2 is positive.
2. **Numeric, well-documented:** momentum (12-1), value (book-to-market, earnings
   yield), quality (margins, accruals), post-earnings-announcement drift from the
   earnings-surprise machinery already in `controls.py`. These are known factors;
   the product's job is to implement them point-in-time and honestly, not to claim
   novelty.
3. **Combined model** (numeric + text), nested walk-forward, compared to numeric only.
Universe expansion: mid-caps, where text is more likely to matter and coverage is
thinner. That is a new ingestion + labeling campaign (the extension-stratum machinery
exists; ~3–4 GPU nights per 35% of core).

### P4 — The product surface. 3–4 sessions.
`screen.py` + the reading aid: for a company, the validated signals and their evidence;
a ranked watchlist where every rank carries its backtested track record, costs, and
drawdown beside it; the "what this would have done" panel per recommendation; the
disclosure block (labeler error, data limits, out-of-sample record, paper record).
Nothing is shown without its evidence.

### P5 — Paper forward test, then personal use. 8 quarters minimum, wall-clock.
Pre-registered: frozen model and rules, live-dated recommendations written to an
append-only log before prices are known, scored quarterly against the same metrics,
published either way. The owner's "test on modern data" is this, on paper. Live use
of a signal is the owner's personal decision after the paper record exists.

### P6 — Distribution, only if the owner wants it and only after legal review.
Licensed data, terms-compliant sources, the disclaimer regime a lawyer specifies,
and a re-ratification. Not scheduled.

## 4. Decisions only the owner can make now

| # | decision | why it gates the plan | default |
|---|---|---|---|
| A | **Price data source.** Yahoo's keyless endpoint is under a robots.txt disallow and is split-adjusted only (no dividends, no delisting returns). A terms-compliant total-return source is needed for P2 and for any use beyond research. Options: a paid feed (tens of $/month; the owner approves the spend) or a free tier with acceptable terms | P2 cannot report money-metrics honestly without total returns; distribution is impossible on the current source | owner names the budget; main session lists candidates with terms |
| B | **Charter wording.** Confirm the amended identity line in one sentence, e.g. *"A personal investing research tool: validated screening signals with their measured track record beside them; personal use; distribution only after legal review."* | it replaces two ruled lines and the council's advisory must be answered on the record | as written |
| C | **Universe expansion to mid-caps** (new ingestion + labeling, GPU nights, more owner reads) | where a text edge is more plausible; without it the study stays a large-cap study | yes, after P1 |
| D | **The P5 paper period** | the number of quarters before any personal use | 8 |

## 5. What gets refactored, concretely

- **Charter documents:** README "What this is not" and HANDOFF §1 rewritten to the
  amended identity (advice for the owner's own use with disclosed evidence; no claims
  without evidence; paper before live; distribution after legal review). The old
  lines are kept as history in HANDOFF §3.
- **Stopping rule:** H5 Option 1's "a positive is never a signal to act on" is
  superseded by P1's branch consequences; recorded as a dated ratification.
- **F5_PLAN.md:** stays as the E2 protocol; its §5 kill-criteria table notes the
  supersession. Nothing in the runners changes.
- **New modules:** `portfolio_sim.py`, `signals/` registry with one pre-registration
  file per signal, `screen.py`, a `paper_log.jsonl` writer. Each with tests, each
  point-in-time, each red-teamed before its numbers are read.
- **App lane:** L2.2 (any ticker on demand) continues unchanged; the refusal list is
  amended to allow a ranked watchlist **only** when it carries its evidence panel.
- **Retired assumptions:** "never a score" (personal use); "never distribution"
  becomes "not without legal review".

## 6. Honest cost and calendar

| phase | agent sessions | owner touchpoints | wall clock |
|---|---|---|---|
| P1a any-ticker + 10 external companies | 3–4 | name companies (optional) | 1–2 weeks |
| P-S demo / video / site | 3–6 (owner directs) | direction, review | 2–4 weeks, parallel |
| P1 E2 close | 5–8 | G3 ruling (14-day clock), per-fold read | 3–5 weeks |
| P2 simulator | 3–4 | decision A | overlaps P1 |
| P3 signals + mid-caps | 4–6 + GPU nights | decision C, one read per signal family | 4–8 weeks after P2 |
| P4 product surface | 3–4 | one read | 2 weeks |
| P5 paper test | ~1 per quarter | quarterly reads | 8 quarters |
| P6 distribution | legal first | legal review | not scheduled |

First personal-use screen with a full backtested record beside it: roughly 3 months.
First trustworthy paper record: roughly 2 years from the first paper quarter. That is
the honest timeline for "verified to have worked"; anything faster is not verified.
