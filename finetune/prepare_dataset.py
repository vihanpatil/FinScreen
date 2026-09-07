"""
prepare_dataset.py — Week 4 instruction-tuning dataset builder.

Converts `finetune/splits/{train,eval}.parquet` (produced by `split.py`)
into instruction-tuning JSONL records per `PROMPT_TEMPLATE.md`. Read this
file's docstring alongside `PROMPT_TEMPLATE.md` — that doc is authoritative
on *why* the template is shaped this way; this module is the concrete
implementation.

Key rules (see PROMPT_TEMPLATE.md for full rationale):
  - `instruction` is byte-identical across every example.
  - `input` is the chunk's raw passage text, and nothing else — no ticker,
    company name, CIK, filing date, or section_type string anywhere.
  - `output` target fields are conditional on section_type per the
    applicability matrix (APPLICABILITY below), matching
    `labeling_rubric.md` §1 exactly, MINUS distress_tier which is globally
    excluded from training targets per DISCOVERY.md §3.
  - Deterministic key order and deterministic red_flags entry order.

Run: `python3 prepare_dataset.py` (writes finetune/prepared/{train,eval}.jsonl)

For the rubric-v1.2 retrain, point it at the v1.2 splits and a new output dir
so E1's prepared data is never overwritten:

    python3 prepare_dataset.py --splits-dir finetune/splits_v12 \
                               --out-dir    finetune/prepared_v12

`INSTRUCTION` is deliberately NOT parameterised. It is the *training*
instruction and it is frozen across E1 and the v1.2 retrain, so that the two
students differ on exactly one axis: the label values. It is a leaner
restatement of the labeling prompt, not the labeling prompt itself — see
`PROMPT_TEMPLATE.md` and HANDOFF §3's 2026-08-10 sync-rule entry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
SPLITS_DIR = HERE / "splits"
OUTPUT_DIR = HERE / "prepared"

# Single source of truth for which target fields apply to which section_type.
# Mirrors labeling_rubric.md §1 exactly, EXCLUDING distress_tier (excluded
# from training targets entirely, see PROMPT_TEMPLATE.md).
APPLICABILITY = {
    "MDA": {"sentiment": True, "guidance_direction": False, "red_flags": True},
    "RISK_FACTORS": {"sentiment": False, "guidance_direction": False, "red_flags": True},
    "EX99_PRESS_RELEASE": {"sentiment": True, "guidance_direction": True, "red_flags": True},
    "8K_BODY": {"sentiment": True, "guidance_direction": True, "red_flags": True},
}

INSTRUCTION = (
    "You are extracting structured signals from a short passage of text taken "
    "from a public SEC filing (10-K/10-Q Management's Discussion & Analysis, "
    "Item 1A Risk Factors, or an 8-K earnings press release / body). You are "
    "not told which company, ticker, or date this passage is from, and must "
    "not guess. Judge only what the passage's own text asserts about the "
    "business's results, performance, condition, and forward guidance -- "
    "never what happened to any company's stock price or business afterward.\n\n"
    "Respond with a single JSON object. Only include the fields that "
    "genuinely apply to this passage's content and section register -- omit "
    "a field entirely rather than guessing or defaulting it if it doesn't "
    "apply:\n\n"
    '- "sentiment": one of "POSITIVE", "NEUTRAL", "NEGATIVE" -- the '
    "passage's predominant tone about the business's own results/condition, "
    "as characterized by the text itself. Omit for passages that are purely "
    "a statutory risk-factor enumeration (negative-by-construction register, "
    "not a real signal).\n"
    '- "guidance_direction": one of "RAISED", "MAINTAINED", "LOWERED", '
    '"WITHDRAWN", "NONE" -- only include this field for passages that are '
    "(or could be) issuing/revising specific quantified forward financial "
    "guidance, such as earnings press releases or 8-K bodies. Omit for "
    "narrative MD&A or risk-factor text, which never issues guidance.\n"
    '- "red_flags": a list of {"category": ..., "modality": ...} objects, '
    "zero or more, from categories DEMAND_WEAKNESS, SUPPLY_INPUT_CONSTRAINT, "
    "TRADE_POLICY_EXPOSURE, IMPAIRMENT_WRITEDOWN, MARGIN_COST_PRESSURE, "
    "LEGAL_REGULATORY_ACTION, each with modality HYPOTHETICAL (framed as "
    "something that may occur) or REALIZED (stated as having already "
    "occurred or currently occurring). Always include this field, with an "
    "empty list if nothing matches.\n\n"
    "Output only the JSON object, no other text."
)

KEY_ORDER = ["sentiment", "guidance_direction", "red_flags"]


def build_target(row) -> dict:
    """Build the conditional, deterministically-ordered target dict for one
    labels.parquet row. distress_tier is never read."""
    applic = APPLICABILITY[row["section_type"]]
    target = {}

    if applic["sentiment"]:
        assert row["sentiment"] is not None, (
            f"chunk {row['chunk_id']}: section_type={row['section_type']} is sentiment-applicable "
            f"per the matrix but sentiment is null in the source label row"
        )
        target["sentiment"] = row["sentiment"]

    if applic["guidance_direction"]:
        assert row["guidance_direction"] is not None, (
            f"chunk {row['chunk_id']}: section_type={row['section_type']} is guidance-applicable "
            f"per the matrix but guidance_direction is null in the source label row"
        )
        target["guidance_direction"] = row["guidance_direction"]

    if applic["red_flags"]:
        flags = row["red_flags"] if row["red_flags"] is not None else []
        flags_sorted = sorted(
            ({"category": f["category"], "modality": f["modality"]} for f in flags),
            key=lambda f: (f["category"], f["modality"]),
        )
        target["red_flags"] = flags_sorted

    # Re-order to the fixed KEY_ORDER (only keys actually present survive).
    ordered = {k: target[k] for k in KEY_ORDER if k in target}
    return ordered


def build_example(row) -> dict:
    return {
        "chunk_id": row["chunk_id"],
        "instruction": INSTRUCTION,
        "input": row["text"],
        "output": json.dumps(build_target(row), sort_keys=False, ensure_ascii=False),
    }


def prepare_split(df: pd.DataFrame) -> list[dict]:
    return [build_example(row) for _, row in df.iterrows()]


def run(splits_dir: Path = SPLITS_DIR, output_dir: Path = OUTPUT_DIR):
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"instruction sha256: {hashlib.sha256(INSTRUCTION.encode()).hexdigest()} "
          f"({len(INSTRUCTION)} chars) — frozen across E1 and the v1.2 retrain")
    for side in ("train", "eval"):
        src = splits_dir / f"{side}.parquet"
        if not src.exists():
            raise FileNotFoundError(
                f"{src} not found — run split.py (E1) or build_splits_v12.py (v1.2) first"
            )
        df = pd.read_parquet(src)
        examples = prepare_split(df)

        out_path = output_dir / f"{side}.jsonl"
        with open(out_path, "w") as f:
            for ex in examples:
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")
        print(f"Wrote {len(examples)} examples to {out_path}")

        # Quick field-presence sanity summary.
        field_counts = {"sentiment": 0, "guidance_direction": 0, "red_flags": 0}
        for ex in examples:
            target = json.loads(ex["output"])
            for k in field_counts:
                if k in target:
                    field_counts[k] += 1
        print(f"  field presence: {field_counts}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--splits-dir", default=str(SPLITS_DIR))
    ap.add_argument("--out-dir", default=str(OUTPUT_DIR))
    args = ap.parse_args()
    run(Path(args.splits_dir), Path(args.out_dir))


if __name__ == "__main__":
    main()
