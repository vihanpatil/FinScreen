"""H3 section 3, part 3 -- how big is the harness's own nuisance variation,
so the teacher-vs-student difference can be read against it rather than
against zero?

Motivation (a real defect found during this run, not a hypothetical): the first
pass wrote the student feature table in a different ON-DISK ROW ORDER from
`data/features.parquet`. `backtest.load_modeling_frame()` sorts by
`filing_date` alone using pandas' default NON-STABLE quicksort and the 630 rows
carry only 298 distinct filing_dates, so tied rows permute. XGBoost's
`subsample=0.8` / `colsample_bytree=0.8` then draw different rows under the same
`random_state=42`. Numeric-only mean dedup IC moved 0.0972 -> 0.1448 and the
primary-spec text delta moved +0.0195 -> +0.0694 with the FEATURES BIT-FOR-BIT
UNCHANGED. That is the whole size of the effect under discussion, produced by
row order alone.

The fix (matching row order) is in `h3_features.py`. This script bounds what is
left: it sweeps XGBoost's `random_state` over 100 values, on the SAME frames,
folds and dedup mask, and reports the resulting distribution of the primary
metric for the teacher labels, for the student labels, and for the PAIRED
student-minus-teacher difference at a common seed.

Run: python3 data/hardening/h3_seed_sensitivity.py
"""

from __future__ import annotations

import json
import sys
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
N_SEEDS = 100


def prepare(path: Path):
    B.FEATURES_PATH = path
    df_raw, _ = B.load_modeling_frame()
    folds = B.build_walk_forward_folds(df_raw, B.BURN_IN_END)
    B.assert_no_fold_leakage(df_raw, folds)
    keep_mask = B.company_quarter_dedup_keep_mask(df_raw)
    return B.build_spec_frames(df_raw), folds, keep_mask


def mean_dedup_delta(frame, folds, keep_mask) -> float:
    res = B.run_backtest(frame, folds, keep_mask=keep_mask)
    d = res["text_and_numeric"]["spearman_ic_dedup"] - res["numeric_only"]["spearman_ic_dedup"]
    return float(d.mean())


def main() -> None:
    t_frames, t_folds, t_keep = prepare(TEACHER_FEATURES)
    s_frames, s_folds, s_keep = prepare(STUDENT_FEATURES)
    assert [str(f["test_quarter"]) for f in t_folds] == [str(f["test_quarter"]) for f in s_folds]
    assert bool((t_keep.values == s_keep.values).all()), "dedup masks differ -- not a paired comparison"

    original_seed = B.XGB_PARAMS["random_state"]
    rows = []
    try:
        for seed in range(N_SEEDS):
            B.XGB_PARAMS["random_state"] = seed
            row = {"seed": seed}
            for spec_name in S.SPEC_NAMES:
                t = mean_dedup_delta(t_frames[spec_name], t_folds, t_keep)
                s = mean_dedup_delta(s_frames[spec_name], s_folds, s_keep)
                row[f"{spec_name}__teacher"] = t
                row[f"{spec_name}__student"] = s
                row[f"{spec_name}__student_minus_teacher"] = s - t
            rows.append(row)
            if seed % 20 == 0:
                print(f"  seed {seed} done")
    finally:
        B.XGB_PARAMS["random_state"] = original_seed

    df = pd.DataFrame(rows)
    summary = {}
    for spec_name in S.SPEC_NAMES:
        block = {}
        for arm in ("teacher", "student", "student_minus_teacher"):
            v = df[f"{spec_name}__{arm}"].values
            block[arm] = {
                "seed42_value": float(df.loc[df["seed"] == 42, f"{spec_name}__{arm}"].iloc[0]),
                "mean": float(v.mean()),
                "sd_across_seeds": float(v.std(ddof=1)),
                "p2_5": float(np.percentile(v, 2.5)),
                "p97_5": float(np.percentile(v, 97.5)),
                "min": float(v.min()),
                "max": float(v.max()),
                "frac_positive": float((v > 0).mean()),
            }
        summary[spec_name] = block

    payload = {
        "generated_utc": pd.Timestamp.utcnow().isoformat(),
        "purpose": "H3 §3 -- XGBoost seed sweep: the harness's own nuisance spread on the primary metric",
        "metric": "cross-fold mean DEDUP Spearman IC delta (text+numeric minus numeric-only), 6 E1 folds",
        "n_seeds": N_SEEDS,
        "seeds": "random_state = 0..99 (the shipped value is 42)",
        "note_row_order_defect": (
            "Measured on this run: writing the student feature table in a different on-disk row "
            "order (identical values) moved numeric-only mean dedup IC 0.0972 -> 0.1448 and the "
            "primary-spec delta +0.0195 -> +0.0694. backtest.load_modeling_frame() sorts by "
            "filing_date with a NON-STABLE sort and 630 rows carry 298 distinct dates. Fixed by "
            "preserving features.py's build order; reported to G3 as a reproducibility convention."
        ),
        "summary": summary,
        "per_seed": df.to_dict(orient="records"),
    }
    out = OUT_DIR / "h3_seed_sensitivity_2026-08-25.json"
    out.write_text(json.dumps(payload, indent=1))
    print(f"wrote {out}\n")
    for spec_name, block in summary.items():
        print(f"=== {spec_name} ===")
        for arm, v in block.items():
            print(
                f"  {arm:24s} seed42={v['seed42_value']:+.4f} mean={v['mean']:+.4f} "
                f"sd={v['sd_across_seeds']:.4f} 95%=[{v['p2_5']:+.4f},{v['p97_5']:+.4f}] "
                f"frac>0={v['frac_positive']:.2f}"
            )


if __name__ == "__main__":
    main()
