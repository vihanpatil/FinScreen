"""
test_census_e2.py -- the freeze tripwire on `data/f5/census_e2.py` (red-team
SH-8, 2026-09-11).

The census is the ONE module that reads the modeling frame, the target table
and the fold structure before ratification, and its whole licence to do so is
F5_PLAN §1: it may COUNT, and it may measure feature-versus-COMPANY-IDENTITY
(the §6 ICCs). It may not fit, rank, correlate or otherwise associate a feature
with `target_excess_63`, and it may not reach into the runner's fitting paths.
Nothing but review enforced that, so a future edit could have slipped an
association in under a "census" name.

These tests are STATIC (AST + line inspection) and READ-ONLY. They import
nothing from the census, run no measurement, and touch no parquet: a tripwire
that had to execute the module would be a tripwire that ran the thing it is
guarding.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
CENSUS_PY = ROOT / "data" / "f5" / "census_e2.py"
CENSUS_JSON = ROOT / "data" / "f5" / "census_e2.json"

#: Identifiers that would mean this module fitted, correlated or re-entered the
#: runner's head-1 machinery. Matched against IDENTIFIERS (import names, called
#: names, attribute names) -- never against string literals, because the census
#: legitimately WRITES prose about XGBoost's missing-value routing and about the
#: correlations it did not compute.
BANNED_EXACT = frozenset(
    {
        "spearmanr",
        "pearsonr",
        "corr",            # ".corr(" on any frame or series
        "fit",
        "fit_predict",
        "evaluate_arm",
        "run_head1",
        "margin_procedure",
        "_spearman_or_nan",
    }
)
#: Matched as substrings of an identifier (a class name can be aliased).
BANNED_SUBSTRING = ("XGB", "LinearRegression")

OUTCOME = "target_excess_63"
#: The census may name the outcome ONLY in a completeness/censoring context.
#: Every line that mentions it today carries one of these words: `.isna()` on
#: the join (line ~228), the two freeze statements that say it is read "only to
#: COUNT completeness", and the channel-B censoring definition, whose whole
#: subject is the target being NULL. "null" is in this set for that one line and
#: is still completeness language -- a line that READ the values would not be
#: describing them as null.
COMPLETENESS_WORDS = ("notna", "isna", "count", "complete", "null")


@pytest.fixture(scope="module")
def source() -> str:
    return CENSUS_PY.read_text()


@pytest.fixture(scope="module")
def tree(source) -> ast.Module:
    return ast.parse(source, filename=str(CENSUS_PY))


def _identifiers(tree: ast.Module) -> set[str]:
    """Every name the module could call or import through: import targets,
    bare names, and attribute names. String literals are deliberately NOT
    included."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                out.update(alias.name.split("."))
                if alias.asname:
                    out.add(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            out.update((node.module or "").split("."))
            for alias in node.names:
                out.add(alias.name)
                if alias.asname:
                    out.add(alias.asname)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(node.name)
    return out


def test_census_never_calls_or_imports_a_fitting_or_correlation_function(tree):
    """No spearman/pearson/`.corr(`/`fit(`/XGB/LinearRegression/`fit_predict`,
    and no re-entry into `backtest_e2`'s head-1 fitting path
    (`evaluate_arm`, `run_head1`, `margin_procedure`, `_spearman_or_nan`)."""
    idents = _identifiers(tree)
    assert not (idents & BANNED_EXACT), sorted(idents & BANNED_EXACT)
    for needle in BANNED_SUBSTRING:
        offenders = sorted(i for i in idents if needle in i)
        assert not offenders, f"{needle}: {offenders}"


def test_the_only_backtest_e2_entry_points_are_fold_and_dedup_helpers(tree):
    """The census reaches into `backtest_e2` for fold construction and the
    dedup keep-mask only. Anything else is a new door into the runner and has
    to be argued for, not discovered."""
    allowed = {"build_folds", "dedup_keep_mask_cik", "load_analysis_frame",
               "exclude_gld_rows", "extract_params_block", "labeler_negative_recall",
               "LABELER_EVAL_PATH"}
    used = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in {"BE", "backtest_e2"}
    }
    assert used <= allowed, sorted(used - allowed)


