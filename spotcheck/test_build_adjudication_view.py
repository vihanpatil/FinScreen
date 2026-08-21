"""
test_build_adjudication_view.py — unit tests for build_adjudication_view.py.

Almost everything here runs over SYNTHETIC frames/verdicts (same discipline
as test_compute_agreement.py): the scope rule, group assignment, high-stakes
forcing, the applicability assertion, the published-set cross-check and the
parse-failed-row guard are all logic, and logic is tested on data we
construct so a failure points at the code and not at the corpus.

The one exception is the block at the bottom marked REAL ARTIFACTS, which is
a read-only regression check that the shipped view still has exactly 174
records / 199 field judgments and that the known refusal chunk
(CHK-8e69547e0900a8dd) is still out of scope. It reads spotcheck/*.parquet
and spotcheck/*.json; it writes nothing and makes no API calls.

Run: python3 -m pytest spotcheck/test_build_adjudication_view.py -v
"""

import json
import os

import numpy as np
import pandas as pd
import pytest

from build_adjudication_view import (
    BASE,
    FIELDS,
    GROUP_DEFS,
    HIGH_STAKES,
    KNOWN_REFUSAL_CHUNK,
    assert_no_failed_rows_in_scope,
    build_records,
    cross_check_published,
    entries_to_list,
    summarize_groups,
    verify_high_stakes,
    verify_parse_failures,
)

EMPTY = np.array([], dtype=object)


def rf(*pairs):
    """list<struct<category, modality>> as parquet hands it back: an ndarray."""
    return np.array([{"category": c, "modality": m} for c, m in pairs], dtype=object)


def make_row(chunk_id, section_type="MDA", parse_ok=True, parse_error=None,
             sentiment="NEUTRAL", guidance_direction=None,
             red_flags=None, distress_tier=None, text="synthetic passage.",
             word_count=350, primary_tier="C", tiers="C", subtier=None):
    return {
        "chunk_id": chunk_id,
        "section_type": section_type,
        "text": text,
        "word_count": word_count,
        "primary_tier": primary_tier,
        "tiers": tiers,
        "subtier": subtier,
        "parse_ok": parse_ok,
        "parse_error": parse_error,
        "sentiment": sentiment,
        "guidance_direction": guidance_direction,
        "red_flags": EMPTY if red_flags is None else red_flags,
        "distress_tier": EMPTY if distress_tier is None else distress_tier,
    }


def make_df(rows):
    return pd.DataFrame(rows)


def verdict(chunk_id, default="agree", **fields):
    v = {"chunk_id": chunk_id}
    for f in FIELDS:
        v[f] = {"verdict": fields.get(f, default), "my_label": None, "reason": None}
    return v


def verdicts_of(*vs):
    return {v["chunk_id"]: v for v in vs}


def one(records):
    assert len(records) == 1, [r["chunk_id"] for r in records]
    return records[0]


# ---------------------------------------------------------------- scope rule


def test_scope_is_exactly_the_contested_fields():
    df = make_df([make_row("CHK-a", "EX99_PRESS_RELEASE")])
    recs = build_records(df, verdicts_of(verdict("CHK-a", sentiment="disagree")),
                         high_stakes=[])
    r = one(recs)
    assert r["adjudication_scope"] == ["sentiment"]
    assert r["in_scope_by"] == "disagreement"


def test_unsure_counts_as_contested():
    df = make_df([make_row("CHK-a")])
    recs = build_records(df, verdicts_of(verdict("CHK-a", red_flags="unsure")),
                         high_stakes=[])
    assert one(recs)["adjudication_scope"] == ["red_flags"]


def test_agree_only_chunk_is_dropped():
    df = make_df([make_row("CHK-a")])
    assert build_records(df, verdicts_of(verdict("CHK-a")), high_stakes=[]) == []


def test_na_verdict_is_not_contested():
    df = make_df([make_row("CHK-a", "RISK_FACTORS")])
    assert build_records(df, verdicts_of(verdict("CHK-a", default="n/a")),
                         high_stakes=[]) == []


def test_scope_uses_canonical_field_order_not_verdict_order():
    df = make_df([make_row("CHK-a", "8K_BODY")])
    recs = build_records(
        df,
        verdicts_of(verdict("CHK-a", distress_tier="disagree", red_flags="disagree",
                            guidance_direction="unsure", sentiment="disagree")),
        high_stakes=[],
    )
    assert one(recs)["adjudication_scope"] == FIELDS


def test_out_of_scope_field_stays_out_of_scope_but_record_is_complete():
    """A chunk in scope for one field still carries the full labels/auditor
    payload — the view needs it to render the uncontested cards."""
    df = make_df([make_row("CHK-a", red_flags=rf(("DEMAND_WEAKNESS", "REALIZED")))])
    r = one(build_records(df, verdicts_of(verdict("CHK-a", sentiment="disagree")),
                          high_stakes=[]))
    assert r["adjudication_scope"] == ["sentiment"]
    assert r["labels"]["red_flags"] == [{"category": "DEMAND_WEAKNESS", "modality": "REALIZED"}]
    assert set(r["auditor"]) == set(FIELDS)


