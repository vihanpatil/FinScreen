"""Offline tests for eval.py's dataset-path arguments (--mlx-data-dir /
--prepared-dir / --splits-eval-parquet), added 2026-08-26 so the rubric-v1.2
re-eval can point at finetune/mlx_data_v12 + finetune/prepared_v12.

Two things these must guarantee:
  1. **E1 invocations stay byte-compatible.** Omitting the new flags must
     resolve to exactly the paths eval.py used before.
  2. **The fail-safe still fires.** A wrong --mlx-data-dir must SystemExit on
     the training manifest's sha check BEFORE any model is loaded or any token
     is generated.

NO MODEL IS LOADED AND NO GPU WORK HAPPENS HERE.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import eval as ev  # noqa: E402


# --------------------------------------------------------------------------
# fixtures: a tiny self-consistent (mlx_data, prepared) pair on disk
# --------------------------------------------------------------------------

INSTRUCTION = "INSTRUCTION TEXT, byte-identical everywhere."


def write_dataset(root: Path, chunk_ids, instruction=INSTRUCTION, passage_suffix="",
                  sentiment="NEUTRAL"):
    """Build mlx_data/{train,valid}.jsonl + prepared/eval.jsonl that agree.

    `sentiment` stands in for "a different rubric's answer" — the real v1.1 vs
    v1.2 difference is in the assistant JSON, on ~30% of rows."""
    mlx = root / "mlx_data"
    prep = root / "prepared"
    mlx.mkdir(parents=True, exist_ok=True)
    prep.mkdir(parents=True, exist_ok=True)

    def rec(cid):
        passage = f"passage for {cid}{passage_suffix}"
        answer = json.dumps({"sentiment": sentiment, "red_flags": []})
        return passage, answer

    with open(mlx / "valid.jsonl", "w") as fv, open(prep / "eval.jsonl", "w") as fp:
        for cid in chunk_ids:
            passage, answer = rec(cid)
            fv.write(json.dumps({"chunk_id": cid, "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": passage},
                {"role": "assistant", "content": answer},
            ]}) + "\n")
            fp.write(json.dumps({
                "chunk_id": cid, "instruction": instruction,
                "input": passage, "output": answer,
            }) + "\n")

    with open(mlx / "train.jsonl", "w") as ft:
        ft.write(json.dumps({"chunk_id": "CHK-train0", "messages": [
            {"role": "system", "content": instruction},
            {"role": "user", "content": "train passage"},
            {"role": "assistant", "content": "{}"},
        ]}) + "\n")
    return mlx, prep


def make_manifest(path: Path, mlx_dir: Path) -> Path:
    """A minimal training manifest naming that mlx dir's valid.jsonl sha."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "run_id": "test-run",
        "model": {"resolved_snapshot_path": "/nonexistent/model", "weights_sha256": "abc"},
        "resolved_config": {"adapter_path": "/nonexistent/adapter"},
        "data": {
            "dir": str(mlx_dir),
            "files": {"valid.jsonl": {"sha256": ev.sha256_file(mlx_dir / "valid.jsonl")}},
        },
    }))
    return path


def make_args(**over) -> SimpleNamespace:
    base = dict(
        backend="mlx", train_manifest=None, model=None, adapter_path=None,
        out_dir=None, max_tokens=520, limit=None, resume=True, score_only=False,
        progress_every=25, section_types=str(ev.SECTION_TYPES_JSON),
        skip_train_instruction_check=False,
        mlx_data_dir=None, prepared_dir=None,
        splits_eval_parquet=str(ev.SPLITS_EVAL_PARQUET),
    )
    base.update(over)
    return SimpleNamespace(**base)


# --------------------------------------------------------------------------
# 1. E1 defaults are byte-compatible
# --------------------------------------------------------------------------

def test_module_constants_unchanged():
    assert ev.MLX_DATA_DIR == HERE / "mlx_data"
    assert ev.MLX_VALID_JSONL == HERE / "mlx_data" / "valid.jsonl"
    assert ev.EVAL_JSONL == HERE / "prepared" / "eval.jsonl"
    assert ev.SPLITS_EVAL_PARQUET == HERE / "splits" / "eval.parquet"


class _Sentinel(Exception):
    pass


