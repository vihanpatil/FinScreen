"""
build_adjudication_view.py — assembles spotcheck/adjudication_174.html, the
filtered owner-adjudication view over the label-auditor disagreement set
(HANDOFF.md §6 Step 1: present ONLY disagreements + the high-stakes distress
chunks, never all 400).

Inputs:
  - sample_400.parquet        (chunk text + stored labels — read directly;
                               sample_400.json is a separate export of the
                               same parquet, verified content-identical)
  - auditor_verdicts.json     (all 400 label-auditor model verdicts)
  - review_app.js             (tested serialization/state logic, inlined
                               untouched — same file review_tool.html uses)
  - adjudication_template.html

Output:
  - adjudication_174.html     (self-contained, works from file://)

Scope rule per chunk: it is included iff the auditor issued >=1
disagree/unsure verdict on it, OR it is one of the 11 high-stakes distress
chunks (in-scope by stakes). Per-field judgment buttons appear only for
contested fields, plus distress_tier on every high-stakes chunk regardless
of auditor agreement.

Parse-failed rows: every record carries `labeling_failed` / `parse_ok` /
`parse_error` (same contract as export_sample_json.py and review_app.js's
`emptyJudgmentForExample` comment). A chunk whose labeling itself failed has
no stored label to agree or disagree with, so the template renders
"NOT AVAILABLE (labeling failed)" with no judgment buttons instead of
rendering an empty red_flags list as "(no matches)" — which would assert
the model found zero flags. `assert_no_failed_rows_in_scope()` additionally
makes it a hard build-time error for such a row to reach the view at all;
the template branch is defence in depth behind that assertion. Today the
corpus's one parse failure (the CHK-8e69547e0900a8dd bio-category refusal,
HANDOFF §2) draws four "n/a" auditor verdicts and is not high-stakes, so it
is correctly outside the 174.

Exports from the view use the same finscreen-spotcheck-v1 format as
review_tool.html, restricted to in-scope (chunk, field) pairs, so
compute_agreement.py's loaders parse them directly. The combined-judgment
merge (auditor agrees + owner adjudications) happens downstream, not here.
"""

import json

import numpy as np
import pandas as pd

BASE = "/Users/vihanpatil/personal/projects/FinScreen/spotcheck"

# Hand-synced with labeling_rubric.md §1, same as export_sample_json.py.
APPLICABILITY = {
    "MDA": {"sentiment": True, "guidance_direction": False, "red_flags": True, "distress_tier": True},
    "RISK_FACTORS": {"sentiment": False, "guidance_direction": False, "red_flags": True, "distress_tier": True},
    "EX99_PRESS_RELEASE": {"sentiment": True, "guidance_direction": True, "red_flags": True, "distress_tier": True},
    "8K_BODY": {"sentiment": True, "guidance_direction": True, "red_flags": True, "distress_tier": True},
}

FIELDS = ["sentiment", "guidance_direction", "red_flags", "distress_tier"]

CONTESTED_VERDICTS = ("disagree", "unsure")

# The corpus's only labeling failure: a genuine bio-category safety refusal,
# confirmed by direct Batch API re-query (stop_reason=refusal), excluded by
# predicate rather than deleted — HANDOFF.md §2. It has no stored labels, so
# it must never enter an adjudication pass.
KNOWN_REFUSAL_CHUNK = "CHK-8e69547e0900a8dd"

# The 11 highest-stakes distress chunks (9 stored REALIZED LIQUIDITY_STRESS +
# 2 ACCOUNTING_RESTATEMENT), in-scope by stakes per the 2026-08-11
# ratification — HANDOFF §6 Step 1. (HANDOFF's lone mention of "8" is a typo;
# its own 9+2 arithmetic gives 11.) Verified against sample_400.parquet.
HIGH_STAKES = [
    "CHK-20d940b1855c8068", "CHK-8153748ce0e68c39", "CHK-9d1f3820572c181c",
    "CHK-a787c4ef45504dd1", "CHK-ba3a1dcd71201c66", "CHK-c17d2149a239bbcd",
    "CHK-ce2710d1b304bea6", "CHK-d9f9c2729c76438b", "CHK-ed1212d8058db87d",
    "CHK-95a7cf23f319ee70", "CHK-d74facbd628dfc96",
]

GROUP_DEFS = [
    ("stakes", "High-stakes distress"),
    ("distress", "Distress contested (other)"),
    ("sent_guid", "Sentiment/guidance contested"),
    ("redflags_only", "Red-flags only"),
]


