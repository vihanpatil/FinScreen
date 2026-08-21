"""
price_client.py -- thin, polite, cached HTTP client for daily OHLCV bars.

New file for Phase C. The backtest target ratified in HANDOFF.md §3
(2026-08-18) is forward excess return, and it authorizes exactly one new
external data source: a free daily-price provider (Stooq-class CSV
download), cached and versioned under data/raw/ the same way the EDGAR data
is. This module is that provider client.

------------------------------------------------------------------------
PRIMARY SOURCE (as specified in the task): Stooq's free CSV endpoint
    https://stooq.com/q/d/l/?s={ticker}.us&i=d

*** VERIFIED DISCREPANCY, FLAGGED NOT SILENTLY WORKED AROUND (2026-08-18) ***
The task's premise is that this is an open, keyless CSV download. As of
this ingestion run that is no longer true: EVERY request to
`stooq.com/q/d/l/` (and the `stooq.pl` mirror) returns an HTML page with a
client-side JavaScript proof-of-work challenge
(`crypto.subtle.digest` puzzle solved in-browser, then POSTed to
`/__verify`) instead of a CSV -- confirmed with `curl` sending this
project's real-contact-email User-Agent AND a full desktop-browser User-
Agent string, across four different tickers (nvda/aapl/msft/xom) and both
mirrors; identical challenge page every time, with no dependence on which
ticker was requested. (Count reconciled 2026-08-18 with
`data/PRICES_NOTES.md` §1, which enumerates the same four.)
`stooq.com/robots.txt` independently states
`User-agent: *` / `Disallow: /` (only Googlebot/Bingbot are allowed). This
is not a rate-limit or pacing problem -- slowing down or retrying does not
help -- it is a structural, site-wide anti-automation control. Solving the
JS challenge programmatically was deliberately NOT attempted: doing so
would mean building a bot-check bypass against a site whose own
`robots.txt` says scripted access is unwanted, which is the opposite of
"be a polite client." Per this agent's standing instructions, a documented-
API mismatch like this gets flagged for the owner, not silently routed
around. See `data/PRICES_NOTES.md` for the full writeup and the owner
question this raises.

FALLBACK SOURCE (used here for all 25 universe tickers -- the Stooq failure
above is site-wide, not per-ticker, so every ticker fell through):
    https://query1.finance.yahoo.com/v8/finance/chart/{ticker}
This is a free, keyless, unauthenticated JSON endpoint -- no signup, no API
key, no payment, satisfying the task's "never a paid or keyed API without
stopping to report" rule on its face. It is the same endpoint the widely
used `yfinance` package is built on. Caveat disclosed rather than hidden:
`query1.finance.yahoo.com/robots.txt` ALSO states `Disallow: /` for all
agents, and Yahoo has no published terms authorizing this exact third-party
use. This client uses it anyway, at very light volume (25 sequential
requests total across the whole universe, cached thereafter), as the
documented, keyless, zero-cost option available once the primary source
failed -- but this substitution is flagged as a real, outstanding
compliance question for the owner (see data/PRICES_NOTES.md), the same way
an EDGAR schema mismatch would be flagged rather than resolved unilaterally.

Both sources are wired up as named, swappable code paths (`fetch_stooq()` /
`fetch_yahoo()`) so if Stooq's bot-check is ever lifted (or the owner
decides differently), switching the primary is a one-line change, not a
rewrite.

Politeness, mirroring edgar_client.py's ethos even though neither host
documents a hard rate limit the way SEC EDGAR does:
  - A real User-Agent naming the project + a contact email, on every
    request, to both hosts.
  - Sequential requests only (no concurrency), with a minimum delay between
    requests (`min_interval_seconds`, default 1.5s).
  - Retry with exponential backoff on 429/5xx, capped at `max_retries`.
  - Idempotent local caching under `data/raw/prices/{stooq,yahoo}/` --
    re-running ingestion against an already-cached universe does not
    re-fetch unless the cache is stale or `force=True`.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Same real project-owner contact info used by edgar_client.py -- not a
# placeholder. Neither Stooq nor Yahoo mandates this the way SEC EDGAR does,
# but sending it everywhere costs nothing and keeps this client identifiable
# and polite by the same standard the rest of this repo holds itself to.
USER_AGENT = "FinScreen Research vihanpatil7@gmail.com"

STOOQ_CSV_URL_TMPL = "https://stooq.com/q/d/l/?s={ticker}.us&i=d"
YAHOO_CHART_URL_TMPL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_CACHE_DIR = REPO_ROOT / "data" / "raw" / "prices"

# Daily bars for "today" can still change intraday (today's own bar isn't
# final until market close), so a short staleness window lets a same-day
# re-run reuse cache, while a next-day run picks up newly-closed sessions --
# same spirit as edgar_client.py's 24h submissions.json policy.
DEFAULT_MAX_AGE_HOURS = 20.0

DEFAULT_MIN_INTERVAL_SECONDS = 1.5
DEFAULT_MAX_RETRIES = 4
DEFAULT_BACKOFF_BASE_SECONDS = 2.0

EXPECTED_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


class PriceFetchError(RuntimeError):
    """Base class for any failure fetching/parsing a price series."""


class StooqBotCheckError(PriceFetchError):
    """Stooq returned its JS proof-of-work challenge page instead of CSV."""


class YahooFetchError(PriceFetchError):
    """Yahoo chart endpoint returned an error shape or an HTTP failure."""


# ---------------------------------------------------------------------------
# Politeness: sequential min-interval throttle + retry/backoff
# ---------------------------------------------------------------------------


class Throttle:
    """Enforces a minimum wall-clock gap between successive `.wait()`
    calls. Deliberately simpler than edgar_client.RateLimiter's sliding
    window -- this client only ever runs single-threaded/sequential
    (25 tickers, one request each per source), so a fixed minimum delay is
    sufficient to be a polite, low-volume client without pretending to
    enforce a documented hard cap neither host publishes.
    """

    def __init__(self, min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS):
        self.min_interval_seconds = min_interval_seconds
        self._last_call: Optional[float] = None

    def wait(self) -> None:
        if self._last_call is not None:
            elapsed = time.monotonic() - self._last_call
            remaining = self.min_interval_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_call = time.monotonic()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class PriceClient:
    def __init__(
        self,
        user_agent: str = USER_AGENT,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        min_interval_seconds: float = DEFAULT_MIN_INTERVAL_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE_SECONDS,
        max_age_hours: float = DEFAULT_MAX_AGE_HOURS,
        verbose: bool = True,
    ):
        if "@" not in user_agent:
            raise ValueError("user_agent must include a contact email")
        self.headers = {"User-Agent": user_agent}
        self.cache_dir = Path(cache_dir)
        self.stooq_dir = self.cache_dir / "stooq"
        self.yahoo_dir = self.cache_dir / "yahoo"
        self.stooq_dir.mkdir(parents=True, exist_ok=True)
        self.yahoo_dir.mkdir(parents=True, exist_ok=True)
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.max_age_hours = max_age_hours
        self.verbose = verbose
        self.throttle = Throttle(min_interval_seconds)
        self.request_count = 0  # incremented only on actual network GETs

    # -- low-level, always sequential + throttled + retried ----------------

    def _get(self, url: str, params: Optional[dict] = None) -> requests.Response:
        backoff = self.backoff_base
        for attempt in range(self.max_retries + 1):
            self.throttle.wait()
            self.request_count += 1
            if self.verbose:
                print(f"[price GET] {url}")
            resp = requests.get(url, headers=self.headers, params=params, timeout=30)
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt == self.max_retries:
                    raise PriceFetchError(
                        f"HTTP {resp.status_code} after {self.max_retries} retries: {url}"
                    )
                if self.verbose:
                    print(f"  -> HTTP {resp.status_code}, backing off {backoff:.1f}s")
                time.sleep(backoff)
                backoff *= 2
                continue
            return resp
        raise PriceFetchError(f"Exhausted retries: {url}")

    @staticmethod
    def _is_stale(path: Path, max_age_hours: Optional[float]) -> bool:
        if not path.exists():
            return True
        if max_age_hours is None:
            return False
        age_hours = (time.time() - path.stat().st_mtime) / 3600.0
        return age_hours > max_age_hours

    # -- Stooq (primary, per task spec -- currently bot-gated, see module
    #    docstring) ----------------------------------------------------

    def fetch_stooq(self, ticker: str, force: bool = False) -> str:
        """Fetch (or reuse cached) raw Stooq CSV text for `ticker`. Raises
        StooqBotCheckError if the response is the JS-challenge HTML page
        rather than real CSV -- this is checked both on a fresh network
        fetch AND on a cache read, so a bad response cached before this
        check existed never gets silently treated as real data.
        """
        path = self.stooq_dir / f"{ticker.upper()}.csv"
        if force or self._is_stale(path, self.max_age_hours):
            url = STOOQ_CSV_URL_TMPL.format(ticker=ticker.lower())
            resp = self._get(url)
            text = resp.text
            _raise_if_stooq_bot_check(text, ticker)
            path.write_text(text)
        text = path.read_text()
        _raise_if_stooq_bot_check(text, ticker)
        return text

    # -- Yahoo (fallback, used for all 25 tickers this run -- see module
    #    docstring) -----------------------------------------------------

    def fetch_yahoo(self, ticker: str, force: bool = False) -> dict:
        """Fetch (or reuse cached) raw Yahoo chart JSON for `ticker`, full
        available history, daily interval, with split/dividend event
        annotations included.

        *** VERIFIED QUIRK, WORKED AROUND DELIBERATELY (2026-08-18) ***
        `range=max` combined with `interval=1d` does NOT reliably return
        daily bars: for a ticker with decades of history, Yahoo silently
        serves `meta.dataGranularity="3mo"` (quarterly) instead, ignoring
        the requested interval entirely -- confirmed on AAPL (168 rows,
        exactly one per ~3 months, `range=max`+`interval=1d`) vs. the fix
        below (11,512 true daily rows for the same ticker). Passing
        explicit `period1`/`period2` unix timestamps instead of `range`
        does not trigger this downgrade. `period1=0` (1970-01-01) is used
        unconditionally -- Yahoo just returns data starting from whatever
        the ticker's real first trade date is, so this reliably gets "full
        available history" without needing to know each ticker's IPO date
        in advance.
        """
        path = self.yahoo_dir / f"{ticker.upper()}.json"
        if force or self._is_stale(path, self.max_age_hours):
            url = YAHOO_CHART_URL_TMPL.format(ticker=ticker.upper())
            period2 = int(time.time())
            params = {
                "period1": 0,
                "period2": period2,
                "interval": "1d",
                "events": "div,split",
            }
            resp = self._get(url, params=params)
            if resp.status_code != 200:
                raise YahooFetchError(
                    f"Yahoo chart HTTP {resp.status_code} for {ticker}: {resp.text[:200]}"
                )
            path.write_text(resp.text)
        data = json.loads(path.read_text())
        err = data.get("chart", {}).get("error")
        if err:
            raise YahooFetchError(f"Yahoo chart error for {ticker}: {err}")
        # Guard against the period1/period2-doesn't-help-after-all case for
        # some future ticker/date-range combination -- loud failure, not a
        # silently-accepted wrong granularity (see docstring above).
        granularity = data["chart"]["result"][0]["meta"].get("dataGranularity")
        if granularity != "1d":
            raise YahooFetchError(
                f"Yahoo returned dataGranularity={granularity!r} for {ticker}, "
                "not '1d' -- refusing to treat non-daily bars as daily data"
            )
        return data

    # -- combined: try Stooq, document+fall through to Yahoo -------------

    def get_daily_bars(self, ticker: str, force: bool = False) -> tuple[pd.DataFrame, str]:
        """Return (DataFrame[date,open,high,low,close,volume], source_name).
        Tries Stooq first (per task spec); on ANY PriceFetchError, records
        why and falls through to Yahoo. Raises PriceFetchError only if both
        sources fail.
        """
        try:
            text = self.fetch_stooq(ticker, force=force)
            df = parse_stooq_csv(text)
            return df, "stooq"
        except PriceFetchError as stooq_err:
            if self.verbose:
                print(f"  [{ticker}] Stooq failed ({stooq_err}); trying Yahoo fallback")
            try:
                data = self.fetch_yahoo(ticker, force=force)
                df = parse_yahoo_chart(data)
                return df, "yahoo_finance_chart"
            except PriceFetchError as yahoo_err:
                raise PriceFetchError(
                    f"Both sources failed for {ticker}: stooq={stooq_err!r}, "
                    f"yahoo={yahoo_err!r}"
                ) from yahoo_err


def _raise_if_stooq_bot_check(text: str, ticker: str) -> None:
    stripped = text.lstrip().lower()
    if stripped.startswith("<!doctype html") or stripped.startswith("<html"):
        raise StooqBotCheckError(
            f"Stooq returned an HTML bot-check page for {ticker}, not CSV "
            "(see price_client.py module docstring)"
        )


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------


def parse_stooq_csv(text: str) -> pd.DataFrame:
    """Parse Stooq's documented CSV shape: header
    `Date,Open,High,Low,Close,Volume`, one row per trading day, oldest
    first. Defensive even though `get_daily_bars()` already screens out the
    HTML bot-check page -- a malformed/empty response should raise, not
    silently produce an empty or garbage frame.
    """
    from io import StringIO

    stripped = text.lstrip().lower()
    if stripped.startswith("<!doctype html") or stripped.startswith("<html"):
        raise StooqBotCheckError("refusing to parse HTML as CSV")
    if not text.strip():
        raise PriceFetchError("empty Stooq response")

    df = pd.read_csv(StringIO(text))
    df.columns = [c.strip().lower() for c in df.columns]
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise PriceFetchError(f"Stooq CSV missing expected columns {missing}: got {list(df.columns)}")
    df = df[EXPECTED_COLUMNS].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date
    for col in ("open", "high", "low", "close"):
        df[col] = df[col].astype(float)
    df["volume"] = df["volume"].astype("int64")
    return df.sort_values("date").reset_index(drop=True)


def parse_yahoo_chart(data: dict) -> pd.DataFrame:
    """Parse a Yahoo `/v8/finance/chart/{ticker}` response into
    [date,open,high,low,close,volume]. Uses the plain `close` field (see
    module + data/PRICES_NOTES.md for adjustment semantics: split-adjusted,
    NOT dividend-adjusted) for consistency with open/high/low, which Yahoo
    only ever reports split-adjusted. Rows where any OHLC field is null
    (Yahoo emits these for a handful of halted/no-trade sessions) are
    dropped rather than kept with fabricated values.
    """
    result = data["chart"]["result"][0]
    timestamps = result.get("timestamp", [])
    quote = result["indicators"]["quote"][0]

    rows = []
    for i, ts in enumerate(timestamps):
        o, h, l, c, v = (
            quote["open"][i],
            quote["high"][i],
            quote["low"][i],
            quote["close"][i],
            quote["volume"][i],
        )
        if o is None or h is None or l is None or c is None:
            continue
        d = datetime.fromtimestamp(ts, tz=timezone.utc).date()
        rows.append(
            {
                "date": d,
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(c),
                "volume": int(v) if v is not None else 0,
            }
        )
    df = pd.DataFrame(rows, columns=EXPECTED_COLUMNS)
    return df.sort_values("date").reset_index(drop=True)
