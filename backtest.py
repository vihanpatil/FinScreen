"""
backtest.py -- FinScreen Phase C walk-forward backtest.

Reads `data/features.parquet` (built by `features.py`) and runs a
hand-written, expanding-window, walk-forward comparison of two XGBoost
screening-score models -- text+numeric vs. numeric-only -- against the
identical target and identical folds. Writes `data/backtest_report.md`.

This is explicitly NOT a trading simulator (DISCOVERY.md §4/§7, ROADMAP.md
non-goals): no position sizing, no execution, no portfolio construction, no
transaction costs. The only outputs are (1) a per-fold Spearman rank
correlation between predicted score and realized forward excess return
("information coefficient", a standard screening-quality metric borrowed
from equity research, not a trading metric) and (2) a per-fold top-vs-
bottom-quintile spread of REALIZED excess return, which describes what a
research screen would have separated, not a return anyone earned or is
promised to earn. See the non-goals note repeated verbatim at the top of
`data/backtest_report.md`.

-----------------------------------------------------------------------
Why XGBoost, not LightGBM
-----------------------------------------------------------------------
Either would do. XGBoost was picked, and the honest record of why is:
(1) it was already importable in this environment, whereas LightGBM was
not -- the initial reasoning was that LightGBM's macOS wheel needs
`libomp.dylib` and XGBoost would avoid introducing a new system
dependency. **That reasoning turned out to be wrong**: XGBoost's compiled
extension needs `libomp.dylib` on macOS too, so `brew install libomp` was
run anyway and is recorded as a prerequisite in `requirements-quant.txt`.
The dependency was incurred either way; the library choice did not avoid
it. (2) With ~500 rows and ~10-40 features, the two libraries' well-known
performance/scale differences (LightGBM's histogram speed advantage on
large data) are irrelevant -- model quality at this scale is dominated by
the tiny-N/overfitting risk both share equally. Nothing here claims
XGBoost is intrinsically better for this problem.

-----------------------------------------------------------------------
Walk-forward fold design
-----------------------------------------------------------------------
Sort every observation by `filing_date` (public availability date --
`features.py` never uses `report_date`/`period_end` for this). Bucket into
calendar quarters. Burn in on the first 6 quarters (2023-08-15 through
2024-12-31, 274 observations after dropping incomplete-target-window rows)
as the initial training set, then walk forward ONE QUARTER AT A TIME as the
test fold, expanding the training window to include everything before it
each time (never re-ordering, never shuffling). This produces 6 test folds
(2025 Q1-Q4, 2026 Q1-Q2), each ~46-53 observations.

Quarterly test folds after a minimum training burn-in, chosen over either
extreme: one single train/test split would hide fold-to-fold variance
entirely, and ~12 tiny per-quarter-from-the-start folds would be unstable
at the ~300-independent-observation scale of this universe. HANDOFF.md §7's
standing rule is the binding constraint here -- "expanding window, never a
random shuffle; report per-fold spreads, never a single point estimate."

-----------------------------------------------------------------------
A real, load-bearing sample-size caveat: 581 usable rows is NOT 581
independent observations
-----------------------------------------------------------------------
25 companies x ~12 quarters is the ~300-observation scale this universe
naturally implies. This backtest's row count (581 with a usable target) is
roughly double that because `features.py`'s unit of observation is the
FILING, not the company-quarter, and most companies file TWO filings per
quarter (an 8-K earnings release, then a 10-Q/10-K one to two days later).
Those two filings' forward-return target windows overlap by 61-62 of their
63 trading days -- they are, for backtest purposes, nearly the same bet
counted twice. Every per-fold N reported below should be read as roughly
HALF that many independent company-quarter observations. This is stated
here plainly, once, rather than re-derived per number; `data/
backtest_report.md` repeats it verbatim near the top.

-----------------------------------------------------------------------
Metrics
-----------------------------------------------------------------------
Per fold, per model:
  - Spearman rank IC: scipy.stats.spearmanr(predicted_score,
    target_excess_return) over the test fold only.
  - Top-vs-bottom quintile spread: sort the test fold by predicted score;
    mean realized target_excess_return of the top 20% minus the bottom
    20% (via pandas.qcut with duplicates='drop', which can produce fewer
    than 5 bins on tied scores in a small fold -- handled and reported
    when it happens, not silently skipped).

No single point estimate is reported as "the" result -- every table below
is per-fold, plus the cross-fold mean/std/min/max as a SUMMARY of the
per-fold spread, never a replacement for seeing the per-fold rows.

-----------------------------------------------------------------------
spearman_p is UNADJUSTED for non-independence (MAJOR #3 fix, red-team
review) -- read this before trusting any p-value below
-----------------------------------------------------------------------
`scipy.stats.spearmanr`'s p-value assumes the paired observations it is
given are i.i.d. They are not: per the sample-size caveat above, roughly
half of every fold's rows are a near-duplicate (company, quarter) pair (an
8-K and its companion 10-Q/10-K, filed a few days apart, whose
63-trading-day forward-return windows overlap by 61-62/63 days --
independently measured on this corpus, within-pair |target| differences
have median 0.0/mean 0.0228 among non-same-day pairs vs. a cross-sectional
std of 0.1154 -- see "Company-quarter deduplication" below for the full
methodology). Treating each of those pairs as two independent draws makes
`spearman_p` anti-conservative (overstates significance) for every fold,
including the folds that would otherwise read as "significant" at p<0.05.
Every `spearman_p` column below carries this caveat and is reported
alongside a SEPARATE `spearman_p_dedup` computed on a deduplicated subset
(one row per near-duplicate cluster, keeping the LATER filing) -- read the
dedup column, not the raw one, if a p-value is going to be used for
anything beyond "did the sign flip."

-----------------------------------------------------------------------
Form-controlled ablation (MAJOR #4 fix, red-team review)
-----------------------------------------------------------------------
`share_chunks_risk_factors` / `share_chunks_mda` / `share_chunks_ex99_press_release`
/ `redflag_any_rate_press` are near-perfect proxies for which SEC form a row
is (verified on this corpus: 8-Ks structurally cannot carry RISK_FACTORS or
MDA chunks; MDA/RISK_FACTORS come from 10-Q/10-K; EX99_PRESS_RELEASE comes
from 8-Ks almost exclusively) -- so any feature-importance ranking that
puts these features high could be detecting "is this row a 10-Q/10-K vs. an
8-K" rather than anything about the TEXT CONTENT of the filing.
`run_form_controlled_ablation()` reruns the identical walk-forward
comparison (same features, same burn-in, same expanding-window discipline)
restricted to 10-Q/10-K observations only (8-Ks dropped) -- if the
text-vs-numeric IC delta survives on this form-homogeneous subset, that is
evidence the text features are contributing something beyond form-type
detection; if it does not, that is evidence it mostly was not. Per-fold N
is small on this restricted subset (roughly half of the already-small
full-sample folds) and is reported plainly, not smoothed over.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from xgboost import XGBRegressor

import features as F

REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
FEATURES_PATH = DATA_DIR / "features.parquet"
BACKTEST_REPORT_OUTPUT = DATA_DIR / "backtest_report.md"

TARGET_COL = "target_excess_return"
FILING_DATE_COL = "filing_date"

NUMERIC_FEATURES = F.NUMERIC_FEATURE_NAMES
TEXT_FEATURES = F.TEXT_FEATURE_NAMES_NON_REDFLAG + F.RED_FLAG_FEATURE_NAMES
FULL_FEATURES = NUMERIC_FEATURES + TEXT_FEATURES

# Burn-in: everything with filing_date in a quarter before this is training-
# only (never a test fold). 2025-01-01 means the burn-in covers 2023 Q3
# through 2024 Q4 -- 6 calendar quarters.
BURN_IN_END = pd.Timestamp("2025-01-01")

XGB_PARAMS = dict(
    n_estimators=100,
    max_depth=3,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_lambda=1.0,
    random_state=42,
    n_jobs=1,
)

# Form-controlled ablation (MAJOR #4): 8-Ks structurally cannot carry
# RISK_FACTORS/MDA chunks and almost never carry press-release chunks
# either way once excluded -- restricting to 10-Q/10-K removes the
# form-type confound at the observation-set level, not just as a feature.
FORM_ABLATION_FORMS = {"10-Q", "10-K"}

# Company-quarter deduplication (MAJOR #3): GAP_DAYS=5 clusters same-ticker
# filings within 5 calendar days of each other into one "company-quarter"
# event. Empirically justified against the REAL 581-observation backtest
# frame (not asserted): sweeping gap thresholds from 3 to 14 days produces
# NO 3+-filing cluster at ANY threshold in that range (verified in-code by
# assign_company_quarter_clusters()'s own construction, which would make
# cluster sizes >2 detectable if they occurred) -- meaning there is no risk
# of this threshold accidentally merging two genuinely different quarters
# (the smallest real gap between two distinct quarterly filing EVENTS for
# any ticker is far larger than 14 days; see the >60-day minimum gap in the
# form-controlled-ablation subset, which contains no near-duplicate pairs
# at all). At GAP_DAYS=5 specifically: 348 singleton filings + 141
# two-filing clusters = 489 clusters from the 630 raw observations, and
# 140/141 of those pairs are exactly an (8-K, 10-Q/10-K) combination (the
# other is two 8-Ks filed the same calendar day) -- matching the red-team
# finding's own characterization ("8-K + 10-Q/10-K filed 1-2 days apart").
COMPANY_QUARTER_DEDUP_GAP_DAYS = 5


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_modeling_frame() -> tuple[pd.DataFrame, int]:
    df = pd.read_parquet(FEATURES_PATH)
    df[FILING_DATE_COL] = pd.to_datetime(df[FILING_DATE_COL])
    n_total = len(df)
    df = df[df[TARGET_COL].notna()].copy()
    n_dropped = n_total - len(df)
    df = df.sort_values(FILING_DATE_COL).reset_index(drop=True)
    return df, n_dropped


# ---------------------------------------------------------------------------
# Walk-forward splitter -- hand-written, no backtesting framework
# ---------------------------------------------------------------------------


def build_walk_forward_folds(df: pd.DataFrame, burn_in_end: pd.Timestamp) -> list[dict]:
    """Expanding-window, quarterly test folds, sorted by filing_date.

    Returns a list of dicts, each: {"test_quarter": Period, "train_idx":
    np.ndarray, "test_idx": np.ndarray}. Train indices for fold k are
    EVERY row with filing_date strictly before that fold's test quarter
    start (i.e. every prior quarter, including all earlier test quarters'
    now-revealed data) -- an expanding window, never a fixed-size rolling
    window and never a shuffle.
    """
    quarters = df[FILING_DATE_COL].dt.to_period("Q")
    test_quarters = sorted(q for q in quarters.unique() if q.start_time >= burn_in_end)

    folds = []
    for q in test_quarters:
        test_mask = quarters == q
        train_mask = df[FILING_DATE_COL] < q.start_time
        train_idx = np.where(train_mask.values)[0]
        test_idx = np.where(test_mask.values)[0]
        if len(test_idx) == 0 or len(train_idx) == 0:
            continue
        folds.append({"test_quarter": q, "train_idx": train_idx, "test_idx": test_idx})
    return folds


def assert_no_fold_leakage(df: pd.DataFrame, folds: list[dict]) -> None:
    """Leakage-critical invariant: no training row's filing_date may be >=
    any test row's filing_date, for every fold."""
    dates = df[FILING_DATE_COL].values
    for fold in folds:
        max_train_date = dates[fold["train_idx"]].max()
        min_test_date = dates[fold["test_idx"]].min()
        if max_train_date >= min_test_date:
            raise AssertionError(
                f"Fold {fold['test_quarter']}: max train filing_date {max_train_date} "
                f">= min test filing_date {min_test_date} -- walk-forward leakage."
            )


