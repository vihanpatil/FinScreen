"""test_ingest_fundamentals.py -- tests for ingest_fundamentals.py's own
logic: concept extraction from a raw companyfacts-shaped dict, the
reportable-quarter window calculation, and -- since F2 stage S4 -- the
six-state alias/migration classifier (F2_SPEC §5.3 as amended 2026-08-24),
the sector-concentration BLOCKER rule, and data/f2/concept_resolution.csv.

E1's per-concept coverage bands and its three hand-curated per-ticker maps
(BANK_TICKERS_MISSING_INDUSTRIAL_CONCEPTS, BANK_EXEMPT_CONCEPTS,
KNOWN_MIDWINDOW_MIGRATIONS) are gone. The tests that pinned them are
replaced by the ACCEPTANCE TESTS below, which run the classifier over
fixtures sliced from the cached companyfacts documents (built by
data/f2/fixtures/build_fixtures.py, real EDGAR values, never live) and pin
what the classifier does with every case those maps encoded.

No network -- pure function tests against fabricated data and on-disk
fixtures. Nothing here opens a socket.

Run with: python3 -m pytest test_ingest_fundamentals.py -v
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import ingest_fundamentals as ing
import ingest_metadata as im


# ---------------------------------------------------------------------
# extract_concept_facts()
# ---------------------------------------------------------------------


def test_extract_concept_facts_basic():
    companyfacts = {
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {"start": "2024-01-01", "end": "2024-03-31", "val": 100,
                             "accn": "A-1", "fy": 2024, "fp": "Q1", "form": "10-Q",
                             "filed": "2024-05-01"},
                        ]
                    }
                }
            }
        }
    }
    rows = ing.extract_concept_facts(companyfacts, "us-gaap", "NetIncomeLoss", "TEST", 12345)
    assert len(rows) == 1
    row = rows[0]
    assert row["ticker"] == "TEST"
    assert row["cik"] == 12345
    assert row["taxonomy"] == "us-gaap"
    assert row["concept"] == "NetIncomeLoss"
    assert row["unit"] == "USD"
    assert row["value"] == 100
    assert row["period_start"] == "2024-01-01"
    assert row["period_end"] == "2024-03-31"
    assert row["accession_number"] == "A-1"
    assert row["filed"] == "2024-05-01"


def test_extract_concept_facts_missing_concept_returns_empty():
    companyfacts = {"facts": {"us-gaap": {}}}
    rows = ing.extract_concept_facts(companyfacts, "us-gaap", "NetIncomeLoss", "TEST", 1)
    assert rows == []


def test_extract_concept_facts_missing_taxonomy_returns_empty():
    companyfacts = {"facts": {}}
    rows = ing.extract_concept_facts(companyfacts, "dei", "EntityCommonStockSharesOutstanding", "TEST", 1)
    assert rows == []


def test_extract_concept_facts_multiple_units_all_captured():
    companyfacts = {
        "facts": {
            "us-gaap": {
                "EarningsPerShareDiluted": {
                    "units": {
                        "USD/shares": [
                            {"end": "2024-03-31", "start": "2024-01-01", "val": 1.5,
                             "accn": "A-1", "fy": 2024, "fp": "Q1", "form": "10-Q",
                             "filed": "2024-05-01"},
                        ],
                        "USDPerShare": [  # hypothetical alternate unit key
                            {"end": "2024-06-30", "start": "2024-04-01", "val": 1.6,
                             "accn": "A-2", "fy": 2024, "fp": "Q2", "form": "10-Q",
                             "filed": "2024-08-01"},
                        ],
                    }
                }
            }
        }
    }
    rows = ing.extract_concept_facts(companyfacts, "us-gaap", "EarningsPerShareDiluted", "TEST", 1)
    assert len(rows) == 2
    assert {r["unit"] for r in rows} == {"USD/shares", "USDPerShare"}


# ---------------------------------------------------------------------
# target_quarters() -- must exclude a quarter that hasn't ended yet as of
# window_end (the bug this function's docstring says an earlier version had).
# ---------------------------------------------------------------------


def test_target_quarters_excludes_not_yet_ended_trailing_quarter():
    # Window ends mid-Q3 2026 (2026-08-07) -- Q3 2026 itself (ends 2026-09-30)
    # cannot possibly have been reported yet and must be excluded.
    qs = ing.target_quarters(date(2023, 8, 14), date(2026, 8, 7))
    assert (2026, 3) not in qs
    assert (2026, 2) in qs  # Q2 2026 ends 2026-06-30, safely before window_end
    assert (2023, 3) in qs  # Q3 2023 ends 2023-09-30 -- reportable well within window
    assert len(qs) == 12


def test_target_quarters_includes_quarter_ending_exactly_on_window_end():
    # A quarter ending exactly on window_end IS reportable (<=, not <).
    qs = ing.target_quarters(date(2024, 1, 1), date(2024, 3, 31))
    assert (2024, 1) in qs
    assert len(qs) == 1


# ---------------------------------------------------------------------
# CONCEPT_FAMILIES + the deleted E1 constants (F2_SPEC §5.2, §8.1 row 3)
# ---------------------------------------------------------------------


def test_concept_families_are_exactly_the_ruled_table():
    """F2_SPEC §5.2 as amended 2026-08-24 (amendment A1, "substitutes-only
    families + explicit dominance"), tag for tag, in preference order. A
    silent edit to the ingested concept set or to a preference order is a
    scope change -- preference is resolution semantics now -- and must break
    a test.
    """
    assert ing.CONCEPT_FAMILIES == {
        "revenue": [
            ("us-gaap", "Revenues"),
            ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
            ("us-gaap", "RevenueFromContractWithCustomerIncludingAssessedTax"),
            ("us-gaap", "RevenuesNetOfInterestExpense"),
            ("us-gaap", "InterestAndDividendIncomeOperating"),
        ],
        "net_income": [
            ("us-gaap", "NetIncomeLoss"),
            ("us-gaap", "ProfitLoss"),
        ],
        "net_income_to_common": [
            ("us-gaap", "NetIncomeLossAvailableToCommonStockholdersBasic"),
        ],
        "operating_income": [("us-gaap", "OperatingIncomeLoss")],
        "pretax_income": [
            ("us-gaap", "IncomeLossFromContinuingOperationsBeforeIncomeTaxes"
                        "MinorityInterestAndIncomeLossFromEquityMethodInvestments"),
            ("us-gaap", "IncomeLossFromContinuingOperationsBeforeIncomeTaxes"
                        "ExtraordinaryItemsNoncontrollingInterest"),
        ],
        "assets": [("us-gaap", "Assets")],
        "liabilities": [("us-gaap", "Liabilities")],
        "liabilities_and_equity": [
            ("us-gaap", "LiabilitiesAndStockholdersEquity"),
        ],
        "equity": [
            ("us-gaap", "StockholdersEquity"),
            ("us-gaap", "StockholdersEquityIncludingPortionAttributable"
                        "ToNoncontrollingInterest"),
            ("us-gaap", "PartnersCapital"),
            ("us-gaap", "PartnersCapitalIncludingPortionAttributable"
                        "ToNoncontrollingInterest"),
        ],
        "minority_interest": [("us-gaap", "MinorityInterest")],
        "cash": [
            ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
            ("us-gaap", "CashAndDueFromBanks"),
            ("us-gaap", "CashCashEquivalentsRestrictedCashAndRestrictedCash"
                        "Equivalents"),
            ("us-gaap", "CashCashEquivalentsRestrictedCashAndRestrictedCash"
                        "EquivalentsIncludingDisposalGroupAndDiscontinuedOperations"),
            ("us-gaap", "Cash"),
        ],
        "operating_cash_flow": [
            ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
            ("us-gaap", "NetCashProvidedByUsedInOperatingActivitiesContinuing"
                        "Operations"),
        ],
        "eps_diluted": [
            ("us-gaap", "EarningsPerShareDiluted"),
            ("us-gaap", "EarningsPerShareBasicAndDiluted"),
            ("us-gaap", "NetIncomeLossNetOfTaxPerOutstandingLimited"
                        "PartnershipUnitDiluted"),
        ],
        "shares_outstanding": [("dei", "EntityCommonStockSharesOutstanding")],
    }


def test_no_family_mixes_distinct_concepts():
    """Principle 1 of the ruling, as a standing guard: the four tags that are
    related-but-distinct each sit ALONE in their own family, so no resolution
    can ever silently substitute one for another.
    """
    for tag, family in [
        ("NetIncomeLossAvailableToCommonStockholdersBasic", "net_income_to_common"),
        ("LiabilitiesAndStockholdersEquity", "liabilities_and_equity"),
        ("MinorityInterest", "minority_interest"),
        ("IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinary"
         "ItemsNoncontrollingInterest", "pretax_income"),
    ]:
        assert ing.FAMILY_OF_TAG[tag] == family
    assert ing.CONCEPT_FAMILIES["operating_income"] == [
        ("us-gaap", "OperatingIncomeLoss")
    ]
    assert len(ing.CONCEPT_FAMILIES["liabilities"]) == 1


def test_the_four_documented_but_never_ingested_tags_are_now_in_families():
    """HANDOFF §2a trap (b): four tags were documented as migration targets
    and NOT ingested, which is what forced features.py to read raw
    companyfacts behind the validator's back. All four are family members now.
    """
    ingested = {tag for _, tag in ing.CONCEPTS}
    for tag in (
        "ProfitLoss",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        "CashAndDueFromBanks",
    ):
        assert tag in ingested


def test_concepts_is_the_deduplicated_union_of_the_families():
    flat = [pair for pairs in ing.CONCEPT_FAMILIES.values() for pair in pairs]
    assert ing.CONCEPTS == list(dict.fromkeys(flat))
    # 30 tags across 14 families, vs E1's flat 13. §5.2's own table held 25;
    # A1 regrouped them and added a measured pre-tax alias, A2 the
    # lowest-preference `Cash` fallback, A5.2 three partnership tags.
    assert len(ing.CONCEPTS) == len(set(ing.CONCEPTS)) == 30
    assert len(ing.CONCEPT_FAMILIES) == 14
    assert ("dei", "EntityCommonStockSharesOutstanding") in ing.CONCEPTS


def test_every_tag_belongs_to_exactly_one_family():
    assert set(ing.FAMILY_OF_TAG) == {tag for _, tag in ing.CONCEPTS}
    assert len(ing.FAMILY_OF_TAG) == len(ing.CONCEPTS)


def test_e1_flat_concept_list_and_hand_curated_maps_are_deleted():
    """F2_SPEC §5.2 / ruling 6: the three per-ticker maps and the flat-list
    split are deleted from code, not merely unused. They are preserved
    verbatim in data/f2/status/S4_fundamentals.md.
    """
    for name in (
        "BANK_TICKERS_MISSING_INDUSTRIAL_CONCEPTS",
        "BANK_EXEMPT_CONCEPTS",
        "KNOWN_MIDWINDOW_MIGRATIONS",
        "REVENUE_CONCEPTS",
        "CORE_NON_REVENUE_CONCEPTS",
        "MIN_QUARTERLY_COVERAGE_CLEAN",
        "MIN_QUARTERLY_COVERAGE_WARN",
    ):
        assert not hasattr(ing, name), f"{name} should have been deleted by S4"


def test_classification_does_not_depend_on_the_display_label():
    """No ticker may steer the classifier. The same facts under two different
    display labels must classify identically -- this is what replaced
    `if ticker in BANK_TICKERS_...`.
    """
    facts = _quarterly("CashAndDueFromBanks", _QUARTERS)
    a = ing.classify_universe(_frame(facts), _universe(1, ticker="JPM"))
    b = ing.classify_universe(_frame(facts), _universe(1, ticker="ZZZZ"))
    assert [(r.family, r.state, r.tags) for r in a] == [
        (r.family, r.state, r.tags) for r in b
    ]


# ---------------------------------------------------------------------
# Synthetic-company classifier states (F2_SPEC §5.3)
# ---------------------------------------------------------------------

# 12 reportable quarters, 2020Q1..2022Q4. 75% of 12 = 9 quarters; the PARTIAL
# floor (40%) is 4.8, i.e. 5 quarters.
WINDOW_START = date(2020, 1, 1)
WINDOW_END = date(2022, 12, 31)
_QUARTERS = [
    "2020-03-31", "2020-06-30", "2020-09-30", "2020-12-31",
    "2021-03-31", "2021-06-30", "2021-09-30", "2021-12-31",
    "2022-03-31", "2022-06-30", "2022-09-30", "2022-12-31",
]


def _fact(cik, concept, period_end, filed=None, form="10-Q", taxonomy="us-gaap",
          value=1.0, unit="USD", accession_number="A-1"):
    return dict(
        ticker=str(cik), cik=cik, taxonomy=taxonomy, concept=concept, unit=unit,
        value=value, fy=2021, fp="Q1", period_start=None, period_end=period_end,
        # `filed` defaults to the period end so every synthetic row is inside
        # the window under test (the classifier filters on `filed`, and a
        # real filing lands weeks later, which would push Q4 rows out).
        form=form, accession_number=accession_number, filed=filed or period_end,
    )


def _quarterly(concept, period_ends, cik=1, form="10-Q"):
    return [_fact(cik, concept, pe, form=form) for pe in period_ends]


def _anchor(cik=1):
    """Rows that make the company's FILED SPAN the whole 12-quarter window.

    Since amendment A5.1 the coverage denominator is the company's own filed
    span, not its window, so a test about a coverage BAND has to say what the
    span is -- otherwise a tag covering 6 of 12 quarters is 6/6 = 100% and
    the test is measuring nothing. `Revenues` is used as the anchor because
    it is in a family none of these tests assert on.
    """
    return _quarterly("Revenues", _QUARTERS, cik=cik)


def _frame(rows):
    return pd.DataFrame(rows)


def _universe(*ciks, sector="test", ticker=None, start=WINDOW_START, end=WINDOW_END):
    return pd.DataFrame({
        "cik": list(ciks),
        "ticker": [ticker or str(c) for c in ciks],
        "sector": [sector] * len(ciks),
        "coverage_start": [start] * len(ciks),
        "coverage_end": [end] * len(ciks),
    })


def _resolution_for(rows, family, universe=None):
    universe = _universe(1) if universe is None else universe
    resolutions = ing.classify_universe(_frame(rows), universe)
    matches = [r for r in resolutions if r.family == family]
    assert len(matches) == 1
    return matches[0]


def test_state_single_one_tag_over_the_bar():
    rows = _anchor() + _quarterly("Assets", _QUARTERS[:10]) + _quarterly(
        "LiabilitiesAndStockholdersEquity", _QUARTERS[:2]
    )
    r = _resolution_for(rows, "assets")
    assert (r.state, r.severity) == (ing.STATE_SINGLE, ing.SEVERITY_RESOLVED)
    assert r.tags == ("Assets",)
    assert r.resolved_tags == ["Assets"]
    assert r.coverage == pytest.approx(10 / 12)


def test_state_migration_disjoint_tags_records_the_switch_quarter():
    rows = (
        _quarterly("CashAndCashEquivalentsAtCarryingValue", _QUARTERS[:6])
        + _quarterly("CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
                     _QUARTERS[6:])
    )
    r = _resolution_for(rows, "cash")
    assert (r.state, r.severity) == (ing.STATE_MIGRATION, ing.SEVERITY_RESOLVED)
    assert r.tags == (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    )
    assert r.switch_quarter == "2021Q3"
    assert r.coverage == pytest.approx(1.0)


def test_migration_tolerates_exactly_one_overlapping_quarter():
    """One shared quarter is the normal shape of a clean switch. The recorded
    switch is where the successor TAKES OVER -- the first quarter it covers
    after its predecessor's last -- so the shared quarter (2021Q3, reported
    under both tags) belongs to the predecessor and the hand-off is 2021Q4.
    """
    rows = (
        _quarterly("CashAndCashEquivalentsAtCarryingValue", _QUARTERS[:7])
        + _quarterly("CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
                     _QUARTERS[6:])
    )
    r = _resolution_for(rows, "cash")
    assert r.state == ing.STATE_MIGRATION
    assert r.switch_quarter == "2021Q4"


def test_a_dead_predecessor_leaving_one_live_tag_is_still_a_migration():
    """Amendment A1 widened MIGRATION past the strict <=1-quarter disjoint
    switch: a filer that co-reported two tags for years and then dropped one
    still leaves an unambiguous chronological series, because within a
    substitutes-only family the two tags are the same series.
    """
    rows = (
        _quarterly("CashAndCashEquivalentsAtCarryingValue", _QUARTERS[:8])
        + _quarterly("CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
                     _QUARTERS[6:])
    )
    r = _resolution_for(rows, "cash")
    assert (r.state, r.severity) == (ing.STATE_MIGRATION, ing.SEVERITY_RESOLVED)
    assert r.tags == (
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    )
    assert r.stale_tags == ("CashAndCashEquivalentsAtCarryingValue",)


def test_state_dominant_prefers_the_higher_preference_co_reported_tag():
    """The heart of the ruling: two tags of one family covering the same
    quarters is a filer naming one series twice, and preference order -- not
    a hand-written per-ticker map, and not row counts -- decides it.
    """
    rows = (
        _quarterly("NetIncomeLoss", _QUARTERS)
        + _quarterly("ProfitLoss", _QUARTERS[:10])
    )
    r = _resolution_for(rows, "net_income")
    assert (r.state, r.severity) == (ing.STATE_DOMINANT, ing.SEVERITY_RESOLVED)
    assert r.tags == ("NetIncomeLoss",)
    assert r.alternates == ("ProfitLoss",)
    assert r.resolved_tags == ["NetIncomeLoss"]


def test_dominance_follows_preference_order_not_coverage():
    """The lower-preference tag covering MORE quarters does not win."""
    rows = (
        _quarterly("NetIncomeLoss", _QUARTERS[:10])
        + _quarterly("ProfitLoss", _QUARTERS)
    )
    r = _resolution_for(rows, "net_income")
    assert (r.state, r.tags, r.alternates) == (
        ing.STATE_DOMINANT, ("NetIncomeLoss",), ("ProfitLoss",),
    )


def test_state_overlap_needs_two_current_tags_and_no_dominant_one():
    """OVERLAP now means genuine ambiguity only: several tags share quarters,
    all are current, and none clears the coverage bar.
    """
    # Both tags run to the last quarter (so neither is stale) and both sit at
    # 8/12 = 67%, below the bar, sharing four quarters.
    rows = (
        _quarterly("NetIncomeLoss", _QUARTERS[:7] + _QUARTERS[11:])
        + _quarterly("ProfitLoss", _QUARTERS[4:])
    )
    r = _resolution_for(rows, "net_income")
    assert (r.state, r.severity) == (ing.STATE_OVERLAP, ing.SEVERITY_UNRESOLVED)
    assert r.resolved_tags == []
    assert set(r.tags) == {"NetIncomeLoss", "ProfitLoss"}


def test_state_partial_union_below_the_bar():
    rows = _anchor() + _quarterly("NetIncomeLoss", _QUARTERS[:6])   # 50%
    r = _resolution_for(rows, "net_income")
    assert (r.state, r.severity) == (ing.STATE_PARTIAL, ing.SEVERITY_UNRESOLVED)
    assert r.coverage == pytest.approx(0.5)
    assert r.resolved_tags == []


def test_two_disjoint_tags_whose_union_misses_the_bar_are_partial_not_migration():
    rows = _anchor() + (
        _quarterly("NetIncomeLoss", _QUARTERS[:4])
        + _quarterly("ProfitLoss", _QUARTERS[4:8])
    )
    r = _resolution_for(rows, "net_income")
    assert r.state == ing.STATE_PARTIAL
    assert r.coverage == pytest.approx(8 / 12)


def test_coverage_below_the_forty_percent_floor_is_still_partial():
    """F2_SPEC §5.3 names PARTIAL as [40%, 75%) and leaves (0%, 40%) unnamed.
    A family with two stray quarters has rows (so it is not ABSENT) and
    cannot be resolved, so it is reported as PARTIAL with its real coverage
    number. Both bands are UNRESOLVED -- severity does not depend on this.
    """
    r = _resolution_for(_anchor() + _quarterly("NetIncomeLoss", _QUARTERS[:2]),
                        "net_income")
    assert (r.state, r.severity) == (ing.STATE_PARTIAL, ing.SEVERITY_UNRESOLVED)
    assert r.coverage == pytest.approx(2 / 12)
    # ...and the FATAL row says so, rather than leaving a reader to wonder
    # why a 17%-covered family is called PARTIAL.
    message = ing.resolution_problems([r])[0].message
    assert "below the 40% floor" in message
    assert "rather than ABSENT" in message


def test_a_tag_that_clears_the_bar_but_has_died_does_not_resolve():
    """The staleness rule (amendment A1). `Assets` covers 9/12 = 75% -- it
    clears the bar -- but stops five quarters before the company's own last
    reported quarter. Resolving to it would hand F5 a series that silently
    freezes, which is exactly how E1 froze JNJ's operating income at 2015.
    """
    rows = (
        _quarterly("Assets", _QUARTERS[:9])
        + _quarterly("Revenues", _QUARTERS)      # anchors "last data quarter"
    )
    r = _resolution_for(rows, "assets")
    assert (r.state, r.severity) == (ing.STATE_PARTIAL, ing.SEVERITY_UNRESOLVED)
    assert r.stale_tags == ("Assets",)
    assert r.coverage == pytest.approx(0.75)
    assert r.resolved_tags == []
    message = ing.resolution_problems([r])[0].message
    assert "STALE" in message and "2022Q4" in message


def test_a_two_quarter_tail_gap_is_not_stale():
    """The threshold's live side: MEASURED, 366 of 371 at-bar tag instances
    on the 25 cached companies have a zero-quarter tail gap and the largest
    normal gap is one quarter, so two quarters must still resolve.
    """
    rows = (
        _quarterly("Assets", _QUARTERS[:10])     # last covered = 2022Q2
        + _quarterly("Revenues", _QUARTERS)      # company last data = 2022Q4
    )
    r = _resolution_for(rows, "assets")
    assert (r.state, r.severity) == (ing.STATE_SINGLE, ing.SEVERITY_RESOLVED)
    assert r.stale_tags == ()


def test_dominance_skips_a_stale_higher_preference_tag():
    """Preference decides between LIVE tags. A dead higher-preference tag is
    recorded as an alternate, never resolved to.
    """
    rows = (
        _quarterly("NetIncomeLoss", _QUARTERS[:9])   # at the bar, but died
        + _quarterly("ProfitLoss", _QUARTERS)
    )
    r = _resolution_for(rows, "net_income")
    assert (r.state, r.severity) == (ing.STATE_DOMINANT, ing.SEVERITY_RESOLVED)
    assert r.tags == ("ProfitLoss",)
    assert r.alternates == ("NetIncomeLoss",)
    assert r.stale_tags == ("NetIncomeLoss",)


def test_a_family_whose_every_tag_died_is_partial_not_migration():
    # Union 9/12 = 75% clears the bar, and the newer of the two tags still
    # stops three quarters before the company's last reported quarter.
    rows = (
        _quarterly("CashAndCashEquivalentsAtCarryingValue", _QUARTERS[:4])
        + _quarterly("CashAndDueFromBanks", _QUARTERS[4:9])
        + _quarterly("Revenues", _QUARTERS)
    )
    r = _resolution_for(rows, "cash")
    assert (r.state, r.severity) == (ing.STATE_PARTIAL, ing.SEVERITY_UNRESOLVED)
    assert set(r.stale_tags) == {
        "CashAndCashEquivalentsAtCarryingValue", "CashAndDueFromBanks",
    }


def test_a_short_life_member_is_scored_on_its_own_filed_span():
    """Amendment A5.1, the AZEK case: a member that IPO'd into the window and
    was acquired out of it is fully covered for its actual life. Charging it
    for quarters before it existed and after it died measures its corporate
    history, not its data quality -- AZEK (CIK 1782754) scored 11/16 = 69%
    PARTIAL on ALL 14 families under the window denominator.
    """
    life = _QUARTERS[3:9]                     # six quarters of a 12-quarter window
    rows: list[dict] = []
    for family, pairs in ing.CONCEPT_FAMILIES.items():
        rows += _quarterly(pairs[0][1], life)
    resolutions = ing.classify_universe(_frame(rows), _universe(1))
    assert {r.n_target for r in resolutions} == {6}
    assert all(r.state == ing.STATE_SINGLE for r in resolutions), [
        (r.family, r.state) for r in resolutions if r.state != ing.STATE_SINGLE
    ]
    assert all(r.coverage == pytest.approx(1.0) for r in resolutions)
    # Nothing is stale either: the company simply stopped existing, which is
    # measured against ITS last quarter, not the calendar.
    assert all(r.stale_tags == () for r in resolutions)


def test_a_genuinely_gappy_member_still_fails_after_the_denominator_fix():
    """The inverse, and the reason the span is trimmed only at the ends: a
    hole in the MIDDLE of a company's own filed span still counts against it.
    """
    rows = _anchor() + _quarterly("Assets", _QUARTERS[:2] + _QUARTERS[10:])
    r = _resolution_for(rows, "assets")
    assert r.n_target == 12
    assert (r.state, r.severity) == (ing.STATE_PARTIAL, ing.SEVERITY_UNRESOLVED)
    assert r.coverage == pytest.approx(4 / 12)


def test_the_span_is_the_company_s_not_the_family_s():
    """The denominator is the company's filed span across ALL families -- if
    it were per family, every family would be 100% by construction and the
    coverage bar would mean nothing.
    """
    rows = _anchor() + _quarterly("Assets", _QUARTERS[:3])
    r = _resolution_for(rows, "assets")
    assert r.n_target == 12 and r.state == ing.STATE_PARTIAL


def test_state_absent_when_no_tag_has_an_in_window_row():
    r = _resolution_for(_quarterly("Assets", _QUARTERS), "net_income")
    assert (r.state, r.severity) == (ing.STATE_ABSENT, ing.SEVERITY_UNRESOLVED)
    assert r.tags == ()
    assert r.resolved_tags == []
    assert r.coverage == 0.0


def test_rows_filed_outside_the_company_window_do_not_count():
    rows = _quarterly("Assets", _QUARTERS, form="10-K")
    rows += [_fact(1, "Assets", "2019-12-31", filed="2019-12-31")]
    # A company whose own window is only 2022 sees 4 quarters, none of them
    # covered by rows filed in 2020-2021.
    universe = _universe(1, start=date(2022, 1, 1), end=date(2022, 12, 31))
    r = _resolution_for(rows, "assets", universe)
    assert r.n_target == 4
    assert r.state == ing.STATE_SINGLE and r.coverage == pytest.approx(1.0)
    # Scored over 2019 instead, only the 2019-filed row is visible at all:
    # the 2020-2022 rows are outside the window, so they set neither the
    # coverage nor the span (which is why n_target is 1, not 4).
    tight = _universe(1, start=date(2019, 1, 1), end=date(2019, 12, 31))
    r2 = _resolution_for(rows, "assets", tight)
    assert r2.n_target == 1
    assert dict(r2.tag_coverage)["Assets"] == 1
    assert r2.last_data_quarter == "2019Q4"


def test_a_company_with_no_facts_at_all_gets_absent_rows_not_silence():
    """A member that disappears from the resolution table is worse than one
    that fails: the failure has to be counted and named.
    """
    for empty in (pd.DataFrame(), _frame(_quarterly("Assets", []))):
        resolutions = ing.classify_universe(empty, _universe(1))
        assert len(resolutions) == len(ing.CONCEPT_FAMILIES)
        assert all(r.state == ing.STATE_ABSENT for r in resolutions)
        assert all(r.severity == ing.SEVERITY_UNRESOLVED for r in resolutions)


def test_universe_row_without_coverage_columns_falls_back_to_the_window_args():
    """E1-shaped frames (no per-company window) still work -- S2's §3.4
    fallback, unchanged by S4.
    """
    universe = pd.DataFrame({"cik": [1], "ticker": ["TICK"], "sector": ["tech"]})
    resolutions = ing.classify_universe(
        _frame(_quarterly("Assets", _QUARTERS)), universe,
        window_start=WINDOW_START, window_end=WINDOW_END,
    )
    assets = [r for r in resolutions if r.family == "assets"][0]
    assert (assets.n_target, assets.state) == (12, ing.STATE_SINGLE)
    assert assets.ticker == "TICK"


def test_every_family_gets_a_row_for_every_member():
    resolutions = ing.classify_universe(_frame(_quarterly("Assets", _QUARTERS)),
                                        _universe(1, 2))
    assert len(resolutions) == 2 * len(ing.CONCEPT_FAMILIES)
    assert {r.cik for r in resolutions} == {1, 2}


# ---------------------------------------------------------------------
# Operating-form filter -- HANDOFF §2a trap (c)
# ---------------------------------------------------------------------


@pytest.mark.parametrize("form,expected", [
    ("10-K", True), ("10-Q", True), ("8-K", True),
    ("10-K/A", True), ("10-Q/A", True), ("8-K/A", True), ("10-k", True),
    ("DEF 14A", False), ("20-F", False), ("S-1", False), ("11-K", False),
    ("40-F", False), ("6-K", False), (None, False), ("", False),
])
def test_is_operating_form(form, expected):
    assert ing.is_operating_form(form) is expected


def test_def_14a_rows_never_count_as_coverage():
    """A company whose only in-window rows for a tag are DEF 14A proxy
    compensation tables has ZERO coverage for it -- the exact shape of the MA
    NetIncomeLoss trap E1 had to describe by hand.
    """
    rows = _quarterly("NetIncomeLoss", _QUARTERS, form="DEF 14A")
    r = _resolution_for(rows, "net_income")
    assert r.state == ing.STATE_ABSENT
    assert r.tag_coverage == ()
    # The same rows on an operating form DO count -- proving the form filter
    # is what excluded them, not a missing tag or a bad window.
    rows_10k = _quarterly("NetIncomeLoss", _QUARTERS, form="10-K")
    assert _resolution_for(rows_10k, "net_income").state == ing.STATE_SINGLE


# ---------------------------------------------------------------------
# ACCEPTANCE TESTS -- the deleted hand-maps, reproduced from cached
# companyfacts slices (F2_SPEC §8.2). Offline: data/f2/fixtures/*.json.
# ---------------------------------------------------------------------

FIXTURE_DIR = Path(__file__).resolve().parent / "data" / "f2" / "fixtures"

# Display labels for the acceptance cases. They exist ONLY in this test file,
# to name the E1 hand-map entries being reproduced -- no ticker steers any
# code path in ingest_fundamentals.py any more.
CASE_CIKS = {"JPM": 19617, "BAC": 70858, "GS": 886982, "MA": 1141391,
             "OXY": 797468, "SLB": 87347, "CVX": 93410, "GOOGL": 1652044,
             "EPD": 1061219, "ENB": 895728}


def _load_fixture_rows(cik: int) -> list[dict]:
    doc = json.loads((FIXTURE_DIR / f"companyfacts_CIK{cik:010d}.json").read_text())
    rows: list[dict] = []
    for taxonomy, tag in ing.CONCEPTS:
        rows.extend(ing.extract_concept_facts(doc, taxonomy, tag, str(cik), cik))
    return rows


@pytest.fixture(scope="module")
def real_universe():
    """The real hybrid136 rows for the acceptance CIKs, checksum-verified."""
    universe = im.load_universe()
    return universe[universe["cik"].isin(CASE_CIKS.values())].reset_index(drop=True)


@pytest.fixture(scope="module")
def acceptance(real_universe):
    """{ (label, family): ConceptResolution } over the real per-company
    coverage windows, from the fixture slices.
    """
    rows: list[dict] = []
    for cik in CASE_CIKS.values():
        rows.extend(_load_fixture_rows(cik))
    resolutions = ing.classify_universe(pd.DataFrame(rows), real_universe)
    label_of = {cik: label for label, cik in CASE_CIKS.items()}
    return {(label_of[r.cik], r.family): r for r in resolutions}


def test_acceptance_universe_windows_are_the_full_corpus_window(real_universe):
    """Pins what the acceptance numbers below are measured against: all seven
    are current members, so each window is 2015-07-01..2026-08-31 = 44
    reportable quarters.
    """
    assert len(real_universe) == len(CASE_CIKS) == 10
    assert set(real_universe["coverage_end"]) == {im.CORPUS_WINDOW_END}
    # Most run the full window; Alphabet and Enbridge joined later, so their
    # own windows are shorter and their coverage denominators differ. That is
    # the per-company scoping working, not an inconsistency.
    assert len(ing.target_quarters(im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END)) == 44
    windows = dict(zip(real_universe["cik"], real_universe["coverage_start"]))
    assert {c for c, w in windows.items() if w == im.CORPUS_WINDOW_START} == {
        v for k, v in CASE_CIKS.items() if k not in ("GOOGL", "ENB")
    }


@pytest.mark.parametrize("label", ["JPM", "BAC"])
def test_acceptance_bank_cash_resolves_to_cashandduefrombanks(label, acceptance):
    """E1 hand-map: BANK_TICKERS_MISSING_INDUSTRIAL_CONCEPTS x
    BANK_EXEMPT_CONCEPTS downgraded these banks' missing
    CashAndCashEquivalentsAtCarryingValue to WARN, by name, and never
    ingested the tag they actually use.

    The classifier finds CashAndDueFromBanks at 44/44 with no ticker named
    anywhere, and DOMINANT resolves to it: the standard cash tag is preferred
    but does not clear the bar for these two, so the bank line wins on its
    own coverage. The co-reported ASU-2016-18 total is recorded, not used.
    """
    r = acceptance[(label, "cash")]
    assert (r.state, r.severity) == (ing.STATE_DOMINANT, ing.SEVERITY_RESOLVED)
    assert r.resolved_tags == ["CashAndDueFromBanks"]
    assert dict(r.tag_coverage)["CashAndDueFromBanks"] == 44
    assert "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents" in r.alternates


def test_acceptance_gs_cash_resolves_to_the_standard_tag_it_actually_reports(acceptance):
    """Same hand-map entry, opposite outcome, deliberately: GS reports the
    STANDARD cash tag at 44/44 as well as CashAndDueFromBanks, so preference
    order resolves it to the tag that is comparable across the whole
    universe. E1's map would have sent it to the bank tag on the strength of
    its ticker being in a set. Documented in the S4 report.
    """
    r = acceptance[("GS", "cash")]
    assert (r.state, r.severity) == (ing.STATE_DOMINANT, ing.SEVERITY_RESOLVED)
    assert r.resolved_tags == ["CashAndCashEquivalentsAtCarryingValue"]
    assert "CashAndDueFromBanks" in r.alternates
    assert dict(r.tag_coverage)["CashAndDueFromBanks"] == 44


@pytest.mark.parametrize("label", ["JPM", "BAC", "GS"])
def test_acceptance_bank_operating_income_stays_absent_and_is_reported(label, acceptance):
    """The other half of the same E1 hand-map. Banks have no GAAP operating
    income line, so `operating_income` is ABSENT -- expected, reported, and
    NOT backfilled from pre-tax income, which the 2026-08-24 ruling moved
    into its own family precisely so it could not stand in silently. The
    pre-tax series itself resolves cleanly for all three.
    """
    op = acceptance[(label, "operating_income")]
    assert (op.state, op.severity) == (ing.STATE_ABSENT, ing.SEVERITY_UNRESOLVED)
    assert op.resolved_tags == []
    pretax = acceptance[(label, "pretax_income")]
    assert pretax.severity == ing.SEVERITY_RESOLVED
    assert dict(pretax.tag_coverage)[pretax.tags[-1]] >= 40


def test_acceptance_ma_net_income_resolves_to_profitloss(acceptance):
    """E1 hand-map KNOWN_MIDWINDOW_MIGRATIONS[("MA","NetIncomeLoss")] --
    including its note that MA's only in-window NetIncomeLoss rows are DEF
    14A proxy tables. Both halves reproduce mechanically: ProfitLoss is now
    ingested and covers 44/44, and NetIncomeLoss contributes ZERO covered
    quarters because its in-window rows are all DEF 14A.
    """
    r = acceptance[("MA", "net_income")]
    assert (r.state, r.severity) == (ing.STATE_SINGLE, ing.SEVERITY_RESOLVED)
    assert r.resolved_tags == ["ProfitLoss"]
    assert "NetIncomeLoss" not in dict(r.tag_coverage)


def test_acceptance_ma_net_income_def_14a_rows_are_the_only_ones_in_window():
    """The trap (c) case, shown rather than asserted second-hand: MA's
    in-window NetIncomeLoss rows exist and are exclusively DEF 14A. Relabel
    them as 10-K and the tag reappears in the coverage table -- so the form
    filter, not an empty tag, is what excludes them.
    """
    rows = pd.DataFrame(_load_fixture_rows(CASE_CIKS["MA"]))
    in_window = rows[
        (rows["concept"] == "NetIncomeLoss")
        & (rows["filed"] >= im.CORPUS_WINDOW_START.isoformat())
        & (rows["filed"] <= im.CORPUS_WINDOW_END.isoformat())
    ]
    assert len(in_window) > 0
    assert set(in_window["form"]) == {"DEF 14A"}

    universe = _universe(CASE_CIKS["MA"], start=im.CORPUS_WINDOW_START,
                         end=im.CORPUS_WINDOW_END)
    relabelled = rows.copy()
    relabelled.loc[relabelled["form"] == "DEF 14A", "form"] = "10-K"
    r = _resolution_for(relabelled.to_dict("records"), "net_income", universe)
    assert "NetIncomeLoss" in dict(r.tag_coverage)


def test_acceptance_oxy_net_income_resolves_to_profitloss(acceptance):
    """E1 hand-map KNOWN_MIDWINDOW_MIGRATIONS[("OXY","NetIncomeLoss")]:
    "ProfitLoss". Reproduced mechanically and for the right reason:
    NetIncomeLoss clears the coverage bar (33/44 = 75%) and is the preferred
    tag, but it DIED in 2024, so dominance skips it and resolves to the live
    ProfitLoss -- the same answer E1 wrote by hand, from the data.
    """
    r = acceptance[("OXY", "net_income")]
    coverage = dict(r.tag_coverage)
    assert coverage["ProfitLoss"] == 41
    assert coverage["NetIncomeLoss"] == 33
    assert (r.state, r.severity) == (ing.STATE_DOMINANT, ing.SEVERITY_RESOLVED)
    assert r.resolved_tags == ["ProfitLoss"]
    assert r.alternates == ("NetIncomeLoss",)
    assert r.stale_tags == ("NetIncomeLoss",)


def test_acceptance_slb_operating_income_is_loud_partial_superseding_e1(acceptance):
    """E1 hand-map KNOWN_MIDWINDOW_MIGRATIONS[("SLB","OperatingIncomeLoss")]
    claimed a migration to ProfitLoss. It is NOT one: ProfitLoss is a
    net-income tag, and what actually happened is that SLB stopped reporting
    a GAAP operating-income line in 2024. The 2026-08-24 ruling makes this
    the deliberate outcome -- OperatingIncomeLoss clears the bar on 11-year
    coverage (35/44 = 80%) and is nonetheless STALE by 9 quarters, so the
    family goes loud-PARTIAL instead of resolving to a dead tag. This test
    supersedes F2_SPEC §8.2's prediction for SLB.
    """
    r = acceptance[("SLB", "operating_income")]
    assert dict(r.tag_coverage)["OperatingIncomeLoss"] == 35
    assert r.coverage == pytest.approx(35 / 44)
    assert (r.state, r.severity) == (ing.STATE_PARTIAL, ing.SEVERITY_UNRESOLVED)
    assert r.stale_tags == ("OperatingIncomeLoss",)
    assert r.resolved_tags == []
    message = ing.resolution_problems([r])[0].message
    assert "STALE" in message and "last 2024Q1" in message


def test_acceptance_googl_revenue_is_a_handoff_migration(acceptance):
    """Not an E1 hand-map case -- the shape amendment A1 added MIGRATION
    coverage for. Alphabet co-reported two revenue tags for years, then
    dropped the higher-coverage one in 2025Q1; the survivor covers 70%, below
    the bar on its own. Neither a dominance nor a strict disjoint-switch
    rule resolves this, and refusing it would cost a core-stratum mega-cap
    its revenue series.
    """
    r = acceptance[("GOOGL", "revenue")]
    assert (r.state, r.severity) == (ing.STATE_MIGRATION, ing.SEVERITY_RESOLVED)
    assert r.tags[-1] == "Revenues"
    assert "RevenueFromContractWithCustomerExcludingAssessedTax" in r.tags
    assert r.stale_tags == ("RevenueFromContractWithCustomerExcludingAssessedTax",)
    assert r.coverage == pytest.approx(1.0)
    assert r.switch_quarter


def test_acceptance_slb_cash_resolves_via_the_lowest_preference_cash_tag(acceptance):
    """Amendment A2 (ruled 2026-08-24): SLB tags its balance-sheet cash under
    plain `Cash` -- a different us-gaap element (cash EXCLUDING equivalents),
    admitted to the family at LOWEST preference because for a filer that
    never tags a broader cash line it is that filer's cash representation.
    Here it covers 44/44 while the family's proper tags reach 52%, so the
    company gets a provenance-tracked series instead of a manufactured gap.
    """
    r = acceptance[("SLB", "cash")]
    assert (r.state, r.severity) == (ing.STATE_SINGLE, ing.SEVERITY_RESOLVED)
    assert r.resolved_tags == ["Cash"]
    assert dict(r.tag_coverage)["Cash"] == 44
    assert ing.CONCEPT_FAMILIES["cash"][-1] == ("us-gaap", "Cash")


def test_plain_cash_never_displaces_a_proper_cash_tag():
    """The guarantee that makes A2 safe: `Cash` sits last, so dominance can
    only reach it when nothing better clears the bar. A filer reporting both
    resolves to the proper tag, with `Cash` recorded as an alternate.
    """
    both = (
        _quarterly("CashAndCashEquivalentsAtCarryingValue", _QUARTERS)
        + _quarterly("Cash", _QUARTERS)
    )
    r = _resolution_for(both, "cash")
    assert (r.state, r.tags, r.alternates) == (
        ing.STATE_DOMINANT, ("CashAndCashEquivalentsAtCarryingValue",), ("Cash",),
    )
    # Same for the bank line and both restricted-cash tags.
    for better in ("CashAndDueFromBanks",
                   "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"):
        r = _resolution_for(
            _quarterly(better, _QUARTERS) + _quarterly("Cash", _QUARTERS), "cash"
        )
        assert r.tags == (better,) and r.alternates == ("Cash",)
    # Only when nothing else clears the bar does `Cash` win.
    alone = _resolution_for(_quarterly("Cash", _QUARTERS), "cash")
    assert (alone.state, alone.tags) == (ing.STATE_SINGLE, ("Cash",))


def test_acceptance_cvx_cash_resolves_to_the_restricted_cash_tag(acceptance):
    """E1 hand-map KNOWN_MIDWINDOW_MIGRATIONS[("CVX",
    "CashAndCashEquivalentsAtCarryingValue")]: the post-ASU-2016-18 combined
    restricted-cash tag. The classifier resolves CVX's cash to exactly that
    tag, from the data, with no ticker named.
    """
    r = acceptance[("CVX", "cash")]
    assert (r.state, r.severity) == (ing.STATE_SINGLE, ing.SEVERITY_RESOLVED)
    assert r.resolved_tags == [
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
    ]
    assert dict(r.tag_coverage)["CashAndCashEquivalentsAtCarryingValue"] == 31


def test_acceptance_partnership_equity_resolves_to_partners_capital(acceptance):
    """Amendment A5.2, the MLP case. A partnership's book equity IS its total
    partners' capital; the two partnership tags mirror the corporate pair
    (parent-share, then NCI-inclusive) and sit after it, so dominance picks
    the parent-share total. Before A5.2 this was ABSENT for every MLP in the
    universe, which drove four of the 244-scale energy blockers.
    """
    r = acceptance[("EPD", "equity")]
    assert (r.state, r.severity) == (ing.STATE_DOMINANT, ing.SEVERITY_RESOLVED)
    assert r.resolved_tags == ["PartnersCapital"]
    assert r.alternates == (
        "PartnersCapitalIncludingPortionAttributableToNoncontrollingInterest",
    )
    assert dict(r.tag_coverage)["PartnersCapital"] == 44


def test_acceptance_partnership_earnings_per_unit_resolves(acceptance):
    """Per-UNIT diluted earnings is per-share diluted earnings for an issuer
    with units instead of shares. The BASIC per-unit sibling is deliberately
    not a family member (basic is a different measure, and MEASURED it adds
    zero coverage), so a resolution here can only be the diluted one.
    """
    r = acceptance[("EPD", "eps_diluted")]
    assert (r.state, r.severity) == (ing.STATE_SINGLE, ing.SEVERITY_RESOLVED)
    assert r.resolved_tags == [
        "NetIncomeLossNetOfTaxPerOutstandingLimitedPartnershipUnitDiluted"
    ]
    basic = "NetIncomeLossPerOutstandingLimitedPartnershipUnitBasicNetOfTax"
    assert basic not in {tag for _, tag in ing.CONCEPT_FAMILIES["eps_diluted"]}


def test_acceptance_partnership_unit_count_comes_from_the_dei_cover_page(acceptance):
    """Why `shares_outstanding` got NO partnership tag (A5.2, measured): the
    partnerships report their unit count in the ordinary dei cover-page fact,
    like everyone else. MEASURED at 244 scale: of the members unresolved on
    this family, ZERO report any unit-count tag in-window -- they are the
    multi-class dimensioned-facts gap, which A5.4 parks unfixed.
    """
    r = acceptance[("EPD", "shares_outstanding")]
    assert (r.state, r.severity) == (ing.STATE_SINGLE, ing.SEVERITY_RESOLVED)
    assert r.resolved_tags == ["EntityCommonStockSharesOutstanding"]
    assert ing.CONCEPT_FAMILIES["shares_outstanding"] == [
        ("dei", "EntityCommonStockSharesOutstanding")
    ]


def test_partnership_tags_never_outrank_corporate_ones():
    """The preference guarantee for A5.2, from the other side: a filer
    reporting both a corporate and a partnership tag resolves corporate.
    """
    rows = _quarterly("StockholdersEquity", _QUARTERS) + _quarterly(
        "PartnersCapital", _QUARTERS
    )
    r = _resolution_for(rows, "equity")
    assert (r.state, r.tags, r.alternates) == (
        ing.STATE_DOMINANT, ("StockholdersEquity",), ("PartnersCapital",),
    )
    rows = _quarterly("EarningsPerShareDiluted", _QUARTERS) + _quarterly(
        "NetIncomeLossNetOfTaxPerOutstandingLimitedPartnershipUnitDiluted", _QUARTERS
    )
    r = _resolution_for(rows, "eps_diluted")
    assert r.tags == ("EarningsPerShareDiluted",)


def test_acceptance_non_usd_reporter_resolves_cleanly_and_says_so(acceptance):
    """S7 finding B11. Enbridge reports 100% of its monetary fundamentals in
    CAD while its price series is USD, and the classifier is unit-blind by
    design -- so the resolution is clean and the CURRENCY is what has to be
    loud. The row carries it and a WARN names it; nothing is converted.
    """
    r = acceptance[("ENB", "revenue")]
    assert r.severity == ing.SEVERITY_RESOLVED       # unit does not gate state
    assert r.unit == "CAD" and r.currency == "CAD" and r.is_non_usd
    assert not r.units_mixed
    eps = acceptance[("ENB", "eps_diluted")]
    assert eps.unit == "CAD/shares" and eps.currency == "CAD"

    problems = ing.non_usd_problems([r, eps])
    assert len(problems) == 2
    assert {p.check for p in problems} == {ing.NON_USD_CHECK}
    assert all(p.severity == "WARN" for p in problems)
    assert "reported in CAD, not USD" in problems[0].message
    assert "wrong by the exchange rate" in problems[0].message


def test_a_usd_reporter_raises_no_currency_warn(acceptance):
    usd = [r for label, r in
           [(k[0], v) for k, v in acceptance.items()] if label != "ENB"]
    assert ing.non_usd_problems(usd) == []
    assert all(not r.is_non_usd for r in usd)


def test_unit_helpers_treat_only_iso_shaped_tokens_as_currency():
    assert ing._unit_currency("USD") == "USD"
    assert ing._unit_currency("CAD/shares") == "CAD"
    assert ing._unit_currency("EUR") == "EUR"
    for non_monetary in ("shares", "pure", "segment", "BillionsCubicFeet",
                         "shares/USD", "", None):
        assert ing._unit_currency(non_monetary) is None


def test_duration_mix_is_recorded_for_every_resolution(acceptance):
    """S7 finding B15: coverage buckets on `period_end`, so an annual or
    year-to-date fact counts toward the quarter it ends in. The semantics are
    deliberately unchanged this round -- the row states the profile so F5 can
    see what it is being handed.
    """
    r = acceptance[("ENB", "revenue")]
    assert r.duration_mix and ":" in r.duration_mix
    kinds = dict(part.split(":") for part in r.duration_mix.split("|"))
    assert {"Q", "FY"} <= set(kinds)
    assert all(int(v) > 0 for v in kinds.values())
    # A balance-sheet family is instant-only, and says so.
    assert acceptance[("EPD", "equity")].duration_mix.startswith("instant:")


def test_duration_buckets_classify_by_length():
    ends = pd.Series(["2024-03-31", "2024-06-30", "2024-09-30",
                      "2024-12-31", "2024-12-31"])
    starts = pd.Series(["2024-01-01", "2024-01-01", "2024-01-01",
                        "2024-01-01", None])
    assert list(ing._duration_buckets(starts, ends)) == [
        "Q", "H1", "9M", "FY", "instant",
    ]


def test_8k_sourced_facts_count_toward_coverage():
    """S7 finding B21, stated as behaviour: an earnings release is a real
    dated disclosure of the same GAAP fact, so a family CAN resolve on 8-K
    facts alone. Documented in OPERATING_FORMS' comment; MEASURED at 244
    scale, no resolved flow family actually depends on it.
    """
    r = _resolution_for(_quarterly("Assets", _QUARTERS, form="8-K"), "assets")
    assert (r.state, r.severity) == (ing.STATE_SINGLE, ing.SEVERITY_RESOLVED)


def test_no_unresolved_pair_ever_yields_a_tag(acceptance):
    """F2_SPEC §8.2: an UNRESOLVED pair never yields a resolved tag from any
    code path -- neither the object, nor the CSV's severity column, nor the
    validation row.
    """
    resolutions = list(acceptance.values())
    unresolved = [r for r in resolutions if r.severity == ing.SEVERITY_UNRESOLVED]
    assert unresolved
    assert all(r.resolved_tags == [] for r in unresolved)
    frame = ing.concept_resolution_frame(resolutions)
    for r in unresolved:
        row = frame[(frame["cik"] == r.cik) & (frame["family"] == r.family)]
        assert row["severity"].iloc[0] == ing.SEVERITY_UNRESOLVED
        assert row["switch_quarter"].iloc[0] == ""
    problems = [p for p in ing.resolution_problems(resolutions)
                if p.check == "fundamentals_alias_unresolved"]
    assert len(problems) == len(unresolved)
    assert all(p.severity == "FATAL" for p in problems)


def test_unresolved_problem_message_names_tags_coverage_and_reason(acceptance):
    """§5.3: the FATAL row names the tags seen, their per-quarter coverage
    (with each tag's last quarter, so a reader can see a dead tag), and the
    exact reason.
    """
    problems = ing.resolution_problems([acceptance[("SLB", "operating_income")]])
    assert len(problems) == 1
    message = problems[0].message
    assert "operating_income: PARTIAL over 44 reportable quarters" in message
    assert "OperatingIncomeLoss 35/44 (80%, last 2024Q1) [STALE]" in message
    assert "union 80%" in message


def test_absent_problem_message_names_the_operating_form_rule(acceptance):
    message = ing.resolution_problems([acceptance[("JPM", "operating_income")]])[0].message
    assert "operating_income: ABSENT" in message
    assert "10-K/10-Q/8-K" in message and "DEF 14A" in message


# ---------------------------------------------------------------------
# Sector-concentration BLOCKER (F2_SPEC §5.3, EXPANSION_PLAN §3.5)
# ---------------------------------------------------------------------


def _synthetic_resolutions(n_members, n_unresolved, family="cash"):
    out = []
    for i in range(n_members):
        unresolved = i < n_unresolved
        out.append(
            ing.ConceptResolution(
                cik=1000 + i, family=family,
                state=ing.STATE_OVERLAP if unresolved else ing.STATE_SINGLE,
                tags=("Assets",), switch_quarter="", coverage=1.0,
                severity=(ing.SEVERITY_UNRESOLVED if unresolved
                          else ing.SEVERITY_RESOLVED),
                tag_coverage=(("Assets", 12),), n_target=12,
            )
        )
    return out


def _sector_universe(n_members, sector="tech"):
    return pd.DataFrame({"cik": [1000 + i for i in range(n_members)],
                         "sector": [sector] * n_members})


def test_sector_blocker_fires_at_21_percent():
    blockers = ing.sector_blockers(_synthetic_resolutions(100, 21),
                                   _sector_universe(100))
    assert len(blockers) == 1
    b = blockers[0]
    assert (b.sector, b.family, b.n_unresolved, b.n_members) == ("tech", "cash", 21, 100)
    assert b.fraction == pytest.approx(0.21)


def test_sector_blocker_does_not_fire_at_19_percent():
    assert ing.sector_blockers(_synthetic_resolutions(100, 19),
                               _sector_universe(100)) == []


def test_sector_blocker_threshold_is_strictly_greater_than_20_percent():
    assert ing.sector_blockers(_synthetic_resolutions(100, 20),
                               _sector_universe(100)) == []


def test_sector_blocker_is_per_sector_and_per_family():
    """One sector's failure must not implicate another's, and one family's
    must not implicate another's.
    """
    resolutions = (
        _synthetic_resolutions(10, 5, family="cash")
        + _synthetic_resolutions(10, 0, family="assets")
    )
    universe = _sector_universe(10, sector="financials")
    blockers = ing.sector_blockers(resolutions, universe)
    assert [(b.sector, b.family, b.n_unresolved) for b in blockers] == [
        ("financials", "cash", 5)
    ]


def test_blocker_problems_are_run_scoped_fatals():
    blockers = ing.sector_blockers(_synthetic_resolutions(100, 21),
                                   _sector_universe(100))
    problems = ing.blocker_problems(blockers)
    assert len(problems) == 1
    p = problems[0]
    assert (p.severity, p.check, p.cik) == (
        "FATAL", "fundamentals_sector_concentration", im.RUN_SCOPE_CIK,
    )
    assert p.message.startswith("BLOCKER: cash is UNRESOLVED for 21/100 (21%)")


def test_print_sector_blockers_says_so_when_there_are_none(capsys):
    ing.print_sector_blockers([])
    assert "no BLOCKER" in capsys.readouterr().out


# ---------------------------------------------------------------------
# companyfacts tail lag -- S7 finding B5 (F2_SPEC amendment A9)
# ---------------------------------------------------------------------


def test_a_truncated_companyfacts_tail_is_caught_by_the_filing_metadata():
    """The blind spot B5 names: coverage and staleness are both anchored on
    the fundamentals themselves, so a company whose companyfacts document
    stops early scores 100% with no alarm. Only an INDEPENDENT source -- the
    filing metadata -- can see it.
    """
    rows = _quarterly("Assets", _QUARTERS) + _quarterly("Revenues", _QUARTERS)
    universe = _universe(1, end=date(2023, 6, 30))
    # The classifier is happy: full coverage, nothing stale.
    r = _resolution_for(rows, "assets", universe)
    assert (r.state, r.coverage, r.stale_tags) == (ing.STATE_SINGLE, 1.0, ())
    # ...but the company filed two 10-Qs after its last fact.
    periodic = {1: ["2022-11-01", "2023-02-01", "2023-05-01"]}
    problems = ing.tail_lag_problems(_frame(rows), universe, periodic)
    assert len(problems) == 1
    assert (problems[0].severity, problems[0].check) == ("WARN", ing.TAIL_LAG_CHECK)
    assert "2023-02-01, 2023-05-01" in problems[0].message
    assert "companyfacts stops at 2022-12-31" in problems[0].message


def test_one_filing_behind_is_info_not_warn():
    """21 of the 22 real cases are the ordinary propagation lag of the most
    recent quarter; escalating those would bury the one real truncation.
    """
    rows = _quarterly("Assets", _QUARTERS)
    problems = ing.tail_lag_problems(
        _frame(rows), _universe(1, end=date(2023, 6, 30)), {1: ["2023-02-01"]},
    )
    assert [p.severity for p in problems] == ["INFO"]
    assert "ordinary propagation lag" in problems[0].message


def test_no_tail_lag_when_filings_stop_with_the_facts():
    rows = _quarterly("Assets", _QUARTERS)
    assert ing.tail_lag_problems(
        _frame(rows), _universe(1), {1: ["2022-11-01", "2022-12-31"]},
    ) == []


def test_tail_lag_is_scoped_to_the_company_window():
    """A member whose window closed years before it stopped filing (EIDP) is
    complete WITHIN its window; the check must not fire on filings that no
    other check in this module would look at either.
    """
    rows = _quarterly("Assets", _QUARTERS)
    problems = ing.tail_lag_problems(
        _frame(rows), _universe(1, start=WINDOW_START, end=WINDOW_END),
        {1: ["2024-05-01", "2025-05-01"]},          # long after window_end
    )
    assert problems == []


def test_tail_lag_emits_nothing_without_filing_metadata():
    """The function stays silent so run() can say NOT CHECKED loudly instead
    of a check quietly passing on an empty input.
    """
    assert ing.tail_lag_problems(
        _frame(_quarterly("Assets", _QUARTERS)), _universe(1), {}
    ) == []


@pytest.mark.parametrize("cik,label", [(831001, "CITIGROUP")])
def test_citigroup_real_data_tail_lag(cik, label):
    """The real B5 case, from the shipped artifacts (read-only): Citigroup's
    companyfacts stops 2026-02-20 while two in-window 10-Qs were filed after
    it, and it still scores 0.9767 with 12 of 14 families resolved.

    If a FRESH companyfacts pull ever closes Citigroup's gap this will fail
    loudly -- at which point re-point it at whichever member is then >= 2
    filings behind, or delete it if none is. It is pinning a real defect, not
    a permanent property of the corpus.
    """
    db, parquet = im.DB_PATH, ing.OUTPUT_PARQUET
    if not db.exists() or not parquet.exists():
        pytest.skip("E2 artifacts not built yet (segments 1 and 3)")
    universe = im.load_universe()
    df = pd.read_parquet(parquet, columns=["cik", "filed"])
    periodic = ing.load_periodic_filing_dates(db)
    assert periodic, "the filings table should carry periodic filings"
    problems = ing.tail_lag_problems(df, universe, periodic)
    warns = [p for p in problems if p.severity == "WARN"]
    assert [p.cik for p in warns] == [cik], (
        f"expected exactly {label} to be >= {ing.TAIL_LAG_WARN_FILINGS} "
        f"periodic filings behind; got {[p.cik for p in warns]}"
    )
    assert "2026-02-20" in warns[0].message
    # ...and the ordinary one-filing lag is reported, not escalated.
    assert len([p for p in problems if p.severity == "INFO"]) >= 1


# ---------------------------------------------------------------------
# BLOCKER_EXEMPT_CELLS (F2_SPEC §5.5 amendment A2, ruled 2026-08-24)
# ---------------------------------------------------------------------


def test_the_shipped_exemptions_are_exactly_the_four_ruled_cells():
    """Entries are added by ruling only. A fifth appearing without one is a
    scope change and must break a test.

    Four, not five: A5.3 added ("*", "liabilities") and ("*",
    "operating_income") and SUPERSEDED ("financials", "operating_income"),
    which is deleted rather than kept alongside its own generalisation.
    """
    assert set(ing.BLOCKER_EXEMPT_CELLS) == {
        ("*", "minority_interest"),
        ("*", "net_income_to_common"),
        ("*", "operating_income"),
        ("*", "liabilities"),
    }
    assert ("financials", "operating_income") not in ing.BLOCKER_EXEMPT_CELLS
    assert all(reason.strip() for reason in ing.BLOCKER_EXEMPT_CELLS.values())
    # The F5 note the ruling attached to the liabilities reason travels with
    # it, because that reason is what a reader sees in the run report.
    assert "liabilities_and_equity - equity" in ing.BLOCKER_EXEMPT_CELLS[
        ("*", "liabilities")
    ]
    assert "non-universal" in ing.BLOCKER_EXEMPT_CELLS[("*", "operating_income")].lower()


def test_an_exempt_cell_is_kept_out_of_the_blocker_table_only(monkeypatch):
    """The whole mechanism in one test: same failures, same FATAL rows, one
    fewer blocker row.
    """
    resolutions = _synthetic_resolutions(100, 21, family="minority_interest")
    universe = _sector_universe(100)
    assert ing.sector_blockers(resolutions, universe) == []
    # ...while every per-pair failure still emits its own FATAL.
    problems = ing.resolution_problems(resolutions)
    assert len(problems) == 21
    assert all(p.severity == "FATAL" for p in problems)
    assert all(p.check == "fundamentals_alias_unresolved" for p in problems)
    # Remove the exemption and the identical data becomes a blocker.
    monkeypatch.setattr(ing, "BLOCKER_EXEMPT_CELLS", {})
    assert len(ing.sector_blockers(resolutions, universe)) == 1


def test_a_sector_scoped_exemption_covers_only_that_sector(monkeypatch):
    """The shipped ledger is all-sector after A5.3, but the mechanism still
    supports a sector-scoped entry and must not leak it to other sectors.
    """
    monkeypatch.setattr(ing, "BLOCKER_EXEMPT_CELLS", {("financials", "cash"): "test"})
    resolutions = _synthetic_resolutions(10, 5, family="cash")
    assert ing.sector_blockers(resolutions, _sector_universe(10, "financials")) == []
    energy = ing.sector_blockers(resolutions, _sector_universe(10, "energy"))
    assert [(b.sector, b.family) for b in energy] == [("energy", "cash")]


def test_a_non_exempt_cell_still_fires_at_the_same_threshold():
    universe = _sector_universe(100)
    assert len(ing.sector_blockers(_synthetic_resolutions(100, 21, family="cash"),
                                   universe)) == 1
    assert ing.sector_blockers(_synthetic_resolutions(100, 19, family="cash"),
                               universe) == []


def test_exemption_status_reports_what_each_entry_suppressed():
    resolutions = (
        _synthetic_resolutions(10, 5, family="minority_interest")
        + _synthetic_resolutions(10, 5, family="cash")
    )
    statuses = ing.blocker_exemption_statuses(resolutions, _sector_universe(10))
    assert len(statuses) == len(ing.BLOCKER_EXEMPT_CELLS)
    by_family = {s.family: s for s in statuses}
    assert by_family["minority_interest"].fired
    assert by_family["minority_interest"].suppressed[0].n_unresolved == 5
    # `cash` is not exempt at all, so it never appears as a status...
    assert "cash" not in by_family
    # ...and the two exemptions that suppressed nothing are reported dead.
    assert not by_family["net_income_to_common"].fired
    assert not by_family["operating_income"].fired


def test_a_dead_exemption_is_reported_as_dead(capsys):
    """Same discipline as data/f2/validation_exceptions.csv: an exemption
    that never fires is a bug in the dict, not a harmless leftover.
    """
    statuses = ing.blocker_exemption_statuses(
        _synthetic_resolutions(10, 0, family="cash"), _sector_universe(10)
    )
    assert all(not s.fired for s in statuses)
    ing.print_blocker_exemptions(statuses)
    out = capsys.readouterr().out
    assert out.count("DEAD") == len(ing.BLOCKER_EXEMPT_CELLS)
    # Every entry is printed with its reason whether or not it fired.
    for (sector, family), reason in ing.BLOCKER_EXEMPT_CELLS.items():
        assert f"({sector}, {family})" in out
        assert reason.split(";")[0][:40] in out


def test_exemptions_never_touch_the_per_pair_fatal_rows(acceptance):
    """Real data, both directions: the exempt families' FATAL rows are all
    still there, and resolution_problems() has no idea the dict exists.
    """
    resolutions = list(acceptance.values())
    problems = [p for p in ing.resolution_problems(resolutions)
                if p.check == "fundamentals_alias_unresolved"]
    unresolved = [r for r in resolutions if r.severity == ing.SEVERITY_UNRESOLVED]
    assert len(problems) == len(unresolved)
    exempt_families = {family for _, family in ing.BLOCKER_EXEMPT_CELLS}
    assert [p for p in problems
            if any(p.message.startswith(f"{f}:") for f in exempt_families)]


# ---------------------------------------------------------------------
# data/f2/concept_resolution.csv (F2_SPEC §5.3)
# ---------------------------------------------------------------------


def test_concept_resolution_csv_has_exactly_the_spec_columns(tmp_path, acceptance):
    path = ing.write_concept_resolution(list(acceptance.values()),
                                        tmp_path / "concept_resolution.csv")
    written = pd.read_csv(path, keep_default_na=False)
    assert list(written.columns) == [
        "cik", "family", "state", "tags", "switch_quarter", "coverage",
        "severity", "alternates", "unit", "units_mixed", "duration_mix",
    ]
    assert len(written) == len(acceptance)
    assert set(written["severity"]) <= {ing.SEVERITY_RESOLVED, ing.SEVERITY_UNRESOLVED}
    assert set(written["state"]) <= set(ing.RESOLVED_STATES) | set(ing.UNRESOLVED_STATES)
    cvx = written[(written["cik"] == CASE_CIKS["CVX"]) & (written["family"] == "cash")]
    assert cvx["tags"].iloc[0] == (
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"
    )


def test_concept_resolution_csv_is_sorted_and_idempotent(tmp_path, acceptance):
    resolutions = list(acceptance.values())
    first = ing.write_concept_resolution(resolutions, tmp_path / "a.csv").read_text()
    second = ing.write_concept_resolution(list(reversed(resolutions)),
                                          tmp_path / "b.csv").read_text()
    assert first == second


def test_migration_row_carries_its_switch_quarter_into_the_csv(tmp_path):
    rows = (
        _quarterly("CashAndCashEquivalentsAtCarryingValue", _QUARTERS[:6])
        + _quarterly("CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
                     _QUARTERS[6:])
    )
    resolutions = ing.classify_universe(_frame(rows), _universe(1))
    written = pd.read_csv(ing.write_concept_resolution(resolutions, tmp_path / "c.csv"),
                          keep_default_na=False)
    cash = written[written["family"] == "cash"].iloc[0]
    assert cash["state"] == ing.STATE_MIGRATION
    assert cash["switch_quarter"] == "2021Q3"
    assert cash["tags"].split("|")[0] == "CashAndCashEquivalentsAtCarryingValue"


# ---------------------------------------------------------------------
# validate_fundamentals() -- the run's whole finding set
# ---------------------------------------------------------------------


def test_validate_fundamentals_returns_unresolved_fatals_and_blockers():
    """One member, one family resolving: every other family is 100% UNRESOLVED
    for the sector, so every non-exempt one is a blocker cell -- and the
    exempt ones lose their table row while keeping their FATAL row.
    """
    rows = _quarterly("Assets", _QUARTERS)          # assets SINGLE, rest ABSENT
    problems = ing.validate_fundamentals(_frame(rows), _universe(1))
    unresolved = [p for p in problems if p.check == "fundamentals_alias_unresolved"]
    blockers = [p for p in problems if p.check == "fundamentals_sector_concentration"]
    assert all(p.severity == "FATAL" for p in problems)
    assert len(unresolved) == len(ing.CONCEPT_FAMILIES) - 1
    exempt_here = {
        family for (sector, family) in ing.BLOCKER_EXEMPT_CELLS
        if sector in ("*", "test")
    }
    assert len(blockers) == len(ing.CONCEPT_FAMILIES) - 1 - len(exempt_here)
    # The exempt families are missing from the blocker table...
    assert not [p for p in blockers
                if any(f"BLOCKER: {f} " in p.message for f in exempt_here)]
    # ...and still present, one per company, in the FATAL rows.
    for family in exempt_here:
        assert [p for p in unresolved if p.message.startswith(f"{family}:")]


def test_validate_fundamentals_is_clean_when_every_family_resolves():
    rows: list[dict] = []
    for family, pairs in ing.CONCEPT_FAMILIES.items():
        rows += _quarterly(pairs[0][1], _QUARTERS)
    assert ing.validate_fundamentals(_frame(rows), _universe(1)) == []


def test_validate_fundamentals_uses_each_company_s_own_window():
    """S2's §3.4 rescoping survives S4: a member with a short window is
    scored against its own reportable quarters, not the corpus window.
    """
    rows = _quarterly("Assets", _QUARTERS, cik=1) + _quarterly(
        "Assets", _QUARTERS[:4], cik=2
    )
    universe = pd.DataFrame({
        "cik": [1, 2],
        "sector": ["tech", "tech"],
        "coverage_start": [WINDOW_START, date(2020, 1, 1)],
        "coverage_end": [WINDOW_END, date(2020, 12, 31)],
    })
    resolutions = {
        (r.cik, r.family): r
        for r in ing.classify_universe(_frame(rows), universe)
    }
    assert resolutions[(1, "assets")].n_target == 12
    assert resolutions[(2, "assets")].n_target == 4
    assert resolutions[(2, "assets")].state == ing.STATE_SINGLE


# ---------------------------------------------------------------------
# run() -- output ordering and the E1-artifact guards
# ---------------------------------------------------------------------


class _FakeClient:
    """Serves the on-disk fixture slices; never touches the network."""

    request_count = 0

    def get_companyfacts(self, cik, force=False):
        return json.loads(
            (FIXTURE_DIR / f"companyfacts_CIK{int(cik):010d}.json").read_text()
        )


def _patch_run(monkeypatch, universe):
    monkeypatch.setattr(ing, "EdgarClient", lambda *a, **k: _FakeClient())
    monkeypatch.setattr(ing, "load_universe", lambda *a, **k: universe)


def test_run_prints_blockers_before_the_per_company_findings(monkeypatch, tmp_path, capsys):
    universe = pd.DataFrame({
        "cik": [CASE_CIKS["JPM"], CASE_CIKS["CVX"]],
        "sector": ["financials", "energy"],
        "coverage_start": [im.CORPUS_WINDOW_START] * 2,
        "coverage_end": [im.CORPUS_WINDOW_END] * 2,
    })
    _patch_run(monkeypatch, universe)
    ing.run(db_path=tmp_path / "e2.db",
            output_parquet=tmp_path / "fundamentals_e2.parquet",
            resolution_csv=tmp_path / "concept_resolution.csv")
    out = capsys.readouterr().out
    banner = "SECTOR-CONCENTRATION BLOCKER(S)"
    assert banner in out and "fundamentals_alias_unresolved" in out
    # The blocker table, then the exemption ledger that says what was kept
    # out of it, then the per-company findings -- never the other way round.
    assert out.index(banner) < out.index("BLOCKER exemptions") \
        < out.index("fundamentals_alias_unresolved")
    assert (tmp_path / "concept_resolution.csv").exists()
    assert (tmp_path / "fundamentals_e2.parquet").exists()
    written = pd.read_csv(tmp_path / "concept_resolution.csv", keep_default_na=False)
    assert len(written) == 2 * len(ing.CONCEPT_FAMILIES)


def test_run_refuses_to_write_e1_frozen_artifacts(monkeypatch, tmp_path):
    _patch_run(monkeypatch, _universe(CASE_CIKS["CVX"]))
    with pytest.raises(ValueError, match="frozen record"):
        ing.run(db_path=ing.E1_DB_PATH, output_parquet=tmp_path / "x.parquet")
    with pytest.raises(ValueError, match="frozen"):
        ing.run(db_path=tmp_path / "e2.db", output_parquet=ing.E1_OUTPUT_PARQUET)


def test_e2_output_paths_are_not_e1_s():
    assert ing.OUTPUT_PARQUET.name == "fundamentals_e2.parquet"
    assert ing.E1_OUTPUT_PARQUET.name == "fundamentals.parquet"
    assert ing.CONCEPT_RESOLUTION_CSV.parts[-2:] == ("f2", "concept_resolution.csv")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