# --------------------------------------------------------- group assignment


def test_group_stakes_wins_over_everything():
    df = make_df([make_row("CHK-a", distress_tier=rf(("LIQUIDITY_STRESS", "REALIZED")))])
    r = one(build_records(df, verdicts_of(verdict("CHK-a", sentiment="disagree",
                                                  distress_tier="disagree")),
                          high_stakes=["CHK-a"]))
    assert r["group"] == "stakes"
    assert r["group_label"] == "High-stakes distress"
    assert r["high_stakes"] is True


def test_group_distress_when_distress_contested_but_not_high_stakes():
    df = make_df([make_row("CHK-a")])
    r = one(build_records(df, verdicts_of(verdict("CHK-a", distress_tier="disagree",
                                                  sentiment="disagree")),
                          high_stakes=[]))
    assert r["group"] == "distress"


def test_group_sent_guid_when_only_scalar_fields_contested():
    df = make_df([make_row("CHK-a", "EX99_PRESS_RELEASE")])
    r = one(build_records(df, verdicts_of(verdict("CHK-a", guidance_direction="disagree",
                                                  red_flags="disagree")),
                          high_stakes=[]))
    assert r["group"] == "sent_guid"


def test_group_redflags_only():
    df = make_df([make_row("CHK-a")])
    r = one(build_records(df, verdicts_of(verdict("CHK-a", red_flags="disagree")),
                          high_stakes=[]))
    assert r["group"] == "redflags_only"


def test_records_sorted_by_group_rank_then_chunk_id():
    rows = [make_row(c) for c in ["CHK-z", "CHK-m", "CHK-a", "CHK-b"]]
    rows[0]["distress_tier"] = rf(("LIQUIDITY_STRESS", "REALIZED"))
    df = make_df(rows)
    v = verdicts_of(
        verdict("CHK-z", red_flags="disagree"),          # stakes
        verdict("CHK-m", red_flags="disagree"),          # redflags_only
        verdict("CHK-a", distress_tier="disagree"),      # distress
        verdict("CHK-b", sentiment="disagree"),          # sent_guid
    )
    recs = build_records(df, v, high_stakes=["CHK-z"])
    assert [r["chunk_id"] for r in recs] == ["CHK-z", "CHK-a", "CHK-b", "CHK-m"]
    assert [r["group"] for r in recs] == ["stakes", "distress", "sent_guid", "redflags_only"]


def test_summarize_groups_counts_every_group_including_empties():
    df = make_df([make_row("CHK-a")])
    recs = build_records(df, verdicts_of(verdict("CHK-a", red_flags="disagree")),
                         high_stakes=[])
    groups = summarize_groups(recs)
    assert [g["key"] for g in groups] == [k for k, _ in GROUP_DEFS]
    assert {g["key"]: g["count"] for g in groups} == {
        "stakes": 0, "distress": 0, "sent_guid": 0, "redflags_only": 1}


# ------------------------------------------------------ high-stakes forcing


def test_high_stakes_chunk_is_in_scope_even_with_zero_disagreements():
    df = make_df([make_row("CHK-a", distress_tier=rf(("ACCOUNTING_RESTATEMENT", "HYPOTHETICAL")))])
    r = one(build_records(df, verdicts_of(verdict("CHK-a")), high_stakes=["CHK-a"]))
    assert r["adjudication_scope"] == ["distress_tier"]
    assert r["in_scope_by"] == "stakes"


def test_high_stakes_with_other_disagreements_marked_as_both():
    df = make_df([make_row("CHK-a")])
    r = one(build_records(df, verdicts_of(verdict("CHK-a", red_flags="disagree")),
                          high_stakes=["CHK-a"]))
    assert r["adjudication_scope"] == ["red_flags", "distress_tier"]
    assert r["in_scope_by"] == "disagreement+stakes"


def test_high_stakes_distress_tier_not_duplicated_when_already_contested():
    df = make_df([make_row("CHK-a")])
    r = one(build_records(df, verdicts_of(verdict("CHK-a", distress_tier="disagree")),
                          high_stakes=["CHK-a"]))
    assert r["adjudication_scope"] == ["distress_tier"]
    assert r["in_scope_by"] == "disagreement+stakes"


