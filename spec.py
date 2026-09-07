"""
spec.py -- FinScreen H2 (F2.5 hardening): the PRE-REGISTERED feature
specification, the two standing zero-information benchmarks, and the
within-fold bootstrap noise anchor.

Source spec: `data/reevaluation_2026-08-25/methodology_audit.md`
recommendations E1 (specification pre-registration) and E2 (bootstrap
anchor / ddof fix). Ledger item H2 in `HARDENING_PROGRESS.md`.

This module is deliberately *pure*: it imports only numpy/pandas/scipy and
takes the model-fitting callable as an argument, so `backtest.py` and
`diagnose.py` can both use it without a circular import and so every
function here is testable offline on synthetic frames.

-----------------------------------------------------------------------
1. Why a pre-registered feature transformation exists at all
-----------------------------------------------------------------------
`methodology_audit.md` §(c) C9 measured the intraclass correlation
(between-company variance / total variance) of the numeric features on
`data/features.parquet`: `log_total_assets` 0.987, leverage 0.986,
equity/assets 0.984. At that ICC the raw feature LEVELS encode company
identity almost exactly, a depth-3 XGBoost can partition the 25 companies
and fit each one's in-sample mean excess return, and BOTH arms of the
text-vs-numeric comparison then ride the same large company-persistence
term -- so the estimand (their difference) is a small residual on a big
shared component. Two zero-information predictors beat both fitted models
on E1's own folds (size-only rank 0.224, ticker-training-mean 0.187, vs.
0.097 numeric-only and 0.088 text+numeric).

Rank-normalising each feature against a trailing cross-section strips the
level and forces the model onto relative variation. That is the a-priori
identification argument, and it is the ONLY reason this transform is
primary. It is emphatically NOT chosen because the audit's E1 re-run
happened to move the headline delta from -0.0097 to +0.0467: that swing
(0.056, ~3x E2's optimistic MDE) is *evidence that the specification was
under-determined*, not evidence about the sign of anything. At SE ~= 0.07
both numbers are statistically indistinguishable from zero and from each
other.

**Contamination warning, stated once and inherited everywhere:** E1
numbers computed under this transform have been SEEN before the transform
was declared primary. They are therefore descriptive/diagnostic only and
can never be quoted as a confirmatory result. The pre-registration binds
E2, whose data does not exist yet.

-----------------------------------------------------------------------
2. The transform (PRIMARY specification)
-----------------------------------------------------------------------
`pit_trailing_rank_frame()`. For a row i observed at filing_date t, each
feature is replaced by its percentile within a comparison set built as:

  - one observation per ticker: that ticker's LAST observation with
    filing_date in [t - window_days, t] (window_days = 180 by default);
  - the subject row itself always represents its own ticker (so a same-day
    sibling filing of the same company never displaces the subject);
  - percentile = (#strictly below + 0.5 * #ties) / #non-null comparators.

**The IMPLEMENTATION is what is pre-registered, not the name.** Measured
on E1 (2026-08-25, H2): SEVEN mutually-defensible, all look-ahead-free
implementations of "PIT trailing cross-sectional percentile ranks, 180-day
window" produce cross-fold mean dedup IC deltas spanning **-0.0172 to
+0.0422** (range 0.059) and cross-fold sample stds spanning 0.0496 to
0.1549 (a 3.1x range) -- on the same folds, same dedup, same XGB params.
(`methodology_audit.md`'s own eighth variant reports +0.0467; its stated
recipe could not be reproduced exactly, and including it widens the span to
0.064.) The variants differ only in: subject inclusion, same-day-peer
inclusion, last-per-ticker vs. every-row comparison sets, and whether the
ranking cross-section is the 581-row modeling frame or the 630-row
artifact. Naming a transform therefore pre-registers nothing; a function
plus its arguments does. The `include_same_day` flag exists so the one
named sensitivity variant is reproducible from this module rather than
reimplemented ad hoc.

Choice of default, made on a-priori grounds and recorded so it cannot be
quietly re-picked: subject INCLUDED (a percentile should be taken over a
set that contains the point it describes, and the result is then always
strictly inside (0,1) and independent of whether the ticker had filed
before), same-day peers INCLUDED (under the next-trading-open action
convention queued for G3, everything filed on day t is public before the
feature is acted on).

No row with `filing_date > t` can enter any comparison set -- pinned by
`test_spec.py::test_future_rows_cannot_change_a_past_percentile`. NaN in
means NaN out (missingness is preserved, never imputed: XGBoost consumes
NaN natively and `methodology_audit.md` §(b) shows 52-76% structural
absence in the red-flag families, which must stay visible as absence).
Fewer than `min_comparators` non-null comparators also yields NaN rather
than a degenerate percentile.

**Inherited convention, not fixed here:** the comparison set is built at
`filing_date` day granularity, so it inherits the corpus-wide post-close
acceptance issue (`data/F2_INGESTION_REPORT.md` §3.3: 45% of filings are
accepted after 16:00 ET while carrying that day's `filing_date`). That is
audit item C1 and is queued for the G3 pre-registration; it is a property
of the date column, not of this transform.

-----------------------------------------------------------------------
3. The two standing zero-information benchmarks
-----------------------------------------------------------------------
`zero_information_benchmarks()`. Every generated report carries these two
rows so that no IC is ever read without knowing what a predictor
containing NO information achieves on the SAME folds:

  - `size_only_rank` -- rank by `log_total_assets` alone. One
    near-constant-per-company variable; zero fitting.
  - `ticker_training_mean_rank` -- rank by the ticker's MEAN realized
    excess return over that fold's TRAINING rows. Zero features; pure
    company persistence. Tickers absent from the training window fall back
    to the overall training mean (a tie block, reported as such).

Both are defined on the RAW frame regardless of which feature
specification the surrounding model run uses: they are properties of the
folds and the target, not of the feature transform, and holding them fixed
is what makes them comparable across specifications.

**Honest caveat on the second one:** `ticker_training_mean_rank` uses
training-row targets, and those targets are 63-trading-day forward windows
that RESOLVE after the train/test boundary (see `embargo_census()`). It
inherits exactly the same non-embargoed-label property the fitted models
have; it is not cleaner than they are, and it is not a look-ahead
*relative to them*.

-----------------------------------------------------------------------
4. The within-fold bootstrap noise anchor
-----------------------------------------------------------------------
`bootstrap_noise_anchor()`. `EXPANSION_PLAN.md` §2a's entire MDE bracket is
anchored on the standard deviation of SIX numbers (the six E1 fold
deltas), whose own 95% chi-square CI spans a ~3.9x range. The within-fold
bootstrap is a strictly better estimator of the sampling component: hold
each fold's fitted predictions fixed, resample that fold's deduplicated
test rows with replacement, recompute the delta. ~40 rows x 4,000
resamples per fold instead of 5 degrees of freedom.

It also identifies the quantity the recon called unidentifiable: the
regime/training "floor" that more companies cannot buy down.

    implied_floor_sd = sqrt(max(0, cross_fold_var - mean_within_fold_var))

Reported with BOTH candidate anchors (arithmetic mean of the per-fold SDs,
and the RMS = sqrt of the mean of the per-fold variances, which is the
variance-decomposition-correct one and is always >= the mean), because
which one anchors an MDE changes the MDE by ~10%.
"""

