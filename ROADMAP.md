# ROADMAP — Financial Text-Signal Research Tool

**Last updated: 2026-08-18.** Phase status at a glance: **A ✅ DONE
(2026-08-18) · B ✅ DONE (2026-08-18) · C ✅ BUILT+RED-TEAMED, GATE READ PENDING · D ⬜ NOT STARTED
· E ⬜ NOT STARTED.**

Phase 2 of the FinScreen operating brief: a solo-owner research/screening
tool, not a trading bot — no investment advice, no live capital, no return
claims (non-goals are contractual, `DISCOVERY.md` §7). This file is the
current forward plan. `DISCOVERY.md`, `data/full_run_report.md`,
`REDTEAM_WEEK3.md`, `INGESTION_NOTES.md` and `data/canary_comparison.md`
are preserved as-is as the project's audit trail — they record what was
true when written and are not kept current; this file and `HANDOFF.md` are.

Subagent roles referenced below (`data-engineer`, `finetune-engineer`,
`quant-modeler`, `red-team-reviewer`, `docs-writer`, `label-auditor` and
`label-adjudicator`) are defined under `.claude/agents/`.

**Phase C is the hard go/no-go gate**, same as it always was — it just now
comes before fine-tuning instead of after it (see History below for why).

---

## History (Weeks 1–3, complete)

- **Week 1–2:** Built `edgar_client.py` (rate-limited SEC EDGAR client) and
  `ingest_metadata.py`/`extract.py`, pulling 10-K/10-Q/8-K metadata and
  MD&A/Item 1A/EX-99.1 text for the locked 25-company, 5-sector universe
  across a 12-quarter window (1,271 filings, 884 extracted filing-sections).
  Point-in-time discipline (`filing_date`, never `report_date`) enforced
  throughout.
- **Week 3:** Built `chunk.py` (dedupe + ~350-word window packing →
  `data/labeling_corpus.parquet`, 6,747 chunks) and `labeling_rubric.md`
  (v1.1: sentiment, 6-category red-flag taxonomy, 3-category distress tier,
  modality, guidance-direction — all look-ahead-bias-safe, no ticker/company/
  date in any prompt). Ran the bootstrap labeling pass via the Batch API.
- **The re-label episode (2026-08-11):** `run_full()` in
  `submit_labeling_batch.py` silently ignored `--variant` and submitted the
  wrong config (500-token/adaptive-thinking instead of the canaried one),
  truncating **37.5% (2,528/6,747)** of the first full run — the separate
  **37.6%** figure quoted elsewhere is 2,537/6,747, the count of results
  that hit *exactly* 500 output tokens (`full_run_report.md`'s evidence
  §2), a slightly different numerator. A corrective run and
  then a full re-label of the affected 4,219 rows brought the whole corpus to
  one uniform config (thinking disabled, max_tokens=4000). Guards now block
  a repeat: `--confirm-full`, a variant/request-file consistency check, and
  `--verify-config` reading real stop-reasons back from the API.
- **Result:** labeling is **complete** — 6,746/6,747 chunks labeled under a
  single config, zero truncations. The 1 excluded row
  (`CHK-8e69547e0900a8dd`, MDA) is a genuine bio-category safety refusal, not
  a bug. A known limitation carries forward: red-flag labels are ~22%
  config-sensitive between the two passes (see Money section and Phase E) —
  sentiment/guidance/distress are far more stable (0.7–3.6%).
- **Why Phase C now precedes fine-tuning:** the bootstrap labels already
  cover the full frozen corpus, so the backtest does not need to wait on a
  fine-tuned model — fine-tuning (Phase D) only has a reason to happen if
  Phase C's go/no-go shows real text signal over the numeric-only baseline.

---

## Phase A — Spot-check: second-rater + human triage — ✅ DONE (2026-08-18)

> **Outcome:** ran end-to-end. `label-auditor` judged all 400; a third
> rater (`label-adjudicator`, added mid-phase under the 2026-08-18
> delegation ratification) resolved the 174 contested chunks; the owner
> ruled a 104-case shortlist. **`red_flags` failed the 0.70 bar (63.4%
> exact-set match, CI [58.6, 68.0]); sentiment 94.6%, guidance 95.2% and
> distress_tier 94.2% cleared it.** Deliverable:
> `spotcheck/agreement_report.txt`. Full write-up: `HANDOFF.md` §2a and
> `RED_FLAGS_LIMITATION.md`. The past-tense record below is the plan as
> written; it is kept because the design rationale is still the rationale.

