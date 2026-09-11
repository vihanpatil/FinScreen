"""
heads_e2.py -- F5 Step 1B: the HEAD-2 and HEAD-3 runners.

WHAT THIS FILE IS
-----------------
Two small secondary-head runners, sharing one freeze guard, one session/price
stack and one provenance block:

  HEAD 2 (F5_PLAN.md §3 decision 12) -- volatility / informativeness event
  study over the CORE-stratum item-2.02 earnings 8-Ks.
      events    : `controls.load_earnings_events` (item-2.02 8-Ks filed inside
                  the filer's own membership spell), core stratum only, and
                  only CIKs that have a column in the sha-pinned price matrix.
      predictor : the event filing's `sentiment_negative_share`, joined on
                  (cik, accession_number) from `data/f5/text_features_e2.parquet`;
                  events with no text row are COUNTED, never imputed.
      DV        : mean |raw daily return| over sessions [+1, +5] AFTER the news
                  session, divided by the mean |raw daily return| over the
                  trailing 60 sessions ENDING AT THE PRE-SESSION. Benchmark-free
                  by construction, so G3 decisions 1-2 (benchmark, GLD) do not
                  propagate into this head.
      inference : wild-cluster bootstrap over EVENT QUARTERS, Rademacher
                  weights, draws pinned by the G3 document. ~39 clusters is a
                  FEW-CLUSTERS setting; the limitation is printed with the
                  number, every time.

  HEAD 3 (F5_PLAN.md §3 decision 13) -- exit prediction over core CIK-quarters.
      panel     : every (cik, quarter) that has at least one core in-membership
                  filing, features taken as of the CIK's LATEST filing in the
                  quarter (rule pinned by the G3 document).
      label     : an exit event within `horizon_quarters` of the feature date.
      metric    : AUC per fold under the HEAD-1 fold list from the G3 document,
                  with per-fold prevalence. A fold whose outcome window extends
                  past the label cut is reported CENSORED with its count and is
                  NOT scored.
      claim     : "exit", never "distress" (decision 13); see `load_exit_events`
                  for why the M&A / distress split is not available from the
                  stored data.

THE FREEZE (F5_PLAN.md §1) IS ENFORCED HERE, NOT ASSUMED
--------------------------------------------------------
No feature-versus-outcome association -- no IC, no correlation, no slope, no
model fit -- is computed by any code path in this module unless

    data/f5/G3_RATIFIED.json  exists AND its `doc_sha256` equals
    sha256(data/f5/G3_PREREGISTRATION.md)

Neither file exists as of 2026-09-10, so `--head2`, `--head3` and `--all`
REFUSE today (exit code 2) and this is a test. The refusal is deliberate and is
the same anti-shopping pattern `data/f4/g2/analyze_g2.py` uses for its bars: a
default parameter that let the runner execute un-ratified would let the
parameter be chosen after seeing the result.

EVERY PINNED PARAMETER IS READ FROM THE DOCUMENT, NEVER FROM THIS FILE.
The guard, the fence convention and the parameter root are IMPORTED from the
head-1 runner `backtest_e2.py` (`require_g3`, `extract_params_block`,
`G3Refusal`, `assert_input_shas`, `sha256_file`, `append_run_log`) so the three
heads cannot drift apart: exactly one fenced ```json g3-params block in the
document, whose JSON object is the parameter root. The keys these two heads read
are enumerated in `data/f5/G3_PARAMS_SCHEMA_heads.json` (written by this
module's `--write-schema`, which is how that file stays in sync with
`REQUIRED_HEAD2` / `REQUIRED_HEAD3` below); head 1's own keys are in
`G3_PARAMS_SCHEMA.json`. Head 3 deliberately reads the SAME `fold_quarters`,
`columns.confirmatory_text`, `columns.numeric` and `embedding.pca_k` head 1
reads -- one fold list and one confirmatory block across heads. A missing key is
a REFUSAL, not a default. Hard-coded parameter values exist in exactly one
place: `--selftest`, which runs on SYNTHETIC data only.

`--census` (allowed before G3; F5_PLAN §2 Step 2) computes counts only -- event
counts, text-join coverage, exit counts by kind, per-quarter panel sizes,
per-quarter censorship under a candidate label cut. It fits nothing, and it
computes no feature-versus-outcome association of any kind.

NON-GOALS (HANDOFF.md §1, inherited unconditionally): nothing here places,
queues, recommends or evaluates a trade; there is no expected-return figure and
no "beats the market" framing. Head 2's DV is a realized dispersion ratio and
head 3's label is a corporate event, both dependent variables of a research
measurement.

PORTED, NOT PARAPHRASED
-----------------------
`controls.load_earnings_events`, `controls.load_membership`,
`controls.load_price_matrix` and `controls.resolve_sessions` are IMPORTED from
the byte-frozen `controls.py`. The session chain is therefore identical to
`target_e2.py` and `numeric_features_e2.py`:
    info_date    = max(filing_date, acceptance_date_ET)
    news_session = first session >= info_date (pre-close) / > info_date (post-close)
    pre_session  = news_session - 1
Head 2's [+1, +5] window is placed STRICTLY after the news session and its
trailing window ends at the pre-session, so no price at or after the news
session enters the denominator and no price before the news session enters the
numerator's own sessions.

Run:
    python3 heads_e2.py --census        # counts only, allowed today
    python3 heads_e2.py --selftest      # synthetic known-answer checks
    python3 heads_e2.py --head2         # REFUSES until G3 is ratified
    python3 heads_e2.py --head3         # REFUSES until G3 is ratified
    python3 -m pytest -q test_heads_e2.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

import controls as C  # frozen; importing it executes no I/O
# The head-1 runner owns the shared freeze guard and the document's parameter
# conventions; heads 2 and 3 IMPORT them rather than carrying a second copy
# (lazy-elite, owner 2026-08-24). backtest_e2.py is a sibling F5 module, not a
# frozen E1 one, and nothing here edits it.
import backtest_e2 as BT

REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
F5_DIR = DATA_DIR / "f5"
STATUS_DIR = F5_DIR / "status"

METADATA_DB = DATA_DIR / "filings_metadata_e2.db"
PRICES_PATH = DATA_DIR / "prices_e2.parquet"
COMMITTED_PROVENANCE = DATA_DIR / "hardening" / "controls_results.json"

TEXT_FEATURES = F5_DIR / "text_features_e2.parquet"
TEXT_MANIFEST = F5_DIR / "text_features_e2_manifest.json"
NUMERIC_FEATURES = F5_DIR / "numeric_features_e2.parquet"
NUMERIC_MANIFEST = F5_DIR / "numeric_features_e2_manifest.json"
TARGET_MANIFEST = F5_DIR / "target_e2_manifest.json"

PREREG_PATH = F5_DIR / "G3_PREREGISTRATION.md"
RATIFIED_PATH = F5_DIR / "G3_RATIFIED.json"
PARAMS_SCHEMA_PATH = F5_DIR / "G3_PARAMS_SCHEMA_heads.json"
CENSUS_PATH = F5_DIR / "census_heads.json"
RUN_LOG = BT.RUN_LOG_PATH  # one run log for all three heads
HEAD2_RESULTS = F5_DIR / "results_head2.json"
HEAD3_RESULTS = F5_DIR / "results_head3.json"

#: The document convention is head 1's, imported so the two runners can never
#: disagree about where parameters live: exactly one fenced ```json g3-params
#: block whose JSON object is the parameter root.
FENCE_INFO = BT.FENCE_INFO

# Dotted paths inside that block. A missing one is a refusal, never a
# default (see the module docstring). Documented in G3_PARAMS_SCHEMA_heads.json.
REQUIRED_HEAD2 = (
    "head2.stratum",
    "head2.predictor",
    "head2.direction",
    "head2.event_window_sessions",
    "head2.trailing_sessions",
    "head2.statistic",
    "head2.bootstrap.weights",
    "head2.bootstrap.n_draws",
    "head2.bootstrap.cluster",
    "head2.bootstrap.seed",
)
REQUIRED_HEAD3 = (
    "fold_quarters",
    "head3.horizon_quarters",
    "head3.label_cut",
    "head3.exit_event_kinds",
    "head3.feature_filing_rule",
    "head3.train_label_purge",
    "columns.confirmatory_text",
    "columns.numeric",
    "head3.missing_value_rule",
    "head3.standardize",
    "head3.model",
    "head3.model_params",
    "head3.metric",
    "seeds.primary",
)
# Read only to validate the confirmatory block's embedding component; required
# when any confirmatory text column name starts with EMBEDDING_PREFIX.
EMBEDDING_PCA_K_KEY = "embedding.pca_k"  # head 1 pins it; head 3 validates against it
EMBEDDING_PREFIX = "emb_pc"

# The census sizes the head-2 population under F5_PLAN §3 decision 12's
# DEFAULT predictor so the owner can rule on it. It is a candidate for sizing,
# never a pre-registered parameter: the guarded path reads head2.predictor from
# the ratified document and never falls back to this name.
CENSUS_CANDIDATE_PREDICTOR = "sentiment_negative_share"

SUPPORTED = {
    "head2.statistic": ("ols_slope",),
    "head2.direction": ("positive", "negative"),
    "head2.bootstrap.weights": ("rademacher",),
    "head2.bootstrap.cluster": ("event_quarter",),
    "head3.feature_filing_rule": ("latest_in_quarter", "latest_in_quarter_with_text"),
    # One implemented rule, as in head 1 (`IMPLEMENTED_PURGE_RULES`): "none"
    # was removed on 2026-09-10 because a no-purge head-3 trains on rows whose
    # exit label resolves inside or after the test quarter, and an unimplemented
    # named rule must be a refusal rather than a selectable convention.
    "head3.train_label_purge": ("horizon_end_before_test_start",),
    "head3.missing_value_rule": ("train_median", "drop_row"),
    "head3.model": ("logistic_l2",),
    "head3.metric": ("auc",),
}


#: The refusal type is head 1's, so a caller can catch one exception for all
#: three heads. A fitting path raising it is a deliberate refusal
#: (F5_PLAN.md §1), not a crash and not a bug to be worked around with a
#: default value.
FreezeRefusal = BT.G3Refusal


# ---------------------------------------------------------------------------
# Provenance and the freeze guard
# ---------------------------------------------------------------------------

#: `controls.py::_sha256_file` pattern, via head 1's copy.
sha256_file = BT.sha256_file


def assert_input_shas() -> dict:
    """Every large input is sha-asserted against the committed record.

    The three H1 inputs are pinned in `data/hardening/controls_results.json`;
    the two F5 feature tables are pinned in their own Step 1a manifests. A
    changed frame is a new pre-registration, not a re-run.
    """
    # The two feature parquets carry their own manifests; head 1's helper reads
    # whichever key convention each manifest uses.
    checked = BT.assert_input_shas([(TEXT_FEATURES, TEXT_MANIFEST),
                                    (NUMERIC_FEATURES, NUMERIC_MANIFEST)])
    committed = json.loads(COMMITTED_PROVENANCE.read_text())["provenance"]["inputs"]
    for name, path in (("filings_metadata_e2.db", METADATA_DB),
                       ("prices_e2.parquet", PRICES_PATH)):
        measured = sha256_file(path)
        if measured != committed[name]:
            raise AssertionError(
                f"{name}: sha256 {measured} != the committed record "
                f"{committed[name]} -- a changed frame is a NEW "
                "pre-registration, not a re-run.")
        checked[name] = measured
    return checked


def load_ratified_params(prereg: Path = PREREG_PATH,
                         ratified: Path = RATIFIED_PATH) -> tuple[dict, str]:
    """THE GUARD. Returns (params, doc_sha256) or raises FreezeRefusal.

    Refuses unless `G3_RATIFIED.json` exists and its `doc_sha256` equals the
    measured sha256 of `G3_PREREGISTRATION.md`, and the document carries
    exactly one ```json g3-params fenced block (head 1's convention, parsed by
    `backtest_e2.extract_params_block`) -- not an `f5_parameters` block.
    """
    if not Path(prereg).exists() and not Path(ratified).exists():
        raise FreezeRefusal(
            "BLOCKED: the E2 freeze (F5_PLAN.md §1) is in force. Neither "
            f"{Path(prereg).name} nor {Path(ratified).name} exists. No "
            "association, model fit or statistic is computed. Unblock with an "
            "OWNER ratification recorded in "
            f"{Path(ratified).as_posix()} as doc_sha256 = "
            f"sha256({Path(prereg).name}).")
    guard = BT.require_g3(prereg, ratified)          # existence + sha match
    params = BT.extract_params_block(Path(prereg).read_text())
    return params, guard["doc_sha256"]


def get_param(params: dict, dotted: str):
    """Read one pinned parameter. A missing key is a refusal, not a default."""
    node = params
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise FreezeRefusal(
                f"BLOCKED: the G3 document does not pin {dotted}. heads_e2.py "
                "holds no default for it by design (F5_PLAN.md §1).")
        node = node[part]
    return node


def check_required(params: dict, keys) -> None:
    """All missing pins reported at once, then refuse."""
    missing = []
    for k in keys:
        try:
            get_param(params, k)
        except FreezeRefusal:
            missing.append(k)
    if missing:
        raise FreezeRefusal(
            f"BLOCKED: the G3 document does not pin {missing}. No default "
            "exists in heads_e2.py by design (F5_PLAN.md §1).")
    bad = {}
    for key, allowed in SUPPORTED.items():
        if key in keys:
            value = get_param(params, key)
            if value not in allowed:
                bad[key] = {"pinned": value, "implemented": list(allowed)}
    if bad:
        raise FreezeRefusal(
            "BLOCKED: the G3 document pins a value this runner does not "
            f"implement: {json.dumps(bad, sort_keys=True)}. Implementing it is a "
            "code change reviewed against the ratified document, never a silent "
            "fallback.")


def append_run_log(record: dict) -> None:
    """One line per guarded run, keyed to the ratified document's sha.

    Same log file as head 1 (`backtest_e2.RUN_LOG_PATH`), so a second run of
    any head is visible in one place (F5_PLAN §1).
    """
    BT.append_run_log(RUN_LOG, record)


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Shared loading
# ---------------------------------------------------------------------------

def load_core_ciks(db_path: Path = METADATA_DB) -> set[int]:
    m = C.load_membership(db_path)
    return set(int(c) for c in m.loc[m["stratum"] == "core", "cik"].unique())


def build_head2_events(stratum: str,
                       post_window: tuple[int, int],
                       trailing_sessions: int,
                       db_path: Path = METADATA_DB,
                       prices_path: Path = PRICES_PATH,
                       text_path: Path = TEXT_FEATURES,
                       predictor: str | None = None) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Event frame + coverage counters. NO DV, NO association is computed here.

    Returns (events, counters, price_matrix). `events` carries the session
    positions and the availability flags; `attach_head2_dv` turns those into the
    dependent variable (guarded path only).
    """
    ev = C.load_earnings_events(db_path)
    counters = {"events_all_strata": int(len(ev)),
                "ciks_all_strata": int(ev["cik"].nunique())}
    ev = ev[ev["stratum"] == stratum].copy()
    counters[f"events_{stratum}"] = int(len(ev))
    counters[f"ciks_{stratum}"] = int(ev["cik"].nunique())

    prices = C.load_price_matrix(prices_path)
    priced = set(int(c) for c in prices.columns)
    has_col = ev["cik"].astype(int).isin(priced)
    counters["events_dropped_no_price_column"] = int((~has_col).sum())
    counters["ciks_dropped_no_price_column"] = int(ev.loc[~has_col, "cik"].nunique())
    ev = ev[has_col].copy()

    ev = C.resolve_sessions(ev, prices.index)
    counters["events_dropped_news_session_off_calendar"] = int((ev["news_pos"] < 0).sum())
    ev = ev[ev["news_pos"] > 0].copy()

    lo, hi = int(post_window[0]), int(post_window[1])
    n_sessions = len(prices.index)
    # The forward window must CLOSE under the price snapshot (decision 12's
    # event span) and the trailing window must OPEN inside it.
    ev["window_closes_in_snapshot"] = (ev["news_pos"] + hi) < n_sessions
    ev["trailing_window_in_snapshot"] = (ev["pre_pos"] - int(trailing_sessions)) >= 0
    counters["events_excluded_window_past_snapshot"] = \
        int((~ev["window_closes_in_snapshot"]).sum())
    counters["events_excluded_trailing_window_short"] = \
        int((~ev["trailing_window_in_snapshot"]).sum())

    ev["event_quarter"] = ev["info_date"].dt.to_period("Q").astype(str)
    ev["news_session"] = prices.index[ev["news_pos"].to_numpy()]
    ev["pre_session"] = prices.index[ev["pre_pos"].to_numpy()]

    cols = [CENSUS_CANDIDATE_PREDICTOR if predictor is None else predictor]
    text = pd.read_parquet(text_path, columns=["cik", "accession_number"] + cols)
    # "no text row at all" and "text row whose predictor is null" are different
    # defects and are counted separately, never merged into one number.
    text["_text_row_present"] = True
    ev = ev.merge(text, on=["cik", "accession_number"], how="left")
    ev["_text_row_present"] = ev["_text_row_present"].eq(True)
    counters["events_without_text_features"] = int((~ev["_text_row_present"]).sum())
    counters["events_with_text_row"] = int(ev["_text_row_present"].sum())
    counters["events_with_text_row_but_null_predictor"] = int(
        (ev["_text_row_present"] & ev[cols[0]].isna()).sum())

    # Price availability inside both windows, counted without computing the DV.
    ok, flat, zero_denom = [], 0, 0
    arr = prices.to_numpy(dtype=float)
    pos = {int(c): j for j, c in enumerate(prices.columns)}
    for row in ev.itertuples(index=False):
        if not (row.window_closes_in_snapshot and row.trailing_window_in_snapshot):
            ok.append(False)
            continue
        col = arr[:, pos[int(row.cik)]]
        post = col[row.news_pos + lo - 1: row.news_pos + hi + 1]
        trail = col[row.pre_pos - int(trailing_sessions): row.pre_pos + 1]
        good = (np.isfinite(post).all() and np.isfinite(trail).all()
                and (post > 0).all() and (trail > 0).all())
        ok.append(bool(good))
        if good:
            post_r = post[1:] / post[:-1] - 1.0
            trail_r = trail[1:] / trail[:-1] - 1.0
            flat += int((post_r == 0.0).any())
            zero_denom += int(np.abs(trail_r).mean() == 0.0)
    ev["prices_complete"] = ok
    counters["events_excluded_incomplete_prices"] = int(
        (~ev["prices_complete"] & ev["window_closes_in_snapshot"]
         & ev["trailing_window_in_snapshot"]).sum())
    counters["events_with_a_flat_session_in_post_window"] = int(flat)
    counters["events_with_zero_trailing_denominator"] = int(zero_denom)

    usable = ev["prices_complete"] & ev[cols[0]].notna()
    counters["events_usable_for_head2"] = int(usable.sum())
    counters["clusters_event_quarters_usable"] = int(ev.loc[usable, "event_quarter"].nunique())
    counters["events_by_quarter_usable"] = {
        q: int(n) for q, n in ev.loc[usable, "event_quarter"].value_counts().sort_index().items()}
    counters["events_by_quarter_all_core"] = {
        q: int(n) for q, n in ev["event_quarter"].value_counts().sort_index().items()}
    return ev, counters, prices


def attach_head2_dv(events: pd.DataFrame, prices: pd.DataFrame,
                    post_window, trailing_sessions: int) -> pd.DataFrame:
    """The dependent variable. Still no association -- one column of arithmetic.

    DV = mean |r| over sessions [news+lo, news+hi] / mean |r| over the
    `trailing_sessions` returns ending at the pre-session. Every session index
    in the numerator is STRICTLY greater than the news session's index; every
    session index in the denominator is at most the pre-session's.
    """
    lo, hi = int(post_window[0]), int(post_window[1])
    if lo < 1:
        raise ValueError(f"post_window opens at +{lo}: the numerator must start "
                         "strictly after the news session (decision 12).")
    arr = prices.to_numpy(dtype=float)
    pos = {int(c): j for j, c in enumerate(prices.columns)}
    dv, num, den = [], [], []
    for row in events.itertuples(index=False):
        if not bool(row.prices_complete):
            num.append(np.nan)
            den.append(np.nan)
            dv.append(np.nan)
            continue
        col = arr[:, pos[int(row.cik)]]
        post = col[row.news_pos + lo - 1: row.news_pos + hi + 1]
        trail = col[row.pre_pos - int(trailing_sessions): row.pre_pos + 1]
        n_abs = float(np.abs(post[1:] / post[:-1] - 1.0).mean())
        d_abs = float(np.abs(trail[1:] / trail[:-1] - 1.0).mean())
        num.append(n_abs)
        den.append(d_abs)
        dv.append(n_abs / d_abs if d_abs > 0 else np.nan)
    out = events.copy()
    out["dv_post_mean_abs_return"] = num
    out["dv_trailing_mean_abs_return"] = den
    out["dv_relative_move"] = dv
    return out


# ---------------------------------------------------------------------------
# Head 2 inference: OLS slope + wild-cluster bootstrap (Rademacher)
# ---------------------------------------------------------------------------

def ols_slope(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Slope and intercept of y on x with an intercept term."""
    xc = x - x.mean()
    sxx = float((xc ** 2).sum())
    if sxx == 0:
        raise ValueError("predictor has zero variance; a slope is not identified.")
    slope = float((xc * y).sum() / sxx)
    return slope, float(y.mean() - slope * x.mean())


def rademacher_weights(n_draws: int, n_clusters: int, seed: int) -> np.ndarray:
    """(n_draws, n_clusters) of +-1, one weight per cluster per draw."""
    rng = np.random.default_rng(int(seed))
    return rng.integers(0, 2, size=(int(n_draws), int(n_clusters))) * 2.0 - 1.0


def wild_cluster_bootstrap(x: np.ndarray, y: np.ndarray, clusters: np.ndarray,
                           n_draws: int, seed: int) -> dict:
    """Wild-cluster bootstrap of the OLS slope, null (slope = 0) imposed.

    Residuals come from the RESTRICTED fit (intercept only), each cluster gets
    one Rademacher weight per draw, and the resampled slope is recomputed. The
    draws are a null distribution: the SE is their sd and the p-values are tail
    fractions. FEW-CLUSTERS LIMITATION: with ~39 event quarters this interval is
    approximate and is reported as such wherever the number appears.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    codes, uniq = pd.factorize(pd.Series(clusters), sort=True)
    n_clusters = len(uniq)
    slope, intercept = ols_slope(x, y)
    resid = y - y.mean()                      # restricted: slope imposed = 0
    xc = x - x.mean()
    sxx = float((xc ** 2).sum())
    contrib = xc * resid
    per_cluster = np.bincount(codes, weights=contrib, minlength=n_clusters)
    weights = rademacher_weights(n_draws, n_clusters, seed)
    draws = (weights @ per_cluster) / sxx
    se = float(draws.std(ddof=1))
    return {
        "slope": slope,
        "intercept": intercept,
        "se_wild_cluster": se,
        "n_obs": int(len(y)),
        "n_clusters": int(n_clusters),
        "cluster_sizes": {str(u): int((codes == i).sum()) for i, u in enumerate(uniq)},
        "n_draws": int(n_draws),
        "seed": int(seed),
        "p_two_sided": float(np.mean(np.abs(draws) >= abs(slope))),
        "p_one_sided_positive": float(np.mean(draws >= slope)),
        "null_draws": draws,
        "few_clusters_limitation": (
            f"{n_clusters} clusters (event quarters). The wild-cluster bootstrap "
            "is approximate in this regime; the SE and p-values are reported "
            "with this limitation attached, never alone."),
    }


# ---------------------------------------------------------------------------
# Head 3: exits, panel, labels, folds
# ---------------------------------------------------------------------------

def load_exit_events(db_path: Path = METADATA_DB) -> pd.DataFrame:
    """The stored `distress_events` table, verbatim, with its `items` column.

    Schema (inspected 2026-09-10):
        cik INTEGER, accession_number TEXT, form TEXT, filing_date TEXT,
        items TEXT, event_kind TEXT, PRIMARY KEY (accession_number, event_kind)

    The M&A / distress split decision 13 asks for "by the stored item where
    possible" IS NOT POSSIBLE for Form 25 / Form 15: `items` is NULL on those
    rows (only 8-K rows carry items), so a Form 25 filed because the company
    was acquired is indistinguishable in this table from one filed because it
    was dropped by the exchange. That is why decision 13 scopes the claim to
    "exit". The counts by (event_kind, form) are reported in the census.
    """
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as con:
        ex = pd.read_sql(
            "SELECT cik, accession_number, form, filing_date, items, event_kind "
            "FROM distress_events", con)
    ex["filing_date"] = pd.to_datetime(ex["filing_date"])
    return ex


def build_head3_panel(feature_filing_rule: str,
                      numeric_path: Path = NUMERIC_FEATURES,
                      text_path: Path = TEXT_FEATURES) -> tuple[pd.DataFrame, dict]:
    """One row per (cik, quarter): the CIK's LATEST in-membership filing.

    `numeric_features_e2.parquet` is already the core-stratum, in-membership,
    PIT row universe (its Step 1a report §1), so the panel is a groupby on it;
    the text block is joined on (cik, accession_number) and is NaN where that
    filing has no extracted text (F3/F4 extracted text only for earnings-bearing
    8-Ks and periodic filings). `info_date` -- not filing_date, not report_date
    -- dates the row.
    """
    num = pd.read_parquet(numeric_path)
    num["info_date"] = pd.to_datetime(num["info_date"])
    num["quarter"] = num["info_date"].dt.to_period("Q").astype(str)

    text = pd.read_parquet(text_path)
    text_keys = set(zip(text["cik"].astype(int), text["accession_number"]))
    num["has_text"] = [ (int(c), a) in text_keys
                        for c, a in zip(num["cik"], num["accession_number"]) ]

    counters = {
        "numeric_rows": int(len(num)),
        "numeric_ciks": int(num["cik"].nunique()),
        "numeric_rows_with_text": int(num["has_text"].sum()),
    }
    pool = num if feature_filing_rule == "latest_in_quarter" else num[num["has_text"]]
    pool = pool.sort_values(["cik", "quarter", "info_date", "accession_number"])
    panel = pool.groupby(["cik", "quarter"], as_index=False).tail(1).copy()
    panel = panel.rename(columns={"info_date": "feature_date"})
    panel = panel.merge(text.drop(columns=["filing_date", "form"]),
                        on=["cik", "accession_number"], how="left")

    counters["panel_rows"] = int(len(panel))
    counters["panel_ciks"] = int(panel["cik"].nunique())
    counters["panel_rows_without_text"] = int((~panel["has_text"]).sum())
    counters["panel_rows_by_quarter"] = {
        q: int(n) for q, n in panel["quarter"].value_counts().sort_index().items()}
    return panel.reset_index(drop=True), counters


def label_exits(panel: pd.DataFrame, exits: pd.DataFrame, horizon_quarters: int,
                exit_event_kinds, label_cut) -> tuple[pd.DataFrame, dict]:
    """`exit_within_horizon` + `label_observable`.

    An exit counts when its filing_date is STRICTLY after the feature date and
    at most `horizon_quarters` (as 3-month offsets) after it. A row whose
    horizon end passes `label_cut` is UNOBSERVABLE: its zero is not a measured
    zero, so it is flagged and counted, never scored as a negative.
    """
    cut = pd.Timestamp(label_cut)
    offset = pd.DateOffset(months=3 * int(horizon_quarters))
    ex = exits[exits["event_kind"].isin(list(exit_event_kinds))].copy()
    by_cik: dict[int, np.ndarray] = {
        int(c): np.sort(g["filing_date"].to_numpy())
        for c, g in ex.groupby("cik")}

    out = panel.copy()
    horizon_end = out["feature_date"] + offset
    labels, first_exit = [], []
    for cik, fdate, hend in zip(out["cik"], out["feature_date"], horizon_end):
        dates = by_cik.get(int(cik))
        if dates is None:
            labels.append(0)
            first_exit.append(pd.NaT)
            continue
        hit = dates[(dates > np.datetime64(fdate)) & (dates <= np.datetime64(hend))]
        labels.append(int(len(hit) > 0))
        first_exit.append(pd.Timestamp(hit[0]) if len(hit) else pd.NaT)
    out["exit_within_horizon"] = labels
    out["first_exit_in_horizon"] = first_exit
    out["horizon_end"] = horizon_end
    out["label_observable"] = horizon_end <= cut

    counters = {
        "exit_event_kinds_used": list(exit_event_kinds),
        "exit_rows_matching_kinds": int(len(ex)),
        "exit_ciks_matching_kinds": int(ex["cik"].nunique()),
        "exit_ciks_in_panel": int(len(set(ex["cik"].astype(int))
                                      & set(out["cik"].astype(int)))),
        "label_cut": str(cut.date()),
        "panel_rows_label_observable": int(out["label_observable"].sum()),
        "panel_rows_label_unobservable": int((~out["label_observable"]).sum()),
        "positives_observable": int(out.loc[out["label_observable"],
                                            "exit_within_horizon"].sum()),
    }
    return out, counters


def quarter_end(q: str) -> pd.Timestamp:
    return pd.Period(q, freq="Q").end_time.normalize()


def fold_censored(q: str, horizon_quarters: int, label_cut) -> bool:
    """A fold is censored when its outcome window closes after the label cut."""
    end = quarter_end(q) + pd.DateOffset(months=3 * int(horizon_quarters))
    return bool(end > pd.Timestamp(label_cut))


def auc_score(y: np.ndarray, score: np.ndarray) -> float | None:
    """Mann-Whitney AUC with average ranks for ties. None if one class is empty."""
    y = np.asarray(y, dtype=float)
    score = np.asarray(score, dtype=float)
    n1 = float((y == 1).sum())
    n0 = float((y == 0).sum())
    if n1 == 0 or n0 == 0:
        return None
    ranks = pd.Series(score).rank().to_numpy()
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def logistic_l2_fit(X: np.ndarray, y: np.ndarray, l2: float,
                    max_iter: int, tol: float) -> np.ndarray:
    """Ridge-penalised logistic regression by IRLS. Intercept unpenalised.

    Written here rather than pulled from a new dependency: 20 lines of numpy,
    deterministic, no seed, and it keeps this module's imports identical to the
    rest of the repo (lazy-elite, owner 2026-08-24).
    """
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    Z = np.column_stack([np.ones(len(X)), X])
    beta = np.zeros(Z.shape[1])
    pen = np.full(Z.shape[1], float(l2))
    pen[0] = 0.0
    for _ in range(int(max_iter)):
        mu = 1.0 / (1.0 + np.exp(-(Z @ beta)))
        w = np.clip(mu * (1.0 - mu), 1e-9, None)
        grad = Z.T @ (y - mu) - pen * beta
        hess = (Z * w[:, None]).T @ Z + np.diag(pen) + np.eye(Z.shape[1]) * 1e-8
        step = np.linalg.solve(hess, grad)
        beta = beta + step
        if np.max(np.abs(step)) < float(tol):
            break
    return beta


def logistic_l2_score(beta: np.ndarray, X: np.ndarray) -> np.ndarray:
    Z = np.column_stack([np.ones(len(X)), np.asarray(X, dtype=float)])
    return 1.0 / (1.0 + np.exp(-(Z @ beta)))


def _prepare_matrix(train: pd.DataFrame, test: pd.DataFrame, cols,
                    missing_rule: str, standardize: bool):
    """Training-fold-only imputation and standardisation (no test information)."""
    tr = train[list(cols)].astype(float).copy()
    te = test[list(cols)].astype(float).copy()
    if missing_rule == "drop_row":
        keep_tr = tr.notna().all(axis=1)
        keep_te = te.notna().all(axis=1)
        tr, te = tr[keep_tr], te[keep_te]
    else:  # train_median
        med = tr.median()
        med = med.fillna(0.0)
        keep_tr = pd.Series(True, index=tr.index)
        keep_te = pd.Series(True, index=te.index)
        tr, te = tr.fillna(med), te.fillna(med)
    if standardize:
        mu, sd = tr.mean(), tr.std(ddof=0).replace(0.0, 1.0).fillna(1.0)
        tr, te = (tr - mu) / sd, (te - mu) / sd
    return (tr.to_numpy(dtype=float), te.to_numpy(dtype=float),
            keep_tr.to_numpy(), keep_te.to_numpy())


def run_head3_folds(panel: pd.DataFrame, params: dict) -> list[dict]:
    """One row per pre-registered fold. Censored folds are NOT scored."""
    quarters = list(get_param(params, "fold_quarters"))
    horizon = int(get_param(params, "head3.horizon_quarters"))
    cut = get_param(params, "head3.label_cut")
    text_cols = list(get_param(params, "columns.confirmatory_text"))
    num_cols = list(get_param(params, "columns.numeric"))
    cols = text_cols + num_cols
    missing_rule = get_param(params, "head3.missing_value_rule")
    standardize = bool(get_param(params, "head3.standardize"))
    model_params = get_param(params, "head3.model_params")
    purge = get_param(params, "head3.train_label_purge")
    if purge not in SUPPORTED["head3.train_label_purge"]:
        raise FreezeRefusal(
            f"REFUSED: head3.train_label_purge = {purge!r} has no implementation here "
            f"(implemented: {list(SUPPORTED['head3.train_label_purge'])}). A named rule with no "
            "implementation pre-registers nothing.")

    absent = [c for c in cols if c not in panel.columns]
    if absent:
        raise FreezeRefusal(
            f"REFUSED: the G3 document pins feature columns absent from the "
            f"panel: {absent}. A pinned feature that does not exist cannot be "
            "silently dropped.")
    embeddings = [c for c in text_cols if c.startswith(EMBEDDING_PREFIX)]
    if embeddings:
        k = int(get_param(params, EMBEDDING_PCA_K_KEY))
        if len(embeddings) != k:
            raise FreezeRefusal(
                f"REFUSED: {len(embeddings)} embedding columns pinned in the "
                f"confirmatory block but {EMBEDDING_PCA_K_KEY}={k}.")

    rows = []
    for q in quarters:
        censored = fold_censored(q, horizon, cut)
        # "2018Q1" < "2018Q2" lexicographically equals the calendar order for
        # 4-digit years, which is the whole span of this universe.
        in_quarter = panel[panel["quarter"] == q]
        test = in_quarter[in_quarter["label_observable"]]
        train = panel[(panel["quarter"] < q) & panel["label_observable"]]
        n_train_before_purge = int(len(train))
        if purge == "horizon_end_before_test_start":
            train = train[train["horizon_end"] < pd.Period(q, freq="Q").start_time]
        rec = {
            "test_quarter": q,
            "censored": censored,
            "train_label_purge": purge,
            "n_train_purged": n_train_before_purge - int(len(train)),
            "n_train": int(len(train)),
            # A censored fold still reports its population: the count is the
            # point of reporting it (decision 13). `n_test` is the rows whose
            # label is observable, `n_test_panel_rows` is every panel row in
            # the quarter, observable or not.
            "n_test_panel_rows": int(len(in_quarter)),
            "n_test": int(len(test)),
            "n_test_positive": int(test["exit_within_horizon"].sum()),
            "n_train_positive": int(train["exit_within_horizon"].sum()),
            "test_prevalence": (float(test["exit_within_horizon"].mean())
                                if len(test) else None),
            "train_prevalence": (float(train["exit_within_horizon"].mean())
                                 if len(train) else None),
            "auc": None,
            "status": None,
        }
        if censored:
            rec["status"] = (
                f"CENSORED: the {horizon}-quarter outcome window of {q} closes "
                f"after the label cut {cut}; counted, not scored (decision 13).")
            rows.append(rec)
            continue
        if len(train) == 0 or len(test) == 0:
            rec["status"] = "NOT SCORED: empty train or test fold."
            rows.append(rec)
            continue
        Xtr, Xte, keep_tr, keep_te = _prepare_matrix(
            train, test, cols, missing_rule, standardize)
        ytr = train["exit_within_horizon"].to_numpy()[keep_tr]
        yte = test["exit_within_horizon"].to_numpy()[keep_te]
        rec["n_train_used"], rec["n_test_used"] = int(len(ytr)), int(len(yte))
        if len(set(ytr.tolist())) < 2:
            rec["status"] = "NOT SCORED: the training fold has one class only."
            rows.append(rec)
            continue
        beta = logistic_l2_fit(Xtr, ytr, float(model_params["l2"]),
                               int(model_params["max_iter"]),
                               float(model_params["tol"]))
        rec["auc"] = auc_score(yte, logistic_l2_score(beta, Xte))
        rec["status"] = ("SCORED" if rec["auc"] is not None else
                         "NOT SCORED: the test fold has one class only "
                         "(AUC undefined); prevalence reported instead.")
        rows.append(rec)
    return rows


# ---------------------------------------------------------------------------
# Guarded runners
# ---------------------------------------------------------------------------

def reverify_guard(doc_sha: str, prereg: Path, ratified: Path) -> None:
    """DEFENCE IN DEPTH: re-measure the ratified document here, inside the
    runner, and refuse unless it equals the sha the caller handed in.

    `main()` already runs the guard, but a fabricated `doc_sha` string passed
    straight to a runner would otherwise reach a fit. A sha argument is a
    caller's claim; the ratification on disk is the fact. The path arguments
    exist so a synthetic fixture can point the re-check at its own document --
    they default to the real ones.
    """
    measured = BT.require_g3(prereg, ratified)["doc_sha256"]
    if measured != doc_sha:
        raise FreezeRefusal(
            f"BLOCKED: this runner was handed doc_sha256 {doc_sha!r}, but "
            f"{Path(prereg).name} measures {measured!r}. A sha argument is not a "
            "ratification; nothing was computed.")


def run_head2(params: dict, doc_sha: str, prereg: Path = PREREG_PATH,
              ratified: Path = RATIFIED_PATH) -> dict:
    reverify_guard(doc_sha, prereg, ratified)
    check_required(params, REQUIRED_HEAD2)
    t0 = time.time()
    shas = assert_input_shas()
    predictor = get_param(params, "head2.predictor")
    post_window = get_param(params, "head2.event_window_sessions")
    trailing = int(get_param(params, "head2.trailing_sessions"))
    events, counters, prices = build_head2_events(
        stratum=get_param(params, "head2.stratum"),
        post_window=post_window, trailing_sessions=trailing,
        predictor=predictor)
    events = attach_head2_dv(events, prices, post_window, trailing)
    use = events[events["dv_relative_move"].notna() & events[predictor].notna()]
    boot = wild_cluster_bootstrap(
        use[predictor].to_numpy(), use["dv_relative_move"].to_numpy(),
        use["event_quarter"].to_numpy(),
        int(get_param(params, "head2.bootstrap.n_draws")),
        int(get_param(params, "head2.bootstrap.seed")))
    draws = boot.pop("null_draws")
    out = {
        "head": 2,
        "generated_utc": now_utc(),
        "g3_doc_sha256": doc_sha,
        "parameters": params.get("head2"),
        "inputs": shas,
        "census": counters,
        "estimate": boot,
        "null_draw_quantiles": {str(p): float(np.percentile(draws, p))
                                for p in (2.5, 50, 97.5)},
        "disclosures": head_disclosures(),
        "runtime_seconds": round(time.time() - t0, 2),
    }
    HEAD2_RESULTS.write_text(json.dumps(out, indent=1, sort_keys=True, default=str))
    append_run_log({"utc": out["generated_utc"], "head": 2,
                    "g3_doc_sha256": doc_sha,
                    "artifact": HEAD2_RESULTS.name})
    return out


def run_head3(params: dict, doc_sha: str, prereg: Path = PREREG_PATH,
              ratified: Path = RATIFIED_PATH) -> dict:
    reverify_guard(doc_sha, prereg, ratified)
    check_required(params, REQUIRED_HEAD3)
    t0 = time.time()
    shas = assert_input_shas()
    panel, counters = build_head3_panel(get_param(params, "head3.feature_filing_rule"))
    exits = load_exit_events()
    panel, label_counters = label_exits(
        panel, exits, int(get_param(params, "head3.horizon_quarters")),
        get_param(params, "head3.exit_event_kinds"),
        get_param(params, "head3.label_cut"))
    folds = run_head3_folds(panel, params)
    out = {
        "head": 3,
        "generated_utc": now_utc(),
        "g3_doc_sha256": doc_sha,
        "parameters": params.get("head3"),
        "fold_quarters": list(get_param(params, "fold_quarters")),
        "inputs": shas,
        "census": {**counters, **label_counters},
        "folds": folds,
        "n_censored_folds": int(sum(f["censored"] for f in folds)),
        "n_scored_folds": int(sum(f["status"] == "SCORED" for f in folds)),
        "disclosures": head_disclosures(),
        "runtime_seconds": round(time.time() - t0, 2),
    }
    HEAD3_RESULTS.write_text(json.dumps(out, indent=1, sort_keys=True, default=str))
    append_run_log({"utc": out["generated_utc"], "head": 3,
                    "g3_doc_sha256": doc_sha,
                    "artifact": HEAD3_RESULTS.name})
    return out


def head_disclosures() -> dict:
    """Regenerated from the Step 1a manifest, never hand-typed prose."""
    caveats = json.loads(TEXT_MANIFEST.read_text())["caveat_constants"]
    return {
        "validation": (
            "Walk-forward by construction: head 3 trains only on quarters "
            "strictly before the test quarter; head 2 is an event study whose "
            "predictor is dated at the event filing and whose windows are "
            "placed strictly after the news session. No number here is an "
            "expected return and nothing here is a trading signal."),
        "benchmark_incomparability": (
            "E1 and E2 backtest numbers are numerically incomparable (different "
            "benchmark). Head 2's DV is benchmark-free."),
        "g2_caveat_constants": caveats,
        "head2_predictor_caveat": (
            "sentiment is the field G2 ruled INDETERMINATE; the escorts that "
            "must travel with a sentiment-based row (including the stored "
            "NEGATIVE recall and precision) are enumerated in the G3 document, "
            "§11."),
        "head2_dividend_caveat": (
            "Prices are split-adjusted only. The DV is NOT dividend-immune: an "
            "ex-dividend session inside the post window inflates it."),
        "head2_forward_fill_caveat": (
            "controls.load_price_matrix forward-fills inside each CIK's own "
            "coverage window, so a non-trading gap appears as a zero return and "
            "deflates both DV components; the count of events with a flat "
            "session in the post window is in the census block."),
        "head3_claim_scope": (
            "The claim is 'exit', never 'distress': the stored distress_events "
            "table carries `items` only on 8-K rows, so Form 25 / Form 15 exits "
            "cannot be split into M&A and distress."),
        "label_quality": (
            "Label-quality constants are E2's own (teacher v1.2 spot-check and "
            "G2); E1's 36.6%/63.4% constants are never carried onto Qwen labels."),
    }


# ---------------------------------------------------------------------------
# Census (allowed before G3): counts only, zero associations
# ---------------------------------------------------------------------------

def _exits_followed_by_later_filings(exits: pd.DataFrame, panel: pd.DataFrame,
                                     days: int = 365) -> dict:
    """How many stored 'exit' rows are followed by the same CIK still filing.

    A pure count, no association. It exists because the census must tell G3
    what `exit_event_kinds` would actually label: a Form 25 can be filed for
    one security class while the company keeps filing, in which case the row
    is not a company exit at all. Counted per event_kind.
    """
    last_seen = panel.groupby("cik")["feature_date"].max()
    out = {}
    for kind, g in exits.groupby("event_kind"):
        g = g[g["cik"].isin(last_seen.index)]
        later = [bool(last_seen[int(c)] > d + pd.Timedelta(days=days))
                 for c, d in zip(g["cik"], g["filing_date"])]
        out[kind] = {"rows_on_panel_ciks": int(len(g)),
                     "rows_with_a_later_in_membership_filing": int(sum(later))}
    return out


def run_census(candidate_post_window=(1, 5), candidate_trailing=60,
               candidate_horizon_quarters=4) -> dict:
    """Counts for the G3 table's 'measured population' column.

    The three `candidate_*` arguments are NOT pre-registered parameters: they
    are the F5_PLAN §3 defaults used to SIZE the population so the owner can
    rule on them. Nothing is fitted, and no feature-versus-outcome association
    is computed anywhere in this function. The per-quarter censorship map is
    reported for every panel quarter because the fold list does not exist until
    G3 ratifies it.
    """
    t0 = time.time()
    shas = assert_input_shas()
    ev, head2_counters, prices = build_head2_events(
        stratum="core", post_window=candidate_post_window,
        trailing_sessions=candidate_trailing)
    head2_counters["candidate_predictor"] = CENSUS_CANDIDATE_PREDICTOR
    head2_counters["candidate_post_window"] = list(candidate_post_window)
    head2_counters["candidate_trailing_sessions"] = int(candidate_trailing)
    head2_counters["membership_filter_note"] = (
        "controls.load_earnings_events filters membership on filing_date; the "
        "F5 target table filters on info_date = max(filing_date, "
        "acceptance_ET). The two differ for filings accepted after the spell "
        "boundary; the ported loader is used unchanged.")

    exits = load_exit_events()
    core = load_core_ciks()
    by_kind = (exits.groupby(["event_kind", "form"])
               .agg(n=("cik", "size"), n_ciks=("cik", "nunique"))
               .reset_index())
    head3 = {
        "exit_rows_total": int(len(exits)),
        "exit_ciks_total": int(exits["cik"].nunique()),
        "exit_rows_with_items_stored": int(exits["items"].notna().sum()),
        "exit_rows_by_kind_and_form": [
            {"event_kind": r.event_kind, "form": r.form, "n": int(r.n),
             "n_ciks": int(r.n_ciks)} for r in by_kind.itertuples(index=False)],
        "exit_rows_core_stratum": int(exits["cik"].isin(core).sum()),
        "exit_ciks_core_stratum": int(exits.loc[exits["cik"].isin(core),
                                                "cik"].nunique()),
        "exit_filing_date_min": str(exits["filing_date"].min().date()),
        "exit_filing_date_max": str(exits["filing_date"].max().date()),
        "ma_vs_distress_split": (
            "NOT AVAILABLE from the stored data: `items` is NULL on "
            f"{int(exits['items'].isna().sum())} of {len(exits)} rows (every "
            "Form 25 / Form 15 row). Only the 8-K item-1.03 rows carry items, "
            "so a Form 25 filed after an acquisition is indistinguishable here "
            "from one filed after an exchange delisting. Decision 13's claim "
            "scope ('exit', never 'distress') is what this measurement "
            "supports."),
    }
    for rule in ("latest_in_quarter", "latest_in_quarter_with_text"):
        panel, counters = build_head3_panel(rule)
        head3[f"panel_{rule}"] = counters
        if rule == "latest_in_quarter":
            quarters = sorted(panel["quarter"].unique())
            candidate_cut = exits["filing_date"].max()
            head3["candidate_label_cut"] = str(candidate_cut.date())
            head3["candidate_label_cut_source"] = (
                "max(distress_events.filing_date) -- a CANDIDATE only; the "
                "label cut is pinned by the G3 document.")
            head3["quarter_censorship_under_candidate_cut"] = {
                q: bool(fold_censored(q, candidate_horizon_quarters, candidate_cut))
                for q in quarters}
            head3["last_uncensored_quarter_under_candidate_cut"] = next(
                (q for q in reversed(quarters)
                 if not fold_censored(q, candidate_horizon_quarters, candidate_cut)),
                None)
            head3["candidate_horizon_quarters"] = int(candidate_horizon_quarters)
            head3["exit_rows_still_filing_a_year_later"] = \
                _exits_followed_by_later_filings(exits, panel)

    census = {
        "generated_utc": now_utc(),
        "module": "heads_e2.py",
        "module_sha256": sha256_file(Path(__file__)),
        "controls_py_sha256": sha256_file(REPO_ROOT / "controls.py"),
        "mode": "census",
        "freeze_statement": (
            "F5_PLAN.md §1: this census fits nothing and computes no "
            "information coefficient, correlation, slope or any other "
            "feature-versus-outcome association. G3_RATIFIED.json exists="
            f"{RATIFIED_PATH.exists()}."),
        "computed_associations_with_outcomes": 0,
        "network_calls": 0,
        "inputs": shas,
        "price_snapshot": json.loads(TARGET_MANIFEST.read_text())["price_snapshot"],
        "head2": head2_counters,
        "head3": head3,
        "runtime_seconds": round(time.time() - t0, 2),
    }
    CENSUS_PATH.write_text(json.dumps(census, indent=1, sort_keys=True, default=str))
    return census


# ---------------------------------------------------------------------------
# Parameter schema (documentation artifact, kept in sync with the code)
# ---------------------------------------------------------------------------

def params_schema() -> dict:
    def entry(key, typ, meaning, example):
        return {"key": key, "type": typ,
                "meaning": meaning, "example": example,
                "allowed": list(SUPPORTED[key]) if key in SUPPORTED else None}
    return {
        "written_by": "heads_e2.py --write-schema",
        "purpose": (
            "The keys heads_e2.py READS from the single fenced ```"
            + FENCE_INFO + " block inside data/f5/G3_PREREGISTRATION.md. "
            "heads_e2.py holds no default for any of them: a missing key is a "
            "refusal. This file documents what G3 must pin for heads 2 and 3; "
            "it is not itself a parameter source and is never read at run "
            "time. Head 1's keys are documented in G3_PARAMS_SCHEMA.json; the "
            "four shared keys (fold_quarters, columns.confirmatory_text, "
            "columns.numeric, embedding.pca_k) appear in both by design."),
        "guard": {
            "rule": ("data/f5/G3_RATIFIED.json must exist and its doc_sha256 "
                     "must equal sha256(data/f5/G3_PREREGISTRATION.md)"),
            "on_failure": "FreezeRefusal; exit code 2; nothing is computed",
        },
        "block_format": (
            "Exactly one fenced block ```" + FENCE_INFO + " ... ``` in the "
            "document; its parsed JSON object is the parameter root. Two such "
            "blocks is a refusal (parameters must have one unambiguous "
            "source). Parsed by backtest_e2.extract_params_block."),
        "required_head2": [
            entry("head2.stratum", "string",
                  "which stratum's events are in scope; the confirmatory arm is core",
                  "core"),
            entry("head2.predictor", "string",
                  "column of data/f5/text_features_e2.parquet used as the predictor",
                  "sentiment_negative_share"),
            entry("head2.direction", "string",
                  "pre-registered sign of the association; fixes the one-sided p",
                  "positive"),
            entry("head2.event_window_sessions", "[int, int]",
                  "inclusive session offsets AFTER the news session for the DV "
                  "numerator; the opening offset must be >= 1",
                  [1, 5]),
            entry("head2.trailing_sessions", "int",
                  "number of daily returns in the DV denominator, ending at the "
                  "pre-session",
                  60),
            entry("head2.statistic", "string",
                  "the estimator of the association", "ols_slope"),
            entry("head2.bootstrap.weights", "string",
                  "bootstrap weight family", "rademacher"),
            entry("head2.bootstrap.n_draws", "int", "bootstrap draws", 2000),
            entry("head2.bootstrap.cluster", "string",
                  "clustering unit for the wild bootstrap", "event_quarter"),
            entry("head2.bootstrap.seed", "int", "bootstrap seed", 0),
        ],
        "required_head3": [
            entry("fold_quarters", "[string]",
                  "the HEAD-1 fold list, read from the same key head 1 reads; "
                  "head 3 scores the same folds",
                  ["2018Q1", "2018Q2"]),
            entry("head3.horizon_quarters", "int",
                  "exit horizon after the feature date, as 3-month offsets", 4),
            entry("head3.label_cut", "string (YYYY-MM-DD)",
                  "last date on which an exit would have been observed; folds "
                  "whose horizon closes after it are censored, not scored",
                  "2026-08-17"),
            entry("head3.exit_event_kinds", "[string]",
                  "which distress_events.event_kind values count as an exit",
                  ["delisting_form_25", "deregistration_form_15"]),
            entry("head3.feature_filing_rule", "string",
                  "which filing in the quarter supplies the features",
                  "latest_in_quarter"),
            entry("head3.train_label_purge", "string",
                  "whether training rows whose exit horizon closes on or after "
                  "the test quarter's start are purged. "
                  "'horizon_end_before_test_start' is the head-3 analogue of "
                  "decision 5's label purge and is the ONLY implemented rule "
                  "(as in head 1, one purge rule); a no-purge convention would "
                  "train on rows whose labels resolve inside or after the test "
                  "quarter and is a refusal here, not a selectable value. This "
                  "module holds no default: the key is leakage-relevant and "
                  "must be pinned explicitly",
                  "horizon_end_before_test_start"),
            entry("columns.confirmatory_text", "[string]",
                  "the confirmatory text block (decision 3), shared with head "
                  f"1; embedding columns are named {EMBEDDING_PREFIX}* and "
                  f"their count must equal {EMBEDDING_PCA_K_KEY}",
                  ["sentiment_negative_share", "guidance_any_present"]),
            entry("columns.numeric", "[string]",
                  "the numeric baseline block, shared with head 1",
                  ["log_total_assets"]),
            entry("head3.missing_value_rule", "string",
                  "how a missing feature is handled; imputation is computed on "
                  "the training fold only",
                  "train_median"),
            entry("head3.standardize", "bool",
                  "standardise features by training-fold mean/sd", True),
            entry("head3.model", "string", "the classifier", "logistic_l2"),
            entry("head3.model_params", "object",
                  "l2 (ridge penalty), max_iter, tol",
                  {"l2": 1.0, "max_iter": 50, "tol": 1e-8}),
            entry("head3.metric", "string", "the per-fold metric", "auc"),
            entry("seeds.primary", "int",
                  "the primary seed recorded with the run", 0),
        ],
        "conditionally_required": [
            entry(EMBEDDING_PCA_K_KEY, "int",
                  "number of pooled-embedding principal components; required "
                  "when the confirmatory text block names any "
                  f"{EMBEDDING_PREFIX}* column",
                  16),
        ],
        "read_by_head1_not_by_this_module": [
            "spec.*", "margin.*", "purge_rule", "loco.*", "se.*", "tost.*",
            "dedup.*", "overlap.*", "form_ablation_forms",
            "post_2019_first_quarter", "bootstrap_anchor.*",
        ],
        "shared_with_head1": [
            "fold_quarters", "columns.confirmatory_text", "columns.numeric",
            EMBEDDING_PCA_K_KEY, "seeds.primary", "head2.trailing_sessions",
            "head2.event_window_sessions", "head3.horizon_quarters",
            "head3.metric",
        ],
    }


