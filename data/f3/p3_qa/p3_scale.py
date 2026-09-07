"""P3 / F3_SPEC §12 — F4-scale re-derivation from the REAL 28,900-section output.

Uses chunk.py's own pure functions and constants (imported, never re-implemented):
`normalize_paragraph`, `MIN_PROSE_WORDS`, `TARGET_WINDOW_WORDS`, `MIN_FLUSH_WORDS`,
and chunk.py's home tie-break and packing rules.

Two documented deviations, both forced and both named:

 1. `chunk.extract_prose_paragraphs` reads `row["ticker"]`; F3's corpus is
    CIK-keyed (F3_SPEC R6/C3 — `ticker` is NULL for all 45,545 E2 filings).
    The home tie-break therefore uses `cik` zero-padded to 10 chars in the
    slot chunk.py gives `ticker`. This is exactly the one-line F4 edit C3
    predicts; the tie-break only bites for identical paragraphs filed on the
    same date by different filers.
 2. Memory: the corpus is 620 MB of text and `build_canonical_paragraphs`
    holds every occurrence's text. This driver streams the parquet and keeps
    only a 16-byte digest, word count, position and section index per
    occurrence (§12.1's instruction). Chunk *counts* are therefore exact;
    chunk *text* is never materialised.

Read-only. No corpus artifact is written (§12.5) — counts only.
"""
import sys, hashlib, sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import chunk as C

OUT = ROOT / "data/f3/p3_qa"
CORPUS = ROOT / "data/filings_e2.parquet"
DB = ROOT / "data/filings_metadata_e2.db"


def prose_lines(text):
    """chunk.extract_prose_paragraphs's rule, text-only."""
    return [ln.strip() for ln in text.split("\n")
            if ln.strip() and len(ln.strip().split()) >= C.MIN_PROSE_WORDS]


def prose_lines_reflow(text):
    """reflow_v1 -- STRICTLY ADDITIVE variant, named and defined here.

    Keeps every >=MIN_PROSE_WORDS line exactly as the shipped rule does, and
    additionally glues each RUN of consecutive shorter lines into blocks,
    emitting a block as soon as it reaches MIN_PROSE_WORDS. On prose-shaped
    text it is identical to the shipped rule; the delta is exactly the
    table-shaped content that `get_text("\\n")` fragments into one short line
    per cell (F3_SPEC C16).

    This is NOT F3_SPEC §12.3's "join within block elements" variant: that one
    needs the section's HTML span re-parsed, i.e. a re-extraction. reflow_v1
    is a pure function of the stored text, so it runs over 100% of the corpus
    with zero sampling error instead of 200 sections with an extrapolation
    band. The substitution is deliberate and is reported as such.
    """
    out, buf, bw = [], [], 0
    for ln in text.split("\n"):
        ln = ln.strip()
        if not ln:
            continue
        w = len(ln.split())
        if w >= C.MIN_PROSE_WORDS:
            if buf:
                out.append(" ".join(buf)); buf, bw = [], 0
            out.append(ln)
        else:
            buf.append(ln); bw += w
            if bw >= C.MIN_PROSE_WORDS:
                out.append(" ".join(buf)); buf, bw = [], 0
    if buf and bw >= C.MIN_PROSE_WORDS:
        out.append(" ".join(buf))
    return out


def scan(splitter):
    """One streaming pass over the corpus. Returns (sections_df, occ_df)."""
    from array import array
    secs = []
    h_hi, h_lo = array("Q"), array("Q")           # 8 bytes/elem, not 32 (list of ints)
    wcs, poss, sidx = array("i"), array("i"), array("i")
    f = pq.ParquetFile(CORPUS)
    cols = ["cik", "accession_number", "form", "filing_date", "section_type",
            "stratum", "sector", "text"]
    i = 0
    for b in f.iter_batches(batch_size=200, columns=cols):
        d = b.to_pydict()
        for k in range(len(d["cik"])):
            secs.append((d["cik"][k], d["accession_number"][k], d["form"][k],
                         d["filing_date"][k], d["section_type"][k],
                         d["stratum"][k], d["sector"][k]))
            for pos, ln in enumerate(splitter(d["text"][k])):
                dg = hashlib.blake2b(C.normalize_paragraph(ln).encode("utf-8"),
                                     digest_size=16).digest()
                h_hi.append(int.from_bytes(dg[:8], "big"))
                h_lo.append(int.from_bytes(dg[8:], "big"))
                wcs.append(len(ln.split())); poss.append(pos); sidx.append(i)
            i += 1
    sdf = pd.DataFrame(secs, columns=["cik", "accession_number", "form",
                                      "filing_date", "section_type", "stratum", "sector"])
    odf = pd.DataFrame({"h_hi": np.frombuffer(h_hi, dtype="uint64"),
                        "h_lo": np.frombuffer(h_lo, dtype="uint64"),
                        "wc": np.frombuffer(wcs, dtype="int32"),
                        "pos": np.frombuffer(poss, dtype="int32"),
                        "sidx": np.frombuffer(sidx, dtype="int32")})
    return sdf, odf


def section_rank(sdf):
    """chunk.py's home order: (filing_date, ticker, accession, section_type, position).
    ticker -> zero-padded cik (deviation 1)."""
    key = sdf.assign(_t=sdf.cik.astype(str).str.zfill(10))
    order = key.sort_values(["filing_date", "_t", "accession_number", "section_type"]).index
    rank = pd.Series(np.arange(len(order)), index=order).sort_index()
    return rank.values


