# HARDENING_PROGRESS — phase F2.5 (pre-F3 hardening package)

**Started 2026-08-25** on the owner's explicit full-package ratification
(HANDOFF §3, 2026-08-25 second entry; EXPANSION_PLAN §8). Same resume
discipline as `F2_PROGRESS.md`: an item is DONE only when its
completion report exists at `data/hardening/status/H<N>_*.md`; briefs
below are the relaunch text if an agent dies; long compute runs
main-session-only per HANDOFF §4. **F3 starts only when H1–H6 are all
DONE and the owner has ruled G1 (held for H3) and ratified H5.**

Source specs: the four lens reports in `data/reevaluation_2026-08-25/`
carry the concrete details (file:line, formulas, measured populations)
— each item's executor reads its lens section first.

## Item table

| # | Item | Executor (tier) | Status | Report |
|---|---|---|---|---|
| H1 | Positive controls T1+T2 | quant-modeler (Opus) | **DONE 2026-08-25** — T1 FAILS its own pre-declared bar (t=3.13 vs 4.0; 70.7% vs 75% quarters) but the relation is present (bootstrap CI [+0.026,+0.105]) and the STACK IS AFFIRMATIVELY VERIFIED (2.82× announcement-day spike; post-close D+1 vs pre-close D split confirms the acceptance-time fix); 8.1% stale-Q4 spec defect reported as a G3 repair, not folded in. T2 ambiguous-as-expected, placebo clean; **measured yardstick: PEAD ≈ 0.06–0.08 IC here, noise floor ≈ 0.047**. Main-session reading (flagged as such, owner decides): kill-criterion 1 NOT triggered by the letter — relation shown, anomaly weakly present, not absent | `data/hardening/status/H1_controls.md` |
| H2 | Spec pre-registration + honest MDE | research-statistician (Opus) | **DONE 2026-08-25** — ddof fixed at all 5 sites; PIT-rank primary spec + paired secondary + standing zero-info benchmark rows (0.224/0.187 re-derived) live in code; honest MDE: primary-spec **0.032–0.085** (floor UNRESOLVED at 6 folds; TOST Δ=0.03 needs the floor-free corner or 68–125 folds) — published 0.019–0.037 superseded via EXPANSION_PLAN §2a amendment; NEW findings: the audit's +0.0467 not reproducible (implementation sensitivity 0.059 dominates → G3 pre-registers function+args), 12.9% train-labels-resolve-in-test-quarter embargo gap → G3; H5 draft reconciled via dated note; 105 targeted tests | `data/hardening/status/H2_spec.md` |
| H3 | Labeler attenuation check | finetune-engineer implements (Opus); MAIN SESSION ran the generation; quant-modeler comparison | **DONE 2026-08-25** — generation 6,746/6,746 (exit 0, no kills; eval slice byte-identical to the epoch-2 eval). MEASURED retention (eval-only, unbiased): sentiment_mean 0.834, sentiment_negative_share 0.592 (matches prediction), **red-flag family 0.669 [0.586, 0.742] vs predicted 0.808 — KILL-CRITERION 2 BREACHED for the red-flag block**; MDA MARGIN_COST_PRESSURE (0.115) and DEMAND_WEAKNESS (0.215) retain nothing distinguishable from zero (mechanism: worst-recall categories). Pooled numbers proven memorization-inflated via matched-composition control. IC-delta arm uninformative (differences < 100-seed nuisance SD 0.028; a non-stable-sort row-order defect worth +0.050 found+fixed). Three new G3 items: stable-sort pin, seed-nuisance band beside every estimate, per-feature (never family-mean) retention reporting | `data/hardening/status/H3_attenuation.md` |
| H4 | Doc-selection Tier-C sample | extraction-qa-engineer (Opus) | **DONE 2026-08-25** — 155 documents read: **0 wrong picks** [0.00, 2.42] (policy vindicated); NEW ~5.0% [1.96, 12.16] population-definition error class (9/9 are "extra" filings in multi-filing quarters: transcripts, merger 8-Ks, one other-company release); **F3 CONDITION recorded**: FAIL/WARN gate on multi-filing-quarter cells lacking a results signature (measured recall 9/9; sole-filing cells 0/116); plus 3 F3 calibration inputs (length is a bad discriminator; 8K_BODY needs item-2.02-anchored slicing; combined release+supplemental dilution) | `data/hardening/status/H4_docsample.md` |
| H5 | Stopping rule + G3-conventions skeleton (DRAFT for owner) | tech-council (Fable) | **DRAFT DONE 2026-08-25** — Option 1 recommended ("one experiment, three branches, hard top" + CFO price annex; CFO/CRO-research dissents recorded); 5 kill-criteria tie the rule's validity to H1/H3 results, so OWNER RATIFICATION deliberately waits for those + rules together with G1 | `data/hardening/status/H5_stopping_rule.md` |
| H6 | Prior-work section | docs-writer (Opus) | **DONE 2026-08-25** — `PRIOR_WORK.md` written; every citation flagged recalled-not-fetched (verify before external use); refused to overstate the lens (head-1 literature = "settled small-and-decaying, not settled zero"); exit head explicitly NOT a distress-replication | `data/hardening/status/H6_priorwork.md` |

