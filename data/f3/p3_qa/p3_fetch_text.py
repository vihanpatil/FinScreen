"""Stream data/filings_e2.parquet and return text for named (accession, section)
pairs WITHOUT loading the 620 MB corpus into memory.

Uses pyarrow iter_batches so peak memory is one batch, not the whole column.
Read-only.
"""
import sys
from pathlib import Path
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "data/filings_e2.parquet"
COLS = ["cik", "company_name", "accession_number", "form", "filing_date",
        "section_type", "word_count", "char_count", "n_prose_paragraphs",
        "prose_word_share", "extraction_method", "extraction_confidence",
        "extraction_status", "flags", "below_length_floor", "text"]


def fetch(pairs, batch_size=200):
    """pairs: iterable of (accession_number, section_type). Returns dict->row."""
    want = set(pairs)
    got = {}
    f = pq.ParquetFile(CORPUS)
    for b in f.iter_batches(batch_size=batch_size, columns=COLS):
        accs = b.column("accession_number").to_pylist()
        secs = b.column("section_type").to_pylist()
        hits = [i for i, k in enumerate(zip(accs, secs)) if k in want]
        if hits:
            d = b.to_pydict()
            for i in hits:
                got[(accs[i], secs[i])] = {c: d[c][i] for c in COLS}
            if len(got) == len(want):
                break
    return got


def card(row, head=1200, mid=600, tail=600):
    t = row["text"]
    n = len(t)
    out = [f"### {row['company_name']} | CIK {row['cik']} | {row['form']} | "
           f"{row['section_type']} | {row['filing_date']} | {row['accession_number']}",
           f"    method={row['extraction_method']} conf={row['extraction_confidence']} "
           f"status={row['extraction_status']} flags={list(row['flags'] or [])}",
           f"    words={row['word_count']} chars={n} prose_paras={row['n_prose_paragraphs']} "
           f"prose_share={row['prose_word_share']} below_floor={row['below_length_floor']}",
           "--- HEAD ---", t[:head]]
    if n > head + tail:
        m = n // 2
        out += ["--- MID ---", t[m:m + mid]]
    if n > head:
        out += ["--- TAIL ---", t[-tail:]]
    return "\n".join(out)


if __name__ == "__main__":
    import csv
    pairs = []
    for arg in sys.argv[1:]:
        acc, _, sec = arg.partition(":")
        pairs.append((acc, sec))
    got = fetch(pairs)
    for p in pairs:
        if p in got:
            print(card(got[p]))
            print("=" * 100)
        else:
            print(f"### NOT IN CORPUS: {p}")
