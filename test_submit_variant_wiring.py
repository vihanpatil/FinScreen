"""
test_submit_variant_wiring.py — regression tests for the 2026-08-11
run_full() variant-wiring bug and the guards that prevent recurrence.

Rewritten 2026-08-18 against the v2 `--verify-config` heuristic: the four
tests in the last section encoded heuristic v1 and failed after the
verifier was reworked; they were replaced rather than deleted, so the
file now collects 25 tests and all of them pass. (HANDOFF.md §4 records
the correction; LIMITATIONS.md §5 no longer lists an open failure here.)

HARD CONSTRAINT: no network, no real client, no .env/API key touched.
Every test that would otherwise call get_client()/batches.create() stubs
the client via monkeypatching submit_labeling_batch.get_client.

Run with: python3 -m pytest test_submit_variant_wiring.py -v
"""
from __future__ import annotations

import json

import pytest

import submit_labeling_batch as sub
from build_batch_requests import VARIANTS


# ---------------------------------------------------------------------
# Fake client — records what it was asked to submit, never touches the
# network. Used to assert run_full() etc. load/submit the RIGHT file
# without actually calling batches.create() against a real API.
# ---------------------------------------------------------------------
class _FakeBatch:
    def __init__(self, batch_id="msgbatch_FAKE000000000000000000000"):
        self.id = batch_id
        self.created_at = "2026-08-11T00:00:00Z"
        self.processing_status = "in_progress"


class _FakeBatchesResource:
    def __init__(self):
        self.create_calls = []  # list of kwargs passed to create()

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return _FakeBatch()


class _FakeMessagesResource:
    def __init__(self):
        self.batches = _FakeBatchesResource()


class _FakeClient:
    def __init__(self):
        self.messages = _FakeMessagesResource()


def _req(custom_id, max_tokens, thinking="ABSENT", effort="ABSENT"):
    params = {"max_tokens": max_tokens}
    if thinking != "ABSENT":
        params["thinking"] = thinking
    if effort != "ABSENT":
        params["output_config"] = {"effort": effort}
    return {"custom_id": custom_id, "params": params}


def _write_jsonl(path, requests):
    with open(path, "w") as f:
        for r in requests:
            f.write(json.dumps(r) + "\n")


# ---------------------------------------------------------------------
# GROUP 1 regression: run_full() must honor the variant/requests_file it
# is given, not silently fall back to the module-default requests file.
# (This is the 2026-08-11 incident itself -- HANDOFF.md §4.)
# ---------------------------------------------------------------------
def test_run_full_honors_variant_and_requests_file(tmp_path, monkeypatch):
    # Build a "disabled" (max_tokens=800, thinking=disabled) requests file
    # at a NON-default path, distinct from REQUESTS_JSONL_PATH's default
    # ("data/batch_requests.jsonl", which — pre-fix — is what the buggy
    # run_full() always loaded regardless of what was asked for).
    correct_file = tmp_path / "batch_requests_disabled_test.jsonl"
    _write_jsonl(
        correct_file,
        [_req(f"c{i}", 800, thinking={"type": "disabled"}) for i in range(5)],
    )

    fake_client = _FakeClient()
    monkeypatch.setattr(sub, "get_client", lambda: fake_client)

    meta_path = tmp_path / "full_batch_meta_test.json"
    sub.run_full(variant="disabled", requests_file=str(correct_file), meta_path=str(meta_path))

    # The fake client must have been asked to submit exactly the 5
    # requests from `correct_file` — proof run_full() actually loaded the
    # file it was given, not some hardcoded default.
    assert len(fake_client.messages.batches.create_calls) == 1
    submitted = fake_client.messages.batches.create_calls[0]["requests"]
    assert len(submitted) == 5
    assert {r["custom_id"] for r in submitted} == {f"c{i}" for i in range(5)}

    meta = json.loads(meta_path.read_text())
    assert meta["variant"] == "disabled"
    assert meta["requests_file"] == str(correct_file)
    assert meta["n_submitted"] == 5


