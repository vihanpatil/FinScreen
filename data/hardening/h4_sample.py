"""H4 -- doc-selection Tier-C sample. Draws the seeded sample and writes a
manifest. READ-ONLY against the E2 DB and data/raw/. Zero network calls."""
import json
import os
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # data/hardening/<this file> -> repo root
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")

SEED_PRIMARY = 20260825
SEED_8KBODY = 20260826

conn = sqlite3.connect(f"file:{ROOT/'data/filings_metadata_e2.db'}?mode=ro", uri=True)
conn.row_factory = sqlite3.Row

rows = conn.execute(
    """
    SELECT f.accession_number, f.cik, f.form, f.filing_date, f.report_date,
           f.acceptance_datetime, f.items, f.primary_document, f.ex99_1_document,
           f.earnings_doc_filename, f.earnings_doc_relative_path,
           f.earnings_doc_section_type AS section_type,
           f.earnings_doc_selection_confidence AS confidence,
           c.company_name, c.sector, c.stratum
      FROM filings f
      LEFT JOIN companies c ON c.cik = f.cik
     WHERE f.earnings_doc_filename IS NOT NULL
     ORDER BY f.accession_number
    """
).fetchall()
pop = [dict(r) for r in rows]
N = len(pop)
assert N == 10567, N

# --- PRIMARY: simple random sample, no stratification (Tier-C protocol) ---
rng = random.Random(SEED_PRIMARY)
primary_idx = sorted(rng.sample(range(N), 80))
primary = [pop[i] for i in primary_idx]
primary_acc = {r["accession_number"] for r in primary}

# --- SUPPLEMENTARY A: census of every medium/low selection (45) ---
suppA = [r for r in pop if r["confidence"] in ("medium", "low")]

# --- SUPPLEMENTARY B: SRS of 30 from the 210 8K_BODY/high ---
body_pop = [r for r in pop if r["section_type"] == "8K_BODY"]
rng2 = random.Random(SEED_8KBODY)
suppB = [body_pop[i] for i in sorted(rng2.sample(range(len(body_pop)), 30))]

manifest = {"primary": primary, "suppA": suppA, "suppB": suppB}
seen, ordered = set(), []
for tier, lst in (("primary", primary), ("suppA", suppA), ("suppB", suppB)):
    for r in lst:
        a = r["accession_number"]
        if a in seen:
            continue
        seen.add(a)
        r = dict(r)
        r["tiers"] = [t for t, l in (("primary", primary), ("suppA", suppA), ("suppB", suppB))
                      if any(x["accession_number"] == a for x in l)]
        ordered.append(r)

(OUT / "h4_manifest.json").write_text(json.dumps(
    {"seed_primary": SEED_PRIMARY, "seed_8kbody": SEED_8KBODY, "population": N,
     "primary_acc": sorted(primary_acc),
     "suppA_acc": sorted(r["accession_number"] for r in suppA),
     "suppB_acc": sorted(r["accession_number"] for r in suppB),
     "rows": ordered}, indent=1))

print(f"population={N}")
print(f"primary n={len(primary)}  suppA n={len(suppA)}  suppB n={len(suppB)}  "
      f"unique docs to read={len(ordered)}")

# composition checks (balance, not stratification)
from collections import Counter
def comp(lst, key):
    return dict(Counter(key(r) for r in lst).most_common())
for name, lst in (("POP", pop), ("PRIMARY", primary)):
    print(name, "conf/type:", comp(lst, lambda r: f"{r['section_type']}/{r['confidence']}"))
    print(name, "era:", comp(lst, lambda r: r["filing_date"][:4]))
    print(name, "sector:", comp(lst, lambda r: r["sector"]))
    print(name, "stratum:", comp(lst, lambda r: r["stratum"]))
    print(name, "distinct ciks:", len({r["cik"] for r in lst}))
