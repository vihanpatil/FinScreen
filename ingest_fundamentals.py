"""
ingest_fundamentals.py -- pull numeric XBRL fundamentals (SEC "companyfacts")
for every member of the E2 hybrid136 universe (ingest_metadata.load_universe(),
CIK-keyed) and store them in data/fundamentals_e2.parquet, one row per
(company, concept, period, filing). Prerequisite for features.py -- see
ROADMAP.md Phase C's numeric-fundamentals-sourcing bullet and HANDOFF.md §2a
"Phase C artifacts".

F2 stage S2 re-scoped this module's VALIDATION to per-company coverage
windows and made it CIK-keyed (`ticker` is now a display label only).
F2 stage S4 (this file's current shape) replaced the flat CONCEPTS list with
CONCEPT_FAMILIES + an automated alias/migration classifier (F2_SPEC §5), and
DELETED the three hand-curated per-ticker maps E1 carried
(BANK_TICKERS_MISSING_INDUSTRIAL_CONCEPTS, BANK_EXEMPT_CONCEPTS,
KNOWN_MIDWINDOW_MIGRATIONS). They are preserved verbatim in
data/f2/status/S4_fundamentals.md as the record of what the classifier has to
reproduce mechanically; test_ingest_fundamentals.py's acceptance tests pin
every case they encoded against fixtures sliced from cached companyfacts.

E1's data/fundamentals.parquet is its frozen record and is never rewritten
here (same discipline as data/filings_metadata.db -- F2_SPEC §1.4 / §10).

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

This means the fundamentals parquet is intentionally NOT deduplicated by
(cik, concept, period) -- row count is (companies) x (concepts) x
(distinct filed occurrences per concept), not x (distinct periods). Do not
"clean this up" downstream without re-deriving the point-in-time guarantee
some other way.

-----------------------------------------------------------------------
Concept families and the alias/migration problem
-----------------------------------------------------------------------
Companies tag the same economic quantity under different us-gaap concepts
depending on filer type, ASC 606 / ASU 2016-18 adoption vintage, and plain
taxonomy drift over an 11-year window. CONCEPT_FAMILIES below maps each
logical concept to an ORDERED list of acceptable tags; every tag is pulled
and stored AS-IS under its own real tag name. This module still does not
unify them into one column -- that boundary is unchanged, the unification is
features.py's job (F5).

What IS new in E2 is that the choice is made mechanically and per company:
classify_universe() decides, per (cik, family), whether the family resolves
to one series (SINGLE / MIGRATION) or fails (OVERLAP / PARTIAL / ABSENT),
writes data/f2/concept_resolution.csv, and emits a FATAL
`fundamentals_alias_unresolved` row for every failure. The family's
preference order is used for REPORTING only -- never to silently pick a tag
when two of them cover the same quarters (F2_SPEC §5.2).

-----------------------------------------------------------------------
Idempotency
-----------------------------------------------------------------------
Same pattern as ingest_metadata.py: EdgarClient.get_companyfacts() is the
only thing gated by network staleness (24h). This script always recomputes
data/fundamentals_e2.parquet from whatever's in the cache -- cheap, local, no
network -- so re-running it is always safe and does not re-download anything
already cached and fresh.
"""

from __future__ import annotations

import argparse
import collections
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

from edgar_client import EdgarClient
from ingest_metadata import (
    CORPUS_WINDOW_END,
    CORPUS_WINDOW_START,
    DB_PATH,
    E1_DB_PATH,
    RUN_SCOPE_CIK,
    load_universe,
    print_validation_report,
    ValidationProblem,
)

REPO_ROOT = Path(__file__).resolve().parent
# E2's own output. data/fundamentals.parquet is E1's frozen Phase C record
# and is never rewritten from here (F2_SPEC §10).
OUTPUT_PARQUET = REPO_ROOT / "data" / "fundamentals_e2.parquet"
E1_OUTPUT_PARQUET = REPO_ROOT / "data" / "fundamentals.parquet"
CONCEPT_RESOLUTION_CSV = REPO_ROOT / "data" / "f2" / "concept_resolution.csv"

# ---------------------------------------------------------------------------
# Concept families (F2_SPEC §5.2)
# ---------------------------------------------------------------------------

