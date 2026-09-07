# Red-flag label limitation — Phase B disposition (2026-08-18)

This is the §6-Step-2 / ROADMAP-Phase-B record: the spot-check's verdict on
every headline label category, and the full documentation of the one
category that failed the quality bar. The eventual model card (Phase E)
must draw from this file. Source data: `spotcheck/agreement_report.txt`
(rates + provenance appendix), `spotcheck/combined_judgments.csv` (all
1,222 judgments), `spotcheck/adjudicator_verdicts.json` (briefs), HANDOFF
§3 decision log (the owner ratifications this rests on).

## Disposition of every category (Phase B definition-of-done)

| Category | Agreement (95% Wilson CI) | vs. 0.70 bar | Disposition |
|---|---|---|---|
| sentiment | 94.6% [91.3, 96.7] | passes | **Cleared — no action.** |
| guidance_direction | 95.2% [90.4, 97.6] | passes | **Cleared — no action.** (WITHDRAWN n=1 remains non-evaluable per HANDOFF §7.) |
| distress_tier (separate per rubric §5) | 94.2% [91.5, 96.1] | passes | **Cleared as a category** — but see the REALIZED-class note below. |
| **red_flags** (**exact-set match** — see note) | **63.4% [58.6, 68.0]** | **fails — upper bound below the bar** | **Failed. Fix proposed below; documented limitation; NO re-label (API-spend freeze, §5).** |

**`red_flags` is not measured the same way as the three rows above it.**
It is an **exact-set-match** rate: one added, dropped, or re-modalized
category on a multi-category chunk scores the whole chunk as a
disagreement, whereas `sentiment` and `guidance_direction` are single-value
comparisons. On a per-category basis, the same 146 disagreements decompose
into **180 category-level corrections over 399 × 6 = 2,394 chunk-category
decisions — 7.5% per-category error (92.5% per-category agreement, 95%
Wilson CI [91.4, 93.5])**. Both numbers are true and they answer different
questions: quote the exact-set rate for "is a chunk's full flag set right",
the per-category rate for "is any single category call right".

Measurement provenance (per the 2026-08-18 epistemic clause): these rates
are model-consensus agreement — blind second-rater (opus) over all 400
sample chunks, disputes resolved by a third-rater adjudicator, with the
owner personally ruling on 104 judgments (85 by block ratification of
medium+-confidence adjudications, 19 explicitly: the 11 high-stakes
distress chunks and an 8-case final round). They are NOT human validation
of ground truth.

## What is wrong with the red-flag labels, concretely

Of the 399 evaluable chunks, **146 stored red-flag sets (36.6%) were ruled
incorrect** under adjudication. The corrections decompose into three error
modes (counts are category-level corrections across those 146 chunks):

**1. Spurious flags — stored label flags something the text does not
assert (61 corrections):** LEGAL_REGULATORY_ACTION 21,
MARGIN_COST_PRESSURE 20, DEMAND_WEAKNESS 7, IMPAIRMENT_WRITEDOWN 7,
TRADE_POLICY_EXPOSURE 5, SUPPLY_INPUT_CONSTRAINT 1. Typical failure:
direction-neutral language ("supply and demand considerations") read as
DEMAND_WEAKNESS; descriptions of the existing regulatory regime read as a
legal-action flag.

**2. Missed flags — the text asserts a category the stored label omits
(76 corrections):** MARGIN_COST_PRESSURE 23, SUPPLY_INPUT_CONSTRAINT 15,
DEMAND_WEAKNESS 14, LEGAL_REGULATORY_ACTION 12, IMPAIRMENT_WRITEDOWN 6,
TRADE_POLICY_EXPOSURE 6. Typical failure: generic cost-inflation language
("unexpected changes in costs, inflationary pressures") not flagged as
MARGIN_COST_PRESSURE despite the rubric §4 disambiguation note requiring
it.

