"""
compute_agreement.py — computes spot-check agreement rates from the merged,
provenance-tagged judgment file.

Usage (this is the command that produced spotcheck/agreement_report.txt):
    python3 compute_agreement.py --input combined_judgments.csv --format auto

The real input is `combined_judgments.csv` — the merged output of the
three rater layers (model second rater / model third rater / owner
rulings), written by merge_adjudications.py. Any file with the same column
shape works.

Accepts either export shape (the CSV shape is also what review_tool.html
exports):
  - CSV: one row per (chunk_id, field) with columns
    chunk_id, section_type, primary_tier, field, judgment, field_note, example_note
  - JSON: {"format": "finscreen-spotcheck-v1", "state": {chunk_id: {...}}}

TIER LEGEND (Section 3 reports all four):
  A — all distress positives, exhaustive.
  B — deliberate oversample of thin/rare categories.
  C — proportional stratified random fill; the ONLY base-rate-
      representative slice.
  D — the config-disagreement set (chunks whose red_flags differed between
      the two labeling configs), judged blind.

`red_flags` is scored as an EXACT-SET MATCH: one added, dropped, or
re-modalized category on a multi-category chunk marks the whole chunk as a
disagreement. Its rate is therefore NOT comparable to the single-value
rates for `sentiment` / `guidance_direction` printed beside it.

DISTRESS TIER IS REPORTED SEPARATELY (per labeling_rubric.md §5's own
statement that whether to fold this tier into headline reporting is a
downstream pipeline decision, and per this project's Week 3 DoD requiring
distress-tier categories be excluded from any agreement-rate claim rather
than averaged in). This is asserted in code, not just described here: see
`assert_distress_excluded_from_headline()`.

TIER B (targeted oversample of thin categories — guidance non-NONE, a
per-category REALIZED red-flag quota, and 2 named chunks) makes any
pooled-across-tiers rate NON-REPRESENTATIVE of the corpus's true base
rates, because Tier B deliberately over-samples rare categories. Tier A
(exhaustive distress positives) and Tier D (the config-disagreement hard
cases) skew it the same way. Tier C (proportional stratified random fill)
is the base-rate-representative slice — this script reports Tier C's rate
separately and labels it as such; the pooled/all-tier number is reported
too, but explicitly flagged as not base-rate-representative.

Section 3's per-tier figures POOL all three headline fields together
(sentiment + guidance_direction + red_flags). They are not per-field
rates; a red-flags-only per-tier breakdown is published in HANDOFF.md §2a.
"""

import argparse
import csv
import json
import math
from collections import defaultdict

DISTRESS_TAG = "__distress_tier__"  # kept as its own bucket
HEADLINE_FIELDS = {"sentiment", "guidance_direction", "red_flags"}
# distress_tier is a FIELD name too, but is excluded from any "headline"
# aggregate — see assert_distress_excluded_from_headline().

CI_LOWER_BOUND_BAR = 0.70  # documented bar: categories whose 95% CI lower
# bound falls below this are flagged as rubric-revision candidates. This
# is a documented judgment call, not derived from the rubric itself — the
# rubric does not specify a numeric bar, so 0.70 is chosen here as a
# conservative-but-not-arbitrary threshold (an agreement rate whose lower
# CI bound is below 70% means we cannot rule out, at 95% confidence, that
# true agreement is below "correct roughly 7 times out of 10") and is
# reported explicitly so the owner can override it.


def wilson_ci(successes, n, z=1.959963984540054):
    """95% Wilson score confidence interval for a binomial proportion.
    z=1.959963984540054 is the two-sided 97.5th percentile of the standard
    normal (the exact value for a 95% CI), not the common z=1.96 rounding.
    Implemented directly from the closed-form Wilson formula (not a
    normal/Wald approximation) per the task's explicit instruction.
    Returns (point_estimate, lower, upper). n=0 returns (None, None, None).
    """
    if n == 0:
        return (None, None, None)
    phat = successes / n
    denom = 1 + z ** 2 / n
    center = phat + z ** 2 / (2 * n)
    margin = z * math.sqrt((phat * (1 - phat) / n) + (z ** 2 / (4 * n ** 2)))
    lower = (center - margin) / denom
    upper = (center + margin) / denom
    return (phat, max(0.0, lower), min(1.0, upper))


def load_csv(path):
    rows = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def load_json(path):
    with open(path) as f:
        obj = json.load(f)
    if obj.get("format") != "finscreen-spotcheck-v1":
        raise ValueError(f"Unrecognized export format: {obj.get('format')!r}")
    rows = []
    for chunk_id, entry in obj["state"].items():
        example_note = entry.get("example_note", "")
        for field, fj in entry.get("fields", {}).items():
            rows.append(
                {
                    "chunk_id": chunk_id,
                    "field": field,
                    "judgment": fj.get("judgment") or "",
                    "field_note": fj.get("note", ""),
                    "example_note": example_note,
                    # section_type / primary_tier are NOT stored in the JSON
                    # export state (that lives in sample_400.json, the
                    # dataset side) — caller must join if needed.
                }
            )
    return rows