def _capture_resolved_paths(monkeypatch, args, tman_dir):
    """Run run_real_eval far enough to see which paths it hands load_eval_rows."""
    seen = {}

    def fake(mlx_valid, prepared_eval, verify_train_instruction, mlx_train):
        seen.update(mlx_valid=Path(mlx_valid), prepared_eval=Path(prepared_eval),
                    mlx_train=Path(mlx_train), verify=verify_train_instruction)
        raise _Sentinel()

    monkeypatch.setattr(ev, "load_eval_rows", fake)
    with pytest.raises(_Sentinel):
        ev.run_real_eval(args)
    return seen


def test_omitting_the_new_flags_resolves_to_the_exact_e1_paths(monkeypatch, tmp_path):
    """THE byte-compatibility pin: a command line that never mentions the new
    flags must hand load_eval_rows exactly what eval.py used before this change
    — mlx_data/valid.jsonl, prepared/eval.jsonl, mlx_data/train.jsonl."""
    right, _ = write_dataset(tmp_path / "right", ["CHK-x"])
    tman = make_manifest(tmp_path / "run" / "manifest.json", right)
    seen = _capture_resolved_paths(
        monkeypatch,
        make_args(train_manifest=str(tman), out_dir=str(tmp_path / "out")),
        right,
    )
    assert seen["mlx_valid"] == ev.MLX_VALID_JSONL
    assert seen["prepared_eval"] == ev.EVAL_JSONL
    assert seen["mlx_train"] == ev.MLX_DATA_DIR / "train.jsonl"
    assert seen["verify"] is True


def test_the_new_flags_redirect_all_three_paths_together(monkeypatch, tmp_path):
    """--mlx-data-dir must move train.jsonl too, not just valid.jsonl —
    otherwise the instruction cross-check would compare v1.2 eval against E1
    train."""
    right, _ = write_dataset(tmp_path / "right", ["CHK-x"])
    tman = make_manifest(tmp_path / "run" / "manifest.json", right)
    v12_mlx = tmp_path / "v12" / "mlx_data"
    v12_prep = tmp_path / "v12" / "prepared"
    seen = _capture_resolved_paths(
        monkeypatch,
        make_args(train_manifest=str(tman), out_dir=str(tmp_path / "out"),
                  mlx_data_dir=str(v12_mlx), prepared_dir=str(v12_prep)),
        right,
    )
    assert seen["mlx_valid"] == v12_mlx / "valid.jsonl"
    assert seen["mlx_train"] == v12_mlx / "train.jsonl"
    assert seen["prepared_eval"] == v12_prep / "eval.jsonl"


def test_load_eval_rows_signature_defaults_are_the_e1_paths():
    import inspect
    sig = inspect.signature(ev.load_eval_rows)
    assert sig.parameters["mlx_valid"].default == ev.MLX_VALID_JSONL
    assert sig.parameters["prepared_eval"].default == ev.EVAL_JSONL
    assert sig.parameters["verify_train_instruction"].default is True
    assert sig.parameters["mlx_train"].default is None


def test_default_train_check_path_is_beside_the_valid_file(tmp_path):
    """mlx_train=None must resolve to train.jsonl NEXT TO the valid.jsonl being
    evaluated. For E1's defaults that is exactly the old MLX_DATA_DIR path; for
    a v1.2 run it is mlx_data_v12/train.jsonl, not E1's."""
    mlx, prep = write_dataset(tmp_path / "v12", ["CHK-a", "CHK-b"])
    rows, prov = ev.load_eval_rows(
        mlx_valid=mlx / "valid.jsonl", prepared_eval=prep / "eval.jsonl",
        verify_train_instruction=True,
    )
    assert len(rows) == 2
    assert prov["instruction_byte_identical_to_train"] is True, (
        "the train file beside the given valid.jsonl should have been found and checked"
    )


def test_e1_defaults_still_load_the_real_e1_dataset():
    if not ev.MLX_VALID_JSONL.exists():
        pytest.skip("E1 mlx_data not present on this box")
    rows, prov = ev.load_eval_rows(verify_train_instruction=False)
    assert len(rows) == 1010
    assert prov["eval_rows_file"] == str(ev.MLX_VALID_JSONL)
    assert prov["prepared_eval_file"] == str(ev.EVAL_JSONL)


