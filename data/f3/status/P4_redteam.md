# P4 red-team report — adversarial pass over F3 (P0 spec → P3 QA)

**Stage:** F3 P4. **Agent:** red-team-reviewer (Opus). **Date:** 2026-08-27.
**Authorization:** F3 ratified 2026-08-26 (HANDOFF §3); overnight-autonomy
grant (§3 2026-08-27 item 5).

**Network: ZERO GETs.** Every document read went through
`extract.read_cached_document` (raises `CacheMiss`, cannot fetch); every
metadata row through `data/filings_metadata_e2.db` opened `mode=ro`. No
EDGAR, price, or Anthropic call. **Zero API spend.**

**Writes: `data/f3/p4_redteam/**` and this file only.** No ledger, no P0–P3
artifact, no `extract.py`, no frozen E1 artifact was modified. The 620 MB
corpus text column was never fully materialised — all text access streams
via `pyarrow.iter_batches` at 200 rows.

**GPU overlap:** H3v2 `finetune/relabel_e1.py --v12` (PIDs 79086/79087) was
alive at start and at finish. No GPU/mlx work performed.

---

## 0. Verdict on the verdict

P3's arithmetic is, with two exceptions, **exact**. I re-derived 40+ of its
published numbers independently and they reproduce to the row. That is
unusual and it should be said plainly.

But P3's headline **recommendation** does not survive measurement, and one
population it declared clean was never actually examined. Concretely:

- **P3's top-ranked fix (F2, "smallest change, largest recovery") would
  make the corpus worse, not better.** Measured on all 148 rows: F2 alone
  produces a plausible-length slice for **70 of 148**; 36 are truncations
  (17 under 200 words against medians of 9,325–13,134) and 23 are
  over-captures up to **9.7×** the section median. On the 32 rows where F2
  is the *only* fix P3 offers, **4 of 32** land in a defensible band.
- **The 779 `EXPECTED_ABSENT` rows carry the identical conflated reason
  code P3 proved is 39.4% wrong on the FAIL side — and P3's census excluded
  them by construction.** A seeded 80-row replay finds **11 (13.8%,
  95% Wilson [7.9%, 23.0%] → 61–179 of 779)** where the Item 1A TOC entry
  exists and the extractor simply failed to resolve it. These are recorded
  as "the filer correctly omitted Item 1A" — a benign status that generates
  no review queue.

**Recommended disposition: NOT FIT FOR F4 AS DESCRIBED — fit for F4 after
three items.** The corpus itself is largely sound; the *record* around it
overstates one fix and under-examines one population. See §9.

**Flag-never-filter invariant: HELD**, verified at key level, not by counts
(§3). **Survivorship: HELD** — 108 of 244 CIKs have dropped out and are
retained (§3.4).

Findings: **2 blocking, 3 major, 6 moderate, 7 minor.**

---

## 1. BLOCKING — "F2 alone recovers all 148" is not a recovery claim

**Claim attacked** (P3 §2.2, §2.4, §0): "**All 116 R2 rows and all 32 R3 rows
have ≥1 hit for the CURRENT, UNCHANGED fallback heading pattern** (`c_cur > 0`
in 148/148). So **F2 alone — a fall-through, with no regex change
whatsoever — recovers all 148.**" Disposition table ranks F2 **"FIX — smallest
change, largest recovery"**, above F1. §2.4 totals: "The three mechanical
fixes (**F2 + F1 + D9**) recover **186 of 796 FAILs (23.4%) exactly**."

**What I did.** `data/f3/p4_redteam/p4_f1_vs_f2.py` — for all 148 R2/R3 rows
(110 cached documents, 470 s), I computed both branches using `extract.py`'s
own shipped functions: **F1** = the first matching TOC entry whose
`anchor_id` actually resolves, sliced and rendered through
`html_fragment_to_text`; **F2** = `locate_item_section_by_heading_regex` on
the whole-document plain text, exactly the call the fall-through would make.
Compared both to the anchor-located median word count for that
(form, section), computed from the shipped corpus.

**What I found.** `data/f3/p4_redteam/f1_vs_f2.csv`.

| | n |
|---|---|
| F2 produces *a span* | **148 / 148** — P3's `c_cur>0` claim HOLDS |
| F2 result < 25% of the (form, section) anchor median | **36** |
| F2 result < 10% of median | **30** |
| F2 result under 200 words | **17** |
| F2 result > 3× median (over-capture) | **23** |
| F2 in a defensible 0.5–2× band | **70** |
| R2 rows where F2 gives < half of F1's words | **58 of 116** |

Named, with the head bytes that decide it:

| filer | accession | form/sec | F1 words | F2 words | F2 head |
|---|---|---|---|---|---|
| Danaher | `0000313616-19-000035` | 10-K MDA | 53,928 | **17** | `Item 7. Management's Discussion … Results of Operations." 57` |
| Coca-Cola | `0000021344-19-000014` | 10-K MDA | 87,025 | **73** | `ITEM 7. … RESULTS OF OPERATIONS Overview` |
| PNC | `0001193125-15-277885` | 10-Q MDA | 86,121 | **89** | `Item 2. … Results of Operations (MD&A).` |
| Honeywell (R3) | `0000930413-19-000366` | 10-K MDA | — | **19** | `… Results of Operations under` |
| Welltower (R3) | `0000766704-16-000082` | 10-Q MDA | — | **68** | median 9,325 |
| Capital One | `0000927628-16-000140` | 10-K RF | 11,536 | **101,388** | `Item 1A. Risk Factors" in this Report for factors that could materially influence our` |
| AIG (R3) | `0000005272-16-000035` | 10-K RF | — | **87,428** | median 10,419 |

Every short head is a **cross-reference sentence**, not a section start —
i.e. §7.2's own documented *last-match* defect firing on the very rows F2 is
supposed to rescue. Every long head is a cross-reference that then runs to
the end of the filing.

