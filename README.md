# FinScreen

FinScreen is a solo-owner research pipeline for US equity filings. It pulls
SEC EDGAR filings for a sector-stratified universe of large-cap US companies
(136 members at each annual reconstitution date, 244 distinct filers across
2016-07-01 to 2026-07-01), extracts MD&A, Item 1A risk-factor and earnings
press-release sections, and labels them for sentiment, forward guidance
direction and disclosure red flags. The labeler is a Qwen2.5-7B student model
fine-tuned locally with 4-bit QLoRA on Claude teacher labels. The research
question is narrow and falsifiable: does anything in the filing text add
screening information on top of a numeric-only baseline, measured by an
expanding-window walk-forward backtest sorted by public filing date. The
first, smaller run (25 companies) answered "no fold-robust text signal." The
second, larger run has finished labeling and has not yet been backtested.

## What this is not

- **Not a trading bot.** No component in this repository places, queues, or
  recommends a trade. There is no brokerage integration and no order path.
- **Not investment advice.** A screening score is a research signal, never a
  buy, hold or sell recommendation.
- **No live capital**, in any phase, ever.
- **No return claims and no "beats the market" language.** Every performance
  number is reported next to exactly how it was measured. Nothing in this
  repository estimates an expected return.

These are contractual non-goals, not current limitations. They are stated in
`HANDOFF.md` §1 and inherited unchanged by the expanded experiment
(`EXPANSION_PLAN.md` §1). A request to add trade execution, real-money
integration, or promotional performance claims conflicts with the charter.

Three hard rules govern everything else here:

1. **No further Anthropic API spend.** The first study's labeling cost $33.51
   and was frozen (`HANDOFF.md` §5). One later re-label under rubric v1.2 was
   separately authorized and cost about $24.92 plus $0.0014 for a completion
   row (`HARDENING_PROGRESS.md`). That run drained the account, the freeze is
   re-sealed, and no future API call is authorized. All labeling in the
   expanded run cost $0 because it ran on the local student model.
2. **Red-flag labels are exploratory and disclosure-only.** They are not
   gate-bearing and no confirmatory claim may rest on them
   (`RED_FLAGS_LIMITATION.md`, and the demotion record below).
3. **Model-rater agreement is not human validation of ground truth.** Every
   agreement rate here came from one model re-judging another model's labels,
   a third model resolving disputes, and the owner ruling a small escalated
   subset. That measures model consensus, not label correctness.

## Where the project stands (2026-09-07)

Two corpora exist. **E1** is the original 25-company study, complete.
**E2** is the expanded study ratified 2026-08-20, currently between labeling
and features.

| Phase | What it did | State |
|---|---|---|
| E1 (whole study) | 25 companies, 884 extracted sections, 6,747 chunks, 6,746 labeled by Claude; features and walk-forward backtest built and run | **Complete.** Reports: `data/full_run_report.md`, `data/backtest_report.md`, `data/features_report.md`, `data/diagnosis_report.md` |
| F1 universe | `hybrid136`: sector-stratified top-K by `dei:EntityPublicFloat` with annual point-in-time reconstitution; 136 members per date, 244 distinct CIKs, 8 sectors, two strata (core / extension) | **Complete.** `data/E2_UNIVERSE_REPORT.md`, table at `data/universe_e2_candidates/hybrid136.csv` |
| F2 ingestion | Corpus window 2015-07-01 to 2026-08-31. 45,632 filings enumerated (45,545 accession rows plus 87 co-registrant rows), 20,521 documents cached (42 GB), 622,661 fundamentals rows, 1,960,738 price rows across 213 CIKs | **Complete.** `data/F2_INGESTION_REPORT.md`, ledger `F2_PROGRESS.md` |
| F2.5 hardening | Six items H1 to H6: positive controls, pre-registered specification and honest minimum detectable effect, labeler-attenuation measurement, document-selection audit, stopping rule, prior-work write-up | **Complete.** `HARDENING_PROGRESS.md`, reports under `data/hardening/status/` |
| F3 extraction | 30,475 extraction attempts produced 28,900 sections, then a fix package rebuilt the corpus to 29,097 rows | **Complete.** `F3_PROGRESS.md`; corpus `data/filings_e2_v2.parquet` (sha256 `15853e9f…`) |
| F4 labeling | The fine-tuned student labeled every chunk: 317,081 chunks across 24 chronological segments, 0 parse failures, 0 finish-reason truncations, 0 API calls, $0 | **Complete.** `data/f4/labels_e2_v1.parquet` (sha256 `f236f421…`), close-out `data/f4/status/F4_campaign.md` |
| G2 spot-check | Blind model rater plus adjudicator over a pre-registered stratified draw, with the owner personally ruling 39 escalated rows and 20 probe rows | **Ruled 2026-09-07.** `data/f4/g2/G2_FINAL_REPORT.md` |
| F5 features and backtest | Build E2 features, run the pre-registered walk-forward in three heads | **NEXT. Not started.** Plan: `F5_PLAN.md`. Rule: no E2 information coefficient is computed before gate G3 ratifies the pre-registration (benchmark, folds, primary metric, stopping rule) |
| F6 diagnosis and docs | E2 diagnosis, independent red-team pass, model card and limitations updated for E1 plus E2 | Not started. Gate G4 is the owner's final read |