**3. Wrong modality, right category (43 corrections):**
LEGAL_REGULATORY_ACTION 26, MARGIN_COST_PRESSURE 13, others 4. Dominant
failure, owner-ratified as principle P1: when a passage names something
that has already happened or currently exists ("we are subject to pending
investigations ... in various stages", "audits ... have in the past
resulted in fines"), the labeler tagged it HYPOTHETICAL because the
surrounding safe-harbor framing is could/may — but rubric §6's
realized-controls rule makes it REALIZED. The stored labels systematically
under-report REALIZED legal/regulatory exposure.

Where it fails hardest — **on a red-flags-only basis** (recomputed
2026-08-18 from `spotcheck/combined_judgments.csv`; do **not** use
`agreement_report.txt` Section 3's per-tier figures for a red-flag claim,
because those pool sentiment + guidance + red_flags together and dilute the
failure by roughly 18 points per tier):

| Tier | red_flags only | 95% Wilson CI | all headline fields pooled |
|---|---|---|---|
| A — all distress positives | 96/162 = **59.3%** | [51.6, 66.5] | 76.9% |
| B — thin-category oversample | 98/141 = **69.5%** | [61.5, 76.5] | 83.4% |
| C — base-rate fill | 27/36 = **75.0%** | [58.9, 86.2] | 84.3% |
| D — config-disagreement set | 32/60 = **53.3%** | [40.9, 65.4] | 71.2% |

**Tier D is the worst tier (53.3%), and Tier A (59.3%) is worse than the
71.2% the pooled view reports for the "worst" tier** — the ordering
inverts between the two bases. By section, RISK_FACTORS is weakest at
**59.2% (71/120)**; that figure is red-flags-only by construction, since
RISK_FACTORS chunks are only ever asked `red_flags`. All of this is
consistent with the previously documented finding that
red-flag labels changed on 22.2% of chunks between labeling configurations
(DISCOVERY §6 risk register, 2026-08-11). The two measurements agree:
red-flag labeling sits closest to the rubric's ambiguity boundaries, so it
is the least stable category under any perturbation — of config or of
rater.

## The three owner-ratified ambiguity principles (2026-08-18)

These rulings, made during adjudication, ARE the diagnosis. They are the
same P1/P2/P3 defined in `spotcheck/owner_shortlist.md` Part A. Any future
rubric revision or re-label must encode them:

- **P1 — realized-controls-modality:** a named, existing event inside
  hypothetical boilerplate carries REALIZED modality; only its outcomes
  are hypothetical.
- **P2 — liquidity-stress threshold:** affirmed adequacy defeats the flag;
  a working-capital deficit alone is not distress. (P2 governs
  `distress_tier` rather than `red_flags` — its consequences are in the
  distress-tier addendum below.)
- **P3 — boilerplate mining depth:** a clause inside an enumerated
  safe-harbor factor list earns a flag only when it meaningfully asserts
  the risk; single-word brushes against a category do not qualify.
  - *Corollary of P3 — the MARGIN_COST_PRESSURE boundary* (from P3's
    members and the add/drop tallies above): the §4 disambiguation note
    (causeless cost inflation → MARGIN_COST_PRESSURE alone) is real and
    binding — the bootstrap pass applied it inconsistently in both
    directions. This is not a fourth principle.

## Proposed rubric revision — **RATIFIED AND APPLIED 2026-08-26**

> **AMENDMENT 2026-08-26.** The owner ratified this revision as rubric
> **v1.2** and lifted the §5 spend freeze for exactly one purpose: a
> single Batch API re-label of all 6,747 E1 chunks under it (HANDOFF §3,
> 2026-08-26, "F2.5 closure rulings", ruling 1). All three items below are
> now applied to `labeling_rubric.md` (§4 twice, §6 once) with a matching
> hand-synced `SYSTEM_PROMPT` edit per the 2026-08-10 sync rule. The
> "no re-label occurs regardless" paragraph at the end of this section is
> **superseded** — a re-label is exactly what was authorized. E1's
> `data/labels.parquet` still stays FROZEN: the v1.2 labels land in a new
> artifact, `data/labels_v12.parquet`. **P2 was deliberately not encoded**
> — it governs `distress_tier`, this section never proposed a §5 edit for
> it, and the ratification names this section; it remains documented in
> the distress-tier addendum below. Prep record:
> `data/hardening/status/G1_repair_prep.md`.

### Original text (2026-08-18, as proposed)

Per the standing sync rule (HANDOFF §3, 2026-08-10): if adopted,
`labeling_rubric.md` §4/§6 get the following clarifications AND
`SYSTEM_PROMPT` in `build_batch_requests.py` gets a matching hand-synced
edit. Proposed text, verbatim-adaptable:

1. §6 addition: "A statement that an event exists or has occurred (pending
   litigation, completed audits with consequences, effective regulation
   already imposing obligations) is REALIZED even inside a forward-looking
   or safe-harbor sentence; only projected consequences of it are
   HYPOTHETICAL."
