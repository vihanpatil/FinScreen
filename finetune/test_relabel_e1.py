#!/usr/bin/env python3
"""Offline tests for relabel_e1.py — no model, no GPU, no network, $0.

Run with the SYSTEM python3 (needs pandas/pyarrow, which .mlx_venv lacks):

    python3 -m pytest finetune/test_relabel_e1.py -q

Everything that touches a real artifact reads it READ-ONLY. Nothing here writes
outside pytest's tmp_path — in particular data/labels.parquet is never opened
for writing anywhere in this module or in relabel_e1.py.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import eval as ev
import relabel_e1 as rl


# --- student_label_row: the journal -> label-columns mapping -----------------

def _rec(raw, **kw):
    base = {
        "chunk_id": "CHK-test", "split": "train", "raw_output": raw,
        "prompt_sha256": "abc", "prompt_tokens": 100, "generation_tokens": 20,
        "finish_reason": "stop", "latency_s": 1.5,
        "generated_utc": "2026-08-25T00:00:00+00:00",
    }
    base.update(kw)
    return base


def test_clean_output_maps_to_label_columns():
    raw = ('{"sentiment": "NEGATIVE", "guidance_direction": "LOWERED", '
           '"red_flags": [{"category": "DEMAND_WEAKNESS", "modality": "REALIZED"}]}')
    row = rl.student_label_row(_rec(raw))
    assert row["parse_ok"] and row["schema_valid"]
    assert row["sentiment"] == "NEGATIVE"
    assert row["guidance_direction"] == "LOWERED"
    assert row["red_flags"] == [{"category": "DEMAND_WEAKNESS", "modality": "REALIZED"}]
    assert row["parse_error"] is None
    assert row["raw_label_json"] == raw
    assert row["api_result_type"] == "student_local_mlx"
    assert row["stop_reason"] == "stop" and row["output_tokens"] == 20


def test_omitted_fields_stay_null_not_defaulted():
    """The applicability matrix is encoded by which fields the model emits.
    An omitted field must be null, never back-filled with a guess."""
    row = rl.student_label_row(_rec('{"red_flags": []}'))
    assert row["parse_ok"] and row["schema_valid"]
    assert row["sentiment"] is None
    assert row["guidance_direction"] is None
    assert row["red_flags"] == []


def test_guidance_none_is_preserved_verbatim():
    """The missing->NONE post-rule is PROPOSED, not adopted: raw output only."""
    row = rl.student_label_row(_rec('{"sentiment": "NEUTRAL", "guidance_direction": "NONE", "red_flags": []}'))
    assert row["guidance_direction"] == "NONE"


def test_unparseable_output_is_recorded_not_dropped():
    row = rl.student_label_row(_rec("I think this passage is neutral."))
    assert row["parse_ok"] is False
    assert row["schema_valid"] is False
    assert row["parse_error"].startswith("json_decode_error")
    assert row["sentiment"] is None and row["red_flags"] == []
    assert row["raw_label_json"] == "I think this passage is neutral."


def test_out_of_taxonomy_entries_are_dropped_and_flagged():
    raw = ('{"sentiment": "POSITIVE", "red_flags": ['
           '{"category": "CYBER_ATTACK", "modality": "REALIZED"}, '
           '{"category": "MARGIN_COST_PRESSURE", "modality": "SPECULATIVE"}, '
           '{"category": "MARGIN_COST_PRESSURE", "modality": "REALIZED"}]}')
    row = rl.student_label_row(_rec(raw))
    assert row["parse_ok"] is True
    assert row["schema_valid"] is False
    assert row["red_flags"] == [{"category": "MARGIN_COST_PRESSURE", "modality": "REALIZED"}]
    assert "bad_enum:red_flag_category" in row["schema_issues"]
    assert "bad_enum:red_flag_modality" in row["schema_issues"]


def test_distress_tier_is_always_empty():
    """HANDOFF §7: never a training target. If the model volunteers one it is a
    schema violation and is still not stored as a label."""
    raw = '{"sentiment": "NEUTRAL", "distress_tier": [{"category": "GOING_CONCERN"}], "red_flags": []}'
    row = rl.student_label_row(_rec(raw))
    assert row["distress_tier"] == []
    assert row["schema_valid"] is False
    assert "extra_key:distress_tier" in row["schema_issues"]


def test_bad_enum_sentiment_is_not_stored_as_a_label():
    row = rl.student_label_row(_rec('{"sentiment": "VERY_POSITIVE", "red_flags": []}'))
    assert row["sentiment"] is None
    assert row["schema_valid"] is False


# --- resume semantics --------------------------------------------------------

def test_torn_final_line_is_ignored_and_the_row_is_regenerated(tmp_path):
    journal = tmp_path / "j.jsonl"
    good = _rec('{"red_flags": []}', chunk_id="CHK-a", prompt_sha256="sha-a")
    with open(journal, "w") as f:
        f.write(json.dumps(good) + "\n")
        f.write('{"chunk_id": "CHK-b", "raw_out')  # kill -9 mid-write
    existing = ev.load_predictions(journal)
    assert set(existing) == {"CHK-a"}

    rows = [{"chunk_id": "CHK-a", "_prompt_sha256": "sha-a"},
            {"chunk_id": "CHK-b", "_prompt_sha256": "sha-b"}]
    todo = ev.select_rows_to_generate(rows, existing, journal)
    assert [r["chunk_id"] for r in todo] == ["CHK-b"]


def test_prompt_drift_under_a_resume_is_a_hard_stop(tmp_path):
    journal = tmp_path / "j.jsonl"
    with open(journal, "w") as f:
        f.write(json.dumps(_rec('{"red_flags": []}', chunk_id="CHK-a", prompt_sha256="OLD")) + "\n")
    existing = ev.load_predictions(journal)
    with pytest.raises(SystemExit):
        ev.select_rows_to_generate([{"chunk_id": "CHK-a", "_prompt_sha256": "NEW"}], existing, journal)


def test_appending_after_a_torn_line_does_not_swallow_the_next_row(tmp_path):
    """The bug the resume smoke caught: without the newline repair, the first
    appended record is glued onto the fragment and lost (9/10 instead of 10/10)."""
    journal = tmp_path / "j.jsonl"
    with open(journal, "w") as f:
        f.write(json.dumps(_rec("{}", chunk_id="CHK-a")) + "\n")
        f.write('{"chunk_id": "CHK-torn", "raw_ou')  # kill -9 mid-write

    assert rl.ensure_trailing_newline(journal) is True
    with open(journal, "a") as f:
        ev.append_prediction(f, _rec("{}", chunk_id="CHK-b"))
    assert set(ev.load_predictions(journal)) == {"CHK-a", "CHK-b"}

    # idempotent: a healthy journal is not touched
    before = ev.sha256_file(journal)
    assert rl.ensure_trailing_newline(journal) is False
    assert ev.sha256_file(journal) == before


def test_journal_progress_reports_completion(tmp_path):
    journal = tmp_path / "j.jsonl"
    with open(journal, "w") as f:
        for i in range(3):
            f.write(json.dumps(_rec("{}", chunk_id=f"CHK-{i}")) + "\n")
    assert rl.journal_progress(journal, 3)["complete"] is True
    p = rl.journal_progress(journal, 10)
    assert p["complete"] is False and p["n_rows"] == 3


# --- provenance over the REAL frozen artifacts -------------------------------

def test_sidecar_verifies_the_corpus_to_mlx_data_chain(tmp_path):
    """Pins the claim the whole run rests on: every rendered passage is a
    head-prefix of its labeling_corpus.parquet text, and the 6,746 rendered rows
    are exactly labels.parquet's labeled set."""
    sc = rl.write_sidecar(tmp_path)
    assert sc["verification"]["n_rows"] == rl.TARGET_ROWS
    assert sc["verification"]["n_passages_not_a_head_prefix"] == 0
    assert (sc["verification"]["n_passages_identical_to_corpus_text"]
            + sc["verification"]["n_passages_head_truncated_to_fit_2048"]) == rl.TARGET_ROWS
    assert sc["mlx_data"]["n_train"] == 5736 and sc["mlx_data"]["n_eval"] == 1010
    assert sc["labels_parquet"]["excluded_chunk_ids"] == ["CHK-8e69547e0900a8dd"]
    assert len(sc["order"]) == len(set(sc["order"])) == rl.TARGET_ROWS


