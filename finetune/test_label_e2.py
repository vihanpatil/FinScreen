#!/usr/bin/env python3
"""Offline tests for label_e2.py — no model, no GPU, no network, $0.

    python3 -m pytest finetune/test_label_e2.py -q

The tokenizer-dependent half (the rendering contract and the fixed-reserve head
truncation against real text) lives in `test_label_e2_prompt.py`, which runs
under `finetune/.mlx_venv/bin/python` — the same split `test_eval_real.py` uses,
because .mlx_venv has transformers but neither pytest nor pyarrow:

    finetune/.mlx_venv/bin/python finetune/test_label_e2_prompt.py

Every real artifact is opened READ-ONLY. Nothing writes outside tmp_path — in
particular data/labels_v12.parquet is only ever read for its arrow schema.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
for p in (str(HERE), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)

import eval as ev
import relabel_e1 as r1
import label_e2 as L

try:
    import pyarrow  # noqa: F401
    HAVE_ARROW = True
except ImportError:
    HAVE_ARROW = False

needs_arrow = pytest.mark.skipif(not HAVE_ARROW, reason="pyarrow lives in the system python")

def _rec(raw, **kw):
    base = {
        "chunk_id": "E2CHK-test", "segment_id": "seg-001", "raw_output": raw,
        "prompt_input_sha256": "in", "prompt_sha256": "abc", "prompt_tokens": 1000,
        "generation_tokens": 30, "finish_reason": "stop", "latency_s": 2.4,
        "passage_was_head_truncated": False, "passage_chars_kept": 1234,
        "generated_utc": "2026-08-28T00:00:00+00:00",
    }
    base.update(kw)
    return base


# ===========================================================================
# THE WRITER — missing->NONE with its audit flag (the owner's F4 ruling)
# ===========================================================================

OMITS_GUIDANCE = '{"sentiment": "NEUTRAL", "red_flags": []}'
EXPLICIT_NONE = '{"sentiment": "NEUTRAL", "guidance_direction": "NONE", "red_flags": []}'
RAISED = '{"sentiment": "POSITIVE", "guidance_direction": "RAISED", "red_flags": []}'
BAD_ENUM = '{"sentiment": "NEUTRAL", "guidance_direction": "SIDEWAYS", "red_flags": []}'


def test_missing_guidance_becomes_none_on_an_applicable_passage():
    row = L.f4_label_row(_rec(OMITS_GUIDANCE), guidance_applicable=True)
    assert row["guidance_direction"] == "NONE"
    assert row["guidance_imputed_none"] is True
    assert row["guidance_applicable"] is True


def test_missing_guidance_is_left_null_on_a_NON_applicable_passage():
    """MDA / RISK_FACTORS were never asked for guidance, so an omission there
    is the model behaving correctly — imputing NONE would invent a label."""
    row = L.f4_label_row(_rec(OMITS_GUIDANCE), guidance_applicable=False)
    assert row["guidance_direction"] is None
    assert row["guidance_imputed_none"] is False


def test_an_explicitly_emitted_none_is_not_flagged_as_imputed():
    row = L.f4_label_row(_rec(EXPLICIT_NONE), guidance_applicable=True)
    assert row["guidance_direction"] == "NONE"
    assert row["guidance_imputed_none"] is False


def test_a_real_value_is_untouched():
    row = L.f4_label_row(_rec(RAISED), guidance_applicable=True)
    assert row["guidance_direction"] == "RAISED"
    assert row["guidance_imputed_none"] is False


def test_an_out_of_taxonomy_value_is_NOT_imputed():
    """The rule rewrites the omitted-key case only (eval report A.1). An
    invalid enum stays an error, with its schema issue recorded."""
    row = L.f4_label_row(_rec(BAD_ENUM), guidance_applicable=True)
    assert row["guidance_direction"] is None
    assert row["guidance_imputed_none"] is False
    assert "bad_enum:guidance_direction" in row["schema_issues"]


def test_a_parse_failure_is_kept_and_never_imputed():
    row = L.f4_label_row(_rec("not json"), guidance_applicable=True)
    assert row["parse_ok"] is False
    assert row["guidance_direction"] is None
    assert row["guidance_imputed_none"] is False
    assert row["raw_label_json"] == "not json"
    assert row["parse_error"]


def test_the_rule_touches_nothing_but_guidance():
    raw = ('{"sentiment": "NEGATIVE", "red_flags": ['
           '{"category": "DEMAND_WEAKNESS", "modality": "REALIZED"}]}')
    base = r1.student_label_row(_rec(raw))
    row = L.f4_label_row(_rec(raw), guidance_applicable=True)
    for k in ("sentiment", "red_flags", "parse_ok", "schema_valid", "raw_label_json",
              "distress_tier", "stop_reason", "output_tokens"):
        assert row[k] == base[k], k


def test_distress_tier_is_never_emitted_and_out_of_taxonomy_flags_are_dropped():
    raw = ('{"sentiment": "NEUTRAL", "distress_tier": [{"category": "GOING_CONCERN", '
           '"modality": "REALIZED"}], "red_flags": [{"category": "INVENTED", '
           '"modality": "REALIZED"}, {"category": "DEMAND_WEAKNESS", "modality": "X"}]}')
    row = L.f4_label_row(_rec(raw), guidance_applicable=False)
    assert row["distress_tier"] == []
    assert row["red_flags"] == []
    assert any("red_flag" in i for i in row["schema_issues"])


def test_the_run_id_and_telemetry_land_on_the_row():
    row = L.f4_label_row(_rec(RAISED, segment_id="seg-007",
                              passage_was_head_truncated=True, passage_chars_kept=99),
                         guidance_applicable=True, run_id="F4-e2-label-v1")
    assert row["batch_id"] == "F4-e2-label-v1"
    assert row["api_result_type"] == "student_local_mlx"
    assert row["segment_id"] == "seg-007"
    assert row["passage_was_head_truncated"] is True
    assert row["passage_chars_kept"] == 99


# ===========================================================================
# SEGMENTATION
# ===========================================================================

def test_segment_bounds_cover_every_row_exactly_once():
    accs = [f"a{i // 7}" for i in range(1000)]
    bounds = L.segment_bounds(accs, 100)
    assert bounds[0][0] == 0 and bounds[-1][1] == 1000
    for (a, b), (c, d) in zip(bounds, bounds[1:]):
        assert b == c
    assert sum(b - a for a, b in bounds) == 1000


def test_segment_bounds_never_split_a_filing():
    accs = [f"a{i // 37}" for i in range(1000)]
    for start, end in L.segment_bounds(accs, 100):
        if start > 0:
            assert accs[start] != accs[start - 1]


def test_segment_bounds_are_balanced_and_do_not_leave_a_runt():
    accs = [f"a{i}" for i in range(317081)]
    bounds = L.segment_bounds(accs, 13500)
    sizes = [b - a for a, b in bounds]
    assert len(bounds) == 24
    assert sum(sizes) == 317081
    assert max(sizes) - min(sizes) < 13500          # no runt final night
    assert min(sizes) > 13500 * 0.9


def test_one_segment_when_the_corpus_is_smaller_than_one_night():
    assert L.segment_bounds([f"a{i}" for i in range(10)], 13500) == [(0, 10)]


# ===========================================================================
# RESUME semantics
# ===========================================================================

def test_resume_skips_finished_rows():
    rows = [{"chunk_id": "a", "passage": "p1"}, {"chunk_id": "b", "passage": "p2"}]
    existing = {"a": {"prompt_input_sha256": L.prompt_input_sha("i", "p1")}}
    todo = L.select_rows_to_generate(rows, existing, "j.jsonl", "i")
    assert [r["chunk_id"] for r in todo] == ["b"]
    assert todo[0]["_prompt_input_sha256"] == L.prompt_input_sha("i", "p2")


def test_resume_hard_stops_when_the_passage_changed_underneath():
    rows = [{"chunk_id": "a", "passage": "NEW TEXT"}]
    existing = {"a": {"prompt_input_sha256": L.prompt_input_sha("i", "old text")}}
    with pytest.raises(SystemExit) as e:
        L.select_rows_to_generate(rows, existing, "j.jsonl", "i")
    assert "DIFFERENT prompt" in str(e.value)


def test_resume_hard_stops_when_the_instruction_changed_underneath():
    rows = [{"chunk_id": "a", "passage": "p"}]
    existing = {"a": {"prompt_input_sha256": L.prompt_input_sha("instr-A", "p")}}
    with pytest.raises(SystemExit):
        L.select_rows_to_generate(rows, existing, "j.jsonl", "instr-B")


def test_a_torn_final_line_is_repaired_before_appending(tmp_path):
    """Carried over from H3's resume smoke: appending onto a half-written record
    glues the next row to the fragment and silently loses one GOOD row per kill.
    label_e2 uses relabel_e1's repair verbatim."""
    j = tmp_path / "labels.jsonl"
    j.write_text(json.dumps({"chunk_id": "a", "raw_output": "{}"}) + "\n"
                 + '{"chunk_id": "b", "raw_out')          # torn, no newline
    assert r1.ensure_trailing_newline(j) is True
    with open(j, "a") as f:
        ev.append_prediction(f, {"chunk_id": "c", "raw_output": "{}"})
    recs = ev.load_predictions(j)
    assert set(recs) == {"a", "c"}                        # 'b' is the torn fragment
    assert r1.ensure_trailing_newline(j) is False          # idempotent


