"""Corpus-scale, zero-GET census for the F3 spec:
  (a) population-gate trigger volume over ALL 10,567 earnings selections
      (multi-cell condition + text-signature variants),
  (b) 8K_BODY item-2.02 prefix census over all 210,
  (c) earnings-document word-count distribution (floors recalibration input).
Reads only data/raw/documents/ and the read-only E2 DB."""
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path("/Users/vihanpatil/personal/projects/FinScreen")
sys.path.insert(0, str(ROOT))
from extract import html_fragment_to_text, strip_sgml_document_wrapper  # noqa: E402

DOCS = ROOT / "data/raw/documents"

ANN = ("today reported", "today announced", "announced today", "for immediate release",
       "announced results", "reports first", "reports second", "reports third",
       "reports fourth", "reports results", "announces first", "announces second",
       "announces third", "announces fourth")
H4 = ("today reported", "announced results", "per diluted share", "quarterly results")
V3 = ANN + ("per diluted share",)

ITEM202_RE = re.compile(r"item\s*2\.02", re.IGNORECASE)

con = sqlite3.connect(f"file:{ROOT}/data/filings_metadata_e2.db?mode=ro", uri=True)
rows = con.execute("""
  SELECT f.accession_number, f.cik, c.company_name, c.sector, c.stratum, f.filing_date,
         f.report_date, f.items, f.earnings_doc_section_type, f.earnings_doc_selection_confidence,
         f.earnings_doc_filename, f.earnings_doc_relative_path
  FROM filings f JOIN companies c ON c.cik = f.cik
  WHERE f.earnings_doc_filename IS NOT NULL
  ORDER BY f.accession_number
""").fetchall()
con.close()
print("selections:", len(rows))


def qtr(d):
    y, m = int(d[:4]), int(d[5:7])
    return f"{y}Q{(m - 1) // 3 + 1}"


cells = {}
for r in rows:
    cells[(r[1], qtr(r[5]))] = cells.get((r[1], qtr(r[5])), 0) + 1

out = []
t0 = time.time()
for i, r in enumerate(rows):
    (acc, cik, name, sector, stratum, fdate, rdate, items, sect, conf, fn, rel) = r
    rel = rel or f"/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{fn}"
    p = DOCS / rel.lstrip("/").replace("/", "_")
    raw = p.read_bytes().decode("utf-8", "replace")
    txt = html_fragment_to_text(strip_sgml_document_wrapper(raw))
    low = re.sub(r"\s+", " ", txt.lower())
    m202 = ITEM202_RE.search(txt)
    out.append({
        "acc": acc, "cik": cik, "name": name, "sector": sector, "stratum": stratum,
        "filing_date": fdate, "quarter": qtr(fdate), "cell": cells[(cik, qtr(fdate))],
        "section_type": sect, "conf": conf, "items": items,
        "chars": len(txt), "words": len(txt.split()),
        "sig_h4": any(m in low for m in H4),
        "sig_ann": any(m in low for m in ANN),
        "sig_v3": any(m in low for m in V3),
        "item202_off": m202.start() if m202 else -1,
        "n_item202": len(ITEM202_RE.findall(txt)),
    })
    if (i + 1) % 1000 == 0:
        print(f"  {i+1}/{len(rows)}  {time.time()-t0:.0f}s", flush=True)

d = pd.DataFrame(out)
d.to_parquet(Path(__file__).parent / "gate_corpus.parquet", index=False)
print(f"done in {time.time()-t0:.0f}s -> gate_corpus.parquet")
