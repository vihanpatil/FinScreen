#!/usr/bin/env python3
"""test_eval_real.py — offline tests for eval.py's real (--backend mlx) path.

NO MODEL IS LOADED AND NO GPU WORK HAPPENS HERE. The tests cover:

  A. the rendering contract (byte-identical instruction, message roles, the
     inference prompt being a token-exact prefix of the training sequence, and
     no ticker/date/section_type leaking into the prompt),
  B. metric computation on synthetic predictions, including the case where the
     exact-set and per-category red-flag bases diverge sharply,
  C. parse-failure and schema-violation handling,
  D. resume/skip logic,
  E. an end-to-end `--score-only` run that writes a real report from synthetic
     predictions.

Tokenizer-dependent tests (group A) need `transformers` + the local Qwen2.5
snapshot; they SKIP cleanly when those are absent. Tokenizing is CPU work.

Run either way:
    finetune/.mlx_venv/bin/python finetune/test_eval_real.py     # incl. tokenizer tests
    python3 -m pytest finetune/test_eval_real.py -q              # system python
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import eval as ev  # noqa: E402


class Skip(__import__("unittest").SkipTest):
    """Raised to skip a test when an optional dependency is missing.

    Subclasses unittest.SkipTest so pytest reports a skip rather than an error
    when the suite is run under the system python (which has pandas + pytest
    but no transformers)."""


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

_TOKENIZER = None
_TOKENIZER_TRIED = False

MODEL_SNAPSHOT = None


def _model_snapshot() -> str:
    global MODEL_SNAPSHOT
    if MODEL_SNAPSHOT is None:
        man = json.loads(ev.DEFAULT_TRAIN_MANIFEST.read_text())
        MODEL_SNAPSHOT = man["model"]["resolved_snapshot_path"]
    return MODEL_SNAPSHOT


def get_tokenizer():
    """HF tokenizer only. No MLX, no weights, no GPU."""
    global _TOKENIZER, _TOKENIZER_TRIED
    if _TOKENIZER_TRIED:
        if _TOKENIZER is None:
            raise Skip("transformers / local tokenizer snapshot unavailable")
        return _TOKENIZER
    _TOKENIZER_TRIED = True
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    try:
        from transformers import AutoTokenizer

        _TOKENIZER = AutoTokenizer.from_pretrained(_model_snapshot(), local_files_only=True)
    except Exception as e:  # pragma: no cover - environment dependent
        _TOKENIZER = None
        raise Skip(f"tokenizer unavailable: {e}")
    return _TOKENIZER


_ROWS = None


def eval_rows():
    global _ROWS
    if _ROWS is None:
        _ROWS, _ = ev.load_eval_rows(verify_train_instruction=False)
    return _ROWS


def mkrow(chunk_id, gold):
    return {"chunk_id": chunk_id, "gold": gold}


def perfect_pred(gold):
    return json.dumps(gold)


# --------------------------------------------------------------------------
# A. rendering contract
# --------------------------------------------------------------------------

def test_instruction_is_byte_identical_across_eval_and_train():
    rows, prov = ev.load_eval_rows(verify_train_instruction=True)
    assert prov["n_rows"] == 1010, prov["n_rows"]
    assert prov["instruction_byte_identical_across_eval"] is True
    assert prov["instruction_byte_identical_to_train"] is True, (
        "the eval instruction must be byte-identical to every train row's instruction"
    )
    assert len({r["instruction"] for r in rows}) == 1


def test_message_roles_and_to_messages_contract():
    import convert_to_mlx as c2m

    rows = eval_rows()
    for row in rows:
        assert [m["role"] for m in row["messages"]] == ["system", "user", "assistant"]
        assert c2m.to_messages(row["instruction"], row["passage"], row["gold_text"]) == row["messages"], (
            f"{row['chunk_id']}: stored messages do not match convert_to_mlx.to_messages()"
        )
    # system is the instruction, user is the passage and NOTHING else
    r = rows[0]
    assert r["messages"][0]["content"] == r["instruction"]
    assert r["messages"][1]["content"] == r["passage"]


def test_prompt_is_token_exact_prefix_of_training_sequence():
    import convert_to_mlx as c2m

    tok = get_tokenizer()
    rows = eval_rows()
    sample = rows[:5] + rows[500:503] + rows[-5:]
    for row in sample:
        prompt_ids = ev.render_prompt_token_ids(tok, row)
        all_ids, offset = c2m.render(tok, row["messages"])
        assert prompt_ids == list(all_ids[:offset]), (
            f"{row['chunk_id']}: the inference prompt is not a token-exact prefix of the "
            f"training sequence"
        )
        assert len(prompt_ids) < len(all_ids)


def test_prompt_contains_nothing_but_instruction_passage_and_chatml_scaffolding():
    """The strongest form of 'nothing appended or prepended': the decoded
    prompt must equal the ChatML template applied to exactly two messages."""
    tok = get_tokenizer()
    rows = eval_rows()
    for row in rows[:5] + rows[777:780]:
        prompt_ids = ev.render_prompt_token_ids(tok, row)
        decoded = tok.decode(prompt_ids)
        expected = (
            "<|im_start|>system\n" + row["instruction"] + "<|im_end|>\n"
            "<|im_start|>user\n" + row["passage"] + "<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
        assert decoded == expected, (
            f"{row['chunk_id']}: rendered prompt has content beyond instruction + passage + "
            f"ChatML scaffolding"
        )
        # and no part of the answer leaked into the prompt
        assert row["gold_text"] not in decoded


def test_no_section_type_ticker_or_date_leakage_in_the_instruction():
    rows = eval_rows()
    instruction = rows[0]["instruction"]

    for st in ("MDA", "RISK_FACTORS", "EX99_PRESS_RELEASE", "8K_BODY"):
        assert st not in instruction, f"section_type literal {st!r} appears in the instruction"

    # No ticker from the universe is named in the instruction.
    universe = HERE.parent / "data" / "universe.csv"
    if universe.exists():
        import csv

        with open(universe) as f:
            tickers = [r["ticker"].strip() for r in csv.DictReader(f) if r.get("ticker")]
        assert tickers, "universe.csv parsed to zero tickers -- check the column name"
        for t in tickers:
            assert f" {t} " not in f" {instruction} ", f"ticker {t} appears in the instruction"

    # No filing-date-shaped strings, and no outcome framing.
    import re

    assert not re.search(r"\b(19|20)\d{2}-\d{2}-\d{2}\b", instruction)
    assert not re.search(r"\bQ[1-4]\s*(19|20)\d{2}\b", instruction)
    low = instruction.lower()
    for phrase in ("stock went", "share price rose", "outperform", "afterward the stock",
                   "did the stock", "subsequent return"):
        assert phrase not in low
    # it must positively contain the anti-look-ahead instruction
    assert "never what happened to any company's stock price" in low


def test_no_section_type_appears_in_any_rendered_prompt_scaffolding():
    """section_type is used only to bucket results, never as prompt text. The
    sidecar exists; assert the pipeline cannot smuggle it into a prompt."""
    section_types = ev.load_section_types()
    rows = eval_rows()
    assert set(section_types) >= {r["chunk_id"] for r in rows}
    for row in rows[:200]:
        st = section_types[row["chunk_id"]]
        # The passage is verbatim filing text and may coincidentally contain
        # words; what must never happen is the pipeline ADDING the label.
        rendered = row["messages"][0]["content"] + row["messages"][1]["content"]
        assert rendered == row["instruction"] + row["passage"]
        assert st not in row["instruction"]


def test_head_truncated_passages_are_prefixes_and_counted():
    rows, prov = ev.load_eval_rows(verify_train_instruction=False)
    n_trunc = sum(1 for r in rows if r["passage_was_truncated"])
    assert n_trunc == prov["n_passages_head_truncated_to_fit_2048"] == 49, n_trunc


# --------------------------------------------------------------------------
# B. metrics
# --------------------------------------------------------------------------

def test_score_single_label_hand_computed():
    golds = ["POSITIVE", "POSITIVE", "NEUTRAL", "NEGATIVE"]
    preds = ["POSITIVE", "NEUTRAL", "NEUTRAL", "POSITIVE"]
    r = ev.score_single_label(golds, preds, ev.SENTIMENT_LABELS)
    assert r["n"] == 4 and r["n_correct"] == 2 and r["exact_match"] == 0.5
    pos = r["per_class"]["POSITIVE"]
    assert (pos["tp"], pos["fp"], pos["fn"], pos["support"]) == (1, 1, 1, 2)
    assert pos["precision"] == 0.5 and pos["recall"] == 0.5 and pos["f1"] == 0.5
    neu = r["per_class"]["NEUTRAL"]
    assert (neu["tp"], neu["fp"], neu["fn"]) == (1, 1, 0)
    neg = r["per_class"]["NEGATIVE"]
    assert (neg["tp"], neg["fp"], neg["fn"]) == (0, 0, 1)
    assert r["confusion"]["POSITIVE->NEUTRAL"] == 1
    assert r["confusion"]["NEGATIVE->POSITIVE"] == 1


def test_macro_excludes_zero_support_classes_withdrawn_case():
    """WITHDRAWN has zero eval support. Averaging it in would silently drag
    guidance's macro-F1 down by a structural 1/5."""
    golds = ["NONE"] * 8 + ["RAISED", "LOWERED"]
    preds = ["NONE"] * 8 + ["RAISED", "LOWERED"]
    r = ev.score_single_label(golds, preds, ev.GUIDANCE_LABELS)
    assert "WITHDRAWN" in r["zero_support_classes"]
    assert "MAINTAINED" in r["zero_support_classes"]
    assert set(r["macro_over_supported_classes"]["classes"]) == {"NONE", "RAISED", "LOWERED"}
    assert r["macro_over_supported_classes"]["f1"] == 1.0, (
        "a perfect prediction must show macro-F1 1.0, not 0.6 because two classes are absent"
    )
    assert ev.NOT_EVALUABLE_REASONS["WITHDRAWN"]


