# G2 — OWNER RULING PACKET (generated 2026-09-07T10:30:09Z) — MODEL-CONSENSUS stage

> model-consensus agreement (blind rater + adjudicator, both Claude-family) with owner rulings superseding on the escalated subset; NOT human validation of ground truth (HANDOFF §3).
>
> Everything below is **model consensus** — a blind Claude-family rater plus a Claude-family adjudicator, scored mechanically. It is not your judgment and it is not human validation of ground truth. It becomes the owner-ratified stage only where you rule.

Rule on the merits. The bars (0.85, both gate-bearing fields), the k\* boundaries and the escalation trigger were pinned on 2026-09-07 **before** any chunk was rated (design §14.6); the arithmetic below is printed so the consequence of a ruling is visible, not so it can be aimed at.

## The two gate-bearing primaries (verbatim, `results_g2.json`, stage `model_consensus`, generated 2026-09-07T10:30:08Z)

**`sentiment` — bar 0.85: 292/337 = 86.65% 95% Wilson [82.60%, 89.87%] -> INDETERMINATE**

  - **What the 86.65% is made of** (`results_g2.json` → `secondaries['S-ERR']`, stored (student) → reference (adjudicated), P arm, 334 scored + 3 omission-pinned nulls): NEGATIVE->NEGATIVE 24; NEGATIVE->NEUTRAL 25; NEUTRAL->NEUTRAL 215; NEUTRAL->POSITIVE 2; POSITIVE->NEUTRAL 15; POSITIVE->POSITIVE 53.
  - **Precision on each stored value** (rows the reference upheld): **NEGATIVE 24/49 = 49.0%**; **NEUTRAL 215/217 = 99.1%**; **POSITIVE 53/68 = 77.9%**.
  - **Read this beside the headline.** 40 of the 45 sentiment errors are the student asserting a DIRECTION on a passage the reference calls NEUTRAL. NEUTRAL is 217/334 = 65% of the scored base and is upheld 99.1% of the time, so the pooled figure is carried by the NEUTRAL mass — structurally the same NONE-mass problem the whole G-A arm was bought to expose for guidance. The two surviving E2 sentiment features are `sentiment_mean_score` and `sentiment_negative_share`, and **`sentiment_negative_share` consumes exactly the stored-NEGATIVE quantity measured at 24/49 = 49.0% precision.** This is disclosure, not a bar: no per-value figure carries a bar and none can move the verdict.

**`guidance_direction` — bar 0.85: 115/119 = 96.64% 95% Wilson [91.68%, 98.69%] -> PASS**  ||  guidance_active_precision 68.67% 95% Wilson [58.17%, 77.55%] (corpus-re-weighted; n_eff 84.8 of nominal n 100)  ||  guidance_false_none_rate 0/80 = 0.00% 95% Wilson [0.00%, 4.58%]

- ceiling (S-NOISE, **two independent runs of the same Claude-family blind rater** — same agent card `.claude/agents/label-rater-blind.md`, same model family, same prompt, on byte-identical files in identical row order; it is a run-to-run reproducibility figure, NOT an instrument validation and NOT two independent instruments; **cannot move any bar**): sentiment 107/110 = 97.27% [92.29%, 99.07%]; guidance 64/65 = 98.46% [91.79%, 99.73%]; red_flags 106/120 = 88.33% [81.37%, 92.92%]. Both gate-bearing ceilings' **lower** bounds clear 0.85, so §6.4 fact 3 (a bar above the instrument's own ceiling) does **not** fire on this draw. The ceiling is UPPER-biased by an unmeasured amount: raters A and B saw byte-identical files in the same row order, so any ordering or context effect is shared (§14.9).
- **the third rater, measured** (descriptive; no bar; moves nothing): the adjudicator sided with the blind rater **against** the stored student label on 271/314 = 86.31% of contested rows — guidance_direction 31/32 = 96.88%; red_flags 169/193 = 87.56%; sentiment 71/89 = 79.78%. Read it beside the ceiling immediately above: the Claude family agrees with itself run-to-run at 97–98% and goes against the Qwen student on ~86% of the rows it is asked to arbitrate. That is consistent with the adjudicator correctly finding student error AND with within-family agreement, and **this design cannot separate the two** — which is exactly why §12.1 calls the estimate plausibly optimistic. It is a free disclosure, not a defect.

- `red_flags` — **disclosure-only, exploratory** (your 2026-08-27 ruling; this pass cannot change it, and no red-flag row escalates to you): exact-set (category+modality) error 112/400 = 28.00% [23.83%, 32.59%]; per-category-decision error 150/2400 = 6.25% [5.21%, 7.38%] (chunk-clustered bootstrap over 400 chunks; the naive binomial interval is anti-conservative and is not the one quoted). Exact-set and per-category are different bases and are never quoted as each other.

### §6.6 — what a non-FAIL does not mean (pre-registered wording, verbatim)

> **sentiment.** The G2 spot-check did not trigger a decisive failure for `sentiment`. Measured agreement is 86.65% [82.60%, 89.87%] (n = 337, bar 0.85, model-consensus reference with owner rulings on the escalated subset; NOT human validation of ground truth). At this n the design would have declared a decisive failure with probability 0.18 if true agreement were 0.83 and 0.03 if it were 0.85 — those two numbers are the whole of what this result excludes on the low side, and a true value below the bar is made less likely at those rates, not ruled out. For the gate-bearing fields this estimate is plausibly optimistic (§12.1): the rater's family is the teacher's family, so teacher error the student memorized is invisible to it, biasing measured error low. This is a chunk-level label-accuracy figure; it is NOT the feature-level reliability lambda of EXPANSION_PLAN §2a (§6.5) and must not be used as one. Every E2 feature derived from `sentiment` carries this figure as a stated caveat.

> **guidance_direction.** The G2 spot-check did not trigger a decisive failure for `guidance_direction`. Measured agreement is 96.64% [91.68%, 98.69%] (n = 119, bar 0.85, model-consensus reference with owner rulings on the escalated subset; NOT human validation of ground truth). At this n the design would have declared a decisive failure with probability 0.10 if true agreement were 0.83 and 0.03 if it were 0.85 — those two numbers are the whole of what this result excludes on the low side, and a true value below the bar is made less likely at those rates, not ruled out. For the gate-bearing fields this estimate is plausibly optimistic (§12.1): the rater's family is the teacher's family, so teacher error the student memorized is invisible to it, biasing measured error low. This is a chunk-level label-accuracy figure; it is NOT the feature-level reliability lambda of EXPANSION_PLAN §2a (§6.5) and must not be used as one. Every E2 feature derived from `guidance_direction` carries this figure as a stated caveat. Binding, ruling (vii): this number is a base rate over the NONE mass and is never quoted alone — guidance_active_precision 68.67% 95% Wilson [58.17%, 77.55%] (corpus-re-weighted; n_eff 84.8 of nominal n 100); guidance_false_none_rate 0/80 = 0.00%  95% Wilson [0.00%, 4.58%]  (+-2.29%).

### What your Part A rulings can and cannot move (arithmetic)

A STORED-RIGHT ruling on a row the adjudicator overturned moves that field's k **up 1**; an OTHER ruling on a row the adjudicator upheld moves it **down 1**; an ADJUDICATOR-RIGHT ruling changes nothing. Only rows in the **P (base-rate) arm** sit in a primary's denominator — G-A and G-N rows move the guidance escorts instead, and n never changes (0 unsure, 0 unadjudicated on both primaries).

| field | k / n | k\* PASS | k\* FAIL | Part A rows in this base | reachable k | verdicts attainable across every combination of Part A rulings |
|---|---|---|---|---|---|---|
| `sentiment` | 292 / 337 | 300 | 273 | 6 (3 up-movable, 3 down-movable; 5 more sit outside this base) | 289–295 | INDETERMINATE only — **the verdict cannot change** |
| `guidance_direction` | 115 / 119 | 109 | 93 | 3 (3 up-movable, 0 down-movable; 25 more sit outside this base) | 115–118 | PASS only — **the verdict cannot change**. Never quotable alone (ruling (vii)): guidance_active_precision 68.67% 95% Wilson [58.17%, 77.55%] (corpus-re-weighted; n_eff 84.8 of nominal n 100); guidance_false_none_rate 0/80 = 0.00% 95% Wilson [0.00%, 4.58%] |

- **`sentiment` is INDETERMINATE at 292/337 and no combination of Part A rulings changes that.** PASS needs k ≥ 300, i.e. 8 more agreements; only **3** of the 11 escalated sentiment rows sit in the P base with an overturn to reverse, so ruling **all** of them STORED-RIGHT reaches k = 295 — still 5 short. **PASS is not reachable.** DECISIVE FAIL needs k ≤ 273, i.e. 19 more errors; only **3** rows can be moved down, floor k = 289. **FAIL is not reachable either.** The other 5 escalated sentiment rows are in the G-A / G-N arms and are outside the sentiment primary's base entirely. 3 of the 45 errors are pre-registered omission errors (the student emitted no sentiment, §1.3) and are not adjudicable by anyone.
- **`guidance_direction` is PASS at 115/119 (guidance_active_precision 68.67% 95% Wilson [58.17%, 77.55%] (corpus-re-weighted; n_eff 84.8 of nominal n 100); guidance_false_none_rate 0/80 = 0.00% 95% Wilson [0.00%, 4.58%]) and no combination of Part A rulings changes that either.** k ranges 115–118 across all 8 combinations of the 3 P-arm rows, and the floor 115 is still ≥ k\* PASS 109. Losing the PASS would take 7 more errors, and Part A offers 0 rows that could add one (all 3 P-arm guidance rows are already scored as errors).
- **Where your rulings do bite: the G-A escort.** 25 of the 39 Part A rows are G-A active-guidance rows, and they carry 24 of G-A's 27 errors. Ruling every one STORED-RIGHT takes the corpus-re-weighted active precision from 68.67% [58.17%, 77.55%] to 96.73% [90.80%, 98.88%] (n_eff 91.4); ruling the upheld row OTHER takes it to 67.42% [56.89%, 76.44%] (n_eff 85.0). This is the number the guidance verdict may never be quoted without (ruling (vii), Option 1), and it carries no bar. **G-N has 0 Part A rows**, so the false-NONE rate stays 0/80 mechanically whatever you rule here — but see the coupling note directly below; that is an arithmetic fact about this packet, not a substantive reassurance.
- **What the 68.67% active precision is mostly measuring: an unresolved RUBRIC question, not the student.** Of G-A's 27 errors, 22 resolve to `correct_label = NONE`, and **20 of the 27 sit in three adjudicator slugs that are all one and the same question** — `fresh-quantified-guidance-no-prior-comparison` (10); `quantified-outlook-without-revision-language` (5); `new-or-initiated-guidance-not-raised` (5): *a quantified forward outlook issued with no explicit revision language.* Design §3.3 already records that rubric §3's preamble names "issue new guidance" as a case for which the label set offers **no value**. So this is substantially a measurement of a rubric gap, and it moves to 96.73% [90.80%, 98.88%] on a single convention ruling by you. The rubric gap is the thing to rule on; the percentage is downstream of it.
- **The same convention is load-bearing in two other places, and this is disclosed rather than left implicit.** (1) The 60 `guidance_imputed_none` rows inside the guidance primary are scored AS NONE by the same writer rule. (2) **G-N had zero contested rows, so G-N was never adjudicated at all** — its 0/80 was produced by the same blind rater applying the same convention. Measured bound on that coupling, re-derived here from the 80 G-N passages: 18 contain any of outlook / guidance / expect / anticipate / forecast, and only **3 of 80** place a company-subject forward-expectation phrase within 200 characters of a quantified figure (≈3.8%, Wilson [1.28%, 10.45%]) — and on inspection those are a tax-refund timing, a buyback execution timing, and a forward restructuring-charge estimate, none of them a financial-performance outlook. **A convention reversal could therefore plausibly move G-N from 0/80 to at most about 3/80; it could not invert it.** The screen is deliberately over-inclusive and is an upper bound on exposure, not a judgement about any chunk.
- The only mechanism in this packet that can move either verdict is **Part B**: ≥ 2 of 20 overturns fires the pre-committed sweep of the uncontested set, which can only add errors (it re-checks rows currently scored as agreements).

## PART A — the 39 `needs_human` rows (14 pattern slugs)