from __future__ import annotations

from typing import Callable, Optional

import numpy as np
import pandas as pd
from scipy.stats import chi2, rankdata, spearmanr

# ---------------------------------------------------------------------------
# Pre-registered specification constants -- change these ONLY through a dated
# amendment, never inside an analysis run.
# ---------------------------------------------------------------------------

PRIMARY_SPEC = "pit_trailing_rank"
SECONDARY_SPEC = "raw_levels"
SPEC_NAMES = (PRIMARY_SPEC, SECONDARY_SPEC)

#: Trailing window for the cross-sectional comparison set, calendar days.
#: 180 days ~= two quarterly reporting cycles, so every ticker that filed at
#: its normal cadence is represented exactly once.
PIT_RANK_WINDOW_DAYS = 180

#: Below this many non-null comparators a percentile is degenerate; emit NaN.
MIN_COMPARATORS = 2

#: Whether same-day filings (including the subject's own row) enter the
#: comparison set. TRUE is the pre-registered default; FALSE is the single
#: named sensitivity variant (see the module docstring §2).
INCLUDE_SAME_DAY = True

#: Bootstrap settings, fixed here so every report's anchor is reproducible.
BOOTSTRAP_RESAMPLES = 4000
BOOTSTRAP_SEED = 0

ZERO_INFO_SIZE = "size_only_rank"
ZERO_INFO_TICKER_MEAN = "ticker_training_mean_rank"
ZERO_INFO_BENCHMARKS = (ZERO_INFO_SIZE, ZERO_INFO_TICKER_MEAN)

SPEC_CONTAMINATION_WARNING = (
    "E1 numbers under the PIT-rank specification were computed AFTER the "
    "specification sensitivity was observed (`methodology_audit.md` E1: raw "
    "-0.0097 vs. rank +0.0467, a 0.056 swing at SE ~= 0.07). They are "
    "descriptive of a re-derivation on already-seen data and can never be "
    "quoted as a confirmatory result. The pre-registration binds E2, whose "
    "data does not exist yet."
)


# ---------------------------------------------------------------------------
# 1. PIT trailing cross-sectional percentile-rank transform
# ---------------------------------------------------------------------------


