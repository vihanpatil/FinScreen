# S6 segment-1 EX-99 diagnosis + fix (data-engineer, 2026-08-24)

Answers the brief at `data/f2/status/S6_seg1_ex99_brief.md`. Segment 1
ingested cleanly and exited 1 on its own designed guard: **400 of 10,569
earnings 8-Ks (3.78%) `earnings_doc_unresolved`**, above F2_SPEC §4.4's 1%
FATAL ceiling.

**Headline:** the 400 are two causes, neither of them a selection-policy
gap on a real earnings exhibit. **336 (84%) are transient EDGAR 5xx /
timeouts that `edgar_client._get()` never retried**; **64 (16%) are one
benign filer dialect** — a single-document earnings 8-K with no exhibit at
all — that the index parser's `>=3 row` completeness heuristic rejected as
a broken parse. Both are fixed. Offline replay over the cached indices for
all 400 failing accessions plus all 10,169 successful ones: **0 parse
failures, 0 changed document selections**. Expected post-fix rate
**0.00%**; worst realistic case ~0.1%. **No recalibration of the 1%
ceiling is proposed — it worked.**

Everything below was derived with **zero live network GETs**, from
`universe_validation_problems` (read-only), `data/f2/ex99_selection_audit.csv`,
`data/f2/s6_segment1_metadata.log`, and `data/raw/filing_index/`.
`data/filings_metadata_e2.db` was not written to.

---

## 1. Failure taxonomy — all 400, by cause

| # | Cause | n | of 400 | of 10,569 | Brief's class |
|---|---|---|---|---|---|
| A | Transient EDGAR `503 Service Unavailable`, no retry arm | 309 | 77.3% | 2.92% | (c) infrastructure |
| B | Transient read timeout (30 s), no retry arm | 27 | 6.8% | 0.26% | (c) infrastructure |
| C | Single-document 8-K rejected by the `>=3`-row parse guard | 64 | 16.0% | 0.61% | (b) benign → `8K_BODY` |
| — | **(a) parser/selection gaps on a real earnings exhibit** | **0** | **0%** | **0%** | — |
| — | Selection policy returned no document | 0 | 0% | 0% | — |

The DB slice holds 401 rows for `check_name='earnings_doc_unresolved'`
(400 WARN + the 1 run-scope FATAL); the 400 WARNs are fully accounted for
above with no residue.

### 1.1 Classes A + B — transient, not a corpus property

Five independent lines of evidence, all offline:

1. **Cache split is perfectly clean.** 0 of the 336 A/B accessions have a
   cached filing index (a failed fetch is never written to cache); **all
   64** class-C accessions do. `data/raw/filing_index/` holds exactly
   10,233 `.html` files = 10,569 − 336. Nothing is cached under an
   alternate CIK key (checked all 10,233).
2. **Zero 429s in 10,841 GETs.** We were never rate-limited in EDGAR's
   documented sense. The run averaged ~3.4 req/s against the client's
   10 req/s cap — this was not us over-driving the limiter.
3. **Uniform in time.** Bucketing the log into twentieths, 503s appear in
   every bucket from 5% to 100% at 9–32 per bucket. There is no outage
   window; it is a flat background rate.
4. **Uniform across filers.** 163 of 243 CIKs took at least one, maximum
   6 for any single CIK, against per-CIK volumes up to 47 — a ~3.2%
   per-request Bernoulli scatter, not a property of any URL or filer.
5. **URL shapes are canonical** and identical to the 10,233 that
   succeeded (`/Archives/edgar/data/{cik}/{nodash}/{accession}-index.html`).

`_get()` retried HTTP 429 and nothing else: a 503 fell through to
`raise_for_status()` and a timeout escaped as `requests.ReadTimeout`, so
every one became a permanent hole in the corpus.

### 1.2 Class C — one benign dialect, uniformly

All 64 have **exactly the same shape**, with no variation at all:

- 2 parsed index rows, doc types `('8-K', '')` — the 8-K body plus the
  "Complete submission text file" row.