def test_mlx_data_matches_the_epoch2_training_manifest():
    tman = json.loads(rl.DEFAULT_TRAIN_MANIFEST.read_text())
    assert ev.sha256_file(rl.MLX_TRAIN) == tman["data"]["files"]["train.jsonl"]["sha256"]
    assert ev.sha256_file(rl.MLX_VALID) == tman["data"]["files"]["valid.jsonl"]["sha256"]


def test_load_rows_is_corpus_ordered_and_split_tagged(tmp_path):
    sc = rl.write_sidecar(tmp_path)
    rows = rl.load_rows(sc, split="all", limit=25)
    assert [r["chunk_id"] for r in rows] == sc["order"][:25]
    assert all(r["split"] in ("train", "eval") for r in rows)
    assert all(set(r) >= {"instruction", "passage", "gold_text", "messages"} for r in rows)
    ev_rows = rl.load_rows(sc, split="eval", limit=5)
    assert all(r["split"] == "eval" for r in ev_rows)


def test_load_rows_refuses_moved_mlx_data(tmp_path):
    sc = rl.write_sidecar(tmp_path)
    sc["mlx_data"]["valid_jsonl_sha256"] = "0" * 64
    with pytest.raises(SystemExit):
        rl.load_rows(sc)


# --- the output artifact -----------------------------------------------------