### What G2 actually measured

Gate G2 asked whether the student's labels are good enough to build features
on. The 0.85 agreement bar was pinned before any rating. Results, from
`data/f4/g2/G2_FINAL_REPORT.md` §1:

- `sentiment`: 293/337 = 86.94% [82.93, 90.13]. **INDETERMINATE** at the 0.85
  bar. It proceeds, but the measured chunk-level error is a first-class input
  to every F5 number derived from it.
- `guidance_direction`: 115/119 = 96.64% [91.68, 98.69]. **PASS** at the 0.85
  bar, on the NONE mass. It may never be quoted without two escorts,
  `guidance_active_precision` 68.67% [58.17, 77.55] (n_eff 84.8) and
  `guidance_false_none_rate` 0/80 [0, 4.58], plus §0 of that report. The
  owner's reading is that much of the 68.67% reflects a rubric with no label
  for newly issued, directionless guidance, not hallucinated guidance.
- `red_flags`: 112/400 = 28.0% exact-set error [23.8, 32.6]. No bar applies,
  because the family had already been demoted on 2026-08-27.

The owner ruled the gate "proceed under the ladder," and separately ruled
"extend": the three unseen extension sectors get labeled, but those labels
enter F5 only after their own spot-check, and nothing in G2 speaks to them.
All of the above is model consensus with an owner-ruled escalation layer, not
human validation of ground truth.

### Standing limitations that travel with every number

Pulled from the risk registers, not invented. Each carries its measurement and
its source, and each must travel with any number derived from it.

