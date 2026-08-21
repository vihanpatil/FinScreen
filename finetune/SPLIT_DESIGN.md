# SPLIT_DESIGN — Week 4 held-out eval split

> **✅ CURRENT** — the split was regenerated after the re-label (2026-08-11);
> all 6,747 rows share one labeling config. **§5 and §6 below were
> recomputed directly from the live `finetune/splits/{train,eval}.parquet`
> on 2026-08-18** and now match them; the earlier provisional/stale block
> that used to sit in §5 has been replaced. Headline: train **5,736** /
> eval **1,010** (15.0%). A post-assignment repair pass enforces that no
> label may exceed 35% eval share or fall below a training floor, moving
> whole components back to train when it would (which preserves the §2
> leakage guarantee by construction). The earlier `guidance:RAISED`
> starvation (12 training examples) is fixed: **27 train / 7 eval**.
>
> The split itself is a **frozen artifact** — §5/§6 were recomputed from the
> parquets, not by re-running `split.py`.

`split.py` carves `finetune/splits/{manifest,train,eval}.parquet` from
`data/labels.parquet` before any training artifact exists. This doc records
the leakage-safety rule, the company/time tradeoff analysis (with real
counts), the decision, and its costs — honestly, including where the result
came out worse-balanced than intended.

## 1. Exclusion predicate (and a documentation discrepancy found along the way)

Rows are excluded from both train and eval via the predicate
`parse_ok & schema_valid`, not by hardcoding a chunk_id. Today this drops
exactly **1 row**, `CHK-8e69547e0900a8dd`, and `split.py` asserts that count
so a future re-labeling run that changes the failure set fails loudly
instead of silently mislabeling the split. `check_leakage.py` re-derives and
re-checks the same predicate independently.

**Resolved**: this was previously flagged as an open discrepancy between
`data/full_run_report.md`'s `stop_reason=refusal` claim and the row's own
columns, which show a truncated/malformed JSON string (`parse_error`:
`"JSON parse error: Unterminated string starting at: line 1 column 64 (char
63)"`, `schema_valid=False`) — a signature that on its face looked more like
an ordinary truncation than a content refusal. Primary API evidence now
resolves this: the raw Batch API response shows `stop_reason=refusal`,
`stop_details.category='bio'`, with 293 output tokens of partial JSON before
the refusal — a genuine mid-stream safety refusal, not a truncation.
`section_type` for this row is `MDA`. A re-run of this chunk would refuse
again under the same prompt/content, so this is not a fixable
config-delivery artifact like the 500-token/adaptive-thinking rows discussed
elsewhere. The exclusion predicate used (`parse_ok & schema_valid`) is
correct and does not depend on this question either way — the row has no
usable labels regardless of the refusal/truncation distinction, and is
unchanged by this resolution.

## 2. Leakage rule: connected components over shared paragraphs / filings

A chunk's text is built (`chunk.py`) from deduplicated paragraphs that can
recur, verbatim, across many filings. Each chunk row already carries the
union of every filing any of its constituent paragraphs appears in anywhere
in the corpus, in `source_accession_numbers` (computed once, at chunk-build
time, by `chunk.py`'s `flush()` — not re-derived here).

`split.py` builds an undirected graph over `chunk_id`s:
- edge if two chunks share any `paragraph_id`
- edge if two chunks share any `source_accession_number`

and assigns whole **connected components** to train or eval — never
individual chunks — so no recurring paragraph or overlapping source filing
can straddle the boundary. `check_leakage.py` verifies this directly (by
paragraph_id and by accession_number) against the actual `train.parquet` /
`eval.parquet` outputs, not just by trusting the component logic.

## 3. Finding: components are (almost) companies, not an artifact of the algorithm

Before deciding whether to *additionally* split by company, the actual
component structure was inspected. Result: **74 of 89 components have more
than 1 chunk, and the large ones are, without exception, single-ticker.**
The 20 largest components by size are each 100% one ticker (JPM 736, GS 506,
BAC 476, PFE 347, KO 291, CSCO 287, PG 282, MRK 272, NVDA 251, WMT 238, COP
228, GOOGL 211, XOM 209, MSFT 201, OXY 197, CVX 169, V 158, UNH 149, JNJ 146,
MA 144, and so on for every ticker in the universe).

This is the mechanical consequence of `chunk.py`'s dedup: risk-factor and
MD&A boilerplate is reused, near-verbatim, across a *company's own*
successive quarterly/annual filings far more than across different
companies' filings (25 unrelated issuers rarely share exact filing prose;
one issuer reusing its own risk-factor register year over year is normal
filer practice). So the leakage-safe connected-component graph, built purely
from paragraph/accession overlap with no ticker input at all, ends up
re-deriving something very close to a company partition on its own for most
tickers.

**Consequence for the company-vs-random decision below: it's largely already
decided by the leakage rule, not a free choice.** A handful of small
companies (SLB 90 total chunks, AAPL 118, MCD 120) and various small residual
components are the only real flexibility available; the big single-company
components are effectively atomic and go to one side or the other as a
whole.

