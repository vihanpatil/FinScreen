# L2.2 — any-ticker on demand, proven on un-curated companies

**What this is.** PRODUCT_PLAN §3 P1a's acceptance test, and the first concrete
application of the real-data-first rule (§0.5): ten companies **outside** the
244-company research universe, chosen by a seeded random draw from the SEC
ticker list before any of them was attempted, each taken end to end —
`ingest_one.py` → `label_filing.py` → `report_filing.py --store` — with every
failure recorded and none removed.

**The draw is sealed.** `data/app/status/external_draw.json`, seed 20260911,
drawn 2026-09-11T09:49:39Z, over 10,062 candidates (10,407 tickers in
`company_tickers.json` minus the 244 research-universe CIKs, minus anything
with no 10-K in the last 730 days — which is what removes funds, trusts and
foreign private issuers). 20 candidates were examined to fill 10 slots; the ten
rejections and their reasons are in that file. **No company here was replaced,
and no failure below was filtered out.** Rows are appended as each company
finishes, so an interrupted run resumes without losing what it measured.

**Cost.** $0. EDGAR only, through the existing rate-limited client; labeling is
the local MLX student on this machine. `cost_usd: 0.0` and
`anthropic_api_calls: 0` are recorded in every store's `label_manifest.json`.

**What a "yes" in the render columns means.** A static HTML report was written
for that filing, carrying the mandatory disclosure header plus the one extra
line this path adds: *"This company is outside the 244-company research
universe; its labels have no spot-check and carry the same model-consensus
error at best."* It does not mean the labels are right — nothing here has been
spot-checked, and the G2 model-consensus error applies at best.

---

## 1. Pilot (not part of the draw)

CROX was ingested and labeled first, before the draw was used, to prove the
three stages joined up at all. It is recorded here for completeness and is
**not** one of the ten; it replaces nobody.

| ticker | CIK | name | forms found | sections extracted (confidence) | chunks | ingest | labeling | 10-K | 8-K |
|---|---|---|---|---|---|---|---|---|---|
| CROX | 1334036 | Crocs, Inc. | 10-Q 2026-07-30; 8-K 2026-07-30; 10-K 2026-02-12 | MDA·high; RISK_FACTORS·high; EX99_PRESS_RELEASE·high; MDA·high; RISK_FACTORS·high | 98 | 1.6 s | 290 s (2.96 s/chunk) | yes | yes |

The repro canary against the G1 eval was run once, here, before the first real
label: 10 of 10 rows byte-identical to
`finetune/runs/2026-08-28-v12-eval-epoch2/predictions.jsonl`
(sha256 `e32dc481…`), adapter `cadca849…`, instruction sha
`ebc45a85…`. Every company below reuses that cached PASS — it covers exactly
these artifacts, and re-running it would not test anything new.

---

## 2. The ten drawn companies

Timings are wall clock on this machine, one company at a time. "ingest" is
EDGAR metadata + document fetch + extraction + chunking. "labeling" is the
local student over that company's chunks.

