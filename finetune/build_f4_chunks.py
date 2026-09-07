#!/usr/bin/env python3
"""
build_f4_chunks.py — the F4 labeling-chunk table for E2.

WHAT THIS IS
------------
The owner ruled F4's scope on 2026-08-27 (HANDOFF §3, "F4 CONFIG RULED", and
re-confirmed post-demotion the same night):

    window rule = **W1 core**  ·  **full reflow_v1**  ·  guidance missing->NONE
    adopted at the labeling writer with an audit flag.

This script implements the first two. It turns the P5 corpus
(`data/filings_e2_v2.parquet`, 29,097 located sections) into
`data/f4/chunks_v1.parquet` — one row per ~350-word labeling window — using
`chunk.py`'s own constants, normalisation and packing arithmetic, plus P3's
ratified `reflow_v1` line rule.

    W1 core   = every section whose `stratum == "core"` (the continuity5
                stratum), over the full 2015-07 -> 2026-08 window. No date
                filter: that is what "W1" means (P3 §8, `p3_scale.py`'s
                `W1_full_core` rule = `sdf.index[core]`).
    reflow_v1 = keep every >=40-word line exactly as chunk.py does, and
                ADDITIONALLY glue runs of consecutive shorter lines into
                >=40-word blocks. Strictly additive: on prose-shaped text it is
                identical to the shipped rule. It recovers the table-shaped /
                word-per-line content that `get_text("\\n")` fragments into one
                short line per cell (P3 §7.1: 11.98M words in 1,634 sections).

THE WINDOW RULE IS APPLIED **BEFORE** DEDUP, not after. Restricting the corpus
changes which occurrence is "home", so W1-core is a full rebuild over the core
subset, exactly as `p3_scale.py` ran it. Consequence, stated plainly: a chunk's
`source_*` back-references cover **core-stratum sections only**. If the
extension stratum is ever labeled it is a separate campaign with its own home
selection, not an append.

CHUNK IDs
---------
Same construction as E1 (`chunk.py`), different namespace:

    paragraph_id = "E2P-"   + sha1(normalize_paragraph(line)).hexdigest()[:16]
    chunk_id     = "E2CHK-" + sha1("|".join(paragraph_ids)).hexdigest()[:16]

E1 uses `P-` / `CHK-`. The prefixes make a collision with E1's frozen
`data/labeling_corpus.parquet` impossible by construction — and it is verified
empirically anyway (`--verify-e1-disjoint`), because E1's 25 mega-caps are also
E2 universe members and byte-identical boilerplate across the two corpora is
expected, not surprising.

DEVIATION FROM chunk.py, DECLARED (P3's deviation 1, "the one-line F4 edit C3
predicts): `chunk.extract_prose_paragraphs` reads `row["ticker"]`, which is
NULL for every E2 filing. The home tie-break therefore uses `cik` zero-padded
to 10 characters in the slot chunk.py gives `ticker`. The tie-break only bites
for identical paragraphs filed on the same date by different filers.

PROOF THAT THE PACKING IS chunk.py's
------------------------------------
This module streams (the corpus is 628 MB of text; 2.15M canonical paragraphs
as `chunk.CanonicalParagraph` objects would not fit), so the packing arithmetic
is re-expressed over arrays rather than objects. It is not trusted on the
strength of that claim: `test_build_f4_chunks.py` rebuilds **E1's frozen
`data/labeling_corpus.parquet`** with this code (`e1_regression_config()` —
`data/filings.parquet`, as-is lines, ticker tie-break, `CHK-`/`P-` prefixes)
and asserts the 6,747 chunk_ids, texts, word counts, paragraph_ids and
`source_accession_numbers` come back identical.

Run:
    python3 finetune/build_f4_chunks.py                    # the real build
    python3 finetune/build_f4_chunks.py --verify-only      # shas + counts only

$0. Zero network. Zero Anthropic API calls. No GPU, no MLX.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import chunk as C  # noqa: E402  — MIN_PROSE_WORDS / TARGET_WINDOW_WORDS /
                   #               MIN_FLUSH_WORDS / normalize_paragraph

# --- frozen inputs, sha-pinned (P5's rebuild; HANDOFF §3 2026-08-27) ---------
CORPUS_PARQUET = REPO / "data" / "filings_e2_v2.parquet"
CORPUS_SHA256 = "15853e9f54902a933f0372869209a353ab3f052cb5c7dc1f897297f75b53f417"
AUDIT_PARQUET = REPO / "data" / "f3" / "v2" / "extraction_audit.parquet"
AUDIT_SHA256 = "207f392aa54c5151015093ecb34e5c57319f17e1ce22a3375ec1ac7f18e81eef"
MEMBERSHIP_DB = REPO / "data" / "filings_metadata_e2.db"

# E1, frozen, opened READ-ONLY and only for the disjointness check
E1_CORPUS_PARQUET = REPO / "data" / "labeling_corpus.parquet"

OUT_DIR = REPO / "data" / "f4"
OUT_PARQUET = OUT_DIR / "chunks_v1.parquet"
OUT_MANIFEST = OUT_DIR / "chunks_v1_manifest.json"

WINDOW_RULE = "W1_core"
LINE_RULE = "reflow_v1"
CHUNK_PREFIX = "E2CHK-"
PARA_PREFIX = "E2P-"

# The rubric's applicability matrix, measured from the frozen training targets
# (finetune/mlx_data_v12/{train,valid}.jsonl): which section types were ever
# asked for `guidance_direction`. It is used ONLY at the labeling writer, to
# scope the missing->NONE rule — never as prompt text (rubric v1.1, HANDOFF §3
# 2026-08-10: section_type must never appear in a prompt).
GUIDANCE_APPLICABLE_SECTION_TYPES = ("EX99_PRESS_RELEASE", "8K_BODY")

BATCH_ROWS = 200          # corpus streaming batch (P3's value: 620 MB text column)
WRITE_ROWS = 2000         # output row-group batch


# ===========================================================================
# the two line rules
# ===========================================================================

def as_is_lines(text: str) -> list:
    """chunk.py's shipped rule: keep every line with >= MIN_PROSE_WORDS words."""
    out = []
    for line in text.split("\n"):
        line = line.strip()
        if line and len(line.split()) >= C.MIN_PROSE_WORDS:
            out.append(line)
    return out


