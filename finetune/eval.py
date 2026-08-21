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

Usage:
    python3 eval.py --dry-run                     # synthetic predictions, no model/GPU needed
    python3 eval.py --predictions preds.jsonl      # real run: preds.jsonl = {"chunk_id":..., "raw_output": "<model's raw text>"}
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVAL_JSONL = HERE / "prepared" / "eval.jsonl"

GUIDANCE_LABELS = ["RAISED", "MAINTAINED", "LOWERED", "WITHDRAWN", "NONE"]
SENTIMENT_LABELS = ["POSITIVE", "NEUTRAL", "NEGATIVE"]
RED_FLAG_CATEGORIES = [
    "DEMAND_WEAKNESS", "SUPPLY_INPUT_CONSTRAINT", "TRADE_POLICY_EXPOSURE",
    "IMPAIRMENT_WRITEDOWN", "MARGIN_COST_PRESSURE", "LEGAL_REGULATORY_ACTION",
]


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
    args = parser.parse_args()

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
        sys.exit(1)

    results = run_eval(examples, predictions_by_id)
    print_report(results)


if __name__ == "__main__":
    main()