def test_parquet_schema_is_drop_in_for_labels_parquet(tmp_path):
    import pandas as pd
    import pyarrow.parquet as pq

    sc = rl.write_sidecar(tmp_path)
    ids = sc["order"][:3]
    journal = tmp_path / "j.jsonl"
    with open(journal, "w") as f:
        for i, cid in enumerate(ids):
            raw = ('{"sentiment": "NEUTRAL", "red_flags": [{"category": "DEMAND_WEAKNESS", '
                   '"modality": "HYPOTHETICAL"}]}') if i == 0 else '{"red_flags": []}'
            f.write(json.dumps(_rec(raw, chunk_id=cid)) + "\n")

    out = tmp_path / "student.parquet"
    info = rl.build_parquet(journal, out, max_tokens=520)
    assert info["n_rows"] == 3

    frozen = pq.read_schema(rl.LABELS_PARQUET).remove_metadata()
    got = pq.read_schema(out).remove_metadata()
    # the first 31 fields must BE labels.parquet's schema, name and type
    assert list(got)[: len(frozen)] == list(frozen)
    assert [f.name for f in list(got)[len(frozen):]] == [
        "split", "passage_was_head_truncated", "prompt_tokens", "prompt_sha256",
        "latency_s", "schema_issues",
    ]

    # and a features.py-shaped read works over it
    df = pd.read_parquet(out)
    df = df[df["parse_ok"]]
    cats = [f["category"] for flags in df["red_flags"] for f in flags]
    assert cats == ["DEMAND_WEAKNESS"]
    assert set(df["chunk_id"]) == set(ids)
    assert (df["labeling_config"].str.contains("epoch2")).all()
    assert df["max_tokens_used"].eq(520).all()
    assert all(len(x) == 0 for x in df["distress_tier"])


def test_e1_labels_parquet_is_untouched(tmp_path):
    """The frozen artifact's hash must be identical before and after a build."""
    before = ev.sha256_file(rl.LABELS_PARQUET)
    sc = rl.write_sidecar(tmp_path)
    journal = tmp_path / "j.jsonl"
    with open(journal, "w") as f:
        f.write(json.dumps(_rec('{"red_flags": []}', chunk_id=sc["order"][0])) + "\n")
    rl.build_parquet(journal, tmp_path / "s.parquet", max_tokens=520)
    assert ev.sha256_file(rl.LABELS_PARQUET) == before


# --- summary helpers ---------------------------------------------------------

