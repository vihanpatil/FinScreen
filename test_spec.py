"""
test_spec.py -- offline tests for H2 (F2.5 hardening): the pre-registered
PIT trailing cross-sectional rank transform, the two standing
zero-information benchmarks, the within-fold bootstrap noise anchor, the
label-embargo census, and the ddof=1 corrections in `backtest.py` /
`diagnose.py`.

Every test here is OFFLINE: no network, no Anthropic API, no writes to any
frozen artifact. The handful of tests that read `data/features.parquet`
open it read-only and skip when it is absent.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import spearmanr

import spec as S

REPO_ROOT = Path(__file__).resolve().parent
FEATURES_PATH = REPO_ROOT / "data" / "features.parquet"


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _frame(rows: list[tuple]) -> pd.DataFrame:
    """rows: (ticker, 'YYYY-MM-DD', x) -> a sorted modeling-style frame."""
    df = pd.DataFrame(rows, columns=["ticker", "filing_date", "x"])
    df["filing_date"] = pd.to_datetime(df["filing_date"])
    return df.sort_values("filing_date").reset_index(drop=True)


def _fold(train_idx, test_idx, quarter="2025Q1") -> dict:
    return {
        "test_quarter": quarter,
        "train_idx": np.asarray(train_idx),
        "test_idx": np.asarray(test_idx),
    }


# ---------------------------------------------------------------------------
# 1. PIT trailing cross-sectional percentile-rank transform
# ---------------------------------------------------------------------------


def test_pit_rank_percentile_is_below_plus_half_ties():
    """Four tickers, one date. Subject included in its own comparison set,
    so the percentile of the smallest value is (0 + 0.5*1)/4 = 0.125."""
    df = _frame(
        [("A", "2025-01-10", 1.0), ("B", "2025-01-10", 2.0), ("C", "2025-01-10", 3.0), ("D", "2025-01-10", 4.0)]
    )
    out = S.pit_trailing_rank_frame(df, ["x"])
    assert out["x"].tolist() == pytest.approx([0.125, 0.375, 0.625, 0.875])


def test_pit_rank_ties_share_the_midpoint():
    df = _frame([("A", "2025-01-10", 5.0), ("B", "2025-01-10", 5.0), ("C", "2025-01-10", 9.0)])
    out = S.pit_trailing_rank_frame(df, ["x"])
    # two ties below the max: each gets (0 + 0.5*2)/3
    assert out["x"].tolist() == pytest.approx([1 / 3, 1 / 3, (2 + 0.5) / 3])


def test_future_rows_cannot_change_a_past_percentile():
    """LEAKAGE PIN. Mutating a strictly later row's feature value must not
    move any earlier row's percentile."""
    base = _frame(
        [
            ("A", "2025-01-10", 1.0),
            ("B", "2025-01-10", 2.0),
            ("C", "2025-01-11", 3.0),
            ("D", "2025-02-01", 4.0),
        ]
    )
    mutated = base.copy()
    mutated.loc[mutated["filing_date"] == pd.Timestamp("2025-02-01"), "x"] = -999.0

    out_base = S.pit_trailing_rank_frame(base, ["x"])
    out_mut = S.pit_trailing_rank_frame(mutated, ["x"])
    earlier = out_base["filing_date"] < pd.Timestamp("2025-02-01")
    assert out_base.loc[earlier, "x"].tolist() == pytest.approx(out_mut.loc[earlier, "x"].tolist())
    # and the mutated row itself DID move, proving the test has teeth
    assert out_base["x"].iloc[-1] != pytest.approx(out_mut["x"].iloc[-1])


def test_pit_rank_same_day_rows_of_other_tickers_are_included():
    """A same-day filing by a DIFFERENT ticker has filing_date <= t and is a
    legitimate comparator under the corpus's day-granularity convention."""
    df = _frame([("A", "2025-01-10", 1.0), ("B", "2025-01-10", 2.0)])
    out = S.pit_trailing_rank_frame(df, ["x"], min_comparators=2)
    assert out["x"].notna().all()


