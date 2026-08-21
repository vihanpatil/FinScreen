> # ✅ COMPLETE (2026-08-18) — the 400-example review is finished
>
> All 400 sample chunks were judged, all disputes resolved, and the results
> are published in **`agreement_report.txt`**. Nothing in this directory is
> waiting on anyone.
>
> **Three rater layers, by provenance — none of them is a human read of all
> 400:**
>
> 1. **`label-auditor` (a model, opus)** — blind second rater over all 400
>    chunks. `source=model-auditor` on 1,023 of the 1,222 judgments.
> 2. **`label-adjudicator` (a model)** — third rater over the 174 contested
>    chunks (199 field-cases). `source=model-adjudicator` on 95 judgments.
> 3. **The owner (a human)** — ruled the 104-case shortlist only
>    (85 by block ratification of medium+-confidence adjudications, 19
>    explicitly: the 11 high-stakes distress chunks and an 8-case final
>    round). `source=owner`.
>
> These rates therefore measure **model-consensus agreement, adjudicated,
> with human judgment concentrated on the shortlist** — they are **not**
> human validation of ground truth. See `agreement_report.txt`'s provenance
> appendix.
>
> Sample composition: A=162 (all distress positives) · B=142 · D=60 · C=36.
---

# FinScreen Week 3 spot-check package

This directory holds the tooling and outputs for the 400-example
second-rater spot-check of `data/labels.parquet` (Week 3 DoD in
`ROADMAP.md`). **Zero paid actions were used anywhere in this package.**
Everything here reads `data/labels.parquet` read-only and never touches
`.env` or any API key.

## Pipeline order (what actually ran)

```
build_sample.py       →  sample_400.parquet / sample_400.json   (400 chunks)
label-auditor         →  auditor_verdicts.json                  (400 verdicts)
                      →  auditor_disagreements.json             (174 contested chunks)
build_adjudicator_batches.py → adjudicator_batches/             (12 batches)
label-adjudicator     →  adjudicator_verdicts.json              (199 field-cases)
merge_adjudications.py / build_owner_shortlist.py
                      →  owner_shortlist.md                     (104 field-cases)
                      →  owner_final_round.md                   (8 unsure/low-conf)
                      →  combined_judgments.csv                 (1,222 judgments)
compute_agreement.py  →  agreement_report.txt                   (the deliverable)
```

## Files

| File | What it is |
|---|---|
| **Sample construction** | |
| `build_sample.py` | Builds the tiered 400-row sample from `data/labels.parquet`. Read-only on source data. |
| `sample_400.parquet` | The 400-row sample, one row per selected `chunk_id`, with `primary_tier`, `tiers`, `subtier` columns added. |
| `export_sample_json.py` | Converts `sample_400.parquet` into `sample_400.json`, the JSON blob embedded in the HTML review tool. |
| `sample_400.json` | The 400 examples in the shape the review tool consumes. |
| **Second rater (model)** | |
| `auditor_verdicts.json` | All 400 `label-auditor` verdicts. **Model verdicts, never the owner's.** |
| `auditor_disagreements.json` | The 174-chunk contested set (any field with a disagree/unsure verdict). |
| **Third rater (model)** | |
| `build_adjudicator_batches.py`, `adjudicator_batches/` | Inputs for the 12 adjudication batches; deterministic rebuild. |
| `adjudication_workflow.js` | The workflow script that drove the adjudication run. |
| `adjudicator_verdicts.json` | All 199 `label-adjudicator` field-case verdicts over the 174 chunks (`source=model-adjudicator`). |
| `merge_adjudications.py` | Validates coverage and writes `adjudicator_verdicts.json` + `combined_judgments.csv`. |
| **Owner rulings (human)** | |
| `build_owner_shortlist.py`, `owner_shortlist.md` | The consolidated decision list: 3 principle rulings + 11 high-stakes chunks + 62 individual items. **RESOLVED 2026-08-18.** |
| `owner_final_round.md` | The 8 unsure/low-confidence cases. **RESOLVED 2026-08-18.** |
| `adjudication_174.html`, `build_adjudication_view.py`, `adjudication_template.html` | Browser view over the 174 contested chunks (reuses `review_app.js` byte-identical). Superseded in practice by `owner_shortlist.md` for decision-making; still the reference UI for reading chunks in context. |
| **Results** | |
| `combined_judgments.csv` | All 1,222 provenance-tagged judgments. `source` = model-auditor 1023 / model-adjudicator 95 / owner 104. No blanks; nothing imputed. |
| `agreement_report.txt` | **The deliverable** — per-category, per-tier and per-section rates with Wilson CIs, plus the provenance appendix. |
| `compute_agreement.py` | Computes that report from `combined_judgments.csv`. |
| **Original review tool (superseded by the pipeline above)** | |
| `review_app.js` | Pure serialization/state logic (build initial state, CSV/JSON export, CSV/JSON import, progress calc). Tested under Node in `test_review_app.js`, then inlined into the HTML tool by `build_review_tool.py`. |
| `review_app_template.html` | The DOM/CSS/JS shell with two placeholders that get filled in by the build script. |
| `build_review_tool.py` | Assembles `review_tool.html` from the template + `review_app.js` + `sample_400.json`. |
| `review_tool.html` | Self-contained review tool. Open directly from `file://` — no server, no external hosts. |
| `make_review_template_csv.py`, `sample_400_review_template.csv` | Spreadsheet-editable fallback to the HTML tool — same columns as the tool's CSV export, judgments blank. |
| **Tests** | |
| `test_review_app.js` | Node round-trip test for `review_app.js` (see "What was and wasn't tested" below). |
| `test_compute_agreement.py` | Unit tests for `compute_agreement.py`, synthetic data only. |
| `test_build_adjudication_view.py` | Unit tests for `build_adjudication_view.py`. |

