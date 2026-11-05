"""test_f6a_late_renders.py -- `data/f5/sensitivity_decision11.py` (review M1) and
`data/f5/render_head1_addendum.py` (review S4 + S5). Offline; synthetic data except
the tests marked `real`, which read today's committed artifacts and skip if absent."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import backtest_e2 as BE  # noqa: E402


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "data" / "f5" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


D11 = _load("sensitivity_decision11")
ADD = _load("render_head1_addendum")


# ---------------------------------------------------------------------------
# decision 11: which rows carry a WITHDRAWN label
# ---------------------------------------------------------------------------

def _corpus(rows):
    labels = pd.DataFrame([{"chunk_id": r[0], "section_type": r[1], "sentiment": None,
                            "guidance_direction": r[2], "guidance_applicable": r[3]}
                           for r in rows])
    chunks = pd.DataFrame([{"chunk_id": r[0], "home_cik": r[4], "home_accession_number": r[5],
                            "source_ciks": np.array(r[6]),
                            "source_accession_numbers": np.array(r[7])} for r in rows])
    return labels, chunks


def test_withdrawn_keys_follow_the_feature_masks_and_same_cik_attribution():
    labels, chunks = _corpus([
        # scored: home filing + a later same-CIK filing; the cross-CIK one is dropped
        ("c1", "EX99_PRESS_RELEASE", "WITHDRAWN", True, 1, "a1", [1, 1, 2], ["a1", "a9", "b1"]),
        ("c2", "MDA", "WITHDRAWN", True, 3, "m1", [3], ["m1"]),           # masked on MDA
        ("c3", "8K_BODY", "WITHDRAWN", True, 4, "k1", [4], ["k1"]),        # register excluded
        ("c4", "EX99_PRESS_RELEASE", "WITHDRAWN", False, 5, "n1", [5], ["n1"]),  # not applicable
        ("c5", "EX99_PRESS_RELEASE", "LOWERED", True, 6, "l1", [6], ["l1"]),     # -1, not WITHDRAWN
    ])
    keys = D11.withdrawn_keys(labels, chunks)
    assert keys["n_scored_withdrawn_chunks"] == 1
    assert keys["attributed"] == {(1, "a1"), (1, "a9")}
    assert keys["home"] == {(1, "a1")}


def test_withdrawn_keys_refuse_misaligned_inputs():
    labels, chunks = _corpus([("c1", "EX99_PRESS_RELEASE", "WITHDRAWN", True, 1, "a1", [1], ["a1"]),
                              ("c2", "EX99_PRESS_RELEASE", "NONE", True, 1, "a2", [1], ["a2"])])
    with pytest.raises(AssertionError):
        D11.withdrawn_keys(labels, chunks.iloc[::-1].reset_index(drop=True))


def test_primary_dedup_deltas_reproduce_run_head1_on_the_selftest(tmp_path):
    """The recomposed primary must equal run_head1's own estimand exactly -- the
    same guarantee the real script asserts before writing anything."""
    out = BE.selftest(tmp_path)
    recorded = pd.DataFrame(out["results"]["per_fold_primary_delta_dedup"])
    tgt, txt, num, fam = BE.synthetic_frames()
    frame, _ = BE.join_frames(tgt, txt, num, fam)
    params = BE.selftest_params(frame)
    frame, _ = BE.exclude_gld_rows(frame, params)
    deltas, _ = D11.primary_dedup_deltas(frame, params)
    assert list(deltas["test_quarter"]) == list(recorded["test_quarter"])
    assert np.array_equal(deltas["delta"].values, recorded["delta"].values, equal_nan=True)


def test_sensitivity_refuses_without_the_pin(tmp_path, monkeypatch):
    def refuse(*a, **k):
        raise BE.G3Refusal("BLOCKED: synthetic refusal")
    monkeypatch.setattr(D11.BE, "load_g3_params", refuse)
    monkeypatch.setattr(D11, "OUT_PATH", tmp_path / "out.json")
    monkeypatch.setattr(D11, "RUN_LOG", tmp_path / "run_log.jsonl")
    assert D11.main() == 2
    assert not (tmp_path / "out.json").exists() and not (tmp_path / "run_log.jsonl").exists()


REAL_D11 = ROOT / "data" / "f5" / "sensitivity_decision11.json"
REAL_RESULTS = ROOT / "data" / "f5" / "results_head1.json"
REAL_LOG = ROOT / "data" / "f5" / "run_log.jsonl"


@pytest.mark.skipif(not REAL_D11.exists(), reason="decision-11 sensitivity not run on this checkout")
def test_real_decision11_artifact_is_labelled_late_and_logged():
    d = json.loads(REAL_D11.read_text())
    assert d["label"] == D11.LABEL and "can never be selected as the primary" in d["label"]
    assert d["reproduction_check"]["primary_recomposed_equals_results_head1"] is True
    assert d["reproduction_check"]["max_abs_diff_per_fold_delta"] == 0.0
    head1 = json.loads(REAL_RESULTS.read_text())
    assert d["primary_mean_fold_delta_dedup"] == head1["margin"]["mean_fold_delta"]
    assert d["sensitivity"]["k_folds"] == 33 == len(d["sensitivity"]["per_fold"])
    assert d["home_key_reconciliation"]["n_rows_removed_total"] == 35  # prereg §10's count
    q2 = next(f for f in d["sensitivity"]["per_fold"] if f["test_quarter"] == "2020Q2")
    assert q2["n_removed_test_rows"] == 25                              # "25 in one fold"
    logged = {json.loads(ln).get("sha256") for ln in REAL_LOG.read_text().splitlines() if ln}
    assert BE.sha256_file(REAL_D11) in logged


# ---------------------------------------------------------------------------
# the head-1 addendum
# ---------------------------------------------------------------------------

def _results(stored_mean_offset=0.0):
    recs = [{"test_quarter": f"2018Q{i}", "delta": d} for i, d in enumerate([0.1, -0.05, 0.01], 1)]
    mean = sum(r["delta"] for r in recs) / 3
    res = {"margin": {"mean_fold_delta": mean, "k_folds": 3, "measured_lag1_autocorrelation": -0.1},
           "params": {"purge_rule": "target_window_close_on_or_after_test_quarter_start"},
           "standing": {
               "bootstrap_anchor_scope": "SCOPE NOTE VERBATIM",
               "embargo_census_post_purge": [
                   {"n_train": 10, "n_train_labels_resolving_in_or_after_test_quarter": 0}] * 3,
               "bootstrap_anchor": {BE.S.PRIMARY_SPEC: {"per_fold": [
                   {"test_quarter": r["test_quarter"], "fold_delta_dedup": r["delta"] / 2}
                   for r in recs]}}}}
    for _, key, sub, stored in ADD.ARMS:
        if sub:
            res[key] = {sub: recs, stored: mean + stored_mean_offset}
        else:
            res[key] = recs
    return res


def test_arm_rows_cover_every_always_reported_arm_beside_the_primary():
    rows = ADD.arm_rows(_results())
    assert [r["arm"] for r in rows] == [a[0] for a in ADD.ARMS]
    assert rows[0]["arm"].startswith("PRIMARY") and all(r["k"] == 3 for r in rows)


def test_arm_rows_refuse_a_stored_mean_that_disagrees_with_its_records():
    with pytest.raises(AssertionError):
        ADD.arm_rows(_results(stored_mean_offset=1e-6))


def test_render_quotes_the_scope_note_and_only_stale_phrases_actually_present():
    report = "intro. At E2's ~26 folds the thing. end"
    text = ADD.render(_results(), report, {"labels": "LABEL SENTENCE"},
                      {"results": "r" * 64, "report": "p" * 64}, None, ["net_margin"])
    assert "> SCOPE NOTE VERBATIM" in text
    assert "\"At E2's ~26 folds\"" in text
    assert "\"at k = 6 neither tail" not in text
    assert "**0 of 30 training labels**" in text
    assert "LABEL SENTENCE" in text and "`net_margin`" in text
    assert "not human validation of ground truth" in text


def test_addendum_refuses_without_the_pin(tmp_path, monkeypatch):
    def refuse(*a, **k):
        raise BE.G3Refusal("BLOCKED: synthetic refusal")
    monkeypatch.setattr(ADD.BE, "load_g3_params", refuse)
    monkeypatch.setattr(ADD, "OUT", tmp_path / "addendum.md")
    assert ADD.main() == 2
    assert not (tmp_path / "addendum.md").exists()


REAL_ADD = ROOT / "data" / "f5" / "report_head1_addendum.md"


@pytest.mark.skipif(not REAL_ADD.exists(), reason="addendum not rendered on this checkout")
def test_real_addendum_is_logged_and_carries_the_overrides():
    text = REAL_ADD.read_text()
    logged = {json.loads(ln).get("sha256") for ln in REAL_LOG.read_text().splitlines() if ln}
    assert BE.sha256_file(REAL_ADD) in logged
    assert "**0 of 123,180 training labels**" in text
    assert "NEGATIVE recall 0.529 (64/121)" in text and "25/49" in text and "84/200" in text
    assert "standing.bootstrap_anchor_scope" in text