def pit_trailing_rank_frame(
    df: pd.DataFrame,
    feature_cols: list[str],
    window_days: int = PIT_RANK_WINDOW_DAYS,
    date_col: str = "filing_date",
    ticker_col: str = "ticker",
    min_comparators: int = MIN_COMPARATORS,
    include_same_day: bool = INCLUDE_SAME_DAY,
) -> pd.DataFrame:
    """Return a COPY of `df` with `feature_cols` replaced by strictly
    look-ahead-free trailing cross-sectional percentiles. See the module
    docstring §2 for the full definition. `df` must be sorted ascending by
    `date_col` (raises otherwise -- silently ranking an unsorted frame
    would produce look-ahead).

    `include_same_day=False` is the ONE named sensitivity variant: the
    comparison set becomes [t - window_days, t) so no same-day filing --
    including the subject's own row -- enters it, which is the conservative
    reading under the unresolved post-close acceptance issue (audit C1). On
    E1 it moves the headline dedup delta from -0.0093 to +0.0422. Flipping
    this default is a pre-registration amendment, not an analysis choice."""
    if not feature_cols:
        return df.copy()
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        raise KeyError(f"pit_trailing_rank_frame: columns not in frame: {missing}")

    dates = pd.to_datetime(df[date_col]).values
    if len(dates) > 1 and not np.all(dates[:-1] <= dates[1:]):
        raise ValueError(
            f"pit_trailing_rank_frame requires df sorted ascending by {date_col}; "
            "ranking an unsorted frame would silently admit look-ahead."
        )

    tickers = df[ticker_col].astype(str).values
    values = df[feature_cols].astype(float).values
    n_rows = values.shape[0]
    out = np.full(values.shape, np.nan, dtype=float)
    window = np.timedelta64(int(window_days), "D")

    for i in range(n_rows):
        t = dates[i]
        # hi is exclusive: nothing at or after it can enter the comparison
        # set. side="right" admits same-day rows, side="left" excludes them.
        # lo is the first index inside the trailing window.
        hi = int(np.searchsorted(dates, t, side="right" if include_same_day else "left"))
        lo = int(np.searchsorted(dates, t - window, side="left"))
        last_by_ticker: dict[str, int] = {}
        for j in range(lo, hi):
            last_by_ticker[tickers[j]] = j
        if include_same_day:
            # The subject row always represents its own ticker, so a same-day
            # sibling filing (8-K + 10-Q pair) never displaces it.
            last_by_ticker[tickers[i]] = i
        if not last_by_ticker:
            continue

        comp = np.fromiter(last_by_ticker.values(), dtype=np.int64, count=len(last_by_ticker))
        comp_vals = values[comp]
        row = values[i]

        n_valid = (~np.isnan(comp_vals)).sum(axis=0).astype(float)
        below = (comp_vals < row).sum(axis=0)  # NaN comparisons are False
        ties = (comp_vals == row).sum(axis=0)
        denom = np.where(n_valid > 0, n_valid, np.nan)
        pct = (below + 0.5 * ties) / denom
        pct[n_valid < min_comparators] = np.nan
        pct[np.isnan(row)] = np.nan
        out[i] = pct

    out_df = df.copy()
    out_df[feature_cols] = out
    return out_df


def transform_frame(
    df: pd.DataFrame, spec: str, feature_cols: list[str], **kwargs
) -> pd.DataFrame:
    """Dispatch to the named specification. `SECONDARY_SPEC` is the
    identity (raw levels, E1's shipped behaviour)."""
    if spec == SECONDARY_SPEC:
        return df.copy()
    if spec == PRIMARY_SPEC:
        return pit_trailing_rank_frame(df, feature_cols, **kwargs)
    raise ValueError(f"unknown specification {spec!r}; expected one of {SPEC_NAMES}")


def spec_label(spec: str) -> str:
    if spec == PRIMARY_SPEC:
        return f"PRIMARY -- PIT trailing cross-sectional percentile ranks ({PIT_RANK_WINDOW_DAYS}d window)"
    if spec == SECONDARY_SPEC:
        return "SECONDARY (mandatory) -- raw levels, as shipped in E1"
    return spec


# ---------------------------------------------------------------------------
# 2. Zero-information benchmarks
# ---------------------------------------------------------------------------


def _spearman_or_nan(pred: np.ndarray, realized: np.ndarray) -> tuple[float, float, int]:
    """Spearman IC over the pairs where BOTH values are non-null. Returns
    (ic, p, n_used); (NaN, NaN, n) when fewer than 2 usable pairs or the
    predictor is constant -- never silently 0."""
    pred = np.asarray(pred, dtype=float)
    realized = np.asarray(realized, dtype=float)
    ok = ~np.isnan(pred) & ~np.isnan(realized)
    n_used = int(ok.sum())
    if n_used < 2 or np.std(pred[ok]) == 0:
        return np.nan, np.nan, n_used
    ic, p = spearmanr(pred[ok], realized[ok])
    return float(ic), float(p), n_used