def entries_to_list(x):
    if isinstance(x, np.ndarray) and len(x) > 0:
        return [{"category": e["category"], "modality": e["modality"]} for e in x]
    return []


def _indexed(df):
    """chunk_id-indexed view of the sample frame, idempotent."""
    if df.index.name == "chunk_id":
        return df
    return df.set_index("chunk_id", drop=False)


def verify_high_stakes(df, high_stakes=HIGH_STAKES):
    """Re-derive the stakes set from the parquet — never trust the hardcoded
    list alone (HANDOFF §7: verify the artifact)."""
    def has(v, cat, mod=None):
        if not isinstance(v, np.ndarray):
            return False
        return any(d["category"] == cat and (mod is None or d["modality"] == mod) for d in v)

    derived = set(df[df["distress_tier"].apply(lambda v: has(v, "LIQUIDITY_STRESS", "REALIZED"))]["chunk_id"])
    derived |= set(df[df["distress_tier"].apply(lambda v: has(v, "ACCOUNTING_RESTATEMENT"))]["chunk_id"])
    assert derived == set(high_stakes), (
        f"High-stakes set drifted: derived-only={derived - set(high_stakes)}, "
        f"hardcoded-only={set(high_stakes) - derived}"
    )


def verify_parse_failures(df, known=KNOWN_REFUSAL_CHUNK):
    """No parse failure in the sample other than the one known, documented
    refusal. A new one showing up is a data-integrity event, not something to
    quietly render — fail the build and make the operator look at it."""
    d = _indexed(df)
    failed = set(d.loc[~d["parse_ok"].astype(bool), "chunk_id"])
    unexpected = failed - {known}
    assert not unexpected, (
        "UNEXPECTED PARSE-FAILED ROWS in sample_400.parquet: "
        f"{sorted(unexpected)}. Only {known} (the documented bio-category "
        "refusal, HANDOFF §2) is a known labeling failure. Investigate the "
        "labeling artifact before rebuilding the adjudication view — a "
        "failed row has no stored label, so it cannot be adjudicated."
    )
    return failed


def build_records(df, verdicts, high_stakes=HIGH_STAKES):
    """Pure-ish core: (sample frame, auditor verdicts) -> ordered records.

    `verdicts` maps chunk_id -> {field: {verdict, my_label, reason}}.
    Raises AssertionError if a chunk is scoped for a field that is not
    applicable to its section_type (rubric §1 matrix).
    """
    d = _indexed(df)
    records = []
    for chunk_id, v in verdicts.items():
        contested = [f for f in FIELDS if v[f]["verdict"] in CONTESTED_VERDICTS]
        is_high_stakes = chunk_id in high_stakes
        if not contested and not is_high_stakes:
            continue

        row = d.loc[chunk_id]
        section_type = row["section_type"]
        applicability = APPLICABILITY[section_type]

        scope = list(contested)
        if is_high_stakes and "distress_tier" not in scope:
            scope.append("distress_tier")
        scope = [f for f in FIELDS if f in scope]  # canonical field order
        assert scope, chunk_id
        assert all(applicability[f] for f in scope), (chunk_id, scope)

        if is_high_stakes:
            group = "stakes"
        elif "distress_tier" in contested:
            group = "distress"
        elif "sentiment" in contested or "guidance_direction" in contested:
            group = "sent_guid"
        else:
            group = "redflags_only"

        in_scope_by = ("disagreement+stakes" if is_high_stakes and contested
                       else "stakes" if is_high_stakes else "disagreement")

        parse_ok = bool(row["parse_ok"])

        records.append({
            "chunk_id": chunk_id,
            "section_type": section_type,
            "text": row["text"],
            "word_count": int(row["word_count"]),
            "primary_tier": row["primary_tier"],
            "tiers": row["tiers"],
            "subtier": row["subtier"],
            "applicability": applicability,
            "group": group,
            "group_label": dict(GROUP_DEFS)[group],
            "in_scope_by": in_scope_by,
            "high_stakes": is_high_stakes,
            "adjudication_scope": scope,
            # Labeling-failure contract, mirroring export_sample_json.py: a
            # failed row's empty red_flags/distress_tier are ABSENT, not an
            # asserted empty list, and the template must say so.
            "parse_ok": parse_ok,
            "labeling_failed": not parse_ok,
            "parse_error": row["parse_error"] if pd.notna(row["parse_error"]) else None,
            "labels": {
                "sentiment": row["sentiment"] if pd.notna(row["sentiment"]) else None,
                "guidance_direction": row["guidance_direction"] if pd.notna(row["guidance_direction"]) else None,
                "red_flags": entries_to_list(row["red_flags"]),
                "distress_tier": entries_to_list(row["distress_tier"]),
            },
            "auditor": {f: {"verdict": v[f]["verdict"],
                            "my_label": v[f].get("my_label"),
                            "reason": v[f].get("reason")} for f in FIELDS},
        })

    # Review order: stakes first, then other distress, then sentiment/
    # guidance, then the red-flags-only bulk; chunk_id order within groups.
    group_rank = {k: i for i, (k, _) in enumerate(GROUP_DEFS)}
    records.sort(key=lambda r: (group_rank[r["group"]], r["chunk_id"]))
    return records


