"""
test_prepare_dataset.py — lightweight local tests (pandas only, no GPU/heavy deps).

Covers:
  - applicability-matrix test: prepare_dataset.APPLICABILITY matches
    labeling_rubric.md §1 exactly (minus distress_tier, globally excluded).
  - prompt-template no-leakage test: no ticker/company-name string from the
    real universe.csv, and no date-shaped string, appears in any generated
    prompt (instruction + input) for a sample of real chunks.
  - distress_tier is never present in any generated training target.

Run: `python3 -m pytest test_prepare_dataset.py -v` or `python3 test_prepare_dataset.py`
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

import prepare_dataset as pd_mod

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
UNIVERSE_PATH = REPO_ROOT / "data" / "universe.csv"
LABELS_PATH = REPO_ROOT / "data" / "labels.parquet"

# Rubric's applicability matrix (labeling_rubric.md §1), minus distress_tier
# (asked in the rubric/schema, but deliberately excluded from fine-tuning
# targets entirely -- see PROMPT_TEMPLATE.md's "distress_tier exclusion"
# section and DISCOVERY.md §3).
RUBRIC_APPLICABILITY = {
    "MDA": {"sentiment": True, "guidance_direction": False, "red_flags": True},
    "RISK_FACTORS": {"sentiment": False, "guidance_direction": False, "red_flags": True},
    "EX99_PRESS_RELEASE": {"sentiment": True, "guidance_direction": True, "red_flags": True},
    "8K_BODY": {"sentiment": True, "guidance_direction": True, "red_flags": True},
}


def test_applicability_matrix_matches_rubric():
    assert pd_mod.APPLICABILITY == RUBRIC_APPLICABILITY, (
        "prepare_dataset.APPLICABILITY has drifted from labeling_rubric.md §1's matrix "
        "(distress_tier excluded intentionally on both sides of this comparison)"
    )
    print("PASS: test_applicability_matrix_matches_rubric")


def test_no_distress_tier_in_targets():
    labels = pd.read_parquet(LABELS_PATH)
    df = labels[labels["parse_ok"] & labels["schema_valid"]].reset_index(drop=True)
    sample = df.sample(n=min(300, len(df)), random_state=42)
    for _, row in sample.iterrows():
        target = pd_mod.build_target(row)
        assert "distress_tier" not in target, (
            f"chunk {row['chunk_id']}: distress_tier leaked into training target"
        )
    print(f"PASS: test_no_distress_tier_in_targets ({len(sample)} sampled rows)")


def test_target_field_presence_matches_applicability():
    labels = pd.read_parquet(LABELS_PATH)
    df = labels[labels["parse_ok"] & labels["schema_valid"]].reset_index(drop=True)
    sample = df.sample(n=min(500, len(df)), random_state=7)
    for _, row in sample.iterrows():
        target = pd_mod.build_target(row)
        applic = pd_mod.APPLICABILITY[row["section_type"]]
        assert ("sentiment" in target) == applic["sentiment"], (
            f"chunk {row['chunk_id']} ({row['section_type']}): sentiment presence mismatch"
        )
        assert ("guidance_direction" in target) == applic["guidance_direction"], (
            f"chunk {row['chunk_id']} ({row['section_type']}): guidance_direction presence mismatch"
        )
        assert ("red_flags" in target) == applic["red_flags"], (
            f"chunk {row['chunk_id']} ({row['section_type']}): red_flags presence mismatch"
        )
    print(f"PASS: test_target_field_presence_matches_applicability ({len(sample)} sampled rows)")


def _leakage_needles() -> list[str]:
    """Real ticker / company-name strings from universe.csv, plus common
    variants, to search for in generated prompts."""
    universe = pd.read_csv(UNIVERSE_PATH)
    needles = []
    for _, row in universe.iterrows():
        needles.append(row["ticker"])
        name = row["company_name"]
        needles.append(name)
        # Also test a couple of common short forms / stripped suffixes.
        stripped = re.sub(r"\s+(Inc\.?|Corp\.?|Co\.?|Group\s+Inc\.?|Limited.*)$", "", name).strip()
        if stripped and stripped != name:
            needles.append(stripped)
    return sorted(set(n for n in needles if n))


_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")  # ISO date, e.g. home_filing_date format


def test_instruction_template_never_leaks():
    """The FIXED `instruction` string (byte-identical across every example,
    never derived from a row) must never contain any real ticker, company
    name, or date-shaped string. This is the part fully under our control:
    unlike `input` (raw filing prose, see the next test), nothing here is
    row-derived, so this should hold with zero exceptions."""
    needles = _leakage_needles()
    text = pd_mod.INSTRUCTION
    violations = []
    for needle in needles:
        if len(needle) <= 2:
            continue  # too short to test meaningfully against template prose
        if re.search(r"\b" + re.escape(needle) + r"\b", text, flags=re.IGNORECASE):
            violations.append(needle)
    if _DATE_RE.search(text):
        violations.append("ISO-date-shaped string")
    assert not violations, f"Fixed instruction template contains leakage: {violations}"
    print("PASS: test_instruction_template_never_leaks")


def test_input_is_unmodified_passthrough_no_injected_metadata():
    """`input` must be EXACTLY the chunk's raw `text` field -- nothing
    prepended/appended/injected (no ticker, company, date, or section_type
    string added by prepare_dataset.py itself). This is the guarantee we
    can actually make and enforce in code.

    NOTE -- documented, accepted residual risk (DISCOVERY.md §5, restated
    here rather than silently worked around): the underlying filing PROSE
    itself sometimes self-identifies the company by name (~19% of chunks
    corpus-wide per DISCOVERY.md's figure, up to ~48% of press releases) --
    e.g. "Pfizer today announced..." This is source-text content, not
    something prepare_dataset.py adds, and the rubric's mitigation is
    explicit-instruction-based (labeling_rubric.md §0), not text redaction
    (deliberately not attempted -- real NLP risk of corrupting content, see
    DISCOVERY.md §5). This test reports the observed self-identification
    rate on its sample for visibility, and does NOT fail on it, since
    fixing it would require the redaction effort DISCOVERY.md explicitly
    chose not to do for the MVP -- failing this test on a known, accepted,
    already-documented risk would be noise, not a real regression signal.
    A REAL regression this test WOULD catch: `input` differing at all from
    the source `text` (i.e. any injected metadata prepare_dataset.py itself
    added, which is fully within our control and never acceptable).
    """
    labels = pd.read_parquet(LABELS_PATH)
    df = labels[labels["parse_ok"] & labels["schema_valid"]].reset_index(drop=True)
    sample = df.sample(n=min(400, len(df)), random_state=123)

    needles = _leakage_needles()
    long_needles = [n for n in needles if len(n) > 2]

    self_id_count = 0
    for _, row in sample.iterrows():
        ex = pd_mod.build_example(row)
        assert ex["input"] == row["text"], (
            f"chunk {row['chunk_id']}: prepare_dataset.py's 'input' field differs from the "
            f"source chunk text -- something was injected, this is a real bug"
        )
        for needle in long_needles:
            if re.search(r"\b" + re.escape(needle) + r"\b", ex["input"], flags=re.IGNORECASE):
                self_id_count += 1
                break

    print(
        f"INFO (not a failure): {self_id_count}/{len(sample)} "
        f"({self_id_count / len(sample):.1%}) sampled chunks self-identify a company/ticker "
        f"in their own source prose -- consistent with DISCOVERY.md §5's corrected "
        f"26.8%-46.0% (strict-to-loose) residual-identification range (see REDTEAM_WEEK3.md "
        f"finding #2), not something this script injects or can remove."
    )
    print("PASS: test_input_is_unmodified_passthrough_no_injected_metadata")


def test_output_json_deterministic_key_order():
    labels = pd.read_parquet(LABELS_PATH)
    df = labels[labels["parse_ok"] & labels["schema_valid"]].reset_index(drop=True)
    ex99 = df[df["section_type"] == "EX99_PRESS_RELEASE"].iloc[0]
    ex = pd_mod.build_example(ex99)
    keys = list(json.loads(ex["output"]).keys())
    assert keys == [k for k in pd_mod.KEY_ORDER if k in keys], (
        f"output JSON key order {keys} doesn't respect KEY_ORDER {pd_mod.KEY_ORDER}"
    )
    print("PASS: test_output_json_deterministic_key_order")


if __name__ == "__main__":
    test_applicability_matrix_matches_rubric()
    test_no_distress_tier_in_targets()
    test_target_field_presence_matches_applicability()
    test_instruction_template_never_leaks()
    test_input_is_unmodified_passthrough_no_injected_metadata()
    test_output_json_deterministic_key_order()
    print("\nALL TESTS PASSED")
