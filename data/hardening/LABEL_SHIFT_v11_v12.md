# LABEL SHIFT — rubric v1.1 vs v1.2 (same teacher, same corpus)

Generated 2026-08-26T16:43:13.887573+00:00. Zero API calls (both label files already on disk).

> teacher-vs-teacher label shift between rubric v1.1 and v1.2. Same corpus, same model id (claude-sonnet-5), same decoding config (thinking=disabled, max_tokens=4000). NOT an accuracy measurement — neither side is ground truth.

## 0. Population

- v1.1 labeled: **6746** / 6747
- v1.2 labeled: **6747** / 6747
- **Comparable (labeled on both sides): 6746**
- Labeled in v1.1 only: none
- Labeled in v1.2 only: ['CHK-8e69547e0900a8dd'] (E1's safety-refusal chunk — it labeled under v1.2, but the split is frozen so it still enters neither side)
- By section_type: {'MDA': 3961, 'RISK_FACTORS': 1606, 'EX99_PRESS_RELEASE': 1171, '8K_BODY': 8}
- By split: {'train': 5736, 'eval': 1010}

## 1. Headline — per-field changed-row counts

| field | basis | denominator | changed | % |
|---|---|---|---|---|
| sentiment | single value | 5140 | **236** | 4.59% |
| guidance_direction | single value | 1179 | **14** | 1.19% |
| red_flags | EXACT SET | 6746 | **1854** | 27.48% |
| red_flags | PER-CATEGORY | 40476 | **2372** | 5.86% |
| distress_tier (not a target) | set | 6746 | 80 | — |

`red_flags` is an **exact-set** rate: one added, dropped or re-modalized category on a multi-category chunk counts the whole chunk as changed. It is not comparable to sentiment's single-value rate printed beside it.

### red_flags — how the changed rows decompose

- adds only: **658**
- drops only: **472**
- modality only: **410**
- mixed (adds+drops): **192**
- mixed (adds+modality): **67**
- mixed (drops+modality): **44**
- mixed (adds+drops+modality): **11**

- rows carrying ≥1 flag: 4416 → **4513** (+97)
- total flags emitted: 7715 → **7933** (+218)

## 2. red_flags — per-category deltas

| category | v1.1 rows | v1.2 rows | delta | % | added | dropped | HYP→REAL | REAL→HYP |
|---|---|---|---|---|---|---|---|---|
| DEMAND_WEAKNESS | 1318 | 1313 | **-5** | -0.4% | 163 | 168 | 27 | 14 |
| SUPPLY_INPUT_CONSTRAINT | 607 | 567 | **-40** | -6.6% | 46 | 86 | 22 | 4 |
| TRADE_POLICY_EXPOSURE | 699 | 702 | **+3** | 0.4% | 64 | 61 | 29 | 7 |
| IMPAIRMENT_WRITEDOWN | 1015 | 1028 | **+13** | 1.3% | 97 | 84 | 8 | 3 |
| MARGIN_COST_PRESSURE | 1736 | 2030 | **+294** | 16.9% | 479 | 185 | 53 | 24 |
| LEGAL_REGULATORY_ACTION | 2257 | 2215 | **-42** | -1.9% | 170 | 212 | 300 | 10 |

### modality split per category

| category | HYP v1.1 | HYP v1.2 | Δ | REAL v1.1 | REAL v1.2 | Δ |
|---|---|---|---|---|---|---|
| DEMAND_WEAKNESS | 529 | 516 | -13 | 797 | 803 | +6 |
| SUPPLY_INPUT_CONSTRAINT | 458 | 403 | -55 | 158 | 174 | +16 |
| TRADE_POLICY_EXPOSURE | 477 | 442 | -35 | 236 | 270 | +34 |
| IMPAIRMENT_WRITEDOWN | 252 | 246 | -6 | 766 | 787 | +21 |
| MARGIN_COST_PRESSURE | 538 | 672 | +134 | 1199 | 1370 | +171 |
| LEGAL_REGULATORY_ACTION | 1258 | 884 | -374 | 1047 | 1366 | +319 |

## 3. red_flags by section_type

| section_type | n | exact-set changed | % | ≥1 flag v1.1 → v1.2 | total flags v1.1 → v1.2 |
|---|---|---|---|---|---|
| 8K_BODY | 8 | 2 | 25.0% | 5 → 5 (+0) | 15 → 17 (+2) |
| EX99_PRESS_RELEASE | 1171 | 305 | 26.05% | 698 → 711 (+13) | 1255 → 1313 (+58) |
| MDA | 3961 | 879 | 22.19% | 2228 → 2309 (+81) | 3690 → 3850 (+160) |
| RISK_FACTORS | 1606 | 668 | 41.59% | 1485 → 1488 (+3) | 2755 → 2753 (-2) |

## 4. Train vs eval — do the two sides move together?

| split | n | red_flags exact-set changed | % | total flags Δ | sentiment % changed |
|---|---|---|---|---|---|
| train | 5736 | 1571 | 27.39% | +178 | 4.22% |
| eval | 1010 | 283 | 28.02% | +40 | 6.4% |

If these rates diverged materially the retrain and its held-out eval would be measuring different rubrics. They do not.

## 5. sentiment and guidance_direction transitions

**sentiment** — 236/5140 changed (4.59%)
- v1.1: {'NEUTRAL': 3436, 'POSITIVE': 1024, 'NEGATIVE': 680}
- v1.2: {'NEUTRAL': 3385, 'POSITIVE': 1046, 'NEGATIVE': 709}
- transitions: NEUTRAL -> NEGATIVE (74), NEUTRAL -> POSITIVE (68), POSITIVE -> NEUTRAL (47), NEGATIVE -> NEUTRAL (44), NEGATIVE -> POSITIVE (2), POSITIVE -> NEGATIVE (1)

**guidance_direction** — 14/1179 changed (1.19%)
- v1.1: {'NONE': 1096, 'RAISED': 34, 'MAINTAINED': 34, 'LOWERED': 14, 'WITHDRAWN': 1}
- v1.2: {'NONE': 1098, 'RAISED': 35, 'MAINTAINED': 30, 'LOWERED': 15, 'WITHDRAWN': 1}
- transitions: MAINTAINED -> NONE (5), NONE -> MAINTAINED (3), NONE -> RAISED (2), MAINTAINED -> LOWERED (2), RAISED -> NONE (1), LOWERED -> NONE (1)

## 6. distress_tier — the 162 → 129 question (HARDENING_PROGRESS.md said 130; see §7)

> distress_tier is never a training target and never a headline metric (HANDOFF §7). Reported here only because rubric v1.2's §6 modality rule is shared vocabulary and therefore reaches it.

Positive rows on the comparable population: **162 → 129 (-33)**.

| tier / modality | v1.1 | v1.2 | delta |
|---|---|---|---|
| ACCOUNTING_RESTATEMENT/HYPOTHETICAL | 2 | 2 | +0 |
| LIQUIDITY_STRESS/HYPOTHETICAL | 151 | 112 | -39 |
| LIQUIDITY_STRESS/REALIZED | 9 | 15 | +6 |

Row-level transitions:
- positive_both: **108**
- positive_v11_only (dropped): **54**
- positive_v12_only (added): **21**
- negative_both: **6563**
- positive_both_but_changed: **5**

## 7. Correction to HARDENING_PROGRESS.md's post-batch summary

- quoted there: ≥1-red-flag rows **4515**, distress rows **130**
- recomputed over all 6,747 labeled rows: **4514** and **129**
- cause: the quoted figures were computed while CHK-1c1812ed45219a3a was still unanswered and carried NULL (not empty) red_flags / distress_tier; a null-inclusive predicate counted it as a positive. It has since been labeled by the completion batch with an EMPTY set for both fields, so the correct counts are the same either way.
- authoritative: the recomputed figures