Grouped by the adjudicator's pattern slug; where a pattern repeats, one ruling can settle the group — say so in the note and the rest can follow it. Every row: rule **STORED-RIGHT** (the student's stored label is right) / **ADJUDICATOR-RIGHT** (the adjudicator's `correct_label` is right) / **OTHER** (give the label). On the 4 rows where the adjudicator **upheld** the stored label the two are the same ruling — only OTHER moves those.

### pattern `fresh-quantified-guidance-no-prior-comparison` — 10 row(s)

#### A1. `E2CHK-254e479a0e14017c`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `RAISED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** The table's "Approximate Change" column compares the "Full Year 2017 Outlook" against "Full Year 2016 Actual," not against any previously issued 2017 target, and nothing in the passage says guidance was increased. Section 3's RAISED covers a target "increased versus a prior figure" in the sense of revising previously-issued guidance, so stored RAISED is unsupported. Owner must weigh the same residual convention question that governs the other undirected guidance tables in this batch.
**Rater's reason (its own words, written before it saw any stored label):** Guidance is NONE because the 'Full Year 2017 Outlook' table states figures against 'Full Year 2016 Actual' with no raise, cut, reaffirmation or withdrawal of a prior guidance figure; flags are empty because the trailing 'regulation or taxation of health benefits ...; trends in health care costs ...; our participation in federal and state health insurance exchanges' is a safe-harbor enumeration that fails mining depth.
<details><summary>chunk text (2662 chars)</summary>

```
$ 374.3 76.0 % $ 4,555.4 $ 4,631.0 (1.6 )% 14 Anthem, Inc. Financial Guidance Summary (Unaudited) Full Year 2016 Actual Full Year 2017 Outlook 1 Approximate Change Year-End Medical Enrollment Self-funded 24,688 25,000 - 25,100 315k - 415k Fully-Insured

15,231 15,100 - 15,200 (130k) - (30k) Total 39,919 40,100 - 40,300 185k - 385k Operating Revenue $84.2 billion $86.5 - $87.5 billion $2.3 - $3.3 billion or 2.7% - 3.9% Benefit Expense Ratio 84.8% 87.0% +/- 30 basis points

(220) bps SG&A Expense Ratio 14.9% 13.3% +/- 30 basis points 160 bps Operating Gain $4.8 billion Greater than $4.5 billion Greater than ($300) million or (6.3%) Other Pre-Tax Items: Net Investment income $780 million $740 million ($40) million Interest Expense

($723) million ($660) million $63 million Amortization of Intangible Assets ($192) million ($160) million $32 million Net Pre-Tax Expense ($135) million ($80) million $55 million Effective Tax Rate 45.8% 33.0% - 35.0% (12.8%) - (10.8%) GAAP EPS $9.21 Greater than $11.11

20.6% or better Adjusted EPS 1 $11.00 Greater than $11.50 4.5% or better Diluted Shares 268.1 million 262 - 266 million (2.3%) - (0.8%) Operating Cash Flow $3.2 billion Greater than $3.5 billion Greater than $300 million (1) 2017 outlook does not include any benefits or transaction costs associated with the pending Cigna acquisition.

15 Forward-Looking Statements This document contains certain forward-looking information about us that is intended to be covered by the safe harbor for “forward-looking statements” provided by the Private Securities Litigation Reform Act of 1995. Forward-looking statements are generally not historical facts. Words such as “expect,” “feel,” “believe,” “will,”

regulation or taxation of health benefits and managed care operations, including, but not limited to, the impact of the Patient Protection and Affordable Care Act and the Health Care and Education Reconciliation Act of 2010, or Health Care Reform, and the impact of any future modification, repeal or replacement of Health Care Reform; trends in health care costs and utilization rates; our ability to secure sufficient premium rates including regulatory approval for and implementation of such

rates; our participation in federal and state health insurance exchanges under Health Care Reform, which have experienced and continue to experience challenges due to implementation of initial and phased-in provisions of Health Care Reform, and which entail uncertainties associated with the mix and volume of business, particularly in our Individual and Small Group markets, that could negatively impact the adequacy of our premium rates and which may not
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A2. `E2CHK-28641af1dd53a56c`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `MAINTAINED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** Under "Financial outlook and guidance" the company "is projecting 10% to 12% revenue growth, GAAP earnings per diluted share ... of $5.26 to $5.36" -- specific figures, but with no word reaffirming, raising, or lowering a previously issued number. Section 3 requires MAINTAINED to be an explicit reaffirmation, so stored MAINTAINED is unsupported. Owner must weigh whether restating full-year guidance in a later quarterly release should count as an implicit reaffirmation or, as I read the rubric, fall to NONE.
**Rater's reason (its own words, written before it saw any stored label):** Guidance is the least certain field: 'the company is projecting 10% to 12% revenue growth ... non-GAAP earnings per diluted share ... of $3.60 to $3.70' is quantified but is neither reaffirmed nor compared to a prior figure, so no raise/maintain/lower direction is stated; sentiment POSITIVE on 'We are pleased with our first quarter results' and 'an exciting uptake of the NovaSeq platform'.
<details><summary>chunk text (2521 chars)</summary>

```
compared to $150 million

in the prior year period. Excluding the effect of performance-based compensation related to the GRAIL Series B financing, acquisition related gain, amortization of acquired intangible assets, and contingent compensation, but including stock-based compensation expense, SG&A expenses as a percentage of revenue were

25.6% , including 1.5% attributable to GRAIL and Helix. This compares to 25.7% in the prior year period, including 0.6% attributable to GRAIL and Helix. Depreciation and amortization expenses were $38 million and capital expenditures for free cash flow purposes were

$83 million during the first quarter of 2017 . At the close of the quarter, the company held $1.8 billion in cash, cash equivalents and short-term investments, compared to $1.6 billion as of January 1, 2017 .

"We are pleased with our first quarter results,” said Francis deSouza, President and CEO. “We are witnessing an exciting uptake of the NovaSeq platform with more than 135 orders placed in Q1, and look forward to the advancements in genomics this instrument will enable for years to come.”

Updates since our last earnings release: • Launched the VeriSeq™ NIPT Solution in Europe, a CE-IVD marked next-generation sequencing based approach to noninvasive prenatal testing • Contributed more than 8,000 associations of somatic genetic alterations to the Clinical Interpretation of Variants in Cancer (CIViC) database

• Announced the iHope Network, a consortium of institutions who have committed to providing clinical whole genome sequencing to underserved families • Announced that GRAIL raised $900 million in the first close of its Series B financing and that Illumina’s stake is now less than 20 percent of GRAIL

• Announced that John W. Thompson will join the company’s Board of Directors • Repurchased $101 million of common stock under the previously announced share repurchase program thereby completing the authorization Financial outlook and guidance

For fiscal 2017, the company is projecting 10% to 12% revenue growth, GAAP earnings per diluted share attributable to Illumina stockholders of $5.26 to $5.36 and non-GAAP earnings per diluted share attributable to Illumina stockholders of $3.60 to $3.70. Our annual guidance assumes second quarter revenue growth of approximately 7% versus the prior year, GAAP earnings per diluted share attributable to Illumina stockholders of $0.56 to $0.61 and non-GAAP earnings per diluted share attributable to Illumina stockholders of $0.65 to $0.70.
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A3. `E2CHK-9992a913245c70dc`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `MAINTAINED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** The chunk prints a "2022 Guidance" production and cost table with no statement that any figure was reaffirmed, raised, or reduced; the only forward comparison is an acquisition "expected to drive average pro forma free cash flow breakeven down approximately $0.15 per MMBtu," which is a deal effect, not a revision of issued guidance. Section 3's MAINTAINED requires an explicit reaffirmation, which is absent, so stored MAINTAINED is unsupported. Owner must weigh the shared residual question of where undirected quantified guidance tables land.
**Rater's reason (its own words, written before it saw any stored label):** Guidance is NONE because the '2022 Guidance' table states figures without any statement that a target was raised, lowered, reaffirmed, or withdrawn versus a prior figure; sentiment is POSITIVE on 'improves the durability of EQT's free cash flow generation' and 'drive average pro forma free cash flow breakeven down approximately $0.15 per MMBtu'.
<details><summary>chunk text (2297 chars)</summary>

```
EQT previously announced its agreement to acquire Tug Hill’s upstream assets and XcL Midstream’s gathering and processing assets, for consideration of approximately $2.6 billion in cash and 55.0 million shares of EQT common stock, subject to customary closing adjustments. The transaction is expected to close in the fourth quarter of 2022, with an effective date of July 1, 2022.

The Tug Hill assets are anticipated to add approximately 90,000 core net acres offsetting EQT's existing core leasehold in West Virginia, approximately 800 MMcfe/d of production, and 11 years of inventory at maintenance capital levels. XcL Midstream adds 95-miles of owned and operated midstream gathering systems connected to every major long-haul interstate pipeline in southwest Appalachia. The liquids yields and integrated cost structure improves the durability of EQT's free cash flow generation and is expected to drive average pro forma free cash flow

(1) breakeven down approximately $0.15 per MMBtu through 2027. (1) A non-GAAP financial measure. See the Non-GAAP Disclosures section of this news release for the definition of, and other important information regarding, this non-GAAP financial measure. 3 2022 Guidance Production

Q4 2022 Full Year 2022 Total sales volume (Bcfe) 450 – 475 1,925 – 1,975 Liquids sales volume, excluding ethane (MBbls) 2,610 – 2,710 10,500 – 10,750 Ethane sales volume (MBbls) 1,565 – 1,665 6,100 – 6,200 Total liquids sales volume (MBbls)

4,175 – 4,375 16,600 – 16,950 Btu uplift (MMBtu / Mcf) 1.045 – 1.055 1.045 – 1.055 Average differential ($ / Mcf) ($0.95) – ($0.85) ($0.85) – ($0.75) Resource Counts Top-hole Rigs 1 – 2 Horizontal Rigs 2 – 3

Frac Crews 2 – 3 Per Unit Operating Costs ($ / Mcfe) Gathering $0.67 – $0.69 $0.66 – $0.68 Transmission $0.31 – $0.33 $0.29 – $0.31 Processing $0.09 – $0.11 $0.08 – $0.10 LOE $0.07 – $0.09 $0.08 – $0.10

Production taxes $0.07 – $0.09 $0.06 – $0.08 SG&A $0.13 – $0.15 $0.11 – $0.13 Total per unit operating costs $1.34 – $1.46 $1.28 – $1.40 Financial ($ Billions) Adjusted EBITDA (a) $3.450 – $3.550 Adjusted operating cash flow (a)

$3.300 – $3.400 Capital expenditures (b) $0.375 – $0.425 $1.400 – $1.475 Free cash flow (a) $1.900 – $2.000 Based on NYMEX natural gas price of $6.62 per MMBtu as of October 25, 2022. (a)
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A4. `E2CHK-b9cbe918d3cead0a`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `RAISED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** The headline says the company "PROVIDES FISCAL 2020 GUIDANCE" and the text expects "full fiscal year 2020 revenues to increase 4.0 to 4.5 percent" -- growth measured against prior-year actual results, not an increase of a previously issued target. Section 3's RAISED requires a target "increased versus a prior figure" in the sense of revising previously-issued guidance, so stored RAISED is unsupported. Owner must weigh whether "a prior figure" in RAISED can mean prior-year actuals; on my reading it cannot, which makes this fresh guidance and therefore NONE.
**Rater's reason (its own words, written before it saw any stored label):** Guidance is NONE because the passage 'PROVIDES FISCAL 2020 GUIDANCE' with fresh figures ('between $12.50 and $12.65') but never states any figure was raised, lowered, reaffirmed, or withdrawn versus a prior figure, and the rubric's five labels only describe revisions.
<details><summary>chunk text (2635 chars)</summary>

```
Exhibit 99.1 1 Becton Drive Franklin Lakes, NJ 07417 www.bd.com Contact: Monique N. Dolecki, Investor Relations - 201-847-5378 Kristen Cardillo, Corporate Communications - 201-847-5657 BD ANNOUNCES RESULTS FOR 2019 FOURTH FISCAL QUARTER AND FULL YEAR; PROVIDES FISCAL 2020 GUIDANCE •

As reported, full fiscal year revenues of $17.290 billion increased 8.2 percent. • On a comparable, currency-neutral basis, revenues increased 5.1 percent for the full fiscal year. • As reported, full fiscal year diluted earnings per share of $3.89 increased

548.3 percent. • As adjusted, full fiscal year diluted earnings per share of $11.68 increased 6.1 percent, or 11.9 percent on a currency-neutral basis. • The company expects full fiscal year 2020 revenues to increase 4.0 to 4.5 percent as reported, or 5.0 to 5.5 percent on a currency-neutral basis.

As adjusted, the company expects full fiscal year 2020 diluted earnings per share to be between $12.50 and $12.65, resulting in growth of approximately 9.5 to 11.0 percent on a currency-neutral basis. This represents growth of approximately 7.0 to 8.5 percent including the estimated unfavorable impact of foreign currency. Adjusted diluted earnings per share guidance includes an adverse impact of approximately 500 basis points related to the expiration of the Gore royalty.

Franklin Lakes, NJ ( November 5, 2019 ) - BD (Becton, Dickinson and Company) (NYSE: BDX), a leading global medical technology company, today reported quarterly revenues of $4.584 billion for the fourth fiscal quarter ended September 30, 2019 . This represents an increase of

4.1 percent over the prior-year period. On a comparable, currency-neutral basis, revenues increased 6.2 percent over the prior-year period. For the full fiscal year ended September 30, 2019, revenues of $17.290 billion increased 8.2 percent from the prior-year period. On a comparable, currency-neutral basis, full fiscal year revenues of

$17.281 billion grew 5.1 percent.

“We are very proud of our accomplishments in fiscal year 2019. Our performance this year demonstrates our ability to overcome multiple headwinds and deliver on our financial and operational goals,” said Vincent A. Forlenza, chairman and CEO. “We enter fiscal 2020 with continued optimism. There are significant opportunities ahead to leverage the capabilities we’ve built to better serve our customers and their patients around the world. It has been a privilege to lead BD and our global team of talented associates. I’m confident that under Tom Polen’s leadership the company will further accelerate its impact as BD enters its next phase of value creation.”
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A5. `E2CHK-cf5aa0cd9c95e4ee`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `MAINTAINED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** The passage lays out a complete "2022 Guidance" table but never says these figures reaffirm, raise, or cut any prior number; the only backward reference is "a presentation of the company's 2022 and updated 2021 guidance," which states no direction. Section 3 defines MAINTAINED as a passage that "explicitly reaffirms previously-issued guidance without changing it," so stored MAINTAINED is unsupported and NONE is the only remaining label in the closed set. Owner must weigh whether a fresh, fully quantified guidance issuance with no comparison to a prior guidance figure should fall to NONE, as the label set forces, or get its own convention -- this same question decides 10 rows in this batch.
**Rater's reason (its own words, written before it saw any stored label):** Guidance: "The following table summarizes the company's 2022 financial guidance" issues figures without stating any relation to a prior figure, so §3's ambiguity tie-breaker gives NONE; sentiment is a flat figure table plus boilerplate "About" text.
<details><summary>chunk text (2319 chars)</summary>

```
Marketing, selling and administrative expenses are expected to be in the range of $6.4 billion to $6.6 billion. Research and development expenses are expected to be in the range of $7.0 billion to $7.2 billion. Operating margin for 2022 is expected to be approximately 30 percent on a reported basis and approximately 32 percent on a

non-GAAP basis. Other income (expense) is expected to be expense between $100 million and $0 on both a reported basis and on a non-GAAP basis. The 2022 effective tax rate is expected to be approximately 13 to 14 percent on both a reported basis and

non-GAAP basis, assuming no significant changes to U.S. tax policy. 7 The following table summarizes the company’s 2022 financial guidance. 2022 Guidance Revenue $27.8 to $28.3 billion Gross Margin % of Revenue (reported) Approx. 78% Gross Margin % of Revenue

(non-GAAP) Approx. 80% Marketing, Selling & Administrative $6.4 to $6.6 billion Research & Development $7.0 to $7.2 billion Other Income/(Expense) $(100) million to $0 Tax Rate Approx. 13 to 14% Earnings per share (reported) $8.00 to $8.15 Earnings per share

(non-GAAP) $8.50 to $8.65 Operating Margin (reported) Approx. 30% Operating Margin (non-GAAP) Approx. 32% Non-GAAP adjustments are consistent with the earnings per share table above. Webcast of Conference Call and Investor Materials As previously announced, investors and the general public can access a live webcast of the Investment Community Meeting, including a presentation of the

company’s 2022 and updated 2021 guidance, through a link on Lilly’s website at www.lilly.com . The conference call will begin at 9 a.m. Eastern time today and will be available for replay via the website. About Eli Lilly and Company

Lilly is a global healthcare

leader that unites caring with discovery to create medicines that make life better for people around the world. We were founded more than a century ago by a man committed to creating high-quality medicines that meet real needs, and today we remain

true to that mission in all our work. Across the globe, Lilly employees work to discover and bring life-changing medicines to those who need them, improve the understanding and management of disease, and give back to communities through philanthropy and volunteerism. To learn more about Lilly, please visit us at
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A6. `E2CHK-d31e86fcdacacb90`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `RAISED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** The outlook is issued fresh -- "First quarter revenue guidance of approximately $6.6 billion; and First quarter Adjusted EBITDA of approximately $3.9 billion" -- with no statement that any figure was increased versus a prior target. Section 3's RAISED requires an increase versus a prior figure, so stored RAISED is unsupported. Owner must weigh the shared residual question: quantified new-period guidance with no directional comparison falls to NONE on my reading of the closed label set.
**Rater's reason (its own words, written before it saw any stored label):** Guidance is NONE because 'First quarter revenue guidance of approximately $6.6 billion' is newly issued outlook with no prior figure raised, lowered, reaffirmed or withdrawn; sentiment is NEUTRAL given the predominantly procedural dividend, conference-call and non-GAAP-definition content.
<details><summary>chunk text (3713 chars)</summary>

```
23 +28 % Total net revenue $ 23,888 100 % $ 22,597 100 % First Quarter Fiscal Year 2021 Business Outlook Based on current business trends and conditions, the outlook for the first quarter of fiscal year 2021, ending January 31, 2021, is expected to be as follows:

• First quarter revenue guidance of approximately $6.6 billion; and • First quarter Adjusted EBITDA of approximately $3.9 billion, or 59 percent of projected revenue.

Broadcom Inc. will be presenting to investors at the J.P. Morgan Tech Forum on January 12, 2021. Quarterly Dividends

The Company’s Board of Directors has approved a quarterly cash dividend on its common stock of $3.60 per share. The common stock dividend is payable on December 31, 2020 to common stockholders of record at the close of business (5:00 p.m. Eastern Time) on December 21, 2020.

The Company’s Board of Directors has also approved a quarterly cash dividend on its 8.00% Mandatory Convertible Preferred Stock, Series A, of $20.00 per share. This dividend is payable on December 31, 2020 to preferred stockholders of record at the close of business (5:00 p.m. Eastern Time) on December 15, 2020.

Broadcom Inc. will host a conference call to review its financial results for the fourth quarter and fiscal year ended November 1, 2020, and to discuss the business outlook, today at 2:00 p.m. Pacific Time. Those wishing to access the call should dial (866) 310-8712; International +1 (720) 634-2946. The passcode is 5074985. A replay of the call will be accessible for one week after the call. To access the replay dial (855) 859-2056; International +1 (404) 537-3406; and reference the passcode: 5074985. A webcast of the conference call will also be available in the “Investors” section of Broadcom’s website at www.broadcom.com.

3 Basis of Presentation

The Company’s financial results include contributions from the Symantec enterprise security business’s continuing operations starting in the first quarter of fiscal year 2020. The financial results from businesses that have been classified as discontinued operations in the Company’s financial statements are not included in the results presented above, unless otherwise stated.

In addition to GAAP reporting, Broadcom provides investors with net revenue, net income, operating income, gross margin, operating expenses, cash flow and other data on a non-GAAP basis. This non-GAAP information excludes amortization of acquisition-related intangible assets, stock-based compensation expense, restructuring, impairment and disposal charges, acquisition-related costs, including integration costs, purchase accounting effect on inventory, litigation settlements, loss on debt extinguishment, gain from lapse of indemnification, gains (losses) on investments, gain from sale of business, income (loss) from discontinued operations and non-GAAP tax reconciling adjustments. Management does not believe that these items are reflective of the Company’s underlying performance. Internally, these non-GAAP measures are significant measures used by management for purposes of evaluating the core operating performance of the Company, establishing internal budgets, calculating return on investment for development programs and growth initiatives, comparing performance with internal forecasts and targeted business models, strategic planning, evaluating and valuing potential acquisition candidates and how their operations compare to the Company’s operations, and benchmarking performance externally against the Company’s competitors. The exclusion of these and other similar items from Broadcom’s non-GAAP financial results should not be interpreted as implying that these items are non-recurring, infrequent or unusual.
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A7. `E2CHK-df0f98a67031f9fb`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `RAISED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** The release "Provides 2018 Financial Guidance" with "2018 EPS guidance of $13.50 to $14.00 on an Adjusted basis" -- an initial issuance, with no statement that a previously issued 2018 figure was increased. The dividend increase to "$0.50 per share, an increase of 25 percent" is a declared corporate action, not a forward financial target, so it does not trigger section 3's RAISED either; stored RAISED is unsupported. Owner must weigh the shared residual question of where first-issuance quantified guidance lands.
**Rater's reason (its own words, written before it saw any stored label):** Guidance NONE because '2018 EPS guidance of $13.50 to $14.00' is an initial issuance under 'Provides 2018 Financial Guidance' with no prior figure raised, reaffirmed, lowered or withdrawn; the 'Guaranty fund assessment expense' and 'workforce reduction programs' charges are a mechanical statutory assessment and a non-asset restructuring cost, so neither earns a flag.
<details><summary>chunk text (2389 chars)</summary>

```
Exhibit 99.1 news release Humana Inc. 500 West Main Street P.O. Box 1438 Louisville, KY 40202 http://www.humana.com FOR MORE INFORMATION CONTACT: Amy Smith Humana Investor Relations (502) 580-2811 e-mail: Amysmith@humana.com Tom Noland Humana Corporate Communications (502) 580-3674 e-mail: Tnoland@humana.com Humana Reports Fourth Quarter 2017 Financial Results;

Provides 2018 Financial Guidance • Full year 2017 earnings per diluted common share (EPS) of $11.71 on an Adjusted basis, $16.81 on a GAAP basis • Full year 2017 operating cash flow of $4.1 billion • Individual Medicare Advantage finished 2017 above target margins, with strong membership growth in the Annual Election Period providing momentum into 2018

• 2018 EPS guidance of $13.50 to $14.00 on an Adjusted basis, $13.16 to $13.66 on a GAAP basis, including a net benefit from tax reform of approximately $2.00 EPS • Company’s Board of Directors increases cash dividend to $0.50 per share, an increase of 25

percent from prior dividend of $0.40 per share LOUISVILLE, KY (February 7, 2018) – Humana Inc. (NYSE: HUM) today reported diluted earnings per common share (EPS) for the quarter ended December 31, 2017 (4Q17) versus the quarter ended December 31, 2016 (4Q16) and for the year ended December 31, 2017 (FY17) versus for the year ended December 31, 2016 (FY16) as follows:

Consolidated pretax income (loss) In millions 4Q17 (a) 4Q16 (b) FY17 (c) FY16 (d) Generally Accepted Accounting Principles (GAAP) $ 490 ($ 486 ) $ 4,020 $ 1,552 Net (gain) expenses associated with the terminated merger agreement (for FY17, primarily the

break-up fee) 11 23 (936 ) 104 Amortization associated with identifiable intangibles 21 18 75 77 Guaranty fund assessment expense to support the policyholder obligations of Penn Treaty (an unaffiliated long-term care insurance company) — — 54 — Operating loss (income) associated with the Individual Commercial segment

14 634 (193 ) 869 Charges associated with voluntary and involuntary workforce reduction programs 23 — 148 — Costs associated with early retirement of debt in 4Q17 17 — 17 — Reserve strengthening for the company’s non-strategic closed block of long-term care insurance business (f)

— 505 — 505 Adjusted (non-GAAP) – 4Q16 and FY16 as recast $ 576 $ 694 $ 3,185 $ 3,107 1 Diluted earnings per common share (EPS) 4Q17 (a) 4Q16 (b) FY17 (c) FY16 (d) GAAP $ 1.29 ($ 2.68
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A8. `E2CHK-f6a580a23f5c73c2`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `MAINTAINED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** The "Fiscal 2022 Guidance" bullets are issued fresh ("Net interest expense of approximately $1.5 billion," "Tax rate of approximately 24.6 percent") with no language reaffirming or revising any earlier figure; several items are qualitative ("slightly positive," "low single digits"). Section 3's MAINTAINED requires an explicit reaffirmation, which is absent, so stored MAINTAINED is unsupported. Owner must weigh the shared question of where undirected new-year guidance lands.
**Rater's reason (its own words, written before it saw any stored label):** Guidance was the close call: 'Fiscal 2022 Guidance: • Sales growth ... slightly positive • Operating margin approximately flat' is newly issued rather than raised, lowered, reaffirmed or withdrawn, which the rubric's residual clause sends to NONE; the long 'impact of tariffs; ... commodity or other price inflation and deflation' string is a safe-harbor noun list that fails mining depth.
<details><summary>chunk text (4325 chars)</summary>

```
th consecutive quarter the Company has paid a cash dividend. Fiscal 2022 Guidance

The Company’s fiscal 2022 guidance assumes the run-rate of dollar demand it has observed over the last two quarters continues through fiscal 2022. This dollar run-rate is adjusted for the Company’s historical seasonality to calculate its sales outlook for 2022.

Fiscal 2022 Guidance: • Sales growth and comparable sales growth to be slightly positive • Operating margin approximately flat with fiscal 2021 • Net interest expense of approximately $1.5 billion • Tax rate of approximately 24.6 percent • Diluted earnings-per-share-growth to be low single digits

The Home Depot will conduct a conference call today at 9 a.m. ET to discuss information included in this news release and related matters, including a brief update on strategic initiatives. The Company expects the conference call to end no later than 10:30 a.m. ET. Following the call, supplemental slides related to the conference call can be found at https://ir.homedepot.com/financial-reports/quarterly-earnings/2021. The conference call will be available in its entirety through a webcast and replay at ir.homedepot.com/events-and-presentations.

At the end of the fourth quarter, the Company operated a total of 2,317 retail stores in all 50 states, the District of Columbia, Puerto Rico, the U.S. Virgin Islands, Guam, 10 Canadian provinces and Mexico, including 14 stores in the U.S. from a small acquisition completed during the second quarter of fiscal 2021. The Company employs approximately 500,000 associates. The Home Depot's stock is traded on the New York Stock Exchange (NYSE: HD) and is included in the Dow Jones industrial average and Standard & Poor's 500 index.

Certain statements contained herein constitute “forward-looking statements” as defined in the Private Securities Litigation Reform Act of 1995. Forward-looking statements may relate to, among other things, the impact of the COVID-19 pandemic and the related recovery on our business, operations and financial results (which, among other things, may affect many of the items listed below); the demand for our products and services; net sales growth; comparable sales; the effects of competition; our brand and reputation; implementation of store, interconnected retail, supply chain and technology initiatives; inventory and in-stock positions; the state of the economy; the state of the housing and home improvement markets; the state of the credit markets, including mortgages, home equity loans and consumer credit; impact of tariffs; issues related to the payment methods we accept; demand for credit offerings; management of relationships with our associates, potential associates, suppliers and service providers; international trade disputes, natural disasters, climate change, public health issues (including pandemics and quarantines, related shut-downs and other governmental orders, and similar restrictions, as well as subsequent re-openings), cybersecurity events, and other business interruptions that could disrupt supply or delivery of, or demand for, the Company’s products or services; our ability to meet environmental, social and governance (ESG) goals; continuation or suspension of share repurchases; net earnings performance; earnings per share; dividend targets; capital allocation and expenditures; liquidity; return on invested capital; expense leverage; stock-based compensation expense; commodity or other price inflation and deflation; our ability to issue debt on terms and at rates acceptable to us; the impact and expected outcome of investigations, inquiries, claims and litigation, including compliance with related settlements; the effect of accounting charges; the effect of adopting certain accounting standards; the impact of regulatory changes, including changes to tax laws and regulations; store openings and closures; guidance for fiscal 2022 and beyond; financial outlook; and the impact of acquired companies, including HD Supply Holdings, Inc., on our organization and the ability to recognize the anticipated benefits of those acquisitions. Forward-looking statements are based on currently available information and our current assumptions, expectations and projections about future events. You should not rely on our forward-looking statements. These
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A9. `E2CHK-f8154d76409080a3`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `MAINTAINED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** The chunk contains an "Adjusted Earnings Per Share Guidance (Unaudited)" schedule with a low/high pair ("Adjusted earnings per share $ 5.02 $ 5.06") but no words reaffirming, raising, or cutting anything. Section 3 requires MAINTAINED to "explicitly reaffirm previously-issued guidance," and no such statement exists, so stored MAINTAINED is unsupported. Owner must weigh the same residual question as the other guidance rows: does a quantified outlook schedule with no directional language fall to NONE?
**Rater's reason (its own words, written before it saw any stored label):** Guidance is NONE because the 'Adjusted Earnings Per Share Guidance' table presents figures with no reaffirming, raising, lowering, or withdrawing language relative to a prior figure; sentiment is NEUTRAL because the table mixes 'Pharmacy sales 4.6%' against 'Front store sales (5.8)%' with no characterization by the filer.
<details><summary>chunk text (2348 chars)</summary>

```
Front store (2.4 )% (3.7 )% (3.7 )% (1.6 )% Total prescription volume (90 Day = 3 Rx) (1) 10.7 % 6.4 % 7.7 % 4.6 % Same store increase (decrease) (2) : Total sales 1.7 % 2.0 % 1.1

% 2.3 % Pharmacy sales 4.6 % 4.8 % 4.3 % 4.5 % Front store sales (3) (5.8 )% (4.5 )% (6.6 )% (2.9 )% Prescription volume (90 Day = 3 Rx) (1) 4.4 % 5.1 % 4.8 % 3.7

% Generic dispensing rate 84.8 % 83.3 % 84.7 % 83.3 % Pharmacy % of total revenues 74.1 % 71.8 % 72.5 % 70.5 % (1) Includes the adjustment to convert 90-day, non-specialty prescriptions to the equivalent of three 30-day prescriptions. This adjustment reflects the fact that these prescriptions include approximately three times the amount of product days supplied compared to a normal prescription.

(2) Same store sales and prescriptions exclude revenues from MinuteClinic ® , and revenue and prescriptions from stores in Brazil, LTC operations and from commercialization services. (3) Front store same store sales would have been approximately 490 and 690 basis points higher for the three and nine months ended

September 30, 2015 , respectively, if tobacco and the estimated associated basket sales were excluded from the three and nine months ended September 30, 2014 . 11 Adjusted Earnings Per Share Guidance (Unaudited)

In millions, except per share amounts Year Ending December 31, 2015 Income before income tax provision (1)(2) $ 8,759 $ 8,834 Amortization 608 608 Adjusted income before income tax provision 9,367 9,442 Adjusted income tax provision and other (3) 3,717

3,747 Adjusted income from continuing operations 5,650 5,695 Net income attributable to noncontrolling interest (2 ) (2 ) Adjusted net income $ 5,648 $ 5,693 Weighted average diluted shares outstanding 1,126 1,126 Adjusted earnings per share $ 5.02 $ 5.06

Adjustments for acquisition-related costs: Add back: Per share bridge financing, transaction and integration costs recorded during the nine months ended September 30, 2015 (1) 0.12 0.12 Adjusted earnings per share (excluding acquisition-related bridge financing, transaction and integration costs) (4) $

5.14 $ 5.18 In millions, except per share amounts Three Months Ending December 31, 2015 Income before income tax provision (2) $ 2,595 $ 2,670 Amortization 189 189 Adjusted income before income tax provision 2,784 2,859 Adjusted income tax provision and other
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A10. `E2CHK-ffe43fc41893b067`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `RAISED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** The passage states "For fiscal year 2022, the company expects total revenue in the range of $3.395 billion to $3.435 billion" and gives GAAP/non-GAAP margin and EPS ranges, but never says any of these were raised relative to a prior target. Section 3's RAISED requires the passage to state that a target "has been increased versus a prior figure," so stored RAISED is unsupported. Owner must weigh the shared residual convention for quantified guidance carrying no directional claim.
**Rater's reason (its own words, written before it saw any stored label):** 'the company expects total revenue in the range of $3.395 billion to $3.435 billion' is issued outlook with no stated prior figure raised, lowered or reaffirmed, so NONE; tone is mechanical outlook plus corporate boilerplate, and 'the rapidly evolving global tax environment' is ordinary tax-regime language, not a regulatory action.
<details><summary>chunk text (2370 chars)</summary>

```
For fiscal year 2022, the company expects total revenue in the range of $3.395 billion to $3.435 billion. On a GAAP basis, operating margin is expected to be in the range of 28.5 percent to 30 percent and GAAP net income per diluted share for 2022 is expected to be in the range of $2.51 to $2.59. Using the non-GAAP measures defined below, operating margin for 2022 is expected to be in the range of 38.5 percent to 40 percent and net income per diluted share for 2022 is expected to be in the range of $3.89 to $3.97.

The company utilizes a long-term projected non-GAAP tax rate, which reflects currently available information, as well as other factors and assumptions. The non-GAAP tax rate could be subject to change for a variety of reasons, including the rapidly evolving global tax environment, significant changes in the company’s geographic earnings mix, or other changes to the company’s strategy or business operations. The company expects to use this normalized non-GAAP tax rate through fiscal 2025 but will re-evaluate this rate periodically for significant items that may materially affect its projections.

Anirudh Devgan, president and chief executive officer, and John Wall, senior vice president and chief financial officer, will host the first quarter 2022 financial results audio webcast today, April 25, 2022, at 2 p.m. (Pacific) / 5 p.m. (Eastern). Attendees are asked to register at the website at least 10 minutes prior to the scheduled webcast. An archive of the webcast will be available starting April 25, 2022 at 5 p.m. (Pacific) and ending June 17, 2022 at 5 p.m. (Pacific). Webcast access is available at www.cadence.com/cadence/investor_relations.

Cadence is a pivotal leader in electronic systems design, building upon more than 30 years of computational software expertise. The company applies its underlying Intelligent System Design strategy to deliver software, hardware and IP that turn design concepts into reality. Cadence customers are the world’s most innovative companies, delivering extraordinary products from chips to boards to complete systems for the most dynamic market applications, including hyperscale computing, 5G communications, automotive, mobile, aerospace, consumer, industrial and healthcare. For eight years in a row, Fortune magazine has named Cadence one of the 100 Best Companies to Work For. Learn more a
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

### pattern `new-or-initiated-guidance-not-raised` — 6 row(s)

#### A11. `E2CHK-22f9206e6562326a`  ·  field `guidance_direction`  ·  arm P
**Stored (student):** `RAISED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** The outlook reads "The company now expects fiscal 2018 GAAP earnings per diluted share... of $5.32 to $5.37," giving a quantified figure but neither a prior figure nor any statement of direction; "now expects" signals an update, not an increase. Rubric section 3 requires RAISED to state that the target "has been increased versus a prior figure," so RAISED is unsupported and NONE is the residual. The owner must weigh whether "now expects" plus a fresh number should be read as an upward revision without any comparative in the text.
**Rater's reason (its own words, written before it saw any stored label):** Guidance is NONE because "The company now expects fiscal 2018 GAAP earnings per diluted share ... of $5.32 to $5.37" states neither an increase nor a reaffirmation against a prior figure, and "projects revenue growth of approximately 20%" lacks reaffirmation language; the flag rests on "Reached a legal settlement ... with Premaitha", while the received NMPA clearance is a favorable approval and not a flag.
<details><summary>chunk text (2464 chars)</summary>

```
Depreciation and amortization expenses were $46 million and capital expenditures for free cash flow purposes were $64 million during the third quarter of 2018 . At the close of the quarter, the company held $3.4 billion in cash, cash equivalents and short-term investments, compared to

“Illumina’s strong performance in the third quarter of 2018 reflected growth across our sequencing and arrays portfolios,” said Francis deSouza, President and CEO. “Sequencing system revenue of $138 million was the strongest since 2015, reflecting strong demand within our sequencing family from the NovaSeq, the most powerful and flexible sequencer ever, to the iSeq, our most accessible and easiest-to-use sequencer.”

Updates since our last earnings release: • Received regulatory approval for the MiSeqDx, Illumina’s first next-generation sequencing (NGS) system cleared by the National Medical Products Administration (NMPA) in China • Released the S4 200 cycle kit for the NovaSeq in response to customer requests to support high-throughput sequencing for whole exome, RNA and single-cell sequencing

Reached a legal settlement as well as a supply and license agreement with Premaitha, who will now license Illumina’s IP for NIPT, launch an IONA test that runs on Illumina sequencing technology, and work with customers to migrate to Illumina systems

Completed an offering of 0.0% convertible senior notes due 2023 for an aggregate principal amount of $650 million, plus an additional $100 million pursuant to the initial purchasers’ option to purchase additional notes, for total net proceeds of $735 million

• Repurchased $103 million of common stock in the third quarter under the previously announced share repurchase program Financial outlook and guidance

For fiscal 2018, the company projects revenue growth of approximately 20%. The company now expects fiscal 2018 GAAP earnings per diluted share attributable to Illumina stockholders of $5.32 to $5.37 and non-GAAP earnings per diluted share attributable to Illumina stockholders of $5.70 to $5.75.

The conference call will begin at 2:00 pm Pacific Time (5:00 pm Eastern Time) on Tuesday, October 23, 2018. Interested parties may access the live teleconference through the Investor Relations section of Illumina’s web site under the “company” tab at www.illumina.com. Alternatively, individuals can access the call by dialing 800-708-4540, or 1-847-619-6397 outside North America, both with passcode 47554920.
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A12. `E2CHK-4f560e57c0051a11`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `RAISED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** The only forward figures are two bare table lines - "2020 adjusted earnings per share outlook >= $4.37" and "2020 adjusted earnings per share growth outlook >= 11%" - with no prior figure and no revision language of any kind. Rubric section 3's RAISED requires the passage to state that a target "has been increased versus a prior figure," which nothing here does. NONE is the residual; the owner should rule once on unrevised forward outlook lines in reconciliation tables.
**Rater's reason (its own words, written before it saw any stored label):** Guidance is NONE even though "2020 adjusted earnings per share outlook ≥ $4.37" is a quantified forward figure, because the passage nowhere reaffirms, raises, lowers or withdraws it relative to a prior figure; the surrounding text is a reconciliation schedule with no tone.
<details><summary>chunk text (2230 chars)</summary>

```
— 11 — 72 First Data financing costs, debt discounts and other — — — 7 First Data sales commissions — — — — First Data deferred conversion costs — 4 — 22 Total First Data amortization 2 $ —

$ 58 $ — $ 396 Combined acquisition-related intangible assets $ 504 $ 420 $ 1,603 $ 709 Combined capitalized software and other intangibles 41 50 119 179 Combined purchased software 78 43 212 129 Combined financing costs, debt discounts and other

13 11 36 123 Combined sales commissions 23 20 67 61 Combined deferred conversion costs 8 10 22 38 Total combined amortization $ 667 $ 554 $ 2,059 $ 1,239 1

2 467 Severance and restructuring costs 3 150 Amortization of acquisition-related intangible assets 4 1,222 Debt financing activities 5 287 Non wholly-owned entity activities 6 (53) Tax impact of adjustments 7 (480) Gain on sale of businesses 8 (12) Tax impact of gain on sale of businesses

7 3 Discrete tax items 9 (5) 2019 adjusted net income 2,775 Impact of divestitures 8 (46) Taxes on Impact of divestitures 7 10 2019 adjusted net income, as adjusted for divestitures $ 2,739 Weighted average common shares outstanding - diluted

522.6 Issuance of shares for combination 167.0 Dilutive impact of exchanged equity awards 4.5 Combined weighted average common shares outstanding - diluted 10 694.1 2019 GAAP earnings per share 10 $ 1.71 Combined earnings per share 10 $ 1.72 Combined adjustments - net of income taxes:

Merger and integration costs 2 0.52 Severance and restructuring costs 3 0.17 Amortization of acquisition-related intangible assets 4 1.36 Debt financing activities 5 0.32 Non wholly-owned entity activities 6 (0.06) Gain on sale of businesses 8 (0.01) Discrete tax items

9 (0.01) 2019 adjusted earnings per share 4.00 Impact of divestitures 8 (0.05) 2019 adjusted earnings per share, as adjusted for divestitures $ 3.95 2020 adjusted earnings per share outlook ≥ $4.37 2020 adjusted earnings per share growth outlook ≥ 11%

In millions, except per share amounts, unaudited. Earnings per share is calculated using actual, unrounded amounts. See pages 3-5 for disclosures related to the use of non-GAAP financial measures. 19 News Release Fiserv, Inc. Full Year Forward-Looking Non-GAAP Financial Measures (cont.)
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A13. `E2CHK-881ca5c9182d3a82`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `RAISED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** The guidance bullets read "Full year 2017 GAAP net income is now expected to be greater than $10.35" and "adjusted net income is now expected to be greater than $11.70" - an updated quantified figure, but the passage never states a prior figure or that the target was increased, which rubric section 3 requires for RAISED. Inferring an upward revision from "now" and "our updated 2017 outlook" would go beyond what the text asserts, contrary to rubric section 0. This is the closest case in the family, so the owner must weigh whether "now expected" plus favorable framing suffices for RAISED.
**Rater's reason (its own words, written before it saw any stored label):** Guidance is my least certain field: 'Full year 2017 GAAP net income is now expected to be greater than $10.35' is specific and quantified but is never stated as increased versus a prior figure nor explicitly reaffirmed, so under the letter of the rubric it is NONE; sentiment POSITIVE on 'I am pleased with our second quarter 2017 results, carrying forward our operating momentum' and 'solid performance across our various business segments'.
<details><summary>chunk text (2264 chars)</summary>

```
Exhibit 99.1 PRESS RELEASE ANTHEM REPORTS SECOND QUARTER 2017 RESULTS • Net income was $3.16 per share, including net negative adjustment items of $0.21 per share. Adjusted net income was $3.37 per share (refer to the GAAP reconciliation table on page 14).

• Medical enrollment has increased by approximately 0.5 million members in 2017, or 1.2%, totaling approximately 40.4 million members as of June 30, 2017. • Company expects medical enrollment to grow by nearly 300 - 500 thousand members for the full year 2017.

• Full year 2017 GAAP net income is now expected to be greater than $10.35. Full year adjusted net income is now expected to be greater than $11.70 (refer to the GAAP reconciliation table on page 14). • Company increased its third quarter 2017 dividend to shareholders by $0.05 per share to $0.70 per share.

Indianapolis, Ind. – July 26, 2017 – Anthem, Inc. (NYSE: ANTM) today announced that second quarter 2017 net income was $855.3 million, or $3.16 per share. These results included net negative adjustment items of $0.21 per share. Net income in the second quarter of 2016 was $780.6 million, or $2.91 per share, which included net negative adjustment items of

$0.42 per share. Excluding the items noted in each period, adjusted net income was $3.37 per share in the second quarter of 2017 compared to the adjusted net income of $3.33 per share in the prior year quarter (refer to page 14 for a reconciliation to the most directly comparable measure calculated in accordance with U.S. generally accepted accounting principles, or “GAAP”).

“I am pleased with our second quarter 2017 results, carrying forward our operating momentum. Our commitment to improving the quality and affordability of health care for our customers is resonating in the marketplace and benefiting our shareholders,” said Joseph Swedish, president and chief executive officer.

“Our solid second quarter financial results reflect solid performance across our various business segments, which is reflected in our updated 2017 outlook,” said John Gallina, executive vice president and chief financial officer. 1 CONSOLIDATED HIGHLIGHTS Membership: Medical enrollment totaled approximately 40.4 million members at June 30, 2017, an increase of 0.6 million members, or
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A14. `E2CHK-8a0a66af1210f721`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `RAISED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** The text says the company "is providing full year 2024 guidance" with figures such as "Revenue between $9.075 billion to $9.225 billion" - an initiation, with no prior figure quoted and no statement that any target was increased. Rubric section 3 defines RAISED as a target that "has been increased versus a prior figure," which this passage never asserts, so RAISED fails on its own terms and NONE is the only residual label. The owner must weigh where newly-issued (not revised) quantified guidance belongs, since section 3's preamble mentions "issues new guidance" but the five labels offer no home for it except NONE.
**Rater's reason (its own words, written before it saw any stored label):** Guidance NONE because 'Zoetis is providing full year 2024 guidance' issues an initial quantified outlook without any reaffirmed, raised, lowered or withdrawn figure; no LEGAL_REGULATORY_ACTION because the agency decisions cited ('received approval in the U.S. for claims related to the treatment and control of lone star tick infestations') are favorable approvals, not adverse ones.
<details><summary>chunk text (2406 chars)</summary>

```
received approval in Japan for claims related to efficacy against sarcoptic and demodectic manges. Revolution ® Plus

(selamectin/sarolaner), the company’s topical combination product that treats ticks, fleas, ear mites, lice and gastrointestinal worms and prevents heartworm disease in cats, received approval in the U.S. for claims related to the treatment and control of lone star tick infestations, making it the only parasiticide for cats on the market to defend against four types of ticks.

FINANCIAL GUIDANCE Zoetis is providing full year 2024 guidance, which includes: • Revenue between $9.075 billion to $9.225 billion ( operational growth of 7% to 9%) • Reported net income between $2.468 billion to $2.513 billion • Adjusted net income between $2.650 billion to $2.700 billion (

operational growth of 9% to 11%) • Reported diluted EPS between $5.34 to $5.44 • Adjusted diluted EPS between $5.74 to $5.84 This guidance reflects foreign exchange rates as of late January 2024. Additional details on guidance are included in the financial tables and will be discussed on the company's conference call this morning.

Zoetis will host a webcast and conference call at 8:30 a.m. (ET) today, during which company executives will review fourth quarter and full year 2023 results, discuss financial guidance and respond to questions from financial analysts. Investors and the public may access the live webcast by visiting the Zoetis website at

http://investor.zoetis.com/events-presentations . A replay of the webcast will be archived and made available on February 13, 2024. About Zoetis

As the world’s leading animal health company, Zoetis is driven by a singular purpose: to nurture our world and humankind by advancing care for animals. After innovating ways to predict, prevent, detect, and treat animal illness for more than 70 years, Zoetis continues to stand by those raising and caring for animals worldwide – from veterinarians and pet owners to livestock farmers and ranchers. The company’s leading portfolio and pipeline of medicines, vaccines, diagnostics and technologies make a

4 | difference in over 100 countries. A Fortune 500 company, Zoetis generated revenue of $8.5 billion in 2023 with approximately 14,100 employees. For more information, visit www.zoetis.com. 1 Operational growth (a non-GAAP financial measure) is defined as growth excluding the impact of foreign exchange.
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A15. `E2CHK-b9201930e2c6eb33`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `RAISED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** The only forward content is a table row, "FY 2019 (Estimate) +16% to +23%... Core EPS Growth +3% to +8%," with no prior figure, no comparative, and no revision language. Rubric section 3 requires RAISED to state that a target "has been increased versus a prior figure," which the table does not do, leaving NONE. The owner should rule once on bare forward-estimate rows inside non-GAAP reconciliation tables.
**Rater's reason (its own words, written before it saw any stored label):** Guidance NONE because 'FY 2019 (Estimate) +16% to +23% ... +3% to +8%' is a reconciliation table with no raise, reaffirmation, cut, or withdrawal language attached to it; sentiment NEUTRAL as the growth figures and the 'loss on early extinguishment of debt' / 'gain on PGT Health Care joint venture dissolution' items are presented without characterization.
<details><summary>chunk text (1227 chars)</summary>

```
Core EPS and currency-neutral Core EPS : Total Company Diluted EPS Growth Impact of Change in Non-Core Items* Core EPS Growth FY 2019 (Estimate) +16% to +23% (13%) to (15%) +3% to +8% * Includes impact of loss on early extinguishment of debt and impact of U.S. Tax Act in 2018, year over year changes in incremental non-core restructuring charges and gain on PGT Health Care joint venture dissolution in 2019.

Free cash flow (dollars in millions) : Three Months Ended June 30, 2018 Operating Cash Flow Capital Spending Free Cash Flow $4,199 $(907) $3,292 Twelve Months Ended June 30, 2018 Operating Cash Flow Capital Spending Free Cash Flow $14,867 $(3,717)

$11,150 Adjusted free cash flow productivity (dollars in millions) : Three Months Ended June 30, 2018 Net Earnings Adjustments to Net Earnings (1) Adjusted Net Earnings Free Cash Flow Adjusted Free Cash Flow Productivity $1,890 $195 $2,085 $3,292 158% Twelve Months Ended June 30, 2018

Net Earnings Adjustments to Net Earnings (1) Adjusted Net Earnings Free Cash Flow Adjusted Free Cash Flow Productivity $9,861 $845 $10,706 $11,150 104% (1) Adjustments to Net Earnings relate to the transitional impact of the U.S. Tax Act and the loss on early debt extinguishment.
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A16. `E2CHK-dc843d3a2623c573`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `RAISED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** The guidance bullets all use the word "Initiates" - "Initiates Q4 FY20 Revenue Guidance of $4.743 Billion to $4.753 Billion" and "Initiates Q1 FY21 Revenue Guidance" - with no prior figure and no statement that any target was increased. Rubric section 3 requires for RAISED that the passage "states that a specific forward-looking financial target... has been increased versus a prior figure," which this text never does. NONE is the residual; the owner must rule once on where newly-initiated guidance belongs.
**Rater's reason (its own words, written before it saw any stored label):** Guidance is NONE because the quantified figures are newly initiated ("Initiates Q4 FY20 Revenue Guidance of $4.743 Billion to $4.753 Billion") and are not stated as raised, lowered, reaffirmed, or withdrawn versus any prior figure.
<details><summary>chunk text (2888 chars)</summary>

```
John Cummings Salesforce Investor Relations 415-778-4188 jcummings@salesforce.com Gina Sheibley Salesforce Public Relations 917-297-8988 gsheibley@salesforce.com Salesforce Announces Record Third Quarter Fiscal 2020 Results ◦ Third Quarter Revenue of $4.5 Billion, up 33% Year-Over-Year, 34% in Constant Currency ◦ Current Remaining Performance Obligation of Approximately $12.8 Billion, up 28% Year-Over-Year, 28% in Constant Currency

◦ Remaining Performance Obligation of Approximately $25.9 Billion, up 22% Year-Over-Year ◦ Initiates Q4 FY20 Revenue Guidance of $4.743 Billion to $4.753 Billion, up 32% Year-Over-Year ◦ Initiates Q4 FY20 Current Remaining Performance Obligation Guidance of Approximately 21% Year-Over-Year ◦

Initiates Q1 FY21 Revenue Guidance of $4.800 Billion to $4.835 Billion, up 28% to 29% Year-Over-Year SAN FRANCISCO, Calif. - Dec. 3, 2019 - Salesforce (NYSE: CRM), the global leader in CRM, today announced results for its fiscal third quarter ended October 31, 2019.

“We're now on track to double our revenue in five years,” said Marc Benioff, Chairman and co-CEO, Salesforce. “With Customer 360, only Salesforce is providing companies with a single source of truth, bringing them even closer to their customers across every touchpoint.”

“We had strong growth across our clouds and regions in the quarter as more companies turn to Salesforce as a trusted advisor in their digital transformations,” said Keith Block, co-CEO, Salesforce. “With these trusted customer relationships, continuous innovation and our phenomenal Trailblazer ecosystem, we have never been better positioned for the future.”

Salesforce delivered the following results for its fiscal third quarter: Revenue

: Total third quarter revenue was $4.5 billion, an increase of 33% year-over-year, and 34% in constant currency. Subscription and support revenues were $4.24 billion, an increase of 34% year-over-year. Professional services and other revenues were $274 million, an increase of 22% year-over-year.

: Third quarter GAAP loss per share was $0.12, and non-GAAP diluted earnings per share was $0.75. Mark-to-market accounting of the company’s strategic investments, required by ASU 2016-01, benefited GAAP loss per share by $0.01 based on a U.S. tax rate of 25% and non-GAAP diluted earnings per share by $0.01 based on a non-GAAP tax rate of 22.5%.

Cash : Cash generated from operations for the third quarter was $298 million, an increase of 108% year-over-year. Total cash, cash equivalents and marketable securities ended the third quarter at $6.53 billion. Remaining Performance Obligation : Remaining performance obligation ended the third quarter at approximately $25.9 billion, an increase of 22% year-over-year. Current remaining performance obligation ended the third quarter at approximately $12.8 billion, an increase of 28% year-over-year, 28% in constant currency.
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

### pattern `quantified-outlook-without-revision-language` — 6 row(s)

#### A17. `E2CHK-0138602f200d6bcb`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `LOWERED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** "Capital investment ... for the full-year 2025 is now expected to be approximately $2.4 billion" is compared only with actual prior-year spend ("Capital investment for the full-year 2024 was $2.6 billion"), not with a previously issued 2025 target. Section 3's LOWERED requires a forward target "decreased versus a prior figure", and a prior-year actual is not that figure. The owner ruling on the quantified-outlook gap covers this row.
**Rater's reason (its own words, written before it saw any stored label):** Guidance: 'Capital investment ... for the full-year 2025 is now expected to be approximately $2.4 billion' is a quantified forward figure but is compared only to the 2024 actual of $2.6 billion, with no prior-guidance figure raised, lowered, or reaffirmed, so NONE.
<details><summary>chunk text (2234 chars)</summary>

```
(2) (228 ) (167 ) $ 17,035 $ 2,348 $ 17,846 $ 2,778 (1) Excludes amounts which are included in the segments’ results. (2) See section entitled “Charges & Credits” for details. Supplementary Information Frequently Asked Questions 1) What is the capital investment guidance for the full-year 2025?

Capital investment (consisting of capex, exploration data costs and APS investments) for the full-year 2025 is now expected to be approximately $2.4 billion, reflecting the impact of the ChampionX acquisition. Capital investment for the full-year 2024 was $2.6 billion. 2)

What were cash flow from operations and free cash flow for the second quarter of 2025? Cash flow from operations for the second quarter of 2025 was $1.14 billion and free cash flow was $622 million. 3) What was included in “Interest & other income” for the second quarter of 2025?

“Interest & other income” for the second quarter of 2025 was $252 million. This consisted of the following: (Stated in millions) Gain on sale of Palliser APS project $ 149 Interest income 30 Earnings of equity method investments 73 $

252 4) How did interest income and interest expense change during the second quarter of 2025? Interest income of $30 million for the second quarter of 2025 decreased $4 million sequentially. Interest expense of $142 million decreased $5 million sequentially.

5) What is the difference between SLB’s consolidated income before taxes and pretax segment operating income? The difference consists of corporate items, charges and credits, and interest income and interest expense not allocated to the segments, as well as stock-based compensation expense, amortization expense associated with certain intangible assets, certain centrally managed initiatives, and other nonoperating items.

6) What was the effective tax rate (ETR) for the second quarter of 2025? The ETR for the second quarter of 2025, calculated in accordance with GAAP, was 18.4% as compared to 22.0% for the first quarter of 2025. Excluding

charges and credits, the ETR for the second quarter of 2025 was 19.3% as compared to 19.4% for the first quarter of 2025. 7) How many shares of common stock were outstanding as of June 30, 2025, and how did this change from the end of the
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A18. `E2CHK-0d980c1e7832cb26`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `RAISED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** "Vertex today provided full year 2026 financial guidance" with "total revenue guidance of $12.95 billion to $13.1 billion" is an initial figure; no prior figure and no reaffirmation appears anywhere in the passage. Section 3's RAISED requires an increase "versus a prior figure", so RAISED cannot stand on this text. The owner ruling on the new-guidance gap under this slug governs the outcome here.
**Rater's reason (its own words, written before it saw any stored label):** Guidance: 'Vertex today provided full year 2026 financial guidance' issues quantified targets but reaffirms, raises, lowers, or withdraws nothing, so NONE; the tariff flag is REALIZED because 'currently known tariff rates and regulations' asserts the trade measures exist, with only the cost impact projected, and I left margin/cost pressure off because that impact is called 'immaterial'.
<details><summary>chunk text (2729 chars)</summary>

```
Full Year 2026 Financial Guidance Vertex today provided full year 2026 financial guidance. Vertex’s total revenue guidance of $12.95 billion to $13.1

billion includes expectations for continued growth in CF, including the ongoing U.S. rollout and ex-U.S. launches of ALYFTREK; as well as $500 million or more in revenue from non-CF products, including increased patient infusions of CASGEVY through Vertex’s global ATC network and growth in prescriptions and revenue from the second year of the launch of JOURNAVX. Vertex’s guidance for both combined GAAP and non-GAAP R&D, AIPR&D and SG&A expenses includes expectations for continued investment in multiple mid- and late-stage clinical development programs and commercial and manufacturing capabilities, and approxi

mately $100 million of currently anticipated AIPR&D expenses. This guidance also includes an immaterial cost impact from tariffs in 2026 based on currently known tariff rates and regulations. Vertex’s financial guidance is summarized below: FY 2026 Total revenue $12.95 to $13.1 billion

Non-CF product revenue $0.5 billion or greater Combined GAAP R&D, AIPR&D and SG&A expenses * $6.3 to $6.45 billion Combined non-GAAP R&D, AIPR&D and SG&A expenses * $5.65 to $5.75 billion Non-GAAP effective tax rate 19.5% to 20.5% *The difference between the combined GAAP R&D, AIPR&D and SG&A expenses and the combined non-GAAP R&D, AIPR&D and SG&A expenses guidance relates primarily to $650 million to $700 million of stock-based compensation expense.

**Combined GAAP and non-GAAP R&D, AIPR&D and SG&A expenses guidance includes approximately $100 million of AIPR&D expenses. Key Business Highlights Marketed Products Cystic Fibrosis (CF) Portfolio

Vertex has worked for more than 20 years to discover and develop medicines to treat the underlying cause of CF. Vertex CFTR modulators can treat nearly 95 percent of all people living with CF in core markets and are approved for patients as young as one month old. ALYFTREK, the newest marketed CFTR modulator, is approved in the U.S., the United Kingdom (U.K.), the European Union (EU), Canada, New Zealand, Switzerland, Australia, and Israel for the treatment of patients 6 years and older. Vertex

3 anticipates that the number of CF patients taking its medicines will continue to grow through new approvals and reimbursement agreements, treatment of younger patients, increased survival, and expansion into additional geographies. Recent progress includes: • ALYFTREK is reimbursed for eligible patients in the U.S., England, Ireland, Germany, Denmark, Northern Ireland, Norway, Wales, Italy, Australia, New Zealand, and Luxembourg. Vertex is working to secure access for eligible patients in additional countries.
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A19. `E2CHK-179659419a317bb8`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `RAISED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** The passage issues figures — "Lilly expects 2022 revenue to be between $27.8 billion and $28.3 billion", "now expects 2021 revenue to be between $28.0 billion and $28.3 billion" — but never states a prior figure or a direction; "updated 2021 guidance" says only that a revision occurred. Section 3's RAISED requires an increase "versus a prior figure", which the text does not supply, and calling it RAISED would be inference rather than reading. This turns on the same new-guidance gap the owner must close under this slug.
**Rater's reason (its own words, written before it saw any stored label):** Guidance: the passage issues quantified 2022 targets and says the company 'now expects 2021 revenue to be between $28.0 billion and $28.3 billion' but never states any figure was increased, decreased, or reaffirmed versus a prior figure, so no raised/lowered/maintained/withdrawn figure exists and NONE is the residual call.
<details><summary>chunk text (2579 chars)</summary>

```
Exhibit 99.1 Dec. 15, 2021 For Release: Immediately Refer to: Molly McCully; mccully_molly@lilly.com ; 317-478-5423 (Media) Kevin Hern; hern_kevin_r@lilly.com ; 317-277-1838 (Investors) Lilly Highlights Innovation-based Growth Strategy and Pipeline Developments; Announces 2022 Financial Guidance at Investment Community Meeting • In today’s presentations, Lilly will highlight newer medicines and upcoming launches expected to drive

growth through the decade – showcasing how the company impacts millions of people and brings to life its purpose of creating medicines that make life better. • Lilly also will reinforce its commitment to innovation and investment in science to create the next wave of

new medicines for patients, share new information across its four therapeutic areas – including pipeline and regulatory updates and new data readouts for early-phase molecules – and provide visibility to future investments. • The company announces initiation of rolling submission to FDA for pirtobrutinib in mantle cell lymphoma,

reveals new phase 3 trials planned for tirzepatide in obesity outcomes, sleep apnea and kidney disease, and releases new biomarker data supporting donanemab efficacy. • Lilly expects 2022 revenue to be between $27.8 billion and $28.3 billion, with key growth products driving

two-thirds of core business revenue, excluding COVID-19 therapies; expects operating margin to be approximately 30 percent on a reported basis and approximately 32 percent on a non-GAAP basis, and expects earnings per share (EPS) to be in the range of $8.00 to $8.15 on

a reported basis and $8.50 to $8.65 on a non-GAAP basis. • The company now expects 2021 revenue to be between $28.0 billion and $28.3 billion and EPS to be in the range of $6.18 to $6.23 on a reported basis and $8.15 to $8.20 on a

non-GAAP basis. INDIANAPOLIS, Dec. 15, 2021 – Eli Lilly and Company (NYSE: LLY) is providing extensive updates across its research and development (R&D) programs to highlight the company’s strong pipeline and potential for future growth. At an investment community meeting today, the company is sharing key information across its four therapeutic areas – including pipeline updates and future

R&D investments – along with 2022 financial guidance and updated 2021 guidance. The company is on track to meet its goal of launching 20 new medicines over the 10-year period from 2014 to 2023. Over the last eight years, Lilly has delivered 16 new medicines and plans to launch five more medicines over the next two years, if approved, including tirzepatide, donanemab,
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A20. `E2CHK-3f14cf282cf504e8`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `MAINTAINED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** The chunk restates a full-year outlook ("Revenue growth of 6% to 7%", "Adjusted diluted EPS growth of 8% to 9%") with no revision or reaffirmation language anywhere — no "reiterates", no "unchanged", no prior figures. Section 3's MAINTAINED requires that the passage "explicitly reaffirms previously-issued guidance", which this does not do. The owner must decide whether a mid-year outlook restated without any comparison counts as MAINTAINED or NONE.
**Rater's reason (its own words, written before it saw any stored label):** Guidance: the 'Fiscal 2025 Outlook' bullets give quantified targets ('Revenue growth of 6% to 7%') but nothing states they were raised, lowered, or reaffirmed against a prior figure; 'PEO Services margin down 60 to 80 basis points' names no cost cause, so no margin-pressure flag.
<details><summary>chunk text (2525 chars)</summary>

```
Third Quarter Segment Results Employer Services – Employer Services offers a comprehensive range of global HCM and Human Resources Outsourcing solutions. Compared to last year's third quarter: • Employer Services revenues increased 5% on a reported basis and 5% on an organic constant currency basis

• U.S. pays per control increased 1% • Employer Services segment margin increased 20 basis points PEO Services – PEO Services provides comprehensive employment administration outsourcing solutions. Compared to last year's third quarter: • PEO Services revenues increased 7% •

PEO Services revenues excluding zero-margin benefits pass-throughs increased 8% • Average worksite employees paid by PEO Services increased 2% to about 748,000 • PEO Services segment margin was flat Included within the results of our segments above: Interest on Funds Held for Clients

• Interest on funds held for clients increased 11% to $355 million • Average client funds balances increased 7% to $44.5 billion • The average interest yield on client funds increased 10 basis points to 3.2% 2 Fiscal 2025 Outlook

Consolidated Fiscal 2025 Outlook • Revenue growth of 6% to 7% • Adjusted EBIT margin expansion of 40 to 50 basis points • Adjusted effective tax rate of about 23% • Diluted EPS growth of 9% to 10% • Adjusted diluted EPS growth of 8% to 9%

Employer Services Segment Fiscal 2025 Outlook • Employer Services revenue growth of 6% to 7% • Employer Services margin up 50 to 60 basis points • Employer Services new business bookings growth of 4% to 7% • Employer Services client revenue retention decrease of 20 basis points to flat

• Increase in U.S. pays per control of about 1% PEO Services Segment Fiscal 2025 Outlook • PEO Services revenue growth of 6% to 7% • PEO Services revenue, excluding zero-margin benefits pass-throughs, growth of 5% to 6% • PEO Services margin down 60 to 80 basis points

• PEO Services average worksite employee count growth of 2% to 3% Client Funds Extended Investment Strategy Fiscal 2025 Outlook

The interest assumptions in our outlook are based on Fed Funds futures contracts and various forward yield curves as of April 29, 2025. The Fed Funds futures contracts are used in the client short and corporate cash interest income outlook. A combination of various forward yield curves that reflect our investment mix, resulting in a blended rate of 4.1%, was used to forecast new purchase rates across the client and corporate extended and client long portfolios over the remainder of the fiscal year.
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A21. `E2CHK-9ed330a5a63136c9`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `RAISED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** "2020 adjusted earnings per share outlook ≥ $4.33" is a specific forward figure, but the passage never says it was increased versus any prior figure. Section 3's RAISED requires a target "increased versus a prior figure"; with no prior figure and no reaffirmation, the only available value is NONE. The owner must close a real rubric gap here: section 3's preamble names passages that "issue new guidance" as a case, but the label set offers no value for it — this one ruling decides six guidance rows in this batch.
**Rater's reason (its own words, written before it saw any stored label):** Guidance is the least sure field: '2020 adjusted earnings per share outlook ≥ $4.33' is a quantified forward figure but is neither raised, reaffirmed, lowered nor withdrawn against a prior figure, so the rubric's residual category applies; 'a non-cash impairment charge of $48 million primarily related to an international core processing platform' is an explicit realized write-down.
<details><summary>chunk text (2517 chars)</summary>

```
(12 ) Tax impact of gain on sale of businesses 7 3 Discrete tax items 9 (5 ) 2019 adjusted net income 2,775 Impact of divestitures 8 (46 ) Taxes on Impact of divestitures 7 10 2019 adjusted net income, as adjusted for divestitures

$ 2,739 Weighted average common shares outstanding - diluted 522.6 Issuance of shares for combination 167.0 Dilutive impact of exchanged equity awards 4.5 Combined weighted average common shares outstanding - diluted 10 694.1 2019 GAAP earnings per share 10 $

1.71 Combined earnings per share 10 $ 1.72 Combined adjustments - net of income taxes: Merger and integration costs 2 0.52 Severance and restructuring costs 3 0.17 Amortization of acquisition-related intangible assets 4 1.36 Debt financing activities 5 0.32 Non wholly-owned entity activities

6 (0.06 ) Gain on sale of businesses 8 (0.01 ) Discrete tax items 9 (0.01 ) 2019 adjusted earnings per share 4.00 Impact of divestitures 8 (0.05 ) 2019 adjusted earnings per share, as adjusted for divestitures $ 3.95

2020 adjusted earnings per share outlook ≥ $4.33 2020 adjusted earnings per share growth outlook ≥ 10% In millions, except per share amounts, unaudited. Earnings per share is calculated using actual, unrounded amounts. See pages 3-5 for disclosures related to the use of non-GAAP financial measures.

19 News Release Fiserv, Inc. Full Year Forward-Looking Non-GAAP Financial Measures (cont.) 1 Represents the financial results of First Data prior to the date of acquisition. For the year ended December 31, 2019, this includes the results of First Data from January 1, 2019 through July 28, 2019.

Represents acquisition and related integration costs incurred as a result of the company's various acquisitions. Merger and integration costs include $408 million, related to the acquisition of First Data and primarily consist of legal and other professional service fees and incremental share-based compensation including the fair value of stock awards assumed by Fiserv in connection with the First Data acquisition. Legal and other professional service fees were $199 million and incremental share-based compensation including the fair value of assumed stock awards was $108 million.

Represents severance and other costs associated with the achievement of ongoing expense management initiatives, including real estate and data center consolidation activities. Severance and restructuring costs includes a non-cash impairment charge of $48 million primarily related to an international core processing platform.
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A22. `E2CHK-af98d865cf1fcf87`  ·  field `guidance_direction`  ·  arm P
**Stored (student):** `RAISED`  
**Rater (blind):** `NONE`  
**Adjudicator (disagree, medium confidence):** `NONE`
**Adjudicator brief:** The outlook is new quarterly guidance — "Applied expects net sales to be in the range of $4.00 billion to $4.20 billion" — and the only comparison offered is to prior-year actuals ("the midpoint of the range would be an increase of approximately 25 percent, year over year"), not to a previously issued target. Section 3's RAISED requires an increase versus a prior guidance figure. The owner ruling on the new-guidance gap under this slug governs this row.
**Rater's reason (its own words, written before it saw any stored label):** Guidance: "Applied expects net sales to be in the range of $4.00 billion to $4.20 billion" is newly issued with no reaffirmed, raised or lowered prior figure, so the tie-breaker gives NONE; sentiment rests on the passage describing improvement throughout ("Net sales ... 20% 34%", "Net income ... 61% 100%").
<details><summary>chunk text (2004 chars)</summary>

```
Applied Materials, Inc. Page 2 of 12 Results Summary Change Q4 FY2017 Q4 FY2016 FY2017 FY2016 Q4 FY2017 vs. Q4 FY2016 FY2017 vs. FY2016 (In millions, except per share amounts and percentages) Net sales $ 3,969 $ 3,297 $ 14,537

$ 10,825 20% 34% Gross margin 45.0 % 42.4 % 44.9 % 41.7 % 2.6 points 3.2 points Operating margin 27.7 % 23.6 % 26.6 % 19.9 % 4.1 points 6.7 points Net income $ 982 $ 610 $ 3,434

$ 1,721 61% 100% Diluted earnings per share $ 0.91 $ 0.56 $ 3.17 $ 1.54 63% 106% Non-GAAP Adjusted Results Non-GAAP adjusted gross margin 46.2 % 43.7 % 46.1 % 43.2 % 2.5 points 2.9 points Non-GAAP adjusted operating margin

28.7 % 25.2 % 27.9 % 21.7 % 3.5 points 6.2 points Non-GAAP adjusted net income $ 1,005 $ 722 $ 3,525 $ 1,950 39% 81% Non-GAAP adjusted diluted EPS $ 0.93 $ 0.66 $ 3.25 $ 1.75 41% 86%

A reconciliation of the GAAP and non-GAAP adjusted results is provided in the financial tables included in this release. See also “Use of Non-GAAP Adjusted Financial Measures” section. Business Outlook

In the first quarter of fiscal 2018, Applied expects net sales to be in the range of $4.00 billion to $4.20 billion; the midpoint of the range would be an increase of approximately 25 percent, year over year. Non-GAAP adjusted diluted EPS is expected to be in the range of $0.94 to $1.02; the midpoint of the range would be an increase of approximately 46 percent, year over year.

Fourth Quarter and Fiscal Year Reportable Segment Information Semiconductor Systems Q4 FY2017 Q4 FY2016 FY2017 FY2016 (In millions, except percentages) Net sales $ 2,431 $ 2,127 $ 9,517 $ 6,873 Foundry 36 % 52 % 41 % 40 % DRAM

12 % 10 % 16 % 16 % Flash 38 % 23 % 34 % 31 % Logic and other 14 % 15 % 9 % 13 % Operating income 801 667 3,173 1,807 Operating margin 32.9 % 31.4 %

33.3 % 26.3 % Non-GAAP Adjusted Results Non-GAAP adjusted operating income $ 847 $ 713 $ 3,357 $ 1,991 Non-GAAP adjusted operating margin 34.8 % 33.5 % 35.3 % 29.0 % Applied Materials, Inc. Page 3 of 12 Applied Global Services
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

### pattern `directional-percent-table-no-evaluative-words` — 4 row(s)

#### A23. `E2CHK-0ce0f271a0db498d`  ·  field `sentiment`  ·  arm P
**Stored (student):** `NEUTRAL`  
**Rater (blind):** `POSITIVE`  
**Adjudicator (agree, medium confidence):** `NEUTRAL`
**Adjudicator brief:** The passage is a segment sales table with change columns ("Net Sales $ 2,105 $ 1,888 11 %") plus flat prose ("net income for the third quarter of 2016 was $228 million"); the only directional prose is a footnote, "Urology and Pelvic Health grew 13% on an organic basis". Section 2 says magnitude alone isn't sentiment and "the text has to characterize it" — there are no evaluative words such as "strong" or "record" — so NEUTRAL stands. The owner must weigh whether uniformly positive percent-change columns are themselves "growth" under the POSITIVE definition, since the same question decides several chunks carrying this slug.
**Rater's reason (its own words, written before it saw any stored label):** Guidance is the least sure field: the passage reaches 'The company now estimates revenue for the full year 2016 to be in a range of' and stops before any figure, so there is no specific quantified target to call raised or lowered; 'These results included an intangible asset impairment charge ... litigation-related net charges ... of $140 million (after-tax)' are realized charges actually recorded.
<details><summary>chunk text (2154 chars)</summary>

```
20 countries in our definition of Emerging Markets. ** The LOTUS Edge™ Valve System and Ranger™ Drug-Coated Balloon Catheter are not available for use or sale in the U.S. *** In the U.S., the Eluvia™ Drug-Eluting Vascular Stent System is an investigational device, limited by federal law to investigational use only.

Net sales for the third quarter : Change Three Months Ended September 30, As Reported Basis Less: Impact of Foreign Currency Constant Currency Basis in millions 2016 2015 Interventional Cardiology $ 568 $ 500 14 % $ (1 ) 1

% 13 % Peripheral Interventions 257 227 12 % 3 1 % 11 % Cardiovascular 825 727 13 % 2 1 % 12 % Cardiac Rhythm Management 467 451 4 % 1 1 % 3 % Electrophysiology 60 57 5

% 0 0 % 5 % Rhythm Management 527 508 4 % 1 1 % 3 % Endoscopy 367 331 11 % 5 2 % 9 % Urology and Pelvic Health 248 198 26 % (3 ) 0 % 26

% * Neuromodulation 138 124 11 % (1 ) (1 ) % 12 % MedSurg 753 653 15 % 1 1 % 14 % Net Sales $ 2,105 $ 1,888 11 % $ 4 1 % 10 % *Urology and Pelvic Health grew 13% on an organic basis.

On a consolidated GAAP basis, net income for the third quarter of 2016 was $228 million , or $0.17 per share. These results included an intangible asset impairment charge, acquisition-related net credits, restructuring and restructuring-related net charges, litigation-related net charges and amortization expense

, of $140 million (after-tax) or $0.10 per share. Adjusted net income for the third quarter of 2016 , excluding these net charges, was $368 million , or $0.27 per share. On a consolidated GAAP basis, net loss for the

third quarter of 2015 was $198 million , or $(0.15) per share. These results included intangible asset impairment charges, acquisition-related net charges, restructuring and restructuring-related net charges, litigation-related net charges, pension termination charges and amortization expense , of $524 million

(after-tax) or $0.39 per share. Adjusted net income for the third quarter of 2015 , excluding these net charges, was $326 million , or $0.24 per share. Guidance for Full Year and Fourth Quarter 2016 The company now estimates revenue for the full year 2016 to be in a range of
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A24. `E2CHK-19cbfdfda539b797`  ·  field `sentiment`  ·  arm G-N
> **This ruling enters NO reported estimate.** The sentiment primary is P-arm only, every sentiment secondary is computed on P, and S-NOISE uses rater A vs rater B without adjudications. This row is in an off-primary arm and is included solely so the escalated set is complete — rule it or skip it, no number moves either way.
**Stored (student):** `POSITIVE`  
**Rater (blind):** `NEUTRAL`  
**Adjudicator (disagree, medium confidence):** `NEUTRAL`
**Adjudicator brief:** The chunk is volume and segment-reconciliation tables ("Total natural gas processed 6,132 5,636 9 %", "Income from operations $ 265 $ 50") with no prose beyond table footnotes. Section 2 requires that the text characterize the numbers before sentiment attaches. The owner must weigh the shared percent-change-table question flagged under this slug.
**Rater's reason (its own words, written before it saw any stored label):** Red flag: the reconciliation line 'Impairment expense — 129' asserts a $129 million impairment was recorded in the comparative period, a realized charge; the passage otherwise reports volumes and income without characterization, hence NEUTRAL.
<details><summary>chunk text (2118 chars)</summary>

```
Marcellus operations 3,532 3,152 12 % Utica operations 1,068 1,120 (5 )% Southwest operations 1,267 1,110 14 % Southern Appalachian operations 265 254 4 % Total natural gas processed 6,132 5,636 9 % C2 + NGLs fractionated (mbpd) Marcellus operations

291 237 23 % Utica operations 43 48 (10 )% Southwest operations 19 19 — % Southern Appalachian operations 14 17 (18 )% Total C2 + NGLs fractionated 367 321 14 % (a) Pipeline throughput and tariff rates as of March 31, 2016, have been recast to reflect the acquisition of HST.

(b) MPLXT was not established as a business until April 1, 2016, therefore there is no terminal throughput to disclose for the three months ended March 31, 2016. 12 Reconciliation of Segment Operating Income Attributable to MPLX LP to Income From Operations (unaudited)

Three Months Ended March 31 (In millions) 2017 2016 L&S segment operating income attributable to MPLX LP $ 156 $ 88 G&P segment operating income attributable to MPLX LP (a) 309 257 Segment portion attributable to equity affiliates (40 )

(42 ) Segment portion attributable to Predecessor (b) 53 62 Income from equity method investments 5 5 Other income - related parties 11 7 Unrealized derivative gains (losses) (c) 16 (9 ) Depreciation and amortization (187 ) (136 ) Impairment expense

— (129 ) General and administrative expenses (58 ) (53 ) Income from operations $ 265 $ 50 (a) All Partnership-operated, non-wholly owned subsidiaries are treated as if they are consolidated. (b) The operating income of the Predecessor is excluded from segment operating income attributable to MPLX LP prior to the acquisition dates.

13 Reconciliation of Adjusted EBITDA attributable to MPLX LP and DCF attributable to GP and LP unitholders from Net Income (Loss) (unaudited) Three Months Ended March 31 (In millions) 2017 2016 Net income (loss) $ 187 $ (14 ) Depreciation and amortization

187 136 Benefit for income taxes — (4 ) Amortization of deferred financing costs 12 11 Non-cash equity-based compensation 3 2 Impairment expense — 129 Net interest and other financial costs 66 57 Income from equity method investments (5 )
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A25. `E2CHK-c139014881563565`  ·  field `sentiment`  ·  arm P
**Stored (student):** `NEUTRAL`  
**Rater (blind):** `POSITIVE`  
**Adjudicator (agree, medium confidence):** `NEUTRAL`
**Adjudicator brief:** The chunk is a procedural capital-return announcement ("declared a regular quarterly dividend of $1.10 per share", "authorized an additional $5.0 billion of share repurchases") followed by a segment table with change columns. Section 2 names procedural narrative as NEUTRAL, and the improving figures carry no characterizing words. The owner must weigh the same percent-change-table question flagged under this slug elsewhere in the batch.
**Rater's reason (its own words, written before it saw any stored label):** Sentiment POSITIVE on the segment results the passage reports — underwriting gain, net investment income and segment income all up and 'Combined ratio 84.4% ... (0.8) pts' improved; guidance NONE because a declared 'regular quarterly dividend of $1.10 per share' and a repurchase authorization are corporate actions, not a raised, reaffirmed or lowered forward financial target.
<details><summary>chunk text (2124 chars)</summary>

```
The Board of Directors declared a regular quarterly dividend of $1.10 per share. The dividend is payable March 31, 2026, to shareholders of record at the close of business on March 10, 2026. The Board of Directors also authorized an additional $5.0 billion of share repurchases. This amount is in addition to the $2.015 billion that remained from previous authorizations as of December 31, 2025. This authorization does not have a stated expiration date. The timing and actual number of shares to be repurchased will depend on a variety of factors, including the factors described below in the Forward-Looking Statements section.

4 Business Insurance Segment Financial Results Three Months Ended December 31, Twelve Months Ended December 31, ($ in millions and pre-tax, unless noted otherwise) 2025 2024 Change 2025 2024 Change Underwriting gain: $ 877 $ 808 $ 69 $ 1,810

$ 1,554 $ 256 Underwriting gain includes : Net favorable prior year reserve development 205 147 58 233 90 143 Catastrophes, net of reinsurance (57) (94) 37 (1,073) (1,032) (41) Net investment income 737 677 60 2,782 2,560 222 Other income (expense)

2 (7) 9 (6) (27) 21 Segment income before income taxes 1,616 1,478 138 4,586 4,087 499 Income tax expense 324 290 34 891 781 110 Segment income $ 1,292 $ 1,188 $ 104 $ 3,695 $ 3,306 $ 389

Combined ratio 84.4 % 85.2 % (0.8) pts 91.7 % 92.5 % (0.8) pts Impact on combined ratio Net favorable prior year reserve development (3.6) pts (2.7) pts (0.9) pts (1.1) pts (0.4) pts (0.7) pts Catastrophes, net of reinsurance

1.0 pts 1.7 pts (0.7) pts 4.8 pts 4.8 pts — pts Underlying combined ratio 87.0 % 86.2 % 0.8 pts 88.0 % 88.1 % (0.1) pts Net written premiums by market Domestic Select Accounts $ 930 $ 893 4

% $ 3,830 $ 3,727 3 % Middle Market 3,109 3,011 3 12,541 12,023 4 National Accounts 348 356 (2) 1,262 1,259 — National Property and Other 666 684 (3) 3,112 3,134 (1) Total Domestic 5,053 4,944 2 20,745 20,143

3 International 461 482 (4) 1,934 1,935 — Total $ 5,514 $ 5,426 2 % $ 22,679 $ 22,078 3 % Fourth Quarter 2025 Results (All comparisons vs. fourth quarter 2024, unless noted otherwise)
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A26. `E2CHK-dfb41597a10fbecc`  ·  field `sentiment`  ·  arm P
**Stored (student):** `POSITIVE`  
**Rater (blind):** `NEUTRAL`  
**Adjudicator (disagree, medium confidence):** `NEUTRAL`
**Adjudicator brief:** The chunk is a GAAP-to-non-GAAP table with percent-change columns ("TOTAL REVENUES $ 12,453 ... 9% 9%", "NET INCOME $ 2,420 ... 56%") followed by a constant-currency methodology paragraph. No sentence characterizes the results as strong, improved, or anything else. Section 2's rule that magnitude of a number alone isn't sentiment points to NEUTRAL; the owner must resolve the shared percent-change-table question, since POSITIVE's "growth" wording could be read to cover uniformly positive change columns.
**Rater's reason (its own words, written before it saw any stored label):** A GAAP-to-non-GAAP reconciliation with percentage columns and no characterizing language, so the growth figures alone do not make it positive; 'Restructuring 138' is an unexplained adjustment line with no asserted asset-value reduction.
<details><summary>chunk text (1933 chars)</summary>

```
* Not meaningful 1 ORACLE CORPORATION Q1 FISCAL 2024 FINANCIAL RESULTS RECONCILIATION OF SELECTED GAAP MEASURES TO NON-GAAP MEASURES (1) ($ in millions, except per share data) Three Months Ended August 31, % Increase (Decrease) in US $ % Increase (Decrease) in

Constant Currency (2) 2023 GAAP Adj. 2023 Non-GAAP 2022 GAAP Adj. 2022 Non-GAAP GAAP Non-GAAP GAAP Non-GAAP TOTAL REVENUES $ 12,453 $ — $ 12,453 $ 11,445 $ — $ 11,445 9% 9% 8% 8% TOTAL OPERATING EXPENSES $ 9,157

$ (1,761 ) $ 7,396 $ 8,822 $ (1,854 ) $ 6,968 4% 6% 3% 5% Stock-based compensation (3) 849 (849 ) — 750 (750 ) — 13% * 13% * Amortization of intangible assets (4) 763 (763 ) —

919 (919 ) — (17%) * (17%) * Acquisition related and other 11 (11 ) — 41 (41 ) — (72%) * (72%) * Restructuring 138 (138 ) — 144 (144 ) — (4%) * (1%) * OPERATING INCOME $

3,296 $ 1,761 $ 5,057 $ 2,623 $ 1,854 $ 4,477 26% 13% 23% 12% OPERATING MARGIN % 26% 41% 23% 39% 355 bp. 150 bp. 327 bp. 140 bp. INCOME TAX EFFECTS (5) $ 45 $ (823 ) $

(778 ) $ (108 ) $ (574 ) $ (682 ) * 14% * 13% NET INCOME $ 2,420 $ 938 $ 3,358 $ 1,548 $ 1,280 $ 2,828 56% 19% 52% 17% DILUTED EARNINGS PER SHARE $ 0.86 $

1.19 $ 0.56 $ 1.03 52% 16% 48% 14% DILUTED WEIGHTED AVERAGE COMMON SHARES OUTSTANDING 2,823 — 2,823 2,747 — 2,747 3% 3% 3% 3% (1)

We compare the percent change in the results from one period to another period using constant currency disclosure. We present constant currency information to provide a framework for assessing how our underlying businesses performed excluding the effect of foreign currency rate fluctuations. To present this information, current and comparative prior period results for entities reporting in currencies other than United States dollars are converted into United States dollars at the exchange rates in effect on May 31, 2023, which was the last day of our prior fiscal year, rather than the actual exchange rates in effect during the respective periods.
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

### pattern `explicit-reaffirmation-controls-mixed-revisions` — 3 row(s)

#### A27. `E2CHK-1e2619c28f2f551f`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `LOWERED`  
**Rater (blind):** `MAINTAINED`  
**Adjudicator (disagree, medium confidence):** `MAINTAINED`
**Adjudicator brief:** The bottom-line target is explicitly held: "Guidance range for Adjusted diluted EPS was reaffirmed at $2.82 to $2.92," and revenue guidance carries no 'previously' note. The revisions that did occur run both ways and are mostly cost lines moving favorably ("Adjusted cost of sales... was lowered by 400 basis points... to reflect the favorable impact of product mix"; "Adjusted R&D expenses was increased by $500 million"). Rubric section 3's mixed rule says to prefer the label matching the passage's overall framing, and the framing here is an EPS reaffirmation with line-item reallocation, not a guidance cut. The owner must weigh this against the genuinely reduced New Pfizer operating cash flow range ($10.0-11.0B, "previously $11.0 to $12.0 billion").
**Rater's reason (its own words, written before it saw any stored label):** Sentiment NEUTRAL because 'favorable impact of product mix and other efficiencies' and 'incremental cost-savings opportunities' are offset by 'a $0.04 unfavorable impact from changes in foreign exchange rates' and cash-flow guidance cut to '$10.0 to $11.0 billion (previously $11.0 to $12.0 billion)'; MAINTAINED because the bottom-line target is explicitly 'reaffirmed at $2.82 to $2.92' while the revised lines are cost/expense inputs.
<details><summary>chunk text (2595 chars)</summary>

```
▪ Guidance range for Adjusted cost of sales (3) as a percentage of revenues was lowered by 400 basis points to a range of 19.5% to 20.5% , primarily to reflect the favorable impact of product mix and other efficiencies.

▪ Guidance range for Adjusted SI&A expenses (3) was lowered by $500 million to a range of $11.5 to $12.5 billion , primarily to reflect incremental cost-savings opportunities, primarily reductions in indirect SI&A spend associated with corporate enabling functions, as well as actual and anticipated COVID-19-related spending reductions.

▪ Guidance range for Adjusted R&D expenses (3) was increased by $500 million to a range of $8.6 to $9.0 billion

, solely to reflect incremental investments Pfizer anticipates making in 2020 to combat the COVID-19 pandemic, including development of potential anti-viral treatments and a potential vaccine, as well as the evaluation of existing Pfizer medicines, which are the subject of novel research projects for investigation in COVID-19 patients.

▪ Guidance range for Adjusted diluted EPS (3) was reaffirmed at $2.82 to $2.92 , absorbing a $0.04 unfavorable impact from changes in foreign exchange rates since mid-January 2020. Revenues $48.5 to $50.5 billion Adjusted Cost of Sales (3) as a Percentage of Revenues

19.5% to 20.5% (previously 19.9% to 20.9%) Adjusted SI&A Expenses (3) $11.5 to $12.5 billion (previously $12.0 to $13.0 billion) Adjusted R&D Expenses (3) $8.6 to $9.0 billion (previously $8.1 to $8.5 billion) Adjusted Other (Income)/Deductions (3) Approximately $800 million of income

Effective Tax Rate on Adjusted Income (3) Approximately 15.0% Adjusted Diluted EPS (3) $2.82 to $2.92 Financial guidance for Adjusted diluted EPS (3) continues to assume no share repurchases in 2020. - 5 - 2020 Financial Guidance for New Pfizer

(8) Pfizer’s updated 2020 financial guidance for New Pfizer (8) is presented below. New Pfizer (8) revenue guidance absorbs a $500 million unfavorable impact from changes in foreign exchange rates since mid-January 2020. New Pfizer (8) financial guidance reflects a full-year 2020 pro forma view of the company assuming the pending Upjohn combination with Mylan was completed at the beginning of 2020.

Revenues $40.7 to $42.3 billion Adjusted IBT Margin (9) Approximately 37.0% Adjusted Diluted EPS (3) $2.25 to $2.35 Operating Cash Flow $10.0 to $11.0 billion (previously $11.0 to $12.0 billion) Financial guidance for New Pfizer (8) operating cash flow now includes a $1.25 billion voluntary contribution to the U.S. qualified pension plans, planned for the second half of 2020.
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A28. `E2CHK-467320dd59f87847`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `RAISED`  
**Rater (blind):** `MAINTAINED`  
**Adjudicator (disagree, medium confidence):** `MAINTAINED`
**Adjudicator brief:** The headline says guidance is "UPDATED FOR INCLUSION OF BARD" and gives a new range ($10.85-$11.00), but nowhere states that a target was increased versus a prior figure, which rubric section 3 requires for RAISED. The one explicit direction word in the passage is reaffirmation: "The Company reaffirms that the acquisition of C.R. Bard is expected to be accretive to adjusted dilutive earnings per share on a high-single digit basis in fiscal year 2019," which matches MAINTAINED ("explicitly reaffirms previously-issued guidance without changing it"). The owner must weigh whether an explicit reaffirmation of a secondary quantified target should control when the headline metric is restated without a stated direction.
**Rater's reason (its own words, written before it saw any stored label):** Guidance MAINTAINED on the explicit 'The Company reaffirms that the acquisition of C.R. Bard is expected to be accretive to adjusted dilutive earnings per share on a high-single digit basis in fiscal year 2019'; sentiment POSITIVE because the filer's own characterization is 'we continued to deliver solid, consistent results' despite the flatly stated '$(0.76) decreased 129.5 percent'.
<details><summary>chunk text (2321 chars)</summary>

```
Exhibit 99.1 1 Becton Drive Franklin Lakes, NJ 07417 www.bd.com Contact: Monique N. Dolecki, Investor Relations - 201-847-5378 Kristen Cardillo, Corporate Communications - 201-847-5657 BD ANNOUNCES RESULTS FOR 2018 FIRST FISCAL QUARTER; PROVIDES FISCAL 2018 GUIDANCE UPDATED FOR INCLUSION OF BARD

• As reported, revenues of $3.080 billion increased 5.4 percent, or 3.7 percent on a currency-neutral basis, which includes an estimated 110 basis point adverse impact from the previously disclosed change in the U.S. dispensing business model. • As reported, diluted earnings per share of

$(0.76) decreased 129.5 percent. • As adjusted, diluted earnings per share of $2.48 increased 6.4 percent, or 3.9 percent on a currency-neutral basis. • The Company expects full fiscal year 2018 adjusted diluted earnings per share, including the accretion from the C.R. Bard acquisition, to be between $10.85 and $11.00, which represents growth of approximately 15.0 to 16.0 percent, or approximately 12.0 percent on a currency-neutral basis.

• The Company reaffirms that the acquisition of C.R. Bard is expected to be accretive to adjusted dilutive earnings per share on a high-single digit basis in fiscal year 2019. Franklin Lakes, NJ ( February 6, 2018 ) - BD (Becton, Dickinson and Company) (NYSE: BDX), a leading global medical technology company, today reported quarterly revenues of

$3.080 billion for the first fiscal quarter ended December 31, 2017 . This represents an increase of 5.4 percent from the prior-year period, or 3.7 percent on a currency-neutral basis, and includes an estimated 110 basis point adverse impact from the previously disclosed change in the U.S. dispensing business model.

“We are proud of our performance in our final stand-alone quarter, as we continued to deliver solid, consistent results,” said Vincent A. Forlenza, Chairman and CEO. “We look forward to the future with confidence as we welcome C.R. Bard to BD. Together, through our combined capabilities and the impact we can have on our customers and their patients, we have a tremendous opportunity to advance the world of health.”

First Quarter Fiscal 2018 Operating Results As reported, diluted earnings per share for the first quarter were $(0.76) , compared with $2.58 in the prior-year period. This represents a decrease of 129.5
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A29. `E2CHK-d36b7ebe315b5249`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `LOWERED`  
**Rater (blind):** `MAINTAINED`  
**Adjudicator (disagree, medium confidence):** `MAINTAINED`
**Adjudicator brief:** The passage says it is "Narrowing fiscal 2024 adjusted EPS guidance to $3.20 to $3.35" without quoting the prior range or stating that the target was decreased, so LOWERED's requirement in rubric section 3 ("has been decreased versus a prior figure") is not met. The only explicit direction statement is a reaffirmation: "Maintaining U.S. Healthcare adjusted EBITDA to be breakeven at the midpoint of the guidance range of ($50) million to $50 million," which fits MAINTAINED. The owner must weigh whether a narrowed range with unfavorable stated reasons should count as LOWERED, and whether an explicitly maintained segment metric can carry the label when the headline metric is merely narrowed.
**Rater's reason (its own words, written before it saw any stored label):** Guidance is MAINTAINED because the only explicit reaffirmation of a quantified figure is "Maintaining U.S. Healthcare adjusted EBITDA ... range of ($50) million to $50 million", while "Narrowing fiscal 2024 adjusted EPS guidance to $3.20 to $3.35" states no prior figure and so does not establish a decrease; sentiment is NEGATIVE on "loss per share* was $6.85 compared to earnings per share of $0.81", the "$5.8 billion after-tax non-cash impairment charge" and "challenging retail environment".
<details><summary>chunk text (2711 chars)</summary>

```
Exhibit 99.1 Walgreens Boots Alliance Reports Fiscal 2024 Second Quarter Results Second quarter operational results in line with expectations, U.S. Healthcare achieved adjusted EBITDA profitability, narrowing full-year adjusted EPS guidance range Second quarter financial highlights • Second quarter loss per share* was $6.85 compared to earnings per share of $0.81 in the

year-ago quarter; Second quarter results included a $5.8 billion after-tax non-cash impairment charge related to VillageMD goodwill • Adjusted earnings per share (EPS)** increased 3.4 percent to $1.20, up 2.8 percent on a constant currency basis reflecting lower adjusted effective tax rate** and improved profitability in U.S. Healthcare

• Second quarter sales increased 6.3 percent year-over-year to $37.1 billion, up 5.7 percent on a constant currency basis Fiscal 2024 guidance 1 • Narrowing fiscal 2024 adjusted EPS** guidance to $3.20 to $3.35, reflecting challenging retail environment in the

U.S., early wind-down of sale-leaseback program, and lower earnings due to Cencora share sales, offset by execution in pharmacy services and a lower adjusted effective tax rate** • Maintaining U.S. Healthcare adjusted EBITDA** to be breakeven at the midpoint of the guidance range of ($50)

million to $50 million DEERFIELD, Ill. — March 28, 2024 — Walgreens Boots Alliance, Inc. (Nasdaq: WBA) today announced financial results for the second quarter of fiscal 2024, which ended February 29, 2024. Chief Executive Officer Tim Wentworth said: “We’re encouraged by our first quarter of U.S. Healthcare positive adjusted EBITDA and continued topline growth alongside another quarter of strong

execution in pharmacy, as we look to re-energize and evolve its impact both at Walgreens and at large. As we continue to operate in a challenging retail environment, we are taking actions to focus on customer engagement and value. We remain confident in our goal of achieving $1 billion in cost savings this year. We are continuing to strategically review

our portfolio over the next three months in an effort to ensure it drives growth and delivers value. Our team members, led by WBA’s new executive committee with a track record of operational excellence, are powering our progress as we map

growth opportunities, aim to create long-term value across our businesses and execute the hard work to simplify and strengthen WBA.” 1 The Company does not provide a reconciliation for non-GAAP estimates on a forward-looking basis where it is unable to provide a meaningful or accurate calculation or estimation of reconciling items and the information is not available without unreasonable effort and the Company is unable to address the probable
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

### pattern `safe-harbor-enumeration-not-negative-sentiment` — 2 row(s)

#### A30. `E2CHK-040942506845bb80`  ·  field `sentiment`  ·  arm P
**Stored (student):** `NEUTRAL`  
**Rater (blind):** `NEGATIVE`  
**Adjudicator (agree, medium confidence):** `NEUTRAL`
**Adjudicator brief:** After the results header the chunk is a "Notice regarding forward-looking statements" bullet list — "A loss suffered by one of our customers or distributors", "Losses or curtailments of purchases from key customers", "Impairments of our non-financial assets". These are hypothetical risk items, not statements about current results, and section 1 explains that scoring risk enumerations negative teaches "risk-factor register implies negative". The owner should confirm this treatment for safe-harbor lists appearing inside press-release chunks.
**Rater's reason (its own words, written before it saw any stored label):** Red flags: the bullets under 'Notice regarding forward-looking statements' ('Impairments of our non-financial assets', 'Losses or curtailments of purchases from key customers') are a safe-harbor enumeration that the addendum directs should ordinarily fail mining depth, so no flags; sentiment is negative because the passage's content is entirely a list of adverse contingencies.
<details><summary>chunk text (939 chars)</summary>

```
40.9 % 37.5 %

TI reports third quarter 2019 financial results and shareholder returns Page 8 # # # Notice regarding forward-looking statements

• A loss suffered by one of our customers or distributors with respect to TI-consigned inventory; • Financial difficulties of our distributors or their promotion of competing product lines to our detriment, or the unexpected loss of significant distributors; •

Losses or curtailments of purchases from key customers or the timing and amount of distributor and other customer inventory adjustments; • Our ability to maintain or improve profit margins, including our ability to utilize our manufacturing facilities at sufficient levels to cover our fixed operating costs, in an intensely competitive and cyclical industry and despite changes in the regulatory environment;

• Impairments of our non-financial assets. TI reports third quarter 2019 financial results and shareholder returns Page 9
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

#### A31. `E2CHK-53c7e256395f4d8f`  ·  field `sentiment`  ·  arm P
**Stored (student):** `NEGATIVE`  
**Rater (blind):** `NEUTRAL`  
**Adjudicator (disagree, medium confidence):** `NEUTRAL`
**Adjudicator brief:** The one substantive paragraph is technical and two-sided — the reserve increase "primarily reflected the impacts of (i) catastrophe losses ... partially offset by ... (v) net favorable prior year reserve development" — and the rest is a forward-looking-statements bullet list ("the Company's financial results could be materially and adversely affected"). Section 2 treats mechanical disclosure and hypothetical risk enumeration as NEUTRAL, and section 1 warns that scoring risk registers negative teaches the shortcut "risk-factor register implies negative". The owner must confirm that a safe-harbor bullet list sitting inside a non-risk-factors chunk does not by itself drive sentiment NEGATIVE.
**Rater's reason (its own words, written before it saw any stored label):** Sentiment NEUTRAL because the reserve walk is a balanced mechanical attribution ('catastrophe losses ... loss cost trends ... partially offset by ... net favorable prior year reserve development'); MARGIN_COST_PRESSURE is REALIZED off the asserted 'loss cost trends for the current accident year' driving the $1.88 billion increase, and LEGAL_REGULATORY_ACTION REALIZED off 'its continued exposure to asbestos and environmental claims and related litigation' (existence claim; only the harm is projected), while the parenthetical 'the impact of tariffs' is a bare noun in an enumeration and fails mining depth.
<details><summary>chunk text (2442 chars)</summary>

```
— 4 5 — 5 Claims and claim adjustment expense reserves $ 30,054 $ 35,922 $ 65,976 $ 29,302 $ 34,791 $ 64,093

The $1.88 billion increase in gross claims and claim adjustment expense reserves since December 31, 2024 primarily reflected the impacts of (i) catastrophe losses in the first three months of 2025, (ii) higher volumes of insured exposures and (iii) loss cost trends for the current accident year, partially offset by (iv) claim payments made during the first three months of 2025 and (v) net favorable prior year reserve development.

FUTURE APPLICATION OF ACCOUNTING STANDARDS See note 1 of the notes to the unaudited consolidated financial statements contained in this quarterly report and in the Company’s 2024 Annual Report for a discussion of recently issued accounting pronouncements. 53 THE TRAVELERS COMPANIES, INC. AND SUBSIDIARIES

• the cost and availability of reinsurance coverage; • catastrophe losses (including the January 2025 California wildfires) and modeling, including statements about probabilities or likelihood of exceedance; • the impact of investment (including changes in interest rates), economic (including inflation, the impact of tariffs, changes in tax laws, changes in commodity prices and fluctuations in foreign currency exchange rates) and underwriting market conditions;

• the Company’s cybersecurity policies and practices; • new product offerings; • the impact of developments in the tort environment, such as increased attorney involvement in insurance claims; and • the impact of developments in the geopolitical environment.

if actual claims exceed the Company’s claims and claim adjustment expense reserves, if changes in the estimated level of claims and claim adjustment expense reserves are necessary, or if the Company is unable to offset increases in loss costs with sufficient price increases, including as a result of, among other things, changes in the legal/tort, regulatory and economic environments in which the Company operates, including increased inflation and the impact of tariffs, the Company’s financial results could be materially and adversely affected;

• the Company’s business could be harmed because of its continued exposure to asbestos and environmental claims and related litigation; • the Company is exposed to, and may face adverse developments involving, mass tort claims such as those relating to exposure to potentially harmful products or substances; and
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

### pattern `directional-variance-narrative` — 1 row(s)

#### A32. `E2CHK-2d90e2ccfe435d5c`  ·  field `sentiment`  ·  arm G-N
> **This ruling enters NO reported estimate.** The sentiment primary is P-arm only, every sentiment secondary is computed on P, and S-NOISE uses rater A vs rater B without adjudications. This row is in an off-primary arm and is included solely so the escalated set is complete — rule it or skip it, no number moves either way.
**Stored (student):** `NEUTRAL`  
**Rater (blind):** `POSITIVE`  
**Adjudicator (disagree, medium confidence):** `POSITIVE`
**Adjudicator brief:** The narrative is a variance walk that is predominantly favorable: "Gross operating margin... increased 16 percent to $172 million," "increased $21 million," "increased $16 million," "led to a $7 million increase," against only a "$13 million decrease" and a "$3 million decrease." Rubric section 2's own NEGATIVE example ("Revenue declined... as demand softened") shows that plain directional language, without emotive adjectives, does carry sentiment, so the symmetric increase language reads as improvement. The owner must weigh whether an adjective-free MD&A variance walk that nets favorable should be POSITIVE (my call) or NEUTRAL descriptive narrative, because this pattern recurs across many chunks.
**Rater's reason (its own words, written before it saw any stored label):** Sentiment is POSITIVE on the predominance of "increased 16 percent to $172 million" and multiple segment margin increases over two smaller declines; I did not flag demand weakness for "766 MBPD compared to 840 MBPD" because the volume change is stated flatly with no demand attribution, while "higher maintenance expenses" and "higher PDH commissioning costs" explicitly reduced margin.
<details><summary>chunk text (2447 chars)</summary>

```
– Gross operating margin for the Petrochemical & Refined Products Services segment increased 16 percent to $172 million for the fourth quarter of 2017 compared to the fourth quarter of 2016. Total petrochemical and refined products transportation volumes for the fourth quarter of 2017 were 766 MBPD compared to 840 MBPD reported for the fourth quarter of 2016.

Gross operating margin for Enterprise’s butane isomerization and related operations increased $21 million for the fourth quarter of 2017 compared to the fourth quarter of 2016, primarily due to downtime and costs associated with the turnaround of two processing units in the fourth quarter of 2016. Butane isomerization volumes were 108 MBPD for the fourth quarter of 2017 compared to 94 MBPD for the same quarter of 2016.

Gross operating margin for Enterprise’s octane enhancement and high-purity isobutylene business increased $16 million for the fourth quarter of 2017 compared to the fourth quarter of 2016, primarily due to lower operating costs and higher sales volumes. Total plant production volumes were 27 MBPD for the fourth quarter of 2017 compared to 26 MBPD for the fourth quarter of 2016.

Higher transportation fees on our TE Products pipeline and related terminals led to a $7 million increase in gross operating margin for the fourth quarter of 2017 compared to the fourth quarter of 2016. Enterprise’s Houston and Beaumont products terminals and related marketing activities reported a $13 million decrease in gross operating margin for the fourth quarter of 2017 compared to the same quarter of 2016, primarily due to higher maintenance expenses as a result of Hurricane Harvey.

The partnership’s propylene fractionation business reported a $3 million decrease in gross operating margin for the fourth quarter of 2017 compared to the fourth quarter of 2016, primarily due to higher PDH commissioning costs. Propylene fractionation volumes were 81 MBPD for the fourth quarter of 2017 compared to 67 MBPD for the fourth quarter of last year.

6 Capitalization

Total debt principal outstanding at December 31, 2017 was $24.8 billion, including $3.2 billion of junior subordinated notes, to which the debt rating agencies ascribe partial equity content. At December 31, 2017, Enterprise had consolidated liquidity of approximately $3.7 billion, which was comprised of unrestricted cash on hand and available borrowing capacity under our revolving credit facilities.
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

### pattern `hold-outlook-steer-to-low-end` — 1 row(s)

#### A33. `E2CHK-195c4f302b0636bf`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `LOWERED`  
**Rater (blind):** `MAINTAINED`  
**Adjudicator (disagree, high confidence):** `MAINTAINED`
**Adjudicator brief:** The CFO says "we are holding our outlook for the year yet currently anticipate results to be closer to the low end of our range" — an explicit reaffirmation with no figure changed. Section 3's LOWERED requires a target "decreased versus a prior figure", while MAINTAINED is "explicitly reaffirms previously-issued guidance without changing it". The owner must weigh whether steering to the low end of an unchanged range should ever count as LOWERED, since this phrasing recurs in earnings releases.
**Rater's reason (its own words, written before it saw any stored label):** Guidance is least sure: 'we are holding our outlook for the year yet currently anticipate results to be closer to the low end of our range' explicitly reaffirms the prior range without changing the figure, so maintained rather than lowered; 'a dynamic environment marked by increasing memory costs' is a realized price increase with no shortage asserted, and 'certain litigation charges' inside the $208 million of adjustments asserts charges actually taken.
<details><summary>chunk text (2326 chars)</summary>

```
“We are pleased with our execution in Q1, driving better than expected revenue growth and non-GAAP EPS above consensus.” said Karen Parkhill, CFO, HP Inc. “With just one quarter behind us in a dynamic environment marked by increasing memory costs, we are holding our outlook for the year yet currently anticipate results to be closer to the low end of our range. We are well practiced at managing through headwinds and remain focused on executing our mitigation plans.”

First quarter GAAP diluted net EPS was $0.58, down from $0.59 in the prior-year period and within the previously provided outlook of $0.58 to $0.66. First quarter non-GAAP diluted net EPS was $0.81, up from $0.74 in the prior-year period and within the previously provided outlook of $0.73 to $0.81. First quarter non-GAAP net earnings and non-GAAP diluted net EPS exclude after-tax adjustments of $208 million, or $0.23 per diluted share, related to restructuring and other charges, acquisition and divestiture (credits) charges, net, amortization of intangible assets, certain litigation charges, non-operating retirement-related credits, tax adjustments, and the related tax impact on these items.

HP's net cash provided by operating activities in the first quarter of fiscal 2026 was $383 million. Accounts receivable ended the quarter at $5.3 billion, down 2 days quarter over quarter to 33 days. Inventory ended the quarter at $8.7 billion, up 2 days quarter over quarter to 68 days. Accounts payable ended the quarter at $18.2 billion, up 2 days quarter over quarter to 141 days.

HP generated $175 million of free cash flow in the first quarter of fiscal 2026. Free cash flow includes net cash provided by operating activities of $383 million adjusted for net investments in leases from integrated financing of $25 million and net investments in property, plant, equipment and purchased intangible of $233 million.

HP’s dividend payment of $0.30 per share in the first quarter resulted in cash usage of $277 million. HP also utilized $325 million of cash during the quarter to repurchase approximately 13.3 million shares of common stock in the open market. HP exited the quarter with $3.2 billion in gross cash, which includes cash and cash equivalents of $3.2 billion, and short-term investments of $3 million included in other current assets.
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

### pattern `leadership-transition-ceremonial-praise` — 1 row(s)

#### A34. `E2CHK-2683c59700eec6d3`  ·  field `sentiment`  ·  arm G-N
> **This ruling enters NO reported estimate.** The sentiment primary is P-arm only, every sentiment secondary is computed on P, and S-NOISE uses rater A vs rater B without adjudications. This row is in an off-primary arm and is included solely so the escalated set is complete — rule it or skip it, no number moves either way.
**Stored (student):** `NEUTRAL`  
**Rater (blind):** `POSITIVE`  
**Adjudicator (disagree, medium confidence):** `POSITIVE`
**Adjudicator brief:** Every characterization of the company in this transition announcement is favorable: "Intel has made significant progress on its strategy", "instrumental in reenergizing the company's culture to drive better execution", "He leaves Intel in a strong strategic and financial position". Section 2's POSITIVE includes "explicitly favorable characterization by the filer", and there is no unfavorable content to balance it. The owner must weigh whether ceremonial praise in a leadership-change release counts as tone "regarding the business's current results and condition" or is procedural boilerplate that should stay NEUTRAL.
**Rater's reason (its own words, written before it saw any stored label):** Sentiment POSITIVE on the filer's explicit favorable characterization of its own condition — 'Intel has made significant progress on its strategy' and 'He leaves Intel in a strong strategic and financial position'.
<details><summary>chunk text (2653 chars)</summary>

```
“I am thrilled to rejoin and lead Intel forward at this important time for the company, our industry and our nation,” said Gelsinger. “Having begun my career at Intel and learned at the feet of Grove, Noyce and Moore, it’s my privilege and honor to return in this leadership capacity. I have tremendous regard for the company’s rich history and powerful technologies that have created the world’s digital infrastructure.

I believe Intel has significant potential to continue to reshape the future of technology and look forward to working with the incredibly talented global Intel team to accelerate innovation and create value for our customers and shareholders.” “The Board and I deeply appreciate Bob Swan for his leadership and significant contributions through

this period of transformation for Intel,” continued Ishrak. “Under his leadership, Intel has made significant progress on its strategy to transform into a multi-architecture XPU company to capitalize on market shifts and extend Intel’s reach into fast-growing markets. Bob has also been instrumental in reenergizing the company’s culture to drive better execution of our product and innovation roadmap. He leaves Intel in a strong strategic and financial position,

and we thank him for his ongoing guidance as he works with Pat to ensure the leadership transition is seamless.” “My goal over the past two years has been to position Intel for a new era of distributed intelligence, improving execution to strengthen our core CPU franchise and extending our reach to accelerate growth,” said Bob Swan. “With significant progress made

across those priorities, we’re now at the right juncture to make this transition to the next leader of Intel. I am fully supportive of the Board’s selection of Pat and have great confidence that, under his leadership and the rest of the

management team, Intel will continue to lead the market as one of the world’s most influential technology companies.” Most recently, Gelsinger served as the CEO of VMware since 2012, where he significantly transformed the company into a recognized global leader in cloud infrastructure, enterprise mobility and cyber security, almost tripling the company’s annual

revenues. Prior to joining VMware, Gelsinger was President and Chief Operating Officer of EMC Information Infrastructure Products at EMC, overseeing engineering and operations for information storage, data computing, backup and recovery, RSA security and enterprise solutions. Before joining EMC, he spent 30 years at Intel, becoming the company’s first Chief Technology Officer and driving the creation of key industry technologies such as USB and
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

### pattern `preannouncement-versus-prior-guidance-range` — 1 row(s)

#### A35. `E2CHK-6696be4c00546807`  ·  field `guidance_direction`  ·  arm G-A
**Stored (student):** `MAINTAINED`  
**Rater (blind):** `RAISED`  
**Adjudicator (agree, medium confidence):** `MAINTAINED`
**Adjudicator brief:** The passage reprints the prior guidance ranges and then says the company "estimates that it will exceed its previously issued guidance ranges for earnings on a GAAP basis" while "adjusted earnings ... will be within its previously issued guidance ranges". No target is restated at a higher number, so section 3's RAISED ("increased versus a prior figure") is not met, while the adjusted-earnings sentence is an explicit reaffirmation of a previously-stated range. The owner must weigh a third reading the rubric leaves open — that a pre-announcement about expected actual results is not a guidance action at all, hence NONE.
**Rater's reason (its own words, written before it saw any stored label):** Guidance: the passage both states 'it will exceed its previously issued guidance ranges for earnings on a GAAP basis per share' and that adjusted earnings 'will be within its previously issued guidance ranges'; the leading and more prominent claim is the upward revision versus a prior figure, so RAISED over MAINTAINED.
<details><summary>chunk text (2327 chars)</summary>

```
(1 )% (1 )% (2 )% (2.0 )% Estimated sales growth, operational 14 % 16 % 11 % 11.5 % Less: Estimated impact of the aforementioned acquisitions and divestitures 6 % 7 % 3.5 % 4.0 % Estimated sales growth, organic

8 % 9 % 7.5 % 7.5 % Prior Guidance Estimate - Q4 and Full Year 2019 Earnings per Share Q4 2019 Estimate Full Year 2019 Estimate (Low) (High) (Low) (High) GAAP results $ 0.22 $ 0.25 $ 0.72 $

0.75 Estimated amortization expense 0.13 0.13 0.44 0.44 Estimated acquisition / divestitures-related net charges (credits) 0.06 0.06 0.33 0.33 Estimated other adjustments 0.01 0.01 0.06 0.06 Adjusted results $ 0.42 $ 0.45 $ 1.55 $ 1.58 The prior guidance estimates presented above for revenue growth rates and earnings per share for the fourth quarter and full year 2019 were previously disclosed by the company in the third quarter of 2019.

While the company is still conducting financial closing procedures for the fourth quarter and full year, the company estimates that it will exceed its previously issued guidance ranges for earnings on a GAAP basis per share for the fourth quarter and full year 2019, primarily due to a significant non-cash tax benefit arising from an intra-entity asset transfer of intellectual property completed in the fourth quarter of 2019. The company estimates adjusted earnings, excluding certain charges (credits), will be within its previously issued guidance ranges for the fourth quarter and full year 2019.

To supplement our financial statements presented on a GAAP basis, we disclose certain non-GAAP financial measures, including adjusted net income (earnings) and adjusted net income (earnings) per share that exclude certain amounts, operational net sales, which exclude the impact of foreign currency fluctuations, and organic net sales, which exclude the impact of foreign currency fluctuations and the impact of aforementioned acquisitions and divestitures. These non-GAAP financial measures are not in accordance with generally accepted accounting principles in the United States and should not be considered in isolation from or as a replacement for the most directly comparable GAAP financial measures. Further, other companies may calculate these non-GAAP financial measures differently than we do, which may limit the usefulness of those measures for comparative purposes.
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

### pattern `promotional-award-block-vs-mixed-financials` — 1 row(s)

#### A36. `E2CHK-abb5c701902a9312`  ·  field `sentiment`  ·  arm G-N
> **This ruling enters NO reported estimate.** The sentiment primary is P-arm only, every sentiment secondary is computed on P, and S-NOISE uses rater A vs rater B without adjudications. This row is in an off-primary arm and is included solely so the escalated set is complete — rule it or skip it, no number moves either way.
**Stored (student):** `NEUTRAL`  
**Rater (blind):** `POSITIVE`  
**Adjudicator (disagree, medium confidence):** `POSITIVE`
**Adjudicator brief:** Alongside mixed financials ("Net income of $2.5 billion decreased 5%", "Total investment banking fees (excl. self-led) of $1.1 billion decreased $1.3 billion, or 54%"), roughly half the chunk is explicit self-characterization: "Continued Business Leadership", "World's Best Bank", "Strong Digital Usage Continued", "Record quarterly CashPro App Active Users increased 25%", "reflecting strong client demand". Section 2's POSITIVE covers "achievement" and "explicitly favorable characterization by the filer", judged by predominance across the passage as a whole. The owner must weigh whether an awards-and-records block outweighs declining headline earnings.
**Rater's reason (its own words, written before it saw any stored label):** Sentiment POSITIVE is a close call — net income 'decreased 5%' and 'investment banking fees ... decreased $1.3 billion, or 54%' cut against it, but the filer's explicit characterization is favorable throughout ('Record quarterly CashPro App Active Users increased 25%', 'reflecting strong client demand', an awards list); IMPAIRMENT_WRITEDOWN REALIZED follows addendum rule 6's consistency directive on carrying-value reductions applied to the substantively discussed 'Provision for credit losses was $149 million, primarily driven by a dampened macroeconomic outlook'.
<details><summary>chunk text (3419 chars)</summary>

```
5 Global Banking1,2,3 Financial Results Three months ended ($ in millions) 12/31/2022 9/30/2022 12/31/2021 Total revenue2,3 $6,438 $5,591 $5,907 Provision for credit losses 149 170 (463) Noninterest expense 2,833 2,651 2,717 Pretax income 3,456 2,770 3,653 Income tax expense 916 734 986 Net income $2,540 $2,036 $2,667 Business Highlights2(B) Three months ended ($ in billions) 12/31/2022 9/30/2022 12/31/2021 Average deposits $503.5 $495.2 $562.4 Average loans and leases 380.4 384.3 338.6 Total Corp. IB fees (excl. self- led)2 1.1 1.2 2.4 Global Banking IB fees2 0.7 0.7 1.5 Business Lending revenue 2.7 2.1 2.2 Global Transaction Services revenue4 3.1 2.8 2.1 Efficiency ratio 44 % 47 % 46 % Return on average allocated capital 23 18 25 1 Comparisons are to the year-ago quarter unless noted. 2 Global Banking and Global Markets share in certain deal economics from investment banking, loan origination activities, and sales and trading activities. 3 Revenue, net of interest expense. 4 Prior periods have been revised to conform to current-period presentation. • Net income of $2.5 billion decreased 5% – Pretax income of $3.5 billion decreased 5% – Pretax, pre-provision income(D) of $3.6 billion increased 13% • Revenue of $6.4 billion increased $531 million driven by higher NII from the benefit of higher interest rates and loan growth, partially offset by lower investment banking fees and lower treasury service charges due to higher earnings credit rates • Provision for credit losses was $149 million, primarily driven by a dampened macroeconomic outlook and loan growth, with an increase of $612 million from Q4-21 as the prior year benefited from asset quality improvement and an improved macroeconomic outlook • Noninterest expense of $2.8 billion increased 4%, primarily reflecting continued investments in the business, including strategic hiring and technology Continued Business Leadership • Global Most Innovative Financial Institution – 2022(m) • World's Best Bank, North America’s Best Bank for Small to Medium-sized Enterprises, and Best Bank in the US(n) • Best Global Bank for Payments & Collections(o) • Model Bank for Corporate Digital Banking – For CashPro App(p) • World’s Best Bank for Payments and Treasury and North America’s Best Bank for Transaction Services(n) • Best Global Bank for Trade Finance FX – 2023 (m) • Outstanding Global Leadership in Sustainable Project Finance, and Outstanding Leadership in Sustainable Finance for North America(m) • Relationships with 73% of the Global Fortune 500; 95% of the U.S. Fortune 1,000 (2022) See page 11 for Business Leadership sources. Strong Digital Usage Continued1 • 75% digitally active clients across commercial, corporate, and business banking clients (CashPro & BA360 platforms) (as of November 2022) • Record quarterly CashPro App Active Users increased 25% and sign-ins increased 50% • Record quarterly CashPro App Payment Approvals value was $186 billion, increased 40% • Record quarterly percentage of eligible credit monitoring documents uploaded digitally at 42%, increased 1,069 bps (as of November 2022) Business Highlights1,2(B) • Average loans and leases of $380 billion increased $42 billion, or 12%, reflecting strong client demand in the first half of 2022 • Average deposits of $503 billion decreased $59 billion, or 10% • Total investment banking fees (excl. self-led) of $1.1 billion decreased $1.3 billion, or 54%
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

### pattern `reaffirmed-multiyear-cost-savings-target` — 1 row(s)

#### A37. `E2CHK-a55a42eef205eb7f`  ·  field `guidance_direction`  ·  arm P
**Stored (student):** `NONE`  
**Rater (blind):** `MAINTAINED`  
**Adjudicator (disagree, medium confidence):** `MAINTAINED`
**Adjudicator brief:** The CEO states the company "remain[s] on track to achieve our previously announced goal of $750 million of savings by the end of 2023" -- an explicit reaffirmation of a previously-stated number, which is precisely what section 3's MAINTAINED and its judging rule ("an explicit reaffirmation of a previously-stated number") describe. Stored NONE treats the release as historical results only and misses that sentence. Owner must weigh whether a multi-year cost-savings objective counts as "previously-issued forward guidance" or whether only revenue/EPS-style targets qualify.
**Rater's reason (its own words, written before it saw any stored label):** Guidance is the least certain field: 'remain on track to achieve our previously announced goal of $750 million of savings by the end of 2023' is an explicit reaffirmation of a specific previously-issued quantified target, which is MAINTAINED rather than NONE; sentiment POSITIVE on 'reported strong financial results ... and made significant progress'.
<details><summary>chunk text (2477 chars)</summary>

```
Exhibit 99.1 February 3, 2022 Prudential Financial, Inc. Announces 2021 Results • Fourth quarter 2021 net income attributable to Prudential Financial, Inc. of $1.208 billion or $3.13 per Common share versus net income of $819 million or $2.03 per share for the year-ago quarter.

• Fourth quarter 2021 after-tax adjusted operating income of $1.227 billion or $3.18 per Common share versus $1.130 billion or $2.80 per share for the year-ago quarter. • 2021 net income attributable to Prudential Financial, Inc. of $7.724 billion or $19.51 per Common share versus net loss of $374 million or $1.00 per share for 2020.

• 2021 after-tax adjusted operating income of $5.772 billion or $14.58 per Common share versus $3.913 billion or $9.72 per share for 2020. • Book value per Common share of $161.26 versus $167.81 per share for the year-ago; adjusted book value per Common share of $108.72 versus $94.79 per share for the year-ago.

• Parent company highly liquid assets (1) of $3.6 billion versus $5.6 billion for the year-ago quarter. • Assets under management (2) of $1.742 trillion versus $1.721 trillion for the year-ago quarter. •

As previously announced, the Company’s Board of Directors has authorized the repurchase of up to $1.5 billion of outstanding Common Stock during the period from January 1, 2022 through December 31, 2022. In addition, the Company declared a quarterly dividend of $1.20 per share of Common Stock, payable on March 11, 2022, to shareholders of record as of February 15, 2022, representing an increase of 4% over the prior year dividend level and a 4% annualized yield on adjusted book value.

Charles Lowrey, Chairman and CEO, commented on results: “Prudential reported strong financial results for the fourth quarter and full year, and made significant progress in becoming a higher growth, less market sensitive, and more nimble company.

During 2021, we entered into agreements to divest lower growth and more market sensitive businesses and programmatically acquired businesses for sustainable long-term growth. We advanced our cost savings program and remain on track to achieve our previously announced goal of $750 million of savings by the end of 2023. We also refined our product mix to meet our customers’ changing needs. We did all of this while returning $4.3 billion to shareholders through share repurchases and dividends, expanding our commitments to our employees and communities, and taking new steps to address climate change.
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

### pattern `results-plus-guidance-withdrawal` — 1 row(s)

#### A38. `E2CHK-c930635e1e19d252`  ·  field `sentiment`  ·  arm G-A
> **This ruling enters NO reported estimate.** The sentiment primary is P-arm only, every sentiment secondary is computed on P, and S-NOISE uses rater A vs rater B without adjudications. This row is in an off-primary arm and is included solely so the escalated set is complete — rule it or skip it, no number moves either way.
**Stored (student):** `NEUTRAL`  
**Rater (blind):** `POSITIVE`  
**Adjudicator (disagree, medium confidence):** `POSITIVE`
**Adjudicator brief:** Every characterization of current results in this passage is explicitly favorable -- "CORE TOBACCO SEGMENTS DELIVER STRONG OCI AND CASH FLOW," "We had an excellent start to the year, growing our first-quarter adjusted diluted EPS by 18.5%," "strong cash generation and the strength of our balance sheet" -- while the guidance withdrawal is attributed to external "uncertainties related to the impact of the COVID-19 pandemic," not to performance. Section 2 asks for the tone regarding "the business's current results and condition," which here is unambiguously favorable. Owner must weigh whether a headline guidance withdrawal should pull an otherwise strongly favorable results passage down to NEUTRAL or NEGATIVE, since this pattern recurs across pandemic-era releases.
**Rater's reason (its own words, written before it saw any stored label):** Sentiment POSITIVE on 'CORE TOBACCO SEGMENTS DELIVER STRONG OCI AND CASH FLOW,' 'excellent start to the year, growing our first-quarter adjusted diluted EPS by 18.5%'; guidance WITHDRAWN on the explicit 'we're withdrawing our full-year 2020 adjusted diluted EPS guidance'; no red-flag category is affirmatively asserted despite the pandemic reference.
<details><summary>chunk text (2348 chars)</summary>

```
Exhibit 99.1 ALTRIA REPORTS 2020 FIRST-QUARTER RESULTS; CORE TOBACCO SEGMENTS DELIVER STRONG OCI AND CASH FLOW; WITHDRAWS EARNINGS GUIDANCE DUE TO UNCERTAIN COVID-19 IMPACTS ON DIVERSE BUSINESS MODEL

RICHMOND, Va. - April 30, 2020 - Altria Group, Inc. (Altria) (NYSE: MO) today announces its 2020 first-quarter business results, including strong performance from its core tobacco segments and the withdrawal of its full-year 2020 adjusted diluted earnings per share (EPS) guidance and 2020 - 2022 adjusted diluted EPS growth objective due to COVID-19 uncertainty.

“The first-quarter brought out the best in Altria’s employees as we navigated the dynamic tobacco environment and the unprecedented effects of the COVID-19 pandemic,” said Billy Gifford, Altria’s Chief Executive Officer. “We’ve approached these challenges together by focusing on the health and welfare of our employees, maintaining business continuity and supporting our communities.”

“We had an excellent start to the year, growing our first-quarter adjusted diluted EPS by 18.5%, driven by the strength of our smokeable and oral tobacco products segments. Due to the uncertainties related to the impact of the COVID-19 pandemic on our diverse business model and economic recovery scenarios, we’re withdrawing our full-year 2020 adjusted diluted EPS guidance and, as a result, we’re also withdrawing our compounded annual adjusted diluted EPS growth objective. We’re continuing to assess the COVID-19 situation and intend to reestablish guidance at the appropriate time.”

“Our dividend is important to our investors and it remains a top priority for us. Our objective continues to be a dividend payout ratio target of approximately 80% of adjusted diluted EPS. For 2020, we expect to recommend a quarterly dividend rate to our Board that reflects, among other things, our strong cash generation and the strength of our balance sheet.”

Altria Headline Financials 1 ($ in millions, except per share data) Q1 2020 Change vs. Q1 2019 Net revenues $6,359 13.0% Revenues net of excise taxes $5,046 15.0% Reported tax rate 26.5% 0.4 pp Adjusted tax rate 2 24.0% 0.1 pp

Reported diluted EPS $0.83 38.3% Adjusted diluted EPS 2 $1.09 18.5% 1 “Adjusted” financial measures presented in this release exclude the impact of special items. See “Basis of Presentation” for more information. 2
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

### pattern `topline-growth-with-bottomline-decline` — 1 row(s)

#### A39. `E2CHK-24b6855a3e22af3c`  ·  field `sentiment`  ·  arm P
**Stored (student):** `NEGATIVE`  
**Rater (blind):** `NEUTRAL`  
**Adjudicator (disagree, medium confidence):** `NEUTRAL`
**Adjudicator brief:** The passage runs both directions in flat language: "Total revenue increased 12% YoY to $28.1B" and "The sequential increase of $4.9B was primarily the result of increased free cash flow" against "Our operating income decreased 40% YoY" and a margin line of "-501 bp." Drivers are given as neutral +/- bullet lists with no favorable or unfavorable adjectives anywhere. Rubric section 2's mixed-passage rule says label by predominant tone and, if genuinely balanced with no lean, use NEUTRAL; top-line growth against bottom-line decline with no characterizing words is exactly that. The owner should weigh whether a flat recitation where every profit metric falls but every revenue/cash metric rises counts as balanced (my call) or as predominantly unfavorable.
**Rater's reason (its own words, written before it saw any stored label):** Sentiment NEUTRAL is the closest call: 'Total revenue increased 12% YoY to $28.1B' and 'Free cash flow ... 46%' sit against 'Our operating income decreased 40% YoY' and 'Operating margin ... -501 bp,' all in a flat plus/minus bullet register with no lean; both flags come from 'higher average cost per vehicle due to lower fixed cost absorption for certain models, an increase in tariffs, and sales mix.'
<details><summary>chunk text (3526 chars)</summary>

```
F I N A N C I A L S U M M A R Y (Unaudited) ($ in millions, except percentages and per share data) Q3-2024 Q4-2024 Q1-2025 Q2-2025 Q3-2025 YoY Total automotive revenues 20,016 19,798 13,967 16,661 21,205 6% Energy generation and storage revenue 2,376 3,061 2,730 2,789 3,415 44% Services and other revenue 2,790 2,848 2,638 3,046 3,475 25% Total revenues 25,182 25,707 19,335 22,496 28,095 12% Total gross profit 4,997 4,179 3,153 3,878 5,054 1% Total GAAP gross margin 19.8% 16.3% 16.3% 17.2% 18.0% -185 bp Operating expenses 2,280 2,596 2,754 2,955 3,430 50% Income from operations 2,717 1,583 399 923 1,624 -40% Operating margin 10.8% 6.2% 2.1% 4.1% 5.8% -501 bp Adjusted EBITDA (1) (2) 4,665 4,333 2,814 3,401 4,227 -9% Adjusted EBITDA margin (1) (2) 18.5% 16.9% 14.6% 15.1% 15.0% -348 bp Net income attributable to common stockholders (GAAP) (1) 2,173 2,128 409 1,172 1,373 -37% Net income attributable to common stockholders (non-GAAP) (1) (3) 2,505 2,107 934 1,393 1,770 -29% EPS attributable to common stockholders, diluted (GAAP) (1) 0.62 0.60 0.12 0.33 0.39 -37% EPS attributable to common stockholders, diluted (non-GAAP) (1) (3) 0.72 0.60 0.27 0.40 0.50 -31% Net cash provided by operating activities 6,255 4,814 2,156 2,540 6,238 0% Capital expenditures (4) (3,513) (2,780) (1,492) (2,394) (2,248) -36% Free cash flow (4) 2,742 2,034 664 146 3,990 46% Cash, cash equivalents and investments 33,648 36,563 36,996 36,782 41,647 24% 4 (1) As a result of the adoption of the new crypto assets standard, the previously reported quarterly periods in 2024 have been recast. (2) Beginning in Q1'25, Adjusted EBITDA (non-GAAP) is presented net of digital assets gains and losses and all prior periods have been adjusted. (3) Beginning in Q1'25, Net income attributable to common stockholders (non-GAAP) is presented net of digital assets gains and losses and all prior periods have been adjusted. (4) Beginning in Q1'25, Capital expenditures is presented inclusive of purchases of solar energy systems and all prior periods have been adjusted.

F I N A N C I A L S U M M A R Y Revenue Total revenue increased 12% YoY to $28.1B. YoY, revenue was impacted by the following items(1): + increase in vehicle deliveries + growth in Energy Generation and Storage + growth in Services and Other - lower regulatory credit revenue - lower one-time FSD revenue recognition YoY due to Q3’24 releases related to Cybertruck and certain features such as Actually Smart Summon Profitability Our operating income decreased 40% YoY to $1.6B, resulting in a 5.8% operating margin. YoY, operating income was primarily impacted by the following items(1): - increase in operating expenses (excl. SBC and Restructuring and Other) driven by SG&A, AI and other R&D projects - increase in SBC and Restructuring and Other charges - lower regulatory credit revenue - lower one-time FSD revenue recognition YoY as described above - higher average cost per vehicle due to lower fixed cost absorption for certain models, an increase in tariffs, and sales mix, partially offset by lower raw material costs + growth in Energy Generation and Storage gross profit + increase in vehicle deliveries + growth in Services and Other gross profit Cash Quarter-end cash, cash equivalents and investments was $41.6B. The sequential increase of $4.9B was primarily the result of increased free cash flow. 5 (1) Impact is calculated on a constant currency basis. Actuals are compared against current results converted into USD using average exchange rates from Q3’24.
```
</details>

**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)