def test_failure_sentinels_score_as_errors_and_are_attributed():
    golds = ["POSITIVE", "NEUTRAL", "NEGATIVE"]
    preds = [ev.S_UNPARSEABLE, ev.S_MISSING_FIELD, ev.S_INVALID_ENUM]
    r = ev.score_single_label(golds, preds, ev.SENTIMENT_LABELS)
    assert r["n"] == 3 and r["n_correct"] == 0 and r["exact_match"] == 0.0
    assert r["failure_attribution"] == {
        ev.S_UNPARSEABLE: 1, ev.S_MISSING_FIELD: 1, ev.S_INVALID_ENUM: 1,
    }
    for lb in ev.SENTIMENT_LABELS:
        assert r["per_class"][lb]["fn"] == 1
        assert r["per_class"][lb]["fp"] == 0


def test_red_flags_exact_set_and_per_category_diverge():
    """The headline reason both bases are printed: on the same predictions the
    exact-set rate can be 0% while per-category agreement is 83%."""
    n = 60
    gold = [{("DEMAND_WEAKNESS", "REALIZED")} for _ in range(n)]
    # every row keeps the right flag but adds one spurious category
    pred = [{("DEMAND_WEAKNESS", "REALIZED"), ("MARGIN_COST_PRESSURE", "HYPOTHETICAL")} for _ in range(n)]
    r = ev.score_red_flags(gold, pred, [False] * n)

    assert r["exact_set_match_category_modality"]["rate"] == 0.0
    assert r["exact_set_match_category_only"]["rate"] == 0.0
    # 6 categories x 60 rows = 360 decisions, exactly 60 wrong (the spurious one)
    d = r["per_category_decisions"]
    assert d["n_decisions"] == 360 and d["n_errors"] == 60
    assert d["agreement_rate"] == round(300 / 360, 4) == 0.8333  # rates are reported to 4dp
    # and the per-category table localises the damage to one category
    assert r["per_category"]["DEMAND_WEAKNESS"]["f1"] == 1.0
    assert r["per_category"]["MARGIN_COST_PRESSURE"]["fp"] == 60
    assert r["per_category"]["MARGIN_COST_PRESSURE"]["support"] == 0
    assert "MARGIN_COST_PRESSURE" in r["zero_support_categories"]
    assert "MARGIN_COST_PRESSURE" not in r["macro_over_supported_categories"]["categories"]


