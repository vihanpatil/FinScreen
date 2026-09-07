"""P4b: what would a GUARDED recovery ladder admit, measured on all 779?

Ladder (the fix package this census supports):
  rung 1  F1 -- first matching TOC entry whose anchor RESOLVES (not just the
          first matching entry), span closed with the shipped end-patterns
  rung 2  F2 -- the shipped heading-regex fallback
  reject  otherwise: keep the loud row

Both rungs must pass the same two guards:
  G1  the span opens on an "Item 1A ... Risk Factors" heading within 40 chars
  G2  the end-guarded span must NOT terminate at end-of-document

Run over R1 too, so the report can bound what an UNSCOPED "fall through on
EXPECTED_ABSENT" would inject. Read-only; prints, writes nothing.
"""
from __future__ import annotations

import os
import re

import numpy as np
import pandas as pd

OUT = "/Users/vihanpatil/personal/projects/FinScreen/data/f3/p4b_ea_census"
H = re.compile(r"item\s*1\s*\(?a\)?[\s\xa0.:|\-–—]{0,20}risk\s*factors", re.I)


def g1(head):
    m = H.search(str(head)[:400])
    return bool(m) and m.start() < 40


d = pd.read_json(os.path.join(OUT, "census_rows.jsonl"), lines=True)
assert len(d) == 779

rows = []
for _, r in d.iterrows():
    rung, words, why = "reject", np.nan, ""
    # rung 1 -- only available when a matching entry resolved (R2/R4)
    if pd.notna(r.get("rec_guarded_words")):
        ok1 = g1(r.get("rec_head"))
        ok2 = not (bool(r.get("rec_end_at_eof")) and not (r.get("rec_guarded_words") < r.get("rec_words")))
        if ok1 and ok2 and r.get("rec_guarded_words") >= 15:
            rung, words, why = "F1_anchor_guarded", r.get("rec_guarded_words"), "G1+G2 pass"
        else:
            why = f"F1 rejected (G1={ok1} G2={ok2})"
    # rung 2 -- the shipped fallback
    if rung == "reject" and pd.notna(r.get("fb_words")):
        ok1 = g1(r.get("fb_head"))
        ok2 = not bool(r.get("fb_end_at_eof"))
        if ok1 and ok2 and r.get("fb_words") >= 15:
            rung, words, why = "F2_fallback_guarded", r.get("fb_words"), why + " -> F2 G1+G2 pass"
        else:
            why = why + f" -> F2 rejected (G1={ok1} G2={ok2})"
    rows.append(dict(accession_number=r.accession_number, company_name=r.company_name,
                     filing_date=str(r.filing_date)[:10], verdict=r.verdict,
                     rung=rung, words=words, why=why))

L = pd.DataFrame(rows)
print("=== guarded ladder outcome, all 779 ===")
print(pd.crosstab(L.verdict, L.rung, margins=True).to_string())
print()
for arm in ["R2_first_dangling_later_resolves", "R3_all_matching_dangling",
            "R1_genuinely_absent_from_toc"]:
    g = L[L.verdict == arm]
    acc = g[g.rung != "reject"]
    print(f"--- {arm}: n={len(g)}  admitted={len(acc)}  rejected={len(g)-len(acc)}")
    if len(acc):
        print(acc.groupby(["company_name", "rung"]).agg(
            n=("accession_number", "size"), wmin=("words", "min"), wmax=("words", "max")
        ).to_string())
    print()
