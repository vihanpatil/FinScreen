# Red-team review of the G3 ratification package — 2026-09-11

> Saved verbatim by the main session from the `red-team-reviewer` agent (Opus, read-only). Convened after the pre-registration reached RATIFICATION-READY and the scorecard code landed, before the owner is asked for "ratify". **Verdict: NOT SAFE TO ASK FOR RATIFICATION** in that form. The main session's disposition of every item is appended in §"Disposition" at the end.

## Freeze / safety verification (all clean)

- `python3 backtest_e2.py` → **exit 2**, "BLOCKED: … G3_RATIFIED.json does not exist"; nothing fitted.
- `python3 -m pytest test_backtest_e2.py test_scorecard_e2.py -q` → **73 passed**.
- `--selftest --outdir <scratchpad>` → OK, synthetic only.
- `shasum` of every file under `data/f5/` before vs. after tests+selftest: **identical**; `git status` unchanged. No `G3_RATIFIED.json`, no `head1_scorecard.*`, no `head1_oof_predictions.parquet` anywhere in the repo.
- `git check-ignore`: all three scorecard artifacts are ignored (`.gitignore:161,162` and `:146`) — legal finding #4's fix is real.
- `scorecard_e2.py` has no `__main__`, no CLI, reads no feature/price table of its own; `test_backtest_e2.py:1075` pins by AST that `build_scorecard` is called only from `run_head1`. It cannot reach real data standalone.
- PIT claims re-derived independently: `backtest.build_walk_forward_folds` trains on `filing_date < quarter_start`; the rolling filter keeps `q-N <= tq < q` (`backtest_e2.py:909-912`); the purge drops `window_close >= quarter_start` (`:914-922`); `assert_no_fold_leakage` runs on both (`:944`); PCA is fit on `train_pos` only (`:970-999`) including in the rolling arms; `size_only` goes through the same `fit_predict_seeded` train-only path. **No look-ahead found in the new code.** OOF records are emitted inside the fold loop from that fold's `test_idx` (`:1127-1148`), so every record's prediction is from the fold that excluded it. `make_calls` filters `arm == "pit_trailing_rank"` by equality, so the `_no_same_day` and `raw_levels` arms cannot contaminate the scorecard.

---

# Findings, ranked

## BLOCKER — do not ask for "ratify" in the current form

**B1. §14 launders a main-session design into an owner ruling; decision 23(a)–(h) is worse.**
`data/f5/G3_PREREGISTRATION.md:218-244`. Every §14 row sits under the column header "RATIFIED rule (dec.; owner 2026-09-11)" tagged `(3)`, and **§14 contains zero ⚠ marks** (verified: ⚠ appears only at lines 11-12, 61, 64, 95, 101, 109, 177). The owner's entire input to decision 3 was the word **"Default"** — against a packet (`G3_OWNER_PACKET.md:65-110`) that contained no scorecard at all and whose superseded line said "nothing REPORTS a per-company score". Terciles, `sign_match_nonzero`, min-6-calls, Wilson, the two comparators, the base-rate column — all main-session. The rulings file is honest about this (§2-3 "Added under the owner's core value statement"; §4 row 3 lists it as interpreted); the pre-registration is not, and the pre-registration is the document whose sha gets pinned.
Worse: `:179` and `:61` assert "**the owner ruled the defaults on 23(a)–(h)**". The owner's decision-23 words were a *question* about quarterly filings. §4 row 23 only covers the sequential-novelty answer. So 23b (min-shingle 50), 23c, 23d (8K_BODY exclusion), 23e, 23f, 23g and **23h (the embedding model as a ratified third-party artifact)** are recorded as owner rulings with no owner words behind them and no entry in the confirmation list.
*Minimal fix:* mark every §14 row and every 23(b)–(h) cell "⚠ INTERPRETED — owner confirms", and add two rows to the rulings §4 table: "§14 scorecard mechanism in full" and "23(b)–(h) defaults adopted with no owner words".