def test_run_full_pre_fix_signature_would_have_ignored_requests_file(monkeypatch):
    """This test documents/pins the bug signature itself: the OLD buggy
    run_full() took no variant/requests_file arguments at all, so calling
    it the way the fixed CLI now does (with keyword args) must raise a
    TypeError against that old signature. That incompatibility is the
    regression signal: this file fails against the old buggy run_full()
    precisely because the old function cannot accept the fixed call site.
    """
    import inspect

    sig = inspect.signature(sub.run_full)
    # Fixed signature must accept variant + requests_file explicitly.
    assert "variant" in sig.parameters
    assert "requests_file" in sig.parameters
    # And neither may carry a default that silently reintroduces the old
    # hardcoded-default-file bug.
    assert sig.parameters["variant"].default is inspect._empty
    assert sig.parameters["requests_file"].default is inspect._empty


# ---------------------------------------------------------------------
# GROUP 2 regression: the guard itself.
# ---------------------------------------------------------------------
def test_guard_accepts_matching_requests():
    requests = [_req(f"c{i}", 800, thinking={"type": "disabled"}) for i in range(10)]
    # Should not raise.
    sub.assert_requests_match_variant(requests, "disabled", "fake_path.jsonl")


def test_guard_rejects_fully_mismatched_requests():
    # All requests at max_tokens=500, no thinking key (the actual bug:
    # old default file's real shape) claimed as "disabled" (800/disabled).
    requests = [_req(f"c{i}", 500) for i in range(10)]
    with pytest.raises(sub.VariantMismatchError, match="REFUSING TO SUBMIT"):
        sub.assert_requests_match_variant(requests, "disabled", "fake_path.jsonl")


def test_guard_rejects_partially_mismatched_requests():
    """A mixed-config file (some requests correct, some not) must be
    rejected too — the guard must check EVERY request, not just the
    first."""
    requests = [_req(f"c{i}", 800, thinking={"type": "disabled"}) for i in range(9)]
    requests.append(_req("bad_one", 500))  # only the last one is wrong
    with pytest.raises(sub.VariantMismatchError) as exc_info:
        sub.assert_requests_match_variant(requests, "disabled", "fake_path.jsonl")
    assert "1/10" in str(exc_info.value)
    assert "bad_one" in str(exc_info.value)


def test_guard_treats_absent_thinking_as_adaptive_and_rejects_for_disabled_variant():
    """The exact original-bug shape: max_tokens matches by coincidence
    but the `thinking` key is simply ABSENT from the request (adaptive
    default), which must NOT be silently read as `thinking=disabled`."""
    requests = [_req(f"c{i}", 800) for i in range(5)]  # no thinking key at all
    with pytest.raises(sub.VariantMismatchError, match="REFUSING TO SUBMIT"):
        sub.assert_requests_match_variant(requests, "disabled", "fake_path.jsonl")


def test_guard_rejects_unknown_variant():
    requests = [_req("c0", 800, thinking={"type": "disabled"})]
    with pytest.raises(sub.VariantMismatchError, match="Unknown variant"):
        sub.assert_requests_match_variant(requests, "not-a-real-variant", "fake_path.jsonl")


def test_guard_rejects_empty_requests_list():
    with pytest.raises(sub.VariantMismatchError, match="empty"):
        sub.assert_requests_match_variant([], "disabled", "fake_path.jsonl")


# ---------------------------------------------------------------------
# Guard vs. the real, already-built request files (paired with their
# correct variant) — proves the guard actually passes real data, not
# just synthetic fixtures. Skips gracefully if a given file isn't
# present in this checkout (read-only, no network either way).
# ---------------------------------------------------------------------
REAL_FILE_VARIANT_PAIRS = [
    ("data/batch_requests_disabled.jsonl", "disabled"),
    ("data/batch_requests_adaptive_low.jsonl", "adaptive-low"),
    ("data/batch_requests_corrective.jsonl", "disabled-4000"),
    ("data/batch_requests_relabel.jsonl", "disabled-4000"),
]


@pytest.mark.parametrize("path,variant", REAL_FILE_VARIANT_PAIRS)
def test_guard_passes_real_request_files_paired_with_correct_variant(path, variant):
    import os

    if not os.path.exists(path):
        pytest.skip(f"{path} not present in this checkout")
    requests = list(sub.load_requests_by_custom_id(path=path).values())
    # Should not raise for the whole file.
    sub.assert_requests_match_variant(requests, variant, path)