**R3 in isolation (32 rows, where F2 is the only fix P3 proposes):**
17 fall below the floor, **25 come in under 0.5× the median**, 3 over-capture,
**4 land in a defensible band.**

**Where the recovered rows land.** 30 of 148 fall below their floor (loud);
**118 clear the floor** and would enter the corpus carrying only
`heading_regex_fallback` at `low` confidence. Of those 118, **30 are >2×
the anchor median** and 18 are <0.5×.

**Why it matters.** F2 converts 148 rows that currently **fail loudly and
stay out of the corpus** into 118 rows that **enter the corpus** with mostly
wrong text. That is a strict inversion of the project's own hard rule ("a
section that extracts wrong is worse than one that fails loudly") — the rule
P0 §4 invoked to settle R1. It is also the exact change `extract.py:1213-1232`
warns against in a dated, empirically-motivated comment ("Falling back to the
heading regex here is **actively dangerous**, not just lower-confidence"),
with a named XOM counterexample. P3 quotes the surrounding function but not
this comment.

Note also the **scoping ambiguity**: F2 as written ("fall through to the
fallback when the anchor path returns `None`") is unscoped and would also fire
on the 625 R1 rows, 81 of which already have `c_cur > 0`. P3's table
annotates those 81 only as "(these fail for a different reason downstream)" —
unsourced.

**P3 disclosed the seam** in §12(1) ("the census proves the fallback pattern
*matches*, not that the resulting slice is right … That is the seam to
attack"). Credit where due. But §0, §2.2 and §2.4 carry the claim without
that qualifier and the word **"exactly"** is attached to it.

**VERDICT: CONFIRMED-DEFECT (recommendation), OVERSTATED (claim).** The
correct ordering is **F1 first** (it produces the right anchor span for all
116 R2 rows), F2 only as a *scoped* R3-only fall-through, and only with a
minimum-span and maximum-span guard. "186 exactly" should read "186 rows for
which a span is produced; ~70+25 of them measured plausible."

---

## 2. BLOCKING — the 779 `EXPECTED_ABSENT` rows were never censused, and ~107 are the same defect

**Claim attacked** (P3 §0): located-rate line — "10-Q RF 87.3% (10.4% of the
shortfall is the documented `EXPECTED_ABSENT` Item-1A omission)"; §0's
"Arithmetic closes"; §2's census scope, and §10.1's "all 784 periodic FAIL
rows … COMPLETE".

**What I did.** Checked the reason codes on the 779 `EXPECTED_ABSENT` rows,
then checked the census file's coverage, then ran a seeded 80-row replay
(`data/f3/p4_redteam/p4_expected_absent.py`, seed 20260828, cache-only).

**What I found.**

- All **779** `EXPECTED_ABSENT` rows carry `reason_code = item_absent_from_toc`
  — the exact code P3 proved is **39.4% mislabelled** on the FAIL side.
- `data/f3/p3_qa/fail_recovery.csv` contains **0** `EXPECTED_ABSENT` rows;
  its frame is `extraction_status == 'FAIL'` only. So the population most
  likely to be silently mis-statused is the one population the census skipped.
- Replay of 80 sampled rows: **69 R1 (genuinely absent) / 8 R2 (first anchor
  dangling, a later identical entry resolves) / 3 R3 (all dangling)**.
  **11 of 80 = 13.8%**, 95% Wilson **[7.9%, 23.0%]** → **61–179 of the 779**.

Named (all 11 in `data/f3/p4_redteam/expected_absent_sample.csv`):

| filer | accession | date | matching / resolvable | cause | fallback finds |
|---|---|---|---|---|---|
| Salesforce | `0001108524-16-000066` | 2016-05-20 | 2 / 1 | R2 | **11,305 w** |
| Vertex | `0000875320-16-000107` | 2016-10-31 | 3 / 1 | R2 | 1,350 w |
| AIG | `0000005272-16-000041` | 2016-05-02 | 3 / 0 | R3 | 1,330 w |
| AIG | `0000005272-16-000046` | 2016-08-02 | 3 / 0 | R3 | 1,246 w |
| BNY Mellon | `0001390777-20-000072` | 2020-08-06 | 2 / 1 | R2 | 896 w |
| AIG | `0000005272-19-000031` | 2019-05-07 | 3 / 0 | R3 | 751 w |
| Vertex | `0000875320-19-000019` | 2019-05-01 | 3 / 2 | R2 | 667 w |
| Eversource | `0000072741-19-000026` | 2019-05-07 | 3 / 1 | R2 | 112 w |
| UnitedHealth | `0000731766-16-000081` | 2016-08-02 | 3 / 2 | R2 | 106 w |
| ADP | `0000008670-18-000007` | 2018-05-04 | 3 / 2 | R2 | 37 w |
| Capital One | `0000927628-26-000048` | 2026-05-07 | 3 / 2 | R2 | 29 w |

**Why it matters.** `EXPECTED_ABSENT` is a **benign** status: it asserts a
fact about the *filer* ("this 10-Q genuinely has no Part II Item 1A"), it
produces no review work, no flag, no queue entry, and P3's own headline uses
it to explain away 10.4 pp of the 10-Q RF shortfall. For 61–179 rows that
assertion is **false** — the item is in the TOC with the right number and
title keyword. This is the "drop rows silently" failure mode my brief names.

Bounded impact, stated honestly: most 10-Q Item 1A entries point at a
one-sentence cross-reference (the legitimate 6,554-row class already in the
corpus at a 94-word median), so most of the 61–179 would add short rows. But
Salesforce `0001108524-16-000066` at 11,305 words and the three AIG rows at
751–1,350 words are not that. And the *status* is wrong regardless of length.

**VERDICT: CONFIRMED-DEFECT.** The §2.2 census must be re-run over the 779
`EXPECTED_ABSENT` rows before F4, or the status must be renamed to something
that does not assert filer intent.

---

## 3. The invariants I was asked to test independently

### 3.1 Flag-never-filter — **HOLDS** (key-level, not count-level)

Joined `extraction_audit.parquet` (30,475) to `filings_e2.parquet` (28,900)
on `(accession_number, section_type)`:

| check | result |
|---|---|
| audit unique keys | 30,475 (no dupes) |
| corpus unique keys | 28,900 (no dupes) |
| OK+FLAGGED keys expected in corpus | 28,900 |
| **missing from corpus** | **0** |
| **extra in corpus** | **0** |
| FAIL / EXPECTED_ABSENT keys leaking into corpus | **0** |
| FLAGGED rows present | **3,655 / 3,655** |
| FLAGGED rows at `high` confidence (R3 forbids) | **0** |
| all 1,509 gate rows present in corpus | yes |

No floor, no gate level, and no flag removes a row. R1 and R3 hold in the
shipped output.

### 3.2 Audit arithmetic — **HOLDS, exactly**

25,245 OK + 3,655 FLAGGED + 796 FAIL + 779 EXPECTED_ABSENT = 30,475.
`run_manifest.json`'s merge entry carries the identical counts and
`complete: true`, shards found = expected (8/10/16).

### 3.3 Located rates — **HOLD, all six, to two decimals**

| form / section | P4 measured | P3 published |
|---|---|---|
| 8-K EX99 | 99.88% | 99.9% |
| 8-K 8K_BODY | 100.00% | 100% |
| 10-Q MDA | 95.15% | 95.2% |
| 10-K RF | 95.09% | 95.1% |
| 10-K MDA | 94.93% | 94.9% |
| 10-Q RF | 87.28% | 87.3% |

Era rates (§5.3) also reproduce exactly: 10-K MDA 91.3% / 96.4%,
10-Q RF 81.9% / 89.9%.

### 3.4 Survivorship — **HOLDS, and this is a genuine strength**

`universe_membership`: 244 distinct CIKs, **299 spells**, 136 currently open
→ **108 CIKs have dropped out of the universe and their filings are
retained**. 47 CIKs carry more than one spell (re-entry preserved). The
corpus is *not* scoped to current members: **32.5% of sections (9,405) sit
outside any spell + 12-month margin** and are kept in W1. There is no
survivorship filter in the corpus.

### 3.5 Look-ahead in the extraction path — **none found in `extract.py`**

Extraction is a pure function of one cached document plus fixed constants.
No price, no return, no future filing enters a slice decision. `report_date`
is metadata, never a boundary. But see finding §5.1 — look-ahead enters via a
*flag* that P3 then hands forward as safe to condition on.

### 3.6 Network / spend / charter — **HOLD**

`run_manifest.json`: `network_gets = 0` and `cache_miss = 0` on **all four**
runs. `extract_py_sha256 = b9acceea…` in every run entry **matches the file
on disk today** — `extract.py` is byte-unchanged since P2, so my replays ran
the shipped code. Zero `import requests` / `urllib` / `EdgarClient` /
`anthropic` in any P0/P1/P3 script. A keyword sweep for trade / advice /
performance language across all four stage reports and the spec returns only
incidental hits ("the wrong **trade**-off", "investors.simon.com"). **No
component recommends a trade, distributes data, or quotes a return.**

---

## 4. MAJOR findings

### 4.1 N1's proposed detector misses a garbled row it was not fitted on — **CONFIRMED-DEFECT**

**Claim attacked** (P3 §6.2 / proposal N1): "**Class size: 4 rows;
2 unprotected.** Detector: `ctrl_ratio ≥ 0.02` selects exactly 3 rows with a
60× margin to the next." N1 is called "the only corpus-quality item I would
not ship F4 without."

**What I did.** Built a detector that shares **no** metric with P3's:
`data/f3/p4_redteam/p4_garble_scan.py` scores every section by the share of
alphabetic tokens that are common English/finance words, streamed over the
whole corpus. Then read the raw bytes of every outlier.

**What I found.** `data/f3/p4_redteam/garble_scan.parquet`. Corpus
`eng_share`: p0.1% = 0.301, p5% = 0.427, median 0.487. Five rows below 0.12;
four are garbled, one (Emerson `0000032604-25-000094`) is a clean numeric
table — a true negative I verified by reading it.

The two Ford rows and Freeport reproduce P3 exactly. **The fifth row does
not appear in P3's class at all:**

| row | words | `eng_share` | `ctrl_ratio` | `nonascii_ratio` | status | flags | prose share |
|---|---|---|---|---|---|---|---|
| **Digital Realty `0001297996-18-000125`** | **2,063** | **0.036** | **0.00000** | **0.0011** | FLAGGED | `[earnings_population_gate]` | **0.9312**, 16 prose paras |

I read its bytes. Head: `!"#$%&"'$%(%&)*+%%$,"(+%- !"#$%&'()(*')+%,-./+0. 1/+2%!3#$ Digital Realty …`;
tail: `d%%%%%%%%#_aU3#3% … eA?LR>AJWE\AFELA%=REFA=%E<J%@<?>=%B@>=>E<J?<L%W`. It is
a font-map-garbled press release, same class as Ford.

- **N1's `ctrl_ratio ≥ 0.02` scores it 0.00000** — a complete miss, not a
  threshold miss.
- **P1's `nonascii_ratio` scores it 0.0011 — *below* the corpus median of
  0.0023.**
- Its only flag is `earnings_population_gate`, a *population* flag. Nothing in
  its record says the text is garbage. With `prose_word_share = 0.9312` and
  16 prose paragraphs it will be packed into ~6 labeling chunks of garbage —
  i.e. it is a third **unprotected** row, not a protected one.

**Why it matters.** P3's own §12(2) says the threshold "is fitted on n=4 …
the honest move is a second measurement on an independent slice, not a
re-fit." I ran that independent measurement and it broke the detector on the
first try. "Class size: 4 rows; 2 unprotected" is **≥5 rows, ≥3 unprotected**,
and the recommended detector generalises poorly.

**VERDICT: CONFIRMED-DEFECT.** N1 should not ship as `ctrl_ratio` alone.
Caveat on my own work: my 0.12 threshold is also chosen after looking, and
my metric false-positives on pure numeric tables (1 of 5). I am claiming the
*counterexample*, not a better production detector.

### 4.2 P3's §2.2 replay table contradicts P3's own census on its motivating example — **CONFIRMED-DEFECT**

**Claim attacked** (P3 §2.2 table row 7): Coca-Cola `0000021344-18-000008`
10-K MDA — "matching TOC entries **3** | first entry resolves? **no** | a
LATER identical entry resolves? **no** — all three share one dangling id",
used to justify **Fix F2**: "Coca-Cola (all three entries dangling) is the
case F1 alone does not fix."

**What I did.** `data/f3/p4_redteam/p4_replay.py` — replayed
`find_toc_item_anchors` → `find_anchor_offset` →
`locate_item_section_by_anchor` on the cached primary document.

**What I found.**

```
0000021344-18-000008 10-K MDA  [a2017123110-k.htm]
  toc_entries=68  matching=3  resolvable=1
    idx=  27 anchor_id='sB1B37B41DFAF5EAEB7DB3170D2F981B9' defined_offset=None
    idx=  28 anchor_id='sB1B37B41DFAF5EAEB7DB3170D2F981B9' defined_offset=None
    idx=  29 anchor_id='sB96D18BEF9965FA4864258455CB0EFDE' defined_offset=411063
```

Entries 27 and 28 share one dangling id; **entry 29 carries a different id
that resolves at offset 411,063.** So a later matching entry *does* resolve,
**F1 alone fixes Coca-Cola**, and the row is R2 — which is exactly what
`fail_recovery.csv` says (`n_matching=3, n_resolvable=1,
cause=R2_first_anchor_dangling_later_resolvable`). The narrative table and
the census disagree, and the narrative table is the wrong one.

The other six rows in that table reproduce exactly, including P3's offsets
(Danaher RF 238,718 via `s4b44ee0d…`; ADP 1,485,459; Welltower `gmnh108`
unresolvable → R3).

**Compounding: the §2.2 table is unreproducible from any artifact.**
`p3_diagnose_fails.py` writes no output file, so the seven-row replay exists
only as prose. That is how the error survived to the report.

**Also wrong in the same paragraph:** the stated mechanism — "each TOC row
carries **two** `<a href="#…">` links — an **upper-case-hex** id that is only
ever *referenced*, and a **lower-case-hex** id that is actually *defined*."
True for Danaher. **False for Coca-Cola** (`sB1B37B41…` → `sB96D18BE…`, both
upper) and **false for ADP** (`sAB6AB196…` → `s5AF8E031…`, both upper). The
*effect* generalises; the *causal story* does not, and it is stated without
hedging.

**VERDICT: CONFIRMED-DEFECT** (factual error in the evidence table, wrong
motivating example for the top-ranked fix, unreproducible provenance).

### 4.3 D9 recovers a third fewer rows than claimed when implemented as specified — **OVERSTATED**

**Claim attacked** (P3 §2.3 / §2.4): D9 = "**one-character-class change** in
`_heading_pattern`", **38 exact**, counted into "186 of 796 … exactly."

**What I did.** `data/f3/p4_redteam/p4_d9.py` and `p4_d9_both.py` — built the
dash-widened pattern and re-ran the fallback on all 38 rows, **twice**: once
widening only the start pattern, once widening `_heading_pattern` itself
(which governs start *and* end patterns — the change P3 actually specifies).

**What I found.** `data/f3/p4_redteam/d9_check_bothends.csv`. All 38 heads
are clean and verbatim (`ITEM 7 - MANAGEMENT'S DISCUSSION…`,
`ITEM 1A - RISK FACTORS Investing in our securities involves risks…`) — D9's
*diagnosis* is right. But the spans:

| | start-only | `_heading_pattern` (as P3 specifies) |
|---|---|---|
| <0.5× anchor median | 1 | **13** |
| 0.5–2× | 16 | **25** |
| >2× | 21 | 0 |

Widening the end patterns fixes the over-captures and creates truncations:
**Emerson's 10 10-K RISK_FACTORS rows collapse to 1,873–4,037 words against a
10,419 median** (3 of them below the 2,000 floor), and Eversource
`0000072741-15-000043` 10-Q MDA collapses to **50 words** from 32,602.

**VERDICT: OVERSTATED.** D9 is the best of the three fixes and worth shipping,
but "38 exact" is a count of rows that *match*, not rows recovered correctly;
~25 of 38 measured plausible. The two-sided effect of changing
`_heading_pattern` is not mentioned anywhere in P3.

---

## 5. MODERATE findings

### 5.1 P3 hands F4/F5 a look-ahead column and calls it safe — **RISK, high confidence**

**Claim attacked** (P3 §6.5, proposal N4): "`reason_code`, `population_gate`,
`quarter_cell_size` and `results_signature_present` are all stored per row, so
**F4/F5 can condition on extraction quality and population membership
separately without any change.**"

**What I did.** Read `extract.load_quarter_cells` (line 1654) and measured.

`load_quarter_cells` counts earnings selections per `(cik, filing_quarter)`
**over the whole 2015–2026 population in one pass** — deliberately, and for a
good reason (the docstring: so a shard boundary can never change a row's gate
level). The consequence is that `quarter_cell_size`, and therefore
`population_gate`, **embeds within-quarter hindsight**.

Measured: **726 corpus rows carry `WARN_MULTI`/`WARN_MULTI_NOSIG` where every
other filing in the cell is later-dated** — the flag is unknowable on the
filing date. Examples: AMD `0000002488-22-000163` filed 2022-10-06 flagged
because of a 2022-11-01 filing (26 days ahead); Air Products
`0000002969-17-000016` filed 2017-04-27 flagged on a 2017-06-05 filing.

Same shape in `p3_gate_verdicts.py`: `habit_share` = the filer's multi-quarter
share **over the full 11 years**, used to verdict 2016 rows
(`REVIEW_NOSIG_HABITUAL`, `ACCEPT_MULTI_HABIT` — 254 rows).

**This is not an F3 defect.** As an audit flag it is correct and the
determinism argument is right. The defect is the **handoff sentence**: any
F5 walk-forward that conditions on `population_gate`, `quarter_cell_size`, or
the gate verdicts is using future information. F3's record contains no PIT
caveat on these columns.

**VERDICT: RISK WORTH FLAGGING (high confidence).** Add a one-line PIT
warning to the F4 handoff: these four columns are corpus-level, not
point-in-time, and are safe for **triage** but not for **conditioning** in a
walk-forward.

### 5.2 §2.3's filer-overlap claim traces to nothing — **CONFIRMED-DEFECT (minor scale)**

**Claim attacked** (P3 §2.3, F1/F2 row): "**148 exact** | **28 filers**:
R2's 25 + R3's 6 (**overlap Honeywell, Apache, Concho**)".

**What I found.** From `fail_recovery.csv`: R2 filers = 25, R3 filers = 6,
**intersection = ∅**. Apache appears only in R2; Honeywell and Concho appear
only in R3. The correct count is **31 distinct filers**, not 28, and the
three named overlaps do not exist. (25 + 6 − 3 = 28 is the arithmetic that
was performed; the subtrahend is fictional.)

**VERDICT: CONFIRMED-DEFECT.** Small number, but it is a "verified" detail
that traces to nothing, in the load-bearing dialect table.

### 5.3 §2.3's hand-verified exemplar quotes a document count as a section count — **OVERSTATED**

**Claim attacked** (P3 §2.3, D9 row): exemplar
`0000032604-21-000038` "(spot-read card 36): heading present verbatim,
**section 37,275 words**".

**What I found.** Card 36 in `qa_cards.txt` is a **stub** — its entire
content is `### NOT IN CORPUS (FAIL row): EMERSON ELECTRIC CO 10-K MDA
2021-11-15 0000032604-21-000038 reason=no_toc_and_no_heading_match`. There is
no text, no word count, no evidence. I then computed the **whole-document**
plain-text word count of `emr-20210930.htm`: **37,275**. Exactly.

So the "section 37,275 words" is the word count of the entire 10-K, presented
in an evidence table as a hand-verified property of the *section*. The actual
D9-recovered section is 8,952 words (`_heading_pattern` widened) or 27,614
(start-only) — neither is 37,275.

**VERDICT: OVERSTATED.** The "heading present verbatim" half is true (I
confirmed it); the number attached to it measures something else.

### 5.4 §6.3's published screen does not reproduce its published number — **OVERSTATED (reproducibility)**

**Claim attacked** (P3 §6.3): "Broader class, measured (`word_count ≥ 8,000`
**and** `prose_word_share < 0.35` **and** ≥5 supplemental page-header hits):
**105 rows, 12 filers** — 78 of them missed by the shipped flag."

**What I found.** Applying exactly that predicate to P3's own
`text_metrics_joined.parquet` gives **119 rows, 14 filers**. The published
filer table also differs: P3 lists Aon **5**; the screen returns Aon **14**.
Walt Disney (3) and ExxonMobil (2) are in the screen and absent from P3's
table. 9 + 3 + 2 = 14 = the gap.

Adding an undisclosed fourth condition — restrict to
`section_type == 'EX99_PRESS_RELEASE'` (equivalently `form == '8-K'`) —
returns **105 rows, 12 filers** exactly. So P3's number is right and its
**stated recipe is incomplete**. The 14 excluded rows are the same
combined-book shape on periodic forms and are dropped without comment.

Everything else in §6.3 reproduces exactly: shipped flag fires on **419**;
Simon 44 EX99 rows, **0** flagged; negative anchors AvalonBay 0/45 and
Prologis 0/45 with median prose share 0.52 / 0.61; **78** missed of 105.

**VERDICT: OVERSTATED (as written).** A reader following the published
definition gets a different answer.

### 5.5 The T3 extension is a different stratum, not a same-frame extension — **RISK, low-moderate**

**Claim attacked** (P3 §5.1(3)): the extension was drawn "from the same
frozen FLAGGED/FAIL frame".

**What I found.** T3's frame is the **8 largest** reason-code classes (one
row each). T3_EXT is **7 of the 7 smallest** classes (one each) + 3 SRS fill.
Those 7 classes total **178 rows = 4.0%** of the 4,451-row FLAGGED/FAIL
population. P3's parenthetical description ("every reason code not already
represented, one each, then SRS fill") is accurate; the phrase "same frozen
frame" is not.

