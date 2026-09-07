"""
controls.py -- POSITIVE CONTROLS for the E2 evaluation harness (item H1 of
the F2.5 hardening phase, `HARDENING_PROGRESS.md`).

WHY THIS FILE EXISTS
--------------------
`data/reevaluation_2026-08-25/alternatives.md` §D5a states the gap plainly:
E1 tested a hypothesis, got a null, and diagnosed the null; E2 is a
higher-powered rerun of the same test; and **nowhere in the plan is there a
known-positive effect that the harness is required to recover**. Without one,
a null is uninterpretable -- "there is no text signal" cannot be separated
from "this harness, universe, horizon, benchmark and target cannot detect
*any* signal."

This module answers that with two controls over frozen artifacts only:

  T1 -- PLUMBING CHECK (must be strongly positive).
        Over the in-membership item-2.02 earnings 8-Ks with price coverage,
        does the CONTEMPORANEOUS announcement-window return relate to the
        earnings surprise in the expected (positive) direction? This is the
        single most replicated relationship in empirical accounting
        (Ball & Brown 1968 and its 50-year successor literature). If the
        PIT / join / date-alignment / benchmark stack is wired correctly it
        MUST show up. A T1 failure means the stack is broken and no E2
        result -- positive or null -- can be believed.

  T2 -- KNOWN NUMERIC ANOMALY at the harness's own configuration.
        (a) PEAD: does the same earnings surprise predict the FORWARD
            63-trading-day excess return (the harness's own window and
            benchmark)?
        (b) 12-1 MOMENTUM: does the classic Jegadeesh-Titman cross-sectional
            momentum signal do the same?
        Both are documented but heavily decayed in post-2000 large caps, so
        the honest pre-declared expectation is "small and positive," and a
        flat zero is a soft warning about the configuration, not proof of a
        bug. This is stated in the spec BEFORE the run, not after.

  T0 -- ZERO-INFORMATION PLACEBO (must be ~zero).
        A deterministic seeded pseudo-random signal pushed through the exact
        same event panel, target, folds and IC machinery. If the placebo
        shows signal, the machinery manufactures correlation and every other
        number in this file is void. This is the "assume an evaluation bug
        first" rule made executable.

NON-GOALS (`HANDOFF.md` §1, unconditional and inherited here). Nothing in
this file places, queues, recommends or evaluates a trade. There is no
expected-return figure, no "beats the market" framing, and no investment
advice anywhere. The quantities computed are rank correlations used to test
whether a research harness can recover a relationship that is already known
to exist in the academic record; they are diagnostics of the measurement
instrument, not a strategy.

WHAT THIS FILE MAY AND MAY NOT TOUCH
------------------------------------
* Reads (read-only, no writes ever): `data/filings_metadata_e2.db`,
  `data/prices_e2.parquet`, `data/fundamentals_e2.parquet`.
* Imports `backtest.py` READ-ONLY for the deduplication machinery, so the
  dedup rule here is literally the shipped one, not a paraphrase of it.
  It does NOT edit `backtest.py` or `diagnose.py` (item H2 owns those).
* Writes exactly one artifact: `data/hardening/controls_results.json`.
* Makes ZERO network requests. There is no HTTP client imported anywhere in
  this module's import graph that it calls.

PRE-DECLARATION AND THE G3 HAZARD
---------------------------------
Gate G3 is a hard stop: the E2 benchmark definition, fold structure and
primary metric are owner-ratified BEFORE the first E2 backtest run, and folds
are never chosen or adjusted after seeing results.

This module is deliberately built so that it CANNOT pre-empt G3:

* No model is fitted. Every signal here (SUE, momentum, placebo) is a fixed
  formula with zero estimated parameters, so there is no training set, no
  test set, and no train/test split to choose. The calendar-quarter grouping
  below exists only to report per-period spreads (a standing requirement:
  never a single point estimate) -- it is NOT a fold structure and must not
  be read as a proposal for one.
* Every threshold, window, and pass/fail rule lives in `SPEC` below and was
  written before the module was executed for the first time. `SPEC_SHA256`
  is emitted into the results JSON so the spec text that produced a given
  set of numbers is identifiable after the fact. (This is provenance, not
  proof of ordering: the honest statement is that the author had seen no T1,
  T2 or T0 outcome number when SPEC was written.)
* E2's benchmark (equal-weighted over that date's members EXCLUDING self,
  membership-dated) is used here because it is E2's PROPOSAL under
  `EXPANSION_PLAN.md` §3.3, still awaiting the owner's G3 ratification. If
  G3 ratifies something else, these controls must be re-run under it. E1 and
  E2 numbers are numerically incomparable (different benchmark) and nothing
  in this file should ever be compared to an E1 backtest figure.

POINT-IN-TIME DISCIPLINE, EXACTLY AS IMPLEMENTED
------------------------------------------------
1. **`filing_date` never `report_date`.** Event dates come from
   `filings.filing_date`; `report_date` is not read anywhere in this module.
   Fundamentals availability is governed solely by the `filed` column.
   `period_end` IS used, but only as a fiscal-calendar label to line up
   quarter q with quarter q-4 -- never as an availability date.

2. **The post-close acceptance issue (`data/F2_INGESTION_REPORT.md` §3.3:
   20,715 of 45,545 filings, 45%, are accepted at 16:00-17:00 ET while
   carrying that day's `filing_date`).** Handled explicitly and
   conservatively:

     info_date    = max(filing_date, acceptance_date_ET)
                    -- the max() also covers the two Salesforce filings whose
                       filing_date precedes acceptance by 344 and 633 days;
                       the bytes were not public on their filing_date.
     post_close   = (acceptance time in ET) >= 16:00
     news_session = first trading session >= info_date        if not post_close
                    first trading session >  info_date        if post_close
     pre_session  = the trading session immediately before news_session

   `news_session` is the first session whose CLOSE can reflect the news.
   `pre_session`'s close cannot. Everything downstream is defined off those
   two, so no return window in this module can open on a session that
   pre-dates the information.

   The forward (T2) window opens at `news_session + 1` sessions -- i.e. the
   entry close always POST-DATES the session in which the news was first
   impounded. For a pre-close filing this equals the shipped harness rule
   ("first trading day strictly after filing_date", `features.py`
   `build_target()`); for a post-close filing it is one session LATER than
   the shipped rule, which is exactly the conservative correction the
   post-close finding demands. A `skip1` sensitivity arm opens one further
   session out.

3. **The surprise numerator is contemporaneous by construction; every
   scaling input is strictly prior.** The announced quarter's EPS is the
   figure the 8-K itself made public at `info_date`. Our structured record
   of it usually arrives later (in the subsequent 10-Q), so the value used is
   the AS-ORIGINALLY-REPORTED one (earliest `filed` row for that
   (cik, period_end)), never a restatement. The year-ago comparison quarter
   and every quarter entering the trailing volatility scaler are required to
   have been `filed` STRICTLY BEFORE the event date. See the honest caveat
   in `sue_caveat` in the results JSON: because the XBRL record of the
   announced quarter post-dates the press release, its value can differ from
   the number actually printed in the release (GAAP vs adjusted, or an
   early revision). That biases T2 mildly OPTIMISTIC, which is why a
   strict-PIT sensitivity arm (events whose announced-quarter EPS was itself
   filed on or before the event date) is reported beside it.

4. **Benchmark members are membership-dated and self-excluded**, and a
   member contributes to the benchmark only where it has REAL price coverage
   on both window endpoints. Prices are forward-filled only INSIDE each
   CIK's own [first observation, last observation] coverage window; outside
   it they are NaN. This deliberately differs from `features.py`'s
   `_asof_price()`, which returns the last known price for any later date and
   would therefore contribute a fabricated 0% return for a name whose price
   history has ended. The count of member-cells dropped for missing coverage
   is reported, never silently absorbed.

5. **No shuffling anywhere.** Every panel is time-ordered by the public
   date. Period grouping is calendar-quarter of the event's own session.

HOW UNCERTAINTY IS REPORTED
---------------------------
Never a single point estimate. For every control:
  * per-calendar-quarter cross-sectional Spearman IC, with n per quarter;
  * cross-quarter mean, SAMPLE std (ddof=1 -- the methodology-audit lens's
    defect 1 is that the shipped code uses ddof=0 over 6 numbers; this file
    uses ddof=1 from the start, and does not edit the shipped files, which
    are H2's), SE = std/sqrt(k), t = mean/SE;
  * fraction of positive quarters;
  * a block bootstrap over WHOLE QUARTERS (resampling quarters, not events)
    -- the honest treatment of within-quarter cross-sectional dependence;
  * the pooled all-events IC beside it, with its unadjusted p-value flagged
    as anti-conservative because events cluster in earnings seasons;
  * dedup and raw side by side (dedup via the shipped
    `backtest.company_quarter_dedup_keep_mask`, imported read-only).

Run:  python3 controls.py
      python3 -m pytest test_controls.py -q
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

# Read-only import: we reuse the SHIPPED deduplication rule rather than
# paraphrasing it. Importing backtest.py executes no I/O and fits nothing.
import backtest as B

REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
METADATA_DB = DATA_DIR / "filings_metadata_e2.db"
PRICES_PATH = DATA_DIR / "prices_e2.parquet"
FUNDAMENTALS_PATH = DATA_DIR / "fundamentals_e2.parquet"
OUTPUT_DIR = DATA_DIR / "hardening"
RESULTS_PATH = OUTPUT_DIR / "controls_results.json"


# ---------------------------------------------------------------------------
# SPEC -- every choice pre-declared, before the first execution of this file.
# ---------------------------------------------------------------------------

SPEC = {
    "version": "H1-controls-v1 (2026-08-25)",
    "population": {
        "events": "filings.has_earnings_item = 1 (8-K item 2.02), whose "
                  "filing_date lies inside the filer's own membership spell "
                  "(member_from <= filing_date < member_to; open spells "
                  "treated as running to a far-future sentinel), and whose CIK appears "
                  "in data/prices_e2.parquet. Expected n = 5,552 per "
                  "data/reevaluation_2026-08-25/alternatives.md §1.",
        "identity_key": "cik (never ticker -- dual-class/shared-CIK safety, "
                        "EXPANSION_PLAN.md §5)",
    },
    "calendar": {
        "market_sessions": "union of dates in data/prices_e2.parquet from "
                           "2014-01-01; a guard asserts every retained "
                           "session carries >= 50 priced CIKs",
        "post_close_cutoff_et_hour": 16,
        "news_session": "first session >= info_date (pre-close) / > info_date "
                        "(post-close); info_date = max(filing_date, "
                        "acceptance_date_ET)",
    },
    "surprise": {
        "name": "SUE (standardized unexpected earnings), seasonal random walk",
        "eps_concepts_priority": [
            "EarningsPerShareDiluted",
            "EarningsPerShareBasicAndDiluted",
            "NetIncomeLossNetOfTaxPerOutstandingLimitedPartnershipUnitDiluted",
        ],
        "eps_concept_choice": "per CIK, the listed concept with the most "
                              "distinct quarterly period_ends; a CIK never "
                              "mixes concepts",
        "quarterly_duration_days": [80, 100],
        "unit_filter": "unit endswith '/shares'",
        "value_rule": "as-originally-reported = earliest `filed` row for the "
                      "(cik, period_end), ties broken by smallest "
                      "accession_number; never a restatement",
        "announced_quarter": "the largest period_end in [event_date - 120d, "
                             "event_date - 5d]",
        "seasonal_lag_match_days": [320, 410],
        "formula": "SUE = (EPS_q - EPS_{q-4}) / sd(dEPS over the trailing "
                   "MAX_TRAILING quarters), dEPS_p = EPS_p - EPS_{p-4}",
        "max_trailing": 8,
        "min_trailing": 6,
        "trailing_sd_ddof": 1,
        "pit_rule": "EPS_{q-4} and every quarter entering the trailing sd "
                    "must have first_filed STRICTLY < event_date; the "
                    "announced quarter's own value is contemporaneous "
                    "(public in the release at info_date) and is exempt, "
                    "which is the documented caveat",
    },
    "t1_announcement_window": {
        "primary": "1-session: close(news_session) / close(pre_session) - 1",
        "secondary": "2-session: close(news_session + 1) / close(pre_session) - 1",
        "adjustment": "benchmark-adjusted: minus the equal-weighted mean of "
                      "the SAME-window return over that session's universe "
                      "members EXCLUDING self (EXPANSION_PLAN.md §3.3 "
                      "proposal, pending G3)",
        "raw_also_reported": True,
        "min_benchmark_members": 20,
    },
    "t2_forward_window": {
        "holding_trading_days": 63,
        "entry_primary": "news_session + 1 sessions",
        "entry_skip1_sensitivity": "news_session + 2 sessions",
        "target": "subject 63-session return minus the equal-weighted mean "
                  "63-session return over that entry session's members "
                  "EXCLUDING self, membership-dated",
        "momentum": "12-1: close(pre_session - 21) / close(pre_session - 252) "
                    "- 1, computed only from sessions strictly before the "
                    "news session",
    },
    "period_grouping": {
        "unit": "calendar quarter of the event's own session",
        "min_events_per_quarter": 10,
        "purpose": "REPORTING SPREADS ONLY -- not a fold structure, not a "
                   "train/test split, and not a G3 proposal",
    },
    "inference": {
        "primary_statistic": "cross-quarter mean of per-quarter Spearman IC",
        "sd_ddof": 1,
        "block_bootstrap_resamples": 10000,
        "block_bootstrap_unit": "whole calendar quarter",
        "bootstrap_seed": 20260825,
        "pooled_p_note": "pooled p-values are UNADJUSTED for the clustering "
                         "of earnings events in seasons and are therefore "
                         "anti-conservative; the cross-quarter t and the "
                         "block bootstrap are the honest statistics",
    },
    "verdicts": {
        "T1_pass": "mean IC > 0 AND t >= 4.0 AND >= 75% of quarters positive",
        "T1_fail_meaning": "the PIT / join / date-alignment / benchmark stack "
                           "is broken; E2 is not evaluable and F3 must not "
                           "start until it is fixed",
        "T2_pass": "mean IC > 0 AND t >= 2.0",
        "T2_ambiguous": "|t| < 2.0 (consistent with a decayed anomaly at "
                        "this power -- pre-declared as the modal expectation "
                        "for post-2000 large caps)",
        "T2_fail": "mean IC < 0 AND t <= -2.0",
        "T2_fail_meaning": "a documented anomaly comes out significantly "
                           "BACKWARDS at this configuration -- a "
                           "configuration defect (sign, window, benchmark), "
                           "not a statement about text",
        "T0_pass": "|mean IC| < 0.02 AND |t| < 2.0",
        "T0_fail_meaning": "the machinery manufactures correlation from a "
                           "signal that carries none; every other number "
                           "here is void",
        "implausibility_tripwire": "|mean IC| > 0.15 on ANY control other "
                                   "than T1 => treat as a suspected "
                                   "evaluation bug FIRST and investigate "
                                   "look-ahead before reporting "
                                   "(HANDOFF.md §7 / the standing rule)",
    },
    "placebo": {
        "signal": "uniform in [0,1) from sha256('H1-placebo|<cik>|<date>')",
        "note": "deterministic, reproducible, and by construction independent "
                "of every price and every fundamental",
    },
}

MAX_TRAILING = SPEC["surprise"]["max_trailing"]
MIN_TRAILING = SPEC["surprise"]["min_trailing"]
HOLDING_DAYS = SPEC["t2_forward_window"]["holding_trading_days"]
MIN_BENCHMARK_MEMBERS = SPEC["t1_announcement_window"]["min_benchmark_members"]
MIN_EVENTS_PER_QUARTER = SPEC["period_grouping"]["min_events_per_quarter"]
POST_CLOSE_HOUR_ET = SPEC["calendar"]["post_close_cutoff_et_hour"]
N_BOOTSTRAP = SPEC["inference"]["block_bootstrap_resamples"]
BOOTSTRAP_SEED = SPEC["inference"]["bootstrap_seed"]
PLACEBO_SALT = "H1-placebo"

SPEC_SHA256 = hashlib.sha256(
    json.dumps(SPEC, sort_keys=True).encode("utf-8")
).hexdigest()


# ---------------------------------------------------------------------------
# Loading -- frozen artifacts, read-only, zero network
# ---------------------------------------------------------------------------


def load_membership(db_path: Path = METADATA_DB) -> pd.DataFrame:
    """Dated membership spells. `member_to` NULL/'' means still a member."""
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as con:
        m = pd.read_sql("SELECT cik, sector, stratum, member_from, member_to "
                        "FROM universe_membership", con)
    # Open spells get a far-future sentinel inside pandas' ns range.
    m["member_to"] = m["member_to"].replace("", None).fillna("2200-01-01")
    m["member_from"] = pd.to_datetime(m["member_from"])
    m["member_to"] = pd.to_datetime(m["member_to"])
    return m


def load_earnings_events(db_path: Path = METADATA_DB) -> pd.DataFrame:
    """Item-2.02 8-Ks filed inside the filer's own membership spell.

    `has_earnings_item` is the stored item-2.02 flag. `report_date` is not
    selected: it must never drive a point-in-time decision.
    """
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as con:
        ev = pd.read_sql(
            "SELECT accession_number, cik, form, filing_date, "
            "acceptance_datetime FROM filings WHERE has_earnings_item = 1",
            con,
        )
    ev["filing_date"] = pd.to_datetime(ev["filing_date"])
    m = load_membership(db_path)
    ev = ev.merge(m, on="cik", how="inner")
    ev = ev[(ev["filing_date"] >= ev["member_from"])
            & (ev["filing_date"] < ev["member_to"])].copy()
    return ev.drop(columns=["member_from", "member_to"]).reset_index(drop=True)


def load_price_matrix(prices_path: Path = PRICES_PATH,
                      min_date: str = "2014-01-01") -> pd.DataFrame:
    """Wide close-price matrix: index = market session, columns = cik.

    Forward-filled only INSIDE each CIK's own coverage window; NaN outside.
    See the module docstring, PIT item 4, for why this deliberately differs
    from `features.py::_asof_price`.
    """
    p = pd.read_parquet(prices_path, columns=["cik", "date", "close"])
    p["date"] = pd.to_datetime(p["date"])
    p = p[p["date"] >= pd.Timestamp(min_date)]
    wide = p.pivot_table(index="date", columns="cik", values="close",
                         aggfunc="last").sort_index()
    per_session = wide.notna().sum(axis=1)
    thin = per_session[per_session < 50]
    if len(thin) > 0:
        raise AssertionError(
            f"{len(thin)} market sessions carry < 50 priced CIKs "
            f"(first: {thin.index[0].date()}) -- the union calendar is not "
            "clean enough to treat as a market calendar."
        )
    last_valid = wide.apply(lambda c: c.last_valid_index())
    wide = wide.ffill()
    for cik, last in last_valid.items():
        if last is not None:
            wide.loc[wide.index > last, cik] = np.nan
    return wide


def build_membership_matrix(members: pd.DataFrame,
                            calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """Boolean matrix: index = market session, columns = cik, True where the
    CIK is a universe member on that session (membership-dated)."""
    ciks = sorted(members["cik"].unique())
    mat = pd.DataFrame(False, index=calendar, columns=ciks)
    for row in members.itertuples(index=False):
        mask = (calendar >= row.member_from) & (calendar < row.member_to)
        mat.loc[mask, row.cik] = True
    return mat


def load_quarterly_eps(path: Path = FUNDAMENTALS_PATH) -> pd.DataFrame:
    """As-originally-reported quarterly EPS per (cik, period_end).

    Columns: cik, period_end, eps, first_filed, concept.
    """
    f = pd.read_parquet(path, columns=["cik", "concept", "unit", "value",
                                       "period_start", "period_end", "form",
                                       "accession_number", "filed"])
    fam = SPEC["surprise"]["eps_concepts_priority"]
    e = f[f["concept"].isin(fam) & f["unit"].astype(str).str.endswith("/shares")].copy()
    e["period_start"] = pd.to_datetime(e["period_start"])
    e["period_end"] = pd.to_datetime(e["period_end"])
    e["filed"] = pd.to_datetime(e["filed"])
    dur = (e["period_end"] - e["period_start"]).dt.days
    lo, hi = SPEC["surprise"]["quarterly_duration_days"]
    e = e[(dur >= lo) & (dur <= hi)]

    # One EPS concept per CIK: the one covering the most distinct quarters,
    # ties broken by the declared priority order.
    prio = {c: i for i, c in enumerate(fam)}
    cnt = (e.groupby(["cik", "concept"])["period_end"].nunique()
             .reset_index(name="n_quarters"))
    cnt["prio"] = cnt["concept"].map(prio)
    cnt = cnt.sort_values(["cik", "n_quarters", "prio"],
                          ascending=[True, False, True])
    chosen = cnt.groupby("cik").head(1)[["cik", "concept"]]
    e = e.merge(chosen, on=["cik", "concept"], how="inner")

    e = e.sort_values(["cik", "period_end", "filed", "accession_number"])
    first = e.groupby(["cik", "period_end"], as_index=False).head(1)
    out = first[["cik", "period_end", "value", "filed", "concept"]].rename(
        columns={"value": "eps", "filed": "first_filed"})
    return out.sort_values(["cik", "period_end"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Session alignment -- the post-close acceptance handling lives here
# ---------------------------------------------------------------------------


def resolve_sessions(events: pd.DataFrame,
                     calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """Attach info_date, post_close, news_pos, pre_pos to each event.

    Rows whose news session falls outside the calendar get news_pos = -1 and
    are dropped downstream WITH A COUNT, never silently.
    """
    out = events.copy()
    acc = pd.to_datetime(out["acceptance_datetime"], utc=True, format="mixed")
    acc_et = acc.dt.tz_convert("America/New_York")
    out["acceptance_et"] = acc_et
    out["post_close"] = (acc_et.dt.hour >= POST_CLOSE_HOUR_ET).fillna(True)
    acc_date = acc_et.dt.tz_localize(None).dt.normalize()
    # max() also covers the Salesforce filing_date-precedes-acceptance case.
    out["info_date"] = np.maximum(out["filing_date"].values, acc_date.values)

    info = out["info_date"].values
    news_pos = np.where(
        out["post_close"].values,
        calendar.searchsorted(info, side="right"),
        calendar.searchsorted(info, side="left"),
    )
    news_pos = np.where(news_pos >= len(calendar), -1, news_pos)
    news_pos = np.where(news_pos <= 0, -1, news_pos)  # need a pre-session too
    out["news_pos"] = news_pos
    out["pre_pos"] = np.where(news_pos > 0, news_pos - 1, -1)
    return out


# ---------------------------------------------------------------------------
# Earnings surprise (SUE)
# ---------------------------------------------------------------------------


def _seasonal_diffs(eps_q: pd.DataFrame) -> pd.DataFrame:
    """Attach the q-4 counterpart (matched on period_end lag window) and the
    seasonal difference, for one CIK's quarterly EPS series."""
    lo, hi = SPEC["surprise"]["seasonal_lag_match_days"]
    pe = eps_q["period_end"].values.astype("datetime64[D]").astype(int)
    n = len(eps_q)
    lag_idx = np.full(n, -1, dtype=int)
    for i in range(n):
        gap = pe[i] - pe[:i]
        ok = np.where((gap >= lo) & (gap <= hi))[0]
        if len(ok) > 0:
            # closest to a 365-day lag
            lag_idx[i] = ok[np.argmin(np.abs(gap[ok] - 365))]
    out = eps_q.copy().reset_index(drop=True)
    out["lag_idx"] = lag_idx
    vals = out["eps"].values
    filed = out["first_filed"].values
    out["eps_lag4"] = np.where(lag_idx >= 0, vals[lag_idx], np.nan)
    out["lag4_first_filed"] = pd.to_datetime(
        np.where(lag_idx >= 0, filed[lag_idx], np.datetime64("NaT")))
    out["deps"] = out["eps"] - out["eps_lag4"]
    return out


