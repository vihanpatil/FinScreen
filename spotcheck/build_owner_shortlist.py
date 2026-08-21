"""
build_owner_shortlist.py — generates spotcheck/owner_shortlist.md, the
owner's decision list over the adjudicator's needs_human escalations.
Supersedes the flat shortlist merge_adjudications.py emits (this one
consolidates the 12 batch-agents' divergent pattern slugs into principle
rulings that cascade).

Structure:
  Part A — 3 principle rulings (one owner decision each, cascading over all
           member chunks; members + proposed labels listed so ratification
           is concrete)
  Part B — the 11 high-stakes distress chunks, individually (protocol
           reserves these for the owner; most also fall under Principle 2)
  Part C — everything else, grouped by field, one compact entry each

Every recommendation in this file is a MODEL adjudication
(source=model-adjudicator). Only what the owner actually decides — in chat
or via the view — counts as the owner's judgment. Bulk ratification of a
block, stated by the owner in chat, is an owner judgment over that block
and is recorded as such (source=owner, method=bulk-ratified).
"""

import json
from collections import defaultdict

BASE = "/Users/vihanpatil/personal/projects/FinScreen/spotcheck"

HIGH_STAKES = [
    "CHK-20d940b1855c8068", "CHK-8153748ce0e68c39", "CHK-9d1f3820572c181c",
    "CHK-a787c4ef45504dd1", "CHK-ba3a1dcd71201c66", "CHK-c17d2149a239bbcd",
    "CHK-ce2710d1b304bea6", "CHK-d9f9c2729c76438b", "CHK-ed1212d8058db87d",
    "CHK-95a7cf23f319ee70", "CHK-d74facbd628dfc96",
]

# Cross-batch slug consolidation: the 12 agents invented slugs
# independently; these clusters name the same underlying rubric question.
PRINCIPLES = [
    {
        "key": "P1-realized-controls",
        "title": "P1 — Does a realized statement inside hypothetical boilerplate control the modality?",
        "question": (
            "When a risk-factor or safe-harbor passage names something that has "
            "actually happened or currently exists ('we are subject to pending "
            "investigations', 'audits ... have in the past resulted in fines'), is "
            "the red flag REALIZED even though the surrounding framing is "
            "could/may hypothetical? Rubric §6's realized-controls rule says yes; "
            "the adjudicator ruled REALIZED throughout. Ruling AGREE with the "
            "principle ratifies each member's proposed label below."
        ),
        "slugs": {
            "safe-harbor-pending-litigation-modality",
            "realized-trigger-hypothetical-impact-modality",
            "realized-statement-controls",
            "party-to-proceedings-realized",
            "risk-factor-realized-lead-in-modality",
        },
    },
    {
        "key": "P2-liquidity-threshold",
        "title": "P2 — What does LIQUIDITY_STRESS require?",
        "question": (
            "Does LIQUIDITY_STRESS require the text to assert insufficiency or "
            "difficulty meeting obligations — so that adverse raw facts (a "
            "working-capital deficit, past adverse effects on liquidity ratios, "
            "definitional risk language) paired with affirmed adequacy ('we "
            "anticipate being able to support our short-term liquidity') do NOT "
            "qualify? The adjudicator consistently ruled that affirmed adequacy "
            "defeats the flag. This principle covers most of the high-stakes "
            "chunks in Part B."
        ),
        "slugs": {
            "liquidity-stress-requires-explicit-insufficiency",
            "wc-deficit-with-affirmed-adequacy",
            "liquidity-language-threshold-for-distress",
            "past-adverse-liquidity-effect-not-explicit-distress",
            "legal-impediment-not-liquidity-stress",
            "forecast-variance-not-liquidity-stress",
        },
    },
    {
        "key": "P3-boilerplate-mining",
        "title": "P3 — How aggressively should enumerated boilerplate risk lists be mined for category flags?",
        "question": (
            "In long safe-harbor factor lists, does every clause that brushes a "
            "category (a single word like 'impairments' or 'costs' inside an "
            "enumeration) earn a HYPOTHETICAL flag, or only clauses that "
            "meaningfully assert the risk? The adjudicator generally required a "
            "meaningful assertion and trimmed single-word matches, but flagged "
            "the line as a precedent the rubric does not draw explicitly."
        ),
        "slugs": {
            "boilerplate-enumeration-mining-depth",
            "consequence-clause-category-mining",
            "single-clause-hypothetical-match",
            "embedded-risk-mention-hypothetical",
            "boilerplate-factor-list-category-sweep",
            "impairment-assessment-clause-boilerplate",
        },
    },
]


def fmt_label(field, v):
    if field in ("sentiment", "guidance_direction"):
        return "(none)" if v is None else str(v)
    if v is None:
        return "(n/a)"
    if not v:
        return "(no flags)"
    return "; ".join(
        f"{p[0]}—{p[1]}" if isinstance(p, list) else f"{p['category']}—{p['modality']}" for p in v
    )


