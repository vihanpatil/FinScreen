"""
build_adjudicator_batches.py — rebuilds the label-adjudicator batch input
files (spotcheck/adjudicator_batches/batch_*.json) from the auditor
disagreement set + sample parquet. Deterministic: same inputs -> same
batches. The committed batch files were built by this logic on 2026-08-18;
re-run only if the inputs change (then re-run the adjudication workflow).

Each chunk carries: chunk_id, section_type, text, high_stakes flag, and
contested_fields (stored label + auditor verdict/label/reason per field).
High-stakes chunks whose distress_tier was NOT contested get an advisory
distress entry (both raters agreed; adjudicator still briefs the owner).
"""

import json
import os

import pandas as pd

BASE = "/Users/vihanpatil/personal/projects/FinScreen/spotcheck"
FIELDS = ["sentiment", "guidance_direction", "red_flags", "distress_tier"]
N_BATCHES = 12

# 9 stored REALIZED LIQUIDITY_STRESS + 2 ACCOUNTING_RESTATEMENT (HANDOFF §6
# Step 1; re-derived and asserted against the parquet in
# build_adjudication_view.py's verify_high_stakes()).
HIGH_STAKES = {
    "CHK-20d940b1855c8068", "CHK-8153748ce0e68c39", "CHK-9d1f3820572c181c",
    "CHK-a787c4ef45504dd1", "CHK-ba3a1dcd71201c66", "CHK-c17d2149a239bbcd",
    "CHK-ce2710d1b304bea6", "CHK-d9f9c2729c76438b", "CHK-ed1212d8058db87d",
    "CHK-95a7cf23f319ee70", "CHK-d74facbd628dfc96",
}


def stored_of(row, f):
    v = row[f]
    if f in ("sentiment", "guidance_direction"):
        return v if pd.notna(v) else None
    return [[d["category"], d["modality"]] for d in v] if v is not None and len(v) else []


def main():
    df = pd.read_parquet(f"{BASE}/sample_400.parquet").set_index("chunk_id", drop=False)
    adj = json.load(open(f"{BASE}/auditor_disagreements.json"))["rows"]
    assert len(adj) == 174, len(adj)

    chunks = []
    n_cases = 0
    for r in adj:
        cid = r["chunk_id"]
        row = df.loc[cid]
        contested = []
        for f in FIELDS:
            if r[f]["verdict"] in ("disagree", "unsure"):
                n_cases += 1
                contested.append({
                    "field": f,
                    "stored_label": stored_of(row, f),
                    "auditor_verdict": r[f]["verdict"],
                    "auditor_label": r[f].get("my_label"),
                    "auditor_reason": r[f].get("reason"),
                })
        assert contested, cid
        chunks.append({
            "chunk_id": cid,
            "section_type": row["section_type"],
            "high_stakes": cid in HIGH_STAKES,
            "text": row["text"],
            "contested_fields": contested,
        })

    for c in chunks:
        if c["high_stakes"] and not any(f["field"] == "distress_tier" for f in c["contested_fields"]):
            row = df.loc[c["chunk_id"]]
            c["contested_fields"].append({
                "field": "distress_tier",
                "stored_label": stored_of(row, "distress_tier"),
                "auditor_verdict": "agree",
                "auditor_label": None,
                "auditor_reason": None,
                "note": "not contested — both raters agree; adjudicate anyway as advisory input for the owner (high-stakes chunk)",
            })
            n_cases += 1

    outdir = f"{BASE}/adjudicator_batches"
    os.makedirs(outdir, exist_ok=True)
    per = (len(chunks) + N_BATCHES - 1) // N_BATCHES
    for b in range(N_BATCHES):
        part = chunks[b * per:(b + 1) * per]
        if not part:
            break
        with open(f"{outdir}/batch_{b:02d}.json", "w") as f:
            json.dump({"batch": b, "chunks": part}, f, indent=1)
        print(f"batch_{b:02d}: {len(part)} chunks, {sum(len(c['contested_fields']) for c in part)} field-cases")
    print(f"total: {len(chunks)} chunks, {n_cases} field-cases")


if __name__ == "__main__":
    main()
