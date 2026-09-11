"""
numeric_features_e2.py -- the NUMERIC side of the E2 feature table (F5 Step 1A).

One row per (cik, accession_number) for every core-stratum filing inside its
filer's own membership spell, carrying the 10 E1 numeric fundamentals features
ported to E2 plus the three EXPANSION_PLAN §8 item 4 baseline factors
(momentum, realized volatility, one valuation ratio).

WHAT THIS MODULE DOES NOT DO (F5_PLAN §1, the freeze): it computes no
information coefficient, no correlation, and no feature-versus-outcome
association of any kind. It never reads a target/return column. It is a
feature builder and nothing else.

-----------------------------------------------------------------------
Point-in-time discipline (the whole point of the file)
-----------------------------------------------------------------------
1. The as-of date for every fundamentals lookup is the filing's
   `info_date = max(filing_date, acceptance_datetime_ET_date)` -- never
   `report_date`, which is not selected from the DB at all.
2. Fundamentals are read ONLY through `pit.value_as_of()` (filed <= as_of,
   then the latest-filed row for the freshest knowable period). A
   latest-value groupby is prohibited and would be wrong: MEASURED on
   `data/fundamentals_e2.parquet`, 20,027 / 273,268 = 7.33% of
   (cik, concept, unit, period_start, period_end) groups carry more than one
   distinct value -- restatements. `test_numeric_features_e2.py` pins both
   that census and the as-of behaviour (a restatement filed after info_date
   must not be visible).
3. The price factors are computed on sessions STRICTLY BEFORE the filing's
   news session. Sessions come from `controls.resolve_sessions()` (imported,
   not re-implemented): post-close acceptance (>= 16:00 ET) pushes the news
   session forward one, `pre_session = news_session - 1`, and every window
   ends at `pre_session`.

-----------------------------------------------------------------------
Concept resolution -- no hand-typed per-company tags, ever
-----------------------------------------------------------------------
Which XBRL tag carries a company's revenue / equity / cash / ... is decided
by F2's alias-migration classifier, already run and committed at
`data/f2/concept_resolution.csv` (see `ingest_fundamentals.py`,
"Concept families and the alias/migration problem" and `classify_family()`).
This module consumes that outcome and nothing else:

  * severity `resolved` (SINGLE / MIGRATION / DOMINANT) -> use the tag(s) in
    the `tags` column, in the order the classifier recorded them;
  * severity `UNRESOLVED` (OVERLAP / PARTIAL / ABSENT) -> every feature that
    needs the family is NaN for that company, and the (cik, family) pair is
    written to `data/f5/numeric_unresolved_e2.csv` with its state, coverage
    and the features it nulls. It fails loudly, per pair. There is no
    fallback tag, no "most rows wins", and no per-company override map --
    that is exactly E1's failure mode (JNJ operating income frozen at 2015).

`resolve_family_value()` below is a CIK-keyed, taxonomy-aware port of
`features.resolve_concept_family()` (E1, frozen). Two deliberate differences,
both forced and both tested:
  * it filters on `cik` only (E2 is CIK-keyed end to end; E2 labels and 31
    member companies carry no ticker), and
  * it takes the taxonomy from the tag's own family, because one E2 family
    (`shares_outstanding`) lives in `dei`, not `us-gaap`, which E1's
    hard-coded `taxonomy="us-gaap"` cannot express.
`test_numeric_features_e2.py::test_port_matches_e1_resolver` pins that the
port agrees with the frozen E1 function wherever E1 can express the case.

-----------------------------------------------------------------------
Constants: ported, and re-measured on E2 rather than assumed
-----------------------------------------------------------------------
`STALENESS_MAX_DAYS = 200`, `end_tolerance_days = 45` and
`duration_tolerance_days = 20` are E1 values justified against E1's 25
mega-caps. They are IMPORTED from `features.py` unchanged (retuning a
pre-registration input is a G3 decision, not this module's), and the run
re-measures on E2 what they actually do -- the days-stale distribution of
every resolved candidate, the count and family breakdown of facts the guard
discards, and the |period_end - target| distribution of the YoY matches --
and writes those numbers into the manifest. They are reported, not assumed.

-----------------------------------------------------------------------
Currency (FX is G3 decision 7, NOT ratified; this run makes no FX call)
-----------------------------------------------------------------------
One core member reports in CAD (CIK 895728, 13 resolved families). Ratio and
growth features are currency-invariant when numerator and denominator share a
currency, so they are computed and the unit pair is asserted to match. The two
currency-SENSITIVE columns -- `log_total_assets` (a level) and
`book_to_market` (a CAD numerator over a USD-priced denominator) -- are NaN
for non-USD reporters, counted, and flagged as an open question for G3. No
rate is fabricated; $0, no network.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

import controls as C
import features as F1
from ingest_fundamentals import CONCEPT_FAMILIES, is_operating_form
from pit import value_as_of

REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
F5_DIR = DATA_DIR / "f5"

METADATA_DB = DATA_DIR / "filings_metadata_e2.db"
PRICES_PATH = DATA_DIR / "prices_e2.parquet"
FUNDAMENTALS_PATH = DATA_DIR / "fundamentals_e2.parquet"
CONCEPT_RESOLUTION_CSV = DATA_DIR / "f2" / "concept_resolution.csv"
# The committed record carrying sha256 for all three E2 inputs (controls.py's
# `provenance()` block). Every read below is asserted against it.
SHA_REFERENCE = DATA_DIR / "hardening" / "controls_results.json"

OUTPUT_PARQUET = F5_DIR / "numeric_features_e2.parquet"
OUTPUT_MANIFEST = F5_DIR / "numeric_features_e2_manifest.json"
OUTPUT_UNRESOLVED = F5_DIR / "numeric_unresolved_e2.csv"
# The run's status report (written by hand from this run's diagnostics):
# data/f5/status/STEP1A_numeric_features_e2.md

# Price-factor windows (EXPANSION_PLAN §8 item 4; pinned here, ratified at G3).
MOMENTUM_LOOKBACK_SESSIONS = 126
VOL_WINDOW_SESSIONS = 63
VOL_DDOF = 1  # sample std; H2's ddof item -- stated, not defaulted

TAXONOMY_OF_TAG: dict[str, str] = {
    tag: taxonomy
    for pairs in CONCEPT_FAMILIES.values()
    for taxonomy, tag in pairs
}

# feature -> the concept families it needs. A feature is NaN whenever ANY of
# its families is UNRESOLVED for that company.
FEATURE_FAMILIES: dict[str, tuple[str, ...]] = {
    "log_total_assets": ("assets",),
    "leverage_liabilities_to_assets": ("liabilities", "assets"),
    "equity_to_assets": ("equity", "assets"),
    "cash_to_assets": ("cash", "assets"),
    "net_margin": ("net_income", "revenue"),
    "operating_margin": ("operating_income", "revenue"),
    "operating_cashflow_to_revenue": ("operating_cash_flow", "revenue"),
    "revenue_yoy_growth": ("revenue",),
    "net_income_yoy_growth": ("net_income",),
    "eps_diluted_yoy_growth": ("eps_diluted",),
    "book_to_market": ("equity", "shares_outstanding"),
}
# The 10 E1 names come from the frozen module, not retyped.
E1_NUMERIC_FEATURES: list[str] = list(F1.NUMERIC_FEATURE_NAMES)
BASELINE_FACTORS = ["momentum_126", "realized_vol_63", "book_to_market"]
ALL_FEATURES = E1_NUMERIC_FEATURES + BASELINE_FACTORS

# Families consulted per row (union of FEATURE_FAMILIES).
NEEDED_FAMILIES = tuple(sorted({f for fams in FEATURE_FAMILIES.values() for f in fams}))
# Families whose current-period value drives a YoY growth feature.
YOY_FAMILIES = {"revenue": "revenue_yoy_growth",
                "net_income": "net_income_yoy_growth",
                "eps_diluted": "eps_diluted_yoy_growth"}

# Currency-sensitive columns: a level, and a mixed-currency ratio.
FX_SENSITIVE_FEATURES = ("log_total_assets", "book_to_market")


# ---------------------------------------------------------------------------
# Provenance (the controls.py pattern, copied deliberately)
# ---------------------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def assert_input_shas() -> dict:
    """Every large input's sha256 is asserted against the committed record
    before a byte of it is used. Mismatch is fatal, never a warning."""
    reference = json.loads(SHA_REFERENCE.read_text())["provenance"]["inputs"]
    measured = {
        "filings_metadata_e2.db": _sha256_file(METADATA_DB),
        "prices_e2.parquet": _sha256_file(PRICES_PATH),
        "fundamentals_e2.parquet": _sha256_file(FUNDAMENTALS_PATH),
    }
    for name, sha in measured.items():
        expected = reference.get(name)
        if expected != sha:
            raise AssertionError(
                f"{name} sha256 mismatch: measured {sha}, "
                f"{SHA_REFERENCE.name} records {expected}. The E2 inputs are "
                "frozen; refusing to build features off an unpinned artifact."
            )
    measured["concept_resolution.csv"] = _sha256_file(CONCEPT_RESOLUTION_CSV)
    measured["_asserted_against"] = SHA_REFERENCE.name
    measured["_asserted_against_sha256"] = _sha256_file(SHA_REFERENCE)
    return measured


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_row_universe(db_path: Path = METADATA_DB, stratum: str = "core") -> pd.DataFrame:
    """One row per (cik, accession_number): every filing of a stratum member
    filed inside that member's own membership spell.

    `report_date` is deliberately NOT selected -- it must never reach a
    point-in-time decision (HANDOFF §7).
    """
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as con:
        f = pd.read_sql(
            "SELECT accession_number, cik, form, filing_date, acceptance_datetime "
            "FROM filings", con)
    f["filing_date"] = pd.to_datetime(f["filing_date"])
    members = C.load_membership(db_path)
    members = members[members["stratum"] == stratum]
    j = f.merge(members, on="cik", how="inner")
    j = j[(j["filing_date"] >= j["member_from"]) & (j["filing_date"] < j["member_to"])]
    j = j.drop(columns=["member_from", "member_to"])
    j = j.sort_values(["cik", "filing_date", "accession_number"]).reset_index(drop=True)
    if j["accession_number"].duplicated().any():
        raise AssertionError("accession_number is not unique in the row universe")
    return j


def load_resolution(ciks: set[int]) -> pd.DataFrame:
    """F2's committed per-(cik, family) classifier outcome, scoped to `ciks`."""
    r = pd.read_csv(CONCEPT_RESOLUTION_CSV)
    r = r[r["cik"].isin(ciks)].copy()
    r["tag_list"] = r["tags"].fillna("").apply(
        lambda s: [t for t in str(s).split("|") if t])
    r["resolved"] = r["severity"] == "resolved"
    return r


