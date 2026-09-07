# EXPANSION_PLAN — the E2 experiment

**Written 2026-08-20.** This is the working spec for the expanded
experiment ("E2") the owner ratified in chat on 2026-08-20. It is
maintained alongside `HANDOFF.md` (whose §3 decision log holds the
ratifications) and `ROADMAP.md`. The original 25-company study is "E1"
throughout. Raw recon behind every number here:
`data/expansion_recon_2026-08-20.json` (four-agent workflow
`wf_193acdfb-490`, 2026-08-20 — coupling audit / universe design /
labeling feasibility / statistical power).

---

## 1. What was ratified (owner, in chat, 2026-08-20, via explicit option selection)

1. **Direction:** after reading `data/diagnosis_report.md` (E1 verdict: no
   fold-robust text signal), the owner chose — verbatim — *"I want to do a
   bigger experiment. Please help me expand, so that fine-tuning may be an
   option in the future."*
2. **Scope: 100 companies × 10 years** (the maximal recon config).
   ~26 quarterly test folds; window back to ~2016 (exact dates fixed in
   §4's pre-registration gate).
   **AMENDED 2026-08-21 (owner, in chat) → hybrid136, a two-stratum
   universe:** the owner ruled "do both" between deep-5 and whole-market —
   **core stratum** = the 5 E1 sectors at K=20 (identical to continuity5),
   **extension stratum** = industrials, utilities (incl. telecom),
   materials_realestate at K=12 → **136 members per reconstitution date**,
   every membership row tagged `core`/`extension`. Bound analysis rule:
   the primary confirmatory analysis runs on the CORE stratum (the
   labeler's training distribution); the extension arm is a pooled +
   stratified secondary, promoted only if gate G2's sector-stratified
   spot-check shows label quality holds in the unseen sectors. Labeling
   cost grows ~36% (~98k new chunks; ~11–16 worst-case overnights, $0).
3. **Universe rule: sector-stratified top-K by `dei:EntityPublicFloat`,
   with ANNUAL point-in-time reconstitution** (Russell-style). Membership
   at each annual reconstitution date is computed using only filings
   public before that date. `universe.csv` becomes a dated membership
   table: `(ticker, cik, sector, member_from, member_to)` + `stratum`.
   Residual float mis-scalings that survive the within-registrant
   sanitizer (e.g. the MedEquities $316.7B artifact) are handled by a
   verified, documented manual-exclusion file — never silent drops.
4. **No mid-cap arm this round.** Large-cap only — the hybrid's extension
   stratum broadens SECTOR coverage, not the cap range. (A mid-cap arm
   remains a possible later addition; see §7.)
5. **Fine-tune: LAUNCHED.** The owner gave the explicit "launch, 1 epoch
   first" go. This satisfies the standing rule that the fine-tune needs
   the owner's explicit in-chat go. Discipline: implement → timed probe →
   smoke test → 1 epoch → held-out eval → owner reviews before more
   epochs.

**Non-goals are unchanged and unconditional** (`HANDOFF.md` §1): no
trading, no investment advice, no live capital, every number reported with
its measurement. E2 inherits all of E1's hard rules (`HANDOFF.md` §7),
including: no Anthropic API spend ever (the fine-tuned local model is the
only labeler), GPU rental not pre-approved, model verdicts never recorded
as the owner's.

---

## 2. Why this design (recon summary)

### 2a. Power — the reason E2 exists

E1's design (25 companies × 6 folds) has a minimum detectable effect
(~95%/80%) of **~0.077 cross-fold mean IC delta — larger than any text
delta ever observed in the data**. E1's null was near-inevitable at that
power. Key structural finding: the observed fold-to-fold delta noise
(std 0.0677 at n≈40/fold) is fully consistent with pure sampling noise at
model-model correlation ~0.92, but a market-regime variance floor cannot
be ruled out — and a floor is divided down only by **more test quarters**,
not more companies. Hence the ratified config expands BOTH axes:

| Config | MDE (optimistic–pessimistic bracket) |
|---|---|
| 25 co × 6 folds (E1) | 0.077 |
| 100 co × 6 folds | 0.039–0.077 (may buy nothing) |
| 25 co × 26 folds | ~0.037 |
| **100 co × 26 folds (E2, ratified)** | **0.019–0.037** |

> ⚠️ **The 0.019–0.037 bracket and the ±0.013–0.027 null bound below are
> SUPERSEDED.** They are left in place unaltered as the record of what was
> ratified on 2026-08-20. Read the dated amendment at the end of this §2a
> ("AMENDMENT 2026-08-25 — honest MDE restatement") before quoting any
> number from this section.

At E2's power, even a null is a meaningful result: it bounds the true
dedup IC delta within roughly ±0.013–0.027, supporting "no text-vs-numeric
improvement of economically relevant size (|δ| ≳ 0.03) exists in this
universe." That is the pre-committed acceptable outcome, restated for E2.

Caveats that stay attached to every E2 power claim: fold non-independence
makes every MDE a lower bound; the noise anchor was estimated on
2025–2026 mega-cap folds and may not transfer to 2016-era folds; per-family
MDEs scale ~0.4×–2.4× around the full-model numbers.

---

#### AMENDMENT 2026-08-25 — honest MDE restatement (H2, phase F2.5)

*APPENDED, NOT A REWRITE. Everything above this line is the 2026-08-20
record and is left byte-intact. Source: the H2 hardening item
(`HARDENING_PROGRESS.md`), specified by
`data/reevaluation_2026-08-25/methodology_audit.md` §(a) defects 1–4 and
§(e) E2. Every number below was **re-derived from frozen artifacts**, not
copied from the audit: generator `backtest.py` at `spec.py`'s
pre-registered specification, artifact
`data/hardening/backtest_report_2026-08-25_H2.md`. The re-derivation
reproduces E1's published per-fold dedup deltas exactly
(−0.1275, −0.0078, −0.0399, 0.0183, −0.0004, 0.0992), so the disagreements
below are about method, not arithmetic. `data/backtest_report.md` and
`data/diagnosis_report.md` — the go/no-go record — were not touched.*

**Why the published bracket was optimistic.** Four corrections, three of
them tightening against E2:

1. **ddof.** The published anchor 0.0677 was a *population* std over six
   fold deltas (`diagnose.py:222`, `backtest.py:513/689/693/781`, all now
   ddof=1). The sample std is **0.0742** — every published MDE inherited a
   √(5/6) = 0.913 optimism.
2. **The anchor's own sampling error was never carried.** 5 degrees of
   freedom: 95% chi-square CI **[0.0463, 0.1819]**, a 3.9× range.
3. **The anchor is measurable far better than by six numbers.** The
   within-fold bootstrap (predictions held fixed, dedup test rows resampled,
   4,000×/fold) gives a per-fold SD of **0.1046** (mean) / **0.1154**
   (RMS) at n_dd ≈ 39.5 — ~1.5× the published anchor.
4. **The feature specification changes the answer**, and it is now
   pre-registered (`spec.py`; PRIMARY = PIT trailing cross-sectional
   percentile ranks, SECONDARY = raw levels, both always reported).

**Correction to the audit's "defect 4 is good news".** The audit concluded
that the bootstrap resolves recon caveat (1) — the regime-variance floor —
in E2's favour (implied floor = 0, so more companies buy power). That
holds **only under raw levels**. Re-derived on the same folds:

| specification | cross-fold sample std (ddof=1) | bootstrap SD (mean / RMS) | implied floor | chi-square p |
|---|---|---|---|---|
| `raw_levels` (secondary) | 0.0742 [CI 0.046, 0.182] | 0.1046 / 0.1154 | **0.0000** | p(spread<sampling)=0.16 |
| `pit_trailing_rank` (**PRIMARY**) | 0.1549 [CI 0.097, 0.380] | 0.1149 / 0.1190 | **0.0992** | p(spread>sampling)=0.13 |

Neither tail is close to significant at 5 df. **The floor is unidentified
at 6 folds in both directions**: a measured 0.0000 does not establish its
absence and a measured 0.0992 does not establish its presence. Recon
caveat (1) therefore stands, and the honest E2 bracket must carry the
floor endpoint.

**The honest MDE** (2.8 × SE; two-sided 5%, 80% power; E2 core stratum =
100 companies → n_dd ≈ 158 at E1's measured 1.58 dedup rows/company/fold;
26 test folds; ρ_f = 0.3 applied as the finite-k AR(1) inflation
1 + 2Σ(1−l/k)ρ^l = 1.810, SE ×1.345):

| specification | branch | SE(mean δ) | **MDE** | 95% null bound |
|---|---|---|---|---|
| `raw_levels` | floor-free, ρ_f=0 | 0.0103 | **0.029** | ±0.020 |
| `raw_levels` | floor-free, ρ_f=0.3 | 0.0138 | **0.039** | ±0.027 |
| **`pit_trailing_rank`** | floor-free, ρ_f=0 | 0.0113 | **0.032** | ±0.022 |
| **`pit_trailing_rank`** | floor-free, ρ_f=0.3 | 0.0152 | **0.043** | ±0.030 |
| **`pit_trailing_rank`** | implied floor, ρ_f=0 | 0.0225 | **0.063** | ±0.044 |
| **`pit_trailing_rank`** | implied floor, ρ_f=0.3 | 0.0303 | **0.085** | ±0.059 |

In **true-construct (noise-free-label) units**, dividing by the labeler
reliability λ ≈ 0.8 from `methodology_audit.md` §(b) (λ ≈ 0.6–0.7 where
sections are short, which would be worse still): **0.036 → 0.107**.

| quantity | published §2a (2026-08-20) | honest restatement (2026-08-25) |
|---|---|---|
| MDE, E2 (100co × 26 folds) | 0.019–0.037 | **0.029–0.085 measured** (0.032–0.085 under the PRIMARY spec) |
| same, true-construct units | not stated | **0.036–0.107** |
| null bound on \|δ\| | ±0.013–0.027 | **±0.020 → ±0.059** |

Two minor items, for completeness: at k = 26 a t-correction raises the
multiplier from 2.802 to 2.916 (+4%, folded into none of the above — add it
if you want the conservative read). And 41 member-window quarters exist, so
a shorter burn-in buys up to ~35 folds and multiplies every MDE above by
0.86; pooling the extension stratum (136 vs 100 members) multiplies the
**sampling** component by 0.86 and the floor component by 1.00.

**The pre-committed claim's SCOPE was wrong, and is corrected here.**
Published: *"no text-vs-numeric IC improvement of economically relevant
size (|δ| ≳ 0.03) exists in this universe."* That is a claim about text.
What E2 can support is a claim about this pipeline:

> **"No text-vs-numeric IC improvement of economically relevant size is
> detectable in this universe through this labeling schema, these 22
> features, this labeler, and this feature specification."**

The four qualifiers are load-bearing, not hedging: the schema is a ~20-bit
bottleneck, the red-flag features are 52–76% structurally absent, the
student sits at its teacher's reproducibility ceiling, and the
specification itself moves the E1 headline (see below).

**Named equivalence procedure (was missing; a bounded null is not "we
failed to reject").** Pre-registered at G3:

- **Test:** TOST (two one-sided tests) at α = 0.05 on the cross-fold mean
  dedup IC delta, against an equivalence margin ±Δ fixed at G3.
- **Decision rule, equivalently stated:** declare equivalence iff the
  **90% CI** (mean ± 1.645·SE, the TOST-equivalent interval) lies entirely
  inside ±Δ. Report the interval always — including when equivalence fails
  — never a bare "no significant effect."
- **SE estimator:** block bootstrap over folds (moving block, length set
  from the *measured* lag-1 autocorrelation of fold deltas — measurable for
  the first time at 26 folds) or Newey–West; **never** std/√k, which is the
  quantity every number above had to assume.
- **Power requirement, stated up front:** a TOST at margin Δ with 80% power
  needs **SE ≤ Δ/(z₀.₉₅+z₀.₈₀) = Δ/2.487**. At Δ = 0.03 that is
  **SE ≤ 0.0121**. E2's achievable SE spans 0.0103–0.0303 across the
  branches above, so **Δ = 0.03 is powered only in the floor-free,
  independent-folds corner**; Δ = 0.05 (SE ≤ 0.0201) is met in every
  floor-free branch of both specifications.
- **If the rank-spec floor is real, no company count fixes it**: the floor
  divides only by folds, so a Δ = 0.03 TOST would need **k ≥ 68 folds**
  (ρ_f = 0) or **k ≥ 125** (ρ_f = 0.3) — 17 to 31 years of quarters. E2's
  26 folds cannot deliver it. Choosing Δ after seeing the realized SE is a
  post-hoc design choice and is prohibited; the responses to each outcome
  are H5's stopping rule, ratified before results exist.

**New finding this amendment adds (not in the recon and not in the audit):
implementation sensitivity dominates specification sensitivity.** Seven
mutually-defensible, all look-ahead-free implementations of the *same named*
transform ("PIT trailing cross-sectional percentile ranks, 180-day
window") — differing only in subject inclusion, same-day-peer inclusion,
last-per-ticker vs. every-row comparison sets, and the 581-row vs. 630-row
ranking cross-section — move E1's headline dedup delta across
**[−0.0172, +0.0422]** (range **0.059**, ~2× the honest MDE) and the
cross-fold std across [0.0496, 0.1549] (3.1×). The audit's own headline
+0.0467 is an eighth variant whose stated recipe could not be reproduced
exactly (it is closest to the `include_same_day=False` arm, +0.0422);
including it widens the span to 0.064. The two pinned implementations in
`spec.py` differ from each
other by only 0.0004, which is **not** reassurance — it is the reason G3
must pre-register **a function and its arguments**, not a transform's name.

**Caveats that still stay attached to every E2 power claim** (unchanged,
plus one): fold non-independence makes every MDE a lower bound; the anchor
was estimated on 2025–2026 mega-cap folds and may not transfer to 2016-era
folds; per-family MDEs scale ~0.4×–2.4×; **and every number above is
conditional on the pre-registered feature specification, whose
implementation must be pinned at G3 before any E2 IC exists.**

---

### 2b. Feasibility — measured/verified in recon

- **Local labeling is NOT the binding constraint.** ~70k new chunks at a
  reasoned ~950 chunks/h single-stream on the M5 (verified against
  Apple's own M5/MLX study; base-M5 MacBook Pro 14", actively cooled) ≈
  56–117 h ≈ **8–9 overnights**, compressing to ~1.5–2 days with the free
  mlx_lm prefix-cache + batching levers. A 50-chunk on-box timed probe
  replaces these bands before any commitment (see gate G1).
- **EDGAR ingestion is cheap.** ~100 new companies × 10 yr ≈ low
  thousands of polite GETs, ~10–25 GB raw, hours of network time. The
  frames API (`dei/EntityPublicFloat`, quarterly instants) was verified
  live to enumerate delisted registrants (BBBY present in CY2022Q3I) —
  survivorship-free *selection* is real, with zero price data needed.
- **The real costs** are extraction QA on ~11× the text (new filer HTML
  dialects — E1's extract.py calibrations are all fit on 25 mega-caps'
  2023–2026 filings) and the label-quality measurement for the new
  labeler (§4, gate G2).

### 2c. Survivorship honesty — what E2 fixes and what it cannot

- FIXED (selection side): membership decided per reconstitution date from
  pre-date filings only; declining companies stay in-sample until they
  stop filing. The tempting "continuous filing across the window" rule is
  look-ahead and is REJECTED explicitly.
- NOT FULLY FIXABLE (outcome side): Yahoo (the only working free price
  source) generally has no data for delisted tickers, so forward returns
  right-censor at delisting — informative censoring. Mitigations, all
  mandatory: report the count of selected CIKs excluded solely for missing
  prices (never silently drop); ingest EDGAR-native distress outcomes
  (8-K Item 1.03 bankruptcy, Form 25 delisting, Form 15 deregistration)
  as flags so censored names are visible; carry the residual bias into
  the E2 limitations doc. Sector labels come from current SIC codes — a
  small, stated look-ahead confined to the sector *label*, not membership.

---

## 3. Standing design rulings for the build

These were identified by the recon as decisions that must be made
deliberately, not discovered by crash. Rulings below are the working plan;
items marked **[OWNER-GATE]** get an explicit owner sign-off at the gate
noted in §4 before they take effect.

1. **Full corpus rebuild + relabel everything with the fine-tuned model.**
   chunk_ids are content-derived and do not survive corpus growth (homes
   are earliest-occurrence, boilerplate is shared across companies), so
   E2 rebuilds chunking over the full expanded corpus and the fine-tuned
   model labels ALL chunks — including re-labeling E1's 6,746 (~+5–11 h).
   This removes the two-labeler covariate that would otherwise be
   confounded exactly with the old-vs-new axis. E1's artifacts
   (`labels.parquet`, the finetune split, spot-check record) stay frozen
   as the training/eval/audit record — they are no longer the feature
   pipeline's input in E2.
2. **Labeler-contamination provenance flag.** The fine-tuned model was
   trained on E1 text; recurring boilerplate means it will effectively
   replay memorized labels on E1-era chunks and generalize on new ones.
   Every E2 chunk gets a provenance flag (train-overlap vs novel, via
   paragraph/accession overlap against the training split), and the E2
   analysis reports key results with and without the overlap set.
3. **Benchmark redefinition [OWNER-GATE G3].** The excess-return target's
   universe-average benchmark must be re-ratified for a 100-name churning
   universe: proposal = equal-weighted average over that date's members
   EXCLUDING self, with membership-dated constituents. All E2 targets are
   regenerated; E1 and E2 backtest numbers are declared numerically
   incomparable (different benchmark), stated wherever both appear.
4. **Fold structure pre-registered [OWNER-GATE G3].** `backtest.py`'s
   burn-in is a fixed calendar date today — extending the window backward
   adds ZERO test folds unless it is deliberately moved. The E2 fold
   structure (burn-in length, first test quarter, expected ~26 folds) is
   fixed and logged BEFORE the first E2 backtest run, so the fold split is
   never chosen after seeing results.
5. **Fundamentals ingestion goes systematic.** The hand-curated 13-concept
   list + per-ticker alt-tag maps do not scale to 100 names. E2 re-ingests
   with a broadened concept set (adding `ProfitLoss`, `CashAndDueFromBanks`,
   restricted-cash and NCI-equity variants — closing HANDOFF §2a trap (b))
   and an automated alias/migration classifier whose UNRESOLVED cases fail
   loudly per (company, concept) instead of resolving stale. Concentrated
   per-sector missingness is a blocker, not a footnote.
6. **Validation gates get per-company windows.** `validate_universe()`'s
   FATALs assume currently-active, always-filing companies. With a dated
   membership table, each company validates against its own
   `[member_from, member_to]` (IPO-late entry and delisting exits are
   expected states, not FATALs). No blanket `--allow-incomplete-universe`
   overrides — the per-check-only override design flaw gets fixed, not
   worked around.
7. **A new-labeler quality measurement replaces the old caveats.** The
   36.6%/63.4% red-flag error constants baked into report generators were
   measured on the Claude bootstrap labels; carrying them onto Qwen labels
   would be silent misinformation. E2 runs its own spot-check
   (auditor-style, over a stratified sample of Qwen labels) and regenerates
   every caveat constant from it. **[OWNER-GATE G2 sets the bar.]**
8. **Frozen-split asserts become derive-and-report.** The exactly-1
   parse-failure asserts in `split.py`/`check_leakage.py`, the corpus-pinned
   test tripwires (6 folds, [52,52,52,52,53,46], len(universe)==25, …), and
   the hand-typed per-ticker caveat strings in `features.py` are re-derived
   from the new corpus — tripwires re-pinned, never deleted.

---

## 4. Execution phases and gates

Phases run in order; parallelism within a phase is fine. Every gate is a
stop: the next phase does not start until the gate's condition is met.

- **F0 — Fine-tune + eval (ACTIVE, launched 2026-08-20).**
  Implement real MLX QLoRA path → timed probe → smoke → 1 epoch →
  `eval.py` real path against the frozen 1,010-row eval split.
  **Gate G1 (owner):** owner reviews the held-out eval (per-category
  precision/recall/F1, distress excluded per standing rule) and the
  measured labeling throughput probe, then rules whether the student is
  good enough to be E2's labeler (and whether to train more epochs).
  Proposed floor for "good enough," subject to the owner's ruling:
  sentiment and guidance ≥ ~0.90 exact-match on eval; red-flags reported
  against the teacher's own noise level rather than an absolute bar.
- **F1 — Universe construction.** Frames-API enumeration (4-quarter union
  + per-CIK patch pass), SIC→sector mapping, top-K per sector per annual
  reconstitution date, dated membership table, CIK diligence per the XOM
  lesson, delisted-ticker price-availability census (count and report).
  **Gate G2 is scheduled here in calendar terms but belongs to labels**
  (see F4).
- **F2 — Ingestion at scale.** Metadata + documents + fundamentals
  (systematic concept strategy, §3.5) + prices for all members;
  per-company-window validation (§3.6); window-relative recalibration of
  filing-gap/coverage thresholds. Yahoo-volume provenance caveat restated
  for owner visibility.
- **F3 — Extraction + QA.** Run extract.py over the expanded corpus;
  mandatory QA: triage every failure/low-confidence/length-floor flag by
  filer, manual spot-read sample (~30–50 sections) weighted toward new
  filers and pre-2019 filings; recalibrate word-count floors and the stub
  ceiling from the new distribution; expect new per-filer edge handlers.
- **F4 — Chunk + label.** Full re-chunk (new chunk_ids, new occurrence
  map, no-backward-flow verification re-run); label ALL chunks with the
  fine-tuned model (checkpointed overnight runs; prefix-cache + batching
  levers first); provenance flags per §3.2.
  **Gate G2 (owner):** E2 spot-check of the Qwen labels (new stratified
  sample, auditor protocol) — owner reviews the measured agreement rates
  and rules that labeling quality is sufficient to proceed to features.
- **F5 — Features + backtest, pre-registered.**
  **Gate G3 (owner, BEFORE running):** ratify the benchmark definition
  (§3.3), the fold structure (§3.4), and the primary metric (dedup IC
  delta, form-controlled ablation as the honest secondary) — logged in
  HANDOFF §3. Then build features (systematic alt-tags, staleness sweep
  re-justified), run the walk-forward, regenerate all report prose from
  run diagnostics.
- **F6 — Diagnosis + red-team + docs.** E2 diagnosis rerun of the E1
  analyses at the new power; independent red-team pass over F1–F5 output
  (look-ahead, survivorship, overfitting, overstated claims); model card
  and LIMITATIONS updated to cover E1 (complete) + E2, including the
  censoring residual (§2c) and labeler-quality measurement (G2).
  **Gate G4 (owner):** final read.

---

## 5. Coupling workplan (from the audit — condensed)

Full detail with file:line refs in `data/expansion_recon_2026-08-20.json`
(`coupling.items`, 32 entries). By phase:

**F1/F2 (ingestion):** universe.csv → dated membership schema; 20–30
universe-size bound removed deliberately; window → fixed dates (not
trailing-from-today), floors derived from window length; per-(company,
check) validation exceptions; filing-gap/staleness thresholds recalibrated;
EX-99 selection audited per new filer; fundamentals CONCEPTS broadened +
alias classifier; `CORPUS_WINDOW_*` literals → derived; migration map
re-derived for the new window; frames/companyfacts/submissions fetches
cached under `data/raw/` as today.

**F3 (extraction):** anchor-TOC coverage degrades pre-~2010 (E2's 2016
floor is safely inside the modern era, but 2016–2019 pre-iXBRL filings
still need the QA sample); MIN_SECTION_WORDS / MDA_STUB_WORD_CEILING
recalibration; expect new TOC dialects.

**F4 (chunk/label):** chunk_id identity break (full rebuild per §3.1);
occurrence arrays regenerated over the union corpus; Qwen labels.parquet
writer reproduces the existing schema exactly (parse_ok/schema_valid,
enum values, occurrence arrays; no single-refusal assumptions;
distress_tier emitted empty — the student never predicts it);
APPLICABILITY extended only deliberately.

**F5 (features/backtest):** accession→company map keyed by CIK (breaks on
shared-CIK dual-class otherwise); benchmark + targets regenerated
[G3]; BURN_IN_END → derived quarter count [G3]; dedup-gap and
form-ablation empirical justifications re-derived on the new frame; LOCO
compute budgeted or sampled (100 tickers × 26 folds ≫ 150 refits);
caveat constants regenerated from data [G2]; report prose regenerated
from diagnostics.

**Tests:** every corpus tripwire re-pinned to verified new values
(fold sizes, universe size, sector set, staleness guard firing set,
exactly-1-parse-failure asserts → derive-and-report).

---

## 6. Cost summary (owner-facing, honest)

- **Cash:** $0 planned. No Anthropic API (hard rule). EDGAR + existing
  free price endpoint only. GPU rental stays not-pre-approved; the recon
  priced an inference-only rental at ~$1–10 total if ever wanted — it
  would need its own explicit sign-off and an MLX→PEFT adapter
  conversion, and is NOT part of this plan.
- **Owner's machine:** fine-tune ~1 epoch (measured estimate replaces the
  5–13 h paper band after the probe; overnight, checkpointed); labeling
  ~8–9 overnights at worst for the full corpus (less with the free
  levers); all resumable — a crashed night loses nothing.
- **Wall-clock elephant:** extraction/QA and the systematic fundamentals
  work are the real effort sinks, not compute.
- **Provenance exposure:** Yahoo price fetches scale ~4× (100 tickers);
  the existing robots.txt/ToS caveat (`data/PRICES_NOTES.md` §1) grows
  with volume and is restated for the owner at F2.

---

## 7. Explicitly out of scope this round

- Mid-cap arm (owner ruled no; revisit only after E2's F6 read).
- Any re-label of E1's frozen `labels.parquet` by the API (impossible —
  spend freeze) or any change to the frozen fine-tune split (it remains
  the model-eval artifact).
- Rubric v1.2 ratification (still pending from E1 Phase B; if the owner
  ever ratifies it, the sync rule applies and the fine-tune's training
  data does NOT change retroactively — a ratified v1.2 would only govern
  a future re-train, not this one).
- dividend-adjusted returns, universe weighting schemes beyond equal
  weight, and any live/paper trading (charter, unconditional).

---

## 8. AMENDMENT 2026-08-25 — post-re-evaluation rulings (owner, in chat)

Source: `REEVALUATION_2026-08-25.md` (four-lens panel) and the owner's
four explicit rulings (HANDOFF §3, 2026-08-25 second entry). These
amend §4's phase plan:

1. **New phase F2.5 — HARDENING (inserted before F3, ratified in
   full).** Ledger: `HARDENING_PROGRESS.md`. Items: H1 positive
   controls (known-effect recovery in this exact harness); H2
   specification pre-registration (PIT cross-sectional ranks primary,
   raw secondary; standing zero-information benchmark rows; ddof fix;
   bootstrap noise anchor; honest MDE restatement of §2a); H3 labeler
   attenuation check (student relabels E1's 6,746 chunks, E1 backtest
   re-run); H4 document-selection Tier-C error sample; H5 stopping rule
   (pre-committed responses to all three E2 outcomes incl. the
   ambiguous branch and an explicit E3 policy — drafted by
   tech-council, ratified by the owner at/before G3); H6 prior-work
   positioning section. **F3 does not start until F2.5 completes.**
2. **Gate G1 is HELD** pending H3 — supersedes "conditional on the
   epoch-2 re-eval" (the re-eval is read; the floor is failed on
   sentiment; the ruling now waits on measured attenuation).
3. **F4 scope: extension-stratum labeling DEFERRED until after gate
   G2.** Core stratum labels first; the extension arm is labeled only
   if G2 promotes it. (Its data stays ingested; deferral is free.)
   *Owner ruling 2026-09-07 (HANDOFF §3): G2 ruled "proceed under the
   ladder"; extension labeling RULED "extend" — run after the wrapper lock
   fix; the extension arm is promoted into F5 only after its own
   spot-check on the unseen sectors (G2 measured core only).*
   F4's chunk-count and window (member-spell+margin vs full-window) are
   re-derived from F3's actual output before any overnight is
   committed (decision-audit lens: plan's count is low 1.2–2.1×).
4. **F5 features: two zero-labeling text families added** —
   year-over-year filing-change/novelty (Item 1A / Item 7 similarity)
   and pooled document embeddings — plus momentum, realized volatility,
   and a valuation ratio in the numeric baseline. §3's feature plan is
   amended accordingly; G3 pre-registers the transformation (ranks
   primary) before any E2 IC exists.
5. **F5 runs THREE heads:** the pre-registered return target; a
   volatility/informativeness event study over the ~5,552 in-membership
   earnings events; exit prediction over the 86 exit-CIKs (M&A vs
   distress separated from stored 8-K items). Each head's conventions
   land in the G3 pre-registration document.
6. **Identity ruling** (HANDOFF §3 verbatim): research +
   pipeline-as-asset; the owner's analysis-app vision is a post-E2
   direction, charter-bounded (analysis yes, advice/execution never,
   distribution requires re-ratification).