def main():
    adjs = {a["chunk_id"]: a
            for a in json.load(open(f"{BASE}/adjudicator_verdicts.json"))["adjudications"]}
    stored = {r["chunk_id"]: r["stored_labels"]
              for r in json.load(open(f"{BASE}/auditor_disagreements.json"))["rows"]}

    slug_to_principle = {}
    for p in PRINCIPLES:
        for s in p["slugs"]:
            slug_to_principle[s] = p["key"]

    principle_members = defaultdict(list)   # key -> [(cid, field_adj)]
    rest = defaultdict(list)                # field -> [(cid, field_adj, chunk_adj)]
    for a in adjs.values():
        if not a["needs_human"]:
            continue
        for f in a["fields"]:
            pk = slug_to_principle.get(f.get("pattern", ""))
            if pk:
                principle_members[pk].append((a["chunk_id"], f))
            elif not (a["chunk_id"] in HIGH_STAKES and f["field"] == "distress_tier"):
                rest[f["field"]].append((a["chunk_id"], f, a))

    L = []
    L.append("# Owner adjudication shortlist (consolidated)")
    L.append("")
    L.append("Every recommendation here is a **model** adjudication — reference, not")
    L.append("your judgment. Verdicts are about the STORED label: *agree* = stored is")
    L.append("right; *disagree* = stored is wrong (proposed label shown); *unsure* =")
    L.append("rubric underdetermines. You may rule item-by-item, or ratify a whole")
    L.append("block in chat ('I ratify P1', 'I ratify all of Part C') — a bulk")
    L.append("ratification is your judgment over that block and is recorded that way.")
    L.append("")
    n_principle_cases = sum(len(v) for v in principle_members.values())
    n_rest = sum(len(v) for v in rest.values())
    L.append(f"**Decisions: 3 principles (cascading over {n_principle_cases} field-cases) "
             f"+ {len(HIGH_STAKES)} high-stakes chunks + {n_rest} individual items.**")
    L.append("")

    L.append("## Part A — Principle rulings")
    L.append("")
    for p in PRINCIPLES:
        members = principle_members[p["key"]]
        L.append(f"### {p['title']}")
        L.append("")
        L.append(p["question"])
        L.append("")
        L.append(f"**Members ({len(members)}):**")
        L.append("")
        for cid, f in sorted(members):
            hs = " ★high-stakes" if cid in HIGH_STAKES else ""
            L.append(f"- `{cid}`{hs} [{f['field']}] stored: {fmt_label(f['field'], stored[cid][f['field']])}"
                     f" → adjudicator ({f['verdict']}, {f['confidence']}): "
                     f"{fmt_label(f['field'], f.get('correct_label')) if f['verdict'] == 'disagree' else f['verdict']}")
        L.append("")
        L.append("**Your ruling on the principle:** [ ] agree with adjudicator  [ ] reject (explain)  [ ] unsure")
        L.append("")

    L.append("## Part B — The 11 high-stakes distress chunks (yours regardless)")
    L.append("")
    L.append("Rule each individually — a principle ruling above informs but does not")
    L.append("replace these (protocol reserves them for you).")
    L.append("")
    for cid in HIGH_STAKES:
        a = adjs[cid]
        f = next(x for x in a["fields"] if x["field"] == "distress_tier")
        L.append(f"### {cid}")
        L.append(f"- stored: {fmt_label('distress_tier', stored[cid]['distress_tier'])}"
                 f" → adjudicator ({f['verdict']}, {f['confidence']}): "
                 f"{fmt_label('distress_tier', f.get('correct_label')) if f['verdict'] == 'disagree' else f['verdict']}")
        L.append(f"- brief: {f['brief']}")
        if a.get("needs_human_reason"):
            L.append(f"- what you must weigh: {a['needs_human_reason']}")
        L.append("- **Your ruling:** [ ] agree  [ ] disagree (state label)  [ ] unsure")
        L.append("")

    L.append("## Part C — Remaining individual items")
    L.append("")
    for field in ["sentiment", "guidance_direction", "red_flags", "distress_tier"]:
        items = rest.get(field, [])
        if not items:
            continue
        L.append(f"### {field} ({len(items)})")
        L.append("")
        for cid, f, a in sorted(items):
            L.append(f"#### `{cid}` — {f.get('pattern', 'no pattern')}")
            L.append(f"- stored: {fmt_label(field, stored[cid][field])}"
                     f" → adjudicator ({f['verdict']}, {f['confidence']}): "
                     f"{fmt_label(field, f.get('correct_label')) if f['verdict'] == 'disagree' else f['verdict']}")
            L.append(f"- brief: {f['brief']}")
            L.append("- **Your ruling:** [ ] agree  [ ] disagree (state label)  [ ] unsure")
            L.append("")

    with open(f"{BASE}/owner_shortlist.md", "w") as fh:
        fh.write("\n".join(L))
    print(f"Part A: 3 principles / {n_principle_cases} cases | Part B: {len(HIGH_STAKES)} | Part C: {n_rest} items")


if __name__ == "__main__":
    main()