def test_guidance_post_rule_only_rewrites_missing_fields():
    rows = [
        {"chunk_id": "a", "gold": {"guidance_direction": "NONE"}},
        {"chunk_id": "b", "gold": {"guidance_direction": "RAISED"}},
        {"chunk_id": "c", "gold": {"sentiment": "NEUTRAL"}},  # not applicable: skipped
    ]
    preds = {
        "a": '{"red_flags": []}',                                  # missing -> NONE, agrees
        "b": '{"guidance_direction": "LOWERED", "red_flags": []}',  # real disagreement
        "c": '{"sentiment": "NEUTRAL", "red_flags": []}',
    }
    out = rl._guidance_post_rule(rows, preds)
    assert out["n"] == 2 and out["n_agree"] == 1
    assert out["n_rows_rewritten_missing_to_NONE"] == 1
    assert "NOT ADOPTED" in out["status"]


def test_reproduction_check_counts_byte_identity(tmp_path):
    ref = tmp_path / "ref.jsonl"
    with open(ref, "w") as f:
        f.write(json.dumps({"chunk_id": "a", "raw_output": '{"x": 1}'}) + "\n")
        f.write(json.dumps({"chunk_id": "b", "raw_output": '{"x": 2}'}) + "\n")
    records = {
        "a": {"raw_output": '{"x": 1}'},
        "b": {"raw_output": '{"x": 99}'},
        "c": {"raw_output": "{}"},  # not in the reference: not compared
    }
    out = rl.reproduction_check(records, ref)
    assert out["n_compared"] == 2 and out["n_identical"] == 1
    assert out["differing_examples"] == ["b"]


def test_caveats_name_the_memorization_and_teacher_agreement_limits():
    blob = " ".join(rl.CAVEATS)
    assert "memorization" in blob
    assert "not accuracy" in blob
    assert "distress_tier" in blob


# ===========================================================================
# H3v2 — the rubric-v1.2 analogue (--v12)
#
# Same 6,746 chunks, same frozen row order, same decoding, same resume
# machinery; different rendered data, teacher, adapter, training manifest,
# reference eval and output paths. Everything below is offline: no model, no
# GPU, no network. The v1.2 adapter and the v1.2 epoch-2 eval predictions do
# NOT have to exist for these to pass — those are checked at RELABEL time.
# ===========================================================================

V12_TRAIN_SHA = "396aef131bec0e5cffc22df94fe310e07a8e440d9d5a020b09772699a2931a43"
V12_VALID_SHA = "b74efdb326e9b862820453eecfa64307f460499cac0fd92562fdf91eb0b1126b"
TRAINING_INSTRUCTION_SHA = "ebc45a856bff58a562535867e5a1f4173519fe77c58a47b16bfa28e6eea8efe2"


def _resolved(argv):
    args = rl.build_parser().parse_args(argv)
    return rl.resolve_profile(args), args


@pytest.fixture(scope="module")
def v12_sidecar(tmp_path_factory):
    """One real v1.2 sidecar for the whole module (it reads 33 MB of JSONL)."""
    out = tmp_path_factory.mktemp("v12")
    return rl.write_sidecar(out, mlx_dir=rl.MLX_DATA_DIR_V12,
                            labels_parquet=rl.LABELS_PARQUET_V12, name_suffix="_v12")


# --- the profile: E1 must be byte-compatible, v1.2 must be the ratified set ---

def test_e1_defaults_are_unchanged_when_the_v12_flag_is_absent():
    """H3 ran with no path flags at all. Adding --v12 must not have moved a
    single default out from under that invocation."""
    resolved, _ = _resolved([])
    assert resolved == {
        "mlx_data_dir": str(rl.HERE / "mlx_data"),
        "labels_parquet": str(rl.REPO / "data" / "labels.parquet"),
        "adapter_path": str(rl.HERE / "checkpoints" / "qwen2.5-7b-finscreen-lora-mlx-epoch2"),
        "train_manifest": str(rl.HERE / "runs" / "2026-08-21-epoch2" / "manifest.json"),
        "reference_predictions": str(rl.HERE / "runs" / "2026-08-22-eval-epoch2" / "predictions.jsonl"),
        "out_dir": str(rl.REPO / "data" / "hardening"),
        "name_suffix": "",
        "run_id": "H3-e1-relabel-epoch2",
    }