# One logical series -> an ORDERED list of (taxonomy, tag) pairs, ordered by
# PREFERENCE. Every tag in every family is pulled and stored as-is under its
# own tag name; nothing is unified at ingestion (that boundary is unchanged --
# unification is F5's job).
#
# TWO BINDING RULES, from the 2026-08-24 "substitutes-only families +
# explicit dominance" ruling (F2_PROGRESS §5, F2_SPEC §5 amendment A1):
#
#   1. A family may contain ONLY tags that are alternative representations of
#      the SAME logical series -- true aliases or migration successors.
#      Related-but-distinct concepts get their own single-tag family (still
#      ingested, trivially resolved); whether one may proxy for another is
#      F5's decision, made in the open, not a grouping decided here.
#   2. Preference order is RESOLUTION SEMANTICS, not just reporting: when two
#      tags of one family are co-reported, the highest-preference tag that
#      clears the coverage bar and is not stale wins (state DOMINANT), and the
#      co-reported alternates are recorded on the row.
#
# The first S4 pass grouped non-substitutes (Liabilities with
# LiabilitiesAndStockholdersEquity = total assets; parent-share with
# NCI-inclusive income; balance-sheet cash with the ASU-2016-18 cash-flow
# total) and left 86/250 pairs UNRESOLVED on E1's own 25 companies. Same 25
# tags, regrouped: the ingested tag set and therefore the network cost are
# unchanged.
#
# `companyfacts` returns every concept a company ever tagged in ONE document,
# so widening the tag set costs zero extra requests and zero extra bytes --
# only parse time (F2_SPEC §5.1). E1's 13-concept flat list was a scope
# choice, not a cost constraint.
#
# The n/25 counts are the S1 pass's MEASURED availability across the cached
# companyfacts documents (does the tag exist at all), not coverage.
CONCEPT_FAMILIES: dict[str, list[tuple[str, str]]] = {
    # Top line. All five are one company's headline revenue under different
    # filer conventions and ASC 606 vintages; a company uses one of them.
    "revenue": [
        ("us-gaap", "Revenues"),                                              # 24/25
        ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),   # 17/25
        ("us-gaap", "RevenueFromContractWithCustomerIncludingAssessedTax"),   # 1/25
        # The bank/broker-dealer top line. NOT a GS special case: JPM reports
        # it too (HANDOFF §2a trap (d)).
        ("us-gaap", "RevenuesNetOfInterestExpense"),                          # 2/25
        ("us-gaap", "InterestAndDividendIncomeOperating"),                    # 3/25
    ],
    # Bottom line. NetIncomeLoss is the parent-share figure; ProfitLoss is the
    # same line including non-controlling interests, and is the tag MA/OXY
    # migrated to (trap (b)) -- for a filer with no NCI they are identical,
    # and for one with NCI the difference is small and consistent. They are
    # alternatives for "the company's net income"; the two concepts that are
    # NOT are below in their own families.
    "net_income": [
        ("us-gaap", "NetIncomeLoss"),                                         # 25/25
        ("us-gaap", "ProfitLoss"),                                            # 19/25
    ],
    # Net income AFTER preferred dividends -- a different quantity, not an
    # alias of net income. Own family; F5 may use it as a proxy or not.
    "net_income_to_common": [
        ("us-gaap", "NetIncomeLossAvailableToCommonStockholdersBasic"),       # 13/25
    ],
    # Operating income proper. Structurally absent for banks and for filers
    # that present no operating-income line -- ABSENT there is expected, is
    # reported, and is NOT silently backfilled from pre-tax income.
    "operating_income": [("us-gaap", "OperatingIncomeLoss")],                 # 16/25
    # Pre-tax income: a real, useful, DIFFERENT line. E1's map and S4's first
    # pass both effectively let it stand in for operating income; it does not.
    # Two us-gaap subtotals express it, differing only in whether
    # equity-method income sits inside or outside the subtotal -- a statement-
    # structure choice, so they are alternatives for "income before income
    # taxes" and the more-covered one is preferred. MEASURED reason for adding
    # the second tag (a membership adjustment under principle 1, S4 second
    # pass): F2_SPEC §5.2 carried only the …ExtraordinaryItemsNoncontrolling-
    # Interest variant, which EXISTS for 23/25 companies but is thinly
    # covered -- MSFT 24/44 quarters vs 31 under the …MinorityInterestAnd-
    # IncomeLossFromEquityMethodInvestments variant, JNJ 24 vs 29, MA 12 vs
    # 43 -- which left 11 of 25 companies PARTIAL on a family that is
    # perfectly well reported. The …Domestic / …Foreign siblings are
    # geographic COMPONENTS, not the subtotal, and are deliberately excluded.
    "pretax_income": [
        ("us-gaap",
         "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"),
        ("us-gaap",
         "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"),  # 23/25
    ],
    "assets": [("us-gaap", "Assets")],                                        # 25/25
    "liabilities": [("us-gaap", "Liabilities")],                              # 19/25
    # Total liabilities AND equity == total assets. Not a liabilities series;
    # its own family so that fact is visible rather than buried in an OVERLAP.
    "liabilities_and_equity": [("us-gaap", "LiabilitiesAndStockholdersEquity")],
    # Total equity, parent-share first, NCI-inclusive second -- the V/UNH
    # variant of trap (b). True alternatives for "book equity".
    #
    # The two partnership tags (ruled in 2026-08-24, A5.2) are the same
    # series for an issuer with units instead of shares: a partnership's book
    # equity IS its total partners' capital, and the pair mirrors the
    # corporate pair exactly (parent-share, then NCI-inclusive). They sit
    # after the corporate tags, so an issuer reporting both resolves
    # corporate. MEASURED users across the 244 cached companyfacts:
    # PartnersCapital 12, PartnersCapitalIncludingPortion… 8.
    # `LimitedPartnersCapitalAccount` (7 users) is deliberately NOT here: it
    # is the LP slice of capital, a COMPONENT like MinorityInterest, and
    # MEASURED it adds zero coverage -- every member reporting it also
    # reports a partners-capital total.
    "equity": [
        ("us-gaap", "StockholdersEquity"),                                    # 24/25
        ("us-gaap",
         "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),  # 17/25
        ("us-gaap", "PartnersCapital"),
        ("us-gaap", "PartnersCapitalIncludingPortionAttributableToNoncontrollingInterest"),
    ],
    # The NCI component on its own is not an equity-total alias.
    "minority_interest": [("us-gaap", "MinorityInterest")],                   # 16/25
    # Cash on the balance sheet, one family (design (a), measured -- see the
    # S4 report §2 of the second pass). CashAndDueFromBanks is the bank
    # presentation of the same line (E1's BANK_EXEMPT_CONCEPTS case); the two
    # restricted-cash tags are the post-ASU-2016-18 successors that some
    # filers (CVX) moved their tagging to entirely (trap (b)). Preference
    # order puts the standard balance-sheet line first, so a restricted-cash
    # tag only ever wins where the filer abandoned the standard one.
    # DEFINITIONAL CAVEAT on the last entry (ruled in 2026-08-24, S4 third
    # pass): `Cash` is us-gaap's cash EXCLUDING equivalents -- it is not
    # strictly a substitute for the four above it. It sits at LOWEST
    # preference because for a filer that never tags any broader cash line
    # (MEASURED: SLB, 49 quarters 2012Q4-2026Q2 under `Cash` and nothing
    # usable elsewhere) plain `Cash` IS that filer's balance-sheet cash
    # representation. Dominance guarantees it can never displace a proper
    # tag, and concept_resolution.csv records which tag actually won, so the
    # caveat travels with the data: provenance-tracked coverage beats a
    # manufactured gap at 244 scale. A consumer that needs cash-with-
    # equivalents strictly can filter on the resolved tag name.
    "cash": [
        ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),                 # 25/25
        ("us-gaap", "CashAndDueFromBanks"),                                   # 3/25
        ("us-gaap", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),  # 24/25
        ("us-gaap",
         "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsIncludingDisposalGroupAndDiscontinuedOperations"),  # 4/25
        ("us-gaap", "Cash"),
    ],
    "operating_cash_flow": [
        ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),            # 25/25
        ("us-gaap", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),  # 14/25
    ],
    # Diluted earnings per share -- or, for a partnership, per UNIT, which is
    # the same series under the issuer's own capital structure (ruled
    # 2026-08-24, A5.2). MEASURED users across the 244: the diluted
    # per-unit tag 8. Its BASIC sibling
    # (NetIncomeLossPerOutstandingLimitedPartnershipUnitBasicNetOfTax) is
    # deliberately NOT here -- basic is a different measure, the corporate
    # `EarningsPerShareBasic` is not in this family either, and MEASURED it
    # adds zero coverage: all 8 unresolved members reporting it also report
    # the diluted one. Same for the continuing-operations per-unit variant
    # (4 users, all already covered).
    "eps_diluted": [
        ("us-gaap", "EarningsPerShareDiluted"),                               # 24/25
        # 0/25 in E1's mega-caps; kept anyway -- common among single-class
        # filers, and free (F2_SPEC §5.2).
        ("us-gaap", "EarningsPerShareBasicAndDiluted"),                       # 0/25
        ("us-gaap", "NetIncomeLossNetOfTaxPerOutstandingLimitedPartnershipUnitDiluted"),
    ],
    # NO partnership tag here, and that is a MEASURED decision, not an
    # oversight (A5.2): of the 30 members unresolved on this family, ZERO
    # report any unit-count tag in-window. The unit-count tags that do exist
    # (LimitedPartnersCapitalAccountUnitsOutstanding, 7 users) belong to
    # members that already resolve via the dei cover-page fact. All 30 are
    # the multi-class dimensioned-facts gap, which A5.4 parks unfixed.
    "shares_outstanding": [("dei", "EntityCommonStockSharesOutstanding")],    # 25/25
}

# Every (taxonomy, tag) pulled from companyfacts, deduplicated, in family
# order. This is what build_fundamentals() iterates -- the flat E1 CONCEPTS
# list it replaces is gone.
CONCEPTS: list[tuple[str, str]] = list(
    dict.fromkeys(pair for pairs in CONCEPT_FAMILIES.values() for pair in pairs)
)

# tag -> the family it belongs to. Asserted 1:1 (a tag in two families would
# make a resolution ambiguous by construction).
FAMILY_OF_TAG: dict[str, str] = {}
for _family, _pairs in CONCEPT_FAMILIES.items():
    for _taxonomy, _tag in _pairs:
        assert _tag not in FAMILY_OF_TAG, f"{_tag} appears in two families"
        FAMILY_OF_TAG[_tag] = _family

# DELETED HERE BY S4, ON PURPOSE: E1's flat CONCEPTS list, its
# REVENUE_CONCEPTS / CORE_NON_REVENUE_CONCEPTS split, and its three
# hand-curated per-ticker maps -- BANK_TICKERS_MISSING_INDUSTRIAL_CONCEPTS,
# BANK_EXEMPT_CONCEPTS, KNOWN_MIDWINDOW_MIGRATIONS. Every case they encoded
# (JPM/BAC/GS cash -> CashAndDueFromBanks, MA/OXY -> ProfitLoss, SLB's
# operating-income switch, CVX -> the restricted-cash tag) is now an ordinary
# family member that classify_family() resolves -- or refuses to resolve --
# mechanically, with no ticker named anywhere in this file. The maps are
# preserved verbatim in data/f2/status/S4_fundamentals.md and pinned by the
# acceptance tests in test_ingest_fundamentals.py.



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


def _company_identity(row: pd.Series) -> tuple[int, str]:
    """(cik, display_label) for one universe row.

    E2's universe is CIK-keyed and carries no ticker at all (31 member CIKs
    have none in EDGAR's own submissions, and mapping a dead member by its
    former symbol is the F1 trap). E1-shaped frames -- including this
    module's synthetic test fixtures -- do carry one. The label is used for
    display/grouping in reports ONLY; every filter in this module is on
    `cik`.
    """
    cik = int(row["cik"])
    ticker = row.get("ticker")
    label = str(ticker) if isinstance(ticker, str) and ticker.strip() else str(cik)
    return cik, label


def _company_window(
    row: pd.Series, default_start: date, default_end: date,
) -> tuple[date, date]:
    """The window this company's coverage is scored against: its own
    `[coverage_start, coverage_end]` when the universe row carries them
    (hybrid136 always does -- see ingest_metadata.load_universe()), else the
    shared fallback window. A member that joined in 2022 or left in 2019 must
    not be scored against the full corpus window (F2_SPEC §3.4).
    """
    start = row.get("coverage_start")
    end = row.get("coverage_end")
    return (
        start if isinstance(start, date) else default_start,
        end if isinstance(end, date) else default_end,
    )


