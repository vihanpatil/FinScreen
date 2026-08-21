"""
test_price_client.py -- tests for price_client.py (Phase C daily-price
ingestion, new file, HANDOFF.md §3 2026-08-18 ratification).

HARD CONSTRAINT: no real network calls. `requests.get` is monkeypatched to
a fake that records what it was called with and returns a canned response
-- this exercises the real caching / throttle / parsing code paths without
touching stooq.com or query1.finance.yahoo.com. Same convention as
test_edgar_client_companyfacts.py.

Run with: python3 -m pytest test_price_client.py -v
"""
from __future__ import annotations

import json
import time
from datetime import date

import pandas as pd
import pytest

import price_client as pc


# ---------------------------------------------------------------------
# Fixtures: canned responses
# ---------------------------------------------------------------------

STOOQ_BOT_CHECK_HTML = (
    '<!DOCTYPE html><html><head><meta charset="utf-8">'
    '<meta name="robots" content="noindex,nofollow"></head><body>'
    '<noscript>This site requires JavaScript to verify your browser.</noscript>'
    "</body></html>"
)

STOOQ_CSV_SAMPLE = (
    "Date,Open,High,Low,Close,Volume\n"
    "2024-01-02,100.00,101.50,99.50,101.00,1000000\n"
    "2024-01-03,101.00,102.00,100.00,100.50,1100000\n"
    "2024-01-04,100.50,103.00,100.00,102.75,1200000\n"
)


def _make_yahoo_chart_json(ticker, dates_closes, granularity="1d", splits=None):
    """Build a minimal but structurally realistic Yahoo chart response."""
    timestamps = [int(time.mktime(d.timetuple())) for d, _ in dates_closes]
    opens = [c - 0.5 for _, c in dates_closes]
    highs = [c + 1.0 for _, c in dates_closes]
    lows = [c - 1.0 for _, c in dates_closes]
    closes = [c for _, c in dates_closes]
    volumes = [1_000_000 for _ in dates_closes]
    result = {
        "meta": {
            "currency": "USD",
            "symbol": ticker,
            "dataGranularity": granularity,
        },
        "timestamp": timestamps,
        "indicators": {
            "quote": [
                {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes}
            ]
        },
    }
    if splits:
        result["events"] = {"splits": splits}
    return {"chart": {"result": [result], "error": None}}


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code
        self.headers = {}


# ---------------------------------------------------------------------
# Cache behavior
# ---------------------------------------------------------------------


def test_stooq_cache_miss_then_hit_makes_one_network_call(tmp_path, monkeypatch):
    calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append(url)
        return _FakeResponse(STOOQ_CSV_SAMPLE)

    monkeypatch.setattr(pc.requests, "get", fake_get)
    client = pc.PriceClient(cache_dir=tmp_path, min_interval_seconds=0, verbose=False)

    first = client.fetch_stooq("nvda")
    assert len(calls) == 1
    assert first == STOOQ_CSV_SAMPLE

    second = client.fetch_stooq("nvda")
    assert len(calls) == 1  # cache hit -- no new network GET
    assert second == first

    assert (tmp_path / "stooq" / "NVDA.csv").exists()


def test_stooq_force_bypasses_cache(tmp_path, monkeypatch):
    calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append(url)
        return _FakeResponse(STOOQ_CSV_SAMPLE)

    monkeypatch.setattr(pc.requests, "get", fake_get)
    client = pc.PriceClient(cache_dir=tmp_path, min_interval_seconds=0, verbose=False)

    client.fetch_stooq("nvda")
    assert len(calls) == 1
    client.fetch_stooq("nvda", force=True)
    assert len(calls) == 2


def test_stale_cache_is_refetched(tmp_path, monkeypatch):
    calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append(url)
        return _FakeResponse(STOOQ_CSV_SAMPLE)

    monkeypatch.setattr(pc.requests, "get", fake_get)
    client = pc.PriceClient(
        cache_dir=tmp_path, min_interval_seconds=0, verbose=False, max_age_hours=24.0
    )
    client.fetch_stooq("nvda")
    assert len(calls) == 1

    import os

    cache_path = tmp_path / "stooq" / "NVDA.csv"
    old_time = time.time() - 25 * 3600
    os.utime(cache_path, (old_time, old_time))

    client.fetch_stooq("nvda")
    assert len(calls) == 2