## Briefs (relaunch verbatim if an item shows IN FLIGHT with no report)

### H1 — positive controls (quant-modeler)
Read `data/reevaluation_2026-08-25/alternatives.md` (positive-control
finding) + `methodology_audit.md` first. Build a NEW script
(`controls.py` + tests; do NOT edit backtest.py/diagnose.py — H2 owns
them) over frozen artifacts (`data/filings_metadata_e2.db`,
`data/prices_e2.parquet`, `data/fundamentals_e2.parquet`): **T1** — over
the ~5,552 in-membership earnings 8-Ks with price coverage, does the
contemporaneous announcement-window return relate to earnings surprise
(use a simple standardized surprise from fundamentals; document the
construction) in the expected direction? **T2** — does a documented
numeric anomaly (PEAD ~60d drift and/or 12-1 momentum) appear at the
actual backtest configuration (same folds/dedup/IC machinery,
re-implemented or imported read-only)? Deliverable: pass/fail per
control with effect sizes, SEs, and the honest statement of what
failure would mean. Zero GETs; PIT discipline absolute (filing_date
windows; note the post-close acceptance issue and use
next-trading-open conservatively, documenting it).

### H2 — specification pre-registration + honest MDE (research-statistician)
Read `data/reevaluation_2026-08-25/methodology_audit.md` in full — it
is your spec. Implement: ddof=0→1 at diagnose.py:222 and
backtest.py:513,689,693,781 (verify each); PIT trailing cross-sectional
percentile-rank transform as the PRIMARY feature specification with raw
levels as mandatory reported secondary; two standing zero-information
benchmark rows (size-only rank; ticker-training-mean rank) in every
report; the within-fold bootstrap noise anchor as a standing section;
restate EXPANSION_PLAN §2a's MDE honestly (append a dated amendment,
never rewrite): ~0.029 (bootstrap anchor)/~0.039 (ρ_f=0.3)/~0.036–0.049
attenuated, with the bounded-null scope corrected to "detectable
through this labeling schema, these features, and this labeler" and a
named equivalence procedure (TOST or explicit CI). Tests for each code
change; targeted suites; E1 frozen artifacts untouched (re-derive on
copies/in-memory).

### H3 — labeler attenuation check (finetune-engineer implements)
Implement a SEGMENTED, RESUMABLE relabel runner: the epoch-2 student
(adapter `finetune/checkpoints/qwen2.5-7b-finscreen-lora-mlx-epoch2`,
prompt_rendering_contract exact) labels ALL 6,746 E1 chunks from
`data/labeling_corpus.parquet`, writing per-row append-checkpointed
output (`data/hardening/e1_relabel_student.parquet` via a .jsonl
journal), ~5–6 h at measured 1,337/h — designed for the MAIN SESSION to
run as a background auto-resume chain (HANDOFF §4; never run the
compute yourself). Provenance manifest (shas of adapter/base/
instruction/corpus). E1's `data/labels.parquet` is FROZEN — never
touched; the student output is a separate artifact. After the run, the
comparison (feature re-derivation + E1 backtest re-run on student
labels, retention ρ per feature, IC delta comparison) is a follow-up
task for quant-modeler — design your output schema to make that join
trivial (chunk_id-keyed, same label schema).

### H4 — doc-selection Tier-C sample (extraction-qa-engineer)
Read `data/reevaluation_2026-08-25/decision_audit.md` (EX-99 finding).
Draw a random, base-rate-representative sample of ~80 earnings-document
selections from `data/f2/ex99_selection_audit.csv` / the E2 DB
(seeded, documented), stratified only by nothing — this is the Tier-C
protocol applied to selection. Read each selected document (cached,
zero GETs) and verdict: correct earnings text / wrong / not-earnings.
Report the error rate with a 95% Wilson CI, compared against the three
known error classes' rates. This estimates what patching never did.

