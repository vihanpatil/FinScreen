# FinScreen documentation review — consolidated findings

**Scope:** the in-scope stable set only. **Method:** three lens reviews (accuracy, readability, navigation) deduped and re-verified. Every CRITICAL and MAJOR factual claim below was independently re-checked by me against the underlying parquet/CSV/JSON/SQLite artifacts or by re-running the tests; recomputations are quoted inline. Findings that violated the audit-trail convention, or that a lens got wrong, are listed in **Dropped** at the end with reasons.

**Note on drift:** `HANDOFF.md` was rewritten by a concurrent agent during the lens passes (744 → 786 lines). All line numbers below are against the **current 786-line file**, re-grepped. One lens finding was invalidated by that rewrite and is dropped.

---

## CRITICAL — a reader would act wrongly, or a stated number is false

### C1. `HANDOFF.md` §2 "Pending (not started…)" (lines 319–329) is flatly contradicted by §2a in the same section
Lines 320–323 state "Spot-check second-rater pass itself — `label-auditor.md` has not yet been run against any of the 400 sample chunks", "Any rubric revision (contingent on spot-check results)", and "Week 5 features + walk-forward backtest — not started."

**Evidence (verified):** §2a line 93 "Label-auditor pass complete: 400/400"; line 147 "STEP 1 IS COMPLETE"; line 170 "STEP 2 (Phase B) COMPLETE". On disk: `spotcheck/auditor_verdicts.json` (400 verdicts), `spotcheck/agreement_report.txt` (final rates), `RED_FLAGS_LIMITATION.md` (the Phase B disposition), `data/features.parquet` (630 rows), `data/backtest_report.md`, `features.py`, `backtest.py`. A newcomer reading §2 top-to-bottom learns the work is done and then, 190 lines later in the same section, that it never started.

**Fix:** delete the first three bullets; replace with "Steps 1–2 and the Phase C build — complete, see §2a." Keep only Step 4 go/no-go, Step 5 QLoRA, Step 6 model card.

### C2. `HANDOFF.md` header (lines 12–16) — the first thing every reader is told is wrong
"…the third-rater adjudication to **159/174**" and "**the work is mid-flight and the first step is a 10-minute completion task**."

**Evidence (verified):** §2a line 121 "Adjudicator run: COMPLETE (174/174, 12/12 batches, zero failures)"; `adjudicator_verdicts.json` carries 174 chunk records / 199 field-cases. The current first step (§2a line 263) is the Phase C fix+verify workflow plus the owner's personal go/no-go read — not a 10-minute task.

**Fix:** "174/174, complete. Steps 1–2 done. Start at §2a → IMMEDIATE NEXT STEPS; the first step is the Phase C fix+verify workflow and the owner's go/no-go read."

### C3. Pooled-all-field agreement rates are presented as red-flag rates, in three docs
`HANDOFF.md` §2a lines 159–161: "**red_flags 63.4% … FAILS** … Worst in RISK_FACTORS sections (59.2%) and Tier D (71.2% vs A 76.9 / B 83.4 / C 84.3)". Same construction in `RED_FLAGS_LIMITATION.md` lines 60–62 (inside a section titled "What is wrong with the red-flag labels, concretely") and in `DISCOVERY.md` §6's 2026-08-18 amendment.

Those four tier numbers are `agreement_report.txt` Section 3's **headline-pooled** figures (sentiment + guidance + red_flags together). Recomputed from `spotcheck/combined_judgments.csv`:

| Tier | red_flags only | pooled-headline (what the docs quote) |
|---|---|---|
| A | 96/162 = **59.3%** | 76.9% |
| B | 98/141 = **69.5%** | 83.4% |
| C | 27/36 = **75.0%** | 84.3% |
| D | 32/60 = **53.3%** | 71.2% |

The docs understate the red-flag failure in Tier D by ~18 points, and the "lowest of the four tiers" ordering **inverts** on the red-flags-only basis (Tier A 59.3% is worse than the 71.2% quoted for the "worst" tier). The 59.2% for RISK_FACTORS is correct either way — RISK_FACTORS chunks are only asked `red_flags`, so its pooled and red-flags-only rates are identically 71/120.

**Fix:** quote the red-flags-only tier rates in all three places, or label every one of them "all headline fields pooled" as `HANDOFF.md` line 164 already does for Tier C. Say in one clause that RISK_FACTORS' 59.2% is red-flags-only by construction.

### C4. `finetune/SPLIT_DESIGN.md` §6 (line 187) states a false split composition, unflagged
"**10 of 25 companies have zero eval presence, and 2 (UNH, NVDA) have zero train presence.**"

**Evidence (recomputed from `finetune/splits/{train,eval}.parquet`):** **7** tickers have zero eval presence (GOOGL, JPM, MSFT, PG, V, WMT, XOM); **3** have zero train presence (**AAPL, MCD, SLB**). UNH and NVDA are present on **both** sides. §6 sits outside §5's self-flagged-stale block, and `HANDOFF.md` §8 line 758 flags only "§5's table" — so nothing warns the reader.

**Fix:** recompute §6's bullet from the live split; extend the §8 flag to §6.

### C5. `finetune/SPLIT_DESIGN.md` banner (lines 3–9) contradicts §5 inside the same file, and cites §5 as its own evidence
Banner: "**✅ CURRENT (2026-08-11)** — §5's tables below reflect the retuned split: eval is 1,010 chunks (15.0%) … `guidance:RAISED` starvation (12 training examples) is fixed: 27 train / 7 eval."
§5 (line 128): headed "**PROVISIONAL, pending re-label regeneration**", says "This section is stale", prints `train=5669 (84.0%), eval=1077 (16.0%)` and `guidance:RAISED 12 / 23`.

**Evidence (recomputed):** train **5,736** / eval **1,010** = **15.0%**; RAISED **27 / 7**. §5's section-type table is also wrong (eval RISK_FACTORS 215 vs live **135**; MDA 241 vs **297**; EX99 613 vs **570**). The banner is right; §5 is the superseded half — but the banner asserts the opposite.

**Fix:** regenerate §5 from the live split, or change the banner to read "§5 below has NOT yet been regenerated." Either way, delete §5 line 130's reference to "the HOLD note at the top of this doc" — no HOLD note exists.

