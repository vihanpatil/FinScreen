"""P3: exact recovery census over ALL 784 periodic FAIL rows.

For each FAIL row, replay extract.py's own locate path on the cached document
and record WHY it returned None, distinguishing three causes that the shipped
audit conflates into one reason_code:

  R1 no TOC entry matches (item_no + required_keyword)      -> truly absent
  R2 a matching entry exists but the FIRST one's anchor id
     is never DEFINED in the html (dangling href), and the
     code breaks at the first match instead of trying the
     next identical entry                                    -> first-anchor-wins defect
  R3 every matching entry's anchor is dangling               -> no resolvable anchor

plus, for every row, whether each candidate fallback WOULD have located it:

  C_cur   the shipped heading-regex fallback
  C_dash  same, with dash/paren added to the label-title gap
  C_wide  same, with a wider gap that tolerates a line-broken title

Nothing in extract.py is modified. This is a measurement harness.
Read-only, cache-only, zero network.
"""
import sys, re, sqlite3, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import pandas as pd
import extract as E

OUT = ROOT / "data/f3/p3_qa"
DB = ROOT / "data/filings_metadata_e2.db"

TARGET = {("10-K", "MDA"): "7", ("10-K", "RISK_FACTORS"): "1A",
          ("10-Q", "MDA"): "2", ("10-Q", "RISK_FACTORS"): "1A"}
KW = {"MDA": ("discussion and analysis",), "RISK_FACTORS": ("risk factor",)}
TITLE = {"MDA": r"management.{0,4}s\s+discussion", "RISK_FACTORS": r"risk\s+factors"}


def _pat(item_no, kw, gap):
    return re.compile(rf"item\s*{re.escape(item_no)}\.?{gap}{{0,20}}{kw}", re.I)


def _pat_wide(item_no, kw):
    # tolerate a line-broken / punctuated title within 60 chars
    return re.compile(rf"item\s*{re.escape(item_no)}\b.{{0,60}}?{kw}", re.I | re.S)


def analyse(html, soup, text, form, section):
    tgt, kws = TARGET[(form, section)], KW[section]
    toc = E.find_toc_item_anchors(soup)
    matching = [e for e in toc
                if e.item_no == tgt
                and any(re.sub(r"\s+", "", k) in re.sub(r"\s+", "", e.row_text) for k in kws)]
    offsets = [E.find_anchor_offset(html, e.anchor_id) for e in matching]
    n_res = sum(o is not None for o in offsets)
    if not matching:
        cause = "R1_no_matching_toc_entry"
    elif offsets[0] is None and n_res > 0:
        cause = "R2_first_anchor_dangling_later_resolvable"
    elif n_res == 0:
        cause = "R3_all_anchors_dangling"
    else:
        cause = "R4_other_span_failure"

    t = TITLE[section]
    cur = _pat(tgt, t, r"[\s\xa0.:]")
    dash = _pat(tgt, t, r"[\s\xa0.:\-–—‐−|)(]")
    wide = _pat_wide(tgt, t)
    return dict(n_toc=len(toc), n_matching=len(matching), n_resolvable=n_res,
                cause=cause,
                c_cur=len(cur.findall(text)), c_dash=len(dash.findall(text)),
                c_wide=len(wide.findall(text)),
                bare_title=len(re.findall(rf"(?im)^\s*{t}[^\n]{{0,80}}$", text)),
                doc_words=len(text.split()))


def main():
    a = pd.read_parquet(ROOT / "data/f3/extraction_audit.parquet",
                        columns=["cik", "company_name", "sector", "stratum",
                                 "accession_number", "form", "filing_date",
                                 "section_type", "extraction_status", "reason_code"])
    f = a[(a.extraction_status == "FAIL") & (a.form != "8-K")].copy()
    print("periodic FAIL rows:", len(f), "distinct accessions:", f.accession_number.nunique())

    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    meta = dict((r[0], (r[1], r[2])) for r in con.execute(
        "SELECT accession_number, cik, primary_document FROM filings").fetchall())
    con.close()

    by_acc = {}
    for r in f.itertuples(index=False):
        by_acc.setdefault(r.accession_number, []).append(r)

    rows, t0 = [], time.time()
    for i, (acc, rs) in enumerate(sorted(by_acc.items()), 1):
        cik, primary = meta[acc]
        rel = f"/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{primary}"
        try:
            html = E.strip_sgml_document_wrapper(E.read_cached_document(rel))
            soup = E.BeautifulSoup(html, "html.parser")
            text = E.html_fragment_to_text(html)
        except Exception as exc:
            for r in rs:
                rows.append({**r._asdict(), "cause": f"ERR {type(exc).__name__}"})
            continue
        for r in rs:
            try:
                rows.append({**r._asdict(), **analyse(html, soup, text, r.form, r.section_type)})
            except Exception as exc:
                rows.append({**r._asdict(), "cause": f"ERR {type(exc).__name__}: {exc}"})
        del html, soup, text
        if i % 50 == 0:
            print(f"  {i}/{len(by_acc)} docs {time.time()-t0:.0f}s", flush=True)

    d = pd.DataFrame(rows)
    d.to_csv(OUT / "fail_recovery.csv", index=False)
    print("wrote", OUT / "fail_recovery.csv", len(d), f"{time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
