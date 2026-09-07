"""H3 section 3, part 1 -- re-derive E1's feature table from the STUDENT
labels and measure per-feature retention against the teacher-derived table.

Uses `features.py`'s real machinery verbatim (same every-occurrence
attribution, same NaN-vs-0 policy, same numeric/target joins) by swapping only
which labels frame `features.build_feature_table()` consumes.

Writes ONLY under data/hardening/. `data/features.parquet`,
`data/labels.parquet` and every other frozen artifact are read-only here --
re-verified by sha256 at the end of the run.

Four feature tables are built:
  teacher_pooled  -- all 6,746 teacher labels        (must reproduce data/features.parquet)
  student_pooled  -- all 6,746 student labels
  teacher_eval    -- teacher labels, eval chunks only (n=1,010)
  student_eval    -- student labels, eval chunks only (n=1,010)

The eval-only pair is the ONLY unbiased slice: 5,736/6,746 = 85.0% of the
pooled chunks are the student's own training rows, so pooled retention is an
upper bound, not an estimate.

Run: python3 data/hardening/h3_features.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import features as F  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "hardening"
STUDENT_LABELS = OUT_DIR / "e1_relabel_student.parquet"
FROZEN_FEATURES = REPO_ROOT / "data" / "features.parquet"
FROZEN_LABELS = REPO_ROOT / "data" / "labels.parquet"

KEY = ["ticker", "accession_number", "filing_date"]
TEXT_FEATURES = F.TEXT_FEATURE_NAMES_NON_REDFLAG + F.RED_FLAG_FEATURE_NAMES
# Composition features are label-independent by construction (section_type is a
# corpus column, not a model output). They are kept in the table as a WIRING
# CHECK: retention must come back at exactly 1.0 or the join is wrong.
COMPOSITION_FEATURES = [
    "n_text_chunks_attributed",
    "share_chunks_risk_factors",
    "share_chunks_mda",
    "share_chunks_ex99_press_release",
    "share_chunks_8k_body",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def build_with_labels(labels: pd.DataFrame) -> pd.DataFrame:
    """features.build_feature_table() over an arbitrary labels frame.

    ROW ORDER IS LOAD-BEARING and is deliberately NOT re-sorted here. It is
    driven by `filings_base`, so it is identical across all four builds and
    identical to `data/features.parquet`. `backtest.load_modeling_frame()`
    sorts by `filing_date` alone with pandas' default NON-STABLE quicksort,
    and 630 rows carry only 298 distinct filing_dates (largest tie group 8),
    so a different on-disk row order permutes tied rows -> XGBoost's
    subsample/colsample_bytree draw different rows under the same seed ->
    different predictions from IDENTICAL features. Measured on the first pass
    of this script (which did sort): numeric-only mean dedup IC moved 0.0972
    -> 0.1448 with the numeric columns bit-for-bit unchanged. Preserving the
    order removes that confound entirely; the residual sensitivity is
    quantified separately in h3_seed_sensitivity.py.
    """
    original = F.load_labels
    F.load_labels = lambda: labels  # type: ignore[assignment]
    try:
        out, _diag = F.build_feature_table()
    finally:
        F.load_labels = original  # type: ignore[assignment]
    return out.set_index(KEY)


def retention_row(name: str, t: pd.Series, s: pd.Series) -> dict:
    both = t.notna() & s.notna()
    n_both = int(both.sum())
    row = {
        "feature": name,
        "n_rows": int(len(t)),
        "n_both_defined": n_both,
        "n_teacher_only_defined": int((t.notna() & s.isna()).sum()),
        "n_student_only_defined": int((s.notna() & t.isna()).sum()),
        "n_neither_defined": int((t.isna() & s.isna()).sum()),
        "teacher_mean": float(t.mean()) if t.notna().any() else float("nan"),
        "student_mean": float(s.mean()) if s.notna().any() else float("nan"),
        "teacher_std": float(t.std(ddof=1)) if t.notna().sum() > 1 else float("nan"),
        "student_std": float(s.std(ddof=1)) if s.notna().sum() > 1 else float("nan"),
        "mean_abs_diff": float((t[both] - s[both]).abs().mean()) if n_both else float("nan"),
        "pearson": float("nan"),
        "pearson_p": float("nan"),
        "spearman": float("nan"),
        "spearman_p": float("nan"),
        "note": "",
    }
    if n_both < 3:
        row["note"] = f"n_both={n_both} < 3 -- not computable"
        return row
    tv, sv = t[both].values.astype(float), s[both].values.astype(float)
    if np.std(tv) == 0 and np.std(sv) == 0:
        row["note"] = "both constant on the shared support"
        return row
    if np.std(tv) == 0 or np.std(sv) == 0:
        row["note"] = "one side constant on the shared support -- correlation undefined"
        return row
    r, rp = pearsonr(tv, sv)
    rho, rhop = spearmanr(tv, sv)
    row.update(pearson=float(r), pearson_p=float(rp), spearman=float(rho), spearman_p=float(rhop))
    return row


def retention_table(teacher: pd.DataFrame, student: pd.DataFrame, row_mask=None) -> pd.DataFrame:
    idx = teacher.index
    if row_mask is not None:
        idx = idx[row_mask]
    rows = [retention_row(c, teacher.loc[idx, c], student.loc[idx, c]) for c in TEXT_FEATURES]
    return pd.DataFrame(rows)


def main() -> None:
    t_start = time.time()
    frozen_features_sha_before = sha256(FROZEN_FEATURES)
    frozen_labels_sha_before = sha256(FROZEN_LABELS)

    student_labels_all = pd.read_parquet(STUDENT_LABELS)
    student_labels_all = student_labels_all[student_labels_all["parse_ok"]].copy()
    teacher_labels_all = F.load_labels()

    eval_ids = set(student_labels_all.loc[student_labels_all["split"] == "eval", "chunk_id"])
    train_ids = set(student_labels_all.loc[student_labels_all["split"] == "train", "chunk_id"])
    assert set(teacher_labels_all["chunk_id"]) == set(student_labels_all["chunk_id"]), (
        "student and teacher label sets differ -- the join is not chunk-for-chunk"
    )

    teacher_eval_labels = teacher_labels_all[teacher_labels_all["chunk_id"].isin(eval_ids)].copy()
    student_eval_labels = student_labels_all[student_labels_all["chunk_id"].isin(eval_ids)].copy()

    print(f"chunks: pooled={len(teacher_labels_all)} train={len(train_ids)} eval={len(eval_ids)}")

    print("building teacher_pooled ...")
    teacher_pooled = build_with_labels(teacher_labels_all)
    print("building student_pooled ...")
    student_pooled = build_with_labels(student_labels_all)
    print("building teacher_eval ...")
    teacher_eval = build_with_labels(teacher_eval_labels)
    print("building student_eval ...")
    student_eval = build_with_labels(student_eval_labels)

    # --- verification: the teacher re-derivation must reproduce the frozen artifact
    frozen = pd.read_parquet(FROZEN_FEATURES).set_index(KEY)
    check_cols = F.NUMERIC_FEATURE_NAMES + TEXT_FEATURES + ["target_excess_return"]
    reproduces = bool(
        teacher_pooled.index.equals(frozen.index)  # order-sensitive: same rows, SAME ORDER
        and np.allclose(
            teacher_pooled[check_cols].values.astype(float),
            frozen[check_cols].values.astype(float),
            equal_nan=True,
        )
    )
    print(f"teacher re-derivation reproduces data/features.parquet: {reproduces}")
    if not reproduces:
        raise AssertionError("teacher re-derivation did NOT reproduce data/features.parquet")

    # --- numeric columns and target must be byte-identical across all four builds
    invariant_cols = F.NUMERIC_FEATURE_NAMES + ["target_excess_return"]
    for name, tbl in (
        ("student_pooled", student_pooled),
        ("teacher_eval", teacher_eval),
        ("student_eval", student_eval),
    ):
        assert tbl.index.equals(teacher_pooled.index), f"{name} row set differs"
        assert np.allclose(
            tbl[invariant_cols].values.astype(float),
            teacher_pooled[invariant_cols].values.astype(float),
            equal_nan=True,
        ), f"{name} numeric/target columns moved -- they must not depend on labels"

    modeling_mask = teacher_pooled["target_excess_return"].notna().values

    tables = {
        "pooled_all_rows": retention_table(teacher_pooled, student_pooled),
        "pooled_modeling_rows": retention_table(teacher_pooled, student_pooled, modeling_mask),
        "eval_only_all_rows": retention_table(teacher_eval, student_eval),
        "eval_only_modeling_rows": retention_table(teacher_eval, student_eval, modeling_mask),
    }

    # --- wiring check: composition features must retain exactly 1.0
    wiring = {}
    for tname, tbl in tables.items():
        sub = tbl[tbl["feature"].isin(COMPOSITION_FEATURES)]
        vals = sub.set_index("feature")["pearson"].to_dict()
        wiring[tname] = {k: (None if pd.isna(v) else round(float(v), 12)) for k, v in vals.items()}

    # --- family summaries
    redflag_12 = [c for c in F.RED_FLAG_FEATURE_NAMES if c != "redflag_any_rate_press"]

    def family_summary(tbl: pd.DataFrame) -> dict:
        idx = tbl.set_index("feature")
        def mean_over(cols, col):
            v = idx.loc[[c for c in cols if c in idx.index], col].dropna()
            return float(v.mean()) if len(v) else float("nan")
        return {
            "redflag_12_pearson_mean": mean_over(redflag_12, "pearson"),
            "redflag_12_spearman_mean": mean_over(redflag_12, "spearman"),
            "redflag_12_pearson_min": (
                float(idx.loc[redflag_12, "pearson"].min())
                if idx.loc[redflag_12, "pearson"].notna().any() else float("nan")
            ),
            "redflag_12_n_computable": int(idx.loc[redflag_12, "pearson"].notna().sum()),
            "sentiment_negative_share_pearson": float(idx.loc["sentiment_negative_share", "pearson"]),
            "sentiment_negative_share_spearman": float(idx.loc["sentiment_negative_share", "spearman"]),
            "sentiment_mean_score_pearson": float(idx.loc["sentiment_mean_score", "pearson"]),
            "sentiment_mean_score_spearman": float(idx.loc["sentiment_mean_score", "spearman"]),
        }

    families = {k: family_summary(v) for k, v in tables.items()}

    # --- write artifacts
    student_features_path = OUT_DIR / "features_student_2026-08-25_H3.parquet"
    student_pooled.reset_index().to_parquet(student_features_path, index=False)
    student_eval.reset_index().to_parquet(
        OUT_DIR / "features_student_evalchunks_2026-08-25_H3.parquet", index=False
    )
    teacher_eval.reset_index().to_parquet(
        OUT_DIR / "features_teacher_evalchunks_2026-08-25_H3.parquet", index=False
    )

    payload = {
        "generated_utc": pd.Timestamp.utcnow().isoformat(),
        "purpose": "H3 §3 part 1 -- student-vs-teacher feature retention on E1",
        "inputs": {
            "student_labels": {"path": str(STUDENT_LABELS), "sha256": sha256(STUDENT_LABELS), "n_parse_ok": int(len(student_labels_all))},
            "teacher_labels": {"path": str(FROZEN_LABELS), "sha256": frozen_labels_sha_before, "n_parse_ok": int(len(teacher_labels_all))},
            "frozen_features": {"path": str(FROZEN_FEATURES), "sha256": frozen_features_sha_before},
        },
        "splits": {"n_train_chunks": len(train_ids), "n_eval_chunks": len(eval_ids), "train_share": round(len(train_ids) / len(student_labels_all), 4)},
        "teacher_rederivation_reproduces_frozen_features": reproduces,
        "n_feature_rows": int(len(teacher_pooled)),
        "n_modeling_rows": int(modeling_mask.sum()),
        "wiring_check_composition_pearson": wiring,
        "family_summaries": families,
        "retention_tables": {k: v.to_dict(orient="records") for k, v in tables.items()},
        "outputs": {
            "student_features": str(student_features_path),
            "student_evalchunk_features": str(OUT_DIR / "features_student_evalchunks_2026-08-25_H3.parquet"),
            "teacher_evalchunk_features": str(OUT_DIR / "features_teacher_evalchunks_2026-08-25_H3.parquet"),
        },
    }

    # --- frozen artifacts unchanged
    payload["frozen_unchanged"] = {
        "data/features.parquet": sha256(FROZEN_FEATURES) == frozen_features_sha_before,
        "data/labels.parquet": sha256(FROZEN_LABELS) == frozen_labels_sha_before,
    }
    assert all(payload["frozen_unchanged"].values()), "a frozen artifact changed -- abort"

    out_json = OUT_DIR / "h3_retention_2026-08-25.json"
    out_json.write_text(json.dumps(payload, indent=1, default=str))
    print(f"wrote {out_json} in {time.time() - t_start:.1f}s")

    for k, v in families.items():
        print(f"\n[{k}]")
        for kk, vv in v.items():
            print(f"  {kk:44s} {vv:.4f}" if isinstance(vv, float) else f"  {kk:44s} {vv}")


if __name__ == "__main__":
    main()