def test_verify_high_stakes_detects_drift_in_either_direction():
    df = make_df([
        make_row("CHK-a", distress_tier=rf(("LIQUIDITY_STRESS", "REALIZED"))),
        make_row("CHK-b", distress_tier=rf(("ACCOUNTING_RESTATEMENT", "HYPOTHETICAL"))),
        make_row("CHK-c", distress_tier=rf(("LIQUIDITY_STRESS", "HYPOTHETICAL"))),
    ])
    verify_high_stakes(df, high_stakes=["CHK-a", "CHK-b"])          # exact match
    with pytest.raises(AssertionError, match="High-stakes set drifted"):
        verify_high_stakes(df, high_stakes=["CHK-a"])                # missed one
    with pytest.raises(AssertionError, match="High-stakes set drifted"):
        verify_high_stakes(df, high_stakes=["CHK-a", "CHK-b", "CHK-c"])  # HYPOTHETICAL is not high-stakes


# --------------------------------------------------- applicability assertion


def test_scope_outside_the_applicability_matrix_is_a_hard_error():
    """RISK_FACTORS is never asked for sentiment (rubric §1), so a sentiment
    verdict on one means the verdict file and the matrix disagree — fail the
    build rather than render a card for a label that was never requested."""
    df = make_df([make_row("CHK-a", "RISK_FACTORS")])
    with pytest.raises(AssertionError) as exc:
        build_records(df, verdicts_of(verdict("CHK-a", sentiment="disagree")),
                      high_stakes=[])
    assert "CHK-a" in str(exc.value)


def test_guidance_direction_not_applicable_to_mda():
    df = make_df([make_row("CHK-a", "MDA")])
    with pytest.raises(AssertionError):
        build_records(df, verdicts_of(verdict("CHK-a", guidance_direction="unsure")),
                      high_stakes=[])


def test_unknown_section_type_is_a_hard_error_not_a_permissive_default():
    df = make_df([make_row("CHK-a", "SOMETHING_NEW")])
    with pytest.raises(KeyError):
        build_records(df, verdicts_of(verdict("CHK-a", red_flags="disagree")),
                      high_stakes=[])


# ------------------------------------------------- published-set cross-check


def test_cross_check_published_passes_on_exact_match():
    df = make_df([make_row("CHK-a"), make_row("CHK-b")])
    recs = build_records(df, verdicts_of(verdict("CHK-a", red_flags="disagree"),
                                         verdict("CHK-b", red_flags="disagree")),
                         high_stakes=[])
    cross_check_published(recs, {"CHK-a", "CHK-b"})


def test_cross_check_published_reports_built_only():
    df = make_df([make_row("CHK-a")])
    recs = build_records(df, verdicts_of(verdict("CHK-a", red_flags="disagree")),
                         high_stakes=[])
    with pytest.raises(AssertionError, match=r"built-only=\['CHK-a'\]"):
        cross_check_published(recs, set())


def test_cross_check_published_reports_published_only():
    df = make_df([make_row("CHK-a")])
    recs = build_records(df, verdicts_of(verdict("CHK-a", red_flags="disagree")),
                         high_stakes=[])
    with pytest.raises(AssertionError, match=r"published-only=\['CHK-ghost'\]"):
        cross_check_published(recs, {"CHK-a", "CHK-ghost"})


# --------------------------------------------------- labeling_failed handling


def test_parse_ok_row_carries_labeling_failed_false():
    df = make_df([make_row("CHK-a")])
    r = one(build_records(df, verdicts_of(verdict("CHK-a", red_flags="disagree")),
                          high_stakes=[]))
    assert r["parse_ok"] is True
    assert r["labeling_failed"] is False
    assert r["parse_error"] is None


def test_failed_row_carries_the_flag_and_the_error_into_the_record():
    """The flag must reach the template — otherwise a failed row's empty
    red_flags renders as '(no matches)', asserting the model found zero
    flags when in fact it produced no labels at all."""
    df = make_df([make_row("CHK-a", parse_ok=False,
                           parse_error="stop_reason=refusal (bio)",
                           sentiment=None)])
    r = one(build_records(df, verdicts_of(verdict("CHK-a", red_flags="disagree")),
                          high_stakes=[]))
    assert r["labeling_failed"] is True
    assert r["parse_ok"] is False
    assert r["parse_error"] == "stop_reason=refusal (bio)"
    assert r["labels"]["red_flags"] == []      # absent, not asserted-empty
    assert r["labels"]["sentiment"] is None


def test_assert_no_failed_rows_in_scope_raises_and_names_the_chunk():
    df = make_df([make_row("CHK-broken", parse_ok=False, parse_error="truncated")])
    recs = build_records(df, verdicts_of(verdict("CHK-broken", red_flags="disagree")),
                         high_stakes=[])
    with pytest.raises(AssertionError) as exc:
        assert_no_failed_rows_in_scope(recs)
    msg = str(exc.value)
    assert "CHK-broken" in msg
    assert "LABELING-FAILED" in msg


