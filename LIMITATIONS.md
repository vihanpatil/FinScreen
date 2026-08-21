# FinScreen — Known Limitations

**Written 2026-08-18.** This is the honest-limitations write-up: everything
known to be wrong, uncertain, or unvalidated about FinScreen's data, labels,
and (eventually) results, in one place, in plain language.

It assembles only what is **final** as of the write date. The Phase D
fine-tune has not happened and carries an explicit `TODO` placeholder below
rather than an estimate. The Phase C walk-forward backtest **has** run —
§4.1 points at its reports but deliberately restates none of their numbers,
because the owner reads those gate files personally before anything is
concluded from them. Nothing in this document is extrapolated: every number
is quoted from the artifact that produced it, with the measurement method
stated next to it.

Sources are named inline. Where another file is the canonical record for a
limitation (notably `RED_FLAGS_LIMITATION.md`), this document cites it
rather than restating numbers independently, so the two can never drift.

---

## 0. Non-goals — read these before anything else

These are contractual, not aspirational, and they govern every other
statement in this repo (`DISCOVERY.md` §7; restated in `HANDOFF.md` §1):

- **Not a trading bot.** No component of this system places, queues, or
  recommends executing any trade.
- **Not investment advice.** A screening score is a research signal, never
  a recommendation to buy, hold, or sell anything.
- **No live capital**, ever, in any phase of this project.
- **No return guarantees**, expected-performance claims, or "beats the
  market" language anywhere in code, docs, README, or model card. Every
  performance number is reported with exactly how it was measured, next to
  it, every time.

FinScreen is a solo-owner research tool operating on a frozen historical
snapshot of SEC filings for 25 mega-cap companies. It has no users, no
deployment, no live data feed, and no money attached to it.

---

## 1. How to read the numbers in this document

Every rate below is stated with (a) what was measured, (b) on what
population, and (c) how. Two conventions matter especially:

- **"Agreement" is not accuracy.** The label-quality rates in §2 measure
  agreement between raters on a 400-chunk sample. See §2.3 for exactly who
  those raters were — most of them were models, not the owner.
- **Pooled sample rates are not corpus base rates.** The 400-chunk sample
  deliberately oversamples rare and contested categories. See §2.4.

---

## 2. Label quality

### 2.1 `red_flags` labels fail the project's own quality bar

**`red_flags` agreement is 63.4% (95% Wilson CI [58.6%, 68.0%]), which
fails the project's pre-registered 0.70 lower-bound bar — the *upper* bound
is below the bar, so this is not a borderline miss.** Measured over 399
evaluable chunks of the 400-chunk spot-check sample (`spotcheck/sample_400.parquet`),
scored by `spotcheck/compute_agreement.py` against Wilson 95% confidence
intervals; the full report is `spotcheck/agreement_report.txt`. Rater
composition for that number is in §2.3 — it is model-consensus agreement,
not human validation.

