# P5 — the pre-F4 corpus fix package: implementation, rebuild, regression

**Stage:** F3 P5 (owner rulings 2026-08-27, HANDOFF §3 — the fix package is a
named pre-F4 gate). **Agent:** extraction-qa-engineer (Opus).
**Date:** 2026-08-27/28. **Status: DONE.**

**Network: ZERO GETs.** Every document byte read through
`extract.read_cached_document` (raises `CacheMiss`, cannot fetch);
`data/filings_metadata_e2.db` opened `mode=ro`. All 34 shards report
`cache_miss = 0`; the merge manifest reports `network_gets = 0`. **Zero API
spend. No GPU/mlx.**

**Writes:** `extract.py`, `test_extract_e2.py`, `data/f3/p5_fixes/**`,
`data/f3/v2/**`, `data/filings_e2_v2.parquet`, and this file. **Nothing from
P2/P3/P4/P4b was overwritten** — the 2026-08-27 corpus and its five audit
artifacts are byte-unchanged (hashes in §7). `data/hardening/spotcheck_v12/`
untouched. No ledger edited.

---

## 0. Headline

| | |
|---|---|
| **F4 consumes** | `data/filings_e2_v2.parquet` — sha256 `15853e9f54902a933f0372869209a353ab3f052cb5c7dc1f897297f75b53f417` (627,948,973 bytes) |
| audit artifact | `data/f3/v2/extraction_audit.parquet` — sha256 `207f392aa54c5151015093ecb34e5c57319f17e1ce22a3375ec1ac7f18e81eef` |
| extractor | `extract.py` sha256 `a5a519b1f436e4e798c94655d243a851fbaed1957a4c2970f1b7dac545385663` (P2's was `b9acceea8377…`) |
| corpus | 28,900 → **29,097 sections** (+197) from the same 30,475 attempts |
| **rows whose TEXT BYTES changed** | **276 of 29,097 (0.95%)** — every one attributed to a named fix |
| rows changed on any field | 1,055 of 30,475 · **UNATTRIBUTED = 0** |
| words recovered | **+2,419,124** (ladder 1,686,459 · N5 518,549 · NIKE 214,116) |
| tests | **163 pass** (118 pre-P5 suite with 4 updated, + 45 new) |
| E1 regression | **880/884 byte-identical** — the same four `8K_BODY` rows P1 named, no others |
| discipline | `cache_miss = 0` · 0 GETs · `merge.complete: true` · 34/34 shards · one extract.py sha across every shard · no floor constant changed |

Status arithmetic closes on both sides:
25,245 + 3,655 + 796 + 779 = 30,475 (old) → 25,243 + 3,854 + 682 + 696 = 30,475 (new).

---

## 1. What changed, fix by fix

### Fix 1 — the guarded TOC recovery ladder

**Population.** Attempts where the anchor TOC *does* carry a matching entry for
the target item (right number, right title keyword) but the shipped anchor path
still returns `None`: P3's 148 FAIL rows (116 R2 + 32 R3) and P4b's 83
`EXPECTED_ABSENT` rows (71 R2 + 12 R3). 231 rows in scope; the 696 R1 rows are
the negative control.

**Design, in the order the guards run.**

- **G1 — the recovered span must open on the item's own heading** within 40
  characters (`span_opens_on_item_heading`, `HEAD_GUARD_CHARS = 40`). The guard
  pattern is deliberately looser than the locator's (it accepts
  `ITEM 1A - RISK FACTORS` and `ITEM 1(A).`), because it is testing located text,
  not searching for it.
- **G1, completed for the heading-regex rung — a heading begins a LINE**
  (`_fallback_span_starts_a_line`). On the anchor rung G1 is a real test; on the
  heading-regex rung the span starts *at* the regex match by construction, so
  the plain test is vacuous and a mid-line match is a cross-reference inside a
  sentence. See §2 for the measurement that forced this.
- **G2 — the span must not run to end-of-document.** An anchor span that already
  closed on a later resolving TOC anchor has a real boundary and keeps it; one
  that reached EOF passes only if one of the shipped end-patterns can supply a
  boundary, and then the end-guarded text is what is stored.
- **G3 — the recovered span must clear its `MIN_SECTION_WORDS` floor.** Added at
  P5; see §2 for why P4b's two guards were not sufficient once the population
  widened from `(10-Q, RISK_FACTORS)` to all four targets. **No floor constant
  moved**: the shipped values are used as an *admission* test on a new path,
  which can only ever decline to add a row.

**Rungs.** F1′ = the first matching TOC entry whose anchor actually resolves.
F2′ = the shipped heading-regex fallback, reached **only** where F1′ has no
resolving anchor at all or fails G1 — the ordering the brief specifies, and it
is load-bearing (§2).

