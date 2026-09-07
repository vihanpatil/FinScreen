# P3 completion report — mandatory extraction QA over the P2 corpus

**Stage:** P3. **Agent:** extraction-qa-engineer (Opus). **Date:**
2026-08-27. **Status: DONE.** Brief: `F3_PROGRESS.md` P3 row; protocol:
`data/f3/F3_SPEC.md` §7–§9 and §12; inputs: `data/f3/status/P1_impl.md`
§4–§5, `data/f3/status/P2_runs.md`.

**Network: ZERO GETs.** Every document read came from `data/raw/documents/`
through `extract.read_cached_document` (which raises `CacheMiss`, never
fetches); every metadata row from `data/filings_metadata_e2.db` opened
`mode=ro`. **D2 got a census, not a fetch** (§6.1).

**Nothing outside `data/f3/p3_qa/` and this file was written.** `extract.py`,
`chunk.py`, the corpus, all five P2 artifacts, the E1 frozen artifacts and
every ledger (`F3_PROGRESS.md`, `HANDOFF.md`) are byte-unchanged; P2's
`population_gate.csv` was copied-and-verdicted to a new path, never
overwritten.

**GPU overlap:** the H3v2 relabel job (`finetune/relabel_e1.py --v12`,
PIDs 79086/79087) was alive at start and alive at finish (§11).

---

## 0. Headline verdict

**The corpus is FIT FOR F4, with three named carve-outs and one class that
must be fixed or excluded before labeling.**

| | measured |
|---|---|
| Attempts → sections | 30,475 → 28,900. Arithmetic closes: 25,245 OK + 3,655 FLAGGED + 796 FAIL + 779 EXPECTED_ABSENT = 30,475 |
| Located rate (OK+FLAGGED / attempts) | 8-K EX-99 **99.9%** · 8K_BODY **100%** · 10-Q MDA 95.2% · 10-K RF 95.1% · 10-K MDA 94.9% · 10-Q RF 87.3% (10.4% of the shortfall is the documented `EXPECTED_ABSENT` Item-1A omission) |
| Spot read, tier T1 BASE (the only base-rate slice) | **16/16 CORRECT**; 95% Wilson upper bound on the error rate **19.4%** |
| Spot read, tier T2 NEW/OLD (new filers + pre-2019) | **16/16 CORRECT**; same bound. **The pre-2019 / new-filer degradation the plan predicted did not show up in the base tiers.** |
| Spot read, tier T3 FLAG (deliberately unrepresentative) | 3/8 not-CORRECT → triggered the pre-committed extension → T3_EXT 5/10 not-CORRECT |
| Sections carrying **no** flag and **not** hand-verifiable as wrong | 25,245 |

