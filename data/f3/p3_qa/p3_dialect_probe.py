"""P3: classify the 796 FAILs into named dialect classes, and size the
recovery a candidate fix would deliver.

Method: the FAIL population is 90% concentrated in 54 (cik, form, section,
reason) clusters of n>=4 whose filings share one filer template. Probe 2
filings per cluster (seeded, deterministic) plus a seeded sample of the
residual, read each cached primary document ONCE, and record a fixed set of
dialect signatures. No extract.py behaviour is changed; this is a harness.

Read-only, cache-only. Zero network.
"""
import sys, re, json, random, sqlite3, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import pandas as pd
import extract as E

OUT = ROOT / "data/f3/p3_qa"
DB = ROOT / "data/filings_metadata_e2.db"
SEED = 20260827

KEYWORD = {("10-K", "MDA"): r"management.{0,4}s\s+discussion",
           ("10-K", "RISK_FACTORS"): r"risk\s+factors",
           ("10-Q", "MDA"): r"management.{0,4}s\s+discussion",
           ("10-Q", "RISK_FACTORS"): r"risk\s+factors"}
ITEMNO = {("10-K", "MDA"): "7", ("10-K", "RISK_FACTORS"): "1A",
          ("10-Q", "MDA"): "2", ("10-Q", "RISK_FACTORS"): "1A"}


def meta(accs):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    q = ",".join("?" * len(accs))
    rows = con.execute(
        f"SELECT accession_number, cik, primary_document FROM filings "
        f"WHERE accession_number IN ({q})", list(accs)).fetchall()
    con.close()
    return {a: (c, p) for a, c, p in rows}


def signatures(text, soup, body, form, section):
    """Fixed, named dialect signatures. Each is a boolean/int, no judgement."""
    n, kw = ITEMNO[(form, section)], KEYWORD[(form, section)]
    ne = re.escape(n)
    s = {}
    # current shipped fallback pattern (gap = whitespace/nbsp/period/colon only)
    s["cur_heading"] = len(re.findall(rf"(?i)item\s*{ne}\.?[\s\xa0.:]{{0,20}}{kw}", text))
    # D9 candidate: allow dash/en-dash/em-dash/paren in the gap  (Emerson)
    s["dash_heading"] = len(re.findall(
        rf"(?i)item\s*{ne}\.?[\s\xa0.:\-–—‐−|)(]{{0,20}}{kw}", text))
    # D12 candidate: gap may contain a newline-broken title (Colgate-shape)
    s["item_kw_within_60"] = len(re.findall(rf"(?i)item\s*{ne}\b.{{0,60}}?{kw}", text, re.S))
    # bare title heading, no item label at all, on its own line
    s["bare_title_line"] = len(re.findall(rf"(?im)^\s*{kw}[^\n]{{0,80}}$", text))
    s["kw_anywhere"] = len(re.findall(rf"(?i){kw}", text))
    # D10 candidate: combined-item TOC row  ("Items 2 and 3 - MD&A", "Items 1, 2, 3 and 4")
    s["combined_items_row"] = len(re.findall(
        rf"(?i)items\s*[0-9]{{1,2}}[a-c]?\s*[.,]?(?:\s*(?:and|,|&)\s*[0-9]{{1,2}}[a-c]?\s*[.,]?)+", text))
    s["combined_items_with_kw"] = len(re.findall(
        rf"(?i)items\s*[0-9]{{1,2}}[a-c]?[^\n]{{0,80}}{kw}", text))
    # D13: reversed order -- title line then "Part I, Item 1A" on the next line
    s["title_then_itemlabel"] = len(re.findall(
        rf"(?i){kw}[^A-Za-z]{{0,20}}(?:part\s+[ivx]+,?\s*)?item\s*{ne}\b", text))
    # D7: cross-reference index and NO item token at all in the body
    s["item_token_count"] = len(re.findall(rf"(?i)\bitem\s*{ne}\b", text))
    s["crossref_index"] = int(bool(re.search(r"(?i)cross-?reference\s+index", text)))
    s["words"] = len(text.split())
    # TOC anchor state
    an = E.find_toc_item_anchors(soup)
    s["n_anchors"] = len(an)
    s["anchor_items"] = ",".join(sorted({e.item_no for e in an}))
    s["target_in_toc"] = int(any(e.item_no == n for e in an))
    # of the target-numbered TOC rows, does any row_text carry the title keyword?
    s["target_toc_row_has_kw"] = int(any(
        e.item_no == n and re.search(kw, e.row_text) for e in an))
    return s


def main():
    audit = pd.read_parquet(ROOT / "data/f3/extraction_audit.parquet",
                            columns=["cik", "company_name", "accession_number", "form",
                                     "filing_date", "section_type", "extraction_status",
                                     "reason_code"])
    f = audit[audit.extraction_status == "FAIL"].copy()
    f = f[f.form != "8-K"]                     # the 12 8-K FAILs are the named P5 class
    f["cluster"] = (f.cik.astype(str) + "|" + f.form + "|" + f.section_type + "|" + f.reason_code)

    rng = random.Random(SEED)
    picks = []
    for cl, g in f.groupby("cluster"):
        g = g.sort_values(["accession_number", "section_type"])
        k = 2 if len(g) >= 4 else 1
        idx = sorted(rng.sample(range(len(g)), min(k, len(g))))
        for i in idx:
            r = g.iloc[i]
            picks.append(dict(cluster=cl, cluster_n=len(g), cik=r.cik,
                              company_name=r.company_name, form=r.form,
                              section_type=r.section_type, reason_code=r.reason_code,
                              accession_number=r.accession_number,
                              filing_date=r.filing_date))
    print(f"clusters={f.cluster.nunique()} probe_rows={len(picks)} "
          f"covering {f.cluster.nunique()} clusters / {len(f)} periodic FAILs")

    m = meta(sorted({p["accession_number"] for p in picks}))
    # group by accession so each document is read+parsed exactly once
    by_acc = {}
    for p in picks:
        by_acc.setdefault(p["accession_number"], []).append(p)

    rows, t0 = [], time.time()
    for i, (acc, ps) in enumerate(sorted(by_acc.items()), 1):
        cik, primary = m[acc]
        rel = f"/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{primary}"
        try:
            body = E.strip_sgml_document_wrapper(E.read_cached_document(rel))
            soup = E.BeautifulSoup(body, "html.parser")
            text = E.html_fragment_to_text(body)
        except Exception as exc:
            for p in ps:
                rows.append({**p, "error": f"{type(exc).__name__}: {exc}"})
            continue
        for p in ps:
            try:
                rows.append({**p, "error": "",
                             **signatures(text, soup, body, p["form"], p["section_type"])})
            except Exception as exc:
                rows.append({**p, "error": f"sig {type(exc).__name__}: {exc}"})
        del soup, text, body
        if i % 20 == 0:
            print(f"  {i}/{len(by_acc)} docs  {time.time()-t0:.0f}s", flush=True)

    d = pd.DataFrame(rows)
    d.to_csv(OUT / "dialect_probe.csv", index=False)
    print("wrote", OUT / "dialect_probe.csv", len(d), f"{time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
