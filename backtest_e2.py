"""
backtest_e2.py -- E2 HEAD 1: the walk-forward text-vs-numeric screening
comparison, under the G3 freeze.

This is a RESEARCH SCREENING tool. Nothing here is a trading signal, an
expected return, or investment advice (HANDOFF §1, charter).

E1 and E2 backtest numbers are NUMERICALLY INCOMPARABLE (different
benchmark: E2 uses the membership-dated equal-weighted average over that
date's members excluding self). Every report this module writes says so.

-----------------------------------------------------------------------
0. THE FREEZE (F5_PLAN §1) -- read before touching anything
-----------------------------------------------------------------------
No information coefficient, correlation, model fit or feature-versus-
outcome association may be computed on E2 data until BOTH exist and agree:

    data/f5/G3_PREREGISTRATION.md      (the pre-registration document)
    data/f5/G3_RATIFIED.json           ({"doc_sha256": <sha of the .md>, ...})

`require_g3()` is the anti-shopping guard (the `analyze_g2.py` pattern):
absent file -> REFUSAL (exit 2), sha mismatch -> REFUSAL (exit 2). There is
no default, no override flag, and no environment variable that lets the
real run proceed without it. A missing guard is not a crash to be "fixed"
by adding a default; the fix is an owner ratification.

Every parameter G3 pins is READ from the document, never hard-coded here:
fold quarter list, spec args, margin ladder, seeds, purge rule, LOCO rule,
confirmatory column list, embedding PCA k, head-2/3 windows. The only
hard-coded parameter values in this file are `SELFTEST_PARAMS`, which are
used EXCLUSIVELY by `--selftest` over an in-process synthetic frame; they
are F5_PLAN §3's defaults and they are a test fixture, not a default for
the real run.

-----------------------------------------------------------------------
1. The three modes
-----------------------------------------------------------------------
  --census    no fitting, no association of any kind. Per-candidate-quarter
              row counts, usable CIKs, target completeness, purge counts,
              per-fold dedup n. ALLOWED before ratification. Writes
              data/f5/census_head1.json.
  --selftest  end-to-end on a SYNTHETIC seeded frame generated in-process,
              exercising every path (guard, params, folds, purge, PCA,
              margin, TOST, LOCO, seed band, report). Writes into a
              temporary directory (or --outdir).
  (default)   the real run. REFUSES unless the guard passes, then reads
              every parameter from the document.

-----------------------------------------------------------------------
2. Expected G3 params block (also written to data/f5/G3_PARAMS_SCHEMA.json)
-----------------------------------------------------------------------
The document must contain EXACTLY ONE fenced code block whose info string
is `json g3-params`:

    ```json g3-params
    { ... }
    ```

Schema (all keys required; unknown keys are echoed into the results JSON
but never consulted):

    params_version            "g3-params-1"
    fold_quarters             ["2018Q1", ...]  ascending test-quarter labels
    post_2019_first_quarter   "2019Q4"         censoring sub-window arm start
    purge_rule                "target_window_close_on_or_after_test_quarter_start"
    spec.window_days          int      -> spec.pit_trailing_rank_frame
    spec.min_comparators      int
    spec.include_same_day     bool     (primary arm)
    spec.same_day_sensitivity_arm bool (run include_same_day=False beside it)
    spec.secondary            "raw_levels"
    columns.numeric           [...]    numeric-only baseline block
    columns.confirmatory_text [...]    the confirmatory text block
    columns.exploratory_red_flags [...] exploratory row only, never confirmatory
    columns.family_novelty    [...]    YoY novelty columns (may be [])
    columns.size_col          "log_total_assets"  (zero-information row)
    embedding.pca_k           int, 0 disables the embedding block
    embedding.rank_transform_components  bool  -- PRIMARY (PIT-ranked) spec
                              arms only; the `raw_levels` secondary arm always
                              carries the untransformed PCA projection, or it
                              would not be a raw arm
    dedup.gap_days            int
    form_ablation_forms       ["10-Q", "10-K"]
    margin.ladder             [0.03, 0.04, 0.05]
    margin.power_divisor      2.487        (z_.95 + z_.80)
    margin.mde_multiplier     2.8
    margin.kc3_flag_above     0.03
    se.method                 "moving_block_bootstrap"
    se.block_length_rule      "ceil_k13_ac1"
    se.n_resamples            int
    se.seed                   int
    se.alternative            "newey_west"
    tost.alpha                0.05
    tost.ci_level             0.90
    tost.reference_distribution "normal" | "t"
    bootstrap_anchor.n_resamples int   (4000 per F5_PLAN)
    bootstrap_anchor.seed     int
    seeds.primary             0
    seeds.nuisance_band       [1, 100]
    loco.n_folds              6
    loco.index_rule           "round(j*(K-1)/5)"
    loco.scope                "per_fold_training_members"
    loco.max_ciks_per_fold    int | null
    overlap.column            "train_overlap_share"
    overlap.threshold         0.0
    head2.*, head3.*          pinned for the other heads; head 1 validates
                              their presence and echoes them, uses neither.

Any unimplemented named rule (`purge_rule`, `se.block_length_rule`,
`tost.reference_distribution`, `se.method`, `se.alternative`) is a
REFUSAL, not a silent fallback.

-----------------------------------------------------------------------
3. What the real run does (F5_PLAN Step 1 / §3 decisions 3-6, 14, 15)
-----------------------------------------------------------------------
Frame = inner join of data/f5/{target,text_features,numeric_features}_e2
on (cik, accession_number), `in_membership` only, plus the optional
text_families_e2 (novelty + pooled embeddings) when present. CIK is the
company key end to end. Input sha256s are asserted against the
data/f5/*_manifest.json records before a byte is used.

Folds: `backtest.build_walk_forward_folds` (frozen, imported) restricted to
the ratified quarter list; expanding window, time-ordered by filing date,
never a shuffle. PURGE: a training row whose 63-session target window
closes on or after the test quarter's first session is dropped. Because
`window_close_session` is always a real trading session, "on or after the
first session of the quarter" and "on or after the quarter's first calendar
day" select exactly the same rows; the calendar comparison is used and this
equivalence is pinned by a test.

Specifications, always as a pair, plus the named sensitivity arm:
  primary   spec.pit_trailing_rank_frame(..., ticker_col="cik",
                                         date_col="filing_date")
  secondary raw levels
  sensitivity  the same primary with include_same_day=False

Blocks per fold: `numeric_only` and `text_and_numeric` (CONFIRMATORY), plus
`text_and_numeric_exploratory` which adds the 13 red-flag columns and is
tagged exploratory/disclosure-only (owner ruling 2026-08-27) in every
table. The optional embedding block is reduced per fold by a PCA fit on
that fold's TRAINING rows only -- never on test rows. A ratified pca_k > 0
with no usable `emb` column, or any fold that realizes fewer than pca_k
components, is a REFUSAL. The PIT-rank transform of those components is a
PRIMARY-arm decision: the `raw_levels` secondary arm always carries the
untransformed projection.

Metrics: dedup Spearman IC per fold (company-quarter dedup, frozen rule
wrapped on the CIK key) and raw, both always; delta = text+numeric minus
numeric-only. Form-controlled ablation is the honest secondary. Standing
rows beside every IC: the two zero-information predictors, H1's E2-measured
noise floor, and the within-fold bootstrap anchor (4,000 resamples/fold,
both tails).

SE: moving-block bootstrap over folds, block length from the MEASURED lag-1
autocorrelation of the fold deltas; Newey-West reported as the stated
alternative. std/sqrt(k) is computed only to be labelled
`never_used_for_inference`.

THE MARGIN PROCEDURE (decision 15) runs inside this runner in one
non-interactive invocation. Delta = the smallest ladder value whose power
requirement SE <= Delta/2.487 holds, else UNPOWERED (never "equivalent").
It is written to the results JSON, with its inputs, BEFORE any per-fold
delta is serialized or printed -- enforced structurally by `ResultsWriter`,
which raises if a delta-bearing payload is added before the margin block.

Arms reported side by side: full window and the post-2019 sub-window; with
and without filings whose `train_overlap_share > 0` (an evaluation-side
restriction: the fit is unchanged, the scored set shrinks -- stated as an
open question for G3). Primary seed 0 with a nuisance band over seeds
1..100. LOCO per decision 14: 6 folds at round(j*(K-1)/5) over each fold's
training members, DESCRIPTIVE ONLY -- no per-CIK inference at k = 6.

Every run appends {utc, doc_sha256, params_sha256, results_sha256} to
data/f5/run_log.jsonl, so a second run is visible. The markdown report is
generated from the results JSON plus the G2 caveats read from
data/f4/g2/results_g2.json; no number in it is hand-typed.

-----------------------------------------------------------------------
4. What is imported rather than restated
-----------------------------------------------------------------------
FROZEN, imported, never edited:
  spec.pit_trailing_rank_frame / transform_frame / spec_label
  spec.zero_information_benchmarks / zero_information_summary   (ticker_col
      is a parameter -> passed "cik", no wrapper needed)
  spec.bootstrap_noise_anchor (fit callable injected)
  spec.embargo_census
  spec._spearman_or_nan  (NaN-safe Spearman; used so the NaN convention
      cannot drift between this runner and the standing sections)
  backtest.build_walk_forward_folds, assert_no_fold_leakage,
  backtest.company_quarter_dedup_keep_mask (ticker-keyed -> wrapped on CIK),
  backtest.fit_predict, quintile_spread, standing_section_lines,
  backtest.XGB_PARAMS, FORM_ABLATION_FORMS, COMPANY_QUARTER_DEDUP_GAP_DAYS
  controls.mde_from_se (the 2.8x MDE), controls.HOLDING_DAYS

Two frozen functions cannot be called directly and are NOT copied:
  * `backtest.run_backtest` / `run_form_controlled_ablation` bind E1's
    module-global feature-name lists and E1's TARGET_COL. The form
    ablation here reuses the frozen FORM_ABLATION_FORMS ruleset and the
    frozen fold builder, and runs the identical per-fold loop this module
    already runs on the restricted row set.
  * `backtest.fit_predict` fixes `random_state` inside the frozen
    XGB_PARAMS, so the pre-registered seed band cannot be expressed through
    it. `fit_predict_seeded(seed=None)` calls the frozen function verbatim;
    with a seed it constructs the SAME estimator with `random_state`
    overridden and nothing else (pinned by a test that shows the two paths
    agree bit-for-bit at the frozen seed).

The E2 target column is `target_excess_63`; the frame carries it ALSO under
`backtest.TARGET_COL` so the frozen fit path needs no edit. Both names hold
the same values (asserted).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import norm as _norm
from scipy.stats import t as _tdist
from xgboost import XGBRegressor

import backtest as B
import controls as C
import spec as S

REPO_ROOT = Path(__file__).resolve().parent
F5_DIR = REPO_ROOT / "data" / "f5"

TARGET_PATH = F5_DIR / "target_e2.parquet"
TEXT_PATH = F5_DIR / "text_features_e2.parquet"
NUMERIC_PATH = F5_DIR / "numeric_features_e2.parquet"
FAMILIES_PATH = F5_DIR / "text_families_e2.parquet"  # optional, built in parallel

TARGET_MANIFEST = F5_DIR / "target_e2_manifest.json"
TEXT_MANIFEST = F5_DIR / "text_features_e2_manifest.json"
NUMERIC_MANIFEST = F5_DIR / "numeric_features_e2_manifest.json"
FAMILIES_MANIFEST = F5_DIR / "text_families_e2_manifest.json"

G3_DOC_PATH = F5_DIR / "G3_PREREGISTRATION.md"
G3_RATIFIED_PATH = F5_DIR / "G3_RATIFIED.json"
PARAMS_SCHEMA_PATH = F5_DIR / "G3_PARAMS_SCHEMA.json"
RUN_LOG_PATH = F5_DIR / "run_log.jsonl"
CENSUS_PATH = F5_DIR / "census_head1.json"
RESULTS_PATH = F5_DIR / "results_head1.json"
REPORT_PATH = F5_DIR / "report_head1.md"

G2_RESULTS_PATH = REPO_ROOT / "data" / "f4" / "g2" / "results_g2.json"
H1_CONTROLS_PATH = REPO_ROOT / "data" / "hardening" / "controls_results.json"

KEY = ["cik", "accession_number"]
E2_TARGET_COL = "target_excess_63"
FILING_DATE_COL = B.FILING_DATE_COL  # "filing_date"
CIK_COL = "cik"
WINDOW_CLOSE_COL = "window_close_session"

FENCE_INFO = "json g3-params"
PARAMS_VERSION = "g3-params-1"

#: Implemented named rules. Anything else in the document is a REFUSAL --
#: never a silent fallback (a named rule with no implementation is exactly
#: the "a name is not a pre-registration" failure H2 measured).
IMPLEMENTED_PURGE_RULES = ("target_window_close_on_or_after_test_quarter_start",)
IMPLEMENTED_BLOCK_RULES = ("ceil_k13_ac1",)
IMPLEMENTED_SE_METHODS = ("moving_block_bootstrap",)
IMPLEMENTED_SE_ALTERNATIVES = ("newey_west",)
IMPLEMENTED_TOST_DISTS = ("normal", "t")
#: The literal string F5_PLAN decision 14 pins is `round(j*(K-1)/5)`, which is
#: the general form at loco.n_folds = 6. Both spellings are accepted; the
#: literal one is REFUSED at any other fold count, because a formula that no
#: longer matches its own budget is exactly the silent drift this file exists
#: to prevent.
IMPLEMENTED_LOCO_RULES = ("round(j*(K-1)/5)", "round(j*(K-1)/(n_folds-1))")

#: The fixed scope sentence every claim carries (F5_PLAN §2 Step 3).
SCOPE_SENTENCE = (
    "No text-vs-numeric IC improvement of economically relevant size is detectable "
    "in this universe through this labeling schema, these features, this labeler, "
    "and this feature specification."
)

INCOMPARABLE_SENTENCE = (
    "E1 and E2 backtest numbers are numerically incomparable: E2's benchmark is the "
    "membership-dated equal-weighted average over that date's members excluding self."
)

#: Required parameter paths, as (dotted path, python type or tuple of types).
REQUIRED_PARAMS: tuple[tuple[str, object], ...] = (
    ("params_version", str),
    ("fold_quarters", list),
    ("post_2019_first_quarter", str),
    ("purge_rule", str),
    ("spec.window_days", int),
    ("spec.min_comparators", int),
    ("spec.include_same_day", bool),
    ("spec.same_day_sensitivity_arm", bool),
    ("spec.secondary", str),
    ("columns.numeric", list),
    ("columns.confirmatory_text", list),
    ("columns.exploratory_red_flags", list),
    ("columns.family_novelty", list),
    ("columns.size_col", str),
    ("embedding.pca_k", int),
    ("embedding.rank_transform_components", bool),
    ("dedup.gap_days", int),
    ("form_ablation_forms", list),
    ("margin.ladder", list),
    ("margin.power_divisor", (int, float)),
    ("margin.mde_multiplier", (int, float)),
    ("margin.kc3_flag_above", (int, float)),
    ("se.method", str),
    ("se.block_length_rule", str),
    ("se.n_resamples", int),
    ("se.seed", int),
    ("se.alternative", str),
    ("tost.alpha", (int, float)),
    ("tost.ci_level", (int, float)),
    ("tost.reference_distribution", str),
    ("bootstrap_anchor.n_resamples", int),
    ("bootstrap_anchor.seed", int),
    ("seeds.primary", int),
    ("seeds.nuisance_band", list),
    ("loco.n_folds", int),
    ("loco.index_rule", str),
    ("loco.scope", str),
    ("overlap.column", str),
    ("overlap.threshold", (int, float)),
    ("head2.event_window_sessions", list),
    ("head2.trailing_sessions", int),
    ("head3.horizon_quarters", int),
    ("head3.metric", str),
)

#: F5_PLAN §3 defaults -- THE SELFTEST'S VALUES ONLY. These are a synthetic
#: fixture. The real run never reads this dict (a test pins that).
SELFTEST_PARAMS: dict = {
    "params_version": PARAMS_VERSION,
    "fold_quarters": [],  # filled by the selftest from the synthetic frame
    "post_2019_first_quarter": "",
    "purge_rule": IMPLEMENTED_PURGE_RULES[0],
    "spec": {
        "window_days": S.PIT_RANK_WINDOW_DAYS,
        "min_comparators": S.MIN_COMPARATORS,
        "include_same_day": True,
        "same_day_sensitivity_arm": True,
        "secondary": S.SECONDARY_SPEC,
    },
    "columns": {
        "numeric": [],
        "confirmatory_text": [],
        "exploratory_red_flags": [],
        "family_novelty": [],
        "size_col": "log_total_assets",
    },
    "embedding": {"pca_k": 3, "rank_transform_components": False},
    "dedup": {"gap_days": B.COMPANY_QUARTER_DEDUP_GAP_DAYS},
    "form_ablation_forms": sorted(B.FORM_ABLATION_FORMS),
    "margin": {
        "ladder": [0.03, 0.04, 0.05],
        "power_divisor": 2.487,
        "mde_multiplier": 2.8,
        "kc3_flag_above": 0.03,
    },
    "se": {
        "method": "moving_block_bootstrap",
        "block_length_rule": "ceil_k13_ac1",
        "n_resamples": 400,
        "seed": 0,
        "alternative": "newey_west",
    },
    "tost": {"alpha": 0.05, "ci_level": 0.90, "reference_distribution": "normal"},
    "bootstrap_anchor": {"n_resamples": 200, "seed": 0},
    "seeds": {"primary": 0, "nuisance_band": [1, 3]},
    "loco": {
        "n_folds": 2,
        "index_rule": "round(j*(K-1)/(n_folds-1))",
        "scope": "per_fold_training_members",
        "max_ciks_per_fold": 3,
    },
    "overlap": {"column": "train_overlap_share", "threshold": 0.0},
    "head2": {"event_window_sessions": [1, 5], "trailing_sessions": 60},
    "head3": {"horizon_quarters": 4, "metric": "auc"},
}


class G3Refusal(RuntimeError):
    """The freeze guard refused. Never caught-and-defaulted anywhere."""


class OrderingViolation(RuntimeError):
    """A per-fold delta was about to be serialized before the margin block."""


# ---------------------------------------------------------------------------
# 1. Provenance: sha256 assertions (controls.py `_sha256_file` pattern)
# ---------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def sha256_obj(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def manifest_recorded_sha(manifest_path: Path) -> str:
    """The artifact sha256 a data/f5 manifest records. The three Step-1a
    manifests use three different key conventions; all three are read here,
    and an unrecognised manifest is an error rather than a skipped check."""
    man = json.loads(Path(manifest_path).read_text())
    for key in ("output_sha256", "artifact_sha256"):
        if key in man:
            return str(man[key])
    out = man.get("output")
    if isinstance(out, dict) and "sha256" in out:
        return str(out["sha256"])
    raise KeyError(f"{manifest_path.name}: no artifact sha256 key found")


def assert_input_shas(paths_and_manifests: list[tuple[Path, Path]]) -> dict:
    """Assert each parquet's measured sha256 equals its manifest's record."""
    checked = {}
    for data_path, manifest_path in paths_and_manifests:
        measured = sha256_file(data_path)
        recorded = manifest_recorded_sha(manifest_path)
        if measured != recorded:
            raise AssertionError(
                f"{data_path.name}: sha256 {measured} != manifest record {recorded}. "
                "A changed input frame is a NEW pre-registration, not a re-run."
            )
        checked[data_path.name] = measured
    return checked


# ---------------------------------------------------------------------------
# 2. The freeze guard + the pre-registered parameter block
# ---------------------------------------------------------------------------


def require_g3(
    doc_path: Path = G3_DOC_PATH, ratified_path: Path = G3_RATIFIED_PATH
) -> dict:
    """Return {"doc_sha256", "ratified"} or raise G3Refusal.

    Refusal is deliberate, not a crash: fitting anything before the
    pre-registration is ratified lets the specification be chosen after
    seeing the result. There is no default that permits an unratified run.
    """
    doc_path, ratified_path = Path(doc_path), Path(ratified_path)
    if not ratified_path.exists():
        raise G3Refusal(
            f"BLOCKED: {ratified_path} does not exist. The G3 pre-registration has not "
            "been owner-ratified, so no model may be fit and no IC may be computed on "
            "E2 data (F5_PLAN §1). Allowed today: --census and --selftest."
        )
    if not doc_path.exists():
        raise G3Refusal(
            f"BLOCKED: {ratified_path.name} exists but {doc_path} does not. A ratification "
            "without the document it ratifies pins nothing."
        )
    ratified = json.loads(ratified_path.read_text())
    claimed = ratified.get("doc_sha256")
    measured = sha256_file(doc_path)
    if not claimed:
        raise G3Refusal(
            f"BLOCKED: {ratified_path.name} carries no doc_sha256. The ratification does "
            "not pin a document."
        )
    if claimed != measured:
        raise G3Refusal(
            f"BLOCKED: {doc_path.name} sha256 {measured} != ratified doc_sha256 {claimed}. "
            "The document changed after ratification; that is a NEW pre-registration, not "
            "a re-run."
        )
    return {"doc_sha256": measured, "ratified": ratified}


def extract_params_block(doc_text: str) -> dict:
    """Parse the single ```json g3-params fenced block out of the document."""
    lines = doc_text.splitlines()
    blocks, i = [], 0
    open_fence = "```" + FENCE_INFO
    while i < len(lines):
        if lines[i].strip() == open_fence:
            j, buf = i + 1, []
            while j < len(lines) and lines[j].strip() != "```":
                buf.append(lines[j])
                j += 1
            if j >= len(lines):
                raise G3Refusal("BLOCKED: unterminated ```json g3-params fenced block.")
            blocks.append("\n".join(buf))
            i = j + 1
        else:
            i += 1
    if len(blocks) != 1:
        raise G3Refusal(
            f"BLOCKED: expected exactly one ```{FENCE_INFO} fenced block in the "
            f"pre-registration, found {len(blocks)}. Parameters must be unambiguous."
        )
    try:
        params = json.loads(blocks[0])
    except json.JSONDecodeError as exc:
        raise G3Refusal(f"BLOCKED: the g3-params block is not valid JSON: {exc}") from exc
    return params


