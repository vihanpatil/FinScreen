# P4b — full census of all 779 `EXPECTED_ABSENT` rows

**Stage:** F3 P4b (P4 blocking finding 2, owner-ordered — HANDOFF §3,
2026-08-27 evening). **Agent:** extraction-qa-engineer (Opus).
**Date:** 2026-08-27.

**Network: ZERO GETs.** Every document byte read through
`extract.read_cached_document` (raises `CacheMiss`, cannot fetch);
`data/filings_metadata_e2.db` opened `mode=ro`. No EDGAR, price, or Anthropic
call. **Zero API spend. No GPU/mlx.**

**Writes: `data/f3/p4b_ea_census/**` and this file only.** No ledger, no P0–P4
artifact, no `extract.py`, no frozen E1 artifact touched. `extract.py`
sha256 = `b9acceea837796e598113eb35d3af53404ec33a101cd26b6d87623200d95ecdd`,
**identical to `run_manifest.json`'s `extract_py_sha256` on all four runs** —
so the replays below ran the shipped code, byte-for-byte.

**Method:** P4's own scripts, extended — not reinvented.
`p4b_ea_census.py` is `p4_expected_absent.py`'s replay with
`p4_f1_vs_f2.py`'s F1 span arithmetic bolted on, run over the **whole
population instead of an 80-row sample**, plus two measurements P4 did not
make (an end-guarded span, and a head check).

---

## 0. Headline

| | n | of 779 |
|---|---|---|
| **Genuinely absent (R1)** — no matching Item 1A entry in the anchor TOC; the status is correct as specified | **696** | 89.35% |
| **R2** — first matching entry's anchor dangles, a LATER matching entry resolves | **71** | 9.11% |
| **R3** — every matching entry dangles | **12** | 1.54% |
| **total** | **779** | 100.00% |
| **R4** (first anchor resolves, span arithmetic fails) | **0** | — |
| **errors / cache misses** | **0** | — |

**Reconciliation: 696 + 71 + 12 + 0 = 779. Exact.** Every one of the 779 rows
was replayed; `shipped_span_is_none` is `True` on all 779, confirming each row
really sat on the `EXPECTED_ABSENT` path and not somewhere else.

**The honest bottom line:**

> **83 of 779 (10.65%) are misclassified extractor failures** — the Item 1A
> entry IS in the TOC, with the right item number and the required title
> keyword, and the extractor simply failed to resolve it. **Of those 83, 58
> are recoverable with a defensible span** through a guarded use of the
> already-resolving later anchor; **a further 13 (Eversource) are recoverable
> only through the fallback**, taking the recoverable total to **71**; and
> **12 (all AIG) are not recoverable by any current mechanism and must stay
> loud FAIL rows.**

Recovered volume, for scale: the 58 defensible spans carry **120,424 words**;
adding the 13 Eversource rows takes it to **125,156 words**. 89,436 of those
words (74%) are eight Salesforce 10-Qs.

**All 779 are `(10-Q, RISK_FACTORS)`. Zero MDA.** This is structural, not a
sampling accident: `extract.py:334-337` maps `item_absent_from_toc` to
`EXPECTED_ABSENT` **only** for `(10-Q, RISK_FACTORS)`; the same reason code on
the other three targets is a FAIL and was already inside P3's frame (10-K MDA
96, 10-K RF 83, 10-Q MDA 197 — 376 rows, 1,155 total). So the RISK_FACTORS /
MDA question resolves to **83 recoverable rows, 83 RISK_FACTORS, 0 MDA**.

---

## 1. Reconciliation against P4's Wilson interval — **it held**

| quantity | P4 (seeded n=80) | P4 95% Wilson → of 779 | P4b census (n=779) | inside? |
|---|---|---|---|---|
| misclassified | 11/80 = 13.75% | [7.9%, 23.0%] → **61–179** | **83** (10.65%) | **yes** |
| R2 | 8/80 = 10.00% | [5.2%, 18.5%] → 40–144 | **71** (9.11%) | yes |
| R3 | 3/80 = 3.75% | [1.3%, 10.5%] → 10–81 | **12** (1.54%) | yes |