| # | ticker | CIK | name | forms found | sections extracted (confidence) | chunks | ingest | labeling | 10-K | 8-K | failures |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | SIRI | 908937 | SIRIUS XM HOLDINGS INC. | 10-Q 2026-07-30; 8-K 2026-07-30; 10-K 2026-02-05 | MDA·high; RISK_FACTORS·high; EX99_PRESS_RELEASE·high; MDA·high; RISK_FACTORS·high | 100 | 1.6 s | 207 s (2.04 s/chunk) | yes | yes | none |
| 2 | CBKM | 1006830 | CONSUMERS BANCORP INC /OH/ | 10-K 2026-09-10; 8-K 2026-07-29; 10-Q 2026-05-08 | MDA·low·FAIL; RISK_FACTORS·low·FAIL; EX99_PRESS_RELEASE·high; MDA·low·FAIL; RISK_FACTORS·low·FAIL | 5 | 6.7 s | 14 s (2.38 s/chunk) | NO | yes | 1 — see §3 |
| 3 | TGLS | 1534675 | Tecnoglass Holdings Inc. | 10-Q 2026-08-06; 8-K 2026-08-06; 10-K 2026-03-02 | MDA·high; RISK_FACTORS·low·ITEM_ABSENT_FROM_TOC; EX99_PRESS_RELEASE·high; MDA·high; RISK_FACTORS·high | 69 | 1.7 s | 161 s (2.30 s/chunk) | yes | yes | none |
| 4 | CARG | 1494259 | CarGurus, Inc. | 10-Q 2026-08-06; 8-K 2026-08-06; 10-K 2026-02-19 | MDA·high; RISK_FACTORS·high; EX99_PRESS_RELEASE·high; MDA·high; RISK_FACTORS·high | 100 | 2.3 s | 221 s (2.19 s/chunk) | yes | yes | none |
| 5 | RNGE | 1438943 | RANGE IMPACT, INC. | 10-Q 2026-08-12; 8-K 2026-03-31; 10-K 2026-03-31 | MDA·high; RISK_FACTORS·high; EX99_PRESS_RELEASE·high; MDA·high; RISK_FACTORS·high | 45 | 1.6 s | 87 s (1.89 s/chunk) | yes | yes | none |
| 6 | AETN | 764630 | AETERNUM HEALTH, INC. | 10-Q 2026-08-19; 10-K 2026-03-31 | MDA·high; RISK_FACTORS·high; MDA·low·FLAGGED; RISK_FACTORS·medium·FLAGGED | 7 | 1.1 s | 14 s (1.71 s/chunk) | yes | NO | 1 — see §3 |
| 7 | STC | 94344 | STEWART INFORMATION SERVICES CORP | 10-Q 2026-08-04; 8-K 2026-07-22; 10-K 2026-02-27 | MDA·high; RISK_FACTORS·high; EX99_PRESS_RELEASE·high; MDA·high; RISK_FACTORS·high | 59 | 11.7 s | 131 s (2.19 s/chunk) | yes | yes | none |
| 8 | YSGL | 2071489 | Yellowstone Group Ltd. | 10-Q 2026-08-10; 10-K 2026-06-25 | MDA·medium·FLAGGED; RISK_FACTORS·low·ITEM_ABSENT_FROM_TOC; MDA·low·FLAGGED; RISK_FACTORS·medium·FLAGGED | 4 | 1.0 s | 9 s (1.78 s/chunk) | yes | NO | 1 — see §3 |
| 9 | REAL | 1573221 | TheRealReal, Inc. | 10-Q 2026-08-06; 8-K 2026-08-06; 10-K 2026-02-26 | MDA·high; RISK_FACTORS·high; EX99_PRESS_RELEASE·high; MDA·high; RISK_FACTORS·high | 105 | 1.8 s | 218 s (2.06 s/chunk) | yes | yes | none |
| 10 | ODYS | 1577445 | Odysight.ai Inc. | 8-K 2026-08-13; 10-Q 2026-08-13; 10-K 2026-03-19 | EX99_PRESS_RELEASE·high; MDA·high; RISK_FACTORS·high; MDA·high; RISK_FACTORS·high | 85 | 1.4 s | 177 s (2.05 s/chunk) | yes | yes | none |

**Totals over the ten.** 579 chunks; 579 labels; 36 EDGAR requests; $0.00 and
0 Anthropic API calls (the labeler is local). Wall clock end to end, one
company at a time: **21.6 minutes**, mean 129 s per company — 30.9 s of it
ingestion, 1,238.9 s labeling, 24.0 s rendering. Per-company end-to-end
(ingest + labeling + both renders), in seconds:

| # | ticker | ingest | labeling | render 10-K | render 8-K | end to end |
|---|---|---|---|---|---|---|
| 1 | SIRI | 1.6 | 206.6 | 1.3 | 1.2 | 210.7 |
| 2 | CBKM | 6.7 | 14.0 | 1.0 (failed) | 1.2 | 22.9 |
| 3 | TGLS | 1.7 | 160.8 | 1.3 | 1.2 | 165.0 |
| 4 | CARG | 2.3 | 220.7 | 1.3 | 1.2 | 225.5 |
| 5 | RNGE | 1.6 | 87.3 | 1.3 | 1.2 | 91.4 |
| 6 | AETN | 1.1 | 14.1 | 1.3 | 0.9 (failed) | 17.4 |
| 7 | STC | 11.7 | 131.0 | 1.3 | 1.2 | 145.2 |
| 8 | YSGL | 1.0 | 9.3 | 1.2 | 0.9 (failed) | 12.4 |
| 9 | REAL | 1.8 | 218.5 | 1.3 | 1.2 | 222.8 |
| 10 | ODYS | 1.4 | 176.6 | 1.3 | 1.2 | 180.5 |

Labeling dominates and scales with chunk count at **1.7–2.4 s per chunk** on
this machine; a large filer (SIRI, CARG, REAL: ~100 chunks) is ~3.5 minutes.
A viewer-named ticker is therefore a **2–4 minute wait** for a big company and
under a minute for a small one — the live demo of §P-S is feasible as it
stands, but not instant.