**B2. "Reply *ratify* and the main session … runs the three heads" is not executable — at least six ratified rules are not implemented in the artifacts the run reads.**
`G3_OWNER_RULINGS_2026-09-11.md:372`. Against the pre-registration's own enforcement column:
- decision 2 (GLD): `:103` "The analysis-side exclusion is **NOT YET ENFORCED**" — and the benchmark half is *also* unimplemented and not flagged. `target_e2.py:106,262` only sets `is_gld`; `backtest_e2.py` never reads it (grep: the only other hit is the synthetic fixture at `:2444`). I measured **6 GLD rows inside the 33 folds**, so GLD both sits in every peer average and will be scored.
- decision 20 (same-CIK attribution): `:146` "the artifact carries the E1 cross-CIK rule".
- decision 21 (duration-matched cash-flow ratio): `:89` "the artifact carries the ported definition".
- decision 23a/23b (year-over-year prior + min-shingle): `:61` "The as-built artifact is NOT this rule … the `_yoy` names are only truthful after that rebuild".
- decision 23d (8K_BODY out of the embeddings): `:62` "85 8K_BODY sections are embedded in the artifact on disk".
Ratify-then-run means running a study that violates six of its own ratified rules. Rebuild-then-ratify means the pinned document's measured populations are stale on the day they are pinned. Either is a decision, neither is stated.
*Minimal fix:* put a **pre-run build list** in the rulings §4 ("these five rebuilds run *before* the sha is pinned, then the measured-population cells are refreshed"), or an explicit line the owner signs: "this run uses the as-built artifacts; decisions 2, 20, 21, 23a, 23b, 23d are pre-registered for the next build and are NOT in this run's numbers".

---

## MUST-FIX BEFORE RATIFY

**M1. The code prints per-company hit rates that §14 forbids, and a test pins the violation.**
§14 (`:236`): "A hit rate with a Wilson 95% interval only when that company has ≥ 6 calls … below that, **rows only, no rate and no interval**." Rulings §2-3: "otherwise rows only". Code `scorecard_e2.py:349-355` computes `hit_rate` always and nulls only the interval; `:451` prints `"The model: 2/3 calls right, hit rate 0.6667 (fewer than 6 calls (§14): rows only, no interval)"`; the JSON carries it too. `test_scorecard_e2.py:240` asserts `b["hit_rate"] == 2/3, "the rate is still shown"` — the suite pins the contradiction. I measured **30 of the 140 scored companies have fewer than 9 dedup rows**, so this fires on a large minority; GLD (6 dedup rows) will render as a company with a printed hit rate. *Fix:* set `hit_rate`/`n_correct` to `None` below the threshold in both md and json, and flip the test.

**M2. §14's measured populations are the wrong population — off by ~20-30% in the owner's headline artifact.**
- `:231` "Rows scored … **5,383** of 7,405 (72.7%) … **6,204** rows inside the 33 folds". Re-derived from `census_head1.json` and from the frame itself: the scorecard scores **4,498 rows per block** (Σ `n_test_dedup` over the 33 ratified quarters). 5,383 is dedup over all 40 candidate quarters; 6,204 is raw in-fold. Neither is the number.
- `:233` "**161–202** scored rows per test quarter — terciles are **~54–67** rows a side". Those are *raw* counts over all 40 candidates (33-fold raw range is 163–202). The scorecard's per-quarter scored rows are **119–161 (mean 136.3)** → terciles **~40–53** a side.
- `:236` / rulings §1 D "**144** CIKs in the run" → **140** CIKs actually appear in the 33 folds.
*Fix:* replace with 4,498 / 119–161 / ~40–53 / 140, each with its source.

**M3. The tercile tie rule is unregistered, and it demonstrably fires on the load-bearing comparator.**
§14 `:233` says nothing about ties; `scorecard_e2.py:189` breaks them with `rank(method="first")` over frame order, i.e. **by filing date within the quarter**. `size_only` is a one-feature XGB fit → a step function → mass ties. On the synthetic selftest run I measured `size_only`: **21.5% of rows sit in exact tie groups, and 2 rows in tie groups received different calls purely by filing order** (`numeric_only`/`text_and_numeric`: 0%). Real data will be worse (ranked single feature, 119–161 rows/quarter). Since §1 `:65` and legal Q2-2 make `size_only` the yardstick — "if `size_only` matches or beats the model, that is the headline" — an arbitrary date-ordered tie-break inside its calls is a measurement artifact in the number that decides the honest headline. *Fix:* pre-register one rule — tied rows → "no call", or `rank(method="average")`, or a seeded random break — and state it in §14.