def reflow_v1(text: str) -> list:
    """P3's ratified STRICTLY ADDITIVE line rule (`p3_qa/p3_scale.py`).

    Keeps every >= MIN_PROSE_WORDS line exactly as the shipped rule does, and
    additionally glues each RUN of consecutive shorter lines into blocks,
    emitting a block as soon as it reaches MIN_PROSE_WORDS. A trailing run that
    never reaches the floor is dropped, exactly as the shipped rule drops a
    short line.

    ONE WRINKLE, REPRODUCED DELIBERATELY, NOT FIXED: a run that has NOT reached
    the floor is still flushed when the next >= 40-word line arrives, so
    reflow_v1 does emit some below-floor paragraphs. Measured on this corpus:
    629,050 of 3,007,084 reflowed lines (20.9%) are below the floor, carrying
    5.5% of the words; after dedup and packing, 13.6% of the shipped chunk
    table's paragraphs are below-floor, carrying 4.95% of its words, and
    exactly 2 of 317,081 chunks consist only of them. This is P3's ratified
    implementation and the one the owner's 314,211-chunk scope was quoted from
    — changing it here would silently move the ruled scope.

    This is NOT F3_SPEC §12.3's "join within block elements" variant — that one
    needs each section's HTML span re-parsed, i.e. a re-extraction. reflow_v1 is
    a pure function of the stored text, which is why P3 could run it over 100%
    of the corpus with zero sampling error, and why it is what the owner ruled.
    """
    out, buf, bw = [], [], 0
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        w = len(line.split())
        if w >= C.MIN_PROSE_WORDS:
            if buf:
                out.append(" ".join(buf))
                buf, bw = [], 0
            out.append(line)
        else:
            buf.append(line)
            bw += w
            if bw >= C.MIN_PROSE_WORDS:
                out.append(" ".join(buf))
                buf, bw = [], 0
    if buf and bw >= C.MIN_PROSE_WORDS:
        out.append(" ".join(buf))
    return out


LINE_RULES = {"reflow_v1": reflow_v1, "as_is": as_is_lines}


# ===========================================================================
# config
# ===========================================================================