def test_red_flags_modality_only_error_fails_exact_pair_but_not_category_set():
    gold = [{("DEMAND_WEAKNESS", "REALIZED")}]
    pred = [{("DEMAND_WEAKNESS", "HYPOTHETICAL")}]
    r = ev.score_red_flags(gold, pred, [False])
    assert r["exact_set_match_category_modality"]["rate"] == 0.0
    assert r["exact_set_match_category_only"]["rate"] == 1.0
    assert r["per_category"]["DEMAND_WEAKNESS"]["tp"] == 1
    mg = r["modality_given_category_agreed"]
    assert mg["n"] == 1 and mg["n_agree"] == 0 and mg["rate"] == 0.0
    assert mg["confusion"] == {"REALIZED->HYPOTHETICAL": 1}


def test_unparseable_row_is_never_an_empty_set_match():
    """Most rows have no red flags. If 'no output' scored as a correct empty
    set, the red-flag headline would be inflated by the parse-failure rate."""
    gold = [set(), set()]
    pred = [set(), set()]
    ok = ev.score_red_flags(gold, pred, [False, False])
    assert ok["exact_set_match_category_modality"]["rate"] == 1.0

    failed = ev.score_red_flags(gold, pred, [True, False])
    assert failed["exact_set_match_category_modality"]["n_match"] == 1
    assert failed["exact_set_match_category_modality"]["rate"] == 0.5
    assert failed["n_parse_failed"] == 1


