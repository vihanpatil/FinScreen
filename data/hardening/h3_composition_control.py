"""H3 section 3, part 1b -- the composition control for the eval-only slice.

The eval-only retention numbers are unbiased with respect to memorization but
they are computed over a much THINNER chunk composition (1,010 chunks spread
over 630 filings instead of 6,746), so every filing-level rate is a mean over
1-3 chunks on BOTH sides. That inflates per-filing sampling noise symmetrically
and mechanically drags the measured correlation down, in the OPPOSITE direction
from pooled's memorization inflation.

This script separates the two effects. It draws, from the student's own TRAIN
chunks only, a sample matched to the eval split's per-section_type counts, and
recomputes retention on it. That sample is:
  - thin, exactly like eval (same composition, same size), and
  - 100% memorized, exactly like the pooled corpus's bulk.

So:   pooled (thick, memorized)  ->  matched-train (thin, memorized)  = the
      thin-composition deflation alone;
      matched-train (thin, memorized)  ->  eval (thin, unmemorized)   = the
      memorization inflation alone.

8K_BODY (n=8) is entirely in the eval split, so the matched control is short by
those 8 chunks (1,002 vs 1,010). 8K_BODY is non-evaluable anyway (HANDOFF §7).

Run: python3 data/hardening/h3_composition_control.py
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
from h3_features import KEY, TEXT_FEATURES, retention_table  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "hardening"
STUDENT_LABELS = OUT_DIR / "e1_relabel_student.parquet"
N_SEEDS = 5

_BASE = None
_ACCMAP = None


def _prep():
    global _BASE, _ACCMAP
    if _BASE is None:
        _BASE = F.load_filings_base()
        _ACCMAP = F.build_accession_to_company_map(_BASE)
    return _BASE, _ACCMAP


def text_table(labels: pd.DataFrame) -> pd.DataFrame:
    """The TEXT half of features.build_feature_table(), verbatim machinery,
    without re-deriving the (label-independent) numeric block each time."""
    base, acc_map = _prep()
    occ = F.explode_label_occurrences(labels)
    occ_attached = F.attach_company_and_verify_no_backward_flow(occ, acc_map)
    text_features = F.build_text_features(occ_attached)
    out = base.merge(text_features, on=KEY, how="left")
    text_cols = [c for c in text_features.columns if c not in KEY]
    mean_score_cols = {"sentiment_mean_score", "sentiment_negative_share", "guidance_signed_mean"}
    redflag_rate_cols = {c for c in text_cols if c.startswith("redflag_")}
    zero_fill = [c for c in text_cols if c not in mean_score_cols and c not in redflag_rate_cols]
    out[zero_fill] = out[zero_fill].fillna(0.0)
    return out.set_index(KEY).sort_index()


def main() -> None:
    student = pd.read_parquet(STUDENT_LABELS)
    student = student[student["parse_ok"]].copy()
    teacher = F.load_labels()

    # --- verification: the fast text path reproduces the full build exactly
    full = pd.read_parquet(OUT_DIR / "features_student_2026-08-25_H3.parquet").set_index(KEY).sort_index()
    fast = text_table(student)
    assert fast.index.equals(full.index)
    assert np.allclose(
        fast[TEXT_FEATURES].values.astype(float),
        full[TEXT_FEATURES].values.astype(float),
        equal_nan=True,
    ), "fast text path does not reproduce build_feature_table()'s text columns"
    print("fast text path verified against features_student_2026-08-25_H3.parquet")

    eval_counts = (
        student[student["split"] == "eval"].groupby("section_type").size().to_dict()
    )
    train_pool = student[student["split"] == "train"]
    print("eval per-section counts:", eval_counts)

    results = []
    for seed in range(N_SEEDS):
        rng = np.random.default_rng(seed)
        picked = []
        shortfall = {}
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
        "purpose": "H3 §3 -- thin-composition vs memorization decomposition of the retention drop",
        "n_seeds": N_SEEDS,
        "eval_per_section_counts": eval_counts,
        "per_seed": [
            {"seed": r["seed"], "n_chunks": r["n_chunks"], "shortfall": r["shortfall"],
             "table": r["table"].to_dict(orient="records")}
            for r in results
        ],
        "summary": summary.to_dict(orient="records"),
    }
    out_json = OUT_DIR / "h3_composition_control_2026-08-25.json"
    out_json.write_text(json.dumps(payload, indent=1, default=str))
    print(f"\nwrote {out_json}")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.4f}"))


if __name__ == "__main__":
    main()