**Goal:** Validate label quality on the 400-example stratified sample
(`spotcheck/sample_400.parquet`: A=162 all distress positives, B=142 thin
categories, D=60 config-disagreement adjudication judged blind, C=36
stratified fill) without spending any further API budget, by having a model
subagent do the first pass and reserving owner time for what actually needs
human judgment.

**Deliverable:**
- `label-auditor` (opus, blind protocol) independently re-judges all 400
  examples in ~40-chunk batches (10 batches), producing structured verdicts
  by judging the text independently before comparing to the stored label
  (the rater's context does include the stored label, per
  `.claude/agents/label-auditor.md` Rule 3 — the discipline is
  judge-first-then-compare, not technical blinding from the label data).
- Merged rater-vs-stored-label disagreement set.
- Owner adjudicates **only**: that disagreement set, plus the 11
  highest-stakes distress chunks (9 REALIZED `LIQUIDITY_STRESS` + 2
  `ACCOUNTING_RESTATEMENT`) regardless of whether the rater agreed.
- `compute_agreement.py` run on the combined (rater + adjudicated + owner)
  judgments → per-category agreement rate with Wilson confidence intervals,
  against the 0.70 lower-bound bar. *(Its Section 3 per-tier breakdown once
  hardcoded `["A", "B", "C"]` and silently dropped Tier D — **fixed
  2026-08-18**; Section 3 now reports A/B/C/D.)*

**Definition of done:** All 400 examples have a `label-auditor` verdict; the
disagreement set is fully owner-adjudicated; per-category agreement + CI is
reported for sentiment, guidance_direction, and red_flags, with distress
reported separately and never averaged into the headline number; the report
states plainly that the rater is a model, not a second human — this is
model-assisted triage, not independent human validation.

**Cost:** $0 — `label-auditor` runs on the owner's Claude Max subscription,
no API calls.

**Subagent:** `label-auditor` is the second rater; `label-adjudicator` is
the third rater over disputes; the owner **ratifies** — vocabulary per
`HANDOFF.md` §2a/§3. (An earlier draft of this line said "owner
adjudicates disagreements"; the 2026-08-18 delegation ratification moved
the bulk of the adjudicating to the third-rater model, with the owner
ruling a shortlist.)

---

## Phase B — Rubric revisions (only if Phase A demands it) — ✅ DONE (2026-08-18)

> **Outcome:** Phase A did demand it. `RED_FLAGS_LIMITATION.md` (repo root)
> is the disposition record: every headline category has an explicit
> verdict, `red_flags` is documented as failed with its error
> decomposition and the owner-ratified P1/P2/P3 ambiguity principles, and
> a concrete `labeling_rubric.md` §4/§6 revision is drafted —
> **proposed, NOT ratified, NOT applied, and no re-label regardless**
> (API-spend freeze). `labeling_rubric.md` §9 points at it.

**Goal:** Fix any label category whose agreement rate falls below the 0.70
bar.

**Deliverable (conditional):** If a category fails the bar, a
`labeling_rubric.md` revision plus the corresponding hand-sync update to
`SYSTEM_PROMPT` in `build_batch_requests.py`, per the standing sync rule
(rubric is authoritative; system prompt is a synced restatement, never the
other way around). If nothing fails the bar, this phase is a no-op — record
that explicitly rather than skipping silently.

**Important constraint:** no further labeling run is possible under the
no-more-API-spend rule. A category that fails the bar gets a documented
rubric fix proposal and is recorded as a known limitation in the model card
(Phase E) — it does **not** get re-labeled.

**Definition of done:** Every headline category has an explicit disposition
— cleared the bar (no action), or failed it (fix proposed, limitation
documented, no re-run performed).

**Cost:** $0.

**Subagent:** rubric owner (`finetune-engineer`) drafts the fix;
`docs-writer` folds the limitation into Phase E's docs; owner ratifies any
rubric change.

---

