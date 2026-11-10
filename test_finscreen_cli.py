"""Offline tests for finscreen.py: subprocess.run is faked, paths point at tmp_path."""
import hashlib
import json
import re
import shutil
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


# --- landing page (2026-11-09) ------------------------------------------------
def _rendered(paths, cik, ticker, name, scorecard=False):
    store = make_store(paths, cik=cik, ticker=ticker)
    man = json.loads((store / "manifest.json").read_text())
    (store / "manifest.json").write_text(json.dumps(dict(man, company_name=name)))
    rep = paths / "reports" / str(cik)
    rep.mkdir(parents=True)
    (rep / "index.html").write_text("x")
    (rep / "0000000000-26-000001.html").write_text("x")
    if scorecard:
        (rep / "scorecard.html").write_text("hit rate 0.7143 [0.5294, 0.8475] 71.43%")


def test_landing_page_is_alphabetical_by_ticker_with_scorecard_links_only_when_present(paths):
    _rendered(paths, 320193, "AAPL", "Apple Inc.", scorecard=True)
    _rendered(paths, 908937, "SIRI", "Sirius XM")
    _rendered(paths, 1018724, "AMZN", "Amazon")
    make_store(paths, cik=5, ticker="NOPG")  # a store with no rendered pages is not listed
    html = fs.write_landing().read_text()
    assert html.index("AAPL") < html.index("AMZN") < html.index("SIRI")
    assert "NOPG" not in html
    assert html.count(fs.SCORECARD_LINK) == 1
    assert 'href="320193/scorecard.html"' in html and 'href="908937/scorecard.html"' not in html
    assert 'href="908937/index.html">labeled filings</a>' in html
    assert fs.LANDING_IDENTITY in html.replace("&quot;", '"').replace("&#x27;", "'")
    assert "Rendered for the author&#x27;s personal use only" in html
    body = html.split("<body>")[1]
    for number in ("0.7143", "71.43%", "0.5294"):
        assert number not in body, "no scorecard number on the landing page"


def _with_fundamentals(paths, cik=320193, ticker="AAPL", days=364, scale=1.0):
    """A rendered store with the four store tables (existence is all the panel checks) and two
    years of Revenues + NetIncomeLoss covering `days` each (364 = a fiscal year, 90 = a quarter),
    the newest ending 60 days ago so none is stale."""
    import pandas as pd
    _rendered(paths, cik, ticker, f"{ticker} Inc.")
    store = paths / "companies" / str(cik)
    for name in ("chunks.parquet", "labels.parquet", "sections.parquet", "metadata.db"):
        (store / name).write_bytes(b"")
    end = pd.Timestamp.utcnow().tz_localize(None).normalize() - pd.Timedelta(days=60)
    rows = []
    for years_back, revenue, income in ((1, 100e6 * scale, 20e6), (0, 110e6 * scale, 22e6)):
        e = end - pd.DateOffset(years=years_back)
        for concept, value in (("Revenues", revenue), ("NetIncomeLoss", income)):
            rows.append(dict(ticker=ticker, cik=cik, taxonomy="us-gaap", concept=concept, unit="USD",
                             value=value, fy=float(e.year), fp="FY",
                             period_start=str((e - pd.Timedelta(days=days)).date()),
                             period_end=str(e.date()), form="10-K",
                             accession_number=f"0000000000-{e.year % 100}-000001",
                             filed=str((e + pd.Timedelta(days=30)).date())))
    pd.DataFrame(rows).to_parquet(store / "fundamentals.parquet", index=False)
    man = json.loads((store / "manifest.json").read_text())
    man["filings"] = [{"accession_number": "0000000000-26-000001", "form": "10-K", "filing_date": "2026-02-10"},
                      {"accession_number": "0000000000-26-000009", "form": "8-K", "filing_date": "2026-01-05"}]
    (store / "manifest.json").write_text(json.dumps(man))
    (store / "concept_resolution.csv").write_text(
        "cik,family,state,tags,severity\n"
        f"{cik},revenue,SINGLE,Revenues,resolved\n{cik},net_income,SINGLE,NetIncomeLoss,resolved\n")
    return end