**The one class that must be fixed or excluded: 2 rows of pure font-encoded
garbage sitting at `extraction_status=OK`, `extraction_confidence=high`,
zero flags, 3,333 and 2,609 words** — Ford `0000037996-18-000082` and
`0000037996-19-000065` (§6.2). They are the exact failure the project's hard
rule names ("a section that extracts wrong is worse than one that fails
loudly"), they will produce labeling chunks of garbage, and **the
non-ASCII-ratio measurement P1 proposed does not find them.** One measured
detector does (§6.2). This is P4/main-session proposal **N1**.

The three carve-outs, all sized below and none of them corpus-blocking:
**(a)** 796 FAILs, 82% of them in 40 named per-filer clusters, of which
**186 are recoverable exactly** by three small code fixes and ~320 more by
four named per-filer handlers (§2); **(b)** ~12M
words stranded in table-shaped/word-per-line sections that produce almost no
labeling chunks (§5, §8); **(c)** the D2 external-document class, now
measured at **121 rows across 17 filers, spread evenly 2016→2026** — not a
pre-2019 legacy (§6.1).

---

## 1. What I actually read (not just counts)

Reads are model judgements (HANDOFF §7), recorded as such.

| read | n | where |
|---|---|---|
| §9 spot-read evidence cards, tiers T1/T2/T3 | **40** | `p3_qa/qa_cards.txt`, verdicts in `p3_qa/qa_verdicts.csv` |
| §9.4(3) one-time extension, tier T3_EXT | **10** | `p3_qa/qa_cards_ext.txt`, `p3_qa/qa_verdicts_ext.csv` |
| §8.2 floor-gap hand-read, `(10-K, MDA)` band [250, 1500) | **4 (all of them)** | §4.1 |
| §8.2 floor-gap hand-read, `(10-K, RISK_FACTORS)` band [250, 2000) | **19 (all of them)** | §4.2 |
| §9.5 triage diagnosis, cached primary documents opened and inspected by hand | **16** | §2 — Colgate, Citigroup, Edison, Emerson ×3, AEP ×2, BNY Mellon, Morgan Stanley, US Bancorp, KO, Danaher, ADP, UNH, Salesforce, Humana, Welltower, SLB |
| representative reads for the D2-on-`RISK_FACTORS` census | **9** | §6.1 — Abbott, US Bancorp, Wells Fargo, McDonald's, J&J, Aetna, BNY Mellon, AT&T, TWDC |
| mojibake class, full text inspected | **4 (all of them)** | §6.2 |
| **total sections/documents read by hand** | **~102** | |

**What I did NOT read.** I did not read any of the 25,245 OK rows beyond the
16 drawn for T1 and the 16 for T2 — the base rate rests on 32 reads and its
Wilson bound is stated, not hidden. I did not hand-read the 1,509 gate rows
(§3 explains why that is a census by rule, not a choice). I read **1 of the
44** `mda_stub_resolved` rows; the other 43 are screened mechanically only
(§7.3). I did not read any of the 105 combined-book candidates beyond the
Simon anchor's metrics.

---

## 2. Per-filer failure triage (§9.5) — the 796 FAILs

`p3_qa/p3_triage.py`, `p3_qa/fails_all.csv`, `p3_qa/fail_clusters.csv`,
`p3_qa/rollup_tier1_filers.csv`, `p3_qa/dialect_probe.csv`.

### 2.1 Shape of the failure population

| reason_code | FAIL rows | pre2019 | 2019+ |
|---|---|---|---|
| `no_toc_and_no_heading_match` | 397 | 164 | 233 |
| `item_absent_from_toc` | 376 | 189 | 187 |
| `empty_after_extraction` | 12 | 6 | 6 |
| `anchor_span_below_min_chars` | 11 | 8 | 3 |

**Failure is a filer property, not an era property.** 67 filers carry all
796; the top 10 carry **60.8%**; 40 clusters of n≥7 cover **653 of 796
(82%)**, and 54 clusters of n≥4 cover **717 (90%)**. Sixteen of those
clusters run the **full 2015→2026 window at a 100% fail rate** — the
Prologis/PSEG shape, at scale:

| filer | form/section | n | window | reason |
|---|---|---|---|---|
| Colgate-Palmolive | 10-Q MDA | 34 | 2015–2026 | `no_toc_and_no_heading_match` |
| Citigroup | 10-Q MDA **and** 10-Q RF | 34 + 34 | 2015–2026 | `no_toc_and_no_heading_match` |
| Edison International | 10-Q MDA **and** 10-Q RF | 34 + 34 | 2015–2026 | `no_toc_and_no_heading_match` |
| Emerson Electric | 10-Q MDA | 34 | 2015–2026 | `no_toc_and_no_heading_match` |
| Bank of New York Mellon | 10-Q MDA | 34 | 2015–2026 | `item_absent_from_toc` |
| American Electric Power | 10-Q MDA | 34 | 2015–2026 | `item_absent_from_toc` |
| Morgan Stanley | 10-Q MDA | 29 | 2017–2026 | `item_absent_from_toc` |
| US Bancorp | 10-Q MDA | 27+7 | 2015–2026 | both codes |
| Citigroup / Edison / Emerson | 10-K MDA + RF | 11 each | 2016–2026 | `no_toc_and_no_heading_match` |

### 2.2 The single biggest finding: `item_absent_from_toc` is a **conflated
reason code**, and the majority of it is a code defect, not a filer dialect

`extract.locate_item_section_by_anchor` returns `None` in three distinct
ways and `run()` reports all three as `item_absent_from_toc`:

```python
    start_idx = None
    for i, entry in enumerate(toc_entries):
        if entry.item_no != target_item_no: continue
        if required_keywords:
            ... if no keyword match: continue
        start_idx = i
        break                       # <-- FIRST match wins, unconditionally
    if start_idx is None: return None            # (1) genuinely absent
    start_offset = find_anchor_offset(html_text, start_entry.anchor_id)
    if start_offset is None: return None         # (2) DANGLING anchor id
    ...
    if end_offset <= start_offset: return None   # (3) degenerate span
```

Cases (2) and (3) are **not** "item absent from TOC". Verified by replaying
the exact code path on seven cached documents:

| filing | filer | matching TOC entries | first entry resolves? | a LATER identical entry resolves? |
|---|---|---|---|---|
| `0000313616-16-000145` | Danaher 10-K RF | 2 | **no** (`s87C39EC8…`) | **yes**, offset 238,718 (`s4b44ee0d…`) |
| `0000008670-19-000005` | ADP 10-Q MDA | 3 | **no** | **yes**, offset 1,485,459 |
| `0000731766-17-000028` | UnitedHealth 10-Q MDA | 3 | **no** | **yes**, offset 1,382,439 |
| `0001108524-16-000128` | Salesforce 10-Q MDA | 2 | **no** | **yes**, offset 1,265,563 |
| `0000049071-16-000117` | Humana 10-K RF | 2 | **no** | **yes**, offset 352,737 |
| `0000766704-15-000043` | Welltower 10-Q MDA | 1 (`gmnh108`) | **no** | no → case (3)/(2) |
| `0000021344-18-000008` | Coca-Cola 10-K MDA | 3 | **no** | **no** — all three share one dangling id |

The pattern is a Workiva/EDGAR-filer-agent HTML shape in which each TOC row
carries **two** `<a href="#…">` links — an upper-case-hex id that is only
ever *referenced*, and a lower-case-hex id that is actually *defined*. The
extractor takes the first, gets `None`, and gives up **without trying the
next identical entry**.

- **Fix F1 — "try every matching TOC entry, not just the first."** Loop over
  all `(item_no + keyword)` matches and take the first whose `anchor_id`
  actually resolves. ~6 lines inside one function. This is not a per-filer
  handler; it is a bug.
- **Fix F2 — "fall through to the heading fallback when the anchor path
  returns `None`."** Today a TOC that parses but yields no usable anchor
  short-circuits the heading-regex fallback entirely. Coca-Cola (all three
  entries dangling) is the case F1 alone does not fix.

**Exact census — `p3_qa/p3_fail_recovery.py`, all 784 periodic FAIL rows,
595 cached documents, 0 read errors, 1,740 s.** Every row's cause was
determined by replaying `extract.py`'s own locate path; the dialect probe's
~148 estimate (§2.3) is confirmed to the row.

| cause | `item_absent_from_toc` (376) | `no_toc_and_no_heading_match` (397) | `anchor_span_below_min_chars` (11) |
|---|---|---|---|
| **R1** no matching TOC entry (genuinely absent) | 228 | 397 | 0 |
| **R2** first anchor dangling, **a later identical entry resolves** | **116** | 0 | 0 |
| **R3** every matching anchor dangling | **32** | 0 | 0 |
| **R4** degenerate span (`end ≤ start`) | 0 | 0 | **11** |

**148 of the 376 `item_absent_from_toc` FAILs (39.4%) are mislabelled** —
the item *is* in the TOC with the right number and the right title keyword.

And the recovery is exactly quantified, because the census also evaluated
what each fallback would have found:

- **All 116 R2 rows and all 32 R3 rows have ≥1 hit for the CURRENT,
  UNCHANGED fallback heading pattern** (`c_cur > 0` in 148/148). So **F2
  alone — a fall-through, with no regex change whatsoever — recovers all
  148.** F1 then upgrades 116 of them from a low-confidence fallback slice
  to a proper anchor span, which matters because the fallback carries its
  own *last-match* defect (§7.2).
- R2's 25 filers: ADP 14, PMI 10, FIS 10, Humana 10, Salesforce 8, UnitedHealth 8, Danaher 8, Apache 8, Coca-Cola 8, Caterpillar 6, Pfizer 5, Zoetis 4, NextEra 3, PNC 2, Alphabet 1, Diamondback 1, Williams Partners 1, …
- R3's 6 filers: Welltower 12, AIG 6, Honeywell 6, Concho 4, IBM 3, Walgreens 1.

**For the 625 R1 rows, what the candidate fallback widenings would add,
measured (incremental, in order):**

| candidate | rows it newly locates | filers |
|---|---|---|
| shipped pattern already hits | 81 | (these fail for a different reason downstream) |
| **+ dash/en-dash in the label→title gap (D9)** | **+38** | Emerson 22, MercadoLibre 10, Apache 5, Eversource 1 |
| + a 60-char line-break-tolerant gap | **+43** | |
| + bare-title line with no item label at all | +281 | **NOT recommended as a blanket rule** — this is exactly E1's loose-heading trap |
| **nothing any candidate finds** | **182** | BNY Mellon 34, Citigroup 30, Emerson 25, Edison 24, Colgate 15, ExxonMobil 14, Howmet 13, Apache 12, Freeport 11, TI 3, AT&T 1 |

The 182 "nothing found" rows are not a mystery: they are D10 (plural
`Items 2 and 3.`, which no `item\s*N` pattern can match) and D7
(Citigroup's no-item-label body), both named below.

### 2.3 The dialect classes, named and sized

`p3_qa/p3_dialect_probe.py` probed **2 filings per cluster over 97 clusters
(150 probe rows, 137 documents, seed 20260827)** and recorded fixed
signatures; class sizes below are the probe class weighted by its cluster's
true size. Every class has at least one hand-read exemplar.

| id | dialect | est. FAILs | named filers | exemplar verified by hand | disposition |
|---|---|---|---|---|---|
| **D9** | item/title separated by `-` / en-dash: `ITEM 1A - RISK FACTORS`. The shipped `_heading_pattern` gap class is `[\s\xa0.:]{0,20}` — a hyphen blocks it. | **38 exact** | Emerson 22, Union Pacific 10, Apache, McDonald's, Eversource, Honeywell, Intel | `0000032604-21-000038` (spot-read card 36): heading present verbatim, section 37,275 words | **one-character-class change** in `_heading_pattern` |
| **D10** | **combined-item** rows/headings: `Items 1, 2, 3 and 4 - …`, `Items 2. and 3. Management's Discussion…`, `Items 2 and 3.` — the plural `Items` defeats `^item\s*[0-9]` | ~83 + Emerson 10-Q 34 | AEP 34, BNY Mellon 34, Emerson 34, Freeport 11, Apache | `0000004904-16-000102` (card 37) and `0000032604-16-000097` (card 41) | **small named handler / prefix-regex extension**; regulated utilities + banks |
| **D7** | 10-K with **no `Item` label anywhere in the body** — a `FORM 10-K CROSS-REFERENCE INDEX` maps item→page and the body uses narrative headings only | ~107 | **Citigroup 90**, Emerson | `0000831001-17-000038`: 178,189 words, **0** `Item 7`/`Item 1A` tokens, 0 TOC anchors | **documented acceptance** — locating this needs a bare-title heading match, exactly the loose pattern E1's lesson forbids. Recommend FAIL-and-name. |
| **D12/D15** | heading present but **line-broken or reversed**: Colgate's running page header `Management\n'\ns Discussion and Analysis of Financial\nCondition…` (never labelled `Item 2`); Edison's `RISK FACTORS\n30\nPart I, Item 1A` (label *after* the title) | ~110 + Colgate 34 | Edison 66, US Bancorp 27, Emerson 17, Colgate 34, Stryker 17, Merck 13 | `0000021665-17-000006`, `0000827052-17-000033` | **per-filer handlers**, 2–4 of them; a general fix here is the loose-regex trap |
| **D11** | columnar TOC: the item number lives in a **later table cell**, so `^item…` / `^N\.` never match the row prefix; the anchors found are a *different* index (Morgan Stanley's parse returns item_no 1…20) | ~74 | Morgan Stanley 14, ICE 11, MercadoLibre 10, Corning 9, Honeywell 7, US Bancorp 7 | `0000895421-21-000286`: TOC reads `Risk Factors │ 1A │ 12` | **one named handler** (accept a trailing `Part/Item/Page` column shape) |
| **F1/F2** (§2.2) | dangling-first-anchor / unusable-TOC, mislabelled `item_absent_from_toc` | **148 exact** | 28 filers: R2's 25 + R3's 6 (overlap Honeywell, Apache, Concho) | 7 filings, §2.2 table | **code fix, not a handler** |
| **SLB span** | anchor resolves but the computed span renders to 22 chars (`Item 1A. Risk Factors.`); the real 37-word cross-reference sits past the end boundary | 11 | SLB 2016–2019 | `0001564590-18-024846` (card 50), span `(2716778, 2717059)` | note as case (3) of §2.2; F2 covers it |
| **P5 near-empty EX-99** | 12 named F2 §5 rows | 12 | PNC ×7, Ford, MetLife, Cigna, Linde ×2 | card 47 (MetLife) | **correct as-is** — pinned by T21, must keep failing |

### 2.4 Triage disposition table (every class gets a disposition)

| class | size | basis | disposition | for whom |
|---|---|---|---|---|
| **F2** fall through to the fallback when the anchor path returns None | **148 exact** | R2+R3 census, `c_cur>0` in 148/148 | **FIX** — smallest change, largest recovery | P4 → main session |
| **F1** try every matching TOC entry, not just the first | **116 exact** (subset of the 148) | R2 census, 25 filers | **FIX** — upgrades those 116 from low-confidence fallback to anchor | P4 → main session |
| **D9** dash / en-dash in the label→title gap | **38 exact** | R1 census, `c_cur==0 & c_dash>0` | **FIX** (one character class) | P4 → main session |
| line-break-tolerant 60-char gap | **43 exact** | R1 census | **FIX, but measure the false-positive rate first** | P4 |
| **D10** combined-item (`Items 2 and 3.`) | ~102–113 | cluster sizes AEP 34 + BNY 34 + Emerson 34 + Freeport 11 | **NAMED HANDLER** ×1 (plural-aware prefix + heading) | P4 → main session |
| **D11** columnar TOC | ~74 | dialect probe | **NAMED HANDLER** ×1 | P4 → main session |
| **D12/D15** line-broken / reversed headings | ~144 | dialect probe | **NAMED HANDLERS** ×2–4, per filer | P4 → main session |
| **D7** Citigroup cross-reference-index body | ~90 (Citigroup) | 0 `Item` tokens in 178,189 words | **DOCUMENTED ACCEPTANCE** — fail loudly; a bare-title match is E1's forbidden loose pattern | recorded here |
| **R4** SLB degenerate span | **11 exact** | R4 census | end-boundary fix, or accept | P4 |
| P5 near-empty EX-99 | 12 | F2 §5, T21 | **CORRECT AS-IS** — must keep failing | pinned |
| residual singletons | 143 in clusters of n<7 | | **DOCUMENTED ACCEPTANCE** — 0.5% of attempts | recorded here |

**Recovery, measured not estimated.** The three mechanical fixes
(**F2 + F1 + D9**) recover **186 of 796 FAILs (23.4%) exactly**, with the
line-break-tolerant gap adding a further 43 (→ **229, 28.8%**). The named
handlers address a further ~320. **~250 rows — Citigroup's 90 plus the
long tail — are documented acceptances and should keep failing loudly.**
Nothing here is implemented; P3 did not touch `extract.py`.

---

## 3. Population-gate verdicts (§7.4)

Completed file: **`data/f3/p3_qa/population_gate_verdicted.csv`** (1,509
rows, all `verdict`/`verdict_note` filled). `data/f3/population_gate.csv`
is byte-unchanged.

**Row-count reconciliation, exact.** P0 censused **1,519** gate-eligible
selections; the shipped file has **1,509**. The 10 missing are gate-eligible
rows that FAILed `empty_after_extraction` before the gate ran — verified by
name: Ford `0000037996-19-000005`, PNC ×7 (`0000713676-17-000017`,
`0000713676-19-000020`, `0001193125-16-556144`, `-16-709397`, `-16-758662`,
`0001193125-17-073082`, `-17-283876`), MetLife `0001099219-23-000041`,
Linde `0001654954-19-012971`. Cigna and Linde `-24-013519` are the 2 of the
12 in sole-filing cells. **1,519 − 10 = 1,509.** ✔

**Why the verdicts are a census, not 1,509 reads.** §9.4(4) is explicit: a
named class gets a census, not more reading. So every row is verdicted from
a fixed decision table, published here, and the vocabulary is deliberately
**not** H4's A/B/C — those are hand-read judgements of document content and
these are not.

| verdict | rule | n | filers | pre-2019 | median words |
|---|---|---|---|---|---|
| `ACCEPT_MULTI_SIGNED` | WARN_MULTI, signature present, filer not a habitual pair-filer | **778** | 135 | 267 | 4,710 |
| `REVIEW_NOSIG` | WARN_MULTI_NOSIG **and** the filer does *not* habitually file pairs — highest priority | **357** | 109 | 115 | 1,921 |
| `REVIEW_NOSIG_HABITUAL` | WARN_MULTI_NOSIG but the filer files ≥2 earnings 8-Ks in ≥50% of its quarters | **159** | 4 | 65 | 3,488 |
| `REVIEW_NOSIG_SHORT` | WARN_MULTI_NOSIG and <400 w — overlaps the thin/pre-announcement class | **103** | 25 | 31 | 271 |
| `ACCEPT_MULTI_HABIT` | WARN_MULTI, signature present, habitual pair-filer (Pioneer 35, PNC 34, MetLife 26) | **95** | 3 | 38 | 8,929 |
| `ACCEPT_MULTI_SIGNED_SUPP` | WARN_MULTI, signature present, also `earnings_supplemental_diluted` | **17** | 7 | 3 | 7,402 |

**619 rows across 119 filers land in a REVIEW class** (41% of the gate
population). Concentration: Tesla 93, Pioneer 39, PNC 39, MetLife 27,
Ecolab 21, AbbVie 19, EQT 19, Diamondback 17, Occidental 15, EOG 13.

**The gate is doing its job, and I read one of its rows.** Spot-read card 33
— Tesla `0001628280-24-041816`, `WARN_MULTI_NOSIG`, 285 w — is a Production
& Deliveries release whose own text says *"Our net income and cash flow
results will be announced along with the rest of our financial performance
when we announce Q3 earnings."* That is exactly the population defect the
gate exists to surface, and the extraction itself is complete and correct.

**No gate row is dropped and no gate level suppresses extraction** — R1
holds in the shipped output: all 1,509 are in the corpus.

---

## 4. Floors and ceilings — recalibration read (§8.2)

Evidence table: `data/f3/length_distribution.csv` (published by P2, before
any of the reads below). Rule 8.1(2) governs: a floor moves only with the
measured distribution, a hand-read of the gap, the named rows that must
still fail, and before/after counts.

### 4.1 `(10-K, MDA)` floor **1,500** — HOLD. The pilot's overlap worry is refuted.

n = 2,321. **134 below the floor. Every single one of the 134 is
`extraction_method='incorporated_by_reference_unresolved'`; 130 of the 134
are under 250 words.** The band [250, 1500) holds exactly **4 rows**, and
per rule 8.4 I read all four:

| row | words | what I read | verdict |
|---|---|---|---|
| Pioneer `0001038357-20-000009` | 835 | correct `ITEM 7.` head; ends **mid-guidance-table** ("Effective tax rate 21% - 25%") | **TRUNCATED** |
| Concho `0001358071-16-000026` | 1,184 | correct head; ends mid-sentence `…included in "` | **TRUNCATED** |
| Concho `0001358071-17-000005` | 1,238 | identical shape | **TRUNCATED** |
| Linde plc `0001707925-18-000004` | 841 | *"Linde plc has not conducted any material activities other than those incidental to its formation"* — the pre-merger shell 10-K; ends cleanly on the forward-looking bullets | **CORRECT, genuinely short** |

F3_SPEC §8.3 worried that "genuine p5 ≈ 1,199 w overlaps the ceiling". At
corpus scale that is **false**: the pilot's 1,199-word p5 was a small-sample
artifact, and the only sub-1,500-word rows are stubs and truncations.
**Proposal: HOLD 1,500. Do not lower it** — lowering to 800 would un-flag
three real truncations. Before → after: **134 → 134** (no change).

### 4.2 `(10-K, RISK_FACTORS)` floor **2,000** — HOLD, and here is the cost of holding, in the open.

n = 2,325, 63 below floor. Band [250, 2000) holds 19 rows; **I read all 19**:

| what I read | n | verdict |
|---|---|---|
| Eaton Corp plc 2016–2022, 1,296–1,971 w — clean `Item 1A. Risk Factors.` head, clean end at the Notes cross-reference | 7 | **CORRECT, genuinely short** |
| 3M 2016–2019, 1,681–1,746 w — ends at `Item 1B. Unresolved Staff Comment`; head clipped by 1–2 chars (`s. \| Provided below…`) | 4 | **CORRECT** (cosmetic head clip) |
| Occidental 2016/2017, 1,793/1,933 w — ends at `ITEM 1B UNRESOLVED STAFF COMMENTS` | 2 | **CORRECT, genuinely short** |
| Consolidated Edison 2016, 1,987 w | 1 | **CORRECT** |
| AT&T 2016/2017/2018/2019, 985–1,138 w — *"Information required by this Item is included in the Annual Report under the heading 'Risk Factors' on pages 36 through 39"* + ~1,000 w of forward-looking boilerplate | 4 | **external-document pointer** (D2-on-RF, §6.1) |
| Texas Instruments 2020, 1,187 w — ends mid-sentence `…as listed in` | 1 | **TRUNCATED** |

**14 of 19 (74%) are benign.** A move to 1,000 would remove those 14 from
the review queue — and would also un-flag the TI truncation and three of
the four AT&T external-document pointers. **Proposal: HOLD 2,000.** The
whole flag population for this (form, section) is 63 of 2,325 rows (2.7%);
buying a 14-row-smaller queue by losing 4 real catches is the wrong trade
under R3 and under the hard rule that prefers a loud flag to a quiet
mistake. Before → after: **63 → 63**. This is a recalibration *considered
and rejected on evidence*, which is the point of doing it in the open.

### 4.3 `(10-Q, MDA)` floor **1,000** — HOLD.

n = 7,145, 92 below floor, 14 filers. The class is not "thin MD&As", it is
**two named extraction defects** (§7.2): AT&T 34 rows at a 333-word median
(the fallback's *last*-match rule landing on the final `— Continued` page
header), and 25 heading-only slices under 100 words (Union Pacific 10 @ 15 w,
TWDC 10 @ 13 w, Eversource 3 @ 45 w, AT&T 2). The floor is the only thing
catching them. **HOLD; before → after 92 → 92.**

### 4.4 `(10-Q, RISK_FACTORS)` floor **15** — HOLD, and it is measurably inert.

n = 6,554, **min 19 words, so 0 rows are flagged**. p25 = 39, p50 = 94;
**4,193 of 6,554 (64%) are under 250 words** — the legitimate
one-sentence cross-reference class, exemplified by three rows I read:
Chevron 59 w (card 3), Target 31 w (card 17), Humana 19 w (card 18), all
complete and correct. Raising the floor to 250 would flag 4,193 legitimate
rows. **HOLD at 15**, and record that its measured effect on this corpus is
zero flags — it is a tripwire, not a screen.

### 4.5 `8-K` floors — both already argued at P1, both confirmed at corpus scale.

- `EX99_PRESS_RELEASE` **250** (P1's raise from 50): 41 corpus rows flagged,
  which is exactly P1's predicted "0 → 41". H4's named survivors both clear
  it with margin: Tesla Q1-22 P&D `0001564590-22-013264` = **276 w**, KKR
  `0001140361-19-006520` = **384 w**. **HOLD.**
- `8K_BODY` **500**: 43 of 210, entirely caused by §5's item-2.02 slicing
  (4 pre-slice → 43 post-slice), which R2 rules is the intended effect.
  **HOLD.**

### 4.6 `MDA_STUB_WORD_CEILING` **1,500** — HOLD, and §8.4's pre-committed band read is satisfied.

The ceiling must sit above the longest observed stub and the band between it
and the `(10-K, MDA)` floor must be hand-read in full if ≤20 rows. The
ceiling **equals** the floor, so the band is empty by construction; the four
rows immediately below (§4.1) were read in full anyway. Longest confirmed
external-document stub: AEP `0000004904-23-000011` at 149 words (card 30) —
an order of magnitude under the ceiling. **HOLD.**

**Net: no floor and no ceiling moves at P3. Every one is a documented
hold with its before/after count and its gap read.**

---

## 5. Spot read (§9) — what was drawn, what was read, what the stopping rule did

Frozen manifests: `p3_qa/qa_manifest.json` (40 rows, seed 20260827, written
before the first card was opened) and `p3_qa/qa_manifest_ext.json` (10 rows,
seed 20260828). Verdicts: `p3_qa/qa_verdicts.csv`,
`p3_qa/qa_verdicts_ext.csv`. **Path deviation, declared:** the spec names
`data/f3/qa_manifest.json` / `qa_verdicts.csv`; this brief restricts writes
to `data/f3/p3_qa/`, so both live there. Content and freeze discipline are
unchanged.

| tier | n | not-CORRECT | rate | 95% Wilson |
|---|---|---|---|---|
| **T1 BASE** (SRS over OK) | 16 | 0 | 0.0% | [0.0%, 19.4%] |
| **T2 NEW/OLD** (6 pre-2019 new-filer periodic, 4 pre-2019 earnings, 3 2019+ new filers, 3 extension-stratum) | 16 | 0 | 0.0% | [0.0%, 19.4%] |
| **T3 FLAG** (one row per reason code, largest classes) | 8 | 3 | 37.5% | [13.7%, 69.4%] |
| **T3_EXT** (the one permitted extension) | 10 | 5 | 50.0% | [23.7%, 76.3%] |

**Tiers are never pooled.** There is no all-tier headline rate in this
report, by design.

### 5.1 The stopping rule, applied as written

1. *"The read is complete when all 40 drawn rows carry a written verdict."*
   → **All 40 carry a verdict.** Complete.
2. *"Escalation does not stop the read… ≥3 rows in a tier sharing a single
   diagnosable cause."* → **Did not fire.** T3's three not-CORRECT rows have
   **three different** causes (D9 dash separator; D10 combined-item TOC row;
   the heading-fallback matching a table-of-contents row). Each is censused
   mechanically anyway (§2.3, §7.2).
3. *"Exactly one extension is permitted, once: a tier whose 95% Wilson lower
   bound exceeds 10% gets +10 rows in that tier, seed 20260828."* →
   **T3_FLAG's lower bound is 13.7% > 10%. The condition FIRED, and I took
   the extension** — 10 rows, seed 20260828, drawn from the same frozen
   FLAGGED/FAIL frame (every reason code not already represented, one each,
   then SRS fill), reported as its own tier, never pooled. **No second
   extension was taken and none is permitted.**
4. *Prohibited actions* — none taken: no re-draw after seeing verdicts, no
   reading extra rows to find another example of a named class (every named
   class got a census instead), no floor moved on spot-read evidence
   (§4 argues floors from `length_distribution.csv` and its own gap reads).
5. Read completed; no unread drawn rows.
6. All verdicts recorded as model judgements.

### 5.2 The eight not-CORRECT rows, by name

| card | row | verdict | what decided it |
|---|---|---|---|
| 36 | Emerson `0000032604-21-000038` 10-K MDA | **WRONGLY-FAILED** | document contains `ITEM 7 - MANAGEMENT'S DISCUSSION AND ANALYSIS…` verbatim; the ` - ` separator blocks the fallback gap class. D9. |
| 37 | AEP `0000004904-16-000102` 10-Q MDA | **WRONGLY-FAILED** | TOC row is `Items 1, 2, 3 and 4 - Financial Statements, Management's Discussion and Analysis…`. D10. |
| 39 | Union Pacific `0000100885-16-000339` 10-Q MDA, 15 w | **EMPTY-OR-BOILERPLATE** | the whole "section" is `Item 2.\nManagement's Discussion…\n20\n﻿` — that `20` is a **page number**. The fallback matched a TOC row. |
| 41 | Emerson `0000032604-16-000097` 10-Q MDA | **WRONGLY-FAILED** | heading is `Items 2 and 3.\nManagement's Discussion and Analysis…`. D10, heading variant. |
| 42 | NIKE `0000320187-25-000151` 10-Q MDA, 666 w | **WRONG-SECTION** | the "MD&A" is Part II: `ITEM 1A. RISK FACTORS … ITEM 2. UNREGISTERED SALES … ITEM 6. EXHIBITS … SIGNATURES`. Caught by **three** flags at medium confidence — the C14/D4 guard working. 21 NIKE rows in the class (§7.4). |
| 46 | IBM `0001047469-18-001117` 10-K MDA, 13 w | **EMPTY-OR-BOILERPLATE** | the entire section is the heading line and nothing else. |
| 48 | Warner Media `0001193125-18-053619` 10-K MDA, 47,927 w | **OVER-CAPTURED** | head reads `…- (Continued)` (resolver landed mid-section); the slice then runs through `TIME WARNER INC. NOTES TO CONSOLIDATED FINANCIAL STATEMENTS - (Continued)` and ends inside the **internal-control-over-financial-reporting report** (Item 9A). `medium` confidence, in the corpus. |
| 50 | SLB `0001564590-18-024846` 10-Q RF | **WRONGLY-FAILED** | anchor resolves at 2,716,750 but the span renders to 22 chars; the real 37-word cross-reference sits past the end boundary. |

**Two things this table is evidence FOR.** First, the flag machinery is
working: 6 of the 8 are FLAGGED or FAILed loudly and 2 of the remaining are
FAIL rows — **none of the eight is a silent OK/high mistake.** Second, T3 is
deliberately drawn from the flagged population, so a 37–50% not-CORRECT rate
there is the *expected* shape, not a corpus-quality number. The corpus-quality
number is T1's 0/16.

### 5.3 One thing the base tiers did NOT show

`EXPANSION_PLAN` §5 F3 predicted anchor-TOC coverage degrading in pre-2019
filings. **T2 was built to catch that and found nothing**: 16/16 CORRECT
across 6 pre-2019 new-filer periodic sections, 4 pre-2019 earnings, 3 2019+
new filers and 3 extension-stratum sections (Autodesk 2017, Expand Energy
2016, McKesson 2017, Walgreens 2017, Target 2017, Humana 2017, Emerson 2017,
Lam 2017, Northrop 2017, Energy Transfer 2016, CrowdStrike 2021, Uber 2020,
EIDP 2026, AEP 2023, Realty Income 2023, Vistra 2023). The corpus-wide
located rates agree: pre-2019 is 2–8 points below 2019+, not a cliff
(10-K MDA 91.3% vs 96.4%; 10-Q RF 81.9% vs 89.9%). **The era effect is real
but small; the filer effect is large.** That reframing is the main thing
P3 changes about the plan's expectations.

---

## 6. The five P1 carried-forward censuses

### 6.1 D2 — MD&A (and Risk Factors) incorporated from a different DOCUMENT. **CENSUS ONLY. No fetch.**

**On 10-K MD&A** (`reason_code = mda_stub_external_document`): **80 rows,
15 filers, 100% 10-K MDA.**

| filer | n | window | median words |
|---|---|---|---|
| US Bancorp | 11 | 2016–2026 | 49 |
| Wells Fargo | 11 | 2016–2026 | 42 |
| Progressive | 11 | 2016–2026 | 35 |
| Bank of New York Mellon | 11 | 2016–2026 | 53 |
| IBM | 7 | 2020–2026 | 32 |
| RTX | 5 | 2016–2020 | 50 |
| CVS Health | 4 | 2016–2019 | 62 |
| Nucor | 4 | 2016–2019 | 38 |
| Sherwin-Williams | 4 | 2016–2019 | 52 |
| AEP 3 · AT&T 3 · Walmart 2 · Verizon 2 · Sempra 1 · Aetna 1 | 12 | | |

Per-year: 2016 **12** · 2017 12 · 2018 9 · 2019 8 · 2020 6 · 2021 5 ·
2022 6 · 2023 6 · 2024 6 · 2025 5 · 2026 **5**.

**This is the number that should change the fetch conversation: D2 is not a
pre-iXBRL legacy.** Four filers — US Bancorp, Wells Fargo, Progressive, BNY
Mellon — do it in **every one of the 11 years**, and five rows land in 2026.

**A new finding: D2 exists on `RISK_FACTORS` too, and F3 cannot see it.**
`stub_language_present` is computed **only** for `(10-K, MDA)` — it is 0 for
all 2,325 10-K RF rows, all 7,145 10-Q MDA rows, all 6,554 10-Q RF rows and
all 10,555 8-K rows. So there is no `*_stub_external_document` reason code
outside 10-K MD&A. Measured: **44 10-K RISK_FACTORS rows under 250 words
(7 filers) + 4 long AT&T pointer rows = 48 rows**, carrying only
`below_length_floor`. I read one representative per filer:

| filer | n | the bytes |
|---|---|---|
| US Bancorp | 11 | *"Information in response to this Item 1A can be found in the Company's 2015 Annual Report on pages 156 to 166"* |
| Wells Fargo | 11 | *"…in the 2015 Annual Report to Stockholders under 'Financial Review – Risk Factors.'"* |
| BNY Mellon | 11 | *"…set forth in the Annual Report under 'MD&A – Risk Factors'"* |
| AT&T | 4 | *"…included in the Annual Report under the heading 'Risk Factors' on pages 36 through 39"* |
| McDonald's | 2 | *"Risk Factors and Cautionary Statement… Pages 3, 25-30"* |
| J&J | 1 | *"…the factors set forth in **Exhibit 99** to this Report"* — an in-filing exhibit, also not cached (§1.3) |
| Aetna | 1 | *"…the 'Forward-Looking Information/Risk Factors' section of the MD&A… of the Annual Report"* |
| **Abbott** | **7** | **NOT a stub** — the fallback matched the phrase `Item 1A. Risk Factors" of this Form 10-K` inside a forward-looking-statements sentence. A *wrong slice*, separate defect. |

**D2 total for the main session's decision: 80 (10-K MDA) + 41 (10-K RF,
excluding Abbott's 7 mis-slices) = 121 sections across 17 distinct filers, evenly
distributed 2016–2026.** Recovering them needs the filing's *other*
documents, which `filing_documents` does not index for periodic forms
(§1.3) — i.e. a bounded one-time EDGAR fetch of ~121 accessions' exhibit
sets. **That decision is the main session's (F3_SPEC §13.1). F3 did not
fetch and does not recommend here; it hands over the count.** Until then the
80 are FLAGGED and visible; the 41 are visible only via the length floor,
which is proposal **N2** (§9).

### 6.2 Mojibake — **P1's proposed measurement does not work; a different one does.**

P1 suggested "a cheap non-ASCII-ratio measurement would size the class."
Measured over all 28,900 sections (`p3_qa/p3_text_metrics.py`):

- `nonascii_ratio`: p50 0.0023, p99 **0.016**, max 0.0585.
- The P1-named anchor row, Freeport `0000831259-24-000026`, scores
  **0.0136 — below the corpus 99th percentile.** The proposed screen would
  have missed the one row it was designed for. The garbage is ASCII
  punctuation (`! "#$%&'() *+) ,-./`), not high code points.

**What does work: the share of private-use / non-printable characters
(`ctrl_ratio`).** The distribution is bimodal with a ~60× gap:

| row | words | ctrl_ratio | status / confidence | flags |
|---|---|---|---|---|
| **Ford `0000037996-18-000082`** (2018-10-24) | **3,333** | **0.335** | **OK / high** | **none** |
| **Ford `0000037996-19-000065`** (2019-07-24) | **2,609** | **0.242** | **OK / high** | **none** |
| Freeport `0000831259-24-000026` | 167 | 0.229 | FLAGGED / medium | gate + below_length_floor |
| Digital Realty `0001297996-16-000203` | 108 | 0.016 | FLAGGED / medium | gate + thin + below_floor |
| *next highest row in the corpus* | — | **0.0037** | — | — |

The two Ford rows decode as Caesar-shifted PDF font maps —
`)RUG\x03'HOLYHUV\x037KLUG\x034XDUWHU` is *"Ford Delivers Third Quarter"*.
They are **3,333 and 2,609 words of garbage at OK/high with zero flags, and
`prose_word_share = 1.0`**, which means they will be packed into labeling
chunks as if they were clean prose. Neither the population gate, nor any
floor, nor the head checks, nor prose-share sees them.

**Class size: 4 rows; 2 unprotected.** Detector: `ctrl_ratio ≥ 0.02` selects
exactly 3 rows with a 60× margin to the next. Proposal **N1** (§9).

### 6.3 Simon combined release+supplemental book — P1's named miss is **systematic**, not a one-off.

The shipped §6 `supplemental_tail_share ≥ 0.5` flag fires on 419 rows
corpus-wide. **On Simon Property it fires 0 times in 44 rows** — every
earnings 8-K from 2015-07-24 to 2026-08-10, 13,442–16,964 words,
`prose_word_share` 0.000–0.234, **46–58** occurrences of the
`4Q 2020 SUPPLEMENTAL`-shaped page header per document. P1 diagnosed the
cause correctly (the only whole-line `SUPPLEMENTAL INFORMATION` heading is
on the title page, inside the first 20%); the census shows it is Simon's
standing format for 11 years, not a single filing.

Broader class, measured (`word_count ≥ 8,000` **and**
`prose_word_share < 0.35` **and** ≥5 supplemental page-header hits):
**105 rows, 12 filers — 78 of them missed by the shipped flag.**

| filer | n | median words | median prose share | already flagged |
|---|---|---|---|---|
| Simon Property | 44 | 15,272 | 0.185 | **0** |
| BlackRock | 21 | 8,596 | 0.296 | 20 |
| BNY Mellon | 11 | 13,923 | 0.185 | **0** |
| Walgreens 6 · Aon 5 · PNC 5 · CVS 4 · Activision 3 · Digital Realty 3 · Welltower 1 · EMC 1 · Express Scripts 1 | 29 | | | 7 |

Negative anchors hold: **AvalonBay 0/45 and Prologis 0/45** flagged, median
prose share 0.52 / 0.61 — the screen does not fire on the clean
two-exhibit shape. **Disposition: measured, not fixed.** §6 forbids
truncating this class and P3 does not propose truncating it; the class is a
*visibility* problem for F4 (a 15,000-word section that yields ~2,800 prose
words). Proposal **N3** (§9).

### 6.4 Tesla thin P&D — the floor's known false-alarm class, now measured.

P1 named "11 genuine-but-thin Tesla P&D releases". Corpus-wide: Tesla has
**93 earnings-8-K rows, of which 43 are Production & Deliveries releases
under 600 words** (2015-07-02 → 2026-07-02, one per quarter), **12 of them
below the raised 250-word EX-99 floor**. All 43 are `WARN_MULTI_NOSIG`,
all `medium` confidence, **none dropped**. H4's named survivor Tesla Q1-22
`0001564590-22-013264` measures **276 w** and is *not* below-floor, as
required. The known non-release inside the class survives too: 2018-10-01
`0001564590-18-023716`, 67 w — the Musk employee e-mail P1 named.
**Disposition: correct as-is.** These are in the review queue by
construction and that is the intended cost of the 250-word floor.

### 6.5 Confidence semantics — the observation, quantified.

`extraction_confidence` × `reason_code` over all 30,475 attempts confirms
C6 is shipped literally: **`high` appears only on `reason_code = ok`
(25,211 rows)** and nowhere else.

- **1,387 rows carry `earnings_population_gate` as their primary reason
  code and are `medium` for that reason alone.**
- **1,337 corpus rows carry `earnings_population_gate` as their *only*
  flag — 12.7% of the entire 8-K corpus loses `high` purely because of
  which document was selected, not how well it extracted.**
- P1 flagged the conflation; P3 measures it and agrees with P1's own
  mitigation: `reason_code`, `population_gate`, `quarter_cell_size` and
  `results_signature_present` are all stored per row, so F4/F5 can condition
  on extraction quality and population membership **separately** without any
  change. **Disposition: measured, not changed.** Splitting confidence into
  two fields is a spec amendment, not a P3 edit — recorded as proposal
  **N4** for P4/main session, with the note that it is cosmetic given the
  columns already present.

---

## 7. Classes P3 found that were not on P1's list

### 7.1 Word-per-line rendering — the largest F4-facing finding

Found by reading, not by screening: spot-read card 12 (Apache
`0001193125-17-157723`, a complete and correct 4,546-word earnings release)
has `n_prose_paragraphs = 1` and `prose_word_share = 0.0101`, because the
exhibit renders **one word per line**
(`Delivered\nfirst-quarter\nproduction\nof\n481,000`). Card 34 (Waste
Management 10-Q MD&A) has the same shape in its tail.

Corpus-wide: **1,634 sections of ≥1,000 words with
`prose_word_share < 0.05`, across 136 filers, holding 11,983,216 words that
produce almost no labeling chunks.** Named heaviest: ICE 45, Chubb 43, AIG
43, Blackstone 42, Howmet 40, Walgreens 39, ExxonMobil 39, Cisco 38,
Goldman Sachs 36, Devon 35, SLB 34, Concho 33, Eversource 33, Microsoft 32,
Cigna 31, Honeywell 30. **17,718 of 28,900 sections have more than half
their lines at ≤1 word.**

**The extraction is correct** — every word is present and in order. The loss
is entirely in `chunk.py`'s 40-word line rule (C16 predicted the mechanism;
P3 measures the magnitude). This is F4's decision and §8 hands it over
quantified.

### 7.2 The heading-regex fallback's *last-match* rule

`locate_item_section_by_heading_regex` takes **the last** start-pattern
match, on the reasoning that content follows the TOC. For filers whose MD&A
carries a repeating page header the last match is the *final page*, not the
section start. Screening the 1,140 `heading_regex` rows against the
anchor-located median for the same (form, section) gives **150 suspiciously
short rows across 18 filers**; hand-reading representatives separates them:

| class | rows | verdict |
|---|---|---|
| **AT&T 10-Q MDA, 2015–2026, median 333 w** (anchor median 9,325) — head reads `Item 2. Management's Discussion… - Continued` | **34** | **systematically TRUNCATED** to the last page |
| Heading-only / TOC-row slices <100 w: Union Pacific 10 @ 15 w, TWDC 10 @ 13 w, Eversource 3 @ 45 w, AT&T 2 (+ JPM 1 at 104 w) | **25** | **EMPTY-OR-BOILERPLATE** (card 39, card 46 shape) |
| Abbott 10-K RF ×7 @ 83 w — matched `Item 1A. Risk Factors"` inside a prose cross-reference | **7** | **wrong slice** |
| Genuinely-short-and-correct (US Bancorp/Wells Fargo/BNY/MCD/Aetna 10-K RF stubs; Simon 18 and Colgate 12 10-Q RF cross-references @ 22–23 w) | ~72 | **correct** |

All are FLAGGED at `low` confidence, so none is silent. **Disposition:
documented; proposal N5 (§9) is a *prefer-first-match-with-sufficient-span*
rule, which is a behaviour change and therefore explicitly not a P3 edit.**

### 7.3 `mda_stub_resolved` can over-capture

44 rows were recovered by C7's resolver — a real win (JPMorgan 11 rows at
55,520–66,302 w, Southern Co 90,471 and 74,799 w, AEP 6, Chevron 6, XOM 7,
McDonald's 4, Verizon 3, HPE 2, Micron 1, Honeywell 1, Warner Media 1). Word
count alone cannot separate a genuine giant MD&A from an over-capture:
JPM's 60k-word MD&A is real (P1 verified it).

`prose_word_share` does separate them. Across the 44 resolved rows it runs
p10 0.404, p25 0.507, median 0.586, max 0.834 — **with exactly one outlier
at 0.101: Warner Media `0001193125-18-053619`**, which I read (card 48) and
confirmed runs past the MD&A through the notes to the financial statements
and into the Item 9A internal-control report. **1 confirmed over-capture of
44; the other 43 were not hand-read and are screened only by that one
statistic — stated as a limitation, not as a clean bill.**

### 7.4 `head_foreign_item` — the C14 guard, at corpus scale

51 rows, 7 filers, and it is **concentrated, not diffuse**: NIKE 21 (10-Q
MDA, 2019-10 → 2026-04, median 515 w — the Part II slice I read as card 42),
Allergan 11 (10-Q RF, 35 w), Tesla 8 (10-Q MDA, 1,172 w), SPDR Gold Trust 4,
MercadoLibre 3, **Bank of America 2 (10-K MDA, median 76,308 w)**, Realty
Income 2. C14's pilot estimate was 0.4% (1/263); the corpus rate is
**51/30,475 = 0.17%**. The guard found a real, systematic 21-filing NIKE
defect that nothing else in the pipeline sees. **Disposition: guard
validated; NIKE is a named-handler candidate (proposal N6).**

---

## 8. F4-scale re-derivation (§12) — the required deliverable

`p3_qa/p3_scale.py`, output `p3_qa/f4_scale.csv`. Method is §12.1's: stream
the corpus, import `chunk.normalize_paragraph`, `MIN_PROSE_WORDS = 40`,
`TARGET_WINDOW_WORDS = 350`, `MIN_FLUSH_WORDS = 100` and chunk.py's home
tie-break and packing arithmetic; keep only digests, word counts and
positions in memory. Each window rule is a **separate full run** because
restricting the corpus changes which occurrence is home.

**Two declared deviations.** (1) `chunk.extract_prose_paragraphs` reads
`row["ticker"]`, which is NULL at E2 scale (R6); the home tie-break uses
`cik` zero-padded to 10 characters in that slot — precisely the one-line F4
edit C3 predicts. (2) §12.3's "reflowed" variant asks for a
join-within-block-elements rule applied to ≥200 sections with an
extrapolation band; that rule needs each section's HTML span re-parsed,
i.e. a re-extraction. I substituted **`reflow_v1`**, a strictly additive
pure function of the stored text (keep every ≥40-word line unchanged;
additionally glue runs of consecutive shorter lines into ≥40-word blocks),
and ran it over **100% of the corpus with zero sampling error** instead of
200 sections with a band. The substitution is deliberate and is the reason
the reflow column is exact.

### 8.1 Measured, from the real 28,900-section output

| variant | window rule | sections | prose paras | canonical | dedup | **chunks** | zero-chunk sections |
|---|---|---|---|---|---|---|---|
| as-is | **W1 full** 2015-07→2026-08 | 28,900 | 1,303,855 | 830,851 | 36.3% | **199,403** | 5,729 (19.8%) |
| as-is | W1 full, **core only** | 20,832 | 972,109 | 603,226 | 38.0% | **146,571** | 3,925 |
| as-is | **W2 spell + 12-month margin** | 19,495 | 861,261 | 568,380 | 34.0% | **135,351** | 3,924 |
| as-is | W2, **core only** | 14,327 | 644,389 | 417,004 | 35.3% | **99,965** | 2,821 |
| as-is | **W3 spell only** | 16,029 | 711,867 | 475,588 | 33.2% | **113,398** | 3,147 |
| as-is | W3, **core only** | 11,779 | 527,442 | 346,258 | 34.4% | **83,010** | 2,303 |
| reflow_v1 | W1 full | 28,900 | 4,076,349 | 2,991,059 | 26.6% | **433,798** | 4,199 |
| reflow_v1 | W1 core | 20,832 | 2,977,013 | 2,150,145 | 27.8% | **314,211** | 2,815 |
| reflow_v1 | W2 | 19,495 | 2,764,040 | 2,079,150 | 24.8% | **299,294** | 2,904 |
| reflow_v1 | **W2 core** | 14,327 | 2,051,842 | 1,529,449 | 25.5% | **220,641** | 2,048 |
| reflow_v1 | W3 | 16,029 | 2,259,734 | 1,704,146 | 24.6% | **245,901** | 2,371 |
| reflow_v1 | W3 core | 11,779 | 1,671,176 | 1,251,469 | 25.1% | **180,734** | 1,688 |

Chunks by section type (as-is, W1 full): MDA 113,039 · RISK_FACTORS 48,428 ·
EX99_PRESS_RELEASE 37,467 · 8K_BODY 469. By era: pre-2019 52,772 ·
2019+ 146,631.

### 8.2 Labeling-time translation (§12.4)

Quoted at the **measured 1,068 chunks/h** from the epoch-1 held-out eval
(`finetune/runs/2026-08-21-eval-epoch1/`), **not** the ~950 chunks/h paper
band. Overnights = 10 labeling hours.

| | as-is hours | as-is overnights | reflow_v1 hours | reflow_v1 overnights |
|---|---|---|---|---|
| **W1 all** | 186.7 | 18.7 | 406.2 | 40.6 |
| **W1 core** | 137.2 | 13.7 | 294.2 | 29.4 |
| **W2 core** | **93.6** | **9.4** | 206.6 | 20.7 |
| **W3 core** | 77.7 | 7.8 | 169.2 | 16.9 |

### 8.3 The three numbers the member-spell-vs-full-window decision needs

1. **Cost.** W2-core → W1-core costs **+46,606 chunks = +43.6 h = +4.4
   overnights** (as-is). W3-core → W2-core costs +16,955 chunks (+15.9 h).
2. **What each rule loses.** W3 (spell only) loses the trailing-feature
   margin **and the corpus's only bankruptcy** — CIK 895126's two item-1.03
   8-Ks (2020-06-29, 2021-01-19) fall outside its spell (F2 §3.1). W3 is
   presented for completeness and loses on that ground, as F3_SPEC §12.2
   predicted. W2 keeps the margin and the IPO-late entrants; W1-core adds
   **46,606 chunks** of out-of-spell history over W2-core.
3. **The reflow gap is the real decision.** `reflow_v1` **2.18×** the as-is
   chunk count at W1 and **2.21×** at W2-core, and it cuts zero-chunk
   sections from 5,729 to 4,199. That gap is 11,983,216 words of
   table-shaped/word-per-line content (§7.1) that the current 40-word line
   rule discards. **F3's position: hand it over measured; the choice is
   F4's.**

### 8.4 How wrong the plan's estimate was

`EXPANSION_PLAN` §244 budgeted **"~70k new chunks"** (plus E1's 6,747).
Measured:

| against the plan's ~77k total | measured | multiple |
|---|---|---|
| W2 core, as-is (F4's likely default under scope-amendment 3) | 99,965 | **1.30×** |
| W1 core, as-is | 146,571 | **1.90×** |
| W1 full, as-is | 199,403 | **2.59×** |
| W1 full, reflow_v1 | 433,798 | **5.63×** |

The decision-audit's "plan's chunk count low 1.2–2.1×" band is **correct
for the core arms and too optimistic for the full window**. F3_SPEC's own
corrected estimate of ≈28,840 sections landed within 0.2% of the actual
28,900.

---

## 9. Proposals for P4 / the main session (nothing implemented here)

| # | proposal | evidence | size |
|---|---|---|---|
| **N1** | **Add a `mojibake` / `garbled_text` FLAG at `ctrl_ratio ≥ 0.02`.** Two Ford rows (3,333 w, 2,609 w) sit at OK/high/no-flags with `prose_word_share = 1.0` and will be labeled as prose. | §6.2; 60× separation from the next row | one measurement + one reason code; **the only corpus-quality item I would not ship F4 without** |
| **N2** | **Compute `stub_language_present` for `(10-K, RISK_FACTORS)` too**, and give it an external-document reason code. | §6.1: 41 rows, 6 filers, invisible today | mirrors existing MDA logic |
| **N3** | **Add the repeating-page-header marker to the §6 supplemental screen** (`<n>Q <yyyy> SUPPLEMENTAL`). | §6.3: recovers Simon's 44 rows and 78 of 105 combined-book rows; 0 false positives on the AvalonBay/Prologis negative anchors | one marker; measurement only, still no truncation |
| **N4** | Split `extraction_confidence` from population-gate membership (or record that the existing columns already suffice). | §6.5: 1,337 rows lose `high` for a non-extraction reason | spec amendment, cosmetic |
| **N5** | Change `locate_item_section_by_heading_regex` from *last match* to *first match with a sufficient span*. | §7.2: 34 AT&T truncations + 26 heading-only slices | behaviour change; needs its own before/after regression against T14's byte-identity pin |
| **N6** | Named handler for NIKE 10-Q (`head_foreign_item` ×21, 2019–2026). | §7.4 | one handler |
| **F1/F2/D9/D10/D11/D12** | The failure-recovery fixes and handlers of §2.3–§2.4. | §2 | 2 small code fixes + ~4 named handlers |
| **§13.1** | **D2 bounded-fetch decision — main session's, not F3's.** F3 hands over: **121 sections, 17 distinct filers, evenly spread 2016–2026, four filers doing it in every one of the 11 years.** | §6.1 | decision only |

---

## 10. Artifacts

All under `data/f3/p3_qa/`:

| file | what |
|---|---|
| `p3_triage.py` | §2.1 failure census; writes `fails_all.csv`, `fail_clusters.csv`, `rollup_tier1_filers.csv`, `rollup_tier2_filers.csv` |
| `p3_diagnose_fails.py` | single-filing cache-only diagnostic used for the 16 triage reads |
| `p3_dialect_probe.py` → `dialect_probe.csv`, `dialect_probe_classified.csv` | §2.3, 150 probe rows / 137 documents, seed 20260827 |
| `p3_fail_recovery.py` → `fail_recovery.csv`, `fail_recovery.log` | per-row R1/R2/R3/R4 cause census over all 784 periodic FAILs, COMPLETE (§10.1) |
| `p3_qa_sample.py` → `qa_manifest.json`, `qa_manifest.csv` | frozen §9.1 sample, seed 20260827 |
| `qa_manifest_ext.json`, `qa_manifest_ext.csv` | frozen §9.4(3) extension, seed 20260828 |
| `p3_fetch_text.py`, `qa_cards.txt`, `qa_cards_ext.txt` | the 50 evidence cards actually read |
| `p3_write_verdicts.py` → `qa_verdicts.csv`, `qa_verdicts_ext.csv` | the 50 per-row verdicts + notes |
| `p3_gate_verdicts.py` → `population_gate_verdicted.csv` | §3, 1,509 verdicted rows |
| `p3_text_metrics.py` → `text_metrics.parquet`, `text_metrics_joined.parquet` | §6.2/§6.3/§7.1 metrics for all 28,900 sections |
| `p3_scale.py` → `f4_scale.csv`, `f4_scale.log` | §8 |
| `corpus_meta.parquet` | text-free working copy of the corpus columns (21 MB), so no analysis ever loaded the 620 MB text column |
| `d2_riskfactors_scan.csv` | §6.1 RF-side scan |

### 10.1 The per-row failure-recovery census — COMPLETE

`p3_fail_recovery.py` replayed `extract.py`'s own locate path over **all
784 periodic FAIL rows (595 distinct cached documents), 0 read errors,
1,740 s**, labelling each with R1/R2/R3/R4 and evaluating three candidate
fallback patterns per row. Output: `p3_qa/fail_recovery.csv` (784 rows),
log `p3_qa/fail_recovery.log`. **It confirmed the dialect probe's ~148
estimate to the row (116 R2 + 32 R3 = 148)** and converted every recovery
number in §2.2–§2.4 from an estimate into an exact count. The 12 8-K FAILs
are excluded by construction (they are F2 §5's named P5 class, §2.3).

---

## 11. Discipline checks

| check | result |
|---|---|
| Live GETs | **0.** `extract.py` has no `EdgarClient` import on the F3 path; every read went through `read_cached_document`. |
| D2 | **census only** — 121 sections named and counted (17 filers); **no fetch, and no fetch recommendation**. |
| Writes | only `data/f3/p3_qa/**` and this file. `population_gate.csv` (179,439 bytes) unchanged; `extraction_audit.parquet`, `extraction_failures.csv`, `per_filer_rollup.csv`, `length_distribution.csv`, `run_manifest.json`, `data/filings_e2.parquet` unchanged; `extract.py` / `chunk.py` / `test_extract_e2.py` untouched; `F3_PROGRESS.md`, `HANDOFF.md` untouched. |
| E1 freeze | `data/filings.parquet`, `data/labels.parquet`, `data/universe.csv` read only. |
| Memory | the 620 MB corpus text column was **never** fully materialised — all text access streams through `pyarrow.iter_batches` at 200 rows; the working metadata copy is 21 MB. |
| GPU overlap | H3v2 `finetune/relabel_e1.py --v12` (PIDs 79086/79087) **alive at start and at finish**; no GPU/mlx job launched by P3. |
| Floors | **no constant changed.** Four holds, each with its distribution, its full gap read, its named must-still-fail rows, and its before/after count (all unchanged). |
| Spot read | 40 + 10 rows, both manifests frozen before their first read, stopping rule §9.4 applied as written including the one permitted extension. |
| Verdicts | model judgements (HANDOFF §7), never the owner's. |

---

## 12. Handed to P4

1. §2.2's claim — 148 of 376 `item_absent_from_toc` FAILs are a code
   defect, not an absent item — is now a full 784-row census, not an
   estimate. What it does NOT establish is that the recovered text would be
   *correct*: the census proves the fallback pattern *matches*, not that
   the resulting slice is right. Given §7.2's last-match defect, F2 alone
   could recover 148 rows as truncations. That is the seam to attack.
2. §6.2's `ctrl_ratio ≥ 0.02` threshold is fitted on n=4. The 60× gap is
   the argument; the sample is tiny. If P4 wants it defended, the honest
   move is a second measurement on an independent slice, not a re-fit.
3. §7.3 rests on **one** hand-read of 44 rows plus a single outlier
   statistic. The other 43 resolved stubs are unread.
4. §4.2's "hold 2,000" is a judgement that 4 real catches beat 14 benign
   flags. That is arguable and the numbers to argue it with are in the table.
5. §8's `reflow_v1` is my substitution for §12.3's named variant. It is
   exact where the spec's was extrapolated, but it is **not** the same rule;
   if P4 thinks the block-element variant is materially different, the
   re-extraction cost is the reason it was not run.