- 2 index data rows, 2 parsed: **nothing was dropped**.
- EDGAR's own Filing Detail header declares `Documents: 1`.

These are earnings 8-Ks that carry the release **in the 8-K body** with no
EX-99 exhibit. `select_earnings_document()` rule 5 handles exactly this
(`8K_BODY` fallback) — but it never ran, because
`parse_index_html_documents()` raised first.

Three further confirmations that this is benign, not a missed exhibit:

- **The guard's real failure mode never fired.** Its docstring says it
  exists to catch "EDGAR serving non-hyperlinked rows … which this
  href-required parse would otherwise silently drop". Measured across all
  10,233 cached indices, that dropped-row condition fired **0 times**; the
  `>=3` proxy fired **64 times**. The threshold caught no real broken
  parse — it only ever mislabelled legitimately sparse filings.
- **Same filers, same behaviour, already resolving.** HAL (45012), PXD
  (1038357), IBM (51143), PYPL (1633917), EOG (821189) and CXO (1358071)
  each already carry **high-confidence `8K_BODY` selections** in the
  pre-fix audit, on their *other* earnings 8-Ks.
- **The threshold was an accidental proxy for filing vintage.** All 64
  failures are 2015–2019 (2018:18, 2016:16, 2019:14, 2017:11, 2015:5).
  Of the 152 exhibit-less 8-Ks that *did* resolve pre-fix, all 130 from
  2020 onward had ≥3 rows — because the iXBRL cover-page mandate adds
  `EX-101.*`/XML rows to nearly every post-2020 8-K index. `>=3` was
  really asking "does this index have iXBRL data-file rows", which is
  true for modern filings and false for a lean pre-2020 8-K.

### 1.3 Class C by CIK (24 CIKs)

| CIK | Name | n |
|---|---|---|
| 45012 | HALLIBURTON CO | 17 |
| 1038357 | PIONEER NATURAL RESOURCES CO | 16 |
| 51143 | INTERNATIONAL BUSINESS MACHINES CORP | 4 |
| 1633917 | PayPal Holdings, Inc. | 3 |
| 49071 | HUMANA INC | 2 |
| 701221 | Cigna Holding Co | 2 |
| 1156039 | Elevance Health, Inc. | 2 |
| 1578845 | Allergan plc | 2 |
| 32604 · 72903 · 72971 · 97476 · 100885 · 766704 · 821189 · 849399 · 1099219 · 1163165 · 1358071 · 1373715 · 1390777 · 1467858 · 1564408 · 1596532 | (1 each) | 16 |

Classes A + B are spread over **163 CIKs** (max 6 each) and are not
listed per-CIK here: they are a property of the network, not of any filer.

---

## 2. What was fixed

Five changes, all small and named. Nothing weakens the 1% check.

### 2.1 `ingest_metadata.parse_index_html_documents()` — exact completeness

`len(out) < 3` is replaced by the invariant the guard's own docstring
describes: **no index data row may be dropped**. Every row with ≥5 `<td>`
cells is counted; if any lacks a document hyperlink (and so would vanish
from the parse) it raises, naming the offending rows. A separate raise
covers "0 rows parsed". The `primary_document` assertion is unchanged.

This is a *tightening*, not a loosening: the new check is exact where the
old one was a proxy, and it still fails loudly on the real failure mode
(pinned by `test_a_row_with_no_hyperlink_is_still_a_parse_failure`).

### 2.2 `edgar_client._get()` — retry the transient failures

HTTP 5xx and `requests.Timeout`/`ConnectionError` now retry on the same
exponential backoff as 429 (`max_retries=5`, 1→2→4→8→16 s, honouring
`Retry-After`). **403 and every other 4xx are still never retried** — a
403 is a User-Agent/fair-access problem, and a bad URL does not improve.
**Exhausting the retries still raises**, so §4.4's accounting still counts
the case: this makes transient failures rare, not silent. Rate limiting
and the User-Agent header are untouched; no rate change was needed
(evidence §1.1 item 2).

### 2.3–2.4 Two named selection dialects (confidence only, never the pick)