## Regenerating the sample

```
cd spotcheck
python3 build_sample.py           # -> sample_400.parquet
python3 export_sample_json.py     # -> sample_400.json
python3 make_review_template_csv.py   # -> sample_400_review_template.csv
python3 build_review_tool.py      # -> review_tool.html (re-embeds sample_400.json)
```

`build_sample.py` is deterministic: re-running it against an unchanged
`data/labels.parquet` produces a byte-identical `sample_400.parquet`
(verified: `md5sum sample_400.parquet` is identical across two
consecutive runs in this session). If `data/labels.parquet` changes
(e.g. a rubric-revision re-label), the sample will change accordingly —
that's expected, not a bug.

**Seed:** `SEED = 20260810` (numpy `default_rng`), used for every random
draw in `build_sample.py`. Documented at the top of that file.

## Tier definitions, precedence, and exact composition

> **Tier legend (one line each — this is the shorthand every agreement
> number in `agreement_report.txt` is reported against):**
> **A** = all distress positives, exhaustive · **B** = thin-category
> oversample · **C** = proportional base-rate fill (**the only
> base-rate-representative slice**) · **D** = the config-disagreement set,
> judged blind.
>
> **Live composition, recomputed from `sample_400.parquet` 2026-08-18:**
> **A=162 · B=142 · D=60 · C=36 = 400.**
>
> | Tier | 8K_BODY | EX99_PRESS_RELEASE | MDA | RISK_FACTORS | total |
> |---|---|---|---|---|---|
> | A | 2 | 42 | 44 | 74 | 162 |
> | B | 0 | 88 | 39 | 15 | 142 |
> | C | 0 | 6 | 22 | 8 | 36 |
> | D | 0 | 7 | 30 | 23 | 60 |
>
> **Tier D — the config-disagreement set (60 rows, owner-approved):**
> chunks where the two labeling configs produced different `red_flags`
> sets (935 such chunks corpus-wide, 22.2% of the re-labeled set). They
> were judged blind — the alternative config's labels were deliberately
> not shown — so that Tier D's agreement rate against the other tiers
> measures which config was more accurate.
>
> **The rest of this section describes the ORIGINAL pre-relabel,
> pre-Tier-D draw (A=143 / B=142 / C=115).** It is kept because it is the
> only written record of the sampling *rules*, which did not change. Trust
> the numbers in this box and in `build_sample.py`, not the counts below.