---

## 3. Every failure, with its cause

Twenty renders were attempted — the latest 10-K and the latest earnings 8-K
for each of the ten. **Seventeen produced a page; three did not.** None was
worked around, and no company was replaced.

**2. CBKM (CIK 1006830) — Consumers Bancorp Inc /OH/ — 10-K did not render.**
`report_filing --latest 10-K` exited 1 with *"CIK 1006830 has no labeled 10-K
in the corpus"*, and it was right: extraction produced **zero words** for
MD&A and Risk Factors on both the 10-K (2026-09-10) and the 10-Q (2026-05-08),
with reason code `no_toc_and_no_heading_match` on all four. The only readable
text in this company's store is the earnings press release attached to its
8-K, which did render. The cause is a **filer-dialect gap in `extract.py`**,
visible in the raw document:
- the table of contents writes items with an em dash and no separating period
  — `Item 7—Management's Discussion and Analysis…` — and the document never
  emits the literal string "Table of Contents", so the TOC path finds nothing;
- the body heading is rendered as `Item 7 — Management ’ s Discussion and
  Analysis…`, with the curly apostrophe split into its own token by the filing
  agent's markup, so the heading-anchor path does not match either;
- and Item 1A itself reads *"Not applicable for Smaller Reporting Companies"*,
  so even a perfect extraction would return a stub there.

This is the F3 filer-dialect failure class, reproduced on the first un-curated
community bank the draw handed us. **It was not fixed**: `extract.py` is the
frozen research extractor and changing it would move the sealed E2 corpus.
Recorded as follow-up work, not repaired here.

**6. AETN (CIK 764630) — Aeternum Health, Inc. — earnings 8-K did not render.**
`report_filing --latest 8-K` exited 1. There is nothing to render: the company
filed five 8-Ks in the 1,100-day window and **none of them carries Item 2.02**
(they are items 1.01, 2.01, 3.02, 5.01, 5.02, 5.03, 7.01, 9.01). `ingest_one`
deliberately never takes a non-earnings 8-K, so the store holds only the 10-K
and 10-Q, both of which extracted and both of which rendered. This is correct
behaviour meeting a company that does not report earnings by 8-K; it is
recorded as a failure of the acceptance test's own "render the latest earnings
8-K" step, not as a defect.

**8. YSGL (CIK 2071489) — Yellowstone Group Ltd. — earnings 8-K did not
render.** Same cause, stronger form: this company has filed **no 8-K at all,
ever** — 13 filings in its entire EDGAR history, a 2025 registrant. Its 10-K
and 10-Q both rendered.

### Near-misses that did not fail but are worth seeing

- **AETN and YSGL 10-K MD&A** extracted as `FLAGGED` /
  `mda_stub_unresolved_same_doc` + `below_length_floor` — 517 and 775 words.
  These are shell-scale filings; the page renders, but there is very little
  text on it (7 and 4 chunks for the whole company). A report with four
  passages is honest, and thin.
- **TGLS and YSGL Risk Factors** came back `ITEM_ABSENT_FROM_TOC` on the 10-Q,
  which is the normal case (a 10-Q usually says risk factors are unchanged).
- **Guidance is only ever asked on the earnings press release.** 74 of the 579
  chunks are `guidance_applicable`; all 74 are `EX99_PRESS_RELEASE`. A company
  with no earnings 8-K (AETN, YSGL) therefore gets **no guidance labels at
  all** — for those two companies the guidance field is empty by construction,
  not because the model saw no guidance.
- **Most of the guidance field is an imputation, not a judgment.** On
  **41 of those 74** guidance-applicable passages (55%) the student's JSON
  omitted the `guidance_direction` key entirely and the owner-ruled
  missing→NONE rule wrote `NONE` with `guidance_imputed_none = True`. The
  remaining 33 are the model's own: 29 NONE and 4 RAISED. A reader who sees
  "NONE" on an external company is, more often than not, seeing the writer's
  default. The flag is in the table and the rule is F4's, unchanged — but the
  rate is worth the owner's eye.
- **A handful of labels land outside their section's scope**, preserved
  exactly as emitted (the writer rewrites only the omitted-guidance-key case):
  5 of 251 Risk Factors passages carry a sentiment (4 NEUTRAL, 1 NEGATIVE)
  where the student normally returns none, and 1 of 254 MD&A passages carries
  a `guidance_direction`.

---

## 4. What the run proves, and what it does not

