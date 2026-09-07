"""H3v2 section 3, part 1d -- PAIRED filing-clustered bootstrap on the
v1.1 -> v1.2 retention DELTA, and on the teacher/student attribution of it.

Why this exists. H3's eval-only CIs and H3v2's eval-only CIs are two MARGINAL
intervals on the same 630 filings and the same 1,010 held-out chunks. Reading
"do they overlap?" is valid but very conservative: the two estimates share
every source of filing-level sampling noise. Resampling the SAME filing indices
for both campaigns inside one bootstrap removes that shared noise and gives the
interval that actually answers "did retention move?".

WHAT THE DELTA IS AND IS NOT. Each retention is measured against ITS OWN
teacher, so the delta is a difference of two instrument-vs-own-teacher
correlations, NOT two scores on one yardstick (H3v2 §1.8 caveat 8). The v1.2
teacher's own labels moved: red_flags 27.48% exact-set / 5.86% per-category,
sentiment 4.59% (LABEL_SHIFT_v11_v12.md). The attribution arms below exist
precisely to say how much of the delta is the teacher moving.

Four quantities, all on the eval-only (unbiased) slice, all from the SAME
4,000 filing resamples, seed 0:

  TOTAL       rho(T12,S12) - rho(T11,S11)   -- the headline move
  TEACHER_ARM rho(T12,S11) - rho(T11,S11)   -- new teacher, OLD student
  STUDENT_ARM rho(T11,S12) - rho(T11,S11)   -- old teacher, NEW student
  RUBRIC_GAP  rho(T11,T12)                  -- how far the rubric alone moved
                                                the teacher-derived feature,
                                                as a scale for reading the rest

Run: python3 data/hardening/h3v2/h3v2_paired_delta_ci.py
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
from h3_retention_ci import KEY, N_BOOT, SEED, _corr  # noqa: E402  -- verbatim

HARD = REPO_ROOT / "data" / "hardening"
OUT_DIR = HARD / "h3v2"
STAMP = "2026-08-27_H3v2"

REDFLAG_12 = [c for c in F.RED_FLAG_FEATURE_NAMES if c != "redflag_any_rate_press"]
HEADLINE = [
    "sentiment_negative_share",
    "sentiment_mean_score",
    "guidance_any_present",
    "redflag_any_rate_press",
]
COLS = HEADLINE + REDFLAG_12

PAIRS = {
    "T11_S11": ("t11", "s11"),
    "T12_S12": ("t12", "s12"),
    "T12_S11": ("t12", "s11"),
    "T11_S12": ("t11", "s12"),
    "T11_T12": ("t11", "t12"),
}


def _pack(df: pd.DataFrame) -> dict:
    return {c: df[c].values.astype(float) for c in COLS}


def main() -> None:
    paths = {
        "t11": HARD / "features_teacher_evalchunks_2026-08-25_H3.parquet",
        "s11": HARD / "features_student_evalchunks_2026-08-25_H3.parquet",
        "t12": OUT_DIR / f"features_teacher_evalchunks_v12_{STAMP}.parquet",
        "s12": OUT_DIR / f"features_student_evalchunks_v12_{STAMP}.parquet",
    }
    frames = {k: pd.read_parquet(v).set_index(KEY).sort_index() for k, v in paths.items()}
    ref = frames["t11"].index
    for k, v in frames.items():
        assert v.index.equals(ref), f"{k}: index differs -- the pairing is invalid"
    n = len(ref)
    data = {k: _pack(v) for k, v in frames.items()}
    print(f"paired bootstrap over {n} filings, {N_BOOT} draws, seed {SEED}")

    rng = np.random.default_rng(SEED)
    # per-draw storage: pair -> feature -> list, plus family means
    draws = {p: {c: [] for c in COLS} for p in PAIRS}
    fam = {p: [] for p in PAIRS}

    for _ in range(N_BOOT):
        idx = rng.integers(0, n, size=n)      # ONE resample, applied to BOTH campaigns
        for pname, (a, b) in PAIRS.items():
            per = {}
            for c in COLS:
                per[c] = _corr(data[a][c][idx], data[b][c][idx], "pearson")
                draws[pname][c].append(per[c])
            vals = [per[c] for c in REDFLAG_12 if not np.isnan(per[c])]
            fam[pname].append(float(np.mean(vals)) if vals else np.nan)

    def point(pname: str, feat: str) -> float:
        a, b = PAIRS[pname]
        if feat == "redflag_12_mean":
            return float(np.mean([_corr(data[a][c], data[b][c], "pearson") for c in REDFLAG_12]))
        return _corr(data[a][feat], data[b][feat], "pearson")

    def series(pname: str, feat: str) -> np.ndarray:
        return np.array(fam[pname] if feat == "redflag_12_mean" else draws[pname][feat], dtype=float)

    feats = COLS + ["redflag_12_mean"]
    out = {"levels": {}, "deltas": {}}

    for pname in PAIRS:
        out["levels"][pname] = {}
        for f in feats:
            a = series(pname, f)
            fin = a[~np.isnan(a)]
            out["levels"][pname][f] = {
                "point": point(pname, f),
                "ci_lo": float(np.percentile(fin, 2.5)) if len(fin) else None,
                "ci_hi": float(np.percentile(fin, 97.5)) if len(fin) else None,
                "n_degenerate": int(np.isnan(a).sum()),
            }

    # The 2x2 gives each factor's effect at BOTH levels of the other factor.
    # The v1.2-teacher-held-fixed student arm is the one E2 would actually run
    # under, so it is reported alongside the v1.1-teacher-held-fixed one.
    for dname, (hi, lo) in {
        "TOTAL_v12_minus_v11": ("T12_S12", "T11_S11"),
        "TEACHER_ARM_at_v11_student": ("T12_S11", "T11_S11"),
        "STUDENT_ARM_at_v11_teacher": ("T11_S12", "T11_S11"),
        "TEACHER_ARM_at_v12_student": ("T12_S12", "T11_S12"),
        "STUDENT_ARM_at_v12_teacher": ("T12_S12", "T12_S11"),
    }.items():
        out["deltas"][dname] = {}
        for f in feats:
            d = series(hi, f) - series(lo, f)
            fin = d[~np.isnan(d)]
            p = point(hi, f) - point(lo, f)
            out["deltas"][dname][f] = {
                "point": p,
                "ci_lo": float(np.percentile(fin, 2.5)),
                "ci_hi": float(np.percentile(fin, 97.5)),
                "frac_draws_gt_0": float((fin > 0).mean()),
                "n_degenerate": int(np.isnan(d).sum()),
            }

    payload = {
        "generated_utc": pd.Timestamp.utcnow().isoformat(),
        "purpose": "H3v2 §3 -- paired filing-clustered bootstrap on the v1.1->v1.2 retention delta",
        "slice": "EVAL-ONLY (the only unbiased slice), n=630 feature rows / 1,010 held-out chunks",
        "n_boot": N_BOOT,
        "seed": SEED,
        "n_filings": n,
        "framing": (
            "INSTRUMENT-VS-INSTRUMENT. Each retention is measured against ITS OWN teacher; "
            "the delta is a difference of two such correlations, not two scores on one yardstick. "
            "rubric v1.2 moved red_flags on 27.48% of rows (exact-set) / 5.86% per-category and "
            "sentiment on 4.59% (LABEL_SHIFT_v11_v12.md). TEACHER_ARM holds the student fixed at "
            "v1.1 and swaps only the teacher; it is the measured size of the 'easier teacher' "
            "explanation. The arms are NOT orthogonal and do not sum to TOTAL."
        ),
        "pairs": {k: list(v) for k, v in PAIRS.items()},
        **out,
    }
    p = OUT_DIR / f"h3v2_paired_delta_ci_{STAMP}.json"
    p.write_text(json.dumps(payload, indent=1))
    print(f"wrote {p}\n")

    show = ["redflag_12_mean", "sentiment_negative_share", "sentiment_mean_score",
            "redflag_any_rate_press", "redflag_MARGIN_COST_PRESSURE_rate_mda",
            "redflag_DEMAND_WEAKNESS_rate_mda"]
    print("LEVELS (eval-only, Pearson)")
    for pname in PAIRS:
        print(f"  [{pname}]")
        for f in show:
            v = out["levels"][pname][f]
            print(f"    {f:44s} {v['point']:.4f}  [{v['ci_lo']:.4f}, {v['ci_hi']:.4f}]")
    print("\nPAIRED DELTAS (same 4,000 filing resamples on both sides)")
    for dname in out["deltas"]:
        print(f"  [{dname}]")
        for f in show:
            v = out["deltas"][dname][f]
            print(f"    {f:44s} {v['point']:+.4f}  [{v['ci_lo']:+.4f}, {v['ci_hi']:+.4f}]  P(>0)={v['frac_draws_gt_0']:.3f}")


if __name__ == "__main__":
    main()
