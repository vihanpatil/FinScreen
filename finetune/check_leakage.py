"""
check_leakage.py — automated leakage check for the finetune/splits/ output.

Asserts, against the produced split:
  1. No paragraph_id appears in chunks on both sides of the split.
  2. No source accession_number appears in chunks on both sides of the split.
  3. No chunk_id appears in both splits.parquet outputs (train.parquet /
     eval.parquet) simultaneously, and every chunk_id in the manifest is
     assigned to exactly one of {train, eval}.
  4. Every row failing (parse_ok & schema_valid) is excluded from BOTH
     train and eval targets — currently exactly 1 row (CHK-8e69547e0900a8dd),
     re-derived from data/labels.parquet directly rather than hardcoded, so
     this check still means something if the labeled corpus is ever re-run.

Exit code: 0 if every check passes, 1 (with a printed reason) otherwise.
Intended to be run after split.py and re-run any time splits/ changes.

Run: `python3 check_leakage.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
LABELS_PATH = REPO_ROOT / "data" / "labels.parquet"
SPLITS_DIR = HERE / "splits"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")


def main() -> int:
    ok = True

    manifest_path = SPLITS_DIR / "manifest.parquet"
    train_path = SPLITS_DIR / "train.parquet"
    eval_path = SPLITS_DIR / "eval.parquet"
    for p in (manifest_path, train_path, eval_path):
        if not p.exists():
            fail(f"missing expected split output: {p}. Run split.py first.")
            return 1

    manifest = pd.read_parquet(manifest_path)
    train_df = pd.read_parquet(train_path)
    eval_df = pd.read_parquet(eval_path)
    labels = pd.read_parquet(LABELS_PATH)

    # --- Check 3a: chunk_id not in both train.parquet and eval.parquet ---
    train_ids = set(train_df["chunk_id"])
    eval_ids = set(eval_df["chunk_id"])
    overlap = train_ids & eval_ids
    if overlap:
        fail(f"{len(overlap)} chunk_id(s) present in BOTH train.parquet and eval.parquet: "
             f"{sorted(overlap)[:10]}{'...' if len(overlap) > 10 else ''}")
        ok = False
    else:
        print(f"PASS: no chunk_id overlap between train.parquet ({len(train_ids)}) "
              f"and eval.parquet ({len(eval_ids)})")

    # --- Check 3b: manifest assigns every chunk_id to exactly one side ---
    manifest_dupes = manifest["chunk_id"][manifest["chunk_id"].duplicated()]
    if len(manifest_dupes):
        fail(f"{len(manifest_dupes)} duplicate chunk_id(s) in manifest.parquet")
        ok = False
    bad_splits = set(manifest["split"]) - {"train", "eval"}
    if bad_splits:
        fail(f"manifest.parquet has unexpected split values: {bad_splits}")
        ok = False
    if not manifest_dupes.any() and not bad_splits:
        print(f"PASS: manifest.parquet assigns {len(manifest)} chunk_ids uniquely to train/eval")

    # --- Check 4: excluded (parse_ok & schema_valid == False) rows are in neither ---
    clean_predicate = labels["parse_ok"] & labels["schema_valid"]
    excluded_ids = set(labels.loc[~clean_predicate, "chunk_id"])
    if len(excluded_ids) != 1:
        fail(f"expected exactly 1 row failing (parse_ok & schema_valid) in data/labels.parquet, "
             f"found {len(excluded_ids)}: {sorted(excluded_ids)}. The labeled corpus may have "
             f"changed since split.py was last run — re-run split.py before trusting this split.")
        ok = False
    leaked_excluded = excluded_ids & (train_ids | eval_ids)
    if leaked_excluded:
        fail(f"excluded chunk_id(s) present in train or eval targets: {sorted(leaked_excluded)}")
        ok = False
    else:
        print(f"PASS: excluded chunk_id(s) {sorted(excluded_ids)} are in neither train nor eval")

    # --- Checks 1 & 2: build paragraph_id / accession_number -> split-sides map ---
    id_to_split = dict(zip(manifest["chunk_id"], manifest["split"]))

    para_sides: dict[str, set[str]] = {}
    acc_sides: dict[str, set[str]] = {}
    all_chunks = pd.concat([train_df, eval_df], ignore_index=True)
    for row in all_chunks.itertuples(index=False):
        side = id_to_split.get(row.chunk_id)
        if side is None:
            continue
        for pid in row.paragraph_ids:
            para_sides.setdefault(pid, set()).add(side)
        for acc in row.source_accession_numbers:
            acc_sides.setdefault(acc, set()).add(side)

    straddling_paras = {pid: sides for pid, sides in para_sides.items() if len(sides) > 1}
    if straddling_paras:
        fail(f"{len(straddling_paras)} paragraph_id(s) appear on both sides of the split: "
             f"{list(straddling_paras)[:10]}{'...' if len(straddling_paras) > 10 else ''}")
        ok = False
    else:
        print(f"PASS: no paragraph_id straddles train/eval ({len(para_sides)} distinct paragraph_ids checked)")

    straddling_accs = {acc: sides for acc, sides in acc_sides.items() if len(sides) > 1}
    if straddling_accs:
        fail(f"{len(straddling_accs)} source accession_number(s) appear on both sides of the split: "
             f"{list(straddling_accs)[:10]}{'...' if len(straddling_accs) > 10 else ''}")
        ok = False
    else:
        print(f"PASS: no source accession_number straddles train/eval ({len(acc_sides)} distinct accessions checked)")

    print()
    if ok:
        print("ALL LEAKAGE CHECKS PASSED")
        return 0
    else:
        print("LEAKAGE CHECKS FAILED — see FAIL lines above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
