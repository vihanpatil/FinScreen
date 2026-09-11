# STEP 1B — `heads_e2.py`: the HEAD-2 and HEAD-3 runners

Written 2026-09-10 by the quant-modeler session executing F5_PLAN §2 Step 1.
Every number below was measured by the run that produced
`data/f5/census_heads.json` (module sha
`fd7d1399ced73552…`, recorded inside that file) or by the test run quoted in §4.
Nothing is hand-carried from a prior session or document.

**Amended 2026-09-10 (same day), after a red-team pass, by the session that
applied its findings.** Three changes: (1) `head3.train_label_purge` no longer
accepts `"none"` — head 3 now matches head 1's single-implemented-rule stance,
and a no-purge convention is a refusal at both doors (schema, tests and open
question 4 updated); (2) `run_head2` / `run_head3` re-measure the ratified
document themselves and refuse a fabricated `doc_sha` (defence in depth,
A46–A47); (3) the guard docstring named the wrong fence (`f5_parameters`); the
convention is and always was head 1's ```` ```json g3-params ````. The census
was NOT re-run: no census input changed (`census_heads.json` still records
module sha `fd7d1399ced73552…`, which is the pre-amendment module; the current
`heads_e2.py` sha is `5f033339fd0fa392…`).

**Freeze status (F5_PLAN §1): clean.** No information coefficient, correlation,
slope, model fit or any other feature-versus-outcome association was computed on
E2 data — not in `heads_e2.py`'s executed paths, not in `test_heads_e2.py`, not
interactively. `data/f5/G3_PREREGISTRATION.md` and `data/f5/G3_RATIFIED.json`
do not exist and were not created. `python3 heads_e2.py --head2 / --head3 /
--all` **refuse today with exit code 2**, and that refusal is a test
(`test_cli_refuses_both_heads_today`, `test_the_real_repo_has_no_ratified_document_today`).
`$0` — no network call, no API call.

E1 and E2 backtest numbers are numerically incomparable (different benchmark).
Head 2's dependent variable is benchmark-free by construction, so decisions 1–2
do not propagate into it; head 3 uses no benchmark at all.

---

## 1. What was built

| file | role |
|---|---|
| `/Users/vihanpatil/personal/projects/FinScreen/heads_e2.py` | the two runners + census + selftest + schema writer |
| `/Users/vihanpatil/personal/projects/FinScreen/test_heads_e2.py` | 58 tests, all on synthetic frames |
| `/Users/vihanpatil/personal/projects/FinScreen/data/f5/census_heads.json` | the counts below (`--census`) |
| `/Users/vihanpatil/personal/projects/FinScreen/data/f5/G3_PARAMS_SCHEMA_heads.json` | the document keys heads 2 and 3 read (`--write-schema`) |

Modes: `--census` (counts only, allowed before G3), `--selftest` (synthetic
known-answer checks, the only place a parameter literal may appear), `--head2`
/ `--head3` / `--all` (guarded; refuse today), `--write-schema`.

**The guard is head 1's guard, imported, not a second copy.** `backtest_e2.py`
appeared in the repo during this session, so per the brief this module imports
`G3Refusal`, `require_g3`, `extract_params_block`, `assert_input_shas`,
`sha256_file` and `append_run_log` from it rather than re-implementing the
check (`FreezeRefusal is backtest_e2.G3Refusal` is a test). The consequences,
stated because they are conventions and not code details:

* the document convention is head 1's — **exactly one fenced ```` ```json
  g3-params ```` block whose JSON object is the parameter root** (not a
  `f5_parameters` sub-key);
* head 3 reads the **same** `fold_quarters`, `columns.confirmatory_text`,
  `columns.numeric` and `embedding.pca_k` head 1 reads, so there is one fold
  list and one confirmatory block across heads;
* both heads append to the **same** run log, `data/f5/run_log.jsonl`, keyed to
  the ratified document's sha, so a second run of any head is visible;
