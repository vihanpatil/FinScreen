"""
test_submit_complete_missing.py — offline tests for --complete-missing,
the guarded mode that finishes rows an existing labels parquet never got
answers for (2026-08-26; the v1.2 re-label's credit-balance bounce left
CHK-1c1812ed45219a3a unanswered in data/labels_v12.parquet).

HARD CONSTRAINT, same as test_submit_variant_wiring.py: no network, no
real client, no .env/API key touched. Every path that could construct a
client either is asserted never to reach one, or has
submit_labeling_batch.get_client monkeypatched to a fake that records
what it was asked to submit.

The property under test throughout is scope: this mode completes bounced
SINGLETONS. It must refuse above --max-missing, refuse without
--confirm-complete, refuse to overwrite a row that already carries a
label, and refuse to clobber the pre-merge backup.

Run with: python3 -m pytest test_submit_complete_missing.py -v
"""
from __future__ import annotations

import json
import os

import pandas as pd
import pytest

import submit_labeling_batch as sub
from build_batch_requests import MODEL, build_request, system_prompt_sha256


# ---------------------------------------------------------------------
# Fakes — mirror the real SDK shapes run_complete_missing()/run_poll()
# read, and record every create() call so "nothing was submitted" is an
# assertion rather than a hope.
# ---------------------------------------------------------------------
class _FakeBatch:
    def __init__(self, batch_id="msgbatch_FAKECOMPLETION0000000000"):
        self.id = batch_id
        self.created_at = "2026-08-26T18:00:00Z"
        self.processing_status = "in_progress"


class _FakeBatchesResource:
    def __init__(self):
        self.create_calls = []

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return _FakeBatch()


class _FakeMessagesResource:
    def __init__(self):
        self.batches = _FakeBatchesResource()


class _FakeClient:
    def __init__(self):
        self.messages = _FakeMessagesResource()


def _no_client(monkeypatch):
    """Installs a get_client that blows up if anything tries to use it."""
    calls = []

    def _boom():
        calls.append("get_client")
        raise AssertionError("this path must never construct a client")

    monkeypatch.setattr(sub, "get_client", _boom)
    return calls


# ---------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------
_RF = [{"category": "DEMAND_WEAKNESS", "modality": "REALIZED"}]


def _answered_row(chunk_id, section_type="MDA", **over):
    row = {
        "chunk_id": chunk_id,
        "section_type": section_type,
        "text": f"passage for {chunk_id}",
        "parse_ok": True,
        "schema_valid": True,
        "api_result_type": "succeeded",
        "parse_error": None,
        "raw_label_json": '{"sentiment": "NEUTRAL"}',
        "sentiment": "NEUTRAL",
        "guidance_direction": None,
        "red_flags": list(_RF),
        "distress_tier": [],
        "stop_reason": "end_turn",
        "output_tokens": 70.0,
        "batch_id": "msgbatch_ORIGINAL",
        "max_tokens_used": 4000,
        "labeling_config": "thinking=disabled,max_tokens=4000",
        "rubric_version": "v1.2",
        "system_prompt_sha256": "deadbeef",
        "labeled_at": "2026-08-26T16:00:00+00:00",
    }
    row.update(over)
    return row


def _bounced_row(chunk_id, section_type="MDA"):
    """The credit-balance bounce shape: errored, nothing came back."""
    return _answered_row(
        chunk_id,
        section_type=section_type,
        parse_ok=False,
        schema_valid=False,
        api_result_type="errored",
        parse_error="batch result type=errored, not 'succeeded'",
        raw_label_json=None,
        sentiment=None,
        guidance_direction=None,
        red_flags=None,
        distress_tier=None,
        stop_reason=None,
        output_tokens=float("nan"),
    )


def _labels_frame(rows):
    return pd.DataFrame(rows)


def _write_target(tmp_path, rows, name="labels_target.parquet"):
    path = tmp_path / name
    _labels_frame(rows).to_parquet(path)
    return str(path)


def _write_requests(tmp_path, chunk_ids, variant="v12_relabel",
                    name="requests.jsonl", section_type="MDA"):
    """A REAL request file: bodies come from build_batch_requests so both
    the variant guard and the rubric guard see genuine artifacts."""
    path = tmp_path / name
    with open(path, "w") as f:
        for cid in chunk_ids:
            req = build_request(cid, section_type, f"passage for {cid}",
                                variant=variant)
            f.write(json.dumps(req) + "\n")
    return str(path)