def build_sue(events: pd.DataFrame, eps: pd.DataFrame) -> pd.DataFrame:
    """SUE per event, PIT-clean in the scaler and the seasonal comparison.

    Returns the event frame with sue, sue_eps, sue_period_end,
    sue_first_filed, sue_n_trailing, sue_sd added (NaN where unbuildable).
    """
    by_cik = {cik: _seasonal_diffs(g) for cik, g in eps.groupby("cik")}
    rows = []
    for ev in events.itertuples(index=False):
        g = by_cik.get(ev.cik)
        rec = {"sue": np.nan, "sue_eps": np.nan, "sue_period_end": pd.NaT,
               "sue_first_filed": pd.NaT, "sue_n_trailing": 0,
               "sue_sd": np.nan, "sue_strict_pit": False}
        if g is None:
            rows.append(rec)
            continue
        ev_date = pd.Timestamp(ev.info_date)
        lo = ev_date - pd.Timedelta(days=120)
        hi = ev_date - pd.Timedelta(days=5)
        cand = g[(g["period_end"] >= lo) & (g["period_end"] <= hi)]
        if cand.empty:
            rows.append(rec)
            continue
        q = cand.iloc[-1]  # largest period_end in window
        if not np.isfinite(q["deps"]):
            rows.append(rec)
            continue
        # PIT: the year-ago comparison must have been public before the event.
        if not (pd.notna(q["lag4_first_filed"]) and q["lag4_first_filed"] < ev_date):
            rows.append(rec)
            continue
        # PIT: the trailing scaler uses only quarters whose OWN value and
        # whose q-4 counterpart were both filed strictly before the event.
        prior = g[(g["period_end"] < q["period_end"])
                  & g["deps"].notna()
                  & (g["first_filed"] < ev_date)
                  & (g["lag4_first_filed"] < ev_date)]
        prior = prior.tail(MAX_TRAILING)
        if len(prior) < MIN_TRAILING:
            rows.append(rec)
            continue
        sd = float(prior["deps"].std(ddof=SPEC["surprise"]["trailing_sd_ddof"]))
        if not np.isfinite(sd) or sd <= 0:
            rows.append(rec)
            continue
        rec.update({
            "sue": float(q["deps"]) / sd,
            "sue_eps": float(q["eps"]),
            "sue_period_end": q["period_end"],
            "sue_first_filed": q["first_filed"],
            "sue_n_trailing": int(len(prior)),
            "sue_sd": sd,
            "sue_strict_pit": bool(q["first_filed"] <= ev_date),
        })
        rows.append(rec)
    return pd.concat([events.reset_index(drop=True),
                      pd.DataFrame(rows)], axis=1)


