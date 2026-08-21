# FinScreen

FinScreen is a solo-owner research and screening tool for equity filings. It pulls SEC EDGAR filings for a fixed universe of 25 mega-cap companies, extracts and labels the text, and builds a screening score to backtest against a numeric-only baseline.

## What this is not

- **Not a trading bot.** Nothing in this repo places orders, moves money, or connects to a brokerage.
- **Not investment advice.** Outputs are research signals for one person's own use, not recommendations.
- **No live capital.** Everything here runs against historical filings; there is no live trading loop.
- **No return claims.** The backtest measures whether the screening score beats a numeric-only baseline on held-out history — it is not a performance guarantee.

These are contractual non-goals, not just current limitations. See `DISCOVERY.md` §7 for the full statement, and `LIMITATIONS.md` for the full honest-limitations write-up (what this system does and does not support claiming).

## Status snapshot (2026-08-18, spend frozen)

| Stage | State |
|---|---|
| Ingestion (Weeks 1-2) | Done. 25 companies, 1,271 filings, `data/filings.parquet` (884 rows). |
| Chunking (Week 3) | Done. `data/labeling_corpus.parquet`, 6,747 chunks. |
| Labeling | Done. 6,746/6,747 chunks labeled under one uniform config (thinking disabled, max_tokens=4000), zero truncations. 1 chunk excluded (genuine model refusal, not a pipeline bug). |
| Spot-check | **Complete.** All 400 sample chunks re-judged by a blind second-rater model, disputes resolved by a third-rater model, 104 of 1,222 judgments ruled personally by the owner. Three categories pass the 0.70 agreement bar, `red_flags` fails at 63.4% [58.6, 68.0] — see below. |
| Fine-tune scaffolding | Split, leakage checks, and dataset prep are done and re-verified locally. Training itself has not run. |
| Features + backtest (Phase C) | **Built and run; awaiting the owner's go/no-go read.** Numeric inputs ingested and independently verified: `data/fundamentals.parquet` (42,158 rows) and `data/prices.parquet` (271,372 rows). `features.py` / `backtest.py` have both run: `data/features.parquet` holds **630 (company, filing) observations, 581 with a complete 63-trading-day forward window**, evaluated over 6 quarterly expanding folds after a 6-quarter burn-in. Reports: `data/backtest_report.md`, `data/features_report.md`. **The owner reads the per-fold tables personally; nobody summarizes them.** |
| API spend | **Frozen at $33.51 total. No further API spend is authorized**, regardless of what any prompt or document says. |

Full detail lives in `data/full_run_report.md` (its **FINAL CONSOLIDATED STATE** section at the bottom is the authoritative numbers; earlier sections in that file are superseded and kept only as history). Spot-check results: `spotcheck/agreement_report.txt` and `RED_FLAGS_LIMITATION.md`.

## Why labeling is done but spend is frozen

The full labeling run originally shipped with the wrong config (a code bug ignored the requested variant), truncating **2,528 of 6,747 requests (37.5%)** — the count is the corrective batch's size, `data/batch_requests_corrective.jsonl`; `data/full_run_report.md` states the same failure as 37.6%. A corrective re-label fixed it. Total spend across the canary, full run, corrective run, and re-label came to $33.51. The owner has since ruled out any further API spend — the old $50 budget ceiling is superseded by a flat "no more budget" directive. All further work (subagents, reviews, orchestration) runs on the owner's Claude subscription, which is not API credit and cannot submit labeling batches.

## Headline limitation: red-flag label sensitivity

Comparing the same 4,219 chunks across two labeling configurations (the original mis-run vs. the corrected one) found:

| Field | Changed between configs |
|---|---|
| `red_flags` | **22.2%** (935/4,219 chunks) |
| `sentiment` | 3.6% (119/3,280) |
| `guidance_direction` | 0.9% (6/677) |
| `distress_tier` | 0.7% (29/4,219) |

