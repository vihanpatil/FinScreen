"""P4b: FULL census of all 779 EXPECTED_ABSENT rows in
`data/f3/extraction_audit.parquet`.

Why: P4 §2 proved the 779 `EXPECTED_ABSENT` rows carry `item_absent_from_toc`
-- the same conflated reason code P3 measured 39.4% wrong on the FAIL side --
and that P3's census frame (`fail_recovery.csv`) was `status == 'FAIL'` only,
so this population was never examined. P4's seeded 80-row replay found 11
(13.8%) misclassified. This script runs the same replay over ALL 779 and adds
the two things the 80-row replay did not do:

  * for R2 rows it actually RESOLVES the later anchor to a span and measures
    the recovered text (word count, char count, floor clearing, whether the
    end boundary ran to EOF);
  * for every row it records a span-plausibility verdict against the measured
    (10-Q, RISK_FACTORS) anchor-located distribution, reported BOTH in P4's
    0.5-2x-median form (for comparability) and in a bimodal form (because
    that distribution is strongly bimodal -- see the report).

Method is P4's (`p4_expected_absent.py` + `p4_f1_vs_f2.py`), extended, not
reinvented. Every locate decision uses `extract.py`'s own shipped functions.

Cache-only, ZERO network: document bytes come through
`extract.read_cached_document`, which raises `CacheMiss` and cannot fetch.
The metadata DB is opened `mode=ro`.

Resumable: results are appended to `census_rows.jsonl`; a re-run skips
accessions already present.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from multiprocessing import Pool

ROOT = "/Users/vihanpatil/personal/projects/FinScreen"
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

import extract as E  # noqa: E402

OUT_DIR = os.path.join(ROOT, "data/f3/p4b_ea_census")
JSONL = os.path.join(OUT_DIR, "census_rows.jsonl")
DB = os.path.join(ROOT, "data/filings_metadata_e2.db")

TARGET_ITEM = "1A"
KEYWORDS = ("risk factor",)
FORM, SECTION = "10-Q", "RISK_FACTORS"

WORD_FLOOR = E.MIN_SECTION_WORDS[(FORM, SECTION)]      # 15
CHAR_GATE = E.MIN_SECTION_CHARS                         # 30

# The shipped end-patterns for (10-Q, RISK_FACTORS): Item 2 Unregistered,
# Item 3 Defaults, Item 4 Mine Safety, Item 5 Other Information, Item 6
# Exhibits. `locate_item_section_by_heading_regex` already applies them; the
# anchor path does NOT (it ends at the next differing TOC anchor, or EOF).
_START_PAT, END_PATS = E.FALLBACK_SECTIONS[(FORM, SECTION)]

# A real Part II Item 1A heading is followed by a sentence start ("There have
# been no material changes...", "In addition to the other information...", a
# risk-factor title). A prose CROSS-REFERENCE reads "...Item 1A. Risk Factors
# in our 2015 Annual Report..." -- a lowercase preposition/participle right
# after the title. This is the XOM failure mode `extract.py:1220-1232` names.
_CROSSREF_NEXT = re.compile(
    r"^(in|of|to|and|or|for|from|under|above|below|included|contained|"
    r"described|discussed|set|appearing|beginning|referred|listed|"
    r"presented|incorporated|therein|thereto)\b")
_HEADING_RE = re.compile(r"item\s*1\s*\(?a\)?[\s\xa0.:\-–—]{0,20}risk\s*factors",
                         re.IGNORECASE)


def guarded_end(text: str) -> int:
    """Where the section would end if the anchor span were closed by the same
    end-patterns the heading-regex path already uses. Measures whether a
    span-guarded F1 produces a defensible section."""
    end = len(text)
    for ep in END_PATS:
        m = ep.search(text, 30)
        if m and m.start() < end:
            end = m.start()
    return end


def head_is_crossref(text: str) -> bool | None:
    """True when the text opens on an Item 1A title that is immediately
    continued by a preposition -- i.e. a cross-reference sentence, not a
    section start. None when no Item 1A heading is found near the start."""
    m = _HEADING_RE.search(text[:400])
    if m is None:
        return None
    after = text[m.end():].lstrip("  .,:;—–-“\"'")
    return bool(_CROSSREF_NEXT.match(after))

_con = None


def con():
    global _con
    if _con is None:
        _con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    return _con


def rel_path(acc, fn, cik):
    r = con().execute(
        "SELECT relative_path FROM filing_documents WHERE accession_number=? AND filename=?",
        (acc, fn)).fetchone()
    if r and r[0]:
        return r[0]
    return f"/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{fn}"


def matching_entries(toc):
    """TOC entries the shipped `locate_item_section_by_anchor` would consider:
    item_no == '1A' AND row_text carries a required keyword (whitespace-
    insensitive on both sides, exactly as the shipped function does)."""
    out = []
    for i, e in enumerate(toc):
        if e.item_no != TARGET_ITEM:
            continue
        rt = re.sub(r"\s+", "", e.row_text)
        if not any(re.sub(r"\s+", "", kw) in rt for kw in KEYWORDS):
            continue
        out.append(i)
    return out


def anchor_span(html, toc, idx):
    """Reproduce `locate_item_section_by_anchor`'s span arithmetic for the
    matching entry at `idx` (rather than only for the FIRST matching entry,
    which is the shipped behaviour and the defect under test)."""
    off = E.find_anchor_offset(html, toc[idx].anchor_id)
    if off is None:
        return None
    start = E._end_of_enclosing_tag(html, off)
    end = len(html)
    end_at_eof = True
    for e2 in toc[idx + 1:]:
        if e2.item_no != TARGET_ITEM:
            cand = E.find_anchor_offset(html, e2.anchor_id, after=start)
            if cand is not None and cand > start:
                end = E._start_of_enclosing_tag(html, cand)
                end_at_eof = False
            break
    if end <= start:
        return None
    return start, end, end_at_eof


def classify(row):
    acc = row["accession_number"]
    rec = {
        "accession_number": acc,
        "cik": int(row["cik"]),
        "company_name": row["company_name"],
        "sector": row["sector"],
        "stratum": row["stratum"],
        "filing_date": str(row["filing_date"])[:10],
        "section_type": row["section_type"],
        "form": row["form"],
        "source_document": row["source_document"],
    }
    try:
        raw = E.read_cached_document(rel_path(acc, row["source_document"], row["cik"]))
        html = E.strip_sgml_document_wrapper(raw)
        soup = BeautifulSoup(html, E._PARSER)
        toc = E.find_toc_item_anchors(soup)
    except Exception as ex:
        rec.update(verdict="ERROR", error=f"{type(ex).__name__}: {ex}")
        return rec

    idxs = matching_entries(toc)
    resolved = [(i, E.find_anchor_offset(html, toc[i].anchor_id)) for i in idxs]
    n_res = sum(1 for _, o in resolved if o is not None)
    rec.update(n_toc_entries=len(toc), n_matching=len(idxs), n_resolvable=n_res,
               anchor_ids=[toc[i].anchor_id for i in idxs][:6])

    # --- shipped-behaviour sanity: confirm the shipped locate really returns
    # None here, i.e. this row really is on the EXPECTED_ABSENT path.
    shipped = E.locate_item_section_by_anchor(html, toc, TARGET_ITEM, KEYWORDS)
    rec["shipped_span_is_none"] = shipped is None

    # --- R2 arm: a LATER matching entry resolves to a real span -------------
    if idxs and n_res > 0 and resolved[0][1] is None:
        verdict = "R2_first_dangling_later_resolves"
    elif idxs and resolved[0][1] is not None:
        # the first entry DID resolve -- the shipped span must have failed on
        # the end-boundary arithmetic (end <= start). Rare; recorded separately.
        verdict = "R4_first_resolves_span_arithmetic_failed"
    elif idxs:
        verdict = "R3_all_matching_dangling"
    else:
        verdict = "R1_genuinely_absent_from_toc"
    rec["verdict"] = verdict

    if verdict in ("R2_first_dangling_later_resolves", "R4_first_resolves_span_arithmetic_failed"):
        got = None
        for i, o in resolved:
            if o is None:
                continue
            sp = anchor_span(html, toc, i)
            if sp is None:
                continue
            got = (i, sp)
            break
        if got is not None:
            i, (s, e, eof) = got
            text = E.html_fragment_to_text(html[s:e])
            words = text.split()
            g = text[:guarded_end(text)].strip()
            gw = g.split()
            rec.update(rec_idx=i, rec_start=s, rec_end=e, rec_end_at_eof=eof,
                       rec_words=len(words), rec_chars=len(text),
                       rec_head=" ".join(words[:40]), rec_tail=" ".join(words[-25:]),
                       rec_guarded_words=len(gw), rec_guarded_chars=len(g),
                       rec_guarded_tail=" ".join(gw[-25:]),
                       rec_head_crossref=head_is_crossref(text),
                       rec_method="anchor_later_entry")
        else:
            rec["rec_method"] = "anchor_later_entry_span_failed"

    # --- fallback measurement (the R3 arm's only option; also recorded for
    # R1 rows so the residual "absent from TOC but present in body" class is
    # quantified rather than assumed empty).
    full = E._LazyFullText(html)
    try:
        span = E.locate_item_section_by_heading_regex(full.get(), FORM, SECTION)
    except Exception as ex:
        rec["fb_error"] = f"{type(ex).__name__}: {ex}"
        span = None
    if span is not None:
        t = full.get()[span[0]:span[1]].strip()
        w = t.split()
        rec.update(fb_words=len(w), fb_chars=len(t), fb_start=span[0], fb_end=span[1],
                   fb_head=" ".join(w[:40]), fb_tail=" ".join(w[-25:]),
                   fb_end_at_eof=span[1] >= len(full.get()) - 2,
                   fb_head_crossref=head_is_crossref(t),
                   doc_words=len(full.get().split()))
    else:
        rec["doc_words"] = len(full.get().split())
    return rec


def main():
    audit = pd.read_parquet(os.path.join(ROOT, "data/f3/extraction_audit.parquet"))
    ea = audit[audit.extraction_status == "EXPECTED_ABSENT"].sort_values(
        ["accession_number", "section_type"]).reset_index(drop=True)
    assert len(ea) == 779, f"expected 779 EXPECTED_ABSENT rows, got {len(ea)}"

    done = set()
    if os.path.exists(JSONL):
        with open(JSONL) as fh:
            for line in fh:
                line = line.strip()
                if line:
                    done.add(json.loads(line)["accession_number"])
    todo = [r for _, r in ea.iterrows() if r["accession_number"] not in done]
    print(f"total {len(ea)}  done {len(done)}  todo {len(todo)}", file=sys.stderr, flush=True)

    t0 = time.time()
    n = 0
    with open(JSONL, "a") as fh, Pool(processes=6) as pool:
        for rec in pool.imap_unordered(classify, todo, chunksize=4):
            fh.write(json.dumps(rec, default=str) + "\n")
            n += 1
            if n % 25 == 0:
                fh.flush()
                print(f"  {n}/{len(todo)}  {time.time()-t0:.0f}s", file=sys.stderr, flush=True)
    print(f"DONE {n} rows in {time.time()-t0:.0f}s", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
