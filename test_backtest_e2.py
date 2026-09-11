"""
test_backtest_e2.py -- tests for the E2 head-1 runner.

EVERY test here runs on SYNTHETIC frames built in-process (or on `tmp_path`).
No test reads a `data/f5` parquet, a real return, a real price or a real
filing, and no test fits a model on E2 data -- that is the F5_PLAN §1 freeze,
and these tests are part of how it is enforced rather than merely described.

What is pinned here:
  * the freeze guard refuses without `G3_RATIFIED.json` and on a sha mismatch;
  * every parameter comes from the document's fenced block, not from code;
  * the purge rule, and its calendar-start == first-session equivalence;
  * the fold builder (expanding, ratified quarters only, no leakage);
  * the embedding PCA is fit on TRAINING rows only (perturbing test rows
    cannot move a training row's components);
  * the margin block is written before any per-fold delta -- structurally;
  * the ladder, including the UNPOWERED branch, and TOST;
  * company-quarter dedup on the CIK key, and the train-overlap split;
  * an end-to-end `--selftest` run.
"""

from __future__ import annotations

import ast
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import backtest as B
import backtest_e2 as E
import spec as S


# ---------------------------------------------------------------------------
# fixtures -- synthetic only
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def synth():
    tgt, txt, num, fam = E.synthetic_frames(seed=7, n_ciks=12, n_quarters=10, emb_dim=6)
    frame, diag = E.join_frames(tgt, txt, num, fam)
    return frame, diag


@pytest.fixture(scope="module")
def synth_params(synth):
    frame, _ = synth
    return E.selftest_params(frame)


def _write_doc(tmp_path: Path, params: dict, body: str = "") -> tuple[Path, Path]:
    doc, rat = E.write_synthetic_g3(tmp_path, params)
    if body:
        doc.write_text(doc.read_text() + body)
        rat.write_text(json.dumps({"doc_sha256": E.sha256_file(doc)}) + "\n")
    return doc, rat


# ---------------------------------------------------------------------------
# 1. The freeze guard
# ---------------------------------------------------------------------------


def test_guard_refuses_when_ratification_file_absent(tmp_path):
    with pytest.raises(E.G3Refusal) as exc:
        E.require_g3(tmp_path / "G3_PREREGISTRATION.md", tmp_path / "G3_RATIFIED.json")
    assert "BLOCKED" in str(exc.value)


def test_guard_refuses_when_document_absent_but_ratification_present(tmp_path):
    (tmp_path / "G3_RATIFIED.json").write_text(json.dumps({"doc_sha256": "0" * 64}))
    with pytest.raises(E.G3Refusal):
        E.require_g3(tmp_path / "G3_PREREGISTRATION.md", tmp_path / "G3_RATIFIED.json")


def test_guard_refuses_on_sha_mismatch(tmp_path, synth_params):
    doc, rat = _write_doc(tmp_path, synth_params)
    assert E.require_g3(doc, rat)["doc_sha256"] == E.sha256_file(doc)
    doc.write_text(doc.read_text() + "\nan edit made after ratification\n")
    with pytest.raises(E.G3Refusal) as exc:
        E.require_g3(doc, rat)
    assert "sha256" in str(exc.value)


def test_guard_refuses_when_ratification_pins_no_document(tmp_path, synth_params):
    doc, rat = _write_doc(tmp_path, synth_params)
    rat.write_text(json.dumps({"note": "signed but pins nothing"}))
    with pytest.raises(E.G3Refusal):
        E.require_g3(doc, rat)


def test_real_run_refuses_today(capsys):
    """The repo state this test runs in has no ratified document; `main()`
    must exit 2 without fitting anything."""
    assert not E.G3_RATIFIED_PATH.exists(), "a ratified G3 file appeared; this test must be re-read"
    assert E.main([]) == 2
    out = capsys.readouterr().out
    assert "BLOCKED" in out and "no IC was computed" in out


# ---------------------------------------------------------------------------
# 2. Parameters come from the document, never from code
# ---------------------------------------------------------------------------


def test_params_are_read_from_the_document_block(tmp_path, synth_params):
    custom = json.loads(json.dumps(synth_params))
    custom["margin"]["ladder"] = [0.017, 0.071]
    custom["spec"]["window_days"] = 123
    custom["seeds"]["primary"] = 5
    doc, rat = _write_doc(tmp_path, custom)
    params, guard = E.load_g3_params(doc, rat)
    assert params["margin"]["ladder"] == [0.017, 0.071]
    assert params["spec"]["window_days"] == 123
    assert params["seeds"]["primary"] == 5
    assert guard["params_sha256"] == E.sha256_obj(params)
    # ... and they are NOT the module's selftest fixture values
    assert params["margin"]["ladder"] != E.SELFTEST_PARAMS["margin"]["ladder"]


def test_selftest_params_are_referenced_only_by_the_selftest_path():
    """`SELFTEST_PARAMS` may not leak into the real run (F5_PLAN §1: hard-coded
    values only on the synthetic path)."""
    src = Path(E.__file__).read_text()
    lines = [l for l in src.splitlines() if "SELFTEST_PARAMS" in l and not l.strip().startswith("#")]
    for line in lines:
        assert (
            line.startswith("SELFTEST_PARAMS")
            or "json.loads(json.dumps(SELFTEST_PARAMS))" in line
            or "E.SELFTEST_PARAMS" in line
            or "`SELFTEST_PARAMS`" in line
            or "SELFTEST_PARAMS[" in line
        ), f"unexpected SELFTEST_PARAMS use: {line!r}"
    funcs = [l for l in src.splitlines() if l.startswith("def ") ]
    assert "def run_head1(" in "\n".join(funcs)
    body = src.split("def run_head1(")[1].split("\ndef ")[0]
    assert "SELFTEST_PARAMS" not in body