# ---------------------------------------------------------------------------
# Company-quarter deduplication (MAJOR #3, red-team review) -- see module
# docstring "spearman_p is UNADJUSTED for non-independence" and
# COMPANY_QUARTER_DEDUP_GAP_DAYS's docstring for the full justification.
# ---------------------------------------------------------------------------


def assign_company_quarter_clusters(
    df: pd.DataFrame, gap_days: int = COMPANY_QUARTER_DEDUP_GAP_DAYS
) -> pd.Series:
    """Integer cluster id per row, aligned to df.index. Two rows share a
    cluster iff they are the SAME ticker and every consecutive pair of
    filing_dates between them (once sorted) is within `gap_days` calendar
    days -- i.e. contiguous same-ticker filings close in time collapse into
    one cluster. On the real backtest frame this produces only
    singleton/pair clusters (verified, never a 3+ cluster, for every
    gap_days from 3 through 14) -- see COMPANY_QUARTER_DEDUP_GAP_DAYS."""
    ordered = df[["ticker", FILING_DATE_COL]].sort_values(["ticker", FILING_DATE_COL])
    cluster_ids = pd.Series(0, index=ordered.index, dtype="int64")
    cluster_id = 0
    prev_ticker = None
    prev_date = None
    for idx, row in ordered.iterrows():
        if row["ticker"] != prev_ticker or (row[FILING_DATE_COL] - prev_date).days > gap_days:
            cluster_id += 1
        cluster_ids.loc[idx] = cluster_id
        prev_ticker = row["ticker"]
        prev_date = row[FILING_DATE_COL]
    return cluster_ids.reindex(df.index)