def test_landing_page_shows_point_in_time_fundamentals_yoy_and_margin(paths):
    end = _with_fundamentals(paths)
    html = fs.write_landing().read_text()
    assert fs.SORT_JS in html
    assert "older than 200 days" in html  # NF.F1.STALENESS_MAX_DAYS, formatted in
    row = html.split("<tbody>")[1].split("</tr>")[0]
    assert '<td data-v="110000000.0" data-g="12">110.00 m USD' in row  # raw value and span in months
    assert row.count('<td data-v="">—</td>') == 3  # blanks sort last
    assert "110.00 m USD" in row and "22.00 m USD" in row
    assert ">+10.0%<" in row, "revenue YoY = 110 / 100 - 1"
    assert ">20.0%<" in row, "net margin = 22 / 110"
    assert f"12 months ending {end.date()}" in row
    assert '<a href="320193/0000000000-26-000001.html">10-K 2026-02-10</a>' in row
    assert row.count(">—<") == 3  # operating cash flow, assets, equity: no row in the resolution


def test_landing_page_sorts_flow_columns_by_span_before_amount(paths):
    """A year is never ranked against a quarter: the flow cells carry their span in months as
    data-g, and the page's own comparator (run in node when present) groups by it first."""
    _with_fundamentals(paths, cik=1, ticker="YEAR", days=364)
    _with_fundamentals(paths, cik=2, ticker="BIGQ", days=90, scale=5.0)   # 550 m quarter
    _with_fundamentals(paths, cik=3, ticker="SMLQ", days=90, scale=0.5)   # 55 m quarter
    html = fs.write_landing().read_text()
    assert "so those columns sort by span first, then by amount" in html
    rows = re.findall(r"<tr>(.*?)</tr>", html.split("<tbody>")[1])
    revenue = {re.search(r"<td>(\w+)</td>", r).group(1): re.findall(r"<td ([^>]*)>", r)[1] for r in rows}
    assert 'data-g="12"' in revenue["YEAR"] and 'data-g="3"' in revenue["BIGQ"]
    node = shutil.which("node")
    if node is None:
        return  # comparator: equal-or-missing data-g falls through to data-v, so grouping holds
    cells = [[dict(d=dict(re.findall(r'data-(\w)="([^"]*)"', attrs)), t=re.sub(r"<[^>]+>", "", text))
              for attrs, text in re.findall(r"<td([^>]*)>(.*?)</td>", r)] for r in rows]
    script = ("const document = {querySelectorAll: () => []};"
        + html.split("<script>")[1].split("</script>")[0]
        + f"const rows = {json.dumps(cells)}.map(r => ({{cells: r.map(c => ({{dataset: c.d, textContent: c.t}}))}}));"
        + 'console.log(rows.sort(cmp(3, "-1")).map(r => r.cells[0].textContent).join(" "));')
    out = subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout
    assert out.split() == ["YEAR", "BIGQ", "SMLQ"]  # by raw value it would be BIGQ, YEAR, SMLQ


def test_landing_page_survives_a_store_whose_panel_raises(paths, monkeypatch, capsys):
    import report_filing as RF
    _with_fundamentals(paths)

    def boom(cik, as_of):
        raise RuntimeError("broken store")
    monkeypatch.setattr(RF, "fundamentals_panel", boom)
    row = fs.write_landing().read_text().split("<tbody>")[1].split("</tr>")[0]
    assert "AAPL" in row and row.count(">—<") == 7  # every number; the filing link stays
    assert "broken store" in capsys.readouterr().err
    assert RF.ACTIVE_STORE is None


def test_open_writes_the_landing_page_and_opens_it(paths, monkeypatch, capsys):
    _rendered(paths, 908937, "SIRI", "Sirius XM")
    fake = FakeRun()
    monkeypatch.setattr(fs.subprocess, "run", fake)
    assert fs.main(["open"]) == 0
    out = paths / "reports" / "index.html"
    assert fake.calls == [["open", str(out)]] and "SIRI" in out.read_text()
    assert str(out) in capsys.readouterr().out


def test_index_writes_the_landing_page(paths, capsys):
    _rendered(paths, 908937, "SIRI", "Sirius XM")
    assert fs.main(["index"]) == 0
    assert (paths / "reports" / "index.html").exists()
    assert "landing page:" in capsys.readouterr().out


def test_report_refreshes_the_landing_page(paths, monkeypatch):
    make_store(paths, per_form=2, labeled=True)
    monkeypatch.setattr(fs.subprocess, "run", FakeRun(report_respond))
    assert fs.main(["report", "SIRI"]) == 0
    assert (paths / "reports" / "index.html").exists()


def test_scorecard_runs_the_page_writer(paths, monkeypatch):
    fake = FakeRun()
    monkeypatch.setattr(fs.subprocess, "run", fake)
    assert fs.main(["scorecard", "--cik", "320193"]) == 0
    assert fake.scripts() == ["scorecard_page.py --cik 320193"]
    assert (paths / "reports" / "index.html").exists()