def test_pit_rank_subject_represents_its_own_ticker_not_its_sibling():
    """An 8-K and a 10-Q from the same company on the same day must each be
    ranked on THEIR OWN value, not on the later sibling's."""
    df = _frame(
        [("A", "2025-01-10", 0.0), ("A", "2025-01-10", 100.0), ("B", "2025-01-10", 50.0)]
    )
    out = S.pit_trailing_rank_frame(df, ["x"], min_comparators=2)
    # subject A(0.0) sees {A:0.0 (itself), B:50.0} -> (0 + 0.5)/2 = 0.25
    assert out["x"].iloc[0] == pytest.approx(0.25)
    # subject A(100.0) sees {A:100.0 (itself), B:50.0} -> (1 + 0.5)/2 = 0.75
    assert out["x"].iloc[1] == pytest.approx(0.75)


def test_pit_rank_window_excludes_observations_older_than_the_window():
    df = _frame(
        [
            ("A", "2024-01-01", 1.0),  # 400+ days before the subject
            ("B", "2025-03-01", 2.0),
            ("C", "2025-03-02", 3.0),
        ]
    )
    out = S.pit_trailing_rank_frame(df, ["x"], window_days=180, min_comparators=2)
    # subject C sees only {B, C}: (1 + 0.5)/2 = 0.75. A is stale and excluded.
    assert out["x"].iloc[2] == pytest.approx(0.75)


def test_pit_rank_uses_only_the_last_observation_per_ticker():
    df = _frame(
        [
            ("A", "2025-01-01", -100.0),
            ("A", "2025-02-01", 10.0),
            ("B", "2025-02-02", 5.0),
        ]
    )
    out = S.pit_trailing_rank_frame(df, ["x"], min_comparators=2)
    # subject B sees {A: 10.0 (last), B: 5.0}: (0 + 0.5)/2 = 0.25.
    # If the stale -100.0 leaked in as a third comparator the answer is 1/6.
    assert out["x"].iloc[2] == pytest.approx(0.25)


def test_pit_rank_nan_in_nan_out_and_nan_comparators_excluded():
    df = _frame(
        [("A", "2025-01-10", np.nan), ("B", "2025-01-10", 2.0), ("C", "2025-01-10", 3.0)]
    )
    out = S.pit_trailing_rank_frame(df, ["x"], min_comparators=2)
    assert pd.isna(out["x"].iloc[0])
    # B and C rank against 2 non-null comparators, not 3
    assert out["x"].iloc[1] == pytest.approx(0.25)
    assert out["x"].iloc[2] == pytest.approx(0.75)


def test_pit_rank_too_few_comparators_is_nan_not_a_degenerate_half():
    df = _frame([("A", "2025-01-10", 1.0)])
    out = S.pit_trailing_rank_frame(df, ["x"], min_comparators=2)
    assert pd.isna(out["x"].iloc[0])


def test_include_same_day_false_excludes_the_subject_and_its_same_day_peers():
    """The one named sensitivity variant. With same-day rows excluded the
    subject ranks against its own PRIOR filing and prior peers only."""
    df = _frame(
        [
            ("A", "2025-01-01", 1.0),
            ("B", "2025-01-02", 2.0),
            ("C", "2025-03-01", 99.0),  # same-day peer as the subject
            ("A", "2025-03-01", 50.0),  # subject
        ]
    )
    default = S.pit_trailing_rank_frame(df, ["x"])
    variant = S.pit_trailing_rank_frame(df, ["x"], include_same_day=False)
    # default: subject sees {A:50 (itself), B:2, C:99} -> (1 + 0.5)/3 = 0.5
    assert default["x"].iloc[3] == pytest.approx(0.5)
    # variant: subject sees {A:1 (its own prior filing), B:2} -> (2 + 0)/2 = 1.0
    assert variant["x"].iloc[3] == pytest.approx(1.0)


def test_include_same_day_false_is_still_look_ahead_free():
    base = _frame(
        [("A", "2025-01-01", 1.0), ("B", "2025-01-02", 2.0), ("C", "2025-02-01", 3.0)]
    )
    mutated = base.copy()
    mutated.loc[2, "x"] = -999.0
    out_b = S.pit_trailing_rank_frame(base, ["x"], include_same_day=False)
    out_m = S.pit_trailing_rank_frame(mutated, ["x"], include_same_day=False)
    assert out_b["x"].iloc[:2].fillna(-1).tolist() == out_m["x"].iloc[:2].fillna(-1).tolist()


def test_first_row_with_no_prior_comparators_is_nan_not_a_crash():
    df = _frame([("A", "2025-01-01", 1.0), ("B", "2025-02-01", 2.0)])
    out = S.pit_trailing_rank_frame(df, ["x"], include_same_day=False)
    assert pd.isna(out["x"].iloc[0])