* `backtest_e2.py` was **not edited**. The only names this module may take from
  it are the guard and provenance helpers, and a test enforces that whitelist
  (`test_only_guard_and_provenance_helpers_are_taken_from_head_1`) — importing
  head 1's fitting machinery would put an IC one attribute access away from the
  census path.

**Parameters this module requires the G3 document to pin** (a missing key is a
refusal; there is no default anywhere outside `--selftest`). Full descriptions,
types, examples and allowed values are in `G3_PARAMS_SCHEMA_heads.json`.

* head 2: `head2.stratum`, `head2.predictor`, `head2.direction`,
  `head2.event_window_sessions`, `head2.trailing_sessions`, `head2.statistic`,
  `head2.bootstrap.weights`, `head2.bootstrap.n_draws`,
  `head2.bootstrap.cluster`, `head2.bootstrap.seed`.
* head 3: `fold_quarters`, `head3.horizon_quarters`, `head3.label_cut`,
  `head3.exit_event_kinds`, `head3.feature_filing_rule`,
  `head3.train_label_purge`, `columns.confirmatory_text`, `columns.numeric`,
  `head3.missing_value_rule`, `head3.standardize`, `head3.model`,
  `head3.model_params`, `head3.metric`, `seeds.primary`; plus
  `embedding.pca_k` **conditionally**, required as soon as the confirmatory
  block names any `emb_pc*` column (the count must equal it).
* `head3.train_label_purge` is a key this module **added** to the schema: see
  open question 4. It is leakage-relevant, so it holds no default — and since
  the 2026-09-10 red-team pass it has exactly ONE implemented value,
  `horizon_end_before_test_start`, matching head 1's single `purge_rule`. The
  document must still pin it explicitly; `"none"` is now a refusal rather than
  a selectable convention.

