#!/usr/bin/env python3
"""
eval.py — held-out evaluation for the Week 4 fine-tuned extractor.

Computes per-category precision/recall/F1 (macro and per-class) against
`finetune/splits/eval.parquet` / `finetune/prepared/eval.jsonl`, per
ROADMAP.md Week 4. Never rounds weak categories up to a single "it works"
number -- every category is reported, including the bad ones.

distress_tier is EXCLUDED from headline metrics (it was excluded from
training targets entirely -- see PROMPT_TEMPLATE.md / DISCOVERY.md §3).
It is not reported here at all by default, since the model was never
trained to predict it; if a distress_tier analysis is ever wanted, it would
need a separately-trained or separately-prompted path, not this script.

Handles unparseable model output as an explicit failure category
("UNPARSEABLE"), never silently dropped from denominators.

WHAT THE NUMBERS MEAN (binding, restated in every report this file writes):
the eval-split labels are the TEACHER's labels (Claude, via the bootstrap
Batch API run), not human ground truth. Every metric here is
AGREEMENT-WITH-TEACHER, not accuracy. The teacher's own red-flag labels
carry a documented ~36.6% set-level error (sample-pooled) / ~25%
base-rate-representative -- see HANDOFF.md §2a and RED_FLAGS_LIMITATION.md.
A student that "agrees" is reproducing the teacher including its errors.

This is a research/screening classifier. It extracts sentiment, red-flag
categories and guidance direction from text. It does not predict prices,
recommend trades, or connect to any brokerage.

Usage:
    # legacy paths (unchanged)
    python3 eval.py --dry-run                      # synthetic predictions, no model/GPU needed
    python3 eval.py --predictions preds.jsonl      # preds.jsonl = {"chunk_id":..., "raw_output": "<model's raw text>"}

    # real path -- generate with the fine-tuned MLX adapter, then score
    .mlx_venv/bin/python eval.py --backend mlx

    # score/re-render the report from an existing predictions.jsonl (no model, no GPU)
    .mlx_venv/bin/python eval.py --backend mlx --score-only \
        --out-dir runs/2026-08-21-eval-epoch1

    # one-off regeneration of the chunk_id -> section_type sidecar (needs pandas;
    # run with the SYSTEM python3, not the mlx venv)
    python3 eval.py --write-section-types

See `finetune/runs/EVAL_RUNBOOK.md` for the exact command to run after the
fine-tune finishes, the expected wall-clock, and what "done" looks like.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_JSONL = HERE / "prepared" / "eval.jsonl"

GUIDANCE_LABELS = ["RAISED", "MAINTAINED", "LOWERED", "WITHDRAWN", "NONE"]
SENTIMENT_LABELS = ["POSITIVE", "NEUTRAL", "NEGATIVE"]
RED_FLAG_CATEGORIES = [
    "DEMAND_WEAKNESS", "SUPPLY_INPUT_CONSTRAINT", "TRADE_POLICY_EXPOSURE",
    "IMPAIRMENT_WRITEDOWN", "MARGIN_COST_PRESSURE", "LEGAL_REGULATORY_ACTION",
]
RED_FLAG_MODALITIES = ["HYPOTHETICAL", "REALIZED"]

# --- real-path paths / defaults ---------------------------------------------
MLX_DATA_DIR = HERE / "mlx_data"
MLX_VALID_JSONL = MLX_DATA_DIR / "valid.jsonl"
SPLITS_EVAL_PARQUET = HERE / "splits" / "eval.parquet"
SECTION_TYPES_JSON = HERE / "eval_section_types.json"
DEFAULT_TRAIN_MANIFEST = (
    HERE / "runs" / "2026-08-21-epoch1-resume-from-500" / "manifest.json"
)

# The three keys PROMPT_TEMPLATE.md allows in a target JSON object. Anything
# else the model emits (including `distress_tier`, which it was never trained
# on) is a schema violation and is counted as one.
ALLOWED_TOP_LEVEL_KEYS = ("sentiment", "guidance_direction", "red_flags")

# HANDOFF.md §7: not evaluable, excluded from headline tables, reason printed.
HEADLINE_EXCLUDED_SECTION_TYPES = ("8K_BODY",)
NOT_EVALUABLE_REASONS = {
    "8K_BODY": (
        "n=8 corpus-wide from only 2 tickers (BAC, CVX); all 8 landed in the "
        "eval split. No per-class estimate on 8 rows from 2 issuers is stable, "
        "so 8K_BODY rows are excluded from every headline table and reported "
        "separately below (HANDOFF.md §7)."
    ),
    "WITHDRAWN": (
        "guidance_direction=WITHDRAWN has exactly 1 example corpus-wide and it "
        "is in the TRAIN split, so eval support is 0. A P/R/F1 row for it would "
        "be three zeros masquerading as a measurement (HANDOFF.md §7)."
    ),
}

# Sentinel "predicted values" for failure modes. These can never equal a gold
# label, so they always score as errors -- they exist so failures show up in a
# named bucket instead of being dropped from a denominator.
S_UNPARSEABLE = "__UNPARSEABLE__"
S_MISSING_FIELD = "__MISSING_FIELD__"
S_INVALID_ENUM = "__INVALID_ENUM__"
FAILURE_SENTINELS = (S_UNPARSEABLE, S_MISSING_FIELD, S_INVALID_ENUM)

# Teacher-noise figures quoted in every report header. Sourced, not rounded.
TEACHER_NOISE = {
    "red_flags_set_level_error_pooled": "36.6% (146/399 exact-set disagreements, sample-pooled)",
    "red_flags_set_level_error_base_rate": "~25.0% (Tier C, n=36, 95% CI [13.8, 41.1] on error)",
    "red_flags_per_category_error": "7.5% (180 category corrections / 2,394 chunk-category decisions)",
    "sentiment_agreement": "94.6% [91.3, 96.7]",
    "guidance_agreement": "95.2% [90.4, 97.6]",
    "source": "HANDOFF.md §2a + RED_FLAGS_LIMITATION.md (spot-check second-rater pass, 2026-08-18)",
}


def load_eval_examples() -> list[dict]:
    if not EVAL_JSONL.exists():
        raise FileNotFoundError(f"{EVAL_JSONL} not found -- run prepare_dataset.py first")
    examples = []
    with open(EVAL_JSONL) as f:
        for line in f:
            examples.append(json.loads(line))
    return examples


def parse_model_output(raw_output: str) -> tuple[dict | None, str | None]:
    """Returns (parsed_dict, None) on success, or (None, error_reason) on
    failure. Failure is never silently dropped -- callers must handle the
    error_reason case as an explicit UNPARSEABLE outcome."""
    if raw_output is None:
        return None, "null_output"
    text = raw_output.strip()
    # Tolerate a model that wraps JSON in a code fence despite instructions.
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        return None, f"json_decode_error: {e}"
    if not isinstance(obj, dict):
        return None, "not_a_json_object"
    return obj, None


def prf1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return precision, recall, f1


def eval_single_label(golds: list[str | None], preds: list[str | None], labels: list[str]) -> dict:
    """Per-class + macro precision/recall/F1 for a single-label categorical
    field. `None` predictions (field absent / unparseable) count as wrong
    for whichever gold label they were supposed to match (never dropped)."""
    per_class = {}
    for lb in labels:
        tp = sum(1 for g, p in zip(golds, preds) if g == lb and p == lb)
        fp = sum(1 for g, p in zip(golds, preds) if g != lb and p == lb)
        fn = sum(1 for g, p in zip(golds, preds) if g == lb and p != lb)
        support = sum(1 for g in golds if g == lb)
        precision, recall, f1 = prf1(tp, fp, fn)
        per_class[lb] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "support": support,
        }
    macro_p = sum(v["precision"] for v in per_class.values()) / len(labels)
    macro_r = sum(v["recall"] for v in per_class.values()) / len(labels)
    macro_f1 = sum(v["f1"] for v in per_class.values()) / len(labels)
    accuracy = sum(1 for g, p in zip(golds, preds) if g == p) / len(golds) if golds else 0.0
    return {
        "per_class": per_class,
        "macro_precision": round(macro_p, 3),
        "macro_recall": round(macro_r, 3),
        "macro_f1": round(macro_f1, 3),
        "accuracy": round(accuracy, 3),
        "n": len(golds),
    }


def eval_multilabel(gold_sets: list[set[str]], pred_sets: list[set[str]], labels: list[str]) -> dict:
    per_class = {}
    for lb in labels:
        tp = sum(1 for g, p in zip(gold_sets, pred_sets) if lb in g and lb in p)
        fp = sum(1 for g, p in zip(gold_sets, pred_sets) if lb not in g and lb in p)
        fn = sum(1 for g, p in zip(gold_sets, pred_sets) if lb in g and lb not in p)
        support = sum(1 for g in gold_sets if lb in g)
        precision, recall, f1 = prf1(tp, fp, fn)
        per_class[lb] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "support": support,
        }
    macro_p = sum(v["precision"] for v in per_class.values()) / len(labels)
    macro_r = sum(v["recall"] for v in per_class.values()) / len(labels)
    macro_f1 = sum(v["f1"] for v in per_class.values()) / len(labels)
    return {
        "per_class": per_class,
        "macro_precision": round(macro_p, 3),
        "macro_recall": round(macro_r, 3),
        "macro_f1": round(macro_f1, 3),
        "n": len(gold_sets),
    }


def run_eval(examples: list[dict], predictions_by_id: dict[str, str]) -> dict:
    """`predictions_by_id`: chunk_id -> raw model output text (unparsed)."""
    n_total = len(examples)
    n_unparseable = 0
    unparseable_reasons = Counter()

    sentiment_gold, sentiment_pred = [], []
    guidance_gold, guidance_pred = [], []
    redflag_gold_sets, redflag_pred_sets = [], []

    for ex in examples:
        gold = json.loads(ex["output"])
        raw_pred = predictions_by_id.get(ex["chunk_id"])
        parsed, err = parse_model_output(raw_pred) if raw_pred is not None else (None, "missing_prediction")

        if parsed is None:
            n_unparseable += 1
            unparseable_reasons[err] += 1
            # Explicit failure: counts against every applicable field for this example.
            if "sentiment" in gold:
                sentiment_gold.append(gold["sentiment"])
                sentiment_pred.append("UNPARSEABLE")
            if "guidance_direction" in gold:
                guidance_gold.append(gold["guidance_direction"])
                guidance_pred.append("UNPARSEABLE")
            if "red_flags" in gold:
                redflag_gold_sets.append({f["category"] for f in gold["red_flags"]})
                redflag_pred_sets.append(set())  # no categories recoverable
            continue

        if "sentiment" in gold:
            sentiment_gold.append(gold["sentiment"])
            sentiment_pred.append(parsed.get("sentiment", "MISSING_FIELD"))
        if "guidance_direction" in gold:
            guidance_gold.append(gold["guidance_direction"])
            guidance_pred.append(parsed.get("guidance_direction", "MISSING_FIELD"))
        if "red_flags" in gold:
            redflag_gold_sets.append({f["category"] for f in gold["red_flags"]})
            pred_flags = parsed.get("red_flags", [])
            pred_cats = set()
            if isinstance(pred_flags, list):
                for f in pred_flags:
                    if isinstance(f, dict) and "category" in f:
                        pred_cats.add(f["category"])
            redflag_pred_sets.append(pred_cats)

    results = {
        "n_total_examples": n_total,
        "n_unparseable": n_unparseable,
        "unparseable_rate": round(n_unparseable / n_total, 3) if n_total else 0.0,
        "unparseable_reasons": dict(unparseable_reasons),
        "sentiment": eval_single_label(sentiment_gold, sentiment_pred, SENTIMENT_LABELS + ["UNPARSEABLE", "MISSING_FIELD"]),
        "guidance_direction": eval_single_label(guidance_gold, guidance_pred, GUIDANCE_LABELS + ["UNPARSEABLE", "MISSING_FIELD"]),
        "red_flags": eval_multilabel(redflag_gold_sets, redflag_pred_sets, RED_FLAG_CATEGORIES),
    }
    return results


def print_report(results: dict) -> None:
    print("=" * 70)
    print("HELD-OUT EVALUATION REPORT")
    print("=" * 70)
    print(f"Total eval examples: {results['n_total_examples']}")
    print(f"Unparseable model outputs: {results['n_unparseable']} "
          f"({results['unparseable_rate']:.1%}) -- reported as an explicit failure "
          f"category, counted against every applicable field, never dropped.")
    if results["unparseable_reasons"]:
        print(f"  Reasons: {results['unparseable_reasons']}")
    print()

    for field in ("sentiment", "guidance_direction"):
        r = results[field]
        print(f"--- {field} (n={r['n']}, accuracy={r['accuracy']:.1%}, "
              f"macro P/R/F1={r['macro_precision']:.3f}/{r['macro_recall']:.3f}/{r['macro_f1']:.3f}) ---")
        for lb, m in r["per_class"].items():
            flag = "  <-- ZERO SUPPORT, not evaluable" if m["support"] == 0 else ""
            flag = "  <-- WEAK" if (m["support"] > 0 and m["f1"] < 0.3) else flag
            print(f"    {lb:16s} support={m['support']:5d}  P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f}{flag}")
        print()

    r = results["red_flags"]
    print(f"--- red_flags (multi-label, n={r['n']}, "
          f"macro P/R/F1={r['macro_precision']:.3f}/{r['macro_recall']:.3f}/{r['macro_f1']:.3f}) ---")
    for lb, m in r["per_class"].items():
        flag = "  <-- WEAK" if m["f1"] < 0.3 else ""
        print(f"    {lb:26s} support={m['support']:5d}  P={m['precision']:.3f} R={m['recall']:.3f} F1={m['f1']:.3f}{flag}")
    print()

    print("NOTE: distress_tier is excluded from this report entirely -- it was excluded "
          "from training targets (see PROMPT_TEMPLATE.md / DISCOVERY.md §3), so the model "
          "was never trained to predict it and evaluating it here would be meaningless.")
    print("NOTE: 8K_BODY has only 8 examples total in the whole labeled corpus (see "
          "SPLIT_DESIGN.md) and guidance:WITHDRAWN has exactly 1 example corpus-wide, "
          "currently in train, not eval -- per-class numbers above for very low-support "
          "classes (see 'support' column) should not be read as statistically meaningful, "
          "and this is stated here rather than presented as a working metric.")
    print("=" * 70)


def make_synthetic_predictions(examples: list[dict], seed: int = 42) -> dict[str, str]:
    """--dry-run only: synthetic predictions to validate the eval pipeline
    itself (parsing, metric computation, report formatting) without a real
    model. Deliberately includes a mix of correct, incorrect, missing-field,
    and unparseable outputs so all code paths are exercised."""
    rng = random.Random(seed)
    preds = {}
    for i, ex in enumerate(examples):
        gold = json.loads(ex["output"])
        mode = rng.random()
        if mode < 0.05:
            preds[ex["chunk_id"]] = "not json at all {{{"
            continue
        pred = dict(gold)  # start from correct
        if "sentiment" in pred and rng.random() < 0.3:
            pred["sentiment"] = rng.choice(SENTIMENT_LABELS)
        if "guidance_direction" in pred and rng.random() < 0.3:
            pred["guidance_direction"] = rng.choice(GUIDANCE_LABELS)
        if "red_flags" in pred and rng.random() < 0.3:
            pred["red_flags"] = [
                {"category": rng.choice(RED_FLAG_CATEGORIES), "modality": "HYPOTHETICAL"}
            ] if rng.random() < 0.5 else []
        preds[ex["chunk_id"]] = json.dumps(pred)
    return preds


# ==========================================================================
# REAL (non-dry-run) EVALUATION PATH
# ==========================================================================
# Everything above this line is the original dry-run/offline scorer and is
# left behaviourally untouched: `--dry-run` prints exactly the bytes it
# printed before this section existed.
#
# Everything below implements `--backend mlx`: render the frozen 1,010-row
# eval split through THE rendering contract, generate greedily with the
# fine-tuned adapter, checkpoint every row, and score on the bases the
# standing rules require.
# ==========================================================================


# --- hashing / small utilities ---------------------------------------------

def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _pct(num: int, den: int) -> str:
    return f"{(100.0 * num / den):.1f}%" if den else "n/a"


def _quantiles(xs: list, ps=(50, 90, 95, 99)) -> dict:
    """Percentiles that degrade gracefully on tiny samples (a resumed run
    that only generated 3 rows must not crash the report)."""
    if not xs:
        return {f"p{p}": None for p in ps}
    s = sorted(xs)
    if len(s) < 2:
        return {f"p{p}": s[0] for p in ps}
    q = statistics.quantiles(s, n=100, method="inclusive")
    return {f"p{p}": q[p - 1] for p in ps}


# --- chunk_id -> section_type sidecar --------------------------------------
# `splits/eval.parquet` carries section_type, but the mlx venv has no pandas
# (and the eval must run inside that venv, because that is where mlx_lm
# lives). So the mapping is materialised once, offline, into a small JSON
# sidecar with the source hash recorded. The parquet itself is never
# modified -- it is opened read-only.

def write_section_types(out_path=SECTION_TYPES_JSON, source=SPLITS_EVAL_PARQUET) -> dict:
    """Regenerate the chunk_id -> section_type sidecar from an eval split parquet.
    Needs pandas; run with the SYSTEM python3, not the mlx venv.

    `source` defaults to E1's `splits/eval.parquet`. The rubric-v1.2 splits give
    an identical mapping (eval membership is frozen and section_type is corpus
    metadata, not a label), so regenerating is optional there -- but the flag
    exists so the campaign can be reproduced from its own artifacts."""
    import pandas as pd  # lazy: only this one entry point needs it

    source = Path(source)
    df = pd.read_parquet(source, columns=["chunk_id", "section_type"])
    mapping = {str(r.chunk_id): str(r.section_type) for r in df.itertuples()}
    payload = {
        "_source": str(source),
        "_source_sha256": sha256_file(source),
        "_generated_utc": datetime.now(timezone.utc).isoformat(),
        "_generator": "eval.py --write-section-types",
        "_note": (
            "Read-only derivation of splits/eval.parquet. section_type is used ONLY "
            "to exclude 8K_BODY from headline tables (HANDOFF.md §7) and to break out "
            "per-section results. It is NEVER placed in a prompt -- PROMPT_TEMPLATE.md "
            "forbids the section_type string appearing as prompt text anywhere."
        ),
        "_counts": dict(Counter(mapping.values())),
        "section_type_by_chunk_id": mapping,
    }
    out_path = Path(out_path)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    return payload


def load_section_types(path=SECTION_TYPES_JSON) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. It is required so 8K_BODY can be excluded from the "
            f"headline tables (HANDOFF.md §7). Regenerate it with the SYSTEM python3 "
            f"(the mlx venv has no pandas):\n"
            f"    python3 {Path(__file__).resolve()} --write-section-types"
        )
    payload = json.loads(path.read_text())
    return payload["section_type_by_chunk_id"]


# --- eval rows + the rendering contract ------------------------------------

def load_eval_rows(
    mlx_valid=MLX_VALID_JSONL,
    prepared_eval=EVAL_JSONL,
    verify_train_instruction: bool = True,
    mlx_train=None,
) -> tuple[list[dict], dict]:
    """Load the 1,010 frozen eval rows and verify, before a single token is
    generated, that what we are about to feed the model is byte-identical to
    what the trainer fed it.

    The rows come from `mlx_data/valid.jsonl` -- i.e. the exact rendered
    records the trainer used -- NOT from `prepared/eval.jsonl`. That matters:
    49 of the 1,010 eval passages were head-truncated by `convert_to_mlx.py`
    so the rendered sequence fits max_seq_length 2048. Feeding the untruncated
    passage at inference time would put the model outside the length regime it
    was trained/validated in, on exactly the rows already known to be longest.
    `prepared/eval.jsonl` is still opened, read-only, to cross-check that every
    gold answer matches and that each (possibly truncated) passage is a genuine
    head-prefix of the original -- so truncation can never have swapped,
    reordered or rewritten a passage.

    Returns (rows, provenance).
    """
    mlx_valid, prepared_eval = Path(mlx_valid), Path(prepared_eval)
    for p in (mlx_valid, prepared_eval):
        if not p.exists():
            raise FileNotFoundError(f"{p} not found -- run convert_to_mlx.py / prepare_dataset.py first")

    prepared = {}
    with open(prepared_eval) as f:
        for line in f:
            rec = json.loads(line)
            prepared[rec["chunk_id"]] = rec

    rows = []
    instructions = set()
    n_truncated = 0
    with open(mlx_valid) as f:
        for i, line in enumerate(f):
            rec = json.loads(line)
            messages = rec["messages"]
            roles = [m["role"] for m in messages]
            if roles != ["system", "user", "assistant"]:
                raise AssertionError(
                    f"{mlx_valid}[{i}] chunk={rec['chunk_id']}: message roles are {roles}, "
                    f"but the rendering contract is [system, user, assistant] "
                    f"(convert_to_mlx.py::to_messages)"
                )
            instruction = messages[0]["content"]
            passage = messages[1]["content"]
            gold_text = messages[2]["content"]
            instructions.add(instruction)

            src = prepared.get(rec["chunk_id"])
            if src is None:
                raise AssertionError(
                    f"chunk {rec['chunk_id']} is in {mlx_valid} but not in {prepared_eval} -- "
                    f"the two artifacts are out of sync; do not evaluate against them"
                )
            if gold_text != src["output"]:
                raise AssertionError(
                    f"chunk {rec['chunk_id']}: gold answer differs between {mlx_valid} and "
                    f"{prepared_eval}. Refusing to score against an ambiguous label."
                )
            if instruction != src["instruction"]:
                raise AssertionError(
                    f"chunk {rec['chunk_id']}: instruction differs between {mlx_valid} and "
                    f"{prepared_eval}"
                )
            if passage != src["input"]:
                n_truncated += 1
                if not src["input"].startswith(passage):
                    raise AssertionError(
                        f"chunk {rec['chunk_id']}: the rendered passage is not a head-prefix "
                        f"of the original passage -- convert_to_mlx.py only ever drops the "
                        f"TAIL of a passage, so this means the artifacts disagree about the text"
                    )

            rows.append(
                {
                    "chunk_id": rec["chunk_id"],
                    "instruction": instruction,
                    "passage": passage,
                    "gold_text": gold_text,
                    "gold": json.loads(gold_text),
                    "messages": messages,
                    "passage_was_truncated": passage != src["input"],
                }
            )

    if len(instructions) != 1:
        raise AssertionError(
            f"instruction is NOT byte-identical across the eval rows "
            f"({len(instructions)} distinct values). PROMPT_TEMPLATE.md requires exactly one."
        )
    instruction = next(iter(instructions))

    train_instruction_checked = False
    if verify_train_instruction:
        # Default to train.jsonl BESIDE the valid.jsonl being evaluated, so a
        # non-default --mlx-data-dir cross-checks its own train split rather
        # than E1's. Explicitly overridable for tests.
        train_path = Path(mlx_train) if mlx_train is not None else mlx_valid.parent / "train.jsonl"
        if train_path.exists():
            n_bad = 0
            with open(train_path) as f:
                for line in f:
                    if json.loads(line)["messages"][0]["content"] != instruction:
                        n_bad += 1
            if n_bad:
                raise AssertionError(
                    f"{n_bad} TRAIN rows have a system instruction that differs from the "
                    f"eval instruction. Inference would then be prompted differently from "
                    f"training -- the eval would be measuring the wrong thing. Refusing to run."
                )
            train_instruction_checked = True

    provenance = {
        "eval_rows_file": str(mlx_valid),
        "eval_rows_sha256": sha256_file(mlx_valid),
        "prepared_eval_file": str(prepared_eval),
        "prepared_eval_sha256": sha256_file(prepared_eval),
        "n_rows": len(rows),
        "n_passages_head_truncated_to_fit_2048": n_truncated,
        "instruction_sha256": sha256_text(instruction),
        "instruction_chars": len(instruction),
        "instruction_byte_identical_across_eval": True,
        "instruction_byte_identical_to_train": train_instruction_checked,
    }
    return rows, provenance


def render_prompt_token_ids(tokenizer, row: dict) -> list:
    """THE inference-side rendering contract, reusing convert_to_mlx.py's own
    code rather than restating it.

    `convert_to_mlx.render` returns (all_token_ids, prompt_offset) where
    `prompt_offset = len(apply_chat_template(messages[:-1],
    add_generation_prompt=True))`. So `all_token_ids[:prompt_offset]` IS the
    inference prompt, and it is a token-exact prefix of the sequence the
    trainer saw for this row -- by construction, not by a parallel
    reimplementation that could drift.

    Nothing is appended or prepended: the prompt is exactly
    system=<instruction> / user=<passage> / <generation prompt>.
    """
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    import convert_to_mlx as c2m

    messages = c2m.to_messages(row["instruction"], row["passage"], row["gold_text"])
    if messages != row["messages"]:
        raise AssertionError(
            f"chunk {row['chunk_id']}: convert_to_mlx.to_messages() does not reproduce the "
            f"stored messages -- the rendering contract and the training data disagree"
        )
    all_ids, offset = c2m.render(tokenizer, messages)
    if not (0 < offset < len(all_ids)):
        raise AssertionError(
            f"chunk {row['chunk_id']}: nonsensical prompt offset {offset} for a "
            f"{len(all_ids)}-token sequence"
        )
    return list(all_ids[:offset])


# --- schema validation + field extraction ----------------------------------

def validate_schema(obj: dict) -> list:
    """Structural validation of a parsed model object against
    PROMPT_TEMPLATE.md's target schema. Returns a list of issue strings
    (empty == clean). A schema issue is NOT a parse failure: the object
    parsed, so its usable fields are still scored. Both rates are reported.
    """
    issues = []
    for k in obj:
        if k not in ALLOWED_TOP_LEVEL_KEYS:
            issues.append(f"extra_key:{k}")

    if "sentiment" in obj and obj["sentiment"] not in SENTIMENT_LABELS:
        issues.append("bad_enum:sentiment")
    if "guidance_direction" in obj and obj["guidance_direction"] not in GUIDANCE_LABELS:
        issues.append("bad_enum:guidance_direction")

    if "red_flags" not in obj:
        # The instruction says "Always include this field, with an empty list
        # if nothing matches" -- so its absence is a schema violation, not an
        # applicability judgment.
        issues.append("missing_key:red_flags")
    elif not isinstance(obj["red_flags"], list):
        issues.append("bad_type:red_flags")
    else:
        for f in obj["red_flags"]:
            if not isinstance(f, dict):
                issues.append("bad_type:red_flag_entry")
                continue
            for k in f:
                if k not in ("category", "modality"):
                    issues.append(f"extra_key:red_flag_entry:{k}")
            if f.get("category") not in RED_FLAG_CATEGORIES:
                issues.append("bad_enum:red_flag_category")
            if f.get("modality") not in RED_FLAG_MODALITIES:
                issues.append("bad_enum:red_flag_modality")
    return issues


def extract_red_flag_pairs(obj: dict) -> tuple[set, set]:
    """(category, modality) pairs and bare categories from a parsed object.
    Entries that are not well-formed or not in the taxonomy are dropped from
    the scored sets -- they are already counted as schema violations, and
    inventing a category to score would corrupt the per-category table."""
    pairs, cats = set(), set()
    flags = obj.get("red_flags")
    if isinstance(flags, list):
        for f in flags:
            if not isinstance(f, dict):
                continue
            cat, mod = f.get("category"), f.get("modality")
            if cat in RED_FLAG_CATEGORIES:
                cats.add(cat)
                if mod in RED_FLAG_MODALITIES:
                    pairs.add((cat, mod))
    return pairs, cats


def predicted_single_label(parsed, field: str, labels: list, parse_failed: bool) -> str:
    """Map a model output to a scoreable value for a single-label field.
    Failures become named sentinels, never dropped."""
    if parse_failed:
        return S_UNPARSEABLE
    if field not in parsed:
        return S_MISSING_FIELD
    value = parsed[field]
    if value not in labels:
        return S_INVALID_ENUM
    return value


# --- metrics ----------------------------------------------------------------

def score_single_label(golds: list, preds: list, labels: list) -> dict:
    """Per-class P/R/F1 + macro for one single-label field.

    Differences from the legacy `eval_single_label` above, all deliberate:
      * the macro average is taken over classes WITH SUPPORT IN THIS SPLIT
        only. Averaging in a zero-support class contributes a structural 0.0
        and silently drags the headline down; zero-support classes are listed
        separately as not evaluable instead (WITHDRAWN is exactly this case).
      * failure sentinels are reported in their own attribution table rather
        than as pseudo-classes.
    """
    per_class = {}
    for lb in labels:
        tp = sum(1 for g, p in zip(golds, preds) if g == lb and p == lb)
        fp = sum(1 for g, p in zip(golds, preds) if g != lb and p == lb)
        fn = sum(1 for g, p in zip(golds, preds) if g == lb and p != lb)
        support = sum(1 for g in golds if g == lb)
        precision, recall, f1 = prf1(tp, fp, fn)
        per_class[lb] = {
            "support": support, "tp": tp, "fp": fp, "fn": fn,
            "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
        }
    supported = [lb for lb in labels if per_class[lb]["support"] > 0]
    zero_support = [lb for lb in labels if per_class[lb]["support"] == 0]
    n = len(golds)
    correct = sum(1 for g, p in zip(golds, preds) if g == p)

    def _macro(key):
        return round(sum(per_class[lb][key] for lb in supported) / len(supported), 3) if supported else 0.0

    return {
        "n": n,
        "exact_match": round(correct / n, 4) if n else 0.0,
        "n_correct": correct,
        "per_class": per_class,
        "macro_over_supported_classes": {
            "classes": supported,
            "precision": _macro("precision"),
            "recall": _macro("recall"),
            "f1": _macro("f1"),
        },
        "zero_support_classes": zero_support,
        "failure_attribution": dict(Counter(p for p in preds if p in FAILURE_SENTINELS)),
        "confusion": {
            f"{g}->{p}": c
            for (g, p), c in sorted(Counter(zip(golds, preds)).items())
            if g != p
        },
    }


def score_red_flags(gold_pairsets: list, pred_pairsets: list, parse_failed: list) -> dict:
    """red_flags on BOTH bases, because quoting only one is misleading.

    HANDOFF.md §2a: the spot-check's headline 63.4% red-flag agreement is an
    EXACT-SET-MATCH rate -- one added, dropped or re-modalized category on a
    four-category chunk scores the whole chunk as a disagreement -- and it is
    not comparable to the single-value rates printed beside it. The same
    disagreements decompose to 7.5% per-category error. Both bases are
    therefore computed here and printed together, always.

    An unparseable row is scored as a set-level MISMATCH even when the gold
    set is empty. Treating "no output at all" as a correct prediction of the
    empty set would silently reward failure -- the empty-gold case is 60%+ of
    this corpus, so that inflation would be large.
    """
    n = len(gold_pairsets)
    assert len(pred_pairsets) == n == len(parse_failed)

    exact_pair = exact_cat = 0
    for g, p, failed in zip(gold_pairsets, pred_pairsets, parse_failed):
        if failed:
            continue
        if g == p:
            exact_pair += 1
        if {c for c, _ in g} == {c for c, _ in p}:
            exact_cat += 1

    per_class = {}
    n_decisions = n * len(RED_FLAG_CATEGORIES)
    n_decision_errors = 0
    for cat in RED_FLAG_CATEGORIES:
        tp = fp = fn = tn = 0
        for g, p in zip(gold_pairsets, pred_pairsets):
            gin = any(c == cat for c, _ in g)
            pin = any(c == cat for c, _ in p)
            if gin and pin:
                tp += 1
            elif pin:
                fp += 1
            elif gin:
                fn += 1
            else:
                tn += 1
        n_decision_errors += fp + fn
        precision, recall, f1 = prf1(tp, fp, fn)
        per_class[cat] = {
            "support": tp + fn, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
        }

    micro_tp = sum(v["tp"] for v in per_class.values())
    micro_fp = sum(v["fp"] for v in per_class.values())
    micro_fn = sum(v["fn"] for v in per_class.values())
    micro_p, micro_r, micro_f1 = prf1(micro_tp, micro_fp, micro_fn)
    supported = [c for c in RED_FLAG_CATEGORIES if per_class[c]["support"] > 0]

    # Modality: only meaningful where both sides agree the category is present.
    mod_n = mod_ok = 0
    modality_confusion = Counter()
    for g, p in zip(gold_pairsets, pred_pairsets):
        gmod = {c: m for c, m in g}
        pmod = {c: m for c, m in p}
        for cat in set(gmod) & set(pmod):
            mod_n += 1
            if gmod[cat] == pmod[cat]:
                mod_ok += 1
            else:
                modality_confusion[f"{gmod[cat]}->{pmod[cat]}"] += 1

    return {
        "n": n,
        "n_parse_failed": sum(1 for x in parse_failed if x),
        "exact_set_match_category_modality": {
            "n_match": exact_pair, "n": n, "rate": round(exact_pair / n, 4) if n else 0.0,
        },
        "exact_set_match_category_only": {
            "n_match": exact_cat, "n": n, "rate": round(exact_cat / n, 4) if n else 0.0,
        },
        "per_category": per_class,
        "per_category_decisions": {
            "n_decisions": n_decisions,
            "n_errors": n_decision_errors,
            "error_rate": round(n_decision_errors / n_decisions, 4) if n_decisions else 0.0,
            "agreement_rate": round(1 - n_decision_errors / n_decisions, 4) if n_decisions else 0.0,
        },
        "micro": {
            "precision": round(micro_p, 3), "recall": round(micro_r, 3), "f1": round(micro_f1, 3),
            "tp": micro_tp, "fp": micro_fp, "fn": micro_fn,
        },
        "macro_over_supported_categories": {
            "categories": supported,
            "precision": round(sum(per_class[c]["precision"] for c in supported) / len(supported), 3) if supported else 0.0,
            "recall": round(sum(per_class[c]["recall"] for c in supported) / len(supported), 3) if supported else 0.0,
            "f1": round(sum(per_class[c]["f1"] for c in supported) / len(supported), 3) if supported else 0.0,
        },
        "zero_support_categories": [c for c in RED_FLAG_CATEGORIES if per_class[c]["support"] == 0],
        "modality_given_category_agreed": {
            "n": mod_n, "n_agree": mod_ok,
            "rate": round(mod_ok / mod_n, 4) if mod_n else None,
            "confusion": dict(modality_confusion),
        },
    }


def score_slice(rows: list, preds_by_id: dict) -> dict:
    """Score one slice of eval rows. `preds_by_id`: chunk_id -> raw text."""
    n = len(rows)
    n_missing = n_unparseable = 0
    parse_reasons = Counter()
    schema_issues = Counter()
    n_schema_violations = 0

    sent_g, sent_p = [], []
    guid_g, guid_p = [], []
    rf_gold, rf_pred, rf_failed = [], [], []
    presence = {
        f: Counter() for f in ("sentiment", "guidance_direction")
    }

    for row in rows:
        gold = row["gold"]
        raw = preds_by_id.get(row["chunk_id"])
        if raw is None:
            n_missing += 1
            parsed, err = None, "missing_prediction"
        else:
            parsed, err = parse_model_output(raw)
        failed = parsed is None
        if failed:
            n_unparseable += 1
            parse_reasons[err.split(":")[0] if err else "unknown"] += 1
        else:
            issues = validate_schema(parsed)
            if issues:
                n_schema_violations += 1
                for i in issues:
                    schema_issues[i] += 1

        if "sentiment" in gold:
            sent_g.append(gold["sentiment"])
            sent_p.append(predicted_single_label(parsed or {}, "sentiment", SENTIMENT_LABELS, failed))
        if "guidance_direction" in gold:
            guid_g.append(gold["guidance_direction"])
            guid_p.append(predicted_single_label(parsed or {}, "guidance_direction", GUIDANCE_LABELS, failed))

        # Field-presence (applicability) agreement: PROMPT_TEMPLATE.md encodes
        # the applicability matrix ONLY through which fields appear in the
        # target -- section_type is never in the prompt -- so "did it emit the
        # right fields" is itself a learned behaviour worth measuring.
        for f in ("sentiment", "guidance_direction"):
            applicable = f in gold
            if failed:
                presence[f]["undetermined_unparseable"] += 1
            else:
                emitted = f in parsed
                presence[f][f"gold_{'yes' if applicable else 'no'}_pred_{'yes' if emitted else 'no'}"] += 1

        if "red_flags" in gold:
            rf_gold.append({(f["category"], f["modality"]) for f in gold["red_flags"]})
            gp, _ = extract_red_flag_pairs(parsed or {})
            rf_pred.append(gp)
            rf_failed.append(failed)

    presence_out = {}
    for f, c in presence.items():
        determined = sum(v for k, v in c.items() if k != "undetermined_unparseable")
        agree = c.get("gold_yes_pred_yes", 0) + c.get("gold_no_pred_no", 0)
        presence_out[f] = {
            "counts": dict(c),
            "n_determined": determined,
            "n_agree": agree,
            "agreement_rate": round(agree / determined, 4) if determined else None,
        }

    return {
        "n_rows": n,
        "parse": {
            "n_missing_prediction": n_missing,
            "n_unparseable": n_unparseable,
            "parse_failure_rate": round(n_unparseable / n, 4) if n else 0.0,
            "reasons": dict(parse_reasons),
        },
        "schema": {
            "n_rows_with_violations": n_schema_violations,
            "violation_rate": round(n_schema_violations / n, 4) if n else 0.0,
            "issues": dict(schema_issues),
        },
        "sentiment": score_single_label(sent_g, sent_p, SENTIMENT_LABELS),
        "guidance_direction": score_single_label(guid_g, guid_p, GUIDANCE_LABELS),
        "red_flags": score_red_flags(rf_gold, rf_pred, rf_failed),
        "field_presence": presence_out,
    }


def score_all(rows: list, preds_by_id: dict, section_types: dict) -> dict:
    """Headline slice (8K_BODY excluded) + the excluded slices, reported
    separately and labelled not-evaluable."""
    for r in rows:
        if r["chunk_id"] not in section_types:
            raise AssertionError(
                f"chunk {r['chunk_id']} missing from the section_type sidecar; "
                f"regenerate it with `python3 eval.py --write-section-types`"
            )
    headline_rows = [r for r in rows if section_types[r["chunk_id"]] not in HEADLINE_EXCLUDED_SECTION_TYPES]
    excluded_rows = [r for r in rows if section_types[r["chunk_id"]] in HEADLINE_EXCLUDED_SECTION_TYPES]

    by_section = {}
    for st in sorted({section_types[r["chunk_id"]] for r in headline_rows}):
        sub = [r for r in headline_rows if section_types[r["chunk_id"]] == st]
        by_section[st] = score_slice(sub, preds_by_id)

    return {
        "headline": score_slice(headline_rows, preds_by_id),
        "headline_row_count": len(headline_rows),
        "excluded_row_count": len(excluded_rows),
        "excluded_slice_8K_BODY": score_slice(excluded_rows, preds_by_id) if excluded_rows else None,
        "by_section_type": by_section,
        "section_type_counts": dict(Counter(section_types[r["chunk_id"]] for r in rows)),
    }


# --- prediction store (checkpointed + resumable) ---------------------------

def load_predictions(path) -> dict:
    """Read an existing predictions.jsonl. Tolerates a torn final line (a
    kill -9 mid-write), which is the whole point of the format."""
    path = Path(path)
    out = {}
    if not path.exists():
        return out
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                print(f"  [resume] ignoring torn/incomplete final record in {path.name}", file=sys.stderr)
                continue
            if "chunk_id" in rec:
                out[rec["chunk_id"]] = rec
    return out


def append_prediction(fh, rec: dict) -> None:
    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    fh.flush()
    os.fsync(fh.fileno())


def select_rows_to_generate(rows: list, existing: dict, preds_path="predictions.jsonl") -> list:
    """Resume filter: which rows still need generating.

    Every row must already carry `_prompt_sha256`. A checkpointed record whose
    stored prompt hash disagrees with the prompt this run renders means the
    dataset or the rendering changed underneath a resume -- the two halves of
    predictions.jsonl would then come from two different prompts, which is a
    silently invalid eval. That is a hard stop, not a warning.
    """
    todo = []
    for row in rows:
        prev = existing.get(row["chunk_id"])
        if prev is None:
            todo.append(row)
            continue
        stored = prev.get("prompt_sha256")
        if stored is not None and stored != row["_prompt_sha256"]:
            raise SystemExit(
                f"chunk {row['chunk_id']}: the checkpointed prediction was generated from a "
                f"DIFFERENT prompt than the one this run renders. The dataset or the "
                f"rendering changed under a resume. Delete {preds_path} and start clean."
            )
    return todo


# --- throughput -------------------------------------------------------------

def throughput_summary(records: list, wall_seconds: float, n_generated: int) -> dict:
    """Per-row latency + running chunks/hour.

    This doubles as EXPANSION_PLAN.md F4's labeling-throughput probe: F4 needs
    to know how long it takes this exact model, on this exact machine, to emit
    one label for one chunk. The eval IS that measurement at n=1,010, which is
    20x the 50-chunk probe EXPANSION_PLAN §2b asked for -- so the projections
    below should replace the reasoned ~950 chunks/h band rather than sit
    beside it.
    """
    lat = [r["latency_s"] for r in records if r.get("latency_s") is not None]
    gen = [r["generation_tokens"] for r in records if r.get("generation_tokens") is not None]
    pro = [r["prompt_tokens"] for r in records if r.get("prompt_tokens") is not None]
    gtps = [r["generation_tps"] for r in records if r.get("generation_tps")]
    ptps = [r["prompt_tps"] for r in records if r.get("prompt_tps")]
    chunks_per_hour = (n_generated / wall_seconds * 3600.0) if wall_seconds > 0 else None

    projections = {}
    if chunks_per_hour:
        for label, n_chunks in (
            ("E1 re-label (6,746 chunks)", 6746),
            ("E2 low estimate (~70k new + 6,746 E1 = 76,746)", 76746),
            ("E2 high estimate (~98k new + 6,746 E1 = 104,746)", 104746),
        ):
            hours = n_chunks / chunks_per_hour
            projections[label] = {
                "hours": round(hours, 1),
                "overnights_at_10h": round(hours / 10.0, 1),
            }

    return {
        "n_rows_generated_this_process": n_generated,
        "wall_seconds": round(wall_seconds, 1),
        "chunks_per_hour": round(chunks_per_hour, 1) if chunks_per_hour else None,
        "latency_seconds_per_row": {
            "mean": round(statistics.fmean(lat), 3) if lat else None,
            **{k: (round(v, 3) if v is not None else None) for k, v in _quantiles(lat).items()},
            "max": round(max(lat), 3) if lat else None,
        },
        "prompt_tokens": {
            "mean": round(statistics.fmean(pro), 1) if pro else None,
            "total": sum(pro) if pro else 0,
            **_quantiles(pro),
        },
        "generation_tokens": {
            "mean": round(statistics.fmean(gen), 1) if gen else None,
            "total": sum(gen) if gen else 0,
            "max": max(gen) if gen else None,
            **_quantiles(gen),
        },
        "prefill_tokens_per_second": {
            "mean": round(statistics.fmean(ptps), 1) if ptps else None,
            **{k: (round(v, 1) if v is not None else None) for k, v in _quantiles(ptps).items()},
        },
        "decode_tokens_per_second": {
            "mean": round(statistics.fmean(gtps), 1) if gtps else None,
            **{k: (round(v, 1) if v is not None else None) for k, v in _quantiles(gtps).items()},
        },
        "finish_reasons": dict(Counter(r.get("finish_reason") for r in records)),
        "f4_note": (
            "These figures are EXPANSION_PLAN.md F4's labeling-throughput probe, "
            "measured at n=1,010 on this machine with this adapter."
        ),
        "projections": projections,
    }


# --- report -----------------------------------------------------------------

def _table(headers: list, rows: list) -> str:
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(c) for c in r) + " |")
    return "\n".join(out)


def _single_label_section(title: str, res: dict, teacher_rate: str) -> str:
    lines = [f"### {title}", ""]
    lines.append(
        f"n = {res['n']} rows where the teacher's label includes this field. "
        f"**Exact-match agreement with the teacher: {res['exact_match']:.1%}** "
        f"({res['n_correct']}/{res['n']}). "
        f"Teacher's own second-rater agreement on this field: {teacher_rate}."
    )
    lines.append("")
    rows = []
    for lb, m in res["per_class"].items():
        note = ""
        if m["support"] == 0:
            note = "**NOT EVALUABLE — zero support in eval**"
            if m["fp"]:
                note += f" (the model still emitted it {m['fp']}×; all are false positives)"
        elif m["support"] < 10:
            note = f"**very low support (n={m['support']}) — not a stable estimate**"
        elif m["f1"] < 0.3:
            note = "**WEAK**"
        rows.append([lb, m["support"], m["tp"], m["fp"], m["fn"],
                     f"{m['precision']:.3f}", f"{m['recall']:.3f}", f"{m['f1']:.3f}", note])
    lines.append(_table(["class", "support", "TP", "FP", "FN", "P", "R", "F1", "note"], rows))
    lines.append("")
    mac = res["macro_over_supported_classes"]
    lines.append(
        f"Macro over classes **with support in this split** ({', '.join(mac['classes']) or 'none'}): "
        f"P={mac['precision']:.3f} R={mac['recall']:.3f} F1={mac['f1']:.3f}. "
        f"Zero-support classes are excluded from this average and listed as not evaluable "
        f"rather than averaged in as structural zeros."
    )
    if res["zero_support_classes"]:
        for lb in res["zero_support_classes"]:
            why = NOT_EVALUABLE_REASONS.get(lb, "zero support in the eval split")
            lines.append(f"- `{lb}`: NOT EVALUABLE — {why}")
    if res["failure_attribution"]:
        lines.append("")
        lines.append(f"Failure attribution (counted as errors, never dropped): `{res['failure_attribution']}`")
    if res["confusion"]:
        top = sorted(res["confusion"].items(), key=lambda kv: -kv[1])[:8]
        lines.append("")
        lines.append("Top confusions (gold -> predicted): " + ", ".join(f"`{k}` × {v}" for k, v in top))
    lines.append("")
    return "\n".join(lines)


def format_report(scored: dict, meta: dict) -> str:
    h = scored["headline"]
    L = []
    A = L.append

    A(f"# FinScreen held-out evaluation — {meta['run_id']}")
    A("")
    A(f"Generated {meta['generated_utc']} · adapter `{meta['adapter']['path']}` · "
      f"base `{meta['model']['path']}`")
    A("")
    A("## Read this before quoting any number")
    A("")
    A("1. **This measures AGREEMENT WITH THE TEACHER, not accuracy.** The eval-split")
    A("   labels are Claude's bootstrap labels, not human ground truth. A student that")
    A("   agrees perfectly has reproduced the teacher *including the teacher's errors*.")
    A("2. **The teacher's red-flag labels are documented as noisy.** Set-level error")
    A(f"   {TEACHER_NOISE['red_flags_set_level_error_pooled']}; base-rate-representative")
    A(f"   estimate {TEACHER_NOISE['red_flags_set_level_error_base_rate']}; per-category")
    A(f"   error {TEACHER_NOISE['red_flags_per_category_error']}.")
    A(f"   Source: {TEACHER_NOISE['source']}. A red-flag agreement number materially")
    A("   below the teacher's own reproducibility is not separable from teacher noise")
    A("   with this eval alone.")
    A("3. **`red_flags` is reported on two bases and both are shown, always.** The")
    A("   exact-set rate and the per-category rate answer different questions and differ")
    A("   by tens of points; quoting only the exact-set figure beside sentiment's")
    A("   single-value rate is the specific error HANDOFF.md §2a calls out.")
    A("4. **`distress_tier` is not reported.** It was excluded from the training targets")
    A("   entirely (PROMPT_TEMPLATE.md / DISCOVERY.md §3), so the student never predicts")
    A("   it and any number here would be meaningless.")
    A("5. **This is a research/screening classifier.** It extracts signals from text. It")
    A("   does not predict prices, recommend trades, or connect to any brokerage.")
    A("")

    A("## Not evaluable — excluded from every headline table")
    A("")
    for k, why in NOT_EVALUABLE_REASONS.items():
        A(f"- **{k}** — {why}")
    A("")
    A(f"Headline row count: **{scored['headline_row_count']}** of {scored['headline_row_count'] + scored['excluded_row_count']} "
      f"eval rows ({scored['excluded_row_count']} excluded as 8K_BODY).")
    A(f"Section-type mix of the full eval split: `{scored['section_type_counts']}`")
    A("")

    if meta.get("limit"):
        A(f"> **SMOKE RUN — `--limit {meta['limit']}` was set, so this covers only the first")
        A(f"> {meta['limit']} of {meta.get('n_eval_rows_in_split', '?')} eval rows, in split order.**")
        A("> The eval split is not shuffled here, so this slice is NOT a random sample and")
        A("> its rates are not the held-out result. Use it to check the plumbing only.")
        A("")
    if meta.get("partial"):
        A(f"> **PARTIAL RUN — {meta['n_scored']} of {meta['n_eval_rows']} rows have predictions.**")
        A("> Every rate below is computed over the rows present. Do not quote it as the")
        A("> held-out result until the run is complete.")
        A("")

    A("## Provenance (verify-artifact rule)")
    A("")
    prov_rows = [
        ["base model", f"`{meta['model']['path']}`"],
        ["base weights sha256", f"`{meta['model'].get('weights_sha256', 'n/a')}`"],
        ["adapter dir", f"`{meta['adapter']['path']}`"],
        ["adapters.safetensors sha256", f"`{meta['adapter']['adapters_sha256']}`"],
        ["adapters.safetensors matches checkpoint", f"`{meta['adapter'].get('matches_checkpoint', 'unknown')}`"],
        ["adapter_config.json sha256", f"`{meta['adapter']['adapter_config_sha256']}`"],
        ["training run manifest", f"`{meta['train_manifest']['path']}`"],
        ["eval rows", f"`{meta['data']['eval_rows_file']}`"],
        ["eval rows sha256", f"`{meta['data']['eval_rows_sha256']}`"],
        ["eval rows sha matches training manifest", f"`{meta['data'].get('sha_matches_train_manifest')}`"],
        ["instruction sha256", f"`{meta['data']['instruction_sha256']}`"],
        ["instruction byte-identical across eval", f"`{meta['data']['instruction_byte_identical_across_eval']}`"],
        ["instruction byte-identical to train", f"`{meta['data']['instruction_byte_identical_to_train']}`"],
        ["decoding", f"`{meta['generation']}`"],
        ["mlx / mlx_lm / transformers", f"`{meta.get('versions')}`"],
    ]
    A(_table(["item", "value"], prov_rows))
    A("")

    A("## 1. Parse and schema integrity (first-class metrics)")
    A("")
    p, s = h["parse"], h["schema"]
    A(f"- **Parse-failure rate: {p['parse_failure_rate']:.2%}** ({p['n_unparseable']}/{h['n_rows']} rows). "
      f"Reasons: `{p['reasons'] or '{}'}`.")
    A(f"- Rows with no prediction at all: {p['n_missing_prediction']}.")
    A(f"- **Schema-violation rate: {s['violation_rate']:.2%}** ({s['n_rows_with_violations']}/{h['n_rows']} rows "
      f"that parsed as JSON but broke the target schema). Issues: `{s['issues'] or '{}'}`.")
    A("")
    A("An unparseable row is counted as an error against every field the teacher labelled")
    A("for that row, and as a set-level mismatch for `red_flags` even when the teacher's")
    A("set is empty — scoring \"no output\" as a correct empty set would inflate the")
    A("red-flag headline substantially, since most rows have no flags.")
    A("")

    A("## 2. sentiment")
    A("")
    A(_single_label_section("sentiment (3-class)", h["sentiment"], TEACHER_NOISE["sentiment_agreement"]))

    A("## 3. guidance_direction")
    A("")
    A(_single_label_section("guidance_direction (5-class)", h["guidance_direction"], TEACHER_NOISE["guidance_agreement"]))

    rf = h["red_flags"]
    A("## 4. red_flags — exact-set basis")
    A("")
    A(f"- **Exact set match on (category, modality): {rf['exact_set_match_category_modality']['rate']:.2%}** "
      f"({rf['exact_set_match_category_modality']['n_match']}/{rf['n']} rows)")
    A(f"- Exact set match on categories only (modality ignored): "
      f"{rf['exact_set_match_category_only']['rate']:.2%} "
      f"({rf['exact_set_match_category_only']['n_match']}/{rf['n']} rows)")
    A(f"- {rf['n_parse_failed']} of these rows were unparseable and are counted as mismatches.")
    A("")
    A("This basis is strict by construction: one added, dropped or re-modalized category")
    A("on a multi-flag chunk fails the whole row. It is the same basis as the spot-check's")
    A(f"63.4% teacher-vs-auditor figure, so it is the comparable one — but it is NOT")
    A("comparable to the single-value sentiment/guidance rates above.")
    A("")

    A("## 5. red_flags — per-category decomposition")
    A("")
    d = rf["per_category_decisions"]
    A(f"- **Per-category agreement: {d['agreement_rate']:.2%}** "
      f"({d['n_errors']} wrong decisions over {d['n_decisions']} chunk-category decisions "
      f"= {rf['n']} rows × {len(RED_FLAG_CATEGORIES)} categories). "
      f"Teacher's own per-category error on the spot-check sample: {TEACHER_NOISE['red_flags_per_category_error']}.")
    A("")
    A("Note this rate is dominated by true negatives (most chunk-category cells are")
    A("correctly empty), which is exactly why the P/R/F1 table below is the honest read")
    A("of it and the headline percentage is not.")
    A("")
    rows = []
    for cat, m in rf["per_category"].items():
        note = ""
        if m["support"] == 0:
            note = "**NOT EVALUABLE — zero support in eval**"
        elif m["support"] < 10:
            note = f"**very low support (n={m['support']})**"
        elif m["f1"] < 0.3:
            note = "**WEAK**"
        rows.append([cat, m["support"], m["tp"], m["fp"], m["fn"],
                     f"{m['precision']:.3f}", f"{m['recall']:.3f}", f"{m['f1']:.3f}", note])
    A(_table(["category", "support", "TP", "FP", "FN", "P", "R", "F1", "note"], rows))
    A("")
    mi, ma = rf["micro"], rf["macro_over_supported_categories"]
    A(f"- Micro (all categories pooled): P={mi['precision']:.3f} R={mi['recall']:.3f} F1={mi['f1']:.3f} "
      f"(TP={mi['tp']} FP={mi['fp']} FN={mi['fn']})")
    A(f"- Macro over categories with support ({', '.join(ma['categories']) or 'none'}): "
      f"P={ma['precision']:.3f} R={ma['recall']:.3f} F1={ma['f1']:.3f}")
    if rf["zero_support_categories"]:
        A(f"- Zero-support categories, excluded from the macro and NOT evaluable: "
          f"`{rf['zero_support_categories']}`")
    mg = rf["modality_given_category_agreed"]
    A(f"- Modality agreement, restricted to (row, category) cells where both sides say the "
      f"category is present: "
      + (f"{mg['rate']:.2%} ({mg['n_agree']}/{mg['n']}), confusion `{mg['confusion'] or '{}'}`"
         if mg["rate"] is not None else "no such cells — not evaluable"))
    A("")

    A("## 6. Field-presence (applicability) agreement")
    A("")
    A("`section_type` is never in the prompt (PROMPT_TEMPLATE.md), so *which* fields to")
    A("emit is itself learned from the passage's register. This measures that directly.")
    A("")
    rows = []
    for f, m in h["field_presence"].items():
        rows.append([f, m["n_determined"], m["n_agree"],
                     f"{m['agreement_rate']:.2%}" if m["agreement_rate"] is not None else "n/a",
                     f"`{m['counts']}`"])
    A(_table(["field", "n determined", "n agree", "agreement", "breakdown"], rows))
    A("")

    A("## 7. Throughput (doubles as EXPANSION_PLAN F4's labeling-throughput probe)")
    A("")
    t = meta.get("throughput") or {}
    if t.get("chunks_per_hour"):
        if t.get("reconstructed"):
            A("> These are RECONSTRUCTED from checkpointed per-row latencies, not measured")
            A("> in this process. See the caveat below the table.")
            A("")
        A(f"- Rows {'measured' if t.get('reconstructed') else 'generated this process'}: "
          f"{t['n_rows_generated_this_process']} in "
          f"{t['wall_seconds']}s → **{t['chunks_per_hour']} chunks/hour**")
        A(f"- Per-row latency (s): mean {t['latency_seconds_per_row']['mean']}, "
          f"p50 {t['latency_seconds_per_row']['p50']}, p95 {t['latency_seconds_per_row']['p95']}, "
          f"p99 {t['latency_seconds_per_row']['p99']}, max {t['latency_seconds_per_row']['max']}")
        A(f"- Prompt tokens: mean {t['prompt_tokens']['mean']}, total {t['prompt_tokens']['total']}")
        A(f"- Generated tokens: mean {t['generation_tokens']['mean']}, max {t['generation_tokens']['max']}, "
          f"total {t['generation_tokens']['total']}")
        A(f"- Prefill: mean {t['prefill_tokens_per_second']['mean']} tok/s · "
          f"Decode: mean {t['decode_tokens_per_second']['mean']} tok/s")
        A(f"- Finish reasons: `{t['finish_reasons']}` "
          f"(`length` means the row hit --max-tokens and its JSON is probably truncated)")
        A("")
        A(f"{t['f4_note']}")
        A("")
        if t.get("projections"):
            A(_table(["E2 labeling workload", "hours @ measured rate", "≈ 10h overnights"],
                     [[k, v["hours"], v["overnights_at_10h"]] for k, v in t["projections"].items()]))
            A("")
            A("Single-stream, no prefix cache, no batching. EXPANSION_PLAN §2b lists both")
            A("as free levers that were not used here.")
    else:
        A("No generation happened in this process (`--score-only`), so there is no fresh")
        A("throughput measurement. Any figures quoted must come from the run that actually")
        A("generated `predictions.jsonl`.")
    A("")

    A("## 8. Excluded slices, reported separately (never headline)")
    A("")
    ex = scored.get("excluded_slice_8K_BODY")
    if ex:
        A(f"**8K_BODY, n={ex['n_rows']} — NOT EVALUABLE.** {NOT_EVALUABLE_REASONS['8K_BODY']}")
        A("")
        A(f"Shown for completeness only: sentiment exact-match "
          f"{ex['sentiment']['exact_match']:.1%} (n={ex['sentiment']['n']}), "
          f"guidance exact-match {ex['guidance_direction']['exact_match']:.1%} "
          f"(n={ex['guidance_direction']['n']}), red_flags exact-set "
          f"{ex['red_flags']['exact_set_match_category_modality']['rate']:.1%} (n={ex['red_flags']['n']}), "
          f"parse failures {ex['parse']['n_unparseable']}.")
        A("")
        A("Do not average these into anything.")
    else:
        A("No 8K_BODY rows in the scored set.")
    A("")

    A("## 9. Per-section-type breakdown (headline rows only)")
    A("")
    rows = []
    for st, r in scored["by_section_type"].items():
        rows.append([
            st, r["n_rows"],
            f"{r['parse']['parse_failure_rate']:.2%}",
            f"{r['sentiment']['exact_match']:.1%} (n={r['sentiment']['n']})" if r["sentiment"]["n"] else "n/a",
            f"{r['guidance_direction']['exact_match']:.1%} (n={r['guidance_direction']['n']})" if r["guidance_direction"]["n"] else "n/a",
            f"{r['red_flags']['exact_set_match_category_modality']['rate']:.1%}",
            f"{r['red_flags']['per_category_decisions']['agreement_rate']:.2%}",
        ])
    A(_table(["section_type", "n", "parse-fail", "sentiment exact", "guidance exact",
              "red_flags exact-set", "red_flags per-category"], rows))
    A("")
    A("The spot-check found red_flags weakest in RISK_FACTORS (59.2% teacher-vs-auditor);")
    A("compare that row specifically rather than the pooled figure.")
    A("")
    A("---")
    A("")
    A(f"Full machine-readable results: `metrics.json` · raw generations: `predictions.jsonl` · "
      f"run provenance: `manifest.json` (same directory).")
    A("")
    return "\n".join(L)


# --- generation -------------------------------------------------------------

def mlx_generate(rows: list, args, out_dir) -> tuple[dict, dict]:
    """Generate one JSON answer per eval row with the fine-tuned adapter.

    Deterministic: greedy (temperature 0 -> argmax sampler). Checkpointed:
    every row is appended to predictions.jsonl and fsync'd before the next row
    starts, so a kill at any point loses at most the in-flight row.

    Returns (records_by_chunk_id, throughput).
    """
    from mlx_lm import load as mlx_load
    from mlx_lm.generate import stream_generate
    from mlx_lm.sample_utils import make_sampler
    from transformers import AutoTokenizer

    preds_path = Path(out_dir) / "predictions.jsonl"
    if not args.resume and preds_path.exists():
        raise SystemExit(
            f"{preds_path} already exists and --no-resume was given. Appending would "
            f"duplicate rows and mix two generations in one file. Move or delete it first."
        )
    existing = load_predictions(preds_path) if args.resume else {}

    # The RENDERING tokenizer is the plain HF tokenizer, loaded from the same
    # snapshot convert_to_mlx.py used -- not mlx_lm's TokenizerWrapper, whose
    # apply_chat_template injects an `enable_thinking` kwarg. Identical code
    # path as training == identical bytes.
    render_tok = AutoTokenizer.from_pretrained(args.model, local_files_only=True)

    print(f"Loading base model + adapter (this is the only GPU work) ...", file=sys.stderr)
    t_load = time.perf_counter()
    model, tokenizer = mlx_load(args.model, adapter_path=args.adapter_path)
    print(f"  loaded in {time.perf_counter() - t_load:.1f}s", file=sys.stderr)

    sampler = make_sampler(temp=0.0)  # temp==0 -> mx.argmax, fully deterministic

    for row in rows:
        prompt_ids = render_prompt_token_ids(render_tok, row)
        row["_prompt_ids"] = prompt_ids
        row["_prompt_sha256"] = sha256_text(json.dumps(prompt_ids))
    todo = select_rows_to_generate(rows, existing, preds_path)

    n_done_before = len(rows) - len(todo)
    print(f"{len(rows)} eval rows · {n_done_before} already in {preds_path.name} · "
          f"{len(todo)} to generate", file=sys.stderr)

    records = dict(existing)
    fresh = []
    t0 = time.perf_counter()
    with open(preds_path, "a") as fh:
        for i, row in enumerate(todo, 1):
            t_row = time.perf_counter()
            text = ""
            last = None
            for resp in stream_generate(
                model, tokenizer, row["_prompt_ids"],
                max_tokens=args.max_tokens, sampler=sampler,
            ):
                text += resp.text
                last = resp
            latency = time.perf_counter() - t_row

            rec = {
                "chunk_id": row["chunk_id"],
                "raw_output": text,
                "prompt_sha256": row["_prompt_sha256"],
                "prompt_tokens": int(last.prompt_tokens) if last else len(row["_prompt_ids"]),
                "generation_tokens": int(last.generation_tokens) if last else 0,
                "prompt_tps": float(last.prompt_tps) if last else None,
                "generation_tps": float(last.generation_tps) if last else None,
                "finish_reason": last.finish_reason if last else "no_response",
                "peak_memory_gb": round(float(last.peak_memory), 3) if last else None,
                "latency_s": round(latency, 3),
                "generated_utc": datetime.now(timezone.utc).isoformat(),
            }
            append_prediction(fh, rec)
            records[row["chunk_id"]] = rec
            fresh.append(rec)

            if i % args.progress_every == 0 or i == len(todo):
                elapsed = time.perf_counter() - t0
                cph = i / elapsed * 3600.0
                eta_h = (len(todo) - i) / cph if cph else float("nan")
                print(
                    f"  [{i}/{len(todo)}] {latency:.2f}s/row · running {cph:.0f} chunks/h · "
                    f"ETA {eta_h:.2f}h · last finish={rec['finish_reason']} "
                    f"gen_tok={rec['generation_tokens']}",
                    file=sys.stderr, flush=True,
                )

    wall = time.perf_counter() - t0
    return records, throughput_summary(fresh, wall, len(fresh))


# --- orchestration ----------------------------------------------------------

def _resolve_train_manifest(path) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"training run manifest not found: {path}")
    return json.loads(path.read_text())


def _adapter_provenance(adapter_dir, expected_model: str) -> dict:
    adapter_dir = Path(adapter_dir)
    cfg_path = adapter_dir / "adapter_config.json"
    weights_path = adapter_dir / "adapters.safetensors"
    for p in (cfg_path, weights_path):
        if not p.exists():
            raise FileNotFoundError(
                f"{p} not found. If training has not finished writing this checkpoint yet, "
                f"wait for it -- do not evaluate a half-written adapter."
            )
    cfg = json.loads(cfg_path.read_text())

    # Verify-artifact rule: confirm what is actually in the file, do not trust
    # the directory name.
    problems = []
    if cfg.get("model") != expected_model:
        problems.append(f"adapter_config.model={cfg.get('model')!r} != training manifest model={expected_model!r}")
    if cfg.get("fine_tune_type") != "lora":
        problems.append(f"fine_tune_type={cfg.get('fine_tune_type')!r}, expected 'lora'")
    if cfg.get("max_seq_length") != 2048:
        problems.append(f"max_seq_length={cfg.get('max_seq_length')!r}, expected 2048")
    if problems:
        raise SystemExit(
            "Adapter does not match the training run it claims to come from:\n  - "
            + "\n  - ".join(problems)
        )

    w_sha = sha256_file(weights_path)
    checkpoints = {}
    for p in sorted(adapter_dir.glob("*_adapters.safetensors")):
        checkpoints[p.name] = sha256_file(p)
    matches = [name for name, sha in checkpoints.items() if sha == w_sha]

    # mlx_lm writes a NUMBERED checkpoint only on save_every boundaries; the
    # final "Saved final weights" write at the end of training updates
    # adapters.safetensors alone (trainer.py, end of train()). So when iters is
    # not a multiple of save_every -- 5236 % 250 != 0 here -- a completed run
    # legitimately has no numbered twin. That is expected, not a red flag; a
    # numbered match instead means the run stopped on a save boundary.
    if matches:
        match_note = matches[0]
    else:
        match_note = (
            "no numbered twin — expected for a COMPLETED run whose iters is not a "
            "multiple of save_every (mlx_lm writes the final weights to "
            "adapters.safetensors only). If training is still running, this may "
            "instead be an in-flight write: check the process has exited."
        )

    st = weights_path.stat()
    return {
        "path": str(adapter_dir),
        "adapters_sha256": w_sha,
        "adapters_bytes": st.st_size,
        "adapters_mtime_utc": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
        "adapter_config_sha256": sha256_file(cfg_path),
        "checkpoint_shas": checkpoints,
        "matches_checkpoint": match_note,
        "lora_parameters": cfg.get("lora_parameters"),
        "num_layers": cfg.get("num_layers"),
        "iters_configured": cfg.get("iters"),
        "resume_adapter_file": cfg.get("resume_adapter_file"),
    }


def run_real_eval(args) -> int:
    tman_path = Path(args.train_manifest)
    tman = _resolve_train_manifest(tman_path)

    model_path = args.model or tman["model"]["resolved_snapshot_path"]
    args.model = model_path
    adapter_path = args.adapter_path or tman["resolved_config"]["adapter_path"]
    args.adapter_path = adapter_path

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Which dataset to evaluate. Defaults are E1's (finetune/mlx_data +
    # finetune/prepared); the rubric-v1.2 re-eval passes --mlx-data-dir
    # finetune/mlx_data_v12 --prepared-dir finetune/prepared_v12.
    mlx_data_dir = Path(getattr(args, "mlx_data_dir", None) or MLX_DATA_DIR)
    prepared_dir = Path(getattr(args, "prepared_dir", None) or EVAL_JSONL.parent)
    rows, data_prov = load_eval_rows(
        mlx_valid=mlx_data_dir / "valid.jsonl",
        prepared_eval=prepared_dir / "eval.jsonl",
        verify_train_instruction=not args.skip_train_instruction_check,
        mlx_train=mlx_data_dir / "train.jsonl",
    )
    data_prov["mlx_data_dir"] = str(mlx_data_dir)
    data_prov["prepared_dir"] = str(prepared_dir)

    # verify-artifact: the eval file we just loaded must be the one the
    # training manifest recorded, or the split moved under the model.
    expected_sha = tman["data"]["files"]["valid.jsonl"]["sha256"]
    data_prov["sha_matches_train_manifest"] = data_prov["eval_rows_sha256"] == expected_sha
    if not data_prov["sha_matches_train_manifest"]:
        raise SystemExit(
            f"{data_prov['eval_rows_file']} sha256 {data_prov['eval_rows_sha256']} does not "
            f"match the training manifest's {expected_sha}. Either the held-out split changed "
            f"since training, or --mlx-data-dir points at a different dataset than the one this "
            f"adapter was trained on (the training manifest names "
            f"{tman['data']['dir']}). Refusing to report an eval against a moved target."
        )

    section_types = load_section_types(args.section_types)

    n_rows_total = len(rows)
    if args.limit:
        rows = rows[: args.limit]

    adapter_prov = _adapter_provenance(adapter_path, model_path)

    meta = {
        "run_id": out_dir.name,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "cost_usd": 0.0,
        "anthropic_api_calls": 0,
        "model": {
            "path": model_path,
            "weights_sha256": tman["model"].get("weights_sha256"),
        },
        "adapter": adapter_prov,
        "train_manifest": {"path": str(tman_path), "sha256": sha256_file(tman_path),
                           "run_id": tman.get("run_id")},
        "data": data_prov,
        "section_types_sidecar": {
            "path": str(Path(args.section_types)),
            "sha256": sha256_file(args.section_types) if Path(args.section_types).exists() else None,
        },
        "generation": {
            "backend": args.backend,
            "decoding": "greedy (temperature 0.0 -> argmax sampler)",
            "max_tokens": args.max_tokens,
            "prompt": "apply_chat_template([system=instruction, user=passage], add_generation_prompt=True)",
            "prompt_source": "convert_to_mlx.render(); the inference prompt is a token-exact "
                             "prefix of the training sequence for the same row",
        },
        "n_eval_rows": len(rows),
        "n_eval_rows_in_split": n_rows_total,
        "limit": args.limit,
    }

    if args.score_only:
        preds_path = out_dir / "predictions.jsonl"
        records = load_predictions(preds_path)
        if not records:
            raise SystemExit(f"--score-only but {preds_path} has no usable records.")
        throughput = None
        print(f"--score-only: scoring {len(records)} checkpointed predictions from {preds_path}",
              file=sys.stderr)
    else:
        try:
            import mlx_lm  # noqa: F401
        except ImportError:
            raise SystemExit(
                "mlx_lm is not importable. Run this with the project venv:\n"
                f"    {HERE / '.mlx_venv' / 'bin' / 'python'} {Path(__file__).name} --backend mlx"
            )
        records, throughput = mlx_generate(rows, args, out_dir)
        meta["throughput"] = throughput
        meta["versions"] = _versions()

    preds_by_id = {cid: r.get("raw_output") for cid, r in records.items()}
    if args.score_only:
        meta["throughput"] = _throughput_from_records(list(records.values()))
        meta["versions"] = _versions()

    scored_rows = [r for r in rows if r["chunk_id"] in preds_by_id]
    meta["n_scored"] = len(scored_rows)
    meta["partial"] = len(scored_rows) < len(rows)
    if not scored_rows:
        raise SystemExit("No predictions to score.")

    scored = score_all(scored_rows, preds_by_id, section_types)

    report = format_report(scored, meta)
    (out_dir / "eval_report.md").write_text(report + "\n")
    (out_dir / "metrics.json").write_text(json.dumps(scored, indent=2) + "\n")
    (out_dir / "manifest.json").write_text(json.dumps(meta, indent=2) + "\n")

    print(report)
    print(f"\nWrote:\n  {out_dir / 'eval_report.md'}\n  {out_dir / 'metrics.json'}\n"
          f"  {out_dir / 'manifest.json'}\n  {out_dir / 'predictions.jsonl'}", file=sys.stderr)
    if meta["partial"]:
        print(f"\nPARTIAL: {meta['n_scored']}/{len(rows)} rows scored. Re-run the same command "
              f"to resume; it skips finished rows.", file=sys.stderr)
        return 2
    return 0


def _throughput_from_records(records: list) -> dict:
    """Reconstruct throughput stats from checkpointed records (--score-only).
    Wall-clock is the SUM of per-row latencies, not a fresh measurement --
    labelled as such so it is never mistaken for one."""
    lat = [r.get("latency_s") for r in records if r.get("latency_s") is not None]
    if not lat:
        return {}
    t = throughput_summary(records, sum(lat), len(lat))
    t["reconstructed"] = True
    t["f4_note"] = (
        "Reconstructed from checkpointed per-row latencies (sum of row times), not a "
        "fresh wall-clock measurement: it excludes model load and any idle gaps between "
        "rows, so it is an upper bound on sustained throughput. "
        + t.get("f4_note", "")
    )
    return t


def _versions() -> dict:
    """Read distribution versions from installed metadata.

    Deliberately does NOT `import` the packages: importing `mlx_lm` pulls in
    `mlx.core`, and a run that only needs to re-render a report (`--score-only`)
    should not touch the GPU stack at all just to print a version string.
    """
    from importlib import metadata

    out = {}
    for dist in ("mlx", "mlx-lm", "transformers", "numpy"):
        try:
            out[dist] = metadata.version(dist)
        except Exception:
            out[dist] = "not installed"
    out["python"] = sys.version.split()[0]
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--predictions", default=None,
        help="JSONL file of {'chunk_id':..., 'raw_output':...} model predictions over the eval split.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate the eval pipeline against synthetic predictions, no model/GPU needed.",
    )

    real = parser.add_argument_group("real (non-dry-run) MLX path")
    real.add_argument(
        "--backend", choices=["mlx"], default=None,
        help="Run the real evaluation: generate with the fine-tuned adapter, then score.",
    )
    real.add_argument(
        "--train-manifest", default=str(DEFAULT_TRAIN_MANIFEST),
        help="Training run manifest; supplies the base model path, adapter path and the "
             "expected valid.jsonl hash (verify-artifact rule).",
    )
    real.add_argument("--model", default=None, help="Override the base model path from the manifest.")
    real.add_argument("--adapter-path", default=None, help="Override the adapter dir from the manifest.")
    real.add_argument(
        "--out-dir", default=str(HERE / "runs" / f"{date.today().isoformat()}-eval-epoch1"),
        help="Run directory for predictions.jsonl / eval_report.md / metrics.json / manifest.json.",
    )
    real.add_argument(
        "--max-tokens", type=int, default=520,
        help="Generation cap. Measured eval answers are 40.3 tokens mean / 129 p99 / 150 max, "
             "so 520 is ~3.5x the longest real answer: ample margin, while still capping a "
             "runaway generation instead of letting it burn the clock. (default: 520)",
    )
    real.add_argument("--limit", type=int, default=None, help="Only the first N eval rows (smoke test).")
    real.add_argument(
        "--resume", dest="resume", action="store_true", default=True,
        help="Skip rows already in predictions.jsonl (default).",
    )
    real.add_argument("--no-resume", dest="resume", action="store_false")
    real.add_argument(
        "--score-only", action="store_true",
        help="Do not load a model; score/re-render from an existing predictions.jsonl.",
    )
    real.add_argument("--progress-every", type=int, default=25, help="Progress line every N rows.")
    real.add_argument("--section-types", default=str(SECTION_TYPES_JSON))
    real.add_argument(
        "--mlx-data-dir", default=None,
        help="Directory holding the mlx-format train.jsonl / valid.jsonl to evaluate. "
             f"Default: {MLX_DATA_DIR} (E1). The rubric-v1.2 re-eval passes "
             "finetune/mlx_data_v12. The valid.jsonl found here must sha256-match the "
             "training manifest's, or the run stops before generating a token.",
    )
    real.add_argument(
        "--prepared-dir", default=None,
        help="Directory holding prepare_dataset.py's eval.jsonl, opened read-only to "
             f"cross-check gold answers and head-prefix truncation. Default: "
             f"{EVAL_JSONL.parent} (E1). The v1.2 re-eval passes finetune/prepared_v12.",
    )
    real.add_argument(
        "--splits-eval-parquet", default=str(SPLITS_EVAL_PARQUET),
        help="Source for --write-section-types. Default: E1's splits/eval.parquet "
             "(the v1.2 splits give an identical mapping; eval membership is frozen).",
    )
    real.add_argument(
        "--skip-train-instruction-check", action="store_true",
        help="Skip streaming mlx_data/train.jsonl to confirm the instruction is byte-identical "
             "to the eval one (saves ~2s; not recommended).",
    )
    real.add_argument(
        "--write-section-types", action="store_true",
        help="Regenerate the chunk_id -> section_type sidecar from --splits-eval-parquet "
             "(needs pandas: run with the SYSTEM python3, not the mlx venv), then exit.",
    )
    args = parser.parse_args()

    if args.write_section_types:
        payload = write_section_types(Path(args.section_types), Path(args.splits_eval_parquet))
        print(f"Wrote {args.section_types}: {len(payload['section_type_by_chunk_id'])} chunk_ids, "
              f"counts={payload['_counts']}")
        return

    if args.backend:
        sys.exit(run_real_eval(args))

    examples = load_eval_examples()

    if args.dry_run:
        print("(--dry-run: using SYNTHETIC predictions to validate the eval pipeline itself, "
              "not a real model. Numbers below are meaningless as a model-quality claim.)\n")
        predictions_by_id = make_synthetic_predictions(examples)
    elif args.predictions:
        predictions_by_id = {}
        with open(args.predictions) as f:
            for line in f:
                rec = json.loads(line)
                predictions_by_id[rec["chunk_id"]] = rec.get("raw_output")
    else:
        print("Must pass --dry-run or --predictions <file>.", file=sys.stderr)
        print("For the real held-out evaluation see finetune/runs/EVAL_RUNBOOK.md:", file=sys.stderr)
        print("    .mlx_venv/bin/python eval.py --backend mlx --out-dir runs/<date>-eval-epoch1",
              file=sys.stderr)
        sys.exit(1)

    results = run_eval(examples, predictions_by_id)
    print_report(results)


if __name__ == "__main__":
    main()