def test_pit_rank_requires_a_sorted_frame():
    df = pd.DataFrame(
        {
            "ticker": ["A", "B"],
            "filing_date": pd.to_datetime(["2025-02-01", "2025-01-01"]),
            "x": [1.0, 2.0],
        }
    )
    with pytest.raises(ValueError, match="sorted ascending"):
        S.pit_trailing_rank_frame(df, ["x"])


def test_pit_rank_returns_a_copy_and_preserves_other_columns():
    df = _frame([("A", "2025-01-10", 1.0), ("B", "2025-01-10", 2.0)])
    df["keepme"] = ["p", "q"]
    original = df["x"].tolist()
    out = S.pit_trailing_rank_frame(df, ["x"], min_comparators=2)
    assert df["x"].tolist() == original, "input frame was mutated"
    assert out["keepme"].tolist() == ["p", "q"]
    assert out is not df


def test_pit_rank_unknown_column_raises():
    df = _frame([("A", "2025-01-10", 1.0)])
    with pytest.raises(KeyError):
        S.pit_trailing_rank_frame(df, ["nope"])


def test_transform_frame_dispatch():
    df = _frame([("A", "2025-01-10", 1.0), ("B", "2025-01-10", 2.0)])
    raw = S.transform_frame(df, S.SECONDARY_SPEC, ["x"])
    assert raw["x"].tolist() == [1.0, 2.0]
    ranked = S.transform_frame(df, S.PRIMARY_SPEC, ["x"], min_comparators=2)
    assert ranked["x"].tolist() == pytest.approx([0.25, 0.75])
    with pytest.raises(ValueError):
        S.transform_frame(df, "some_other_idea", ["x"])


@pytest.mark.skipif(not FEATURES_PATH.exists(), reason="data/features.parquet not present")
def test_pit_rank_on_real_frame_is_bounded_and_preserves_missingness():
    df = pd.read_parquet(FEATURES_PATH)
    df["filing_date"] = pd.to_datetime(df["filing_date"])
    df = df.sort_values("filing_date").reset_index(drop=True)
    cols = ["log_total_assets", "net_margin", "redflag_any_rate_press"]
    out = S.pit_trailing_rank_frame(df, cols)
    for c in cols:
        vals = out[c].dropna()
        assert ((vals > 0) & (vals < 1)).all(), f"{c} percentile out of (0,1)"
        # a raw NaN can never become a number
        assert out.loc[df[c].isna(), c].isna().all()


# ---------------------------------------------------------------------------
# 2. Zero-information benchmarks
# ---------------------------------------------------------------------------


def _bench_frame() -> pd.DataFrame:
    df = pd.DataFrame(
        {
            "ticker": ["A", "B", "C", "A", "B", "C"],
            "filing_date": pd.to_datetime(
                ["2024-01-01", "2024-01-02", "2024-01-03", "2025-01-01", "2025-01-02", "2025-01-03"]
            ),
            "log_total_assets": [1.0, 2.0, 3.0, 1.1, 2.1, 3.1],
            "target_excess_return": [0.10, -0.20, 0.30, 0.05, -0.05, 0.15],
        }
    )
    return df


def test_ticker_training_mean_uses_only_training_rows():
    df = _bench_frame()
    fold = _fold(train_idx=[0, 1, 2], test_idx=[3, 4, 5])
    preds = S.zero_information_predictions(df, fold, "target_excess_return")
    # each test ticker gets its own TRAINING target, not its test target
    assert preds[S.ZERO_INFO_TICKER_MEAN] == pytest.approx([0.10, -0.20, 0.30])
    assert preds[S.ZERO_INFO_SIZE] == pytest.approx([1.1, 2.1, 3.1])


def test_ticker_training_mean_falls_back_to_overall_mean_for_unseen_ticker():
    df = _bench_frame()
    fold = _fold(train_idx=[0, 1], test_idx=[3, 4, 5])  # C never trained on
    preds = S.zero_information_predictions(df, fold, "target_excess_return")
    overall = np.mean([0.10, -0.20])
    assert preds[S.ZERO_INFO_TICKER_MEAN][2] == pytest.approx(overall)


