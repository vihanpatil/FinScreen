"""
diagnose.py -- FinScreen Phase D signal diagnosis.

Owner's Step-4 go/no-go ruling (`HANDOFF.md` §3, 2026-08-18, verbatim: "GO,
diagnosis-scoped") selected ROADMAP Phase C outcome (2): the backtest in
`data/backtest_report.md` shows a mixed, sign-unstable text-vs-numeric IC
delta (RAW cross-fold mean +0.0177, DEDUPLICATED cross-fold mean -0.0097 --
the two disagree in sign), and Phase D's job is to diagnose WHICH
categories/companies drive that instability, not to add depth for its own
sake.

This script does NOT retrain a "final" model, does NOT change the go/no-go
verdict, and does NOT alter `features.py`, `backtest.py`, or
`data/features.parquet` (hard rule, `HANDOFF.md` prompt). It reuses
`backtest.py`'s fold construction, dedup mask, `fit_predict`, and
`XGB_PARAMS` so every analysis below runs on BYTE-IDENTICAL folds and
discipline as the backtest the owner's GO was based on -- see
`test_diagnose.py` for the assertion that this is actually true, not just
claimed.

-----------------------------------------------------------------------
Five analyses (ROADMAP / Phase D scope)
-----------------------------------------------------------------------
1. Feature-family ablations: numeric-only (reference) vs. numeric+each of
   {sentiment, guidance, red-flags, section-mix} vs. full (all text
   features). Per-fold dedup IC and delta-vs-numeric, on the full sample
   AND on the 10-Q/10-K form-controlled subset (section-mix and
   `redflag_any_rate_press` are near-perfect SEC-form proxies --
   `backtest.py`'s own docstring calls this out -- so the form-controlled
   grid is the honest read for those two families specifically).
2. Leave-one-company-out: refit the FULL model per fold with each of the 25
   tickers excluded from BOTH train and test (25 x 6 = 150 refits), report
   the per-ticker delta on cross-fold mean dedup IC vs. the all-25-ticker
   baseline; aggregated to the 5 `data/universe.csv` sectors. Also a
   per-ticker predicted-vs-realized Spearman across that ticker's own
   out-of-fold test observations (n~12-24 each -- explicitly indicative-
   only at this n).
3. Fold sensitivity: drop-one-fold cross-fold means of the text-minus-
   numeric dedup IC delta (6 leave-one-fold-out means), to see whether any
   single quarter (2025Q4 especially -- the fold with the largest-magnitude
   IC in the backtest) dominates the overall sign.
4. Red-flag category contribution: per-fold permutation importance
   (permute one column within a COPY of the already-built test-fold
   feature matrix, re-score the ALREADY-FITTED full model -- never refit),
   for the 13 `redflag_*` columns, on the form-controlled subset. Carries
   the red-flag exact-set-match caveat verbatim next to the table.
5. "What this diagnosis can and cannot conclude" -- signal-concentration
   statements with uncertainty, an explicit list of what n=25 tickers / 6
   folds cannot support, and no recommendation language (non-goals,
   `HANDOFF.md` §1, are unconditional).

No Anthropic API calls anywhere in this file. All compute is local
(pandas/numpy/scipy/xgboost), matching backtest.py's dependency footprint
exactly.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from xgboost import XGBRegressor

import backtest as B
import features as F

REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
UNIVERSE_PATH = DATA_DIR / "universe.csv"
DIAGNOSIS_REPORT_OUTPUT = DATA_DIR / "diagnosis_report.md"

# Permutation-importance repeat count -- local RandomState per (fold,
# column), never touches numpy's global RNG or XGBoost's fit-time
# random_state (which stays fixed at B.XGB_PARAMS["random_state"]=42).
PERMUTATION_REPEATS = 200
PERMUTATION_SEED_BASE = 20260818

# ---------------------------------------------------------------------------
# Feature families (Phase D analysis 1)
# ---------------------------------------------------------------------------

FAMILY_SENTIMENT = ["sentiment_mean_score", "sentiment_negative_share"]
FAMILY_GUIDANCE = ["guidance_signed_mean", "guidance_any_present"]
FAMILY_REDFLAGS = list(F.RED_FLAG_FEATURE_NAMES)  # 13 redflag_* rate columns
FAMILY_SECTION_MIX = [
    "n_text_chunks_attributed",
    "share_chunks_risk_factors",
    "share_chunks_mda",
    "share_chunks_ex99_press_release",
    "share_chunks_8k_body",
]

# Order matters -- this is the report's table order, and "numeric_only" must
# stay first (it is the reference every delta is measured against).
FEATURE_FAMILIES: dict[str, list[str]] = {
    "numeric_only": [],
    "numeric_plus_sentiment": FAMILY_SENTIMENT,
    "numeric_plus_guidance": FAMILY_GUIDANCE,
    "numeric_plus_redflags": FAMILY_REDFLAGS,
    "numeric_plus_section_mix": FAMILY_SECTION_MIX,
    "full": list(B.TEXT_FEATURES),
}

# Sanity: "full" must equal numeric + every non-overlapping text feature
# added across the other families (i.e. the families partition TEXT_FEATURES
# except full duplicates sentiment/guidance/redflags/section_mix's union).
assert set(FAMILY_SENTIMENT) | set(FAMILY_GUIDANCE) | set(FAMILY_REDFLAGS) | set(FAMILY_SECTION_MIX) == set(
    B.TEXT_FEATURES
), "feature families do not partition backtest.py's TEXT_FEATURES -- family list is stale."


def family_feature_cols(name: str) -> list[str]:
    return B.NUMERIC_FEATURES + FEATURE_FAMILIES[name]


# ---------------------------------------------------------------------------
# Analysis 1 -- feature-family ablations
# ---------------------------------------------------------------------------


def build_form_controlled_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Mirrors `backtest.run_form_controlled_ablation`'s row-filter + fold-
    build lines exactly (same `B.FORM_ABLATION_FORMS`, same
    `B.build_walk_forward_folds`, same `B.BURN_IN_END`) so the form-
    controlled subset used here is byte-identical to the one in
    `data/backtest_report.md`."""
    df_form = df[df["form"].isin(B.FORM_ABLATION_FORMS)].reset_index(drop=True)
    folds_form = B.build_walk_forward_folds(df_form, B.BURN_IN_END)
    B.assert_no_fold_leakage(df_form, folds_form)
    return df_form, folds_form


