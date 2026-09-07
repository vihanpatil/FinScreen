"""
test_rubric_v12_sync.py — pins rubric v1.2 and the v12_relabel request build.

Two jobs:
  1. THE SYNC RULE (HANDOFF §3 2026-08-10 / §7). `labeling_rubric.md` is
     authoritative; `build_batch_requests.SYSTEM_PROMPT` is a hand-synced
     leaner restatement. These tests pin that the three ratified v1.2
     rules landed in BOTH, and — just as important — that the categories
     v1.2 did NOT touch (sentiment, guidance direction) are still
     byte-identical to the v1.1 prompt E1 actually shipped.
  2. THE REQUEST BUILD. Single-axis discipline (HANDOFF §3 2026-08-26):
     the v12_relabel variant must differ from E1's final pass in the
     system prompt and nothing else, and must never write to a frozen E1
     artifact path.

HARD CONSTRAINT: offline. No `anthropic` import, no network, no .env.
Tests that would reach a client stub it via monkeypatch.

Run: python3 -m pytest test_rubric_v12_sync.py -v
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

import build_batch_requests as B
import submit_labeling_batch as S

REPO = Path(__file__).resolve().parent
RUBRIC = REPO / "labeling_rubric.md"
V12_REQUESTS = REPO / "data" / "batch_requests_v12.jsonl"
E1_FINAL_REQUESTS = REPO / "data" / "batch_requests_relabel.jsonl"

# Frozen E1 artifacts that this campaign must never write to.
FROZEN_PATHS = {
    "data/labels.parquet",
    "data/labels_pre_relabel.parquet",
    "data/labeling_corpus.parquet",
    "data/full_batch_meta.json",
    "data/relabel_batch_meta.json",
    "data/corrective_batch_meta.json",
    "data/batch_requests_relabel.jsonl",
    "data/batch_requests_corrective.jsonl",
}


def _first_request(path: Path) -> dict:
    with open(path) as f:
        return json.loads(f.readline())


def _system_text(req: dict) -> str:
    return req["params"]["system"][0]["text"]


@pytest.fixture(scope="module")
def v11_prompt() -> str:
    """The rubric-v1.1 SYSTEM_PROMPT exactly as E1 shipped it. Read from
    the real request file, not reconstructed — that file IS the record of
    what was submitted."""
    if not E1_FINAL_REQUESTS.exists():
        pytest.skip(f"{E1_FINAL_REQUESTS} not present in this checkout")
    return _system_text(_first_request(E1_FINAL_REQUESTS))


def _block(prompt: str, header: str) -> str:
    """One labelled block of the model-facing prompt, from its ALL-CAPS
    header up to the next one."""
    headers = ["SENTIMENT (when asked):", "GUIDANCE DIRECTION (when asked):",
               "RED FLAGS (when asked", "DISTRESS TIER (when asked",
               "MODALITY (required"]
    start = prompt.index(header)
    ends = [prompt.index(h) for h in headers if h != header and prompt.find(h) > start]
    return prompt[start: min(ends)] if ends else prompt[start:]


# =====================================================================
# 1. The sync rule
# =====================================================================
def test_rubric_file_declares_v12():
    text = RUBRIC.read_text()
    assert text.startswith("# Labeling Rubric")
    assert "Version 1.2 (ratified 2026-08-26" in text
    assert B.RUBRIC_VERSION == "v1.2"


def test_rubric_revision_log_records_the_ratification():
    text = RUBRIC.read_text()
    log = text[text.index("## 9. Revision log"):]
    assert "**v1.2 (RATIFIED 2026-08-26, applied same day).**" in log
    # The ratification must name where the owner's ruling lives.
    assert "HANDOFF.md" in log and "2026-08-26" in log
    # And it must be explicit about what v1.2 did NOT change.
    assert "Unchanged by v1.2" in log
    # P2 was deliberately not encoded — that must be stated, not silent.
    assert "Deliberately NOT encoded" in log and "P2" in log


@pytest.mark.parametrize(
    "name,rubric_marker,prompt_marker",
    [
        # P1 — realized controls modality (rubric §6)
        ("P1 realized-controls",
         "**Realized-controls rule (v1.2 — owner-ratified principle P1,",
         "REALIZED CONTROLS:"),
        # P3 — mining depth in enumerated risk lists (rubric §4)
        ("P3 mining-depth",
         "**Mining depth in enumerated risk lists (v1.2 — owner-ratified principle",
         "MINING DEPTH:"),
        # P3 corollary — causeless cost inflation (rubric §4 disambiguation)
        ("P3 corollary causeless-cost-inflation",
         "Cost-inflation language\nwith no named cause is *always* `MARGIN_COST_PRESSURE`",
         "Cost-inflation language with NO named cause is ALWAYS this category"),
    ],
)
def test_each_v12_rule_is_in_both_the_rubric_and_the_prompt(name, rubric_marker, prompt_marker):
    """The sync rule in its operative form: a rule that exists in only one
    of the two documents is exactly the drift this rule was written to
    prevent."""
    assert rubric_marker in RUBRIC.read_text(), f"{name}: missing from labeling_rubric.md"
    assert prompt_marker in B.SYSTEM_PROMPT, f"{name}: missing from SYSTEM_PROMPT"


def test_v12_rules_carry_the_same_substance_in_both_documents():
    """Beyond marker presence: the load-bearing phrases of each rule must
    appear in both, so a future edit cannot quietly weaken one side.

    The anchors are deliberately short. The sync rule (HANDOFF §3,
    2026-08-10) is "same rules, leaner wording — not a verbatim embed", so
    demanding sentence-level identity would be testing the wrong thing.
    """
    # The rubric is hard-wrapped markdown and the prompt is not, so
    # compare on whitespace-collapsed text.
    flat = lambda s: re.sub(r"\s+", " ", s).lower()  # noqa: E731
    rubric = flat(RUBRIC.read_text())
    prompt = flat(B.SYSTEM_PROMPT)
    for phrase in [
        # P1 — the existence claim wins over the safe-harbor framing, and
        # only the downstream consequence stays hypothetical.
        "forward-looking or safe-harbor sentence",
        "pending litigation",
        "consequences",
        # P3 — the mining-depth bar.
        "stand alone as a sentence about this company",
        # P3 corollary — the causeless-cost-inflation rule.
        "no named cause",
    ]:
        assert flat(phrase) in rubric, f"rubric missing: {phrase!r}"
        assert flat(phrase) in prompt, f"SYSTEM_PROMPT missing: {phrase!r}"


@pytest.mark.parametrize("header", ["SENTIMENT (when asked):", "GUIDANCE DIRECTION (when asked):"])
def test_categories_v12_did_not_touch_are_byte_identical_to_v11(v11_prompt, header):
    """v1.2 is a red-flag/modality revision. If sentiment or guidance
    wording drifted, the re-label would no longer be a single-axis
    experiment on the red-flag block — it would silently perturb the two
    categories that PASSED the agreement bar."""
    assert _block(B.SYSTEM_PROMPT, header) == _block(v11_prompt, header)


def test_distress_tier_category_definitions_are_byte_identical_to_v11(v11_prompt):
    """§5's category definitions are unchanged; only the shared §6 modality
    vocabulary moved. distress_tier is never a training target or headline
    metric (HANDOFF §7) either way."""
    assert _block(B.SYSTEM_PROMPT, "DISTRESS TIER (when asked") == _block(
        v11_prompt, "DISTRESS TIER (when asked"
    )


def test_red_flag_and_modality_blocks_did_change(v11_prompt):
    """The other half of the sync check: the blocks v1.2 targets must
    actually differ. A no-op edit here would mean paying for E1's labels
    twice."""
    for header in ["RED FLAGS (when asked", "MODALITY (required"]:
        assert _block(B.SYSTEM_PROMPT, header) != _block(v11_prompt, header), header


def test_six_red_flag_categories_and_their_names_are_unchanged(v11_prompt):
    """v1.2 changes how categories are applied, never the taxonomy."""
    cats = ["DEMAND_WEAKNESS", "SUPPLY_INPUT_CONSTRAINT", "TRADE_POLICY_EXPOSURE",
            "IMPAIRMENT_WRITEDOWN", "MARGIN_COST_PRESSURE", "LEGAL_REGULATORY_ACTION"]
    for c in cats:
        assert f"- {c}:" in B.SYSTEM_PROMPT and f"- {c}:" in v11_prompt
    assert B.build_json_schema("MDA")["properties"]["red_flags"]["items"][
        "properties"]["category"]["enum"] == cats


def test_prompt_never_names_a_section_type(v11_prompt):
    """labeling_rubric.md §8.2, owner-ratified 2026-08-10 and stricter than
    v1: section_type enters only as schema shape, never as prompt text."""
    for st in ("MDA", "RISK_FACTORS", "EX99_PRESS_RELEASE", "8K_BODY"):
        assert not re.search(rf"\b{re.escape(st)}\b", B.SYSTEM_PROMPT), st


def test_prompt_keeps_the_look_ahead_prohibition():
    """§0 of the rubric is the one rule that overrides everything, and it
    must survive every revision verbatim in substance."""
    p = B.SYSTEM_PROMPT
    assert "THE ONE RULE THAT OVERRIDES EVERYTHING ELSE" in p
    assert "You are not told which company, ticker, or date this passage is from" in p
    assert "what happened to any company's stock price or business afterward" in p


def test_system_prompt_still_clears_the_cache_minimum():
    """The 1h-TTL prompt cache needs a >=1024-token prefix; v1.2 is longer
    than v1.1, so this can only have improved, but pin it."""
    assert B.count_tokens(B.SYSTEM_PROMPT) >= 1024


# =====================================================================
# 2. The request build
# =====================================================================
def test_v12_variant_config_is_identical_to_e1s_final_variant():
    """SINGLE-AXIS DISCIPLINE. Only the rubric changes; the config must be
    byte-for-byte E1's final pass config."""
    v12 = dict(B.VARIANTS["v12_relabel"])
    e1 = dict(B.VARIANTS["disabled-4000"])
    v12.pop("output_path"), e1.pop("output_path")
    assert v12 == e1 == {"max_tokens": 4000, "thinking": {"type": "disabled"}, "effort": None}
    assert B.MODEL == "claude-sonnet-5"