| Limitation | What was measured | Source |
|---|---|---|
| Red-flag config sensitivity | Across two labeling configurations on the same 4,219 E1 chunks, `red_flags` changed on 935 of them (**22.2%**), against `sentiment` 3.6%, `guidance_direction` 0.9%, `distress_tier` 0.7%. Flag counts are partly a function of how the model was asked. | `HANDOFF.md` §2, `data/full_run_report.md` |
| The E1 red-flag spot-check failed its bar | Exact-set agreement **63.4% [58.6, 68.0]** against a 0.70 lower-bound bar, pooled over a sample that deliberately oversamples rare and contested text. The only base-rate-representative slice is Tier C at **75.0% [58.9, 86.2]**, which is 25.0% error on 9 of 36 chunks. Always report the basis next to the rate. | `RED_FLAGS_LIMITATION.md` (canonical) |
| The rubric v1.2 teacher was itself wrong on red flags | 84 of 200 chunks, **42.00% [35.37, 48.93]**. That fired a pre-registered demotion, so the E2 red-flag family is exploratory and disclosure-only. | `data/hardening/spotcheck_v12/`, ruled 2026-08-27 |
| Self-identification channel | Filing text names its own company in **26.8%** of chunks by a strict measurement and **46.0%** by a loose one. Both are cited so neither is mistaken for the other. A look-ahead risk mitigated only by prompt instruction. | `REDTEAM_WEEK3.md` finding #2, `HANDOFF.md` §7 |
| Price provenance | Prices come from Yahoo's keyless chart endpoint, after Stooq turned out to be bot-gated. Split-adjusted, **not** dividend-adjusted. | `data/PRICES_NOTES.md` §1 |
| E2 censoring residual | Selection is survivorship-free: membership uses only filings public before the reconstitution date, and declining companies stay in-sample until they stop filing. Outcomes are not. Yahoo generally has no data for delisted tickers, so forward returns right-censor at delisting, which is informative censoring. 32 of 244 members have no usable prices, which in membership-time is 95 of 1,496 member-date cells (**6.35%**), concentrated in the earliest cohorts (14.0% in 2016, 0% in 2026) and in energy (16.4%). | `EXPANSION_PLAN.md` §2c, `data/F2_INGESTION_REPORT.md` §0(c) and §2 |
| Labeler contamination | The student was fine-tuned on E1 text, and with the same adapter it behaves measurably differently on E2: flag incidence drops 9, 14 and 7 points by section type, and the guidance key is omitted 33% of the time on E1 versus 51% on E2. Every E2 result must be reported with and without the train-overlap set. | `data/f4/status/F4_campaign.md` §2, `EXPANSION_PLAN.md` §3 |
| E1 and E2 backtest numbers are numerically incomparable | E2 redefines the excess-return benchmark for a churning 136-name universe. State this wherever both appear. | `EXPANSION_PLAN.md` §3.3 |
| The E1 result was mixed, and that is the honest summary | Over six expanding-window folds against the numeric-only baseline, the raw cross-fold mean information-coefficient delta was **+0.0177** and the deduplicated version was **-0.0097**. The sign is not stable across folds, so the text signal did not clearly help. | `data/backtest_report.md`, `data/diagnosis_report.md` |
| A consumer trap in the E2 labels | 2,826 rows carry a guidance value on a section where guidance is not applicable, so any consumer must filter on `guidance_applicable`. | `data/f4/status/F4_campaign.md` |

## How to read this repository

Read in this order. Files on disk beat any summary, including this one.

1. **`README.md`** (this file) for orientation.
2. **`RESUME_HERE.md`** for the current state in one screen: what is running,
   what is blocked, what must not be re-run. Written for a session picking
   the project up cold.
3. **`HANDOFF.md`** for depth: §1 charter, §2 exact state, §3 the dated
   decision log of every owner ratification, §4 incidents compressed to
   standing rules, §5 spend, §7 hard rules, §8 file map. Where any other
   document conflicts with `HANDOFF.md`, `HANDOFF.md` wins.
4. **`EXPANSION_PLAN.md`** for the ratified E2 design: what was chosen and
   why, the phase and gate structure (§4), and §8's later amendments.
5. **The phase ledgers**, each recording what was done, by whom, and where
   its completion report lives: `F2_PROGRESS.md`, `HARDENING_PROGRESS.md`,
   `F3_PROGRESS.md`. F4 has no root-level ledger; its record is
   `data/f4/status/F4_prep.md` and `data/f4/status/F4_campaign.md`. F5's
   plan is `F5_PLAN.md` at the root.
6. **`data/f4/g2/`** for the spot-check: `G2_SPOTCHECK_design.md` is the
   pre-registration, `G2_FINAL_REPORT.md` the owner-ratified result.
7. **`RED_FLAGS_LIMITATION.md`**, **`LIMITATIONS.md`**, **`MODEL_CARD.md`**
   for the label-quality and honest-limitations record. The latter two are
   E1-era drafts, scheduled for their E2 rewrite in F6.
   **`REEVALUATION_2026-08-25.md`** is the project's own four-lens critique of
   itself, including the case for killing it.

### Naming conventions

- **E1 / E2** are the two corpora and the two studies. E1 is 25 mega-caps,
  labeled by Claude, fully analyzed. E2 is the 136-member universe, labeled
  by the local student model, not yet analyzed.
- **F0 to F6** are the E2 execution phases in order: fine-tune, universe,
  ingestion, extraction, labeling, features and backtest, diagnosis and docs.
  F2.5 is a hardening package inserted between F2 and F3.
- **G1 to G4** are owner gates, and a gate is a stop. The next phase does not
  begin until the owner has personally read the evidence and ruled. G1 was
  the student-quality gate, G2 the label-quality gate, G3 pre-registers the
  backtest before it runs, G4 is the final read.