def zero_information_predictions(
    df: pd.DataFrame,
    fold: dict,
    target_col: str,
    size_col: str = "log_total_assets",
    ticker_col: str = "ticker",
) -> dict[str, np.ndarray]:
    """The two zero-information predictors for one fold's test rows.

    `size_only_rank` is the raw `size_col` level (Spearman is
    rank-invariant, so no explicit ranking step is needed).
    `ticker_training_mean_rank` is that ticker's mean realized target over
    the fold's TRAINING rows only, with the overall training mean as the
    fallback for tickers unseen in training."""
    train_idx, test_idx = fold["train_idx"], fold["test_idx"]
    size_pred = df.loc[test_idx, size_col].astype(float).values

    train_y = df.loc[train_idx, target_col].astype(float)
    train_tickers = df.loc[train_idx, ticker_col].astype(str)
    per_ticker_mean = train_y.groupby(train_tickers.values).mean()
    overall_mean = float(train_y.mean()) if len(train_y) else np.nan
    test_tickers = df.loc[test_idx, ticker_col].astype(str).values
    ticker_pred = np.array(
        [float(per_ticker_mean.get(tk, overall_mean)) for tk in test_tickers], dtype=float
    )
    return {ZERO_INFO_SIZE: size_pred, ZERO_INFO_TICKER_MEAN: ticker_pred}


def zero_information_benchmarks(
    df: pd.DataFrame,
    folds: list[dict],
    target_col: str,
    keep_mask: Optional[pd.Series] = None,
    size_col: str = "log_total_assets",
    ticker_col: str = "ticker",
) -> pd.DataFrame:
    """Per-fold IC (raw and deduplicated) for both zero-information
    benchmarks, on the SAME folds and the SAME dedup mask the models use."""
    if keep_mask is None:
        keep_values = np.ones(len(df), dtype=bool)
    else:
        keep_values = np.asarray(keep_mask.reindex(df.index).values, dtype=bool)

    rows = []
    for fold in folds:
        test_idx = fold["test_idx"]
        realized = df.loc[test_idx, target_col].astype(float).values
        keep_positions = np.where(keep_values[test_idx])[0]
        preds = zero_information_predictions(
            df, fold, target_col, size_col=size_col, ticker_col=ticker_col
        )
        for name, pred in preds.items():
            ic, p, n_used = _spearman_or_nan(pred, realized)
            ic_dd, p_dd, n_used_dd = _spearman_or_nan(
                pred[keep_positions], realized[keep_positions]
            )
            rows.append(
                {
                    "benchmark": name,
                    "test_quarter": str(fold["test_quarter"]),
                    "n_test": len(test_idx),
                    "n_used": n_used,
                    "spearman_ic": ic,
                    "spearman_p": p,
                    "n_test_dedup": len(keep_positions),
                    "n_used_dedup": n_used_dd,
                    "spearman_ic_dedup": ic_dd,
                    "spearman_p_dedup": p_dd,
                }
            )
    return pd.DataFrame(rows)