def test_v12_profile_is_the_ratified_path_set():
    resolved, _ = _resolved(["--v12"])
    assert resolved == {
        "mlx_data_dir": str(rl.HERE / "mlx_data_v12"),
        "labels_parquet": str(rl.REPO / "data" / "labels_v12.parquet"),
        "adapter_path": str(rl.HERE / "checkpoints" / "qwen2.5-7b-finscreen-lora-mlx-v12-epoch2"),
        "train_manifest": str(rl.HERE / "runs" / "2026-08-27-v12-epoch2" / "manifest.json"),
        "reference_predictions": str(rl.HERE / "runs" / "2026-08-28-v12-eval-epoch2" / "predictions.jsonl"),
        "out_dir": str(rl.REPO / "data" / "hardening" / "h3v2"),
        "name_suffix": "_v12",
        "run_id": "H3v2-e1-relabel-v12-epoch2",
    }


def test_v12_flag_only_supplies_defaults_explicit_paths_win():
    """A segmented epoch 2 puts the final adapter somewhere else; the main
    session must be able to override without losing the rest of the profile."""
    resolved, _ = _resolved(["--v12", "--adapter-path", "/tmp/last-segment",
                             "--reference-predictions", "/tmp/p.jsonl"])
    assert resolved["adapter_path"] == "/tmp/last-segment"
    assert resolved["reference_predictions"] == "/tmp/p.jsonl"
    assert resolved["mlx_data_dir"] == str(rl.HERE / "mlx_data_v12")
    assert resolved["run_id"] == "H3v2-e1-relabel-v12-epoch2"


def test_artifact_names_never_collide_with_h3s_ruled_filenames():
    """H3's outputs are the record of a ruled measurement. The v1.2 run must
    not be able to land on any of those four names, even in the same dir."""
    h3 = {rl.SIDECAR_NAME, rl.JOURNAL_NAME, rl.PARQUET_NAME, rl.MANIFEST_NAME}
    v12 = {rl.artifact_name(n, "_v12") for n in h3}
    assert v12 == {
        "e1_relabel_sidecar_v12.json", "e1_relabel_student_v12.jsonl",
        "e1_relabel_student_v12.parquet", "e1_relabel_manifest_v12.json",
    }
    assert not (h3 & v12)
    assert {rl.artifact_name(n, "") for n in h3} == h3  # E1 names unchanged


# --- provenance over the real v1.2 artifacts ---------------------------------

def test_mlx_data_v12_matches_the_v12_training_manifests():
    """The relabel feeds the student the records the v1.2 trainer consumed.

    Epoch 1 and epoch 2 share identical data shas (same dataset, second pass),
    so either manifest validates the data. The epoch-2 manifest is re-checked
    at relabel time by preflight() against the files actually on disk.
    """
    assert ev.sha256_file(rl.MLX_DATA_DIR_V12 / "train.jsonl") == V12_TRAIN_SHA
    assert ev.sha256_file(rl.MLX_DATA_DIR_V12 / "valid.jsonl") == V12_VALID_SHA
    for manifest in (rl.HERE / "runs" / "2026-08-26-v12-epoch1" / "manifest.json",
                     rl.HERE / "runs" / "2026-08-27-v12-epoch2" / "manifest.json"):
        if not manifest.exists():
            continue
        files = json.loads(manifest.read_text())["data"]["files"]
        assert files["train.jsonl"]["sha256"] == V12_TRAIN_SHA, manifest
        assert files["valid.jsonl"]["sha256"] == V12_VALID_SHA, manifest