# =====================================================================
# GROUP 1 — find_missing_label_rows: what counts as unanswered.
# =====================================================================
def test_find_missing_flags_only_the_bounced_row():
    df = _labels_frame(
        [_answered_row("CHK-a"), _bounced_row("CHK-b"), _answered_row("CHK-c")]
    )
    found = sub.find_missing_label_rows(df)
    assert found["missing_ids"] == ["CHK-b"]
    assert found["n_missing"] == 1
    assert found["n_rows"] == 3


def test_find_missing_does_not_flag_a_refusal():
    """E1's CHK-8e69547e0900a8dd shape: a genuine safety refusal is an
    ANSWER — excluded by predicate, never re-asked, and certainly never
    silently re-submitted by a completion run."""
    refusal = _answered_row(
        "CHK-refusal",
        parse_ok=False,
        schema_valid=False,
        raw_label_json=None,
        sentiment=None,
        guidance_direction=None,
        red_flags=None,
        distress_tier=None,
        stop_reason="refusal",
    )
    found = sub.find_missing_label_rows(_labels_frame([refusal, _answered_row("CHK-a")]))
    assert found["missing_ids"] == []
    # ...but it IS reported, so nobody has to guess why it was left alone.
    assert found["n_excluded_answered_failures"] == 1
    assert found["excluded_answered_failures"][0]["chunk_id"] == "CHK-refusal"
    assert found["excluded_answered_failures"][0]["stop_reason"] == "refusal"


def test_find_missing_does_not_flag_a_truncation():
    """stop_reason='max_tokens' is an answer that ran out of room — a
    config problem for a variant re-run, not a bounce to complete."""
    truncated = _answered_row(
        "CHK-trunc",
        parse_ok=False,
        schema_valid=False,
        raw_label_json='{"sentiment": "NEU',
        sentiment=None,
        guidance_direction=None,
        red_flags=None,
        distress_tier=None,
        stop_reason="max_tokens",
    )
    found = sub.find_missing_label_rows(_labels_frame([truncated]))
    assert found["missing_ids"] == []
    assert found["n_excluded_answered_failures"] == 1


def test_find_missing_does_not_flag_healthy_rows_with_empty_or_absent_labels():
    """A RISK_FACTORS row is never asked for sentiment/guidance and can
    legitimately carry an EMPTY red_flags list. Empty is an answer ("no
    flags here"); treating it as missing would re-submit the corpus."""
    rf_row = _answered_row(
        "CHK-rf",
        section_type="RISK_FACTORS",
        sentiment=None,
        guidance_direction=None,
        red_flags=[],
        distress_tier=[],
    )
    found = sub.find_missing_label_rows(_labels_frame([rf_row]))
    assert found["missing_ids"] == []
    assert found["n_excluded_answered_failures"] == 0


def test_find_missing_reports_answered_failures_separately_from_missing():
    df = _labels_frame(
        [
            _bounced_row("CHK-bounce"),
            _answered_row("CHK-schema", schema_valid=False,
                          parse_error="unexpected fields"),
            _answered_row("CHK-ok"),
        ]
    )
    found = sub.find_missing_label_rows(df)
    assert found["missing_ids"] == ["CHK-bounce"]
    assert [r["chunk_id"] for r in found["excluded_answered_failures"]] == ["CHK-schema"]


def test_find_missing_raises_on_a_frame_without_the_required_columns():
    df = pd.DataFrame({"chunk_id": ["CHK-a"], "sentiment": ["NEUTRAL"]})
    with pytest.raises(ValueError, match="missing required column"):
        sub.find_missing_label_rows(df)


def test_find_missing_on_the_real_v12_parquet_sees_the_completed_corpus():
    """RE-PINNED 2026-09-07. Ground truth (HARDENING_PROGRESS 'G1 REPAIR
    CAMPAIGN'): the v1.2 batch ended 6,746/6,747 and the one API-errored row
    was CHK-1c1812ed45219a3a. The completion batch then ANSWERED that row, so
    on the current corpus the correct answer is zero missing rows — this test
    was pinned to the pre-completion artifact and had gone red.

    The original ground truth is not deleted, it MOVES to the artifact that
    still carries it: data/labels_v12.parquet.pre_completion. Both legs verified
    against the parquets on 2026-09-07 (post: 6747 rows, 0 missing, the target
    row parse_ok=True/schema_valid=True; pre: the same 6747 rows with exactly
    that one id missing). Read-only; skips if absent from the checkout.
    """
    path = "data/labels_v12.parquet"
    if not os.path.exists(path):
        pytest.skip(f"{path} not present in this checkout")
    found = sub.find_missing_label_rows(pd.read_parquet(path))
    assert found["n_rows"] == 6747
    assert found["missing_ids"] == [], (
        "labels_v12.parquet has unanswered rows again — the 2026-08-27 "
        f"completion batch is the only thing that filled them: {found['missing_ids']}")

    pre = path + ".pre_completion"
    if not os.path.exists(pre):
        pytest.skip(f"{pre} not present in this checkout")
    before = sub.find_missing_label_rows(pd.read_parquet(pre))
    assert before["n_rows"] == 6747
    assert before["missing_ids"] == ["CHK-1c1812ed45219a3a"], (
        "the detector no longer finds the one bounced row in the "
        f"pre-completion artifact: {before['missing_ids']}")