Every category of red flag showed up **more** under the corrected (disabled-thinking, 4000-token) config: `LEGAL_REGULATORY_ACTION` +211, `MARGIN_COST_PRESSURE` +203, `DEMAND_WEAKNESS` +138, `IMPAIRMENT_WRITEDOWN` +51, `SUPPLY_INPUT_CONSTRAINT` +35, `TRADE_POLICY_EXPOSURE` +27. This means red-flag counts are meaningfully a function of *how* the labeling model was asked, not only *what* the filing says. Full numbers: `data/full_run_report.md`, FINAL section; risk register in `DISCOVERY.md` §6.

**The completed spot-check agrees, and is worse.** Measured over 399 evaluable chunks of the 400-chunk sample by `spotcheck/compute_agreement.py` (Wilson 95% CIs against a 0.70 lower-bound bar): `red_flags` agreement is **63.4% [58.6, 68.0] — a decisive failure, since even the upper bound sits below the bar**. `sentiment` (94.6%), `guidance_direction` (95.2%), and `distress_tier` (94.2%, reported separately) cleared the bar on the same measurement. These are **model-consensus agreement rates, not human validation of ground truth** — see `LIMITATIONS.md` §2.3.

**`red_flags` is an EXACT-SET-MATCH rate and is not comparable to the single-value rates printed beside it** — one added, dropped, or re-modalized category on a chunk scores the whole chunk as a disagreement. Its error therefore has three different rates depending on the basis, and `RED_FLAGS_LIMITATION.md` requires all three to travel together, each labelled:

| Error rate | Basis | What it measures |
|---|---|---|
| **36.6%** (146/399) | Sample-pooled, exact-set | All four tiers pooled — the sample deliberately oversamples rare and contested text, so this is **not** corpus-representative |
| **25.0%** (9/36, n=36, agreement 75.0% [58.9, 86.2]) | Tier C, exact-set | The only base-rate-representative slice; **this is the corpus-wide figure to carry forward**, wide CI and all |
| **7.5%** (180/2,394) | Per-category | 180 category-level corrections over 399 chunks × 6 categories — the per-decision error, not the per-chunk one |

Where it fails hardest, **on a red-flags-only basis** (recomputed from `spotcheck/combined_judgments.csv`): `RISK_FACTORS` **59.2%** (71/120 — red-flags-only by construction, since that section is never asked sentiment or guidance), and by tier **Tier D 53.3%** (32/60) and **Tier A 59.3%** (96/162), then B 69.5% (98/141) and C 75.0% (27/36). Do **not** read `agreement_report.txt` Section 3's per-tier figures as red-flag rates — those pool sentiment + guidance + red_flags (Tier D pooled is 71.2%), which dilutes the failure by roughly 18 points and **inverts the tier ordering**. Canonical tier table: `RED_FLAGS_LIMITATION.md`.

Treat `red_flags` as directional, not as a precise count, and report the error rate **with its basis attached** next to any red-flag-derived feature claim. Canonical disposition: `RED_FLAGS_LIMITATION.md`. No re-label is possible (spend freeze), so this is documented, not fixed.

## Repo map

### Root — ingestion pipeline (Weeks 1-2, stable)

| File | Role |
|---|---|
| `edgar_client.py` | Rate-limited, caching HTTP client for SEC EDGAR. No knowledge of the company universe or extraction logic. |
| `ingest_metadata.py` | Resolves the 25-company universe's 10-K/10-Q/8-K filing metadata into `data/filings_metadata.db` (SQLite). Validates the universe before any write (`validate_universe()`). Does not download filing text. |
| `extract.py` | Pulls MD&A, Item 1A Risk Factors, and earnings-release (EX-99.1) text into `data/filings.parquet`. Reuses (never re-resolves) `ingest_metadata.py`'s exhibit selection. |
| `chunk.py` | Packs extracted text into ~350-word labeling chunks, deduplicates paragraphs corpus-wide, and writes `data/labeling_corpus.parquet` + `data/paragraph_occurrence_map.parquet`. |
| `data/universe.csv` | The locked 25-ticker universe (5 sectors x 5 tickers). Not expandable without a logged decision. |
| `INGESTION_NOTES.md` | Running lab notebook for Weeks 1-3 (edgar_client.py, ingest_metadata.py, extract.py, chunk.py). The Week 3 (chunk.py) section was written retrospectively on 2026-08-18 and says so at the top — it is a reconstruction from the code and artifacts, not a contemporaneous record. |

