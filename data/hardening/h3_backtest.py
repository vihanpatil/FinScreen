"""H3 section 3, part 2 -- re-run E1's walk-forward backtest on the
STUDENT-derived feature table, under BOTH pre-registered specifications
(H2 primary `pit_trailing_rank` and mandatory secondary `raw_levels`), and pair
it fold-for-fold against the teacher-derived run.

Everything comes from `backtest.py`/`spec.py` as they stand after H2 -- the
only thing swapped is `backtest.FEATURES_PATH`. Same folds, same dedup mask,
same XGB params (random_state=42, n_jobs=1 -> deterministic), same primary
metric (cross-fold mean DEDUP Spearman IC delta, text+numeric minus
numeric-only), same standing zero-information benchmark rows.

E1 and E2 backtest numbers are NUMERICALLY INCOMPARABLE (different benchmark
definition). Everything here is E1-on-E1.

Writes only under data/hardening/. Frozen artifacts are read-only; their
sha256s are re-verified at the end.

Run: python3 data/hardening/h3_backtest.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import backtest as B  # noqa: E402
import spec as S  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "hardening"
TEACHER_FEATURES = REPO_ROOT / "data" / "features.parquet"
STUDENT_FEATURES = OUT_DIR / "features_student_2026-08-25_H3.parquet"

PRIMARY_METRIC = "spearman_ic_dedup"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _delta(results: dict[str, pd.DataFrame], col: str) -> pd.Series:
    return results["text_and_numeric"][col] - results["numeric_only"][col]


def run_one(features_path: Path, label: str) -> dict:
    print(f"\n### {label}: {features_path}")
    B.FEATURES_PATH = features_path
    df_raw, n_dropped = B.load_modeling_frame()
    folds = B.build_walk_forward_folds(df_raw, B.BURN_IN_END)
    B.assert_no_fold_leakage(df_raw, folds)
    keep_mask = B.company_quarter_dedup_keep_mask(df_raw)
    spec_frames = B.build_spec_frames(df_raw)

    out: dict = {
        "label": label,
        "features_path": str(features_path),
        "features_sha256": sha256(features_path),
        "n_rows": int(len(df_raw)),
        "n_dropped_incomplete_target": int(n_dropped),
        "n_folds": len(folds),
        "test_quarters": [str(f["test_quarter"]) for f in folds],
        "n_dedup_rows": int(keep_mask.sum()),
        "specs": {},
    }

    for spec_name in S.SPEC_NAMES:
        t0 = time.time()
        res = B.run_backtest(spec_frames[spec_name], folds, keep_mask=keep_mask)
        df_form, folds_form, res_form = B.run_form_controlled_ablation(
            spec_frames[spec_name], B.BURN_IN_END
        )
        d_dedup = _delta(res, "spearman_ic_dedup")
        d_raw = _delta(res, "spearman_ic")
        d_form = _delta(res_form, "spearman_ic")
        out["specs"][spec_name] = {
            "per_fold": {
                "test_quarter": res["numeric_only"]["test_quarter"].tolist(),
                "n_test": res["numeric_only"]["n_test"].tolist(),
                "n_test_dedup": res["numeric_only"]["n_test_dedup"].tolist(),
                "ic_dedup_numeric": res["numeric_only"]["spearman_ic_dedup"].tolist(),
                "ic_dedup_full": res["text_and_numeric"]["spearman_ic_dedup"].tolist(),
                "ic_dedup_delta": d_dedup.tolist(),
                "ic_raw_numeric": res["numeric_only"]["spearman_ic"].tolist(),
                "ic_raw_full": res["text_and_numeric"]["spearman_ic"].tolist(),
                "ic_raw_delta": d_raw.tolist(),
                "p_dedup_numeric": res["numeric_only"]["spearman_p_dedup"].tolist(),
                "p_dedup_full": res["text_and_numeric"]["spearman_p_dedup"].tolist(),
                "p_raw_numeric": res["numeric_only"]["spearman_p"].tolist(),
                "p_raw_full": res["text_and_numeric"]["spearman_p"].tolist(),
            },
            "form_controlled": {
                "n_rows": int(len(df_form)),
                "n_folds": len(folds_form),
                "test_quarter": res_form["numeric_only"]["test_quarter"].tolist(),
                "ic_numeric": res_form["numeric_only"]["spearman_ic"].tolist(),
                "ic_full": res_form["text_and_numeric"]["spearman_ic"].tolist(),
                "ic_delta": d_form.tolist(),
                "mean_delta": float(d_form.mean()),
                "std_delta_ddof1": float(d_form.std(ddof=1)),
                "n_positive_folds": int((d_form > 0).sum()),
            },
            "summary": {
                "mean_ic_dedup_numeric": float(res["numeric_only"]["spearman_ic_dedup"].mean()),
                "mean_ic_dedup_full": float(res["text_and_numeric"]["spearman_ic_dedup"].mean()),
                "mean_dedup_delta_PRIMARY_METRIC": float(d_dedup.mean()),
                "std_dedup_delta_ddof1": float(d_dedup.std(ddof=1)),
                "n_positive_dedup_folds": int((d_dedup > 0).sum()),
                "mean_ic_raw_numeric": float(res["numeric_only"]["spearman_ic"].mean()),
                "mean_ic_raw_full": float(res["text_and_numeric"]["spearman_ic"].mean()),
                "mean_raw_delta": float(d_raw.mean()),
                "std_raw_delta_ddof1": float(d_raw.std(ddof=1)),
                "n_positive_raw_folds": int((d_raw > 0).sum()),
            },
            "seconds": round(time.time() - t0, 1),
        }
        print(
            f"  [{spec_name}] mean dedup delta = "
            f"{out['specs'][spec_name]['summary']['mean_dedup_delta_PRIMARY_METRIC']:+.4f} "
            f"(std {out['specs'][spec_name]['summary']['std_dedup_delta_ddof1']:.4f}, "
            f"{out['specs'][spec_name]['summary']['n_positive_dedup_folds']}/{len(folds)} positive folds) "
            f"| form-controlled {out['specs'][spec_name]['form_controlled']['mean_delta']:+.4f}"
        )

    print("  standing diagnostics ...")
    standing = B.compute_standing_diagnostics(
        df_raw, spec_frames, folds, keep_mask, active_spec=S.PRIMARY_SPEC
    )
    out["zero_information_benchmarks"] = standing["bench_summary"].to_dict(orient="records")
    out["bootstrap_anchor"] = {
        k: {kk: (float(vv) if isinstance(vv, (int, float, np.floating)) else vv) for kk, vv in v[1].items()}
        for k, v in standing["bootstrap"].items()
    }
    out["_standing"] = standing
    out["_frames"] = (df_raw, n_dropped, folds, spec_frames, keep_mask)
    return out


def main() -> None:
    frozen_before = {p: sha256(p) for p in (TEACHER_FEATURES,)}

    teacher = run_one(TEACHER_FEATURES, "TEACHER (E1 Claude labels, frozen data/features.parquet)")
    student = run_one(STUDENT_FEATURES, "STUDENT (epoch-2 Qwen relabel of the same 6,746 chunks)")

    # --- write the student's full generated report through the real generator
    df_raw, n_dropped, folds, spec_frames, keep_mask = student.pop("_frames")
    standing = student.pop("_standing")
    B.FEATURES_PATH = STUDENT_FEATURES
    df = spec_frames[S.PRIMARY_SPEC]
    res_primary = B.run_backtest(df, folds, keep_mask=keep_mask)
    res_secondary = B.run_backtest(spec_frames[S.SECONDARY_SPEC], folds, keep_mask=keep_mask)
    df_form, folds_form, res_form = B.run_form_controlled_ablation(df, B.BURN_IN_END)
    importances = {
        "numeric_only": B.fit_full_sample_importance(df, B.NUMERIC_FEATURES),
        "text_and_numeric": B.fit_full_sample_importance(df, B.FULL_FEATURES),
    }
    report_path = OUT_DIR / "backtest_report_2026-08-25_H3_student.md"
    B.write_backtest_report(
        df, n_dropped, folds, res_primary, importances, B.compute_dedup_diagnostics(df),
        df_form, folds_form, res_form, standing=standing, results_secondary=res_secondary,
        output_path=report_path,
    )
    print(f"\nwrote {report_path}")
    teacher.pop("_frames", None)
    teacher.pop("_standing", None)

    # --- correspondence table
    corr = {}
    for spec_name in S.SPEC_NAMES:
        t = np.array(teacher["specs"][spec_name]["per_fold"]["ic_dedup_delta"], float)
        s = np.array(student["specs"][spec_name]["per_fold"]["ic_dedup_delta"], float)
        both = ~(np.isnan(t) | np.isnan(s))
        corr[spec_name] = {
            "teacher_mean_dedup_delta": float(np.nanmean(t)),
            "student_mean_dedup_delta": float(np.nanmean(s)),
            "student_minus_teacher_mean": float(np.nanmean(s) - np.nanmean(t)),
            "per_fold_teacher": t.tolist(),
            "per_fold_student": s.tolist(),
            "per_fold_difference": (s - t).tolist(),
            "mean_abs_per_fold_difference": float(np.nanmean(np.abs(s - t))),
            "sign_agreement_folds": int(np.sum(np.sign(t[both]) == np.sign(s[both]))),
            "n_folds": int(both.sum()),
            "pearson_across_folds": (
                float(np.corrcoef(t[both], s[both])[0, 1]) if both.sum() > 2 else None
            ),
            "teacher_form_controlled_mean": teacher["specs"][spec_name]["form_controlled"]["mean_delta"],
            "student_form_controlled_mean": student["specs"][spec_name]["form_controlled"]["mean_delta"],
        }

    payload = {
        "generated_utc": pd.Timestamp.utcnow().isoformat(),
        "purpose": "H3 §3 part 2 -- E1 backtest, teacher vs student labels, both pre-registered specs",
        "primary_metric": "cross-fold mean DEDUP Spearman IC delta (text+numeric minus numeric-only)",
        "benchmark_note": (
            "E1 benchmark (as shipped). E2 will use a different, membership-dated "
            "excl-self equal-weighted benchmark -- E1 and E2 backtest numbers are "
            "NUMERICALLY INCOMPARABLE."
        ),
        "validation": (
            "Walk-forward expanding window, time-ordered by public filing_date, 6 quarterly "
            "test folds after a 2023Q3-2024Q4 burn-in; no shuffle; per-fold spreads reported; "
            "dedup IC beside raw IC; XGB random_state=42, n_jobs=1 (deterministic)."
        ),
        "teacher": teacher,
        "student": student,
        "correspondence": corr,
        "student_report": str(report_path),
    }
    payload["frozen_unchanged"] = {str(p): sha256(p) == v for p, v in frozen_before.items()}
    assert all(payload["frozen_unchanged"].values()), "a frozen artifact changed -- abort"

    out_json = OUT_DIR / "h3_backtest_2026-08-25.json"
    out_json.write_text(json.dumps(payload, indent=1, default=str))
    print(f"wrote {out_json}")

    for spec_name in S.SPEC_NAMES:
        c = corr[spec_name]
        print(f"\n=== {spec_name} ===")
        print(f"  teacher mean dedup delta {c['teacher_mean_dedup_delta']:+.4f}")
        print(f"  student mean dedup delta {c['student_mean_dedup_delta']:+.4f}")
        print(f"  per-fold teacher: {[round(x,4) for x in c['per_fold_teacher']]}")
        print(f"  per-fold student: {[round(x,4) for x in c['per_fold_student']]}")
        print(f"  sign agreement {c['sign_agreement_folds']}/{c['n_folds']}, across-fold r={c['pearson_across_folds']}")
        print(f"  form-controlled: teacher {c['teacher_form_controlled_mean']:+.4f} student {c['student_form_controlled_mean']:+.4f}")


if __name__ == "__main__":
    main()
