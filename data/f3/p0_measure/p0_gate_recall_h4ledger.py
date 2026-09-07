"""Re-measure the NARROWED text-signature population gate on H4's 155-row
ledger. Zero GETs: every document read from data/raw/documents/."""
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/Users/vihanpatil/personal/projects/FinScreen")
sys.path.insert(0, str(ROOT))
from extract import html_fragment_to_text, strip_sgml_document_wrapper  # noqa: E402

DOCS = ROOT / "data/raw/documents"
man = json.loads((ROOT / "data/hardening/h4_manifest.json").read_text())
BY_ACC = {r["accession_number"]: r for r in man["rows"]}
led = pd.read_csv(ROOT / "data/hardening/h4_verdict_ledger.csv")


def text_for(acc):
    rel = BY_ACC[acc]["earnings_doc_relative_path"]
    raw = (DOCS / rel.lstrip("/").replace("/", "_")).read_bytes().decode("utf-8", "replace")
    return html_fragment_to_text(strip_sgml_document_wrapper(raw))


# ---- candidate signature marker sets -------------------------------------
H4_PROPOSED = ("today reported", "announced results", "per diluted share",
               "quarterly results")
EXTRA = ("today announced", "announced today", "reported net income",
         "reported a net loss", "results of operations for",
         "financial results", "per share", "earnings per share",
         "net income of", "net loss of", "revenue of", "revenues of",
         "first quarter", "second quarter", "third quarter", "fourth quarter",
         "full year", "fiscal year", "reports first", "reports second",
         "reports third", "reports fourth", "reports results",
         "for immediate release", "press release", "announces first",
         "announces second", "announces third", "announces fourth",
         "diluted share", "compared with", "year-over-year", "quarter ended",
         "months ended", "adjusted eps", "operating income", "adjusted ebitda")

rows = []
for _, r in led.iterrows():
    acc = r["accession_number"]
    t = re.sub(r"\s+", " ", text_for(acc).lower())
    rec = {"acc": acc, "verdict": r["verdict"], "cell": r["quarter_cell_size"],
           "sect": r["section_type"], "conf": r["selection_confidence"],
           "cik": r["cik"], "name": r["company_name"], "words": len(t.split())}
    for m in H4_PROPOSED + EXTRA:
        rec["m::" + m] = m in t
    rows.append(rec)

d = pd.DataFrame(rows)
d["multi"] = d["cell"] > 1
d.to_json(Path(__file__).parent / "h4_gate_markers.json")

print("=== ledger composition ===")
print(pd.crosstab(d.verdict, d.multi))
print()

sig_h4 = d[["m::" + m for m in H4_PROPOSED]].any(axis=1)
d["sig_h4"] = sig_h4


def report(name, sig):
    flag = d["multi"] & ~sig
    c = d.verdict == "C"
    b = d.verdict == "B"
    a = d.verdict == "A"
    print(f"--- {name}")
    print(f"    recall on C  : {int((flag & c).sum())}/{int(c.sum())}")
    print(f"    flags total  : {int(flag.sum())}/155   (A {int((flag&a).sum())}/{int(a.sum())},"
          f" B {int((flag&b).sum())}/{int(b.sum())}, C {int((flag&c).sum())}/{int(c.sum())})")
    prec_c = (flag & c).sum() / max(flag.sum(), 1)
    prec_cb = (flag & (c | b)).sum() / max(flag.sum(), 1)
    print(f"    precision C  : {prec_c:.3f}   C-or-B: {prec_cb:.3f}")
    missed = d[c & ~flag]
    if len(missed):
        print("    MISSED C rows:")
        for _, m in missed.iterrows():
            hits = [k[5:] for k in d.columns if k.startswith("m::") and m[k]]
            print(f"      {m.acc} {m['name']} cell={m.cell} sig_hits={hits}")
    return flag


report("V0  multi-cell only (H4 measured 9/9)", pd.Series(False, index=d.index))
print()
report("V1  multi-cell AND lacks H4-proposed signature", sig_h4)
print()

print("=== per-marker hit rates by verdict (H4 proposed + extras) ===")
for m in H4_PROPOSED + EXTRA:
    col = "m::" + m
    a = d[d.verdict == "A"][col].mean()
    b = d[d.verdict == "B"][col].mean()
    c = d[d.verdict == "C"][col].mean()
    print(f"  {m:28s} A {a:5.2f}  B {b:5.2f}  C {c:5.2f}")