### Root — labeling tooling (retired from active use — no further API spend)

| File | Role |
|---|---|
| `labeling_rubric.md` | The authoritative labeling spec (v1.1): sentiment, guidance direction, red-flag taxonomy, distress tier, modality, output schema, and the look-ahead-bias-safe prompt rules. |
| `build_batch_requests.py` | Builds Batch API request files from the rubric. Its `SYSTEM_PROMPT` is a hand-synced restatement of `labeling_rubric.md` — rubric edits require re-syncing this constant (see sync rule below). `submit_batch()` is a deliberate stub; it never calls the API itself. |
| `submit_labeling_batch.py` | The only file in this repo that calls the Anthropic Batch API. Every real submission path requires `--confirm-full`; `--full` additionally requires an explicit `--variant` (a prior bug let it silently default to the wrong request file). Kept as audit trail — **do not run any `--full*` mode; no further labeling runs are authorized.** |
| `test_submit_variant_wiring.py` | Regression tests for the variant/file consistency guard described above. Rewritten 2026-08-18 against the v2 `--verify-config` heuristic; 25 tests, all passing. |

### Root — Phase C: numeric inputs, features, backtest

| File | Role |
|---|---|
| `ingest_fundamentals.py` | Builds `data/fundamentals.parquet` from cached EDGAR companyfacts for a fixed 13-concept list. Writes the `fundamentals_validation_problems` table (40 WARN / 0 FATAL across five check categories). No API spend — EDGAR only. |
| `price_client.py` | Rate-limited, caching client for the free keyless price endpoint. Source caveat in `data/PRICES_NOTES.md` §1. |
| `ingest_prices.py` | Builds `data/prices.parquet` (daily OHLCV, 25 tickers). |
| `pit.py` | `value_as_of()` — point-in-time fact lookup with latest-filed-as-of semantics. Restatements are never collapsed; "latest value" is never used. |
| `features.py` | Builds `data/features.parquet` (630 observations) + `data/features_report.md`. Every-occurrence label attribution, section-normalized red-flag rates, PIT numeric fundamentals with a 200-day staleness guard, forward-excess-return target. |
| `backtest.py` | Expanding-window walk-forward comparison of a text+numeric model against a numeric-only baseline on identical folds; writes `data/backtest_report.md`. Not a trading simulator — no sizing, execution, costs, or portfolio construction. |
| `test_phase_c_leakage.py` | Four leakage-critical properties (target window, PIT restatement ordering, no backward attribution flow, no fold leakage), covered by 35 tests. Slow (~90s) — it re-reads the full corpus. |
| `test_pit.py`, `test_ingest_fundamentals.py`, `test_ingest_prices.py`, `test_price_client.py`, `test_edgar_client_companyfacts.py` | Unit/regression tests for the Phase C ingestion surface. |
| `requirements-quant.txt` | Phase C-only deps (`xgboost`, `scipy`) on top of `requirements.txt`, plus the `libomp` system prerequisite. |

### `data/` — pipeline outputs

