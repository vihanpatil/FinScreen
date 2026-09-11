# Tech-council advisory — "can it tell me what to invest in?" (convened 2026-09-11 by the main session at the owner's request)

> **ADVISORY ONLY. Nothing here is an owner ruling.** The owner's verbatim prompt (chat, 2026-09-11): *"What are the next moves? Will this for real be usable by me? Can I give it a company and will this engine let me know if I should invest? Can this engine give me top companies to invest? I need you to work hard towards this goal for product. Can you take a look at the overall big picture of this project from end-to-end. I want to make a marketable product. It is aimed for individual use, but should be so useful and amazing, that if one looks at my portfolio, may ask to use as well. I know I cannot compete with huge tech firms and investment banks and their resources, but this should genuinely be useful and give accurate advice. Ensure that this is tested on older company reports which are then verified with real life stock market prices and how they moved up and down throughout. That should test and actually verify that the advice has and would have worked in the past (factor in when reports are reported and if they would help at the proper times). Then once everything is verified to have worked, I can test on modern and upcoming data to see if I make profit. Ask questions like: What have we done so far? What are we building? What is yet to be done? Is this the best possible product? Look through the git repo, ensuring that everything aligns. Be brutally honest and reflect deeply."*
>
> Under H5 §5 kill criterion 5, these words ("marketable product … others may ask to use") are a product-pivot trigger; the council re-convened the same day. The owner's ruling on the charter question is pending and is recorded in HANDOFF §3 when given.

**Decision restated.** Whether this pipeline can become (or be presented as) an engine that tells the owner whether to invest in a company or ranks companies to invest in, and what to run/build/decide next — in direct tension with the owner's own 2026-09-11 identity ruling (HANDOFF §1/§3: "never a score or a recommendation"; distribution not pursued) and the charter (§1: no advice, no live capital, no return claims).

**Brief check.** The owner's message assumes "verified on old reports" implies "profit on modern data." The ratified stopping rule (H5 Option 1, ruled 2026-08-26) explicitly denies that inference — a positive "is a research finding, never a signal to act on." `F5_PLAN.md` §5 recorded KC5 as "not triggered"; that is now stale.

## 1. Can it tell you whether to invest, or rank top companies? Evidence answer: no.

- **E1 (the only completed backtest):** text-vs-numeric IC delta +0.0177 raw (3/6 folds), −0.0097 dedup (2/6), std 0.0677; the two signs disagree, and "fragility, not a direction" is the report's own conclusion (`data/backtest_report.md`). Worse: sorting the 25 stocks by `log_total_assets` alone scored dedup IC 0.224, beating both fitted models (0.097 numeric-only, 0.088 text+numeric) — the models mostly encode company identity (`data/reevaluation_2026-08-25/methodology_audit.md` §0). Per-fold numeric-only IC ranged −0.177 to +0.329.
- **E2 power:** honest MDE at k=33 is 0.030–0.077 measured, 0.038–0.096 in true-construct units, and every implied-floor branch is UNPOWERED at any fold count (`data/f5/status/STEP2_census_e2.md` §C.3, §D). The best case E2 can ever deliver is "a rank-correlation improvement of ~0.03–0.05 with 63-day excess returns across ~100 large caps." A publishable footnote, not an edge you can trade.
- **Labels:** sentiment 86.94% [82.93, 90.13] INDETERMINATE at the 0.85 bar, NEGATIVE recall 0.529 (64/121); guidance passes only on the NONE mass, active precision 68.67% [58.17, 77.55]; red flags 28.0% [23.8, 32.6] student exact-set error over a 42.00% teacher — demoted to exploratory (`data/f4/g2/G2_FINAL_REPORT.md` §1). All model consensus, not human validation.
- **Prices/coverage:** Yahoo keyless endpoint under a robots.txt disallow, split- not dividend-adjusted; 32/244 members have no usable prices (6.35% of member-date cells, 14.0% in 2016); Citigroup 100%, Morgan Stanley 93%, US Bancorp 81% of periodic filings never extracted (census §E).
- **Base rate:** the field's answer to this question in large caps is "barely, and less every year"; a null is the modal outcome (`PRIOR_WORK.md` §1).

**What a ranked list produced today would actually be:** from E1, a ranking that a size sort beats; from E2, nothing — no per-company score is ever written out, and the runners refuse to fit until `G3_RATIFIED.json` exists. A list sorted by raw labels would be a 13–47%-error labeler's opinion about tone, with zero measured predictive validity.

## 2. The validation the owner asked for already exists

`target_e2.py` + `backtest_e2.py` are exactly "old reports → subsequent price moves at the proper time": 63-trading-session forward excess return, window opening at the next trading open after max(filing_date, acceptance time) — necessary because 45% of filings are accepted after 16:00 ET — expanding walk-forward sorted by public date, 33 folds 2018Q1–2026Q1 over 7,405 filing rows / 144 CIKs. E1 answered "no fold-robust text signal." E2 will answer, with a TOST margin ladder {0.03, 0.04, 0.05}: bounded null, above-MDE positive, or unpowered.

**What it does NOT do:** transaction costs, position sizing, turnover, execution, portfolio construction, P&L, Sharpe ("Not a trading simulator"); dividends; delisting returns (right-censored); an S&P benchmark (equal-weight universe average instead); horizons beyond one quarter; any forward/paper run on new data; any per-company output. "Would I make profit" is not a question this harness can ask, by design.

