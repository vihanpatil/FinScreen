"""P3 — fill the population_gate.csv verdict/verdict_note columns.

F3_SPEC §7.4 leaves `verdict`/`verdict_note` empty "for P3's triage to fill
(the H4 ledger pattern)". §9.4(4) forbids reading extra rows to find more
examples of an already-named class: "a named class gets a CENSUS". 1,519 rows
is a census job, not a read job. So every row is verdicted MECHANICALLY from a
fixed decision table published below, and the verdict vocabulary is explicitly
NOT H4's A/B/C (those are hand-read judgements of document content; these are
not). Rows that were hand-read in the §9 spot-read are marked separately.

Writes data/f3/p3_qa/population_gate_verdicted.csv. The P2 original is never
overwritten.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import json
import pandas as pd

OUT = ROOT / "data/f3/p3_qa"
g = pd.read_csv(ROOT / "data/f3/population_gate.csv")
c = pd.read_parquet(OUT / "corpus_meta.parquet")
a = pd.read_parquet(ROOT / "data/f3/extraction_audit.parquet",
                    columns=["accession_number", "section_type", "extraction_status",
                             "reason_code"])
g["year"] = g.filing_date.str[:4].astype(int)
g = g.merge(c[["accession_number", "section_type", "below_length_floor",
               "supplemental_tail_share", "n_prose_paragraphs", "stratum",
               "item202_block_words"]],
            on=["accession_number", "section_type"], how="left")
g = g.merge(a, on=["accession_number", "section_type"], how="left")

# --- filer-level context: is a multi-filing quarter this CIK's STANDING habit? ---
allsel = pd.read_parquet(ROOT / "data/f3/extraction_audit.parquet",
                         columns=["cik", "accession_number", "form", "filing_date"])
allsel = allsel[allsel.form == "8-K"].drop_duplicates("accession_number")
allsel["quarter"] = pd.PeriodIndex(pd.to_datetime(allsel.filing_date), freq="Q").astype(str)
cells = allsel.groupby(["cik", "quarter"]).size().rename("cell").reset_index()
habit = (cells.assign(multi=cells.cell > 1).groupby("cik")
              .agg(q=("cell", "size"), multi_q=("multi", "sum")))
habit["habit_share"] = habit.multi_q / habit.q
g = g.merge(habit[["habit_share", "q", "multi_q"]], on="cik", how="left")

spot = {tuple(r) for r in [(x["accession_number"], x["section_type"])
        for x in json.loads((OUT / "qa_manifest.json").read_text())["rows"]]}


def verdict(r):
    """Decision table, fixed before it was run. One verdict per row."""
    if r.extraction_status == "FAIL":
        return ("GATE_MOOT_ROW_FAILED",
                f"row FAILed extraction ({r.reason_code}); never entered the corpus")
    if r.gate_level == "WARN_MULTI_NOSIG":
        if r.words < 400:
            return ("REVIEW_NOSIG_SHORT",
                    f"no results signature AND {int(r.words)} w — overlaps the thin/"
                    f"pre-announcement class H4 classed B/C; filer multi-quarter habit "
                    f"{r.habit_share:.0%}")
        if r.habit_share >= 0.5:
            return ("REVIEW_NOSIG_HABITUAL",
                    f"no results signature, but this filer files >=2 earnings 8-Ks in "
                    f"{r.multi_q:.0f}/{r.q:.0f} quarters ({r.habit_share:.0%}) — a standing "
                    f"pair, lower triage priority than a one-off unsigned document")
        return ("REVIEW_NOSIG", "no results signature in a multi-filing quarter cell, and the "
                                "filer does NOT habitually file pairs — the highest-priority "
                                "triage class (H4 V3 precision-C 0.375)")
    # WARN_MULTI: signature present
    if r.habit_share >= 0.5:
        return ("ACCEPT_MULTI_HABIT",
                f"filer files >=2 earnings 8-Ks in {r.multi_q:.0f}/{r.q:.0f} of its quarters "
                f"({r.habit_share:.0%}) — the multi-cell is standing practice, not an anomaly")
    if r.supplemental_tail_share and r.supplemental_tail_share >= 0.5:
        return ("ACCEPT_MULTI_SIGNED_SUPP",
                "results signature present; also carries earnings_supplemental_diluted")
    return ("ACCEPT_MULTI_SIGNED",
            "results signature present in an occasional multi-filing quarter")


v = g.apply(verdict, axis=1, result_type="expand")
g["verdict"], g["verdict_note"] = v[0], v[1]
g["hand_read_in_p3"] = [(a_, s) in spot for a_, s in zip(g.accession_number, g.section_type)]

g.to_csv(OUT / "population_gate_verdicted.csv", index=False)
print("rows:", len(g), "| P2 original untouched:",
      (ROOT / "data/f3/population_gate.csv").stat().st_size, "bytes")
print("\n=== verdict census ===")
t = (g.groupby("verdict").agg(n=("accession_number", "size"), filers=("cik", "nunique"),
                              pre2019=("year", lambda s: (s <= 2018).sum()),
                              med_words=("words", "median"))
       .sort_values("n", ascending=False))
t["share"] = (t.n / len(g)).round(4)
print(t.to_string())
print("\n=== gate_level x verdict ===")
print(pd.crosstab(g.gate_level, g.verdict).to_string())
print("\n=== REVIEW_* by filer (top 20) ===")
rev = g[g.verdict.str.startswith("REVIEW")]
print(rev.groupby(["cik", "company_name"]).size().sort_values(ascending=False).head(20).to_string())
print("total REVIEW rows:", len(rev), "filers:", rev.cik.nunique())
print("\n=== ACCEPT_MULTI_HABIT top filers ===")
h = g[g.verdict == "ACCEPT_MULTI_HABIT"]
print(h.groupby(["cik", "company_name"]).size().sort_values(ascending=False).head(15).to_string())
print("\nhand-read in the §9 spot sample:", g.hand_read_in_p3.sum())