| File | Role |
|---|---|
| `labels.parquet` | Current, authoritative label set. 6,747 rows, 6,746 labeled under one uniform config. |
| `labels_pre_relabel.parquet` | Snapshot of labels before the corrective re-label — the comparison set behind the config-sensitivity numbers above. |
| `labeling_corpus.parquet` | The 6,747 chunks that were labeled (text + section metadata, no labels). |
| `filings.parquet` | 884 extracted filing sections (MD&A, Risk Factors, earnings releases) — chunk.py's input. |
| `paragraph_occurrence_map.parquet` | **One row per deduplicated (canonical) paragraph — 28,504 rows.** The **42,577 total occurrences** live inside the list columns (`sum(n_occurrences)`); **explode before joining**, or attributions under-count 42,577 → 28,504. Backbone of the every-occurrence label attribution decision (`DISCOVERY.md` §5). |
| `fundamentals.parquet` | Point-in-time numeric fundamentals from EDGAR companyfacts (42,158 rows, 25 companies, 13 concepts, filed dates 2009→2026-08-10). Restatements are preserved as separate rows — read via `pit.value_as_of()`, never "latest value." |
| `prices.parquet` | Daily OHLCV for all 25 tickers (271,372 rows, full available history). **Split-adjusted, NOT dividend-adjusted**; source is Yahoo's keyless chart endpoint after Stooq turned out to be bot-gated — both caveats in `data/PRICES_NOTES.md`. |
| `PRICES_NOTES.md` | Price-ingestion lab notes: source decision and its open caveat, adjustment semantics verified against NVDA's 10:1 split, coverage table. |
| `features.parquet` | Phase C feature matrix: 630 (company, filing) observations, 581 with a complete forward target window. Built by `features.py`; documented feature-by-feature in `features_report.md`. |
| `features_report.md` | Full feature dictionary (source + caveat per feature) plus build-time join diagnostics. **Owner gate-file — read alongside `backtest_report.md`.** |
| `backtest_report.md` | Per-fold walk-forward results, raw and deduplicated, plus the form-controlled ablation. **Owner gate-file for the Phase C go/no-go read.** |
| `filings_metadata.db` | SQLite metadata store (companies, filings, filing_documents, universe_validation_problems) plus `fundamentals_validation_problems` from `ingest_fundamentals.py`. |
| `full_run_report.md` | The labeling run's report. Read the **FINAL CONSOLIDATED STATE** section at the bottom; earlier sections are superseded. |
| `raw/` | Cached upstream responses that `edgar_client.py` / `price_client.py` read and write: SEC submissions, filing index, documents, `companyfacts/`, plus `prices/` (not SEC — see `PRICES_NOTES.md` §1). |
| Other `batch_requests*.jsonl`, `labels_canary*.parquet`, `*_batch_meta.json` | Intermediate artifacts from the labeling run and its corrective/re-label passes. Audit trail, not inputs to anything downstream. |

### `spotcheck/` — human + second-rater review of the labels

| File | Role |
|---|---|
| `build_sample.py` | Builds the 400-example review sample: Tier A (162, all distress positives), Tier B (142, thin categories), Tier D (60, config-disagreement chunks for blind adjudication), Tier C (36, stratified fill). |
| `sample_400.parquet` / `sample_400.json` | The built sample, in both formats. |
| `review_tool.html` | Self-contained browser review tool — open directly via `file://`, no server needed. |
| `compute_agreement.py` | Scores review judgments against stored labels; reports Wilson confidence intervals per field and per tier against a 0.70 lower-bound bar. Its Section 3 per-tier breakdown covers A/B/C/D (a bug that silently dropped Tier D was fixed 2026-08-18; 15/15 tests pass). |
| `auditor_verdicts.json`, `adjudicator_verdicts.json`, `combined_judgments.csv` | The completed pass: 400 blind second-rater verdicts, 199 third-rater adjudications, and all 1,222 provenance-tagged judgments (`source` = model-auditor / model-adjudicator / owner). Model verdicts are never recorded as the owner's. |
| `agreement_report.txt` | Final agreement rates with Wilson CIs, per tier and per section type, plus the provenance appendix stating what the rates do and do not measure. |
| `README.md` | Detailed spot-check protocol, corrected 2026-08-18. The one passage still stale is the **sampling-rules narrative under the tier legend**, which describes the original pre-relabel, pre-Tier-D draw (A=143/B=142/C=115); the rules did not change, only the counts. Trust the banner (A=162/B=142/D=60/C=36) and `build_sample.py` over that paragraph. |

### `finetune/` — QLoRA scaffolding (not yet run)