# ---------------------------------------------------------------------
# GROUP 3: --full-relabel wiring (own meta/labels paths, gated on
# --confirm-full, never touches labels.parquet/full_batch_meta.json).
# ---------------------------------------------------------------------
def test_run_full_relabel_writes_only_its_own_meta_path(tmp_path, monkeypatch):
    relabel_file = tmp_path / "batch_requests_relabel_test.jsonl"
    _write_jsonl(
        relabel_file,
        [_req(f"r{i}", 4000, thinking={"type": "disabled"}) for i in range(3)],
    )
    relabel_meta = tmp_path / "relabel_meta_test.json"

    fake_client = _FakeClient()
    monkeypatch.setattr(sub, "get_client", lambda: fake_client)
    monkeypatch.setattr(sub, "RELABEL_REQUESTS_PATH", str(relabel_file))
    monkeypatch.setattr(sub, "RELABEL_META_PATH", str(relabel_meta))

    sub.run_full_relabel()

    meta = json.loads(relabel_meta.read_text())
    assert meta["mode"] == "full-relabel"
    assert meta["variant"] == "disabled-4000"
    assert meta["n_submitted"] == 3
    # Distinct from the full/corrective paths.
    assert relabel_meta != sub.FULL_LABELS_PATH
    assert str(relabel_meta) != sub.CORRECTIVE_META_PATH


def test_full_relabel_cli_requires_confirm_full(monkeypatch, capsys):
    monkeypatch.setattr(sub.sys, "argv", ["submit_labeling_batch.py", "--full-relabel"])
    with pytest.raises(SystemExit) as exc_info:
        sub.main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "confirm-full" in captured.err


# ---------------------------------------------------------------------
# GROUP 4: post-submission verification helper.
#
# NOTE ON HEURISTIC VERSIONS (tests updated 2026-08-18).
# The four tests in this section originally encoded heuristic **v1**,
# whose bug signature was simply `observed_max_output_tokens <
# intended_max_tokens`. v1 was deliberately replaced by **v2** on
# 2026-08-11 (see the block comment in verify_batch_config()) because v1
# flagged *every healthy run* as SUSPECT_WRONG_CONFIG — the 4,219-request
# re-label ran a median of 47 output tokens against a 4,000 cap and was
# falsely flagged. HANDOFF §4 row 2: "a verifier that cries wolf on every
# healthy run is worse than no verifier."
#
# v2 keys on the actual truncation rate (`stop_reason == "max_tokens"`),
# which is the incident's real signature (2,537/6,747 = 37.6% truncated,
# all piled at exactly 500). `ceiling_below_intended` survives in the
# report as *informational only* and must never again drive a verdict.
#
# The v1 tests were never updated when the heuristic was, so they had been
# failing ever since. They are rewritten below against v2 — no assertion
# was loosened: the must-flag case still must flag, the must-pass case
# still must pass, and the new cases pin the anti-cry-wolf behaviour and
# the threshold so neither can be silently relaxed.
# ---------------------------------------------------------------------
def _rec(output_tokens, stop_reason="end_turn"):
    """One reduced result record in the shape run_verify_config() builds
    from a real SDK result item (output_tokens + message-level
    stop_reason)."""
    return {"output_tokens": output_tokens, "stop_reason": stop_reason}


def test_verify_config_flags_real_incident_truncation_signature():
    """The original bug's real observable signature: requests actually
    submitted against max_tokens=500 while the variant claimed is
    'disabled' (intended 800), so a large fraction of results stop on
    max_tokens piled at exactly the 500 ceiling."""
    records = (
        [_rec(500, "max_tokens") for _ in range(4)]
        + [_rec(t) for t in [120, 250, 480, 310]]
    )
    report = sub.verify_batch_config(records, "disabled")
    assert report["verdict"] == "SUSPECT_WRONG_CONFIG"
    assert report["observed_max_output_tokens"] == 500
    assert report["intended_max_tokens"] == 800
    assert report["n_at_observed_ceiling"] == 4
    assert report["n_truncated"] == 4
    # ceiling_below_intended is still reported, but only as context.
    assert report["ceiling_below_intended"] is True
    assert "max_tokens" in report["message"]