def build_fundamentals(
    client: EdgarClient, universe: pd.DataFrame, force_refresh: bool = False,
) -> pd.DataFrame:
    """One companyfacts request per company (cached/idempotent per
    EdgarClient.get_companyfacts()'s staleness policy), extracted into one
    row per (company, concept, unit, period, filing).
    """
    all_rows: list[dict] = []
    for _, row in universe.iterrows():
        cik, ticker = _company_identity(row)
        companyfacts = client.get_companyfacts(cik, force=force_refresh)
        for taxonomy, concept in CONCEPTS:
            all_rows.extend(
                extract_concept_facts(companyfacts, taxonomy, concept, ticker, cik)
            )
        print(f"  {ticker} (CIK {cik}): {sum(1 for r in all_rows if r['cik'] == cik)} fact rows")

    df = pd.DataFrame(all_rows)
    if df.empty:
        raise RuntimeError(
            "build_fundamentals() produced zero rows across the whole universe -- "
            "something is badly wrong (concept names changed, or every "
            "companyfacts fetch failed silently). Refusing to write an empty parquet."
        )
    # Deterministic row order: helps diffing/inspection, not a correctness
    # requirement (pit.value_as_of() doesn't rely on row order).
    df = df.sort_values(["cik", "concept", "period_end", "filed", "accession_number"]).reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# The alias / migration classifier (F2_SPEC §5.3)
# ---------------------------------------------------------------------------

# Per (cik, family), over the company's own coverage window, using only rows
# from OPERATING forms, the family is classified into exactly one of six
# states. Three resolve; three are UNRESOLVED and each emits a FATAL
# `fundamentals_alias_unresolved` row naming the tags seen, their per-quarter
# coverage and the exact reason. There is deliberately NO fallback to "the tag
# with the most rows" and no per-ticker override map: an UNRESOLVED pair must
# fail loudly, because the alternative -- E1's behaviour -- was silently
# building features off a tag that had gone stale years earlier (the Phase C
# red-team BLOCKER: JNJ operating income frozen at 2015, JPM/BAC cash frozen
# at 2018/2020).
#
# DOMINANT is the 2026-08-24 ruling's addition: with substitutes-only
# families, two tags covering the same quarters is a filer reporting one
# series under two names, not an ambiguity, and preference order decides it.
# OVERLAP then means what its name says -- genuine ambiguity, no tag dominant.
STATE_SINGLE = "SINGLE"
STATE_MIGRATION = "MIGRATION"
STATE_DOMINANT = "DOMINANT"
STATE_OVERLAP = "OVERLAP"
STATE_PARTIAL = "PARTIAL"
STATE_ABSENT = "ABSENT"

SEVERITY_RESOLVED = "resolved"
SEVERITY_UNRESOLVED = "UNRESOLVED"

RESOLVED_STATES = (STATE_SINGLE, STATE_MIGRATION, STATE_DOMINANT)
UNRESOLVED_STATES = (STATE_OVERLAP, STATE_PARTIAL, STATE_ABSENT)

# A tag "covers" the family when it reaches this fraction of the company's own
# reportable quarters (target_quarters() over [coverage_start, coverage_end]).
RESOLUTION_COVERAGE_BAR = 0.75
# Union coverage in [PARTIAL_COVERAGE_FLOOR, RESOLUTION_COVERAGE_BAR) is the
# spec's PARTIAL band. Anything below the floor but still non-empty is also
# reported as PARTIAL -- see classify_family()'s docstring; both are
# UNRESOLVED, so the severity does not depend on which side of 40% it lands.
PARTIAL_COVERAGE_FLOOR = 0.40
# "Disjoint (allowing <=1 quarter of overlap)" -- one shared quarter is the
# normal shape of a clean tag switch (the quarter the filer reports both).
MIGRATION_MAX_OVERLAP_QUARTERS = 1

# A tag can clear the coverage bar over an 11-year window and still be DEAD:
# it covered 2015-2024 and stopped. Resolving to it would hand F5 a series
# that silently freezes -- exactly the Phase C red-team BLOCKER. So a tag also
# has to be CURRENT: its last covered quarter must be within this many
# quarters of the company's own last quarter with any fundamentals data at all
# (that anchor, rather than the calendar window end, is what keeps a delisted
# member from looking stale merely for having stopped filing).
#
# MEASURED over the 25 cached companyfacts on the E2 windows: of 371
# (company, family, tag) instances at or above the bar, 366 have a gap of 0,
# two have a gap of 1 (V ProfitLoss, PG shares_outstanding), NONE has 2, and
# the only larger gaps are the three genuinely dead tags -- SLB
# OperatingIncomeLoss (9), OXY NetIncomeLoss (9), GOOGL
# RevenueFromContractWithCustomerExcludingAssessedTax (5). The threshold sits
# in that empty band, two quarters above the largest normal gap.
STALE_TAIL_MAX_QUARTERS = 2

# Concentrated missingness is a blocker, not a per-company footnote
# (EXPANSION_PLAN §3.5): a family that fails for more than one in five of a
# sector's members is a taxonomy mismatch, not filer noise, and would
# silently bias any sector-stratified E2 result. STRICTLY greater than --
# 21% of a sector fires, 19% (and exactly 20%) does not.
SECTOR_BLOCKER_FRACTION = 0.20

# HANDOFF §2a trap (c): MA's only in-window NetIncomeLoss rows are DEF 14A
# proxy compensation-table disclosures, not operating filings. Coverage is
# therefore counted ONLY from 10-K / 10-Q / 8-K and their /A amendments; every
# other form (DEF 14A, S-1, 20-F, 11-K, ...) is excluded from the classifier's
# denominator and numerator alike.
#
# 8-K IS ADMITTED DELIBERATELY (stated explicitly after S7 finding B21, which
# noted the docstring argued only the DEF 14A exclusion): an earnings release
# is a real, dated, point-in-time disclosure of the same GAAP fact, and
# excluding it would drop 12,172 of the parquet's rows and penalise filers who
# tag their release exhibit properly. So a family CAN clear the coverage bar
# on earnings-release facts rather than periodic-filing facts. MEASURED at 244
# scale: that never actually happens -- ZERO resolved flow-family pairs have
# their quarterly-length facts only from 8-Ks, and zero have none at all.
OPERATING_FORMS = frozenset({"10-K", "10-Q", "8-K"})


def is_operating_form(form: Optional[str]) -> bool:
    """True for 10-K / 10-Q / 8-K and their /A amendments only."""
    if not isinstance(form, str):
        return False
    base = form.strip().upper()
    if base.endswith("/A"):
        base = base[:-2]
    return base in OPERATING_FORMS


def _quarter_label(quarter: tuple[int, int]) -> str:
    return f"{quarter[0]}Q{quarter[1]}"


def _quarter_index(quarter: tuple[int, int]) -> int:
    """Quarters as a monotone integer, so gaps subtract."""
    return quarter[0] * 4 + quarter[1]


# Fact duration buckets (S7 finding B15). `_quarter_bucket()` buckets on
# `period_end` alone, so a 12-month or 9-month fact "covers" the quarter it
# ends in. That is deliberate -- coverage asks "was this concept disclosed for
# this period", not "at what frequency" -- but the resolution row has to SAY
# so, because `tags` otherwise looks like a promise of a quarterly series.
DURATION_BUCKET_DAYS = ((115, "Q"), (210, "H1"), (300, "9M"), (400, "FY"))


def _duration_buckets(period_start: pd.Series, period_end: pd.Series) -> pd.Series:
    """Vectorised duration classification: instant / Q / H1 / 9M / FY / other."""
    start = pd.to_datetime(period_start, errors="coerce")
    end = pd.to_datetime(period_end, errors="coerce")
    days = (end - start).dt.days
    out = pd.Series("other", index=days.index, dtype=object)
    out[days.isna()] = "instant"
    previous = 0
    for limit, label in DURATION_BUCKET_DAYS:
        out[(days > previous) & (days <= limit)] = label
        previous = limit
    return out


# Units. `unit` is stored per fact but was never consulted by the classifier
# (S7 finding B11): CIK 895728 Enbridge reports 100% of its monetary
# fundamentals in CAD while its price series is USD, so any
# fundamentals-to-price ratio would be silently wrong by the exchange rate.
# The classifier still does not USE the unit -- resolution states are
# unchanged -- but every row now carries its dominant unit and a mixed flag,
# and a non-USD reporting currency is a named WARN.
NON_USD_CHECK = "fundamentals_non_usd_reporting"


def _unit_currency(unit: Optional[str]) -> Optional[str]:
    """The ISO-4217-shaped currency of a unit, or None if it is not monetary.

    `USD` -> USD, `CAD/shares` -> CAD, `shares` / `pure` / `segment` /
    `BillionsCubicFeet` -> None. Deliberately a shape test, not a currency
    list: an unknown three-letter code is a currency worth WARNing about.
    """
    if not isinstance(unit, str) or not unit:
        return None
    head = unit.split("/")[0]
    return head if len(head) == 3 and head.isalpha() and head.isupper() else None