# --------------------------------------------------------------------------
# 2. the new flags actually redirect
# --------------------------------------------------------------------------

def test_explicit_dirs_load_the_other_dataset(tmp_path):
    mlx, prep = write_dataset(tmp_path / "v12", ["CHK-x"])
    rows, prov = ev.load_eval_rows(
        mlx_valid=mlx / "valid.jsonl", prepared_eval=prep / "eval.jsonl",
        verify_train_instruction=False,
    )
    assert [r["chunk_id"] for r in rows] == ["CHK-x"]
    assert prov["eval_rows_file"] == str(mlx / "valid.jsonl")


def test_mlx_train_override_is_honoured(tmp_path):
    mlx, prep = write_dataset(tmp_path / "a", ["CHK-x"])
    other, _ = write_dataset(tmp_path / "b", ["CHK-x"], instruction="A DIFFERENT INSTRUCTION")
    with pytest.raises(AssertionError, match="TRAIN rows have a system instruction"):
        ev.load_eval_rows(
            mlx_valid=mlx / "valid.jsonl", prepared_eval=prep / "eval.jsonl",
            verify_train_instruction=True, mlx_train=other / "train.jsonl",
        )


def test_crossing_the_two_datasets_is_caught_on_the_gold_answer(tmp_path):
    """v1.2 valid.jsonl against E1 prepared/eval.jsonl (or vice versa) must not
    silently score. The real v1.1/v1.2 difference is the assistant JSON, and
    that is what the gold cross-check catches."""
    mlx_a, _ = write_dataset(tmp_path / "a", ["CHK-x"], sentiment="NEUTRAL")
    _, prep_b = write_dataset(tmp_path / "b", ["CHK-x"], sentiment="NEGATIVE")
    with pytest.raises(AssertionError, match="gold answer differs"):
        ev.load_eval_rows(
            mlx_valid=mlx_a / "valid.jsonl", prepared_eval=prep_b / "eval.jsonl",
            verify_train_instruction=False,
        )


def test_a_passage_that_is_not_a_head_prefix_is_a_hard_error(tmp_path):
    """A shorter prepared passage than the rendered one cannot be explained by
    convert_to_mlx's head-truncation, so it must not be tolerated."""
    mlx_a, _ = write_dataset(tmp_path / "a", ["CHK-x"], passage_suffix=" EXTRA TAIL")
    _, prep_b = write_dataset(tmp_path / "b", ["CHK-x"])
    with pytest.raises(AssertionError):
        ev.load_eval_rows(
            mlx_valid=mlx_a / "valid.jsonl", prepared_eval=prep_b / "eval.jsonl",
            verify_train_instruction=False,
        )


def test_a_genuine_head_truncation_is_tolerated_and_counted(tmp_path):
    """The legitimate case: the rendered passage is a head-prefix of the
    prepared one (convert_to_mlx truncated it to fit 2048)."""
    mlx_a, _ = write_dataset(tmp_path / "a", ["CHK-x"])
    _, prep_b = write_dataset(tmp_path / "b", ["CHK-x"], passage_suffix=" DROPPED TAIL")
    rows, prov = ev.load_eval_rows(
        mlx_valid=mlx_a / "valid.jsonl", prepared_eval=prep_b / "eval.jsonl",
        verify_train_instruction=False,
    )
    assert len(rows) == 1
    assert prov["n_passages_head_truncated_to_fit_2048"] == 1


def test_a_chunk_missing_from_prepared_is_a_hard_error(tmp_path):
    mlx, _ = write_dataset(tmp_path / "a", ["CHK-x", "CHK-y"])
    _, prep = write_dataset(tmp_path / "b", ["CHK-x"])
    with pytest.raises(AssertionError, match="but not in"):
        ev.load_eval_rows(
            mlx_valid=mlx / "valid.jsonl", prepared_eval=prep / "eval.jsonl",
            verify_train_instruction=False,
        )


# --------------------------------------------------------------------------
# 3. THE FAIL-SAFE: a wrong --mlx-data-dir stops before generation
# --------------------------------------------------------------------------

