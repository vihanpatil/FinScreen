"""Offline tests for label_shift_v11_v12.py. No network, no API, no model."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

import label_shift_v11_v12 as S

HERE = Path(__file__).resolve().parent


def rf(*pairs):
    return [{"category": c, "modality": m} for c, m in pairs]


def series(*cells):
    return pd.Series(list(cells))


# ------------------------------------------------------------ normalizing ----

def test_as_pairs_handles_none_empty_and_lists():
    assert S.as_pairs(None) == frozenset()
    assert S.as_pairs([]) == frozenset()
    assert S.as_pairs(rf(("DEMAND_WEAKNESS", "REALIZED"))) == {("DEMAND_WEAKNESS", "REALIZED")}


def test_modalities_of_returns_a_set_not_a_scalar():
    s = S.as_pairs(rf(("DEMAND_WEAKNESS", "REALIZED"), ("DEMAND_WEAKNESS", "HYPOTHETICAL")))
    assert S.modalities_of(s, "DEMAND_WEAKNESS") == {"REALIZED", "HYPOTHETICAL"}
    assert S.modalities_of(s, "MARGIN_COST_PRESSURE") == frozenset()


def test_dual_modality_row_is_detected_as_changed_not_silently_equal():
    """A category carried at BOTH modalities vs one — a scalar `modality_of`
    would compare equal by iteration order. This is the regression pin."""
    a = series(rf(("LEGAL_REGULATORY_ACTION", "HYPOTHETICAL"), ("LEGAL_REGULATORY_ACTION", "REALIZED")))
    b = series(rf(("LEGAL_REGULATORY_ACTION", "REALIZED")))
    out = S.set_field_shift(a, b, "red_flags")
    assert out["exact_set"]["n_changed"] == 1
    assert out["exact_set"]["decomposition"] == {"modality only": 1}
    assert out["per_category_decisions"]["n_changed"] == 1


# ------------------------------------------------------------ scalar field ----

def test_field_shift_counts_only_rows_applicable_on_both_sides():
    a = series("NEUTRAL", "POSITIVE", None, "NEGATIVE")
    b = series("NEGATIVE", "POSITIVE", "NEUTRAL", None)
    out = S.field_shift(a, b)
    assert out["n_applicable_both"] == 2
    assert out["n_changed"] == 1
    assert out["transitions"] == {"NEUTRAL -> NEGATIVE": 1}
    assert out["applicability_only_v11"] == 1
    assert out["applicability_only_v12"] == 1


# --------------------------------------------------------- set decomposition ----

def test_decomposition_labels_each_change_kind():
    a = series(
        rf(("DEMAND_WEAKNESS", "REALIZED")),                       # -> add
        rf(("DEMAND_WEAKNESS", "REALIZED"), ("TRADE_POLICY_EXPOSURE", "REALIZED")),  # -> drop
        rf(("DEMAND_WEAKNESS", "HYPOTHETICAL")),                   # -> modality
        rf(("DEMAND_WEAKNESS", "REALIZED")),                       # -> mixed
        rf(("DEMAND_WEAKNESS", "REALIZED")),                       # unchanged
    )
    b = series(
        rf(("DEMAND_WEAKNESS", "REALIZED"), ("MARGIN_COST_PRESSURE", "REALIZED")),
        rf(("DEMAND_WEAKNESS", "REALIZED")),
        rf(("DEMAND_WEAKNESS", "REALIZED")),
        rf(("MARGIN_COST_PRESSURE", "REALIZED")),
        rf(("DEMAND_WEAKNESS", "REALIZED")),
    )
    out = S.set_field_shift(a, b, "red_flags")
    assert out["exact_set"]["n_changed"] == 4
    d = out["exact_set"]["decomposition"]
    assert d["adds only"] == 1 and d["drops only"] == 1 and d["modality only"] == 1
    assert d["mixed (adds+drops)"] == 1


def test_per_category_counts_added_dropped_and_modality_flips():
    a = series(rf(("MARGIN_COST_PRESSURE", "HYPOTHETICAL")), [], rf(("MARGIN_COST_PRESSURE", "REALIZED")))
    b = series(rf(("MARGIN_COST_PRESSURE", "REALIZED")), rf(("MARGIN_COST_PRESSURE", "REALIZED")), [])
    p = S.set_field_shift(a, b, "red_flags")["per_category"]["MARGIN_COST_PRESSURE"]
    assert p["v11_rows"] == 2 and p["v12_rows"] == 2 and p["delta"] == 0
    assert p["added_rows"] == 1 and p["dropped_rows"] == 1
    assert p["hypothetical_to_realized"] == 1 and p["realized_to_hypothetical"] == 0
    assert p["modality"]["HYPOTHETICAL"] == {"v11": 1, "v12": 0, "delta": -1}
    assert p["modality"]["REALIZED"] == {"v11": 1, "v12": 2, "delta": 1}


def test_per_category_decisions_denominator_is_rows_times_six():
    a = series([], [])
    b = series([], [])
    out = S.set_field_shift(a, b, "red_flags")["per_category_decisions"]
    assert out["n_decisions"] == 12 and out["n_changed"] == 0
    assert out["agreement_pct"] == 100.0


def test_total_flags_counts_entries_not_rows():
    a = series(rf(("DEMAND_WEAKNESS", "REALIZED"), ("MARGIN_COST_PRESSURE", "REALIZED")))
    b = series(rf(("DEMAND_WEAKNESS", "REALIZED")))
    out = S.set_field_shift(a, b, "red_flags")
    assert out["total_flags"] == {"v11": 2, "v12": 1, "delta": -1}
    assert out["rows_with_at_least_one"] == {"v11": 1, "v12": 1, "delta": 0}


# --------------------------------------------------------------- distress ----

def test_distress_decomposition_splits_adds_drops_and_within_positive_changes():
    a = series(rf(("LIQUIDITY_STRESS", "HYPOTHETICAL")), rf(("LIQUIDITY_STRESS", "HYPOTHETICAL")), [])
    b = series(rf(("LIQUIDITY_STRESS", "REALIZED")), [], rf(("LIQUIDITY_STRESS", "HYPOTHETICAL")))
    out = S.distress_decomposition(a, b)
    assert out["positive_rows"] == {"v11": 2, "v12": 2, "delta": 0}
    t = out["row_transitions"]
    assert t["positive_both"] == 1 and t["positive_both_but_changed"] == 1
    assert t["positive_v11_only (dropped)"] == 1 and t["positive_v12_only (added)"] == 1
    assert out["by_tier_modality"]["LIQUIDITY_STRESS/HYPOTHETICAL"] == {"v11": 2, "v12": 1, "delta": -1}


# ------------------------------------------------- real-artifact pinning ----

REPORT = HERE / "label_shift_v11_v12.json"
real = pytest.mark.skipif(not REPORT.exists(), reason="label-shift report not generated on this box")


@real
def test_real_comparable_population_is_6746_with_one_asymmetric_row():
    """After the completion batch, v1.2 covers all 6,747; v1.1 covers 6,746
    (its refusal chunk is unlabeled). So the comparable set is 6,746 and the
    only asymmetric row is E1's refusal chunk — which is in neither split."""
    r = json.loads(REPORT.read_text())
    cp = r["comparable_population"]
    assert cp["n"] == 6746
    assert cp["asymmetric_rows"]["labeled_in_v11_only"] == []
    assert cp["asymmetric_rows"]["labeled_in_v12_only"] == ["CHK-8e69547e0900a8dd"]
    assert cp["by_split"] == {"train": 5736, "eval": 1010}


