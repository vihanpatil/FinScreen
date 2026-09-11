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

**Owner's core value statement (2026-09-11, verbatim, all caps theirs):** *"I NEED THIS TO BE A PERSONAL INVESTMENT TOOL THAT OTHERS CAN USE. I NEED YOU TO EMPHASIZE TESTING PREVIOUSLY PUBLISHED REPORTS FOR A COMPANY AND EVALUATING HOW THOSE STOCKS DID FOR THOSE CERTAIN QUARTERS (for example, if Google published reports in 2018, what would my model evaluate their stock to do, and historically, what did their stock do? Was my model correct or wrong? Do that for many many many companies. THIS IS THE VALUE!)"* → the
per-company, per-quarter historical scorecard is the centrepiece of P4 and must be a
reported output in the G3 pre-registration (with a pinned rule for "correct"); "others
can use it" makes distribution intended, so the legal review of §1.3 precedes any public
tool and decision E's default no longer applies as written.

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
   *(Main-session condition, like §1; owner may strike.)*
5. **No marketing claim precedes its evidence.** The site may explain what the tool
   does today and what it is testing; it may not state or imply returns until P5 has
   a record. *(Main-session condition, like §1; owner may strike.)*

## 1. Execution conditions (main session; owner may strike in writing)

1. **Paper before live.** Any signal is paper-traded forward, pre-registered, for a
   stated number of quarters before it informs a real position. No live-capital hook
   exists in the code in any phase. **RULED 2026-09-11 (decision F): the charter line is amended — the owner's own
   capital only, after the pre-registered paper period has run and been read, never
   automated, never anyone else's money (HANDOFF §1).**
2. **No claim without out-of-sample evidence.** A recommendation surface shows its own
   backtested and paper record, with costs, or it does not exist.
3. **Distribution requires legal review.** Personal use is the owner's business.
   Letting others use it (or sharing rankings) is regulated territory; a lawyer reviews
   before anyone else touches it. Until then: personal use only. **The repository is
   already public under MIT and the owner links it from a resume, LinkedIn and a
   personal site; the code being public is fine, but a hosted tool strangers can run,
   a waitlist, a ranked watchlist, a backtested track record or a paper log on a public
   page is other people touching it — RULED 2026-09-11 (decisions B and E): the owner
   first; others only if the legal reviewer (`.claude/agents/legal-reviewer.md`;
   baseline memo `data/legal/LEGAL_REVIEW_baseline_2026-09-11.md`) finds it "not much
   harder"; a live box, waitlist, ranked list or track record stays off any public page
   until that review clears it (authoring the site is fine; deploying its live box is
   not).**
4. **No new API spend without owner sign-off** (unchanged). A licensed price feed is
   new recurring spend and is the owner's decision (§4, decision A).
5. **Everything pre-registered.** Signals, costs, universe, rebalance rule, and stopping
   rules are written before the data is seen, as the whole repository has done so far.

## 2. Where we are (what has been done) and why it is the right foundation

| built and verified | why it matters for the goal |
|---|---|
| Point-in-time ingestion of 45,545 stored filings (45,632 enumerated), 244 companies, 2016–2026 — of which the modeling frame is 7,405 filing rows over 144 companies, 119–161 deduplicated rows per quarter; fundamentals that never leak restatements; filing dates that respect after-hours acceptance | this is exactly "factor in when reports are reported" and most retail backtests get it wrong |
| A local labeler (Qwen 2.5 7B student) that reads filings at $0 with measured error | the text signal family, if any, comes from here |
| A walk-forward harness with a 63-session excess-return target, expanding folds, dedup, purge rule, and a pre-registration gate | this is the first version of "verify the advice would have worked" |
| E1 result: no fold-robust text signal on 25 companies | the honest prior |
| Known holes, named: membership requires a tagged public-float value, so an untagged top-K firm never enters; ten companies (seven financials, e.g. Citigroup 100%, Morgan Stanley 93%) had no periodic filings extracted; 31 of the 108 companies whose membership ended have no price history at all while all 136 current members do (survivorship in the price data, outcome-correlated) | these are the resume-matcher risk in this repo, and P2 must count them, never drop them silently |
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
*(The draw is sealed before the run: replacements are allowed only before any company is
attempted, and a replaced company's failure stays in the table. "The owner may add" means
add, never swap out a failure.)*
`ingest_one.py` (ticker → CIK → EDGAR metadata → documents → extract → chunk) and
`label_filing.py` (the same v1.2 adapter, same prompt, a 10-row repro canary against the
G1 eval before the first real label), feeding `report_filing.py`. Acceptance test, the
real-data-first rule made concrete: **10 companies outside the 244-company universe,
chosen by a seeded random draw from the SEC ticker list (the owner may add companies;
no post-hoc replacement), each rendered end to end; every failure recorded in
`data/app/status/L2_2_external_companies.md` with its cause.** Nothing is called done
until that table is honest. This is also the demo's backbone (§P-S).

