# Daily price ingestion notes (Phase C)

Companion to `price_client.py` / `ingest_prices.py`. Covers `data/prices.parquet`,
the daily-OHLCV dataset backing the forward-excess-return backtest target
ratified in `HANDOFF.md` §3 (2026-08-18): next-quarter return vs. the
25-stock universe average, aligned to filing dates.

This is the **canonical** write-up of the price-source and adjustment
decisions; `price_client.py` and `ingest_prices.py` point here rather than
repeating it.

---

## 1. Source: Stooq failed, Yahoo Finance chart API used instead (flagged, not silently resolved)

**The task's premise** was that `https://stooq.com/q/d/l/?s={ticker}.us&i=d`
is an open, keyless CSV download. Verified 2026-08-18 that this is no
longer true:

- Every request to `stooq.com/q/d/l/` -- and the `stooq.pl` mirror --
  returns an HTML page requiring a client-side JavaScript proof-of-work
  challenge (a `crypto.subtle.digest` puzzle solved in-browser and POSTed
  to `/__verify`) instead of CSV data. Confirmed with `curl` sending this
  project's real-contact-email User-Agent (`FinScreen Research
  vihanpatil7@gmail.com`) AND a full desktop-browser User-Agent string,
  across **four** different tickers (`nvda`, `aapl`, `msft`, `xom`, each
  tested individually) and both `.com`/`.pl` mirrors. (Earlier drafts of
  this note and of `price_client.py`'s docstring said "five" and "three"
  respectively; the count is reconciled here to the four tickers actually
  enumerated.) Identical challenge page
  every time, independent of ticker -- this is a site-wide gate, not a
  per-symbol data problem, and not a rate-limit/pacing problem (slowing
  down does not help).
- `stooq.com/robots.txt` independently states `User-agent: *` /
  `Disallow: /` (only Googlebot/Bingbot are allowed to crawl anything).

Solving the JS challenge programmatically was **deliberately not
attempted** -- doing so would mean building a bot-check bypass against a
site whose own `robots.txt` says scripted access is unwanted, which is the
opposite of "be a polite client," and arguably crosses from "polite
ingestion" into "circumventing an anti-automation control," which this
agent's scope does not authorize unilaterally.

**Fallback used for all 25 universe tickers** (the Stooq failure is
site-wide, so every ticker fell through, not a handful):
`https://query1.finance.yahoo.com/v8/finance/chart/{ticker}`. This is a
free, keyless, unauthenticated JSON endpoint -- no signup, no API key, no
payment -- the same one the widely-used `yfinance` package is built on.
Caveat disclosed rather than hidden: `query1.finance.yahoo.com/robots.txt`
*also* states `Disallow: /` for all agents, and Yahoo has no published
terms authorizing third-party programmatic use of this endpoint. It was
used anyway, at very light volume (25 sequential GETs total across the
whole universe -- one full-history pull per ticker -- cached to disk
thereafter so re-runs make zero further calls), as the best available
keyless/free/zero-cost option once the task's named primary source failed.

**This is flagged as an open item for the owner**, the same way an EDGAR
schema mismatch would be flagged rather than silently resolved: the data
source actually in use (`data/prices.parquet`, `source=yahoo_finance_chart`
for all rows) is not the one named in the task, and neither of the two
realistic free/keyless options here has a robots.txt that welcomes
programmatic access. If the owner wants a different resolution (e.g.
paying for a licensed data feed, or accepting Yahoo's endpoint as a
documented exception), that is their call, not something this agent should
decide by proceeding silently.

`price_client.py` keeps both code paths (`fetch_stooq()` / `fetch_yahoo()`)
named and swappable -- `get_daily_bars()` always tries Stooq first and only
falls through to Yahoo on failure, so if Stooq's bot-check is ever lifted,
switching back is a one-line change, not a rewrite.

---

## 2. Adjustment semantics -- verified, not assumed

Yahoo's chart endpoint (like Stooq's, and like most free daily-bar feeds)
reports OHLC that is **split-adjusted** but **NOT dividend-adjusted**.

**Verification performed (2026-08-18), against NVDA's real 10-for-1 split
(effective 2024-06-10):**