def test_the_outcome_column_is_read_only_to_count_completeness(tree, source):
    """`target_excess_63` may be touched by `.isna()` / `.notna()` and nothing
    else. Checked twice: in the AST (every code-level access is wrapped in a
    completeness call) and line by line (every mention, prose included, sits in
    a completeness sentence)."""
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    accesses = 0
    for node in ast.walk(tree):
        hit = (
            (isinstance(node, ast.Attribute) and node.attr == OUTCOME)
            or (
                isinstance(node, ast.Subscript)
                and isinstance(node.slice, ast.Constant)
                and node.slice.value == OUTCOME
            )
        )
        if not hit:
            continue
        accesses += 1
        parent = parents.get(node)
        assert isinstance(parent, ast.Attribute) and parent.attr in {"isna", "notna"}, (
            f"{OUTCOME} is read at line {node.lineno} outside a completeness call "
            f"(parent: {ast.dump(parent)[:120] if parent else None})"
        )
    assert accesses >= 1, "the tripwire must actually be watching a real access"

    for lineno, line in enumerate(source.splitlines(), start=1):
        if OUTCOME not in line:
            continue
        low = line.lower()
        assert any(word in low for word in COMPLETENESS_WORDS), (
            f"line {lineno} mentions {OUTCOME} outside a completeness/censoring "
            f"context: {line.strip()[:120]}"
        )


def test_the_committed_census_carries_the_ratified_fold_and_run_time_blocks():
    """The two blocks round 3 added, ON DISK: the GLD-excluded ratified-fold
    census (whose `sum_n_test_dedup` is the scorecard's row count) and the
    run-time frame's overlap/coverage block the document quotes."""
    doc = json.loads(CENSUS_JSON.read_text())

    folds = doc["section_1b_ratified_folds_ex_gld"]
    assert isinstance(folds["sum_n_test_dedup"], int) and folds["sum_n_test_dedup"] > 0
    assert folds["n_folds"] == len(folds["per_fold"]) == 33
    assert folds["frame"] == "ex_gld_run_time"
    for key in ("overlap_arm_scored_rows_in_folds", "n_distinct_ciks_in_folds",
                "n_test_dedup_mean", "n_purge_instances"):
        assert key in folds, key
    assert "section_1b_ratified_folds_gld_in" in doc

    run_time = doc["section_1c_run_time_frame_overlap_and_coverage"]
    for block in ("train_overlap_gld_in", "train_overlap_ex_gld_run_time"):
        overlap = run_time[block]
        assert {"n_rows", "n_ciks", "filing_level_n", "filing_level_share",
                "cik_level_n", "cik_level_share"} <= set(overlap), block
    assert run_time["confirmatory_column_coverage_ex_gld_run_time"]
    assert run_time["families_vs_join_set_differences"]


def test_the_committed_census_quotes_no_superseded_overlap_arithmetic():
    """Red-team MF-1: the overlap-arm row count is the in-fold one from
    §1b, and the company-level overlap share is this frame's -- the module used
    to assert a frame-arithmetic row count and G2's fine-tuning-corpus CIK
    share, both of which the JSON's own §1b/§1c blocks contradicted."""
    doc = json.loads(CENSUS_JSON.read_text())
    overlap = doc["section_5_label_purge_and_instrument_census"]["train_overlap"]
    # every PROSE value of the block, so a superseded number cannot come back in
    # a neighbouring sentence (measured floats elsewhere in the file may of
    # course contain those digits, which is why this reads the block, not the
    # raw text)
    prose = " ".join(v for v in overlap.values() if isinstance(v, str))
    assert "4859" not in prose and "4,859" not in prose
    assert "15.85" not in prose
    assert "cik_level_share" in overlap["different_questions"]
    assert "overlap_arm_scored_rows_in_folds" in overlap["arm_as_built"]
