# P1 completion report — F3 implementation + offline tests

**Stage:** P1. **Agent:** extraction-qa-engineer (Opus). **Date:**
2026-08-26. **Status: DONE.** Brief: `F3_PROGRESS.md` P1 row; spec:
`data/f3/F3_SPEC.md` (P0, APPROVED by the main session 2026-08-26).

**Network: ZERO live GETs**, and now structurally so, not by promise —
`extract.py` no longer imports `EdgarClient` at all on the F3 path
(`grep EdgarClient extract.py` returns three docstring mentions and no
import). Every document read came from `data/raw/documents/`; every
metadata row from `data/filings_metadata_e2.db` opened `mode=ro`.

**E1's frozen artifacts were not touched.** `data/filings.parquet`
(mtime Aug 10 17:09), `data/filings_metadata.db` (Aug 18 12:08) and
`data/labels.parquet` (Aug 11 02:30) are unchanged; they were read only.
`extract.py` now refuses them by name (`assert_not_e1_path`, exit 2,
tested). `F3_PROGRESS.md` was not edited.

---

## 1. Files touched

| path | what |
|---|---|
| `extract.py` | **modified in place** (+1,581 / −193; 2,337 lines, 69 functions). The only pipeline file changed. |
| `test_extract_e2.py` | **new**, 113 tests, offline |
| `data/f3/fixtures/build_fixtures.py` + 4 real-byte fixtures | new (536 KB total) |
| `data/f3/p1_calibrate/p1_floor_gap_read.py` + `floor_gap_ex99_50_249.csv` | new — the EX-99 floor-raise hand-read evidence |
| `data/f3/p1_calibrate/p1_supplemental_markers.py` + `supplemental_marker_calibration.csv` | new — the §6 marker calibration |
| `data/f3/p1_calibrate/p1_e1_regression.py` + `e1_regression_884.csv` | new — the corpus-scale E1 byte-identity regression |
| `data/f3/status/P1_impl.md` | this report |