## 3. Product options

**(A) Reading aid (ruled, L2.1 built).** Filing text, labels beside passages, paragraph-level NEW/REMOVED vs the prior same-form filing, PIT fundamentals, non-collapsible disclosure header; L2.2 (any ticker on demand) is 3–4 sessions + 1–2 GPU-h per company-decade. Odds it is genuinely useful to the owner as a reader: high. Odds it tells the owner what to do: zero, by construction.

**(B) Personal screening list.** Defensible only if head 1 shows an above-Δ positive that survives the pre-registered robustness suite and the extension replication AND beats both zero-information benchmarks (size sort 0.224, ticker-mean 0.187 on E1). Even then the ratified rule says: write up, stop. To change that, the owner must explicitly supersede the 2026-08-26 ratification with a new one naming what changed, its MDE, cost and stopping rule (H5 §3). Sharing it ("others may ask") is distribution: recommending securities to others is regulated territory (US: the Investment Advisers Act regime; the publisher's exclusion does not obviously cover personalized per-company verdicts) — a lawyer's question. Personal-capital risk: acting on an IC-0.03 signal after costs is, on the evidence, noise with fees.

**(C) "Should I invest?" verdict.** No honest version exists. A verdict needs an expected-return estimate, and nothing in this repository estimates one. Valuation, price, the owner's portfolio, horizon — none are inputs.

**(D) Genuinely useful and uniquely enabled:** point-in-time diffs and YoY novelty (the "Lazy Prices" family, the one text effect that survived replication per `PRIOR_WORK.md` §1); guidance-direction change with its Rule 9 caveat; newly appearing red-flag categories (exploratory); restatement-visible PIT fundamentals; post-close dating; disclosed-error labels. Commodity tools read filings; none carry error rates or PIT correctness.

## 4. Alignment audit

**Built (strength = discipline):** E1 complete; E2 universe (244 CIKs), ingestion (45,632 filings, 42 GB), H1–H6 hardening, 29,097 sections, 317,081 labels at $0, G2 ruled, F5 data layer + guarded runners + census, G3 packet on disk dated 2026-09-11, L2.1; suite green.
**In progress:** G3 ruling (23 decisions, 14-day clock), L2.2, Track X extension labeling.
**Not done:** G3 → run → per-fold read → F6 → G4; L2.2/L2.3; extension spot-check.

**Disagreements — owner decisions, not bugs:**
1. Owner's goal today (advice, ranking, product, profit test) vs charter §1 and the 2026-09-11 identity ruling. Decide: keep the charter, or re-ratify it in writing (the charter says flag, not build).
2. "Forward test to see if I make profit" vs "no live capital, in any phase."
3. "Personal use" (09-10) vs "marketable … others may use" (09-11).
4. Record gap: HANDOFF §3 has no entry marking G3 packet receipt, so the 14-day clock's start is unrecorded.
5. `HANDOFF.md` §1's opening paragraph still describes "25 mega-caps … trains a screening score"; L2.1 renders NEGATIVE recall 0.529 where the ruling text said 0.487 (the v1.2 adapter's own number; correction recorded).

## 5. Proposed agreement

1. **Run E2 under G3 now.** Record packet receipt; rule the 23 decisions within 14 days; run all three heads; owner reads per-fold tables personally. This is the historical validation the owner asked for, done properly.
2. **Build L2.2 meanwhile** — "give it a company" for any ticker — under the ruled refusals. No ranking/scoring code in any branch.
3. **Decide only after the result** whether a personal screen is even discussable, against the bar in §3(B), pre-committed now. Null or unpowered closes the question: "the advice would not detectably have worked."
4. **Off the table in every branch:** buy/hold/sell verdicts, "top companies," return claims, live capital, distribution without legal review, a licensed price source and charter re-ratification.
5. **Honest forward test, if E2 is positive:** paper only, pre-registered, frozen model and rules, ≥8 quarters (E1's per-fold IC std ~0.17 means single quarters prove nothing), same metrics, published either way. Expect it to be uninformative about profit because costs are unmodeled.
6. **Stated expectation:** the null is the modal result. The durable deliverable is the aid plus a closed, honest study.

**Seats:** CTO, CRO-research, CRO-risk, CFO endorse 1–6. **CEO dissent:** the owner has now twice (08-25, 09-11) stated an investing-product goal; folding that into "run E2" is the council deciding the charter question for the owner. Put the charter re-ratification question to the owner explicitly, before the clock is spent.

**Strongest case against:** the owner is being told to spend ~11–14 agent sessions and 23 rulings on a study whose result cannot serve the stated goal in any branch, then to build a tool that refuses to answer the question. If what the owner wants is help investing, the honest alternative is to stop here, keep the aid, and buy a licensed data feed plus a quant framework — a different project reusing ~70% of this one (methodology audit App. A).

**Kill criteria:** G3 unruled by day 14 → close E2 "not run, documented." Owner asks for a score/rank/price overlay → KC5 re-convene before code. Head 1 positive fails the size/ticker-mean benchmarks → screen question closed. Any charter re-ratification → this advisory is void; re-convene.

**Options:** (1) *Recommended:* points 1–6. (2) CEO's: charter re-ratification session first, then 1–6. (3) Close E2 now, ship the aid only. (4) Re-ratify the charter toward a screen — requires legal review, licensed prices, new stopping rule; council would re-convene to argue against.
