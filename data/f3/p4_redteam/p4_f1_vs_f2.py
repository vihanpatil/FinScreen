"""P4: does 'F2 alone recovers all 148' hold? For each R2/R3 row, compute what
F1 (use the resolvable later anchor) and F2 (fall through to heading regex)
would each return, and compare word counts to the anchor-located median for
that (form, section). Cache-only, ZERO network."""
import sys, sqlite3, re, random, time
sys.path.insert(0, "/Users/vihanpatil/personal/projects/FinScreen")
import extract as E
import pandas as pd
from bs4 import BeautifulSoup

DB = "/Users/vihanpatil/personal/projects/FinScreen/data/filings_metadata_e2.db"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)

fr = pd.read_csv("data/f3/p3_qa/fail_recovery.csv")
aud = pd.read_parquet("data/f3/extraction_audit.parquet",
                      columns=["accession_number","section_type","source_document","cik"])
fr = fr.merge(aud, on=["accession_number","section_type","cik"], how="left")
tgt = fr[fr.cause.isin(["R2_first_anchor_dangling_later_resolvable","R3_all_anchors_dangling"])].copy()
print("target rows", len(tgt), "docs", tgt.accession_number.nunique(), file=sys.stderr)

def rel_path(acc, fn, cik):
    r = con.execute("SELECT relative_path FROM filing_documents WHERE accession_number=? AND filename=?",
                    (acc, fn)).fetchone()
    if r and r[0]:
        return r[0]
    return f"/Archives/edgar/data/{int(cik)}/{acc.replace('-','')}/{fn}"

out = []
t0 = time.time()
for k, (acc, grp) in enumerate(tgt.groupby("accession_number")):
    fn = grp.source_document.iloc[0]; cik = grp.cik.iloc[0]
    try:
        html = E.strip_sgml_document_wrapper(E.read_cached_document(rel_path(acc, fn, cik)))
        soup = BeautifulSoup(html, E._PARSER)
        toc = E.find_toc_item_anchors(soup)
        full = E._LazyFullText(html)
    except Exception as ex:
        for _, r in grp.iterrows():
            out.append(dict(acc=acc, section=r.section_type, form=r.form, cause=r.cause,
                            err=f"{type(ex).__name__}"))
        continue
    for _, r in grp.iterrows():
        sec, form = r.section_type, r.form
        target = "7" if sec == "MDA" and form == "10-K" else ("2" if sec == "MDA" else "1A")
        kws = ("discussion and analysis",) if sec == "MDA" else ("risk factor",)
        # ---- F1: first matching entry whose anchor RESOLVES ----
        f1_words = None; f1_head = ""
        idxs = []
        for i, e in enumerate(toc):
            if e.item_no != target: continue
            rt = re.sub(r"\s+", "", e.row_text)
            if not any(re.sub(r"\s+", "", kw) in rt for kw in kws): continue
            idxs.append(i)
        for i in idxs:
            off = E.find_anchor_offset(html, toc[i].anchor_id)
            if off is None: continue
            start = E._end_of_enclosing_tag(html, off)
            end = len(html)
            for e2 in toc[i+1:]:
                if e2.item_no != target:
                    c = E.find_anchor_offset(html, e2.anchor_id, after=start)
                    if c is not None and c > start:
                        end = E._start_of_enclosing_tag(html, c)
                    break
            if end <= start: continue
            t = E.html_fragment_to_text(html[start:end])
            f1_words = len(t.split()); f1_head = " ".join(t.split()[:14])
            break
        # ---- F2: shipped heading-regex fallback on whole-doc plain text ----
        f2_words = None; f2_head = ""
        span = E.locate_item_section_by_heading_regex(full.get(), form, sec)
        if span is not None:
            t2 = full.get()[span[0]:span[1]].strip()
            f2_words = len(t2.split()); f2_head = " ".join(t2.split()[:14])
        out.append(dict(acc=acc, company=r.company_name, section=sec, form=form, cause=r.cause,
                        n_matching=r.n_matching, n_resolvable=r.n_resolvable,
                        f1_words=f1_words, f2_words=f2_words, f1_head=f1_head, f2_head=f2_head))
    if k % 20 == 0:
        print(f"  {k} docs {time.time()-t0:.0f}s", file=sys.stderr)

df = pd.DataFrame(out)
df.to_csv("data/f3/p4_redteam/f1_vs_f2.csv", index=False)
print("wrote", len(df), f"{time.time()-t0:.0f}s", file=sys.stderr)