# ---------------------------------------------------------------------------
# Returns -- announcement window (T1) and forward excess window (T2)
# ---------------------------------------------------------------------------


def align_membership(member_mat: pd.DataFrame,
                     price_columns: pd.Index) -> np.ndarray:
    """Boolean array (n_sessions x n_price_ciks) aligned to the price
    matrix's columns. CIKs that are members but carry no price data are
    simply absent -- they are counted separately as censored, never imputed.
    """
    return (member_mat.reindex(columns=price_columns).fillna(False)
            .to_numpy(dtype=bool))


def excess_return(price_arr: np.ndarray, cik_positions: dict,
                  member_arr: np.ndarray, cik: int, start_pos: int,
                  end_pos: int,
                  member_session_pos: int) -> tuple[float, float, int, int]:
    """(subject_return, benchmark_avg, n_members_used, n_members_no_price).

    Benchmark = equal-weighted mean over that session's members EXCLUDING
    self, over the identical window. Members without real price coverage on
    both endpoints are counted and excluded, never imputed.
    """
    p0 = price_arr[start_pos]
    p1 = price_arr[end_pos]
    with np.errstate(divide="ignore", invalid="ignore"):
        rets = np.where((p0 > 0) & np.isfinite(p0) & np.isfinite(p1),
                        p1 / p0 - 1.0, np.nan)
    peers = member_arr[member_session_pos].copy()
    col = cik_positions.get(cik)
    subj = float(rets[col]) if col is not None else np.nan
    if col is not None:
        peers[col] = False
    n_members = int(peers.sum())
    peer_rets = rets[peers]
    valid = np.isfinite(peer_rets)
    n_used = int(valid.sum())
    bench = float(peer_rets[valid].mean()) if n_used > 0 else np.nan
    return subj, bench, n_used, n_members - n_used