def _profile(counts: dict[str, int]) -> str:
    """A Counter as a compact, deterministic `Q:40|FY:11` string."""
    return "|".join(
        f"{k}:{v}" for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    )


@dataclass(frozen=True)
class ConceptResolution:
    """One (cik, family) verdict. `tags` is the resolution itself -- the tag
    (SINGLE / DOMINANT) or the chronological tag sequence (MIGRATION) a
    downstream consumer should build the series from -- NOT merely the tags
    observed. `alternates` are the co-reported tags that also cleared the
    coverage bar and lost on preference; they are recorded, never used.
    For an UNRESOLVED state `tags` is the tags seen, for the record, and
    `resolved_tags` is empty by construction: no code path hands a caller a
    tag for a pair the classifier refused.

    WHAT `tags` DOES NOT PROMISE (S7 findings B11 and B15). It names a tag,
    not a validated series: the classifier resolves on DISCLOSURE COVERAGE
    and nothing else. Two properties a consumer must read off the row instead
    of assuming --

      `unit` / `units_mixed`  the dominant unit of the resolving rows and
                              whether more than one appears. A non-USD
                              reporting currency resolves exactly as cleanly
                              as USD and is NOT converted anywhere in F2.
      `duration_mix`          the profile of fact durations (`instant` / `Q`
                              / `H1` / `9M` / `FY`). Coverage buckets on
                              `period_end` alone, so nothing here makes a
                              resolved series quarterly.
    """

    cik: int
    family: str
    state: str
    tags: tuple[str, ...]
    switch_quarter: str
    coverage: float
    severity: str
    tag_coverage: tuple[tuple[str, int], ...]   # (tag, covered quarters), desc
    n_target: int
    alternates: tuple[str, ...] = ()
    stale_tags: tuple[str, ...] = ()            # cleared the bar but had died
    tag_last_quarter: tuple[tuple[str, str], ...] = ()   # (tag, "2024Q1")
    last_data_quarter: str = ""                 # the company's own, any family
    unit: str = ""                              # dominant unit of the rows
    units_mixed: bool = False
    duration_mix: str = ""                      # e.g. "Q:40|FY:11"
    ticker: Optional[str] = None

    @property
    def resolved_tags(self) -> list[str]:
        return list(self.tags) if self.severity == SEVERITY_RESOLVED else []

    @property
    def currency(self) -> Optional[str]:
        """The ISO-shaped currency of `unit`, or None if it is not monetary."""
        return _unit_currency(self.unit)

    @property
    def is_non_usd(self) -> bool:
        return self.currency is not None and self.currency != "USD"

    def coverage_detail(self) -> str:
        if not self.tag_coverage:
            return "(no tag has an in-window operating-form row)"
        n = self.n_target or 1
        last = dict(self.tag_last_quarter)
        return ", ".join(
            f"{tag} {covered}/{self.n_target} ({covered / n:.0%}, last "
            f"{last.get(tag, '?')})" + (" [STALE]" if tag in self.stale_tags else "")
            for tag, covered in self.tag_coverage
        )


@dataclass(frozen=True)
class _Verdict:
    state: str
    tags: tuple[str, ...]
    switch_quarter: str
    coverage: float
    alternates: tuple[str, ...] = ()
    stale_tags: tuple[str, ...] = ()


def classify_family(
    family: str,
    quarters_by_tag: dict[str, set],
    n_target: int,
    last_data_quarter: Optional[tuple[int, int]] = None,
) -> _Verdict:
    """The six-state classifier for one (company, family), given each tag's
    set of covered reportable quarters and the company's own last quarter
    with any fundamentals data (the staleness anchor).

    States (F2_SPEC §5.3 as amended 2026-08-24, amendment A1):

      SINGLE     exactly one tag clears the 75% bar, and it is current
      MIGRATION  >=2 tags, covered-quarter sets disjoint (<=1 quarter of
                 overlap), union >= 75%, and the last tag in the sequence is
                 current -- the switch quarter is recorded
      DOMINANT   >=2 tags clear the bar (a filer co-reporting one series under
                 two names): the highest-PREFERENCE current tag wins and the
                 others are recorded as `alternates`
      OVERLAP    >=2 tags share quarters, union >= 75%, and NO tag clears the
                 bar -- genuine ambiguity, nothing to prefer     UNRESOLVED
      PARTIAL    union below the bar, or every bar-clearing tag is STALE
                 (a dead tag is not a series)                    UNRESOLVED
      ABSENT     no tag in the family has any in-window row      UNRESOLVED

    Two clarifications the spec is silent on, both severity-neutral:
    §5.3 defines PARTIAL as union coverage in [40%, 75%), leaving (0%, 40%)
    unnamed -- a family with a couple of stray quarters has rows (so it is not
    ABSENT) and cannot resolve, so it is PARTIAL with its real coverage
    number; and a family whose only bar-clearing tags are stale is PARTIAL
    rather than a seventh state, with the reason spelled out in the FATAL row.
    """
    covered = {tag: qs for tag, qs in quarters_by_tag.items() if qs}
    if not covered:
        return _Verdict(STATE_ABSENT, (), "", 0.0)

    union: set = set().union(*covered.values())
    coverage = len(union) / n_target if n_target else 0.0
    seen = tuple(sorted(covered, key=lambda t: (-len(covered[t]), t)))
    preference = [tag for _, tag in CONCEPT_FAMILIES[family] if tag in covered]

    def is_stale(tag: str) -> bool:
        if last_data_quarter is None:
            return False
        gap = _quarter_index(last_data_quarter) - _quarter_index(max(covered[tag]))
        return gap > STALE_TAIL_MAX_QUARTERS

    at_bar = [
        tag for tag in preference
        if n_target and len(covered[tag]) / n_target >= RESOLUTION_COVERAGE_BAR
    ]
    stale = tuple(tag for tag in at_bar if is_stale(tag))
    live = [tag for tag in at_bar if tag not in stale]

    if live:
        winner = live[0]
        alternates = tuple(t for t in at_bar if t != winner)
        state = STATE_SINGLE if len(at_bar) == 1 else STATE_DOMINANT
        return _Verdict(state, (winner,), "", coverage, alternates, stale)

    if len(covered) >= 2 and coverage >= RESOLUTION_COVERAGE_BAR:
        dead = tuple(t for t in covered if is_stale(t))
        alive = [t for t in covered if t not in dead]
        newest = max(covered, key=lambda t: (max(covered[t]), t))
        overlap = sum(len(qs) for qs in covered.values()) - len(union)
        if is_stale(newest):
            # Every tag in the family died: the series ended, whatever its
            # union coverage over the window says.
            return _Verdict(STATE_PARTIAL, seen, "", coverage, stale_tags=dead)
        if overlap <= MIGRATION_MAX_OVERLAP_QUARTERS or len(alive) == 1:
            # A tag switch: either a clean disjoint hand-off, or a co-reported
            # predecessor that has since died leaving exactly one live tag.
            # Both give F5 an unambiguous chronological series to build.
            #
            # Ordered by LAST covered quarter, so `tags[-1]` is always the
            # current tag -- with co-reporting, first-seen order can put the
            # dead tag last. The switch quarter is where the successor
            # actually takes over: its first quarter after its predecessor's
            # last, not its own first appearance.
            chronological = sorted(covered, key=lambda t: (max(covered[t]), t))
            switches = []
            for earlier, later in zip(chronological, chronological[1:]):
                after = [q for q in covered[later] if q > max(covered[earlier])]
                switches.append(_quarter_label(min(after)) if after else "")
            return _Verdict(STATE_MIGRATION, tuple(chronological),
                            ";".join(switches), coverage, stale_tags=dead)
        # Two or more CURRENT tags share quarters and none is dominant --
        # genuine ambiguity, the only thing OVERLAP now means.
        return _Verdict(STATE_OVERLAP, seen, "", coverage, stale_tags=dead)

    # Everything left is unusable: union below the bar, or every tag that
    # cleared it is dead. Both are PARTIAL, and `stale_tags` says which.
    return _Verdict(STATE_PARTIAL, seen, "", coverage, stale_tags=stale)