def _dig(params: dict, dotted: str):
    node = params
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None, False
        node = node[part]
    return node, True


def validate_params(params: dict) -> dict:
    """Presence + type + named-rule validation. Any failure is a REFUSAL."""
    problems = []
    for dotted, typ in REQUIRED_PARAMS:
        value, found = _dig(params, dotted)
        if not found:
            problems.append(f"missing key {dotted!r}")
            continue
        if typ is int and isinstance(value, bool):
            problems.append(f"{dotted!r} must be an int, got a bool")
        elif not isinstance(value, typ):
            problems.append(f"{dotted!r} must be {typ}, got {type(value).__name__}")
    if problems:
        raise G3Refusal("BLOCKED: the g3-params block is incomplete: " + "; ".join(problems))

    if params["params_version"] != PARAMS_VERSION:
        raise G3Refusal(
            f"BLOCKED: params_version {params['params_version']!r} != {PARAMS_VERSION!r}."
        )
    named = (
        ("purge_rule", params["purge_rule"], IMPLEMENTED_PURGE_RULES),
        ("se.method", params["se"]["method"], IMPLEMENTED_SE_METHODS),
        ("se.block_length_rule", params["se"]["block_length_rule"], IMPLEMENTED_BLOCK_RULES),
        ("se.alternative", params["se"]["alternative"], IMPLEMENTED_SE_ALTERNATIVES),
        (
            "tost.reference_distribution",
            params["tost"]["reference_distribution"],
            IMPLEMENTED_TOST_DISTS,
        ),
        ("spec.secondary", params["spec"]["secondary"], (S.SECONDARY_SPEC,)),
        ("loco.index_rule", params["loco"]["index_rule"], IMPLEMENTED_LOCO_RULES),
    )
    for key, value, allowed in named:
        if value not in allowed:
            raise G3Refusal(
                f"BLOCKED: {key} = {value!r} has no implementation here (implemented: "
                f"{list(allowed)}). A named rule with no implementation pre-registers nothing."
            )
    if not params["fold_quarters"]:
        raise G3Refusal("BLOCKED: fold_quarters is empty; the fold structure is not pinned.")
    if not params["margin"]["ladder"]:
        raise G3Refusal("BLOCKED: margin.ladder is empty; the margin procedure is not pinned.")
    if params["loco"]["index_rule"] == "round(j*(K-1)/5)" and int(params["loco"]["n_folds"]) != 6:
        raise G3Refusal(
            "BLOCKED: loco.index_rule pins the divisor 5 (i.e. 6 folds) but loco.n_folds = "
            f"{params['loco']['n_folds']}. Use round(j*(K-1)/(n_folds-1)) if a different budget "
            "is intended; a formula that disagrees with its own budget pins nothing."
        )
    return params


