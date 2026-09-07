#!/usr/bin/env python3
"""
build_dataset_manifest.py — provenance manifest for the rubric-v1.2 retrain's
DATA, written before any training starts.

`train_qlora.py` writes this run directory's `manifest.json` at launch time
(model, resolved config, versions, machine, data hashes). This file records
everything UPSTREAM of that: which labels, which frozen split manifest, which
join, which prepared JSONL, which MLX chat-format data, which instruction —
each with a sha256 — so "the artifact you run is the artifact you tested" is
checkable in both directions.

Re-runnable, read-only, zero API calls:
    python3 finetune/runs/2026-08-26-v12-epoch1/build_dataset_manifest.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
FT = HERE.parent.parent            # finetune/
REPO = FT.parent


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def entry(p: Path, **extra) -> dict:
    d = {"path": str(p), "exists": p.exists()}
    if p.exists():
        d["sha256"] = sha256_file(p)
        d["bytes"] = p.stat().st_size
    d.update(extra)
    return d


def lines(p: Path) -> int:
    with open(p, "rb") as f:
        return sum(1 for _ in f)


def instruction_sha() -> dict:
    src = (FT / "prepare_dataset.py").read_text()
    ns: dict = {}
    exec(src[src.index("INSTRUCTION = ("): src.index("KEY_ORDER")], ns)
    ins = ns["INSTRUCTION"]
    return {
        "role": "TRAINING instruction — the `system` turn of every training and inference prompt",
        "source": "finetune/prepare_dataset.py::INSTRUCTION",
        "sha256": hashlib.sha256(ins.encode()).hexdigest(),
        "chars": len(ins),
        "frozen_across": "E1 epoch-1, E1 epoch-2, and this rubric-v1.2 retrain — byte-identical",
        "why_frozen": (
            "keeping it fixed makes the v1.1-student vs v1.2-student comparison single-axis "
            "(label values moved, nothing else). It is NOT the labeling system prompt: see "
            "labeling_system_prompt below."
        ),
    }


def labeling_system_prompt() -> dict:
    src = (REPO / "build_batch_requests.py").read_text()
    marker = "SYSTEM_PROMPT = "
    i = src.index(marker)
    j = src.index("\n\n\n", i)
    ns: dict = {}
    exec(src[i:j], ns)
    sp = ns["SYSTEM_PROMPT"]
    return {
        "role": "LABELING system prompt — what the TEACHER (claude-sonnet-5) was told when it "
                "produced data/labels_v12.parquet. It is NOT the training instruction.",
        "source": "build_batch_requests.py::SYSTEM_PROMPT",
        "sha256": hashlib.sha256(sp.encode()).hexdigest(),
        "chars": len(sp),
        "rubric_version": "v1.2",
        "qwen2_5_tokens": 1904,
        "relationship_to_training_instruction": (
            "hand-synced restatement, not a verbatim embed (HANDOFF §3, 2026-08-10 sync rule). "
            "Substituting it for the training instruction is INFEASIBLE at max_seq_length 2048: "
            "it renders to 1,934 tokens with an empty passage, leaving ~114 tokens for the "
            "passage against a measured mean of ~660."
        ),
    }


def git_rev() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True,
                              text=True).stdout.strip() or None
    except Exception:
        return None


def main():
    conv = json.loads((FT / "mlx_data_v12" / "conversion_report.json").read_text())
    split_rep = json.loads((FT / "splits_v12" / "build_report.json").read_text())

    man = {
        "run_id": HERE.name,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": git_rev(),
        "what_this_run_is": (
            "Epoch 1 of the rubric-v1.2 retrain (G1 repair campaign). Same base model, same "
            "LoRA recipe, same frozen train/eval split as the 2026-08-21 epoch-1 run. The only "
            "thing that changed is the TEACHER LABELS: data/labels.parquet (rubric v1.1) -> "
            "data/labels_v12.parquet (rubric v1.2)."
        ),
        "cost": {"usd": 0.0, "anthropic_api_calls": 0, "gpu_rental": "none — local Apple Silicon"},
        "authorization": json.loads((HERE / "authorization.json").read_text()),
        "labels": {
            "v12": entry(REPO / "data" / "labels_v12.parquet", rows=6747, labeled=6747,
                         batch_id="msgbatch_01UdoUkZfuaTRJzokZDfbFYN (6,746) + "
                                  "msgbatch_01RvQpZofwP2yrHNnuJVmFZu (1, the completion row)",
                         rubric_version="v1.2"),
            "v12_pre_completion_backup": entry(REPO / "data" / "labels_v12.parquet.pre_completion"),
            "v12_completion_audit": entry(REPO / "data" / "labels_v12_completion.parquet"),
            "e1_v11_frozen_reference": entry(REPO / "data" / "labels.parquet", rows=6747, labeled=6746,
                                             note="FROZEN — read-only reference, never written"),
            "corpus": entry(REPO / "data" / "labeling_corpus.parquet"),
        },
        "split": {
            "frozen_manifest": entry(FT / "splits" / "manifest.parquet", rows=6746,
                                     note="THE source of membership. split.py was NOT run."),
            "builder": entry(FT / "build_splits_v12.py"),
            "build_report": entry(FT / "splits_v12" / "build_report.json"),
            "train": entry(FT / "splits_v12" / "train.parquet", rows=split_rep["outputs"]["train"]["rows"]),
            "eval": entry(FT / "splits_v12" / "eval.parquet", rows=split_rep["outputs"]["eval"]["rows"]),
            "manifest": entry(FT / "splits_v12" / "manifest.parquet", rows=6746),
            "counts": {
                "train": split_rep["outputs"]["train"]["rows"],
                "eval": split_rep["outputs"]["eval"]["rows"],
                "frozen_train": 5736,
                "frozen_eval": 1010,
            },
            "gaps": split_rep["v12_label_gaps"],
            "e1_refusal_chunk": split_rep["e1_refusal_chunk"],
            "e1_splits_untouched": {
                "train": entry(FT / "splits" / "train.parquet", rows=5736),
                "eval": entry(FT / "splits" / "eval.parquet", rows=1010),
            },
        },
        "prepared": {
            "builder": entry(FT / "prepare_dataset.py"),
            "train": entry(FT / "prepared_v12" / "train.jsonl", rows=lines(FT / "prepared_v12" / "train.jsonl")),
            "eval": entry(FT / "prepared_v12" / "eval.jsonl", rows=lines(FT / "prepared_v12" / "eval.jsonl")),
            "e1_prepared_untouched": {
                "train": entry(FT / "prepared" / "train.jsonl"),
                "eval": entry(FT / "prepared" / "eval.jsonl"),
            },
        },
        "mlx_data": {
            "converter": entry(FT / "convert_to_mlx.py"),
            "train": entry(FT / "mlx_data_v12" / "train.jsonl", rows=conv["splits"]["train"]["n_examples"]),
            "valid": entry(FT / "mlx_data_v12" / "valid.jsonl", rows=conv["splits"]["eval"]["n_examples"]),
            "conversion_report": entry(FT / "mlx_data_v12" / "conversion_report.json"),
            "max_seq_length": conv["max_seq_length"],
            "head_truncated": {
                "train": conv["splits"]["train"]["n_passage_truncated"],
                "eval": conv["splits"]["eval"]["n_passage_truncated"],
            },
            "e1_mlx_data_untouched": {
                "train": entry(FT / "mlx_data" / "train.jsonl"),
                "valid": entry(FT / "mlx_data" / "valid.jsonl"),
            },
        },
        "instruction": instruction_sha(),
        "labeling_system_prompt": labeling_system_prompt(),
        "rubric": entry(REPO / "labeling_rubric.md", version="v1.2"),
        "prompt_rendering_contract": {
            "format": "mlx-lm chat format: {'messages': [system, user, assistant]}",
            "system": "the TRAINING instruction, byte-identical across all rows (verified)",
            "user": "the raw passage text and nothing else",
            "assistant": "the target JSON string",
            "inference_equivalent": "apply_chat_template(messages[:2], add_generation_prompt=True)",
            "loss_region": "tokens[offset:], offset = len(apply_chat_template(messages[:-1], add_generation_prompt=True))",
            "look_ahead_bias": "no ticker, CIK, filing date, section_type string, or outcome framing is "
                               "added anywhere; the conversion is a pure re-serialization",
            "verified_against_E1": {
                "shared_rows": 6746,
                "rows_only_in_E1": 0,
                "rows_only_in_v12": 0,
                "split_side_differs": 0,
                "system_turn_differs": 0,
                "passage_turn_differs": 14,
                "assistant_json_differs": 2034,
                "inference_prompt_token_identical": 6732,
                "note": "the 14 are ALL among the 52 head-truncated rows (2 train / 12 eval). "
                        "convert_to_mlx.py truncates the passage until the rendered sequence "
                        "INCLUDING the answer fits 2048, so a longer v1.2 answer keeps slightly "
                        "less passage. All 14 are a strict head-prefix relation — only the "
                        "passage TAIL moved. This is a real, small second axis: state it at G1.",
            },
        },
        "base_model": {
            "repo": "mlx-community/Qwen2.5-7B-Instruct-4bit",
            "snapshot": "/Users/vihanpatil/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/"
                        "snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed",
            "hf_revision": "c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed",
            "weights_sha256": "86110f368236b53cf4c2336f991a85703b17bcc60bb75f292b4002ec0219f071",
            "sha_source": "HF blob filename (content-addressed) — identical to the value recorded "
                          "in the 2026-08-21 epoch-1 and epoch-2 manifests",
            "license": "apache-2.0",
        },
        "reference_adapters_v11_student": {
            "epoch1_final": entry(FT / "checkpoints" / "qwen2.5-7b-finscreen-lora-mlx-epoch1-final-from-2250" / "adapters.safetensors"),
            "epoch2_final": entry(FT / "checkpoints" / "qwen2.5-7b-finscreen-lora-mlx-epoch2" / "adapters.safetensors"),
            "note": "the v1.1 student, for comparison at the G1 read. NOT resumed from — the v1.2 "
                    "epoch-1 run starts from the base model, exactly as the 2026-08-20 epoch-1 did.",
        },
        "label_shift_report": {
            "generator": entry(REPO / "data" / "hardening" / "label_shift_v11_v12.py"),
            "json": entry(REPO / "data" / "hardening" / "label_shift_v11_v12.json"),
            "markdown": entry(REPO / "data" / "hardening" / "LABEL_SHIFT_v11_v12.md"),
        },
    }
    out = HERE / "dataset_manifest.json"
    out.write_text(json.dumps(man, indent=2))
    print(f"wrote {out}")
    print(f"  train {man['split']['counts']['train']} / eval {man['split']['counts']['eval']}")
    print(f"  mlx_data_v12 train sha {man['mlx_data']['train']['sha256'][:16]}...")
    print(f"  mlx_data_v12 valid sha {man['mlx_data']['valid']['sha256'][:16]}...")
    print(f"  instruction sha {man['instruction']['sha256'][:16]}... ({man['instruction']['chars']} chars)")
    print(f"  labeling system prompt sha {man['labeling_system_prompt']['sha256'][:16]}...")


if __name__ == "__main__":
    main()
