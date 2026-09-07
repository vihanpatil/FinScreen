# FinScreen held-out evaluation — 2026-08-21-eval-epoch1

Generated 2026-08-21T21:23:15.115176+00:00 · adapter `/Users/vihanpatil/personal/projects/FinScreen/finetune/checkpoints/qwen2.5-7b-finscreen-lora-mlx-epoch1-final-from-2250` · base `/Users/vihanpatil/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed`

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
| adapter dir | `/Users/vihanpatil/personal/projects/FinScreen/finetune/checkpoints/qwen2.5-7b-finscreen-lora-mlx-epoch1-final-from-2250` |
| adapters.safetensors sha256 | `3c6adc9eedaec2adc7f7b4bd3c4c2b3e8b2e970ac63f6679570562be948f25e8` |
| adapters.safetensors matches checkpoint | `0003400_adapters.safetensors` |
| adapter_config.json sha256 | `cb0815ffc2bace85269b88fb816f26a84de83121ffcaf5c01d28a25696fad4d8` |
| training run manifest | `/Users/vihanpatil/personal/projects/FinScreen/finetune/runs/2026-08-21-epoch1-final-from-2250/manifest.json` |
| eval rows | `/Users/vihanpatil/personal/projects/FinScreen/finetune/mlx_data/valid.jsonl` |
| eval rows sha256 | `deb63b76992404ecaf4fdc4c3a3acbea9b0c3bb7f655064aec7191ebc9ab0736` |
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

n = 867 rows where the teacher's label includes this field. **Exact-match agreement with the teacher: 81.7%** (708/867). Teacher's own second-rater agreement on this field: 94.6% [91.3, 96.7].

| class | support | TP | FP | FN | P | R | F1 | note |
|---|---|---|---|---|---|---|---|---|
| POSITIVE | 247 | 227 | 51 | 20 | 0.817 | 0.919 | 0.865 |  |
| NEUTRAL | 507 | 433 | 62 | 74 | 0.875 | 0.854 | 0.864 |  |
| NEGATIVE | 113 | 48 | 12 | 65 | 0.800 | 0.425 | 0.555 |  |

Macro over classes **with support in this split** (POSITIVE, NEUTRAL, NEGATIVE): P=0.831 R=0.733 F1=0.761. Zero-support classes are excluded from this average and listed as not evaluable rather than averaged in as structural zeros.

Failure attribution (counted as errors, never dropped): `{'__MISSING_FIELD__': 34}`

Top confusions (gold -> predicted): `NEGATIVE->NEUTRAL` × 42, `NEUTRAL->POSITIVE` × 42, `NEUTRAL->__MISSING_FIELD__` × 20, `POSITIVE->NEUTRAL` × 20, `NEGATIVE->__MISSING_FIELD__` × 14, `NEUTRAL->NEGATIVE` × 12, `NEGATIVE->POSITIVE` × 9

## 3. guidance_direction

### guidance_direction (5-class)

n = 570 rows where the teacher's label includes this field. **Exact-match agreement with the teacher: 47.7%** (272/570). Teacher's own second-rater agreement on this field: 95.2% [90.4, 97.6].

| class | support | TP | FP | FN | P | R | F1 | note |
|---|---|---|---|---|---|---|---|---|
| RAISED | 7 | 5 | 1 | 2 | 0.833 | 0.714 | 0.769 | **very low support (n=7) — not a stable estimate** |
| MAINTAINED | 7 | 3 | 4 | 4 | 0.429 | 0.429 | 0.429 | **very low support (n=7) — not a stable estimate** |
| LOWERED | 3 | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 | **very low support (n=3) — not a stable estimate** |
| WITHDRAWN | 0 | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 | **NOT EVALUABLE — zero support in eval** |
| NONE | 553 | 261 | 4 | 292 | 0.985 | 0.472 | 0.638 |  |

Macro over classes **with support in this split** (RAISED, MAINTAINED, LOWERED, NONE): P=0.812 R=0.654 F1=0.709. Zero-support classes are excluded from this average and listed as not evaluable rather than averaged in as structural zeros.
- `WITHDRAWN`: NOT EVALUABLE — guidance_direction=WITHDRAWN has exactly 1 example corpus-wide and it is in the TRAIN split, so eval support is 0. A P/R/F1 row for it would be three zeros masquerading as a measurement (HANDOFF.md §7).

Failure attribution (counted as errors, never dropped): `{'__MISSING_FIELD__': 289}`

Top confusions (gold -> predicted): `NONE->__MISSING_FIELD__` × 289, `MAINTAINED->NONE` × 4, `NONE->MAINTAINED` × 2, `RAISED->MAINTAINED` × 2, `NONE->RAISED` × 1

## 4. red_flags — exact-set basis

- **Exact set match on (category, modality): 62.77%** (629/1002 rows)
- Exact set match on categories only (modality ignored): 63.57% (637/1002 rows)
- 0 of these rows were unparseable and are counted as mismatches.

This basis is strict by construction: one added, dropped or re-modalized category
on a multi-flag chunk fails the whole row. It is the same basis as the spot-check's
63.4% teacher-vs-auditor figure, so it is the comparable one — but it is NOT
comparable to the single-value sentiment/guidance rates above.

## 5. red_flags — per-category decomposition

