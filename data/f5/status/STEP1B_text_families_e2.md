# F5 Step 1B — `text_families_e2.py`: the two zero-labeling text families

Status: BUILT and on disk. Session of 2026-09-10. Scope: EXPANSION_PLAN §8
item 4 / F5_PLAN §2 Step 1 — (A) year-over-year novelty of Item 1A / Item 7,
(B) pooled document embeddings. **Zero information coefficients,
correlations, model fits or feature-versus-outcome associations were
computed, in code, in tests, or interactively** (`F5_PLAN.md` §1, the E2
freeze). No return column was read: `data/f5/target_e2.parquet` was opened
for four key columns only (`cik`, `accession_number`, `filing_date`,
`in_membership`). No price and no fundamental was read. `$0` — no API call;
the only network action in the session was the one permitted model download
(§4).

E1 and E2 backtest numbers are numerically incomparable (different
benchmark); nothing in this file is a backtest number, but the features here
feed the E2 side of that comparison.

**Amended 2026-09-10 (same day) after a red-team pass**, by the session that
applied its findings: two source changes (a renamed this-run diagnostic and a
refusal that stops `--limit-filings` writing the production artifact) plus a
precise restatement of what a mid-way resume reproduces. **The shipped parquet
and manifest were not rebuilt** — see the module-sha paragraph in §1 and the
resume bullet in §2. No number in this report changed.

## 1. What was built

| file | role |
|---|---|
| `/Users/vihanpatil/personal/projects/FinScreen/text_families_e2.py` | the module (new sibling; no frozen module edited) |
| `/Users/vihanpatil/personal/projects/FinScreen/test_text_families_e2.py` | 32 tests: 31 synthetic (`tmp_path` only) + 1 real-data smoke marked `slow` (≤ 20 filings) |
| `/Users/vihanpatil/personal/projects/FinScreen/data/f5/text_families_e2.parquet` | **7,723 rows × 10 columns**, sha256 `acc2712e358fb0fa650e69392bce435799cfc9520179409e31d53bbde0a2346b`, 12.7 MB (git-ignored by the existing `data/f5/**/*.parquet` rule) |
| `/Users/vihanpatil/personal/projects/FinScreen/data/f5/text_families_e2_manifest.json` | input shas, model name/revision/weight sha, every pinned argument, coverage counts, gap and degeneracy censuses, runtimes, output sha |
| `/Users/vihanpatil/personal/projects/FinScreen/data/f5/text_families_e2_partial.parquet` | the crash-resume checkpoint (written every 500 filings; 12.6 MB) |
| `/Users/vihanpatil/personal/projects/FinScreen/requirements-quant.txt` | appended: the six packages the embedding family needs, pinned, with a comment |

Module sha256 at BUILD TIME
`45e0df09e833e11a4685f4ab5b95fb3ed8ec14e7ad8ab2124f093588bbe6efe9` — that is the
value recorded in `text_families_e2_manifest.json` (`module_sha256`) and it
describes the code that produced the shipped parquet. **A same-day red-team pass
(2026-09-10) then made two source changes that do not touch any computed value**
— the family-B diagnostic `n_sections_hitting_the_window_cap` was renamed
`n_sections_hitting_the_window_cap_this_run` (it was always a this-run counter:
a resumed build does not recount sections an earlier run capped), and
`--limit-filings` now REFUSES to write the production `OUT_PARQUET` unless an
explicit `--out` prefix is given, so a truncated smoke table cannot land under
the name a downstream sha assertion trusts. The current module sha is
`d2631a11d38c82a8…`. **The parquet and the manifest were deliberately NOT
rebuilt** (25 min of GPU time for a rename): the shipped artifact, its
`output_sha256` and its `module_sha256` all still describe the build-time
module, and the manifest's diagnostic still carries the old key name with the
value 1,888 — which is correct for that build, whose
`n_filings_resumed_from_partial` is 0, i.e. the count covers the whole output
frame. A future rebuild will write the new key name.
Output schema, exactly as written:

```
cik int64 · accession_number string · filing_date timestamp[ns]
novelty_risk_factors_yoy double · novelty_mda_yoy double
prior_gap_days_risk_factors double · prior_gap_days_mda double
emb fixed_size_list<float>[384] · n_sections_embedded int64
n_windows_embedded int64
```

