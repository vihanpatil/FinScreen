"""P3 spot-read sample — drawn and FROZEN before the first evidence card is read.

Implements F3_SPEC §9.1 exactly: 40 rows, three tiers, random.Random(20260827),
over extraction_audit.parquet sorted by (accession_number, section_type).

Path deviation, declared: the spec names data/f3/qa_manifest.json; this P3 brief
restricts writes to data/f3/p3_qa/, so the manifest is written to
data/f3/p3_qa/qa_manifest.json. Content and freeze discipline are unchanged --
the file is written once and never regenerated.
"""
import json, random, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import pandas as pd

OUT = ROOT / "data/f3/p4_redteam"
MANIFEST = OUT / "p4_repro_manifest.json"
SEED = 20260827

if MANIFEST.exists():
    sys.exit(f"REFUSING to regenerate frozen manifest {MANIFEST} (spec §9.1)")

a = pd.read_parquet(ROOT / "data/f3/extraction_audit.parquet",
                    columns=["cik", "company_name", "sector", "stratum",
                             "accession_number", "form", "filing_date",
                             "section_type", "extraction_status", "reason_code",
                             "extraction_method", "extraction_confidence",
                             "word_count", "prose_word_share"])
a = a.sort_values(["accession_number", "section_type"]).reset_index(drop=True)
a["year"] = a.filing_date.str[:4].astype(int)

e1_ciks = set(pd.read_csv(ROOT / "data/universe.csv")["cik"].astype(int))
assert len(e1_ciks) == 25, len(e1_ciks)

rng = random.Random(SEED)


def draw(frame, n, tier, why):
    idx = frame.index.tolist()
    if len(idx) <= n:
        picked = idx
    else:
        picked = rng.sample(idx, n)
    return [dict(tier=tier, why=why, **{k: (int(v) if hasattr(v, "item") and str(v.dtype).startswith("int") else v)
                                        for k, v in a.loc[i].items()}) for i in sorted(picked)]


drawn = []

# T1 BASE -- 16, SRS over all OK rows
drawn += draw(a[a.extraction_status == "OK"], 16, "T1_BASE", "SRS over OK rows")

# T2 NEW/OLD -- 16
periodic = a.form.isin(["10-K", "10-Q"])
new_filer = ~a.cik.isin(e1_ciks)
located = a.extraction_status.isin(["OK", "FLAGGED"])
drawn += draw(a[periodic & new_filer & (a.year <= 2018) & located], 6,
              "T2_NEWOLD", "pre-2019 periodic, CIK not in E1's 25")
drawn += draw(a[(a.form == "8-K") & (a.year <= 2018) & located], 4,
              "T2_NEWOLD", "pre-2019 earnings")
drawn += draw(a[new_filer & (a.year >= 2019) & located], 3,
              "T2_NEWOLD", "2019+ new filer")
drawn += draw(a[(a.stratum == "extension") & located
                & a.sector.isin(["industrials", "utilities", "materials_realestate"])], 3,
              "T2_NEWOLD", "extension stratum, sector E1 never had")

# T3 FLAG -- 8, one row per distinct reason_code in FLAGGED/FAIL, largest classes first
flagpop = a[a.extraction_status.isin(["FLAGGED", "FAIL"])]
codes = flagpop.reason_code.value_counts().index.tolist()[:8]
for c in codes:
    drawn += draw(flagpop[flagpop.reason_code == c], 1, "T3_FLAG", f"reason_code={c}")

df = pd.DataFrame(drawn)
assert len(df) == 40, len(df)
assert df.duplicated(["accession_number", "section_type"]).sum() == 0

MANIFEST.write_text(json.dumps(dict(
    seed=SEED, spec="F3_SPEC §9.1", frozen=True, n=len(df),
    tier_counts=df.tier.value_counts().to_dict(),
    rows=json.loads(df.to_json(orient="records")),
), indent=1))
df.to_csv(OUT / "p4_repro_manifest.csv", index=False)
print(df[["tier", "why", "company_name", "form", "section_type", "filing_date",
          "accession_number", "extraction_status", "reason_code",
          "word_count"]].to_string(index=False))
print("\nfrozen ->", MANIFEST)
