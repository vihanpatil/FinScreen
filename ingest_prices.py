"""
ingest_prices.py -- Phase C daily-price ingestion for FinScreen's backtest
target: forward excess return (next-quarter return vs. the 25-stock universe
average), aligned to filing dates (HANDOFF.md §3, ratified 2026-08-18).

WHAT THIS DOES
  1. Reads the locked 25-ticker universe from data/universe.csv (read-only;
     never expands it -- "no silent scope expansion").
  2. Fetches full available daily-OHLCV history per ticker via
     price_client.PriceClient: Stooq first (per task spec), Yahoo Finance's
     chart endpoint as the documented, keyless fallback -- see
     price_client.py's module docstring and data/PRICES_NOTES.md for why
     the fallback is doing all the work this run (Stooq is bot-gated
     site-wide as of 2026-08-18, not a per-ticker gap).
  3. Writes data/prices.parquet: one row per (ticker, trading day), columns
     ticker, date, open, high, low, close, volume, source, fetched_at.
  4. Runs a validation pass (coverage vs. the union trading calendar,
     zero/negative closes, single-day return outliers) and prints a
     WARN/FATAL report in the same spirit as INGESTION_NOTES.md's
     validate_universe() conventions -- loud, not silent, but does not
     block writing the parquet (the report IS the deliverable signal for a
     human to read, same as ingest_metadata.py's non-DB-blocking WARNs).

ADJUSTMENT SEMANTICS (see data/PRICES_NOTES.md for the full writeup):
  Both sources' OHLC series are SPLIT-ADJUSTED but NOT DIVIDEND-ADJUSTED.
  Verified against NVDA's 10-for-1 split (effective 2024-06-10): the close
  series is continuous (~$115-131 on both sides of the split date) with no
  ~90% cliff. Because the backtest target is EXCESS return vs. the 25-stock
  universe average, excluding dividends partially self-cancels (a common
  "the whole universe is missing dividend income" effect nets out in a
  cross-sectional excess-return calculation) but does NOT cancel differences
  in dividend yield ACROSS the 25 names (e.g. XOM/CVX/JNJ/PG/KO/MCD carry
  materially higher yields than AAPL/GOOGL/NVDA) -- that residual is a real,
  documented limitation, not silently assumed away.

Point-in-time note: `date` here is the trading/quote date of the bar itself,
not a filing date -- this file has no opinion on filing dates at all. The
PIT discipline for the eventual backtest is enforced downstream (Phase C
features/backtest code), by only ever looking up a price bar dated AFTER a
filing's actual `filing_date`, never before it. Storing full history (not
just the post-filing window) here is deliberate -- it's the raw market data
layer; the "don't look before the filing date" rule belongs to the
feature/backtest code that consumes this file, not to ingestion.

NO Anthropic API calls anywhere in this file (verified: no `anthropic`
import, no reference to ANTHROPIC_API_KEY). No trading/order/execution logic
of any kind -- this is a read-only market-data ingestion script for
research/backtesting.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from price_client import PriceClient, PriceFetchError

REPO_ROOT = Path(__file__).resolve().parent
UNIVERSE_CSV = REPO_ROOT / "data" / "universe.csv"
OUTPUT_PARQUET = REPO_ROOT / "data" / "prices.parquet"

# Task-specified validation window: filings corpus spans ~2023-2026 and
# forward returns need ~1 quarter beyond the last filing date, so coverage
# is validated back to 2022-12-01 even though full history is fetched and
# stored.
VALIDATION_WINDOW_START = date(2022, 12, 1)

# "missing more than a handful of trading days" -> WARN
COVERAGE_GAP_WARN_THRESHOLD = 5
# "ending months early" -> FATAL (calendar days behind the universe's own
# most-recent trading day)
ENDING_EARLY_FATAL_DAYS = 45

# Sanity bound for single-day |return|, used only to flag outliers for
# human eyeballing -- never to silently drop or "correct" data. Calibrated
# per-run from the fetched data itself (see calibrate_return_bound()) with a
# floor so a very calm sample doesn't produce a hair-trigger threshold.
RETURN_BOUND_FLOOR = 0.15


# ---------------------------------------------------------------------------
# Universe
# ---------------------------------------------------------------------------


def load_universe(path: Path = UNIVERSE_CSV) -> list[str]:
    df = pd.read_csv(path)
    tickers = df["ticker"].tolist()
    return tickers


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


@dataclass
class TickerResult:
    ticker: str
    source: Optional[str] = None
    rows: int = 0
    first_date: Optional[date] = None
    last_date: Optional[date] = None
    error: Optional[str] = None


def ingest_all(
    client: PriceClient, tickers: list[str], fetched_at: str, force: bool = False
) -> tuple[pd.DataFrame, list[TickerResult]]:
    frames = []
    results = []
    for ticker in tickers:
        try:
            df, source = client.get_daily_bars(ticker, force=force)
        except PriceFetchError as e:
            print(f"[FATAL] {ticker}: no data from any source ({e})")
            results.append(TickerResult(ticker=ticker, error=str(e)))
            continue
        if df.empty:
            print(f"[FATAL] {ticker}: source {source} returned zero rows")
            results.append(TickerResult(ticker=ticker, source=source, error="empty"))
            continue
        df = df.copy()
        df["ticker"] = ticker
        df["source"] = source
        df["fetched_at"] = fetched_at
        frames.append(df)
        results.append(
            TickerResult(
                ticker=ticker,
                source=source,
                rows=len(df),
                first_date=df["date"].min(),
                last_date=df["date"].max(),
            )
        )
    if frames:
        combined = pd.concat(frames, ignore_index=True)
        combined = combined[
            ["ticker", "date", "open", "high", "low", "close", "volume", "source", "fetched_at"]
        ]
        combined = combined.drop_duplicates(subset=["ticker", "date"]).sort_values(
            ["ticker", "date"]
        ).reset_index(drop=True)
    else:
        combined = pd.DataFrame(
            columns=["ticker", "date", "open", "high", "low", "close", "volume", "source", "fetched_at"]
        )
    return combined, results


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


@dataclass
class Issue:
    severity: str  # "WARN" or "FATAL"
    ticker: str
    check: str
    message: str


def build_trading_calendar(df: pd.DataFrame, window_start: date, window_end: date) -> list[date]:
    """Union of every distinct trading date across all tickers within the
    window -- used as a stand-in for "the real NYSE/NASDAQ trading
    calendar." With 25 large-cap US equities, robust to any one ticker's
    own gaps/outages.
    """
    in_window = df[(df["date"] >= window_start) & (df["date"] <= window_end)]
    return sorted(in_window["date"].unique())


def calibrate_return_bound(df: pd.DataFrame, floor: float = RETURN_BOUND_FLOOR) -> float:
    """Calibrate the single-day-return sanity bound from the data itself:
    the 99.5th percentile of |daily return| across the whole universe's
    full fetched history, floored so a very calm sample doesn't produce an
    overly tight threshold that flags routine moves as outliers.
    """
    if df.empty:
        return floor
    d = df.sort_values(["ticker", "date"]).copy()
    d["prev_close"] = d.groupby("ticker")["close"].shift(1)
    d["ret"] = d["close"] / d["prev_close"] - 1.0
    abs_ret = d["ret"].dropna().abs()
    if abs_ret.empty:
        return floor
    calibrated = float(abs_ret.quantile(0.995))
    return max(floor, calibrated)


def find_return_outliers(df: pd.DataFrame, bound: float) -> pd.DataFrame:
    d = df.sort_values(["ticker", "date"]).copy()
    d["prev_close"] = d.groupby("ticker")["close"].shift(1)
    d["ret"] = d["close"] / d["prev_close"] - 1.0
    outliers = d[d["ret"].abs() > bound][["ticker", "date", "prev_close", "close", "ret"]]
    return outliers.reset_index(drop=True)


def validate_prices(
    df: pd.DataFrame,
    tickers: list[str],
    window_start: date,
    window_end: date,
) -> list[Issue]:
    issues: list[Issue] = []

    # -- non-negative/positive close, over the FULL fetched history -------
    bad_close = df[df["close"] <= 0]
    for _, row in bad_close.iterrows():
        issues.append(
            Issue(
                "FATAL",
                row["ticker"],
                "non_positive_close",
                f"close={row['close']} on {row['date']}",
            )
        )

    # -- coverage vs. union trading calendar, within the validation window -
    calendar = build_trading_calendar(df, window_start, window_end)
    calendar_set = set(calendar)
    global_last = max(calendar) if calendar else None

    for ticker in tickers:
        tdf = df[df["ticker"] == ticker]
        in_window = tdf[(tdf["date"] >= window_start) & (tdf["date"] <= window_end)]
        if tdf.empty:
            issues.append(
                Issue("FATAL", ticker, "missing_entirely", "no rows from any source")
            )
            continue
        if in_window.empty:
            issues.append(
                Issue(
                    "FATAL",
                    ticker,
                    "missing_in_window",
                    f"has {len(tdf)} rows total but none in "
                    f"[{window_start}, {window_end}]",
                )
            )
            continue

        ticker_dates = set(in_window["date"])
        missing = sorted(calendar_set - ticker_dates)
        if len(missing) > COVERAGE_GAP_WARN_THRESHOLD:
            preview = ", ".join(str(d) for d in missing[:10])
            more = f" (+{len(missing) - 10} more)" if len(missing) > 10 else ""
            issues.append(
                Issue(
                    "WARN",
                    ticker,
                    "coverage_gap",
                    f"missing {len(missing)} trading days vs. union calendar: {preview}{more}",
                )
            )

        ticker_last = max(ticker_dates)
        if global_last is not None:
            days_behind = (global_last - ticker_last).days
            if days_behind > ENDING_EARLY_FATAL_DAYS:
                issues.append(
                    Issue(
                        "FATAL",
                        ticker,
                        "ends_early",
                        f"last date {ticker_last} is {days_behind} calendar days "
                        f"behind universe max {global_last}",
                    )
                )

    # -- single-day return outliers ---------------------------------------
    bound = calibrate_return_bound(df)
    outliers = find_return_outliers(df, bound)
    for _, row in outliers.iterrows():
        issues.append(
            Issue(
                "WARN",
                row["ticker"],
                "return_outlier",
                f"{row['date']}: {row['prev_close']:.2f} -> {row['close']:.2f} "
                f"({row['ret'] * 100:+.1f}%), bound={bound * 100:.1f}%",
            )
        )

    return issues


def print_report(issues: list[Issue], bound: Optional[float] = None) -> int:
    fatals = [i for i in issues if i.severity == "FATAL"]
    warns = [i for i in issues if i.severity == "WARN"]

    print("\n=== Validation report ===")
    if bound is not None:
        print(f"Return-outlier sanity bound (calibrated from data): {bound * 100:.1f}%")
    if not issues:
        print("No issues found.")
        return 0
    for i in fatals:
        print(f"[FATAL] {i.ticker}: {i.check} -- {i.message}")
    for i in warns:
        print(f"[WARN]  {i.ticker}: {i.check} -- {i.message}")
    print(f"\n{len(fatals)} FATAL, {len(warns)} WARN")
    return 1 if fatals else 0


def print_coverage_summary(results: list[TickerResult]) -> None:
    print("\n=== Per-ticker coverage summary ===")
    print(f"{'ticker':8s} {'source':22s} {'rows':>6s} {'first_date':12s} {'last_date':12s}")
    for r in sorted(results, key=lambda r: r.ticker):
        if r.error:
            print(f"{r.ticker:8s} {'FAILED':22s} {'-':>6s} {'-':12s} {'-':12s}  ({r.error})")
        else:
            print(
                f"{r.ticker:8s} {r.source:22s} {r.rows:6d} "
                f"{str(r.first_date):12s} {str(r.last_date):12s}"
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="bypass cache, re-fetch every ticker"
    )
    parser.add_argument(
        "--fetched-at",
        default=None,
        help="override the ingestion timestamp (ISO 8601, UTC); default: now",
    )
    parser.add_argument(
        "--output", default=str(OUTPUT_PARQUET), help="output parquet path"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="suppress per-request GET logging"
    )
    args = parser.parse_args(argv)

    fetched_at = args.fetched_at or datetime.now(timezone.utc).isoformat()

    tickers = load_universe()
    print(f"Universe: {len(tickers)} tickers -- {', '.join(tickers)}")

    client = PriceClient(verbose=not args.quiet)
    combined, results = ingest_all(client, tickers, fetched_at=fetched_at, force=args.force)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(output_path, index=False)
    print(f"\nWrote {len(combined)} rows to {output_path}")

    print_coverage_summary(results)

    window_end = date.today()
    issues = validate_prices(combined, tickers, VALIDATION_WINDOW_START, window_end)
    bound = calibrate_return_bound(combined)
    exit_code = print_report(issues, bound=bound)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
