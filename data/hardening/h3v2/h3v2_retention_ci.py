"""H3v2 section 3, part 1c -- filing-clustered bootstrap CIs on the v1.2
retention estimates.

THIN WRAPPER over `data/hardening/h3_retention_ci.py`: its `bootstrap()` is
imported and used verbatim (4,000 draws, seed 0, resampling FILINGS -- the unit
the features live on -- with the 12-feature red-flag family mean recomputed
WITHIN each resample so the interval carries the cross-feature correlation).
Only the input tables are swapped. That module is not edited.

The eval-only slice is the unbiased one but it is also the thin one: 29 filings
carry a RISK_FACTORS rate and 50 carry an MDA rate. A point estimate without an
interval on 29 filings would be the exact mistake this project keeps finding.

Run: python3 data/hardening/h3v2/h3v2_retention_ci.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "data" / "hardening"))

from h3_retention_ci import KEY, N_BOOT, SEED, bootstrap  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "hardening" / "h3v2"
STAMP = "2026-08-27_H3v2"


def main() -> None:
    t_eval = pd.read_parquet(OUT_DIR / f"features_teacher_evalchunks_v12_{STAMP}.parquet").set_index(KEY).sort_index()
    s_eval = pd.read_parquet(OUT_DIR / f"features_student_evalchunks_v12_{STAMP}.parquet").set_index(KEY).sort_index()
    t_pool = pd.read_parquet(OUT_DIR / f"features_teacher_v12_{STAMP}.parquet").set_index(KEY).sort_index()
    s_pool = pd.read_parquet(OUT_DIR / f"features_student_v12_{STAMP}.parquet").set_index(KEY).sort_index()

    payload = {
        "generated_utc": pd.Timestamp.utcnow().isoformat(),
        "campaign": "H3v2 -- rubric v1.2 student vs rubric v1.2 teacher",
        "n_boot": N_BOOT,
        "seed": SEED,
        "resample_unit": "filing (the 630-row feature table's rows), with replacement",
        "machinery": "h3_retention_ci.bootstrap imported verbatim; only the input tables differ",
        "note_pooled": "POOLED IS AN UPPER BOUND: 5,736/6,746 = 85.0% of pooled chunks are the student's own training rows.",
        "eval_only": {k: bootstrap(t_eval, s_eval, k) for k in ("pearson", "spearman")},
        "pooled_UPPER_BOUND": {k: bootstrap(t_pool, s_pool, k) for k in ("pearson", "spearman")},
    }
    out = OUT_DIR / f"h3v2_retention_ci_{STAMP}.json"
    out.write_text(json.dumps(payload, indent=1))
    print(f"wrote {out}")
    for slice_name in ("eval_only", "pooled_UPPER_BOUND"):
        for kind in ("pearson", "spearman"):
            print(f"\n=== {slice_name} ({kind}) ===")
            for k, v in payload[slice_name][kind].items():
                lo = "None" if v["ci_lo"] is None else f"{v['ci_lo']:.4f}"
                hi = "None" if v["ci_hi"] is None else f"{v['ci_hi']:.4f}"
                print(f"  {k:52s} {v['point']:.4f}  [{lo}, {hi}]  degenerate={v['n_degenerate_resamples']}")


if __name__ == "__main__":
    main()