**Head 2, as implemented.** Events = `controls.load_earnings_events` (item-2.02
8-Ks filed inside the filer's own membership spell), core stratum, CIKs with a
column in the sha-pinned price matrix; sessions from `controls.resolve_sessions`
(identical chain to `target_e2.py` and `numeric_features_e2.py`). Predictor =
the event filing's text-feature column, joined on `(cik, accession_number)`.
DV = mean |raw daily return| over sessions `[+1, +5]` after the news session ÷
mean |raw daily return| over the 60 returns ending at the pre-session.
Statistic = OLS slope; SE and p by wild-cluster bootstrap over event quarters
with Rademacher weights, the null (slope = 0) imposed on the restricted
residuals. The few-clusters limitation string carries the measured cluster
count and is part of the estimate block, so it cannot be reported without it.

**Head 3, as implemented.** Panel = one row per `(cik, quarter)` taken from
`numeric_features_e2.parquet` (already the core, in-membership, PIT row
universe), dated at `info_date`, features from the CIK's latest filing in the
quarter under the pinned rule, text block joined on `(cik, accession_number)`.
Label = an exit filing strictly after the feature date and at most
`horizon_quarters` × 3 months after it. Rows whose horizon closes after
`head3.label_cut` are flagged unobservable and counted. Folds are the pinned
`fold_quarters`; a fold whose outcome window closes after the label cut is
**censored — counted (`n_test_panel_rows`), never scored**. Model =
ridge-penalised logistic regression by IRLS (20 lines of numpy, so this module's
dependency set stays identical to the rest of the repo); imputation and
standardisation use training-fold statistics only; metric = Mann-Whitney AUC
with average ranks, `None` when a fold has one class, prevalence reported either
way.

---

## 2. Every assertion enforced, with its measured value

Provenance and guard assertions run inside the code; the rest are tests over
synthetic frames. All passed on the run reported here.

| # | assertion | where | measured |
|---|---|---|---|
| A1 | `text_features_e2.parquet` sha equals its manifest record | `assert_input_shas` | `f9084e95c5fa…` MATCH |
| A2 | `numeric_features_e2.parquet` sha equals its manifest record | `assert_input_shas` | `23f2ef2ec405…` MATCH |
| A3 | `filings_metadata_e2.db` sha equals the committed H1 record | `assert_input_shas` | `61dcefaae43c…` MATCH |
| A4 | `prices_e2.parquet` sha equals the committed H1 record | `assert_input_shas` | `744e1cc5ccc2…` MATCH (snapshot last session 2026-08-24) |
| A5 | no ratified document → both heads refuse, write nothing, exit 2 | code + test | exit code 2 on `--head2`, `--head3`, `--all`; no results file, no run-log line |
| A6 | a document edited after ratification (sha mismatch) → refusal | test | refusal message names `doc_sha256` |
| A7 | a ratification without its document → refusal | test | refused |
| A8 | zero or two parameter blocks → refusal | test | "expected exactly one" |
| A9 | dropping ANY single required key → refusal naming that key | test, looped over all 10 head-2 and all 14 head-3 keys | 24/24 refused, each message names the dropped key |
| A10 | a pinned value this runner does not implement → refusal, never a fallback | test | `head3.model="gradient_boosting"` refused |
| A11 | DV numerator = mean \|r\| over sessions `+lo..+hi` only | test | matches the hand-computed mean to 1e-12; poisoning every session < news, and every session ≥ +6, leaves it bit-identical; poisoning session +3 moves it |
| A12 | DV denominator sees nothing at or after the news session | test | poisoning every session ≥ news leaves it bit-identical |
| A13 | the denominator uses exactly `trailing_sessions` returns | test | 10 → 10 returns, 20 → 20 returns, both hand-checked |
| A14 | a window opening on the news session is rejected | test | `ValueError` at `post_window[0] < 1` |
| A15 | incomplete prices / zero denominator → NaN, never a number | test | NaN in both cases; zero denominator counted separately |
| A16 | DV is invariant to the price level | test | ×3.0 → identical |
| A17 | Rademacher weights: shape `(n_draws, n_clusters)`, values ±1, seed-deterministic | test + `--selftest` | `(50, 7)`, `{-1, +1}`, equal on the same seed, different on another |
| A18 | one weight per CLUSTER, not per observation | test | with 1 cluster the null draws take exactly 1 distinct \|value\| |
| A19 | null draws have shape `(n_draws,)`; cluster sizes sum to n; p-values in [0, 1] | test | `(250,)`; Σ sizes = n = 120; both p in range |
| A20 | the OLS slope matches an independent fit | test | equals `np.polyfit` to 1e-10 |
| A21 | the null draws are centred on zero, not on the estimate | test | \|mean(draws)\| < \|slope\| |
| A22 | an exit is labelled only strictly after the feature date and at most the horizon | test | exit on the feature date → 0; inside → 1; outside → 0; exactly at the horizon end → 1 |
| A23 | only the pinned `exit_event_kinds` count | test | same row labels 0 or 1 depending only on the pinned list |
| A24 | rows whose horizon closes past the label cut are flagged unobservable and counted | test | 1 of 2 flagged, counter agrees |
| A25 | fold censoring boundary is exact | test | 2020Q4 + 4q vs cut 2021-12-31 → not censored; cut 2021-12-30 → censored |
| A26 | a censored fold is counted, not scored | test | `auc is None`, `status` starts CENSORED, `n_test_panel_rows = 40` |
| A27 | prevalence is reported even when a fold is not scored | test | 0.25 reported on a fold with no training data |
| A28 | training rows come only from strictly earlier quarters | test | 120 rows from 3 earlier quarters, 0 from the test quarter |
| A29 | the purge rule is applied as pinned, and it is the only implemented one | test | on a 12-month-horizon fixture `horizon_end_before_test_start` purges 80 of 120 training rows; `"none"` is refused by `check_required` AND by `run_head3_folds` ("no implementation") |
| A30 | imputation and standardisation use training statistics only | test | a NaN test value is filled with the TRAINING median (standardises to exactly 0.0); the test fold's own median does not enter |
| A31 | a later quarter cannot change an earlier fold's score | test | AUC unchanged when a post-test quarter is shifted by 1e6 |
| A32 | `drop_row` drops instead of imputing | test | 5 NaN training rows → `n_train_used = n_train − 5` |
| A33 | a pinned feature column absent from the panel → refusal | test | refusal names the column |
| A34 | embedding column count must equal `embedding.pca_k` | test | unpinned k → refusal; k=3 with 2 columns → refusal; k=2 → runs |
| A35 | AUC known answers | test + `--selftest` | perfect separation 1.0, reversed 0.0, all ties 0.5, one-class `None` |
| A36 | the logistic fit recovers the signal direction and emits probabilities in [0, 1] | test | signal coefficient > 0 and larger in absolute value than the noise one; AUC > 0.9 |
| A37 | head-2 windows come from the document, not the code | test | a document pinning `[1, 2]` / 5 produces exactly the 2-return and 5-return arithmetic |
| A38 | the fold list and the censoring verdict come from the document | test | flipping only `head3.label_cut` in the document flips `censored` |
| A39 | the schema file on disk equals what the code requires | test | equal; required key sets match `REQUIRED_HEAD2` / `REQUIRED_HEAD3` exactly |
| A40 | the census path cannot reach a fitting function | AST call-graph test from `run_census` | reachable set ∩ {`ols_slope`, `wild_cluster_bootstrap`, `logistic_l2_fit`, `logistic_l2_score`, `auc_score`, `run_head3_folds`, `attach_head2_dv`, `run_head2`, `run_head3`} = ∅ |
| A41 | only the guard/provenance helpers are taken from head 1 | AST test | `BT.*` calls used = {`sha256_file`, `assert_input_shas`, `require_g3`, `extract_params_block`, `append_run_log`} |
| A42 | the guard runs before any fit in `main`, and each runner checks its required keys | AST + source test | `load_ratified_params` precedes both runners; both call `check_required` |
| A43 | no association statistic is imported from a library | source scan | none of `spearmanr`, `pearsonr`, `corrcoef`, `.corr(`, `linregress`, `sklearn` appears |
| A44 | the census is byte-stable across runs | two runs, sha of the JSON minus timestamp/runtime | `212b5a51bf047a12…` both times |
| A45 | the guarded runners assemble correctly (synthetic end-to-end) | 2 tests with every loader monkeypatched to synthetic fixtures | head 2 writes a results document + one run-log line keyed to the document sha, with `n_clusters`/`n_obs` matching the fixture and no raw draw array; head 3 writes per-fold rows, censored folds counted, prevalence present wherever there are observable rows |
| A46 | each runner re-measures the ratified document itself; a fabricated `doc_sha` cannot reach a fit | `reverify_guard` at the top of `run_head2` / `run_head3` | tests (both runners): a forged sha against a real synthetic pair refuses ("not a ratification"); the same call against the repo's real paths refuses because nothing is ratified; in both cases no loader ran, no results file and no run-log line was written |
| A47 | the re-check is the FIRST thing each runner does | source test | `reverify_guard(` precedes `check_required(`, `assert_input_shas(` and every `get_param(` in both runner bodies |

### Mutation checks (throw-away copies in the scratchpad; repo files never mutated)

Each mutation was applied to a copy and the suite re-run; the baseline in that
sandbox is 1 failure (the schema-file test needs the real `data/f5` path).

| mutation | caught |
|---|---|
| M1 numerator window opens ON the news session | yes (4 failures) |
| M2 trailing window slides one session past the pre-session | yes (5) |
| M3 guard bypassed (`require_g3` short-circuited) | yes (4) |
| M4 one Rademacher weight per OBSERVATION instead of per cluster | yes (5) |
| M5 censored folds scored anyway | yes (2) |
| M6 training window includes the test quarter | yes (4) |
| M7 a missing pin returns `None` instead of refusing | yes (4) |
| M8 an exit ON the feature date counts as an exit | yes (2) |
| M9 standardisation pooled over train + test | yes (2, after A30 was strengthened — the first version of that test did **not** catch it) |
| M10 an unimplemented pinned value silently accepted | yes (2) |

---

## 3. Census, as measured (`data/f5/census_heads.json`)

Nothing in this section is an association. The `candidate_*` values used to size
the population (predictor `sentiment_negative_share`, window `[1, 5]`, trailing
60, horizon 4 quarters) are F5_PLAN §3 defaults for sizing only; the runner
reads none of them.

### Head 2 — events

| quantity | measured |
|---|---|
| item-2.02 in-membership events, all strata / CIKs | 5,903 / 242 |
| core stratum / core CIKs | 4,374 / 174 |
| dropped: CIK has no column in the price snapshot | 320 events over 27 CIKs |
| dropped: news session off the price calendar | 0 |
| excluded: `[+1, +5]` window does not close under the snapshot | 3 |
| excluded: trailing 60-session window opens before the calendar | 0 |
| excluded: price gap inside either window | 17 |
| **events with no text-feature row at all** | **38** |
| events with a text row | 4,016 |
| events with a text row but a null predictor | 0 |
| **usable events (prices complete AND predictor present)** | **3,996** |
| clusters (event quarters) | **41**, 2016Q3 → 2026Q3 |
| usable events per quarter | min 83, mean 97.5, max 107 |
| events with a flat (exactly zero-return) session in the post window | 81 |
| events with a zero trailing denominator | 0 |

The 41 clusters exceed F5_PLAN decision 12's "~39" because a 5-session window
closes under the 2026-08-24 snapshot for events well into 2026Q3, where a
63-session window would not. It is still a few-clusters setting. The terminal
cluster is PARTIAL for exactly that reason (2026Q3: 92 usable events against a
98–107 run-rate over the preceding eight quarters) — open question 10.

### Head 3 — panel and exits

| quantity | measured |
|---|---|
| numeric row universe (core, in-membership, PIT) | 18,300 rows / 175 CIKs |
| of those, rows that also have text features | 8,212 |
| panel under `latest_in_quarter` | **4,056 rows / 175 CIKs**, 41 quarters 2016Q3–2026Q3, 95–100 per quarter (mean 98.9) |
| of those, rows whose feature filing has **no** text | **2,840 (70.0%)** |
| panel under `latest_in_quarter_with_text` | **4,042 rows**, 0 without text, 92–100 per quarter |
| `distress_events` rows / CIKs | 668 / 144 |
| rows carrying a stored `items` value | **2** (both 8-K item 1.03) |
| rows on core-stratum CIKs / core CIKs touched | 480 / 99 |
| exit filing dates | 2015-07-01 → 2026-08-17 |

`distress_events` schema, as stored: `cik INTEGER, accession_number TEXT, form
TEXT, filing_date TEXT, items TEXT, event_kind TEXT, PRIMARY KEY
(accession_number, event_kind)`. Counts by kind and form:

| event_kind | form | rows | CIKs |
|---|---|---|---|
| `delisting_form_25_nse_exchange_filed` | 25-NSE | 510 | 131 |
| `deregistration_form_15` | 15-12B | 65 | 42 |
| `deregistration_form_15` | 15-15D | 32 | 13 |
| `deregistration_form_15` | 15-12G | 22 | 21 |
| `delisting_form_25` | 25 | 37 | 30 |
| `bankruptcy_8k_item_1_03` | 8-K | 2 | 1 |

**The M&A / distress split decision 13 asks for "by the stored item where
possible" is not possible here**: `items` is NULL on 666 of 668 rows — every
Form 25 and Form 15 row. Only the two 8-K item-1.03 rows carry items. A Form 25
filed after an acquisition is indistinguishable in this table from one filed
after an exchange delisting. That is what decision 13's claim scope ("exit",
never "distress") supports, and no more.

