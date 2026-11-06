"""
test_census_e3.py -- the freeze tripwire on `data/f5/census_e3.py`, the E3
numeric-families pre-registration census (2026-11-06).

Same licence as `census_e2.py` and the same STATIC, READ-ONLY checks, reused
from `test_census_e2.py`: the census may COUNT and may run the feature-only
PIT rank transform; it may not fit, rank, correlate or otherwise associate a
feature with `target_excess_63`, and it may reach into `backtest_e2` only
through the fold, dedup, sha and parameter-parsing helpers. It imports
nothing from the census, runs no measurement, touches no parquet.

The pin check is INVERTED relative to a naive "must be absent" (the G3 M2
lesson, F6 §5): a pin may be absent (today) or present and matching the
document's sha; a present-but-mismatched pin is the only failure, and
nothing here ever invites deleting a pin.
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

import pytest

from test_census_e2 import (
    BANNED_EXACT, BANNED_SUBSTRING, COMPLETENESS_WORDS, OUTCOME, _identifiers,
)

ROOT = Path(__file__).resolve().parent
CENSUS_PY = ROOT / "data" / "f5" / "census_e3.py"
CENSUS_JSON = ROOT / "data" / "f5" / "census_e3.json"
PREREG = ROOT / "data" / "f5" / "E3_PREREGISTRATION.md"
PIN = ROOT / "data" / "f5" / "E3_RATIFIED.json"


@pytest.fixture(scope="module")
def source() -> str:
    return CENSUS_PY.read_text()


@pytest.fixture(scope="module")
def tree(source) -> ast.Module:
    return ast.parse(source, filename=str(CENSUS_PY))


def test_census_e3_never_calls_or_imports_a_fitting_or_correlation_function(tree):
    idents = _identifiers(tree)
    assert not (idents & BANNED_EXACT), sorted(idents & BANNED_EXACT)
    for needle in BANNED_SUBSTRING:
        offenders = sorted(i for i in idents if needle in i)
        assert not offenders, f"{needle}: {offenders}"


def test_census_e3_backtest_e2_entry_points_are_helpers_only(tree):
    allowed = {"build_folds", "dedup_keep_mask_cik", "exclude_gld_rows",
               "extract_params_block", "assert_input_shas"}
    used = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in {"BE", "backtest_e2"}
    }
    assert used <= allowed, sorted(used - allowed)


def test_census_e3_touches_the_outcome_only_to_count_completeness(tree, source):
    """Code-level: every subscript on OUTCOME_COL is the receiver of an
    `.isna()` / `.notna()` call. Line-level: every mention of the outcome,
    prose included, carries completeness language."""
    completeness_receivers = {
        id(node.func.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr in ("isna", "notna")
    }
    for node in ast.walk(tree):
        if (isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Name)
                and node.slice.id == "OUTCOME_COL"):
            assert id(node) in completeness_receivers, \
                f"line {node.lineno}: OUTCOME_COL used outside .isna()/.notna()"
    for n, line in enumerate(source.splitlines(), 1):
        if OUTCOME in line or "OUTCOME_COL" in line:
            low = line.lower()
            assert any(w in low for w in COMPLETENESS_WORDS) or "read only" in low, f"line {n}: {line.strip()}"


def test_committed_census_e3_reproduces_the_e2_run_time_frame_and_is_frozen():
    census = json.loads(CENSUS_JSON.read_text())
    checks = census["section_1_reproduction_checks"]
    assert checks["frame_B_reproduces_e2_run_time_frame"] is True
    assert checks["frame_B_rows_measured"] == 7381
    assert census["network_calls"] == 0 and census["api_spend_usd"] == 0.0
    assert "No information coefficient" in census["freeze_statement"]
    folds = census["section_3_folds"]
    for fb in folds.values():
        assert fb["n_folds"] == 33
        assert fb["fold_quarters"][0] == "2018Q1" and fb["fold_quarters"][-1] == "2026Q1"
    a = folds["A_periodic_10K_10Q"]
    assert a["n_rows_in_folds_raw"] == a["n_rows_in_folds_dedup"]  # dedup is the identity on periodic rows
    for name, anchor in census["section_4_mde"]["anchors"].items():
        assert anchor["source"], name
    # the ladder is G3's, never above 0.05 (red-team M3)
    ladders = {str(r["ladder_selected"]) for fr in census["section_4_mde"]["by_frame"].values() for r in fr["rows"]}
    assert ladders <= {"None", "0.03", "0.04", "0.05"}, ladders


def test_pin_is_absent_or_matches_the_document():
    """Absent today. Once `pin_e3.py` writes it, it must carry this document's
    sha; a mismatch means the document moved under the pin. Never 'must be
    absent': that invited deleting the G3 pin (F6 §5, M2)."""
    if not PIN.exists():
        return
    pin = json.loads(PIN.read_text())
    assert pin["doc_sha256"] == hashlib.sha256(PREREG.read_bytes()).hexdigest()
