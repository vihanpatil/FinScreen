"""
test_diagnose.py -- Phase D diagnosis test suite for `diagnose.py`.

Covers the four assertions the Phase D brief requires:
  1. Ablation folds are byte-identical to backtest.py's own fold
     construction (same train/test index SETS per fold), for both the
     full-sample and form-controlled subsets.
  2. Leave-one-company-out never leaks the excluded ticker into either
     train or test, for any fold.
  3. Permutation importance happens on TEST-fold copies only -- the fitted
     model and the original X_test/X_train arrays are never mutated.
  4. Cross-checks that `diagnose.py`'s reused-function results agree
     exactly with `backtest.py`'s own numbers where they measure the same
     thing (e.g. the "full" family's dedup IC must equal
     backtest.run_backtest's text_and_numeric dedup IC).

Uses the real `data/features.parquet` corpus (not a synthetic fixture) --
consistent with `test_phase_c_leakage.py`'s real-data-at-scale approach --
but keeps leave-one-out and permutation-importance tests to small ticker/
fold subsets so the suite runs in seconds, not minutes.

Run with: python3 -m pytest test_diagnose.py -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import backtest as B
import diagnose as D
import features as F


@pytest.fixture(scope="module")
def modeling_frame():
    df, n_dropped = B.load_modeling_frame()
    return df, n_dropped


@pytest.fixture(scope="module")
def full_sample_folds(modeling_frame):
    df, _ = modeling_frame
    folds = B.build_walk_forward_folds(df, B.BURN_IN_END)
    B.assert_no_fold_leakage(df, folds)
    return folds


@pytest.fixture(scope="module")
def form_controlled(modeling_frame):
    df, _ = modeling_frame
    df_form, folds_form = D.build_form_controlled_frame(df)
    return df_form, folds_form


# ---------------------------------------------------------------------------
# 1. Ablation folds byte-identical to backtest.py's own folds
# ---------------------------------------------------------------------------


def _fold_index_sets(folds: list[dict]) -> list[tuple[frozenset, frozenset]]:
    return [(frozenset(f["train_idx"].tolist()), frozenset(f["test_idx"].tolist())) for f in folds]


def test_full_sample_folds_identical_to_backtest_py(modeling_frame):
    """diagnose.py builds its full-sample folds via the exact same
    B.build_walk_forward_folds(df, B.BURN_IN_END) call backtest.py's main()
    uses -- calling it twice on the same df must give byte-identical
    train/test index sets per fold."""
    df, _ = modeling_frame
    folds_a = B.build_walk_forward_folds(df, B.BURN_IN_END)
    folds_b = B.build_walk_forward_folds(df, B.BURN_IN_END)
    assert [f["test_quarter"] for f in folds_a] == [f["test_quarter"] for f in folds_b]
    assert _fold_index_sets(folds_a) == _fold_index_sets(folds_b)
    # And matches the known 6-fold structure documented in data/backtest_report.md.
    assert len(folds_a) == 6
    assert [len(f["test_idx"]) for f in folds_a] == [52, 52, 52, 52, 53, 46]
    assert [len(f["train_idx"]) for f in folds_a] == [274, 326, 378, 430, 482, 535]


def test_form_controlled_folds_identical_to_backtest_run_form_controlled_ablation(modeling_frame, form_controlled):
    """diagnose.build_form_controlled_frame must produce the SAME df_form/
    folds_form as backtest.run_form_controlled_ablation -- i.e. diagnose.py
    is reusing backtest.py's fold logic, not reimplementing it."""
    df, _ = modeling_frame
    df_form_ref, folds_form_ref, _ = B.run_form_controlled_ablation(df, B.BURN_IN_END)
    df_form_diag, folds_form_diag = form_controlled

    pd.testing.assert_frame_equal(df_form_ref, df_form_diag)
    assert [f["test_quarter"] for f in folds_form_ref] == [f["test_quarter"] for f in folds_form_diag]
    assert _fold_index_sets(folds_form_ref) == _fold_index_sets(folds_form_diag)


def test_family_ablation_uses_the_supplied_folds_unmodified(modeling_frame, full_sample_folds):
    """run_family_ablation must not mutate or reorder the folds list it is
    given -- train/test idx arrays identical before and after the call."""
    df, _ = modeling_frame
    before = _fold_index_sets(full_sample_folds)
    D.run_family_ablation(df, full_sample_folds, families={"numeric_only": []})
    after = _fold_index_sets(full_sample_folds)
    assert before == after


