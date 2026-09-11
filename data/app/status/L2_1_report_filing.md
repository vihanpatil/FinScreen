# L2.1 — per-filing HTML renderer (`report_filing.py`)

**Status: BUILT 2026-09-11; RED-TEAMED and REPAIRED the same day. Not an owner
ruling — this is the implementation record of the app lane's first
deliverable, ruled by the owner on 2026-09-11 (HANDOFF §3, "PERSONAL-USE
DIRECTION RULED"). Open questions for the owner are in §11; three of
the ten raised in the first draft are now CLOSED in code and are recorded as
such.**

Deliverables: `report_filing.py`, `test_report_filing.py`, this file. The fix
pass also touched `test_features_e2.py` (one test's output paths) and added a
minimal `pytest.ini` at the repo root — both listed in §0 with their reasons.
E1 modules, the target / backtest / heads modules, `HANDOFF.md`,
`RESUME_HERE.md`, `README.md`, `F5_PLAN.md` and `.gitignore` are untouched
(`.gitignore` already excluded `data/app/reports/` and `data/app/**/*.parquet`
as of commit 09c5d6a).

Cost: $0. No network, no API, no GPU. Standard library + pandas/pyarrow;
no new dependency.

---

## 0. What the red-team found, and what changed

The first draft shipped a page that looked right and was not. Twelve findings
were raised; all twelve are addressed. The blocker is first.

| # | Finding | Disposition |
|---|---|---|
| 1 | **BLOCKER — text containment.** A chunk was attributed to a filing whenever the accession appeared in `source_accession_numbers`, but that array is the UNION over the chunk's paragraphs. The Apple FY2024 10-K page rendered **30,706 words** where the filing's MD&A + Risk Factors hold **12,355**; 242 of 417 rendered paragraphs (58%) were not in the filing at all, and seven passages were homed at other issuers. | FIXED. `apply_containment` checks every candidate paragraph for physical containment in THIS filing's own section text and renders only what is contained. §1. |
| 2 | NEGATIVE recall 0.487 is the **v1.1** student's number, not this labeler's. | FIXED. The header now quotes **0.529 (64/121)** from the adapter that actually labeled the corpus, sha-pinned. §2. |
| 3 | The rendered-output refusal scan deleted the whole text-col div, taking the report's own markers out of the scan with the filing's words; the cross-company assertion was vacuous. | FIXED and demonstrated against the red-team's own mutation. §6. |
| 4 | The renderer read `data/backtest_report.md` at render time — an outcome artifact, which is the council's kill criterion. | FIXED. Two module constants + a runtime file-open guard. §3. |
| 5 | `features_e2` pulls `controls`, which pulls `backtest`. | KEPT (the mask must stay derived) and BOUNDED by three tests. §3. |
| 6 | Disclosure wording: the sentiment estimand was unstated; 22.2% / 26.8% / 46.0% were unattributed. | FIXED. §2. |
| 7 | Train-overlap banner counted pre-containment passages and never fired on the index. | FIXED. §4. |
| 8 | `prior_same_form` relied on the caller's sort order. | FIXED — it sorts for itself; tested on shuffled frames. |
| 9 | `mask_flags`'s probe could silently mask everything if a label map changed. | FIXED — the probe asserts its own precondition and raises. |
| 10 | This document's test count and its §1 corpus claim were wrong. | FIXED. §1, §7. |
| 11 | The `slow` marker was unregistered; the index listed filings with no homed passage; the company name in `<h1>` was inside the vocabulary scan. | FIXED. `pytest.ini`, an index footnote, an `<h1>`/`<title>` exclusion. |
| 12 | Running `test_features_e2.py`'s slow real-data test rewrote two **committed** `data/f5` artifacts. | FIXED in the test. §9. |

**Files edited outside the L2.1 lane, and why.**

* `pytest.ini` (new, 8 lines) — registers the `slow` marker so `pytest -q`
  stops printing a `PytestUnknownMarkWarning` per slow test. It sets nothing
  else: no `addopts`, no `testpaths`, no `filterwarnings`. Collection and
  behaviour are otherwise identical to having no file.
* `test_features_e2.py` — `test_real_build_reproduces_every_pinned_census_number`
  now redirects `features_e2`'s three output paths into `tmp_path`. See §9 for
  why the fix landed in the test rather than as a `build(out_dir=...)`
  parameter: `features_e2.py` cannot be edited without invalidating
  `text_features_e2_manifest.json`'s `module_sha256`, and that manifest is a
  committed artifact this pass may not rewrite.

---

## 1. Containment — the blocker, and the property that replaced the wrong one

### What the first draft claimed, and what was actually verified

The first draft's §1 said: *"A chunk is attributed if its
`source_accession_numbers` array contains this accession — the array is E2's
occurrence primitive, and a chunk's home accession is always in it (verified
corpus-wide: 0 exceptions)."*

Both measured facts in that sentence are true. Neither supports the
conclusion drawn from them. Stated precisely, what E2 verifies is:

* **home ∈ sources.** Every chunk's own `home_accession_number` appears in its
  `source_accession_numbers` array — 0 exceptions over 317,081 chunks. This
  makes the occurrence map a superset of each filing's own chunks; it says
  nothing about the other entries in the array.
* **no backward flow.** No occurrence attaches a chunk to a filing dated
  before that chunk's home filing date — 0 violations over 854,933 frame
  occurrences (`features_e2.verify_no_backward_flow`). This is a *dating*
  property: it rules out look-ahead, not misattribution.

What is NOT true, and was assumed: that every paragraph of a chunk is present
in every filing its array names. The array is the **union over the chunk's
paragraphs** (`finetune/build_f4_chunks.py:436-448`; `features_e2.py:60-70`
records the consequence and calls it a G3 disposition question). One shared
boilerplate paragraph pulls a whole chunk — and all of its other companies'
words — into a filing it has almost nothing to do with.

### The property the renderer now enforces

> Every paragraph rendered on a filing's page is a whitespace-collapsed
> substring of THAT filing's own extracted section text for the same section
> (`data/filings_e2_v2.parquet`, filtered on `accession_number`).

Mechanics, in `apply_containment`:

* a chunk whose paragraphs are **all** contained renders whole;
* a chunk **partly** contained renders carrying only its contained paragraphs,
  under the marker *"Partial: N of M paragraphs of this corpus passage are in
  this filing. The rest belong to other filings the chunker merged into the
  same passage and are not shown."*;
* a chunk with **no** contained paragraph never renders.

The same filter runs over the prior same-form filing **before** the diff, so
NEW / REMOVED describe the two filings' texts rather than their occurrence
arrays. Every passage now also carries *"This passage appears in N filings in
the corpus"* (`n_source_filings`), which is the honest signal about shared
boilerplate.

It is a physical test — substring containment — not a similarity measure. No
threshold, no degree, no ordering. The section text in
`filings_e2_v2.parquet` carries no paragraph separators (each section is one
blob), so substring containment is also the only test available; paragraph-set
membership was measured and matches nothing.

### Measured, on the two real filings

| | FY2024 10-K `0000320193-24-000123` | Q1-FY2025 8-K `0000320193-25-000007` |
|---|---|---|
| words rendered **before** the fix | 30,706 | 2,496 |
| words rendered **after** | **12,397** | **1,365** |
| words the extractor recorded for these sections | 12,355 | 1,383 |
| candidate passages → rendered | 75 → **73** (55 partial, 2 dropped) | 6 → **6** (3 partial, 0 dropped) |
| paragraphs rendered / candidate paragraphs | 175 / 417 | 25 / 37 |
| **rendered paragraphs contained in the filing** | **175 / 175 = 100%** | **25 / 25 = 100%** |
| NEW / REMOVED / UNCHANGED | 26 / 24 / 47 | 3 / 5 / 3 |
| new red-flag categories | 0 | 0 |

The ±0.3% / −1.3% gap between rendered words and the extractor's recorded
word count is definitional, not missing text: `word_count` is the extractor's
own tokenization of the whole section, the rendered figure is
`len(paragraph.split())` summed over rendered paragraphs. The slow test
asserts the ratio stays inside [0.80, 1.05] on both filings.

### The seven issuers that were leaking

Before the fix, passages homed at **MICRON, CELGENE, STRYKER, QUALCOMM,
Palo Alto, LAM RESEARCH and CADENCE** rendered on the Apple 10-K page under
the marker "Shared boilerplate, first seen in … (`<that company>`)".
**None of those names appears anywhere on either page now**, asserted by
`test_real_apple_10k_names_no_other_issuer`.

The three chunk ids the review named, individually:

* `E2CHK-87ba8ba42c3ce6f0` (Micron, RISK_FACTORS, 9 paragraphs) — **0
  contained. Gone entirely.**
* `E2CHK-b5405964f2346d4e` (Celgene, MDA, 8 paragraphs) — 7 paragraphs
  dropped. Its **1** contained paragraph is the literal string `®`.
* `E2CHK-059b32bc6d2a0405` (Stryker, MDA, 5 paragraphs) — 4 dropped. Its **1**
  contained paragraph is `Legal and Other Contingencies`.

Two of the three therefore still render, as one-paragraph partials. Being
straight about it: those two paragraphs **are** in Apple's MD&A — they are the
section heading and a registered-trademark glyph, deduplicated by the chunker
into whichever filing happened to contain them first, which was Qualcomm's or
Stryker's. What made the old page wrong was not their presence but the seven
other issuers' *words* beside them and the marker naming those issuers. Both
are gone: the deduplication marker now names the home **accession, form and
date only**, never the home company, because after containment the words below
it are this filing's own and "first seen in STRYKER CORP" read as a claim
about Apple's text. The same pattern holds for Qualcomm's
`Liquidity and Capital Resources`, Cadence's `Critical Accounting Estimates`
and Lam Research's `Uncertain Tax Positions`.

### Tests

`test_every_rendered_paragraph_is_inside_the_filing_text` (synthetic frame),
`test_rendered_html_quotes_only_this_filings_own_words` (synthetic HTML),
`test_real_every_rendered_paragraph_is_inside_the_filing` and
`test_real_rendered_html_quotes_only_this_filings_own_words` (both real
filings, frame and HTML), `test_a_chunk_with_no_contained_paragraph_never_renders`,
`test_a_chunk_homed_in_another_company_renders_only_if_contained`,
`test_partial_chunks_keep_only_their_contained_paragraphs`,
`test_diff_on_a_synthetic_pair_is_exact`.

The synthetic fixture is built so the diff has a right answer that is not a
restatement of the code: `C-here-only` and `C-prior-only` are attributed to
**both** filings by their occurrence arrays and would both be UNCHANGED
without containment; each is physically in exactly one of the two, so the
diff must split them. `C-foreign` is in neither and must appear nowhere.

---

## 2. The mandatory disclosure header

Every number is read from a committed artifact at render time, with two
deliberate exceptions recorded below. Nothing is typed except the wording
around the numbers.

| Disclosure item | Source |
|---|---|
| labeler = v1.2 student, adapter sha `cadca8499b66…`, "model output throughout" | `data/f4/campaign_manifest.json` + `results_g2.json` `provenance` |
| sentiment 293/337 = 86.9% [82.9, 90.1], INDETERMINATE at the 0.85 bar | `results_g2.json` `primary.sentiment` |
| **what that number IS** — "chunk-level label agreement under the applicability mask — MD&A and press-release chunks — against a model-consensus reference; not accuracy against human ground truth" | `SENTIMENT_ESTIMAND`, rendered beside the artifact's own `caveat` string verbatim |
| **NEGATIVE recall 0.529 (64/121)** | `finetune/runs/2026-08-28-v12-eval-epoch2/metrics.json` — **this labeler's own held-out eval** |
| "model consensus, not human validation" | rendered verbatim beside the sentiment line |
| guidance 115/119 = 96.6% [91.7, 98.7] on the NONE mass, active precision 68.7% [58.2, 77.6], false-NONE 0/80 | `results_g2.json` |
| the G2 §0 first paragraph, verbatim | parsed out of `G2_FINAL_REPORT.md`, never transcribed |
| red flags EXPLORATORY: teacher 84/200 = 42.0% [35.4, 48.9] | `results_v12.json` `P1_exact_set_error` |
| student 112/400 = 28.0% [23.8, 32.6] | `results_g2.json` (k derived as point × n, refused unless integral) |
| **config-sensitivity 935/4,219 chunks (22.2%), labelled as E1's TEACHER measurement** | prose constants, pinned to the HANDOFF sentence |
| predictive validity: "E1 (25 companies): no fold-robust text signal (+0.0177 raw / −0.0097 dedup IC delta); E2: not run" | **module constants**, pinned to `data/backtest_report.md` by a test — see §3 |
| train-overlap banner | `finetune/splits_v12/train.parquet` under `features_e2.TRAIN_OVERLAP_DEFINITION` — §4 |
| **self-identification 26.8% / 46.0%, labelled as E1 measurements** | prose constants, pinned to the HANDOFF sentence |
| "No price data is used anywhere in this report." | constant |
| footer, identity line | the ruling's own sentences |

### Item 2 — the NEGATIVE recall now matches the labeler

The ruling and the council's Q4 block both say "NEGATIVE recall 0.487". That
figure is from `finetune/runs/2026-08-22-eval-epoch2/metrics.json` — the
**epoch-2 / rubric-v1.1** student, a different model on a different split
under a different rubric. The adapter that produced every label in this corpus
(`cadca849…`, per `data/f4/campaign_manifest.json`) measured **NEGATIVE recall
0.529 — 64 true positives against support 121** on its own held-out eval. The
header now quotes **0.529**, names its file, and prints the raw 64/121 beside
it. `0.487` appears nowhere in the rendered page.

That file's sha256 (`21c3360f38a4…`) is pinned in `DISCLOSURE_SOURCE_SHA256`
and recomputed by `test_disclosure_source_shas_are_pinned`, and
`test_the_quoted_negative_recall_is_this_labelers_own_number` asserts the
adapter in the campaign manifest is the one whose eval is quoted.

This **supersedes open question §7.1 of the first draft**, which asked which
number should ship. It is a correction of fact, not a scope change: the ruling
named 0.487 because that was the number in circulation, and the header would
otherwise have quoted one model's error rate beside another model's labels.
Flagged for the owner in §8.1 in case they want the ruled figure restored,
in which case it must carry the words "superseded v1.1 student, different
split and rubric".

### Item 6 — what the numbers are measurements OF

* **Sentiment.** The estimand sentence above renders in the header, followed
  by the artifact's own `caveat` field as a blockquote. Agreement against a
  model-consensus reference is not accuracy against human ground truth, and
  the page now says so in the same breath as the number.
* **22.2%.** Rendered as *"Config-sensitivity 935/4,219 chunks (22.2%) is E1's
  teacher labels, compared against themselves across two labeling configs on
  E1's 4,219-chunk corpus — an E1 TEACHER measurement, not a measurement of
  the v1.2 student that labeled this corpus."*
* **26.8% / 46.0%.** Rendered with *"Both figures are measured on E1
  (REDTEAM_WEEK3.md finding #2), strict and loose method; not re-measured on
  E2."*

`test_prose_constants_still_match_their_source_document` no longer greps for a
bare `22.2%`. It pins the two exact HANDOFF sentences —
``` `red_flags` changed on 935/4,219 chunks (22.2%) ``` and
`method 26.8% overall, loose method 46.0% overall` — and a companion test pins
the sha256 of each of those HANDOFF lines, so an edit that keeps the number but
changes what it is a number *of* fails with a re-pin instruction.

---

## 3. No outcome artifact is reachable, opened, or read

Three independent guards, because the council's kill criterion ("report layer
found reading an outcome table or IC → app lane halts") deserves more than a
source grep.

**(a) The E1 deltas are constants, not a render-time read.** `report_filing`
holds `E1_IC_DELTA_RAW = 0.0177` and `E1_IC_DELTA_DEDUP = -0.0097`. The regex
that lifted them out of `data/backtest_report.md` moved into
`test_e1_ic_deltas_match_the_backtest_report_they_came_from`, which pins that
report's sha256 (`a313cea8…`), re-parses both sentences and asserts the
constants match. The module no longer contains the string `backtest_report`
at all (`test_the_module_never_names_the_backtest_report`).

**(b) The transitive import closure is pinned.** `features_e2` imports
`controls` for path constants and a file hasher; `controls` imports
`backtest`. Both are therefore in `sys.modules` whenever the renderer is.
**The imports are kept** — removing them means not importing the F5 modules,
i.e. restating the section mask, which the ruling forbids.
`test_transitive_import_closure_is_exactly_what_is_documented` walks the
first-party import graph from `report_filing` and asserts it is exactly
`{backtest, controls, edgar_client, features, features_e2, ingest_fundamentals,
ingest_metadata, numeric_features_e2, pit, report_filing, spec}` — so
`controls` and `backtest` are present *by record*, and no new module can enter
the closure unnoticed. `prices_e2`, `target_e2`, `backtest_e2`, `heads_e2`,
`price_client` and `ingest_prices` are asserted absent.

**(c) Nothing in the outcome layer is CALLED, and nothing is OPENED.**

* `test_no_outcome_layer_function_is_reachable_from_a_render` builds a static
  AST call graph out of `render_filing` and `render_index`, following
  same-module calls, `from X import f` symbols and `X.f()` module attributes
  transitively. The reachable set spans exactly five modules —
  `report_filing`, `features_e2`, `numeric_features_e2`, `features`, `pit` —
  and **no function of `controls` or `backtest` is in it**. `controls` and
  `backtest` are loaded but unreachable: no price-loading function
  (`controls.load_price_matrix`, `controls.attach_returns`,
  `backtest.load_modeling_frame`, …) can run on any render path.
* `test_render_opens_no_outcome_artifact` patches `builtins.open`,
  `Path.read_text`, `Path.read_bytes`, `pandas.read_parquet`,
  `pandas.read_csv`, `pyarrow.parquet.read_table`,
  `pyarrow.parquet.ParquetFile` and `sqlite3.connect`, renders a real filing
  and a real index, and lists every path opened. It asserts none matches
  `prices_e2.parquet`, `target_e2.parquet`, `backtest_report.md`, `data/f5/`,
  `text_features_e2`, `backtest_e2` or `heads_e2` — **and** that every path
  opened is on a documented allow-list, so a new read cannot enter silently.

Measured: a full 10-K render opens 13 distinct files — the cache, the two F4
parquets, the campaign manifest, the training split, the metadata DB, the
section table, the two G2 artifacts, the v1.2 spot-check, the v1.2 eval, the
fundamentals table and F2's concept resolution. Nothing else.

This **closes open questions §7.5 and §7.6 of the first draft.**

---

## 4. Train-overlap banner, recounted

`features_e2.TRAIN_OVERLAP_DEFINITION` has three channels: home accession, any
source accession, normalized-text identity. The first two are baked into the
cache (`CACHE_VERSION` bumped to `app-index-v2`); the third needs the 788 MB
text column and is computed per filing at render time with the same
`_sha1_norm` normalizer.

Two changes:

1. **The count runs on the CONTAINED frame.** A passage containment dropped is
   not on the page and must not raise the banner's numbers. The text channel
   still hashes the **raw** chunk text, because it asks whether this corpus
   passage *is* a training passage and a trimmed passage is no longer that
   corpus object.
2. **The accession channel is split in two**, because the two halves say
   different things and the second is inflated by the same union-array effect
   containment exists to undo:
   * *"N of M passages are stored under a filing that is itself in the v1.2
     training split"* — this passage IS a training passage;
   * *"N of M passages are also attributed to a training filing by the corpus
     (a shared paragraph, not this filing's own text)"*.

**Measured on the Apple FY2024 10-K:** the banner fired on 7 of 75 passages
before; it now reports **5 of 73**, all of them in the second, inherited
channel — **0 passages are homed in a training filing**, and no Apple
accession is in the v1.2 split at all. Apple is not one of the 22 training
CIKs. The banner is silent on the Q1-FY2025 8-K (0/6 on every channel).

The review expected "only its own 2020 10-Q hit". That is the *home* view of
one of the five: `E2CHK-7f347e6df90795ad` is homed in Apple's own
`0000320193-20-000062` (a 2020 10-Q), which is **not** in the training split —
it trips the channel because its union array names two training filings of
another company. The other four trip it the same way, via the one-word
headings described in §1. Under `features_e2`'s definition — which the report
imports and may not restate — 5 of 73 is the correct count, and the split
banner now makes the distinction legible on the page.

3. **The index page fires the banner too.** `render_index` calls
   `train_cik_overlap(cik)`, which asks the company-level question (the only
   one an index can ask, since it shows no passage). An index for one of the
   22 training CIKs links to reports whose labels are all memorized fits; a
   page with no banner read as though that were not so.

---

## 5. The section mask is derived, not restated (unchanged, plus one guard)

`mask_flags()` calls `features_e2.score_labels` on a **probe copy** of the
frame in which every row carries a label value that maps through
`SENTIMENT_MAP` / `GUIDANCE_MAP`. A NaN in the probe's scored column therefore
means *this row's field was masked*, not *this row had no label*.
`test_mask_is_derived_from_features_e2_not_restated` monkeypatches
`score_labels` to a stricter rule and asserts the report's mask follows.

**New (item 9):** the probe now asserts its own precondition. If
`SENTIMENT_MAP` lost `NEUTRAL` or `GUIDANCE_MAP` lost `MAINTAINED`, every
field would read as masked and the page would quietly show **no labels at
all**. `mask_flags` raises instead, with the message *"the mask probe … no
longer maps to a number … the report would silently show no labels at all"*.
Two parametrized tests strip each key in turn and assert the raise; a third
asserts both probe values are live keys of the imported maps.

Rendering consequences are unchanged and all still tested: RISK_FACTORS hides
sentiment; MDA / RISK_FACTORS hide guidance; imputed NONE carries the G2 §0
sentence; `schema_valid = false` shows "invalid enum, not remapped" with
branching on the stored label columns only; every red flag carries an inline
`exploratory` tag; `8K_BODY` renders text with no label values.

---

## 6. The rendered-output refusal scan, and the mutation that beat the old one

### The blind spot

`chrome_only()` removed three regions before scanning: the disclosure block
(ruled allow-list), the disclosure footer line (ruled allow-list), and
`<div class="text-col">…</div>` — the filing's quoted words. The third removed
**the report's own markers along with the filing's words**, because the
markers live inside that div. Anything the renderer emitted there was
invisible to the scan.

### The fix

`chrome_only` now removes only the **quoted paragraphs**: the `<p>` elements
with no class inside a text-col. Every `<p class="small">` marker the report
writes in that div — the deduplication marker, the partial marker, the
`n_source_filings` line — stays in the scanned chrome.
`test_the_chrome_scan_still_sees_the_reports_own_markers` asserts all three
markers are present in the chrome and that the filing's own sentences are not.

Two more changes:

* **HTML tag names are whitelisted by TAG, not by word.** `strip_tag_names`
  drops a whitelisted tag name and keeps its attributes in the scan, so
  `<summary>` is markup while the word "summary" written in a sentence still
  fails. `summary` / `summaries` were added to the refused vocabulary at the
  same time (the ruling refuses generative summaries), which is what makes the
  whitelist load-bearing.
* **The `<h1>` and `<title>` are excluded** — a company's own name is not
  vocabulary. A company called "Best Buy" no longer fails the scan. This
  matters for L2.2, where any ticker may be requested.

### The cross-company assertion is no longer vacuous

`test_rendered_page_has_no_cross_company_table` asserted a string that could
not appear. It now asserts, on the real Apple 10-K page, that none of
**MICRON, CELGENE, STRYKER, QUALCOMM, Palo Alto, LAM RESEARCH, CADENCE**
appears anywhere on the page — chrome, markers or quoted text — plus the
original header check.

### The mutation, re-run

The red-team's mutation is
`"sc"+"ore" + " 9.1 — " + "st"+"ock" + " up since filing"` emitted inside
text-col. Applied to `passage_html` and run against the suite:

| Mutation | Old suite | New suite |
|---|---|---|
| **A** — emitted as `<p class="small">` (the report's own voice) | `chrome_only` on the real Apple page returned **`[]`** — clean | **`['score', 'stock']`** — **8 failures**, including `test_rendered_chrome_contains_no_refused_vocabulary` and `test_real_report_chrome_carries_no_refused_vocabulary`, the two that were blind |
| **B** — emitted as a bare `<p>` (indistinguishable from quoted text) | — | **2 failures**, caught by `test_module_chrome_carries_no_action_vocabulary` (the module's string literals) |

Both mutations were reverted; the suite is green.

Mutation A is now also a **standing test** —
`test_the_chrome_scan_catches_a_refused_line_emitted_inside_text_col`
monkeypatches `passage_html` to inject the line and asserts the scan returns
`score` and `stock`. The scan cannot silently regress into vacuity again.

**Residual, recorded.** Mutation B was caught by the *source* scan because the
injected line was a literal in the module. A line assembled at runtime from
non-literal parts and emitted as a bare `<p>` inside a text-col would evade
both the source scan and the chrome scan — a bare `<p>` there is, by
construction, indistinguishable from the filing's words. The compensating
control is containment, asserted on the HTML itself:
`test_rendered_html_quotes_only_this_filings_own_words` (synthetic) and
`test_real_rendered_html_quotes_only_this_filings_own_words` (both real
filings) extract every unclassed `<p>` from every text-col and assert each one
is inside this filing's own section text — or, in the REMOVED block of the
diff, the prior filing's. Below the "The filing, section by section" heading,
only this filing's text is permitted. An injected sentence is in neither.

---

## 7. Every enforcement test

`test_report_filing.py` — **98 tests from 93 functions: 82 fast (1.6 s),
16 `@pytest.mark.slow` real-data (49 s)**. All pass.
`test_features_e2.py` (31) + `test_numeric_features_e2.py` (24) = **55**, all
pass — the first draft's "51 passed" was wrong and is corrected here.
The **full suite is 1,661 passed in ~5 m 20 s**, offline, with the one
pre-existing numpy RuntimeWarning in `test_ingest_prices.py` and — since
`pytest.ini` — no `PytestUnknownMarkWarning` at all.

### Containment (14)
`test_collapse_whitespace_is_the_only_normalisation` ·
`test_split_paragraphs_uses_the_blank_line_separator` ·
`test_contained_paragraphs_ignores_whitespace_differences` ·
`test_every_rendered_paragraph_is_inside_the_filing_text` ·
`test_a_chunk_with_no_contained_paragraph_never_renders` ·
`test_a_chunk_homed_in_another_company_renders_only_if_contained` ·
`test_partial_chunks_keep_only_their_contained_paragraphs` ·
`test_partial_marker_says_how_many_paragraphs_survived` ·
`test_a_fully_contained_chunk_carries_no_partial_marker` ·
`test_n_source_filings_is_shown_on_every_passage` ·
`test_containment_stats_add_up` ·
`test_shared_boilerplate_marker_never_names_another_company` ·
`test_apply_containment_on_an_empty_frame_is_empty` ·
`test_a_section_missing_from_the_filing_renders_nothing`

### Section mask (7)
`test_mask_hides_sentiment_on_risk_factors_only` ·
`test_mask_hides_guidance_on_mda_risk_factors_and_non_applicable` ·
`test_mask_is_derived_from_features_e2_not_restated` ·
`test_mask_does_not_confuse_a_null_label_with_a_masked_one` ·
`test_mask_probe_refuses_to_run_if_its_label_stops_mapping[SENTIMENT_MAP]` ·
`…[GUIDANCE_MAP]` · `test_mask_probe_labels_are_live_keys_of_the_imported_maps`

### Label rendering (5) — unchanged from the first draft

### Passages (5)
`test_8k_body_renders_text_but_no_labels` ·
`test_a_passage_homed_here_is_not_marked_as_deduplicated` ·
`test_filing_frame_collects_home_and_inherited_candidates` ·
`test_filing_frame_order_is_deterministic` ·
`test_word_count_shown_is_the_rendered_word_count`

### Prior-filing diff (7)
`test_diff_on_a_synthetic_pair_is_exact` ·
`test_diff_lists_only_newly_appearing_red_flag_categories` ·
`test_diff_ignores_red_flags_on_the_non_evaluable_section` ·
`test_unchanged_block_is_collapsed_by_default` ·
`test_prior_same_form_is_strictly_earlier_and_same_form` ·
`test_prior_same_form_sorts_for_itself_on_an_unsorted_frame` ·
`test_prior_same_form_never_returns_the_same_day_filing`

### Disclosure header (8) + the E1 null sentence (3) + prose constants (2)
`test_disclosure_source_shas_are_pinned` ·
`test_the_quoted_negative_recall_is_this_labelers_own_number` ·
`test_every_disclosure_number_comes_from_its_artifact` ·
`test_disclosure_header_renders_every_ruled_number` (34 required tokens) ·
`test_disclosure_states_the_sentiment_estimand` ·
`test_disclosure_attributes_the_e1_prose_numbers_to_e1` ·
`test_disclosure_header_carries_the_g2_section_zero_paragraph` ·
`test_disclosure_header_is_not_collapsible` ·
`test_e1_ic_deltas_match_the_backtest_report_they_came_from` ·
`test_the_module_never_names_the_backtest_report` ·
`test_predictive_validity_is_one_replaceable_constant` ·
`test_prose_constants_still_match_their_source_document` ·
`test_prose_constant_sentences_are_sha_pinned_in_their_source`

### Train-overlap banner (5)
`test_banner_fires_for_a_training_cik` ·
`test_banner_fires_for_a_training_accession` ·
`test_banner_separates_the_home_channel_from_the_inherited_one` ·
`test_banner_is_silent_when_nothing_overlaps` ·
`test_overlap_definition_is_imported_from_features_e2`

### REFUSALS — source scan and import closure (7)
`test_source_scan_no_forbidden_name_appears_in_the_module` (now scanned over
the module with only its DOCSTRING removed, so code **and comments** are held
to it) · `test_the_docstring_names_the_outcome_layer_only_to_disclose_the_closure` ·
`test_source_scan_no_forbidden_import_statement` ·
`test_the_distress_column_is_never_loaded` ·
`test_module_chrome_carries_no_action_vocabulary` ·
`test_transitive_import_closure_is_exactly_what_is_documented` ·
`test_no_outcome_layer_function_is_reachable_from_a_render`

### REFUSALS — rendered output (10)
`test_rendered_chrome_contains_no_refused_vocabulary` ·
`test_the_chrome_scan_still_sees_the_reports_own_markers` ·
`test_the_chrome_scan_catches_a_refused_line_emitted_inside_text_col` ·
`test_html_tag_names_are_whitelisted_by_tag_not_by_word` ·
`test_a_company_name_in_the_h1_or_title_is_not_scanned_as_vocabulary` ·
`test_rendered_html_quotes_only_this_filings_own_words` ·
`test_rendered_page_has_no_javascript` ·
`test_rendered_page_never_shows_the_excluded_label` ·
`test_rendered_page_has_no_cross_company_table` ·
`test_disclosure_block_is_the_only_allow_listed_region`

### Determinism (2) and units (7) — as the first draft, plus
`test_section_records_drops_the_text_column`

### Real data, `@pytest.mark.slow` (12 functions, 16 cases)
`test_real_filing_renders_under_ten_seconds[10-K | 8-K]` ·
`test_real_render_is_byte_identical_on_a_second_run` ·
`test_real_every_rendered_paragraph_is_inside_the_filing[10-K | 8-K]` ·
`test_real_rendered_html_quotes_only_this_filings_own_words[10-K | 8-K]` ·
`test_real_apple_10k_names_no_other_issuer` ·
`test_real_report_chrome_carries_no_refused_vocabulary` ·
`test_real_index_page_has_no_label_derived_column` ·
`test_real_index_page_skips_filings_with_no_homed_passage` ·
`test_real_index_page_fires_the_train_overlap_banner_for_a_training_cik` ·
`test_real_masks_hold_on_the_corpus` ·
`test_real_ticker_resolves_to_the_expected_cik` ·
`test_render_opens_no_outcome_artifact[filing | index]`

---

## 8. Performance, cache and the index page

| | |
|---|---|
| One-time cache build | 2.4 s → `data/app/cache/chunk_index_v1.parquet`, 6.0 MB, 317,081 rows (metadata + labels, **no passage text**) |
| Cache invalidation | the two F4 parquets' sha256 and `CACHE_VERSION` (`app-index-v2`) are stamped into the parquet's Arrow schema metadata; any drift rebuilds automatically |
| Render, 10-K (73 passages) | **3.3 s** including interpreter start |
| Render, earnings 8-K (6 passages) | **3.0 s** |
| Render, index (91 filings) | **0.8 s** |
| Where the added time goes | one filtered `pq.read_table` per filing over `filings_e2_v2.parquet` (~0.9 s each, this filing and its prior) — the section **record** and the section **text** come from that single read, not two |

The <10 s budget is met with ~3× headroom; the slow test asserts it.

**Index page.** Filings with **zero** homed passages are skipped and counted
in a footnote instead: not one paragraph of such a filing is stored under its
own accession, so a report for it would be assembled entirely out of other
filings' rows. Measured on Apple: **0 of 91** filings are skipped — the
footnote reads "0 further labeled filings…". The path is covered by
`test_real_index_page_skips_filings_with_no_homed_passage`, which derives the
expected set from the corpus rather than pinning a number.

---

## 9. The F5 test-hygiene bug (item 12)

Running `test_features_e2.py::test_real_build_reproduces_every_pinned_census_number`
called `features_e2.build()`, which writes three artifacts into `data/f5/`.
Two of them — `feature_dictionary_e2.json` and `text_features_e2_manifest.json`
— are **committed**, and the manifest carries a `generated_utc` timestamp, so
every run of the suite left a dirty tree.

**Fixed in the test**: it now redirects `features_e2.OUT_PARQUET`,
`OUT_MANIFEST`, `OUT_DICTIONARY` and `F5_DIR` into `tmp_path` via
`monkeypatch`, and asserts the three artifacts land there. No feature
computation changed; only where the result is written.

**Why not a `build(out_dir=…)` parameter**, which was the suggested fix and is
the cleaner API: `text_features_e2_manifest.json` records
`module_sha256 = sha256(features_e2.py)` and
`test_artifact_on_disk_matches_this_module_and_its_manifest` asserts it, with
the message *"manifest is stale — re-run `python3 features_e2.py`"*. **Any**
edit to `features_e2.py` invalidates that pin, and the only way to restore it
is to regenerate the manifest — i.e. to rewrite a committed `data/f5` artifact,
which is exactly what this item forbids and what this pass is scoped out of.
The parameter was implemented, measured against that constraint, and reverted;
`features_e2.py` is byte-identical to HEAD. The monkeypatch achieves the whole
stated goal (`git diff` clean under `data/f5` after the suite) with no
production change at all. If the owner wants the parameter, it has to travel
with a deliberate `features_e2.py` re-run and a manifest commit.

---

## 10. The two real filings, re-rendered

Core company: **Apple Inc., CIK 320193** (`core` stratum, tech, current member).

| | 10-K | earnings 8-K |
|---|---|---|
| accession | `0000320193-24-000123` | `0000320193-25-000007` |
| filed | 2024-11-01 (FY2024) | 2025-01-30 (Q1 FY2025, items 2.02, 9.01) |
| path | `data/app/reports/320193/0000320193-24-000123.html` | `data/app/reports/320193/0000320193-25-000007.html` |
| size | 377 KB (was 620 KB) | 53 KB (was 69 KB) |
| passages rendered | **73** of 75 candidates (55 partial) | **6** of 6 (3 partial) |
| words rendered / section words | **12,397 / 12,355** | **1,365 / 1,383** |
| rendered paragraphs contained | **175 / 175 = 100%** | **25 / 25 = 100%** |
| sections | MDA, RISK_FACTORS — both `OK` / `high` / `anchor`, no flags | EX99_PRESS_RELEASE |
| prior same-form | `0000320193-23-000106`, 2023-11-03 | `0000320193-24-000120`, 2024-10-31 |
| diff | 26 NEW / 24 REMOVED / 47 UNCHANGED, 0 new red-flag categories | 3 NEW / 5 REMOVED / 3 UNCHANGED, 0 new |
| train-overlap banner | **fires** — 0/73 homed in a training filing, 5/73 inherited-attribution, 0/73 text-identical | silent (0/6 on every channel) |
| other issuers named on the page | **none** | **none** |
| fundamentals as-of | all five families resolved from the 10-K filed that same day | all five resolved from the prior 10-K |

`data/app/reports/320193/index.html` lists all 91 labeled Apple filings, 0
skipped, no train-overlap banner (Apple is not a training CIK).

---

## 11. Open questions for the owner

Three of the first draft's ten are CLOSED in code and are recorded here as
closed, not dropped: **§7.1** (NEGATIVE recall — now this labeler's 0.529,
see §2 and §11.1 below), **§7.5** (reading `backtest_report.md` — now
constants plus a runtime guard, §3), **§7.6** (transitive `controls` import —
kept, bounded by three tests, §3). The rest stand, renumbered.

**11.1 — The header now departs from the ruled 0.487.** The ruling's Q4 block
says "NEGATIVE recall 0.487"; the header renders **0.529 (64/121)**, this
labeler's own number, because 0.487 belongs to the v1.1 student. Confirm the
correction, or say the ruled figure must be restored — in which case it will
render with the words "superseded v1.1 student, different split and rubric"
beside it, never bare.

**11.2 — Two one-word passages from other issuers' chunks still render.**
`®` (Celgene's chunk) and `Legal and Other Contingencies` (Stryker's) are
genuinely in Apple's MD&A and pass containment; they render as
one-paragraph partials with no company named and with
"appears in 481 / 56 filings in the corpus" beside them. Keep as built, or
suppress a partial whose only surviving paragraph is a section heading? The
second is a threshold and the project refuses thresholds, which is why the
default is to keep them.

**11.3 — How should an imputed NONE be presented?** 51.18% of all
guidance-applicable rows corpus-wide are `guidance_imputed_none = true`. Each
currently shows "NONE (no guidance key emitted)" plus the **first sentence** of
G2 §0, with the full §0 paragraph in the header. Options: (a) keep as built;
(b) one note per section; (c) a short marker per passage with the sentence
only in the header.

**11.4 — What should the index page show?** Form, filing date, accession
(linked), sections present, passage counts — deliberately no label-derived
column and no sort by any quantity. Default is to leave it as built.

**11.5 — Ticker resolution reads `data/f2/price_ticker_map.csv`.** E2 carries
no ticker anywhere by design. The module reads four identity columns
(`cik`, `name`, `stratum`, `chosen_ticker`) and the file contains no market
data. Acceptable, or should `--ticker` be dropped until a ticker map with a
neutral name is committed?

**11.6 — Reading order of deduplicated paragraphs.** Containment now gives
each rendered paragraph a byte offset inside the filing's section text, so the
document order that was "not recoverable from the corpus" **is** recoverable
after all. The renderer still places deduplicated passages after the filing's
own within each section and says so on the page. Re-ordering the section view
by offset would make it read as the document does; it was left out of this
pass as scope. Worth doing?

**11.7 — The 8-K comparison.** "Prior same-form filing" for an 8-K resolves to
the prior *labeled* 8-K, and only earnings 8-Ks (item 2.02) are in the corpus,
so it is effectively "the prior quarter's earnings release".

**11.8 — No label is colour-coded.** The page is monochrome by deliberate
choice (the ruling refuses "action colours").

**11.9 — The diff is at chunk granularity, containment is at paragraph
granularity.** A passage contained in both filings with *different* contained
paragraph sets is classified UNCHANGED, though the text rendered on the two
pages differs. Paragraph-level classification would need labels to attach to
paragraphs, which they do not. Recorded, not fixed.

---

## 12. What is NOT in this deliverable

* No on-demand ingest or labeling of an unlabeled company — that is L2.2.
* No E2 predictive-validity sentence — the disclosure says "E2: not run" and
  the single constant `PREDICTIVE_VALIDITY_TEMPLATE` is what L2.3 replaces
  after F6.
* No score, composite, rank, cross-company table, price, return, alert,
  generated summary, distress label, or portfolio import — each refused, each
  with a test in §7.
