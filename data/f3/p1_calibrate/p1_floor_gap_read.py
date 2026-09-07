"""P1 evidence for the (8-K, EX99_PRESS_RELEASE) floor raise 50 -> 250 words.

F3_SPEC §8.1(2)(b): a floor may only move with a HAND-READ of every row in
the gap between the old and the new floor (or a seeded sample of >=10 with
the sampling rule stated). The gap here holds 41 rows, so all 41 are read.
Zero GETs -- text comes from data/raw/documents/ through extract.py's own
strip_sgml_document_wrapper -> html_fragment_to_text.

Also verifies the two rows H4 §8.1 forbids any floor from failing "without
arguing past them by name": Tesla Q1-22 P&D (0001564590-22-013264, 276 w)
and KKR's monetization update (0001140361-19-006520, 384 w).
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path("/Users/vihanpatil/personal/projects/FinScreen")
sys.path.insert(0, str(ROOT))
from extract import html_fragment_to_text, read_cached_document, strip_sgml_document_wrapper  # noqa: E402

OLD_FLOOR, NEW_FLOOR = 50, 250
NAMED_SURVIVORS = {"0001564590-22-013264": "Tesla Q1-22 P&D (H4 §8.1)",
                   "0001140361-19-006520": "KKR monetization update (H4 §8.1)"}

census = pd.read_parquet(ROOT / "data/f3/p0_measure/gate_corpus.parquet")
ex99 = census[census.section_type == "EX99_PRESS_RELEASE"]
gap = ex99[(ex99.words >= OLD_FLOOR) & (ex99.words < NEW_FLOOR)].sort_values("words")

con = sqlite3.connect(f"file:{ROOT}/data/filings_metadata_e2.db?mode=ro", uri=True)
paths = dict(con.execute(
    "SELECT accession_number, earnings_doc_relative_path FROM filings "
    "WHERE earnings_doc_relative_path IS NOT NULL"))
con.close()


def text_for(acc):
    return html_fragment_to_text(strip_sgml_document_wrapper(read_cached_document(paths[acc])))


print(f"EX99 selections: {len(ex99)}")
print(f"below OLD floor {OLD_FLOOR}: {(ex99.words < OLD_FLOOR).sum()}  "
      f"below NEW floor {NEW_FLOOR}: {(ex99.words < NEW_FLOOR).sum()}")
print(f"GAP rows to hand-read: {len(gap)}\n")

rows = []
for _, r in gap.iterrows():
    t = text_for(r.acc)
    rows.append({"acc": r.acc, "filer": r["name"], "filing_date": r.filing_date,
                 "words": r.words, "chars": r.chars, "text": t})
    print("=" * 78)
    print(f"{r.acc}  {r['name']}  {r.filing_date}  {r.words}w {r.chars}c")
    print(t[:900].replace("\n", " | "))
    print()

print("=" * 78)
print("NAMED SURVIVORS (must stay ABOVE the new floor):")
for acc, why in NAMED_SURVIVORS.items():
    row = ex99[ex99.acc == acc]
    if row.empty:
        print(f"  {acc}: NOT FOUND in the EX99 census -- investigate")
        continue
    w = int(row.words.iloc[0])
    print(f"  {acc} {row['name'].iloc[0]}: {w} words -> "
          f"{'ABOVE' if w >= NEW_FLOOR else 'BELOW (VIOLATION)'} the {NEW_FLOOR}-word floor  [{why}]")

pd.DataFrame(rows).to_csv(Path(__file__).parent / "floor_gap_ex99_50_249.csv", index=False)