def test_verify_config_flags_ceiling_below_intended_corrective_scale():
    """Same signature at corrective scale: observed max=500 when 4000 was
    intended (disabled-4000 / corrective variant), with the results at
    that ceiling truncated rather than finishing naturally."""
    records = [_rec(500, "max_tokens") for _ in range(3)] + [_rec(400), _rec(320)]
    report = sub.verify_batch_config(records, "disabled-4000")
    assert report["verdict"] == "SUSPECT_WRONG_CONFIG"
    assert report["observed_max_output_tokens"] == 500
    assert report["intended_max_tokens"] == 4000
    assert report["n_at_observed_ceiling"] == 3
    assert report["n_truncated"] == 3


def test_verify_config_passes_healthy_case():
    """Healthy case: responses finish on their own under the cap, so
    nothing is truncated — no wrong-config signature."""
    records = [_rec(t) for t in [120, 250, 640, 800, 300, 410, 800]]
    report = sub.verify_batch_config(records, "disabled")
    assert report["verdict"] == "OK"
    assert report["ceiling_below_intended"] is False
    assert report["observed_max_output_tokens"] == 800
    assert report["n_at_observed_ceiling"] == 2
    assert report["n_truncated"] == 0


def test_verify_config_does_not_cry_wolf_on_healthy_relabel_profile():
    """Regression test for the v1 false positive (HANDOFF §4 row 2): the
    real 'disabled-4000' re-label profile — a ceiling far below the
    4,000 cap, median tens of tokens, zero truncation — is HEALTHY and
    must not be flagged. v1 flagged exactly this case, which is why it
    was replaced."""
    records = [_rec(t) for t in [31, 44, 47, 47, 52, 61, 88, 143, 260]]
    report = sub.verify_batch_config(records, "disabled-4000")
    assert report["verdict"] == "OK"
    assert report["verdict"] != "SUSPECT_WRONG_CONFIG"
    # A low ceiling is reported but must NOT drive the verdict.
    assert report["ceiling_below_intended"] is True
    assert report["observed_max_output_tokens"] == 260
    assert report["truncation_rate"] == 0.0


def test_verify_config_truncation_threshold_is_pinned_at_one_percent():
    """Pins the >1% truncation bar in both directions so it cannot be
    quietly loosened (too lax = the incident slips through) or tightened
    back toward v1's cry-wolf behaviour (too strict = ignored verifier)."""
    # Exactly 1/100 = 1.0% truncation — at the bar, not over it: OK.
    at_bar = [_rec(800, "max_tokens")] + [_rec(120) for _ in range(99)]
    assert sub.verify_batch_config(at_bar, "disabled")["verdict"] == "OK"
    # 2/100 = 2.0% — over the bar: flagged.
    over_bar = [_rec(800, "max_tokens") for _ in range(2)] + [
        _rec(120) for _ in range(98)
    ]
    over = sub.verify_batch_config(over_bar, "disabled")
    assert over["verdict"] == "SUSPECT_WRONG_CONFIG"
    assert over["truncation_rate"] == 0.02


def test_verify_config_without_stop_reasons_is_inconclusive_never_ok():
    """Records carrying no stop_reason cannot be judged: truncation is
    unmeasurable. The verifier must say so — and must never hand out a
    clean 'OK' (nor a SUSPECT verdict inferred from the ceiling alone,
    which is what v1 did) on evidence it does not have."""
    records = [{"output_tokens": t} for t in [500, 500, 500, 400, 320]]
    report = sub.verify_batch_config(records, "disabled-4000")
    assert report["verdict"] == "INCONCLUSIVE"
    assert report["verdict"] not in ("OK", "SUSPECT_WRONG_CONFIG")
    assert "stop_reason" in report["message"]


def test_verify_config_no_results():
    report = sub.verify_batch_config([], "disabled")
    assert report["verdict"] == "NO_RESULTS"


def test_verify_config_unknown_variant_raises():
    with pytest.raises(sub.VariantMismatchError, match="Unknown variant"):
        sub.verify_batch_config([{"output_tokens": 10}], "not-a-real-variant")


