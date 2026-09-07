"""Targeted offline tests for the train_qlora.py flags the rubric-v1.2 retrain
adds: --expect-train/--expect-eval, the LR-schedule overrides, and
--authorization. No MLX, no GPU, no model weights.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

import train_qlora as T

HERE = Path(__file__).resolve().parent


def make_data_dir(tmp_path: Path, n_train: int, n_valid: int, with_report: bool = True) -> Path:
    d = tmp_path / "mlx_data_x"
    d.mkdir()
    for name, n in (("train.jsonl", n_train), ("valid.jsonl", n_valid)):
        (d / name).write_text("".join('{"chunk_id": "c%d"}\n' % i for i in range(n)))
    if with_report:
        (d / "conversion_report.json").write_text(json.dumps({
            "splits": {
                "train": {"output_sha256": T.sha256_file(d / "train.jsonl")},
                "eval": {"output_sha256": T.sha256_file(d / "valid.jsonl")},
            }
        }))
    return d


def make_args(tmp_path: Path, data_dir: Path, **over) -> SimpleNamespace:
    model_dir = tmp_path / "model_snapshot"
    model_dir.mkdir(exist_ok=True)
    base = dict(
        mlx_config=str(HERE / "config_mlx.yaml"),
        run_dir=str(tmp_path / "run"),
        tag="v12-test",
        data_dir=str(data_dir),
        model=str(model_dir),
        weights_sha256="deadbeef",
        adapter_path=str(tmp_path / "adapter"),
        iters=None, save_every=None, steps_per_report=None,
        steps_per_eval=None, val_batches=None, resume_adapter_file=None,
        lr_peak=None, lr_decay_steps=None, lr_warmup=None,
        expect_train=5736, expect_eval=1010, authorization=None,
    )
    base.update(over)
    return SimpleNamespace(**base)


# ------------------------------------------------------------ row counts ----

def test_default_expected_rows_still_5736_1010():
    assert T.EXPECTED_ROWS == {"train.jsonl": 5736, "valid.jsonl": 1010}


def test_expect_train_5735_accepts_the_v12_dataset(tmp_path):
    d = make_data_dir(tmp_path, 5735, 1010)
    built = T.build_mlx_run(make_args(tmp_path, d, expect_train=5735, iters=5735))
    assert built["manifest"]["data"]["files"]["train.jsonl"]["rows"] == 5735
    assert built["manifest"]["data"]["expected_rows"] == {"train.jsonl": 5735, "valid.jsonl": 1010}
    assert built["manifest"]["derived"]["epochs"] == 1.0
    assert built["manifest"]["derived"]["optimizer_updates"] == 5735 // 4


def test_the_v12_dataset_is_REJECTED_under_the_e1_default(tmp_path):
    """The guard still guards: 5,735 rows must not sail through as if it were E1."""
    d = make_data_dir(tmp_path, 5735, 1010)
    with pytest.raises(ValueError, match="expected 5736"):
        T.build_mlx_run(make_args(tmp_path, d))


def test_eval_split_shrinking_is_still_a_hard_stop(tmp_path):
    d = make_data_dir(tmp_path, 5735, 1009)
    with pytest.raises(ValueError, match="expected 1010"):
        T.build_mlx_run(make_args(tmp_path, d, expect_train=5735))


def test_one_epoch_cap_tracks_the_expected_train_count(tmp_path):
    d = make_data_dir(tmp_path, 5735, 1010)
    with pytest.raises(ValueError, match="exceeds one epoch"):
        T.build_mlx_run(make_args(tmp_path, d, expect_train=5735, iters=5736))


# --------------------------------------------------------- lr schedule ----

def test_lr_flags_override_the_resolved_config_only(tmp_path):
    d = make_data_dir(tmp_path, 5735, 1010)
    built = T.build_mlx_run(make_args(
        tmp_path, d, expect_train=5735, iters=5735,
        lr_peak=1.0e-4, lr_decay_steps=1413, lr_warmup=20,
    ))
    cfg = built["cfg"]
    assert cfg["learning_rate"] == 1.0e-4
    assert cfg["lr_schedule"]["arguments"] == [1.0e-4, 1413]
    assert cfg["lr_schedule"]["warmup"] == 20
    on_disk = yaml.safe_load(Path(built["config"]).read_text())
    assert on_disk["lr_schedule"]["arguments"] == [1.0e-4, 1413]
    # the shared source config is untouched
    src = yaml.safe_load(Path(HERE / "config_mlx.yaml").read_text())
    assert src["lr_schedule"]["arguments"] == [2.0e-4, 1391]
    assert src["lr_schedule"]["warmup"] == 43


def test_lr_warmup_zero_is_honoured_not_treated_as_unset(tmp_path):
    """Mid-epoch continuations use warmup 0; a falsy-check bug would drop it."""
    d = make_data_dir(tmp_path, 5735, 1010)
    built = T.build_mlx_run(make_args(tmp_path, d, expect_train=5735, iters=100, lr_warmup=0))
    assert built["cfg"]["lr_schedule"]["warmup"] == 0


def test_no_lr_flags_leaves_the_fresh_epoch_schedule(tmp_path):
    d = make_data_dir(tmp_path, 5735, 1010)
    built = T.build_mlx_run(make_args(tmp_path, d, expect_train=5735, iters=5735))
    assert built["cfg"]["lr_schedule"]["arguments"] == [2.0e-4, 1391]
    assert built["cfg"]["lr_schedule"]["warmup"] == 43


# -------------------------------------------------------- authorization ----

def test_default_authorization_is_the_2026_08_20_one_epoch_ratification(tmp_path):
    d = make_data_dir(tmp_path, 5736, 1010)
    built = T.build_mlx_run(make_args(tmp_path, d, iters=5736))
    assert built["manifest"]["owner_authorization"]["date"] == "2026-08-20"


def test_authorization_file_replaces_the_block_and_is_hashed(tmp_path):
    d = make_data_dir(tmp_path, 5735, 1010)
    auth = tmp_path / "auth.json"
    auth.write_text(json.dumps({"campaign": "G1 REPAIR", "scope": "ONE EPOCH"}))
    built = T.build_mlx_run(make_args(tmp_path, d, expect_train=5735, iters=5735,
                                      authorization=str(auth)))
    a = built["manifest"]["owner_authorization"]
    assert a["campaign"] == "G1 REPAIR"
    assert a["source_sha256"] == T.sha256_file(auth)
    assert "quote" not in a, "the default block must be replaced, not merged"


# ------------------------------------------------------- standing guards ----

def test_conversion_report_mismatch_is_still_a_hard_stop(tmp_path):
    d = make_data_dir(tmp_path, 5735, 1010)
    rep = json.loads((d / "conversion_report.json").read_text())
    rep["splits"]["train"]["output_sha256"] = "0" * 64
    (d / "conversion_report.json").write_text(json.dumps(rep))
    with pytest.raises(ValueError, match="ARTIFACT MISMATCH"):
        T.build_mlx_run(make_args(tmp_path, d, expect_train=5735, iters=5735))


def test_prompt_rendering_contract_is_recorded_in_every_manifest(tmp_path):
    d = make_data_dir(tmp_path, 5735, 1010)
    built = T.build_mlx_run(make_args(tmp_path, d, expect_train=5735, iters=5735))
    c = built["manifest"]["prompt_rendering_contract"]
    assert c["system"].startswith("the byte-identical instruction")
    assert c["user"] == "the raw passage text and nothing else"
    assert "no ticker, CIK, filing date, section_type string" in c["look_ahead_bias"]