def load_fundamentals(ciks: set[int]) -> pd.DataFrame:
    """Operating-form fundamentals facts for the row universe's companies.

    Form filter = `ingest_fundamentals.is_operating_form` (10-K / 10-Q / 8-K
    and their /A amendments) -- E2's own ratified rule, the one the committed
    classifier's coverage decisions were made under. E1's
    `features.ALLOWED_FUNDAMENTALS_FORMS` is the same three forms without the
    amendments; the row-count difference is measured and reported, never
    assumed to be zero.
    """
    f = pd.read_parquet(FUNDAMENTALS_PATH)
    f = f[f["cik"].isin(ciks)]
    f = f[f["form"].map(is_operating_form)].copy()
    f["filed"] = pd.to_datetime(f["filed"])
    f["period_end"] = pd.to_datetime(f["period_end"])
    f["period_start"] = pd.to_datetime(f["period_start"])
    return f


def slice_by_cik_tag(fund: pd.DataFrame) -> dict[tuple[int, str], pd.DataFrame]:
    """Pre-slice the fact table per (cik, concept).

    This is a performance move ONLY and changes no semantics: `value_as_of()`
    re-applies the same cik/concept/taxonomy filters on whatever frame it is
    handed, so calling it on the pre-sliced frame returns exactly the row it
    returns on the full frame (pinned by
    `test_slicing_does_not_change_value_as_of`). It is 14x faster.
    """
    out: dict[tuple[int, str], pd.DataFrame] = {}
    for (cik, concept), g in fund.groupby(["cik", "concept"], sort=False):
        out[(int(cik), str(concept))] = g.reset_index(drop=True)
    return out


