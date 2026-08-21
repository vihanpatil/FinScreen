"""
make_review_template_csv.py — generates spotcheck/sample_400_review_template.csv,
a spreadsheet-editable fallback to review_tool.html with the SAME columns
as the HTML tool's CSV export, one row per (chunk_id, applicable field),
judgment/notes columns left blank.

The owner can fill in `judgment` (agree/disagree/unsure), `field_note`,
and `example_note` in a spreadsheet and hand the saved CSV straight to
compute_agreement.py --format csv.

Run after export_sample_json.py (reads sample_400.json).
"""

import csv
import json

FIELD_NAMES = ["sentiment", "guidance_direction", "red_flags", "distress_tier"]
IN_PATH = "/Users/vihanpatil/personal/projects/FinScreen/spotcheck/sample_400.json"
OUT_PATH = "/Users/vihanpatil/personal/projects/FinScreen/spotcheck/sample_400_review_template.csv"


def main():
    with open(IN_PATH) as f:
        sample = json.load(f)

    rows = [["chunk_id", "section_type", "primary_tier", "field", "judgment", "field_note", "example_note"]]
    for ex in sample:
        for field in FIELD_NAMES:
            if ex["applicability"][field]:
                rows.append([ex["chunk_id"], ex["section_type"], ex["primary_tier"], field, "", "", ""])

    with open(OUT_PATH, "w", newline="") as f:
        csv.writer(f).writerows(rows)

    print(f"Wrote {len(rows) - 1} blank judgment rows for {len(sample)} examples to {OUT_PATH}")


if __name__ == "__main__":
    main()