def attach_returns(events: pd.DataFrame, prices: pd.DataFrame,
                   member_mat: pd.DataFrame) -> pd.DataFrame:
    """Attach every window this module needs, in one pass over events."""
    n_sessions = len(prices.index)
    price_arr = prices.to_numpy(dtype=float)
    member_arr = align_membership(member_mat, prices.columns)
    cik_positions = {c: i for i, c in enumerate(prices.columns)}
    recs = []
    for ev in events.itertuples(index=False):
        r = {
            "ann_ret_1d": np.nan, "ann_bench_1d": np.nan, "ann_excess_1d": np.nan,
            "ann_ret_2d": np.nan, "ann_bench_2d": np.nan, "ann_excess_2d": np.nan,
            "fwd_ret": np.nan, "fwd_bench": np.nan, "fwd_excess": np.nan,
            "fwd_ret_skip1": np.nan, "fwd_excess_skip1": np.nan,
            "mom_12_1": np.nan,
            "n_bench_used_ann": 0, "n_bench_missing_ann": 0,
            "n_bench_used_fwd": 0, "n_bench_missing_fwd": 0,
            "news_date": pd.NaT, "entry_date": pd.NaT, "exit_date": pd.NaT,
        }
        np_ = int(ev.news_pos)
        pp = int(ev.pre_pos)
        if np_ < 1:
            recs.append(r)
            continue
        r["news_date"] = prices.index[np_]

        # --- T1: announcement windows, benchmark-adjusted, membership at the
        # news session.
        s, b, used, miss = excess_return(price_arr, cik_positions, member_arr,
                                         ev.cik, pp, np_, np_)
        r["ann_ret_1d"], r["ann_bench_1d"] = s, b
        r["n_bench_used_ann"], r["n_bench_missing_ann"] = used, miss
        if np.isfinite(s) and np.isfinite(b) and used >= MIN_BENCHMARK_MEMBERS:
            r["ann_excess_1d"] = s - b
        if np_ + 1 < n_sessions:
            s2, b2, used2, _ = excess_return(price_arr, cik_positions,
                                             member_arr, ev.cik, pp, np_ + 1, np_)
            r["ann_ret_2d"], r["ann_bench_2d"] = s2, b2
            if np.isfinite(s2) and np.isfinite(b2) and used2 >= MIN_BENCHMARK_MEMBERS:
                r["ann_excess_2d"] = s2 - b2

        # --- T2: forward 63-session excess return, entry strictly after the
        # session in which the news was first impounded.
        entry = np_ + 1
        exit_ = entry + HOLDING_DAYS
        if exit_ < n_sessions:
            r["entry_date"] = prices.index[entry]
            r["exit_date"] = prices.index[exit_]
            s3, b3, used3, miss3 = excess_return(price_arr, cik_positions,
                                                 member_arr, ev.cik,
                                                 entry, exit_, entry)
            r["fwd_ret"], r["fwd_bench"] = s3, b3
            r["n_bench_used_fwd"], r["n_bench_missing_fwd"] = used3, miss3
            if np.isfinite(s3) and np.isfinite(b3) and used3 >= MIN_BENCHMARK_MEMBERS:
                r["fwd_excess"] = s3 - b3
        entry1 = np_ + 2
        exit1 = entry1 + HOLDING_DAYS
        if exit1 < n_sessions:
            s4, b4, used4, _ = excess_return(price_arr, cik_positions,
                                             member_arr, ev.cik,
                                             entry1, exit1, entry1)
            r["fwd_ret_skip1"] = s4
            if np.isfinite(s4) and np.isfinite(b4) and used4 >= MIN_BENCHMARK_MEMBERS:
                r["fwd_excess_skip1"] = s4 - b4

        # --- 12-1 momentum, measured entirely on sessions before the news.
        col = cik_positions.get(ev.cik)
        if pp - 252 >= 0 and col is not None:
            p_start = price_arr[pp - 252, col]
            p_end = price_arr[pp - 21, col]
            if np.isfinite(p_start) and np.isfinite(p_end) and p_start > 0:
                r["mom_12_1"] = float(p_end / p_start - 1.0)
        recs.append(r)
    return pd.concat([events.reset_index(drop=True), pd.DataFrame(recs)], axis=1)