## Phase C — Features + walk-forward backtest (GO/NO-GO GATE) — ✅ BUILT AND RED-TEAM-CLEARED (2026-08-18); ⏳ the owner's gate read is the only open item

> **Status:** fundamentals ingestion, price ingestion, `features.py` and
> `backtest.py` are all built and run. The red-team found **1 BLOCKER + 3
> MAJORs**, so **the pre-fix per-fold numbers are not fit for the owner's
> go/no-go read**; a fix+re-verify workflow is in flight. See
> `HANDOFF.md` §2a for the current detail and the binding feature traps.

**Goal:** Get the first honest read of whether text signal helps, using the
bootstrap labels directly — they already cover the frozen corpus, so this
does not wait on fine-tuning.

**Deliverable:**
- Numeric-fundamentals sourcing — **DONE (2026-08-18).**
  `EdgarClient.get_companyfacts()` pulls the SEC XBRL companyfacts API;
  `ingest_fundamentals.py` writes `data/fundamentals.parquet` (42,158 rows,
  25 companies, 13 concepts, every filed occurrence preserved) plus a
  `fundamentals_validation_problems` WARN table (40 WARN / 0 FATAL across
  five check names). `pit.py`'s `value_as_of()` is the one tested
  point-in-time selection helper — **consume fundamentals through it, never
  by taking the latest row.** Before writing numeric features, read the
  WARN-taxonomy traps in `HANDOFF.md` §2a: `OperatingIncomeLoss` has zero
  in-window coverage for 10 of 25 companies; several mid-window tag
  migrations point at `ProfitLoss`, which is **documented but not
  ingested**; MA's in-window `NetIncomeLoss` rows are DEF 14A proxy
  disclosures; and `RevenuesNetOfInterestExpense` is used by **GS and
  JPM**, not GS alone.
- `features.py` — joins text-derived signals with point-in-time numeric
  fundamentals via every-occurrence attribution
  (`data/paragraph_occurrence_map.parquet`, per `DISCOVERY.md` §5), and
  normalizes red-flag features by section composition to control for the
  modality/section_type confound (RISK_FACTORS skews HYPOTHETICAL, MD&A
  skews REALIZED — REDTEAM finding #4).
- `backtest.py` — walk-forward harness: expanding window, sorted by public
  availability (`filing_date`), never random shuffle.
- A results report: text-augmented model vs. numeric-only baseline,
  per-fold spreads, never a single point estimate.

**🛑 HARD GO/NO-GO GATE.** Three outcomes:
1. **Text signal clearly helps** → proceed to Phase D.
2. **Mixed / inconclusive across folds** → proceed to Phase D, but scope it
   toward diagnosing which categories/companies drive the signal, not depth
   for its own sake.
3. **No signal, or a look-ahead-bias bug is suspected** → stop. Debug the
   evaluation before touching fine-tuning at all.

**Definition of done:** `red-team-reviewer` checks look-ahead bias and
overfitting *before* the owner reviews the results, not after. The owner
personally reads the per-fold results — not a subagent's summary — and
makes the go/no-go call.

**Cost:** $0 — local compute only, against labels that already exist.

**Subagent:** `quant-modeler` builds it; `red-team-reviewer` checks it first.

---

## Phase D — Optional local MLX fine-tune + held-out eval — ⬜ NOT STARTED

**Goal:** Only if Phase C is a GO and the owner wants to pursue it — fine-
tune Qwen2.5-7B-Instruct (Apache-2.0) via 4-bit QLoRA, run entirely locally,
and evaluate it against the held-out split that was carved out before any
training touched it.

**Deliverable:**
- Convert `finetune/prepared/{train,eval}.jsonl` (5,736 / 1,010 rows, split
  and leakage-checked already — 5 assertions pass, no chunk/paragraph/
  accession straddle) to MLX format; run QLoRA training locally on the
  owner's M5 Mac (16GB RAM, 359GB free), small batch, overnight.
- `eval.py` run against the held-out 1,010-row eval split.
- Eval report: per-category precision/recall/F1 against the held-out split,
  plus qualitative examples of actual model output. Distress tier stays
  excluded from headline metrics (n=162 corpus-wide, GOING_CONCERN n=0).
  `guidance_direction=WITHDRAWN` (n=1) and `section_type=8K_BODY` (n=8,
  concentrated in 2 of 25 tickers) are likewise not meaningfully evaluable
  — exclude both from headline per-category metrics and say why, same
  treatment as the distress tier.
- The checkpoint stored somewhere durable, not left only on local disk.

**Definition of done:** The eval report is honest about weak categories, not
just strong ones; no claim about model quality goes further than what the
held-out eval actually shows.

**Cost:** $0 — local M5 compute. GPU rental is **not** a fallback that
triggers itself if local MLX proves infeasible — it requires the owner to
explicitly authorize a new, separate "very minimal" budget first (see Money
section).

**Subagent:** `finetune-engineer`.

---

## Phase E — Red-team pass + docs — ⬜ NOT STARTED

**Goal:** Adversarially check everything from Phases A–D, then write it up
honestly for a reader who wasn't in the room.

**Deliverable:**
- `red-team-reviewer` report: look-ahead bias re-verified independently,
  overfitting risk given the small universe, and the config-sensitivity
  headline limitation folded in explicitly (red_flags 22.2% [935/4,219]
  config-sensitive between passes — LEGAL_REGULATORY_ACTION +211,
  MARGIN_COST_PRESSURE +203, DEMAND_WEAKNESS +138, IMPAIRMENT_WRITEDOWN +51,
  SUPPLY_INPUT_CONSTRAINT +35, TRADE_POLICY_EXPOSURE +27, all in the
  more-flags direction; sentiment 3.6%, guidance 0.9%, distress 0.7%).
- `README.md` + `HANDOFF.md` (new) — what this is, how to run it, current
  state, non-goals stated plainly near the top.
- `MODEL_CARD.md` — training data, evaluation methodology, the config-
  sensitivity limitation, and honest spot-check epistemics (the `label-
  auditor` pass is a model second-rater, not human validation; human
  judgment is concentrated on disagreements + the 11 highest-stakes distress
  chunks, not a general read-through).
- `LIMITATIONS.md` (or a section of the above) — survivorship bias, small
  universe, frozen snapshot, any category that failed Phase A's bar and
  wasn't re-labeled (per Phase B's constraint), the residual self-
  identification channel (~27–46% of chunks name their own company,
  mitigated by instruction, watched in spot-check).