**M4. The base rate is printed as the yardstick, and under a tercile rule it is the *wrong* yardstick.**
§14 `:236` justifies it: "so a hit rate is never read against an implied 50%". But the tercile rule forces ≈ equal "outperform" and "underperform" counts, so a call-count-matched random rule scores **exactly 0.50 regardless of the base rate**. The rendered page (`scorecard_e2.py:451-454`) prints "hit rate 0.5000 … Base rate … 0.3000 over 10 filings", which reads as "the model beat the base rate by 20 points" when it in fact matched chance and an always-underperform rule (unavailable under this rule) would have hit 0.70. This is precisely the evaluation-interpretation error that makes a null look like a product. *Fix:* print the call-matched random baseline (0.50 by construction) as the comparison line; keep the base rate, but label it as the outcome mix, not the benchmark.

**M5. The scorecard page carries three disclosures and is missing the ones that matter most to it.**
§11 is titled "each travels with **every** result"; legal Q2-4 requires labeler error, the train-overlap banner, and "price return only, dividends not included" on the scorecard specifically. The page (`scorecard_e2.py:490-522`) carries the scope sentence, the inference sentence and the prices sentence — and **not**: teacher red-flag error 42.00%, sentiment 86.94% INDETERMINATE, train-overlap 4.53% chunk / 80.19% filing, the seven-financials extraction hole, the unconverted CAD reporter, the survivorship direction of price censoring, "no transaction costs/taxes/slippage", "dividends not included" in those words. This is the one artifact the owner will read standalone (it is deliberately git-excluded from the report it sits beside). *Fix:* add a fixed disclosure block read from the same constants the report uses.

**M6. Decision 4: "the data range cannot be increased" is asserted as fact and justified by a decision the owner made about something else.**
Owner (rulings `:229`): *"if you need to increase the quarterly range, you may. I have the luxury of having a lot of historical data… we must play with the range and not settle for a specific quarterly range without REAL DATA TESTING."* The reading (`:231`, prereg `:64`, `:109`) answers: "the data **range cannot be increased** — the corpus starts 2016Q3 and earlier data is the ingestion the owner declined under **decision C**." Decision C is `:73` — *mid-cap expansion*, not more history for the existing 144 companies. The owner's premise ("a lot of historical data") is wrong for this corpus and was never corrected to them; their explicit offer to extend the range was closed with a misattributed justification, and the knob was then swapped for a different one (rolling *training* window), which is not what "quarterly range" most naturally means. Given decision D ("HISTORICAL TEST IS UTMOST IMPORTANCE"), this is the one place the owner asked for more and was told no. *Fix:* state the real cost of extending the corpus backwards (re-ingest + re-extract + re-label, days, $0 API) and put "extend the range, or run 33 folds" in the §4 confirmation list as the owner's own choice.

**M7. Three readings that the rulings file's own policy says must be ⚠-marked are neither marked nor in §4.**
The file's stated rule (`:6-9`): a reading is marked ⚠ where the owner "wrote 'you know best', asked a question, or used a word whose meaning had to be fixed."
- **17** (`:286`) — owner opened with *"I am unsure of what this means."* and the pre-registration converts "I agree with this" into **"the signature on §13"** (`:193-216`), unmarked. The UNPOWERED row of the outcome map is entirely the main session's; the owner never used the word.
- **13** (`:270`) — owner *asked a question* ("What this mean?"). Reading unmarked at prereg `:134`.
- **22** (`:303`) — owner wrote *"Idk what default is, but I believe you know best. If it is fixed, then good."* Reading unmarked at prereg `:88`, and "it" was interpreted for them.
HANDOFF `:1586-1593` itself lists 13 and 17 among "the readings", which confirms the gap. *Fix:* add rows 13, 17, 22 to the §4 list. A signature taken from "I am unsure of what this means" is the single line most likely to be repudiated later.

