# G2 — E2 STUDENT-LABEL SPOT-CHECK — pre-registered design

**Status: PRE-REGISTERED 2026-09-06; PARAMETERS OWNER-RATIFIED 2026-09-07 (§14); no verdict exists**

The design is closed to edits as of this revision. **No chunk has been rated
and no G2 verdict of any kind exists.** What the owner owed the design was
§4 (total n) and §6 (the bars) plus the five other decisions in the §13 menu;
those were *parameters left deliberately open*, not open design questions.
**They were ruled on 2026-09-07 and are pinned in §14** — Option C with a
guidance-direction quota, b = 0.85 on both gate-bearing fields, a 120-row
two-rater ceiling. Once ratified they are frozen into
`build_draw_g2.py` / `analyze_g2.py` (§10) as module constants, and any later
change to anything in this file is a **new pre-registration with a named
reason**, not an edit.

**Revision note (2026-09-06).** This version incorporates an adversarial
red-team pass and the independent F4 artifact verification. Substantive
changes: the λ / reliability-denominator claim is withdrawn (§6.5, §8, §12.3);
a train-overlap census and the S-OVERLAP secondary discharge
`EXPANSION_PLAN.md` §3 item 2 (§2.5, §7, §12.9); the two-rater ceiling is
priced and put on the owner's menu (§5.4, §6.4, §13-v); `draw_g2.csv` is
stripped to three columns + an arm sidecar outside the tree (§5.1, §14.9); the WITHDRAWN non-evaluability is corrected
from a mis-cited standing rule to a power statement (§3.2, §12.5); `red_flags`
becomes a purchasable arm (Option B-lite, §4.2); and §10 is rewritten to be
implementable independently by two engineers.

**Amendment note (2026-09-07).** The owner ruled all seven §13 menu items plus
the two flags and the two build items. They are recorded verbatim, with every
parameter the tooling needs pinned and re-derived from the frame, in **§14**;
§§2, 3.1–3.3, 4.2, 5.4, 6, 7, 9, 10.1, 10.2, 12.6 and 13 carry dated
cross-references to it. The amendment predates any rating: no chunk has been
rated and no G2 number exists. It changes **n, the G-A allocation, the bars and
`CEILING_BATCHES`**, and it adds **one** estimator (the §14.4 quota
re-weighting, required because G-A stopped being a proportional arm). No other
estimator, no arm definition, no assertion and no protocol rule is touched.

**Authority.** `EXPANSION_PLAN.md` §3 item 7 ("a new-labeler quality
measurement replaces the old caveats … **[OWNER-GATE G2 sets the bar]**")
and §4 gate G2 ("E2 spot-check of the Qwen labels — new stratified sample,
auditor protocol — owner reviews the measured agreement rates and rules that
labeling quality is sufficient to proceed to features"). Structure and rigor
mirror `data/hardening/spotcheck_v12/SPOTCHECK_v12_design.md`.

**Provenance rule (HANDOFF §3, §7).** Everything this pass produces is
*model-consensus agreement, with owner rulings superseding on the escalated
subset*. It is **not** human validation of ground truth. The rater and the
adjudicator are Claude-family instances; the labeler under audit is a
Qwen2.5-7B QLoRA student distilled from a Claude teacher. Rater and labeler
are therefore **different** model families — unlike the v1.2 pass, shared-
family bias is *not* the dominant worry here. The dominant worry is the
opposite one: the rater's family is the teacher's family, so the measurement
partly scores *"does the student reproduce Claude"* rather than *"is the
student right"*. Restated in §12.

**Cost.** 0 API calls, 0 GPU seconds, 0 network. Agent lane only.

---

## 1. The estimands, and which ones the gate reads

### 1.1 Three fields, two tiers

| field | tier | why |
|---|---|---|
| `sentiment` | **GATE-BEARING** | survives into `sentiment_mean_score`, `sentiment_negative_share` — the only text features not demoted |
| `guidance_direction` | **GATE-BEARING** | survives into `guidance_signed_mean`, `guidance_any_present` |
| `red_flags` | **DISCLOSURE-ONLY** | demoted to exploratory 2026-08-27 (owner ruling). Measured here **solely** to regenerate the caveat constants of §8. **No kill rule, no gate branch, and no owner-adjudication load attaches to it.** Purchasable — Option B-lite (§4.2) drops it entirely |
| `distress_tier` | **NOT MEASURED** | excluded from every headline metric by standing hard rule (HANDOFF §7); the student was never trained on it |

**No G2 red-flag result can re-promote the family.** The 2026-08-27 demotion
is an owner ruling; only the owner can revisit it. A *favourable* S-RF1 — and
one is plausible, the teacher's own exact-set error was 42.00% — is
**disclosure, not evidence for re-promotion**. The re-promotion path that must
stay closed is not a gate branch but a caveat rewrite: `RED_FLAG_CAVEAT` is
the highest-traffic string in the repo (§8), and a rewrite that reads
"measured student error is X, better than the teacher's" would function as a
silent promotion. `analyze_g2.py` therefore writes `red_flags_status` into
`results_g2.json` and the rewritten caveat must contain that sentence (§10.2).

**Primary estimand, per gate-bearing field f:** the probability that a chunk
drawn uniformly from the frame (§2), *on which the rubric's applicability
matrix asks for f*, carries a stored student value of f that an adjudicated
independent blind re-rating rules **incorrect** under **rubric v1.2 as
interpreted by the owner's 2026-08-27 policy rulings** (which bear on rubric
§4/§6 only; §2 sentiment and §3 guidance are unaffected — §5.2). Reported
as its complement, an agreement rate, with a 95% Wilson interval — the
convention `spotcheck/compute_agreement.py:65` established and HANDOFF §2a
requires.

**Secondary estimand for `red_flags`:** exact-set (category, modality) error
and per-category-decision error, on the same draw, same construction as
v1.2's P1/S2 so the two are comparable in *construction* (not in target —
§7).

### 1.2 Applicability is applied at analysis time, mechanically

Rubric §8.2 forbids `section_type` from reaching the labeler as prompt text;
the student learned *which fields to emit* from the passage's register alone
(epoch-2 eval §6 measured that directly: sentiment field-presence 97.11%,
guidance 73.35%). The rater must operate on the same information, so:

- **The rater emits all three fields on every chunk**, unconditionally:
  `sentiment ∈ {POSITIVE, NEUTRAL, NEGATIVE}`, `guidance_direction ∈
  {RAISED, MAINTAINED, LOWERED, WITHDRAWN, NONE}`, `red_flags` a possibly
  empty list. There is no "N/A" option, because offering one would leak the
  applicability matrix back into the rater's decision.
- **`analyze_g2.py` masks by the writer-side matrix**, read from
  `section_type` in the frame, exactly as `build_batch_requests.py` shaped
  the teacher's schema (rubric §1, §7):

  | field | evaluable on |
  |---|---|
  | `sentiment` | MDA, EX99_PRESS_RELEASE (8K_BODY excluded, §2.3) |
  | `guidance_direction` | EX99_PRESS_RELEASE (8K_BODY excluded) |
  | `red_flags` | MDA, RISK_FACTORS, EX99_PRESS_RELEASE |

Consequence, stated rather than discovered: a rater sentiment on a
RISK_FACTORS chunk and a rater guidance on an MDA chunk are **collected and
discarded**. That is not waste — it is what keeps the rater blind.

### 1.3 The three omission conventions, pinned now

The student's failure modes are field *omission*, not just wrong values.
Pre-registered scoring, before data:

| situation | corpus count | primary scoring |
|---|---|---|
| stored `sentiment` null on an applicable row | 2,630 MDA (1.53%) + 205 EX99 (0.22%) | **error** — matches the epoch-2 eval's `__MISSING_FIELD__` convention (`finetune/eval.py`), and matches the downstream reality that the chunk contributes nothing to the sentiment features |
| stored `guidance_direction` = NONE via `guidance_imputed_none = true` | 48,293 EX99 (51.08% of EX99) | scored **as NONE** — the writer rule is adopted (F4_prep §3.2), so "NONE" *is* the stored label. Arm G-N (§3.3) exists to test exactly this |
| stored `guidance_direction` null from a bad enum | 17 EX99 (`UPDATED` ×15, `REVIEWED` ×2) | **error** |

**Implementer's trap, from the F4 verification:** `schema_valid == false` does
**not** imply a null guidance value. Of the 23 schema-invalid rows, 17 are
`bad_enum:guidance_direction` (guidance null, `guidance_imputed_none = false`),
but `E2CHK-c9502bff4d7a248b` (seg-004, EX99, `bad_enum:red_flag_category`)
omitted the guidance key entirely, so the owner-ruled missing→NONE writer rule
fired: stored `guidance_direction = "NONE"`, `guidance_imputed_none = true`.
That row scores under the **imputed-NONE** convention, not the bad-enum one.
Branch on the stored columns, never on `schema_valid`.

A pre-registered zero-owner-load secondary (S-OMIT) restates every rate with
omissions **excluded** from numerator and denominator, plus the omission rate
itself as a first-class number. Missing-as-error and missing-as-excluded
answer different questions (value correctness vs. coverage); both ship,
neither is chosen after seeing which is kinder.

### 1.4 What is **not** the estimand

Not teacher error, not E1, not feature-level retention, not backtest
performance, and **not** whether the student agrees with the Claude teacher.
Agreement-with-the-teacher was already measured (epoch-2 eval, §7 comparison
rows) and is a different target.

---

## 2. The frame

> **Owner ruling 2026-09-07 (§14.1 item 2(a)), recorded here because it is the
> precondition for measuring this frame at all.** The council's §7-item-3
> stop-trigger (`data/hardening/status/G1_council_advisory.md`) was ruled
> *"noted, does not fire as agreement drift; G2 is the mandated measurement;
> drift disclosed."* The drift is real and stays disclosed — same student, same
> adapter, E1 → E2: guidance-key omission 33.08% → 51.18%, sentiment emitted on
> RISK_FACTORS 1.00% → 8.41%, per-section flag rates 9–14 points lower (record:
> `data/f4/status/F4_campaign.md` §2; restated in §3.3 and §3.4). The ruling is
> that this is distribution drift on a changed corpus rather than measured
> agreement drift, and that G2 is the measurement that settles it. **No G2
> estimate is licensed by this ruling; the drift travels into §12 as a
> limitation either way.**

### 2.1 `data/f4/labels_e2_v1.parquet`, minus 8K_BODY

317,081 rows, `chunk_id` unique, `chunk_id` set identical to
`data/f4/chunks_v1.parquet`, `parse_ok` true on all rows, 0 `finish=length`.
Provenance is joined on `chunk_id` from `chunks_v1.parquet`:
`section_type`, `home_sector`, `home_filing_date`, `home_cik`, `home_flags`,
`home_extraction_confidence`.

**23 `schema_valid = false` rows stay in frame.** They are real stored
labels with real downstream effect (F4_campaign §3); excluding them would
measure a corpus the pipeline does not consume.

| stratum | rows | share of frame |
|---|---|---|
| MDA | 172,098 | 54.41% |
| EX99_PRESS_RELEASE | 94,545 | 29.89% |
| RISK_FACTORS | 49,648 | 15.70% |
| *(8K_BODY — excluded)* | *790* | *0.249% of corpus* |
| **frame total** | **316,291** | 100% |

Sectors (all core stratum): financials 31.10%, tech 19.96%, consumer 17.22%,
healthcare 16.55%, energy 15.17%. Era: 2019+ 66.06%, pre-2019 33.94%.
**176 distinct CIKs, 14,315 distinct home accessions *in the frame*** (14,510
corpus-wide, i.e. including 8K_BODY; the frame figure is the one this design
samples from).

### 2.2 Non-independence audit — done, not assumed away

HANDOFF's near-duplicate hard rule bites at chunk construction, and it was
enforced there. Re-verified on `chunks_v1.parquet`:

- **0 exact-duplicate chunk texts** of 317,081; **89 normalized-duplicate**
  texts (0.028%).
- **0 canonical paragraphs appear in more than one chunk** (2,164,741
  distinct paragraphs, global exact-dedup at build time).
- The primary is an SRS of *elements* within strata. A design effect arises
  from cluster *sampling*, not from a clustered population, so the
  chunk-level Wilson interval is correct as-is. Clustering **does** bite the
  per-category-decision rate, where the chunk is the cluster — handled by a
  chunk-clustered bootstrap in S-RF2 (§7).
- Company clustering: an n=300 draw is expected to touch **132.9 of 176 CIKs**
  (mean over 200 replicates, range 117–145) — simulated **under the actual
  §3.1 two-way Hamilton allocation**, not under SRS. (Unstratified SRS gives
  mean 132.8, range 121–142 on the same seed; the allocation barely moves it.)
  The simulation is **re-run at the ratified `N_PRIMARY = 400`** and the
  manifest carries that number; the n=300 figure here is the pre-ratification
  value and is not quoted after the draw.
  Per-company concentration is not a threat to the chunk-level estimand at
  this n. The simulation lives in `build_draw_g2.py::simulate_cik_coverage()`
  and its output is written to `draw_manifest.json`, so the number is
  reproducible rather than quoted.

**No FPC** (1 − 300/316,291 ≈ 1): omitted, i.e. conservative.
Under proportional allocation Var(p̂_st) = Σ W_h p_h(1−p_h)/n ≤ p(1−p)/n, so
the binomial Wilson interval used as the primary **is conservative by
construction** — it can only be too wide, never too narrow.

### 2.3 8K_BODY is excluded from the frame, and that is stated

790 chunks (0.249%). `data/f4/RUN_COMMANDS.md` trap 7: *"8K_BODY is 790
chunks here and was 8 in E1. The student has essentially no supervision for
it. Do not report a per-class metric on it (HANDOFF §7)."* Proportional
allocation at n=400 would place ~1 row there — enough to contaminate a
headline, never enough to estimate anything. Excluded by predicate.

**Bounded consequence, stated per estimand** — a single pooled bound would be
wrong for the two fields that matter, because 8K_BODY's share of an
*applicable* population is larger than its share of the corpus:

| estimand | applicable population | 8K_BODY share | max points it could move the estimate |
|---|---|---|---|
| `red_flags` / all-section | 317,081 | 790 | **≤ 0.25 pts** |
| `sentiment` (MDA+EX99+8K) | 267,433 | 790 | **≤ 0.30 pts** |
| `guidance_direction` (EX99+8K) | 95,335 | 790 | **≤ 0.83 pts** |

The guidance bound is 3.3× the naive pooled one, in exactly the field where
RUN_COMMANDS trap 7 says the student has "essentially no supervision."
Unmeasured, stated, not hidden.

### 2.4 The chunk-uniform / occurrence-weighted gap — measured, named, NOT built

`features.py::explode_label_occurrences` attributes a label to **every**
filing its paragraph appears in (HANDOFF §3, 2026-08-11). So features consume
an **occurrence-weighted** label-error rate, weight = `n_source_filings`
(mean 2.71, p50 1, p95 9, p99 22, **max 6,220**). The chunk-uniform estimand
this design measures is not that quantity.

Measured before deciding: the Kish effective-sample ratio of those weights
**over the frame** is **0.0298** — an n=300 sample supports an
occurrence-weighted estimate with **n_eff ≈ 8.9**. (Corpus-wide, including
8K_BODY, it is 0.0295 → n_eff 8.8; the frame value is the relevant one.) Per
section: EX99 0.0079, 8K_BODY 0.0124, MDA 0.0714, RISK_FACTORS 0.0939.

**Decision: no occurrence-weighted estimator, at any n.** It is not
estimable from any sample this project can afford, and publishing one would
be a wide interval dressed as a measurement. The gap is instead reported as
a named limitation (§12 item 4) with the weight distribution beside it, and
the exposure is disclosed: the single most-replicated chunk in the frame
appears in 6,220 filings.

### 2.5 Train-overlap census — `EXPANSION_PLAN` §3 item 2, discharged here

`EXPANSION_PLAN.md` §3 item 2 is a ratified standing design ruling:

> *"Every E2 chunk gets a provenance flag (train-overlap vs novel, via
> paragraph/accession overlap against the training split), and the E2 analysis
> reports key results with and without the overlap set."*

**G2 is the first E2 analysis of these labels, and the flag was never built.**
`chunks_v1.parquet` has 28 columns and `labels_e2_v1.parquet` has 43; neither
carries a train-overlap column. A headline that pools memorized and novel
chunks is precisely the optimistic bias the ruling exists to prevent, so the
census is measured here and the flag is constructed inside
`build_draw_g2.py` (§10.1) rather than assumed.

Measured against the **frozen retrain split** `finetune/splits_v12/train.parquet`
(5,736 rows, 392 distinct home accessions, 22 CIKs), over the 316,291-row
frame:

| overlap channel | frame rows | share | expected in an n=300 P draw |
|---|---|---|---|
| chunk_id identical to a train chunk | 0 | 0% | 0 |
| **paragraph_id** shared with a train chunk | **0** | 0% | 0 |
| normalized-exact **text** identical to a train chunk | 487 | 0.154% | ~0.5 |
| **home accession** is a train accession | 10,442 | 3.30% | ~9.9 |
| **any source accession** is a train accession | 14,341 | 4.53% | ~13.6 |
| **union of the three text/accession channels** (the operative flag) | **14,342** | **4.535%** | **~13.6** |
| home CIK is a train CIK | 50,140 | 15.85% | ~48 |

Two findings that matter for how the flag is built:

1. **Paragraph-id overlap is structurally zero and is not evidence of
   novelty.** E1 paragraph ids are namespaced `P-…` and E2's are `E2P-…`; the
   corpus was re-chunked, so ids cannot collide by construction. Any
   implementation that reads §3 item 2's "paragraph … overlap" as an id join
   will report 0% overlap and be wrong. The text-hash channel is the honest
   paragraph-level substitute and is what §10.1 pins.
2. **The operative flag is `overlap = home_accession ∈ train ∨ any source
   accession ∈ train ∨ normalized text ∈ train`** = **14,342 rows, 4.535%**.
   The text channel is almost entirely subsumed by the accession channels —
   486 of its 487 rows are already caught, and it contributes exactly **1**
   row of its own — but it is kept because it is the only channel that catches
   boilerplate replayed under a non-train accession, and dropping it would
   make the flag's definition depend on a fact measured after the fact. Per
   section (accession channels): MDA 5.80%, EX99 2.13%, RISK_FACTORS 4.73%.
   Per arm: G-A frame 2.61%, G-N frame 1.51%.

**What G2 can and cannot say about it, stated now.** At Option B the overlap
subgroup is ~14 rows in P, ~2 in G-A, ~1 in G-N. **That cannot be resolved** —
a 14-row agreement rate carries a ±18.2-point Wilson half-width at p̂=0.85 and no
overlap-vs-novel difference of any plausible size is detectable. The honest
disposition is: report S-OVERLAP (§7) on realized counts, with its useless
interval, and state that the comparison is not powered at any n this project
will buy. Silence would not be honest; a resolved-looking number would be
worse. Note also that CIK-level exposure (15.85%) is 3.5× the accession-level
figure, and company boilerplate recurs near-verbatim, so 4.53% is a **lower
bound** on effective memorization exposure.

---

## 3. Arms

Seed **20260906** — the date this design was written. Fixed by rule before
any composition was inspected; one child RNG stream per stratum, so the draw
is independent of iteration order. **There is no re-draw clause and no
seed-shopping clause.** If the realized composition has an ugly tail, it is
disclosed and reported, exactly as v1.2 §2.3 disclosed its −2.2σ
SUPPLY_INPUT_CONSTRAINT cell rather than repairing it.