# ===========================================================================
# PROMPT — reserve, truncation, and the rendering contract
# ===========================================================================

class _StubTokenizer:
    """A tokenizer whose tokens are whitespace-delimited words, with a chat
    template shaped like Qwen's. Enough to exercise the truncation arithmetic
    without a 400 MB download."""

    HEAD = ["<sys>"]
    MID = ["<user>"]
    GEN = ["<assistant>"]

    def apply_chat_template(self, messages, tools=None, add_generation_prompt=False,
                            return_dict=False):
        out = list(self.HEAD) + messages[0]["content"].split() + list(self.MID) \
            + messages[1]["content"].split()
        if add_generation_prompt:
            return out + list(self.GEN)
        return out + list(self.GEN) + (messages[2]["content"].split() if len(messages) > 2 else [])

    def encode(self, text, add_special_tokens=False):
        return text.split()

    def decode(self, ids):
        return " ".join(ids)


def test_fit_prompt_is_a_noop_when_the_passage_already_fits():
    tok = _StubTokenizer()
    passage = " ".join(f"w{i}" for i in range(50))
    kept, ids, truncated, ok = L.fit_prompt(tok, "instr", passage,
                                            max_seq_len=200, reserve=20)
    assert kept == passage and truncated is False and ok is True
    assert len(ids) <= 180


