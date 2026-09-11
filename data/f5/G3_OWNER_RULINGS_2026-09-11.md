# Owner rulings, 2026-09-11 — decisions A–F (PRODUCT_PLAN §4) and the 23 G3 decisions

**Provenance.** Given by the owner in chat on 2026-09-11, after the main session
explained every decision in depth the same day. Owner text is quoted **verbatim**
(their capitals, their spelling). Everything else on this page is the main session's
reading of those words, and is labelled as such. Where the owner wrote "you know
best", asked a question, or used a word whose meaning had to be fixed, the reading is
marked **⚠ INTERPRETED — owner confirms** and listed again in §4 so the owner can
confirm all of them with one word or correct any of them.

**Status.** RULINGS RECEIVED. The pre-registration (`G3_PREREGISTRATION.md`) is being
edited from DRAFT to **RATIFICATION-READY**; its sha256 is pinned into
`G3_RATIFIED.json` only when the owner replies **"ratify"** to the §4 list (or corrects
it and then says so). No head runs and no E2 IC exists until then. The 14-day clock
(due 2026-09-25) is running.

The owner's governing statement, given the same day and binding on every reading below
(RESUME_HERE.md top block): *"I NEED THIS TO BE A PERSONAL INVESTMENT TOOL THAT OTHERS
CAN USE. I NEED YOU TO EMPHASIZE TESTING PREVIOUSLY PUBLISHED REPORTS FOR A COMPANY AND
EVALUATING HOW THOSE STOCKS DID FOR THOSE CERTAIN QUARTERS … Was my model correct or
wrong? Do that for many many many companies. THIS IS THE VALUE!"*

---

## 1. Decisions A–F (PRODUCT_PLAN.md §4)

### A — price data source

> **Owner:** "Cheaper feed without identifier."

**Reading.** The "cheaper feed without identifier" in
`data/app/status/PRICE_SOURCE_OPTIONS_2026-09-11.md` is **EODHD "EOD Historical Data —
All World"**: $19.99/month or $199/year, 30+ years of history, delisted names kept to
their delisting date, `adjusted_close` = split + dividend adjusted, Non-Professional
User licence. "Without identifier" means it keys on ticker symbols, not on a permanent
id or the SEC's CIK; the CIK↔ticker mapping is ours to build (current tickers from the
cached `data/raw/company_tickers.json`; historical and delisted tickers from each CIK's
EDGAR submissions record, which lists former names and tickers).

**Consequences.** (1) The purchase is the owner's own act: entering payment details is
not something the main session does. Owner steps: subscribe at eodhd.com to the "EOD
Historical Data — All World" plan; put the token in the environment as
`EODHD_API_TOKEN`; say so in chat. Nothing is fetched before that. (2) The licence
forbids re-displaying or redistributing the data: raw price series from EODHD never
appear on the public site or in git; derived numbers (a company's quarterly excess
return on a scorecard) are a question for the legal reviewer (decision E) before they
go on any public page. (3) P2 (the portfolio simulator) is unblocked in principle and
starts once the token exists. (4) The E2 run itself does **not** wait for this feed
(decision 8 below).

### B — the identity sentence

> **Owner:** "If legality and licensing is harder when involving others, prioritize this
> product for just myself. I wouldn't mind not having anyone else use it but me. I need
> this product to be perfect for me. However, if not much harder to have it available
> for others to use, that would be perfect."

**Reading.** Priority order fixed: **the owner first; others if the legal reviewer
(decision E) finds it "not much harder".** The sentence below is drafted from the
owner's words and is **⚠ INTERPRETED — owner confirms**:

> *FinScreen is a personal investment tool that reads a company's filings and shows,
> beside every call, its historical scorecard — what it would have said from that
> company's past reports and what the stock then did — built to be right for its owner
> first, and opened to others only after a legal review says the extra burden is small.*

This replaces HANDOFF §1's working identity line and PRODUCT_PLAN §4 B's example
sentence. "Perfect for me" is read as the product bar: correct data, disclosed error,
and a scorecard the owner can check against public prices for any company in the run.

### C — mid-cap expansion

> **Owner:** "Decide after E2 result. I would rather not spend many more days of the
> ingestion extraction labeling and spot checking."

**Reading.** Default. No mid-cap arm before the E2 result; when it is discussed, the
cost is stated as a full repeat of ingestion, extraction, labeling and a spot-check,
and the owner has said they would rather not pay it. No further reading needed.

### D — the paper period