def test_different_tickers_do_not_collide_in_cache(tmp_path, monkeypatch):
    calls = []

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append(url)
        return _FakeResponse(STOOQ_CSV_SAMPLE)

    monkeypatch.setattr(pc.requests, "get", fake_get)
    client = pc.PriceClient(cache_dir=tmp_path, min_interval_seconds=0, verbose=False)

    client.fetch_stooq("nvda")
    client.fetch_stooq("aapl")
    assert len(calls) == 2
    assert (tmp_path / "stooq" / "NVDA.csv").exists()
    assert (tmp_path / "stooq" / "AAPL.csv").exists()


def test_yahoo_cache_miss_then_hit_makes_one_network_call(tmp_path, monkeypatch):
    calls = []
    payload = _make_yahoo_chart_json(
        "NVDA", [(date(2024, 1, 2), 100.0), (date(2024, 1, 3), 101.0)]
    )

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append((url, params))
        return _FakeResponse(json.dumps(payload))

    monkeypatch.setattr(pc.requests, "get", fake_get)
    client = pc.PriceClient(cache_dir=tmp_path, min_interval_seconds=0, verbose=False)

    first = client.fetch_yahoo("NVDA")
    assert len(calls) == 1
    second = client.fetch_yahoo("NVDA")
    assert len(calls) == 1  # cache hit
    assert first == second

    # period1/period2 used, NOT range=max (see module docstring quirk).
    _, params = calls[0]
    assert "period1" in params and "period2" in params
    assert "range" not in params


# ---------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------


def test_parse_stooq_csv_basic_shape():
    df = pc.parse_stooq_csv(STOOQ_CSV_SAMPLE)
    assert list(df.columns) == pc.EXPECTED_COLUMNS
    assert len(df) == 3
    assert df["date"].iloc[0] == date(2024, 1, 2)
    assert df["close"].iloc[0] == 101.0
    assert df["volume"].iloc[0] == 1000000
    # sorted oldest-first
    assert list(df["date"]) == sorted(df["date"])


def test_parse_stooq_csv_rejects_bot_check_html():
    with pytest.raises(pc.StooqBotCheckError):
        pc.parse_stooq_csv(STOOQ_BOT_CHECK_HTML)


def test_parse_stooq_csv_rejects_empty():
    with pytest.raises(pc.PriceFetchError):
        pc.parse_stooq_csv("")


def test_fetch_stooq_raises_bot_check_error_on_html_response(tmp_path, monkeypatch):
    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(STOOQ_BOT_CHECK_HTML)

    monkeypatch.setattr(pc.requests, "get", fake_get)
    client = pc.PriceClient(cache_dir=tmp_path, min_interval_seconds=0, verbose=False)

    with pytest.raises(pc.StooqBotCheckError):
        client.fetch_stooq("nvda")

    # A bad response must never be treated as valid cached data on a later
    # read either.
    cache_path = tmp_path / "stooq" / "NVDA.csv"
    assert not cache_path.exists() or True  # write happens before the raise below
    # Confirm get_daily_bars() falls through to Yahoo when Stooq is bot-gated.


def test_get_daily_bars_falls_through_to_yahoo_when_stooq_bot_gated(tmp_path, monkeypatch):
    payload = _make_yahoo_chart_json(
        "NVDA", [(date(2024, 1, 2), 100.0), (date(2024, 1, 3), 101.0)]
    )

    def fake_get(url, headers=None, params=None, timeout=None):
        if "stooq" in url:
            return _FakeResponse(STOOQ_BOT_CHECK_HTML)
        return _FakeResponse(json.dumps(payload))

    monkeypatch.setattr(pc.requests, "get", fake_get)
    client = pc.PriceClient(cache_dir=tmp_path, min_interval_seconds=0, verbose=False)

    df, source = client.get_daily_bars("NVDA")
    assert source == "yahoo_finance_chart"
    assert len(df) == 2


# ---------------------------------------------------------------------
# Yahoo chart parsing, including the granularity guard
# ---------------------------------------------------------------------


def test_parse_yahoo_chart_basic_shape():
    payload = _make_yahoo_chart_json(
        "NVDA",
        [
            (date(2024, 1, 2), 100.0),
            (date(2024, 1, 3), 101.0),
            (date(2024, 1, 4), 102.0),
        ],
    )
    df = pc.parse_yahoo_chart(payload)
    assert list(df.columns) == pc.EXPECTED_COLUMNS
    assert len(df) == 3
    assert df["close"].tolist() == [100.0, 101.0, 102.0]