def test_v12_sidecar_verifies_the_corpus_to_mlx_data_v12_chain(v12_sidecar):
    sc = v12_sidecar
    assert sc["verification"]["n_rows"] == rl.TARGET_ROWS
    assert sc["verification"]["n_passages_not_a_head_prefix"] == 0
    # v1.2 truncates 52 (2 train + 50 eval); E1 truncated 51. A longer v1.2
    # answer leaves less room for the passage — see G1_repair_dataset.md §3.
    assert sc["verification"]["n_passages_head_truncated_to_fit_2048"] == 52
    assert sc["mlx_data"]["n_train"] == 5736 and sc["mlx_data"]["n_eval"] == 1010
    assert sc["mlx_data"]["dir"].endswith("mlx_data_v12")
    assert sc["instruction_sha256"] == TRAINING_INSTRUCTION_SHA
    # v1.2 LABELED the refusal chunk, but the frozen split still excludes it.
    assert sc["labels_parquet"]["n_labeled"] == 6747
    assert sc["labels_parquet"]["excluded_chunk_ids"] == ["CHK-8e69547e0900a8dd"]


def test_v12_and_e1_render_the_same_chunk_ids_in_the_same_frozen_order(v12_sidecar, tmp_path):
    """The split is frozen: same 6,746 rows, same canonical corpus order. If
    this ever fails, the two campaigns are not measuring the same corpus."""
    e1 = rl.write_sidecar(tmp_path)
    assert v12_sidecar["order"] == e1["order"]


def test_v12_prompts_differ_from_e1_only_by_the_documented_head_truncation():
    """Recorded, not hidden: 6,732/6,746 prompts are token-identical to E1's;
    14 (2 train / 12 eval) keep a different amount of passage because
    convert_to_mlx.py truncates to fit 2,048 INCLUDING the answer, and v1.2's
    answers differ in length. Only the passage TAIL moves."""
    e1 = {r["chunk_id"]: r for r in rl.read_mlx_rows(rl.MLX_DATA_DIR)}
    v12 = {r["chunk_id"]: r for r in rl.read_mlx_rows(rl.MLX_DATA_DIR_V12)}
    assert set(e1) == set(v12)

    differing = []
    for cid, a in e1.items():
        b = v12[cid]
        assert a["instruction"] == b["instruction"], cid   # the system turn never moves
        assert a["split"] == b["split"], cid
        if a["passage"] != b["passage"]:
            differing.append((cid, b["split"], len(b["passage"]) - len(a["passage"])))
            assert a["passage"].startswith(b["passage"]) or b["passage"].startswith(a["passage"]), cid

    assert len(differing) == 14
    assert sum(1 for _, s, _ in differing if s == "train") == 2
    assert sum(1 for _, s, _ in differing if s == "eval") == 12
    assert min(d for _, _, d in differing) == -505
    assert max(d for _, _, d in differing) == 33


# --- the v1.2 output artifact ------------------------------------------------

def _journal(path, ids, raws):
    with open(path, "w") as f:
        for cid, raw in zip(ids, raws):
            f.write(json.dumps(_rec(raw, chunk_id=cid)) + "\n")


def _build_v12(tmp_path, sidecar, raws):
    ids = sidecar["order"][: len(raws)]
    journal = tmp_path / "j.jsonl"
    _journal(journal, ids, raws)
    out = tmp_path / "student_v12.parquet"
    info = rl.build_parquet(
        journal, out, max_tokens=520,
        mlx_dir=rl.MLX_DATA_DIR_V12, labels_parquet=rl.LABELS_PARQUET_V12,
        run_id=rl.RUN_ID_V12, student="qwen2.5-7b-finscreen-lora-mlx-v12-epoch2",
        instruction_sha256=sidecar["instruction_sha256"],
    )
    return ids, out, info