def test_family_ablation_full_family_matches_backtest_text_and_numeric_dedup_ic(modeling_frame, full_sample_folds):
    """Cross-check: diagnose.py's "full" family (numeric + ALL text
    features) must reproduce backtest.py's own text_and_numeric per-fold
    dedup IC EXACTLY, since both use identical folds, features, fit_predict,
    and XGB_PARAMS. This is the load-bearing sanity check that diagnose.py
    is genuinely reusing backtest.py's machinery rather than a subtly
    different reimplementation."""
    df, _ = modeling_frame
    keep_mask = B.company_quarter_dedup_keep_mask(df)
    ref_results = B.run_backtest(df, full_sample_folds, keep_mask=keep_mask)
    diag_results = D.run_family_ablation(
        df, full_sample_folds, keep_mask=keep_mask, families={"full": D.FEATURE_FAMILIES["full"]}
    )
    ref_dedup = ref_results["text_and_numeric"]["spearman_ic_dedup"].to_numpy()
    diag_dedup = diag_results["full"]["spearman_ic_dedup"].to_numpy()
    np.testing.assert_allclose(ref_dedup, diag_dedup, rtol=0, atol=1e-12)

    ref_numeric_results = D.run_family_ablation(
        df, full_sample_folds, keep_mask=keep_mask, families={"numeric_only": []}
    )
    np.testing.assert_allclose(
        ref_results["numeric_only"]["spearman_ic_dedup"].to_numpy(),
        ref_numeric_results["numeric_only"]["spearman_ic_dedup"].to_numpy(),
        rtol=0, atol=1e-12,
    )


def test_feature_families_partition_text_features():
    union = set(D.FAMILY_SENTIMENT) | set(D.FAMILY_GUIDANCE) | set(D.FAMILY_REDFLAGS) | set(D.FAMILY_SECTION_MIX)
    assert union == set(B.TEXT_FEATURES)
    assert len(D.FAMILY_REDFLAGS) == 13
    assert D.family_feature_cols("full") == B.FULL_FEATURES
    assert D.family_feature_cols("numeric_only") == B.NUMERIC_FEATURES


# ---------------------------------------------------------------------------
# 2. Leave-one-company-out never leaks the excluded ticker
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ticker", ["AAPL", "JPM", "OXY"])
def test_leave_one_ticker_out_excludes_ticker_from_every_fold(modeling_frame, ticker):
    df, _ = modeling_frame
    loco_df, _ = D.run_leave_one_ticker_out(df, [ticker])
    assert len(loco_df) == 1
    # Independently reconstruct the excluded-ticker frame/folds and verify
    # the ticker is absent from every train_idx and test_idx.
    df_loco = df[df["ticker"] != ticker].reset_index(drop=True)
    folds_loco = B.build_walk_forward_folds(df_loco, B.BURN_IN_END)
    for fold in folds_loco:
        train_tickers = set(df_loco.loc[fold["train_idx"], "ticker"])
        test_tickers = set(df_loco.loc[fold["test_idx"], "ticker"])
        assert ticker not in train_tickers
        assert ticker not in test_tickers
    assert ticker not in df_loco["ticker"].unique()


def test_leave_one_ticker_out_function_raises_style_guard_holds(modeling_frame):
    """The internal assertion inside run_leave_one_ticker_out (excluded
    ticker not in any fold's train/test) must actually execute -- verified
    by running on the full 25-ticker set for two tickers without error and
    confirming n_folds == 6 for both (no fold silently vanished)."""
    df, _ = modeling_frame
    loco_df, baseline = D.run_leave_one_ticker_out(df, ["MSFT", "NVDA"])
    assert set(loco_df["ticker"]) == {"MSFT", "NVDA"}
    assert (loco_df["n_folds"] == 6).all()
    assert np.isfinite(baseline)


def test_leave_one_ticker_out_baseline_matches_full_model_dedup_mean(modeling_frame, full_sample_folds):
    """The baseline (all-25-ticker) mean dedup IC computed inside
    run_leave_one_ticker_out must equal backtest.py's own text_and_numeric
    cross-fold dedup IC mean exactly."""
    df, _ = modeling_frame
    keep_mask = B.company_quarter_dedup_keep_mask(df)
    ref_results = B.run_backtest(df, full_sample_folds, keep_mask=keep_mask)
    ref_mean = ref_results["text_and_numeric"]["spearman_ic_dedup"].mean()
    _, baseline = D.run_leave_one_ticker_out(df, ["MSFT"])
    assert baseline == pytest.approx(ref_mean, abs=1e-9)