def test_v12_variant_writes_only_to_new_paths():
    """E1's artifacts are frozen (HANDOFF §3, 2026-08-26). Every path the
    v1.2 campaign can write must be new."""
    paths = set(S.VARIANT_PATHS["v12_relabel"].values())
    paths.add(B.VARIANTS["v12_relabel"]["output_path"])
    paths.discard(S.VARIANT_PATHS["v12_relabel"]["requests_file"])  # checked below
    assert not (paths & FROZEN_PATHS), f"frozen path in v12 outputs: {paths & FROZEN_PATHS}"
    assert S.VARIANT_PATHS["v12_relabel"]["canary_labels"] == "data/labels_v12.parquet"
    assert S.VARIANT_PATHS["v12_relabel"]["requests_file"] not in FROZEN_PATHS
    # run_full's default meta path is E1's; the variant must override it.
    assert S.VARIANT_PATHS["v12_relabel"]["full_meta"] != "data/full_batch_meta.json"


def test_write_requests_jsonl_refuses_to_clobber(tmp_path):
    """Every request file on disk is the audit trail of what was really
    submitted under whatever rubric was current then."""
    p = tmp_path / "x.jsonl"
    B.write_requests_jsonl([{"custom_id": "a", "params": {}}], path=str(p))
    with pytest.raises(FileExistsError, match="audit trail"):
        B.write_requests_jsonl([{"custom_id": "a", "params": {}}], path=str(p))
    B.write_requests_jsonl([{"custom_id": "b", "params": {}}], path=str(p), overwrite=True)


