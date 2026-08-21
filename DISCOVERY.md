> **READER NOTE (2026-08-18):** historical design record, preserved as the
> audit trail. Some operational details are superseded (spend tally, GPU
> fine-tune path, spot-check protocol, week ordering). **Current state and
> plan live in `HANDOFF.md` and `ROADMAP.md`.** The decisions and risk
> register recorded here — including the 2026-08-11 additions — remain
> binding unless HANDOFF.md says otherwise.

# DISCOVERY — Financial Text-Signal Research Tool

Phase 1 discovery for FinScreen, confirmed with the project owner on 2026-08-10.
This is a research/screening tool, not a trading bot: a fine-tuned open-source
LLM extracts structured signals (sentiment, red flags, guidance direction) from
SEC filings; those signals feed a gradient-boosted model alongside numeric
features; everything is validated with honest walk-forward backtesting.

Two items came back genuinely open after research and were resolved directly
with the owner:

- **Transcript sourcing → EDGAR-only for the MVP.** Verbatim earnings-call
  transcripts are deferred to a stretch goal (see §1).
- **Weekly time budget → near full-time (30+ hrs/week).** This sizes the
  week-by-week roadmap (Phase 2), not the MVP scope in this document — the MVP
  stays modest regardless of hours available, because scope creep past a
  small, honest proof of concept is item 5 in the risk register (§6).

---

## 1. Data Sourcing

### SEC EDGAR (filings — 10-K, 10-Q, 8-K)

- **Access is free and public**, no API key. Two surfaces: the `data.sec.gov`
  JSON API (`submissions`, `companyfacts`, `companyconcept`, `frames`) and the
  EDGAR full-text search API (`efts.sec.gov`).
- **Rate limit: 10 requests/second per user**, enforced org-wide regardless of
  how many machines you use. Exceeding it → HTTP 429; sustained abuse →
  temporary IP block.
- **Mandatory `User-Agent` header** identifying you by name + email (e.g.
  `"FinScreen Research vihanpatil7@gmail.com"`). Requests without one are
  throttled or blocked. This is the only real "terms of service" gate — no
  license to accept, no account to create.
- **Bulk data**: `sec.gov/files/` hosts daily-updated `company_tickers.json`,
  `companyfacts.zip`, `submissions.zip` — useful for building the initial
  universe without hammering the per-filing endpoints.
- **No redistribution restriction** — this is US government data, public
  domain.