def load_g3_params(
    doc_path: Path = G3_DOC_PATH, ratified_path: Path = G3_RATIFIED_PATH
) -> tuple[dict, dict]:
    """(params, guard). Guard first, then params -- never the other way."""
    guard = require_g3(doc_path, ratified_path)
    params = validate_params(extract_params_block(Path(doc_path).read_text()))
    guard["params_sha256"] = sha256_obj(params)
    return params, guard


def write_params_schema(path: Path = PARAMS_SCHEMA_PATH) -> dict:
    """Materialize the machine-readable schema beside the runner."""
    schema = {
        "schema_version": PARAMS_VERSION,
        "consumer": "backtest_e2.py (head 1); heads 2 and 3 read head2.*/head3.*",
        "location": "exactly one fenced code block with info string "
        f"`{FENCE_INFO}` inside data/f5/G3_PREREGISTRATION.md",
        "guard": "data/f5/G3_RATIFIED.json.doc_sha256 == sha256(G3_PREREGISTRATION.md)",
        "required_keys": [
            {"path": p, "type": (t.__name__ if isinstance(t, type) else "|".join(x.__name__ for x in t))}
            for p, t in REQUIRED_PARAMS
        ],
        "implemented_named_rules": {
            "purge_rule": list(IMPLEMENTED_PURGE_RULES),
            "se.method": list(IMPLEMENTED_SE_METHODS),
            "se.block_length_rule": list(IMPLEMENTED_BLOCK_RULES),
            "se.alternative": list(IMPLEMENTED_SE_ALTERNATIVES),
            "tost.reference_distribution": list(IMPLEMENTED_TOST_DISTS),
        },
        "optional_keys": [
            {"path": "loco.max_ciks_per_fold", "type": "int|null",
             "note": "LOCO budget cap; null means every training member of the selected folds."}
        ],
        "notes": [
            "Unknown keys are echoed into the results JSON and never consulted.",
            "No value here is a default: the runner refuses without the ratified document.",
            "F5_PLAN §3's defaults are the SELFTEST's values only.",
            "embedding.rank_transform_components applies to the PIT-ranked spec arms only; "
            "the raw_levels secondary arm always carries the untransformed PCA projection.",
            "embedding.pca_k > 0 with no usable `emb` column in the analysis frame is a "
            "REFUSAL, as is any fold realizing fewer than pca_k components.",
        ],
    }
    Path(path).write_text(json.dumps(schema, indent=2) + "\n")
    return schema


# ---------------------------------------------------------------------------
# 3. The analysis frame
# ---------------------------------------------------------------------------


def join_frames(
    target: pd.DataFrame,
    text: pd.DataFrame,
    numeric: pd.DataFrame,
    families: Optional[pd.DataFrame] = None,
) -> tuple[pd.DataFrame, dict]:
    """Inner join on (cik, accession_number), in_membership rows only.

    `families` (novelty + pooled embeddings) is joined LEFT when present so a
    filing missing an embedding keeps its row and gets NaN components, and the
    missing count is reported rather than silently dropping rows."""
    diag = {
        "n_target_rows": int(len(target)),
        "n_text_rows": int(len(text)),
        "n_numeric_rows": int(len(numeric)),
        "n_families_rows": int(len(families)) if families is not None else None,
    }
    tgt = target[target["in_membership"].astype(bool)].copy()
    diag["n_target_in_membership"] = int(len(tgt))

    drop_dupes = [c for c in ("filing_date", "form", "acceptance_datetime", "info_date",
                              "post_close", "news_session") if c in text.columns]
    txt = text.drop(columns=drop_dupes)
    drop_dupes_n = [c for c in ("filing_date", "form", "acceptance_datetime", "info_date",
                                "post_close", "news_session") if c in numeric.columns]
    num = numeric.drop(columns=drop_dupes_n)

    df = tgt.merge(txt, on=KEY, how="inner").merge(num, on=KEY, how="inner")
    diag["n_joined"] = int(len(df))

    diag["n_emb_missing"] = None
    if families is not None:
        fam = families.drop(columns=[c for c in ("filing_date", "form") if c in families.columns])
        df = df.merge(fam, on=KEY, how="left")
        if "emb" in df.columns:
            diag["n_emb_missing"] = int(df["emb"].isna().sum())
    diag["n_after_families_join"] = int(len(df))

    df[FILING_DATE_COL] = pd.to_datetime(df[FILING_DATE_COL])
    # Stable, fully-determined order. `spec.pit_trailing_rank_frame` REQUIRES
    # ascending filing_date; (cik, accession) break ties so the row order --
    # and therefore every downstream fold index -- is reproducible.
    df = df.sort_values([FILING_DATE_COL, CIK_COL, "accession_number"], kind="mergesort")
    df = df.reset_index(drop=True)

    diag["n_target_null"] = int(df[E2_TARGET_COL].isna().sum())
    modeling = df[df[E2_TARGET_COL].notna()].copy().reset_index(drop=True)
    diag["n_modeling_rows"] = int(len(modeling))
    diag["n_ciks"] = int(modeling[CIK_COL].nunique())
    if len(modeling):
        diag["first_filing_date"] = str(modeling[FILING_DATE_COL].min().date())
        diag["last_filing_date"] = str(modeling[FILING_DATE_COL].max().date())

    # The frozen fit path reads `backtest.TARGET_COL`; carry the same values
    # under both names so no frozen module needs editing.
    modeling[B.TARGET_COL] = modeling[E2_TARGET_COL].astype(float)
    assert modeling[B.TARGET_COL].equals(modeling[E2_TARGET_COL].astype(float))
    return modeling, diag


def load_analysis_frame(
    target_path: Path = TARGET_PATH,
    text_path: Path = TEXT_PATH,
    numeric_path: Path = NUMERIC_PATH,
    families_path: Path = FAMILIES_PATH,
    assert_shas: bool = True,
) -> tuple[pd.DataFrame, dict]:
    pairs = [
        (Path(target_path), TARGET_MANIFEST),
        (Path(text_path), TEXT_MANIFEST),
        (Path(numeric_path), NUMERIC_MANIFEST),
    ]
    families = None
    fam_path = Path(families_path)
    if fam_path.exists():
        families = pd.read_parquet(fam_path)
        if FAMILIES_MANIFEST.exists():
            pairs.append((fam_path, FAMILIES_MANIFEST))
    shas = assert_input_shas(pairs) if assert_shas else {p.name: None for p, _ in pairs}

    df, diag = join_frames(
        pd.read_parquet(target_path),
        pd.read_parquet(text_path),
        pd.read_parquet(numeric_path),
        families,
    )
    diag["input_sha256"] = shas
    diag["families_present"] = families is not None
    return df, diag


def dedup_keep_mask_cik(df: pd.DataFrame, gap_days: int) -> pd.Series:
    """Company-quarter dedup keep mask on the CIK key.

    `backtest.company_quarter_dedup_keep_mask` is ticker-keyed (E2 labels
    carry no ticker). It is WRAPPED, never copied: the frame is handed to the
    frozen function with `ticker` bound to the CIK string, so the frozen
    clustering, the later-filing rule and the form-aware same-day tiebreak
    are exactly the published ones."""
    keyed = df.assign(ticker=df[CIK_COL].astype(str))
    mask = B.company_quarter_dedup_keep_mask(keyed, gap_days=gap_days)
    return mask.reindex(df.index)


# ---------------------------------------------------------------------------
# 4. Folds + purge
# ---------------------------------------------------------------------------


def quarter_of(label: str) -> pd.Period:
    return pd.Period(str(label), freq="Q")


def build_folds(
    df: pd.DataFrame,
    quarters: list[str],
    purge_rule: str = IMPLEMENTED_PURGE_RULES[0],
) -> tuple[list[dict], list[dict]]:
    """Expanding-window quarterly folds restricted to the ratified quarter
    list, with the pre-registered purge applied to the training rows.

    The fold SET comes from the frozen `backtest.build_walk_forward_folds`
    (burn-in = the first ratified test quarter's start); this function only
    selects the ratified quarters and purges. Purge: drop training rows whose
    63-session target window closes on or after the test quarter's first
    session. `window_close_session` is always a trading session, so comparing
    against the quarter's first CALENDAR day selects exactly the same rows --
    pinned by `test_backtest_e2.py::test_purge_calendar_start_equals_first_session`.
    """
    if purge_rule not in IMPLEMENTED_PURGE_RULES:
        raise G3Refusal(f"BLOCKED: purge_rule {purge_rule!r} has no implementation here.")
    wanted = [quarter_of(q) for q in quarters]
    burn_in_end = wanted[0].start_time
    all_folds = B.build_walk_forward_folds(df, burn_in_end)
    by_quarter = {f["test_quarter"]: f for f in all_folds}
    missing = [str(q) for q in wanted if q not in by_quarter]
    if missing:
        raise G3Refusal(
            f"BLOCKED: the ratified fold quarters {missing} have no usable fold on this "
            "frame (no test rows, or no training rows). The fold list cannot be adjusted "
            "after ratification; this is a data/ratification mismatch to be ruled on."
        )
    closes = pd.to_datetime(df[WINDOW_CLOSE_COL]).values if WINDOW_CLOSE_COL in df.columns else None

    folds, purge_rows = [], []
    for q in wanted:
        fold = by_quarter[q]
        train_idx = fold["train_idx"]
        n_before = len(train_idx)
        if closes is not None:
            cutoff = np.datetime64(q.start_time.to_datetime64())
            train_closes = closes[train_idx]
            keep = ~(train_closes >= cutoff)
            # A training row with an unknown close date has no resolved label
            # and is already absent from the modeling frame; treat NaT as keep
            # so the rule never silently drops an unexplained row.
            keep = keep | pd.isna(train_closes)
            train_idx = train_idx[keep]
        purge_rows.append(
            {
                "test_quarter": str(q),
                "n_train_before_purge": int(n_before),
                "n_train_after_purge": int(len(train_idx)),
                "n_purged": int(n_before - len(train_idx)),
                "share_purged": float((n_before - len(train_idx)) / n_before) if n_before else float("nan"),
            }
        )
        if len(train_idx) == 0:
            raise G3Refusal(
                f"BLOCKED: fold {q} has no training rows left after the purge. The purge "
                "rule and the fold list are both pre-registered; neither is adjustable here."
            )
        folds.append({"test_quarter": q, "train_idx": train_idx, "test_idx": fold["test_idx"]})
    B.assert_no_fold_leakage(df, folds)
    return folds, purge_rows


# ---------------------------------------------------------------------------
# 5. Model fitting, per-fold metrics
# ---------------------------------------------------------------------------


def fit_predict_seeded(
    df: pd.DataFrame, feature_cols: list[str], train_idx, test_idx, seed: Optional[int] = None
) -> np.ndarray:
    """`backtest.fit_predict` with the ONE pre-registered nuisance parameter
    (`random_state`) exposed. `seed=None` calls the frozen function verbatim."""
    if seed is None:
        return B.fit_predict(df, feature_cols, train_idx, test_idx)
    params = dict(B.XGB_PARAMS)
    params["random_state"] = int(seed)
    model = XGBRegressor(**params)
    model.fit(
        df.loc[train_idx, feature_cols].astype(float).values,
        df.loc[train_idx, B.TARGET_COL].astype(float).values,
    )
    return model.predict(df.loc[test_idx, feature_cols].astype(float).values)


def pca_project(emb: np.ndarray, train_pos: np.ndarray, k: int) -> tuple[np.ndarray, dict]:
    """PCA fit on TRAINING rows only, applied to every row.

    Centering mean and loadings come from `emb[train_pos]` exclusively; test
    rows are projected, never fitted. Component signs are pinned by the
    largest-magnitude loading so the output is deterministic across runs and
    platforms. Rows with any non-finite embedding get NaN components (and are
    excluded from the fit)."""
    emb = np.asarray(emb, dtype=float)
    ok = np.isfinite(emb).all(axis=1)
    fit_pos = np.asarray([p for p in train_pos if ok[p]], dtype=int)
    k = int(min(k, emb.shape[1], max(len(fit_pos) - 1, 0)))
    out = np.full((emb.shape[0], max(k, 0)), np.nan, dtype=float)
    if k <= 0 or len(fit_pos) < 2:
        return out, {"k_effective": 0, "n_fit_rows": int(len(fit_pos))}
    mu = emb[fit_pos].mean(axis=0)
    _, sv, vt = np.linalg.svd(emb[fit_pos] - mu, full_matrices=False)
    v = vt[:k]
    lead = np.abs(v).argmax(axis=1)
    signs = np.sign(v[np.arange(k), lead])
    signs[signs == 0] = 1.0
    v = v * signs[:, None]
    proj = (emb[ok] - mu) @ v.T
    out[ok] = proj
    total = float((sv ** 2).sum())
    return out, {
        "k_effective": int(k),
        "n_fit_rows": int(len(fit_pos)),
        "explained_variance_share": float((sv[:k] ** 2).sum() / total) if total > 0 else float("nan"),
    }