def detect_format(path, fmt_arg):
    if fmt_arg != "auto":
        return fmt_arg
    if path.lower().endswith(".json"):
        return "json"
    if path.lower().endswith(".csv"):
        return "csv"
    raise ValueError(f"Cannot auto-detect format for {path}; pass --format csv|json")


def join_with_sample_metadata(rows, sample_path):
    """If the export rows are missing section_type/primary_tier (JSON export
    shape), join them in from sample_400.json so tier/section breakdowns
    still work."""
    with open(sample_path) as f:
        sample = json.load(f)
    meta = {ex["chunk_id"]: ex for ex in sample}
    for r in rows:
        if not r.get("section_type"):
            ex = meta.get(r["chunk_id"])
            if ex:
                r["section_type"] = ex["section_type"]
                r["primary_tier"] = ex["primary_tier"]
    return rows


def summarize(rows, label_filter=None):
    """rows: list of dicts with judgment in {agree, disagree, unsure, ''}.
    Returns dict: agree, disagree, unsure, unfilled, total, coverage."""
    agree = disagree = unsure = unfilled = 0
    for r in rows:
        if label_filter and not label_filter(r):
            continue
        j = (r.get("judgment") or "").strip().lower()
        if j == "agree":
            agree += 1
        elif j == "disagree":
            disagree += 1
        elif j == "unsure":
            unsure += 1
        else:
            unfilled += 1
    total = agree + disagree + unsure + unfilled
    judged = agree + disagree + unsure
    return {
        "agree": agree,
        "disagree": disagree,
        "unsure": unsure,
        "unfilled": unfilled,
        "total": total,
        "judged": judged,
        "coverage": (judged / total) if total else None,
    }


def agreement_rate_with_ci(summary):
    """Agreement rate = agree / (agree + disagree). `unsure` judgments are
    reported separately (neither counted as agreement nor as
    disagreement) because collapsing "unsure" into either bucket would
    misrepresent what the owner actually said. Unfilled rows are excluded
    (missing-data handling — never imputed)."""
    n = summary["agree"] + summary["disagree"]
    return wilson_ci(summary["agree"], n)


def assert_distress_excluded_from_headline(headline_rows):
    for r in headline_rows:
        assert r["field"] != "distress_tier", (
            "BUG: distress_tier field leaked into a headline aggregate — "
            "labeling_rubric.md §5 and the Week 3 DoD require distress-tier "
            "categories be reported separately and excluded from any "
            "headline/macro agreement number."
        )