Consequence: T3_EXT's 50% not-CORRECT is a rate over the rarest 4% of the
flagged tail and is not comparable to T3's 37.5%. P3 never pools them and
§5.2 partly says so, which mitigates. But the two tiers are presented in one
table as if the extension continued the same sample.

**VERDICT: RISK WORTH FLAGGING.** Disposition: label T3_EXT
"rare-reason-code tail" in the table.

### 5.6 The gate "verdicts" are a deterministic relabel of columns already present — **naming, not error**

`population_gate_verdicted.csv`: 1,509 rows, 0 blanks, accession set
identical to `population_gate.csv` (byte-unchanged, 179,439 bytes — verified).
But the mapping is exact and mechanical: the three ACCEPT classes are
precisely the 890 `WARN_MULTI` rows (778 + 95 + 17); the three REVIEW classes
are precisely the 619 `WARN_MULTI_NOSIG` rows (357 + 159 + 103). Both totals
match the corpus columns exactly.

P3 is explicit that this is "a census, not 1,509 reads" and that the
vocabulary is deliberately not H4's A/B/C. Fair. But the substantive question
— *is the selected document the right earnings release* — remains unmeasured
for 1,508 of 1,509 rows (P3 read the Tesla row). Calling the output a
"verdict" invites the reader to think otherwise.