def embedding_matrix(df: pd.DataFrame, col: str = "emb") -> Optional[np.ndarray]:
    if col not in df.columns:
        return None
    lengths = {len(v) for v in df[col] if isinstance(v, (list, np.ndarray))}
    if not lengths:
        return None  # the column exists but carries no embedding on any row
    if len(lengths) != 1:
        raise AssertionError(f"embedding column {col!r} is not fixed-width: widths {sorted(lengths)}")
    width = lengths.pop()
    out = np.full((len(df), width), np.nan, dtype=float)
    for i, v in enumerate(df[col].values):
        if isinstance(v, (list, np.ndarray)) and len(v) == width:
            out[i] = np.asarray(v, dtype=float)
    return out


def eval_masks_for_fold(
    df: pd.DataFrame, fold: dict, keep_values: np.ndarray, overlap_col: str, threshold: float
) -> dict[str, np.ndarray]:
    """Positional masks over the fold's test rows: raw / dedup /
    dedup-excluding-overlap. The overlap arm is an EVALUATION-side
    restriction (the fit is unchanged); whether training should also drop
    those filings is an open question for G3."""
    test_idx = fold["test_idx"]
    n = len(test_idx)
    raw = np.ones(n, dtype=bool)
    dedup = keep_values[test_idx].astype(bool)
    if overlap_col in df.columns:
        ov = df.loc[test_idx, overlap_col].astype(float).values
        no_overlap = dedup & ~(ov > threshold)
    else:
        no_overlap = dedup.copy()
    return {"raw": raw, "dedup": dedup, "dedup_no_overlap": no_overlap}


def build_fold_frames(
    frame: pd.DataFrame,
    folds: list[dict],
    emb: Optional[np.ndarray],
    emb_k: int,
    emb_rank_transform: bool,
    spec_kwargs: Optional[dict],
) -> list[dict]:
    """One modeling frame per fold, with the optional embedding block reduced
    by a PCA fit on THAT FOLD'S TRAINING ROWS ONLY.

    Built once and shared by the IC loop, the seed band and LOCO, so all three
    score the identical feature block (and so the PCA is not refit per seed --
    it does not depend on the model seed).

    `emb_rank_transform` is decided by the CALLER per arm: the ratified
    `embedding.rank_transform_components` governs the PIT-ranked spec arms, and
    the `raw_levels` secondary arm is always passed False (see `run_head1`).
    A raw arm whose components had been rank-transformed would not be raw."""
    out = []
    for fold in folds:
        entry = {"fold": fold, "frame": frame, "emb_cols": [], "pca": None}
        if emb is not None and emb_k > 0:
            comps, info = pca_project(emb, fold["train_idx"], emb_k)
            info["test_quarter"] = str(fold["test_quarter"])
            entry["pca"] = info
            cols = [f"emb_pc{i+1}" for i in range(comps.shape[1])]
            if cols:
                fold_frame = frame.copy()
                for i, col in enumerate(cols):
                    fold_frame[col] = comps[:, i]
                if emb_rank_transform:
                    used = np.unique(np.concatenate([fold["train_idx"], fold["test_idx"]]))
                    sub = fold_frame.loc[used]
                    ranked = S.pit_trailing_rank_frame(sub, cols, **(spec_kwargs or {}))
                    fold_frame.loc[ranked.index, cols] = ranked[cols].values
                entry["frame"], entry["emb_cols"] = fold_frame, cols
        out.append(entry)
    return out


def blocks_for_fold(blocks: dict[str, list[str]], emb_cols: list[str]) -> dict[str, list[str]]:
    """The embedding components join the text blocks (F5_PLAN: the pooled
    embeddings are part of the confirmatory text block), never the baseline."""
    return {
        name: list(cols) + (list(emb_cols) if name != "numeric_only" else [])
        for name, cols in blocks.items()
    }


def evaluate_arm(
    frame: pd.DataFrame,
    fold_frames: list[dict],
    blocks: dict[str, list[str]],
    keep_values: np.ndarray,
    overlap_col: str,
    overlap_threshold: float,
    seed: Optional[int],
) -> tuple[list[dict], dict]:
    """Per-fold fit + IC for every block. Returns (rows, diagnostics).

    Nothing here is printed or serialized; the caller decides ordering."""
    rows: list[dict] = []
    pca_diag = []
    for entry in fold_frames:
        fold = entry["fold"]
        fold_frame = entry["frame"]
        test_idx, train_idx = fold["test_idx"], fold["train_idx"]
        realized = frame.loc[test_idx, B.TARGET_COL].astype(float).values
        masks = eval_masks_for_fold(frame, fold, keep_values, overlap_col, overlap_threshold)
        if entry["pca"]:
            pca_diag.append(entry["pca"])

        preds = {}
        for name, cols in blocks_for_fold(blocks, entry["emb_cols"]).items():
            preds[name] = np.asarray(
                fit_predict_seeded(fold_frame, cols, train_idx, test_idx, seed), dtype=float
            )

        for name, pred in preds.items():
            for mask_name, mask in masks.items():
                ic, p, n_used = S._spearman_or_nan(pred[mask], realized[mask])
                spread, n_top, n_bot = B.quintile_spread(pred[mask], realized[mask])
                rows.append(
                    {
                        "test_quarter": str(fold["test_quarter"]),
                        "n_emb_components": int(len(entry["emb_cols"])),
                        "block": name,
                        "eval_set": mask_name,
                        "n_train": int(len(train_idx)),
                        "n_test": int(mask.sum()),
                        "n_used": int(n_used),
                        "n_test_ciks": int(frame.loc[test_idx[mask], CIK_COL].nunique()),
                        "spearman_ic": ic,
                        "spearman_p": p,
                        "quintile_spread": spread,
                        "n_top": int(n_top),
                        "n_bottom": int(n_bot),
                    }
                )
    return rows, {"pca_per_fold": pca_diag}


def fold_deltas(rows: list[dict], eval_set: str, block: str, baseline: str = "numeric_only") -> pd.DataFrame:
    """Per-fold (block - baseline) IC deltas on one evaluation set."""
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["test_quarter", "ic_baseline", "ic_block", "delta"])
    sub = df[df["eval_set"] == eval_set]
    a = sub[sub["block"] == block].set_index("test_quarter")
    b = sub[sub["block"] == baseline].set_index("test_quarter")
    idx = [q for q in b.index if q in a.index]
    return pd.DataFrame(
        {
            "test_quarter": idx,
            "n_test": b.loc[idx, "n_test"].values,
            "ic_baseline": b.loc[idx, "spearman_ic"].values,
            "ic_block": a.loc[idx, "spearman_ic"].values,
            "delta": (a.loc[idx, "spearman_ic"] - b.loc[idx, "spearman_ic"]).values,
        }
    )


# ---------------------------------------------------------------------------
# 6. SE over folds, the margin procedure, TOST
# ---------------------------------------------------------------------------


def lag1_autocorr(x: np.ndarray) -> float:
    x = np.asarray([v for v in x if np.isfinite(v)], dtype=float)
    if len(x) < 3:
        return float("nan")
    xc = x - x.mean()
    denom = float((xc * xc).sum())
    if denom <= 0:
        return float("nan")
    return float((xc[:-1] * xc[1:]).sum() / denom)


def block_length(ac1: float, k: int, rule: str) -> int:
    """`ceil_k13_ac1`: L = 1 when the measured lag-1 autocorrelation is <= 0,
    else ceil(k**(1/3) * (2*rho/(1-rho))**(2/3)), capped at k. The rule is
    named in the pre-registration; an unnamed rule is a refusal."""
    if rule not in IMPLEMENTED_BLOCK_RULES:
        raise G3Refusal(f"BLOCKED: se.block_length_rule {rule!r} has no implementation here.")
    if not np.isfinite(ac1) or ac1 <= 0:
        return 1
    rho = min(float(ac1), 0.99)
    val = (k ** (1.0 / 3.0)) * ((2.0 * rho / (1.0 - rho)) ** (2.0 / 3.0))
    return int(max(1, min(k, np.ceil(val))))


def moving_block_bootstrap_se(x: np.ndarray, length: int, n_resamples: int, seed: int) -> float:
    """SE of the mean by moving-block bootstrap. Never std/sqrt(k)."""
    x = np.asarray([v for v in x if np.isfinite(v)], dtype=float)
    k = len(x)
    if k < 2:
        return float("nan")
    length = int(max(1, min(length, k)))
    starts = np.arange(0, k - length + 1)
    n_blocks = int(np.ceil(k / length))
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(starts), size=(n_resamples, n_blocks))
    offsets = np.arange(length)
    means = np.empty(n_resamples, dtype=float)
    for r in range(n_resamples):
        idx = (starts[picks[r]][:, None] + offsets[None, :]).ravel()[:k]
        means[r] = x[idx].mean()
    return float(means.std(ddof=1))


def newey_west_se(x: np.ndarray, lag: int) -> float:
    """Newey-West SE of the mean with Bartlett weights -- the stated
    alternative estimator, reported beside the block bootstrap."""
    x = np.asarray([v for v in x if np.isfinite(v)], dtype=float)
    k = len(x)
    if k < 2:
        return float("nan")
    xc = x - x.mean()
    gamma0 = float((xc * xc).sum() / k)
    total = gamma0
    for l in range(1, int(max(0, lag)) + 1):
        if l >= k:
            break
        gl = float((xc[:-l] * xc[l:]).sum() / k)
        total += 2.0 * (1.0 - l / (lag + 1.0)) * gl
    if total <= 0:
        return float("nan")
    return float(np.sqrt(total / k))


def tost(mean: float, se: float, margin: float, alpha: float, ci_level: float, dist: str, k: int) -> dict:
    """TOST + the equivalent CI, which is ALWAYS reported (including when
    equivalence fails and when the design is UNPOWERED)."""
    if dist not in IMPLEMENTED_TOST_DISTS:
        raise G3Refusal(f"BLOCKED: tost.reference_distribution {dist!r} not implemented.")
    if dist == "normal":
        crit = float(_norm.ppf(0.5 + ci_level / 2.0))
        sf = lambda t: float(_norm.sf(t))
        cdf = lambda t: float(_norm.cdf(t))
    else:
        dof = max(k - 1, 1)
        crit = float(_tdist.ppf(0.5 + ci_level / 2.0, dof))
        sf = lambda t: float(_tdist.sf(t, dof))
        cdf = lambda t: float(_tdist.cdf(t, dof))
    lo, hi = mean - crit * se, mean + crit * se
    out = {
        "mean_delta": float(mean),
        "se": float(se),
        "reference_distribution": dist,
        "ci_level": float(ci_level),
        "critical_value": crit,
        "ci_lo": float(lo),
        "ci_hi": float(hi),
        "alpha": float(alpha),
    }
    if margin is None or not np.isfinite(se) or se <= 0:
        out.update(
            {
                "margin": margin,
                "p_lower": float("nan"),
                "p_upper": float("nan"),
                "p_tost": float("nan"),
                "equivalence": None,
                "note": "no equivalence claim: the design is UNPOWERED at every ladder value "
                "(or the SE is undefined). The CI above is still the result.",
            }
        )
        return out
    p_lower = sf((mean + margin) / se)   # H0: mu <= -margin
    p_upper = cdf((mean - margin) / se)  # H0: mu >= +margin
    p_tost = max(p_lower, p_upper)
    out.update(
        {
            "margin": float(margin),
            "p_lower": p_lower,
            "p_upper": p_upper,
            "p_tost": p_tost,
            "equivalence": bool(p_tost < alpha and lo > -margin and hi < margin),
            "note": "equivalence iff the CI lies entirely inside +/- margin.",
        }
    )
    return out


