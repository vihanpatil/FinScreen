"""P5 regression: prove that every row NOT touched by fixes 1-5 is
byte-identical to the 2026-08-27 corpus, and attribute every row that DID
change to a named fix.

Compares, on the key (accession_number, section_type):
    old  data/f3/extraction_audit.parquet   + data/filings_e2.parquet
    new  data/f3/v2/extraction_audit.parquet + data/filings_e2_v2.parquet

Text is compared by sha256 digest, streamed in 200-row batches, so the 620 MB
text column is never materialised on either side.

Attribution buckets (a row is assigned to the FIRST that matches, and the
buckets are then reconciled against the populations P3/P4b/P5 measured):
    fix1_ladder_recovered   a FAIL / EXPECTED_ABSENT row the guarded ladder
                            recovered  -> new corpus row
    fix1_ladder_declined    a row whose reason_code moved from
                            item_absent_from_toc to toc_recovery_declined
    fix2_status_rename      EXPECTED_ABSENT -> ITEM_ABSENT_FROM_TOC
    fix2_body_heading_mark  gained `item_body_heading_present`
    fix3_garble_flag        gained `garbled_text`
    fix4_n5_floor_rescue    heading_regex row whose text changed
    fix5_nike_handler       NIKE 10-Q MDA row whose text changed
    UNATTRIBUTED            anything else -- must be zero

Read-only. Zero network.
"""
from __future__ import annotations

import hashlib
import os
import sys

ROOT = "/Users/vihanpatil/personal/projects/FinScreen"
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

OLD_AUDIT = os.path.join(ROOT, "data/f3/extraction_audit.parquet")
NEW_AUDIT = os.path.join(ROOT, "data/f3/v2/extraction_audit.parquet")
OLD_CORP = os.path.join(ROOT, "data/filings_e2.parquet")
NEW_CORP = os.path.join(ROOT, "data/filings_e2_v2.parquet")
NIKE_CIK = 320187


def digests(path):
    out = {}
    pf = pq.ParquetFile(path)
    for b in pf.iter_batches(batch_size=200,
                             columns=["accession_number", "section_type", "text"]):
        d = b.to_pydict()
        for i, acc in enumerate(d["accession_number"]):
            out[(acc, d["section_type"][i])] = hashlib.sha256(
                (d["text"][i] or "").encode()).hexdigest()
    return out


def main():
    oa = pd.read_parquet(OLD_AUDIT)
    na = pd.read_parquet(NEW_AUDIT)
    print(f"audit rows: old {len(oa)}  new {len(na)}")
    oa["flagset"] = [frozenset(f) for f in oa["flags"]]
    na["flagset"] = [frozenset(f) for f in na["flags"]]
    key = ["accession_number", "section_type"]
    m = oa.merge(na, on=key, suffixes=("_o", "_n"), how="outer", indicator=True)
    print("key alignment:", m["_merge"].value_counts().to_dict())
    assert (m["_merge"] == "both").all(), "attempt keys must be identical"

    od, nd = digests(OLD_CORP), digests(NEW_CORP)
    print(f"corpus rows: old {len(od)}  new {len(nd)}")
    # "" for a row that is not in the corpus at all, so that two absent rows
    # compare EQUAL (pandas would make them NaN, and NaN != NaN).
    m["dig_o"] = [od.get(k, "") for k in zip(m.accession_number, m.section_type)]
    m["dig_n"] = [nd.get(k, "") for k in zip(m.accession_number, m.section_type)]

    changed = m[(m.dig_o != m.dig_n) | (m.extraction_status_o != m.extraction_status_n)
                | (m.reason_code_o != m.reason_code_n) | (m.flagset_o != m.flagset_n)
                | (m.extraction_confidence_o != m.extraction_confidence_n)
                | (m.extraction_method_o != m.extraction_method_n)].copy()
    print(f"\nrows differing on text, status, reason_code, flags, confidence or method: "
          f"{len(changed)} of {len(m)}")

    def bucket(r):
        if r.reason_code_n in ("toc_recovered_f1", "toc_recovered_f2"):
            return "fix1_ladder_recovered"
        if r.reason_code_n == "toc_recovery_declined":
            return "fix1_ladder_declined"
        if "garbled_text" in r.flagset_n and "garbled_text" not in r.flagset_o:
            return "fix3_garble_flag"
        if (r.cik_n == NIKE_CIK and r.form_n == "10-Q" and r.section_type == "MDA"
                and r.dig_o != r.dig_n):
            return "fix5_nike_handler"
        if r.dig_o != r.dig_n and r.extraction_method_n == "heading_regex":
            return "fix4_n5_floor_rescue"
        if "item_body_heading_present" in r.flagset_n and "item_body_heading_present" not in r.flagset_o:
            return "fix2_body_heading_mark"
        if (r.extraction_status_o == "EXPECTED_ABSENT"
                and r.extraction_status_n == "ITEM_ABSENT_FROM_TOC"):
            return "fix2_status_rename"
        return "UNATTRIBUTED"

    changed["bucket"] = [bucket(r) for r in changed.itertuples()]
    print("\n=== attribution ===")
    print(changed.bucket.value_counts().to_string())

    txt = changed[changed.dig_o != changed.dig_n]
    print(f"\nrows whose TEXT BYTES changed: {len(txt)}")
    print(txt.bucket.value_counts().to_string())

    unattr = changed[changed.bucket == "UNATTRIBUTED"]
    print(f"\nUNATTRIBUTED: {len(unattr)}")
    if len(unattr):
        print(unattr[["accession_number", "section_type", "company_name_o", "form_o",
                      "extraction_status_o", "extraction_status_n",
                      "reason_code_o", "reason_code_n"]].head(40).to_string())

    print("\n=== corpus membership ===")
    print("old sections", len(od), "-> new", len(nd), f"(delta {len(nd)-len(od):+d})")
    print("\nstatus counts, old -> new")
    print(pd.concat([oa.extraction_status.value_counts().rename("old"),
                     na.extraction_status.value_counts().rename("new")],
                    axis=1).fillna(0).astype(int).to_string())
    print("\nnew reason codes not present before:")
    print(na[~na.reason_code.isin(set(oa.reason_code))].reason_code.value_counts().to_string())

    changed.to_csv(os.path.join(ROOT, "data/f3/p5_fixes/changed_rows.csv"), index=False,
                   columns=["accession_number", "section_type", "cik_n", "company_name_n",
                            "form_n", "filing_date_n", "bucket",
                            "extraction_status_o", "extraction_status_n",
                            "reason_code_o", "reason_code_n",
                            "extraction_confidence_o", "extraction_confidence_n",
                            "extraction_method_o", "extraction_method_n",
                            "word_count_o", "word_count_n"])
    print("\nwrote data/f3/p5_fixes/changed_rows.csv")

    # word deltas per bucket
    print("\n=== words added / removed per bucket ===")
    changed["dw"] = changed.word_count_n.fillna(0) - changed.word_count_o.fillna(0)
    print(changed.groupby("bucket").agg(n=("dw", "size"), words_delta=("dw", "sum"),
                                         words_new=("word_count_n", "sum")).to_string())


if __name__ == "__main__":
    main()
