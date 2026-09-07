"""P4: independent re-derivation of the F4-scale chunk counts.
Written from chunk.py's semantics, NOT copied from p3_scale.py.
Step A: validate the streaming approach against chunk.py's REAL
build_canonical_paragraphs + pack_windows on a bounded subset.
Step B: apply it to the full corpus for W1_full and W2_spell_plus12m_core."""
import sys, sqlite3
from pathlib import Path
ROOT = Path("/Users/vihanpatil/personal/projects/FinScreen")
sys.path.insert(0, str(ROOT))
import pandas as pd, numpy as np, pyarrow.parquet as pq
import chunk as C

CORPUS = ROOT / "data/filings_e2.parquet"

def paras_of(text):
    out, pos = [], 0
    for ln in text.split("\n"):
        ln = ln.strip()
        if not ln: continue
        w = len(ln.split())
        if w >= C.MIN_PROSE_WORDS:
            out.append((pos, ln, w)); pos += 1
    return out

# ---------- Step A: ground-truth validation on a bounded subset ----------
sub = pq.ParquetFile(CORPUS)
rows = []
for b in sub.iter_batches(batch_size=200, columns=["cik","accession_number","form","filing_date","section_type","text"]):
    d = b.to_pydict()
    rows.append(pd.DataFrame(d))
    if sum(len(r) for r in rows) >= 600: break
gt = pd.concat(rows, ignore_index=True).head(600)
gt["ticker"] = gt.cik.astype(str).str.zfill(10)     # same deviation-1 substitution
real_chunks = C.pack_windows(C.build_canonical_paragraphs(gt))
print("STEP A ground truth (chunk.py's own functions, 600 sections):", len(real_chunks))

# my streaming version on the same 600
occ = []
for i, r in gt.iterrows():
    for pos, ln, w in paras_of(r.text):
        occ.append((i, pos, w, C.normalize_paragraph(ln)))
o = pd.DataFrame(occ, columns=["si","pos","wc","norm"])
key = gt.assign(_t=gt.ticker)
rank = pd.Series(np.arange(len(gt)),
                 index=key.sort_values(["filing_date","_t","accession_number","section_type"]).index).sort_index()
o["_r"] = rank.values[o.si.values]
o = o.sort_values(["_r","pos"], kind="mergesort")
home = o.drop_duplicates("norm", keep="first")

def count_chunks(home):
    n = 0
    for si, g in home.groupby("si", sort=False):
        ww = 0
        for w in g.sort_values("pos").wc.values:
            ww += int(w)
            if ww >= C.TARGET_WINDOW_WORDS:
                n += 1; ww = 0
        if ww >= C.MIN_FLUSH_WORDS: n += 1
    return n
mine = count_chunks(home)
print("STEP A my streaming re-implementation:          ", mine,
      "  ->", "AGREE" if mine == len(real_chunks) else "*** DISAGREE ***")

# ---------- Step B: full corpus ----------
print("\nSTEP B full corpus scan...", flush=True)
import hashlib
from array import array
secs = []; hh, hl, wcs, poss, sidx = array("Q"), array("Q"), array("i"), array("i"), array("i")
pf = pq.ParquetFile(CORPUS); i = 0
for b in pf.iter_batches(batch_size=200, columns=["cik","accession_number","form","filing_date","section_type","stratum","text"]):
    d = b.to_pydict()
    for k in range(len(d["cik"])):
        secs.append((d["cik"][k], d["accession_number"][k], d["filing_date"][k], d["section_type"][k], d["stratum"][k]))
        for pos, ln, w in paras_of(d["text"][k]):
            dg = hashlib.sha1(C.normalize_paragraph(ln).encode()).digest()   # sha1, not blake2b
            hh.append(int.from_bytes(dg[:8],"big")); hl.append(int.from_bytes(dg[8:16],"big"))
            wcs.append(w); poss.append(pos); sidx.append(i)
        i += 1
S = pd.DataFrame(secs, columns=["cik","accession_number","filing_date","section_type","stratum"])
O = pd.DataFrame({"hh":np.frombuffer(hh,dtype="uint64"),"hl":np.frombuffer(hl,dtype="uint64"),
                  "wc":np.frombuffer(wcs,dtype="int32"),"pos":np.frombuffer(poss,dtype="int32"),
                  "si":np.frombuffer(sidx,dtype="int32")})
print("  sections", len(S), "occurrences", len(O))
K = S.assign(_t=S.cik.astype(str).str.zfill(10))
RANK = pd.Series(np.arange(len(S)),
                 index=K.sort_values(["filing_date","_t","accession_number","section_type"]).index).sort_index().values

con = sqlite3.connect(f"file:{ROOT}/data/filings_metadata_e2.db?mode=ro", uri=True)
mem = pd.read_sql("SELECT cik, member_from, member_to FROM universe_membership", con); con.close()
mem["member_to"] = mem.member_to.fillna("9999-12-31")
fd = S.filing_date.values; ins12 = np.zeros(len(S), bool)
for cik, g in mem.groupby("cik"):
    sel = (S.cik.values == cik)
    if not sel.any(): continue
    for _, sp in g.iterrows():
        lo12 = (pd.Timestamp(sp.member_from) - pd.DateOffset(months=12)).strftime("%Y-%m-%d")
        ins12 |= sel & (fd >= lo12) & (fd <= sp.member_to)
core = (S.stratum.values == "core")

def run(mask, label, claim):
    keep = set(np.flatnonzero(mask).tolist()) if mask is not None else None
    oo = O[O.si.isin(keep)] if keep is not None else O
    oo = oo.assign(_r=RANK[oo.si.values]).sort_values(["_r","pos"], kind="mergesort")
    hm = oo.drop_duplicates(["hh","hl"], keep="first")
    n = 0
    hm = hm.sort_values(["si","pos"], kind="mergesort")
    cur, ww = None, 0
    for s, w in zip(hm.si.values, hm.wc.values):
        if s != cur:
            if cur is not None and ww >= C.MIN_FLUSH_WORDS: n += 1
            cur, ww = s, 0
        ww += int(w)
        if ww >= C.TARGET_WINDOW_WORDS: n += 1; ww = 0
    if cur is not None and ww >= C.MIN_FLUSH_WORDS: n += 1
    print(f"  {label:24s} sections={int(mask.sum()) if mask is not None else len(S):6d} "
          f"paras={len(oo):8d} canon={len(hm):8d} chunks={n:7d}  P3={claim:7d}  "
          f"{'MATCH' if n==claim else '*** MISMATCH ***'}")

run(np.ones(len(S),bool), "W1_full", 199403)
run(ins12 & core, "W2_spell_plus12m_core", 99965)
run(core, "W1_full_core", 146571)