def margin_procedure(deltas: np.ndarray, params: dict) -> dict:
    """Decision 15, executed BEFORE any per-fold delta is serialized/printed.

    Delta = the smallest ladder value whose power requirement
    SE <= Delta/power_divisor holds; otherwise UNPOWERED and no equivalence
    claim is made. The implied MDE (mde_multiplier x SE) is printed beside any
    selected Delta above `kc3_flag_above`, flagged as the KC3 branch."""
    x = np.asarray([v for v in np.asarray(deltas, dtype=float) if np.isfinite(v)], dtype=float)
    k = int(len(x))
    mean = float(x.mean()) if k else float("nan")
    ac1 = lag1_autocorr(x)
    length = block_length(ac1, k, params["se"]["block_length_rule"]) if k >= 2 else 1
    se = moving_block_bootstrap_se(x, length, int(params["se"]["n_resamples"]), int(params["se"]["seed"]))
    se_alt = newey_west_se(x, max(length - 1, 0))
    naive = float(x.std(ddof=1) / np.sqrt(k)) if k > 1 else float("nan")

    ladder = sorted(float(v) for v in params["margin"]["ladder"])
    divisor = float(params["margin"]["power_divisor"])
    chosen, ladder_rows = None, []
    for value in ladder:
        required = value / divisor
        ok = bool(np.isfinite(se) and se <= required)
        ladder_rows.append({"margin": value, "se_required": required, "se_measured": se, "satisfied": ok})
        if ok and chosen is None:
            chosen = value
    status = "POWERED" if chosen is not None else "UNPOWERED"
    implied_mde = float(params["margin"]["mde_multiplier"]) * se if np.isfinite(se) else float("nan")
    block = {
        "status": status,
        "delta_selected": chosen,
        "ladder": ladder,
        "ladder_evaluation": ladder_rows,
        "power_divisor": divisor,
        "k_folds": k,
        "mean_fold_delta": mean,
        "measured_lag1_autocorrelation": ac1,
        "block_length": int(length),
        "block_length_rule": params["se"]["block_length_rule"],
        "se_block_bootstrap": se,
        "se_n_resamples": int(params["se"]["n_resamples"]),
        "se_seed": int(params["se"]["seed"]),
        "se_newey_west_alternative": se_alt,
        "se_std_over_sqrt_k_never_used_for_inference": naive,
        "implied_mde": implied_mde,
        "mde_multiplier": float(params["margin"]["mde_multiplier"]),
        "kc3_branch": bool(chosen is not None and chosen > float(params["margin"]["kc3_flag_above"])),
        "kc3_note": (
            "KC3 branch: the selected margin is above the ladder's floor, so the honest MDE "
            f"({implied_mde:.4f}) is printed beside it and no equivalence claim is read as "
            "tighter than that." if (chosen is not None and chosen > float(params["margin"]["kc3_flag_above"]))
            else "Selected margin is at the ladder floor (or the design is UNPOWERED)."
        ),
        "unpowered_note": (
            "No ladder value satisfies the power requirement. The result is UNPOWERED: the CI is "
            "published and NO equivalence claim is made." if chosen is None else ""
        ),
        "fold_non_independence_caveat": (
            "Every MDE here is a LOWER bound: expanding-window training sets are nested and "
            "63-session target windows straddle fold boundaries, so effective k < nominal k."
        ),
    }
    block["tost"] = tost(
        mean,
        se,
        chosen,
        float(params["tost"]["alpha"]),
        float(params["tost"]["ci_level"]),
        params["tost"]["reference_distribution"],
        k,
    )
    return block


# ---------------------------------------------------------------------------
# 7. The ordered serializer (margin block strictly before any per-fold delta)
# ---------------------------------------------------------------------------


#: A header may carry provenance, parameters and census counts. It may NOT
#: carry a number that is (or is one subtraction away from) the estimand: the
#: ordering rule of decision 15 is about the NUMBERS, not about which method
#: wrote them, so `add_header` screens its payload's keys with this pattern.
DELTA_LIKE_KEY = re.compile(r"delta|_ic$|spearman")


def delta_like_keys(key: str, value) -> list[str]:
    """Every key at or under `value` (and `key` itself) that looks like a
    per-fold delta, an IC or a Spearman statistic. Keys only -- a column NAME
    appearing as a string value is a parameter, not a result."""
    found = []
    if DELTA_LIKE_KEY.search(str(key)):
        found.append(str(key))
    stack = [value]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            for k, v in node.items():
                if DELTA_LIKE_KEY.search(str(k)):
                    found.append(str(k))
                stack.append(v)
        elif isinstance(node, (list, tuple)):
            stack.extend(node)
    return sorted(set(found))


class ResultsWriter:
    """Structural enforcement of decision 15's ordering.

    The results document is an OrderedDict. `add_delta_payload` raises
    `OrderingViolation` until `set_margin` has been called, and `set_margin`
    can be called only once; because the margin block is inserted first, it is
    also the first key of the serialized JSON and the first thing printed."""

    def __init__(self) -> None:
        self._headers: "OrderedDict[str, object]" = OrderedDict()
        self._payloads: "OrderedDict[str, object]" = OrderedDict()
        self._margin: Optional[dict] = None

    @property
    def margin_written(self) -> bool:
        return self._margin is not None

    def add_header(self, key: str, value) -> None:
        """Provenance/params/census -- contains no delta and is serialized
        AFTER the margin block, so `margin` is always the document's first key.

        "Contains no delta" is ENFORCED, not assumed: before the margin block
        exists, a header whose own key or any key inside its payload matches
        `DELTA_LIKE_KEY` is refused, so the ordering rule cannot be sidestepped
        by handing a delta-bearing payload to the header door."""
        if self._margin is None:
            offending = delta_like_keys(key, value)
            if offending:
                raise OrderingViolation(
                    f"refusing to add the header {key!r}: its payload carries the "
                    f"delta/IC-bearing keys {offending} and the equivalence margin has not "
                    "been written yet. Decision 15 requires Delta and its inputs BEFORE any "
                    "per-fold delta is serialized or printed -- through any door."
                )
        self._headers[key] = value

    def set_margin(self, block: dict) -> None:
        if self._margin is not None:
            raise OrderingViolation("the margin block may be written exactly once.")
        self._margin = block

    def add_delta_payload(self, key: str, value) -> None:
        if self._margin is None:
            raise OrderingViolation(
                f"refusing to serialize {key!r}: the equivalence margin has not been written "
                "yet. Decision 15 requires Delta and its inputs in the results JSON BEFORE any "
                "per-fold delta is serialized or printed."
            )
        self._payloads[key] = value

    def document(self) -> "OrderedDict[str, object]":
        if self._margin is None:
            raise OrderingViolation("no margin block: the document cannot be assembled.")
        doc: "OrderedDict[str, object]" = OrderedDict()
        doc["margin"] = self._margin
        doc.update(self._headers)
        doc.update(self._payloads)
        return doc

    def to_json(self, path: Path) -> str:
        text = json.dumps(self.document(), indent=2, default=str)
        Path(path).write_text(text + "\n")
        return hashlib.sha256((text + "\n").encode("utf-8")).hexdigest()

    def stdout_lines(self) -> list[str]:
        """The margin block first, then a one-line pointer. Per-fold tables are
        read from the report/JSON, never printed ahead of the margin."""
        if self._margin is None:
            raise OrderingViolation("nothing may be printed before the margin block.")
        m = self._margin
        lines = [
            "EQUIVALENCE MARGIN (decision 15, computed before any per-fold delta was written):",
            f"  status              {m['status']}",
            f"  delta_selected      {m['delta_selected']}",
            f"  k folds             {m['k_folds']}",
            f"  lag-1 autocorr      {m['measured_lag1_autocorrelation']:.4f}",
            f"  block length        {m['block_length']} ({m['block_length_rule']})",
            f"  SE (block boot)     {m['se_block_bootstrap']:.4f}",
            f"  SE (Newey-West)     {m['se_newey_west_alternative']:.4f}",
            f"  implied MDE         {m['implied_mde']:.4f}",
            f"  {int(m['tost']['ci_level']*100)}% CI            "
            f"[{m['tost']['ci_lo']:.4f}, {m['tost']['ci_hi']:.4f}]",
        ]
        return lines


# ---------------------------------------------------------------------------
# 8. Census mode (no fitting, no association -- allowed pre-ratification)
# ---------------------------------------------------------------------------


def run_census(
    df: pd.DataFrame,
    diag: dict,
    gap_days: int = B.COMPANY_QUARTER_DEDUP_GAP_DAYS,
    out_path: Optional[Path] = CENSUS_PATH,
) -> dict:
    """Per-candidate-quarter structure of the head-1 frame. Computes NO
    feature-versus-outcome association of any kind (F5_PLAN §1/§2 Step 2)."""
    quarters = sorted(str(q) for q in df[FILING_DATE_COL].dt.to_period("Q").unique())
    keep = dedup_keep_mask_cik(df, gap_days)
    keep_values = keep.values.astype(bool)
    closes = pd.to_datetime(df[WINDOW_CLOSE_COL]).values if WINDOW_CLOSE_COL in df.columns else None
    qser = df[FILING_DATE_COL].dt.to_period("Q")

    rows = []
    for q in quarters:
        period = quarter_of(q)
        test_mask = (qser == period).values
        train_mask = (df[FILING_DATE_COL] < period.start_time).values
        n_purged = 0
        if closes is not None and train_mask.any():
            cutoff = np.datetime64(period.start_time.to_datetime64())
            tc = closes[train_mask]
            n_purged = int(np.sum((tc >= cutoff) & ~pd.isna(tc)))
        rows.append(
            {
                "candidate_test_quarter": q,
                "n_test": int(test_mask.sum()),
                "n_test_dedup": int((test_mask & keep_values).sum()),
                "n_test_ciks": int(df.loc[test_mask, CIK_COL].nunique()),
                "n_train_expanding": int(train_mask.sum()),
                "n_train_purged": n_purged,
                "share_train_purged": float(n_purged / train_mask.sum()) if train_mask.sum() else float("nan"),
                "n_test_forms_10x": int(df.loc[test_mask, "form"].isin(B.FORM_ABLATION_FORMS).sum())
                if "form" in df.columns
                else None,
                "n_test_overlap_rows": int((df.loc[test_mask, "train_overlap_share"].astype(float) > 0).sum())
                if "train_overlap_share" in df.columns
                else None,
            }
        )
    census = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": "census",
        "freeze_statement": (
            "No IC, correlation, model fit or feature-versus-outcome association was computed. "
            "Census mode is allowed before G3 ratification (F5_PLAN §1)."
        ),
        "scope_sentence": SCOPE_SENTENCE,
        "e1_e2_incomparable": INCOMPARABLE_SENTENCE,
        "frame": diag,
        "dedup_gap_days": int(gap_days),
        "n_rows": int(len(df)),
        "n_rows_dedup": int(keep_values.sum()),
        "target_completeness": {
            "n_rows_joined_in_membership": int(diag.get("n_after_families_join", len(df))),
            "n_rows_with_target": int(len(df)),
            "n_rows_target_null_dropped": int(diag.get("n_target_null", 0)),
        },
        "per_candidate_quarter": rows,
        "mean_n_test_dedup": float(np.mean([r["n_test_dedup"] for r in rows])) if rows else float("nan"),
        "min_n_test_dedup": int(np.min([r["n_test_dedup"] for r in rows])) if rows else 0,
        "mean_n_test_ciks": float(np.mean([r["n_test_ciks"] for r in rows])) if rows else float("nan"),
    }
    if out_path is not None:
        Path(out_path).write_text(json.dumps(census, indent=2, default=str) + "\n")
    return census


# ---------------------------------------------------------------------------
# 9. Standing rows: zero-information, noise floor, bootstrap anchor
# ---------------------------------------------------------------------------


def h1_noise_floor(path: Path = H1_CONTROLS_PATH) -> dict:
    """H1's E2-measured zero-information floor, RE-DERIVED from
    `controls_results.json` (2.8 x the placebo SE via the frozen
    `controls.mde_from_se`) rather than quoted from prose."""
    if not Path(path).exists():
        return {"available": False}
    res = json.loads(Path(path).read_text())
    arms = {}
    for name in ("T0_placebo_announcement_core", "T0_placebo_forward_core"):
        entry = res.get("controls", {}).get(name, {}).get("dedup")
        if entry:
            arms[name] = {
                "se_ic": entry["se_ic"],
                "mean_ic": entry["mean_ic"],
                "n_periods": entry["n_periods"],
                "floor_2p8_se": C.mde_from_se(entry["se_ic"]),
            }
    floors = [a["floor_2p8_se"] for a in arms.values()]
    return {
        "available": bool(arms),
        "source": str(Path(path)),
        "arms": arms,
        "floor_lo": min(floors) if floors else None,
        "floor_hi": max(floors) if floors else None,
        "definition": "2.8 x the T0 placebo cross-period SE (controls.mde_from_se), i.e. the "
        "|IC| a zero-information predictor reaches on these folds.",
    }