def test_verify_config_is_pure_and_touches_no_client():
    """verify_batch_config() must be a pure function over already-fetched
    records — it may never construct a client or reach the network."""
    calls = []

    def _boom():
        calls.append("get_client")
        raise AssertionError("verify_batch_config must not build a client")

    original = sub.get_client
    sub.get_client = _boom
    try:
        sub.verify_batch_config([_rec(120)], "disabled")
    finally:
        sub.get_client = original
    assert calls == []


# ---------------------------------------------------------------------
# run_verify_config(): the read-only CLI path.
#
# The doubles below mirror the REAL SDK result shape that
# run_verify_config() reads: item.result.type / .message.usage
# .output_tokens / .message.stop_reason. The pre-2026-08-18 version of
# _FakeMessage carried no stop_reason, so every reduced record came back
# with stop_reason=None and the run could only ever be INCONCLUSIVE —
# test-double drift, not a defect in the verifier.
# ---------------------------------------------------------------------
class _FakeUsage:
    def __init__(self, output_tokens):
        self.output_tokens = output_tokens


class _FakeMessage:
    def __init__(self, output_tokens, stop_reason):
        self.usage = _FakeUsage(output_tokens)
        self.stop_reason = stop_reason


class _FakeSucceededResult:
    def __init__(self, output_tokens, stop_reason):
        self.type = "succeeded"
        self.message = _FakeMessage(output_tokens, stop_reason)


class _FakeErroredResult:
    """Errored results carry no usage — run_verify_config must skip them
    rather than counting them toward the truncation rate."""

    def __init__(self):
        self.type = "errored"


class _FakeResultItem:
    def __init__(self, result):
        self.result = result


def _fake_client_with_results(pairs, include_errored=False):
    """pairs: list of (output_tokens, stop_reason)."""
    items = [_FakeResultItem(_FakeSucceededResult(t, s)) for t, s in pairs]
    if include_errored:
        items.append(_FakeResultItem(_FakeErroredResult()))

    class _FakeBatchesResourceWithResults(_FakeBatchesResource):
        def results(self, batch_id):
            return list(items)

    fake_client = _FakeClient()
    fake_client.messages.batches = _FakeBatchesResourceWithResults()
    return fake_client


def test_run_verify_config_never_calls_batches_create(monkeypatch, capsys):
    """--verify-config is a READ-only path: it must call
    batches.results(), never batches.create() — i.e. it cannot possibly
    submit anything even if invoked. Fed the incident's truncation
    signature, it must also report SUSPECT_WRONG_CONFIG."""
    fake_client = _fake_client_with_results(
        [(500, "max_tokens"), (500, "max_tokens"), (320, "end_turn")],
        include_errored=True,
    )
    monkeypatch.setattr(sub, "get_client", lambda: fake_client)

    sub.run_verify_config("msgbatch_FAKE", "disabled")

    assert fake_client.messages.batches.create_calls == []
    captured = capsys.readouterr()
    assert "SUSPECT_WRONG_CONFIG" in captured.out
    report = json.loads(captured.out)
    # The errored result is skipped, not counted as a healthy completion.
    assert report["n_results"] == 3
    assert report["n_truncated"] == 2


def test_run_verify_config_healthy_batch_reports_ok_and_submits_nothing(
    monkeypatch, capsys
):
    """The CLI-level half of the anti-cry-wolf guarantee: a healthy batch
    whose ceiling sits far below the cap reports OK, and still nothing is
    ever submitted."""
    fake_client = _fake_client_with_results(
        [(47, "end_turn"), (52, "end_turn"), (260, "end_turn")]
    )
    monkeypatch.setattr(sub, "get_client", lambda: fake_client)

    sub.run_verify_config("msgbatch_FAKE", "disabled-4000")

    assert fake_client.messages.batches.create_calls == []
    captured = capsys.readouterr()
    assert "SUSPECT_WRONG_CONFIG" not in captured.out
    assert "SUSPECT_WRONG_CONFIG" not in captured.err
    report = json.loads(captured.out)
    assert report["verdict"] == "OK"