### C6. `spotcheck/README.md` lines 129–164 makes two false claims about a resolved question, and the staleness pointer doesn't cover it
The 36-line section "The CHK-8e69547e0900a8dd discrepancy (report this to the owner directly)" asserts:
(a) "`data/full_run_report.md` describes … section **`RISK_FACTORS`**" — grepped: `full_run_report.md` says **`MDA`** at lines 46, 279 and 314.
(b) "That's the signature of an **output-token truncation** … not a refusal", and tells the owner they "still need to decide whether to hand-label it or drop it."

**Evidence (verified):** `data/labels.parquet` row `CHK-8e69547e0900a8dd` carries `section_type=MDA`, `stop_reason='refusal'`, `output_tokens=293`. Four other in-scope docs record the resolution from primary API evidence: `full_run_report.md:46` and `:314` (`stop_details.category=bio`), `REDTEAM_WEEK3.md` finding #1's RESOLUTION — CORRECTED, `finetune/SPLIT_DESIGN.md` §1's explicit "**Resolved**" block, and `HANDOFF.md` line 53. `HANDOFF.md` §2's staleness pointer for this file (lines 350–356) lists only tier definitions, the composition table, GOING_CONCERN counts and round-trip counts — this whole section is uncovered, so a reader following the pointer trusts it.

**Fix:** replace the section with one sentence and a pointer to `full_run_report.md`'s FINAL section, and extend HANDOFF's pointer to name it.

### C7. `ROADMAP.md` is designated "current, not stale" but contains three false load-bearing statements
`HANDOFF.md` line 342 and §8 line 709 both designate ROADMAP current — and the owner's own audit-trail list excludes it — so its staleness is a finding, not preserved history.

- **Phase A, lines 76–80:** "Fix needed first: the script currently hardcodes `["A", "B", "C"]` … add Tier D to that breakdown before running it for real." **Verified fixed:** `spotcheck/compute_agreement.py:258` reads `for tier in ["A", "B", "C", "D"]`; `agreement_report.txt` Section 3 is headed "A / B / C / D" and prints Tier D; `pytest spotcheck/` = 51 passed.
- **Phase C, lines 132–134:** "**no fundamentals dataset exists in this repo yet** (`edgar_client.py` has no XBRL/company-facts pulling capability today)." **False:** `edgar_client.py:299` defines `get_companyfacts()`; `data/fundamentals.parquet` = 42,158 rows / 25 companies / 13 concepts.
- **Phases A and B are written entirely in future tense with no completion marker**, though both are complete (`agreement_report.txt`, `RED_FLAGS_LIMITATION.md`). A reader told "ROADMAP is current" reads Phase A as the next action.

**Fix:** add a `DONE` / `IN PROGRESS` marker and a date stamp per phase; delete the Tier-D fix note; rewrite the Phase C fundamentals bullet as a done-pointer to `ingest_fundamentals.py` / `pit.py` plus the WARN-taxonomy traps.

---

## MAJOR — misleading, contradictory, or seriously unclear

### M1. `HANDOFF.md` §2 lines 66–70 falsely accuses a correct document of an arithmetic error
"…1,606 of the 6,746 rows have no sentiment label for that reason; the report text says 1,607, **a known 1-off arithmetic slip in `full_run_report.md`**, not a data problem."

**Evidence (recomputed from `data/labels.parquet`):** null-sentiment rows = **1,607** = 1,606 RISK_FACTORS + 1 refusal chunk. `full_run_report.md:320` says exactly that: "1,607 n/a = 1,606 RISK_FACTORS never asked + 1 refusal chunk." Both numbers are right against different denominators (6,747 vs 6,746); the "slip" claim is the error, and acting on it would introduce a real one.

**Fix:** delete the parenthetical (three lines, and it impugns a correct doc).

### M2. `HANDOFF.md` §2 line 56 and §8 line 754 mis-describe the artifact `features.py` joins on
Both read "28,504 | **every occurrence of every deduplicated paragraph**".

**Evidence (recomputed):** `data/paragraph_occurrence_map.parquet` has **one row per canonical paragraph** — 28,504 rows, 28,504 distinct `paragraph_id`s — with occurrences held in the list columns `occurrence_tickers` / `occurrence_accession_numbers`. Total occurrences = `sum(n_occurrences)` = **42,577**. `REDTEAM_WEEK3.md` finding #3 gets this right ("28,504 canonical paragraphs"). A features author expecting a pre-exploded occurrence table silently under-counts attributions 42,577 → 28,504.

**Fix:** "28,504 deduplicated paragraphs; 42,577 total occurrences held in list columns — explode before joining."

### M3. `HANDOFF.md` §2a trap (b) (lines 193–197) implies `ProfitLoss` data is available. It is not.
"tag migrations mid-window: MA/OXY `NetIncomeLoss`→`ProfitLoss`, SLB `OperatingIncomeLoss`→`ProfitLoss` (mid-2024) … numeric features **must use alias/migration families, not single tags**."

**Evidence (verified):** `ProfitLoss` is absent from `fundamentals.parquet`'s 13 concepts and from `CONCEPTS` in `ingest_fundamentals.py`; the DB WARN rows say so explicitly ("not pulled here — outside the fixed concept list"). `features.py` **cannot** build that migration family from this artifact without a re-ingest.

**Fix:** state that the alternate tags are documented but **not ingested**, and that using them requires a re-ingest (free, EDGAR-only, no API spend).

### M4. `ingest_fundamentals.py` lines 121–122 state a falsehood the module's own validator contradicts; `HANDOFF.md` inherits it
`# (RevenuesNetOfInterestExpense is GS-specific in this universe -- see the comment on CONCEPTS above.)`

**Evidence (recomputed):** `RevenuesNetOfInterestExpense` appears for **GS (172 rows) and JPM (149 rows)**. The module's own `revenue_alias_consistency` WARN for JPM reads "Multiple revenue aliases reported in-window: `['Revenues', 'RevenuesNetOfInterestExpense']`". `HANDOFF.md` §2a line 199 inherits it as trap (d) "GS revenue = `RevenuesNetOfInterestExpense`" — which would lead `features.py` to special-case GS and mis-handle JPM.

