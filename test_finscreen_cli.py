"""Offline tests for finscreen.py: subprocess.run is faked, paths point at tmp_path."""
import hashlib
import json
import re
import subprocess

import pytest

import finscreen as fs


class FakeRun:
    """Records every command; returns (rc, stdout) chosen by `respond(cmd)`."""

    def __init__(self, respond=lambda cmd: (0, "")):
        self.calls, self.respond = [], respond

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        rc, out = self.respond(cmd)
        return subprocess.CompletedProcess(cmd, rc, stdout=out, stderr="")

    def scripts(self):  # "script.py --flags" for each call, interpreter dropped
        return [" ".join([c[1].rsplit("/", 1)[-1]] + c[2:]) for c in self.calls
                if c[0] not in ("pgrep", "open")]


@pytest.fixture
def paths(tmp_path, monkeypatch):
    monkeypatch.setattr(fs, "COMPANIES", tmp_path / "companies")
    monkeypatch.setattr(fs, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(fs, "RATIFIED", tmp_path / "G3_RATIFIED.json")
    monkeypatch.setattr(fs, "CHAIN_LOG", tmp_path / "status" / "g3_chain_log.jsonl")
    monkeypatch.setattr(fs, "alive", lambda pattern: [])
    return tmp_path


def make_store(root, cik=908937, ticker="SIRI", per_form=2, labeled=False):
    store = root / "companies" / str(cik)
    store.mkdir(parents=True)
    (store / "manifest.json").write_text(json.dumps(
        {"cik": cik, "ticker": ticker, "window": {"per_form": per_form},
         "chunks": {"sha256": "abc", "n_chunks": 5}}))
    if labeled:
        (store / "labels.parquet").write_bytes(b"x")
        (store / "label_manifest.json").write_text(
            json.dumps({"prepare": {"chunks_parquet_sha256": "abc"}}))
    return store


def test_parse_cik():
    line = "SIRIUS XM HOLDINGS INC. (CIK 908937) -> data/app/companies/908937"
    assert fs.parse_cik(line) == 908937
    assert fs.parse_cik("no cik here") is None


# --- g3 ---------------------------------------------------------------------
@pytest.mark.parametrize("word,date", [("Ratify", "2026-11-05"), ("ratify ", "2026-11-05"),
                                       ("ratify", "2026-11-5"), ("ratify", "today")])
def test_g3_refuses_bad_word_or_date(paths, monkeypatch, word, date):
    fake = FakeRun()
    monkeypatch.setattr(fs.subprocess, "run", fake)
    assert fs.main(["g3", "--date", date, "--owner-word", word]) == 2
    assert fake.calls == []


def test_g3_refuses_when_already_pinned(paths, monkeypatch):
    fs.RATIFIED.write_text("{}")
    fake = FakeRun()
    monkeypatch.setattr(fs.subprocess, "run", fake)
    assert fs.main(["g3", "--date", "2026-11-05", "--owner-word", "ratify"]) == 2
    assert fake.calls == []


def test_g3_runs_four_steps_in_order_and_logs(paths, monkeypatch):
    fake = FakeRun(lambda cmd: (0, "diff text\n"))
    monkeypatch.setattr(fs.subprocess, "run", fake)
    assert fs.main(["g3", "--date", "2026-11-05", "--owner-word", "ratify"]) == 0
    assert fake.scripts() == ["pin_g3.py --show --date 2026-11-05",
                              "pin_g3.py --pin --owner-word ratify --date 2026-11-05",
                              "backtest_e2.py", "heads_e2.py --all"]
    log = [json.loads(l) for l in fs.CHAIN_LOG.read_text().splitlines()]
    assert [r["step"] for r in log] == ["pin_show", "pin", "head1", "heads23"]
    assert (fs.CHAIN_LOG.parent / "PIN_SHOW_2026-11-05.txt").read_text() == "diff text\n"


def test_g3_stops_on_first_failure(paths, monkeypatch):
    fake = FakeRun(lambda cmd: (2, "") if "--pin" in cmd else (0, ""))
    monkeypatch.setattr(fs.subprocess, "run", fake)
    assert fs.main(["g3", "--date", "2026-11-05", "--owner-word", "ratify"]) == 2
    assert len(fake.scripts()) == 2


# --- report -----------------------------------------------------------------
def report_respond(cmd):
    if "ingest_one.py" in cmd[1]:
        return 0, "SIRIUS XM HOLDINGS INC. (CIK 908937) -> data/app/companies/908937\n"
    if "--latest" in cmd and cmd[-1] == "8-K":
        return 1, ""  # e.g. no earnings 8-K: tolerated
    if "report_filing.py" in cmd[1]:
        return 0, f"data/app/reports/908937/{cmd[-1]}.html  (0.4s)\n"
    return 0, ""


def test_report_full_chain_tolerates_failing_latest(paths, monkeypatch, capsys):
    fake = FakeRun(report_respond)
    make_store(paths, per_form=1)  # different per_form -> ingest re-runs
    monkeypatch.setattr(fs.subprocess, "run", fake)
    assert fs.main(["report", "SIRI"]) == 0
    s = fake.scripts()
    assert s[0] == "ingest_one.py --ticker SIRI --per-form 2"
    assert s[1] == "ingest_one.py --ticker SIRI --fundamentals"
    assert s[2].startswith("label_filing.py --store ")
    assert [x.split(" ", 3)[-1] for x in s[3:]] == ["--index", "--latest 10-K",
                                                    "--latest 10-Q", "--latest 8-K"]
    out = capsys.readouterr().out
    assert "data/app/reports/908937/10-Q.html" in out and "8-K: no page" in out


def test_report_skips_ingest_and_label_when_current(paths, monkeypatch):
    make_store(paths, per_form=2, labeled=True)
    fake = FakeRun(report_respond)
    monkeypatch.setattr(fs.subprocess, "run", fake)
    assert fs.main(["report", "siri", "--open"]) == 0
    s = fake.scripts()
    assert s[0] == "ingest_one.py --ticker siri --fundamentals"
    assert not any(x.startswith("label_filing") for x in s)
    assert fake.calls[-1][0] == "open" and fake.calls[-1][1].endswith("--index.html")


# Regression, 2026-11-05 review finding 1: `--refresh` must fetch new filings, i.e. run the
# per-form ingest even on a store that is already current; labeling still keys on the chunks sha.
def test_report_refresh_reingests_a_current_store(paths, monkeypatch):
    make_store(paths, per_form=2, labeled=True)
    fake = FakeRun(report_respond)
    monkeypatch.setattr(fs.subprocess, "run", fake)
    assert fs.main(["report", "SIRI", "--refresh"]) == 0
    s = fake.scripts()
    assert s[:2] == ["ingest_one.py --ticker SIRI --per-form 2",
                     "ingest_one.py --ticker SIRI --fundamentals"]
    assert not any(x.startswith("label_filing") for x in s)  # chunks sha unchanged


def test_report_relabels_when_labels_are_stale(paths, monkeypatch):
    store = make_store(paths, per_form=2, labeled=True)
    (store / "label_manifest.json").write_text(json.dumps({"prepare": {"chunks_parquet_sha256": "old"}}))
    fake = FakeRun(report_respond)
    monkeypatch.setattr(fs.subprocess, "run", fake)
    assert fs.main(["report", "SIRI"]) == 0
    assert any(x.startswith("label_filing") for x in fake.scripts())


def test_report_refuses_when_labeler_alive(paths, monkeypatch):
    monkeypatch.setattr(fs, "alive", lambda p: ["4242 python label_filing.py --store x"])
    fake = FakeRun()
    monkeypatch.setattr(fs.subprocess, "run", fake)
    assert fs.main(["report", "SIRI"]) == 2
    assert fake.calls == []


# Regression, 2026-11-06: an agent shell whose command line merely contained the guard's
# bare names made `report` refuse 18 watchlist tickers. Python's re agrees with pgrep's ERE
# on this pattern (verified live against macOS pgrep with a probe script).
@pytest.mark.parametrize("command, hit", [
    ("/x/MacOS/Python /repo/label_filing.py --store s", True),
    ("/repo/finetune/.mlx_venv/bin/python /repo/label_filing.py --store s --generate", True),
    ("caffeinate -dims /v/bin/python /repo/finetune/label_e2.py --segment 3", True),
    ("python3 ingest_one.py --ticker X", True),
    ('/bin/bash -c pgrep -fl "label_filing|label_e2|ingest_one"', False),
    ("vim test_label_filing.py", False),
    ("python3 -m pytest test_label_filing.py", False),
])
def test_busy_guard_matches_only_a_real_interpreter_invocation(command, hit):
    assert bool(re.search(fs.BUSY, command)) is hit
    assert bool(re.search(fs.LABELERS, command)) is (hit and "ingest_one" not in command)


# --- doctor -----------------------------------------------------------------
def test_doctor_fails_on_adapter_sha_mismatch(paths, monkeypatch, capsys):
    adapter = paths / "adapters.safetensors"
    adapter.write_bytes(b"weights")
    manifest = paths / "campaign_manifest.json"
    monkeypatch.setattr(fs, "ADAPTER", adapter)
    monkeypatch.setattr(fs, "CAMPAIGN_MANIFEST", manifest)
    monkeypatch.setattr(fs, "MLX_PYTHON", adapter)  # exists; the fake run says import works
    monkeypatch.setattr(fs, "DATA_FILES", [adapter])
    monkeypatch.setattr(fs.subprocess, "run", FakeRun())
    pytest.importorskip("xgboost")

    manifest.write_text(json.dumps({"inputs": {"adapter_sha256_expected": hashlib.sha256(b"weights").hexdigest()}}))
    assert fs.main(["doctor"]) == 0
    manifest.write_text(json.dumps({"inputs": {"adapter_sha256_expected": "cadca849" + "0" * 56}}))
    assert fs.main(["doctor"]) == 1
    assert "FAIL  adapter sha256" in capsys.readouterr().out
