"""P4: independent garbled-text detector. Does NOT use ctrl_ratio.
Metric: share of alphabetic tokens that are common English words (stopword-ish
+ finance vocab). Real filing prose scores high; Caesar/font-map garbage scores ~0.
Streams the corpus; never materialises the text column."""
import re, sys, pyarrow.parquet as pq, pandas as pd

COMMON = set("""the of and to in a is for that on as with by are be this or from at
it was an we our its will not have has had were which their they may us can
also been more other such any all than into no if under about report company
year quarter results net income loss cash total share shares per revenue
revenues operating financial statements business risk factors management
discussion analysis condition operations period periods three six nine months
ended december march june september increase decrease compared primarily due
million billion percent tax taxes interest debt equity assets liabilities
customers products services market markets growth costs expenses margin
including related certain new during first second third fourth
""".split())

WORD = re.compile(r"[A-Za-z]{2,}")

rows = []
pf = pq.ParquetFile("data/filings_e2.parquet")
n = 0
for b in pf.iter_batches(batch_size=200, columns=["accession_number","section_type","cik",
        "company_name","form","filing_date","word_count","extraction_status",
        "extraction_confidence","flags","prose_word_share"]):
    d = b.to_pydict()
    rows.append(pd.DataFrame(d))
    n += len(d["accession_number"])
meta = pd.concat(rows, ignore_index=True)
print("meta rows", len(meta), file=sys.stderr)

scores = []
pf2 = pq.ParquetFile("data/filings_e2.parquet")
i = 0
for b in pf2.iter_batches(batch_size=200, columns=["text"]):
    for t in b.column("text").to_pylist():
        t = t or ""
        toks = WORD.findall(t[:200000])
        if len(toks) < 50:
            scores.append(float("nan"))
        else:
            lo = [w.lower() for w in toks]
            scores.append(sum(1 for w in lo if w in COMMON) / len(lo))
        i += 1
    if i % 5000 < 200:
        print("scored", i, file=sys.stderr)
meta["eng_share"] = scores
meta.to_parquet("data/f3/p4_redteam/garble_scan.parquet", index=False)
print("wrote", len(meta), file=sys.stderr)
