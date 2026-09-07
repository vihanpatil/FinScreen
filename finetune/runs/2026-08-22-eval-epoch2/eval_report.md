# FinScreen held-out evaluation — 2026-08-22-eval-epoch2

Generated 2026-08-22T11:33:24.379566+00:00 · adapter `/Users/vihanpatil/personal/projects/FinScreen/finetune/checkpoints/qwen2.5-7b-finscreen-lora-mlx-epoch2` · base `/Users/vihanpatil/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed`

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
| adapter dir | `/Users/vihanpatil/personal/projects/FinScreen/finetune/checkpoints/qwen2.5-7b-finscreen-lora-mlx-epoch2` |
| adapters.safetensors sha256 | `9c08e3cb3f1f917c3c6903cc0154f9d175d928f0116edc60e2dd1b2e0f9e7fa8` |
| adapters.safetensors matches checkpoint | `no numbered twin — expected for a COMPLETED run whose iters is not a multiple of save_every (mlx_lm writes the final weights to adapters.safetensors only). If training is still running, this may instead be an in-flight write: check the process has exited.` |
| adapter_config.json sha256 | `539983655bef0692ac512ed757b5724a818bb638a948eab72a0214ebe551fd65` |
| training run manifest | `/Users/vihanpatil/personal/projects/FinScreen/finetune/runs/2026-08-21-epoch2/manifest.json` |
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

n = 867 rows where the teacher's label includes this field. **Exact-match agreement with the teacher: 83.5%** (724/867). Teacher's own second-rater agreement on this field: 94.6% [91.3, 96.7].

| class | support | TP | FP | FN | P | R | F1 | note |
|---|---|---|---|---|---|---|---|---|
| POSITIVE | 247 | 225 | 31 | 22 | 0.879 | 0.911 | 0.895 |  |
| NEUTRAL | 507 | 444 | 62 | 63 | 0.877 | 0.876 | 0.877 |  |
| NEGATIVE | 113 | 55 | 20 | 58 | 0.733 | 0.487 | 0.585 |  |

Macro over classes **with support in this split** (POSITIVE, NEUTRAL, NEGATIVE): P=0.830 R=0.758 F1=0.786. Zero-support classes are excluded from this average and listed as not evaluable rather than averaged in as structural zeros.

Failure attribution (counted as errors, never dropped): `{'__MISSING_FIELD__': 30}`

Top confusions (gold -> predicted): `NEGATIVE->NEUTRAL` × 40, `NEUTRAL->POSITIVE` × 26, `POSITIVE->NEUTRAL` × 22, `NEUTRAL->NEGATIVE` × 20, `NEUTRAL->__MISSING_FIELD__` × 17, `NEGATIVE->__MISSING_FIELD__` × 13, `NEGATIVE->POSITIVE` × 5

## 3. guidance_direction

### guidance_direction (5-class)

n = 570 rows where the teacher's label includes this field. **Exact-match agreement with the teacher: 58.8%** (335/570). Teacher's own second-rater agreement on this field: 95.2% [90.4, 97.6].

| class | support | TP | FP | FN | P | R | F1 | note |
|---|---|---|---|---|---|---|---|---|
| RAISED | 7 | 5 | 1 | 2 | 0.833 | 0.714 | 0.769 | **very low support (n=7) — not a stable estimate** |
| MAINTAINED | 7 | 3 | 3 | 4 | 0.500 | 0.429 | 0.462 | **very low support (n=7) — not a stable estimate** |
| LOWERED | 3 | 3 | 0 | 0 | 1.000 | 1.000 | 1.000 | **very low support (n=3) — not a stable estimate** |
| WITHDRAWN | 0 | 0 | 0 | 0 | 0.000 | 0.000 | 0.000 | **NOT EVALUABLE — zero support in eval** |
| NONE | 553 | 324 | 5 | 229 | 0.985 | 0.586 | 0.735 |  |

Macro over classes **with support in this split** (RAISED, MAINTAINED, LOWERED, NONE): P=0.830 R=0.682 F1=0.741. Zero-support classes are excluded from this average and listed as not evaluable rather than averaged in as structural zeros.
- `WITHDRAWN`: NOT EVALUABLE — guidance_direction=WITHDRAWN has exactly 1 example corpus-wide and it is in the TRAIN split, so eval support is 0. A P/R/F1 row for it would be three zeros masquerading as a measurement (HANDOFF.md §7).

Failure attribution (counted as errors, never dropped): `{'__MISSING_FIELD__': 226}`

