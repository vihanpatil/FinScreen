"""H3v2 section 3 -- the "if it looks too good, assume an evaluation bug first"
pass (HANDOFF §7).

The v1.2 eval-only retention numbers came in far above H3's v1.1 numbers while
the CHUNK-level eval agreement barely moved. That shape is exactly what an
evaluation bug looks like, so it was chased before anything was reported.

Three diagnostics, none of which requires a model or the network:

  V5  WRAPPER-REPRODUCES-H3. Run h3v2_features.py's own code path over the
      v1.1 artifacts (v1.1 student vs v1.1 teacher) and check it reproduces
      H3 §3.1's RULED values. If the wrapper is wrong, this fails.

  X   THE 2x2 CROSS-PAIRING. Retention for every combination of
      {v1.1, v1.2} student x {v1.1, v1.2} teacher, on the SAME 630-row index,
      reusing the already-built feature tables (no new builds). This is the
      only available handle on H3v2 §1.8 caveat 8: "a retention rho that rises
      could reflect an easier teacher as much as a better student -- say which
      is being claimed."

  M   CHUNK-LEVEL MECHANISM. Per section_type x per red-flag-category
      precision/recall/F1 on the EVAL slice for both students against their
      own teachers, plus the SIGNED filing-level rate error. The manifests
      only carry per-category figures pooled over sections; the features are
      per-section, so the mechanism has to be read per-section.

Run: python3 data/hardening/h3v2/h3v2_diagnostics.py
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
import h3_features as H3  # noqa: E402

HARD = REPO_ROOT / "data" / "hardening"
OUT_DIR = HARD / "h3v2"
STAMP = "2026-08-27_H3v2"
KEY = H3.KEY
REDFLAG_12 = [c for c in F.RED_FLAG_FEATURE_NAMES if c != "redflag_any_rate_press"]

# H3 §3.1 / §3.5 RULED eval-only values (Pearson), transcribed from the ledger.
H3_RULED_EVAL = {
    "redflag_12_mean": 0.669,
    "sentiment_negative_share": 0.592,
    "sentiment_mean_score": 0.834,
    "redflag_MARGIN_COST_PRESSURE_rate_mda": 0.115,
    "redflag_DEMAND_WEAKNESS_rate_mda": 0.215,
    "redflag_any_rate_press": 0.622,
}


def fam(tbl: pd.DataFrame) -> dict:
    idx = tbl.set_index("feature")
    return {
        "redflag_12_mean": float(idx.loc[REDFLAG_12, "pearson"].mean()),
        "sentiment_negative_share": float(idx.loc["sentiment_negative_share", "pearson"]),
        "sentiment_mean_score": float(idx.loc["sentiment_mean_score", "pearson"]),
        "redflag_MARGIN_COST_PRESSURE_rate_mda": float(idx.loc["redflag_MARGIN_COST_PRESSURE_rate_mda", "pearson"]),
        "redflag_DEMAND_WEAKNESS_rate_mda": float(idx.loc["redflag_DEMAND_WEAKNESS_rate_mda", "pearson"]),
        "redflag_any_rate_press": float(idx.loc["redflag_any_rate_press", "pearson"]),
    }


def v5_wrapper_reproduces_h3() -> dict:
    """Rebuild H3's v1.1 arm through h3v2_features.py's own logic."""
    student = pd.read_parquet(HARD / "e1_relabel_student.parquet")
    student = student[student["parse_ok"]].copy()
    student_ids = set(student["chunk_id"])
    teacher = pd.read_parquet(REPO_ROOT / "data" / "labels.parquet")
    teacher = teacher[teacher["parse_ok"] & teacher["chunk_id"].isin(student_ids)].copy()
    assert set(teacher["chunk_id"]) == student_ids

    eval_ids = set(student.loc[student["split"] == "eval", "chunk_id"])
    t_eval = H3.build_with_labels(teacher[teacher["chunk_id"].isin(eval_ids)])
    s_eval = H3.build_with_labels(student[student["chunk_id"].isin(eval_ids)])
    got = fam(H3.retention_table(t_eval, s_eval))
    # H3 §3.1/§3.5 quotes 3 decimal places, so the tolerance is half an ulp of
    # the quoted precision (<=5.1e-4). H3's own machine record is also checked
    # exactly, which is the stronger of the two comparisons.
    ok = {k: bool(abs(got[k] - v) <= 5.1e-4) for k, v in H3_RULED_EVAL.items()}
    h3_json = json.load(open(HARD / "h3_retention_2026-08-25.json"))
    rec = fam(pd.DataFrame(h3_json["retention_tables"]["eval_only_all_rows"]))
    exact = {k: bool(abs(got[k] - rec[k]) < 1e-12) for k in rec}
    return {
        "measured": got,
        "h3_ledger_quoted_3dp": H3_RULED_EVAL,
        "matches_ledger_within_half_ulp_of_3dp": ok,
        "all_match_ledger": all(ok.values()),
        "h3_machine_record": rec,
        "matches_h3_machine_record_exactly": exact,
        "all_match_machine_record": all(exact.values()),
    }


def cross_pairing() -> dict:
    tables = {
        ("teacher", "v1.1", "eval"): HARD / "features_teacher_evalchunks_2026-08-25_H3.parquet",
        ("student", "v1.1", "eval"): HARD / "features_student_evalchunks_2026-08-25_H3.parquet",
        ("teacher", "v1.2", "eval"): OUT_DIR / f"features_teacher_evalchunks_v12_{STAMP}.parquet",
        ("student", "v1.2", "eval"): OUT_DIR / f"features_student_evalchunks_v12_{STAMP}.parquet",
        ("teacher", "v1.1", "pooled"): REPO_ROOT / "data" / "features.parquet",
        ("student", "v1.1", "pooled"): HARD / "features_student_2026-08-25_H3.parquet",
        ("teacher", "v1.2", "pooled"): OUT_DIR / f"features_teacher_v12_{STAMP}.parquet",
        ("student", "v1.2", "pooled"): OUT_DIR / f"features_student_v12_{STAMP}.parquet",
    }
    loaded = {k: pd.read_parquet(v).set_index(KEY).sort_index() for k, v in tables.items()}
    ref = loaded[("teacher", "v1.1", "eval")].index
    for k, v in loaded.items():
        assert v.index.equals(ref), f"{k} index differs -- cross-pairing invalid"

    out = {}
    for slc in ("eval", "pooled"):
        for tv in ("v1.1", "v1.2"):
            for sv in ("v1.1", "v1.2"):
                tab = H3.retention_table(loaded[("teacher", tv, slc)], loaded[("student", sv, slc)])
                out[f"{slc}__teacher_{tv}__student_{sv}"] = fam(tab)
    # teacher-vs-teacher and student-vs-student: how far the two RUBRICS move the
    # feature table, as a scale for reading the retention deltas.
    for slc in ("eval", "pooled"):
        out[f"{slc}__teacher_v1.1_VS_teacher_v1.2"] = fam(
            H3.retention_table(loaded[("teacher", "v1.1", slc)], loaded[("teacher", "v1.2", slc)])
        )
        out[f"{slc}__student_v1.1_VS_student_v1.2"] = fam(
            H3.retention_table(loaded[("student", "v1.1", slc)], loaded[("student", "v1.2", slc)])
        )
    return out


def _has(flags, cat) -> bool:
    return any(f["category"] == cat for f in flags)


def chunk_mechanism() -> dict:
    """Per section_type x category chunk-level P/R/F1 on the EVAL slice."""
    s11 = pd.read_parquet(HARD / "e1_relabel_student.parquet")
    s12 = pd.read_parquet(OUT_DIR / "e1_relabel_student_v12.parquet")
    t11 = pd.read_parquet(REPO_ROOT / "data" / "labels.parquet")
    t12 = pd.read_parquet(REPO_ROOT / "data" / "labels_v12.parquet")

    out = {}
    for tag, s, t in (("v1.1", s11, t11), ("v1.2", s12, t12)):
        s = s[s["parse_ok"] & (s["split"] == "eval")][["chunk_id", "section_type", "sentiment", "red_flags"]]
        t = t[t["parse_ok"]][["chunk_id", "sentiment", "red_flags"]]
        m = s.merge(t, on="chunk_id", suffixes=("_s", "_t"))
        assert len(m) == len(s), f"{tag}: eval join lost rows"
        rows = []
        for sec in ("RISK_FACTORS", "MDA", "EX99_PRESS_RELEASE"):
            sub = m[m["section_type"] == sec]
            if not len(sub):
                continue
            for cat in F.RED_FLAG_CATEGORIES:
                ts = sub["red_flags_t"].apply(lambda f, c=cat: _has(f, c)).values
                ss = sub["red_flags_s"].apply(lambda f, c=cat: _has(f, c)).values
                tp = int((ts & ss).sum()); fp = int((~ts & ss).sum()); fn = int((ts & ~ss).sum())
                prec = tp / (tp + fp) if tp + fp else float("nan")
                rec = tp / (tp + fn) if tp + fn else float("nan")
                f1 = 2 * prec * rec / (prec + rec) if tp and (prec + rec) else 0.0
                rows.append({
                    "section_type": sec, "category": cat, "n_chunks": int(len(sub)),
                    "support": int(ts.sum()), "predicted": int(ss.sum()),
                    "tp": tp, "fp": fp, "fn": fn,
                    "precision": round(prec, 4) if prec == prec else None,
                    "recall": round(rec, 4) if rec == rec else None,
                    "f1": round(f1, 4),
                    "net_bias_pred_minus_support": int(ss.sum() - ts.sum()),
                })
            # any-flag, the basis for redflag_any_rate_press
            ts = sub["red_flags_t"].apply(lambda f: len(f) > 0).values
            ss = sub["red_flags_s"].apply(lambda f: len(f) > 0).values
            tp = int((ts & ss).sum()); fp = int((~ts & ss).sum()); fn = int((ts & ~ss).sum())
            rows.append({
                "section_type": sec, "category": "__ANY__", "n_chunks": int(len(sub)),
                "support": int(ts.sum()), "predicted": int(ss.sum()),
                "tp": tp, "fp": fp, "fn": fn,
                "precision": round(tp / (tp + fp), 4) if tp + fp else None,
                "recall": round(tp / (tp + fn), 4) if tp + fn else None,
                "f1": round(2 * tp / (2 * tp + fp + fn), 4) if tp else 0.0,
                "net_bias_pred_minus_support": int(ss.sum() - ts.sum()),
            })
        out[tag] = rows
    return out


def nan_patterns() -> dict:
    a = json.load(open(HARD / "h3_retention_2026-08-25.json"))
    b = json.load(open(OUT_DIR / f"h3v2_retention_{STAMP}.json"))
    out = {}
    for slc in ("eval_only_all_rows", "pooled_all_rows"):
        A = pd.DataFrame(a["retention_tables"][slc]).set_index("feature")
        B = pd.DataFrame(b["retention_tables"][slc]).set_index("feature")
        rows = []
        for f in B.index:
            rows.append({
                "feature": f,
                "v11_n_both": int(A.loc[f, "n_both_defined"]),
                "v12_n_both": int(B.loc[f, "n_both_defined"]),
                "v11_teacher_only": int(A.loc[f, "n_teacher_only_defined"]),
                "v12_teacher_only": int(B.loc[f, "n_teacher_only_defined"]),
                "v11_student_only": int(A.loc[f, "n_student_only_defined"]),
                "v12_student_only": int(B.loc[f, "n_student_only_defined"]),
            })
        out[slc] = rows
    return out


def main() -> None:
    print("[V5] rebuilding H3's v1.1 arm through the H3v2 code path ...")
    v5 = v5_wrapper_reproduces_h3()
    for k, v in v5["measured"].items():
        print(f"  {k:44s} measured {v:.4f}  ledger {H3_RULED_EVAL[k]:.3f}  "
              f"ledger_ok={v5['matches_ledger_within_half_ulp_of_3dp'][k]}  "
              f"exact_vs_h3_json={v5['matches_h3_machine_record_exactly'][k]}")
    print(f"[V5] matches H3 ledger (3dp): {v5['all_match_ledger']}   "
          f"matches H3 machine record exactly: {v5['all_match_machine_record']}")

    print("\n[X] 2x2 cross-pairing ...")
    x = cross_pairing()
    for k in sorted(x):
        v = x[k]
        print(f"  {k:46s} rf12={v['redflag_12_mean']:.4f}  negshare={v['sentiment_negative_share']:.4f} "
              f" mean_score={v['sentiment_mean_score']:.4f}  press={v['redflag_any_rate_press']:.4f}")

    print("\n[M] chunk-level per-section mechanism ...")
    m = chunk_mechanism()
    A = pd.DataFrame(m["v1.1"]).set_index(["section_type", "category"])
    B = pd.DataFrame(m["v1.2"]).set_index(["section_type", "category"])
    cmp = pd.DataFrame({
        "v11_sup": A["support"], "v12_sup": B["support"],
        "v11_pred": A["predicted"], "v12_pred": B["predicted"],
        "v11_bias": A["net_bias_pred_minus_support"], "v12_bias": B["net_bias_pred_minus_support"],
        "v11_rec": A["recall"], "v12_rec": B["recall"],
        "v11_prec": A["precision"], "v12_prec": B["precision"],
        "v11_f1": A["f1"], "v12_f1": B["f1"],
    })
    print(cmp.to_string())

    payload = {
        "generated_utc": pd.Timestamp.utcnow().isoformat(),
        "purpose": "H3v2 §3 -- evaluation-bug hunt before reporting the v1.2 retention numbers",
        "V5_wrapper_reproduces_H3_ruled_v11_values": v5,
        "X_cross_pairing_2x2": x,
        "M_chunk_level_eval_per_section": m,
        "NAN_patterns": nan_patterns(),
    }
    out = OUT_DIR / f"h3v2_diagnostics_{STAMP}.json"
    out.write_text(json.dumps(payload, indent=1, default=str))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