def pack_counts(home_df):
    """chunk.pack_windows's arithmetic, counts only.
    home_df: one row per canonical paragraph, cols [sidx, pos, wc]."""
    home_df = home_df.sort_values(["sidx", "pos"])
    n_chunks, chunk_sidx = 0, []
    cur_sidx, ww = None, 0
    for s, w in zip(home_df.sidx.values, home_df.wc.values):
        if s != cur_sidx:
            if cur_sidx is not None and ww >= C.MIN_FLUSH_WORDS:
                n_chunks += 1; chunk_sidx.append(cur_sidx)
            cur_sidx, ww = s, 0
        ww += int(w)
        if ww >= C.TARGET_WINDOW_WORDS:
            n_chunks += 1; chunk_sidx.append(s); ww = 0
    if cur_sidx is not None and ww >= C.MIN_FLUSH_WORDS:
        n_chunks += 1; chunk_sidx.append(cur_sidx)
    return n_chunks, pd.Series(chunk_sidx, dtype="int32")


def run_rule(name, sdf, odf, keep_sidx, rank):
    o = odf[odf.sidx.isin(keep_sidx)] if keep_sidx is not None else odf
    if len(o) == 0:
        return dict(rule=name, sections=0, raw_paras=0, canonical=0, dedup_rate=0.0, chunks=0)
    o = o.assign(_r=rank[o.sidx.values])
    o = o.sort_values(["_r", "pos"])
    home = o.drop_duplicates(["h_hi", "h_lo"], keep="first")
    n_chunks, chunk_sidx = pack_counts(home[["sidx", "pos", "wc"]])
    meta = sdf.loc[chunk_sidx.values] if len(chunk_sidx) else sdf.iloc[0:0]
    sec_ids = keep_sidx if keep_sidx is not None else sdf.index
    res = dict(rule=name, sections=len(sec_ids), raw_paras=len(o),
               canonical=len(home), dedup_rate=round(1 - len(home) / len(o), 4),
               chunks=n_chunks,
               sections_zero_chunks=len(sec_ids) - meta.index.nunique())
    for k, v in meta.section_type.value_counts().items():
        res[f"chunks_{k}"] = int(v)
    for k, v in meta.stratum.value_counts().items():
        res[f"chunks_{k}"] = int(v)
    era = (meta.filing_date.str[:4].astype(int) <= 2018).map({True: "pre2019", False: "2019plus"})
    for k, v in era.value_counts().items():
        res[f"chunks_{k}"] = int(v)
    return res


def main():
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    mem = pd.read_sql("SELECT cik, member_from, member_to FROM universe_membership", con)
    con.close()
    mem["member_to"] = mem.member_to.fillna("9999-12-31")

    results = []
    for variant, splitter in (("as_is", prose_lines), ("reflow_v1", prose_lines_reflow)):
        print(f"--- scanning corpus, variant={variant} ---", flush=True)
        sdf, odf = scan(splitter)
        print(f"    sections={len(sdf)} occurrences={len(odf)}", flush=True)
        rank = section_rank(sdf)

        fd = sdf.filing_date.values
        inside = np.zeros(len(sdf), bool)
        inside_m12 = np.zeros(len(sdf), bool)
        for cik, g in mem.groupby("cik"):
            sel = (sdf.cik.values == cik)
            if not sel.any():
                continue
            for _, sp in g.iterrows():
                lo, hi = sp.member_from, sp.member_to
                lo12 = (pd.Timestamp(lo) - pd.DateOffset(months=12)).strftime("%Y-%m-%d")
                inside |= sel & (fd >= lo) & (fd <= hi)
                inside_m12 |= sel & (fd >= lo12) & (fd <= hi)
        core = (sdf.stratum.values == "core")

        rules = {
            "W1_full": None,
            "W1_full_core": sdf.index[core],
            "W2_spell_plus12m": sdf.index[inside_m12],
            "W2_spell_plus12m_core": sdf.index[inside_m12 & core],
            "W3_spell_only": sdf.index[inside],
            "W3_spell_only_core": sdf.index[inside & core],
        }
        for name, keep in rules.items():
            r = run_rule(name, sdf, odf, keep, rank)
            r["variant"] = variant
            results.append(r)
            print(f"  {variant:10s} {name:24s} sections={r['sections']:6d} "
                  f"paras={r['raw_paras']:8d} canon={r['canonical']:8d} "
                  f"dedup={r['dedup_rate']:.3f} chunks={r['chunks']:7d}", flush=True)
        del sdf, odf

    df = pd.DataFrame(results)
    df.to_csv(ROOT / "data/f3/p3_qa/f4_scale.csv", index=False)
    # labeling-time translation: measured student throughput (epoch-1 held-out eval)
    df["hours_at_1068_per_h"] = (df.chunks / 1068).round(1)
    df["overnights_10h"] = (df.chunks / 1068 / 10).round(2)
    df.to_csv(ROOT / "data/f3/p3_qa/f4_scale.csv", index=False)
    print("\n", df[["variant", "rule", "sections", "chunks", "hours_at_1068_per_h",
                    "overnights_10h"]].to_string(index=False))


if __name__ == "__main__":
    main()