Frozen modules: `controls.py`, `features.py`, `backtest.py`, `diagnose.py`,
`spec.py`, `pit.py`, `target_e2.py`, `features_e2.py`,
`numeric_features_e2.py` — `git status` shows **0** of them modified. The
module imports `controls._sha256_file` rather than restating it.

### 1.1 Pinned definitions (the manifest carries these verbatim under `arguments`)

**Family A.** `novelty = 1 − Jaccard(shingles(normalize(current)),
shingles(normalize(prior)))`.
`normalize` = `str.lower()` → remove every unicode digit run (regex `\d+`) →
split on whitespace and rejoin with single spaces, **in that order**.
Shingle = 5 consecutive whitespace words; a shingle's identity is the 64-bit
polynomial hash of its five word ids (word id = blake2b-8 of the word,
P = 1000003, arithmetic mod 2⁶⁴), and the shingle **set** is `np.unique` of
those hashes, so multiplicity is ignored. `blake2b`, not python's `hash()`,
because `hash()` is salted per process and would make the artifact
irreproducible (there is a test that runs a fresh interpreter and compares).
Prior = same CIK **and** same `section_type` **and** `filing_date` strictly
earlier; the maximum such `filing_date`; ties on that date broken by the
smallest `accession_number`. Candidate pool = every row of
`data/filings_e2_v2.parquet` for that CIK and section type, including
out-of-membership and out-of-scope filings (pinned as
`prior_candidate_pool`; §5 item 2). NaN when the section is absent, when no
prior exists, or when either side yields 0 shingles.