## PART B — the 20-row S-PROBE of the UNCONTESTED set

These are rows where the blind rater independently produced **the same** label as the student on every applicable gate-bearing field, drawn seeded (20260906) by pinned code after rating from the 402 eligible rows — realized 12 P / 4 G-A / 4 G-N. They are the design's only non-model check: the protocol only ever re-examines disagreements, so rows where student and rater are wrong the same way are otherwise invisible (§5.5). Rule **AGREE** or **OVERTURN** against the stored label shown.

**The trigger and its price.** If **≥ 2 of 20** are overturned, the one pre-committed extension fires: every uncontested row with an applicable gate-bearing field goes to the adjudicator once on those fields and the primaries are recomputed. Realized size of that sweep, re-derived here: **402 chunks = 619 (chunk, field) rows → 16 adjudicator batches** at the pinned ≤ 40 rows/batch (the design modelled ~10 runs at §14.7 and ~7 at §5.5, on chunk counts and on expected rather than realized numbers). New disagreements it produces become new `needs_human` rows for you — §14.7 models **~+19 owner items, band 0–38**. It adds no chunks, no API calls, and fires at most once. Probe rulings themselves never enter a primary; only the sweep they trigger does.

### B1. `E2CHK-3536f1859d0b9ace`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `NEUTRAL`; `guidance_direction` = `LOWERED`
<details><summary>chunk text (2938 chars)</summary>