**A stored exit row is frequently not a company exit.** Counting, per event
kind, the rows on panel CIKs that are followed by that same CIK still filing
in-membership more than 365 days later:

| event_kind | rows on panel CIKs | still filing a year later |
|---|---|---|
| `delisting_form_25_nse_exchange_filed` | 360 | **285** |
| `deregistration_form_15` | 93 | 50 |
| `delisting_form_25` | 25 | 14 |
| `bankruptcy_8k_item_1_03` | 2 | 2 |

### Censoring (candidate cut only)

The label cut is pinned by G3; the census reports the candidate
`max(distress_events.filing_date) = 2026-08-17` and, under a 4-quarter horizon,
which quarters it censors: **5 of the 41 panel quarters (2025Q3 onward); the
last uncensored quarter is 2025Q2.** The per-quarter map is in the census file.
The per-fold censored count itself is computed at run time from the document's
`fold_quarters`, because that list does not exist yet.

---

## 4. Runtimes (M5, single process, cold start)

| step | wall |
|---|---|
| `python3 heads_e2.py --census` | 1.5 s (0.5 s of work; ~1.0 s is interpreter + pandas/`backtest_e2` import) |
| `python3 heads_e2.py --selftest` | 1.0 s |
| `python3 heads_e2.py --write-schema` | 1.0 s |
| `python3 -m pytest -q test_heads_e2.py` | **58 passed in 1.1 s** (51 before the red-team pass, +7) |
| `python3 -m pytest -q test_backtest_e2.py test_heads_e2.py test_text_families_e2.py -m "not slow"` | 9.6 s — **142 passed, 1 deselected** |
| `python3 -m pytest -q test_target_e2.py test_features_e2.py test_numeric_features_e2.py test_controls.py` (sibling suites, unchanged by this session) | 105 passed in 39.2 s |