Top confusions (gold -> predicted): `NONE->__MISSING_FIELD__` × 226, `MAINTAINED->NONE` × 4, `NONE->MAINTAINED` × 2, `NONE->RAISED` × 1, `RAISED->MAINTAINED` × 1, `RAISED->NONE` × 1

## 4. red_flags — exact-set basis

- **Exact set match on (category, modality): 64.87%** (650/1002 rows)
- Exact set match on categories only (modality ignored): 65.87% (660/1002 rows)
- 0 of these rows were unparseable and are counted as mismatches.

This basis is strict by construction: one added, dropped or re-modalized category
on a multi-flag chunk fails the whole row. It is the same basis as the spot-check's
63.4% teacher-vs-auditor figure, so it is the comparable one — but it is NOT
comparable to the single-value sentiment/guidance rates above.

## 5. red_flags — per-category decomposition

- **Per-category agreement: 92.42%** (456 wrong decisions over 6012 chunk-category decisions = 1002 rows × 6 categories). Teacher's own per-category error on the spot-check sample: 7.5% (180 category corrections / 2,394 chunk-category decisions).

Note this rate is dominated by true negatives (most chunk-category cells are
correctly empty), which is exactly why the P/R/F1 table below is the honest read
of it and the headline percentage is not.

| category | support | TP | FP | FN | P | R | F1 | note |
|---|---|---|---|---|---|---|---|---|
| DEMAND_WEAKNESS | 202 | 122 | 14 | 80 | 0.897 | 0.604 | 0.722 |  |
| SUPPLY_INPUT_CONSTRAINT | 148 | 107 | 14 | 41 | 0.884 | 0.723 | 0.796 |  |
| TRADE_POLICY_EXPOSURE | 105 | 86 | 12 | 19 | 0.878 | 0.819 | 0.847 |  |
| IMPAIRMENT_WRITEDOWN | 154 | 133 | 20 | 21 | 0.869 | 0.864 | 0.866 |  |
| MARGIN_COST_PRESSURE | 242 | 162 | 48 | 80 | 0.771 | 0.669 | 0.717 |  |
| LEGAL_REGULATORY_ACTION | 297 | 233 | 43 | 64 | 0.844 | 0.785 | 0.813 |  |

- Micro (all categories pooled): P=0.848 R=0.734 F1=0.787 (TP=843 FP=151 FN=305)
- Macro over categories with support (DEMAND_WEAKNESS, SUPPLY_INPUT_CONSTRAINT, TRADE_POLICY_EXPOSURE, IMPAIRMENT_WRITEDOWN, MARGIN_COST_PRESSURE, LEGAL_REGULATORY_ACTION): P=0.857 R=0.744 F1=0.793
- Modality agreement, restricted to (row, category) cells where both sides say the category is present: 95.73% (807/843), confusion `{'REALIZED->HYPOTHETICAL': 20, 'HYPOTHETICAL->REALIZED': 16}`

## 6. Field-presence (applicability) agreement

`section_type` is never in the prompt (PROMPT_TEMPLATE.md), so *which* fields to
emit is itself learned from the passage's register. This measures that directly.

| field | n determined | n agree | agreement | breakdown |
|---|---|---|---|---|
| sentiment | 1002 | 971 | 96.91% | `{'gold_no_pred_no': 134, 'gold_yes_pred_yes': 837, 'gold_yes_pred_no': 30, 'gold_no_pred_yes': 1}` |
| guidance_direction | 1002 | 769 | 76.75% | `{'gold_no_pred_no': 425, 'gold_yes_pred_yes': 344, 'gold_yes_pred_no': 226, 'gold_no_pred_yes': 7}` |

## 7. Throughput (doubles as EXPANSION_PLAN F4's labeling-throughput probe)

- Rows generated this process: 1010 in 2718.8s → **1337.4 chunks/hour**
- Per-row latency (s): mean 2.691, p50 2.421, p95 4.896, p99 6.286, max 7.163
- Prompt tokens: mean 1105.6, total 1116622
- Generated tokens: mean 36.3, max 151, total 36675
- Prefill: mean 841.5 tok/s · Decode: mean 28.1 tok/s
- Finish reasons: `{'stop': 1010}` (`length` means the row hit --max-tokens and its JSON is probably truncated)

These figures are EXPANSION_PLAN.md F4's labeling-throughput probe, measured at n=1,010 on this machine with this adapter.

| E2 labeling workload | hours @ measured rate | ≈ 10h overnights |
|---|---|---|
| E1 re-label (6,746 chunks) | 5.0 | 0.5 |
| E2 low estimate (~70k new + 6,746 E1 = 76,746) | 57.4 | 5.7 |
| E2 high estimate (~98k new + 6,746 E1 = 104,746) | 78.3 | 7.8 |