> **Owner:** "HISTORICAL TEST IS UTMOST IMPORTANCE! If 8 quarters is not enough, increase
> it. I need this historical test to be used as a real test. All others are synthetic
> and takes me in loops. This is the real world test and would show if everything was
> for naught and we would have to improve drastically, or if we have a real product."

**Reading — ⚠ INTERPRETED — owner confirms.** Two different tests are named here, and
the owner's priority attaches to the first:

1. **The historical test** is head 1's walk-forward under G3: 33 scored quarters
   (2018Q1–2026Q1), 144 companies, real filings and real prices, every model fitted only
   on data public before the quarter it is scored on. **Nothing in it is synthetic.**
   It is the largest historical test the corpus allows: the corpus begins in 2016Q3 and
   the owner declined more ingestion (decision C), so it cannot be lengthened backwards;
   forwards it is bounded by today. It is *the* real-world test the owner describes, and
   it is what the scorecard (decision 3 / §14 of the pre-registration) reports company
   by company. It is ratified as the primary evidence.
2. **The paper period** (P5) is a *forward* test: the frozen model makes dated calls
   on new filings as they arrive, and each quarter of it costs three months of calendar
   time. "If 8 quarters is not enough, increase it" is read as: **8 quarters is the
   minimum; its length is set from the walk-forward's own measured per-quarter
   dispersion so that the paper record reaches a stated detection threshold, and that
   length is written into P5's pre-registration before the paper period starts.** If no
   feasible length reaches the walk-forward's threshold, P5 says so on every paper
   report and is labelled a pipeline check, exactly as PRODUCT_PLAN §4 D's default. The
   earlier "8 quarters detects only 0.17–0.20" figure used E1's 25-company dispersion;
   the E2 universe scores ~130–200 filings a quarter, so the paper period is more
   informative per quarter than that figure implies — but the honest number is
   measured, not asserted, and it comes out of the same run.

### E — legal review before any public tool

> **Owner:** "Create a virtualized lawyer agent. Have them review it before the public
> tool."

**Reading.** Done this turn: `.claude/agents/legal-reviewer.md`. It reviews product
surfaces, site copy, disclosures and data-licence use before any public tool exists,
and answers decision B's question ("how much harder is it to let others use it?").
**Honesty line, recorded here and inside the agent:** it is a language model, not a
licensed attorney; its memo is a checklist, not legal advice; where distribution
beyond the owner is real, its memo says what a human lawyer must confirm. Its first
review (a baseline over what exists today: README, PRODUCT_PLAN, the storyboard, the
report disclosure block, the two data licences) is written to
`data/legal/LEGAL_REVIEW_baseline_2026-09-11.md`. The explainer site and a recorded
demo may be public before that review; a live tool, a waitlist, a ranked list or any
track record may not.

### F — live capital, in the owner's own words

> **Owner:** "Change that line. I NEED LIVE CAPITAL. I do not care if I am changing
> foundational rule, I NEED LIVE CAPITAL. If you think best, change it to my own capital
> after paper period and not automated. You know best."

**Reading.** The charter line "No live capital, in any phase, ever" is **amended by the
owner** as of 2026-09-11. The owner delegated the wording; the line adopted, built from
their words "my own capital after paper period and not automated", is:

> **Live capital: the owner's own capital only, after the pre-registered paper period
> has run and been read, never automated — no component places, queues, or routes a
> trade, and never anyone else's money.**

Applied to HANDOFF §1, README, LIMITATIONS.md, MODEL_CARD.md and the two agent
definitions that police the charter (tech-council, docs-writer). Older documents
(DISCOVERY.md §7, EXPANSION_PLAN.md §1, ROADMAP.md, PRIOR_WORK.md) keep the original
line as history with HANDOFF §1 governing. **⚠ INTERPRETED — owner confirms the
wording** (the substance is the owner's; the sentence is the main session's).

---

## 2. The 23 G3 decisions

Format: owner verbatim → reading → what changes in the pre-registration. "Default" means
the model proposal in `G3_OWNER_PACKET.md` / `F5_PLAN.md` §3, unchanged.

**1 — Benchmark.**
> "Did the stock do well like how my engine and model reported their findings and
> reports. Depending on that, did the stock do well? Also compare to other companies and
> ETFs, etc. You know best."

