"""P5 pre-flight: replay the PATCHED extractor over the two populations the
recovery ladder targets, before committing to a full corpus rebuild.

  * the 148 R2/R3 FAIL rows      -- `data/f3/p3_qa/fail_recovery.csv`
  * the 83 R2/R3 EXPECTED_ABSENT rows -- `data/f3/p4b_ea_census/ea_census_779.csv`
  * the 696 R1 EXPECTED_ABSENT rows   -- the ladder MUST NOT fire on any of them

Uses the shipped `extract.extract_periodic_sections`, i.e. the real code path,
not a re-implementation. Cache-only, zero network.
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
DB = os.path.join(ROOT, "data/filings_metadata_e2.db")
_con = None


def con():
    global _con
    if _con is None:
        _con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    return _con


def work(job):
    acc, section, arm = job
    rec = {"accession_number": acc, "section_type": section, "arm": arm}
    r = con().execute("SELECT cik, primary_document, form, company_name, filing_date "
                      "FROM filings f JOIN companies c USING (cik) "
                      "WHERE accession_number=?", (acc,)).fetchone()
    if r is None:
        r = con().execute("SELECT cik, primary_document, form, '', filing_date "
                          "FROM filings WHERE accession_number=?", (acc,)).fetchone()
    cik, doc, form, name, fd = r
    rec.update(cik=cik, form=form, company_name=name, filing_date=fd)
    try:
        fired = {}
        res = E.extract_periodic_sections(E.read_cached_document, cik, acc, doc, form,
                                          fired=fired)[section]
    except Exception as ex:  # noqa: BLE001
        rec["error"] = f"{type(ex).__name__}: {ex}"
        return rec
    rec.update(status=res.status, reason_code=res.reason_code, flags=list(res.flags),
               method=res.method, confidence=res.confidence,
               words=len(res.text.split()), head=" ".join(res.text.split()[:35]),
               tail=" ".join(res.text.split()[-20:]), note=res.note, fired=fired)
    return rec


def main():
    jobs = []
    fr = pd.read_csv(os.path.join(ROOT, "data/f3/p3_qa/fail_recovery.csv"))
    r23 = fr[fr.cause.isin(["R2_first_anchor_dangling_later_resolvable",
                            "R3_all_anchors_dangling"])]
    assert len(r23) == 148, len(r23)
    jobs += [(r.accession_number, r.section_type, "FAIL_" + r.cause[:2]) for r in r23.itertuples()]

    ea = pd.read_csv(os.path.join(ROOT, "data/f3/p4b_ea_census/ea_census_779.csv"))
    for r in ea.itertuples():
        arm = "EA_" + str(r.verdict)[:2]
        jobs.append((r.accession_number, "RISK_FACTORS", arm))
    print("jobs:", len(jobs), file=sys.stderr)

    t0 = time.time()
    with open(os.path.join(OUT, "preflight.jsonl"), "w") as fh, Pool(processes=6) as pool:
        for i, rec in enumerate(pool.imap_unordered(work, jobs, chunksize=4), 1):
            fh.write(json.dumps(rec, default=str) + "\n")
            if i % 100 == 0:
                fh.flush()
                print(f"  {i}/{len(jobs)} {time.time()-t0:.0f}s", file=sys.stderr, flush=True)
    print("DONE", time.time() - t0, file=sys.stderr)


if __name__ == "__main__":
    main()