Single-stream, no prefix cache, no batching. EXPANSION_PLAN §2b lists both
as free levers that were not used here.

## 8. Excluded slices, reported separately (never headline)

**8K_BODY, n=8 — NOT EVALUABLE.** n=8 corpus-wide from only 2 tickers (BAC, CVX); all 8 landed in the eval split. No per-class estimate on 8 rows from 2 issuers is stable, so 8K_BODY rows are excluded from every headline table and reported separately below (HANDOFF.md §7).

Shown for completeness only: sentiment exact-match 100.0% (n=8), guidance exact-match 50.0% (n=8), red_flags exact-set 62.5% (n=8), parse failures 0.

Do not average these into anything.

## 9. Per-section-type breakdown (headline rows only)

| section_type | n | parse-fail | sentiment exact | guidance exact | red_flags exact-set | red_flags per-category |
|---|---|---|---|---|---|---|
| EX99_PRESS_RELEASE | 570 | 0.00% | 86.1% (n=570) | 58.8% (n=570) | 67.5% | 92.72% |
| MDA | 297 | 0.00% | 78.5% (n=297) | n/a | 64.6% | 92.42% |
| RISK_FACTORS | 135 | 0.00% | n/a | n/a | 54.1% | 91.11% |

The spot-check found red_flags weakest in RISK_FACTORS (59.2% teacher-vs-auditor);
compare that row specifically rather than the pooled figure.

---

Full machine-readable results: `metrics.json` · raw generations: `predictions.jsonl` · run provenance: `manifest.json` (same directory).

---

# APPENDIX A — guidance_direction under the proposed missing→NONE post-rule

**Added 2026-08-25. Everything above this line is the report as generated on
2026-08-22 and is unmodified — this is an append, not a rewrite.**

## A.0 Why this appendix exists

The gate-G1 ruling (HANDOFF.md §3, 2026-08-21) required the epoch-2 re-eval to
report `guidance_direction` **both raw and under the proposed missing→NONE
post-rule**. Section 3 above reports only the raw figure. This appendix supplies
the missing half, recomputed for real from this run's own stored
`predictions.jsonl` — **zero inference, zero training, zero network, zero
Anthropic API calls, $0**. No number above this line changed.

## A.1 The rule, stated exactly

> **missing→NONE:** on a row where the *teacher's* label contains a
> `guidance_direction` field, if the student's JSON omits that key entirely, read
> the omission as `NONE`. Nothing else changes.

Scope limits, stated so the rule is not read as broader than it is:

- It applies **only** to the 570 guidance-applicable headline rows — the rows the
  teacher itself labelled for guidance. It is not an applicability rule.
- It rewrites **only** the `__MISSING_FIELD__` sentinel. Unparseable output,
  invalid enums, and every wrong-value prediction stay errors. (There were 0
  unparseable and 0 invalid-enum rows in this run, so `__MISSING_FIELD__` was the
  only sentinel present.)
- It touches **no other metric**: `sentiment`, `red_flags` (both bases), parse/
  schema integrity, field-presence, and throughput above are unaffected.
  `distress_tier` remains excluded entirely — never a training target, never a
  headline metric (HANDOFF.md §7).

**Adoption status — do not assume it.** This post-rule was *proposed* at the
epoch-1 read (HANDOFF.md §3, gate-G1 entry, 2026-08-21) and remains **proposed,
not adopted**. Its formal adoption is a decision for the owner at the G1 read; it
is not adopted by the act of being computed here. Both numbers are therefore
printed side by side below, and the raw number is the one that stands if the rule
is declined.

## A.2 Headline result — raw beside post-ruled

n = 570 guidance-applicable headline rows (8K_BODY excluded, as everywhere above).

| basis | exact-match agreement with the teacher | errors |
|---|---|---|
| **raw** (as reported in §3) | **58.8%** (335/570) | 235 |
| **post-ruled** (missing→NONE) | **98.4%** (561/570) | 9 |

Teacher's own second-rater agreement on this field: 95.2% [90.4, 97.6].