**M8. The §13/§14 split contradicts the owner's stated purpose for the scorecard, and nothing tells them so.**
Owner, decision D (`:82`): the historical test *"would show if everything was for naught … or if we have a real product."* The pre-registration says the opposite: §10 `:144` head 1's IC delta is "the **only** metric driving the stopping rule"; §13 `:208-211` and §11 `:170` say the scorecard "never moves the branch". So a bounded null closes the alpha line even if the scorecard looks excellent to the owner, and an UNPOWERED result does the same. That may well be correct science, but the owner is being asked to sign it while believing the scorecard answers their question. *Fix:* one plain sentence in §4: "the scorecard cannot change the §13 outcome; if the IC margin comes back bounded-null or UNPOWERED, the text arm is closed regardless of how the hit rates read."

**M9. The pinning procedure has no defined text.**
Header `:3` says "NOT YET RATIFIED; no sha pinned"; the params block carries `"draft_status": "RATIFICATION-READY … sha pinned only on the owner's word"` (`:253`). Both `doc_sha256` and `params_sha256` cover that text. So either the sha pinned is of a document that asserts it is not ratified (and `draft_status` stays wrong forever), or the header/status is edited after the owner reads it — in which case the pinned document is not the one they read, and `require_g3` (`backtest_e2.py:576`) will later refuse any attempt to fix it. *Fix:* decide now, in the rulings §4, which exact text is pinned, and if it is the edited one, re-present the final two lines to the owner before pinning.

---

## SHOULD

**S1.** `G3_PREREGISTRATION.md:44` still says "**43** head-1 … pinned paths". I regenerated `G3_PARAMS_SCHEMA.json` from `write_params_schema` — byte-identical to the committed file, **54** required head-1 keys (43 + 11 new). Same cell's "**4** documentation-only keys" undercounts: the block's non-required leaves are `draft_status`, `post_2019_fold_quarters`, `post_2019_fold_quarters_note`, `spec.ticker_col`, `spec.date_col`, `families.novelty_prior_rule`, `families.novelty_min_shingles`, `families._note` (`loco.max_ciks_per_fold` and `head3.model_params.*` are consumed). Same cell's "backtest_e2.py **gains** … until it does, a run cannot consume them" is written in the future tense for a change already on disk.

**S2.** `:102` "**No ETF price series exists on disk**" is false as written — GLD (CIK 1222333) is a filer *and* an ETF and is priced. The true statement is "no broad-market index ETF (SPY) series exists". The owner's decision-1 words were "other companies and **ETFs**"; the cell they'd rely on is inaccurate.

**S3.** Two cells in a RATIFICATION-READY document still say a parameter is **open**: `:74` "whether training also drops those filings, or the arm uses a share threshold instead of 'any', **is open at this decision**" and `:162` "is open at dec. 3" — but the packet said that sub-question was part of decision 3 and the owner answered "Default". The code implements evaluation-side-only at threshold 0.0. Say so; nothing in a pre-registration may be "open".

**S4.** The "descriptive" sentence exists in three non-identical forms: §11 `:170`, §14 `:237`, and `scorecard_e2.py:86-90` ("…(§1, decision 15); a per-company hit rate over at most 33 quarters…"). Legal Q2-2 requires it verbatim. `SCOPE_SENTENCE` is imported from the runner precisely to prevent this (`scorecard_e2.py:125-132`) — do the same for the inference sentence and quote the constant in the docs.

**S5.** The hit-rate denominator is stated (`n_calls`) but the **"no call" count is never printed**, and `score_calls` (`scorecard_e2.py:213-215`) collapses "middle third" and "unresolved outcome" into the same `NaN` — the artifact cannot distinguish them. Legal Q2-3 asks for the denominator explicitly. Print `n_no_call` and `n_unresolved` per block.

**S6.** `backtest_e2.py:2312`-ish (report §7) prints the **absolute local path** of the scorecard into `report_head1.md`, which is committed (`/Users/vihanpatil/…`). Use a repo-relative path.

---

## NOTE (low confidence / accepted-risk, flagging anyway)

**N1.** The tercile boundary is drawn across the whole test quarter, so a call is **not reproducible in real time** — it depends on filings published later in the same quarter. The rendered page says so ("not a real-time one", `scorecard_e2.py:504-506`); §14 does not. This matters for P5: the paper period's forward calls cannot use this rule, so the paper record will not be like-for-like with the scorecard the owner is being sold on.

