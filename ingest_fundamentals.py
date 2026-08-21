"""
ingest_fundamentals.py -- pull numeric XBRL fundamentals (SEC "companyfacts")
for the fixed FinScreen 25-company universe (data/universe.csv) and store
them in data/fundamentals.parquet, one row per (company, concept, period,
filing). Phase C prerequisite for features.py -- see ROADMAP.md Phase C's
numeric-fundamentals-sourcing bullet and HANDOFF.md §2a "Phase C
artifacts".

Scope: numeric fundamentals only. No derived metrics (margins, growth rates,
ratios) are computed here -- that is explicitly features.py's job. The
requirement, restated inline so it can be checked without hunting for an
external brief: *do not invent derived metrics in the ingestion layer; store
only as-reported GAAP facts.* This module's only responsibilities are: pull
the raw facts, keep every filed occurrence (never dedupe/overwrite), and
validate coverage.

-----------------------------------------------------------------------
POINT-IN-TIME DISCIPLINE (hard rule, HANDOFF.md §7 -- read before touching
this file)
-----------------------------------------------------------------------
Every stored row carries EDGAR's own `filed` date for the specific filing
that reported it -- never a fiscal period end date, exactly the same
discipline `ingest_metadata.py` enforces for filing metadata (`filing_date`,
never `report_date`). Concretely:

  - A single (concept, period) pair is stored MULTIPLE times if it was
    reported in multiple filings (the ordinary case -- a quarter's figure
    is reported once as "current period" and again as a prior-period
    comparative in the following quarter's 10-Q).
  - A restatement is a NEW row with the same period but a later `filed`
    date and a possibly different `value` -- it is never used to overwrite
    or delete the original row. This is what lets a downstream consumer
    answer "what was known as of date X" instead of implicitly leaking
    hindsight (restated figures) into an as-of-the-time analysis.
  - `pit.value_as_of()` is the one tested helper for doing that "as of date
    X" selection correctly; see its module docstring for the exact rule.

This means data/fundamentals.parquet is intentionally NOT deduplicated by
(ticker, concept, period) -- row count is (companies) x (concepts) x
(distinct filed occurrences per concept), not x (distinct periods). Do not
"clean this up" downstream without re-deriving the point-in-time guarantee
some other way.

-----------------------------------------------------------------------
Concept set and the revenue-alias problem
-----------------------------------------------------------------------
Companies tag revenue under different us-gaap concepts depending on filer
choice and ASC 606 adoption vintage. All FOUR aliases carried in
`REVENUE_CONCEPTS` below are extracted and stored AS-IS under their real tag
name -- this module does not resolve them into a single unified "revenue"
column (that reconciliation belongs to features.py). The fourth,
`RevenuesNetOfInterestExpense`, is the bank/broker-dealer presentation and
is used in this universe by **GS and JPM** -- and JPM reports `Revenues`
in-window as well, which is why the `revenue_alias_consistency` validator
WARNs on it. Do not special-case a single ticker. See
`revenue_alias_report()` for the per-company breakdown of which alias(es)
actually appear.

-----------------------------------------------------------------------
Idempotency
-----------------------------------------------------------------------
Same pattern as ingest_metadata.py: EdgarClient.get_companyfacts() is the
only thing gated by network staleness (24h). This script always recomputes
data/fundamentals.parquet from whatever's in the cache -- cheap, local, no
network -- so re-running it is always safe and does not re-download anything
already cached and fresh.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from edgar_client import EdgarClient
from ingest_metadata import (
    load_universe,
    print_validation_report,
    ValidationProblem,
)

REPO_ROOT = Path(__file__).resolve().parent
OUTPUT_PARQUET = REPO_ROOT / "data" / "fundamentals.parquet"
DB_PATH = REPO_ROOT / "data" / "filings_metadata.db"

# ---------------------------------------------------------------------------
# Concept set (task-specified, Phase C)
# ---------------------------------------------------------------------------

# (taxonomy, concept) pairs pulled from companyfacts for every company.
CONCEPTS: list[tuple[str, str]] = [
    ("us-gaap", "Revenues"),
    ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
    ("us-gaap", "RevenueFromContractWithCustomerIncludingAssessedTax"),
    # 4th revenue alias, added after investigating the one real FATAL this
    # ingestion produced on a live pull: Goldman Sachs (GS) reports ZERO rows
    # under all three aliases above -- confirmed by reading its raw
    # companyfacts JSON, GS's actual headline top-line tag is
    # RevenuesNetOfInterestExpense (standard investment-bank income-statement
    # presentation: gross revenues net of interest expense, distinct from an
    # industrial/retail "Revenues" line). This is the exact "determine what's
    # actually reported before deciding what is a FATAL gap" investigation
    # required for the bank/broker-dealer tickers (JPM/BAC/GS) rather than
    # recording them as coverage gaps -- see HANDOFF.md §2a's Phase C traps.
    # NOTE: this alias is NOT GS-only. JPM reports it too (GS 172 rows /
    # JPM 149 rows as of 2026-08-18), and JPM additionally reports
    # `Revenues` in-window, which is why revenue_alias_consistency WARNs on
    # it. Added as a 4th
    # named alias (not a derived metric -- it is GS's own real, as-reported
    # GAAP fact, stored as-is) rather than left as an unexplained gap for
    # 1/25 companies; flagged prominently in the run report as a deliberate,
    # narrow, verified addition in direct response to that instruction, not
    # a silent scope expansion.
    ("us-gaap", "RevenuesNetOfInterestExpense"),
    ("us-gaap", "NetIncomeLoss"),
    ("us-gaap", "OperatingIncomeLoss"),
    ("us-gaap", "Assets"),
    ("us-gaap", "Liabilities"),
    ("us-gaap", "StockholdersEquity"),
    ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
    ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
    ("us-gaap", "EarningsPerShareDiluted"),
    ("dei", "EntityCommonStockSharesOutstanding"),
]

# The well-known revenue-alias problem: a company reports revenue under
# exactly one (occasionally more, across a tag-migration year) of these
# us-gaap tags. All four are pulled; none is treated as "the" revenue
# concept at ingestion time -- see module docstring.
# (RevenuesNetOfInterestExpense is used by GS *and* JPM in this universe --
# see the comment on CONCEPTS above. It is not a GS-specific special case.)
REVENUE_CONCEPTS = {
    "Revenues",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "RevenuesNetOfInterestExpense",
}

# "Core" concepts for the validation pass below -- every concept except the
# three raw revenue aliases, which are validated together as one logical
# "revenue" bucket (a company only needs ONE alias present, not all three).
CORE_NON_REVENUE_CONCEPTS = [
    c for t, c in CONCEPTS if c not in REVENUE_CONCEPTS
]

# Corpus window this validates coverage against -- matches the actual
# filings.parquet / filings_metadata.db date range (2023-08-14 to
# 2026-08-07), not a guessed "2023-2026". Fundamentals themselves are NOT
# filtered to this window when stored (companyfacts returns full company
# history and all of it is kept -- see module docstring), only the
# *validation* pass below scopes to it, since that's the window the rest of
# the pipeline (labels, filings) actually spans.
CORPUS_WINDOW_START = date(2023, 8, 14)
CORPUS_WINDOW_END = date(2026, 8, 7)
# The number of "reportable" quarters in that window is computed dynamically
# by target_quarters() below (currently 12, matching
# ingest_metadata.py's LOOKBACK_QUARTERS) -- not hardcoded, since it must
# exclude any trailing quarter that hasn't even ended yet as of
# CORPUS_WINDOW_END (see target_quarters()'s docstring for why that fix
# mattered).


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def extract_concept_facts(
    companyfacts: dict, taxonomy: str, concept: str, ticker: str, cik: int,
) -> list[dict]:
    """Pull every disclosed fact for one (taxonomy, concept) out of a raw
    companyfacts JSON document, across every unit it's reported in (almost
    always exactly one unit per concept in practice -- USD, USD/shares, or
    shares -- but this doesn't assume that).

    Returns one dict per filed occurrence -- i.e. if the same period was
    reported in 3 different filings (current + comparative + restatement),
    this returns 3 rows. Nothing is deduplicated here; see module docstring.
    """
    concept_data = companyfacts.get("facts", {}).get(taxonomy, {}).get(concept)
    if concept_data is None:
        return []
    rows: list[dict] = []
    for unit, facts in concept_data.get("units", {}).items():
        for fact in facts:
            rows.append(
                {
                    "ticker": ticker,
                    "cik": cik,
                    "taxonomy": taxonomy,
                    "concept": concept,
                    "unit": unit,
                    "value": fact.get("val"),
                    "fy": fact.get("fy"),
                    "fp": fact.get("fp"),
                    "period_start": fact.get("start"),  # None for instant facts
                    "period_end": fact.get("end"),
                    "form": fact.get("form"),
                    "accession_number": fact.get("accn"),
                    "filed": fact.get("filed"),
                }
            )
    return rows


def build_fundamentals(
    client: EdgarClient, universe: pd.DataFrame, force_refresh: bool = False,
) -> pd.DataFrame:
    """One companyfacts request per company (25 total, cached/idempotent per
    EdgarClient.get_companyfacts()'s staleness policy), extracted into one
    row per (company, concept, unit, period, filing).
    """
    all_rows: list[dict] = []
    for _, row in universe.iterrows():
        cik = int(row["cik"])
        ticker = row["ticker"]
        companyfacts = client.get_companyfacts(cik, force=force_refresh)
        for taxonomy, concept in CONCEPTS:
            all_rows.extend(
                extract_concept_facts(companyfacts, taxonomy, concept, ticker, cik)
            )
        print(f"  {ticker} (CIK {cik}): {sum(1 for r in all_rows if r['ticker'] == ticker)} fact rows")

    df = pd.DataFrame(all_rows)
    if df.empty:
        raise RuntimeError(
            "build_fundamentals() produced zero rows across the whole universe -- "
            "something is badly wrong (concept names changed, or every "
            "companyfacts fetch failed silently). Refusing to write an empty parquet."
        )
    # Deterministic row order: helps diffing/inspection, not a correctness
    # requirement (pit.value_as_of() doesn't rely on row order).
    df = df.sort_values(["ticker", "concept", "period_end", "filed", "accession_number"]).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# Revenue-alias report (per-company, which alias(es) actually appear)
# ---------------------------------------------------------------------------


def revenue_alias_report(df: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    """Per-ticker: which revenue alias(es) appear anywhere in the company's
    full stored history (not window-scoped -- this is a documentation aid,
    not a validation gate; the window-scoped version of this check lives in
    validate_fundamentals()).
    """
    revenue_rows = df[df["concept"].isin(REVENUE_CONCEPTS)]
    out = []
    for _, row in universe.iterrows():
        ticker = row["ticker"]
        aliases = sorted(revenue_rows.loc[revenue_rows["ticker"] == ticker, "concept"].unique())
        out.append({"ticker": ticker, "revenue_aliases_used": ", ".join(aliases) if aliases else "(none)"})
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# Validation -- ingest_metadata.py WARN/FATAL conventions
# ---------------------------------------------------------------------------

# Calibrated against the REAL coverage distribution from a live 25-company
# pull (2026-08-18), not guessed -- see the run report accompanying this
# module for the full numbers. Method: for each (ticker, core concept),
# count how many of the 12 "reportable" corpus-window quarters (see
# `target_quarters()`) have >=1 fact row whose `period_end` falls in that
# quarter AND whose `filed` date is itself inside the window. Across all
# 225 (25 companies x 9 core concepts) pairs:
#   - 198 pairs have >0 quarters covered; of those, coverage is >=91.7%
#     (11/12 or 12/12) for the overwhelming majority -- a single missing
#     quarter is normal, harmless variance (a late/early filing landing just
#     outside a calendar-quarter bucket, or -- confirmed for the dei
#     EntityCommonStockSharesOutstanding concept specifically -- because its
#     `end` is a cover-page "as of" date that trails the associated fiscal
#     quarter's real end by ~3-7 weeks and can spill into the next calendar
#     quarter under this check's date-bucketing; see the dei caveat below).
#   - A small, fully-explained cluster sits well below that (25-75%):
#     MA/OXY NetIncomeLoss (25%), SLB OperatingIncomeLoss (25%), CVX
#     CashAndCashEquivalentsAtCarryingValue (33%), and several tickers'
#     EntityCommonStockSharesOutstanding in the 67-75% band. Every single one
#     of these was individually inspected against the raw companyfacts JSON
#     (not assumed) -- see KNOWN_MIDWINDOW_MIGRATIONS and the dei caveat.
#   - 27/225 pairs have ZERO in-window coverage. All 27, without exception,
#     are explained by one of two real, verified causes -- see
#     STRUCTURALLY_ABSENT / migrated-before-window logic below. Zero
#     unexplained (FATAL) zero-coverage pairs were found in this universe.
MIN_QUARTERLY_COVERAGE_CLEAN = 0.75   # >= this: no problem logged at all
MIN_QUARTERLY_COVERAGE_WARN = 0.40    # [WARN, CLEAN): WARN, ordinary sparse coverage
# below MIN_QUARTERLY_COVERAGE_WARN: WARN only if the pair is a verified,
# named mid-window migration (see KNOWN_MIDWINDOW_MIGRATIONS); FATAL
# otherwise (unexplained, not verified against real data -- err loud).

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


def target_quarters(window_start: date, window_end: date) -> set[tuple[int, int]]:
    """The set of (year, calendar_quarter) buckets that are actually
    "reportable" by `window_end` -- i.e. whose quarter END date is on or
    before `window_end`. Excludes any trailing partial quarter whose end
    hasn't even happened yet as of `window_end` (e.g. for this corpus's real
    window, 2026-08-07, the quarter ending 2026-09-30 is excluded -- no
    company could possibly have filed a report for a quarter that hasn't
    ended yet, so counting it as a missing "target" quarter would understate
    coverage for every single company/concept identically, which is exactly
    what an earlier, less careful version of this function did -- caught by
    inspecting the real coverage distribution, which showed every single
    company/concept pair capped at a suspicious, identical 92.3% ceiling
    until this fix).
    """
    def _quarter_end(y: int, q: int) -> date:
        import calendar
        month = q * 3
        day = calendar.monthrange(y, month)[1]
        return date(y, month, day)

    start_q = (window_start.year, (window_start.month - 1) // 3 + 1)
    end_q = (window_end.year, (window_end.month - 1) // 3 + 1)
    quarters = set()
    y, q = start_q
    while (y, q) <= end_q:
        if _quarter_end(y, q) <= window_end:
            quarters.add((y, q))
        q += 1
        if q == 5:
            q = 1
            y += 1
    return quarters


def _quarter_bucket(period_end: Optional[str]) -> Optional[tuple[int, int]]:
    if not period_end:
        return None
    ts = pd.Timestamp(period_end)
    return (ts.year, (ts.month - 1) // 3 + 1)


def init_fundamentals_validation_table(conn) -> None:
    """A dedicated table, NOT `universe_validation_problems` --
    ingest_metadata.write_validation_problems() deletes every row for a given
    `run_date` regardless of check_name before inserting, so sharing that
    table between two independent validation passes run on the same day
    would silently erase whichever one wrote second. Same column shape
    (ticker, check_name, severity, message) for convention consistency, just
    a separate table so the two passes' history can't stomp each other.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS fundamentals_validation_problems (
            run_date TEXT NOT NULL,
            ticker TEXT NOT NULL,
            check_name TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT NOT NULL
        );
        """
    )
    conn.commit()


def write_fundamentals_validation_problems(
    conn, problems: list[ValidationProblem], run_date: date,
) -> None:
    conn.execute(
        "DELETE FROM fundamentals_validation_problems WHERE run_date = ?",
        (run_date.isoformat(),),
    )
    conn.executemany(
        "INSERT INTO fundamentals_validation_problems "
        "(run_date, ticker, check_name, severity, message) VALUES (?, ?, ?, ?, ?)",
        [(run_date.isoformat(), p.ticker, p.check, p.severity, p.message) for p in problems],
    )
    conn.commit()


def validate_fundamentals(
    df: pd.DataFrame,
    universe: pd.DataFrame,
    window_start: date = CORPUS_WINDOW_START,
    window_end: date = CORPUS_WINDOW_END,
) -> list[ValidationProblem]:
    """Per-company, per-core-concept quarterly coverage across the corpus
    window, plus the revenue-alias-presence check. Mirrors
    ingest_metadata.validate_universe()'s WARN/FATAL reporting convention
    (same ValidationProblem shape, same print_validation_report()).
    """
    problems: list[ValidationProblem] = []

    work = df.copy()
    work["filed_date"] = pd.to_datetime(work["filed"]).dt.date
    work["period_end_bucket"] = work["period_end"].map(_quarter_bucket)
    in_window = work[(work["filed_date"] >= window_start) & (work["filed_date"] <= window_end)]
    target_qs = target_quarters(window_start, window_end)
    n_target = len(target_qs)

    for _, row in universe.iterrows():
        ticker = row["ticker"]
        company_all = df[df["ticker"] == ticker]
        company_window = in_window[in_window["ticker"] == ticker]

        # -- Revenue concept presence (FATAL if truly absent anywhere) ----
        revenue_all = company_all[company_all["concept"].isin(REVENUE_CONCEPTS)]
        revenue_window = company_window[company_window["concept"].isin(REVENUE_CONCEPTS)]
        aliases_ever = sorted(revenue_all["concept"].unique())
        aliases_in_window = sorted(revenue_window["concept"].unique())

        if not aliases_ever:
            problems.append(
                ValidationProblem(
                    ticker, "revenue_concept_present", "FATAL",
                    f"No revenue concept ({sorted(REVENUE_CONCEPTS)}) reported in "
                    f"companyfacts at all -- cannot compute any revenue-based feature "
                    f"for this company.",
                )
            )
        elif not aliases_in_window:
            problems.append(
                ValidationProblem(
                    ticker, "revenue_concept_present", "FATAL",
                    f"Revenue concept(s) {aliases_ever} exist in this company's full "
                    f"history but none have an in-window ({window_start}..{window_end}) "
                    f"filed occurrence -- no revenue data usable for the corpus window.",
                )
            )
        elif len(aliases_in_window) > 1:
            problems.append(
                ValidationProblem(
                    ticker, "revenue_alias_consistency", "WARN",
                    f"Multiple revenue aliases reported in-window: {aliases_in_window} -- "
                    f"features.py must reconcile these into one series, not treat them "
                    f"as independent concepts (see module docstring).",
                )
            )

        # -- Per-core-concept quarterly coverage ---------------------------
        for concept in CORE_NON_REVENUE_CONCEPTS:
            concept_rows_window = company_window[company_window["concept"] == concept]
            quarters_covered = {
                q for q in concept_rows_window["period_end_bucket"] if q is not None
            } & target_qs
            coverage = len(quarters_covered) / n_target if n_target else 0.0

            is_bank_exempt = (
                ticker in BANK_TICKERS_MISSING_INDUSTRIAL_CONCEPTS
                and concept in BANK_EXEMPT_CONCEPTS
            )
            migration_note = KNOWN_MIDWINDOW_MIGRATIONS.get((ticker, concept))

            if len(quarters_covered) == 0:
                concept_ever = company_all[company_all["concept"] == concept]
                tag_ever_exists = not concept_ever.empty
                most_recent_filed_ever = (
                    concept_ever["filed"].max() if tag_ever_exists else None
                )
                migrated_before_window = (
                    most_recent_filed_ever is not None
                    and most_recent_filed_ever < window_start.isoformat()
                )

                if is_bank_exempt:
                    problems.append(
                        ValidationProblem(
                            ticker, "concept_structurally_absent", "WARN",
                            f"{concept}: zero in-window quarters covered -- expected for "
                            f"this ticker (bank-exempt concept, see BANK_EXEMPT_CONCEPTS "
                            f"docstring), not a data gap.",
                        )
                    )
                elif not tag_ever_exists:
                    problems.append(
                        ValidationProblem(
                            ticker, "concept_structurally_absent", "WARN",
                            f"{concept}: this us-gaap/dei tag has NEVER appeared anywhere "
                            f"in {ticker}'s full companyfacts history (not just the "
                            f"window) -- a structural filer-taxonomy choice, not a data "
                            f"gap; not recoverable by re-pulling.",
                        )
                    )
                elif migrated_before_window:
                    problems.append(
                        ValidationProblem(
                            ticker, "concept_tag_migrated_before_window", "WARN",
                            f"{concept}: last ever reported {most_recent_filed_ever}, "
                            f"before this corpus window began ({window_start}) -- {ticker} "
                            f"switched to an equivalent GAAP-taxonomy alias years ago; "
                            f"expected absence, not a gap.",
                        )
                    )
                else:
                    problems.append(
                        ValidationProblem(
                            ticker, "concept_unexplained_gap", "FATAL",
                            f"{concept}: zero in-window quarters covered "
                            f"(0/{n_target}), and the tag HAS been used both before and "
                            f"potentially after the window elsewhere in this company's "
                            f"history (most recent ever: {most_recent_filed_ever}) -- no "
                            f"known/verified explanation; treat as a real gap.",
                        )
                    )
            elif coverage >= MIN_QUARTERLY_COVERAGE_CLEAN:
                pass  # healthy -- matches the observed normal-variance baseline, no report
            elif migration_note is not None:
                problems.append(
                    ValidationProblem(
                        ticker, "concept_quarterly_coverage_midwindow_migration", "WARN",
                        f"{concept}: {len(quarters_covered)}/{n_target} in-window quarters "
                        f"covered ({coverage:.0%}) -- verified mid-window migration to "
                        f"{migration_note}; not pulled here (outside the fixed concept "
                        f"list), but real, usable data exists downstream under that tag.",
                    )
                )
            elif coverage >= MIN_QUARTERLY_COVERAGE_WARN:
                problems.append(
                    ValidationProblem(
                        ticker, "concept_quarterly_coverage_partial", "WARN",
                        f"{concept}: {len(quarters_covered)}/{n_target} in-window quarters "
                        f"covered ({coverage:.0%}) -- below the "
                        f"{MIN_QUARTERLY_COVERAGE_CLEAN:.0%} clean threshold; not "
                        f"catastrophic but worth features.py's awareness.",
                    )
                )
            else:
                problems.append(
                    ValidationProblem(
                        ticker, "concept_quarterly_coverage_low", "FATAL",
                        f"{concept}: only {len(quarters_covered)}/{n_target} in-window "
                        f"quarters covered ({coverage:.0%}), below "
                        f"{MIN_QUARTERLY_COVERAGE_WARN:.0%}, with no verified explanation "
                        f"(not in KNOWN_MIDWINDOW_MIGRATIONS) -- treat as a real gap "
                        f"needing manual investigation before use.",
                    )
                )

    return problems


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------


def run(force_refresh: bool = False) -> None:
    universe = load_universe()
    client = EdgarClient()

    print(f"Pulling companyfacts for {len(universe)} companies "
          f"({len(CONCEPTS)} concepts each)...")
    df = build_fundamentals(client, universe, force_refresh=force_refresh)

    print(f"\nTotal EDGAR network GETs this run: {client.request_count}")
    print(f"Total fundamentals rows: {len(df)}")

    print("\nRevenue alias usage per company:")
    alias_report = revenue_alias_report(df, universe)
    for _, r in alias_report.iterrows():
        print(f"  {r['ticker']:<6} {r['revenue_aliases_used']}")

    problems = validate_fundamentals(df, universe)
    print_validation_report(problems)

    fatal = [p for p in problems if p.severity == "FATAL"]
    if fatal:
        print(
            f"\n{len(fatal)} FATAL coverage problem(s) found. Writing "
            f"{OUTPUT_PARQUET} anyway (fundamentals sourcing is not gated the "
            f"way ingest_metadata.py's universe validation is -- these are "
            f"reported for the record and for quant-modeler to see, not a "
            f"hard stop on an otherwise-successful 25/25 companyfacts pull)."
        )

    import sqlite3

    conn = sqlite3.connect(DB_PATH)
    init_fundamentals_validation_table(conn)
    write_fundamentals_validation_problems(conn, problems, date.today())
    conn.close()

    df.to_parquet(OUTPUT_PARQUET, index=False)
    print(f"\nWrote {len(df)} rows to {OUTPUT_PARQUET}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force-refresh", action="store_true",
        help="Ignore companyfacts cache staleness and re-fetch from EDGAR for every company.",
    )
    args = parser.parse_args()
    run(force_refresh=args.force_refresh)