def _run_real_eval_expecting_exit(args):
    """run_real_eval must raise SystemExit at the sha check. If it ever got
    past that point it would try to import mlx_lm and load a model from
    /nonexistent — so any other exception type is also a failure of the
    'stops before generation' contract, and we assert the message."""
    with pytest.raises(SystemExit) as exc:
        ev.run_real_eval(args)
    return str(exc.value)


def test_wrong_mlx_data_dir_systemexits_on_the_sha_check(tmp_path):
    right, prep_r = write_dataset(tmp_path / "right", ["CHK-x", "CHK-y"])
    wrong, prep_w = write_dataset(tmp_path / "wrong", ["CHK-x", "CHK-y"],
                                  passage_suffix=" DIFFERENT")
    tman = make_manifest(tmp_path / "run" / "manifest.json", right)

    msg = _run_real_eval_expecting_exit(make_args(
        train_manifest=str(tman),
        out_dir=str(tmp_path / "out"),
        mlx_data_dir=str(wrong), prepared_dir=str(prep_w),
        skip_train_instruction_check=True,
    ))
    assert "does not match the training manifest" in msg
    assert str(wrong / "valid.jsonl") in msg, "the message must name the file actually loaded"
    assert str(right) in msg, "the message must name the dataset the manifest expects"


def test_wrong_dir_exits_before_predictions_are_written(tmp_path):
    right, _ = write_dataset(tmp_path / "right", ["CHK-x"])
    wrong, prep_w = write_dataset(tmp_path / "wrong", ["CHK-x"], passage_suffix=" X")
    tman = make_manifest(tmp_path / "run" / "manifest.json", right)
    out = tmp_path / "out"

    _run_real_eval_expecting_exit(make_args(
        train_manifest=str(tman), out_dir=str(out),
        mlx_data_dir=str(wrong), prepared_dir=str(prep_w),
        skip_train_instruction_check=True,
    ))
    assert not (out / "predictions.jsonl").exists(), "no generation may have happened"
    assert not (out / "metrics.json").exists()


def test_matching_dir_passes_the_sha_check_and_fails_later_on_the_model(tmp_path):
    """Positive control: with the RIGHT dir the sha check passes, so the run
    proceeds past it (and then dies on the fake model path). This proves the
    guard is not simply always-failing."""
    right, prep_r = write_dataset(tmp_path / "right", ["CHK-x"])
    tman = make_manifest(tmp_path / "run" / "manifest.json", right)

    with pytest.raises(BaseException) as exc:
        ev.run_real_eval(make_args(
            train_manifest=str(tman), out_dir=str(tmp_path / "out"),
            mlx_data_dir=str(right), prepared_dir=str(prep_r),
            skip_train_instruction_check=True,
        ))
    assert "does not match the training manifest" not in str(exc.value)


# --------------------------------------------------------------------------
# 4. --write-section-types source override
# --------------------------------------------------------------------------

def test_write_section_types_defaults_to_e1_splits():
    import inspect
    sig = inspect.signature(ev.write_section_types)
    assert sig.parameters["out_path"].default == ev.SECTION_TYPES_JSON
    assert sig.parameters["source"].default == ev.SPLITS_EVAL_PARQUET


def test_write_section_types_from_the_v12_split_reproduces_the_e1_sidecar():
    """Eval membership is frozen and section_type is corpus metadata, so the
    v1.2 eval split must give a mapping identical to the shipped sidecar."""
    v12 = HERE / "splits_v12" / "eval.parquet"
    if not (v12.exists() and ev.SECTION_TYPES_JSON.exists()):
        pytest.skip("v1.2 splits or the sidecar are not present on this box")
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json") as tf:
        payload = ev.write_section_types(Path(tf.name), v12)
    shipped = json.loads(ev.SECTION_TYPES_JSON.read_text())["section_type_by_chunk_id"]
    assert payload["section_type_by_chunk_id"] == shipped
    assert payload["_source"] == str(v12)


# --------------------------------------------------------------------------
# 5. the CLI surface itself
# --------------------------------------------------------------------------

def test_cli_help_lists_the_new_flags():
    import subprocess
    out = subprocess.run(
        [sys.executable, str(HERE / "eval.py"), "--help"],
        capture_output=True, text=True,
    ).stdout
    for flag in ("--mlx-data-dir", "--prepared-dir", "--splits-eval-parquet"):
        assert flag in out, f"{flag} missing from --help"