def test_missing_key_is_a_refusal(tmp_path, synth_params):
    bad = json.loads(json.dumps(synth_params))
    del bad["margin"]["power_divisor"]
    doc, rat = _write_doc(tmp_path, bad)
    with pytest.raises(E.G3Refusal) as exc:
        E.load_g3_params(doc, rat)
    assert "power_divisor" in str(exc.value)


def test_unimplemented_named_rule_is_a_refusal(tmp_path, synth_params):
    bad = json.loads(json.dumps(synth_params))
    bad["se"]["block_length_rule"] = "whatever_sounds_right"
    doc, rat = _write_doc(tmp_path, bad)
    with pytest.raises(E.G3Refusal) as exc:
        E.load_g3_params(doc, rat)
    assert "no implementation" in str(exc.value)


def test_two_params_blocks_is_a_refusal(tmp_path, synth_params):
    doc, rat = _write_doc(
        tmp_path,
        synth_params,
        body="\n```" + E.FENCE_INFO + "\n" + json.dumps(synth_params) + "\n```\n",
    )
    with pytest.raises(E.G3Refusal) as exc:
        E.load_g3_params(doc, rat)
    assert "exactly one" in str(exc.value)


def test_no_params_block_is_a_refusal(tmp_path):
    doc = tmp_path / "G3_PREREGISTRATION.md"
    doc.write_text("# a document with prose but no parameters\n")
    rat = tmp_path / "G3_RATIFIED.json"
    rat.write_text(json.dumps({"doc_sha256": E.sha256_file(doc)}))
    with pytest.raises(E.G3Refusal):
        E.load_g3_params(doc, rat)


def test_params_schema_file_lists_every_required_key(tmp_path):
    schema = E.write_params_schema(tmp_path / "G3_PARAMS_SCHEMA.json")
    listed = {row["path"] for row in schema["required_keys"]}
    assert listed == {p for p, _ in E.REQUIRED_PARAMS}
    assert schema["implemented_named_rules"]["purge_rule"] == list(E.IMPLEMENTED_PURGE_RULES)


# ---------------------------------------------------------------------------
# 3. Frame, dedup, overlap split
# ---------------------------------------------------------------------------


def test_join_keeps_in_membership_rows_only_and_aliases_the_target():
    tgt, txt, num, fam = E.synthetic_frames(seed=1, n_ciks=4, n_quarters=4)
    tgt.loc[tgt.index[:6], "in_membership"] = False
    frame, diag = E.join_frames(tgt, txt, num, fam)
    assert diag["n_target_in_membership"] == len(tgt) - 6
    assert len(frame) == diag["n_modeling_rows"]
    assert frame[B.TARGET_COL].equals(frame[E.E2_TARGET_COL].astype(float))
    assert frame["filing_date"].is_monotonic_increasing


def test_dedup_mask_is_the_frozen_rule_wrapped_on_cik(synth):
    frame, _ = synth
    mask = E.dedup_keep_mask_cik(frame, B.COMPANY_QUARTER_DEDUP_GAP_DAYS)
    expected = B.company_quarter_dedup_keep_mask(
        frame.assign(ticker=frame[E.CIK_COL].astype(str)), gap_days=B.COMPANY_QUARTER_DEDUP_GAP_DAYS
    )
    assert mask.equals(expected.reindex(frame.index))
    # exactly one kept row per near-duplicate cluster (the frozen definition:
    # same company, consecutive filings within gap_days -- NOT "one per
    # calendar quarter", which the frozen rule deliberately does not assume)
    clusters = B.assign_company_quarter_clusters(
        frame.assign(ticker=frame[E.CIK_COL].astype(str)), gap_days=B.COMPANY_QUARTER_DEDUP_GAP_DAYS
    )
    assert int(mask.sum()) == int(clusters.nunique())
    assert int(mask.sum()) < len(frame)
    for cid, sub in frame.groupby(clusters.values):
        kept_row = sub[mask.reindex(sub.index).values]
        assert len(kept_row) == 1
        assert kept_row["filing_date"].iloc[0] == sub["filing_date"].max()
        assert sub[E.CIK_COL].nunique() == 1


def test_overlap_split_excludes_only_overlapping_rows(synth):
    frame, _ = synth
    folds, _ = E.build_folds(frame, sorted(str(q) for q in frame["filing_date"].dt.to_period("Q").unique())[4:])
    keep = E.dedup_keep_mask_cik(frame, 5).values.astype(bool)
    fold = folds[0]
    masks = E.eval_masks_for_fold(frame, fold, keep, "train_overlap_share", 0.0)
    ov = frame.loc[fold["test_idx"], "train_overlap_share"].astype(float).values
    assert masks["dedup_no_overlap"].sum() <= masks["dedup"].sum()
    assert not (masks["dedup_no_overlap"] & (ov > 0)).any()
    assert (masks["dedup"] & ~masks["dedup_no_overlap"]).sum() == int(((ov > 0) & masks["dedup"]).sum())


# ---------------------------------------------------------------------------
# 4. Folds + purge
# ---------------------------------------------------------------------------


