"""Diagnose the top FAIL clusters by reading the cached primary document.

Read-only, cache-only (extract.read_cached_document raises CacheMiss, never fetches).
Usage: python3 p3_diagnose_fails.py <accession> [<accession> ...]
"""
import sys, re, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import extract as E

DB = ROOT / "data/filings_metadata_e2.db"


def load(acc):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    row = con.execute(
        "SELECT cik, form, filing_date, primary_document, company_name "
        "FROM filings f LEFT JOIN companies c USING(cik) WHERE accession_number=?",
        (acc,)).fetchone()
    con.close()
    return row


def rel_path(cik, acc, primary):
    return f"/Archives/edgar/data/{cik}/{acc.replace('-','')}/{primary}"


def diag(acc, show_toc=25, show_heads=True):
    cik, form, fd, primary, name = load(acc)
    raw = E.read_cached_document(rel_path(cik, acc, primary))
    body = E.strip_sgml_document_wrapper(raw)
    soup = E.BeautifulSoup(body, "html.parser")
    anchors = E.find_toc_item_anchors(soup)
    text = E.html_fragment_to_text(body)
    print(f"\n===== {acc} | {name} | {form} | {fd} | {primary} =====")
    print(f"raw {len(raw):,}ch  body {len(body):,}ch  text {len(text):,}ch  words {len(text.split()):,}")
    print(f"TOC anchors found: {len(anchors)} -> {sorted(anchors)[:show_toc]}")
    # what item-ish lines exist in the plain text
    if show_heads:
        pat = re.compile(r"^\s*(?:PART\s+[IVX]+[\s.,:\-]*)?ITEM\s*[0-9]+\s*[A-Z]?\s*[.:\-–—)]?.{0,80}$",
                         re.I | re.M)
        hits = [m.group(0).strip() for m in pat.finditer(text)]
        seen, uniq = set(), []
        for h in hits:
            k = h.lower()[:60]
            if k not in seen:
                seen.add(k); uniq.append(h)
        print(f"item-shaped lines in text: {len(hits)} ({len(uniq)} distinct)")
        for h in uniq[:30]:
            print("   |", h[:110])
    return text, soup, anchors


if __name__ == "__main__":
    for acc in sys.argv[1:]:
        try:
            diag(acc)
        except Exception as exc:
            print(f"!! {acc}: {type(exc).__name__}: {exc}")