Reading — **⚠ INTERPRETED**: the first two sentences describe the **scorecard** (see
decision 3): for each past filing, the model's call versus what the stock then did.
"Compare to other companies" is the default benchmark: the equal-weighted average of
the universe's other members over the same 63 sessions, membership-dated, self
excluded. That is ratified as the primary benchmark and as the scorecard's yardstick
("beat or lagged its peers over the next quarter"). "ETFs" needs a price series that
does not exist on disk (only the 244 filers were ever fetched, and no new Yahoo fetch
is made under the robots.txt disallow), so **an ETF comparison (SPY) is pinned as a
reported comparator under P2, from the decision-A feed, never inside the G3 run**. Nothing
about the G3 numbers changes.

**2 — GLD.** > "Default" → excluded from benchmark and IC rows; one sensitivity row.

**3 — Primary metric, specification, the confirmatory text block — and the scorecard.**
> "Default"

Default on every element (dedup Spearman IC delta; PIT-rank spec primary with raw levels
secondary as a pair; 8 legacy + 2 novelty + 16 embedding components confirmatory; 13
red-flag columns exploratory; the without-overlap arm as an evaluation-side restriction
with "any" contamination). **Added under the owner's core value statement, and
superseding the packet's line "nothing REPORTS a per-company score":** head 1 also
reports a **per-company, per-quarter historical scorecard**, pre-registered in a new
§14 with this rule, pinned before the sha:

- rows: the primary arm's deduplicated test rows of every fold (one filing per company
  per 5-day gap), exactly the rows the primary estimand uses;
- "the model" = the confirmatory `text_and_numeric` block's out-of-fold prediction;
  two comparators are printed beside it on the same rows: `numeric_only` (numbers,
  no text) and `size_only` (a model fitted on `log_total_assets` alone — the
  zero-text comparator that beat both fitted models on E1);
- the call: within each test quarter, the prediction's percentile among that quarter's
  scored rows; top third → **"outperform peers"**, bottom third → **"underperform
  peers"**, middle third → **"no call"** (shown, not scored);
- the outcome: the sign of `target_excess_63` — the filing's 63-session forward return
  minus the peer benchmark, window opening at the next session after the filing was
  public (post-close filings open the next morning);
- **correct** = "outperform" and excess > 0, or "underperform" and excess < 0; an
  excess of exactly zero is not correct;
- per company: every scored filing (quarter, form, public date, call, realized excess
  return, right/wrong, for the model and both comparators); a hit rate with a Wilson
  95% interval when the company has at least 6 calls, otherwise rows only; that
  company's base rate (share of its scored rows with positive excess);
- across the universe: the model's hit rate with its interval, the two comparators'
  hit rates, and the sentence that **hit rates are descriptive — the inference is the
  pre-registered IC margin ladder**, printed on every scorecard page;
- written only inside the same guarded run (no separate fit, no forward-looking row,
  never for a company outside the run), after the margin block, to
  `data/f5/head1_scorecard.md` + `.json` and a per-row parquet (git-excluded).

**4 — Fold structure.**
> "Default. However, if you need to increase the quarterly range, you may. I have the
> luxury of having a lot of historical data and if the more you feed, the better the
> prediction, then perfect. However, we must play with the range and not settle for a
> specific quarterly range without REAL DATA TESTING."

Reading — **⚠ INTERPRETED**: primary = default (6-quarter burn-in, 33 folds 2018Q1–2026Q1,
expanding training window — "feeds everything", which is the owner's stated
preference). The data range cannot be increased: the corpus starts 2016Q3, and earlier
data is the ingestion the owner declined under C. "Play with the range … with REAL DATA
TESTING" is honoured by a **pre-registered sensitivity family on the training
window**, run on the real data in the same guarded run and reported beside the primary:
rolling windows of **8 and 16 quarters** (`fold_sensitivity.train_window_quarters =
[8, 16]`), same folds, same purge, same metric. The primary is declared now and is not
chosen after the arms are seen; the arms answer "does more history help?" and are
labelled as sensitivities. The post-2019 sub-window (29 folds, no refit) stays as the
censoring arm.

**5 — Label purge.** > "Default" → purge; no extra buffer.
**6 — Same-day comparisons.** > "Default" → `include_same_day=True` primary, `False` arm beside it.
**7 — Currency conversion.** > "Default" → convert to USD via a dated FX series from the
existing provider, rate as-of the feature date, logged not fatal. As built nothing
converts, and the one non-USD reporter (Enbridge, CAD) enters unconverted; ratifying the
default means the FX ingest + rebuild + test are a **pre-run build item** (or the run
carries the single unconverted CIK as a disclosed exception). Chosen: **disclosed
exception for the G3 run, FX build queued for P2** — because no FX code exists today and
one CIK's float fact does not move a 144-CIK rank correlation; the disclosure travels
with every result. **⚠ INTERPRETED.**