@dataclass
class BuildConfig:
    """Everything the build depends on, in one place, so the E1 regression is a
    different config rather than a different code path."""
    corpus_path: Path = CORPUS_PARQUET
    corpus_sha256: str = CORPUS_SHA256          # "" disables the pin (E1 regression)
    stratum: str = "core"                       # None = every section
    line_rule: str = LINE_RULE
    tie_slot: str = "cik10"                     # "ticker" for E1
    chunk_prefix: str = CHUNK_PREFIX
    para_prefix: str = PARA_PREFIX
    window_rule: str = WINDOW_RULE
    out_parquet: Path = OUT_PARQUET
    membership_db: Path = MEMBERSHIP_DB         # None = no member-spell columns
    limit_sections: int = 0                     # >0 = smoke build
    meta_columns: tuple = (
        "cik", "company_name", "sector", "stratum", "accession_number", "form",
        "filing_date", "report_date", "section_type", "extraction_status",
        "extraction_confidence", "extraction_method", "flags",
    )


def e1_regression_config(out_parquet: Path) -> BuildConfig:
    """Rebuild E1's frozen labeling corpus with this code. Used by the tests."""
    return BuildConfig(
        corpus_path=REPO / "data" / "filings.parquet",
        corpus_sha256="",
        stratum=None,
        line_rule="as_is",
        tie_slot="ticker",
        chunk_prefix="CHK-",
        para_prefix="P-",
        window_rule="E1_regression",
        out_parquet=out_parquet,
        membership_db=None,
        meta_columns=(
            "ticker", "cik", "accession_number", "form", "filing_date",
            "section_type",
        ),
    )


# ===========================================================================
# helpers
# ===========================================================================

def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def assert_sha(path: Path, expected: str, what: str) -> str:
    actual = sha256_file(path)
    if expected and actual != expected:
        raise SystemExit(
            f"{what} sha256 MISMATCH — refusing to build.\n"
            f"  path     {path}\n  expected {expected}\n  actual   {actual}\n"
            f"The F4 corpus is pinned (HANDOFF §3, P5). If the corpus legitimately "
            f"moved, that is a new owner decision, not a constant to edit here."
        )
    return actual


def paragraph_id(prefix: str, normalized: str) -> str:
    return prefix + hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def chunk_id_for(prefix: str, paragraph_ids: list) -> str:
    return prefix + hashlib.sha1("|".join(paragraph_ids).encode("utf-8")).hexdigest()[:16]


# ===========================================================================
# pass A — sections, occurrences, dedup, packing (no text retained)
# ===========================================================================

def _scan_sections(cfg: BuildConfig):
    """Stream the corpus once. Returns (meta rows, occurrence arrays).

    Occurrence arrays are parallel numpy arrays, one entry per (section, line):
      h_hi/h_lo  the first 16 bytes of sha1(normalized line) — the dedup key.
                 h_hi's hex IS the paragraph_id body, so the id and the dedup
                 key are the same object as in chunk.py.
      wc         word count · pos  in-section line position · sidx  section index
    """
    import numpy as np
    import pyarrow.parquet as pq
    from array import array

    splitter = LINE_RULES[cfg.line_rule]
    cols = list(cfg.meta_columns) + ["text"]
    meta = []
    n_lines = array("i")
    h_hi, h_lo = array("Q"), array("Q")
    wcs, poss, sidx = array("i"), array("i"), array("i")

    pf = pq.ParquetFile(cfg.corpus_path)
    i = 0
    for batch in pf.iter_batches(batch_size=BATCH_ROWS, columns=cols):
        d = batch.to_pydict()
        for k in range(len(d["accession_number"])):
            if cfg.stratum is not None and d["stratum"][k] != cfg.stratum:
                continue
            if cfg.limit_sections and i >= cfg.limit_sections:
                break
            meta.append({c: d[c][k] for c in cfg.meta_columns})
            lines = splitter(d["text"][k] or "")
            for pos, line in enumerate(lines):
                dig = hashlib.sha1(C.normalize_paragraph(line).encode("utf-8")).digest()
                h_hi.append(int.from_bytes(dig[:8], "big"))
                h_lo.append(int.from_bytes(dig[8:16], "big"))
                wcs.append(len(line.split()))
                poss.append(pos)
                sidx.append(i)
            n_lines.append(len(lines))
            i += 1
        if cfg.limit_sections and i >= cfg.limit_sections:
            break

    occ = {
        "h_hi": np.frombuffer(h_hi, dtype="uint64").copy(),
        "h_lo": np.frombuffer(h_lo, dtype="uint64").copy(),
        "wc": np.frombuffer(wcs, dtype="int32").copy(),
        "pos": np.frombuffer(poss, dtype="int32").copy(),
        "sidx": np.frombuffer(sidx, dtype="int32").copy(),
    }
    return meta, occ, np.frombuffer(n_lines, dtype="int32").copy()


