"""P3 — one streaming pass over data/filings_e2.parquet computing the text
metrics the P1 carried-forward censuses need. No text is retained.

  nonascii_ratio     -- P1 finding 2 (mojibake class, e.g. Freeport-McMoRan
                        0000831259-24-000026, 6,470 chars of font-encoded
                        garbage that clears MIN_SECTION_CHARS)
  ctrl_ratio         -- non-printable / private-use characters
  mean_words_per_line, share_1word_lines
                     -- the word-per-line rendering class found in the P3 spot
                        read (Apache 0001193125-17-157723 EX-99: 4,546 words,
                        1 prose paragraph; Waste Management 10-Q MD&A tail)
  n_lines, longest_line_words
  supplemental_hits  -- P1 finding 4 (Simon Property combined release+
                        supplemental book): count of whole-line supplemental
                        headings ANYWHERE (not just after the first 20%), plus
                        a page-header marker count ("<n>Q <yyyy> SUPPLEMENTAL")

Read-only. Peak memory = one 200-row batch.
"""
import sys, re, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import pandas as pd
import pyarrow.parquet as pq

SUPP_LINE = re.compile(r"(?im)^\s*supplemental[^\n]{0,60}$")
SUPP_PAGEHDR = re.compile(r"(?i)\b[1-4]Q\s*(?:20)?\d{2}\s+supplemental\b|\bsupplemental\s+(?:package|information)\b")


def metrics(t):
    n = len(t)
    if n == 0:
        return dict(nonascii_ratio=0.0, ctrl_ratio=0.0, n_lines=0,
                    mean_words_per_line=0.0, share_1word_lines=0.0,
                    longest_line_words=0, supp_line_hits=0, supp_pagehdr_hits=0)
    na = sum(1 for ch in t if ord(ch) > 127)
    ct = sum(1 for ch in t if unicodedata.category(ch) in ("Cc", "Co", "Cn") and ch not in "\n\t")
    lines = [ln for ln in t.split("\n") if ln.strip()]
    wc = [len(ln.split()) for ln in lines] or [0]
    return dict(nonascii_ratio=round(na / n, 4), ctrl_ratio=round(ct / n, 5),
                n_lines=len(lines),
                mean_words_per_line=round(sum(wc) / len(wc), 3),
                share_1word_lines=round(sum(1 for w in wc if w <= 1) / len(wc), 4),
                longest_line_words=max(wc),
                supp_line_hits=len(SUPP_LINE.findall(t)),
                supp_pagehdr_hits=len(SUPP_PAGEHDR.findall(t)))


def main():
    f = pq.ParquetFile(ROOT / "data/filings_e2.parquet")
    cols = ["cik", "company_name", "accession_number", "form", "filing_date",
            "section_type", "word_count", "char_count", "n_prose_paragraphs",
            "prose_word_share", "supplemental_tail_share", "extraction_status",
            "text"]
    rows = []
    for b in f.iter_batches(batch_size=200, columns=cols):
        d = b.to_pydict()
        for k in range(len(d["cik"])):
            r = {c: d[c][k] for c in cols if c != "text"}
            r.update(metrics(d["text"][k]))
            rows.append(r)
    m = pd.DataFrame(rows)
    m.to_parquet(ROOT / "data/f3/p3_qa/text_metrics.parquet")
    print("wrote text_metrics.parquet", len(m))


if __name__ == "__main__":
    main()
