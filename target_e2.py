"""
target_e2.py -- F5 Step 1A: the 63-TRADING-SESSION FORWARD EXCESS-RETURN
TARGET for every E2 core-stratum filing.

WHAT THIS FILE IS
-----------------
One row per (core-stratum filing), carrying the point-in-time event dating,
the forward window's two endpoint sessions, the subject's 63-session return,
the membership-dated equal-weighted benchmark return EXCLUDING self, and the
excess (subject - benchmark). It writes `data/f5/target_e2.parquet` and
`data/f5/target_e2_manifest.json`.

It is a TARGET table only. It computes no information coefficient, no
correlation, and no feature-versus-outcome association of any kind
(`F5_PLAN.md` §1, the E2 freeze). No feature table is read or joined here.

NON-GOALS (`HANDOFF.md` §1, inherited unconditionally). Nothing here places,
queues, recommends or evaluates a trade; there is no expected-return figure
and no "beats the market" framing anywhere. A forward realized return is the
dependent variable of a research measurement, not a projection.

EVERYTHING DATE-RELATED IS PORTED, NOT PARAPHRASED
--------------------------------------------------
`load_membership`, `load_price_matrix`, `build_membership_matrix`,
`align_membership`, `excess_return` and `resolve_sessions` are IMPORTED from
`controls.py` (byte-frozen; see its module docstring, "POINT-IN-TIME
DISCIPLINE, EXACTLY AS IMPLEMENTED"). The holding horizon is
`controls.HOLDING_DAYS` (63), the estimand's defining parameter, so this
module cannot drift from the published H1 control stack.

The resulting session chain, restated here because it is the whole PIT
argument:

    info_date    = max(filing_date, acceptance_date_ET)
                   -- the max() covers both anomaly families: the 45%
                      post-close population, and the filings whose
                      filing_date PRECEDES acceptance (Salesforce CIK
                      1108524 by 344 and 633 days, plus two others; the
                      bytes were not public on the earlier date).
    post_close   = acceptance hour in ET >= 16
    news_session = first session >= info_date  (pre-close)
                   first session >  info_date  (post-close)
    window_open  = news_session + 1 session    -- the entry close STRICTLY
                   post-dates the session that first impounded the news
    window_close = window_open + 63 sessions

`window_open_session > info_date` always; that invariant is asserted on
every run and is a test.

BENCHMARK (E2's §3.3 proposal, still awaiting the owner's G3 ratification)
-------------------------------------------------------------------------
Equal-weighted mean of the SAME 63-session window return over the universe
members on the WINDOW-OPEN session, EXCLUDING self, membership-dated. The
member set is the universe's membership table as a whole (both strata), which
is exactly what `controls.py` used for its published H1 numbers; the core
stratum governs which FILINGS are scored, not who is in the average. Members
without real price coverage at BOTH endpoints are COUNTED
(`n_benchmark_unpriced`) and excluded from the mean -- never imputed, never
forward-filled past a CIK's last observation.

E1 and E2 backtest numbers are NUMERICALLY INCOMPARABLE (different
benchmark); any document quoting both must say so.

NO FLOOR IS APPLIED to the benchmark member count here: `n_benchmark_members`
is written on every row so that a floor (if G3 wants one; `controls.py`'s own
T2 arm used >= 20) can be applied downstream without recomputing the table.

WHAT IS READ, WHAT IS WRITTEN
-----------------------------
Reads read-only: `data/filings_metadata_e2.db` (tables `filings`,
`universe_membership`), `data/prices_e2.parquet`. `report_date` is never
selected. Writes exactly two artifacts, both under `data/f5/`. Zero network
calls.

Run:  python3 target_e2.py
      python3 -m pytest -q test_target_e2.py
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Read-only import of the frozen E1/H1 stack. Importing it executes no I/O.
import controls as C

REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
METADATA_DB = DATA_DIR / "filings_metadata_e2.db"
PRICES_PATH = DATA_DIR / "prices_e2.parquet"
FUNDAMENTALS_PATH = DATA_DIR / "fundamentals_e2.parquet"
# The committed record that pins the three input shas (H1 provenance block).
COMMITTED_PROVENANCE = DATA_DIR / "hardening" / "controls_results.json"

OUT_DIR = DATA_DIR / "f5"
STATUS_DIR = OUT_DIR / "status"
OUT_PARQUET = OUT_DIR / "target_e2.parquet"
OUT_MANIFEST = OUT_DIR / "target_e2_manifest.json"

HOLDING_SESSIONS = C.HOLDING_DAYS  # 63, from controls.SPEC -- never re-typed
GLD_CIK = 1222333  # SPDR GOLD TRUST: kept and flagged; exclusion is a G3 call

OUTPUT_COLUMNS = [
    "cik", "accession_number", "form", "filing_date", "acceptance_datetime",
    "info_date", "post_close", "news_session", "window_open_session",
    "window_close_session", "subject_return_63", "benchmark_return_63",
    "target_excess_63", "n_benchmark_members", "n_benchmark_unpriced",
    "target_complete", "in_membership", "is_gld",
]


# ---------------------------------------------------------------------------
# Provenance -- every large artifact is sha-asserted before it is used
# ---------------------------------------------------------------------------


def assert_input_shas(strict: bool = True) -> dict:
    """Assert the three E2 inputs against the committed provenance record.

    `data/hardening/controls_results.json` is the committed manifest that
    pins `filings_metadata_e2.db`, `prices_e2.parquet` and
    `fundamentals_e2.parquet` (its `provenance.inputs` block). A mismatch
    means the snapshot moved under us and every number below would be
    unreproducible, so it raises rather than warns.

    Returns the MEASURED shas (which go into the manifest this module
    writes, so the price snapshot is pinned by this run too).
    """
    measured = {
        "filings_metadata_e2.db": C._sha256_file(METADATA_DB),
        "prices_e2.parquet": C._sha256_file(PRICES_PATH),
        "fundamentals_e2.parquet": C._sha256_file(FUNDAMENTALS_PATH),
    }
    expected = json.loads(COMMITTED_PROVENANCE.read_text())["provenance"]["inputs"]
    mismatches = {k: {"expected": expected.get(k), "measured": v}
                  for k, v in measured.items() if expected.get(k) != v}
    if mismatches and strict:
        raise AssertionError(
            "input sha256 mismatch against the committed provenance record "
            f"{COMMITTED_PROVENANCE}: {json.dumps(mismatches, indent=2)}")
    return {"measured": measured, "expected_source":
            str(COMMITTED_PROVENANCE.relative_to(REPO_ROOT)),
            "matches_committed": not mismatches}


# ---------------------------------------------------------------------------
# Loading -- read-only, no network, `report_date` never selected
# ---------------------------------------------------------------------------


def load_core_spells(db_path: Path = METADATA_DB) -> pd.DataFrame:
    """The core-stratum membership spells (a subset of `load_membership`)."""
    m = C.load_membership(db_path)
    return m[m["stratum"] == "core"].reset_index(drop=True)


def load_core_filings(db_path: Path = METADATA_DB) -> pd.DataFrame:
    """Every filing by a CIK that holds at least one core membership spell.

    Rows are NOT filtered to in-membership here: `in_membership` is a flag on
    the output so the scope decision stays visible and reversible at G3.
    """
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as con:
        f = pd.read_sql(
            "SELECT accession_number, cik, form, filing_date, "
            "acceptance_datetime FROM filings", con)
    f["filing_date"] = pd.to_datetime(f["filing_date"])
    core_ciks = set(load_core_spells(db_path)["cik"])
    f = f[f["cik"].isin(core_ciks)].copy()
    return f.sort_values(["filing_date", "cik", "accession_number"]).reset_index(drop=True)


def flag_in_membership(rows: pd.DataFrame, spells: pd.DataFrame) -> pd.Series:
    """True where `info_date` falls inside one of that CIK's core spells.

    Half-open [member_from, member_to), the SAME convention
    `controls.build_membership_matrix` uses for the benchmark, so a filing
    can never be scored in-membership on a session where its own CIK is not
    a benchmark member. (The brief's closed-interval bracket notation and
    this half-open rule differ only on `info_date == member_to`; that count
    is measured and reported in the manifest.)
    """
    j = rows[["accession_number", "cik", "info_date"]].merge(
        spells[["cik", "member_from", "member_to"]], on="cik", how="left")
    hit = (j["info_date"] >= j["member_from"]) & (j["info_date"] < j["member_to"])
    inside = set(j.loc[hit, "accession_number"])
    return rows["accession_number"].isin(inside)


def count_boundary_rows(rows: pd.DataFrame, spells: pd.DataFrame) -> int:
    """Rows the half-open convention excludes but a closed one would keep."""
    j = rows[["accession_number", "cik", "info_date"]].merge(
        spells[["cik", "member_from", "member_to"]], on="cik", how="left")
    edge = set(j.loc[j["info_date"] == j["member_to"], "accession_number"])
    hit = (j["info_date"] >= j["member_from"]) & (j["info_date"] < j["member_to"])
    return int(len(edge - set(j.loc[hit, "accession_number"])))


# ---------------------------------------------------------------------------
# The target
# ---------------------------------------------------------------------------


def build_targets(filings: pd.DataFrame, prices: pd.DataFrame,
                  member_mat: pd.DataFrame, spells: pd.DataFrame,
                  holding_sessions: int = HOLDING_SESSIONS) -> pd.DataFrame:
    """One row per filing with the forward excess-return target attached.

    Rows whose window cannot be completed against the price snapshot keep
    every dated column they do have and carry `target_complete = False` with
    null returns -- they are the census the G3 fold decision reads, so they
    are never dropped.
    """
    cal = prices.index
    n_sessions = len(cal)
    price_arr = prices.to_numpy(dtype=float)
    member_arr = C.align_membership(member_mat, prices.columns)
    cik_positions = {c: i for i, c in enumerate(prices.columns)}

    ev = C.resolve_sessions(filings, cal)
    ev["in_membership"] = flag_in_membership(ev, spells)

    news_pos = ev["news_pos"].to_numpy(dtype=int)
    open_pos = np.where(news_pos >= 1, news_pos + 1, -1)
    open_pos = np.where(open_pos >= n_sessions, -1, open_pos)
    close_pos = np.where(open_pos >= 0, open_pos + holding_sessions, -1)
    close_pos = np.where(close_pos >= n_sessions, -1, close_pos)

    recs = []
    for i, e in enumerate(ev.itertuples(index=False)):
        o, cl = int(open_pos[i]), int(close_pos[i])
        r = {
            "news_session": cal[news_pos[i]] if news_pos[i] >= 1 else pd.NaT,
            "window_open_session": cal[o] if o >= 0 else pd.NaT,
            "window_close_session": cal[cl] if cl >= 0 else pd.NaT,
            "subject_return_63": np.nan,
            "benchmark_return_63": np.nan,
            "target_excess_63": np.nan,
            "n_benchmark_members": 0,
            "n_benchmark_unpriced": 0,
            "target_complete": False,
        }
        if o >= 0 and cl >= 0:
            subj, bench, n_used, n_missing = C.excess_return(
                price_arr, cik_positions, member_arr, e.cik, o, cl, o)
            r["subject_return_63"] = subj
            r["benchmark_return_63"] = bench
            r["n_benchmark_members"] = n_used
            r["n_benchmark_unpriced"] = n_missing
            r["target_complete"] = True
            if np.isfinite(subj) and np.isfinite(bench):
                r["target_excess_63"] = subj - bench
        recs.append(r)

    out = pd.concat([ev.reset_index(drop=True), pd.DataFrame(recs)], axis=1)
    out["acceptance_datetime"] = out["acceptance_et"].astype(str)
    out["is_gld"] = out["cik"] == GLD_CIK
    out = out[OUTPUT_COLUMNS].copy()
    assert_target_invariants(out, cal, holding_sessions)
    return out


def assert_target_invariants(t: pd.DataFrame, calendar: pd.DatetimeIndex,
                             holding_sessions: int = HOLDING_SESSIONS) -> None:
    """Hard PIT invariants. A violation is a leakage bug, not a warning."""
    bad = t[t["news_session"].notna() & (t["news_session"] < t["info_date"])]
    if len(bad):
        raise AssertionError(f"{len(bad)} rows have news_session < info_date.")

    post = t[t["news_session"].notna() & t["post_close"]]
    bad = post[post["news_session"] <= post["info_date"]]
    if len(bad):
        raise AssertionError(
            f"{len(bad)} post-close rows have news_session <= info_date -- "
            "the 16:00 ET acceptance correction is not being applied.")

    open_ok = t["window_open_session"].notna()
    bad = t[open_ok & (t["window_open_session"] <= t["info_date"])]
    if len(bad):
        raise AssertionError(
            f"{len(bad)} rows open the forward window on or before info_date.")
    bad = t[open_ok & (t["window_open_session"] <= t["news_session"])]
    if len(bad):
        raise AssertionError(
            f"{len(bad)} rows open the forward window on or before the "
            "session that first impounded the news.")

    both = t["window_open_session"].notna() & t["window_close_session"].notna()
    if both.any():
        o = calendar.get_indexer(t.loc[both, "window_open_session"])
        c = calendar.get_indexer(t.loc[both, "window_close_session"])
        if (o < 0).any() or (c < 0).any():
            raise AssertionError("a window endpoint is not a market session.")
        span = c - o
        if not (span == holding_sessions).all():
            raise AssertionError(
                f"window length is not exactly {holding_sessions} sessions "
                f"(observed {sorted(set(span.tolist()))}).")

    incomplete = ~t["target_complete"].astype(bool)
    bad = t[incomplete & (t["window_close_session"].notna()
                          | t["subject_return_63"].notna()
                          | t["benchmark_return_63"].notna()
                          | t["target_excess_63"].notna())]
    if len(bad):
        raise AssertionError(
            f"{len(bad)} incomplete rows carry a close session or a return.")

    ex = t["target_excess_63"].notna()
    if ex.any():
        resid = (t.loc[ex, "target_excess_63"]
                 - (t.loc[ex, "subject_return_63"] - t.loc[ex, "benchmark_return_63"]))
        if float(np.nanmax(np.abs(resid))) > 1e-12:
            raise AssertionError("target_excess_63 != subject - benchmark.")


# ---------------------------------------------------------------------------
# Census + manifest
# ---------------------------------------------------------------------------


def quarter_census(t: pd.DataFrame) -> dict:
    """Complete vs incomplete targets per calendar quarter of `info_date`.

    Keyed on the event's own PIT date because that is how a fold assigns a
    filing. Reported for the in-membership rows (the analysis population)
    and for all scoped rows beside it -- the G3 fold decision needs both.
    """
    def _tab(frame: pd.DataFrame) -> dict:
        if frame.empty:
            return {}
        q = frame["info_date"].dt.to_period("Q").astype(str)
        g = frame.assign(q=q).groupby("q")["target_complete"]
        return {k: {"n_rows": int(v.size), "n_complete": int(v.sum()),
                    "n_incomplete": int(v.size - v.sum())}
                for k, v in g}

    return {
        "key": "calendar quarter of info_date = max(filing_date, "
               "acceptance_date_ET)",
        "in_membership_rows": _tab(t[t["in_membership"]]),
        "all_scoped_rows": _tab(t),
    }


def build_manifest(t: pd.DataFrame, prices: pd.DataFrame, shas: dict,
                   counts: dict, runtimes: dict) -> dict:
    inmem = t[t["in_membership"]]
    return {
        "artifact": "data/f5/target_e2.parquet",
        "module": "target_e2.py",
        "module_sha256": C._sha256_file(Path(__file__)),
        "controls_py_sha256": C._sha256_file(REPO_ROOT / "controls.py"),
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "network_calls": 0,
        "estimand": {
            "horizon_trading_sessions": HOLDING_SESSIONS,
            "window_open": "next trading session after news_session; "
                           "news_session = first session >= info_date "
                           "(pre-close) / > info_date (post-close)",
            "benchmark": "equal-weighted mean 63-session return over the "
                         "universe members on the window-open session, "
                         "EXCLUDING self, membership-dated (EXPANSION_PLAN "
                         "§3.3 proposal, pending G3 ratification)",
            "benchmark_member_floor_applied": None,
            "e1_e2_comparability": "E1 and E2 backtest numbers are "
                                   "numerically incomparable (different "
                                   "benchmark).",
            "no_ic_computed": True,
        },
        "inputs": shas,
        "price_snapshot": {
            "path": "data/prices_e2.parquet",
            "sha256": shas["measured"]["prices_e2.parquet"],
            "last_session": str(prices.index.max().date()),
            "first_session": str(prices.index.min().date()),
            "n_sessions": int(len(prices.index)),
            "n_priced_ciks": int(prices.shape[1]),
        },
        "row_counts": counts,
        "target_completeness": {
            "n_complete_all": int(t["target_complete"].sum()),
            "n_incomplete_all": int((~t["target_complete"]).sum()),
            "n_complete_in_membership": int(inmem["target_complete"].sum()),
            "n_incomplete_in_membership": int((~inmem["target_complete"]).sum()),
            "n_excess_non_null_in_membership": int(inmem["target_excess_63"].notna().sum()),
        },
        "quarter_census": quarter_census(t),
        "runtimes_seconds": runtimes,
        "output_sha256": None,  # filled after the parquet is written
    }


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def main() -> None:
    t0 = time.time()
    shas = assert_input_shas()
    t_sha = time.time() - t0

    t1 = time.time()
    prices = C.load_price_matrix(PRICES_PATH)
    members = C.load_membership(METADATA_DB)          # BOTH strata: the benchmark
    member_mat = C.build_membership_matrix(members, prices.index)
    spells = load_core_spells(METADATA_DB)            # core only: the scope
    filings = load_core_filings(METADATA_DB)
    t_load = time.time() - t1

    counts = {
        "n_core_ciks": int(spells["cik"].nunique()),
        "n_core_spells": int(len(spells)),
        "n_universe_member_ciks_all_strata": int(members["cik"].nunique()),
        "n_filings_by_core_ciks": int(len(filings)),
    }
    priced = set(prices.columns)
    missing_price_cik = filings[~filings["cik"].isin(priced)]
    counts["n_filings_excluded_solely_missing_subject_prices"] = int(len(missing_price_cik))
    counts["n_core_ciks_excluded_solely_missing_subject_prices"] = int(
        missing_price_cik["cik"].nunique())
    counts["n_core_ciks_with_price_coverage"] = int(
        filings.loc[filings["cik"].isin(priced), "cik"].nunique())
    filings = filings[filings["cik"].isin(priced)].copy()
    counts["n_rows_written"] = int(len(filings))

    t2 = time.time()
    t = build_targets(filings, prices, member_mat, spells)
    t_build = time.time() - t2

    counts["n_in_membership"] = int(t["in_membership"].sum())
    counts["n_out_of_membership"] = int((~t["in_membership"]).sum())
    # NOT a measured post-close rate. `post_close` is the TREATMENT flag of
    # the ported `controls.resolve_sessions` rule (acceptance hour in ET >= 16,
    # and True when the acceptance timestamp is missing), so these count rows
    # TREATED as post-close, which is a superset of "filings the market could
    # only have read after that session's close". The largest known gap is
    # carried beside it: rows accepted on an ET date EARLIER than their
    # filing_date -- the evening-before family -- are flagged post-close and
    # their window opens one session later than the information arguably
    # requires (status report §5 item 4).
    acc_et_date = (pd.to_datetime(t["acceptance_datetime"], utc=True, format="mixed")
                   .dt.tz_convert("America/New_York")   # same tz as controls.resolve_sessions
                   .dt.tz_localize(None).dt.normalize())
    early = acc_et_date < t["filing_date"]
    counts["n_rows_treated_post_close_under_ported_rule"] = int(t["post_close"].sum())
    counts["share_rows_treated_post_close_under_ported_rule"] = float(t["post_close"].mean())
    counts["n_rows_acceptance_et_date_before_filing_date"] = int(early.sum())
    counts["n_rows_acceptance_et_date_before_filing_date_treated_post_close"] = int(
        (early & t["post_close"]).sum())
    counts["n_info_date_after_filing_date"] = int((t["info_date"] > t["filing_date"]).sum())
    counts["n_no_news_session"] = int(t["news_session"].isna().sum())
    counts["n_no_window_open"] = int(t["window_open_session"].isna().sum())
    counts["n_complete_window_missing_subject_price"] = int(
        (t["target_complete"] & t["subject_return_63"].isna()).sum())
    counts["n_complete_window_missing_benchmark"] = int(
        (t["target_complete"] & t["benchmark_return_63"].isna()).sum())
    counts["n_gld_rows"] = int(t["is_gld"].sum())
    counts["n_membership_boundary_rows_excluded_by_half_open_rule"] = \
        count_boundary_rows(t, spells)
    counts["benchmark_members_used"] = {
        "median": float(t.loc[t["target_complete"], "n_benchmark_members"].median()),
        "min": int(t.loc[t["target_complete"], "n_benchmark_members"].min()),
        "max": int(t.loc[t["target_complete"], "n_benchmark_members"].max()),
    }
    counts["benchmark_member_cells_counted_unpriced"] = int(t["n_benchmark_unpriced"].sum())
    # Honest boundary of `n_benchmark_unpriced`: it counts member CIKs that
    # HAVE a price column but no real coverage at an endpoint. Member CIKs
    # with no price column at all are absent from the price matrix entirely
    # and cannot be counted per row -- so they are counted here, globally.
    absent = [c for c in member_mat.columns if c not in priced]
    counts["n_universe_member_ciks_absent_from_price_matrix"] = len(absent)
    counts["member_cells_absent_from_price_matrix_per_session"] = {
        "median": float(member_mat[absent].sum(axis=1).median()) if absent else 0.0,
        "max": int(member_mat[absent].sum(axis=1).max()) if absent else 0,
    }
    counts["forms"] = {str(k): int(v) for k, v in t["form"].value_counts().items()}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_DIR.mkdir(parents=True, exist_ok=True)
    t.to_parquet(OUT_PARQUET, index=False)

    runtimes = {"sha_assert": round(t_sha, 2), "load": round(t_load, 2),
                "build_targets": round(t_build, 2),
                "total": round(time.time() - t0, 2)}
    man = build_manifest(t, prices, shas, counts, runtimes)
    man["output_sha256"] = C._sha256_file(OUT_PARQUET)
    OUT_MANIFEST.write_text(json.dumps(man, indent=2, default=str))

    print(f"rows written: {len(t)}  in-membership: {counts['n_in_membership']}")
    print(f"complete targets: {man['target_completeness']['n_complete_all']}  "
          f"incomplete: {man['target_completeness']['n_incomplete_all']}")
    print(f"price snapshot last session: {man['price_snapshot']['last_session']}")
    print(f"runtimes: {json.dumps(runtimes)}")
    print(f"wrote {OUT_PARQUET} ({man['output_sha256'][:12]}…) and {OUT_MANIFEST}")


if __name__ == "__main__":
    main()