# =====================================================================
# GROUP 2 — select_completion_requests: EXACTLY those custom_ids.
# =====================================================================
def test_select_completion_requests_extracts_exactly_the_named_ids(tmp_path):
    req_file = _write_requests(tmp_path, [f"CHK-{i}" for i in range(5)])
    by_id = sub.load_requests_by_custom_id(req_file)
    picked = sub.select_completion_requests(["CHK-3", "CHK-1"], by_id, req_file)
    assert [r["custom_id"] for r in picked] == ["CHK-3", "CHK-1"]


def test_select_completion_requests_refuses_when_an_id_has_no_request(tmp_path):
    req_file = _write_requests(tmp_path, ["CHK-0", "CHK-1"])
    by_id = sub.load_requests_by_custom_id(req_file)
    with pytest.raises(sub.VariantMismatchError, match="no request in"):
        sub.select_completion_requests(["CHK-0", "CHK-nope"], by_id, req_file)


# =====================================================================
# GROUP 3 — cost estimate.
# =====================================================================
def test_estimate_completion_cost_counts_both_tiers_off_the_request_bodies(tmp_path):
    req_file = _write_requests(tmp_path, ["CHK-0"])
    reqs = list(sub.load_requests_by_custom_id(req_file).values())
    est = sub.estimate_completion_cost(reqs, 68.31)
    assert est["n_requests"] == 1
    assert est["cache_write_input_tokens_est"] > 1024  # the cached system prefix
    assert est["plain_input_tokens_est"] > 0
    assert set(est["cost_usd_by_tier"]) == {"intro", "standard"}
    assert 0 < est["cost_usd_by_tier"]["intro"] < est["cost_usd_by_tier"]["standard"]


def test_estimate_completion_cost_scales_with_request_count(tmp_path):
    one = list(sub.load_requests_by_custom_id(
        _write_requests(tmp_path, ["CHK-0"], name="one.jsonl")).values())
    three = list(sub.load_requests_by_custom_id(
        _write_requests(tmp_path, ["CHK-0", "CHK-1", "CHK-2"], name="three.jsonl")
    ).values())
    c1 = sub.estimate_completion_cost(one, 70)["cost_usd_by_tier"]["intro"]
    c3 = sub.estimate_completion_cost(three, 70)["cost_usd_by_tier"]["intro"]
    assert c3 > c1


def test_estimate_completion_cost_is_pure_and_touches_no_client(tmp_path, monkeypatch):
    calls = _no_client(monkeypatch)
    reqs = list(sub.load_requests_by_custom_id(
        _write_requests(tmp_path, ["CHK-0"])).values())
    sub.estimate_completion_cost(reqs, 70)
    assert calls == []


def test_measure_output_tokens_estimate_uses_measured_rows_then_falls_back():
    df = _labels_frame([
        _answered_row("CHK-a", output_tokens=60.0),
        _answered_row("CHK-b", output_tokens=80.0),
        _bounced_row("CHK-c"),
    ])
    mean, n = sub.measure_output_tokens_estimate(df, ["MDA"])
    assert (mean, n) == (70.0, 2)
    # No measurable rows of that section type -> the planning fallback,
    # reported honestly as such by the caller.
    mean2, n2 = sub.measure_output_tokens_estimate(df, ["8K_BODY"])
    assert mean2 == float(sub.FALLBACK_OUTPUT_TOKENS_PER_REQUEST)
    assert n2 == 0