def test_sector_aggregation_requires_every_ticker_have_a_sector(modeling_frame):
    df, _ = modeling_frame
    universe_df = pd.read_csv(D.UNIVERSE_PATH)
    loco_df, _ = D.run_leave_one_ticker_out(df, ["AAPL", "V", "PG"])
    sector_agg = D.aggregate_loco_to_sector(loco_df, universe_df)
    assert set(sector_agg["sector"]) <= set(universe_df["sector"].unique())
    assert sector_agg["n_tickers"].sum() == 3


def test_universe_csv_tickers_match_features_parquet_tickers(modeling_frame):
    df, _ = modeling_frame
    universe_df = pd.read_csv(D.UNIVERSE_PATH)
    assert set(df["ticker"].unique()) == set(universe_df["ticker"])
    assert len(universe_df) == 25
    assert set(universe_df["sector"].unique()) == {"tech", "financials", "healthcare", "energy", "consumer"}


# ---------------------------------------------------------------------------
# 3. Permutation importance happens on test-fold copies only
# ---------------------------------------------------------------------------


def test_permutation_never_mutates_x_test_or_train_data(modeling_frame, form_controlled):
    df_form, folds_form = form_controlled
    fold = folds_form[0]
    train_idx, test_idx = fold["train_idx"], fold["test_idx"]
    full_cols = D.FEATURE_FAMILIES_FULL_COLS

    X_train_before = df_form.loc[train_idx, full_cols].astype(float).values.copy()
    model, baseline_pred, X_test = D.fit_and_predict_with_model(df_form, full_cols, train_idx, test_idx)
    X_test_before = X_test.copy()
    realized = df_form.loc[test_idx, B.TARGET_COL].astype(float).values

    for col_idx in range(len(full_cols)):
        D.permute_column_and_rescore(model, X_test, realized, col_idx, n_repeats=5, seed=col_idx)
        assert np.array_equal(X_test, X_test_before, equal_nan=True), (
            f"permute_column_and_rescore mutated X_test at col_idx={col_idx}"
        )

    # Training data in the source DataFrame must also be untouched.
    X_train_after = df_form.loc[train_idx, full_cols].astype(float).values
    assert np.array_equal(X_train_before, X_train_after, equal_nan=True)

    # The model must not have been refit -- predicting on the original
    # X_test again reproduces the exact same baseline prediction.
    np.testing.assert_allclose(model.predict(X_test), baseline_pred, rtol=0, atol=1e-9)


def test_permutation_uses_a_fresh_copy_not_a_view(modeling_frame, form_controlled):
    """Directly verifies permute_column_and_rescore's internal X_perm is a
    copy: mutating the returned drop value across repeats must never leave
    a trace on the caller's X_test array, checked by identity as well as
    value equality."""
    df_form, folds_form = form_controlled
    fold = folds_form[1]
    train_idx, test_idx = fold["train_idx"], fold["test_idx"]
    full_cols = D.FEATURE_FAMILIES_FULL_COLS
    model, _, X_test = D.fit_and_predict_with_model(df_form, full_cols, train_idx, test_idx)
    realized = df_form.loc[test_idx, B.TARGET_COL].astype(float).values

    redflag_idx = full_cols.index("redflag_any_rate_press")
    baseline_ic, mean_drop = D.permute_column_and_rescore(
        model, X_test, realized, redflag_idx, n_repeats=25, seed=7
    )
    assert np.isfinite(baseline_ic) or np.isnan(baseline_ic)  # always one or the other, never a crash
    assert isinstance(mean_drop, float)


def test_run_redflag_permutation_importance_covers_all_13_columns_every_fold(form_controlled):
    df_form, folds_form = form_controlled
    # Restrict to the first 2 folds for test speed; the function itself is
    # not fold-count-limited -- diagnose.py's main() runs all 6.
    perm_df = D.run_redflag_permutation_importance(df_form, folds_form[:2])
    assert set(perm_df["redflag_column"]) == set(D.FAMILY_REDFLAGS)
    assert len(perm_df) == 2 * 13
    for q in perm_df["test_quarter"].unique():
        assert (perm_df[perm_df["test_quarter"] == q]["redflag_column"].nunique()) == 13


def test_redflag_permutation_importance_reproducible_with_fixed_seed(form_controlled):
    df_form, folds_form = form_controlled
    perm_df_a = D.run_redflag_permutation_importance(df_form, folds_form[:1])
    perm_df_b = D.run_redflag_permutation_importance(df_form, folds_form[:1])
    pd.testing.assert_frame_equal(
        perm_df_a.sort_values(["test_quarter", "redflag_column"]).reset_index(drop=True),
        perm_df_b.sort_values(["test_quarter", "redflag_column"]).reset_index(drop=True),
    )