**Proved.** The three stages join up on companies nobody chose: a ticker goes
in, EDGAR metadata and documents come down through the existing rate-limited
client, sections are extracted with the research extractor and its own audit
columns, chunks are built on the F4 schema, the v1.2 local student labels them,
and `report_filing --store` renders a page with every refusal and disclosure
the research path carries plus the outside-universe line. **19 store reports
were written — 17 for the ten drawn companies plus the pilot's 2 — and all 19
carry that line exactly once**; the three research-corpus reports on disk
(AAPL, from L2.1) carry it zero times, which is the intended split. All 579 labels parsed (`parse_ok` and `schema_valid` true on every
row, zero `schema_issues`), and the repro canary's cached PASS covered every
run — the adapter, instruction sha and prompt renderer were the ones gate G1
was ruled on.

**Not proved, and stated plainly.**

1. **No spot-check.** Nothing on these pages has been checked by a human or
   by a second model. The G2 model-consensus error is the *best* case here,
   and G2 itself was measured on the 244-company universe; these ten companies
   include a community bank, two shells and a 2025 registrant, none of which
   resemble that universe. The disclosure line on every page says so.
2. **Fundamentals are blank for every external company.** The point-in-time
   panel reads F2's committed per-company concept resolution, which only
   covers the 244 research CIKs, so all five families print
   `UNRESOLVED for this company in F2's concept resolution` on all ten pages.
   That is honest but it means an external report is text-only today.
   (Fixing it means running the concept resolver per company at ingest time —
   real work, not a flag.)
3. **One filing per form.** These runs used `--per-form 1`, so no company has
   a prior filing of the same form in its store and every page prints *"No
   earlier labeled filing of the same form exists for this company"* in the
   "what changed" section. The year-over-year diff — the part of the reading
   aid most likely to matter — is **untested on external companies**.
   `--per-form 2` would test it at roughly double the labeling time.
   *(Done 2026-09-11 — see `L2_4_diff_and_extraction.md`. The ten stores on
   disk now hold two filings per form and 1,021 labeled passages; the
   per-company chunk and label counts in §1–2 above describe the per-form-1
   run they superseded, and are left as measured.)*
4. **Success rate, counted honestly:** 10 of 10 companies ingested and
   labeled; **9 of 10 rendered a 10-K** (CBKM's extraction produced nothing to
   render); **8 of 10 rendered an earnings 8-K**, and for two of those the
   company has no such filing to render. Counting only what the pipeline
   controls: **one extraction failure in ten companies (10%)**, on the
   smallest and most idiosyncratic filer in the draw.

## 5. Follow-up work this run identified

- `extract.py` filer dialect: em-dash item separators, no "Table of Contents"
  string, and markup-split possessive apostrophes defeat both the TOC and the
  heading-anchor paths (CBKM). Any fix must be made without disturbing the
  sealed E2 corpus — a store-side override, or a re-extraction that is scoped
  to `data/app/` only. *(Done 2026-09-11, app-lane only, `extract.py`
  untouched — `L2_4_diff_and_extraction.md` §3.)*
- Per-company XBRL concept resolution at ingest time, so the fundamentals
  panel is not blank outside the research universe.
- `--per-form 2` on at least one external company, to exercise the diff.
  *(Done 2026-09-11 on all ten — `L2_4_diff_and_extraction.md` §2.)*
- `report_filing`'s refusal message says "in the corpus" when reading a store;
  "in this store" would be the accurate wording.

---

## 6. How to reproduce any row

```bash
python3 ingest_one.py  --ticker TGLS                       # EDGAR -> store
python3 label_filing.py --store data/app/companies/1534675 # v1.2 student
python3 report_filing.py --store data/app/companies/1534675 --latest 10-K
python3 report_filing.py --store data/app/companies/1534675 --latest 8-K
```

The draw itself is `python3 ingest_one.py --draw 10 --seed 20260911`; it is
already written to `data/app/status/external_draw.json` and **must not be
redrawn**. Each store keeps its own provenance: `manifest.json` (EDGAR
requests, per-section extraction audit, shas), `generation.json` (adapter sha,
canary, per-chunk timing) and `label_manifest.json` (`cost_usd: 0.0`,
`anthropic_api_calls: 0`). Rows above were appended one company at a time, so
a re-run skips any ticker already in the table.

**Plumbing tests:** `python3 -m pytest -q test_report_filing.py
test_app_store.py` — 155 passed. `test_app_store.py` is synthetic-fixture only
(the real-data-first rule allows synthetic data for unit tests and nowhere
else); every number in this file came from the ten real companies.
