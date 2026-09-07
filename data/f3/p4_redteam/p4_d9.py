"""P4: does D9 (widen the label->title gap char class to allow -/en-dash) produce
correct slices, or does the last-match rule ruin it too? Cache-only, ZERO network."""
import sys, sqlite3, re, time
sys.path.insert(0, "/Users/vihanpatil/personal/projects/FinScreen")
import extract as E
import pandas as pd
from bs4 import BeautifulSoup

con = sqlite3.connect("file:/Users/vihanpatil/personal/projects/FinScreen/data/filings_metadata_e2.db?mode=ro", uri=True)

def dash_pattern(item_no, keyword):
    return re.compile(rf"item\s*{re.escape(item_no)}\.?[\s\xa0.:\-‐-―]{{0,20}}{keyword}", re.IGNORECASE)

DASH = {}
for (form, sec), (sp, eps) in E.FALLBACK_SECTIONS.items():
    pass
SPECS = {
    ("10-K","MDA"): ("7", r"management.?s\s+discussion"),
    ("10-K","RISK_FACTORS"): ("1A", r"risk\s+factors"),
    ("10-Q","MDA"): ("2", r"management.?s\s+discussion"),
    ("10-Q","RISK_FACTORS"): ("1A", r"risk\s+factors"),
}

def locate_dash(text, form, sec):
    ino, kw = SPECS[(form, sec)]
    start_pat = dash_pattern(ino, kw)
    _, end_pats = E.FALLBACK_SECTIONS[(form, sec)]
    starts = list(start_pat.finditer(text))
    if not starts: return None
    for sm in reversed(starts):
        s_end = sm.end(); end_offset = len(text)
        for ep in end_pats:
            em = ep.search(text, s_end)
            if em and em.start() < end_offset: end_offset = em.start()
        if end_offset - s_end >= E.MIN_SECTION_CHARS:
            return sm.start(), end_offset
    return None

fr = pd.read_csv("data/f3/p3_qa/fail_recovery.csv")
aud = pd.read_parquet("data/f3/extraction_audit.parquet",
                      columns=["accession_number","section_type","source_document","cik"])
fr = fr.merge(aud, on=["accession_number","section_type","cik"], how="left")
d9 = fr[(fr.cause=="R1_no_matching_toc_entry") & (fr.c_cur==0) & (fr.c_dash>0)].copy()
print("D9 rows", len(d9), "docs", d9.accession_number.nunique(), file=sys.stderr)

def rel(acc, fn, cik):
    r = con.execute("SELECT relative_path FROM filing_documents WHERE accession_number=? AND filename=?", (acc, fn)).fetchone()
    return r[0] if r and r[0] else f"/Archives/edgar/data/{int(cik)}/{acc.replace('-','')}/{fn}"

out=[]; t0=time.time()
for acc, grp in d9.groupby("accession_number"):
    fn=grp.source_document.iloc[0]; cik=grp.cik.iloc[0]
    try:
        html=E.strip_sgml_document_wrapper(E.read_cached_document(rel(acc,fn,cik)))
        full=E._LazyFullText(html); txt=full.get()
    except Exception as ex:
        for _,r in grp.iterrows(): out.append(dict(acc=acc, company=r.company_name, form=r.form, section=r.section_type, err=str(type(ex).__name__)))
        continue
    for _,r in grp.iterrows():
        sp=locate_dash(txt, r.form, r.section_type)
        if sp is None:
            out.append(dict(acc=acc, company=r.company_name, form=r.form, section=r.section_type, d9_words=None, d9_head=""))
        else:
            t=txt[sp[0]:sp[1]].strip()
            out.append(dict(acc=acc, company=r.company_name, form=r.form, section=r.section_type,
                            d9_words=len(t.split()), d9_head=" ".join(t.split()[:14])))
pd.DataFrame(out).to_csv("data/f3/p4_redteam/d9_check.csv", index=False)
print("wrote", len(out), f"{time.time()-t0:.0f}s", file=sys.stderr)