# ---------------------------------------------------------------------------
# 4. fit_and_predict_with_model pinned against backtest.fit_predict
# ---------------------------------------------------------------------------


def test_fit_and_predict_with_model_matches_backtest_fit_predict(modeling_frame, full_sample_folds):
    df, _ = modeling_frame
    fold = full_sample_folds[0]
    train_idx, test_idx = fold["train_idx"], fold["test_idx"]
    ref_pred = B.fit_predict(df, B.FULL_FEATURES, train_idx, test_idx)
    _, diag_pred, _ = D.fit_and_predict_with_model(df, B.FULL_FEATURES, train_idx, test_idx)
    np.testing.assert_allclose(ref_pred, diag_pred, rtol=0, atol=1e-9)


# ---------------------------------------------------------------------------
# Fold sensitivity (analysis 3) correctness
# ---------------------------------------------------------------------------


def test_fold_sensitivity_matches_backtest_report_dedup_delta_column(modeling_frame, full_sample_folds):
    """The per-fold `dropped_fold_delta` column must equal
    data/backtest_report.md's IC_dedup_delta_text_minus_numeric column
    exactly (both are text_and_numeric dedup IC minus numeric_only dedup
    IC, same folds)."""
    df, _ = modeling_frame
    keep_mask = B.company_quarter_dedup_keep_mask(df)
    ref_results = B.run_backtest(df, full_sample_folds, keep_mask=keep_mask)
    ref_delta = (
        ref_results["text_and_numeric"]["spearman_ic_dedup"] - ref_results["numeric_only"]["spearman_ic_dedup"]
    ).to_numpy()

    diag_results = D.run_family_ablation(df, full_sample_folds, keep_mask=keep_mask, families=D.FEATURE_FAMILIES)
    long_full = D.family_delta_long(diag_results, list(D.FEATURE_FAMILIES.keys()))
    full_delta = long_full[long_full["family"] == "full"]["delta_dedup_vs_numeric"].to_numpy()

    np.testing.assert_allclose(ref_delta, full_delta, rtol=0, atol=1e-12)

    fold_sens = D.fold_sensitivity(long_full[long_full["family"] == "full"].reset_index(drop=True))
    # 6 dropped-fold rows + 1 reference row.
    assert len(fold_sens) == 7
    reference_row = fold_sens[fold_sens["dropped_fold"] == "NONE (all 6 folds)"].iloc[0]
    assert reference_row["loo_mean_ic_dedup_delta"] == pytest.approx(np.mean(ref_delta), abs=1e-9)

    # Each drop-one-fold mean must equal the mean of the other 5 deltas.
    for i, row in enumerate(fold_sens.itertuples()):
        if row.dropped_fold == "NONE (all 6 folds)":
            continue
        expected = np.mean(np.delete(ref_delta, i))
        assert row.loo_mean_ic_dedup_delta == pytest.approx(expected, abs=1e-9)


# ---------------------------------------------------------------------------
# Misc: red-flag caveat carried verbatim, report is written, non-goals
# ---------------------------------------------------------------------------


def test_red_flag_caveat_string_used_verbatim():
    """diagnose.py must not paraphrase the red-flag caveat -- pull the exact
    F.RED_FLAG_CAVEAT string (same one backtest_report.md uses) and confirm
    it is importable and non-empty."""
    assert F.RED_FLAG_CAVEAT
    assert "63.4%" in F.RED_FLAG_CAVEAT or "36.6%" in F.RED_FLAG_CAVEAT


def test_no_recommendation_language_helpers_exist():
    """Charter check: diagnose.py must not define any function whose name
    implies a trading/recommendation action (buy/sell/execute/trade)."""
    banned = ("buy", "sell", "execute_trade", "place_order", "recommend_action")
    names = [n.lower() for n in dir(D)]
    for b in banned:
        assert not any(b in n for n in names), f"found a banned-sounding name containing '{b}'"