**Fix:** "GS **and JPM**"; update HANDOFF trap (d).

### M5. `HANDOFF.md` gives three incompatible states for one test file
§2a line 217: "`test_submit_variant_wiring.py` has 4 failures … Pre-existing, untouched." §2a line 245: "4 stale-v1 tests rewritten against the v2 verifier + 5 pinning tests." §4 line 483: "25/25 pass."

**Evidence:** I ran it — **25 passed, 0 failures**. (Caveat: this file is on the excluded in-flight list; the count could move, but the internal contradiction inside HANDOFF is real either way.)

**Fix:** delete the lines 217–219 bullet.

### M6. `HANDOFF.md` §2a "IMMEDIATE NEXT STEPS (in order)" (lines 262–276) is numbered 1, 2, **4** — and item 4 contradicts the paragraph above it
Item 3 is missing from a list explicitly labelled "(in order)". Item 4 lists four latent MINORs as open — "the adjudication view doesn't handle parse-failed rows", "the `sample_400.json` default … is the stale Aug-11 export", "no test for `build_adjudication_view.py`" — while lines 240–244 say "**all four latent MINORs fixed** … `sample_400.json` regenerated byte-identical … 36 new tests in `test_build_adjudication_view.py`".

**Evidence (verified):** `spotcheck/test_build_adjudication_view.py` exists and `pytest spotcheck/` = **51 passed**; `build_adjudication_view.py`'s current docstring itself says `sample_400.json` is "verified content-identical".

**Fix:** renumber 1–2; delete item 4.

### M7. `HANDOFF.md` §8 (the file map) is a full phase behind the tree and contradicts §2/§2a in six rows
This is the only map of the repo, and it is where a newcomer orients. One pass over §8 fixes all of it:

**Contradicted rows (all verified false):**
- line 778 `compute_agreement.py` — "**Section 3 currently drops Tier D — fix before relying on it**". Fixed; §2 line 357 and §6 line 550 both already say so.
- line 785 `owner_shortlist.md` — "**THE pending human input** as of 2026-08-18". §2a line 147: "STEP 1 IS COMPLETE. All 1,222 judgments recorded."
- line 786 `combined_judgments.csv` — "`source`: model-auditor / model-adjudicator / **owner-pending**. Owner-pending rows are blank until the owner rules." Recomputed: `source` = model-auditor 1023 / model-adjudicator 95 / **`owner` 104**; **zero** `owner-pending`; **zero** blank judgments (agree 1031 / disagree 191). §2a line 133 carries the same stale description inside §2a itself.
- line 714 `INGESTION_NOTES.md` — "No Week 3 (`chunk.py`) section exists yet." A Week 3 section exists at `INGESTION_NOTES.md:802`; §2a line 259 says it was added.
- line 759 `MODEL_CHOICE.md` — "Not re-verified against a live license page" vs §2a line 248 "license verified live Apache-2.0 (2026-08-18)".
- line 747 `filings_metadata.db` — table list omits `fundamentals_validation_problems` (verified present in the DB).

