"""P4 independent replay of extract.py's anchor-locate path for named FAIL rows.
Cache-only: uses extract.read_cached_document (raises on miss). ZERO network."""
import sys, sqlite3, re
sys.path.insert(0, "/Users/vihanpatil/personal/projects/FinScreen")
import extract as E
from bs4 import BeautifulSoup

DB = "/Users/vihanpatil/personal/projects/FinScreen/data/filings_metadata_e2.db"

def doc_path(accession, source_document):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    r = con.execute(
        "SELECT relative_path FROM filing_documents WHERE accession_number=? AND filename=?",
        (accession, source_document)).fetchone()
    if r and r[0]:
        con.close(); return r[0]
    cik = con.execute("SELECT cik FROM filings WHERE accession_number=?", (accession,)).fetchone()[0]
    con.close()
    return f"/Archives/edgar/data/{int(cik)}/{accession.replace('-','')}/{source_document}"

def replay(accession, source_document, form, section):
    p = doc_path(accession, source_document)
    raw = E.read_cached_document(p)
    html = E.strip_sgml_document_wrapper(raw)
    soup = BeautifulSoup(html, "html.parser")
    toc = E.find_toc_item_anchors(soup)
    target = "7" if section == "MDA" and form == "10-K" else ("2" if section == "MDA" else "1A")
    kws = ("discussion and analysis",) if section == "MDA" else ("risk factor",)
    matches = []
    for i, e in enumerate(toc):
        if e.item_no != target:
            continue
        rt = re.sub(r"\s+", "", e.row_text)
        if not any(re.sub(r"\s+", "", k) in rt for k in kws):
            continue
        off = E.find_anchor_offset(html, e.anchor_id)
        matches.append((i, e.anchor_id, off))
    print(f"\n{accession} {form} {section}  [{source_document}]")
    print(f"  toc_entries={len(toc)}  matching={len(matches)}  resolvable={sum(1 for m in matches if m[2] is not None)}")
    for i, aid, off in matches:
        print(f"    idx={i:4d} anchor_id={aid!r:34s} defined_offset={off}")
    span = E.locate_item_section_by_anchor(html, toc, target, kws)
    print(f"  shipped locate_item_section_by_anchor -> {span}")
    return matches, span

if __name__ == "__main__":
    cases = [
        ("0000021344-18-000008", "a2017123110-k.htm", "10-K", "MDA"),
        ("0000021344-18-000008", "a2017123110-k.htm", "10-K", "RISK_FACTORS"),
        ("0000313616-16-000145", "dhr-20151231x10xk.htm", "10-K", "RISK_FACTORS"),
        ("0000313616-16-000145", "dhr-20151231x10xk.htm", "10-K", "MDA"),
        ("0000766704-15-000043", "10-Q.htm", "10-Q", "MDA"),
        ("0000008670-19-000005", "q2fy1910q.htm", "10-Q", "MDA"),
    ]
    for c in cases:
        try:
            replay(*c)
        except Exception as ex:
            print(f"{c[0]} {c[3]}: ERROR {type(ex).__name__}: {ex}")