**63.4% is an EXACT-SET-MATCH rate.** One added, dropped, or re-modalized
category on a chunk scores that whole chunk as a disagreement, so the
number is **not comparable to the single-value rates for sentiment,
guidance, or distress printed beside it**. Wherever it travels, the
exact-set basis travels with it (`RED_FLAGS_LIMITATION.md`, binding
implication #1).

Restated as an error rate: **146 of 399 stored red-flag sets (36.6%) were
ruled incorrect** under the adjudication protocol. That error decomposes
into three modes (category-level corrections across those 146 chunks):

| Error mode | Corrections | Largest contributors |
|---|---|---|
| Spurious flag (text does not assert it) | 61 | LEGAL_REGULATORY_ACTION 21, MARGIN_COST_PRESSURE 20 |
| Missed flag (text asserts it, label omits it) | 76 | MARGIN_COST_PRESSURE 23, SUPPLY_INPUT_CONSTRAINT 15 |
| Right category, wrong modality | 43 | LEGAL_REGULATORY_ACTION 26, MARGIN_COST_PRESSURE 13 |

`RED_FLAGS_LIMITATION.md` (repo root) is the **canonical disposition
record** for this failure — per-category verdicts, the full decomposition,
the owner-ratified ambiguity principles behind it, and four binding
constraints on feature engineering. Every rate in this section is **quoted
from that file**, not independently re-derived here; cite it rather than
recomputing these numbers anywhere else.

Where it fails hardest, same measurement: **RISK_FACTORS sections, 59.2%
[50.2, 67.5]** (n=120 field-cases — for RISK_FACTORS this is already a
red_flags-only rate, since the applicability matrix never asks that section
type for sentiment or guidance).

By tier, **read the red-flags-only column, not the pooled one** (both from
`spotcheck/combined_judgments.csv`; canonical table in
`RED_FLAGS_LIMITATION.md` / `HANDOFF.md` §2a):

| Tier | red_flags only (agree/n) | All headline fields pooled |
|---|---|---|
| A — exhaustive distress positives | 96/162 = **59.3%** [51.6, 66.5] | 76.9% |
| B — thin/rare-category oversample | 98/141 = **69.5%** [61.5, 76.5] | 83.4% |
| C — base-rate-representative fill | 27/36 = **75.0%** [58.9, 86.2] | 84.3% |
| D — config-disagreement set | 32/60 = **53.3%** [40.9, 65.4] | 71.2% |

The pooled column (what `spotcheck/agreement_report.txt` Section 3 prints)
folds sentiment and guidance in alongside red_flags, diluting the failure
by roughly 18 points per tier **and inverting the ordering**: pooled, Tier D
looks like the floor at 71.2%; red-flags-only, **Tier D (53.3%) and Tier A
(59.3%) both sit below that pooled "worst" figure**. Do not quote the
pooled per-tier numbers for a red-flag claim.

**Practical consequence:** any feature derived from `red_flags` inherits a
measured error rate that must be reported **with its basis attached**,
next to any red-flag feature-importance or ablation claim. The three rates
and what each measures:

| Error rate | Basis | Use it for |
|---|---|---|
| **36.6%** (146/399) | Sample-pooled, exact-set | "How often was a chunk's full flag set wrong *in this deliberately hard sample*" — not corpus-representative |
| **25.0%** (9/36, [58.9, 86.2] on agreement) | Tier C, exact-set | **The corpus-wide figure to carry forward** (§2.4), wide CI and all |
| **7.5%** (180/2,394) | Per-category | "How often was any single category decision wrong" — 399 chunks × 6 categories |

Modality splits (REALIZED vs. HYPOTHETICAL) are the least reliable
dimension of all, and stored REALIZED counts for legal/regulatory exposure
are biased **low**.

The three other headline categories cleared the bar on the same
measurement: sentiment 94.6% [91.3, 96.7] (n=279), guidance_direction
95.2% [90.4, 97.6] (n=145), distress_tier 94.2% [91.5, 96.1] (n=399,
reported separately per `labeling_rubric.md` §5 and excluded from every
headline number).

### 2.2 Red-flag labels are also sensitive to how the labeling model was configured

**Comparing the same 4,219 chunks across two full-corpus labeling passes —
the original adaptive-thinking pass vs. the corrected
`thinking=disabled, max_tokens=4000` pass — `red_flags` changed on 935 of
4,219 chunks (22.2%).** The comparison set is
`data/labels_pre_relabel.parquet` vs. `data/labels.parquet`; recorded in
`DISCOVERY.md` §6's risk register and `data/full_run_report.md`'s FINAL
section, and carried as the headline limitation in `HANDOFF.md` §2.

Same comparison, other fields: `sentiment` 3.6% (119/3,280),
`guidance_direction` 0.9% (6/677), `distress_tier` 0.7% (29/4,219). Red
flags are the outlier by an order of magnitude.

The direction of the difference is known and systematic — the retained
config flags **more** in every category: LEGAL_REGULATORY_ACTION +211,
MARGIN_COST_PRESSURE +203, DEMAND_WEAKNESS +138, IMPAIRMENT_WRITEDOWN +51,
SUPPLY_INPUT_CONSTRAINT +35, TRADE_POLICY_EXPOSURE +27.

**Read §2.1 and §2.2 together, because they agree:** red-flag labeling sits
closest to the rubric's ambiguity boundaries, so it is the least stable
category under any perturbation — of configuration *or* of rater. Red-flag
counts are meaningfully a function of *how the labeling model was asked*,
not only of *what the filing says*. Treat them as directional, not as
precise counts.

Related, and not ruled out: this instability was **invisible at canary
scale**. The 50-chunk canary runs validated request mechanics, not
distributional stability; the 22.2% only appeared when two full-corpus
passes were compared (`HANDOFF.md` §4).

### 2.3 What the agreement rates actually measure — and what they do not

**The rates in §2.1 measure model-consensus agreement. They are NOT human
validation of ground truth.** This is an owner-ratified epistemic
requirement (`HANDOFF.md` §3, 2026-08-18 adjudication-delegation entry) and
must be restated wherever these numbers appear.

The protocol that produced them:

1. A blind second-rater model (`label-auditor`, opus) independently
   re-judged all 400 sample chunks before seeing the stored label.
2. Where the second rater disagreed with the stored label, a third-rater
   model (`label-adjudicator`, sees both prior positions) ruled on rubric
   merits.
3. The owner personally ruled on a shortlist.

Of the **1,222 total (chunk, field) judgments** in
`spotcheck/combined_judgments.csv`:

| Source | Judgments | What it means |
|---|---|---|
| `model-auditor` | 1,023 | Two models independently agreed; no human looked at it |
| `model-adjudicator` | 95 | A third model resolved a two-rater dispute; no human looked at it |
| `owner` | **104** | The owner's own judgment |

**The owner personally ruled 104 of 1,222 judgments** — 85 by block
ratification of the adjudicator's medium-or-higher-confidence rulings, and
19 explicitly (the 11 high-stakes distress chunks plus an 8-case final
verification round). That is the entire human input. No document derived
from this work may imply more human validation than that, and no model
verdict may be presented as the owner's own (`HANDOFF.md` §7).

Human judgment here was deliberately *concentrated* where it was most
informative (high-stakes and rubric-underdetermined cases), not spread
evenly — which is a reasonable design, and also means the 104 owner rows
are not a random sample of the corpus.

Per-category provenance mix (from `spotcheck/agreement_report.txt`'s
provenance appendix): sentiment 263 auditor / 10 adjudicator / 6 owner;
guidance_direction 137 / 3 / 5; red_flags 251 / 74 / 74; distress_tier
372 / 8 / 19.

### 2.4 The pooled agreement rates are not base-rate representative

The 400-chunk sample is tiered on purpose: Tier A = 162 (every distress
positive), Tier B = 142 (oversample of thin/rare categories), Tier D = 60
(chunks drawn from the config-disagreement set, judged blind), Tier C = 36
(proportional stratified random fill). Built by `spotcheck/build_sample.py`.

**Any rate pooled across all four tiers therefore overweights rare and
contested text and is not an estimate of the corpus's true base-rate
agreement.** Tier C is the only base-rate-representative slice. It reports
**84.3% [74.0, 91.0]** pooled across headline fields (sentiment + guidance
+ red_flags together) over 70 field-cases — which is **not** a
red_flags-specific number.

The base-rate-representative, **red_flags-specific** rate has been computed
and is canonical: **Tier C red-flags-only = 27/36 = 75.0% agreement /
25.0% exact-set error, 95% Wilson CI [58.9, 86.2]**
(`RED_FLAGS_LIMITATION.md`; `HANDOFF.md` §2a). **This is the corpus-wide
red-flag error rate to carry forward — ~25%, not the 36.6% sample-pooled
figure**, which `RED_FLAGS_LIMITATION.md` says overstates it by roughly 11
points. The n is 36 and the interval is wide, so quote it with the CI
attached, never as a point estimate. The "fails the 0.70 bar" verdict
survives either way: Tier C's lower bound is 58.9%.

### 2.5 Every REALIZED distress class is now empty or near-empty

- **`LIQUIDITY_STRESS` / REALIZED: n=0 corpus-wide.** The corpus stored 9
  such labels; the second rater disputed 8 of 9, the third rater sided with
  the second rater on all of them, and the owner then explicitly ruled all
  9 incorrect (`HANDOFF.md` §3, 2026-08-18 bulk-ratification entry; owner
  principle P2: affirmed adequacy defeats the flag, and a working-capital
  deficit alone is not distress). Five of the nine were the **same
  recurring PG "working-capital deficit + affirmed adequacy" disclosure
  across successive quarters** — not one deduplicated passage; each quarter
  carries its own figure ($10.2B / $12.8B / $10.1B / $8.2B / $9.0B).
- **`GOING_CONCERN`: n=0 by construction.** The universe is 25
  currently-healthy mega-caps; zero is the expected result, not a data
  problem.
- **`ACCOUNTING_RESTATEMENT`: n=2**, both HYPOTHETICAL-framed risk-factor
  text. Both labels survived adjudication.

Corpus distress-tier positives total 162: LIQUIDITY_STRESS/HYPOTHETICAL
151, LIQUIDITY_STRESS/REALIZED 9 (all now ruled incorrect),
ACCOUNTING_RESTATEMENT/HYPOTHETICAL 2, GOING_CONCERN 0.

**Consequence:** there is no realized-distress coverage in this dataset. Do
not engineer distress-REALIZED features — they are known-empty. The
distress tier stays excluded from fine-tuning targets and from every
headline eval metric, enforced in code
(`finetune/prepare_dataset.py`, `finetune/eval.py`,
`spotcheck/compute_agreement.py`'s `assert_distress_excluded_from_headline()`).

Note the asymmetry this creates: `distress_tier` as a *category* passed the
agreement bar at 94.2%, while one of its classes was simultaneously ruled
entirely wrong. The category rate is dominated by correct negatives.

### 2.6 Two categories cannot be evaluated at all

- **`guidance_direction = WITHDRAWN`: n=1 corpus-wide.** One example. It
  sits in the training split, not the eval split, by necessity. No
  per-class metric on it means anything. (The owner explicitly ruled to
  keep this single label during the final adjudication round.)
- **`section_type = 8K_BODY`: n=8 corpus-wide, from only 2 of 25 tickers
  (BAC, CVX).** Zero training examples, 8 eval examples. Not a
  meaningfully learnable or evaluable section type at this corpus size.

Both are excluded from headline eval tables (`REDTEAM_WEEK3.md` finding #7;
standing rule, `HANDOFF.md` §7). Any table that reports a number for either
must say "insufficient support" rather than folding it into an aggregate
that implies it was actually evaluated.

### 2.7 One chunk has no labels at all

`CHK-8e69547e0900a8dd` (`section_type=MDA`) is excluded: the labeling model
issued a genuine mid-stream safety refusal (`stop_reason=refusal`,
`stop_details.category=bio`, 293 output tokens emitted), confirmed by a
direct read-only query of the batch result rather than inferred from the
stored parquet columns. It is excluded by predicate, not deleted, and its 3
otherwise-applicable spot-check fields are excluded from agreement rates
rather than imputed. So the corpus is 6,747 rows, 6,746 labeled (99.99%).

Note for anyone re-reading the audit trail: `REDTEAM_WEEK3.md` finding #1
originally called this a truncation, on reasonable evidence — the stored
columns show an unterminated JSON string and no `stop_reason` field exists
in that schema. That finding carries an owner-verified correction inline.

### 2.8 The labels are frozen, and the known fix has not been applied

`data/labels.parquet` **stays frozen** (owner ruling, 2026-08-18). The
spot-check corrections live in the spot-check record only — they were not
written back into the label file. Downstream work consumes the frozen
corpus **with the documented error rates above**.

A rubric revision addressing the §2.1 failure modes is drafted in
`RED_FLAGS_LIMITATION.md` but is **pending owner ratification and NOT
applied**. Even if ratified, **no re-label will occur**: Anthropic API
spend is frozen at $33.51 total with a hard no-further-spend rule
(`HANDOFF.md` §5). The revision exists so that any *future* labeling does
not re-inherit these ambiguities — not as a fix to the current data.

---

## 3. Corpus and data

### 3.1 Survivorship bias in the 25-company universe

**The universe is 25 large-caps chosen because they are large and prominent
*today*.** A company that was equally prominent in 2023–2024 but has since
been acquired, delisted, or gone through distress does not appear here, by
construction. This bias is inherited by every downstream result trained or
evaluated on this universe.

Stated plainly in `INGESTION_NOTES.md` ("Universe: how it was chosen") as a
deliberate convenience choice, flagged in `DISCOVERY.md` §5 and carried in
§6's risk register as documented-not-solved. It is **not** solved anywhere
in this project. A screening tool validated only on survivors will look
better than one validated on the full historical cross-section, and nothing
here quantifies how much better.

Related and unquantified: `GOING_CONCERN` n=0 (§2.5) is a direct
consequence of the same selection — the dataset contains no examples of the
distress the tool nominally screens for.

### 3.2 Everything here is a frozen snapshot, not a live system

Keeping the model current is an explicit non-goal (`DISCOVERY.md` §6, "data
drift"). Concretely, what is frozen:

- **Filings:** 12 quarters back from 2026-08-10, i.e. `filing_date >=
  2023-08-14`. 1,271 filings; 884 extracted sections in
  `data/filings.parquet`.
- **Labels:** `data/labels.parquet`, 6,747 rows, one uniform config, frozen
  (§2.8). No further labeling is possible under the spend freeze.
- **Fundamentals:** `data/fundamentals.parquet`, 42,158 rows, filed dates
  2009 → 2026-08-10.
- **Prices:** `data/prices.parquet`, 271,372 rows, fetched 2026-08-18.

Any result derived from these is dated to this snapshot and says nothing
about periods after it. Re-running the pipeline later against fresh EDGAR
data would produce a different corpus, and the label set could not be
regenerated to match it.

### 3.3 The labeling model could often tell which company it was reading

The rubric's structural mitigation works: ticker, company name, and filing
date are **never** injected into a labeling request, and `section_type` is
never named as literal prompt text (rubric v1.1, verified by grep across
all 6,747 requests — 0 hits for dates, 0 for `section_type`).

**But the filing text self-identifies its own company in a substantial
share of chunks, and that channel is open.** Two independent measurements
against `data/labeling_corpus.parquet` (`REDTEAM_WEEK3.md` finding #2 —
both are cited here so no reader picks one and assumes the other was
wrong):

| Method | Overall | By section |
|---|---|---|
| **Strict** (full/near-full legal name as a phrase; exact whole-word ticker, excluding ambiguous 1–2-letter tickers V/MA/GS) | **26.8%** | 8K_BODY 75.0, EX99_PRESS_RELEASE 59.2, MDA 19.9, RISK_FACTORS 19.9 |
| **Loose** (company-name first token or bare ticker anywhere) | **46.0%** | 8K_BODY 75.0, EX99_PRESS_RELEASE 73.5, MDA 42.3, RISK_FACTORS 34.9 |

The loose method is knowingly over-permissive ("Bank", "Home"); the strict
method is the more defensible figure. Both are meaningfully above the ~19%
/ 48% originally estimated in `DISCOVERY.md`, which now carries both
measurements as an amendment to §5.

**What this risks:** a labeling model that recognizes the company could, in
principle, use post-training knowledge of what happened to that company
next, instead of judging what the text says — a look-ahead-bias channel.
The only countermeasure is a prompt instruction not to use recognized
identity (`labeling_rubric.md` §0). That is a real safeguard but not a
structural guarantee the way withholding the field is. Full redaction of
identifying language was considered and deliberately not attempted for the
MVP.

**What is not known:** how often the labeling model actually *exploited*
the channel. The red-team review could bound how often the channel exists,
not how often it was used, and said so explicitly. This is a documented
open risk, not a solved problem.

### 3.4 Nearly half of Risk Factors sections have no labeled text of their own

`chunk.py` deduplicates prose paragraphs corpus-wide and packs each unique
paragraph into a labeling window only at its **earliest ("home")**
occurrence. Verified consequence (`REDTEAM_WEEK3.md` finding #3, joined
from `data/filings.parquet` + `data/labeling_corpus.parquet`):

```
total filing-sections:                884
sections with >=1 home chunk:         734
sections with ZERO home chunks:       150  (17.0%)
  RISK_FACTORS:        118/254 = 46.5%
  8K_BODY:               1/4   = 25.0%
  EX99_PRESS_RELEASE:   29/327 =  8.9%
  MDA:                   2/299 =  0.7%
```

This is **not** a look-ahead leak — home is always the earliest occurrence
(verified: 0 mismatches across all 5,029 multi-occurrence paragraphs), so
labeled text never post-dates a filing it recurs in.

It **is** a coverage bias. The owner-ratified mitigation (2026-08-11,
`DISCOVERY.md` §5) is every-occurrence attribution: a paragraph's label
attaches to *every* filing it appears in, each with that filing's own real
filing date, via `data/paragraph_occurrence_map.parquet` — **28,504
deduplicated (canonical) paragraphs, carrying 42,577 total occurrences in
list columns. Explode before joining**; treating the row count as an
occurrence count under-counts attributions 42,577 → 28,504. That decision
is binding on `features.py`, which implements it — see §4.1.

**The failure mode to watch for:** a naive join on `home_accession_number` /
`home_filing_date` would make ~46% of Risk Factors sections silently show
"no risk-factors signal," which is easily misread (or imputed) as "no red
flags," when the correct reading is "same boilerplate as the prior filing."

### 3.5 Price data is split-adjusted but NOT dividend-adjusted, and the source is a caveat

**Adjustment.** `data/prices.parquet` stores Yahoo's raw OHLC, which is
split-adjusted only. Verified against NVDA's real 10-for-1 split (effective
2024-06-10): the close series is continuous across the split date
($122.44 → $120.99 → $120.89 → $121.79 → $120.91), max single-day |return|
in that window is 5.2%, and Yahoo's own `events.splits` payload confirms
the 10:1 ratio. Yahoo's dividend-adjusted `adjclose` is deliberately **not**
stored, to keep open/high/low/close internally consistent.
(`data/PRICES_NOTES.md` §2.)

**Consequence for the backtest target, stated plainly.** The ratified target
is forward *excess* return — one stock's return minus the 25-stock universe
average, both from these dividend-excluded closes. Because every name in the
average also excludes dividends, most of the systematic price-vs-total-return
gap cancels in the subtraction. **It does not cancel cross-sectional
differences in dividend yield.** This universe spans very different yield
profiles (XOM, CVX, JNJ, PG, KO, MCD vs. AAPL, GOOGL, NVDA), so a
high-yield name carries a small systematic *negative* bias in its measured
excess return, and a low-yield name a small positive one, entirely
independent of anything in its filings. The magnitude of this bias has not
been quantified.

**Source caveat — open owner-attention item.** The ratified example source
(Stooq) turned out to be bot-gated (JavaScript proof-of-work challenge;
`robots.txt` says `Disallow: /` for all non-search-engine agents). The
ingestion agent correctly refused to build a bypass and fell back to Yahoo
Finance's free keyless chart endpoint (the same one `yfinance` uses) for all
25 tickers, at 25 total requests, cached thereafter. **Yahoo's `robots.txt`
also disallows automated access and Yahoo publishes no terms authorizing
this use.** This is disclosed, not resolved — it is the owner's call whether
to accept it as a documented exception or swap in a licensed feed. The
parquet schema carries a `source` column, so swapping providers costs a
re-ingest and nothing else. (`data/PRICES_NOTES.md` §1; `HANDOFF.md` §2.)

**Known coverage gap:** one missing day, HD 2026-07-21 — the upstream
response carries null OHLC for it (verified against the raw cached JSON —
not a parsing bug). **In `data/prices.parquet` the row is absent, not
present-with-NaN**: the window holds 930 trading days, HD has 929 of them,
and there are **zero null-close rows anywhere in the file**. A consumer
guarding with `.isna()` will not catch this; guard on missing dates per
ticker instead.

### 3.6 Numeric fundamentals have structural gaps and tag migrations

From the validated ingestion of `data/fundamentals.parquet` (42,158 rows,
25 companies, 13 concepts; 40 WARN / 0 FATAL across **five** WARN
categories, all empirically verified — `concept_structurally_absent` 20,
`revenue_alias_consistency` 8, `concept_tag_migrated_before_window` 7,
`concept_quarterly_coverage_midwindow_migration` 4,
`concept_quarterly_coverage_partial` 1; `HANDOFF.md` §2a, "Binding traps
for `features.py`"):

- **`OperatingIncomeLoss` has zero in-window coverage for 10 of 25
  companies.** Nine never report the tag at all (BAC, COP, CVX, GS, JPM,
  MRK, OXY, PFE, XOM); JNJ's last one predates the window
  (`concept_tag_migrated_before_window`, period_end 2015-03-29), which is
  the tenth. SLB is a separate case — *partial* in-window coverage (3/12
  quarters), not absent. Any feature assuming this concept exists
  universally silently loses 40% of the universe.
- **Tags migrate mid-window:** MA and OXY `NetIncomeLoss` → `ProfitLoss`;
  SLB `OperatingIncomeLoss` → `ProfitLoss` (mid-2024); cash-tag migrations
  post-ASU-2016-18; equity-tag variants for V and UNH. Features must use
  alias/migration families, not single tags — **but the alternate tags are
  documented, not ingested.** `ProfitLoss` is absent from
  `data/fundamentals.parquet`'s 13 concepts and from `CONCEPTS` in
  `ingest_fundamentals.py`, so that parquet alone cannot satisfy the rule.
  Reaching them requires either a re-ingest (free, EDGAR-only, no API
  spend) or `features.py`'s `load_supplemental_alt_tags()` route, which
  reads the already-cached `data/raw/companyfacts/*.json` offline. Values
  obtained that way are **outside** the validated WARN table above.
- **MA's only in-window `NetIncomeLoss` rows are DEF 14A proxy
  compensation-table disclosures** — not financial statements. Form
  filtering (10-K/10-Q/8-K only) is required, not optional.
- **Revenue aliases are not one-per-bank.**
  `RevenuesNetOfInterestExpense` is used by **GS (172 rows) *and* JPM
  (149 rows)**, and JPM additionally reports `Revenues` in-window, carrying
  a `revenue_alias_consistency` WARN that reads "Multiple revenue aliases
  reported in-window". **Eight tickers carry a multi-alias WARN.** Reconcile
  aliases per ticker; never special-case GS (`HANDOFF.md` §2a trap (d)).
- **Restatements are preserved as separate rows: 9,705 facts are reported
  by more than one filing** (grouping key: `ticker` + `concept` +
  `period_end`, counting distinct `accession_number`; nearby keys give
  materially different answers, so the key travels with the number).
  Point-in-time correctness therefore depends on using
  `pit.value_as_of()` (latest-filed-as-of semantics) rather than the most
  recent value; using restated figures as if they were knowable at the
  original filing date is one of the look-ahead-bias modes `DISCOVERY.md`
  §5 names explicitly.

### 3.7 Third-party dataset licensing (Financial PhraseBank / FiQA)

`DISCOVERY.md` §1 names Financial PhraseBank and FiQA as an off-the-shelf
sentiment sanity-check reference. **Financial PhraseBank's license is
reported inconsistently across mirrors — CC-BY-NC-SA-3.0 on the canonical
HuggingFace page vs. CC0 on a Kaggle repackaging. This project treats it as
NC-licensed (the more restrictive, canonical reading); FiQA carries the same
caveat.**

That is fine for a non-commercial personal research project, and is why the
risk register (`DISCOVERY.md` §6) constrains them to eval/sanity-check
reference use only — never redistributed, never used to train a model
intended for anything beyond this project.

Two honest qualifications: (a) neither dataset is ingested by any artifact
currently in this repo — the constraint is forward-looking, not a
description of something that happened; (b) the license discrepancy was
never resolved against the canonical license page (`DISCOVERY.md`'s own
open item flags this). **A commercial derivative of anything touching these
datasets would need re-licensing or a different labeled set**, and the
license question would need to be settled first.

---

## 4. Modeling and evaluation

### 4.1 Backtest results — run, but not yet read by the owner

**Results exist as of 2026-08-18** and live in `data/backtest_report.md`
(with the feature-side documentation in `data/features_report.md`):
`data/features.parquet` holds 630 (company, filing) observations, 581 with
a complete 63-trading-day forward window, evaluated over 6 quarterly
expanding folds after a 6-quarter burn-in.

**This section does not restate any of those numbers**, deliberately. They
are the owner's go/no-go gate files and the owner reads the per-fold tables
personally before anything is concluded from them (`HANDOFF.md` §2a,
§6 Step 4). Once that read happens, this section records, together and in
the same place:

- the **walk-forward scheme** actually used — sorted by public filing
  availability date, expanding window, never a random shuffle;
- the **baseline** the screening score was compared against — a
  numeric-fundamentals-only model, same walk-forward scheme, same target;
- **per-fold spreads, never a single point estimate**;
- the target definition — forward excess return vs. the 25-stock universe
  average, filing-date aligned (owner-ratified 2026-08-18) — with the
  dividend caveat from §3.5 attached;
- the **red-flag error rate with its basis attached (§2.1)** next to any
  red-flag feature importance or ablation claim — 36.6% sample-pooled
  exact-set, 25.0% Tier C base-rate-representative, 7.5% per-category.

**Pre-committed honesty rule** (`DISCOVERY.md` §5, "honest baseline to
beat"): if the text-augmented model does not beat the numeric-only baseline
by a margin larger than run-to-run fold noise, **the honest conclusion is
"the text signal didn't help here"** — stated exactly that plainly, not
hedged into ambiguity that reads as success, and not hidden. That is a
legitimate research result for this project and the go/no-go gate is
designed to accept it.

Known constraints that will shape any result: the universe is 25 companies
over ~12 quarters, which is small; overfitting risk is real and the
mitigation is per-fold variance reporting, not a single averaged number.

### 4.2 Fine-tuned model — TODO (Phase D not started; nothing trained)

**No model has been fine-tuned. No checkpoint exists. No weights have been
downloaded anywhere in this repo.** `finetune/train_qlora.py`'s non-dry-run
path raises `NotImplementedError` by design, and `finetune/eval.py`'s real
path needs predictions from a checkpoint that does not exist. Only the
scaffolding (split, leakage checks, dataset prep, dry-run harnesses) has
been built and verified.

Phase D is conditional: it happens **only if** the Phase C backtest shows
real text signal over the numeric-only baseline, and only if the owner
wants it.

Three Phase D limitations are already **settled findings**, not TODOs,
measured in `finetune/MLX_FEASIBILITY.md` (a paper study — nothing
installed, downloaded, or run):

- **`config.yaml`'s `per_device_train_batch_size: 4` will not fit** in the
  owner's 16 GB M5. The feasible configuration is `batch_size: 1`,
  `max_seq_length: 2048`, `grad_checkpoint: true`, `num_layers: 16`, with
  `grad_accumulation_steps: 4` to recover the intended effective batch.
- **`config.yaml`'s `num_train_epochs: 3` is not an overnight run.** One
  epoch over the 5,736 training examples is estimated at 5–13 hours, so
  three epochs is ≈15–39 hours. Plan one epoch first.
- **`mlx-lm` truncates over-length sequences from the tail**, which
  silently destroys the JSON answer — the only part that carries loss — on
  ~0.5% of train and **~6.3% of eval rows** at `max_seq_length: 2048`.
  Over-length rows must be handled explicitly (dropped, or head-truncated
  on the `input` passage) rather than left to the default.

`TODO (Phase D):` if a fine-tune happens, this section must record the
eval methodology (held-out 1,010-row eval split, its leakage rule per §4.3),
the known weak categories from that eval, and results reported *alongside*
the Phase C baseline — never as a replacement for it.

### 4.3 The fine-tune split tests generalization to unseen text, not to the future

The train/eval split (train 5,736 / eval 1,010, 15.0% eval) is a
connected-component graph over shared `paragraph_id` / `accession_number`,
so whole components — not individual chunks — go to one side. All five
leakage assertions pass (re-verified 2026-08-18: no chunk_id overlap, no
paragraph_id straddle across 28,371 distinct paragraph_ids, no
source-accession straddle across 605 distinct accessions).

Two consequences stated plainly in `finetune/SPLIT_DESIGN.md`:

- **The split is not time-ordered.** `home_filing_date` spans both sides.
  It answers "does the model generalize to unseen text," not "does it
  generalize to the future." The walk-forward backtest (§4.1) is the only
  test of the latter, on a different axis.
- **It is effectively closer to a company-level split than a random one**
  for large components, because filing boilerplate repeats far more within
  one company's own filing history than across companies. That is a
  mechanical consequence of the leakage rule, documented rather than
  hidden; per-ticker train/eval presence is whatever
  `finetune/splits/*.parquet` currently says.

### 4.4 Token counts in the fine-tune scaffolding are estimates, not measurements

Every token count in `finetune/config.yaml` and `train_qlora.py --dry-run`
is `word_count * 1.35`, not a measurement with the real Qwen2.5 tokenizer —
no tokenizer can be loaded offline in this environment. `max_seq_length`
truncation assumptions must be re-measured before any real training run;
`finetune/MLX_FEASIBILITY.md` §2.1 specifies the free local re-measurement
(download `tokenizer.json` only, no weights).

The base-model choice (`Qwen/Qwen2.5-7B-Instruct`, Apache-2.0) **was**
verified live on 2026-08-18 — model-card tag, API metadata, `gated: false`,
and the repository's own unmodified 11.3 kB Apache-2.0 `LICENSE` file — see
the verification table in `finetune/MODEL_CHOICE.md`. That caveat is closed.

---

## 5. Process limitations worth knowing

- **API spend is frozen at $33.51, permanently.** Not a budget to manage
  down — a hard stop (`HANDOFF.md` §5). This is why known label defects are
  documented rather than fixed, and why the §2.8 rubric revision can never
  trigger a re-label.
- **Agent work is not human review.** All labeling, auditing, adjudication,
  red-teaming, and documentation in this project was produced by models
  running on the owner's subscription. The owner's personal judgment
  appears in the decision log (`HANDOFF.md` §3) and in the 104 spot-check
  rulings (§2.3) — nowhere else. Model verdicts are recorded as model
  verdicts throughout.
- **Some audit-trail docs are knowingly stale.** `DISCOVERY.md` (2026-08-10,
  carrying a 2026-08-18 READER NOTE plus **two amendment layers**,
  2026-08-11 and 2026-08-18) and the sampling-rules narrative in
  `spotcheck/README.md` describe earlier states. `HANDOFF.md` is the current
  source of truth and supersedes them where they conflict; `HANDOFF.md` §2
  lists the specific stale passages.

---

## 6. Source index

| Limitation | Canonical source |
|---|---|
| Non-goals (§0) | `DISCOVERY.md` §7; `HANDOFF.md` §1 |
| red_flags failure, error decomposition (§2.1) | `RED_FLAGS_LIMITATION.md`; `spotcheck/agreement_report.txt` |
| Config sensitivity 22.2% (§2.2) | `HANDOFF.md` §2; `DISCOVERY.md` §6; `data/full_run_report.md` FINAL section |
| Spot-check epistemics, 104 owner rulings (§2.3) | `HANDOFF.md` §3 (2026-08-18 entries); `spotcheck/combined_judgments.csv`; `spotcheck/agreement_report.txt` provenance appendix |
| Tier composition / base-rate caveat (§2.4) | `spotcheck/build_sample.py`; `RED_FLAGS_LIMITATION.md` (Tier C red-flags-only rate); `HANDOFF.md` §2a "Base-rate caveat" |
| Empty REALIZED distress classes (§2.5) | `RED_FLAGS_LIMITATION.md` distress addendum; `HANDOFF.md` §3 |
| WITHDRAWN n=1, 8K_BODY n=8 (§2.6) | `REDTEAM_WEEK3.md` finding #7; `HANDOFF.md` §7 |
| Refusal chunk (§2.7) | `HANDOFF.md` §2; `data/full_run_report.md` FINAL section; `REDTEAM_WEEK3.md` finding #1 + resolution |
| Survivorship bias (§3.1) | `INGESTION_NOTES.md` "Universe"; `DISCOVERY.md` §5/§6 |
| Frozen snapshot (§3.2) | `DISCOVERY.md` §6; `HANDOFF.md` §2 |
| Self-identification channel (§3.3) | `REDTEAM_WEEK3.md` finding #2; `DISCOVERY.md` §5 |
| Dedup/home-filing coverage (§3.4) | `REDTEAM_WEEK3.md` finding #3; `DISCOVERY.md` §5 |
| Price adjustment + source caveat (§3.5) | `data/PRICES_NOTES.md` §1–§4; `HANDOFF.md` §2a "Phase C artifacts" (owner-attention item) |
| Fundamentals traps (§3.6) | `HANDOFF.md` §2a, "Binding traps for `features.py`"; `fundamentals_validation_problems` in `data/filings_metadata.db` |
| Phase C backtest artifacts (§4.1) | `data/backtest_report.md`; `data/features_report.md`; `HANDOFF.md` §2a |
| MLX feasibility findings (§4.2, §4.4) | `finetune/MLX_FEASIBILITY.md` §0, §2.3, §3.5, §4.2 |
| PhraseBank/FiQA license (§3.7) | `DISCOVERY.md` §1, §6 risk register |
| Split limitations (§4.3) | `finetune/SPLIT_DESIGN.md`; `finetune/README.md` |