**8 — Price source for the E2 run.**
> "Free version of Yahoo, if Yahoo isn't free."

Reading — **⚠ INTERPRETED**: Yahoo's chart endpoint is keyless and free, so the condition
is satisfied: **ratify** the price series already stored from it (snapshot 2026-08-24,
`data/prices_e2.parquet`, $0) for the E2 run, with the split-adjusted-only caveat and
the 32-of-244 no-price gap disclosed on every result. **No new fetch is made from
Yahoo** (its robots.txt disallows automated access; the stored snapshot is what E2
uses). Prices for anything after the snapshot, and every product use, come from the
decision-A feed.

**9 — 8-K bodies.** > "Default" → exclude the 790 8K_BODY chunks.
**10 — Section masks.** > "Default" → mask.
**11 — Withdrawn guidance.** > "Default" → keep as −1; sensitivity row without it, labelled a 2020Q2 sensitivity.
**12 — Head 2.** > "Default" → `sentiment_negative_share`, positive, sessions [+1, +5] over trailing 60, last event quarter 2026Q2.

**13 — Head 3 exit definition.**
> "What this mean? I want to say default, but do not drop companies still filing a year
> later if they are still public."

Reading: **default, and the owner's condition is already what the default does.** The
screen (`exit_screen = no_in_membership_filing_within_1y`) does not drop any company
from the study. It drops a *stored "exit" row* from the set of positives when the same
company is still filing a year later — because that row was an exchange transfer or a
single-class deregistration, not the company leaving the market. The company stays in
the panel, still scored, as a non-exit. The packet's word "drops" referred to those
mislabelled rows, not to companies. No change.

**14 — Leave-one-company-out.** > "Yes include this." → default: 6 folds, descriptive only.
**15 — Equivalence margin.** > "Default" → ladder {0.03, 0.04, 0.05}, SE ≤ Δ/2.487, else UNPOWERED, serialized before any delta.
**16 — Extension spot-check timing.** > "Default" → run X4 only when a branch consumes the extension arm.

**17 — The stopping rule signature.**
> "I am unsure of what this means. A positive proceeds to the signal program and null
> should not be used as signal. I agree with this."

Reading: the owner's "I agree with this" is the signature on §13, dated 2026-09-11,
with the outcome map as the owner stated it: **above-MDE positive → proceeds to the
signal program (PRODUCT_PLAN P3) under its own pre-registration; bounded null → text
is not used as a signal, the study is written up and closed; UNPOWERED → text is not
used as a signal, and the result is reported as "not tested at the margin", never as
null and never as positive.** The scorecard is reported in every branch, because it
is a description of what happened, not an inference.

**18 — KC1 disposition.** > "Default" → not triggered by the letter; taxonomy stands; the stale-Q4 defect is repaired only if SUE enters a head.
**19 — KC6 carve-out.** > "Default" → the H1 plumbing check may be reproduced before ratification.
**20 — Cross-company attribution.** > "Default" → same-company occurrences only; `cross_cik_share` reported; E1 rule as a named sensitivity.
**21 — Cash-flow ratio period.** > "Default" → duration-matched, disclosed.

**22 — Fundamentals staleness cutoff.**
> "Idk what default is, but I believe you know best. If it is fixed, then good."

Reading: default — keep the 200-day rule and disclose that accepted facts now reach it.
The period-end defect the owner refers to **is fixed** (2026-09-11: duration-aware
resolver in `numeric_features_e2.py`; table rebuilt, sha `07971505…`; censuses
identical; red-teamed). Both parts recorded.

**23 — The two new text features.**
> "Would quarterly filings be able to be judged as well, on top of prior year's filings?
> If not accurate then no, but it would be cool to accumulate and progressively taking
> in history, and adding a quarter would also work for a company with history in this
> FinScreen."

Reading — **⚠ INTERPRETED**: defaults on (a)–(h). The owner's question, answered: **yes,
quarterly filings are already judged** — every 10-Q is in the study, and its novelty is
measured against the same quarter's 10-Q one year earlier (the same-form,
year-over-year rule of default (a)), because a 10-Q against the preceding 10-K compares
a short document to a long one. The "accumulate progressively" idea — each new filing
compared with the one just before it, whatever its form — is added as an **exploratory
second novelty feature** (`novelty_*_seq`, sequential prior filing), reported beside the
confirmatory one and never in the headline; if it adds nothing it is dropped at the
write-up, which is what "if not accurate then no" asks for.

