#!/usr/bin/env python3
"""Offline tests for the G2 spot-check tooling — no GPU, no network, $0.

    python3 -m pytest finetune/test_g2_spotcheck.py -q -p no:cacheprovider

Covers `data/f4/g2/build_draw_g2.py` and `data/f4/g2/analyze_g2.py` against
`data/f4/g2/G2_SPOTCHECK_design.md`. Every repo artifact is opened READ-ONLY;
the one test that re-runs the builder redirects all of its writes into
`tmp_path` via a symlink mirror of the five pinned inputs, so no repo file is
touched (in particular `draw_manifest.json`, the G2 resume state, is not
rewritten).

2026-09-07: RE-PINNED to the OWNER-RATIFIED Option C draw (design §14). The
owner ruled n on 2026-09-07: P = 400 (two-way section x sector Hamilton),
G-A = 80 proportional + the direction quota = 100, G-N = 80, b = 0.85 on BOTH
gate-bearing fields, and three ceiling batches. The Option-B pins (n=300 /
G-A=60 / 420 rows / 11 batches / `ratified_bars: null`) are SUPERSEDED (§14.8)
and are re-pinned here, not deleted:

  * the two builder tripwires that were written to fire the moment the
    parameters were ratified DID fire, by design. They are re-pinned to the
    ratified values (`PARAMETERS_STATUS == "OWNER_RATIFIED"`, bars 0.85/0.85)
    and the refusal path they guarded is still exercised — by flipping the
    constant under monkeypatch, not by deleting the check.
  * the analyzer's bar-shopping guard changed SHAPE with the ruling: an unset
    bar is still a refusal (exit 2), and the remaining degree of freedom — a
    bar or an n edited after the draw exists — is now a hard fail. Both legs
    are tested, plus the must-not-cry-wolf leg on the real manifest.
  * §3.1's n=300 Hamilton table is kept as the LICENSING check that §14.2
    itself cites ("the same code reproduces §3.1's pinned n=300 table
    cell-for-cell, which is the check that licenses this one").

Runtime is dominated by `test_draw_reproduces_byte_for_byte` (~21 s: it is a
full independent re-draw over the 317,081-row corpus). Everything else is
sub-second apart from the analyzer's sha re-check of the pinned inputs.

Two deliberate departures from a literal reading of the brief, both with a
design citation:

  * `schema_valid` is REPORTED, not asserted true. Design §2.1 keeps the 23
    `schema_valid = false` rows *in* the frame, so a re-draw that lands on one
    is design-conformant; a hard `all(schema_valid)` would cry wolf on a legal
    draw. The frame invariants that ARE asserted are the ones the design
    pins: membership, `parse_ok`, and no 8K_BODY.
  * Allocations are derived from the frame (Hamilton, recomputed here) and
    then checked against the design's pre-registered table AND the realized
    draw — three-way, rather than one hand-typed constant
    (EXPANSION_PLAN §3.8, derive-and-report).
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from math import sqrt
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO = Path(__file__).resolve().parent.parent
G2 = REPO / "data" / "f4" / "g2"
BATCHES = G2 / "batches"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


B = _load("build_draw_g2", G2 / "build_draw_g2.py")
A = _load("analyze_g2", G2 / "analyze_g2.py")

DRAW = pd.read_csv(G2 / "draw_g2.csv").merge(
    pd.read_csv(G2.parent / "g2_draw_arms.csv"), on="chunk_id", how="left")
MANIFEST = json.loads((G2 / "draw_manifest.json").read_text())
DRAWN_IDS = list(DRAW.chunk_id)

# ---------------------------------------------------------------------------
# design §14 pre-registered constants, owner-ratified 2026-09-07. Typed from
# the design doc; every one of them is checked against a value DERIVED from
# the corpus and against the realized draw.
# ---------------------------------------------------------------------------
DESIGN_ARMS = {"P": 400, "G-A": 100, "G-N": 80}          # §14.1 (i), (vi)
DESIGN_N_TOTAL = 580
DESIGN_BARS = {"sentiment": 0.85, "guidance_direction": 0.85}   # §14.1 (ii)
DESIGN_CEILING_BATCHES = ["batch_01", "batch_02", "batch_03"]   # §14.1 (v)(b)
DESIGN_CEILING_ROWS = 120

# §14.2 — the P arm's two-way Hamilton table at n = 400, all 15 cells
DESIGN_P_ALLOC = {
    ("MDA", "consumer"): 37, ("MDA", "energy"): 32, ("MDA", "financials"): 81,
    ("MDA", "healthcare"): 33, ("MDA", "tech"): 35,
    ("EX99_PRESS_RELEASE", "consumer"): 25, ("EX99_PRESS_RELEASE", "energy"): 21,
    ("EX99_PRESS_RELEASE", "financials"): 30,
    ("EX99_PRESS_RELEASE", "healthcare"): 22, ("EX99_PRESS_RELEASE", "tech"): 21,
    ("RISK_FACTORS", "consumer"): 8, ("RISK_FACTORS", "energy"): 8,
    ("RISK_FACTORS", "financials"): 13, ("RISK_FACTORS", "healthcare"): 11,
    ("RISK_FACTORS", "tech"): 23,
}
# §3.1's superseded n=300 table, kept as the licensing check §14.2 cites.
DESIGN_P_ALLOC_N300 = {
    ("MDA", "consumer"): 27, ("MDA", "energy"): 24, ("MDA", "financials"): 61,
    ("MDA", "healthcare"): 25, ("MDA", "tech"): 26,
    ("EX99_PRESS_RELEASE", "consumer"): 18, ("EX99_PRESS_RELEASE", "energy"): 16,
    ("EX99_PRESS_RELEASE", "financials"): 23,
    ("EX99_PRESS_RELEASE", "healthcare"): 17, ("EX99_PRESS_RELEASE", "tech"): 16,
    ("RISK_FACTORS", "consumer"): 6, ("RISK_FACTORS", "energy"): 6,
    ("RISK_FACTORS", "financials"): 10, ("RISK_FACTORS", "healthcare"): 8,
    ("RISK_FACTORS", "tech"): 17,
}
# §14.3 — the G-A quota arm: proportional base at n=80, floor vector, and the
# elementwise-maximum target rule that combines them.
DESIGN_GA_PROPORTIONAL = {"RAISED": 46, "MAINTAINED": 24, "LOWERED": 9, "WITHDRAWN": 1}
DESIGN_GA_FLOOR = {"LOWERED": 15, "MAINTAINED": 20, "WITHDRAWN": 15}
DESIGN_GA_ALLOC = {"RAISED": 46, "MAINTAINED": 24, "LOWERED": 15, "WITHDRAWN": 15}
DESIGN_GA_QUOTA_ADDED = {"RAISED": 0, "MAINTAINED": 0, "LOWERED": 6, "WITHDRAWN": 14}
DESIGN_GA_CORPUS_COUNTS = {"RAISED": 3716, "MAINTAINED": 1940,
                           "LOWERED": 757, "WITHDRAWN": 66}
DESIGN_GA_WEIGHTS = {"RAISED": 0.573545, "MAINTAINED": 0.299429,
                     "LOWERED": 0.116839, "WITHDRAWN": 0.010187}   # §14.4, 6 dp
DESIGN_GA_FRAME = 6479
# §14.2 / §14.6 — evaluable bases inside P at n=400, which the §6.3 caveat
# arithmetic and the §14.6 decision boundaries are computed on.
DESIGN_P_EVALUABLE = {"sentiment": 337, "guidance_direction": 119}
# §14.7 — gate-bearing-applicable rows across all three arms
DESIGN_EVALUABLE_ALL_ARMS = {"sentiment": 517, "guidance_direction": 299,
                             "red_flags": 580}
# §14.6 — decision boundaries at the ratified (n, b), pinned before data
DESIGN_BOUNDARIES = [
    # field, n, bar, k_pass, p_hat_pass, k_fail, p_hat_fail
    ("sentiment", 337, 0.85, 300, 0.8902, 273, 0.8101),
    ("guidance_direction", 119, 0.85, 109, 0.9160, 93, 0.7815),
]
SELFTEST_CHECKS_MIN = 87   # analyze_g2.py --selftest, 2026-09-07. Checks may be
                           # added; a drop means a pre-registered check was cut.


def batch_files(include_replicate=True):
    return [p for p in sorted(BATCHES.glob("batch_*.json"))
            if include_replicate or "replicate" not in p.name]


@pytest.fixture(scope="module")
def drawn_labels():
    """Stored labels for the 580 drawn rows, in draw order. READ-ONLY."""
    lab = pd.read_parquet(REPO / "data/f4/labels_e2_v1.parquet", columns=[
        "chunk_id", "section_type", "parse_ok", "schema_valid", "word_count",
        "sentiment", "guidance_direction", "guidance_imputed_none"])
    d = lab[lab.chunk_id.isin(set(DRAWN_IDS))].set_index("chunk_id")
    d = d.loc[DRAWN_IDS]
    d["arm"] = DRAW.arm.values
    return d


@pytest.fixture(scope="module")
def frame_cells():
    """Frame (corpus minus 8K_BODY) section x sector counts. READ-ONLY."""
    ch = pd.read_parquet(REPO / "data/f4/chunks_v1.parquet",
                         columns=["chunk_id", "section_type", "home_sector",
                                  "home_company_name"])
    frame = ch[ch.section_type != "8K_BODY"]
    return frame


@pytest.fixture(scope="module")
def ga_frame_counts():
    """Per-direction row counts of the active-guidance EX99 stratum (§3.2).

    Derived from labels_e2_v1.parquet, not read from the manifest — this is
    the frame the G-A allocation and the §14.4 weights are computed on.
    """
    lab = pd.read_parquet(REPO / "data/f4/labels_e2_v1.parquet", columns=[
        "section_type", "guidance_direction", "guidance_imputed_none"])
    act = lab[(lab.section_type == "EX99_PRESS_RELEASE")
              & (lab.guidance_direction.isin(B.ACTIVE_GUIDANCE))
              & (~lab.guidance_imputed_none.fillna(False))]
    return {d: int((act.guidance_direction == d).sum()) for d in B.ACTIVE_GUIDANCE}


# ===========================================================================
# 1. the draw reproduces, and the parameters are the owner's
# ===========================================================================

MIRRORED_INPUTS = [
    "data/f4/labels_e2_v1.parquet",
    "data/f4/chunks_v1.parquet",
    "labeling_rubric.md",
    "data/hardening/spotcheck_v12/OWNER_POLICY_RULINGS.md",
    "finetune/splits_v12/train.parquet",
    "data/f4/g2/G2_SPOTCHECK_design.md",
]


@pytest.fixture(scope="module")
def rebuild(tmp_path_factory):
    """A full re-run of build_draw_g2.py writing ONLY into tmp_path.

    The five pinned inputs plus the design doc are symlinked into a mirror
    root; ROOT/OUT/BATCH_DIR are repointed at it. Nothing under the repo's
    data/f4/g2/ is opened for writing.

    Invoked with NO flags: the parameters are owner-ratified (§14.1) and §14.9
    deleted the dead `--provisional` flag outright. If the §10.1 guard were
    still armed this fixture would raise SystemExit and every test using it
    would fail loudly.
    """
    root = tmp_path_factory.mktemp("g2mirror")
    for rel in MIRRORED_INPUTS:
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.symlink_to(REPO / rel)
    out = root / "data/f4/g2"
    old = (B.ROOT, B.OUT, B.BATCH_DIR, sys.argv)
    B.ROOT, B.OUT, B.BATCH_DIR = root, out, out / "batches"
    sys.argv = ["build_draw_g2.py"]
    try:
        B.main()
    finally:
        B.ROOT, B.OUT, B.BATCH_DIR, sys.argv = old
    return out


def test_draw_reproduces_byte_for_byte(rebuild):
    """A fresh re-draw from the same seed reproduces every rater-visible file."""
    names = ["draw_g2.csv", "rater_policy_addendum.md"] + [
        f"batches/{p.name}" for p in batch_files()]
    # §14.9: the arm sidecar lives one level up, outside the rater-pointed tree.
    assert (rebuild.parent / "g2_draw_arms.csv").read_bytes() == \
        (G2.parent / "g2_draw_arms.csv").read_bytes(), \
        "the arm sidecar did not reproduce from the same seed"
    differing = [n for n in names
                 if (rebuild / n).read_bytes() != (G2 / n).read_bytes()]
    assert not differing, (
        f"re-drawing with seed {B.SEED} did NOT reproduce {differing} — the "
        "draw is not deterministic, or the on-disk artifacts were edited "
        "after the build")
    # 15 batches + 3 ceiling replicates + csv + addendum = 20, derived from the
    # manifest rather than hand-typed.
    expect = 2 + MANIFEST["n_batches"] + len(MANIFEST["ceiling_batches"])
    assert len(names) == expect == 20, f"compared {len(names)} files: {names}"

    fresh = json.loads((rebuild / "draw_manifest.json").read_text())
    # generated_utc is a timestamp; outputs are sha256s of paths under the
    # mirror; reproducibility_check/assertions_passed differ because a fresh
    # directory has no prior artifacts for A14 to compare against.
    volatile = {"generated_utc", "outputs", "reproducibility_check",
                "assertions_passed"}
    drifted = [k for k in fresh if k not in volatile and fresh[k] != MANIFEST.get(k)]
    assert not drifted, f"manifest keys drifted on re-draw: {drifted}"
    assert MANIFEST["reproducibility_check"] == "byte_identical_to_prior_run"
    assert set(fresh["assertions_passed"]) <= set(MANIFEST["assertions_passed"])


def test_parameters_are_the_owner_ratified_option_c_set():
    """§14.1: the ruled parameters, in the builder, the analyzer and the
    manifest — one disagreement is a parameter edited after the ruling."""
    assert B.PARAMETERS_STATUS == "OWNER_RATIFIED" and B.OPTION == "C"
    assert B.RATIFIED_BARS == DESIGN_BARS, (
        "b = 0.85 on BOTH gate-bearing fields is owner ruling (ii); changing a "
        "bar is a new pre-registration, not an edit")
    assert (B.N_PRIMARY, B.N_GA, B.N_GA_TOTAL, B.N_GN, B.N_TOTAL) == \
        (400, 80, 100, 80, DESIGN_N_TOTAL)
    assert B.N_GA_FLOOR == DESIGN_GA_FLOOR and B.GA_TARGETS == DESIGN_GA_ALLOC
    assert B.CEILING_BATCHES == DESIGN_CEILING_BATCHES  # ruling (v), option (b)
    assert B.RATE_RED_FLAGS is True                     # Option C, not B-lite

    for key, want in [("parameters_status", "OWNER_RATIFIED"), ("option", "C"),
                      ("n_primary", 400), ("n_ga", 80), ("n_ga_total", 100),
                      ("n_gn", 80), ("n_total", DESIGN_N_TOTAL),
                      ("ratified_bars", DESIGN_BARS),
                      ("ceiling_batches", DESIGN_CEILING_BATCHES),
                      ("ceiling_rows", DESIGN_CEILING_ROWS),
                      ("rate_red_flags", True)]:
        assert MANIFEST[key] == want, f"draw_manifest.json {key}={MANIFEST[key]!r}"
    # analyze_g2.py carries its own copy and hard-fails on disagreement (§10.0)
    assert A.PARAMETERS_STATUS == "OWNER_RATIFIED"
    assert {k: MANIFEST[k] for k in A.RATIFIED} == A.RATIFIED, (
        "analyze_g2.py's RATIFIED block disagrees with draw_manifest.json")
    assert "EXPLORATORY" in MANIFEST["red_flags_status"] and \
        "DISCLOSURE-ONLY" in MANIFEST["red_flags_status"], \
        "red_flags stays exploratory/disclosure-only (owner, 2026-08-27)"


def test_builder_refuses_to_run_if_the_parameters_stop_being_ratified(tmp_path, monkeypatch):
    """§10.1 guard, must-flag leg: the draw is impossible unless the parameter
    block is owner-ratified. The constant is ratified now (ruling 2026-09-07),
    so the guard is exercised by flipping it back — the check is re-pinned,
    not deleted. The must-not-cry-wolf leg is the `rebuild` fixture, which
    runs the same main() with no flag at all.
    """
    out = tmp_path / "g2"
    monkeypatch.setattr(B, "PARAMETERS_STATUS", "PROPOSED")
    monkeypatch.setattr(B, "OUT", out)
    monkeypatch.setattr(B, "BATCH_DIR", out / "batches")
    monkeypatch.setattr(sys, "argv", ["build_draw_g2.py"])
    with pytest.raises(SystemExit) as e:
        B.main()
    assert "REFUSING TO RUN" in str(e.value)
    assert not out.exists(), "the builder wrote something before refusing"


# ===========================================================================
# 2. blindness
# ===========================================================================

def test_batch_objects_carry_only_chunk_id_and_text():
    seen = []
    for p in batch_files():
        objs = json.loads(p.read_text())
        assert isinstance(objs, list), f"{p.name} is not a JSON array"
        for o in objs:
            assert set(o) == {"chunk_id", "text"}, (
                f"{p.name}: object key set {sorted(o)} != "
                "['chunk_id', 'text'] — blindness leak (§5.1 / A7)")
            assert isinstance(o["text"], str) and o["text"].strip(), (
                f"{p.name}: {o['chunk_id']} has empty text")
        if "replicate" not in p.name:
            seen += [o["chunk_id"] for o in objs]
    assert seen == DRAWN_IDS, "batch ids do not match draw_g2.csv, in order"
    assert len(set(seen)) == len(seen) == DESIGN_N_TOTAL == MANIFEST["n_total"]


def test_batch_text_is_the_whole_chunk(drawn_labels):
    """No chunk text is missing or truncated: every batch text's word count
    equals the corpus word_count for that chunk_id."""
    bad = []
    for p in batch_files(include_replicate=False):
        for o in json.loads(p.read_text()):
            want = int(drawn_labels.word_count[o["chunk_id"]])
            got = len(o["text"].split())
            if got != want:
                bad.append((o["chunk_id"], got, want))
    assert not bad, f"batch text word counts != corpus word_count: {bad[:5]}"


def test_every_ceiling_replicate_is_byte_identical_to_its_original():
    """§5.4 / §14.5: the ceiling arm is THREE batches (ruling (v), option (b)),
    n = 120 rows. A replicate that differed would measure text differences
    rather than rater noise; a replicate outside CEILING_BATCHES would silently
    enlarge the arm."""
    assert MANIFEST["ceiling_batches"] == DESIGN_CEILING_BATCHES
    for b in MANIFEST["ceiling_batches"]:
        assert (BATCHES / f"{b}_replicate.json").read_bytes() == \
               (BATCHES / f"{b}.json").read_bytes(), (
            f"{b}_replicate.json differs from {b}.json — the two-rater "
            "ceiling arm (§5.4) would measure text differences, not rater noise")
    replicated = sorted(p.name.replace("_replicate.json", "")
                        for p in BATCHES.glob("*_replicate.json"))
    assert replicated == DESIGN_CEILING_BATCHES, (
        f"replicates exist for {replicated}, not for the three ruled ceiling "
        "batches — the ceiling arm is exactly the ruled 120 rows")
    n_ceiling = int(DRAW.batch.isin(MANIFEST["ceiling_batches"]).sum())
    assert n_ceiling == DESIGN_CEILING_ROWS == MANIFEST["ceiling_rows"], n_ceiling


def test_draw_csv_carries_no_label_or_metadata_columns(drawn_labels):
    """§5.1 as amended by §14.9: three columns, and `arm` is NOT one of them.

    `arm` is a per-row disclosure of stored guidance status — every G-A row
    carries an active `guidance_direction`, every G-N row an imputed NONE — so
    it may not sit in the directory the raters are pointed at. Both halves are
    checked: the column is gone from the rater-visible CSV, and the sidecar
    outside that tree really does encode what the move was made to hide.
    """
    header = (G2 / "draw_g2.csv").read_text().splitlines()[0]
    assert header == "rank,batch,chunk_id", header
    assert "arm" not in header, "the arm map is back beside the batch files (§14.9)"
    leaked = [k for k in B.FORBIDDEN_KEYS if k in header]
    assert not leaked, f"draw_g2.csv header leaks {leaked}"

    arms_path = G2.parent / "g2_draw_arms.csv"
    assert arms_path.parent != G2, "the sidecar must be OUTSIDE data/f4/g2/"
    assert arms_path.read_text().splitlines()[0] == "chunk_id,arm"
    assert set(DRAW.arm.unique()) == {"P", "G-A", "G-N"}, sorted(DRAW.arm.unique())
    assert DRAW.arm.notna().all() and len(DRAW) == DESIGN_N_TOTAL

    # the channel that was closed, stated as a fact about the data
    ga = drawn_labels[drawn_labels.arm == "G-A"]
    gn = drawn_labels[drawn_labels.arm == "G-N"]
    assert ga.guidance_direction.isin(B.ACTIVE_GUIDANCE).all(), \
        "arm='G-A' would have disclosed an active stored guidance_direction"
    assert (gn.guidance_imputed_none.fillna(False).astype(bool).all()
            and (gn.guidance_direction == "NONE").all()), \
        "arm='G-N' would have disclosed an imputed stored NONE"
    assert len(ga) + len(gn) == 180

    # no rater-visible file under data/f4/g2/ mentions the arm map
    for path in [G2 / "draw_g2.csv", G2 / "rater_policy_addendum.md"] + batch_files():
        assert "g2_draw_arms" not in path.read_text(), path.name


def test_rater_visible_prose_leaks_no_identity(frame_cells):
    """The addendum a rater reads carries no company name, no exemplar id,
    no metadata column name and no chunk_id; the manifest carries no drawn id."""
    addendum = (G2 / "rater_policy_addendum.md").read_text()
    low = addendum.lower()
    drawn_names = frame_cells.set_index("chunk_id").home_company_name.reindex(DRAWN_IDS)
    tokens = {t for t in (B.distinctive_token(n) for n in drawn_names.unique()) if t}
    hits = sorted(t for t in tokens if re.search(rf"\b{re.escape(t)}\b", low))
    assert not hits, f"rater_policy_addendum.md names a drawn company: {hits}"
    assert not re.search(r"\b[AB]\d+\b", addendum), "an exemplar id survived redaction"
    assert not [k for k in B.FORBIDDEN_IN_PROSE if k in low]
    assert not [c for c in DRAWN_IDS if c in addendum]
    blob = (G2 / "draw_manifest.json").read_text()
    assert not [c for c in DRAWN_IDS if c in blob], "draw_manifest.json leaks a drawn id"


# ===========================================================================
# 3. allocation — Option C (§14.2, §14.3)
# ===========================================================================

def test_p_allocation_is_the_pre_registered_hamilton(frame_cells, drawn_labels):
    """Derive the allocation from the frame, then check it three ways:
    derived == design §14.2 table == realized draw."""
    cells = frame_cells.groupby(["section_type", "home_sector"]).size()
    derived = {k: int(v) for k, v in B.hamilton(cells, B.N_PRIMARY).items()}
    assert derived == DESIGN_P_ALLOC, (
        "Hamilton allocation re-derived from the frame differs from design "
        f"§14.2's pre-registered n=400 table: {derived}")
    # §14.2's own licensing check: the same code reproduces §3.1's n=300 table.
    assert {k: int(v) for k, v in B.hamilton(cells, 300).items()} == \
        DESIGN_P_ALLOC_N300, "the Hamilton rule changed under the re-pin"
    p = drawn_labels[drawn_labels.arm == "P"].join(
        frame_cells.set_index("chunk_id")[["home_sector"]])
    realized = {k: int(v) for k, v in
                p.groupby(["section_type", "home_sector"]).size().items()}
    assert realized == DESIGN_P_ALLOC, f"realized P cells != allocation: {realized}"
    assert {k: int(v) for k, v in MANIFEST["allocation_p"].items()} == \
        {f"{s}|{k}": v for (s, k), v in DESIGN_P_ALLOC.items()}
    assert sum(DESIGN_P_ALLOC.values()) == B.N_PRIMARY == 400
    assert min(DESIGN_P_ALLOC.values()) == 8, "§14.2's smallest cell is 8"


def test_ga_quota_is_the_elementwise_max_of_proportional_and_floor(
        ga_frame_counts, drawn_labels):
    """§14.3: target_d = max(hamilton_d(N_GA), floor_d), no direction reduced,
    unspent floor budget NOT reallocated. Derived from the frame, checked
    against the design table, the manifest and the realized draw."""
    assert ga_frame_counts == DESIGN_GA_CORPUS_COUNTS, (
        f"active EX99 frame re-derived from labels_e2_v1 = {ga_frame_counts}, "
        "not §14.3's pinned N_d — the frame moved, so the weights moved")
    assert sum(ga_frame_counts.values()) == DESIGN_GA_FRAME == MANIFEST["arm_frames"]["G-A"]

    prop = {k: int(v) for k, v in
            B.hamilton(pd.Series(ga_frame_counts), B.N_GA).items()}
    assert prop == DESIGN_GA_PROPORTIONAL, f"proportional base at n=80: {prop}"
    target = {d: max(prop[d], DESIGN_GA_FLOOR.get(d, 0)) for d in B.ACTIVE_GUIDANCE}
    assert target == DESIGN_GA_ALLOC, f"max(proportional, floor) = {target}"
    added = {d: target[d] - prop[d] for d in B.ACTIVE_GUIDANCE}
    assert added == DESIGN_GA_QUOTA_ADDED, (
        f"rows bought by the quota = {added}; §14.3 buys +6 LOWERED (floor) and "
        "+14 WITHDRAWN (the 2026-09-07 amendment) and spends nothing else")
    assert sum(target.values()) == B.N_GA_TOTAL == 100
    assert sum(added.values()) == 20, (
        "the '+30-row floor' costs 20 rows, not 30: MAINTAINED's floor of 20 is "
        "already met by the proportional 24 and the remainder is NOT reallocated")

    ga = drawn_labels[drawn_labels.arm == "G-A"]
    realized = {d: int((ga.guidance_direction == d).sum()) for d in B.ACTIVE_GUIDANCE}
    assert realized == DESIGN_GA_ALLOC, f"realized G-A direction mix {realized}"
    assert MANIFEST["allocation_ga"] == DESIGN_GA_ALLOC
    assert MANIFEST["allocation_ga_proportional"] == DESIGN_GA_PROPORTIONAL
    assert MANIFEST["allocation_ga_quota_added"] == DESIGN_GA_QUOTA_ADDED
    # sub-arm counts live in the manifest only (§14.8 / test_draw_csv_...)
    assert MANIFEST["realized"]["subarm_counts"] == {
        "P": 400, "G-A": 80, "G-N": 80, "G-A-floor": 6, "G-A-withdrawn": 14}


def test_ga_weights_are_re_derived_from_the_frame(ga_frame_counts):
    """§14.4: w_d = N_d / 6479, asserted to 6 dp in both tools and the manifest.
    A weight that drifts silently re-defines the pooled estimand."""
    w, tot = A.ga_weights_from_counts(ga_frame_counts)
    assert tot == DESIGN_GA_FRAME
    six = {d: round(w[d], 6) for d in B.ACTIVE_GUIDANCE}
    assert six == DESIGN_GA_WEIGHTS, six
    assert MANIFEST["ga_weights"] == DESIGN_GA_WEIGHTS
    assert B.GA_WEIGHTS == DESIGN_GA_WEIGHTS
    assert B.GA_CORPUS_COUNTS == DESIGN_GA_CORPUS_COUNTS == A.RATIFIED["ga_corpus_counts"]
    assert abs(sum(w.values()) - 1.0) < 1e-12


def test_arms_are_disjoint_and_batched_without_homogeneity(frame_cells):
    by_arm = {a: set(g.chunk_id) for a, g in DRAW.groupby("arm")}
    assert {a: len(s) for a, s in by_arm.items()} == DESIGN_ARMS
    assert len(set.union(*by_arm.values())) == DESIGN_N_TOTAL == len(DRAW)
    assert DRAW.chunk_id.is_unique, "a chunk was drawn into two arms"
    sizes = DRAW.batch.value_counts().sort_index().to_dict()
    assert sizes == {**{f"batch_{i:02d}": 40 for i in range(1, 15)}, "batch_15": 20}
    assert sizes == MANIFEST["batches"] and len(sizes) == MANIFEST["n_batches"] == 15
    meta = frame_cells.set_index("chunk_id")
    for b, g in DRAW.groupby("batch"):
        assert g.arm.nunique() > 1, f"{b} is arm-homogeneous (§3.1: rater drift)"
        assert meta.section_type[g.chunk_id].nunique() > 1, f"{b} is section-homogeneous"
        assert meta.home_sector[g.chunk_id].nunique() > 1, f"{b} is sector-homogeneous"


# ===========================================================================
# 4. every drawn chunk really is in its arm's frame
# ===========================================================================

def test_drawn_rows_are_in_frame(drawn_labels, capsys):
    assert len(drawn_labels) == DESIGN_N_TOTAL, \
        "a drawn chunk_id is absent from labels_e2_v1.parquet"
    assert drawn_labels.parse_ok.all(), "a drawn row has parse_ok false (§2.1)"
    assert (drawn_labels.section_type != "8K_BODY").all(), (
        "8K_BODY reached the draw — RUN_COMMANDS trap 7 / design §2.3 exclude it")
    # derive-and-report: design §2.1 keeps the 23 schema-invalid rows in frame,
    # so this is a reported composition with a frame-level ceiling, not a pin.
    n_invalid = int((~drawn_labels.schema_valid).sum())
    with capsys.disabled():
        print(f"\n  [report] drawn rows with schema_valid=false: {n_invalid}/"
              f"{DESIGN_N_TOTAL} (design §2.1 keeps all 23 such frame rows eligible)")
    assert n_invalid <= 23, f"{n_invalid} schema-invalid rows > the 23 in the frame"


def test_arm_frame_predicates_hold(drawn_labels):
    ga = drawn_labels[drawn_labels.arm == "G-A"]
    assert (ga.section_type == "EX99_PRESS_RELEASE").all()
    assert ga.guidance_direction.isin(B.ACTIVE_GUIDANCE).all(), (
        "a G-A row does not carry a stored active guidance direction (§3.2)")
    assert not ga.guidance_imputed_none.fillna(False).any()

    gn = drawn_labels[drawn_labels.arm == "G-N"]
    assert (gn.section_type == "EX99_PRESS_RELEASE").all()
    assert gn.guidance_imputed_none.fillna(False).all(), (
        "a G-N row is not guidance_imputed_none (§3.3 — the arm's whole point)")
    assert (gn.guidance_direction == "NONE").all()

    p = drawn_labels[drawn_labels.arm == "P"]
    assert set(p.section_type) <= set(B.SECTIONS)
    # §14.2's evaluable bases, which §6.3's caveat arithmetic and §14.6's
    # decision boundaries are computed on
    sec_ok = {f: A.APPLICABLE[f] for f in ("sentiment", "guidance_direction")}
    for f, secs in sec_ok.items():
        assert int(p.section_type.isin(secs).sum()) == DESIGN_P_EVALUABLE[f], f
    # §14.7's escalation denominator, across all three arms
    for f, want in DESIGN_EVALUABLE_ALL_ARMS.items():
        got = int(drawn_labels.section_type.isin(A.APPLICABLE[f]).sum())
        assert got == want, f"{f}: {got} applicable rows in the draw, expected {want}"


# ===========================================================================
# 5. analyzer estimators, on synthetic verdicts
# ===========================================================================

def _wilson_by_roots(k, n, z=1.96):
    """Wilson bounds as the roots of (p_hat - p)^2 = z^2 p(1-p)/n.

    Written from the definition, independently of analyze_g2.wilson()'s
    centre +- half-width arrangement.
    """
    ph = k / n
    a = 1 + z * z / n
    b = -(2 * ph + z * z / n)
    c = ph * ph
    disc = sqrt(b * b - 4 * a * c)
    return ((-b - disc) / (2 * a), (-b + disc) / (2 * a))


def test_wilson_matches_hand_values_and_an_independent_derivation():
    assert A.wilson(10, 40) == pytest.approx((0.14186967895549518, 0.40194259066970106), abs=1e-12)
    assert A.wilson(0, 20)[1] == pytest.approx(0.16113012549493322, abs=1e-12)  # §5.5 probe bound
    assert A.wilson(36, 40) == pytest.approx((0.7694792561952611, 0.9604211124044252), abs=1e-12)
    for k, n in [(0, 20), (1, 80), (10, 40), (46, 100), (300, 337), (119, 119)]:
        assert A.wilson(k, n) == pytest.approx(_wilson_by_roots(k, n), abs=1e-12), (k, n)
    assert all(np.isnan(x) for x in A.wilson(0, 0)), "n=0 must be nan, not a crash"
    # wilson(k, n) delegates to wilson_p(p, n), the primitive §14.4's pooled
    # interval needs at a NON-INTEGER effective n.
    assert A.wilson_p(300 / 337, 337) == pytest.approx(A.wilson(300, 337), abs=1e-15)
    assert A.wilson_p(0.8, 85.18) == pytest.approx(
        _wilson_by_roots(0.8 * 85.18, 85.18), abs=1e-12)


def test_kstar_boundaries_monotonicity_and_the_ratified_design_table():
    # §14.6, the ratified (n, b) — plus §6.2/§6.3's pinned rows, which are the
    # licensing check that the same primitives reproduce the older tables.
    for n, b, kp, kf in [(337, 0.85, 300, 273), (119, 0.85, 109, 93),
                         (253, 0.85, 227, 203), (253, 0.90, 238, 218),
                         (90, 0.90, 87, 75), (90, 0.85, 84, 69),
                         (59, 0.90, 58, 48), (119, 0.90, 114, 100)]:
        assert (A.kstar_pass(n, b), A.kstar_fail(n, b)) == (kp, kf), (n, b)
        # k* is the *boundary*: one fewer agreement does not pass, one more
        # agreement is no longer a decisive fail.
        assert A.wilson(kp, n)[0] >= b > A.wilson(kp - 1, n)[0]
        assert A.wilson(kf, n)[1] < b <= A.wilson(kf + 1, n)[1]
        assert kf < kp, "PASS and DECISIVE_FAIL regions must not touch"
        assert A.verdict_of(kp, n, b) == "PASS"
        assert A.verdict_of(kf, n, b) == "DECISIVE_FAIL"
        assert A.verdict_of((kp + kf) // 2, n, b) == "INDETERMINATE"
    # §14.6 quotes the boundaries as p-hats too; those are what a report reads.
    for field, n, b, kp, php, kf, phf in DESIGN_BOUNDARIES:
        assert DESIGN_BARS[field] == b
        assert round(kp / n, 4) == php and round(kf / n, 4) == phf, field
    # None means a PASS is arithmetically unreachable at that n (the report
    # prints "UNREACHABLE at n=..."), so it ranks above every attainable k*.
    assert A.kstar_pass(59, 0.95) is None and A.wilson(59, 59)[0] < 0.95, \
        "an unreachable bar must return None, not a k* that cannot pass"
    bars = [0.70, 0.80, 0.85, 0.90, 0.95]
    for n in (80, 119, 337):
        ks = [n + 1 if k is None else k for k in (A.kstar_pass(n, b) for b in bars)]
        assert ks == sorted(ks), f"kstar_pass not monotone in the bar at n={n}: {ks}"
    kk = [A.kstar_pass(n, 0.90) for n in (59, 90, 119, 168, 253, 337)]
    assert kk == sorted(kk), f"kstar_pass not monotone in n: {kk}"


def _synthetic():
    """Six chunks exercising masking, both omission conventions, imputed NONE,
    unsure, and an exact-set red-flag disagreement."""
    draw = pd.DataFrame({
        "rank": range(1, 7), "batch": ["batch_01"] * 6,
        "arm": ["P", "P", "P", "P", "G-N", "G-A"],
        "chunk_id": [f"s{i}" for i in range(1, 7)]})
    section_of = {"s1": "MDA", "s2": "MDA", "s3": "RISK_FACTORS",
                  "s4": "EX99_PRESS_RELEASE", "s5": "EX99_PRESS_RELEASE",
                  "s6": "EX99_PRESS_RELEASE"}
    raw = {
        # s1: clean MDA; its stored off-matrix guidance must be masked
        "s1": {"sentiment": "NEUTRAL", "guidance_direction": "NONE", "red_flags": []},
        # s2: stored sentiment omitted -> pinned error regardless of the rater
        "s2": {"sentiment": None, "guidance_direction": None, "red_flags": []},
        # s3: off-matrix stored sentiment on RISK_FACTORS -> masked
        "s3": {"sentiment": "NEGATIVE", "guidance_direction": None,
               "red_flags": [{"category": "DEMAND_WEAKNESS", "modality": "REALIZED"}]},
        # s4: contested sentiment ruled unsure; guidance agrees
        "s4": {"sentiment": "POSITIVE", "guidance_direction": "RAISED", "red_flags": []},
        # s5: writer-rule imputed NONE, scored AS NONE
        "s5": {"sentiment": "NEUTRAL", "guidance_direction": "NONE", "red_flags": []},
        # s6: guidance disagreement upheld by the adjudicator
        "s6": {"sentiment": "NEUTRAL", "guidance_direction": "MAINTAINED", "red_flags": []},
    }
    stored = {c: A.stored_values(v, True) for c, v in raw.items()}
    rater = {
        "s1": {"sentiment": "NEUTRAL", "guidance_direction": "NONE", A.RED: frozenset()},
        "s2": {"sentiment": "NEUTRAL", "guidance_direction": "NONE", A.RED: frozenset()},
        "s3": {"sentiment": "POSITIVE", "guidance_direction": "NONE",
               A.RED: A.as_set([["DEMAND_WEAKNESS", "HYPOTHETICAL"],
                                ["MARGIN_COST_PRESSURE", "REALIZED"]])},
        "s4": {"sentiment": "NEGATIVE", "guidance_direction": "RAISED", A.RED: frozenset()},
        "s5": {"sentiment": "NEUTRAL", "guidance_direction": "NONE", A.RED: frozenset()},
        "s6": {"sentiment": "NEUTRAL", "guidance_direction": "LOWERED", A.RED: frozenset()},
    }
    adj = {("s4", "sentiment"): {"verdict": "unsure", "correct_label": None},
           ("s6", "guidance_direction"): {"verdict": "disagree", "correct_label": "LOWERED"},
           ("s3", "red_flags"): {"verdict": "disagree",
                                 "correct_label": [["DEMAND_WEAKNESS", "HYPOTHETICAL"],
                                                   ["MARGIN_COST_PRESSURE", "REALIZED"]]}}
    return A.score(draw, stored, section_of, rater, adj, {}, True)


def test_applicability_masking_and_omission_conventions():
    sc = _synthetic()
    assert set(sc.field) == {"sentiment", "guidance_direction", "red_flags"}, \
        "distress_tier must never be scored (HANDOFF §7)"

    def row(cid, field):
        return sc[(sc.chunk_id == cid) & (sc.field == field)].iloc[0]

    assert row("s3", "sentiment").basis == "masked", \
        "sentiment on RISK_FACTORS must be collected and discarded (§1.2/§3.4)"
    assert np.isnan(row("s3", "sentiment").err)
    assert row("s1", "guidance_direction").basis == "masked", \
        "guidance on MDA must be masked even though a value is stored (§3.4)"
    assert row("s2", "sentiment").err == 1.0
    assert row("s2", "sentiment").basis == "omission_pinned_error", \
        "a stored null on an applicable row is a pre-registered error (§1.3)"
    assert row("s5", "guidance_direction").err == 0.0, \
        "an imputed NONE is scored AS NONE, not as an omission (§1.3)"
    assert row("s6", "guidance_direction").err == 1.0
    assert row("s1", "sentiment").err == 0.0 and row("s1", "sentiment").basis == "uncontested"

    sent = sc[(sc.field == "sentiment") & sc.applicable]
    assert A.counts(sent)[:4] == (3, 1, 4, 1), (
        "expected 3 agree / 1 error / n=4 evaluable / 1 unsure; got "
        f"{A.counts(sent)[:4]}")


def test_unsure_is_removed_from_the_rate_and_bracketed():
    sc = _synthetic()
    sent = sc[(sc.field == "sentiment") & sc.applicable]
    blk = A.primary_block(sent, DESIGN_BARS["sentiment"], "test")
    assert blk["n"] == 4 and blk["n_unsure"] == 1 and blk["k"] == 3, blk
    assert blk["p_hat"] == 0.75, "the unsure row must leave numerator AND denominator"
    lo, hi = A.wilson(3, 4)
    assert blk["sens_all_error"] == pytest.approx(list(A.wilson(3, 5)))
    assert blk["sens_all_agree"] == pytest.approx(list(A.wilson(4, 5)))
    assert blk["sens_all_error"][0] <= lo and blk["sens_all_agree"][1] >= hi, \
        "the pre-registered sensitivity must bracket the point interval (§10.2.4)"
    assert blk["n_omission_pinned_errors"] == 1
    assert blk["bar"] == 0.85, "the verdict is emitted at the ONE ratified bar (§14.1 ii)"
    assert blk["verdict"] in {"PASS", "DECISIVE_FAIL", "INDETERMINATE"}


def test_exact_set_error_and_per_category_decomposition():
    sc = _synthetic()
    rf = sc[sc.field == "red_flags"]
    assert A.as_set([{"category": "DEMAND_WEAKNESS", "modality": "REALIZED"}]) == \
        A.as_set([["DEMAND_WEAKNESS", "REALIZED"]]), \
        "struct-list and list-of-lists red_flags must normalize identically"
    s3 = rf[rf.chunk_id == "s3"].iloc[0]
    assert s3.err == 1.0, "one modality flip plus one missed flag is an exact-set error"
    # a chunk both sides scored as no-flags is an agreement, not a vacuous error
    assert rf[rf.chunk_id == "s1"].iloc[0].err == 0.0
    sent = sc[(sc.field == "sentiment") & sc.applicable]
    guid = sc[(sc.field == "guidance_direction") & sc.applicable]
    err = A._s_err(sent, guid, rf, True)
    assert err["red_flags"] == {"spurious_flags": 0, "missed_flags": 1,
                                "wrong_modality": 1, "note": err["red_flags"]["note"]}, \
        err["red_flags"]
    exact_set = A.rate_block(rf[rf.applicable], count_errors=True)
    assert (exact_set["k"], exact_set["n"], exact_set["scale"]) == (1, 6, "error"), \
        f"exact-set error should be 1 of 6 rated chunks: {exact_set}"
    assert A.RED_FLAGS_STATUS in A._red_flag_caveat(exact_set, {}, True), \
        "the rewritten caveat must restate the 2026-08-27 demotion verbatim (§10.2.7 item 9)"


def test_rater_schema_guard_flags_the_auditor_fallback_and_passes_clean_input():
    ok = {"chunk_id": "c1", "sentiment": "NEUTRAL", "guidance_direction": "NONE",
          "red_flags": [["DEMAND_WEAKNESS", "REALIZED"]], "reason": "x"}
    assert A.check_rater_objects("t.json", [ok], {"c1"}, True) == ["c1"], \
        "the guard must not cry wolf on a conforming rater file"
    for bad, why in [
            ({**ok, "verdict": "agree"}, "the label-auditor 'verdict' key"),
            ({**ok, "sentiment": "n/a"}, "an 'n/a' applicability leak"),
            ({**ok, "sentiment": None}, "a null label"),
            ({**ok, "guidance_direction": "MAYBE"}, "an enum violation"),
            ({**ok, "chunk_id": "zz"}, "a chunk_id from another batch"),
            ({**ok, "distress_tier": "GOING_CONCERN"}, "a distress_tier key")]:
        try:
            A.check_rater_objects("t.json", [bad], {"c1"}, True)
        except AssertionError:
            continue
        pytest.fail(f"the §10.2.1 rater guard missed {why} — that is a FAILED "
                    "BATCH (§11.3), not a finding to interpret at analysis time")


# ===========================================================================
# 6. the quota re-weighting (§14.4) — the ONE estimator the ruling added
# ===========================================================================

def _ga_rows(k_by_dir, n_by_dir):
    """A minimal G-A scoring frame: k agreements and n-k errors per direction."""
    rows = []
    for d, n in n_by_dir.items():
        for i in range(n):
            rows.append({"stored": d, "err": 0.0 if i < k_by_dir[d] else 1.0,
                         "basis": "uncontested"})
    return pd.DataFrame(rows)


def test_ga_quota_reweighting_on_a_hand_computed_case():
    """The arm is no longer proportional, so the pooled number must be the
    corpus-share-weighted one. Hand case: p_d = (0.8, 0.5, 1.0, 0.0)."""
    w, _ = A.ga_weights_from_counts(DESIGN_GA_CORPUS_COUNTS)
    k = {"RAISED": 8, "MAINTAINED": 2, "LOWERED": 2, "WITHDRAWN": 0}
    n = {"RAISED": 10, "MAINTAINED": 4, "LOWERED": 2, "WITHDRAWN": 2}
    # by hand, with the exact frame fractions:
    #   (3716*0.8 + 1940*0.5 + 757*1.0 + 66*0.0) / 6479 = 4699.8 / 6479
    hand = (3716 * 0.8 + 1940 * 0.5 + 757 * 1.0) / 6479
    assert round(hand, 7) == 0.7253897

    pooled, by_dir = A.ga_reweighted(_ga_rows(k, n), w, complete=True)
    assert pooled["point"] == pytest.approx(hand, abs=1e-12), pooled["point"]
    assert pooled["p_hat_unweighted_do_not_quote"] == pytest.approx(12 / 18), (
        "the unweighted proportion must still be computed and labelled "
        "do-not-quote — it is what the quota would distort")
    assert (pooled["wilson_lo"], pooled["wilson_hi"]) == pytest.approx(
        A.wilson_p(pooled["point"], pooled["n_eff"]), abs=1e-12), \
        "the interval must be the §10.0 Wilson primitive evaluated at n_eff"
    assert pooled["n_nominal"] == 18 and pooled["n_eff"] < 18, (
        "n_eff is the price of the quota and must be REPORTED beside the "
        f"interval, never replaced by the nominal n: {pooled['n_eff']}")
    assert pooled["design_effect"] == pytest.approx(18 / pooled["n_eff"])
    assert pooled["bar"] is None, "no floor on G-A (owner rulings (iv), (vi))"
    assert pooled["weights"] == {d: w[d] for d in B.ACTIVE_GUIDANCE}
    assert sum(pooled["weights"].values()) == pytest.approx(1.0, abs=1e-12)
    for d, blk in by_dir.items():
        assert blk["bar"] is None and blk["note"], \
            f"{d} must ship as a DISCLOSURE with no bar (ruling (vi))"
        assert blk["p_hat"] == pytest.approx(k[d] / n[d])
        assert "verdict" not in blk

    # §14.4's three pre-registered behaviours, at the REAL arm sizes
    real_n = DESIGN_GA_ALLOC
    flat = A.ga_pooled({d: 0.8 * v for d, v in real_n.items()}, real_n, w)
    assert (round(flat["point"], 3), round(flat["n_eff"], 1),
            round(flat["wilson_lo"], 3), round(flat["wilson_hi"], 3)) == \
        (0.800, 85.2, 0.703, 0.871), flat
    perfect = A.ga_pooled({d: float(v) for d, v in real_n.items()}, real_n, w)
    assert round(perfect["n_eff"], 1) == 89.3 and perfect["wilson_hi"] <= 1.0
    assert round(perfect["wilson_lo"], 3) == 0.959, (
        "at p_d = 1 the interval must be non-degenerate — that is why the "
        "delta-method interval was rejected (§14.4)")
    mixed = A.ga_pooled({"RAISED": .90 * 46, "MAINTAINED": .85 * 24,
                         "LOWERED": .70 * 15, "WITHDRAWN": .60 * 15}, real_n, w)
    assert (round(mixed["point"], 4), round(mixed["n_eff"], 1)) == (0.8586, 90.9)
    assert round(mixed["wilson_lo"], 3) == 0.772 and round(mixed["wilson_hi"], 3) == 0.916


def test_an_empty_ga_direction_is_never_silently_renormalised():
    """§10.2.4: dropping a stratum changes the estimand. Before the arm is
    complete the pooled point is simply not computed; once it is complete an
    empty direction is a hard fail."""
    w, _ = A.ga_weights_from_counts(DESIGN_GA_CORPUS_COUNTS)
    k = {"RAISED": 8, "MAINTAINED": 2, "LOWERED": 2, "WITHDRAWN": 0}
    n = {"RAISED": 10, "MAINTAINED": 4, "LOWERED": 2, "WITHDRAWN": 0}
    pooled, by_dir = A.ga_reweighted(_ga_rows(k, n), w, complete=False)
    assert pooled["point"] is None and pooled["not_yet_available"] is True
    assert pooled["empty_directions"] == ["WITHDRAWN"]
    assert "WITHDRAWN" in pooled["blocked_reason"]
    assert sum(pooled["weights"].values()) == pytest.approx(1.0, abs=1e-12), \
        "the weights were renormalised over the surviving directions"
    assert pooled["weights"]["WITHDRAWN"] == w["WITHDRAWN"]
    with pytest.raises(AssertionError, match="WITHDRAWN"):
        A.ga_reweighted(_ga_rows(k, n), w, complete=True)


# ===========================================================================
# 7. the analyzer's parameter guard, and its degraded path
# ===========================================================================

def test_analyze_refuses_unratified_parameters_and_proceeds_on_the_ruled_ones(
        tmp_path, capsys, monkeypatch):
    """Bar-shopping guard, re-pinned to the ruled bars (§14.1 (ii), §10.0).

    Three must-flag legs — an unset bar, an un-ratified parameter block, and a
    bar EDITED after the draw (the degree of freedom that survives ratification)
    — and one must-not-cry-wolf leg: on the real manifest the analyzer proceeds,
    stops on the missing verdict files, and writes nothing.
    """
    work = tmp_path / "g2"
    work.mkdir()
    (work / "draw_g2.csv").write_bytes((G2 / "draw_g2.csv").read_bytes())
    # §14.9: the arm sidecar sits OUTSIDE the g2 dir, so it mirrors to work.parent
    (work.parent / "g2_draw_arms.csv").write_bytes(
        (G2.parent / "g2_draw_arms.csv").read_bytes())
    monkeypatch.setattr(A, "G2", work)
    verdict_words = ("PASS", "DECISIVE_FAIL", "INDETERMINATE")

    # (1) no bar -> refusal, exit 2, no p-hat
    man = dict(MANIFEST)
    man["ratified_bars"] = None
    (work / "draw_manifest.json").write_text(json.dumps(man))
    assert A.analyze() == 2
    out = capsys.readouterr().out
    assert "BLOCKED" in out and "ratified_bars" in out
    assert not any(w in out for w in verdict_words), \
        "a verdict word escaped before the bar was ratified"
    assert not (work / "results_g2.json").exists()

    # (2) parameters not owner-ratified -> the same refusal, same reason
    man = dict(MANIFEST)
    man["parameters_status"] = "PROPOSED"
    (work / "draw_manifest.json").write_text(json.dumps(man))
    assert A.analyze() == 2
    out = capsys.readouterr().out
    assert "BLOCKED" in out and "parameters_status" in out
    assert not any(w in out for w in verdict_words)

    # (3) a ratified parameter EDITED after the draw -> hard fail, by name.
    # Fabricating a bar in the manifest is exactly what must not be possible.
    for field, value in [("ratified_bars", {"sentiment": 0.90,
                                            "guidance_direction": 0.90}),
                         ("n_primary", 300)]:
        man = dict(MANIFEST)
        man[field] = value
        (work / "draw_manifest.json").write_text(json.dumps(man))
        with pytest.raises(AssertionError, match=field):
            A.analyze()

    # (4) the real, owner-ratified manifest: no block, degraded, invents nothing
    (work / "draw_manifest.json").write_bytes((G2 / "draw_manifest.json").read_bytes())
    rc = A.analyze()
    out = capsys.readouterr().out
    assert rc == 0 and "BLOCKED" not in out, (
        "with the owner's parameters in the manifest the analyzer must proceed "
        f"(it then stops on the missing verdict files). rc={rc}\n{out}")
    assert "not yet available" in out
    assert sorted(p.name for p in work.iterdir()) == ["draw_g2.csv", "draw_manifest.json"], \
        "the analyzer wrote an artifact while degraded — it must invent nothing"


def test_analyzer_selftest_passes(capsys):
    """analyze_g2.py --selftest is the estimators' own pre-registration in
    code; running it here keeps it from rotting outside the suite."""
    assert A.selftest() == 0
    out = capsys.readouterr().out
    n_checks = int(re.search(r"SELFTEST PASSED — (\d+) checks", out).group(1))
    with capsys.disabled():
        print(f"\n  [report] analyze_g2.py --selftest: {n_checks} checks passed")
    assert n_checks >= SELFTEST_CHECKS_MIN, (
        f"{n_checks} selftest checks < the {SELFTEST_CHECKS_MIN} pinned on "
        "2026-09-07 — a pre-registered estimator check was removed")


def test_g2_tooling_is_offline_by_construction():
    for path in (G2 / "build_draw_g2.py", G2 / "analyze_g2.py"):
        src = path.read_text()
        for mod in A.NETWORK_MODULES + ("socket", "urllib"):
            assert not re.search(rf"^\s*(import|from)\s+{mod}\b", src, re.M), \
                f"{path.name} imports {mod} — the G2 lane is 0 network calls, $0"
        assert "api_key" not in src.lower()


# ===========================================================================
# 8. the 2026-09-07 §14.9 fix pass — each defect it removed, pinned
# ===========================================================================

def _blk(verdict, n=119, k=118, bar=0.85):
    return {"k": k, "n": n, "p_hat": k / n, "wilson_lo": 0.95, "wilson_hi": 0.999,
            "bar": bar, "verdict": verdict,
            "operating_characteristics_at_realized_n": {
                "P_DECISIVE_FAIL_if_q_0.83": 0.93, "P_DECISIVE_FAIL_if_q_0.85": 0.72}}


GA_STUB = {"point": 0.80, "wilson_lo": 0.70, "wilson_hi": 0.87,
           "n_eff": 85.2, "n_nominal": 100}
GN_STUB = {"k": 3, "n": 80}


@pytest.mark.parametrize("verdict", ["PASS", "INDETERMINATE", "DECISIVE_FAIL"])
def test_guidance_verdict_is_never_stated_without_its_two_arms(verdict):
    """Owner ruling (vii) OPTION 1, enforced on the PROSE too (§6.6, §14.9).

    Before the fix this paragraph read "The G2 spot-check returned PASS for
    `guidance_direction`. Measured agreement is 100.00% …" with neither arm on
    it, and A8's token scan never saw it.
    """
    text = A._non_fail_wording("guidance_direction", _blk(verdict), GA_STUB, GN_STUB)
    assert "guidance_active_precision" in text and "guidance_false_none_rate" in text
    assert A.guidance_verdict_is_escorted(text)
    # the guard is live: strip the escort and it must reject the same sentence
    assert not A.guidance_verdict_is_escorted(
        text.split("Binding, ruling (vii)")[0])


@pytest.mark.parametrize("verdict", ["PASS", "INDETERMINATE", "DECISIVE_FAIL"])
def test_non_fail_wording_is_the_pre_registered_clause_and_is_verdict_gated(verdict):
    """§6.6's opening clause, verbatim, and no unmeasured 0.94 endpoint."""
    text = A._non_fail_wording("sentiment", _blk(verdict), GA_STUB, GN_STUB)
    assert "returned PASS" not in text, (
        "'returned PASS' reads as a clearance — §6.6 exists to weaken exactly "
        "that sentence (§14.9 item 3)")
    assert "0.94" not in text, (
        "the hardcoded 0.94 upper endpoint is back; it was never recomputed at "
        "any (n, bar) and shipped as a malformed interval (§14.9 item 2)")
    if verdict == "DECISIVE_FAIL":
        assert "DID trigger a decisive failure" in text and "§6.5" in text
    else:
        assert text.startswith("The G2 spot-check did not trigger a decisive failure")