# ---------------------------------------------------------------------------
# Concept resolution (CIK-keyed, taxonomy-aware port of E1's resolver)
# ---------------------------------------------------------------------------


def resolve_family_value(
    slices: dict[tuple[int, str], pd.DataFrame],
    tags: list[str],
    cik: int,
    as_of,
    staleness_log: Optional[list[dict]] = None,
    family: str = "",
) -> tuple[Optional[dict], Optional[str]]:
    """The freshest knowable fact across a family's resolved tags, or
    (None, None). Same rule as `features.resolve_concept_family()`: every tag
    is looked up through `pit.value_as_of`, the candidate with the most recent
    `period_end` wins (ties by `filed`), and a winner whose `period_end` is
    more than `STALENESS_MAX_DAYS` stale relative to `as_of` is DISCARDED
    rather than returned -- a resolved-but-ancient fact is not a usable
    current feature, and silently returning one is the E1 red-team BLOCKER.
    """
    candidates: list[tuple[dict, str]] = []
    for tag in tags:
        sub = slices.get((int(cik), tag))
        if sub is None or sub.empty:
            continue
        row = value_as_of(sub, tag, as_of, cik=cik, taxonomy=TAXONOMY_OF_TAG.get(tag))
        if row is not None:
            candidates.append((row, tag))
    if not candidates:
        return None, None
    candidates.sort(key=lambda item: (pd.Timestamp(item[0]["period_end"]),
                                      pd.Timestamp(item[0]["filed"])))
    row, tag = candidates[-1]
    days_stale = (pd.Timestamp(as_of) - pd.Timestamp(row["period_end"])).days
    if F1._is_stale(row, as_of):
        if staleness_log is not None:
            staleness_log.append({"cik": int(cik), "family": family, "tag": tag,
                                  "as_of": pd.Timestamp(as_of),
                                  "period_end": pd.Timestamp(row["period_end"]),
                                  "days_stale": days_stale})
        return None, None
    row = dict(row)
    row["_days_stale"] = days_stale
    return row, tag


