"""
test_ingest_fundamentals.py -- tests for ingest_fundamentals.py's own logic:
concept extraction from a raw companyfacts-shaped dict, the reportable-
quarter window calculation, and the WARN/FATAL validation classification
(structurally-absent vs. migrated-before-window vs. unexplained-gap vs.
partial-coverage bands vs. known mid-window migrations).

No network -- pure function tests against fabricated data.

Run with: python3 -m pytest test_ingest_fundamentals.py -v
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

import ingest_fundamentals as ing


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
# validate_fundamentals() -- synthetic universe/df exercising every branch.
# ---------------------------------------------------------------------


def _fact(ticker, cik, concept, period_end, filed, taxonomy="us-gaap", value=1.0,
          period_start=None, unit="USD", form="10-Q", accession_number="A-1"):
    return dict(
        ticker=ticker, cik=cik, taxonomy=taxonomy, concept=concept, unit=unit,
        value=value, fy=2024, fp="Q1", period_start=period_start, period_end=period_end,
        form=form, accession_number=accession_number, filed=filed,
    )


WINDOW_START = date(2024, 1, 1)
WINDOW_END = date(2024, 12, 31)  # 4 target quarters: 2024 Q1-Q4


def _universe(*tickers):
    return pd.DataFrame({
        "ticker": list(tickers),
        "cik": list(range(1, len(tickers) + 1)),
        "sector": ["test"] * len(tickers),
        "company_name": list(tickers),
    })


def test_structurally_absent_concept_is_warn_not_fatal():
    # TICK never reports Liabilities at all, ever -- but does report revenue
    # and every other core concept fully, so only Liabilities should fire.
    rows = [_fact("TICK", 1, "Revenues", f"2024-0{q}-30" if False else pe, fl)
            for q, (pe, fl) in enumerate([
                ("2024-03-31", "2024-05-01"), ("2024-06-30", "2024-08-01"),
                ("2024-09-30", "2024-11-01"), ("2024-12-31", "2025-02-01"),
            ])]
    for concept in ing.CORE_NON_REVENUE_CONCEPTS:
        if concept == "Liabilities":
            continue
        for pe, fl in [("2024-03-31", "2024-05-01"), ("2024-06-30", "2024-08-01"),
                       ("2024-09-30", "2024-11-01"), ("2024-12-31", "2025-02-01")]:
            rows.append(_fact("TICK", 1, concept, pe, fl))
    df = pd.DataFrame(rows)
    problems = ing.validate_fundamentals(df, _universe("TICK"), WINDOW_START, WINDOW_END)

    liab_problems = [p for p in problems if p.check == "concept_structurally_absent" and p.ticker == "TICK"]
    assert len(liab_problems) == 1
    assert liab_problems[0].severity == "WARN"
    assert "NEVER appeared" in liab_problems[0].message

    fatals = [p for p in problems if p.severity == "FATAL"]
    assert fatals == []


def test_migrated_before_window_concept_is_warn():
    rows = []
    for concept in ing.CORE_NON_REVENUE_CONCEPTS:
        for pe, fl in [("2024-03-31", "2024-05-01"), ("2024-06-30", "2024-08-01"),
                       ("2024-09-30", "2024-11-01"), ("2024-12-31", "2025-02-01")]:
            rows.append(_fact("TICK", 1, concept, pe, fl))
    for pe, fl in [("2024-03-31", "2024-05-01"), ("2024-06-30", "2024-08-01"),
                   ("2024-09-30", "2024-11-01"), ("2024-12-31", "2025-02-01")]:
        rows.append(_fact("TICK", 1, "Revenues", pe, fl))
    # Now overwrite StockholdersEquity with only an OLD, pre-window row.
    rows = [r for r in rows if r["concept"] != "StockholdersEquity"]
    rows.append(_fact("TICK", 1, "StockholdersEquity", "2015-12-31", "2016-02-01"))

    df = pd.DataFrame(rows)
    problems = ing.validate_fundamentals(df, _universe("TICK"), WINDOW_START, WINDOW_END)

    se_problems = [p for p in problems if p.check == "concept_tag_migrated_before_window"]
    assert len(se_problems) == 1
    assert se_problems[0].severity == "WARN"
    assert se_problems[0].ticker == "TICK"

    fatals = [p for p in problems if p.severity == "FATAL"]
    assert fatals == []


def test_unexplained_zero_coverage_is_fatal():
    rows = []
    for concept in ing.CORE_NON_REVENUE_CONCEPTS:
        for pe, fl in [("2024-03-31", "2024-05-01"), ("2024-06-30", "2024-08-01"),
                       ("2024-09-30", "2024-11-01"), ("2024-12-31", "2025-02-01")]:
            rows.append(_fact("TICK", 1, concept, pe, fl))
    for pe, fl in [("2024-03-31", "2024-05-01"), ("2024-06-30", "2024-08-01"),
                   ("2024-09-30", "2024-11-01"), ("2024-12-31", "2025-02-01")]:
        rows.append(_fact("TICK", 1, "Revenues", pe, fl))
    # Assets: has rows, but ALL of them fall outside the target window on
    # both ends (not structurally absent, not migrated-before-window) --
    # e.g. reported only far in the future relative to this window, which
    # is a real, unexplained gap for the window under test.
    rows = [r for r in rows if r["concept"] != "Assets"]
    rows.append(_fact("TICK", 1, "Assets", "2030-03-31", "2030-05-01"))

    df = pd.DataFrame(rows)
    problems = ing.validate_fundamentals(df, _universe("TICK"), WINDOW_START, WINDOW_END)

    assets_problems = [p for p in problems if p.check == "concept_unexplained_gap"]
    assert len(assets_problems) == 1
    assert assets_problems[0].severity == "FATAL"


def test_bank_exemption_downgrades_to_warn():
    rows = []
    for concept in ing.CORE_NON_REVENUE_CONCEPTS:
        if concept in ing.BANK_EXEMPT_CONCEPTS:
            continue
        for pe, fl in [("2024-03-31", "2024-05-01"), ("2024-06-30", "2024-08-01"),
                       ("2024-09-30", "2024-11-01"), ("2024-12-31", "2025-02-01")]:
            rows.append(_fact("JPM", 1, concept, pe, fl))
    for pe, fl in [("2024-03-31", "2024-05-01"), ("2024-06-30", "2024-08-01"),
                   ("2024-09-30", "2024-11-01"), ("2024-12-31", "2025-02-01")]:
        rows.append(_fact("JPM", 1, "Revenues", pe, fl))

    df = pd.DataFrame(rows)
    problems = ing.validate_fundamentals(df, _universe("JPM"), WINDOW_START, WINDOW_END)

    exempt_problems = [p for p in problems if p.ticker == "JPM" and p.check == "concept_structurally_absent"]
    exempt_checks = {p.message.split(":")[0] for p in exempt_problems}
    assert exempt_checks == ing.BANK_EXEMPT_CONCEPTS
    assert all(p.severity == "WARN" for p in exempt_problems)


def test_known_midwindow_migration_is_warn_not_fatal():
    rows = []
    for concept in ing.CORE_NON_REVENUE_CONCEPTS:
        if concept == "NetIncomeLoss":
            continue
        for pe, fl in [("2024-03-31", "2024-05-01"), ("2024-06-30", "2024-08-01"),
                       ("2024-09-30", "2024-11-01"), ("2024-12-31", "2025-02-01")]:
            rows.append(_fact("MA", 1, concept, pe, fl))
    for pe, fl in [("2024-03-31", "2024-05-01"), ("2024-06-30", "2024-08-01"),
                   ("2024-09-30", "2024-11-01"), ("2024-12-31", "2025-02-01")]:
        rows.append(_fact("MA", 1, "Revenues", pe, fl))
    # Only 1/4 target quarters covered for NetIncomeLoss -- a known migration.
    rows.append(_fact("MA", 1, "NetIncomeLoss", "2024-03-31", "2024-05-01"))

    df = pd.DataFrame(rows)
    problems = ing.validate_fundamentals(df, _universe("MA"), WINDOW_START, WINDOW_END)

    ni_problems = [p for p in problems if p.ticker == "MA" and p.check == "concept_quarterly_coverage_midwindow_migration"]
    assert len(ni_problems) == 1
    assert ni_problems[0].severity == "WARN"
    fatals = [p for p in problems if p.severity == "FATAL"]
    assert fatals == []


def test_low_coverage_without_known_migration_is_fatal():
    rows = []
    for concept in ing.CORE_NON_REVENUE_CONCEPTS:
        if concept == "NetIncomeLoss":
            continue
        for pe, fl in [("2024-03-31", "2024-05-01"), ("2024-06-30", "2024-08-01"),
                       ("2024-09-30", "2024-11-01"), ("2024-12-31", "2025-02-01")]:
            rows.append(_fact("TICK", 1, concept, pe, fl))
    for pe, fl in [("2024-03-31", "2024-05-01"), ("2024-06-30", "2024-08-01"),
                   ("2024-09-30", "2024-11-01"), ("2024-12-31", "2025-02-01")]:
        rows.append(_fact("TICK", 1, "Revenues", pe, fl))
    rows.append(_fact("TICK", 1, "NetIncomeLoss", "2024-03-31", "2024-05-01"))  # 1/4 = 25%

    df = pd.DataFrame(rows)
    problems = ing.validate_fundamentals(df, _universe("TICK"), WINDOW_START, WINDOW_END)

    ni_problems = [p for p in problems if p.ticker == "TICK" and p.check == "concept_quarterly_coverage_low"]
    assert len(ni_problems) == 1
    assert ni_problems[0].severity == "FATAL"


def test_clean_coverage_produces_no_problem():
    rows = []
    for concept in ing.CORE_NON_REVENUE_CONCEPTS:
        for pe, fl in [("2024-03-31", "2024-05-01"), ("2024-06-30", "2024-08-01"),
                       ("2024-09-30", "2024-11-01"), ("2024-12-31", "2025-02-01")]:
            rows.append(_fact("TICK", 1, concept, pe, fl))
    rows.append(_fact("TICK", 1, "Revenues", "2024-03-31", "2024-05-01"))

    df = pd.DataFrame(rows)
    problems = ing.validate_fundamentals(df, _universe("TICK"), WINDOW_START, WINDOW_END)
    assert problems == []


def test_revenue_absent_entirely_is_fatal():
    rows = []
    for concept in ing.CORE_NON_REVENUE_CONCEPTS:
        for pe, fl in [("2024-03-31", "2024-05-01"), ("2024-06-30", "2024-08-01"),
                       ("2024-09-30", "2024-11-01"), ("2024-12-31", "2025-02-01")]:
            rows.append(_fact("TICK", 1, concept, pe, fl))
    # No revenue rows at all.
    df = pd.DataFrame(rows)
    problems = ing.validate_fundamentals(df, _universe("TICK"), WINDOW_START, WINDOW_END)

    rev_problems = [p for p in problems if p.check == "revenue_concept_present"]
    assert len(rev_problems) == 1
    assert rev_problems[0].severity == "FATAL"


def test_multiple_revenue_aliases_in_window_is_warn():
    rows = []
    for concept in ing.CORE_NON_REVENUE_CONCEPTS:
        for pe, fl in [("2024-03-31", "2024-05-01"), ("2024-06-30", "2024-08-01"),
                       ("2024-09-30", "2024-11-01"), ("2024-12-31", "2025-02-01")]:
            rows.append(_fact("TICK", 1, concept, pe, fl))
    rows.append(_fact("TICK", 1, "Revenues", "2024-03-31", "2024-05-01"))
    rows.append(_fact("TICK", 1, "RevenueFromContractWithCustomerExcludingAssessedTax",
                       "2024-06-30", "2024-08-01"))

    df = pd.DataFrame(rows)
    problems = ing.validate_fundamentals(df, _universe("TICK"), WINDOW_START, WINDOW_END)

    alias_problems = [p for p in problems if p.check == "revenue_alias_consistency"]
    assert len(alias_problems) == 1
    assert alias_problems[0].severity == "WARN"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