**N2.** The ordering guarantee covers the *results payload* (`ResultsWriter.add_delta_payload` raises before `set_margin`, `backtest_e2.py:1460-1467`; `test_scorecard_e2.py:465-469` pins the key order and would fail or error if the scorecard moved) — but **not the disk write**: `SC.build_scorecard` writes the md/json/parquet itself (`scorecard_e2.py:566`), so a future edit that moved only the build call above `set_margin` would write a scorecard page before the margin existed while still failing on the payload. A stricter version passes the margin block into `build_scorecard`.

**N3.** The dedup keep-mask is computed over the whole frame, so which filing in a ≤5-day cluster gets the call depends on a possibly *later* filing. Harmless for the IC (applied identically to all blocks, frozen E1 rule) but it means the scorecard sometimes reports the call for the filing that survived dedup, not the first one the owner read.

**N4.** The scorecard's peer benchmark is the **whole universe, both strata** (§5 `:101`) — including the unpromoted extension stratum that G2 never validated and GLD. Disclosed in §5, but the scorecard's prices sentence says only "the equal-weighted universe average excluding the company".

**N5.** Decision 7's adopted reading *reverses* the literal default the owner ruled ("Default" = convert FX; the run converts nothing). It is ⚠-marked and in §4, so this is visibility-adequate, but the cell header still reads "RATIFIED".

**N6.** Rulings §1 D: "Nothing in it is synthetic." True of filings and prices; the text features are model-produced labels with 42% red-flag exact-set error and 86.94% INDETERMINATE sentiment. Worth one escorting clause given the owner's "All others are synthetic" complaint.

**N7.** The column header "RATIFIED rule (dec.; owner 2026-09-11)" appears on ~60 rows, 31 of which carry "NOT YET ENFORCED" in the next column. "RULED rule (pending ratification)" would be the honest header while the document is unratified.

---

## What I could not verify

- **Whether the owner's chat words are transcribed correctly.** Every "verbatim" quote I checked is internally consistent across `G3_OWNER_RULINGS_2026-09-11.md`, `HANDOFF.md` §3 and `G3_PREREGISTRATION.md`, but all three are main-session artifacts; there is no independent record of the chat. Anything in this review about "the owner said X" inherits that.
- **The real scorecard's behaviour.** I deliberately never ran a head against real data, so every real-data statement here is derived from `census_head1.json`, the input parquets and a fold/dedup re-derivation — not from predictions. Tie prevalence in `size_only` is measured on the *synthetic* fixture; I expect it to be worse on real ranked data but I have not measured it.
- **Whether the rebuilds in B2 are cheap.** §1 claims 18 s for family A and §10 claims 19 s for text features; I did not run them.
- **Head 2 / head 3 code paths** (`heads_e2.py`) beyond confirming that the params block satisfies `REQUIRED_HEAD2`/`REQUIRED_HEAD3` — out of this brief's scope.
- **The legal memo's substance.** I took it as given and only checked that the pre-registration's claimed responses to findings #4 and Q2 match the code (gitignore ✓, universe-block-only commit ✓, sorted-by-name-not-hit-rate ✓, "all companies" ✗ — absent companies are not listed with their reason; only the aggregate "31 of 244" sentence appears).

---

## Verdict

**NOT SAFE TO ASK FOR RATIFICATION** — two BLOCKERs (§14/23 provenance laundering; "ratify → run" against six unimplemented ratified rules) and nine MUST-FIX items, of which M1, M2, M3 and M4 are defects in the scorecard the owner is being asked to treat as the product's centrepiece. The freeze itself is sound and the new code is free of look-ahead as far as I can re-derive it; the problem is the document and the presentation, not the folds.

---

## Disposition (main session, 2026-09-11, same day)

Every item is accepted. **B2 resolves as rebuild-then-ratify:** the pre-run build list (decision 2 both halves, 20, 21, 23a/23b, 23d, plus the exploratory sequential-novelty feature from the decision-23 reading) is executed before the sha is pinned, the censuses are re-run, and every measured-population cell in the pre-registration is refreshed from the rebuilt artifacts (M2 is done in that same refresh). **M3 rule adopted:** percentiles by average rank; a tie group that straddles a tercile boundary is "no call" in full, with `n_tied_no_call` printed per block. **M4:** the call-matched chance line (0.50 by construction under the tercile rule) is the comparison; the base rate is labelled the outcome mix. **M9:** the text pinned is the final one, with the header changed to "STATUS: RATIFIED <date>" and `draft_status` to "RATIFIED …"; the owner sees those two lines verbatim before the pin. **B1 / M6 / M7 / M8:** ⚠ marks added; rows for §14-in-full, 23(b)–(h), 13, 17, 22 and "extend the corpus backwards (days of re-ingest/extract/label, $0 API) or run 33 folds" added to the rulings §4 list; the "scorecard cannot move the §13 branch" sentence added. Code items M1, M5, S4, S5, S6, N2, N4 fixed in `scorecard_e2.py` / `backtest_e2.py`; S1–S3, N1, N5–N7 fixed in the document. A second, shorter red-team pass runs on the diffs before the owner is asked.

