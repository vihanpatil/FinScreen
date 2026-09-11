# L2.4 — the diff exercised, the CBKM extraction failure repaired, the imputed guidance printed

**What this is.** PRODUCT_PLAN §3 P1a follow-up **P1a.3**, and the three things
`data/app/status/L2_2_external_companies.md` §5 left open that belong to the
reading aid rather than to fundamentals:

1. **`--per-form 2`.** Every one of the ten drawn companies now holds the
   latest **two** filings of each form, so the year-over-year diff — L2.2 §4.3
   called it "the part of the reading aid most likely to matter", and it was
   untested outside the research universe — has a prior same-form filing to
   compare against. **27 of the 28 pages that rendered now carry a real diff**;
   the one that does not is a 2025 registrant that has filed one 10-K in its
   life.
2. **The CBKM extraction failure** (L2.2 §3, the one pipeline failure in ten
   companies) is **fixed in the app lane only**. `extract.py` is byte-for-byte
   unchanged and the sealed E2 corpus is untouched; see §3 for the proof and
   for the one thing that is still, correctly, a FAIL.
3. **The guidance-imputation share is now on every page.** L2.2 §3 measured
   55% of guidance-applicable passages carrying a NONE the model never emitted
   and asked for the owner's eye on it. That number is now counted off the very
   labels a page renders and printed in the mandatory disclosure block, with
   the G2 §0 sentence beside it.

Same discipline as L2.2 and §0.5: **real, un-curated companies, every failure
recorded, nothing filtered out.** The draw is the sealed one
(`data/app/status/external_draw.json`, seed 20260911) — it was **not** redrawn
and no company was replaced.

**Cost: $0.** EDGAR only, through the existing rate-limited client; the labeler
is the local v1.2 student on this machine. `cost_usd: 0.0` and
`anthropic_api_calls: 0` in all ten `label_manifest.json` files.

---

## 1. The run

| stage | what ran | wall clock |
|---|---|---|
| ingest | `ingest_one.py --ticker <T> --per-form 2` ×10 | **26.2 s** total wall clock (1.1–7.7 s each), **35** EDGAR requests |
| labeling | `label_filing.py --store …` ×10, strictly one at a time | **34.1 min** (2,045 s; 2,040 s of it generation) for 923 new passages, **1.63–2.37 s/chunk** |
| rendering | latest 10-K, 10-Q and earnings 8-K per company, 30 attempts | **9.1 s** total, 0.29–0.36 s per page |

The stores went from 579 labeled passages to **1,021**. 923 of those 1,021 had
to be generated fresh, not 442: adding the prior filing changes which filing a
shared paragraph is *homed* in, and a chunk's id is the sha1 of its paragraph
ids, so most of the newer filing's chunks are new objects. The journal resumed
the 98 that were genuinely identical and skipped them.

**Quality of the labeling run:** 1,021 of 1,021 rows `parse_ok` and
`schema_valid`, **zero** parse failures and **zero** schema violations across
all ten companies. The repro canary was the cached 10/10 PASS against the G1
eval on every run (same adapter `cadca849…`, same instruction sha).

No two labelers ever ran at once. The sequencing script checks for a live
`label_filing.py` / `label_e2.py` before each company and refuses rather than
share the GPU; it did refuse once, between AETN and STC, on a child process
that had not yet been reaped, and the four remaining companies were run by a
second pass whose guard ignores defunct entries and waits two seconds for a
just-finished child. **That refusal is recorded here rather than edited out.**

---

## 2. The diff, on ten companies nobody chose

Every row is a real render. NEW / REMOVED / UNCHANGED are the page's own set
arithmetic over the two **contained** passage sets (`diff_vs_prior`): a
passage counts as present in a filing only if its text is physically in that
filing's extracted section, so a paragraph the prior filing merely inherited
from the corpus lands in NEW, which is the honest answer.

