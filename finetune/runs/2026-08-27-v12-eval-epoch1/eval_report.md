# FinScreen held-out evaluation — 2026-08-27-v12-eval-epoch1

Generated 2026-08-27T02:39:27.894878+00:00 · adapter `/Users/vihanpatil/personal/projects/FinScreen/finetune/checkpoints/qwen2.5-7b-finscreen-lora-mlx-v12-epoch1` · base `/Users/vihanpatil/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed`

## Read this before quoting any number

1. **This measures AGREEMENT WITH THE TEACHER, not accuracy.** The eval-split
   labels are Claude's bootstrap labels, not human ground truth. A student that
   agrees perfectly has reproduced the teacher *including the teacher's errors*.
2. **The teacher's red-flag labels are documented as noisy.** Set-level error
   36.6% (146/399 exact-set disagreements, sample-pooled); base-rate-representative
   estimate ~25.0% (Tier C, n=36, 95% CI [13.8, 41.1] on error); per-category
   error 7.5% (180 category corrections / 2,394 chunk-category decisions).
   Source: HANDOFF.md §2a + RED_FLAGS_LIMITATION.md (spot-check second-rater pass, 2026-08-18). A red-flag agreement number materially
   below the teacher's own reproducibility is not separable from teacher noise
   with this eval alone.
3. **`red_flags` is reported on two bases and both are shown, always.** The
   exact-set rate and the per-category rate answer different questions and differ
   by tens of points; quoting only the exact-set figure beside sentiment's
   single-value rate is the specific error HANDOFF.md §2a calls out.
4. **`distress_tier` is not reported.** It was excluded from the training targets
   entirely (PROMPT_TEMPLATE.md / DISCOVERY.md §3), so the student never predicts
   it and any number here would be meaningless.
5. **This is a research/screening classifier.** It extracts signals from text. It
   does not predict prices, recommend trades, or connect to any brokerage.

## Not evaluable — excluded from every headline table

- **8K_BODY** — n=8 corpus-wide from only 2 tickers (BAC, CVX); all 8 landed in the eval split. No per-class estimate on 8 rows from 2 issuers is stable, so 8K_BODY rows are excluded from every headline table and reported separately below (HANDOFF.md §7).
- **WITHDRAWN** — guidance_direction=WITHDRAWN has exactly 1 example corpus-wide and it is in the TRAIN split, so eval support is 0. A P/R/F1 row for it would be three zeros masquerading as a measurement (HANDOFF.md §7).

Headline row count: **1002** of 1010 eval rows (8 excluded as 8K_BODY).
Section-type mix of the full eval split: `{'RISK_FACTORS': 135, 'MDA': 297, 'EX99_PRESS_RELEASE': 570, '8K_BODY': 8}`

## Provenance (verify-artifact rule)

| item | value |
|---|---|
| base model | `/Users/vihanpatil/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed` |
| base weights sha256 | `86110f368236b53cf4c2336f991a85703b17bcc60bb75f292b4002ec0219f071` |
| adapter dir | `/Users/vihanpatil/personal/projects/FinScreen/finetune/checkpoints/qwen2.5-7b-finscreen-lora-mlx-v12-epoch1` |
| adapters.safetensors sha256 | `241b3d409c8d36924af894aa3b1fc3f54b0849d8ae602b69432cc61e3a0b33e5` |
| adapters.safetensors matches checkpoint | `no numbered twin — expected for a COMPLETED run whose iters is not a multiple of save_every (mlx_lm writes the final weights to adapters.safetensors only). If training is still running, this may instead be an in-flight write: check the process has exited.` |
| adapter_config.json sha256 | `40c77bde438e5af70ce51338df407255db2d7f64b82bf9d2445c3f400f48a00c` |
| training run manifest | `/Users/vihanpatil/personal/projects/FinScreen/finetune/runs/2026-08-26-v12-epoch1/manifest.json` |
| eval rows | `/Users/vihanpatil/personal/projects/FinScreen/finetune/mlx_data_v12/valid.jsonl` |
| eval rows sha256 | `b74efdb326e9b862820453eecfa64307f460499cac0fd92562fdf91eb0b1126b` |
| eval rows sha matches training manifest | `True` |
| instruction sha256 | `ebc45a856bff58a562535867e5a1f4173519fe77c58a47b16bfa28e6eea8efe2` |
| instruction byte-identical across eval | `True` |
| instruction byte-identical to train | `True` |
| decoding | `{'backend': 'mlx', 'decoding': 'greedy (temperature 0.0 -> argmax sampler)', 'max_tokens': 520, 'prompt': 'apply_chat_template([system=instruction, user=passage], add_generation_prompt=True)', 'prompt_source': 'convert_to_mlx.render(); the inference prompt is a token-exact prefix of the training sequence for the same row'}` |
| mlx / mlx_lm / transformers | `{'mlx': '0.32.1', 'mlx-lm': '0.31.3', 'transformers': '5.15.1', 'numpy': '2.4.6', 'python': '3.11.10'}` |