### P-S — Show: demo, video, website. In parallel from P1a; owner directs.
- **Demo:** a live run — the viewer names a ticker, the tool fetches, labels and
  renders the report in minutes. No curated examples.
- **Video:** a screen-captured narrative of the live run plus the pipeline story
  (storyboard in `site/STORYBOARD.md`; the owner records or approves narration).
- **Website:** a scroll-driven explainer in `site/` (static; authored now, **deployed
  publicly only after decision E** and, for any live box or waitlist, the legal review of
  §1.3): the filing's journey — EDGAR → extraction → the local labeler → point-in-time
  joins → the walk-forward test → the evidence panel — told as a 3D/animated flow the
  viewer scrolls through, in the spirit of the supply-chain site the owner described.
  The owner leads direction. Content rule: §0.5 item 5 (no return claims); the site
  invites interest, it does not give advice; a waitlist is fine, a recommendation is
  not (P6).

### P2 — Build the missing half of the validation: a portfolio simulator. 3–4 sessions.
The harness measures rank correlation. The owner's question is about money. New module
`portfolio_sim.py`, pre-registered. It does NOT consume the head-1 frame (that frame is
per filing, two overlapping 63-session windows per quarter, excess vs the universe); it
builds its own company-quarter panel of absolute total returns from the same point-in-time
membership and dating rules, with a stated filing→quarter collapse rule. Pre-registered
before the first run, and printed beside every headline:
- long-only portfolio rules (equal-weight top decile / top N, quarterly rebalance
  matched to the signal's horizon; monthly only as a named sensitivity), with a
  transaction-cost model pinned per cap band (spread + commission + slippage on
  rebalance day; large-cap costs are not reused for mid-caps), turnover, cash drag,
  and position limits;
- total-return prices including dividends, spin-offs and merger consideration, and
  **delisted-name history with a stated delisting-return convention** (e.g. −30% on a
  distress delisting) and a sensitivity arm — decision A must supply delisted names,
  not only total returns; **every rebalance prints the count of names dropped for
  missing prices, never silently**;
- benchmarks = the equal-weight universe (sector-matched by construction) and a
  sector-neutral comparison; an index total-return series only if decision A licenses
  one — a top-decile-vs-S&P comparison on a sector-balanced universe mostly measures the
  sector tilt;
- **a power statement for the money metrics, pre-registered like KC3's for the IC:**
  over the ~8-year span a Sharpe of 0.5 carries a 95% interval of roughly ±0.7, and a
  max drawdown on a ~14-name portfolio is a single-path number with no interval; both
  print beside the headline;
- outputs per strategy: cumulative return, annualized return, volatility, Sharpe,
  max drawdown, hit rate, per-year table, bootstrap confidence bands, and the
  **"what this would have done"** panel: for every historical recommendation, the
  price path after it at the proper date;
- multiple-testing control, named: the family of every signal ever tested on this
  panel is seeded BEFORE P2 runs — E1's 22 features, H1's T2a (post-earnings drift,
  +0.028 [−0.020, +0.076]) and T2b (12-1 momentum, +0.029, t = 0.73), E2's
  confirmatory block and its three baseline factors already in `numeric_features_e2.py`
  — and every P2/P3 result is reported with a family-wise correction (Holm at minimum;
  a reality-check bootstrap for the strategy family); the log is append-only and
  keyed to the pre-registration sha;
- **the guard travels:** `portfolio_sim.py` (and later `screen.py`) refuse to run
  without a sha-pinned pre-registration, the same pattern as `backtest_e2.py`, so no
  session can re-run until a backtest looks good; the reading aid's refusal tests are
  replaced only by this guard plus the evidence-panel test, never simply deleted.

### P3 — Signal research program, pre-registered. 4–6 sessions + GPU nights.
*(P3 is a new experiment — an "E3" in the ratified stopping rule's terms — and its
pre-registration meets that rule's three conditions: it names what changed since E2, it
states its own detectable effect, cost and stopping rule, and it quotes and explicitly
supersedes the closed paragraph. One markdown per signal and one script until a second
validated signal exists; no registry machinery before then.)*
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
Universe expansion to mid-caps (decision C) is a **reversal** of three rulings
(EXPANSION_PLAN §7 "mid-cap arm: owner ruled no"; the stopping rule's E3 policy; F5_PLAN
§3 "no mid-cap arm"). The existing extension machinery broadens sectors, not the cap
range — `build_universe_e2.py` has no cap band. Honest cost, from this repo's own record
for the core: a new float band and universe build, EDGAR ingestion at the scale of F2
(45,545 filings, 42 GB), extraction and QA at the scale of F3, labeling at the scale of
F4 (317,081 chunks ran continuously for nine nights), and a new owner-adjudicated label
spot-check like G2 (580 rated rows, 59 owner rulings) — weeks of wall clock and several
owner reads, not "3–4 GPU nights".

### P4 — The product surface. 3–4 sessions.
`screen.py` + the reading aid: for a company, the validated signals and their evidence;
a ranked watchlist where every rank carries its backtested track record, costs, and
drawdown beside it; the "what this would have done" panel per recommendation; the
disclosure block (labeler error, data limits, out-of-sample record, paper record).
Nothing is shown without its evidence.

### P5 — Paper forward test, then personal use. 8 quarters minimum, wall-clock.

**Ruled 2026-09-11 (decision D reading, ⚠ owner confirms):** the walk-forward under G3 is
the historical test the owner calls "the real world test"; P5's length is derived from
that run's measured per-quarter dispersion (8 quarters minimum) and pre-registered before
P5 starts; if no feasible length reaches the walk-forward's detection threshold, every
paper report says so and P5 is labelled a pipeline check. Live use afterwards is under
the amended charter line (§1.1).
Pre-registered: frozen model and rules, live-dated recommendations written to an
append-only log before prices are known, scored quarterly against the same metrics,
published either way. The owner's "test on modern data" is this, on paper. Live use
of a signal is the owner's personal decision after the paper record exists.

### P6 — Distribution, only if the owner wants it and only after legal review.
Licensed data, terms-compliant sources, the disclaimer regime a lawyer specifies,
and a re-ratification. Not scheduled.

## 4. Decisions only the owner can make now

**ALL SIX RULED 2026-09-11 — see §4.1 below. The table's "default" column is now the
historical proposal; the ruling governs. Verbatim rulings and the main session's readings:
`data/f5/G3_OWNER_RULINGS_2026-09-11.md` §1.**

| # | decision | why it gates the plan | default |
|---|---|---|---|
| A | **Price data source.** Yahoo's keyless endpoint is under a robots.txt disallow and is split-adjusted only (no dividends, no delisting returns). A terms-compliant source with total returns AND delisted-name history is needed for P2 and for any use beyond research. Options: a paid feed (tens of $/month; the owner approves the spend) or a free tier with acceptable terms. **Note: G3 decision 8 makes Yahoo ratify-or-refuse for the E2 run itself, so A gates P1 as well as P2** | P2 cannot report money-metrics honestly without total returns and delisted names; distribution is impossible on the current source | owner names the budget; candidates with terms in `data/app/status/PRICE_SOURCE_OPTIONS_2026-09-11.md` |
| B | **Charter wording.** Confirm the amended identity line in one sentence, e.g. *"A personal investing research tool: validated screening signals with their measured track record beside them; personal use; distribution only after legal review."* | it replaces two ruled lines and the council's advisory must be answered on the record | as written |
| C | **Universe expansion to mid-caps** — a reversal of "mid-cap arm: owner ruled no" (EXPANSION_PLAN §7) and of the stopping rule's E3 policy, at the cost of a repeat of F2 + F3 + F4 + G2 (see P3) | where a text edge is more plausible; without it the study stays a large-cap study | not before E2 reports; costed and pre-registered as an E3 first |
| D | **What the paper period is for, and how long.** Eight quarterly observations at E1's measured per-fold dispersion (std 0.17) detect only an IC of about 0.17–0.20, three to six times coarser than E2's own threshold; no feasible paper period can confirm an effect of E2's size. The paper test's honest job is to catch a broken pipeline and gross failure, not to verify an edge | so the owner does not mistake "8 quarters of paper" for verification | 8 quarters, defined as a pipeline check, stated as such on every paper report |
| E | **Repository visibility and public-site scope.** The repo is public under MIT (fine for code). A hosted "name a company" box, a waitlist, a ranked watchlist, a backtested track record or a paper log on a public page is other people using the tool — the §1.3 legal line. Options: keep the code public and deploy only an explainer site with a recorded demo (no live box, no waitlist) until legal review; or make the repo private until then | this is the distribution question, and it is already live | explainer + recorded demo public; live box, waitlist, track record and paper log withheld until legal review |
| F | **Live capital, in the owner's own words.** The charter says "No live capital, in any phase, ever"; P5 would let the owner act personally after a paper period. Only the owner can narrow that line | it is the charter's most consequential non-goal | as the owner writes it; until then the charter line stands |

### 4.1 Rulings received 2026-09-11 (owner verbatim → reading)

| # | owner (verbatim) | reading adopted | status |
|---|---|---|---|
| A | "Cheaper feed without identifier." | EODHD "EOD Historical Data — All World" ($19.99/mo or $199/yr; ticker-keyed, CIK mapping ours; Non-Professional licence: no display/redistribution). The owner subscribes and sets `EODHD_API_TOKEN`; nothing is fetched before that; P2 starts on that word. The E2 run does not wait for it (G3 decision 8) | RULED; owner action pending |
| B | "If legality and licensing is harder when involving others, prioritize this product for just myself. … if not much harder to have it available for others to use, that would be perfect." | Owner first; others if the legal reviewer finds it "not much harder". Identity sentence drafted from these words (HANDOFF §1), pending the owner's one-word confirmation | RULED; sentence ⚠ to confirm |
| C | "Decide after E2 result. I would rather not spend many more days of the ingestion extraction labeling and spot checking." | Default: no mid-cap arm before the E2 result; its cost is a full F2+F3+F4+G2 repeat | RULED |
| D | "HISTORICAL TEST IS UTMOST IMPORTANCE! If 8 quarters is not enough, increase it. I need this historical test to be used as a real test. All others are synthetic and takes me in loops." | The historical test = head 1's 33-quarter walk-forward on real filings and real prices (nothing synthetic), reported per company by the scorecard; it is the primary evidence. The paper period (P5) is forward calendar time: 8 quarters minimum, its length derived from the walk-forward's measured per-quarter dispersion and written into P5's pre-registration before it starts; if no feasible length reaches the threshold, every paper report says so | RULED; reading ⚠ to confirm |
| E | "Create a virtualized lawyer agent. Have them review it before the public tool." | `.claude/agents/legal-reviewer.md` created (a language model, not a licensed attorney — stated on every memo); baseline memo `data/legal/LEGAL_REVIEW_baseline_2026-09-11.md`; explainer site + recorded demo may be public; live box, waitlist, ranked list, track record wait on its review | RULED; done |
| F | "Change that line. I NEED LIVE CAPITAL. … If you think best, change it to my own capital after paper period and not automated. You know best." | Charter line amended (HANDOFF §1, README, LIMITATIONS, MODEL_CARD): the owner's own capital only, after the pre-registered paper period has run and been read, never automated, never anyone else's money | RULED; wording ⚠ to confirm |

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
- **Retired assumptions (as ruled):** "never a score" (personal use). **Pending the
  owner's words, not retired by this document:** "never distribution" (decision E) and
  "no live capital, ever" (decision F). EXPANSION_PLAN §7 also lists paper trading as out
  of scope; P5 reverses that and is part of the same ruling.

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

First personal-use screen with a full backtested record beside it: 9–15 weeks on the
serial path (P1 3–5 weeks, P3 4–8, P4 2), assuming a prompt G3 ruling and no
null-triggered redesign. **A paper period does not verify an edge of this size at any
feasible length (decision D); "verified to have worked" can only ever mean the
walk-forward record with its confidence intervals, and the paper period is the check
that the live pipeline behaves like the backtest.**
