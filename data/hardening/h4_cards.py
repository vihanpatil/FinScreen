"""H4 -- render one evidence card per sampled selection, from CACHED bytes only.
Zero network. Uses extract.py's own text pipeline so what I read is what F3 sees."""
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # data/hardening/<this file> -> repo root
sys.path.insert(0, str(ROOT))
from extract import html_fragment_to_text, strip_sgml_document_wrapper  # noqa: E402

SCRATCH = Path("/private/tmp/claude-501/-Users-vihanpatil-personal-projects-FinScreen/"
               "56426783-64ca-4155-8fbf-a11a57913516/scratchpad")
man = json.loads((SCRATCH / "h4_manifest.json").read_text())
conn = sqlite3.connect(f"file:{ROOT/'data/filings_metadata_e2.db'}?mode=ro", uri=True)

DOCS = ROOT / "data/raw/documents"
SKIP_TYPES = re.compile(r"^(EX-101|EX-104|XML|GRAPHIC|EXCEL|ZIP|JSON)", re.I)

MARKERS = {
    "results-headline": r"(?i)\b(reports?|announce[sd]?|report(?:ed|ing)?)\b[^.\n]{0,60}"
                        r"\b(first|second|third|fourth|full[- ]year|quarter|fiscal|q[1-4]|annual)\b",
    "EPS": r"(?i)(earnings per (?:diluted |basic |common )?share|\bEPS\b|per diluted share)",
    "revenue": r"(?i)\b(net sales|total revenue|revenues?|net revenue)\b",
    "guidance": r"(?i)(outlook|guidance|expects? .{0,30}(full[- ]year|fiscal))",
    "GAAP-recon": r"(?i)(non-?GAAP|reconciliation of)",
    "cover-page": r"(?i)(check the appropriate box below|registrant'?s telephone number|"
                  r"securities registered pursuant to section 12\(b\))",
    "furnished-elsewhere": r"(?i)(attached (hereto )?as exhibit|furnished as exhibit|"
                           r"is attached to this (current )?report)",
    "deck": r"(?i)(safe harbor statement|forward-looking statements.{0,40}slide|"
            r"conference call|webcast|slide \d)",
    "supplemental": r"(?i)(supplemental (financial |operating )?information|"
                    r"supplemental (report|package))",
}


def card(row, body_chars, head_chars):
    acc = row["accession_number"]
    sibs = conn.execute(
        "SELECT seq, doc_type, description, filename FROM filing_documents "
        "WHERE accession_number=? ORDER BY CASE WHEN seq IS NULL THEN 999 ELSE seq END", (acc,)
    ).fetchall()
    lines = []
    A = lines.append
    A(f"===== {acc} | CIK {row['cik']} {row['company_name']} "
      f"({row['sector']}/{row['stratum']}) | filed {row['filing_date']} "
      f"| tiers={','.join(row['tiers'])}")
    A(f"  items={row['items']!r} report_date={row['report_date']} "
      f"accepted={row['acceptance_datetime']}")
    A(f"  SELECTED: {row['earnings_doc_filename']}  [{row['section_type']}/{row['confidence']}]")
    A("  INDEX (document-format rows):")
    for seq, dt, desc, fn in sibs:
        if dt and SKIP_TYPES.match(dt or ""):
            continue
        if fn and fn.endswith(".txt") and (desc or "").lower().startswith("complete submission"):
            continue
        mark = " <== SELECTED" if fn == row["earnings_doc_filename"] else ""
        A(f"    seq={seq} type={dt!r} desc={desc!r} file={fn!r}{mark}")

    p = DOCS / row["earnings_doc_relative_path"].lstrip("/").replace("/", "_")
    raw = p.read_bytes().decode("utf-8", errors="replace")
    text = html_fragment_to_text(strip_sgml_document_wrapper(raw))
    nimg = len(re.findall(r"(?i)<img\b", raw))
    A(f"  BYTES={len(raw)} TEXTCHARS={len(text)} WORDS={len(text.split())} IMGTAGS={nimg}")
    hits = [k for k, pat in MARKERS.items() if re.search(pat, text[:60000])]
    A(f"  MARKERS: {', '.join(hits) if hits else '(none)'}")
    A("  ---- TEXT HEAD ----")
    A(text[:head_chars] if text else "(NO EXTRACTABLE TEXT)")
    if len(text) > head_chars and body_chars:
        mid = len(text) // 2
        A(f"  ---- TEXT MID (offset {mid}) ----")
        A(text[mid:mid + body_chars])
    A("")
    return "\n".join(lines)


if __name__ == "__main__":
    which = sys.argv[1]
    lo, hi = int(sys.argv[2]), int(sys.argv[3])
    head = int(sys.argv[4]) if len(sys.argv) > 4 else 1400
    body = int(sys.argv[5]) if len(sys.argv) > 5 else 500
    accs = set(man[f"{which}_acc"]) if which != "all" else None
    rows = [r for r in man["rows"] if accs is None or r["accession_number"] in accs]
    rows.sort(key=lambda r: r["accession_number"])
    for r in rows[lo:hi]:
        print(card(r, body, head))