def yoy_growth_family(
    slices: dict[tuple[int, str], pd.DataFrame],
    tags: list[str],
    cik: int,
    as_of,
    current_row: Optional[dict],
    current_tag: Optional[str],
) -> tuple[float, Optional[str]]:
    """(current - prior) / |prior| for the period ending ~1 year before the
    current period, of matching duration, knowable at the SAME as_of --
    `features.yoy_growth()`'s definition, with the prior-period search run
    over the family's resolved tags instead of only the current tag.

    Why the widening is needed at E2 and is not a redefinition: a MIGRATION
    family's prior-year figure legitimately sits under the PREDECESSOR tag,
    so E1's single-tag search returns NaN across every switch. With one tag
    in the family the two are identical by construction. The lookup itself is
    `features.value_for_target_period()` imported verbatim (its
    end_tolerance_days=45 / duration_tolerance_days=20 unchanged), and the
    returned tag is recorded so cross-tag YoY values are countable.
    """
    if current_row is None or current_tag is None:
        return np.nan, None
    current_value = current_row.get("value")
    if current_value is None or pd.isna(current_value):
        return np.nan, None
    period_end = pd.Timestamp(current_row["period_end"])
    period_start = current_row.get("period_start")
    duration = None
    if period_start is not None and not pd.isna(period_start):
        duration = (period_end - pd.Timestamp(period_start)).days
    target_period_end = period_end - pd.DateOffset(years=1)

    best: Optional[tuple[dict, str]] = None
    for tag in tags:
        sub = slices.get((int(cik), tag))
        if sub is None or sub.empty:
            continue
        ticker = sub["ticker"].iloc[0]  # one ticker label per cik (asserted at build)
        prior = F1.value_for_target_period(
            sub, tag, ticker, cik, as_of, target_period_end, duration_days=duration)
        if prior is None:
            continue
        if best is None:
            best = (prior, tag)
            continue
        # closest to the target period wins; ties to the later-filed row
        def key(p):
            return (abs((pd.Timestamp(p["period_end"]) - target_period_end).days),
                    -pd.Timestamp(p["filed"]).value)
        if key(prior) < key(best[0]):
            best = (prior, tag)
    if best is None:
        return np.nan, None
    prior_row, prior_tag = best
    prior_value = prior_row.get("value")
    if prior_value is None or pd.isna(prior_value) or abs(prior_value) < 1e-6:
        return np.nan, None
    return float(current_value - prior_value) / abs(float(prior_value)), prior_tag


# ---------------------------------------------------------------------------
# Price factors -- every window ends strictly before the news session
# ---------------------------------------------------------------------------