def standing_payload(
    frame_raw: pd.DataFrame,
    spec_frames: dict[str, pd.DataFrame],
    folds: list[dict],
    keep_mask: pd.Series,
    numeric_cols: list[str],
    full_cols: list[str],
    params: dict,
) -> dict:
    """The standing sections' inputs, computed with the frozen spec.py
    functions (zero-information rows are ticker-keyed by PARAMETER -> "cik")."""
    bench = S.zero_information_benchmarks(
        frame_raw,
        folds,
        B.TARGET_COL,
        keep_mask=keep_mask,
        size_col=params["columns"]["size_col"],
        ticker_col=CIK_COL,
    )
    bench_summary = S.zero_information_summary(bench)
    boot = {}
    for spec_name, sframe in spec_frames.items():
        boot[spec_name] = S.bootstrap_noise_anchor(
            sframe,
            folds,
            full_cols,
            numeric_cols,
            lambda d, c, tr, te: fit_predict_seeded(d, c, tr, te, params["seeds"]["primary"]),
            B.TARGET_COL,
            keep_mask=keep_mask,
            n_resamples=int(params["bootstrap_anchor"]["n_resamples"]),
            seed=int(params["bootstrap_anchor"]["seed"]),
        )
    return {
        "active_spec": S.PRIMARY_SPEC,
        "bench_df": bench,
        "bench_summary": bench_summary,
        "bootstrap": boot,
        "embargo_census": S.embargo_census(frame_raw, folds, target_end_col=WINDOW_CLOSE_COL),
    }


def standing_to_records(standing: dict) -> dict:
    return {
        "bootstrap_anchor_scope": (
            "The frozen spec.bootstrap_noise_anchor takes ONE frame, not per-fold frames, so the "
            "anchor is computed on the confirmatory block WITHOUT the per-fold embedding "
            "components. Stated, not silently absorbed."
        ),
        "zero_information_per_fold": standing["bench_df"].to_dict("records"),
        "zero_information_summary": standing["bench_summary"].to_dict("records"),
        "bootstrap_anchor": {
            name: {
                "per_fold": entry[0].to_dict("records"),
                "summary": entry[1],
            }
            for name, entry in standing["bootstrap"].items()
        },
        "embargo_census_post_purge": standing["embargo_census"].to_dict("records"),
    }


def standing_from_records(records: dict) -> dict:
    return {
        "active_spec": S.PRIMARY_SPEC,
        "bench_df": pd.DataFrame(records["zero_information_per_fold"]),
        "bench_summary": pd.DataFrame(records["zero_information_summary"]),
        "bootstrap": {
            name: (pd.DataFrame(entry["per_fold"]), entry["summary"])
            for name, entry in records["bootstrap_anchor"].items()
        },
        "embargo_census": pd.DataFrame(records["embargo_census_post_purge"]),
    }


# ---------------------------------------------------------------------------
# 10. LOCO + the nuisance seed band
# ---------------------------------------------------------------------------


def loco_table(
    fold_frames: list[dict],
    blocks: dict[str, list[str]],
    keep_values: np.ndarray,
    params: dict,
) -> dict:
    """Decision 14: leave-one-company-out over each fold's TRAINING members,
    6 folds at round(j*(K-1)/5). DESCRIPTIVE ONLY -- at k = 6 folds there is
    no per-CIK inference to be had and none is offered."""
    k = len(fold_frames)
    n_sel = int(params["loco"]["n_folds"])
    idxs = sorted({int(round(j * (k - 1) / max(n_sel - 1, 1))) for j in range(n_sel)})
    max_ciks = params["loco"].get("max_ciks_per_fold")
    seed = int(params["seeds"]["primary"])
    rows, refits = [], 0
    for fi in idxs:
        entry = fold_frames[fi]
        fold, frame = entry["fold"], entry["frame"]
        fold_blocks = blocks_for_fold(blocks, entry["emb_cols"])
        test_idx, train_idx = fold["test_idx"], fold["train_idx"]
        realized = frame.loc[test_idx, B.TARGET_COL].astype(float).values
        dd = keep_values[test_idx].astype(bool)
        members = sorted(frame.loc[train_idx, CIK_COL].unique().tolist())
        if max_ciks:
            members = members[: int(max_ciks)]
        train_ciks = frame.loc[train_idx, CIK_COL].values
        for cik in members:
            sub_train = train_idx[train_ciks != cik]
            if len(sub_train) < 10:
                continue
            ics = {}
            for name, cols in fold_blocks.items():
                pred = fit_predict_seeded(frame, cols, sub_train, test_idx, seed)
                ics[name], _, _ = S._spearman_or_nan(np.asarray(pred)[dd], realized[dd])
                refits += 1
            rows.append(
                {
                    "test_quarter": str(fold["test_quarter"]),
                    "held_out_cik": int(cik),
                    "n_train_after_holdout": int(len(sub_train)),
                    "delta_dedup": ics.get("text_and_numeric", np.nan) - ics.get("numeric_only", np.nan),
                }
            )
    frame_rows = pd.DataFrame(rows)
    summary = []
    if not frame_rows.empty:
        for q, sub in frame_rows.groupby("test_quarter"):
            d = sub["delta_dedup"].dropna()
            summary.append(
                {
                    "test_quarter": q,
                    "n_held_out_ciks": int(len(sub)),
                    "min_delta": float(d.min()) if len(d) else float("nan"),
                    "median_delta": float(d.median()) if len(d) else float("nan"),
                    "max_delta": float(d.max()) if len(d) else float("nan"),
                }
            )
    return {
        "rule": params["loco"]["index_rule"],
        "rule_applied": f"round(j*(K-1)/(n_folds-1)) with n_folds={n_sel}, K={k}",
        "scope": params["loco"]["scope"],
        "fold_indices": idxs,
        "max_ciks_per_fold": max_ciks,
        "n_refits": refits,
        "status": "DESCRIPTIVE ONLY -- no per-CIK inference at this fold count (decision 14).",
        "per_fold_summary": summary,
        "rows": rows,
    }


def seed_band(
    fold_frames: list[dict],
    blocks: dict[str, list[str]],
    keep_values: np.ndarray,
    seeds: list[int],
) -> dict:
    """Cross-fold mean dedup delta at each nuisance seed, beside the primary."""
    means = []
    for seed in seeds:
        deltas = []
        for entry in fold_frames:
            fold, frame = entry["fold"], entry["frame"]
            test_idx, train_idx = fold["test_idx"], fold["train_idx"]
            realized = frame.loc[test_idx, B.TARGET_COL].astype(float).values
            dd = keep_values[test_idx].astype(bool)
            ics = {}
            for name, cols in blocks_for_fold(blocks, entry["emb_cols"]).items():
                pred = np.asarray(fit_predict_seeded(frame, cols, train_idx, test_idx, seed), dtype=float)
                ics[name], _, _ = S._spearman_or_nan(pred[dd], realized[dd])
            deltas.append(ics.get("text_and_numeric", np.nan) - ics.get("numeric_only", np.nan))
        d = np.asarray([v for v in deltas if np.isfinite(v)], dtype=float)
        means.append({"seed": int(seed), "mean_fold_delta_dedup": float(d.mean()) if len(d) else float("nan")})
    vals = np.asarray([m["mean_fold_delta_dedup"] for m in means], dtype=float)
    vals = vals[np.isfinite(vals)]
    return {
        "seeds": [int(s) for s in seeds],
        "per_seed": means,
        "band_min": float(vals.min()) if len(vals) else float("nan"),
        "band_max": float(vals.max()) if len(vals) else float("nan"),
        "band_sd": float(vals.std(ddof=1)) if len(vals) > 1 else float("nan"),
        "note": "Nuisance band over the model seed only; it is a spread of the SAME estimand, "
        "not a sampling distribution and not a confidence interval.",
    }


# ---------------------------------------------------------------------------
# 11. The real run
# ---------------------------------------------------------------------------


def _blocks_from_params(params: dict, frame: pd.DataFrame) -> dict[str, list[str]]:
    numeric = [c for c in params["columns"]["numeric"] if c in frame.columns]
    text = [c for c in params["columns"]["confirmatory_text"] if c in frame.columns]
    fam = [c for c in params["columns"]["family_novelty"] if c in frame.columns]
    red = [c for c in params["columns"]["exploratory_red_flags"] if c in frame.columns]
    missing = sorted(
        set(params["columns"]["numeric"] + params["columns"]["confirmatory_text"]
            + params["columns"]["family_novelty"] + params["columns"]["exploratory_red_flags"])
        - set(frame.columns)
    )
    if missing:
        raise G3Refusal(
            f"BLOCKED: the pre-registered columns {missing} are not in the analysis frame. "
            "A column list ratified at G3 cannot be silently trimmed."
        )
    return {
        "numeric_only": numeric,
        "text_and_numeric": numeric + text + fam,
        "text_and_numeric_exploratory": numeric + text + fam + red,
    }


def assert_pinned_components(fold_frames: list[dict], pinned_k: int, arm: str) -> None:
    """Every fold must realize the ratified number of embedding components.

    `pca_project` caps k at the embedding width and at (n_fit_rows - 1), so a
    thin or NaN-heavy fold silently yields fewer components than G3 pinned.
    Silently narrowing a pre-registered feature block is the same failure as
    silently trimming a pre-registered column list -- both refuse."""
    if pinned_k <= 0:
        return
    short = [
        {"test_quarter": str(entry["fold"]["test_quarter"]),
         "k_effective": int((entry["pca"] or {}).get("k_effective", 0))}
        for entry in fold_frames
        if int((entry["pca"] or {}).get("k_effective", 0)) < pinned_k
    ]
    if short:
        raise G3Refusal(
            f"BLOCKED: arm {arm!r} realized fewer embedding components than the ratified "
            f"embedding.pca_k = {pinned_k}: {short}. A feature block ratified at G3 cannot be "
            "silently narrowed."
        )