def test_zero_information_benchmarks_report_both_rows_per_fold():
    df = _bench_frame()
    folds = [_fold([0, 1, 2], [3, 4, 5], "2025Q1")]
    bench = S.zero_information_benchmarks(df, folds, "target_excess_return")
    assert set(bench["benchmark"]) == set(S.ZERO_INFO_BENCHMARKS)
    assert len(bench) == 2
    assert bench["n_test"].tolist() == [3, 3]


def test_zero_information_benchmarks_honour_the_dedup_mask():
    df = _bench_frame()
    folds = [_fold([0, 1, 2], [3, 4, 5], "2025Q1")]
    keep = pd.Series([True, True, True, True, True, False], index=df.index)
    bench = S.zero_information_benchmarks(df, folds, "target_excess_return", keep_mask=keep)
    assert bench["n_test_dedup"].tolist() == [2, 2]
    assert bench["n_test"].tolist() == [3, 3]


def test_zero_information_summary_uses_sample_std_ddof1():
    bench = pd.DataFrame(
        {
            "benchmark": [S.ZERO_INFO_SIZE] * 3,
            "test_quarter": ["a", "b", "c"],
            "spearman_ic": [0.0, 1.0, 2.0],
            "spearman_ic_dedup": [0.0, 1.0, 2.0],
        }
    )
    summ = S.zero_information_summary(bench)
    assert summ["std_ic_raw"].iloc[0] == pytest.approx(1.0)  # ddof=1; ddof=0 would be 0.8165


def test_spearman_or_nan_returns_nan_on_constant_predictor():
    ic, p, n = S._spearman_or_nan(np.array([1.0, 1.0, 1.0]), np.array([1.0, 2.0, 3.0]))
    assert np.isnan(ic) and n == 3


def test_spearman_or_nan_drops_nan_pairs_and_reports_n_used():
    ic, p, n = S._spearman_or_nan(
        np.array([1.0, np.nan, 3.0, 4.0]), np.array([1.0, 2.0, 3.0, np.nan])
    )
    assert n == 2
    assert not np.isnan(ic)


# ---------------------------------------------------------------------------
# 3. Bootstrap noise anchor
# ---------------------------------------------------------------------------


def test_rowwise_spearman_matches_scipy_including_ties():
    rng = np.random.default_rng(7)
    x = rng.integers(0, 4, size=(25, 12)).astype(float)  # forces ties
    y = rng.integers(0, 4, size=(25, 12)).astype(float)
    got = S.rowwise_spearman(x, y)
    for i in range(x.shape[0]):
        if np.std(x[i]) == 0 or np.std(y[i]) == 0:
            assert np.isnan(got[i])
            continue
        want, _ = spearmanr(x[i], y[i])
        assert got[i] == pytest.approx(want, abs=1e-12)


def test_rowwise_spearman_constant_row_is_nan_not_zero():
    x = np.array([[1.0, 1.0, 1.0]])
    y = np.array([[1.0, 2.0, 3.0]])
    assert np.isnan(S.rowwise_spearman(x, y)[0])


def test_bootstrap_delta_sd_is_zero_when_the_two_predictors_are_identical():
    rng = np.random.default_rng(1)
    p = rng.normal(size=40)
    y = rng.normal(size=40)
    sd, n_bad = S.bootstrap_delta_sd(p, p, y, n_resamples=200, seed=3)
    assert sd == pytest.approx(0.0, abs=1e-12)
    assert n_bad == 0


def test_bootstrap_delta_sd_is_deterministic_given_the_seed():
    rng = np.random.default_rng(2)
    a, b, y = rng.normal(size=40), rng.normal(size=40), rng.normal(size=40)
    first, _ = S.bootstrap_delta_sd(a, b, y, n_resamples=300, seed=11)
    second, _ = S.bootstrap_delta_sd(a, b, y, n_resamples=300, seed=11)
    other, _ = S.bootstrap_delta_sd(a, b, y, n_resamples=300, seed=12)
    assert first == second
    assert first != other
    assert first > 0


def test_bootstrap_delta_sd_too_few_rows_is_nan():
    sd, _ = S.bootstrap_delta_sd(np.array([1.0, 2.0]), np.array([2.0, 1.0]), np.array([1.0, 2.0]))
    assert np.isnan(sd)


