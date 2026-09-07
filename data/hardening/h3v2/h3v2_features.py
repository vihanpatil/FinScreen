"""H3v2 section 3, part 1 -- re-derive E1's feature table from the REPAIRED
(rubric v1.2) STUDENT labels and measure per-feature retention against the
v1.2 TEACHER-derived table.

This is a THIN WRAPPER over `data/hardening/h3_features.py`. That module is
imported, never edited: its hardcoded `STUDENT_LABELS`/`FROZEN_LABELS`/
`FROZEN_FEATURES` are v1.1 constants and stay v1.1 constants. What is reused
verbatim is its machinery -- `build_with_labels` (which preserves
`features.py`'s build order; see H3 §3.0a, the row-order defect worth +0.050
on the headline IC delta), `retention_row`, `retention_table`, `TEXT_FEATURES`,
`COMPOSITION_FEATURES`, `KEY`, `sha256`.

`features.py` itself is used verbatim through `build_with_labels`; nothing in
`features.py`, `backtest.py`, `spec.py` or any frozen artifact is edited.

WHAT IS DIFFERENT FROM H3, AND WHY:

  * The teacher is `data/labels_v12.parquet` (rubric v1.2), not
    `data/labels.parquet`. H3's verification #1 ("the teacher re-derivation
    reproduces data/features.parquet exactly") therefore HAS NO H3v2 ANALOGUE:
    `data/features.parquet` is the frozen v1.1-derived table and a v1.2 teacher
    arm will not reproduce it. That is correct, not a bug
    (H3v2_attenuation.md §1.8 caveat 10).

  * The two checks that replace it, both run below:
      V1 HARNESS-UNCHANGED -- the pipeline run on `data/labels.parquet` still
          reproduces `data/features.parquet` exactly, so the harness is the
          same harness H3 measured with.
      V2 DETERMINISM -- the pipeline run TWICE on `data/labels_v12.parquet`
          gives bit-identical tables (values and row order).

  * `data/labels_v12.parquet` carries 6,747 parse_ok rows; the student carries
    6,746. The extra row is E1's safety-refusal chunk CHK-8e69547e0900a8dd,
    which labeled under v1.2 but is outside the FROZEN split (H3v2 §1.6 step
    3). The teacher is restricted to the student's 6,746 chunk_ids so the two
    arms are chunk-for-chunk; otherwise a feature difference could be that one
    extra chunk rather than the labeler.

Four feature tables are built (plus the two verification builds):
  teacher_pooled  -- all 6,746 v1.2 teacher labels
  student_pooled  -- all 6,746 v1.2 student labels
  teacher_eval    -- v1.2 teacher labels, eval chunks only (n=1,010)
  student_eval    -- v1.2 student labels, eval chunks only (n=1,010)

The eval-only pair is the ONLY unbiased slice: 5,736/6,746 = 85.0% of the
pooled chunks are the student's own training rows, so pooled retention is an
upper bound, not an estimate.

Run: python3 data/hardening/h3v2/h3v2_features.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "data" / "hardening"))

import features as F  # noqa: E402
import h3_features as H3  # noqa: E402  -- imported, never edited

OUT_DIR = REPO_ROOT / "data" / "hardening" / "h3v2"
STUDENT_LABELS_V12 = OUT_DIR / "e1_relabel_student_v12.parquet"
TEACHER_LABELS_V12 = REPO_ROOT / "data" / "labels_v12.parquet"
FROZEN_LABELS_V11 = REPO_ROOT / "data" / "labels.parquet"
FROZEN_FEATURES_V11 = REPO_ROOT / "data" / "features.parquet"

KEY = H3.KEY
TEXT_FEATURES = H3.TEXT_FEATURES
COMPOSITION_FEATURES = H3.COMPOSITION_FEATURES
REDFLAG_12 = [c for c in F.RED_FLAG_FEATURE_NAMES if c != "redflag_any_rate_press"]

STAMP = "2026-08-27_H3v2"


def _load_teacher_v12(keep_chunk_ids: set[str]) -> pd.DataFrame:
    t = pd.read_parquet(TEACHER_LABELS_V12)
    t = t[t["parse_ok"]].copy()
    n_all = len(t)
    t = t[t["chunk_id"].isin(keep_chunk_ids)].copy()
    return t, n_all


def _identical(a: pd.DataFrame, b: pd.DataFrame, cols: list[str]) -> bool:
    return bool(
        a.index.equals(b.index)
        and np.allclose(
            a[cols].values.astype(float), b[cols].values.astype(float), equal_nan=True
        )
    )


def family_summary(tbl: pd.DataFrame) -> dict:
    idx = tbl.set_index("feature")

    def mean_over(cols, col):
        v = idx.loc[[c for c in cols if c in idx.index], col].dropna()
        return float(v.mean()) if len(v) else float("nan")

    return {
        "redflag_12_pearson_mean": mean_over(REDFLAG_12, "pearson"),
        "redflag_12_spearman_mean": mean_over(REDFLAG_12, "spearman"),
        "redflag_12_pearson_min": (
            float(idx.loc[REDFLAG_12, "pearson"].min())
            if idx.loc[REDFLAG_12, "pearson"].notna().any()
            else float("nan")
        ),
        "redflag_12_n_computable": int(idx.loc[REDFLAG_12, "pearson"].notna().sum()),
        "sentiment_negative_share_pearson": float(idx.loc["sentiment_negative_share", "pearson"]),
        "sentiment_negative_share_spearman": float(idx.loc["sentiment_negative_share", "spearman"]),
        "sentiment_mean_score_pearson": float(idx.loc["sentiment_mean_score", "pearson"]),
        "sentiment_mean_score_spearman": float(idx.loc["sentiment_mean_score", "spearman"]),
        "redflag_any_rate_press_pearson": float(idx.loc["redflag_any_rate_press", "pearson"]),
        "guidance_signed_mean_pearson": float(idx.loc["guidance_signed_mean", "pearson"]),
        "guidance_any_present_pearson": float(idx.loc["guidance_any_present", "pearson"]),
    }


def main() -> None:
    t0 = time.time()
    sha_before = {
        "data/labels.parquet": H3.sha256(FROZEN_LABELS_V11),
        "data/features.parquet": H3.sha256(FROZEN_FEATURES_V11),
        "data/labels_v12.parquet": H3.sha256(TEACHER_LABELS_V12),
        "data/hardening/h3v2/e1_relabel_student_v12.parquet": H3.sha256(STUDENT_LABELS_V12),
    }
    print("input sha256:")
    for k, v in sha_before.items():
        print(f"  {k:60s} {v[:16]}...")

    # ---- labels -----------------------------------------------------------
    student = pd.read_parquet(STUDENT_LABELS_V12)
    n_student_rows = len(student)
    student = student[student["parse_ok"]].copy()
    student_ids = set(student["chunk_id"])
    teacher, n_teacher_parse_ok_all = _load_teacher_v12(student_ids)

    assert set(teacher["chunk_id"]) == student_ids, (
        "v1.2 teacher and student label sets differ after restriction -- "
        "the join is not chunk-for-chunk"
    )
    dropped = n_teacher_parse_ok_all - len(teacher)
    print(
        f"chunks: student parse_ok={len(student)}/{n_student_rows}  "
        f"teacher v1.2 parse_ok={n_teacher_parse_ok_all} -> {len(teacher)} "
        f"(dropped {dropped}: outside the frozen split)"
    )

    eval_ids = set(student.loc[student["split"] == "eval", "chunk_id"])
    train_ids = set(student.loc[student["split"] == "train", "chunk_id"])
    print(f"split: train={len(train_ids)} eval={len(eval_ids)}")

    teacher_eval_labels = teacher[teacher["chunk_id"].isin(eval_ids)].copy()
    student_eval_labels = student[student["chunk_id"].isin(eval_ids)].copy()

    # ---- V1: HARNESS-UNCHANGED -------------------------------------------
    # The v1.1 pipeline still reproduces the frozen v1.1 feature table.
    print("\n[V1] harness-unchanged: rebuilding data/features.parquet from data/labels.parquet ...")
    teacher_v11 = H3.build_with_labels(F.load_labels())
    frozen = pd.read_parquet(FROZEN_FEATURES_V11).set_index(KEY)
    check_cols = F.NUMERIC_FEATURE_NAMES + TEXT_FEATURES + ["target_excess_return"]
    harness_unchanged = _identical(teacher_v11, frozen, check_cols)
    print(f"[V1] v1.1 re-derivation reproduces data/features.parquet EXACTLY: {harness_unchanged}")
    if not harness_unchanged:
        raise AssertionError("[V1] FAILED -- the harness moved; no v1.2 number may be read")

    # ---- the four v1.2 tables ---------------------------------------------
    print("\nbuilding teacher_pooled (v1.2) ...")
    teacher_pooled = H3.build_with_labels(teacher)
    print("building student_pooled (v1.2) ...")
    student_pooled = H3.build_with_labels(student)
    print("building teacher_eval (v1.2) ...")
    teacher_eval = H3.build_with_labels(teacher_eval_labels)
    print("building student_eval (v1.2) ...")
    student_eval = H3.build_with_labels(student_eval_labels)

    # ---- V2: DETERMINISM ---------------------------------------------------
    print("\n[V2] determinism: rebuilding teacher_pooled and student_pooled (v1.2) ...")
    teacher_pooled_2 = H3.build_with_labels(teacher)
    student_pooled_2 = H3.build_with_labels(student)
    det_teacher = _identical(teacher_pooled, teacher_pooled_2, check_cols)
    det_student = _identical(student_pooled, student_pooled_2, check_cols)
    print(f"[V2] teacher v1.2 build deterministic: {det_teacher}")
    print(f"[V2] student v1.2 build deterministic: {det_student}")
    if not (det_teacher and det_student):
        raise AssertionError("[V2] FAILED -- the v1.2 pipeline is not deterministic")

    # ---- the v1.2 teacher table is NOT data/features.parquet (expected) ----
    v12_reproduces_frozen = _identical(teacher_pooled, frozen, check_cols)
    n_text_cells_differ = int(
        (
            ~np.isclose(
                teacher_pooled[TEXT_FEATURES].values.astype(float),
                frozen[TEXT_FEATURES].values.astype(float),
                equal_nan=True,
            )
        ).sum()
    )
    print(
        f"\n[expected FALSE] v1.2 teacher table reproduces data/features.parquet: "
        f"{v12_reproduces_frozen}  ({n_text_cells_differ} text cells differ)"
    )

    # ---- numeric block and target must be label-independent ---------------
    invariant_cols = F.NUMERIC_FEATURE_NAMES + ["target_excess_return"]
    for name, tbl in (
        ("student_pooled", student_pooled),
        ("teacher_eval", teacher_eval),
        ("student_eval", student_eval),
        ("teacher_v11", teacher_v11),
    ):
        assert tbl.index.equals(teacher_pooled.index), f"{name} row set/order differs"
        assert np.allclose(
            tbl[invariant_cols].values.astype(float),
            teacher_pooled[invariant_cols].values.astype(float),
            equal_nan=True,
        ), f"{name} numeric/target columns moved -- they must not depend on labels"
    print("numeric block + target identical across all builds (label-independent): True")

    modeling_mask = teacher_pooled["target_excess_return"].notna().values

    tables = {
        "pooled_all_rows": H3.retention_table(teacher_pooled, student_pooled),
        "pooled_modeling_rows": H3.retention_table(teacher_pooled, student_pooled, modeling_mask),
        "eval_only_all_rows": H3.retention_table(teacher_eval, student_eval),
        "eval_only_modeling_rows": H3.retention_table(teacher_eval, student_eval, modeling_mask),
    }

    # ---- V3: WIRING CHECK --------------------------------------------------
    wiring = {}
    wiring_ok = True
    for tname, tbl in tables.items():
        sub = tbl[tbl["feature"].isin(COMPOSITION_FEATURES)].set_index("feature")["pearson"]
        wiring[tname] = {k: (None if pd.isna(v) else round(float(v), 12)) for k, v in sub.items()}
        for k, v in wiring[tname].items():
            if v is None or abs(v - 1.0) > 1e-12:
                wiring_ok = False
    print(f"\n[V3] wiring check -- all 5 composition features retain exactly 1.0: {wiring_ok}")
    if not wiring_ok:
        raise AssertionError("[V3] FAILED -- broken join; STOP (H3 §3.0 verification 2)")

    # ---- V4: guidance NaN mapping is still a no-op for missing vs NONE -----
    gmap = F.GUIDANCE_MAP
    guidance_noop = {
        "NONE_maps_to_nan": "NONE" not in gmap,
        "null_maps_to_nan": bool(pd.isna(pd.Series([None]).map(gmap)).all()),
        "student_guidance_value_counts": {
            str(k): int(v)
            for k, v in student["guidance_direction"].value_counts(dropna=False).items()
        },
        "teacher_guidance_value_counts": {
            str(k): int(v)
            for k, v in teacher["guidance_direction"].value_counts(dropna=False).items()
        },
    }
    print(f"[V4] guidance missing->NONE post-rule is a no-op for features: "
          f"{guidance_noop['NONE_maps_to_nan'] and guidance_noop['null_maps_to_nan']}")

    families = {k: family_summary(v) for k, v in tables.items()}

    # ---- write derived tables ---------------------------------------------
    paths = {
        "teacher_features_v12": OUT_DIR / f"features_teacher_v12_{STAMP}.parquet",
        "student_features_v12": OUT_DIR / f"features_student_v12_{STAMP}.parquet",
        "teacher_evalchunk_features_v12": OUT_DIR / f"features_teacher_evalchunks_v12_{STAMP}.parquet",
        "student_evalchunk_features_v12": OUT_DIR / f"features_student_evalchunks_v12_{STAMP}.parquet",
    }
    teacher_pooled.reset_index().to_parquet(paths["teacher_features_v12"], index=False)
    student_pooled.reset_index().to_parquet(paths["student_features_v12"], index=False)
    teacher_eval.reset_index().to_parquet(paths["teacher_evalchunk_features_v12"], index=False)
    student_eval.reset_index().to_parquet(paths["student_evalchunk_features_v12"], index=False)

    payload = {
        "generated_utc": pd.Timestamp.utcnow().isoformat(),
        "purpose": "H3v2 §3 part 1 -- v1.2 student-vs-v1.2-teacher feature retention on E1",
        "framing": (
            "INSTRUMENT-VS-INSTRUMENT. Each student is measured against ITS OWN teacher. "
            "H3's v1.1 numbers and these v1.2 numbers are not two scores on one yardstick: "
            "the v1.2 teacher's own labels moved (red_flags 27.48% exact-set / 5.86% "
            "per-category, sentiment 4.59%, guidance 1.19% -- LABEL_SHIFT_v11_v12.md)."
        ),
        "inputs": {
            "student_labels_v12": {"path": str(STUDENT_LABELS_V12), "sha256": sha_before["data/hardening/h3v2/e1_relabel_student_v12.parquet"], "n_rows": n_student_rows, "n_parse_ok": len(student)},
            "teacher_labels_v12": {"path": str(TEACHER_LABELS_V12), "sha256": sha_before["data/labels_v12.parquet"], "n_parse_ok_all": n_teacher_parse_ok_all, "n_used": len(teacher), "n_dropped_outside_frozen_split": dropped},
            "frozen_labels_v11": {"path": str(FROZEN_LABELS_V11), "sha256": sha_before["data/labels.parquet"]},
            "frozen_features_v11": {"path": str(FROZEN_FEATURES_V11), "sha256": sha_before["data/features.parquet"]},
        },
        "splits": {
            "n_train_chunks": len(train_ids),
            "n_eval_chunks": len(eval_ids),
            "train_share": round(len(train_ids) / len(student), 4),
        },
        "pre_verifications": {
            "V1_harness_unchanged_v11_reproduces_frozen_features": harness_unchanged,
            "V2_v12_pipeline_deterministic_teacher": det_teacher,
            "V2_v12_pipeline_deterministic_student": det_student,
            "v12_teacher_reproduces_frozen_features_EXPECTED_FALSE": v12_reproduces_frozen,
            "v12_teacher_vs_frozen_n_text_cells_differ": n_text_cells_differ,
            "V3_wiring_composition_retention_exactly_1": wiring_ok,
            "V4_guidance_missing_to_none_is_noop": guidance_noop,
            "numeric_block_and_target_label_independent": True,
        },
        "n_feature_rows": int(len(teacher_pooled)),
        "n_modeling_rows": int(modeling_mask.sum()),
        "wiring_check_composition_pearson": wiring,
        "family_summaries": families,
        "retention_tables": {k: v.to_dict(orient="records") for k, v in tables.items()},
        "outputs": {k: str(v) for k, v in paths.items()},
    }

    sha_after = {
        "data/labels.parquet": H3.sha256(FROZEN_LABELS_V11),
        "data/features.parquet": H3.sha256(FROZEN_FEATURES_V11),
        "data/labels_v12.parquet": H3.sha256(TEACHER_LABELS_V12),
        "data/hardening/h3v2/e1_relabel_student_v12.parquet": H3.sha256(STUDENT_LABELS_V12),
    }
    payload["frozen_unchanged"] = {k: sha_after[k] == sha_before[k] for k in sha_before}
    payload["frozen_sha256_after"] = sha_after
    assert all(payload["frozen_unchanged"].values()), "a frozen artifact changed -- abort"

    out_json = OUT_DIR / f"h3v2_retention_{STAMP}.json"
    out_json.write_text(json.dumps(payload, indent=1, default=str))
    print(f"\nwrote {out_json} in {time.time() - t0:.1f}s")

    for k, v in families.items():
        print(f"\n[{k}]")
        for kk, vv in v.items():
            print(f"  {kk:44s} {vv:.4f}" if isinstance(vv, float) else f"  {kk:44s} {vv}")


if __name__ == "__main__":
    main()
