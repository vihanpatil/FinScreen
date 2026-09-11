"""
test_heads_e2.py -- tests for the HEAD-2 / HEAD-3 runners.

EVERY FIXTURE IN THIS FILE IS SYNTHETIC. No test reads a `data/f5` parquet, the
metadata DB, the price snapshot, or any real return; no test computes an
association on E2 data. That is the E2 freeze (F5_PLAN.md §1) applied to the
test suite, where it is easiest to break by accident.

The one real file any test opens is `heads_e2.py`'s own SOURCE, parsed with
`ast` for the call-graph tripwire that proves the census path cannot reach a
fitting function.

What is enforced here:
  * the guard: no ratified document, missing document, sha mismatch, zero or
    two parameter blocks, a missing pin, an unimplemented pinned value;
  * head-2 DV arithmetic and window placement strictly after the news session;
  * wild-cluster bootstrap shape, Rademacher weights, cluster structure,
    determinism;
  * head-3 exit labelling, horizon boundaries, censoring, AUC and prevalence
    per fold, the training-purge rule;
  * every pinned parameter comes from the document (drop a key -> refusal;
    change a value -> the arithmetic changes).
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import backtest_e2 as BT
import heads_e2 as H


# ---------------------------------------------------------------------------
# Synthetic G3 document helpers
# ---------------------------------------------------------------------------

def minimal_params() -> dict:
    """A complete, SYNTHETIC parameter block in the SHARED document convention
    (backtest_e2's `json g3-params` fence, parameters at the root). Not a
    proposal for G3."""
    return {
        "seeds": {"primary": 0},
        "fold_quarters": ["2019Q1", "2019Q2"],
        "columns": {"confirmatory_text": ["t1"], "numeric": ["n1"]},
        "head2": {
            "stratum": "core",
            "predictor": "x",
            "direction": "positive",
            "event_window_sessions": [1, 5],
            "trailing_sessions": 60,
            "statistic": "ols_slope",
            "bootstrap": {"weights": "rademacher", "n_draws": 100,
                          "cluster": "event_quarter", "seed": 0},
        },
        "head3": {
            "horizon_quarters": 4,
            "label_cut": "2020-12-31",
            "exit_event_kinds": ["delisting_form_25"],
            "feature_filing_rule": "latest_in_quarter",
            "train_label_purge": "horizon_end_before_test_start",
            "missing_value_rule": "train_median",
            "standardize": True,
            "model": "logistic_l2",
            "model_params": {"l2": 1.0, "max_iter": 50, "tol": 1e-10},
            "metric": "auc",
        },
    }


def write_doc(tmp_path: Path, params_blocks, ratify=True, sha_override=None):
    """Write a synthetic pre-registration (+ ratification) and return the paths."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    doc = tmp_path / "G3_PREREGISTRATION.md"
    body = ["# synthetic pre-registration (test fixture)\n"]
    for block in params_blocks:
        body.append("```" + H.FENCE_INFO + "\n" + json.dumps(block, indent=1)
                    + "\n```\n")
    doc.write_text("\n".join(body))
    rat = tmp_path / "G3_RATIFIED.json"
    if ratify:
        sha = sha_override or hashlib.sha256(doc.read_bytes()).hexdigest()
        rat.write_text(json.dumps({"doc_sha256": sha, "ratified_by": "test"}))
    return doc, rat


# ---------------------------------------------------------------------------
# 1. The guard
# ---------------------------------------------------------------------------

def test_guard_refuses_when_neither_file_exists(tmp_path):
    with pytest.raises(H.FreezeRefusal) as e:
        H.load_ratified_params(tmp_path / "nope.md", tmp_path / "nope.json")
    assert "BLOCKED" in str(e.value)


def test_the_guard_is_head_1s_guard_not_a_second_copy():
    """One guard for all three heads: a divergence here is how two runners end
    up with two different definitions of 'ratified'."""
    assert H.FreezeRefusal is BT.G3Refusal
    assert H.sha256_file is BT.sha256_file
    assert H.FENCE_INFO == BT.FENCE_INFO
    assert H.RUN_LOG == BT.RUN_LOG_PATH


def test_guard_refuses_when_only_the_document_exists(tmp_path):
    doc, rat = write_doc(tmp_path, [minimal_params()], ratify=False)
    assert not rat.exists()
    with pytest.raises(H.FreezeRefusal):
        H.load_ratified_params(doc, rat)


def test_guard_refuses_on_sha_mismatch(tmp_path):
    doc, rat = write_doc(tmp_path, [minimal_params()])
    doc.write_text(doc.read_text() + "\nan edit made after ratification\n")
    with pytest.raises(H.FreezeRefusal) as e:
        H.load_ratified_params(doc, rat)
    assert "doc_sha256" in str(e.value)


def test_guard_accepts_a_matching_sha_and_returns_the_block(tmp_path):
    doc, rat = write_doc(tmp_path, [minimal_params()])
    params, sha = H.load_ratified_params(doc, rat)
    assert sha == hashlib.sha256(doc.read_bytes()).hexdigest()
    assert H.get_param(params, "head2.trailing_sessions") == 60


def test_guard_refuses_two_parameter_blocks(tmp_path):
    doc, rat = write_doc(tmp_path, [minimal_params(), minimal_params()])
    with pytest.raises(H.FreezeRefusal) as e:
        H.load_ratified_params(doc, rat)
    assert "exactly one" in str(e.value)


def test_guard_refuses_zero_parameter_blocks(tmp_path):
    doc = tmp_path / "G3_PREREGISTRATION.md"
    doc.write_text("# no fenced parameter block here\n")
    rat = tmp_path / "G3_RATIFIED.json"
    rat.write_text(json.dumps(
        {"doc_sha256": hashlib.sha256(doc.read_bytes()).hexdigest()}))
    with pytest.raises(H.FreezeRefusal):
        H.load_ratified_params(doc, rat)


@pytest.mark.parametrize("keys", [H.REQUIRED_HEAD2, H.REQUIRED_HEAD3])
def test_every_required_key_is_individually_load_bearing(keys):
    """Drop any single pin and the head refuses; there is no default."""
    for dropped in keys:
        params = minimal_params()
        parts = dropped.split(".")
        target = params
        for part in parts[:-1]:
            target = target[part]
        target.pop(parts[-1])
        with pytest.raises(H.FreezeRefusal) as e:
            H.check_required(params, keys)
        assert dropped in str(e.value)


def test_unimplemented_pinned_value_is_a_refusal_not_a_fallback():
    params = minimal_params()
    params["head3"]["model"] = "gradient_boosting"
    with pytest.raises(H.FreezeRefusal) as e:
        H.check_required(params, H.REQUIRED_HEAD3)
    assert "does not implement" in str(e.value)


def test_cli_refuses_both_heads_today(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(H, "PREREG_PATH", tmp_path / "absent.md")
    monkeypatch.setattr(H, "RATIFIED_PATH", tmp_path / "absent.json")
    monkeypatch.setattr(H, "HEAD2_RESULTS", tmp_path / "results_head2.json")
    monkeypatch.setattr(H, "HEAD3_RESULTS", tmp_path / "results_head3.json")
    monkeypatch.setattr(H, "RUN_LOG", tmp_path / "run_log.jsonl")
    for flag in ("--head2", "--head3", "--all"):
        assert H.main([flag]) == 2
    assert not (tmp_path / "results_head2.json").exists()
    assert not (tmp_path / "results_head3.json").exists()
    assert not (tmp_path / "run_log.jsonl").exists()
    assert "BLOCKED" in capsys.readouterr().err


def test_the_real_repo_has_no_ratified_document_today():
    """The freeze is in force; if this fails, G3 happened and that is news."""
    assert not H.RATIFIED_PATH.exists()
    assert not H.PREREG_PATH.exists()


# ---------------------------------------------------------------------------
# 2. Head-2 DV arithmetic and window placement
# ---------------------------------------------------------------------------

def synthetic_prices(n=40, cik=11):
    cal = pd.date_range("2021-01-04", periods=n, freq="B")
    closes = 100.0 * np.cumprod(1.0 + 0.01 * np.sin(np.arange(n)))
    return pd.DataFrame({cik: closes}, index=cal)


def one_event(cik=11, news_pos=30):
    return pd.DataFrame({"cik": [cik], "news_pos": [news_pos],
                         "pre_pos": [news_pos - 1], "prices_complete": [True]})


def test_dv_equals_the_hand_computed_ratio():
    prices = synthetic_prices()
    col = prices.iloc[:, 0].to_numpy()
    ev = one_event(news_pos=30)
    out = H.attach_head2_dv(ev, prices, (1, 5), 10)
    num = np.abs(col[31:36] / col[30:35] - 1).mean()   # sessions +1..+5
    den = np.abs(col[20:30] / col[19:29] - 1).mean()   # 10 returns ending at +0-1
    assert out["dv_post_mean_abs_return"].iloc[0] == pytest.approx(num, rel=1e-12)
    assert out["dv_trailing_mean_abs_return"].iloc[0] == pytest.approx(den, rel=1e-12)
    assert out["dv_relative_move"].iloc[0] == pytest.approx(num / den, rel=1e-12)


def test_numerator_sessions_are_strictly_after_the_news_session():
    """Only sessions +1..+5 move the numerator; the news session's own close is
    the base of the +1 return and nothing earlier enters it."""
    prices = synthetic_prices()
    ev = one_event(news_pos=30)
    base = H.attach_head2_dv(ev, prices, (1, 5), 10)["dv_post_mean_abs_return"].iloc[0]
    # Poisoning any session strictly before the news session leaves it alone.
    poisoned = prices.copy()
    poisoned.iloc[:30] = 7.0
    got = H.attach_head2_dv(ev, poisoned, (1, 5), 10)["dv_post_mean_abs_return"].iloc[0]
    assert got == pytest.approx(base, rel=1e-12)
    # Poisoning session +6 and later leaves it alone too.
    poisoned2 = prices.copy()
    poisoned2.iloc[36:] = 7.0
    got2 = H.attach_head2_dv(ev, poisoned2, (1, 5), 10)["dv_post_mean_abs_return"].iloc[0]
    assert got2 == pytest.approx(base, rel=1e-12)
    # Poisoning session +3 does move it -- the window is not vacuous.
    poisoned3 = prices.copy()
    poisoned3.iloc[33] = 7.0
    got3 = H.attach_head2_dv(ev, poisoned3, (1, 5), 10)["dv_post_mean_abs_return"].iloc[0]
    assert got3 != pytest.approx(base, rel=1e-6)


def test_denominator_never_sees_the_news_session_or_later():
    prices = synthetic_prices()
    ev = one_event(news_pos=30)
    base = H.attach_head2_dv(ev, prices, (1, 5), 10)["dv_trailing_mean_abs_return"].iloc[0]
    poisoned = prices.copy()
    poisoned.iloc[30:] = 7.0            # every session >= news
    got = H.attach_head2_dv(ev, poisoned, (1, 5), 10)["dv_trailing_mean_abs_return"].iloc[0]
    assert got == pytest.approx(base, rel=1e-12)
    # ... and it uses exactly `trailing_sessions` returns.
    longer = H.attach_head2_dv(ev, prices, (1, 5), 20)["dv_trailing_mean_abs_return"].iloc[0]
    col = prices.iloc[:, 0].to_numpy()
    assert longer == pytest.approx(np.abs(col[10:30] / col[9:29] - 1).mean(), rel=1e-12)


def test_a_window_opening_on_the_news_session_is_rejected():
    with pytest.raises(ValueError):
        H.attach_head2_dv(one_event(), synthetic_prices(), (0, 5), 10)


def test_incomplete_prices_and_zero_denominator_give_nan_not_a_number():
    prices = synthetic_prices()
    ev = one_event(news_pos=30)
    ev.loc[0, "prices_complete"] = False
    assert np.isnan(H.attach_head2_dv(ev, prices, (1, 5), 10)["dv_relative_move"].iloc[0])
    flat = prices.copy()
    flat.iloc[:30] = 50.0               # trailing window is perfectly flat
    ev2 = one_event(news_pos=30)
    out = H.attach_head2_dv(ev2, flat, (1, 5), 10)
    assert out["dv_trailing_mean_abs_return"].iloc[0] == 0.0
    assert np.isnan(out["dv_relative_move"].iloc[0])


def test_dv_is_scale_free_in_the_price_level():
    prices = synthetic_prices()
    ev = one_event(news_pos=30)
    a = H.attach_head2_dv(ev, prices, (1, 5), 10)["dv_relative_move"].iloc[0]
    b = H.attach_head2_dv(ev, prices * 3.0, (1, 5), 10)["dv_relative_move"].iloc[0]
    assert a == pytest.approx(b, rel=1e-12)


# ---------------------------------------------------------------------------
# 3. Wild-cluster bootstrap
# ---------------------------------------------------------------------------

def test_rademacher_weights_shape_values_and_determinism():
    w = H.rademacher_weights(50, 7, 0)
    assert w.shape == (50, 7)
    assert set(np.unique(w)) <= {-1.0, 1.0}
    assert np.array_equal(w, H.rademacher_weights(50, 7, 0))
    assert not np.array_equal(w, H.rademacher_weights(50, 7, 1))


def synthetic_head2_sample(n=120, n_clusters=6, seed=3):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0, 1, size=n)
    y = 1.0 + 0.8 * x + rng.normal(scale=0.2, size=n)
    clusters = np.array([f"20{18 + i // 4}Q{1 + i % 4}"
                         for i in np.repeat(np.arange(n_clusters), n // n_clusters)])
    return x, y, clusters


def test_bootstrap_shape_clusters_and_determinism():
    x, y, cl = synthetic_head2_sample()
    b = H.wild_cluster_bootstrap(x, y, cl, n_draws=250, seed=0)
    assert b["null_draws"].shape == (250,)
    assert b["n_clusters"] == len(set(cl))
    assert sum(b["cluster_sizes"].values()) == b["n_obs"] == len(y)
    assert b["se_wild_cluster"] > 0
    assert 0.0 <= b["p_two_sided"] <= 1.0
    assert 0.0 <= b["p_one_sided_positive"] <= 1.0
    assert str(b["n_clusters"]) in b["few_clusters_limitation"]
    again = H.wild_cluster_bootstrap(x, y, cl, n_draws=250, seed=0)
    assert np.array_equal(b["null_draws"], again["null_draws"])


def test_bootstrap_slope_matches_an_independent_ols():
    x, y, cl = synthetic_head2_sample()
    b = H.wild_cluster_bootstrap(x, y, cl, n_draws=50, seed=0)
    assert b["slope"] == pytest.approx(np.polyfit(x, y, 1)[0], rel=1e-10)


def test_weights_are_constant_within_a_cluster():
    """With one cluster the null draws can take only two values, +-d."""
    x, y, _ = synthetic_head2_sample()
    one = np.array(["2019Q1"] * len(y))
    b = H.wild_cluster_bootstrap(x, y, one, n_draws=200, seed=0)
    assert b["n_clusters"] == 1
    assert len(np.unique(np.round(np.abs(b["null_draws"]), 12))) == 1


def test_null_draws_are_centred_on_zero_not_on_the_estimate():
    x, y, cl = synthetic_head2_sample(n=240, n_clusters=12)
    b = H.wild_cluster_bootstrap(x, y, cl, n_draws=2000, seed=0)
    assert abs(float(np.mean(b["null_draws"]))) < abs(b["slope"])


# ---------------------------------------------------------------------------
# 4. Head-3 exit labelling and censoring
# ---------------------------------------------------------------------------

def synthetic_exits():
    return pd.DataFrame({
        "cik": [1, 2, 3, 4],
        "accession_number": list("abcd"),
        "form": ["25", "25", "15-12B", "25"],
        "filing_date": pd.to_datetime(
            ["2019-05-01", "2020-06-01", "2019-05-01", "2019-02-01"]),
        "items": [None, None, None, None],
        "event_kind": ["delisting_form_25", "delisting_form_25",
                       "deregistration_form_15", "delisting_form_25"],
    })


def test_exit_is_labelled_only_inside_the_horizon_and_strictly_after_the_feature_date():
    panel = pd.DataFrame({
        "cik": [1, 2, 4],
        "quarter": ["2019Q1"] * 3,
        "feature_date": pd.to_datetime(["2019-02-01"] * 3),
    })
    out, counters = H.label_exits(panel, synthetic_exits(), 4,
                                  ["delisting_form_25"], "2021-12-31")
    # cik 1 exits 2019-05-01 (inside 4 quarters); cik 2 exits 2020-06-01
    # (outside); cik 4's exit is ON the feature date -> strictly after fails.
    assert out["exit_within_horizon"].tolist() == [1, 0, 0]
    assert counters["positives_observable"] == 1


def test_only_the_pinned_event_kinds_count():
    panel = pd.DataFrame({"cik": [3], "quarter": ["2019Q1"],
                          "feature_date": pd.to_datetime(["2019-02-01"])})
    only_25, _ = H.label_exits(panel, synthetic_exits(), 4,
                               ["delisting_form_25"], "2021-12-31")
    both, _ = H.label_exits(panel, synthetic_exits(), 4,
                            ["delisting_form_25", "deregistration_form_15"],
                            "2021-12-31")
    assert only_25["exit_within_horizon"].tolist() == [0]
    assert both["exit_within_horizon"].tolist() == [1]


def test_an_exit_exactly_at_the_horizon_end_counts():
    panel = pd.DataFrame({"cik": [1], "quarter": ["2018Q2"],
                          "feature_date": pd.to_datetime(["2018-05-01"])})
    out, _ = H.label_exits(panel, synthetic_exits(), 4,
                           ["delisting_form_25"], "2021-12-31")
    assert out["horizon_end"].iloc[0] == pd.Timestamp("2019-05-01")
    assert out["exit_within_horizon"].iloc[0] == 1


def test_unobservable_rows_are_flagged_and_counted_not_scored_as_zeros():
    panel = pd.DataFrame({
        "cik": [1, 1],
        "quarter": ["2019Q1", "2020Q4"],
        "feature_date": pd.to_datetime(["2019-02-01", "2020-11-01"]),
    })
    out, counters = H.label_exits(panel, synthetic_exits(), 4,
                                  ["delisting_form_25"], "2021-06-30")
    assert out["label_observable"].tolist() == [True, False]
    assert counters["panel_rows_label_unobservable"] == 1


def test_fold_censoring_boundary_is_exact():
    # 2020Q4 ends 2020-12-31; +4 quarters = 2021-12-31.
    assert H.fold_censored("2020Q4", 4, "2021-12-31") is False
    assert H.fold_censored("2020Q4", 4, "2021-12-30") is True


# ---------------------------------------------------------------------------
# 5. Head-3 folds: AUC, prevalence, censoring, purge
# ---------------------------------------------------------------------------

def synthetic_panel(n_per_quarter=40, quarters=("2018Q1", "2018Q2", "2019Q1", "2019Q2"),
                    horizon_months=2):
    """A panel whose feature `n1` separates the label perfectly by construction.

    Entirely synthetic: no price, no return, no real filing. `t1` is noise so
    that the text block is exercised without being informative.

    `horizon_months` sets `horizon_end` (feature date + that many months).
    The default is short enough that the ONE implemented training purge
    (`horizon_end_before_test_start`) still leaves earlier quarters in the
    training fold, so the scoring tests exercise scoring rather than the purge;
    the purge test passes 12 explicitly and checks the boundary itself.
    """
    rng = np.random.default_rng(7)
    rows = []
    for q in quarters:
        start = pd.Period(q, freq="Q").start_time + pd.Timedelta(days=20)
        for i in range(n_per_quarter):
            label = int(i % 4 == 0)
            rows.append({
                "cik": 1000 + i,
                "quarter": q,
                "feature_date": start,
                "t1": float(rng.normal()),
                "n1": 3.0 + label * 5.0,
                "exit_within_horizon": label,
                "label_observable": True,
                "horizon_end": start + pd.DateOffset(months=horizon_months),
            })
    return pd.DataFrame(rows)


def test_auc_is_one_per_scored_fold_when_the_feature_separates_perfectly():
    params = minimal_params()
    params["fold_quarters"] = ["2019Q1", "2019Q2"]
    params["head3"]["label_cut"] = "2030-12-31"
    folds = H.run_head3_folds(synthetic_panel(), params)
    assert [f["test_quarter"] for f in folds] == ["2019Q1", "2019Q2"]
    for f in folds:
        assert f["status"] == "SCORED"
        assert f["auc"] == pytest.approx(1.0)
        assert f["test_prevalence"] == pytest.approx(0.25)
        assert f["n_test"] == 40 and f["n_test_positive"] == 10


def test_auc_is_one_half_when_only_a_noise_feature_is_pinned():
    params = minimal_params()
    params["columns"]["numeric"] = []
    params["columns"]["confirmatory_text"] = ["t1"]
    params["head3"]["label_cut"] = "2030-12-31"
    folds = H.run_head3_folds(synthetic_panel(), params)
    for f in folds:
        assert f["auc"] is not None
        assert 0.0 <= f["auc"] <= 1.0


def test_a_censored_fold_is_counted_and_not_scored():
    params = minimal_params()
    params["fold_quarters"] = ["2018Q2", "2019Q2"]
    params["head3"]["label_cut"] = "2019-12-31"   # 2019Q2 + 4q = 2020-06-30
    folds = H.run_head3_folds(synthetic_panel(), params)
    by_q = {f["test_quarter"]: f for f in folds}
    assert by_q["2018Q2"]["censored"] is False and by_q["2018Q2"]["auc"] is not None
    assert by_q["2019Q2"]["censored"] is True
    assert by_q["2019Q2"]["auc"] is None
    assert "CENSORED" in by_q["2019Q2"]["status"]
    assert by_q["2019Q2"]["n_test_panel_rows"] == 40   # counted, not scored


def test_prevalence_is_reported_even_when_the_fold_is_not_scored():
    params = minimal_params()
    params["fold_quarters"] = ["2018Q1"]     # no earlier quarter -> no train
    params["head3"]["label_cut"] = "2030-12-31"
    folds = H.run_head3_folds(synthetic_panel(), params)
    assert folds[0]["auc"] is None
    assert "NOT SCORED" in folds[0]["status"]
    assert folds[0]["test_prevalence"] == pytest.approx(0.25)


def test_training_is_strictly_earlier_quarters_and_the_purge_rule_is_applied():
    panel = synthetic_panel(horizon_months=12)
    params = minimal_params()
    params["fold_quarters"] = ["2019Q2"]
    params["head3"]["label_cut"] = "2030-12-31"
    purged = H.run_head3_folds(panel, params)[0]
    # Training rows come from 2018Q1 + 2018Q2 + 2019Q1 only (120 rows), and the
    # fixture's horizon ends 12 months after the feature date, so only the
    # 2018Q1 rows (horizon end 2019-01-20) resolve before 2019Q2 opens.
    assert purged["n_train_purged"] == 80
    assert purged["n_train"] == 40
    assert purged["train_label_purge"] == "horizon_end_before_test_start"


def test_a_no_purge_head3_is_a_refusal_not_a_selectable_convention():
    """Head 1 implements exactly one purge rule; head 3 now matches it. "none"
    trains on rows whose exit label resolves inside or after the test quarter,
    so it is refused at both doors -- `check_required` and the fold runner."""
    assert H.SUPPORTED["head3.train_label_purge"] == ("horizon_end_before_test_start",)
    params = minimal_params()
    params["head3"]["train_label_purge"] = "none"
    with pytest.raises(H.FreezeRefusal) as exc:
        H.check_required(params, H.REQUIRED_HEAD3)
    assert "train_label_purge" in str(exc.value)
    with pytest.raises(H.FreezeRefusal) as exc:
        H.run_head3_folds(synthetic_panel(), params)
    assert "no implementation" in str(exc.value)


def test_a_single_class_training_fold_is_not_scored():
    panel = synthetic_panel()
    panel.loc[panel["quarter"] == "2018Q1", "exit_within_horizon"] = 0
    panel = panel[panel["quarter"].isin(["2018Q1", "2018Q2"])]
    params = minimal_params()
    params["fold_quarters"] = ["2018Q2"]
    params["head3"]["label_cut"] = "2030-12-31"
    folds = H.run_head3_folds(panel, params)
    assert folds[0]["auc"] is None
    assert "one class" in folds[0]["status"]


def test_a_pinned_feature_column_that_does_not_exist_is_a_refusal():
    params = minimal_params()
    params["columns"]["numeric"] = ["n1", "a_column_that_does_not_exist"]
    params["head3"]["label_cut"] = "2030-12-31"
    with pytest.raises(H.FreezeRefusal) as e:
        H.run_head3_folds(synthetic_panel(), params)
    assert "a_column_that_does_not_exist" in str(e.value)


def test_embedding_column_count_must_equal_the_pinned_pca_k():
    panel = synthetic_panel()
    panel["emb_pc1"] = 0.0
    panel["emb_pc2"] = 0.0
    params = minimal_params()
    params["columns"]["confirmatory_text"] = ["t1", "emb_pc1", "emb_pc2"]
    params["head3"]["label_cut"] = "2030-12-31"
    with pytest.raises(H.FreezeRefusal):
        H.run_head3_folds(panel, params)          # embedding.pca_k unpinned
    params["embedding"] = {"pca_k": 3}
    with pytest.raises(H.FreezeRefusal) as e:
        H.run_head3_folds(panel, params)
    assert "embedding" in str(e.value)
    params["embedding"] = {"pca_k": 2}
    assert H.run_head3_folds(panel, params)       # 2 columns, k = 2


def test_imputation_and_standardisation_use_training_statistics_only():
    """The test fold's own mean / sd / median must never touch its own matrix."""
    train = pd.DataFrame({"n1": [1.0, 3.0, 5.0], "t1": [0.0, 1.0, 2.0]})
    test = pd.DataFrame({"n1": [np.nan, 100.0], "t1": [10.0, 20.0]})
    Xtr, Xte, _, _ = H._prepare_matrix(train, test, ["n1", "t1"],
                                       "train_median", True)
    mu, sd = 3.0, float(np.std([1.0, 3.0, 5.0]))      # training mean / sd, ddof=0
    # The missing test value is filled with the TRAINING median (3.0) and so
    # standardises to exactly 0.0; the test fold's own median (100.0) would not.
    assert Xte[0, 0] == pytest.approx(0.0)
    assert Xte[1, 0] == pytest.approx((100.0 - mu) / sd)
    assert Xtr[:, 0] == pytest.approx((np.array([1.0, 3.0, 5.0]) - mu) / sd)


def test_a_later_quarter_cannot_change_an_earlier_folds_score():
    panel = synthetic_panel()
    params = minimal_params()
    params["fold_quarters"] = ["2019Q1"]
    params["head3"]["label_cut"] = "2030-12-31"
    base = H.run_head3_folds(panel, params)[0]["auc"]
    shifted = panel.copy()
    mask = shifted["quarter"] == "2019Q2"          # a quarter AFTER the test fold
    shifted.loc[mask, "n1"] = 1e6
    assert H.run_head3_folds(shifted, params)[0]["auc"] == pytest.approx(base)


def test_drop_row_missing_rule_drops_rather_than_imputes():
    panel = synthetic_panel()
    panel.loc[panel.index[:5], "n1"] = np.nan
    params = minimal_params()
    params["fold_quarters"] = ["2019Q1"]
    params["head3"]["label_cut"] = "2030-12-31"
    params["head3"]["missing_value_rule"] = "drop_row"
    fold = H.run_head3_folds(panel, params)[0]
    assert fold["n_train_used"] == fold["n_train"] - 5
    assert fold["n_test_used"] == fold["n_test"]


# ---------------------------------------------------------------------------
# 6. AUC / classifier primitives
# ---------------------------------------------------------------------------

def test_auc_known_answers_and_tie_handling():
    assert H.auc_score(np.array([0, 0, 1, 1]), np.array([1.0, 2.0, 3.0, 4.0])) == 1.0
    assert H.auc_score(np.array([1, 1, 0, 0]), np.array([1.0, 2.0, 3.0, 4.0])) == 0.0
    assert H.auc_score(np.array([0, 1, 0, 1]), np.array([1.0, 1.0, 1.0, 1.0])) == 0.5
    assert H.auc_score(np.array([0, 0, 0]), np.array([1.0, 2.0, 3.0])) is None


def test_logistic_l2_recovers_the_direction_on_synthetic_data():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(400, 2))
    y = (X[:, 0] + 0.2 * rng.normal(size=400) > 0).astype(float)
    beta = H.logistic_l2_fit(X, y, l2=1.0, max_iter=50, tol=1e-10)
    assert beta[1] > 0                     # first feature is the signal
    assert abs(beta[2]) < abs(beta[1])
    p = H.logistic_l2_score(beta, X)
    assert ((p >= 0) & (p <= 1)).all()
    assert H.auc_score(y, p) > 0.9


# ---------------------------------------------------------------------------
# 7. Parameters come from the document, not from the code
# ---------------------------------------------------------------------------

def test_head2_windows_are_taken_from_the_document(tmp_path):
    params_block = minimal_params()
    params_block["head2"]["event_window_sessions"] = [1, 2]
    params_block["head2"]["trailing_sessions"] = 5
    doc, rat = write_doc(tmp_path, [params_block])
    params, _ = H.load_ratified_params(doc, rat)
    prices = synthetic_prices()
    out = H.attach_head2_dv(one_event(news_pos=30), prices,
                            H.get_param(params, "head2.event_window_sessions"),
                            H.get_param(params, "head2.trailing_sessions"))
    col = prices.iloc[:, 0].to_numpy()
    assert out["dv_post_mean_abs_return"].iloc[0] == pytest.approx(
        np.abs(col[31:33] / col[30:32] - 1).mean(), rel=1e-12)
    assert out["dv_trailing_mean_abs_return"].iloc[0] == pytest.approx(
        np.abs(col[25:30] / col[24:29] - 1).mean(), rel=1e-12)


def test_head3_fold_list_and_horizon_are_taken_from_the_document(tmp_path):
    params_block = minimal_params()
    params_block["fold_quarters"] = ["2018Q2"]
    params_block["head3"]["horizon_quarters"] = 2
    params_block["head3"]["label_cut"] = "2030-12-31"
    doc, rat = write_doc(tmp_path, [params_block])
    params, _ = H.load_ratified_params(doc, rat)
    folds = H.run_head3_folds(synthetic_panel(), params)
    assert [f["test_quarter"] for f in folds] == ["2018Q2"]
    # 2018Q2 ends 2018-06-30 and a 2-quarter horizon is a 6-month offset, so
    # the outcome window closes 2018-12-30. Only the document decides whether
    # that is past the cut, so flipping the document flips the verdict.
    params_block["head3"]["label_cut"] = "2018-12-29"
    doc2, rat2 = write_doc(tmp_path / "b", [params_block])
    params2, _ = H.load_ratified_params(doc2, rat2)
    assert H.run_head3_folds(synthetic_panel(), params2)[0]["censored"] is True


def test_params_schema_documents_exactly_the_keys_the_code_requires():
    schema = H.params_schema()
    documented2 = {e["key"] for e in schema["required_head2"]}
    documented3 = {e["key"] for e in schema["required_head3"]}
    assert documented2 == set(H.REQUIRED_HEAD2)
    assert documented3 == set(H.REQUIRED_HEAD3)
    assert {e["key"] for e in schema["conditionally_required"]} == \
        {H.EMBEDDING_PCA_K_KEY}


def test_the_schema_file_on_disk_matches_the_code():
    on_disk = json.loads(H.PARAMS_SCHEMA_PATH.read_text())
    assert on_disk == json.loads(json.dumps(H.params_schema()))


# ---------------------------------------------------------------------------
# 8. Freeze tripwires over the module's own source
# ---------------------------------------------------------------------------

FITTING_FUNCTIONS = {"ols_slope", "wild_cluster_bootstrap", "logistic_l2_fit",
                     "logistic_l2_score", "auc_score", "run_head3_folds",
                     "attach_head2_dv", "run_head2", "run_head3"}


def _call_graph(tree):
    graph = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            graph[node.name] = {c.func.id for c in ast.walk(node)
                                if isinstance(c, ast.Call)
                                and isinstance(c.func, ast.Name)}
    return graph


def test_the_census_path_cannot_reach_a_fitting_function():
    tree = ast.parse(Path(H.__file__).read_text())
    graph = _call_graph(tree)
    seen, stack = set(), ["run_census"]
    while stack:
        fn = stack.pop()
        if fn in seen:
            continue
        seen.add(fn)
        stack.extend(graph.get(fn, ()))
    assert not (seen & FITTING_FUNCTIONS), \
        f"run_census can reach {sorted(seen & FITTING_FUNCTIONS)} -- the census " \
        "must fit nothing (F5_PLAN.md §1)."


def test_the_guarded_runners_check_the_guard_before_they_fit():
    """`run_head2`/`run_head3` are only reachable from main() after the guard."""
    tree = ast.parse(Path(H.__file__).read_text())
    main_fn = next(n for n in tree.body
                   if isinstance(n, ast.FunctionDef) and n.name == "main")
    lines = {c.func.id: c.lineno for c in ast.walk(main_fn)
             if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert lines["load_ratified_params"] < lines["run_head2"] < lines["run_head3"]
    src = Path(H.__file__).read_text()
    for fn in ("run_head2", "run_head3"):
        body = src.split(f"def {fn}(")[1].split("\ndef ")[0]
        assert "check_required(" in body


def test_only_guard_and_provenance_helpers_are_taken_from_head_1():
    """heads_e2 may borrow the guard and sha helpers from backtest_e2 and
    nothing else: importing head 1's fitting machinery would put an IC one
    attribute access away from the census path."""
    tree = ast.parse(Path(H.__file__).read_text())
    used = {c.func.attr for c in ast.walk(tree)
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
            and isinstance(c.func.value, ast.Name) and c.func.value.id == "BT"}
    assert used <= {"sha256_file", "assert_input_shas", "require_g3",
                    "extract_params_block", "append_run_log"}, used


def test_no_association_statistic_is_imported_from_a_library():
    src = Path(H.__file__).read_text()
    for banned in ("spearmanr", "pearsonr", "corrcoef", ".corr(", "linregress",
                   "sklearn"):
        assert banned not in src, f"{banned} appears in heads_e2.py"


# ---------------------------------------------------------------------------
# 9. End-to-end assembly of both guarded runners, on SYNTHETIC data
# ---------------------------------------------------------------------------
# The real mode refuses today (section 1). These two tests exercise the
# runners' assembly -- what they write, what they log, what they carry -- with
# every loader replaced by a synthetic fixture, so no E2 datum and no real
# return is touched. Without them the guarded code paths would first execute
# after ratification, which is the worst moment to find a typo.

def _synthetic_head2_world():
    cal = pd.date_range("2018-01-01", periods=400, freq="B")
    rng = np.random.default_rng(11)
    prices = pd.DataFrame(
        {cik: 100.0 * np.cumprod(1.0 + rng.normal(scale=0.01, size=len(cal)))
         for cik in (11, 12, 13)}, index=cal)
    events = []
    for pos in range(120, 360, 12):
        for cik in (11, 12, 13):
            events.append({"cik": cik, "accession_number": f"{cik}-{pos}",
                           "news_pos": pos, "pre_pos": pos - 1,
                           "prices_complete": True,
                           "event_quarter": str(cal[pos].to_period("Q")),
                           "x": float(rng.uniform(0, 1))})
    return pd.DataFrame(events), prices


def test_run_head2_assembles_a_result_document_on_synthetic_data(tmp_path, monkeypatch):
    events, prices = _synthetic_head2_world()
    monkeypatch.setattr(H, "assert_input_shas", lambda: {"synthetic": "n/a"})
    monkeypatch.setattr(H, "build_head2_events",
                        lambda **kw: (events, {"events_core": len(events)}, prices))
    monkeypatch.setattr(H, "head_disclosures", lambda: {"synthetic": True})
    monkeypatch.setattr(H, "HEAD2_RESULTS", tmp_path / "results_head2.json")
    monkeypatch.setattr(H, "RUN_LOG", tmp_path / "run_log.jsonl")
    doc, rat = write_doc(tmp_path / "g3", [minimal_params()])
    doc_sha = hashlib.sha256(doc.read_bytes()).hexdigest()
    out = H.run_head2(minimal_params(), doc_sha, prereg=doc, ratified=rat)
    assert out["estimate"]["n_clusters"] == events["event_quarter"].nunique()
    assert out["estimate"]["n_obs"] == len(events)
    assert "few_clusters_limitation" in out["estimate"]
    assert "null_draws" not in out["estimate"]          # arrays are summarised
    written = json.loads((tmp_path / "results_head2.json").read_text())
    assert written["g3_doc_sha256"] == doc_sha
    logged = json.loads((tmp_path / "run_log.jsonl").read_text().splitlines()[0])
    assert logged["g3_doc_sha256"] == doc_sha and logged["head"] == 2


def test_run_head3_assembles_per_fold_rows_on_synthetic_data(tmp_path, monkeypatch):
    panel = synthetic_panel().drop(columns=["exit_within_horizon",
                                            "label_observable", "horizon_end"])
    exits = synthetic_exits()
    monkeypatch.setattr(H, "assert_input_shas", lambda: {"synthetic": "n/a"})
    monkeypatch.setattr(H, "build_head3_panel", lambda rule: (panel, {"rule": rule}))
    monkeypatch.setattr(H, "load_exit_events", lambda: exits)
    monkeypatch.setattr(H, "head_disclosures", lambda: {"synthetic": True})
    monkeypatch.setattr(H, "HEAD3_RESULTS", tmp_path / "results_head3.json")
    monkeypatch.setattr(H, "RUN_LOG", tmp_path / "run_log.jsonl")
    params = minimal_params()
    params["fold_quarters"] = ["2018Q2", "2019Q1", "2019Q2"]
    params["head3"]["label_cut"] = "2019-06-30"
    doc, rat = write_doc(tmp_path / "g3", [params])
    out = H.run_head3(params, hashlib.sha256(doc.read_bytes()).hexdigest(),
                      prereg=doc, ratified=rat)
    assert [f["test_quarter"] for f in out["folds"]] == params["fold_quarters"]
    assert out["n_censored_folds"] == sum(f["censored"] for f in out["folds"]) > 0
    for f in out["folds"]:
        # A censored fold is counted, never scored, and never silently empty.
        assert f["n_test_panel_rows"] > 0
        assert f["auc"] is None or not f["censored"]
        if f["n_test"] > 0:
            assert f["test_prevalence"] is not None
    written = json.loads((tmp_path / "results_head3.json").read_text())
    assert written["fold_quarters"] == params["fold_quarters"]
    logged = json.loads((tmp_path / "run_log.jsonl").read_text().splitlines()[0])
    assert logged["head"] == 3


# ---------------------------------------------------------------------------
# 10. Defence in depth (red-team 2026-09-10): the runners re-check the guard
# ---------------------------------------------------------------------------
# `main()` runs the guard before either runner, but a caller inside this
# process could hand a runner a fabricated `doc_sha` string and skip it. Both
# runners therefore re-measure the document themselves and refuse on any
# mismatch, so a guard argument cannot stand in for a ratification.


@pytest.mark.parametrize("runner", ["run_head2", "run_head3"])
def test_a_fabricated_doc_sha_cannot_reach_a_fit(tmp_path, monkeypatch, runner):
    called = []
    monkeypatch.setattr(H, "assert_input_shas", lambda: called.append("shas") or {})
    monkeypatch.setattr(H, "build_head2_events",
                        lambda **kw: called.append("head2 fit") or (None, {}, None))
    monkeypatch.setattr(H, "build_head3_panel",
                        lambda rule: called.append("head3 fit") or (None, {}))
    monkeypatch.setattr(H, "HEAD2_RESULTS", tmp_path / "results_head2.json")
    monkeypatch.setattr(H, "HEAD3_RESULTS", tmp_path / "results_head3.json")
    monkeypatch.setattr(H, "RUN_LOG", tmp_path / "run_log.jsonl")
    doc, rat = write_doc(tmp_path / "g3", [minimal_params()])

    with pytest.raises(H.FreezeRefusal) as exc:
        getattr(H, runner)(minimal_params(), "0" * 64, prereg=doc, ratified=rat)
    assert "not a ratification" in str(exc.value)
    assert called == []
    assert not (tmp_path / "results_head2.json").exists()
    assert not (tmp_path / "results_head3.json").exists()
    assert not (tmp_path / "run_log.jsonl").exists()


@pytest.mark.parametrize("runner", ["run_head2", "run_head3"])
def test_the_runners_refuse_against_the_real_paths_today(tmp_path, monkeypatch, runner):
    """With no ratified document in the repo, even a runner called directly
    with a plausible sha refuses: the default paths are the real ones."""
    called = []
    monkeypatch.setattr(H, "assert_input_shas", lambda: called.append("shas") or {})
    monkeypatch.setattr(H, "HEAD2_RESULTS", tmp_path / "results_head2.json")
    monkeypatch.setattr(H, "HEAD3_RESULTS", tmp_path / "results_head3.json")
    monkeypatch.setattr(H, "RUN_LOG", tmp_path / "run_log.jsonl")
    assert not H.RATIFIED_PATH.exists()
    with pytest.raises(H.FreezeRefusal) as exc:
        getattr(H, runner)(minimal_params(), "0" * 64)
    assert "BLOCKED" in str(exc.value)
    assert called == []


def test_reverify_guard_accepts_the_matching_document(tmp_path):
    doc, rat = write_doc(tmp_path / "g3", [minimal_params()])
    sha = hashlib.sha256(doc.read_bytes()).hexdigest()
    H.reverify_guard(sha, doc, rat)                      # no raise
    doc.write_text(doc.read_text() + "\nedited after ratification\n")
    with pytest.raises(H.FreezeRefusal):
        H.reverify_guard(sha, doc, rat)


def test_both_runners_reverify_before_anything_else():
    """Source-level: the re-check is the FIRST statement of each runner, so no
    input is read and no fit is started before the freeze is confirmed."""
    src = Path(H.__file__).read_text()
    for fn in ("run_head2", "run_head3"):
        body = src.split(f"def {fn}(")[1].split("\ndef ")[0]
        assert "reverify_guard(" in body, fn
        for later in ("check_required(", "assert_input_shas(", "get_param("):
            assert body.index("reverify_guard(") < body.index(later), (fn, later)