def run_head1(
    params: dict,
    guard: dict,
    frame: pd.DataFrame,
    frame_diag: dict,
    results_path: Path,
    report_path: Path,
    run_log_path: Path,
    g2_path: Path = G2_RESULTS_PATH,
    h1_path: Path = H1_CONTROLS_PATH,
    doc_path: Path = G3_DOC_PATH,
    ratified_path: Path = G3_RATIFIED_PATH,
) -> dict:
    """One non-interactive invocation: folds -> fits -> margin -> everything
    else. Nothing is printed or serialized before the margin block.

    DEFENCE IN DEPTH: the guard is re-checked HERE, against the same document
    pair, and the measured sha must equal the one the caller's `guard` dict
    carries. A `guard` dict is a caller's claim; the ratification on disk is
    the fact. `doc_path`/`ratified_path` exist so the selftest can point the
    re-check at its own synthetic fixture -- they default to the real paths."""
    verified = require_g3(doc_path, ratified_path)
    if verified["doc_sha256"] != guard.get("doc_sha256"):
        raise G3Refusal(
            "BLOCKED: the guard handed to run_head1 claims doc_sha256 "
            f"{guard.get('doc_sha256')!r}, but {Path(doc_path).name} measures "
            f"{verified['doc_sha256']!r}. A guard dictionary is not a ratification; nothing was "
            "fitted."
        )
    started = datetime.now(timezone.utc)
    blocks = _blocks_from_params(params, frame)
    folds, purge = build_folds(frame, params["fold_quarters"], params["purge_rule"])
    keep_mask = dedup_keep_mask_cik(frame, int(params["dedup"]["gap_days"]))
    keep_values = keep_mask.values.astype(bool)
    all_cols = sorted({c for cols in blocks.values() for c in cols})

    spec_kwargs = {
        "window_days": int(params["spec"]["window_days"]),
        "min_comparators": int(params["spec"]["min_comparators"]),
        "include_same_day": bool(params["spec"]["include_same_day"]),
        "ticker_col": CIK_COL,
        "date_col": FILING_DATE_COL,
    }
    arms: dict[str, tuple[pd.DataFrame, dict]] = {
        S.PRIMARY_SPEC: (S.pit_trailing_rank_frame(frame, all_cols, **spec_kwargs), spec_kwargs),
        S.SECONDARY_SPEC: (frame, {}),
    }
    if params["spec"]["same_day_sensitivity_arm"]:
        alt = dict(spec_kwargs, include_same_day=False)
        arms[S.PRIMARY_SPEC + "_no_same_day"] = (S.pit_trailing_rank_frame(frame, all_cols, **alt), alt)

    emb = embedding_matrix(frame)
    pinned_k = int(params["embedding"]["pca_k"])
    if pinned_k > 0 and emb is None:
        raise G3Refusal(
            f"BLOCKED: embedding.pca_k = {pinned_k} is ratified but the analysis frame carries no "
            "usable pooled-embedding column (data/f5/text_families_e2.parquet absent from the "
            "join, or `emb` empty on every row). A feature block ratified at G3 cannot be "
            "silently dropped."
        )
    emb_k = pinned_k if emb is not None else 0
    # `embedding.rank_transform_components` governs the PIT-RANKED spec arms.
    # The secondary arm is `raw_levels`; passing it a rank-transformed PCA
    # component block would make the secondary arm not raw, and the two arms
    # would stop being the pair the pre-registration describes.
    rank_components = bool(params["embedding"]["rank_transform_components"])

    arm_rows, arm_diag, arm_fold_frames = {}, {}, {}
    for arm_name, (aframe, akwargs) in arms.items():
        fframes = build_fold_frames(
            aframe, folds, emb, emb_k,
            rank_components and arm_name != S.SECONDARY_SPEC,
            akwargs or spec_kwargs,
        )
        assert_pinned_components(fframes, pinned_k, arm_name)
        rows, diag = evaluate_arm(
            aframe,
            fframes,
            blocks,
            keep_values,
            params["overlap"]["column"],
            float(params["overlap"]["threshold"]),
            int(params["seeds"]["primary"]),
        )
        arm_rows[arm_name] = rows
        arm_diag[arm_name] = diag
        arm_fold_frames[arm_name] = fframes

    # --- the estimand's per-fold deltas (in memory only; not yet writable) ---
    primary_deltas = fold_deltas(arm_rows[S.PRIMARY_SPEC], "dedup", "text_and_numeric")

    # --- DECISION 15: the margin block is computed and written FIRST --------
    writer = ResultsWriter()
    writer.add_header(
        "run",
        {
            "module": "backtest_e2.py",
            "head": 1,
            "started_utc": started.isoformat(timespec="seconds"),
            "mode": "real",
            "doc_sha256": guard["doc_sha256"],
            "params_sha256": guard["params_sha256"],
            "module_sha256": sha256_file(Path(__file__)),
            "frozen_module_sha256": {
                "spec.py": sha256_file(REPO_ROOT / "spec.py"),
                "backtest.py": sha256_file(REPO_ROOT / "backtest.py"),
                "controls.py": sha256_file(REPO_ROOT / "controls.py"),
            },
        },
    )
    writer.add_header(
        "scope",
        {
            "scope_sentence": SCOPE_SENTENCE,
            "e1_e2_incomparable": INCOMPARABLE_SENTENCE,
            "not_a_trading_signal": "Research screening only; no expected return, no trade.",
            "primary_metric": "dedup Spearman IC delta (text+numeric minus numeric-only), core stratum",
            "secondary": "form-controlled ablation; raw levels spec; raw (non-dedup) IC",
            "red_flags": "exploratory / disclosure-only (owner ruling 2026-08-27)",
        },
    )
    writer.add_header("params", params)
    writer.add_header("frame", frame_diag)
    writer.add_header("folds", [{"test_quarter": str(f["test_quarter"]),
                                 "n_train": int(len(f["train_idx"])),
                                 "n_test": int(len(f["test_idx"]))} for f in folds])
    writer.add_header("purge", purge)
    writer.set_margin(margin_procedure(primary_deltas["delta"].values, params))

    # --- everything delta-bearing, only now ---------------------------------
    writer.add_delta_payload("per_fold_primary_delta_dedup", primary_deltas.to_dict("records"))
    for arm_name, rows in arm_rows.items():
        writer.add_delta_payload(f"per_fold_ic__{arm_name}", rows)
        for eval_set in ("raw", "dedup", "dedup_no_overlap"):
            for block in ("text_and_numeric", "text_and_numeric_exploratory"):
                d = fold_deltas(rows, eval_set, block)
                writer.add_delta_payload(
                    f"per_fold_delta__{arm_name}__{eval_set}__{block}", d.to_dict("records")
                )

    # censoring arm: the post-2019 sub-window is the same folds, restricted
    post = quarter_of(params["post_2019_first_quarter"])
    sub = primary_deltas[[quarter_of(q) >= post for q in primary_deltas["test_quarter"]]]
    writer.add_delta_payload(
        "censoring_arms",
        {
            "full_window": {
                "k_folds": int(len(primary_deltas)),
                "mean_fold_delta_dedup": float(primary_deltas["delta"].mean()),
                "first_quarter": primary_deltas["test_quarter"].iloc[0] if len(primary_deltas) else None,
                "last_quarter": primary_deltas["test_quarter"].iloc[-1] if len(primary_deltas) else None,
            },
            "post_2019_sub_window": {
                "first_quarter": str(post),
                "k_folds": int(len(sub)),
                "mean_fold_delta_dedup": float(sub["delta"].mean()) if len(sub) else float("nan"),
            },
            "note": "Side by side, never one without the other; the sub-window is a subset of "
            "the same expanding-window folds (no refit).",
        },
    )

    # form-controlled ablation (honest secondary)
    forms = set(params["form_ablation_forms"])
    fsub = frame[frame["form"].isin(forms)].reset_index(drop=True)
    ablation = {"forms": sorted(forms), "n_rows": int(len(fsub))}
    if len(fsub) > 0:
        try:
            f_folds, f_purge = build_folds(fsub, params["fold_quarters"], params["purge_rule"])
            f_keep = dedup_keep_mask_cik(fsub, int(params["dedup"]["gap_days"])).values.astype(bool)
            f_frame = S.pit_trailing_rank_frame(fsub, all_cols, **spec_kwargs)
            f_emb = embedding_matrix(fsub)
            if pinned_k > 0 and f_emb is None:
                raise G3Refusal(
                    f"BLOCKED: embedding.pca_k = {pinned_k} is ratified but the form-restricted "
                    "rows carry no usable pooled-embedding column."
                )
            f_fframes = build_fold_frames(
                f_frame, f_folds, f_emb, emb_k if f_emb is not None else 0,
                rank_components, spec_kwargs,
            )
            assert_pinned_components(f_fframes, pinned_k, "form_controlled_ablation")
            f_rows, _ = evaluate_arm(
                f_frame, f_fframes, blocks, f_keep, params["overlap"]["column"],
                float(params["overlap"]["threshold"]), int(params["seeds"]["primary"]),
            )
            f_deltas = fold_deltas(f_rows, "dedup", "text_and_numeric")
            ablation.update(
                {
                    "purge": f_purge,
                    "per_fold_ic": f_rows,
                    "per_fold_delta_dedup": f_deltas.to_dict("records"),
                    "mean_fold_delta_dedup": float(f_deltas["delta"].mean()) if len(f_deltas) else float("nan"),
                    "note": "Restricted to 10-Q/10-K rows (backtest.FORM_ABLATION_FORMS, frozen). "
                    "The frozen run_form_controlled_ablation() binds E1 feature lists and could "
                    "not be called; the ruleset and the fold builder are the frozen ones.",
                }
            )
        except G3Refusal as exc:
            ablation["status"] = f"not run: {exc}"
    writer.add_delta_payload("form_controlled_ablation", ablation)

    # standing rows + noise floor
    standing = standing_payload(
        frame, {S.PRIMARY_SPEC: arms[S.PRIMARY_SPEC][0], S.SECONDARY_SPEC: frame},
        folds, keep_mask, blocks["numeric_only"], blocks["text_and_numeric"], params,
    )
    writer.add_delta_payload("standing", standing_to_records(standing))
    writer.add_delta_payload("noise_floor_h1", h1_noise_floor(h1_path))
    writer.add_delta_payload("embedding_pca", {"k_requested": emb_k, "per_arm": arm_diag})
    confirmatory_blocks = {k: v for k, v in blocks.items() if k != "text_and_numeric_exploratory"}
    writer.add_delta_payload(
        "seed_band",
        seed_band(
            arm_fold_frames[S.PRIMARY_SPEC],
            confirmatory_blocks,
            keep_values,
            list(range(int(params["seeds"]["nuisance_band"][0]), int(params["seeds"]["nuisance_band"][1]) + 1)),
        ),
    )
    writer.add_delta_payload(
        "loco",
        loco_table(arm_fold_frames[S.PRIMARY_SPEC], confirmatory_blocks, keep_values, params),
    )
    writer.add_delta_payload("g2_caveats", load_g2_caveats(g2_path))
    writer.add_delta_payload(
        "runtime_seconds", (datetime.now(timezone.utc) - started).total_seconds()
    )

    results_sha = writer.to_json(results_path)
    doc = writer.document()
    write_report(doc, report_path)
    append_run_log(
        run_log_path,
        {
            "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "doc_sha256": guard["doc_sha256"],
            "params_sha256": guard["params_sha256"],
            "results_sha256": results_sha,
        },
    )
    for line in writer.stdout_lines():
        print(line)
    print(f"results: {results_path}")
    print(f"report:  {report_path}")
    return doc