---

# Second pass (same evening, after round 2) — verbatim

**Verdict: NOT SAFE TO ASK FOR RATIFICATION tonight.** Freeze verified, all six suites green (211 passed), `python3 backtest_e2.py` → exit 2, `data/f5` sha-identical before/after, no `G3_RATIFIED.json`. Round 2 is a real improvement — the rebuilds are genuine (all four artifact and module shas recomputed and matching), the folds are clean, and 22 of the 24 first-pass items are fully resolved (M4 and M9 PARTIALLY; N3 NOT RESOLVED). Rebuild integrity re-derived independently: 23a prior selection strictly earlier (0 of 6,905 gaps outside [300, 430]); same-CIK attribution leaks no foreign labels and `cross_cik_share`'s population is stated correctly; duration matching leaves no long-flow-over-short-revenue row (within-bucket slack bounded to 0 disagreements vs a 20-day tolerance); GLD excluded from the peer average in the rebuilt target table and from the frame in every arm, the sensitivity arm restores GLD as a *subject* only (benchmark GLD-free in both arms) — code correct, doc silent. The two-line pin was simulated in the scratchpad and **is sufficient for the guards** (`require_g3`, `load_g3_params`, `heads_e2.load_ratified_params` all accept it).

## New findings

**MUST-FIX**
- **NF-1.** §11 (`:170`) and §1 (`:137`) quote NEGATIVE recall **0.487** — the v1.1 adapter's eval (`finetune/runs/2026-08-22-eval-epoch2/`, 55/113). The pinned labeler is the v1.2 adapter `cadca849…`, whose own held-out eval (`finetune/runs/2026-08-28-v12-eval-epoch2/`) measures **0.529 (64/121)**; `backtest_e2.LABELER_EVAL_PATH` points there, so the scorecard page will print 0.529 beside a document saying 0.487. The word "teacher" is also wrong (it is the student adapter's eval). `census_e2.json teacher_negative_recall: 0.487` carries the same stale value; the number is hand-typed (no test covers it).
- **NF-2.** "The overlap arm as built scores **4,859** rows" (`:85`, `:173`) is frame arithmetic (7,389 − 2,530). The arm scores dedup, non-overlapping **test rows inside the 33 folds**: **2,700** (GLD in) / **2,694** (ex-GLD) — ~82 rows a quarter, ~60% of the primary's n_dd. Same error class as M2.
- **NF-3.** "CIK-level exposure **15.85%**" (`:173`) is G2 §2.5's *fine-tuning-corpus* figure. On **this frame**, under the same "≥ 1 overlapping chunk" rule that gives 34.24%, **108 of 144 CIKs = 75.0%** carry overlap.
- **NF-4.** The scorecard page's price-censoring sentence (`backtest_e2.py:2664`) asserts "disproportionately acquired or delisted names — absence is outcome-correlated", which §11 (`:178`) forbids: "the cause is not separately measured … must not be described as [delistings]".
- **NF-5.** §1's numeric-block cell (`:71`) was not refreshed: `operating_cashflow_to_revenue` coverage is now **42.0%** (was 83.6%) after decision 21 — the worst-covered numeric feature — and the cell still names only leverage (71.4%) and operating margin (56.4%).
- **NF-6.** Four ⚠ in the document have no §4 row: the [300, 430]-day window + closest-to-365 tie-break; "same fiscal quarter" from the filing-date window; decision 21's bucket-equality criterion; decision 21's scope boundary (`net_margin` 135 rows, `operating_margin` 20 rows left ported).

