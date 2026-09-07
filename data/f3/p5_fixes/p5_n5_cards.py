"""P5 / N5: evidence cards for the hand read of the rows whose bytes would
change under the candidate `first match with span >= X` selection rule.

For each selected row it prints, side by side, the head and tail of the
SHIPPED (last-match) slice and of the CANDIDATE (first-match-with-span>=500)
slice, plus both word counts and the (form, section) anchor median. The read
verdicts are recorded by hand in `n5_read_verdicts.csv`.

Sampling is stratified by (form, section) and seeded, drawn BEFORE any card is
read. Cache-only, zero network.
"""
from __future__ import annotations

import os
import sqlite3
import sys

ROOT = "/Users/vihanpatil/personal/projects/FinScreen"
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

import extract as E  # noqa: E402

OUT = os.path.join(ROOT, "data/f3/p5_fixes")
DB = os.path.join(ROOT, "data/filings_metadata_e2.db")
X = 500
SEED = 20260828

con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


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


def card(acc, section, out):
    r = con.execute("SELECT cik, primary_document, form, filing_date FROM filings "
                    "WHERE accession_number=?", (acc,)).fetchone()
    cik, doc, form, fd = r
    html = E.strip_sgml_document_wrapper(
        E.read_cached_document(E.periodic_relative_path(cik, acc, doc)))
    text = E.html_fragment_to_text(html)
    sp = spans(text, form, section)
    a, b = pick_last30(sp), pick_first_x(sp, X)
    out.append(f"\n{'='*78}\n{acc}  {form} {section}  {fd}  matches={len(sp)}")
    for label, pick in (("SHIPPED(last)", a), (f"CANDIDATE(first>={X})", b)):
        t = text[pick[0]:pick[1]].strip()
        w = t.split()
        out.append(f"--- {label}: {len(w)} words, start={pick[0]}")
        out.append("    HEAD: " + " ".join(w[:45]))
        out.append("    TAIL: " + " ".join(w[-20:]))


def main():
    cal = pd.read_json(os.path.join(OUT, "n5_calibrate.jsonl"), lines=True)
    corp = pd.read_parquet(os.path.join(ROOT, "data/filings_e2.parquet"),
                           columns=["accession_number", "section_type", "form",
                                    "company_name", "extraction_method"])
    hr = corp[corp.extraction_method == "heading_regex"]
    cal = cal.merge(hr[["accession_number", "section_type", "company_name"]],
                    on=["accession_number", "section_type"])
    changed = cal[cal[f"first{X}_words"] != cal["last30_words"]]
    print("changed rows by (form, section):", file=sys.stderr)
    print(changed.groupby(["form", "section_type"]).size(), file=sys.stderr)

    picks = []
    for (f, s), g in changed.groupby(["form", "section_type"]):
        n = min(len(g), 12 if (f, s) == ("10-Q", "RISK_FACTORS") else 10)
        picks.append(g.sample(n, random_state=SEED))
    sample = pd.concat(picks)
    sample[["accession_number", "section_type", "form", "company_name",
            "last30_words", f"first{X}_words"]].to_csv(
        os.path.join(OUT, "n5_read_manifest.csv"), index=False)

    out = []
    for r in sample.itertuples():
        card(r.accession_number, r.section_type, out)
    with open(os.path.join(OUT, "n5_read_cards.txt"), "w") as fh:
        fh.write("\n".join(out))
    print("wrote", len(sample), "cards", file=sys.stderr)


if __name__ == "__main__":
    main()