**Definition of done:** A stranger reading only these docs could not mistake
this for a trading product or a source of investment advice. Every red-team
finding is either fixed or logged as a known limitation with a reason —
nothing silently dropped.

**Cost:** $0.

**Subagent:** `red-team-reviewer` leads; `docs-writer` writes; others fix
findings in their own area.

---

## Money

**API spend is FROZEN at $33.51 total** — canary $0.27, dual canary $0.64,
full run (wrong config, 62.5% usable) $18.05, corrective run $4.49, re-label
$10.06. This is an owner directive that **supersedes the old $50 ceiling**:
no further API spend is permitted, period — not "$16.49 remaining," just no
more, regardless of what any earlier document's ceiling implies.

All agent work in Phases A–E — subagent runs, `label-auditor`'s second-rater
passes, reviews, orchestration — runs on the owner's $200/mo Claude Max
subscription at **$0 marginal cost**. Claude Max cannot fine-tune models and
is not API credit; it covers agent work, not Phase D's actual training.

Fine-tuning (Phase D), if it happens, runs **locally** via MLX 4-bit QLoRA
on the owner's M5 Mac at **$0**. GPU rental is not currently authorized and
is not a fallback that activates itself if local MLX proves infeasible — it
requires the owner to explicitly re-open a new, separate "very minimal" GPU
budget before any rental happens, evaluated fresh against the no-more-spend
directive above.

---

## Subagent roster

`data-engineer` (Weeks 1–2, stable), `finetune-engineer` (rubric owner,
Phase D), `quant-modeler` (Phase C), `red-team-reviewer` (Phase C check,
Phase E lead), `docs-writer` (Phase E), `label-auditor` (Phase A second
rater — opus, blind protocol), `label-adjudicator` (Phase A **third**
rater — created 2026-08-18 under the delegation ratification, sees both
prior positions, performed the bulk of Phase A's dispute resolution;
`.claude/agents/label-adjudicator.md`).