**Sources:** [SEC EDGAR API Guide 2026](https://tldrfiling.com/blog/sec-edgar-api-guide/),
[SEC EDGAR API Rate Limits](https://tldrfiling.com/blog/sec-edgar-api-rate-limits-best-practices),
[SEC Developer Resources](https://www.sec.gov/about/developer-resources)
*(direct fetch of this last URL returned 403 in this research session — likely
a bot-check on sec.gov, not a policy signal; the facts above are corroborated
by two independent third-party summaries and match well-documented EDGAR
behavior, but worth a 2-minute manual glance before building against it)*.

### Earnings call transcripts — decision: EDGAR-only for the MVP

Skip verbatim call transcripts entirely for now. Instead, use **8-K Item 2.02
exhibits (EX-99.1 earnings press releases)** — filed on EDGAR itself, public
domain, no ToS ambiguity, and containing the forward-looking/guidance language
that's the actual point of interest. Paired with the **MD&A section (Item 7)**
of 10-Ks/10-Qs and **Item 1A Risk Factors** for red-flag signal.

- **Zero incremental cost or legal risk** — same EDGAR pipeline, same rate
  limits, same `User-Agent` requirement.
- **What's lost vs. real transcripts**: Q&A-session tone (analyst pushback,
  hedging in live answers) and speaker-level attribution. Prepared-remarks
  language and MD&A cover a meaningful chunk of what would otherwise be wanted.
- **Verbatim transcripts are a stretch goal**, revisited only if the MVP
  proves out. Options researched for later: (a) [Roic AI](https://www.roic.ai/api/docs/earnings-calls)
  — free tier permits programmatic access at 5 req/min, capped at 2 years of
  history; (b) a paid tier from a provider like EarningsCalls.dev or API
  Ninjas (their free tiers are read-only-website or non-commercial-only).
  Neither is committed to now.

### Non-EDGAR labeled datasets (for weak supervision / eval, not primary data)

- **Financial PhraseBank** (4,845 human-annotated sentences from Lexis-Nexis
  financial news, 16 annotators, ~75% agreement) — license is reported
  inconsistently across mirrors: **CC-BY-NC-SA-3.0** on the canonical
  HuggingFace page vs. CC0 on a Kaggle repackaging. Treated here as
  **NC-licensed** (the more restrictive, canonical source) — fine for this
  non-commercial research project, but flagged in the eventual model card
  that a commercial derivative would need re-licensing or a different labeled
  set.
- **FiQA** (financial sentiment on news/microblog headlines) — same caveat,
  used the same way.

**Sources:** [Financial Sentiment dataset discussion](https://huggingface.co/datasets/takala/financial_phrasebank).
Direct license-page URLs for the CC0-vs-CC-BY-NC-SA-3.0 discrepancy weren't
resolved in this pass — worth a direct check of the canonical HF page before
this becomes load-bearing rather than just an eval reference.

---

## 2. Labeling Strategy

**Revised after Week 2 extraction landed real data and a second Opus review
examined it (see Open Items) — the original "~5,000 whole-section" plan
didn't match what got extracted (884 sections, most far too long to label as
a single unit).** No hand-labeling of thousands of examples either way.
Three-tier approach:

1. **Weak supervision seed** — Financial PhraseBank + FiQA (both
   non-commercial-licensed, fine here) as an off-the-shelf sentiment
   baseline / sanity check, not as training data for the fine-tuned model
   directly, since the label taxonomy here (sentiment + red-flag categories +
   guidance-direction) is bespoke to filings language, not news headlines.
2. **Bootstrap labels with Claude Sonnet 5**, single model, via the Batch
   API, over a **~6,400-example corpus of ~350-word prose windows** (not
   whole sections — see §3 for why the labeling unit changed) against a
   written rubric per label category.
3. **Owner spot-checks 400 examples**, tiered (a proportional random sample
   across section types, targeted oversampling of thin/rare categories, and
   every positive in the rarely-triggered "distress tier" reviewed
   exhaustively) — sized so per-category agreement rates have a confidence
   interval tight enough to actually act on, not just a vibe. Disagreements
   get folded back into the rubric; a second bootstrap pass runs on any label
   category where spot-check agreement is low.

### Cost of the bootstrap pass (Sonnet-only, real corpus size)

| Model | Standard | Intro (through 2026-08-31) |
|---|---|---|
| Claude Sonnet 5 | $3.00/$15.00 per MTok | $2.00/$10.00 per MTok |

**Why Sonnet-only, not Haiku-first-with-fallback as originally planned:** on
the real 6,400-example corpus (~12.8M input / ~1.28M output tokens including
a multi-category rubric + JSON schema output), the Batch-API cost difference
between Haiku-everything (~$9.57) and Sonnet-everything with prompt caching
(~$10.50–19, depending on how much of the run lands inside the cache TTL) is
**under $10 either way** — not enough to justify a two-model fallback
scheme, which would also make Week 4's held-out eval harder to interpret
(a weak category could be "the rubric is wrong" or "half its labels came
from the weaker model," and there'd be no way to tell). Single model, one
provenance, comfortably inside the $50 ceiling. **Not run yet** — this is
the first real spend of the project and needs explicit owner sign-off before
the batch job fires, regardless of how small the estimate is.

---

## 3. MVP Scope

**In scope for the MVP:**
- **~20–30 companies**, one sector-diverse fixed universe (e.g., a slice of
  the S&P 500 spanning tech, financials, healthcare, energy, consumer) —
  diversity matters more than count for an honest backtest.
- **~8–12 quarters of history** (2–3 years) — enough for several walk-forward
  folds without needing a decade of data.
- **Text sources**: 10-K/10-Q (MD&A, Item 1A) + 8-K EX-99.1 earnings releases,
  all via EDGAR.
- **Signals extracted**: sentiment (3-class; **not applied to Risk Factors
  text**, which is negative by statutory construction and would just teach
  the model "risk-factor register ⇒ negative" rather than a real signal),
  guidance direction (raised/maintained/lowered/withdrawn/none — **only
  applies to earnings press releases and 8-K bodies**, MD&A "we expect"
  language is generic forward-looking prose, not issued guidance), and a
  red-flag taxonomy **revised from the original 4 categories after checking
  actual prevalence in the extracted corpus** — see the note below.

  **Red-flag taxonomy, revised:** the original 4 categories (going-concern
  language, restatement mentions, liquidity concerns, litigation escalation)
  were proposed before any real filing text existed to check them against.
  Once it did: going-concern language appears in 5 of ~6,400 labeling
  examples (0.08%) and real accounting restatements in essentially none —
  unsurprising for 25 currently-healthy mega-caps, but not a learnable
  category. Revised to **6 categories with actual support in the data**
  (demand weakness, supply/input constraint, trade-policy exposure,
  impairment/write-down, margin/cost pressure, legal/regulatory action), plus
  a **"distress tier"** (going-concern, accounting restatement, liquidity
  stress) that's still labeled — so the rubric doesn't silently assume these
  things can't happen — but explicitly **excluded from fine-tuning and from
  agreement-rate reporting**, since there isn't enough real signal in this
  universe/window to learn or evaluate it honestly. Every red flag also
  carries a **modality field** (`HYPOTHETICAL` vs. `REALIZED`) — without it,
  "we may experience supply chain disruption" (boilerplate, ~85% of risk
  factors) and "supply constraints reduced Q3 revenue by $400M" (rare, the
  actually informative sentence) would collapse into the same label.
- **Model**: QLoRA-fine-tuned small open-source model (7–8B class) for
  consistent signal extraction, feeding features into XGBoost/LightGBM
  alongside numeric fundamentals.
- **Deliverable**: a walk-forward-validated screening score, an honest
  baseline comparison (numeric-only model, no text), and a written
  limitations doc.

**Explicitly a later stretch goal, not MVP:**
- Verbatim earnings-call transcripts.
- Expanding past ~30 companies or past 2–3 years of history.
- Any live/refreshing data pipeline — the MVP works on a frozen, versioned
  dataset snapshot.
- A UI beyond whatever's needed to demo the backtest results (a notebook or a
  simple static report is enough).

---

## 4. Tech Stack

Optimized for solo, long-term, low-maintenance ownership — mature and boring
over new and clever.

| Layer | Choice | Why |
|---|---|---|
| Language | Python | The default for both ML tooling and data wrangling; one language for the whole pipeline keeps context-switching low for a solo maintainer. |
| Filing ingestion | `requests`/`httpx` + hand-written EDGAR client (or `sec-edgar-downloader` if still maintained at build time) | EDGAR's API is simple JSON/HTML; a hand-rolled thin client avoids depending on a small library that could go stale. |
| Storage | SQLite (metadata) + local Parquet files (filing text, extracted features) | Zero ops, zero hosting cost, trivially backed up, and openable with tools already known. No reason to run Postgres for a single-user research project. |
| Fine-tuning | Hugging Face `transformers` + `peft` (QLoRA) + `bitsandbytes` | The standard, well-documented stack for parameter-efficient fine-tuning on rented GPUs; huge community support if something breaks. |
| GPU rental | RunPod or Vast.ai, spot/community pricing (RTX 4090 ≈ $0.34–0.40/hr; A100 80GB ≈ $0.67–1.99/hr depending on host) | Pay-as-you-go, no idle cost, fits the $50 budget for short fine-tuning runs. *(Figures are a session snapshot and volatile — reconfirm before the first real rental, which needs sign-off anyway.)* |
| Feature engineering / modeling | `pandas` + `xgboost`/`lightgbm` | Boring, mature, exactly what the evaluation design calls for; both have first-class scikit-learn-style APIs. |
| Labeling / bootstrap LLM calls | Claude API (Batch API for bulk labeling) | Already the model family used for this whole project; Batch API is the cheapest bulk-classification path (see §2). |
| Backtest harness | Hand-written walk-forward splitter over `pandas`, evaluated with `scikit-learn` metrics | A dedicated backtesting framework (backtrader, zipline, etc.) is built for trade simulation, not screening-score evaluation — using one here would be exactly the "framework-of-the-month" the operating brief warns against. |
| Hosting | None required for MVP | This is a research artifact, not a service — a script + notebook + static report has zero ongoing cost and nothing to keep patched. |

---

## 5. Evaluation Design

**Time-based train/test split scheme:**
- Sort every observation (company, filing/quarter) by the filing's **public
  availability date** — not the fiscal period end date. A 10-Q covering Q1 is
  often filed 4–6 weeks after quarter-end; the model may only use it once it
  was actually public.
- Walk-forward folds: e.g. train on quarters 1–4, test on quarter 5; train on
  1–5, test on quarter 6; etc. — an expanding window, never a random shuffle.
- Numeric fundamentals used as features must also be point-in-time — e.g.
  don't use a "trailing twelve months revenue" figure that wasn't knowable
  until a later filing corrected it.

**Look-ahead bias, concretely, for this project:**
- Using a filing's text to predict a price move that occurred *before* the
  filing's actual EDGAR filing timestamp (not the period-end date).
- Using restated/corrected financials in features when the original filing
  had different (wrong) numbers at the time.
- Any label bootstrapped from a model that itself has training-data-cutoff
  knowledge of the company's *actual subsequent stock performance* — the
  labeling rubric must be about what the text *says*, not what happened next.
  This is a real risk with LLM-bootstrapped labels and needs an explicit
  prompt-design safeguard (label from text content only, no "and did this
  stock go up" framing). **Week 3 implemented the direct mitigation (never
  inject ticker/company_name/filing_date into a labeling request) but found
  a residual channel it can't fully close**: the filing text itself
  self-identifies the company in a range the Week 3 red-team independently
  measured at **26.8% (strict) to 46% (loose)** of chunks — see
  `REDTEAM_WEEK3.md` §2 for the two measurement methods (loose: company-name
  first token or ticker as a bare word anywhere in the text; strict:
  full/near-full legal company name as a phrase, or exact whole-word ticker
  match excluding ambiguous 1-2-letter tickers) — so a sufficiently
  knowledgeable labeling model can sometimes infer identity from content
  alone. Even the stricter, more defensible figure is meaningfully above the
  ~19% originally estimated here, which means the residual risk this
  paragraph is bounding is larger than the original framing suggested. The
  rubric's explicit countermeasure is instructing the labeler not to use
  recognized identity even when it happens to know it (`labeling_rubric.md`
  §0) — a real safeguard, but not a structural guarantee the way withholding
  the field entirely is. Full redaction of company-identifying language from
  source text was considered and deliberately not attempted for the MVP
  (nontrivial NLP task, real risk of corrupting content the way earlier
  naive text-surgery attempts did in this project). Mitigated instead by:
  the explicit instruction above, and the Week 3 spot-check treating this as
  a specific thing to watch for, not just general labeling quality.
- Universe survivorship bias: if the ~20–30 company universe is picked using
  today's S&P 500 membership, that silently excludes companies that were in
  it historically and later failed or were delisted — a real bias for a
  "screening" tool. Flagged in the limitations doc even though the MVP
  doesn't fully solve it.

**Label-to-filing attribution (owner decision, 2026-08-11):** because
near-verbatim boilerplate is deduplicated and labeled only once — at its
earliest ("home") filing — 17% of filing-sections, and 46.5% of Risk
Factors sections specifically, contain no labeled text of their own.
**Decision: a paragraph's label attributes to every filing it appears in,
not only its home filing.** This is point-in-time safe because the label
describes what the *text* says, and each filing receives the label only
from that filing's own public availability date onward — no information
flows backward in time. The alternative (home-filing-only) would leave
nearly half of Risk Factors sections with no text signal at all, which
would weaken the very hypothesis this project exists to test. Implemented
in Week 5's `features.py` against `data/paragraph_occurrence_map.parquet`;
`red-team-reviewer` re-verifies the no-backward-flow property in Week 6.

**Honest baseline to beat:**
- A model using **only numeric fundamentals** (no text features at all), same
  walk-forward scheme, same target. If the text-augmented model doesn't beat
  this baseline by a margin bigger than run-to-run noise (measured via
  repeated folds), the honest conclusion is "text signal didn't help here" —
  not a result to hide.
- Both baseline and text-augmented performance reported with confidence
  intervals or at minimum a spread across folds, not a single point estimate.

---

## 6. Risk Register

| Risk | Mitigation |
|---|---|
| Overfitting to a small (~20–30 company) universe | Walk-forward validation with an expanding window; report per-fold variance, not just an average; explicit numeric-only baseline comparison. |
| LLM-bootstrapped labels encode look-ahead bias (model "knows" what happened next) | Rubric-based labeling prompts that reference only the text content, never outcome framing; owner spot-check specifically probes for this. |
| Chosen data source (EDGAR) changes format/rate limits | Low risk — EDGAR is a stable, decades-old government system, but the client is built with a thin abstraction layer so a schema change doesn't ripple through the whole pipeline. |
| GPU/fine-tuning cost overruns the $50 budget | Every action over $5 gets pre-approved (standing operating rule); start with the cheapest viable GPU tier and a short trial run before a full fine-tune. |
| Scope creep (more companies, more quarters, live pipeline) turns a 2-month project into a 6-month one | MVP scope is fixed in this doc regardless of available hours; expansions are explicitly logged as stretch goals, not silently absorbed into "the MVP." |
| Data drift — the world changes between training and any later use | Explicitly a non-goal to keep the model live/current; every result is dated and tied to the frozen dataset snapshot it was trained on. |
| Financial PhraseBank/FiQA license (CC-BY-NC-SA-3.0) restricts downstream use | Used only as an eval/sanity-check reference, never redistributed or used to train a model intended for anything beyond this personal project; documented in the model card. |
| Survivorship bias in company universe selection | Documented explicitly as a known limitation in the honest-limitations write-up rather than solved in the MVP. |
| **Red-flag labels are ~22% sensitive to labeling configuration** (measured 2026-08-11: 935 of 4,219 chunks changed red-flag sets between an adaptive-thinking pass and a thinking-disabled pass, systematically in the direction of more flags). Sentiment (3.6%) and guidance (0.9%) are stable by comparison. | Treated as a **headline limitation**, not a footnote: any downstream red-flag-derived feature inherits this uncertainty, and the direction of the bias is documented (the retained config flags more liberally). The owner's 400-example spot-check includes a dedicated 60-chunk blind adjudication tier drawn from the disagreement set to measure which configuration is actually more accurate. Reported in the model card. **[2026-08-18 amendment: the spot-check completed — red_flags agreement measured at 63.4% (95% CI [58.6, 68.0]), failing the 0.70 bar; Tier D (the config-disagreement tier) was the weakest tier at 71.2% pooled-headline. 36.6% of stored red-flag sets were ruled incorrect under a three-rater + owner-adjudicated protocol. Full decomposition, ratified ambiguity principles, proposed rubric fix (pending ratification, no re-label), and binding Week-5 feature constraints: `RED_FLAGS_LIMITATION.md`. Sentiment (94.6%), guidance (95.2%), and distress_tier (94.2%, reported separately) cleared the bar — with the caveat that all 9 REALIZED LIQUIDITY_STRESS labels were owner-ruled incorrect, emptying that class.]** **[2026-08-18, correction to the amendment immediately above: the four per-tier figures in `agreement_report.txt` Section 3, including that 71.2%, pool ALL THREE headline fields (sentiment + guidance + red_flags) together. On a **red-flags-only** basis, recomputed from `spotcheck/combined_judgments.csv`, the tier rates are **A 96/162 = 59.3%, B 98/141 = 69.5%, C 27/36 = 75.0%, D 32/60 = 53.3%** — so Tier D is indeed the weakest (53.3%, not 71.2%), but Tier A at 59.3% is also worse than the pooled figure quoted for the "weakest" tier, and the two bases order the tiers differently. The 36.6% error figure is likewise sample-pooled, not corpus-representative; the base-rate slice is Tier C at 25.0% error, n=36, CI [58.9, 86.2]. See `RED_FLAGS_LIMITATION.md`.]** |

---

## 7. Non-Goals (restated for the project docs)

- **Not a trading bot.** No component of this system places, queues, or
  recommends executing any trade.
- **Not investment advice.** Screening scores are a research signal, not a
  recommendation to buy, hold, or sell anything.
- **No live capital**, ever, in any phase of this project.
- **No return guarantees**, expected-performance claims, or "beats the
  market" language anywhere in code, docs, README, or model card. Every
  performance number is reported with exactly how it was measured, next to
  it, every time.

---

## Open items flagged, not resolved

- ~~`sec.gov/about/developer-resources` returned HTTP 403 to direct fetch in
  this research session~~ **Confirmed in Week 1 (`INGESTION_NOTES.md`):** the
  403 was just a bot-check on the un-agented fetch tool, not real EDGAR
  behavior. A request carrying the required `User-Agent` gets a normal 200.
  The 10 req/sec rate limit was never approached across ~640 requests in
  Week 1's ingestion run (no 429s observed).
- **Resolved by an Opus review of Week 1's two findings, which surfaced a
  bigger problem than either original finding — corrective work completed,
  re-verified:** the "XOM CIK override" and "exhibit filename unreliable"
  fixes were both narrow patches for a single underlying gap: nothing in the
  pipeline validated that a resolved CIK's data was actually complete.
  Checking that assumption against the cached data found **JPM, BAC, and GS
  (3 of 25 companies) had only ~12 months of filing history, not 36** —
  EDGAR's `filings.recent` array doesn't reach back far enough for
  high-filing-volume companies, and the older history sits in paginated
  `filings.files[]` chunks the Week 1 client never fetched. This directly
  contradicted the "recent covered back to at least 2015 for every company,
  so this wasn't a real problem here" claim in the original
  `INGESTION_NOTES.md` — that claim was wrong; the per-company data was
  never actually checked, only an aggregate impression that happened to hide
  the shortfall. **Fixed**: `EdgarClient.get_effective_recent()` fetches
  `files[]` pagination chunks on demand; all three companies now land at the
  expected 3 10-Ks / 9 10-Qs, matching the rest of the universe. Also added:
  a hard-fail `validate_universe()` pass (entity resolves, history reaches
  the cutoff, plausible per-company filing counts, no filing gap > 135 days,
  recent-activity staleness, current tickers actually match, and
  `company_tickers.json` vs. `universe.csv` CIK disagreements reported as
  warnings rather than silently trusted either way — confirmed this fires a
  WARN, not a FATAL, for the known XOM case), and a `filing_documents` table
  + selection-policy function replacing the old single-filename exhibit
  resolution (handles multiple/zero `EX-99.x` exhibits and the MCD
  dual-"8-K"-typed-index-row hazard explicitly). Full writeup in
  `INGESTION_NOTES.md`.
- **The 45-day "any filing" staleness threshold (HD tripped it by 2 days) —
  resolved by a third Opus pass that checked the real inter-filing-gap
  distribution across all 25 companies instead of guessing at a number.
  Fix landed and re-verified (this pass).** The owner's instinct that 45
  was too tight was right, but the initially proposed fix (65 days) would
  still misfire — the real max observed gap in three years of data is 70
  days (SLB). **Fixed**: raised the threshold to 80 days (same calibration
  discipline as the existing 135-day 10-K/10-Q check: max-observed + ~15%
  headroom) and downgraded it from FATAL to WARN (split into its own check
  name, `recent_activity_any_form`, distinct from the still-FATAL
  `recent_activity_10k_10q`), since it fired on ~10% of possible run-dates
  at 45 days and isn't the check that actually detects a stopped-filing
  entity (the 135-day 10-K/10-Q-specific check is, and stays FATAL).
  Re-verified: HD no longer trips anything under the new threshold (47 <
  80), and a fresh `ingest_metadata.py` run produces zero FATALs. This pass
  also caught, and fixed, a more serious bug: the
  `--allow-incomplete-universe` override flag silently disarmed every FATAL
  check for a run, not just the one being overridden — the HD override on
  2026-08-10 also silently disarmed the JPM/BAC/GS-class regression guard
  for that same run. **Fixed**: the flag now takes an explicit,
  comma-separated list of check names to downgrade; any FATAL on a
  check not named still hard-fails the run, and downgraded checks are
  printed loudly. Verified with a simulated FATAL: an unscoped or
  wrongly-scoped override correctly still exits(1); a correctly-scoped one
  proceeds. Also caught in extracted Week 2 data during the same pass, and
  now fixed and re-verified: 9 of 75 10-K "MD&A" sections were empty
  one-sentence stubs marked high-confidence (CVX, XOM, and JPM's 10-Ks
  incorporate MD&A by reference elsewhere in the document rather than
  writing it inline, and the extractor grabbed only the pointer sentence) —
  3 companies had zero usable MD&A text. **Fixed**: all 9 now resolve to
  real, substantive MD&A content (14,871–64,645 words, `extraction_method
  ='incorporated_by_reference_resolved'`, `confidence='medium'`) located
  elsewhere in the same primary document; zero remain unresolved. Full
  writeup, including the general per-(form,section) length-floor
  plausibility check this was one instance of, in `INGESTION_NOTES.md`'s
  Week 2 section.
- GPU spot pricing is a session snapshot and moves; re-check the actual rate
  at the provider before the first paid rental (which needs sign-off anyway
  under the $5 rule).
- Financial PhraseBank's license is reported inconsistently between
  HuggingFace (CC-BY-NC-SA-3.0) and a Kaggle mirror (CC0) — treating it as the
  more restrictive one is the safe default; worth a direct check of the
  canonical HF page if it ever becomes load-bearing rather than just an eval
  reference.

---

## Session spend tally

**$0 spent this session** against the $50 ceiling. All research used free web
search/fetch and the Claude Code session itself (Pro subscription usage, not
"outside the Pro subscription" spend per the operating rules). **Cumulative
project spend: $0 / $50.**
