"""Build the acceptance-test fixtures in this directory out of the caches
under data/raw/. Offline, deterministic, zero network: it reads only files
already on disk.

Kept in the repo so the fixtures are reproducible rather than mystery blobs.
Re-run only if the acceptance cases change:

    python3 data/f2/fixtures/build_fixtures.py

Two kinds of fixture:

1. `companyfacts_CIK*.json` -- a real companyfacts document reduced to (a)
   the tags of the families the case is about and (b) facts filed on or
   after 2015-01-01 (the E2 corpus window opens 2015-07-01, so nothing
   earlier can affect a classification). Fact dicts keep only the fields
   extract_concept_facts() reads.
2. `filing_index_CIK*.html` -- a real cached filing index, copied BYTE FOR
   BYTE (never sliced): one per filer dialect the EX-99 selection policy
   has a named handler for, plus one dialect it deliberately does NOT
   recognise. These are the S6 segment-1 diagnosis cases (2026-08-24).

Nothing is renamed, reordered, or invented -- every value is EDGAR's.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CACHE = REPO_ROOT / "data" / "raw" / "companyfacts"
INDEX_CACHE = REPO_ROOT / "data" / "raw" / "filing_index"
OUT = Path(__file__).resolve().parent

# One cached filing index per EX-99 selection dialect (S6 segment-1
# diagnosis, 2026-08-24). (cik, accession) -> what the case pins.
INDEX_CASES = {
    (18230, "0000018230-16-000702"):
        "S1's live probe: plain EX-99.1, 2016-era index -> high (baseline)",
    (45012, "0000045012-17-000039"):
        "single-document 8-K, no exhibit at all -> 8K_BODY/high "
        "(2 index rows; used to trip the old >=3-row parse guard)",
    (92122, "0000092122-24-000011"):
        "zero-padded EX-99.01..EX-99.07 -> EX-99.01 at high (was low)",
    (18230, "0001104659-16-091860"):
        "EX-99.1 filed twice, .htm + 'EX-99.1 PDF' -> the .htm at high "
        "(was a lowest-seq canary at low)",
    (37996, "0000037996-15-000044"):
        "bare EX-99 filed twice, .htm + .pdf -> the .htm at high "
        "(was a lowest-seq canary at low)",
    (72741, "0000072741-18-000056"):
        "three different bare EX-99 exhibits, separable by description "
        "-> NEWS RELEASE at medium (was a lowest-seq canary at low)",
    (200406, "0000200406-19-000004"):
        "NEGATIVE case: EX-99.15 / EX-99.2O are types no handler claims "
        "-> must STAY low and go to the §4.4 manual read",
}


def copy_index_fixtures() -> None:
    for (cik, accession), why in sorted(INDEX_CASES.items()):
        source = INDEX_CACHE / f"{cik}_{accession.replace('-', '')}.html"
        if not source.exists():
            print(f"SKIP CIK {cik:<8} {accession}  (not in data/raw/ cache)")
            continue
        dest = OUT / f"filing_index_CIK{cik:010d}_{accession}.html"
        dest.write_bytes(source.read_bytes())
        print(f"CIK {cik:<8} {accession}  {dest.stat().st_size / 1024:>5.0f} KB  {why}")

FACT_FIELDS = ("start", "end", "val", "accn", "fy", "fp", "form", "filed")
MIN_FILED = "2015-01-01"

# The deleted hand-map cases (F2_SPEC §5.2 / §8.2), by CIK -- tickers appear
# here only as human labels for the case, never in pipeline code.
CASES = {
    19617: ("JPM", ["cash", "operating_income", "pretax_income"]),
    70858: ("BAC", ["cash", "operating_income", "pretax_income"]),
    886982: ("GS", ["cash", "operating_income", "pretax_income"]),
    1141391: ("MA", ["net_income"]),
    797468: ("OXY", ["net_income"]),
    87347: ("SLB", ["operating_income", "cash"]),
    93410: ("CVX", ["cash"]),
    # Not an E1 hand-map case: the tag-handoff shape the 2026-08-24 amendment
    # added MIGRATION coverage for (a co-reported predecessor that died,
    # leaving one live tag).
    1652044: ("GOOGL", ["revenue"]),
    # The MLP case (amendment A5.2): a partnership issuer whose equity and
    # per-unit earnings live under partnership tags, and whose unit count
    # nonetheless comes from the ordinary dei cover-page fact.
    1061219: ("EPD", ["equity", "eps_diluted", "shares_outstanding"]),
    # S7 finding B11: the corpus's only non-USD reporter. Its fundamentals
    # are 100% CAD while its price series is USD.
    895728: ("ENB", ["revenue", "eps_diluted"]),
}


def slice_document(cik: int, families: list[str]) -> dict:
    import sys

    sys.path.insert(0, str(REPO_ROOT))
    from ingest_fundamentals import CONCEPT_FAMILIES

    source = json.loads((CACHE / f"CIK{cik:010d}.json").read_text())
    out: dict = {
        "cik": source.get("cik", cik),
        "entityName": source.get("entityName"),
        "facts": {},
    }
    for family in families:
        for taxonomy, tag in CONCEPT_FAMILIES[family]:
            data = source.get("facts", {}).get(taxonomy, {}).get(tag)
            if data is None:
                continue
            units = {}
            for unit, facts in data.get("units", {}).items():
                kept = [
                    {k: f.get(k) for k in FACT_FIELDS}
                    for f in facts
                    if (f.get("filed") or "") >= MIN_FILED
                ]
                if kept:
                    units[unit] = kept
            if units:
                out["facts"].setdefault(taxonomy, {})[tag] = {"units": units}
    return out


def main() -> None:
    for cik, (label, families) in sorted(CASES.items()):
        doc = slice_document(cik, families)
        path = OUT / f"companyfacts_CIK{cik:010d}.json"
        path.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
        n = sum(
            len(f)
            for tax in doc["facts"].values()
            for tag in tax.values()
            for f in tag["units"].values()
        )
        print(f"{label:<4} CIK {cik:<8} {', '.join(families):<28} "
              f"{n:>5} facts  {path.stat().st_size / 1024:.0f} KB")
    print()
    copy_index_fixtures()


if __name__ == "__main__":
    main()