| # | ticker | form | this filing | prior filing | NEW | REMOVED | UNCHANGED | passages on page | render |
|---|---|---|---|---|---|---|---|---|---|
| 1 | SIRI | 10-K | 2026-02-05 | 2025-01-30 | 36 | 12 | 49 | 85 | 0.4 s |
|  |  | 10-Q | 2026-07-30 | 2026-04-30 | 22 | 14 | 34 | 56 | 0.3 s |
|  |  | 8-K | 2026-07-30 | 2026-04-30 | 13 | 7 | 7 | 20 | 0.3 s |
| 2 | CBKM | 10-K | 2026-09-10 | 2025-09-05 | 15 | 4 | 17 | 32 | 0.3 s |
|  |  | 10-Q | 2026-05-08 | 2026-02-06 | 11 | 3 | 15 | 26 | 0.3 s |
|  |  | 8-K | 2026-07-29 | 2026-04-20 | 5 | 3 | 2 | 7 | 0.3 s |
| 3 | TGLS | 10-K | 2026-03-02 | 2025-02-28 | 23 | 8 | 41 | 64 | 0.3 s |
|  |  | 10-Q | 2026-08-06 | 2026-05-08 | 7 | 4 | 5 | 12 | 0.3 s |
|  |  | 8-K | 2026-08-06 | 2026-05-07 | 10 | 8 | 2 | 12 | 0.3 s |
| 4 | CARG | 10-K | 2026-02-19 | 2025-02-20 | 49 | 25 | 44 | 93 | 0.3 s |
|  |  | 10-Q | 2026-08-06 | 2026-05-07 | 15 | 6 | 27 | 42 | 0.3 s |
|  |  | 8-K | 2026-08-06 | 2026-05-07 | 12 | 5 | 7 | 19 | 0.3 s |
| 5 | RNGE | 10-K | 2026-03-31 | 2025-03-31 | 25 | 13 | 18 | 43 | 0.3 s |
|  |  | 10-Q | 2026-08-12 | 2026-05-15 | 10 | 8 | 5 | 15 | 0.3 s |
|  |  | 8-K | 2026-03-31 | 2024-03-29 | 2 | 6 | 0 | 2 | 0.3 s |
| 6 | AETN | 10-K | 2026-03-31 | 2025-04-15 | 2 | 2 | 0 | 2 | 0.3 s |
|  |  | 10-Q | 2026-08-19 | 2026-05-19 | 4 | 2 | 1 | 5 | 0.3 s |
|  |  | 8-K | — | — | — | — | — | — | **no earnings 8-K exists** |
| 7 | STC | 10-K | 2026-02-27 | 2025-02-28 | 22 | 3 | 29 | 51 | 0.3 s |
|  |  | 10-Q | 2026-08-04 | 2026-05-06 | 14 | 5 | 20 | 34 | 0.3 s |
|  |  | 8-K | 2026-07-22 | 2026-04-22 | 10 | 8 | 0 | 10 | 0.3 s |
| 8 | YSGL | 10-K | 2026-06-25 | **NONE** | 2 | 0 | 0 | 2 | 0.3 s |
|  |  | 10-Q | 2026-08-10 | 2026-02-17 | 1 | 1 | 1 | 2 | 0.3 s |
|  |  | 8-K | — | — | — | — | — | — | **no 8-K ever filed** |
| 9 | REAL | 10-K | 2026-02-26 | 2025-02-21 | 34 | 11 | 52 | 86 | 0.3 s |
|  |  | 10-Q | 2026-08-06 | 2026-05-07 | 25 | 13 | 81 | 106 | 0.4 s |
|  |  | 8-K | 2026-08-06 | 2026-05-07 | 8 | 5 | 3 | 11 | 0.3 s |
| 10 | ODYS | 10-K | 2026-03-19 | 2025-03-26 | 45 | 21 | 44 | 89 | 0.4 s |
|  |  | 10-Q | 2026-08-13 | 2026-05-14 | 15 | 10 | 3 | 18 | 0.3 s |
|  |  | 8-K | 2026-08-13 | 2026-05-14 | 7 | 5 | 2 | 9 | 0.3 s |

**Counted honestly: 28 of 30 renders produced a page.** The two that did not
are AETN and YSGL's earnings 8-K, and neither is a defect — those companies do
not report earnings by 8-K at all (L2.2 §3 established this; nothing changed).
**CBKM's 10-K, the one real failure of the L2.2 run, now renders** — see §3.