def test_per_category_agreement_is_dominated_by_true_negatives():
    """Documented in the report; asserted here so the claim stays true."""
    gold = [set() for _ in range(100)]
    pred = [set() for _ in range(100)]
    r = ev.score_red_flags(gold, pred, [False] * 100)
    assert r["per_category_decisions"]["agreement_rate"] == 1.0
    assert r["micro"]["tp"] == 0
    assert r["macro_over_supported_categories"]["f1"] == 0.0
    assert len(r["zero_support_categories"]) == 6


# --------------------------------------------------------------------------
# C. parse failures and schema violations
# --------------------------------------------------------------------------

def test_parse_failures_are_classified_not_dropped():
    rows = [
        mkrow("a", {"sentiment": "POSITIVE", "red_flags": []}),
        mkrow("b", {"sentiment": "NEUTRAL", "red_flags": []}),
        mkrow("c", {"sentiment": "NEGATIVE", "red_flags": []}),
    ]
    preds = {
        "a": "{not json",
        "b": '["a", "list"]',
        # "c" absent entirely
    }
    r = ev.score_slice(rows, preds)
    assert r["parse"]["n_unparseable"] == 3
    assert r["parse"]["parse_failure_rate"] == 1.0
    assert r["parse"]["n_missing_prediction"] == 1
    assert set(r["parse"]["reasons"]) == {"json_decode_error", "not_a_json_object", "missing_prediction"}
    assert r["sentiment"]["n"] == 3, "unparseable rows stay in the denominator"
    assert r["sentiment"]["n_correct"] == 0


def test_code_fenced_json_is_tolerated():
    parsed, err = ev.parse_model_output('```json\n{"sentiment": "POSITIVE", "red_flags": []}\n```')
    assert err is None and parsed["sentiment"] == "POSITIVE"


def test_schema_extra_keys_including_distress_tier():
    issues = ev.validate_schema(
        {"sentiment": "POSITIVE", "red_flags": [], "distress_tier": "NONE", "confidence": 0.9}
    )
    assert "extra_key:distress_tier" in issues
    assert "extra_key:confidence" in issues


def test_schema_enum_violations():
    issues = ev.validate_schema({"sentiment": "VERY_POSITIVE", "guidance_direction": "UP", "red_flags": []})
    assert "bad_enum:sentiment" in issues
    assert "bad_enum:guidance_direction" in issues

    issues = ev.validate_schema(
        {"red_flags": [{"category": "NOT_A_CATEGORY", "modality": "MAYBE"}]}
    )
    assert "bad_enum:red_flag_category" in issues
    assert "bad_enum:red_flag_modality" in issues


def test_schema_missing_and_mistyped_red_flags():
    assert "missing_key:red_flags" in ev.validate_schema({"sentiment": "NEUTRAL"})
    assert "bad_type:red_flags" in ev.validate_schema({"red_flags": "none"})
    assert "bad_type:red_flag_entry" in ev.validate_schema({"red_flags": ["DEMAND_WEAKNESS"]})


def test_invalid_enum_is_an_error_not_a_dropped_row():
    rows = [mkrow("a", {"sentiment": "POSITIVE", "red_flags": []})]
    preds = {"a": json.dumps({"sentiment": "MILDLY_POSITIVE", "red_flags": []})}
    r = ev.score_slice(rows, preds)
    assert r["parse"]["n_unparseable"] == 0, "valid JSON with a bad enum is NOT a parse failure"
    assert r["schema"]["n_rows_with_violations"] == 1
    assert r["sentiment"]["n"] == 1 and r["sentiment"]["n_correct"] == 0
    assert r["sentiment"]["failure_attribution"] == {ev.S_INVALID_ENUM: 1}


