"""
export_sample_json.py — turns spotcheck/sample_400.parquet into
spotcheck/sample_400.json, the JSON blob embedded in review_tool.html.

READ-ONLY on data/*. Writes only within spotcheck/.

Run this after build_sample.py (or after any change to sample_400.parquet)
and then re-run build_review_tool.py to regenerate review_tool.html with
the updated blob embedded.
"""

import json
import numpy as np
import pandas as pd

IN_PATH = "/Users/vihanpatil/personal/projects/FinScreen/spotcheck/sample_400.parquet"
OUT_PATH = "/Users/vihanpatil/personal/projects/FinScreen/spotcheck/sample_400.json"

# Applicability matrix from labeling_rubric.md §1 — which label categories
# are asked (and therefore reviewable) per section_type. Kept in sync by
# hand with the rubric, same as build_batch_requests.py's SYSTEM_PROMPT.
APPLICABILITY = {
    "MDA": {"sentiment": True, "guidance_direction": False, "red_flags": True, "distress_tier": True},
    "RISK_FACTORS": {"sentiment": False, "guidance_direction": False, "red_flags": True, "distress_tier": True},
    "EX99_PRESS_RELEASE": {"sentiment": True, "guidance_direction": True, "red_flags": True, "distress_tier": True},
    "8K_BODY": {"sentiment": True, "guidance_direction": True, "red_flags": True, "distress_tier": True},
}


def entries_to_list(x):
    if isinstance(x, np.ndarray) and len(x) > 0:
        return [{"category": e["category"], "modality": e["modality"]} for e in x]
    return []


def main():
    df = pd.read_parquet(IN_PATH)
    records = []
    for _, row in df.iterrows():
        section_type = row["section_type"]
        applicability = APPLICABILITY.get(
            section_type,
            {"sentiment": True, "guidance_direction": True, "red_flags": True, "distress_tier": True},
        )
        labeling_failed = bool(not row["parse_ok"])
        rec = {
            "chunk_id": row["chunk_id"],
            "section_type": section_type,
            "text": row["text"],
            "word_count": int(row["word_count"]),
            "home_ticker": row["home_ticker"],
            "home_form": row["home_form"],
            "home_filing_date": str(row["home_filing_date"]),
            "primary_tier": row["primary_tier"],
            "tiers": row["tiers"],
            "subtier": row["subtier"],
            "applicability": applicability,
            "labeling_failed": labeling_failed,
            "parse_ok": bool(row["parse_ok"]),
            "parse_error": row["parse_error"] if pd.notna(row["parse_error"]) else None,
            "labels": {
                "sentiment": row["sentiment"] if pd.notna(row["sentiment"]) else None,
                "guidance_direction": row["guidance_direction"] if pd.notna(row["guidance_direction"]) else None,
                "red_flags": entries_to_list(row["red_flags"]),
                "distress_tier": entries_to_list(row["distress_tier"]),
            },
        }
        records.append(rec)

    with open(OUT_PATH, "w") as f:
        json.dump(records, f, indent=1, sort_keys=False)

    print(f"Wrote {len(records)} records to {OUT_PATH}")


if __name__ == "__main__":
    main()
