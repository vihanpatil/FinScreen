"""
analyze_v12.py — THE PRE-REGISTERED ANALYSIS for the v1.2 teacher spot-check.

Written 2026-08-27, BEFORE any rater verdict exists. This file IS the
pre-registration: the estimators, the Wilson convention, the unsure rule,
the kill-threshold arithmetic and the seeded owner-probe draw are all fixed
here in code so that no degree of freedom is chosen after seeing results.
Design prose: SPOTCHECK_v12_design.md (same directory).

Inputs (all under data/hardening/spotcheck_v12/):
  draw_v12.csv                    the 200-row draw (label-free)
  verdicts/rater_a.json           blind rater A over all 200:
                                  [{chunk_id, red_flags:[[CAT,MOD],...], reason}]
  verdicts/rater_b_batch01.json   OPTIONAL replicate over batch 1 (S7)
  adjudications/adjudications.json OPTIONAL, contested rows:
                                  [{chunk_id, verdict:"agree|disagree|unsure",
                                    correct_label:[[CAT,MOD],...]|null,
                                    confidence, brief, pattern, needs_human}]
  owner_rulings.json              OPTIONAL, supersedes adjudications:
                                  [{chunk_id, verdict, correct_label, note}]
  probe_rulings.json              OPTIONAL, the 20-row uncontested probe:
                                  [{chunk_id, verdict:"agree|disagree", note}]

Stored labels are joined here from data/labels_v12.parquet — they are never
written into any rater-visible file.

Output: results_v12.json + a printed report. Zero network, zero API.

PROVENANCE RULE (HANDOFF §3/§7): every rate produced here is model-consensus
agreement with owner rulings on the escalated subset. It is NOT human
validation of ground truth. Because both raters are the same model family,
shared bias is invisible to this design, so the measured error is plausibly
biased LOW — which matters for the kill rule: failing to trigger demotion is
not evidence the teacher is fine.
"""

import json
from math import sqrt
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/vihanpatil/personal/projects/FinScreen")
DIR = ROOT / "data" / "hardening" / "spotcheck_v12"
LABELS = ROOT / "data" / "labels_v12.parquet"
LABELS_V11 = ROOT / "data" / "labels.parquet"

Z = 1.96
KILL_THRESHOLD = 0.35          # advisory §7 item 1
PROBE_N = 20                   # S8 owner probe of the uncontested set
PROBE_SEED = 20260827
PROBE_ESCALATION_K = 2         # >= this many overturns -> pre-committed extension
BOOT = 10000
BOOT_SEED = 20260827
CATS = ["DEMAND_WEAKNESS", "SUPPLY_INPUT_CONSTRAINT", "TRADE_POLICY_EXPOSURE",
        "IMPAIRMENT_WRITEDOWN", "MARGIN_COST_PRESSURE", "LEGAL_REGULATORY_ACTION"]

# v1.1 comparison row (RED_FLAGS_LIMITATION.md, Tier C = the only
# base-rate-representative slice of the 2026-08-18 pass). DESCRIPTIVE ONLY:
# different rubric, different reference labels.
V11_TIERC_K, V11_TIERC_N = 9, 36