def _section_rank(meta: list, tie_slot: str):
    """chunk.py's home order over sections: (filing_date, ticker, accession,
    section_type). `ticker` -> zero-padded cik at E2 scale (declared deviation).

    Returns rank[sidx] — the position of that section in the global order.
    """
    import numpy as np

    if tie_slot == "ticker":
        slots = [str(m["ticker"]) for m in meta]
    else:
        slots = [str(m["cik"]).zfill(10) for m in meta]
    keys = [
        (m["filing_date"], slots[i], m["accession_number"], m["section_type"], i)
        for i, m in enumerate(meta)
    ]
    order = sorted(range(len(keys)), key=lambda i: keys[i])
    rank = np.empty(len(keys), dtype="int64")
    rank[np.asarray(order, dtype="int64")] = np.arange(len(keys), dtype="int64")
    return rank


def _source_keys(meta: list):
    """Sections collapse to SOURCE FILINGS for the back-reference lists.

    chunk.py keys the union on `(ticker, accession_number)`, not on the section
    — a paragraph appearing in both the MD&A and the Risk Factors of one filing
    is ONE source filing there, and must be here too, or every downstream
    every-occurrence count is inflated. `ticker` is NULL at E2 scale, so the key
    is `(cik, accession_number)`.

    Returns (key_of_sidx, keys) where keys[j] = (filing_date, cik, accession, form).
    """
    import numpy as np

    index, keys = {}, []
    key_of = np.empty(len(meta), dtype="int64")
    for i, m in enumerate(meta):
        slot = m["ticker"] if "ticker" in m else int(m["cik"])
        k = (slot, m["accession_number"])
        j = index.get(k)
        if j is None:
            j = len(keys)
            index[k] = j
            keys.append((m["filing_date"], int(m["cik"]), m["accession_number"], m["form"]))
        key_of[i] = j
    return key_of, keys


def _dedup_and_pack(occ, rank, cfg: BuildConfig, srckey_of_sidx=None):
    """Global exact-dedup -> home selection -> chunk.py's window packing.

    Returns a dict of compact arrays describing every chunk, plus the
    canonical-paragraph arrays they index into. No text is touched here.
    """
    import numpy as np

    n_occ = len(occ["h_hi"])
    occ_rank = rank[occ["sidx"]]

    # Group by dedup key; inside a group the FIRST row in (rank, pos) order is
    # the home occurrence — chunk.py's rule, expressed as a sort.
    order = np.lexsort((occ["pos"], occ_rank, occ["h_lo"], occ["h_hi"]))
    hi_s, lo_s = occ["h_hi"][order], occ["h_lo"][order]
    new_group = np.empty(n_occ, dtype=bool)
    new_group[0] = True
    new_group[1:] = (hi_s[1:] != hi_s[:-1]) | (lo_s[1:] != lo_s[:-1])
    group_of_sorted = np.cumsum(new_group) - 1          # 0..n_canonical-1
    n_canon = int(group_of_sorted[-1]) + 1 if n_occ else 0

    group_of_occ = np.empty(n_occ, dtype="int64")
    group_of_occ[order] = group_of_sorted

    head = np.flatnonzero(new_group)                    # index into `order`
    home_occ = order[head]                              # occurrence index of each home
    canon = {
        "h_hi": occ["h_hi"][home_occ],
        "home_sidx": occ["sidx"][home_occ],
        "home_pos": occ["pos"][home_occ],
        "wc": occ["wc"][home_occ],
    }

    # Walk each home section's home paragraphs in original order and pack them
    # into ~TARGET_WINDOW_WORDS windows (chunk.pack_windows, verbatim rules).
    corder = np.lexsort((canon["home_pos"], canon["home_sidx"]))
    for key in canon:
        canon[key] = canon[key][corder]

    c_sidx = canon["home_sidx"]
    c_wc = canon["wc"]
    starts, ends, words, chunk_sidx = [], [], [], []
    cur_sidx, w_start, w_words = None, 0, 0
    for idx in range(n_canon):
        s = int(c_sidx[idx])
        if s != cur_sidx:
            if cur_sidx is not None and w_words >= C.MIN_FLUSH_WORDS:
                starts.append(w_start); ends.append(idx); words.append(w_words)
                chunk_sidx.append(cur_sidx)
            cur_sidx, w_start, w_words = s, idx, 0
        w_words += int(c_wc[idx])
        if w_words >= C.TARGET_WINDOW_WORDS:
            starts.append(w_start); ends.append(idx + 1); words.append(w_words)
            chunk_sidx.append(s)
            w_start, w_words = idx + 1, 0
    if cur_sidx is not None and w_words >= C.MIN_FLUSH_WORDS:
        starts.append(w_start); ends.append(n_canon); words.append(w_words)
        chunk_sidx.append(cur_sidx)

    chunks = {
        "start": np.asarray(starts, dtype="int64"),
        "end": np.asarray(ends, dtype="int64"),
        "words": np.asarray(words, dtype="int64"),
        "sidx": np.asarray(chunk_sidx, dtype="int64"),
    }

    # every-occurrence attribution: which sections does each chunk's text
    # appear in, anywhere in the (window-restricted) corpus?
    chunk_of_canon = np.full(n_canon, -1, dtype="int64")
    for ci in range(len(chunks["start"])):
        chunk_of_canon[chunks["start"][ci]:chunks["end"][ci]] = ci
    # canon arrays were reordered by `corder`; map occurrence -> canon slot
    canon_slot = np.empty(n_canon, dtype="int64")
    canon_slot[corder] = np.arange(n_canon, dtype="int64")
    chunk_of_occ = chunk_of_canon[canon_slot[group_of_occ]]
    keep = chunk_of_occ >= 0
    src = (srckey_of_sidx[occ["sidx"][keep]] if srckey_of_sidx is not None
           else occ["sidx"][keep].astype("int64"))
    pairs = np.unique(np.stack([chunk_of_occ[keep], src], axis=1), axis=0)
    return canon, chunks, pairs, n_canon, n_occ