Arms are drawn **sequentially without replacement across arms**: P first,
then G-A, then G-N from the frame minus already-drawn ids. Each arm's
estimator reads its own arm only; nothing is pooled across arms. Removing
≤ ~120 rows from a 48,293-row stratum is a null operation on G-N's frame,
and disjointness is asserted in code.

### 3.1 (P) — the primary, base-rate-representative arm

Two-way proportional (Hamilton largest-remainder) allocation over
`section_type × home_sector`, 15 cells.

Two-way rather than v1.2's one-way, for one reason that is in the record and
not invented here: the 2026-08-21 owner amendment binds the extension
stratum's promotion to *"gate G2's **sector-stratified** spot-check"*
(HANDOFF §3). Section×sector proportional allocation honours that wording,
removes sampling noise from the sector mix (making the per-sector secondary
composition-clean), and keeps Var ≤ p(1−p)/n. It costs nothing.

Allocation at n=300 (n=200 and n=400 in §4; **the ratified n=400 table, all 15 cells, is pinned in §14.2**):

| | consumer | energy | financials | healthcare | tech | **total** |
|---|---|---|---|---|---|---|
| MDA | 27 | 24 | 61 | 25 | 26 | **163** |
| EX99_PRESS_RELEASE | 18 | 16 | 23 | 17 | 16 | **90** |
| RISK_FACTORS | 6 | 6 | 10 | 8 | 17 | **47** |
| **total** | 51 | 46 | 94 | 50 | 59 | **300** |

Evaluable bases inside P at n=300: **sentiment n=253** (MDA+EX99),
**guidance n=90** (EX99), **red_flags n=300**.
Expected era split 198 / 102 (not stratified — multinomial, reported on
realized counts).

Batches are a seeded permutation of the whole draw, so no batch is
cell-homogeneous and rater drift cannot be confounded with section or sector.

### 3.2 (G-A) — active-guidance precision, the arm P cannot power

Frame: EX99 rows whose stored `guidance_direction ∈ {RAISED, MAINTAINED,
LOWERED, WITHDRAWN}` — **6,479 rows, 6.85% of EX99** (6,745 corpus-wide
across all sections; 36 on 8K_BODY; 230 on MDA/RISK_FACTORS where the rubric
says the field is N/A and analysis masks it, §3.4).

**Why it is needed:** at n=300, P delivers 90 EX99 rows, of which ~46 (51.08%)
are `guidance_imputed_none = true` rows that §1.3 scores *as NONE*, and only
~6 carry an active direction. Six rows cannot say anything about the calls
that actually drive `guidance_signed_mean` (RAISED +1, LOWERED/WITHDRAWN −1,
MAINTAINED 0). **P's guidance number is therefore a statement about the NONE
mass, and is barred from being quoted alone** — the constraint is written into
the decision rule at §6.3 and into the report template at §10.2, not left as a
caveat here.

**Estimand:** precision of an active call — P(adjudicated reference equals
the stored active value | stored is that active value). Proportional
allocation *within* the active stratum, so the arm estimates one clean
number in the mix features consume:

| n(G-A) | RAISED | MAINTAINED | LOWERED | WITHDRAWN | half-width @ p̂=0.80 |
|---|---|---|---|---|---|
| 40 | 23 | 12 | 5 | 0 | ±12.1 |
| **60** | **34** | **18** | **7** | **1** | **±10.0** |
| 80 | 46 | 24 | 9 | 1 | ±8.7 |

**Per-direction precision is not powered and will not be reported as if it
were.** WITHDRAWN is **not POWERED at this n** — proportional allocation draws
≤1 of the **66 WITHDRAWN rows in the EX99 frame** — and is reported as a count
only.

> **Correction, recorded because it is an E1 constant that was travelling onto
> an E2 artifact.** An earlier draft called WITHDRAWN "not evaluable under
> HANDOFF §7's standing rule." HANDOFF §7 reads *"WITHDRAWN (n=1) and 8K_BODY
> (n=8, from only 2 tickers: BAC, CVX) are not evaluable"* — a statement about
> **E1's corpus**, where n=1. In E2 the EX99 frame holds 66 WITHDRAWN rows
> (plus 1 on 8K_BODY), so the population premise no longer holds. The real
> constraint is sample size, which **the owner can buy out** (§13-vi). This
> matters downstream: `GUIDANCE_MAP` sends WITHDRAWN → −1, so those 66 rows do
> feed `guidance_signed_mean`. 8K_BODY's non-evaluability, by contrast, is
> correctly cited: RUN_COMMANDS trap 7 is about E2's own 790 chunks.

A per-direction quota arm was considered and rejected on v1.2 §3.4's arithmetic: it costs
+30 chunks and ~+10 owner rulings for a metric that cannot move any gate and
must be reported un-pooled anyway. It is offered once, priced, in Option C
(§4.2) so the owner can buy it **before** data rather than after.

> **BOUGHT — owner ruling 2026-09-07 (§14.1 item (vi)).** The quota arm is
> purchased and extended with a 15-row WITHDRAWN quota. **G-A is 100 rows:
> RAISED 46 / MAINTAINED 24 / LOWERED 15 / WITHDRAWN 15** (§14.3 pins the
> arithmetic: 80 proportional + 6 LOWERED floor rows + 14 WITHDRAWN quota
> rows). WITHDRAWN is therefore **measured, at ±19.1 pts and with no bar** —
> it is a disclosure, not a resolution. The arm is now a **quota** arm, so its
> pooled number is corpus-re-weighted by the §14.4 estimator; the
> "~+10 owner rulings" price quoted above is corrected in §14.7 (it is a
> contested-row count under a +30-row budget; the realized cost is ~+3 owner
> items). Per-direction precision carries **no floor** (ruling (iv)).

### 3.3 (G-N) — does "omitted" really mean NONE?

Frame: EX99 rows with `guidance_imputed_none = true` — **48,293 rows, 51.08%
of EX99** (48,790 corpus-wide, 51.18% of guidance-applicable rows).

This is the single largest unverified assumption in the E2 label set. Half of
all guidance-applicable rows carry a value the *writer rule* asserted, not
the model. F4 adopted the rule deliberately (F4_prep §3.2) on E1 evidence;
nothing has tested it on E2 text.

**Estimand:** the false-NONE rate r = P(adjudicated reference is an active
direction | stored is an imputed NONE). It is the quantity that scales the
contamination of every guidance feature: an active call is missed on
0.511 × r of applicable rows.

| n(G-N) | k=0 | k=1 | k=2 | k=3 | k=6 |
|---|---|---|---|---|---|
| 40 | [0.000, 0.088] | [0.004, 0.129] | [0.014, 0.165] | [0.026, 0.199] | [0.071, 0.291] |
| **60** | **[0.000, 0.060]** | [0.003, 0.089] | [0.009, 0.114] | [0.017, 0.137] | [0.047, 0.201] |
| 80 | [0.000, 0.046] | [0.002, 0.067] | [0.007, 0.087] | [0.013, 0.105] | [0.035, 0.154] |

**Two calibration anchors, not one.**

1. *Within E2.* Among EX99 rows where the student *did* emit the key,
   6,479 / 46,252 = **14.0%** are active. If omission were uninformative, r
   would sit near 14%; the rule's premise is that it sits far below. n=60
   separates those two hypotheses cleanly.
2. *Same student, same adapter, different corpus.* `data/hardening/h3v2/
   e1_relabel_student_v12.parquet` is **this student with this adapter**
   (`adapters_sha256 cadca8499b66b2e7…`) labeling E1. Re-derived from its
   `raw_label_json`: the guidance key was omitted on **390 / 1,179 = 33.08%**
   of guidance-applicable E1 rows, against **48,790 / 95,335 = 51.18%** on E2
   — the labeler is held constant and omission worsens by **18.1 points**.
   Off-schema behaviour moved the same way: sentiment emitted on
   RISK_FACTORS went **16 / 1,606 = 1.00%** on E1 to **4,177 / 49,648 = 8.41%**
   on E2, an 8.4× rise. And conditional on emitting, the active rate *rose*
   (81/786 = 10.31% on E1 vs 14.01% on E2) — the apparently stable pooled
   active rate (6.85% E2 vs 6.92% E1 teacher) is two offsetting moves, and
   must never be quoted without the emission rate that produced it.

Anchor 2 is the stronger prior and it points the wrong way for the writer
rule: holding the labeler fixed, omission behaviour is at least partly a
**behavioural/corpus response**, not a semantic "there is no guidance here."
That is exactly the hypothesis G-N exists to test, so G-N is not a formality.
The free decomposition in §7 (omission rate by `word_count` and by
`passage_was_head_truncated`, with the E1-student comparison) ships beside it.

**Owner ruling 2026-09-07 (§14.1 item 2(a)).** This 33.08% → 51.18% move is the
drift the council's §7-item-3 stop-trigger pointed at. It was ruled *"noted,
does not fire as agreement drift; G2 is the mandated measurement; drift
disclosed."* G-N at **n = 80, no floor** (ruling (iv)) is the arm that discharges
it; the §3.3 n=80 row is its pinned operating characteristic.

### 3.4 Sentiment on RISK_FACTORS — a downstream mask, **not** an arm. And a defect.

**The exposure, measured:** 4,177 of 49,648 RISK_FACTORS rows (**8.41%**)
carry a stored `sentiment` the rubric declares N/A (NEUTRAL 3,452 / NEGATIVE
688 / POSITIVE 37). Symmetrically, 2,803 MDA rows (1.63%) and 23
RISK_FACTORS rows carry a `guidance_direction`; **230** of those are active
values that `GUIDANCE_MAP` would map to ±1/0.

**Why it is not a sampled arm.** The rubric does not ask for sentiment on a
RISK_FACTORS passage, so there is no correct value for a rater to agree
with. An agreement rate over a field the rubric never posed measures the
rater's willingness to invent an answer, not the labeler's quality. The right
disposition is mechanical: mask, then never look again.

