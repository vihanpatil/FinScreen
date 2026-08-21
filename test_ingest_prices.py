"""
test_ingest_prices.py -- tests for ingest_prices.py's coverage/return
validation logic (Phase C, new file, HANDOFF.md §3).

No network calls anywhere in this file -- all inputs are synthetic
DataFrames built in-memory.

Run with: python3 -m pytest test_ingest_prices.py -v
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

import ingest_prices as ip


def _business_days(start: date, n: int) -> list[date]:
    """n consecutive Mon-Fri calendar dates starting at `start` (which must
    itself be a Monday) -- a simple stand-in trading calendar for tests.
    """
    days = []
    d = start
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def _make_universe_df(tickers, calendar_days, close=100.0):
    rows = []
    for t in tickers:
        for d in calendar_days:
            rows.append(
                {
                    "ticker": t,
                    "date": d,
                    "open": close,
                    "high": close + 1,
                    "low": close - 1,
                    "close": close,
                    "volume": 1_000_000,
                    "source": "yahoo_finance_chart",
                    "fetched_at": "2026-08-18T00:00:00+00:00",
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------
# Full-coverage baseline -- no issues at all.
# ---------------------------------------------------------------------


def test_full_coverage_produces_no_issues():
    calendar = _business_days(date(2023, 1, 2), 40)  # a Monday
    tickers = ["AAA", "BBB", "CCC"]
    df = _make_universe_df(tickers, calendar)

    issues = ip.validate_prices(df, tickers, calendar[0], calendar[-1])
    assert issues == []


# ---------------------------------------------------------------------
# Synthetic gap case: a "handful" of missing days is fine; more is a
# loud WARN.
# ---------------------------------------------------------------------


def test_small_gap_is_not_flagged():
    calendar = _business_days(date(2023, 1, 2), 40)
    tickers = ["AAA", "BBB"]
    df = _make_universe_df(tickers, calendar)

    # Drop 3 days for BBB only -- at/under the "handful" threshold.
    drop_dates = set(calendar[5:8])
    df = df[~((df["ticker"] == "BBB") & (df["date"].isin(drop_dates)))]

    issues = ip.validate_prices(df, tickers, calendar[0], calendar[-1])
    warn_gaps = [i for i in issues if i.check == "coverage_gap"]
    assert warn_gaps == []


def test_large_gap_is_flagged_warn_with_missing_dates_listed():
    calendar = _business_days(date(2023, 1, 2), 40)
    tickers = ["AAA", "BBB"]
    df = _make_universe_df(tickers, calendar)

    # Drop 10 days for BBB only -- well past the "handful" threshold.
    drop_dates = set(calendar[5:15])
    df = df[~((df["ticker"] == "BBB") & (df["date"].isin(drop_dates)))]

    issues = ip.validate_prices(df, tickers, calendar[0], calendar[-1])
    gap_issues = [i for i in issues if i.check == "coverage_gap"]
    assert len(gap_issues) == 1
    assert gap_issues[0].severity == "WARN"
    assert gap_issues[0].ticker == "BBB"
    assert "missing 10 trading days" in gap_issues[0].message
    # AAA (full coverage) must not be flagged.
    assert all(i.ticker != "AAA" for i in gap_issues)


# ---------------------------------------------------------------------
# FATAL cases: missing entirely, or ends months early.
# ---------------------------------------------------------------------


def test_ticker_missing_entirely_is_fatal():
    calendar = _business_days(date(2023, 1, 2), 40)
    tickers = ["AAA", "BBB"]
    df = _make_universe_df(["AAA"], calendar)  # BBB never fetched at all

    issues = ip.validate_prices(df, tickers, calendar[0], calendar[-1])
    fatals = [i for i in issues if i.severity == "FATAL" and i.ticker == "BBB"]
    assert len(fatals) == 1
    assert fatals[0].check == "missing_entirely"


def test_ticker_ending_months_early_is_fatal():
    calendar = _business_days(date(2023, 1, 2), 120)
    tickers = ["AAA", "BBB"]
    df = _make_universe_df(tickers, calendar)

    # BBB's history stops ~3 months (60 trading-ish days) before AAA's.
    cutoff = calendar[-60]
    df = df[~((df["ticker"] == "BBB") & (df["date"] > cutoff))]

    issues = ip.validate_prices(df, tickers, calendar[0], calendar[-1])
    fatals = [i for i in issues if i.severity == "FATAL" and i.ticker == "BBB"]
    assert any(i.check == "ends_early" for i in fatals)


def test_ticker_present_but_zero_rows_in_window_is_fatal():
    calendar = _business_days(date(2023, 1, 2), 40)
    tickers = ["AAA", "BBB"]
    df = _make_universe_df(tickers, calendar)

    # BBB only has data before the validation window starts.
    window_start = calendar[-5]
    window_end = calendar[-1]
    df = df[~((df["ticker"] == "BBB") & (df["date"] >= window_start))]

    issues = ip.validate_prices(df, tickers, window_start, window_end)
    fatals = [i for i in issues if i.severity == "FATAL" and i.ticker == "BBB"]
    assert any(i.check == "missing_in_window" for i in fatals)


# ---------------------------------------------------------------------
# Non-positive close -- always FATAL, regardless of window.
# ---------------------------------------------------------------------


def test_zero_or_negative_close_is_fatal():
    calendar = _business_days(date(2023, 1, 2), 10)
    tickers = ["AAA"]
    df = _make_universe_df(tickers, calendar)
    df.loc[df.index[3], "close"] = 0.0
    df.loc[df.index[5], "close"] = -5.0

    issues = ip.validate_prices(df, tickers, calendar[0], calendar[-1])
    fatals = [i for i in issues if i.check == "non_positive_close"]
    assert len(fatals) == 2
    assert all(i.severity == "FATAL" for i in fatals)


# ---------------------------------------------------------------------
# Return outlier detection + calibration.
# ---------------------------------------------------------------------


def test_return_outlier_detected_above_bound():
    calendar = _business_days(date(2023, 1, 2), 10)
    tickers = ["AAA"]
    df = _make_universe_df(tickers, calendar, close=100.0)
    # Inject a +50% single-day move on the LAST day, so there's no
    # subsequent "reverts back to normal" day to also register as its own
    # (equally real) outlier -- keeps this test's assertion count == 1
    # unambiguous while still exercising real outlier detection logic.
    idx = df.index[-1]
    df.loc[idx, "close"] = 150.0

    outliers = ip.find_return_outliers(df, bound=0.15)
    assert len(outliers) == 1
    assert outliers["ret"].iloc[0] == pytest.approx(0.5)


def test_calibrate_return_bound_has_a_floor():
    # Perfectly flat series -> calibrated percentile is 0, floor must apply.
    calendar = _business_days(date(2023, 1, 2), 30)
    df = _make_universe_df(["AAA"], calendar, close=100.0)
    bound = ip.calibrate_return_bound(df)
    assert bound == ip.RETURN_BOUND_FLOOR


def test_calibrate_return_bound_rises_above_floor_for_volatile_data():
    calendar = _business_days(date(2023, 1, 2), 250)
    df = _make_universe_df(["AAA"], calendar, close=100.0)
    # Make most days swing between two values well past the floor so the
    # 99.5th percentile of |return| exceeds RETURN_BOUND_FLOOR.
    closes = [100.0 * (1.3 if i % 2 == 0 else 1.0) for i in range(len(calendar))]
    df["close"] = closes
    bound = ip.calibrate_return_bound(df)
    assert bound > ip.RETURN_BOUND_FLOOR


# ---------------------------------------------------------------------
# load_universe() reads the real, locked universe file without mutating it.
# ---------------------------------------------------------------------


def test_load_universe_returns_all_25_tickers():
    tickers = ip.load_universe()
    assert len(tickers) == 25
    assert "NVDA" in tickers
    assert "AAPL" in tickers


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
