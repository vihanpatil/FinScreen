"""Deep read helper: dump a wider slice of a selected doc + the cached index page's
own document table (richer descriptions than the DB row). Cache only, zero GETs."""
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # data/hardening/<this file> -> repo root
sys.path.insert(0, str(ROOT))
from extract import html_fragment_to_text, strip_sgml_document_wrapper  # noqa: E402

conn = sqlite3.connect(f"file:{ROOT/'data/filings_metadata_e2.db'}?mode=ro", uri=True)
IDX = ROOT / "data/raw/filing_index"
DOCS = ROOT / "data/raw/documents"

acc = sys.argv[1]
start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
n = int(sys.argv[3]) if len(sys.argv) > 3 else 4000
grep = sys.argv[4] if len(sys.argv) > 4 else None

cik, path, sel = conn.execute(
    "SELECT cik, earnings_doc_relative_path, earnings_doc_filename FROM filings "
    "WHERE accession_number=?", (acc,)).fetchone()

ipath = IDX / f"{cik}_{acc.replace('-','')}.html"
if ipath.exists():
    itxt = html_fragment_to_text(ipath.read_text(errors="replace"))
    print("---- CACHED INDEX PAGE (doc table region) ----")
    print(itxt[:3000])
    print("---- /INDEX ----\n")

raw = (DOCS / path.lstrip("/").replace("/", "_")).read_bytes().decode("utf-8", "replace")
text = html_fragment_to_text(strip_sgml_document_wrapper(raw))
print(f"[{acc}] SELECTED={sel} TEXTCHARS={len(text)} WORDS={len(text.split())}")
if grep:
    for m in re.finditer(grep, text, re.I):
        s = max(0, m.start() - 250)
        print(f"\n>>> match @{m.start()}: ...{text[s:m.start()+450]}...")
else:
    print(text[start:start + n])