def test_v12_parquet_copies_the_v12_schema_and_names_every_deviation(v12_sidecar, tmp_path):
    """v1.2's teacher schema is NOT v1.1's: 34 fields, not 31, in a different
    order, with `parse_error` typed `null` (every teacher row parsed). The copy
    must still be a copy, and each deviation must be named in the manifest
    rather than papered over."""
    import pyarrow.parquet as pq

    ids, out, info = _build_v12(
        tmp_path, v12_sidecar,
        ['{"sentiment": "NEUTRAL", "red_flags": []}', '{"red_flags": []}'],
    )
    teacher = pq.read_schema(rl.LABELS_PARQUET_V12).remove_metadata()
    got = list(pq.read_schema(out).remove_metadata())

    assert len(teacher) == 34 and info["n_columns"] == 40
    assert [f.name for f in got[:34]] == [f.name for f in teacher]
    # exactly one field differs from the teacher's, and it is the named repair
    assert [f.name for a, f in zip(teacher, got) if a != f] == ["parse_error"]
    assert info["null_typed_columns_widened_to_string"] == ["parse_error"]
    assert [f.name for f in got[34:]] == [
        "split", "passage_was_head_truncated", "prompt_tokens", "prompt_sha256",
        "latency_s", "schema_issues",
    ]
    # the three v1.2-only teacher columns a student run has no analogue for
    assert info["teacher_only_columns_filled_for_the_student"] == {
        "rubric_version": "v1.2",
        # the STUDENT's system turn is the training instruction, NOT the
        # teacher's 9,521-char labeling prompt (30605197...)
        "system_prompt_sha256": TRAINING_INSTRUCTION_SHA,
        "completion_batch_id": None,
    }
    assert "labels_v12.parquet" in info["schema_source"]


def test_a_parse_failure_survives_the_v12_null_typed_parse_error_column(v12_sidecar, tmp_path):
    """The load-bearing consequence of the widening: a null-typed arrow column
    cannot hold a string, so an un-widened copy would crash (or silently drop
    the diagnosis) on the first row the student fails to parse."""
    import pandas as pd

    ids, out, info = _build_v12(tmp_path, v12_sidecar,
                                ["I think this passage is neutral.", '{"red_flags": []}'])
    assert info["parse_failures"] == 1
    df = pd.read_parquet(out)
    by_id = df.set_index("chunk_id")
    assert not by_id.loc[ids[0], "parse_ok"]
    assert by_id.loc[ids[0], "parse_error"].startswith("json_decode_error")
    assert by_id.loc[ids[1], "parse_error"] is None
    # a features.py-shaped read still works, and drops the failed row
    assert len(df[df["parse_ok"]]) == 1


def test_v12_run_id_and_labeling_config_travel_into_the_artifact(v12_sidecar, tmp_path):
    import pandas as pd

    ids, out, info = _build_v12(tmp_path, v12_sidecar, ['{"red_flags": []}'])
    df = pd.read_parquet(out)
    assert df["batch_id"].eq("H3v2-e1-relabel-v12-epoch2").all()
    assert df["labeling_config"].str.contains(
        "student=qwen2.5-7b-finscreen-lora-mlx-v12-epoch2").all()
    assert df["api_result_type"].eq("student_local_mlx").all()
    assert all(len(x) == 0 for x in df["distress_tier"])   # never a training target


def test_v12_labels_parquet_is_untouched(v12_sidecar, tmp_path):
    before = ev.sha256_file(rl.LABELS_PARQUET_V12)
    _build_v12(tmp_path, v12_sidecar, ['{"red_flags": []}'])
    assert ev.sha256_file(rl.LABELS_PARQUET_V12) == before


# --- honesty machinery -------------------------------------------------------

def test_agreement_is_scored_against_the_teacher_that_matches_the_data(v12_sidecar):
    """Feeding the v1.2 gold back as the student's output must agree at 1.0
    under mlx_data_v12 — i.e. the gold side follows --mlx-data-dir. Scoring the
    SAME outputs against v1.1's gold does not, which is the whole reason the
    two campaigns' numbers are instrument-vs-instrument."""
    rows = rl.read_mlx_rows(rl.MLX_DATA_DIR_V12)
    pick = [r for r in rows if r["split"] == "eval"][:5] + \
           [r for r in rows if r["split"] == "train"][:5]
    records = {r["chunk_id"]: {"raw_output": r["gold_text"], "split": r["split"]} for r in pick}

    same = rl.agreement_summary(records, mlx_dir=rl.MLX_DATA_DIR_V12)
    assert same["n_scored"] == 10
    rf = same["pooled_MEMORIZATION_INFLATED"]["red_flags"]
    assert rf["exact_set_match_category_modality"]["rate"] == 1.0
    assert "per_category" in rf            # both bases, always
    assert same["eval_ONLY_UNBIASED_SLICE"]["red_flags"][
        "exact_set_match_category_modality"]["n"] == 5

    cross = rl.agreement_summary(records, mlx_dir=rl.MLX_DATA_DIR)
    assert cross["pooled_MEMORIZATION_INFLATED"]["red_flags"][
        "exact_set_match_category_modality"]["rate"] < 1.0


