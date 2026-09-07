# FinScreen held-out evaluation — 2026-08-21-eval-smoke

Generated 2026-08-21T14:22:37.577397+00:00 · adapter `/Users/vihanpatil/personal/projects/FinScreen/finetune/checkpoints/qwen2.5-7b-finscreen-lora-mlx-epoch1-final-from-2250` · base `/Users/vihanpatil/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed`

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

Headline row count: **20** of 20 eval rows (0 excluded as 8K_BODY).
Section-type mix of the full eval split: `{'RISK_FACTORS': 2, 'MDA': 5, 'EX99_PRESS_RELEASE': 13}`

> **SMOKE RUN — `--limit 20` was set, so this covers only the first
> 20 of 1010 eval rows, in split order.**
> The eval split is not shuffled here, so this slice is NOT a random sample and
> its rates are not the held-out result. Use it to check the plumbing only.

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

- **Parse-failure rate: 0.00%** (0/20 rows). Reasons: `{}`.
- Rows with no prediction at all: 0.
- **Schema-violation rate: 0.00%** (0/20 rows that parsed as JSON but broke the target schema). Issues: `{}`.

An unparseable row is counted as an error against every field the teacher labelled
for that row, and as a set-level mismatch for `red_flags` even when the teacher's
set is empty — scoring "no output" as a correct empty set would inflate the
red-flag headline substantially, since most rows have no flags.

## 2. sentiment

### sentiment (3-class)

n = 18 rows where the teacher's label includes this field. **Exact-match agreement with the teacher: 100.0%** (18/18). Teacher's own second-rater agreement on this field: 94.6% [91.3, 96.7].

| class | support | TP | FP | FN | P | R | F1 | note |
|---|---|---|---|---|---|---|---|---|
| POSITIVE | 7 | 7 | 0 | 0 | 1.000 | 1.000 | 1.000 | **very low support (n=7) — not a stable estimate** |
| NEUTRAL | 10 | 10 | 0 | 0 | 1.000 | 1.000 | 1.000 |  |
| NEGATIVE | 1 | 1 | 0 | 0 | 1.000 | 1.000 | 1.000 | **very low support (n=1) — not a stable estimate** |

Macro over classes **with support in this split** (POSITIVE, NEUTRAL, NEGATIVE): P=1.000 R=1.000 F1=1.000. Zero-support classes are excluded from this average and listed as not evaluable rather than averaged in as structural zeros.

## 3. guidance_direction

### guidance_direction (5-class)

n = 13 rows where the teacher's label includes this field. **Exact-match agreement with the teacher: 53.8%** (7/13). Teacher's own second-rater agreement on this field: 95.2% [90.4, 97.6].

| class | support | TP | FP | FN | P | R | F1 | note |
|---|---|---|---|---|---|---|---|---|
| RAISED | 0 | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 | **NOT EVALUABLE — zero support in eval** |
| MAINTAINED | 0 | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 | **NOT EVALUABLE — zero support in eval** |
| LOWERED | 0 | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 | **NOT EVALUABLE — zero support in eval** |
| WITHDRAWN | 0 | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 | **NOT EVALUABLE — zero support in eval** |
| NONE | 13 | 7 | 0 | 6 | 1.000 | 0.538 | 0.700 |  |

Macro over classes **with support in this split** (NONE): P=1.000 R=0.538 F1=0.700. Zero-support classes are excluded from this average and listed as not evaluable rather than averaged in as structural zeros.
- `RAISED`: NOT EVALUABLE — zero support in the eval split
- `MAINTAINED`: NOT EVALUABLE — zero support in the eval split
- `LOWERED`: NOT EVALUABLE — zero support in the eval split
- `WITHDRAWN`: NOT EVALUABLE — guidance_direction=WITHDRAWN has exactly 1 example corpus-wide and it is in the TRAIN split, so eval support is 0. A P/R/F1 row for it would be three zeros masquerading as a measurement (HANDOFF.md §7).

Failure attribution (counted as errors, never dropped): `{'__MISSING_FIELD__': 6}`

Top confusions (gold -> predicted): `NONE->__MISSING_FIELD__` × 6

## 4. red_flags — exact-set basis

- **Exact set match on (category, modality): 65.00%** (13/20 rows)
- Exact set match on categories only (modality ignored): 70.00% (14/20 rows)
- 0 of these rows were unparseable and are counted as mismatches.

This basis is strict by construction: one added, dropped or re-modalized category
on a multi-flag chunk fails the whole row. It is the same basis as the spot-check's
63.4% teacher-vs-auditor figure, so it is the comparable one — but it is NOT
comparable to the single-value sentiment/guidance rates above.

## 5. red_flags — per-category decomposition

- **Per-category agreement: 93.33%** (8 wrong decisions over 120 chunk-category decisions = 20 rows × 6 categories). Teacher's own per-category error on the spot-check sample: 7.5% (180 category corrections / 2,394 chunk-category decisions).