# =====================================================================
# GROUP 4 — run_complete_missing: the gates.
# =====================================================================
def test_complete_missing_with_nothing_to_do_exits_zero_and_submits_nothing(
    tmp_path, monkeypatch, capsys
):
    calls = _no_client(monkeypatch)
    target = _write_target(tmp_path, [_answered_row("CHK-a"), _answered_row("CHK-b")])
    req_file = _write_requests(tmp_path, ["CHK-a", "CHK-b"])

    code = sub.run_complete_missing(
        against=target, variant="v12_relabel", requests_file=req_file,
        meta_path=str(tmp_path / "meta.json"), confirm=True,
    )
    assert code == 0
    assert calls == []
    assert "Nothing to complete" in capsys.readouterr().out
    assert not (tmp_path / "meta.json").exists()


def test_complete_missing_refuses_above_the_max_missing_guard(
    tmp_path, monkeypatch, capsys
):
    """The whole point of the mode's scope: 4 unanswered rows against a
    default guard of 3 is a campaign, not a bounced singleton."""
    calls = _no_client(monkeypatch)
    rows = [_bounced_row(f"CHK-{i}") for i in range(4)] + [_answered_row("CHK-ok")]
    target = _write_target(tmp_path, rows)
    req_file = _write_requests(tmp_path, [f"CHK-{i}" for i in range(4)] + ["CHK-ok"])

    code = sub.run_complete_missing(
        against=target, variant="v12_relabel", requests_file=req_file,
        meta_path=str(tmp_path / "meta.json"), confirm=True,
    )
    assert code == 1
    assert calls == []
    err = capsys.readouterr().err
    assert "REFUSING TO SUBMIT" in err
    assert "not a campaign re-runner" in err
    assert not (tmp_path / "meta.json").exists()


def test_max_missing_default_is_three_and_is_pinned():
    """Pins the default in both the constant and the function signature —
    raising it has to be a deliberate, visible edit (or a CLI flag), never
    a drift."""
    import inspect

    assert sub.DEFAULT_MAX_MISSING == 3
    sig = inspect.signature(sub.run_complete_missing)
    assert sig.parameters["max_missing"].default == 3
    # ...and the confirm gate defaults to OFF.
    assert sig.parameters["confirm"].default is False


def test_complete_missing_without_confirm_prints_count_and_cost_and_submits_nothing(
    tmp_path, monkeypatch, capsys
):
    calls = _no_client(monkeypatch)
    target = _write_target(tmp_path, [_answered_row("CHK-a"), _bounced_row("CHK-b")])
    req_file = _write_requests(tmp_path, ["CHK-a", "CHK-b"])

    code = sub.run_complete_missing(
        against=target, variant="v12_relabel", requests_file=req_file,
        meta_path=str(tmp_path / "meta.json"), confirm=False,
    )
    assert code == 1
    assert calls == []
    captured = capsys.readouterr()
    assert "requests: 1" in captured.out
    assert "estimated cost" in captured.out
    assert "cost_usd_by_tier" in captured.out
    assert "--confirm-complete" in captured.err
    assert not (tmp_path / "meta.json").exists()


def test_complete_missing_with_confirm_submits_exactly_the_unanswered_requests(
    tmp_path, monkeypatch
):
    fake = _FakeClient()
    monkeypatch.setattr(sub, "get_client", lambda: fake)
    target = _write_target(
        tmp_path, [_answered_row("CHK-a"), _bounced_row("CHK-b"), _answered_row("CHK-c")]
    )
    req_file = _write_requests(tmp_path, ["CHK-a", "CHK-b", "CHK-c"])

    code = sub.run_complete_missing(
        against=target, variant="v12_relabel", requests_file=req_file,
        meta_path=str(tmp_path / "meta.json"), confirm=True,
    )
    assert code == 0
    assert len(fake.messages.batches.create_calls) == 1
    submitted = fake.messages.batches.create_calls[0]["requests"]
    assert [r["custom_id"] for r in submitted] == ["CHK-b"]


def test_complete_missing_runs_the_variant_guard_before_submitting(
    tmp_path, monkeypatch
):
    """A requests file whose bodies don't match the named variant must be
    refused at the same choke point every other submit path uses."""
    calls = _no_client(monkeypatch)
    target = _write_target(tmp_path, [_bounced_row("CHK-b")])
    # Built as 'disabled' (max_tokens=800) but submitted as 'v12_relabel'.
    req_file = _write_requests(tmp_path, ["CHK-b"], variant="disabled")

    with pytest.raises(sub.VariantMismatchError, match="variant/artifact mismatch"):
        sub.run_complete_missing(
            against=target, variant="v12_relabel", requests_file=req_file,
            meta_path=str(tmp_path / "meta.json"), confirm=True,
        )
    assert calls == []