```
October 27, 2020 Eli Lilly and Company Lilly Corporate Center Indianapolis, Indiana 46285 U.S.A. +1.317.276.2000 www.lilly.com For Release: Immediately Refer to: Mark Taylor; mark.taylor@lilly.com; (317) 276-5795 (Media) Kevin Hern; hern_kevin_r@lilly.com; (317) 277-1838 (Investors) Lilly Reports Third-Quarter Financial Results, Updates Guidance

• Revenue in the third quarter of 2020 increased 5 percent driven by volume growth of 9 percent, while on a year-to-date basis revenue increased 6 percent driven by volume growth of 12 percent. • Key growth products launched since 2014, consisting of Taltz, Trulicity, Verzenio, Jardiance, Olumiant, Emgality, Tyvyt, Baqsimi, Cyramza, Retevmo and Basaglar contributed nearly 9 percentage points of revenue growth and represented approximately 52 percent of total revenue for the quarter.

Lilly continues to rapidly advance the development of potential therapeutics for the treatment of COVID-19 and has submitted requests for Emergency Use Authorization to the FDA for both bamlanivimab and baricitinib. The company anticipates its full-year 2020 COVID-19 research and development expense to be approximately $400 million.

• Third-quarter 2020 operating expenses increased 9 percent, driven by higher marketing and research and development investments, including expenses of $125 million to develop potential COVID-19 therapies. • Third-quarter 2020 earnings per share (EPS) decreased to $1.33 on a reported basis and increased to $1.54 on a non-GAAP basis.

• 2020 EPS guidance lowered to be in the range of $6.20 to $6.40 on a reported basis and reaffirmed to be in the range of $7.20 to $7.40 on a non-GAAP basis. Eli Lilly and Company (NYSE: LLY) today announced financial results for the third quarter of 2020.

$ in millions, except per share data Third Quarter % 2020 2019 Change Revenue $ 5,740.6 $ 5,476.6 5% Net Income – Reported 1,208.4 1,253.9 (4)% EPS – Reported 1.33 1.37 (3)% Net Income – Non-GAAP 1,406.9 1,360.0 3% EPS – Non-GAAP

1.54 1.48 4%

Certain financial information for 2020 and 2019 is presented on both a reported and a non-GAAP basis. Some numbers in this press release may not add due to rounding. Reported results were prepared in accordance with U.S. generally accepted accounting principles (GAAP), include all revenue and expenses recognized during the periods, and reflect Elanco Animal Health (Elanco) as discontinued operations during the first quarter of 2019. Non-GAAP measures reflect adjustments for the items described in the reconciliation tables later in the release, and assume that the disposition of Elanco occurred at the beginning of 2019 (including the benefit from the reduction in shares of common stock outstanding). The company’s 2020 financial guidance is being provided on both a reported and a non-GAAP basis. The non-GAAP measures are presented to provide additional insights into the underlying trends in the company’s business.
```
</details>

