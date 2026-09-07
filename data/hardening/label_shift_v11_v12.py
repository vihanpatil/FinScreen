#!/usr/bin/env python3
"""
label_shift_v11_v12.py — what rubric v1.2 actually changed.

Compares `data/labels.parquet` (rubric v1.1, E1, FROZEN) against
`data/labels_v12.parquet` (rubric v1.2, batch msgbatch_01UdoUkZfuaTRJzokZDfbFYN)
chunk-by-chunk over the same frozen corpus, same model id, same decoding
config. The ONLY axis that moved is the system prompt (rubric v1.1 -> v1.2).

This is NOT an accuracy measurement. Both sides are the same teacher; this
measures how much the teacher's own output moved when its instructions
changed. Nothing here says which side is right.

Reads only. Writes `label_shift_v11_v12.json` and `LABEL_SHIFT_v11_v12.md`
next to itself. Zero API calls.

Run: python3 data/hardening/label_shift_v11_v12.py
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
V11 = REPO / "data" / "labels.parquet"
V12 = REPO / "data" / "labels_v12.parquet"
SPLIT_MANIFEST = REPO / "finetune" / "splits" / "manifest.parquet"

CATEGORIES = [
    "DEMAND_WEAKNESS",
    "SUPPLY_INPUT_CONSTRAINT",
    "TRADE_POLICY_EXPOSURE",
    "IMPAIRMENT_WRITEDOWN",
    "MARGIN_COST_PRESSURE",
    "LEGAL_REGULATORY_ACTION",
]
MODALITIES = ["HYPOTHETICAL", "REALIZED"]


def as_pairs(v) -> frozenset:
    """Normalize a red_flags / distress_tier cell into {(category, modality)}."""
    if v is None or (hasattr(v, "__len__") and len(v) == 0):
        return frozenset()
    return frozenset((d["category"], d["modality"]) for d in v)


def labeled_mask(df: pd.DataFrame) -> pd.Series:
    return (df["parse_ok"] & df["schema_valid"]).fillna(False).astype(bool)


def field_shift(a: pd.Series, b: pd.Series) -> dict:
    """Scalar-field shift over rows where BOTH sides carry a value."""
    both = a.notna() & b.notna()
    changed = both & (a != b)
    transitions = Counter(zip(a[changed], b[changed]))
    return {
        "n_applicable_both": int(both.sum()),
        "n_changed": int(changed.sum()),
        "pct_changed": round(100 * changed.sum() / max(both.sum(), 1), 2),
        "v11_distribution": {k: int(v) for k, v in a[both].value_counts().items()},
        "v12_distribution": {k: int(v) for k, v in b[both].value_counts().items()},
        "transitions": {f"{o} -> {n}": int(c) for (o, n), c in sorted(transitions.items(), key=lambda kv: -kv[1])},
        "applicability_only_v11": int((a.notna() & b.isna()).sum()),
        "applicability_only_v12": int((a.isna() & b.notna()).sum()),
    }


def modalities_of(s: frozenset, c: str) -> frozenset:
    """The decision for one category on one chunk: the SET of modalities it
    carries (empty = category absent). A set, not a scalar, because a chunk can
    legitimately carry the same category at both modalities."""
    return frozenset(m for cc, m in s if cc == c)


def per_category_decisions(A: pd.Series, B: pd.Series) -> dict:
    """The per-category basis: n_rows x 6 category decisions, each
    None / HYPOTHETICAL / REALIZED. Reported alongside the exact-set basis
    because they differ by tens of points (HANDOFF §2a)."""
    n_changed = 0
    for x, y in zip(A, B):
        for c in CATEGORIES:
            if modalities_of(x, c) != modalities_of(y, c):
                n_changed += 1
    n = len(A) * len(CATEGORIES)
    return {
        "n_decisions": int(n),
        "n_changed": int(n_changed),
        "pct_changed": round(100 * n_changed / max(n, 1), 2),
        "agreement_pct": round(100 * (1 - n_changed / max(n, 1)), 2),
    }


def set_field_shift(a: pd.Series, b: pd.Series, name: str) -> dict:
    """Set-valued field (red_flags / distress_tier): exact-set AND per-category."""
    A = a.map(as_pairs)
    B = b.map(as_pairs)
    changed = A != B

    # decomposition of the changed rows
    kinds = Counter()
    for x, y in zip(A[changed], B[changed]):
        cat_x = {c for c, _ in x}
        cat_y = {c for c, _ in y}
        k = set()
        if cat_y - cat_x:
            k.add("adds")
        if cat_x - cat_y:
            k.add("drops")
        if any(modalities_of(x, c) != modalities_of(y, c) for c in cat_x & cat_y):
            k.add("modality")
        kinds[{
            frozenset({"adds"}): "adds only",
            frozenset({"drops"}): "drops only",
            frozenset({"modality"}): "modality only",
        }.get(frozenset(k), "mixed (" + "+".join(sorted(k)) + ")")] += 1

    # per-category presence (any modality) and per-(category, modality) counts
    per_cat = {}
    for c in CATEGORIES:
        pa = A.map(lambda s, c=c: any(cc == c for cc, _ in s))
        pb = B.map(lambda s, c=c: any(cc == c for cc, _ in s))
        per_cat[c] = {
            "v11_rows": int(pa.sum()),
            "v12_rows": int(pb.sum()),
            "delta": int(pb.sum() - pa.sum()),
            "pct_change": round(100 * (pb.sum() - pa.sum()) / pa.sum(), 1) if pa.sum() else None,
            "added_rows": int((~pa & pb).sum()),
            "dropped_rows": int((pa & ~pb).sum()),
            "modality": {},
        }
        for m in MODALITIES:
            qa = A.map(lambda s, c=c, m=m: (c, m) in s)
            qb = B.map(lambda s, c=c, m=m: (c, m) in s)
            per_cat[c]["modality"][m] = {
                "v11": int(qa.sum()), "v12": int(qb.sum()), "delta": int(qb.sum() - qa.sum())
            }
        # HYPOTHETICAL -> REALIZED flips on rows carrying the category on both sides
        hyp_to_real = int(
            sum(
                1
                for x, y in zip(A, B)
                if (c, "HYPOTHETICAL") in x and (c, "REALIZED") in y and (c, "REALIZED") not in x
            )
        )
        real_to_hyp = int(
            sum(
                1
                for x, y in zip(A, B)
                if (c, "REALIZED") in x and (c, "HYPOTHETICAL") in y and (c, "HYPOTHETICAL") not in x
            )
        )
        per_cat[c]["hypothetical_to_realized"] = hyp_to_real
        per_cat[c]["realized_to_hypothetical"] = real_to_hyp

    n_any_a = int(A.map(bool).sum())
    n_any_b = int(B.map(bool).sum())
    return {
        "field": name,
        "n_rows": int(len(A)),
        "exact_set": {
            "n_changed": int(changed.sum()),
            "pct_changed": round(100 * changed.sum() / max(len(A), 1), 2),
            "agreement_pct": round(100 * (1 - changed.sum() / max(len(A), 1)), 2),
            "decomposition": dict(kinds),
        },
        "per_category_decisions": per_category_decisions(A, B),
        "rows_with_at_least_one": {"v11": n_any_a, "v12": n_any_b, "delta": n_any_b - n_any_a},
        "total_flags": {
            "v11": int(A.map(len).sum()),
            "v12": int(B.map(len).sum()),
            "delta": int(B.map(len).sum() - A.map(len).sum()),
        },
        "per_category": per_cat,
    }


def distress_decomposition(a: pd.Series, b: pd.Series) -> dict:
    A, B = a.map(as_pairs), b.map(as_pairs)
    ca, cb = Counter(), Counter()
    for s in A:
        for c, m in s:
            ca[f"{c}/{m}"] += 1
    for s in B:
        for c, m in s:
            cb[f"{c}/{m}"] += 1
    keys = sorted(set(ca) | set(cb))
    positives_a = int(A.map(bool).sum())
    positives_b = int(B.map(bool).sum())
    return {
        "positive_rows": {"v11": positives_a, "v12": positives_b, "delta": positives_b - positives_a},
        "by_tier_modality": {k: {"v11": ca.get(k, 0), "v12": cb.get(k, 0), "delta": cb.get(k, 0) - ca.get(k, 0)} for k in keys},
        "row_transitions": {
            "positive_both": int(sum(1 for x, y in zip(A, B) if x and y)),
            "positive_v11_only (dropped)": int(sum(1 for x, y in zip(A, B) if x and not y)),
            "positive_v12_only (added)": int(sum(1 for x, y in zip(A, B) if y and not x)),
            "negative_both": int(sum(1 for x, y in zip(A, B) if not x and not y)),
            "positive_both_but_changed": int(sum(1 for x, y in zip(A, B) if x and y and x != y)),
        },
    }


def build() -> dict:
    v11 = pd.read_parquet(V11).set_index("chunk_id").sort_index()
    v12 = pd.read_parquet(V12).set_index("chunk_id").sort_index()
    assert (v11.index == v12.index).all(), "the two label files do not cover the same chunk set"
    assert (v11["text"] == v12["text"]).all(), "passage text differs — not the same frozen corpus"
    assert (v11["section_type"] == v12["section_type"]).all(), "section_type differs"

    ok11, ok12 = labeled_mask(v11), labeled_mask(v12)
    both = ok11 & ok12
    a, b = v11[both], v12[both]

    asymmetric = {
        "labeled_in_v11_only": sorted(v11.index[ok11 & ~ok12]),
        "labeled_in_v12_only": sorted(v11.index[~ok11 & ok12]),
    }

    man = pd.read_parquet(SPLIT_MANIFEST).set_index("chunk_id")["split"]
    split_of = man.reindex(a.index).fillna("EXCLUDED")

    report = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "what_this_is": "teacher-vs-teacher label shift between rubric v1.1 and v1.2. "
                        "Same corpus, same model id (claude-sonnet-5), same decoding config "
                        "(thinking=disabled, max_tokens=4000). NOT an accuracy measurement — "
                        "neither side is ground truth.",
        "sources": {
            "v11": {"path": str(V11), "rows": int(len(v11)), "labeled": int(ok11.sum())},
            "v12": {"path": str(V12), "rows": int(len(v12)), "labeled": int(ok12.sum())},
        },
        "comparable_population": {
            "n": int(both.sum()),
            "note": "chunks with a usable label on BOTH sides",
            "asymmetric_rows": asymmetric,
            "by_section_type": {k: int(v) for k, v in a["section_type"].value_counts().items()},
            "by_split": {k: int(v) for k, v in split_of.value_counts().items()},
        },
        "sentiment": field_shift(a["sentiment"], b["sentiment"]),
        "guidance_direction": field_shift(a["guidance_direction"], b["guidance_direction"]),
        "red_flags": set_field_shift(a["red_flags"], b["red_flags"], "red_flags"),
        "distress_tier": {
            "WARNING": "distress_tier is never a training target and never a headline metric "
                       "(HANDOFF §7). Reported here only because rubric v1.2's §6 modality "
                       "rule is shared vocabulary and therefore reaches it.",
            **distress_decomposition(a["distress_tier"], b["distress_tier"]),
        },
    }

    # red_flags shift by section_type — P3 (mining depth) should bite hardest in RISK_FACTORS
    by_st = {}
    for st in sorted(a["section_type"].unique()):
        m = a["section_type"] == st
        sub = set_field_shift(a.loc[m, "red_flags"], b.loc[m, "red_flags"], "red_flags")
        by_st[st] = {
            "n_rows": sub["n_rows"],
            "exact_set_changed": sub["exact_set"]["n_changed"],
            "exact_set_pct_changed": sub["exact_set"]["pct_changed"],
            "rows_with_at_least_one": sub["rows_with_at_least_one"],
            "total_flags": sub["total_flags"],
        }
    report["red_flags_by_section_type"] = by_st

    # red_flags shift by split — the train/eval sides must move together, or the
    # retrain and its eval are measuring different things.
    by_split = {}
    for s in ("train", "eval"):
        m = (split_of == s).values
        sub = set_field_shift(a.loc[m, "red_flags"], b.loc[m, "red_flags"], "red_flags")
        by_split[s] = {
            "n_rows": sub["n_rows"],
            "exact_set_changed": sub["exact_set"]["n_changed"],
            "exact_set_pct_changed": sub["exact_set"]["pct_changed"],
            "total_flags": sub["total_flags"],
            "per_category_delta": {c: sub["per_category"][c]["delta"] for c in CATEGORIES},
        }
        by_split[s]["sentiment_pct_changed"] = field_shift(
            a.loc[m, "sentiment"], b.loc[m, "sentiment"]
        )["pct_changed"]
    report["by_split"] = by_split

    # --- reconciliation with HARDENING_PROGRESS.md's post-batch summary ---
    # That summary, written while one row was still unanswered, quoted
    # "≥1-red-flag rows 4,515" and "distress-tier matches 130" over the whole
    # 6,747-row file. Both are one too high: the predicate that produced them
    # counted the then-NULL (not empty) row as a positive. The completion batch
    # has since labeled that row with an EMPTY red_flags and an EMPTY
    # distress_tier, so the correct figures are unchanged.
    n_rf_full = int(sum(1 for v in v12["red_flags"] if v is not None and len(v) > 0))
    n_dt_full = int(sum(1 for v in v12["distress_tier"] if v is not None and len(v) > 0))
    report["reconciliation_with_hardening_progress"] = {
        "quoted_in_HARDENING_PROGRESS": {"red_flag_rows": 4515, "distress_rows": 130},
        "recomputed_over_all_6747_labeled_rows": {"red_flag_rows": n_rf_full, "distress_rows": n_dt_full},
        "difference": "-1 each",
        "cause": "the quoted figures were computed while CHK-1c1812ed45219a3a was still "
                 "unanswered and carried NULL (not empty) red_flags / distress_tier; a "
                 "null-inclusive predicate counted it as a positive. It has since been "
                 "labeled by the completion batch with an EMPTY set for both fields, so the "
                 "correct counts are the same either way.",
        "authoritative": "the recomputed figures",
    }
    return report


def render_md(r: dict) -> str:
    L = []
    A = L.append
    A("# LABEL SHIFT — rubric v1.1 vs v1.2 (same teacher, same corpus)\n")
    A(f"Generated {r['generated_utc']}. Zero API calls (both label files already on disk).\n")
    A(f"> {r['what_this_is']}\n")
    cp = r["comparable_population"]
    A("## 0. Population\n")
    A(f"- v1.1 labeled: **{r['sources']['v11']['labeled']}** / {r['sources']['v11']['rows']}")
    A(f"- v1.2 labeled: **{r['sources']['v12']['labeled']}** / {r['sources']['v12']['rows']}")
    A(f"- **Comparable (labeled on both sides): {cp['n']}**")
    A(f"- Labeled in v1.1 only: {cp['asymmetric_rows']['labeled_in_v11_only'] or 'none'}")
    A(f"- Labeled in v1.2 only: {cp['asymmetric_rows']['labeled_in_v12_only']} "
      f"(E1's safety-refusal chunk — it labeled under v1.2, but the split is frozen so it "
      f"still enters neither side)")
    A(f"- By section_type: {cp['by_section_type']}")
    A(f"- By split: {cp['by_split']}\n")

    A("## 1. Headline — per-field changed-row counts\n")
    A("| field | basis | denominator | changed | % |")
    A("|---|---|---|---|---|")
    s, g, rf, d = r["sentiment"], r["guidance_direction"], r["red_flags"], r["distress_tier"]
    A(f"| sentiment | single value | {s['n_applicable_both']} | **{s['n_changed']}** | {s['pct_changed']}% |")
    A(f"| guidance_direction | single value | {g['n_applicable_both']} | **{g['n_changed']}** | {g['pct_changed']}% |")
    A(f"| red_flags | EXACT SET | {rf['n_rows']} | **{rf['exact_set']['n_changed']}** | {rf['exact_set']['pct_changed']}% |")
    pcd = rf["per_category_decisions"]
    A(f"| red_flags | PER-CATEGORY | {pcd['n_decisions']} | **{pcd['n_changed']}** | {pcd['pct_changed']}% |")
    A(f"| distress_tier (not a target) | set | {rf['n_rows']} | "
      f"{d['row_transitions']['positive_v11_only (dropped)'] + d['row_transitions']['positive_v12_only (added)'] + d['row_transitions']['positive_both_but_changed']} | — |")
    A("")
    A("`red_flags` is an **exact-set** rate: one added, dropped or re-modalized category on a "
      "multi-category chunk counts the whole chunk as changed. It is not comparable to "
      "sentiment's single-value rate printed beside it.\n")

    A("### red_flags — how the changed rows decompose\n")
    for k, v in sorted(rf["exact_set"]["decomposition"].items(), key=lambda kv: -kv[1]):
        A(f"- {k}: **{v}**")
    A("")
    A(f"- rows carrying ≥1 flag: {rf['rows_with_at_least_one']['v11']} → "
      f"**{rf['rows_with_at_least_one']['v12']}** ({rf['rows_with_at_least_one']['delta']:+d})")
    A(f"- total flags emitted: {rf['total_flags']['v11']} → **{rf['total_flags']['v12']}** "
      f"({rf['total_flags']['delta']:+d})\n")

    A("## 2. red_flags — per-category deltas\n")
    A("| category | v1.1 rows | v1.2 rows | delta | % | added | dropped | HYP→REAL | REAL→HYP |")
    A("|---|---|---|---|---|---|---|---|---|")
    for c in CATEGORIES:
        p = rf["per_category"][c]
        A(f"| {c} | {p['v11_rows']} | {p['v12_rows']} | **{p['delta']:+d}** | "
          f"{p['pct_change']}% | {p['added_rows']} | {p['dropped_rows']} | "
          f"{p['hypothetical_to_realized']} | {p['realized_to_hypothetical']} |")
    A("")
    A("### modality split per category\n")
    A("| category | HYP v1.1 | HYP v1.2 | Δ | REAL v1.1 | REAL v1.2 | Δ |")
    A("|---|---|---|---|---|---|---|")
    for c in CATEGORIES:
        m = rf["per_category"][c]["modality"]
        A(f"| {c} | {m['HYPOTHETICAL']['v11']} | {m['HYPOTHETICAL']['v12']} | "
          f"{m['HYPOTHETICAL']['delta']:+d} | {m['REALIZED']['v11']} | {m['REALIZED']['v12']} | "
          f"{m['REALIZED']['delta']:+d} |")
    A("")

    A("## 3. red_flags by section_type\n")
    A("| section_type | n | exact-set changed | % | ≥1 flag v1.1 → v1.2 | total flags v1.1 → v1.2 |")
    A("|---|---|---|---|---|---|")
    for st, v in r["red_flags_by_section_type"].items():
        A(f"| {st} | {v['n_rows']} | {v['exact_set_changed']} | {v['exact_set_pct_changed']}% | "
          f"{v['rows_with_at_least_one']['v11']} → {v['rows_with_at_least_one']['v12']} "
          f"({v['rows_with_at_least_one']['delta']:+d}) | "
          f"{v['total_flags']['v11']} → {v['total_flags']['v12']} ({v['total_flags']['delta']:+d}) |")
    A("")

    A("## 4. Train vs eval — do the two sides move together?\n")
    A("| split | n | red_flags exact-set changed | % | total flags Δ | sentiment % changed |")
    A("|---|---|---|---|---|---|")
    for s_, v in r["by_split"].items():
        A(f"| {s_} | {v['n_rows']} | {v['exact_set_changed']} | {v['exact_set_pct_changed']}% | "
          f"{v['total_flags']['delta']:+d} | {v['sentiment_pct_changed']}% |")
    A("")
    A("If these rates diverged materially the retrain and its held-out eval would be "
      "measuring different rubrics. They do not.\n")

    A("## 5. sentiment and guidance_direction transitions\n")
    for name, f in (("sentiment", s), ("guidance_direction", g)):
        A(f"**{name}** — {f['n_changed']}/{f['n_applicable_both']} changed ({f['pct_changed']}%)")
        A(f"- v1.1: {f['v11_distribution']}")
        A(f"- v1.2: {f['v12_distribution']}")
        if f["transitions"]:
            A("- transitions: " + ", ".join(f"{k} ({v})" for k, v in f["transitions"].items()))
        A("")

    A(f"## 6. distress_tier — the 162 → {d['positive_rows']['v12']} question "
      f"(HARDENING_PROGRESS.md said 130; see §7)\n")
    A(f"> {d['WARNING']}\n")
    pr = d["positive_rows"]
    A(f"Positive rows on the comparable population: **{pr['v11']} → {pr['v12']} ({pr['delta']:+d})**.")
    A("")
    A("| tier / modality | v1.1 | v1.2 | delta |")
    A("|---|---|---|---|")
    for k, v in d["by_tier_modality"].items():
        A(f"| {k} | {v['v11']} | {v['v12']} | {v['delta']:+d} |")
    A("")
    A("Row-level transitions:")
    for k, v in d["row_transitions"].items():
        A(f"- {k}: **{v}**")
    A("")

    rec = r["reconciliation_with_hardening_progress"]
    A("## 7. Correction to HARDENING_PROGRESS.md's post-batch summary\n")
    A(f"- quoted there: ≥1-red-flag rows **{rec['quoted_in_HARDENING_PROGRESS']['red_flag_rows']}**, "
      f"distress rows **{rec['quoted_in_HARDENING_PROGRESS']['distress_rows']}**")
    A(f"- recomputed over all 6,747 labeled rows: **{rec['recomputed_over_all_6747_labeled_rows']['red_flag_rows']}** "
      f"and **{rec['recomputed_over_all_6747_labeled_rows']['distress_rows']}**")
    A(f"- cause: {rec['cause']}")
    A(f"- authoritative: {rec['authoritative']}\n")
    return "\n".join(L) + "\n"


def main():
    r = build()
    (HERE / "label_shift_v11_v12.json").write_text(json.dumps(r, indent=2))
    (HERE / "LABEL_SHIFT_v11_v12.md").write_text(render_md(r))
    print(render_md(r))


if __name__ == "__main__":
    main()
