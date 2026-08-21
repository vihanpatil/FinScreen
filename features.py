"""
features.py -- FinScreen Phase C feature engineering.

Builds `data/features.parquet`: one row per (company, filing) observation,
joining every-occurrence text-derived signals from `data/labels.parquet`
with point-in-time numeric fundamentals (`data/fundamentals.parquet` via
`pit.value_as_of()`) and a forward-excess-return target built from
`data/prices.parquet`. Also writes `data/features_report.md`, a full
feature dictionary (source + caveat per feature).

Reads only (the Phase C input set fixed by HANDOFF.md §6 Step 3):
  data/labels.parquet, data/paragraph_occurrence_map.parquet (used
  transitively -- see "Every-occurrence attribution" below),
  data/filings.parquet, data/filings_metadata.db (not needed directly --
  filings.parquet already carries filing_date/form), data/fundamentals.parquet
  + pit.py, data/prices.parquet, data/universe.csv.

Does NOT modify any existing pipeline file. `ingest_fundamentals.py` is
imported for one pure helper function (`extract_concept_facts`) reused to
resolve two documented, binding numeric-fundamentals traps (see "Numeric
fundamentals" below) -- no network calls, no re-ingestion, no edits to that
file.

-----------------------------------------------------------------------
Unit of observation
-----------------------------------------------------------------------
One row per (ticker, accession_number, filing_date, form) -- i.e. one row
per SEC filing, not per filing-section. `filings.parquet` stores one row
per extracted *section* (e.g. a 10-K contributes both an MDA row and a
RISK_FACTORS row with the same accession_number/filing_date); this module
de-duplicates to the filing level first. 630 distinct filings across the
25-company universe as of this build (2023-08-15 through 2026-08-07).

-----------------------------------------------------------------------
Every-occurrence attribution (DISCOVERY.md §5, HANDOFF.md §3 2026-08-11)
-----------------------------------------------------------------------
A label attaches to EVERY filing its paragraph(s) occur in, not only the
"home" filing where the paragraph was first deduplicated and labeled. This
is what lets text features cover filings whose own sections are mostly
verbatim-repeated boilerplate (46.5% of Risk Factors sections have zero
"home" chunks of their own).

Implementation note: `data/labels.parquet` already carries this
attribution baked in per-chunk (`source_accession_numbers`,
`source_filing_dates`, `source_forms` -- parallel arrays, one entry per
occurrence) -- these columns were themselves built from
`data/paragraph_occurrence_map.parquet` by unioning occurrences across a
chunk's `paragraph_ids`. This was independently verified before relying on
it at FULL CORPUS SCALE, not a sample: for every one of the 6,747 chunks in
`data/labels.parquet`, the union of `paragraph_occurrence_map.parquet`
occurrence accession numbers across that chunk's `paragraph_ids` was
compared against its stored `source_accession_numbers` -- 6,747/6,747
matched exactly, 0 violations. (An earlier draft of this docstring
understated this as verification "for a sampled chunk"; corrected here
after a red-team pass re-ran the check across the whole corpus and
confirmed the same zero-violation result the sampled check had suggested.)
`explode_label_occurrences()` below explodes those parallel arrays into one
row per (chunk, occurrence) -- this is equivalent to re-deriving the join
from `paragraph_occurrence_map.parquet` directly, not a shortcut around it.

No-backward-flow is enforced twice: (1) empirically, every chunk's
`home_filing_date` equals `min(source_filing_dates)` (verified corpus-wide,
100%) -- a label can never be earliest at a filing other than its home
filing; (2) defensively, `attach_company_and_verify_no_backward_flow()`
below raises if any occurrence's filing date precedes its own chunk's home
filing date, so a future corpus update that broke this silently would fail
loud, not pass silently.

`source_tickers` (a *deduplicated* per-chunk list, NOT parallel to
`source_accession_numbers`) is NOT used to resolve which company an
occurrence belongs to -- one chunk's occurrences can span >1 ticker (one
observed case: an 8-K cover-page checkbox sentence shared verbatim by BAC
and CVX), so ticker is instead resolved per-occurrence via
`accession_number -> ticker`, which is a true 1:1 mapping in this universe
(verified: no accession_number maps to >1 ticker in `filings.parquet`).

-----------------------------------------------------------------------
Red-flag features -- modality/section confound (REDTEAM_WEEK3.md #4,
RED_FLAGS_LIMITATION.md binding constraints)
-----------------------------------------------------------------------
Recomputed directly from the live `data/labels.parquet` (parse_ok rows
only) at build time -- see `recompute_modality_by_section()` and the
printed/report-embedded table; the HANDOFF §6 Step 3 reference numbers
(RISK_FACTORS HYP=2,049/REAL=706, MDA HYP=958/REAL=2,733) are treated as
provisional and NOT trusted blindly. (HANDOFF.md §2a flags its own Phase C
reference counts as needing re-verification against the regenerated
artifacts; this module does that re-verification at build time.)

Binding constraints applied (RED_FLAGS_LIMITATION.md "Binding implications
for Week 5"):
  1. Every red-flag feature inherits the measured 36.6% set-level error
     rate (63.4% agreement, 95% CI [58.6%, 68.0%], below the 0.70 bar).
     `RED_FLAG_CAVEAT` below is the exact string carried into
     features_report.md and backtest_report.md next to every red-flag
     feature claim.
  2. Modality (REALIZED vs HYPOTHETICAL) is the least reliable dimension
     (43 of 146 corrections were modality flips, 26 of those
     LEGAL_REGULATORY_ACTION) -- this module does NOT build any
     REALIZED-vs-HYPOTHETICAL split feature for ANY category (not just
     LEGAL_REGULATORY_ACTION -- applying the caution project-wide is a
     simplification documented here, not required literally by the
     constraint but chosen for a single, simply-defensible policy).
     Category-presence (any modality) is used throughout instead.
  3. Raw flag counts are not treated as comparable across section types.
     Category-presence rates are computed SEPARATELY for RISK_FACTORS and
     MDA (the two sections the redteam finding names), each normalized by
     the count of chunks actually attributed to that section for that
     filing (not by a fixed denominator) -- this controls for both
     section-type base-rate differences and per-filing section length.
     Explicit section-composition-share features are also included so a
     model can further control for mix even when rates are pooled.
  4. No distress-REALIZED features are built -- distress_tier is excluded
     from the feature set ENTIRELY (not just the REALIZED class), per
     HANDOFF §7 ("distress tier stays excluded from ... headline metrics")
     and the explicit Phase-C instruction to keep it out of headline
     features altogether.

-----------------------------------------------------------------------
Numeric fundamentals -- point-in-time discipline + the four named traps
-----------------------------------------------------------------------
Every numeric fact is read via `pit.value_as_of()`, scoped to
`filing_date` as the as-of date -- never `report_date`/`period_end`. Two
extra disciplines on top of `value_as_of()` itself:

  (c) Forms filter: `data/fundamentals.parquet` is filtered to
      form in {10-K, 10-Q, 8-K} BEFORE any lookup. This is what prevents
      MA's DEF 14A proxy compensation-table `NetIncomeLoss` rows (filed
      2026-04-27, covering fiscal years back to 2021) from leaking into a
      point-in-time numeric feature -- those rows are real XBRL facts but
      not from an operating filing, and would otherwise silently outrank
      MA's genuine (zero, in-window) `NetIncomeLoss` 10-K/10-Q coverage.

  (a/b) Concept families, not single tags: `OperatingIncomeLoss` has ZERO
      in-window coverage for 10 of 25 companies -- 9 never report the tag
      at all (BAC, COP, CVX, GS, JPM, MRK, OXY, PFE, XOM; the three banks
      by income-statement structure) plus JNJ, whose last such row is
      period_end 2015-03-29, i.e. before the window
      (`concept_tag_migrated_before_window`). SLB is NOT one of the 10 --
      it has *partial* in-window coverage (3/12 quarters) and is handled
      by its `ProfitLoss` alt tag. (HANDOFF.md §2a trap (a).)
      `NetIncomeLoss`/`OperatingIncomeLoss` migrate mid-window to
      `ProfitLoss` for MA/OXY and SLB respectively; `StockholdersEquity`
      is absent in-window for V/UNH/PG (uses
      `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`
      instead); `CashAndCashEquivalentsAtCarryingValue` is absent
      in-window for CVX/PG/SLB (each has its own restricted-cash-inclusive
      alt tag) AND, discovered by an independent red-team pass and fixed
      here, for JPM/BAC (banks report cash position under
      `CashAndDueFromBanks` instead -- confirmed directly against
      `data/raw/companyfacts/CIK0000019617.json` (JPM) and
      `CIK0000070858.json` (BAC): both banks' `CashAndCashEquivalentsAtCarryingValue`
      series stop cold (JPM's freshest row is period_end=2018-12-31, BAC's
      is 2020-09-30) while `CashAndDueFromBanks` continues reporting fresh
      values through the end of the corpus window for both). Before this
      fix, `resolve_concept_family()`'s freshest-wins logic still returned
      those stale 2018/2020 values for every JPM/BAC observation in the
      2023-2026 window (a real row existing at all was enough for
      `value_as_of()` to answer, exactly the MA/NetIncomeLoss failure mode
      already described below, just undetected for this pair because
      neither ticker was in `ALT_TAG_FAMILIES` yet) -- 24 JPM and 25 BAC
      observations were silently computing `cash_to_assets` off
      multi-year-stale balance-sheet data. GS is NOT added here: it
      reports its cash position under the plain
      `CashAndCashEquivalentsAtCarryingValue` tag normally and was never
      stale. `ALT_TAG_FAMILIES` below encodes exactly these documented,
      individually-verified migrations (never a blind "try every tag that
      sounds similar" heuristic) as an ordered ticker-specific fallback.

  (e) GENERAL STALENESS GUARD (added after the same red-team pass that
      found the JPM/BAC cash bug above, which was symptomatic of a broader
      unguarded failure mode): `resolve_concept_family()` -- and therefore
      every numeric feature, including the plain single-concept lookups for
      Assets/Liabilities/OCF/EPS that used to call `pit.value_as_of()`
      directly -- now discards the freshest-available candidate and returns
      `None` if that candidate's `period_end` is more than
      `STALENESS_MAX_DAYS` (200 days) stale relative to `as_of`, rather than
      silently returning a stale value just because SOME row exists. This
      is a `features.py`-side guard layered on top of `pit.value_as_of()`
      (which is deliberately NOT modified -- `value_as_of()`'s own contract
      is "return the freshest knowable row or None," and it is correct at
      that contract; "knowable but too old to trust as a current feature" is
      a feature-engineering judgment call, squarely this module's scope per
      `pit.py`'s own docstring). Concretely this fixes, independently of the
      JPM/BAC alt-tag fix above: JNJ's `OperatingIncomeLoss` (freshest row
      ever filed has period_end=2015-03-29 -- JNJ does not use this tag in
      the corpus window at all, so it now correctly resolves to `None`/NaN
      for all 26 JNJ observations, matching JNJ's listed membership in the
      "10 companies structurally absent for OperatingIncomeLoss" set two
      paragraphs up, which the pre-fix code silently contradicted for this
      one ticker); and MRK's `NetCashProvidedByUsedInOperatingActivities`
      for exactly one observation (its 2024-04-25 8-K) -- see
      `features_report.md`'s "Staleness guard" section for the full
      root-cause (MRK's FY2023 10-K, filed 2024-02-26, tagged operating
      cash flow under `NetCashProvidedByUsedInOperatingActivitiesContinuingOperations`
      instead of the plain tag for that one filing only, then reverted back
      to the plain tag from the FY2024 10-K onward -- a one-filing tag
      detour, not an ongoing migration, so not added to `ALT_TAG_FAMILIES`;
      the general guard is what neutralizes it instead of a dedicated
      alt-tag entry). `STALENESS_MAX_DAYS = 200` is justified in-code next
      to the constant; a full-corpus sweep against every resolved fact in
      this build is a permanent regression test
      (`test_no_resolved_fact_is_stale_beyond_guard` in
      `test_phase_c_leakage.py`).

      A GAP DISCOVERED WHILE BUILDING THIS FILE, not previously flagged in
      HANDOFF.md: `ingest_fundamentals.py`'s fixed `CONCEPTS` list (13
      tags) does NOT include `ProfitLoss`, `StockholdersEquityIncluding...`,
      or the restricted-cash alt tags -- even though its own
      `KNOWN_MIDWINDOW_MIGRATIONS` comments name them. So
      `data/fundamentals.parquet` alone cannot satisfy the "use
      alias/migration families" instruction for MA/OXY/SLB's post-migration
      period -- the alt-tag data simply isn't in that parquet.
      `load_supplemental_alt_tags()` resolves this by reading the ALREADY-
      CACHED raw companyfacts JSON directly from
      `data/raw/companyfacts/CIK##########.json` (written by
      `ingest_fundamentals.py`'s own prior run) and calling
      `ingest_fundamentals.extract_concept_facts()` (an unmodified, pure
      function of that JSON) for just the named alt concepts on just the
      named tickers. This makes ZERO network calls and ZERO calls to any
      Anthropic API -- it is a local, offline read of data this repo
      already fetched. It does not modify `ingest_fundamentals.py` or
      `data/fundamentals.parquet`; the supplemental rows exist only in
      this module's in-memory combined fundamentals frame.

  (d) GS revenue: `REVENUE_FAMILY_ORDER` tries
      `RevenueFromContractWithCustomerExcludingAssessedTax` ->
      `RevenueFromContractWithCustomerIncludingAssessedTax` -> `Revenues`
      -> `RevenuesNetOfInterestExpense` in that fixed order for every
      company; GS reports zero rows under the first three, so it resolves
      to its real, as-reported `RevenuesNetOfInterestExpense` tag
      naturally, without a GS-specific branch.

Scope kept modest and defensible (ratios/growth rates a numeric-only
baseline would plausibly build): leverage, equity ratio, cash ratio,
margins, cash-flow-to-revenue, and three period-matched YoY growth rates.
See NUMERIC_FEATURE_NAMES / features_report.md for the full list with
per-feature caveats (esp. which companies are structurally NaN for which
feature, and why).

-----------------------------------------------------------------------
Target -- forward excess return (owner-ratified 2026-08-18)
-----------------------------------------------------------------------
Next ~63-trading-day (one quarter) return for the filer, starting on the
FIRST TRADING DAY STRICTLY AFTER filing_date, minus the equal-weighted
average of the same-window return across all 25 universe tickers
(including the filer itself -- the ratified wording is "excess vs. the
25-stock universe average", and the filer is one of the 25; this choice is
stated explicitly here and in the report, not left implicit).
`build_target()` uses `DatetimeIndex.searchsorted(filing_date, side="right")`
to find the entry date, which by construction can never return a date
<= filing_date -- this is the structural mechanism the leakage test
`test_target_window_starts_after_filing_date` checks holds in practice, not
just in theory.

Prices are split-adjusted but NOT dividend-adjusted (`data/PRICES_NOTES.md`
§1) -- both `target_subject_return` and `target_universe_avg_return` share
this omission identically, so it is a modest, roughly-common-mode bias
across the 25 tickers, not a random-noise source, but a real limitation
carried into every downstream report verbatim.

Recent filings near the end of the priced window (today, per this
environment's clock, is 2026-08-18) do not yet have 63 subsequent trading
days of price history -- `build_target()` returns NaN target fields for
those and they are counted, not silently dropped, in features_report.md.
`backtest.py` drops NaN-target rows before modeling and reports the drop
count.
"""