- **Per-category agreement: 91.58%** (506 wrong decisions over 6012 chunk-category decisions = 1002 rows × 6 categories). Teacher's own per-category error on the spot-check sample: 7.5% (180 category corrections / 2,394 chunk-category decisions).

Note this rate is dominated by true negatives (most chunk-category cells are
correctly empty), which is exactly why the P/R/F1 table below is the honest read
of it and the headline percentage is not.

| category | support | TP | FP | FN | P | R | F1 | note |
|---|---|---|---|---|---|---|---|---|
| DEMAND_WEAKNESS | 202 | 118 | 18 | 84 | 0.868 | 0.584 | 0.698 |  |
| SUPPLY_INPUT_CONSTRAINT | 148 | 81 | 3 | 67 | 0.964 | 0.547 | 0.698 |  |
| TRADE_POLICY_EXPOSURE | 105 | 80 | 14 | 25 | 0.851 | 0.762 | 0.804 |  |
| IMPAIRMENT_WRITEDOWN | 154 | 131 | 20 | 23 | 0.868 | 0.851 | 0.859 |  |
| MARGIN_COST_PRESSURE | 242 | 149 | 59 | 93 | 0.716 | 0.616 | 0.662 |  |
| LEGAL_REGULATORY_ACTION | 297 | 241 | 44 | 56 | 0.846 | 0.811 | 0.828 |  |

- Micro (all categories pooled): P=0.835 R=0.697 F1=0.760 (TP=800 FP=158 FN=348)
- Macro over categories with support (DEMAND_WEAKNESS, SUPPLY_INPUT_CONSTRAINT, TRADE_POLICY_EXPOSURE, IMPAIRMENT_WRITEDOWN, MARGIN_COST_PRESSURE, LEGAL_REGULATORY_ACTION): P=0.852 R=0.695 F1=0.758
- Modality agreement, restricted to (row, category) cells where both sides say the category is present: 95.13% (761/800), confusion `{'REALIZED->HYPOTHETICAL': 19, 'HYPOTHETICAL->REALIZED': 20}`

## 6. Field-presence (applicability) agreement

`section_type` is never in the prompt (PROMPT_TEMPLATE.md), so *which* fields to
emit is itself learned from the passage's register. This measures that directly.

| field | n determined | n agree | agreement | breakdown |
|---|---|---|---|---|
| sentiment | 1002 | 966 | 96.41% | `{'gold_no_pred_no': 133, 'gold_yes_pred_yes': 833, 'gold_yes_pred_no': 34, 'gold_no_pred_yes': 2}` |
| guidance_direction | 1002 | 704 | 70.26% | `{'gold_no_pred_no': 423, 'gold_yes_pred_no': 289, 'gold_yes_pred_yes': 281, 'gold_no_pred_yes': 9}` |

## 7. Throughput (doubles as EXPANSION_PLAN F4's labeling-throughput probe)

- Rows generated this process: 39 in 131.5s → **1067.5 chunks/hour**
- Per-row latency (s): mean 3.372, p50 3.083, p95 5.248, p99 5.503, max 5.509
- Prompt tokens: mean 1188.8, total 46363
- Generated tokens: mean 52.0, max 112, total 2028
- Prefill: mean 873.1 tok/s · Decode: mean 27.1 tok/s
- Finish reasons: `{'stop': 39}` (`length` means the row hit --max-tokens and its JSON is probably truncated)

These figures are EXPANSION_PLAN.md F4's labeling-throughput probe, measured at n=1,010 on this machine with this adapter.

| E2 labeling workload | hours @ measured rate | ≈ 10h overnights |
|---|---|---|
| E1 re-label (6,746 chunks) | 6.3 | 0.6 |
| E2 low estimate (~70k new + 6,746 E1 = 76,746) | 71.9 | 7.2 |
| E2 high estimate (~98k new + 6,746 E1 = 104,746) | 98.1 | 9.8 |

Single-stream, no prefix cache, no batching. EXPANSION_PLAN §2b lists both
as free levers that were not used here.

## 8. Excluded slices, reported separately (never headline)

**8K_BODY, n=8 — NOT EVALUABLE.** n=8 corpus-wide from only 2 tickers (BAC, CVX); all 8 landed in the eval split. No per-class estimate on 8 rows from 2 issuers is stable, so 8K_BODY rows are excluded from every headline table and reported separately below (HANDOFF.md §7).

Shown for completeness only: sentiment exact-match 100.0% (n=8), guidance exact-match 25.0% (n=8), red_flags exact-set 62.5% (n=8), parse failures 0.

Do not average these into anything.

## 9. Per-section-type breakdown (headline rows only)

| section_type | n | parse-fail | sentiment exact | guidance exact | red_flags exact-set | red_flags per-category |
|---|---|---|---|---|---|---|
| EX99_PRESS_RELEASE | 570 | 0.00% | 83.3% (n=570) | 47.7% (n=570) | 64.2% | 91.58% |
| MDA | 297 | 0.00% | 78.5% (n=297) | n/a | 64.0% | 91.98% |
| RISK_FACTORS | 135 | 0.00% | n/a | n/a | 54.1% | 90.74% |

The spot-check found red_flags weakest in RISK_FACTORS (59.2% teacher-vs-auditor);
compare that row specifically rather than the pooled figure.

---

Full machine-readable results: `metrics.json` · raw generations: `predictions.jsonl` · run provenance: `manifest.json` (same directory).