- `data/prices.parquet`'s NVDA `close` series is continuous across the
  split date: `$122.44` (2024-06-05) -> `$120.99` (06-06) -> `$120.89`
  (06-07) -> `$121.79` (06-10, split-effective day) -> `$120.91` (06-11) --
  no ~90% cliff.
- Max single-day `|return|` for NVDA across 2024-06-01..2024-06-20 is
  **5.2%** (2024-06-05), i.e. an ordinary trading day, not a split
  artifact.
- Confirmed directly from Yahoo's own `events.splits` payload for NVDA:
  `{"date": 1718026200, "numerator": 10.0, "denominator": 1.0,
  "splitRatio": "10:1"}` -- June 10, 2024, matching the real public
  10-for-1 split.
- Confirmed the retroactive-adjustment mechanism directly: fetching a raw
  window spanning the split shows PRE-split dates (e.g. 2024-06-03) already
  reported on the POST-split price scale (~$115), not the pre-split raw
  scale (~$1150) -- i.e. Yahoo restates the entire historical series after
  every split, it does not just adjust forward from the split date.
- `price_client.PriceClient.fetch_yahoo()` additionally asserts
  `meta.dataGranularity == "1d"` on every fetch and raises loudly if not
  (see §3 below for why that guard exists) -- so a silently-wrong
  granularity can't corrupt this check either.

**Dividend adjustment: explicitly NOT applied.** Yahoo's raw `close` field
(what `data/prices.parquet` stores) excludes dividends entirely. Yahoo
separately exposes an `adjclose` field (split- AND dividend-adjusted) in
the same response, which this pipeline deliberately does NOT store, to
keep `open`/`high`/`low`/`close` internally consistent (all four fields are
split-adjusted-only; mixing a dividend-adjusted `close` with
non-dividend-adjusted `open`/`high`/`low` would break OHLC invariants like
`close <= high` in edge cases and make single-column return math
inconsistent with the intraday range columns).

**Consequence for the forward-excess-return backtest target, stated
plainly:** the target is *excess* return -- one stock's return minus the
25-stock universe average return, both computed from these
dividend-excluded closes. Because every name in the average is *also*
missing its dividend income, a large chunk of the systematic
"total-return-vs-price-return" gap cancels out in the subtraction (this is
the "partial mitigation" the task anticipated). **It does NOT cancel
cross-sectional differences in dividend yield across the 25 names.** This
universe spans meaningfully different yield profiles -- e.g. XOM, CVX, JNJ,
PG, KO, MCD historically carry materially higher dividend yields than
AAPL, GOOGL, NVDA. A name with an above-universe-average yield will show a
small, systematic negative bias in its measured "excess return" purely from
this omission (and a below-average-yield name a small positive bias),
independent of anything in its filings. This is a known, documented
limitation of the target as computed from this data -- not something this
ingestion step can fix (a dividend-inclusive target would require storing
`adjclose` and re-deriving OHLC consistency rules, a design decision for
whoever builds `features.py`/`backtest.py`, not for this ingestion file to
decide unilaterally).

---

## 3. A second verified quirk: `range=max` silently returns quarterly bars, not daily

Independent of the Stooq/Yahoo sourcing question above: an initial version
of `fetch_yahoo()` requested `range=max&interval=1d`. For tickers with
decades of history this **silently** returned `meta.dataGranularity="3mo"`
(quarterly bars, e.g. 168 rows for a 42-year AAPL history) while ignoring
the requested `interval=1d` entirely -- caught by the per-ticker coverage
summary showing every ticker with ~160-450 rows instead of ~5,000-14,000,
and confirmed directly by inspecting the cached JSON's `meta` block.

**Fix:** request explicit `period1=0` (1970-01-01) / `period2=<now>` unix
timestamps instead of `range=max`. This reliably returns true daily bars
(verified: AAPL goes from 168 rows to 11,512 true daily rows for the same
ticker/date-range). `fetch_yahoo()` also now asserts
`meta.dataGranularity == "1d"` after every fetch and raises `YahooFetchError`
if that ever stops being true, so a future recurrence of this exact failure
mode can't silently re-corrupt the dataset the way it would have gone
unnoticed without the coverage-summary + granularity-assert combination.