def classify_universe(
    df: pd.DataFrame,
    universe: pd.DataFrame,
    window_start: date = CORPUS_WINDOW_START,
    window_end: date = CORPUS_WINDOW_END,
) -> list[ConceptResolution]:
    """Classify every (member CIK, family) pair. One row per pair, always --
    a company with no facts at all still gets ABSENT rows rather than
    disappearing from the report.
    """
    work = df.copy()
    if work.empty:
        work = pd.DataFrame(
            columns=["cik", "concept", "form", "filed", "period_end"]
        )
    work["filed_date"] = pd.to_datetime(work["filed"], errors="coerce")
    # A row EDGAR gave no parseable `filed` date for cannot be placed in a
    # point-in-time window at all, so it is not coverage. Dropping it can only
    # push a family toward UNRESOLVED (loud), never toward a false resolution.
    work = work[work["filed_date"].notna()]
    work["filed_date"] = work["filed_date"].dt.date
    work["quarter"] = work["period_end"].map(_quarter_bucket)
    work = work[work["form"].map(is_operating_form)]
    if "unit" not in work.columns:
        work["unit"] = ""
    work["duration"] = (
        _duration_buckets(work.get("period_start"), work["period_end"])
        if not work.empty else pd.Series(dtype=object)
    )
    by_cik = {int(cik): g for cik, g in work.groupby("cik")} if not work.empty else {}

    out: list[ConceptResolution] = []
    for _, row in universe.iterrows():
        cik, ticker = _company_identity(row)
        w_start, w_end = _company_window(row, window_start, window_end)
        target_qs = target_quarters(w_start, w_end)
        n_target = len(target_qs)

        company = by_cik.get(cik)
        quarters_by_tag: dict[str, set] = {}
        units_by_tag: dict[str, collections.Counter] = {}
        durations_by_tag: dict[str, collections.Counter] = {}
        if company is not None:
            company = company[
                (company["filed_date"] >= w_start) & (company["filed_date"] <= w_end)
            ]
            for tag, sub in company.groupby("concept"):
                quarters_by_tag[str(tag)] = {
                    q for q in sub["quarter"] if q in target_qs
                }
                units_by_tag[str(tag)] = collections.Counter(sub["unit"].fillna(""))
                durations_by_tag[str(tag)] = collections.Counter(sub["duration"])

        # The staleness anchor: the company's own most recent reportable
        # quarter with ANY fundamentals data. Anchoring on this rather than on
        # the calendar window end is what stops a delisted member -- whose
        # window runs 400 days past its last membership date, with no filings
        # in the tail -- from looking stale in every family at once.
        data_quarters = {q for qs in quarters_by_tag.values() for q in qs}
        last_data_quarter = max(data_quarters, default=None)

        # DENOMINATOR (ruled 2026-08-24, F2_SPEC §5.7 A5.1): coverage is
        # scored against the company's own FILED SPAN inside its window --
        # first to last quarter in which it reported any fundamentals -- not
        # against the whole window. This inherits S2's identical ruling for
        # `plausible_filing_counts`.
        #
        # Charging a company for quarters before it existed or after it was
        # acquired measures its corporate history, not its data quality: AZEK
        # (CIK 1782754, IPO 2020, acquired 2025) is fully covered for its
        # actual life and scored 11/16 = 69% PARTIAL on ALL 14 families under
        # the window denominator. Interior holes -- the thing this check is
        # for -- still count, because the span is trimmed only at the ends.
        target_qs = {
            q for q in target_qs
            if data_quarters and min(data_quarters) <= q <= max(data_quarters)
        }
        n_target = len(target_qs)

        for family, pairs in CONCEPT_FAMILIES.items():
            family_quarters = {
                tag: quarters_by_tag.get(tag, set()) for _, tag in pairs
            }
            verdict = classify_family(
                family, family_quarters, n_target, last_data_quarter
            )
            detail = tuple(
                sorted(
                    ((tag, len(qs)) for tag, qs in family_quarters.items() if qs),
                    key=lambda tc: (-tc[1], tc[0]),
                )
            )
            tag_last = tuple(
                (tag, _quarter_label(max(qs)))
                for tag, qs in family_quarters.items() if qs
            )
            # Unit and duration are described over the rows the resolution
            # actually points at (the tags seen, when there is no
            # resolution) -- describing the whole family would report a
            # currency or a frequency the consumer will never read.
            described = verdict.tags or tuple(
                tag for tag, qs in family_quarters.items() if qs
            )
            units: collections.Counter = collections.Counter()
            durations: collections.Counter = collections.Counter()
            for tag in described:
                units.update(units_by_tag.get(tag, {}))
                durations.update(durations_by_tag.get(tag, {}))
            out.append(
                ConceptResolution(
                    cik=cik,
                    family=family,
                    state=verdict.state,
                    tags=verdict.tags,
                    switch_quarter=verdict.switch_quarter,
                    coverage=verdict.coverage,
                    severity=(
                        SEVERITY_RESOLVED if verdict.state in RESOLVED_STATES
                        else SEVERITY_UNRESOLVED
                    ),
                    tag_coverage=detail,
                    n_target=n_target,
                    alternates=verdict.alternates,
                    stale_tags=verdict.stale_tags,
                    tag_last_quarter=tag_last,
                    last_data_quarter=(
                        _quarter_label(last_data_quarter) if last_data_quarter else ""
                    ),
                    unit=units.most_common(1)[0][0] if units else "",
                    units_mixed=len(units) > 1,
                    duration_mix=_profile(durations),
                    ticker=ticker,
                )
            )
    return out


_UNRESOLVED_REASON = {
    STATE_ABSENT: (
        "no tag in this family has a single in-window row from an operating "
        "form (10-K/10-Q/8-K + /A). Non-operating forms -- DEF 14A proxy "
        "compensation tables above all -- are excluded by design and never "
        "count as coverage."
    ),
    STATE_OVERLAP: (
        "two or more tags share quarters and NONE of them clears the "
        f"{RESOLUTION_COVERAGE_BAR:.0%} coverage bar, so there is no dominant "
        "tag to prefer and no migration pattern to follow -- genuine "
        "ambiguity. The classifier will not pick one, and there is no "
        "per-ticker override. F5 must refuse to build this series."
    ),
    STATE_PARTIAL: (
        "the tags' union does not reach the "
        f"{RESOLUTION_COVERAGE_BAR:.0%} coverage bar, so any series built "
        "from them would be silently gapped."
    ),
}

_STALE_REASON = (
    "every tag that cleared the {bar:.0%} coverage bar is STALE -- its "
    "coverage stops more than {max_gap} quarter(s) before {last}, this "
    "company's own last quarter with fundamentals data. A tag can clear a "
    "bar computed over an 11-year window and still have died years ago; "
    "resolving to it is exactly how E1 froze JNJ's operating income at 2015. "
    "Stale: {stale}."
)


def resolution_problems(
    resolutions: list[ConceptResolution],
) -> list[ValidationProblem]:
    """One FATAL row per UNRESOLVED (cik, family). Never a WARN, never a
    downgrade, never a stale fallback (F2_SPEC §5.3).
    """
    problems: list[ValidationProblem] = []
    for r in resolutions:
        if r.severity != SEVERITY_UNRESOLVED:
            continue
        if r.stale_tags and r.state == STATE_PARTIAL:
            reason = _STALE_REASON.format(
                bar=RESOLUTION_COVERAGE_BAR, max_gap=STALE_TAIL_MAX_QUARTERS,
                last=r.last_data_quarter or "its last reported quarter",
                stale=", ".join(r.stale_tags),
            )
            problems.append(
                ValidationProblem(
                    r.cik, "fundamentals_alias_unresolved", "FATAL",
                    f"{r.family}: {r.state} over {r.n_target} reportable "
                    f"quarters -- {r.coverage_detail()}; union "
                    f"{r.coverage:.0%}. {reason}",
                    ticker=r.ticker,
                )
            )
            continue
        reason = _UNRESOLVED_REASON[r.state]
        if r.state == STATE_PARTIAL and r.coverage < PARTIAL_COVERAGE_FLOOR:
            reason += (
                f" It is below the {PARTIAL_COVERAGE_FLOOR:.0%} floor where "
                f"F2_SPEC §5.3's PARTIAL band starts, and is reported as "
                f"PARTIAL rather than ABSENT because the family does have "
                f"in-window operating-form rows."
            )
        problems.append(
            ValidationProblem(
                r.cik, "fundamentals_alias_unresolved", "FATAL",
                f"{r.family}: {r.state} over {r.n_target} reportable quarters "
                f"-- {r.coverage_detail()}; union {r.coverage:.0%}. {reason}",
                ticker=r.ticker,
            )
        )
    return problems + non_usd_problems(resolutions)