def test_fit_prompt_head_truncates_to_the_budget_and_flags_it():
    tok = _StubTokenizer()
    passage = " ".join(f"w{i}" for i in range(500))
    kept, ids, truncated, ok = L.fit_prompt(tok, "instr", passage,
                                            max_seq_len=200, reserve=64)
    assert truncated is True
    assert len(ids) <= 200 - 64
    assert ok is True
    assert passage.startswith(kept)                 # only the TAIL is ever dropped
    assert len(kept) < len(passage)


def test_a_bigger_reserve_keeps_less_passage():
    tok = _StubTokenizer()
    passage = " ".join(f"w{i}" for i in range(500))
    small, _, _, _ = L.fit_prompt(tok, "instr", passage, max_seq_len=300, reserve=32)
    big, _, _, _ = L.fit_prompt(tok, "instr", passage, max_seq_len=300, reserve=128)
    assert len(big.split()) < len(small.split())


def test_fit_prompt_refuses_a_reserve_that_leaves_no_room_for_the_instruction():
    tok = _StubTokenizer()
    with pytest.raises(SystemExit):
        L.fit_prompt(tok, " ".join(["i"] * 100), "some passage",
                     max_seq_len=100, reserve=90)


def test_the_reserve_clears_every_generation_length_ever_measured():
    """256 vs the measured maxima: v1.2 epoch-2 eval max 151 generated tokens,
    H3v2's 6,746-row relabel max 151, and the v1.2 training targets' own
    loss-bearing region max 152."""
    assert L.ANSWER_TOKEN_RESERVE >= 160
    assert L.ANSWER_TOKEN_RESERVE / 152 >= 1.5
    assert L.MAX_SEQ_LEN - L.ANSWER_TOKEN_RESERVE == 1792
    assert L.MAX_TOKENS == 520                       # generation is NOT capped at the reserve