def run_family_ablation(
    df: pd.DataFrame,
    folds: list[dict],
    keep_mask: pd.Series | None = None,
    families: dict[str, list[str]] | None = None,
) -> dict[str, pd.DataFrame]:
    """Per-fold raw + dedup Spearman IC for each feature family. Mirrors
    `backtest.run_backtest`'s per-model loop exactly (same `B.fit_predict`
    call, same dedup restriction to `keep_mask`-marked test rows) but over
    an arbitrary set of feature families instead of just the two backtest.py
    reports (numeric_only / text_and_numeric)."""
    if families is None:
        families = FEATURE_FAMILIES
    if keep_mask is None:
        keep_mask = B.company_quarter_dedup_keep_mask(df)
    keep_mask_values = keep_mask.reindex(df.index).values

    out: dict[str, list[dict]] = {name: [] for name in families}
    for fold in folds:
        q = fold["test_quarter"]
        train_idx, test_idx = fold["train_idx"], fold["test_idx"]
        realized = df.loc[test_idx, B.TARGET_COL].astype(float).values
        test_keep_positions = np.where(keep_mask_values[test_idx])[0]

        for name in families:
            feats = family_feature_cols(name)
            pred = B.fit_predict(df, feats, train_idx, test_idx)
            ic, ic_p = spearmanr(pred, realized)

            pred_dedup = pred[test_keep_positions]
            realized_dedup = realized[test_keep_positions]
            if len(pred_dedup) >= 2 and np.std(pred_dedup) > 0:
                ic_dedup, ic_p_dedup = spearmanr(pred_dedup, realized_dedup)
            else:
                ic_dedup, ic_p_dedup = np.nan, np.nan

            out[name].append(
                {
                    "test_quarter": str(q),
                    "n_test": len(test_idx),
                    "n_test_dedup": len(pred_dedup),
                    "spearman_ic": ic,
                    "spearman_p": ic_p,
                    "spearman_ic_dedup": ic_dedup,
                    "spearman_p_dedup": ic_p_dedup,
                }
            )
    return {name: pd.DataFrame(v) for name, v in out.items()}


def family_delta_long(results: dict[str, pd.DataFrame], families_order: list[str]) -> pd.DataFrame:
    """Long-format table: one row per (family, fold), with the family's
    dedup/raw IC and its delta against `numeric_only` in the SAME fold
    (folds are guaranteed aligned across families -- every family in
    `results` was built from the identical `folds` list)."""
    ref = results["numeric_only"]
    rows = []
    for name in families_order:
        res = results[name]
        for i in range(len(res)):
            rows.append(
                {
                    "family": name,
                    "test_quarter": res.loc[i, "test_quarter"],
                    "n_test": res.loc[i, "n_test"],
                    "n_test_dedup": res.loc[i, "n_test_dedup"],
                    "spearman_ic": res.loc[i, "spearman_ic"],
                    "spearman_ic_dedup": res.loc[i, "spearman_ic_dedup"],
                    "delta_dedup_vs_numeric": res.loc[i, "spearman_ic_dedup"] - ref.loc[i, "spearman_ic_dedup"],
                    "delta_raw_vs_numeric": res.loc[i, "spearman_ic"] - ref.loc[i, "spearman_ic"],
                }
            )
    return pd.DataFrame(rows)