def non_usd_problems(
    resolutions: list[ConceptResolution],
) -> list[ValidationProblem]:
    """WARN per RESOLVED (cik, family) whose dominant unit is a non-USD
    currency (S7 finding B11).

    Nothing is converted and no state changes -- the point is that a
    cleanly-resolved series can be denominated in a different currency from
    the price series it will be divided by, and until now nothing anywhere
    said so. Unresolved pairs are already FATAL, so they are not warned about
    twice.
    """
    return [
        ValidationProblem(
            r.cik, NON_USD_CHECK, "WARN",
            f"{r.family}: resolved series is reported in {r.currency}, not USD "
            f"(dominant unit {r.unit!r}"
            + (", MIXED units in this family" if r.units_mixed else "")
            + "). Prices for this member are USD, so ANY "
            "fundamentals-to-price ratio (P/E, P/B, market-cap-to-book, "
            "earnings yield) is wrong by the exchange rate unless F5 "
            "converts. No conversion happens in F2.",
            ticker=r.ticker,
        )
        for r in resolutions
        if r.severity == SEVERITY_RESOLVED and r.is_non_usd
    ]


# ---------------------------------------------------------------------------
# The companyfacts tail-lag check (S7 finding B5)
# ---------------------------------------------------------------------------

# Both halves of the coverage machinery are anchored on the data being
# checked: the denominator is the company's own filed span (A5.1) and the
# staleness rule its own last data quarter (A1.3). That is right for the
# questions they ask, but it makes ONE failure mode structurally invisible --
# a companyfacts document truncated at the tail scores 100% coverage with no
# alarm, because the missing quarters are missing from the denominator too.
#
# This check breaks the circularity by comparing against an INDEPENDENT
# source: the filing metadata in the E2 database, read-only. If a member filed
# periodic reports after its last fundamentals fact, those reports' facts are
# missing from companyfacts.
#
# MEASURED over the 244 (2026-08-24, offline): 22 members have >=1 in-window
# 10-K/10-Q filed after their last fact. 21 of them lag by exactly ONE filing
# at 82-92 days -- the ordinary propagation lag of the most recent quarter,
# reported at INFO. Exactly one, CITIGROUP (831001), lags by TWO filings and
# 167 days while scoring 0.9767 with 12 of 14 families resolved; that is the
# WARN case. The leading edge is clean (no member has a periodic filing before
# its first fact), so this is a tail-only hole.
TAIL_LAG_CHECK = "companyfacts_tail_lag"
TAIL_LAG_WARN_FILINGS = 2      # >= this many periodic filings behind -> WARN
PERIODIC_FORMS = ("10-K", "10-Q", "10-K/A", "10-Q/A")


def load_periodic_filing_dates(db_path: Path = DB_PATH) -> dict[int, list[str]]:
    """{cik: [filing_date, ...]} for every 10-K/10-Q in the E2 database.

    Opened READ-ONLY (`mode=ro`): this module never writes filing metadata,
    and the check must not be able to disturb S3's table. Returns {} if the
    database or the table does not exist yet -- the caller reports that as a
    finding rather than skipping silently.
    """
    import sqlite3

    path = Path(db_path)
    if not path.exists():
        return {}
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        placeholders = ",".join("?" for _ in PERIODIC_FORMS)
        rows = conn.execute(
            f"SELECT cik, filing_date FROM filings WHERE form IN ({placeholders})",
            PERIODIC_FORMS,
        ).fetchall()
    except Exception:
        return {}
    finally:
        conn.close()
    out: dict[int, list[str]] = {}
    for cik, filing_date in rows:
        out.setdefault(int(cik), []).append(str(filing_date))
    return out


def tail_lag_problems(
    df: pd.DataFrame,
    universe: pd.DataFrame,
    periodic_filing_dates: dict[int, list[str]],
    window_start: date = CORPUS_WINDOW_START,
    window_end: date = CORPUS_WINDOW_END,
) -> list[ValidationProblem]:
    """One finding per member whose companyfacts tail lags its own filings.

    WARN at `TAIL_LAG_WARN_FILINGS` periodic filings or more, INFO at one --
    the single-filing case is the ordinary propagation lag of the most recent
    quarter and would drown the real signal if it were a WARN.

    The comparison is scoped to the company's own coverage window, like every
    other check here. A member whose window closed years before it stopped
    filing (EIDP, CIK 30554, facts stop 2019 while it files through 2026) is
    complete WITHIN its window and is not warned about; the run report states
    the corpus-window count separately so the shape is still visible.

    Emits nothing at all if `periodic_filing_dates` is empty -- the caller
    decides how to report an unavailable database; see run().
    """
    if not periodic_filing_dates:
        return []
    last_fact = (
        df.groupby("cik")["filed"].max().to_dict() if not df.empty else {}
    )
    problems: list[ValidationProblem] = []
    for _, row in universe.iterrows():
        cik, ticker = _company_identity(row)
        w_start, w_end = _company_window(row, window_start, window_end)
        latest_fact = last_fact.get(cik)
        if not latest_fact:
            continue        # ABSENT everywhere already; nothing to lag behind
        in_window = sorted(
            d for d in periodic_filing_dates.get(cik, [])
            if w_start.isoformat() <= d <= w_end.isoformat()
        )
        behind = [d for d in in_window if d > str(latest_fact)]
        if not behind:
            continue
        lag_days = (date.fromisoformat(behind[-1]) - date.fromisoformat(str(latest_fact))).days
        severity = "WARN" if len(behind) >= TAIL_LAG_WARN_FILINGS else "INFO"
        problems.append(
            ValidationProblem(
                cik, TAIL_LAG_CHECK, severity,
                f"companyfacts stops at {latest_fact} but {len(behind)} "
                f"in-window periodic filing(s) were filed after it (latest "
                f"{behind[-1]}, {lag_days} days later): "
                f"{', '.join(behind)}. Those filings' facts are absent from "
                f"the companyfacts document, so this member's coverage and "
                f"staleness scores -- both anchored on its own data -- cannot "
                f"see the gap. Re-fetch companyfacts before trusting its "
                f"latest quarters."
                + ("" if severity == "WARN" else
                   " One filing behind is the ordinary propagation lag of the "
                   "most recent quarter; reported, not escalated."),
                ticker=ticker,
            )
        )
    return problems


@dataclass(frozen=True)
class SectorBlocker:
    """One (sector, family) cell whose UNRESOLVED share exceeds
    SECTOR_BLOCKER_FRACTION -- reported at the TOP of the run output, never
    buried in a per-company list.
    """

    sector: str
    family: str
    n_unresolved: int
    n_members: int
    fraction: float
    ciks: tuple[int, ...]
    # Which states the failures are, most common first. An ABSENT-only cell
    # says "this sector does not report this concept"; a cell with
    # PARTIAL/OVERLAP in it says "the data is there and unusable". Both are
    # blockers and both are printed -- the split is what makes the top-of-run
    # table readable instead of a wall.
    states: tuple[tuple[str, int], ...] = ()

    @property
    def states_label(self) -> str:
        return " ".join(f"{state}:{n}" for state, n in self.states)


# The ONE mechanism by which a (sector, family) cell can be kept out of the
# BLOCKER aggregation (ruled in 2026-08-24, S4 third pass; F2_SPEC §5.5 A2).
# Key: (sector or "*", family) -> one-line reason. Semantics, deliberately
# narrow:
#
#   - An exemption removes a cell from the BLOCKER TABLE ONLY. It never
#     silences a per-(cik, family) UNRESOLVED row: every failure is still
#     counted, named, and emitted as a FATAL `fundamentals_alias_unresolved`.
#   - Every exemption is printed in the run report whether it fired or not,
#     and one that never fires is reported as DEAD -- a bug in this dict, not
#     a harmless leftover. Same discipline as
#     data/f2/validation_exceptions.csv (F2_SPEC §3.2).
#   - Entries are added by ruling only. A cell that measurement suggests
#     belongs here goes into the stage report as PROPOSED-not-exempted.
#
# Why the mechanism exists at all: HANDOFF §4's crying-wolf lesson. An
# aggregate alarm that always carries structurally-expected cells trains its
# reader to skim past the one real cell in the list. These three are
# structural facts about US GAAP, not data problems.
BLOCKER_EXEMPT_CELLS: dict[tuple[str, str], str] = {
    ("*", "minority_interest"):
        "MinorityInterest exists only for a filer with non-wholly-owned "
        "subsidiaries; its absence is the company's structure, not a gap.",
    ("*", "net_income_to_common"):
        "NetIncomeLossAvailableToCommonStockholdersBasic differs from net "
        "income only when preferred dividends exist; most filers have none.",
    # Added 2026-08-24 (A5.3) on the 244-scale table. SUPERSEDES the earlier
    # ("financials", "operating_income") entry, which is deleted, not kept
    # beside this one: the fact it stated turned out not to be a banking fact.
    ("*", "operating_income"):
        "E1's HANDOFF §2a trap (a) generalises well past banks: MEASURED at "
        "244 scale, operating_income is UNRESOLVED for 31% of energy, 25% of "
        "healthcare, 29% of materials_realestate and 21% of industrials "
        "members. Presenting a GAAP operating-income line is a "
        "sector-correlated reporting style, not a data quality signal, so F5 "
        "must treat operating_income as a NON-UNIVERSAL feature; "
        "pretax_income is the resolving fallback family.",
    ("*", "liabilities"):
        "Total liabilities is ABSENT-dominated for 21-56% of members in 7 of "
        "8 sectors -- a filer-taxonomy choice, not a gap. F5 NOTE: the "
        "quantity is derivable as liabilities_and_equity - equity, both of "
        "which resolve far more widely; that derivation is F5's call to make "
        "in the open, which is why the tags stay in separate families.",
}


