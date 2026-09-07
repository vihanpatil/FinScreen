# P0 completion report — F3 spec (extraction-qa-engineer)

**Stage:** P0. **Agent:** extraction-qa-engineer (Opus). **Date:**
2026-08-26. **Status: DONE.** Brief: `F3_PROGRESS.md` §"P0 brief".
**Deliverable:** `data/f3/F3_SPEC.md`.

**Network: ZERO live GETs.** Every document read came from
`data/raw/documents/`; every metadata row from the read-only
`data/filings_metadata_e2.db` (`mode=ro` URI) or from E1's frozen parquets.
No EDGAR request path was executed, no price/Yahoo call, no Anthropic API
call. The measurement harness is a cache-only client stub that **raises on
a cache miss** (the same discipline S2/S5 used).

**No pipeline code was edited.** `extract.py`, `chunk.py`,
`ingest_metadata.py`, `edgar_client.py` and every test file are untouched
(imported read-only). `F3_PROGRESS.md` was not edited. No test suite was
run. E1's artifacts were read, never written.

**Files written**

| path | what |
|---|---|
| `data/f3/F3_SPEC.md` | the deliverable |
| `data/f3/status/P0_spec.md` | this report |
| `data/f3/p0_measure/p0_probe_periodic.py` | 144-filing pilot (located-rate + timing), seeded |
| `data/f3/p0_measure/p0_probe_heads.py` | same sample, stores head/tail text for the head checks |
| `data/f3/p0_measure/p0_gate_recall_h4ledger.py` | **the gate re-measurement** on H4's 155-row ledger |
| `data/f3/p0_measure/p0_gate_corpus.py` | corpus-wide gate/word-count/item-2.02 census (all 10,567 selections) |
| `data/f3/p0_measure/p0_body8k_census.py` | `8K_BODY` item-2.02 census (all 210) |
| `data/f3/p0_measure/gate_corpus.parquet` | its output, 10,567 rows |
| `data/f3/p0_measure/body8k.parquet` | its output, 210 rows |
| `data/f3/p0_measure/prose_share.parquet` | 301-row prose-share sample |

The harness is archived as evidence, not as pipeline code — same status as
`data/hardening/h4_*.py`.

---

## 1. The re-measured gate recall (the brief's gating question)

H4 §7 proposed narrowing its population gate with a results-announcement
text signature and refused to trust it unmeasured. Re-measured on H4's own
155-row ledger, with text extracted through `extract.py`'s
`strip_sgml_document_wrapper` → `html_fragment_to_text`:

| variant | recall on the 9 C rows | flags in 155 | precision C / C-or-B | corpus trigger |
|---|---|---|---|---|
| **V0 multi-cell only (H4's measured baseline)** | **9/9** | 39 | 0.231 / 0.667 | **1,519 (14.37%)** |
| **V1 = H4's proposed narrowing** (`today reported` / `announced results` / `per diluted share` / `quarterly results`) | **8/9 = 88.9%** | 29 | 0.276 / 0.759 | 966 (9.14%) |
| V3 = announcement-verb set + `per diluted share` (fitted on this ledger) | 9/9 **in-sample only** | 24 | 0.375 / 0.917 | 629 (5.95%) |

**V1 is rejected.** The row it drops is `0001104659-22-112514` —
Intercontinental Exchange furnishing **Bakkt's** results. Its text contains
"quarterly results", "per share", "press release" and "months ended": a
results-announcement signature cannot tell *whose* results are announced,
which is the error class itself. H4 named that row as the one "worth naming
loudly."

**V3 is not a rescue** and does not ship: its markers were chosen after
seeing which markers the nine C rows lack, so 9/9 is an in-sample fit with
no held-out evidence.

**What ships:** V0 as the gate (`WARN_MULTI`), with the signature carried
as a severity field (`WARN_MULTI_NOSIG`, 629 rows) and stored per row
(`results_signature_present`, `quarter_cell_size`) so a future narrowing
can be measured against real verdicts. Sanity check on the reproduction:
my cell computation returns **1,519 multi-cell selections (14.37%)** —
H4's number exactly.

---

## 2. What I measured (nothing in the spec is asserted without a number)

1. **Cache census:** 20,521 / 20,521 target documents present, **0
   missing** → the 0-GET run is structurally available.
2. **Workload:** 20,521 filings → **30,475 section attempts**; expected
   output **≈28,840 sections** at pilot located-rates. The brief's "~23k"
   is low by ~1.25×.
3. **Located rates** (144-filing seeded pilot, 288 attempts): 10-K MDA
   87.5% pre-2019 vs 93.8% 2019+; 10-K RF 83.3% → 91.7%; 10-Q MDA 95.8% →
   100%; 10-Q RF 87.5% → 85.4%. `heading_regex` fallback fires **10/288**
   (E1: 0 of 884).
4. **Four short-MD&A rows in that pilot, three of them at `anchor`/HIGH
   confidence** (43, 50, 55, 102 words) — and `STUB_REFERENCE_LANGUAGE_RE`
   matched **0 of 4**. Named: Sempra 2017 ("is set forth in … the Annual
   Report"), US Bancorp 2017 ("incorporated **into this report** by
   reference"), JPMorgan 2017 ("appears on\npages 36–138" — a line break
   inside the phrase), HPE 2019 (a wrong slice, "OFF-BALANCE SHEET
   ARRANGEMENTS").
5. **A wrong-section extraction at high confidence:**
   `0001628280-26-026673` — a 10-Q whose "MD&A" opens *"ITEM 3.
   QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK"*, 1,770
   words, `anchor`/high, above the floor. The new `head_foreign_item` check
   catches it and fires on **1 of 263** located sections (0 false positives
   in the pilot). A second, related row — `0001628280-26-032278`, a
   "RISK_FACTORS" slice opening *"PART II. OTHER INFORMATION ITEM 1. LEGAL
   PROCEEDINGS"*, 422 words — is **not** caught by that check (its first
   item token is "1", the same number as the 1A target) and is caught only
   by the weaker informational `head_keyword_absent` check. Both are in the
   spec; the miss is stated there rather than papered over.
6. **`8K_BODY`, all 210:** every one contains `Item 2.02`; prefix before it
   min 1,121 / median 1,971 / max 14,938 chars (median 21% of the
   document). **Ending the slice at the next item heading would leave <200
   words in 45 of 210 (21%)** — so the end boundary is end-of-document.
   Post-slice, rows below the 500-word floor go 4 → 43.
7. **Earnings word distribution, all 10,357 EX-99 selections:** median
   5,194 w; 12 under 30 chars, 53 under 250 w, 86 under 400 w. The 12 are
   exactly F2 §5's named P5 near-empty class and will FAIL loudly.
8. **Prose-share:** `n_prose_paragraphs == 0 ⇒ 0 labeling chunks`,
   verified 97/97 on E1's frozen artifacts. Zero-prose share for earnings
   sections rises from E1's 4.6% to **14.7%** in a 300-row E2 sample — a
   measured F3→F4 handoff, not an extraction bug.
9. **Timing:** earnings segment measured end-to-end at **1,635 s for
   10,567 documents**; periodic 3.10 s/filing (10-K) and 1.18 s/filing
   (10-Q) under contention; whole-document `BeautifulSoup` parse is
   **1.05 s of a 1.42 s filing**, and the current code pays it twice
   (parse-once saves 44%).
10. **E1 regression is available:** 12 randomly drawn E1 sections
    re-extracted from cache today are **12/12 byte-identical** to
    `data/filings.parquet`.
11. **Membership arithmetic for the F4 window decision:** 20,521 filings →
    13,886 (67.7%) inside member-spell + 12-month margin → 11,403 (55.6%)
    inside spell only; core-only 14,780 / 10,241 / 8,415.
12. **Gate concentration:** 146 filers hold all 1,519 flags; the top 10
    hold 34.4% (Tesla 93, PNC 80, Pioneer 74, MetLife 54, EQT 40, …).

---

## 3. Headline design choices in the spec

- **R1** gate ships broad; signature ranks, never suppresses (§1 above).
- **R2** `8K_BODY` slices item-2.02 → EOD; the tempting next-item boundary
  would have mangled 45 of 210 sections.
- **R3** floors flag, never filter — and a FLAGGED row can never be `high`
  confidence.
- **R4** the MD&A stub resolver triggers on word count alone; the
  reference-language regex is demoted to evidence.
- **R5** cache-only reader, `EdgarClient` not imported on the F3 path.
- **R6** CIK-keyed output (`ticker` is NULL for all 45,545 E2 rows) — with
  the one-line `chunk.py` coupling named for F4.
- **R7** parse each document once.
- **R8** one small named edge-handler registry with fired-counts and DEAD
  detection.
- **R9** every attempt yields an audit row with a closed-enum reason code.
- **R10** F4's scale is re-derived by running `chunk.py`'s own functions
  over F3's real output, separately under three window rules (they are not
  subsets of each other — dedup homes move).

The **manual-QA protocol and its stopping rule are written in full in
§9 of the spec, before any E2 section has been read**: 40 sections in three
never-pooled tiers (16 base-rate SRS / 16 weighted to new filers and
pre-2019 / 8 flag-class), seven pre-declared verdict values, exactly one
permitted extension under one pre-committed condition, escalation that
names-and-censuses a class rather than reading more rows, and an explicit
prohibition on re-drawing or revising verdicts after corpus sizes are known.

**Run segmentation:** 3 segments / 34 shards (earnings 8 × 1,500 docs;
10-K 10 × 250 filings; 10-Q 16 × 500 filings), each ≈5–8 min, `.done`
markers after an atomic rename, resume = re-run the identical command.
Estimated **2–3.5 h single-process**; earnings first so a defect surfaces
in 20 minutes rather than 3 hours. Main-session background chain, never
launched from a subagent (HANDOFF §4).

---

## 4. Owner-facing items

**None.** The one judgment that could have escalated — accept an
8/9-recall gate for a 36% smaller flag list, or keep the broad gate — is
settled by the project's own hard rule ("a section that extracts wrong is
worse than one that fails loudly") and is recorded as ruling R1.

Two **main-session** items (not owner decisions) are named in spec §13:
the size of the "MD&A incorporated from a different document" class
(Sempra/US Bancorp shape) will be measured in P3, and recovering it would
need a bounded EDGAR fetch that F3 will not perform; and the choice of 1 or
2 concurrent workers when P2 launches.

---

## 5. What P0 did NOT do

- No implementation. Every change in spec §3 is described, not written.
- No test file created or run.
- No extraction run: the pilots are 144 filings + 3 census passes over
  already-cached bytes, all in scratch, none writing a pipeline artifact.
- No section was hand-read for QA purposes — deliberately. §9's sample is
  drawn from P2's audit output, after the stopping rule was written.
- No floor or ceiling was changed. §8 states candidates with measured
  before/after counts; P3 applies them, in the open.