def placebo_signal(ciks, dates) -> np.ndarray:
    """Deterministic uniform[0,1) independent of every price and fundamental."""
    out = np.empty(len(ciks), dtype=float)
    for i, (c, d) in enumerate(zip(ciks, dates)):
        key = f"{PLACEBO_SALT}|{int(c)}|{pd.Timestamp(d).date()}".encode()
        h = hashlib.sha256(key).digest()
        out[i] = int.from_bytes(h[:8], "big") / float(1 << 64)
    return out


# ---------------------------------------------------------------------------
# IC machinery -- per-period spreads, cross-period mean, block bootstrap
# ---------------------------------------------------------------------------


def per_period_ic(df: pd.DataFrame, signal: str, target: str,
                  period_col: str) -> pd.DataFrame:
    rows = []
    sub = df[df[signal].notna() & df[target].notna()]
    for period, g in sub.groupby(period_col, sort=True):
        if len(g) < MIN_EVENTS_PER_QUARTER:
            continue
        x = g[signal].values.astype(float)
        y = g[target].values.astype(float)
        if np.std(x) == 0 or np.std(y) == 0:
            continue
        ic, p = spearmanr(x, y)
        rows.append({"period": str(period), "n": len(g),
                     "ic": float(ic), "p": float(p)})
    return pd.DataFrame(rows)


def summarize_ic(ic_df: pd.DataFrame, df: pd.DataFrame, signal: str,
                 target: str) -> dict:
    """Cross-period mean with ddof=1 SE, positive-period share, block
    bootstrap over whole periods, and the pooled (anti-conservative) IC."""
    if len(ic_df) == 0:
        return {"n_periods": 0}
    ics = ic_df["ic"].values.astype(float)
    k = len(ics)
    mean = float(ics.mean())
    sd = float(ics.std(ddof=1)) if k > 1 else float("nan")
    se = sd / np.sqrt(k) if k > 1 else float("nan")
    t = mean / se if se and np.isfinite(se) and se > 0 else float("nan")

    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = rng.integers(0, k, size=(N_BOOTSTRAP, k))
    boot = ics[draws].mean(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])

    sub = df[df[signal].notna() & df[target].notna()]
    pooled_ic, pooled_p = spearmanr(sub[signal].values.astype(float),
                                    sub[target].values.astype(float))
    return {
        "n_periods": int(k),
        "n_events_total": int(len(sub)),
        "mean_ic": mean,
        "sd_ic_ddof1": sd,
        "se_ic": float(se) if np.isfinite(se) else None,
        "t_stat": float(t) if np.isfinite(t) else None,
        "frac_periods_positive": float((ics > 0).mean()),
        "n_periods_positive": int((ics > 0).sum()),
        "block_bootstrap_ci95": [float(lo), float(hi)],
        "min_period_ic": float(ics.min()),
        "max_period_ic": float(ics.max()),
        "pooled_ic": float(pooled_ic),
        "pooled_p_anticonservative": float(pooled_p),
        "per_period": ic_df.to_dict(orient="records"),
    }


def verdict_t1(s: dict) -> str:
    if not s.get("n_periods"):
        return "FAIL (no evaluable periods)"
    ok = (s["mean_ic"] > 0 and (s["t_stat"] or 0) >= 4.0
          and s["frac_periods_positive"] >= 0.75)
    return "PASS" if ok else "FAIL"