def test_build_variant_files_rejects_unknown_variant():
    with pytest.raises(KeyError, match="Unknown variant"):
        B.build_variant_files(corpus_df=None, only=["nope"])


def test_rubric_guard_rejects_the_v11_request_file():
    """The guard that matters most: a stale, v1.1 request file passes the
    max_tokens/thinking variant guard (identical config!) and would buy
    E1's labels a second time. The rubric guard must stop it."""
    if not E1_FINAL_REQUESTS.exists():
        pytest.skip("E1 request file not present")
    reqs = [_first_request(E1_FINAL_REQUESTS)]
    # ...passes the variant guard...
    S.assert_requests_match_variant(reqs, "v12_relabel", str(E1_FINAL_REQUESTS))
    # ...and is caught by the rubric guard.
    with pytest.raises(S.VariantMismatchError, match="rubric/model mismatch"):
        S.assert_requests_use_current_system_prompt(reqs, str(E1_FINAL_REQUESTS))


def test_rubric_guard_rejects_a_wrong_model_id():
    req = {"custom_id": "c0", "params": {
        "model": "claude-sonnet-4-5",
        "system": [{"type": "text", "text": B.SYSTEM_PROMPT}],
    }}
    with pytest.raises(S.VariantMismatchError, match="name a model other than"):
        S.assert_requests_use_current_system_prompt([req], "fake.jsonl")