# ===========================================================================
# OUTPUT SCHEMA
# ===========================================================================

@needs_arrow
def test_output_schema_is_the_v12_teacher_schema_plus_nine_f4_columns():
    schema, n_teacher, widened = L.output_schema()
    assert n_teacher == 34
    assert len(schema) == 43
    assert [f.name for f in schema][:34] == [
        f.name for f in __import__("pyarrow.parquet", fromlist=["x"]).read_schema(
            L.LABELS_V12).remove_metadata()]
    assert widened == ["parse_error"]                # null-typed in the teacher file
    for name, _ in L.STUDENT_ONLY_FIELDS:
        assert name in schema.names


@needs_arrow
def test_the_schema_metadata_carries_the_red_flag_demotion_and_the_labeler():
    schema, _, _ = L.output_schema()
    md = {k.decode(): v.decode() for k, v in schema.metadata.items()}
    assert "EXPLORATORY" in md["f4_red_flags_status"]
    assert "42.00%" in md["f4_red_flags_status"]
    assert L.ADAPTER_SHA256 in md["f4_labeler"]
    assert "STUDENT labels" in md["f4_teacher"]
    assert "guidance_imputed_none" in md["f4_guidance_rule"]


@needs_arrow
def test_a_parse_failure_round_trips_through_the_widened_parse_error(tmp_path):
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
    schema, _, _ = L.output_schema()
    row = L.f4_label_row(_rec("not json"), guidance_applicable=True)
    row.update({"chunk_id": "E2CHK-x", "section_type": "MDA", "text": "t", "word_count": 1,
                "n_paragraphs": 1, "paragraph_ids": ["E2P-a"], "home_ticker": None,
                "home_cik": 1, "home_accession_number": "a", "home_form": "10-K",
                "home_filing_date": "2020-01-01", "source_tickers": [],
                "source_accession_numbers": ["a"], "source_filing_dates": ["2020-01-01"],
                "source_forms": ["10-K"], "n_source_filings": 1, "max_tokens_used": 520,
                "labeling_config": "x", "rubric_version": "v1.2",
                "system_prompt_sha256": L.INSTRUCTION_SHA256, "completion_batch_id": None})
    df = pd.DataFrame([row])
    tbl = pa.Table.from_pandas(df[[f.name for f in schema]], schema=schema,
                               preserve_index=False)
    out = tmp_path / "x.parquet"
    pq.write_table(tbl, out)
    back = pd.read_parquet(out)
    assert back.parse_ok.iloc[0] is False or not back.parse_ok.iloc[0]
    assert isinstance(back.parse_error.iloc[0], str) and back.parse_error.iloc[0]
    assert back.guidance_imputed_none.iloc[0] == False  # noqa: E712


# ===========================================================================
# PREFLIGHT GUARDS
# ===========================================================================

