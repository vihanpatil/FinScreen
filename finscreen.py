#!/usr/bin/env python3
"""finscreen.py -- one front door for the existing CLIs. Personal use only.

    bin/fs doctor                       environment checks (no network)
    bin/fs report SIRI [--open]         ingest -> fundamentals -> label -> HTML pages
    bin/fs g3 --date D --owner-word W   pin G3 + run head 1 and heads 2/3 (owner's word only)
    bin/fs index                        list the per-company stores

It only chains ingest_one.py, label_filing.py, report_filing.py, data/f5/pin_g3.py,
backtest_e2.py and heads_e2.py as subprocesses under this interpreter; every rule
(adapter sha, repro canary, G3 guard) stays inside those modules.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent
COMPANIES = REPO / "data" / "app" / "companies"
REPORTS = REPO / "data" / "app" / "reports"
F5 = REPO / "data" / "f5"
RATIFIED = F5 / "G3_RATIFIED.json"
CHAIN_LOG = F5 / "status" / "g3_chain_log.jsonl"
MLX_PYTHON = REPO / "finetune" / ".mlx_venv" / "bin" / "python"
ADAPTER = (REPO / "finetune" / "checkpoints" / "qwen2.5-7b-finscreen-lora-mlx-v12-epoch2"
           / "adapters.safetensors")
CAMPAIGN_MANIFEST = REPO / "data" / "f4" / "campaign_manifest.json"
DATA_FILES = [REPO / "data" / "filings_e2_v2.parquet", REPO / "data" / "f4" / "labels_e2_v1.parquet"]
LABELERS = "label_filing|label_e2"
BUSY = LABELERS + "|ingest_one"
CIK_RE = re.compile(r"\(CIK (\d+)\)")
PAGE_RE = re.compile(r"^(.+\.html)\s+\([\d.]+s\)\s*$")


def py(script, *args):
    return [sys.executable, str(REPO / script), *map(str, args)]


def rel(path):
    try:
        return path.relative_to(REPO)
    except ValueError:
        return path


def run(cmd, capture=False, timeout=None):
    """Print the command, run it in REPO, print its wall-clock seconds."""
    print("$ " + " ".join(cmd), flush=True)
    t = time.time()
    proc = subprocess.run(cmd, cwd=REPO, text=True, timeout=timeout,
                          stdout=subprocess.PIPE if capture else None)
    if capture and proc.stdout:
        print(proc.stdout, end="" if proc.stdout.endswith("\n") else "\n")
    print(f"  -> exit {proc.returncode} in {time.time() - t:.1f}s", flush=True)
    return proc


def alive(pattern):
    """`pgrep -fl` lines of live processes matching pattern ([] if none)."""
    proc = subprocess.run(["pgrep", "-fl", pattern], capture_output=True, text=True)
    return [l for l in (proc.stdout or "").splitlines() if l.strip()]


def parse_cik(text):
    m = CIK_RE.search(text or "")
    return int(m.group(1)) if m else None


def manifests():
    for path in sorted(COMPANIES.glob("*/manifest.json")):
        yield path.parent, json.loads(path.read_text())


def find_store(ticker):
    hits = [(d, m) for d, m in manifests() if str(m.get("ticker", "")).upper() == ticker.upper()]
    if len(hits) > 1:
        raise SystemExit(f"ticker {ticker} has {len(hits)} stores: {[str(d) for d, _ in hits]}")
    return hits[0] if hits else (None, None)


def labels_fresh(store):
    """labels.parquet exists AND was written from the store's current chunks.parquet."""
    lab, man = store / "labels.parquet", store / "label_manifest.json"
    if not (lab.exists() and man.exists()):
        return False
    chunks_sha = json.loads((store / "manifest.json").read_text()).get("chunks", {}).get("sha256")
    label_sha = json.loads(man.read_text()).get("prepare", {}).get("chunks_parquet_sha256")
    return bool(chunks_sha) and chunks_sha == label_sha


# ---------------------------------------------------------------------------
def cmd_report(a):
    busy = alive(LABELERS)
    if busy:
        print("REFUSED: a labeling process is alive; never run two:\n  " + "\n  ".join(busy))
        return 2
    store, man = find_store(a.ticker)
    if store is not None and man.get("window", {}).get("per_form") == a.per_form:
        print(f"ingest: store {store} already has per_form={a.per_form}; skipped")
    else:
        proc = run(py("ingest_one.py", "--ticker", a.ticker, "--per-form", a.per_form), capture=True)
        if proc.returncode:
            return proc.returncode
        cik = parse_cik(proc.stdout)
        store = COMPANIES / str(cik) if cik else find_store(a.ticker)[0]
        if store is None or not (store / "manifest.json").exists():
            print(f"FAILED: ingest_one ran but no store for {a.ticker} was found")
            return 1
    proc = run(py("ingest_one.py", "--ticker", a.ticker, "--fundamentals"), capture=True)
    if proc.returncode:
        return proc.returncode
    if a.skip_label:
        print("label: --skip-label given; skipped")
    elif labels_fresh(store):
        print(f"label: {store / 'labels.parquet'} matches the current chunks; skipped")
    else:
        proc = run(py("label_filing.py", "--store", rel(store)))
        if proc.returncode:
            return proc.returncode
    pages, missing = [], []
    for extra in (["--index"], ["--latest", "10-K"], ["--latest", "10-Q"], ["--latest", "8-K"]):
        proc = run(py("report_filing.py", "--store", rel(store), *extra), capture=True)
        found = [m.group(1) for m in map(PAGE_RE.match, (proc.stdout or "").splitlines()) if m]
        if proc.returncode == 0 and found:
            pages += found
        elif extra == ["--index"]:
            print("FAILED: the index page did not render")
            return proc.returncode or 1
        else:
            missing.append(extra[1])
    print("\npages written:\n  " + "\n  ".join(pages))
    for form in missing:
        print(f"  {form}: no page")
    if a.open:
        subprocess.run(["open", pages[0]], cwd=REPO)
    return 0