def test_complete_missing_runs_the_rubric_guard_for_pinned_variants(
    tmp_path, monkeypatch
):
    """v12_relabel is rubric-pinned: a request file carrying a stale
    system prompt would sail through the variant guard and re-label under
    the wrong rubric. Completion gets no discount on that check."""
    calls = _no_client(monkeypatch)
    target = _write_target(tmp_path, [_bounced_row("CHK-b")])
    req_file = tmp_path / "stale.jsonl"
    req = build_request("CHK-b", "MDA", "passage for CHK-b", variant="v12_relabel")
    req["params"]["system"][0]["text"] = "STALE v1.1 RUBRIC TEXT"
    req_file.write_text(json.dumps(req) + "\n")

    assert "v12_relabel" in sub.RUBRIC_PINNED_VARIANTS
    with pytest.raises(sub.VariantMismatchError, match="rubric/model mismatch"):
        sub.run_complete_missing(
            against=target, variant="v12_relabel", requests_file=str(req_file),
            meta_path=str(tmp_path / "meta.json"), confirm=True,
        )
    assert calls == []


def test_complete_missing_writes_full_provenance_meta(tmp_path, monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(sub, "get_client", lambda: fake)
    target = _write_target(tmp_path, [_answered_row("CHK-a"), _bounced_row("CHK-b")])
    req_file = _write_requests(tmp_path, ["CHK-a", "CHK-b"])
    meta_path = tmp_path / "v12_completion_batch_meta.json"

    sub.run_complete_missing(
        against=target, variant="v12_relabel", requests_file=req_file,
        meta_path=str(meta_path), confirm=True,
    )
    meta = json.loads(meta_path.read_text())
    assert meta["mode"] == "complete-missing"
    assert meta["batch_id"] == "msgbatch_FAKECOMPLETION0000000000"
    assert meta["custom_ids"] == ["CHK-b"]
    assert meta["n_submitted"] == 1
    assert meta["against"] == target
    assert meta["max_missing_guard"] == 3
    assert meta["n_rows_in_target"] == 2
    assert meta["model"] == MODEL
    assert meta["asserted_max_tokens"] == 4000
    assert meta["rubric_version"] == "v1.2"
    assert meta["system_prompt_sha256"] == system_prompt_sha256()
    assert meta["estimated_cost"]["n_requests"] == 1
    assert meta["estimated_cost"]["cost_usd_by_tier"]["intro"] > 0


def test_complete_missing_refuses_to_clobber_another_runs_meta_file(
    tmp_path, monkeypatch
):
    """A meta file is the only record of what a batch actually was. Same
    failure class as the 2026-08-11 variant-wiring bug."""
    fake = _FakeClient()
    monkeypatch.setattr(sub, "get_client", lambda: fake)
    target = _write_target(tmp_path, [_bounced_row("CHK-b")])
    req_file = _write_requests(tmp_path, ["CHK-b"])
    meta_path = tmp_path / "someone_elses_meta.json"
    meta_path.write_text(json.dumps({"mode": "full", "batch_id": "msgbatch_REAL"}))

    with pytest.raises(sub.VariantMismatchError, match="would erase it"):
        sub.run_complete_missing(
            against=target, variant="v12_relabel", requests_file=req_file,
            meta_path=str(meta_path), confirm=True,
        )
    assert fake.messages.batches.create_calls == []
    assert json.loads(meta_path.read_text())["batch_id"] == "msgbatch_REAL"


# =====================================================================
# GROUP 5 — merge_completion_into: the in-place merge.
# =====================================================================
def _completion_frame(chunk_ids, batch_id="msgbatch_FAKECOMPLETION0000000000",
                      **over):
    rows = []
    for cid in chunk_ids:
        row = _answered_row(cid, batch_id=batch_id, sentiment="NEGATIVE",
                            labeled_at="2026-08-26T18:05:00+00:00")
        row.update(over)
        rows.append(row)
    return _labels_frame(rows)


def test_merge_backs_up_the_target_before_writing(tmp_path):
    target = _write_target(tmp_path, [_answered_row("CHK-a"), _bounced_row("CHK-b")])
    before = open(target, "rb").read()

    summary = sub.merge_completion_into(target, _completion_frame(["CHK-b"]), "BID")

    backup = target + sub.COMPLETION_BACKUP_SUFFIX
    assert summary["backup_path"] == backup
    assert os.path.exists(backup)
    assert open(backup, "rb").read() == before  # byte-identical pre-merge copy
    assert open(target, "rb").read() != before  # ...and the target did change


def test_merge_refuses_when_a_backup_already_exists(tmp_path):
    target = _write_target(tmp_path, [_bounced_row("CHK-b")])
    backup = target + sub.COMPLETION_BACKUP_SUFFIX
    open(backup, "wb").write(b"an earlier pre-merge state")
    before = open(target, "rb").read()

    with pytest.raises(FileExistsError, match="already exists"):
        sub.merge_completion_into(target, _completion_frame(["CHK-b"]), "BID")
    assert open(backup, "rb").read() == b"an earlier pre-merge state"
    assert open(target, "rb").read() == before


def test_merge_refuses_to_overwrite_a_row_that_already_has_labels(tmp_path):
    """This is what keeps the mode from becoming a re-labeler: a row that
    already carries an answer is off-limits, full stop."""
    target = _write_target(tmp_path, [_answered_row("CHK-a"), _bounced_row("CHK-b")])
    before = open(target, "rb").read()

    with pytest.raises(ValueError, match="already carries an answer"):
        sub.merge_completion_into(target, _completion_frame(["CHK-a"]), "BID")
    assert open(target, "rb").read() == before
    assert not os.path.exists(target + sub.COMPLETION_BACKUP_SUFFIX)


def test_merge_refuses_a_chunk_id_that_is_not_in_the_target(tmp_path):
    target = _write_target(tmp_path, [_bounced_row("CHK-b")])
    before = open(target, "rb").read()

    with pytest.raises(ValueError, match="is not in"):
        sub.merge_completion_into(target, _completion_frame(["CHK-elsewhere"]), "BID")
    assert open(target, "rb").read() == before
    assert not os.path.exists(target + sub.COMPLETION_BACKUP_SUFFIX)


def test_merge_fills_the_row_and_stamps_completion_provenance(tmp_path):
    target = _write_target(
        tmp_path, [_answered_row("CHK-a"), _bounced_row("CHK-b"), _answered_row("CHK-c")]
    )
    summary = sub.merge_completion_into(
        target, _completion_frame(["CHK-b"], batch_id="msgbatch_COMPLETION"),
        "msgbatch_COMPLETION",
    )
    out = pd.read_parquet(target).set_index("chunk_id")

    assert summary["n_merged"] == 1
    assert summary["merged_ids"] == ["CHK-b"]
    assert summary["n_missing_after"] == 0
    filled = out.loc["CHK-b"]
    assert filled["sentiment"] == "NEGATIVE"
    assert filled["stop_reason"] == "end_turn"
    assert bool(filled["parse_ok"]) is True
    assert filled["batch_id"] == "msgbatch_COMPLETION"
    # Per-row provenance: only the completed row is stamped.
    assert filled["completion_batch_id"] == "msgbatch_COMPLETION"
    assert out.loc["CHK-a", "completion_batch_id"] is None
    assert out.loc["CHK-c", "completion_batch_id"] is None


def test_merge_leaves_every_other_row_and_the_corpus_columns_untouched(tmp_path):
    rows = [_answered_row("CHK-a"), _bounced_row("CHK-b"), _answered_row("CHK-c")]
    target = _write_target(tmp_path, rows)
    before = pd.read_parquet(target).set_index("chunk_id")

    sub.merge_completion_into(target, _completion_frame(["CHK-b"]), "BID")
    after = pd.read_parquet(target).set_index("chunk_id")

    assert len(after) == len(before) == 3
    for cid in ("CHK-a", "CHK-c"):
        for col in ("sentiment", "stop_reason", "batch_id", "labeled_at",
                    "text", "section_type"):
            assert after.loc[cid, col] == before.loc[cid, col]
    # The frozen corpus columns of the FILLED row are untouched too — a
    # merge writes labels, never passage text or section_type.
    assert after.loc["CHK-b", "text"] == before.loc["CHK-b", "text"]
    assert after.loc["CHK-b", "section_type"] == before.loc["CHK-b", "section_type"]


def test_merge_skips_a_completion_row_that_bounced_again(tmp_path):
    """A retry can bounce too. An unanswered completion row is reported,
    not merged, and the target is left exactly as it was."""
    target = _write_target(tmp_path, [_bounced_row("CHK-b")])
    before = open(target, "rb").read()

    summary = sub.merge_completion_into(
        target, _labels_frame([_bounced_row("CHK-b")]), "BID"
    )
    assert summary["n_merged"] == 0
    assert summary["skipped_ids"] == ["CHK-b"]
    assert summary["n_missing_after"] == 1
    assert summary["backup_path"] is None
    assert open(target, "rb").read() == before
    assert not os.path.exists(target + sub.COMPLETION_BACKUP_SUFFIX)


def test_merged_parquet_round_trips_list_valued_label_columns(tmp_path):
    """red_flags/distress_tier are list-of-struct columns; the merged row
    must read back as real label objects, not as a mangled scalar."""
    target = _write_target(tmp_path, [_answered_row("CHK-a"), _bounced_row("CHK-b")])
    completion = _completion_frame(["CHK-b"])
    completion.at[0, "red_flags"] = [
        {"category": "MARGIN_COST_PRESSURE", "modality": "REALIZED"},
        {"category": "DEMAND_WEAKNESS", "modality": "HYPOTHETICAL"},
    ]
    completion.at[0, "distress_tier"] = [
        {"category": "LIQUIDITY_STRESS", "modality": "HYPOTHETICAL"}
    ]

    sub.merge_completion_into(target, completion, "BID")
    filled = pd.read_parquet(target).set_index("chunk_id").loc["CHK-b"]

    got = [dict(x) for x in filled["red_flags"]]
    assert got == [
        {"category": "MARGIN_COST_PRESSURE", "modality": "REALIZED"},
        {"category": "DEMAND_WEAKNESS", "modality": "HYPOTHETICAL"},
    ]
    assert [dict(x) for x in filled["distress_tier"]] == [
        {"category": "LIQUIDITY_STRESS", "modality": "HYPOTHETICAL"}
    ]


# =====================================================================
# GROUP 6 — CLI wiring.
# =====================================================================
def test_cli_complete_missing_requires_against(monkeypatch, capsys):
    monkeypatch.setattr(
        sub.sys, "argv",
        ["submit_labeling_batch.py", "--complete-missing", "--variant", "v12_relabel"],
    )
    with pytest.raises(SystemExit) as exc:
        sub.main()
    assert exc.value.code == 1
    assert "--against" in capsys.readouterr().err


def test_cli_complete_missing_requires_variant(monkeypatch, capsys):
    monkeypatch.setattr(
        sub.sys, "argv",
        ["submit_labeling_batch.py", "--complete-missing",
         "--against", "data/labels_v12.parquet"],
    )
    with pytest.raises(SystemExit) as exc:
        sub.main()
    assert exc.value.code == 1
    assert "--variant" in capsys.readouterr().err


def test_cli_merge_into_requires_poll(monkeypatch, capsys):
    monkeypatch.setattr(
        sub.sys, "argv",
        ["submit_labeling_batch.py", "--canary",
         "--merge-into", "data/labels_v12.parquet"],
    )
    with pytest.raises(SystemExit) as exc:
        sub.main()
    assert exc.value.code == 1
    assert "--merge-into is only meaningful with --poll" in capsys.readouterr().err


def test_cli_refuses_out_equal_to_merge_into(monkeypatch, capsys):
    monkeypatch.setattr(
        sub.sys, "argv",
        ["submit_labeling_batch.py", "--poll", "msgbatch_X",
         "--out", "data/labels_v12.parquet",
         "--merge-into", "data/labels_v12.parquet"],
    )
    with pytest.raises(SystemExit) as exc:
        sub.main()
    assert exc.value.code == 1
    assert "must differ" in capsys.readouterr().err


def test_cli_complete_missing_dry_run_exits_one_without_a_client(
    tmp_path, monkeypatch, capsys
):
    """Full CLI path, no --confirm-complete: prints the preview, exits 1,
    never builds a client."""
    calls = _no_client(monkeypatch)
    target = _write_target(tmp_path, [_answered_row("CHK-a"), _bounced_row("CHK-b")])
    req_file = _write_requests(tmp_path, ["CHK-a", "CHK-b"])
    monkeypatch.setitem(
        sub.VARIANT_PATHS["v12_relabel"], "requests_file", req_file
    )
    monkeypatch.setattr(
        sub.sys, "argv",
        ["submit_labeling_batch.py", "--complete-missing",
         "--against", target, "--variant", "v12_relabel",
         "--complete-meta", str(tmp_path / "meta.json")],
    )
    with pytest.raises(SystemExit) as exc:
        sub.main()
    assert exc.value.code == 1
    assert calls == []
    assert "requests: 1" in capsys.readouterr().out


# ---------------------------------------------------------------------
# GROUP 6b — --poll --merge-into, end to end against a fake client.
# ---------------------------------------------------------------------
class _FakeUsage:
    def __init__(self):
        self.input_tokens = 780
        self.output_tokens = 66
        self.cache_creation_input_tokens = 1893
        self.cache_read_input_tokens = 0


class _FakeTextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeMessage:
    def __init__(self, text):
        self.usage = _FakeUsage()
        self.stop_reason = "end_turn"
        self.content = [_FakeTextBlock(text)]


class _FakeSucceededResult:
    def __init__(self, text):
        self.type = "succeeded"
        self.message = _FakeMessage(text)


class _FakeResultItem:
    def __init__(self, custom_id, text):
        self.custom_id = custom_id
        self.result = _FakeSucceededResult(text)


class _EndedBatch:
    def __init__(self):
        self.id = "msgbatch_COMPLETION"
        self.processing_status = "ended"
        self.request_counts = {"succeeded": 1}


def _poll_client(custom_id, payload):
    class _Batches(_FakeBatchesResource):
        def retrieve(self, batch_id):
            return _EndedBatch()

        def results(self, batch_id):
            return [_FakeResultItem(custom_id, json.dumps(payload))]

    client = _FakeClient()
    client.messages.batches = _Batches()
    return client


def test_poll_with_merge_into_writes_its_own_file_and_merges_in_place(
    tmp_path, monkeypatch, capsys
):
    corpus = pd.DataFrame(
        [
            {"chunk_id": "CHK-a", "section_type": "MDA", "text": "passage for CHK-a"},
            {"chunk_id": "CHK-b", "section_type": "MDA", "text": "passage for CHK-b"},
        ]
    )
    corpus_path = tmp_path / "corpus.parquet"
    corpus.to_parquet(corpus_path)
    monkeypatch.setattr(sub, "CORPUS_PATH", str(corpus_path))

    target = _write_target(tmp_path, [_answered_row("CHK-a"), _bounced_row("CHK-b")])
    payload = {
        "sentiment": "NEGATIVE",
        "red_flags": [{"category": "DEMAND_WEAKNESS", "modality": "REALIZED"}],
        "distress_tier": [],
    }
    monkeypatch.setattr(sub, "get_client", lambda: _poll_client("CHK-b", payload))

    out_path = tmp_path / "labels_completion.parquet"
    sub.run_poll(
        "msgbatch_COMPLETION", out_path=str(out_path), max_wait_s=1,
        variant="v12_relabel", merge_into=target,
    )

    # The completion batch's own result file survives as an audit trail...
    assert out_path.exists()
    assert len(pd.read_parquet(out_path)) == 1
    # ...and the target was filled in place, backed up first.
    assert os.path.exists(target + sub.COMPLETION_BACKUP_SUFFIX)
    merged = pd.read_parquet(target).set_index("chunk_id")
    assert len(merged) == 2
    assert merged.loc["CHK-b", "sentiment"] == "NEGATIVE"
    assert merged.loc["CHK-b", "completion_batch_id"] == "msgbatch_COMPLETION"
    assert merged.loc["CHK-b", "rubric_version"] == "v1.2"
    assert sub.find_missing_label_rows(pd.read_parquet(target))["n_missing"] == 0
    assert "MERGE INTO" in capsys.readouterr().out


def test_poll_without_merge_into_is_unchanged(tmp_path, monkeypatch):
    """Regression guard: every pre-existing --poll caller must behave
    exactly as before — no backup, no merge, no new column."""
    corpus = pd.DataFrame(
        [{"chunk_id": "CHK-b", "section_type": "MDA", "text": "passage for CHK-b"}]
    )
    corpus_path = tmp_path / "corpus.parquet"
    corpus.to_parquet(corpus_path)
    monkeypatch.setattr(sub, "CORPUS_PATH", str(corpus_path))

    target = _write_target(tmp_path, [_bounced_row("CHK-b")])
    before = open(target, "rb").read()
    payload = {"sentiment": "NEUTRAL", "red_flags": [], "distress_tier": []}
    monkeypatch.setattr(sub, "get_client", lambda: _poll_client("CHK-b", payload))

    out_path = tmp_path / "plain_poll.parquet"
    sub.run_poll("msgbatch_X", out_path=str(out_path), max_wait_s=1,
                 variant="v12_relabel")

    assert out_path.exists()
    assert open(target, "rb").read() == before
    assert not os.path.exists(target + sub.COMPLETION_BACKUP_SUFFIX)