def verdict_t2(s: dict) -> str:
    if not s.get("n_periods"):
        return "FAIL (no evaluable periods)"
    t = s["t_stat"] or 0.0
    if s["mean_ic"] > 0 and t >= 2.0:
        return "PASS"
    if s["mean_ic"] < 0 and t <= -2.0:
        return "FAIL"
    return "AMBIGUOUS"


def verdict_t0(s: dict) -> str:
    if not s.get("n_periods"):
        return "FAIL (no evaluable periods)"
    return ("PASS" if abs(s["mean_ic"]) < 0.02 and abs(s["t_stat"] or 0) < 2.0
            else "FAIL")


def tripwire(s: dict) -> bool:
    """True when a result is implausibly large and must be treated as a
    suspected evaluation bug before it is reported."""
    return bool(s.get("n_periods")) and abs(s["mean_ic"]) > 0.15


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def build_panel() -> tuple[pd.DataFrame, dict]:
    """The one event panel both controls run on, plus population diagnostics."""
    events = load_earnings_events()
    prices = load_price_matrix()
    members = load_membership()
    member_mat = build_membership_matrix(members, prices.index)

    diag = {
        "n_earnings_8k_in_membership": int(len(events)),
        "n_ciks_in_membership": int(events["cik"].nunique()),
    }
    priced = set(prices.columns)
    events = events[events["cik"].isin(priced)].copy()
    diag["n_events_with_price_coverage"] = int(len(events))
    diag["n_ciks_with_price_coverage"] = int(events["cik"].nunique())
    diag["n_events_dropped_no_price_cik"] = (
        diag["n_earnings_8k_in_membership"] - diag["n_events_with_price_coverage"])

    events = resolve_sessions(events, prices.index)
    diag["post_close_share"] = float(events["post_close"].mean())
    diag["n_post_close"] = int(events["post_close"].sum())
    diag["n_acceptance_date_after_filing_date"] = int(
        (events["info_date"] > events["filing_date"]).sum())
    diag["n_events_no_session"] = int((events["news_pos"] < 1).sum())
    events = events[events["news_pos"] >= 1].copy()

    eps = load_quarterly_eps()
    diag["n_eps_firm_quarters"] = int(len(eps))
    diag["n_eps_ciks"] = int(eps["cik"].nunique())

    events = build_sue(events, eps)
    events = attach_returns(events, prices, member_mat)

    events["period"] = events["news_date"].dt.to_period("Q").astype(str)
    events["fwd_period"] = events["entry_date"].dt.to_period("Q").astype(str)
    events["placebo"] = placebo_signal(events["cik"].values,
                                       events["news_date"].values)

    # Shipped dedup rule, imported read-only. `ticker` is set to the CIK so
    # identity is CIK-keyed (dual-class safety) while the shipped function's
    # column contract is honoured exactly.
    dd = events.assign(ticker=events["cik"].astype(str))
    events["dedup_keep"] = B.company_quarter_dedup_keep_mask(
        dd[["ticker", "filing_date", "form", "accession_number"]]).values

    diag["dedup_gap_days"] = int(B.COMPANY_QUARTER_DEDUP_GAP_DAYS)
    diag["n_dedup_kept"] = int(events["dedup_keep"].sum())
    diag["n_dedup_dropped"] = int((~events["dedup_keep"]).sum())
    diag["n_sue_available"] = int(events["sue"].notna().sum())
    diag["n_sue_strict_pit"] = int(events["sue_strict_pit"].sum())
    diag["n_ann_excess_1d"] = int(events["ann_excess_1d"].notna().sum())
    diag["n_fwd_excess"] = int(events["fwd_excess"].notna().sum())
    diag["n_mom"] = int(events["mom_12_1"].notna().sum())
    lag_days = (events["sue_first_filed"] - events["info_date"]).dt.days
    diag["sue_first_filed_minus_event_days"] = {
        "median": float(lag_days.median()),
        "p10": float(lag_days.quantile(0.10)),
        "p90": float(lag_days.quantile(0.90)),
        "n_negative_or_zero": int((lag_days <= 0).sum()),
    }
    diag["benchmark_members_used_ann"] = {
        "median": float(events["n_bench_used_ann"].median()),
        "min": int(events["n_bench_used_ann"].min()),
        "max": int(events["n_bench_used_ann"].max()),
    }
    diag["benchmark_member_cells_dropped_no_price"] = {
        "ann_total": int(events["n_bench_missing_ann"].sum()),
        "fwd_total": int(events["n_bench_missing_fwd"].sum()),
    }
    assert_no_lookahead(events)
    return events, diag


def assert_no_lookahead(events: pd.DataFrame) -> None:
    """Hard invariants. Any violation is a leakage bug, not a warning."""
    ok = events["news_date"].notna()
    bad = events.loc[ok & (events["news_date"] < events["info_date"])]
    if len(bad):
        raise AssertionError(
            f"{len(bad)} events have news_date < info_date -- session "
            "alignment is broken.")
    post = events.loc[ok & events["post_close"]]
    bad2 = post[post["news_date"] <= post["info_date"]]
    if len(bad2):
        raise AssertionError(
            f"{len(bad2)} post-close events have news_date <= info_date -- "
            "the post-close acceptance correction is not being applied.")
    ent = events["entry_date"].notna()
    bad3 = events.loc[ent & (events["entry_date"] <= events["news_date"])]
    if len(bad3):
        raise AssertionError(
            f"{len(bad3)} events have entry_date <= news_date -- the forward "
            "window opens on or before the session that impounded the news.")
    sue = events["sue"].notna()
    bad4 = events.loc[sue & (events["sue_period_end"] >= events["info_date"])]
    if len(bad4):
        raise AssertionError(
            f"{len(bad4)} events use a fiscal quarter ending on or after the "
            "event date.")


def run_control(events: pd.DataFrame, signal: str, target: str,
                period_col: str) -> dict:
    """Both bases, always: dedup primary + raw beside it."""
    dd = events[events["dedup_keep"]]
    out = {}
    for label, frame in (("dedup", dd), ("raw", events)):
        ic_df = per_period_ic(frame, signal, target, period_col)
        out[label] = summarize_ic(ic_df, frame, signal, target)
    return out


# ---------------------------------------------------------------------------
# POST-HOC DIAGNOSTICS
#
# READ THIS LABEL BEFORE READING ANY NUMBER BELOW. Everything in this section
# was written AFTER the pre-declared T1 arm was run and came in under its
# pre-declared bar. It exists to answer "which component fell short," which is
# the standing rule applied in reverse: a control that misses its expected
# magnitude gets the evaluation stack investigated before any conclusion is
# drawn about the world.
#
# These arms CANNOT and DO NOT overturn a pre-declared verdict. `verdicts` in
# the results JSON is computed from the pre-declared arms only. Any spec
# change they motivate must be pre-registered at G3 before it is used in a
# confirmatory run.
# ---------------------------------------------------------------------------