With a finite-population correction (80 drawn without replacement from 779)
the headline interval tightens to [63, 175]; 83 is still inside.

**No surprise. P4's interval held on all three quantities.** Its point
estimate ran ~3.1 pp high (13.75% vs 10.65%) — an n=80 artifact, well inside
the stated uncertainty. P4 was right to state the range, not the point.

**Stronger check: I reproduced P4's 80-row replay exactly.** Joining
`expected_absent_sample.csv` to my census on accession: **80/80 rows agree on
the arm** (R1 69/69, R2 8/8, R3 3/3), and all 11 named rows agree on
`n_matching`, `n_resolvable` and `fallback_words` to the row. P4's sample is a
faithful subset of this census.

---

## 2. Span plausibility — the recalibration, in the open

**P4's band is unfit for this section, and I am not using it as the verdict.**
P4's method (justified on 10-K MDA / 10-K RF, where it works) is 0.5–2× the
(form, section) anchor-located median. For `(10-Q, RISK_FACTORS)` that median
is **97 words**, so the band is **[48.5, 194]**.

That band is wrong here because the measured distribution is **strongly
bimodal**, not unimodal. Measured over all 6,070 anchor-located
`(10-Q, RISK_FACTORS)` rows in the shipped corpus:

| word range | n | what it is |
|---|---|---|
| 19–250 | 3,863 (63.6%) | the legitimate "no material changes since the 10-K" cross-reference stub — real, complete Item 1A content |
| 250–2,000 | 981 (16.2%) | partial / supplemental updates |
| 2,000–51,295 | 1,226 (20.2%) | substantive restated Risk Factors |