def test_rubric_guard_rejects_a_request_with_no_system_prompt():
    req = {"custom_id": "c0", "params": {"model": B.MODEL}}
    with pytest.raises(S.VariantMismatchError, match="rubric/model mismatch"):
        S.assert_requests_use_current_system_prompt([req], "fake.jsonl")


def test_rubric_guard_accepts_a_current_request():
    req = {"custom_id": "c0", "params": {
        "model": B.MODEL,
        "system": [{"type": "text", "text": B.SYSTEM_PROMPT}],
    }}
    S.assert_requests_use_current_system_prompt([req], "fake.jsonl")


def test_system_prompt_sha256_is_stable_and_matches_the_built_file():
    assert B.system_prompt_sha256() == hashlib.sha256(
        B.SYSTEM_PROMPT.encode("utf-8")
    ).hexdigest()
    if not V12_REQUESTS.exists():
        pytest.skip("v1.2 request file not built in this checkout")
    on_disk = _system_text(_first_request(V12_REQUESTS))
    assert hashlib.sha256(on_disk.encode("utf-8")).hexdigest() == B.system_prompt_sha256()


def test_built_v12_file_passes_both_guards():
    if not V12_REQUESTS.exists():
        pytest.skip("v1.2 request file not built in this checkout")
    reqs = list(S.load_requests_by_custom_id(path=str(V12_REQUESTS)).values())
    assert len(reqs) == 6747
    S.assert_requests_match_variant(reqs, "v12_relabel", str(V12_REQUESTS))
    S.assert_requests_use_current_system_prompt(reqs, str(V12_REQUESTS))


def test_built_v12_file_covers_every_corpus_chunk_including_the_refusal():
    if not V12_REQUESTS.exists():
        pytest.skip("v1.2 request file not built in this checkout")
    import pandas as pd

    corpus = pd.read_parquet(REPO / "data" / "labeling_corpus.parquet")
    ids = set(S.load_requests_by_custom_id(path=str(V12_REQUESTS)))
    assert ids == set(corpus["chunk_id"])
    # E1 submitted its one safety-refusal chunk and excluded it downstream
    # by predicate. Pre-filtering it here would assume the v1.2 outcome
    # instead of measuring it.
    assert "CHK-8e69547e0900a8dd" in ids