def test_chi2_std_ci_reproduces_the_audit_interval_for_six_folds():
    """methodology_audit.md defect 2: point 0.0742 over 6 folds ->
    95% CI [0.0463, 0.1820]."""
    lo, hi = S.chi2_std_ci(0.0742, 6)
    assert lo == pytest.approx(0.0463, abs=5e-4)
    assert hi == pytest.approx(0.1820, abs=5e-4)
    assert lo < 0.0742 < hi


def test_chi2_std_ci_degenerate_inputs():
    assert all(np.isnan(v) for v in S.chi2_std_ci(np.nan, 6))
    assert all(np.isnan(v) for v in S.chi2_std_ci(0.05, 1))


def _stub_fit_predict_factory(seed: int):
    """Deterministic stand-in for backtest.fit_predict: returns a fixed
    pseudo-random score per test row, keyed by feature-list length so the
    two arms differ."""

    def _fit_predict(df, feature_cols, train_idx, test_idx):
        rng = np.random.default_rng(seed + len(feature_cols))
        return rng.normal(size=len(test_idx))

    return _fit_predict


def test_bootstrap_noise_anchor_shape_and_summary_keys():
    rng = np.random.default_rng(5)
    n = 60
    df = pd.DataFrame(
        {
            "ticker": [f"T{i%10}" for i in range(n)],
            "filing_date": pd.to_datetime("2024-01-01") + pd.to_timedelta(np.arange(n), unit="D"),
            "target_excess_return": rng.normal(size=n),
        }
    )
    folds = [_fold(np.arange(0, 30), np.arange(30, 45), "2025Q1"), _fold(np.arange(0, 45), np.arange(45, 60), "2025Q2")]
    per_fold, summary = S.bootstrap_noise_anchor(
        df, folds, ["a", "b"], ["a"], _stub_fit_predict_factory(0), "target_excess_return",
        n_resamples=300, seed=0,
    )
    assert len(per_fold) == 2
    assert (per_fold["bootstrap_sd_of_delta"] > 0).all()
    for key in (
        "cross_fold_std_ddof1",
        "cross_fold_std_ddof0_published_convention",
        "cross_fold_std_ddof1_chi2_ci_lo",
        "mean_within_fold_bootstrap_sd",
        "rms_within_fold_bootstrap_sd",
        "implied_regime_floor_sd",
        "se_of_cross_fold_mean_naive",
    ):
        assert key in summary
    # RMS is never below the arithmetic mean of the same SDs
    assert summary["rms_within_fold_bootstrap_sd"] >= summary["mean_within_fold_bootstrap_sd"] - 1e-12
    assert summary["implied_regime_floor_sd"] >= 0.0


def test_bootstrap_summary_tests_the_floor_in_both_directions():
    """The floor must never be quoted as a point estimate alone: at k folds
    the cross-fold std has k-1 df, so both tails are reported."""
    rng = np.random.default_rng(9)
    n = 60
    df = pd.DataFrame(
        {
            "ticker": [f"T{i%10}" for i in range(n)],
            "filing_date": pd.to_datetime("2024-01-01") + pd.to_timedelta(np.arange(n), unit="D"),
            "target_excess_return": rng.normal(size=n),
        }
    )
    folds = [
        _fold(np.arange(0, 20), np.arange(20, 30), "2025Q1"),
        _fold(np.arange(0, 30), np.arange(30, 45), "2025Q2"),
        _fold(np.arange(0, 45), np.arange(45, 60), "2025Q3"),
    ]
    _, summary = S.bootstrap_noise_anchor(
        df, folds, ["a", "b"], ["a"], _stub_fit_predict_factory(4), "target_excess_return",
        n_resamples=300, seed=0,
    )
    p_hi = summary["p_spread_exceeds_sampling"]
    p_lo = summary["p_spread_below_sampling"]
    assert 0.0 <= p_hi <= 1.0 and 0.0 <= p_lo <= 1.0
    assert p_hi + p_lo == pytest.approx(1.0)
    assert summary["cross_var_over_bootstrap_var"] > 0