**VERDICT: HOLDS with a naming caveat.**

---

## 6. MINOR findings

1. **`P2_runs.md`'s timeline disagrees with the manifest it cites.** Manifest
   UTC → local (UTC−5): earnings 10:05→10:31 (26 min), 10-K 10:31→11:22
   (51 min), 10-Q 11:22→12:56 (94 min); merge run **0.078 s**.
   `P2_runs.md` states 19 / 57 / 82 / ~3 min. Totals 171 vs 161 min. The
   table is marked "~", so this is soft — but `run_manifest.json` is in the
   same directory and is exact. **OVERSTATED (precision).**
2. **"10.4% of the shortfall" is 10.4 *percentage points*, i.e. 81.6% of the
   shortfall.** 10-Q RF shortfall = 12.72 pp; EXPECTED_ABSENT = 10.37 pp. As
   written it reads like 1.3 pp. **OVERSTATED (wording).**
3. **`EDGE_HANDLERS == []` in every run.** `edge_handlers_fired = {}` and
   `edge_handlers_dead = []` in all four manifest entries; `dead_edge_handlers`
   returns `[]` vacuously; `apply_edge_handlers` is a no-op called once per
   section for 30,475 attempts. P1 §4f **discloses this honestly** and argues
   it well ("inventing a handler would have been theatre"). Under the owner's
   lazy-elite rule this is still machinery built ahead of need — a registry,
   a DEAD-detector, two manifest fields and a print for zero members. Neither
   P2 nor P3 mentions the registry is empty while P3 §2.4 proposes ~4
   handlers. **COMPLEXITY / low.**