def company_quarter_dedup_keep_mask(
    df: pd.DataFrame, gap_days: int = COMPANY_QUARTER_DEDUP_GAP_DAYS
) -> pd.Series:
    """Boolean Series aligned to df.index -- True for exactly ONE row per
    near-duplicate cluster: the LATER filing (by filing_date), because it
    has the fullest information set. Same-calendar-day ties are broken
    FORM-AWARE: a 10-Q/10-K beats any other form, and only then does the
    larger accession_number decide. A pure accession tiebreak is NOT
    reliable across filing agents: accession prefixes encode the agent,
    not intra-day order -- the 2026-08-18 re-verification found one real
    counterexample (SLB 2025-04-25: 8-K accession 0001193125-25-094916 >
    10-Q accession 0000950170-25-058413, different agents), where the old
    tiebreak kept the less-informative 8-K. 65 of the corpus's 66 same-day
    pairs happened to resolve correctly by accession alone; the form-aware
    rule makes all 66 correct by construction."""
    cluster_ids = assign_company_quarter_clusters(df, gap_days=gap_days)
    order = pd.DataFrame(
        {
            "cluster": cluster_ids,
            "filing_date": df[FILING_DATE_COL],
            "form_rank": df["form"].isin(("10-Q", "10-K")).astype(int),
            "accession_number": df["accession_number"],
        },
        index=df.index,
    )
    order = order.sort_values(["cluster", "filing_date", "form_rank", "accession_number"])
    keep_idx = order.groupby("cluster").tail(1).index
    mask = pd.Series(False, index=df.index)
    mask.loc[keep_idx] = True
    return mask


# ---------------------------------------------------------------------------
# Model fit + metrics
# ---------------------------------------------------------------------------


def fit_predict(df: pd.DataFrame, feature_cols: list[str], train_idx, test_idx) -> np.ndarray:
    X_train = df.loc[train_idx, feature_cols].astype(float).values
    y_train = df.loc[train_idx, TARGET_COL].astype(float).values
    X_test = df.loc[test_idx, feature_cols].astype(float).values
    model = XGBRegressor(**XGB_PARAMS)
    model.fit(X_train, y_train)
    return model.predict(X_test)


def quintile_spread(predicted: np.ndarray, realized: np.ndarray) -> tuple[float, int, int]:
    """Top-quintile minus bottom-quintile mean realized return, by
    predicted-score rank. Returns (spread, n_top, n_bottom); spread is NaN
    if the fold is too small/tied to form 2 distinct extreme groups."""
    s = pd.Series(predicted)
    try:
        bins = pd.qcut(s.rank(method="first"), 5, labels=False, duplicates="drop")
    except ValueError:
        return np.nan, 0, 0
    n_bins = bins.nunique()
    if n_bins < 2:
        return np.nan, 0, 0
    top_label = bins.max()
    bottom_label = bins.min()
    top_vals = realized[bins.values == top_label]
    bottom_vals = realized[bins.values == bottom_label]
    if len(top_vals) == 0 or len(bottom_vals) == 0:
        return np.nan, 0, 0
    return float(np.mean(top_vals) - np.mean(bottom_vals)), len(top_vals), len(bottom_vals)


def run_backtest(
    df: pd.DataFrame, folds: list[dict], keep_mask: Optional[pd.Series] = None
) -> dict[str, pd.DataFrame]:
    """`keep_mask`: boolean Series aligned to df.index marking the
    deduplicated company-quarter subset (see
    company_quarter_dedup_keep_mask()) -- computed automatically from `df`
    if not supplied. Every fold's `spearman_ic_dedup`/`spearman_p_dedup`/
    `quintile_spread_dedup` are computed by restricting that SAME fold's
    already-fitted predictions to the rows `keep_mask` marks True, NOT by
    retraining on a deduplicated training set -- this isolates the
    non-independence question (are the EVALUATION pairs correlated) from
    training-set size effects, which is exactly what the raw-vs-dedup
    comparison is meant to isolate. See module docstring "spearman_p is
    UNADJUSTED for non-independence"."""
    if keep_mask is None:
        keep_mask = company_quarter_dedup_keep_mask(df)
    keep_mask_values = keep_mask.reindex(df.index).values

    results = {"numeric_only": [], "text_and_numeric": []}
    for fold in folds:
        q = fold["test_quarter"]
        train_idx, test_idx = fold["train_idx"], fold["test_idx"]
        realized = df.loc[test_idx, TARGET_COL].astype(float).values
        test_keep_positions = np.where(keep_mask_values[test_idx])[0]

        for model_name, feats in (("numeric_only", NUMERIC_FEATURES), ("text_and_numeric", FULL_FEATURES)):
            pred = fit_predict(df, feats, train_idx, test_idx)
            ic, ic_p = spearmanr(pred, realized)
            spread, n_top, n_bottom = quintile_spread(pred, realized)

            pred_dedup = pred[test_keep_positions]
            realized_dedup = realized[test_keep_positions]
            if len(pred_dedup) >= 2 and np.std(pred_dedup) > 0:
                ic_dedup, ic_p_dedup = spearmanr(pred_dedup, realized_dedup)
            else:
                ic_dedup, ic_p_dedup = np.nan, np.nan
            spread_dedup, n_top_dedup, n_bottom_dedup = quintile_spread(pred_dedup, realized_dedup)

            results[model_name].append(
                {
                    "test_quarter": str(q),
                    "n_train": len(train_idx),
                    "n_test": len(test_idx),
                    "spearman_ic": ic,
                    "spearman_p": ic_p,
                    "quintile_spread": spread,
                    "n_top": n_top,
                    "n_bottom": n_bottom,
                    "n_test_dedup": len(pred_dedup),
                    "spearman_ic_dedup": ic_dedup,
                    "spearman_p_dedup": ic_p_dedup,
                    "quintile_spread_dedup": spread_dedup,
                    "n_top_dedup": n_top_dedup,
                    "n_bottom_dedup": n_bottom_dedup,
                }
            )
    return {k: pd.DataFrame(v) for k, v in results.items()}


