"""Full E1 regression: re-extract every one of E1's 884 frozen sections with
F3's extract.py and compare text byte-for-byte.

The corpus-scale version of test T14 (which pins 12 named rows). Result on the
shipped code: 880/884 byte-identical; the only 4 differences are the 8K_BODY
rows that R2's item-2.02 slicing legitimately changes (BAC, CVX x2, GS).
All 544 `anchor` rows and all 9 `incorporated_by_reference_resolved` stubs are
byte-identical. Output: e1_regression_884.csv. Zero GETs.
"""
import json, sys, time
sys.path.insert(0, "/Users/vihanpatil/personal/projects/FinScreen")
import pandas as pd, extract as E

e1 = pd.read_parquet("/Users/vihanpatil/personal/projects/FinScreen/data/filings.parquet")
read = lambda rel: E.read_cached_document(rel)
out = []
t0 = time.time()
# one parse per (accession, form) for periodic rows
cache = {}
for i, r in e1.iterrows():
    try:
        if r.form in ("10-K", "10-Q"):
            key = (r.accession_number, r.source_document)
            if key not in cache:
                cache[key] = E.extract_periodic_sections(read, int(r.cik), r.accession_number, r.source_document, r.form)
            res = cache[key][r.section_type]
        else:
            rel = f"/Archives/edgar/data/{int(r.cik)}/{r.accession_number.replace('-','')}/{r.source_document}"
            res = E.extract_earnings_document(read, rel, r.section_type, {"quarter_cell_size": 1})
        out.append(dict(ticker=r.ticker, acc=r.accession_number, form=r.form,
                        section=r.section_type, e1_method=r.extraction_method,
                        f3_method=res.method, f3_reason=res.reason_code,
                        f3_status=res.status, same=bool(res.text == r.text),
                        e1_words=len(r.text.split()), f3_words=len(res.text.split())))
    except Exception as e:
        out.append(dict(ticker=r.ticker, acc=r.accession_number, form=r.form,
                        section=r.section_type, e1_method=r.extraction_method,
                        f3_method="ERROR", f3_reason=f"{type(e).__name__}: {e}",
                        f3_status="ERROR", same=False, e1_words=len(r.text.split()), f3_words=0))
    if (i + 1) % 100 == 0:
        print(f"{i+1}/{len(e1)} {time.time()-t0:.0f}s", flush=True)
d = pd.DataFrame(out)
d.to_csv(str(Path(__file__).parent / "e1_regression_884.csv"), index=False)
print("TOTAL", len(d), "SAME", int(d.same.sum()), "DIFF", int((~d.same).sum()))
print(d[~d.same].groupby(["e1_method", "f3_method", "section"]).size().to_string())
print("elapsed", round(time.time() - t0))
