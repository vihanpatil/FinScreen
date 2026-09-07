"""P4: are the 779 EXPECTED_ABSENT rows really absent, or does the §2.2 conflation
defect leak into them? Seeded sample, replay extract.py's own locate path.
Cache-only, ZERO network."""
import sys, sqlite3, re, time, random
sys.path.insert(0, "/Users/vihanpatil/personal/projects/FinScreen")
import extract as E
import pandas as pd
from bs4 import BeautifulSoup

con = sqlite3.connect("file:/Users/vihanpatil/personal/projects/FinScreen/data/filings_metadata_e2.db?mode=ro", uri=True)
a = pd.read_parquet("data/f3/extraction_audit.parquet")
ea = a[a.extraction_status == "EXPECTED_ABSENT"].sort_values(["accession_number", "section_type"]).reset_index(drop=True)
rng = random.Random(20260828)
idx = sorted(rng.sample(range(len(ea)), 80))
s = ea.iloc[idx]
print("sampled", len(s), "of", len(ea), file=sys.stderr)

def rel(acc, fn, cik):
    r = con.execute("SELECT relative_path FROM filing_documents WHERE accession_number=? AND filename=?", (acc, fn)).fetchone()
    return r[0] if r and r[0] else f"/Archives/edgar/data/{int(cik)}/{acc.replace('-','')}/{fn}"

out = []; t0 = time.time()
for n, (_, r) in enumerate(s.iterrows()):
    try:
        html = E.strip_sgml_document_wrapper(E.read_cached_document(rel(r.accession_number, r.source_document, r.cik)))
        soup = BeautifulSoup(html, E._PARSER)
        toc = E.find_toc_item_anchors(soup)
    except Exception as ex:
        out.append(dict(acc=r.accession_number, company=r.company_name, cause="ERR_" + type(ex).__name__)); continue
    kws = ("risk factor",)
    matches = []
    for i, e in enumerate(toc):
        if e.item_no != "1A": continue
        rt = re.sub(r"\s+", "", e.row_text)
        if not any(re.sub(r"\s+", "", k) in rt for k in kws): continue
        matches.append((i, E.find_anchor_offset(html, e.anchor_id)))
    nres = sum(1 for _, o in matches if o is not None)
    if not matches:
        cause = "R1_genuinely_absent_from_toc"
    elif matches[0][1] is not None:
        cause = "R4_first_resolves_but_span_failed"
    elif nres > 0:
        cause = "R2_first_dangling_later_resolves"
    else:
        cause = "R3_all_dangling"
    # would the shipped heading-regex fallback find anything?
    full = E._LazyFullText(html)
    span = E.locate_item_section_by_heading_regex(full.get(), "10-Q", "RISK_FACTORS")
    fb = None
    if span:
        fb = len(full.get()[span[0]:span[1]].strip().split())
    out.append(dict(acc=r.accession_number, company=r.company_name, filing_date=r.filing_date,
                    n_toc=len(toc), n_matching=len(matches), n_resolvable=nres, cause=cause, fallback_words=fb))
    if n % 20 == 0: print(f"  {n} {time.time()-t0:.0f}s", file=sys.stderr)

d = pd.DataFrame(out)
d.to_csv("data/f3/p4_redteam/expected_absent_sample.csv", index=False)
print(d.cause.value_counts().to_string())
print("\nrows where a matching Item 1A TOC entry EXISTS:", int((d.n_matching > 0).sum()), "/", len(d))
print(d[d.n_matching > 0][["company","acc","filing_date","n_matching","n_resolvable","cause","fallback_words"]].to_string(index=False))