def test_folds_are_expanding_ratified_quarters_and_leakage_free(synth):
    frame, _ = synth
    quarters = sorted(str(q) for q in frame["filing_date"].dt.to_period("Q").unique())[4:8]
    folds, purge = E.build_folds(frame, quarters)
    assert [str(f["test_quarter"]) for f in folds] == quarters
    sizes = [len(f["train_idx"]) for f in folds]
    assert sizes == sorted(sizes), "training window must expand"
    for fold in folds:
        qstart = E.quarter_of(str(fold["test_quarter"])).start_time
        assert (frame.loc[fold["train_idx"], "filing_date"] < qstart).all()
        assert (frame.loc[fold["test_idx"], "filing_date"] >= qstart).all()
    B.assert_no_fold_leakage(frame, folds)
    assert all(r["n_purged"] >= 0 for r in purge)


def test_unratifiable_quarter_is_a_refusal(synth):
    frame, _ = synth
    with pytest.raises(E.G3Refusal) as exc:
        E.build_folds(frame, ["2099Q1"])
    assert "no usable fold" in str(exc.value)


def test_purge_drops_training_rows_whose_window_closes_inside_the_test_quarter():
    frame = _purge_fixture()
    folds, purge = E.build_folds(frame, ["2018Q1"])
    train = frame.loc[folds[0]["train_idx"]]
    assert (train["window_close_session"] < pd.Timestamp("2018-01-01")).all()
    assert purge[0]["n_purged"] == 2  # the two rows closing on/after the quarter start
    assert purge[0]["n_train_before_purge"] - purge[0]["n_train_after_purge"] == 2


def test_purge_calendar_start_equals_first_session():
    """`window_close_session` is always a trading session, so "closes on or
    after the test quarter's FIRST SESSION" and "closes on or after the
    quarter's first CALENDAR day" select the same training rows. 2018-01-01 is
    a holiday; the first session is 2018-01-02."""
    frame = _purge_fixture()
    folds, _ = E.build_folds(frame, ["2018Q1"])
    kept_calendar = set(frame.loc[folds[0]["train_idx"], "accession_number"])

    sessions = pd.DatetimeIndex(sorted(set(frame["window_close_session"]) | set(frame["news_session"])))
    first_session = sessions[sessions >= pd.Timestamp("2018-01-01")][0]
    assert first_session == pd.Timestamp("2018-01-02")
    train_all = frame[frame["filing_date"] < pd.Timestamp("2018-01-01")]
    kept_session = set(train_all[train_all["window_close_session"] < first_session]["accession_number"])
    assert kept_calendar == kept_session