No test was deleted or weakened. **No module and no `data/f4` or
`data/hardening` artifact was touched by this work beyond `heads_e2.py` and its
test file**: `features.py`, `backtest.py`, `diagnose.py`, `spec.py`, `pit.py`,
`controls.py`, `target_e2.py`, `features_e2.py` and `numeric_features_e2.py`
are unmodified, and `backtest_e2.py` was not edited by the heads work (the
same-day red-team pass edited it under its own report, `STEP1B_backtest_e2.md`).
Other `data/f5` artifacts are written by their own modules and are outside this
report's scope.

---

## 5. Open questions for G3 (no recommendation attached)

1. **`head3.exit_event_kinds` decides what "exit" means, and the default is not
   obviously an exit.** 285 of the 360 `delisting_form_25_nse_exchange_filed`
   rows on panel CIKs are followed by the same company still filing
   in-membership a year later; so are 50 of 93 Form 15 rows, 14 of 25 Form 25
   rows, and both bankruptcy rows. Whatever list G3 pins is what the label
   measures; the runner counts but does not judge.
2. **`head3.label_cut` has no measured source.** The census offers
   `max(distress_events.filing_date) = 2026-08-17` as a candidate, but that is
   the last exit that happened to be ingested, not a statement about when
   ingestion stopped. If the true observation boundary is earlier, more folds
   are censored than the candidate implies.