4. **34 corpus rows sit at `OK` status with `medium` confidence** — all 44
   `mda_stub_resolved` rows split 34 OK / 10 FLAGGED. P3 §6.5's "high appears
   only on `reason_code = ok` (25,211)" is exactly true, but the OK-but-not-high
   subset is never named. **Minor omission.**
5. **P3 §0's row "Sections carrying **no** flag and **not hand-verifiable as
   wrong** | 25,245"** is a double negative that reads as a quality result in
   a table headed "measured". It is the OK count; nobody looked at 25,213 of
   them. §1 is honest about this ("the base rate rests on 32 reads"). The
   headline table is not. **Framing / low.**
6. **P3's §2.2 code excerpt elides `_end_of_enclosing_tag`** between the
   `find_anchor_offset` line and the end-boundary loop. Immaterial to the
   argument; noting it because the excerpt is presented as the code.
7. **§5.2 and §2.3 disagree on the SLB anchor offset** — "anchor resolves at
   2,716,750" (§5.2) vs "span `(2716778, 2717059)`" (§2.3), for
   `0001564590-18-024846`. 28-char discrepancy; the two are probably pre- and
   post-`_end_of_enclosing_tag`, unstated. **Minor.**

---

## 7. Claims I re-derived that HOLD, exactly

Recording these because a red-team report that lists only failures misleads.
All reproduced from the artifacts, independently:

| claim | source | P4 result |
|---|---|---|
| Audit arithmetic 25,245/3,655/796/779 = 30,475 | §0 | exact |
| All six located rates | §0 | exact |
| Era located rates 91.3/96.4, 81.9/89.9 | §5.3 | exact |
| **F4-scale: W1 199,403 · W1-core 146,571 · W2-core 99,965** | §8.1 | **exact, independently re-implemented** (§8 below) |
| All six window-rule section counts (28,900 / 20,832 / 19,495 / 14,327 / 16,029 / 11,779) | §8.1 | exact |
| 1,634 sections, 136 filers, **11,983,216** words, prose<0.05 & ≥1,000 w | §7.1 | exact |
| Ford ×2 + Freeport ctrl_ratio 0.335 / 0.242 / 0.229; next row 0.0037 | §6.2 | exact |
| `nonascii_ratio` p50 0.0023 / p99 0.016 / max 0.0585 | §6.2 | exact |
| All four floor holds: 134 / 63 / 92 / 0 below-floor; bands 4 and 19 | §4.1–4.4 | exact |
| 10-K MDA sub-floor: 134/134 `incorporated_by_reference_unresolved`, 130 under 250 w | §4.1 | exact |
| 10-Q RF min 19 w, p25 39, p50 94, 4,193 under 250 w | §4.4 | exact |
| EX99 floor → 41 flagged; 8K_BODY floor → 43 of 210 | §4.5 | exact |
| `high` only on `reason_code=ok`, 25,211 rows | §6.5 | exact |
| 1,387 `earnings_population_gate` primary, all medium | §6.5 | exact |
| 1,337 rows with the gate as their **only** flag = 12.67% of 10,555 8-K rows | §6.5 | exact |
| D2: 80 rows / 15 filers, 100% 10-K MDA; 44 10-K RF under 250 w / 7 filers | §6.1 | exact |
| `stub_language_present` is 0 outside (10-K, MDA) | §6.1 | exact |
| Simon 44 EX99 rows, 0 flagged; 419 shipped-flag fires; 78 of 105 missed; AvalonBay/Prologis 0/45 each | §6.3 | exact |
| 1,140 `heading_regex` rows, all `low`; AT&T 34 rows, median 333.5 w | §7.2 | exact |
| `head_foreign_item` 51 rows / 7 filers / NIKE 21 / 0.17% | §7.4 | exact |
| `mda_stub_resolved` 44 rows; prose share p10 .404 / p25 .507 / p50 .586 / max .834; sole outlier = Warner Media at 0.101 | §7.3 | exact |
| Gate reconciliation 1,519 − 10 = 1,509; verdict totals 778/357/159/103/95/17; 619 REVIEW = 41% | §3 | exact |
| **All Wilson intervals** — T1/T2 [0, 19.4], T3 [13.7, 69.4], T3_EXT [23.7, 76.3] | §0, §5 | exact; the extension condition (LB 13.7% > 10%) genuinely fired |
| `c_cur > 0` in 148/148 R2+R3 | §2.2 | exact |
| R1 fallback ladder 81 / +38 / +43 / +281 / 182 | §2.2 | exact |
| §1's hand-read arithmetic 40+10+4+19+16+9+4 = 102 | §1 | exact |
| E1 method counts 544 anchor / 331 whole_document / 9 resolved; the 4 named regression rows are all `8K_BODY`/`whole_document` at the stated word counts | P1 §4a | exact (inputs) |