@needs_arrow
def test_plan_hard_fails_if_the_chunk_table_sha_moved(tmp_path, monkeypatch):
    fake = tmp_path / "chunks.parquet"
    fake.write_bytes(b"not the chunk table")
    monkeypatch.setattr(L, "CHUNKS_PARQUET", fake)
    with pytest.raises(SystemExit) as e:
        L.build_plan(out_path=tmp_path / "plan.json")
    assert "CHUNK TABLE MISMATCH" in str(e.value)


@needs_arrow
def test_plan_hard_fails_if_the_chunk_table_was_built_from_another_corpus(tmp_path, monkeypatch):
    if not L.CHUNKS_PARQUET.exists():
        pytest.skip("chunks_v1.parquet has not been built on this machine")
    bad = tmp_path / "m.json"
    man = json.loads(L.CHUNKS_MANIFEST.read_text())
    man["corpus"]["sha256"] = "0" * 64
    bad.write_text(json.dumps(man))
    monkeypatch.setattr(L, "CHUNKS_MANIFEST", bad)
    with pytest.raises(SystemExit) as e:
        L.build_plan(out_path=tmp_path / "plan.json")
    assert "pinned P5 corpus" in str(e.value)


def test_the_pinned_provenance_constants_are_the_ruled_ones():
    assert L.INSTRUCTION_SHA256 == (
        "ebc45a856bff58a562535867e5a1f4173519fe77c58a47b16bfa28e6eea8efe2")
    assert L.ADAPTER_SHA256 == (
        "cadca8499b66b2e7d60a161f2021a5c5dac51ddd3a0bccea52d055cefb159de3")
    assert L.CORPUS_SHA256 == (
        "15853e9f54902a933f0372869209a353ab3f052cb5c7dc1f897297f75b53f417")
    assert L.RUN_ID == "F4-e2-label-v1" and L.RUBRIC_VERSION == "v1.2"


def test_the_instruction_on_disk_is_the_frozen_one():
    if not (L.MLX_DATA_DIR / "train.jsonl").exists():
        pytest.skip("mlx_data_v12 is not on this machine")
    assert ev.sha256_text(L.read_instruction()) == L.INSTRUCTION_SHA256


def test_the_adapter_the_reference_eval_ran_is_the_one_we_pin():
    m = L.REFERENCE_EVAL_DIR / "manifest.json"
    if not m.exists():
        pytest.skip("the v1.2 epoch-2 eval is not on this machine")
    man = json.loads(m.read_text())
    assert man["adapter"]["adapters_sha256"] == L.ADAPTER_SHA256
    assert man["data"]["instruction_sha256"] == L.INSTRUCTION_SHA256


@needs_arrow
def test_load_rows_hard_fails_when_the_chunk_id_list_moved(tmp_path):
    spec = {"segment_id": "seg-001", "n_rows": 2, "chunk_id_list_sha256": "0" * 64}
    (tmp_path / L.ROWS_NAME).write_text(
        json.dumps({"chunk_id": "a", "passage": "p", "section_type": "MDA",
                    "guidance_applicable": False}) + "\n"
        + json.dumps({"chunk_id": "b", "passage": "q", "section_type": "MDA",
                      "guidance_applicable": False}) + "\n")
    with pytest.raises(SystemExit) as e:
        L.load_rows(tmp_path, spec)
    assert "chunk_id list sha" in str(e.value)


# ===========================================================================
# END-TO-END, OFFLINE: prepare -> synthetic journal -> finalize
# ===========================================================================