def append_run_log(path: Path, entry: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


# ---------------------------------------------------------------------------
# 12. Report (generated from the results document; no hand-typed numbers)
# ---------------------------------------------------------------------------


def load_g2_caveats(path: Path = G2_RESULTS_PATH) -> dict:
    """The G2 label-quality caveats, READ from data/f4/g2/results_g2.json.
    E1's 36.6%/63.4% constants are never carried onto Qwen labels."""
    path = Path(path)
    if not path.exists():
        return {"available": False, "path": str(path)}
    g2 = json.loads(path.read_text())
    return {
        "available": True,
        "path": str(path),
        "sha256": sha256_file(path),
        "provenance": g2.get("provenance"),
        "red_flags_status": g2.get("red_flags_status"),
        "constants": g2.get("constants"),
        "guidance_active_precision": g2.get("guidance_active_precision"),
        "guidance_false_none_rate": g2.get("guidance_false_none_rate"),
        "verdicts": {
            field: {
                "p_hat": entry.get("p_hat"),
                "n": entry.get("n"),
                "wilson_95": entry.get("wilson_95"),
                "verdict": entry.get("verdict"),
                "caveat": entry.get("caveat"),
            }
            for field, entry in (g2.get("primary") or {}).items()
        },
    }


def _table(rows: list[dict], cols: list[str]) -> list[str]:
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        vals = []
        for c in cols:
            v = r.get(c)
            vals.append(f"{v:.4f}" if isinstance(v, float) else ("" if v is None else str(v)))
        out.append("| " + " | ".join(vals) + " |")
    return out


def write_report(doc: dict, path: Path) -> str:
    """Regenerate the markdown from the results document. Every number here
    is read out of `doc`; nothing is hand-carried from a previous corpus."""
    m = doc["margin"]
    floor = doc.get("noise_floor_h1", {})
    floor_txt = (
        f"{floor.get('floor_lo', float('nan')):.4f}-{floor.get('floor_hi', float('nan')):.4f}"
        if floor.get("available")
        else "NOT AVAILABLE"
    )
    lines = [
        "# E2 head 1 -- walk-forward text-vs-numeric screening comparison",
        "",
        f"Generated from the run's own diagnostics ({doc['run']['started_utc']} UTC, "
        f"params_sha256 `{doc['run']['params_sha256'][:16]}...`, doc_sha256 "
        f"`{doc['run']['doc_sha256'][:16]}...`). No number below is hand-typed.",
        "",
        f"**Scope sentence.** {doc['scope']['scope_sentence']}",
        "",
        f"**{doc['scope']['e1_e2_incomparable']}**",
        "",
        "**Validation of every number below:** quarterly expanding-window walk-forward, "
        "time-ordered by public filing date, never a shuffle; training rows whose 63-session "
        "target window closes on or after the test quarter's first session are purged; "
        "company-quarter deduplicated Spearman IC is primary and the raw IC is reported beside "
        "it; per-fold values are published, never a lone point estimate.",
        "",
        "## 1. Equivalence margin (decision 15) -- written before any per-fold delta",
        "",
        f"- status: **{m['status']}**, Delta = **{m['delta_selected']}** (ladder {m['ladder']}, "
        f"power requirement SE <= Delta/{m['power_divisor']})",
        f"- k = {m['k_folds']} folds; measured lag-1 autocorrelation of the fold deltas = "
        f"{m['measured_lag1_autocorrelation']:.4f}; moving-block length {m['block_length']} "
        f"({m['block_length_rule']})",
        f"- SE = **{m['se_block_bootstrap']:.4f}** (moving-block bootstrap, "
        f"{m['se_n_resamples']} resamples, seed {m['se_seed']}); Newey-West alternative "
        f"{m['se_newey_west_alternative']:.4f}; std/sqrt(k) = "
        f"{m['se_std_over_sqrt_k_never_used_for_inference']:.4f} is recorded only to be labelled "
        "never used for inference",
        f"- implied MDE ({m['mde_multiplier']} x SE) = **{m['implied_mde']:.4f}**; {m['kc3_note']}",
        f"- mean fold delta (dedup) = {m['mean_fold_delta']:.4f}; "
        f"{int(m['tost']['ci_level']*100)}% CI [{m['tost']['ci_lo']:.4f}, {m['tost']['ci_hi']:.4f}] "
        f"(always printed); "
        + (
            f"TOST p = {m['tost']['p_tost']:.4f} at alpha {m['tost']['alpha']}; equivalence = "
            f"{m['tost']['equivalence']}"
            if m["tost"]["equivalence"] is not None
            else f"{m['tost']['note']} {m['unpowered_note']}"
        ),
        f"- {m['fold_non_independence_caveat']}",
        "",
        f"**Zero-information noise floor (H1, re-derived on E2): |IC| ~ {floor_txt}.** Read every "
        "IC below against it and against the two standing zero-information rows in §4.",
        "",
        "## 2. Per-fold deltas, primary specification (dedup)",
        "",
    ]
    lines += _table(
        doc.get("per_fold_primary_delta_dedup", []),
        ["test_quarter", "n_test", "ic_baseline", "ic_block", "delta"],
    )
    cens = doc.get("censoring_arms", {})
    lines += [
        "",
        "## 3. Censoring arms, side by side",
        "",
        f"- full window: k = {cens.get('full_window', {}).get('k_folds')}, mean fold delta "
        f"{cens.get('full_window', {}).get('mean_fold_delta_dedup', float('nan')):.4f}",
        f"- post-{cens.get('post_2019_sub_window', {}).get('first_quarter')} sub-window: k = "
        f"{cens.get('post_2019_sub_window', {}).get('k_folds')}, mean fold delta "
        f"{cens.get('post_2019_sub_window', {}).get('mean_fold_delta_dedup', float('nan')):.4f}",
        "",
        "## 4. Standing sections",
        "",
    ]
    if "standing" in doc:
        lines += B.standing_section_lines(standing_from_records(doc["standing"]))
    seed = doc.get("seed_band", {})
    loco = doc.get("loco", {})
    lines += [
        "## 5. Nuisance seed band and LOCO",
        "",
        f"- seed band over {len(seed.get('seeds', []))} nuisance seeds: cross-fold mean delta in "
        f"[{seed.get('band_min', float('nan')):.4f}, {seed.get('band_max', float('nan')):.4f}] "
        f"(sd {seed.get('band_sd', float('nan')):.4f}). {seed.get('note', '')}",
        f"- LOCO: {loco.get('n_refits')} refits over folds {loco.get('fold_indices')} "
        f"({loco.get('status')})",
        "",
        "## 6. Label-quality caveats (G2, read from results_g2.json)",
        "",
    ]
    g2 = doc.get("g2_caveats", {})
    if g2.get("available"):
        lines.append(f"Provenance: {g2.get('provenance')}")
        lines.append("")
        for field, v in (g2.get("verdicts") or {}).items():
            ci = v.get("wilson_95") or [float("nan"), float("nan")]
            lines.append(
                f"- **{field}**: {v.get('p_hat', float('nan')):.4f} "
                f"[{ci[0]:.4f}, {ci[1]:.4f}] (n = {v.get('n')}) -- {v.get('verdict')}"
            )
        ap = g2.get("guidance_active_precision") or {}
        if ap:
            lines.append(
                f"- guidance ACTIVE precision (mandatory escort): {ap.get('point', float('nan')):.4f} "
                f"[{ap.get('wilson_lo', float('nan')):.4f}, {ap.get('wilson_hi', float('nan')):.4f}] "
                f"(n_eff {ap.get('n_eff', float('nan')):.2f})"
            )
        fn = g2.get("guidance_false_none_rate") or {}
        if fn:
            lines.append(
                f"- guidance false-NONE rate: {fn.get('p_hat', float('nan')):.4f} "
                f"[{fn.get('wilson_lo', float('nan')):.4f}, {fn.get('wilson_hi', float('nan')):.4f}] "
                f"(n = {fn.get('n')})"
            )
        lines.append(f"- red flags: {g2.get('red_flags_status')}")
    else:
        lines.append("**G2 results file not available to this run** -- the caveats are NOT stated, "
                     "and no number above should be read as label-quality-qualified.")
    lines += ["", f"_{doc['scope']['not_a_trading_signal']}_", ""]
    text = "\n".join(lines)
    Path(path).write_text(text + "\n")
    return text


# ---------------------------------------------------------------------------
# 13. Selftest -- synthetic data only
# ---------------------------------------------------------------------------


def synthetic_frames(seed: int = 0, n_ciks: int = 24, n_quarters: int = 14, emb_dim: int = 8):
    """A seeded synthetic (target, text, numeric, families) quartet with the
    same schemas as the real tables. No real return, price or filing is read."""
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2016-01-15")
    sessions = pd.bdate_range(start, periods=n_quarters * 70 + 200)
    trows, xrows, nrows, frows = [], [], [], []
    for q in range(n_quarters):
        qdate = start + pd.DateOffset(months=3 * q)
        for c in range(n_ciks):
            cik = 100000 + c
            for form, off in (("10-Q", 3), ("8-K", 1)):
                fd = (qdate + pd.Timedelta(days=off + int(rng.integers(0, 5)))).normalize()
                pos = int(np.searchsorted(sessions.values, fd.to_datetime64()))
                close = sessions[min(pos + 64, len(sessions) - 1)]
                acc = f"{cik}-{q:02d}-{form}"
                sig = rng.normal()
                trows.append(
                    {
                        "cik": cik, "accession_number": acc, "form": form, "filing_date": fd,
                        "info_date": fd, "news_session": sessions[min(pos, len(sessions) - 1)],
                        "window_open_session": sessions[min(pos + 1, len(sessions) - 1)],
                        "window_close_session": close,
                        "target_excess_63": float(0.02 * sig + rng.normal(0, 0.12)),
                        "target_complete": True, "in_membership": True, "is_gld": False,
                    }
                )
                xrows.append(
                    {
                        "cik": cik, "accession_number": acc, "filing_date": fd, "form": form,
                        "sentiment_mean_score": float(sig * 0.3 + rng.normal(0, 0.5)),
                        "sentiment_negative_share": float(rng.uniform(0, 1)),
                        "guidance_signed_mean": float(rng.normal()),
                        "guidance_any_present": float(rng.integers(0, 2)),
                        "n_text_chunks_attributed": int(rng.integers(1, 40)),
                        "redflag_any_rate_press": float(rng.uniform(0, 1)),
                        "train_overlap_share": float(rng.choice([0.0, 0.0, 0.0, 0.2])),
                    }
                )
                nrows.append(
                    {
                        "cik": cik, "accession_number": acc, "filing_date": fd, "form": form,
                        "log_total_assets": float(10 + c * 0.1 + rng.normal(0, 0.05)),
                        "momentum_126": float(rng.normal(0, 0.2)),
                        "realized_vol_63": float(abs(rng.normal(0.3, 0.1))),
                    }
                )
                frows.append(
                    {
                        "cik": cik, "accession_number": acc,
                        "novelty_risk_factors_yoy": float(rng.uniform(0, 1)),
                        "novelty_mda_yoy": float(rng.uniform(0, 1)),
                        "emb": list(rng.normal(size=emb_dim).astype(np.float32)),
                    }
                )
    return (
        pd.DataFrame(trows), pd.DataFrame(xrows), pd.DataFrame(nrows), pd.DataFrame(frows),
    )


def selftest_params(frame: pd.DataFrame) -> dict:
    """SELFTEST-ONLY parameter block (F5_PLAN §3 defaults as a fixture)."""
    params = json.loads(json.dumps(SELFTEST_PARAMS))
    quarters = sorted(str(q) for q in frame[FILING_DATE_COL].dt.to_period("Q").unique())
    params["fold_quarters"] = quarters[4:]
    params["post_2019_first_quarter"] = quarters[len(quarters) // 2]
    params["columns"]["numeric"] = ["log_total_assets", "momentum_126", "realized_vol_63"]
    params["columns"]["confirmatory_text"] = [
        "sentiment_mean_score", "sentiment_negative_share", "guidance_signed_mean",
        "guidance_any_present", "n_text_chunks_attributed",
    ]
    params["columns"]["exploratory_red_flags"] = ["redflag_any_rate_press"]
    params["columns"]["family_novelty"] = ["novelty_risk_factors_yoy", "novelty_mda_yoy"]
    return params


def write_synthetic_g3(outdir: Path, params: dict) -> tuple[Path, Path]:
    """Write a synthetic pre-registration + ratification pair into `outdir`.
    NEVER writes to data/f5 (a test pins that the real paths are untouched)."""
    doc = outdir / "G3_PREREGISTRATION.md"
    doc.write_text(
        "# SYNTHETIC pre-registration (selftest fixture -- NOT the real G3 document)\n\n"
        "```" + FENCE_INFO + "\n" + json.dumps(params, indent=2) + "\n```\n"
    )
    rat = outdir / "G3_RATIFIED.json"
    rat.write_text(json.dumps({"doc_sha256": sha256_file(doc), "note": "SYNTHETIC selftest fixture"}) + "\n")
    return doc, rat


def selftest(outdir: Optional[Path] = None) -> dict:
    out = Path(outdir) if outdir else Path(tempfile.mkdtemp(prefix="backtest_e2_selftest_"))
    out.mkdir(parents=True, exist_ok=True)
    tgt, txt, num, fam = synthetic_frames()
    frame, diag = join_frames(tgt, txt, num, fam)
    params = selftest_params(frame)
    doc_path, rat_path = write_synthetic_g3(out, params)
    loaded, guard = load_g3_params(doc_path, rat_path)
    assert loaded == params, "selftest: the params read back from the document differ"
    census = run_census(frame, diag, params["dedup"]["gap_days"], out / "census_head1.json")
    result = run_head1(
        loaded, guard, frame, diag,
        out / "results_head1.json", out / "report_head1.md", out / "run_log.jsonl",
        doc_path=doc_path, ratified_path=rat_path,
    )
    print(f"selftest OK: {census['n_rows']} synthetic rows, "
          f"{len(result['per_fold_primary_delta_dedup'])} folds, artifacts in {out}")
    return {"outdir": str(out), "census": census, "results": result}


# ---------------------------------------------------------------------------
# 14. CLI
# ---------------------------------------------------------------------------


def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="E2 head 1 -- walk-forward screening comparison")
    p.add_argument("--census", action="store_true", help="row/fold census only; no fitting (allowed pre-G3)")
    p.add_argument("--selftest", action="store_true", help="end-to-end on a synthetic seeded frame")
    p.add_argument("--outdir", type=Path, default=None, help="selftest output directory")
    p.add_argument("--write-schema", action="store_true", help="(re)write data/f5/G3_PARAMS_SCHEMA.json")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    if args.write_schema:
        write_params_schema()
        print(f"wrote {PARAMS_SCHEMA_PATH}")
        return 0
    if args.selftest:
        selftest(args.outdir)
        return 0
    if args.census:
        frame, diag = load_analysis_frame()
        census = run_census(frame, diag, out_path=CENSUS_PATH)
        print(f"census: {census['n_rows']} rows, {len(census['per_candidate_quarter'])} candidate "
              f"quarters, mean n_dedup {census['mean_n_test_dedup']:.1f}; wrote {CENSUS_PATH}")
        return 0
    try:
        params, guard = load_g3_params()
    except G3Refusal as exc:
        print(str(exc))
        print("Nothing was fitted and no IC was computed. Allowed today: "
              "`python3 backtest_e2.py --census` and `python3 backtest_e2.py --selftest`.")
        return 2
    frame, diag = load_analysis_frame()
    run_head1(params, guard, frame, diag, RESULTS_PATH, REPORT_PATH, RUN_LOG_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
