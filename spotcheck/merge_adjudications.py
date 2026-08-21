"""Merge label-adjudicator results: validate coverage, write provenance-tagged
outputs, build the owner's pattern-grouped shortlist, and assemble the
combined-judgments file for compute_agreement.py.

Usage: python3 merge_adjudications.py <workflow_output.json>

Writes:
  spotcheck/adjudicator_verdicts.json   - all model adjudications, provenance-stamped:
                                          199 field-cases across 174 contested chunks
  spotcheck/owner_shortlist.md          - a flat pattern-grouped decision list w/ briefs.
                                          SUPERSEDED by build_owner_shortlist.py, which
                                          writes the Part A/B/C shortlist actually used.
                                          Both were fully ruled 2026-08-18 - not pending.
  spotcheck/combined_judgments.csv      - full-400 provenance-tagged judgments. At the
                                          time this script runs, rows awaiting an owner
                                          ruling are left BLANK and never imputed; as of
                                          2026-08-18 none remain blank (source =
                                          model-auditor 1023 / model-adjudicator 95 /
                                          owner 104 = 1,222 judgments).
"""
import json
import sys
from collections import defaultdict

import pandas as pd

REPO = "/Users/vihanpatil/personal/projects/FinScreen"
FIELDS = ["sentiment", "guidance_direction", "red_flags", "distress_tier"]
HIGH_STAKES = [
    "CHK-20d940b1855c8068", "CHK-8153748ce0e68c39", "CHK-9d1f3820572c181c",
    "CHK-a787c4ef45504dd1", "CHK-ba3a1dcd71201c66", "CHK-c17d2149a239bbcd",
    "CHK-ce2710d1b304bea6", "CHK-d9f9c2729c76438b", "CHK-ed1212d8058db87d",
    "CHK-95a7cf23f319ee70", "CHK-d74facbd628dfc96",
]


def fmt_label(field, v):
    if field in ("sentiment", "guidance_direction"):
        return "(none)" if v is None else str(v)
    if v is None:
        return "(n/a)"
    if not v:
        return "(no flags)"
    pairs = [f"{p[0]}—{p[1]}" if isinstance(p, list) else f"{p['category']}—{p['modality']}" for p in v]
    return "; ".join(pairs)


def load_adjudications(path):
    """Accepts a workflow output JSON ({result:{adjudications:[...]}} or
    {adjudications:[...]}), a persisted adjudicator_verdicts*.json, or a
    workflow journal.jsonl (one result line per agent)."""
    if path.endswith(".jsonl"):
        adjs = {}
        for ln in open(path).read().strip().split("\n"):
            e = json.loads(ln)
            r = e.get("result")
            if isinstance(r, dict) and "adjudications" in r:
                for a in r["adjudications"]:
                    adjs[a["chunk_id"]] = a
        return adjs
    raw = json.load(open(path))
    result = raw.get("result", raw)
    return {a["chunk_id"]: a for a in result["adjudications"]}