3. **`head3.feature_filing_rule` changes the panel's text coverage by 70
   points.** Under `latest_in_quarter` (F5_PLAN's wording), 2,840 of 4,056 rows
   have no text features at all, because a quarter's last filing is usually a
   non-earnings 8-K; under `latest_in_quarter_with_text` the panel is 4,042 rows
   and fully covered, but the feature date moves earlier within the quarter.
   Both are implemented; neither is chosen here.
4. **`head3.train_label_purge` is a leakage convention with no prior ruling.**
   Training rows from the quarters immediately before the test quarter have
   4-quarter outcome windows that resolve inside or after it. This is head 3's
   analogue of decision 5's label purge, it is not named anywhere in F5_PLAN,
   and the module therefore refuses without it. On a synthetic 3-quarter
   training window the rule removes two thirds of the training rows, so it is
   not a rounding-error choice. **Since the 2026-09-10 red-team pass there is
   exactly one implemented value** (`horizon_end_before_test_start`), matching
   head 1's single `purge_rule`: G3 must still pin the key, but a no-purge
   head 3 would now be a code change reviewed against the ratified document,
   not a value that can be selected in the document. What is still open is
   whether a LONGER embargo (purging rows whose horizon closes within some
   buffer of the test quarter's start) is wanted; only the exact-boundary rule
   exists here.
5. **Membership dating differs between head 2 and the rest of F5.**
   `controls.load_earnings_events` filters membership on `filing_date`; the F5
   target and numeric tables filter on `info_date = max(filing_date,
   acceptance_ET)`. The ported loader is used unchanged (the brief says reuse
   it), so a filing accepted across a spell boundary can be in-membership for
   head 2 and out for head 1.
6. **The DV is not dividend-immune and not gap-immune.** Prices are
   split-adjusted only, so an ex-dividend session inside `[+1, +5]` inflates the
   numerator, and `controls.load_price_matrix` forward-fills inside a CIK's
   coverage window, so a non-trading gap enters as a zero return (81 usable
   events carry at least one exactly-flat session in the post window). Neither
   can be repaired from the current price source; both travel with the number.
7. **Head 2's predictor is the field G2 ruled INDETERMINATE (86.9%).** The
   disclosure block regenerates the G2 and v1.2 teacher constants from
   `text_features_e2_manifest.json`, but the stored-NEGATIVE recall/precision
   escorts required beside a sentiment row are not in any machine-readable
   artifact this module reads; G3 §11 has to carry them.
8. **`head3.model` is a ridge logistic regression written in this module.**
   G3 pins `l2`, `max_iter` and `tol`; the IRLS solver itself is not pinned by
   anything but this file's sha. If G3 wants the classifier to be a third-party
   artifact, that is a different ratification.
9. **The AUC of a fold with one class in the test set is `None`, not 0.5.**
   With per-quarter exit prevalence unknown until the kinds and cut are pinned,
   the number of such folds cannot be predicted here; the runner reports
   prevalence for every fold either way.
10. **Head 2's terminal cluster, 2026Q3, is a PARTIAL quarter.** The census's
    41 clusters end at 2026Q3, which contributes **92** usable events against a
    **98–107** run-rate over the preceding eight quarters (2024Q3–2026Q2:
    98, 104, 101, 103, 105, 105, 105, 107; whole-span min 83, mean 97.5). The
    quarter is short because the price snapshot is dated **2026-08-24**, so only
    events whose `[+1, +5]` window closes on or before it survive — a
    truncation of the calendar, not a change in filing behaviour. That makes the
    last cluster both smaller and differently composed (early-quarter filers
    only), and the wild-cluster bootstrap weights every cluster equally. G3
    should rule whether head 2's event span ends at the last COMPLETE quarter
    (2026Q2, i.e. 40 clusters) or keeps the partial one, **symmetric with head
    1's open question 1 about the last test quarter**
    (`STEP1B_backtest_e2.md` §4 item 1). The runner takes no position: it
    reports the per-quarter counts and uses whatever span the document pins.
11. **One red-team pass has now happened** (2026-09-10; its three findings are
    applied and listed in the amendment note at the top of this file). It
    precedes the owner's read and substitutes for neither it nor G3. The
    guarded paths have never run on E2 data by design, and no IC exists for any
    of it.