**RULE:** AGREE / OVERTURN

### B2. `E2CHK-397f693db996a0a5`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `NEUTRAL`
<details><summary>chunk text (2258 chars)</summary>

```
% (4.5) % Studios 884 1,041 1,058 (15.1) (1.6) Theme Parks 1,267 (477) 2,498 NM (119.1) Headquarters and Other (840) (563) (690) (49.3) 18.4 Eliminations (205) (220) 11 6.5 NM Total Adjusted EBITDA $ 5,675 $ 5,355 $ 8,711 6.0

% (38.5) % Percentage changes that are considered not meaningful are denoted with NM. Comcast 2021 Annual Report on Form 10-K 44 Table of Contents Media Segment Results of Operations Year ended December 31 (in millions) 2021 2020 2019 % Change

2020 to 2021 % Change 2019 to 2020 Revenue Advertising $ 10,291 $ 8,296 $ 9,267 24.1 % (10.5) % Distribution 10,449 8,795 8,887 18.8 (1.0) Other 2,040 1,845 1,793 10.5 2.9 Total revenue 22,780 18,936 19,947 20.3 (5.1) Operating costs and expenses

Programming and production 13,337 9,319 9,907 43.1 (5.9) Other operating and administrative 3,611 3,209 3,286 12.5 (2.3) Advertising, marketing and promotion 1,264 834 920 51.4 (9.3) Total operating costs and expenses 18,212 13,362 14,113 36.3 (5.3) Adjusted EBITDA $ 4,569

$ 5,574 $ 5,834 (18.0) % (4.5) % Media Segment – Revenue Advertising Revenue consists of the sale of advertising on our television networks, Peacock and digital properties. Year ended December 31 (in millions) 2021 2020 2019 % Change 2020 to 2021

% Change 2019 to 2020 Advertising $ 10,291 $ 8,296 $ 9,267 24.1 % (10.5) % Advertising, excluding Tokyo Olympics 9,054 8,296 9,267 9.1 (10.5)

Revenue increased in 2021 compared to 2020 primarily due to our broadcast of the Tokyo Olympics. Excluding $1.2 billion of revenue associated with our broadcast of the Tokyo Olympics, advertising revenue increased due to higher pricing in the current year period, reduced spending from advertisers in the prior year period as a result of COVID-19, increased advertising revenue in Peacock and an increased number of sporting events, partially offset by continued audience ratings declines at our networks.

R

evenue decreased in 2020 compared to 2019 primarily due to continued audience rating declines at our networks and reduced spending from advertisers as a result of COVID-19, including as a result of the reduced number of sporting events, partially offset by higher prices for advertising units sold and advertising revenue in Peacock following its launch in 2020.
```
</details>