**Spot-read freeze discipline — HOLDS, verified by reproduction.** I re-ran
`p3_qa_sample.py`'s draw into my own directory
(`data/f3/p4_redteam/p4_repro_sample.py`) and the 40-row manifest is
**identical, row for row, tier for tier**, from seed 20260827. T3's 8 codes
are exactly the top-8 reason codes by class size, as the spec requires. T2's
composition is exactly 6/4/3/3 per spec §9.1. File mtimes give a clean
causal order: manifest 13:13:28 → cards 13:20:07 → verdicts 13:23:27 →
**ext manifest 13:23:55** (i.e. drawn *after* the T3 verdicts existed, as
required) → ext cards 13:24:03 → ext verdicts 13:25:33. The script refuses
to regenerate a manifest that exists. **No evidence of a re-draw, and no
cherry-picking mechanism available.**

---

## 8. The F4-scale table, independently re-derived

**Claim attacked** (§8.1): the whole 12-row table, and W2-core = 99,965 in
particular.

**What I did.** `data/f3/p4_redteam/p4_scale_check.py`, written from
`chunk.py`'s semantics rather than copied from `p3_scale.py` (different hash
function — sha1 vs blake2b; different control flow). **Two-step:**

- **Step A — ground truth.** Ran `chunk.build_canonical_paragraphs` +
  `chunk.pack_windows` (the *real* functions, unmodified) over a bounded
  600-section slice → **8,727 chunks**. My streaming re-implementation on the
  same 600 → **8,727. AGREE.** This validates the streaming approach against
  chunk.py itself.
- **Step B — full corpus.**

| rule | P4 sections | P4 paras | P4 canonical | P4 chunks | P3 | |
|---|---|---|---|---|---|---|
| W1_full | 28,900 | 1,303,855 | 830,851 | **199,403** | 199,403 | MATCH |
| W1_full_core | 20,832 | 972,109 | 603,226 | **146,571** | 146,571 | MATCH |
| **W2_spell_plus12m_core** | 14,327 | 644,389 | 417,004 | **99,965** | 99,965 | **MATCH** |

