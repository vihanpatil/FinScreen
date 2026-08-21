"""
test_pit.py -- tests for pit.value_as_of(), the point-in-time selection
helper over data/fundamentals.parquet-shaped DataFrames.

No network, no EDGAR client involved -- pure DataFrame logic against
fabricated fact rows.

Run with: python3 -m pytest test_pit.py -v
"""
from __future__ import annotations

import pandas as pd
import pytest

from pit import value_as_of


def _row(
    ticker="TEST",
    cik=999999,
    taxonomy="us-gaap",
    concept="NetIncomeLoss",
    unit="USD",
    value=0,
    fy=2024,
    fp="Q1",
    period_start="2024-01-01",
    period_end="2024-03-31",
    form="10-Q",
    accession_number="0000000000-24-000001",
    filed="2024-05-01",
):
    return dict(
        ticker=ticker, cik=cik, taxonomy=taxonomy, concept=concept, unit=unit,
        value=value, fy=fy, fp=fp, period_start=period_start, period_end=period_end,
        form=form, accession_number=accession_number, filed=filed,
    )


# ---------------------------------------------------------------------
# Restatement case -- the one the task spec explicitly requires.
# ---------------------------------------------------------------------


def test_restatement_original_before_restated_after():
    original = _row(value=100, accession_number="0000000000-24-000001", filed="2024-05-01")
    restated = _row(value=105, accession_number="0000000000-24-000002", filed="2024-08-01",
                     form="10-Q/A")
    df = pd.DataFrame([original, restated])

    # Before the restatement was ever filed: nothing to find at all yet for
    # this period -- as_of predates BOTH filings for it.
    assert value_as_of(df, "NetIncomeLoss", "2024-04-01", ticker="TEST") is None

    # After the original filing, before the restatement's filed date: only
    # the original value was knowable.
    before = value_as_of(df, "NetIncomeLoss", "2024-06-01", ticker="TEST")
    assert before is not None
    assert before["value"] == 100
    assert before["accession_number"] == "0000000000-24-000001"

    # Exactly on the restatement's filed date: the restatement is knowable
    # as of that date (filed <= as_of is inclusive).
    on_date = value_as_of(df, "NetIncomeLoss", "2024-08-01", ticker="TEST")
    assert on_date["value"] == 105

    # Well after the restatement: restated value knowable.
    after = value_as_of(df, "NetIncomeLoss", "2024-09-01", ticker="TEST")
    assert after is not None
    assert after["value"] == 105
    assert after["accession_number"] == "0000000000-24-000002"


def test_no_rows_at_all_returns_none():
    df = pd.DataFrame([_row()])
    assert value_as_of(df, "Assets", "2024-06-01", ticker="TEST") is None
    assert value_as_of(df, "NetIncomeLoss", "2024-06-01", ticker="OTHER") is None


# ---------------------------------------------------------------------
# "Latest period" selection -- a newer quarter should win over an older
# quarter's restatement, even if the older quarter was restated more
# recently.
# ---------------------------------------------------------------------


def test_latest_period_wins_over_older_restated_period():
    q1_original = _row(value=100, period_start="2024-01-01", period_end="2024-03-31",
                        fp="Q1", accession_number="0000000000-24-000001", filed="2024-05-01")
    q1_restated = _row(value=105, period_start="2024-01-01", period_end="2024-03-31",
                        fp="Q1", form="10-Q/A",
                        accession_number="0000000000-24-000003", filed="2024-08-15")
    q2_original = _row(value=200, period_start="2024-04-01", period_end="2024-06-30",
                        fp="Q2", accession_number="0000000000-24-000002", filed="2024-08-01")
    df = pd.DataFrame([q1_original, q1_restated, q2_original])

    # As of 2024-08-10: Q2 (filed 2024-08-01) is already knowable and is the
    # latest period; Q1's restatement (filed 2024-08-15) is NOT yet knowable.
    # Latest-period selection should return Q2's value, not Q1's.
    result = value_as_of(df, "NetIncomeLoss", "2024-08-10", ticker="TEST")
    assert result["value"] == 200
    assert result["period_end"] == "2024-06-30"


# ---------------------------------------------------------------------
# Ticker/cik/taxonomy scoping -- no cross-company contamination.
# ---------------------------------------------------------------------


def test_scoped_by_ticker_no_cross_contamination():
    aapl = _row(ticker="AAPL", cik=320193, value=111, accession_number="A-1", filed="2024-05-01")
    msft = _row(ticker="MSFT", cik=789019, value=222, accession_number="M-1", filed="2024-05-01")
    df = pd.DataFrame([aapl, msft])

    aapl_result = value_as_of(df, "NetIncomeLoss", "2024-06-01", ticker="AAPL")
    msft_result = value_as_of(df, "NetIncomeLoss", "2024-06-01", ticker="MSFT")
    assert aapl_result["value"] == 111
    assert msft_result["value"] == 222


def test_scoped_by_cik_and_taxonomy():
    row = _row(taxonomy="dei", concept="EntityCommonStockSharesOutstanding", unit="shares",
               value=1_000_000, period_start=None, period_end="2024-04-15",
               accession_number="A-1", filed="2024-05-01")
    df = pd.DataFrame([row])
    result = value_as_of(
        df, "EntityCommonStockSharesOutstanding", "2024-06-01",
        cik=999999, taxonomy="dei",
    )
    assert result is not None
    assert result["value"] == 1_000_000
    # Wrong taxonomy should not match even with the same concept name.
    assert value_as_of(df, "EntityCommonStockSharesOutstanding", "2024-06-01",
                        cik=999999, taxonomy="us-gaap") is None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