def test_appendix_at_a_non_ratified_bar_prints_only_what_the_bar_changes():
    """§10.2.7 item 1 as amended (§14.9): k* only — p-hat and CI do not depend
    on the bar, so reprinting them duplicated the ratified bar's numbers under
    an un-ratified bar's heading."""
    src = (G2 / "analyze_g2.py").read_text()
    block = src.split("appendix = {}")[1].split("# ---- G-A")[0]
    for banned in ('"p_hat": b[', '"wilson_lo"', '"wilson_hi"'):
        assert banned not in block, f"appendix reprints {banned} (§14.9 item 6)"
    assert "k_required_to_clear" in block and "kstar_fail" in block


def test_ceiling_arm_size_is_measured_from_the_draw_not_projected():
    """§14.5 as amended (§14.9): 110 / 65 realized, not the ~107 / ~62 planned."""
    lab = pd.read_parquet(REPO / "data/f4/labels_e2_v1.parquet",
                          columns=["chunk_id", "section_type"])
    section_of = dict(zip(lab.chunk_id, lab.section_type))
    got = A.ceiling_realized_n(DRAW, section_of, MANIFEST["ceiling_batches"])
    assert got == {"sentiment": 110, "guidance_direction": 65}, got
    assert A.CEILING_PLANNED_N == {"sentiment": 107, "guidance_direction": 62}, \
        "CEILING_PLANNED_N is the labelled PLANNING value and stays visible"