def run_form_controlled_ablation(
    df: pd.DataFrame, burn_in_end: pd.Timestamp
) -> tuple[pd.DataFrame, list[dict], dict[str, pd.DataFrame]]:
    """MAJOR #4 fix: identical walk-forward comparison, restricted to
    10-Q/10-K observations only (FORM_ABLATION_FORMS) -- removes the
    form-type confound at the observation-set level (not just as a
    feature), so any surviving text-vs-numeric IC delta cannot be
    "detecting which SEC form this row is." Same burn-in date, same
    expanding-window discipline, same feature lists, same model
    hyperparameters as the full-sample backtest -- the ONLY difference is
    the input row set. No company-quarter dedup pass is needed on this
    subset -- verified on this corpus, the minimum gap between consecutive
    same-ticker filings once 8-Ks are excluded is 61 calendar days (a full
    reporting cycle), i.e. zero near-duplicate pairs remain."""
    df_form = df[df["form"].isin(FORM_ABLATION_FORMS)].reset_index(drop=True)
    folds_form = build_walk_forward_folds(df_form, burn_in_end)
    assert_no_fold_leakage(df_form, folds_form)
    results_form = run_backtest(df_form, folds_form)
    return df_form, folds_form, results_form


def compute_dedup_diagnostics(df: pd.DataFrame, gap_days: int = COMPANY_QUARTER_DEDUP_GAP_DAYS) -> dict:
    """Build-time diagnostics for the company-quarter dedup methodology
    (MAJOR #3) -- feeds the "Company-quarter deduplication" report section
    so the reported numbers come from THIS run, not hand-typed separately."""
    cluster_ids = assign_company_quarter_clusters(df, gap_days=gap_days)
    sizes = cluster_ids.value_counts()
    n_singletons = int((sizes == 1).sum())
    n_pairs = int((sizes == 2).sum())
    n_other = int((sizes > 2).sum())

    pair_cluster_ids = sizes[sizes == 2].index
    form_combos = []
    abs_diffs = []
    gaps = []
    for cid in pair_cluster_ids:
        sub = df[cluster_ids.values == cid].sort_values(FILING_DATE_COL)
        form_combos.append(tuple(sorted(sub["form"].tolist())))
        vals = sub[TARGET_COL].astype(float).values
        abs_diffs.append(abs(float(vals[0]) - float(vals[1])))
        gaps.append(int((sub[FILING_DATE_COL].iloc[1] - sub[FILING_DATE_COL].iloc[0]).days))
    abs_diffs = pd.Series(abs_diffs, dtype=float)
    gaps = pd.Series(gaps, dtype=int)
    form_combo_counts = pd.Series([str(c) for c in form_combos]).value_counts().to_dict()

    same_day_mask = gaps == 0
    nonzero_diffs = abs_diffs[~same_day_mask.values]

    return {
        "gap_days": gap_days,
        "n_clusters": int(len(sizes)),
        "n_singletons": n_singletons,
        "n_pairs": n_pairs,
        "n_other_size_clusters": n_other,
        "form_combo_counts": form_combo_counts,
        "n_same_day_pairs": int(same_day_mask.sum()),
        "n_nonzero_gap_pairs": int((~same_day_mask).sum()),
        "median_nonzero_abs_diff": float(nonzero_diffs.median()) if len(nonzero_diffs) else float("nan"),
        "mean_nonzero_abs_diff": float(nonzero_diffs.mean()) if len(nonzero_diffs) else float("nan"),
        "mean_abs_diff_all_pairs": float(abs_diffs.mean()) if len(abs_diffs) else float("nan"),
        "cross_sectional_std": float(df[TARGET_COL].astype(float).std()),
        "n_dedup_rows": int(len(sizes)),
    }