def main(path):
    adjs = load_adjudications(path)

    sample = pd.read_parquet(f"{REPO}/spotcheck/sample_400.parquet").set_index("chunk_id", drop=False)
    auditor = {v["chunk_id"]: v for v in json.load(open(f"{REPO}/spotcheck/auditor_verdicts.json"))["verdicts"]}
    disagreements = json.load(open(f"{REPO}/spotcheck/auditor_disagreements.json"))["rows"]
    expected_ids = {r["chunk_id"] for r in disagreements}

    # ---- coverage validation ----
    missing = sorted(expected_ids - set(adjs))
    extra = sorted(set(adjs) - expected_ids)
    print(f"coverage: {len(set(adjs) & expected_ids)}/174 | missing={missing} | extra={extra}")
    field_mismatches = []
    for r in disagreements:
        cid = r["chunk_id"]
        if cid not in adjs:
            continue
        want = {f for f in FIELDS if r[f]["verdict"] in ("disagree", "unsure")}
        if cid in HIGH_STAKES:
            want.add("distress_tier")
        got = {f["field"] for f in adjs[cid]["fields"]}
        if want != got:
            field_mismatches.append((cid, sorted(want), sorted(got)))
    print(f"field-scope mismatches: {len(field_mismatches)}")
    for m in field_mismatches[:10]:
        print("  ", m)
    stakes_not_escalated = [c for c in HIGH_STAKES if c in adjs and not adjs[c]["needs_human"]]
    if stakes_not_escalated:
        print(f"WARNING: high-stakes chunks not marked needs_human (forcing): {stakes_not_escalated}")
        for c in stakes_not_escalated:
            adjs[c]["needs_human"] = True
            adjs[c].setdefault("needs_human_reason", "high-stakes distress chunk — owner adjudication mandatory per protocol")

    # ---- verdict/confidence stats ----
    stats = defaultdict(int)
    for a in adjs.values():
        for f in a["fields"]:
            stats[(f["field"], f["verdict"])] += 1
            stats[("confidence", f["confidence"])] += 1
    print("\nadjudicator verdicts (about the STORED label):")
    for fld in FIELDS:
        row = {v: stats.get((fld, v), 0) for v in ("agree", "disagree", "unsure")}
        if sum(row.values()):
            print(f"  {fld:20s} {row}")
    print("confidence:", {c: stats.get(("confidence", c), 0) for c in ("high", "medium", "low")})

    n_needs_human = sum(1 for a in adjs.values() if a["needs_human"])
    print(f"\nneeds_human chunks: {n_needs_human}")

    # ---- write adjudicator verdicts (provenance-stamped) ----
    with open(f"{REPO}/spotcheck/adjudicator_verdicts.json", "w") as f:
        json.dump({
            "provenance": "label-adjudicator (third-rater model) adjudications - MODEL verdicts, source=model-adjudicator, never the owner's judgment (HANDOFF §3 2026-08-18 delegation, §7 hard rule #1)",
            "adjudications": list(adjs.values()),
        }, f, indent=1)

    # ---- owner shortlist, grouped by pattern ----
    pattern_groups = defaultdict(list)   # pattern -> [(chunk_id, field_adj)]
    singletons = []
    for a in adjs.values():
        if not a["needs_human"]:
            continue
        for f in a["fields"]:
            key = f.get("pattern")
            if key:
                pattern_groups[key].append((a["chunk_id"], f, a))
            else:
                singletons.append((a["chunk_id"], f, a))

    lines = [
        "# Owner adjudication shortlist",
        "",
        "Every decision below is YOURS to make - the adjudicator's recommendation",
        "is a model opinion (source=model-adjudicator), shown so you can weigh it.",
        "Verdicts are about the STORED label: agree = stored is right / disagree =",
        "stored is wrong (correct label shown) / unsure = rubric underdetermines.",
        "Chunks sharing a pattern turn on the same question - one ruling covers all.",
        "",
    ]
    n_decisions = 0
    for pat in sorted(pattern_groups, key=lambda p: -len(pattern_groups[p])):
        members = pattern_groups[pat]
        n_decisions += 1
        lines.append(f"## Pattern: `{pat}` — {len(members)} chunk(s), one ruling")
        lead_cid, lead_f, lead_a = members[0]
        st = sample.loc[lead_cid]
        stored = fmt_label(lead_f["field"], None)
        lines.append(f"**Field:** {lead_f['field']} | **Chunks:** " + ", ".join(c for c, _, _ in members))
        lines.append("")
        lines.append(f"**Adjudicator:** {lead_f['verdict']} (confidence {lead_f['confidence']})"
                     + (f" — correct label: {fmt_label(lead_f['field'], lead_f.get('correct_label'))}" if lead_f["verdict"] == "disagree" else ""))
        lines.append(f"**Brief:** {lead_f['brief']}")
        if lead_a.get("needs_human_reason"):
            lines.append(f"**What you must weigh:** {lead_a['needs_human_reason']}")
        lines.append("")
        lines.append("**Your ruling:** [ ] agree  [ ] disagree (state label)  [ ] unsure")
        lines.append("")
    for cid, f, a in singletons:
        n_decisions += 1
        lines.append(f"## {cid} — {f['field']}")
        lines.append(f"**Adjudicator:** {f['verdict']} (confidence {f['confidence']})"
                     + (f" — correct label: {fmt_label(f['field'], f.get('correct_label'))}" if f["verdict"] == "disagree" else ""))
        lines.append(f"**Brief:** {f['brief']}")
        if a.get("needs_human_reason"):
            lines.append(f"**What you must weigh:** {a['needs_human_reason']}")
        lines.append("")
        lines.append("**Your ruling:** [ ] agree  [ ] disagree (state label)  [ ] unsure")
        lines.append("")
    lines.insert(6, f"**Total rulings needed: {n_decisions}** (covering {n_needs_human} chunks)")
    with open(f"{REPO}/spotcheck/owner_shortlist.md", "w") as f:
        f.write("\n".join(lines))
    print(f"shortlist: {n_decisions} rulings covering {n_needs_human} chunks -> spotcheck/owner_shortlist.md")

    # ---- combined judgments CSV (full 400, provenance-tagged) ----
    APPLICABILITY = {
        "MDA": {"sentiment": True, "guidance_direction": False, "red_flags": True, "distress_tier": True},
        "RISK_FACTORS": {"sentiment": False, "guidance_direction": False, "red_flags": True, "distress_tier": True},
        "EX99_PRESS_RELEASE": {"sentiment": True, "guidance_direction": True, "red_flags": True, "distress_tier": True},
        "8K_BODY": {"sentiment": True, "guidance_direction": True, "red_flags": True, "distress_tier": True},
    }
    needs_human_fields = set()
    for a in adjs.values():
        if a["needs_human"]:
            for f in a["fields"]:
                needs_human_fields.add((a["chunk_id"], f["field"]))
    adj_by_field = {(a["chunk_id"], f["field"]): f for a in adjs.values() for f in a["fields"]}

    rows = []
    anomalies = []
    for cid, av in auditor.items():
        st = sample.loc[cid]
        for field in FIELDS:
            if not APPLICABILITY[st["section_type"]][field]:
                continue
            verdict = av[field]["verdict"]
            if verdict == "n/a":
                anomalies.append((cid, field, "auditor n/a on applicable field"))
                continue
            if (cid, field) in needs_human_fields:
                judgment, source = "", "owner-pending"
            elif (cid, field) in adj_by_field:
                judgment, source = adj_by_field[(cid, field)]["verdict"], "model-adjudicator"
            else:
                judgment, source = "agree", "model-auditor"
                assert verdict == "agree", (cid, field, verdict)
            rows.append({"chunk_id": cid, "section_type": st["section_type"],
                         "primary_tier": st["primary_tier"], "field": field,
                         "judgment": judgment, "field_note": "", "example_note": "",
                         "source": source})
    df = pd.DataFrame(rows)
    df.to_csv(f"{REPO}/spotcheck/combined_judgments.csv", index=False)
    print(f"\ncombined_judgments.csv: {len(df)} rows | by source: {df['source'].value_counts().to_dict()}")
    if anomalies:
        print(f"anomalies (excluded, must be documented): {anomalies}")


if __name__ == "__main__":
    main(sys.argv[1])
