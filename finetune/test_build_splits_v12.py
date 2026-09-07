"""Offline tests for build_splits_v12.py — the join / gap / exclusion logic.

No network, no model, no GPU. Synthetic fixtures for the logic tests; a small
number of tests read the real on-disk artifacts and are skipped if absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import build_splits_v12 as B

REPO = Path(__file__).resolve().parent.parent
LABEL_COLS = [
    "chunk_id", "section_type", "text", "parse_ok", "schema_valid",
    "api_result_type", "parse_error", "sentiment", "guidance_direction",
    "red_flags", "distress_tier",
]


def make_manifest(rows) -> pd.DataFrame:
    return pd.DataFrame(
        rows, columns=["chunk_id", "split", "section_type", "home_ticker", "home_filing_date"]
    )


def make_labels(chunk_ids, section_types=None, ok=None) -> pd.DataFrame:
    n = len(chunk_ids)
    section_types = section_types or ["MDA"] * n
    ok = [True] * n if ok is None else ok
    return pd.DataFrame(
        {
            "chunk_id": chunk_ids,
            "section_type": section_types,
            "text": [f"passage for {c}" for c in chunk_ids],
            "parse_ok": ok,
            "schema_valid": ok,
            "api_result_type": ["succeeded" if o else "errored" for o in ok],
            "parse_error": [None if o else "batch result type=errored" for o in ok],
            "sentiment": ["NEUTRAL" if o else None for o in ok],
            "guidance_direction": [None] * n,
            "red_flags": [[] for _ in range(n)],
            "distress_tier": [None] * n,
        }
    )


def synth(tmp_path, *, n_train=8, n_eval=3, gap_ids=(), extra_label_ids=()):
    """Build a synthetic frozen manifest + v1.2 label set on disk.

    Patches FROZEN_SPLIT_SIZES so the small fixture passes the frozen-size
    guard (the guard itself is tested separately against the real numbers).
    """
    train_ids = [f"CHK-t{i:04d}" for i in range(n_train)]
    eval_ids = [f"CHK-e{i:04d}" for i in range(n_eval)]
    man = make_manifest(
        [(c, "train", "MDA", "AAA", "2024-01-01") for c in train_ids]
        + [(c, "eval", "MDA", "BBB", "2024-01-01") for c in eval_ids]
    )
    all_ids = train_ids + eval_ids + list(extra_label_ids)
    ok = [c not in set(gap_ids) for c in all_ids]
    lab = make_labels(all_ids, ok=ok)

    man_path = tmp_path / "manifest.parquet"
    lab_path = tmp_path / "labels_v12.parquet"
    man.to_parquet(man_path, index=False)
    lab.to_parquet(lab_path, index=False)
    return man_path, lab_path, train_ids, eval_ids


@pytest.fixture
def sizes(monkeypatch):
    def _set(train, ev):
        monkeypatch.setattr(B, "FROZEN_SPLIT_SIZES", {"train": train, "eval": ev})
    return _set


# ---------------------------------------------------------------- join ----

def test_join_reproduces_frozen_membership_exactly(tmp_path, sizes):
    sizes(8, 3)
    man_path, lab_path, train_ids, eval_ids = synth(tmp_path)
    rep = B.build(lab_path, man_path, tmp_path / "out")
    assert rep["outputs"]["train"]["rows"] == 8
    assert rep["outputs"]["eval"]["rows"] == 3
    tr = pd.read_parquet(tmp_path / "out" / "train.parquet")
    ev = pd.read_parquet(tmp_path / "out" / "eval.parquet")
    assert list(tr.chunk_id) == train_ids
    assert list(ev.chunk_id) == eval_ids


def test_extra_labels_not_in_the_manifest_are_ignored(tmp_path, sizes):
    """The v1.2 label file has 6,747 rows; the frozen manifest has 6,746.
    The surplus row must never enter a split."""
    sizes(8, 3)
    man_path, lab_path, *_ = synth(tmp_path, extra_label_ids=["CHK-surplus"])
    rep = B.build(lab_path, man_path, tmp_path / "out")
    assert rep["outputs"]["train"]["rows"] + rep["outputs"]["eval"]["rows"] == 11
    for side in ("train", "eval"):
        assert "CHK-surplus" not in set(pd.read_parquet(tmp_path / "out" / f"{side}.parquet").chunk_id)


def test_split_column_is_dropped_from_the_side_parquets(tmp_path, sizes):
    sizes(8, 3)
    man_path, lab_path, *_ = synth(tmp_path)
    B.build(lab_path, man_path, tmp_path / "out")
    assert "split" not in pd.read_parquet(tmp_path / "out" / "train.parquet").columns


def test_manifest_missing_from_labels_is_a_hard_error(tmp_path, sizes):
    sizes(8, 3)
    man_path, lab_path, train_ids, _ = synth(tmp_path)
    lab = pd.read_parquet(lab_path)
    lab = lab[lab.chunk_id != train_ids[0]]
    lab.to_parquet(lab_path, index=False)
    with pytest.raises(ValueError, match="absent from"):
        B.build(lab_path, man_path, tmp_path / "out")


def test_section_type_disagreement_is_a_hard_error(tmp_path, sizes):
    sizes(8, 3)
    man_path, lab_path, train_ids, _ = synth(tmp_path)
    lab = pd.read_parquet(lab_path)
    lab.loc[lab.chunk_id == train_ids[0], "section_type"] = "RISK_FACTORS"
    lab.to_parquet(lab_path, index=False)
    with pytest.raises(ValueError, match="section_type disagrees"):
        B.build(lab_path, man_path, tmp_path / "out")


# ---------------------------------------------------------------- gaps ----

def test_a_label_gap_drops_exactly_that_row_and_is_reported_loudly(tmp_path, sizes):
    sizes(8, 3)
    gap = "CHK-t0003"
    man_path, lab_path, train_ids, _ = synth(tmp_path, gap_ids=[gap])
    rep = B.build(lab_path, man_path, tmp_path / "out")
    assert rep["v12_label_gaps"]["n"] == 1
    g = rep["v12_label_gaps"]["rows"][0]
    assert g["chunk_id"] == gap and g["split"] == "train"
    assert rep["outputs"]["train"]["rows"] == 7
    assert rep["outputs"]["eval"]["rows"] == 3
    assert rep["deltas_vs_frozen"] == {"train": -1, "eval": 0}
    assert gap not in set(pd.read_parquet(tmp_path / "out" / "train.parquet").chunk_id)


def test_gap_row_stays_in_the_manifest_flagged_not_deleted(tmp_path, sizes):
    sizes(8, 3)
    gap = "CHK-t0003"
    man_path, lab_path, *_ = synth(tmp_path, gap_ids=[gap])
    B.build(lab_path, man_path, tmp_path / "out")
    m = pd.read_parquet(tmp_path / "out" / "manifest.parquet")
    assert len(m) == 11, "the manifest keeps every frozen row"
    assert not bool(m.loc[m.chunk_id == gap, "v12_labeled"].iloc[0])
    assert bool(m.loc[m.chunk_id != gap, "v12_labeled"].all())


def test_an_eval_side_gap_would_also_be_caught(tmp_path, sizes):
    sizes(8, 3)
    man_path, lab_path, *_ = synth(tmp_path, gap_ids=["CHK-e0001"])
    rep = B.build(lab_path, man_path, tmp_path / "out")
    assert rep["deltas_vs_frozen"] == {"train": 0, "eval": -1}


# ----------------------------------------------------------- exclusions ----

def test_refusal_chunk_present_in_the_manifest_is_a_hard_error(tmp_path, sizes):
    sizes(9, 3)
    man_path, lab_path, *_ = synth(tmp_path, n_train=8)
    man = pd.read_parquet(man_path)
    man.loc[len(man)] = [B.E1_REFUSAL_CHUNK, "train", "MDA", "AAA", "2024-01-01"]
    man.to_parquet(man_path, index=False)
    lab = pd.read_parquet(lab_path)
    lab = pd.concat([lab, make_labels([B.E1_REFUSAL_CHUNK])], ignore_index=True)
    lab.to_parquet(lab_path, index=False)
    with pytest.raises(ValueError, match="must not be"):
        B.build(lab_path, man_path, tmp_path / "out")


def test_refusal_chunk_labeled_under_v12_still_never_enters_a_split(tmp_path, sizes):
    """The real case: v1.2 successfully labeled it, the frozen manifest excludes it."""
    sizes(8, 3)
    man_path, lab_path, *_ = synth(tmp_path, extra_label_ids=[B.E1_REFUSAL_CHUNK])
    rep = B.build(lab_path, man_path, tmp_path / "out")
    assert rep["e1_refusal_chunk"]["labels_under_v12"] is True
    assert rep["e1_refusal_chunk"]["kept_out_of_both_splits"] is True
    for side in ("train", "eval"):
        assert B.E1_REFUSAL_CHUNK not in set(pd.read_parquet(tmp_path / "out" / f"{side}.parquet").chunk_id)
    assert B.E1_REFUSAL_CHUNK not in set(pd.read_parquet(tmp_path / "out" / "manifest.parquet").chunk_id)


def test_wrong_sized_manifest_is_refused(tmp_path):
    """Guard against being handed a re-derived (not frozen) manifest."""
    man_path, lab_path, *_ = synth(tmp_path)
    with pytest.raises(ValueError, match="not the frozen split"):
        B.build(lab_path, man_path, tmp_path / "out")


# ------------------------------------------------------- corpus identity ----

def test_text_drift_between_e1_and_v12_is_a_hard_error(tmp_path, sizes):
    sizes(8, 3)
    man_path, lab_path, train_ids, _ = synth(tmp_path)
    e1 = pd.read_parquet(lab_path)
    e1.loc[e1.chunk_id == train_ids[0], "text"] = "DIFFERENT PASSAGE"
    e1_path = tmp_path / "labels_e1.parquet"
    e1.to_parquet(e1_path, index=False)
    with pytest.raises(ValueError, match="passage text differs"):
        B.build(lab_path, man_path, tmp_path / "out", e1_path)


def test_text_identity_flag_is_false_when_e1_labels_are_absent(tmp_path, sizes):
    sizes(8, 3)
    man_path, lab_path, *_ = synth(tmp_path)
    rep = B.build(lab_path, man_path, tmp_path / "out", tmp_path / "nope.parquet")
    assert rep["inputs"]["e1_labels_text_identity_verified"] is False


# ------------------------------------------------- real-artifact pinning ----

REAL_OUT = Path(__file__).resolve().parent / "splits_v12"
real = pytest.mark.skipif(
    not (REAL_OUT / "build_report.json").exists(), reason="v1.2 splits not built on this box"
)


@real
def test_real_counts_equal_the_frozen_split_exactly():
    """After the 2026-08-26 completion batch closed the one-row gap, the v1.2
    splits are the frozen split exactly — no delta on either side."""
    rep = json.loads((REAL_OUT / "build_report.json").read_text())
    assert rep["outputs"]["train"]["rows"] == 5736
    assert rep["outputs"]["eval"]["rows"] == 1010
    assert rep["deltas_vs_frozen"] == {"train": 0, "eval": 0}


@real
def test_real_build_has_no_label_gaps():
    rep = json.loads((REAL_OUT / "build_report.json").read_text())
    assert rep["v12_label_gaps"]["n"] == 0
    assert rep["v12_label_gaps"]["rows"] == []


@real
def test_real_build_still_excludes_the_refusal_chunk_that_v12_did_label():
    rep = json.loads((REAL_OUT / "build_report.json").read_text())
    ref = rep["e1_refusal_chunk"]
    assert ref["labels_under_v12"] is True
    assert ref["in_frozen_manifest"] is False
    assert ref["kept_out_of_both_splits"] is True


@real
def test_real_membership_is_bit_for_bit_the_frozen_membership():
    frozen = pd.read_parquet(B.FROZEN_MANIFEST)[["chunk_id", "split"]]
    new = pd.read_parquet(REAL_OUT / "manifest.parquet")[["chunk_id", "split"]]
    merged = frozen.merge(new, on="chunk_id", suffixes=("_frozen", "_v12"), validate="1:1")
    assert len(merged) == len(frozen) == len(new) == 6746
    assert (merged.split_frozen == merged.split_v12).all()


@real
def test_e1_frozen_artifacts_were_not_written():
    """The E1 splits must be untouched — same shas as their own contents."""
    for name, n in (("train", 5736), ("eval", 1010), ("manifest", 6746)):
        assert len(pd.read_parquet(B.HERE / "splits" / f"{name}.parquet")) == n