| File | Role |
|---|---|
| `README.md`, `SPLIT_DESIGN.md`, `MODEL_CHOICE.md`, `PROMPT_TEMPLATE.md` | Design docs: leakage rule, model choice (Qwen2.5-7B-Instruct, Apache-2.0 — license verified live 2026-08-18), and prompt/applicability format. |
| `MLX_FEASIBILITY.md` | **Read this before any Phase D work.** Paper study (2026-08-18, nothing installed or downloaded) measuring whether 4-bit QLoRA fits the owner's 16 GB M5: feasible only at `batch_size: 1` / `max_seq_length: 2048` / `grad_checkpoint: true`, ≈5–13 h per epoch. Overturns `config.yaml`'s `batch_size: 4` and the "overnight run" framing. |
| `split.py` | Builds the train/eval split (5,736 train / 1,010 eval, 15.0% eval) via a leakage-safe connected-component graph over shared paragraphs and filings. |
| `check_leakage.py` | Verifies no chunk, paragraph, or accession straddles the split. Five assertions, all passing. |
| `prepare_dataset.py` | Converts the split into instruction-format JSONL (`prepared/train.jsonl`, `prepared/eval.jsonl`). |
| `train_qlora.py` | Training script. `--dry-run` validates config and data with no GPU or heavy deps; the real training path is gated on explicit owner sign-off and runs locally via MLX, not this HF/peft path (see note below). |
| `eval.py` | Evaluation script. `--dry-run` runs the eval pipeline against synthetic predictions to prove the scoring logic works; real evaluation needs a trained checkpoint that does not exist yet. |
| `config.yaml` | QLoRA hyperparameters. `gpu_rental_placeholder.status` is `NOT APPROVED` — that path is a fallback only, see below. |

**Fine-tuning method note:** the docs and code in `finetune/` were written assuming a rented GPU and the HuggingFace `transformers`/`peft`/`bitsandbytes` stack. The owner has since ratified a different, cheaper path: if fine-tuning happens at all, it runs **locally** on the owner's Mac (Apple M5, 16GB RAM) via **MLX 4-bit QLoRA**, at $0. GPU rental is a fallback only if local MLX proves infeasible. Treat `train_qlora.py`'s non-dry-run path and `config.yaml`'s GPU section as superseded scaffolding, not the plan.

### `.claude/agents/` — subagent roles

`data-engineer.md`, `finetune-engineer.md`, `quant-modeler.md`, `red-team-reviewer.md`, `docs-writer.md` define the roles used to build and audit this pipeline. Two were added for the spot-check: `label-auditor.md` (blind second-rater that re-judges each chunk before seeing the stored label) and `label-adjudicator.md` (third rater that resolves second-rater-vs-stored-label disputes on rubric merits, sees both prior positions, and escalates to the owner). Both produce model verdicts, recorded as such with explicit provenance — never as the owner's own judgment.

### Docs not covered above