**27 of the 28 rendered pages carry a diff against a prior same-form filing;
exactly one does not.** YSGL's 10-K is its first and only 10-K (a 2025
registrant with 13 filings in its entire EDGAR history), so its page still
prints *"No earlier labeled filing of the same form exists for this company"* —
which is the truth, not a gap.

### What the diff looks like when it works

- **A 10-K year-over-year diff is roughly half new text.** Across the nine
  companies with a real 10-K pair: **251 NEW, 99 REMOVED, 294 UNCHANGED** —
  a reader who reads only NEW reads **46.1%** of the page.
- **A 10-Q quarter-over-quarter diff is smaller.** Ten pairs: **124 NEW,
  66 REMOVED, 192 UNCHANGED**, NEW = **39.2%** of the page. TheRealReal's 10-Q
  is 25 NEW against 81 UNCHANGED (its risk factors repeat verbatim);
  Odysight's is 15 NEW against 3 UNCHANGED, because its 10-Q risk factors were
  rewritten.
- **An earnings 8-K diff is nearly all NEW, by construction.** Eight pairs:
  **67 NEW, 47 REMOVED, 23 UNCHANGED**, NEW = **74.4%** of the page; a press
  release shares almost nothing with the prior quarter's, and two of the eight
  (STC 10/8/**0** and RNGE 2/6/**0**) share not one passage with it.
  This is correct behaviour, and it is also the case where the diff tells the
  reader least. Worth the owner's eye: the 8-K diff is honest but close to
  useless, and the 10-K diff is the one that earns its place.
- **Newly-appearing red-flag categories fired on 8 of the 28 pages** — e.g.
  `TRADE_POLICY_EXPOSURE` on CBKM's and STC's 10-K, `DEMAND_WEAKNESS` +
  `IMPAIRMENT_WRITEDOWN` on STC's 8-K. Every one of them renders with the
  `exploratory` tag the G3 demotion requires. **They are disclosure only and
  must not be read as findings.**

---

## 3. CBKM: the filer-dialect failure, fixed in the app lane and nowhere else

### What was broken

L2.2 §3 recorded it exactly: extraction produced **zero words** for MD&A and
Risk Factors on CBKM's 10-K and 10-Q, reason code `no_toc_and_no_heading_match`
on all four attempts, and `report_filing --latest 10-K` exited 1. Re-read in
the raw document, there are three separate facts:

1. **The document contains no `<a href="#…">` at all.** `find_toc_item_anchors`
   returns an empty list, so the anchor-TOC path never had a candidate. (L2.2
   said "the document never emits the literal string *Table of Contents*"; the
   operative fact is the missing internal links, since that is what the
   extractor actually walks.)
2. **Every item label uses an em dash and no period.** The TOC row is
   `Item&#160;7&#8212;Management&#8217;s Discussion and Analysis…`.
   `extract._heading_pattern` allows only `[\s\xa0.:]{0,20}` between "Item 7"
   and the title keyword — an em dash stops the match dead.
3. **The body heading bolds each token separately:**
   `<b>Item</b>&#160;<b>7</b>&#8212;<b>Management</b>&#8217;<b>s Discussion…</b>`.
   `extract.html_fragment_to_text` joins tags with `"\n"`, so the extractor
   sees `Item\n7\n—\nManagement\n’\ns Discussion`, and `management.?s\s+discussion`
   cannot match that either.

### The fix, and why it cannot move the research corpus

`extract.py` is **not edited**. Its sha256 is unchanged
(`a5a519b1…`), `git status` shows it clean, and
`data/filings_e2_v2.parquet` has not been rewritten (mtime 2026-08-27, the
seal). The fix lives entirely in `ingest_one.py`, in the one place the app lane
already controls: **the `read` callable `extract.extract_filing` takes as its
first argument.**

`ingest_one.normalize_filer_dialect()` does two things to the HTML and nothing
else:

- drops **inline formatting tags** (`b`, `strong`, `i`, `em`, `u`, `span`,
  `font`, `sup`, `sub`, `small`, `ins`, `mark`) — elements a browser does not
  break a line on, so joining their text is what a human reader already sees;
- rewrites an **em/en dash used as an item separator** — anchored on the word
  "Item" and a 1–2 digit item number — into the `Item 7.` spelling the
  extractor's own patterns were calibrated on. An em dash anywhere else in the
  filing's prose is left alone; escaped markup (`&lt;b&gt;`) is left alone,
  because `html.unescape` is deliberately not used.

And it is applied under one rule: **`retry_failed_on_normalized_html` re-runs
only the attempts the frozen extractor already FAILED**, with a reason code in
a named set of locator failures (`no_toc_and_no_heading_match`,
`anchor_span_below_min_chars`, `empty_after_extraction`,
`toc_recovery_declined`, `item_absent_from_toc`). A cache miss or an unreadable
document is not a dialect problem and is never retried. A located row — even a
FLAGGED, below-floor one — is never touched. A retry that fails too leaves the
frozen extractor's own FAIL row standing, so **no failure is hidden**.

Measured consequence: **the retry fired on CBKM and on no other company.**
`dialect_retry.rescued` is empty in nine of the ten manifests, and the other
nine companies' extraction rows are the same rows the frozen extractor wrote.
Every rescued row carries `DIALECT_NOTE` in its audit note and is listed in
`manifest.json → dialect_retry.rescued`.

### Does the app-lane fix change any research-corpus extraction? No.

It cannot, on two counts. `extract.run()` — the only path that writes the
research corpus — passes `extract.read_cached_document` directly and never
sees `normalizing_reader`; and the retry can only fire where the shipped read
produced a FAIL, i.e. where the corpus has **no row at all**. Nothing in
`data/filings_e2_v2.parquet` is modified by this change, and nothing was
re-extracted.

**For the owner, stated and not acted on:** the research corpus's own audit
(`data/f3/extraction_audit.parquet`, 30,475 attempts) holds **397**
`no_toc_and_no_heading_match` FAILs, plus 376 FAIL `item_absent_from_toc`, 12
`empty_after_extraction` and 11 `anchor_span_below_min_chars` — **796 FAIL
attempts** the same normalization *could* be pointed at if F3 were ever re-run.
That would move the sealed corpus and therefore every F4 label, the G1 eval and
the G2 spot-check. **It is not done here and needs an owner ruling, not a
commit.**

### CBKM after the fix — words per section, with the extractor's own confidence

| filing | filed | section | words | method | confidence | status | flags |
|---|---|---|---|---|---|---|---|
| 10-K `…26-030039` | 2026-09-10 | MDA | **8,157** | heading_regex | low | FLAGGED | `heading_regex_fallback` |
| 10-K `…26-030039` | 2026-09-10 | RISK_FACTORS | **10** | heading_regex | low | FLAGGED | `heading_regex_fallback`, `below_length_floor` |
| 10-K `…25-028445` | 2025-09-05 | MDA | **8,381** | heading_regex | low | FLAGGED | `heading_regex_fallback` |
| 10-K `…25-028445` | 2025-09-05 | RISK_FACTORS | **10** | heading_regex | low | FLAGGED | `heading_regex_fallback`, `below_length_floor` |
| 10-Q `…26-015787` | 2026-05-08 | MDA | **5,869** | heading_regex | low | FLAGGED | `heading_regex_fallback` |
| 10-Q `…26-003344` | 2026-02-06 | MDA | **5,844** | heading_regex | low | FLAGGED | `heading_regex_fallback` |
| 10-Q ×2 | — | RISK_FACTORS | **0** | none | low | **FAIL** | `no_toc_and_no_heading_match` |
| 8-K ×2 | — | EX99_PRESS_RELEASE | 2,403 / 2,383 | whole_document | high | OK | — |

Before this change the first six rows were all **0 words / FAIL**. All six are
`confidence: low` and `FLAGGED`, which is correct and is what the page prints:
`heading_regex` is the extractor's fallback locator and it never claims `high`.

Spot-read of the two rescued MD&As: both open on their own heading
(*"Item 7. Management's Discussion and Analysis … (Dollars in thousands …)
General The following is management's analysis …"*) and both end exactly where
Item 7A begins (*"… commitments to extend credit to borrowers under lines of
credit."*). The span is the real Item 7, not a mis-anchored slice.

The **10-word Risk Factors** rows are the truth, not a defect: CBKM's Item 1A
reads in full *"Not applicable for Smaller Reporting Companies."* They are
flagged `below_length_floor` and are too short to become a chunk, so CBKM's
store carries MD&A and press-release passages only.

**The one attempt that is still a FAIL, and why it should stay one.** CBKM's
10-Q Item 1A row reads *"Item 1A. Not Applicable for Smaller Reporting
Companies"* — the words "Risk Factors" **never appear in the 10-Q at all**.
`_heading_pattern("1A", r"risk\s+factors")` therefore cannot match, and it
should not: matching a bare "Item 1A." with no title keyword is exactly the
false-positive the extractor's guards exist to prevent. Recorded as a FAIL,
left as a FAIL.

---

## 4. The imputed-guidance share is now on the page

Every report — store and research corpus, filing page and index page — now
carries this line in the mandatory, non-collapsible disclosure block:

> **Imputed guidance.** *N* of *M* guidance-applicable passages carry an
> imputed NONE (the model emitted no guidance key) — *p*% of the
> guidance-applicable passages in *this company's store* (*K* labeled
> passages). The owner-ruled missing→NONE rule (F4, `label_e2.f4_label_row`)
> wrote those values and flagged every one of them `guidance_imputed_none`;
> the model did not emit them, and each is marked where it renders.
>
> > *Do not interpret the 68.67% active-guidance precision as evidence that the
> > model usually hallucinates the existence of guidance.* — G2 §0, parsed from
> > `G2_FINAL_REPORT.md` at render time

The numbers are **counted from the labels the page renders** —
`report_filing.guidance_imputation()` reads the store's `labels.parquet` under
`--store` and the F4 corpus otherwise. They are never a module constant; a
test asserts the sentence carries format placeholders and no literal pair of
numbers, so a corpus change cannot leave a stale figure on a page.

| # | ticker | labeled passages | guidance-applicable | imputed NONE | share |
|---|---|---|---|---|---|
| 1 | SIRI | 163 | 27 | 20 | **74.1%** |
| 2 | CBKM | 71 | 10 | 6 | 60.0% |
| 3 | TGLS | 106 | 20 | 13 | 65.0% |
| 4 | CARG | 173 | 24 | 9 | 37.5% |
| 5 | RNGE | 84 | 8 | 2 | 25.0% |
| 6 | AETN | 11 | **0** | 0 | n/a |
| 7 | STC | 98 | 18 | 8 | 44.4% |
| 8 | YSGL | 5 | **0** | 0 | n/a |
| 9 | REAL | 165 | 16 | 7 | 43.8% |
| 10 | ODYS | 145 | 14 | 7 | 50.0% |
| | **all ten** | **1,021** | **137** | **72** | **52.6%** |

L2.2 §3 measured 41 of 74 (55.4%) on the per-form-1 stores; on twice the
filings it is **72 of 137 (52.6%)**. **The finding holds: more than half of
every "NONE" a reader sees on an external company is the writer's default, not
the model's judgment.** The research corpus is the same story at
**48,790 of 95,335 (51.2%)**, and that is the figure the AAPL pages now print.

**AETN and YSGL print `0 of 0` and say why.** Neither files an earnings 8-K, so
no passage is guidance-applicable at all, and the line adds the sentence:
*"No passage here is guidance-applicable at all — guidance is asked only on the
earnings press release — so the guidance field is empty by construction, not
because the model saw no guidance."* A bare `0 of 0` would read like a clean
bill of health; it is not one.

---

## 5. What this run proves, and what it does not

**Proved.**

- The year-over-year diff works on companies nobody chose. 28 renders, 27 with
  a real prior same-form filing, every count deterministic set arithmetic over
  contained text.
- The one extraction failure the L2.2 draw found is repairable **without**
  touching the frozen extractor, and the repair is provably inert on the other
  nine companies (`dialect_retry.rescued` empty in nine of ten manifests).
- 1,021 of 1,021 labels parsed and validated; $0 and 0 API calls.
- Every page carries the outside-universe line exactly once, and now the
  imputed-guidance line as well.

**Not proved, said plainly.**

1. **Still no spot-check.** Nothing here has been checked by a human or a
   second model. The G2 model-consensus error is the *best* case and it was
   measured on the 244-company universe, which contains no community bank, no
   shell and no 2025 registrant. The disclosure line on every page says so.
2. **The diff measures TEXT, not meaning.** NEW means "these words are not in
   the prior filing", including a sentence that was merely re-worded. The page
   says this; the counts above should be read as an index into the filing, not
   as a measure of how much changed.
3. **The 8-K diff is close to useless.** Nearly all NEW by construction (three
   companies show 0 UNCHANGED). It is honest and it is not informative.
4. **`heading_regex` is a `low`-confidence locator.** CBKM's six rescued
   sections are all FLAGGED and all `low`. A reader of CBKM's page is reading
   text the extractor is least sure about — which the page states in the
   sections table, per section.
5. **The rescue is app-lane only.** The 796 comparable FAIL attempts in the
   research corpus are **untouched** and stay untouched without an owner ruling.
6. **Fundamentals are out of scope here** and are being done separately
   (P1a.2). This document makes no claim about them.

---

## 6. How to reproduce any row

```bash
python3 ingest_one.py  --ticker CBKM --per-form 2        # EDGAR -> store
python3 label_filing.py --store data/app/companies/1006830   # v1.2 student
python3 report_filing.py --store data/app/companies/1006830 --latest 10-K
python3 report_filing.py --store data/app/companies/1006830 --latest 10-Q
python3 report_filing.py --store data/app/companies/1006830 --latest 8-K
```

Check `pgrep -fl "label_filing|label_e2"` before every labeling run and never
start a second one; `label_filing.py` also refuses on its own if an F4 campaign
process is alive.

**The draw must not be redrawn.** `data/app/status/external_draw.json` is the
sealed one from L2.2.

**If `ingest_one.py` is re-run for these companies for any reason, pass
`--per-form 2` again** — the flag's default is still 1, and a re-ingest
without it would drop the prior filings this document measures and invalidate
every diff count above. (`--fundamentals` on a store that already has a
`manifest.json` does **not** re-ingest — it only adds step 7 — so the P1a.2
pass is safe to run over these ten as they stand.)

Provenance per store: `manifest.json` (EDGAR requests, per-section extraction
audit, `dialect_retry`, shas), `generation.json` (adapter sha, canary,
per-chunk timing), `label_manifest.json` (`cost_usd: 0.0`,
`anthropic_api_calls: 0`).

**Tests:** `python3 -m pytest -q test_report_filing.py test_app_store.py`.
The new ones, all synthetic-fixture (§0.5 permits synthetic data for unit tests
and nowhere else):

- `test_the_dialect_normalizer_repairs_the_two_things_it_names` — the CBKM
  markup shapes, asserted against `extract._heading_pattern` itself;
- `test_the_normalizer_leaves_prose_and_escaped_markup_alone`;
- `test_a_section_the_frozen_extractor_located_is_never_retried`,
  `test_a_cache_miss_is_not_a_dialect_problem_and_is_not_retried`,
  `test_a_retry_that_fails_too_leaves_the_original_failure_standing`,
  `test_a_rescued_section_says_so_in_its_audit_note`;
- `test_the_app_lane_never_writes_into_the_frozen_extractor` — an AST scan
  proving `ingest_one` never assigns into the `extract` module;
- `test_the_imputation_share_is_counted_off_the_rendered_labels`,
  `test_an_imputed_flag_outside_the_applicable_set_is_not_counted`,
  `test_the_disclosure_block_prints_the_guidance_imputation_share`,
  `test_the_imputation_line_says_when_nothing_is_guidance_applicable`,
  `test_the_imputation_share_is_never_a_module_constant`,
  `test_the_store_report_prints_ITS_OWN_guidance_imputation_share`.

---

## 7. Still open after this run

- **The 796 research-corpus FAIL attempts** the same normalization could
  address. Needs an owner ruling; re-running F3 moves the sealed corpus.
- **`report_filing`'s refusal message** still says *"has no labeled 10-K in the
  corpus"* when it is reading a store; *"in this store"* is the accurate
  wording (L2.2 §5, not done here).
- **No label spot-check for external companies.** PRODUCT_PLAN §0.5 item 3
  requires one before any new universe's labels count. The imputed-guidance
  share printed on every page is a disclosure, not a substitute for it.
- **The 8-K diff earns little.** Consider whether a page should print it at
  all, or print it collapsed with a sentence saying why it is almost always
  100% NEW. An owner call, not a code change to make unasked.