def diag_event_date_alignment(events: pd.DataFrame,
                              prices: pd.DataFrame) -> dict:
    """Does the session we call `news_session` actually carry the news?

    Independent of any surprise proxy: compares |return| on the pre / news /
    news+1 sessions to the same CIK's own trailing baseline (sessions
    t-30..t-10). A correctly identified announcement session must show a
    sharp, LOCALIZED volatility spike. Split by post_close, because that is
    the convention under test.
    """
    parr = prices.to_numpy(dtype=float)
    rets = np.full_like(parr, np.nan)
    rets[1:] = parr[1:] / parr[:-1] - 1.0
    pos = {c: i for i, c in enumerate(prices.columns)}
    rows = []
    for ev in events.itertuples(index=False):
        c = pos.get(ev.cik)
        n = int(ev.news_pos)
        if c is None or n < 31 or n + 2 >= len(parr):
            continue
        window = np.abs(rets[n - 30:n - 9, c])
        if np.all(np.isnan(window)):
            continue
        base = float(np.nanmedian(window))
        if not np.isfinite(base) or base <= 0:
            continue
        rows.append({
            "post_close": bool(ev.post_close),
            "pre": abs(rets[n - 1, c]) / base,
            "news": abs(rets[n, c]) / base,
            "next": abs(rets[n + 1, c]) / base,
        })
    d = pd.DataFrame(rows).dropna()

    def _med(frame):
        return {k: float(frame[k].median()) for k in ("pre", "news", "next")}

    return {
        "what_it_tests": "whether the identified news session is where the "
                         "information actually lands, independent of the "
                         "surprise proxy",
        "metric": "median |session return| / that CIK's own median |return| "
                  "over sessions t-30..t-10",
        "n_events": int(len(d)),
        "all_events": _med(d),
        "post_close_events": _med(d[d["post_close"]]),
        "pre_close_events": _med(d[~d["post_close"]]),
    }


def diag_post_close_convention(events: pd.DataFrame,
                               prices: pd.DataFrame) -> dict:
    """Is the post-close acceptance correction right, empirically?

    For each event, computes the 1-session return on session D (the NAIVE
    rule: first session >= info_date, i.e. what a harness that ignores
    acceptance time would use) and on session D+1, and correlates each with
    SUE, split by post_close. If the correction is right, post-close events'
    surprise should track D+1 and NOT D; pre-close events the reverse.
    """
    cal = prices.index
    parr = prices.to_numpy(dtype=float)
    pos = {c: i for i, c in enumerate(prices.columns)}
    naive = cal.searchsorted(events["info_date"].values, side="left")
    naive = np.where((naive > 0) & (naive < len(cal) - 1), naive, -1)

    def _ret(cik, a, b):
        c = pos.get(cik)
        if c is None or a < 0 or b < 0 or b >= len(cal):
            return np.nan
        p0, p1 = parr[a, c], parr[b, c]
        if not (np.isfinite(p0) and np.isfinite(p1) and p0 > 0):
            return np.nan
        return p1 / p0 - 1.0

    df = events.copy()
    df["naive_pos"] = naive
    df["ret_D"] = [_ret(r.cik, r.naive_pos - 1, r.naive_pos)
                   for r in df.itertuples(index=False)]
    df["ret_D1"] = [_ret(r.cik, r.naive_pos, r.naive_pos + 1)
                    for r in df.itertuples(index=False)]
    out = {
        "what_it_tests": "whether the 16:00 ET acceptance cutoff correctly "
                         "moves the reaction session, measured rather than "
                         "assumed",
        "naive_rule": "session D = first session >= info_date (a harness "
                      "that ignores acceptance time)",
    }
    sub = df[(df["stratum"] == "core") & df["sue"].notna()]
    for flag, label in ((True, "post_close_events"), (False, "pre_close_events")):
        g = sub[sub["post_close"] == flag]
        block = {"n": int(len(g))}
        for col, key in (("ret_D", "sue_vs_session_D"),
                         ("ret_D1", "sue_vs_session_D_plus_1")):
            gg = g[g[col].notna()]
            ic, p = spearmanr(gg["sue"].values, gg[col].values)
            block[key] = {"n": int(len(gg)), "pooled_ic": float(ic),
                          "pooled_p_anticonservative": float(p)}
        out[label] = block
    return out


def diag_stale_quarter_arm(events: pd.DataFrame) -> dict:
    """The one construction defect the pre-declared spec contains.

    SPEC picks the announced quarter as the largest `period_end` in
    [event - 120d, event - 5d]. Many filers never tag a 90-day Q4 fact (they
    tag the fiscal year only), so a Q4 earnings 8-K silently matches the
    STALE Q3 surprise. This arm reports the affected share and re-runs T1 and
    T2a with those events removed.

    This is a spec DEFECT, not a tuning knob: matching an announcement to a
    quarter that was already public months earlier is wrong under any
    reading. But it was found by looking at the data, so it is reported here
    and NOT folded into the pre-declared verdict.
    """
    ev = events.copy()
    ev["gap_days"] = (ev["info_date"] - ev["sue_period_end"]).dt.days
    have = ev["sue"].notna()
    stale = have & (ev["gap_days"] > 100)
    fresh = ev[~stale]
    core_all = ev[ev["stratum"] == "core"]
    core_fresh = fresh[fresh["stratum"] == "core"]

    def _arm(frame, signal, target, period):
        f = frame[frame["dedup_keep"]]
        return summarize_ic(per_period_ic(f, signal, target, period),
                            f, signal, target)

    return {
        "what_it_tests": "how much of T1's shortfall is the stale-quarter "
                         "matching defect rather than the harness",
        "n_events_with_sue": int(have.sum()),
        "n_stale_matches": int(stale.sum()),
        "stale_share_of_sue_events": float(stale.sum() / max(1, have.sum())),
        "T1_core_as_declared": _arm(core_all, "sue", "ann_excess_1d", "period"),
        "T1_core_stale_removed": _arm(core_fresh, "sue", "ann_excess_1d", "period"),
        "T2a_core_as_declared": _arm(core_all, "sue", "fwd_excess", "fwd_period"),
        "T2a_core_stale_removed": _arm(core_fresh, "sue", "fwd_excess", "fwd_period"),
    }


def diag_announcement_response_by_quintile(events: pd.DataFrame) -> dict:
    """Descriptive effect size for T1 in return units.

    CHARTER NOTE: this is the CONTEMPORANEOUS, already-realized, in-sample
    reaction of the announcement session itself, sorted by a surprise that
    was public at that same moment. It is a description of what happened in
    an event window. It is NOT a forecast, NOT an expected return, NOT
    achievable by anyone, and NOT a strategy. No equivalent table is produced
    for T2's forward window, deliberately.
    """
    g = events[(events["stratum"] == "core") & events["dedup_keep"]
               & events["sue"].notna() & events["ann_excess_1d"].notna()].copy()
    g["quintile"] = g.groupby("period")["sue"].transform(
        lambda s: pd.qcut(s.rank(method="first"), 5, labels=False,
                          duplicates="drop"))
    tab = g.groupby("quintile")["ann_excess_1d"].agg(["mean", "median", "count"])
    return {
        "what_it_is": "contemporaneous announcement-session excess response "
                      "by within-quarter SUE quintile (descriptive only)",
        "by_quintile_pct": {int(k): {"mean_pct": float(v["mean"] * 100),
                                     "median_pct": float(v["median"] * 100),
                                     "n": int(v["count"])}
                            for k, v in tab.iterrows()},
        "top_minus_bottom_mean_pct": float(
            (g.loc[g["quintile"] == tab.index.max(), "ann_excess_1d"].mean()
             - g.loc[g["quintile"] == tab.index.min(), "ann_excess_1d"].mean()) * 100),
    }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def provenance() -> dict:
    """Exactly what produced a given set of numbers.

    `backtest.py` is under concurrent edit by hardening item H2, so the
    dedup rule this module imports is pinned by the sha of the FUNCTION
    SOURCE, not of the whole file -- unrelated H2 edits then cannot silently
    invalidate a reproduction.
    """
    import inspect
    dedup_src = inspect.getsource(B.company_quarter_dedup_keep_mask) + \
        inspect.getsource(B.assign_company_quarter_clusters)
    return {
        "spec_sha256": SPEC_SHA256,
        "controls_py_sha256": _sha256_file(Path(__file__)),
        "imported_dedup_source_sha256":
            hashlib.sha256(dedup_src.encode("utf-8")).hexdigest(),
        "backtest_py_sha256": _sha256_file(REPO_ROOT / "backtest.py"),
        "inputs": {
            "filings_metadata_e2.db": _sha256_file(METADATA_DB),
            "prices_e2.parquet": _sha256_file(PRICES_PATH),
            "fundamentals_e2.parquet": _sha256_file(FUNDAMENTALS_PATH),
        },
        "artifacts_written": [str(RESULTS_PATH.relative_to(REPO_ROOT))],
        "network_calls": 0,
    }