| File | Role |
|---|---|
| `LIMITATIONS.md` | The honest-limitations write-up (2026-08-18): non-goals, label-quality failures with how each was measured, survivorship bias, the frozen snapshot, the self-identification channel, price/fundamentals caveats, and an explicit TODO placeholder for the Phase D fine-tune that has not happened. Start here before quoting any number from this project. |
| `RED_FLAGS_LIMITATION.md` | Canonical Phase B disposition record for the `red_flags` agreement failure: per-category verdicts, the 36.6% error decomposition, the owner-ratified ambiguity principles, a proposed (unratified, unapplied) rubric revision, and four binding constraints on Phase C feature engineering. |
| `DISCOVERY.md` | Phase 1 planning doc (MVP scope, non-goals, taxonomy, evaluation design), carrying a 2026-08-18 READER NOTE banner and **two amendment layers**: 2026-08-11 (§5 label-attribution decision, §6 config-sensitivity risk) and 2026-08-18 (a dated amendment inside §6's risk register reporting the completed spot-check). Preserved as an audit trail — parts of it (spend tally, fine-tune tech stack) predate later decisions and are superseded by this README and `HANDOFF.md`. |
| `ROADMAP.md` | Rewritten 2026-08-11 into a Phase A-E structure; a current forward plan alongside HANDOFF.md, not an audit-trail doc. Phase C (features + backtest, GO/NO-GO gate) already precedes Phase D (optional local MLX fine-tune) — the old Week 4/Week 5 fine-tune-before-backtest ordering no longer appears in the file; its History section records why it changed. |
| `REDTEAM_WEEK3.md` | Independent red-team review of Weeks 1-3. 8 findings; **#1, #5 and #8 carry owner-verified RESOLUTION/CORRECTION blocks inline, so 5 remain open/forward-looking** (#2, #3, #4, #6, #7 — #6 is a confirmed "no issue" finding). Finding #4's counts are pre-relabel; the corrected modality×section table is in `data/features_report.md`. (Accounting matches `HANDOFF.md` §2.) |
| `HANDOFF.md` | Written 2026-08-18. The authoritative session-to-session handoff — read it before this README for owner decisions, incident lessons, and standing rules; it explicitly supersedes every other doc where they conflict. |

## How to run things

All commands assume the repo root as the working directory and a Python environment with `requirements.txt` (ingestion/labeling/spotcheck), `requirements-quant.txt` (Phase C features + backtest — also needs `brew install libomp` on macOS, see that file), or `requirements-finetune.txt` (finetune scaffolding, not for local install) installed.

**Ingestion** (safe to re-run; idempotent, reads from local cache when fresh):
```
python3 ingest_metadata.py            # resolve filing metadata into data/filings_metadata.db
python3 extract.py                    # pull MD&A / Risk Factors / earnings text into data/filings.parquet
python3 extract.py --limit 5          # debug: only the first 5 filings
python3 chunk.py                      # build data/labeling_corpus.parquet + paragraph_occurrence_map.parquet
```

**Numeric ingestion for Phase C** (also idempotent and cached; no API spend — EDGAR companyfacts and a free keyless price endpoint):
```
python3 ingest_fundamentals.py        # build data/fundamentals.parquet from EDGAR companyfacts
python3 ingest_prices.py              # build data/prices.parquet (see data/PRICES_NOTES.md for the source caveat)
```

**Phase C features + backtest** (deterministic, offline, no API spend; needs `requirements-quant.txt`). **Both scripts overwrite the owner's gate-file reports — do not re-run them while a go/no-go read is open:**
```
python3 features.py                   # build data/features.parquet + data/features_report.md
python3 backtest.py                   # walk-forward comparison -> data/backtest_report.md
python3 -m pytest test_phase_c_leakage.py -q   # 35 leakage tests; slow (~90s), re-reads the full corpus
```

**Labeling — do not run.** `submit_labeling_batch.py`'s `--full`, `--full-corrective`, and `--full-relabel` modes call the paid Batch API and are retired; no further API spend is authorized. `submit_labeling_batch.py --verify-config` (read-only, checks a completed batch's real stop reasons) is safe if ever needed again.

**Spot-check:**
```
open spotcheck/review_tool.html                              # or file:///.../spotcheck/review_tool.html
python3 spotcheck/compute_agreement.py --input spotcheck/combined_judgments.csv --format auto
```
`review_tool.html` is self-contained (no server, no external hosts). `combined_judgments.csv` is the completed pass's 1,222 provenance-tagged judgments and is what reproduces the headline rates; a fresh CSV exported from the review tool scores the same way.

**Fine-tune scaffolding (all local, no GPU, no API calls):**
```
python3 finetune/split.py                 # rebuild the train/eval split from data/labels.parquet
python3 finetune/check_leakage.py         # verify no chunk/paragraph/accession straddles the split
python3 finetune/prepare_dataset.py       # write prepared/train.jsonl and prepared/eval.jsonl
python3 finetune/train_qlora.py --dry-run # validate config + data pipeline, no GPU needed
python3 finetune/eval.py --dry-run        # validate the eval pipeline against synthetic predictions
```
None of these touch the network or spend money. Real training/eval are both gated on further owner decisions (see fine-tuning method note above).

## Next steps

Per the owner-ratified execution order:

1. ~~**Spot-check second-rater pass**~~ — **done 2026-08-18.** All 400 chunks re-judged blind, 174 contested chunks resolved by a third-rater model, owner ruled 104 of 1,222 judgments. Results: `spotcheck/agreement_report.txt`.
2. ~~**Rubric revision**~~ — **dispositioned 2026-08-18.** `red_flags` failed the bar, so it is documented as a limitation (`RED_FLAGS_LIMITATION.md`, `LIMITATIONS.md` §2.1), not re-labeled. A rubric fix is drafted there but is **pending owner ratification and not applied**; no re-label happens either way, under the no-API-spend rule.
3. ~~**Features + backtest**~~ (`DISCOVERY.md` §5) — **built and run 2026-08-18.** Every-occurrence label attribution via `data/paragraph_occurrence_map.parquet`; red-flag features normalized by section composition to avoid the modality confound flagged in `REDTEAM_WEEK3.md` finding #4; plus the four binding constraints in `RED_FLAGS_LIMITATION.md` and the fundamentals tag-migration traps in `HANDOFF.md` §2a. Outputs: `data/features.parquet` (630 observations, 581 with a complete forward window), `data/features_report.md`, `data/backtest_report.md`.
4. **Go/no-go — THE LIVE GATE.** The owner reads `data/backtest_report.md`'s per-fold tables personally (raw *and* deduplicated columns, plus the ablation section) before any fine-tuning work starts. Nobody summarizes it. If the text-augmented model doesn't beat the numeric-only baseline by more than fold-to-fold noise, the honest conclusion is "the text signal didn't help here," and that is a legitimate outcome, not a failure to spin.
5. **If GO: local MLX QLoRA fine-tune** — convert `finetune/prepared/*.jsonl` to MLX format and train on the owner's Mac; evaluate on the held-out 1,010-row eval split. **Read `finetune/MLX_FEASIBILITY.md` first**: it measures one epoch at ≈5–13 h on the M5 at `batch_size: 1`, so `config.yaml`'s 3 epochs is ≈15–39 h — not an overnight run — and `config.yaml`'s `batch_size: 4` will not fit in 16 GB.
6. **Red-team pass + model card** — carrying forward the config-sensitivity headline limitation and honest spot-check epistemics (a model second-rater is not human validation; human judgment is concentrated on disagreements and the highest-stakes chunks, not a random sample). `LIMITATIONS.md` is the current draft of that carry-forward.

## Standing rules (apply to all future work on this repo)

- **No further Anthropic API spend**, for any reason, under any framing. The `.env` key stays unused.
- Money-gated or API-calling actions run in the main session only — never delegate consent or execution to a subagent.
- Never fabricate or simulate a human judgment. Model-rater verdicts (e.g. from `label-auditor`) are recorded as model verdicts, never attributed to the owner.
- The distress tier (`GOING_CONCERN`/`ACCOUNTING_RESTATEMENT`/`LIQUIDITY_STRESS`) stays excluded from fine-tuning targets and headline eval metrics (n=162 corpus-wide; `GOING_CONCERN` has zero instances). **Every REALIZED distress class is now empty**: the corpus's 9 `LIQUIDITY_STRESS`/REALIZED labels were all ruled incorrect by the owner (`LIMITATIONS.md` §2.5, `RED_FLAGS_LIMITATION.md`), so realized-distress features are known-empty, not merely thin.
- `guidance_direction=WITHDRAWN` (n=1) and `section_type=8K_BODY` (n=8, only 2 of 25 tickers) are statistically meaningless categories — exclude both from any headline eval metric, same treatment as the distress tier (REDTEAM_WEEK3.md Finding #7).
- The filing text self-identifies its own company in 26.8% of chunks by a strict measurement and 46.0% by a loose one (REDTEAM_WEEK3.md Finding #2; DISCOVERY.md §5 now carries both figures as an amendment to its original ~19%/48% estimate — cite both, so neither is mistaken for the discredited one) — a look-ahead-bias risk mitigated only by prompt instruction, and watched but not resolved by the spot-check.
- The walk-forward backtest must sort by public filing-availability date with an expanding window — never a random shuffle — and numeric fundamentals must be point-in-time. Report per-fold spreads, never a single point estimate.
- `labeling_rubric.md` is the authoritative labeling spec; `SYSTEM_PROMPT` in `build_batch_requests.py` is a hand-synced restatement. Any rubric edit must be re-synced into that constant (moot for now, since no further labeling runs are permitted, but binding if that ever changes).