def cmd_g3(a):
    if a.owner_word != "ratify":
        print("REFUSED: --owner-word must be exactly 'ratify' (the owner's own word). Nothing ran.")
        return 2
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", a.date):
        print(f"REFUSED: --date must be YYYY-MM-DD, got {a.date!r}. Nothing ran.")
        return 2
    if RATIFIED.exists():
        print(f"REFUSED: {RATIFIED} exists -- already pinned; run the heads directly.")
        return 2
    CHAIN_LOG.parent.mkdir(parents=True, exist_ok=True)
    steps = [("pin_show", py("data/f5/pin_g3.py", "--show", "--date", a.date)),
             ("pin", py("data/f5/pin_g3.py", "--pin", "--owner-word", "ratify", "--date", a.date)),
             ("head1", py("backtest_e2.py")),
             ("heads23", py("heads_e2.py", "--all"))]
    for step, cmd in steps:
        started, t = datetime.now(timezone.utc).isoformat(), time.time()
        proc = run(cmd, capture=step == "pin_show")
        if step == "pin_show":
            (CHAIN_LOG.parent / f"PIN_SHOW_{a.date}.txt").write_text(proc.stdout or "")
        with CHAIN_LOG.open("a") as fh:
            fh.write(json.dumps({"step": step, "cmd": cmd, "started": started,
                                 "seconds": round(time.time() - t, 1), "exit": proc.returncode}) + "\n")
        if proc.returncode:
            print(f"STOPPED at {step} (exit {proc.returncode}); log: {CHAIN_LOG}")
            return proc.returncode
    print(f"\nexpected outputs:\n  {F5 / 'head1_scorecard.md'}\n  {F5 / 'run_log.jsonl'}\n  {CHAIN_LOG}")
    return 0


def cmd_index(a):
    print(f"{'ticker':<8}{'cik':<10}{'chunks':>7}  {'labeled':<8}{'pages':>5}  name")
    for store, m in manifests():
        rep = REPORTS / store.name
        n = len(list(rep.glob("*.html"))) if rep.is_dir() else 0
        idx = " +index" if (rep / "index.html").exists() else ""
        print(f"{m.get('ticker', '?'):<8}{store.name:<10}{m.get('chunks', {}).get('n_chunks', 0):>7}  "
              f"{'yes' if (store / 'labels.parquet').exists() else 'no':<8}{n:>5}  "
              f"{m.get('company_name', '?')}{idx}")
    return 0


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def cmd_doctor(a):
    rows = []
    add = lambda status, check, detail="": rows.append((status, check, detail))
    add("INFO", "interpreter", f"{sys.executable} ({sys.version.split()[0]})")
    for mod in ("pandas", "pyarrow", "xgboost"):
        try:
            add("PASS", f"import {mod}", __import__(mod).__version__)
        except Exception as exc:
            add("FAIL", f"import {mod}", repr(exc))
    if not MLX_PYTHON.exists():
        add("FAIL", "mlx venv", f"{MLX_PYTHON} missing")
    else:
        try:
            p = subprocess.run([str(MLX_PYTHON), "-c", "import mlx_lm"], capture_output=True,
                               text=True, timeout=120)
            add("PASS" if p.returncode == 0 else "FAIL", "mlx venv: import mlx_lm",
                str(MLX_PYTHON) if p.returncode == 0 else (p.stderr or "").strip()[-200:])
        except subprocess.TimeoutExpired:
            add("FAIL", "mlx venv: import mlx_lm", "timed out after 120s")
    expected = json.loads(CAMPAIGN_MANIFEST.read_text()).get("inputs", {}).get("adapter_sha256_expected") \
        if CAMPAIGN_MANIFEST.exists() else None
    if not ADAPTER.exists() or not expected:
        add("FAIL", "adapter sha256", f"adapter exists={ADAPTER.exists()}, expected sha={expected}")
    else:
        got = sha256(ADAPTER)
        add("PASS" if got == expected else "FAIL", "adapter sha256",
            f"{got[:12]}... {'==' if got == expected else '!='} campaign {expected[:12]}...")
    for path in DATA_FILES:
        add("PASS" if path.exists() else "FAIL", "data file", str(rel(path)))
    add("INFO", "G3_RATIFIED.json", "present (pinned)" if RATIFIED.exists() else "absent (not pinned)")
    add("INFO", "EODHD_API_TOKEN", "set" if os.environ.get("EODHD_API_TOKEN") else "not set")
    free = shutil.disk_usage(REPO).free / 1e9
    add("PASS" if free >= 30 else "WARN", "free disk", f"{free:.0f} GB")
    busy = alive(BUSY)
    add("WARN" if busy else "PASS", "no label/ingest process alive", "; ".join(busy))
    for status, check, detail in rows:
        print(f"{status:<5} {check:<32} {detail}")
    return 1 if any(r[0] == "FAIL" for r in rows) else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    sub.add_parser("index").set_defaults(fn=cmd_index)
    r = sub.add_parser("report")
    r.add_argument("ticker")
    r.add_argument("--per-form", type=int, default=2)
    r.add_argument("--open", action="store_true")
    r.add_argument("--skip-label", action="store_true")
    r.set_defaults(fn=cmd_report)
    g = sub.add_parser("g3")
    g.add_argument("--date", required=True)
    g.add_argument("--owner-word", required=True)
    g.set_defaults(fn=cmd_g3)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