**But the mask does not currently exist in code, and that is a real finding
this design is obliged to surface.** `features.py:596-604` computes
`sentiment_mean_score` / `sentiment_negative_share` as
`grouped["sentiment_num"].mean()` **over all section types**, and
`guidance_any_present` / `guidance_signed_mean` likewise. It is correct today
only because E1's *teacher* never emitted those fields off-matrix —
`features.py:1159` states that as a property ("RISK_FACTORS chunks never
carry sentiment (rubric applicability matrix); mean excludes them, not
zero-fills"), and on E2 labels it is **false**. Run unchanged at F5, 4,177
off-matrix sentiments and 230 off-matrix active guidance calls would enter
the features silently.

**Pre-registered G2 deliverables on this point (zero owner load, zero extra
sampling):**

1. `analyze_g2.py` emits the exposure census (counts, per-section, per-value)
   as a first-class output.
2. A **required F5 change** is recorded here as a G2 finding, not a G2
   measurement: `features.py` must null `sentiment` on RISK_FACTORS and
   `guidance_direction` on MDA/RISK_FACTORS **before** aggregation, with an
   assertion that the masked count matches the census. Filed as an F5
   blocker, owned by whoever runs G3/F5. The exact sites are
   `features.py:596` (`sentiment_mean_score`), `:602`
   (`sentiment_negative_share`), `:603` (`guidance_signed_mean`), `:604`
   (`guidance_any_present`) — all four aggregate with **no section filter** —
   and the now-false property statement at `features.py:1159`.
   *Provenance note:* `build_segment_parquet` did measure this per segment
   (`guidance.n_emitted_on_non_applicable_section`, summing to 2,826 across
   the 24 segment manifests; `sentiment.n_emitted_on_risk_factors` = 4,177),
   but `finalize_campaign`'s totals dict does not aggregate those keys, so the
   campaign manifest and the close-out never carried them. The counts here are
   re-derived from the parquet, not read from the campaign manifest.
3. If the owner declines the mask, the affected rows stop being off-matrix
   and become in-scope — which would require a **new pre-registration** with
   its own arm. Stated now so that choice cannot be made silently after
   results exist.

### 3.5 Arms considered and rejected

- **Low-extraction-confidence arm** (12,028 rows, 3.79%; FLAGGED status
  41,055, 12.95%). Rejected: label error conditional on bad extraction
  confounds two error sources and cannot be attributed; extraction quality is
  F3's own QA question. Reported instead as a free subgroup on realized P
  counts (S-CONF, §7).
- **Out-of-member-spell arm.** `in_member_spell == false` on **139,418 of
  316,291 frame rows (44.08%)** — 139,711 / 44.06% corpus-wide. This is by far
  the largest weak-region stratum in the frame and it would be dishonest to
  handle the 3.79% and 0.78% strata and drop the 44% one silently. Rejected as
  a **sampled** arm for one reason: `chunks_v1.parquet`'s own caveat says the
  population-gate columns are **not point-in-time** (triage only, never
  conditioning in a walk-forward), so allocating sample to a non-PIT predicate
  would bake a non-PIT choice into the pre-registration. It is however free to
  *report*: `in_member_spell` joins S-CONF (§7) as a subgroup on realized
  counts — zero extra sampling, zero owner load. Prior: membership status is a
  property of the *company-quarter*, not of the *passage*, so there is no
  mechanism by which it should move label quality; S-CONF exists to check that
  rather than to assume it.
- **Head-truncated arm** (2,487 rows, 0.784%). Rejected: bounded influence
  ≤0.78 pts. Reported as a count, and as a free split of the G-N omission rate
  (S-GNDEC, §7). One further passage-level anomaly, surfaced by the F4
  verification and absent from the campaign close-out because
  `finalize_campaign` does not aggregate the key: `seg-021/manifest.json`
  carries `n_passages_not_a_head_prefix: 1` (all 23 other segments: 0). Two
  things re-derived here rather than inherited — (a) the count is real and
  lives only in the per-segment manifests, and (b) **re-checking all 13,226
  stored passages of seg-021 against `chunks_v1.text`, every one *is* a
  byte-exact head prefix**, so the flag fired on an intermediate tokenizer
  encode/decode round-trip inside `fit_prompt`, not on the stored passage. No
  frame row is affected. Recorded so it is disclosed rather than rediscovered.
- **Occurrence-weighted arm.** Rejected on measurement, §2.4.
- **Extension-stratum arm.** Impossible — `home_stratum` is `core` on all
  317,081 rows (W1-core; RUN_COMMANDS trap 8). See §7's deferral note.

---

## 4. n — the owner's choice, priced

### 4.1 Precision (Wilson, 95%, half-width in points)

| n | p̂=0.70 | p̂=0.80 | p̂=0.85 | p̂=0.90 | p̂=0.95 |
|---|---|---|---|---|---|
| 40 | ±13.7 | ±12.1 | ±11.0 | ±9.5 | ±7.6 |
| 60 | ±11.3 | ±10.0 | ±9.0 | ±7.7 | ±6.0 |
| 90 | ±9.3 | ±8.2 | ±7.4 | ±6.3 | ±4.8 |
| 119 | ±8.1 | ±7.1 | ±6.4 | ±5.5 | ±4.1 |
| 168 | ±6.9 | ±6.0 | ±5.4 | ±4.6 | ±3.4 |
| 253 | ±5.6 | ±4.9 | ±4.4 | ±3.7 | ±2.7 |
| 337 | ±4.9 | ±4.3 | ±3.8 | ±3.2 | ±2.4 |

### 4.2 Four options

| | **A — lean** | **B — recommended** | **B-lite — gate-bearing only** | **C — full** |
|---|---|---|---|---|
| P (primary) | 200 | **300** | 300 | 400 |
| G-A (active guidance) | 40 | **60** | 60 | 80 + 30-row direction floor |
| G-N (imputed NONE) | 40 | **60** | 60 | 80 |
| **chunks rated** | **280** | **420** | 420 | **590** |
| rater agent runs (40/batch + 1 replicate) | 8 | **12** | 12 | 16 |
| **adjudicator agent runs, gate-bearing** (≤40 contested rows/batch) | 2 | **3** | **3** | 4 |
| **adjudicator agent runs, `red_flags`** | 2–3 | **3–5** | **0** | 4–6 |
| **adjudicator agent runs, total** | 4–5 | **6–8** | **3** | 8–10 |
| sentiment evaluable n | 168 | **253** | 253 | 337 |
| guidance evaluable n (base-rate arm) | 59 | **90** | 90 | 119 |
| red_flags evaluable n | 200 | **300** | **0 (not rated)** | 400 |
| sentiment half-width @ p̂=0.85 | ±5.4 | **±4.4** | ±4.4 | ±3.8 |
| P(decisive FAIL of a 0.90 bar \| true sentiment agreement 0.83) | 0.80 | **0.93** | 0.93 | 0.97 |
| smallest section×sector cell | 4 | **6** | 6 | 8 |
| **modelled owner items** (§9) | **~54** | **~71** | **~71** | **~86** |

Adjudicator runs are modelled from §9's contested-rate assumptions at ≤40
contested (chunk, field) rows per batch, with `red_flags` broken out because
it is the dominant term: v1.2 measured teacher exact-set error at 42.00% and a
student on novel text will not beat that, so 40–60% of the red-flag rows
contest.

**What B-lite buys and what it costs, honestly.** Under the 2026-08-27
demotion, `red_flags` purchases exactly one deliverable: a rewritten
`RED_FLAG_CAVEAT` string (§8). B-lite drops `red_flags` from the rating task
and from S-RF1/S-RF2 (including the 10,000-resample clustered bootstrap), and
`RED_FLAG_CAVEAT` becomes *"E2 red-flag labels are exploratory /
disclosure-only per the owner's 2026-08-27 ruling; E2 student red-flag error
is unmeasured."* Savings: **3–5 adjudicator agent runs** and the S-RF
apparatus. **Owner items are unchanged (~71)** — `red_flags` never escalated
to the owner in any option (§5.3), so B-lite does *not* buy owner attention,
and it would be dishonest to price it as if it did. It saves calendar and
tokens, and it forfeits the only measured statement E2 will have about its
red-flag labels. The same 420 chunks are still drawn and still rated
(RISK_FACTORS rows included) so blindness and the §3.1 allocation are
unchanged. The choice is the owner's; it is priced here so it is a purchase
rather than an assumption.

**Recommendation: Option B.** Two arguments, both restated on like-for-like
arithmetic:

1. *Guidance base arm.* At the rate this number will actually sit near
   (p̂ ≈ 0.95, since ~93% of the arm is NONE mass), n=59 gives **±6.1 pts** and
   n=90 gives **±4.8** — a **1.3-point** gain, not the 5-point gain an earlier
   draft implied by comparing n=59 at p̂=0.80 (±10.1) against n=90 at p̂=0.95.
   *That correction removes the guidance arm as the load-bearing reason for B.*
2. *Sentiment decisive-FAIL power.* This carries the recommendation on its
   own: P(decisive FAIL of a 0.90 bar | true agreement 0.83) rises
   **0.80 → 0.93** for +140 chunks, +4 rater runs, +1–2 gate-bearing
   adjudicator runs and ~17 owner items. Given §6.4's prior — a FAIL is the
   most probable sentiment outcome — the difference between a 20% and a 7%
   chance of landing INDETERMINATE on the one gate-bearing field that
   survived is the whole value of the pass. C buys a further +0.04 for another
   ~15 owner items and 2 more adjudicator runs; that is the flat part of the
   curve.

The binding currency is owner adjudication attention, not machine time — the
campaign is $0 and runs in agent lane at any of these sizes.

**Option C's direction floor**, priced explicitly so it is bought before data
or not at all: +30 rows allocated to reach ≥15 LOWERED and ≥20 MAINTAINED,
making per-direction precision reportable at ±~12 pts. It converts G-A from a
proportional arm into a quota arm, so the pooled active-precision number must
then be **re-weighted** to the corpus mix (the estimator changes; it is
pinned in code either way).

> **RULED 2026-09-07 (§14.1 item (i), (vi)): OPTION C, with the direction floor
> bought and extended by a 15-row WITHDRAWN quota.** Realized sizes are
> **P = 400, G-A = 100, G-N = 80 → 580 chunks, 15 batches, 18 rater runs**
> (15 + 3 ceiling replicates), `RATE_RED_FLAGS = True`. The Option C column's
> "590 chunks / 16 rater runs" assumed the full +30 floor was spent; only 6 of
> those 30 rows are needed and the WITHDRAWN quota adds 14 (§14.3). Owner load
> and adjudicator runs are restated in §14.7; the per-direction half-widths are
> **±11 to ±19 pts**, not the "±~12" above (§14.3).

---

## 5. Blindness and protocol — v1.2 §5, unchanged in shape

### 5.1 The batch files carry `{chunk_id, text}` and nothing else

Asserted in `build_draw_g2.py`: no stored label, no `section_type`, no
sector, no CIK, no company name, no filing date, no `home_flags`, no
extraction status.

**`draw_g2.csv` carries exactly three columns: `rank, batch, chunk_id`, and
the `chunk_id → arm` map is the sidecar `data/f4/g2_draw_arms.csv`, OUTSIDE
this directory** (§14.9, 2026-09-07 — a model amendment made before any rating,
not an owner ruling). It was a four-column file including `arm` until the
red-team pass of 2026-09-07 pointed out that this section's own argument
applies to `arm` too: `arm = "G-A"` implies the stored `guidance_direction` is
an ACTIVE value and `arm = "G-N"` implies an imputed `NONE`, verified on the
realized draw (100 G-A rows all active; 80 G-N rows all `guidance_imputed_none
= true`, stored `NONE`). That is a per-row disclosure of stored guidance status
for **180 of the 580 drawn rows**, sitting beside the batch files the rater is
told to open, guarded only by the prompt sentence *"no `draw_g2.csv`"* — which
also names the file. If the instruction were ever violated the bias runs one
way: **G-A active precision up and G-N false-NONE rate down**, both flattering
the labels the gate exists to test. Moving the column costs nothing (no
estimator reads it before analysis, arm membership is deterministic from the
seed, and `analyze_g2.py` re-joins it) so it is moved rather than instructed
against. The rater's binding rule still names `draw_g2.csv`, as defence in
depth on a file that no longer carries the channel.
An earlier draft had it also carry `section_type, home_sector, home_cik,
home_filing_date, word_count, n_source_filings` "for auditability" and relied
on a prompt instruction not to read it. That is the *instruct-against-it*
pattern this section credits v1.2 with replacing. `home_cik` +
`home_filing_date` + `section_type` **is** the company and the exact filing
for every drawn chunk — precisely the identity and date information rubric
§8.1 forbids reaching the labeler — and the rater agents hold Read/Grep/Glob.
None of it is needed before analysis: `analyze_g2.py` re-joins every one of
those columns from `chunks_v1.parquet`. Realized composition and per-cell
provenance go to `draw_manifest.json` (which no rater is pointed at) and to
`draw_g2_provenance.csv`, written at **analysis** time. The three-column set
and the sidecar's `chunk_id,arm` set are both asserted exactly, in the same
style as §10.1 item 7's batch-file assertion.

The residual, and it is not solved: the *passage text itself* frequently names
the company. Measured on the frame (first distinctive token of
`home_company_name` appearing in the chunk text): **46.46% overall — EX99
71.14%, MDA 39.03%, RISK_FACTORS 25.25%**; 86.51% contain a 4-digit year and
71.57% a month name. HANDOFF §7 names this channel (*"strict method 26.8%,
loose method 46.0%"*) and says it *"should be watched for in the spot-check,
not treated as solved."* §10.4's prompt states it as fact rather than denying
it, and S-SELFID (§7) discharges the watch instruction at zero cost.

Agreement is **computed mechanically** by `analyze_g2.py`, never
self-reported — the v1.2 correction to v1.1's anchor-resistant self-report
protocol, carried forward verbatim.

**A prompt override of the `label-auditor` spec is not sufficient here, and a
dedicated agent ships instead.** `.claude/agents/label-auditor.md` binding rule
3 reads *"You will be given the chunk text and the STORED labels. First form
your own labels…, THEN compare,"* and its output schema is per-field
`{"verdict": "agree|disagree|unsure|n/a", "my_label": …}`. That `n/a` verdict
**directly contradicts §1.2**: offering it leaks the applicability matrix back
into the rater's decision, which is the leak §1.2 exists to close. v1.2 got
away with an override because it asked for one field and posed no
applicability question; G2 asks for three fields plus a counter-intuitive
"emit even where the field feels inapplicable" instruction, across 12 agent
runs. A rater that falls back to its spec either emits verdicts (anchored on
stored labels → agreement biased **up**, the exact failure v1.2's blindness
change removed) or emits `n/a` (the applicability leak). v1.2 §7.2 already
recommended this fix and it was not taken.

**Pre-registered:** ship `.claude/agents/label-rater-blind.md` (~30 lines, no
new machinery, contents exactly §10.4) and launch *that* agent. Independently,
`analyze_g2.py` hard-fails on any verdict-shaped object and on any `n/a` value
anywhere in `verdicts/*.json`; a rejection counts as a **failed batch** under
§11.3's two-attempt cap. A schema fallback must not be discovered at analysis
time.

### 5.2 What the rater is allowed to read, and why that list is exactly this

`labeling_rubric.md` in full, plus **`rater_policy_addendum.md`** — written
by `build_draw_g2.py` from the eight locked-in policy rules and the A4
hierarchy in `data/hardening/spotcheck_v12/OWNER_POLICY_RULINGS.md`, and
nothing else from that file, **with exemplar ids and company names redacted**.

The redaction is not fastidiousness. Rule 5 reads in part *"A8 and A22 are
materially the same Occidental enumeration and must get the same treatment: no
flags"* — a company-named, prescribed answer. Occidental Petroleum and
JPMorgan Chase (the B11 subject) are both among the 176 CIKs in the E2
universe, and safe-harbor enumerations recur near-verbatim across a company's
own filings, so a G2 draw can contain materially the same passage — for which
the rater would have been handed the answer, keyed to a company name, while
its own binding rule 1 forbids using company identity *"even if the text names
it."* The rule statements stand without the ids: *"materially identical
enumerations must get the same treatment: no flags."* Bounded (red_flags only,
disclosure-only) and entirely avoidable, so it is avoided. `build_draw_g2.py`
asserts the generated addendum contains no string appearing in
`chunks_v1.home_company_name` (§10.1 item 12) and pins the **redacted**
addendum's own sha256 in the manifest.

Justification, and its cost, both stated: OWNER_POLICY_RULINGS.md declares
itself *"the binding interpretation of rubric v1.2 §4/§6 … any future rubric
revision (v1.3) or **F4 labeling QA** must be consistent with them."* G2 is
F4 labeling QA. A rater that ignored the eight rules would be measuring
against a standard the owner has already overruled.

**The consequence is real and is a red-flag caveat, not a gate problem.** The
student was distilled from a v1.2 teacher whose labels *predate* those
rulings, so measured `red_flags` error contains a standard-shift component
that is not the student's error. All eight rules live in rubric §4/§6 — they
say nothing about §2 (sentiment) or §3 (guidance) — so **the gate-bearing
fields are untouched by this**. The addendum's own sha256 is pinned in the
manifest.

### 5.3 Sequencing — model-consensus first, owner-ratified supersedes

Two labelled estimates, both reported with provenance:

1. **Model-consensus estimate** — rater + adjudicator, zero owner load,
   available as soon as adjudication lands.
2. **Owner-ratified estimate** — owner rulings superseding on the escalated
   subset (needs_human + probe).

The gate reads the latest available one at the owner's G2 read. On the v1.1
record the owner overturned 2 of 74 adjudications (2.7%), moving the headline
0.5 pts; on the v1.2 record the owner's rulings landed P1 exactly on the
pre-pinned boundary. Expect a small gap; do not assume one.

**`red_flags` never escalates to the owner.** Its verdicts are adjudicator-
final (constrained by §5.2's addendum) and its provenance line reads
*"model-consensus, no owner ratification"* — appropriate for a
disclosure-only family, and the largest single lever on owner attention.

### 5.4 Rater-noise replicate (the ceiling)

**Batch 1 is re-rated by a second, independent rater instance.** Reports
rater-A-vs-rater-B agreement per field. This is the **ceiling**: no
student-vs-rater agreement can exceed what two independent raters achieve on
the same rubric. Zero owner load; never feeds any primary.

**The ceiling is UPPER-biased, and by how little is unknown (added 2026-09-07,
§14.9).** The replicate files are byte-identical to their originals *including
row order* — the right call for text identity, and asserted — but it means
rater A and rater B see the same passages in the same sequence, so any
ordering, drift or context effect is **shared**. Shared nuisance variance
inflates A-vs-B agreement, so the measured ceiling is an upper bound on the
true two-rater ceiling, not an unbiased estimate of it. Direction is clear;
magnitude is unmeasured and probably small for chunk-level independent
judgements. This biases toward making the *instrument* look more capable, which
in turn makes a student FAIL easier to attribute to the student.

Pre-registration discipline: the ceiling is **reported beside** every bar but
**cannot move** any bar or any decision. If the owner wants a
noise-normalised criterion, it must be ratified as such in §6 **now**, not
chosen after the ceiling is known.

**The problem that rule creates, stated plainly rather than left implicit.**
No student-vs-rater agreement can exceed what two independent raters achieve.
On the only measurement that exists, v1.2's own S7 put rater-vs-rater
exact-set agreement at **0.90, 95% Wilson [0.7695, 0.9604]** at n=40
(`results_v12.json` §S7) — on `red_flags`, not on the gate-bearing fields, and
with an interval that spans the entire region the candidate bars live in. G2's
S-NOISE at n=40 gives ±11.0 pts at p̂=0.85 and cannot bound it either. So as
drafted, this design pre-registers a **near-certain, consequential DECISIVE
FAIL** (§6.4: P = 0.93 at a 0.90 bar if true agreement is 0.83) on an
instrument whose ceiling it cannot pin — and §6.5 makes that FAIL force
demotion or global attenuation of the **only surviving text-feature family**.
A FAIL produced that way is a statement about the measuring device.

**Priced options, for ratification now (decision §13-v):**

| ceiling arm n | replicate batches | half-width @ p̂=0.85 | @ p̂=0.90 | extra rater runs | extra chunks | owner load |
|---|---|---|---|---|---|---|
| **40** (as drafted) | 1 | ±11.0 | ±9.6 | +1 | 0 | 0 |
| 80 | 2 | ±7.8 | ±6.7 | +2 | 0 | 0 |
| **120** | 3 | ±6.4 | ±5.4 | +3 | 0 | 0 |
| 160 | 4 | ±5.5 | ±4.7 | +4 | 0 | 0 |

The arm re-rates chunks already drawn, so it costs **no new chunks and no
owner attention** — only rater agent runs. Concretely: a ceiling measured at
p̂ = 0.90 gives [0.769, 0.960] at n=40 (useless — it contains both bars and the
sentiment prior), [0.815, 0.948] at n=80, **[0.833, 0.942] at n=120** (first n
whose lower bound clears 0.83, so the ceiling stops being confusable with the
student's expected agreement), [0.844, 0.938] at n=160. The owner rules one of: **(a)** ratify
a noise-normalised criterion in §6 now; **(b)** buy a ceiling arm large enough
to bound the instrument (n≥120); or **(c)** ratify explicitly that the ceiling
is reported and ignored, accepting that a FAIL may be instrument noise. All
three are legitimate; choosing none of them after the data is not.

> **RULED 2026-09-07 (§14.1 item (v)): option (b), n = 120.**
> `CEILING_BATCHES = ["batch_01","batch_02","batch_03"]` — 3 replicate batches,
> **0 new chunks, 0 owner items, +3 rater agent runs**. No noise-normalised
> criterion was adopted, so §5.4's standing rule holds unchanged: the ceiling
> is **reported beside** every bar and **cannot move** any bar or any decision.
> **What n=120 actually bounds is smaller than 120 per field, and the table
> above overstates it.** S-NOISE is applicability-masked like every other
> estimate (§10.2.4), so the realized arms are **110 sentiment-evaluable** and
> **65 guidance-evaluable** rows (counted from the completed draw, §14.9 —
> earlier drafts said "~107 / ~62", which were expectations), at **±5.7** and
> **±7.4** pts — not ±6.4 on both. At the plausible ceiling of p̂ = 0.90 (v1.2
> S7's only measurement) the intervals are **[0.8298, 0.9432]** and
> **[0.8034, 0.9520]**: **neither lower bound clears the ratified 0.85 bar, and
> neither clears the 0.83 separation criterion this table used to recommend
> n=120** (sentiment misses it by 0.0002 at the design's pinned z = 1.96 — a
> rounding artefact away from a tie, so quote this endpoint to 4 dp, never as
> "0.830"). Clearing 0.85 needs a measured ceiling of **p̂ ≥ 0.9167**
> (sentiment) / **≥ 0.9368** (guidance). So the
> §6.4 fact-3 attribution problem is **narrowed, not closed, for both
> gate-bearing fields**. §14.5 states what the arm does buy, and prices — but
> does not take — a fourth replicate batch.

### 5.5 (S-PROBE) — the 20-row owner probe of the *uncontested* set

The one arm that is not model consensus, and the fix for the protocol's
one-directional verification (only disagreements are ever checked, so the
pipeline can lower the error estimate but never raise it; rows where student
and rater are wrong the same way are structurally invisible).

- `analyze_g2.py` writes `probe_ids.json`: **20 chunks drawn seeded
  (20260906) from rows that (a) have at least one applicable gate-bearing
  field and (b) on which the rater matched the stored label on every such
  field.** Drawn after rating, by pinned code, so it cannot be curated.
  - Condition (a) is not decoration. RISK_FACTORS has **no** applicable
    gate-bearing field (sentiment N/A per rubric §1, guidance N/A), so all ~47
    RISK_FACTORS rows in P at n=300 satisfy "matched on every applicable
    gate-bearing field" **vacuously**. Without (a), roughly 3–4 of the 20
    probe rows would carry zero gate-bearing information, the owner would
    spend attention ruling on them, and the ≥2/20 trigger would be diluted by
    that share. Asserted in code before `probe_ids.json` is written.
  - **Arm stratification of the 20 is pre-registered: 12 P / 4 G-A / 4 G-N.**
    G-N's uncontested rows are exactly where shared error is most likely —
    student and rater both reading an omitted-guidance press release as NONE —
    so excluding them would defeat the arm's stated purpose. If an arm has
    fewer than its quota of eligible rows, the shortfall moves to P and the
    realized stratification is reported.
- The owner reads text + the agreed labels and rules agree/disagree.
- Reported as k/20 with a Wilson interval on **hidden shared error**. At 0/20
  the 95% upper bound is 16.1%; scaled by the uncontested share **of the
  gate-bearing-applicable rows** (the corrected frame, ~277 of 313 such rows
  at Option B, not the whole draw), that is the most the agreed mass could be
  hiding. That sentence ships with the result.
- **Pre-committed extension, the only one:** if **≥ 2 of 20** are overturned,
  every uncontested row **with an applicable gate-bearing field** goes to the
  adjudicator **once** on those fields, and the primaries are recomputed with
  that correction. Fires at most once. **It adds no chunks and no API calls;
  it does add adjudicator runs and it may add owner items** — at Option B,
  ~277 uncontested rows → **~7 additional adjudicator agent runs**, and any
  new disagreements the sweep produces generate new `needs_human` rows that
  flow back to the owner (~+14 items at a 10% hidden-error rate, band 0 to
  ~28). Modelled as its own row in §9 rather than described as free.

---

## 6. Decision rules — **RATIFIED 2026-09-07: b = 0.85, both gate-bearing fields**

`EXPANSION_PLAN.md` §3 item 7 assigns the bar to gate G2 explicitly:
**[OWNER-GATE G2 sets the bar]**. This section was written as a proposal; what
it owed the owner was not a recommendation dressed as arithmetic but the
operating characteristics of each candidate bar, computed before data.

> **RULED 2026-09-07 (§14.1 items (ii), (iii)).** `RATIFIED_BARS =
> {sentiment: 0.85, guidance_direction: 0.85}` — **one bar each**, rule shape
> §6.1 as proposed, consequence ladder §6.5 as proposed with the λ row
> withdrawn. **No floor on G-A or G-N** (item (iv)). The decision boundaries at
> the ratified (n, b) are pinned in §14.6 — sentiment PASS needs k ≥ 300 of 337
> (p̂ ≥ 0.8902), DECISIVE FAIL k ≤ 273 (p̂ ≤ 0.8101); guidance PASS k ≥ 109 of
> 119 (p̂ ≥ 0.9160), FAIL k ≤ 93 (p̂ ≤ 0.7815) — together with the disclosure
> the bar choice owes: **INDETERMINATE is the modal outcome for both fields
> across §6.4's plausible range**, so §6.5's INDETERMINATE branch is the one
> most likely to execute. Everything below stands as the pre-data record of the
> alternatives; §10.2.7 item 1 forbids emitting a verdict at any bar but 0.85.

### 6.1 Proposed rule shape (three outcomes, per gate-bearing field)

Following the E1 convention already implemented in
`spotcheck/compute_agreement.py:65` and used in HANDOFF §2a's verdicts
(*"red_flags 63.4% — FAILS the 0.70 bar decisively (upper bound below the
bar)"*; *"sentiment 94.6% [91.3, 96.7] — passes"*):

- **PASS** iff the 95% Wilson **lower** bound ≥ bar b.
- **DECISIVE FAIL** iff the 95% Wilson **upper** bound < b.
- **INDETERMINATE** otherwise.

Strict/non-strict inequalities are pinned in code (`kstar_pass()`,
`kstar_fail()`), never applied by judgement, and recomputed for the realized
n_evaluable if it differs from plan.

### 6.2 Operating characteristics — sentiment arm (Option B, n=253)

| bar b | PASS needs k ≥ | i.e. p̂ ≥ | DECISIVE FAIL needs k ≤ | i.e. p̂ ≤ |
|---|---|---|---|---|
| 0.85 | 227 | 0.8972 | 203 | 0.8024 |
| 0.90 | 238 | 0.9407 | 218 | 0.8617 |

P(PASS) at true agreement q; P(DECISIVE FAIL) at true q:

| n (option) | bar | P(PASS \| q=0.90) | q=0.92 | q=0.94 | q=0.95 | P(FAIL \| q=0.75) | q=0.80 | q=0.83 | q=0.85 |
|---|---|---|---|---|---|---|---|---|---|
| 168 (A) | 0.90 | 0.023 | 0.128 | 0.444 | 0.668 | 0.999 | 0.964 | 0.796 | 0.550 |
| **253 (B)** | **0.90** | **0.015** | **0.134** | **0.549** | **0.799** | **1.000** | **0.996** | **0.926** | **0.724** |
| 337 (C) | 0.90 | 0.017 | 0.187 | 0.708 | 0.917 | 1.000 | 0.999 | 0.971 | 0.821 |
| 168 (A) | 0.85 | 0.483 | 0.811 | — | — | 0.911 | 0.424 | — | — |
| **253 (B)** | **0.85** | **0.609** | **0.922** | — | — | **0.979** | **0.563** | — | — |
| 337 (C) | 0.85 | 0.759 | 0.979 | — | — | 0.996 | 0.699 | — | — |

Error rates of the rule when the truth sits **exactly at the bar**: false
FAIL 2.4–3.3%, false PASS 1.3–2.5%, across every (n, b) in §6.2 and §6.3.

### 6.3 Operating characteristics — guidance base-rate arm

| n (option) | bar | PASS needs p̂ ≥ | P(PASS \| q=0.95) | q=0.97 | FAIL needs p̂ ≤ | P(FAIL \| q=0.80) | q=0.85 |
|---|---|---|---|---|---|---|---|
| 59 (A) | 0.90 | 0.9831 | 0.199 | 0.468 | 0.8136 | 0.654 | 0.265 |
| **90 (B)** | **0.90** | **0.9667** | **0.336** | **0.715** | **0.8333** | **0.821** | **0.372** |
| 119 (C) | 0.90 | 0.9580 | 0.450 | 0.851 | 0.8403 | 0.890 | 0.422 |
| **90 (B)** | **0.85** | **0.9333** | **0.836** | **0.981** | **0.7667** | **0.250** | **0.024** |

**Binding constraint on how the guidance verdict may be quoted**, pinned into
`analyze_g2.py`'s report template verbatim and into `results_g2.json` as the
`caveat` field of `guidance_agreement_base_rate`:

> **A PASS on guidance-P is a statement about the NONE mass only.** Of the 119
> EX99 rows in P at n=400, ~61 are `guidance_imputed_none = true` rows scored
> *as NONE* by the §1.3 writer rule and only ~8 carry an active direction, so
> the bar can be cleared almost entirely by the writer rule being right about
> the NONE mass. It is **not** evidence about the RAISED / LOWERED /
> MAINTAINED / WITHDRAWN calls that drive `guidance_signed_mean`. **G-A's
> active precision and G-N's false-NONE rate must be quoted in every table
> where the guidance verdict appears, and no headline may cite the guidance
> verdict alone.**

`analyze_g2.py` enforces this mechanically: it refuses to emit
`guidance_agreement_base_rate` into the report without `guidance_active_precision`
and `guidance_false_none_rate` on the same line (§10.2). The alternative
considered — making S-OMIT's omission-excluded guidance rate **co-primary**
with its own bar, so the primary reads value-correctness rather than coverage
— is a legitimate design and is offered on the owner's menu (§13-vii) rather
than adopted here, because it adds a second bar for the owner to ratify and
the caveat route delivers the same information at zero decision cost.

**G-A and G-N carry no bar in this proposal.** They are precision/contamination
measurements feeding §8's caveat constants. If the owner wants a floor on
active-guidance precision, it must be set now, and §3.2's half-widths
(±10.0 pts at n=60, p̂=0.80) are the honest constraint on how sharp such a
floor can be.

> **RULED 2026-09-07.** *(vii) — OPTION 1:* the base-rate arm stays the
> **single** guidance primary, at bar **0.85**, with the boxed caveat above
> enforced mechanically in `analyze_g2.py` (the guidance verdict is never
> printed without `guidance_active_precision` and `guidance_false_none_rate` on
> the same line, §10.2.7 item 8). **S-OMIT stays a secondary with no bar** — the
> co-primary alternative was declined, so no second bar exists to ratify.
> *(iv), (vi) — no floor on G-A, G-N, or any guidance direction:* G-A's pooled
> active precision is now the **corpus-re-weighted quota estimator of §14.4**
> (reported with its `n_eff`), and each direction's own precision ships with its
> own Wilson interval and `"bar": null` as a **disclosure beside the guidance
> feature**. The caveat's requirement is satisfied by the **pooled** number; no
> per-direction number satisfies it.

### 6.4 The disclosure the owner is owed before choosing

Gate G1's *proposed* floor was **"sentiment and guidance ≥ ~0.90 exact-match
on eval"** (EXPANSION_PLAN §4, F0). Two facts must sit beside that number
before it is carried into G2:

1. **The G1 floor was a floor on a different quantity** — student-vs-teacher
   exact match on the frozen E1 eval split. G2 measures student-vs-blind-
   rater agreement on E2 chunks under the rubric. These are not the same
   number and there is no reason they should coincide.
2. **On the only evidence that exists, a PASS at 0.90 is unlikely.** The
   epoch-2 eval measured sentiment student-vs-teacher exact match at
   **83.6%** (725/867), guidance raw **52.1%** (297/570) — the latter almost
   entirely field omission that F4's adopted missing→NONE writer rule
   converts to asserted NONEs (arm G-N tests exactly that conversion). Rater
   error adds to student error in G2, so the honest prior for sentiment is
   **below** 83.6%, not above. At bar 0.90 and n=253 the most probable
   outcome for sentiment is **DECISIVE FAIL** (P = 0.93 if true agreement is
   0.83).
3. **A bar may sit above the instrument's own ceiling, and this design as
   drafted cannot tell.** No student-vs-rater agreement can exceed two-rater
   agreement. The only ceiling measurement in the record — v1.2 S7,
   `red_flags`, n=40 — is **0.90, 95% Wilson [0.7695, 0.9604]**, an interval
   that straddles both candidate bars; G2's S-NOISE at n=40 (±11.0 pts at
   p̂=0.85) cannot resolve it either. **If the measured two-rater ceiling for a
   field falls below the candidate bar, a DECISIVE FAIL at that bar is a
   statement about the instrument, not about the student, and the §6.5
   consequence ladder should not be executed on it.** The owner's three
   options for closing this are priced in §5.4 and are decision §13-v;
   choosing one is required *before* the draw, because §5.4's own rule forbids
   a noise-normalised criterion chosen after the ceiling is known.
   **RULED 2026-09-07 (item (v)): option (b), a 120-row ceiling arm.** No
   noise-normalised criterion was adopted, so this fact is **narrowed, not
   retired**. After applicability masking the arm is **110** sentiment-evaluable
   and **65** guidance-evaluable rows (realized, §14.9); at a plausible ceiling
   of p̂ = 0.90 the intervals are **[0.8298, 0.9432]** and **[0.8034, 0.9520]**,
   so **neither field's ceiling lower bound clears the ratified 0.85 bar** (that
   needs p̂ ≥ 0.9167 / ≥ 0.9368). **Fact 3 therefore remains live for BOTH
   gate-bearing fields**, and §6.5's instrument-exception may fire on either.
   What the arm bought is width: ±11.0 pts at n=40 → ±5.7 / ±7.4. §14.5.

That is not an argument for lowering the bar. It is the argument for
ratifying **what a FAIL means** before it happens, because with `red_flags`
already demoted, a silent "sentiment fails too" would leave E2 with no text
feature family and no pre-agreed response.

### 6.5 The consequence ladder — **RATIFIED 2026-09-07 as proposed** (§14.1 item (iii); λ row withdrawn)

| outcome | proposed consequence |
|---|---|
| **PASS** | the field is gate-bearing in G3/F5. Its measured error ships as the stated caveat beside every number derived from it. |
| **INDETERMINATE** | the field proceeds, and its measured chunk-level error becomes a **first-class input**: it ships beside every F5 number derived from the field, and the F5 MDE restatement carries the reliability sourced per the box below. No headline may quote the raw MDE alone. |
| **DECISIVE FAIL** | the owner rules one of: (a) demote the field to exploratory/disclosure-only, the `red_flags` precedent; or (b) proceed with the attenuation correction applied to every headline and the demotion re-examined at G4. **Not** a silent proceed. **Unless §6.4 fact 3 fires** — a measured two-rater ceiling below the bar — in which case the FAIL is an instrument result and the ladder is not executed. |

> **WITHDRAWN: G2 does not produce EXPANSION_PLAN §2a's λ.** An earlier draft
> pre-registered "the measured labeler reliability λ per gate-bearing field,
> which is the number §2a's amendment currently assumes at 0.8," and divided
> the F5 MDE by it. That is wrong, and it is the mechanism by which a
> chunk-level proportion would have travelled into an F5 headline denominator.
> §2a's λ traces to `data/reevaluation_2026-08-25/methodology_audit.md` §(b),
> where reliability is defined literally as `reliability = corr(p_s, p_t)` —
> the correlation between a **filing-level aggregated rate feature** and the
> true rate, computed by running per-chunk recall/false-positive rates through
> m-chunk averaging (0.91 at m=30, 0.78 at m=10, ~0.68 at m=5). Three
> mismatches, each independently fatal:
> 1. **Wrong level.** Per-chunk error averages *down* under aggregation, so a
>    G2 chunk-level agreement proportion is systematically **below** the
>    feature reliability, and dividing by it would **inflate** the
>    true-construct MDE.
> 2. **Wrong family.** §2a's λ ≈ 0.8 was derived for red-flag **rate**
>    features, which are now demoted. It is not the λ for sentiment or
>    guidance.
> 3. **Wrong shape.** `guidance_any_present` is an **OR** across chunks, which
>    *amplifies* false positives rather than averaging them down. A single
>    per-field λ is wrong-shaped for it regardless of level.
>
> The draft also contradicted itself: §7's H3v2 comparison row states that a
> chunk proportion and a filing-level correlation *"are not comparable in
> construction and no arithmetic relates them"* — and then §6.5/§8/§12 related
> them arithmetically.
>
> **Pre-registered replacement.** G2 supplies **chunk-level label accuracy
> only**. The λ in §2a's MDE restatement is a feature-level reliability and
> must remain one. F5 sources it from **H3v2's already-measured per-feature
> retention** — `sentiment_mean_score` **0.8696 [0.8153, 0.9109]**,
> `guidance_any_present` **0.7534 [0.5356, 0.9114]** — or from a
> re-derivation that runs G2's measured chunk error through
> `methodology_audit.md` §(b)'s m-chunk algebra **with m stated** (H3v2
> eval-only arm, Pearson, filing-clustered bootstrap, n=630 filings). If that
> composition route is taken, the algebra is pre-registered per feature
> **now**, not chosen after the data. **Under no circumstance is a G2
> agreement proportion substituted for λ.**

### 6.6 What a non-FAIL does **not** mean

Pre-registered wording for the report:

> The G2 spot-check did not trigger a decisive failure for `<field>`.
> Measured agreement is p̂ [LB, UB] (n = …, model-consensus reference with
> owner rulings on the escalated subset; **not** human validation of ground
> truth). At this n the design would have declared a decisive failure with
> probability P₁ if true agreement were 0.83 and P₂ if it were 0.85 — those
> two numbers are the whole of what this result excludes on the low side, and
> a true value below the bar is made **less likely at those rates, not ruled
> out**. **For the gate-bearing fields this estimate is plausibly optimistic
> for the reason in §12.1** — the rater's family is the teacher's family, so
> teacher error the student successfully memorized is invisible to it, biasing
> measured error low. This is a chunk-level label-accuracy figure; it is
> **not** the feature-level reliability λ of `EXPANSION_PLAN` §2a (§6.5), and
> it must not be used as one. Every E2 feature derived from `<field>` carries
> this figure as a stated caveat.
> *(guidance only, ruling (vii)):* … and is never quoted alone —
> `guidance_active_precision` <pooled, corpus-re-weighted, with n_eff>;
> `guidance_false_none_rate` <k/n>.

**Amendments to this template, 2026-09-07 (§14.9), recorded rather than made
silently:**

1. **P₁ / P₂ are computed at the realized (n, bar)**, not the drafted 0.93 /
   0.72. `analyze_g2.py` already emitted the realized values; the prose is now
   consistent with them.
2. **The "true agreement anywhere in roughly [UB, 0.94]" clause is deleted.**
   `0.94` was a literal inherited from an earlier (n, bar) and nothing
   recomputed it, so the emitted sentence read `[99.62%, 0.94]` — a malformed
   interval with one measured endpoint and one undocumented constant, inside
   the one paragraph that exists to prevent overstatement. The point it was
   making is made by P₁ / P₂, which are measured.
3. **The paragraph is verdict-gated.** It is called for both gate-bearing
   fields including under a `DECISIVE_FAIL`, where "what a non-FAIL does not
   mean" is incoherent; that branch now says a decisive failure *did* fire and
   points at §6.5 and §6.4 fact 3 instead of borrowing the non-FAIL wording.
   The interim implementation's opening clause — *"The G2 spot-check returned
   PASS for `<field>`"* — is withdrawn: "returned PASS" reads as a clearance,
   which is exactly what the rest of the paragraph then has to walk back.
4. **The guidance sentence is mandatory here too**, and `A8` was widened from a
   token scan (`guidance_agreement_base_rate` present on the line) to a
   **field** scan over every report line *and* every string in
   `results_g2.json`: any text naming `guidance_direction` alongside a verdict
   marker must also carry `guidance_active_precision` and
   `guidance_false_none_rate`. The assertion is renamed
   `A8_guidance_verdict_never_quoted_without_its_two_arms`, and it was verified
   to **fire** when the escort is removed — a guard that cannot fail is not a
   guard.

---

## 7. Pre-registered secondaries — **none of them can move a gate**

| id | what | precision at Option B |
|---|---|---|
| **S-SEC** | per-section agreement, each gate-bearing field | MDA n=163 (±5.5 @ 0.85), EX99 n=90 (±7.4) |
| **S-SECTOR** | per-sector agreement, 5 core sectors | n = 46–94 → ±7.2 to ±10.3 @ p̂=0.85 |
| **S-ERA** | pre-2019 (~102) vs 2019+ (~198) | ±6.9 / ±5.0 @ p̂=0.85. Pre-named: 33.9% of the frame predates the E1 training window's style |
| **S-CONF** | agreement by `home_extraction_confidence` (high/medium/low), by `home_extraction_status` (FLAGGED vs not, 12.95% of frame), and by **`in_member_spell`** (false on 44.08% of frame, §3.5) | low-confidence is ~3.8% of frame → ~11 rows at n=300, reported with its useless interval, not dropped; `in_member_spell` splits ~168/132 at n=300 → ±5.4 / ±6.1 @ p̂=0.85 |
| **S-OVERLAP** | every gate-bearing rate split by the §2.5 train-overlap flag (overlap vs novel), discharging `EXPANSION_PLAN` §3 item 2's "with and without the overlap set" | ~14 overlap rows of 300 → ±18.2 pts @ p̂=0.85. **Not powered at any n this project will buy**; reported on realized counts with that sentence attached |
| **S-SELFID** | agreement split by whether the passage names its own home company (first-distinctive-token match, §5.1); realized self-identifying share reported beside the frame's 46.46% | discharges HANDOFF §7's *"should be watched for in the spot-check"* instruction. Expect ~139/161 at n=300 → ±5.9 / ±5.5 @ p̂=0.85 |
| **S-GNDEC** | G-N omission decomposition: omission rate on drawn rows split by `word_count` quartile and by `passage_was_head_truncated`, with the same-adapter E1-student baseline (33.08% → 51.18%) beside it | descriptive counts; zero owner load, zero extra sampling |
| **S-ERR** | error-mode decomposition. sentiment: confusion matrix + the NEGATIVE-recall question (epoch-2 eval: R=0.529 vs teacher). guidance: {active→NONE, NONE→active, wrong-active, omitted}. red_flags: spurious / missed / wrong-modality | descriptive counts, no CI |
| **S-OMIT** | every rate restated with omissions excluded, plus the omission rate itself (§1.3) | zero extra load |
| **S-RF1** | `red_flags` exact-set error, v1.2 P1 construction | n=300 → ±5.5 @ p̂=0.60 |
| **S-RF2** | `red_flags` per-category-decision error over n×6 decisions, **chunk-clustered bootstrap** (10,000 resamples, seed 20260906), naive binomial printed beside it and labelled anti-conservative | the v1.1 published 7.5% [91.4, 93.5] was the naive interval; that error is not repeated |
| **S-MASK** | the off-matrix emission census of §3.4 | counts, no CI |
| **S-NOISE** | rater-A vs rater-B, per gate-bearing field (§5.4) | n=40 → ±11.0 @ p̂=0.85. **Ruled 2026-09-07: 3 replicate batches, 120 rows** — after applicability masking the REALIZED arm is **110 sentiment-evaluable (±5.7 @ p̂=0.90) and 65 guidance-evaluable (±7.4)**, not ±6.4 on both (§14.5 as amended by §14.9; the "~107 / ~62" in earlier drafts were planning expectations, superseded by the realized draw) |

**Interval construction, stated once so the document is consistent about which
of its intervals ignore clustering:** S-SEC / S-SECTOR / S-ERA / S-CONF /
S-OVERLAP / S-SELFID intervals are **naive binomial and ignore company
clustering** — the same caveat S-RF2's naive twin carries. The concentration
is mild (the financials cell at n=94 touches ~31 of 37 financial CIKs; energy
at n=46 touches ~23 of 32), so this is a labelling requirement rather than a
wrong number; but it is labelled. Only S-RF2 gets a resampling interval,
because only there is the chunk genuinely a cluster of decisions.

### Comparison rows — **DESCRIPTIVE ONLY, no decision reads them**

| row | why it is a different target |
|---|---|
| vs **epoch-2 eval** (sentiment 83.6%, guidance 52.1% raw, red_flags exact-set 63.07%, per-category 92.42%) | student-vs-**teacher** exact match, on **E1** chunks, on the frozen 1,010-row eval split, with **no adjudication**. G2 is student-vs-**blind rater with adjudication**, on **E2** chunks. Different reference, different corpus, different protocol. **The two numbers are printed side by side with this caveat and NO difference interval is computed.** A Newcombe interval on two non-comparable quantities has no interpretation and would invite exactly the quotation the caveat forbids; `newcombe()` is therefore struck from §10.2's implementation list. |
| vs **H3v2 retention** (12-flag family 0.8078 [0.7503, 0.8528] eval-only; `sentiment_mean_score` 0.8696; `guidance_any_present` 0.7534) | a **filing-level Pearson correlation between two feature vectors**, n=630 filings, filing-clustered bootstrap. G2 is a **chunk-level proportion**. Different unit, different estimator, different frame. They are not comparable in construction and no arithmetic relates them. |
| vs **v1.2 teacher spot-check** (owner-ratified P1 84/200 = 42.00% [35.37, 48.93] red-flag exact-set error) | different labeler, different rubric-interpretation standard (§5.2), different corpus. Reported so the disclosure-only red-flag constants have a lineage, never as "the student is better/worse than the teacher". |

### The deferred "unseen sectors" clause — stated, not quietly dropped

The 2026-08-21 owner amendment binds extension-stratum promotion to G2
showing *"label quality holds in the unseen sectors"* (industrials,
utilities/telecom, materials_realestate). **G2 cannot speak to it.**
`home_stratum` is `core` on all 317,081 rows — the extension stratum was
never chunked and never labeled (W1-core; RUN_COMMANDS trap 8). The clause is
**deferred to a future gate on a future campaign**, not satisfied and not
waived.

What G2 *does* extend beyond E1 is issuer breadth within the five core
sectors: **176 CIKs vs E1's 25 tickers**, and 33.9% of the frame predates
2019. S-SECTOR and S-ERA are the arms that speak to that, and they speak
about breadth, not about unseen sectors.

> **Owner ruling 2026-09-07 (§14.1 item 2(b)): DEFERRED.** Whether to label /
> extend the corpus into the three extension sectors is decided **only after
> G2 passes on core** — *"decide after you know whether the core labels are
> worth extending."* The 2026-08-21 promotion clause is therefore **neither
> satisfied nor waived**; it stays open, and any future extension campaign
> carries its own spot-check. Nothing in G2 may be quoted as speaking to the
> unseen sectors.

---

## 8. Caveat constants to regenerate from THIS pass, and where they travel

EXPANSION_PLAN §3 item 7: *"the 36.6%/63.4% red-flag error constants baked
into report generators were measured on the Claude bootstrap labels; carrying
them onto Qwen labels would be silent misinformation."* Every site below was
located by grep on 2026-09-06 and must be re-derived or re-scoped before F5
emits a report.

**E1-teacher constants that must stop travelling onto E2 numbers:**

| file:line | constant | disposition |
|---|---|---|
| `features.py:91-92` | "36.6% set-level error rate (63.4% agreement, 95% CI [58.6%, 68.0%], below the 0.70 bar)" | replace with G2's S-RF1, **or** re-scope to "E1 teacher, v1.1" |
| `features.py:97`, `features.py:1466` | "43 of 146 corrections were modality flips, 26 of those LEGAL_REGULATORY_ACTION" | replace with G2's S-ERR modality counts |
| `features.py:298-304` (`RED_FLAG_CAVEAT`) | the string carried next to **every** red-flag feature claim | rewritten from G2 + the 2026-08-27 demotion. **This is the single highest-traffic constant in the repo.** |
| `features.py:1097`, `features.py:1159-1160` | "RISK_FACTORS chunks never carry sentiment (rubric applicability matrix)" | **false on E2 labels** (§3.4). Must become a code-enforced mask + a true statement |
| `diagnose.py:625`, `diagnose.py:733` | emits `F.RED_FLAG_CAVEAT` verbatim | inherits automatically once the source string is fixed |
| `backtest.py:1016`, `backtest.py:1031` | emits `F.RED_FLAG_CAVEAT` verbatim | inherits automatically |
| `test_diagnose.py:336` | `assert "63.4%" in F.RED_FLAG_CAVEAT or "36.6%" in ...` | **tripwire — re-pin, never delete** (EXPANSION_PLAN §3.8) |
| `test_diagnose.py:392` | asserts the caveat string appears in the report | re-pin |
| `finetune/eval.py:23`, `:116-118`, `:737`, `:741`, `:1247` | "~36.6% … ~25.0% (Tier C, n=36) … 7.5% (180/2,394)" | correctly scoped to the **E1 teacher** and to eval reports. **Leave as-is; do not repoint at G2** — eval.py measures agreement with that teacher |
| `finetune/relabel_e1.py:105-106`, `:211-212` | same trio, in the H3/H3v2 manifest | frozen record. **Do not touch** |
| `finetune/test_eval_real.py:566` | `assert "36.6%" in rep` | frozen tripwire on the E1 eval report |
| `spotcheck/compute_agreement.py:65-68` | `CI_LOWER_BOUND_BAR = 0.70`, documented as a judgment call | G2's bar is set separately by the owner (§6); this module is E1's. Do not overload it |
| `data/hardening/h3v2/h3v2_diagnostics.py:54` | `"redflag_12_mean": 0.669` | frozen H3 v1.1 record. **Do not touch** |

**New constants this pass produces**, each with its interval and its
provenance line, to be written once into a machine-readable
`data/f4/g2/results_g2.json` and consumed from there rather than retyped:

`sentiment_agreement`, `guidance_agreement_base_rate`,
`guidance_active_precision`, `guidance_false_none_rate`,
`redflag_exact_set_error`, `redflag_per_category_error_clustered`,
`sentiment_omission_rate`, `guidance_omission_rate`,
`offmatrix_emission_census`, `rater_noise_ceiling`, `train_overlap_census`,
`selfid_census`, and `red_flags_status`.

**No λ.** An earlier draft listed "the measured labeler reliability λ per
gate-bearing field, which is the number `EXPANSION_PLAN` §2a's amendment
currently assumes at 0.8." It is struck — see the boxed withdrawal in §6.5.
G2 produces chunk-level label accuracy; §2a's λ is a filing-level feature
reliability; no arithmetic in this pass relates them.

`red_flags_status` is a fixed string, not a measurement:
*"exploratory / disclosure-only (owner ruling 2026-08-27); this pass cannot
change it."* The rewritten `RED_FLAG_CAVEAT` must contain that sentence
(asserted in `analyze_g2.py`, §10.2).

---

## 9. Owner-adjudication load

Model, calibrated on the v1.1/v1.2 record: contested ≈ error rate;
needs_human ≈ 50% of contested; `red_flags` never escalates (§5.3).

Assumed contested rates, stated as assumptions: sentiment 25% (epoch-2
disagreement with the teacher was 16.4%; rater noise adds), guidance base 15%,
G-A 30%, G-N 8%.

**Option B-lite has the same owner load as Option B** — `red_flags` never
escalated to the owner in any option, so dropping it saves adjudicator runs
and calendar, not owner attention (§4.2). It is not given its own column
below for that reason.

| | Option A | Option B / B-lite | Option C as priced | **Option C + quota (RATIFIED 2026-09-07)** |
|---|---|---|---|---|
| sizes (P / G-A / G-N) | 200 / 40 / 40 | 300 / 60 / 60 | 400 / 80+30 / 80 | **400 / 100 / 80 = 580 chunks** |
| sentiment contested → needs_human | 42 → 21 | 63 → 32 | 84 → 42 | **84 → 42** |
| guidance (base) contested → needs_human | 9 → 5 | 14 → 7 | 18 → 9 | **18 → 9** |
| G-A contested → needs_human | 12 → 6 | 18 → 9 | 24 → 12 | **30 → 15** |
| G-N contested → needs_human | 3 → 2 | 5 → 3 | 6 → 3 | **6 → 3** |
| S-PROBE | 20 | 20 | 20 | **20** |
| **owner items, base path** | ~54 | ~71 | ~86 | **~89** |
| *branch:* owner items if the §5.5 probe escalation fires | +~9 (band 0–18) | +~14 (band 0–28) | +~18 (band 0–37) | **+~19 (band 0–38)** |
| *branch:* adjudicator runs if it fires | +5 | +7 | +10 | **+10** |
| **owner items, escalated path** | ~63 | ~85 | ~104 | **~108** |
| rater agent runs | 8 | 12 | 16 | **18** (15 batches + 3 ceiling replicates) |
| adjudicator runs (gate-bearing / red_flags) | 2 / 2–3 | 3 / 3–5 | 4 / 4–6 | **4 / 5–7** |

**The quota's owner-load price, corrected.** §3.2 and the owner brief priced
the direction quota at *"~+10 owner rulings"*. That is a **contested-row** count
under a **+30-row** budget (30 × 30% ≈ 9); §9's currency is **needs_human**,
which is half of contested, and the realized quota is **+20 rows**, not +30
(§14.3). The honest figure is **+3 owner items** over Option C (+6 contested),
banding to **+6** if the two rare directions contest at 60% rather than the
modelled 30% — plausible, since LOWERED and WITHDRAWN are the hardest calls in
the field. The quota is **cheaper in owner attention than it was sold as**;
that is recorded rather than quietly banked. The escalation branch's
denominator at the ratified draw is 337 + 100 + 80 = **517**
gate-bearing-applicable rows, expected uncontested ≈ **379**.

The escalation branch is modelled by sweeping the uncontested
gate-bearing-applicable rows (~184 / ~277 / ~369 at A / B / C, the last
without the §13-vi direction floor; ~390 with it) through the
adjudicator at ≤40 rows per batch, assuming the sweep surfaces new
disagreements at the ~10% hidden-error rate that a ≥2/20 probe result implies,
and that half of those become `needs_human`. `red_flags` is not swept (§5.3).

Reference points: the v1.1 pass ran **104** owner rulings; the v1.2 pass ran
**42** (22 needs_human + 20 probe) against a modelled 45–62 — the model runs
**high**, so treat the table as an upper band. Pattern-block ratification
(the adjudicator's kebab-case `pattern` slug) reduces *reading* effort; on
v1.1's record it was a weak lever on item **count** (90 distinct slugs across
148 contested chunks, 58 singletons).

**Sequencing:** the owner is not the critical path for the model-consensus
number (§5.3). Only the owner-ratified number needs the owner, and only
before the G2 ruling.

---

## 10. What the tooling must do

This section is written so that two engineers implementing `build_draw_g2.py`
and `analyze_g2.py` **independently** produce compatible files. Every path,
column, JSON key and assertion is named. Where a choice exists, it is made
here, not left to the implementer.

### 10.0 Shared contract

- All paths are relative to the repo root; every G2 artifact lives under
  `data/f4/g2/`. Subdirectories `batches/`, `verdicts/`,
  `adjudicator_batches/`, `adjudications/` are created by the script that
  first writes into them.
- Both scripts: system `python3`, **pandas / pyarrow / stdlib only**, **no
  scipy** (Wilson, the exact binomial and the bootstrap are implemented
  in-file), no network, no MLX, no GPU, read-only on every input, `$0`.
- **There is no shared library.** The two scripts communicate only through
  `draw_g2.csv` and `draw_manifest.json`. `build_draw_g2.py` needs no
  statistics; `analyze_g2.py` needs no allocation logic. Neither imports the
  other.
- Every script writes `api_calls: 0`, `gpu_seconds: 0`, `network_calls: 0`
  into its manifest, and asserts it made none.
- Hashing is `sha256` of the raw file bytes, lowercase hex.
- All timestamps are ISO-8601 UTC with a `Z` suffix.
- **Ratified parameters** (owner, §13) enter as module-level constants in
  `build_draw_g2.py` and are copied into `draw_manifest.json`;
  `analyze_g2.py` reads them from the manifest and asserts they match its own
  constants. Neither script contains a default that would let it run
  un-ratified.

**Statistical primitives — one definition, used by both any consumer:**

```
z = 1.96                       # exactly; not 1.959963985
wilson(k, n):                  # no continuity correction, no FPC
    p = k / n
    d = 1 + z*z/n
    c = (p + z*z/(2*n)) / d
    h = z * sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (clip01(c - h), clip01(c + h))
kstar_pass(n, b) = min k in [0..n] with wilson(k,n)[0] >= b      # PASS iff LB >= b
kstar_fail(n, b) = max k in [0..n] with wilson(k,n)[1] <  b      # FAIL iff UB <  b
                   (-1 if no such k)
```

Bounds are clipped to [0, 1] in both JSON and display. `power()` is the exact
binomial tail, `sum(C(n,i) q^i (1-q)^(n-i))`, `i >= kstar_pass` for P(PASS)
and `i <= kstar_fail` for P(FAIL). Bootstrap: chunk-clustered, **10,000
resamples, seed 20260906, percentile method at 2.5 / 97.5**.
**`newcombe()` is NOT implemented** — struck in §7.

### 10.1 `build_draw_g2.py`

**Reads (READ-ONLY, sha-pinned, hard-fail on mismatch):**

| artifact | sha256 |
|---|---|
| `data/f4/labels_e2_v1.parquet` | `f236f421096c665b373addb9ffdbb6cf45454027761838361cf179cbb7b538df` |
| `data/f4/chunks_v1.parquet` | `d67395ece6126045e851e05f4b8fe5c8c49bd69069c44a08b9ee8f9d67bf0857` |
| `labeling_rubric.md` | `46dea3c886846849c82ae2b65d8e29ef95016dece706cd19a2e00b8d99c30b25` |
| `data/hardening/spotcheck_v12/OWNER_POLICY_RULINGS.md` | `eb59c6d3418c28539de1f7f0e39b0a9645dc2bbe00845ca3b2fca0b74a415cef` |
| `finetune/splits_v12/train.parquet` | pinned at implementation time; 5,736 rows asserted |

**Module constants — OWNER-RATIFIED 2026-09-07 (§14). No value below is a
default and none may be inferred; `build_draw_g2.py` hard-fails unless
`PARAMETERS_STATUS == "OWNER_RATIFIED"`.**

```
SEED              = 20260906
BATCH_SIZE        = 40
PARAMETERS_STATUS = "OWNER_RATIFIED"        # owner ruling 2026-09-07, §14.1
OPTION            = "C"                     # §14.1 item (i)
N_PRIMARY         = 400                     # two-way section x sector Hamilton, 15 cells (§14.2)
N_GA              = 80                      # proportional BASE within the active EX99 stratum
N_GA_FLOOR        = {"LOWERED": 15, "MAINTAINED": 20, "WITHDRAWN": 15}   # §14.1 item (vi)
N_GA_WITHDRAWN    = 15                      # == N_GA_FLOOR["WITHDRAWN"]; named because it is
                                            # the 2026-09-07 amendment to the priced +30 floor
N_GA_TOTAL        = 100                     # asserted == sum of targets below
N_GN              = 80                      # §14.1 item (i); no floor (item (iv))
N_TOTAL           = 580                     # 400 + 100 + 80  ->  15 batches (14 x 40 + 1 x 20)
RATE_RED_FLAGS    = True                    # Option C, not B-lite (standing owner item)
CEILING_BATCHES   = ["batch_01", "batch_02", "batch_03"]   # §14.1 item (v): n = 120 rows
RATIFIED_BARS     = {"sentiment": 0.85, "guidance_direction": 0.85}   # §14.1 item (ii)
GA_CORPUS_COUNTS  = {"RAISED": 3716, "MAINTAINED": 1940,   # N_d in the 6,479-row active EX99
                     "LOWERED": 757, "WITHDRAWN": 66}      # frame; w_d = N_d/6479 (§14.4)
SECTIONS = ["MDA", "EX99_PRESS_RELEASE", "RISK_FACTORS"]
SECTORS  = ["consumer", "energy", "financials", "healthcare", "tech"]   # sorted
ACTIVE_GUIDANCE = ["RAISED", "MAINTAINED", "LOWERED", "WITHDRAWN"]
PROBE_STRATA = {"P": 12, "G-A": 4, "G-N": 4}

# G-A target rule, pinned (§14.3). Hamilton within the active stratum at N_GA,
# then the elementwise maximum against the floor vector:
#     target_d = max(hamilton_d(N_GA), N_GA_FLOOR.get(d, 0))
# No direction is reduced below its proportional count, and the UNSPENT remainder
# of the +30-row floor budget is NOT reallocated to any other direction.
# Realized targets, asserted to the row:
#     RAISED 46 (proportional) / MAINTAINED 24 (proportional; floor 20 already met)
#     LOWERED 15 (9 proportional + 6 floor) / WITHDRAWN 15 (1 proportional + 14 quota)
#     = 100 = N_GA_TOTAL
```

`draw_manifest.json` carries every constant above verbatim, including
`parameters_status`, `n_ga_total`, `n_ga_floor` and `ga_corpus_counts`;
`analyze_g2.py` re-asserts each against its own copy (§10.0).

**RNG discipline.** One `numpy.random.default_rng` seeded `SEED`, from which
one **named child stream per stratum** is spawned in a fixed order
(`SECTIONS × SECTORS` for P, then G-A directions, then G-N, then the batch
permutation, then the coverage simulation), so the draw is independent of
iteration order. Hamilton largest-remainder ties break on
`(-fractional_part, section, sector)` — deterministic, stated, not
implementation-defined.

**Train-overlap flag (§2.5), constructed here:**

```
train_acc = set(train.home_accession_number)
train_txt = { sha1(normalize(t)) for t in train.text }      # normalize = collapse whitespace, strip, lower
overlap(row) = row.home_accession_number in train_acc
            or any(a in train_acc for a in row.source_accession_numbers)
            or sha1(normalize(row.text)) in train_txt
```

Asserted to yield **14,342 rows (4.535%)** over the frame. Paragraph-id joins
are **forbidden** — the namespaces differ (`P-…` vs `E2P-…`) and such a join
returns a structurally meaningless 0%.

**Self-identification flag (§5.1), constructed here:** `selfid(row)` is true
iff the first token of `home_company_name` that is longer than 2 characters
and not in the generic-suffix stop list (`inc, inc., corp, corp.,
corporation, company, co, co., the, of, and, group, holdings, holding, ltd,
llc, plc, &, /de/, international, industries, systems, technologies, com`),
lowercased, occurs in `lower(text)`. Asserted to yield **46.46%** over the
frame (MDA 39.03%, EX99 71.14%, RISK_FACTORS 25.25%).

**Writes:**

| path | shape |
|---|---|
| `data/f4/g2/draw_g2.csv` | header **exactly** `rank,batch,chunk_id`, in that order. `rank` 1..N_TOTAL int; `batch` `batch_01`…`batch_NN`; `chunk_id` str |
| `data/f4/g2_draw_arms.csv` | header **exactly** `chunk_id,arm`; `arm` ∈ `{P, G-A, G-N}`. **Outside `data/f4/g2/`** by §14.9 — it discloses stored guidance status per row and must not sit beside the batch files |
| `data/f4/g2/draw_manifest.json` | §10.1.1 |
| `data/f4/g2/batches/batch_NN.json` | JSON array; each object key set **exactly** `{"chunk_id","text"}`; `BATCH_SIZE` objects except the last |
| `data/f4/g2/batches/batch_NN_replicate.json` | one per entry in `CEILING_BATCHES`; byte-identical to its source batch |
| `data/f4/g2/rater_policy_addendum.md` | redacted eight rules + A4 hierarchy (§5.2) |

#### 10.1.1 `draw_manifest.json` keys (all required)

```
generated_utc, design_doc, design_doc_sha256,
seed, option, n_primary, n_ga, n_gn, n_total, batch_size, n_batches,
ceiling_batches, rate_red_flags, ratified_bars, probe_strata,
inputs           : {path: {sha256, rows}}          # the five pinned artifacts
outputs          : {relpath: sha256}               # every file this script wrote
frame            : {n_corpus, n_frame, excluded_8k_body,
                    section_counts, sector_counts, era_counts,
                    distinct_home_ciks, distinct_home_accessions}
allocation_p     : {"<SECTION>|<sector>": int}     # 15 keys, sums to n_primary
allocation_ga    : {"RAISED": int, "MAINTAINED": int, "LOWERED": int, "WITHDRAWN": int}
arm_frames       : {"P": 316291, "G-A": 6479, "G-N": 48293}
realized         : {section_counts, sector_counts, era_counts, distinct_home_ciks,
                    train_overlap: {overlap, novel},
                    selfid: {selfid, not_selfid},
                    in_member_spell: {"true", "false"},
                    extraction_confidence: {high, medium, low},
                    extraction_status: {FLAGGED, ...},
                    head_truncated}
cik_coverage_simulation : {n_replicates: 200, mean, min, max, design: "stratified_hamilton"}
train_overlap_definition, selfid_definition        # the prose above, verbatim
api_calls: 0, gpu_seconds: 0, network_calls: 0
```

#### 10.1.2 Assertions (all hard-fail, all logged by name into `draw_manifest.json.assertions_passed`)

1. every sha256 matches; a changed frame is a **new pre-registration**, not a
   silent re-draw;
2. 317,081 rows, `chunk_id` unique, `chunk_id` set **and order** equality
   between the two parquets;
3. frame excludes 8K_BODY (316,291 rows); **0 8K_BODY rows in any arm**;
4. two-way Hamilton allocation sums to `N_PRIMARY` and every realized cell
   count equals its allocation;
5. G-A frame == EX99 ∧ `guidance_direction ∈ ACTIVE_GUIDANCE` (**6,479** rows,
   asserted); G-N frame == EX99 ∧ `guidance_imputed_none` (**48,293** rows,
   asserted);
6. **arms are pairwise disjoint**, and the union has `N_TOTAL` distinct
   `chunk_id`s;
7. every object in every `batches/*.json` has key set **exactly**
   `{chunk_id, text}` — the v1.2 leak assertion, verbatim;
8. **`draw_g2.csv`'s column set is exactly `{rank, batch, chunk_id}`**, the
   sidecar `data/f4/g2_draw_arms.csv`'s is exactly `{chunk_id, arm}`, and
   `"arm"` does not appear in `draw_g2.csv`'s header — same assertion style as
   item 7, and the reason is §5.1 / §14.9;
9. no batch is section- or sector-homogeneous (seeded permutation over the
   union of all arms);
10. each `batch_NN_replicate.json` is **byte-identical** to `batch_NN.json`;
11. the train-overlap flag yields 14,342 frame rows and the self-id flag
    46.46%, both to the row;
12. **`rater_policy_addendum.md` contains no string appearing in
    `chunks_v1.home_company_name`** (case-insensitive, over the distinctive
    token of each of the 176 names) and contains no `A<number>` / `B<number>`
    exemplar id;
13. no file written under `data/f4/g2/` contains any of the columns
    `sentiment`, `guidance_direction`, `red_flags`, `distress_tier`,
    `section_type`, `home_cik`, `home_filing_date`, `home_company_name`;
14. re-running against unchanged inputs reproduces `draw_g2.csv`,
    `data/f4/g2_draw_arms.csv`, every `batches/*.json` and
    `rater_policy_addendum.md` **byte-for-byte**. A change to the *output
    schema* (as opposed to the draw) is recorded through `draw_schema` in
    `PARAM_KEYS`, so it registers as a supersession with the changed key named,
    never as a silent reproducibility pass (§14.9).

### 10.2 `analyze_g2.py` — this file *is* the pre-registration in code

**Reads:**

| path | required | shape |
|---|---|---|
| `data/f4/g2/draw_g2.csv` | yes | 3 columns: `rank,batch,chunk_id` |
| `data/f4/g2_draw_arms.csv` | yes | `chunk_id,arm`; joined here because §14.9 keeps it outside the rater-pointed tree |
| `data/f4/g2/draw_manifest.json` | yes | §10.1.1; bars and n are read from here |
| `data/f4/labels_e2_v1.parquet`, `data/f4/chunks_v1.parquet`, `finetune/splits_v12/train.parquet` | yes | re-sha-checked against the manifest |
| `data/f4/g2/verdicts/rater_a_batchNN.json` | yes | §10.2.1 |
| `data/f4/g2/verdicts/rater_b_batchNN.json` | optional | §10.2.1; S-NOISE |
| `data/f4/g2/failed_batches.json` | optional | §11.3 re-run record: `{batch, attempt, cause, utc}`, `cause` from §11.3's enumerated list; absent == no batch was re-run |
| `data/f4/g2/adjudications/adjudications.json` | optional | §10.2.2 |
| `data/f4/g2/owner_rulings.json` | optional | §10.2.3; supersedes |
| `data/f4/g2/probe_rulings.json` | optional | §10.2.3 |

Stored labels are joined **here** from `labels_e2_v1.parquet` and are never
written into any rater-visible file.

#### 10.2.1 Rater verdict schema (`verdicts/rater_*_batchNN.json`)

JSON array. Each object's key set is **exactly**
`{"chunk_id","sentiment","guidance_direction","red_flags","reason"}` — or
`{"chunk_id","sentiment","guidance_direction","reason"}` when
`rate_red_flags` is false (B-lite).

- `sentiment` ∈ `{POSITIVE, NEUTRAL, NEGATIVE}`
- `guidance_direction` ∈ `{RAISED, MAINTAINED, LOWERED, WITHDRAWN, NONE}`
- `red_flags`: list (possibly empty) of 2-element lists `[CATEGORY, MODALITY]`
- `reason`: string

**Hard rejections (each counts as a failed batch under §11.3):** any object
containing a key named `verdict`, `my_label`, `n/a`, or `distress_tier`; any
value equal to `"n/a"` / `"N/A"` / `null` in the three label fields; any
`chunk_id` not in that batch; any missing `chunk_id`; any duplicate. This is
§5.1's schema-fallback guard and it fires at parse time, never at
interpretation time.

#### 10.2.2 Adjudicator schemas

`build_adjudicator_batches_g2.py` writes
`adjudicator_batches/adj_batch_NN.json`: JSON array, key set **exactly**
`{"chunk_id","field","text","stored_label","rater_label"}`, ≤ 40 objects per
file, only rows where `stored_label != rater_label` on an **applicable**
field.

`adjudications/adjudications.json`: JSON array, key set **exactly**
`{"chunk_id","field","verdict","correct_label","confidence","brief","pattern","needs_human"}`.
`verdict` ∈ `{agree, disagree, unsure}`; `needs_human` bool; `pattern` a
kebab-case slug.

#### 10.2.3 Owner schemas

`owner_rulings.json`: array, key set **exactly**
`{"chunk_id","field","correct_label","note"}`.
`probe_rulings.json`: array, key set **exactly**
`{"chunk_id","ruling","note"}`, `ruling` ∈ `{agree, disagree}`.

#### 10.2.4 Reference construction, per (chunk, field), pinned

| situation | reference | error |
|---|---|---|
| rater value == stored value | stored | 0 |
| contested, verdict `disagree` | `correct_label` | 1 |
| contested, verdict `agree` | stored | 0 |
| contested, verdict `unsure` or unruled | — | **non-evaluable** |
| field not applicable to `section_type` | — | **masked out** |

Applicability is the §1.2 matrix, applied from `section_type` joined at
analysis time. Owner rulings supersede model adjudications on the rows the
owner rules. `unsure` rows are removed from numerator and denominator,
counted as `n_unsure`, and bracketed by a pre-registered two-sided sensitivity
(`sens_all_error` / `sens_all_agree`).

**G-A quota re-weighting — the only estimator this pass adds (§14.4, owner
ruling 2026-09-07 item (vi)).** G-A is a quota arm, so its unweighted pooled
proportion would over-weight LOWERED (11.7% of the corpus, 15% of the arm) and
WITHDRAWN (1.0% / 15%). `analyze_g2.py` computes, per direction d over the four
`ACTIVE_GUIDANCE` values:

```
k_d, n_d      from the adjudicated reference (§10.2.4 above), per direction
p_hat_d       = k_d / n_d
w_d           = GA_CORPUS_COUNTS[d] / 6479          # asserted re-derived from the frame, 6 dp
p_hat_active  = SUM_d w_d * p_hat_d                 # <- guidance_active_precision.point
p_tilde_d     = (k_d + z*z/2) / (n_d + z*z)         # Wilson centre; never 0 or 1 => V > 0
V             = SUM_d w_d**2 * p_tilde_d * (1 - p_tilde_d) / n_d
p_tilde       = SUM_d w_d * p_tilde_d
n_eff         = p_tilde * (1 - p_tilde) / V         # reported beside the interval, ALWAYS
CI            = wilson_p(p_hat_active, n_eff)       # §10.0 Wilson, p supplied rather than k/n
```

`wilson_p(p, n)` is the §10.0 Wilson formula with `p` supplied instead of
`k/n`; it is the same three lines and is **not** a second interval method. The
plain delta-method interval `p_hat +- z*sqrt(V)` is **not implemented**: it
returns zero width when a direction lands at `p_hat_d == 1`, which at
`n_d == 15` is not a remote outcome.

Each direction is **also** reported on its own —
`guidance_active_precision_by_direction[d] = {k, n, p_hat, wilson_lo,
wilson_hi, corpus_weight, "bar": null}` — with **no bar and no verdict**
(rulings (iv), (vi)); it ships as a disclosure beside the guidance feature.
§6.3's binding caveat is satisfied by the **pooled, re-weighted**
`guidance_active_precision` only. If a direction has `n_d == 0` after masking
and `unsure` removal, `analyze_g2.py` hard-fails rather than silently
renormalising the weights — a dropped stratum changes the estimand.

#### 10.2.5 Writes

| path | contents |
|---|---|
| `data/f4/g2/results_g2.json` | §10.2.6 |
| `data/f4/g2/report_g2.md` | the printed report; the provenance line and the §6.6 non-FAIL wording appear on **every** page |
| `data/f4/g2/probe_ids.json` | `{seed, n, stratification, realized_stratification, frame_size, frame_predicate, chunk_ids[]}` |
| `data/f4/g2/draw_g2_provenance.csv` | `rank,batch,arm,chunk_id,section_type,home_sector,home_cik,home_company_name,home_filing_date,word_count,n_source_filings,in_member_spell,home_extraction_status,home_extraction_confidence,passage_was_head_truncated,train_overlap,selfid` — written **at analysis time**, never before (§5.1) |

#### 10.2.6 `results_g2.json` keys (all required)

```
schema_version : "g2-1"
generated_utc
stage          : "model_consensus" | "owner_ratified" | "owner_ratified_escalated"
provenance     : the HANDOFF §3 model-rater line, verbatim
red_flags_status : "exploratory / disclosure-only (owner ruling 2026-08-27);
                    this pass cannot change it."
inputs         : {path: sha256}
ratified_bars  : {field: b}                      # copied from draw_manifest, asserted equal
primary        : {field: {k, n, p_hat, wilson_lo, wilson_hi,
                          kstar_pass, kstar_fail, bar, verdict,
                          n_unsure, sens_all_error, sens_all_agree, caveat}}
appendix_non_decisional_bars                     # §14.9: k* ONLY, no p_hat/CI
               : {field: {"<b>": {n, k_required_to_clear, p_hat_required_to_clear,
                                  k_at_or_below_which_decisive,
                                  note: "non-decisional; no verdict is defined at this bar..."}}}
failed_batches : [{batch, attempt, cause, utc}]  # §11.3, empty when none
guidance_active_precision
               : {point, wilson_lo, wilson_hi, n_eff, n_nominal, weights, bar: null}
guidance_active_precision_by_direction
               : {"<DIRECTION>": {k, n, p_hat, wilson_lo, wilson_hi,
                                  corpus_weight, bar: null,
                                  note: "disclosure only; no bar (owner ruling 2026-09-07)"}}
secondaries    : {"S-SEC"|"S-SECTOR"|"S-ERA"|"S-CONF"|"S-ERR"|"S-OMIT"|
                  "S-RF1"|"S-RF2"|"S-MASK"|"S-NOISE"|"S-OVERLAP"|"S-SELFID"|
                  "S-GNDEC"|"S-PROBE": {...}}
comparison_rows: [{name, g2_value, other_value, caveat, interpretable: false}]
constants      : {name: {point, ci_lo, ci_hi, n, provenance}}   # the §8 list
assertions_passed : [str]
api_calls: 0, gpu_seconds: 0, network_calls: 0
```

#### 10.2.7 Assertions (all hard-fail)

1. **exactly one ratified bar per gate-bearing field.** `verdict` is emitted
   **only** at `ratified_bars[field]`. Any other bar may appear in
   `appendix_non_decisional_bars` as its **k\* boundaries only** — **no verdict
   word**, and (amended 2026-09-07, §14.9) **no p̂ and no CI**, because neither
   depends on the bar, so reprinting them produced a byte-identical copy of the
   ratified bar's numbers under an un-ratified bar's heading: zero information
   and a second surface that reads like a result. The `note` field above still
   rides on every entry. Printing PASS/INDETERMINATE/DECISIVE-FAIL at two
   bars is bar-shopping reintroduced at report time — the precedent
   (`analyze_v12.py`) carries one `KILL_THRESHOLD` and one `kstar()`, and G2
   matches it;
2. `ratified_bars` in `results_g2.json` equals `draw_manifest.json`'s;
3. no `distress_tier` field is scored anywhere;
4. no 8K_BODY row appears in any arm or any estimate;
5. no `red_flags` row carries `source = owner` (§5.3: red_flags never
   escalates);
6. the rater schema guard of §10.2.1 passed on every verdict file;
7. `probe_ids.json`'s frame contains **only rows with ≥1 applicable
   gate-bearing field**, and its realized arm stratification is recorded;
8. **the guidance VERDICT is never stated without its two arms** (§6.3, ruling
   (vii)). Amended 2026-09-07 (§14.9) from a token scan to a field scan: any
   line of `report_g2.md` — and any string value in `results_g2.json` — that
   names `guidance_direction` or `guidance_agreement_base_rate` alongside a
   verdict marker (`PASS`, `DECISIVE_FAIL`, `INDETERMINATE`, or §6.6's prose
   forms) must also carry `guidance_active_precision` **and**
   `guidance_false_none_rate`. The token version passed while §6.6's prose
   paragraph stated the verdict alone, because that paragraph never contains
   the literal token;
9. the rewritten `RED_FLAG_CAVEAT` string contains `red_flags_status`
   verbatim;
10. no `results_g2.json` field named `lambda`, `reliability` or
    `attenuation_denominator` exists (§6.5's withdrawal, enforced);
11. every subgroup interval is tagged `"interval": "naive_binomial"` except
    S-RF2's, tagged `"interval": "chunk_clustered_bootstrap"` (§7);
12. `S-OVERLAP` is present and carries
    `"powered": false` plus the §2.5 sentence;
13. the emitted verdict is reproducible from `results_g2.json` alone;
14. `api_calls == 0` and no network module was imported.

### 10.3 Order of operations

1. `python3 data/f4/g2/build_draw_g2.py`
2. launch the blind rater agents — one per batch, plus one per entry in
   `CEILING_BATCHES` — each writing `verdicts/rater_a_batchNN.json` (and
   `rater_b_batchNN.json` for the ceiling batches)
3. `python3 data/f4/g2/build_adjudicator_batches_g2.py` → `adjudicator_batches/`
4. launch `label-adjudicator` agents → `adjudications/adjudications.json`
5. `python3 data/f4/g2/analyze_g2.py` → model-consensus estimate +
   `probe_ids.json`
6. owner rules needs_human + the 20 probe rows → `owner_rulings.json`,
   `probe_rulings.json`
7. re-run `analyze_g2.py` → owner-ratified estimate; if the probe fired, run
   the one pre-committed extension (§5.5) and re-run once more

### 10.4 The blind rater agent

**A new agent spec ships: `.claude/agents/label-rater-blind.md`** (§5.1). Its
body is the prompt below; it is launched instead of `label-auditor`, whose
`verdict` / `n/a` schema is incompatible with §1.2. The prompt is not an
override of an incompatible spec — that was the drafting error §5.1 corrects.

> Read `labeling_rubric.md` in full, then `data/f4/g2/rater_policy_addendum.md`,
> then `data/f4/g2/batches/batch_NN.json`. **This is the BLIND variant of the
> protocol: the batch carries no stored labels and no metadata — no stored
> label, no section type, no ticker, no filing date. There is nothing to
> compare against and nothing to agree with.** Note that **the passage text
> itself frequently names the company and contains dates**; you must not use
> company identity, dates, or any outside knowledge of that company, exactly
> as your binding rule 1 requires. Produce your OWN labels for each chunk
> under rubric v1.2. Emit **all three** fields on **every** chunk —
> `sentiment` (POSITIVE / NEUTRAL / NEGATIVE), `guidance_direction` (RAISED /
> MAINTAINED / LOWERED / WITHDRAWN / NONE), `red_flags` (possibly empty list
> of `[CATEGORY, MODALITY]`) — even where the passage's register makes a field
> feel inapplicable; applicability is applied later, mechanically, and is not
> your judgement to make. **There is no "N/A" and no "unsure" option**; if the
> rubric underdetermines the call, make the call the rubric's tie-breakers
> point to. Do **not** label `distress_tier`. **Do not read any other file
> under `data/`** — in particular no `labels*.parquet`, no `draw_g2.csv`, and
> no other file under `data/f4/`. Return, as your final message, one JSON
> array and no prose: `[{"chunk_id": "...", "sentiment": "...",
> "guidance_direction": "...", "red_flags": [["CATEGORY","MODALITY"], ...],
> "reason": "one sentence per field you are least sure of, citing the
> passage's own decisive words"}]`.

Under Option B-lite the `red_flags` clauses are removed from the prompt and
the returned key set is `{chunk_id, sentiment, guidance_direction, reason}`.

## 11. Stopping rule

Pre-committed, so no future session can extend the sample toward a bar:

1. **One draw. One n. Seed 20260906. No re-draws, no top-ups, no adaptive n.**
   If a result lands next to a `kstar`, that is the answer.
2. The **only** extension is §5.5's probe escalation (≥2/20 → adjudicate all
   uncontested rows once on the gate-bearing fields, recompute). It fires at
   most once and adds no chunks.
3. A **failed batch** is re-run on the **same chunk ids**, up to twice.
   **"Failed" means, exhaustively:** the agent errored; returned non-parsing
   JSON; returned a `chunk_id` set that does not match the batch; omitted a
   required field; or violated the output schema (§10.2.1's guard, including
   any `verdict`-shaped object or any `n/a` value). **A batch may NEVER be
   re-run because of what its verdicts say.** The failure cause is recorded in
   **`data/f4/g2/failed_batches.json`** — a list of
   `{batch, attempt, cause, utc}` where `cause` is one of the five enumerated
   above (`agent_errored`, `non_parsing_json`, `chunk_id_set_mismatch`,
   `missing_required_field`, `schema_violation`). `analyze_g2.py` reads it,
   hard-fails on an unenumerated cause, ships it in `results_g2.json` and
   prints it in report §0; an absent file means no batch was ever re-run.
   *(Amended 2026-09-07, §14.9: this clause previously pointed at
   `draw_manifest.json`, which is written only by `build_draw_g2.py` and must
   not be re-run after the draw — so the enumerated record had no implemented
   home and a re-run cause would have been written down nowhere.)* An undefined re-run channel with a two-attempt budget
   is a selection channel a future session could open on content grounds, so
   it is closed by enumeration. Re-running a batch is not a re-draw. If a
   batch still cannot complete, its chunks are reported non-evaluable and n is
   restated — **never replaced with fresh chunks**, because replacement is a
   selection channel.
4. If `labels_e2_v1.parquet` or `chunks_v1.parquet` changes,
   `build_draw_g2.py` fails its sha256 assertion. A changed frame is a new
   pre-registration.
5. The campaign is complete when §10.3 has run once. Anything further is a
   new, named, ratified measurement.

---

## 12. What this design cannot show

1. **It is model consensus, and the direction of the bias differs by field.**
   The rater and the adjudicator are Claude-family instances and the student
   was distilled from a Claude teacher, so G2 partly measures *"does the
   student reproduce Claude"* rather than *"is the student right"*.
   - **`red_flags`: direction genuinely unclear.** Two channels oppose each
     other — shared family pushes measured error **down**, and §5.2's
     owner-policy addendum (a standard the teacher predates) pushes it
     **up**.
   - **`sentiment` / `guidance_direction`: the estimate is plausibly
     optimistic.** §5.2 establishes that all eight policy rules live in rubric
     §4/§6 and *"the gate-bearing fields are untouched by this"* — so the
     addendum channel does **not** operate here. Only the shared-family
     channel remains: any teacher error the student successfully memorized is
     invisible to a Claude-family rater, biasing measured error **low** and
     agreement **high**, the same direction v1.2 declared. §6's PASS rule
     reads only the gate-bearing fields, so this softening lands exactly where
     the decision is made. §6.6's pre-registered wording carries it.

   The 20-row owner probe is the only non-model check and bounds hidden shared
   error weakly (16.1% upper bound at 0/20).
2. **A non-FAIL is not a clearance** (§6.6).
3. **It measures chunk-level label correctness, not feature quality and not
   signal.** Nothing here licenses a claim about F5 backtest results, and —
   corrected in this revision — **it does not supply `EXPANSION_PLAN` §2a's
   reliability denominator λ.** §2a's λ is a *filing-level feature*
   reliability, `corr(p_student, p_true)`; G2's output is a *chunk-level
   proportion*; per-chunk error averages down under aggregation and
   `guidance_any_present`'s OR amplifies it, so no single conversion exists.
   The full withdrawal, with its arithmetic, is boxed in §6.5.
4. **The occurrence-weighted estimand is out of reach** (§2.4, n_eff ≈ 8.9 at
   n=300). Features consume a weighted rate this design cannot estimate. The
   weights are disclosed; the number is not manufactured.
5. **8K_BODY is unmeasured** — 790 chunks, 0.249% of corpus; influence
   ≤ 0.25 pts on the all-section estimand, ≤ 0.30 on sentiment, ≤ 0.83 on
   guidance (§2.3) — **by standing rule** (RUN_COMMANDS trap 7, which is about
   E2's own 790 chunks). **WITHDRAWN guidance is not POWERED**, which is a
   different thing: 66 rows sit in the EX99 frame and proportional allocation
   draws ≤1. HANDOFF §7's *"WITHDRAWN (n=1) … not evaluable"* was a statement
   about **E1's** corpus and does not carry to E2 (§3.2). The constraint is
   sample size and the owner can buy it out (§13-vi).
6. **The extension stratum is unmeasurable here** — it was never labeled. The
   2026-08-21 "unseen sectors" promotion clause is **deferred**, not
   satisfied (§7). **Owner ruling 2026-09-07 (§14.1 item 2(b)) confirms the
   deferral**: the label/extend decision is taken only after G2 passes on core.
   The clause stays open; G2 says nothing about industrials, utilities/telecom
   or materials/real estate.
7. **`red_flags` numbers carry a standard-shift component** from §5.2's owner
   policy addendum, which post-dates the teacher the student learned from.
   Disclosure-only either way.
8. **Per-direction guidance precision and per-sector rates are weak by
   design** — **±11 to ±19 pts**, not the ±10–12 an earlier draft of this line
   claimed: per-direction Wilson half-widths at p̂ = 0.80 are RAISED ±11.3,
   MAINTAINED ±15.4, LOWERED ±19.1, WITHDRAWN ±19.1 (§14.3, which derives
   them). Corrected in place on 2026-09-07 rather than only downstream, because
   this is the section a reader comes to for limitations and the friendlier
   number is the one that gets quoted. Named now so they are not rediscovered
   as a surprise.
9. **`EXPANSION_PLAN` §3 item 2's provenance flag was never populated in the
   F4 artifacts.** `chunks_v1.parquet` (28 cols) and `labels_e2_v1.parquet`
   (43 cols) carry no train-overlap column; G2 constructs one (§2.5, §10.1)
   rather than inheriting one. Consequently **the headline pools memorized and
   novel chunks**, and S-OVERLAP cannot separate them at any n this project
   will buy (~14 overlap rows at Option B, ±18.2 pts). The 4.53%
   accession-level figure is itself a **lower bound**: company-level exposure
   is 15.85%, and boilerplate recurs near-verbatim across a company's filings.
10. **The two-rater ceiling may sit below the bar and this design cannot
   currently tell** (§5.4, §6.4 fact 3). Until decision §13-v is ruled, a
   DECISIVE FAIL is not cleanly attributable to the student. **Two further
   ceiling caveats, added 2026-09-07 (§14.9):** the replicates are
   byte-identical to their originals *including row order*, so raters A and B
   share any ordering / drift / context effect — shared nuisance variance
   inflates A-vs-B agreement, making the measured ceiling an **upper-biased**
   estimate (direction clear, magnitude unmeasured and probably small for
   chunk-level independent judgements); and the realized masked arm is 110 / 65
   rows, not the ~107 / ~62 planned.
11. **The adjudicator sees which candidate is the stored label.** §10.2.2 pins
   the adjudicator batch key set as `{chunk_id, field, text, stored_label,
   rater_label}`, so the incumbent value is always identifiable. Anchoring on
   the incumbent biases adjudications toward *agree*, which lowers measured
   error and raises measured agreement — **the same direction as §12.1's
   shared-family bias**, so the two do not offset. Disclosed, not closed:
   closing it means randomised `label_a` / `label_b` with the key map held
   outside the adjudicator's view, which is a §10.2.2 schema amendment and an
   owner call that would have to be ruled *before* rating. Well attested in
   adjudication protocols; unmeasured here.

---

## 13. Provenance

| item | value |
|---|---|
| frame | `data/f4/labels_e2_v1.parquet`, 317,081 rows, sha256 `f236f421096c665b…` |
| provenance join | `data/f4/chunks_v1.parquet`, sha256 `d67395ece6126045…` |
| rubric | `labeling_rubric.md` v1.2, sha256 `46dea3c886846849…` |
| policy addendum source | `data/hardening/spotcheck_v12/OWNER_POLICY_RULINGS.md`, sha256 `eb59c6d3418c2853…` |
| seed | **20260906** (draw, batching, bootstrap, probe) |
| API calls / GPU seconds / network | **0 / 0 / 0** |
| authority | `EXPANSION_PLAN.md` §3 item 7 [OWNER-GATE G2 sets the bar] + §4 gate G2; 2026-08-21 sector-stratification amendment (HANDOFF §3) |
| protocol precedent | `data/hardening/spotcheck_v12/SPOTCHECK_v12_design.md` (pre-registered 2026-08-27) |
| sources re-derived for this design | `data/f4/labels_e2_v1.parquet`, `data/f4/chunks_v1.parquet`, `data/f4/status/F4_campaign.md`, `data/f4/status/F4_prep.md`, `data/f4/RUN_COMMANDS.md`, `finetune/runs/2026-08-28-v12-eval-epoch2/eval_report.md`, `data/hardening/status/H3v2_attenuation.md` §3, `data/hardening/h3v2/{h3v2_retention_ci_2026-08-27_H3v2.json, e1_relabel_student_v12.parquet}`, `data/hardening/spotcheck_v12/{build_draw_v12.py, analyze_v12.py, OWNER_POLICY_RULINGS.md, SPOTCHECK_v12_design.md, results_v12.json}`, `data/reevaluation_2026-08-25/methodology_audit.md` §(b), `finetune/splits_v12/train.parquet`, `data/labels_v12.parquet`, `features.py`, `diagnose.py`, `backtest.py`, `finetune/eval.py`, `spotcheck/compute_agreement.py`, `labeling_rubric.md`, `HANDOFF.md` §7, `EXPANSION_PLAN.md` §2a/§3/§4 |
| review inputs folded into this revision | adversarial red-team pass on the draft (3 blocking / 12 material / 7 minor) and the independent F4 artifact verification (row-level integrity clean; close-out reporting discrepancies). Both are **model** verdicts, not owner rulings |
| owner decisions required before the draw | **all seven RULED in chat 2026-09-07** (plus flags 2(a), 2(b) and build items 3.1, 3.2); recorded verbatim with their pinned parameters in **§14** |

### Owner decision menu — **ALL SEVEN RULED 2026-09-07 (§14)**

The "options, priced" column is the pre-data record of what was on offer; the
"RULED" column is the owner's decision, given in chat 2026-09-07 before any
chunk was rated. Pinned parameters and their arithmetic are in §14.

| # | decision | options, priced | **RULED 2026-09-07** |
|---|---|---|---|
| **i** | **total n** | A (280 chunks, 4–5 adj runs, ~54 owner items) / **B (420, 6–8, ~71)** / B-lite (420, 3, ~71, no red-flag measurement) / C (590, 8–10, ~86). §4.2 | **OPTION C** — P=400, G-A=80 base, G-N=80; with (vi) the arm totals 580 chunks / 15 batches (§14.2–§14.3, load §14.7) |
| **ii** | **the bar b per gate-bearing field** | 0.85 or 0.90, per field, **one bar each** — §10.2.7 item 1 forbids emitting a verdict at a second bar. Operating characteristics in §6.2/§6.3; the disclosure the choice is owed is §6.4 | **b = 0.85 on BOTH gate-bearing fields**, one bar each; boundaries pinned in §14.6 |
| **iii** | **the consequence ladder** | §6.5 as proposed, with the λ row withdrawn | **§6.5 as proposed**, λ row withdrawn |
| **iv** | **any floor on G-A / G-N** | none proposed; ±10.0 pts at n=60 is the honest sharpness limit (§6.3) | **No floor** on G-A or G-N (nor on any guidance direction, per (vi)) |
| **v** | **the two-rater ceiling** | (a) ratify a noise-normalised criterion now; (b) buy a bigger ceiling arm — n=80 (+2 rater runs, ±7.8), **n=120 (+3, ±6.4)**, n=160 (+4, ±5.5); or (c) ratify that the ceiling is reported and ignored. Zero owner load in every branch. §5.4, §6.4 fact 3 | **(b), n = 120** — `CEILING_BATCHES = batch_01..03`; bounds ~107 sentiment- / ~62 guidance-evaluable rows (§14.5) |
| **vi** | **WITHDRAWN** | leave unpowered (≤1 row drawn of 66 in frame), or add a quota — Option C's +30-row direction floor reaches ≥15 LOWERED / ≥20 MAINTAINED at ±~12 pts and converts G-A into a quota arm whose pooled precision must then be re-weighted to the corpus mix. §3.2, §4.2 | **Quota BOUGHT and EXTENDED** — ≥15 LOWERED, ≥20 MAINTAINED, **plus a 15-row WITHDRAWN quota**; no bar on any direction; pooled precision corpus-re-weighted (§14.3, §14.4). Per-direction precision ships as a disclosure |
| **vii** | **guidance primary** | keep the base-rate arm as the single guidance primary with §6.3's binding caveat (proposed), **or** make S-OMIT's omission-excluded rate co-primary with its own bar, so the primary reads value-correctness rather than coverage. §6.3 | **OPTION 1** — base-rate arm stays the single guidance primary with the §6.3 caveat enforced in code; S-OMIT stays a secondary with no bar |

---

## 14. Owner rulings 2026-09-07 and pre-registered amendments

**Status of this section.** The rulings in §14.1 are the **owner's**, given in
chat on 2026-09-07 on `data/f4/g2/G2_OWNER_BRIEF.md`; their section numbers
refer to this design. They are recorded here as a **dated pre-registration
amendment written before any rating and before any verdict exists**:
`data/f4/g2/verdicts/` does not exist, `adjudications/` does not exist, no
chunk has been rated, and no G2 number of any kind has been computed.
Everything in §14.2–§14.8 is the arithmetic that implements the rulings; it is
re-derived from the frame here, not inherited from prose, and where it revises
a number this design or the brief previously quoted, it says so. **The
arithmetic is model work, not owner judgement.**

### 14.1 The rulings, verbatim

> **(i)** Sample size: OPTION C — P = 400 (two-way section×sector Hamilton),
> G-A = 80, G-N = 80.
>
> **(ii)** Bar b = 0.85 for BOTH gate-bearing fields (sentiment,
> guidance_direction). One bar each. Rule shape §6.1 as proposed.
>
> **(iii)** Consequence ladder §6.5 ratified as proposed (λ row withdrawn).
>
> **(iv)** No floor on G-A / G-N.
>
> **(v)** Two-rater ceiling: buy the larger ceiling arm, n = 120 (3 replicate
> batches; option (b) of §5.4).
>
> **(vi)** Guidance directions: BUY the quota — Option C's +30-row direction
> floor (≥15 LOWERED, ≥20 MAINTAINED) AND extend it with a WITHDRAWN quota of
> 15 rows (a pre-registered amendment, since the design priced only
> LOWERED/MAINTAINED). NO pass/fail floor on any direction (consistent with
> iv). The measured per-direction precision ships as a DISCLOSURE beside the
> guidance feature. *Owner's own note: they said "unpowered" believing it
> meant they would not have to rule on those rows; the intent is: measure it,
> no bar, disclose.*
>
> **(vii)** Guidance primary framing: OPTION 1 — single base-rate primary with
> the binding caveat enforced in `analyze_g2.py` (guidance verdict never
> printed without G-A active precision and G-N false-NONE rate on the same
> line); S-OMIT stays a secondary with no bar.
>
> **2(a)** Council §7 item 3 (`data/hardening/status/G1_council_advisory.md`):
> "noted, does not fire as agreement drift; G2 is the mandated measurement;
> drift disclosed" (drift record: `data/f4/status/F4_campaign.md` §2).
>
> **2(b)** Extension stratum: DEFERRED — decide whether to label/extend the
> corpus only after G2 passes on core ("decide after you know whether the core
> labels are worth extending").
>
> **3.1** Build `.claude/agents/label-rater-blind.md` — APPROVED.
>
> **3.2** Build `data/f4/g2/build_adjudicator_batches_g2.py` — APPROVED.
>
> **Standing from earlier:** `red_flags` are rated (Option C, not B-lite).

### 14.2 The P arm at n = 400 — the §4 two-way Hamilton table, all 15 cells

Computed from the 316,291-row frame (§2.1) under the §10.1 Hamilton rule
(largest remainder; ties on `(-fractional_part, section, sector)`). The same
code reproduces §3.1's pinned n=300 table cell-for-cell, which is the check
that licenses this one.

| | consumer | energy | financials | healthcare | tech | **total** |
|---|---|---|---|---|---|---|
| MDA | 37 | 32 | 81 | 33 | 35 | **218** |
| EX99_PRESS_RELEASE | 25 | 21 | 30 | 22 | 21 | **119** |
| RISK_FACTORS | 8 | 8 | 13 | 11 | 23 | **63** |
| **total** | **70** | **61** | **124** | **66** | **79** | **400** |

Evaluable bases inside P at n=400: **sentiment n=337** (MDA+EX99),
**guidance n=119** (EX99), **red_flags n=400** — matching §4.2's Option C row.
Expected era split **264 / 136** (2019+ / pre-2019; not stratified —
multinomial, reported on realized counts). Smallest cell 8.

Within P's 119 EX99 rows the expected guidance composition is **~61**
`guidance_imputed_none` rows scored *as NONE* (51.08% of EX99) and **~8**
active directions (6.85%) — the two numbers §6.3's binding caveat quotes,
restated at the ratified n. P's guidance primary remains a statement about the
NONE mass; ruling (vii) keeps it as the single primary with that caveat bound
in code.

### 14.3 The G-A quota arm — pinned, with the arithmetic

**Step 1 — proportional base at n = 80** (ruling (i)), Hamilton within the
active stratum. Identical to §3.2's pinned n=80 row, recomputed from the
6,479-row active EX99 frame:

| direction | frame rows | corpus share `w_d` | proportional at n=80 |
|---|---|---|---|
| RAISED | 3,716 | 0.573545 | 46 |
| MAINTAINED | 1,940 | 0.299429 | 24 |
| LOWERED | 757 | 0.116839 | 9 |
| WITHDRAWN | 66 | 0.010187 | 1 |
| **total** | **6,479** | **1.000000** | **80** |

**Step 2 — floor rows** (ruling (vi)). Pre-registered floor vector:
LOWERED ≥ 15, MAINTAINED ≥ 20, WITHDRAWN ≥ 15, RAISED no floor.

**Allocation rule, pinned (the simplest defensible one): the per-direction
target is the elementwise maximum of the proportional allocation and the floor
vector. No direction is reduced below its proportional count, and the unused
remainder of the +30-row budget is NOT spent.**

| direction | proportional | floor | target = max | rows added |
|---|---|---|---|---|
| RAISED | 46 | — | **46** | 0 |
| MAINTAINED | 24 | 20 | **24** | 0 — floor already met by proportional allocation |
| LOWERED | 9 | 15 | **15** | **+6** |
| WITHDRAWN | 1 | 15 | **15** | **+14** |
| **total** | **80** | | **100** | **+20** |

So the design's "+30-row direction floor" costs **6 rows, not 30**, at n=80:
MAINTAINED's ≥20 floor is already satisfied by proportional allocation (24), so
only LOWERED's shortfall (15 − 9) is a floor purchase. **24 of the 30 budgeted
rows are not needed and are not drawn.** The WITHDRAWN quota of 15 is a
separate additive purchase of **+14** rows over the proportional 1.

*Why the remainder is not reallocated, stated so it is not read as
under-delivery:* rows added to a direction already above its floor buy
precision no rule reads (there is no bar on any direction — rulings (iv) and
(vi)), cost owner adjudication items, and push the arm further from
proportional, which raises the re-weighting's design effect (§14.4). Spending
the full 30 would be paying for a number nothing consumes.

> **FINAL G-A = 100 rows: RAISED 46 / MAINTAINED 24 / LOWERED 15 /
> WITHDRAWN 15.**

Sampling fractions, and what the quota does and does not buy:

- WITHDRAWN draws **15 of the 66** rows in the frame — a 22.7% sampling
  fraction. §2.2's no-FPC rule stands, so the interval is ~12% wider than a
  finite-population one (√(1−f) = 0.879): conservative by construction.
- LOWERED 15 of 757 (2.0%); MAINTAINED 24 of 1,940; RAISED 46 of 3,716.
- **Per-direction Wilson half-widths at p̂ = 0.80: RAISED ±11.3, MAINTAINED
  ±15.4, LOWERED ±19.1, WITHDRAWN ±19.1 points.** §12.8's "±10–12 pts"
  understates this for the quota directions; the honest range is **±11 to ±19
  pts**, corrected here rather than left to be rediscovered. These are
  **disclosure numbers with no bar**; what the quota buys is that the value
  `GUIDANCE_MAP` sends to −1 stops being literally unmeasured, not that it
  becomes resolved.

### 14.4 Pooled active precision under the quota — the re-weighting, pinned

The arm is no longer proportional, so an unweighted pooled p̂ would over-weight
LOWERED (11.7% of the corpus, 15% of the arm) and WITHDRAWN (1.0% of the
corpus, 15% of the arm). Pinned estimator, replacing the proportional arm's
simple pooled proportion **and nothing else** (no other estimator in this
design changes):

```
p_hat_active = SUM_d w_d * p_hat_d            d in {RAISED, MAINTAINED, LOWERED, WITHDRAWN}
    w_d      = N_d / 6479  = {RAISED 0.573545, MAINTAINED 0.299429,
                              LOWERED 0.116839, WITHDRAWN 0.010187}   # asserted from the frame
    p_hat_d  = k_d / n_d
# interval: stratified Wilson via an effective n (reuses the §10.0 primitive; no bootstrap, no scipy)
    p_tilde_d = (k_d + z*z/2) / (n_d + z*z)                  # Wilson centre; never 0 or 1, so V > 0
    V         = SUM_d w_d^2 * p_tilde_d*(1 - p_tilde_d) / n_d
    p_tilde   = SUM_d w_d * p_tilde_d
    n_eff     = p_tilde*(1 - p_tilde) / V
    CI        = wilson_p(p_hat_active, n_eff)                # §10.0 Wilson formula, p supplied not k/n
```

`n_eff` is reported **beside the interval, always**. Behaviour computed before
data so the estimator is on the record: at p̂_d = 0.80 in all four directions,
p̂_active = 0.800, **n_eff = 85.2**, CI [0.703, 0.871] (±8.4 pts) — the quota
costs ~15 effective rows against a nominal n=100; at p̂_d = 1.00 in all four,
n_eff = 89.3 and the interval is [0.959, 1.000] rather than degenerate; at
(R .90 / M .85 / L .70 / W .60), p̂_active = 0.8586, n_eff = 90.9, CI
[0.772, 0.916], against an unweighted quota-distorted 0.813.

The plain delta-method interval p̂ ± z√V was the alternative; it is rejected
because it returns **zero width** when a direction lands at p̂_d = 1, which at
n_d = 15 is not a remote outcome.

**Each direction's own precision is reported with its own Wilson(k_d, n_d)
interval and NO bar** (rulings (iv), (vi)). `analyze_g2.py` emits
`guidance_active_precision` (pooled, re-weighted, carrying `n_eff` and
`weights`) and `guidance_active_precision_by_direction` (four p̂ + Wilson + n,
each carrying `"bar": null`). The **pooled** number is what §6.3's binding
caveat requires on the guidance verdict's line; no per-direction number
satisfies that requirement.

### 14.5 G-N, the ceiling, and what the ceiling now bounds

- **G-N = 80** rows from the 48,293-row imputed-NONE frame (§3.3), **no floor**
  (ruling (iv)). §3.3's n=80 row is the pinned operating characteristic:
  k=0 → [0.000, 0.046]; k=3 → [0.013, 0.105]; k=6 → [0.035, 0.154].
- **`CEILING_BATCHES = ["batch_01", "batch_02", "batch_03"]` → n = 120 rows**
  re-rated by an independent rater B (ruling (v), option (b) of §5.4). 0 new
  chunks, 0 owner items, **+3 rater agent runs**.
- **Total drawn and rated: 400 + 100 + 80 = 580 chunks**, in **15 batches** of
  40 (14 full, one of 20). **Rater agent runs: 15 + 3 replicates = 18.**
- `RATE_RED_FLAGS = True` (Option C, not B-lite): `red_flags` is rated on all
  580 chunks, stays exploratory / disclosure-only, and no G2 result can
  re-promote it (§1.1).

**What the ceiling now bounds, at the level applicability leaves it.** S-NOISE
is computed on the applicability-masked intersection like every other estimate
(§10.2.4), so 120 re-rated *rows* are **not** 120 evaluable rows *per field*.
The draw is complete, so this is a **count, not an expectation** (corrected
2026-09-07, §14.9 — the "~107 / ~62" below were planning values shipped where a
measurement existed). Batches 01–03 hold EX99 65 / MDA 45 / RISK_FACTORS 10, so
the ceiling arm is **110 sentiment-evaluable and 65 guidance-evaluable** rows.
`analyze_g2.py` recomputes both from the draw at run time
(`ceiling_realized_n()`) and keeps `CEILING_PLANNED_N = {107, 62}` only as an
explicitly labelled planning value, so planned-vs-realized drift stays visible.
Therefore:

- **sentiment ceiling**, **110** evaluable rows: at p̂ = 0.90 the interval is
  **[0.8298, 0.9432]**, ±5.7 pts. Its lower bound is **below the ratified 0.85
  bar**, and still — now by **0.0002**, at the design's pinned z = 1.96 — below
  the **0.83** separation criterion §5.4 used to recommend n=120. *The realized
  n does not flip that sign; it makes the miss a rounding artefact away from a
  tie, which is a reason to quote 4 decimal places on this endpoint and never
  the 3-dp "0.830".* Clearing 0.85 requires a measured ceiling of **p̂ ≥ 0.9167**
  (discrete k* ≥ 101/110 = 0.9182); clearing 0.83 requires **p̂ ≥ 0.9002**.
- **guidance ceiling**, **65** evaluable rows: at p̂ = 0.90, **[0.8034, 0.9520]**,
  ±7.4 pts. Clearing 0.85 requires **p̂ ≥ 0.9368** (discrete k* ≥ 61/65 =
  0.9385); clearing 0.83, **p̂ ≥ 0.9213**.

**Correction to what the arm was sold as, recorded before data.** §5.4's table
and the owner brief priced n=120 at "±6.4 pts" and called 120 *"the first n
whose lower bound clears 0.83."* Both figures assume all 120 re-rated rows are
evaluable **for the field in question**; they are not. At the plausible ceiling
of p̂ ≈ 0.90 — v1.2 S7's only measurement, and on `red_flags` at that —
**neither gate-bearing field's ceiling lower bound clears 0.83 or the ratified
0.85 bar.** §6.4 fact 3 therefore stays live for **both** fields, not just
guidance, and the owner ruled (v)(b) on the optimistic figure. Stating that
now, before the draw, is the only honest time to state it.

**What the arm does buy, exactly.** (1) Width: ±11.0 pts at n=40 — an interval
containing both candidate bars and the entire student prior — becomes ±5.7 and
±7.4 at the realized masked n. (2) If the ceiling lands high (p̂ ≥ 0.9167 / ≥ 0.9368 at the realized n) the
attribution question is closed by the lower-bound criterion. (3) If it lands low enough
that its **upper** bound is below 0.85, fact 3 fires decisively and §6.5's
ladder is not executed on that field. (4) In between — the likeliest region —
the ceiling is reported, a FAIL's attribution is stated as unresolved, and **no
bar moves**: §5.4's standing rule holds, no noise-normalised criterion was
adopted, and none may be adopted after the ceiling is known.

**Priced, flagged, NOT taken — a model recommendation, not an owner ruling.** A
**fourth** replicate batch (`batch_04`) would give **142** sentiment-evaluable
and **86** guidance-evaluable rows — recomputed from the realized draw, not
projected (±5.0 / ±6.4 pts; lower bound clears 0.83 at p̂ ≥ 0.8918 / ≥ 0.9094)
— for **+1 rater agent run, 0 new chunks, 0 owner items**.
`CEILING_BATCHES` stays at **three** — ruling (v) said three — unless the owner
rules otherwise. It is surfaced here because the ruling was made against the
"±6.4 at n=120" figure, and a top-up decided *after* the ceiling is measured
would be exactly the post-hoc design choice §5.4 forbids.

Computing S-NOISE unmasked, on all 120 rows, is **not** an option: it would mix
in RISK_FACTORS sentiment and MDA guidance, fields the rubric never poses
(§3.4), and would be an estimator chosen to make a number look better.

### 14.6 Decision boundaries at the ratified (n, b) — pinned before data

Planning values, from the §10.0 primitives; `analyze_g2.py` recomputes them at
the realized `n_evaluable` if it differs (§6.1). The same code reproduces
§6.2's pinned n=253 row exactly, which is the check that licenses these.

| field | n (plan) | bar | PASS iff k ≥ | i.e. p̂ ≥ | DECISIVE FAIL iff k ≤ | i.e. p̂ ≤ |
|---|---|---|---|---|---|---|
| `sentiment` | 337 | **0.85** | 300 | 0.8902 | 273 | 0.8101 |
| `guidance_direction` (base-rate arm) | 119 | **0.85** | 109 | 0.9160 | 93 | 0.7815 |

Operating characteristics at those boundaries (exact binomial):

| field | q=0.80 | q=0.83 | q=0.85 | q=0.88 | q=0.90 | q=0.92 |
|---|---|---|---|---|---|---|
| sentiment — P(PASS) | 0.000 | 0.001 | 0.020 | 0.317 | 0.759 | 0.979 |
| sentiment — P(DECISIVE FAIL) | 0.699 | 0.183 | 0.027 | 0.000 | 0.000 | 0.000 |
| sentiment — **P(INDETERMINATE)** | 0.301 | **0.816** | 0.953 | **0.683** | 0.241 | 0.021 |
| guidance — P(PASS) | 0.000 | 0.006 | 0.024 | 0.141 | 0.347 | 0.645 |
| guidance — P(DECISIVE FAIL) | 0.341 | 0.102 | 0.029 | 0.002 | 0.000 | 0.000 |
| guidance — **P(INDETERMINATE)** | 0.658 | 0.893 | 0.947 | 0.857 | 0.653 | 0.355 |

**The disclosure the ratified bar owes, stated before data.** Lowering the bar
from the G1-floated 0.90 to 0.85 buys an outcome space the data can resolve at
the top end and pays for it at the bottom: at n=337, if true sentiment
agreement is 0.83 this design now declares a decisive FAIL **18.3%** of the
time (it was **97.1%** at bar 0.90). And over the region §6.4's prior actually
points to, **INDETERMINATE is the modal outcome for both fields**: for
sentiment at q ∈ [0.83, 0.88] it runs **0.68–0.95** and only stops being modal
at q ≥ 0.90 (PASS 0.759); for guidance it is modal across the whole of
q ∈ [0.80, 0.90], **0.65–0.95**, yielding to PASS only at q ≥ 0.92. §6.5's
INDETERMINATE branch (the field proceeds; its measured chunk-level error
becomes a first-class input to every F5 number derived from it; no headline
quotes the raw MDE alone) is therefore the branch **most likely to execute**,
and it was ratified under (iii) before that was known. §6.4's warning stands
unchanged: the bar is justified by its ratification date, not by the
friendliness of the number it produces.

### 14.7 Owner load and run counts, restated (amends §4.2 and §9)

Under §9's own model (contested ≈ error rate; needs_human ≈ 50% of contested;
`red_flags` never escalates), at P=400 / G-A=100 / G-N=80:

| | Option C as priced | **Option C + quota (RATIFIED)** |
|---|---|---|
| sentiment contested → needs_human | 84 → 42 | **84 → 42** |
| guidance (base) contested → needs_human | 18 → 9 | **18 → 9** |
| G-A contested → needs_human | 24 → 12 | **30 → 15** |
| G-N contested → needs_human | 6 → 3 | **6 → 3** |
| S-PROBE | 20 | **20** |
| **owner items, base path** | ~86 | **~89** |
| *branch:* probe escalation (§5.5) | +~18 (band 0–37) | **+~19 (band 0–38)** |
| *branch:* adjudicator runs if it fires | +10 | **+10** |
| **owner items, escalated path** | ~104 | **~108** |
| rater agent runs | 16 | **18** (15 batches + 3 ceiling replicates) |
| adjudicator runs, gate-bearing / red_flags / total | 4 / 4–6 / 8–10 | **4 / 5–7 / 9–11** |

**Correction to the price the quota was sold at, recorded because it travelled
into the owner brief.** §3.2 and the brief priced the quota at *"~+10 owner
rulings"*. That figure is a **contested-row** count under a **+30-row** budget
(30 × 30% ≈ 9); §9's currency is **needs_human**, which is half of contested,
and the realized quota is **+20 rows**, not +30. The honest figure is
**+3 owner items** (+6 contested), with a band to **+6 items** if the two rare
directions contest at 60% rather than the modelled 30% — plausible, since
LOWERED and WITHDRAWN are the hardest calls in the field. The quota is
therefore **cheaper in owner attention than it was sold as**; that is stated
rather than quietly banked.

The escalation branch's denominator is restated for the ratified draw:
gate-bearing-applicable rows = 337 (P, MDA+EX99) + 100 (G-A) + 80 (G-N) =
**517**; expected uncontested ≈ **379**; sweeping those at ≤40 rows/batch is
the +10 adjudicator runs above.

### 14.8 Operational consequences, and what this amendment does NOT change

- The existing `draw_g2.csv`, `draw_manifest.json` and `batches/*.json` are the
  **provisional Option-B draw** (420 chunks, 11 batches, `ratified_bars: null`)
  and are **superseded**. `build_draw_g2.py` is re-run once at the §14
  constants. **No selection channel opens by doing so:** `verdicts/` does not
  exist, no chunk has been rated, no result exists, and the seed (20260906),
  the allocation rule, the batching rule and the assertion list are unchanged
  — only `N_PRIMARY`, the G-A targets and `CEILING_BATCHES` change, all of them
  ruled before any rating. §11's one-draw / no-re-draw / no-top-up clause binds
  from this draw forward.
- **Unchanged:** the seed and stopping rule (§3, §11); every estimator in
  §10.2.4 (§14.4's re-weighting is an *addition* required by the quota, which
  did not exist while the arm was proportional); the applicability matrix
  (§1.2); the omission conventions (§1.3); blindness (§5.1 — whose *column
  set* was later narrowed by §14.9 without changing the draw); the rater policy addendum and its redaction (§5.2);
  the §5.5 probe (20 rows, 12 P / 4 G-A / 4 G-N); the §8 caveat-constant list
  and the `red_flags_status` string; every §10.1.2 and §10.2.7 assertion.
- **Assertions added**, in the same style as §10.1.2 / §10.2.7: G-A realized
  per-direction counts equal `{RAISED 46, MAINTAINED 24, LOWERED 15,
  WITHDRAWN 15}` exactly; `w_d` re-derived from the frame equals the pinned
  vector to 6 dp; `guidance_active_precision` carries `n_eff` and `weights`;
  every entry of `guidance_active_precision_by_direction` carries
  `"bar": null`; `PARAMETERS_STATUS == "OWNER_RATIFIED"`.
- **Subgroup counts quoted at Option B elsewhere in this document scale by
  400/300 and none of them change a conclusion.** The largest is S-OVERLAP:
  the §2.5 train-overlap subgroup goes from ~14 rows in P to **~18** (4.535% of
  400), whose Wilson half-width at p̂=0.85 improves from ±18.2 to **±16.2 pts**
  — still **not powered at any n this project will buy**, so §2.5's and §7's
  disposition stands verbatim. Likewise §2.3's 8K_BODY influence bounds
  (≤0.25 / ≤0.30 / ≤0.83 pts) are properties of the *frame*, not of n, and are
  unchanged. Realized counts, not these projections, are what ship.
- **Still deferred, still not satisfied:** the extension stratum and its
  2026-08-21 "unseen sectors" promotion clause (ruling 2(b); §7, §12.6). **Still
  unmeasured:** the occurrence-weighted estimand (§2.4), 8K_BODY (§2.3), and
  `distress_tier` (never scored, standing hard rule). **Still exploratory:**
  `red_flags` (§1.1). Nothing in this amendment touches any of them.

### 14.9 Red-team fix pass, 2026-09-07 — model amendments, NOT owner rulings

Made **before any rating exists** (`verdicts/` absent, `adjudications/` absent,
no `results_g2.json`), in response to a red-team review of the §14 build. None
of these is the owner's judgement; the owner's rulings are §14.1's twelve items
and nothing else. Every one of them either **removes a number that was not
measured** or **removes a channel that was only instructed against**. No
estimand, no bar, no n, no seed and no drawn chunk changes.

| # | change | why | blast radius |
|---|---|---|---|
| 1 | §6.6's paragraph now carries `guidance_active_precision` + `guidance_false_none_rate` for `guidance_direction`, and `A8` became a **field** scan over the report *and* every string in `results_g2.json` | ruling (vii) OPTION 1 was enforced only on the machine-formatted line. The prose paragraph — the most quotable text in the report — stated the guidance verdict and its rate alone, and `A8`'s token scan never looked at it because it does not contain the literal `guidance_agreement_base_rate` | `analyze_g2.py` `_non_fail_wording`, `_assertions`; verified the widened guard **fires** when the escort is removed |
| 2 | the `[UB, 0.94]` clause is deleted; the point is made with the two operating characteristics that are computed | `0.94` was a literal from a different (n, bar); nothing recomputed it, so the sentence shipped as `[99.62%, 0.94]` | §6.6 template + `_non_fail_wording` |
| 3 | §6.6's pre-registered opening clause restored verbatim; the paragraph is verdict-gated | *"The G2 spot-check returned PASS"* was an unlabelled strengthening of the sentence §6.6 exists to weaken, and was incoherent under a `DECISIVE_FAIL` | §6.6 + `_non_fail_wording` |
| 4 | `arm` moves out of `draw_g2.csv` into `data/f4/g2_draw_arms.csv`, **outside** the rater-pointed tree | `arm` disclosed stored guidance status for 180 of 580 rows, beside the batch files, guarded only by a prompt sentence. §5.1 rejects exactly that pattern for every other column | §5.1, §10.1 (writes table + item 8), `build_draw_g2.py`, `analyze_g2.py`, `build_adjudicator_batches_g2.py`, tests. **The draw is unchanged**: same seed, same 580 `chunk_id`s in the same order, `batches/*.json` byte-identical (verified by diff against the pre-fix artifacts). `draw_schema` is now a `PARAM_KEYS` entry so the schema change registers as a recorded supersession rather than a silent `A14` reproducibility failure |
| 5 | realized numbers replace planning approximations in three places: the §6.3 caveat (119 EX99 rows in P → **60** imputed-NONE, **9** active, was "~61 / ~8"), the ceiling arm (**110 / 65**, was "~107 / ~62"), and the fourth-batch option (**142 / 86**) | a projection shipped where a measurement existed. All three are now computed at run time or recomputed here | §7, §12.8, §14.3, §14.5, `analyze_g2.py` (`guidance_base_caveat()`, `ceiling_realized_n()`) |
| 6 | `appendix_non_decisional_bars` prints only `k*` and the `p̂` it implies at the non-ratified bar | `p̂` and the Wilson interval do not depend on the bar, so the block was byte-identical to the ratified bar's numbers — zero information, and a second surface that read like a result at an un-ratified bar | `analyze_g2.py`, report §1 |
| 7 | §11.3's failed-batch record gets a writable home: `failed_batches.json`, enumerated causes hard-checked, surfaced in report §0 | it pointed at `draw_manifest.json`, which only `build_draw_g2.py` writes and which must not be re-run after the draw — so a re-run cause would have been recorded nowhere | §11.3, `analyze_g2.py` |
| 8 | two ceiling caveats disclosed: replicates are **identically ordered**, so the ceiling is **upper-biased**; and the adjudicator sees which candidate is the incumbent (`stored_label`), which biases adjudications toward *agree* | both push measured agreement **up**, the same direction as §12.1's shared-family bias, so they do not offset it | §5.4, §12.10, §12.11, `_s_noise` note, `build_adjudicator_batches_g2.py` docstring. The adjudicator key set is **pinned** by §10.2.2, so closing that one is an owner call and it is disclosed, not silently changed |
| 9 | deleted: `simulate_cik_coverage()` (a 200-replicate Monte Carlo no decision, assertion, estimator or report line read) and the dead `--provisional` flag | lazy-elite: machinery the task did not need | `build_draw_g2.py`. Its RNG stream **name is retained as reserved** — a `SeedSequence` child is identified by position, so dropping the name would shift every `G-A-quota` stream and silently re-draw the quota |

**One red-team claim did not reproduce and is recorded as not-adopted.** The
review stated that at the realized n = 110 the sentiment ceiling's lower bound
at p̂ = 0.90 is `0.8300`, so §14.5's "misses the 0.83 separation criterion by
0.001" *"flips sign"*. Recomputed with this design's own pinned primitive
(§10.0 Wilson, z = 1.96 exactly): the lower bound is **0.82976**, still below
0.83, by 0.0002. The claim's direction is wrong but its substance holds — the
miss is now a rounding artefact away from a tie — so §14.5 states the recomputed
figure and instructs that this endpoint be quoted to 4 decimal places, never as
the 3-dp "0.830".

**Not done, deliberately.** No new secondary, no new estimator, no new arm, no
change to any bar, n, seed, weight, applicability rule or omission convention.
`red_flags` remains exploratory / disclosure-only; `distress_tier` remains
unscored; 8K_BODY remains excluded.
