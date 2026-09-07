"""8K_BODY item-2.02 slicing census over ALL 210 rows. Zero GETs."""
import re, sqlite3, sys, json
from pathlib import Path
import pandas as pd
ROOT = Path("/Users/vihanpatil/personal/projects/FinScreen")
sys.path.insert(0, str(ROOT))
from extract import html_fragment_to_text, strip_sgml_document_wrapper
DOCS = ROOT / "data/raw/documents"
con = sqlite3.connect(f"file:{ROOT}/data/filings_metadata_e2.db?mode=ro", uri=True)
rows = con.execute("""SELECT f.accession_number, f.cik, c.company_name, f.filing_date, f.items,
    f.earnings_doc_filename, f.earnings_doc_relative_path FROM filings f JOIN companies c ON c.cik=f.cik
    WHERE f.earnings_doc_section_type='8K_BODY' ORDER BY f.accession_number""").fetchall()
con.close()
ITEM = re.compile(r"item\s*(\d)\.(\d\d)", re.I)
out=[]
for acc, cik, name, fdate, items, fn, rel in rows:
    rel = rel or f"/Archives/edgar/data/{cik}/{acc.replace('-','')}/{fn}"
    raw=(DOCS/rel.lstrip('/').replace('/','_')).read_bytes().decode('utf-8','replace')
    txt = html_fragment_to_text(strip_sgml_document_wrapper(raw))
    ms=[(m.start(), m.group(1)+"."+m.group(2)) for m in ITEM.finditer(txt)]
    first202 = next((s for s,k in ms if k=="2.02"), -1)
    nxt = next((s for s,k in ms if s>first202 and k!="2.02"), -1) if first202>=0 else -1
    out.append(dict(acc=acc,cik=cik,name=name,filing_date=fdate,items=items,
        chars=len(txt),words=len(txt.split()),first202=first202,
        n202=sum(1 for _,k in ms if k=="2.02"), next_item=nxt,
        next_item_kind=next((k for s,k in ms if s>first202 and k!="2.02"), None) if first202>=0 else None,
        words_from_202=len(txt[first202:].split()) if first202>=0 else None,
        words_202_to_next=len(txt[first202:nxt].split()) if (first202>=0 and nxt>0) else None))
d=pd.DataFrame(out); d.to_parquet("body8k.parquet",index=False)
print("n=",len(d))
print("first202 missing:", (d.first202<0).sum())
print("prefix chars: ", d[d.first202>=0].first202.describe(percentiles=[.1,.5,.9]).round(0).to_dict())
print("prefix share of doc:", (d[d.first202>=0].first202/d[d.first202>=0].chars).describe(percentiles=[.1,.5,.9]).round(3).to_dict())
print("words total:", d.words.describe(percentiles=[.05,.5,.95]).round(0).to_dict())
print("words from 202:", d.words_from_202.describe(percentiles=[.05,.5,.95]).round(0).to_dict())
print("words 202->next item:", d.words_202_to_next.describe(percentiles=[.05,.5,.95]).round(0).to_dict())
print("next_item_kind counts:\n", d.next_item_kind.value_counts(dropna=False).head(10))
print("\nrows where slicing to next item leaves <200 words:", (d.words_202_to_next<200).sum())
print(d[d.words_202_to_next<200][["acc","name","words","words_from_202","words_202_to_next","next_item_kind"]].head(20).to_string())
print("\nrows with n202>1:", (d.n202>1).sum())
print("\ntop CIKs:\n", d.name.value_counts().head(8))
