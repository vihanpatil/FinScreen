# FinScreen — Model Card

> # ⚠️ DRAFT — Phase E deliverable, awaiting final review. Last updated 2026-08-18.
>
> **This file is not finished and must not be cited as if it were.** Sections
> §1–§6 contain results (Phase C backtest now complete with owner's GO decision).
> Sections §7–§9 remain **GATED** (Phase D fine-tune is optional and un-launched;
> Phase E red-team review not yet requested). Gated sections are marked with a
> loud `🚧 GATED TODO` banner and contain **no results, no estimates, and no
> placeholders that could be mistaken for findings**. Nothing has been filled
> in speculatively.
>
> **Two gates remain open; one is now closed:**
>
> | Gate | Blocks | Status |
> |---|---|---|
> | Phase C go/no-go — the owner's own read of `data/backtest_report.md` | §6 (Evaluation results) | ✅ CLOSED — owner read: GO, diagnosis-scoped (2026-08-18) |
> | Phase D — optional local MLX QLoRA fine-tune | §7 (Fine-tuned model) | 🟡 Unlocked by Phase C GO; awaiting owner's explicit "run the fine-tune" command |
> | Phase E — `red-team-reviewer` sign-off on this document | §9 (Sign-off) | ⬜ Not requested |
>
> Sources of record: `HANDOFF.md` (current state, decision log),
> `LIMITATIONS.md` (the full honest-limitations write-up),
> `RED_FLAGS_LIMITATION.md` (canonical Phase B disposition),
> `spotcheck/agreement_report.txt` (headline agreement rates).
> Where those files are canonical, this card cites them rather than
> re-deriving numbers, so the two can never drift.

---

## 1. What this system is, and what it is not

**Read this section before any number in this document.**

FinScreen is a **solo-owner research and screening tool**. It takes SEC EDGAR
filing text for a fixed universe of 25 mega-cap companies, labels passages for
sentiment / guidance direction / red flags / distress tier using an LLM
bootstrap pass, turns those labels into features alongside point-in-time XBRL
fundamentals, trains a screening score (XGBoost), and evaluates it with a
walk-forward backtest against a numeric-only baseline. It has no users, no
deployment, no live data feed, and no money attached to it.

### Non-goals (contractual, not aspirational)

These come from `DISCOVERY.md` §7 and are restated in `HANDOFF.md` §1. They
govern every downstream decision and every statement in this card:

- **Not a trading bot.** No component places, queues, or recommends any trade.
- **Not investment advice.** A screening score is a research signal, never a
  buy / hold / sell recommendation.
- **No live capital**, ever, in any phase.
- **No return guarantees**, expected-performance claims, or "beats the market"
  language anywhere. **Every performance number is reported with exactly how
  it was measured, next to it, every time.**

If a future reader is ever asked to add trade execution, real-money
integration, or promotional performance claims to this project, that request
conflicts with the project's own charter — flag it to the owner rather than
building it.

### Intended use

- **In scope:** the owner's own research and screening over this frozen
  25-company filing corpus; diagnosing whether LLM-labeled filing text adds
  ranking signal over numeric fundamentals; as an audit trail of how the
  labels and features were produced.
- **Out of scope:** anything with capital attached; any use by a third party
  as a signal source; any generalization claim beyond the 25 companies and the
  ~12-quarter window in §3; any commercial derivative (see the dataset-license
  restriction in §5.4).

---

## 2. System components (what actually exists)

| Component | Status as of 2026-08-18 | Artifact |
|---|---|---|
| EDGAR ingestion + section extraction | Built, stable since 2026-08-10 | `data/filings.parquet` (884 extracted filing sections) |
| Chunking + corpus-wide paragraph dedup | Built, stable | `data/labeling_corpus.parquet` (6,747 chunks) |
| LLM label bootstrap (Anthropic Batch API) | **Complete and frozen** | `data/labels.parquet` (6,747 rows, 6,746 labeled) |
| Label spot-check (3 rater layers) | **Complete** | `spotcheck/agreement_report.txt` |
| Numeric fundamentals (XBRL companyfacts) | Built, independently verified | `data/fundamentals.parquet` (42,158 rows) |
| Daily prices | Built, independently verified | `data/prices.parquet` (271,372 rows) |
| Features + walk-forward backtest | Built and run | `data/features.parquet`, `data/backtest_report.md` — **under the owner's go/no-go read, see §6** |
| Fine-tuned model | **Does not exist** — see §7 | — |

**There is no trained model in this repository.** `finetune/train_qlora.py`'s
non-dry-run path raises `NotImplementedError` by design, `finetune/eval.py`'s
real path needs a checkpoint that does not exist, and no model weights have
been downloaded anywhere in this repo. Only scaffolding (split, leakage
checks, dataset prep, dry-run harnesses) has been built and verified.

---

## 3. Training / labeling data provenance

### 3.1 Universe

25 US mega-cap companies, 5 sectors × 5 tickers, locked in
`data/universe.csv`. **Chosen because they are large and prominent *today*** —
this is a deliberate convenience choice with a survivorship-bias consequence
stated plainly in §5.1.

### 3.2 Source and window

- **Source:** SEC EDGAR, via `edgar_client.py` (rate-limited, caching). 10-K /
  10-Q / 8-K filings and their EX-99.x earnings exhibits. Raw responses are
  cached under `data/raw/`.
- **Sections extracted:** MD&A, Item 1A Risk Factors, earnings-release text
  (EX-99.1), and 8-K bodies → **884 filing-sections** in
  `data/filings.parquet`.
- **Window:** 12 quarters back from 2026-08-10, i.e. `filing_date >=
  2023-08-14`. **1,271 filings resolved.**
- **The corpus is a frozen snapshot, not a live feed** (§5.2).

### 3.3 Chunking and paragraph deduplication

`chunk.py` splits each section into prose paragraphs (≥40 words), deduplicates
them **corpus-wide** (normalized whitespace + lowercase, SHA1-keyed), packs
each unique paragraph into a ~350-word labeling window at its **earliest
("home") occurrence only**, and writes:

- `data/labeling_corpus.parquet` — **6,747 chunks**;
- `data/paragraph_occurrence_map.parquet` — **28,504 rows, one per canonical
  (deduplicated) paragraph**, with **42,577 total occurrences** held in list
  columns (`sum(n_occurrences)`). This is *not* a pre-exploded occurrence
  table — explode before joining.

Labeling once per unique paragraph is what makes the run affordable; its
coverage consequence (46.5% of Risk Factors sections have zero home chunks of
their own) and the every-occurrence attribution rule adopted to mitigate it
are in §5.3.

### 3.4 The label bootstrap pass and its uniform configuration

Labels were produced by an LLM bootstrap pass over the 6,747 chunks
(Anthropic Batch API, `submit_labeling_batch.py`), against the rubric in
`labeling_rubric.md` (v1.1). **They are model-generated labels, not
human-annotated ground truth.**

- **Configuration is uniform across all 6,747 rows:** `thinking=disabled,
  max_tokens=4000`, **zero truncations** (every row `stop_reason=end_turn`
  except the single refusal below). Reaching that uniformity required a
  corrective re-label of 4,219 rows originally run under the wrong config —
  the incident and its standing rule are in `HANDOFF.md` §4.
- **6,746 of 6,747 chunks labeled (99.99%).** One chunk,
  `CHK-8e69547e0900a8dd` (`section_type=MDA`), carries no labels: a genuine
  mid-stream safety refusal (`stop_reason=refusal`,
  `stop_details.category=bio`, 293 output tokens emitted), confirmed by a
  direct read-only re-query of the batch result rather than inferred from
  stored columns. Excluded by predicate, not deleted.
- **Look-ahead-bias controls at labeling time:** ticker, company name, and
  filing date are **never** injected into a labeling request, and
  `section_type` is never named as literal prompt text (rubric v1.1;
  applicability is enforced only through the JSON output schema). Verified by
  grep across all 6,747 requests: 0 hits for dates, 0 for `section_type`. The
  residual channel that this does *not* close is §5.5.
- **Cost, frozen:** $33.51 total across canary, full run, corrective run, and
  re-label. Further Anthropic API spend is prohibited outright
  (`HANDOFF.md` §5), which is why every known label defect below is
  *documented* rather than fixed.

### 3.5 Label distributions (final, post-relabel; from `data/labels.parquet`)

| Field | Distribution |
|---|---|
| `sentiment` | NEUTRAL 3,436 / POSITIVE 1,024 / NEGATIVE 680. **1,607 rows carry no sentiment label** = 1,606 RISK_FACTORS chunks (never asked for sentiment, per the applicability matrix) + the 1 refusal chunk. |
| `guidance_direction` (non-NONE) | RAISED 34 / MAINTAINED 34 / LOWERED 14 / WITHDRAWN 1 — 83 non-NONE labels across 6,746 chunks. |
| `distress_tier` positives | 162 total: LIQUIDITY_STRESS/HYPOTHETICAL 151, LIQUIDITY_STRESS/REALIZED 9, ACCOUNTING_RESTATEMENT/HYPOTHETICAL 2, GOING_CONCERN 0. **All 9 REALIZED LIQUIDITY_STRESS labels were subsequently ruled incorrect — see §4.4.** |
| `red_flags` | 6 categories × 2 modalities. Category counts are in `data/full_run_report.md`'s FINAL section, dated 2026-08-18 CURRENT PER-CATEGORY COUNTS block. **These labels failed the project's quality bar — see §4.1.** |

### 3.6 Numeric and price inputs (Phase C)

- **Fundamentals:** `data/fundamentals.parquet` — 42,158 rows, 25 companies,
  13 XBRL concepts, filed dates 2009 → 2026-08-10, pulled from EDGAR
  companyfacts (free, no API spend). **Every filed occurrence is preserved as
  its own row; restatements are never overwritten** — per `HANDOFF.md` §2a,
  9,705 facts are reported by more than one filing under the grouping key
  `ticker` + `concept` + `period_end`. Point-in-time correctness therefore
  depends on reading via `pit.value_as_of()` (latest-filed-as-of), never
  "latest value". Validation: **40 WARN / 0 FATAL across five WARN
  categories**, all empirically verified; the structural gaps and tag
  migrations they encode are in §5.6.
- **Prices:** `data/prices.parquet` — 271,372 rows, 25 tickers, full available
  history. **Split-adjusted, NOT dividend-adjusted**, and sourced from a
  fallback provider — both are real caveats, in §5.7.

### 3.7 Fine-tune split (built; no model trained against it)

`finetune/split.py` builds a leakage-safe train/eval split as a connected-
component graph over shared `paragraph_id` / `accession_number`, so whole
components — not individual chunks — land on one side. Live split:
**train 5,736 / eval 1,010 (15.0% eval), 6,746 total.** All five leakage
assertions pass (re-verified 2026-08-18: no `chunk_id` overlap, no
`paragraph_id` straddle across 28,371 distinct paragraph_ids, no
source-accession straddle across 605 distinct accessions, excluded chunk in
neither split, manifest uniquely covers all 6,746). Its two honest limits —
it is **not time-ordered**, and it is mechanically closer to a company-level
split than a random one — are in `LIMITATIONS.md` §4.3 and
`finetune/SPLIT_DESIGN.md`.

---

## 4. Label quality — how it was measured, and what failed

`RED_FLAGS_LIMITATION.md` is the **canonical disposition record** and
`LIMITATIONS.md` §2 is the full write-up. This section states the headline
verdicts and the measurement that produced each; it does not re-derive the
underlying numbers.

### 4.1 Measurement method (read before any rate below)

A 400-chunk sample (`spotcheck/sample_400.parquet`, built by
`spotcheck/build_sample.py`) was re-judged in three rater layers, scored by
`spotcheck/compute_agreement.py` with 95% Wilson confidence intervals against
a pre-registered **0.70 CI-lower-bound bar**:

1. **Blind second rater** (`label-auditor`, a model) independently re-judged
   all 400 chunks before seeing the stored label.
2. **Third rater** (`label-adjudicator`, a model, sees both prior positions)
   ruled on rubric merits where the second rater disagreed with the stored
   label.
3. **The owner** personally ruled a shortlist.

**The sample is deliberately tiered and is NOT base-rate representative:**
Tier A = 162 (all distress positives, exhaustive), Tier B = 142 (thin/rare
category oversample), Tier D = 60 (the config-disagreement set, judged blind),
Tier C = 36 (proportional stratified random fill — **the only
base-rate-representative slice**). Any all-tier pooled rate overweights rare
and contested text.

### 4.2 Headline verdicts

Rates below are pooled across all four tiers unless stated otherwise; n is the
number of judged field-cases; source `spotcheck/agreement_report.txt`.

| Category | Agreement (95% Wilson CI) | vs. 0.70 bar | Verdict |
|---|---|---|---|
| `sentiment` | 94.6% [91.3, 96.7], n=279 | passes | Cleared |
| `guidance_direction` | 95.2% [90.4, 97.6], n=145 | passes | Cleared (WITHDRAWN n=1 remains non-evaluable) |
| `distress_tier` (reported separately per rubric §5, excluded from every headline number) | 94.2% [91.5, 96.1], n=399 | passes | Cleared **as a category** — but one of its classes was emptied, §4.4 |
| **`red_flags`** | **63.4% [58.6, 68.0], n=399** | **fails — the *upper* bound is below the bar** | **Failed. Documented, not fixed.** |

**`red_flags` is an EXACT-SET-MATCH rate and is not comparable to the
single-value rates printed beside it.** One added, dropped, or re-modalized
category on a multi-category chunk scores the whole chunk as a disagreement.
The same 146 disagreements decompose into **180 category-level corrections
over 399 × 6 = 2,394 chunk-category decisions = 7.5% per-category error
(92.5% per-category agreement [91.4, 93.5])**. Both numbers are true and they
answer different questions.

**Which error rate to carry forward, with its basis attached** (per
`RED_FLAGS_LIMITATION.md` binding implication #1 — quote all three, never one
alone):

| Basis | Error rate | How measured |
|---|---|---|
| Sample-pooled, exact-set | **36.6%** (146/399) | All four tiers pooled — deliberately oversampled, **not** corpus-representative |
| Base-rate-representative, exact-set | **25.0%** (Tier C, 27/36 agree = 75.0% [58.9, 86.2]) | Tier C only, the proportional stratified slice; wide CI, n=36 |
| Per-category | **7.5%** (180/2,394) | Category-level corrections over chunk-category decisions |

The "fails the 0.70 bar" verdict survives on every basis except the
per-category one (Tier C's CI lower bound is 58.9%). Carrying 36.6% forward as
*the* corpus error rate overstates it by roughly 11 points.

**Where `red_flags` fails hardest, on a red-flags-only basis** (recomputed
from `spotcheck/combined_judgments.csv`; do **not** use
`agreement_report.txt` Section 3's per-tier figures for a red-flag claim —
those pool sentiment + guidance + red_flags and dilute the failure by roughly
18 points per tier, inverting the ordering): Tier D 53.3% [40.9, 65.4], Tier A
59.3% [51.6, 66.5], Tier B 69.5% [61.5, 76.5], Tier C 75.0% [58.9, 86.2]. By
section, RISK_FACTORS is weakest at **59.2% (71/120)** — red-flags-only by
construction, since RISK_FACTORS chunks are only ever asked `red_flags`.

The three error modes and their per-category decomposition (61 spurious flags
/ 76 missed flags / 43 right-category-wrong-modality = 180 corrections) are in
`RED_FLAGS_LIMITATION.md`. **Modality (REALIZED vs. HYPOTHETICAL) is the least
reliable dimension**, and stored REALIZED counts for legal/regulatory exposure
are biased **low**.

### 4.3 Red-flag labels are also configuration-sensitive (22.2%)

**Comparing the same 4,219 chunks across two full-corpus labeling passes** —
the original adaptive-thinking pass (`data/labels_pre_relabel.parquet`) vs.
the retained `thinking=disabled, max_tokens=4000` pass
(`data/labels.parquet`) — **`red_flags` changed on 935 of 4,219 chunks
(22.2%)**. Same comparison, other fields: `sentiment` 3.6% (119/3,280),
`guidance_direction` 0.9% (6/677), `distress_tier` 0.7% (29/4,219). Red flags
are the outlier by an order of magnitude, and the retained config flags
systematically **more** in every category (deltas in `HANDOFF.md` §2 and
`DISCOVERY.md` §6, on a per-chunk-category-presence basis).

**Read §4.2 and §4.3 together, because they agree:** red-flag labeling sits
closest to the rubric's ambiguity boundaries, so it is the least stable
category under any perturbation — of configuration *or* of rater. **Red-flag
counts are meaningfully a function of *how the labeling model was asked*, not
only of *what the filing says*. Treat them as directional, never as precise
counts.**

Worth stating because it is the generalizable lesson: **this instability was
completely invisible at canary scale.** The 50-chunk canary runs validated
request mechanics, not distributional stability; the 22.2% only appeared when
two full-corpus passes were compared.

### 4.4 Every REALIZED distress class is empty or near-empty

- **`LIQUIDITY_STRESS` / REALIZED: n=0 corpus-wide.** The corpus stored 9 such
  labels; the second rater disputed 8 of 9, the third rater sided with the
  second rater on all of them, and the owner then explicitly ruled all 9
  incorrect (owner principle P2: affirmed adequacy defeats the flag, and a
  working-capital deficit alone is not distress). Five of the nine were the
  same recurring PG "working-capital deficit + affirmed adequacy" disclosure
  across successive quarters.
- **`GOING_CONCERN`: n=0 by construction** — the universe is 25
  currently-healthy mega-caps. Zero is the expected result, not a data
  problem.
- **`ACCOUNTING_RESTATEMENT`: n=2**, both HYPOTHETICAL-framed risk-factor
  text; both survived adjudication.

**Consequence: there is no realized-distress coverage in this dataset.**
Distress-REALIZED features are known-empty and must not be engineered. The
distress tier stays excluded from fine-tuning targets and from every headline
eval metric, enforced in code (`finetune/prepare_dataset.py`,
`finetune/eval.py`, `compute_agreement.py`'s
`assert_distress_excluded_from_headline()`).

Note the asymmetry: `distress_tier` as a *category* passed at 94.2% while one
of its classes was simultaneously ruled entirely wrong. The category rate is
dominated by correct negatives.

### 4.5 Two categories cannot be evaluated at all

- **`guidance_direction = WITHDRAWN`: n=1 corpus-wide**, and it sits in the
  training split by necessity. No per-class metric on it means anything.
- **`section_type = 8K_BODY`: n=8 corpus-wide, from only 2 of 25 tickers
  (BAC, CVX)** — 0 train / 8 eval. Not meaningfully learnable or evaluable at
  this corpus size.

Any table reporting a number for either must say "insufficient support" rather
than folding it into an aggregate that implies it was actually evaluated.

### 4.6 Epistemics — what the agreement rates do and do not measure

**These are model-consensus agreement rates. They are NOT human validation of
ground truth.** This is an owner-ratified requirement (`HANDOFF.md` §3,
2026-08-18 adjudication-delegation entry) and must be restated wherever the
rates appear.

Of the **1,222 (chunk, field) judgments** in
`spotcheck/combined_judgments.csv`:

| Source | Judgments | What it means |
|---|---|---|
| `model-auditor` | 1,023 | Two models independently agreed; **no human looked at it** |
| `model-adjudicator` | 95 | A third model resolved a two-rater dispute; **no human looked at it** |
| `owner` | **104** | The owner's own judgment |

**The owner personally ruled 104 of 1,222 judgments** — 85 by block
ratification of the adjudicator's medium-or-higher-confidence rulings, and 19
explicitly (the 11 high-stakes distress chunks plus an 8-case final
verification round). **That is the entire human input to this project's label
validation.** No claim derived from this work may imply more human validation
than that, and no model verdict may be presented as the owner's own.

Human judgment was deliberately *concentrated* where it was most informative
(high-stakes and rubric-underdetermined cases) rather than spread evenly —
a reasonable design that also means the 104 owner rows are **not** a random
sample of the corpus.

### 4.7 The labels are frozen, and the known fix was not applied

`data/labels.parquet` **stays frozen** (owner ruling, 2026-08-18). Spot-check
corrections live in the spot-check record only; they were **not** written back
into the label file. Everything downstream consumes the frozen corpus with the
documented error rates above.

A rubric revision addressing the §4.2 failure modes is drafted in
`RED_FLAGS_LIMITATION.md` but is **pending owner ratification and NOT
applied**. Even if ratified, **no re-label will occur** — API spend is frozen
at $33.51 with a hard no-further-spend rule. The revision exists so that any
*future* labeling does not re-inherit these ambiguities, not as a fix to the
current data.

---

## 5. Known limitations carried into every downstream claim

Full write-up: `LIMITATIONS.md`. Summarized here because a model card is read
by people who will not open it.

### 5.1 Survivorship bias in the fixed universe

The 25 companies were chosen because they are large and prominent **today**. A
company equally prominent in 2023–2024 that has since been acquired,
delisted, or gone through distress does not appear here, by construction. Every
downstream result inherits this. **It is not corrected anywhere in this
project, and nothing here quantifies how much it flatters the results.**
Related and unquantified: `GOING_CONCERN` n=0 (§4.4) is a direct consequence
of the same selection — the dataset contains no examples of the distress the
tool nominally screens for.

### 5.2 Everything is a frozen snapshot

Filings (12 quarters to 2026-08-10), labels (frozen, un-regenerable under the
spend freeze), fundamentals (filed dates to 2026-08-10), and prices (fetched
2026-08-18). Any result is dated to this snapshot and says nothing about
periods after it. Re-running the pipeline later would produce a different
corpus, and **the label set could not be regenerated to match it.**

### 5.3 Deduplication coverage bias

Because paragraphs are labeled only at their earliest occurrence, **150 of 884
filing-sections (17.0%) have zero home chunks of their own — 118/254 = 46.5%
of Risk Factors sections.** This is *not* a look-ahead leak (home is always
the earliest occurrence; verified 0 mismatches across all 5,029
multi-occurrence paragraphs), but it *is* a coverage bias. The owner-ratified
mitigation (2026-08-11) is **every-occurrence attribution**: a paragraph's
label attaches to every filing it appears in, each carrying that filing's own
real filing date. The failure mode to watch: a naive join on
`home_accession_number` would make ~46% of Risk Factors sections silently show
"no risk-factors signal", easily misread as "no red flags".

### 5.4 Third-party dataset licensing (Financial PhraseBank / FiQA)

`DISCOVERY.md` §1 names **Financial PhraseBank** and **FiQA** as an
off-the-shelf sentiment sanity-check reference. **Financial PhraseBank's
license is reported inconsistently across mirrors — CC-BY-NC-SA-3.0 on the
canonical HuggingFace page vs. CC0 on a Kaggle repackaging. This project
treats it as NC-licensed (the more restrictive, canonical reading); FiQA
carries the same caveat.**

That is fine for a non-commercial personal research project, which is why the
risk register constrains both to eval / sanity-check reference use only —
never redistributed, never used to train a model intended for anything beyond
this project. Two honest qualifications: **(a)** neither dataset is ingested
by any artifact currently in this repo, so the constraint is forward-looking,
not a description of something that happened; **(b)** the license discrepancy
was never resolved against the canonical license page. **A commercial
derivative of anything touching these datasets would need re-licensing or a
different labeled set, and the license question would have to be settled
first.**

### 5.5 The residual self-identification channel

The structural mitigation works — ticker, company name, and filing date are
never injected into a labeling request (§3.4). **But the filing text
self-identifies its own company in a substantial share of chunks, and that
channel is open.** Two independent measurements against
`data/labeling_corpus.parquet` (`REDTEAM_WEEK3.md` finding #2 — **both are
cited so no reader picks one and assumes the other was wrong**):

| Method | Overall | Highest sections |
|---|---|---|
| **Strict** (full/near-full legal name as a phrase; exact whole-word ticker, excluding ambiguous 1–2-letter tickers V/MA/GS) | **26.8%** | 8K_BODY 75.0%, EX99_PRESS_RELEASE 59.2% |
| **Loose** (company-name first token or bare ticker anywhere) | **46.0%** | 8K_BODY 75.0%, EX99_PRESS_RELEASE 73.5% |

The loose method is knowingly over-permissive ("Bank", "Home"); the strict
method is the more defensible figure. **The risk:** a labeling model that
recognizes the company could in principle use post-training knowledge of what
happened to that company next instead of judging what the text says — a
look-ahead-bias channel. The only countermeasure is a prompt instruction not
to use recognized identity — a real safeguard, but not a structural guarantee
the way withholding the field is. **What is not known: how often the labeling
model actually exploited the channel.** The red-team review could bound how
often the channel *exists*, not how often it was *used*. Documented open risk,
not a solved problem.

### 5.6 Numeric fundamentals have structural gaps and tag migrations

From the validated ingestion (40 WARN / 0 FATAL across five WARN categories):

- **`OperatingIncomeLoss` has zero in-window coverage for 10 of 25
  companies** (9 never report the tag: BAC, COP, CVX, GS, JPM, MRK, OXY, PFE,
  XOM; plus JNJ, whose last such filing predates the window). SLB has partial
  in-window coverage. Any feature assuming this concept exists universally
  silently loses 40% of the universe.
- **Tags migrate mid-window** (`NetIncomeLoss`→`ProfitLoss` for MA/OXY;
  `OperatingIncomeLoss`→`ProfitLoss` for SLB; post-ASU-2016-18 cash-tag
  migrations; equity-tag variants for V/UNH; bank cash under
  `CashAndDueFromBanks`). Features must resolve **concept families**, not
  single tags — but **the alternate tags are documented, not ingested.**
  `ProfitLoss` and the alt cash/equity tags are absent from
  `data/fundamentals.parquet`'s 13 concepts and from `ingest_fundamentals.py`'s
  `CONCEPTS`, so `features.py` reads them offline from the cached
  `data/raw/companyfacts/*.json` instead. Values obtained that way sit
  **outside** the validated WARN table above; closing the gap needs a free,
  EDGAR-only re-ingest.
- **MA's only in-window `NetIncomeLoss` rows are DEF 14A proxy
  compensation-table disclosures** — form filtering (10-K/10-Q/8-K only) is
  required, not optional.
- **Revenue aliases are not one-per-bank:** `RevenuesNetOfInterestExpense` is
  used by **GS and JPM**, and eight tickers carry a multi-alias WARN. Do not
  special-case a single ticker.
- **Restatements are preserved as separate rows**, so point-in-time
  correctness depends on `pit.value_as_of()` rather than the most recent
  value. Using restated figures as if they were knowable at the original
  filing date is one of the look-ahead-bias modes `DISCOVERY.md` §5 names
  explicitly.

### 5.7 Price data: adjustment semantics and an unresolved source caveat

- **Split-adjusted, NOT dividend-adjusted.** `data/prices.parquet` stores raw
  OHLC; Yahoo's dividend-adjusted `adjclose` is deliberately not stored, to
  keep open/high/low/close internally consistent. Adjustment verified against
  NVDA's real 10-for-1 split (effective 2024-06-10): the close series is
  continuous across the split date and Yahoo's own `events.splits` payload
  confirms the 10:1 ratio.
- **Consequence for the excess-return target, stated plainly:** because every
  name in the universe average also excludes dividends, most of the systematic
  price-vs-total-return gap cancels in the subtraction — **but it does not
  cancel cross-sectional differences in dividend yield.** This universe spans
  very different yield profiles (XOM, CVX, JNJ, PG, KO, MCD vs. AAPL, GOOGL,
  NVDA), so a high-yield name carries a small systematic *negative* bias in
  its measured excess return and a low-yield name a small positive one,
  entirely independent of anything in its filings. **The magnitude of this
  bias has not been quantified.**
- **Source caveat — open owner-attention item.** The ratified example source
  (Stooq) turned out to be bot-gated (JavaScript proof-of-work;
  `robots.txt` `Disallow: /`). The ingestion agent correctly refused to build
  a bypass and fell back to Yahoo Finance's free keyless chart endpoint for
  all 25 tickers. **Yahoo's `robots.txt` also disallows automated access and
  Yahoo publishes no terms authorizing this use.** This is **disclosed, not
  resolved** — it is the owner's call whether to accept it as a documented
  exception or swap in a licensed feed. The parquet carries a `source` column,
  so swapping providers costs a re-ingest and nothing else.
- **Known coverage gap:** one missing day, HD 2026-07-21 — the upstream
  response carries null OHLC for it (verified against the raw cached JSON —
  not a parsing bug). **In `data/prices.parquet` that row is absent, not
  present-with-NaN**: HD has 929 of the window's 930 trading days and the
  file contains zero null-close rows anywhere. Guard on missing dates per
  ticker, not on `.isna()`. Every other ticker has all 930 days.

### 5.8 Process limitations

- **API spend is frozen at $33.51, permanently.** This is why known label
  defects are documented rather than fixed.
- **Agent work is not human review.** All labeling, auditing, adjudication,
  red-teaming, and documentation in this project was produced by models. The
  owner's personal judgment appears in the decision log (`HANDOFF.md` §3) and
  in the 104 spot-check rulings (§4.6) — nowhere else.

---

## 6. Evaluation methodology and results

### 6.1 Methodology (drafted — this part is settled)

The Phase C evaluation is a **walk-forward, expanding-window backtest of a
screening score against a numeric-only baseline**, on the identical target and
identical folds. Its non-negotiable disciplines, all enforced in code and
regression-tested by `test_phase_c_leakage.py`:

- **Sorted by public availability (`filing_date`), never `report_date`;
  expanding window; never a random shuffle.** Each fold's training set is
  every observation strictly before that fold's test quarter.
- **Point-in-time numeric fundamentals only**, via `pit.value_as_of()`.
- **Target:** forward excess return — the subject company's return over the
  ~63 trading days starting the first trading day *strictly after*
  `filing_date`, minus the equal-weighted average of the identical-window
  return across all 25 universe tickers (owner-ratified 2026-08-18). Carries
  the dividend caveat in §5.7.
- **Baseline:** a numeric-fundamentals-only model, same walk-forward scheme,
  same folds, same target, same library — so missing-value handling is
  identical and confers no advantage on the text-augmented model.
- **Per-fold spreads are reported, never a single point estimate.**
- **Metrics are screening diagnostics, not trading results:** per-fold Spearman
  rank correlation between predicted score and realized forward excess return,
  and a per-fold top-vs-bottom-quintile spread of *realized* excess return.
  No position sizing, no execution, no transaction costs, no portfolio
  simulation exists anywhere in this repository.

**Two measurement caveats that must travel with any result from this harness:**

1. **Filing-level rows are not independent bets.** The unit of observation is
   the filing, not the company-quarter; most companies file an 8-K earnings
   release and then a 10-Q/10-K one to two days later, and those two rows'
   63-trading-day forward windows overlap by 61–62 of 63 days. Treat every N
   as roughly **half** that many independent company-quarter observations.
   Any `spearman_p` not explicitly labeled `_dedup` is **anti-conservative**.
2. **Several text features are near-perfect proxies for SEC form type**
   (8-Ks structurally cannot carry RISK_FACTORS or MDA chunks), so a raw
   feature-importance ranking cannot distinguish "the text matters" from "the
   model detected which form this is." A 10-Q/10-K-only form-controlled
   ablation exists for exactly this reason and must be read alongside any
   importance claim.

Plus, from §4.2: **every red-flag-derived feature inherits the measured
red-flag error rate, quoted with its basis** (36.6% sample-pooled exact-set /
25.0% Tier C base-rate exact-set / 7.5% per-category), stated next to any
red-flag feature-importance or ablation claim.

### 6.2 Results (walk-forward backtest, Phase C, **owner read: GO, diagnosis-scoped, 2026-08-18**)

**Backtest vintage:** `data/backtest_report.md`, generated 2026-08-18 20:53. This is the vintage the owner's GO decision was based on.

**Walk-forward scheme and data:** Expanding-window walk-forward backtest sorted by `filing_date` (public availability date, never `report_date`), with a 6-quarter burn-in (2023 Q3 – 2024 Q4, 274 observations) before the first test fold. Each fold's training set contains every observation strictly before that fold's test quarter; the test set is exactly that calendar quarter. **This scheme enforces temporal ordering and prevents look-ahead bias.** The evaluation spans 6 folds over 2025Q1–2026Q2, with **581 total observations** (49 dropped from the 630-observation feature set for lacking complete 63-trading-day forward windows as of this snapshot).

**Baseline and comparison model:** A numeric-fundamentals-only model (10 features: `log_total_assets`, `leverage_liabilities_to_assets`, `equity_to_assets`, `cash_to_assets`, `net_margin`, `operating_margin`, `operating_cashflow_to_revenue`, `revenue_yoy_growth`, `net_income_yoy_growth`, `eps_diluted_yoy_growth`), evaluated on the identical walk-forward scheme, identical folds, identical target, and same library (XGBoost). The text+numeric model uses all 10 numeric features plus 22 text-derived features.

**Target definition:** Forward excess return — the subject company's total return over approximately 63 trading days starting the first trading day strictly after `filing_date`, minus the equal-weighted average of the identical-window return across all 25 universe tickers. Owner-ratified 2026-08-18. **Dividend caveat (§5.7):** both numerator and denominator use split-adjusted closes (NOT dividend-adjusted). This is a common-mode bias across the panel, but it systematically understates total return more for high-dividend-yield names (PG, KO, MCD, XOM, CVX, JNJ) than for low-yield names (AAPL, GOOGL, NVDA), introducing a small systematic bias in the measured excess return entirely independent of filing content. The magnitude of this bias has not been quantified.

**Non-independence caveat (critical for reading the tables below):** The unit of observation is the filing, not the company-quarter. Most companies file an 8-K earnings release and then a 10-Q/10-K one to two days later, each becoming its own observation with entry dates 1-2 trading days apart. Their 63-trading-day forward return windows overlap by 61–62 of 63 days. Treat every N below as roughly **half** that many independent company-quarter observations. The dedup-IC columns below address this by clustering same-ticker filings within 5 calendar days and keeping one per cluster.

---

#### Numeric-only baseline: per-fold Spearman IC and quintile spread (RAW and DEDUP)

| Test Quarter | N train | N test | IC (raw) | IC (dedup) | Spread (raw) | Spread (dedup) | N dedup |
|---|---|---|---|---|---|---|---|
| 2025Q1 | 274 | 52 | 0.1856 | 0.2329 | 0.0973 | 0.1000 | 44 |
| 2025Q2 | 326 | 52 | 0.2446 | 0.3292 | 0.1465 | 0.1729 | 40 |
| 2025Q3 | 378 | 52 | 0.2216 | 0.1921 | 0.0489 | 0.0137 | 39 |
| 2025Q4 | 430 | 52 | -0.3075 | -0.1773 | -0.1586 | -0.0911 | 37 |
| 2026Q1 | 482 | 53 | -0.0150 | -0.0169 | 0.0041 | -0.0112 | 45 |
| 2026Q2 | 535 | 46 | -0.0597 | 0.0233 | -0.0111 | 0.0062 | 32 |
| **Cross-fold** | — | — | **mean=0.0449, std=0.1956** | **mean=0.0972, std=0.1708** | **mean=0.0212, std=0.0965** | **mean=0.0318, std=0.0841** | — |

#### Text + numeric (augmented): per-fold Spearman IC and quintile spread (RAW and DEDUP)

| Test Quarter | N train | N test | IC (raw) | IC (dedup) | Spread (raw) | Spread (dedup) | N dedup |
|---|---|---|---|---|---|---|---|
| 2025Q1 | 274 | 52 | 0.1196 | 0.1054 | 0.0275 | 0.0217 | 44 |
| 2025Q2 | 326 | 52 | 0.2290 | 0.3214 | 0.1390 | 0.1693 | 40 |
| 2025Q3 | 378 | 52 | 0.1956 | 0.1522 | 0.0704 | 0.0508 | 39 |
| 2025Q4 | 430 | 52 | -0.2556 | -0.1591 | -0.0602 | -0.0006 | 37 |
| 2026Q1 | 482 | 53 | 0.0179 | -0.0173 | -0.0009 | -0.0232 | 45 |
| 2026Q2 | 535 | 46 | 0.0692 | 0.1224 | 0.0062 | -0.0052 | 32 |
| **Cross-fold** | — | — | **mean=0.0626, std=0.1591** | **mean=0.0875, std=0.1485** | **mean=0.0303, std=0.0622** | **mean=0.0355, std=0.0642** | — |

---

#### Key finding: sign-unstable, fragile result

The text-augmented model's cross-fold IC deltas (text minus numeric) **disagree in sign** between raw and deduplicated bases:

- **Raw IC delta:** mean +0.0177 (std 0.0630), positive in 3/6 folds
- **Dedup IC delta:** mean -0.0097 (std 0.0677), positive in 2/6 folds

Neither mean is distinguishable from zero. The reversal between the two measurements is **the finding itself: fragility, not a direction.** The per-fold rows show that IC swings from +0.23 to -0.31 on both models; at this scale (25 companies, ~12 quarters, ~50 effectively-independent observations per fold), fold-to-fold noise dominates any signal.

**Read the per-fold rows, not the means.** The cross-fold variance is the honest summary at this sample size (project-standing rule, `DISCOVERY.md` §5).

**Dedup columns are the more defensible read.** Raw p-values are anti-conservative because filing-level rows are not independent. Company-quarter dedup keeps one row per cluster (same ticker, filings within 5 calendar days; on same-day filings, form-aware tie-break: 10-Q/10-K first, then accession). Of the 581 observations, 454 unique clusters exist (327 singletons, 127 two-filing pairs). The dedup IC values above are computed on the same fitted predictions, restricted to one row per cluster. `data/backtest_report.md`'s "Company-quarter deduplication" section documents the full methodology and verifies the measured (not asserted) independence of the pairs: same-day pairs (66 of 127) have identical target values; other pairs (61 of 127) differ by median 0.0191 vs. cross-sectional std 0.1154.

---

#### Form-controlled ablation: 10-Q/10-K filings only

Text features including `share_chunks_risk_factors`, `share_chunks_mda`, `share_chunks_ex99_press_release`, and `redflag_any_rate_press` are near-perfect proxies for SEC form type: 8-Ks structurally cannot carry RISK_FACTORS or MDA chunks, and press-release text comes from 8-K exhibits almost exclusively. To test whether the text model is detecting form type rather than filing content, the analysis was re-run on 10-Q/10-K filings only (8-Ks dropped, 275 observations vs. 581 full-sample):

| Test Quarter | N test (10-Q/10-K only) | IC delta (raw, form-controlled) |
|---|---|---|
| 2025Q1 | 25 | -0.2223 |
| 2025Q2 | 25 | 0.0992 |
| 2025Q3 | 25 | -0.0923 |
| 2025Q4 | 25 | 0.0992 |
| 2026Q1 | 25 | 0.0846 |
| 2026Q2 | 21 | 0.1455 |
| **Cross-fold mean** | — | **0.0190 (std 0.1315, positive in 4/6 folds)** |

**Per-fold N is small here (21–25 per fold).** Read this result as a directional check on the form-type confound, not a precise estimate. The form-controlled mean IC delta (0.0190) is very close to the full-sample raw delta (0.0177), which is consistent with form type not dominating the feature importance rankings — but the small per-fold N means neither result is distinguishable-from-noise at this scale.

---

#### Red-flag feature reliability

Every red-flag-derived feature (all 6 `redflag_*` features) inherits the red-flag label error rate documented in §4.2: **36.6% sample-pooled exact-set error (63.4% agreement, 146/399, 95% CI [58.6%, 68.0%])** on the spot-check sample. The base-rate-representative figure is **25.0% exact-set error (75.0% agreement on Tier C, 95% CI [58.9%, 86.2%])**, or **7.5% per-category error (92.5% agreement, per-category basis)**. Any claim about red-flag feature importance, feature ablation effect, or signal contribution must state which error rate applies (sample-pooled vs. Tier C vs. per-category) **next to the number**, per `RED_FLAGS_LIMITATION.md` binding implication #1.

---

#### Owner decision and Phase D implications

**Owner's go/no-go (2026-08-18, verbatim):** "GO, diagnosis-scoped."

The owner personally read `data/backtest_report.md`'s per-fold tables (2026-08-18 20:53 vintage) and selected **ROADMAP Phase C outcome (2): proceed to Phase D scoped toward diagnosing which categories/companies drive the mixed, sign-unstable signal — not depth for its own sake.**

This decision activates:
1. **Phase D diagnosis (in progress):** feature-family ablations, per-company/sector decomposition, fold sensitivity analysis — all local, at $0 cost. Deliverable: `data/diagnosis_report.md` (red-team review pending before treated as real).
2. **Phase D fine-tune (optional, un-launched):** is now available under this GO, but requires the owner's explicit "run the fine-tune" in chat to actually execute. It occupies the owner's Mac for an estimated 15–39 hours (`finetune/MLX_FEASIBILITY.md`).

---

#### Honesty rule applied

Per the pre-committed honesty rule (`DISCOVERY.md` §5, ratified before any result existed): **the text-augmented model does not beat the numeric-only baseline by a margin larger than fold-to-fold noise.** The honest conclusion, stated plainly: **the text signal didn't help here — it showed sign-flipping and fold-instability rather than consistent directional benefit.** This is a legitimate research result for this project. The go/no-go gate was designed to accept it, and outcome (2) was selected to diagnose what the mixed signal means rather than claim victory and move forward.

---

## 7. Fine-tuned model

> ## 🚧 GATED TODO — whether a fine-tuned model exists at all
>
> **As of 2026-08-18 no model has been fine-tuned, no checkpoint exists, and
> no weights have been downloaded anywhere in this repository.** Phase D
> **is now unlocked by the §6 GO decision** but remains **not launched**: it
> happens only if the owner explicitly commands "run the fine-tune" in chat.
> The owner's `finetune/MLX_FEASIBILITY.md` read suggests feasibility is
> narrow (batch_size 1, ~15–39 hours per run) — the owner decides whether
> that investment is worth the exploratory value.
>
> **Do not fill this section in from the scaffolding.** A dry-run harness is
> not a model, and an eval script with synthetic predictions is not an
> evaluation.
>
> **What is settled and may be stated now (planning only, no results):**
>
> - **Planned base model:** `Qwen/Qwen2.5-7B-Instruct`, **Apache-2.0
>   confirmed live 2026-08-18** against the HF model page, the API metadata,
>   and the repository's own unmodified `LICENSE` file — not gated, no
>   appended acceptable-use policy (`finetune/MODEL_CHOICE.md`).
> - **Planned method:** local MLX 4-bit QLoRA on the owner's M5 Mac at $0.
>   GPU rental is a fallback only, is **NOT pre-approved**, and would need its
>   own explicit owner sign-off.
> - **Feasibility is narrow, and the numbers are estimates, not measurements**
>   (`finetune/MLX_FEASIBILITY.md`): feasible only at `batch_size 1` @ seq
>   2048 with gradient checkpointing (`config.yaml`'s `batch_size: 4` will not
>   fit in 16 GB); wall-clock ~15–39 h for 3 epochs — **not the overnight run
>   the roadmap assumed**; token counts are ±20% estimates because no
>   tokenizer could be loaded offline.
> - **Known traps that would invalidate a naive port** and must be handled
>   before any run: `lora_alpha` has no MLX equivalent (a naive copy changes
>   effective adapter strength ~10×); `nf4` / paged optimizers / double-quant
>   do not exist in MLX; the prepared JSONL shape is not a format `mlx-lm`
>   accepts; and `mlx-lm` truncates the **tail** of over-length sequences —
>   which is exactly where the JSON answer lives, affecting an estimated 6.34%
>   of eval rows.
>
> **When (and only when) a fine-tune has actually run, this section must
> record:**
>
> - the exact base model, quantization, adapter config, and the **measured**
>   token counts that replaced the estimates above;
> - the eval methodology — the held-out 1,010-row split, its connected-
>   component leakage rule (§3.7), and the fact that it tests generalization
>   to **unseen text, not to the future**;
> - **the known weak categories from that eval, named individually**, with
>   per-class support next to each — and `guidance_direction=WITHDRAWN` (n=1),
>   `section_type=8K_BODY` (n=8) and the whole `distress_tier` explicitly
>   marked **"insufficient support"** rather than folded into an aggregate
>   (§4.5);
> - results reported **alongside** the Phase C numeric baseline, **never as a
>   replacement for it**, with the same measurement-next-to-the-number rule as
>   §6;
> - the honest note that with prompt masking on, one epoch carries only
>   ~170K loss-bearing tokens across 5,736 examples — a small training signal,
>   and a reason to expect modest gains.

---

## 8. Reproducibility

- **Deterministic and re-runnable at $0:** ingestion, extraction, chunking,
  fundamentals ingestion, price ingestion, feature building, and the backtest
  all run from local caches or free public endpoints. Chunk and paragraph IDs
  are content-derived, so re-running `chunk.py` on the same input regenerates
  identical IDs.
- **Not re-runnable at all:** the label bootstrap. `data/labels.parquet`
  cannot be regenerated under the spend freeze, which is why it is treated as
  a frozen artifact rather than a build output.
- **The headline agreement rates are reproducible** from
  `spotcheck/combined_judgments.csv` via
  `python3 spotcheck/compute_agreement.py --input spotcheck/combined_judgments.csv --format csv`;
  the command and run date are stamped in `spotcheck/agreement_report.txt`'s
  header.

---

## 9. Review and sign-off

> ## 🚧 GATED TODO — Phase E red-team sign-off
>
> **This card has not been reviewed.** Phase E requires an independent
> `red-team-reviewer` pass over this document and the work it describes,
> before it is treated as final. Nothing below has been filled in.
>
> | Item | Status |
> |---|---|
> | `red-team-reviewer` pass over this model card | ⬜ Not requested |
> | Findings raised / resolved (counts + severities) | ⬜ — |
> | Charter-compliance check (non-goals §1: no trading, no advice, no return claims, every number with its measurement) | ⬜ — |
> | Verification that every number in this card was re-derived from its artifact, not copied | ⬜ — |
> | Verification that no gated section was filled in speculatively | ⬜ — |
> | Reviewer, date | ⬜ — |
> | Owner acceptance, date | ⬜ — |
>
> **The definition of done** (`HANDOFF.md` §6 Step 6): a model card /
> limitations document exists, reviewed by `red-team-reviewer`, **that a
> reader with no other context could use to understand exactly what this
> system does and does not support claiming.** Until every gate above is
> closed, this file does not meet that bar and must carry its DRAFT banner.

---

## 10. Where the numbers in this card come from

| Claim area | Canonical source |
|---|---|
| Non-goals (§1) | `DISCOVERY.md` §7; `HANDOFF.md` §1 |
| Corpus counts, labeling config, spend (§3) | `HANDOFF.md` §2; `data/full_run_report.md` FINAL section |
| Agreement rates, tiers, provenance (§4.1, §4.2, §4.6) | `spotcheck/agreement_report.txt`; `spotcheck/combined_judgments.csv` |
| Red-flag failure, error decomposition, error-rate bases (§4.2) | `RED_FLAGS_LIMITATION.md` |
| Config sensitivity 22.2% (§4.3) | `HANDOFF.md` §2; `DISCOVERY.md` §6; `data/full_run_report.md` FINAL section |
| Distress-class emptiness (§4.4) | `RED_FLAGS_LIMITATION.md` distress addendum; `HANDOFF.md` §3 |
| All limitations (§5) | `LIMITATIONS.md` — the full write-up |
| Self-identification channel (§5.5) | `REDTEAM_WEEK3.md` finding #2; `DISCOVERY.md` §5 |
| Price adjustment + source caveat (§5.7) | `data/PRICES_NOTES.md` |
| Backtest methodology (§6.1) | `backtest.py` / `features.py` module docstrings; `test_phase_c_leakage.py` |
| Fine-tune plan and feasibility (§7) | `finetune/MODEL_CHOICE.md`; `finetune/MLX_FEASIBILITY.md`; `finetune/SPLIT_DESIGN.md` |