def _ref(path, mapping):
    with open(path, "w") as f:
        for cid, raw in mapping.items():
            f.write(json.dumps({"chunk_id": cid, "raw_output": raw}) + "\n")
    return path


def test_reproduction_check_is_loud_when_the_reference_is_missing(tmp_path):
    """The v1.2 epoch-2 eval predictions do not exist until that eval runs. A
    missing reference must read as DID NOT RUN, never as a quiet pass."""
    out = rl.reproduction_check({"a": {"raw_output": "{}"}}, tmp_path / "nope.jsonl")
    assert out["verified"] is False
    assert "MISSING_REFERENCE" in out["STATUS"]
    assert "n_identical" not in out and "n_compared" not in out

    ok = rl.reproduction_check({"a": {"raw_output": "{}"}},
                               _ref(tmp_path / "same.jsonl", {"a": "{}"}))
    assert ok["verified"] is True and ok["n_identical"] == 1

    bad = rl.reproduction_check({"a": {"raw_output": "{}"}},
                                _ref(tmp_path / "diff.jsonl", {"a": '{"x": 1}'}))
    assert bad["verified"] is False and bad["n_differing"] == 1


def test_the_extended_runner_still_rebuilds_h3s_ruled_parquet_byte_for_byte(tmp_path):
    """The strongest regression proof available: re-run build_parquet over H3's
    real 6,746-row journal with every new argument left at its default, and the
    result must hash to the parquet H3 shipped and quant-modeler ruled on
    (`data/hardening/e1_relabel_manifest.json`). Writes only to tmp_path — H3's
    artifacts are read, never touched."""
    journal = rl.REPO / "data" / "hardening" / "e1_relabel_student.jsonl"
    manifest = rl.REPO / "data" / "hardening" / "e1_relabel_manifest.json"
    if not (journal.exists() and manifest.exists()):
        pytest.skip("H3's run artifacts are not on this machine")

    recorded = json.loads(manifest.read_text())["parquet"]
    info = rl.build_parquet(journal, tmp_path / "rebuilt.parquet", max_tokens=520)

    assert info["sha256"] == recorded["sha256"] == (
        "5de9230bed706b92edb361bbd371c3538ccad85c5918b440924e4259f8a9adbd")
    assert info["n_rows"] == 6746 and info["n_columns"] == 37
    assert info["null_typed_columns_widened_to_string"] == []   # v1.1 needs no repair
    assert info["teacher_only_columns_filled_for_the_student"] == {}
    assert ev.sha256_file(rl.REPO / "data" / "hardening" / "e1_relabel_student.parquet") == \
        recorded["sha256"]


def test_v12_caveats_carry_the_cross_rubric_framing():
    """The one caveat H3 could not have: two teachers, two rubrics."""
    e1 = rl.caveats_for(rl.LABELS_PARQUET)
    v12 = rl.caveats_for(rl.LABELS_PARQUET_V12)
    assert e1 == rl.CAVEATS
    assert v12[: len(rl.CAVEATS)] == rl.CAVEATS
    blob = " ".join(v12[len(rl.CAVEATS):])
    assert "labels_v12.parquet" in blob
    assert "INSTRUMENT-VS-INSTRUMENT" in blob
    assert "27.48%" in blob          # the measured label shift, not a vibe
    assert "14 of the 6,746 prompts" in blob
    # and the standing ones are still there
    joined = " ".join(v12)
    assert "memorization" in joined and "not accuracy" in joined
    assert "8K_BODY" in joined and "WITHDRAWN" in joined