## 4. Decision: connected-component split, stratified for rare labels, NOT independently company- or time-partitioned

Given §3, an explicit "split by company" policy and "don't split by company"
policy converge for most of the universe regardless — the graph already
forces most large components to be single-company. What's left as an actual
design choice is: **which** components (≈ which companies, for the big
ones) go to eval, chosen to preserve rare-label representation, vs. a pure
random/company-blind choice that could easily zero out rare guidance labels
in eval by chance (e.g. `WITHDRAWN` has exactly 1 occurrence in the whole
corpus — it cannot be represented in eval no matter what is done, and
`LOWERED`/`MAINTAINED`/`RAISED` have only **14/34/34** occurrences total in
the final `data/labels.parquet` (83 non-`NONE` in all), spread unevenly by
ticker).

`stratified_component_split()` in `split.py`:
1. Orders rare-label categories rarest-count-first (guidance labels, then
   the 6 red-flag categories, then distress-tier categories informationally).
2. For each, greedily assigns the **smallest** as-yet-unassigned components
   containing that label to eval, until a target fraction of that label's
   total occurrences is reached (20% for guidance labels, 15% for red-flag
   and distress categories) — smallest-first specifically to avoid a
   cheap-on-label-count-but-expensive-in-chunks outcome where satisfying one
   label's quota means dumping one giant single-company component (500+
   chunks) into eval.
3. Fills the remaining eval budget (target 15% of total chunks) with
   remaining components, again smallest-first with a seeded random
   tie-break, to spread eval across as many distinct components/companies
   as the budget allows rather than a coin-flip that could concentrate it.

Fixed seed (`SEED = 42`) throughout → reproducible.

### What this bought vs. an unweighted random component split

An earlier (unweighted-random) version of this same algorithm was run first
and produced a visibly worse outcome: `RAISED`/`MAINTAINED`/`LOWERED` in eval
at 31–50% (fine), but ticker representation was severely lopsided — 16 of 25
tickers had **zero** eval presence, while `GOOGL` and `PG` landed **100% in
eval, 0% in train**. The smallest-first weighting materially improved this
(see current run below) without changing the leakage guarantee at all — it's
purely which side each component lands on.

## 5. Actual output (seed=42) — recomputed from the live split, 2026-08-18

**Source of these numbers:** read directly out of
`finetune/splits/train.parquet` and `finetune/splits/eval.parquet` on
2026-08-18. `split.py` was **not** re-run — the split is a frozen artifact
and this section is a report of it, not a fresh draw.

```
Final split: train=5736 (85.0%), eval=1010 (15.0%)   [6,746 usable rows]
```

Per-label chunk counts (train / eval / eval-fraction):

| Label | Train | Eval | Eval frac |
|---|---|---|---|
| guidance:RAISED | 27 | 7 | 20.6% |
| guidance:MAINTAINED | 27 | 7 | 20.6% |
| guidance:LOWERED | 11 | 3 | 21.4% |
| guidance:WITHDRAWN | 1 | 0 | 0.0% (n=1 total, not evaluable) |
| redflag:DEMAND_WEAKNESS | 1115 | 203 | 15.4% |
| redflag:SUPPLY_INPUT_CONSTRAINT | 457 | 150 | 24.7% |
| redflag:TRADE_POLICY_EXPOSURE | 592 | 107 | 15.3% |
| redflag:IMPAIRMENT_WRITEDOWN | 859 | 156 | 15.4% |
| redflag:MARGIN_COST_PRESSURE | 1491 | 245 | 14.1% |
| redflag:LEGAL_REGULATORY_ACTION | 1955 | 302 | 13.4% |
| distress:GOING_CONCERN | 0 | 0 | n/a (zero support corpus-wide) |
| distress:ACCOUNTING_RESTATEMENT | 2 | 0 | 0.0% (n=2 total, informational only) |
| distress:LIQUIDITY_STRESS | 120 | 40 | 25.0% |

Every label's eval share is at or under the 35% cap. Red-flag counts are
per-chunk category presence (a chunk counts once per category regardless of
modality).

Section-type counts:

| section_type | train | eval | eval frac |
|---|---|---|---|
| MDA | 3664 | 297 | 7.5% |
| RISK_FACTORS | 1471 | 135 | 8.4% |
| EX99_PRESS_RELEASE | 601 | 570 | 48.7% |
| 8K_BODY | 0 | 8 | 100.0% |

**The `EX99_PRESS_RELEASE` split is genuinely lopsided (48.7% eval), and
that is not a typo.** It falls out of §3: press-release components are
small and are exactly what the rare-guidance and rare-red-flag quotas pull
into eval first, so a disproportionate share of that section type lands
there. It does not violate the leakage rule or the per-label 35% cap
(which is enforced on labels, not on `section_type`), but any per-section
eval metric should be read with the base rate in mind.

Ticker counts (train / eval), all 25:

| Ticker | Train | Eval | Eval frac |
|---|---|---|---|
| AAPL | 0 | 118 | 100.0% |
| ABBV | 54 | 133 | 71.1% |
| BAC | 476 | 173 | 26.7% |
| COP | 228 | 5 | 2.1% |
| CSCO | 291 | 7 | 2.3% |
| CVX | 169 | 36 | 17.6% |
| GOOGL | 211 | 0 | 0.0% |
| GS | 509 | 4 | 0.8% |
| HD | 142 | 22 | 13.4% |
| JNJ | 146 | 20 | 12.0% |
| JPM | 736 | 0 | 0.0% |
| KO | 291 | 114 | 28.1% |
| MA | 144 | 37 | 20.4% |
| MCD | 0 | 120 | 100.0% |
| MRK | 277 | 6 | 2.1% |
| MSFT | 209 | 0 | 0.0% |
| NVDA | 273 | 5 | 1.8% |
| OXY | 197 | 80 | 28.9% |
| PFE | 347 | 8 | 2.3% |
| PG | 282 | 0 | 0.0% |
| SLB | 0 | 90 | 100.0% |
| UNH | 149 | 32 | 17.7% |
| V | 158 | 0 | 0.0% |
| WMT | 238 | 0 | 0.0% |
| XOM | 209 | 0 | 0.0% |

## 6. Costs and limitations — stated plainly, not glossed over

- **`WITHDRAWN` guidance cannot be evaluated at all.** n=1 in the entire
  corpus; it is in train. Any eval report must say "0 examples, not
  evaluable" for this class rather than omitting it or implying 0/0 = some
  accuracy.
- **`8K_BODY` has 0 training examples and only 8 eval examples**, all from 2
  of 25 tickers (BAC, CVX). This section_type is functionally unusable for
  either training a dedicated signal or reporting a meaningful per-class
  eval metric — it will be reported as `n=8, not meaningfully evaluable`,
  not folded into a headline number that implies otherwise.
- **7 of 25 companies have zero eval presence (GOOGL, JPM, MSFT, PG, V,
  WMT, XOM), and 3 have zero train presence (AAPL, MCD, SLB)** — recomputed
  from the live split 2026-08-18. (UNH and NVDA are present on **both**
  sides; an earlier draft of this bullet named them as train-absent, which
  was wrong in both directions.) This is the direct cost of §3: the leakage rule forces
  large single-company components, and satisfying rare-label eval quotas
  with a reasonable overall eval-budget both push toward whole companies
  moving as a unit. A genuinely random, unweighted chunk-level split would
  not have this property, but would violate the leakage rule (§2) if used
  naively.
- **This is honestly closer to a company split than a random split, for
  most of the universe, whether or not that was the stated goal** — worth
  restating plainly: the connected-component leakage rule, not a deliberate
  policy choice, is what produces this. A deliberate, explicit company
  split (e.g. holding out 4-5 whole companies) was considered and would
  have produced a similarly-shaped result with less algorithmic complexity,
  at the cost of even less control over rare-label representation (some
  rare guidance labels are concentrated in specific companies — see the
  per-ticker breakdown in `split.py`'s own output — an unweighted company
  choice could easily zero out `LOWERED` or `RAISED` from eval entirely).
  The stratified approach here is a deliberate compromise between those two
  failure modes, not a claim that either pure policy would be better.
- **Relative to Week 5's walk-forward design (`DISCOVERY.md` §5):** Week 5's
  backtest evaluation is explicitly time-ordered (expanding window, no
  random shuffle) specifically to avoid a model being evaluated on data from
  a company/period it implicitly saw patterns from during training. This
  Week 4 split does **not** enforce a time cutoff — `home_filing_date` spans
  essentially the same range on both sides (train 2023-08-16 → 2026-08-07;
  eval 2023-08-15 → 2026-08-07) (a chunk
  from company X's 2024 filing and company X's 2026 filing land in the same
  component and thus the same split side purely because they share
  boilerplate, regardless of date order). **This is a real limitation,
  stated plainly**: this split answers "does the fine-tuned extractor
  generalize to unseen text/companies," not "does it generalize to the
  future" — that second, stronger claim is exactly what Week 5's
  walk-forward harness is for, on a different axis (numeric/text feature
  performance over time), and this split should not be read as already
  covering it.
- **Universe size (25 companies) is a hard ceiling on how much both
  company-level and stratified approaches can achieve simultaneously** —
  only **11** companies carry all 83 non-`NONE` guidance labels (ABBV, COP,
  HD, JNJ, KO, OXY, PFE, PG, UNH, WMT, XOM); asking for both broad
  ticker balance and solid rare-label eval coverage from 25 companies is
  asking for more degrees of freedom than the universe has. The distribution
  above is the actual achieved compromise, not an idealized target.

## 7. Reproducibility

`SEED = 42` in `split.py`, no other source of randomness. Re-running
`python3 split.py` from a clean `finetune/splits/` produces byte-identical
output as long as `data/labels.parquet` is unchanged (verified by inspection
of the deterministic union-find + sort-based assignment logic — no
non-deterministic dict/set iteration order is relied on for output content,
only for internal graph traversal, which doesn't affect final component
membership).
