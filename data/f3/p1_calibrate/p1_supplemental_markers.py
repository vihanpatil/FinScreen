"""P1 calibration of `extract.SUPPLEMENTAL_MARKERS` (F3_SPEC §6).

The spec ships the marker list PROVISIONAL and requires it to be calibrated
against the corpus before any flag count is reported, using F2 §5's deck-title
rule: a marker enters the list only if its measured hits are dominated by true
positives, with the false positive named.

Method: a seeded sample of EX-99 selections plus the two named anchors
(Simon Property's combined release+supplemental book, AvalonBay's clean
two-exhibit shape). For each candidate marker, count whole-line hits after the
first 20% of the document and print the hit line with the resulting tail share
so each can be hand-read. Zero GETs.
"""
import random
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path("/Users/vihanpatil/personal/projects/FinScreen")
sys.path.insert(0, str(ROOT))
import extract as E  # noqa: E402

SEED = 20260826
SAMPLE_N = 1500
ANCHOR_CIKS = {1063761: "Simon Property (combined release+supplemental, H4 §8.4)",
               915912: "AvalonBay (clean two-exhibit shape)",
               1045609: "Prologis (F2 §5 deck/title-page precedent)"}

con = sqlite3.connect(f"file:{ROOT}/data/filings_metadata_e2.db?mode=ro", uri=True)
rows = con.execute(
    "SELECT f.accession_number, f.cik, c.company_name, f.filing_date, "
    "       f.earnings_doc_relative_path, f.earnings_doc_filename "
    "FROM filings f JOIN companies c ON c.cik = f.cik "
    "WHERE f.earnings_doc_section_type = 'EX99_PRESS_RELEASE' "
    "ORDER BY f.accession_number").fetchall()
con.close()

rnd = random.Random(SEED)
sample = rnd.sample(rows, SAMPLE_N)
anchors = [r for r in rows if r[1] in ANCHOR_CIKS]
seen = {r[0] for r in sample}
sample += [r for r in anchors if r[0] not in seen]
print(f"EX99 population {len(rows)}; sample {SAMPLE_N} (seed {SEED}) "
      f"+ {len(sample) - SAMPLE_N} forced anchor rows = {len(sample)}")

EDGE = re.compile(r"^[^0-9a-z]+|[^0-9a-z]+$")
hits = Counter()
records = []
for acc, cik, name, fdate, rel, fn in sample:
    rel = rel or f"/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{fn}"
    try:
        text = E.html_fragment_to_text(E.strip_sgml_document_wrapper(E.read_cached_document(rel)))
    except E.CacheMiss:
        continue
    total = len(text)
    if not total:
        continue
    share = E.supplemental_tail_share(text)
    # re-find which line fired, for the hand-read
    fired_line, fired_marker = "", ""
    offset = 0
    for line in text.split("\n"):
        start = offset
        offset += len(line) + 1
        if start < E.SUPPLEMENTAL_MIN_POSITION_SHARE * total:
            continue
        norm = EDGE.sub("", re.sub(r"\s+", " ", line.strip().lower()))
        if len(norm) > E._SUPPLEMENTAL_HEADING_MAX_CHARS:
            continue
        m = next((mk for mk in E.SUPPLEMENTAL_MARKERS if norm == mk or norm.startswith(mk)), None)
        if m:
            fired_line, fired_marker = line.strip()[:90], m
            break
    if fired_marker:
        hits[fired_marker] += 1
    records.append({"acc": acc, "cik": cik, "name": name, "filing_date": fdate,
                    "words": len(text.split()), "chars": total,
                    "tail_share": share, "marker": fired_marker, "line": fired_line,
                    "anchor": ANCHOR_CIKS.get(cik, "")})

d = pd.DataFrame(records)
d.to_csv(Path(__file__).parent / "supplemental_marker_calibration.csv", index=False)
print(f"\nread {len(d)} documents")
print(f"fired at all: {(d.marker != '').sum()}   "
      f"flagged at >= {E.SUPPLEMENTAL_DILUTED_SHARE}: {(d.tail_share >= E.SUPPLEMENTAL_DILUTED_SHARE).sum()}")
print("\nper-marker hit counts:")
for mk in E.SUPPLEMENTAL_MARKERS:
    sub = d[d.marker == mk]
    print(f"  {mk:34s} hits {len(sub):4d}   flagged {int((sub.tail_share >= 0.5).sum()):4d}   "
          f"median tail share {sub.tail_share.median() if len(sub) else float('nan')}")
print("\nEVERY hit, for the hand-read:")
for _, r in d[d.marker != ""].sort_values("tail_share", ascending=False).iterrows():
    print(f"  {r.acc} {r['name'][:32]:32s} {r.filing_date} {r.words:6d}w "
          f"share={r.tail_share:.3f} [{r.marker}] :: {r.line}")
print("\nANCHOR ROWS:")
for _, r in d[d.anchor != ""].sort_values(["name", "filing_date"]).iterrows():
    print(f"  {r.acc} {r['name'][:32]:32s} {r.filing_date} {r.words:6d}w "
          f"share={r.tail_share:.3f} marker={r.marker or '-'} :: {r.line}")
