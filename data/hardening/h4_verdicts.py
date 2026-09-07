"""H4 verdict ledger + Wilson CIs + post-stratified corpus estimate."""
import json
import math
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # data/hardening/<this file> -> repo root
SCRATCH = Path(__file__).parent
sys.path.insert(0, str(ROOT))
from extract import html_fragment_to_text, strip_sgml_document_wrapper  # noqa: E402

man = json.loads((SCRATCH / "h4_manifest.json").read_text())
BY_ACC = {r["accession_number"]: r for r in man["rows"]}

# --- verdicts assigned by hand-read (see H4_docsample.md for evidence) --------
# default 'A' for every sampled accession; only departures are listed.
B = {  # partial / preliminary results pre-announcement
    "0000831259-20-000026": "FCX Q2-20 operational+financial update (expected Q2 EBITDA ~$650M, adj EPS ~$(0.03))",
    "0001035267-21-000008": "ISRG preliminary Q4/FY2020 results ahead of JPM conference",
    "0001140361-19-006520": "KKR Q1-19 monetization-activity update (realized carry ~$425M), 384 words",
    "0001564590-22-013264": "TSLA Q1-22 production/deliveries + earnings-date advisory, 276 words, no $ figures",
    "0000033213-25-000002": "EQT Q4-24 expected derivatives loss $184M",
    "0000033213-25-000040": "EQT Q3-25 expected derivatives gain $136M",
    "0001104659-22-107727": "EQT Q3-22 expected derivatives loss $1,627M",
    "0001038357-19-000040": "PXD Q2-19 derivative gains / realized prices / purchased-oil effect",
    "0001038357-19-000054": "PXD Q3-19 derivative gains / realized prices",
    "0001038357-24-000040": "PXD Q1-24 derivative results / investment in affiliate",
    "0001539838-25-000120": "FANG Q2-25 realized prices + derivative activity",
    "0001633917-19-000168": "PYPL Q2-19 strategic-investment pre-tax gain $218M (+$0.14 EPS)",
    "0001633917-19-000204": "PYPL Q3-19 strategic-investment pre-tax loss $228M (-$0.15 EPS)",
    "0001193125-25-007725": "WDC preliminary FQ2-25 results",
    "0001110803-15-000136": "ILMN Q2-15 earnings-call clarification Q&A w/ consumable revenue ~$250M",
    "0001140361-23-000463": "OXY Q4-22 financial+operational update (debt repaid, storm production impact)",
    "0000093410-26-000108": "CVX Q1-26 pre-earnings guidance on timing effects / production",
    "0000064803-23-000003": "CVS FY22 preliminary-vs-guidance statement at investor webcast (borderline)",
    "0001193125-18-001247": "AGN restructuring plan w/ ~$125M Q4-17 charge (borderline)",
}
C = {  # not results content at all
    "0001193125-16-496516": ("XOM 2016 Analyst Meeting presentation + CEO Q&A transcript "
                             "(21,009 words); XOM's Q4/FY15 release was a different 8-K"),
    "0001193125-16-623725": ("CB pro-forma recast segment tables (ACE/Chubb merger), "
                             "52% numeric tokens, no narrative"),
    "0001193125-16-792454": ("HWM/Arconic non-GAAP reconciliation appendix, 761 words, "
                             "investor-day filing (EX-99.2 = 80-image slide deck)"),
    "0001645590-18-000004": ("HPE revised FY2016 segment schedules (segment reorg recast); "
                             "'no impact on previously reported ... net earnings per share'"),
    "0000200406-19-000063": ("JNJ re-furnished Q3-19 condensed financial statements "
                             "(release was accession 0000200406-19-000059, 2019-10-15)"),
    "0000072903-18-000003": "XEL Tax Cuts and Jobs Act impact analysis + 2018 guidance reaffirm",
    "0001104659-22-112514": "ICE furnishing its equity-method investee Bakkt's results, not ICE's",
    "0001140361-20-008805": "KKR debt-offering business/COVID update; 'have not completed ... financial results'",
    "0000950103-21-015731": ("EMR AspenTech transaction agreement 8-K (Item 1.01 dominant); "
                             "~200-word Item 2.02 FY21 guidance reaffirmation inside 4,406 words"),
}
WRONG: dict[str, str] = {}  # a better document existed in the filing and was not picked