# ===========================================================================
# pass B — text, provenance, parquet
# ===========================================================================

def _member_spells(meta: list, db_path: Path):
    """(in_member_spell, in_member_spell_plus12m) per section, from the
    point-in-time universe membership table. Read-only; triage columns only —
    never a conditioning variable in a walk-forward (P4 §5.1 / P5 §8.2)."""
    import numpy as np

    n = len(meta)
    inside = np.zeros(n, dtype=bool)
    inside12 = np.zeros(n, dtype=bool)
    if db_path is None:
        return inside, inside12
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    spells = {}
    for cik, mfrom, mto in con.execute(
        "SELECT cik, member_from, member_to FROM universe_membership"
    ):
        spells.setdefault(int(cik), []).append((mfrom, mto or "9999-12-31"))
    con.close()

    def minus12(d):
        y, m, rest = int(d[:4]), int(d[5:7]), d[7:]
        return f"{y - 1:04d}-{m:02d}{rest}"

    for i, m in enumerate(meta):
        fd = m["filing_date"]
        for lo, hi in spells.get(int(m["cik"]), ()):
            if lo <= fd <= hi:
                inside[i] = True
            if minus12(lo) <= fd <= hi:
                inside12[i] = True
    return inside, inside12


def _arrow_schema(cfg: BuildConfig):
    import pyarrow as pa

    fields = [
        pa.field("chunk_id", pa.string()),
        pa.field("section_type", pa.string()),
        pa.field("text", pa.string()),
        pa.field("word_count", pa.int64()),
        pa.field("n_paragraphs", pa.int64()),
        pa.field("paragraph_ids", pa.list_(pa.string())),
        pa.field("home_cik", pa.int64()),
        pa.field("home_accession_number", pa.string()),
        pa.field("home_form", pa.string()),
        pa.field("home_filing_date", pa.string()),
        pa.field("source_ciks", pa.list_(pa.int64())),
        pa.field("source_accession_numbers", pa.list_(pa.string())),
        pa.field("source_filing_dates", pa.list_(pa.string())),
        pa.field("source_forms", pa.list_(pa.string())),
        pa.field("n_source_filings", pa.int64()),
    ]
    if "company_name" in cfg.meta_columns:
        fields += [
            pa.field("home_company_name", pa.string()),
            pa.field("home_sector", pa.string()),
            pa.field("home_stratum", pa.string()),
            pa.field("home_report_date", pa.string()),
            pa.field("home_extraction_status", pa.string()),
            pa.field("home_extraction_confidence", pa.string()),
            pa.field("home_extraction_method", pa.string()),
            pa.field("home_flags", pa.list_(pa.string())),
            pa.field("in_member_spell", pa.bool_()),
            pa.field("in_member_spell_plus12m", pa.bool_()),
        ]
    fields += [
        pa.field("window_rule", pa.string()),
        pa.field("line_rule", pa.string()),
        pa.field("guidance_applicable", pa.bool_()),
    ]
    return pa.schema(fields)