### H5 — stopping rule + G3 skeleton (tech-council, model=fable)
First convening. Read `REEVALUATION_2026-08-25.md`, all four lens
reports, HANDOFF §1+§3, EXPANSION_PLAN §2a+§8. DRAFT (for the owner —
advisory, decision-ready options per your charter): (1) the stopping
rule — pre-committed responses to bounded-null / above-MDE /
ambiguous-inside-MDE outcomes, an explicit E3 policy (default: no E3
without a new owner ratification naming what changed), and closure of
the EXPANSION_PLAN §7 mid-cap ramp; (2) the G3 pre-registration
document SKELETON listing every convention with its measured population
(post-close acceptance rule, restatement as-of, FX PIT, benchmark
excl-self, GLD treatment, fold structure, censoring sensitivity arm,
primary metric + equivalence procedure, three-heads conventions).
Output both as drafts the owner can ratify or amend, with per-seat
positions and the mandatory strongest-case-against.

### H6 — prior-work section (docs-writer)
Read `data/reevaluation_2026-08-25/alternatives.md` (the
zero-references finding + named literature). Write `PRIOR_WORK.md`
(root): one honest page positioning FinScreen against
Loughran-McDonald, Tetlock, Feldman et al., Lazy Prices
(Cohen/Malloy/Nguyen), FinBERT-era work, and Kravet/Muslu +
Campbell et al. on risk-language→volatility — what is known, what this
project replicates vs adds, and which of its three F5 heads test
effects the literature says are real vs settled-negative. No numbers
invented; cite the lens report's named sources; state clearly this was
written from the lens's literature summary, not fresh retrieval.

## G1 REPAIR CAMPAIGN (2026-08-26, owner-ratified — HANDOFF §3)

- Prep DONE (`data/hardening/status/G1_repair_prep.md`): rubric v1.2
  applied + SYSTEM_PROMPT hand-synced (sync rule); P2 deliberately NOT
  encoded (distress-tier scope — flagged in rubric §9 for its own
  ruling); 2 new guards added (stale-prompt, meta-path overwrite fix);
  60 targeted tests.
- Pricing verified from the authoritative reference (not memory):
  Sonnet 5 INTRO tier ($2/$10) live through 2026-08-31 → estimate
  $11.95–$19.30 at observed cache fan-outs, under the $25 cap.
- Alias residual closed as far as observable: E1's 4,219 results all
  resolve to exactly `claude-sonnet-5` (no dated snapshot exposed —
  no observable second axis).
- **SUBMITTED 2026-08-26 (main session, owner authorization HANDOFF §3):
  batch `msgbatch_01UdoUkZfuaTRJzokZDfbFYN`, 6,747 requests, variant
  v12_relabel, both guards green.** Meta: `data/v12_relabel_batch_meta.json`
  (new file; E1's frozen). Poll SYNCHRONOUSLY in the main session (no
  background watcher, §4 rule):
  `python3 submit_labeling_batch.py --poll msgbatch_01UdoUkZfuaTRJzokZDfbFYN
  --variant v12_relabel --out data/labels_v12.parquet --max-wait-s 1800`
  then `--verify-config`. Labels → NEW `data/labels_v12.parquet`.
  Next after labels: rebuild splits by JOINING onto the frozen
  `finetune/splits/manifest.parquet` (NEVER re-run split.py — its
  LABELS_PATH points at frozen E1 labels and it would re-derive
  membership); prepare_dataset; retrain (2 nights); re-eval; owner
  rules G1.
