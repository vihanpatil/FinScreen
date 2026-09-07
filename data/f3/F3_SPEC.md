# F3_SPEC — extraction at scale (E2 phase F3)

**Written 2026-08-26 by extraction-qa-engineer (Opus) as stage P0 of
`F3_PROGRESS.md`.** Spec only: no pipeline code was edited, no test was
edited, `F3_PROGRESS.md` was not edited. **Zero live GETs** — every number
below was measured offline against `data/raw/documents/` and the read-only
`data/filings_metadata_e2.db` (`mode=ro`).

Reading order behind this document: `F3_PROGRESS.md` → `HANDOFF.md` §3
(2026-08-26 entry), §4, §7 → `EXPANSION_PLAN.md` §4 F3, §5 F3, §8 →
`data/hardening/status/H4_docsample.md` (incl. its 155-row ledger) →
`extract.py` → `data/F2_INGESTION_REPORT.md` §5.

The measurement harness that produced every number here is archived at
`data/f3/p0_measure/` (scripts + three small parquet evidence files). It is
a harness, not pipeline code — same discipline as `data/hardening/h4_*.py`.

---

## 0. Headline rulings, with the evidence line for each

| # | Ruling | Evidence |
|---|---|---|
| **R1** | **The population gate ships as the BROAD condition** (`multi-filing (CIK, quarter) cell` → WARN). The text signature is carried as a **severity/ordering field, never as a suppressor.** | The narrowed variant H4 proposed was **re-measured on H4's own 155-row ledger: recall 8/9, not 9/9** (§4.2). It drops the ICE third-party-results row — the loudest error in the sample. |
| **R2** | **`8K_BODY` slices from the first `Item 2.02` to END OF DOCUMENT**, never to the next item heading. | Census of **all 210** `8K_BODY` selections: ending at the next item heading leaves **<200 words in 45 of 210 (21%)** — Humana 8 words, BAC 12, Emerson 30 (§5). |
| **R3** | **Floors and ceilings are FLAGS, never filters.** No row is ever dropped by a word-count floor; but a flagged row may never carry `extraction_confidence='high'`. | Four pilot rows of 43/50/55/102 words came out `anchor`/**high** today — plausible-looking garbage at the highest confidence label (§3 C7, §8). |
| **R4** | **The 10-K MD&A stub resolver is triggered by WORD COUNT alone.** The reference-language regex is demoted from gate to evidence field. | `STUB_REFERENCE_LANGUAGE_RE` matched **0 of 4** real stubs found in a 144-filing pilot (Sempra, US Bancorp, JPMorgan-2017, plus a wrong-slice) (§3 C7). |
| **R5** | **F3 reads the cache directly and never constructs `EdgarClient`.** A cache miss is a loud FAIL row, never a fetch. | All **20,521/20,521** target documents verified present in `data/raw/documents/`; 0 missing (§1.3). |
| **R6** | **Output is CIK-keyed.** `filings.ticker` is NULL for **all 45,545 rows** of the E2 DB; `companies.ticker` is NULL for all 244. | Direct query (§3 C3). E1's `run()` writes a `ticker` column that would be entirely NULL at E2 scale. |
| **R7** | **Parse each primary document once**, reuse the soup + TOC for both sections. | Measured: whole-document `BeautifulSoup` parse is **1.05 s of a 1.42 s filing**; the current code pays it twice (§10). |
| **R8** | **Per-filer / per-dialect edge handlers live in one small named registry** with fired-counts and DEAD detection, exactly like F2's `earnings_doc_overrides.csv`. | F2 §5's arc; five new dialects already named in C15. |
| **R9** | **Every attempt produces an audit row** — OK, FLAGGED, EXPECTED_ABSENT or FAIL with a reason code. Failures are never a print statement. | E1's `run()` prints failures to stdout and drops them; at 30,475 attempts that is unauditable (§7). |
| **R10** | **F3 hands F4 a MEASURED chunk count**, re-derived by running `chunk.py`'s own pure functions over F3's real output under three window rules. | The plan's "~23k sections" is itself low: **30,475 attempts**, ~28–29k expected sections (§2.2, §12). |

Nothing in this spec needs an owner decision. Two items are *main-session*
decisions and are named in §13.

---

## 1. Inputs, and what is already verified

### 1.1 Binding measured inputs (from F2 / F2.5 — the source docs win)

Carried verbatim from `F3_PROGRESS.md` §"Binding F3 inputs" and honoured
as follows:

| Input | Where it is honoured |
|---|---|
| Population gate (H4, recall 9/9 broad; narrowed variant must be re-measured) | §4 — re-measured, **8/9**, broad variant ships |
| `8K_BODY` item-2.02 slicing (median 1,975 chars of cover page) | §5 — re-measured over all 210 |
| Length is a bad discriminator; recalibrate floors, never as an error-catch substitute | §8 |
| Combined release+supplemental dilution (Simon Property ~74% tables) | §6 |
| Pre-2019 dialects; per-filer triage; 30–50-section spot read with a stopping rule written first; small named handlers | §9, C15 |
| 0 GETs; F4-scale re-derivation is a required F3 deliverable | §1.3, §12 |

### 1.2 Corpus scope

`data/filings_metadata_e2.db`, read-only. Target set is E1's predicate,
unchanged:

```sql
form IN ('10-K','10-Q')
OR (form='8-K' AND has_earnings_item=1 AND earnings_doc_section_type IS NOT NULL)
```

| form | filings | sections attempted |
|---|---|---|
| 10-K | 2,445 | 4,890 (MDA + RISK_FACTORS) |
| 10-Q | 7,509 | 15,018 (MDA + RISK_FACTORS) |
| 8-K (earnings) | 10,567 | 10,567 (1 per filing) |
| **total** | **20,521** | **30,475** |

8-K selections by stored class: `EX99_PRESS_RELEASE` high 10,312 /
medium 26 / low 19; `8K_BODY` high 210. (Reconciles with
F2_INGESTION_REPORT §5's final table.)

Membership context, measured for §12: of the 20,521 target filings,
**11,403 (55.6%)** fall inside their own CIK's membership spell and
**13,886 (67.7%)** inside spell − 12 months. Core stratum: 14,780 total /
8,415 inside / 10,241 with the 12-month margin.

### 1.3 Cache census — the zero-GET precondition, verified

Every one of the **20,521** target documents is present in
`data/raw/documents/` (0 missing; 20,628 files in the directory). F3
therefore runs at **0 GETs by construction**, and R5 makes that structural
rather than incidental.

Two consequences that constrain design and must not be forgotten:

- **`filing_documents` holds rows for 8-K accessions only** (129,249 rows,
  10,569 distinct accessions — all 8-K). There is **no document index for
  any 10-K or 10-Q**, and only the *primary document* of a periodic filing
  is cached. Any resolution strategy that would need a sibling exhibit of a
  10-K (e.g. an EX-13 annual report) is **out of scope at 0 GETs** and must
  FAIL loudly with a named reason (C15 / D2).
- `data/raw/filing_index/` holds 10,875 index pages, again 8-K only.

### 1.4 What F3 does not touch

E1's artifacts stay frozen: `data/filings.parquet`,
`data/filings_metadata.db`, `data/labels.parquet`,
`data/labeling_corpus.parquet`, `data/universe.csv`. F3's outputs are new
paths (§7). `extract.py` must **refuse E1 paths by name** (§3 C1), the same
guard `ingest_prices.py` carries.

---

## 2. Section targets, and the arithmetic that follows from them

### 2.1 Per-form section targets (exhaustive; no new section types in F3)

| form | section_type | how located | absence semantics |
|---|---|---|---|
| 10-K | `MDA` | Item 7, TOC anchor → heading regex → stub resolver | FAIL (a 10-K always has an Item 7) |
| 10-K | `RISK_FACTORS` | Item 1A, TOC anchor → heading regex | FAIL, except the documented smaller-filer omission — reason code distinguishes |
| 10-Q | `MDA` | Part I Item 2 | FAIL |
| 10-Q | `RISK_FACTORS` | Part II Item 1A | **EXPECTED_ABSENT** — filers legitimately omit Item 1A when nothing changed (E1 documented this for 45 sections; pilot rate ~14%) |
| 8-K | `EX99_PRESS_RELEASE` \| `8K_BODY` | the document `ingest_metadata.select_earnings_document` already chose; F3 never re-resolves exhibits | FAIL only if the cached document yields <`MIN_SECTION_CHARS` |

**No new section types.** Item 7A, Item 1 Business and Item 3 Legal
Proceedings stay out: the labeling schema, `PROMPT_TEMPLATE.md`'s
applicability matrix and the fine-tune's training distribution are all
built on these four. Adding a section type is an F4 decision with a gate,
not an extraction change (`EXPANSION_PLAN` §5 F4: "APPLICABILITY extended
only deliberately").

### 2.2 Expected output volume — and why "~23k" is low

Pilot located-rates (144 filings drawn 6 per (form, filing-year) cell, seed
20260826; 288 attempts; `p0_probe_periodic.py`):

| form | section | located, 2015–18 | located, 2019+ | pooled |
|---|---|---|---|---|
| 10-K | MDA | 87.5% (21/24) | 93.8% (45/48) | 91.7% |
| 10-K | RISK_FACTORS | 83.3% | 91.7% | 88.9% |
| 10-Q | MDA | 95.8% | 100% | 98.6% |
| 10-Q | RISK_FACTORS | 87.5% | 85.4% | 86.1% |

The 8-K side is measured exactly, not estimated: of the 10,567 selections,
**12 extract to under `MIN_SECTION_CHARS` (30 chars) and will FAIL
`empty_after_extraction`** — and they are precisely F2 §5's named P5
near-empty class (Ford `0000037996-19-000005` 0 chars, MetLife
`0001099219-23-000041` 0 chars, PNC ×7, Cigna, Linde ×2, all image-only or
empty exhibits). F2 wrote that these *should* fail F3's floor; they do, by
name, before anything is recalibrated. So 8-K yields **10,555** sections.

Applied to §1.2's counts: **≈28,840 sections** (4,416 from 10-K + 13,869
from 10-Q + 10,555 from 8-K), with a sampling band of roughly ±700 at
n=72 per cell. The F3 brief's "~23k" is **low by ~1.25×**, which is inside
the decision-audit's "plan's chunk count low 1.2–2.1×" finding and is the
reason §12 re-derives F4's scale from real output rather than from a plan
number.

**Failure volume to triage is therefore ~1,600 rows** (30,475 − ~28,840),
of which ~1,040 are the legitimate 10-Q Item 1A omissions. This is what
makes per-filer rollup (§7.3) the mandatory instrument: nobody reads 1,600
rows, but 244 filers sorted by failure rate is a morning.

---

## 3. Exact `extract.py` changes

Lazy-elite: extend `extract.py` in place, add one small module-level
registry, add one new test file. No framework, no new dependency, no
abstraction layer. Every change below is scoped to a named function.

### C1 — CLI and paths (`main`, new `run(...)` signature)

```
python3 extract.py --db data/filings_metadata_e2.db \
                   --out-dir data/f3 \
                   --segment {earnings,10-K,10-Q,all} \
                   --shard-size N [--shard i] [--limit N] [--merge]
```

- `DB_PATH` / `PARQUET_PATH` become arguments with the E2 values as
  defaults. `--db data/filings_metadata.db` or an `--out-dir` resolving to
  `data/filings.parquet` **exits 2** with a message naming the E1 freeze
  (mirrors `ingest_prices.main`'s refusal, and gets the same test).
- `--limit` is retained for debugging and is recorded in the run manifest
  so a truncated run can never be mistaken for a full one.

### C2 — cache-only document reader (new `read_cached_document`)

```python
class CacheMiss(Exception): ...
def read_cached_document(relative_path: str, cache_dir: Path = RAW_DOCS) -> str
```

Reproduces `EdgarClient.get_archive_document`'s cache-key rule (leading
slash normalised, `/` → `_`) and **raises `CacheMiss` instead of
fetching**. `extract_item_section` / `extract_earnings_document` take a
`read` callable (defaulting to this one) instead of a `client`. `EdgarClient`
is no longer imported by the F3 path; the run manifest records
`network_gets: 0` as an assertion, not a hope.

### C3 — output schema, CIK-keyed (`run`)

`ticker` is dropped (NULL for all 45,545 E2 rows). Per-section row:

`cik, company_name, sector, stratum, accession_number, form, filing_date,
report_date, section_type, text, word_count, char_count, n_prose_paragraphs,
prose_word_share, extraction_method, extraction_confidence,
extraction_status, flags (list[str]), source_document, below_length_floor,
population_gate, quarter_cell_size, results_signature_present,
item202_prefix_chars, item202_block_words, supplemental_tail_share,
extractor_version, run_id`

- `filing_date` and `report_date` are carried through **unchanged** from
  the `filings` table (HANDOFF §7 point-in-time discipline; pinned by a
  test in §11).
- `company_name/sector/stratum` join from `companies` — the per-filer
  rollup and the QA sampling frames need them, and joining once at
  extraction time is cheaper and safer than at three downstream sites.
- **F4 coupling, named here so it is not discovered by crash:** `chunk.py`
  reads `row["ticker"]` in `extract_prose_paragraphs` and writes
  `home_ticker` / `occurrence_tickers`. F4 must switch those to `cik`. One
  line each; it is F4's edit, not F3's.

### C4 — parse the document once (`extract_periodic_sections`, new)

```python
def extract_periodic_sections(read, cik, accession, primary_document, form
                              ) -> dict[str, ExtractionResult | None]
```

Reads → `strip_sgml_document_wrapper` → one `BeautifulSoup` →
`find_toc_item_anchors` once → locate both sections → per-section text
extraction. `extract_item_section` stays as a thin wrapper so existing
call-sites and tests keep working. Measured saving: 2.53 s → 1.42 s per
filing (§10).

### C5 — attempt records and the failure taxonomy (`run`)

`run()` currently appends failures to a list and prints them. Replace with
an `AttemptRecord` per (accession, section_type) written to the audit
artifact (§7.2). `extraction_status ∈ {OK, FLAGGED, EXPECTED_ABSENT, FAIL}`,
with exactly one `reason_code` from this closed enum:

| reason_code | status | meaning |
|---|---|---|
| `ok` | OK | located, above floor, no flag |
| `item_absent_from_toc` | EXPECTED_ABSENT (10-Q RF) / FAIL (else) | TOC parsed, target item not listed. E1's deliberate no-regex-fallback guard stays. |
| `no_toc_and_no_heading_match` | FAIL | no anchor TOC and the tight heading regex found nothing |
| `anchor_span_below_min_chars` | FAIL | anchor found, slice < `MIN_SECTION_CHARS` |
| `mda_stub_resolved` | OK | resolver recovered same-document MD&A (confidence `medium`) |
| `mda_stub_unresolved_same_doc` | FLAGGED | stub kept, low confidence |
| `mda_stub_external_document` | FLAGGED | stub points at another *document* (Annual Report / Exhibit 13) — unresolvable at 0 GETs (§1.3) |
| `below_length_floor` | FLAGGED | word count under the (form, section) floor |
| `head_foreign_item` | FLAGGED | slice head names a different Item (C14) |
| `head_keyword_absent` | FLAGGED (informational) | slice head lacks the section's own title keyword |
| `heading_regex_fallback` | FLAGGED | located by the low-confidence fallback |
| `earnings_item202_missing` | FLAGGED | `8K_BODY` with no `Item 2.02` in its text |
| `earnings_item202_block_thin` | FLAGGED | item-2.02 block <200 words before the next item heading |
| `earnings_population_gate` | FLAGGED | §4 |
| `earnings_thin_document` | FLAGGED | carries F2's P5 thin/near-empty class into F3 by name |
| `earnings_supplemental_diluted` | FLAGGED | §6 |
| `empty_after_extraction` | FAIL | text < `MIN_SECTION_CHARS` |
| `cache_miss` | FAIL | must be 0; a nonzero count is a run-level FATAL |
| `document_read_error` | FAIL | decode/parse exception, with the exception text |

A row may carry several flags (`flags` list) but exactly one primary
`reason_code`, chosen by this fixed precedence: FAIL codes > `cache_miss` >
stub codes > `head_foreign_item` > `below_length_floor` > earnings codes >
`heading_regex_fallback` > `head_keyword_absent` > `ok`.

### C6 — confidence invariant

`extraction_confidence ∈ {high, medium, low}` as today, plus one hard
invariant, tested: **`extraction_status='FLAGGED'` ⇒ confidence ≠ 'high'.**
This is the direct fix for the four pilot rows below that are `anchor/high`
today at 43–102 words.

### C7 — stub detection becomes word-count-triggered (R4)

Current code requires `len(text.split()) < MDA_STUB_WORD_CEILING`
**AND** `STUB_REFERENCE_LANGUAGE_RE` to match before it will even try to
resolve. Measured on the 144-filing pilot, that language gate rejected
**every real stub it met (0/4 matched)**:

| filing | filer | words | conf today | why the regex missed it |
|---|---|---|---|---|
| `0000086521-17-000017` | Sempra 2017 | 43 | **anchor/high** | *"The information required by Item 7 **is set forth in** … in the Annual Report, on pages 2 through 78."* — phrase not in the regex |
| `0001193125-17-053947` | US Bancorp 2017 | 50 | heading_regex/low | *"…incorporated **into this report** by reference"* — word order breaks the literal `incorporated by reference` |
| `0000019617-17-000314` | JPMorgan 2017 | 55 | **anchor/high** | *"appears on\npages 36–138"* — the regex is `appears on page`; the line break lands between `on` and `pages` |
| `0001645590-19-000044` | HPE 2019 | 102 | **anchor/high** | not a stub at all — a wrong slice ("OFF-BALANCE SHEET ARRANGEMENTS") that only the floor can catch |

New rule: any `(10-K, MDA)` extraction under `MDA_STUB_WORD_CEILING`
enters `resolve_incorporated_by_reference_mda`, regardless of phrasing.
`STUB_REFERENCE_LANGUAGE_RE` is kept as an **evidence field**
(`stub_language_present`) and as the discriminator between
`mda_stub_unresolved_same_doc` and `mda_stub_external_document` (the latter
requires a match on `annual report|exhibit 13|separate|accompanying`).
Cost: ~135 extra resolver passes corpus-wide (5.6% of 2,445), ~1.5 s each.

### C8 — 8-K earnings path (`extract_earnings_document`)

Gains the item-2.02 slicing (§5), the population gate (§4), the dilution
measurement (§6) and the prose-share measurement (C16). Signature becomes
`extract_earnings_document(read, relative_path, section_type, gate_context)`.

### C9 — resumable sharding (`plan_shards`, `run_shard`, `merge_shards`)

Deterministic: filings sorted by `(form, accession_number)`, sliced into
contiguous shards of `--shard-size`. Each shard writes
`data/f3/shards/{segment}_{i:04d}.parquet` and
`…_{i:04d}.audit.parquet` to a temp name then `os.replace`s them, then
writes `…_{i:04d}.done`. A shard whose `.done` exists is skipped. Resume =
re-run the identical command. `--merge` concatenates, asserts no duplicate
`(accession_number, section_type)` and that
`attempts == OK + FLAGGED + EXPECTED_ABSENT + FAIL`, then writes the final
artifacts (§7).

### C10 — run manifest (`write_manifest`)

`data/f3/run_manifest.json`: run_id, UTC start/end, git rev, sha256 of
`extract.py`, sha256 of the input DB, argv, per-shard row counts and
wall-times, `network_gets: 0`, cache-miss count, and the resolved values of
every floor/ceiling constant used **in that run** (so a later floor change
is diffable against the run that produced the numbers).

### C11 — edge-handler registry (`EDGE_HANDLERS`, new)

```python
EdgeHandler = namedtuple("EdgeHandler", "name applies_to reason handler")
EDGE_HANDLERS: list[EdgeHandler] = [...]
```

`applies_to` is a `(cik, form, section_type)` predicate — deliberately
narrow, per the lazy-elite rule and F2's Prologis/PSEG precedent. Every
handler carries a one-paragraph docstring naming the filer, the filing that
motivated it and what it was verified against. The run prints fired-counts
and marks any handler with **0 fires as DEAD** (F2's override-file
discipline). A handler must never be added without a test and a fired-count
line in the P1/P3 report.

### C12 — dialect fixes inside existing regexes (small, named)

- `_ITEM_LABEL_PREFIX_RE` accepts the parenthesised-letter dialect
  `Item 1(A).` (measured: ICE `0001571949-24-000011` 10-Q 2024). Normalises
  to `1A`.
- `STUB_REFERENCE_LANGUAGE_RE` gains `is set forth in`,
  `incorporated .{0,20}by reference`, and tolerates whitespace inside
  `appears on\s+pages?` — all three from named filings in C7. (Demoted to
  evidence by C7, but it should still be *right*.)

### C13 — nothing else changes

`html_fragment_to_text`, `strip_sgml_document_wrapper`,
`find_toc_item_anchors`, `locate_item_section_by_anchor`, the heading-regex
fallback and the anchor-hop / text-heuristic resolvers keep their current
behaviour. This is deliberate: a 12-row spot regression re-extracted E1
filings with today's code and got **12/12 byte-identical text** against
`data/filings.parquet`, so E1's extractions are exactly reproducible and
that property is worth keeping as a regression pin (§11 T14).

### C14 — the two head checks (new, both measured)

Measured on the pilot's 263 located sections (`p0_probe_heads.py`):

| check | rule | fires | true defects found |
|---|---|---|---|
| `head_foreign_item` | first `Item N` token in `text[:200]` has a **different number** than the target item | **1 / 263 (0.4%)** | 1 — `0001628280-26-026673`, a 10-Q whose "MD&A" slice opens *"ITEM 3. QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK"*: 1,770 words, `anchor`/**high**, above the 1,000-word floor. Nothing else in the pipeline sees this. |
| `head_keyword_absent` | `text[:300]` lacks the section's title keyword | 10 / 263 (3.8%) | ~3 of 10; the other 7 are benign (the slice starts one sub-heading in: "CRITICAL ACCOUNTING POLICIES…", "WHAT YOU WILL FIND IN THIS MD&A", …) |

So: `head_foreign_item` is a FLAG that downgrades confidence;
`head_keyword_absent` is **informational only** — it is a good sampling
frame for §9's T3 tier and a bad verdict. Both rates are pilot estimates on
n=263 and are re-measured corpus-wide in P3.

**A known miss, stated rather than papered over.** Two variants were
measured on the same 263 rows before choosing:

| variant | rule | flags | outcome |
|---|---|---|---|
| A | item label matched at the very start of the head, compared **exactly** (`1A` vs `1A`) | 2 | 1 true defect + **1 false positive**: the `ITEM 1(A). RISK FACTORS` dialect (D1). Also missed the row below entirely — its head begins "PART II. OTHER INFORMATION…", which an anchored pattern never matches. |
| **B (ships)** | first `Item N` token anywhere in `text[:200]`, compared on the **number** only | 1 | the true defect, 0 false positives |

Neither variant catches `0001628280-26-032278` — a "RISK_FACTORS" slice
that opens *"PART II. OTHER INFORMATION ITEM 1. LEGAL PROCEEDINGS"* (422
words, `anchor`/high), because its first item number ("1") equals the
target's. It is caught only by the weaker `head_keyword_absent` check and
by the QA sample. The residual is documented, not closed by a cleverer
regex — this is the E1 lesson about loose heading patterns, applied to the
guard rather than to the extractor.

### C15 — dialects/edge classes already found in P0 (input to C11/C12)

| id | class | filer(s) seen | disposition |
|---|---|---|---|
| D1 | `Item 1(A).` parenthesised letter | ICE 10-Q 2024 | C12 regex fix |
| D2 | **MD&A incorporated from a different DOCUMENT** ("in the Annual Report, on pages 2 through 78" / "in the Company's 2016 Annual Report") | Sempra, US Bancorp | `mda_stub_external_document`, FLAGGED. **Unresolvable at 0 GETs** — no 10-K exhibit is cached and `filing_documents` has no periodic rows (§1.3). Class size measured in P3; the fetch decision is main-session (§13.1). |
| D3 | `appears on\npages 36–138` (line break inside the phrase) | JPMorgan 2017 | C12 regex fix; C7 makes it moot |
| D4 | anchor lands on a foreign item → wrong-section text at high confidence | one 10-Q 2026 | `head_foreign_item` (C14) |
| D5 | `heading_regex` fallback fires at all (0 rows in E1's 884; **10 of 288 attempts** in the pilot) | 5 filings incl. 2 pre-2018 | Always `low` confidence; over-sampled in QA tier T3 |

### C16 — prose-share, measured at extraction time (input to F4)

Each row records `n_prose_paragraphs` and `prose_word_share` using
`chunk.py`'s own `MIN_PROSE_WORDS = 40` (imported, not re-implemented).
Reason: **a section with zero ≥40-word lines produces zero labeling
chunks.** Verified on E1's frozen artifacts — `n_prose == 0` ⇒
`n_chunks == 0` in **97 of 97** cases.

Measured share of sections with zero prose paragraphs:

| section_type | E1 (frozen, 25 filers) | E2 sample (n=300 EX99, seed 20260826) |
|---|---|---|
| `EX99_PRESS_RELEASE` | 4.6% (15/327) | **14.7%** |
| `RISK_FACTORS` | 31.1% (79/254) | (measured in P3) |
| `MDA` | 0.7% (2/299) | (measured in P3) |
| `8K_BODY` | 25% (1/4) | (measured in P3) |

Cause is structural, not a bug: SEC press releases are frequently laid out
as tables, so `get_text("\n")` emits one short line per cell. **F3 does not
change the text for this** (it would break the E1 byte-identity pin and it
is chunk.py's constant, not extract.py's) — F3 *measures* it and hands F4
both the count and the decision (§12.3).

---

## 4. The population gate (H4's condition, re-measured)

### 4.1 What the gate is

Per `H4_docsample.md` §7, and binding input 1:

> Emit a FAIL/WARN row, do not silently extract, when an earnings selection
> sits in a multi-filing (CIK, calendar-quarter) cell AND its text lacks a
> results-announcement signature.

Cell key = `(cik, calendar quarter of filing_date)`. My reproduction of the
cell computation over all 10,567 selections returns **1,519 multi-cell
selections (14.37%)** — H4's number exactly, so the two implementations
agree before any of the rest is trusted.

### 4.2 The narrowed variant, RE-MEASURED on H4's 155-row ledger

H4 proposed narrowing the trigger with a results-announcement signature
(*"today reported / announced results / per diluted share / quarterly
results"*) and explicitly refused to trust it unmeasured. Re-measured, on
the same ledger, with text extracted through `extract.py`'s own
`strip_sgml_document_wrapper` → `html_fragment_to_text`:

| variant | recall on the 9 C rows | flags in the 155 | precision C | precision C-or-B | corpus trigger volume |
|---|---|---|---|---|---|
| **V0 — multi-cell only (shipped)** | **9/9 = 100%** | 39/155 | 0.231 | 0.667 | **1,519 (14.37%), 146 filers** |
| V1 — multi-cell AND lacks H4's 4 markers | **8/9 = 88.9%** | 29/155 | 0.276 | 0.759 | 966 (9.14%) |
| V3 — multi-cell AND lacks an announcement-verb set + "per diluted share" | 9/9 (**in-sample, fitted**) | 24/155 | 0.375 | 0.917 | 629 (5.95%) |

**The narrowed variant as proposed fails.** The row it drops is
`0001104659-22-112514` — Intercontinental Exchange furnishing **Bakkt's**
results, not its own. Its text contains "quarterly results", "per share",
"press release" and "months ended": a results-announcement signature cannot
distinguish *whose* results are being announced, which is precisely the
error class. H4 named that row as "worth naming loudly"; a screen that
suppresses it is worse than no screen.

**V3 is not a rescue.** It reaches 9/9 only because its marker set was
chosen after looking at which markers the nine C rows lack — an in-sample
recall on the very ledger used to fit it, with no held-out evidence. It is
recorded here as a candidate for a future, independently-sampled
measurement; it does not ship.

### 4.3 What ships

```
population_gate ∈ {OK, WARN_MULTI, WARN_MULTI_NOSIG}
```

- `OK` — sole earnings 8-K of its (CIK, quarter). 9,048 selections
  (85.63%); H4 measured **0 errors in 116 hand reads** of this class
  [0.00, 3.21].
- `WARN_MULTI` — multi-cell, signature present. 890 selections.
- `WARN_MULTI_NOSIG` — multi-cell, no signature. **629 selections.** Same
  gate outcome, higher triage priority.

Both WARN levels are **flags on rows that are still extracted**, plus an
audit row plus a per-filer rollup line. They do not drop text: the 1,519
include real second releases (PNC files 29 same-day pairs; AT&T/IBM file
release + supplement) and the genuine short pre-announcements H4 classed B.
`results_signature_present` and `quarter_cell_size` are stored per row so
F4/F5 can condition on either, and so a future narrowing can be measured
against real verdicts instead of a fitted marker list.

Concentration (why per-filer triage works): 146 filers carry all 1,519
flags; the top 10 carry **34.4%** — Tesla 93, PNC 80, Pioneer 74, MetLife
54, EQT 40, AbbVie 39, Illumina 38, Diamondback 36, Regeneron 36,
Occidental 32. 34.6% of flagged rows are pre-2019; 82.4% are core stratum.
Cell sizes among flagged: 2 → 1,344, 3 → 162, 4 → 8, 5 → 5.

### 4.4 What the gate is explicitly NOT

Not a re-run of selection, not a policy change to
`select_earnings_document`, not a per-filer handler, and not a deletion of
the 790 "extra" filings. H4 §7 rules all four out; the gate is a
population-membership flag, which is where the defect actually lives.

---

## 5. `8K_BODY` item-2.02-anchored slicing

Census over **all 210** `8K_BODY` selections (`p0_body8k_census.py`;
H4 §8.3 sampled 30 of these):

| quantity | measured |
|---|---|
| documents containing `Item 2.02` in extracted text | **210 / 210** |
| chars before the first `Item 2.02` | min 1,121 · p10 1,277 · **median 1,971** · p90 2,216 · max 14,938 |
| that prefix as a share of the document | median **21%** · p90 52% · max 78% |
| words, whole document | median 1,408 (min 378) |
| words, from `Item 2.02` to EOD | median 1,094 (min 107) |
| filings where a *different* item heading follows the 2.02 heading | 88 / 210 |
| …of which the 2.02 block is **<200 words** | **45 / 210 (21%)** |
| `EX99_PRESS_RELEASE` documents containing `Item 2.02` | 1 / 10,357 (0.01%) — slicing is `8K_BODY`-only |

### The rule

1. Find the **first** `item\s*2\.02` in the extracted plain text.
2. Slice `[match.start() : end of document]`. Record
   `item202_prefix_chars`.
3. **The end boundary is the end of the document, never the next item
   heading** (R2). Ending at the next item heading would leave <200 words
   in 45 of 210 sections — Humana 8 words, BAC 12, Xcel 14, Goldman 8,
   Emerson 30 — because those filers put the substance under 7.01/8.01 and
   incorporate it into 2.02 by reference. Cutting there is exactly the
   "mangle silently" failure the hard rules forbid.
4. Record `item202_block_words` (words between the 2.02 heading and the
   next different item heading, else null) and FLAG
   `earnings_item202_block_thin` when it is <200. This is the honest
   version of what the discarded end-boundary rule would have done
   silently: 45 rows say *"the 2.02 block here is a pointer; most of this
   text belongs to other items."*
5. If no `Item 2.02` match exists (0/210 today), keep the whole document,
   `extraction_method='whole_document'`, FLAG `earnings_item202_missing`.
6. FLAG `earnings_item202_prefix_large` when the dropped prefix exceeds
   **4,000 chars** (measured: 4 of 210 — BAC 4,890, MPLX 7,491, Marathon
   12,378, Emerson 14,938), so an unusually large drop is visible to a
   human rather than assumed.

### Consequence for the floor, stated up front

Slicing removes boilerplate that was padding word counts. Against E1's
`("8-K","8K_BODY")` floor of 500 words: **4 of 210 rows are below it
pre-slice, 43 of 210 post-slice.** That is a real 10× increase in flagged
rows and it is the *intended* effect — the cover page was making thin
item-2.02 disclosures look substantial. The floor is not moved to hide it
(§8.3).

---

## 6. Combined release + supplemental dilution

H4 §8.4: Simon Property `0001104659-21-013702` is a single EX-99.1
"EARNINGS RELEASE & SUPPLEMENTAL INFORMATION" book, ~74% property-level
tables. The pick is correct; the section is diluted.

**F3 measures the class; it does not truncate the text.** Truncating at a
guessed boundary is exactly "extraction that mangles content", and the
release narrative's end is not reliably marked across filers.

What is stored per earnings row (all from the single pass that already
extracts the text — no extra cost):

- `words`, `n_prose_paragraphs`, `prose_word_share` (C16).
- `supplemental_tail_share`: if a supplemental-package heading is found
  after the first 20% of the document (marker list: `supplemental
  information`, `supplemental package`, `supplemental financial
  information`, `supplemental operating`, `supplemental data` —
  case-insensitive, whole-line matches only), the share of characters after
  it; else 0.0. FLAG `earnings_supplemental_diluted` at ≥0.5.
- The marker list is **provisional and must be calibrated in P1** against
  the corpus before the flag counts are reported: the calibration rule is
  the one F2 used for the deck-title screen — a marker enters the list only
  if measured hits are dominated by true positives, with the false positive
  named (F2 §5, Danaher). Simon Property's known row and AvalonBay's clean
  two-exhibit shape are the anchors.

Measured today, on a 300-row EX99 sample: `prose_word_share` median 0.399,
p25 0.274, and **14.7% at exactly 0.0**; Simon Property 2021 sits at 0.233
with 39 prose paragraphs out of 14,916 words. So prose-share alone does not
identify the class (many ordinary releases are table-heavy) — which is why
the flag needs the boundary marker, and why the class size is reported as a
measured number in P3 rather than asserted here.

---

## 7. Audit artifacts F3 emits

All under `data/f3/`. Every one is regenerated by a re-run; none is
hand-edited.

### 7.1 `data/filings_e2.parquet` — the corpus
One row per extracted section (schema in C3). ~28–29k rows expected.
Rows with `extraction_status='FLAGGED'` are **included** (with their flags);
rows that FAILed are not (they exist in 7.2). This keeps "the corpus" and
"the audit" as two artifacts with one join key.

### 7.2 `data/f3/extraction_audit.parquet` — one row per ATTEMPT
`cik, company_name, sector, stratum, accession_number, form, filing_date,
section_type, extraction_status, reason_code, flags, extraction_method,
extraction_confidence, word_count, prose_word_share, source_document,
note`. **30,475 rows.** Plus `data/f3/extraction_failures.csv` — the
FAIL + FLAGGED subset only, CSV so it can be eyeballed and sorted without
pandas.

### 7.3 `data/f3/per_filer_rollup.csv` — the mandatory triage instrument
One row per (cik, form, section_type): `n_attempt, n_ok, n_flagged,
n_expected_absent, n_fail, fail_rate, flag_rate, n_pre2019, fail_rate_pre2019,
fail_rate_2019plus, top_reason_code, n_low_confidence, median_words`.
Sorted by `fail_rate` desc. This is what §9's triage reads, and it is what
makes "triage every failure BY FILER" a finite job for 244 filers.

### 7.4 `data/f3/population_gate.csv`
All 1,519 gate-flagged selections: `cik, company_name, accession_number,
filing_date, quarter, quarter_cell_size, section_type,
selection_confidence, results_signature_present, gate_level, words,
prose_word_share`, plus an empty `verdict` / `verdict_note` column pair for
P3's triage to fill (the H4 ledger pattern).

### 7.5 `data/f3/length_distribution.csv`
Per (form, section_type): n, min, p1, p5, p10, p25, p50, p75, p90, p99,
max of `word_count`, split by era (≤2018 / ≥2019) and by stratum, plus the
count flagged at the current floor and at each candidate floor. This is the
evidence table §8's recalibration argues from — published before any floor
moves.

### 7.6 `data/f3/run_manifest.json` (C10) and `data/f3/shards/` (C9)

### 7.7 `data/f3/status/P*.md`
Stage reports; `P3_qa.md` carries the QA read, the recalibration
before/after counts and the F4-scale table.

---

## 8. Floors and ceilings: the recalibration plan

### 8.1 Standing rules (these are the point)

1. **A floor is a flag, never a filter.** No row is dropped for being
   short. A floor change therefore never changes corpus membership — only
   the size of the review queue. That is what makes recalibrating it
   low-stakes and honest.
2. **A floor never moves to make a specific failure disappear.** It moves
   only with: (a) the measured new distribution (§7.5) in the report;
   (b) a hand-read of rows in the gap between old and new floor (all of
   them, or a seeded sample of ≥10 with the sampling rule stated);
   (c) the **named rows that must still fail**, verified still flagged
   after the change; (d) before/after counts printed in `P3_qa.md`.
3. **Named rows that any recalibration must argue past, by name:**
   - F2 §5 P5's **50 thin (<1,500 chars) and 12 near-empty (<100 chars)**
     EX-99 selections — F2 states in writing they *should* fail F3's floor.
     Corroborated here, exactly: **12 EX99 documents extract to <30 chars**
     (the same 12 filings — Ford, MetLife, PNC ×7, Cigna, Linde ×2) and
     **53 to <250 words** out of 10,357.
   - H4 §8.1's two genuine short releases: **Tesla Q1-22 P&D, 276 words**
     and **KKR monetization update, 384 words**. A floor above ~400 words
     fails both, and H4 forbids that "without arguing past these two rows
     by name."
   - E1's `(10-Q, RISK_FACTORS)` floor of 15 words exists because a
     one-sentence compliant cross-reference (MA/OXY/COP/MCD, 24 words) is
     legitimate filer practice, not a bug.
4. **The floor is not the error-catch.** H4's largest document (21,009
   words) was an error and its smallest (276) was genuine. Length screens
   for *thin* extractions; §4 screens for *wrong-population* documents;
   C14 screens for *wrong-section* slices. Never substitute one for
   another.

### 8.2 Procedure (P3)

1. Run F3 with **E1's floors unchanged**; publish §7.5's distribution.
2. For each (form, section_type), state the candidate floor as a
   distribution quantile with the gap to the nearest genuine row named.
3. Apply rules 8.1(2)–(3); record before/after flag counts.
4. Re-run only the flag computation (a pure function over the parquet) —
   **never re-extract to make a floor look better**.

### 8.3 Candidate values, with what is already measured

| (form, section) | E1 floor | measured E2 evidence | P0's candidate | before → after flagged |
|---|---|---|---|---|
| `8-K, EX99_PRESS_RELEASE` | 50 | 10,357 docs: p0.5% = 243 w, p1 = 553 w, p5 = 1,567 w, median 5,194 w. 12 docs <50 w; 53 <250 w; 86 <400 w. F2's P5 thin class (~50 docs) sits under ~250 w. Tesla 276 / KKR 384 stay above 250. | **250** (a raise, not a lowering) | **12 → 53** |
| `8-K, 8K_BODY` | 500 | post-slice words: min 107, p5 289, median 1,094. 4/210 below 500 pre-slice, **43/210 post-slice**. | **keep 500** | 4 → 43 (caused by §5's slicing, not by a floor move) |
| `10-K, MDA` | 1,500 | pilot: 4 of 72 below (43/50/55/102 w); genuine p5 ≈ 1,199 w — **overlaps the ceiling**, so P3 must read the 1,000–1,500 w band before touching either constant | **hold pending P3 read** | — |
| `10-K, RISK_FACTORS` | 2,000 | pilot p5 3,084 w, min 39 w (one stub-shaped row) | hold | — |
| `10-Q, MDA` | 1,000 | pilot min 1,770 w — but the 1,770-word row is the wrong-section `ITEM 3` slice, i.e. the floor cannot catch it; C14 must | hold | — |
| `10-Q, RISK_FACTORS` | 15 | pilot median 59 w, p5 26 w — the legitimate cross-reference class dominates | hold at 15 | — |

### 8.4 `MDA_STUB_WORD_CEILING`

Today 1,500, justified by E1's "stubs are 36–53 words, smallest genuine
MD&A is 2,441". That gap does not survive 244 filers: the pilot's genuine
10-K MD&A p5 is ~1,199 words. Under C7 the ceiling is now a **resolver
trigger only** (it no longer decides trust), so a false trigger costs
compute, not correctness — an over-wide ceiling is the safe direction.

Recalibration rule for P3, pre-committed: the ceiling must sit **above the
longest observed stub** and the band between it and the `(10-K, MDA)` floor
must be **hand-read in full** if it holds ≤20 rows, or sampled at 10 rows
with the seed recorded if more. If genuine MD&As and stubs overlap in
length (they may), the ceiling stays where it is and the overlap rows are
named individually in `P3_qa.md` — no constant is tuned to separate an
overlap that does not exist.

---

## 9. Manual-QA protocol — written in full BEFORE any section is read

This section is the pre-registration. It is written now, in P0, before a
single E2 section has been read, precisely so that the read cannot be
extended, re-drawn or re-scoped after its results are visible.

### 9.1 Sample: 40 sections, three tiers, seeded and frozen before reading

Drawn from `data/f3/extraction_audit.parquet` with
`random.Random(20260827)`, over rows sorted by
`(accession_number, section_type)`; the drawn ids are written to
`data/f3/qa_manifest.json` **before the first read**, and that file is
never regenerated.

| tier | n | frame | why |
|---|---|---|---|
| **T1 BASE** | 16 | SRS over all `extraction_status='OK'` rows | The only base-rate-representative slice. Reported alone, never pooled. |
| **T2 NEW / OLD** | 16 | 6 pre-2019 periodic sections from CIKs **not in E1's 25**; 4 pre-2019 earnings; 3 from 2019+ new filers; 3 from the extension stratum (industrials / utilities / materials_realestate — sectors E1 never had) | `EXPANSION_PLAN` §5 F3's mandate: weight toward new filers and pre-2019 filings. 219 of 244 CIKs are new. |
| **T3 FLAG** | 8 | one row per distinct `reason_code` in the FLAGGED/FAIL population, prioritised by class size, drawn at random within the code | The Tier-A/B analogue: deliberately unrepresentative, kept out of the base rate, reported separately. |

24 of 40 (60%) are new-filer / pre-2019 / flagged by construction. Tiers are
never pooled into one headline number (the §2a and H4 precedent).

### 9.2 Verdicts, fixed before reading

- **CORRECT** — the first and last 200 words both belong to the target
  section, and the middle slice is that section's content.
- **TRUNCATED** — right section, ends early (next section's heading absent
  and the text stops mid-topic).
- **OVER-CAPTURED** — right section plus material from a neighbouring item.
- **WRONG-SECTION** — the text is predominantly another item.
- **EMPTY-OR-BOILERPLATE** — cover page, exhibit index, image wrapper, or a
  stub.
- **CORRECTLY-FAILED** (FAIL rows only) — the section genuinely is not in
  this document and failing was right.
- **WRONGLY-FAILED** — the section is there and the extractor missed it.

One verdict per row, plus a free-text note quoting the bytes that decided
it. Verdicts are written to `data/f3/qa_verdicts.csv` as they are made and
are **frozen per row when written** — never revised after the class's
corpus size is known.

### 9.3 Evidence card (what is actually read)

For each drawn row, from the parquet only (no re-extraction): filer, CIK,
form, section, filing_date, method, confidence, flags, word count,
prose-share; then `text[:1200]`, a 600-char slice at the midpoint, and
`text[-600:]`. Every card is read individually and the read is reported as
"what I read", not as counts (the H4 §3 standard).

### 9.4 STOPPING RULE

1. **The read is complete when all 40 drawn rows carry a written verdict.**
   Not before, not after.
2. **Escalation does not stop the read.** If ≥3 rows in any tier share a
   single diagnosable cause, that class is (a) named, (b) measured
   mechanically over the whole corpus — not by reading more rows — and
   (c) given either a named handler (§3 C11) or a written
   "measured, not fixed" disposition. The read then continues to 40.
3. **Exactly one extension is permitted, once, under one condition:** a
   tier whose measured error rate has a 95% Wilson **lower** bound above
   10% gets **+10 rows in that tier**, drawn from the same frozen frame
   with seed 20260828. The extension is reported as its own tier and is
   never pooled into the base-rate estimate. There is no second extension
   and no extension in any other tier.
4. **Prohibited, explicitly:** extending because the results look good;
   re-drawing after seeing verdicts; reading extra rows to find another
   example of an already-named class (a named class gets a census — the H4
   lesson); using the spot-read to justify moving a floor (§8.1(2) governs
   floors); reporting a pooled all-tier headline rate.
5. **If the read cannot be finished** (context/time), the partial read is
   reported with the drawn-but-unread row ids listed explicitly. A
   truncated read is never silently reported as a completed one.
6. The read's verdicts are **model judgments** (HANDOFF §7) — recorded as
   such, never as the owner's.

### 9.5 Per-filer failure triage (mandatory, separate from the spot read)

Every FAIL, every FLAGGED row and every below-floor row is triaged **by
filer**, from `per_filer_rollup.csv`, in this fixed order:

1. Filers whose `fail_rate` is ≥50% on any (form, section) with n≥4 — the
   Prologis/PSEG shape (a systematic single-filer defect).
2. Filers with ≥10 flagged rows.
3. Every remaining `reason_code` class, by size, with at least one row read
   per class.
4. Every class either gets a named handler, or a written disposition
   ("measured, not fixed, here is the size and why").

Triage output is a table in `P3_qa.md`: class, size, filers affected,
disposition, and — for anything fixed — the before/after count.

---

## 10. Run segmentation, resumability, wall-clock

### 10.1 Measured rates (this machine, offline, partial CPU contention)

| workload | measurement | rate |
|---|---|---|
| earnings 8-K, whole population | **10,567 documents in 1,635 s** (a full-population measurement, not an extrapolation — it is `p0_gate_corpus.py`, which does F3's text extraction plus the gate and item-2.02 scans) | **0.155 s/doc** |
| 10-K, current double-parse code | 144-filing pilot | 3.10 s/filing |
| 10-Q, current double-parse code | same | 1.18 s/filing |
| component split | 12 filings | read 0.03 s · **soup 1.05 s** · TOC 0.03 s · both slices 0.31 s |
| parse-once saving (C4) | same 12 | **2.53 s → 1.42 s per filing (−44%)** |
| solo-vs-contended factor | probe run alone vs. alongside one other job | ×0.59 |

### 10.2 Segments and shards

| # | segment | units | shard size | shards | est. wall (single process, parse-once, solo) |
|---|---|---|---|---|---|
| A | `earnings` (8-K) | 10,567 docs | 1,500 | 8 | **~18–27 min** (0.155 s/doc measured; solo ≈0.10–0.12) |
| B | `10-K` | 2,445 filings | 250 | 10 | **~45–75 min** |
| C | `10-Q` | 7,509 filings | 500 | 16 | **~55–90 min** |
| | **total** | 20,521 filings | | **34** | **~2–3.5 h** |

Each shard is ≈5–8 minutes of work, satisfying HANDOFF §4's "checkpoint ≈
10 minutes of work". Segment A runs **first**: it is the fastest, exercises
the whole write/merge path end-to-end, and produces the population-gate
audit early, so a defect surfaces in 20 minutes rather than 3 hours.

### 10.3 Resume protocol (HANDOFF §4)

- Long runs are **main-session background tasks**, launched as an
  auto-resume chain. **Never spawn the run from inside a subagent** (the
  epoch-1 SIGTERM lesson).
- Any task can be SIGTERMed at any time. The blast radius of a kill is
  **one shard** (≤8 min), because `.done` markers are written only after an
  atomic `os.replace` of both output files.
- Resume = re-run the identical command. Idempotent by construction; a
  re-run with all shards present does nothing but re-merge.
- Concurrency is a knob, not a requirement: `--shard i` allows N workers.
  Measured scaling is poor (two mixed processes returned ~1.2× aggregate
  throughput), so **2 workers is the recommended maximum** and the
  single-process estimate above is the one to plan against.
- The run prints, per shard: shard id, rows in/out, status counts, elapsed
  seconds, and a running `network_gets=0` assertion.

---

## 11. Offline test plan

`extract.py` **has no test file today** — that is itself a finding, and it
is why P1's test work is scoped as a new file rather than an edit.
New: `test_extract_e2.py`. All tests offline, no sockets, no network
imports on the F3 path. Real-byte fixtures go in `data/f3/fixtures/` as
truncated prefixes, the convention `data/f2/fixtures/` already uses.

| # | test | pins |
|---|---|---|
| T1 | `read_cached_document` raises `CacheMiss` on a missing path and never constructs `EdgarClient` (monkeypatched to raise on import-use) | R5 |
| T2 | end-to-end run over a 6-row fixture DB records `network_gets == 0`; a deliberately missing document yields a `cache_miss` FAIL row, not a fetch | R5, R9 |
| T3 | `--db data/filings_metadata.db` and any `--out-dir` resolving onto `data/filings.parquet` exit 2 | E1 freeze |
| T4 | `extract_periodic_sections` returns per-section results identical to two `extract_item_section` calls on the same fixtures | C4 |
| T5 | population gate: cell computation from `(cik, quarter)`; the three levels; **all 9 H4 C-row accessions are flagged** by the shipped V0 gate | §4 |
| T6 | the narrowed variant's measured recall is encoded as a test over the ICE fixture: the H4 marker set **does not** flag `0001104659-22-112514`, and the shipped gate **does** — the test documents why V1 was rejected | §4.2 |
| T7 | `8K_BODY` slicing: prefix dropped from the first `Item 2.02`; end boundary is EOD; `item202_block_words` computed; thin-block flag fires on a Humana-shaped fixture | §5 |
| T8 | missing `Item 2.02` → whole document + `earnings_item202_missing`, never an empty section | §5 |
| T9 | item-2.02 slicing does **not** apply to `EX99_PRESS_RELEASE` rows | §5 |
| T10 | stub path: Sempra / US Bancorp / JPM-2017 phrasings all enter the resolver on word count alone; unresolved → `low` confidence and the right reason code; external-document phrasing → `mda_stub_external_document` | C7 |
| T11 | invariant: no row with `extraction_status='FLAGGED'` carries `confidence='high'` (property test over a synthetic mixed frame) | C6 |
| T12 | floors flag but never drop: a below-floor row appears in both parquet and audit; changing a floor constant changes only `below_length_floor` | §8.1(1) |
| T13 | PIT: every output row's `filing_date`/`report_date` equal the DB's; no row's `filing_date` exceeds the F2 freeze `2026-08-31`; nothing sorts on `report_date` | HANDOFF §7 |
| T14 | **E1 regression**: re-extract 12 named E1 filings from cache and assert byte-identical text against `data/filings.parquet` for the anchor-MDA / anchor-RF / EX99 classes; the classes that legitimately change (`8K_BODY` slicing, stub-trigger widening) are enumerated in the test with their reason | R7/C13 — verified feasible in P0: **12/12 byte-identical today** |
| T15 | shard determinism + idempotence: `plan_shards` is a pure function of `(form, accession)`; two runs produce byte-identical shard files; deleting one `.done` recomputes exactly that shard; `--merge` refuses duplicate `(accession, section_type)` |C9 |
| T16 | audit arithmetic: `attempts == OK + FLAGGED + EXPECTED_ABSENT + FAIL`, and the per-filer rollup sums to the audit table | §7.3 |
| T17 | schema pin: exact column list and dtypes of both artifacts; `ticker` absent | C3 |
| T18 | edge-handler registry: every handler has a name, docstring and predicate; a handler that fires 0 times is reported DEAD; a fixture exercises each handler | C11 |
| T19 | dialect regexes: `Item 1(A).` normalises to `1A`; `appears on\npages` matches; neither change alters E1's TOC parsing on the E1 fixtures | C12 |
| T20 | prose-share uses `chunk.MIN_PROSE_WORDS` (imported, not re-declared) and `n_prose == 0 ⇒` the section is flagged for F4 visibility | C16 |
| T21 | the 12 named near-empty EX-99 selections (Ford `0000037996-19-000005`, MetLife `0001099219-23-000041`, PNC ×7, Cigna, Linde ×2) FAIL with `empty_after_extraction` — pinned by accession, so a future floor or reader change that silently rescues them breaks a test | §2.2, §8.1(3) |

Run scope: `test_extract_e2.py` only (F3 runs in parallel with the G1
repair campaign; do not run or edit other suites — the F2 coordination
discipline).

---

## 12. F4-scale re-derivation (a required F3 deliverable)

### 12.1 Method — exact, not estimated

Run **`chunk.py`'s own pure functions** over F3's real output. Do not
re-implement the packing rules; import `normalize_paragraph`,
`MIN_PROSE_WORDS`, `TARGET_WINDOW_WORDS`, `MIN_FLUSH_WORDS` and the home
tie-break. A small driver (`data/f3/p3_scale.py`) streams sections and
keeps only hashes + word counts + positions in memory, because the full
corpus is ~1 GB of text and `build_canonical_paragraphs` holds every
occurrence's text.

Report, per run: raw prose-paragraph count, canonical (deduplicated)
paragraph count, dedup rate, **chunk count**, chunks by `section_type`, by
stratum, and by era; plus the count of sections producing **zero** chunks.

### 12.2 The three window rules, run separately (they are not subsets)

Dedup homes are "earliest occurrence globally", so restricting the corpus
**changes which occurrence is home** and therefore the chunk count
non-linearly. Each rule is a separate full run:

| rule | filings (measured today) | what it loses |
|---|---|---|
| **W1 full window** 2015-07 → 2026-08 | 20,521 | nothing |
| **W2 member spell + 12-month pre-margin** | 13,886 (67.7%) | pre-margin history for trailing features; keeps IPO-late entrants |
| **W3 member spell only** | 11,403 (55.6%) | the trailing-feature margin, and the corpus's **only bankruptcy** — CIK 895126's two 8-K item-1.03 filings (2020-06-29, 2021-01-19) sit outside its spell (F2 §3.1). W3 is presented for completeness and is expected to lose the argument on that ground. |

Core-stratum-only counts are reported beside each (F4 labels core first,
extension deferred until G2 — `EXPANSION_PLAN` §8.3): core filings are
14,780 / 10,241 / 8,415 under W1 / W2 / W3.

### 12.3 The zero-chunk correction, and why it must be in the table

C16: `n_prose == 0 ⇒ n_chunks == 0` (97/97 in E1), and the zero-prose
share for earnings sections **triples** from E1's 4.6% to ~14.7% in the E2
sample. So chunk counts must be reported **twice**:

- **as-is** (chunk.py's current 40-word prose rule), and
- **reflowed**, under one documented variant (join text within block
  elements before line-splitting) applied to a seeded sample of ≥200
  sections and extrapolated with its sampling error stated.

The gap between those two numbers is F4's decision, not F3's. F3's job is
to hand it over measured rather than let F4 discover it as a missing 15% of
the earnings corpus.

### 12.4 Labeling-time translation (the number the owner cares about)

Chunks × measured student throughput. Use the **measured** 1,068 chunks/h
from the epoch-1 held-out eval (`finetune/runs/2026-08-21-eval-epoch1/`),
never the ~950 chunks/h paper band, and state which one is quoted. Report
hours and overnights for: W1 all, W1 core, W2 core, W3 core, each × (as-is,
reflowed). That 8-cell table plus §12.2's loss column is the complete
decision input for the member-spell-vs-full-window ruling.

### 12.5 What this deliverable is not

Not a re-chunk. F4 re-chunks for real, with new `chunk_id`s
(`EXPANSION_PLAN` §3.1). §12 writes no corpus artifact — only counts, into
`P3_qa.md` and `data/f3/f4_scale.csv`.

---

## 13. Items for the main session (none need the owner)

1. **The D2 external-document MD&A class** (C15): its size is measured in
   P3. If it is material, recovering it needs the filing's *other*
   documents, which are not cached and which `filing_documents` does not
   index for periodic forms — i.e. a bounded, one-time EDGAR fetch. That is
   an ingestion decision for the main session (F2's remit), with a measured
   count in hand; F3 will not fetch. Until then the class is FLAGGED and
   visible.
2. **Concurrency for the P2 run**: the segmentation supports N workers; the
   measured scaling says 2 is the sensible maximum. The main session
   chooses 1 or 2 when it launches the chain.

No owner decision is required by anything in this spec. The one judgment
that could have gone to the owner — whether to accept an 8/9-recall gate in
exchange for a 36% smaller flag list — is settled by the project's own hard
rule ("a section that extracts wrong is worse than one that fails loudly")
and is recorded as R1 rather than escalated.

---

## 14. What this spec deliberately does not do

- **No re-ingest, no change to `select_earnings_document`, no per-filer
  selection handler, no deletion of the 790 "extra" earnings filings.**
  H4 §7 rules all four out; F3 gates the population, it does not re-pick
  documents.
- **No new section types** (§2.1).
- **No change to `html_fragment_to_text`**, despite C16's finding — the
  E1 byte-identity pin and chunk.py's ownership of `MIN_PROSE_WORDS` both
  argue against it, and the decision is F4's with F3's numbers in hand.
- **No truncation of diluted release+supplemental documents** (§6).
- **No universal "prefer the exhibit that reads like a release" scorer**,
  no clever universal regex. Per-dialect handlers, small and named (R8).
- **No live GETs, anywhere, at any stage of F3.**
