# S4 completion report — fundamentals, systematic re-ingest

**Stage:** S4. **Agent:** data-engineer (Opus). **Date:** 2026-08-24.
**Status: DONE.** Brief: `data/f2/status/S4_brief.md`. Scope implemented:
`data/f2/F2_SPEC.md` §5.2, §5.3, §5.4 + the §8.2 "S4" test block + the §8.1
row-3 re-pins, **then the main session's 2026-08-24 "substitutes-only
families + explicit dominance" ruling** (`F2_PROGRESS.md` §5), recorded as
F2_SPEC §5.5 amendment A1.

**Read §9 (SECOND PASS) for the current numbers.** §§1–8 are the first
pass, preserved as written: they are the measurement that produced the
finding the ruling answers. Where the two disagree, §9 wins — the first
pass's headline (34% UNRESOLVED, 22 BLOCKERs, MIGRATION never firing) is
superseded by 16% / 17 justified / 13.

**Network: ZERO live GETs.** No `EdgarClient` request path ran at any point.
Every measurement below comes from the 25 already-cached companyfacts
documents in `data/raw/companyfacts/` (mtimes unchanged; nothing under
`data/raw/` was created or modified this session). No Anthropic API use.

**E1's frozen record is untouched:** `data/fundamentals.parquet` (Aug 18
12:08), `data/filings_metadata.db` (Aug 18 12:08), `data/universe.csv`
(Aug 10), `data/labels.parquet` (Aug 11) all carry their pre-session mtimes.
E2's fundamentals now write to a **new** path, `data/fundamentals_e2.parquet`
(§5, clarification 1), and `run()` raises if pointed at either E1 artifact.

**Parallel-run discipline honoured:** `F2_PROGRESS.md` not edited;
`ingest_metadata.py`, `edgar_client.py`, `ingest_prices.py`,
`price_client.py` and their test files not opened for writing (imported
read-only); the full suite was NOT run — only `test_ingest_fundamentals.py`,
`test_pit.py`, and a read-only re-run of S2's `test_ingest_metadata_universe.py`
(45 passed) to confirm S4 did not break the module that imports mine.

---

## 1. Test counts (exact)