def verdict(acc):
    if acc in WRONG:
        return "WRONG"
    if acc in C:
        return "C"
    if acc in B:
        return "B"
    return "A"


def wilson(k, n, z=1.959963985):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


def fmt(k, n, label):
    lo, hi = wilson(k, n)
    return f"{label}: {k}/{n} = {100*k/n:5.2f}%   95% Wilson CI [{100*lo:.2f}, {100*hi:.2f}]"


DOCS = ROOT / "data/raw/documents"


def words(acc):
    r = BY_ACC[acc]
    raw = (DOCS / r["earnings_doc_relative_path"].lstrip("/").replace("/", "_")
           ).read_bytes().decode("utf-8", "replace")
    return len(html_fragment_to_text(strip_sgml_document_wrapper(raw)).split())


if __name__ == "__main__":
    from collections import Counter
    primary = man["primary_acc"]
    suppA = man["suppA_acc"]
    suppB = man["suppB_acc"]
    print("overlap primary&suppB:", set(primary) & set(suppB))
    print("overlap primary&suppA:", set(primary) & set(suppA))
    print()

    for name, accs in (("PRIMARY (SRS n=80)", primary), ("SUPP-A med/low census", suppA),
                       ("SUPP-B 8K_BODY SRS", suppB)):
        c = Counter(verdict(a) for a in accs)
        n = len(accs)
        print(f"--- {name} n={n}: {dict(c)}")
        print("   ", fmt(c["WRONG"] + c["C"], n, "headline error (WRONG+C)"))
        print("   ", fmt(c["WRONG"] + c["C"] + c["B"], n, "strict error  (+B)   "))
        print("   ", fmt(c["WRONG"], n, "selection-policy err "))
        print()

    # post-stratified corpus estimate
    POP = {"EX99_PRESS_RELEASE/high": 10312, "8K_BODY/high": 210,
           "EX99_PRESS_RELEASE/medium": 26, "EX99_PRESS_RELEASE/low": 19}
    N = sum(POP.values())
    strata = {k: {"n": 0, "err": 0, "strict": 0} for k in POP}
    seen = set()
    for a in list(primary) + list(suppA) + list(suppB):
        if a in seen:
            continue
        seen.add(a)
        r = BY_ACC[a]
        k = f"{r['section_type']}/{r['confidence']}"
        v = verdict(a)
        strata[k]["n"] += 1
        strata[k]["err"] += v in ("WRONG", "C")
        strata[k]["strict"] += v in ("WRONG", "C", "B")
    print("--- POST-STRATIFIED (weights = true class sizes) ---")
    est = strict_est = 0.0
    for k, s in strata.items():
        p = s["err"] / s["n"]
        ps = s["strict"] / s["n"]
        lo, hi = wilson(s["err"], s["n"])
        est += POP[k] / N * p
        strict_est += POP[k] / N * ps
        print(f"  {k:28s} N={POP[k]:6d} sampled n={s['n']:3d}  err={s['err']:2d} "
              f"({100*p:5.1f}% [{100*lo:.1f},{100*hi:.1f}])  strict={100*ps:5.1f}%")
    print(f"  => corpus headline error {100*est:.2f}% ; strict {100*strict_est:.2f}%")
    print()
    print("--- word counts of sampled selections, by verdict ---")
    for v in "ABC":
        ws = sorted(words(a) for a in seen if verdict(a) == v)
        if ws:
            print(f"  {v}: n={len(ws)} min={ws[0]} p10={ws[len(ws)//10]} "
                  f"median={ws[len(ws)//2]} max={ws[-1]}")
    below = [(a, words(a)) for a in seen if words(a) < 400]
    print(f"  selections under 400 words: {len(below)}/{len(seen)}")
    for a, w in sorted(below, key=lambda x: x[1]):
        print(f"     {a} {BY_ACC[a]['company_name']} {w}w [{verdict(a)}]")