def price_factors(closes: Optional[np.ndarray], pre_pos: int) -> tuple[float, float, float]:
    """(momentum_126, realized_vol_63, close_at_pre_session).

    `pre_pos` is the index of the last session STRICTLY BEFORE the filing's
    news session (`controls.resolve_sessions`). Nothing at or after the news
    session is touched: the highest index read anywhere below is `pre_pos`.
    """
    nan3 = (np.nan, np.nan, np.nan)
    if closes is None or pre_pos is None or pre_pos < 0 or pre_pos >= len(closes):
        return nan3
    pre_close = closes[pre_pos]
    if not np.isfinite(pre_close):
        return nan3

    mom = np.nan
    back = pre_pos - MOMENTUM_LOOKBACK_SESSIONS
    if back >= 0:
        base = closes[back]
        if np.isfinite(base) and base > 0:
            mom = float(pre_close / base - 1.0)

    vol = np.nan
    start = pre_pos - VOL_WINDOW_SESSIONS
    if start >= 0:
        window = closes[start:pre_pos + 1]           # inclusive of pre_pos only
        if np.all(np.isfinite(window)) and np.all(window > 0):
            rets = np.diff(np.log(window))           # exactly VOL_WINDOW_SESSIONS
            vol = float(np.std(rets, ddof=VOL_DDOF))
    return mom, vol, float(pre_close)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def build(limit: Optional[int] = None,
          stratum: str = "core",
          verbose: bool = True) -> tuple[pd.DataFrame, dict]:
    """Build the numeric feature table. Returns (frame, diagnostics)."""
    t0 = time.time()
    shas = assert_input_shas()

    rows = load_row_universe(stratum=stratum)
    n_rows_universe = len(rows)
    if limit is not None:
        rows = rows.head(limit).copy()

    prices = C.load_price_matrix(PRICES_PATH)
    calendar = prices.index
    rows = C.resolve_sessions(rows, calendar)
    close_by_cik = {int(c): prices[c].to_numpy(dtype=float) for c in prices.columns}

    ciks = set(int(c) for c in rows["cik"].unique())
    res = load_resolution(ciks)
    fund = load_fundamentals(ciks)
    if fund.groupby("cik")["ticker"].nunique().max() > 1:
        raise AssertionError("a cik carries more than one ticker label in fundamentals_e2")
    slices = slice_by_cik_tag(fund)

    # (cik, family) -> resolved tag list; missing/UNRESOLVED -> None
    resolved: dict[tuple[int, str], Optional[list[str]]] = {}
    unresolved_rows: list[dict] = []
    sector_of = (rows.drop_duplicates("cik").set_index("cik")["sector"].to_dict())
    for cik in sorted(ciks):
        for family in NEEDED_FAMILIES:
            hit = res[(res["cik"] == cik) & (res["family"] == family)]
            if hit.empty:
                resolved[(cik, family)] = None
                unresolved_rows.append({"cik": cik, "sector": sector_of.get(cik),
                                        "family": family, "state": "MISSING_FROM_RESOLUTION_CSV",
                                        "severity": "UNRESOLVED", "coverage": np.nan,
                                        "tags_seen": ""})
                continue
            row = hit.iloc[0]
            if not bool(row["resolved"]):
                resolved[(cik, family)] = None
                unresolved_rows.append({"cik": cik, "sector": sector_of.get(cik),
                                        "family": family, "state": row["state"],
                                        "severity": row["severity"],
                                        "coverage": row["coverage"],
                                        "tags_seen": row["tags"] if isinstance(row["tags"], str) else ""})
            else:
                resolved[(cik, family)] = list(row["tag_list"])
    staleness_log: list[dict] = []
    accepted_days_stale: list[float] = []
    cache: dict[tuple[int, str, pd.Timestamp], tuple[Optional[dict], Optional[str]]] = {}
    records: list[dict] = []
    yoy_cross_tag = 0
    duration_mismatch: dict[str, int] = {"net_income": 0, "operating_income": 0,
                                         "operating_cash_flow": 0}
    fx_blocked = 0
    unit_mismatch = 0
    price_gap_rows = 0
    price_gap_ciks: set[int] = set()

    for i, r in enumerate(rows.itertuples(index=False)):
        cik = int(r.cik)
        as_of = pd.Timestamp(r.info_date)
        vals: dict[str, Optional[dict]] = {}
        tags_used: dict[str, Optional[str]] = {}
        for family in NEEDED_FAMILIES:
            tags = resolved[(cik, family)]
            if not tags:
                vals[family], tags_used[family] = None, None
                continue
            key = (cik, family, as_of)
            if key not in cache:
                cache[key] = resolve_family_value(
                    slices, tags, cik, as_of, staleness_log=staleness_log, family=family)
            vals[family], tags_used[family] = cache[key]
            if vals[family] is not None:
                accepted_days_stale.append(float(vals[family]["_days_stale"]))

        def v(family: str) -> float:
            row = vals.get(family)
            return np.nan if row is None else row.get("value", np.nan)

        def unit(family: str) -> str:
            row = vals.get(family)
            return "" if row is None else str(row.get("unit", ""))

        def ratio(num_family: str, den_family: str) -> float:
            """E1's `_safe_div`, with an explicit same-currency assertion --
            a ratio of two different currencies is not a number this file
            will emit."""
            nonlocal unit_mismatch
            nu, du = unit(num_family), unit(den_family)
            if nu and du and nu != du:
                unit_mismatch += 1
                return np.nan
            return F1._safe_div(v(num_family), v(den_family))

        assets = v("assets")
        is_usd = (unit("assets") or "USD").upper().startswith("USD")

        rec = {
            "cik": cik,
            "accession_number": r.accession_number,
            "form": r.form,
            "sector": r.sector,
            "stratum": r.stratum,
            "filing_date": pd.Timestamp(r.filing_date),
            "acceptance_datetime": r.acceptance_datetime,
            "info_date": as_of,
            "post_close": bool(r.post_close),
            "news_session": calendar[r.news_pos] if r.news_pos >= 0 else pd.NaT,
            "pre_session": calendar[r.pre_pos] if r.pre_pos >= 0 else pd.NaT,
            "log_total_assets": (float(np.log(assets))
                                 if is_usd and pd.notna(assets) and assets > 0 else np.nan),
            "leverage_liabilities_to_assets": ratio("liabilities", "assets"),
            "equity_to_assets": ratio("equity", "assets"),
            "cash_to_assets": ratio("cash", "assets"),
            "net_margin": ratio("net_income", "revenue"),
            "operating_margin": ratio("operating_income", "revenue"),
            "operating_cashflow_to_revenue": ratio("operating_cash_flow", "revenue"),
        }
        if not is_usd and pd.notna(assets):
            fx_blocked += 1

        # Flow-period durations are MATERIALIZED, not judged. E1's definition
        # is ported unchanged (a change to a pre-registered feature is G3's
        # call, not this module's), but the ratio features pair facts whose
        # accounting periods can differ -- most importantly year-to-date
        # operating cash flow over a single-quarter revenue in Q2/Q3 10-Qs.
        # Writing each used fact's duration lets any consumer see, filter or
        # rule on that without this file silently deciding; the per-pair
        # mismatch rate is measured into the manifest.
        def dur(family: str) -> Optional[int]:
            row = vals.get(family)
            if row is None:
                return None
            ps, pe = row.get("period_start"), row.get("period_end")
            if ps is None or pd.isna(ps):
                return None
            return int((pd.Timestamp(pe) - pd.Timestamp(ps)).days)

        rev_dur = dur("revenue")
        rec["period_days_revenue"] = rev_dur
        for flow in ("net_income", "operating_income", "operating_cash_flow"):
            fd = dur(flow)
            rec[f"period_days_{flow}"] = fd
            if rev_dur is not None and fd is not None and abs(fd - rev_dur) > 20:
                duration_mismatch[flow] += 1

        for family, feature in YOY_FAMILIES.items():
            tags = resolved[(cik, family)] or []
            g, prior_tag = yoy_growth_family(slices, tags, cik, as_of,
                                             vals.get(family), tags_used.get(family))
            rec[feature] = g
            if prior_tag is not None and prior_tag != tags_used.get(family):
                yoy_cross_tag += 1

        mom, vol, pre_close = price_factors(close_by_cik.get(cik), int(r.pre_pos))
        rec["momentum_126"] = mom
        rec["realized_vol_63"] = vol
        # Second price-censoring channel, counted separately from the
        # no-price-column one below: this CIK HAS a column in the snapshot,
        # but the column carries no usable history inside this row's window
        # (no close at the pre-session, or a gap/non-positive close inside the
        # 126/63-session look-back), so momentum_126, realized_vol_63 AND
        # book_to_market (whose denominator needs the pre-session close) are
        # NaN for want of real prices rather than for want of a ticker.
        if cik in close_by_cik and not (np.isfinite(pre_close)
                                        and np.isfinite(mom) and np.isfinite(vol)):
            price_gap_rows += 1
            price_gap_ciks.add(cik)

        equity = v("equity")
        shares = v("shares_outstanding")
        equity_usd = is_usd and (unit("equity") or "USD").upper().startswith("USD")
        if (equity_usd and pd.notna(equity) and pd.notna(shares) and shares > 0
                and pd.notna(pre_close) and pre_close > 0):
            rec["book_to_market"] = float(equity / (shares * pre_close))
        else:
            rec["book_to_market"] = np.nan

        for family in NEEDED_FAMILIES:
            rec[f"tag_{family}"] = tags_used.get(family)
        rec["fx_currency"] = unit("assets") or None
        records.append(rec)
        if verbose and (i + 1) % 2000 == 0:
            print(f"  {i + 1}/{len(rows)} rows  ({time.time() - t0:.0f}s)")

    df = pd.DataFrame(records)
    unresolved = pd.DataFrame(unresolved_rows)
    if not unresolved.empty:
        counts = df.groupby("cik").size().to_dict()
        unresolved["n_rows_affected"] = unresolved["cik"].map(counts).fillna(0).astype(int)
        unresolved["features_affected"] = unresolved["family"].map(
            lambda fam: "|".join(f for f, fams in FEATURE_FAMILIES.items() if fam in fams))
        unresolved = unresolved.sort_values(["family", "cik"]).reset_index(drop=True)

    # Price censoring, reported per the standing rule (never silently dropped),
    # on TWO channels side by side: (a) the CIK has no column in the price
    # snapshot at all; (b) the CIK has a column but no usable history inside
    # the row's window (counted in the loop above). Both leave momentum_126,
    # realized_vol_63 and book_to_market NaN and both keep the row.
    unpriced = sorted(c for c in ciks if c not in close_by_cik)
    n_rows_unpriced = int(rows["cik"].isin(unpriced).sum())
    n_rows_short_history = int((rows["pre_pos"] < MOMENTUM_LOOKBACK_SESSIONS).sum())

    diag = _diagnostics(df, accepted_days_stale, unresolved, staleness_log, shas, calendar,
                        n_rows_universe, stratum,
                        {"yoy_cross_tag": yoy_cross_tag,
                         "flow_duration_mismatch_vs_revenue": duration_mismatch,
                         "fx_blocked_rows": fx_blocked,
                         "unit_mismatch_ratios": unit_mismatch,
                         "ciks_without_price_coverage": len(unpriced),
                         "rows_without_price_coverage": n_rows_unpriced,
                         "ciks_with_price_column_but_no_usable_history": len(price_gap_ciks),
                         "rows_with_price_column_but_no_usable_history": price_gap_rows,
                         "rows_with_pre_session_before_momentum_window": n_rows_short_history},
                        runtime_s=time.time() - t0)
    return df, {"diagnostics": diag, "unresolved": unresolved,
                "staleness_log": pd.DataFrame(staleness_log)}