| file | collected | passed | failed |
|---|---|---|---|
| `test_ingest_fundamentals.py` | **70** | **70** | 0 |
| `test_pit.py` | 5 | 5 | 0 |
| `test_ingest_metadata_universe.py` (S2's, read-only sanity) | 45 | 45 | 0 |

`test_ingest_fundamentals.py` went 15 → 70 tests. All offline; no socket is
opened anywhere. `pyflakes` clean on `ingest_fundamentals.py`,
`test_ingest_fundamentals.py`, `data/f2/fixtures/build_fixtures.py`.

```bash
python3 -m pytest test_ingest_fundamentals.py test_pit.py -q   # 75 passed
```

## 2. Files touched

**Modified**

| path | what |
|---|---|
| `ingest_fundamentals.py` | `CONCEPT_FAMILIES` (10 families / 25 tags) replaces the flat 13-concept `CONCEPTS` list, which survives only as the deduplicated `(taxonomy, tag)` union the fetch loop iterates. The three hand-curated maps + `REVENUE_CONCEPTS` / `CORE_NON_REVENUE_CONCEPTS` / `MIN_QUARTERLY_COVERAGE_*` / `revenue_alias_report()` are deleted. New: `is_operating_form()`, `ConceptResolution`, `classify_family()`, `classify_universe()`, `resolution_problems()`, `SectorBlocker`, `sector_blockers()`, `blocker_problems()`, `print_sector_blockers()`, `print_resolution_summary()`, `concept_resolution_frame()`, `write_concept_resolution()`. `validate_fundamentals()` keeps its name/signature and is now a 3-line wrapper over the classifier. `run()` gained `output_parquet` / `resolution_csv` parameters, prints BLOCKERs first, writes the resolution CSV, and refuses E1's DB **and** E1's parquet. |
| `test_ingest_fundamentals.py` | Rewritten: 4 extraction + 2 `target_quarters` tests kept verbatim; the 9 hand-map/coverage-band tests replaced by family pins, the five classifier states, the operating-form filter, the sector-blocker boundary, the CSV contract, `run()` ordering, and the acceptance tests below. |

**New**

| path | what |
|---|---|
| `data/f2/fixtures/companyfacts_CIK*.json` (7 files, 564 KB total) | Real companyfacts slices for the seven acceptance CIKs — only the families each case is about, only facts filed ≥ 2015-01-01, only the 8 fields `extract_concept_facts()` reads. Nothing renamed or invented. |
| `data/f2/fixtures/build_fixtures.py` | Regenerates those slices from `data/raw/companyfacts/`. Offline, deterministic, in-repo so the fixtures are not mystery blobs. |
| `data/f2/concept_resolution_preview_25.csv` | The §5.3 artifact's schema, run over the **25 cached companies only** (250 rows). Deliberately NOT written to `data/f2/concept_resolution.csv` — that path is the 244-member artifact and belongs to S6's fundamentals segment; a partial file at the canonical path is exactly the kind of thing a later reader consumes as if it were complete. |

`data/f2/concept_resolution.csv` therefore **does not exist yet**; the code
that writes it is implemented, tested, and wired into `run()`.

## 3. The three deleted hand-curated maps, preserved verbatim

Copied byte-for-byte out of `git show HEAD:ingest_fundamentals.py` (they were
untouched by S1–S3, so HEAD is their final E1 state), including their
comments, which carry the E1 evidence.

```python
# Concepts that are legitimately, structurally absent for large commercial
# banks (JPM, BAC, GS) -- determined by inspecting what these three actually
# report in companyfacts (confirmed zero rows across their ENTIRE history,
# not just the window -- see build_fundamentals()'s cached raw JSON):
#   - OperatingIncomeLoss: banks' income statements don't have a GAAP
#     "operating income" line the way industrials do (net interest income +
#     noninterest income - noninterest expense doesn't map onto this one
#     us-gaap tag).
#   - CashAndCashEquivalentsAtCarryingValue: banks report cash position under
#     bank-specific tags (e.g. CashAndDueFromBanks, InterestBearingDeposits*)
#     which are out of this ingestion's fixed concept set by design (adding
#     bank-specific tags would be scope creep on a 25-company universe where
#     only 3 are banks).
# A missing core concept for one of these three tickers is downgraded from
# FATAL to WARN by this named exemption; every other ticker still FATALs on
# total absence (unless it separately qualifies via the general
# structurally-absent / migrated-before-window logic below, which turned out
# to also cover several NON-bank concept absences -- see the run report).
BANK_TICKERS_MISSING_INDUSTRIAL_CONCEPTS = {"JPM", "BAC", "GS"}
BANK_EXEMPT_CONCEPTS = {"OperatingIncomeLoss", "CashAndCashEquivalentsAtCarryingValue"}

# Verified (not guessed) mid-window GAAP-tag migrations: the company switched
# away from this ingestion's fixed concept to a real alternate us-gaap tag
# DURING the corpus window (as opposed to the more common case of having
# migrated years before the window even started, which the general
# structurally-absent/migrated-before-window logic already handles cleanly).
# Each entry was confirmed by reading the actual in-window rows for that
# (ticker, concept) pair and the candidate alt tag's presence in the same
# company's raw companyfacts JSON -- not inferred from the low percentage
# alone. The alt tag is NOT pulled into this ingestion (out of the
# task-specified fixed concept list -- adding it would be undocumented scope
# expansion); this map exists purely to make an already-low coverage number
# an explained WARN instead of an unexplained FATAL.
KNOWN_MIDWINDOW_MIGRATIONS: dict[tuple[str, str], str] = {
    # MA's only in-window NetIncomeLoss rows (3 of them) come from DEF 14A
    # proxy statements' compensation tables (annual figures for say-on-pay
    # disclosure), NOT from any 10-K/10-Q in the window -- MA's operating
    # filings tag net income under ProfitLoss instead. True 10-K/10-Q
    # coverage under NetIncomeLoss for MA in this window is actually 0/12,
    # not 3/12 -- worse than the raw number suggests, flagged explicitly.
    ("MA", "NetIncomeLoss"): "ProfitLoss (also: the 3 in-window rows that DO "
        "exist are from DEF 14A proxy filings, not 10-K/10-Q -- true "
        "operating-filing coverage is 0/12, not 3/12)",
    # OXY's own in-window NetIncomeLoss rows run from 2023-11-07 through
    # 2024-05-07 filings only (10-K/10-Q) -- confirmed no later occurrence in
    # the window; OXY's companyfacts confirms ProfitLoss is populated.
    ("OXY", "NetIncomeLoss"): "ProfitLoss",
    # Same pattern: SLB's in-window OperatingIncomeLoss rows run only through
    # its 2024-04-24 10-Q; ProfitLoss is populated afterward.
    ("SLB", "OperatingIncomeLoss"): "ProfitLoss",
    # CVX's in-window CashAndCashEquivalentsAtCarryingValue rows run only
    # through its 2024-08-07 10-Q filing; CVX fully adopted the combined
    # restricted-cash tag afterward (confirmed: 48 in-window rows under the
    # alt tag vs. this ingestion's fixed concept list not including it).
    ("CVX", "CashAndCashEquivalentsAtCarryingValue"):
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
}
```

Also deleted with them (same commit, same reason — they only existed to
support the per-ticker exemptions): `MIN_QUARTERLY_COVERAGE_CLEAN/WARN`, the
`REVENUE_CONCEPTS` / `CORE_NON_REVENUE_CONCEPTS` split, `revenue_alias_report()`,
and the checks `concept_structurally_absent`, `concept_tag_migrated_before_window`,
`concept_unexplained_gap`, `concept_quarterly_coverage_partial`,
`concept_quarterly_coverage_low`, `concept_quarterly_coverage_midwindow_migration`,
`revenue_concept_present`, `revenue_alias_consistency`. Revenue is now a family
like any other: its absence is `ABSENT`, its multi-alias case is `OVERLAP` or
`MIGRATION`, decided per company from data instead of from a ticker list.
**No ticker appears in any code path in `ingest_fundamentals.py` any more** —
pinned behaviourally by `test_classification_does_not_depend_on_the_display_label`.

## 4. What the classifier does with every deleted case (MEASURED, from the fixtures)

Real per-company coverage window for all seven: `2015-07-01 .. 2026-08-31`,
**44 reportable quarters** (they are all current hybrid136 members).

| E1 hand-map entry | classifier verdict | evidence |
|---|---|---|
| `BANK_EXEMPT_CONCEPTS` cash, **JPM** | `OVERLAP` → UNRESOLVED, **not ABSENT** | `CashAndDueFromBanks` **44/44 (100%)**, restricted-cash 36/44 (82%), old cash tag 10/44 |
| … **BAC** | `OVERLAP` → UNRESOLVED, not ABSENT | `CashAndDueFromBanks` 44/44, restricted-cash 36/44, old cash tag 21/44 |
| … **GS** | `OVERLAP` → UNRESOLVED, not ABSENT | `CashAndDueFromBanks` 44/44, old cash tag 44/44, restricted-cash 23/44 |
| `BANK_EXEMPT_CONCEPTS` operating income, **JPM / BAC / GS** | **`SINGLE` → resolved** | `IncomeLossFromContinuingOperationsBeforeIncomeTaxes…` 44/44 for all three — the exemption list is fully superseded here |
| `("MA","NetIncomeLoss")` → ProfitLoss | **`SINGLE` → resolved on `ProfitLoss`** (44/44) | and `NetIncomeLoss` contributes **0** covered quarters: its only in-window rows are 5 DEF 14A rows filed 2026-04-27 — trap (c) reproduced mechanically, pinned by a test that relabels them to `10-K` and watches the tag reappear |
| `("OXY","NetIncomeLoss")` → ProfitLoss | `OVERLAP` → UNRESOLVED | `NetIncomeLossAvailableToCommonStockholdersBasic` 44/44, `ProfitLoss` 41/44, `NetIncomeLoss` 33/44 |
| `("SLB","OperatingIncomeLoss")` → ProfitLoss | `OVERLAP` → UNRESOLVED | `OperatingIncomeLoss` **35/44** (stops mid-window, exactly as E1 recorded) alongside `IncomeLossFromContinuingOperations…` 44/44 — concurrent, not sequential, so not a MIGRATION. (Note the E1 map's target, `ProfitLoss`, is a **net-income** tag and is not in the `operating_income` family at all; §8.2's "SLB → MIGRATION to ProfitLoss" prediction is internally inconsistent with §5.2's table.) |
| `("CVX","CashAndCashEquivalents…")` → restricted-cash tag | **`SINGLE` → resolved on `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents`** (40/44) | old tag 31/44 — the hand map's target chosen from data, no ticker named |

**Every hand-map case is now *seen*: the alternate tag is ingested, found,
and counted, and no case is ABSENT or hand-exempted.** Five of the ten
(cik, family) acceptance pairs resolve outright — bank operating income ×3,
MA net income, CVX cash. The other five fail **loudly** as `OVERLAP` instead
of being silently resolved to whichever tag a human once wrote down, which is
the stricter behaviour §5.3 asks for ("UNRESOLVED never resolves stale…
there is no fallback to 'the tag with the most rows'").

**Where §8.2's predicted states differ from measurement, measurement wins and
is pinned.** §8.2 predicted `MIGRATION`/`SINGLE` for JPM/BAC/GS cash, MA/OXY
net income, SLB operating income and CVX cash. Four of those predictions
hold (MA, CVX, and the bank operating-income rows); the JPM/BAC/GS cash,
OXY and SLB predictions do not, because a second family tag covers the same
quarters — verified over both the E2 window and E1's 12-quarter window, so it
is structural, not a window artifact. §5.3's tabled conditions admit no
reading under which they resolve; the S1 pass measured tag *availability*
(n/25) but never ran the classifier, so those state predictions were
untested. The acceptance tests assert the measured state **plus** the
load-bearing invariants (alt tag found with real coverage; never `ABSENT`;
`resolved_tags == []` for every UNRESOLVED pair).

## 5. Deviations from spec — none in substance; five clarifications recorded

None of these changes a ratified ruling, a threshold, a state definition, or
a family's tags. Each is a place the spec was silent or self-inconsistent.

1. **E2 output path `data/fundamentals_e2.parquet`.** The spec names
   `data/f2/concept_resolution.csv` but never names the E2 fundamentals
   parquet; the brief states `data/fundamentals.parquet` is E1's. Applied the
   §1.4 DB discipline verbatim: new file, E1's frozen, `run()` refuses E1's
   path. **Two follow-ups for the main session:** (a) `.gitignore` (shared,
   already modified by other stages — deliberately not edited by me) does not
   exclude it, and §5.4 estimates 25–60 MB; (b) `features.py` reads
   `data/fundamentals.parquet` and is F5's to re-point.
2. **The (0%, 40%) coverage band.** §5.3 defines PARTIAL as [40%, 75%) and
   leaves (0%, 40%) unnamed. A family with a couple of stray in-window
   quarters is not ABSENT (it has rows) and cannot resolve, so it is reported
   as `PARTIAL` with its real coverage number, and the FATAL message says
   explicitly that it sits below the 40% floor. Both bands are UNRESOLVED, so
   severity, the CSV and the blocker aggregation are unaffected.
3. **Blocker threshold is strictly greater than 20%.** §8.2's boundary test
   (21% fires / 19% does not) fixes the direction; exactly 20% does not fire.
   Pinned by three tests.
4. **`revenue_concept_present` / `revenue_alias_consistency` are subsumed,
   not silently dropped.** They become the revenue family's `ABSENT` and
   `OVERLAP`/`MIGRATION` states. Net severity change: E1 WARNed on multiple
   in-window revenue aliases (HANDOFF §2a trap (d)); E2 makes an overlapping
   pair a FATAL. That is the direction §5.3 mandates.
5. **`tags` in the CSV is the resolution, not the observation.** For `SINGLE`
   it is the one tag that cleared the bar; for `MIGRATION` the chronological
   sequence; for UNRESOLVED states the tags seen, with `severity=UNRESOLVED`
   next to them and `resolved_tags == []` on the object. Per-tag coverage
   detail lives in the FATAL message and `ConceptResolution.tag_coverage`,
   because §5.3 fixes the CSV's seven columns.

## 6. THE FINDING THAT NEEDS A RULING (§5.3 says it is ruled here)

Preview over the **25 cached companyfacts documents** (all 25 are hybrid136
members; the 244-member run is S6's). 250 (cik, family) pairs:

| | pairs |
|---|---|
| resolved — `SINGLE` 164, `MIGRATION` **0** | **164** |
| UNRESOLVED — `OVERLAP` | **78** |
| UNRESOLVED — `PARTIAL` | 3 |
| UNRESOLVED — `ABSENT` | 5 |
| **UNRESOLVED total** | **86 / 250 = 34%** |

**22 of the 50 (sector × family) cells are BLOCKERs**, including
`financials/cash` 5/5, `tech/liabilities` 5/5, `energy/net_income` 5/5.
(Sector denominators are 5 here by construction — E1's universe is 5 tickers
× 5 sectors — so the *fractions* will move at 244 members; the *cause* will
not.)

The cause is concentrated in six tag pairs, all of which are **family
members that are not economic substitutes**, not filer noise:

| n | family | the tags that both clear 75% |
|---|---|---|
| 19 | `liabilities` | `Liabilities` + `LiabilitiesAndStockholdersEquity` — the second is total liabilities **plus equity**, i.e. total assets |
| 16 | `cash` | `CashAndCashEquivalentsAtCarryingValue` + the ASU-2016-18 combined tag — balance-sheet cash vs the cash-flow statement's ending total incl. restricted cash |
| 16 | `net_income` | `NetIncomeLoss` / `ProfitLoss` / `NetIncomeLossAvailableToCommonStockholdersBasic` — differ by non-controlling interests and preferred dividends |
| 11 | `equity` | `StockholdersEquity` / `…IncludingPortionAttributableToNoncontrollingInterest` / `MinorityInterest` |
| 6 | `revenue` | `Revenues` + `RevenueFromContractWithCustomerExcludingAssessedTax`, and two bank cases with `InterestAndDividendIncomeOperating` |
| 4 | `operating_income` | `OperatingIncomeLoss` + `IncomeLossFromContinuingOperationsBeforeIncomeTaxes…` — operating income vs **pre-tax** income |

The classifier is doing precisely what §5.3 designed it to do: it refuses to
choose between two concurrently-reported lines, aggregates the refusals, and
surfaces them as taxonomy mismatches. The ruling §5.3 anticipates is
therefore about the **families**, not the classifier. Three options, stated
without picking one (this is a build-level ruling for the main session; it
touches no owner gate):

- **(a) Ship as ratified.** F5 builds ~2/3 of the (company, family) series
  and refuses the rest, per family and per company, with the reason attached.
  Honest and safe; costs real coverage on `cash`, `liabilities`, `net_income`.
- **(b) Tighten the families so members are true substitutes** — e.g. drop
  `LiabilitiesAndStockholdersEquity` from `liabilities` and `MinorityInterest`
  from `equity`, and decide explicitly whether pre-tax income belongs in
  `operating_income`. This changes §5.2's table (a build-level amendment,
  MEASURED impact re-derivable in minutes from the preview CSV) and leaves
  §5.3 untouched. It would clear the two largest blocker clusters.
- **(c) Ratify an explicit dominance rule** — e.g. "if exactly one tag has
  strictly the highest coverage and clears the bar, that is the series" —
  which would resolve **31 of the 78** OVERLAP cases. This is the "silently
  pick one" §5.2 forbids, so it would need a deliberate, written ratification
  and would still leave 47 genuine ties.

The 5 `ABSENT` and 3 `PARTIAL` cases are all real and worth knowing about:
- `dei:EntityCommonStockSharesOutstanding` is **absent for GOOGL, V and MA**
  and `EarningsPerShareDiluted` is **absent for V** — multi-class filers
  report those per share class, and companyfacts omits dimensioned facts.
  This will scale to every multi-class member of the 244 and is not fixable
  by re-fetching.
- `CVX/operating_income` ABSENT; `JNJ/operating_income` 55%; `SLB/cash` 55%;
  `XOM/shares_outstanding` **73%** — just under the 75% bar, the cover-page
  "as-of" date-bucketing caveat E1 documented.

## 7. Volume check against §5.4

MEASURED over the 25 cached documents with the new 25-tag set: **63,680 rows**
(E1's 13-tag list produced 42,158 → **+51%**), 2,547 rows/company. Linear
extrapolation to 244 members: **~621k rows**, the low end of §5.4's
600k–1.0M ESTIMATE. Network cost is unchanged by construction (§5.1): the
same 244 companyfacts GETs, ~1.1 GB.

## 8. Resume instructions

Nothing is partial. To re-verify from scratch, offline:

```bash
cd /Users/vihanpatil/personal/projects/FinScreen
python3 -m pytest test_ingest_fundamentals.py test_pit.py -q   # 75 passed
python3 data/f2/fixtures/build_fixtures.py                     # fixtures, byte-identical
```

To re-derive §6's preview numbers (offline, ~20 s, no network): load each
`data/raw/companyfacts/CIK*.json`, feed every `(taxonomy, tag)` in
`ingest_fundamentals.CONCEPTS` through `extract_concept_facts()`, then
`classify_universe(df, load_universe()[isin(cached_ciks)])` and
`sector_blockers(...)`. That is exactly how
`data/f2/concept_resolution_preview_25.csv` was produced.

**For S6 (segment 3):** `python3 ingest_fundamentals.py --db data/filings_metadata_e2.db`
is unchanged as a command line. It now additionally writes
`data/f2/concept_resolution.csv` (244 × 10 = 2,440 rows) and prints the
BLOCKER table first. Its FATALs do not stop the run (E1 behaviour, kept) —
the parquet is written and the resolution CSV is what F5 must consult before
building any series. Expect the §6 finding to reappear at 244-member scale;
if the §6 ruling lands first, re-run is free (cache-only re-parse).

---

# 9. SECOND PASS — implementing the 2026-08-24 ruling (same day, same agent)

The main session read §6, accepted the finding, and ruled: **"substitutes-only
families + explicit dominance"** (`F2_PROGRESS.md` §5). This section is what
that ruling produced. It supersedes §§4, 6 and 7 above; §3's verbatim
hand-maps and §5's clarifications 1–5 still stand (clarification 5's `tags`
semantics is extended by A1.2's `alternates` column; the `.gitignore` item in
clarification 1 is closed — the main session handled it).

## 9.1 Resolution profile, before and after (MEASURED, 25 cached companyfacts, E2 windows)

| | first pass | after the ruling |
|---|---|---|
| (cik, family) pairs | 250 (10 families) | **350** (14 families) |
| UNRESOLVED | **86 = 34%** | **57 = 16%** |
| …on the ten pre-amendment families only | 86/250 = 34% | **23/250 = 9%** |
| `OVERLAP` (genuine ambiguity) | **22** | **0** |
| `MIGRATION` | **0** | **13** |
| `DOMINANT` | — (state did not exist) | **47** |
| `SINGLE` | 164 | 233 |
| `PARTIAL` / `ABSENT` | 3 / 5 | 12 / 45 |
| sector BLOCKERs | **22** | **17**, each justified in §9.4 (15 ABSENT-only) |
| rows ingested (25 companies) | 63,680 | **65,924** (26 tags) |

Per family, after (companies per state):

| family | SINGLE | DOMINANT | MIGRATION | PARTIAL | ABSENT |
|---|---|---|---|---|---|
| revenue | 16 | 6 | 3 | 0 | 0 |
| net_income | 13 | 12 | 0 | 0 | 0 |
| assets | 25 | 0 | 0 | 0 | 0 |
| liabilities_and_equity | 25 | 0 | 0 | 0 | 0 |
| operating_cash_flow | 24 | 1 | 0 | 0 | 0 |
| eps_diluted | 24 | 0 | 0 | 0 | 1 |
| equity | 16 | 9 | 0 | 0 | 0 |
| cash | 5 | 19 | 0 | 1 | 0 |
| pretax_income | 13 | 0 | 10 | 1 | 1 |
| shares_outstanding | 21 | 0 | 0 | 1 | 3 |
| liabilities | 19 | 0 | 0 | 0 | 6 |
| operating_income | 14 | 0 | 0 | 1 | 10 |
| net_income_to_common | 8 | 0 | 0 | 3 | 14 |
| minority_interest | 10 | 0 | 0 | 5 | 10 |

## 9.2 What changed in code

1. **`CONCEPT_FAMILIES`: 10 families / 25 tags → 14 / 26.** Split out
   `net_income_to_common`, `liabilities_and_equity`, `minority_interest`,
   `pretax_income`; `operating_income` is `OperatingIncomeLoss` alone.
   **One membership adjustment beyond the ruling's proposal, measured and
   documented** (the ruling authorised adjustment within principle 1): added
   `IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments`
   to `pretax_income` and preferred it. The variant §5.2 carried exists for
   23/25 companies but is thinly covered — MSFT 24/44 quarters vs 31, JNJ 24
   vs 29, MA 12 vs 43 — and without the sibling, 11 of 25 companies sat
   PARTIAL on a family that is perfectly well reported. The `…Domestic` /
   `…Foreign` siblings are geographic components, not the subtotal, and are
   deliberately excluded.
2. **`DOMINANT`** (A1.2) — highest-preference bar-clearing live tag wins;
   losers recorded in the new `alternates` CSV column (8 columns now).
3. **Staleness** (A1.3) — `STALE_TAIL_MAX_QUARTERS = 2`, anchored on the
   company's own last quarter with any fundamentals data. Calibration is in
   §9.5; this is what makes the SLB outcome the ruled one rather than an
   accident.
4. **`MIGRATION` widened to hand-offs** (A1.4), ordered by last covered
   quarter so `tags[-1]` is the live tag, with `switch_quarter` = where the
   successor takes over.
5. **`SectorBlocker.states`** — every blocker row now carries its failure
   profile (`ABSENT:4 PARTIAL:1`), printed in the top-of-run table. Nothing
   is suppressed; the split is what makes 17 rows readable instead of a wall.

## 9.3 Cash: design (a), chosen on measurement

The ruling left the cash family to me. Measured both:

- **(a) one family**, preference `CashAndCashEquivalentsAtCarryingValue >
  CashAndDueFromBanks > CashCashEquivalentsRestrictedCash… >
  …IncludingDisposalGroup…`: **24/25 resolve** (5 SINGLE, 19 DOMINANT), 1
  PARTIAL (SLB, §9.4). JPM/BAC resolve to `CashAndDueFromBanks`; CVX resolves
  to the restricted-cash tag; no cross-family machinery.
- **(b) split** balance-sheet-cash + restricted-total families: CVX's
  balance-sheet family measures **31/44 = 70%**, below the bar, so design (b)
  turns the single most-documented E1 migration case into an UNRESOLVED
  unless a cross-family fallback is built — new machinery whose only job is
  to undo the split.

(a) wins on both counts. It stays inside principle 1 because a migration
successor is explicitly an allowed family member, and preference order means
a restricted-cash tag can only win where the filer abandoned the standard
line — which is exactly the ASU-2016-18 case.

## 9.4 Every remaining UNRESOLVED pair, justified (57)

**By category — 45 ABSENT, 12 PARTIAL, 0 OVERLAP:**

| n | pairs | justification |
|---|---|---|
| 17 | `net_income_to_common` (14 ABSENT / 3 PARTIAL) | Differs from net income only when preferred dividends exist. Most of these filers have no preferred stock, so the tag is absent or annual-only. Expected; the family exists so the tag stays ingested for filers that do use it. |
| 15 | `minority_interest` (10 / 5) | Non-controlling interests exist only for a company with non-wholly-owned subsidiaries. Same reasoning. |
| 11 | `operating_income` (10 ABSENT + SLB) | The ruled-expected absence: banks and most energy/pharma majors present no GAAP operating-income line (BAC, COP, CVX, GS, JNJ, JPM, MRK, OXY, PFE, XOM — E1 documented the same 9 plus JNJ in HANDOFF §2a trap (a)). `pretax_income` resolves for all of them except MCD. SLB is §9.6. |
| 6 | `liabilities` ABSENT (ABBV, KO, MCD, MRK, OXY, WMT) | These six do not tag a total-liabilities line — the exact set E1's `features_report.md` documented. `liabilities_and_equity` resolves SINGLE for **all 25**, so F5 can derive total liabilities as `LiabilitiesAndStockholdersEquity − StockholdersEquity` if it chooses to; that is F5's decision, made in the open, which is the point of the split. |
| 4 | `shares_outstanding` (GOOGL, MA, V ABSENT; XOM PARTIAL 73%) | Multi-class filers report the dei cover-page fact per share class, and companyfacts omits dimensioned facts — not fixable by re-fetching, and it will recur for every multi-class member of the 244. XOM sits 2 points under the bar on the cover-page "as-of" date bucketing E1 documented. |
| 1 | `eps_diluted` ABSENT (V) | Same cause: V's EPS is tagged per share class; its undimensioned `EarningsPerShareDiluted` has zero rows. |
| 2 | `pretax_income` (MCD ABSENT, PG PARTIAL 11%) | MCD tags neither pre-tax subtotal; PG tags one **annually only** (5 in-window quarters, all 364/365-day durations), so it cannot reach a quarterly bar. |
| 1 | `cash` PARTIAL (SLB) | §9.6 — a live recommendation, not a defect. |

**The 17 BLOCKERs are these same seven causes, per sector:**
`net_income_to_common` ×5 sectors, `minority_interest` ×5,
`operating_income` ×3 (energy 5/5, financials 3/5, healthcare 3/5),
`liabilities` ×2 (consumer 3/5, healthcare 2/5), `shares_outstanding` ×1
(financials — MA and V), `pretax_income` ×1 (consumer — MCD and PG). Eleven
of the 17 belong to the four single-tag families the ruling created; on the
ten pre-amendment families the count is **22 → 6**.

**Optional refinement, NOT taken unilaterally:** ten of the 17 are families
for concepts that are inherently optional (NCI, preferred dividends). A
family-level `optional=True` flag would keep the per-pair UNRESOLVED rows
loud while keeping those cells out of the BLOCKER table. That changes the
BLOCKER rule, which the ruling said was unchanged, so it is flagged here for
the main session rather than implemented.

## 9.5 Staleness threshold — the calibration

Across the 25 cached companies, every (company, family, tag) instance at or
above the 75% bar, gap = quarters between the tag's last covered quarter and
the company's own last quarter with any fundamentals data:

| gap (quarters) | instances |
|---|---|
| 0 | **366** |
| 1 | 2 (V `ProfitLoss`, PG `EntityCommonStockSharesOutstanding`) |
| 2 | **0** |
| 5 | 1 (GOOGL `RevenueFromContractWithCustomerExcludingAssessedTax`) |
| 9 | 2 (SLB `OperatingIncomeLoss`, OXY `NetIncomeLoss`) |

`STALE_TAIL_MAX_QUARTERS = 2` sits in the empty band, two quarters above the
largest normal gap and three below the smallest dead tag. Same calibration
discipline as E1's thresholds (min-observed with margin), and the anchor is
the company rather than the calendar so a delisted member does not go stale
in every family at once for having stopped filing.

## 9.6 The one live recommendation: SLB `cash`

SLB tags its balance-sheet cash under plain **`Cash`** — 49 quarters,
2012Q4–2026Q2, MEASURED — which is a *different* us-gaap element (cash
excluding equivalents) and therefore not a family member under principle 1.
What the family does carry covers 55% (`…IncludingDisposalGroupAnd
DiscontinuedOperations` 23/44 from 2019Q4, plus six pre-2016 quarters of the
standard tag), so `cash` fails loudly for SLB rather than proxying.

That is the conservative call and it is deliberate. **If the main session
rules `Cash` an acceptable balance-sheet-cash alias, it is a one-line family
edit and a re-run** (cache-only, free). I did not make that call myself
because `Cash` vs `CashAndCashEquivalents` is a definitional difference, not
a presentation one — the same kind of distinction the ruling exists to stop
being papered over.

## 9.7 Hand-map case outcomes, after the ruling

| E1 hand-map entry | verdict | detail |
|---|---|---|
| bank cash, **JPM** | **DOMINANT → `CashAndDueFromBanks`** | 44/44; alternate: the ASU-2016-18 total (36/44). The standard cash tag is preferred but only reaches 10/44 for JPM, so it does not clear the bar. |
| bank cash, **BAC** | **DOMINANT → `CashAndDueFromBanks`** | 44/44; standard tag 21/44. |
| bank cash, **GS** | **DOMINANT → `CashAndCashEquivalentsAtCarryingValue`** | Deliberate and documented: GS reports the standard tag at 44/44 *and* `CashAndDueFromBanks` at 44/44, so preference resolves it to the line that is comparable across the whole universe. E1's map would have sent GS to the bank tag purely because its ticker was in a set. Pinned by its own test. |
| bank operating income, **JPM / BAC / GS** | **ABSENT, reported** | Ruled-expected. `pretax_income` resolves SINGLE at 44/44 for all three — and because the ruling moved it to its own family, it can no longer stand in for operating income silently. |
| `("MA","NetIncomeLoss")` → ProfitLoss | **SINGLE → `ProfitLoss`** (44/44) | `NetIncomeLoss` contributes 0 covered quarters: its only in-window rows are 5 DEF 14A rows filed 2026-04-27 (trap (c)), pinned by a test that relabels them to `10-K` and watches the tag reappear. |
| `("OXY","NetIncomeLoss")` → ProfitLoss | **DOMINANT → `ProfitLoss`** (41/44) | Reproduced for the right reason: `NetIncomeLoss` clears the bar (33/44 = 75%) and is preferred, but died in 2024 (gap 9), so dominance skips it. Same answer E1 wrote by hand, derived from data. |
| `("SLB","OperatingIncomeLoss")` → ProfitLoss | **PARTIAL, loud — deliberately NOT reproduced** | Per ruling item (4). `OperatingIncomeLoss` 35/44 = 80%, STALE by 9 quarters (last 2024Q1 vs SLB's 2026Q2). E1's map was wrong twice: `ProfitLoss` is a net-income tag, and what happened is that SLB stopped reporting a GAAP operating-income line. Supersedes F2_SPEC §8.2's SLB prediction. |
| `("CVX","CashAndCashEquivalents…")` → restricted-cash | **SINGLE → `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents`** (40/44) | Standard tag 31/44 (70%), below the bar. |

**Not an E1 case, added as an acceptance fixture:** GOOGL `revenue` →
**MIGRATION**, switch **2025Q2**, `…ExcludingAssessedTax` (34/40, died
2025Q1) → `Revenues` (28/40, live), union 100%. This is the shape A1.4 was
written for; without it a core-stratum mega-cap loses its revenue series.

## 9.8 Test counts (second pass)

| file | collected | passed | failed |
|---|---|---|---|
| `test_ingest_fundamentals.py` | **81** | **81** | 0 |
| `test_pit.py` | 5 | 5 | 0 |

15 (E1) → 70 (first pass) → **81**. New/rewritten this pass: the ruled family
table + a principle-1 guard, `DOMINANT` (3 tests incl. preference-beats-
coverage), staleness (5, incl. the 2-quarter live boundary and the
delisted-member anchor), MIGRATION hand-offs, the ruled acceptance outcomes
for every hand-map case, GOOGL's hand-off, SLB `cash`'s justification, and
the 8-column CSV. `pyflakes` clean. Still offline, still no socket.

## 9.9 Files touched in the second pass

- `ingest_fundamentals.py` — families, `DOMINANT`, staleness, hand-off
  MIGRATION, `alternates`, blocker state profile.
- `test_ingest_fundamentals.py` — 70 → 81 tests.
- `data/f2/F2_SPEC.md` — **appended** §5.5 amendment A1 (S1's §5.2/§5.3 text
  untouched).
- `data/f2/fixtures/` — regenerated; `build_fixtures.py` CASES now slice
  `pretax_income` for the banks, `cash` for SLB, and add GOOGL `revenue`.
  568 KB total.
- `data/f2/concept_resolution_preview_25.csv` — regenerated, 350 rows, 8
  columns.
- This report.

Unchanged and still true: zero live GETs (nothing under `data/raw/` written;
all measurement from the 25 cached documents), E1's frozen artifacts
untouched, `F2_PROGRESS.md` not edited, no sibling-stage file opened for
writing, full suite not run.

---

# 10. THIRD PASS — the two second-pass items, ruled and implemented (2026-08-24)

The main session ruled both of §9's open items (`F2_PROGRESS.md` §5, "S4
second-pass items"), recorded as F2_SPEC §5.6 amendment A2. This section
supersedes §9.6 (SLB cash was a recommendation; it is now ruled in) and
§9.4's "optional refinement" note (the exemption mechanism now exists).
§9's measurements otherwise stand, with the deltas below.

## 10.1 `us-gaap:Cash` at lowest preference — a strict addition, as predicted

Added to the `cash` family last, with the definitional caveat (**it excludes
cash equivalents**) written into the family definition's comment and repeated
here. Dominance guarantees it can never displace a proper tag; the resolution
CSV records which tag actually won, so the caveat travels with the data
rather than living only in a comment.

**Exactly one resolution changed** (diffed all 350 pairs on `state`, `tags`,
`switch_quarter`, `severity`, `alternates` against the §9 preview):

| pair | before | after |
|---|---|---|
| SLB `cash` | `PARTIAL` / UNRESOLVED, tags `…IncludingDisposalGroup…\|CashAndCashEquivalentsAtCarryingValue`, coverage 55% | **`SINGLE` / resolved on `Cash`**, 44/44 = 100% |

Nothing else moved: no other company changed state, resolved tag, alternates
or switch quarter, and **no other company carries `Cash` even as an
alternate** — for the other 24 it either has no in-window coverage or does
not clear the bar, so preference never reaches it. Tag count 26 → **27**;
rows ingested from the 25 cached documents 65,924 → **66,164**. Preview
UNRESOLVED **57/350 → 56/350 (16.0%)**; `cash` is now the only family that
resolves for all 25 companies twice over (6 SINGLE + 19 DOMINANT).

Pinned by two tests: SLB resolves via `Cash` from its fixture, and a
synthetic filer reporting `Cash` alongside each of the three proper tags
resolves to the proper tag every time, with `Cash` recorded as an alternate —
`Cash` wins only when it is alone.

## 10.2 `BLOCKER_EXEMPT_CELLS` — 17 BLOCKERs → 6

One dict, three ruled entries, no other mechanism. Exempt cells leave the
BLOCKER table and **nothing else**: all 56 per-pair FATAL
`fundamentals_alias_unresolved` rows are still emitted, including all 15
`minority_interest` failures. `resolution_problems()` does not import,
consult, or know about the dict — pinned by a test that removes the exemption
under `monkeypatch` and watches the identical data become a blocker.

The run report prints the ledger directly under the blocker table, always:

```
BLOCKER exemptions (3 in BLOCKER_EXEMPT_CELLS; they suppress table rows only
-- every per-company UNRESOLVED row is still emitted as FATAL):
  [suppressed 5] (*, minority_interest): tech 5/5, financials 4/5, consumer 2/5, energy 2/5, healthcare 2/5
      reason: MinorityInterest exists only for a filer with non-wholly-owned subsidiaries; ...
  [suppressed 5] (*, net_income_to_common): tech 5/5, consumer 4/5, energy 3/5, healthcare 3/5, financials 2/5
      reason: NetIncomeLossAvailableToCommonStockholdersBasic differs from net income only when ...
  [suppressed 1] (financials, operating_income): financials 3/5
      reason: Banks have no GAAP operating-income line ... HANDOFF §2a trap (a) fact.
```

All three fire; **none is dead**. A dead entry prints
`[DEAD -- suppressed nothing this run; fix the dict rather than leaving it]`,
pinned by a test.

**The six surviving BLOCKERs** (each already justified in §9.4):

| sector | family | cell | states |
|---|---|---|---|
| energy | operating_income | 5/5 = 100% | ABSENT 4, PARTIAL 1 (SLB) |
| consumer | liabilities | 3/5 = 60% | ABSENT 3 |
| healthcare | operating_income | 3/5 = 60% | ABSENT 3 |
| consumer | pretax_income | 2/5 = 40% | ABSENT 1 (MCD), PARTIAL 1 (PG, annual-only) |
| financials | shares_outstanding | 2/5 = 40% | ABSENT 2 (MA, V — multi-class) |
| healthcare | liabilities | 2/5 = 40% | ABSENT 2 |

## 10.3 PROPOSED-not-exempted (for a later ruling, NOT implemented)

Measurement suggests three more cells are structural rather than defects. I
did not add them — the ruling says entries come by ruling only:

1. **`("*", "liabilities")`** — 6 of 25 filers (ABBV, KO, MCD, MRK, OXY, WMT)
   tag no total-liabilities line; E1 documented the same six. Because
   `liabilities_and_equity` resolves SINGLE for **all 25**, the quantity is
   recoverable as `LiabilitiesAndStockholdersEquity − StockholdersEquity` if
   F5 chooses. Would clear 2 of the 6 remaining blockers. The argument
   against exempting: unlike NCI and preferred dividends, total liabilities
   is a universal economic quantity, so its absence is a tagging choice, not
   a structural fact — arguably exactly what a BLOCKER should keep visible.
2. **`("*", "shares_outstanding")` for multi-class filers** — GOOGL, MA and V
   report the dei cover-page fact per share class and companyfacts omits
   dimensioned facts. Unfixable by re-fetching and certain to recur across
   the 244. Would clear 1 blocker. A per-company exemption would be more
   honest than a blanket one, which the current key shape does not express.
3. **`("*", "operating_income")` beyond financials** — energy and healthcare
   majors also present no operating-income line. This is the same fact the
   financials entry states, one sector wider; whether it generalises is a
   judgement about GAAP presentation I would want measured across all 244
   before proposing it as a `*` rule. Would clear 2 blockers.

Nothing else in the preview looks exemptible: the remaining cells are real,
individually-justified data limits.

## 10.4 Test counts (third pass)

| file | collected | passed | failed |
|---|---|---|---|
| `test_ingest_fundamentals.py` | **89** | **89** | 0 |
| `test_pit.py` | 5 | 5 | 0 |

15 (E1) → 70 → 81 → **89**. New this pass: the `Cash` family pin and tag
count 27, SLB resolving via `Cash`, `Cash`-never-displaces-a-proper-tag, the
three shipped exemptions pinned exactly, exempt-cell-suppresses-table-only
(with the monkeypatch inverse), sector-scoped exemption does not leak across
sectors, non-exempt cell still fires at 21%/19%, exemption status reporting,
dead-exemption reporting, and exemptions-never-touch-per-pair-rows on real
fixture data. The `run()` ordering test now pins blocker table → exemption
ledger → per-company findings. `pyflakes` clean, all offline.

## 10.5 Files touched in the third pass

- `ingest_fundamentals.py` — `Cash` at lowest preference with its caveat
  comment; `BLOCKER_EXEMPT_CELLS`, `blocker_exemption_reason()`,
  `_unresolved_cells()` (the one place the aggregation is computed),
  `BlockerExemptionStatus`, `blocker_exemption_statuses()`,
  `print_blocker_exemptions()`; `run()` prints the ledger under the table.
- `test_ingest_fundamentals.py` — 81 → 89 tests.
- `data/f2/F2_SPEC.md` — **appended** §5.6 amendment A2.
- `data/f2/fixtures/` — SLB's slice regenerated (now carries `Cash`); the
  other seven byte-identical.
- `data/f2/concept_resolution_preview_25.csv` — regenerated (350 rows, 8
  columns, one changed row).
- This report.

Still true: zero live GETs, E1's frozen artifacts untouched, `F2_PROGRESS.md`
not edited, no sibling-stage file opened for writing, full suite not run.

---

# 11. FOURTH PASS — the 244-scale calibration, ruled and implemented (2026-08-24)

Segment 3 ran for real (619,597 rows, 3,416 pairs, 693 UNRESOLVED, 18
BLOCKERs); the main session read the blocker table and issued four rulings
(`F2_PROGRESS.md` §5, "244-scale classifier calibration"), recorded as
F2_SPEC amendment A5. This section supersedes §10.3's PROPOSED list (two of
its three items are now ruled in) and §9.5's denominator description.
Everything here is MEASURED by replaying the classifier offline over
`data/fundamentals_e2.parquet` plus the three new tags extracted from the 244
**cached** companyfacts — **0 GETs, no DB or parquet written**.

## 11.1 Predicted new profile (offline replay, 3,416 pairs)

| state | real segment-3 run | predicted |
|---|---|---|
| SINGLE | 2,192 | **2,355** |
| DOMINANT | 456 | **489** |
| MIGRATION | 75 | 75 |
| OVERLAP | 8 | 8 |
| PARTIAL | 332 | **147** |
| ABSENT | 353 | **342** |
| **UNRESOLVED** | **693** | **497** |

**196 pairs improved, 0 regressed.** Three resolved pairs changed which tag
they resolve to, all in the safe direction — under the trimmed denominator a
single preferred tag now clears the bar where a stitched sequence was needed
before: Activision `revenue` (MIGRATION → SINGLE on
`RevenueFromContractWithCustomerExcludingAssessedTax`), Pioneer `eps_diluted`
(MIGRATION → SINGLE on `EarningsPerShareDiluted`), BlackRock Finance
`operating_cash_flow` (MIGRATION → SINGLE on the preferred total).

Artifacts: `data/f2/concept_resolution_prediction_244.csv` (the full predicted
table, same 8 columns) and a regenerated
`data/f2/concept_resolution_preview_25.csv`. The real
`data/f2/concept_resolution.csv` was **not** touched — the main session's
re-run writes it.

## 11.2 Surviving blocker table: **empty**

| sector | family | cell |
|---|---|---|
| — | — | **no cell above 20% survives the exemption ledger** |

All four exemptions fire, none is dead, and between them they suppress **27**
cells. **This deserves a deliberate read, not a celebration:** four of the
fourteen families can no longer produce a blocker at all, so the alarm's value
now rests entirely on someone reading the exemption ledger and the 497
per-pair FATAL rows. The ledger is printed directly under the (empty) blocker
table on every run, with each entry's reason and the cells it suppressed.

The suppressed cells, by exemption:

| exemption | cells suppressed | worst |
|---|---|---|
| `("*", "net_income_to_common")` | 8 sectors | industrials 89% |
| `("*", "minority_interest")` | 8 sectors | tech 81% |
| `("*", "liabilities")` | 6 sectors | energy 56% |
| `("*", "operating_income")` | 5 sectors | financials 62% |

**Nearest cells to the 20% line, all below it:** `tech`
`shares_outstanding` 8/42 = 19%, `financials` 7/37 = 19%, `consumer` 6/33 =
18%, `materials_realestate` `pretax_income` 5/28 = 18%. Ruling 4 expected the
multi-class `shares_outstanding` blockers to keep firing; **measurement says
they no longer clear the threshold** — the denominator fix resolved the
members whose dei coverage was merely window-diluted, leaving only the truly
ABSENT ones. They stay loud per pair (16 UNRESOLVED rows). I did not
manufacture a blocker to match the expectation. **If the main session wants
them visible at run level, the honest mechanism is a "cells just below
threshold" line in the report rather than moving the threshold** — proposed,
not implemented.

## 11.3 Every added MLP tag, with its measured user count

| family | tag | users / 244 | effect |
|---|---|---|---|
| `equity` | `PartnersCapital` | **12** | resolves EPD, Magellan, Williams Partners, MPLX (was ABSENT) |
| `equity` | `PartnersCapitalIncludingPortionAttributableToNoncontrollingInterest` | **8** | the NCI-inclusive mirror; recorded as `alternates` where both exist |
| `eps_diluted` | `NetIncomeLossNetOfTaxPerOutstandingLimitedPartnershipUnitDiluted` | **8** | resolves all 8 partnership members that were ABSENT, incl. KKR |

Preference order is corporate-first in both families, pinned by a test: a
filer reporting both a corporate and a partnership tag resolves corporate.

**Deliberately not added, each with the measurement that says so:**

| candidate | users | why not |
|---|---|---|
| `LimitedPartnersCapitalAccount` | 7 | the LP slice of capital — a COMPONENT, like `MinorityInterest`, which `equity` already excludes. Adds **zero** coverage: every member reporting it also reports a partners-capital total. |
| `GeneralPartnersCapitalAccount` | 4 | same, the GP slice. |
| `NetIncomeLossPerOutstandingLimitedPartnershipUnitBasicNetOfTax` | 8 | BASIC per unit. The corporate `EarningsPerShareBasic` is not in this family either, and it adds **zero** coverage over the diluted tag. |
| `IncomeLossFromContinuingOperations…PerOutstandingLimitedPartnershipUnit…` | 4 | continuing-ops per unit; all 4 users already covered. |
| `WeightedAverageLimitedPartnershipUnitsOutstanding(Diluted)` | 8 | a period AVERAGE, not a point-in-time count — a different measure from shares outstanding. |
| any unit-count tag for `shares_outstanding` | — | **of the 30 members unresolved on this family, ZERO report any unit-count tag in-window.** The partnerships use the ordinary dei cover-page fact (pinned by an EPD test). The 30 are the multi-class gap, not an MLP gap. |
| any partnership tag for `pretax_income` | — | partnerships are **pass-through entities with no income-tax subtotal**; no partnership variant of the concept exists. ABSENT is the economically correct answer, not a taxonomy miss. |

## 11.4 The 8 OVERLAP cases, listed and left firing (ruling 4)

Unchanged in count and membership by this pass. Each is a filer co-reporting
two or three tags of one family where **none** clears the 75% bar, so there is
no dominant tag to prefer and no hand-off to follow — genuine ambiguity, and
the classifier refuses.

| company | sector | family | union | tags |
|---|---|---|---|---|
| APACHE CORP (6769) | energy | revenue | 79% | `Revenues` + `RFCWC-Including` + `RFCWC-Excluding` |
| BECTON DICKINSON (10795) | healthcare | operating_cash_flow | 100% | `NetCashProvidedByUsedInOperatingActivities` + `…ContinuingOperations` |
| GENERAL DYNAMICS (40533) | industrials | revenue | 85% | `RFCWC-Excluding` + `Revenues` |
| HALLIBURTON (45012) | energy | cash | 100% | `CashAndCashEquivalentsAtCarryingValue` + both restricted-cash tags |
| INTEL (50863) | tech | cash | 91% | the three cash tags + `Cash` |
| WEYERHAEUSER (106535) | materials_realestate | equity | 100% | `StockholdersEquity` + `…IncludingPortionAttributableToNoncontrollingInterest` |
| FISERV (798354) | financials | revenue | 100% | `Revenues` + `RFCWC-Excluding` |
| CROWN CASTLE (1051470) | materials_realestate | pretax_income | 100% | both pre-tax subtotals |

Pattern worth a later look (not fixed here): six of the eight are a filer
alternating between two tags quarter by quarter rather than migrating — the
union is complete but neither tag is continuous. A "stitch two interleaved
substitutes" rule would resolve them; it is a different rule from anything
ruled so far, so it is a proposal, not an edit.

## 11.5 Multi-class `shares_outstanding`, listed and left firing (ruling 4)

16 members UNRESOLVED, 12 of them ABSENT with **zero** in-window rows for
`dei:EntityCommonStockSharesOutstanding`: Alphabet, Meta, Visa, Mastercard,
Berkshire Hathaway, Comcast, Ford, CME, Estée Lauder, Snap, Block, Zoom,
Palantir, LinkedIn, AZEK (plus PARTIAL cases: Truist 74%, Citigroup 74%,
Schwab 61%, CrowdStrike 50%, Charter 11%, Nike 2%). Cause: companyfacts
publishes only undimensioned facts, and a multi-class filer tags its cover-page
share count per class. **Not fixable by re-fetching** — it needs the XBRL
dimensional data (`companyconcept` frames or the filing's own instance
document), which is out of F2's scope. Parked, loud, and certain to recur.

## 11.6 Two smaller things the replay surfaced

- **Three members have a filed span under 8 quarters**: EMC (790070) 4,
  LinkedIn (1271024) 5, Spectra Energy (1373835) 7 — all acquired mid-window.
  Their families now resolve at 100% of a very short span, which is honest but
  thin; F5 should treat a resolution's `coverage` alongside the span, and the
  span is recoverable from the FATAL messages and the run report. Flagged, not
  changed: trimming the span is exactly what A5.1 ruled.
- **The ruling says "the 5-entry exemption ledger"; the ledger is 4.**
  A5.3 adds two entries and supersedes one, so 3 − 1 + 2 = 4, all `("*", …)`.
  I implemented the ruling's body (replace, do not keep) and pinned four, with
  an explicit assertion that `("financials", "operating_income")` is gone.
  Flagging the arithmetic rather than silently picking one reading.

## 11.7 Test counts (fourth pass)

| file | collected | passed | failed |
|---|---|---|---|
| `test_ingest_fundamentals.py` | **95** | **95** | 0 |
| `test_pit.py` | 5 | 5 | 0 |

15 (E1) → 70 → 81 → 89 → **95**. New this pass: the AZEK-shaped denominator
test (a six-quarter-life member resolves SINGLE on **all 14** families), its
inverse (an interior hole still fails), a guard that the span is the
company's and not the family's, the three MLP acceptance tests against a new
EPD fixture (partners-capital DOMINANT, per-unit EPS SINGLE, unit count from
the dei fact), corporate-tags-outrank-partnership-tags, and the four-entry
ledger pinned exactly with the supersession asserted. Six existing coverage
tests gained an explicit `_anchor()` because under A5.1 a test about a
coverage BAND has to state the filed span or it measures nothing.

## 11.8 Files touched in the fourth pass

- `ingest_fundamentals.py` — A5.1 denominator, A5.2 three tags (27 → 30),
  A5.3 ledger (4 entries).
- `test_ingest_fundamentals.py` — 89 → 95 tests.
- `data/f2/F2_SPEC.md` — **appended** amendment A5 under §11.
- `data/f2/fixtures/` — added `companyfacts_CIK0001061219.json` (EPD) and its
  `CASES` entry in the shared `build_fixtures.py` (S3 owns the index-fixture
  half of that file; the merge is clean).
- `data/f2/concept_resolution_prediction_244.csv` — **new**, the predicted
  table for the main session to diff against its re-run.
- `data/f2/concept_resolution_preview_25.csv` — regenerated under the new
  rules (350 pairs, 56 UNRESOLVED, 2 blockers). Superseded in practice by the
  real 244-scale artifact; safe to delete once the re-run lands.
- This report.

`data/f2/concept_resolution.csv`, `data/fundamentals_e2.parquet` and the E2 DB
were **not** written by this pass. E1's frozen artifacts untouched,
`F2_PROGRESS.md` not edited, no sibling-stage module opened for writing, full
suite not run.

---

# 12. FIFTH PASS — the S4 half of the S7 red-team fixes (2026-08-24)

S7 re-derived the classifier independently and agreed on all 3,416 pairs, then
named four gaps. The main session triaged B5/B11/B15/B21 to S4
(`F2_PROGRESS.md` §5); this section is the implementation, recorded as F2_SPEC
amendment **A9**. All four are additive — **zero resolution states change**,
re-verified by diffing all 3,416 rows of the replay against §11's prediction on
`state`, `tags`, `switch_quarter`, `coverage`, `severity` and `alternates`.

## 12.1 B5 — `companyfacts_tail_lag`, an independent tail check

The finding is exactly right and worth restating: the coverage denominator
(A5.1) and the staleness anchor (A1.3) are both defined by the data being
checked, so a truncated companyfacts document scores 100% with no alarm. The
fix breaks the circularity by comparing against S3's filing metadata,
**read-only** (`file:…?mode=ro`): per member, how many in-window 10-K/10-Q
filings were filed **after** its last fundamentals fact.

**WARN roster (≥ 2 filings behind) — 1 member:**

| CIK | member | last fact | filings after | lag | its score |
|---|---|---|---|---|---|
| 831001 | CITIGROUP INC | 2026-02-20 | **2** (2026-05-07, 2026-08-06) | 167 d | 0.9767, 12 of 14 families resolved |

**INFO roster (exactly 1 filing behind) — 21 members**, all 82–92 days: 1800
Abbott, 4904 AEP, 21344 Coca-Cola, 34088 ExxonMobil, 64040 S&P Global, 92122
Southern, 715957 Dominion, 753308 NextEra, 766704 Welltower, 813672 Cadence,
895126 Expand Energy, 896159 Chubb, 927628 Capital One, 1032208 Sempra,
1045609 Prologis, 1053507 American Tower, 1103982 Mondelez, 1109357 Exelon,
1297996 Digital Realty, 1403161 Visa, 1633917 PayPal. Every one is the Q2-2026
10-Q filed in late July / early August whose XBRL facts had not propagated
into the cached companyfacts document — one quarter, uniformly. Escalating
those to WARN would bury Citigroup, which is the only real truncation; INFO
keeps them counted and named.

Total = 22, reproducing S7's measured 22 exactly.

**Window scoping, stated because it is a judgement call.** The comparison runs
inside each member's own coverage window, like every other check in this
module. EIDP (30554) — facts stop 2019-05-08, filings continue to 2026-07-31,
S7's 2,641-day example — is **complete within its own window** (which closes
2019-05-08) and therefore does not WARN. Ignoring `coverage_end` instead would
put 33 members on the roster, most of them former members whose windows closed
years ago and whose "missing" filings no other check in F2 would ever look at.
The run summary prints both counts so the shape stays visible.

If the `filings` table is unreadable, `run()` emits a single **`NOT CHECKED`
WARN** naming the reason — a check that silently did not run is worse than one
that failed.

## 12.2 B11 — reporting currency recorded and warned. Full non-USD roster: **one member**

| CIK | member | stratum / sector | resolved families | units |
|---|---|---|---|---|
| **895728** | **ENBRIDGE INC** | **core / energy** | **13** | 12 × `CAD`, 1 × `CAD/shares`, none mixed |

Its 13 resolved families are revenue, net_income, net_income_to_common,
operating_income, pretax_income, assets, liabilities, liabilities_and_equity,
equity, minority_interest, cash, operating_cash_flow, eps_diluted — every one
in CAD, every one resolving as cleanly as a USD filer's, and its price series
is USD. Each now carries `unit=CAD` in the CSV and emits a
`fundamentals_non_usd_reporting` WARN naming the consequence (P/E, P/B,
market-cap-to-book and earnings yield are all wrong by the exchange rate until
F5 converts). **F2 converts nothing.**

**No other member reports a non-USD currency.** Measured over every
operating-form row in the corpus: 547,263 `USD`, 61,306 `USD/shares`, 13,783
`shares`, **1,915 `CAD` + 163 `CAD/shares` (all Enbridge)**, 93 `pure`, and
three oddities that are non-monetary and never dominant — EQT's two
`BillionsCubicFeet` rows and CVS's one `segment` row. Currency detection is an
ISO-4217 *shape* test (three uppercase letters), so those three do not warn
and an unknown real currency would.

Owner-visible note carried from S7: F1's float ranking that placed Enbridge in
the **core** stratum rests on the same currency question. That is F1's
artifact and outside F2's scope; flagged, not touched.

## 12.3 B15 — duration mix recorded; no semantics change proposed, and here is why

Every row now carries `duration_mix` (e.g. `Q:122|FY:27|H1:18|9M:16`, or
`instant:68` for a balance-sheet family), and `ConceptResolution`'s docstring
states plainly that `tags` promises neither a unit nor a duration.

**I am NOT proposing a coverage-semantics change, on measurement.** The defect
class is empty at 244 scale: **zero** resolved pairs have neither a
quarterly-length nor an instant fact, and **zero** resolved flow-family pairs
have their quarterly facts only from 8-Ks. B15's own example does not
reproduce as a resolved pair — CIK 32604 Emerson's `revenue` is **ABSENT** in
both the shipped CSV and the replay (its coverage window closes before its
`Revenues` rows), so nothing resolves on its FY-only durations. The tag-level
observation behind the finding is correct and worth keeping: Emerson's
`Revenues` has only FY-length facts (3 in 10-Ks, 2 in 10-Qs, zero quarterly).
Changing `_quarter_bucket` to require a duration would be a real semantics
change with no live case to justify it, so it stays a documented property.

## 12.4 B21 — 8-K sourcing stated

`OPERATING_FORMS`' comment now says 8-K facts are admitted **deliberately**
(an earnings release is a real, dated, point-in-time disclosure of the same
GAAP fact; excluding it would drop 12,172 parquet rows and penalise filers who
tag their release exhibit properly) alongside the DEF 14A exclusion it already
argued, and adds the measurement: no resolved flow family actually depends on
8-K-sourced quarterly facts. Pinned behaviourally by a test that resolves a
family whose facts are 8-K-only.

## 12.5 Confirmation: zero resolution-state changes

Replayed the classifier offline over `data/fundamentals_e2.parquet` + the
three A5.2 tags and diffed all **3,416** rows against §11's prediction on
`state`, `tags`, `switch_quarter`, `coverage`, `severity`, `alternates`:
**0 differences.** The only deltas are the three appended columns (`unit`,
`units_mixed`, `duration_mix`) and the new WARN/INFO rows. Distribution of the
new `unit` column: USD 2,596 / `""` 342 (the ABSENT rows) / USD-per-share 239 /
shares 226 / CAD 12 / CAD-per-share 1; **zero** mixed-unit rows.

## 12.6 Test counts (fifth pass)

| file | collected | passed | failed |
|---|---|---|---|
| `test_ingest_fundamentals.py` | **107** | **107** | 0 |
| `test_pit.py` | 5 | 5 | 0 |

15 (E1) → 70 → 81 → 89 → 95 → **107**. New: the synthetic truncated-tail case
(full coverage, nothing stale, two filings behind → WARN), one-filing-behind →
INFO, no-lag, window-scoping (the EIDP shape), silent-without-metadata, and
the **Citigroup real-data case** read from the shipped artifacts; the ENB
acceptance trio (non-USD resolves cleanly, carries `unit=CAD`, emits the
WARN), a USD-reporter negative, the ISO-shape unit helper, `duration_mix`
presence and bucket boundaries, and 8-K-only coverage. Six existing
assertions were narrowed to the `fundamentals_alias_unresolved` check because
`resolution_problems()` now also returns currency WARNs.

The Citigroup test carries an explicit instruction in its docstring: if a
fresh companyfacts pull ever closes that gap it will fail loudly and should be
re-pointed at whichever member is then ≥ 2 filings behind, or deleted if none
is. It pins a real defect, not a permanent property.

## 12.7 Files touched in the fifth pass

- `ingest_fundamentals.py` — `load_periodic_filing_dates()` (read-only),
  `tail_lag_problems()`, `non_usd_problems()`, `_duration_buckets()`,
  `_unit_currency()`, three new `ConceptResolution` fields + CSV columns,
  `run()` wiring and summary lines, B15/B21 docstrings.
- `test_ingest_fundamentals.py` — 95 → 107 tests.
- `data/f2/F2_SPEC.md` — **appended** amendment **A9** (next free number:
  A1/A2 are S4's, A3/A4 S5's, A5 S4's, A6–A8 S3's).
- `data/f2/fixtures/` — added `companyfacts_CIK0000895728.json` (Enbridge) and
  its `CASES` entry.
- `data/f2/concept_resolution_prediction_244.csv` and
  `concept_resolution_preview_25.csv` — regenerated with the three new columns
  (states identical).
- This report.

`data/f2/concept_resolution.csv`, `data/fundamentals_e2.parquet` and the E2 DB
were **not** written — the DB was opened read-only. Zero live GETs, E1's
frozen artifacts untouched, `F2_PROGRESS.md` not edited, no sibling-stage
module opened for writing, full suite not run.