def zero_information_summary(bench_df: pd.DataFrame) -> pd.DataFrame:
    """Cross-fold mean / sample std (ddof=1) per benchmark, raw and dedup."""
    rows = []
    for name in ZERO_INFO_BENCHMARKS:
        sub = bench_df[bench_df["benchmark"] == name]
        if sub.empty:
            continue
        raw = sub["spearman_ic"].dropna()
        dd = sub["spearman_ic_dedup"].dropna()
        rows.append(
            {
                "benchmark": name,
                "n_folds": len(sub),
                "mean_ic_raw": raw.mean() if len(raw) else np.nan,
                "std_ic_raw": raw.std(ddof=1) if len(raw) > 1 else np.nan,
                "mean_ic_dedup": dd.mean() if len(dd) else np.nan,
                "std_ic_dedup": dd.std(ddof=1) if len(dd) > 1 else np.nan,
                "positive_folds_dedup": int((dd > 0).sum()),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 3. Within-fold bootstrap noise anchor
# ---------------------------------------------------------------------------


def rowwise_spearman(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Spearman correlation of each ROW of `x` against the same row of `y`
    (both (B, n)). Pearson-on-midranks, i.e. numerically identical to
    `scipy.stats.spearmanr` including tie handling -- pinned against scipy
    in `test_spec.py`. Rows where either ranking is constant return NaN."""
    rx = rankdata(x, axis=1).astype(float)
    ry = rankdata(y, axis=1).astype(float)
    rx -= rx.mean(axis=1, keepdims=True)
    ry -= ry.mean(axis=1, keepdims=True)
    num = (rx * ry).sum(axis=1)
    den = np.sqrt((rx * rx).sum(axis=1) * (ry * ry).sum(axis=1))
    return np.where(den > 0, num / np.where(den > 0, den, 1.0), np.nan)


def bootstrap_delta_sd(
    pred_a: np.ndarray,
    pred_b: np.ndarray,
    realized: np.ndarray,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, int]:
    """Bootstrap SD of (IC_a - IC_b) with the FITTED PREDICTIONS HELD FIXED
    and only the evaluation rows resampled with replacement. Returns
    (sd, n_degenerate_resamples) -- degenerate resamples (a constant
    ranking) are NaN and excluded from the SD, and their count is reported
    rather than hidden."""
    pred_a = np.asarray(pred_a, dtype=float)
    pred_b = np.asarray(pred_b, dtype=float)
    realized = np.asarray(realized, dtype=float)
    n = len(realized)
    if n < 3:
        return np.nan, 0
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_resamples, n))
    d = rowwise_spearman(pred_a[idx], realized[idx]) - rowwise_spearman(
        pred_b[idx], realized[idx]
    )
    n_bad = int(np.isnan(d).sum())
    valid = d[~np.isnan(d)]
    sd = float(valid.std(ddof=1)) if len(valid) > 1 else np.nan
    return sd, n_bad


def chi2_std_ci(sample_std: float, n_obs: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact chi-square CI for a normal standard deviation estimated from
    `n_obs` observations (n_obs - 1 df). This is the interval
    `EXPANSION_PLAN.md` §2a's 6-number noise anchor never carried."""
    if not np.isfinite(sample_std) or n_obs < 2:
        return np.nan, np.nan
    dof = n_obs - 1
    lo = sample_std * np.sqrt(dof / chi2.ppf(1 - alpha / 2, dof))
    hi = sample_std * np.sqrt(dof / chi2.ppf(alpha / 2, dof))
    return float(lo), float(hi)


def bootstrap_noise_anchor(
    df: pd.DataFrame,
    folds: list[dict],
    feature_cols_a: list[str],
    feature_cols_b: list[str],
    fit_predict_fn: Callable[[pd.DataFrame, list[str], np.ndarray, np.ndarray], np.ndarray],
    target_col: str,
    keep_mask: Optional[pd.Series] = None,
    n_resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[pd.DataFrame, dict]:
    """Per-fold within-fold bootstrap of the (a - b) IC delta on the
    DEDUPLICATED test rows, plus the summary that replaces the 6-number
    noise anchor. `fit_predict_fn` is injected (normally
    `backtest.fit_predict`) so this module stays import-free of the model
    code and testable on a stub."""
    if keep_mask is None:
        keep_values = np.ones(len(df), dtype=bool)
    else:
        keep_values = np.asarray(keep_mask.reindex(df.index).values, dtype=bool)

    rows = []
    for i, fold in enumerate(folds):
        train_idx, test_idx = fold["train_idx"], fold["test_idx"]
        realized = df.loc[test_idx, target_col].astype(float).values
        keep_positions = np.where(keep_values[test_idx])[0]
        pred_a = np.asarray(fit_predict_fn(df, feature_cols_a, train_idx, test_idx), dtype=float)
        pred_b = np.asarray(fit_predict_fn(df, feature_cols_b, train_idx, test_idx), dtype=float)

        a_dd, b_dd, y_dd = pred_a[keep_positions], pred_b[keep_positions], realized[keep_positions]
        ic_a, _, _ = _spearman_or_nan(a_dd, y_dd)
        ic_b, _, _ = _spearman_or_nan(b_dd, y_dd)
        sd, n_bad = bootstrap_delta_sd(a_dd, b_dd, y_dd, n_resamples=n_resamples, seed=seed + i)
        rows.append(
            {
                "test_quarter": str(fold["test_quarter"]),
                "n_test": len(test_idx),
                "n_test_dedup": len(keep_positions),
                "fold_delta_dedup": ic_a - ic_b,
                "bootstrap_sd_of_delta": sd,
                "n_degenerate_resamples": n_bad,
            }
        )

    per_fold = pd.DataFrame(rows)
    deltas = per_fold["fold_delta_dedup"].dropna()
    sds = per_fold["bootstrap_sd_of_delta"].dropna()
    k = len(deltas)

    cross_std_ddof1 = float(deltas.std(ddof=1)) if k > 1 else np.nan
    cross_std_ddof0 = float(deltas.std(ddof=0)) if k > 0 else np.nan
    ci_lo, ci_hi = chi2_std_ci(cross_std_ddof1, k)
    mean_sd = float(sds.mean()) if len(sds) else np.nan
    rms_sd = float(np.sqrt((sds.values ** 2).mean())) if len(sds) else np.nan
    floor_var = cross_std_ddof1 ** 2 - rms_sd ** 2 if np.isfinite(cross_std_ddof1) and np.isfinite(rms_sd) else np.nan
    implied_floor = float(np.sqrt(floor_var)) if np.isfinite(floor_var) and floor_var > 0 else 0.0

    # Formal test of the floor, in BOTH directions. Under floor = 0 the
    # cross-fold sum of squares is chi-square with k-1 df scaled by the
    # within-fold sampling variance, so the ratio locates the observed spread
    # against pure sampling. Reported two-sided-aware (both tails) because at
    # k = 6 a spread BELOW the sampling level is just as much a fluke as one
    # above it, and quoting only one tail is how "the floor is zero" gets
    # over-claimed.
    if np.isfinite(cross_std_ddof1) and np.isfinite(rms_sd) and rms_sd > 0 and k > 1:
        var_ratio = (cross_std_ddof1 ** 2) / (rms_sd ** 2)
        p_spread_exceeds_sampling = float(chi2.sf((k - 1) * var_ratio, k - 1))
        p_spread_below_sampling = float(chi2.cdf((k - 1) * var_ratio, k - 1))
    else:
        var_ratio = np.nan
        p_spread_exceeds_sampling = np.nan
        p_spread_below_sampling = np.nan

    summary = {
        "n_folds": int(k),
        "n_resamples_per_fold": int(n_resamples),
        "mean_n_test_dedup": float(per_fold["n_test_dedup"].mean()) if len(per_fold) else np.nan,
        "mean_fold_delta": float(deltas.mean()) if k else np.nan,
        "cross_fold_std_ddof1": cross_std_ddof1,
        "cross_fold_std_ddof0_published_convention": cross_std_ddof0,
        "cross_fold_std_ddof1_chi2_ci_lo": ci_lo,
        "cross_fold_std_ddof1_chi2_ci_hi": ci_hi,
        "mean_within_fold_bootstrap_sd": mean_sd,
        "rms_within_fold_bootstrap_sd": rms_sd,
        "implied_regime_floor_sd": implied_floor,
        "cross_var_over_bootstrap_var": float(var_ratio) if np.isfinite(var_ratio) else np.nan,
        "p_spread_exceeds_sampling": p_spread_exceeds_sampling,
        "p_spread_below_sampling": p_spread_below_sampling,
        "se_of_cross_fold_mean_naive": cross_std_ddof1 / np.sqrt(k) if k else np.nan,
        "total_degenerate_resamples": int(per_fold["n_degenerate_resamples"].sum()) if len(per_fold) else 0,
    }
    return per_fold, summary


# ---------------------------------------------------------------------------
# 4. Non-embargoed-label census (a fold-structure convention, measured)
# ---------------------------------------------------------------------------


def embargo_census(
    df: pd.DataFrame,
    folds: list[dict],
    target_end_col: str = "target_end_date",
) -> pd.DataFrame:
    """Per fold: how many TRAINING rows have a target window that resolves
    on or after the test quarter starts.

    The walk-forward split is on `filing_date` only, so a training row
    filed the day before a fold boundary carries a 63-trading-day forward
    label that resolves ~3 months INSIDE the test quarter. That is not
    feature look-ahead and `assert_no_fold_leakage()` is right to pass, but
    it is an un-pre-registered convention (no embargo / no purge) whose
    population has never been stated. Stating it is the point of this
    function; whether to embargo is a G3 decision, not one this module
    makes."""
    if target_end_col not in df.columns:
        return pd.DataFrame()
    end_dates = pd.to_datetime(df[target_end_col])
    rows = []
    for fold in folds:
        q = fold["test_quarter"]
        start = q.start_time if hasattr(q, "start_time") else pd.Timestamp(str(q))
        train_ends = end_dates.iloc[fold["train_idx"]]
        n_overlap = int((train_ends >= start).sum())
        n_known = int(train_ends.notna().sum())
        rows.append(
            {
                "test_quarter": str(q),
                "n_train": len(fold["train_idx"]),
                "n_train_with_target_end": n_known,
                "n_train_labels_resolving_in_or_after_test_quarter": n_overlap,
                "share_non_embargoed": (n_overlap / n_known) if n_known else np.nan,
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 5. Report sections -- shared by backtest.py and diagnose.py so the wording
#    cannot drift between the two generators.
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


def specification_section_lines(active_spec: str) -> list[str]:
    """The standing pre-registration header. Every generated report states
    which specification produced its numbers and which one is primary."""
    lines = [
        "## Feature specification (pre-registered, H2 / F2.5 hardening)",
        "",
        f"- **PRIMARY:** `{PRIMARY_SPEC}` -- PIT trailing cross-sectional percentile ranks, "
        f"{PIT_RANK_WINDOW_DAYS}-day trailing window, one observation per ticker, "
        f"`include_same_day={INCLUDE_SAME_DAY}` (subject row always represents its own ticker), "
        f"NaN preserved as NaN, fewer than {MIN_COMPARATORS} non-null comparators -> NaN "
        "(`spec.pit_trailing_rank_frame()` -- the FUNCTION AND ITS ARGUMENTS are what is "
        "pre-registered, not the transform's name).",
        f"- **SECONDARY (mandatory, always reported):** `{SECONDARY_SPEC}` -- the raw levels E1 shipped.",
        f"- **This report's numbers were produced under: `{active_spec}`** ({spec_label(active_spec)}).",
        "",
        "Rationale (a priori, not results-driven): raw feature levels encode company identity "
        "almost exactly (`methodology_audit.md` §(c) C9 -- ICC 0.987 for `log_total_assets`, "
        "0.986 leverage, 0.984 equity/assets), so both arms of a text-vs-numeric comparison ride "
        "the same large company-persistence term and the estimand is a small residual on it. "
        "Rank-normalising against a trailing cross-section strips the level. The two "
        "zero-information benchmark rows below are the direct measurement of that problem.",
        "",
        f"**Contamination warning.** {SPEC_CONTAMINATION_WARNING}",
        "",
        "**Implementation sensitivity, measured (H2, 2026-08-25).** Seven mutually-defensible, all "
        "look-ahead-free implementations of the SAME named transform (differing only in subject "
        "inclusion, same-day-peer inclusion, last-per-ticker vs. every-row comparison sets, and "
        "581-row vs. 630-row ranking cross-section) move E1's headline dedup delta across "
        "**[-0.0172, +0.0422]** -- a 0.059 range, ~2x the honest MDE -- and the cross-fold sample "
        "std across [0.0496, 0.1549]. Naming a transform pre-registers nothing. Named sensitivity "
        "variant, reproducible from this module: "
        "`pit_trailing_rank_frame(..., include_same_day=False)`.",
        "",
        "**Look-ahead status of the transform:** no row with `filing_date` later than the subject "
        "row's can enter any comparison set (pinned in `test_spec.py`). The transform inherits the "
        "corpus-wide `filing_date` day-granularity convention and therefore audit item C1 "
        "(45% of filings accepted after 16:00 ET carrying that day's `filing_date`, "
        "`data/F2_INGESTION_REPORT.md` §3.3) -- a property of the date column, queued for G3, not "
        "introduced here.",
        "",
    ]
    return lines


def zero_information_section_lines(
    bench_df: Optional[pd.DataFrame], bench_summary: Optional[pd.DataFrame]
) -> list[str]:
    """The two STANDING zero-information benchmark rows. Present in every
    generated report; when the inputs were not computed the section says so
    explicitly rather than being silently absent."""
    lines = ["## Zero-information benchmarks (STANDING -- read every IC above against these)", ""]
    if bench_df is None or bench_summary is None or bench_df.empty:
        lines += [
            "**NOT COMPUTED IN THIS RUN.** This report was generated without the standing "
            "zero-information benchmark inputs, so no IC above has been read against what a "
            "predictor containing no information achieves on the same folds. Treat every IC in "
            "this report as un-benchmarked.",
            "",
        ]
        return lines
    lines += [
        f"- **`{ZERO_INFO_SIZE}`** -- rank by `log_total_assets` alone (one near-constant-per-company "
        "variable, zero fitting, zero text).",
        f"- **`{ZERO_INFO_TICKER_MEAN}`** -- rank by the ticker's mean realized excess return over "
        "that fold's TRAINING rows (zero features; pure company persistence). Tickers unseen in "
        "training fall back to the overall training mean.",
        "",
        "Both are computed on the RAW frame, on the SAME folds and the SAME dedup mask as the "
        "fitted models, so they are comparable across feature specifications. They are the "
        "measurement of `methodology_audit.md` §(c) C9: if a fitted model does not beat them, its "
        "IC is cross-sectional persistence, not predictive skill.",
        "",
        "Cross-fold summary (std is the SAMPLE std, ddof=1):",
        "",
    ]
    lines += _fmt_table(
        bench_summary,
        ["benchmark", "n_folds", "mean_ic_raw", "std_ic_raw", "mean_ic_dedup", "std_ic_dedup", "positive_folds_dedup"],
    )
    lines += ["", "Per fold:", ""]
    lines += _fmt_table(
        bench_df,
        ["benchmark", "test_quarter", "n_test", "spearman_ic", "n_test_dedup", "spearman_ic_dedup"],
    )
    lines += [
        "",
        f"**`{ZERO_INFO_TICKER_MEAN}` uses training-row targets**, which are 63-trading-day forward "
        "windows that resolve after the train/test boundary -- exactly the same non-embargoed-label "
        "property the fitted models have. It is not cleaner than they are, and the comparison is "
        "like-for-like on that axis.",
        "",
    ]
    return lines


def bootstrap_section_lines(
    per_fold: Optional[pd.DataFrame], summary: Optional[dict], spec_label_text: str = ""
) -> list[str]:
    """The STANDING within-fold bootstrap noise-anchor section."""
    title = "## Within-fold bootstrap noise anchor (STANDING)"
    if spec_label_text:
        title += f" -- {spec_label_text}"
    lines = [title, ""]
    if per_fold is None or summary is None or per_fold.empty:
        lines += [
            "**NOT COMPUTED IN THIS RUN.** No noise anchor accompanies the deltas above; any MDE "
            "or null bound quoted against them is unsupported by this report.",
            "",
        ]
        return lines
    lines += [
        f"Each fold's fitted predictions are held FIXED and only that fold's deduplicated test rows "
        f"are resampled with replacement ({summary['n_resamples_per_fold']} resamples/fold, "
        f"`numpy.random.default_rng`, seed base {BOOTSTRAP_SEED}); the delta is recomputed on each "
        "resample. This estimates the sampling component of the delta from ~40 rows x thousands of "
        "resamples per fold, instead of from the standard deviation of six numbers.",
        "",
    ]
    lines += _fmt_table(
        per_fold,
        ["test_quarter", "n_test_dedup", "fold_delta_dedup", "bootstrap_sd_of_delta", "n_degenerate_resamples"],
    )
    lines += [
        "",
        f"- mean within-fold bootstrap SD of the delta = **{summary['mean_within_fold_bootstrap_sd']:.4f}** "
        f"(RMS, the variance-decomposition-correct anchor = **{summary['rms_within_fold_bootstrap_sd']:.4f}**)",
        f"- cross-fold SAMPLE std of the {summary['n_folds']} fold deltas (ddof=1) = "
        f"**{summary['cross_fold_std_ddof1']:.4f}**; 95% chi-square CI "
        f"[{summary['cross_fold_std_ddof1_chi2_ci_lo']:.4f}, {summary['cross_fold_std_ddof1_chi2_ci_hi']:.4f}]",
        f"- the same quantity under the PUBLISHED population convention (ddof=0), for continuity with "
        f"pre-2026-08-25 reports = {summary['cross_fold_std_ddof0_published_convention']:.4f}",
        f"- implied regime/training floor SD = sqrt(max(0, cross_var - mean within-fold var)) = "
        f"**{summary['implied_regime_floor_sd']:.4f}**",
        f"- cross-fold variance / within-fold bootstrap variance = "
        f"{summary.get('cross_var_over_bootstrap_var', float('nan')):.3f}; one-sided chi-square "
        f"p(spread > sampling) = {summary.get('p_spread_exceeds_sampling', float('nan')):.3f}, "
        f"p(spread < sampling) = {summary.get('p_spread_below_sampling', float('nan')):.3f}",
        f"- naive SE of the cross-fold mean (std/sqrt(k), assumes independent folds) = "
        f"{summary['se_of_cross_fold_mean_naive']:.4f}",
        "",
        "**How to read the floor.** A floor of 0 would mean the observed fold-to-fold spread is "
        "fully accounted for by test-set sampling noise, with nothing left over for a market-regime "
        "component -- i.e. adding COMPANIES buys power. A floor above 0 means part of the spread is "
        "NOT sampling and is divided down only by more TEST QUARTERS, never by more companies "
        "(`data/expansion_recon_2026-08-20.json` caveat (1)). **Read the chi-square p-values above "
        "before reading the point estimate.** It is a truncated-at-zero estimator resting on a "
        "cross-fold std with k-1 degrees of freedom; at k = 6 neither tail is anywhere near "
        "significant, so a measured floor of 0.0000 does NOT establish that the floor is absent and "
        "a measured floor of ~0.10 does NOT establish that it is present. On E1 the two "
        "pre-registered specifications give 0.0000 and 0.0992 on the same folds -- which is the "
        "honest answer: at 6 folds the floor is unidentified, and recon caveat (1) is NOT resolved "
        "by this estimator once the feature specification is allowed to vary.",
        "",
        "**Fold non-independence is NOT in any of these numbers.** The naive SE assumes independent "
        "fold deltas; expanding-window training sets are nested and 63-trading-day target windows "
        "straddle fold boundaries, so effective k < nominal k and every MDE derived from this anchor "
        "is a LOWER BOUND. At E2's ~26 folds the lag-1 autocorrelation of fold deltas becomes "
        "measurable for the first time and must be measured, not assumed.",
        "",
    ]
    return lines


def embargo_section_lines(census: Optional[pd.DataFrame]) -> list[str]:
    """Standing statement of the non-embargoed-label population."""
    lines = ["## Label-embargo census (fold-structure convention, measured not assumed)", ""]
    if census is None or census.empty:
        lines += [
            "**NOT COMPUTED IN THIS RUN.**",
            "",
        ]
        return lines
    total_train = int(census["n_train_with_target_end"].sum())
    total_overlap = int(census["n_train_labels_resolving_in_or_after_test_quarter"].sum())
    share = total_overlap / total_train if total_train else float("nan")
    lines += [
        "The walk-forward split is on `filing_date` only, so training rows filed shortly before a "
        "fold boundary carry 63-trading-day forward labels that RESOLVE inside the test quarter. "
        "That is not feature look-ahead -- no test-row feature or test-row label enters training, "
        "and `assert_no_fold_leakage()` is correct to pass -- but there is no embargo/purge, and "
        "the population has never been stated. It is stated here:",
        "",
    ]
    lines += _fmt_table(
        census,
        ["test_quarter", "n_train", "n_train_labels_resolving_in_or_after_test_quarter", "share_non_embargoed"],
    )
    lines += [
        "",
        f"Pooled across folds: **{total_overlap} of {total_train} training labels "
        f"({share:.1%})** resolve on or after their fold's test quarter begins. The target is an "
        "EXCESS return against a same-window universe average, which differences out the "
        "market-wide component of that overlap but not a company-specific one. Whether to embargo "
        "is a G3 pre-registration decision; this report only measures it.",
        "",
    ]
    return lines