`chunk.py` was **not** edited (only imported, for `MIN_PROSE_WORDS`).
No other suite was run or edited (F3_SPEC §11's coordination rule); no
other test file imports `extract`, so `test_extract_e2.py` is the complete
test scope for the change.

Shipped `extract.py` sha256 `b9acceea8377…`, `test_extract_e2.py`
sha256 `b63e35930b4c…` — the hashes the 113/113 run below was made against.

---

## 2. Test counts

**113 tests, 113 pass, 0 fail, 0 skip, no warnings** (33 s).
`python3 -m pytest test_extract_e2.py -q`

Coverage of the spec's T1–T21 (several spec items are more than one test):

| spec test | tests | headline pin |
|---|---|---|
| T1 | 2 | `CacheMiss` raised; `edgar_client` poisoned in `sys.modules` and never touched; the cache key rule matches `EdgarClient.get_archive_document` byte-for-byte |
| T2 | 1 | end-to-end run records `network_gets == 0`; 3 deliberately-missing documents produce 3 `cache_miss` FAIL rows, no fetch |
| T3 | 4 | `--db data/filings_metadata.db` and `--out-parquet data/filings.parquet` both exit 2 |
| T4 | 3 | parse-once == a reference double-parse on two real filings; the lazy full-text is computed at most once |
| T5 | 4 | gate levels; **all 9 H4 C-rows flagged**; the census reproduces 1,519/10,567 |
| T6 | 2 | the narrowed variant would have dropped the ICE/Bakkt row; the signature never suppresses |
| T7–T9 | 4 | Humana slice = `text[1269:]` to EOD, `item202_block_words == 8`, thin flag fires; missing 2.02 → whole document; EX-99 never sliced; >4,000-char prefix flagged |
| T10 | 8 | all three real phrasings enter the resolver on word count alone; external vs same-document reason codes; US Bancorp's real bytes |
| T11 | 3 | every FLAGGED reason code ⇒ confidence ≠ high (parametrised over the enum); a flag can't be hidden by precedence |
| T12 | 2 | floors flag but never drop — text byte-identical under a 10⁹-word floor |
| T13 | 3 | dates carried through unchanged; nothing ≥ the F2 freeze; nothing in the F3 path sorts on `report_date` |
| T14 | 14 | 12 named E1 rows byte-identical + all 9 E1 resolved stubs byte-identical + the changing classes named |
| T15 | 8 | shard determinism, idempotent resume, one-`.done`-deleted recompute, `--limit` can't satisfy a full run, duplicate refusal, no `.tmp` survivors, **34 shards on the real corpus** |
| T16 | 5 | attempts == status sum; rollup reconciles; closed enum; all five artifacts; manifest |
| T17 | 1 | exact column lists and dtypes for both artifacts; `ticker` absent |
| T18 | 4 | registry empty-and-why; handler invariants; fired-counts; DEAD detection |
| T19 | 12 | `Item 1(A).` → `1A`; E1's bare-number and split-row dialects unchanged; `appears on\npages` |
| C14 | 4 | `head_foreign_item` fires on Tesla's Item-3 slice, does **not** fire on ICE's `1(A)` dialect, and the known miss is pinned as a miss |
| T20 | 3 | `prose_stats` reads `chunk.MIN_PROSE_WORDS` live and agrees with `chunk.extract_prose_paragraphs` |
| T21 | 14 | the 12 named near-empty EX-99 selections FAIL `empty_after_extraction`; the two named short-release survivors clear the raised floor; before/after floor counts |

---

## 3. Deviations from spec

**None in substance.** Four items where the spec was silent, internally
inconsistent, or contradicted by measurement are recorded here in full,
because "a recalibration is a documented, evidence-backed change" applies
to spec readings too:

1. **`--out-parquet` added to the CLI.** C1's CLI sketch has no output-file
   argument, but §7.1 puts the corpus at `data/filings_e2.parquet`, which is
   *outside* `--out-dir data/f3`. C1's E1-refusal clause ("any `--out-dir`
   resolving to `data/filings.parquet`") can only be about an output file,
   since a directory cannot resolve to a file. Implemented as
   `--out-parquet` (default `data/filings_e2.parquet`), with
   `assert_not_e1_path` applied to the DB, the corpus parquet and the audit
   parquet. **Additive, not a change of behaviour.**

2. **`earnings_item202_prefix_large` is a reason code, not only a flag.**
   §5 rule 6 names it as a FLAG; C5's "closed enum" table omits it. Leaving
   it flag-only would let a row be FLAGGED with `reason_code = 'ok'`, which
   breaks C5's own invariant. It is placed in the earnings block of the
   precedence list. This is the one place P1 extends C5's table, and it is
   the direction that preserves the spec's invariants.

3. **The stub resolver also runs on the heading-regex path.** C7 says "any
   `(10-K, MDA)` extraction under `MDA_STUB_WORD_CEILING` enters
   `resolve_incorporated_by_reference_mda`", while C7's own evidence table
   lists **US Bancorp `0001193125-17-053947` as `heading_regex/low`** — a
   stub that the anchor branch never sees. Implemented literally: the
   resolver runs on both paths; when there is no usable anchor TOC the
   anchor-hop strategy is skipped (it has nothing to hop through) and only
   the text heuristic runs. Without this, US Bancorp would have come out
   `below_length_floor`, not a stub code, and T10 would have been untestable
   on one of its three named rows.

4. **T20's "n_prose == 0 ⇒ the section is flagged" is implemented as
   *recorded*, not as a new flag.** C16 says F3 *measures* prose share and
   explicitly does not change behaviour for it; C5's enum has no
   zero-prose code. Adding one would set `FLAGGED` on ~14.7% of earnings
   sections and, through C6, strip `high` confidence from all of them — a
   large unspecified consequence. `n_prose_paragraphs` and
   `prose_word_share` are columns on every row of both artifacts, which is
   what makes the class visible to F4. Flagged here so P3/P4 can overrule.

Two consequences of shipping C6 literally, surfaced rather than smoothed:

- **The population gate downgrades confidence.** `earnings_population_gate`
  is a FLAGGED code, so C6 turns `high` into `medium` for every multi-cell
  earnings row — **1,519 rows corpus-wide (14.4% of earnings)**. That is
  the spec as written (R3: "a flagged row may never carry
  `extraction_confidence='high'`"), but note it conflates *which document
  was picked* with *how well it extracted*. The `reason_code` carries the
  distinction; P3's triage reads that, not the confidence label.
- **Downgrade rule:** a FLAGGED row's `high` becomes `medium`, one rule, no
  per-code special cases. The spec requires only "≠ high".

---

## 4. What was measured at P1 (nothing below is asserted without a number)

### 4a. E1 regression at corpus scale — 880/884 byte-identical

`data/f3/p1_calibrate/p1_e1_regression.py` re-extracted **all 884** rows of
E1's frozen `data/filings.parquet` through the shipped code:

| E1 extraction_method | byte-identical |
|---|---|
| `anchor` | **544 / 544** |
| `incorporated_by_reference_resolved` | **9 / 9** |
| `whole_document` | 327 / 331 |
| **total** | **880 / 884** |

The **only four differences are the four `8K_BODY` rows** — BAC
`0000070858-24-000006` (1,412 → 665 w), CVX `0000093410-24-000002`
(1,603 → 1,297), CVX `0000093410-26-000108` (2,004 → 1,700), GS
`0000886982-26-000004` (2,643 → 2,225) — i.e. exactly R2's intended
cover-page removal, and two of the four also raise
`earnings_item202_block_thin`. **No `anchor` or `EX99` row changed by a
single byte.** The E1-era 884 rows re-classify as 858 OK / 26 FLAGGED
under the new taxonomy (12 `below_length_floor`, 9 `head_keyword_absent`,
3 `earnings_supplemental_diluted`, 2 `earnings_item202_block_thin`).

### 4b. The four P0-named stub rows are all fixed

| filing | filer | E1 today | F3 |
|---|---|---|---|
| `0000086521-17-000017` | Sempra 2017 | 43 w, **anchor / HIGH** | `mda_stub_external_document`, FLAGGED, low |
| `0001193125-17-053947` | US Bancorp 2017 | 50 w, heading_regex / low, no stub reason | `mda_stub_external_document`, FLAGGED, low |
| `0000019617-17-000314` | JPMorgan 2017 | 55 w, **anchor / HIGH** | **RESOLVED to 59,855 words of real MD&A** (`mda_stub_resolved`, medium) |
| `0001645590-19-000044` | HPE 2019 | 102 w, **anchor / HIGH** (a wrong slice) | `mda_stub_unresolved_same_doc` + `below_length_floor` + `head_keyword_absent`, FLAGGED, low |

A fifth, not in P0's list, surfaced while validating: **Nucor
`0001193125-18-064018`** — 39 words, "incorporated by reference to Nucor's
2017 Annual Report to Stockholders" → `mda_stub_external_document`. Under
E1's rules this was `anchor/high`. The D2 class is real and larger than
P0's two examples; **P3 censuses it** before the main session's fetch
decision (F3_SPEC §13.1).

### 4c. EX-99 floor raise 50 → 250: the hand-read, in the open

Rule 8.1(2) requires the measured distribution, a hand-read of the gap, the
named rows that must still fail, and before/after counts. All four:

- **Distribution** (all 10,357 EX-99 selections): p0.5% 243 w, p1 553 w,
  p5 1,567 w, median 5,194 w.
- **Gap hand-read: all 41 rows in [50, 250) words were read individually**
  (`p1_floor_gap_read.py`; text in `floor_gap_ex99_50_249.csv`). What I
  actually read, by class:
  - **16 AbbVie** "Guidance Including the Impact of Acquired IPR&D and
    Milestones Expense" exhibits (109–170 w) — a single EPS-guidance
    reconciliation table, substantive but ~zero prose; they will produce
    **zero labeling chunks**. Flag correct.
  - **7 Southern Co** "Mississippi Power / Kemper County IGCC Project
    Monthly Status Report" exhibits (184–216 w) — **wrong-population
    documents**: monthly regulatory construction reports, not earnings
    releases. Flag clearly correct.
  - **11 Tesla** vehicle production & delivery releases (122–220 w) —
    **genuine short disclosures of exactly the class H4 protected.** Named
    here as the flag's known false-alarm class. They are flagged, never
    dropped (R3), and they sit below the 276-word row H4 named.
  - **1 Tesla** `0001564590-18-023716` (67 w) — an internal **e-mail from
    Elon Musk to employees** filed as EX-99.1. Not a results release at all.
  - **2 Abbott** recast comparable-sales tables (234 / 245 w), **1 Danaher**
    investor-deck slide (162 w, F2 §5's named deck class), **1 Digital
    Realty** garbled chart fragment (108 w), and **1 Freeport-McMoRan**
    `0000831259-24-000026` — **mojibake**: 6,470 chars of font-encoded
    garbage (`! "#$%&'() *+) ,-./`). A **new named class** for P3 to census;
    the floor catches it only incidentally.
  - Net: **29 of 41 (71%) are wrong-population, table-only or garbled;
    11 of 41 are genuine-but-thin Tesla P&D releases; 1 is an employee
    e-mail.**
- **Named rows that must survive, both verified above 250 and unflagged:**
  Tesla Q1-22 P&D `0001564590-22-013264` = **276 w**; KKR monetization
  update `0001140361-19-006520` = **384 w**. H4's "a floor above ~400 words
  fails both" is respected with margin. *(H4's other KKR row,
  `0001140361-20-008805`, is an `8K_BODY` at 2,189 w whole / 1,853 w
  post-slice — comfortably above the unchanged 500-word `8K_BODY` floor;
  it is flagged by `earnings_item202_block_thin` (13-word 2.02 block),
  not by any floor.)*
- **Before → after**, stated both ways because the two differ:
  - counting all selections (F3_SPEC §8.3's framing): **12 → 53** of 10,357.
  - counting **corpus rows only** (the 12 are FAIL rows that never enter
    the corpus): **0 → 41** rows carrying `below_length_floor`.
  - **Corpus membership is unchanged either way.** A floor is a flag.
- Every other floor and `MDA_STUB_WORD_CEILING` are **E1's values,
  untouched**, pending P3's read of the corpus-wide
  `length_distribution.csv` (§8.2 step 1).

### 4d. §6 supplemental-marker calibration (the spec required this at P1)

`p1_supplemental_markers.py`, 1,613 documents read (seeded 1,500-row EX-99
sample, seed 20260826, plus every Simon Property / AvalonBay / Prologis row):

| marker | hits | flagged (share ≥ 0.5) |
|---|---|---|
| `supplemental information` | 92 | 41 |
| `supplemental financial information` | 46 | 14 |
| `supplemental data` | 12 | 1 |
| `supplemental operating` | 8 | 0 |
| `supplemental package` | **0** | 0 → **REMOVED as DEAD** |

I read all 158 hits. They are overwhelmingly true positives — real
tables-only appendices in earnings releases (Union Pacific 0.797, PepsiCo
0.790, Texas Instruments 0.789, BlackRock 0.784, KKR 0.725, Progressive,
PNC, 3M, Energy Transfer, Marsh & McLennan, Walgreens, QUALCOMM, Elevance,
Becton Dickinson, Walmart, Amazon, Intel, CVS…).

- **Named false positive (2 of 158, both BELOW the flag threshold):**
  ConocoPhillips `0001157523-15-002627` / `0001157523-15-003543`, where a
  line break split a sentence into the fragment
  *"supplemental information, go to"* (shares 0.322 / 0.329). Named rather
  than special-cased — F2 §5's Danaher standard.
- **Named MISS, measured not fixed: Simon Property `0001104659-21-013702`
  scores 0.000** — H4 §8.4's own anchor. Its 14,916-word EX-99.1 *is* the
  combined "EARNINGS RELEASE AND SUPPLEMENTAL INFORMATION" book: the only
  whole-line `SUPPLEMENTAL INFORMATION` heading is on the title page
  (inside the first 20%), and the rest is marked solely by a repeating page
  header, `4Q 2020 SUPPLEMENTAL`. **There is no tail boundary to find** —
  which is precisely why §6 forbids truncating this class. Widening the
  marker to a bare `supplemental` is not the fix: the same document
  contains the prose line "Supplemental information on our fourth quarter
  2020 performance is available at investors.simon.com". That 165-char
  line is already excluded by the 60-char heading-length guard, which is
  doing real work. The row stays visible via `prose_word_share` = 0.233 and
  `word_count` = 14,916; the class census is P3's.
- **AvalonBay (40 rows) and Prologis (44 rows) score 0.000 throughout**, as
  their clean two-exhibit shape predicts — no false positives on the
  negative anchors.
- Measured flag rate 56/1,613 = **3.5%** on the seeded sample.

### 4e. Real-corpus validation run (scratch output, P2's paths left clean)

One full earnings shard + 25 10-K + 25 10-Q filings, merged:

- `earnings_0000`: **1,500 filings → 1,500 attempts / 1,499 sections**,
  OK 1,289 / FLAGGED 210 / FAIL 1, `cache_miss=0`, **181.4 s = 0.121
  s/doc** under CPU contention. → the earnings segment projects to **~21
  min**, inside the spec's 18–27 min band.
- The single FAIL is **Ford `0000037996-19-000005`, `empty_after_extraction`,
  "0 chars of extractable text"** — one of the 12 named P5 rows, failing
  loudly by name exactly as F2 said it should.
- Gate on that shard: OK 1,355 / WARN_MULTI 100 / WARN_MULTI_NOSIG 44.
- All five artifacts render correctly: `extraction_audit.parquet` (1,600
  rows), `extraction_failures.csv`, `per_filer_rollup.csv` (sorted by
  `fail_rate` desc), `population_gate.csv` (with empty `verdict` /
  `verdict_note`), `length_distribution.csv` (quantiles × era × stratum ×
  the 11-value candidate ladder), `run_manifest.json` (git rev, both
  sha256s, `network_gets: 0`, every resolved constant).
- The partial-merge guard printed
  `[WARNING] merge is PARTIAL: shards done/expected = …` as designed.

### 4f. Edge-handler registry: EMPTY at P1, deliberately

`EDGE_HANDLERS == []`. P0's five dialect classes are each handled where
they belong: **D1** (`Item 1(A).`) and **D3** (`appears on\npages`) are
shared-across-filers regex dialects fixed in the patterns (C12); **D2** is
a reason code because it is unrecoverable at 0 GETs; **D4** is the
`head_foreign_item` check; **D5** is a confidence level. None is per-filer,
so inventing a handler would have been theatre. The mechanism, its
invariants (name + docstring + narrow predicate), fired-counts and DEAD
detection are all live and tested; P3's per-filer triage over the real
30,475-attempt audit is where handlers are expected to appear.

---

## 5. Carried forward to P3 (not decisions, findings)

1. **D2 (MD&A incorporated from a different DOCUMENT) is larger than P0's
   two examples** — Sempra, US Bancorp and now Nucor. Census it before the
   main session's bounded-fetch decision (F3_SPEC §13.1).
2. **A new named class: mojibake exhibits.** Freeport-McMoRan
   `0000831259-24-000026` extracts 6,470 chars of font-encoded garbage. It
   is *long enough in characters* to clear `MIN_SECTION_CHARS` and only
   short in *words*. Neither the population gate nor the head checks see it.
   Census it; a cheap non-ASCII-ratio measurement would size the class.
3. **The 11 genuine-but-thin Tesla P&D releases** are the EX-99 floor's
   known false-alarm class; they are in the review queue by construction.
4. **Simon Property's combined-book shape is not detected by the §6 marker**
   — the class needs its own census, not a widened regex.
5. **Confidence semantics**: 1,519 earnings rows lose `high` purely because
   of the population gate. If P3/P4 wants confidence to mean "extraction
   quality" only, that is a spec amendment, not a silent code change.

---

## 6. P2 segment commands (for the main session)

Run from the repo root, in this order, as **main-session background tasks**
(never from inside a subagent — F3_SPEC §10.3, HANDOFF §4). Defaults are
already the E2 values: `--db data/filings_metadata_e2.db`,
`--out-dir data/f3`, `--out-parquet data/filings_e2.parquet`, shard sizes
1500 / 250 / 500.

```
python3 extract.py --segment earnings      # 10,567 docs,  8 shards, ~21 min measured
python3 extract.py --segment 10-K          #  2,445 filings, 10 shards, ~45-75 min
python3 extract.py --segment 10-Q          #  7,509 filings, 16 shards, ~55-90 min
python3 extract.py --merge                 #  writes the five F3 artifacts
```

- **Resume = re-run the identical command.** A shard whose `.done` marker
  exists (and records the same `--limit`) is skipped; both output files
  land via `os.replace` *before* the marker is written, so the blast radius
  of a SIGTERM is exactly one shard (≤ 8 min).
- **Concurrency (F3_SPEC §13.2):** `--shard i` restricts a process to one
  shard. Measured scaling is poor; **1 worker is the recommendation**, 2 the
  maximum. With 2 workers, split by shard index, e.g.
  `python3 extract.py --segment 10-Q --shard 0` … `--shard 7` in one
  process and `--shard 8` … `--shard 15` in the other. Do not run two
  workers on the same shard index.
- `python3 extract.py --merge` alone re-scans all three segments (skipping
  done shards) and re-merges; it prints
  `[WARNING] merge is PARTIAL: shards done/expected = …` if any segment is
  short, and stamps `merge.complete: false` in `run_manifest.json`.
- Expect: **30,475 attempts**, roughly 28–29k sections, `cache_miss` **0**
  (a nonzero count prints `[FATAL]` and is a run-level stop, never a fetch),
  and `Total EDGAR network GETs this run: 0` on every line.
- Debugging only: `--limit N`. It is recorded in the manifest and in every
  `.done` marker, and a limited shard can never satisfy a later full run.
  `--limit` with `--merge` exits 2.