def test_run_full_applies_the_rubric_guard_for_pinned_variants(tmp_path, monkeypatch):
    """End-to-end wiring, offline: run_full must reject a config-correct
    but rubric-stale file for a pinned variant, and must submit nothing."""
    stale = tmp_path / "stale_v11.jsonl"
    with open(stale, "w") as f:
        f.write(json.dumps({"custom_id": "c0", "params": {
            "model": B.MODEL, "max_tokens": 4000,
            "thinking": {"type": "disabled"},
            "system": [{"type": "text", "text": "an older rubric"}],
            "messages": [{"role": "user", "content": "x"}],
            "output_config": {"format": {}},
        }}) + "\n")

    class _Batches:
        def __init__(self): self.calls = []
        def create(self, **kw): self.calls.append(kw); raise AssertionError("submitted!")

    class _Client:
        def __init__(self): self.messages = type("M", (), {"batches": _Batches()})()

    client = _Client()
    monkeypatch.setattr(S, "get_client", lambda: client)
    with pytest.raises(S.VariantMismatchError, match="rubric/model mismatch"):
        S.run_full(variant="v12_relabel", requests_file=str(stale),
                   meta_path=str(tmp_path / "meta.json"))
    assert client.messages.batches.calls == []
    assert not (tmp_path / "meta.json").exists()


def test_run_full_stamps_rubric_provenance_into_the_meta(tmp_path, monkeypatch):
    good = tmp_path / "good.jsonl"
    with open(good, "w") as f:
        f.write(json.dumps({"custom_id": "c0", "params": {
            "model": B.MODEL, "max_tokens": 4000,
            "thinking": {"type": "disabled"},
            "system": [{"type": "text", "text": B.SYSTEM_PROMPT}],
            "messages": [{"role": "user", "content": "x"}],
            "output_config": {"format": {}},
        }}) + "\n")

    class _Batch:
        id = "msgbatch_FAKE"; processing_status = "in_progress"

    class _Batches:
        def create(self, **kw): return _Batch()

    class _Client:
        def __init__(self): self.messages = type("M", (), {"batches": _Batches()})()

    monkeypatch.setattr(S, "get_client", lambda: _Client())
    meta_path = tmp_path / "v12_meta.json"
    S.run_full(variant="v12_relabel", requests_file=str(good), meta_path=str(meta_path))
    meta = json.loads(meta_path.read_text())
    assert meta["variant"] == "v12_relabel"
    assert meta["rubric_version"] == "v1.2"
    assert meta["system_prompt_sha256"] == B.system_prompt_sha256()
    assert meta["asserted_max_tokens"] == 4000
    assert meta["asserted_thinking"] == "disabled"
    assert meta["model"] == "claude-sonnet-5"


def test_full_cli_routes_v12_away_from_e1s_frozen_meta(monkeypatch):
    """--full --variant v12_relabel must not write data/full_batch_meta.json
    (E1's provenance record). Checks main()'s routing without submitting."""
    seen = {}
    monkeypatch.setattr(S, "run_full", lambda **kw: seen.update(kw))
    monkeypatch.setattr(
        "sys.argv",
        ["submit_labeling_batch.py", "--full", "--confirm-full", "--variant", "v12_relabel"],
    )
    S.main()
    assert seen["variant"] == "v12_relabel"
    assert seen["requests_file"] == "data/batch_requests_v12.jsonl"
    assert seen["meta_path"] == "data/v12_relabel_batch_meta.json"
    assert seen["meta_path"] != "data/full_batch_meta.json"


def test_legacy_variants_are_not_rubric_pinned():
    """Historical variants keep their v1.1 files and stay submittable-shaped
    for the tests that exercise them; only v12_relabel is pinned."""
    assert S.RUBRIC_PINNED_VARIANTS == {"v12_relabel"}