def _sort_chronological(path: Path, chunks, rank):
    """Re-order the written parquet into CHRONOLOGICAL row order.

    Pass B has to stream the 628 MB corpus in file order, so it emits in file
    order — and the F3 corpus is grouped by FORM (all 10-K/10-Q sections, then
    all 8-K/EX-99 ones). That order would make F4's nightly segments
    section-type-homogeneous, with two consequences worth 60 seconds of sorting
    to avoid:

      1. a campaign stopped early (HANDOFF §4: assume every long run gets
         killed) would hold every MD&A and Risk Factors chunk and NOT ONE press
         release — i.e. no guidance-applicable rows at all. Chronological order
         makes a stopped campaign a complete TIME PREFIX instead, which is
         exactly the shape a walk-forward study can use.
      2. per-night wall clock would not be comparable between nights, because
         MD&A passages are much longer than press-release passages.

    Order = the same key the home tie-break uses (filing_date, ticker/cik,
    accession, section_type) then in-section chunk position, so a filing's
    chunks stay contiguous and a night boundary can be filing-aligned.
    """
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq

    scan = np.lexsort((chunks["start"], chunks["sidx"]))          # the written order
    key_rank = rank[chunks["sidx"][scan]]
    key_start = chunks["start"][scan]
    perm = np.lexsort((key_start, key_rank))
    if np.array_equal(perm, np.arange(len(perm))):
        return
    table = pq.read_table(path).take(pa.array(perm))
    tmp = path.with_suffix(".sorting.parquet")
    pq.write_table(table, tmp)
    del table
    tmp.replace(path)


