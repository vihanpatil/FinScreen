# Price-source options for PRODUCT_PLAN §4 decision A

**Researched and written 2026-09-11.** Every pricing/terms claim below carries the URL it
came from and was read on **2026-09-11** unless a different date is stated.

> **NOTHING HAS BEEN PURCHASED, SIGNED UP FOR, OR AGREED TO.** No account was created, no
> paid API was called, no terms were accepted. The owner must approve any spend before
> anything is signed up — PRODUCT_PLAN §1 condition 4 ("No new API spend without owner
> sign-off") is unchanged and this document does not discharge it. This is a shopping
> list, not a purchase.
>
> **What network calls were actually made, so this is auditable:** public pricing and
> terms pages; three `robots.txt` files; Nasdaq Data Link's *unauthenticated public*
> dataset-metadata endpoint (`/api/v3/datatables/.../metadata.json`, no key); and
> Sharadar's own **published, no-signup sample query** using the `test-api-key` printed
> on their front page (`https://sharadar.com/`). Nothing keyed, nothing billable.

---

## 0. Bottom line

| | recommendation | published cost | covers 2014–present? | delisted history | total return | terms fit |
|---|---|---|---|---|---|---|
| **Minimal-cost personal research** | **Sharadar "Prices — Full History"**, bought direct at sharadar.com | **$39/mo**, or **$299/yr = $24.92/mo** | yes (to 1998) | yes, with `permaticker` + CIK | yes (`closeadj`) | Personal Use License, explicit | 
| runner-up on price only | EODHD "EOD Historical Data — All World" | **$19.99/mo**, or **$199/yr = $16.58/mo** | yes (30+ yrs) | yes, full history to delisting date | yes (`adjusted_close`) | Non-Professional User, explicit |
| **Distribution-ready (P6)** | **Tiingo Commercial** + a separately-quoted display/redistribution rider | **$50/mo** published, rider **not published** | yes (30+ yrs) | partial / not vendor-documented | yes (`adjClose`, `divCash`, `splitFactor`) | commercial internal use; **public display still needs the rider** |

**The honest headline on distribution:** *no* personal or non-professional tier from *any*
vendor surveyed permits letting other people use the tool or showing them price data. Every
one of them forbids it in writing. P6 is a commercial-licence purchase plus legal review,
exactly as PRODUCT_PLAN §1 condition 3 says — it is not a config flag. See §5.

**Recommended immediate action:** approve **Sharadar Prices Full History at $299/yr
($24.92/mo)** for P2. It is the only option surveyed whose securities master solves the
repo's *actual* documented failure mode (ticker reassignment on dead members — §4.1), and
its licence is the only one that explicitly carves research outputs and backtest results
out of its attribution requirement. If the owner wants the cheapest number on the page and
is willing to do the CIK↔ticker mapping work by hand, EODHD at $199/yr is $6/mo cheaper.

---

## 1. What the repo actually needs, stated against repo facts

From `data/PRICES_NOTES.md` §2, `data/F2_INGESTION_REPORT.md` §0(c), and PRODUCT_PLAN §3 P2:

| requirement | why, in repo terms |
|---|---|
| **(a) total return / dividend adjustment** | `data/prices_e2.parquet` stores split-adjusted-but-not-dividend-adjusted closes. `PRICES_NOTES.md` §2 already names the consequence: high-yield names (XOM, CVX, JNJ, PG, KO, MCD) carry a systematic negative bias in measured excess return vs low-yield names (AAPL, GOOGL, NVDA), independent of anything in their filings. P2's money-metrics (cumulative return, Sharpe, drawdown vs S&P 500 **total** return) cannot be reported honestly on price return. |
| **(b) delisted-security history** | 32 of 244 members have no usable prices. Per §0(c) the loss is **not flat**: 14.0% of the 2016 membership panel, 16.2% of 2017, → 0% by 2026; energy 16.4%, utilities 0%; core 7.7% vs extension 2.5%. It is **outcome-correlated** (acquisitions and take-privates, not random gaps) — the exact shape that makes early folds look different from late folds for a non-alpha reason. Fixing this is worth more to the study than the dividend gap. |
| **(c) terms permitting automated download + personal research** | The current source has none. See §2. |
| **(d) fundamentals / corporate actions** | **Fundamentals are already solved** — the repo has point-in-time XBRL from EDGAR (`ingest_fundamentals.py`, 3,416 resolutions). Do **not** pay for fundamentals. **Corporate actions are not solved** and are what (a) and (b) actually depend on. |
| scale | 244 CIKs today, 500–1,000 planned (PRODUCT_PLAN §4 decision C, mid-caps). Any per-ticker rate limit must survive ~1,000 full-history backfills. |
| platform | macOS (darwin). Matters for exactly one vendor — see §4.8. |

---

## 2. Yahoo: the current terms state, verified today

**The repo's treatment of Yahoo as non-compliant is correct, and today's evidence is
stronger than what `PRICES_NOTES.md` §1 recorded on 2026-08-18.**

Direct `GET https://query1.finance.yahoo.com/robots.txt`, read 2026-09-11, returns in full:

```
User-agent: *
Disallow: /
```

That is the host serving `/v8/finance/chart/{ticker}` — the endpoint `price_client.fetch_yahoo()`
uses and the one every row of `data/prices.parquet` and `data/prices_e2.parquet` came from
(`source=yahoo_finance_chart`). Unchanged from the 2026-08-18 reading.

Additionally, `GET https://finance.yahoo.com/robots.txt` (read 2026-09-11) now carries a
long `Disallow: /` group that **names automated agents explicitly**, including
`anthropic-ai`, `ClaudeBot`, `Claude-Web`, `GPTBot`, `ChatGPT-User`, `CCBot`, `Bytespider`,
`PerplexityBot`, `Scrapy`, `Google-Extended` and ~30 others. Yahoo has published no terms
authorizing third-party programmatic use of the chart endpoint.

**Conclusion:** Yahoo is a documented compliance exception, not a source. It also fails
requirement (a) — the pipeline deliberately stores raw `close`, not `adjclose`, to keep OHLC
invariants intact (`PRICES_NOTES.md` §2) — and fails (b), since a delisted ticker's history
disappears or is reassigned to whoever holds the symbol now. Decision A is real, not
cosmetic.

*Source: direct HTTPS GET, 2026-09-11 — https://query1.finance.yahoo.com/robots.txt and
https://finance.yahoo.com/robots.txt*

---

## 3. Comparison table

All figures read 2026-09-11. "Personal" = the vendor's own individual / non-professional /
personal tier. Monthly costs are the published list price for that tier.

| vendor | personal cost/mo | history depth | delisted incl.? | div/split adjustment | rate limits | bulk download | automated access | redistribution / display | notable caveat |
|---|---|---|---|---|---|---|---|---|---|
| **Sharadar (direct, sharadar.com)** | **$9** (5yr) / **$19** (10yr) / **$39** (full) — annual $99/$199/**$299** | to **1998** on full tier | **yes**, 21,000+ active *and* delisted, with `permaticker` | **yes** — `closeadj` (split+div), `close` (split), `closeunadj` (raw) | not published as req/min; bulk files sized to the purchased tier | **yes** — `years=5/10/full` bulk downloads | REST API is the product; guest checkout | personal use only, **no redistribution**; attribution needed only if the *data itself* is displayed publicly | not real-time; adjustments restated retroactively (see §4.1) |
| **EODHD** | free ($0) / **$19.99** EOD All World / $29.99 +intraday / $59.99 fundamentals / $99.99 all-in-one | **30+ years** | **yes** — full history to delisting date; pre-2018 delistings are EOD-only | **yes** — `adjusted_close` = split + dividend | **100,000 calls/day**, 1,000 req/min (free tier: 20 calls/day, 1yr depth) | **yes** — Bulk API for EOD/splits/dividends; Windows+Linux downloaders | yes | Non-Pro may "store, manipulate, and analyze"; **may not** resell/retransmit/redistribute/**display**; no account sharing | vendor's own disclaimer: data "is not necessarily real-time nor accurate" |
| **Massive** (ex-Polygon.io) | $0 (2yr) / **$29** (5yr) / **$79** (10yr) / **$199** (20+yr) | **capped per tier** — 12 years needs the **$199** tier | **yes** — "free of survivorship bias — delisted tickers keep their full history", since 2003 | **split only. NOT dividend-adjusted.** Vendor states so outright | unlimited calls on paid tiers; free = 5/min | **yes** — S3 flat files (CSV.gz) on Starter+ | yes, API is the product | individual ToS: "solely for your own personal, non-commercial, and non-business purposes"; business licence otherwise | **rebranded from Polygon.io on 2025-10-30**; public reports of duplicated/missing splits |
| **Tiingo** | $0 Starter / **$30** Power / **$50** Commercial | 30+ years | metadata flags delisted w/ end date; **price-history completeness not vendor-documented** | **yes** — `adjClose/adjOpen/adjHigh/adjLow/adjVolume`, `divCash`, `splitFactor` | Starter: 500 symbols/mo, 50/hr, 1,000/day, 1GB. Power: 109,910 symbols/mo, 10,000/hr, 100,000/day, 40GB | not prominent; per-ticker REST | yes (the ToS anti-scraping clause targets *Website pages*, not the API) | "internal consumption only"; redistribution "only available upon special request... additional fees" | **the free tier is unusable here** — Starter/Trial may not "write, save, archive, back up, or otherwise retain Tiingo Data in any persistent or durable storage". The repo caches to Parquet. |
| **Nasdaq Data Link (Quandl)** | **pricing not published without login** | SEP: to 1998 | yes (via Sharadar) | yes (via Sharadar) | per dataset | yes (datatables bulk) | yes | professional/commercial licence route for Sharadar | **free US equity price tables are gone.** WIKI frozen at March 2018; `GET /api/v3/databases/WIKI.json` now returns "incorrect Dataset code" (verified 2026-09-11) |
| **Alpha Vantage** | free (**25 requests/day**) / $49.99 (75 req/min) / $99.99 / $149.99 / $199.99 / $249.99 | 20+ yrs | `LISTING_STATUS` lists delisted symbols; price history for them not guaranteed | `TIME_SERIES_DAILY_ADJUSTED` is **premium-only** | free tier 25/day | no | yes; ToS grants personal non-commercial use for "investment analysis, research, testing, monitoring" | commercial the moment anyone other than the User can access the information | free tier at 25 req/day = **10–40 days** to backfill 244–1,000 tickers. Cheapest usable tier is **$49.99** — more than twice Sharadar/EODHD for less |
| **Financial Modeling Prep** | free (250 calls/day, 5yr) / **$22** Starter / **$59** Premium / **$149** Ultimate — *all billed annually* | Starter 5yr, Premium 30+yr, Ultimate full | has a Delisted Companies endpoint | adjusted series available | 300 / 750 / 3,000 calls per minute | Ultimate only ("Bulk and Batch Delivery") | yes | "Displaying or redistributing data sourced from FMP requires a specific Data Display and Licensing Agreement with FMP" | month-to-month prices are rendered client-side and **could not be verified** — only the annual-billed figures above are confirmed |
| **IEX Cloud** | — | — | — | — | — | — | — | — | **DEFUNCT.** All API products retired **2024-08-31**; no successor product offered. Do not plan around it. |
| **Norgate Data** | US Stocks: Silver $270/yr, Gold $360/yr, **Platinum $630/yr ($52.50/mo)**, Diamond $787.50/yr ($65.63/mo) — 6-month options also listed | Silver 10yr, Gold 20yr, **Platinum to 1990**, Diamond to 1950 | **only Platinum and above.** Silver/Gold have no delisted securities | yes, incl. historical index constituents ("suitable for backtesting") | local database, no API rate limit | local database refreshed by a desktop updater | via `norgatedata` Python package | licence agreement per their site | **BLOCKER: Windows-only.** Norgate Data Updater requires Windows 10/11 64-bit + .NET 4.7.2, and the Python package needs NDU *running*. The owner's machine is macOS. Would need a Windows VM. |

---

## 4. Per-vendor detail, with the parts that matter

### 4.1 Sharadar — direct channel, and the one that solves the repo's actual problem

Sharadar now sells **direct to consumers** at `sharadar.com` with published prices and guest
checkout, separate from the Nasdaq Data Link route. Published personal-use plans:

| plan | 5 years | 10 years | Full History |
|---|---|---|---|
| Prices | $9/mo ($99/yr) | $19/mo ($199/yr) | **$39/mo ($299/yr)** |
| Fundamentals | $19/mo | $29/mo | $39/mo |
| Bundle (everything) | $29/mo | $49/mo | $69/mo ($499/yr) |

*Source: https://sharadar.com/subscribe (identical content at /pricing), read 2026-09-11.*

**Which tier:** the **10-year tier is not enough.** Ten years back from 2026-09 is ~2016-09,
which misses both the task's 2014 floor and the E2 corpus floor of **2015-07-01**
(`F2_INGESTION_REPORT.md` §1). **Full History ($39/mo, or $299/yr = $24.92/mo effective)** is
the minimum tier that covers the need.

The **Prices** plan (not the Bundle) is the right purchase: it includes `stocks`, `funds`,
`metrics`, `actions` (corporate actions incl. delist reasons), `tickers`, `sp500`
(S&P 500 constituents — P2's benchmark) and `descriptions`. It excludes `fundamentals`,
which the repo already has from EDGAR. **Do not buy the Bundle.**

**Adjustment semantics, verified against the repo's own NVDA split check.** Sharadar's
published no-signup sample query returns, for NVDA around the real 10-for-1 split
(2024-06-10):

```
ticker,date,open,high,low,close,volume,closeadj,closeunadj,lastupdated
NVDA,2024-06-11,...,120.91,...,120.577,120.91,2026-09-10
NVDA,2024-06-10,...,121.79,...,121.444,121.79,2026-09-10
NVDA,2024-06-07,...,120.888,...,120.545,1208.88,2026-09-10
NVDA,2024-06-06,...,120.998,...,120.654,1209.98,2026-09-10
NVDA,2024-06-05,...,122.44,...,122.092,1224.4,2026-09-10
```

Three things fall out, all checkable against `PRICES_NOTES.md` §2:
1. `close` is **split-adjusted** and continuous across the split (122.44 → 120.998 → 120.888
   → 121.79 → 120.91) — **matching the repo's stored Yahoo series to the cent**
   (122.44 / 120.99 / 120.89 / 121.79 / 120.91). Independent cross-vendor agreement on the
   exact window the repo already validated.
2. `closeunadj` shows the true pre-split scale (1224.4, 1209.98, 1208.88) flipping to 121.79
   on the split-effective day — the raw series, available if ever needed.
3. `closeadj` (122.092 vs `close` 122.44) is **split *and* dividend adjusted** — requirement
   (a), delivered as a separate column so `open/high/low/close` stay internally consistent.
   This is precisely the design `PRICES_NOTES.md` §2 said it would not invent unilaterally.

*Source: `https://api.sharadar.com/v1.0/data/stocks?api_key=test-api-key&...` — the sample
key published on https://sharadar.com/ ; queried 2026-09-11.*

**The decisive feature: `permaticker`, `isdelisted`, and a CIK.** The `tickers` table returns
`permaticker, ticker, name, exchange, isdelisted, ..., firstpricedate, lastpricedate,
secfilings` where `secfilings` is the EDGAR URL carrying the CIK. Three lookups against the
repo's own documented failure cases:

| query | Sharadar returns | matches repo? |
|---|---|---|
| `PXD` | `permaticker=196845`, PIONEER NATURAL RESOURCES, **`isdelisted=Y`**, prices 1987-12-22 → 2024-05-02, CIK **0001038357** | delisted member, full price history to the delisting date — exactly what §0(c)'s censoring needs |
| `APC` | **ARKO PETROLEUM CORP**, `isdelisted=N`, CIK **0002080921** | **independently reproduces `ingest_prices.py`'s finding** that `APC` was reassigned away from Anadarko's CIK 773910 |
| `EMC` | a Global X emerging-markets **ETF**, CIK 0001432353 | reproduces the repo's "`EMC` is absent from the bulk map" problem — the symbol is now someone else's |

`ingest_prices.py`'s module docstring says the **only** admissible source of a member's ticker
is EDGAR's CIK-keyed `submissions.json`, because "a dead member's former symbol is routinely
REASSIGNED to an unrelated company" and mapping by symbol "would silently fetch a different
company's price history into this pipeline." Sharadar's `permaticker` + `secfilings` CIK is a
second, independent key that makes that mapping *verifiable* rather than merely *refused* —
and it is the mechanism by which some of the 32 censored CIKs could be recovered. **No other
vendor surveyed publishes a permanent security identifier alongside the SEC CIK.**

**Terms** (https://sharadar.com/terms, read 2026-09-11) — "Personal Use License Terms":
- §2 personal use only; §3 "not available to legal entities or institutions"; accounts
  non-transferable.
- §4 **no redistribution**: "you may not publish, disseminate, re-distribute or share the
  Services Data, or any part thereof, or any derivative data that allows reverse engineering
  of part or all of the Services Data, with anyone else."
- §6 attribution: if the data is **displayed publicly** it must carry "Data from Sharadar.com"
  hyperlinked — **but**, verbatim: *"Attribution is not required for research outputs,
  backtest results, models, summary statistics, trade logs, and similar derived works that do
  not display the Services Data itself."* This is the **only** licence surveyed that names
  research outputs and backtests explicitly, and it is directly on point for the P-S website
  and the P4 evidence panels, which show *metrics*, not price series.
- §5: Sharadar may ask for proof of personal use.

**Caveats.** Daily EOD only, no intraday. `closeadj` is **restated retroactively** on every
new corporate action (the `lastupdated` column exists for exactly this reason) — so a
backtest's adjusted prices are *not* point-in-time as-of the trade date. That is true of every
adjusted-close series from every vendor here and is a property of adjusted prices, not a
Sharadar defect; it needs a one-line disclosure in `PRICES_NOTES.md`, not a different vendor.

### 4.2 EODHD — the cheapest option that clears all three hard requirements

**"EOD Historical Data — All World": $19.99/mo, or $199/yr ($16.58/mo effective).**
100,000 API calls/day, 1,000 requests/minute, 30+ years depth, "splits/dividends, adjusted
data, delisted data". Free tier is 20 calls/day with one year of depth — useless for a
backfill. Fundamentals is a separate $59.99/mo feed the repo does **not** need.
*Source: https://eodhd.com/pricing, 2026-09-11.*

EOD endpoint returns `open, high, low, close` (unadjusted close), **`adjusted_close`**
("Closing price adjusted for splits and dividends") and `volume` (split-adjusted). A **Bulk
API for EOD, Splits and Dividends** exists, which is the right shape for 500–1,000 names.
*Source: https://eodhd.com/financial-apis/api-for-historical-data-and-volumes, 2026-09-11.*

Delisted: a dedicated endpoint; "The US list alone returns tens of thousands of symbols";
"Delisted tickers keep their full history up to the delisting date"; depth by delisting era —
*"Before 2018: EOD only"*, *"After 2018: EOD, Fundamentals, Dividends and Splits"*. The repo's
censoring is concentrated in **2016–2019** delistings, so much of it lands in the
"EOD only" band — which is fine, EOD is all P2 needs, but dividends for a pre-2018 delisted
name may be thin.
*Source: https://eodhd.com/financial-apis/delisted-stock-companies-data-2, 2026-09-11.*

**Terms** (https://eodhd.com/financial-apis/terms-conditions, 2026-09-11): a Non-Professional
User is "an individual who views or uses EOD Historical Data Information solely in a personal
capacity for their own personal investment activities"; such a user **may** "store,
manipulate, and analyze the data for private, non-commercial purposes" — an unusually clean
grant for exactly this repo's behaviour. They **may not** "sell, resell, retransmit,
redistribute, display, or grant access to" the data, and may not share account access.
Vendor's own disclaimer: the data "is not necessarily real-time nor accurate."

**Why it is the runner-up and not the pick:** no permanent security identifier and no CIK. The
repo would have to build and audit its own CIK↔delisted-ticker map for the 32 censored
members — the exact work `ingest_prices.py` refuses to do by symbol alone. That is worth more
than the $6.34/mo saved. If the owner prefers the lower number, this is a perfectly defensible
choice; just budget a session for the mapping and expect some members to stay censored.

### 4.3 Massive (formerly Polygon.io) — rebranded, and priced wrong for this job

**Polygon.io renamed to Massive.com on 2025-10-30.** `polygon.io/*` 301-redirects to
`massive.com/*`; `api.polygon.io` continues to work in parallel with `api.massive.com`.
*Sources: https://massive.com/blog/polygon-is-now-massive ; https://fisd.net/polygon-io-is-now-massive/ ; 301 observed directly 2026-09-11.*

Individual plans: Basic $0 (5 calls/min, **2 years**), Starter **$29** (unlimited calls,
**5 years**, 15-min delayed), Developer **$79** (**10 years**), Advanced **$199** (**20+
years**, real-time). Marked "Individual use only" / "Non-pros only". Flat-file S3 bulk
(CSV.gz) from Starter up. Delisted tickers included on all plans — "free of survivorship bias
— delisted tickers keep their full history", back to 2003.
*Source: https://massive.com/pricing and https://massive.com/stocks, 2026-09-11.*

**Two disqualifiers:**
1. **History is tier-capped and 2014–present is 12 years.** Developer's 10 years does not
   reach 2014 *or* the E2 floor of 2015-07-01. The qualifying tier is **Advanced at $199/mo**
   — 5× Sharadar and 10× EODHD.
2. **No dividend adjustment.** Their own knowledge base, verbatim: *"Our historical market
   data is adjusted for splits by default"* and *"We do not currently provide
   dividend-adjusted data, but we have plans to in the future."* Requirement (a) would have to
   be built by hand from the dividends endpoint — and *"historical dividends are not adjusted
   for splits"*, so the repo would be assembling a total-return series from two feeds with
   mismatched adjustment bases. That is a bug factory in the one number P2 exists to report.
   *Source: https://massive.com/knowledge-base/article/is-polygons-stock-data-adjusted-for-splits-or-dividends, 2026-09-11.*

**Data quality:** public reports of duplicated and missing splits causing wrong prices for
months, missing dividends on well-known tickers, and unresponsive support (Trustpilot reviews
through Dec 2025; `github.com/polygon-io/issues`). Treat as a flag to verify on trial, not as
settled fact.

**Terms** (https://massive.com/legal/individuals-terms-of-service, 2026-09-11): individual
licence is "solely for your own personal, non-commercial, and non-business purposes";
§6.1(h) bars transferring access; §6.1(m) bars use "to carry out any financial activities
subject to registration or licensing". A business licence is required for anything
public-facing; the listed Business stocks tier is **$2,499/mo**.

### 4.4 Tiingo — good data, and the free tier is a trap for this repo

Starter **$0**, Power **$30/mo**, Business/Commercial **$50/mo**.
*Source: https://www.tiingo.com/about/pricing, 2026-09-11.*
Starter: 500 unique symbols/month, 50 requests/hour, 1,000/day, 1 GB/month, 30+ years of price
history. Power: 109,910 symbols/month, 10,000 requests/hour, 100,000/day, 40 GB/month.
*Source: https://www.tiingo.com/pricing, 2026-09-11.*

Fields include `adjClose, adjOpen, adjHigh, adjLow, adjVolume, divCash, splitFactor` — full
total-return machinery, and adjusted OHLC rather than an adjusted close bolted onto raw OHLC,
which is a real advantage over EODHD's single `adjusted_close`.
*Source: https://www.tiingo.com/documentation/end-of-day, 2026-09-11.*

**The trap.** From the ToS (https://app.tiingo.com/tos/, read 2026-09-11), for Starter/Trial
plans the user may not *"write, save, archive, back up, or otherwise retain Tiingo Data in any
persistent or durable storage."* `ingest_prices.py` writes `data/prices_e2.parquet` and
`price_client.py` caches raw payloads under `data/raw/prices/`. **The free tier is therefore
not usable by this repo at all** — a point worth making loudly, because "just use Tiingo's
free tier" is the obvious-looking answer and it is wrong. Paid plans permit retention "solely
to the extent permitted by that Paid Plan" — wording vague enough that the exact retention
right on Power should be confirmed **in writing with Tiingo before purchase**.

Also: "All data via the API is for internal consumption only... Redistribution is only
available upon special request and permission, and comes with additional fees." One account
per platform. The anti-scraping clause ("spiders, robots, scrapers, crawlers... to 'scrape' or
download data") is scoped to *"web pages contained in the Website"*, not the API — API access
is the product and is permitted.

**Delisted coverage** is the weak spot: ticker metadata flags delisted companies with an end
date, but Tiingo does not publish a survivorship-bias claim the way Sharadar, EODHD and
Massive do. Would need verifying on trial against a named dead member (e.g. Anadarko, EMC,
Pioneer) before relying on it.

### 4.5 Nasdaq Data Link (Quandl) — the free US equity tables are gone

- **WIKI Prices is dead.** Frozen at March 2018; `GET https://data.nasdaq.com/api/v3/databases/WIKI.json`
  returns `{"quandl_error":{"code":"QECx02","message":"You have submitted an incorrect Dataset
  code..."}}` (verified 2026-09-11), and the help article on why it stops at March 2018 now
  302-redirects to a generic FAQ. There is **no free US equity price table** on Nasdaq Data
  Link worth planning around.
- **Sharadar is there and healthy but priced behind a login.**
  `GET https://data.nasdaq.com/api/v3/datatables/SHARADAR/SEP/metadata.json` (public, no key,
  read 2026-09-11) returns `"name":"Sharadar Equity Prices"`, `"premium":true`,
  `"status":"ON TIME"`, `"refreshed_at":"2026-09-11T08:04:54.000Z"`,
  `"update_frequency":"CONTINUOUS"`, primary key `["ticker","date"]`. The product page
  (https://data.nasdaq.com/databases/SEP) is JavaScript-rendered and its **pricing is not
  readable without an account** — so no monthly figure for the Nasdaq route can be quoted
  here. QuantRocket's Sharadar page likewise says "Log in or create account to see pricing"
  and "Select license to see pricing", distinguishing Professional from Non-Professional
  licences.
  *Sources: the metadata endpoint above; https://data.nasdaq.com/databases/SEP ;
  https://www.quantrocket.com/pricing/data/sharadar/ — all 2026-09-11.*
- **Practical consequence:** for personal use, buy Sharadar **direct** (§4.1) where the price
  is published and checkout is open. The Nasdaq Data Link route is the **professional /
  commercial** channel — Sharadar's own terms say "Commercial and institutional users should
  obtain data through Nasdaq or another appropriate commercial arrangement." That is the P6
  upgrade path, and its price requires contacting them.

Coverage, per the SEP product page: "more than 20,000 US public companies from 1998",
unadjusted prices, split-adjusted prices, and split-and-dividend-adjusted prices, plus splits,
dividends, spinoffs, acquisitions, **delist reasons** and ticker changes.

### 4.6 Alpha Vantage — free tier is 25 requests/day

Free: **25 API requests per day**, no premium functions. Premium: $49.99 (75 req/min),
$99.99 (150), $149.99 (300), $199.99 (600), $249.99 (1,200); annual plans $499–$2,499.
*Source: https://www.alphavantage.co/premium/, 2026-09-11.*

At 25 requests/day, backfilling 244 tickers takes ~10 days and 1,000 tickers ~40 days, before
any refresh. `TIME_SERIES_DAILY_ADJUSTED` — the endpoint that carries dividend adjustment — is
premium-only. So the real entry price is **$49.99/mo**, more than twice Sharadar Full History
and 2.5× EODHD, for a feed with no permanent identifier and no vendor survivorship-bias claim.

**Terms** (https://www.alphavantage.co/terms_of_service/, a PDF, read 2026-09-11) are
unusually clear and unusually favourable *for personal research*: §2(a) grants use "for
personal, non-commercial use", and the commercial triggers are listed — use beyond
"investment analysis, research, testing, monitoring, and any other activities that are private
and individual in nature"; use on behalf of an entity; **"provide information accessed through
the Alpha Vantage Platform as part of any type of commercial activity that allows individuals
or entities other than User to access information directly or indirectly"**; or active
affiliation with an advisor/broker-dealer. Personal research is squarely inside the grant.
That third trigger is also the clearest statement in this whole survey of why P6 is a
different licence.

### 4.7 Financial Modeling Prep — verified only at annual billing

Personal Use tab: Basic **free** (250 calls/day, EOD historical, 5 years), Starter
**$22.00/mo billed annually** (300 calls/min, 5 years, US coverage), Premium **$59.00/mo
billed annually** (750 calls/min, 30+ years, UK/Canada), Ultimate **$149.00/mo billed
annually** (3,000 calls/min, full historical access, bulk and batch delivery). Trailing-30-day
bandwidth caps: 500 MB free, 20 GB Starter, 50 GB Premium, 150 GB Ultimate. A Delisted
Companies endpoint exists. There is a separate Commercial Use pricing tab.
*Source: https://site.financialmodelingprep.com/developer/docs/pricing, 2026-09-11.*

**Honest gap:** the Monthly/Annual toggle is rendered client-side; the month-to-month prices
could not be read from the served HTML and are **not** stated here. Only the annual-billed
figures above are verified. Anyone acting on FMP must re-read the page in a browser.

Redistribution, verbatim from the pricing page: *"Displaying or redistributing data sourced
from FMP requires a specific Data Display and Licensing Agreement with FMP."*

Not recommended: the 5-year Starter tier misses the window, Premium at $59/yr-billed is more
than Sharadar or EODHD for no identifier advantage, and FMP carries a persistent reputation
for fundamentals-accuracy problems — relevant because its main draw over the cheaper options
is data the repo already gets free from EDGAR.

### 4.8 Norgate Data — excellent for this job, wrong operating system

US Stocks packages (USD, 12-month): Silver **$270**, Gold **$360**, **Platinum $630
($52.50/mo)**, Diamond **$787.50 ($65.63/mo)**; 6-month terms also offered. Only **Platinum
and above** include **delisted securities** (Platinum back to 1990, Diamond back to 1950) and
**historical index constituents**, and only those tiers are marked "Suitable for backtesting".
*Source: https://norgatedata.com/stockmarketpackages.php and https://norgatedata.com/prices.php, 2026-09-11.*

On the merits this is arguably the best survivorship-bias-free retail product in the survey —
historical index constituents are something none of the API vendors sell at this price.

**But it is a local-database product driven by the Norgate Data Updater, which requires
Windows 10/11 64-bit and .NET Framework 4.7.2, and the `norgatedata` Python package requires
NDU to be running.** There is no macOS build. The owner's environment is darwin. Adopting
Norgate means standing up and maintaining a Windows VM purely to refresh prices — a permanent
operational tax that violates the owner's "lazy-elite engineering" principle (no
over-engineering; simple readable core). **Ruled out on platform, not on data.**
*Source: https://norgatedata.com/system-requirements.php, 2026-09-11.*

### 4.9 IEX Cloud — defunct

IEX Group announced retirement in 2024 and **shut all IEX Cloud API products down on
2024-08-31**. Endpoints are unreachable, accounts inactive, and **no successor product** was
offered. Any documentation or blog post recommending IEX Cloud is stale.
*Sources: https://iexcloud.org/ ; https://github.com/api-evangelist/iex-cloud ; 2026-09-11.*

---

## 5. Distribution (P6) — the part that cannot be bought cheaply

PRODUCT_PLAN §1 condition 3 and §3 P6 say distribution requires legal review. The data terms
say the same thing independently, and they are unanimous:

| vendor | what the personal tier forbids |
|---|---|
| Sharadar | "you may not publish, disseminate, re-distribute or share the Services Data... with anyone else" |
| EODHD | may not be "selling, reselling, retransmitting, redistributing, **displaying**, or granting access to the Information" |
| Tiingo | "internal consumption only"; redistribution "only available upon special request and permission, and comes with additional fees" |
| Massive | individual licence is "solely for your own personal, non-commercial, and non-business purposes" |
| Alpha Vantage | commercial if the activity "allows individuals or entities other than User to access information directly or indirectly" |
| FMP | "Displaying or redistributing data sourced from FMP requires a specific Data Display and Licensing Agreement" |

**Three practical consequences, which should be recorded now rather than discovered later:**

1. **The P-S website and the demo must not display price series.** A scroll-driven explainer,
   a recorded video, or a live any-ticker run that *renders a chart of licensed prices* is
   "display" under every licence above. Rendering *derived* outputs — a backtest equity curve,
   a Sharpe number, a drawdown table, a rank with its track record — is a different thing, and
   Sharadar is the only vendor that says so in writing: *"Attribution is not required for
   research outputs, backtest results, models, summary statistics, trade logs, and similar
   derived works that do not display the Services Data itself."* Even there, §6's next
   sentence keeps public display inside personal use only. **Recommendation: make "no licensed
   price series leaves the machine in any public artifact" an architectural rule now**, while
   it is cheap, rather than a retrofit after the site exists.
2. **The cheapest published commercial licence found is Tiingo Commercial at $50/mo**, and it
   buys *internal commercial* use only — public display/redistribution is a separately-priced
   rider that Tiingo does not publish and that must be quoted (sales@tiingo.com). EODHD's B2B
   licensing is quote-based; FMP requires its Data Display and Licensing Agreement; Sharadar
   routes commercial users to Nasdaq Data Link; Massive's Business stocks tier lists at
   **$2,499/mo**. So the distribution-ready number is "$50/mo plus an unknown", and the
   unknown is the real one.
3. **Buying a personal licence now does not prejudice P6.** All of these are month-to-month or
   annual with no long-term contract. Nothing about starting on Sharadar Personal makes a
   later commercial licence harder — and the adapter shape (§6) means switching vendors is a
   new `fetch_*`/`parse_*` pair, not a rewrite.

---

## 6. What the repo would have to change

`price_client.py` and `ingest_prices.py` are already shaped for this. The adapter contract, as
built:

- `PriceClient.fetch_<source>(ticker, force=False) -> raw` — fetches or reuses a cached raw
  payload under `data/raw/prices/<source>/`, with `_is_stale()` honouring `max_age_hours`.
- module-level `parse_<source>_*(raw) -> DataFrame[date, open, high, low, close, volume]`.
- `PriceClient.get_daily_bars(ticker, force, source) -> (DataFrame, source_name)` — dispatches
  on a `source` string, guarded by `if source not in ("stooq-first", "yahoo")`.
- `ingest_prices.ingest_all(..., price_source=...)` threads it through from the
  `--price-source` CLI flag; output is `data/prices_e2.parquet` with
  `cik, ticker, date, open, high, low, close, volume, source, fetched_at`, **keyed on `cik`,
  never `ticker`**.
- `controls.py:382` is the single chokepoint that turns prices into returns:
  `pd.read_parquet(prices_path, columns=["cik", "date", "close"])` → wide close matrix.

**Concrete change list for adopting Sharadar (or EODHD — same shape):**

1. **`price_client.py`** — add `fetch_sharadar()` + `parse_sharadar_csv()`; add `"sharadar"`
   to the `get_daily_bars()` source guard; add the `data/raw/prices/sharadar/` cache dir in
   `__init__`. API key from an environment variable, never committed, never logged. The
   existing `Throttle`, retry/backoff and `USER_AGENT` machinery applies unchanged.
   *Roughly one small function pair plus three one-line edits.*
2. **Prefer the bulk download over per-ticker calls.** Sharadar's bulk files
   (`years=5|10|full`) and EODHD's Bulk API turn ~1,000 sequential GETs into a handful of file
   fetches — better for the vendor, faster, and it fits the existing
   "cache to disk, re-runs make zero network calls" pattern exactly.
3. **Add a `close_adj` column; do not replace `close`.** Widen the Parquet schema to
   `..., close, close_adj, volume, ...`. `PRICES_NOTES.md` §2's reasoning for not storing
   Yahoo's `adjclose` (it would break `close <= high` against split-only OHLC) is satisfied by
   keeping them side by side: `open/high/low/close` stay split-adjusted and mutually
   consistent; `close_adj` is the total-return series and is used only for return math.
4. **`ingest_prices.py`** — add the choice to `build_parser()`'s `--price-source`, the run
   banner at ~line 1573, and the writer. **`meta_tripwire_issues()` is Yahoo-`meta`-specific
   (instrumentType/symbol checks) and must be guarded by source** or it will fire spuriously;
   an equivalent Sharadar tripwire would key off `tickers.category` (`"Domestic Common Stock"`
   vs `"ETF"`) — which would, incidentally, have caught the GLD/SPDR Gold Trust anomaly in
   `F2_INGESTION_REPORT.md` §0(a) the same way.
5. **Ticker resolution — the real prize.** `resolve_universe_tickers()` currently admits only
   EDGAR `submissions.json` plus two evidenced overrides. Add Sharadar's `tickers` table as a
   **second evidenced source keyed on CIK** (via `permaticker` + the CIK in `secfilings`), used
   to recover the 32 censored members. This is a change to
   `data/f2/price_ticker_map.csv`, `resolution_findings()` and the census reconciliation —
   it must be reported as a *finding*, never reconciled away, per the module's own rule.
6. **Freeze discipline — this is the part that must not be done casually.**
   `target_e2.py` pins `sha256(data/prices_e2.parquet)` in its freeze manifest (lines ~136,
   378–379). Rewriting that file silently invalidates the E2 freeze mid-gate. **Write the new
   source to a new file** (e.g. `data/prices_e2_tr.parquet`) and leave `prices_e2.parquet`
   untouched until the owner ratifies a re-pin. Changing the backtest target from `close` to
   `close_adj` changes the **pre-registered** target ratified 2026-08-18 — that is an owner
   ruling under the pre-registration discipline, not an implementation detail.
7. **Tests** — `test_price_client.py` and `test_ingest_prices.py` need offline fixtures for
   the new parser (the suite is offline by design and gates at 815 passed / 5 skipped).
8. **Docs** — `PRICES_NOTES.md` §1/§2 rewritten: the Stooq/Yahoo compliance flag becomes
   history, adjustment semantics change from "dividends excluded, cross-sectional yield bias
   documented" to "total return available in `close_adj`", and the new caveat is added
   (adjusted closes are restated retroactively and are therefore not point-in-time as-of the
   trade date). `README.md` and `LIMITATIONS.md` inherit it.

**Estimated work:** one session for items 1–4 and 7; a second for item 5 (which is genuinely
fiddly and deserves a red-team pass, since a wrong CIK↔permaticker join silently imports
another company's price history — the exact failure `ingest_prices.py` was written to prevent).

---

## 7. Open questions the owner should settle, and what to verify before paying

1. **Approve the spend, and at what level?** $299/yr Sharadar Prices Full History is the
   recommendation. $199/yr EODHD is the cheaper alternative. Nothing proceeds without this.
2. **Does the 2014 floor matter, or is the E2 window (2015-07-01→) the real floor?** Both
   recommended options cover both, so this only matters if a cheaper 10-year tier is ever
   revisited — it is **not** sufficient for either floor.
3. **Verify on a free trial / first billing period, before committing a year:** pull three
   named dead members from the repo's own censored list (Anadarko/CIK 773910, EMC, Pioneer/
   CIK 1038357) and confirm full price history to the delisting date; re-run the NVDA
   2024-06-10 split check in §4.1 against whatever is bought; and diff one live member's
   `close` against `data/prices_e2.parquet` to confirm cross-vendor agreement before the
   target is re-derived.
4. **If Tiingo is ever chosen, get the paid-plan data-retention right in writing** — the ToS
   grants retention "solely to the extent permitted by that Paid Plan" without saying what
   that is, and the free tier forbids durable storage outright.
5. **Ratify the P6 architectural rule now** (§5 item 1): no licensed price series in any
   public artifact — website, video, demo, or shared report. Derived metrics only.
6. **PRODUCT_PLAN §4 decision A's default says "owner names the budget".** The budget that
   buys everything the plan actually needs is **$25/month**.

---

## 8. Source index (all read 2026-09-11)

| claim | URL |
|---|---|
| Yahoo chart-host robots.txt `Disallow: /` | https://query1.finance.yahoo.com/robots.txt |
| Yahoo Finance robots.txt naming ClaudeBot/anthropic-ai/GPTBot etc. | https://finance.yahoo.com/robots.txt |
| Sharadar personal plans and prices | https://sharadar.com/subscribe |
| Sharadar Personal Use License Terms (§2 personal, §4 redistribution, §6 attribution carve-out) | https://sharadar.com/terms |
| Sharadar `stocks`/`tickers` field verification (published `test-api-key` sample) | https://sharadar.com/ → `https://api.sharadar.com/v1.0/data/{stocks,tickers}?api_key=test-api-key&...` |
| Sharadar SEP coverage (20,000+ companies from 1998, delist reasons) | https://data.nasdaq.com/databases/SEP |
| SHARADAR/SEP is premium, status ON TIME 2026-09-11 | https://data.nasdaq.com/api/v3/datatables/SHARADAR/SEP/metadata.json |
| WIKI database code no longer resolves | https://data.nasdaq.com/api/v3/databases/WIKI.json |
| Nasdaq Data Link / Sharadar pricing gated behind login | https://www.quantrocket.com/pricing/data/sharadar/ |
| EODHD plan prices and inclusions | https://eodhd.com/pricing |
| EODHD EOD fields incl. `adjusted_close`, bulk API | https://eodhd.com/financial-apis/api-for-historical-data-and-volumes |
| EODHD delisted coverage and era bands | https://eodhd.com/financial-apis/delisted-stock-companies-data-2 |
| EODHD Non-Professional User rights and prohibitions | https://eodhd.com/financial-apis/terms-conditions |
| Massive individual pricing and history caps | https://massive.com/pricing |
| Massive stocks coverage, delisted, flat files | https://massive.com/stocks |
| Massive: splits adjusted, **dividends not** | https://massive.com/knowledge-base/article/is-polygons-stock-data-adjusted-for-splits-or-dividends |
| Massive individuals ToS (personal, non-commercial) | https://massive.com/legal/individuals-terms-of-service |
| Polygon.io → Massive rebrand, 2025-10-30 | https://massive.com/blog/polygon-is-now-massive ; https://fisd.net/polygon-io-is-now-massive/ |
| Tiingo plan prices ($0 / $30 / $50) | https://www.tiingo.com/about/pricing |
| Tiingo tier limits and symbol counts | https://www.tiingo.com/pricing |
| Tiingo ToS: internal use only, no durable storage on Starter/Trial | https://app.tiingo.com/tos/ |
| Tiingo EOD fields (`adjClose`, `divCash`, `splitFactor`) | https://www.tiingo.com/documentation/end-of-day |
| Alpha Vantage free tier and premium tiers | https://www.alphavantage.co/premium/ |
| Alpha Vantage ToS §2 personal/commercial triggers | https://www.alphavantage.co/terms_of_service/ (PDF) |
| FMP personal-use plans (annual-billed) and display/redistribution agreement | https://site.financialmodelingprep.com/developer/docs/pricing |
| Norgate US Stocks packages and delisted tiers | https://norgatedata.com/stockmarketpackages.php ; https://norgatedata.com/prices.php |
| Norgate Windows-only requirement | https://norgatedata.com/system-requirements.php |
| IEX Cloud shut down 2024-08-31, no successor | https://iexcloud.org/ ; https://github.com/api-evangelist/iex-cloud |

---

*Prepared for PRODUCT_PLAN §4 decision A. This is a main-session research finding, not an
owner ruling, and must never be cited as one (HANDOFF §7). Nothing here has been purchased.*