I also line-by-line compared `p3_scale.py` against `chunk.py`: the home order
(`filing_date, ticker→cik10, accession, section_type, position`), the
first-occurrence-wins dedup, the group-by-home-section rule, and the
accumulate/flush-at-350/tail-flush-at-100 arithmetic all correspond exactly.
The two declared deviations (cik-for-ticker; `reflow_v1` substituting for
§12.3's block-element variant) are stated in the script docstring and in
§8/§12(5), not buried.

**VERDICT: HOLDS.** Every derived figure follows: W2-core→W1-core = +46,606
chunks = +43.6 h; W3-core→W2-core = +16,955; reflow 2.18× at W1 and 2.21× at
W2-core; zero-chunk 5,729 → 4,199; the 1.30× / 1.90× / 2.59× / 5.63×
multiples against the plan's ~77k. One internal note: `chunks_core` inside a
full run differs from the separate core-only run by 2 (as-is) to 10 (reflow)
— correct, and exactly the "dedup homes move" effect §8's method paragraph
predicts.

**One PIT observation on the window rules, not a defect.** W2 is implemented
as a 12-month margin **before** `member_from` (`p3_scale.py:186`), which
matches F3_SPEC §12.2's "member spell + 12-month **pre**-margin" exactly.
Including a filer's filings from 12 months *before* it entered the universe
means the corpus scoping uses knowledge of later membership. For a **corpus**
that is normal and harmless. It becomes look-ahead only if F5 evaluates
as-of a date inside that pre-margin using a universe defined by later
membership. Worth one sentence in the F4 handoff; nothing in F3's record
says it.

---

## 9. The strongest case AGAINST shipping this corpus to F4, and whether the evidence disposes of it

**The case.** 3,655 FLAGGED + 796 FAIL + 779 EXPECTED_ABSENT = **4,451
attempts (14.6%) that are not clean OK**, plus two hand-confirmed rows of
pure garbage sitting at OK/high with zero flags, plus a base rate resting on
**32 hand reads** whose 95% Wilson upper bound on the error rate is **19.4%**.
On 28,900 sections, a 19.4% ceiling is ~5,600 potentially-wrong sections. F4
will spend 9.4 overnights of GPU labeling on this.

**Does the evidence dispose of it? Partly — three of four legs, not the fourth.**

- **The FLAGGED leg: disposed.** Every FLAGGED row is in the corpus with its
  reason code, its flags, and a confidence that can never be `high` (verified,
  §3.1). F4 can condition on them. This is a feature.
- **The FAIL leg: disposed as a corpus question.** FAILs are absent from the
  corpus and fully audited. They cost recall, not correctness. **But the
  proposed remedy makes it worse** — see §1.
- **The garbage leg: NOT disposed, and larger than stated.** §4.1 — the
  recommended detector misses a fifth row it was never fitted on.
- **The base-rate leg: NOT disposed.** 0/16 on T1 is real and the bound is
  stated honestly, but 19.4% is a wide ceiling and nothing else in F3
  narrows it. P3 does not claim otherwise; the FIT FOR F4 headline reads as
  if it did.

**Plus the leg the case did not know to make:** the 779 EXPECTED_ABSENT rows
were never examined at all (§2), and ~107 of them are the defect P3
documented elsewhere. That leg is the reason I do not sign the verdict as
written.

**My verdict: FIT FOR F4 after three items** — N1 rebuilt on a metric that
survives an independent slice; the EXPECTED_ABSENT census run; and the F2/F1
ordering corrected before any `extract.py` change ships. None of the three is
large. None requires a fetch. All three are cheaper than one labeling
overnight.

---

## 10. What I did NOT check

- **P1's "880/884 byte-identical" E1 regression** — verifying it needs a full
  re-extraction of E1's 884 rows, which I judged out of scope while a GPU job
  holds the machine. I verified the *inputs*: `filings.parquet` is 884 rows,
  the method split is 544/331/9 exactly as claimed, and all four named
  regression rows are `8K_BODY`/`whole_document` at the stated pre-word
  counts. **CANNOT-VERIFY-OFFLINE (partially corroborated).**
- **Whether P3's 102 hand-read verdicts are individually right.** They are
  model judgements. I re-read the raw bytes of 4 of them (both Ford rows, both
  Digital Realty rows) and agree with P3 on the 3 it names. I did not re-read
  the other ~98.
- **The 25,245 OK rows.** I screened all 28,900 on one independent metric
  (§4.1) and read 5 outliers. That is a screen, not a read.
- **Whether D2's 121 rows are recoverable.** Needs a fetch. F3 correctly
  refused; so did I. **CANNOT-VERIFY-OFFLINE.**
- **F1's recovered text quality.** I measured F1's *word counts* against
  anchor medians and read their heads; I did not read 116 full sections. F1
  looks right on every case I inspected, but "F1 is correct" is not
  established to the standard I applied to F2.
- **The reflow_v1 vs §12.3 block-element question.** P3 flags it as a
  substitution (§12(5)); I did not re-extract to compare.

---

## 11. Owner-visible items — what the owner must see before F4

1. **The record's top-ranked extraction fix (F2) would degrade the corpus.**
   Measured: of the 148 rows it "recovers", 36 come back truncated (17 under
   200 words) and 23 over-captured (up to 9.7×). It would move 118 rows from
   "fails loudly, stays out" to "enters the labeling set with wrong text" —
   against the project's own hard rule. **Ship F1 first; scope F2 to R3 only,
   with span guards.** (§1)
2. **779 rows were filed under "the filer didn't disclose this" without
   anyone checking.** A seeded 80-row replay finds 61–179 of them are
   extractor failures, including one Salesforce 10-Q whose Risk Factors
   section is ~11,300 words. This is the only *silent* drop I found. (§2)
3. **The garbage-text detector P3 says it "would not ship F4 without" fails
   on the first independent test.** Digital Realty `0001297996-18-000125` —
   2,063 words of font-map garbage, `prose_word_share` 0.93 — scores
   **exactly 0.0** on the proposed `ctrl_ratio` metric and *below the corpus
   median* on the metric P1 proposed. At least 3 unprotected rows, not 2. (§4.1)
4. **Four gate columns are not point-in-time and the record says F4/F5 may
   condition on them.** 726 rows are flagged because of a *later* filing.
   Safe for triage, unsafe in a walk-forward. One sentence fixes the handoff.
   (§5.1)
5. **Two "verified" details in the evidence tables trace to nothing**: the
   Coca-Cola row that motivates fix F2 is contradicted by P3's own census
   (§4.2), and "section 37,275 words" is the whole document's word count, from
   a QA card that is an empty stub (§5.3). Both are small; both are the kind
   of thing that erodes trust in the 40 numbers that *are* exact.
6. **Nothing in F3 violates the charter.** Zero GETs across all four runs
   (manifest-verified), zero API spend, no trade language, no data
   distribution, `extract.py` byte-unchanged since P2. Survivorship is
   genuinely absent — 108 of 244 companies dropped out of the universe and
   their filings are all still in the corpus. (§3.4, §3.6)
7. **P3's arithmetic deserves credit.** Forty-plus published figures — every
   floor, every census, every Wilson interval, the entire F4-scale table
   including the 99,965 W2-core number I re-implemented from scratch —
   reproduce **exactly**. The findings above are about recommendations,
   scope, and two evidence-table errors. They are not about the counting.

---

## 12. P4 artifacts

All under `data/f3/p4_redteam/`:

| file | what |
|---|---|
| `p4_replay.py` | independent replay of `locate_item_section_by_anchor` on P3's 7 named rows (§4.2) |
| `p4_f1_vs_f2.py` → `f1_vs_f2.csv` | F1-vs-F2 recovery measurement, all 148 R2/R3 rows, 110 documents (§1) |
| `p4_d9.py` → `d9_check.csv`; `p4_d9_both.py` → `d9_check_bothends.csv` | D9 recovery quality, start-only and both-ends (§4.3) |
| `p4_expected_absent.py` → `expected_absent_sample.csv` | 80-row seeded replay over the EXPECTED_ABSENT population (§2) |
| `p4_garble_scan.py` → `garble_scan.parquet` | independent English-word-share screen, all 28,900 sections (§4.1) |
| `p4_scale_check.py` | independent F4-scale re-derivation + chunk.py ground-truth validation (§8) |
| `p4_repro_sample.py` → `p4_repro_manifest.{json,csv}` | reproduction of the frozen 40-row QA draw (§7) |

**Discipline:** 0 live GETs · 0 API spend · writes confined to
`data/f3/p4_redteam/**` and this file · corpus text streamed via
`iter_batches`, never materialised · no GPU/mlx work · `extract.py`,
`chunk.py`, all P0–P3 artifacts and every ledger byte-unchanged.

**GPU overlap at finish:** H3v2 `finetune/relabel_e1.py --v12` PIDs
79086/79087 **alive**.