def test_bootstrap_section_never_claims_the_floor_is_established():
    per_fold = pd.DataFrame(
        {
            "test_quarter": ["2025Q1", "2025Q2"],
            "n_test": [40, 40],
            "n_test_dedup": [20, 20],
            "fold_delta_dedup": [0.1, -0.1],
            "bootstrap_sd_of_delta": [0.09, 0.11],
            "n_degenerate_resamples": [0, 0],
        }
    )
    summary = {
        "n_folds": 2, "n_resamples_per_fold": 4000,
        "mean_within_fold_bootstrap_sd": 0.10, "rms_within_fold_bootstrap_sd": 0.1005,
        "cross_fold_std_ddof1": 0.1414, "cross_fold_std_ddof0_published_convention": 0.1,
        "cross_fold_std_ddof1_chi2_ci_lo": 0.06, "cross_fold_std_ddof1_chi2_ci_hi": 0.9,
        "implied_regime_floor_sd": 0.0995, "se_of_cross_fold_mean_naive": 0.1,
        "cross_var_over_bootstrap_var": 1.979, "p_spread_exceeds_sampling": 0.159,
        "p_spread_below_sampling": 0.841,
    }
    text = "\n".join(S.bootstrap_section_lines(per_fold, summary, "test spec"))
    assert "p(spread > sampling) = 0.159" in text
    assert "does NOT establish" in text
    assert "unidentified" in text


def test_bootstrap_noise_anchor_uses_only_dedup_rows():
    rng = np.random.default_rng(6)
    n = 40
    df = pd.DataFrame(
        {
            "ticker": [f"T{i%8}" for i in range(n)],
            "filing_date": pd.to_datetime("2024-01-01") + pd.to_timedelta(np.arange(n), unit="D"),
            "target_excess_return": rng.normal(size=n),
        }
    )
    folds = [_fold(np.arange(0, 20), np.arange(20, 40), "2025Q1")]
    keep = pd.Series([i % 2 == 0 for i in range(n)], index=df.index)
    per_fold, _ = S.bootstrap_noise_anchor(
        df, folds, ["a", "b"], ["a"], _stub_fit_predict_factory(1), "target_excess_return",
        keep_mask=keep, n_resamples=200,
    )
    assert per_fold["n_test"].iloc[0] == 20
    assert per_fold["n_test_dedup"].iloc[0] == 10


# ---------------------------------------------------------------------------
# 4. Label-embargo census
# ---------------------------------------------------------------------------


def test_embargo_census_counts_training_labels_resolving_inside_the_test_quarter():
    df = pd.DataFrame(
        {
            "filing_date": pd.to_datetime(["2024-10-01", "2024-12-20", "2025-01-15"]),
            "target_end_date": pd.to_datetime(["2024-12-30", "2025-03-20", "2025-04-15"]),
        }
    )
    fold = {
        "test_quarter": pd.Period("2025Q1", freq="Q"),
        "train_idx": np.array([0, 1]),
        "test_idx": np.array([2]),
    }
    census = S.embargo_census(df, [fold])
    assert census["n_train"].iloc[0] == 2
    assert census["n_train_labels_resolving_in_or_after_test_quarter"].iloc[0] == 1
    assert census["share_non_embargoed"].iloc[0] == pytest.approx(0.5)


def test_embargo_census_missing_column_returns_empty():
    df = pd.DataFrame({"filing_date": pd.to_datetime(["2024-10-01"])})
    fold = {"test_quarter": pd.Period("2025Q1", freq="Q"), "train_idx": np.array([0]), "test_idx": np.array([0])}
    assert S.embargo_census(df, [fold]).empty


# ---------------------------------------------------------------------------
# 5. Standing report sections
# ---------------------------------------------------------------------------


def test_specification_section_names_primary_secondary_and_contamination():
    lines = "\n".join(S.specification_section_lines(S.PRIMARY_SPEC))
    assert S.PRIMARY_SPEC in lines and S.SECONDARY_SPEC in lines
    assert "PRIMARY" in lines and "SECONDARY" in lines
    assert "Contamination warning" in lines
    assert "0.987" in lines  # the a-priori ICC argument, not a results argument


def test_missing_inputs_produce_an_explicit_not_computed_notice():
    zero = "\n".join(S.zero_information_section_lines(None, None))
    boot = "\n".join(S.bootstrap_section_lines(None, None))
    assert "NOT COMPUTED" in zero and "un-benchmarked" in zero
    assert "NOT COMPUTED" in boot
    # a missing section must never be silently absent
    assert zero.startswith("## Zero-information benchmarks")
    assert boot.startswith("## Within-fold bootstrap noise anchor")