from __future__ import annotations

import json
import datetime as _dt
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from ingest_fundamentals import extract_concept_facts
from pit import value_as_of

REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
RAW_COMPANYFACTS_DIR = DATA_DIR / "raw" / "companyfacts"

LABELS_PATH = DATA_DIR / "labels.parquet"
FILINGS_PATH = DATA_DIR / "filings.parquet"
FUNDAMENTALS_PATH = DATA_DIR / "fundamentals.parquet"
PRICES_PATH = DATA_DIR / "prices.parquet"
UNIVERSE_PATH = DATA_DIR / "universe.csv"

FEATURES_OUTPUT = DATA_DIR / "features.parquet"
FEATURES_REPORT_OUTPUT = DATA_DIR / "features_report.md"

FORWARD_WINDOW_TRADING_DAYS = 63
ALLOWED_FUNDAMENTALS_FORMS = {"10-K", "10-Q", "8-K"}

RED_FLAG_CAVEAT = (
    "Red-flag labels carry a measured 36.6% set-level error rate under "
    "spot-check adjudication (agreement 63.4%, 95% Wilson CI [58.6%, "
    "68.0%], below the 0.70 quality bar) -- see RED_FLAGS_LIMITATION.md. "
    "Any red-flag-derived feature, or a claim about its importance/"
    "ablation effect, inherits this uncertainty."
)

RED_FLAG_CATEGORIES = [
    "DEMAND_WEAKNESS",
    "IMPAIRMENT_WRITEDOWN",
    "LEGAL_REGULATORY_ACTION",
    "MARGIN_COST_PRESSURE",
    "SUPPLY_INPUT_CONSTRAINT",
    "TRADE_POLICY_EXPOSURE",
]

TEXT_SECTION_TYPES = ["RISK_FACTORS", "MDA", "EX99_PRESS_RELEASE", "8K_BODY"]

SENTIMENT_MAP = {"POSITIVE": 1.0, "NEUTRAL": 0.0, "NEGATIVE": -1.0}
# WITHDRAWN (n=1 corpus-wide) is folded into the same bucket as LOWERED for
# this signed-direction feature -- both are directionally negative guidance
# events; n=1 is too small to justify its own bucket, and HANDOFF §7 already
# marks WITHDRAWN as non-evaluable as a standalone class, not as unusable
# input. "NONE" (guidance section applicable, nothing given) and Python
# None (guidance not applicable to this section type) both map to NaN, i.e.
# excluded from the mean, not treated as a 0 (a real "maintained" signal).
GUIDANCE_MAP = {"RAISED": 1.0, "MAINTAINED": 0.0, "LOWERED": -1.0, "WITHDRAWN": -1.0}

# ---------------------------------------------------------------------------
# Numeric fundamentals: concept families (binding traps a-d, HANDOFF §2a)
# ---------------------------------------------------------------------------

REVENUE_FAMILY_ORDER = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "RevenuesNetOfInterestExpense",  # GS's real, as-reported top-line tag (trap d)
]