# ---------------------------------------------------------------------------
# --selftest: SYNTHETIC data only; the only place literals may appear
# ---------------------------------------------------------------------------

def selftest() -> int:
    """Known-answer checks on synthetic frames. Touches no data/f5 artifact."""
    checks = []

    # DV: a flat trailing series and a known post window.
    cal = pd.date_range("2020-01-01", periods=80, freq="B")
    closes = np.full(80, 100.0)
    closes[1::2] = 101.0                      # |r| = 1/101 and 1/100 alternating
    closes[70:76] = [100.0, 110.0, 99.0, 108.9, 98.01, 107.811]
    prices = pd.DataFrame({7: closes}, index=cal)
    ev = pd.DataFrame({"cik": [7], "news_pos": [69], "pre_pos": [68],
                       "prices_complete": [True]})
    out = attach_head2_dv(ev, prices, (1, 5), 60)
    dv = float(out["dv_relative_move"].iloc[0])
    checks.append(("dv is finite and positive", np.isfinite(dv) and dv > 0, dv))
    post_only = float(out["dv_post_mean_abs_return"].iloc[0])
    # news session = index 69, so sessions [+1, +5] are indices 70..74 and the
    # five returns each use the previous close, the earliest being index 69's.
    checks.append(("post window uses exactly the 5 returns of sessions +1..+5",
                   abs(post_only - np.mean(np.abs(closes[70:75] / closes[69:74] - 1))) < 1e-12,
                   post_only))

    # The denominator cannot see the news session or later.
    poisoned = prices.copy()
    poisoned.iloc[69:] = 1.0
    out2 = attach_head2_dv(ev, poisoned, (1, 5), 60)
    checks.append(("denominator is unchanged when every session >= news is poisoned",
                   abs(float(out2["dv_trailing_mean_abs_return"].iloc[0])
                       - float(out["dv_trailing_mean_abs_return"].iloc[0])) < 1e-15,
                   float(out2["dv_trailing_mean_abs_return"].iloc[0])))

    # Wild-cluster bootstrap shape and determinism.
    rng = np.random.default_rng(0)
    x = rng.normal(size=200)
    y = 0.5 * x + rng.normal(size=200)
    cl = np.repeat(np.arange(10), 20)
    b1 = wild_cluster_bootstrap(x, y, cl, 500, 0)
    b2 = wild_cluster_bootstrap(x, y, cl, 500, 0)
    checks.append(("bootstrap is deterministic given the seed",
                   b1["se_wild_cluster"] == b2["se_wild_cluster"],
                   b1["se_wild_cluster"]))
    checks.append(("bootstrap draws have shape (n_draws,)",
                   b1["null_draws"].shape == (500,), b1["null_draws"].shape))
    w = rademacher_weights(4, 3, 0)
    checks.append(("weights are +-1 with one per cluster per draw",
                   w.shape == (4, 3) and set(np.unique(w)) <= {-1.0, 1.0}, w.tolist()))

    # AUC known answers.
    checks.append(("perfect separation scores 1.0",
                   auc_score(np.array([0, 0, 1, 1]), np.array([0.1, 0.2, 0.8, 0.9])) == 1.0,
                   1.0))
    checks.append(("all-tied scores give 0.5",
                   auc_score(np.array([0, 1, 0, 1]), np.array([1.0] * 4)) == 0.5, 0.5))

    # Exit labelling and censoring.
    panel = pd.DataFrame({
        "cik": [1, 2], "quarter": ["2020Q1", "2020Q1"],
        "feature_date": pd.to_datetime(["2020-02-01", "2020-02-01"]),
    })
    exits = pd.DataFrame({
        "cik": [1, 2], "accession_number": ["a", "b"], "form": ["25", "25"],
        "filing_date": pd.to_datetime(["2020-06-01", "2021-06-01"]),
        "items": [None, None], "event_kind": ["delisting_form_25"] * 2})
    labelled, _ = label_exits(panel, exits, 4, ["delisting_form_25"], "2021-12-31")
    checks.append(("exit inside the horizon is a 1, outside is a 0",
                   labelled["exit_within_horizon"].tolist() == [1, 0],
                   labelled["exit_within_horizon"].tolist()))
    checks.append(("a fold whose horizon closes past the label cut is censored",
                   fold_censored("2021Q4", 4, "2021-12-31") is True
                   and fold_censored("2020Q1", 4, "2021-12-31") is False, True))

    # The guard refuses on a repo with no ratified document.
    try:
        load_ratified_params()
        guard_ok = RATIFIED_PATH.exists()
    except FreezeRefusal:
        guard_ok = True
    checks.append(("the freeze guard refuses without a ratified G3 document",
                   guard_ok, RATIFIED_PATH.exists()))

    failed = 0
    for name, ok, measured in checks:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  [measured: {measured}]")
        failed += 0 if ok else 1
    print(f"--selftest: {len(checks) - failed} passed, {failed} failed "
          "(synthetic data only)")
    return 0 if failed == 0 else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--census", action="store_true",
                    help="counts only; allowed before G3 (writes census_heads.json)")
    ap.add_argument("--selftest", action="store_true",
                    help="known-answer checks on synthetic data")
    ap.add_argument("--write-schema", action="store_true",
                    help="write data/f5/G3_PARAMS_SCHEMA_heads.json")
    ap.add_argument("--head2", action="store_true", help="run head 2 (needs G3)")
    ap.add_argument("--head3", action="store_true", help="run head 3 (needs G3)")
    ap.add_argument("--all", action="store_true", help="run both heads (needs G3)")
    args = ap.parse_args(argv)

    if args.write_schema:
        PARAMS_SCHEMA_PATH.write_text(json.dumps(params_schema(), indent=1))
        print(f"wrote {PARAMS_SCHEMA_PATH}")
    if args.selftest:
        return selftest()
    if args.census:
        c = run_census()
        print(json.dumps({"head2_usable_events": c["head2"]["events_usable_for_head2"],
                          "head2_clusters": c["head2"]["clusters_event_quarters_usable"],
                          "head3_panel_rows":
                              c["head3"]["panel_latest_in_quarter"]["panel_rows"],
                          "runtime_seconds": c["runtime_seconds"]}, indent=1))
        print(f"wrote {CENSUS_PATH}")
        return 0
    if not (args.head2 or args.head3 or args.all):
        if args.write_schema:
            return 0
        ap.print_help()
        return 0

    try:
        params, doc_sha = load_ratified_params(PREREG_PATH, RATIFIED_PATH)
    except FreezeRefusal as exc:
        print(str(exc), file=sys.stderr)
        print("No head was run. This refusal is the enforcement of F5_PLAN.md §1 "
              "and is expected until the owner ratifies G3.", file=sys.stderr)
        return 2
    try:
        if args.head2 or args.all:
            print(json.dumps(run_head2(params, doc_sha)["estimate"], indent=1))
        if args.head3 or args.all:
            print(json.dumps(run_head3(params, doc_sha)["folds"], indent=1))
    except FreezeRefusal as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