The brief flagged the 72 low-confidence CIKs as filer-dialect-shaped. They
are, and the four biggest clusters were the policy crying wolf on picks it
was never actually unsure about — the exact failure HANDOFF §4 already
paid for once ("a verifier that cries wolf on every healthy run is worse
than no verifier").

- **`_canonical_exhibit_type()` — zero-padded exhibit sub-numbers.**
  Intuit (53), Gen Digital (43), Xcel (43), Southern (40), Eversource
  (15), Sempra (4) and others type exhibit 99.1 as `EX-99.01`. That IS
  exhibit 99.1. Only a *leading* zero is stripped, so `EX-99.10` is never
  conflated with `EX-99.1`; anything that is not `EX-99.<digits>` (J&J's
  `EX-99.2O`, Coca-Cola's `EX-99.0`) is returned untouched and stays
  unrecognised.
- **`_drop_pdf_renditions()` + `_best_by_description()` in a shared
  `resolve_duplicates()` ladder** for the ">1 row of the same exhibit
  type" arms. Ford files each release twice as `EX-99` (`.htm` + `.pdf`),
  CAT and ITW do the same under `EX-99.1` — one exhibit, two renditions,
  and `extract.py` has no PDF reader, so the HTML rendition is the only
  usable one anyway. Where renditions don't explain it, the description
  scorer already used by rule 4 is tried (Eversource types the release,
  the financial report and the slide deck all as bare `EX-99`). Only if
  neither explains it does it fall to lowest-seq at low confidence **and
  print the CANARY** — which now means what it says.

Rule 4's inline scoring was folded into `_best_by_description()`; its
behaviour is unchanged.

### 2.5 `print_ex99_audit_report()` — name the reclassified benign class

Per the brief, a benign class that stops being counted as a failure must
be **counted and named in the run summary, not dropped**. The report now
prints, whenever any exist:

```
  of which 8K_BODY fallbacks: 216 filing(s) across 62 CIK(s) -- earnings
  8-Ks that carry the release in the 8-K body with no EX-99 exhibit at
  all. A benign, named class, still on the §4.4 read list below.
```

Those 64 filings do **not** disappear: they become counted `8K_BODY`
selections in `ex99_selection_audit.csv`, and `8K_BODY` is already a
§4.4 manual-read trigger, so all 12 newly-appearing CIKs land on the
worklist.

### Files touched

| File | Change |
|---|---|
| `/Users/vihanpatil/personal/projects/FinScreen/ingest_metadata.py` | parse guard recalibrated; `_canonical_exhibit_type` / `_drop_pdf_renditions` / `_best_by_description` / `resolve_duplicates`; audit report names the 8K_BODY class |
| `/Users/vihanpatil/personal/projects/FinScreen/edgar_client.py` | `_get()` retries 5xx + timeouts; 403/4xx still never retried |
| `/Users/vihanpatil/personal/projects/FinScreen/test_ingest_metadata_scale.py` | +23 tests (dialects, guard, retry arm, benign-class reporting) |
| `/Users/vihanpatil/personal/projects/FinScreen/data/f2/fixtures/build_fixtures.py` | reproducible filing-index fixture copier (`INDEX_CASES`) |
| `/Users/vihanpatil/personal/projects/FinScreen/data/f2/fixtures/filing_index_CIK*.html` | 6 new byte-identical cached-index fixtures |

Not touched: `data/filings_metadata_e2.db`, `F2_PROGRESS.md`,
`EARNINGS_DOC_UNRESOLVED_FATAL_RATE`, any E1 artifact.

---

## 3. Offline replay — the post-fix estimate

`ingest_metadata`'s real parser and real selection policy, run over the
cached index of **every** earnings 8-K in the DB. No network, no DB write.

**Deterministic (parser/policy) share — measured, not modelled:**

| Result | n |
|---|---|
| Cached indices replayed | 10,233 |
| Parse or selection failures after the fix | **0** |
| Previously-failing accessions now resolved | **64** → all `8K_BODY` / high |
| **Changed document selections on the 10,169 previously-successful filings** | **0** |

Zero filename changes is the load-bearing safety result: §2.3–2.4 move
confidence labels only, never a pick.

**Confidence movements (all on filings that already resolved):**

| Before | After | n | Why |
|---|---|---|---|
| low | high | 204 | 179 zero-padded `EX-99.01` (Intuit/Xcel/Gen Digital/Southern), 13 HTML+PDF renditions (Ford 11, CAT 2), 12 others |
| medium | high | 84 | Cadence 42 + Synopsys 42 — `EX-99.01` press release beside an `EX-99.02` CFO commentary; same file, now identified by type instead of by keyword |
| low | medium | 15 | Eversource's three bare `EX-99` exhibits, separated by description |

Each of the 288 was inspected; every one keeps the same file.

**Transient share — modelled, and stated as such.** The 336 A/B
accessions have no cached index, so they *cannot* be replayed offline;
the main session's cache-warm re-run re-fetches exactly those 336 (plus
0 for the 10,233 already cached). At the measured 3.2% per-request
failure rate:

- **without** the retry arm: expectation ≈ 336 × 0.032 ≈ **11 residual
  failures (0.10%)** — already under the ceiling, but 11 real holes;
- **with** the retry arm (6 attempts): expectation ≈ 336 × 0.032⁶ ≈
  **0**, assuming per-request independence, which the uniform-in-time and
  uniform-across-filer scatter (§1.1 items 3–4) supports.

| Scenario | Unresolved / 10,569 | Rate | vs 1% ceiling |
|---|---|---|---|
| Pre-fix (segment 1, attempt 1) | 400 | 3.78% | **FATAL** |
| Parser fix only, no retry arm | ~11 | ~0.10% | clears |
| **Both fixes (expected)** | **0** | **0.00%** | **clears** |

### Projected §4.4 audit (over the 10,233 replayable filings)

| section_type / confidence | before | after |
|---|---|---|
| `EX99_PRESS_RELEASE` / high | 9,683 | 9,971 |
| `EX99_PRESS_RELEASE` / medium | 84 | 15 |
| `EX99_PRESS_RELEASE` / low | 250 | **31** |
| `8K_BODY` / high | 152 | **216** |

(The 336 re-fetched filings add to these on the real re-run; they are
overwhelmingly ordinary `EX-99.1` filings.)

`check_ex99_sector_coverage()` on the projected audit: **0 problems** —
all 8 sectors keep ≥1 high-confidence `EX99_PRESS_RELEASE`. Inline
CANARY lines drop **39 → 10**.

### The §4.4 manual read gets dramatically better, not smaller

CIK count barely moves (**72 → 71**: low-confidence CIKs 26 → 10, but
`8K_BODY` CIKs 50 → 62 as the 64 recovered filings surface). What changes
is *what the capped top-20 read spends itself on*:

- **Before**, the 20-filer cap was consumed by 244 low-confidence filings,
  179 of them the zero-padded dialect needing no reading at all.
- **After**, only 31 low-confidence filings remain across 10 CIKs, so the
  top-20 covers **every** low-confidence filer plus 10 `8K_BODY` filers.

The 10 CIKs still low-confidence — these are the real read, and they are
correctly flagged rather than guessed at:

| CIK | Name | n | Dialect |
|---|---|---|---|
| 200406 | JOHNSON & JOHNSON | 18 | `EX-99.15` / `EX-99.2O` (letter O) — unrecognised on purpose |
| 1032208 | SEMPRA | 4 | two bare `EX-99`, numbering only in the description |
| 1045609 | Prologis | 2 | same |
| 80661 | PROGRESSIVE | 1 | `EX-99.0` |
| 106535 | WEYERHAEUSER | 1 | two bare `EX-99` |
| 732717 | AT&T | 1 | — |
| 766704 | WELLTOWER | 1 | two bare `EX-99` |
| 1035267 | INTUITIVE SURGICAL | 1 | — |
| 1045810 | NVIDIA | 1 | — |
| 1364742 | BlackRock | 1 | — |

The remaining **51 CIKs are still uncovered by the cap** and must be
reported as such in the F2 report, exactly as the code already prints.

---

## 4. Tests

| Suite | Result |
|---|---|
| `test_ingest_metadata_scale.py` (targeted) | **83 passed** (60 → 83, **+23 new**) |
| `test_ingest_metadata_universe.py` (S2's suite) | **45 passed** |
| `test_edgar_client_companyfacts.py` | **7 passed** |
| Full suite | **635 passed / 5 skipped / 2 failed** |

The 23 new tests are offline and socket-free: 6 byte-identical cached-index
fixtures (one per named handler, **plus a negative case** — J&J's
unrecognised types must STAY low-confidence, so the handlers can never
quietly grow into "call everything high"), 2 synthetic parse-guard cases,
7 retry-arm cases (503 retried, timeout retried, persistent 503 and
persistent timeout still raise, 403 and 404 never retried, 429 unchanged),
and 2 benign-class reporting cases. Fixtures are regenerated by
`python3 data/f2/fixtures/build_fixtures.py` and pinned byte-identical to
`data/raw/filing_index/`.

### ⚠️ The 2 full-suite failures are PRE-EXISTING and unrelated — but they block the gate

`test_ingest_prices.py::test_price_ticker_map_resolves_212_and_censors_32`
and `::test_real_census_reconciliation_matches_the_preregistration`.
**Not caused by this work** — `ingest_prices` imports only
`CORPUS_WINDOW_START/END` and `load_universe` from `ingest_metadata`, uses
`price_client`'s own `_get()`, and touches none of the changed functions.

Root cause, measured: **CIK 4904 (American Electric Power) lost its ticker
in `submissions.json` between S5's run and segment 1's.** S5 ran 12:22 and
resolved AEP from `submissions.json` (its map row says "absent from
company_tickers.json; absence never censors"). Segment 1's 24 h-TTL
refresh at **12:56:30** re-fetched a full-size (161 KB) document whose
`tickers` and `exchanges` arrays are now **empty** — while
`company_tickers.json` (refreshed the same second) *does* carry
`4904 → AEP`. EDGAR swapped which source holds the mapping. Because
F2_SPEC §9.1 item 7 ratified **submissions-only** CIK-verified resolution,
AEP now censors: **212 resolved / 32 censored → 211 / 33**.

This is an owner/main-session call, not mine to make (it touches a
ratified rule and the evidenced-override mechanism), and it is outside
this brief. Flagging it because **S6's "full suite green" gate cannot pass
until it is ruled on**. It may also self-heal on a later refresh — worth
re-checking before ruling.

---

## 5. On the 1% ceiling — NO recalibration proposed

The taxonomy does not support touching it. The ceiling did precisely what
it was designed to do: 3.78% "is a selection-policy or index-format
problem across filers, not per-filing noise" was a **correct** diagnosis,
and it surfaced two genuine defects — a completeness heuristic
mis-calibrated for the E2 corpus, and a missing retry arm that was
silently punching ~3% holes in every EDGAR walk this project runs. Neither
would have been found by a looser threshold. Post-fix the expected rate is
0.00%, so the ceiling is not binding on healthy behaviour either.

`EARNINGS_DOC_UNRESOLVED_FATAL_RATE` is unchanged at 0.01, and the
`>` (not `>=`) semantics are unchanged.

**One observation, offered without a recommendation:** the check pools two
different kinds of failure — deterministic parse/selection failures (a
corpus property) and transient fetch failures (a network property). With
the retry arm the transient residual should be ~0, so pooling costs
nothing today, and splitting the check would add machinery for no measured
benefit (lazy-elite). Recorded only so that if a future run FATALs on a
bad EDGAR day, the reader knows the two arms are pooled by choice.

---

## 6. What the main session should do next

1. **Re-run segment 1 exactly as the runbook has it** — the command in
   `S6_runs.md` row 1 is unchanged and idempotent:
   `caffeinate -is python3 ingest_metadata.py --stage metadata --db data/filings_metadata_e2.db > data/f2/s6_segment1_metadata.log 2>&1`
   Cost: **~336 index GETs** (10,233 cached indices are hits) plus 244
   submissions only if the 24 h TTL has expired since 12:56 on 2026-08-24
   — if it has and you want the cheap path, add
   `--cache-max-age-hours 168` (accepts the corpus as of the cached
   fetch, which is correct for a fixed window).
2. **Verified idempotency:** `upsert_with_exhibit_sql` uses
   `ON CONFLICT(accession_number) DO UPDATE SET earnings_doc_*=excluded.*`,
   so all 400 previously-NULL rows and all 288 confidence-changed rows are
   corrected in place; `write_validation_problems()` deletes the
   `(run_date, stage='metadata')` slice before rewriting, so the stale 400
   WARNs + 1 FATAL clear themselves.
3. **Expect in the new log:** `unresolved (counted): 0 (0.00%)`,
   `8K_BODY high` ≈ 216, `EX99_PRESS_RELEASE low` ≈ 31, ~10 CANARY lines,
   `CIKs needing the §4.4 manual read` ≈ 71 with ~51 uncovered by the cap.
   Anything materially different is a finding.
4. **Rule on the AEP price-map drift (§4)** before the S6 full-suite gate.
5. The §4.4 manual read itself is unchanged in scope and still owed —
   now worth doing, because the top-20 finally lands on real ambiguity.

## 7. Resume state

Nothing is partial. Code + tests are complete and green (except the two
pre-existing price failures in §4, which are not this work's). If this
session died before the main session read this file: the fixes are on disk
in the five files listed in §2, the replay harness used for §3 was a
throwaway in the session scratchpad (regenerate from §3's description — it
is ~40 lines over `data/raw/filing_index/`), and no state outside those
files was mutated.

---

## CORRECTION — 2026-08-24 (dated, appended; the analysis above is unrewritten)

**This document's "0 genuine selection failures" verdict, and the "benign
class" framing of the `8K_BODY` tail, are SCOPED TO THE 400 FILINGS EXAMINED
and do not hold corpus-wide.** Ruled after the S7 red-team (finding **B1**,
with **B2** naming this overgeneralization specifically);
`F2_PROGRESS.md` §5, dated 2026-08-24.

**What the claim actually rested on.** The examination covered 400 filings and
found no genuine selection failure among them. The generalisation to the whole
`8K_BODY` class rested on a prior — that ten read filings had zero `EX-99`
strings in their index — never on a query over the class.

**What one offline query over the class shows.** Of the **225** `8K_BODY`/high
selections, **20 still hold an unselected non-body candidate document row**,
and **15 of those rows are release-shaped**. In those filings the stored
"earnings document" is the SEC Form 8-K **cover page**, whose own Item 2.02
text says the release is elsewhere — read directly in the stored bytes:

- Aon `0001628280-15-005672` (2,260 chars): *"A copy of the Press Release is
  attached hereto as Exhibit 99.1."*
- Illumina `0001110803-16-000185` (2,827 chars): *"The full text of the
  Company's press release is attached hereto as Exhibit 99.1."*
- HPE `0001645590-17-000006` (4,231 chars): *"A copy of the press release is
  attached hereto as Exhibit 99.1."*

**So the corrected reading of this document is:** 0 genuine selection failures
**among the 400 examined**; the unread remainder of the `8K_BODY` class is
**where the defect lives**, not a low-risk residual. Nothing in the analysis
above is withdrawn on its own terms — the sampling did not cover this class,
and the conclusion was stated more broadly than the sample supports.

**Disposition.** The root cause (an unconditional `8K_BODY` fallback that never
checked for unselected candidates) is fixed in `ingest_metadata.py`; see
`data/f2/F2_SPEC.md` AMENDMENT **A9** and
`data/f2/status/S3_metadata_documents.md` §12.8. Corpus effect: **15 pick
changes — 11 resolved to a real press release, 4 newly UNRESOLVED** (counted
against the 1% ceiling at 0.038%, WARN only).