def test_out_of_taxonomy_red_flag_is_not_scored_as_a_category():
    rows = [mkrow("a", {"red_flags": [{"category": "DEMAND_WEAKNESS", "modality": "REALIZED"}]})]
    preds = {"a": json.dumps({"red_flags": [
        {"category": "DEMAND_WEAKNESS", "modality": "REALIZED"},
        {"category": "MADE_UP_RISK", "modality": "REALIZED"},
    ]})}
    r = ev.score_slice(rows, preds)
    assert r["schema"]["n_rows_with_violations"] == 1
    assert r["red_flags"]["exact_set_match_category_modality"]["rate"] == 1.0, (
        "an invented category is reported as a schema violation, not smuggled into the "
        "per-category table where it would create a phantom class"
    )


def test_field_presence_agreement():
    rows = [
        mkrow("a", {"sentiment": "POSITIVE", "red_flags": []}),          # gold has sentiment
        mkrow("b", {"red_flags": []}),                                    # RISK_FACTORS-like
    ]
    preds = {
        "a": json.dumps({"sentiment": "POSITIVE", "red_flags": []}),
        "b": json.dumps({"sentiment": "NEGATIVE", "red_flags": []}),      # emitted when it shouldn't
    }
    r = ev.score_slice(rows, preds)
    fp = r["field_presence"]["sentiment"]
    assert fp["counts"]["gold_yes_pred_yes"] == 1
    assert fp["counts"]["gold_no_pred_yes"] == 1
    assert fp["n_determined"] == 2 and fp["n_agree"] == 1
    assert fp["agreement_rate"] == 0.5


# --------------------------------------------------------------------------
# D. resume / checkpointing
# --------------------------------------------------------------------------

def test_load_predictions_tolerates_a_torn_final_line():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "predictions.jsonl"
        p.write_text(
            json.dumps({"chunk_id": "a", "raw_output": "{}"}) + "\n"
            + json.dumps({"chunk_id": "b", "raw_output": "{}"}) + "\n"
            + '{"chunk_id": "c", "raw_out'  # killed mid-write
        )
        got = ev.load_predictions(p)
        assert set(got) == {"a", "b"}


def test_resume_skips_completed_rows():
    rows = [
        {"chunk_id": "a", "_prompt_sha256": "sha_a"},
        {"chunk_id": "b", "_prompt_sha256": "sha_b"},
        {"chunk_id": "c", "_prompt_sha256": "sha_c"},
    ]
    existing = {
        "a": {"chunk_id": "a", "prompt_sha256": "sha_a"},
        "b": {"chunk_id": "b", "prompt_sha256": "sha_b"},
    }
    todo = ev.select_rows_to_generate(rows, existing)
    assert [r["chunk_id"] for r in todo] == ["c"]

    assert ev.select_rows_to_generate(rows, {}) == rows
    assert ev.select_rows_to_generate(rows, {r["chunk_id"]: {"prompt_sha256": r["_prompt_sha256"]}
                                             for r in rows}) == []


def test_resume_refuses_when_the_prompt_changed_under_it():
    rows = [{"chunk_id": "a", "_prompt_sha256": "new_sha"}]
    existing = {"a": {"chunk_id": "a", "prompt_sha256": "old_sha"}}
    try:
        ev.select_rows_to_generate(rows, existing)
    except SystemExit as e:
        assert "DIFFERENT prompt" in str(e)
    else:
        raise AssertionError("a changed prompt under a resume must be a hard stop")


def test_resume_accepts_legacy_records_without_a_prompt_hash():
    rows = [{"chunk_id": "a", "_prompt_sha256": "sha_a"}]
    assert ev.select_rows_to_generate(rows, {"a": {"chunk_id": "a"}}) == []


def test_append_prediction_is_durable_and_appendable():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "predictions.jsonl"
        for i in range(3):
            with open(p, "a") as fh:
                ev.append_prediction(fh, {"chunk_id": f"c{i}", "raw_output": "{}"})
            assert len(ev.load_predictions(p)) == i + 1


# --------------------------------------------------------------------------
# E. artifact verification + end-to-end score-only
# --------------------------------------------------------------------------