## 1. Parse and schema integrity (first-class metrics)

- **Parse-failure rate: 0.00%** (0/1002 rows). Reasons: `{}`.
- Rows with no prediction at all: 0.
- **Schema-violation rate: 0.00%** (0/1002 rows that parsed as JSON but broke the target schema). Issues: `{}`.

An unparseable row is counted as an error against every field the teacher labelled
for that row, and as a set-level mismatch for `red_flags` even when the teacher's
set is empty — scoring "no output" as a correct empty set would inflate the
red-flag headline substantially, since most rows have no flags.

## 2. sentiment

### sentiment (3-class)

n = 867 rows where the teacher's label includes this field. **Exact-match agreement with the teacher: 82.6%** (716/867). Teacher's own second-rater agreement on this field: 94.6% [91.3, 96.7].

| class | support | TP | FP | FN | P | R | F1 | note |
|---|---|---|---|---|---|---|---|---|
| POSITIVE | 246 | 223 | 37 | 23 | 0.858 | 0.907 | 0.881 |  |
| NEUTRAL | 500 | 433 | 65 | 67 | 0.869 | 0.866 | 0.868 |  |
| NEGATIVE | 121 | 60 | 14 | 61 | 0.811 | 0.496 | 0.615 |  |

Macro over classes **with support in this split** (POSITIVE, NEUTRAL, NEGATIVE): P=0.846 R=0.756 F1=0.788. Zero-support classes are excluded from this average and listed as not evaluable rather than averaged in as structural zeros.

Failure attribution (counted as errors, never dropped): `{'__MISSING_FIELD__': 35}`

Top confusions (gold -> predicted): `NEGATIVE->NEUTRAL` × 42, `NEUTRAL->POSITIVE` × 33, `POSITIVE->NEUTRAL` × 23, `NEUTRAL->__MISSING_FIELD__` × 20, `NEGATIVE->__MISSING_FIELD__` × 15, `NEUTRAL->NEGATIVE` × 14, `NEGATIVE->POSITIVE` × 4

## 3. guidance_direction

### guidance_direction (5-class)

n = 570 rows where the teacher's label includes this field. **Exact-match agreement with the teacher: 48.6%** (277/570). Teacher's own second-rater agreement on this field: 95.2% [90.4, 97.6].

| class | support | TP | FP | FN | P | R | F1 | note |
|---|---|---|---|---|---|---|---|---|
| RAISED | 8 | 5 | 2 | 3 | 0.714 | 0.625 | 0.667 | **very low support (n=8) — not a stable estimate** |
| MAINTAINED | 5 | 2 | 4 | 3 | 0.333 | 0.400 | 0.364 | **very low support (n=5) — not a stable estimate** |
| LOWERED | 3 | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 | **very low support (n=3) — not a stable estimate** |
| WITHDRAWN | 0 | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 | **NOT EVALUABLE — zero support in eval** |
| NONE | 554 | 267 | 5 | 287 | 0.982 | 0.482 | 0.646 |  |

Macro over classes **with support in this split** (RAISED, MAINTAINED, LOWERED, NONE): P=0.757 R=0.627 F1=0.669. Zero-support classes are excluded from this average and listed as not evaluable rather than averaged in as structural zeros.
- `WITHDRAWN`: NOT EVALUABLE — guidance_direction=WITHDRAWN has exactly 1 example corpus-wide and it is in the TRAIN split, so eval support is 0. A P/R/F1 row for it would be three zeros masquerading as a measurement (HANDOFF.md §7).

Failure attribution (counted as errors, never dropped): `{'__MISSING_FIELD__': 282}`

Top confusions (gold -> predicted): `NONE->__MISSING_FIELD__` × 282, `MAINTAINED->NONE` × 3, `NONE->MAINTAINED` × 3, `NONE->RAISED` × 2, `RAISED->NONE` × 2, `RAISED->MAINTAINED` × 1

## 4. red_flags — exact-set basis

- **Exact set match on (category, modality): 59.38%** (595/1002 rows)
- Exact set match on categories only (modality ignored): 62.67% (628/1002 rows)
- 0 of these rows were unparseable and are counted as mismatches.

This basis is strict by construction: one added, dropped or re-modalized category
on a multi-flag chunk fails the whole row. It is the same basis as the spot-check's
63.4% teacher-vs-auditor figure, so it is the comparable one — but it is NOT
comparable to the single-value sentiment/guidance rates above.

## 5. red_flags — per-category decomposition

- **Per-category agreement: 91.62%** (504 wrong decisions over 6012 chunk-category decisions = 1002 rows × 6 categories). Teacher's own per-category error on the spot-check sample: 7.5% (180 category corrections / 2,394 chunk-category decisions).

Note this rate is dominated by true negatives (most chunk-category cells are
correctly empty), which is exactly why the P/R/F1 table below is the honest read
of it and the headline percentage is not.