Mode medians: **46 w** (stub) and **12,740 w** (substantive); trough at
~250 w. Applying a single 0.5–2× median band to that shape **rejects 49 of the
58 spans I hand-verified as correct** (30 as "above 2× median", 19 as "below
0.5× median") and accepts only 9. Using it as a gate would throw away every
Salesforce recovery.

**Recalibration, with before/after counts.** I report both, and use the
second. Neither lowers a floor to make a failure disappear — the shipped
`MIN_SECTION_WORDS[("10-Q","RISK_FACTORS")] = 15` and
`MIN_SECTION_CHARS = 30` are **unchanged and untouched**; this is a
plausibility band for the census, not a production threshold.

| band verdict on the 83 | P4's 0.5–2×-median band | recalibrated bimodal band |
|---|---|---|
| in band | 12 | 83 (31 STUB / 42 MID / 10 SUBSTANTIVE) |
| below band | 19 | 0 (none under the corpus min of 19 w) |
| above band | 52 | 0 (none over the corpus max of 51,295 w) |

Because the recalibrated band accepts everything, **it is not the
discriminator either.** What actually separated good from bad here was two
structural guards, measured below — and the hand read that validated them.

### The two guards that do the work

- **G1 — the span must OPEN on the item's own heading.** An
  `item\s*1A…risk factors` match within the first 40 characters of the
  rendered text.
- **G2 — an end-guarded span must not terminate at end-of-document.** A real
  Part II Item 1A is always followed by Item 2 (Unregistered Sales) or a later
  Part II item, so if none of `extract.py`'s shipped end-patterns matches after
  the start, the **start** is in the wrong place.

On the 83, the two guards separate the population **with zero disagreements
against my hand read**:

| | G1 pass | G2 pass | both | hand-read verdict |
|---|---|---|---|---|
| R2 (71) | 58 | 58 | **58** | 58 correct, 13 wrong |
| R3 (12) | 12 | **0** | **0** | 0 correct, 12 wrong |

For the 58 R2 survivors the arithmetic behind G2: **21** rows' raw anchor spans
already closed on a resolving anchor; **37** ran to EOF and the end guard
closed them properly (median guarded/raw ratio 0.41 across all 71). **Zero**
rows ran to EOF with no end-pattern to close them. All 12 R3 rows are already
end-guarded by `locate_item_section_by_heading_regex` and **still** run to EOF.

**Floor clearing: 58/58 defensible spans clear the 15-word floor and the
30-char `MIN_SECTION_CHARS` gate.** Not one of them needed a floor moved.

---

## 3. What I actually read (mandatory spot-read)

**~62 sections read by eye**, weighted exactly as the brief requires — toward
new filers and pre-2019 filings (71 of the 83 misclassified rows are pre-2020;
14 of 83 are extension-stratum filers absent from E1's 25 mega-caps).

**Read in full: all 12 R3 rows** (head + tail + word count + EOF flag).
**Read: 15 R2 rows** flagged suspicious by the automated head check, plus
**3 rows per filer × 12 filers = 33** across the R2 arm (heads + guarded
tails). **Read: one representative per (filer, head-signature) group for all
49 groups covering the 145 R1 rows that have a fallback span** — Ford's 26
rows collapse to 11 signatures, Medtronic's 24 to 2, Hess's 22 to 7, so this
is a full read of the distinct R1 fallback behaviours, not a sample of them.

### 3.1 What the R3 arm actually contains — **0 of 12 recoverable**

All 12 R3 rows are **AIG, 2015-08-03 → 2019-05-07**. Every one is the exact
failure mode `extract.py:1220-1232` warns about, on a different filer than the
XOM case named in that comment. Every head begins **mid-sentence**, on the tail
of a cross-reference:

> `0000005272-16-000041` (2016-05-02, 1,330 w) — head:
> *"Item 1A. Risk Factors **in our 2015 Annual Report for additional
> information on** increased capital requirements that may be imposed on
> us…"*
> tail: *"…filed for purposes of Sections 11 and 12 of the Securities Act of
> 1933 and Section 18 of the Securities Exchange Act of 1934. **174**"*

> `0000005272-15-000009` (2015-08-03, 802 w) — head:
> *"Item 1A. Risk Factors **in our 2014 Annual Report. ITEM 2 / UNREGISTERED
> SALES OF EQUITY SECURITIES AND USE OF PROCEEDS** The following table
> provides the information with respect to purchases…"*

The span then runs through Item 2's share-repurchase tables, Items 3–6, and the
signature/exhibit page, terminating at end-of-document on **all 12**
(`fb_end_at_eof = 1` on 12/12). Word counts 751–1,543.

**This directly corrects P4's own §2 table**, which listed three of these AIG
rows under a column headed "fallback finds — 1,330 w / 1,246 w / 751 w". Those
are not 751–1,330 words of Risk Factors. They are 751–1,330 words of
Unregistered Sales, Exhibits and signature blocks with a truncated
cross-reference clause on the front. P4 labelled the column honestly ("do NOT
trust raw recovery" is the brief's own warning) — but the number invites the
opposite reading, and I am recording that it does not survive a read.

### 3.2 The Eversource dialect — F1 gives the **wrong section**, loudly

13 R2 rows, Eversource Energy, 2016-11-04 → 2020-11-06. The later-resolvable
anchor resolves, but it points at the start of **Part II**, not at Item 1A:

> `0000072741-17-000021` (2017-05-05) — F1 head:
> *"**PART II. OTHER INFORMATION ITEM 1. LEGAL PROCEEDINGS** We are parties to
> various legal proceedings. We have disclosed these legal proceedings in
> Part I, Item 3, "Legal Proceedings," and elsewhere in our 2016 Form 10-K…"*
> — 1,249 w raw, 179 w end-guarded, guarded tail lands inside the risk-factors
> paragraph.

So the guarded F1 span for Eversource is **Legal Proceedings concatenated with
Item 1A** — plausible-looking, floor-clearing, and wrong. G1 catches all 13.

**The fallback gets Eversource exactly right, on all 13**: head at offset 0
(*"ITEM 1A. RISK FACTORS We are subject to a variety of significant risks in
addition to the matters set forth under 'Forward-Looking Statements,' in Item
2…"*), no EOF termination, 110–1,263 words. This is the single clearest
counterexample in the census to a rigid "F1 first, always" rule.

### 3.3 The 58 that are right — read and confirmed

Sampled reads across every filer in the arm. Representative:

- **Salesforce ×8** (2015-08-25 → 2019-06-05), 10,750–13,941 w — head
  *"ITEM 1A. RISK FACTORS The risks and uncertainties described below are not
  the only ones facing us…"*, guarded tail *"…might otherwise be beneficial to
  investors. 76 Table of Contents"*. Full substantive Risk Factors. This is
  P4's headline example and it is real.
- **ADP ×14** (2015–2020) — raw spans 487–1,070 w run past the section; the end
  guard closes every one at **37 w**, ending exactly on
  *"…for the fiscal year ended June 30, 2017 . 40"*. The guarded 37 w matches
  the independent fallback's 37 w to the word.
- **UnitedHealth ×8** (2015–2017) — raw 1,263–1,821 w, guarded **102–106 w**,
  again matching the fallback exactly.
- **BNY Mellon ×5** (2017, 2020) — head *"Item 1A. Risk Factors The following
  discussion supplements the discussion of risk factors…"*, guarded 736–1,121 w,
  matching the fallback exactly.
- **Vertex ×15** (2015–2020), 652–2,614 w, end guard not needed (span already
  closed on a resolving anchor).
- **AIG ×2** (2023) at 40 w and **Capital One ×2** (2026) at 29 w — genuine
  short "no material changes" stubs, complete as filed. *(My automated
  cross-reference heuristic false-positived on the two AIG-2023 rows because
  their body text itself ends "…Item 1A. Risk Factors in the 2022 Annual
  Report." The hand read overrides it; the heuristic is not used in the
  verdict.)*

### 3.4 The R1 residual — the status name is wrong more often than the census is

R1 means "no matching Item 1A entry in the anchor TOC", which is what the
extractor tests and therefore the correct classification **as specified**. It
is *not* the same claim as `EXPECTED_ABSENT`'s plain-English meaning ("the
filer genuinely omitted Part II Item 1A"). Reading the 49 head-signature
groups shows those two claims come apart:

| | n of 696 |
|---|---|
| no fallback span at all — nothing that looks like Item 1A anywhere in the document | **551** |
| fallback head opens a **genuine** Item 1A section the anchor TOC never indexed | **42** |
| fallback head is a **cross-reference continuation** (garbage if recovered) | **103** |

The 42 genuine ones, by filer: Cigna Holding 11, Welltower 9, Cigna Group 8,
US Bancorp 7, Truist 3, SBA Communications 2, AbbVie 1, CVS 1. Named examples
I read: SBA `0001034054-16-000022` (2016-08-09) — *"ITEM 1A . RISK FACTORS We
depend on a relatively small number of customers for most of our revenue…"*,
**12,855 w of real Risk Factors**, absent from a 7-entry anchor TOC; Truist
`0000092230-20-000114`; Cigna Holding `0001104659-18-030187` (3,080 w).

The 103 cross-reference rows are Ford 26, Medtronic 24, Hess 22, ExxonMobil 11
(the documented XOM case), Williams Companies + Williams Partners 7, Caterpillar
5, EOG 5, MercadoLibre 3. Worst: Williams `0000107263-17-000006` — the
fallback returns **21,241 words** beginning *"Item 1A. Risk Factors in our
Annual Report on Form 10-K filed with the SEC on February 22, 2017. 3
DEFINITIONS The following is a listing of certain abbreviations…"*.

**Consequence:** the number of rows whose **status is factually wrong** is
**83 (extractor failures) + 42 (filer did disclose, TOC didn't index it) = 125
of 779 (16.0%)**. Only the 83 are extractor defects; the 42 are a naming
defect. P4's alternative disposition — *rename the status so it stops
asserting filer intent* — is independently supported by these 42 rows and
should be adopted **regardless** of which extraction fix ships.

---

## 4. Era and filer concentration

**The recoverable set is dominated by pre-2020 filings and by 12 filers.**

| era | misclassified / total EA | rate |
|---|---|---|
| filed ≤ 2019 | **71 / 421** | **16.9%** |
| filed ≥ 2020 | 12 / 358 | 3.4% |

A **5.0× era gradient** — the same anchor-TOC-degrades-in-older-filings effect
`EXPANSION_PLAN.md` §5 F3 predicted, showing up at the 2020 boundary in this
corpus rather than 2010.

| filer | rows | years | arm | disposition |
|---|---|---|---|---|
| Vertex Pharmaceuticals | 15 | 2015–2020 | R2 | 15 defensible (652–2,614 w) |
| ADP | 14 | 2015–2020 | R2 | 14 defensible (37 w each) |
| **Eversource Energy** | **13** | 2016–2020 | R2 | **0 via F1** (wrong section) / 13 via guarded F2 (110–1,263 w) |
| **AIG (R3)** | **12** | 2015–2019 | R3 | **0 recoverable — keep as loud FAIL** |
| Salesforce | 8 | 2015–2019 | R2 | 8 defensible (10,750–13,941 w) |
| UnitedHealth | 8 | 2015–2017 | R2 | 8 defensible (102–106 w) |
| BNY Mellon | 5 | 2017, 2020 | R2 | 5 defensible (736–1,121 w) |
| AIG (R2) | 2 | 2023 | R2 | 2 defensible (40 w) |
| Capital One | 2 | 2026 | R2 | 2 defensible (29 w) |
| Diamondback / Fiserv / Shire / T-Mobile | 1 each | 2015–2020 | R2 | 4 defensible (36–1,561 w) |

Six filers — Vertex, ADP, Eversource, AIG, Salesforce, UnitedHealth — are
**70 of the 83 (84%)**. Stratum: core 69, extension 14. Sector: healthcare 24,
financials 22, tech 22, utilities 14, energy 1.

Per-filer handler count implied: **two named dialects** cover the two hard
cases (Eversource's Part-II-anchor, AIG's dangling-1A-TOC), and both are
handled by the *generic* guards below rather than by filer-specific code — so
zero new per-filer handlers are actually required.

---

## 5. Does the full census change P4's fix ordering? **Yes — the guards, not the ordering, are load-bearing.**

P4 recommended: **F1 first; F2 scoped to R3 only, with span guards.**
Measured on the whole population, both halves need amending:

**(a) "F1 first" is not safe unguarded.** 13 of 71 R2 rows (18.3%) — every
Eversource row — get a resolving anchor that points at the wrong section, and
the resulting span clears the word floor, the char gate and both length bands.
Unguarded F1 injects 13 rows of Legal-Proceedings-labelled-as-Risk-Factors:
precisely the "extracts wrong is worse than fails loudly" violation P4 correctly
charged against F2. **F1 needs G1 (head check) before it is safe.** With G1,
F1 is 58/58 correct on this population.

**(b) "F2 scoped to R3" is exactly backwards here.** On the R3 arm F2 is
**0 for 12** — every one garbage, every one caught by G2. On the *R2* arm,
where P4 does not propose F2 at all, F2 is the only thing that recovers
Eversource correctly, 13 for 13. So F2's value is not "R3-only"; it is
"whenever guarded-F1 fails its head check."

**(c) The scope condition that matters is TOC presence, not the arm.** I ran
the guarded ladder over the R1 population too, as a bound on any future
"fall through on `EXPECTED_ABSENT`" proposal:

| population | admitted by the guarded ladder | correct (hand read) | wrong |
|---|---|---|---|
| R2+R3 (83) | **71** | **71** | **0** |
| R1 (696) | 131 | 42 | **89** |

The same two guards are perfect on rows where the item is in the TOC and
**68% wrong** on rows where it is not. Guards are necessary; the
item-is-in-the-TOC precondition is what makes them sufficient. **Any fix must
stay scoped to R2/R3 and must not fire on R1.**

### Recommended pre-F4 fix package (replaces P4 §11 item 1's ordering)

1. **G1 + G2 as a shared span validator**, applied to *both* location paths.
   Small, readable, no per-filer branching:
   - G1: rendered span must open on an `item 1A … risk factors` heading within
     40 chars;
   - G2: the end-guarded span must not terminate at end-of-document.
2. **F1′ = "first matching TOC entry whose anchor RESOLVES"** (today: first
   matching entry, full stop), **gated on G1+G2**. Recovers 58 rows.
3. **F2′ = fall through to the shipped heading-regex fallback, gated on the
   same G1+G2, and only when a matching TOC entry existed** (R2/R3). Recovers
   the 13 Eversource rows; correctly rejects all 12 AIG rows.
4. **The 12 AIG rows stay loud FAIL rows** with an honest reason code. No
   mechanism in the current codebase can extract them without a fetch.
5. **Rename `EXPECTED_ABSENT`** to something that asserts what was measured
   (`ITEM_ABSENT_FROM_TOC`) rather than filer intent — independently justified
   by the 42 R1 rows where the filer *did* disclose Item 1A.
6. **Do not adopt P4's 0.5–2×-median band as a production guard for
   `(10-Q, RISK_FACTORS)`.** It rejects 49 of 58 hand-verified-correct spans.
   The floors themselves (15 w / 30 chars) need **no change**: 58/58 clear them.

Ordering, restated in one line: **guards first, then F1′, then F2′ — scoped to
R2/R3.** Under this package the census's 83 misclassified rows resolve as
**71 recovered with defensible spans (125,156 words) + 12 correctly failing
loudly**, and zero R1 rows change status.

**One caveat I am not hiding:** G2's "no EOF termination" rule was chosen after
seeing this population, and it separates it perfectly (58/12, zero errors)
partly because it was chosen against it. Its *mechanism* is principled — Part
II Item 1A is never the last item in a 10-Q — but on an independent slice it
will not be perfect. It should ship as a **flag that downgrades confidence and
routes to review**, not as a silent filter, exactly as every other F3 length
rule does.

---

## 6. Artifacts

All under `data/f3/p4b_ea_census/`:

| file | what |
|---|---|
| `p4b_ea_census.py` | the full-population replay (P4's method, extended); resumable, cache-only, 6-way parallel |
| `census_rows.jsonl` | raw per-row census output, 779 lines, one per accession |
| `p4b_verdicts.py` | derived columns, guards, band recalibration, the hand-read assertion |
| `ea_census_779.csv` | **the deliverable — all 779 verdicts**, 31 columns incl. `verdict`, `best_words`, `head_opens_on_item1a`, `guarded_span_still_ends_at_eof`, `clears_word_floor_15`, both band verdicts, `defensible_span`, `best_head` |
| `p4b_ladder.py` | the guarded-ladder measurement, run over R1 as well as R2/R3 (§5c) |
| `census_run.log` | run log — 779 rows in 231 s, 0 errors, 0 cache misses |

**Discipline:** 0 live GETs · 0 API spend · 0 GPU · writes confined to
`data/f3/p4b_ea_census/**` and this file · DB read-only · `extract.py` and
every P0–P4 artifact and ledger byte-unchanged · every filing's true public
`filing_date` carried through unmodified.