**Verification of the 561/570 derivation.** The main session derived 561/570 by
adding §3's 226 `NONE->__MISSING_FIELD__` confusions to its 335 exact matches.
Recomputed here from `predictions.jsonl` row by row using `eval.py`'s own
`score_single_label`, the answer is **561/570 = 98.42%** — the derivation was
**exactly right**, not approximately right. The recomputation also reproduced the
raw side (335/570, and §3's full confusion counter) byte-for-byte before the rule
was applied, which is what makes the post-ruled figure trustworthy.

Two facts that had to be checked and were:

1. The rule rewrote **226** rows, and **all 226** had teacher-label `NONE`
   (0 had a non-NONE teacher label). So the rule converted 226 errors into 226
   agreements and **created no new agreement on a row where the teacher saw real
   guidance**. Had even one omitted row carried a RAISED/LOWERED/MAINTAINED
   teacher label, the rule would be laundering a real miss into a pass; it does
   not here.
2. `n` is unchanged at 570. The rule moves no row in or out of the denominator.

## A.3 Per-class table under the post-rule (raw shown beside it)

Support and the raw columns are identical to §3; only NONE's prediction column
moves, because the rule only ever writes the value `NONE`.

| class | support | raw TP/FP/FN | raw P / R / F1 | post TP/FP/FN | **post P / R / F1** | note |
|---|---|---|---|---|---|---|
| RAISED | 7 | 5 / 1 / 2 | 0.833 / 0.714 / 0.769 | 5 / 1 / 2 | 0.833 / 0.714 / 0.769 | **very low support (n=7) — not a stable estimate** |
| MAINTAINED | 7 | 3 / 3 / 4 | 0.500 / 0.429 / 0.462 | 3 / 3 / 4 | 0.500 / 0.429 / 0.462 | **very low support (n=7) — not a stable estimate** |
| LOWERED | 3 | 3 / 0 / 0 | 1.000 / 1.000 / 1.000 | 3 / 0 / 0 | 1.000 / 1.000 / 1.000 | **very low support (n=3) — not a stable estimate** |
| WITHDRAWN | 0 | — | — | — | — | **NOT EVALUABLE — zero support in eval** (1 example corpus-wide, in TRAIN; HANDOFF.md §7) |
| NONE | 553 | 324 / 5 / 229 | 0.985 / 0.586 / 0.735 | 550 / 5 / 3 | **0.991 / 0.995 / 0.993** | |

Macro over classes with support in this split (RAISED, MAINTAINED, LOWERED,
NONE): raw P=0.830 R=0.682 F1=0.741 → **post-ruled P=0.831 R=0.784 F1=0.806**.
WITHDRAWN is excluded from the average rather than averaged in as a structural
zero, per the standing rule.

**The single most important caveat on the 98.4%: it is carried by the majority
class.** 553 of the 570 rows are teacher-NONE, and the student gets 550 of those
right. On the **17 rows where the teacher recorded actual guidance**
(RAISED 7 / MAINTAINED 7 / LOWERED 3), the student is right on **11/17 = 64.7%**.
Seventeen rows cannot support a stable estimate, which is exactly why the
per-class rows above carry low-support warnings — but a reader who takes 98.4% as
"the student reads guidance well" is reading the NONE rate, not the guidance rate.

## A.4 Remaining error decomposition after the post-rule

All 9 surviving errors, by kind:

| kind | count | confusions |
|---|---|---|
| **missed real guidance** (teacher non-NONE → student NONE) | 5 | `MAINTAINED->NONE` × 4, `RAISED->NONE` × 1 |
| **spurious guidance** (teacher NONE → student non-NONE) | 3 | `NONE->MAINTAINED` × 2, `NONE->RAISED` × 1 |
| **wrong direction** (both non-NONE, disagree) | 1 | `RAISED->MAINTAINED` × 1 |

- 6 of the 9 land on the 17 non-NONE rows; 3 land on the 553 NONE rows.
- Zero of the 9 are parse failures, schema violations, or invalid enums.
- No error involves LOWERED (3/3 correct) or WITHDRAWN (no eval support).
- Chunk ids, for anyone who wants to read the passages:
  `CHK-8f26c91deeaff05f`, `CHK-56b7947ccd9dc822`, `CHK-ef45841b13a70a29`,
  `CHK-6c60ac55215be937` (MAINTAINED→NONE); `CHK-995038f4b6ac9fc2`
  (RAISED→NONE); `CHK-513efb04fa834419`, `CHK-dfbdc9005df6cd50`
  (NONE→MAINTAINED); `CHK-09802f1bf7c93da7` (NONE→RAISED);
  `CHK-7bd9948d100abc87` (RAISED→MAINTAINED).

**Related, but outside the rule's scope and outside this denominator:** on the 432
headline rows where the teacher emitted *no* guidance field at all, the student
emitted one on **7** rows — and all 7 of those predictions were `NONE`. So the
student's field-presence disagreement with the teacher, in both directions
(226 omissions + 7 over-emissions = 233 rows), is entirely "omitted vs. explicit
NONE" and never a substantive guidance claim. That is the empirical case *for*
the post-rule; it is offered as evidence for the owner's decision, not as the
decision.

## A.5 Epoch-1 vs epoch-2 under the same rule

Recomputed identically from `finetune/runs/2026-08-21-eval-epoch1/
predictions.jsonl` (same eval rows, sha256 `deb63b76…`; same instruction, sha256
`ebc45a85…` — verified, not assumed).

| | epoch-1 | epoch-2 |
|---|---|---|
| guidance raw | 47.7% (272/570) | 58.8% (335/570) |
| omitted guidance field | 289 rows | 226 rows |
| **guidance post-ruled** | **98.4% (561/570)** | **98.4% (561/570)** |
| surviving errors | 9 | 9 |

This also confirms the "~98%" quoted for epoch-1 in the G1 decision-log entry: it
is exactly 561/570.

**Read this row carefully — it is the appendix's main finding.** Epoch 2's raw
guidance gain (+11.1 points) is entirely the student learning to *emit* the
`guidance_direction` key on rows where it means NONE. Under the post-rule the two
epochs are **tied to the row**: 8 of the 9 error chunks are the same chunks in
both runs — 7 of those with the identical wrong prediction, plus
`CHK-995038f4b6ac9fc2` which changed flavour (RAISED→MAINTAINED at epoch 1,
RAISED→NONE at epoch 2). Epoch 2 fixed exactly one chunk
(`CHK-923aa492ae6784dc`) and newly broke exactly one (`CHK-513efb04fa834419`).
A second epoch bought no measurable guidance-*semantics* improvement.

## A.6 Not-evaluable slice, reported separately (never headline)

**8K_BODY, n=8 — NOT EVALUABLE** (n=8 corpus-wide from 2 tickers; HANDOFF.md §7).
Shown for completeness only, never averaged into anything: guidance raw 50.0%
(4/8), post-ruled 87.5% (7/8), 3 omitted fields.

Per-section-type: all 570 guidance-applicable headline rows are
`EX99_PRESS_RELEASE` (MDA and RISK_FACTORS rows are never asked for guidance), so
§9's guidance column under the post-rule is the headline figure exactly — 98.4%
for EX99_PRESS_RELEASE, `n/a` for MDA and RISK_FACTORS, unchanged.

## A.7 If the rule is adopted, it is not only a scoring convention

Adopting missing→NONE at the eval bench without also applying it in the F4
labeling writer would leave the reported number describing something the produced
labels do not do. If the owner adopts it, the same normalisation must be written
into the E2 labeling path (an omitted `guidance_direction` on a guidance-applicable
passage is persisted as `NONE`), and F4's per-row checkpointed output should carry
a flag distinguishing a normalised NONE from an explicitly-emitted one so the
choice stays auditable and reversible. If the owner declines the rule, §3's raw
58.8% stands as the guidance headline.

## A.8 Provenance of this recomputation (verify-artifact rule)

| item | value |
|---|---|
| computed | 2026-08-25, from stored artifacts only |
| inputs | `finetune/runs/2026-08-22-eval-epoch2/predictions.jsonl` (sha256 `b6d55552035784ed291929dc9e7f8da9556a83850a594ee072911db57972b2a6`) |
| gold labels | `finetune/mlx_data/valid.jsonl` sha256 `deb63b76992404ecaf4fdc4c3a3acbea9b0c3bb7f655064aec7191ebc9ab0736` — matches this report's provenance table above |
| instruction sha256 | `ebc45a856bff58a562535867e5a1f4173519fe77c58a47b16bfa28e6eea8efe2` — matches above |
| section-type sidecar | `finetune/eval_section_types.json` (8K_BODY exclusion only) |
| scoring code | `finetune/eval.py` — `load_eval_rows()`, `parse_model_output()`, `predicted_single_label()`, `score_single_label()`, unmodified |
| raw side reproduced | yes — 335/570 and §3's full confusion counter re-derived before the rule was applied |
| model invoked | none. No generation, no adapter load, no network. |
| cost | $0.00 · Anthropic API calls: 0 |

Machine-readable form: the `post_rule_missing_guidance_as_none` block appended to
`metrics.json` in this directory (existing keys untouched).

**Standing frame, restated because it governs every number in this appendix:**
these are AGREEMENT-WITH-THE-TEACHER rates, not accuracy. 98.4% post-ruled
agreement means the student reproduces Claude's guidance labels, including
whatever those labels get wrong.