**Missing rows:** `raw/` (line 751) lists four subdirectories; the tree has **six** (`companyfacts/`, `prices/` missing). Root table omits `pit.py`, `ingest_fundamentals.py`, `ingest_prices.py`, `price_client.py`, `RED_FLAGS_LIMITATION.md`, `requirements-quant.txt` and six root test files. `data/` omits `fundamentals.parquet`, `prices.parquet`, `features.parquet`, `PRICES_NOTES.md`. `spotcheck/` omits `agreement_report.txt` (the pipeline's final deliverable), `owner_final_round.md`, `test_build_adjudication_view.py`. `finetune/` omits `MLX_FEASIBILITY.md`. `price_client.py` and `ingest_prices.py` are not named **anywhere** in HANDOFF, though §2 lines 202–216 describe their output at length.

### M8. `HANDOFF.md` §2's DISCOVERY staleness pointer (lines 333–338) is inaccurate on two counts
It says DISCOVERY has "**one** 2026-08-11 amendment layer" and "does not reflect … **the label-auditor spot-check protocol**."

**Evidence (verified):** `DISCOVERY.md` carries a **2026-08-18 READER NOTE** (lines 1–6) *and* a dated **2026-08-18 amendment** inside the §6 risk register (line 303) that reports the completed spot-check, 63.4%, 36.6%, the Tier D figure and a pointer to `RED_FLAGS_LIMITATION.md`. §2a line 178 acknowledges that amendment; the pointer does not. §8 line 710 repeats "one 2026-08-11 amendment layer".

**Fix:** "two amendment layers (2026-08-11, 2026-08-18)"; drop the spot-check clause. (Everything else in the pointer is accurate and is correctly preserved audit trail — not a finding.)

### M9. `HANDOFF.md` §2's `spotcheck/README.md` pointer (lines 350–356) marks a *current* section stale and misses the genuinely stale ones
It lists "the GOING_CONCERN finding's supporting counts" as pre-relabel. **They are not:** `spotcheck/README.md` lines 166–191 read "Across all **162** distress positives … (post-relabel; this was 143 before the 2026-08-11 corrective re-label)" with LIQUIDITY_STRESS/HYPOTHETICAL **151**, /REALIZED **9**, ACCOUNTING_RESTATEMENT/HYPOTHETICAL **2**, GOING_CONCERN **0** — recomputed from `labels.parquet`, exact match on all four.

Meanwhile the pointer omits four genuinely stale items in the same file: the "all **143** distress positives present" assertion (line 263), the "**Section 3 — per-tier (A/B/C) breakdown**" description (line 241, now A/B/C/D), the Files table (M10), and the CHK section (C6).

**Fix:** swap them.

### M10. `spotcheck/README.md`'s Files table and walkthrough predate the entire pipeline the directory is now about
The "Files" table (lines 28–42) lists 12–13 pre-2026-08-18 artifacts and **none** of: `auditor_verdicts.json`, `auditor_disagreements.json`, `adjudicator_verdicts.json`, `adjudicator_batches/`, `build_adjudicator_batches.py`, `adjudication_workflow.js`, `build_adjudication_view.py`, `adjudication_template.html`, `adjudication_174.html`, `merge_adjudications.py`, `build_owner_shortlist.py`, `owner_shortlist.md`, `owner_final_round.md`, `combined_judgments.csv`, `agreement_report.txt`, `test_build_adjudication_view.py`. It presents itself as the directory map. The "How the owner runs the review" walkthrough (lines 193–220) describes a path that was not the one actually taken, and nothing anywhere states the pipeline's ordering.

**Fix:** regenerate the table and add a five-line ordered pipeline block: `sample_400` → `auditor_verdicts` → `auditor_disagreements` (174) → `adjudicator_batches` → `adjudicator_verdicts` (199 field-cases) → `owner_shortlist` → `owner_final_round` → `combined_judgments.csv` → `agreement_report.txt`. Replace the walkthrough with two lines on what actually ran and where the results live.

### M11. The command that produced the headline rates is recorded nowhere, and the only documented invocation cannot run
`spotcheck/README.md` lines 225–226 and `compute_agreement.py`'s docstring lines 6–7 both give `--input sample_400_review_export.csv` / `.json`. **Neither file exists** (verified by listing `spotcheck/`). The real input is `combined_judgments.csv`. `agreement_report.txt` carries **no run date and no input filename** in its header, despite being the cited source for the headline rates in `HANDOFF.md`, `RED_FLAGS_LIMITATION.md`, `DISCOVERY.md` and the planned model card — which are therefore not reproducible from the documentation.

**Fix:** change both usage examples to `python3 compute_agreement.py --input combined_judgments.csv --format auto`, and stamp the command + run date into the report header.

### M12. `spotcheck/owner_shortlist.md` and `spotcheck/owner_final_round.md` read as ~110 outstanding decisions that are settled
Both are decision forms full of unticked `**Your ruling:** [ ] agree [ ] disagree [ ] unsure` checkboxes with no outcome recorded. `owner_final_round.md` line 2: "These are the only judgments left". Both were fully ruled 2026-08-18 (`HANDOFF.md` lines 147–153; `combined_judgments.csv` has `source=owner` on 104 rows, 85 bulk-ratified / 19 explicit). Neither file appears in HANDOFF's staleness list — and this has already propagated: the owner's own memory index still records `owner_shortlist.md` as "the pending human input."

**Fix:** a one-line banner at the top of each — `RESOLVED 2026-08-18 — rulings recorded in combined_judgments.csv; rates in agreement_report.txt.`

### M13. `data/canary_comparison.md` has no staleness pointer anywhere and reads as a live recommendation
It is in the stable set but appears in neither `HANDOFF.md` §1's audit-trail list nor §2's staleness list; §8 line 749 gives it only "Canary-run comparison notes." Its §5 (line 186) reads "**Use `disabled` (`thinking: {"type": "disabled"}`, `max_tokens=800`) for the full 6,747-request run**" — the corpus was labeled at **`max_tokens=4000`**. Its projections (~$38.55) versus the real $18.05, and its rationale ("the project's $50 total ceiling", "the QLoRA fine-tune still needs GPU budget") are all superseded. A newcomer takes 800 as the corpus config. (Its *measured* numbers are correct and worth keeping — the lens reproduced 35/38 sentiment, 9/9 guidance, 41/50 exact red-flag set, 50/50 distress from `labels_canary_{disabled,adaptive_low}.parquet`.)

**Fix:** add the same dated READER NOTE banner `DISCOVERY.md` and `full_run_report.md` carry; add it to HANDOFF's audit-trail list and give §8's row a status word.

### M14. `HANDOFF.md` §8 line 712 designates `full_run_report.md`'s FINAL section "ground truth" without carving out its budget line
That FINAL section's spend table (line 332) reads "**Total | $33.51 of $50** ($16.49 remaining)" — precisely the framing `HANDOFF.md` §5 lines 290–291 forbids ("not 'spend the remaining $16.49'"). The file's own READER NOTE flags the stale `$23.45` and `143` figures but is silent on the budget line inside the section it directs you to.

**Fix:** amend the §8 pointer and the reader note: "the FINAL section is ground truth *except* its `$50` / `$16.49 remaining` framing, superseded by HANDOFF §5 — no further spend."

### M15. `full_run_report.md`'s reader note over-promises supersession; no current per-category red-flag counts exist anywhere in the stable set
The note says the FINAL section "**supersedes every earlier number**", citing only spend and distress count. But §3's red-flag table, the modality split and the "≥1 flag" rate are all pre-relabel, and the FINAL section never restates them:

| | doc says (§3, lines 98–109) | current (`labels.parquet`) |
|---|---|---|
| LEGAL / MARGIN / DEMAND | 2,079 / 1,534 / 1,186 | **2,305 / 1,737 / 1,326** |
| IMPAIRMENT / TRADE / SUPPLY | 966 / 683 / 580 | **1,019 / 713 / 616** |
| Modality | 3,068 HYP / 3,960 REAL | **3,512 HYP / 4,204 REAL** |
| Rows with ≥1 flag | 4,008/6,746 (59.4%) | **4,416/6,746 (65.5%)** |

I confirmed the doc's figures match `labels_pre_relabel.parquet` exactly (instance basis), and the current figures against `labels.parquet`. `RED_FLAGS_LIMITATION.md` implication 3 tells Week 5 to "normalize by section composition using recomputed post-relabel counts" — those counts are published nowhere.

**Fix:** add the six current per-category counts + the modality split to the FINAL section, or narrow the reader note to name which numbers have no current replacement.

### M16. `RED_FLAGS_LIMITATION.md` implication #1 (lines 130–133) applies a deliberately non-representative rate as a corpus-wide error rate
"Every red-flag-derived feature inherits a measured **36.6% set-level error rate** (63.4% agreement). Report this next to any red-flag feature importance or ablation claim."

146/399 is correct **for the sample**, but the sample is by construction an oversample: Tier A = all 162 distress positives, Tier B = thin-category quotas, Tier D = the config-disagreement set. `agreement_report.txt`'s own TIER-B CAVEAT says "Any agreement rate pooled across all tiers is therefore **NOT representative** … use Tier C." The base-rate slice's red-flags-only rate is **75.0% (25.0% error), n=36, [58.9, 86.2]**. The "fails the 0.70 bar" verdict survives (Tier C's lower bound is 58.9%), but the point estimate carried into `features.py` and the model card is likely overstated by ~11 points.

**Fix:** state 36.6% as *sample-pooled*, and give the Tier C figure with its n and CI immediately next to it.

### M17. `red_flags` 63.4% is an **exact-set-match** rate, and no doc says so where it matters
`agreement_report.txt` Section 1, `HANDOFF.md` §2a, and `RED_FLAGS_LIMITATION.md`'s disposition table all print 63.4% beside sentiment 94.6% and guidance 95.2% as if comparable. It is not: one added or dropped category on a four-category chunk scores the whole chunk as a disagreement. `data/canary_comparison.md` §3 makes exactly this point (per-category 92–100% vs exact-set 82%). Only `RED_FLAGS_LIMITATION.md` uses the phrase "set-level" — once — while directing Week 5 to report 36.6% next to per-category feature claims, where it overstates error.

**Fix:** label the metric "exact-set match" in the disposition table and in `agreement_report.txt` Section 1, and give a per-category error figure alongside it — the existing 61 spurious / 76 missed / 43 wrong-modality decomposition already supports one.

### M18. `spotcheck/README.md:20` calls the pass "the owner's 400-example **human** spot-check" — the project's own §7 rule forbids this
`HANDOFF.md` §7's first hard rule: "**Never fabricate or simulate a human judgment.** `label-auditor` verdicts are model verdicts … never … implied to be the owner's own adjudication." The 400-chunk pass was run by `label-auditor` (a model); the owner ruled only the 104-case shortlist. The README's `✅ READY` banner compounds it, addressing the owner in the second person ("**You** judge these blind") for work that has already been done by a model and is complete.

**Fix:** drop "human" from line 20; replace the READY banner with a COMPLETE banner stating the three rater layers by provenance.

### M19. `labeling_rubric.md` — the authoritative spec — has no pointer to the revision now proposed against it
§9's revision log (line 290) still reads "**No spot-check-driven revisions yet** — those land after the owner's 400-example spot-check (Week 3 DoD)." The spot-check ran and produced exactly that: three concrete §4/§6 additions drafted in `RED_FLAGS_LIMITATION.md` lines 87–105, "PENDING owner ratification". The link is one-directional, so anyone editing the rubric under HANDOFF §7's sync rule will never find the pending proposal. §5's open question ("a decision about whether to exclude this tier … is made later") is also settled — excluded, per §7.

**Fix:** add a §9 line — "v1.2 (proposed 2026-08-18, NOT ratified, NOT applied, no re-label) — see `RED_FLAGS_LIMITATION.md`" — and close §5's open decision.

### M20. `HANDOFF.md` §1's audit-trail list contradicts §2 and §8, and doesn't correspond to §2's list
§1 (lines 3–10) groups `ROADMAP.md` with docs "preserved as an **audit trail** … several have gone stale"; §2 line 342 and §8 line 709 both say ROADMAP is **current**. Of §1's five named docs, only `DISCOVERY.md` has a §2 staleness entry — `full_run_report.md`, `REDTEAM_WEEK3.md`, `INGESTION_NOTES.md` have none — while §2 adds three docs §1 never names. Compounding it, the "treat `ROADMAP.md` as current" paragraph is indented **inside** the DISCOVERY.md bullet, so it reads as being about DISCOVERY.

**Fix:** drop ROADMAP from §1's list; make §1's and §2's lists one-for-one; unnest the ROADMAP paragraph.

### M21. Tier letters are load-bearing shorthand used before definition, in every doc that reports them
`HANDOFF.md` first uses "worst in Tier D (0.517)" at line 98 and never defines Tier D (line 314 gives composition counts only). `agreement_report.txt` Section 3 reports four tiers and defines only B and C. `spotcheck/README.md` has no Tier D definition at all. Only `ROADMAP.md` Phase A and `RED_FLAGS_LIMITATION.md` gloss them. Since C3 and M16 both turn on which tier means what, this is not cosmetic.

**Fix:** a four-line legend — A = all distress positives · B = thin-category oversample · C = proportional base-rate fill · D = config-disagreement set — in `HANDOFF.md` §2a and in `agreement_report.txt`'s header.

### M22. `HANDOFF.md` §2a is a 190-line wall that buries its own conclusion and self-supersedes inside itself
Lines 90–276. The only forward-looking content sits at the very bottom behind completed-work narration; line 133's description of `combined_judgments.csv` ("owner-pending 104, blank, never imputed") is contradicted by line 147 in the same section; several bullets restate §3's decision-log entries at length.

**Fix:** open §2a with a six-row status table (Step 1 ✅ / Step 2 ✅ / fundamentals ✅ / prices ✅ / features+backtest ⚠️ fix-in-flight / go-no-go ⬜) followed immediately by next steps; move the narration §3 already holds. **Do not** cut the Phase C traps, the config-sensitivity numbers, or the agreement rates — those are load-bearing and appear nowhere else.

---

## MINOR — concision, style, small confusions

**Numbers I recomputed and found off:**

1. `HANDOFF.md` §2a:189 — "all **six** WARN categories empirically verified." The DB has **five** distinct WARN `check_name`s (`concept_structurally_absent` 20, `revenue_alias_consistency` 8, `concept_tag_migrated_before_window` 7, `concept_quarterly_coverage_midwindow_migration` 4, `concept_quarterly_coverage_partial` 1 = 40 ✓). Fix: "five."
2. `HANDOFF.md` §2a:184 — "**9,700** facts carry multiple filings." Not reproducible under any obvious grouping: `(ticker, concept, unit, period_start, period_end)` → 12,569 multi-filing facts; adding `fp` → 13,968; adding `fy`+`form` → 82. Fix: publish the grouping key, or recompute.
3. `HANDOFF.md` §2a:192 — "`OperatingIncomeLoss` is **structurally absent** for 10/25." Two defensible counts and the wording matches the wrong one: the `concept_structurally_absent` WARN fires for **9** tickers; **10** have zero *in-window* coverage (those 9 + JNJ, whose last `OperatingIncomeLoss` was 2015-05-01 under `concept_tag_migrated_before_window`). SLB has partial in-window coverage. Fix: "zero in-window coverage for 10/25 (9 never-reported + JNJ pre-window migration); SLB partial."
4. `HANDOFF.md` §6:556 — Definition of done says "every disagreement plus **the 8 distress chunks**" — the exact typo the same section flags and corrects 17 lines earlier (line 537: "an earlier draft of this sentence said '8', a typo — the 9+2 arithmetic is correct"). Fix: 8 → 11.
5. `HANDOFF.md` §3:442 — "**96 rulings**, `source=owner`" is a correct point-in-time snapshot superseded by §2a's 104, with nothing saying so. Fix: append "(→ 104 after the 8-case final round; see §2a)."
6. `HANDOFF.md` §8:713 — "`REDTEAM_WEEK3.md` … 8 findings, 3 with owner-verified resolutions, **4** still open." 3 + 4 = 7. Verified: 8 findings; #1, #5, #8 carry RESOLUTION/CORRECTION blocks; #2, #3, #4, #6, #7 = **5** remain (though #6 is a "no issue" finding). Fix: 4 → 5, or say which is neither.
7. `HANDOFF.md` §2a:106 — "**Five are one repeated PG** 'working-capital deficit + affirmed adequacy' passage." Five of the nine are PG, but their briefs in `owner_shortlist.md` quote five different figures ($10.2B / $12.8B / $10.1B / $8.2B / $9.0B) — the same recurring disclosure across quarters, not one deduplicated passage. Fix: "the same recurring PG disclosure across quarters."
8. `labeling_rubric.md:3` — "**Version 1** (Week 3)" while its own §9, `HANDOFF.md` §8:715 and `ROADMAP.md`:30 all call it v1.1. Fix: "Version 1.1".
9. `finetune/SPLIT_DESIGN.md` §4:98 — "`LOWERED`/`MAINTAINED`/`RAISED` have only **14/33/35** occurrences." Pre-relabel; final `labels.parquet` = **14/34/34** (total 83 unchanged).
10. `finetune/SPLIT_DESIGN.md` §6:222 — "**12 companies** carry all the non-`NONE` guidance labels." Recomputed: **11** (ABBV, COP, HD, JNJ, KO, OXY, PFE, PG, UNH, WMT, XOM).
11. `finetune/SPLIT_DESIGN.md` §6:211 — "`home_filing_date` ranges from **2023-08-15** to 2026-08-07 on both sides." Live: train 2023-08-**16** → 2026-08-07; eval 2023-08-15 → 2026-08-07. The point (both sides span the range) stands.
12. `ROADMAP.md` History:36 — "truncating **37.6% (2,528/6,747)**." 2,528/6,747 = **37.5%**; 37.6% belongs to a different numerator (2,537 results that hit exactly 500 tokens, `full_run_report.md:28`). Fix: pair 37.5% with 2,528.
13. `data/PRICES_NOTES.md` §1 vs `price_client.py:22` — PRICES_NOTES says the Stooq bot-gate was confirmed "across **five** different tickers (`nvda`, `aapl`, `msft`, `xom`, tested individually)" — four listed; `price_client.py` says "across **three** different tickers (aapl/msft/xom)." Fix: reconcile to one number.
14. `spotcheck/agreement_report.txt` Section 5 — "disagreement notes (**72**)" prints directly under "red_flags — agreement 63.4%", which has **146** disagreements. Verified: the 72 are exactly the owner-sourced rows; the 74 `model-adjudicator` rows carry no `field_note` (their briefs live in `adjudicator_verdicts.json`). Fix: "72 of 146 disagreements carry notes; adjudicator-resolved rows carry briefs in `adjudicator_verdicts.json`."
15. `spotcheck/README.md:263` — "all **143** distress positives present" (stale; 162) and `:241` "**Section 3 — per-tier (A/B/C) breakdown**" (stale; now A/B/C/D).

**Docstrings out of sync with their own code:**

16. `ingest_fundamentals.py:44` — "**All three** commonly-seen aliases are extracted and stored AS-IS." `CONCEPTS` (lines 88–106) and `REVENUE_CONCEPTS` (123–128) carry **four**. Fix: "all four", naming the GS/JPM case in one clause (see M4).
17. `ingest_fundamentals.py:6` anchors to "`HANDOFF.md` §2a 'IMMEDIATE NEXT STEPS' **item 1**" — that item is now about `features.py`/`backtest.py`, and the list's numbering is broken (M6). Fix: cite ROADMAP Phase C or §2a "Phase C progress" instead of a positional list item.
18. `spotcheck/merge_adjudications.py` docstring — stale on all three outputs: "all **174** model adjudications" (174 chunks / **199** field-cases, per `HANDOFF.md` §8:783); "`owner_shortlist.md` … (owner input **pending**)" (superseded by `build_owner_shortlist.py`; not pending); "combined_judgments.csv — owner-pending rows left blank" (none remain). Fix all three; add "superseded by `build_owner_shortlist.py`".
19. `spotcheck/compute_agreement.py` docstring — explains Tier B and Tier C but never mentions Tier A or Tier D though Section 3 now reports all four; describes its input as "the owner's completed review export" when the real input is `combined_judgments.csv` (pairs with M11).
20. `spotcheck/agreement_report.txt` Section 5 self-contradicts in one sentence: "override with `--ci-lower-bound-bar` … (not exposed as a CLI flag yet; edit `CI_LOWER_BOUND_BAR`)." Fix: drop the first clause.
21. `pit.py` and `ingest_fundamentals.py` justify decisions by citing "**the task description that commissioned this file**" / "the commissioning task" — an artifact not in the repo, so the reasoning cannot be checked. Fix: cite `HANDOFF.md` §3/§2a, or restate the requirement inline.
22. `data/PRICES_NOTES.md` lines 8–11, `price_client.py:6-8`, `ingest_prices.py:6-8` all say the file "does not touch `edgar_client.py` … owned by a **concurrently-running** data-engineer session." That session is over; the sentence now reads as an unexplained architectural boundary. Fix: delete.
23. `price_client.py:4-6` quotes `HANDOFF.md` §3 non-verbatim inside quotation marks. HANDOFF:452 actually reads "a free daily-price provider (Stooq-class CSV download), cached and versioned under `data/raw/` like the EDGAR data." Fix: paraphrase without quote marks, or quote exactly.
24. `finetune/PROMPT_TEMPLATE.md:30` cites "`ROADMAP.md` **Week 3**"; ROADMAP has no Week 3 section — only a History bullet. Fix: cite `labeling_rubric.md` §8 / `DISCOVERY.md` §5.

**Concision and orientation:**

25. **The CHK-8e69547e0900a8dd story is told at length in seven places** (`HANDOFF.md` §2 table; `full_run_report.md` §1, §4.5, FINAL; `REDTEAM_WEEK3.md` #1 + resolution; `SPLIT_DESIGN.md` §1; `spotcheck/README.md`; `build_sample.py` docstring) — two of which disagree (C6). Fix: one canonical paragraph (`full_run_report.md` FINAL) + one-line pointers.
26. **The Stooq→Yahoo sourcing narrative and the split-vs-dividend adjustment writeup each appear three times at near-full length** (`PRICES_NOTES.md` §1–2, `price_client.py` docstring, `ingest_prices.py` docstring) plus a 10-line restatement in `HANDOFF.md` §2a. Fix: full writeup stays in `PRICES_NOTES.md`; cut both docstrings to three lines + pointer.
27. **The six-category config-sensitivity delta list is restated verbatim four times** (`HANDOFF.md` §2, `ROADMAP.md` Phase E, `full_run_report.md` FINAL, `DISCOVERY.md` §6). The owner's ratification requires the *headline* ("red-flag labels are ~22% config-sensitive") to travel into every downstream doc — it does not require the delta list to. Fix: keep the headline sentence everywhere; keep the delta list in one place.
28. **One activity, five names; one role word, two owners.** "spot-check" / "second-rater pass" / "label-auditor pass" / "audit" / "the owner's human spot-check". Roles: `ROADMAP.md` Phase A says "owner adjudicates disagreements" while `HANDOFF.md` §2a/§3 assign "adjudicate" to the third-rater model and give the owner "rules"/"ratifies". "Blind" carries two meanings: `ROADMAP.md`:67–69 says the rater is explicitly *not* blinded from the stored label; `spotcheck/README.md`:11–13 says "You judge these blind." Fix: fix one vocabulary in `HANDOFF.md` §2a (second rater = `label-auditor`; third rater = `label-adjudicator`; owner = ratifier), propagate, define "blind" once.
29. `RED_FLAGS_LIMITATION.md`:69–85 — a section headed "The **three** owner-ratified ambiguity principles" lists P1, P3, and a MARGIN_COST_PRESSURE boundary that is not a numbered principle, then parenthetically relocates P2 elsewhere. Meanwhile `owner_shortlist.md` Part A defines the three as P1/P2/P3, and `HANDOFF.md` §2a:174 says "the owner-ratified **P1/P3**" (two). Three framings of one set. Fix: list P1/P2/P3 in order with P2's one-line statement in place; demote the MARGIN boundary to a corollary of P3.
30. `HANDOFF.md` corpus table (lines 50–57) gives 6,747 / 884 / 28,504 without ever stating the data model relating them. A newcomer cannot tell what a "chunk" is or why 28,504 > 6,747. Fix: one sentence above the table (884 extracted filing-sections → deduplicated paragraphs → ~350-word chunks). Same for "every-occurrence attribution" (line 56, defined only in §3) and "PIT" (line 187, never expanded).
31. `ROADMAP.md` has no date stamp, and its subagent roster (lines 11–13, 264–269) omits `label-adjudicator`, which exists at `.claude/agents/label-adjudicator.md` and performed the bulk of Phase A.
32. `data/full_run_report.md` §6 points at "`spotcheck/README.md`'s **hold banner**" — that banner was replaced by a "✅ READY" banner, so the pointer now resolves to the opposite message. Its READER NOTE enumerates only two stale facts and doesn't cover this. Fix: one clause in the READER NOTE.

---

## NOTE

- **N1.** `owner_shortlist.md`:10 — "3 principles (cascading over 40 field-cases) + 11 high-stakes chunks + 62 individual items" sums to 113 slots but covers **104** distinct field-cases (9 of P2's 14 members are the same field-cases as 9 of the 11 Part B entries). 104 exactly matches the `source=owner` row count. One clause would reconcile the arithmetic.
- **N2.** The config-sensitivity deltas (LEGAL +211, MARGIN +203, DEMAND +138, IMPAIRMENT +51, SUPPLY +35, TRADE +27) are **correct**, on a per-chunk-category-presence basis — I reproduced all six exactly. Counted as flag *instances* (the basis `full_run_report.md` §3's table uses) they are +226/+203/+140/+53/+36/+30. Stating the basis once would stop a reader mixing the two.
- **N3.** `HANDOFF.md` §2a:98 cites the auditor's raw Tier-D red_flags rate as 0.517 and §2a:161 the final Tier-D figure as 71.2%, with nothing reconciling them — different populations at different pipeline stages, and different field scopes. One clause would stop a reader concluding Tier D improved after adjudication (red-flags-only it did not: 53.3%).
- **N4.** `HANDOFF.md` §2a:244 — "`adjudication_174.html` rebuilt, **174/199** unchanged" mixes units (174 chunks, 199 field-cases) without saying which is "unchanged."
- **N5.** `REDTEAM_WEEK3.md` carries no date and no reader note, unlike `DISCOVERY.md` and `full_run_report.md`, which both got 2026-08-18 banners; it is named in §1's audit-trail list but has no §2 entry, and its finding #4 counts are pre-relabel (corrected only in `HANDOFF.md` §6 Step 3). A matching reader note would close the last gap in the banner convention.
- **N6.** `data/features_report.md` is unclassified — in neither the in-scope set nor the excluded list, unmapped in §8, generated by the concurrently-rewritten `features.py`. Route to the second pass.
- **N7. Charter compliance is clean.** No trading-bot drift, investment-advice framing, or overstated performance claim anywhere in the in-scope set. `ingest_prices.py`'s docstring explicitly disclaims trading/order logic; `PRICES_NOTES.md` §2 states the dividend-yield bias *against* the target rather than assuming it away; `RED_FLAGS_LIMITATION.md` leads with the category that failed. All three lenses produced zero findings here.
- **N8. Cross-reference targets are healthy.** Every backticked filename in the in-scope docs resolves against the tree (the only unresolved token is `MODEL_CARD.md`, correctly a planned deliverable), and every section reference checks out. The failures are all in *descriptions* and *status*, not in *links*.

---

## Dropped findings (and why)

- **"§2a's next step is gated on price ingestion landing, which already happened"** (raised by two lenses) — **stale**. `HANDOFF.md` was rewritten mid-review; item 1 is now the Phase C fix+verify workflow. The 1-2-4 numbering defect and the contradictory item 4 survive and are kept as M6.
- **"`build_adjudication_view.py`'s docstring says `sample_400.json` is stale vs the Aug-18 parquet"** — **wrong against the current file**. Its docstring now reads "verified content-identical."
- **"Cut the 22.2% config-sensitivity headline to one place"** — **overruled by the accuracy lens**. The owner ratified that the headline limitation "must appear in the eventual model card, not just internal docs" and carries into every downstream doc. Scoped down to the six-category delta list only (MINOR 27).
- **Staleness in `DISCOVERY.md`, `data/full_run_report.md`, `REDTEAM_WEEK3.md` as such** (e.g. DISCOVERY's live "$0/$50" tally, full_run_report's pre-relabel §3, REDTEAM #4's pre-relabel counts) — **excluded by the audit-trail convention**. Only pointer accuracy is in scope, which is why M8, M9, M14, M15 and N5 are kept and the underlying staleness is not.
- **`HANDOFF.md` §2's `finetune/README.md` staleness pointer** — the target file is on the excluded in-flight list; the pointer's accuracy can only be judged after the rewrite. Routed to the second pass.
- **Requests to condense §2a's completed-work narration wholesale** — partially overruled. §2a's Phase C traps, agreement rates and spend figures exist nowhere else; only the material §3 duplicates should move (M22).

---

## Top 5 fixes by value

1. **Repair `HANDOFF.md` §2 + the header (C1, C2).** One block deletion and two sentences. This is the difference between a source-of-truth doc that answers "what state is this in?" correctly and one that answers it twice, incompatibly. Everything else a newcomer does flows from these two paragraphs.
2. **Correct the red-flag tier rates in all three docs (C3), and qualify 36.6% as sample-pooled next to the Tier C figure (M16, M17).** These are the numbers headed for `features.py`, the ablation tables and the model card. They are wrong by ~18 points per tier and overstated by ~11 points corpus-wide, and the exact-set-match basis is never named.
3. **Regenerate `finetune/SPLIT_DESIGN.md` §5 and §6 from the live split (C4, C5).** A file badged "✅ CURRENT" whose own body says "this section is stale" and whose ticker-presence bullet is false in both directions is worse than no file. One `split.py` re-run plus a paste fixes it.
4. **Do one pass over `HANDOFF.md` §8 (M7).** Six rows contradict §2/§2a and roughly twenty artifacts are unmapped, including all four Phase C modules. It is the only map of the repo and it is a full phase behind the tree.
5. **Close the loop on the spot-check pipeline's own docs (C6, M10, M11, M12, M18).** Fix the CHK section, regenerate the Files table with the pipeline ordering, record the real `compute_agreement.py` command and stamp the report, banner the two owner decision files as resolved, and drop the word "human". This is the directory the headline finding of the whole project came out of, and today it reads as unstarted work with an unreproducible result.

---

## Verdict against the owner's bar

**The documentation does not yet meet the bar — but the gap is narrower than the finding count suggests, and it is concentrated in status rather than substance.** On *informative* and *useful* the set is genuinely strong: the epistemic discipline is unusual and real (model verdicts are never dressed as human ones in the analytical docs, CIs travel with every rate, the Tier-B non-representativeness caveat is asserted in code, `RED_FLAGS_LIMITATION.md` leads with the category that failed, and the charter's non-goals are honored without exception — N7). Almost every load-bearing number I recomputed was right; the arithmetic backbone of this project is sound. Where it fails is *aligned* and *accurate-in-status*: the same fact is reported in three or four places at three or four different vintages, and the reader has no way to tell which is live — the spot-check is simultaneously complete and not started (C1), the adjudication is 159/174 and 174/174 (C2), the Tier-D bug is fixed and pending (C7, M7), the owner's rulings are recorded and outstanding (M12, M7), and a file badged CURRENT declares itself stale (C5). Two documents state numbers that are simply false (C4, C6) with no pointer to warn anyone. On *concise* and *no fluff* it is mixed: individual paragraphs are tight and well-reasoned, but the same narrative is retold at near-full length in three to seven places (MINOR 25–27), and §2a has grown into a 190-line wall that buries the one thing a next session actually needs (M22). On *intuitive*, `HANDOFF.md` is correctly the entry point and its non-goals section is the best-organized writing in the set — but the two questions a newcomer most needs answered, "what state is this in" and "what do I do next", are the two it currently gets wrong. The seven CRITICALs are all mechanical single-edit fixes; clearing them plus the top five above would move this set over the bar in a single pass, with no re-analysis required.

---

## Excluded in-flight files still needing their second-pass review

Not reviewed here, per instructions — hand these to the second pass once the concurrent rewrites land:

- `README.md`
- `LIMITATIONS.md`
- `INGESTION_NOTES.md`
- `finetune/README.md`
- `finetune/MODEL_CHOICE.md`
- `finetune/MLX_FEASIBILITY.md`
- `data/backtest_report.md`
- `features.py`, `backtest.py` (including their module docstrings)
- `test_submit_variant_wiring.py`
- everything under `.claude/`

**Add to that list:** `data/features_report.md` (N6) — generated by `features.py`, unclassified in the brief, and unmapped in `HANDOFF.md` §8. Also re-check `HANDOFF.md` §2's `finetune/README.md` staleness pointer and §8's `MODEL_CHOICE.md` / `INGESTION_NOTES.md` rows (M7) after those files settle, since their accuracy depends on the rewritten targets.