2. §4 addition: "In enumerated risk-factor lists, flag a category only if
   the clause asserts the risk specifically enough to stand alone as a
   sentence about this company; single-word category mentions inside
   boilerplate enumerations do not qualify."
3. §4 disambiguation-note emphasis: "Cost-inflation language with no named
   cause is always MARGIN_COST_PRESSURE, including inside enumerations
   that qualify under (2)."

**No re-label occurs regardless of ratification** — the API-spend freeze
($33.51 final) is absolute, and `labels.parquet` stays frozen per the
owner's 2026-08-18 confirmation. The revision exists so that any future
labeling (e.g., a local fine-tuned model's training targets, or a later
funded pass) does not re-inherit these ambiguities.

## Distress-tier addendum (category passed; one class emptied)

distress_tier cleared the bar (94.2%), but adjudication + the owner's
explicit Part-B rulings determined that **all 9 REALIZED LIQUIDITY_STRESS
labels in the corpus are incorrect** (7 not distress at all, 2 lacking the
rubric's explicit-insufficiency requirement — owner-ratified principle P2:
affirmed adequacy defeats the flag; a working-capital deficit alone is not
distress). Combined with GOING_CONCERN n=0 by universe construction:
**every REALIZED distress class is now empty or near-empty**
(ACCOUNTING_RESTATEMENT survives at n=2, both HYPOTHETICAL-framed
risk-factor text). Distress-tier data remains excluded from fine-tuning
targets and headline metrics per HANDOFF §7 — this addendum just makes the
emptiness explicit so no downstream doc implies REALIZED-distress coverage
exists.

## Binding implications for Week 5 / Phase C (`features.py`)

1. Every red-flag-derived feature inherits a measured error rate — but
   **quote the right one, with its basis attached.** The **36.6%
   exact-set-level error rate** (63.4% agreement, 146/399) is
   **sample-pooled and deliberately NOT corpus-representative**: Tier A is
   an exhaustive distress oversample, Tier B a thin-category oversample,
   and Tier D a hard-case set drawn from the config disagreements.
   `agreement_report.txt`'s own TIER-B CAVEAT says so in as many words.
   The base-rate-representative estimate is **Tier C: 75.0% agreement /
   25.0% exact-set error, n=36, 95% CI [58.9, 86.2]**. On a per-category
   basis the error is **7.5% (180 corrections / 2,394 chunk-category
   decisions)**. Report all three with their bases, side by side, next to
   any red-flag feature importance or ablation claim — charter rule: every
   number with how it was measured, next to it, every time. The "fails the
   0.70 bar" verdict survives on every basis except the per-category one
   (Tier C's CI lower bound is 58.9%), but carrying 36.6% forward as *the*
   corpus error rate overstates it by roughly 11 points.
2. **Modality splits are the least reliable dimension** (43 modality
   corrections, 26 of them LEGAL_REGULATORY_ACTION). Prefer
   category-presence features or coarse aggregates over
   REALIZED/HYPOTHETICAL splits for legal/regulatory; where modality is
   used, note that stored REALIZED counts are biased low (P1).
3. **Do not treat raw flag counts as comparable across section types**
   (REDTEAM finding #4's confound stands, and RISK_FACTORS is also where
   agreement is worst) — normalize by section composition as already
   planned, using recomputed post-relabel counts. Those counts are
   published in `data/full_run_report.md`'s FINAL section, in the dated
   **2026-08-18 CURRENT PER-CATEGORY COUNTS** block (and the per-section
   modality counts are in HANDOFF §6 Step 3). Do not use §3's pre-relabel
   table.
4. Distress-REALIZED features are **known-empty** — do not engineer them.
