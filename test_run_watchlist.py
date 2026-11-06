"""data/app/run_watchlist.sh (--refresh) and its launchd agent. Offline; `bin/fs` is a stub."""
import os
import plistlib
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import finscreen as fs

REPO = Path(__file__).resolve().parent
SCRIPT = REPO / "data/app/run_watchlist.sh"
PLIST = REPO / "data/app/launchd/com.finscreen.watchlist-refresh.plist"


@pytest.fixture
def tree(tmp_path):
    """A minimal repo layout: the script, a stub bin/fs, a two-ticker watchlist."""
    (tmp_path / "data/app/status").mkdir(parents=True)
    shutil.copy(SCRIPT, tmp_path / "data/app/run_watchlist.sh")
    (tmp_path / "data/app/watchlist.txt").write_text("# comment\nAAA\n\nBBB\n")
    fs = tmp_path / "bin/fs"
    fs.parent.mkdir()
    fs.write_text('#!/bin/bash\necho "stub fs $*"\nexit 0\n')
    fs.chmod(0o755)
    return tmp_path


def run(tree, *args):
    env = dict(os.environ, FS_SKIP_PROCESS_GUARD="1")  # the real chain may be alive
    return subprocess.run(["bash", "data/app/run_watchlist.sh", *args], cwd=tree, env=env,
                          capture_output=True, text=True, timeout=60)


def ledger(tree):
    rows = (tree / "data/app/status/WATCHLIST_DONE.tsv").read_text().splitlines()
    return [r.split("\t") for r in rows]


def test_refresh_archives_ledger_and_reruns_every_ticker(tree):
    old = "AAA\t0\t5\t2026-11-01T00:00:00Z\nBBB\t0\t5\t2026-11-01T00:00:00Z\n"
    (tree / "data/app/status/WATCHLIST_DONE.tsv").write_text(old)
    p = run(tree, "--refresh")
    assert p.returncode == 0, p.stdout + p.stderr
    archived = list((tree / "data/app/status/archive").glob("WATCHLIST_DONE_*.tsv"))
    assert len(archived) == 1 and archived[0].read_text() == old
    assert [(r[0], r[1]) for r in ledger(tree)] == [("AAA", "0"), ("BBB", "0")]
    log = (tree / "data/app/status/WATCHLIST_BUILD.log").read_text()
    assert "refresh: archived previous ledger to" in log
    # refresh mode passes --refresh through, so bin/fs re-ingests (review finding 1)
    assert "stub fs report AAA --refresh" in log and "stub fs report BBB --refresh" in log


def test_refresh_with_empty_ledger_archives_nothing(tree):
    p = run(tree, "--refresh")
    assert p.returncode == 0, p.stdout + p.stderr
    assert not (tree / "data/app/status/archive").exists()
    assert [r[0] for r in ledger(tree)] == ["AAA", "BBB"]


def test_plain_run_skips_done_tickers(tree):
    (tree / "data/app/status/WATCHLIST_DONE.tsv").write_text("AAA\t0\t5\t2026-11-01T00:00:00Z\n")
    p = run(tree)
    assert p.returncode == 0, p.stdout + p.stderr
    log = (tree / "data/app/status/WATCHLIST_BUILD.log").read_text()
    assert "AAA already done; skipped" in log and "stub fs report AAA" not in log
    assert "stub fs report BBB" in log and "refresh:" not in log
    assert "--refresh" not in log
    assert not (tree / "data/app/status/archive").exists()
    assert [(r[0], r[1]) for r in ledger(tree)] == [("AAA", "0"), ("BBB", "0")]


def test_missing_bin_fs_refuses_with_logged_line(tree):
    (tree / "bin/fs").unlink()
    p = run(tree, "--refresh")
    assert p.returncode == 2
    assert "REFUSED: bin/fs missing" in (tree / "data/app/status/WATCHLIST_BUILD.log").read_text()


# Review finding 11: two chains (a launchd run landing on a manual one) could each start a
# labeler between the other's tickers. A lock directory makes the second refuse.
def test_a_held_lock_refuses_and_runs_no_ticker(tree):
    lock = tree / "data/app/status/.chain.lock"
    lock.mkdir()
    (lock / "pid").write_text("4242\n")
    p = run(tree, "--refresh")
    assert p.returncode == 2
    log = (tree / "data/app/status/WATCHLIST_BUILD.log").read_text()
    assert "REFUSED: another chain holds" in log and "pid 4242" in log
    assert "stub fs report" not in log
    assert lock.is_dir() and (lock / "pid").read_text() == "4242\n"  # not ours to remove
    assert not (tree / "data/app/status/WATCHLIST_DONE.tsv").exists()


def test_the_lock_is_gone_after_a_normal_run(tree):
    p = run(tree)
    assert p.returncode == 0, p.stdout + p.stderr
    assert not (tree / "data/app/status/.chain.lock").exists()
    assert [r[0] for r in ledger(tree)] == ["AAA", "BBB"]


@pytest.mark.parametrize("args", [["--refesh"], ["refresh"], ["--refresh", "extra"]])
def test_an_unknown_argument_is_a_usage_error(tree, args):
    p = run(tree, *args)
    assert p.returncode == 2
    assert "usage: bash data/app/run_watchlist.sh [--refresh]" in p.stderr
    log = (tree / "data/app/status/WATCHLIST_BUILD.log").read_text()
    assert "stub fs report" not in log
    assert not (tree / "data/app/status/.chain.lock").exists()


def test_a_ticker_run_cannot_swallow_the_watchlist(tree):
    """bin/fs gets /dev/null as stdin, so a child reading stdin cannot eat the remaining
    tickers off the `while read` pipe (review note 16)."""
    (tree / "bin/fs").write_text('#!/bin/bash\ncat > /dev/null\necho "stub fs $*"\n')
    p = run(tree)
    assert p.returncode == 0, p.stdout + p.stderr
    assert [r[0] for r in ledger(tree)] == ["AAA", "BBB"]


def test_plist_lints_and_points_at_the_script():
    if shutil.which("plutil") is None:
        pytest.skip("plutil is macOS-only")
    p = subprocess.run(["plutil", "-lint", str(PLIST)], capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    with open(PLIST, "rb") as f:
        d = plistlib.load(f)
    prog = d["ProgramArguments"]
    # caffeinate holds a power assertion for the hours-long run (review finding 12)
    assert prog[:3] == ["/usr/bin/caffeinate", "-dims", "/bin/bash"]
    assert prog[4:] == ["--refresh"]
    assert Path(prog[3]).is_file() and Path(prog[3]).resolve() == SCRIPT.resolve()
    assert Path(d["WorkingDirectory"]).resolve() == REPO
    assert d["StartCalendarInterval"] == [{"Day": 1, "Hour": 3, "Minute": 0},
                                          {"Day": 15, "Hour": 3, "Minute": 0}]
    assert "RunAtLoad" not in d and "ProcessType" not in d  # no Background throttling


def test_script_guard_regex_is_finscreen_busy():
    """The chain's pgrep guard is the same interpreter-anchored regex as `bin/fs` (2026-11-06)."""
    m = re.search(r'pgrep -fl "([^"]+)"', SCRIPT.read_text())
    assert m and m.group(1) == fs.BUSY