def _fake_adapter_dir(d, model_path):
    ad = Path(d) / "adapter"
    ad.mkdir()
    (ad / "adapter_config.json").write_text(json.dumps({
        "model": model_path, "fine_tune_type": "lora", "max_seq_length": 2048,
        "num_layers": 16, "iters": 5236,
        "lora_parameters": {"rank": 16, "scale": 2.0, "dropout": 0.05,
                            "keys": ["self_attn.q_proj", "self_attn.v_proj"]},
    }))
    (ad / "adapters.safetensors").write_bytes(b"not-real-weights")
    (ad / "0000500_adapters.safetensors").write_bytes(b"not-real-weights")
    return ad


def test_adapter_provenance_hashes_and_identifies_the_checkpoint():
    with tempfile.TemporaryDirectory() as d:
        ad = _fake_adapter_dir(d, "/models/qwen")
        prov = ev._adapter_provenance(ad, "/models/qwen")
        assert prov["matches_checkpoint"] == "0000500_adapters.safetensors"
        assert len(prov["adapters_sha256"]) == 64
        assert prov["lora_parameters"]["rank"] == 16


def test_adapter_provenance_rejects_a_mismatched_base_model():
    with tempfile.TemporaryDirectory() as d:
        ad = _fake_adapter_dir(d, "/models/some-other-model")
        try:
            ev._adapter_provenance(ad, "/models/qwen")
        except SystemExit as e:
            assert "does not match the training run" in str(e)
        else:
            raise AssertionError("a mismatched base model must be a hard stop")


def test_score_all_excludes_8k_body_from_headline():
    rows = eval_rows()
    section_types = ev.load_section_types()
    preds = {r["chunk_id"]: perfect_pred(r["gold"]) for r in rows}
    scored = ev.score_all(rows, preds, section_types)

    assert scored["headline_row_count"] == 1002
    assert scored["excluded_row_count"] == 8
    assert scored["excluded_slice_8K_BODY"]["n_rows"] == 8
    assert scored["section_type_counts"]["8K_BODY"] == 8
    assert "8K_BODY" not in scored["by_section_type"]
    # perfect predictions -> perfect agreement on the headline slice
    h = scored["headline"]
    assert h["sentiment"]["exact_match"] == 1.0
    assert h["guidance_direction"]["exact_match"] == 1.0
    assert h["red_flags"]["exact_set_match_category_modality"]["rate"] == 1.0
    assert h["parse"]["parse_failure_rate"] == 0.0
    # sentiment applies to MDA + EX99 + 8K_BODY; headline drops the 8 8K rows
    assert h["sentiment"]["n"] == 875 - 8
    assert h["guidance_direction"]["n"] == 578 - 8
    assert "WITHDRAWN" in h["guidance_direction"]["zero_support_classes"]


def test_report_states_the_exclusions_and_the_teacher_caveat():
    rows = eval_rows()
    section_types = ev.load_section_types()
    preds = {r["chunk_id"]: perfect_pred(r["gold"]) for r in rows}
    scored = ev.score_all(rows, preds, section_types)
    meta = {
        "run_id": "test", "generated_utc": "now",
        "model": {"path": "/m", "weights_sha256": "x"},
        "adapter": {"path": "/a", "adapters_sha256": "y", "adapter_config_sha256": "z",
                    "matches_checkpoint": "0000500_adapters.safetensors"},
        "train_manifest": {"path": "/t"}, "data": scored and {
            "eval_rows_file": "v", "eval_rows_sha256": "s", "instruction_sha256": "i",
            "instruction_byte_identical_across_eval": True,
            "instruction_byte_identical_to_train": True,
            "sha_matches_train_manifest": True,
        },
        "generation": {"decoding": "greedy"}, "versions": {},
        "n_scored": 1010, "n_eval_rows": 1010, "partial": False,
    }
    rep = ev.format_report(scored, meta)

    assert "AGREEMENT WITH THE TEACHER, not accuracy" in rep
    assert "36.6%" in rep
    assert "8K_BODY" in rep and "NOT EVALUABLE" in rep
    assert "WITHDRAWN" in rep
    assert "`distress_tier` is not reported" in rep
    assert "does not predict prices" in rep
    # both red-flag bases present
    assert "red_flags — exact-set basis" in rep
    assert "red_flags — per-category decomposition" in rep
    assert "Parse-failure rate" in rep
    # no distress_tier metrics section anywhere
    assert "## distress" not in rep.lower()


