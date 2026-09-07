"""
build_adjudicator_batches_v12.py — turn contested rows into label-adjudicator
batches. Mechanical: no judgement here.

Reads   draw_v12.csv, verdicts/rater_a.json, data/labels_v12.parquet
Writes  adjudicator_batches/adj_batch_0N.json (<= 40 contested chunks each)
        adjudicator_batches/contested_ids.json

A chunk is contested iff the blind rater's (category, modality) SET differs
from the stored v1.2 set. That comparison is made here, in code — the rater
never saw the stored label and never self-reported agreement
(SPOTCHECK_v12_design.md §5.1).

high_stakes is false throughout: this pass has no distress arm, which is what
that flag existed for in 2026-08-18.

Zero network, zero API.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/vihanpatil/personal/projects/FinScreen")
DIR = ROOT / "data" / "hardening" / "spotcheck_v12"
OUT = DIR / "adjudicator_batches"
BATCH_SIZE = 40


def as_pairs(v):
    if isinstance(v, np.ndarray):
        return sorted((e["category"], e["modality"]) for e in v)
    return sorted((c, m) for c, m in v)


def main():
    draw = pd.read_csv(DIR / "draw_v12.csv")
    lab = pd.read_parquet(ROOT / "data" / "labels_v12.parquet",
                          columns=["chunk_id", "section_type", "text", "red_flags"])
    lab = lab.set_index("chunk_id")
    rater = {r["chunk_id"]: r for r in json.loads((DIR / "verdicts" / "rater_a.json").read_text())}

    missing = [c for c in draw.chunk_id if c not in rater]
    assert not missing, f"rater A is missing {len(missing)} chunks: {missing[:5]}"

    contested = []
    for c in draw.chunk_id:
        stored = as_pairs(lab.loc[c, "red_flags"])
        mine = as_pairs(rater[c]["red_flags"])
        if stored != mine:
            contested.append({
                "chunk_id": c,
                "section_type": lab.loc[c, "section_type"],
                "text": lab.loc[c, "text"],
                "high_stakes": False,
                "contested_fields": [{
                    "field": "red_flags",
                    "stored_label": [list(p) for p in stored],
                    "auditor_verdict": "disagree",
                    "auditor_label": [list(p) for p in mine],
                    "auditor_reason": rater[c].get("reason", ""),
                }],
            })

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "contested_ids.json").write_text(
        json.dumps([r["chunk_id"] for r in contested], indent=1))

    for i in range(0, len(contested), BATCH_SIZE):
        b = i // BATCH_SIZE + 1
        payload = {
            "batch": b,
            "protocol": "spotcheck-v12-adjudication (red_flags only)",
            "rubric": "labeling_rubric.md (v1.2)",
            "n": len(contested[i:i + BATCH_SIZE]),
            "chunks": contested[i:i + BATCH_SIZE],
        }
        (OUT / f"adj_batch_{b:02d}.json").write_text(
            json.dumps(payload, indent=1, ensure_ascii=False))

    n_b = (len(contested) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"contested {len(contested)}/{len(draw)} = {len(contested)/len(draw):.1%}"
          f"  ->  {n_b} adjudicator batch(es) in {OUT}")
    print("NOTE: the contested RATE is not the error rate — it becomes the error "
          "rate only after adjudication. In v1.1 the two nearly coincided "
          "(148 contested -> 146 stored-wrong), which is itself a finding, not "
          "a licence to skip adjudication.")


if __name__ == "__main__":
    main()