@pytest.fixture(scope="module")
def finalized(tmp_path_factory):
    if not HAVE_ARROW:
        pytest.skip("pyarrow lives in the system python")
    if not (L.CHUNKS_PARQUET.exists() and L.PLAN_PATH.exists()):
        pytest.skip("the F4 chunk table / plan have not been built on this machine")
    import types
    plan = L.load_plan()
    spec = L.segment_spec(plan, "1")
    out = tmp_path_factory.mktemp("seg")
    L.prepare_segment(plan, spec, out)
    rows = L.load_rows(out, spec, limit=40)
    outputs = [RAISED, OMITS_GUIDANCE, EXPLICIT_NONE, "not json", BAD_ENUM]
    with open(out / L.JOURNAL_NAME, "w") as f:
        for i, r in enumerate(rows):
            f.write(json.dumps(_rec(outputs[i % len(outputs)], chunk_id=r["chunk_id"],
                                    passage_was_head_truncated=(i == 3))) + "\n")
    args = types.SimpleNamespace(max_tokens=520, answer_token_reserve=256,
                                 max_seq_length=2048, run_id=L.RUN_ID)
    info = L.build_segment_parquet(out / L.JOURNAL_NAME,
                                   out / "labels_seg-001.parquet", spec, rows, args)
    import pandas as pd
    return info, pd.read_parquet(out / "labels_seg-001.parquet"), rows


@needs_arrow
def test_end_to_end_parquet_has_the_expected_shape(finalized):
    info, df, rows = finalized
    assert info["n_rows"] == len(df) == 40
    assert info["n_columns"] == 43
    assert info["parse_failures"] == 8              # every 5th synthetic row
    assert set(df.batch_id) == {L.RUN_ID}
    assert set(df.rubric_version) == {"v1.2"}
    assert set(df.system_prompt_sha256) == {L.INSTRUCTION_SHA256}
    assert all(len(x) == 0 for x in df.distress_tier)
    assert df.home_ticker.isna().all()
    assert all(len(x) == 0 for x in df.source_tickers)
    assert "answer_token_reserve=256" in df.labeling_config.iloc[0]
    assert "guidance_missing_to_none=writer" in df.labeling_config.iloc[0]


@needs_arrow
def test_end_to_end_imputation_is_scoped_to_applicable_rows(finalized):
    info, df, rows = finalized
    imputed = df[df.guidance_imputed_none]
    assert len(imputed) == info["guidance"]["n_imputed_none"] > 0
    assert imputed.guidance_applicable.all()
    assert (imputed.guidance_direction == "NONE").all()
    assert set(imputed.section_type) <= set(__import__("build_f4_chunks")
                                            .GUIDANCE_APPLICABLE_SECTION_TYPES)
    # non-applicable rows that omitted guidance stay NULL
    non = df[(~df.guidance_applicable) & df.raw_label_json.eq(OMITS_GUIDANCE)]
    assert non.guidance_direction.isna().all()
    assert not non.guidance_imputed_none.any()


@needs_arrow
def test_end_to_end_manifest_block_reports_the_rule_honestly(finalized):
    info, df, rows = finalized
    g = info["guidance"]
    assert g["n_imputed_none"] + g["n_explicitly_emitted"] <= len(df)
    assert g["rule"].startswith("missing->NONE at the writer")
    assert info["red_flags_status"].startswith("EXPLORATORY")
    assert info["head_truncation"]["answer_token_reserve"] == 256
    assert info["head_truncation"]["prompt_token_budget"] == 1792
    assert info["distress_tier"].startswith("uniformly empty")


@needs_arrow
def test_prepare_segment_writes_stdlib_readable_rows(finalized):
    info, df, rows = finalized
    assert {"chunk_id", "section_type", "guidance_applicable", "passage"} == set(rows[0])
    assert isinstance(rows[0]["passage"], str) and rows[0]["passage"]


# ===========================================================================
# CAMPAIGN
# ===========================================================================