def test_end_to_end_score_only_cli_writes_a_report():
    """Full `--backend mlx --score-only` run: no model, no GPU, real report."""
    rows = eval_rows()
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "2026-08-21-eval-epoch1"
        out.mkdir()
        with open(out / "predictions.jsonl", "w") as fh:
            for i, r in enumerate(rows):
                raw = "{{{ not json" if i % 50 == 0 else perfect_pred(r["gold"])
                ev.append_prediction(fh, {
                    "chunk_id": r["chunk_id"], "raw_output": raw,
                    "prompt_tokens": 1100, "generation_tokens": 40,
                    "prompt_tps": 600.0, "generation_tps": 25.0,
                    "finish_reason": "stop", "latency_s": 3.5,
                })
        ad = _fake_adapter_dir(d, _model_snapshot())
        cmd = [
            sys.executable, str(HERE / "eval.py"), "--backend", "mlx", "--score-only",
            "--out-dir", str(out), "--adapter-path", str(ad),
            "--skip-train-instruction-check",
        ]
        p = subprocess.run(cmd, capture_output=True, text=True)
        assert p.returncode == 0, p.stdout[-3000:] + p.stderr[-3000:]
        assert (out / "eval_report.md").exists()
        assert (out / "metrics.json").exists()
        assert (out / "manifest.json").exists()

        m = json.loads((out / "metrics.json").read_text())
        assert m["headline_row_count"] == 1002
        # 1010/50 -> 21 injected parse failures, of which some fall in 8K_BODY
        assert m["headline"]["parse"]["n_unparseable"] > 0
        man = json.loads((out / "manifest.json").read_text())
        assert man["cost_usd"] == 0.0 and man["anthropic_api_calls"] == 0
        assert man["data"]["sha_matches_train_manifest"] is True
        assert man["generation"]["decoding"].startswith("greedy")
        assert man["throughput"]["chunks_per_hour"] is not None
        rep = (out / "eval_report.md").read_text()
        assert "NOT EVALUABLE" in rep and "8K_BODY" in rep


class _FakeResponse:
    def __init__(self, text, n, prompt_tokens, finish_reason):
        self.text = text
        self.token = 0
        self.prompt_tokens = prompt_tokens
        self.prompt_tps = 600.0
        self.generation_tokens = n
        self.generation_tps = 25.0
        self.finish_reason = finish_reason
        self.peak_memory = 6.7


def _install_mlx_stubs(calls, answer='{"sentiment": "NEUTRAL", "red_flags": []}'):
    """Put fake `mlx_lm` modules in sys.modules BEFORE eval.py imports them, so
    the generation loop can be exercised without importing mlx or touching the
    GPU. Returns a restore() callable."""
    import types

    saved = {k: sys.modules.get(k) for k in ("mlx_lm", "mlx_lm.generate", "mlx_lm.sample_utils")}

    def fake_stream_generate(model, tokenizer, prompt, max_tokens=256, sampler=None, **kw):
        calls.append({"prompt": prompt, "max_tokens": max_tokens, "sampler": sampler})
        parts = [answer[:5], answer[5:]]
        for i, p in enumerate(parts):
            yield _FakeResponse(p, i + 1, len(prompt), None if i == 0 else "stop")

    m = types.ModuleType("mlx_lm")
    m.load = lambda path, adapter_path=None: (f"model@{path}", f"tok@{adapter_path}")
    gen = types.ModuleType("mlx_lm.generate")
    gen.stream_generate = fake_stream_generate
    su = types.ModuleType("mlx_lm.sample_utils")

    def fake_make_sampler(temp=0.0, **kw):
        calls.append({"sampler_temp": temp})
        return "argmax-sampler"

    su.make_sampler = fake_make_sampler
    m.generate = gen
    m.sample_utils = su
    sys.modules["mlx_lm"] = m
    sys.modules["mlx_lm.generate"] = gen
    sys.modules["mlx_lm.sample_utils"] = su

    def restore():
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    return restore


