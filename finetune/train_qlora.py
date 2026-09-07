#!/usr/bin/env python3
"""
train_qlora.py — QLoRA fine-tuning entry point for FinScreen's Phase D model.

TWO BACKENDS LIVE IN THIS FILE
------------------------------
`--backend mlx` (REAL, IMPLEMENTED)
    The ratified path: local 4-bit QLoRA on the owner's 16 GB M5 via
    `mlx_lm.lora`, at $0. Reads `config_mlx.yaml`, resolves it into a run
    directory alongside a `manifest.json` that records exactly what is fed to
    training (data SHA-256s, model revision, version pins, every
    config.yaml -> MLX substitution), then invokes mlx-lm on that resolved
    file. Deliberately a thin wrapper: mlx-lm owns the training loop, this
    script owns provenance and the guardrails.

    Launching a REAL (non---dry-run) MLX run is gated on the owner's explicit
    go. It was given in chat 2026-08-20 ("Yes -- launch, 1 epoch first"), with
    ONE EPOCH as the binding scope. `config_mlx.yaml`'s `iters: 5736` is that
    one epoch; raising it needs a new owner decision, not a flag.

`--backend hf` (DEFAULT, SCAFFOLDING ONLY)
    The superseded CUDA / bitsandbytes / HF-Trainer path for the
    not-pre-approved GPU-rental fallback. `--dry-run` validates config.yaml
    and the prepared JSONL; the real branch still raises NotImplementedError
    by design. Left byte-for-byte intact so its dry-run keeps working.

*** THE hf BACKEND'S REAL PATH REMAINS GATED ON THE OWNER APPROVING GPU  ***
*** RENTAL: exact provider, instance type, and estimated hours confirmed ***
*** BEFORE renting. This script rents nothing and calls no paid API.     ***

Heavy imports happen INSIDE the run functions, not at module import time, so
`--dry-run` works in an environment with none of them installed.

Usage:
    python3 train_qlora.py --dry-run                       # hf scaffolding validation (unchanged)
    python3 train_qlora.py --backend mlx --dry-run         # resolve config + manifest, print the exact command, run nothing
    python3 train_qlora.py --backend mlx --tag probe --iters 20
    python3 train_qlora.py --backend mlx --tag epoch1      # the real one-epoch run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
MLX_CONFIG = HERE / "config_mlx.yaml"
MLX_DATA_DIR = HERE / "mlx_data"
RUNS_DIR = HERE / "runs"
CHECKPOINTS_DIR = HERE / "checkpoints"
VENV_PYTHON = HERE / ".mlx_venv" / "bin" / "python"

# The row counts the split is contractually expected to have. A mismatch means
# the split or the conversion changed underneath this run and it must stop.
EXPECTED_ROWS = {"train.jsonl": 5736, "valid.jsonl": 1010}


def load_config(config_path: Path) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def validate_data_pipeline(cfg: dict) -> dict:
    """Load the prepared JSONL files, check they're well-formed, and
    compute ESTIMATED token counts (word_count * multiplier from config --
    no tokenizer available offline, so this is explicitly an estimate, not
    a measurement). Returns a summary dict for --dry-run printing."""
    summary = {}
    multiplier = cfg["data"]["estimated_token_multiplier_words_to_tokens"]
    max_seq_length = cfg["data"]["max_seq_length"]

    for side in ("train", "eval"):
        path = HERE / cfg["data"][f"{side}_path"]
        if not path.exists():
            raise FileNotFoundError(
                f"{path} not found -- run prepare_dataset.py before train_qlora.py"
            )
        n = 0
        n_over_budget = 0
        total_est_tokens = 0
        max_est_tokens = 0
        malformed = 0
        with open(path) as f:
            for line in f:
                n += 1
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    malformed += 1
                    continue
                for key in ("chunk_id", "instruction", "input", "output"):
                    if key not in rec:
                        raise ValueError(f"{path} line {n}: missing required key '{key}'")
                # Also verify output is itself valid JSON (the training target).
                try:
                    json.loads(rec["output"])
                except json.JSONDecodeError as e:
                    raise ValueError(f"{path} line {n}: 'output' is not valid JSON: {e}")

                approx_words = len(rec["instruction"].split()) + len(rec["input"].split()) + len(rec["output"].split())
                est_tokens = round(approx_words * multiplier)
                total_est_tokens += est_tokens
                max_est_tokens = max(max_est_tokens, est_tokens)
                if est_tokens > max_seq_length:
                    n_over_budget += 1

        summary[side] = {
            "n_examples": n,
            "n_malformed": malformed,
            "estimated_avg_tokens": round(total_est_tokens / n) if n else 0,
            "estimated_max_tokens": max_est_tokens,
            "n_estimated_over_max_seq_length": n_over_budget,
        }
    return summary


def validate_config(cfg: dict) -> None:
    required_top = ["model", "lora", "data", "training"]
    for k in required_top:
        if k not in cfg:
            raise ValueError(f"config.yaml missing required top-level section: {k}")
    if not cfg["model"].get("base_model_id"):
        raise ValueError("config.yaml model.base_model_id must be set")
    if cfg["model"].get("license") != "Apache-2.0":
        print(
            f"WARNING: model license in config is '{cfg['model'].get('license')}', "
            "not the Apache-2.0 documented in MODEL_CHOICE.md -- re-check MODEL_CHOICE.md "
            "is still in sync with config.yaml before a real run.",
            file=sys.stderr,
        )


def print_planned_run(cfg: dict, data_summary: dict) -> None:
    print("=" * 70)
    print("PLANNED QLoRA RUN (not executed -- dry-run)")
    print("=" * 70)
    print(f"Base model:      {cfg['model']['base_model_id']}  (license: {cfg['model']['license']})")
    print(f"Quantization:    4-bit ({cfg['model']['bnb_4bit_quant_type']}), "
          f"compute dtype {cfg['model']['bnb_4bit_compute_dtype']}")
    print(f"LoRA:            r={cfg['lora']['r']}, alpha={cfg['lora']['lora_alpha']}, "
          f"target_modules={cfg['lora']['target_modules']}")
    print(f"Epochs:          {cfg['training']['num_train_epochs']}")
    print(f"Batch size:      {cfg['training']['per_device_train_batch_size']} x "
          f"{cfg['training']['gradient_accumulation_steps']} grad-accum steps")
    print(f"LR:              {cfg['training']['learning_rate']} ({cfg['training']['lr_scheduler_type']})")
    print(f"Max seq length:  {cfg['data']['max_seq_length']} tokens "
          f"(ESTIMATED via words * {cfg['data']['estimated_token_multiplier_words_to_tokens']}, "
          f"NOT measured with the real tokenizer -- see caveat below)")
    print()
    for side, s in data_summary.items():
        print(f"[{side}] {s['n_examples']} examples, {s['n_malformed']} malformed, "
              f"est. avg tokens/example={s['estimated_avg_tokens']}, "
              f"est. max tokens/example={s['estimated_max_tokens']}, "
              f"est. examples over max_seq_length={s['n_estimated_over_max_seq_length']}")
    print()
    print("CAVEAT: token counts above are ESTIMATED (word_count * "
          f"{cfg['data']['estimated_token_multiplier_words_to_tokens']}), not measured -- "
          "no tokenizer can be loaded offline in this environment (would require "
          "downloading the base model's tokenizer files, a networked action). Before a "
          "real run, load the actual Qwen2.5 tokenizer once (on the GPU box, where the "
          "download already needs to happen) and re-measure exact token counts / "
          "truncation rate at max_seq_length.")
    print()
    print("GPU rental: NOT booked by this script. Per config.yaml's "
          "gpu_rental_placeholder section and the standing $5 rule, provider/instance/"
          "estimated-hours must be confirmed with the owner before any real rental.")
    print("=" * 70)


def run_training(cfg: dict) -> None:
    """The REAL training path. Heavy imports happen here, not at module
    scope, so --dry-run never needs them installed."""
    print(
        "REAL TRAINING RUN REQUESTED.\n"
        "This requires a GPU and the heavy deps in requirements-finetune.txt "
        "(torch/transformers/peft/bitsandbytes/accelerate), none of which are "
        "installed in this local dev environment by design.\n"
        "This also requires the owner to have already confirmed GPU rental "
        "provider/instance/estimated-hours per the standing $5 rule "
        "(ROADMAP.md Week 4's money gate) -- this script does not check that "
        "for you; it is a human sign-off, not a flag.\n",
        file=sys.stderr,
    )
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        import peft  # noqa: F401
        import bitsandbytes  # noqa: F401
    except ImportError as e:
        print(
            f"Heavy dependency not installed: {e}. Install requirements-finetune.txt "
            "on the GPU box before running a real training pass.",
            file=sys.stderr,
        )
        sys.exit(1)

    raise NotImplementedError(
        "Real training loop intentionally not implemented in this pass -- scaffolding "
        "only, per the task's ZERO-PAID-ACTIONS constraint. Fill in the "
        "transformers.Trainer / peft QLoRA loop here once GPU rental is approved, "
        "using cfg['model'], cfg['lora'], cfg['data'], cfg['training'] as already "
        "validated by validate_config()/validate_data_pipeline() above."
    )


# ===========================================================================
# MLX BACKEND — the real, implemented path
# ===========================================================================

# Every config.yaml setting that could NOT be carried across to MLX by
# renaming, recorded in each manifest so the substitutions read as decisions
# rather than omissions. Source: MLX_FEASIBILITY.md §5, re-verified against
# the installed mlx-lm source.
MLX_SUBSTITUTIONS = {
    "lora.lora_alpha -> lora_parameters.scale": (
        "MLX has no `alpha`; `scale` is a direct multiplier on the adapter output. "
        "PEFT's effective multiplier is alpha/r, so config.yaml's lora_alpha=32 with "
        "r=16 maps to scale=2.0. Copying 32 across (16x) or accepting mlx-lm's 20.0 "
        "default (10x) would silently change effective LoRA strength."
    ),
    "bnb_4bit_quant_type: nf4 -> MLX affine group-wise quantization": (
        "Dropped, not renamed: MLX quantizes with affine group-wise quantization "
        "(group_size 64, 4 bits => 4.5 effective bits/weight), a different quantizer "
        "from bitsandbytes NF4. Verified on the downloaded weights: 951,910,400 U32 "
        "packed values + 238,310,912 F16 scales/biases = exactly 2 per 64-weight group."
    ),
    "bnb_4bit_use_double_quant: true -> dropped": "MLX has no double quantization.",
    "bnb_4bit_compute_dtype: bfloat16 -> dropped": "Not exposed; MLX computes in the model dtype.",
    "load_in_4bit: true -> implicit": "Not a flag. Pointing `model` at a pre-quantized repo makes it QLoRA.",
    "optim: paged_adamw_8bit -> optimizer: adamw": (
        "MLX has no paged and no 8-bit optimizers. Standard AdamW with fp32 state is "
        "used. Harmless: optimizer state here is ~23 MB (MLX_FEASIBILITY §3.2)."
    ),
    "bf16: true -> dropped": "Not a flag in MLX.",
    "lora.bias / lora.task_type -> dropped": "PEFT-only concepts.",
    "save_total_limit: 3 -> dropped": "mlx-lm keeps every checkpoint; they are ~6 MB each here.",
    "eval_strategy / report_to -> dropped": "No equivalent.",
    "num_train_epochs: 3 -> iters: 5736": (
        "mlx-lm has no epoch concept and `iters` counts MICRO-BATCHES. At batch_size 1, "
        "5736 iters == exactly one pass over the 5736 training examples == 1434 "
        "optimizer updates at grad_accumulation_steps 4. ONE epoch is the owner-ratified "
        "scope; config.yaml's 3 epochs was never approved for this path."
    ),
    "per_device_train_batch_size: 4 -> batch_size: 1": (
        "config.yaml's batch 4 does not fit 16 GB: the 152,064-vocab logits tensor alone "
        "is ~4.6 GiB at batch 4 / seq 2048 (~7.0 GiB with an fp32 CE copy). "
        "grad_accumulation_steps: 4 recovers the effective batch of 4."
    ),
    "lr_scheduler_type: cosine + warmup_ratio: 0.03 -> lr_schedule in OPTIMIZER UPDATES": (
        "MLX's LR schedule is a function of the optimizer's step counter, which advances "
        "once per optimizer.update() -- once per 4 micro-batch iters here. Verified "
        "on-box. So warmup is 0.03 * 1434 = 43 updates (not 172), and cosine decay_steps "
        "is 1434-43 = 1391 (not 5736). MLX_FEASIBILITY §8's figures were in micro-batch "
        "units and are corrected here."
    ),
    "clear_cache_threshold -> accepted but inert in mlx-lm 0.31.3": (
        "lora.py::train_model never passes it into TrainingArgs, so the effective value "
        "is 0, which means the allocator cache is cleared after EVERY step. That is "
        "strictly more conservative than MLX_FEASIBILITY §7's suggested 10 and is the "
        "behaviour upstream issue #828 recommends on memory-tight machines."
    ),
    "gpu_rental_placeholder -> N/A": "This path is local and costs $0. Nothing is rented.",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def count_lines(path: Path) -> int:
    with open(path, "rb") as f:
        return sum(1 for _ in f)


def resolve_model_snapshot(model_ref: str) -> tuple[str, str | None]:
    """Return (local_snapshot_path, revision_hash).

    Prefer an already-downloaded local snapshot so training loads a pinned,
    hashed artifact rather than whatever `main` points at today.
    """
    p = Path(model_ref).expanduser()
    if p.is_dir():
        rev = p.name if len(p.name) == 40 else None
        return str(p.resolve()), rev
    from huggingface_hub import snapshot_download

    path = snapshot_download(repo_id=model_ref)
    return path, Path(path).name if len(Path(path).name) == 40 else None


def verify_mlx_data(data_dir: Path, expected_rows: dict | None = None) -> dict:
    """VERIFY THE SUBMITTED ARTIFACT IS THE TESTED ARTIFACT.

    Re-hash and re-count the files training is about to read, and cross-check
    them against convert_to_mlx.py's own report if it is present. Any drift
    between what was converted/verified and what is about to be trained on is
    a hard stop.
    """
    expected_rows = expected_rows or EXPECTED_ROWS
    info = {"dir": str(data_dir), "expected_rows": dict(expected_rows), "files": {}}
    if not data_dir.is_dir():
        raise FileNotFoundError(
            f"{data_dir} not found — run convert_to_mlx.py before training "
            f"(it renders finetune/prepared/*.jsonl into the chat format mlx-lm accepts)"
        )
    for name, expected_n in expected_rows.items():
        f = data_dir / name
        if not f.exists():
            raise FileNotFoundError(f"{f} missing — run convert_to_mlx.py")
        n = count_lines(f)
        if n != expected_n:
            raise ValueError(
                f"{f} has {n} rows, expected {expected_n}. The split or the conversion "
                f"changed underneath this run; stopping rather than training on it."
            )
        info["files"][name] = {"rows": n, "sha256": sha256_file(f), "bytes": f.stat().st_size}

    report_path = data_dir / "conversion_report.json"
    if report_path.exists():
        rep = json.loads(report_path.read_text())
        info["conversion_report"] = rep
        expected = {
            "train.jsonl": rep["splits"]["train"]["output_sha256"],
            "valid.jsonl": rep["splits"]["eval"]["output_sha256"],
        }
        for name, want in expected.items():
            got = info["files"][name]["sha256"]
            if got != want:
                raise ValueError(
                    f"ARTIFACT MISMATCH: {name} on disk hashes {got} but "
                    f"conversion_report.json (the file whose contents were verified "
                    f"answer-intact) recorded {want}. Re-run convert_to_mlx.py."
                )
        info["verified_against_conversion_report"] = True
    else:
        info["verified_against_conversion_report"] = False
        print(
            f"WARNING: {report_path} not found — cannot cross-check that the data on disk "
            f"is the data convert_to_mlx.py verified answer-intact.",
            file=sys.stderr,
        )
    return info


DEFAULT_AUTHORIZATION = {
    "scope": "ONE EPOCH",
    "quote": "Yes — launch, 1 epoch first",
    "date": "2026-08-20",
    "note": "Any run beyond one epoch requires a new explicit owner decision.",
}


def load_authorization(path: str | None) -> dict:
    """The owner ratification this run is executed under, recorded in the
    manifest. Overridable by file so a later campaign (e.g. the 2026-08-26 G1
    repair retrain) records ITS authorization, not a stale earlier quote."""
    if not path:
        return dict(DEFAULT_AUTHORIZATION)
    p = Path(path).resolve()
    auth = json.loads(p.read_text())
    auth["source_file"] = str(p)
    auth["source_sha256"] = sha256_file(p)
    return auth


def build_mlx_run(args) -> dict:
    """Resolve config_mlx.yaml into a concrete, hashed run directory.

    Returns a dict with the run dir, the resolved config path, the command to
    execute, and the manifest (already written to disk).
    """
    cfg = load_config(Path(args.mlx_config))

    expected_rows = {
        "train.jsonl": getattr(args, "expect_train", None) or EXPECTED_ROWS["train.jsonl"],
        "valid.jsonl": getattr(args, "expect_eval", None) or EXPECTED_ROWS["valid.jsonl"],
    }

    stamp = datetime.now().strftime("%Y-%m-%d")
    run_dir = Path(args.run_dir) if args.run_dir else RUNS_DIR / (f"{stamp}-{args.tag}" if args.tag else stamp)
    run_dir.mkdir(parents=True, exist_ok=True)

    data_dir = Path(args.data_dir).resolve()
    data_info = verify_mlx_data(data_dir, expected_rows)

    model_path, revision = resolve_model_snapshot(args.model or cfg["model"])
    weights = Path(model_path) / "model.safetensors"

    adapter_path = Path(args.adapter_path).resolve() if args.adapter_path else (
        CHECKPOINTS_DIR / f"qwen2.5-7b-finscreen-lora-mlx-{args.tag or stamp}"
    ).resolve()

    # --- apply overrides onto the resolved config ---
    cfg["model"] = model_path
    cfg["data"] = str(data_dir)
    cfg["adapter_path"] = str(adapter_path)
    if args.iters is not None:
        cfg["iters"] = args.iters
    if args.save_every is not None:
        cfg["save_every"] = args.save_every
    if args.steps_per_report is not None:
        cfg["steps_per_report"] = args.steps_per_report
    if args.steps_per_eval is not None:
        cfg["steps_per_eval"] = args.steps_per_eval
    if args.val_batches is not None:
        cfg["val_batches"] = args.val_batches
    if args.resume_adapter_file:
        cfg["resume_adapter_file"] = str(Path(args.resume_adapter_file).resolve())

    # Continuation and second-epoch runs need their own cosine schedule. Doing
    # that by flag replaces the old "temp-edit config_mlx.yaml, resolve, revert"
    # dance (runs/2026-08-21-epoch1-final-from-2250/RESUME_RECIPE.md step 5),
    # which mutated a shared file mid-campaign. Units are OPTIMIZER UPDATES.
    if args.lr_peak is not None:
        cfg["learning_rate"] = args.lr_peak
        cfg["lr_schedule"]["arguments"][0] = args.lr_peak
    if args.lr_decay_steps is not None:
        cfg["lr_schedule"]["arguments"][1] = args.lr_decay_steps
    if args.lr_warmup is not None:
        cfg["lr_schedule"]["warmup"] = args.lr_warmup

    # --- guardrails that are NOT negotiable by flag ---
    if cfg["batch_size"] != 1:
        raise ValueError(
            f"batch_size={cfg['batch_size']} — MLX_FEASIBILITY §3.3 shows anything above 1 "
            f"does not fit 16 GB. Refusing."
        )
    if not cfg.get("grad_checkpoint"):
        raise ValueError("grad_checkpoint must be true — §3.4 makes it mandatory, not an optimization.")
    if not cfg.get("mask_prompt"):
        raise ValueError("mask_prompt must be true — §5.4; without it ~96% of the gradient trains on the prompt.")
    if cfg["iters"] > expected_rows["train.jsonl"]:
        raise ValueError(
            f"iters={cfg['iters']} exceeds one epoch ({expected_rows['train.jsonl']} at batch_size 1). "
            f"The owner ratified ONE epoch. More epochs need a new owner decision, not a flag."
        )

    resolved_config = run_dir / "mlx_lora_config.yaml"
    with open(resolved_config, "w") as f:
        yaml.safe_dump(cfg, f, sort_keys=False, default_flow_style=False)

    mlx_bin = HERE / ".mlx_venv" / "bin" / "mlx_lm.lora"
    command = [str(mlx_bin), "-c", str(resolved_config)]

    n_updates = cfg["iters"] // cfg["grad_accumulation_steps"]
    manifest = {
        "run_id": run_dir.name,
        "tag": args.tag,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "created_local": datetime.now().isoformat(),
        "purpose": "FinScreen Phase D — local MLX 4-bit QLoRA fine-tune of "
                   "Qwen2.5-7B-Instruct on SEC-filing chunk labels. Research/screening "
                   "classifier only: it extracts sentiment / red-flag categories / "
                   "guidance-direction from text. It does not predict prices, recommend "
                   "trades, or connect to any brokerage.",
        "owner_authorization": load_authorization(getattr(args, "authorization", None)),
        "cost": {"usd": 0.0, "gpu_rental": "none — local Apple Silicon only", "api_calls": 0},
        "machine": {
            "chip": subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                   capture_output=True, text=True).stdout.strip(),
            "memory_bytes": int(subprocess.run(["sysctl", "-n", "hw.memsize"],
                                               capture_output=True, text=True).stdout.strip() or 0),
            "macos": platform.mac_ver()[0],
            "python": platform.python_version(),
        },
        "versions": _mlx_versions(),
        "model": {
            "repo": args.model or cfg_original_model(Path(args.mlx_config)),
            "resolved_snapshot_path": model_path,
            "hf_revision": revision,
            "weights_file": str(weights),
            "weights_sha256": args.weights_sha256 or "(not recomputed this run — see verify note)",
            "quantization": "MLX affine group-wise, group_size 64, 4 bits (4.5 effective bits/weight)",
            "identity_verified": {
                "chat_template": "ChatML <|im_start|>/<|im_end|> (genuine Qwen2.5-Instruct template)",
                "eos_token": "<|im_end|> (151645) — the Instruct EOS; the base model uses <|endoftext|>",
                "readme": "states conversion from Qwen/Qwen2.5-7B-Instruct",
                "base_model_metadata_tag": "Qwen/Qwen2.5-7B — confirmed an auto-populated slip, not the actual weights",
                "instruct_generation_check": "passed — answered an instruction directly rather than continuing text",
                "license": "apache-2.0",
            },
        },
        "data": data_info,
        "prompt_rendering_contract": {
            "format": "mlx-lm chat format: {'messages': [system, user, assistant]}",
            "system": "the byte-identical instruction from PROMPT_TEMPLATE.md",
            "user": "the raw passage text and nothing else",
            "assistant": "the target JSON string",
            "mirrors": "build_batch_requests.py::build_request (system=instruction, user=passage)",
            "inference_equivalent": "apply_chat_template(messages[:2], add_generation_prompt=True)",
            "loss_region": "tokens[offset:] where offset = len(apply_chat_template(messages[:-1], add_generation_prompt=True))",
            "look_ahead_bias": "no ticker, CIK, filing date, section_type string, or outcome framing "
                               "is added by the conversion; it is a pure re-serialization of "
                               "prepare_dataset.py's output",
        },
        "config_source": str(Path(args.mlx_config).resolve()),
        "resolved_config_path": str(resolved_config),
        "resolved_config_sha256": sha256_file(resolved_config),
        "resolved_config": cfg,
        "derived": {
            "iters_are_micro_batches": True,
            "optimizer_updates": n_updates,
            "effective_batch_size": cfg["batch_size"] * cfg["grad_accumulation_steps"],
            "epochs": round(cfg["iters"] / expected_rows["train.jsonl"], 4),
            "lr_schedule_units": "OPTIMIZER UPDATES (verified on-box), not micro-batch iters",
        },
        "config_yaml_substitutions": MLX_SUBSTITUTIONS,
        "command": command,
        "log_path": str(run_dir / "train.log"),
    }
    with open(run_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    if (data_dir / "conversion_report.json").exists():
        shutil.copy2(data_dir / "conversion_report.json", run_dir / "conversion_report.json")

    return {"run_dir": run_dir, "config": resolved_config, "command": command, "manifest": manifest, "cfg": cfg}


def cfg_original_model(path: Path) -> str:
    try:
        return load_config(path).get("model", "")
    except Exception:
        return ""


def _mlx_versions() -> dict:
    out = {}
    try:
        import mlx.core as mx

        out["mlx"] = mx.__version__
        out["device"] = dict(mx.device_info())
    except Exception as e:  # pragma: no cover
        out["mlx"] = f"unavailable: {e}"
    for mod in ("mlx_lm", "transformers", "numpy"):
        try:
            out[mod] = __import__(mod).__version__
        except Exception as e:
            out[mod] = f"unavailable: {e}"
    return out


def print_mlx_plan(built: dict) -> None:
    cfg = built["cfg"]
    m = built["manifest"]
    print("=" * 78)
    print("PLANNED MLX QLoRA RUN")
    print("=" * 78)
    print(f"Run dir:         {built['run_dir']}")
    print(f"Manifest:        {built['run_dir'] / 'manifest.json'}")
    print(f"Resolved config: {built['config']}  (sha256 {m['resolved_config_sha256'][:16]}...)")
    print(f"Model:           {cfg['model']}")
    print(f"  revision:      {m['model']['hf_revision']}")
    print(f"Data:            {cfg['data']}")
    for name, f in m["data"]["files"].items():
        print(f"  {name:12s} {f['rows']:>6d} rows  sha256 {f['sha256'][:16]}...")
    print(f"  cross-checked against conversion_report.json: {m['data']['verified_against_conversion_report']}")
    print(f"LoRA:            rank={cfg['lora_parameters']['rank']} "
          f"scale={cfg['lora_parameters']['scale']} (= alpha/r = 32/16) "
          f"dropout={cfg['lora_parameters']['dropout']}")
    print(f"  keys:          {cfg['lora_parameters']['keys']}")
    print(f"  num_layers:    {cfg['num_layers']} (top layers of 28)")
    print(f"Batch:           {cfg['batch_size']} x {cfg['grad_accumulation_steps']} grad-accum "
          f"= effective {m['derived']['effective_batch_size']}")
    print(f"Seq length:      {cfg['max_seq_length']} (over-length rows PRE-truncated by convert_to_mlx.py)")
    print(f"Iters:           {cfg['iters']} micro-batches = {m['derived']['epochs']} epoch(s) "
          f"= {m['derived']['optimizer_updates']} optimizer updates")
    print(f"LR:              {cfg['learning_rate']} cosine, warmup {cfg['lr_schedule']['warmup']} "
          f"UPDATES, decay over {cfg['lr_schedule']['arguments'][1]} updates")
    print(f"mask_prompt:     {cfg['mask_prompt']}   grad_checkpoint: {cfg['grad_checkpoint']}")
    print(f"Adapter path:    {cfg['adapter_path']}  (save every {cfg['save_every']} iters)")
    print(f"Cost:            $0.00 — local Apple Silicon, no rental, no API calls")
    print()
    print("COMMAND:")
    print("  " + " ".join(built["command"]))
    print("=" * 78)


def run_training_mlx(args) -> int:
    built = build_mlx_run(args)
    print_mlx_plan(built)

    if args.dry_run or args.print_command:
        print("\n(dry run — nothing executed; the run directory and manifest above were still written)")
        return 0

    log_path = built["run_dir"] / "train.log"
    print(f"\nLaunching. Log: {log_path}\n", flush=True)
    env = dict(os.environ, TOKENIZERS_PARALLELISM="true")
    with open(log_path, "a") as log:
        log.write(f"\n=== launch {datetime.now().isoformat()} ===\n")
        log.write("command: " + " ".join(built["command"]) + "\n")
        log.flush()
        proc = subprocess.Popen(
            built["command"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, env=env,
        )
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            log.write(line)
            log.flush()
        rc = proc.wait()
    print(f"\nmlx_lm.lora exited with {rc}")
    return rc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=["hf", "mlx"], default="hf",
                        help="hf = superseded CUDA/peft scaffolding (dry-run only). "
                             "mlx = the real, implemented local Apple Silicon path.")
    parser.add_argument("--config", default=str(HERE / "config.yaml"), help="hf backend config")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate data pipeline, config, and tokenization assumptions without a GPU "
        "or any heavy deps installed. Prints the planned run and exits 0.",
    )
    # --- mlx backend ---
    g = parser.add_argument_group("mlx backend")
    g.add_argument("--mlx-config", default=str(MLX_CONFIG))
    g.add_argument("--data-dir", default=str(MLX_DATA_DIR))
    g.add_argument("--model", default=None, help="Override config_mlx.yaml's model (local snapshot dir or repo id)")
    g.add_argument("--weights-sha256", default=None, help="Recorded verbatim in the manifest")
    g.add_argument("--run-dir", default=None)
    g.add_argument("--tag", default=None, help="Run-dir suffix, e.g. probe / smoke / epoch1")
    g.add_argument("--adapter-path", default=None)
    g.add_argument("--iters", type=int, default=None, help="Override iters (capped at one epoch)")
    g.add_argument("--save-every", type=int, default=None)
    g.add_argument("--steps-per-report", type=int, default=None)
    g.add_argument("--steps-per-eval", type=int, default=None)
    g.add_argument("--val-batches", type=int, default=None)
    g.add_argument("--resume-adapter-file", default=None,
                   help="Resume from a checkpoint. NOTE: mlx-lm 0.31.3 restores adapter WEIGHTS "
                        "only — optimizer moments and LR-schedule position are not saved.")
    g.add_argument("--print-command", action="store_true",
                   help="Write the run dir + manifest + resolved config, print the exact command, run nothing.")
    g.add_argument("--lr-peak", type=float, default=None,
                   help="Override the cosine schedule's peak/init LR (and learning_rate).")
    g.add_argument("--lr-decay-steps", type=int, default=None,
                   help="Override cosine decay_steps. Units: OPTIMIZER UPDATES (iters // grad_accum).")
    g.add_argument("--lr-warmup", type=int, default=None,
                   help="Override warmup. Units: OPTIMIZER UPDATES. Use 0 for a mid-epoch continuation.")
    g.add_argument("--expect-train", type=int, default=EXPECTED_ROWS["train.jsonl"],
                   help="Contractual train.jsonl row count. 5736 for E1; 5735 for the rubric-v1.2 "
                        "retrain (one chunk's re-label request errored and was not retried).")
    g.add_argument("--expect-eval", type=int, default=EXPECTED_ROWS["valid.jsonl"],
                   help="Contractual valid.jsonl row count. 1010 — the eval split is complete "
                        "under both rubrics and must never change.")
    g.add_argument("--authorization", default=None,
                   help="Path to a JSON file replacing the manifest's owner_authorization block "
                        "(the default records the 2026-08-20 'launch, 1 epoch first' ratification).")
    args = parser.parse_args()

    if args.backend == "mlx":
        sys.exit(run_training_mlx(args))

    cfg = load_config(Path(args.config))
    validate_config(cfg)
    data_summary = validate_data_pipeline(cfg)

    if args.dry_run:
        print_planned_run(cfg, data_summary)
        return

    run_training(cfg)


if __name__ == "__main__":
    main()
