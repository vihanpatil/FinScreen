#!/usr/bin/env python3
"""
train_qlora.py — QLoRA fine-tuning entry point for FinScreen's Week 4 model.

*** RUNNING THIS FOR REAL (i.e. WITHOUT --dry-run) IS GATED ON THE OWNER  ***
*** APPROVING GPU RENTAL: exact provider, instance type, and estimated   ***
*** hours confirmed BEFORE renting, per the standing $5 rule and         ***
*** ROADMAP.md Week 4's money gate. This script does not rent a GPU,     ***
*** call any paid API, or download model weights on its own -- but a    ***
*** real (non-dry-run) invocation assumes that approval already          ***
*** happened, and heavy deps (transformers/peft/bitsandbytes/torch)     ***
*** installed separately from this repo's local dev environment.        ***

Heavy imports (torch, transformers, peft, bitsandbytes) happen INSIDE
`run_training()`, not at module import time, specifically so `--dry-run`
works in this environment (no GPU, none of those packages installed) to
validate the data pipeline, config, and tokenization assumptions.

Usage:
    python3 train_qlora.py --dry-run              # validates everything below, no GPU/deps needed
    python3 train_qlora.py --config config.yaml    # REAL run -- requires GPU + heavy deps + owner sign-off
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(HERE / "config.yaml"))
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate data pipeline, config, and tokenization assumptions without a GPU "
        "or any heavy deps installed. Prints the planned run and exits 0.",
    )
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    validate_config(cfg)
    data_summary = validate_data_pipeline(cfg)

    if args.dry_run:
        print_planned_run(cfg, data_summary)
        return

    run_training(cfg)


if __name__ == "__main__":
    main()