Precedence for a row's recorded `primary_tier` (used for reporting; a row
is only ever included once in the final 400): **A > B > C**. The `tiers`
column on each row records the FULL set of tier criteria it matches
(independent of which tier it was actually drawn into), so a distress
positive that also has non-NONE guidance shows `tiers=A,B` but
`primary_tier=A` and counts against Tier A's budget only.

**Tier A — exhaustive (143 rows at the original draw; 162 today):** every
row where `distress_tier` is a non-empty list (any of the 3 distress
categories, any modality).

**Tier B — targeted oversample of thin categories (142 rows after
dedup against Tier A), built as 3 sub-groups, each drawn from what's left
after the prior sub-groups are removed:**
- **B1 — named chunks (2 rows):** `CHK-8e69547e0900a8dd` and
  `CHK-6cfb7bb16c8ef2fc`, included regardless of any other criteria.
- **B2 — guidance non-NONE (80 rows):** all rows with
  `guidance_direction` in `{RAISED, MAINTAINED, LOWERED, WITHDRAWN}`,
  minus anything already in A or B1. (83 total non-NONE guidance rows
  exist corpus-wide; 3 overlap with Tier A's distress positives.)
- **B3 — REALIZED-modality red flags, per-category quota (60 rows —
  10 per category x 6 categories):** an earlier draft of this script took
  "all REALIZED-modality red flags" as one pool, but that pool is 2,693 of
  6,747 rows corpus-wide — far too large for a targeted-oversample tier,
  and a flat subsample of it would have been dominated by whichever
  category is most common (`MARGIN_COST_PRESSURE`/REALIZED: 1,064
  instances) rather than giving every category a reviewable sample. B3
  instead guarantees a fixed quota of 10 REALIZED-modality rows **per
  red-flag category** (processed in alphabetical order, each category's
  quota drawn from what's left after A/B1/B2/earlier-B3-categories are
  removed, stratified proportionally by `section_type` within that
  category's pool). Corpus-wide REALIZED-instance counts by category, for
  reference: `DEMAND_WEAKNESS` 755, `IMPAIRMENT_WRITEDOWN` 723,
  `LEGAL_REGULATORY_ACTION` 1020, `MARGIN_COST_PRESSURE` 1064,
  `SUPPLY_INPUT_CONSTRAINT` 158, `TRADE_POLICY_EXPOSURE` 240 — none of
  these are thin enough to exhaust within a 400-row budget the way Tier
  A's distress positives are, hence the per-category quota rather than
  exhaustive coverage.

**Tier C — proportional stratified fill (115 rows):** drawn from
whatever remains after A and B are removed, stratified proportionally by
`section_type` against the *remaining eligible pool* (not the raw
corpus — Tier A/B have already skewed which section types are left; e.g.
`8K_BODY` has only 8 rows corpus-wide and 2 are already claimed by Tier A).
Rounding uses the largest-remainder (Hamilton) apportionment method so
counts sum to exactly the needed fill size.

**Resulting composition of that original draw:** A=143, B=142 (B1=2,
B2=80, B3=60), C=115. **143+142+115=400.** *(Superseded — the live
composition is the table in the box at the top of this section.)*

## CHK-8e69547e0900a8dd — RESOLVED, not an open question

`CHK-8e69547e0900a8dd` is a **genuine mid-stream safety refusal**
(`stop_reason=refusal`, `stop_details.category=bio`, 293 output tokens of
partial JSON, `section_type=MDA`) — not an output-token truncation, and not
a decision the owner still owes anyone. Settled 2026-08-11 from the primary
Batch API record; it is excluded from train/eval by predicate and
`labels.parquet` stays frozen. **Canonical account:
`data/full_run_report.md`'s FINAL CONSOLIDATED STATE section** (also
`REDTEAM_WEEK3.md` finding #1's RESOLUTION, `finetune/SPLIT_DESIGN.md` §1,
`HANDOFF.md` §2). An earlier version of this section argued for truncation
over refusal and said the section type was `RISK_FACTORS`; both were wrong.

## The GOING_CONCERN zero-support finding

The distress tier has 3 rubric categories (`GOING_CONCERN`,
`ACCOUNTING_RESTATEMENT`, `LIQUIDITY_STRESS`). Across all 162 distress
positives in the full labeled corpus (post-relabel; this was 143 before the
2026-08-11 corrective re-label), the actual instance breakdown is:

- `LIQUIDITY_STRESS` / `HYPOTHETICAL`: 151
- `LIQUIDITY_STRESS` / `REALIZED`: 9
- `ACCOUNTING_RESTATEMENT` / `HYPOTHETICAL`: 2
- **`GOING_CONCERN`: zero instances, either modality, anywhere in the
  corpus.**

This is consistent with the rubric's own framing (§5: "this corpus is
drawn from 25 currently-healthy mega-cap filers, so real positives in this
tier are expected to be rare-to-none") but is worth stating plainly:
**`GOING_CONCERN` is entirely unexercised by this labeled corpus** — the
spot-check (and any downstream fine-tuning/eval) cannot say anything about
whether the model or rubric handles going-concern language correctly,
because there is no data to check it against. `compute_agreement.py`'s
distress-tier section will show 0 rows for this category if the owner
tries to break it out further than the pooled `distress_tier` field
(the current CSV/JSON export schema pools all 3 distress categories under
one `distress_tier` field per rubric §5's instruction to keep it a single
separate field — see "Limitations" below for why per-sub-category
breakout wasn't built).

## How the review was actually run (2026-08-18)

The owner never paged through all 400 in `review_tool.html`. What ran was
the three-layer pipeline at the top of this file: a model second rater over
all 400, a model third rater over the 174 contested chunks, and owner
rulings on a 104-case shortlist — with `source` provenance recorded on every
judgment. Results live in `combined_judgments.csv` and `agreement_report.txt`.

`review_tool.html` and `sample_400_review_template.csv` remain as the
manual paths (browser tool and spreadsheet fallback; identical column shape
`chunk_id, section_type, primary_tier, field, judgment, field_note,
example_note`, judgments blank, nothing ever pre-filled), and
`adjudication_174.html` remains the reference UI for reading any contested
chunk in context.

## Running compute_agreement.py

The report in `agreement_report.txt` was produced by:

```
python3 spotcheck/compute_agreement.py --input spotcheck/combined_judgments.csv --format csv
```

`combined_judgments.csv` is the real input. (`--format auto` also works —
it picks CSV vs JSON from the extension.)

The report prints:

1. A header stating the distress-tier exclusion and Tier-B
   non-representativeness caveats.
2. **Section 1** — headline per-category agreement (`sentiment`,
   `guidance_direction`, `red_flags`), all tiers pooled, with 95% Wilson
   CIs. Explicitly flagged as **not** base-rate-representative.
3. **Section 2** — `distress_tier`, reported completely separately,
   **excluded from Section 1's headline numbers** (asserted in code via
   `assert_distress_excluded_from_headline`, which raises if a
   `distress_tier` row ever leaks into the headline computation).
4. **Section 3** — per-tier (**A/B/C/D**) breakdown of the headline fields,
   with an explicit note that Tier C is the base-rate-representative slice
   to use for any true-base-rate claim. **These per-tier figures pool all
   three headline fields together** — for a red-flags-only per-tier rate,
   see `HANDOFF.md` §2a.
5. **Section 4** — per-`section_type` breakdown.
6. **Section 5** — rubric-revision candidates: any category whose 95%
   Wilson CI lower bound falls below `CI_LOWER_BOUND_BAR = 0.70` (a
   documented judgment call made in this script, not specified
   numerically anywhere in `labeling_rubric.md` — edit the constant at the
   top of `compute_agreement.py` to change it), with that category's
   disagreement notes printed for the revision discussion.

Unfilled judgments are reported as a coverage gap (`unfilled` count,
`coverage` percentage) and are **never imputed** as agree or disagree.
`unsure` judgments are reported but excluded from the agreement-rate
numerator/denominator (neither counted as agreement nor disagreement).

## What was verified vs. what wasn't (be honest about this)

**Verified (with actual passing test output):**
- `build_sample.py` is idempotent: two consecutive runs produced
  byte-identical `sample_400.parquet` (checked via `md5sum`).
- The assertion block in `build_sample.py` (exactly 400 rows, unique
  chunk_ids, all distress positives present — **162** in the current
  corpus, 143 at the time this note was first written — all 83
  non-NONE-guidance rows present, both named chunks present, all 6
  red-flag category quotas non-empty) passed on the actual run against
  `data/labels.parquet`.
- `test_review_app.js`, run under Node (`node
  spotcheck/test_review_app.js`), verifies: initial state has zero
  pre-filled judgments; the applicability matrix is correctly respected
  (no `sentiment` field for RISK_FACTORS rows, no `guidance_direction`
  field for MDA/RISK_FACTORS rows); CSV export/import round-trips exactly
  (1239 field-rows, including commas/quotes/newlines in note text); JSON
  export/import round-trips exactly; malformed/wrong-format JSON import is
  rejected rather than silently accepted; the missing-data path (unfilled
  judgments) round-trips correctly. All of this ran against the REAL
  logic in `review_app.js`, which is the identical code inlined into
  `review_tool.html` by `build_review_tool.py` (not a separate
  reimplementation) — verified by extracting the 3 `<script>` blocks from
  the generated `review_tool.html` and confirming each parses as valid
  JavaScript under `node --check`.
- `test_compute_agreement.py` (15 tests, synthetic data only) passes —
  Wilson CI hand-computed checks (10/10, 50/100, 0/20, n=0), a check that
  Wilson meaningfully differs from a naive Wald/normal approximation near
  a boundary proportion, tier/section/category breakdown isolation, the
  missing-data-never-imputed path, and the `distress_tier`
  headline-exclusion assertion (including a test that it correctly raises
  if `distress_tier` leaks into a headline computation).
- `compute_agreement.py` was run end-to-end against two synthetic exports
  (one CSV, one JSON, both generated by actually exercising
  `review_app.js`'s export functions under Node — not hand-written) and
  produced a correctly structured report in both cases.

**Verified (owner's manual browser test, post-review):** the owner opened
`review_tool.html` in a real browser and confirmed it PASSED. Specifically
verified: the page renders correctly; per-field judgments register via
event delegation; state persists in `localStorage` under key
`finscreen_spotcheck_state_v1` across a page reload; the progress counter
increments only when an example is fully judged (confirmed as the intended
behavior); and Export CSV produces well-formed output with header
`chunk_id,section_type,primary_tier,field,judgment,field_note,example_note`
and 1,240 rows for the 400 examples. The test judgments used during this
verification were cleared afterward.

**NOT verified (still open):** the `<input type=file>` JSON-import/resume
path, and cross-browser coverage beyond the one browser the owner tested
in. What WAS separately verified pre-review is that (a) the underlying
serialization/state functions the DOM handlers call are correct (via the
Node test above) and (b) the DOM-wiring script itself is syntactically
valid JavaScript (`node --check`).

## Limitations / judgment calls made

- **Distress tier is reported as one pooled field**, not broken out by
  its 3 sub-categories (`GOING_CONCERN`/`ACCOUNTING_RESTATEMENT`/
  `LIQUIDITY_STRESS`), matching the rubric's framing of `distress_tier` as
  a single field (§5, §7 output schema) — but see the GOING_CONCERN
  zero-support finding above; a sub-category breakout would show 0 rows
  for `GOING_CONCERN` specifically and could be added later if the owner
  wants it.
- **CI_LOWER_BOUND_BAR = 0.70** in `compute_agreement.py` is a judgment
  call, not derived from the rubric (which specifies no numeric bar). It's
  a constant at the top of the file, easy to change and re-run.
- **REALIZED_QUOTA_PER_CATEGORY = 10** and the Tier-C stratification-
  against-remaining-pool rule (rather than against the raw corpus) are
  both documented judgment calls, explained above and in
  `build_sample.py`'s docstring; they were sized to fit a 400-row budget
  while still giving every red-flag category a reviewable sample.
- **`unsure` judgments are excluded from the agreement-rate calculation**
  (neither agree nor disagree) rather than treated as a third outcome
  folded into the rate — this seemed like the more honest choice (an
  "unsure" isn't a disagreement, but counting it as agreement would
  overstate confidence), but it does mean the agreement-rate denominator
  can be smaller than the number of examples reviewed; `compute_agreement.
  py` reports `unsure` counts explicitly alongside the rate so this isn't
  hidden.