Note this rate is dominated by true negatives (most chunk-category cells are
correctly empty), which is exactly why the P/R/F1 table below is the honest read
of it and the headline percentage is not.

| category | support | TP | FP | FN | P | R | F1 | note |
|---|---|---|---|---|---|---|---|---|
| DEMAND_WEAKNESS | 3 | 2 | 0 | 1 | 1.000 | 0.667 | 0.800 | **very low support (n=3)** |
| SUPPLY_INPUT_CONSTRAINT | 0 | 0 | 1 | 0 | 0.000 | 0.000 | 0.000 | **NOT EVALUABLE — zero support in eval** |
| TRADE_POLICY_EXPOSURE | 0 | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 | **NOT EVALUABLE — zero support in eval** |
| IMPAIRMENT_WRITEDOWN | 2 | 1 | 0 | 1 | 1.000 | 0.500 | 0.667 | **very low support (n=2)** |
| MARGIN_COST_PRESSURE | 5 | 3 | 2 | 2 | 0.600 | 0.600 | 0.600 | **very low support (n=5)** |
| LEGAL_REGULATORY_ACTION | 2 | 2 | 1 | 0 | 0.667 | 1.000 | 0.800 | **very low support (n=2)** |

- Micro (all categories pooled): P=0.667 R=0.667 F1=0.667 (TP=8 FP=4 FN=4)
- Macro over categories with support (DEMAND_WEAKNESS, IMPAIRMENT_WRITEDOWN, MARGIN_COST_PRESSURE, LEGAL_REGULATORY_ACTION): P=0.817 R=0.692 F1=0.717
- Zero-support categories, excluded from the macro and NOT evaluable: `['SUPPLY_INPUT_CONSTRAINT', 'TRADE_POLICY_EXPOSURE']`
- Modality agreement, restricted to (row, category) cells where both sides say the category is present: 87.50% (7/8), confusion `{'REALIZED->HYPOTHETICAL': 1}`

## 6. Field-presence (applicability) agreement

`section_type` is never in the prompt (PROMPT_TEMPLATE.md), so *which* fields to
emit is itself learned from the passage's register. This measures that directly.

| field | n determined | n agree | agreement | breakdown |
|---|---|---|---|---|
| sentiment | 20 | 20 | 100.00% | `{'gold_no_pred_no': 2, 'gold_yes_pred_yes': 18}` |
| guidance_direction | 20 | 14 | 70.00% | `{'gold_no_pred_no': 7, 'gold_yes_pred_no': 6, 'gold_yes_pred_yes': 7}` |

## 7. Throughput (doubles as EXPANSION_PLAN F4's labeling-throughput probe)

- Rows generated this process: 20 in 43.7s → **1649.4 chunks/hour**
- Per-row latency (s): mean 2.182, p50 2.22, p95 2.974, p99 3.201, max 3.258
- Prompt tokens: mean 982.1, total 19643
- Generated tokens: mean 28.5, max 59, total 570
- Prefill: mean 880.8 tok/s · Decode: mean 28.8 tok/s
- Finish reasons: `{'stop': 20}` (`length` means the row hit --max-tokens and its JSON is probably truncated)

These figures are EXPANSION_PLAN.md F4's labeling-throughput probe, measured at n=1,010 on this machine with this adapter.

| E2 labeling workload | hours @ measured rate | ≈ 10h overnights |
|---|---|---|
| E1 re-label (6,746 chunks) | 4.1 | 0.4 |
| E2 low estimate (~70k new + 6,746 E1 = 76,746) | 46.5 | 4.7 |
| E2 high estimate (~98k new + 6,746 E1 = 104,746) | 63.5 | 6.4 |

Single-stream, no prefix cache, no batching. EXPANSION_PLAN §2b lists both
as free levers that were not used here.

## 8. Excluded slices, reported separately (never headline)

No 8K_BODY rows in the scored set.

## 9. Per-section-type breakdown (headline rows only)

| section_type | n | parse-fail | sentiment exact | guidance exact | red_flags exact-set | red_flags per-category |
|---|---|---|---|---|---|---|
| EX99_PRESS_RELEASE | 13 | 0.00% | 100.0% (n=13) | 53.8% (n=13) | 61.5% | 91.03% |
| MDA | 5 | 0.00% | 100.0% (n=5) | n/a | 100.0% | 100.00% |
| RISK_FACTORS | 2 | 0.00% | n/a | n/a | 0.0% | 91.67% |

The spot-check found red_flags weakest in RISK_FACTORS (59.2% teacher-vs-auditor);
compare that row specifically rather than the pooled figure.

---

Full machine-readable results: `metrics.json` · raw generations: `predictions.jsonl` · run provenance: `manifest.json` (same directory).