def test_assert_no_failed_rows_in_scope_also_blocks_the_known_refusal_chunk():
    """Belt and braces: even if a future frame claimed parse_ok=True for the
    refusal chunk, it has no stored labels and must stay out of the 174."""
    df = make_df([make_row(KNOWN_REFUSAL_CHUNK, parse_ok=True)])
    recs = build_records(df, verdicts_of(verdict(KNOWN_REFUSAL_CHUNK, red_flags="disagree")),
                         high_stakes=[])
    with pytest.raises(AssertionError, match="known refusal chunk"):
        assert_no_failed_rows_in_scope(recs)


def test_assert_no_failed_rows_in_scope_passes_on_a_clean_set():
    df = make_df([make_row("CHK-a")])
    recs = build_records(df, verdicts_of(verdict("CHK-a", red_flags="disagree")),
                         high_stakes=[])
    assert_no_failed_rows_in_scope(recs)


def test_verify_parse_failures_tolerates_the_known_refusal_only():
    df = make_df([make_row("CHK-a"),
                  make_row(KNOWN_REFUSAL_CHUNK, parse_ok=False, parse_error="refusal")])
    assert verify_parse_failures(df) == {KNOWN_REFUSAL_CHUNK}
    assert verify_parse_failures(make_df([make_row("CHK-a")])) == set()


def test_verify_parse_failures_rejects_a_new_failure():
    df = make_df([make_row("CHK-new-break", parse_ok=False, parse_error="boom")])
    with pytest.raises(AssertionError, match="UNEXPECTED PARSE-FAILED ROWS"):
        verify_parse_failures(df)


# ------------------------------------------------------------------ helpers


def test_entries_to_list_maps_struct_arrays_and_empties():
    assert entries_to_list(rf(("LEGAL_REGULATORY_ACTION", "HYPOTHETICAL"))) == [
        {"category": "LEGAL_REGULATORY_ACTION", "modality": "HYPOTHETICAL"}]
    assert entries_to_list(EMPTY) == []
    assert entries_to_list(None) == []


# ------------------------------------------------------------ REAL ARTIFACTS
# Read-only regression checks against the shipped spot-check files.

SAMPLE = f"{BASE}/sample_400.parquet"
VERDICTS = f"{BASE}/auditor_verdicts.json"
DISAGREEMENTS = f"{BASE}/auditor_disagreements.json"
VIEW = f"{BASE}/adjudication_174.html"

real_artifacts = pytest.mark.skipif(
    not all(os.path.exists(p) for p in (SAMPLE, VERDICTS, DISAGREEMENTS)),
    reason="spot-check artifacts not present",
)


@pytest.fixture(scope="module")
def real_records():
    df = pd.read_parquet(SAMPLE)
    with open(VERDICTS) as f:
        verdicts = {v["chunk_id"]: v for v in json.load(f)["verdicts"]}
    return df, verdicts, build_records(df, verdicts)


@real_artifacts
def test_real_view_is_174_records_and_199_field_judgments(real_records):
    _, _, recs = real_records
    assert len(recs) == 174
    assert sum(len(r["adjudication_scope"]) for r in recs) == 199


@real_artifacts
def test_real_high_stakes_and_parse_failures_verify(real_records):
    df, _, _ = real_records
    verify_high_stakes(df)
    assert verify_parse_failures(df) == {KNOWN_REFUSAL_CHUNK}
    assert len(HIGH_STAKES) == 11


@real_artifacts
def test_real_refusal_chunk_stays_out_of_the_174(real_records):
    _, _, recs = real_records
    assert KNOWN_REFUSAL_CHUNK not in {r["chunk_id"] for r in recs}
    assert_no_failed_rows_in_scope(recs)


@real_artifacts
def test_real_set_matches_the_published_disagreement_set(real_records):
    _, _, recs = real_records
    with open(DISAGREEMENTS) as f:
        published = {r["chunk_id"] for r in json.load(f)["rows"]}
    cross_check_published(recs, published)


@real_artifacts
def test_real_group_counts_sum_to_the_record_count(real_records):
    _, _, recs = real_records
    groups = summarize_groups(recs)
    assert sum(g["count"] for g in groups) == len(recs)
    assert {g["key"]: g["count"] for g in groups}["stakes"] == 11


@pytest.mark.skipif(not os.path.exists(VIEW), reason="adjudication_174.html not built")
def test_built_view_carries_the_hardening():
    """The shipped HTML must actually contain the two fixes, not just the
    sources (HANDOFF §7: verify the artifact, not the filename)."""
    with open(VIEW) as f:
        html = f.read()
    assert "NOT AVAILABLE (labeling failed" in html
    assert "function reconcileState(" in html
    assert '"labeling_failed": false' in html         # flag reaches the records
    assert "finscreen_adjudication_174_v1" in html    # STORAGE_KEY unchanged
    assert '"labeling_failed": true' not in html      # none in scope today
    assert html.count('"labeling_failed": false') == 174