def mde_from_se(se: float | None) -> float | None:
    """Minimum detectable |IC| at two-sided 5% / 80% power = 2.8 x SE."""
    return None if se is None or not np.isfinite(se) else float(2.8 * se)


def main() -> None:
    events, diag = build_panel()
    core = events[events["stratum"] == "core"]

    results = {
        "spec": SPEC,
        "spec_sha256": SPEC_SHA256,
        "provenance": provenance(),
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "population": diag,
        "controls": {},
    }
    R = results["controls"]

    # ---- T1: contemporaneous announcement response (the plumbing check)
    R["T1_primary_1d_excess_core"] = run_control(core, "sue", "ann_excess_1d", "period")
    R["T1_primary_1d_excess_pooled"] = run_control(events, "sue", "ann_excess_1d", "period")
    R["T1_secondary_2d_excess_core"] = run_control(core, "sue", "ann_excess_2d", "period")
    R["T1_secondary_1d_raw_core"] = run_control(core, "sue", "ann_ret_1d", "period")
    R["T1_extension_1d_excess"] = run_control(
        events[events["stratum"] == "extension"], "sue", "ann_excess_1d", "period")

    # ---- T2a: PEAD at the harness's own forward window and benchmark
    R["T2a_pead_core"] = run_control(core, "sue", "fwd_excess", "fwd_period")
    R["T2a_pead_pooled"] = run_control(events, "sue", "fwd_excess", "fwd_period")
    R["T2a_pead_skip1_core"] = run_control(core, "sue", "fwd_excess_skip1", "fwd_period")
    strict = core[core["sue_strict_pit"]]
    R["T2a_pead_strictpit_core"] = run_control(strict, "sue", "fwd_excess", "fwd_period")

    # ---- T2b: 12-1 momentum on the same panel/target/machinery
    R["T2b_momentum_core"] = run_control(core, "mom_12_1", "fwd_excess", "fwd_period")
    R["T2b_momentum_pooled"] = run_control(events, "mom_12_1", "fwd_excess", "fwd_period")

    # ---- T0: zero-information placebo through the identical machinery
    R["T0_placebo_announcement_core"] = run_control(core, "placebo", "ann_excess_1d", "period")
    R["T0_placebo_forward_core"] = run_control(core, "placebo", "fwd_excess", "fwd_period")

    results["verdicts"] = {
        "T1": verdict_t1(R["T1_primary_1d_excess_core"]["dedup"]),
        "T1_pooled": verdict_t1(R["T1_primary_1d_excess_pooled"]["dedup"]),
        "T2a_pead": verdict_t2(R["T2a_pead_core"]["dedup"]),
        "T2b_momentum": verdict_t2(R["T2b_momentum_core"]["dedup"]),
        "T0_placebo_announcement": verdict_t0(R["T0_placebo_announcement_core"]["dedup"]),
        "T0_placebo_forward": verdict_t0(R["T0_placebo_forward_core"]["dedup"]),
    }
    results["tripwires_fired"] = sorted(
        name for name, v in R.items()
        if not name.startswith("T1") and tripwire(v["dedup"]))

    results["implied_mde_two_sided_5pct_80pct_power"] = {
        name: mde_from_se(v["dedup"].get("se_ic")) for name, v in R.items()
    }

    prices = load_price_matrix()
    results["post_hoc_diagnostics"] = {
        "READ_FIRST": "Written AFTER the pre-declared arms were run, because "
                      "T1 came in under its pre-declared bar. Diagnostic "
                      "only. Does not and cannot change `verdicts`. Any spec "
                      "change motivated here must be pre-registered at G3 "
                      "before a confirmatory run uses it.",
        "D1_event_date_alignment": diag_event_date_alignment(events, prices),
        "D2_post_close_convention": diag_post_close_convention(events, prices),
        "D3_stale_quarter_arm": diag_stale_quarter_arm(events),
        "D4_announcement_response_by_quintile":
            diag_announcement_response_by_quintile(events),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(results, indent=2, default=str))

    print(f"spec sha256: {SPEC_SHA256}")
    print(f"population: {json.dumps(diag, indent=2, default=str)}")
    for name, v in R.items():
        d = v["dedup"]
        if not d.get("n_periods"):
            print(f"{name:38s} -- no evaluable periods")
            continue
        print(f"{name:38s} dedup mean IC {d['mean_ic']:+.4f}  "
              f"sd {d['sd_ic_ddof1']:.4f}  SE {d['se_ic']:.4f}  "
              f"t {d['t_stat']:+.2f}  k={d['n_periods']}  "
              f"pos {d['n_periods_positive']}/{d['n_periods']}  "
              f"n={d['n_events_total']}  "
              f"boot95 [{d['block_bootstrap_ci95'][0]:+.4f}, "
              f"{d['block_bootstrap_ci95'][1]:+.4f}]")
    print(f"verdicts (pre-declared arms only): "
          f"{json.dumps(results['verdicts'], indent=2)}")
    print(f"tripwires fired: {results['tripwires_fired']}")
    pd_ = results["post_hoc_diagnostics"]
    print("post-hoc D1 event-date alignment (median |ret| / own baseline): "
          f"{json.dumps(pd_['D1_event_date_alignment']['all_events'])} "
          f"post-close {json.dumps(pd_['D1_event_date_alignment']['post_close_events'])}")
    d3 = pd_["D3_stale_quarter_arm"]
    print(f"post-hoc D3 stale-quarter matches: {d3['n_stale_matches']} of "
          f"{d3['n_events_with_sue']} "
          f"({d3['stale_share_of_sue_events']:.1%}); T1 core stale-removed "
          f"mean IC {d3['T1_core_stale_removed']['mean_ic']:+.4f} "
          f"t {d3['T1_core_stale_removed']['t_stat']:+.2f} "
          f"pos {d3['T1_core_stale_removed']['n_periods_positive']}/"
          f"{d3['T1_core_stale_removed']['n_periods']}")
    print(f"wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
