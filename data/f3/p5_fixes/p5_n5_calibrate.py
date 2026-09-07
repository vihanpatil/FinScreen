"""P5 / N5 calibration: what should `locate_item_section_by_heading_regex`
select when a document has several start-pattern matches?

Today it takes the LAST match whose span clears MIN_SECTION_CHARS (30). P3 §7.2
measured the consequence: 34 AT&T 10-Q MD&As truncated to a 333-word median
against a 9,325-word anchor median, plus 25 heading-only / TOC-row slices.

This script replays the fallback over EVERY corpus row that was located by the
heading-regex path (1,140 rows) and scores three candidate selection rules
against the anchor-located median word count for the same (form, section):

    last_30   -- the shipped rule (last match, span >= 30 chars)
    first_X   -- first match in document order whose span >= X chars,
                 falling back to `last_30` when no match qualifies
                 (X swept over a ladder, so the constant is chosen from a
                 measured distribution and not from a guess)
    maxspan   -- the match with the largest span (ties -> earliest)

Cache-only, ZERO network: every document byte comes through
`extract.read_cached_document`, which raises `CacheMiss` and cannot fetch.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from multiprocessing import Pool

ROOT = "/Users/vihanpatil/personal/projects/FinScreen"
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

import extract as E  # noqa: E402

OUT = os.path.join(ROOT, "data/f3/p5_fixes")
JSONL = os.path.join(OUT, "n5_calibrate.jsonl")
DB = os.path.join(ROOT, "data/filings_metadata_e2.db")

LADDER = (100, 250, 500, 1000, 2000, 4000)

_con = None


def con():
    global _con
    if _con is None:
        _con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    return _con


def spans(text, form, section):
    start_pat, end_pats = E.FALLBACK_SECTIONS[(form, section)]
    out = []
    for sm in start_pat.finditer(text):
        s_end = sm.end()
        end = len(text)
        for ep in end_pats:
            m = ep.search(text, s_end)
            if m and m.start() < end:
                end = m.start()
        out.append((sm.start(), end, end - s_end))
    return out


def pick_last30(sp):
    for s, e, n in reversed(sp):
        if n >= E.MIN_SECTION_CHARS:
            return s, e
    return None


def pick_first_x(sp, x):
    for s, e, n in sp:
        if n >= x:
            return s, e
    return pick_last30(sp)


def pick_maxspan(sp):
    best = None
    for s, e, n in sp:
        if n < E.MIN_SECTION_CHARS:
            continue
        if best is None or n > best[2]:
            best = (s, e, n)
    return None if best is None else (best[0], best[1])


def work(row):
    acc, cik, doc, form, section = row
    rec = {"accession_number": acc, "form": form, "section_type": section}
    try:
        html = E.strip_sgml_document_wrapper(
            E.read_cached_document(E.periodic_relative_path(cik, acc, doc)))
        text = E.html_fragment_to_text(html)
    except Exception as ex:  # noqa: BLE001
        rec["error"] = f"{type(ex).__name__}: {ex}"
        return rec
    sp = spans(text, form, section)
    rec["n_matches"] = len(sp)
    rec["doc_words"] = len(text.split())

    def measure(prefix, picked):
        if picked is None:
            rec[prefix + "_words"] = None
            return
        s, e = picked
        t = text[s:e].strip()
        rec[prefix + "_words"] = len(t.split())
        rec[prefix + "_start"] = s
        rec[prefix + "_head"] = " ".join(t.split()[:25])

    measure("last30", pick_last30(sp))
    for x in LADDER:
        measure(f"first{x}", pick_first_x(sp, x))
    measure("maxspan", pick_maxspan(sp))
    return rec


def main():
    corpus = pd.read_parquet(
        os.path.join(ROOT, "data/filings_e2.parquet"),
        columns=["cik", "company_name", "accession_number", "form", "filing_date",
                 "section_type", "word_count", "extraction_method", "source_document"])
    hr = corpus[corpus.extraction_method == "heading_regex"]
    print("heading_regex rows:", len(hr), file=sys.stderr)

    done = set()
    if os.path.exists(JSONL):
        with open(JSONL) as fh:
            for line in fh:
                if line.strip():
                    r = json.loads(line)
                    done.add((r["accession_number"], r["section_type"]))
    todo = [(r.accession_number, int(r.cik), r.source_document, r.form, r.section_type)
            for r in hr.itertuples() if (r.accession_number, r.section_type) not in done]
    print("todo:", len(todo), file=sys.stderr)

    t0 = time.time()
    n = 0
    with open(JSONL, "a") as fh, Pool(processes=6) as pool:
        for rec in pool.imap_unordered(work, todo, chunksize=4):
            fh.write(json.dumps(rec, default=str) + "\n")
            n += 1
            if n % 50 == 0:
                fh.flush()
                print(f"  {n}/{len(todo)}  {time.time()-t0:.0f}s", file=sys.stderr, flush=True)
    print(f"DONE {n} in {time.time()-t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