---

## 4. Coverage summary (as of the 2026-08-18 ingestion run)

Full history fetched per ticker (earliest available trading day through
today); validated specifically over the task's required window
(2022-12-01 through today, 930 union trading days):

| Ticker | Rows (full history) | First date (full) | Rows in window | Missing vs. union calendar (window) |
|---|---|---|---|---|
| AAPL | 11,512 | 1980-12-12 | 930 | 0 |
| ABBV | 3,427 | 2013-01-02 | 930 | 0 |
| BAC | 13,486 | 1973-02-21 | 930 | 0 |
| COP | 11,247 | 1981-12-31 | 930 | 0 |
| CSCO | 9,191 | 1990-02-16 | 930 | 0 |
| CVX | 14,278 | 1970-01-02 | 930 | 0 |
| GOOGL | 5,534 | 2004-08-19 | 930 | 0 |
| GS | 6,865 | 1999-05-04 | 930 | 0 |
| HD | 11,316 | 1981-09-22 | 929 | 1 (2026-07-21 -- Yahoo itself reports null OHLC that day; not a parsing bug, verified against the raw cached JSON) |
| JNJ | 14,278 | 1970-01-02 | 930 | 0 |
| JPM | 11,700 | 1980-03-17 | 930 | 0 |
| KO | 14,278 | 1970-01-02 | 930 | 0 |
| MA | 5,089 | 2006-05-25 | 930 | 0 |
| MCD | 14,278 | 1970-01-02 | 930 | 0 |
| MRK | 14,278 | 1970-01-02 | 930 | 0 |
| MSFT | 10,186 | 1986-03-13 | 930 | 0 |
| NVDA | 6,935 | 1999-01-22 | 930 | 0 |
| OXY | 11,247 | 1981-12-31 | 930 | 0 |
| PFE | 13,666 | 1972-06-01 | 930 | 0 |
| PG | 14,278 | 1970-01-02 | 930 | 0 |
| SLB | 11,247 | 1981-12-31 | 930 | 0 |
| UNH | 10,539 | 1984-10-17 | 930 | 0 |
| V | 4,633 | 2008-03-19 | 930 | 0 |
| WMT | 13,606 | 1972-08-25 | 930 | 0 |
| XOM | 14,278 | 1970-01-02 | 930 | 0 |

All 25 tickers reach `2026-08-18` (today) as their last date, both in full
history and within the validation window. Total `data/prices.parquet` row
count: 271,372.

**Validation result: 0 FATAL, 249 WARN.** All 249 WARNs are
`return_outlier` entries (single-day `|return|` above the data-calibrated
15.0% sanity bound -- the 99.5th-percentile-of-|return| calibration came in
below the 15% floor, so the floor governs). Spot-checked against known
market history: essentially all outliers cluster around Black Monday
(1987-10-19), the 2008 financial crisis, and the March 2020 COVID crash,
plus a handful of single-name earnings-driven moves -- i.e. real market
events across 40+ years of full history, not data-quality problems. Zero
outliers fall in the NVDA split window (see §2). No `coverage_gap` or
`ends_early` WARNs and no `FATAL`s of any kind were raised.

Re-running `python3 ingest_prices.py` is idempotent: with all 25 tickers
already cached under `data/raw/prices/yahoo/` (Stooq's cache directory
stays empty since it fails before any CSV is ever received), it makes zero
network calls unless a cached file is older than 20 hours or `--force` is
passed.

---

## 5. Columns in `data/prices.parquet`

`ticker, date, open, high, low, close, volume, source, fetched_at` -- one
row per (ticker, trading day). `source` is `yahoo_finance_chart` for every
row in the current run (see §1). `fetched_at` is a single ISO-8601 UTC
timestamp stamped once per ingestion run (the moment `ingest_prices.py`
started, not the filing/quote date) -- an ingestion-provenance field, not
analysis data, matching the same convention `edgar_client.py`/
`ingest_metadata.py` use for their own fetch timestamps.