- **BATCH ENDED 2026-08-26 (~35 min): 6,746/6,747 succeeded, 0 parse
  failures, 0 truncations, all end_turn, resolved model uniformly
  `claude-sonnet-5`.** Labels → `data/labels_v12.parquet` (6,747 rows;
  E1's old refusal chunk DID label under v1.2). Distribution shifts to
  study at re-eval: ≥1-red-flag rows **4,514**; distress-tier matches
  **129** (E1: 162). *(Corrected 2026-08-26 from 4,515 / 130 — those were
  computed while `CHK-1c1812ed45219a3a` was unanswered and carried NULL,
  not empty, `red_flags`/`distress_tier`; a null-inclusive predicate
  counted it as a positive. The completion batch has since labeled it with
  an EMPTY set for both fields, so the corrected counts hold either way.
  See `data/hardening/LABEL_SHIFT_v11_v12.md` §7.)* **COST, disclosed honestly: usage values at $24.92 on the
  intro tier (expected bill; 8¢ under the $25 cap) / $37.38 at standard
  rates — cache fan-out ran ~3× the worst E1 observation (7.32M
  cache-write tokens), the term the prep flagged as uncontrollable. The
  run DRAINED the account's remaining prepaid credits: the final
  request errored "credit balance too low."** That request is
  CHK-1c1812ed45219a3a — a TRAIN row (OXY MDA 2026-02-18) → retrain
  uses 5,735/5,736 train rows (−0.02%); **eval split complete
  1,010/1,010.** Not retried: a retry needs the owner to buy credits;
  not worth half a cent of labels; documented instead. **The spend
  freeze is RE-SEALED — account balance ≈ $0; any future API call
  requires a new owner ratification AND a credit purchase.**
- **COMPLETION ROW LANDED 2026-08-26** (owner added $5 and explicitly
  authorized in chat; guarded `--complete-missing` mode added to
  `submit_labeling_batch.py`, 37 new mutation-tested tests): batch
  `msgbatch_01RvQpZofwP2yrHNnuJVmFZu`, 1 request, **actual cost
  $0.0014** (warm cache). `data/labels_v12.parquet` is now
  **6,747/6,747 with zero unanswered rows**; backup at
  `.pre_completion`; audit at `data/labels_v12_completion.parquet`.
  Owner-account state: ~$5 loaded remains ≈ untouched. FREEZE
  RE-SEALED again — no further API calls anywhere in the plan.
  v12 splits must be REBUILT to pick up the completed train row
  (5,736 full) before training.
- **DATASET BUILD DONE 2026-08-26**
  (`data/hardening/status/G1_repair_dataset.md`). Splits rebuilt against
  the COMPLETED labels by JOIN onto the frozen manifest
  (`finetune/build_splits_v12.py`; `split.py` never run) → **train 5,736 /
  eval 1,010, zero gaps, membership bit-identical to the frozen split**;
  refusal chunk `CHK-8e69547e0900a8dd` labeled under v1.2 but still
  excluded from both sides. `prepared_v12/` + `mlx_data_v12/` built and
  verified answer-intact. Prompt contract: **6,732/6,732 unaffected shared
  rows token-identical to E1**; 14 rows (2 train / 12 eval) differ only by
  answer-length-dependent head truncation — disclosed, not hidden.
  Training instruction FROZEN at `ebc45a85…` (it is NOT the labeling
  system prompt `30605197…`, which is 1,904 tokens and cannot fit
  `max_seq_length 2048`). Label shift published:
  `data/hardening/LABEL_SHIFT_v11_v12.md` — red_flags 27.48% exact-set /
  5.86% per-category, sentiment 4.59%, guidance 1.19%; LEGAL 300 HYP→REAL
  (P1), MARGIN_COST_PRESSURE +294 (P3 corollary), RISK_FACTORS churn 41.6%
  with flat totals (mining depth re-allocated rather than pruned).
  Run dir `finetune/runs/2026-08-26-v12-epoch1/` holds the exact main-
  session commands, both resolved configs, the resume recipe and a full
  sha manifest. **Projected 9.2 h/epoch (band 9.0–9.9 h), measured.**
  **NOT LAUNCHED — main session owns the compute (§4).**
- **EPOCH-1 TRAINING LAUNCHED 2026-08-26 12:07** on the owner's
  in-chat command ("begin the retrain"). Main-session background task
  per §4 — no agent involved. Pre-flight (RUN_COMMANDS §1) fully green
  first: splits + prepared rebuilt and byte-reproduced every pinned sha
  (train `5e56076e…` / eval `0b98531b…` / prepared `91d95653…` /
  `0229d0ba…` — mlx_data_v12 untouched, no reconversion needed);
  154 passed / 5 skipped system-python, 36/0 mlx-venv; config diff vs
  2026-08-20 epoch-1 exactly the three expected lines; GPU idle.
  Launcher's resolved `mlx_lora_config.yaml` hashes **exactly** to the
  pre-generated plan sha `9e35f2fb…` — single-axis claim holds at
  launch. Run dir `finetune/runs/2026-08-26-v12-epoch1/`; resume per
  its RESUME_RECIPE.md on any kill. Next: eval e1 (RUN_COMMANDS §3)
  after clean finish, then OWNER GATE (epoch 2 is an owner call).
- **EPOCH-1 TRAINING COMPLETE 2026-08-26 21:39, clean exit 0 — a
  SINGLE UNSEGMENTED run** (no kills, no resume chain needed): all
  5,736 iters, 12:07 → 21:39 ≈ 9.5 h (inside the 9.0–9.9 h band).
  Final val loss **0.084** (iter-1 baseline 0.697); train loss ~0.03
  at the tail; peak mem 7.84 GB. Final adapter:
  `finetune/checkpoints/qwen2.5-7b-finscreen-lora-mlx-v12-epoch1/adapters.safetensors`
  (+ numbered checkpoints every 100 iters through 0005700). **EVAL e1
  LAUNCHED 2026-08-26 21:40** per RUN_COMMANDS §3 (authorized within
  the campaign; no new owner input needed) → out-dir
  `finetune/runs/2026-08-27-v12-eval-epoch1/`. After it: STOP —
  epoch-1 OWNER READ, epoch 2 only on the owner's call.
- **EVAL e1 COMPLETE 2026-08-26 22:28 (48 min), exit 0, `partial:
  false`** — sanity block all green (mlx_data_v12, sha matches train
  manifest, instruction byte-identical `ebc45a85…`, n_rows 1010).
  Report: `finetune/runs/2026-08-27-v12-eval-epoch1/eval_report.md`.
  Headlines (AGREEMENT with the v1.2 teacher, 1,002 headline rows;
  v1.1-e1 figures in parentheses are against the v1.1 teacher — the
  target moved 27.48% exact-set, so cross-rubric exact-set deltas are
  NOT student regressions per se): parse/schema failures 0.00% (0.00%);
  sentiment 82.6% (81.7%), macro F1 0.788 (0.761), NEGATIVE recall
  0.496 (0.425); guidance raw 48.6% (47.7%) / post-ruled missing→NONE
  98.1% (98.4%); red_flags EXACT-SET 59.38% (62.77%), categories-only
  62.67% (63.57%); red_flags PER-CATEGORY 91.62% (91.58%), micro F1
  0.766 (0.760), macro F1 0.772 (0.758). Category F1 moves: DEMAND
  +0.085, MARGIN +0.024, IMPAIR +0.018, TRADE +0.012, SUPPLY +0.001,
  **LEGAL −0.054 (recall 0.811→0.709; the 300 HYP→REAL v1.2 flips)**;
  modality-given-category 93.32% (95.13%). Exact-set by section:
  EX99 64.2% (flat), MDA 58.6% (64.0%), RISK_FACTORS 40.7% (54.1% —
  tracks the 41.6% RISK_FACTORS label churn). Throughput probe:
  1,245.7 chunks/h (was 1,067.5). **STOPPED at the owner gate:
  epoch-2 go and G1 are the owner's calls. Nothing running.**
- **EPOCH-2 GO (owner, in chat) → LAUNCHED 2026-08-27 00:18** as a
  main-session background task (RUN_COMMANDS §4: fresh cosine at half
  peak LR 1.0e-4, resuming the epoch-1 final adapter; resolved config
  sha matched `plan-epoch2/mlx_lora_config.yaml` `2efa4ea4…` exactly).
  Projected finish ~09:30. Then: eval e2 (§5) → **owner rules G1** —
  and, per the same owner message, **F3 P2 is GO**, queued strictly
  after eval e2 (never concurrent with training; see `F3_PROGRESS.md`
  and HANDOFF §3 2026-08-27 entry).
- **H3v2 RATIFIED 2026-08-27 (owner, in chat — HANDOFF §3 item 4):**
  re-run H3's attenuation measurement on the repaired v1.2 student so
  the G1 read has retention numbers, not just agreement. Day sequence
  (owner-confirmed): epoch 2 (running) → eval e2 → F3 P2 → P3 QA
  agent + H3v2 relabel (relabel is the GPU slot; P3 is file-reads
  only). finetune-engineer (Opus) is prepping `relabel_e1.py` v1.2
  support offline NOW, during training — no GPU, new output paths
  (H3's v1.1 artifacts are a ruled record, never overwritten). Staged
  commands will land in `data/hardening/status/H3v2_attenuation.md`
  §1; quant-modeler comparison (§3 analogue) after the parquet lands.
- **H3v2 PREP DONE 2026-08-27 00:55** (finetune-engineer, offline, no
  GPU; training verified untouched). `relabel_e1.py` gained a single
  `--v12` profile flag flipping all eight campaign paths together
  (each still individually overridable); tests 20 → **36 passed**
  (re-verified by the main session), incl. a regression that rebuilds
  H3's ruled parquet byte-identically (`5de9230b…`) from the real
  journal with all new args defaulted. Output scheme:
  `data/hardening/h3v2/*_v12.*`, run id `H3v2-e1-relabel-v12-epoch2`.
  **Sidecar WRITTEN by the main session** (6,746 rows in corpus
  order, 6,694 identical / 52 head-truncated / 0 non-prefix).
  Schema finding: v1.2 teacher parquet is 34 fields (adds
  `rubric_version`, `system_prompt_sha256`, `completion_batch_id`) →
  output 40 cols; null-typed `parse_error` widened to string (only
  deliberate divergence). Traps recorded in the run doc: eval-e2 dir
  MUST be named `runs/2026-08-28-v12-eval-epoch2/` (the §5 pinned
  name) or `--reference-predictions` must be passed; adapter↔eval
  cross-check guard added (3-s SystemExit beats a 4.7-h waste).
  Observed epoch-2 pace ~6.3–6.9 s/iter early (agent CPU contention
  during prep; may recover toward 5.7) → finish band ~09:30–10:45.
- **EPOCH-2 TRAINING COMPLETE 2026-08-27 09:21, clean exit 0, a
  SINGLE UNSEGMENTED run** (pace recovered post-contention): all
  5,736 iters, 00:18 → 09:21 ≈ 9.05 h. Final val loss **0.076**
  (epoch-1 final: 0.084). Adapter:
  `finetune/checkpoints/qwen2.5-7b-finscreen-lora-mlx-v12-epoch2/adapters.safetensors`.
  **EVAL e2 LAUNCHED 09:22** into the §5-pinned dir
  `finetune/runs/2026-08-28-v12-eval-epoch2/` (name deliberate — the
  H3v2 `--v12` profile expects it). Overnight chain continues per
  HANDOFF §3 2026-08-27 item 5.
- **EVAL e2 COMPLETE 2026-08-27 ~10:10, exit 0, `partial: false`,
  sanity block green** (v12 data, sha match, instruction `ebc45a85…`,
  adapter = v12-epoch2 `cadca849…`). **This is the G1 report.**
  Headlines (vs v1.2-e1 → the epoch-2 gain; parenthetical = v1.1-e2,
  the equal-epoch instrument comparison, different teacher): parse
  0.00%; sentiment 83.6% from 82.6% (v1.1-e2: 83.5%), macro F1 0.797
  (0.786), NEGATIVE recall 0.529; guidance raw 52.1% from 48.6%
  (58.8%), missing 261; red_flags EXACT-SET 63.07% from 59.38%
  (64.87%), cat-only 65.97% (65.87%); PER-CATEGORY 92.42% from 91.62%
  (92.42% — identical), micro F1 0.795 (0.787), macro F1 **0.802**
  from 0.772 (0.793); modality 95.24% from 93.32% (95.73%). Category
  F1 vs v1.2-e1: DEMAND 0.802↑, SUPPLY 0.779↑↑, MARGIN 0.745↑,
  TRADE 0.837↑, LEGAL 0.791↑ (partial recovery), IMPAIR 0.860↓
  (slight). Report: `runs/2026-08-28-v12-eval-epoch2/eval_report.md`.
  **F3 P2 STARTED 2026-08-27 ~10:12** (earnings segment first, log
  `data/f3/p2_earnings.log`). Chain: 10-K → 10-Q → merge → P3 QA +
  H3v2 relabel.
- **F3 P2 DONE 12:56** (see `data/f3/status/P2_runs.md` — 28,900
  sections, all invariants held). **H3v2 SMOKE PASSED ~13:03**: 10/10
  rows, reproduction check **10/10 byte-identical** to the epoch-2
  eval, 0 parse/schema failures, 40 cols, adapter cross-check green,
  genuinely-disagreeing rows (real relabel). **H3v2 FULL RELABEL
  LAUNCHED ~13:05** (main-session background, ~4.7 h, log
  `data/hardening/h3v2/e1_relabel_v12.log`; resume = identical
  command) **+ P3 QA agent launched** (ratified overlap). Next after
  relabel: `--finalize-only` → quant-modeler retention comparison →
  tech-council G1 advisory.
- **H3v2 RELABEL COMPLETE + FINALIZED 2026-08-27 17:32** — single
  segment, 0 kills, 4.57 h, 1,477.7 chunks/h; **6,746/6,746 rows, 0
  parse failures, 0 schema violations, all `finish=stop`;
  reproduction check 1,010/1,010 byte-identical to the epoch-2 eval,
  all provenance cross-checks true** (adapter `cadca849…`). Parquet
  `data/hardening/h3v2/e1_relabel_student_v12.parquet` (40 cols, sha
  `3dbfba64…`). Run record appended as §2 of
  `data/hardening/status/H3v2_attenuation.md`. **quant-modeler
  (Opus) LAUNCHED ~17:40 for §3** — retention comparison vs the v1.1
  benchmark + kill-criterion-2 read (IC-delta backtest arm skipped
  per H3 §3.4's uninformativeness finding, stated in-brief). F3 note:
  P3 + P4 both DONE this afternoon (see `F3_PROGRESS.md`) — P4 found
  2 blocking items on P3's proposals, parked owner-visible.
- **H3v2 §3 COMPARISON DONE 2026-08-27 ~18:00** (quant-modeler; all
  six pre-verifications passed incl. bit-identical reproduction of
  H3's ruled v1.1 values through the new wrapper; frozen shas
  unchanged). **Eval-only red-flag family retention 0.6694 →
  0.8078 [0.7503, 0.8528]: kill-band ρ≈0.81 no longer breached but
  NOT cleared — the band sits INSIDE the CI (point −0.0022).**
  Sentiment fully recovered: negshare 0.7833 [0.6130, 0.8935] (CI
  entirely above its 0.57 band), mean_score 0.8696. 0/12 members
  with CIs including zero (v1.1: 2/12); worst now DEMAND_mda 0.4238,
  MARGIN_mda 0.6000. **Attribution surprise (2×2 cross-pairing):
  only ~⅓ of the family gain is the student (+0.0481 [+0.0096,
  +0.1015] teacher-fixed); press-rate recovery entirely the rubric;
  the one clean student win is sentiment_negative_share (+0.1566).**
  Also: guidance_signed_mean pooled regressed (0.8884 → 0.6248;
  student omits the field on 385 vs 321 chunks); memorization
  penalty collapsed 0.174 → 0.037; **the v1.2 teacher's own error
  is UNMEASURED — v1.1's noise constants must not be quoted as
  v1.2's** (flagged in the manifest). IC-delta arm deliberately not
  run (H3 §3.4). Full §3 in `data/hardening/status/H3v2_attenuation.md`;
  scripts/JSON under `data/hardening/h3v2/`. **tech-council convened
  ~18:05 for the G1 advisory** (advisory only; owner rules).
- **COUNCIL ADVISORY DELIVERED 2026-08-27 ~18:15** —
  `data/hardening/status/G1_council_advisory.md` (verbatim; model
  counsel, never the owner's judgment). Verdict: **ACCEPT-WITH-
  CONDITIONS, 5–0 on the ruling; 3–2 sequencing split** (majority:
  F4 may launch with the v1.2 spot-check concurrent; dissent
  CRO-research + CRO-risk: spot-check completes before F4's first
  overnight). Five conditions incl. an agent-based ~200-chunk v1.2
  spot-check ($0 API) to measure the v1.2 teacher's own error, per-
  feature retention reporting, teacher-arm controls on cross-rubric
  claims, retiring v1.1 noise constants from v1.2 artifacts, and the
  missing→NONE decision before F4. §7 pre-commitments proposed for
  ratification alongside the ruling. **OVERNIGHT CHAIN COMPLETE —
  everything the owner needs is on disk; NOTHING RUNNING; awaiting
  the owner's G1 ruling + F4 decisions.**
- **G1 RULED 2026-08-27 evening (owner, in chat): ACCEPT-WITH-
  CONDITIONS, B1 sequencing** + F4 config ruled (W1-core + full
  reflow_v1 + missing→NONE at writer with audit flag = 314,211
  chunks ≈ 21–29 overnights) — full record HANDOFF §3. **SPOTCHECK
  v1.2 CAMPAIGN OPEN:** design pre-registered
  (`data/hardening/spotcheck_v12/SPOTCHECK_v12_design.md` — n=200
  seed 20260827, kill boundary k≥84/200, one-draw stopping rule,
  S8 uncontested probe); **6 blind label-auditor batches LAUNCHED
  ~19:05** (5 primary + batch-01 replicate). Next per design §7.3:
  write verdicts → adjudicator batches → analyze (model-consensus)
  → owner rules needs_human + 20-row probe → owner-ratified
  estimate. EA-779 census in flight in parallel.
- **SPOTCHECK AUDIT PHASE DONE ~20:15**: all 6 blind batches
  returned, validated (200/200 unique rows + 40-row replicate, ids
  exact, reasons on every row), concatenated to
  `verdicts/rater_a.json`. **Contested: 91/200 = 45.5%** (design
  expected 50–70; the builder's own printed note applies — the
  contested rate becomes an error rate only after adjudication).
  **3 label-adjudicator batches LAUNCHED ~20:20** over the 91
  contested rows. Next: concatenate adjudications → `analyze_v12.py`
  (model-consensus estimate + probe_ids) → owner rules needs_human
  set + 20-row S8 probe.
- **ADJUDICATION DONE + PRE-REGISTERED ANALYSIS RUN ~21:10.**
  Adjudicators: 91/91 resolved — **87 disagree / 4 agree**, 22
  needs_human. **MODEL-CONSENSUS P1: exact-set error 87/200 =
  43.50% [36.82, 50.43] → k=87 ≥ 84 → THE RATIFIED KILL-CRITERION
  FIRES ON CONSENSUS** (§7 item 1: Wilson LB 36.82% > 35%).
  Secondaries: category-set-only 36.00%; per-category-decision
  10.83% [8.75, 13.00]; RISK_FACTORS worst section 62.5%;
  **v1.1→v1.2-CHANGED rows err at 70.9% vs 33.1% unchanged**; error
  modes: spurious 68 / modality 33 / missed 29 (the v1.2 teacher
  OVER-flags); S7 replicate 90% self-agreement (rater noise
  bounded); **v1.2 − v1.1 TierC difference Newcombe 95%
  [+1.1pp, +31.7pp] — excludes zero** (cross-rubric caveat
  attached). NOT FINAL: owner rulings supersede — 22 needs_human
  (each stored-right ruling lowers k by 1; 4+ → below boundary) +
  20-row S8 probe (≥2/20 overturns → adjudicate all 109 uncontested
  once). **Owner packet: `data/hardening/spotcheck_v12/OWNER_RULING_PACKET.md`.
  B1 GATE: F4 does not launch until the owner rules and the
  owner-ratified estimate is computed.** All model-consensus; both
  raters same model family — shared bias invisible, estimate
  plausibly biased LOW per the pre-registration's own provenance
  rule.
- **EVAL WIRING FIXED 2026-08-26** (same status report, §6a): `eval.py`
  gained `--mlx-data-dir` / `--prepared-dir` / `--splits-eval-parquet`.
  E1 defaults are byte-compatible (pinned by a test that captures the
  resolved paths when the flags are omitted) and the fail-safe is intact
  — a wrong data dir still `SystemExit`s on the training manifest's sha
  check before any model load, now naming both datasets, and writes no
  `predictions.jsonl`. **154 tests + 36/36 under the mlx venv.**
  `RUN_COMMANDS.md` §6 now holds the WHOLE campaign copy-paste: train e1
  → eval e1 → owner gate → train e2 → eval e2 → G1, ≈20.2 h, $0.

## F2.5 COMPLETE 2026-08-25 — all six items DONE

Owner rulings now due (one session): **G1** (the measured evidence is
in: sentiment holds, red-flag block breaches kill-criterion 2 — accept
partially / repair the instrument ($16.09 re-label + retrain, requires
lifting the spend freeze + ratifying rubric v1.2, ~2 nights) / third
epoch) and **the stopping rule** (council Option 1 + the
margin-setting-procedure reconciliation). **F3 (extraction) is
labeler-independent and can start regardless of the G1 path.**

## Sequencing notes
- H1/H2/H4/H5/H6 run in parallel (disjoint files; H1 must not touch
  diagnose.py/backtest.py — H2 owns them).
- H3 implementation now; the ~5–6 h overnight runs in the main session
  when implementation lands; the quant-modeler comparison follows the
  run; **G1 is ruled by the owner on its result.**
- After all six + owner ratifications (G1, H5): F3 starts.