@needs_arrow
def test_campaign_finalize_concatenates_finished_segments(tmp_path, finalized):
    """Two finalized segments -> one campaign parquet, COMPLETE, with the
    per-night provenance accumulated."""
    import shutil
    import pyarrow.parquet as pq
    info, df, _ = finalized
    src = Path(info["path"])
    segments = []
    for i in (1, 2):
        d = tmp_path / f"seg-{i:03d}"
        d.mkdir()
        shutil.copy(src, d / f"labels_seg-{i:03d}.parquet")
        (d / L.MANIFEST_NAME).write_text(json.dumps({
            "journal": {"sha256": f"j{i}"},
            "parquet": {"n_rows": info["n_rows"], "sha256": info["sha256"],
                        "parse_failures": info["parse_failures"],
                        "schema_violations": info["schema_violations"],
                        "guidance": info["guidance"],
                        "head_truncation": info["head_truncation"]},
            "segments": [{"wall_seconds": 3600.0}],
            "totals": {"chunks_per_hour_excluding_load_and_gaps": 1400.0},
            "finalized_utc": "2026-08-28T00:00:00+00:00",
        }))
        segments.append({"segment_id": f"seg-{i:03d}", "dir": str(d)})
    plan = {"run_id": L.RUN_ID, "segments": segments, "generation": {},
            "owner_rulings": {},
            "inputs": {"chunks_parquet": {"n_rows": 2 * info["n_rows"]}}}
    man = L.finalize_campaign(plan, tmp_path / "all.parquet", tmp_path / "all.json")
    assert man["COMPLETE"] is True and not man["segments_missing"]
    assert man["n_rows_written"] == 2 * info["n_rows"]
    assert pq.ParquetFile(tmp_path / "all.parquet").metadata.num_rows == 2 * info["n_rows"]
    assert len(man["per_segment"]) == 2
    assert man["totals"]["parse_failures"] == 2 * info["parse_failures"]
    assert man["throughput"]["chunks_per_hour_overall"] is not None
    assert man["cost_usd"] == 0.0 and man["anthropic_api_calls"] == 0
    assert "EXPLORATORY" in man["caveats"][0]


@needs_arrow
def test_campaign_finalize_reports_missing_segments_rather_than_looking_complete(tmp_path):
    plan = {"run_id": L.RUN_ID, "segments": [
        {"segment_id": "seg-001", "dir": str(tmp_path / "a")},
        {"segment_id": "seg-002", "dir": str(tmp_path / "b")},
    ], "inputs": {"chunks_parquet": {"n_rows": 100}}, "generation": {},
        "owner_rulings": {}}
    man = L.finalize_campaign(plan, tmp_path / "c.parquet", tmp_path / "c.json")
    assert man["COMPLETE"] is False
    assert man["segments_missing"] == ["seg-001", "seg-002"]
    assert man["n_rows_written"] == 0
    assert man["cost_usd"] == 0.0 and man["anthropic_api_calls"] == 0


@needs_arrow
def test_the_plan_on_disk_covers_every_chunk_exactly_once():
    if not L.PLAN_PATH.exists():
        pytest.skip("the F4 plan has not been built on this machine")
    plan = L.load_plan()
    segs = plan["segments"]
    assert segs[0]["row_start"] == 0
    assert segs[-1]["row_end"] == plan["inputs"]["chunks_parquet"]["n_rows"]
    for a, b in zip(segs, segs[1:]):
        assert a["row_end"] == b["row_start"]
    assert sum(s["n_rows"] for s in segs) == plan["inputs"]["chunks_parquet"]["n_rows"]


@needs_arrow
def test_every_planned_night_carries_a_full_section_type_mix():
    """Chronological ordering exists so that a campaign stopped early is a
    usable TIME PREFIX rather than 'all MD&As and no press releases'."""
    if not L.PLAN_PATH.exists():
        pytest.skip("the F4 plan has not been built on this machine")
    for s in L.load_plan()["segments"]:
        mix = s["by_section_type"]
        assert {"MDA", "RISK_FACTORS", "EX99_PRESS_RELEASE"} <= set(mix)
        assert mix["EX99_PRESS_RELEASE"] / s["n_rows"] > 0.15


def test_the_runner_cannot_call_an_api_or_the_network():
    src = (HERE / "label_e2.py").read_text()
    for forbidden in ("import anthropic", "Anthropic(", "import requests",
                      "import urllib", "import http", "socket"):
        assert forbidden not in src, forbidden
