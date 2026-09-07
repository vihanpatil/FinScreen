"""P3 per-filer failure triage over data/f3/extraction_audit.parquet.

Read-only. Writes tables under data/f3/p3_qa/. No network, no corpus text load.
"""
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data/f3/p3_qa"
OUT.mkdir(exist_ok=True)

a = pd.read_parquet(ROOT / "data/f3/extraction_audit.parquet",
                    columns=["cik", "company_name", "sector", "stratum",
                             "accession_number", "form", "filing_date",
                             "section_type", "extraction_status", "reason_code",
                             "extraction_method", "extraction_confidence",
                             "word_count", "prose_word_share", "source_document",
                             "note"])
a["year"] = a["filing_date"].str[:4].astype(int)
a["era"] = (a["year"] <= 2018).map({True: "pre2019", False: "2019plus"})

print("=== A. status totals ===")
print(a["extraction_status"].value_counts())
print("attempts", len(a))

print("\n=== B. reason_code x status ===")
print(a.groupby(["extraction_status", "reason_code"]).size().sort_values(ascending=False).to_string())

print("\n=== C. FAIL by reason_code x form x section ===")
f = a[a.extraction_status == "FAIL"]
print(f.groupby(["reason_code", "form", "section_type"]).size().sort_values(ascending=False).to_string())

print("\n=== D. FAIL by era ===")
print(f.groupby(["reason_code", "era"]).size().unstack(fill_value=0).to_string())

print("\n=== E. FAIL concentration by filer ===")
byfiler = f.groupby(["cik", "company_name"]).size().sort_values(ascending=False)
print("filers with >=1 FAIL:", len(byfiler))
print("top 25:")
print(byfiler.head(25).to_string())
print("top10 share of 796 FAILs: %.1f%%" % (100 * byfiler.head(10).sum() / len(f)))

print("\n=== F. FAIL clusters: (cik, form, section, reason) with n>=4 ===")
cl = (f.groupby(["cik", "company_name", "form", "section_type", "reason_code"])
        .agg(n=("accession_number", "size"),
             yr_min=("year", "min"), yr_max=("year", "max"))
        .reset_index().sort_values("n", ascending=False))
cl.to_csv(OUT / "fail_clusters.csv", index=False)
print(cl[cl.n >= 4].to_string(index=False))
print("clusters n>=4:", (cl.n >= 4).sum(), "covering", cl[cl.n >= 4].n.sum(), "of", len(f), "FAILs")

print("\n=== G. rollup: filers with fail_rate>=0.5 on any (form,section) with n>=4 ===")
r = pd.read_csv(ROOT / "data/f3/per_filer_rollup.csv")
sel = r[(r.fail_rate >= 0.5) & (r.n_attempt >= 4)].sort_values(["fail_rate", "n_attempt"],
                                                               ascending=[False, False])
sel.to_csv(OUT / "rollup_tier1_filers.csv", index=False)
print(sel.to_string(index=False))
print("tier-1 rows:", len(sel), "attempts:", sel.n_attempt.sum(), "fails:", sel.n_fail.sum())

print("\n=== H. rollup: filers with >=10 flagged rows (tier 2) ===")
t2 = r[r.n_flagged >= 10].sort_values("n_flagged", ascending=False)
t2.to_csv(OUT / "rollup_tier2_filers.csv", index=False)
print(t2.head(30).to_string(index=False))
print("tier-2 rows:", len(t2), "flagged covered:", t2.n_flagged.sum(), "of", (a.extraction_status == "FLAGGED").sum())

print("\n=== I. FLAGGED reason codes, full census ===")
fl = a[a.extraction_status == "FLAGGED"]
tab = (fl.groupby("reason_code")
         .agg(n=("accession_number", "size"), n_filers=("cik", "nunique"),
              n_pre2019=("era", lambda s: (s == "pre2019").sum()),
              med_words=("word_count", "median"))
         .sort_values("n", ascending=False))
print(tab.to_string())

print("\n=== J. flags column census (multi-flag) ===")
fla = pd.read_parquet(ROOT / "data/f3/extraction_audit.parquet", columns=["flags"])
from collections import Counter
c = Counter()
for v in fla["flags"]:
    if v is not None:
        for x in v:
            c[x] += 1
for k, v in c.most_common():
    print(f"{k:40s} {v}")

print("\n=== K. EXPECTED_ABSENT ===")
ea = a[a.extraction_status == "EXPECTED_ABSENT"]
print(ea.groupby(["form", "section_type", "reason_code"]).size().to_string())
print("distinct filers:", ea.cik.nunique(), "; rate over 10-Q RF attempts: %.1f%%" %
      (100 * len(ea) / len(a[(a.form == "10-Q") & (a.section_type == "RISK_FACTORS")])))

print("\n=== L. confidence x status ===")
print(pd.crosstab(a.extraction_status, a.extraction_confidence).to_string())

print("\n=== M. located-rate by form/section/era (OK+FLAGGED / attempts) ===")
a["located"] = a.extraction_status.isin(["OK", "FLAGGED"])
print((a.groupby(["form", "section_type", "era"])["located"].agg(["size", "sum", "mean"])).to_string())

f.to_csv(OUT / "fails_all.csv", index=False)
print("\nwrote", OUT / "fails_all.csv", len(f))