def _f(x) -> Optional[float]:
    return None if x is None or pd.isna(x) else round(float(x), 6)


def _stats(s: pd.Series) -> dict:
    """Distribution of one feature. Descriptive only -- no outcome enters."""
    v = s.dropna()
    if v.empty:
        return {"n_nonnull": 0, "min": None, "p01": None, "median": None,
                "p99": None, "max": None}
    return {"n_nonnull": int(len(v)), "min": _f(v.min()), "p01": _f(v.quantile(0.01)),
            "median": _f(v.median()), "p99": _f(v.quantile(0.99)), "max": _f(v.max())}


def _coverage(df: pd.DataFrame, by: Optional[str] = None) -> dict:
    """Non-null coverage per feature, overall or grouped."""
    if by is None:
        return {f: round(float(df[f].notna().mean()), 4) for f in ALL_FEATURES}
    out: dict[str, dict] = {}
    for key, g in df.groupby(by):
        out[str(key)] = {"n_rows": int(len(g)),
                         **{f: round(float(g[f].notna().mean()), 4) for f in ALL_FEATURES}}
    return out


def _diagnostics(df, accepted_days_stale, unresolved, staleness_log, shas, calendar,
                 n_rows_universe, stratum, counters, runtime_s) -> dict:
    stale_df = pd.DataFrame(staleness_log)
    # Re-derivation of E1's STALENESS_MAX_DAYS=200 on E2's own data: the
    # days-stale distribution of every fact the guard ACCEPTED, beside the
    # distribution of what it discarded. Reported, not retuned (G3's call).
    acc = pd.Series(accepted_days_stale, dtype=float)
    df_year = df.assign(year=df["filing_date"].dt.year)
    return {
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "module_sha256": _sha256_file(Path(__file__)),
        "stratum": stratum,
        "network_calls": 0,
        "computed_associations_with_returns": 0,
        "inputs": shas,
        "row_universe": {
            "n_filings_in_spell_total": int(n_rows_universe),
            "n_rows_built": int(len(df)),
            "n_ciks": int(df["cik"].nunique()),
            "forms": df["form"].value_counts().to_dict(),
            "filing_date_min": str(df["filing_date"].min().date()),
            "filing_date_max": str(df["filing_date"].max().date()),
            "n_rows_no_news_session": int(df["news_session"].isna().sum()),
            "n_post_close": int(df["post_close"].sum()),
            "price_calendar_first": str(calendar[0].date()),
            "price_calendar_last": str(calendar[-1].date()),
        },
        "coverage_overall": _coverage(df),
        "feature_summary": {f: _stats(df[f]) for f in ALL_FEATURES},
        "coverage_by_year": _coverage(df_year, by="year"),
        "coverage_by_sector": _coverage(df, by="sector"),
        "unresolved": {
            "n_pairs": int(len(unresolved)),
            "n_pairs_by_family": (unresolved["family"].value_counts().to_dict()
                                  if len(unresolved) else {}),
            "n_ciks_with_any": int(unresolved["cik"].nunique()) if len(unresolved) else 0,
            "csv": str(OUTPUT_UNRESOLVED.relative_to(REPO_ROOT)),
        },
        "staleness_guard": {
            "constant_STALENESS_MAX_DAYS": int(F1.STALENESS_MAX_DAYS),
            "constant_source": "features.py (E1, frozen); imported unchanged",
            "re_derived_on_e2_accepted_days_stale": {
                "n_facts_accepted": int(acc.notna().sum()),
                "p50": float(acc.quantile(0.50)) if len(acc) else None,
                "p99": float(acc.quantile(0.99)) if len(acc) else None,
                "p99_9": float(acc.quantile(0.999)) if len(acc) else None,
                "max": float(acc.max()) if len(acc) else None,
                "n_above_150": int((acc > 150).sum()),
                "n_above_180": int((acc > 180).sum()),
                "note": ("E1 justified 200 on 25 mega-caps (largest legitimate "
                         "case 198 days, first broken case 208). These are the "
                         "same quantities measured on E2; the constant was NOT "
                         "retuned here."),
            },
            "n_facts_discarded": int(len(stale_df)),
            "by_family": (stale_df["family"].value_counts().to_dict()
                          if len(stale_df) else {}),
            "days_stale_discarded_min": (int(stale_df["days_stale"].min())
                                         if len(stale_df) else None),
            "days_stale_discarded_median": (float(stale_df["days_stale"].median())
                                            if len(stale_df) else None),
            "days_stale_discarded_max": (int(stale_df["days_stale"].max())
                                         if len(stale_df) else None),
        },
        "counters": counters,
        "constants": {
            "momentum_lookback_sessions": MOMENTUM_LOOKBACK_SESSIONS,
            "vol_window_sessions": VOL_WINDOW_SESSIONS,
            "vol_ddof": VOL_DDOF,
            "yoy_end_tolerance_days": 45,
            "yoy_duration_tolerance_days": 20,
            "yoy_tolerances_source": "features.value_for_target_period defaults (E1, frozen)",
        },
        "runtime_seconds": round(runtime_s, 1),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the E2 numeric feature table (no ICs).")
    ap.add_argument("--limit", type=int, default=None, help="build only the first N rows")
    ap.add_argument("--stratum", default="core")
    ap.add_argument("--out", default=str(OUTPUT_PARQUET))
    args = ap.parse_args()

    df, extra = build(limit=args.limit, stratum=args.stratum)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_UNRESOLVED.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out, index=False)
    extra["unresolved"].to_csv(OUTPUT_UNRESOLVED, index=False)
    if len(extra["staleness_log"]):
        extra["staleness_log"].to_csv(F5_DIR / "numeric_staleness_discards_e2.csv", index=False)

    diag = extra["diagnostics"]
    diag["output"] = {"path": str(out),
                      "sha256": _sha256_file(out),
                      "n_rows": int(len(df)),
                      "key": ["cik", "accession_number"],
                      "features": ALL_FEATURES}
    OUTPUT_MANIFEST.write_text(json.dumps(diag, indent=2, default=str))
    print(f"wrote {out} ({len(df)} rows), manifest {OUTPUT_MANIFEST.name}, "
          f"{len(extra['unresolved'])} unresolved (cik, family) pairs, "
          f"{diag['runtime_seconds']}s")


if __name__ == "__main__":
    main()