def _purge_fixture() -> pd.DataFrame:
    """Four 2017 training filings (two closing in 2017, two closing inside
    2018Q1) plus two 2018Q1 test filings."""
    rows = []
    spec_rows = [
        ("A", "2017-06-01", "2017-09-05"),
        ("B", "2017-07-03", "2017-10-02"),
        ("C", "2017-11-01", "2018-01-02"),   # first session of the test quarter
        ("D", "2017-12-01", "2018-03-01"),
        ("E", "2018-01-16", "2018-04-16"),   # test rows
        ("F", "2018-02-16", "2018-05-16"),
    ]
    for i, (tag, fd, close) in enumerate(spec_rows):
        rows.append(
            {
                "cik": 1000 + (i % 3),
                "accession_number": tag,
                "form": "10-Q",
                "filing_date": pd.Timestamp(fd),
                "news_session": pd.Timestamp(fd),
                "window_close_session": pd.Timestamp(close),
                E.E2_TARGET_COL: 0.01 * (i + 1),
                B.TARGET_COL: 0.01 * (i + 1),
                "in_membership": True,
                "log_total_assets": 10.0 + i,
                "train_overlap_share": 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values("filing_date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# 5. The embedding PCA is fit on training rows only
# ---------------------------------------------------------------------------


def test_pca_is_fit_on_training_rows_only():
    rng = np.random.default_rng(3)
    emb = rng.normal(size=(60, 8))
    train_pos = np.arange(40)
    test_pos = np.arange(40, 60)
    base, info = E.pca_project(emb, train_pos, 3)
    assert info["k_effective"] == 3 and info["n_fit_rows"] == 40

    perturbed = emb.copy()
    perturbed[test_pos] += rng.normal(scale=50.0, size=(len(test_pos), 8))
    after, _ = E.pca_project(perturbed, train_pos, 3)
    # training rows' components are untouched: the loadings and the centering
    # mean saw only training rows.
    assert np.allclose(base[train_pos], after[train_pos], atol=1e-12)
    # and the test rows DID move, so the check is not vacuous
    assert not np.allclose(base[test_pos], after[test_pos])


def test_pca_marks_unusable_rows_nan_and_never_imputes():
    emb = np.random.default_rng(0).normal(size=(20, 5))
    emb[3] = np.nan
    comps, info = E.pca_project(emb, np.arange(15), 2)
    assert np.isnan(comps[3]).all()
    assert info["n_fit_rows"] == 14  # the NaN row is excluded from the fit


def test_fold_frames_carry_per_fold_components(synth):
    frame, _ = synth
    quarters = sorted(str(q) for q in frame["filing_date"].dt.to_period("Q").unique())[4:7]
    folds, _ = E.build_folds(frame, quarters)
    emb = E.embedding_matrix(frame)
    ffs = E.build_fold_frames(frame, folds, emb, 2, False, None)
    assert [len(f["emb_cols"]) for f in ffs] == [2, 2, 2]
    a = ffs[0]["frame"]["emb_pc1"].values
    b = ffs[1]["frame"]["emb_pc1"].values
    assert not np.allclose(a[np.isfinite(a) & np.isfinite(b)], b[np.isfinite(a) & np.isfinite(b)])
    blocks = E.blocks_for_fold({"numeric_only": ["x"], "text_and_numeric": ["x", "t"]}, ["emb_pc1"])
    assert blocks["numeric_only"] == ["x"], "the baseline never gets the embedding block"
    assert blocks["text_and_numeric"] == ["x", "t", "emb_pc1"]


# ---------------------------------------------------------------------------
# 6. Ordering: the margin block strictly precedes any per-fold delta
# ---------------------------------------------------------------------------


def test_delta_payload_cannot_be_written_before_the_margin_block():
    w = E.ResultsWriter()
    w.add_header("run", {"mode": "test"})
    with pytest.raises(E.OrderingViolation) as exc:
        w.add_delta_payload("per_fold_primary_delta_dedup", [{"delta": 0.1}])
    assert "margin" in str(exc.value)
    with pytest.raises(E.OrderingViolation):
        w.stdout_lines()
    with pytest.raises(E.OrderingViolation):
        w.document()


def test_margin_is_the_first_key_and_is_written_once(tmp_path):
    w = E.ResultsWriter()
    w.add_header("run", {"mode": "test"})
    w.set_margin(_margin_block(0.001))
    w.add_delta_payload("per_fold_primary_delta_dedup", [{"delta": 0.1}])
    doc = w.document()
    assert list(doc.keys())[0] == "margin"
    assert list(doc.keys()).index("margin") < list(doc.keys()).index("per_fold_primary_delta_dedup")
    with pytest.raises(E.OrderingViolation):
        w.set_margin(_margin_block(0.001))
    sha = w.to_json(tmp_path / "r.json")
    assert list(json.loads((tmp_path / "r.json").read_text()).keys())[0] == "margin"
    assert len(sha) == 64


def test_run_head1_results_put_margin_before_every_delta(tmp_path, synth, synth_params):
    frame, diag = synth
    doc_path, rat_path = _write_doc(tmp_path, synth_params)
    params, guard = E.load_g3_params(doc_path, rat_path)
    doc = E.run_head1(
        params, guard, frame, diag,
        tmp_path / "results.json", tmp_path / "report.md", tmp_path / "run_log.jsonl",
        doc_path=doc_path, ratified_path=rat_path,
    )
    keys = list(doc.keys())
    assert keys[0] == "margin"
    delta_keys = [i for i, k in enumerate(keys) if "delta" in k or k.startswith("per_fold")]
    assert min(delta_keys) > 0
    log = [json.loads(l) for l in (tmp_path / "run_log.jsonl").read_text().splitlines()]
    assert log[-1]["doc_sha256"] == guard["doc_sha256"]
    assert set(log[-1]) == {"utc", "doc_sha256", "params_sha256", "results_sha256"}


def _margin_block(se: float) -> dict:
    params = json.loads(json.dumps(E.SELFTEST_PARAMS))
    deltas = np.array([se * 2.487 * 0.5] * 6)
    block = E.margin_procedure(deltas, params)
    return block


# ---------------------------------------------------------------------------
# 7. The margin ladder (including UNPOWERED) and TOST
# ---------------------------------------------------------------------------


def _params_for_margin(**over) -> dict:
    p = json.loads(json.dumps(E.SELFTEST_PARAMS))
    p["se"]["n_resamples"] = 500
    p.update(over)
    return p


def test_ladder_selects_the_smallest_satisfying_margin():
    params = _params_for_margin()
    # A tight, near-constant set of fold deltas -> tiny SE -> the floor margin.
    deltas = np.array([0.0005, -0.0005, 0.0004, -0.0004, 0.0006, -0.0006, 0.0003, -0.0003])
    block = E.margin_procedure(deltas, params)
    assert block["status"] == "POWERED"
    assert block["delta_selected"] == 0.03
    assert block["se_block_bootstrap"] <= 0.03 / 2.487
    assert block["kc3_branch"] is False
    assert [r["margin"] for r in block["ladder_evaluation"]] == [0.03, 0.04, 0.05]


def test_ladder_climbs_and_flags_the_kc3_branch():
    params = _params_for_margin()
    rng = np.random.default_rng(0)
    # SE engineered to sit between 0.03/2.487 and 0.05/2.487.
    deltas = rng.normal(0.0, 0.055, size=12)
    block = E.margin_procedure(deltas, params)
    if block["status"] == "POWERED":
        assert block["delta_selected"] in (0.04, 0.05)
        assert block["kc3_branch"] is True
        assert block["implied_mde"] == pytest.approx(2.8 * block["se_block_bootstrap"])
    else:  # still a legitimate outcome for this SE; the branch must be honest
        assert block["delta_selected"] is None


def test_unpowered_when_no_ladder_value_satisfies_the_power_requirement():
    params = _params_for_margin()
    deltas = np.array([0.4, -0.5, 0.6, -0.7, 0.5, -0.4, 0.3, -0.6])
    block = E.margin_procedure(deltas, params)
    assert block["status"] == "UNPOWERED"
    assert block["delta_selected"] is None
    assert all(r["satisfied"] is False for r in block["ladder_evaluation"])
    assert block["tost"]["equivalence"] is None
    assert "no equivalence claim" in block["tost"]["note"]
    # the CI is published even when unpowered
    assert math.isfinite(block["tost"]["ci_lo"]) and math.isfinite(block["tost"]["ci_hi"])


def test_se_is_a_block_bootstrap_not_std_over_sqrt_k():
    params = _params_for_margin()
    deltas = np.array([0.02, 0.03, -0.01, 0.04, 0.00, 0.01, 0.05, -0.02])
    block = E.margin_procedure(deltas, params)
    naive = float(deltas.std(ddof=1) / np.sqrt(len(deltas)))
    assert block["se_std_over_sqrt_k_never_used_for_inference"] == pytest.approx(naive)
    assert block["se_block_bootstrap"] != pytest.approx(naive, rel=1e-9)
    assert math.isfinite(block["se_newey_west_alternative"])
    assert block["block_length_rule"] == "ceil_k13_ac1"


def test_block_length_follows_the_measured_autocorrelation():
    assert E.block_length(-0.4, 30, "ceil_k13_ac1") == 1
    assert E.block_length(0.0, 30, "ceil_k13_ac1") == 1
    assert E.block_length(0.6, 30, "ceil_k13_ac1") > 1
    assert E.block_length(0.9, 30, "ceil_k13_ac1") > E.block_length(0.6, 30, "ceil_k13_ac1")
    with pytest.raises(E.G3Refusal):
        E.block_length(0.5, 30, "an_unimplemented_rule")


def test_lag1_autocorrelation_is_measured_not_assumed():
    x = np.array([1.0, -1.0, 1.0, -1.0, 1.0, -1.0, 1.0, -1.0])
    assert E.lag1_autocorr(x) == pytest.approx(-0.875, abs=0.05)
    y = np.array([1.0, 1.0, 1.0, -1.0, -1.0, -1.0, 1.0, 1.0])
    assert E.lag1_autocorr(y) > 0


def test_tost_known_answers():
    # centred at zero with a small SE -> equivalence inside +/- 0.05
    eq = E.tost(0.0, 0.01, 0.05, 0.05, 0.90, "normal", 20)
    assert eq["equivalence"] is True and eq["p_tost"] < 0.05
    assert eq["ci_lo"] == pytest.approx(-1.6449 * 0.01, abs=1e-4)
    # a mean at the margin -> p = 0.5 on the upper test, never equivalent
    edge = E.tost(0.05, 0.01, 0.05, 0.05, 0.90, "normal", 20)
    assert edge["p_upper"] == pytest.approx(0.5, abs=1e-6)
    assert edge["equivalence"] is False
    # wide SE -> CI escapes the margin even at a zero mean
    wide = E.tost(0.0, 0.10, 0.05, 0.05, 0.90, "normal", 20)
    assert wide["equivalence"] is False
    assert wide["ci_hi"] > 0.05
    # the t reference is wider than the normal at the same SE
    tt = E.tost(0.0, 0.01, 0.05, 0.05, 0.90, "t", 6)
    assert tt["ci_hi"] > eq["ci_hi"]
    with pytest.raises(E.G3Refusal):
        E.tost(0.0, 0.01, 0.05, 0.05, 0.90, "bootstrap_percentile", 6)


# ---------------------------------------------------------------------------
# 8. Fitting helpers
# ---------------------------------------------------------------------------


def test_seeded_fit_matches_the_frozen_fit_at_the_frozen_seed(synth):
    frame, _ = synth
    cols = ["log_total_assets", "momentum_126", "realized_vol_63"]
    n = len(frame)
    train = np.arange(0, int(n * 0.7))
    test = np.arange(int(n * 0.7), n)
    frozen = B.fit_predict(frame, cols, train, test)
    wrapped_default = E.fit_predict_seeded(frame, cols, train, test, None)
    wrapped_same_seed = E.fit_predict_seeded(frame, cols, train, test, B.XGB_PARAMS["random_state"])
    assert np.array_equal(frozen, wrapped_default)
    assert np.array_equal(frozen, wrapped_same_seed)
    other = E.fit_predict_seeded(frame, cols, train, test, 12345)
    assert other.shape == frozen.shape


def test_zero_information_rows_use_cik_as_the_company_key(synth):
    frame, _ = synth
    quarters = sorted(str(q) for q in frame["filing_date"].dt.to_period("Q").unique())[4:7]
    folds, _ = E.build_folds(frame, quarters)
    keep = E.dedup_keep_mask_cik(frame, 5)
    bench = S.zero_information_benchmarks(
        frame, folds, B.TARGET_COL, keep_mask=keep, size_col="log_total_assets", ticker_col=E.CIK_COL
    )
    assert set(bench["benchmark"]) == set(S.ZERO_INFO_BENCHMARKS)
    assert len(bench) == 2 * len(folds)
    assert bench["n_test_dedup"].le(bench["n_test"]).all()


# ---------------------------------------------------------------------------
# 9. Census mode (allowed pre-ratification; no association anywhere)
# ---------------------------------------------------------------------------


def test_census_runs_without_ratification_and_reports_structure(tmp_path, synth):
    frame, diag = synth
    census = E.run_census(frame, diag, 5, tmp_path / "census_head1.json")
    assert census["mode"] == "census"
    assert census["n_rows"] == len(frame)
    assert len(census["per_candidate_quarter"]) >= 4
    row = census["per_candidate_quarter"][-1]
    assert row["n_test_dedup"] <= row["n_test"]
    assert row["n_train_purged"] <= row["n_train_expanding"]
    written = json.loads((tmp_path / "census_head1.json").read_text())
    assert written["freeze_statement"].startswith("No IC")


def test_census_source_contains_no_association_statistic():
    """Freeze tripwire: the census path must not be able to compute a
    feature-versus-outcome association."""
    src = Path(E.__file__).read_text()
    body = src.split("def run_census(")[1].split("\ndef ")[0]
    for banned in ("spearman", "pearson", "corrcoef", ".corr(", "polyfit", "fit_predict", "XGB"):
        assert banned not in body, f"census body mentions {banned!r}"


# ---------------------------------------------------------------------------
# 10. Report + caveats
# ---------------------------------------------------------------------------


def test_h1_noise_floor_is_recomputed_from_the_controls_artifact(tmp_path):
    fake = {
        "controls": {
            "T0_placebo_announcement_core": {"dedup": {"se_ic": 0.01, "mean_ic": 0.0, "n_periods": 40}},
            "T0_placebo_forward_core": {"dedup": {"se_ic": 0.02, "mean_ic": 0.0, "n_periods": 40}},
        }
    }
    path = tmp_path / "controls_results.json"
    path.write_text(json.dumps(fake))
    floor = E.h1_noise_floor(path)
    assert floor["available"] is True
    assert floor["floor_lo"] == pytest.approx(2.8 * 0.01)
    assert floor["floor_hi"] == pytest.approx(2.8 * 0.02)
    assert E.h1_noise_floor(tmp_path / "nope.json") == {"available": False}


def test_g2_caveats_are_read_from_the_file_not_hand_typed(tmp_path):
    fake = {
        "provenance": "model-consensus",
        "red_flags_status": "exploratory",
        "primary": {"sentiment": {"p_hat": 0.5, "n": 10, "wilson_95": [0.2, 0.8], "verdict": "X", "caveat": "c"}},
        "constants": {"sentiment_agreement": {"point": 0.5}},
    }
    path = tmp_path / "results_g2.json"
    path.write_text(json.dumps(fake))
    cav = E.load_g2_caveats(path)
    assert cav["verdicts"]["sentiment"]["p_hat"] == 0.5
    assert cav["sha256"] == E.sha256_file(path)
    assert E.load_g2_caveats(tmp_path / "absent.json")["available"] is False


def test_report_is_rendered_from_the_results_document(tmp_path, synth, synth_params):
    frame, diag = synth
    doc_path, rat_path = _write_doc(tmp_path, synth_params)
    params, guard = E.load_g3_params(doc_path, rat_path)
    doc = E.run_head1(
        params, guard, frame, diag,
        tmp_path / "results.json", tmp_path / "report.md", tmp_path / "run_log.jsonl",
        doc_path=doc_path, ratified_path=rat_path,
    )
    text = (tmp_path / "report.md").read_text()
    assert E.SCOPE_SENTENCE in text
    assert "numerically incomparable" in text
    assert "Equivalence margin" in text
    assert "expanding-window walk-forward" in text
    # the headline numbers in the prose come from the document
    assert f"{doc['margin']['se_block_bootstrap']:.4f}" in text
    assert f"{doc['margin']['mean_fold_delta']:.4f}" in text
    assert text.index("Equivalence margin") < text.index("Per-fold deltas")
    # standing sections are the frozen ones
    assert "Zero-information benchmarks (STANDING" in text
    assert "Within-fold bootstrap noise anchor (STANDING)" in text
    assert "Label-embargo census" in text


# ---------------------------------------------------------------------------
# 11. End-to-end selftest
# ---------------------------------------------------------------------------


def test_selftest_runs_end_to_end_on_synthetic_data(tmp_path):
    out = E.selftest(tmp_path)
    results = json.loads((tmp_path / "results_head1.json").read_text())
    assert list(results.keys())[0] == "margin"
    assert results["margin"]["status"] in ("POWERED", "UNPOWERED")
    assert len(results["per_fold_primary_delta_dedup"]) == len(results["folds"])
    # every required arm is present
    for key in (
        "per_fold_ic__pit_trailing_rank",
        "per_fold_ic__raw_levels",
        "per_fold_ic__pit_trailing_rank_no_same_day",
        "form_controlled_ablation",
        "censoring_arms",
        "standing",
        "seed_band",
        "loco",
        "noise_floor_h1",
        "g2_caveats",
    ):
        assert key in results, key
    # the exploratory red-flag block is reported separately, never as the
    # confirmatory one
    blocks = {r["block"] for r in results["per_fold_ic__pit_trailing_rank"]}
    assert blocks == {"numeric_only", "text_and_numeric", "text_and_numeric_exploratory"}
    evals = {r["eval_set"] for r in results["per_fold_ic__pit_trailing_rank"]}
    assert evals == {"raw", "dedup", "dedup_no_overlap"}
    assert results["loco"]["status"].startswith("DESCRIPTIVE ONLY")
    assert (tmp_path / "report_head1.md").exists()
    assert (tmp_path / "census_head1.json").exists()
    assert out["outdir"] == str(tmp_path)


def test_selftest_writes_nothing_into_the_repo_data_dir(tmp_path):
    before = sorted(p.name for p in E.F5_DIR.glob("*"))
    E.selftest(tmp_path)
    after = sorted(p.name for p in E.F5_DIR.glob("*"))
    assert before == after
    assert not E.G3_DOC_PATH.exists() and not E.G3_RATIFIED_PATH.exists()


# ---------------------------------------------------------------------------
# 12. Red-team follow-ups
# ---------------------------------------------------------------------------


def test_loco_index_rule_must_match_its_own_fold_budget(tmp_path, synth_params):
    bad = json.loads(json.dumps(synth_params))
    bad["loco"]["index_rule"] = "round(j*(K-1)/5)"   # the 6-fold spelling ...
    bad["loco"]["n_folds"] = 4                        # ... with a 4-fold budget
    doc, rat = _write_doc(tmp_path, bad)
    with pytest.raises(E.G3Refusal) as exc:
        E.load_g3_params(doc, rat)
    assert "divisor 5" in str(exc.value)

    ok = json.loads(json.dumps(synth_params))
    ok["loco"]["index_rule"] = "round(j*(K-1)/5)"
    ok["loco"]["n_folds"] = 6
    (tmp_path / "ok").mkdir()
    doc2, rat2 = _write_doc(tmp_path / "ok", ok)
    assert E.load_g3_params(doc2, rat2)[0]["loco"]["n_folds"] == 6


def test_loco_selects_the_pinned_fold_indices(synth, synth_params):
    frame, _ = synth
    params = json.loads(json.dumps(synth_params))
    folds, _ = E.build_folds(frame, params["fold_quarters"])
    keep = E.dedup_keep_mask_cik(frame, 5).values.astype(bool)
    ffs = E.build_fold_frames(frame, folds, None, 0, False, None)
    blocks = {
        "numeric_only": ["log_total_assets", "momentum_126"],
        "text_and_numeric": ["log_total_assets", "momentum_126", "sentiment_mean_score"],
    }
    out = E.loco_table(ffs, blocks, keep, params)
    k, n_sel = len(folds), params["loco"]["n_folds"]
    assert out["fold_indices"] == sorted({int(round(j * (k - 1) / max(n_sel - 1, 1))) for j in range(n_sel)})
    assert out["n_refits"] == 2 * len(out["rows"])
    assert out["status"].startswith("DESCRIPTIVE ONLY")
    for row in out["rows"]:
        assert row["n_train_after_holdout"] > 0


def test_embedding_column_with_no_values_is_reported_not_raised():
    df = pd.DataFrame({"emb": [None, float("nan"), None]})
    assert E.embedding_matrix(df) is None
    assert E.embedding_matrix(pd.DataFrame({"x": [1]})) is None
    ragged = pd.DataFrame({"emb": [[1.0, 2.0], [1.0]]})
    with pytest.raises(AssertionError):
        E.embedding_matrix(ragged)


# ---------------------------------------------------------------------------
# 13. Red-team pass 2026-09-10: arm-gated transform, pinned k, the guard door,
#     the header door, and the census call graph
# ---------------------------------------------------------------------------


def _run_head1(tmp_path, frame, diag, params, **over):
    """Run head 1 against a SYNTHETIC ratified pair written into `tmp_path`."""
    doc_path, rat_path = _write_doc(tmp_path, params)
    loaded, guard = E.load_g3_params(doc_path, rat_path)
    kwargs = dict(
        results_path=tmp_path / "results.json",
        report_path=tmp_path / "report.md",
        run_log_path=tmp_path / "run_log.jsonl",
        doc_path=doc_path,
        ratified_path=rat_path,
    )
    kwargs.update(over)
    return E.run_head1(loaded, guard, frame, diag, **kwargs), (doc_path, rat_path)


def test_the_raw_levels_arm_keeps_the_untransformed_pca_projection(tmp_path, synth, synth_params, monkeypatch):
    """`embedding.rank_transform_components` governs the PIT-RANKED arms only.

    The secondary arm is `raw_levels`; if its PCA components went through the
    PIT-rank transform the secondary arm would not be raw, and the pair the
    pre-registration describes would silently collapse to one specification."""
    frame, diag = synth
    params = json.loads(json.dumps(synth_params))
    params["embedding"]["rank_transform_components"] = True

    seen = []
    real_eval = E.evaluate_arm

    def spy(aframe, fold_frames, *a, **kw):
        seen.append(fold_frames)
        return real_eval(aframe, fold_frames, *a, **kw)

    monkeypatch.setattr(E, "evaluate_arm", spy)
    _run_head1(tmp_path, frame, diag, params)

    # arms are evaluated in insertion order: primary, raw_levels, primary-no-same-day
    primary_frames, secondary_frames = seen[0], seen[1]
    emb = E.embedding_matrix(frame)
    k = int(params["embedding"]["pca_k"])
    assert len(secondary_frames) == len(primary_frames) > 0
    for prim, sec in zip(primary_frames, secondary_frames):
        comps, _info = E.pca_project(emb, sec["fold"]["train_idx"], k)
        cols = sec["emb_cols"]
        assert cols == [f"emb_pc{i + 1}" for i in range(comps.shape[1])] != []
        for i, col in enumerate(cols):
            # EXACTLY the untransformed projection, not merely close to it
            np.testing.assert_array_equal(sec["frame"][col].values, comps[:, i])
        # ... and the check is not vacuous: the primary arm's components moved
        assert not np.array_equal(prim["frame"][cols[0]].values, comps[:, 0])


def test_the_transform_flag_still_reaches_the_primary_arms(synth, synth_params):
    """Guard against over-gating: with the flag on, a PIT-ranked arm's
    components differ from the raw projection; with it off, they match."""
    frame, _ = synth
    params = json.loads(json.dumps(synth_params))
    folds, _ = E.build_folds(frame, params["fold_quarters"], params["purge_rule"])
    emb = E.embedding_matrix(frame)
    k = int(params["embedding"]["pca_k"])
    kwargs = {"window_days": 180, "min_comparators": 2, "include_same_day": True,
              "ticker_col": E.CIK_COL, "date_col": E.FILING_DATE_COL}
    off = E.build_fold_frames(frame, folds, emb, k, False, kwargs)
    on = E.build_fold_frames(frame, folds, emb, k, True, kwargs)
    comps, _ = E.pca_project(emb, folds[0]["train_idx"], k)
    np.testing.assert_array_equal(off[0]["frame"]["emb_pc1"].values, comps[:, 0])
    assert not np.array_equal(on[0]["frame"]["emb_pc1"].values, comps[:, 0])


def test_a_pinned_pca_k_without_an_embedding_column_is_a_refusal(tmp_path, synth_params):
    tgt, txt, num, fam = E.synthetic_frames(seed=3, n_ciks=8, n_quarters=8, emb_dim=6)
    fam = fam.drop(columns=["emb"])                       # families table, no vectors
    frame, diag = E.join_frames(tgt, txt, num, fam)
    params = E.selftest_params(frame)
    assert params["embedding"]["pca_k"] > 0
    with pytest.raises(E.G3Refusal) as exc:
        _run_head1(tmp_path, frame, diag, params)
    assert "embedding.pca_k" in str(exc.value) and "silently dropped" in str(exc.value)


def test_a_fold_that_cannot_realize_the_pinned_components_is_a_refusal(tmp_path, synth, synth_params):
    """`pca_project` caps k at the embedding width; a pinned k above it would
    otherwise run a NARROWER feature block than the one G3 ratified."""
    frame, diag = synth
    params = json.loads(json.dumps(synth_params))
    params["embedding"]["pca_k"] = 99                     # the synthetic emb is 6-wide
    with pytest.raises(E.G3Refusal) as exc:
        _run_head1(tmp_path, frame, diag, params)
    assert "fewer embedding components" in str(exc.value)
    assert "k_effective" in str(exc.value) and "silently narrowed" in str(exc.value)


def test_assert_pinned_components_passes_when_every_fold_realizes_k(synth, synth_params):
    frame, _ = synth
    params = json.loads(json.dumps(synth_params))
    folds, _ = E.build_folds(frame, params["fold_quarters"], params["purge_rule"])
    emb = E.embedding_matrix(frame)
    k = int(params["embedding"]["pca_k"])
    ffs = E.build_fold_frames(frame, folds, emb, k, False, None)
    E.assert_pinned_components(ffs, k, "test")            # no raise
    E.assert_pinned_components(ffs, 0, "test")            # k = 0 disables the block


def test_a_fabricated_guard_dict_cannot_reach_a_fit(tmp_path, synth, synth_params):
    """`run_head1` re-measures the ratified document itself. A caller that
    hands it a made-up `doc_sha256` is refused, and the real repo has no
    ratified document at all today, so the default paths refuse too."""
    frame, diag = synth
    doc_path, rat_path = _write_doc(tmp_path, synth_params)
    params, guard = E.load_g3_params(doc_path, rat_path)

    forged = dict(guard, doc_sha256="0" * 64)
    with pytest.raises(E.G3Refusal) as exc:
        E.run_head1(params, forged, frame, diag,
                    tmp_path / "r.json", tmp_path / "rep.md", tmp_path / "log.jsonl",
                    doc_path=doc_path, ratified_path=rat_path)
    assert "not a ratification" in str(exc.value)
    assert not (tmp_path / "r.json").exists()

    # the same fabrication against the REAL paths: refused because no
    # ratification exists in this repo today
    assert not E.G3_RATIFIED_PATH.exists()
    with pytest.raises(E.G3Refusal):
        E.run_head1(params, {"doc_sha256": "0" * 64, "params_sha256": "x"}, frame, diag,
                    tmp_path / "r2.json", tmp_path / "rep2.md", tmp_path / "log2.jsonl")
    assert not (tmp_path / "r2.json").exists()


def test_add_header_refuses_a_delta_bearing_payload_before_the_margin():
    w = E.ResultsWriter()
    for key, value in (
        ("census", {"spearman_ic": 0.1}),
        ("census", {"rows": [{"test_quarter": "2020Q1", "delta": 0.02}]}),
        ("census", {"nested": {"deep": [{"mean_fold_delta_dedup": 0.01}]}}),
        ("per_fold_delta__primary", {"n": 1}),
        ("census", {"text_ic": 0.3}),
    ):
        with pytest.raises(E.OrderingViolation) as exc:
            w.add_header(key, value)
        assert "margin" in str(exc.value)

    # provenance-shaped headers are unaffected ...
    w.add_header("run", {"module": "backtest_e2.py", "doc_sha256": "a" * 64})
    w.add_header("params", json.loads(json.dumps(E.SELFTEST_PARAMS)))
    w.add_header("folds", [{"test_quarter": "2020Q1", "n_train": 10, "n_test": 3}])
    # ... and after the margin exists the ordering rule has been satisfied
    w.set_margin(_margin_block(0.001))
    w.add_header("late", {"spearman_ic": 0.1})


def test_delta_like_keys_matches_the_documented_pattern():
    assert E.delta_like_keys("x", {"delta": 1}) == ["delta"]
    assert E.delta_like_keys("x", {"spearman_p": 1}) == ["spearman_p"]
    assert E.delta_like_keys("x", {"n_ic": 1}) == ["n_ic"]
    assert E.delta_like_keys("mean_fold_delta_dedup", {}) == ["mean_fold_delta_dedup"]
    # a column NAME as a string VALUE is a parameter, not a result
    assert E.delta_like_keys("params", {"columns": ["spearman_ic", "delta"]}) == []
    assert E.delta_like_keys("frame", {"n_rows": 7405, "ic_note": "x"}) == []


FITTING_FUNCTIONS = {
    "fit_predict_seeded", "evaluate_arm", "fold_deltas", "margin_procedure",
    "loco_table", "seed_band", "standing_payload", "pca_project", "run_head1",
}


def _call_graph(tree):
    graph = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            graph[node.name] = {c.func.id for c in ast.walk(node)
                                if isinstance(c, ast.Call)
                                and isinstance(c.func, ast.Name)}
    return graph


def test_the_census_path_cannot_reach_a_fitting_function():
    """The AST twin of `heads_e2`'s tripwire: census mode is allowed before
    ratification, so nothing reachable from it may fit or associate."""
    tree = ast.parse(Path(E.__file__).read_text())
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
    # the tripwire is not vacuous: run_head1 does reach them
    seen, stack = set(), ["run_head1"]
    while stack:
        fn = stack.pop()
        if fn in seen:
            continue
        seen.add(fn)
        stack.extend(graph.get(fn, ()))
    assert FITTING_FUNCTIONS - {"run_head1"} <= seen
