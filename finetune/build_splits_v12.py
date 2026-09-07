#!/usr/bin/env python3
"""
build_splits_v12.py — rebuild the train/eval splits for the rubric-v1.2
re-label WITHOUT re-deriving split membership.

WHY THIS EXISTS (read before touching it)
-----------------------------------------
`split.py` derives membership from `data/labels.parquet` — E1's FROZEN labels
— by building a paragraph/accession connected-component graph and drawing a
stratified sample from it. Running it again would produce a *different*
membership, because the stratification reads label values, and label values
are exactly what rubric v1.2 changed. The train/eval boundary must not move:
epoch-1 and epoch-2 were trained and evaluated against it, and the whole point
of the v1.2 retrain is a single-axis comparison (labels changed, nothing else).

So this script does the only safe thing: it JOINS `data/labels_v12.parquet`
onto the frozen `finetune/splits/manifest.parquet`. Membership comes from the
manifest and only from the manifest. `split.py` is never invoked, and neither
`data/labels.parquet` nor `finetune/splits/*` is ever written.

WHAT IT MAINTAINS FROM E1
-------------------------
1. **The refusal-chunk exclusion.** `CHK-8e69547e0900a8dd` is absent from the
   frozen manifest (E1 dropped it under the `parse_ok & schema_valid`
   predicate). Under v1.2 that chunk *did* label successfully — but the split
   is frozen, so it stays out of both sides. The script asserts this
   explicitly and prints it, rather than letting it slip in silently.
2. **The same drop predicate**, `parse_ok & schema_valid`, applied to the v1.2
   labels. Any manifest row whose v1.2 label failed is dropped from the
   prepared data with a LOUD count and the chunk_id named. It is NOT removed
   from the manifest — the manifest copy written here keeps all 6,746 rows
   with a `v12_labeled` boolean, so the gap is visible forever.
3. **The corpus is the same corpus.** Passage text is asserted byte-identical
   to E1's for every joined row.

EXPECTED RESULT (2026-08-26, after the completion batch): 6,746 manifest rows
→ **0 v1.2 label gaps** → train 5,736 / eval 1,010, i.e. the frozen split
exactly.

History worth keeping: the main v1.2 batch left one TRAIN row unanswered
(`CHK-1c1812ed45219a3a`, an OXY MD&A chunk whose request errored when the
account's prepaid credits ran out), and this script was written to drop it
with a loud count. The owner then funded a 1-request completion batch
(`msgbatch_01RvQpZofwP2yrHNnuJVmFZu`, $0.0014) and the gap closed. The
gap-handling path stays — it is the guard, not a workaround, and it must keep
working if a future label set is ever incomplete.

Run:
    python3 finetune/build_splits_v12.py
    python3 finetune/build_splits_v12.py --out-dir <dir> --labels <parquet>
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

FROZEN_MANIFEST = HERE / "splits" / "manifest.parquet"
V12_LABELS = REPO / "data" / "labels_v12.parquet"
E1_LABELS = REPO / "data" / "labels.parquet"
DEFAULT_OUT_DIR = HERE / "splits_v12"

# E1's refusal chunk. Excluded from the frozen manifest by predicate; it must
# stay excluded even though it carries a v1.2 label.
E1_REFUSAL_CHUNK = "CHK-8e69547e0900a8dd"

# The frozen split's contractual sizes. Membership never changes.
FROZEN_SPLIT_SIZES = {"train": 5736, "eval": 1010}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def build(
    labels_path: Path,
    manifest_path: Path,
    out_dir: Path,
    e1_labels_path: Path | None = None,
) -> dict:
    """Join v1.2 labels onto the frozen manifest. Returns a report dict."""
    manifest = pd.read_parquet(manifest_path)
    labels = pd.read_parquet(labels_path)

    # --- the frozen manifest must be the frozen manifest ---
    sizes = manifest["split"].value_counts().to_dict()
    if sizes != FROZEN_SPLIT_SIZES:
        raise ValueError(
            f"{manifest_path} is not the frozen split: got {sizes}, "
            f"expected {FROZEN_SPLIT_SIZES}. Membership is frozen — refusing."
        )
    if manifest["chunk_id"].duplicated().any():
        raise ValueError("frozen manifest has duplicate chunk_ids")
    if E1_REFUSAL_CHUNK in set(manifest["chunk_id"]):
        raise ValueError(
            f"{E1_REFUSAL_CHUNK} is in the frozen manifest — it must not be. "
            f"The manifest on disk is not E1's."
        )

    # --- every manifest chunk must have a v1.2 ROW (labeled or not) ---
    missing = set(manifest["chunk_id"]) - set(labels["chunk_id"])
    if missing:
        raise ValueError(
            f"{len(missing)} manifest chunk_ids are absent from {labels_path}: "
            f"{sorted(missing)[:5]} — the re-label did not cover the split."
        )

    # Rename EVERY manifest column explicitly rather than relying on pandas'
    # suffix-on-collision, which only fires for columns that happen to collide.
    man = manifest.rename(columns={c: f"man_{c}" for c in manifest.columns if c != "chunk_id"})
    joined = man.merge(labels, on="chunk_id", how="left", validate="1:1")
    if not (joined["man_section_type"] == joined["section_type"]).all():
        raise ValueError("section_type disagrees between the frozen manifest and the v1.2 labels")

    # --- the corpus is the same corpus ---
    text_verified = False
    if e1_labels_path is not None and Path(e1_labels_path).exists():
        e1 = pd.read_parquet(e1_labels_path, columns=["chunk_id", "text"]).set_index("chunk_id")["text"]
        v12 = labels.set_index("chunk_id")["text"]
        shared = e1.index.intersection(v12.index)
        if not (e1.loc[shared] == v12.loc[shared]).all():
            raise ValueError(
                "passage text differs between labels.parquet and labels_v12.parquet — "
                "the re-label did not run on the frozen corpus."
            )
        text_verified = True

    # --- E1's drop predicate, applied to v1.2 ---
    labeled = (joined["parse_ok"] & joined["schema_valid"]).fillna(False).astype(bool)
    joined["v12_labeled"] = labeled
    gaps = joined.loc[~labeled]

    # The side parquets carry the v1.2 label columns only — same schema shape
    # as E1's splits/{train,eval}.parquet, which are label rows and nothing else.
    label_cols = [c for c in labels.columns]

    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}
    for side in ("train", "eval"):
        df = joined.loc[labeled & (joined["man_split"] == side), label_cols]
        df = df.reset_index(drop=True)
        path = out_dir / f"{side}.parquet"
        df.to_parquet(path, index=False)
        written[side] = {"path": str(path), "rows": len(df), "sha256": sha256_file(path)}

    man_cols = [c for c in joined.columns if c.startswith("man_")]
    man_out = joined[["chunk_id"] + man_cols + ["v12_labeled"]].rename(
        columns={c: c[len("man_"):] for c in man_cols}
    )
    man_path = out_dir / "manifest.parquet"
    man_out.to_parquet(man_path, index=False)

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "rubric-v1.2 retrain splits, built by JOIN onto the frozen manifest — "
                   "split.py was NOT run and membership was NOT re-derived",
        "inputs": {
            "frozen_manifest": {"path": str(manifest_path), "sha256": sha256_file(manifest_path), "rows": len(manifest)},
            "v12_labels": {"path": str(labels_path), "sha256": sha256_file(labels_path), "rows": len(labels)},
            "e1_labels_text_identity_verified": text_verified,
        },
        "frozen_membership": FROZEN_SPLIT_SIZES,
        "e1_refusal_chunk": {
            "chunk_id": E1_REFUSAL_CHUNK,
            "in_frozen_manifest": False,
            "labels_under_v12": bool(
                labels.loc[labels.chunk_id == E1_REFUSAL_CHUNK, "parse_ok"].fillna(False).all()
            )
            if (labels.chunk_id == E1_REFUSAL_CHUNK).any()
            else None,
            "kept_out_of_both_splits": True,
            "reason": "the split is frozen; membership is label-value-independent",
        },
        "v12_label_gaps": {
            "n": int(len(gaps)),
            "rows": [
                {
                    "chunk_id": r["chunk_id"],
                    "split": r["man_split"],
                    "section_type": r["man_section_type"],
                    "home_ticker": r["man_home_ticker"],
                    "home_filing_date": str(r["man_home_filing_date"]),
                    "parse_error": r["parse_error"],
                    "api_result_type": r["api_result_type"],
                }
                for _, r in gaps.iterrows()
            ],
        },
        "outputs": {
            **written,
            "manifest": {"path": str(man_path), "rows": len(man_out), "sha256": sha256_file(man_path)},
        },
        "deltas_vs_frozen": {
            side: written[side]["rows"] - FROZEN_SPLIT_SIZES[side] for side in ("train", "eval")
        },
    }
    (out_dir / "build_report.json").write_text(json.dumps(report, indent=2))
    return report


def print_report(report: dict) -> None:
    print("=" * 78)
    print("v1.2 SPLITS — built by JOIN onto the FROZEN manifest (split.py NOT run)")
    print("=" * 78)
    inp = report["inputs"]
    print(f"frozen manifest : {inp['frozen_manifest']['rows']} rows  sha256 {inp['frozen_manifest']['sha256'][:16]}...")
    print(f"v1.2 labels     : {inp['v12_labels']['rows']} rows  sha256 {inp['v12_labels']['sha256'][:16]}...")
    print(f"corpus text byte-identical to E1: {inp['e1_labels_text_identity_verified']}")
    ref = report["e1_refusal_chunk"]
    print()
    print(f"E1 refusal chunk {ref['chunk_id']}:")
    print(f"  labels under v1.2 : {ref['labels_under_v12']}")
    print(f"  KEPT OUT of both splits anyway — {ref['reason']}")
    print()
    gaps = report["v12_label_gaps"]
    if gaps["n"] == 0:
        print("v1.2 label gaps: NONE — every one of the 6,746 frozen manifest rows "
              "carries a usable v1.2 label.")
    else:
        banner = "!" * 78
        print(banner)
        print(f"v1.2 LABEL GAPS: {gaps['n']} manifest row(s) have NO usable v1.2 label and are DROPPED")
        for r in gaps["rows"]:
            print(f"  DROPPED  {r['chunk_id']}  split={r['split']}  {r['section_type']}  "
                  f"{r['home_ticker']} {r['home_filing_date']}")
            print(f"           reason: {r['parse_error']}  (api_result_type={r['api_result_type']})")
        print(banner)
    print()
    for side in ("train", "eval"):
        o = report["outputs"][side]
        d = report["deltas_vs_frozen"][side]
        print(f"{side:6s} {o['rows']:>6d} rows  (frozen {FROZEN_SPLIT_SIZES[side]}, delta {d:+d})  "
              f"sha256 {o['sha256'][:16]}...")
    o = report["outputs"]["manifest"]
    print(f"manifest {o['rows']:>4d} rows  sha256 {o['sha256'][:16]}...  (all frozen rows, `v12_labeled` flags the gap)")
    print("=" * 78)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", default=str(V12_LABELS))
    ap.add_argument("--manifest", default=str(FROZEN_MANIFEST))
    ap.add_argument("--e1-labels", default=str(E1_LABELS))
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = ap.parse_args()

    report = build(Path(args.labels), Path(args.manifest), Path(args.out_dir), Path(args.e1_labels))
    print_report(report)


if __name__ == "__main__":
    main()