def assert_no_failed_rows_in_scope(records, known=KNOWN_REFUSAL_CHUNK):
    """LOUD guard: no parse-failed chunk may enter the adjudication view.

    A chunk whose labeling failed has no stored label, so "agree / disagree
    with the stored label" is not a question that can be asked about it, and
    counting it would silently contaminate the agreement denominators
    downstream. The template renders such a row defensively if it ever gets
    past here; this assertion says it must not get past here.
    """
    failed = sorted(r["chunk_id"] for r in records if r["labeling_failed"])
    assert not failed, (
        "LABELING-FAILED CHUNK(S) IN ADJUDICATION SCOPE: " + ", ".join(failed) + ".\n"
        "These rows have parse_ok=False — there is no stored label to agree "
        "or disagree with, so they cannot be adjudicated and must not be "
        "counted in any agreement denominator. Decide explicitly how to "
        "handle them (exclude by predicate, as labels.parquet does for the "
        f"{known} refusal) before shipping this view; do not just relax this "
        "assertion. adjudication_template.html will render them as "
        "'NOT AVAILABLE (labeling failed)' with no judgment buttons, but "
        "their presence still means the upstream scope rule changed."
    )
    built = {r["chunk_id"] for r in records}
    assert known not in built, (
        f"The known refusal chunk {known} entered the adjudication set. It "
        "has no stored labels (HANDOFF §2) and must stay out of the 174."
    )


def cross_check_published(records, published):
    """The built set must equal the published disagreement set exactly."""
    built = {r["chunk_id"] for r in records}
    published = set(published)
    assert built == published, (
        f"view/set mismatch: built-only={sorted(built - published)}, "
        f"published-only={sorted(published - built)}"
    )


def summarize_groups(records):
    return [{"key": k, "label": lbl, "count": sum(1 for r in records if r["group"] == k)}
            for k, lbl in GROUP_DEFS]


def render_html(records, groups, template, app_js):
    payload = {"records": records, "groups": groups}
    payload_json = json.dumps(payload, indent=None)
    json.loads(payload_json)  # validate

    out = template.replace("/*__REVIEW_APP_JS__*/", app_js)
    out = out.replace("/*__ADJUDICATION_DATA_JSON__*/", payload_json)
    return out


def main():
    df = pd.read_parquet(f"{BASE}/sample_400.parquet").set_index("chunk_id", drop=False)
    verify_high_stakes(df)
    failed_rows = verify_parse_failures(df)

    with open(f"{BASE}/auditor_verdicts.json") as f:
        verdicts = {v["chunk_id"]: v for v in json.load(f)["verdicts"]}
    assert len(verdicts) == 400, len(verdicts)

    records = build_records(df, verdicts)
    assert_no_failed_rows_in_scope(records)

    # Cross-check against the published disagreement set.
    with open(f"{BASE}/auditor_disagreements.json") as f:
        published = {r["chunk_id"] for r in json.load(f)["rows"]}
    cross_check_published(records, published)

    groups = summarize_groups(records)
    n_field_judgments = sum(len(r["adjudication_scope"]) for r in records)

    with open(f"{BASE}/adjudication_template.html") as f:
        template = f.read()
    with open(f"{BASE}/review_app.js") as f:
        app_js = f.read()

    out = render_html(records, groups, template, app_js)

    out_path = f"{BASE}/adjudication_174.html"
    with open(out_path, "w") as f:
        f.write(out)

    print(f"Wrote {out_path} ({len(out)} bytes)")
    print(f"records: {len(records)} | field judgments required: {n_field_judgments}")
    for g in groups:
        print(f"  {g['label']}: {g['count']}")
    print(f"parse-failed rows in sample: {sorted(failed_rows)} — none in scope (asserted)")


if __name__ == "__main__":
    main()