# Verified (not guessed) mid-window tag migrations/absences: NetIncomeLoss/
# OperatingIncomeLoss -> ProfitLoss entries come from ingest_fundamentals.py's
# own KNOWN_MIDWINDOW_MIGRATIONS comments (confirmed again here against the
# live fundamentals.parquet: MA/OXY have zero in-window 10-K/10-Q
# NetIncomeLoss rows, SLB has zero in-window OperatingIncomeLoss rows after
# its 2024-04-24 10-Q). The StockholdersEquity and cash alt tags were
# independently confirmed for this build by reading the raw cached
# companyfacts JSON for V/UNH/PG/CVX/SLB (see features_report.md
# "Numeric feature caveats" for the exact tags found and rejected).
#
# JPM/BAC CashAndDueFromBanks (added post-red-team-review, see module
# docstring point (e)): confirmed directly against the raw cached
# companyfacts JSON -- JPM's CashAndCashEquivalentsAtCarryingValue freshest
# row is period_end=2018-12-31 (16 rows total, none newer), BAC's is
# 2020-09-30 (184 rows total, none newer); both banks' CashAndDueFromBanks
# series report fresh values every quarter through the end of the corpus
# window (JPM 224 rows through 2026-06-30, BAC 106 rows through
# 2026-06-30). GS is deliberately NOT added here -- it reports cash under
# the plain CashAndCashEquivalentsAtCarryingValue tag normally and was
# never stale (verified: no GS observation trips the staleness guard below
# on this concept).
ALT_TAG_FAMILIES: dict[str, dict[str, list[str]]] = {
    "NetIncomeLoss": {
        "MA": ["ProfitLoss"],
        "OXY": ["ProfitLoss"],
    },
    "OperatingIncomeLoss": {
        "SLB": ["ProfitLoss"],
    },
    "StockholdersEquity": {
        "V": ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
        "UNH": ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
        "PG": ["StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    },
    "CashAndCashEquivalentsAtCarryingValue": {
        "CVX": ["CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
        "PG": ["CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
        "SLB": [
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsIncludingDisposalGroupAndDiscontinuedOperations"
        ],
        "JPM": ["CashAndDueFromBanks"],
        "BAC": ["CashAndDueFromBanks"],
    },
}

# ---------------------------------------------------------------------------
# General staleness guard (BLOCKER fix, red-team review) -- applies to every
# resolved fact, not just the alt-tag families above.
# ---------------------------------------------------------------------------
#
# STALENESS_MAX_DAYS = 200. Justification, grounded in this corpus's real
# data (not a value picked to hit a target split):
#   - This universe's reporting cadence is quarterly (~91 calendar days
#     between period ends). The longest normal gap between "period X's data
#     becomes public" and "period X+1's data becomes public" is one quarter
#     plus this universe's own filing lag (all 25 companies are large
#     accelerated filers; SEC deadlines top out at 40 days after quarter-end
#     for a 10-Q and ~60-75 days after fiscal year-end for a 10-K) -- i.e.
#     roughly 91 + 60-75 =~ 150-165 days in the worst realistic single-cycle
#     case, before the NEXT period's figure supersedes it.
#   - Empirically sweeping every real resolved value in this build (see
#     test_no_resolved_fact_is_stale_beyond_guard in test_phase_c_leakage.py)
#     shows every legitimate, non-broken resolution in the whole 630-
#     observation corpus sits at or below 198 days (JNJ's own late-April
#     earnings-release timing is the single closest case: its FY10-K does
#     not tag StockholdersEquity under this exact concept, so the freshest
#     figure available at 8-K time is the prior fiscal Q3, 198 days old --
#     a real, legitimate PIT answer, not a bug) -- with a sharp gap to the
#     broken cases this guard exists to catch (JNJ OperatingIncomeLoss
#     ~4,100+ days stale, JPM/BAC Cash ~1,700+/~1,300+ days stale before the
#     alt-tag fix above, MRK OCF 208 days stale from a one-filing tag
#     detour). 200 sits just above the legitimate 198-day case and just
#     below the first broken case (208 days) -- any threshold in roughly
#     200-207 would separate the same two groups on this real corpus; 200
#     is chosen as a clean, defensible "about two quarters" round number,
#     not reverse-engineered to an exact boundary.
STALENESS_MAX_DAYS = 200


def _is_stale(row: dict, as_of) -> bool:
    """True if `row`'s period_end is more than STALENESS_MAX_DAYS before
    `as_of` -- i.e. "knowable" per pit.value_as_of()'s contract but too old
    to trust as a current numeric feature. See STALENESS_MAX_DAYS above for
    the threshold's justification."""
    period_end = row.get("period_end")
    if period_end is None or (isinstance(period_end, float) and pd.isna(period_end)):
        return False
    days = (pd.Timestamp(as_of) - pd.Timestamp(period_end)).days
    return days > STALENESS_MAX_DAYS

NUMERIC_FEATURE_NAMES = [
    "log_total_assets",
    "leverage_liabilities_to_assets",
    "equity_to_assets",
    "cash_to_assets",
    "net_margin",
    "operating_margin",
    "operating_cashflow_to_revenue",
    "revenue_yoy_growth",
    "net_income_yoy_growth",
    "eps_diluted_yoy_growth",
]

TEXT_FEATURE_NAMES_NON_REDFLAG = [
    "n_text_chunks_attributed",
    "share_chunks_risk_factors",
    "share_chunks_mda",
    "share_chunks_ex99_press_release",
    "share_chunks_8k_body",
    "sentiment_mean_score",
    "sentiment_negative_share",
    "guidance_signed_mean",
    "guidance_any_present",
]

RED_FLAG_FEATURE_NAMES = [
    f"redflag_{cat}_rate_{sec.lower()}"
    for sec in ("RISK_FACTORS", "MDA")
    for cat in RED_FLAG_CATEGORIES
] + ["redflag_any_rate_press"]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_universe() -> pd.DataFrame:
    return pd.read_csv(UNIVERSE_PATH)


def load_filings_base() -> pd.DataFrame:
    """De-duplicate `filings.parquet` (one row per extracted section) down
    to one row per filing -- the unit of observation."""
    filings = pd.read_parquet(FILINGS_PATH)
    base = filings.drop_duplicates(["ticker", "cik", "accession_number", "filing_date", "form"])
    base = base[["ticker", "cik", "accession_number", "filing_date", "form"]].reset_index(drop=True)
    base["filing_date"] = pd.to_datetime(base["filing_date"])
    return base


def load_labels() -> pd.DataFrame:
    labels = pd.read_parquet(LABELS_PATH)
    labels = labels[labels["parse_ok"]].copy()  # drop the 1 genuine refusal row (CHK-8e69547e0900a8dd)
    return labels


def build_accession_to_company_map(filings_base: pd.DataFrame) -> pd.DataFrame:
    m = filings_base[["accession_number", "ticker", "cik"]].drop_duplicates()
    multi = m.groupby("accession_number")["ticker"].nunique()
    bad = multi[multi > 1]
    if not bad.empty:
        raise AssertionError(
            f"accession_number maps to >1 ticker for {list(bad.index)} -- "
            "the 1:1 accession_number->ticker assumption this module relies "
            "on to resolve occurrence ownership is broken."
        )
    return m.drop_duplicates("accession_number")


# ---------------------------------------------------------------------------
# Text features -- every-occurrence attribution
# ---------------------------------------------------------------------------


def explode_label_occurrences(labels: pd.DataFrame) -> pd.DataFrame:
    """One row per (chunk, occurrence). See module docstring "Every-
    occurrence attribution" for why this is equivalent to re-deriving the
    join from paragraph_occurrence_map.parquet directly."""
    records = []
    for row in labels.itertuples(index=False):
        accs = row.source_accession_numbers
        dates = row.source_filing_dates
        forms = row.source_forms
        for acc, dt, form in zip(accs, dates, forms):
            records.append(
                {
                    "chunk_id": row.chunk_id,
                    "occurrence_accession_number": acc,
                    "occurrence_filing_date": dt,
                    "occurrence_form": form,
                    "home_accession_number": row.home_accession_number,
                    "home_filing_date": row.home_filing_date,
                    "section_type": row.section_type,
                    "sentiment": row.sentiment,
                    "guidance_direction": row.guidance_direction,
                    "red_flags": row.red_flags,
                }
            )
    occ = pd.DataFrame.from_records(records)
    occ["occurrence_filing_date"] = pd.to_datetime(occ["occurrence_filing_date"])
    occ["home_filing_date"] = pd.to_datetime(occ["home_filing_date"])
    return occ


def attach_company_and_verify_no_backward_flow(
    occ: pd.DataFrame, acc_map: pd.DataFrame
) -> pd.DataFrame:
    merged = occ.merge(
        acc_map, left_on="occurrence_accession_number", right_on="accession_number", how="left"
    )
    missing = merged["ticker"].isna()
    if missing.any():
        raise AssertionError(
            f"{int(missing.sum())} label occurrences reference accession numbers "
            "absent from filings.parquet -- cannot resolve which company they belong to."
        )
    backward = merged["occurrence_filing_date"] < merged["home_filing_date"]
    if backward.any():
        raise AssertionError(
            f"{int(backward.sum())} label occurrences attach to a filing dated "
            "BEFORE their own chunk's home filing date -- this is exactly the "
            "backward-flow / look-ahead-bias failure mode every-occurrence "
            "attribution must never produce."
        )
    return merged


def recompute_modality_by_section(labels: pd.DataFrame) -> pd.DataFrame:
    """Recompute the section_type x modality red-flag table from the LIVE,
    final `labels.parquet`. The HANDOFF.md §6 Step 3 reference numbers
    (RISK_FACTORS HYP=2049/REAL=706, MDA HYP=958/REAL=2733) are provisional
    and are independently re-verified here rather than trusted."""
    rows = []
    for _, r in labels.iterrows():
        for flag in r["red_flags"]:
            rows.append({"section_type": r["section_type"], "modality": flag["modality"]})
    if not rows:
        return pd.DataFrame(columns=["section_type", "HYPOTHETICAL", "REALIZED"])
    df = pd.DataFrame(rows)
    table = df.groupby(["section_type", "modality"]).size().unstack(fill_value=0)
    for col in ("HYPOTHETICAL", "REALIZED"):
        if col not in table.columns:
            table[col] = 0
    return table[["HYPOTHETICAL", "REALIZED"]]


def build_text_features(occ_attached: pd.DataFrame) -> pd.DataFrame:
    df = occ_attached.copy()

    for cat in RED_FLAG_CATEGORIES:
        df[f"has_{cat}"] = df["red_flags"].apply(
            lambda flags, c=cat: any(f["category"] == c for f in flags)
        )
    df["has_any_red_flag"] = df["red_flags"].apply(lambda flags: len(flags) > 0)

    df["sentiment_num"] = df["sentiment"].map(SENTIMENT_MAP)
    df["guidance_num"] = df["guidance_direction"].map(GUIDANCE_MAP)

    key_cols = ["ticker", "occurrence_accession_number", "occurrence_filing_date"]
    grouped = df.groupby(key_cols)

    out = grouped.size().rename("n_text_chunks_attributed").reset_index()

    for sec in TEXT_SECTION_TYPES:
        share = grouped.apply(lambda g, s=sec: float((g["section_type"] == s).mean()), include_groups=False)
        out[f"share_chunks_{sec.lower()}"] = share.values

    out["sentiment_mean_score"] = grouped["sentiment_num"].mean().values

    def _neg_share(s: pd.Series) -> float:
        n = s.notna().sum()
        return float((s == -1.0).sum() / n) if n else np.nan

    out["sentiment_negative_share"] = grouped["sentiment_num"].apply(_neg_share).values
    out["guidance_signed_mean"] = grouped["guidance_num"].mean().values
    out["guidance_any_present"] = grouped["guidance_num"].apply(lambda s: float(s.notna().any())).values

    for sec in ["RISK_FACTORS", "MDA"]:
        sec_df = df[df["section_type"] == sec]
        sec_grouped = sec_df.groupby(key_cols)
        n_sec = sec_grouped.size().rename(f"n_chunks_{sec.lower()}").reset_index()
        out = out.merge(n_sec, on=key_cols, how="left")
        for cat in RED_FLAG_CATEGORIES:
            rate = sec_grouped[f"has_{cat}"].mean().rename(f"redflag_{cat}_rate_{sec.lower()}").reset_index()
            out = out.merge(rate, on=key_cols, how="left")

    press_df = df[df["section_type"] == "EX99_PRESS_RELEASE"]
    press_grouped = press_df.groupby(key_cols)
    rate = press_grouped["has_any_red_flag"].mean().rename("redflag_any_rate_press").reset_index()
    out = out.merge(rate, on=key_cols, how="left")

    out = out.rename(
        columns={
            "occurrence_accession_number": "accession_number",
            "occurrence_filing_date": "filing_date",
        }
    )
    return out


# ---------------------------------------------------------------------------
# Numeric fundamentals
# ---------------------------------------------------------------------------


def load_fundamentals_form_filtered() -> pd.DataFrame:
    fund = pd.read_parquet(FUNDAMENTALS_PATH)
    return fund[fund["form"].isin(ALLOWED_FUNDAMENTALS_FORMS)].copy()


def _cik_for_ticker(universe: pd.DataFrame, ticker: str) -> int:
    return int(universe.loc[universe["ticker"] == ticker, "cik"].iloc[0])


def load_supplemental_alt_tags(universe: pd.DataFrame) -> pd.DataFrame:
    """Pull the ALT_TAG_FAMILIES concepts directly from the already-cached
    raw companyfacts JSON (data/raw/companyfacts/) -- zero network calls,
    zero Anthropic API calls. See module docstring "Numeric fundamentals"
    for why this exists (a real gap in ingest_fundamentals.py's fixed
    concept list, discovered while building this file)."""
    cols = [
        "ticker", "cik", "taxonomy", "concept", "unit", "value", "fy", "fp",
        "period_start", "period_end", "form", "accession_number", "filed",
    ]
    rows: list[dict] = []
    for base_concept, per_ticker in ALT_TAG_FAMILIES.items():
        for ticker, alt_concepts in per_ticker.items():
            cik = _cik_for_ticker(universe, ticker)
            path = RAW_COMPANYFACTS_DIR / f"CIK{cik:010d}.json"
            if not path.exists():
                continue
            raw = json.loads(path.read_text())
            for alt_concept in alt_concepts:
                rows.extend(extract_concept_facts(raw, "us-gaap", alt_concept, ticker, cik))
    if not rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(rows)
    return df[df["form"].isin(ALLOWED_FUNDAMENTALS_FORMS)].copy()


def resolve_concept_family(
    fund_df: pd.DataFrame,
    concepts: list[str],
    ticker: str,
    cik: int,
    as_of,
    staleness_log: Optional[list[dict]] = None,
) -> tuple[Optional[dict], Optional[str]]:
    """Resolve a "family" of alias/migration tag names to a single value: try
    EVERY concept name in `concepts`, and among whichever ones return a row
    at all, return the one with the single most recent `period_end` (ties
    broken by `filed`, latest wins -- same discipline as pit.value_as_of()).

    This is NOT "first non-None in priority order" -- that would have been
    wrong here. A concrete bug this fixes, caught while building this file:
    MA's `NetIncomeLoss` tag has real rows, but the newest one has
    period_end=2014-03-31 (MA migrated to `ProfitLoss` afterward and never
    reported `NetIncomeLoss` again in a 10-K/10-Q). `value_as_of()` on
    `NetIncomeLoss` alone therefore does NOT return None for a 2024 as_of
    date -- it returns that decade-stale 2014 figure, silently, because
    "some row exists" is enough for value_as_of() to answer. A naive
    "primary-then-fallback-only-if-None" resolver would have kept using
    that stale value forever, never falling through to `ProfitLoss` at all.
    Comparing period_end across the whole family and taking the freshest
    is the correct fix, and generalizes to the revenue-alias case (several
    tickers report >1 revenue alias simultaneously in-window; freshest-wins
    handles that identically, no separate priority-order logic needed).

    GENERAL STALENESS GUARD (red-team BLOCKER fix): even the freshest
    candidate across the whole family can still be too old to trust (JNJ's
    OperatingIncomeLoss family has exactly one member, and its freshest row
    is over a decade stale -- there is nothing fresher to fall through to).
    If the chosen candidate is more than STALENESS_MAX_DAYS stale relative
    to `as_of` (see that constant's docstring), this returns `(None, None)`
    instead of the stale row -- the caller sees exactly the same "nothing
    knowable" signal it would see if no row existed at all, which is the
    correct treatment: a resolved-but-ancient fact is not a usable current
    feature. When `staleness_log` is provided (a list the caller owns), one
    dict describing the discarded candidate is appended to it so build-time
    diagnostics can report exactly what got guarded out and why (see
    features_report.md "Staleness guard" section).
    """
    candidates: list[tuple[dict, str]] = []
    for concept in concepts:
        row = value_as_of(fund_df, concept, as_of, ticker=ticker, cik=cik, taxonomy="us-gaap")
        if row is not None:
            candidates.append((row, concept))
    if not candidates:
        return None, None
    candidates.sort(key=lambda item: (pd.Timestamp(item[0]["period_end"]), pd.Timestamp(item[0]["filed"])))
    chosen_row, chosen_concept = candidates[-1]
    if _is_stale(chosen_row, as_of):
        if staleness_log is not None:
            days_stale = (pd.Timestamp(as_of) - pd.Timestamp(chosen_row["period_end"])).days
            staleness_log.append(
                {
                    "ticker": ticker,
                    "cik": cik,
                    "as_of": pd.Timestamp(as_of),
                    "concept_family": concepts[0],
                    "concept_resolved": chosen_concept,
                    "period_end": pd.Timestamp(chosen_row["period_end"]),
                    "days_stale": days_stale,
                }
            )
        return None, None
    return chosen_row, chosen_concept


def resolve_family_value(
    fund_df: pd.DataFrame,
    base_concept: str,
    ticker: str,
    cik: int,
    as_of,
    staleness_log: Optional[list[dict]] = None,
) -> tuple[Optional[dict], Optional[str]]:
    concepts = [base_concept] + ALT_TAG_FAMILIES.get(base_concept, {}).get(ticker, [])
    return resolve_concept_family(fund_df, concepts, ticker, cik, as_of, staleness_log=staleness_log)


def resolve_revenue_value(
    fund_df: pd.DataFrame, ticker: str, cik: int, as_of, staleness_log: Optional[list[dict]] = None
) -> tuple[Optional[dict], Optional[str]]:
    return resolve_concept_family(fund_df, REVENUE_FAMILY_ORDER, ticker, cik, as_of, staleness_log=staleness_log)


def resolve_single_concept(
    fund_df: pd.DataFrame, concept: str, ticker: str, cik: int, as_of, staleness_log: Optional[list[dict]] = None
) -> tuple[Optional[dict], Optional[str]]:
    """Single-concept convenience wrapper around resolve_concept_family() --
    routes the plain Assets/Liabilities/OCF/EPS lookups (previously raw
    pit.value_as_of() calls with no staleness guard at all) through the same
    freshest-wins-then-guard machinery as the multi-tag families, so the
    staleness guard applies uniformly to every numeric feature, not just the
    ones that happen to have a documented alt tag."""
    return resolve_concept_family(fund_df, [concept], ticker, cik, as_of, staleness_log=staleness_log)


def value_for_target_period(
    df: pd.DataFrame,
    concept: str,
    ticker: str,
    cik: int,
    as_of,
    target_period_end,
    duration_days: Optional[float] = None,
    end_tolerance_days: int = 45,
    duration_tolerance_days: int = 20,
) -> Optional[dict]:
    """Same PIT selection discipline as pit.value_as_of() (filed <= as_of,
    then latest-filed with accession_number tiebreak) but for a
    CALLER-SPECIFIED target period rather than "the latest known period" --
    used to find the prior-year comparable period for a YoY growth feature.
    This is squarely a features.py-scope decision per pit.py's own
    docstring ("resolving that ambiguity is a feature-engineering decision,
    (features.py's scope)").

    Deliberately NOT routed through the STALENESS_MAX_DAYS guard used by
    resolve_concept_family(): this function's whole purpose is to find a
    value from ~1 year (period-matched YoY) before the CURRENT period, so
    its result's `period_end` is expected and correct to be ~365+ days
    before `as_of` -- applying the same "too old to trust" guard here would
    incorrectly null out every legitimate YoY lookup. `end_tolerance_days`/
    `duration_tolerance_days` are this function's own, differently-scoped
    staleness-like checks (closeness to the TARGET period, not to `as_of`).
    """
    subset = df[(df["concept"] == concept) & (df["ticker"] == ticker) & (df["cik"] == int(cik))]
    if subset.empty:
        return None
    as_of_ts = pd.Timestamp(as_of)
    filed_ts = pd.to_datetime(subset["filed"])
    subset = subset[filed_ts.values <= as_of_ts.to_datetime64()]
    if subset.empty:
        return None

    period_end_ts = pd.to_datetime(subset["period_end"])
    target_ts = pd.Timestamp(target_period_end)
    close_enough = (period_end_ts - target_ts).abs().dt.days <= end_tolerance_days
    subset = subset[close_enough.values]
    if subset.empty:
        return None

    if duration_days is not None:
        period_start_ts = pd.to_datetime(subset["period_start"])
        has_start = period_start_ts.notna()
        subset = subset[has_start.values]
        if subset.empty:
            return None
        period_start_ts = pd.to_datetime(subset["period_start"])
        durations = (pd.to_datetime(subset["period_end"]) - period_start_ts).dt.days
        dur_ok = (durations - duration_days).abs() <= duration_tolerance_days
        subset = subset[dur_ok.values]
        if subset.empty:
            return None

    subset = subset.assign(_filed_ts=pd.to_datetime(subset["filed"]))
    subset = subset.sort_values(["_filed_ts", "accession_number"])
    return subset.iloc[-1].drop(labels=["_filed_ts"]).to_dict()


def _safe_div(numerator, denominator, min_abs_denom: float = 1e-6) -> float:
    if numerator is None or denominator is None:
        return np.nan
    if pd.isna(numerator) or pd.isna(denominator):
        return np.nan
    if abs(denominator) < min_abs_denom:
        return np.nan
    return float(numerator) / float(denominator)


def yoy_growth(
    fund_df: pd.DataFrame, concept: Optional[str], ticker: str, cik: int, as_of, current_row: Optional[dict]
) -> float:
    """(current - prior) / |prior|, where "prior" is the value for the
    period ending ~1 year before the current period's own period_end, of
    matching duration, known as of the SAME as_of date as current_row.
    Using |prior| in the denominator (rather than plain current/prior - 1)
    keeps sign meaningful when prior is negative (e.g. a loss-to-profit
    swing) instead of producing a sign-inverted growth number -- documented
    here, not a silently "clever" choice.
    """
    if concept is None or current_row is None:
        return np.nan
    current_value = current_row.get("value")
    if current_value is None or pd.isna(current_value):
        return np.nan
    period_end = current_row["period_end"]
    period_start = current_row.get("period_start")
    duration = None
    if period_start is not None and not (isinstance(period_start, float) and pd.isna(period_start)):
        duration = (pd.Timestamp(period_end) - pd.Timestamp(period_start)).days
    target_period_end = pd.Timestamp(period_end) - pd.DateOffset(years=1)
    prior = value_for_target_period(fund_df, concept, ticker, cik, as_of, target_period_end, duration_days=duration)
    if prior is None:
        return np.nan
    prior_value = prior.get("value")
    if prior_value is None or pd.isna(prior_value) or abs(prior_value) < 1e-6:
        return np.nan
    return float(current_value - prior_value) / abs(float(prior_value))


def build_numeric_features(base: pd.DataFrame, universe: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Returns (numeric_features_df, staleness_log) -- staleness_log is a
    flat list of every fact discarded by the STALENESS_MAX_DAYS guard across
    every concept/ticker/observation in this build, for features_report.md's
    "Staleness guard" section (see resolve_concept_family()'s docstring)."""
    primary = load_fundamentals_form_filtered()
    alt = load_supplemental_alt_tags(universe)
    fund = pd.concat([primary, alt], ignore_index=True) if not alt.empty else primary

    staleness_log: list[dict] = []
    records = []
    for row in base.itertuples(index=False):
        ticker, cik, acc, filing_date = row.ticker, row.cik, row.accession_number, row.filing_date
        as_of = filing_date

        # Assets/Liabilities/OCF/EPS are single-concept lookups (no
        # documented alt-tag family), but they still route through
        # resolve_single_concept() -- a thin wrapper over
        # resolve_concept_family() -- so the general staleness guard applies
        # to them exactly as it does to the multi-tag families below. This
        # replaces four previously-unguarded raw pit.value_as_of() calls.
        assets_row, _ = resolve_single_concept(fund, "Assets", ticker, cik, as_of, staleness_log=staleness_log)
        liab_row, _ = resolve_single_concept(fund, "Liabilities", ticker, cik, as_of, staleness_log=staleness_log)
        equity_row, _ = resolve_family_value(fund, "StockholdersEquity", ticker, cik, as_of, staleness_log=staleness_log)
        cash_row, _ = resolve_family_value(
            fund, "CashAndCashEquivalentsAtCarryingValue", ticker, cik, as_of, staleness_log=staleness_log
        )
        revenue_row, revenue_concept = resolve_revenue_value(fund, ticker, cik, as_of, staleness_log=staleness_log)
        ni_row, ni_concept = resolve_family_value(fund, "NetIncomeLoss", ticker, cik, as_of, staleness_log=staleness_log)
        oi_row, oi_concept = resolve_family_value(
            fund, "OperatingIncomeLoss", ticker, cik, as_of, staleness_log=staleness_log
        )
        ocf_row, _ = resolve_single_concept(
            fund, "NetCashProvidedByUsedInOperatingActivities", ticker, cik, as_of, staleness_log=staleness_log
        )
        eps_row, _ = resolve_single_concept(
            fund, "EarningsPerShareDiluted", ticker, cik, as_of, staleness_log=staleness_log
        )

        assets = assets_row["value"] if assets_row else np.nan
        liabilities = liab_row["value"] if liab_row else np.nan
        equity = equity_row["value"] if equity_row else np.nan
        cash = cash_row["value"] if cash_row else np.nan
        revenue = revenue_row["value"] if revenue_row else np.nan
        net_income = ni_row["value"] if ni_row else np.nan
        operating_income = oi_row["value"] if oi_row else np.nan
        ocf = ocf_row["value"] if ocf_row else np.nan

        revenue_yoy = yoy_growth(fund, revenue_concept, ticker, cik, as_of, revenue_row)
        ni_yoy = yoy_growth(fund, ni_concept, ticker, cik, as_of, ni_row)
        eps_yoy = yoy_growth(fund, "EarningsPerShareDiluted", ticker, cik, as_of, eps_row)

        records.append(
            {
                "ticker": ticker,
                "accession_number": acc,
                "filing_date": filing_date,
                "log_total_assets": float(np.log(assets)) if assets and assets > 0 else np.nan,
                "leverage_liabilities_to_assets": _safe_div(liabilities, assets),
                "equity_to_assets": _safe_div(equity, assets),
                "cash_to_assets": _safe_div(cash, assets),
                "net_margin": _safe_div(net_income, revenue),
                "operating_margin": _safe_div(operating_income, revenue),
                "operating_cashflow_to_revenue": _safe_div(ocf, revenue),
                "revenue_yoy_growth": revenue_yoy,
                "net_income_yoy_growth": ni_yoy,
                "eps_diluted_yoy_growth": eps_yoy,
                "_revenue_concept_used": revenue_concept,
                "_net_income_concept_used": ni_concept,
                "_operating_income_concept_used": oi_concept,
            }
        )
    return pd.DataFrame(records), staleness_log


# ---------------------------------------------------------------------------
# Target -- forward excess return
# ---------------------------------------------------------------------------


def load_price_panel() -> dict[str, pd.Series]:
    prices = pd.read_parquet(PRICES_PATH)
    prices["date"] = pd.to_datetime(prices["date"])
    panel = {}
    for ticker, g in prices.groupby("ticker"):
        s = g.sort_values("date").set_index("date")["close"]
        s = s[~s.index.duplicated(keep="last")]
        panel[ticker] = s
    return panel


def _asof_price(s: pd.Series, target_date) -> Optional[float]:
    pos = s.index.searchsorted(target_date, side="right") - 1
    if pos < 0:
        return None
    return float(s.iloc[pos])


def _nan_target_row(ticker, acc, filing_date, start_date=None, end_date=None, subj_return=None) -> dict:
    return {
        "ticker": ticker,
        "accession_number": acc,
        "filing_date": filing_date,
        "target_start_date": start_date,
        "target_end_date": end_date,
        "target_subject_return": subj_return,
        "target_universe_avg_return": np.nan,
        "target_excess_return": np.nan,
        "target_n_universe_constituents": 0,
    }


def build_target(
    base: pd.DataFrame,
    panel: dict[str, pd.Series],
    universe_tickers: list[str],
    holding_days: int = FORWARD_WINDOW_TRADING_DAYS,
) -> pd.DataFrame:
    records = []
    for row in base.itertuples(index=False):
        ticker, acc, filing_date = row.ticker, row.accession_number, row.filing_date
        s = panel.get(ticker)
        if s is None or s.empty:
            records.append(_nan_target_row(ticker, acc, filing_date))
            continue

        idx = s.index
        # First trading day STRICTLY after filing_date. side="right" on a
        # sorted index returns i such that idx[:i] <= filing_date < idx[i:]
        # -- idx[pos], if it exists, is by construction > filing_date; this
        # is the structural guarantee "never let the window start on or
        # before filing_date" rests on.
        pos = idx.searchsorted(filing_date, side="right")
        if pos >= len(idx):
            records.append(_nan_target_row(ticker, acc, filing_date))
            continue
        start_date = idx[pos]
        if start_date <= pd.Timestamp(filing_date):
            raise AssertionError(
                f"target start_date {start_date} <= filing_date {filing_date} for "
                f"{ticker}/{acc} -- searchsorted(side='right') invariant violated."
            )

        end_pos = pos + holding_days
        if end_pos >= len(idx):
            records.append(_nan_target_row(ticker, acc, filing_date, start_date=start_date))
            continue
        end_date = idx[end_pos]

        start_price = float(s.iloc[pos])
        end_price = float(s.iloc[end_pos])
        subj_return = end_price / start_price - 1.0

        universe_returns = []
        for u_ticker in universe_tickers:
            u_s = panel.get(u_ticker)
            if u_s is None or u_s.empty:
                continue
            p0 = _asof_price(u_s, start_date)
            p1 = _asof_price(u_s, end_date)
            if p0 is None or p1 is None or p0 == 0:
                continue
            universe_returns.append(p1 / p0 - 1.0)

        if not universe_returns:
            records.append(
                _nan_target_row(ticker, acc, filing_date, start_date=start_date, end_date=end_date, subj_return=subj_return)
            )
            continue

        universe_avg_return = float(np.mean(universe_returns))
        records.append(
            {
                "ticker": ticker,
                "accession_number": acc,
                "filing_date": filing_date,
                "target_start_date": start_date,
                "target_end_date": end_date,
                "target_subject_return": subj_return,
                "target_universe_avg_return": universe_avg_return,
                "target_excess_return": subj_return - universe_avg_return,
                "target_n_universe_constituents": len(universe_returns),
            }
        )
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def build_feature_table() -> tuple[pd.DataFrame, dict]:
    """Returns (features_df, diagnostics) -- diagnostics feeds
    features_report.md so the report is generated from the same run, not
    hand-typed separately."""
    universe = load_universe()
    filings_base = load_filings_base()
    labels = load_labels()
    acc_map = build_accession_to_company_map(filings_base)

    occ = explode_label_occurrences(labels)
    occ_attached = attach_company_and_verify_no_backward_flow(occ, acc_map)
    modality_table = recompute_modality_by_section(labels)
    text_features = build_text_features(occ_attached)

    numeric_features, staleness_log = build_numeric_features(filings_base, universe)

    panel = load_price_panel()
    target = build_target(filings_base, panel, universe["ticker"].tolist())

    out = filings_base.merge(text_features, on=["ticker", "accession_number", "filing_date"], how="left")
    out = out.merge(numeric_features, on=["ticker", "accession_number", "filing_date"], how="left")
    out = out.merge(target, on=["ticker", "accession_number", "filing_date"], how="left")

    # Text-derived columns fall into THREE groups on fillna behavior (MINOR
    # #8 fix, red-team review -- there used to be only two groups, which
    # wrongly 0-filled the redflag rate columns below):
    #   - counts/shares (n_text_chunks_attributed, share_chunks_*,
    #     n_chunks_risk_factors, n_chunks_mda, guidance_any_present): 0 is a
    #     well-defined, correct answer to "how many / what fraction" when a
    #     filing has zero attributed chunks (overall or of the relevant
    #     sub-type) -- fillna(0.0) is exactly right for these.
    #   - mean-score columns (sentiment_mean_score, sentiment_negative_share,
    #     guidance_signed_mean): legitimately UNDEFINED, not zero, when no
    #     chunk of the relevant type was attributed (e.g. a filing whose only
    #     attributed chunks are RISK_FACTORS, which never carry sentiment --
    #     "no sentiment signal" is not the same claim as "0, i.e. neutral").
    #     Left as NaN.
    #   - redflag_*_rate_risk_factors / redflag_*_rate_mda / redflag_any_rate_press
    #     (RED_FLAG_FEATURE_NAMES): these are RATES computed only over chunks
    #     of a specific section type (RISK_FACTORS, MDA, EX99_PRESS_RELEASE).
    #     When a filing has ZERO chunks of that section type attributed, the
    #     rate is UNDEFINED ("not assessed"), not 0 ("assessed, flag-free")
    #     -- the pre-fix code 0-filled these, silently conflating the two
    #     (55.9% of 10-Qs and ~100% of 8-Ks have zero RISK_FACTORS chunks of
    #     their own, per the section-composition numbers below, meaning most
    #     of the corpus was getting a confident-looking 0.0 "no red flags"
    #     rate for a section that was never actually read for this filing).
    #     Left as NaN, exactly like the mean-score columns; XGBoost's native
    #     missing-value handling treats "not assessed" as unknown rather than
    #     as a confident flag-free signal, the same discipline already
    #     applied to sentiment/guidance and to the numeric fundamentals.
    text_cols = [c for c in text_features.columns if c not in ("ticker", "accession_number", "filing_date")]
    mean_score_cols = {"sentiment_mean_score", "sentiment_negative_share", "guidance_signed_mean"}
    redflag_rate_cols = {c for c in text_cols if c.startswith("redflag_")}
    zero_fill_cols = [c for c in text_cols if c not in mean_score_cols and c not in redflag_rate_cols]
    n_zero_text = int(out["n_text_chunks_attributed"].isna().sum())
    # Counts of "section had zero attributed chunks" BEFORE fillna, for the
    # features_report.md 0-vs-NaN write-up of how many observations this
    # NaN-vs-0 policy change actually affects.
    n_zero_risk_factors_section = int(out["n_chunks_risk_factors"].isna().sum())
    n_zero_mda_section = int(out["n_chunks_mda"].isna().sum())
    n_zero_press_section = int(out["redflag_any_rate_press"].isna().sum())
    out[zero_fill_cols] = out[zero_fill_cols].fillna(0.0)

    diagnostics = {
        "n_observations": len(out),
        "n_zero_text_coverage": n_zero_text,
        "n_target_usable": int(out["target_excess_return"].notna().sum()),
        "n_target_incomplete_window": int(out["target_excess_return"].isna().sum()),
        "modality_table": modality_table,
        "numeric_missingness": {c: float(out[c].isna().mean()) for c in NUMERIC_FEATURE_NAMES},
        "revenue_concept_used_counts": out["_revenue_concept_used"].value_counts(dropna=False).to_dict(),
        "net_income_concept_used_counts": out["_net_income_concept_used"].value_counts(dropna=False).to_dict(),
        "operating_income_concept_used_counts": out["_operating_income_concept_used"].value_counts(dropna=False).to_dict(),
        "date_range": (str(out["filing_date"].min().date()), str(out["filing_date"].max().date())),
        "per_ticker_counts": out["ticker"].value_counts().sort_index().to_dict(),
        "form_counts": out["form"].value_counts().to_dict(),
        "staleness_log": staleness_log,
        "n_zero_risk_factors_section": n_zero_risk_factors_section,
        "n_zero_mda_section": n_zero_mda_section,
        "n_zero_press_section": n_zero_press_section,
    }
    return out, diagnostics


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

FEATURE_DICTIONARY: list[tuple[str, str, str]] = [
    # (feature name, source, caveat)
    ("n_text_chunks_attributed", "labels.parquet, every-occurrence attribution", "0 = filing has no attributed labeled text at all (own or inherited); not missing-at-random."),
    ("share_chunks_risk_factors", "labels.parquet section_type composition", "Section-composition control for the modality/section confound (REDTEAM #4)."),
    ("share_chunks_mda", "labels.parquet section_type composition", "See above."),
    ("share_chunks_ex99_press_release", "labels.parquet section_type composition", "See above."),
    ("share_chunks_8k_body", "labels.parquet section_type composition", "n=8 corpus-wide, 2 tickers only (HANDOFF §7) -- expect near-zero variance."),
    ("sentiment_mean_score", "labels.parquet sentiment (POSITIVE/NEUTRAL/NEGATIVE -> +1/0/-1)", "RISK_FACTORS chunks never carry sentiment (rubric applicability matrix); mean excludes them, not zero-fills."),
    ("sentiment_negative_share", "labels.parquet sentiment", "Same exclusion as above."),
    ("guidance_signed_mean", "labels.parquet guidance_direction (RAISED/MAINTAINED/LOWERED/WITHDRAWN -> +1/0/-1/-1)", "Extremely sparse corpus-wide (83 non-NONE labels total across 6,746 chunks); left as genuine NaN (not 0-filled) when no guidance-bearing chunk is attributed, so XGBoost's native missing-value handling treats it as unknown rather than 'maintained' -- see guidance_any_present (0-filled) to distinguish 'no guidance signal seen' from 'maintained'."),
    ("guidance_any_present", "labels.parquet guidance_direction", "1 if ANY RAISED/MAINTAINED/LOWERED/WITHDRAWN chunk attributed, else 0."),
    ("n_chunks_risk_factors", "labels.parquet section_type composition", "Count of RISK_FACTORS chunks attributed to this filing. Load-bearing: it is the denominator for the `redflag_*_rate_risk_factors` columns and the switch that decides NaN vs. a real rate -- see 'Section-rate missingness policy' below."),
    ("n_chunks_mda", "labels.parquet section_type composition", "Count of MDA chunks attributed to this filing. Same role as above for the `redflag_*_rate_mda` columns."),
    (f"redflag_<CATEGORY>_rate_risk_factors (x{len(RED_FLAG_CATEGORIES)})", "labels.parquet red_flags, RISK_FACTORS chunks only", RED_FLAG_CAVEAT + " Category-presence (any modality), NOT a REALIZED/HYPOTHETICAL split -- per RED_FLAGS_LIMITATION.md binding constraint #2. 0-vs-NaN fix: NaN (not 0) when the filing has zero attributed RISK_FACTORS chunks -- 'not assessed' is not the same claim as 'assessed, flag-free'; see 'Section-rate missingness policy' below."),
    (f"redflag_<CATEGORY>_rate_mda (x{len(RED_FLAG_CATEGORIES)})", "labels.parquet red_flags, MDA chunks only", RED_FLAG_CAVEAT + " Same category-presence policy; computed separately from RISK_FACTORS per binding constraint #3 (section-type base rates differ sharply -- see recomputed modality table in this report). 0-vs-NaN fix: NaN (not 0) when the filing has zero attributed MDA chunks; see 'Section-rate missingness policy' below."),
    ("redflag_any_rate_press", "labels.parquet red_flags, EX99_PRESS_RELEASE chunks only", RED_FLAG_CAVEAT + " Single pooled any-category rate (not split by category) to keep the feature set modest. 0-vs-NaN fix: NaN (not 0) when the filing has zero attributed press-release chunks (true for effectively all 10-Q/10-K observations); see 'Section-rate missingness policy' below."),
    ("log_total_assets", "fundamentals.parquet Assets, via pit.value_as_of()", "Size control; log-transformed (raw USD spans ~9 orders of magnitude across the universe)."),
    ("leverage_liabilities_to_assets", "fundamentals.parquet Liabilities/Assets", "Liabilities is structurally absent for ABBV/KO/MRK/OXY/WMT/MCD (6/25) -- NaN for those, not zero. See fundamentals_validation_problems."),
    ("equity_to_assets", "fundamentals.parquet StockholdersEquity family/Assets; alt tag for V/UNH/PG from raw companyfacts (see note above)", "Broader coverage than the leverage ratio above (equity-tag alt resolved for V/UNH/PG); use as the primary leverage-direction feature."),
    ("cash_to_assets", "fundamentals.parquet cash family/Assets; alt tags from raw companyfacts (see note above)", "Alt cash tag resolved for CVX/PG/SLB, and (red-team fix) JPM/BAC -> CashAndDueFromBanks (see ALT_TAG_FAMILIES) -- JPM/BAC previously computed this off multi-year-stale balance-sheet data silently; see 'Staleness guard' section below."),
    ("net_margin", "fundamentals.parquet net income family/revenue family; `ProfitLoss` (50 obs) from raw companyfacts (see note above)", "Duration-invariant (numerator/denominator share the same disclosed period, whether quarterly or annual) -- see module docstring for why this matters."),
    ("operating_margin", "fundamentals.parquet operating income family/revenue family; `ProfitLoss` (24 obs) from raw companyfacts (see note above)", "NaN wherever the operating-income family has no in-window coverage -- **10 of 25 companies**: nine never report `OperatingIncomeLoss` at all (BAC, COP, CVX, GS, JPM, MRK, OXY, PFE, XOM -- the three banks have no GAAP operating-income line by income-statement structure), plus JNJ, whose last such row is period_end 2015-03-29, before the window (`concept_tag_migrated_before_window`). SLB is a SEPARATE case and is not one of the 10: it has PARTIAL in-window coverage (3/12 quarters) and resolves via its `ProfitLoss` alt tag. See 'Staleness guard' below for the fix that makes JNJ correctly NaN instead of silently using a 2015 figure."),
    ("operating_cashflow_to_revenue", "fundamentals.parquet NetCashProvidedByUsedInOperatingActivities/revenue family", "Same duration-invariance property as margins. Can exceed 1.0 for the three banks (JPM/BAC/GS) whose operating cash flow includes large deposit-taking/lending balance-sheet swings not comparable to an industrial company's operating cash flow -- a real accounting-structure difference, not a data error."),
    ("revenue_yoy_growth", "fundamentals.parquet revenue family, period-matched YoY", "(current-prior)/|prior|; period-matching tolerance ±45 days on period_end, ±20 days on duration."),
    ("net_income_yoy_growth", "fundamentals.parquet net income family, period-matched YoY", "Can be a large or sign-flipped-looking number when prior-period net income is near zero -- guarded (NaN) only below |prior|<1e-6, not winsorized further; a known, documented modesty limit, not a bug."),
    ("eps_diluted_yoy_growth", "fundamentals.parquet EarningsPerShareDiluted, period-matched YoY", "V has never reported this tag at all (structurally absent) -- NaN for all V observations."),
]


def write_features_report(diagnostics: dict) -> None:
    lines = []
    lines.append("# FinScreen Phase C -- features.py report")
    lines.append("")
    lines.append(
        f"*Generated by `features.py` on "
        f"{_dt.datetime.now().strftime('%Y-%m-%d %H:%M')} from `data/labels.parquet`, "
        f"`data/filings.parquet`, `data/fundamentals.parquet` (+ cached "
        f"`data/raw/companyfacts/`) and `data/prices.parquet`, producing "
        f"`data/features.parquet` with {diagnostics['n_observations']} rows. "
        f"Re-running `features.py` overwrites this file -- if you are reading it as a "
        f"go/no-go gate file, check that this stamp is the vintage you were pointed at.*"
    )
    lines.append("")
    lines.append(
        "Generated by `features.py`. This documents every feature in "
        "`data/features.parquet`, its source, and its caveats, plus the "
        "build-time diagnostics used to sanity-check the join. See "
        "`features.py`'s module docstring for the full design rationale "
        "(every-occurrence attribution, PIT discipline, the four numeric "
        "fundamentals traps, and the target definition)."
    )
    lines.append("")
    lines.append("## Observation counts")
    lines.append("")
    lines.append(f"- Total (company, filing) observations: **{diagnostics['n_observations']}**")
    lines.append(
        f"- Filing date range: {diagnostics['date_range'][0]} to {diagnostics['date_range'][1]}"
    )
    lines.append(f"- Form breakdown: {diagnostics['form_counts']}")
    lines.append(
        f"- Observations with ZERO attributed text (own or every-occurrence-inherited): "
        f"**{diagnostics['n_zero_text_coverage']}** (text feature columns filled 0.0 for these -- "
        "genuinely no signal, not missing-at-random)."
    )
    lines.append(
        f"- Observations with a complete 63-trading-day forward target window: "
        f"**{diagnostics['n_target_usable']}**"
    )
    lines.append(
        f"- Observations with an INCOMPLETE forward window (too close to the current data "
        f"snapshot to have 63 subsequent trading days yet): "
        f"**{diagnostics['n_target_incomplete_window']}** -- kept in features.parquet with NaN "
        "target fields, dropped by backtest.py before modeling (count re-reported there)."
    )
    lines.append("")
    lines.append("### Per-ticker observation counts")
    lines.append("")
    lines.append("| Ticker | N |")
    lines.append("|---|---|")
    for t, n in diagnostics["per_ticker_counts"].items():
        lines.append(f"| {t} | {n} |")
    lines.append("")

    lines.append("## Red-flag modality x section_type (recomputed from live labels.parquet)")
    lines.append("")
    lines.append(
        "`HANDOFF.md` §6 Step 3's reference numbers for this table are provisional, so this "
        "table is recomputed directly from `data/labels.parquet` (parse_ok rows only) at build "
        "time rather than trusted blindly."
    )
    lines.append("")
    mt = diagnostics["modality_table"]
    lines.append("| section_type | HYPOTHETICAL | REALIZED |")
    lines.append("|---|---|---|")
    for sec, row in mt.iterrows():
        lines.append(f"| {sec} | {int(row['HYPOTHETICAL'])} | {int(row['REALIZED'])} |")
    lines.append("")
    lines.append(
        "This confirms the REDTEAM_WEEK3.md #4 confound persists post-relabel: RISK_FACTORS "
        "skews HYPOTHETICAL, MDA skews REALIZED. Red-flag features below are therefore computed "
        "separately per section (never pooled) and use category-presence, not a "
        "REALIZED/HYPOTHETICAL split, in the headline feature set."
    )
    lines.append("")

    lines.append("## Numeric fundamentals -- concept resolution and missingness")
    lines.append("")
    lines.append(
        "Concept-family resolution picks the SINGLE MOST RECENT `period_end` across every tag "
        "name in a family (base tag + documented alt tags), not \"first non-None in a fixed "
        "priority order.\" This matters concretely: MA's `NetIncomeLoss` tag has real historical "
        "rows, but the newest one is period_end=2014-03-31 (MA migrated to `ProfitLoss` "
        "afterward and never reported `NetIncomeLoss` again in a 10-K/10-Q) -- a naive "
        "\"primary-then-fallback-only-if-None\" resolver would silently return that decade-stale "
        "2014 figure for every 2023-2026 observation (value_as_of() does not return None just "
        "because the freshest available row is old; a row existing at all is enough). Caught and "
        "fixed while building this file -- see `resolve_concept_family()`'s docstring."
    )
    lines.append("")
    lines.append(
        "**Two different sources feed the numeric features, and only one of them is validated.** "
        "The 13 concepts in `data/fundamentals.parquet` went through `ingest_fundamentals.py` and "
        "are covered by the `fundamentals_validation_problems` WARN table (40 WARN / 0 FATAL "
        "across five categories). The `ALT_TAG_FAMILIES` concepts are NOT in that parquet at all "
        "-- `ProfitLoss`, "
        "`StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`, "
        "`CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents`"
        "(`IncludingDisposalGroupAndDiscontinuedOperations`) and `CashAndDueFromBanks` are "
        "outside `ingest_fundamentals.py`'s fixed `CONCEPTS` list. `load_supplemental_alt_tags()` "
        "reads them offline from the already-cached `data/raw/companyfacts/CIK*.json` (zero "
        "network calls, zero API spend), which means **those values bypass the ingestion "
        "validation and have no rows in the WARN table.** Concretely this affects the 50 "
        "net-income observations resolved to `ProfitLoss`, the 24 operating-income observations "
        "resolved to `ProfitLoss`, and every JPM/BAC `cash_to_assets` value. The gap is real and "
        "closable by a free EDGAR-only re-ingest; until then, read the Source column below as "
        "\"fundamentals.parquet, or raw companyfacts for the alt tags.\""
    )
    lines.append("")
    lines.append(
        "**Correction (red-team review; an earlier draft of this report and of "
        "`features.py`'s docstring got this wrong):** an earlier claim here stated "
        "\"JPM reports `Revenues` through fiscal 2025, then switches to "
        "`RevenuesNetOfInterestExpense` starting its 2026 Q1 10-Q.\" That is FALSE -- "
        "re-checked directly against `_revenue_concept_used` and the raw fundamentals: JPM "
        "resolves to `RevenuesNetOfInterestExpense` for ALL 24 of its in-window observations "
        "(2023 Q3 through 2026 Q2 alike), zero to `Revenues`. `RevenuesNetOfInterestExpense` has "
        "been JPM's real, as-reported, QUARTERLY top-line tag (every 10-Q and every 10-K) for the "
        "entire corpus window -- there was never a switch. In-window (filed >= 2023-08-01) `Revenues` is a redundant, "
        "ANNUAL-ONLY co-tag that JPM's 10-Ks also carry alongside `RevenuesNetOfInterestExpense` "
        "for the same fiscal-year period, with an IDENTICAL value (confirmed: e.g. FY2023 "
        "reports $158,104M under both tags in the same 10-K). `resolve_concept_family()`'s "
        "freshest-wins tie-break (stable sort; when two family members tie exactly on "
        "`(period_end, filed)`, the LAST one in the candidates list wins, and "
        "`RevenuesNetOfInterestExpense` is listed after `Revenues` in `REVENUE_FAMILY_ORDER`) is "
        "what makes JPM consistently resolve to `RevenuesNetOfInterestExpense` whenever both are "
        "reported for the same period -- a deterministic tie-break artifact, not a real tag "
        "migration. No feature value changes from this correction (JPM's resolved revenue value "
        "was already numerically correct); only the prose claim was wrong, and is fixed here."
    )
    lines.append("")
    lines.append(f"Revenue concept actually used, by count of observations: {diagnostics['revenue_concept_used_counts']}")
    lines.append("")
    lines.append(f"Net income concept actually used: {diagnostics['net_income_concept_used_counts']}")
    lines.append("")
    lines.append(f"Operating income concept actually used: {diagnostics['operating_income_concept_used_counts']}")
    lines.append("")
    lines.append("| Numeric feature | Missing (NaN) share |")
    lines.append("|---|---|")
    for c in NUMERIC_FEATURE_NAMES:
        lines.append(f"| {c} | {diagnostics['numeric_missingness'][c]:.1%} |")
    lines.append("")
    lines.append(
        "Missingness is NOT imputed to zero -- XGBoost natively handles missing values by "
        "learning a default split direction per node; a numeric-only baseline built with the "
        "same library gets the identical treatment, so this is not an advantage unique to the "
        "text-augmented model."
    )
    lines.append("")

    lines.append("## Staleness guard (fixes the silently-stale-fundamentals defect found in red-team review)")
    lines.append("")
    lines.append(
        f"`resolve_concept_family()` (and therefore every numeric feature -- see its docstring "
        f"and module docstring point (e)) now discards a resolved fact and returns NaN instead if "
        f"its `period_end` is more than `STALENESS_MAX_DAYS` = **{STALENESS_MAX_DAYS} days** stale "
        f"relative to the observation's `filing_date`, rather than silently using whatever value "
        f"happens to exist even if it is years old. Before ANY of this build's fixes, 76 "
        f"observations across 4 (ticker, concept) pairs were silently using a stale value with no "
        f"signal anything was wrong (JNJ OperatingIncomeLoss x26, JPM Cash x24, BAC Cash x25, MRK "
        f"OCF x1). Two of those four pairs (JPM/BAC Cash) are now fixed AT THE SOURCE by the new "
        f"`CashAndDueFromBanks` alt tag (see the `cash_to_assets` row below) -- they resolve fresh "
        f"data and never reach the staleness check at all in this build. The staleness guard "
        f"itself is what this build's remaining discards go through: it fired "
        f"**{len(diagnostics['staleness_log'])} times** across "
        f"{len({(r['ticker'], r['concept_family']) for r in diagnostics['staleness_log']})} "
        f"distinct (ticker, concept) pairs (JNJ OperatingIncomeLoss, MRK OCF -- table below)."
    )
    lines.append("")
    if diagnostics["staleness_log"]:
        stale_df = pd.DataFrame(diagnostics["staleness_log"])
        summary = (
            stale_df.groupby(["ticker", "concept_family"])
            .agg(
                n_observations=("as_of", "count"),
                min_days_stale=("days_stale", "min"),
                max_days_stale=("days_stale", "max"),
                stalest_period_end=("period_end", "min"),
            )
            .reset_index()
            .sort_values(["ticker", "concept_family"])
        )
        lines.append("| Ticker | Concept family | N observations guarded | Min days stale | Max days stale | Stalest period_end |")
        lines.append("|---|---|---|---|---|---|")
        for _, r in summary.iterrows():
            lines.append(
                f"| {r['ticker']} | {r['concept_family']} | {int(r['n_observations'])} | "
                f"{int(r['min_days_stale'])} | {int(r['max_days_stale'])} | "
                f"{pd.Timestamp(r['stalest_period_end']).date()} |"
            )
        lines.append("")
    lines.append(
        "Root causes, one per affected (ticker, concept) pair:"
    )
    lines.append(
        "- **JNJ, OperatingIncomeLoss** -- JNJ has never reported this tag in the corpus window "
        "at all; its single freshest-ever row (period_end=2015-03-29, filed 2015-05-01) was, "
        "before this fix, silently returned as JNJ's \"current\" operating income for every 2023-"
        "2026 observation. JNJ is the tenth of the 10 companies with zero in-window "
        "`OperatingIncomeLoss` coverage -- the other nine never report the tag at all, while JNJ's "
        "is a pre-window migration (module docstring; HANDOFF.md §2a trap (a)) -- and this fix "
        "makes the code's actual behavior "
        "match that documentation for the first time; `operating_margin` is now correctly NaN for "
        "all 26 JNJ observations, not silently computed off a decade-stale figure."
    )
    lines.append(
        "- **JPM/BAC, CashAndCashEquivalentsAtCarryingValue** (NOT in the table above -- fixed "
        "upstream of the guard) -- fixed at the source by the new `CashAndDueFromBanks` alt tag "
        "(see `ALT_TAG_FAMILIES` and module docstring point (a)): `resolve_concept_family()`'s "
        "freshest-wins comparison now includes `CashAndDueFromBanks`, which has fresh data every "
        "quarter, so it wins the freshest-`period_end` comparison and the guard is never even "
        "consulted for these two tickers in this build. Had the alt tag not been added, this is "
        "exactly the failure the guard would have caught instead (24 JPM + 25 BAC observations at "
        "~1,700+/~1,300+ days stale respectively) -- both routes were verified to reach the same "
        "correct outcome (fresh, current cash figures), and the alt-tag fix was kept as the "
        "primary mechanism because it recovers real data rather than discarding it."
    )
    lines.append(
        "- **MRK, NetCashProvidedByUsedInOperatingActivities (one-filing tag detour, 1 observation)** -- "
        "MRK's FY2023 10-K (filed 2024-02-26) tagged operating cash flow under "
        "`NetCashProvidedByUsedInOperatingActivitiesContinuingOperations` instead of the plain "
        "`NetCashProvidedByUsedInOperatingActivities` tag used every other year in this window -- "
        "a one-filing tag detour (MRK reverted to the plain tag starting its FY2024 10-K, filed "
        "2025-02-25). Because the fixed concept list doesn't chase that one-year alias, the freshest "
        "PIT-legal value for the plain tag as of MRK's 2024-04-25 8-K was its 2023 Q3 cumulative "
        "figure (period_end=2023-09-30, filed 2023-11-03) -- exactly 208 days stale. This is a "
        "single-filing anomaly, not an ongoing migration, so it was NOT added to "
        "`ALT_TAG_FAMILIES`; the general staleness guard is what neutralizes it (208 > 200), "
        "turning it into a correctly-NaN `operating_cashflow_to_revenue` for that one observation "
        "instead of a silently-wrong 208-day-old value."
    )
    lines.append("")

    lines.append("## Full feature dictionary")
    lines.append("")
    lines.append("| Feature | Source | Caveat |")
    lines.append("|---|---|---|")
    for name, source, caveat in FEATURE_DICTIONARY:
        lines.append(f"| `{name}` | {source} | {caveat} |")
    lines.append("")

    lines.append("## Section-rate missingness policy (fixes the 0-vs-NaN conflation found in red-team review)")
    lines.append("")
    lines.append(
        "Before the 0-vs-NaN fix, `redflag_<CATEGORY>_rate_risk_factors`, `redflag_<CATEGORY>_rate_mda`, "
        "and `redflag_any_rate_press` were 0-filled whenever their section had zero attributed "
        "chunks -- conflating \"assessed this section, found no flags\" with \"never assessed "
        "this section at all\" (the RISK_FACTORS-rate columns look identical in both cases: a "
        "confident 0.0). Fixed: these columns are now left as genuine NaN when their section's "
        "chunk count is 0, exactly like `sentiment_mean_score`/`guidance_signed_mean` already "
        "were -- XGBoost's native missing-value handling treats them as unknown, not as a "
        "flag-free signal."
    )
    lines.append("")
    lines.append(
        f"Effect on this build: **{diagnostics['n_zero_risk_factors_section']} observations** "
        f"({diagnostics['n_zero_risk_factors_section'] / diagnostics['n_observations']:.1%} of "
        f"{diagnostics['n_observations']}) have zero attributed RISK_FACTORS chunks and now carry "
        f"NaN instead of 0.0 for every `redflag_<CATEGORY>_rate_risk_factors` feature; "
        f"**{diagnostics['n_zero_mda_section']} observations** "
        f"({diagnostics['n_zero_mda_section'] / diagnostics['n_observations']:.1%}) similarly for "
        f"`redflag_<CATEGORY>_rate_mda`; **{diagnostics['n_zero_press_section']} observations** "
        f"({diagnostics['n_zero_press_section'] / diagnostics['n_observations']:.1%}) for "
        f"`redflag_any_rate_press` (this last one is expected to be close to the 10-Q/10-K share "
        f"of the corpus -- press-release chunks come from 8-K EX99 exhibits almost exclusively). "
        "This changes which rows a red-flag-rate feature can influence a model on (previously a "
        "10-Q with no RISK_FACTORS chunks of its own would still contribute a hard '0 flags' "
        "training signal for that feature; now it contributes nothing, correctly). See "
        "`data/backtest_report.md` for whether/how this shifted the text-vs-numeric comparison."
    )
    lines.append("")

    lines.append("## Explicitly excluded from features")
    lines.append("")
    lines.append(
        "- **distress_tier (LIQUIDITY_STRESS, ACCOUNTING_RESTATEMENT, GOING_CONCERN)** -- "
        "excluded entirely, not just its REALIZED class, per HANDOFF §7 and the binding "
        "RED_FLAGS_LIMITATION.md constraint #4 (the REALIZED LIQUIDITY_STRESS class is empty "
        "corpus-wide after owner adjudication; GOING_CONCERN is n=0 by universe construction). "
        "Not a headline feature, not an ablation input, not present in features.parquet at all."
    )
    lines.append(
        "- **Red-flag REALIZED/HYPOTHETICAL modality splits** -- excluded from the headline "
        "feature set project-wide (not just for LEGAL_REGULATORY_ACTION) per "
        "RED_FLAGS_LIMITATION.md binding constraint #2 (modality is the least reliable labeling "
        "dimension: 43 of 146 corrections were modality flips)."
    )
    lines.append(
        "- **EntityCommonStockSharesOutstanding** -- ingested but not used as a feature; "
        "EarningsPerShareDiluted already covers the per-share dimension and this concept is "
        "structurally absent for GOOGL/MA/V, adding little."
    )
    lines.append("")

    lines.append("## Target definition and limitations")
    lines.append("")
    lines.append(
        "Forward excess return: subject-company return over the ~63 trading days STARTING "
        "the first trading day strictly after `filing_date`, minus the equal-weighted average "
        "of the identical-window return across all 25 universe tickers (the subject company is "
        "one of the 25 -- included in its own benchmark average, per the literal ratified "
        "wording; stated explicitly here as a modeling choice)."
    )
    lines.append(
        "- **Not dividend-adjusted.** `data/prices.parquet` closes are split-adjusted only "
        "(`data/PRICES_NOTES.md` §1). Both the subject return and the universe average share "
        "this omission, so it is a common-mode bias across the panel, not independent noise -- "
        "but it systematically understates total return more for high-dividend-yield names "
        "(PG, KO, MCD) than for low-yield names, a real, documented limitation."
    )
    lines.append(
        "- **Recent filings lack a complete forward window** as of this data snapshot -- see "
        "the observation-count section above for the exact drop count."
    )
    lines.append("")
    FEATURES_REPORT_OUTPUT.write_text("\n".join(lines))


def main() -> None:
    print("Building FinScreen Phase C feature table...")
    features_df, diagnostics = build_feature_table()
    features_df.to_parquet(FEATURES_OUTPUT, index=False)
    write_features_report(diagnostics)
    print(f"Wrote {FEATURES_OUTPUT} ({len(features_df)} rows, {len(features_df.columns)} columns)")
    print(f"Wrote {FEATURES_REPORT_OUTPUT}")
    print(f"Observations with usable target: {diagnostics['n_target_usable']} / {diagnostics['n_observations']}")


if __name__ == "__main__":
    main()