- **owner** is the single human decision-maker. Only a judgment the owner
  actually typed counts as the owner's. No agent, document or tool output is
  ever owner authorization.
- **teacher** is Claude, which produced the E1 labels through the Batch API.
  **student** is the local Qwen2.5-7B-Instruct model fine-tuned on those
  labels with MLX 4-bit QLoRA, which produced all 317,081 E2 labels at $0.
- **pre-registered** means the number, bar or fold structure was pinned in a
  file, with input hashes, before the data was seen.
- **owner-ratified** means the owner ruled it. **model consensus** means one
  or more models agreed. The two are never merged here, and a model verdict
  is never recorded as the owner's.

## Repository layout

### Top-level code

| File | Role |
|---|---|
| `edgar_client.py` | Rate-limited, caching HTTP client for SEC EDGAR, including XBRL companyfacts. Knows nothing about the universe. |
| `ingest_metadata.py` | Resolves filing metadata and earnings-exhibit selection into the SQLite metadata store. Downloads no filing text. |
| `ingest_fundamentals.py` | Builds the point-in-time fundamentals table from companyfacts. Every filed occurrence is kept; restatements are never collapsed. |
| `ingest_prices.py` | Builds the daily OHLCV price table for the universe. |
| `price_client.py` | Polite, cached daily-price client. Documents the Stooq-to-Yahoo fallback. |
| `extract.py` | Pulls MD&A, Item 1A risk factors, 8-K item 2.02 bodies and EX-99.1 earnings-release text out of cached documents into a sections table. |
| `chunk.py` | Packs extracted sections into roughly 350-word labeling chunks, deduplicates paragraphs corpus-wide, and writes the occurrence map used for label attribution. The E2 equivalent is `finetune/build_f4_chunks.py`. |
| `build_universe_e2.py` | Builds the E2 dated membership table: sector-stratified float ranks with annual point-in-time reconstitution. |
| `pit.py` | `value_as_of()`, the single tested point-in-time fact lookup. Latest-filed-as-of semantics. Never "latest value". |
| `features.py` | Joins text-derived signals with point-in-time fundamentals and a forward excess-return target into a feature matrix, plus a feature-by-feature report. |
| `backtest.py` | Expanding-window walk-forward comparison of a text-plus-numeric model against a numeric-only baseline on identical folds. Not a trading simulator: no sizing, execution, costs or portfolio construction. |
| `controls.py` | Positive controls (H1): does a known effect show up at this backtest's exact configuration, and where is the noise floor. |
| `diagnose.py` | Post-backtest diagnosis: which categories and companies drive the signal, feature-family ablations. |
| `e2_report.py` | Renders `data/E2_UNIVERSE_REPORT.md` from what `build_universe_e2.py` measured, so the prose is generated rather than hand-typed and drifting. |
| `spec.py` | The pre-registered feature specification, the two standing zero-information benchmarks and the bootstrap noise anchor, shared by `backtest.py` and `diagnose.py`. |
| `build_batch_requests.py` | Builds Batch API request files from the rubric. Its `SYSTEM_PROMPT` is a hand-synced restatement of `labeling_rubric.md`. Retired: no further labeling runs. |
| `submit_labeling_batch.py` | The only file that ever called the paid Batch API. Kept for its safety guards and as an audit trail. Do not run its `--full*` modes. |
| `labeling_rubric.md` | The authoritative labeling spec, v1.2. Defines sentiment, guidance direction, the red-flag taxonomy, distress tier, modality, the applicability matrix, and the rule that labels describe only what the text says. |

### `finetune/`

The local fine-tune and the labeling campaign. `split.py` and
`build_splits_v12.py` build leakage-safe train and eval splits by connected
component over shared paragraphs and filings, and `check_leakage.py` proves no
chunk, paragraph or accession straddles the split. `prepare_dataset.py` and
`convert_to_mlx.py` produce the training data. `train_qlora.py` with
`config_mlx.yaml` runs the 4-bit QLoRA fine-tune on a 16 GB Apple M5, which
`MLX_FEASIBILITY.md` showed fits only narrowly. `eval.py` scores a checkpoint
against the frozen eval split, `relabel_e1.py` re-labels E1 with the student
for the attenuation measurement, and `label_e2.py` is the campaign runner that
produced all 317,081 E2 labels as resumable, per-row-checkpointed segments.
`runs/` holds the dated training and evaluation run directories.