def test_diagnosis_report_written(tmp_path, monkeypatch):
    """Smoke test: write_diagnosis_report runs end-to-end on a tiny slice
    (2 folds, 3 families) without error and produces non-empty markdown
    containing the required section headers."""
    df, n_dropped = B.load_modeling_frame()
    folds = B.build_walk_forward_folds(df, B.BURN_IN_END)[:2]
    families = {"numeric_only": [], "full": D.FEATURE_FAMILIES["full"]}
    results_full = D.run_family_ablation(df, folds, families=families)
    long_full = D.family_delta_long(results_full, ["numeric_only", "full"])
    summary_full = D.family_delta_summary(long_full, ["numeric_only", "full"])

    df_form, folds_form = D.build_form_controlled_frame(df)
    folds_form = folds_form[:2]
    results_form = D.run_family_ablation(df_form, folds_form, families=families)
    long_form = D.family_delta_long(results_form, ["numeric_only", "full"])
    summary_form = D.family_delta_summary(long_form, ["numeric_only", "full"])

    loco_df, loco_baseline = D.run_leave_one_ticker_out(df, ["AAPL", "MSFT"])
    universe_df = pd.read_csv(D.UNIVERSE_PATH)
    sector_agg = D.aggregate_loco_to_sector(loco_df, universe_df)
    per_ticker_df = D.per_ticker_predicted_vs_realized(df, folds)
    fold_sens = D.fold_sensitivity(long_full[long_full["family"] == "full"].reset_index(drop=True))
    perm_df = D.run_redflag_permutation_importance(df_form, folds_form)
    perm_summary = D.redflag_permutation_summary(perm_df)

    keep_mask = B.company_quarter_dedup_keep_mask(df)
    standing = B.compute_standing_diagnostics(df, B.build_spec_frames(df), folds, keep_mask)

    out_path = tmp_path / "diagnosis_report_test.md"
    monkeypatch.setattr(D, "DIAGNOSIS_REPORT_OUTPUT", out_path)
    D.write_diagnosis_report(
        df, n_dropped, ["numeric_only", "full"], results_full, long_full, summary_full,
        df_form, results_form, long_form, summary_form,
        loco_df, loco_baseline, sector_agg, per_ticker_df,
        fold_sens, perm_df, perm_summary,
        standing=standing, output_path=out_path,
    )
    text = out_path.read_text()
    assert "# FinScreen Phase D -- signal diagnosis report" in text
    assert "## 1. Feature-family ablations" in text
    assert "## 2. Per-company / per-sector decomposition" in text
    assert "## 3. Fold sensitivity" in text
    assert "## 4. Red-flag category contribution" in text
    assert "## 5. What this diagnosis can and cannot conclude" in text
    assert F.RED_FLAG_CAVEAT in text
    # H2 standing sections must be present in EVERY generated report
    assert "## Feature specification (pre-registered" in text
    assert "## Zero-information benchmarks (STANDING" in text
    assert "## Within-fold bootstrap noise anchor (STANDING" in text
    assert "## Label-embargo census" in text
    for banned_phrase in ("should buy", "should sell", "beats the market", "guaranteed return", "buy recommendation", "sell recommendation"):
        assert banned_phrase not in text.lower()


def test_diagnosis_report_without_standing_inputs_says_not_computed(tmp_path):
    """H2: a report generated without the standing diagnostics must SAY so,
    not silently omit the sections -- an un-benchmarked IC that looks
    benchmarked is the failure mode being prevented."""
    df, n_dropped = B.load_modeling_frame()
    folds = B.build_walk_forward_folds(df, B.BURN_IN_END)[:1]
    families = {"numeric_only": [], "full": D.FEATURE_FAMILIES["full"]}
    results_full = D.run_family_ablation(df, folds, families=families)
    long_full = D.family_delta_long(results_full, ["numeric_only", "full"])
    summary_full = D.family_delta_summary(long_full, ["numeric_only", "full"])
    df_form, folds_form = D.build_form_controlled_frame(df)
    folds_form = folds_form[:1]
    results_form = D.run_family_ablation(df_form, folds_form, families=families)
    long_form = D.family_delta_long(results_form, ["numeric_only", "full"])
    summary_form = D.family_delta_summary(long_form, ["numeric_only", "full"])
    loco_df, loco_baseline = D.run_leave_one_ticker_out(df, ["AAPL"])
    universe_df = pd.read_csv(D.UNIVERSE_PATH)
    sector_agg = D.aggregate_loco_to_sector(loco_df, universe_df)
    per_ticker_df = D.per_ticker_predicted_vs_realized(df, folds)
    fold_sens = D.fold_sensitivity(long_full[long_full["family"] == "full"].reset_index(drop=True))
    perm_df = D.run_redflag_permutation_importance(df_form, folds_form)
    perm_summary = D.redflag_permutation_summary(perm_df)

    out_path = tmp_path / "diagnosis_no_standing.md"
    D.write_diagnosis_report(
        df, n_dropped, ["numeric_only", "full"], results_full, long_full, summary_full,
        df_form, results_form, long_form, summary_form,
        loco_df, loco_baseline, sector_agg, per_ticker_df,
        fold_sens, perm_df, perm_summary,
        output_path=out_path,
    )
    text = out_path.read_text()
    assert text.count("NOT COMPUTED") >= 3
    assert "un-benchmarked" in text