def print_category_block(title, rows_for_category):
    summary = summarize(rows_for_category)
    est, lo, hi = agreement_rate_with_ci(summary)
    print(f"\n  {title}")
    if summary["total"] == 0:
        print("    (no rows)")
        return summary, (est, lo, hi)
    coverage_pct = f"{summary['coverage']*100:.1f}%" if summary["coverage"] is not None else "n/a"
    print(f"    n reviewed (agree+disagree+unsure) = {summary['judged']}, unfilled = {summary['unfilled']}, coverage = {coverage_pct}")
    print(f"    agree={summary['agree']}  disagree={summary['disagree']}  unsure={summary['unsure']}")
    if est is None:
        print("    agreement rate: n/a (no agree/disagree judgments yet)")
    else:
        print(f"    agreement rate = {est*100:.1f}%  (95% Wilson CI: [{lo*100:.1f}%, {hi*100:.1f}%])  [excludes 'unsure' from numerator/denominator]")
    return summary, (est, lo, hi)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--format", default="auto", choices=["auto", "csv", "json"])
    ap.add_argument(
        "--sample-metadata",
        default="/Users/vihanpatil/personal/projects/FinScreen/spotcheck/sample_400.json",
        help="Path to sample_400.json, used to join section_type/primary_tier for JSON exports.",
    )
    args = ap.parse_args()

    fmt = detect_format(args.input, args.format)
    if fmt == "csv":
        rows = load_csv(args.input)
    else:
        rows = load_json(args.input)
        rows = join_with_sample_metadata(rows, args.sample_metadata)

    print("=" * 78)
    print("FinScreen Week 3 spot-check — agreement report")
    print("=" * 78)
    print(
        "\nHEADER / SCOPE NOTE: distress_tier categories are reported in a "
        "SEPARATE section below and are EXCLUDED from every headline/macro "
        "agreement number in this report, per labeling_rubric.md §5 and the "
        "Week 3 definition-of-done. This exclusion is also asserted in code "
        "(assert_distress_excluded_from_headline)."
    )
    print(
        "\nTIER-B CAVEAT: Tier B (guidance non-NONE, a per-category REALIZED "
        "red-flag quota, and 2 named chunks) is a deliberate OVERSAMPLE of "
        "thin/rare categories. Any agreement rate pooled across all tiers is "
        "therefore NOT representative of the corpus's true base rates. Tier "
        "C (proportional stratified random fill) is reported separately below "
        "as the base-rate-representative estimate."
    )
    print(
        "\nTIER LEGEND: A = all distress positives, exhaustive. "
        "B = thin/rare-category oversample. "
        "C = proportional stratified random fill -- the ONLY "
        "base-rate-representative slice. "
        "D = the config-disagreement set (chunks whose red_flags differed "
        "between the two labeling configs), judged blind."
    )
    print(
        "\nMETRIC NOTE: red_flags is scored as an EXACT-SET MATCH -- one "
        "added, dropped, or re-modalized category on a multi-category chunk "
        "marks the whole chunk a disagreement. Its rate is NOT comparable to "
        "the single-value sentiment / guidance_direction rates printed beside "
        "it, and it is not a per-category error rate. Section 3's per-tier "
        "figures likewise POOL all three headline fields together; for a "
        "red-flags-only per-tier breakdown see HANDOFF.md 2a."
    )

    headline_rows = [r for r in rows if r.get("field") in HEADLINE_FIELDS]
    assert_distress_excluded_from_headline(headline_rows)
    distress_rows = [r for r in rows if r.get("field") == "distress_tier"]

    print("\n" + "-" * 78)
    print("SECTION 1 — HEADLINE per-label-category agreement (all tiers pooled; NOT base-rate-representative — see caveat above)")
    print("-" * 78)
    per_category_results = {}
    for field in sorted(HEADLINE_FIELDS):
        cat_rows = [r for r in headline_rows if r["field"] == field]
        title = field + (" (EXACT-SET MATCH — see METRIC NOTE above)" if field == "red_flags" else "")
        summary, ci = print_category_block(title, cat_rows)
        per_category_results[field] = (summary, ci)

    print("\n" + "-" * 78)
    print("SECTION 2 — Distress tier (SEPARATE, excluded from headline above, per rubric §5)")
    print("-" * 78)
    distress_summary, distress_ci = print_category_block("distress_tier", distress_rows)

    print("\n" + "-" * 78)
    print("SECTION 3 — Per-tier breakdown (A / B / C / D)")
    print("-" * 78)
    # Tier D (config-disagreement adjudication chunks) added 2026-08-18 —
    # this loop previously hardcoded A/B/C and silently dropped Tier D,
    # even though the Tier-D-vs-other-tiers comparison is Tier D's entire
    # purpose (HANDOFF §2/§6 Step 1 known bug, now fixed).
    for tier in ["A", "B", "C", "D"]:
        tier_rows = [r for r in headline_rows if r.get("primary_tier") == tier]
        print_category_block(f"Tier {tier} (headline fields only, distress excluded)", tier_rows)

    print(
        "\n  Tier C is the base-rate-representative slice (proportional "
        "stratified random sample) — use Tier C's numbers above, not the "
        "all-tiers pooled numbers in Section 1, for any claim about the "
        "corpus's true base-rate agreement."
    )

    print("\n" + "-" * 78)
    print("SECTION 4 — Per-section_type breakdown")
    print("-" * 78)
    section_types = sorted(set(r.get("section_type") for r in headline_rows if r.get("section_type")))
    for st in section_types:
        st_rows = [r for r in headline_rows if r.get("section_type") == st]
        print_category_block(st, st_rows)

    print("\n" + "-" * 78)
    print(f"SECTION 5 — Rubric-revision candidates (95% CI lower bound < {CI_LOWER_BOUND_BAR*100:.0f}%)")
    print("-" * 78)
    print(
        f"  Bar of {CI_LOWER_BOUND_BAR*100:.0f}% is a documented judgment call made in this "
        "script (not specified numerically by labeling_rubric.md). It is not "
        "exposed as a CLI flag — edit CI_LOWER_BOUND_BAR at the top of this "
        "file to change it."
    )
    flagged_any = False
    all_categories = list(per_category_results.items()) + [("distress_tier", (distress_summary, distress_ci))]
    for field, (summary, (est, lo, hi)) in all_categories:
        if lo is not None and lo < CI_LOWER_BOUND_BAR:
            flagged_any = True
            notes = [
                r["field_note"] for r in rows
                if r.get("field") == field and (r.get("judgment") or "").strip().lower() == "disagree" and r.get("field_note")
            ]
            print(f"\n  FLAGGED: {field} — agreement {est*100:.1f}%, 95% CI lower bound {lo*100:.1f}% < {CI_LOWER_BOUND_BAR*100:.0f}%")
            print(
                f"    disagreement notes: {len(notes)} of {summary['disagree']} "
                "disagreements carry a note (the owner-sourced rows). "
                "Adjudicator-resolved rows carry their reasoning as briefs in "
                "adjudicator_verdicts.json, not as field_note text."
            )
            for n in notes:
                print(f"      - {n}")
    if not flagged_any:
        print("\n  No category's CI lower bound fell below the bar (or insufficient judged data yet to tell).")

    print("\n" + "=" * 78)
    print("Done. Missing/unfilled judgments are reported as coverage gaps above, never imputed.")
    print("=" * 78)


if __name__ == "__main__":
    main()
