# F5 PLAN — features + walk-forward backtest, pre-registered (written 2026-09-07 evening; red-team fix pass applied the same night)

**Status: Step 1a and 1b DONE 2026-09-10/11; Step 2 (census) in progress. Owner ruled 2026-09-11 (HANDOFF §3): the personal filing-reading aid is built NOW in parallel (app lane, ledger `data/app/status/`), E2 closes as ratified, and the G3 ruling is due within 14 days of the packet. Gate G2 was ruled "proceed under the
ladder" and ruling 2(b) "extend" on 2026-09-07 (HANDOFF §3). This file is the
execution order for F5 and the list of decisions the owner rules at G3, as far
as the record names them; `EXPANSION_PLAN.md` §4 governs any residue.**

Sources this plan is bound by (every item below traces to one of them):
`EXPANSION_PLAN.md` §3–§5, §8 · `data/hardening/status/H2_spec.md` (the
pre-registered specification — the artifact G3 ratifies) ·
`data/hardening/status/H5_stopping_rule.md` (the ratified stopping rule; its §6
skeleton is the council's draft until the owner rules each row) ·
`data/hardening/status/H3v2_attenuation.md` §3.8 ·
`data/hardening/status/G1_council_advisory.md` §6–§7 ·
`data/f4/g2/G2_SPOTCHECK_design.md` §2.5, §3.4, §6.5 · `data/f4/g2/G2_FINAL_REPORT.md`
· `data/f4/status/F4_campaign.md` · `data/hardening/spotcheck_v12/OWNER_POLICY_RULINGS.md` (the v1.2 teacher spot-check) · `data/hardening/status/H1_controls.md` · `data/F2_INGESTION_REPORT.md` §0(c) ·
`data/f3/status/P4_redteam.md` §5.1, §11 ·
`data/reevaluation_2026-08-25/methodology_audit.md` §(c) · HANDOFF §3 entries
2026-08-25 (rulings a–d), 2026-08-26, 2026-08-27, 2026-09-07.

---

## 0. What F5 is, in one paragraph

F5 turns the 317,081 student-labeled core-stratum chunks into one row per
(company, filing) of text features, joins point-in-time numeric fundamentals and
prices for the 100-seat churning core universe (176 distinct core CIKs over the
decade), and runs a quarterly expanding walk-forward comparison of a
text+numeric screening score against a numeric-only baseline on a 63-trading-
session forward excess-return target. Three heads: (1) the pre-registered
return target — the only head that drives the stopping rule; (2) a
volatility/informativeness event study over the core-stratum earnings 8-Ks; (3)
exit prediction over core CIK-quarters. Every number ships with the G2 error
caveats and per-feature retention. It is research; nothing here is a trading
signal (charter, HANDOFF §1).

## 1. The one structural rule

**No session computes or reads any E2 information coefficient (IC) before the
G3 pre-registration document is instantiated, owner-ratified and sha-pinned**
(H5 §5 item 6 + §6 §0, ratified 2026-08-26). Any amendment made after the
first IC exists is labelled POST-HOC inside the document.

What the freeze binds, stated so Step 1 cannot trip it: any IC that involves an
E2 text feature — the head-1 estimand (text+numeric minus numeric-only), the
head-2 and head-3 predictors, and any feature-versus-outcome association in
census code. Proposed carve-out, **owner to confirm at G3 (decision 19)**
because KC6's ratified wording is "any E2 IC": reproducing the H1
positive-control ICs already published in `data/hardening/status/H1_controls.md`
as known-answer checks of the target/session plumbing (no text feature enters
them). Until confirmed, that check runs after ratification.

Enforcement, not convention: all three head runners refuse to fit anything
unless `data/f5/G3_RATIFIED.json` exists and its `doc_sha256` matches the sha
of `data/f5/G3_PREREGISTRATION.md` — the anti-shopping guard `analyze_g2.py`
uses for its bars. Each run appends to `data/f5/run_log.jsonl` keyed to that
sha, so a second run is visible.

## 2. Execution order

Lanes per the tiering policy: Fable plans/verifies, Opus executes
(`quant-modeler`, `research-statistician`, `test-engineer`,
`finetune-engineer`), red-team at every hand-off. $0 API throughout.

### Step 1 — Build the E2 stack (no text-feature ICs). Owner load: none.

New sibling modules; the E1 modules (`features.py`, `backtest.py`,
`diagnose.py`) stay byte-frozen as the E1 record with their tests. The G2 §3.4
blocker filed against `features.py` is discharged in `features_e2.py`;
`features.py:1159` stays because it is a true statement about E1's teacher
labels.

- `features_e2.py` — reads `data/f4/labels_e2_v1.parquet` + `chunks_v1.parquet`
  (sha-asserted against `data/f4/campaign_manifest.json`, the `controls.py`
  provenance pattern), `data/filings_metadata_e2.db` membership, `fundamentals_e2`
  via `pit.value_as_of` only, `prices_e2`. **CIK-keyed end to end** (E2 labels
  carry no ticker by design; the E1 accession→ticker map asserts 1:1 and would
  fail). Every-occurrence attribution from the baked `source_*` arrays
  (`source_ciks` is the ownership key; there is no E2 occurrence map — the
  arrays are the primitive, stated as such).
  - **Section masks (G2 §3.4):** null `sentiment` on RISK_FACTORS and
    `guidance_direction` on MDA / RISK_FACTORS before aggregation, with an
    assertion that the masked counts equal the census: 4,177 sentiment rows;
    2,826 guidance rows (2,803 MDA + 23 RISK_FACTORS), 230 of them active.
  - **`guidance_applicable` filter, explicit.** Nulls are nulls: branch on the
    stored columns, never on `schema_valid` (G2 design's implementer trap —
    `schema_valid == false` does not imply a null guidance value). The 23
    schema-invalid rows are a disclosure count: 17 guidance-enum nulls (all
    EX99, applicable, `guidance_imputed_none = false`), 4 red-flag-category and
    2 red-flag-modality pair drops; nothing is remapped. Imputed NONEs (48,790,
    51.18% of applicable) are NONE by the writer rule and are counted as such —
    disclosed, not hidden.
  - **Provenance flags materialized as columns:** `train_overlap` (G2 §2.5
    definition: home accession OR any source accession in the frozen v1.2
    training split OR normalized-exact text match; must reproduce 14,342 rows on
    the 316,291-row frame — an id-join gives 0 and is wrong) and `selfid`
    (company self-identification, 46.46%). Key results are reported with and
    without the overlap set.
  - Feature set = the 22 pre-registered text features (the 13 red-flag feature
    columns — 6 categories × 2 sections + the press any-rate — kept but
    **partitioned as exploratory**, never in the confirmatory set; G3 carries the
    demotion) + the two zero-labeling families (§8 item 4: YoY Item 1A / Item 7
    novelty; pooled document embeddings) + numeric baseline extended with
    momentum, realized volatility, one valuation ratio. Fundamentals resolution
    goes through the broadened concept set / alias classifier (§3 item 5), which
    fails loudly per (company, concept) — no hand-typed per-ticker alt-tags.
  - Excluded from features by construction: the non-PIT corpus columns
    (`reason_code`, `population_gate`, `quarter_cell_size`,
    `results_signature_present` and the gate verdicts — F3 P4 §5.1, §11 item 4)
    and 8K_BODY chunks (790; disposition ruled at G3).
  - Any non-USD fundamentals fact (today: 1 CAD float fact, Enbridge, and 13
    fundamentals series) converted to USD at an as-of dated rate — owner
    2026-08-25 ruling (d), verbatim: "Convert to USD as standard in future for
    all companies in case not USD"; source and semantics pinned at G3 §4
    (decision 7).
  - Caveat constants regenerated from the two measurements that replace the
    E1 36.6%/63.4% strings: teacher-side, the owner-ruled v1.2 spot-check
    (84/200 = 42.00% [35.37, 48.93], `data/hardening/spotcheck_v12/`); student-
    side, G2 (`results_g2.json`). The feature dictionary is generated from
    diagnostics, not hand-typed prose.
- `target_e2.py` — forward excess return over a **63-trading-session** window
  (the estimand's defining parameter, unchanged from E1) with the
  membership-dated **equal-weighted benchmark excluding self**, ported verbatim
  from `controls.py` (`load_membership`, `load_price_matrix`,
  `build_membership_matrix`, `align_membership`, `excess_return`); the window
  opens at the next trading open after `max(filing_date, acceptance_datetime)`
  (`controls.resolve_sessions`). The price snapshot is sha-pinned and named in
  G3 §12. Per-fold count of CIKs excluded
  solely for missing prices, always reported.
- `backtest_e2.py` (head 1) — the freeze guard (§1); folds derived from the
  pre-registered quarter list, never a hard-coded date; primary specification
  `spec.pit_trailing_rank_frame(window_days=180, min_comparators=2,
  include_same_day=True, ticker_col="cik", date_col="filing_date")` (the E2
  frame is CIK-keyed; the default `ticker_col="ticker"` would be wrong) and
  secondary `raw_levels`, always as a pair, with
  `include_same_day=False` as a named sensitivity arm reported beside them;
  primary metric = dedup Spearman IC delta, with the form-controlled ablation as
  the honest secondary and dedup + raw both reported; the two standing
  zero-information rows (size-only rank, CIK-training-mean rank), H1's
  E2-measured zero-information noise floor (|IC| ≈ 0.047–0.049,
  `H1_controls.md` recommendation 4) and the within-fold bootstrap anchor
  (4,000 resamples/fold, both tails) beside every IC; SE by block bootstrap over folds (block from the measured lag-1
  autocorrelation) or Newey–West, never std/√k; **the margin procedure
  (decision 15) executes inside the runner in one non-interactive invocation,
  and Δ with its inputs is written to the results JSON before any per-fold delta
  is serialized or printed** — Δ is a deterministic pre-registered function of
  the per-fold deltas; the guarantee is that no human reads a delta before Δ is
  fixed; TOST at α = 0.05 with the 90% CI always shown; censoring arm = full
  window primary + post-2019 sub-window, side by side; results with/without
  `train_overlap`; stable sort pinned, primary seed = 0, nuisance band = seeds
  1–100 beside the primary; LOCO per decision 14; per-fold tables, never one
  number. `spec.py` is pure and reused; its identification ICCs are re-measured
  on E2.
- Heads 2 and 3 as separate small runners sharing the target/session code and
  the same freeze guard.
- **Tests (test-engineer):** an E2 leakage suite that enforces the FATAL-class
  conventions as tests, not prose — C1 acceptance dating, C2 as-of joins only
  (assertion over `fundamentals_e2.parquet`: 7.3% of groups are multi-valued),
  no backward flow at 317,081 rows, mask census, applicable filter, non-PIT
  columns absent, freeze guard refuses without ratification. Corpus tripwires
  re-pinned, never deleted (`test_diagnose.py:77-79` fold sizes, `:199-200`
  universe 25 / 5 sectors, `:135/:262` the 13 red-flag feature columns,
  `test_phase_c_leakage.py` artifact paths).
- **Known-answer checks:** the E1 path still reproduces H2's pinned numbers
  (standing rows 0.2240 / 0.1868, six folds [52, 52, 52, 52, 53, 46]); the E2
  target/session code reproduces `controls.py`'s published T1 announcement-
  window result on the same events (the §1 carve-out). Red-team pass before
  Step 3.

Definition of done: E2 feature table + target on disk (sha-pinned, excluded
from git), leakage suite green, full suite green, red-team FIX-list closed,
**zero text-feature ICs computed**.

### Step 2 — Pre-run census (allowed before G3; no text-feature ICs). Owner load: none.

`research-statistician` writes `data/f5/census_e2.json` + a short markdown,
filling the G3 table's "measured population" column:

- usable core CIKs per quarter over the full span (measured so far only for
  2019Q1–2026Q2: mean 96.1, min 84); the span is 40 complete quarters
  2016Q3–2026Q2 (41 including the partial 2026Q3);
- **per-fold target completeness** under the 63-session horizon against the
  sha-pinned price snapshot (`prices_e2` currently ends 2026-08-24), which fixes
  the last test quarter before any IC exists;
- dedup rows per company per fold (plan assumed 1.58 → n_dd ≈ 158) and the
  dedup-gap / form-ablation counts re-derived on the E2 frame (the GAP_DAYS=5
  justification was measured on 630 E1 rows);
- label-purge census at E2 (E1: 12.9% of training labels resolve inside their
  test quarter);
- price censoring, already measured on the E2 member-date panel at F2
  (`F2_INGESTION_REPORT` §0(c): 14.0 / 16.2 / 12.5% of the 2016 / 2017 / 2018
  reconstitution cohorts, 95 of 1,496 member-date cells = 6.35% pooled,
  energy 16.4%) — the census adds the genuinely unmeasured part: the per-fold
  count of CIKs excluded solely for missing prices;
- **the MDE bracket re-derived at the ratified fold count and the measured
  per-fold n_dd, for the primary and the post-2019 arm** (every published MDE
  was computed at k = 26; `decision_audit.md` records that the bracket was
  never re-derived against measured coverage); pure 1/√k rescaling is an upper
  bound on the gain because early folds run on ~84–88 names;
- core-stratum counts for heads 2 and 3 (the published 5,552 events are
  union-universe over the 211 CIKs with price coverage, 5,903 over 242 before
  the price filter; the 86 exit-CIKs are over all 244; F5 has labels for the
  176-CIK core only), with per-fold exit prevalence;
- train-overlap and selfid counts, mask census, WITHDRAWN n = 66, GLD, 8K_BODY
  790, the E2 ICCs for the raw-levels identification argument, and the exact
  quarter lists for the fold options in decision 4.

Census code computes no feature-versus-outcome association.

### Step 3 — G3 pre-registration document + owner ratification. Owner load: one ~3-page read + the §3 decisions below.

`research-statistician` instantiates `data/f5/G3_PREREGISTRATION.md` from the
H5 §6 skeleton — §0 provenance & freeze; §1 estimand & primary metric; §2
event dating; §3 fundamentals PIT; §4 FX PIT; §5 benchmark; §6 fold structure;
§7 censoring arm; §8 head 2; §9 head 3; §10 cross-head hierarchy; §11 instrument
disclosures; §12 data-source ratifications; §13 the stopping rule verbatim,
signed and dated — as a fill-in table (convention → measured population → rule →
enforcing test), ≤ 3 pages. §1 pins every transform, feature, seed, fold-index
rule and the margin procedure as a function plus arguments, including the two
zero-labeling families (embedding model name + revision + sha + pooling;
novelty metric) — a named transform is not a pre-registration (H2: seven
implementations of one name spanned 0.059). §11 carries: adapter sha, the v1.2 teacher red-flag error 42.00% [35.37,
48.93] with the eight owner policy rules (`OWNER_POLICY_RULINGS.md`), H3v2
per-feature retention with CIs (never a family mean), the teacher-arm control
for any cross-rubric claim (the +0.0904 / +0.0481 split, G1 §6 condition 3),
sentiment NEGATIVE recall 0.487 and the G2 stored-NEGATIVE precision 25/49, the
G2 headline and escorts with `G2_FINAL_REPORT.md` §0, the train-overlap
population, the F4 §2 drift disclosure (ruled 2(a): noted, does not fire), and
the labeler-reliability λ sourced per the G2 §6.5 box (H3v2 retention or the
m-chunk composition with m stated — never a G2 chunk proportion); the
survivorship direction of price censoring stated in words (dead-name exclusion
removes the worst outcomes from the scored set and removes dying members from
the benchmark denominator: 27 of 176 core CIKs have no price column, 31 universe
members are absent from the benchmark matrix, 324 subjects delist mid-window);
and whether `train_overlap` gets a CIK-level upper-bound companion (the accession
channel is a lower bound, 4.53% vs 15.85% CIK-level exposure). §12 carries
the price source, the FX source, the sha-pinned price snapshot, and the
embedding model as a third-party artifact. The fixed scope sentence for every
claim: *"No text-vs-numeric IC improvement of economically relevant size is
detectable in this universe through this labeling schema, these features, this
labeler, and this feature specification."*

`tech-council` (Fable) reviews; `red-team-reviewer` checks every measured number
against `census_e2.json`. The owner rules the §3 list, signs §13, and the
document's sha goes into `data/f5/G3_RATIFIED.json` and HANDOFF §3.

### Step 4 — Run. Owner load: read the per-fold tables personally.

One session, one non-interactive invocation per head. Head 1 (both specs, the
same-day sensitivity arm, both censoring windows, with/without overlap,
zero-info rows, anchor, margin procedure, TOST), then heads 2 and 3. Reports
regenerate from diagnostics into `data/f5/`. The owner reads the per-fold
tables; nobody summarizes them for the owner (standing rule).
`red-team-reviewer` re-derives every headline from the artifacts. The stopping
rule (§13) then maps the head-1 result mechanically to one of three branches
(H5 Option 1): bounded null → alpha line closed, negative result written up;
above-MDE positive → only the pre-registered robustness suite, plus the
extension-stratum replication **if and only if the extension arm has been
promoted by its own spot-check** (otherwise the positive branch has no
out-of-sample check and the write-up says so), then stop; ambiguous-inside-MDE
→ closed as the null with the CI published. Heads 2 and 3 cannot rescue head 1.

### Step 5 — Hand-off to F6 (diagnosis rerun, red-team over F1–F5, model card, LIMITATIONS).

### Track X (parallel, GPU nights) — extension-stratum labeling, ruled "extend"

Runs whenever the GPU is free; it is not on head 1's critical path.

- X1 `data/f4/run_campaign_chain.sh` gets a wrapper-level lock (flock/pidfile)
  and a test; the F4 seg-013 triple-drive is the reason (F4 close-out §4).
- X2 extension chunk build as its own campaign with its own home selection
  (RUN_COMMANDS trap 8): 3 sectors, 36 members, 8,115 F3 sections; chunk count
  re-derived before any night is committed (est. ~110k chunks); 10-row smoke +
  repro canary exactly as F4; a one-page pre-registration (window rule, reflow,
  segment plan) recorded in `data/f4/status/`.
- X3 3–4 overnights at the measured 1,455–1,461 chunks/h; resumable; the
  wrapper never launched by hand while alive.
- X4 extension spot-check (same blind-rater instrument, sector-stratified over
  the 3 unseen sectors, bars inherited at 0.85, its own pre-registered n) —
  **proposal: run it only when a branch consumes the extension arm** (the
  positive branch's replication), or earlier if the owner wants the arm
  characterized regardless. If it fails, the arm is not promoted and the
  positive branch proceeds without an out-of-sample check, stated in the
  write-up. Until it runs, extension labels are not promoted and nothing in G2
  is quoted as speaking to those sectors.

## 3. Owner decisions at G3, with defaults

| # | decision | default (model proposal) | why it is the owner's |
|---|---|---|---|
| 1 | Benchmark (EXPANSION_PLAN §3.3) | equal-weighted mean over that date's members **excluding self**, membership-dated (already implemented in `controls.py`); E1/E2 numbers declared incomparable wherever both appear. **Sub-choice surfaced by Step 1a:** the member set is the whole universe (both strata, median 128 priced members per session, as `controls.py` and `target_e2.py` build it today) — default keep, because the extension companies are real universe members with prices and label availability is irrelevant to a benchmark; core-only would require rebuilding the target table | OWNER-GATE G3 |
| 2 | GLD's analysis-side treatment | excluded from the benchmark average and from IC rows in all heads; one sensitivity row including it | deferred to G3 by the retention ruling |
| 3 | Primary metric, specification and the confirmatory text block (EXPANSION_PLAN §4; H2 §2 is "the artifact G3 ratifies") | dedup Spearman IC delta (text+numeric − numeric-only), core stratum, form-controlled ablation as the honest secondary, dedup + raw both reported; specification = PIT trailing ranks (`window_days=180, min_comparators=2`) primary, raw levels secondary, always as a pair. **Confirmatory text block, named:** of the 22 E1 text features the 13 red-flag columns are exploratory (demoted), leaving 9 — `n_text_chunks_attributed`, `share_chunks_risk_factors`, `share_chunks_mda`, `share_chunks_ex99_press_release`, `share_chunks_8k_body`, `sentiment_mean_score`, `sentiment_negative_share`, `guidance_signed_mean`, `guidance_any_present`; `share_chunks_8k_body` is dropped (identically zero under decision 9), so the confirmatory block = 8 legacy features + the two zero-labeling families. This is the feature list the scope sentence and the re-derived MDE refer to. Numeric baseline note (Step 1a): `book_to_market` is buildable — shares from the cover-page `dei:EntityCommonStockSharesOutstanding` (resolved for 151/176 core CIKs; cover-date, not period-end); `leverage_liabilities_to_assets` has 71.4% coverage and `operating_margin` 56.4% because `us-gaap:Liabilities` / operating income are UNRESOLVED for 51 / 46 CIKs (F2 forbids silent substitution) **Overlap arm note (Step 1b):** at the filing level 5,938 of 7,405 modeling rows (80.2%) carry some train-overlap chunk, so the "without overlap" arm as built scores ~1,467 rows with the fit unchanged; whether training also drops those filings, or the arm uses a share threshold, is part of this ruling | OWNER-GATE G3 |
| 4 | Fold structure: one number (§3.4) | 6-quarter burn-in (2016Q3–2017Q4), first test quarter 2018Q1, last test quarter = the last quarter all of whose 63-session forward windows close on or before the sha-pinned price snapshot (2026-08-24 snapshot → 2026Q1) → **33 folds**; post-2019 sub-window = 29 folds. No fold-inclusion floor applied; per-fold usable-name count reported always. **Row scope (Step 1a):** in-membership rows only (the target table flags `in_membership`; 16,859 of 29,271 rows), all forms scored with the form-controlled ablation as the secondary; the analysis frame is the three-way join of target × text × numeric — **7,634 rows today, 161–202 per quarter over 82–99 CIKs** — because F3/F4 extracted text only for earnings-bearing 8-Ks (9,225 in-membership target rows have no text) and 145 periodic filings from 10 CIKs never extracted; Step 2 re-derives n_dd and the MDE on this frame, not on 421–451. Alternative: 26 folds ending at the same last quarter (first test 2019Q4) — under it the mandatory post-2019 arm (H5 §7) is a duplicate of the primary and the censoring sensitivity becomes vacuous. The default deliberately buys the four 2018 folds from the 12.5–16.2%-censored cohort, which is what makes that arm non-vacuous. Step 2 supplies the exact quarter lists and the MDE re-derived at the chosen k | OWNER-GATE G3; adds zero folds unless deliberately moved |
| 5 | Label purge (H2 §3.3: 12.9% of E1 training labels resolve inside their test quarter) | purge training rows whose 63-session forward window ends on or after the test quarter's first session; no additional embargo buffer (the expanding scheme needs none) | never stated before; a fold convention |
| 6 | C1 / `include_same_day` | `include_same_day=True` as primary, with `include_same_day=False` as a mandatory named sensitivity arm reported beside it (E1: the two differed by 0.0515 in the headline). The target already dates at `max(filing_date, acceptance_datetime)` at session granularity while the transform uses filing-date day granularity; this asymmetry is the C1 repair being ruled. Step 1a note: 1,751 filings carry an ET acceptance date before their EDGAR filing_date (accepted after 17:30 the prior evening); the ported rule treats 1,717 of them as post-close and opens the window one to two sessions late — conservative, away from look-ahead; refining it is part of this ruling | H2 §7 queues it for G3 |
| 7 | FX PIT (§4) | owner already ruled the direction on 2026-08-25 (d), verbatim: "Convert to USD as standard in future for all companies in case not USD". Mechanism to ratify: dated FX series from the existing price provider (zero new providers), rate as-of the feature date, PIT-safe; a second non-USD reporter is converted and logged, **not** fatal — the council's draft "FATAL on any second non-USD reporter" (H5 §4) conflicts with the owner's instruction and is not adopted. Population today: 1 CAD float fact (Enbridge) + 13 fundamentals series | mechanism routed to G3 by the 2026-08-25 entry |
| 8 | Yahoo price source at E2 scale | **ratify or refuse** — the only major unratified input (inherited fallback under a robots.txt disallow; split-adjusted-only returns caveat travels with it). Refusing means no head runs until a replacement source is ratified | data-source ratification, HANDOFF §3 |
| 9 | 8K_BODY register (790 chunks, student trained on 0 examples) | exclude | H5 §11: exclude / pilot / caveat |
| 10 | Section masks (G2 §3.4) | mask (the G2 deliverable). Declining makes the 4,177 sentiment + 2,826 guidance off-matrix rows (230 active) in-scope and requires a new pre-registration with its own arm | G2 explicitly left it to F5 |
| 11 | WITHDRAWN guidance, n = 66 on E2 (E1 carved it out at n = 1) | evaluable; keep `GUIDANCE_MAP` WITHDRAWN = −1 for `guidance_signed_mean`; disclose n; one sensitivity row excluding WITHDRAWN | HANDOFF §7 carve-out no longer fits |
| 12 | Head 2 primary predictor + DV | predictor `sentiment_negative_share`, direction pre-registered positive; DV = mean absolute **raw** daily return over sessions [+1, +5] divided by the trailing 60-session mean absolute raw daily return (benchmark-free by construction, so decisions 1–2 do not propagate); event span = every quarter whose windows close under the sha-pinned snapshot — Step 1b measured 41 clusters 2016Q3–2026Q3 because a 5-session window closes late, and the last one is a partial quarter (92 usable events vs a 98–107 run-rate); default: end at the last COMPLETE quarter, symmetric with decision 4; SE by wild-cluster bootstrap over event quarters, stated as a few-clusters limitation. Disclosures attached to the row: the predictor is the field G2 ruled INDETERMINATE (86.9%), NEGATIVE recall 0.487; and because prices are split-adjusted only, the DV is not dividend-immune — an ex-dividend session inside [+1, +5] inflates it, disclosed per event count | H5 §8: one primary per head |
| 13 | Head 3 sample, horizon, metric | sample = all core CIK-quarters, exits as positives; exit within 4 quarters of the feature date; AUC; per-fold prevalence; folds whose 4-quarter outcome window extends past the label cut are reported as censored with the count, not scored; claim scope "exit", never "distress". **Step 1b census findings that this row must settle:** (a) `distress_events` holds 668 rows over 144 CIKs, but most default "exit" kinds are not exits — 285 of 360 Form 25 rows, 50 of 93 Form 15 rows and both 8-K item 1.03 rows are followed by the same company still filing in-membership a year later (exchange transfers, deregistration of a class); the ratified `exit_event_kinds` must be the set that actually ends the company's membership; (b) `label_cut` (observation boundary) has no measured source — candidate max(distress_events.filing_date) = 2026-08-17 censors 5 of 41 panel quarters; (c) feature dating rule: `latest_in_quarter` leaves 70% of panel rows without text features, `latest_in_quarter_with_text` covers all but dates features earlier in the quarter; (d) training-label purge (horizon_end_before_test_start, the only implemented rule) | H5 §9 |
| 14 | LOCO budget | population = each fold's training members; 6 folds at indices round(j·(K−1)/5), j = 0..5; refit count from the census; **descriptive only** — no per-CIK inference at k = 6 | EXPANSION_PLAN §5 |
| 15 | Equivalence-margin procedure (function + arguments + bounds) | Δ = the smallest value in the pre-registered ladder {0.03, 0.04, 0.05} such that the power requirement SE ≤ Δ/2.487 holds, where SE is the block-bootstrap SE from the measured lag-1 fold-delta autocorrelation and the implied floor; Δ is never above 0.05; if no ladder value satisfies the requirement the result is reported as **UNPOWERED** (no equivalence claim), never as equivalent. Executed inside the runner before any delta is printed (§2 Step 1). **Ratifying this ladder is KC3's explicit re-cut:** Δ = 0.05 admits an honest MDE up to 0.056, so any selected Δ > 0.03 is printed beside the implied MDE (2.8 × SE) and flagged as the KC3 branch, never silently | ratified 2026-08-26 as "procedure, not value"; the procedure itself must be pinned |
| 16 | Extension spot-check timing (Track X4) | conditional on a branch consuming the arm | ruling 2(b) sets the requirement, not the timing |
| 17 | §13 stopping rule | sign and date the verbatim Option 1 text in the G3 document | ratified 2026-08-26; the signature is the freeze |
| 18 | KC1 disposition (H1 positive controls) | main-session reading, flagged as such in `HARDENING_PROGRESS.md`: T1 FAILED its pre-declared bar (t = 3.13 vs 4.0; 70.7% vs 75% of quarters) while the relation is present (bootstrap CI [+0.026, +0.105]) and the stack is verified; T2a / T2b AMBIGUOUS with CIs containing zero; removing stale-Q4 matches drops T1 to t = 1.58. Default: KC1 not triggered by the letter, the three-branch taxonomy stands, the stale-Q4 SUE matching defect is repaired only if SUE enters a head (it is not in the default feature set) | H5 §5 KC1 is an owner pre-commitment; only the owner can say it did not fire |
| 19 | KC6 carve-out (§1) | allow reproducing H1's published T1 control as a pre-ratification plumbing check (no text feature enters it); alternative: run it only after ratification | KC6's ratified wording is "any E2 IC" |
| 20 | Every-occurrence attribution across companies at E2 scale (surfaced by Step 1a) | E1's 2026-08-11 ruling attaches a label to every filing its paragraph occurs in; at E2 scale a chunk's occurrence set is the union over its paragraphs, so one shared boilerplate paragraph carries a company-specific chunk into other companies' filings: 5,706 chunks (1.80%) occur under more than one CIK, 99,636 of 854,933 occurrence rows (11.65%) attach a chunk to a different company, one Wells Fargo chunk reaches 6,220 filings across 169 CIKs. **Default: restrict attribution to occurrences under the same CIK** (same-company every-occurrence), report `cross_cik_share`, and keep the E1 rule as a named sensitivity; alternative: extend the E1 ruling unchanged. Changing it rebuilds `text_features_e2.parquet` (19 s) | extends or amends an owner ruling |
| 21 | `operating_cashflow_to_revenue` period mismatch (Step 1a) | under E1's ported definition, 10-Q year-to-date cash flow is divided by quarterly revenue on 8,433 of 18,300 rows (46.1%); `period_days_*` columns are materialized per row. Default: duration-match (both flows over the same period) and disclose; alternatives: keep ported, or drop the feature | changes a pre-registered feature definition |
| 22 | Fundamentals staleness guard at E2 scale (Step 1a) | E1's 200-day `STALENESS_MAX_DAYS` no longer sits in an empty band: accepted facts reach the cap (p99 139 days, 47 above 180) and discards begin continuously at 201 (1,868 discards over 99 (CIK, family) pairs). Default: retain 200 and disclose; alternative: family-specific guards | a pre-registration input |
| 23 | Zero-labeling text families, conventions to pin (Step 1b) | (a) the novelty comparison object: as built, "most recent prior filing of the same section" is quarter-over-quarter (median gap 91 days; a 10-K's prior is the preceding 10-Q) under `_yoy` names — default: pin the prior-year filing of the SAME FORM (true year-over-year) and rebuild (18 s for family A); (b) RISK_FACTORS novelty is dominated by short 10-Q "no material changes" stubs (39% of pairs have a side under 50 shingles; 855 exact zeros, 516 exact ones) — default: minimum-length filter with the stub count disclosed; (c) prior-candidate pool = whole corpus for the CIK (back to 2015-07), default keep; (d) 8K_BODY sections are embedded (85 in scope) though excluded from label features — default exclude for symmetry (25-min rebuild); (e) filing pooling weights sections equally — default keep, window-weighted as a named alternative; (f) the 64-window cap bit 17.1% of sections; (g) embedding PCA k (default 16) and whether components pass through the PIT-rank transform on the primary arm only (raw on the secondary — fixed after review); (h) the model itself as a §12 third-party artifact: sentence-transformers/all-MiniLM-L6-v2, revision 1110a243…, weights sha 53aa5117…, Apache-2.0 | function + arguments must be pinned (H2) |

Not decisions (already ruled, listed so nobody re-opens them): the stopping
rule's three branches (Option 1); red_flags exploratory/disclosure-only; council
§7 item 3 "noted, does not fire"; distress_tier never scored; the FX
*direction* (convert, 2026-08-25); no rubric v1.3 inside F5 (recommended for a
later ratification, HANDOFF §3 2026-09-07); no mid-cap arm; no API spend.

Only new dependency: one small open embedding model downloaded once for the
pooled-embedding family (local, $0, cached outside the repo). Its name,
revision and sha are pinned in G3 §1 and ratified as a third-party artifact in
G3 §12.

## 4. Cost and calendar (honest bands)

| item | cost |
|---|---|
| API | $0 (frozen; nothing here calls one) |
| CPU | features + three heads: minutes to ~1 h on the M5; bootstrap anchors 4,000 × folds × specs, still under an hour; embeddings one-off, a few hours, cached |
| GPU | Track X only: 3–4 overnights |
| agent sessions | Step 1 ≈ 2–3 (Opus) + 1 red-team; Step 2 ≈ 1; Step 3 ≈ 1 + council; Step 4 ≈ 1 + red-team; Track X ≈ 1 plus nights |
| owner time | one ~3-page G3 read + the 23 rulings above; one per-fold read at Step 4 |
| calendar | ~2 weeks elapsed if G3 is ruled promptly; Track X runs alongside |

## 5. What can stop F5 (all six H5 §5 kill criteria, status today)

| criterion | status |
|---|---|
| KC1 positive controls fail → taxonomy void | **owner adjudicates at G3 (decision 18)**; main-session reading: T1 failed its pre-declared bar but the relation is present and the stack verified; T2a / T2b ambiguous |
| KC2 labeler attenuation breaches the band | breached at H3 (family 0.669), discharged by the ratified repair path (H3v2 0.808 [0.750, 0.853]); per-feature retention travels with every result |
| KC3 honest MDE lands above ~0.05 | live in the floor branch. H2 primary-spec numbers at k = 26: 0.032 floor-free → 0.085 if the rank-spec floor is real; true-construct 0.036–0.107 at λ ≈ 0.8. Every MDE is a lower bound under fold non-independence, the noise anchor was estimated on 2025–26 mega-cap folds, and per-family MDEs scale ~0.4–2.4×. Re-derived at the ratified k in Step 2; re-cut only by explicit ratification |
| KC4 measured fold autocorrelation ≫ 0.3 | measured at Step 4; publish the degraded bound, never re-window |
| KC5 owner ratifies a distribution/product pivot → re-convene | not triggered (the app vision is recorded, charter-bounded, post-E2) |
| KC6 the freeze (§1) | enforced by the runner guards and the run log |
| G1 §7 item 4 (attenuation makes the MDE unreachable) | re-examined at G3 with H3v2 retention in hand |

## 6. Definition of done for F5

`data/f5/` holds the ratified G3 document + `G3_RATIFIED.json`, `census_e2.json`,
the feature/target tables (sha-pinned, git-excluded), `run_log.jsonl`, the
three heads' per-fold reports with every standing section printed, and a
red-team verdict; HANDOFF §3 carries the G3 ratification and the branch the
stopping rule selected; RESUME_HERE points at F6. Every headline carries the
scope sentence, the G2 caveats and per-feature retention, and no headline
quotes a raw MDE alone.
