"""P5 / N5, second calibration pass: the FLOOR-RESCUE selection rule.

The first pass (`p5_n5_calibrate.py` + the 38-card hand read in
`n5_read_verdicts.csv`) refuted the obvious "prefer the first match" fix:
position does not decide which start-pattern match is the real section start.
15 of 38 read rows got better, 12 got worse, 11 were wrong both ways, and the
losses were large (PayPal +11.4k words of wrong text, Micron +15k, Walmart
+7.2k, Concho +11.3k).

What DOES separate the P3-named defect from the rest is the shipped slice's
own length: every AT&T row is 43-819 words against a 1,000-word floor and
every Disney row is a 13-word heading, while every row the first-match rule
damaged already had a plausible 7.8k-32k-word shipped slice.

So the rule measured here is narrow and reuses an already-calibrated constant:

    keep the shipped last-match slice; ONLY when it falls below
    MIN_SECTION_WORDS[(form, section)] does the locator scan the remaining
    matches in document order and take the EARLIEST one that clears the floor.
    If none clears it, the shipped slice stands.

Cache-only, zero network.
"""
from __future__ import annotations

import json
import os
import sys
import time
from multiprocessing import Pool

ROOT = "/Users/vihanpatil/personal/projects/FinScreen"
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

import extract as E  # noqa: E402

OUT = os.path.join(ROOT, "data/f3/p5_fixes")
JSONL = os.path.join(OUT, "n5_floor_rule.jsonl")


def work(row):
    acc, cik, doc, form, section = row
    rec = {"accession_number": acc, "form": form, "section_type": section}
    html = E.strip_sgml_document_wrapper(
        E.read_cached_document(E.periodic_relative_path(cik, acc, doc)))
    text = E.html_fragment_to_text(html)
    start_pat, end_pats = E.FALLBACK_SECTIONS[(form, section)]
    cands = []
    for sm in start_pat.finditer(text):
        s_end = sm.end()
        end = len(text)
        for ep in end_pats:
            m = ep.search(text, s_end)
            if m and m.start() < end:
                end = m.start()
        if end - s_end >= E.MIN_SECTION_CHARS:
            t = text[sm.start():end].strip()
            cands.append((sm.start(), end, len(t.split()), " ".join(t.split()[:40])))
    if not cands:
        rec["shipped_words"] = None
        return rec
    ship = cands[-1]
    floor = E.MIN_SECTION_WORDS.get((form, section), 0)
    rec.update(n_candidates=len(cands), shipped_words=ship[2], shipped_start=ship[0],
               shipped_head=ship[3], floor=floor)
    if ship[2] < floor:
        rescue = next((c for c in cands if c[2] >= floor), None)
        if rescue is not None and rescue[0] != ship[0]:
            rec.update(rescued=True, new_words=rescue[2], new_start=rescue[0],
                       new_head=rescue[3])
            return rec
    rec["rescued"] = False
    return rec


def main():
    corpus = pd.read_parquet(
        os.path.join(ROOT, "data/filings_e2.parquet"),
        columns=["cik", "company_name", "accession_number", "form", "filing_date",
                 "section_type", "word_count", "extraction_method", "source_document"])
    hr = corpus[corpus.extraction_method == "heading_regex"]
    todo = [(r.accession_number, int(r.cik), r.source_document, r.form, r.section_type)
            for r in hr.itertuples()]
    print("rows:", len(todo), file=sys.stderr)
    t0 = time.time()
    with open(JSONL, "w") as fh, Pool(processes=6) as pool:
        for i, rec in enumerate(pool.imap_unordered(work, todo, chunksize=4), 1):
            fh.write(json.dumps(rec, default=str) + "\n")
            if i % 200 == 0:
                print(f"  {i}/{len(todo)} {time.time()-t0:.0f}s", file=sys.stderr, flush=True)
    print("DONE", file=sys.stderr)


if __name__ == "__main__":
    main()