def blocker_exemption_reason(sector: str, family: str) -> Optional[str]:
    """The exemption covering this cell, or None. `*` matches any sector."""
    return (
        BLOCKER_EXEMPT_CELLS.get((sector, family))
        or BLOCKER_EXEMPT_CELLS.get(("*", family))
    )


def _unresolved_cells(
    resolutions: list[ConceptResolution], universe: pd.DataFrame,
) -> list[SectorBlocker]:
    """Every (sector, family) cell above the 20% threshold, exemptions NOT
    applied. The one place the aggregation is computed.
    """
    sector_of = {
        int(row["cik"]): str(row.get("sector") or "unknown")
        for _, row in universe.iterrows()
    }
    members: dict[str, set] = {}
    unresolved: dict[tuple[str, str], list[ConceptResolution]] = {}
    for r in resolutions:
        sector = sector_of.get(r.cik, "unknown")
        members.setdefault(sector, set()).add(r.cik)
        if r.severity == SEVERITY_UNRESOLVED:
            unresolved.setdefault((sector, r.family), []).append(r)

    cells: list[SectorBlocker] = []
    for (sector, family), failures in unresolved.items():
        n_members = len(members[sector])
        fraction = len(failures) / n_members if n_members else 0.0
        if fraction > SECTOR_BLOCKER_FRACTION:
            counts: dict[str, int] = {}
            for r in failures:
                counts[r.state] = counts.get(r.state, 0) + 1
            cells.append(
                SectorBlocker(
                    sector=sector, family=family, n_unresolved=len(failures),
                    n_members=n_members, fraction=fraction,
                    ciks=tuple(sorted(r.cik for r in failures)),
                    states=tuple(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))),
                )
            )
    return sorted(cells, key=lambda b: (-b.fraction, b.sector, b.family))


def sector_blockers(
    resolutions: list[ConceptResolution], universe: pd.DataFrame,
) -> list[SectorBlocker]:
    """Aggregate UNRESOLVED by (sector, family) and flag every cell above the
    20% threshold that is not exempt under BLOCKER_EXEMPT_CELLS. Sorted
    worst-first. Exemptions change this table and nothing else -- the
    per-pair FATAL rows are produced by resolution_problems(), which has no
    idea this dict exists.
    """
    return [
        cell for cell in _unresolved_cells(resolutions, universe)
        if blocker_exemption_reason(cell.sector, cell.family) is None
    ]


@dataclass(frozen=True)
class BlockerExemptionStatus:
    """One BLOCKER_EXEMPT_CELLS entry and what it actually did this run."""

    sector: str
    family: str
    reason: str
    suppressed: tuple[SectorBlocker, ...] = ()

    @property
    def fired(self) -> bool:
        return bool(self.suppressed)


def blocker_exemption_statuses(
    resolutions: list[ConceptResolution], universe: pd.DataFrame,
) -> list[BlockerExemptionStatus]:
    """Every exemption in the dict, with the cells it suppressed -- including
    the ones that suppressed nothing, which is how a dead entry gets caught.
    """
    cells = _unresolved_cells(resolutions, universe)
    statuses = []
    for (sector, family), reason in sorted(BLOCKER_EXEMPT_CELLS.items()):
        suppressed = tuple(
            c for c in cells
            if c.family == family and (sector == "*" or c.sector == sector)
        )
        statuses.append(
            BlockerExemptionStatus(sector, family, reason, suppressed)
        )
    return statuses


def print_blocker_exemptions(statuses: list[BlockerExemptionStatus]) -> None:
    """Printed next to the BLOCKER table, always, fired or not."""
    print(f"\nBLOCKER exemptions ({len(statuses)} in BLOCKER_EXEMPT_CELLS; "
          f"they suppress table rows only -- every per-company UNRESOLVED row "
          f"is still emitted as FATAL):")
    for s in statuses:
        if s.fired:
            cells = ", ".join(
                f"{c.sector} {c.n_unresolved}/{c.n_members}" for c in s.suppressed
            )
            print(f"  [suppressed {len(s.suppressed)}] ({s.sector}, {s.family}): "
                  f"{cells}")
        else:
            print(f"  [DEAD -- suppressed nothing this run; fix the dict rather "
                  f"than leaving it] ({s.sector}, {s.family})")
        print(f"      reason: {s.reason}")


def blocker_problems(blockers: list[SectorBlocker]) -> list[ValidationProblem]:
    """The blockers, in the same ValidationProblem vocabulary as everything
    else, so they persist in the DB rather than living only on stdout. Scoped
    to the run (RUN_SCOPE_CIK), because a blocker is about a sector, not a
    company.
    """
    return [
        ValidationProblem(
            RUN_SCOPE_CIK, "fundamentals_sector_concentration", "FATAL",
            f"BLOCKER: {b.family} is UNRESOLVED for {b.n_unresolved}/"
            f"{b.n_members} ({b.fraction:.0%}) of sector '{b.sector}' [{b.states_label}]"
            f" -- above the {SECTOR_BLOCKER_FRACTION:.0%} concentration "
            f"threshold. Either the concept does not exist in this sector "
            f"(ABSENT-only) or its taxonomy does not fit these filers; either "
            f"way it would bias a sector-stratified E2 result and must be "
            f"read, not averaged over. CIKs: "
            f"{', '.join(str(c) for c in b.ciks)}",
        )
        for b in blockers
    ]


def print_sector_blockers(blockers: list[SectorBlocker]) -> None:
    """Printed FIRST, before any per-company detail (F2_SPEC §5.3)."""
    print("\n" + "=" * 78)
    if not blockers:
        print("SECTOR CONCENTRATION: no BLOCKER -- no (sector, family) cell is "
              f"above {SECTOR_BLOCKER_FRACTION:.0%} UNRESOLVED.")
        print("=" * 78)
        return
    print(f"{len(blockers)} SECTOR-CONCENTRATION BLOCKER(S) "
          f"(> {SECTOR_BLOCKER_FRACTION:.0%} of a sector's members UNRESOLVED "
          f"for one family)")
    print("=" * 78)
    print(f"{'sector':<16} {'family':<22} {'unresolved':>12}  share  states")
    for b in blockers:
        print(f"{b.sector:<16} {b.family:<22} "
              f"{b.n_unresolved:>5}/{b.n_members:<6} {b.fraction:>6.0%}  "
              f"{b.states_label}")
    print("=" * 78)


def print_resolution_summary(resolutions: list[ConceptResolution]) -> None:
    """Per-family state counts -- the one-screen read of what resolved."""
    families = list(CONCEPT_FAMILIES)
    states = list(RESOLVED_STATES) + list(UNRESOLVED_STATES)
    print("\nConcept-family resolution (companies per state):")
    print(f"{'family':<22}" + "".join(f"{s:>11}" for s in states))
    for family in families:
        rows = [r for r in resolutions if r.family == family]
        counts = {s: sum(1 for r in rows if r.state == s) for s in states}
        print(f"{family:<22}" + "".join(f"{counts[s]:>11}" for s in states))