**Family B.** `sentence-transformers/all-MiniLM-L6-v2`, revision
`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, Apache-2.0, 384-d,
`model.safetensors` sha256
`53aa51172d142c89d9012cce15ae4d6cc0ca6895895114379cacb4fab128d9db`
(90,868,376 bytes), `tokenizer.json` sha256 `be50c3628f2bf5bb…`, cached at
`~/.cache/huggingface/hub/models--sentence-transformers--all-MiniLM-L6-v2`
(888 MB, **outside the repo**; `in_repo: false` is asserted in the
manifest). Each section is tokenized with `add_special_tokens=False` and cut
into consecutive **254-token** windows; 254 + `[CLS]` + `[SEP]` = 256 =
the model's `max_seq_length`, so **no window is silently truncated**. At most
the **first 64 windows** of a section are used (`max_windows_per_section`,
pinned). Window vectors are the model's own mean-pooled, L2-normalized
output; section vector = unweighted mean of its window vectors; filing
vector = unweighted mean over **section** vectors (sections weighted
equally regardless of length); the pooled vector is **not** renormalized
(`renormalize_pooled: false`). Sections embedded: all four `section_type`
values (`MDA`, `RISK_FACTORS`, `EX99_PRESS_RELEASE`, `8K_BODY`) — see §5
item 3. Device MPS, encode batch 128, float32.

## 2. Assertions enforced, with measured values

`assert_output_invariants` runs inside every build; the structural checks
below were additionally re-derived in a separate red-team pass over the
shipped parquet.

| # | assertion | measured on the shipped run |
|---|---|---|
| A1 | corpus sha256 equals `data/f4/campaign_manifest.json` `inputs.corpus_parquet_sha256` | MATCH, `15853e9f5490…` |
| A2 | target-table sha256 equals `data/f5/target_e2_manifest.json` `output_sha256` | MATCH, `c35956b784b9…` |
| A3 | one row per (cik, accession_number) | 7,723 rows, **0** duplicate keys; 7,723 distinct accession numbers; **0** accessions under more than one CIK |
| A4 | every written key is an in-membership row of `target_e2.parquet` | subset holds, **0** stray keys; `filing_date` equals the target's on **all 7,723** rows |
| A5 | **PIT**: the novelty partner is strictly earlier | min `prior_gap_days_mda` = **56 days**, min `prior_gap_days_risk_factors` = **57 days**; over all 6,972 selected pairs: **0** with prior date ≥ current date, **0** with prior = self |
| A6 | **PIT**: the partner is the same company and the same section | **0** cross-CIK priors, **0** cross-section priors over all 6,972 pairs (structurally impossible — pairs are chosen inside a `(cik, section_type)` group — and measured anyway) |
| A7 | novelty ∈ [0, 1] | RISK_FACTORS min 0.0 max 1.0 mean 0.4916 median 0.3144 (n = 3,357); MDA min 0.0 max 1.0 mean 0.5340 median 0.5097 (n = 3,615) |
| A8 | a novelty value exists iff its gap exists | 0 mismatches on both sections |
| A9 | `emb` is fixed-width 384 and finite | widths observed = {384}; all values finite; L2 norm min 0.5587, mean 0.6893, max 1.0000; the **59** rows at norm 1.0 are exactly the filings with one section and one window (verified: all 59), where the pooled vector *is* the model's normalized window vector |
| A10 | `n_sections_embedded ≥ 1` and `n_windows_embedded ≥ n_sections_embedded` | holds on all rows; sections per filing ∈ {1: 4,426, 2: 3,297}; windows per filing min 1, median 43, max 128 |
| A11 | the module contains no association machinery (freeze tripwire, enforced as a test) | source scan for `spearman`, `pearson`, `corrcoef`, `.corr(`, `linregress`, `ols(`, `polyfit`, `xgboost`, `sklearn`, `regress`: none present |
| A12 | the module never names a return column outside its docstring (freeze tripwire, enforced as a test) | `target_excess_63`, `subject_return_63`, `benchmark_return_63` absent from the module body |
| A13 | the text column is never materialized whole | reads go through `ParquetFile.iter_batches(batch_size=128, columns=["text"])`; measured peak RSS for the whole build **3.75 GB** (the corpus is 599 MB on disk / 1.47 GB of characters) |

**Independent re-derivation (red-team pass, not a self-check).**

* Novelty: 10 shipped values (5 random filings × both sections) recomputed by
  a separate script using **tuple-of-words** 5-grams (no hashing) and a
  direct pandas query for the prior — **10 / 10 match to 1e-12**, and the
  chosen prior accession/date matched in every case.
* Embeddings: 3 random filings recomputed in a fresh process with a freshly
  loaded model and straight-line code — section and window counts identical,
  max abs difference **≤ 6.7e-8** per component, cosine 0.99999988–1.0.
* Reproducibility, cold: the full build was run **cold twice** (23.6 min and
  25.6 min) and once **resuming from a COMPLETE checkpoint** (nothing left to
  embed); all three wrote the identical parquet sha256 `acc2712e358f…`.
* Reproducibility, resumed mid-way — **stated precisely, because the earlier
  wording over-promised**: a resume always reproduces the *frame* (the same
  rows, the same keys, the same novelty values, and embeddings agreeing to
  ~1e-7), but it reproduces the *parquet sha* only when the checkpoint boundary
  is a multiple of `FILINGS_PER_ENCODE_GROUP` (= 32). Filings are encoded in
  groups of 32 and the remaining work is re-grouped from the resume point, so a
  boundary that is not a multiple of 32 shifts group composition, and float32
  batch arithmetic is not composition-invariant (§5 item 8 measures the size:
  ≤ 6.7e-8 per component). The measured case — a 200-filing build with the
  checkpoint truncated to 50 filings, which embedded the remaining 150 and
  reproduced the uninterrupted run's sha `633172b8699c…` exactly — is evidence
  that the arithmetic was stable at THAT boundary, not a guarantee at every
  boundary. **Consequence for downstream sha assertions**
  (`backtest_e2.assert_input_shas` compares this parquet against the manifest's
  `output_sha256` and refuses on mismatch): treat a mid-way-resumed build as
  producing a NEW artifact — let the same build write its own manifest, and
  never edit a recorded sha to make an assertion pass. The natural checkpoints
  this module writes are group-aligned; a hand-truncated partial file is the
  case to be careful with.
* Mutation checks (against throw-away copies in a scratch directory; the repo
  files were never mutated): prior selection relaxed to `<=` (same-day
  allowed) → 4 tests fail; novelty sign flipped to Jaccard → 2 fail; window
  cap raised from 64 → 1 fails; filing pooled over windows instead of
  sections → 1 fails; shingle n 5 → 4 → 6 fail; prior taken from the later
  side (`searchsorted` right) → 3 fail.

## 3. Population, as measured

| quantity | value |
|---|---|
| in-membership core rows in `target_e2.parquet` | 16,859 |
| of those, filings with ≥ 1 section in `filings_e2_v2.parquet` — **rows written** | **7,723** (148 CIKs; `filing_date` 2016-07-05 → 2026-08-20) |
| in-membership filings with no extracted text (no row written) | 9,136 |
| rows per calendar quarter (41 quarters, 2016Q3–2026Q3) | min 166, median 192, max 207 |
| form mix of the written rows | 8-K 4,047 · 10-Q 2,774 · 10-K 902 |
| sections embedded | 11,020 (EX99_PRESS_RELEASE 3,962 · MDA 3,615 · RISK_FACTORS 3,358 · **8K_BODY 85**) |
| windows embedded | **377,542** (uncapped demand 480,070; the 64-window cap bit on **1,888 of 11,020 sections**, 17.1%, dropping 102,528 windows = 21.4% of demand) |
| novelty pairs considered (scoped RISK_FACTORS + MDA sections) | 6,973 |
| pairs with a prior | 6,972 · **without a prior: 1** (CIK 5272, accession `0000005272-17-000017`, RISK_FACTORS — its first Item 1A in the corpus) |
| ties on the prior date (tie-break exercised) | 0 |
| NaN caused by an empty shingle side | 0 |
| sections shingled (scoped + their priors) | 7,344 |
| `novelty_risk_factors_yoy` present / share of rows | 3,357 / 43.47% |
| `novelty_mda_yoy` present / share of rows | 3,615 / 46.81% |

**What the "most recent prior filing" rule actually compares** (manifest
`family_a_diagnostics.prior_gap_days_census`): MDA gap min 56, p25 86.5,
median **91**, p75 97, max 375 days; RISK_FACTORS gap min 57, p25 87, median
**91**, p75 98, max 379. Median by the current filing's form: MDA 10-K
**108**, 10-Q **91**; RISK_FACTORS 10-K **110.5**, 10-Q **91**. The measured
comparison is therefore quarter-over-quarter for almost every row, including
10-Ks (whose most recent prior Item 7 is the preceding 10-Q), not
year-over-year. The columns keep the brief's `_yoy` names; §5 item 1 is the
open question.

**Degenerate values concentrate on short sections** (manifest
`novelty_degenerate_census`): RISK_FACTORS n = 3,357 with **855 exactly 0.0**
and **516 exactly 1.0**, and **1,309 pairs (39.0%) have a side with fewer
than 50 shingles** (median of the smaller side: 86 shingles). MDA n = 3,615
with 10 exactly 0.0, 28 exactly 1.0, and 82 pairs (2.3%) with a side under 50
shingles (median of the smaller side: 6,697 shingles). In a separate
measurement over the 6,972 pairs, the 544 pairs scoring exactly 1.0 have a
median smaller-side length of **36 words** and 443 of them have a side under
50 words; the 865 pairs scoring exactly 0.0 have a median smaller side of
**41 words**. These are 10-Q Item 1A stubs ("no material changes to the risk
factors disclosed in our Annual Report"): an unchanged stub scores 0.0 and a
stub that shares no 5-gram with its partner scores 1.0.

## 4. Environment, the one download, and runtimes

`sentence-transformers` and `torch` were **not** importable in this
environment (system python 3.9.6, arm64). Installed with
`python3 -m pip install --user torch sentence-transformers` and appended to
`requirements-quant.txt` with a comment: **torch 2.8.0 ·
sentence-transformers 5.1.2 · transformers 4.57.6 · tokenizers 0.22.2 ·
huggingface-hub 0.36.2 · safetensors 0.7.0** (manifest also records python
3.9.6, numpy 1.26.4, pandas 2.2.3, pyarrow 21.0.0). The single permitted
network action was `snapshot_download("sentence-transformers/all-MiniLM-L6-v2")`
into the default huggingface cache outside the repo (44 s, 888 MB, 30 files);
every later load passes `local_files_only=True`, so builds are offline. MPS
was available and used.

| step | seconds |
|---|---|
| sha assertion of the two inputs | 0.20 |
| load corpus index + scope | 0.06 |
| family A — prior selection | 0.09 |
| family A — stream + shingle 7,344 sections | 16.56 |
| family A — 6,972 Jaccards | 1.61 |
| family B — tokenize, window, embed 377,542 windows | 1,514.4 |
| **full `python3 text_families_e2.py --no-resume`** | **1,534.7 s = 25.6 min** |
| (first cold run, machine otherwise idle) | 1,415.7 s = 23.6 min |
| re-run resuming from a complete checkpoint | 21.2 s (identical output sha) |
| `python3 -m pytest -q test_text_families_e2.py` | **26 passed**, 8.4 s (25 fast + 1 slow real-data smoke) — before the red-team pass |
| `python3 -m pytest -q test_text_families_e2.py -m "not slow"` | 25 passed, 1 deselected, 1.7 s — before the red-team pass |
| `python3 -m pytest -q test_text_families_e2.py -m "not slow"` (after the red-team pass: **+6** tests for the `--limit-filings` refusal, the `--out` prefix and the renamed counter) | **31 passed**, 1 deselected, 1.8 s |

Throughput: **249.3 windows/s** (5.1 filings/s) on MPS for the shipped run;
270.4 windows/s (5.5 filings/s) on the first cold run, when the machine was
not shared with another session. Peak RSS 3.75 GB. Checkpoint written every
500 filings; 15 checkpoints over the run.

One pytest warning, unavoidable without touching a file outside this task's
list: `PytestUnknownMarkWarning: Unknown pytest.mark.slow` — the repo has no
pytest config registering markers (`test_features_e2.py` carries the same
warning). `-m "not slow"` works regardless.

## 5. Open questions for G3 (no recommendation attached)

1. **The `_yoy` column names do not describe the measured comparison.** The
   brief's rule is "the most recent prior filing of the same section", which
   on this corpus is the previous **quarter** (median gap 91 days; 10-K rows
   median 108–110.5 days, i.e. also the preceding 10-Q). A year-over-year
   comparison would require a different rule (nearest prior filing of the
   same *form*, or the nearest prior filing ~365 days back). The columns are
   named as the brief named them; which object G3 pre-registers is a ruling.
2. **Prior-candidate pool.** Priors are drawn from the whole corpus for that
   CIK and section type, including out-of-membership filings and filings back
   to 2015-07-02 (the corpus starts a year before the universe does). That is
   why only **1** of 6,973 scoped sections has no prior. Restricting the pool
   to in-membership or scoped filings would reduce coverage; both are
   PIT-safe.
3. **8K_BODY is embedded (85 sections).** F5_PLAN §3 decision 9's default
   excludes the 790 8K_BODY *chunks* from the label-derived features because
   the student saw 0 such examples in training. That argument does not apply
   to an embedding, so this module embeds all four section types and counts
   them; if G3 wants the register excluded from family B as well, the
   embeddings must be rebuilt (25 min).
4. **Filing pooling weights sections equally.** A 60,000-word Item 1A and a
   400-word press release contribute equally to `emb`. Length-weighted
   pooling (by windows) is one line and a rebuild; `n_sections_embedded` and
   `n_windows_embedded` are written so the alternative is measurable.
5. **The 64-window cap bit on 1,888 of 11,020 sections (17.1%), discarding
   21.4% of window demand.** The cap is a pinned argument; the affected
   sections are the long Item 1A / Item 7 bodies, so the pooled vector for
   those filings represents their first ~16,256 tokens.
6. **The RISK_FACTORS novelty column is largely a stub detector.** 39.0% of
   its pairs have a side under 50 shingles, 855 values are exactly 0.0 and
   516 exactly 1.0. Whether G3 pre-registers a minimum-length filter, a
   separate stub indicator, or the column as measured, is a ruling; nothing
   is filtered here.
7. **Pooled vectors are not L2-renormalized** (norms 0.559–1.000, mean
   0.689), so a downstream cosine/dot treatment and a downstream
   Euclidean treatment differ. If G3's specification consumes the embedding
   through `spec.pit_trailing_rank_frame`, the per-component ranks are
   invariant to a *global* rescale but not to the per-row norm variation.
   The dimensionality reduction G3 pins (`embedding PCA k`) is downstream of
   this file and is not implemented here.
8. **Determinism is byte-exact for identical inputs and code, but the
   embedding column is only ~1e-7-stable under a different batching.** Three
   builds (two cold, one resumed) produced the identical sha; an independent
   re-implementation with different batch sizes agreed to ≤ 6.7e-8 per
   component. A future rebuild with a different `encode_batch_size` will not
   be byte-identical.
9. **Coverage.** 9,136 of 16,859 in-membership rows have no extracted text
   and therefore no row here — F5_PLAN §3 decision 4 already records that
   F3/F4 extracted text only for earnings-bearing 8-Ks. The analysis frame is
   the three-way join with `numeric_features_e2.parquet`; this file does not
   perform that join and computed nothing across it.
10. **Third-party artifact.** The embedding model is an unratified external
    input (G3 §12 ratifies it). Its weights sha, revision and license are
    pinned in the manifest; it was downloaded once from huggingface.co and
    never re-fetched.