def _write_chunks(cfg: BuildConfig, meta, canon, chunks, pairs, n_lines, srckeys):
    """Second corpus pass: re-derive each home section's lines and emit rows."""
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq

    splitter = LINE_RULES[cfg.line_rule]
    schema = _arrow_schema(cfg)
    inside, inside12 = _member_spells(meta, cfg.membership_db)

    # chunks, in output order: home section (corpus row order), then position
    corder = np.lexsort((chunks["start"], chunks["sidx"]))
    c_start, c_end = chunks["start"][corder], chunks["end"][corder]
    c_words, c_sidx = chunks["words"][corder], chunks["sidx"][corder]
    # inverse permutation, so `pairs` (built on the pre-sort chunk index) maps
    new_of_old = np.empty(len(corder), dtype="int64")
    new_of_old[corder] = np.arange(len(corder), dtype="int64")
    pairs = pairs.copy()
    pairs[:, 0] = new_of_old[pairs[:, 0]]
    pairs = pairs[np.lexsort((pairs[:, 1], pairs[:, 0]))]
    pair_start = np.searchsorted(pairs[:, 0], np.arange(len(corder)), side="left")
    pair_end = np.searchsorted(pairs[:, 0], np.arange(len(corder)), side="right")

    # chunks grouped by home section (they are contiguous after the sort)
    chunk_start_of_sidx = np.searchsorted(c_sidx, np.arange(len(meta)), side="left")
    chunk_end_of_sidx = np.searchsorted(c_sidx, np.arange(len(meta)), side="right")

    has_meta = "company_name" in cfg.meta_columns
    cols = list(cfg.meta_columns) + ["text"]
    pf = pq.ParquetFile(cfg.corpus_path)
    writer = pq.ParquetWriter(cfg.out_parquet, schema)

    buf, n_written = [], 0
    src_dates = [s[0] for s in srckeys]
    src_cik = [s[1] for s in srckeys]
    src_acc = [s[2] for s in srckeys]
    src_form = [s[3] for s in srckeys]

    def flush():
        nonlocal buf, n_written
        if not buf:
            return
        table = pa.Table.from_pylist(buf, schema=schema)
        writer.write_table(table)
        n_written += len(buf)
        buf = []

    i = 0
    for batch in pf.iter_batches(batch_size=BATCH_ROWS, columns=cols):
        d = batch.to_pydict()
        for k in range(len(d["accession_number"])):
            if cfg.stratum is not None and d["stratum"][k] != cfg.stratum:
                continue
            if i >= len(meta):
                break
            lo, hi = int(chunk_start_of_sidx[i]), int(chunk_end_of_sidx[i])
            if lo == hi:
                i += 1
                continue
            lines = splitter(d["text"][k] or "")
            if len(lines) != int(n_lines[i]):
                raise AssertionError(
                    f"section {d['accession_number'][k]}/{d['section_type'][k]}: pass B "
                    f"produced {len(lines)} lines, pass A saw {n_lines[i]}. The line rule "
                    f"is not deterministic — refusing to write a corpus."
                )
            m = meta[i]
            for ci in range(lo, hi):
                s, e = int(c_start[ci]), int(c_end[ci])
                # h_hi's hex IS sha1(normalized)[:16] — see paragraph_id()
                pids = [
                    cfg.para_prefix + format(int(canon["h_hi"][j]), "016x")
                    for j in range(s, e)
                ]
                text = "\n\n".join(lines[int(canon["home_pos"][j])] for j in range(s, e))
                sids = pairs[pair_start[ci]:pair_end[ci], 1]
                order = sorted(
                    (int(x) for x in sids),
                    key=lambda t: (src_dates[t], src_cik[t], src_acc[t]),
                )
                row = {
                    "chunk_id": chunk_id_for(cfg.chunk_prefix, pids),
                    "section_type": m["section_type"],
                    "text": text,
                    "word_count": int(c_words[ci]),
                    "n_paragraphs": e - s,
                    "paragraph_ids": pids,
                    "home_cik": int(m["cik"]),
                    "home_accession_number": m["accession_number"],
                    "home_form": m["form"],
                    "home_filing_date": m["filing_date"],
                    "source_ciks": [src_cik[t] for t in order],
                    "source_accession_numbers": [src_acc[t] for t in order],
                    "source_filing_dates": [src_dates[t] for t in order],
                    "source_forms": [src_form[t] for t in order],
                    "n_source_filings": len(order),
                    "window_rule": cfg.window_rule,
                    "line_rule": cfg.line_rule,
                    "guidance_applicable": m["section_type"] in GUIDANCE_APPLICABLE_SECTION_TYPES,
                }
                if has_meta:
                    row.update({
                        "home_company_name": m["company_name"],
                        "home_sector": m["sector"],
                        "home_stratum": m["stratum"],
                        "home_report_date": m["report_date"],
                        "home_extraction_status": m["extraction_status"],
                        "home_extraction_confidence": m["extraction_confidence"],
                        "home_extraction_method": m["extraction_method"],
                        "home_flags": list(m["flags"] or []),
                        "in_member_spell": bool(inside[i]),
                        "in_member_spell_plus12m": bool(inside12[i]),
                    })
                buf.append(row)
            if len(buf) >= WRITE_ROWS:
                flush()
            i += 1
        if i >= len(meta):
            break
    flush()
    writer.close()
    return n_written


# ===========================================================================
# build
# ===========================================================================

def build(cfg: BuildConfig, verbose: bool = True) -> dict:
    t0 = time.perf_counter()
    corpus_sha = assert_sha(cfg.corpus_path, cfg.corpus_sha256, "corpus")
    cfg.out_parquet.parent.mkdir(parents=True, exist_ok=True)

    meta, occ, n_lines = _scan_sections(cfg)
    t_scan = time.perf_counter() - t0
    if verbose:
        print(f"  pass A: {len(meta)} sections · {len(occ['h_hi'])} lines "
              f"({t_scan:.0f}s)", file=sys.stderr, flush=True)

    rank = _section_rank(meta, cfg.tie_slot)
    srckey_of_sidx, srckeys = _source_keys(meta)
    canon, chunks, pairs, n_canon, n_occ = _dedup_and_pack(occ, rank, cfg, srckey_of_sidx)
    if verbose:
        print(f"  dedup:  {n_canon} canonical of {n_occ} "
              f"({1 - n_canon / n_occ:.1%} duplicate) · {len(chunks['start'])} chunks",
              file=sys.stderr, flush=True)

    n_written = _write_chunks(cfg, meta, canon, chunks, pairs, n_lines, srckeys)
    if n_written != len(chunks["start"]):
        raise AssertionError(f"wrote {n_written} rows, packed {len(chunks['start'])}")
    _sort_chronological(cfg.out_parquet, chunks, rank)

    sections_with_chunks = len(set(int(s) for s in chunks["sidx"]))
    return {
        "corpus": {"path": str(cfg.corpus_path), "sha256": corpus_sha},
        "window_rule": cfg.window_rule,
        "line_rule": cfg.line_rule,
        "stratum": cfg.stratum,
        "tie_break_slot": cfg.tie_slot,
        "constants": {
            "MIN_PROSE_WORDS": C.MIN_PROSE_WORDS,
            "TARGET_WINDOW_WORDS": C.TARGET_WINDOW_WORDS,
            "MIN_FLUSH_WORDS": C.MIN_FLUSH_WORDS,
            "source": "chunk.py (imported, never re-declared)",
        },
        "n_sections": len(meta),
        "n_lines": int(n_occ),
        "n_canonical_paragraphs": int(n_canon),
        "dedup_rate": round(1 - n_canon / n_occ, 4) if n_occ else None,
        "n_chunks": int(len(chunks["start"])),
        "n_sections_with_zero_chunks": len(meta) - sections_with_chunks,
        "parquet": {
            "path": str(cfg.out_parquet),
            "sha256": sha256_file(cfg.out_parquet),
            "bytes": cfg.out_parquet.stat().st_size,
        },
        "wall_seconds": round(time.perf_counter() - t0, 1),
    }