@real
def test_real_red_flags_moved_far_more_than_sentiment_or_guidance():
    r = json.loads(REPORT.read_text())
    assert r["red_flags"]["exact_set"]["pct_changed"] > 10 * r["guidance_direction"]["pct_changed"]
    assert r["red_flags"]["exact_set"]["pct_changed"] > 5 * r["sentiment"]["pct_changed"]


@real
def test_real_reconciliation_flags_the_off_by_one_in_hardening_progress():
    r = json.loads(REPORT.read_text())
    rec = r["reconciliation_with_hardening_progress"]
    assert rec["recomputed_over_all_6747_labeled_rows"] == {"red_flag_rows": 4514, "distress_rows": 129}


@real
def test_real_legal_regulatory_modality_flip_is_the_dominant_p1_effect():
    """P1 (realized-controls) predicted exactly this. Pinned so a regenerated
    report that loses it is noticed."""
    r = json.loads(REPORT.read_text())
    p = r["red_flags"]["per_category"]["LEGAL_REGULATORY_ACTION"]
    assert p["hypothetical_to_realized"] >= 200
    assert p["hypothetical_to_realized"] > 10 * p["realized_to_hypothetical"]
    assert p["modality"]["REALIZED"]["delta"] > 0 > p["modality"]["HYPOTHETICAL"]["delta"]


@real
def test_real_train_and_eval_shifted_at_similar_rates():
    """If they diverged, the retrain and its held-out eval would be measuring
    different rubrics."""
    r = json.loads(REPORT.read_text())
    tr = r["by_split"]["train"]["exact_set_pct_changed"]
    ev = r["by_split"]["eval"]["exact_set_pct_changed"]
    assert abs(tr - ev) < 5.0, (tr, ev)