def concept_resolution_frame(resolutions: list[ConceptResolution]) -> pd.DataFrame:
    """The data/f2/concept_resolution.csv shape: F2_SPEC §5.3's seven columns
    plus `alternates` (A2, so a DOMINANT resolution records what it beat) and
    `unit` / `units_mixed` / `duration_mix` (A9, so a consumer can see the
    reporting currency and the fact frequency behind a resolution instead of
    assuming USD and quarterly).

    `tags` is what F5 builds the series from -- one tag for SINGLE/DOMINANT,
    the chronological sequence for MIGRATION. It is empty for ABSENT and is
    the tags-seen record for the other UNRESOLVED states, whose `severity`
    column already tells F5 to refuse. `alternates` is never a build input.
    """
    return pd.DataFrame(
        [
            {
                "cik": r.cik,
                "family": r.family,
                "state": r.state,
                "tags": "|".join(r.tags),
                "switch_quarter": r.switch_quarter,
                "coverage": round(r.coverage, 4),
                "severity": r.severity,
                "alternates": "|".join(r.alternates),
                "unit": r.unit,
                "units_mixed": int(r.units_mixed),
                "duration_mix": r.duration_mix,
            }
            for r in sorted(resolutions, key=lambda r: (r.cik, r.family))
        ],
        columns=["cik", "family", "state", "tags", "switch_quarter",
                 "coverage", "severity", "alternates",
                 "unit", "units_mixed", "duration_mix"],
    )


def write_concept_resolution(
    resolutions: list[ConceptResolution], path: Path = CONCEPT_RESOLUTION_CSV,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    concept_resolution_frame(resolutions).to_csv(path, index=False)
    return path


# ---------------------------------------------------------------------------
# Coverage-window helpers + the findings table (ingest_metadata.py's
# ValidationProblem / WARN / FATAL conventions, in a separate DB table)
# ---------------------------------------------------------------------------


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
    (run_date, stage) before inserting, so sharing that table between two
    independent validation passes run on the same day would silently erase
    whichever one wrote second. Same column shape as the metadata table
    (cik-keyed, nullable ticker) for convention consistency, just a separate
    table so the two passes' history can't stomp each other.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS fundamentals_validation_problems (
            run_date TEXT NOT NULL,
            cik INTEGER NOT NULL,
            ticker TEXT,                     -- nullable, informational only
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
        "(run_date, cik, ticker, check_name, severity, message) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (run_date.isoformat(), p.cik, p.ticker, p.check, p.severity, p.message)
            for p in problems
        ],
    )
    conn.commit()


def validate_fundamentals(
    df: pd.DataFrame,
    universe: pd.DataFrame,
    window_start: date = CORPUS_WINDOW_START,
    window_end: date = CORPUS_WINDOW_END,
    periodic_filing_dates: Optional[dict[int, list[str]]] = None,
) -> list[ValidationProblem]:
    """Every fundamentals finding for a run, in ingest_metadata.py's
    WARN/FATAL vocabulary: one FATAL per UNRESOLVED (cik, family), one WARN
    per non-USD resolved family, one WARN/INFO per member whose companyfacts
    tail lags its own filings, plus one FATAL per sector-concentration
    BLOCKER.

    E1's per-concept coverage bands (concept_structurally_absent /
    concept_tag_migrated_before_window / concept_unexplained_gap /
    concept_quarterly_coverage_*) and its revenue_concept_present /
    revenue_alias_consistency checks are all subsumed by the classifier:
    revenue is a family like any other, its absence is ABSENT and its
    multi-alias case is OVERLAP or MIGRATION, decided per company from the
    data instead of from a hand-maintained list of tickers.

    E2 window rule (F2_SPEC §3.4), unchanged from S2: the coverage
    denominator is the company's OWN reportable quarters between its
    `coverage_start` and `coverage_end`; `window_start`/`window_end` are only
    the fallback for universe frames that carry no coverage columns.
    """
    resolutions = classify_universe(df, universe, window_start, window_end)
    return (
        resolution_problems(resolutions)
        + tail_lag_problems(
            df, universe, periodic_filing_dates or {}, window_start, window_end
        )
        + blocker_problems(sector_blockers(resolutions, universe))
    )


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------


def run(
    force_refresh: bool = False,
    db_path: Path = DB_PATH,
    output_parquet: Path = OUTPUT_PARQUET,
    resolution_csv: Path = CONCEPT_RESOLUTION_CSV,
) -> None:
    db_path = Path(db_path)
    if db_path.resolve() == E1_DB_PATH.resolve():
        raise ValueError(
            f"Refusing to write {E1_DB_PATH} -- that is E1's frozen record "
            f"(F2_SPEC §1.4 / ruling 4). E2 writes {DB_PATH.name}."
        )
    output_parquet = Path(output_parquet)
    if output_parquet.resolve() == E1_OUTPUT_PARQUET.resolve():
        raise ValueError(
            f"Refusing to write {E1_OUTPUT_PARQUET} -- that is E1's frozen "
            f"Phase C artifact (F2_SPEC §10). E2 writes {OUTPUT_PARQUET.name}."
        )
    universe = load_universe()
    client = EdgarClient()

    print(f"Pulling companyfacts for {len(universe)} companies "
          f"({len(CONCEPTS)} tags across {len(CONCEPT_FAMILIES)} families each)...")
    df = build_fundamentals(client, universe, force_refresh=force_refresh)

    print(f"\nTotal EDGAR network GETs this run: {client.request_count}")
    print(f"Total fundamentals rows: {len(df)}")

    resolutions = classify_universe(df, universe)
    written = write_concept_resolution(resolutions, resolution_csv)
    blockers = sector_blockers(resolutions, universe)

    # The independent half of the tail-lag check (S7 B5) comes from S3's
    # filing metadata, read-only. If it is not there, say so loudly: a check
    # that silently did not run is worse than one that failed.
    periodic = load_periodic_filing_dates(db_path)
    lag = tail_lag_problems(df, universe, periodic)
    if not periodic:
        lag = [ValidationProblem(
            RUN_SCOPE_CIK, TAIL_LAG_CHECK, "WARN",
            f"NOT CHECKED: no readable `filings` table in {db_path}, so the "
            f"companyfacts tail-lag check did not run. Coverage and staleness "
            f"are both anchored on the fundamentals themselves, so a truncated "
            f"companyfacts pull is invisible without it. Run "
            f"ingest_metadata.py --stage metadata first.",
        )]
    problems = (
        resolution_problems(resolutions) + lag + blocker_problems(blockers)
    )

    # BLOCKERS FIRST -- F2_SPEC §5.3: concentrated missingness is reported at
    # the top of the run output, never buried in a per-company list. The
    # exemption ledger prints right under it so the table is never read
    # without knowing what was kept out of it.
    print_sector_blockers(blockers)
    print_blocker_exemptions(blocker_exemption_statuses(resolutions, universe))
    print_resolution_summary(resolutions)
    unresolved = [r for r in resolutions if r.severity == SEVERITY_UNRESOLVED]
    print(f"\n{len(unresolved)} UNRESOLVED (cik, family) pair(s) of "
          f"{len(resolutions)}; resolution written to {written}")
    non_usd = {r.cik for r in resolutions if r.severity == SEVERITY_RESOLVED
               and r.is_non_usd}
    print(f"Reporting currency: {len(non_usd)} member(s) with a resolved "
          f"non-USD family"
          + (f" (CIK {', '.join(str(c) for c in sorted(non_usd))}) -- F2 does "
             f"NOT convert; see the {NON_USD_CHECK} WARNs" if non_usd else ""))
    warn_lag = [p for p in lag if p.severity == "WARN"]
    print(f"companyfacts tail lag: {len(warn_lag)} member(s) >= "
          f"{TAIL_LAG_WARN_FILINGS} periodic filings behind (WARN), "
          f"{len(lag) - len(warn_lag)} exactly one behind (INFO, the ordinary "
          f"propagation lag)")
    print_validation_report(problems)

    fatal = [p for p in problems if p.severity == "FATAL"]
    if fatal:
        print(
            f"\n{len(fatal)} FATAL finding(s). Writing "
            f"{output_parquet} anyway (fundamentals sourcing is not gated the "
            f"way ingest_metadata.py's universe validation is -- these are "
            f"reported for the record and for F5 to consume via "
            f"{resolution_csv.name}, not a hard stop on an otherwise-"
            f"successful companyfacts pull). An UNRESOLVED (cik, family) pair "
            f"must NOT be used to build a series."
        )

    import sqlite3

    conn = sqlite3.connect(db_path)
    init_fundamentals_validation_table(conn)
    write_fundamentals_validation_problems(conn, problems, date.today())
    conn.close()

    output_parquet.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_parquet, index=False)
    print(f"\nWrote {len(df)} rows to {output_parquet}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force-refresh", action="store_true",
        help="Ignore companyfacts cache staleness and re-fetch from EDGAR for every company.",
    )
    parser.add_argument(
        "--db", default=str(DB_PATH),
        help=(
            f"SQLite database to write validation findings to (default: "
            f"{DB_PATH.name}, the E2 database). {E1_DB_PATH.name} is E1's frozen "
            f"record and is refused."
        ),
    )
    args = parser.parse_args()
    run(force_refresh=args.force_refresh, db_path=Path(args.db))
