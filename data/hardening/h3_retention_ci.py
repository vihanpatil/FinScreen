"""H3 section 3, part 1c -- filing-clustered bootstrap CIs on the retention
estimates. The eval-only slice is the unbiased one but it is also the thin one
(29 filings carry a RISK_FACTORS rate, 50 carry an MDA rate), so a point
estimate without an interval would be the same mistake this project keeps
finding in other people's work.

Resamples FILINGS (the unit the features live on) with replacement, 4,000
draws, seed 0, and recomputes each feature's Pearson/Spearman retention on the
resampled rows. The red-flag family figure is recomputed as the mean of the 12
per-feature correlations WITHIN each resample, so its interval carries the
cross-feature correlation instead of pretending the 12 are independent.

Run: python3 data/hardening/h3_retention_ci.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import features as F  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "hardening"
KEY = ["ticker", "accession_number", "filing_date"]
N_BOOT = 4000
SEED = 0

REDFLAG_12 = [c for c in F.RED_FLAG_FEATURE_NAMES if c != "redflag_any_rate_press"]
HEADLINE = [
    "sentiment_negative_share",
    "sentiment_mean_score",
    "guidance_signed_mean",
    "guidance_any_present",
    "redflag_any_rate_press",
]


def _corr(t: np.ndarray, s: np.ndarray, kind: str) -> float:
    both = ~(np.isnan(t) | np.isnan(s))
    t, s = t[both], s[both]
    if len(t) < 3:
        return np.nan
    if kind == "spearman":
        t = pd.Series(t).rank().values
        s = pd.Series(s).rank().values
    if np.std(t) == 0 or np.std(s) == 0:
        return np.nan
    return float(np.corrcoef(t, s)[0, 1])


def bootstrap(teacher: pd.DataFrame, student: pd.DataFrame, kind: str) -> dict:
    rng = np.random.default_rng(SEED)
    n = len(teacher)
    cols = HEADLINE + REDFLAG_12
    T = {c: teacher[c].values.astype(float) for c in cols}
    S = {c: student[c].values.astype(float) for c in cols}

    draws = {c: [] for c in cols}
    fam = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, n, size=n)
        per = {}
        for c in cols:
            per[c] = _corr(T[c][idx], S[c][idx], kind)
            draws[c].append(per[c])
        vals = [per[c] for c in REDFLAG_12 if not np.isnan(per[c])]
        fam.append(float(np.mean(vals)) if vals else np.nan)

    out = {}
    for c in cols:
        a = np.array(draws[c], dtype=float)
        finite = a[~np.isnan(a)]
        out[c] = {
            "point": _corr(T[c], S[c], kind),
            "ci_lo": float(np.percentile(finite, 2.5)) if len(finite) else None,
            "ci_hi": float(np.percentile(finite, 97.5)) if len(finite) else None,
            "n_degenerate_resamples": int(np.isnan(a).sum()),
        }
    fa = np.array(fam, dtype=float)
    finite = fa[~np.isnan(fa)]
    point_fam = float(np.mean([_corr(T[c], S[c], kind) for c in REDFLAG_12]))
    out["redflag_12_mean"] = {
        "point": point_fam,
        "ci_lo": float(np.percentile(finite, 2.5)),
        "ci_hi": float(np.percentile(finite, 97.5)),
        "n_degenerate_resamples": int(np.isnan(fa).sum()),
    }
    return out


def main() -> None:
    t_eval = pd.read_parquet(OUT_DIR / "features_teacher_evalchunks_2026-08-25_H3.parquet").set_index(KEY).sort_index()
    s_eval = pd.read_parquet(OUT_DIR / "features_student_evalchunks_2026-08-25_H3.parquet").set_index(KEY).sort_index()
    t_pool = pd.read_parquet(REPO_ROOT / "data" / "features.parquet").set_index(KEY).sort_index()
    s_pool = pd.read_parquet(OUT_DIR / "features_student_2026-08-25_H3.parquet").set_index(KEY).sort_index()

    payload = {
        "generated_utc": pd.Timestamp.utcnow().isoformat(),
        "n_boot": N_BOOT,
        "seed": SEED,
        "resample_unit": "filing (the 630-row feature table's rows), with replacement",
        "eval_only": {k: bootstrap(t_eval, s_eval, k) for k in ("pearson", "spearman")},
        "pooled_UPPER_BOUND": {k: bootstrap(t_pool, s_pool, k) for k in ("pearson", "spearman")},
    }
    out = OUT_DIR / "h3_retention_ci_2026-08-25.json"
    out.write_text(json.dumps(payload, indent=1))
    print(f"wrote {out}")
    for slice_name in ("eval_only", "pooled_UPPER_BOUND"):
        print(f"\n=== {slice_name} (Pearson) ===")
        for k, v in payload[slice_name]["pearson"].items():
            print(f"  {k:50s} {v['point']:.4f}  [{v['ci_lo']:.4f}, {v['ci_hi']:.4f}]  degenerate={v['n_degenerate_resamples']}")


if __name__ == "__main__":
    main()