def test_report_sections_render_numbers_when_inputs_are_present():
    df = _bench_frame()
    folds = [_fold([0, 1, 2], [3, 4, 5], "2025Q1")]
    bench = S.zero_information_benchmarks(df, folds, "target_excess_return")
    summ = S.zero_information_summary(bench)
    text = "\n".join(S.zero_information_section_lines(bench, summ))
    assert S.ZERO_INFO_SIZE in text and S.ZERO_INFO_TICKER_MEAN in text
    assert "| benchmark |" in text

    per_fold = pd.DataFrame(
        {
            "test_quarter": ["2025Q1", "2025Q2"],
            "n_test": [40, 40],
            "n_test_dedup": [20, 20],
            "fold_delta_dedup": [0.1, -0.1],
            "bootstrap_sd_of_delta": [0.09, 0.11],
            "n_degenerate_resamples": [0, 0],
        }
    )
    summary = {
        "n_folds": 2,
        "n_resamples_per_fold": 4000,
        "mean_within_fold_bootstrap_sd": 0.10,
        "rms_within_fold_bootstrap_sd": 0.1005,
        "cross_fold_std_ddof1": 0.1414,
        "cross_fold_std_ddof0_published_convention": 0.1,
        "cross_fold_std_ddof1_chi2_ci_lo": 0.06,
        "cross_fold_std_ddof1_chi2_ci_hi": 0.9,
        "implied_regime_floor_sd": 0.0995,
        "se_of_cross_fold_mean_naive": 0.1,
    }
    boot = "\n".join(S.bootstrap_section_lines(per_fold, summary, "raw levels"))
    assert "0.1005" in boot and "chi-square CI" in boot
    assert "LOWER BOUND" in boot  # the fold-non-independence caveat is mandatory


def test_embargo_section_states_the_pooled_population():
    census = pd.DataFrame(
        {
            "test_quarter": ["2025Q1"],
            "n_train": [100],
            "n_train_with_target_end": [100],
            "n_train_labels_resolving_in_or_after_test_quarter": [30],
            "share_non_embargoed": [0.30],
        }
    )
    text = "\n".join(S.embargo_section_lines(census))
    assert "30 of 100" in text and "30.0%" in text


# ---------------------------------------------------------------------------
# 6. ddof=1 corrections in the two generators (audit defect 1)
# ---------------------------------------------------------------------------

GENERATORS = ("backtest.py", "diagnose.py")


def test_no_population_std_survives_in_either_generator():
    """methodology_audit.md defect 1: `std(ddof=0)` over six fold deltas is
    a POPULATION std reported as if it were the sample std, and every MDE in
    EXPANSION_PLAN §2a inherited a sqrt(5/6)=0.913 optimism from it. Pin the
    call form out of both generators."""
    for name in GENERATORS:
        src = (REPO_ROOT / name).read_text()
        hits = re.findall(r"std\(\s*ddof\s*=\s*0\s*\)", src)
        assert not hits, f"{name} still computes a population std: {hits}"


def test_backtest_summary_row_reports_the_sample_std():
    import backtest as B

    out = B._summary_row(pd.Series([0.0, 1.0, 2.0]))
    assert "std=1.0000" in out, f"expected ddof=1 (1.0000), got: {out}"


# ---------------------------------------------------------------------------
# 7. Report generation: the standing sections are present on the real path,
#    and the frozen E1 gate reports are never the write target.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not FEATURES_PATH.exists(), reason="data/features.parquet not present")
def test_backtest_report_carries_every_standing_section(tmp_path):
    import backtest as B

    df_raw, n_dropped = B.load_modeling_frame()
    folds = B.build_walk_forward_folds(df_raw, B.BURN_IN_END)[:2]
    keep_mask = B.company_quarter_dedup_keep_mask(df_raw)
    spec_frames = B.build_spec_frames(df_raw)
    df = spec_frames[S.PRIMARY_SPEC]

    results = B.run_backtest(df, folds, keep_mask=keep_mask)
    results_secondary = B.run_backtest(spec_frames[S.SECONDARY_SPEC], folds, keep_mask=keep_mask)
    dedup_stats = B.compute_dedup_diagnostics(df)
    df_form, folds_form, results_form = B.run_form_controlled_ablation(df, B.BURN_IN_END)
    importances = {
        "numeric_only": B.fit_full_sample_importance(df, B.NUMERIC_FEATURES),
        "text_and_numeric": B.fit_full_sample_importance(df, B.FULL_FEATURES),
    }
    standing = B.compute_standing_diagnostics(df_raw, spec_frames, folds, keep_mask)

    out = tmp_path / "report.md"
    B.write_backtest_report(
        df, n_dropped, folds, results, importances, dedup_stats, df_form, folds_form[:2],
        {k: v.head(2) for k, v in results_form.items()},
        standing=standing, results_secondary=results_secondary, output_path=out,
    )
    text = out.read_text()
    assert "## Feature specification (pre-registered" in text
    assert "## Zero-information benchmarks (STANDING" in text
    assert text.count("## Within-fold bootstrap noise anchor (STANDING") == 2  # one per spec
    assert "## Label-embargo census" in text
    assert "## Paired secondary specification" in text
    assert "SPECIFICATION SENSITIVITY" in text
    assert S.ZERO_INFO_SIZE in text and S.ZERO_INFO_TICKER_MEAN in text
    # the frozen go/no-go artifact must not have been the write target
    assert B.BACKTEST_REPORT_OUTPUT.name not in str(out)