**SHOULD**
- **NF-7.** `CHANCE_UNDER_CALL_RULE = 0.5` is hard-coded and the sentence asserts "calls are balanced"; the straddle→no-call tie rule removes whole tie groups and can unbalance them (selftest `size_only`: 79 vs 80). Print `n_outperform` / `n_underperform` per block and compute the chance line as `(n_out·p + n_under·(1−p)) / n_calls`.
- **NF-8.** `n_emb_missing` is **45 on the 7,618-row join, 44 on the modeling frame** (the diag counts before the 229 null targets drop); the doc says 45 "on the modeling frame". Their fate is undisclosed: NaN PCA components → XGBoost's missing-value routing; they are fitted (706 train instances), predicted, and receive **25** published scorecard calls with no embedding and no novelty.
- **NF-9.** After exactly the two ratified line changes, the frozen text still reads "ratification pending" in 13 headers, "unratified" at `:51` and `:270`, "ratified only when the owner says so" at `:14`, and carries a blank signature (`:234–235`); `require_g3` refuses any later repair.
- **NF-10.** "= 20 filings with corpus text but no attributed labeled chunk" (`:74`) is cardinality arithmetic (7,638 − 7,618); the set differences are **65** families rows not in the join and **45** join rows not in families.
- **NF-11.** §5 does not say the GLD sensitivity arm restores GLD as a subject only (benchmark GLD-free in both arms).
- **NF-12.** The scorecard page's guidance line lacks `guidance_false_none_rate` **0/80 [0.00, 4.58]** and the `G2_FINAL_REPORT.md §0` citation that §11 makes mandatory "every time".
- **NF-13.** The ex-GLD numbers (4,481 / 118–161 / 135.79 / 139 / 7,381 / 143) are correct but exist in no committed census; add the GLD-excluded fold census to `census_e2.py`.

**NOTE** — NF-14 two confirmatory columns ~72% missing on the run-time frame (`guidance_signed_mean` 27.99%, `novelty_risk_factors_yoy` 28.56%), unstated in §1; NF-15 the `any_source_accession` overlap channel includes filings dated after the subject (conservative, evaluation-side, not strictly PIT — undisclosed); NF-16 MDE table at n_dd 135.97 (GLD in) vs run 135.79; NF-17 34.24% frame vs 34.28% run-time; NF-18 = N3 (dedup mask sees later filings) still undisclosed in §14; NF-19 within-bucket duration slack is a rule property; NF-20 `loco.max_ciks_per_fold` read with `.get()` — a missing key silently means "no cap"; NF-21 `:68` "three rise by < 0.09" — `revenue_yoy_growth` rises by +0.0903; NF-22 `text_families_e2_partial.parquet` (12.4 MB) is a stale build checkpoint beside the pinned artifact (git-ignored).

## Measured-cell audit: 16 re-derived, 14 exact, 2 mismatches (NF-2, NF-8). Spot-checked exact: §0 key counts (58/58/11/15, schema byte-identical), §8 head-2, §9 head-3, §11 31 of 244 and selfid 0.5686, §7 censoring, §5 GLD deltas.

## Could not verify: the owner's chat words (no independent record); real-data scorecard behaviour (never run); every downstream document quoting 0.487; `heads_e2.py` internals; the legal memo's substance; whether `home_cik` in `chunks_v1.parquet` is itself correct (E1 infrastructure).

## Disposition (main session, same evening)
All items accepted. Round 3: code — NF-1 (census reads the v1.2 eval), NF-2/NF-3/NF-10/NF-13/NF-14 (census additions: ex-GLD fold census incl. the overlap-arm rows in folds, CIK-level overlap on the frame, both-direction set differences, per-column coverage on the run-time frame), NF-4 (wording from §11), NF-7 (chance from counts; n_out/n_under printed), NF-8 (join vs modeling counts; missing-embedding calls counted and disclosed), NF-12 (false-NONE + §0 citation), NF-20 (`loco.max_ciks_per_fold` required, nullable), NF-9 (a `pin_g3.py` script that applies the FULL pin substitution set — header, `draft_status`, the 13 headers, the two "unratified" sentences, the signature line — prints the diff for the owner, and writes `G3_RATIFIED.json` only on `--pin`; §0 names it); NF-22 stale checkpoint removed. Document — every remaining item, refreshed from the re-run census. Then a third, verification-only red-team pass.