# ---------------------------------------------------------------- helpers
def wilson(k, n, z=Z):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def newcombe(k1, n1, k2, n2):
    """Newcombe hybrid-score CI for p1 - p2 (independent samples)."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    return (p1 - p2 - sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2),
            p1 - p2 + sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2))


def kstar(n, threshold=KILL_THRESHOLD):
    """Smallest error count whose Wilson LOWER bound is strictly > threshold."""
    for k in range(n + 1):
        if wilson(k, n)[0] > threshold:
            return k
    return None


def as_set(pairs):
    if pairs is None:
        return None
    if isinstance(pairs, np.ndarray):
        return frozenset((e["category"], e["modality"]) for e in pairs)
    return frozenset((c, m) for c, m in pairs)


def load(name, default=None):
    p = DIR / name
    if not p.exists():
        return default
    return json.loads(p.read_text())


def fmt(k, n):
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k/n:6.2%}  [{lo:6.2%}, {hi:6.2%}]  (+-{(hi-lo)/2:.2%})"


# ---------------------------------------------------------------- main
def main():
    draw = pd.read_csv(DIR / "draw_v12.csv")
    lab = pd.read_parquet(LABELS, columns=["chunk_id", "red_flags"])
    v11 = pd.read_parquet(LABELS_V11, columns=["chunk_id", "red_flags"])
    stored = {r.chunk_id: as_set(r.red_flags) for r in lab.itertuples()}
    prior = {r.chunk_id: as_set(r.red_flags) for r in v11.itertuples()}

    rater_a = {r["chunk_id"]: as_set(r["red_flags"]) for r in load("verdicts/rater_a.json", [])}
    adj = {r["chunk_id"]: r for r in load("adjudications/adjudications.json", [])}
    owner = {r["chunk_id"]: r for r in load("owner_rulings.json", [])}
    probe = {r["chunk_id"]: r for r in load("probe_rulings.json", [])}
    rep_b = {r["chunk_id"]: as_set(r["red_flags"]) for r in load("verdicts/rater_b_batch01.json", [])}

    ids = list(draw.chunk_id)
    missing = [c for c in ids if c not in rater_a]
    if missing:
        print(f"[WARN] rater A has not rated {len(missing)} of {len(ids)} chunks "
              f"— analysis runs on what exists and restates n.")

    rows = []
    for c in ids:
        if c not in rater_a:
            continue
        s, a = stored[c], rater_a[c]
        contested = (s != a)
        ruling = owner.get(c) or adj.get(c)
        if not contested:
            err, basis, ref = 0, "uncontested", s
        elif ruling is None:
            err, basis, ref = None, "contested-unadjudicated", None
        elif ruling["verdict"] == "disagree":
            err, basis = 1, "owner" if c in owner else "adjudicator"
            ref = as_set(ruling.get("correct_label"))
        elif ruling["verdict"] == "agree":
            err, basis, ref = 0, "owner" if c in owner else "adjudicator", s
        else:                                   # "unsure"
            err, basis, ref = None, "unsure", None
        rows.append(dict(chunk_id=c, err=err, basis=basis, stored=s, rater=a,
                         ref=ref, contested=contested))

    d = pd.DataFrame(rows).merge(draw, on="chunk_id")
    d["changed_v11"] = [stored[c] != prior.get(c) for c in d.chunk_id]

    ev = d[d.err.notna()].copy()
    n_ev, k_ev = len(ev), int(ev.err.sum())
    out = {"provenance": "model-consensus + owner rulings on the escalated "
                         "subset; NOT human validation of ground truth",
           "n_drawn": len(draw), "n_rated": len(d), "n_evaluable": n_ev,
           "n_nonevaluable": len(d) - n_ev,
           "nonevaluable_reasons": d[d.err.isna()].basis.value_counts().to_dict()}

    # ---------- P1 PRIMARY: exact-set (category+modality) error ----------
    lo, hi = wilson(k_ev, n_ev) if n_ev else (float("nan"),) * 2
    ks = kstar(n_ev) if n_ev else None
    out["P1_exact_set_error"] = {
        "k": k_ev, "n": n_ev, "point": k_ev / n_ev if n_ev else None,
        "wilson_95": [lo, hi],
        "kstar_for_demotion": ks,
        "phat_star": ks / n_ev if ks else None,
        "demote": bool(lo > KILL_THRESHOLD) if n_ev else None,
        "rule": "demote iff Wilson lower bound STRICTLY > 0.35 (boundary "
                "equality does NOT demote)",
    }
    # sensitivity bounds on the non-evaluable rows
    n_all = len(d)
    out["P1_nonevaluable_bounds"] = {
        "all_nonevaluable_as_error": wilson(k_ev + (n_all - n_ev), n_all),
        "all_nonevaluable_as_agree": wilson(k_ev, n_all),
    }

    # ---------- S1: category-set only (modality ignored) ----------
    s1 = ev[ev.ref.notna()].copy()
    cat_only = [(frozenset(c for c, _ in r.stored) != frozenset(c for c, _ in r.ref))
                for r in s1.itertuples()]
    out["S1_category_set_error"] = {
        "k": int(sum(cat_only)), "n": len(s1),
        "wilson_95": wilson(int(sum(cat_only)), len(s1)) if len(s1) else None,
        "note": "P1 minus S1 is the share of exact-set error that is modality-only",
    }

    # ---------- S2: per-category-decision error, chunk-clustered ----------
    per_chunk = []
    for r in s1.itertuples():
        wrong = sum(1 for c in CATS
                    if ({m for cc, m in r.stored if cc == c}
                        != {m for cc, m in r.ref if cc == c}))
        per_chunk.append(wrong)
    per_chunk = np.array(per_chunk)
    n_dec = len(per_chunk) * len(CATS)
    k_dec = int(per_chunk.sum())
    rng = np.random.default_rng(BOOT_SEED)
    if len(per_chunk):
        idx = rng.integers(0, len(per_chunk), size=(BOOT, len(per_chunk)))
        boot = per_chunk[idx].sum(axis=1) / n_dec
        cl = [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]
    else:
        cl = None
    out["S2_per_category_decision_error"] = {
        "k": k_dec, "n_decisions": n_dec,
        "point": k_dec / n_dec if n_dec else None,
        "cluster_bootstrap_95": cl,
        "naive_binomial_95_ANTICONSERVATIVE": wilson(k_dec, n_dec) if n_dec else None,
        "note": "the 6 category decisions inside a chunk are not independent; "
                "the cluster bootstrap (resampling chunks) is the honest "
                "interval. v1.1's 7.5% [91.4, 93.5] was the naive one.",
    }

    # ---------- S3: per-section ----------
    out["S3_by_section"] = {
        s: {"k": int(g.err.sum()), "n": len(g),
            "point": g.err.mean(), "wilson_95": wilson(int(g.err.sum()), len(g))}
        for s, g in ev.groupby("section_type")}

    # ---------- S4: per-category error, both bases ----------
    s4 = {}
    for c in CATS:
        st = s1[[c in {cc for cc, _ in r} for r in s1.stored]]
        rf = s1[[c in {cc for cc, _ in r} for r in s1.ref]]
        def rate(sub):
            if not len(sub):
                return {"k": 0, "n": 0, "point": None, "wilson_95": None}
            k = int(sum(({m for cc, m in r.stored if cc == c}
                         != {m for cc, m in r.ref if cc == c})
                        for r in sub.itertuples()))
            return {"k": k, "n": len(sub), "point": k / len(sub),
                    "wilson_95": wilson(k, len(sub))}
        s4[c] = {"stored_present_base": rate(st), "reference_present_base": rate(rf)}
    out["S4_per_category"] = s4

    # ---------- S5: v1.1->v1.2 changed vs unchanged ----------
    out["S5_by_v11_change"] = {
        str(bool(v)): {"k": int(g.err.sum()), "n": len(g),
                       "point": g.err.mean(),
                       "wilson_95": wilson(int(g.err.sum()), len(g))}
        for v, g in ev.groupby("changed_v11")}

    # ---------- S6: error-mode decomposition (descriptive counts) ----------
    spurious = missed = modality = 0
    for r in s1.itertuples():
        if r.err != 1:
            continue
        sc = {c for c, _ in r.stored}
        rc = {c for c, _ in r.ref}
        spurious += len(sc - rc)
        missed += len(rc - sc)
        modality += sum(1 for c in sc & rc
                        if {m for cc, m in r.stored if cc == c}
                        != {m for cc, m in r.ref if cc == c})
    out["S6_error_modes"] = {"spurious_flags": spurious, "missed_flags": missed,
                             "wrong_modality": modality,
                             "note": "counts of category-level corrections on "
                                     "error rows; no CI (descriptive)"}

    # ---------- S7: rater-noise replicate (analysis only) ----------
    if rep_b:
        both = [c for c in rep_b if c in rater_a]
        agree = sum(1 for c in both if rater_a[c] == rep_b[c])
        out["S7_rater_replicate"] = {
            "n": len(both), "exact_set_agreement": agree / len(both) if both else None,
            "wilson_95": wilson(agree, len(both)) if both else None,
            "note": "rater A is the primary rater for all 200; this arm never "
                    "feeds P1. It bounds how much of P1 is rater noise."}

    # ---------- S8: seeded owner probe of the uncontested set ----------
    unc = sorted(d[(~d.contested)].chunk_id)
    prng = np.random.default_rng(PROBE_SEED)
    probe_ids = sorted(np.array(unc)[prng.choice(len(unc), size=min(PROBE_N, len(unc)),
                                                 replace=False)].tolist()) if unc else []
    (DIR / "probe_ids.json").write_text(json.dumps(probe_ids, indent=1))
    ruled = [c for c in probe_ids if c in probe]
    overturned = sum(1 for c in ruled if probe[c]["verdict"] == "disagree")
    out["S8_owner_probe"] = {
        "probe_ids_written_to": "probe_ids.json",
        "n_probe": len(probe_ids), "n_ruled": len(ruled),
        "overturned": overturned,
        "wilson_95_on_hidden_shared_error": wilson(overturned, len(ruled)) if ruled else None,
        "escalation_triggered": bool(overturned >= PROBE_ESCALATION_K) if ruled else None,
        "escalation_rule": f"if >= {PROBE_ESCALATION_K} of {PROBE_N} uncontested "
                           "rows are overturned, adjudicate ALL uncontested rows "
                           "ONCE and recompute P1. No re-draw, no n increase.",
    }

    # ---------- comparison row vs v1.1 Tier C (DESCRIPTIVE ONLY) ----------
    if n_ev:
        out["comparison_v11_tierC"] = {
            "v11_tierC": {"k": V11_TIERC_K, "n": V11_TIERC_N,
                          "point": V11_TIERC_K / V11_TIERC_N,
                          "wilson_95": wilson(V11_TIERC_K, V11_TIERC_N)},
            "v12": {"k": k_ev, "n": n_ev, "point": k_ev / n_ev,
                    "wilson_95": [lo, hi]},
            "difference_v12_minus_v11_newcombe_95":
                newcombe(k_ev, n_ev, V11_TIERC_K, V11_TIERC_N),
            "caveats": [
                "different rubrics: a v1.1 label judged under v1.1 vs a v1.2 "
                "label judged under v1.2 — the target moved, so this is NOT a "
                "test that the rubric repair worked",
                "different frames: v1.1 Tier C was drawn from the residual pool "
                "after the exhaustive A/B strata were removed; the frame-induced "
                "bias is +0.45 pts (design doc §5.3), inside its own +-13.7 pt CI",
                "different raters and adjudication rounds",
                "DESCRIPTIVE ONLY — no decision reads this row",
            ]}

    (DIR / "results_v12.json").write_text(json.dumps(out, indent=1, default=float))

    # ---------------------------------------------------------- printout
    print("=" * 72)
    print("v1.2 TEACHER SPOT-CHECK — pre-registered analysis")
    print("=" * 72)
    print(f"drawn {len(draw)} | rated {len(d)} | evaluable {n_ev} | "
          f"non-evaluable {len(d)-n_ev} {out['nonevaluable_reasons']}")
    if n_ev:
        print(f"\nP1 exact-set (category+modality) error: {fmt(k_ev, n_ev)}")
        print(f"   demote iff k >= {ks} (phat >= {ks/n_ev:.4f}); "
              f"observed k = {k_ev}  ->  DEMOTE = {lo > KILL_THRESHOLD}")
        print(f"S1 category-set-only error: "
              f"{fmt(out['S1_category_set_error']['k'], out['S1_category_set_error']['n'])}")
        print(f"S2 per-category-decision error: {k_dec}/{n_dec} = "
              f"{k_dec/n_dec:.2%}  cluster-boot 95% "
              f"[{cl[0]:.2%}, {cl[1]:.2%}]" if cl else "")
        print("\nS3 by section:")
        for s, v in out["S3_by_section"].items():
            print(f"   {s:20s} {fmt(v['k'], v['n'])}")
        print("\nS5 by v1.1->v1.2 change:")
        for s, v in out["S5_by_v11_change"].items():
            print(f"   changed={s:5s} {fmt(v['k'], v['n'])}")
        print(f"\nS6 error modes: {out['S6_error_modes']}")
    print(f"\nwrote {DIR/'results_v12.json'}")
    print("\nREAD THIS WITH EVERY NUMBER ABOVE: model-consensus agreement, not "
          "human ground truth; shared model bias is invisible here, so the "
          "estimate is plausibly biased LOW.")


if __name__ == "__main__":
    main()