@pytest.mark.skipif(not FEATURES_PATH.exists(), reason="data/features.parquet not present")
def test_backtest_report_without_standing_inputs_says_not_computed(tmp_path):
    import backtest as B

    df_raw, n_dropped = B.load_modeling_frame()
    folds = B.build_walk_forward_folds(df_raw, B.BURN_IN_END)[:1]
    results = B.run_backtest(df_raw, folds)
    dedup_stats = B.compute_dedup_diagnostics(df_raw)
    df_form, folds_form, results_form = B.run_form_controlled_ablation(df_raw, B.BURN_IN_END)
    importances = {
        "numeric_only": B.fit_full_sample_importance(df_raw, B.NUMERIC_FEATURES),
        "text_and_numeric": B.fit_full_sample_importance(df_raw, B.FULL_FEATURES),
    }
    out = tmp_path / "report.md"
    B.write_backtest_report(
        df_raw, n_dropped, folds, results, importances, dedup_stats, df_form, folds_form[:1],
        {k: v.head(1) for k, v in results_form.items()}, output_path=out,
    )
    text = out.read_text()
    assert text.count("NOT COMPUTED") >= 3
    assert "## Zero-information benchmarks (STANDING" in text


@pytest.mark.skipif(not FEATURES_PATH.exists(), reason="data/features.parquet not present")
def test_standing_diagnostics_cover_both_specifications():
    import backtest as B

    df_raw, _ = B.load_modeling_frame()
    folds = B.build_walk_forward_folds(df_raw, B.BURN_IN_END)[:2]
    keep_mask = B.company_quarter_dedup_keep_mask(df_raw)
    standing = B.compute_standing_diagnostics(df_raw, B.build_spec_frames(df_raw), folds, keep_mask)
    assert set(standing["bootstrap"]) == set(S.SPEC_NAMES)
    assert not standing["bench_df"].empty
    assert not standing["embargo_census"].empty
    # benchmarks are spec-independent by construction: computed on the raw frame
    assert (standing["bench_df"]["n_test"] > 0).all()


@pytest.mark.skipif(not FEATURES_PATH.exists(), reason="data/features.parquet not present")
def test_build_spec_frames_transforms_primary_and_leaves_secondary_alone():
    import backtest as B

    df_raw, _ = B.load_modeling_frame()
    frames = B.build_spec_frames(df_raw)
    assert frames[S.SECONDARY_SPEC]["log_total_assets"].equals(df_raw["log_total_assets"])
    primary = frames[S.PRIMARY_SPEC]["log_total_assets"].dropna()
    assert ((primary > 0) & (primary < 1)).all()
    # non-feature columns survive the transform untouched
    assert frames[S.PRIMARY_SPEC][B.TARGET_COL].equals(df_raw[B.TARGET_COL])


def test_diagnose_family_summary_reports_the_sample_std():
    import diagnose as D

    long_df = pd.DataFrame(
        {
            "family": ["full"] * 3,
            "test_quarter": ["a", "b", "c"],
            "delta_dedup_vs_numeric": [0.0, 1.0, 2.0],
            "delta_raw_vs_numeric": [0.0, 1.0, 2.0],
        }
    )
    summ = D.family_delta_summary(long_df, ["full"])
    assert summ["std_delta_dedup_vs_numeric"].iloc[0] == pytest.approx(1.0)