**RULE:** AGREE / OVERTURN

### B3. `E2CHK-3d8d81d5cbe61eea`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `POSITIVE`; `guidance_direction` = `NONE`
<details><summary>chunk text (2685 chars)</summary>

```
5,539 5 % $ 11,490 $ 11,135 3 % Second Quarter 2025 Results (All comparisons vs. second quarter 2024, unless noted otherwise)

Segment income for Business Insurance was $813 million after-tax, an increase of $157 million. Segment income increased primarily due to a higher underlying underwriting gain, higher net favorable prior year reserve development, higher net investment income and lower catastrophe losses. The underlying underwriting gain benefited from higher business volumes.

Combined ratio: • The combined ratio of 93.6% improved 2.5 points due to an improvement in the underlying combined ratio (0.9 points), higher net favorable prior year reserve development (0.8 points) and lower catastrophe losses (0.8 points). • The underlying combined ratio improved 0.9 points to an excellent 88.3%.

• Net favorable prior year reserve development was primarily driven by better than expected loss experience in the workers’ compensation product line for multiple accident years, partially offset by an addition to reserves related to run-off operations.

Net written premiums of $5.792 billion increased 5%, led by strong growth of 10% in our core Middle Market business. This was partially offset by a 3% decline in net written premiums in National Property and Other, reflecting our disciplined underwriting.

5 Year-to-Date 2025 Results (All comparisons vs. year-to-date 2024, unless noted otherwise)

Segment income for Business Insurance was $1.496 billion after-tax, an increase of $76 million. Segment income increased primarily due to a higher underlying underwriting gain, higher net favorable prior year reserve development and higher net investment income, partially offset by higher catastrophe losses. The underlying underwriting gain benefited from higher business volumes.

Combined ratio: • The combined ratio of 94.9% increased 0.2 points due to higher catastrophe losses (2.2 points), partially offset by higher net favorable prior year reserve development (1.1 points) and an improvement in the underlying combined ratio (0.9 points).

• The underlying combined ratio improved 0.9 points to an excellent 88.3%. • Net favorable prior year reserve development was primarily driven by the same factors described above for the second quarter of 2025.

Net written premiums of $11.490 billion increased 3%, after the ceded premium impact of the enhanced casualty reinsurance program that took effect January 1, 2025. This change in reinsurance reduced the segment’s net written premium growth by 2 points, as the full year’s worth of ceded premium was booked in the first quarter of 2025. Premium growth also reflected strong renewal premium change and retention.
```
</details>