def family_delta_summary(long_df: pd.DataFrame, families_order: list[str]) -> pd.DataFrame:
    rows = []
    for name in families_order:
        sub = long_df[long_df["family"] == name]
        d_dedup = sub["delta_dedup_vs_numeric"].dropna()
        d_raw = sub["delta_raw_vs_numeric"].dropna()
        rows.append(
            {
                "family": name,
                "n_folds": len(sub),
                "mean_delta_dedup_vs_numeric": d_dedup.mean() if len(d_dedup) else np.nan,
                "std_delta_dedup_vs_numeric": d_dedup.std(ddof=0) if len(d_dedup) else np.nan,
                "positive_folds_dedup": int((d_dedup > 0).sum()),
                "n_folds_dedup_valid": len(d_dedup),
                "mean_delta_raw_vs_numeric": d_raw.mean() if len(d_raw) else np.nan,
                "positive_folds_raw": int((d_raw > 0).sum()),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Analysis 2 -- leave-one-company-out + per-ticker predicted-vs-realized
# ---------------------------------------------------------------------------


def run_leave_one_ticker_out(df: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    """For each ticker, drop every row for that ticker BEFORE building folds
    (so it can appear in neither train nor test of any fold), rebuild folds
    with `B.build_walk_forward_folds` (byte-identical fold logic, smaller
    input frame), refit the FULL (text+numeric) model per fold via
    `B.fit_predict`, and report the delta in cross-fold mean dedup IC vs.
    the all-25-ticker baseline. 25 x 6 = 150 cheap refits, `B.XGB_PARAMS`
    unchanged throughout."""
    baseline_folds = B.build_walk_forward_folds(df, B.BURN_IN_END)
    baseline_res = run_family_ablation(df, baseline_folds, families={"full": FEATURE_FAMILIES["full"]})["full"]
    baseline_mean_dedup_ic = baseline_res["spearman_ic_dedup"].mean(skipna=True)

    rows = []
    for t in tickers:
        df_loco = df[df["ticker"] != t].reset_index(drop=True)
        assert t not in df_loco["ticker"].unique(), f"leave-one-out leak: {t} still present after filtering"
        folds_loco = B.build_walk_forward_folds(df_loco, B.BURN_IN_END)
        B.assert_no_fold_leakage(df_loco, folds_loco)
        # Leakage guard specific to this analysis: the excluded ticker must
        # not appear in ANY fold's train_idx or test_idx (trivially true
        # since df_loco itself never contains it, but asserted explicitly
        # per the diagnosis-scope requirement and pinned in
        # test_diagnose.py).
        for fold in folds_loco:
            train_tickers = set(df_loco.loc[fold["train_idx"], "ticker"])
            test_tickers = set(df_loco.loc[fold["test_idx"], "ticker"])
            assert t not in train_tickers and t not in test_tickers

        res = run_family_ablation(df_loco, folds_loco, families={"full": FEATURE_FAMILIES["full"]})["full"]
        mean_dedup_ic = res["spearman_ic_dedup"].mean(skipna=True)
        rows.append(
            {
                "ticker": t,
                "n_folds": len(res),
                "loco_mean_ic_dedup": mean_dedup_ic,
                "delta_vs_baseline_25ticker": mean_dedup_ic - baseline_mean_dedup_ic,
            }
        )
    out = pd.DataFrame(rows).sort_values("delta_vs_baseline_25ticker", ascending=False).reset_index(drop=True)
    return out, float(baseline_mean_dedup_ic)


def aggregate_loco_to_sector(loco_df: pd.DataFrame, universe_df: pd.DataFrame) -> pd.DataFrame:
    merged = loco_df.merge(universe_df[["ticker", "sector"]], on="ticker", how="left")
    assert merged["sector"].notna().all(), "some tickers in leave-one-out results have no universe.csv sector"
    grp = merged.groupby("sector")["delta_vs_baseline_25ticker"].agg(["mean", "std", "count"])
    grp = grp.rename(columns={"mean": "mean_delta_vs_baseline", "std": "std_delta_vs_baseline", "count": "n_tickers"})
    return grp.reset_index().sort_values("mean_delta_vs_baseline", ascending=False).reset_index(drop=True)


def per_ticker_predicted_vs_realized(df: pd.DataFrame, folds: list[dict]) -> pd.DataFrame:
    """Out-of-fold predictions from the standard 25-ticker FULL model
    (same folds/features/fit as backtest.py's text_and_numeric model),
    collected per TEST-fold row (never a training-fold row -- there is no
    prediction for those), grouped by ticker. n per ticker is only that
    ticker's rows that happen to fall in a test quarter (2025Q1-2026Q2),
    roughly half its total observations -- EXPLICITLY INDICATIVE-ONLY, not
    a per-ticker validated result: n~12-24 is far too small for a
    standalone significance claim."""
    rows = []
    for fold in folds:
        train_idx, test_idx = fold["train_idx"], fold["test_idx"]
        pred = B.fit_predict(df, FEATURE_FAMILIES_FULL_COLS, train_idx, test_idx)
        realized = df.loc[test_idx, B.TARGET_COL].astype(float).values
        tickers = df.loc[test_idx, "ticker"].values
        for tk, p, r in zip(tickers, pred, realized):
            rows.append({"ticker": tk, "predicted": p, "realized": r})
    per_row = pd.DataFrame(rows)

    out = []
    for tk, sub in per_row.groupby("ticker"):
        n = len(sub)
        if n >= 3 and sub["predicted"].std() > 0:
            ic, p = spearmanr(sub["predicted"], sub["realized"])
        else:
            ic, p = np.nan, np.nan
        out.append({"ticker": tk, "n": n, "spearman_ic": ic, "spearman_p": p})
    return pd.DataFrame(out).sort_values("spearman_ic", ascending=False, na_position="last").reset_index(drop=True)


FEATURE_FAMILIES_FULL_COLS = family_feature_cols("full")
assert FEATURE_FAMILIES_FULL_COLS == B.FULL_FEATURES, "full family must equal backtest.py's FULL_FEATURES exactly"


# ---------------------------------------------------------------------------
# Analysis 3 -- fold sensitivity (drop-one-fold cross-fold means)
# ---------------------------------------------------------------------------


def fold_sensitivity(full_family_delta_df: pd.DataFrame) -> pd.DataFrame:
    """`full_family_delta_df`: the "full" family's per-fold
    `delta_dedup_vs_numeric` column from `family_delta_long` (i.e. the
    text-minus-numeric dedup IC delta, one value per fold -- identical to
    `data/backtest_report.md`'s `IC_dedup_delta_text_minus_numeric` column).
    Returns, for each of the 6 folds, the cross-fold MEAN of the other 5
    deltas (drop-one-fold), plus the all-6-fold mean as a reference row."""
    deltas = full_family_delta_df["delta_dedup_vs_numeric"].tolist()
    quarters = full_family_delta_df["test_quarter"].tolist()
    n = len(deltas)
    total = float(np.nansum(deltas))
    valid_n = int(np.sum(~np.isnan(deltas)))

    rows = []
    full_mean = total / valid_n if valid_n else np.nan
    for i in range(n):
        if np.isnan(deltas[i]):
            loo_mean = full_mean
            loo_n = valid_n
        else:
            loo_n = valid_n - 1
            loo_mean = (total - deltas[i]) / loo_n if loo_n else np.nan
        rows.append(
            {
                "dropped_fold": quarters[i],
                "dropped_fold_delta": deltas[i],
                "loo_mean_ic_dedup_delta": loo_mean,
                "loo_n_folds": loo_n,
                "sign_flip_vs_full_6fold_mean": (
                    np.sign(loo_mean) != np.sign(full_mean) if not (np.isnan(loo_mean) or np.isnan(full_mean)) else False
                ),
            }
        )
    rows.append(
        {
            "dropped_fold": "NONE (all 6 folds)",
            "dropped_fold_delta": np.nan,
            "loo_mean_ic_dedup_delta": full_mean,
            "loo_n_folds": valid_n,
            "sign_flip_vs_full_6fold_mean": False,
        }
    )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Analysis 4 -- red-flag category permutation importance (test folds only,
# form-controlled subset, NEVER a refit)
# ---------------------------------------------------------------------------


def fit_and_predict_with_model(
    df: pd.DataFrame, feature_cols: list[str], train_idx: np.ndarray, test_idx: np.ndarray
) -> tuple[XGBRegressor, np.ndarray, np.ndarray]:
    """Mirrors `backtest.fit_predict` EXACTLY (same X/y construction, same
    `B.XGB_PARAMS`, same `B.TARGET_COL`) but also returns the fitted model
    object and the raw X_test matrix -- needed here (and only here) so
    permutation importance can re-score the SAME fitted model on permuted
    copies of X_test without ever calling `.fit()` again. `test_diagnose.py`
    pins this against `backtest.fit_predict` to guarantee it never silently
    drifts from the reused function."""
    X_train = df.loc[train_idx, feature_cols].astype(float).values
    y_train = df.loc[train_idx, B.TARGET_COL].astype(float).values
    X_test = df.loc[test_idx, feature_cols].astype(float).values
    model = XGBRegressor(**B.XGB_PARAMS)
    model.fit(X_train, y_train)
    return model, model.predict(X_test), X_test


def permute_column_and_rescore(
    model: XGBRegressor,
    X_test: np.ndarray,
    realized: np.ndarray,
    col_idx: int,
    n_repeats: int = PERMUTATION_REPEATS,
    seed: int = 0,
) -> tuple[float, float]:
    """Baseline IC (unpermuted) and mean IC-drop over `n_repeats` shuffles
    of column `col_idx`, evaluated on a fresh COPY of `X_test` each time
    (`X_test` itself, and the fitted `model`, are never mutated -- pinned in
    test_diagnose.py). Uses a local `np.random.RandomState`, never the
    global numpy RNG."""
    if len(X_test) < 2 or np.std(model.predict(X_test)) == 0:
        return np.nan, np.nan
    baseline_pred = model.predict(X_test)
    baseline_ic, _ = spearmanr(baseline_pred, realized)

    rng = np.random.RandomState(seed)
    drops = []
    for _ in range(n_repeats):
        X_perm = X_test.copy()  # test-fold COPY only -- see docstring
        perm_order = rng.permutation(len(X_perm))
        X_perm[:, col_idx] = X_perm[perm_order, col_idx]
        pred_perm = model.predict(X_perm)
        if np.std(pred_perm) > 0:
            ic_perm, _ = spearmanr(pred_perm, realized)
        else:
            ic_perm = 0.0
        drops.append(baseline_ic - ic_perm)
    return float(baseline_ic), float(np.mean(drops))


def run_redflag_permutation_importance(df_form: pd.DataFrame, folds_form: list[dict]) -> pd.DataFrame:
    full_cols = FEATURE_FAMILIES_FULL_COLS
    redflag_positions = {name: full_cols.index(name) for name in FAMILY_REDFLAGS}

    rows = []
    for fold_i, fold in enumerate(folds_form):
        q = fold["test_quarter"]
        train_idx, test_idx = fold["train_idx"], fold["test_idx"]
        realized = df_form.loc[test_idx, B.TARGET_COL].astype(float).values
        model, baseline_pred, X_test_orig = fit_and_predict_with_model(df_form, full_cols, train_idx, test_idx)
        X_test_before = X_test_orig.copy()  # for the never-mutated pin

        for col_name, col_idx in redflag_positions.items():
            seed = (PERMUTATION_SEED_BASE + fold_i * 1000 + col_idx) % (2**31 - 1)
            baseline_ic, mean_drop = permute_column_and_rescore(
                model, X_test_orig, realized, col_idx, seed=seed
            )
            rows.append(
                {
                    "test_quarter": str(q),
                    "n_test": len(test_idx),
                    "redflag_column": col_name,
                    "baseline_ic": baseline_ic,
                    "mean_ic_drop_when_permuted": mean_drop,
                }
            )
        assert np.array_equal(X_test_orig, X_test_before, equal_nan=True), "permutation mutated the shared X_test array"
    return pd.DataFrame(rows)


def redflag_permutation_summary(perm_df: pd.DataFrame) -> pd.DataFrame:
    grp = perm_df.groupby("redflag_column")["mean_ic_drop_when_permuted"]
    out = grp.agg(["mean", "std", "count"]).rename(
        columns={"mean": "mean_ic_drop_across_folds", "std": "std_ic_drop_across_folds", "count": "n_folds"}
    )
    return out.reset_index().sort_values("mean_ic_drop_across_folds", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _fmt_table(df: pd.DataFrame, cols: list[str]) -> list[str]:
    return B._fmt_table(df, cols)


def _summary_row(series: pd.Series) -> str:
    return B._summary_row(series)


def write_diagnosis_report(
    df: pd.DataFrame,
    n_target_dropped: int,
    families_order: list[str],
    results_full: dict[str, pd.DataFrame],
    long_full: pd.DataFrame,
    summary_full: pd.DataFrame,
    df_form: pd.DataFrame,
    results_form: dict[str, pd.DataFrame],
    long_form: pd.DataFrame,
    summary_form: pd.DataFrame,
    loco_df: pd.DataFrame,
    loco_baseline: float,
    sector_agg: pd.DataFrame,
    per_ticker_df: pd.DataFrame,
    fold_sens: pd.DataFrame,
    perm_df: pd.DataFrame,
    perm_summary: pd.DataFrame,
) -> None:
    lines: list[str] = []
    lines.append("# FinScreen Phase D -- signal diagnosis report")
    lines.append("")
    _feat_mtime = (
        _dt.datetime.fromtimestamp(F.FEATURES_OUTPUT.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        if Path(F.FEATURES_OUTPUT).exists()
        else "unknown"
    )
    lines.append(
        f"*Generated by `diagnose.py` on {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')} from "
        f"`{F.FEATURES_OUTPUT}` ({len(df) + n_target_dropped} rows, last written {_feat_mtime}) and "
        f"`data/backtest_report.md`'s own fold/dedup discipline, reused via `backtest.py` imports "
        f"(not reimplemented -- see `test_diagnose.py`). Re-running `diagnose.py` overwrites this "
        f"file.*"
    )
    lines.append("")
    lines.append(
        "**Scope (owner ruling, `HANDOFF.md` §3, 2026-08-18, verbatim \"GO, diagnosis-scoped\"):** "
        "this report diagnoses WHICH categories/companies drive the backtest's mixed, sign-unstable "
        "text-vs-numeric signal (RAW cross-fold mean IC delta +0.0177 vs. DEDUPLICATED -0.0097, "
        "`data/backtest_report.md`) -- it does not re-adjudicate the go/no-go, does not propose a "
        "final model, and produces no recommendation of any kind. This is a research diagnostic, "
        "not investment advice, not a trading signal, and nothing here estimates an expected return "
        "(non-goals, `HANDOFF.md` §1, unconditional). Every number below states how it was computed "
        "next to it. **This report has not yet been red-teamed or shown to the owner** -- treat "
        "every number here as unverified until that happens (project-standing rule: flag every "
        "backtest/diagnostic result before it is treated as real)."
    )
    lines.append("")
    lines.append(
        f"**Sample size, carried over from `data/backtest_report.md` unchanged:** {len(df)} usable "
        f"filing-level observations ({n_target_dropped} dropped for an incomplete target window), "
        "roughly HALF that many independent company-quarter bets (8-K + 10-Q/10-K near-duplicate "
        "pairs). Every N below inherits this caveat; it is not re-derived per table."
    )
    lines.append("")

    # ---- Analysis 1: feature-family ablations -----------------------------
    lines.append("## 1. Feature-family ablations")
    lines.append("")
    lines.append(
        "Same 6 walk-forward folds as `data/backtest_report.md` (`B.build_walk_forward_folds`, "
        "`B.BURN_IN_END`), same `B.fit_predict`, same `B.XGB_PARAMS`, same company-quarter dedup "
        "mask (`B.company_quarter_dedup_keep_mask`). `spearman_ic_dedup` is the primary column; "
        "`spearman_ic` (raw) is reported alongside for the same non-independence reason "
        "`backtest.py`'s module docstring gives (roughly half of each fold's rows are near-duplicate "
        "8-K/10-Q pairs)."
    )
    lines.append("")
    lines.append("### 1a. Full sample (581 observations, 6 folds)")
    lines.append("")
    lines.extend(
        _fmt_table(
            long_full,
            ["family", "test_quarter", "n_test", "n_test_dedup", "spearman_ic", "spearman_ic_dedup", "delta_dedup_vs_numeric"],
        )
    )
    lines.append("")
    lines.append("Cross-fold summary per family (delta = family's dedup IC minus numeric-only's dedup IC, same fold):")
    lines.append("")
    lines.extend(
        _fmt_table(
            summary_full,
            [
                "family", "n_folds", "mean_delta_dedup_vs_numeric", "std_delta_dedup_vs_numeric",
                "positive_folds_dedup", "n_folds_dedup_valid", "mean_delta_raw_vs_numeric", "positive_folds_raw",
            ],
        )
    )
    lines.append("")

    lines.append(
        "### 1b. Form-controlled subset (10-Q/10-K only, "
        f"{len(df_form)} observations, {len(results_form['numeric_only'])} folds) -- "
        "**the honest read for `numeric_plus_section_mix` and any red-flag family relying on "
        "`redflag_any_rate_press`**, since `share_chunks_*`/`redflag_any_rate_press` are near-perfect "
        "SEC-form proxies (`backtest.py` MAJOR #4 finding: 8-Ks structurally cannot carry "
        "RISK_FACTORS/MDA chunks). No company-quarter dedup pass needed on this subset -- verified "
        "zero near-duplicate pairs once 8-Ks are excluded (`backtest.py` docstring), so "
        "`spearman_ic_dedup` here equals `spearman_ic` by construction."
    )
    lines.append("")
    lines.extend(
        _fmt_table(
            long_form,
            ["family", "test_quarter", "n_test", "n_test_dedup", "spearman_ic", "spearman_ic_dedup", "delta_dedup_vs_numeric"],
        )
    )
    lines.append("")
    lines.append("Cross-fold summary per family, form-controlled:")
    lines.append("")
    lines.extend(
        _fmt_table(
            summary_form,
            [
                "family", "n_folds", "mean_delta_dedup_vs_numeric", "std_delta_dedup_vs_numeric",
                "positive_folds_dedup", "n_folds_dedup_valid", "mean_delta_raw_vs_numeric", "positive_folds_raw",
            ],
        )
    )
    lines.append("")
    lines.append(f"**{F.RED_FLAG_CAVEAT}**")
    lines.append("")

    # ---- Analysis 2: leave-one-company-out + per-ticker -------------------
    lines.append("## 2. Per-company / per-sector decomposition")
    lines.append("")
    lines.append(
        f"**Leave-one-company-out:** the FULL (text+numeric) model refit per fold with each of the "
        f"25 tickers excluded from BOTH train and test (25 x 6 = 150 refits, `B.XGB_PARAMS` fixed "
        f"throughout, folds rebuilt from scratch via `B.build_walk_forward_folds` on the "
        f"24-ticker frame each time -- byte-identical fold LOGIC, smaller input). Baseline (all 25 "
        f"tickers) cross-fold mean dedup IC = **{loco_baseline:.4f}**. `delta_vs_baseline_25ticker` "
        "= that ticker's leave-one-out cross-fold mean dedup IC minus the baseline. "
        "**Interpretation limits (read before the tables):** (a) the delta CONFLATES two effects the "
        "analysis cannot separate -- losing the ticker's rows from TRAINING, and losing its ~1-2 rows "
        "from each ~40-53-row test-fold Spearman computation itself; removing rows from a small-fold "
        "rank correlation can shift the IC on its own, independent of any model reliance. (b) the "
        "frozen `target_excess_return` benchmark is self-referential: each company's excess return is "
        "measured against a 25-name universe average that still INCLUDES the excluded ticker's "
        "return (targets are frozen in `features.parquet`, deliberately not recomputed) -- so "
        "leave-one-out removes the ticker's filings, not its footprint in everyone else's benchmark. "
        "These deltas are descriptive of this one 25-company/6-fold run, not measures of reliable "
        "per-company signal."
    )
    lines.append("")
    lines.append("Top 5 (cross-fold dedup IC is higher in this run when this ticker is excluded):")
    lines.append("")
    lines.extend(_fmt_table(loco_df.head(5), ["ticker", "n_folds", "loco_mean_ic_dedup", "delta_vs_baseline_25ticker"]))
    lines.append("")
    lines.append("Bottom 5 (cross-fold dedup IC is lower in this run when this ticker is excluded -- subject to the interpretation limits above, NOT thereby shown to be a reliable signal driver):")
    lines.append("")
    lines.extend(_fmt_table(loco_df.tail(5).iloc[::-1], ["ticker", "n_folds", "loco_mean_ic_dedup", "delta_vs_baseline_25ticker"]))
    lines.append("")
    lines.append("Full 25-ticker table:")
    lines.append("")
    lines.extend(_fmt_table(loco_df, ["ticker", "n_folds", "loco_mean_ic_dedup", "delta_vs_baseline_25ticker"]))
    lines.append("")
    lines.append("Aggregated to `data/universe.csv` sectors (mean/std of the per-ticker delta within each sector):")
    lines.append("")
    lines.extend(_fmt_table(sector_agg, ["sector", "mean_delta_vs_baseline", "std_delta_vs_baseline", "n_tickers"]))
    lines.append("")
    lines.append(
        "**Read with caution:** 5 sectors x 5 tickers each is too few to distinguish a real "
        "sector-level effect from noise in the per-ticker deltas above; this aggregation describes "
        "where the removed-ticker effect CONCENTRATES in this specific 25-company/6-fold run, not a "
        "validated sector generalization."
    )
    lines.append("")

    lines.append(
        "**Per-ticker predicted-vs-realized Spearman (INDICATIVE ONLY):** out-of-fold predictions "
        "from the standard all-25-ticker FULL model (identical to `data/backtest_report.md`'s "
        "text_and_numeric fold fits), grouped by ticker across that ticker's own test-fold rows only "
        "(n = however many of that ticker's filings fell in a 2025Q1-2026Q2 test quarter, roughly "
        "half its total observations -- n~12-24 typically). **Three reasons this table cannot "
        "support a per-ticker claim:** (1) n this small carries no per-ticker significance; "
        "(2) each ticker's correlation POOLS predicted scores from up to 6 independently fitted "
        "expanding-window models (one per test fold) into a single ranking, silently assuming "
        "score-scale comparability across differently trained models -- a property `backtest.py` "
        "never relies on (its ICs are always within one fold's own model) and that is not verified "
        "here; (3) with 25 simultaneous nominal tests, ~1-2 would cross p<0.05 by chance alone, so "
        "the handful that do is consistent with multiple-comparisons noise. Descriptive cross-check "
        "against the leave-one-out table above, nothing more."
    )
    lines.append("")
    lines.extend(_fmt_table(per_ticker_df, ["ticker", "n", "spearman_ic", "spearman_p"]))
    lines.append("")

    # ---- Analysis 3: fold sensitivity --------------------------------------
    lines.append("## 3. Fold sensitivity (drop-one-fold cross-fold means)")
    lines.append("")
    lines.append(
        "`dropped_fold_delta` = that fold's own text-minus-numeric dedup IC delta (identical to "
        "`data/backtest_report.md`'s `IC_dedup_delta_text_minus_numeric` column -- reused, not "
        "recomputed independently, and matches it exactly as a cross-check). "
        "`loo_mean_ic_dedup_delta` = the cross-fold mean of the OTHER 5 folds' deltas, i.e. what the "
        "text-vs-numeric verdict would look like if that one fold's quarter had not been observed. "
        "The last row is the reference: the full 6-fold mean, matching `data/backtest_report.md`'s "
        "DEDUPLICATED delta of -0.0097."
    )
    lines.append("")
    lines.extend(
        _fmt_table(fold_sens, ["dropped_fold", "dropped_fold_delta", "loo_mean_ic_dedup_delta", "loo_n_folds", "sign_flip_vs_full_6fold_mean"])
    )
    lines.append("")
    n_flips = int(fold_sens["sign_flip_vs_full_6fold_mean"].sum())
    lines.append(
        f"**{n_flips}/6 single-fold removals flip the sign of the cross-fold mean dedup delta** "
        "relative to the full-6-fold mean (see the `sign_flip_vs_full_6fold_mean` column) -- read "
        "this as the honest measure of how much one quarter can move the overall verdict at this "
        "fold count, not as evidence for or against any one quarter being an outlier to exclude."
    )
    lines.append("")

    # ---- Analysis 4: red-flag permutation importance -----------------------
    lines.append("## 4. Red-flag category contribution (permutation importance, TEST folds only, form-controlled)")
    lines.append("")
    lines.append(
        f"Per fold, the FULL model is fit ONCE on that fold's training data (form-controlled subset, "
        f"same as analysis 1b) and never refit. For each of the 13 `redflag_*` columns, that column's "
        f"values are shuffled ACROSS THE TEST FOLD ROWS ONLY, on a fresh copy of the test-fold feature "
        f"matrix ({PERMUTATION_REPEATS} repeats per column per fold, local `RandomState`, mean IC drop "
        "reported); the already-fitted model then re-predicts on the permuted copy -- the training "
        "data and the fitted model are never touched. `mean_ic_drop_when_permuted` = baseline IC minus "
        "permuted IC, averaged over repeats; a larger positive number means that column's original "
        "(unpermuted) values mattered more to that fold's ranking."
    )
    lines.append("")
    lines.append(f"**{F.RED_FLAG_CAVEAT}**")
    lines.append("")
    lines.append("Cross-fold summary (sorted by mean IC drop, descending):")
    lines.append("")
    lines.extend(
        _fmt_table(perm_summary, ["redflag_column", "mean_ic_drop_across_folds", "std_ic_drop_across_folds", "n_folds"])
    )
    lines.append("")
    lines.append("Per-fold detail:")
    lines.append("")
    lines.extend(_fmt_table(perm_df, ["test_quarter", "n_test", "redflag_column", "baseline_ic", "mean_ic_drop_when_permuted"]))
    lines.append("")

    # ---- Analysis 5: what this can and cannot conclude ---------------------
    lines.append("## 5. What this diagnosis can and cannot conclude")
    lines.append("")
    lines.append(
        "**Signal concentration (with uncertainty, not point claims):** the family-ablation and "
        "leave-one-company-out tables above describe WHERE, in this specific 581-observation/25-"
        "ticker/6-fold run, the text signal's IC delta is largest or smallest -- they are descriptive "
        "decompositions of one already-noisy result, not independent statistical tests. A family or "
        "ticker sitting at the top or bottom of a table here is not thereby shown to be a reliable "
        "driver of anything outside this exact run; std columns and the raw-vs-dedup and full-vs-"
        "form-controlled comparisons throughout are the honest gauge of how much that ranking could "
        "shuffle under a slightly different fold, dedup, or subset choice."
    )
    lines.append("")
    lines.append("**Explicit list of what n=25 tickers / 6 folds cannot support:**")
    lines.append("")
    lines.append(
        "- A per-ticker or per-family significance test at conventional confidence levels -- 6 folds "
        "and ~9-53 observations per fold (roughly half that many independent company-quarter bets) "
        "is far below the sample size non-parametric rank tests need for a trustworthy p-value, and "
        "`backtest.py`'s own `spearman_p` non-independence caveat applies to every IC in this report "
        "just as it does in `data/backtest_report.md`."
    )
    lines.append(
        "- A claim that any one company, sector, or feature family GENERALIZES beyond this specific "
        "25-company mega-cap universe and this specific ~3.5-year window -- there is no held-out "
        "universe or time period beyond what `data/backtest_report.md` already walks forward through."
    )
    lines.append(
        "- A causal claim of any kind (e.g. \"this ticker's text drives its own predictability\") -- "
        "every number here is a correlational screening diagnostic, per the project's non-goals."
    )
    lines.append(
        "- Distinguishing a real, persistent effect from overfitting-to-six-folds with confidence -- "
        "the fold-sensitivity section above (analysis 3) is the closest this diagnosis gets to that "
        "question, and it answers \"how much does one fold move the mean\", not \"is the mean real\"."
    )
    lines.append(
        "- Any claim about red-flag-derived features beyond what analysis 4 measures on the "
        "form-controlled subset with the exact-set-match label-quality caveat attached -- red-flag "
        "features additionally inherit the labeling-quality uncertainty documented in "
        "`RED_FLAGS_LIMITATION.md`, which is a SEPARATE source of noise from the small-sample "
        "backtest noise this whole report otherwise measures."
    )
    lines.append("")
    lines.append(
        "**No recommendation follows from this report.** It is a diagnosis of an already-neutral, "
        "already-mixed backtest result, produced for the owner's own review; it does not change the "
        "GO/NO-GO status, does not select a \"final\" feature set, and is not a signal to act on "
        "(non-goals, `HANDOFF.md` §1, unconditional)."
    )
    lines.append("")

    DIAGNOSIS_REPORT_OUTPUT.write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("Loading data/features.parquet via backtest.load_modeling_frame()...")
    df, n_dropped = B.load_modeling_frame()
    print(f"{len(df)} usable observations ({n_dropped} dropped for incomplete target window)")

    folds = B.build_walk_forward_folds(df, B.BURN_IN_END)
    B.assert_no_fold_leakage(df, folds)
    print(f"{len(folds)} walk-forward folds (byte-identical construction to backtest.py)")

    families_order = list(FEATURE_FAMILIES.keys())

    print("\n--- Analysis 1a: feature-family ablations, full sample ---")
    keep_mask = B.company_quarter_dedup_keep_mask(df)
    results_full = run_family_ablation(df, folds, keep_mask=keep_mask, families=FEATURE_FAMILIES)
    long_full = family_delta_long(results_full, families_order)
    summary_full = family_delta_summary(long_full, families_order)
    print(summary_full.to_string(index=False))

    print("\n--- Analysis 1b: feature-family ablations, form-controlled subset ---")
    df_form, folds_form = build_form_controlled_frame(df)
    results_form = run_family_ablation(df_form, folds_form, families=FEATURE_FAMILIES)
    long_form = family_delta_long(results_form, families_order)
    summary_form = family_delta_summary(long_form, families_order)
    print(summary_form.to_string(index=False))

    print("\n--- Analysis 2: leave-one-company-out ---")
    universe_df = pd.read_csv(UNIVERSE_PATH)
    tickers = sorted(df["ticker"].unique())
    assert set(tickers) == set(universe_df["ticker"]), "features.parquet tickers != universe.csv tickers"
    loco_df, loco_baseline = run_leave_one_ticker_out(df, tickers)
    print(f"baseline cross-fold mean dedup IC (all 25 tickers): {loco_baseline:.4f}")
    print(loco_df.to_string(index=False))
    sector_agg = aggregate_loco_to_sector(loco_df, universe_df)
    print(sector_agg.to_string(index=False))

    per_ticker_df = per_ticker_predicted_vs_realized(df, folds)
    print("\nper-ticker predicted-vs-realized (indicative only):")
    print(per_ticker_df.to_string(index=False))

    print("\n--- Analysis 3: fold sensitivity ---")
    full_delta_df = long_full[long_full["family"] == "full"].reset_index(drop=True)
    fold_sens = fold_sensitivity(full_delta_df)
    print(fold_sens.to_string(index=False))

    print("\n--- Analysis 4: red-flag permutation importance (form-controlled) ---")
    perm_df = run_redflag_permutation_importance(df_form, folds_form)
    perm_summary = redflag_permutation_summary(perm_df)
    print(perm_summary.to_string(index=False))

    write_diagnosis_report(
        df, n_dropped, families_order, results_full, long_full, summary_full,
        df_form, results_form, long_form, summary_form,
        loco_df, loco_baseline, sector_agg, per_ticker_df,
        fold_sens, perm_df, perm_summary,
    )
    print(f"\nWrote {DIAGNOSIS_REPORT_OUTPUT}")


if __name__ == "__main__":
    main()