**Scope.** The ladder runs **only when a matching TOC entry exists**. It never
fires on R1. P4b measured why: the same guards over the 696 R1 rows admit 131 of
which 89 are garbage. Pinned by
`test_t22_the_ladder_never_fires_where_the_item_is_absent_from_the_toc`.

**Outcome, from the shipped code over both populations (`data/f3/p5_fixes/preflight.jsonl`).**

| | recovered | words | declined |
|---|---|---|---|
| P4b `EXPECTED_ABSENT` arm (83) | **71** (58 F1′ + 13 F2′) | **125,156** | 12 (all AIG) |
| P3 FAIL arm (148) | **126** (107 F1′ + 19 F2′) | 1,561,303 | 22 |
| **total** | **197** | **1,686,459** | **34** |
| R1 control (696) | **0** | 0 | 0 |

**The EA arm reproduces P4b exactly** — 58/13/12 and 125,156 words, filer for
filer (Vertex 15, ADP 14, Eversource 13, AIG 12 declined, Salesforce 8,
UnitedHealth 8, BNY Mellon 5, AIG-R2 2, Capital One 2, Diamondback / Fiserv /
Shire / T-Mobile 1 each). That is an independent reproduction of P4b's census by
the shipped extractor, not a re-quotation of it.

By target: 10-K MDA 33 (471,591 + 38,473 w) · 10-K RF 41 (362,356 + 26,173 w) ·
10-Q MDA 52 (479,346 + 183,364 w) · 10-Q RF 71 (120,424 + 4,732 w). 32 filers;
**72.1% of the recovered rows are pre-2019 filings** — the era gradient P4b
measured, confirmed at corpus scale.

**Every recovered row is FLAGGED, never OK, never `high`.** 36 `medium` (F1′
spans that already had a real boundary), 161 `low` (F1′ spans the end guard had
to close, which additionally carry `toc_recovery_end_guarded`; and every F2′
span). Verified on the corpus: 0 of 197 at `high`.

**The 34 declined rows stay loud FAILs** under a new code,
`toc_recovery_declined`, whose `note` names the guard that declined them:

| filer | n | guard |
|---|---|---|
| AIG (10-Q RF 12, 10-Q MDA 5, 10-K RF 1) | 18 | G1 line-start — the fallback match sits mid-sentence in a cross-reference |
| Coca-Cola 10-K MDA | 4 | G3 — F1′ opens on the real Item 7 heading but the end guard truncates it to 73 w at an `Item 8` cross-reference in its own first paragraph |
| Concho 10-K MDA 2 / 10-K RF 2 | 4 | G3 (905/914 w) / G1 line-start |
| Honeywell 10-K MDA | 3 | G1 line-start |
| PNC 10-Q MDA | 2 | G1 head (F1′ points at the wrong section) then G3 (89 w / 77 w — PNC's Financial Review index page) |
| Zoetis 10-K MDA | 2 | G3 (74 w) |
| Weyerhaeuser 10-K MDA | 1 | G1 head then G3 (54 w — the MD&A's own sub-table-of-contents) |

The 12 AIG R3 rows the brief names are inside the 18.

### Fix 2 — the status rename, and the third truth

`EXPECTED_ABSENT` asserted a fact about the **filer** ("this 10-Q genuinely has
no Part II Item 1A") that the extractor never measured. P4b proved it false for
125 of 779. The status is now **`ITEM_ABSENT_FROM_TOC`**, which states only what
is tested.

The three truths inside the old 779 are now separated:

| truth | disposition | n |
|---|---|---|
| extractor-recoverable | recovered, `toc_recovered_f1` / `toc_recovered_f2`, FLAGGED | **71** |
| extractor failure, not recoverable | `toc_recovery_declined`, FAIL | **12** |
| no matching entry in the anchor TOC | `ITEM_ABSENT_FROM_TOC` | **696** |
| …of which the body carries a heading that passes every guard | + flag `item_body_heading_present` | **52** |

**The 42 genuine-but-never-indexed rows P4b named are flagged, not recovered.**
The brief asked for recovery "via the same guarded ladder if they pass guards,
otherwise flag them distinctly" — but fix 1's scope condition forbids the ladder
from firing on R1, and those two instructions cannot both be satisfied. I took
the safe branch and am saying so in the open: the marker is a *review pointer*,
never an extraction. Its measured precision is **42 of 52** — the 52 marked rows
are exactly P4b's named 42 (Cigna Holding 11, Welltower 9, Cigna Group 8, US
Bancorp 7, Truist 3, SBA 2, AbbVie 1, CVS 1) plus 10 Hess rows whose markup
happens to break the line right after "Risk Factors" in a cross-reference
sentence. P4b's own guards, unscoped, would have admitted 131 rows at 32%
precision; this marker is at 81% and admits nothing. Corpus-wide the marker
fires on **95** rows (the 52 above plus 43 `item_absent_from_toc` FAIL rows on
the other three targets — Corning 17, Honeywell 4, ConocoPhillips 3, Travelers 3,
LyondellBasell 3, Deere 4, SBA 3, …).

**Mapping back to the pre-P5 view, for the audit consumer.** Exactly:

```
old EXPECTED_ABSENT  ==  extraction_status == 'ITEM_ABSENT_FROM_TOC'
                      OR (form == '10-Q' AND section_type == 'RISK_FACTORS'
                          AND reason_code IN ('toc_recovered_f1',
                                              'toc_recovered_f2',
                                              'toc_recovery_declined'))
```

Pinned as a test against both artifacts
(`test_t23_the_old_expected_absent_view_is_reconstructible`); the rebuilt key set
equals the old 779 exactly. The per-filer rollup's column is renamed
`n_expected_absent` → `n_item_absent_from_toc`.

### Fix 3 — N1, the garbled-text screen, as a UNION

Shipped: **`ctrl_ratio >= 0.01` OR `eng_word_share < 0.12`**, computed in
`_finish_section` for every located section on every path, stored as two new
columns (`ctrl_ratio`, `eng_word_share`) on both artifacts so the screen is
re-auditable without a re-extraction.

Why a union — each single screen has a named counter-example:

| screen | proposed by | fails on |
|---|---|---|
| `nonascii_ratio` | P1 | Freeport `0000831259-24-000026` scores 0.0136, below the corpus 99th percentile |
| `ctrl_ratio ≥ 0.02` | P3 | Digital Realty `0001297996-18-000125` scores **exactly 0.00000** |
| `eng_word_share < 0.12` | P4 | Digital Realty `0001297996-16-000203` scores 0.333 |

**Recalibration, stated with counts.** P3's `ctrl_ratio` threshold is lowered
0.02 → 0.01. Before: 3 rows. After: **4 rows** — the fourth is
`0001297996-16-000203` at 0.01572, and the next row in the corpus sits at
0.00365, a 4.3× margin. I read that row's bytes: it is a slide-deck fragment
whose bullets are Wingdings private-use glyphs (``, `q`, `p`, `tu`) around
a legible Core-EBITDA table — a *different* class from the Caesar/font-map prose
of Ford and Freeport, which is why I am recording it rather than claiming a
clean sweep. Moving a threshold in the direction that catches more bad rows, on
a flag that can never filter, is the safe direction.

**Corpus-wide fire count: 6 rows.** All 8-K EX-99.

| row | words | ctrl_ratio | eng_word_share | before | after |
|---|---|---|---|---|---|
| Ford `0000037996-18-000082` | 3,333 | 0.33539 | 0.00000 | **OK / high / no flags** | FLAGGED / medium |
| Ford `0000037996-19-000065` | 2,609 | 0.24177 | 0.00743 | **OK / high / no flags** | FLAGGED / medium |
| Freeport `0000831259-24-000026` | 167 | 0.22890 | 0.00629 | FLAGGED | FLAGGED (new primary code) |
| Digital Realty `0001297996-18-000125` | 2,063 | 0.00000 | 0.03635 | FLAGGED (gate only) | FLAGGED |
| Digital Realty `0001297996-16-000203` | 108 | 0.01572 | 0.33333 | FLAGGED | FLAGGED |
| Emerson `0000032604-25-000094` | 3,109 | 0.00000 | 0.11111 | FLAGGED | FLAGGED |

All five known-garbled rows are caught. **Emerson is a named false positive** —
P4 read it and it is a clean numeric table; it costs one review-queue entry and
is not tuned away. **Both thresholds are fitted on a class of five hand-read
rows**; that is why this ships as a flag with its metrics stored, not as a
filter. Stated limitation: 2,748 corpus rows have fewer than 50 alphabetic
tokens and are therefore unscored on `eng_word_share` (they are scored on
`ctrl_ratio`, and all of them sit below every length floor already).

The two Ford rows are the whole point: 5,942 words of font-map garbage with
`prose_word_share = 1.0` that were headed for the labeling set as clean prose.

### Fix 4 — N5, the heading-regex last-match defect

**What shipped: a floor rescue, not a first-match rule.** When the last-match
slice falls below the already-calibrated `MIN_SECTION_WORDS` floor for its
(form, section), the locator scans the matches in document order and takes the
earliest that **begins a line** and clears the floor; otherwise the shipped
slice stands. No new constant.

**The obvious fix was measured and refuted.** I replayed all 1,140
`heading_regex` corpus rows (`data/f3/p5_fixes/p5_n5_calibrate.py`; the shipped
last-match rule reproduces the corpus 1,140/1,140, which validates the replay)
and hand-read 38 of the rows a plain "prefer the first match with span ≥ X" rule
would change (`data/f3/p5_fixes/n5_read_cards.txt`,
`n5_read_verdicts.csv`):

| | better | worse | wrong both ways |
|---|---|---|---|
| 10-K MDA | 0 | 3 | 3 |
| 10-K RISK_FACTORS | 5 | 0 | 5 |
| 10-Q MDA | 7 | 0 | 3 |
| 10-Q RISK_FACTORS | 3 | 9 | 0 |
| **total (38)** | **15** | **12** | **11** |

Position does not decide which match is a section start. The losses were large
and one-directional: PayPal `0001633917-16-000161` +11,359 words of wrong text,
Micron `0000723125-18-000156` +14,818, Waste Management `0001558370-23-016700`
+9,586, Deere ×3 replacing a correct 88-word stub with a 3,000-word
cross-reference span. **Length does decide**: every row the first-match rule
damaged already had a plausible 7.8k–32k-word slice, and every row of P3's named
defect was below its floor.

**Result: 58 rows change, all in named classes.**

| filer | form/section | n | shipped (median) | after (median) |
|---|---|---|---|---|
| **AT&T** | 10-Q MDA | **34** | **333.5 w** | **9,500 w** (min 4,678) |
| Walt Disney (TWDC) | 10-Q MDA | 10 | 13 w | 12,368 w |
| Abbott | 10-K RISK_FACTORS | 7 | 83 w | 3,817 w |
| eBay | 10-Q MDA | 4 | 562.5 w | 8,918 w |
| Berkshire Hathaway / Micron / Shire | 10-Q MDA | 3 | 513–856 w | 6,599–13,623 w |

**All 34 AT&T rows come back full-length**, which is the brief's acceptance
condition, and it is pinned by a parametrised regression
(`test_t25_the_named_att_rows_come_back_full_length`). 21 of the 58 were
hand-read; all 21 open on the real section heading and end naturally.

**The rebuild found one regression in itself, and it is fixed.** The first v2
build changed 61 rows, not 58. The extra three — Valero `0001035002-22-000007`
and Concho `0001358071-16-000026` / `-17-000005` — came back with 16,391 /
23,469 / 23,721 words of Item 1 Business labelled as MD&A, replacing 171 /
1,184 / 1,238-word stubs: measurably **worse** than doing nothing. All three
matched mid-line, inside `See "Item 7. Management's Discussion and Analysis…"`.
Requiring the rescue candidate to begin a line reverts all three to their
pre-P5 bytes and simultaneously improves a fourth (Abbott
`0001104659-22-025141`: 7,258 words of "Patents, Trademarks, and Licenses" →
the real 4,320-word Item 1A, which sits 20k characters later). The whole corpus
was then rebuilt from scratch under the corrected code; all four rows are pinned
by `test_t25_the_rescue_candidate_must_begin_a_line`.

### Fix 5 — N6, the NIKE per-filer edge handler

`EDGE_HANDLERS` gains its first member,
**`nike_10q_mda_shared_toc_anchor`**, and fired **21 times** — exactly the class
P3 §7.4 measured (NIKE 10-Q MDA, 2019-10-04 → 2026-04-01).

**The dialect, named.** NIKE's 10-Q table of contents gives several different
TOC rows the *same* `<a href="#id">` target. From 2019 the Part I Item 2 (MD&A)
row and the Part II Item 1A row share one id; by 2025 all 25 TOC rows share a
single id (`ice0441e621084087aba09b6658a`). That id is defined once, at the Part
II Item 1A heading, so the anchor path resolves MD&A to Part II and returns
389–1,318 words of "ITEM 1A. RISK FACTORS … ITEM 2. UNREGISTERED SALES …". The
Risk Factors extraction on the same documents is correct by luck, which is why
only 21 of NIKE's 66 10-Q attempts are affected.

**Predicate:** `cik == 320187 and form == "10-Q" and section == "MDA"`, **and**
the shipped slice must already carry `head_foreign_item`. So it is inert on the
12 NIKE 10-Q MD&As that extract correctly (pinned byte-identical against the
2026-08-27 corpus) and cannot fire on Tesla's 8, Bank of America's 2, Realty
Income's 2, Allergan's 11, SPDR Gold's 4 or MercadoLibre's 3 `head_foreign_item`
rows. 12,122 → **226,238 words**; e.g. `0000320187-19-000071` 465 → 7,873 w,
`0000320187-22-000017` 545 → 12,961 w, `0000320187-25-000151` 666 → 10,412 w.

**One mechanism change this required.** Edge handlers for periodic sections now
run inside `_locate_one_section` rather than in `extract_filing`, because a
handler that has to *re-locate* needs the document, which is out of scope by the
time control returns. `fired` is threaded down, so the manifest's fired-count and
DEAD-handler discipline is unchanged (and correctly reports the handler DEAD in
the earnings and 10-K segments, where it cannot apply).

---

## 2. Where I departed from the brief's design, and the evidence

Three places. Each is a documented, measured change, not a preference.

**(a) G3, a third guard.** P4b's G1+G2 were calibrated on
`(10-Q, RISK_FACTORS)`, where the floor is 15 and genuine sections really are
29–40 words. Over the 148-row FAIL population, which spans all four targets,
they admitted five rows I hand-read as wrong — Weyerhaeuser 54 w and PNC 77/89 w
(each the section's own sub-table-of-contents), Concho 905/914 w (truncated at
an `Item 8` cross-reference). Requiring the recovered span to clear its own
floor declines all five and keeps every one of P4b's 71.

**(b) The end guard is applied only when the anchor span runs to EOF.** Applying
the shipped end-patterns to a span that already has a boundary truncates 10-K
MD&As at the `Item 8. Financial Statements` cross-reference in their own first
paragraph: Coca-Cola came back at 73 words, Zoetis at 74. P4b's 58 R2 survivors
are unaffected — it recorded 21 rows whose span already closed (guard not needed,
and a no-op there) and 37 that ran to EOF (guard load-bearing).

**(c) G1 completed with a line-start test on the heading-regex rung.** On that
rung the span starts *at* the regex match, so "does it open on the item
heading?" is vacuous. Measured over **all 37** heading-regex recoveries the
ladder produced (the whole population, not a sample): 32 begin a line and 5 do
not, and those 5 are exactly the 5 I had hand-read as wrong — Honeywell
`0000930413-16-005457` / `-18-000292` / `-19-000366` 10-K MDA (the match sits
inside "…that drive our business and future results in Item 7. Management's
Discussion…", so the slice is the tail of Item 1A plus Items 2–6) and Concho
`0001358071-18-000008` / `-19-000003` 10-K RF (inside `See "Item 1A. Risk
Factors" for a description…`). All 13 Eversource and all 12 Welltower rows pass.
The same test then also fixed the N5 self-regression in §1 fix 4.

**The caveat I am not hiding, carried forward from P4b §5 and extended.** G2's
"no EOF run-out" rule and the line-start rule were both chosen *after* seeing the
populations they separate, and they separate them perfectly partly because of
that. Both mechanisms are principled — a Part II Item 1A is never the last item
in a 10-Q; a heading begins a line — but on an independent slice neither will be
perfect. They are wired so that they can only ever **decline to add** a row:
a declined row keeps failing exactly as it does today, under a reason code that
names the guard, which is a review-queue entry and not a silent drop. No guard
in this package can remove text that is in the corpus today. The same is stated
in the code comments at `extract.py` `recover_toc_present_section` and
`_fallback_span_starts_a_line`.

---

## 3. What I actually read (mandatory spot-read)

**~110 sections read by eye**, weighted as the protocol requires: 72.1% of the
ladder recoveries are pre-2019 filings, and the filers carrying the reads —
Eversource, Welltower, Concho, Honeywell, Micron, Deere, PayPal, eBay, Shire,
MercadoLibre, Valero, Walgreens, Vertex, ADP, Salesforce, Zoetis, Weyerhaeuser —
are E2-only, absent from E1's 25 mega-caps.

| read | n | where the verdicts live |
|---|---|---|
| N5 first-match candidate, both slices side by side, stratified + seeded (20260828) | **38** | `p5_fixes/n5_read_cards.txt` → `n5_read_verdicts.csv` |
| N5 floor-rescue rows not covered by the above (eBay ×4, Berkshire, Micron, Shire) | 7 | §1 fix 4 |
| ladder recoveries at the length extremes (<0.5× or >2× the anchor median), FAIL arm | **31** | §3.1 |
| ladder F1′ recoveries, one per filer, earliest filing (23 filers) | 16 | §3.1 |
| every heading-regex recovery's head + preceding 40 chars (line-start audit) | 37 | §2(c) |
| Honeywell 10-K RF, Walgreens 10-K RF, Concho 10-K RF, AIG — full head/tail | 4 | §3.1 |
| NIKE: TOC dumps + full slices, 2019 / 2022 / 2025 | 5 | §1 fix 5 |
| the R1 body-heading marker: SBA, Cigna Holding, Hess ×2 | 4 | §1 fix 2 |
| Digital Realty `0001297996-16-000203` raw bytes | 1 | §1 fix 3 |
| the N5 self-regression: Valero, Concho ×2, Abbott | 4 | §1 fix 4 |

**What I did NOT read.** I did not read the other ~160 ladder recoveries in the
0.5–2× band beyond the 16 one-per-filer draw; they are screened on head, tail
and length only. I did not re-read the 25,243 OK rows. Every verdict here is a
model judgement (HANDOFF §7), never the owner's.

### 3.1 The reads that changed the design

- **16 F1′ recoveries, one per filer, earliest filing: 16/16 correct.** Heads
  open on the real heading (UnitedHealth 2015, Diamondback 2015, ADP 2015,
  Salesforce 2015, Capital One 2016, Caterpillar 2016, Danaher 2016, Williams
  2016, NextEra 2016, FIS 2016, Humana 2016, Zoetis 2016, PMI 2016, Williams
  Partners 2016, Apache 2017, T-Mobile 2017), tails end naturally.
- **31 extreme-ratio rows.** Correct: Humana ×4 (correct head; tail truncated at
  an `Item 8` cross-reference — partial but not wrong), PMI ×5 10-K RF,
  UnitedHealth ×4 10-Q MDA, Shire, Caterpillar, PMI 10-K MDA, IBM ×2 10-Q MDA
  (23k w, genuinely long), Pfizer ×5 10-Q MDA (28k–41k w, 3.0–4.4× median —
  Pfizer's 10-Q MD&A really is that size), Honeywell ×3 10-K RF, Walgreens.
  Wrong, and all now **declined** by a guard: Weyerhaeuser, PNC ×2, Concho 10-K
  MDA ×2, Coca-Cola ×4, Zoetis ×2, Honeywell 10-K MDA ×3, Concho 10-K RF ×2.
- **After the guards, every one of the 32 heading-regex recoveries in the
  shipped corpus was hand-read and judged correct**: Welltower 12 (10-K MDA 3,
  10-Q MDA 9), Eversource 13, IBM 3, Honeywell 10-K RF 3, Walgreens 1.
- **Hess is the marker's named residual false positive.** Its 10-Q renders
  `Item 1A. Risk Factors\nin our Annual Report on Form 10-K for the year ended
  December 31, 2020…` — a cross-reference whose line break falls immediately
  after the title, so it passes the line-start test. 10 rows. It costs nothing:
  the marker never recovers.

---

## 4. Changed-row reconciliation — every changed row attributed

`data/f3/p5_fixes/p5_compare.py` → `changed_rows.csv`. Keys aligned on
(accession_number, section_type): 30,475 both, 0 left-only, 0 right-only. Text
compared by sha256 digest, streamed at 200 rows, so neither 620 MB text column
was ever materialised.

| bucket | rows | text bytes changed | words after |
|---|---|---|---|
| `fix1_ladder_recovered` | 197 | **197** | 1,686,459 |
| `fix1_ladder_declined` | 34 | 0 | 0 |
| `fix2_status_rename` | 644 | 0 | 0 |
| `fix2_body_heading_mark` | 95 | 0 | 0 |
| `fix3_garble_flag` | 6 | 0 | 11,389 (now flagged) |
| `fix4_n5_floor_rescue` | 58 | **58** | 536,021 |
| `fix5_nike_handler` | 21 | **21** | 226,238 |
| **UNATTRIBUTED** | **0** | 0 | — |
| **total** | **1,055** | **276** | |

Reconciliation against the fix populations, exactly:

- 197 recovered + 34 declined = **231** = P3's 148 R2/R3 FAIL rows + P4b's 83
  R2/R3 `EXPECTED_ABSENT` rows.
- 644 status renames + 52 marker rows inside the `EXPECTED_ABSENT` population =
  **696** = P4b's R1 count. (The other 43 marker rows sit on
  `item_absent_from_toc` FAIL rows for the three non-`(10-Q, RISK_FACTORS)`
  targets, where the status was already FAIL and did not change.)
- 58 = the N5 floor rescue, measured independently over all 1,140
  `heading_regex` rows before the rebuild (`n5_floor_rule.csv`) and reproduced
  row-for-row by the rebuild.
- 21 = the NIKE `head_foreign_item` class, exactly as P3 §7.4 counted it.
- 6 = the N1 union.

**28,821 of the 29,097 corpus rows are byte-identical to the 2026-08-27
corpus.** The 276 that are not are the 197 rows that did not exist before plus
the 79 the two behaviour changes touch, all named above.

---

## 5. Tests

**163 pass, 0 fail, 0 skip** (`python3 -m pytest test_extract_e2.py -q`, 121 s).
118 before P5 (four updated for the rename, the new registry member, the handler
signature, and one fixture whose `"word " * 5000` filler now — correctly — trips
the garble screen); **45 new**, in six blocks:

| block | what it pins |
|---|---|
| **T22** guards + ladder | 18 named rows, each with its required disposition and word floor (Salesforce/ADP/UNH recovered by F1′, Eversource ×2 by F2′, AIG ×3 declined, Danaher/UNH/Humana from the FAIL census, Welltower/IBM by F2′, and Coca-Cola / Weyerhaeuser / PNC / Honeywell / Concho declined each for its own named guard); **the R1-must-not-fire test** over four rows including SBA's 12,855-word genuine section and Williams's 21,241-word garbage; the marker test; guard unit tests for G1 (incl. the Eversource shape and the dash / `1(A)` dialects), G2 and the line-start test; the closed-enum + never-`high` invariant for all four new codes |
| **T23** status | the rename; `STATUS_EXPECTED_ABSENT` is gone; a declined recovery is FAIL even on `(10-Q, RISK_FACTORS)`; **the old view is reconstructible from the new audit artifact, key for key** |
| **T24** N1 | all five known garbled rows caught, parametrised, against the real corpus bytes; both single-screen counter-examples as literal thresholds; clean prose not flagged; short sections not scored |
| **T25** N5 | the five named AT&T rows come back >5× longer, above the floor, opening on `Item 2.` with no `- Continued`; the rescue is inert when the last match already clears the floor; the four line-start rows (3 reverted, 1 improved) |
| **T26** N6 | the NIKE predicate fires on exactly that class and not on Tesla / BofA / NIKE's own 10-K or RISK_FACTORS; inert without `head_foreign_item`; three real filings return the real MD&A at `low`; NIKE's 12 unaffected MD&As are byte-identical to the 2026-08-27 corpus |

The pre-existing T14 E1 byte-identity pins (12 named rows + all 9 resolved
stubs) still pass unchanged.

---

## 6. Rebuild discipline

| check | result |
|---|---|
| `cache_miss` | **0** on all 34 shards and in the merge manifest |
| network GETs | **0** on every run line; `extract.py` still has no `EdgarClient` import |
| `merge.complete` | **true**; shards found = expected = 8 / 10 / 16 |
| shard provenance | **one** `extractor_sha256` across all 34 shards, equal to the file on disk |
| merge warnings | `[]` |
| edge handlers | `nike_10q_mda_shared_toc_anchor` fired 21; correctly reported DEAD in the segments where it cannot apply |
| determinism | 34 shards run by 8 processes on **disjoint** shard indices (P1 §6's rule); each shard is a pure function of one cached document plus fixed constants, so the split cannot change output |
| point-in-time | `filing_date` / `report_date` carried through unchanged; nothing in the F3 path sorts on `report_date` (pinned, T13) |
| floors | **no constant changed.** `MIN_SECTION_WORDS`, `MIN_SECTION_CHARS` and `MDA_STUB_WORD_CEILING` are byte-identical to P1's values |
| out of scope, untouched | N3 (Simon marker), D2 fetches, reflow/chunking/labeling, `chunk.py` |

Wall clock: the **shipped** rebuild (earnings 8 shards, 10-K 10, 10-Q 16) ran
03:33 → 04:43 UTC, **70 minutes** across up to six disjoint workers. It is the
second build: the first (00:52 → 03:26 UTC, sequential then 2 workers) was
discarded in full once its own comparison surfaced the three-row N5 regression
in §1 fix 4, and `data/f3/v2/` plus `data/filings_e2_v2.parquet` were deleted
and rebuilt from scratch under the corrected code so that no shard carries a
stale `extractor_sha256`.

---

## 7. E1 freeze and artifact provenance

**E1's frozen artifacts were read only and are byte-unchanged:**

| file | sha256 | mtime |
|---|---|---|
| `data/filings.parquet` | `5e09a749f97d932bf06df607253dfcb2ae4006fdd4c6ae84018a62cef73f260e` | Aug 10 17:09 |
| `data/labels.parquet` | `c3531f03cda602bc2ed7fb7743d5d01f78ed722f2a58bd82922f5b8ccc3daa72` | Aug 11 02:30 |
| `data/universe.csv` | `a4ce980d6f2caa8ddb7085db537ca8b91ad9cf9b168534da420cda1757a22813` | Aug 10 11:06 |
| `data/filings_metadata.db` | — | Aug 18 12:08 |

**The corpus-scale E1 regression was re-run against the shipped P5 code:
880/884 byte-identical** — `anchor` 544/544, `incorporated_by_reference_resolved`
9/9, `whole_document` 327/331, and the only four differences are the same
`8K_BODY` rows P1 named (BAC `0000070858-24-000006`, CVX `0000093410-24-000002`
and `-26-000108`, GS `0000886982-26-000004`), i.e. R2's ruled item-2.02 slicing
and nothing else. Output: `data/f3/p5_fixes/p5_e1_regression_884.csv`.

**P2/P3/P4/P4b artifacts are byte-unchanged**, so the audit record behind those
reports survives:

| file | sha256 |
|---|---|
| `data/filings_e2.parquet` (the 2026-08-27 corpus) | `1255831b030814ca799962b4956b1ca956fc44c786374a50303b6214791d2ef2` |
| `data/f3/extraction_audit.parquet` | `dd7322c69ac64b1d7fc12dfbe7b3550542872a8cb5fbc2fc2778a0e0ce8f88b9` |
| `data/f3/run_manifest.json` | `223185e2d455e8057b2fab3a0afbc3d2087ab09b8eb2b5f5f08e903b63662e98` |

**Which corpus F4 consumes: `data/filings_e2_v2.parquet`**
(sha256 `15853e9f54902a933f0372869209a353ab3f052cb5c7dc1f897297f75b53f417`),
with its audit artifacts under `data/f3/v2/`. The pre-P5 pair remains in place
as the P2/P3/P4 record and must not be used for labeling.

**Schema note for F4.** Two columns are new on both artifacts: `ctrl_ratio` and
`eng_word_share` (nullable float). `extraction_status` gains
`ITEM_ABSENT_FROM_TOC` and loses `EXPECTED_ABSENT`; `reason_code` gains
`toc_recovered_f1`, `toc_recovered_f2`, `toc_recovery_end_guarded`,
`toc_recovery_declined`, `item_body_heading_present`, `garbled_text`;
`extraction_method` gains `anchor_resolving_entry` and
`heading_regex_toc_present`. Any consumer reading columns by name is unaffected;
`per_filer_rollup.csv` renames one column (§1 fix 2).

---

## 8. Carried forward (not decisions — findings for the main session)

1. **The stub resolver does not run on ladder recoveries.** A recovered 10-K
   MD&A that is genuinely an "incorporated by reference" stub is declined by G3
   rather than routed to `resolve_incorporated_by_reference_mda`. Coca-Cola's
   four rows are the visible instance: F1′ opens on the real Item 7 heading and
   the end guard cuts it to 73 words. They stay loud FAILs. Wiring the resolver
   into the ladder is a further change with its own regression, not something to
   slip in here.
2. **The four population-gate columns are still not point-in-time** (P4 §5.1:
   726 rows are flagged because of a *later*-dated filing). P5 changed nothing
   about them. F4/F5 may use them for triage, never for conditioning in a
   walk-forward.
3. **Both N1 thresholds are fitted on five hand-read rows.** The metrics are now
   stored per row, so a future stage can re-fit or re-census for free.
4. **The F4-scale numbers in P3 §8 are now stale by +197 sections / +2.42M
   words** (plus whatever the reflow decision does). A cheap re-run of
   `p3_scale.py` against `data/filings_e2_v2.parquet` would refresh them; P5 did
   not, because the window-rule and reflow decisions are still open.
5. **The `item_body_heading_present` marker is a review queue, not a result.**
   95 rows, ~81% precision on the slice P4b hand-read. If the owner ever
   authorises the D2-class bounded fetch, these 95 are the cheapest adjacent
   population to look at, because they need no fetch at all.

---

## 9. Artifacts

All new work under `data/f3/p5_fixes/` (scripts, logs and evidence) and
`data/f3/v2/` (the rebuilt audit artifacts).

| file | what |
|---|---|
| `p5_n5_calibrate.py` → `n5_calibrate.jsonl` | the 1,140-row N5 replay, three candidate rules, seeded |
| `p5_n5_cards.py` → `n5_read_cards.txt`, `n5_read_manifest.csv` | the 38 side-by-side evidence cards, sample drawn before any read |
| `n5_read_verdicts.csv` | the 38 hand verdicts with the sentence that decided each |
| `p5_n5_floor_rule.py` → `n5_floor_rule.{jsonl,csv}` | the floor-rescue measurement over all 1,140 rows |
| `p5_preflight.py` → `preflight.jsonl` | the ladder replayed by the SHIPPED code over all 231 in-scope rows + the 696-row R1 control |
| `ladder_read_cards.txt` | the 31 extreme-ratio ladder reads |
| `p5_compare.py` → `changed_rows.csv` | the byte-identity regression and the attribution table (§4) |
| `p5_e1_regression.py` → `p5_e1_regression_884.csv` | the corpus-scale E1 regression, re-run against P5 code |
| `run_v2b.sh`, `run_v2*.log` | the rebuild driver and its logs |
| `data/f3/v2/**` | corpus audit, failures CSV, per-filer rollup, gate census, length distribution, `run_manifest.json` |

**Discipline:** 0 live GETs · 0 API spend · 0 GPU · writes confined to
`extract.py`, `test_extract_e2.py`, `data/f3/p5_fixes/**`, `data/f3/v2/**`,
`data/filings_e2_v2.parquet` and this file · DB read-only · every P0–P4b
artifact and every ledger byte-unchanged · E1 frozen artifacts read-only ·
every filing's true public `filing_date` carried through unmodified.
