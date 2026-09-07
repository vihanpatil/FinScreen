#!/usr/bin/env python3
"""Offline tests for data/f4/g2/build_adjudicator_batches_g2.py — $0, no GPU,
no network, and no repo file is written (every write lands in tmp_path).

    python3 -m pytest finetune/test_g2_adjudicator_batches.py -q -p no:cacheprovider

Covers the five things that can silently corrupt the G2 adjudication stage:
§1.2 applicability masking, contested detection (including the §1.3 omission
conventions), the ≤40-row cap with the §5.3 family split, the §10.2.2 key set,
and the no-verdicts-yet exit.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
G2 = REPO / "data" / "f4" / "g2"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _load("build_adjudicator_batches_g2", G2 / "build_adjudicator_batches_g2.py")
A = _load("analyze_g2", G2 / "analyze_g2.py")
RED = M.RED


def stored_of(sentiment=None, guidance=None, red=None):
    return M.stored_values({"sentiment": sentiment, "guidance_direction": guidance,
                            RED: red}, True)


def test_applicability_mask_matches_the_design_and_analyze_g2():
    """§1.2: off-matrix rater values are collected and DISCARDED, however loudly
    they disagree. The mask is the same object analyze_g2.py scores with."""
    assert M.APPLICABLE == A.APPLICABLE
    assert M.APPLICABLE == {"sentiment": {"MDA", "EX99_PRESS_RELEASE"},
                            "guidance_direction": {"EX99_PRESS_RELEASE"},
                            RED: {"MDA", "RISK_FACTORS", "EX99_PRESS_RELEASE"}}

    fields = list(M.GATE_FIELDS) + [RED]
    # Every cell below disagrees; every one of them is off-matrix.
    stored = {"MDA1": stored_of("NEUTRAL", "NONE", []),
              "RF1": stored_of("NEUTRAL", "NONE", [])}
    rater = {"MDA1": {"sentiment": "NEUTRAL", "guidance_direction": "RAISED",
                      RED: frozenset()},
             "RF1": {"sentiment": "NEGATIVE", "guidance_direction": "LOWERED",
                     RED: frozenset()}}
    rows, counts = M.contested_rows(
        ["MDA1", "RF1"], stored, {"MDA1": "MDA", "RF1": "RISK_FACTORS"},
        rater, {"MDA1": "t", "RF1": "t"}, fields)

    assert rows == []
    assert counts["guidance_direction"]["masked"] == 2      # MDA + RISK_FACTORS
    assert counts["sentiment"]["masked"] == 1               # RISK_FACTORS only
    assert counts[RED]["masked"] == 0                       # applicable on both


def test_contested_detection_sets_omissions_and_imputed_none():
    """Contested iff stored != rater on an applicable field: red_flags compares
    as a SET (order-insensitive), a stored null is excluded as a §1.3 pinned
    error, and an imputed NONE compares as the string NONE."""
    fields = list(M.GATE_FIELDS) + [RED]
    pair = [{"category": "DEMAND_WEAKNESS", "modality": "HYPOTHETICAL"},
            {"category": "MARGIN_COST_PRESSURE", "modality": "REALIZED"}]
    stored = {
        "SAME": stored_of("POSITIVE", "NONE", pair),            # imputed NONE row
        "DIFF": stored_of("POSITIVE", "RAISED", pair[:1]),
        "OMIT": stored_of(None, None, []),                      # bad-enum/null row
    }
    assert stored["OMIT"]["sentiment"] == M.MISSING
    assert stored["OMIT"]["guidance_direction"] == M.MISSING
    rater = {
        "SAME": {"sentiment": "POSITIVE", "guidance_direction": "NONE",
                 # same set, reversed order
                 RED: frozenset({("MARGIN_COST_PRESSURE", "REALIZED"),
                                 ("DEMAND_WEAKNESS", "HYPOTHETICAL")})},
        "DIFF": {"sentiment": "NEGATIVE", "guidance_direction": "LOWERED",
                 RED: frozenset({("DEMAND_WEAKNESS", "REALIZED")})},
        "OMIT": {"sentiment": "NEUTRAL", "guidance_direction": "NONE",
                 RED: frozenset()},
    }
    sec = dict.fromkeys(stored, "EX99_PRESS_RELEASE")
    rows, counts = M.contested_rows(list(stored), stored, sec, rater,
                                    dict.fromkeys(stored, "t"), fields)

    assert [(r["chunk_id"], r["field"]) for r in rows] == [
        ("DIFF", "sentiment"), ("DIFF", "guidance_direction"), ("DIFF", RED)]
    assert counts["sentiment"] == {"rated": 3, "masked": 0, "omission_excluded": 1,
                                   "uncontested": 1, "contested": 1}
    assert counts["guidance_direction"]["omission_excluded"] == 1
    assert counts[RED]["uncontested"] == 2                  # SAME (order) + OMIT
    # Sets are rendered as sorted [CATEGORY, MODALITY] pairs, not python sets.
    red_row = rows[-1]
    assert red_row["stored_label"] == [["DEMAND_WEAKNESS", "HYPOTHETICAL"]]
    assert red_row["rater_label"] == [["DEMAND_WEAKNESS", "REALIZED"]]


def test_batch_cap_and_family_split():
    """≤40 rows per file, gate-bearing first, families never mixed (§5.3) —
    red_flags is adjudicator-final, gate-bearing rows can reach the owner."""
    rows = ([{"chunk_id": f"S{i}", "field": "sentiment", "text": "t",
              "stored_label": "POSITIVE", "rater_label": "NEGATIVE"} for i in range(50)]
            + [{"chunk_id": f"G{i}", "field": "guidance_direction", "text": "t",
                "stored_label": "NONE", "rater_label": "RAISED"} for i in range(35)]
            + [{"chunk_id": f"R{i}", "field": RED, "text": "t",
                "stored_label": [], "rater_label": [["DEMAND_WEAKNESS", "REALIZED"]]}
               for i in range(10)])
    batches = M.split_batches(rows)

    assert [(fam, len(rs)) for fam, rs in batches] == [
        ("gate_bearing", 40), ("gate_bearing", 40), ("gate_bearing", 5), (RED, 10)]
    assert all(len(rs) <= M.BATCH_SIZE == 40 for _, rs in batches)
    for fam, rs in batches:
        assert {M.FAMILY[r["field"]] for r in rs} == {fam}
    flat = [r["chunk_id"] for _, rs in batches for r in rs]
    assert sorted(flat) == sorted(r["chunk_id"] for r in rows)   # nothing lost/duped
    assert M.ESCALATES_TO_OWNER == {"sentiment": True, "guidance_direction": True,
                                    RED: False}


def test_end_to_end_batch_files_carry_exactly_the_10_2_2_key_set(tmp_path, monkeypatch):
    """A full run against fabricated inputs: the emitted objects carry the five
    §10.2.2 keys and no metadata (no section_type, sector, cik, date, arm)."""
    g2 = tmp_path / "g2"
    (g2 / "batches").mkdir(parents=True)
    (g2 / "verdicts").mkdir()
    ids = ["E2CHK-aaa", "E2CHK-bbb", "E2CHK-ccc"]
    pd.DataFrame({"rank": [1, 2, 3], "batch": ["batch_01"] * 3,
                  "chunk_id": ids}   # §14.9: no `arm` column here
                 ).to_csv(g2 / "draw_g2.csv", index=False)
    (g2 / "draw_manifest.json").write_text(json.dumps(
        {"rate_red_flags": True,
         "inputs": {"data/f4/labels_e2_v1.parquet": {"sha256": "deadbeef"}}}))
    (g2 / "batches" / "batch_01.json").write_text(json.dumps(
        [{"chunk_id": c, "text": f"passage {c}"} for c in ids]))
    (g2 / "verdicts" / "rater_a_batch01.json").write_text(json.dumps([
        {"chunk_id": "E2CHK-aaa", "sentiment": "NEGATIVE",     # contested
         "guidance_direction": "NONE", "red_flags": [], "reason": "r"},
        {"chunk_id": "E2CHK-bbb", "sentiment": "POSITIVE",     # sentiment agrees
         "guidance_direction": "LOWERED",                      # guidance contested
         "red_flags": [["DEMAND_WEAKNESS", "REALIZED"]], "reason": "r"},
        {"chunk_id": "E2CHK-ccc", "sentiment": "NEUTRAL",      # RISK_FACTORS: masked
         "guidance_direction": "RAISED", "red_flags": [], "reason": "r"}]))

    labels = tmp_path / "labels.parquet"
    pd.DataFrame({
        "chunk_id": ids,
        "sentiment": ["POSITIVE", "POSITIVE", "NEUTRAL"],
        "guidance_direction": ["NONE", "RAISED", "NONE"],
        "red_flags": [[], [{"category": "DEMAND_WEAKNESS", "modality": "REALIZED"}], []],
    }).to_parquet(labels)
    chunks = tmp_path / "chunks.parquet"
    pd.DataFrame({"chunk_id": ids,
                  "section_type": ["MDA", "EX99_PRESS_RELEASE", "RISK_FACTORS"]}
                 ).to_parquet(chunks)
    monkeypatch.setattr(M, "G2", g2)
    monkeypatch.setattr(M, "LABELS", labels)
    monkeypatch.setattr(M, "CHUNKS", chunks)

    assert M.main([]) == 0
    out = g2 / "adjudicator_batches"
    files = sorted(p.name for p in out.glob("adj_batch_*.json"))
    assert files == ["adj_batch_01.json"]
    objs = json.loads((out / "adj_batch_01.json").read_text())

    assert [(o["chunk_id"], o["field"]) for o in objs] == [
        ("E2CHK-aaa", "sentiment"), ("E2CHK-bbb", "guidance_direction")]
    for o in objs:
        assert tuple(o) == M.ADJ_KEYS == ("chunk_id", "field", "text",
                                          "stored_label", "rater_label")
        assert not ({"section_type", "home_sector", "home_cik", "home_filing_date",
                     "home_company_name", "arm", "batch", "distress_tier"} & set(o))
        assert o["text"] == f"passage {o['chunk_id']}"
    # The design pins that key set literally; if the design moves, this fails.
    design = (G2 / "G2_SPOTCHECK_design.md").read_text()
    assert ('`{"chunk_id","field","text","stored_label","rater_label"}`' in design)

    man = json.loads((out / "adj_manifest_g2.json").read_text())
    assert man["contested_by_field"] == {"sentiment": 1, "guidance_direction": 1,
                                         "red_flags": 0}
    assert man["cells_by_field"]["sentiment"]["masked"] == 1        # the RF chunk
    assert man["escalates_to_owner"][RED] is False
    assert (man["api_calls"], man["gpu_seconds"], man["network_calls"]) == (0, 0, 0)
    assert man["inputs_read_only_sha256"][str(labels)] == M.sha256_file(labels)

    # A changed frame is a new pre-registration, not a re-run: hard-fail.
    (g2 / "draw_manifest.json").write_text(json.dumps(
        {"rate_red_flags": True, "inputs": {str(labels): {"sha256": "0" * 64}}}))
    with pytest.raises(AssertionError, match="new pre-registration"):
        M.main([])


def test_exits_cleanly_and_writes_nothing_when_verdicts_are_absent(tmp_path,
                                                                   monkeypatch, capsys):
    g2 = tmp_path / "g2"
    (g2 / "batches").mkdir(parents=True)
    pd.DataFrame({"rank": [1], "batch": ["batch_01"],
                  "chunk_id": ["E2CHK-aaa"]}).to_csv(g2 / "draw_g2.csv", index=False)
    (g2 / "draw_manifest.json").write_text(json.dumps({"rate_red_flags": True}))
    monkeypatch.setattr(M, "G2", g2)

    assert M.main([]) == 0
    assert "no verdicts yet" in capsys.readouterr().out
    assert not (g2 / "adjudicator_batches").exists()

    # ... and the same before the draw itself exists.
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setattr(M, "G2", empty)
    assert M.main([]) == 0
    assert "no draw yet" in capsys.readouterr().out


def test_selftest_passes():
    assert M.main(["--selftest"]) == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