class _Args:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_generation_loop_checkpoints_every_row_and_is_deterministic():
    get_tokenizer()  # skip early if transformers is unavailable
    rows = [dict(r) for r in eval_rows()[:3]]
    calls = []
    restore = _install_mlx_stubs(calls)
    try:
        with tempfile.TemporaryDirectory() as d:
            args = _Args(model=_model_snapshot(), adapter_path="/fake/adapter",
                         max_tokens=520, resume=True, progress_every=100)
            records, tput = ev.mlx_generate(rows, args, d)

            assert len(records) == 3
            preds = ev.load_predictions(Path(d) / "predictions.jsonl")
            assert len(preds) == 3
            for cid, rec in preds.items():
                assert rec["raw_output"] == '{"sentiment": "NEUTRAL", "red_flags": []}'
                assert len(rec["prompt_sha256"]) == 64
                assert rec["latency_s"] >= 0 and rec["finish_reason"] == "stop"
                assert rec["generation_tokens"] == 2
            assert tput["n_rows_generated_this_process"] == 3
            assert tput["chunks_per_hour"] > 0
            assert tput["finish_reasons"] == {"stop": 3}
            assert tput["projections"], "F4 projections must be present"

            # deterministic decoding was actually requested
            assert {"sampler_temp": 0.0} in calls
            gen_calls = [c for c in calls if "prompt" in c]
            assert len(gen_calls) == 3
            assert all(c["max_tokens"] == 520 for c in gen_calls)
            assert all(c["sampler"] == "argmax-sampler" for c in gen_calls)
            # the prompt handed to the model is the contract-rendered token list
            tok = get_tokenizer()
            assert gen_calls[0]["prompt"] == ev.render_prompt_token_ids(tok, rows[0])
            assert all(isinstance(t, int) for t in gen_calls[0]["prompt"])
    finally:
        restore()


def test_generation_loop_resumes_without_regenerating():
    get_tokenizer()
    rows = [dict(r) for r in eval_rows()[:4]]
    calls = []
    restore = _install_mlx_stubs(calls)
    try:
        with tempfile.TemporaryDirectory() as d:
            args = _Args(model=_model_snapshot(), adapter_path="/fake/adapter",
                         max_tokens=520, resume=True, progress_every=100)
            ev.mlx_generate(rows[:2], args, d)
            n_after_first = len([c for c in calls if "prompt" in c])
            assert n_after_first == 2

            # second pass over all 4 rows: only the 2 new ones get generated
            records, tput = ev.mlx_generate(rows, args, d)
            n_total = len([c for c in calls if "prompt" in c])
            assert n_total - n_after_first == 2, "already-finished rows must be skipped"
            assert len(records) == 4
            assert tput["n_rows_generated_this_process"] == 2
            lines = (Path(d) / "predictions.jsonl").read_text().strip().split("\n")
            assert len(lines) == 4, "resume must append, not rewrite"
    finally:
        restore()


def test_generation_loop_refuses_no_resume_over_an_existing_file():
    get_tokenizer()
    rows = [dict(r) for r in eval_rows()[:1]]
    restore = _install_mlx_stubs([])
    try:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "predictions.jsonl").write_text("")
            args = _Args(model=_model_snapshot(), adapter_path="/fake/adapter",
                         max_tokens=520, resume=False, progress_every=100)
            try:
                ev.mlx_generate(rows, args, d)
            except SystemExit as e:
                assert "already exists" in str(e)
            else:
                raise AssertionError("--no-resume over an existing file must be a hard stop")
    finally:
        restore()


def test_dry_run_still_works_and_mentions_nothing_new():
    p = subprocess.run(
        [sys.executable, str(HERE / "eval.py"), "--dry-run"], capture_output=True, text=True
    )
    assert p.returncode == 0
    assert p.stdout.startswith("(--dry-run: using SYNTHETIC predictions")
    assert "HELD-OUT EVALUATION REPORT" in p.stdout
    assert p.stdout.rstrip().endswith("=" * 70)


# --------------------------------------------------------------------------

def _all_tests():
    return [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]


def main():
    passed = failed = skipped = 0
    failures = []
    for name, fn in _all_tests():
        try:
            fn()
        except Skip as e:
            skipped += 1
            print(f"SKIP {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            failures.append((name, e))
            print(f"FAIL {name}: {type(e).__name__}: {e}")
        else:
            passed += 1
            print(f"ok   {name}")
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    if failures:
        import traceback

        for name, e in failures:
            print(f"\n--- {name} ---")
            traceback.print_exception(type(e), e, e.__traceback__)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