**RULE:** AGREE / OVERTURN

### B4. `E2CHK-3ea345cfc589396c`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `POSITIVE`; `guidance_direction` = `RAISED`
<details><summary>chunk text (2444 chars)</summary>

```
Cash : Cash generated from operations was $251 million, a decrease of 18% year-over-year. Total cash, cash equivalents and marketable securities finished the quarter at $1.72 billion. Deferred Revenue

: Deferred revenue on the balance sheet as of July 31, 2016 was $3.82 billion, an increase of 26% year-over-year, and 27% in constant currency. Unbilled deferred revenue, representing business that is contracted but unbilled and off balance sheet, ended the second quarter at approximately $8.0 billion, up 29% year-over-year. This includes approximately $300 million related to unbilled deferred revenue from the Demandware acquisition

. As of August 31, 2016 , the company is initiating revenue ,

earnings per share, and deferred revenue guidance for its third quarter of fiscal year 2017. In addition, the company is raising its full fiscal year 2017 revenue, maintaining non-GAAP earnings per share guidance, and updating its operating cash flow guidance

previously provided on June 1, 2016. The company is also raising its full fiscal year GAAP earnings per share guidance, previously provided on May 18, 2016. This guidance includes the impact of acquisitions that have closed to date or have signed and are expected to close in the company’s third quarter of fiscal 2017.

Q3 FY17 Guidance : Revenue is projected to be approximately $2.11 billion to $2.12 billion, an increase of 23% to 24% year-over-year. GAAP loss per share is projected to be ($0.05) to ($0.04), while non-GAAP diluted earnings per share is projected to be $0.20 to $0.21.

On balance sheet deferred revenue growth is projected to be approximately 20% year-over-year. Full Year FY17 Guidance : Revenue is projected to be approximately $8.275 billion to $8.325 billion, an increase of 24% to 25% year-over-year. GAAP diluted earnings per share is projected to be $0.27 to $0.29, while non-GAAP diluted earnings per share is projected to be $0.93 to $0.95.

Operating cash flow growth is projected to be 20% to 21% year-over-year . The following is a per share reconciliation of GAAP diluted earnings per share to non-GAAP diluted earnings per share guidance for the next quarter and full fiscal year:

Fiscal 2017 Q3 FY2017 GAAP (loss) EPS Range* ($0.05) - ($0.04) $0.27 - $0.29 Plus Amortization of purchased intangibles $ 0.10 $ 0.33 Stock-based expense $ 0.28 $ 1.15 Amortization of debt discount, net $ 0.01 $ 0.04 Less Gains on sales of strategic investments
```
</details>

**RULE:** AGREE / OVERTURN

### B5. `E2CHK-3ee0bbef93ae4dcb`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `NEUTRAL`
<details><summary>chunk text (2048 chars)</summary>

```
0.32 0.15 0.30 0.30 0.35 Nonperforming loans and leases as a percentage of loans and leases (1) 0.33 0.18 0.30 0.30 0.35 NPAs as a percentage of: Total assets (1) 0.23 0.14 0.22 0.23 0.26 Loans and leases HFI plus foreclosed property

0.36 0.19 0.34 0.34 0.39 Net charge-offs as a percentage of average loans and leases HFI 0.36 0.40 0.41 0.38 0.40 ALLL as a percentage of loans and leases HFI 1.63 0.52 1.05 1.05 1.05 Ratio of ALLL to: Net charge-offs

4.76x 2.03x 2.59x 2.80x 2.62x NPLs 5.04x 3.41x 3.52x 3.46x 2.97x Loans 90 days or more past due and still accruing as a percentage of loans and leases HFI (2) 0.04 % 0.03 % 0.04 % 0.04 % 0.04 %

(2) This asset quality ratio has been adjusted to remove the impact of government guaranteed mortgage and student loans and PCI, as applicable. Management believes the inclusion of such assets in this asset quality ratio results in distortion of this ratio such that it might not be reflective of asset collectability or might not be comparable to other periods presented or to other portfolios that do not have government guarantees or were not impacted by PCI accounting requirements.

Truist Financial Corporation 55 The following table presents activity related to NPAs: Table 11: Rollforward of NPAs (Dollars in millions) 2020 2019 Balance, January 1 $ 684 $ 585 New NPAs (1) 949 294 Advances and principal increases 86 64

Disposals of foreclosed assets (2) (158) (122) Disposals of NPLs (3) (23) (30) Charge-offs and losses (124) (71) Payments (147) (106) Transfers to performing status (85) (30) Other, net (5) — Ending balance, March 31 $ 1,177 $ 584 (1) For 2020, includes approximately $500 million of PCI loans that would have been classified as nonperforming as of December 31, 2019.

(2) Includes charge-offs and losses recorded upon sale of $53 million and $58 million for the three months ended March 31, 2020 and 2019, respectively. (3) Includes charge-offs and losses recorded upon sale of $7 million and $6 million for the three months ended March 31, 2020 and 2019, respectively.
```
</details>

**RULE:** AGREE / OVERTURN

### B6. `E2CHK-48a62fd38118e54c`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `NEUTRAL`; `guidance_direction` = `NONE`
<details><summary>chunk text (3100 chars)</summary>

```
orward-looking statements are subject to a number of risks, uncertainties and other factors, many of which are outside Cadence’s control, and which may cause actual results to differ materially from expectations expressed or implied in the forward-looking statements, including, among others: (i) Cadence’s ability to compete successfully in the highly competitive industries in which it operates and realize the benefits of its investments in research and development, including opportunities presented by AI; (ii) the success of Cadence’s efforts to maintain and improve operational efficiency and growth; (iii) the mix of products and services sold, the timing of orders and deliveries and the ability to develop, install or deliver Cadence’s products or services; (iv) changes in customer demands or supply constraints that could result in delays in purchases, development, installations or deliveries of Cadence’s products or services, including those resulting from consolidation, restructurings and other operational efficiency improvements of Cadence’s customers; (v) economic, geopolitical and industry conditions, including export controls, tariffs, other trade restrictions and other government regulations, as well as rising tensions and armed conflicts around the world; (vi) changes in tax laws, interest rate and currency exchange rate fluctuations, inflation rates, Cadence’s increased debt levels and obligations and Cadence’s ability to access capital and debt markets in the future; (vii) legislative or regulatory requirements; (viii) Cadence’s pending acquisitions which remain subject to certain closing conditions, the acquisition of other companies, businesses or technologies or the failure to successfully integrate and operate them; (ix) potential harm caused by compromises in cybersecurity and cybersecurity attacks; (x) capital expenditure requirements and events that affect cash flow, liquidity or reserves, or estimates Cadence may take from time to time with respect to accounts receivable, taxes and tax examinations, litigation, regulatory or other matters; (xi) the effects of any litigation, regulatory, tax or other proceedings to which Cadence is or may become a party or to which Cadence or its products, services, technologies or properties are subject, including the settlements with the DOJ (which is subject to court approval) and BIS, Cadence’s ongoing compliance, cooperation, audit and other obligations under the settlement agreements, any further inquiries or adverse actions by the court, the DOJ, BIS or other U.S. or foreign governmental authorities and any impact of the settlements on Cadence’s operations and business dealings in China, U.S. government contracting business and other customer relationships; and (xii) Cadence’s ability to successfully meet any environmental, social and governance targets and practices. In addition, the timing and amount of Cadence’s repurchases of its common stock are subject to business and market conditions, corporate and regulatory requirements, stock price, acquisition opportunities and other factors.
```
</details>

**RULE:** AGREE / OVERTURN

### B7. `E2CHK-66f7347c3bf8bd02`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `NEUTRAL`; `guidance_direction` = `NONE`
<details><summary>chunk text (2228 chars)</summary>

```
Occupancy and building operations 21.1 21.4 80.2 86.7 Licensing and other fee agreements 38.1 32.5 146.3 135.8 Other 50.8 48.7 116.0 161.7 Total Expenses 362.7 372.7 1,332.7 1,392.5 Operating Income 537.3 540.2 2,312.0 2,202.7 Non-Operating Income (Expense) Investment income 140.5

70.5 531.7 141.8 Interest and other borrowing costs (29.1 ) (31.6 ) (117.0 ) (123.5 ) Equity in net earnings (losses) of unconsolidated subsidiaries 32.7 27.8 129.2 110.2 Other non-operating income (expense) (106.7 ) (12.7 ) (329.6 ) (43.6 )

Total Non-Operating Income (Expense) 37.4 54.0 214.3 84.9 Income before Income Taxes 574.7 594.2 2,526.3 2,287.6 Income tax provision (benefit) (2,364.5 ) 220.8 (1,537.1 ) 753.5 Net Income $ 2,939.2 $ 373.4 $ 4,063.4 $ 1,534.1 Earnings per Common Share:

Basic $ 8.67 $ 1.10 $ 12.00 $ 4.55 Diluted 8.63 1.10 11.94 4.53 Weighted Average Number of Common Shares: Basic 339,153 338,083 338,707 337,496 Diluted 340,490 339,338 340,226 338,966 CME Group Inc. and Subsidiaries Quarterly Operating Statistics 4Q 2016

1Q 2017 2Q 2017 3Q 2017 4Q 2017 Trading Days 63 62 63 63 63 Quarterly Average Daily Volume (ADV) CME Group ADV (in thousands) Product Line 4Q 2016 1Q 2017 2Q 2017 3Q 2017 4Q 2017 Interest rate 8,300

9,169 8,210 7,424 7,970 Equity 2,875 2,766 2,707 2,624 2,632 Foreign exchange 883 894 879 971 941 Energy 2,586 2,496 2,632 2,693 2,489 Agricultural commodity 1,193 1,261 1,491 1,381 1,278 Metal 488 512 533 611 616 Total 16,325 17,098 16,453

15,704 15,925 Venue Electronic 14,375 14,947 14,582 14,264 14,265 Open outcry 1,130 1,362 1,115 889 1,066 Privately negotiated 820 789 756 551 594 Total 16,325 17,098 16,453 15,704 15,925 Average Rate Per Contract (RPC) CME Group RPC Product Line 4Q 2016

1Q 2017 2Q 2017 3Q 2017 4Q 2017 Interest rate $ 0.491 $ 0.492 $ 0.491 $ 0.485 $ 0.467 Equity 0.691 0.718 0.731 0.738 0.768 Foreign exchange 0.804 0.823 0.807 0.796 0.785 Energy 1.099 1.130 1.096 1.072 1.133 Agricultural commodity

1.336 1.334 1.300 1.251 1.251 Metal 1.486 1.496 1.449 1.376 1.315 Average RPC $ 0.731 $ 0.731 $ 0.749 $ 0.749 $ 0.736 CME Group Inc. and Subsidiaries Reconciliation of GAAP to non-GAAP Measures (dollars in millions, except per share amounts; shares in thousands)
```
</details>

**RULE:** AGREE / OVERTURN

### B8. `E2CHK-6c5a45cabe9acb51`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `POSITIVE`; `guidance_direction` = `RAISED`
<details><summary>chunk text (2504 chars)</summary>

```
AbbVie announced that the FDA has approved a label expansion of Botox to include eight new muscles for the treatment of upper limb spasticity in adults. The new muscles for treatment include additional muscles of the elbow and forearm, intrinsic hand muscles and thumb muscles. 6.7 million people in the U.S. are living with adult spasticity across a variety of neurologic conditions and Botox has demonstrated efficacy and has an established safety profile with over 10 years of clinical use in the treatment of adult upper limb spasticity.

Allergan Aesthetics and Soliton announced a definitive agreement under which Allergan Aesthetics will acquire Soliton and Resonic, its Rapid Acoustic Pulse device which recently received FDA 510(k) clearance and is a non-invasive treatment for the improvement in the appearance of cellulite. The novel platform technology uses non-invasive rapid, high-frequency sound waves to disrupt targeted cellular structures and connective tissue, physically impacting the fibrous septae beneath the skin that contribute to the dimpled appearance of cellulite.

AbbVie and Calico Life Sciences announced an extension of their leading-edge collaboration to discover, develop and bring to market new therapies for patients with age-related diseases, including neurodegeneration and cancer. This is the second collaboration extension and builds on the partnership established in 2014 and extended in 2018. The extension is for an additional three years, beginning in 2022, and AbbVie and Calico will each commit to contribute an additional $500 million. AbbVie and Calico have advanced three clinical stage programs in immuno-oncology and neurodegeneration and have a portfolio of more than 20 early-stage programs targeting specific disease pathways.

5 Full-Year 2021 Outlook

AbbVie is updating its GAAP diluted EPS guidance for the full-year 2021 from $7.27 to $7.47 to $6.04 to $6.14. AbbVie is raising its adjusted diluted EPS for the full-year 2021 from $12.37 to $12.57 to $12.52 to $12.62. The company's 2021 adjusted diluted EPS guidance excludes $6.48 per share of intangible asset amortization expense, non-cash charges for contingent consideration adjustments and other specified items.

www.abbvie.com . Follow @abbvie on Twitter, Facebook or LinkedIn . Conference Call AbbVie will host an investor conference call today at 8:00 a.m. Central time to discuss our second-quarter performance. The call will be webcast through AbbVie’s Investor Relations website at
```
</details>

**RULE:** AGREE / OVERTURN

### B9. `E2CHK-77f9908e5dafd434`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `POSITIVE`; `guidance_direction` = `RAISED`
<details><summary>chunk text (2076 chars)</summary>

```
Exhibit 99.1 Hewlett Packard Enterprise 11445 Compaq Center West Drive Houston, TX 77070 hpe.com News Release HPE Reports Fiscal 2021 Second Quarter Results Q2 marked by revenue growth, strong profitability and cash flow; raising FY21 EPS and FCF outlook Q2 2021 Financial Highlights:

• Revenue: $6.7 billion, up 11% from the prior-year period or 9% when adjusted for currency with better than normal sequential seasonality driven by strong demand • Annualized revenue run-rate (ARR): $678 million, up 30% from the prior-year period •

Intelligent Edge revenue: $799 million, up 20% from the prior year period or 17% when adjusted for currency • HPC & MCS revenue: $685 million, up 13% from the prior-year period or 11% when adjusted for currency •

Core businesses delivered revenue growth and strong profitability with Compute revenue of $3.0 billion, up 12% from the prior-year period or 10% when adjusted for currency and Storage revenue of $1.1 billion, up 5% from the prior-year period or 3% when adjusted for currency

• Diluted net earnings per share (“EPS”): • GAAP of $0.19, above the previously provided outlook of $0.02 to $0.08 per share • Non-GAAP of $0.46, up 70% from the prior-year period and above the previously provided outlook of $0.38 to $0.44 per share

• Cash flow from operations of $822 million, up $722 million from the prior-year period • Generated free cash flow of $368 million, up $770 million from the prior-year period Dividend: declared a regular cash dividend of $0.12 per share, payable on July 7, 2021

Outlook: • Fiscal 2021 Third quarter: Estimates GAAP diluted net EPS to be in the range of $0.04 to $0.10 and non-GAAP diluted net EPS to be in the range of $0.38 to $0.44 • Fiscal 2021: Raises GAAP diluted net EPS outlook to $0.60 to $0.72 and non-GAAP diluted net EPS outlook to $1.82 to $1.94

• Fiscal 2021 free cash flow 1 : Raises free cash flow guidance to $1.2 to $1.5 billion HOUSTON, Texas – June 1, 2021 – Hewlett Packard Enterprise (NYSE: HPE) today announced financial results for the second quarter, ended April 30, 2021.
```
</details>

**RULE:** AGREE / OVERTURN

### B10. `E2CHK-7cec415877164dcc`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `NEGATIVE`; `guidance_direction` = `NONE`
<details><summary>chunk text (2343 chars)</summary>

```
Jardiance is part of the company's alliance with Boehringer Ingelheim. Lilly reports as revenue royalties received on net sales of Jardiance. Alimta

For Q1 2022, worldwide Alimta revenue decreased 38% compared with Q1 2021, to $343.9 million. U.S. revenue decreased 3%, to $254.3 million, driven by decreased volume, partially offset by higher realized prices. Revenue outside the U.S. decreased 70%, to $89.7 million, largely driven by decreased volume due to entry of generic competition in certain markets and, to a lesser extent, lower realized prices.

The company expects continued volume decline for Alimta as a result of the entry of generic competition due to the loss of patent exclusivity in Japan and major European markets. An alternative form of pemetrexed launched in the U.S. during Q1 2022 and the company expects multiple generics to launch in Q2 2022, causing a rapid and severe decline in revenue.

For Q1 2022, worldwide Olumiant revenue increased 32% compared with Q1 2021, to $255.6 million. U.S. revenue was $71.3 million, representing growth of $46.6 million compared with Q1 2021. Revenue outside the U.S. was $184.3 million, an increase of 9%, driven by increased volume, partially offset by the unfavorable impact of foreign exchange rates and lower realized prices. Increased volume

11 worldwide was partially driven by utilization of Olumiant for the treatment of hospitalized patients with COVID-19. Emgality

For Q1 2022, Emgality generated worldwide revenue of $149.3 million, an increase of 25% compared with Q1 2021. U.S. revenue was $108.3 million, an increase of 7%, driven by increased demand, partially offset by lower realized prices. Revenue outside the U.S. was $41.0 million, an increase of $23.0 million compared with Q1 2021, driven by increased demand.

For Q1 2022, the company's Tyvyt revenue in China was $85.5 million, a decrease of 22% compared with Q1 2021, driven by lower realized prices due to the impact of the NRDL formulary in China on Tyvyt, largely offset by increased demand.

Tyvyt is part of the company's alliance with Innovent. Lilly reports total sales of Tyvyt made by Lilly as revenue, with payments made to Innovent for its portion of the gross margin reported as cost of sales. Lilly also reports as revenue a portion of the gross margin for Tyvyt sales made by Innovent.
```
</details>

**RULE:** AGREE / OVERTURN

### B11. `E2CHK-83bab413ca96db72`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `NEUTRAL`; `guidance_direction` = `NONE`
<details><summary>chunk text (2707 chars)</summary>