# ===========================================================================
# verification
# ===========================================================================

def verify(parquet_path: Path = OUT_PARQUET) -> dict:
    """chunk-id uniqueness, disjointness from E1, and the headline census."""
    import pandas as pd
    import pyarrow.parquet as pq

    ids = pq.read_table(parquet_path, columns=["chunk_id"])["chunk_id"].to_pylist()
    n_dupe = len(ids) - len(set(ids))
    e1 = set(pd.read_parquet(E1_CORPUS_PARQUET, columns=["chunk_id"])["chunk_id"])
    overlap = sorted(set(ids) & e1)

    tbl = pq.read_table(
        parquet_path,
        columns=["section_type", "word_count", "home_filing_date", "home_sector",
                 "home_extraction_status", "n_source_filings"],
    ).to_pandas()
    return {
        "n_chunks": len(ids),
        "n_duplicate_chunk_ids": n_dupe,
        "chunk_ids_unique": n_dupe == 0,
        "n_colliding_with_E1_labeling_corpus": len(overlap),
        "e1_collision_examples": overlap[:5],
        "by_section_type": {k: int(v) for k, v in tbl["section_type"].value_counts().items()},
        "by_sector": {k: int(v) for k, v in tbl["home_sector"].value_counts().items()},
        "by_extraction_status": {
            k: int(v) for k, v in tbl["home_extraction_status"].value_counts().items()
        },
        "by_era": {
            "pre2019": int((tbl["home_filing_date"].str[:4].astype(int) <= 2018).sum()),
            "2019plus": int((tbl["home_filing_date"].str[:4].astype(int) >= 2019).sum()),
        },
        "word_count": {
            "mean": round(float(tbl["word_count"].mean()), 1),
            "p50": int(tbl["word_count"].median()),
            "p95": int(tbl["word_count"].quantile(0.95)),
            "p99": int(tbl["word_count"].quantile(0.99)),
            "max": int(tbl["word_count"].max()),
        },
        "n_source_filings": {
            "mean": round(float(tbl["n_source_filings"].mean()), 2),
            "max": int(tbl["n_source_filings"].max()),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(OUT_PARQUET))
    ap.add_argument("--limit-sections", type=int, default=0,
                    help="smoke build over the first N core sections (not a deliverable)")
    ap.add_argument("--verify-only", action="store_true",
                    help="re-run the census/uniqueness checks on an existing parquet")
    args = ap.parse_args()

    out = Path(args.out)
    if args.verify_only:
        print(json.dumps(verify(out), indent=2))
        return 0

    assert_sha(AUDIT_PARQUET, AUDIT_SHA256, "extraction audit")
    cfg = BuildConfig(out_parquet=out, limit_sections=args.limit_sections)
    print(f"building {out} — {cfg.window_rule} x {cfg.line_rule}", file=sys.stderr)
    report = build(cfg)
    report["audit_parquet"] = {"path": str(AUDIT_PARQUET), "sha256": AUDIT_SHA256}
    if not args.limit_sections:
        report["verification"] = verify(out)
        OUT_MANIFEST.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