| category | support | TP | FP | FN | P | R | F1 | note |
|---|---|---|---|---|---|---|---|---|
| DEMAND_WEAKNESS | 206 | 139 | 10 | 67 | 0.933 | 0.675 | 0.783 |  |
| SUPPLY_INPUT_CONSTRAINT | 132 | 80 | 17 | 52 | 0.825 | 0.606 | 0.699 |  |
| TRADE_POLICY_EXPOSURE | 107 | 82 | 12 | 25 | 0.872 | 0.766 | 0.816 |  |
| IMPAIRMENT_WRITEDOWN | 152 | 136 | 22 | 16 | 0.861 | 0.895 | 0.877 |  |
| MARGIN_COST_PRESSURE | 287 | 174 | 46 | 113 | 0.791 | 0.606 | 0.686 |  |
| LEGAL_REGULATORY_ACTION | 299 | 212 | 37 | 87 | 0.851 | 0.709 | 0.774 |  |

- Micro (all categories pooled): P=0.851 R=0.696 F1=0.766 (TP=823 FP=144 FN=360)
- Macro over categories with support (DEMAND_WEAKNESS, SUPPLY_INPUT_CONSTRAINT, TRADE_POLICY_EXPOSURE, IMPAIRMENT_WRITEDOWN, MARGIN_COST_PRESSURE, LEGAL_REGULATORY_ACTION): P=0.856 R=0.709 F1=0.772
- Modality agreement, restricted to (row, category) cells where both sides say the category is present: 93.32% (768/823), confusion `{'REALIZED->HYPOTHETICAL': 32, 'HYPOTHETICAL->REALIZED': 23}`

## 6. Field-presence (applicability) agreement

`section_type` is never in the prompt (PROMPT_TEMPLATE.md), so *which* fields to
emit is itself learned from the passage's register. This measures that directly.

| field | n determined | n agree | agreement | breakdown |
|---|---|---|---|---|
| sentiment | 1002 | 964 | 96.21% | `{'gold_no_pred_no': 132, 'gold_yes_pred_yes': 832, 'gold_yes_pred_no': 35, 'gold_no_pred_yes': 3}` |
| guidance_direction | 1002 | 717 | 71.56% | `{'gold_no_pred_no': 429, 'gold_no_pred_yes': 3, 'gold_yes_pred_no': 282, 'gold_yes_pred_yes': 288}` |

## 7. Throughput (doubles as EXPANSION_PLAN F4's labeling-throughput probe)

- Rows generated this process: 1010 in 2918.9s → **1245.7 chunks/hour**
- Per-row latency (s): mean 2.89, p50 2.643, p95 4.903, p99 6.615, max 7.682
- Prompt tokens: mean 1105.4, total 1116491
- Generated tokens: mean 35.0, max 143, total 35350
- Prefill: mean 795.5 tok/s · Decode: mean 24.9 tok/s
- Finish reasons: `{'stop': 1010}` (`length` means the row hit --max-tokens and its JSON is probably truncated)

These figures are EXPANSION_PLAN.md F4's labeling-throughput probe, measured at n=1,010 on this machine with this adapter.

| E2 labeling workload | hours @ measured rate | ≈ 10h overnights |
|---|---|---|
| E1 re-label (6,746 chunks) | 5.4 | 0.5 |
| E2 low estimate (~70k new + 6,746 E1 = 76,746) | 61.6 | 6.2 |
| E2 high estimate (~98k new + 6,746 E1 = 104,746) | 84.1 | 8.4 |

Single-stream, no prefix cache, no batching. EXPANSION_PLAN §2b lists both
as free levers that were not used here.

## 8. Excluded slices, reported separately (never headline)

**8K_BODY, n=8 — NOT EVALUABLE.** n=8 corpus-wide from only 2 tickers (BAC, CVX); all 8 landed in the eval split. No per-class estimate on 8 rows from 2 issuers is stable, so 8K_BODY rows are excluded from every headline table and reported separately below (HANDOFF.md §7).

Shown for completeness only: sentiment exact-match 87.5% (n=8), guidance exact-match 37.5% (n=8), red_flags exact-set 62.5% (n=8), parse failures 0.

Do not average these into anything.

## 9. Per-section-type breakdown (headline rows only)

| section_type | n | parse-fail | sentiment exact | guidance exact | red_flags exact-set | red_flags per-category |
|---|---|---|---|---|---|---|
| EX99_PRESS_RELEASE | 570 | 0.00% | 83.5% (n=570) | 48.6% (n=570) | 64.2% | 92.31% |
| MDA | 297 | 0.00% | 80.8% (n=297) | n/a | 58.6% | 90.91% |
| RISK_FACTORS | 135 | 0.00% | n/a | n/a | 40.7% | 90.25% |

The spot-check found red_flags weakest in RISK_FACTORS (59.2% teacher-vs-auditor);
compare that row specifically rather than the pooled figure.

---

Full machine-readable results: `metrics.json` · raw generations: `predictions.jsonl` · run provenance: `manifest.json` (same directory).