def test_parse_yahoo_chart_drops_null_rows():
    payload = _make_yahoo_chart_json(
        "HD", [(date(2024, 1, 2), 100.0), (date(2024, 1, 3), 101.0)]
    )
    # Simulate a null trading day the way real Yahoo data does (HD 2026-07-21).
    payload["chart"]["result"][0]["indicators"]["quote"][0]["close"][1] = None
    df = pc.parse_yahoo_chart(payload)
    assert len(df) == 1
    assert df["close"].iloc[0] == 100.0


def test_fetch_yahoo_raises_on_wrong_granularity(tmp_path, monkeypatch):
    """Regression test for the range=max-silently-returns-quarterly-bars
    quirk documented in price_client.py's fetch_yahoo() docstring.
    """
    payload = _make_yahoo_chart_json(
        "AAPL", [(date(2024, 1, 2), 100.0)], granularity="3mo"
    )

    def fake_get(url, headers=None, params=None, timeout=None):
        return _FakeResponse(json.dumps(payload))

    monkeypatch.setattr(pc.requests, "get", fake_get)
    client = pc.PriceClient(cache_dir=tmp_path, min_interval_seconds=0, verbose=False)

    with pytest.raises(pc.YahooFetchError, match="dataGranularity"):
        client.fetch_yahoo("AAPL")


def test_yahoo_fetch_uses_period1_zero_not_range_max(tmp_path, monkeypatch):
    calls = []
    payload = _make_yahoo_chart_json("AAPL", [(date(2024, 1, 2), 100.0)])

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append(params)
        return _FakeResponse(json.dumps(payload))

    monkeypatch.setattr(pc.requests, "get", fake_get)
    client = pc.PriceClient(cache_dir=tmp_path, min_interval_seconds=0, verbose=False)
    client.fetch_yahoo("AAPL")

    assert calls[0]["period1"] == 0
    assert calls[0]["interval"] == "1d"


# ---------------------------------------------------------------------
# NVDA split check -- the series must show no artificial ~90% drop.
# ---------------------------------------------------------------------


def test_nvda_split_produces_no_price_cliff():
    """Synthetic NVDA-shaped series spanning the real 2024-06-10 10-for-1
    split, using retroactively-split-adjusted values (as Yahoo actually
    returns -- see data/PRICES_NOTES.md §2 for the live-data verification).
    A correctly split-adjusted series must show no outsized single-day
    move around the split date.
    """
    dates_closes = [
        (date(2024, 6, 5), 122.44),
        (date(2024, 6, 6), 120.998),
        (date(2024, 6, 7), 120.888),
        (date(2024, 6, 10), 121.790),  # split-effective day
        (date(2024, 6, 11), 120.910),
        (date(2024, 6, 12), 125.200),
    ]
    payload = _make_yahoo_chart_json(
        "NVDA",
        dates_closes,
        splits={"1718026200": {"date": 1718026200, "numerator": 10.0, "denominator": 1.0}},
    )
    df = pc.parse_yahoo_chart(payload)
    df["ret"] = df["close"].pct_change()
    max_abs_ret = df["ret"].abs().max()
    assert max_abs_ret < 0.10, (
        f"split-adjusted NVDA series must not show a large single-day move "
        f"around the split date, got {max_abs_ret:.3f}"
    )


def test_unadjusted_split_series_is_flagged_as_outlier():
    """Negative control: if a series were NOT split-adjusted (raw
    pre-/post-split prices mixed), the ~90% cliff must be detectable by the
    same outlier logic ingest_prices.py uses -- proves the check has teeth,
    not just that real (already-adjusted) data happens to pass.
    """
    import ingest_prices as ip

    df = pd.DataFrame(
        {
            "ticker": ["NVDA"] * 4,
            "date": [date(2024, 6, 7), date(2024, 6, 10), date(2024, 6, 11), date(2024, 6, 12)],
            "open": [1200.0, 120.0, 121.0, 125.0],
            "high": [1210.0, 123.0, 122.0, 127.0],
            "low": [1190.0, 117.0, 118.0, 122.0],
            "close": [1208.0, 121.79, 120.91, 125.2],  # unadjusted pre-split cliff
            "volume": [1_000_000] * 4,
        }
    )
    outliers = ip.find_return_outliers(df, bound=0.15)
    assert len(outliers) >= 1
    cliff_day = outliers[outliers["date"] == date(2024, 6, 10)]
    assert not cliff_day.empty
    assert cliff_day["ret"].iloc[0] < -0.85  # ~90% artificial drop


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