### `data/`

Generated artifacts, per-phase status reports, and the raw cache. **Most large
artifacts are not in git.** `.gitignore` has the exact list with a reason per
entry: `data/raw/`, the batch request payloads, the derived text and price
corpora, the label parquets, the E2 ingestion outputs, the F3 extraction shards
and the 599 MB E2 corpus, the F4 chunk table (382 MB) and label table (417 MB)
with their per-segment outputs, and the fine-tune datasets and checkpoints.
Every excluded artifact's sha256 is pinned in a committed manifest
(`data/f4/campaign_manifest.json`, `data/f4/g2/draw_manifest.json`,
`data/f3/v2/run_manifest.json`), so provenance survives even though the bytes
do not. `data/raw/` is a cached EDGAR mirror whose documents subtree alone is
42 GB, regenerable by re-running the idempotent ingestion scripts at the cost
of a lot of polite HTTP. The label parquets are the exception: they are not
free to regenerate (E1's cost API spend, E2's cost nine GPU nights), so git is
not a backup for them. The status directories the ledgers point at are `f2/status/`,
`f3/status/`, `f4/status/`, `f4/g2/`, `hardening/status/` and
`reevaluation_2026-08-25/`.

### `.claude/agents/` and `TEAM.md`

This project was built by a roster of specialist Claude agents, each with a job
description in `.claude/agents/`: `data-engineer`, `extraction-qa-engineer`,
`finetune-engineer`, `quant-modeler`, `research-statistician`,
`test-engineer`, `red-team-reviewer`, `compliance-officer`, `docs-writer`,
`ops-scribe`, `tech-council`, `label-auditor`, `label-adjudicator`,
`label-rater-blind`. `TEAM.md` is the org chart, the model-tiering policy and
the operating protocol every agent follows. It also lists the roles
deliberately not created, including marketing and trading operations, because
they would fight the charter.

## Running the tests

The suite is offline: no network calls, no API calls. Dependencies are split
across `requirements.txt` (ingestion, labeling, spot-check),
`requirements-quant.txt` (features and backtest) and
`finetune/requirements-mlx.txt` (the local MLX fine-tune, in its own venv).

```
python3 -m pytest -q
```

Last full run, 2026-09-07 on the owner's machine with every artifact present:
**1,328 passed, 11 skipped, 0 failed** in about four minutes.
`test_phase_c_leakage.py` is slow because it re-reads the full corpus, and
several suites read generated parquet files that `.gitignore` excludes, so a
fresh clone will skip or fail those until the ingestion scripts have run.

The G2 analyzer carries an in-memory self-test of every estimator against
hand-computed values, touching no data files:

```
python3 data/f4/g2/analyze_g2.py --selftest
```

Scripts under `data/f4/g2/` and `data/hardening/` locate the repository root
from their own file location, so they run from any clone.

## Provenance and honesty rules

- **Every number in a report traces to a script and an artifact.** Reports are
  generated from run diagnostics rather than typed by hand, and the important
  ones carry sha256 digests of their inputs. Builders that pre-register a
  measurement freeze their input hashes, so editing a pinned input breaks the
  build on purpose. That is how a documentation edit was caught in September
  2026 (`HANDOFF.md` §4).
- **Model verdicts are labelled as model verdicts.** Every spot-check judgment
  carries a provenance tag naming its source as model-rater, model-adjudicator
  or owner. Agreement rates over model-adjudicated fields measure model
  consensus, not ground truth, and this repository never says otherwise.
- **Spot-check bars are pinned before rating.** The bar, the draw, the seed and
  the stopping rule go to disk first, with hashes. The G2 analyzer exits
  "BLOCKED" until its ratified bars exist, so no one can shop for a bar after
  seeing the numbers. A pre-registered demotion rule fired against the
  project's own interests in August 2026 and was honored.
- **Nothing here is a performance claim.** The one backtest that has been run
  and read produced a mixed, sign-unstable result over six expanding-window
  folds against a numeric-only baseline, and that is how it is reported. The
  E2 backtest has not been run at all.