def test_guidance_base_caveat_counts_come_from_the_realized_draw():
    """§6.3's caveat quoted "~61 / ~8" while the draw was fixed (§14.9 item 5)."""
    lab = pd.read_parquet(REPO / "data/f4/labels_e2_v1.parquet",
                          columns=["chunk_id", "section_type", "guidance_direction",
                                   "guidance_imputed_none"])
    p_ids = set(DRAW.loc[DRAW.arm == "P", "chunk_id"])
    ex = lab[lab.chunk_id.isin(p_ids) & (lab.section_type == "EX99_PRESS_RELEASE")]
    n, imp = len(ex), int(ex.guidance_imputed_none.fillna(False).astype(bool).sum())
    act = int(ex.guidance_direction.isin(A.ACTIVE_GUIDANCE).sum())
    assert (n, imp, act) == (119, 60, 9), (n, imp, act)
    text = A.guidance_base_caveat(n, imp, act)
    assert "119 EX99 rows" in text and " 60 are " in text and "only 9 carry" in text
    assert "~" not in text, "a planning approximation survived in the caveat"


def test_failed_batch_causes_are_the_enumerated_five():
    """§11.3 gets a writable home (§14.9 item 7); the cause set stays closed so
    the two-attempt re-run channel cannot become a selection channel."""
    assert A.FAILED_BATCH_CAUSES == {
        "agent_errored", "non_parsing_json", "chunk_id_set_mismatch",
        "missing_required_field", "schema_violation"}
    assert "failed_batches.json" in (G2 / "G2_SPOTCHECK_design.md").read_text()


def test_dead_machinery_is_gone():
    """§14.9 item 9. The RNG stream NAME is deliberately kept: a SeedSequence
    child is identified by position, so dropping it would shift every
    G-A-quota stream and silently re-draw the quota."""
    src = (G2 / "build_draw_g2.py").read_text()
    assert "def simulate_cik_coverage" not in src
    assert "cik_coverage_simulation" not in json.dumps(MANIFEST)
    assert 'add_argument("--provisional"' not in src   # the docstring names it
    assert "cik_coverage_sim__reserved" in src, (
        "the reserved stream name was removed — every G-A-quota stream shifts "
        "and the drawn quota rows change")
