"""H3v2 section 3, part 1b -- the matched-composition control for the v1.2
eval-only slice.

THIN WRAPPER over `data/hardening/h3_composition_control.py`: its `text_table()`
(the TEXT half of `features.build_feature_table()`, verbatim machinery) and
`h3_features.retention_table` are imported and reused. Only the labels are
swapped to the v1.2 pair. Neither module is edited.

The procedure is H3 §3.2's, unchanged:

  The v1.2 eval-only retention numbers are unbiased with respect to
  memorization but are computed over a much THINNER chunk composition (1,010
  chunks over 630 filings instead of 6,746), so every filing-level rate is a
  mean over 1-3 chunks on BOTH sides. That inflates per-filing sampling noise
  symmetrically and mechanically drags the correlation down, in the OPPOSITE
  direction from pooled's memorization inflation.

  Control: draw from the student's own TRAIN chunks a sample matched to the
  eval split's per-section_type counts, 5 seeds. That sample is thin exactly
  like eval AND memorized exactly like the pooled corpus's bulk, so:

    pooled (thick, memorized) -> matched-train (thin, memorized)
        = the thin-composition deflation alone
    matched-train (thin, memorized) -> eval (thin, unmemorized)
        = the memorization inflation alone

8K_BODY (n=8) is entirely in the eval split, so the matched control is short by
those 8 chunks (1,002 vs 1,010). 8K_BODY is non-evaluable anyway (H3v2 §1.8
caveat 4).

Run: python3 data/hardening/h3v2/h3v2_composition_control.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "data" / "hardening"))

import features as F  # noqa: E402
from h3_composition_control import text_table  # noqa: E402  -- imported, never edited
from h3_features import KEY, TEXT_FEATURES, retention_table  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "hardening" / "h3v2"
STUDENT_LABELS_V12 = OUT_DIR / "e1_relabel_student_v12.parquet"
TEACHER_LABELS_V12 = REPO_ROOT / "data" / "labels_v12.parquet"
N_SEEDS = 5
STAMP = "2026-08-27_H3v2"


def main() -> None:
    student = pd.read_parquet(STUDENT_LABELS_V12)
    student = student[student["parse_ok"]].copy()
    student_ids = set(student["chunk_id"])

    teacher = pd.read_parquet(TEACHER_LABELS_V12)
    teacher = teacher[teacher["parse_ok"] & teacher["chunk_id"].isin(student_ids)].copy()
    assert set(teacher["chunk_id"]) == student_ids

    # --- verification: the fast text path reproduces the full v1.2 build exactly
    for who, labels, path in (
        ("student", student, OUT_DIR / f"features_student_v12_{STAMP}.parquet"),
        ("teacher", teacher, OUT_DIR / f"features_teacher_v12_{STAMP}.parquet"),
    ):
        full = pd.read_parquet(path).set_index(KEY).sort_index()
        fast = text_table(labels)
        assert fast.index.equals(full.index)
        assert np.allclose(
            fast[TEXT_FEATURES].values.astype(float),
            full[TEXT_FEATURES].values.astype(float),
            equal_nan=True,
        ), f"fast text path does not reproduce build_feature_table()'s text columns ({who})"
        print(f"fast text path verified against {path.name}")

    eval_counts = student[student["split"] == "eval"].groupby("section_type").size().to_dict()
    train_pool = student[student["split"] == "train"]
    print("eval per-section counts:", eval_counts)

    results = []
    for seed in range(N_SEEDS):
        rng = np.random.default_rng(seed)
        picked, shortfall = [], {}
        for sec, n_want in eval_counts.items():
            avail = train_pool.loc[train_pool["section_type"] == sec, "chunk_id"].values
            n_take = min(n_want, len(avail))
            if n_take < n_want:
                shortfall[sec] = n_want - n_take
            if n_take:
                picked.extend(rng.choice(avail, size=n_take, replace=False).tolist())
        ids = set(picked)
        s_tbl = text_table(student[student["chunk_id"].isin(ids)])
        t_tbl = text_table(teacher[teacher["chunk_id"].isin(ids)])
        tab = retention_table(t_tbl, s_tbl)
        results.append({"seed": seed, "n_chunks": len(ids), "shortfall": shortfall, "table": tab})
        print(f"seed {seed}: n={len(ids)} shortfall={shortfall}")

    redflag_12 = [c for c in F.RED_FLAG_FEATURE_NAMES if c != "redflag_any_rate_press"]
    summary_rows = []
    for feat in TEXT_FEATURES + ["__redflag_12_mean__"]:
        pear, spear, nboth = [], [], []
        for r in results:
            idx = r["table"].set_index("feature")
            if feat == "__redflag_12_mean__":
                pear.append(float(idx.loc[redflag_12, "pearson"].mean()))
                spear.append(float(idx.loc[redflag_12, "spearman"].mean()))
                nboth.append(float(idx.loc[redflag_12, "n_both_defined"].mean()))
            else:
                pear.append(float(idx.loc[feat, "pearson"]))
                spear.append(float(idx.loc[feat, "spearman"]))
                nboth.append(float(idx.loc[feat, "n_both_defined"]))
        summary_rows.append(
            {
                "feature": feat,
                "matched_train_pearson_mean": float(np.nanmean(pear)),
                "matched_train_pearson_min": float(np.nanmin(pear)),
                "matched_train_pearson_max": float(np.nanmax(pear)),
                "matched_train_spearman_mean": float(np.nanmean(spear)),
                "matched_train_n_both_mean": float(np.nanmean(nboth)),
            }
        )
    summary = pd.DataFrame(summary_rows)

    payload = {
        "generated_utc": pd.Timestamp.utcnow().isoformat(),
        "purpose": "H3v2 §3 -- thin-composition vs memorization decomposition, rubric v1.2",
        "campaign": "v1.2 student vs v1.2 teacher",
        "n_seeds": N_SEEDS,
        "eval_per_section_counts": eval_counts,
        "per_seed": [
            {"seed": r["seed"], "n_chunks": r["n_chunks"], "shortfall": r["shortfall"],
             "table": r["table"].to_dict(orient="records")}
            for r in results
        ],
        "summary": summary.to_dict(orient="records"),
    }
    out_json = OUT_DIR / f"h3v2_composition_control_{STAMP}.json"
    out_json.write_text(json.dumps(payload, indent=1, default=str))
    print(f"\nwrote {out_json}")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