```
(30,044) nm (12.2) % $ 3,765,434 $ 4,566,061 $ 3,805,119 $ 4,508,060 (1.0) % 1.3 % Operating income (loss): Merchant Solutions $ 1,331,033 $ 1,726,214 $ 1,252,962 $ 1,675,186 6.2 % 3.0 % Issuer Solutions — 511,298 — 488,024 nm

4.8 % Corporate (527,991) (250,875) (417,983) (246,621) (26.3) % (1.7) % Gain on business disposition 4,260 — — — nm nm $ 807,302 $ 1,986,636 $ 834,979 $ 1,916,589 (3.3) % 3.7 % ---------------------------------------------------------------------------------- See Schedules 8 and 9 for a reconciliation of adjusted net revenue and adjusted operating income by segment to the most comparable GAAP measures and Schedule 10 for a discussion of non-GAAP financial measures.

Note: Amounts may not sum due to rounding. Note: nm = not meaningful. 9 Exhibit 99.1 SCHEDULE 4 CONSOLIDATED BALANCE SHEETS (UNAUDITED) GLOBAL PAYMENTS INC. AND SUBSIDIARIES (In thousands, except share data) June 30, 2025 December 31, 2024 ASSETS Current assets:

Cash and cash equivalents $ 2,611,662 $ 2,356,434 Accounts receivable, net 864,429 782,306 Settlement processing assets 2,077,445 1,599,390 Prepaid expenses and other current assets 405,279 350,274 Assets held for sale 905,442 — Current assets of discontinued operations 888,730 942,828 Total current assets

7,752,987 6,031,232 Goodwill 16,742,403 16,777,532 Other intangible assets, net 4,380,462 4,527,382 Property and equipment, net 1,414,244 1,400,247 Deferred income taxes 97,479 98,386 Notes receivable 804,480 772,297 Other noncurrent assets 1,862,917 1,845,053 Noncurrent assets of discontinued operations 15,463,538 15,438,126 Total assets

$ 48,518,510 $ 46,890,255 LIABILITIES, REDEEMABLE NONCONTROLLING INTERESTS AND EQUITY Current liabilities: Settlement lines of credit $ 627,900 $ 503,407 Current portion of long-term debt 1,868,295 1,008,750 Accounts payable and accrued liabilities 2,184,784 2,626,159 Settlement processing obligations 2,691,637 1,518,541 Liabilities held for sale

291,914 — Current liabilities of discontinued operations 518,845 595,857 Total current liabilities 8,183,375 6,252,714 Long-term debt 14,150,983 15,058,675 Deferred income taxes 1,702,310 1,574,232 Other noncurrent liabilities 577,449 543,603 Noncurrent liabilities of discontinued operations 482,804 444,464 Total liabilities 25,096,921 23,873,688 Commitments and contingencies

Redeemable noncontrolling interests 171,831 160,623 Equity: Preferred stock, no par value; 5,000,000 shares authorized and none issued — — Common stock, no par value; 400,000,000 shares authorized at June 30, 2025 and December 31, 2024; 242,475,957 shares issued and outstanding at June 30, 2025 and 248,708,899 shares issued and outstanding at December 31, 2024
```
</details>

**RULE:** AGREE / OVERTURN

### B12. `E2CHK-929886d5e0ebd1c7`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `NEUTRAL`; `guidance_direction` = `NONE`
<details><summary>chunk text (2496 chars)</summary>

```
522 503 419 3.8 24.6 1,025 840 22.0 Other intangibles 159 160 40 (.6 ) nm 319 87 nm Other 353 425 340 (16.9 ) 3.8 778 662 17.5 Total before merger and integration 4,259 4,311 3,527 (1.2 ) 20.8

8,570 7,029 21.9 Merger and integration charges 310 244 197 27.0 57.4 554 197 nm Total noninterest expense $ 4,569 $ 4,555 $ 3,724 .3 22.7 $ 9,124 $ 7,226 26.3 Second quarter noninterest expense of $4,569 million was $845 million (22.7 percent) higher than the

second quarter of 2022. Excluding merger and integration-related charges of $310 million in the second quarter of 2023 and $197 million in the second quarter of 2022, second quarter noninterest expense increased $732 million (20.8 percent) compared with the second quarter of 2022, driven by the impact of MUB operating expenses, core deposit intangible amortization expense, higher compensation expense and higher other noninterest expense. Compensation expense increased

$400 million (17.8 percent) compared with the second quarter of 2022 primarily due to MUB expense as well as merit and hiring to support business growth. Intangible amortization increased $119 million driven by the core deposit intangible

created as a result of the MUB acquisition. Other noninterest expense increased $13 million (3.8 percent) due to higher FDIC insurance expense driven by an increase in the assessment base and rate along with the inclusion of MUB in the current

year, partially offset by lower accruals related to future delivery exposures for merchant and airline processing and other liabilities. Noninterest expense increased $14 million (0.3 percent) on a linked quarter basis. Excluding merger and integration-related charges of $310 million in the second quarter of 2023 and $244 million in the first quarter

of 2023, second quarter noninterest expense decreased $52 million (1.2 percent) from the first quarter of 2023 driven by lower other noninterest expense. Other noninterest expense decreased $72 million (16.9 percent) primarily due to lower accruals related to future delivery exposures for merchant and airline processing and other liabilities.

Provision for Income Taxes The provision for income taxes for the second quarter of 2023 resulted in a tax rate of 23.3 percent on a taxable-equivalent basis (effective tax rate of 21.8 percent), compared with 22.4 percent on a taxable-equivalent basis (effective tax rate of 21.3 percent) in the second quarter of 2022, and a tax rate of 22.3 percent on a taxable-equivalent basis
```
</details>

**RULE:** AGREE / OVERTURN

### B13. `E2CHK-9b0e481826b4b02a`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `POSITIVE`; `guidance_direction` = `NONE`
<details><summary>chunk text (2782 chars)</summary>

```
• We are seeing high levels of engagement and sustained growth in Specs Lens creation, with the number of Lenses submitted increasing 28% year-over-year. • We are seeing expanding use cases across learning, gaming, and AI-powered experiences, with developers building immersive experiences in preparation for launch, including:

◦ Fossils, created by XR focused company VyuXR Immersive Studios, is an interactive AR learning experience that uses spatial puzzle mechanics to let users uncover and assemble prehistoric fossils while bringing extinct animals to life. ◦

Artel, created by Yegor Ryabtsov, is an AR drawing app that lets users create in 3D space with a wide range of brushes, colors, and effects, and now includes physics-based interactions that allow drawings to respond to gravity and motion.

2 Q2 2026 Outlook Snap Inc. will discuss its Q2 2026 outlook during its Q1 2026 Earnings Call (details below) and in its investor letter available at investor.snap.com. Conference Call Information

Snap Inc. is a technology company. We believe the camera presents the greatest opportunity to improve the way people live and communicate. Snap contributes to human progress by empowering people to express themselves, live in the moment, learn about the world, and have fun together.

Snap Inc. operates Snapchat, a visual messaging app that enhances your relationships with friends, family, and the world, and Specs Inc., a wholly-owned subsidiary dedicated to making computing more human, in addition to Bitmoji, Saturn, and other digital services. For more information, visit snap.com.

This press release contains forward-looking statements within the meaning of Section 27A of the Securities Act of 1933, as amended, and Section 21E of the Securities Exchange Act of 1934, as amended, about us and our industry that involve substantial risks and uncertainties. All statements other than statements of historical facts contained in this press release, including statements regarding guidance, our future results of operations or financial condition, future stock repurchase programs or stock dividends, business strategy and plans, user growth and engagement, product initiatives, objectives of management for future operations, and advertiser and partner offerings, are forward-looking statements. In some cases, you can identify forward-looking statements because they contain words such as “anticipate,” “believe,” “contemplate,” “continue,” “could,” “estimate,” “expect,” “going to,” “intend,” “may,” “plan,” “potential,” “predict,” “project,” “should,” “target,” “will,” or “would” or the negative of these words or other similar terms or expressions. We caution you that the foregoing may not include all of the forward-looking statements made in this press release.
```
</details>

**RULE:** AGREE / OVERTURN

### B14. `E2CHK-a9f86731756ad5f6`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `NEUTRAL`; `guidance_direction` = `NONE`
<details><summary>chunk text (2500 chars)</summary>

```
$ 0.17 $ (0.66) NM $ 3.72 $ 1.98 87.9 % Diluted net income (loss) per common share attributable to Walmart $ 0.17 $ (0.66) NM $ 3.71 $ 1.97 88.3 % Weighted-average common shares outstanding: Basic 2,693 2,711 2,693

2,733 Diluted 2,703 2,711 2,703 2,743 Dividends declared per common share $ — $ — $ 2.28 $ 2.24 NM = Not Meaningful 8 Walmart Inc. Condensed Consolidated Balance Sheets (Unaudited) October 31, January 31, October 31, (Amounts in millions)

2023 2023 2022 ASSETS Current assets: Cash and cash equivalents $ 12,154 $ 8,625 $ 11,587 Receivables, net 8,625 7,933 8,218 Inventories 63,951 56,576 64,706 Prepaid expenses and other 3,661 2,521 3,169 Total current assets 88,391 75,655 87,680 Property and equipment, net

107,471 100,760 97,553 Operating lease right-of-use assets 13,547 13,555 13,394 Finance lease right-of-use assets, net 5,806 4,919 4,597 Goodwill 28,015 28,174 28,137 Other long-term assets 15,944 20,134 16,295 Total assets $ 259,174 $ 243,197 $ 247,656 LIABILITIES, REDEEMABLE NONCONTROLLING INTEREST, AND EQUITY

Current liabilities: Short-term borrowings $ 9,942 $ 372 $ 6,811 Accounts payable 61,049 53,742 57,263 Dividends payable 1,533 — 1,527 Accrued liabilities 26,132 31,126 27,443 Accrued income taxes 606 727 900 Long-term debt due within one year 2,806 4,191 5,458

Operating lease obligations due within one year 1,474 1,473 1,457 Finance lease obligations due within one year 688 567 549 Total current liabilities 104,230 92,198 101,408 Long-term debt 36,342 34,649 33,935 Long-term operating lease obligations 12,817 12,828 12,658 Long-term finance lease obligations

5,670 4,843 4,512 Deferred income taxes and other 14,304 14,688 14,760 Commitments and contingencies Redeemable noncontrolling interest 228 237 260 Equity: Common stock 269 269 270 Capital in excess of par value 4,929 4,969 4,817 Retained earnings 85,831 83,135 77,946

Accumulated other comprehensive loss (11,573) (11,680) (10,780) Total Walmart shareholders’ equity 79,456 76,693 72,253 Nonredeemable noncontrolling interest 6,127 7,061 7,870 Total equity 85,583 83,754 80,123 Total liabilities, redeemable noncontrolling interest, and equity $ 259,174 $ 243,197 $ 247,656 9 Walmart Inc.

Condensed Consolidated Statements of Cash Flows (Unaudited) Nine Months Ended October 31, (Amounts in millions) 2023 2022 Cash flows from operating activities: Consolidated net income $ 10,592 $ 5,483 Adjustments to reconcile consolidated net income to net cash provided by operating activities:
```
</details>

**RULE:** AGREE / OVERTURN

### B15. `E2CHK-bfc8d598b0f65dcf`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `NEUTRAL`
<details><summary>chunk text (2180 chars)</summary>

```
As of October 31, 2022, we had $213 million of gross unrecognized tax benefits, of which $35 million would reduce our valuation allowance, if recognized. The remaining $178 million would impact the effective tax rate, if recognized. Autodesk’s unrecognized tax benefits decreased by $8 million in the nine months ended October 31, 2022, due to the settlement of a German tax audit for tax years 2014-2016.

On August 16, 2022, the Inflation Reduction Act was signed into law. The Inflation Reduction Act contains a number of revisions to the Internal Revenue Code effective in taxable years beginning after December 31, 2022, including a 15% corporate minimum income tax and a 1% excise tax on corporate stock repurchases by publicly traded U.S. corporations. Autodesk is currently assessing the impact the Inflation Reduction Act will have on our consolidated financial statements.

In addition to our results determined under GAAP discussed above, we believe the following non-GAAP measures are useful to investors in evaluating our operating performance. For the three and nine months ended October 31, 2022 and 2021, our gross profit, income from operations, operating margin, net income, and diluted net income per share on a GAAP and non-GAAP basis were as follows (in millions except for operating margin and per share data):

Three Months Ended October 31, Nine Months Ended October 31, 2022 2021 2022 2021 (Unaudited) Gross profit $ 1,160 $ 1,018 $ 3,331 $ 2,869 Non-GAAP gross profit $ 1,186 $ 1,040 $ 3,407 $ 2,932 Income from operations $

256 $ 193 $ 712 $ 475 Non-GAAP income from operations $ 465 $ 365 $ 1,306 $ 976 Operating margin 20 % 17 % 19 % 15 % Non-GAAP operating margin 36 % 32 % 35 % 31 %

Net income $ 198 $ 137 $ 530 $ 408 Non-GAAP net income $ 369 $ 297 $ 1,042 $ 795 GAAP diluted net income per share $ 0.91 $ 0.62 $ 2.43 $ 1.84 Non-GAAP diluted net income per share

$ 1.70 $ 1.34 $ 4.78 $ 3.58

51 Reconciliation of GAAP Financial Measures to Non-GAAP Financial Measures (In millions except for operating margin and per share data): Three Months Ended October 31, Nine Months Ended October 31, 2022 2021 2022 2021 (Unaudited) Gross profit $ 1,160 $
```
</details>

**RULE:** AGREE / OVERTURN

### B16. `E2CHK-cecfe507af285466`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `NEUTRAL`; `guidance_direction` = `NONE`
<details><summary>chunk text (2740 chars)</summary>

```
In the first quarter of 2022, the Company changed the extent of matters and charges/benefits it includes within special items with respect to net costs for significant litigation. Previously, 3M included net costs, when significant, associated with changes in accrued liabilities related to respirator mask/asbestos litigation and PFAS-related other environmental matters, along with the associated tax impacts. The non-GAAP measure changes involved including net costs for litigation related to 3M's Combat Arms Earplugs, expanding net costs to include external legal fees and insurance recoveries associated with the applicable matters in addition to changes in accrued liabilities, and to include all such net costs for the applicable matters, not just when considered significant.

The discussion and tables below include information with respect to historical amounts adjusted for special items (non-GAAP measures) reflective of the changes in measure of segment operating performance and non-GAAP measures described above. Special items for the periods presented include:

Net costs for significant litigation: •

These relate to 3M's respirator mask/asbestos, PFAS-related other environmental, and Combat Arms Earplugs matters. Net costs include the impacts of changes in accrued liabilities, external legal fees, and insurance recoveries, along with associated tax impacts. Net costs related to respirator mask/asbestos and Combat Arms Earplugs matters are reflected as special items in the Safety and Industrial business segment while those associated with PFAS-related other environmental matters are primarily reflected as corporate special items in Corporate and Unallocated. With respect to 2019, the after-tax charge includes a reduction in tax expense related to resolution of tax treatment with authorities regarding the previously disclosed 2018 agreement reached with the State of Minnesota that resolved the Natural Resources Damages lawsuit.

In 2020, 3M recorded a pre-tax gain of $2 million ($1 million loss after tax) related to the sale of its advanced ballistic-protection business and recognition of certain contingent consideration and a pre-tax gain of $387 million ($304 million after tax) related to the sale of its drug delivery business.

In 2020, following the divestiture of substantially all of the drug delivery business, management approved and committed to undertake certain restructuring actions addressing corporate functional costs and manufacturing footprint across 3M in relation to the magnitude of amounts previously allocated/burdened to the divested business. As a result, 3M recorded a pre-tax charge of $55 million ($46 million after tax) and made a subsequent immaterial adjustment thereto.
```
</details>

**RULE:** AGREE / OVERTURN

### B17. `E2CHK-d1fd9daf1bcbb960`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `POSITIVE`; `guidance_direction` = `NONE`
<details><summary>chunk text (2691 chars)</summary>

```
Regulatory, connectivity and produced content expenses decreased by $109 million, or 18.3% year-over-year, primarily driven by delayed sports rights costs. Costs to service customers increased by $81 million, or 4.6% year-over-year, despite year-over-year residential and SMB customer growth of 6.3%

. In addition to custom

er growth and record transaction volume for new sales and service, the year-over-year increase in costs to service customers was driven by previously announced accelerated wage benefits for hourly field operations and call center employees and COVID-19 related flex time, partly offset by lower medical costs and a one-time payroll tax credit. While bad debt increased 5.0% year-over-year, bad debt in the second quarter benefited from the revenue reduction for Keep Americans Connected customers and better collections from other customers as a result of Federal stimulus under the CARES Act.

Marketing expenses decreased by $49 million, or 6.3% year-over-year, primarily driven by better media placement rates and a one-time payroll tax credit. 7 Other expenses decreased by $60 million, or 6.6% as compared to the second quarter of 2019 primarily driven by lower advertising sales expense, enterprise costs from the sale of Navisite, employee travel expense and insurance costs.

Second quarter mobile costs totaled $413 million, an increase of 48.6% year-over-year, and were comprised of device costs, customer acquisition costs, and service and operating costs. Adjusted EBITDA Second quarter Adjusted EBITDA of $4.5 billion grew by 7.3% year-over-year, reflecting growth in revenue and operating expenses of 3.1% and 0.6%, respectively. Second quarter cable Adjusted EBITDA grew by 6.7% year-over-year reflecting growth in cable revenue of 1.8% and a decline in cable operating expenses of 1.3%.

Net Income Attributable to Charter Shareholders Net income attributable to Charter shareholders totaled $766 million in the second quarter of 2020 , compared to $314 million

in the second quarter of 2019. The year-over-year increase in net income attributable to Charter shareholders was primarily driven by higher Adjusted EBITDA, a non-cash gain on financial instruments in the current year period versus a loss in the prior year period and lower depreciation and amortization, partly offset by higher tax expense.

Net income per basic common share attributable to Charter shareholders totaled $3.72 in the second quarter of 2020 compared to $1.41 during the same period last year. The increase was primarily the result of the factors described above in addition to a 7.5% decrease in weighted average common shares outstanding versus the prior year period.
```
</details>

**RULE:** AGREE / OVERTURN

### B18. `E2CHK-e95cce1305be9672`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `NEGATIVE`
<details><summary>chunk text (2526 chars)</summary>

```
Canadian Divestiture Activities

On September 5, 2024, we announced an agreement to sell our Canadian retail disposal group. The adjusted purchase price is approximately $148 million. We recorded a charge of $643 million for the three and six months ended September 30, 2024 in total operating expenses to remeasure the Canadian retail disposal group to fair value less costs to sell. The remeasurement adjustment includes a $15 million loss related to the accumulated other comprehensive loss balances associated with the disposal group. The transaction is anticipated to close in the second half of fiscal 2025, pursuant to the satisfaction of customary closing conditions, including receipt of regulatory approvals, as applicable.

As of September 30, 2024, we had $631 million of assets and $371 million of liabilities classified as “Assets held for sale” and “Liabilities held for sale,” respectively, in the Condensed Consolidated Balance Sheet related to the Canadian retail disposal group. Refer to

Financial Note 2, “Held for Sale ,” to the accompanying condensed consolidated financial statements included in this Quarterly Report for more information. Executive Summary: The following summary provides highlights and key factors that impacted our business, operating results, financial condition, and liquidity for the three and six months ended September 30, 2024:

• For the three months ended September 30, 2024 compared to the prior year period, revenues increased by 21%, gross profit increased by 6%, total operating expenses increased by 26%, and other income, net increased by $8 million; •

For the six months ended September 30, 2024 compared to the prior year period, revenues increased by 14%, gross profit increased by 5%, total operating expenses increased by 19%, and other income, net increased by $100 million. Refer to the “

Diluted earnings per common share attributable to McKesson Corporation decreased to $1.87 from $4.92 for the three months ended September 30, 2024 and decreased to $8.89 from $11.95 for the six months ended September 30, 2024 compared to the respective prior year periods;

36 Table of Contents MD&A Index McKESSON CORPORATION FINANCIAL REVIEW (CONTINUED) (UNAUDITED) • In the second quarter of fiscal 2025, we onboarded a new strategic partner within our U.S. Pharmaceutical segment; • Total operating expenses for the three and six months ended September 30, 2024 includes fair value remeasurement charges of $643 million related to our Canadian retail disposal group;
```
</details>

**RULE:** AGREE / OVERTURN

### B19. `E2CHK-f27bf6c2b45ee4b6`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `NEUTRAL`
<details><summary>chunk text (1600 chars)</summary>

```
For the nine months ended September 30, 2025, cash used in financing activities was $652.9 million primarily due to $1.5 billion of share repurchases in the first three quarters of 2025; a $1.0 billion cash payment for the settlement of the outstanding 2025 Convertible Notes that matured in March 2025; and net repayments under Warehouse Facilities borrowings of $1.0 billion. These were partially offset by approximately $2.2 billion of net proceeds related to the issuance of the 2030 and 2033 Senior Notes in the third quarter of 2025, increases in customer funds of $620.8 million and interest-bearing deposits of $81.2 million.

For the nine months ended September 30, 2024, cash provided by financing activities was $1.2 billion primarily due to approximately $2.0 billion of net proceeds related to the issuance of the 2032 Senior Notes in the second quarter of 2024, a change in customer funds of $763.4 million, and proceeds from issuances of common stock from the exercise of options and purchases under our employee share purchase plan of $88.1 million. These were partially offset by repurchases of common stock of $987.2 million as well as net repayments under Warehouse Facilities borrowings of $647.7 million.

There were no significant changes in our critical accounting estimates during the quarter ended September 30, 2025 compared to those previously disclosed in “Critical Accounting Policies and Estimates” in “Management’s Discussion and Analysis of Financial Condition and Results of Operations” included in our Annual Report on Form 10-K for the year ended December 31, 2024.
```
</details>

**RULE:** AGREE / OVERTURN

### B20. `E2CHK-fccdba6e4a09e1b0`
**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** `sentiment` = `NEUTRAL`; `guidance_direction` = `NONE`
<details><summary>chunk text (908 chars)</summary>

```
55,284 $ 4,491,924 Add: Other expense (income) (8,066) (44,771) (88,829) 510,568 368,902 Provision for (benefit from) income taxes 382,245 182,103 223,605 (15,948) 772,005 Depreciation and amortization of property, equipment and intangibles 74,602 83,505 85,188 93,387 336,682 Stock-based compensation expense 119,209

150,392 152,062 153,789 575,452 Adjusted EBITDA $ 2,165,437 $ 1,812,180 $ 1,770,268 $ 797,080 $ 6,544,965 As of December 31, 2022 Non-GAAP LTM EBITDA reconciliation: Total debt $ 14,353,076 Add: Debt issuance costs 78,824 Less: Cash, cash equivalents and short-term investments

(6,058,452) Net debt $ 8,373,448 LTM EBITDA (Net debt / LTM Adjusted EBITDA) 1.3 As Reported Currency Translation Adjustment Adjusted Revenue at 2021 Rates Reported Change Constant Currency Change Non-GAAP reconciliation of reported and constant currency revenue growth for the quarter ended December 31, 2022:
```
</details>

**RULE:** AGREE / OVERTURN

## HOW TO RECORD

Two files, in this directory, exactly these key sets (§10.2.3 — `analyze_g2.py` hard-fails on anything else):

`data/f4/g2/owner_rulings.json` — one object per PART A row you rule:

```json
[
  {
    "chunk_id": "E2CHK-...",
    "field": "sentiment",
    "correct_label": "NEUTRAL",
    "note": "owner ruling 2026-09-07 (A1): ..."
  }
]
```

`correct_label` **is** the reference: put the stored label there for STORED-RIGHT, the adjudicator's `correct_label` for ADJUDICATOR-RIGHT, or your own value for OTHER. There is no verdict word. A `red_flags` row in this file is a hard failure (§5.3: red_flags never escalates).

`data/f4/g2/probe_rulings.json` — one object per PART B row:

```json
[
  {
    "chunk_id": "E2CHK-...",
    "ruling": "agree",
    "note": "owner ruling 2026-09-07"
  }
]
```

`ruling` ∈ `{agree, disagree}` — `disagree` = OVERTURN.

Then re-run, from the repo root:

```
python3 data/f4/g2/analyze_g2.py
```

It re-reads both files, restamps the stage as `owner_ratified`, and regenerates `results_g2.json` / `report_g2.md`. If ≥ 2 probe rows are overturned, run the one pre-committed sweep (§5.5) and re-run it once more; the stage then reads `owner_ratified_escalated`.

**Until you rule, every number in this packet is model consensus** — a Claude-family rater and a Claude-family adjudicator agreeing with (or overturning) a Qwen student, scored mechanically against rubric v1.2 as your 2026-08-27 policy rulings interpret it. It is not human validation of ground truth, and the estimate is plausibly optimistic for the reason in §12.1: the rater's family is the teacher's family, so teacher error the student memorized is invisible to it. Your rulings supersede the adjudicator on exactly the rows you rule, and nothing else changes.