---

## 3. What the rulings change in code and documents (the build spec)

1. **`data/f5/G3_PREREGISTRATION.md`** — every "DRAFT rule" becomes "RATIFIED rule
   (owner 2026-09-11)"; header status RATIFICATION-READY; new **§14 Scorecard** with
   the decision-3 rule verbatim; §1 gains the training-window sensitivity family
   (decision 4); §5 records the ETF comparator as a P2 item; §13 carries the owner's
   signature sentence (decision 17) and the UNPOWERED mapping; §12 ratifies the stored
   Yahoo snapshot (decision 8) and records the Enbridge exception (decision 7); §11
   discloses both. The `json g3-params` block gains:
   ```
   "draft_status": "RATIFICATION-READY 2026-09-11 -- owner rulings applied; sha pinned only on the owner's word",
   "fold_sensitivity": {"train_window_quarters": [8, 16]},
   "scorecard": {
     "arm": "pit_trailing_rank", "eval_set": "dedup",
     "model_block": "text_and_numeric",
     "comparators": ["numeric_only", "size_only"],
     "call_rule": "tercile_within_test_quarter",
     "outcome_col": "target_excess_63",
     "correct_rule": "sign_match_nonzero",
     "min_calls_for_company_hit_rate": 6,
     "ci": "wilson_95"
   },
   "families": { ..., "novelty_sequential_exploratory": true }
   ```
2. **`backtest_e2.py`** — (i) `evaluate_arm` also returns per-row out-of-fold records
   (cik, filing id, form, public date, test quarter, block, prediction, realized
   `target_excess_63`, dedup flag); (ii) a `size_only` block = `[columns.size_col]`,
   fitted like the others; (iii) `build_folds` accepts `train_window_quarters`
   (None = expanding) and `run_head1` runs the sensitivity arms after the primary;
   (iv) a `scorecard_e2.py` module turns the records into the §14 tables, written after
   the margin block; (v) the new keys are **required** in `G3_PARAMS_SCHEMA.json`, with
   `call_rule` / `correct_rule` / `ci` as implemented named rules; (vi) the guard is
   untouched: exit 2 without `G3_RATIFIED.json`, nothing fitted, selftest on the
   synthetic fixture only.
3. **Charter amendment (decision F)** in HANDOFF §1, README, LIMITATIONS.md,
   MODEL_CARD.md, `.claude/agents/tech-council.md`, `.claude/agents/docs-writer.md`.
4. **`.claude/agents/legal-reviewer.md`** created (decision E) and run once as a baseline.
5. **PRODUCT_PLAN.md §4** rows marked RULED with these readings; §1 conditions 1 and 3
   updated; **F5_PLAN.md §3** gains a rulings block; **G3_OWNER_PACKET.md** gets a
   "RULINGS RECEIVED" banner pointing here.

## 4. The owner's confirmation list (one word ratifies all of them)

Reply **"ratify"** and the main session pins sha256(`G3_PREREGISTRATION.md`) into
`G3_RATIFIED.json` and runs the three heads. Or correct any line first.

| # | what was interpreted | the reading adopted |
|---|---|---|
| B | the identity sentence | the one-sentence draft in §1 B |
| D | "if 8 quarters is not enough, increase it" | the walk-forward is the historical test (33 quarters, nothing synthetic); the paper period's length is derived from its measured dispersion, 8 quarters minimum, pre-registered before it starts |
| F | the live-capital wording | "the owner's own capital only, after the paper period, never automated, never anyone else's money" |
| 1 | "compare to other companies and ETFs" | peers = the default universe benchmark, in G3; an ETF comparator under P2 once the decision-A feed exists |
| 3 | the scorecard's "correct" rule | terciles within the quarter; sign of the 63-session excess return; two comparators beside the model; descriptive only |
| 4 | "play with the range" | training-window sensitivity family {8, 16} quarters beside the expanding primary; the data range itself cannot grow |
| 7 | FX mechanism | the one CAD reporter enters unconverted as a disclosed exception in G3; the FX build is queued for P2 |
| 8 | "Free version of Yahoo" | ratify the stored 2026-08-24 snapshot; no new Yahoo fetch |
| 23 | "quarterly filings … accumulate progressively" | 10-Qs already judged year-over-year; a sequential-prior novelty feature added as exploratory |

**Owner's own action items (not the main session's to do):** subscribe to EODHD
"EOD Historical Data — All World" ($19.99/mo or $199/yr) and set `EODHD_API_TOKEN`;
then say so. P2 starts on that word.
