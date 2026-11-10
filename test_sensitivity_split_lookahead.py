"""Tests for data/f5/sensitivity_split_lookahead.py (the post-hoc split arm, HANDOFF §3
2026-11-10). Synthetic and fast, no fit; the NVDA direction checks read the real cached
Yahoo payload / numeric features and skip if absent."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "sensitivity_split_lookahead", ROOT / "data" / "f5" / "sensitivity_split_lookahead.py")
SL = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(SL)

NVDA_PAYLOAD = ROOT / "data" / "raw" / "prices" / "yahoo" / "NVDA.json"
NVDA_CIK = 1045810


def _payload(splits):
    events = {str(d): {"date": d, "numerator": n, "denominator": m, "splitRatio": f"{n:g}:{m:g}"}
              for d, n, m in splits}
    return {"chart": {"result": [{"events": {"splits": events}}]}}


def _epoch(day):  # 09:30 New York on `day`, as Yahoo dates split events
    return int(pd.Timestamp(f"{day} 09:30", tz="America/New_York").timestamp())


@pytest.mark.parametrize("text,ratio", [("10:1", 10.0), ("3:2", 1.5), ("1998:1000", 1.998),
                                        ("1:10", 0.1), ("2.0:1.0", 2.0)])
def test_parse_split_ratio(text, ratio):
    assert SL.parse_split_ratio(text) == pytest.approx(ratio)


@pytest.mark.parametrize("bad", ["10", "0:1", "1:0", "a:b"])
def test_parse_split_ratio_refuses_garbage(bad):
    with pytest.raises(ValueError):
        SL.parse_split_ratio(bad)


def test_split_ratio_disagreeing_with_numerator_refuses():
    p = _payload([(_epoch("2020-08-31"), 4.0, 1.0)])
    next(iter(p["chart"]["result"][0]["events"]["splits"].values()))["splitRatio"] = "5:1"
    with pytest.raises(ValueError):
        SL.splits_from_payload(p)


def test_factor_strictly_after_the_pre_session():
    splits = SL.splits_from_payload(_payload([(_epoch("2020-08-31"), 4.0, 1.0)]))
    assert splits[0][0] == pd.Timestamp("2020-08-31")
    assert SL.split_factor(splits, "2020-08-28") == 4.0   # before: the close was adjusted
    assert SL.split_factor(splits, "2020-08-31") == 1.0   # on the effective day: already post-split
    assert SL.split_factor(splits, "2020-09-01") == 1.0   # after


def test_factor_is_the_product_of_every_later_split():
    splits = SL.splits_from_payload(_payload([(_epoch("2022-06-01"), 10.0, 1.0),
                                              (_epoch("2021-07-20"), 4.0, 1.0)]))
    assert [d for d, _ in splits] == [pd.Timestamp("2021-07-20"), pd.Timestamp("2022-06-01")]
    assert SL.split_factor(splits, "2021-07-19") == 40.0
    assert SL.split_factor(splits, "2021-07-20") == 10.0
    assert SL.split_factor(splits, "2022-05-31") == 10.0
    assert SL.split_factor(splits, "2022-06-01") == 1.0
    assert SL.split_factor(None, "2022-06-01") == 1.0


def test_reverse_split_factor_below_one():
    splits = SL.splits_from_payload(_payload([(_epoch("2023-03-01"), 1.0, 10.0)]))
    assert SL.split_factor(splits, "2023-02-28") == pytest.approx(0.1)


def test_corrected_value_is_stored_divided_by_factor():
    stored = pd.Series([0.5, 0.2, np.nan])
    out = SL.corrected_book_to_market(stored, np.array([10.0, 1.0, 4.0]))
    assert out.iloc[0] == pytest.approx(0.05) and out.iloc[1] == 0.2 and np.isnan(out.iloc[2])


def test_tickers_without_events_or_payload_get_factor_one_and_are_named(tmp_path):
    (tmp_path / "AAA.json").write_text(json.dumps(_payload([(_epoch("2021-01-04"), 2.0, 1.0)])))
    (tmp_path / "BBB.json").write_text(json.dumps({"chart": {"result": [{"meta": {}}]}}))
    (tmp_path / "DDD.json").write_text(json.dumps({"chart": {"result": [{"events": {"dividends": {}}}]}}))
    numeric = pd.DataFrame({"cik": [1, 2, 3, 4, 5],
                            "pre_session": pd.to_datetime(["2020-12-31"] * 5)})
    factors, diag, _ = SL.split_factors(numeric, {1: "AAA", 2: "BBB", 3: "CCC", 4: "DDD"}, tmp_path)
    assert factors.tolist() == [2.0, 1.0, 1.0, 1.0, 1.0]
    assert diag["tickers_no_events_block"] == ["BBB", "DDD"]
    assert diag["n_tickers_no_events_block"] == 2
    assert diag["tickers_no_payload"] == ["CCC"]
    assert diag["ciks_without_ticker"] == [5]


def test_arm_a_drops_book_to_market_from_both_fitted_blocks_only():
    blocks = {"numeric_only": ["log_total_assets", "book_to_market", "momentum_126"],
              "text_and_numeric": ["log_total_assets", "book_to_market", "sentiment_mean_score"],
              "text_and_numeric_exploratory": ["book_to_market", "redflag_x"],
              "size_only": ["log_total_assets"]}
    before = json.dumps(blocks, sort_keys=True)
    a = SL.blocks_without_bm(blocks)
    assert "book_to_market" not in a["numeric_only"] + a["text_and_numeric"]
    assert a["numeric_only"] == ["log_total_assets", "momentum_126"]
    assert a["size_only"] == ["log_total_assets"]
    assert json.dumps(blocks, sort_keys=True) == before  # the ratified lists are untouched


def test_arm_a_on_the_ratified_column_list():
    params = json.loads((ROOT / "data" / "f5" / "results_head1.json").read_text())["params"] \
        if (ROOT / "data" / "f5" / "results_head1.json").exists() else None
    if params is None:
        pytest.skip("results_head1.json absent")
    cols = params["columns"]
    frame = pd.DataFrame(columns=sorted(set(cols["numeric"] + cols["confirmatory_text"]
                                            + cols["family_novelty"] + cols["exploratory_red_flags"]
                                            + cols["exploratory_novelty_seq"])))
    blocks = SL.BE._blocks_from_params(params, frame)
    a = SL.blocks_without_bm(blocks)
    assert "book_to_market" in blocks["numeric_only"] and "book_to_market" in blocks["text_and_numeric"]
    assert a["numeric_only"] == [c for c in cols["numeric"] if c != "book_to_market"]
    assert len(a["text_and_numeric"]) == len(blocks["text_and_numeric"]) - 1
    assert SL.BE._blocks_from_params(params, frame) == blocks


def test_calls_changed_counts_per_block_and_refuses_a_different_row_set():
    base = pd.DataFrame({"block": ["numeric_only", "numeric_only", "size_only"],
                         "test_quarter": ["2018Q1"] * 3, "cik": [1, 2, 1],
                         "accession_number": ["a", "b", "a"],
                         "call": ["outperform peers", "no call", "no call"]})
    arm = base.assign(call=["underperform peers", "no call", "no call"])
    assert SL.calls_changed(arm, base) == {"text_and_numeric": 0, "numeric_only": 1, "size_only": 0}
    with pytest.raises(AssertionError):
        SL.calls_changed(arm.iloc[:2], base)


def test_rule5_fields_are_mechanical():
    r = SL.rule5(0.0011 + 0.019, 0.0011, 0.0096)
    assert r["two_seed_band_sd"] == pytest.approx(0.0192)
    assert r["abs_move_at_most_two_seed_band_sd"] is True
    assert r["arm_delta_outside_plus_minus_margin"] is False
    r = SL.rule5(-0.05, 0.0011, 0.0096)
    assert r["abs_move_at_most_two_seed_band_sd"] is False
    assert r["arm_delta_outside_plus_minus_margin"] is True


def test_private_file_is_git_ignored():
    out = subprocess.run(["git", "check-ignore", "-q", str(SL.PRIVATE_PATH)], cwd=ROOT)
    assert out.returncode == 0
    out = subprocess.run(["git", "check-ignore", "-q", str(SL.OUT_PATH)], cwd=ROOT)
    assert out.returncode == 1  # the universe-level JSON is tracked


# --- real direction check (rule 1): NVDA 10:1 effective 2024-06-10 -----------------

@pytest.mark.skipif(not NVDA_PAYLOAD.exists(), reason="cached NVDA Yahoo payload absent")
def test_nvda_real_payload_direction():
    splits = SL.splits_from_payload(json.loads(NVDA_PAYLOAD.read_text()))
    assert (pd.Timestamp("2024-06-10"), 10.0) in splits
    assert SL.split_factor(splits, "2024-06-07") == 10.0  # filed before it: B/M divided by 10
    assert SL.split_factor(splits, "2024-06-10") == 1.0
    assert SL.split_factor(splits, "2021-07-19") == 40.0  # 4:1 on 2021-07-20 as well


@pytest.mark.skipif(not (NVDA_PAYLOAD.exists() and SL.BE.NUMERIC_PATH.exists()),
                    reason="real NVDA payload or numeric features absent")
def test_nvda_corrected_feature_is_continuous_across_the_2024_split():
    """10:1 effective 2024-06-10. The stored value drops ~10x at the first filing reporting
    the post-split share count (2024-08-28); once the pre-split rows are divided by 10 the
    last pre-split row and that filing agree. A filing in between (2024-07-02: pre-split
    count, post-split close) keeps factor 1 -- rule 1 un-adjusts the close only."""
    nf = pd.read_parquet(SL.BE.NUMERIC_PATH, columns=["cik", "filing_date", "pre_session",
                                                      "book_to_market"])
    nf["pre_session"] = pd.to_datetime(nf["pre_session"])
    nf = nf[(nf.cik == NVDA_CIK) & nf.book_to_market.notna()
            & nf.pre_session.isin(pd.to_datetime(["2024-06-07", "2024-07-02", "2024-08-28"]))]
    nf = nf.drop_duplicates("pre_session").sort_values("pre_session").reset_index(drop=True)
    assert len(nf) == 3
    factors, _, _ = SL.split_factors(nf, {NVDA_CIK: "NVDA"})
    assert factors.tolist() == [10.0, 1.0, 1.0]
    stored = nf.book_to_market
    corrected = SL.corrected_book_to_market(stored, factors)
    assert stored.iloc[2] / stored.iloc[0] < 0.2                      # the defect: a ~10x drop
    assert 0.5 < corrected.iloc[2] / corrected.iloc[0] < 2.0          # gone once corrected
    assert corrected.iloc[1] == stored.iloc[1]                        # the in-between filing


def test_last_split_on_or_before():
    splits = SL.splits_from_payload(_payload([(_epoch("2024-06-10"), 10.0, 1.0)]))
    assert SL.last_split_on_or_before(splits, "2024-06-09") is None
    assert SL.last_split_on_or_before(splits, "2024-07-02") == {
        "effective": "2024-06-10", "ratio": 10.0, "days_before_event": 22}


# --- rule 6: the seed-matched mode (synthetic) ---------------------------------------

def test_matched_stats():
    m = SL.matched_stats([0.01, -0.02, 0.03, 0.02])
    x = np.array([0.01, -0.02, 0.03, 0.02])
    assert m["n_seeds"] == 4 and m["mean"] == pytest.approx(x.mean())
    assert m["sd"] == pytest.approx(x.std(ddof=1))
    assert m["se"] == pytest.approx(x.std(ddof=1) / 2.0)
    assert m["share_positive"] == 0.75


def test_matched_stats_zero_is_not_positive():
    assert SL.matched_stats([0.0, 0.0, 1.0])["share_positive"] == pytest.approx(1 / 3)


def test_percentile_in_band():
    band = [0.0, 0.1, 0.2, 0.3]
    assert SL.percentile_in_band(-1.0, band) == 0.0
    assert SL.percentile_in_band(0.15, band) == 50.0
    assert SL.percentile_in_band(0.1, band) == pytest.approx(37.5)  # ties count half
    assert SL.percentile_in_band(9.0, band) == 100.0


def test_churn_summary_and_call_count():
    assert SL.churn_summary([5, 1, 9, 3]) == {"min": 1, "median": 4.0, "max": 9}
    ratified = pd.DataFrame({"block": ["numeric_only"] * 3 + ["text_and_numeric"] * 3,
                             "test_quarter": ["2018Q1"] * 6, "cik": [1, 2, 3] * 2,
                             "accession_number": ["a", "b", "c"] * 2,
                             "call": ["no call", "outperform peers", "underperform peers"] * 2})
    seed_s = ratified.assign(call=["no call", "underperform peers", "outperform peers",
                                   "no call", "outperform peers", "underperform peers"])
    assert SL.calls_changed(seed_s, ratified) == {"text_and_numeric": 0, "numeric_only": 2,
                                                  "size_only": 0}


def test_seed_gate_refuses_a_mismatched_or_missing_seed():
    recorded = [{"seed": 1, "mean_fold_delta_dedup": 0.012}, {"seed": 2, "mean_fold_delta_dedup": -0.003}]
    assert SL.seed_gate({1: 0.012, 2: -0.003}, recorded) == []
    bad = SL.seed_gate({1: 0.012, 2: np.nextafter(-0.003, 0.0)}, recorded)  # one ulp off
    assert len(bad) == 1 and bad[0].startswith("seed 2")
    assert len(SL.seed_gate({1: 0.012}, recorded)) == 1          # seed 2 missing
    assert len(SL.seed_gate({1: 0.012, 2: -0.003, 3: 0.0}, recorded)) == 1  # extra seed


def test_seed_band_mean_is_backtest_e2_seed_band_arithmetic():
    d = [0.1, np.nan, -0.05, 0.02]
    x = np.asarray([v for v in d if np.isfinite(v)], dtype=float)
    assert SL.seed_band_mean(d) == float(x.mean())


def test_cache_is_used_only_under_the_same_fingerprint(tmp_path):
    p = tmp_path / "seed_001.json"
    assert SL.load_cached(p, "abc") is None
    SL.save_cached(p, {"seed": 1, "fingerprint": "abc"})
    assert SL.load_cached(p, "abc")["seed"] == 1
    assert SL.load_cached(p, "other") is None


def test_factor_reach_splits_large_and_small_factors():
    rows = pd.DataFrame({"cik": [1, 1, 2, 3, 4], "accession_number": ["a", "b", "c", "d", "e"]})
    fac = pd.DataFrame({"cik": [1, 1, 2, 3, 4], "accession_number": ["a", "b", "c", "d", "e"],
                        "factor": [10.0, 1.0, 1.05, 0.1, 1.0],
                        "has_bm": [True, True, False, True, True]})
    r = SL.factor_reach(rows, fac)
    assert r["n_scored_dedup_rows"] == 5
    assert r["factor_not_1"] == {"n_rows": 3, "n_companies": 3}
    assert r["factor_ge_1.8_or_le_1/1.8"] == {"n_rows": 2, "n_companies": 2}
    assert r["factor_other_not_1"] == {"n_rows": 1, "n_companies": 1}
    assert r["factor_not_1_with_book_to_market"] == {"n_rows": 2, "n_companies": 2}


def test_assemble_seed_band_shapes_and_seed0_percentile():
    def arm(delta, ic_n, ic_t, churn):
        return {"mean_fold_delta_dedup": delta,
                "mean_fold_dedup_ic": {"numeric_only": ic_n, "text_and_numeric": ic_t},
                "universe_calls": {b: {"n_calls": 10, "n_correct": 5, "hit_rate": 0.5}
                                   for b in SL.SCORECARD_BLOCKS},
                "n_dedup_rows_call_differs_from_ratified_seed0": {"numeric_only": churn,
                                                                   "text_and_numeric": churn},
                "margin_procedure": {"status": "POWERED", "equivalence": True, "ci_lo": -0.01}}
    recs = [{"seed": s, "primary": arm(0.01 * s, 0.02, 0.03, 100 + s),
             "arm_a": arm(0.01 * s + 0.002, 0.01, 0.02, 200), "arm_b": arm(0.01 * s - 0.001, 0.0, 0.03, 300)}
            for s in (1, 2, 3)]
    head1 = {"margin": {"mean_fold_delta": 0.01 * 2}}  # ties the middle seed
    seed0 = {"ratified": {"mean_fold_dedup_ic": {"numeric_only": 0.02, "text_and_numeric": 0.03}},
             "arm_a_book_to_market_removed": {"mean_fold_delta_dedup": 0.5,
                                              "mean_fold_dedup_ic": {"numeric_only": 0, "text_and_numeric": 0}},
             "arm_b_book_to_market_as_printed": {"mean_fold_delta_dedup": -0.5,
                                                 "mean_fold_dedup_ic": {"numeric_only": 0, "text_and_numeric": 0}}}
    out = SL.assemble_seed_band(recs, head1, seed0)
    m = out["seed_matched_arm_minus_primary"]
    assert m["arm_a"]["delta"]["mean"] == pytest.approx(0.002) and m["arm_a"]["delta"]["share_positive"] == 1.0
    assert m["arm_b"]["delta"]["mean"] == pytest.approx(-0.001) and m["arm_b"]["delta"]["share_positive"] == 0.0
    assert m["arm_a"]["ic_numeric_only"]["mean"] == pytest.approx(-0.01)
    assert out["seed0_in_band"]["primary"]["delta"]["percentile"] == 50.0
    assert out["seed0_in_band"]["arm_a"]["delta"]["percentile"] == 100.0
    assert out["seed0_in_band"]["arm_b"]["delta"]["percentile"] == 0.0
    assert out["calls_differing_from_ratified_seed0"]["primary"]["numeric_only"] == \
        {"min": 101, "median": 102.0, "max": 103}
    assert out["margin_procedure_per_seed"]["arm_a"] == {"n_seeds": 3, "n_equivalent": 3,
                                                        "n_unpowered": 0, "n_ci_lo_above_0": 0}
    assert out["universe_calls_band_mean"]["arm_b"]["size_only"]["hit_rate"] == 0.5


def test_seed_cache_is_git_ignored_and_seed_artifact_is_not():
    p = SL.SEEDS_CACHE_DIR / "seed_001.json"
    assert subprocess.run(["git", "check-ignore", "-q", str(p)], cwd=ROOT).returncode == 0
    assert subprocess.run(["git", "check-ignore", "-q", str(SL.SEEDS_OUT_PATH)], cwd=ROOT).returncode == 1


def test_margin_procedure_is_the_unchanged_backtest_e2_function():
    assert SL.BE.margin_procedure.__module__ == "backtest_e2"