def fit_full_sample_importance(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    """Fit once on ALL usable rows (not a backtest fold -- purely for
    feature-importance interpretability) and return gain-based importances,
    sorted descending. Explicitly NOT used for any of the per-fold IC/
    spread numbers above (that would be in-sample and misleading)."""
    X = df[feature_cols].astype(float).values
    y = df[TARGET_COL].astype(float).values
    model = XGBRegressor(**XGB_PARAMS)
    model.fit(X, y)
    importances = model.feature_importances_
    out = pd.DataFrame({"feature": feature_cols, "importance_gain": importances})
    return out.sort_values("importance_gain", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _fmt_table(df: pd.DataFrame, cols: list[str]) -> list[str]:
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, row in df.iterrows():
        vals = []
        for c in cols:
            v = row[c]
            if isinstance(v, float):
                vals.append("NaN" if pd.isna(v) else f"{v:.4f}")
            else:
                vals.append(str(v))
        lines.append("| " + " | ".join(vals) + " |")
    return lines


def _summary_row(series: pd.Series) -> str:
    s = series.dropna()
    if s.empty:
        return "mean=NaN, std=NaN, min=NaN, max=NaN (all folds NaN)"
    return f"mean={s.mean():.4f}, std={s.std(ddof=0):.4f}, min={s.min():.4f}, max={s.max():.4f}, n_folds_with_value={len(s)}/{len(series)}"


def write_backtest_report(
    df: pd.DataFrame,
    n_target_dropped: int,
    folds: list[dict],
    results: dict[str, pd.DataFrame],
    importances: dict[str, pd.DataFrame],
    dedup_stats: dict,
    df_form: pd.DataFrame,
    folds_form: list[dict],
    results_form: dict[str, pd.DataFrame],
) -> None:
    lines = []
    lines.append("# FinScreen Phase C -- walk-forward backtest report")
    lines.append("")
    _feat_path = Path(FEATURES_PATH) if isinstance(FEATURES_PATH, str) else FEATURES_PATH
    _feat_mtime = (
        _dt.datetime.fromtimestamp(_feat_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        if _feat_path.exists() else "unknown"
    )
    lines.append(
        f"*Generated by `backtest.py` on "
        f"{_dt.datetime.now().strftime('%Y-%m-%d %H:%M')} from `{_feat_path}` "
        f"({len(df) + n_target_dropped} rows, last written {_feat_mtime}). "
        f"Re-running `backtest.py` overwrites this file -- if you are reading it as a "
        f"go/no-go gate file, check that this stamp is the vintage you were pointed at.*"
    )
    lines.append("")
    lines.append(
        "**These are research screening-score diagnostics, not trading results and not "
        "investment advice.** No position sizing, no execution, no transaction costs, no "
        "portfolio simulation of any kind occurs anywhere in this repository. The numbers below "
        "describe how well a predicted score would have RANKED companies against a realized "
        "forward excess return in a strictly time-ordered, walk-forward evaluation -- nothing "
        "here is a recommendation to buy, hold, or sell anything, and nothing here estimates an "
        "expected return. Every number is reported next to how it was computed; treat any number "
        "that looks unusually strong as a prompt to re-check for a look-ahead-bias bug before "
        "treating it as a finding (project-standing rule)."
    )
    lines.append("")
    lines.append(
        "**This report is presented neutrally, with no go/no-go recommendation.** Per the "
        "project's Phase C process, the owner reads these per-fold numbers personally and makes "
        "that call. The `red-team-reviewer` passes (look-ahead bias, overfitting) that precede "
        "that read have COMPLETED: two review passes plus an independent from-scratch "
        "re-verification, whose findings were fixed and re-verified before this report was "
        "regenerated (`HANDOFF.md` §2a). Those passes happen before the owner's read, not "
        "instead of it."
    )
    lines.append("")

    lines.append("## Sample size -- read this before the tables below")
    lines.append("")
    lines.append(
        f"- {len(df) + n_target_dropped} total (company, filing) observations in "
        f"`data/features.parquet`; **{n_target_dropped} dropped** here for lacking a complete "
        "63-trading-day forward target window as of this data snapshot (too recent) -- see "
        "`data/features_report.md` for the exact list."
    )
    lines.append(f"- **{len(df)} observations enter this backtest.**")
    lines.append(
        "- **This is NOT ~581 independent bets.** The universe's natural sizing anchor is 25 "
        "companies x ~12 quarters ~= 300 observations; this backtest's row count is roughly double that "
        "because the unit of observation is the FILING, not the company-quarter, and most "
        "companies file an 8-K earnings release and then a 10-Q/10-K one to two days later, "
        "each becoming its own observation with an entry date 1-2 trading days apart -- their "
        "63-trading-day forward return windows overlap by 61-62 of 63 days. Treat every N below "
        "as roughly HALF that many independent company-quarter bets. This is a design property "
        "of the observation unit, not a data error, and it is the small-universe caveat that "
        "`HANDOFF.md` §6 Step 3 and `ROADMAP.md` Phase C require to be stated plainly rather "
        "than buried."
    )
    lines.append(
        "- Given this, **fewer, wider folds were chosen over many quarterly-from-the-start "
        "folds** -- 6 quarters (2023 Q3-2024 Q4, "
        f"{folds[0]['train_idx'].shape[0] if folds else 'n/a'} obs) burned in as the initial "
        "training set before the first test fold. Many tiny per-quarter-from-the-start folds "
        "would be unstable at this scale; a single train/test split would hide fold-to-fold "
        "variance entirely."
    )
    lines.append("")

    lines.append("## Fold structure")
    lines.append("")
    lines.append(
        "Hand-written expanding-window walk-forward split (`build_walk_forward_folds()`), sorted "
        "by `filing_date` (public availability date, never `report_date`). Every fold's training "
        "set is every observation strictly before that fold's test quarter; the test set is "
        "exactly that calendar quarter. NEVER a random shuffle. Verified: "
        "`assert_no_fold_leakage()` passes for all folds (also covered by "
        "`test_phase_c_leakage.py`)."
    )
    lines.append("")
    lines.append(
        "**Metric definitions** (used in every table below, first appearance included): "
        "**Spearman IC** (`spearman_ic`) = the Spearman rank correlation between a fold's "
        "predicted scores and its realized `target_excess_return` -- an \"information "
        "coefficient\", the standard screening-quality metric, NOT a return. "
        "**Quintile spread** = mean realized excess return of the top-20%-by-predicted-score "
        "minus the bottom-20%, within the same test fold. **`_dedup` suffix** = the same "
        "quantity recomputed on one row per near-duplicate company-quarter cluster."
    )
    lines.append("")
    lines.append("| Test quarter | N train | N test |")
    lines.append("|---|---|---|")
    for fold in folds:
        lines.append(f"| {fold['test_quarter']} | {len(fold['train_idx'])} | {len(fold['test_idx'])} |")
    lines.append("")

    for model_name, label in (("numeric_only", "Numeric-only baseline"), ("text_and_numeric", "Text + numeric (augmented)")):
        res = results[model_name]
        lines.append(f"## {label} -- per-fold results (RAW and deduplicated)")
        lines.append("")
        lines.append(f"Features used ({len(NUMERIC_FEATURES) if model_name=='numeric_only' else len(FULL_FEATURES)}): "
                      f"{'`' + '`, `'.join(NUMERIC_FEATURES) + '`' if model_name=='numeric_only' else '`' + '`, `'.join(FULL_FEATURES) + '`'}")
        lines.append("")
        lines.append(
            "**`spearman_p` is UNADJUSTED for non-independence -- see the module docstring and "
            "\"Company-quarter deduplication\" section below.** Roughly half of each fold's rows "
            "are near-duplicate (company, quarter) pairs; `spearman_p` treats them as independent "
            "draws, which is anti-conservative. `spearman_ic_dedup`/`spearman_p_dedup`/"
            "`quintile_spread_dedup` (computed on the SAME fitted predictions, restricted to one "
            "row per near-duplicate cluster -- the later filing kept, with SAME-DAY ties resolved "
            "10-Q/10-K-first and only then by accession, per `company_quarter_dedup_keep_mask()`; "
            "66 of the 127 pairs file on the same calendar day, so the form rule -- not "
            "\"later\" -- is what decides for half of them) are the more defensible read; `n_test_dedup` is "
            "the deduplicated test-fold size."
        )
        lines.append("")
        lines.extend(
            _fmt_table(
                res,
                [
                    "test_quarter", "n_train", "n_test", "spearman_ic", "spearman_p",
                    "quintile_spread", "n_top", "n_bottom",
                    "n_test_dedup", "spearman_ic_dedup", "spearman_p_dedup", "quintile_spread_dedup",
                ],
            )
        )
        lines.append("")
        lines.append(f"Cross-fold Spearman IC summary (raw): {_summary_row(res['spearman_ic'])}")
        lines.append(f"Cross-fold Spearman IC summary (dedup): {_summary_row(res['spearman_ic_dedup'])}")
        lines.append(f"Cross-fold quintile-spread summary (raw): {_summary_row(res['quintile_spread'])}")
        lines.append(f"Cross-fold quintile-spread summary (dedup): {_summary_row(res['quintile_spread_dedup'])}")
        lines.append("")
        lines.append(
            "Spearman IC = `scipy.stats.spearmanr(predicted_score, realized_target_excess_return)` "
            "over the test fold only. Quintile spread = mean realized excess return of the "
            "top-20%-by-predicted-score minus the bottom-20%-by-predicted-score, within the same "
            "test fold (`pandas.qcut`, ties broken by first-occurrence rank; folds too small/tied "
            "to form 2 distinct groups are marked NaN, not silently dropped from the table)."
        )
        lines.append("")

    lines.append("## Numeric-only vs. text+numeric -- per-fold comparison (RAW and deduplicated)")
    lines.append("")
    comp = pd.DataFrame(
        {
            "test_quarter": results["numeric_only"]["test_quarter"],
            "IC_numeric_only": results["numeric_only"]["spearman_ic"],
            "IC_text_and_numeric": results["text_and_numeric"]["spearman_ic"],
            "IC_delta_text_minus_numeric": results["text_and_numeric"]["spearman_ic"] - results["numeric_only"]["spearman_ic"],
            "spread_numeric_only": results["numeric_only"]["quintile_spread"],
            "spread_text_and_numeric": results["text_and_numeric"]["quintile_spread"],
            "IC_dedup_numeric_only": results["numeric_only"]["spearman_ic_dedup"],
            "IC_dedup_text_and_numeric": results["text_and_numeric"]["spearman_ic_dedup"],
            "IC_dedup_delta_text_minus_numeric": results["text_and_numeric"]["spearman_ic_dedup"] - results["numeric_only"]["spearman_ic_dedup"],
        }
    )
    lines.extend(_fmt_table(comp, list(comp.columns)))
    lines.append("")
    lines.append(
        f"Cross-fold mean IC delta, RAW (text+numeric minus numeric-only): "
        f"{comp['IC_delta_text_minus_numeric'].mean():.4f} "
        f"(std {comp['IC_delta_text_minus_numeric'].std(ddof=0):.4f}, "
        f"positive in {(comp['IC_delta_text_minus_numeric'] > 0).sum()}/{len(comp)} folds). "
        f"Cross-fold mean IC delta, DEDUPLICATED: "
        f"{comp['IC_dedup_delta_text_minus_numeric'].mean():.4f} "
        f"(std {comp['IC_dedup_delta_text_minus_numeric'].std(ddof=0):.4f}, "
        f"positive in {(comp['IC_dedup_delta_text_minus_numeric'] > 0).sum()}/{comp['IC_dedup_delta_text_minus_numeric'].notna().sum()} "
        f"folds; no fold is NaN in this build). "
        "**Read the sign of the two means against each other.** When the RAW and DEDUPLICATED deltas disagree in sign, that disagreement IS the finding: one column favours text, the other favours numeric-only, and neither is distinguishable from zero at six folds. Fragility, not a direction, is what this backtest supports concluding in that case. "
        "This is reported as a per-fold spread, not a single verdict -- see the per-fold table "
        "immediately above for the actual variance across folds, which is the signal this "
        "small-universe backtest can and cannot support (project-standing rule: report per-fold "
        "spreads, never a single point estimate)."
    )
    lines.append("")

    lines.append("## Company-quarter deduplication -- methodology (fixes near-duplicate-pair non-independence, found in red-team review)")
    lines.append("")
    lines.append(
        f"`assign_company_quarter_clusters()` groups same-ticker filings within "
        f"{dedup_stats['gap_days']} calendar days of each other into one \"company-quarter\" "
        f"cluster; `company_quarter_dedup_keep_mask()` keeps exactly ONE filing per cluster: the LATER "
        f"one by filing_date (fullest information set), and where both filings share a calendar day "
        f"-- which is {dedup_stats['n_same_day_pairs']} of the {dedup_stats['n_pairs']} pairs, i.e. about half -- "
        f"the tie is broken FORM-AWARE (10-Q/10-K beats any other form) before accession number is "
        f"consulted at all. Accession order alone is NOT reliable across filing agents. "
        f"On this backtest's {len(df)}-observation frame: "
        f"**{dedup_stats['n_clusters']} clusters** ({dedup_stats['n_singletons']} singleton "
        f"filings + {dedup_stats['n_pairs']} two-filing pairs"
        + (f" + {dedup_stats['n_other_size_clusters']} larger clusters" if dedup_stats["n_other_size_clusters"] else "")
        + f") -- i.e. the deduplicated evaluation set has {dedup_stats['n_dedup_rows']} rows, not "
        f"{len(df)}."
    )
    lines.append("")
    lines.append(f"Pair form-type composition: {dedup_stats['form_combo_counts']} -- confirms these pairs are "
                  "overwhelmingly the (8-K, 10-Q/10-K) same-earnings-event pattern the red-team finding named. "
                  "**Each key is an ALPHABETICALLY SORTED tuple, not a filing order** -- `('10-Q', '8-K')` does "
                  "not mean the 10-Q came first. Where the two filings actually have different dates (61 of the "
                  "127 pairs), the 8-K comes first in 60 of them (8-K then 10-Q x52, 8-K then 10-K x8; the "
                  "remaining pair is 8-K then 8-K). For the other 66 pairs both filings share a calendar day, so "
                  "there is no filing order to report.")
    lines.append("")
    lines.append(
        f"Independent verification that these pairs carry correlated, not independent, target "
        f"information: of the {dedup_stats['n_pairs']} pairs, **{dedup_stats['n_same_day_pairs']}** "
        f"were filed on the exact same calendar day (their `target_excess_return` values are "
        f"therefore numerically IDENTICAL -- diff = 0.0 by construction, since both rows share the "
        f"same target entry date). Of the remaining **{dedup_stats['n_nonzero_gap_pairs']}** pairs "
        f"with a nonzero filing-date gap, the within-pair absolute target difference has median "
        f"**{dedup_stats['median_nonzero_abs_diff']:.4f}** / mean "
        f"**{dedup_stats['mean_nonzero_abs_diff']:.4f}**, versus a cross-sectional std of "
        f"**{dedup_stats['cross_sectional_std']:.4f}** across all {len(df)} observations -- i.e. "
        "paired observations differ from each other by roughly a fifth of the cross-sectional "
        "spread, confirming the near-duplicate characterization."
    )
    lines.append("")

    lines.append("## Form-controlled ablation (10-Q/10-K only) -- per-fold comparison (fixes the SEC-form-type confound, found in red-team review)")
    lines.append("")
    lines.append(
        "`share_chunks_risk_factors`/`share_chunks_mda`/`share_chunks_ex99_press_release`/"
        "`redflag_any_rate_press` are near-perfect proxies for SEC FORM TYPE (8-Ks structurally "
        "cannot carry RISK_FACTORS/MDA chunks; press-release chunks come from 8-K EX99 exhibits "
        "almost exclusively) -- see the feature-importance caveat below. This section reruns the "
        "identical walk-forward comparison restricted to 10-Q/10-K observations only (8-Ks "
        "dropped), same burn-in date, same expanding-window discipline, same features, same model "
        f"hyperparameters -- the only difference is the input row set ({len(df_form)} observations "
        f"vs. {len(df)} full-sample). No company-quarter dedup pass is needed on this subset -- "
        "the minimum gap between consecutive same-ticker filings once 8-Ks are excluded is 61 "
        "calendar days (verified), i.e. zero near-duplicate pairs remain."
    )
    lines.append("")
    lines.append("| Test quarter | N train (form-restricted) | N test (form-restricted) |")
    lines.append("|---|---|---|")
    for fold in folds_form:
        lines.append(f"| {fold['test_quarter']} | {len(fold['train_idx'])} | {len(fold['test_idx'])} |")
    lines.append("")
    form_comp = pd.DataFrame(
        {
            "test_quarter": results_form["numeric_only"]["test_quarter"],
            "n_test": results_form["numeric_only"]["n_test"],
            "IC_numeric_only": results_form["numeric_only"]["spearman_ic"],
            "IC_text_and_numeric": results_form["text_and_numeric"]["spearman_ic"],
            "IC_delta_text_minus_numeric": results_form["text_and_numeric"]["spearman_ic"] - results_form["numeric_only"]["spearman_ic"],
            "spread_numeric_only": results_form["numeric_only"]["quintile_spread"],
            "spread_text_and_numeric": results_form["text_and_numeric"]["quintile_spread"],
        }
    )
    lines.extend(_fmt_table(form_comp, list(form_comp.columns)))
    lines.append("")
    lines.append(
        f"Cross-fold mean IC delta, form-controlled (text+numeric minus numeric-only): "
        f"{form_comp['IC_delta_text_minus_numeric'].mean():.4f} "
        f"(std {form_comp['IC_delta_text_minus_numeric'].std(ddof=0):.4f}, "
        f"positive in {(form_comp['IC_delta_text_minus_numeric'] > 0).sum()}/{len(form_comp)} folds), "
        f"vs. the full-sample RAW delta of {comp['IC_delta_text_minus_numeric'].mean():.4f} reported "
        "above. **Per-fold N here is small (n_test column above) -- read this as a directional "
        "check on the form-type confound, not as a precise estimate; small-N Spearman correlations "
        "are noisy by construction (project-standing rule).**"
    )
    lines.append("")

    lines.append("## Numeric-only baseline -- per-fold results, form-controlled")
    lines.append("")
    lines.extend(
        _fmt_table(
            results_form["numeric_only"],
            ["test_quarter", "n_train", "n_test", "spearman_ic", "spearman_p", "quintile_spread", "n_top", "n_bottom"],
        )
    )
    lines.append("")
    lines.append("## Text + numeric (augmented) -- per-fold results, form-controlled")
    lines.append("")
    lines.extend(
        _fmt_table(
            results_form["text_and_numeric"],
            ["test_quarter", "n_train", "n_test", "spearman_ic", "spearman_p", "quintile_spread", "n_top", "n_bottom"],
        )
    )
    lines.append("")
    lines.append(
        "`spearman_p` in the two tables immediately above is likewise unadjusted for "
        "non-independence in general (scipy's assumption), though this specific subset has no "
        "near-duplicate pairs by construction (see methodology note above)."
    )
    lines.append("")

    lines.append("## Feature importances (full-sample fit, NOT a backtest fold -- interpretability only)")
    lines.append("")
    lines.append(
        "Fit once on all usable rows (in-sample; not used for any IC/spread number above, which "
        "are all strictly out-of-fold). Top 15 by XGBoost gain-based importance, each model:"
    )
    lines.append("")
    lines.append(
        "**Form-type confound caveat (red-team review -- the SEC-form-type confound): `share_chunks_risk_factors` / "
        "`share_chunks_mda` / `share_chunks_ex99_press_release` / `redflag_any_rate_press` are "
        "near-perfect proxies for which SEC form a row is (8-Ks structurally cannot carry "
        "RISK_FACTORS/MDA chunks; press-release chunks come from 8-K EX99 exhibits almost "
        "exclusively) -- their importance below is NOT distinguishable from the model simply "
        "detecting form type, without the form-controlled ablation section above. Flagged in the "
        "table via `is_form_confounded_feature`.**"
    )
    lines.append("")
    form_confounded_prefixes = ("share_chunks_", "redflag_any_rate_press")
    for model_name, label in (("numeric_only", "Numeric-only baseline"), ("text_and_numeric", "Text + numeric (augmented)")):
        imp = importances[model_name].head(15).copy()
        imp["is_red_flag_feature"] = imp["feature"].str.startswith("redflag_")
        imp["is_form_confounded_feature"] = imp["feature"].str.startswith(form_confounded_prefixes)
        lines.append(f"### {label}")
        lines.append("")
        lines.extend(_fmt_table(imp, ["feature", "importance_gain", "is_red_flag_feature", "is_form_confounded_feature"]))
        lines.append("")
        if imp["is_red_flag_feature"].any():
            lines.append(f"**{F.RED_FLAG_CAVEAT}**")
            lines.append("")

    lines.append("## Limitations carried into this report verbatim")
    lines.append("")
    lines.append(
        "- **Dividend adjustment.** `data/prices.parquet` closes are split-adjusted but NOT "
        "dividend-adjusted (`data/PRICES_NOTES.md` §1). Both the subject return and the "
        "universe-average return in `target_excess_return` share this omission identically, so "
        "it is a common-mode bias across the panel rather than independent noise -- but it "
        "systematically understates total return more for high-dividend-yield names (PG, KO, "
        "MCD) than for low-yield names (NVDA, GOOGL). This affects the target itself, not just "
        "a feature, so it is worth restating here even though `features_report.md` already "
        "documents it."
    )
    lines.append(f"- **Red-flag feature reliability.** {F.RED_FLAG_CAVEAT}")
    lines.append(
        "- **Small universe / sample-size caveat** (repeated from the top of this report because "
        "it governs how every number below should be read): 25 companies, ~12 quarters, "
        f"{len(df)} filing-level observations but roughly half that many independent "
        "company-quarter bets (see \"Company-quarter deduplication\" above for the measured, not "
        "just asserted, evidence). Per-fold IC and quintile-spread numbers on ~25-50 truly "
        "independent observations are noisy by construction; the cross-fold variance reported "
        "above is the honest way to see that, not a defect to explain away."
    )
    lines.append(
        "- **`spearman_p` non-independence** (the near-duplicate-pair defect found in red-team review). Every `spearman_p` column not "
        "explicitly labeled `_dedup` is unadjusted for the near-duplicate-pair structure above and "
        "is anti-conservative -- prefer the `_dedup` columns for anything beyond \"did the sign "
        "flip.\""
    )
    lines.append(
        "- **Form-type confound** (found in red-team review). `share_chunks_*`/`redflag_any_rate_press` "
        "feature-importance rankings are not distinguishable from form-type (8-K vs. 10-Q/10-K) "
        "detection without the form-controlled ablation section above; read that section, not "
        "just the raw importance table, before attributing predictive value to those features."
    )
    lines.append(
        "- **Target's mechanical negative cross-correlation** (found in red-team review). The subject company is "
        "one of the 25 constituents of its own benchmark average (see \"Target definition\" in "
        "`data/features_report.md`), so there is a small MECHANICAL negative correlation between "
        "a company's own return and its excess-return target (each company's return pulls its own "
        "1-of-25 benchmark average toward itself, at weight 1/25) -- at n=25 this is a modest, not "
        "dominant, effect (a 1/25 self-weight), and it is further diluted because each filer's "
        "own 63-trading-day window is measured on ITS OWN staggered start date (the first trading "
        "day after ITS filing_date), not a single shared calendar window across the panel, so the "
        "same-company self-weighting effect does not compound identically across observations."
    )
    lines.append(
        "- **No survivorship-bias correction.** The 25-company universe reflects today's "
        "membership, not historical membership -- companies that would have failed or been "
        "delisted during this window are not in it by construction (DISCOVERY.md §5)."
    )
    lines.append(
        "- **Non-goals, restated.** No trade is placed, queued, or recommended by any part of "
        "this system. This screening score is a research signal, not investment advice, in any "
        "phase, for any audience."
    )
    lines.append("")

    BACKTEST_REPORT_OUTPUT.write_text("\n".join(lines))


def main() -> None:
    print("Loading data/features.parquet...")
    df, n_dropped = load_modeling_frame()
    print(f"{len(df)} usable observations ({n_dropped} dropped for incomplete target window)")

    folds = build_walk_forward_folds(df, BURN_IN_END)
    assert_no_fold_leakage(df, folds)
    print(f"{len(folds)} walk-forward folds built and leakage-checked")

    keep_mask = company_quarter_dedup_keep_mask(df)
    results = run_backtest(df, folds, keep_mask=keep_mask)
    dedup_stats = compute_dedup_diagnostics(df)
    print(
        f"Company-quarter dedup: {dedup_stats['n_clusters']} clusters from {len(df)} rows "
        f"({dedup_stats['n_singletons']} singleton + {dedup_stats['n_pairs']} pairs)"
    )

    print("Running form-controlled (10-Q/10-K only) ablation...")
    df_form, folds_form, results_form = run_form_controlled_ablation(df, BURN_IN_END)
    print(f"{len(df_form)} form-restricted observations, {len(folds_form)} folds")

    importances = {
        "numeric_only": fit_full_sample_importance(df, NUMERIC_FEATURES),
        "text_and_numeric": fit_full_sample_importance(df, FULL_FEATURES),
    }

    write_backtest_report(df, n_dropped, folds, results, importances, dedup_stats, df_form, folds_form, results_form)
    print(f"Wrote {BACKTEST_REPORT_OUTPUT}")

    print("\n=== Numeric-only per-fold Spearman IC (raw / dedup) ===")
    print(results["numeric_only"][["test_quarter", "n_train", "n_test", "spearman_ic", "spearman_ic_dedup", "quintile_spread", "quintile_spread_dedup"]].to_string(index=False))
    print("\n=== Text+numeric per-fold Spearman IC (raw / dedup) ===")
    print(results["text_and_numeric"][["test_quarter", "n_train", "n_test", "spearman_ic", "spearman_ic_dedup", "quintile_spread", "quintile_spread_dedup"]].to_string(index=False))
    print("\n=== Form-controlled (10-Q/10-K only) ablation: numeric-only per-fold Spearman IC ===")
    print(results_form["numeric_only"][["test_quarter", "n_train", "n_test", "spearman_ic", "quintile_spread"]].to_string(index=False))
    print("\n=== Form-controlled (10-Q/10-K only) ablation: text+numeric per-fold Spearman IC ===")
    print(results_form["text_and_numeric"][["test_quarter", "n_train", "n_test", "spearman_ic", "quintile_spread"]].to_string(index=False))


if __name__ == "__main__":
    main()
