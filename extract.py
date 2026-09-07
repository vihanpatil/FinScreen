"""
extract.py -- Week 2: pull clean, structured text out of the raw filings
whose metadata `ingest_metadata.py` already resolved, and write it to
data/filings.parquet.

Section types extracted:
  - MDA            -- 10-K Item 7 / 10-Q Part I Item 2 (Management's
                       Discussion and Analysis)
  - RISK_FACTORS   -- 10-K Item 1A / 10-Q Part II Item 1A
  - EX99_PRESS_RELEASE / 8K_BODY -- the earnings document already resolved
                       by ingest_metadata.py's selection policy (Phase A3);
                       this module does NOT re-resolve exhibits, it only
                       reads `filings.earnings_doc_*` / `filing_documents`.

Point-in-time discipline (same as ingest_metadata.py): every row's
`filing_date` is carried through unchanged from the `filings` table --
EDGAR's own recorded public filing date, never `report_date` (fiscal period
end). Downstream code must keep sorting on `filing_date`.

How MD&A / Risk Factors sections are located (10-K/10-Q primary documents):
Modern EDGAR HTML filings almost universally include an anchor-linked table
of contents (`<a href="#some_id">Item 7.</a>` ... elsewhere in the document,
`<div id="some_id"></div>` immediately before the real heading). This is
the SAME mechanism the EDGAR web viewer itself uses for in-page navigation,
so it's reliable across filer/vendor HTML styles in a way that pattern-
matching heading text is not -- a naive "longest span between two heading-
looking regex matches" approach was tried first and produced badly wrong
results (see the extraction notes at the bottom of this file / the Week 2
section of INGESTION_NOTES.md): forward-looking-statements boilerplate
elsewhere in the document contains full cross-reference sentences like
"...as described in Item 7 of this Form 10-K under the heading
'Management's Discussion and Analysis'..." that a loose heading regex
happily matches, and which can appear to have a longer "span to the next
heading" than the real section if an unrelated large section (e.g. Risk
Factors) sits between the false match and the real one.

So the primary strategy here follows the document's own TOC anchors
(`locate_item_section_by_anchor`), falling back to a tightly-scoped heading
regex (`locate_item_section_by_heading_regex`, gap between "Item N" and the
expected title capped at a few characters of whitespace/punctuation only --
specifically to exclude prose cross-references, which have several words of
text in between) only when no usable anchor is found. Every extracted
section records which strategy located it and a confidence level, so a
reviewer can audit low-confidence extractions specifically.

A third, narrower failure mode -- some 10-K filers (CVX, XOM, JPM) write
Item 7 as a one-sentence pointer to real MD&A content that lives elsewhere
in the same document, instead of writing it inline -- is handled by
`resolve_incorporated_by_reference_mda()` and friends, in the
"10-K MD&A 'incorporated by reference elsewhere in this document' resolver"
section below. See INGESTION_NOTES.md's Week 2 section ("MD&A
'incorporated by reference' stub bug, and its resolution") for the full
writeup of why this happens and how it's resolved.

======================================================================
E2 / phase F3 (2026-08-26) -- what changed and why
======================================================================
Everything above describes E1 (25 mega-caps, 884 sections) and is still
exactly how sections are LOCATED. F3 runs the same locator over ~11x the
text (244 filers, 20,521 filings, 30,475 section attempts, back to 2015),
which needs auditability rather than new cleverness. Specified in
`data/f3/F3_SPEC.md` (P0, approved 2026-08-26); the ruling ids below are
that spec's:

  R5  Cache-only. `read_cached_document()` reads `data/raw/documents/` and
      raises `CacheMiss`; `EdgarClient` is NOT used on the F3 path, so
      "0 network GETs" is structural, not a promise. Every locator entry
      point now takes a `read` callable instead of a client.
  R6  Output is CIK-keyed: `filings.ticker` is NULL for all 45,545 E2 rows,
      so a `ticker` column would be entirely NULL. F4 (`chunk.py`) must
      switch `row["ticker"]` -> `row["cik"]`; that is F4's edit, named here.
  R7  Each primary document is parsed ONCE (`extract_periodic_sections`)
      and the soup + TOC reused for both sections (measured: 2.53s -> 1.42s
      per filing).
  R9  Every attempt yields an audit row -- OK / FLAGGED / ITEM_ABSENT_FROM_TOC /
      FAIL with exactly one `reason_code` -- never a print statement.
  R3  Word-count floors FLAG, they never filter; and a FLAGGED row may
      never carry confidence='high' (four pilot rows of 43-102 words came
      out anchor/high under E1's rules).
  R4  The 10-K MD&A stub resolver triggers on WORD COUNT alone.
      `STUB_REFERENCE_LANGUAGE_RE` matched 0 of 4 real stubs found in a
      144-filing pilot, so it is demoted from gate to evidence field.
  R2  `8K_BODY` slices from the first "Item 2.02" to END OF DOCUMENT --
      never to the next item heading, which would leave <200 words in 45 of
      210 sections.
  R1  The earnings population gate ships BROAD (multi-filing (CIK, quarter)
      cell -> WARN); the results-announcement text signature is a severity
      field, never a suppressor.
  R8  Per-filer / per-dialect edge handlers live in one small named
      registry (`EDGE_HANDLERS`) with fired-counts and DEAD detection.

E1's artifacts are frozen: `data/filings.parquet` and
`data/filings_metadata.db` are refused by name (`assert_not_e1_path`).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import unicodedata
from collections import namedtuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

import chunk as chunk_module  # C16: MIN_PROSE_WORDS is chunk.py's constant,
                              # imported here, never re-declared.

# NOTE on parser choice: BeautifulSoup(..., "lxml") was tried first and is
# faster, but silently produces EMPTY get_text() output for HTML fragments
# that start with a dangling/orphan closing tag -- which is exactly what
# our anchor-based slicing produces (we deliberately cut mid-document,
# right after a marker <div>). "html.parser" (stdlib, no extra dependency)
# handles the same malformed fragment correctly. This was caught by the
# MIN_SECTION_CHARS empty-text safety net silently falling back to the
# lower-confidence regex path on every single anchor-based extraction
# attempt, not by any exception -- worth remembering if a future change
# reintroduces "lxml" for a speed win without re-testing this.
_PARSER = "html.parser"

REPO_ROOT = Path(__file__).resolve().parent

# --- E1's frozen artifacts (never written by F3; refused by name) ----------
E1_DB_PATH = REPO_ROOT / "data" / "filings_metadata.db"
E1_PARQUET_PATH = REPO_ROOT / "data" / "filings.parquet"
E1_FROZEN_PATHS = frozenset(
    p.resolve()
    for p in (
        E1_DB_PATH,
        E1_PARQUET_PATH,
        REPO_ROOT / "data" / "labels.parquet",
        REPO_ROOT / "data" / "labeling_corpus.parquet",
        REPO_ROOT / "data" / "paragraph_occurrence_map.parquet",
        REPO_ROOT / "data" / "universe.csv",
    )
)

# --- E2 defaults (C1: the old module constants become arguments) -----------
DB_PATH = REPO_ROOT / "data" / "filings_metadata_e2.db"
PARQUET_PATH = REPO_ROOT / "data" / "filings_e2.parquet"
OUT_DIR = REPO_ROOT / "data" / "f3"
RAW_DOCS = REPO_ROOT / "data" / "raw" / "documents"

EXTRACTOR_VERSION = "f3.1"

MIN_SECTION_CHARS = 30  # below this, treat extraction as failed, not "short but real"

# Per-(form, section_type) minimum WORD count floor -- below this, an
# extraction is flagged for review (a `below_length_floor` column in the
# output parquet) rather than silently trusted at face value just because
# MIN_SECTION_CHARS (30 chars) was cleared. This is the general fix for the
# class of bug the CVX/XOM/JPM MD&A stub was one instance of: MIN_SECTION_CHARS
# is far too low to catch a 242-char "see elsewhere in this document" stub
# being mistaken for a legitimate 10-K MD&A.
#
# Calibrated off the REAL word-count distribution across the whole universe
# (data/filings.parquet as extracted before this fix), not guessed:
#   (10-K, MDA):           real min (excluding the 9 known stubs) is 2,441
#                           words (AAPL) -- floor set well below that with
#                           room to spare, since the stubs themselves are
#                           36-53 words, a >45x gap either side of 1,500.
#   (10-K, RISK_FACTORS):  real min is 4,277 words -- no known bug here;
#                           floor set with headroom below the observed min.
#   (10-Q, MDA):            real min is 2,420 words -- same reasoning.
#   (10-Q, RISK_FACTORS):   real min is 24 words -- confirmed NOT a bug: some
#                           filers (MA, OXY, COP, MCD, ...) legitimately
#                           satisfy Item 1A with a single short compliant
#                           cross-reference sentence to a DIFFERENT, earlier
#                           filing ("see Part I, Item 1A ... of our 2024 Form
#                           10-K"), which Reg S-K explicitly permits when
#                           risk factors haven't materially changed -- this
#                           is the same "genuine filer practice, not an
#                           extraction bug" finding already documented for
#                           the 45 whole-section Item 1A omissions, just
#                           showing up as an explicit sentence instead of a
#                           missing section. Distinct from the MD&A case:
#                           there, the reference points at content elsewhere
#                           in the SAME document (recoverable); here, it
#                           points at a DIFFERENT filing entirely (nothing to
#                           recover from this document). Floor set low
#                           (just above zero) so this doesn't spuriously
#                           re-flag an already-investigated, legitimate
#                           pattern on every future run.
#   (8-K, 8K_BODY):         real min is 1,412 words -- no known bug; floor
#                           set with headroom below the observed min.
#   (8-K, EX99_PRESS_RELEASE): real min is 109 words (a short guidance-only
#                           supplemental release) -- confirmed legitimate on
#                           inspection (ABBV); floor set low so it isn't
#                           re-flagged every run either.
# E2/F3 RECALIBRATION, 2026-08-26 (F3_SPEC §8.3, applied at P1):
#   ("8-K", "EX99_PRESS_RELEASE"): 50 -> 250.  A RAISE, argued from the
#   measured E2 distribution over all 10,357 EX-99 selections (p0.5% = 243w,
#   p1 = 553w, p5 = 1,567w, median 5,194w) and hand-read in the 50-249w gap
#   (`data/f3/p1_calibrate/`). E1's 50 was fitted to E1's own smallest row
#   (ABBV, 109 words) and is far below F2 §5's named P5 thin-exhibit class
#   (~50 selections under 1,500 CHARS), which F2 states in writing "should
#   fail F3's floor". Named rows the raise had to argue past, all verified
#   still ABOVE 250 and therefore unflagged: Tesla Q1-22 P&D (276 words) and
#   the KKR monetization update (384 words) -- H4 §8.1's two genuine short
#   releases. Flagged count 12 -> 53 of 10,357. Remember: a floor is a FLAG,
#   never a filter (§8.1(1)) -- this changes the size of the review queue,
#   never corpus membership.
# Every other floor is E1's, unchanged, pending P3's read of the measured
# corpus-wide distribution (`data/f3/length_distribution.csv`).
MIN_SECTION_WORDS: dict[tuple[str, str], int] = {
    ("10-K", "MDA"): 1500,
    ("10-K", "RISK_FACTORS"): 2000,
    ("10-Q", "MDA"): 1000,
    ("10-Q", "RISK_FACTORS"): 15,
    ("8-K", "8K_BODY"): 500,
    ("8-K", "EX99_PRESS_RELEASE"): 250,
}

# F2 §5's P5 thin-exhibit class is defined in CHARACTERS, not words (49
# distinct documents under 1,500 chars of extractable text, 12 of them under
# 100). Carried into F3 by name as its own flag so the class stays visible
# under whatever the word floor happens to be.
EARNINGS_THIN_DOCUMENT_CHARS = 1500


# ---------------------------------------------------------------------------
# F3: cache-only document reader (R5 / C2)
# ---------------------------------------------------------------------------


class CacheMiss(Exception):
    """A target document is not in `data/raw/documents/`.

    F3 never fetches: F2 prefetched all 20,521 target documents (verified
    0 missing at P0), so a miss is a real defect that must surface as a
    loud FAIL row with reason `cache_miss`, not as a silent re-download.
    """


def read_cached_document(relative_path: str, cache_dir: Path = RAW_DOCS) -> str:
    """Read a cached EDGAR archive document by its `/Archives/...` path.

    Reproduces `EdgarClient.get_archive_document`'s cache-key rule exactly
    (leading slash normalised, then '/' -> '_') so F3 reads the same bytes
    F2 wrote -- but raises `CacheMiss` instead of issuing a GET.
    """
    if not relative_path.startswith("/"):
        relative_path = "/" + relative_path
    cache_key = relative_path.strip("/").replace("/", "_")
    path = Path(cache_dir) / cache_key
    if not path.exists():
        raise CacheMiss(relative_path)
    return path.read_text(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# F3: attempt taxonomy (C5 / R9)
# ---------------------------------------------------------------------------

STATUS_OK = "OK"
STATUS_FLAGGED = "FLAGGED"
# P5 RENAME (was `EXPECTED_ABSENT`). The old name asserted a fact about the
# FILER -- "this 10-Q genuinely has no Part II Item 1A" -- which the extractor
# never measured. P4b censused all 779 rows carrying it and found the claim is
# false for 125 of them: 83 are extractor failures (the item IS in the anchor
# TOC and the anchor simply dangled -- now handled by the recovery ladder
# below) and 42 more are filings whose body carries a genuine Item 1A section
# that the anchor TOC never indexed. The new name states only what is actually
# tested: no matching entry was found in the anchor-linked TOC.
#
# AUDIT MAPPING, for anyone reconstructing the pre-P5 view of the corpus:
#   old EXPECTED_ABSENT  ==  ITEM_ABSENT_FROM_TOC
#                            + every (10-Q, RISK_FACTORS) row whose reason_code
#                              is now toc_recovered_f1 / toc_recovered_f2 /
#                              toc_recovery_declined
STATUS_ITEM_ABSENT_FROM_TOC = "ITEM_ABSENT_FROM_TOC"
STATUS_FAIL = "FAIL"

# reason_code -> status. Exactly one primary reason_code per attempt, chosen
# from `REASON_PRECEDENCE` below; `flags` may hold several.
#
# `item_absent_from_toc` is the one code whose status depends on the target:
# a 10-Q legitimately omits Part II Item 1A when nothing changed (E1
# documented 45 such sections), so there it is ITEM_ABSENT_FROM_TOC; anywhere
# else it is a FAIL.
REASON_STATUS: dict[str, str] = {
    "ok": STATUS_OK,
    "mda_stub_resolved": STATUS_OK,
    "item_absent_from_toc": STATUS_FAIL,  # overridden for (10-Q, RISK_FACTORS)
    "no_toc_and_no_heading_match": STATUS_FAIL,
    "anchor_span_below_min_chars": STATUS_FAIL,
    "empty_after_extraction": STATUS_FAIL,
    "cache_miss": STATUS_FAIL,
    "document_read_error": STATUS_FAIL,
    # P5 fix 1: the item WAS in the TOC and the recovery ladder still could not
    # produce a span that passed both guards. A loud FAIL, never a silent
    # EXPECTED_ABSENT, and distinct from "the item is not in the TOC".
    "toc_recovery_declined": STATUS_FAIL,
    "mda_stub_unresolved_same_doc": STATUS_FLAGGED,
    "mda_stub_external_document": STATUS_FLAGGED,
    "below_length_floor": STATUS_FLAGGED,
    "head_foreign_item": STATUS_FLAGGED,
    "head_keyword_absent": STATUS_FLAGGED,
    "heading_regex_fallback": STATUS_FLAGGED,
    # P5 fix 1: recovered rows. Never OK, never `high`.
    "toc_recovered_f1": STATUS_FLAGGED,
    "toc_recovered_f2": STATUS_FLAGGED,
    "toc_recovery_end_guarded": STATUS_FLAGGED,
    # P5 fix 2: review marker on an ITEM_ABSENT_FROM_TOC / FAIL row -- the
    # anchor TOC has no matching entry, but the document body does carry a
    # heading that passes both recovery guards. Never a recovery (P4b measured
    # 89 garbage admissions if the ladder is allowed to fire here); a pointer
    # for review only.
    "item_body_heading_present": STATUS_FLAGGED,
    # P5 fix 3: the character stream is not readable prose.
    "garbled_text": STATUS_FLAGGED,
    "earnings_item202_missing": STATUS_FLAGGED,
    "earnings_item202_block_thin": STATUS_FLAGGED,
    "earnings_item202_prefix_large": STATUS_FLAGGED,
    "earnings_population_gate": STATUS_FLAGGED,
    "earnings_thin_document": STATUS_FLAGGED,
    "earnings_supplemental_diluted": STATUS_FLAGGED,
}

# Fixed precedence (C5): FAIL codes > cache_miss > garbled_text > stub codes >
# head_foreign_item > recovery codes > below_length_floor > earnings codes >
# heading_regex_fallback > markers > head_keyword_absent > ok.
REASON_PRECEDENCE: tuple[str, ...] = (
    "document_read_error",
    "empty_after_extraction",
    "anchor_span_below_min_chars",
    "no_toc_and_no_heading_match",
    "toc_recovery_declined",
    "item_absent_from_toc",
    "cache_miss",
    # Garbage text outranks every other located-row code: nothing else about a
    # row matters if its characters are not readable (P3 §6.2 / P4 §4.1).
    "garbled_text",
    "mda_stub_external_document",
    "mda_stub_unresolved_same_doc",
    "mda_stub_resolved",
    "head_foreign_item",
    "toc_recovered_f1",
    "toc_recovered_f2",
    "toc_recovery_end_guarded",
    "below_length_floor",
    "earnings_item202_missing",
    "earnings_item202_block_thin",
    "earnings_item202_prefix_large",
    "earnings_population_gate",
    "earnings_thin_document",
    "earnings_supplemental_diluted",
    "heading_regex_fallback",
    "item_body_heading_present",
    "head_keyword_absent",
    "ok",
)


def primary_reason_code(flags: list[str]) -> str:
    """The single highest-precedence code among `flags` (C5)."""
    for code in REASON_PRECEDENCE:
        if code in flags:
            return code
    return "ok"


def status_for(reason_code: str, form: str = "", section: str = "") -> str:
    if reason_code == "item_absent_from_toc" and (form, section) == ("10-Q", "RISK_FACTORS"):
        return STATUS_ITEM_ABSENT_FROM_TOC
    return REASON_STATUS[reason_code]


# ---------------------------------------------------------------------------
# TOC-anchor-based section location
# ---------------------------------------------------------------------------

# C12 (E2/F3): also accept the parenthesised-letter dialect "Item 1(A)." --
# confirmed real, Intercontinental Exchange's 10-Q `0001571949-24-000011`
# writes its Part II Item 1A heading as "ITEM 1(A). RISK FACTORS". Both
# spellings normalise to "1A" via `_normalize_item_label()`. The trailing
# `\.?\b` of the original pattern is replaced by a "not followed by another
# alphanumeric" lookahead because `\b` cannot follow a ')' (two non-word
# characters in a row), which made the parenthesised alternative backtrack
# to the bare number and silently return "1" instead of "1A".
_ITEM_LABEL_PREFIX_RE = re.compile(
    r"^item\s*([0-9]{1,2}\s*\(\s*[a-c]\s*\)|[0-9]{1,2}[a-c]?)(?![0-9a-z])",
    re.IGNORECASE,
)


def _normalize_item_label(raw: str) -> str:
    """"1a" / "1 (A)" / "1(a)" -> "1A". Whitespace and parentheses only."""
    return re.sub(r"[\s()]", "", raw).upper()
# Fallback for filer TOC templates that drop the word "Item" from each row
# and just start with the number (confirmed on COP/CVX's real 10-Ks: rows
# read "7. Management's Discussion..." / "1A. Risk Factors 18", not
# "Item 7." / "Item 1A."). JNJ's real 10-K goes a step further and drops
# the period too for plain-numbered items specifically while KEEPING it for
# lettered ones ("1A. Risk factors 9" but "7 Management's discussion... 22"
# -- same document, inconsistent within itself), so the period is optional
# here. To keep the false-positive risk bounded despite the looser pattern
# (this is still only applied to rows already known to contain a TOC-style
# internal `<a href="#...">` link, not scanned across the whole document),
# also require the row to END in a number -- the page number column, a
# strong TOC-specific fingerprint that ordinary body-text rows with a
# leading digit (e.g. a numbered list item) won't usually share.
_ITEM_LABEL_BARE_NUM_RE = re.compile(r"^([0-9]{1,2}[A-C]?)\.?\s+\S.*\d\s*$", re.IGNORECASE)
_HREF_HASH_RE = re.compile(r"^#")


@dataclass
class TocEntry:
    item_no: str  # normalized, e.g. "7", "1A"
    anchor_id: str
    order: int  # position among <a href="#..."> tags encountered, doc order
    row_text: str  # the matched row's text, lowercased -- used to disambiguate
                    # a real "Item N" heading from an unrelated same-numbered
                    # entry (confirmed real case: UNH's Notes-to-financial-
                    # statements sub-index numbers each note "1.", "2.", "3."
                    # with NO "Note" prefix, identical in shape to the bare-
                    # number Item TOC format -- "2. Investments ... 8" reads
                    # exactly like a TOC row and was, before this fix,
                    # silently mistaken for "Item 2. Management's Discussion
                    # and Analysis" since it's the first bare "2." encountered
                    # in document order)


_TOC_CONTEXT_ROWS_AFTER = 3  # see find_toc_item_anchors() -- GS's real TOC
                              # splits an item's title across up to 3 rows


def find_toc_item_anchors(soup: BeautifulSoup) -> list[TocEntry]:
    """Walk every internal hyperlink (`<a href="#...">`) in the document and,
    for each, look at its enclosing table row's text (or the immediately
    preceding sibling row's text, since some filers -- JPMorgan confirmed --
    split the "Item N." label and the linked title into two adjacent rows
    rather than one) to see if it's a TOC entry for "Item N. <title>".

    Each entry's `row_text` (used by callers for keyword disambiguation --
    see locate_item_section_by_anchor()) is widened to include a few
    FOLLOWING sibling rows too, not just the matched row itself: confirmed
    real case, Goldman Sachs's TOC splits a single item across three
    consecutive rows ("Item 7" / "Management's Discussion and Analysis of
    Financial Condition" / "and Results of Operations 62") with the actual
    `<a href>` living on the middle row -- a title-keyword check against
    only that row's own text ("Item 7", no title at all) would wrongly
    reject a perfectly real entry.

    Returns entries in document order, NOT deduplicated -- callers use order
    to disambiguate forms/parts that reuse the same item number (e.g. a
    10-Q's Part I Item 2 "MD&A" vs. Part II Item 2 "Unregistered Sales" --
    taking the FIRST occurrence of a given item number and then walking
    forward to the next DIFFERENT item number as the section boundary
    naturally resolves this without hand-coding per-form-type item lists).
    """
    entries: list[TocEntry] = []
    anchors = soup.find_all("a", href=_HREF_HASH_RE)
    for idx, a in enumerate(anchors):
        anchor_id = a["href"][1:]
        if not anchor_id:
            continue
        row = a.find_parent("tr")
        if row is None:
            continue
        row_text = row.get_text(" ", strip=True)
        matched_row = row
        m = _ITEM_LABEL_PREFIX_RE.match(row_text) or _ITEM_LABEL_BARE_NUM_RE.match(row_text)
        if not m:
            prev_row = row.find_previous_sibling("tr")
            if prev_row is not None:
                prev_text = prev_row.get_text(" ", strip=True)
                m = _ITEM_LABEL_PREFIX_RE.match(prev_text) or _ITEM_LABEL_BARE_NUM_RE.match(prev_text)
                if m:
                    matched_row = prev_row
        if m:
            context_parts = [matched_row.get_text(" ", strip=True)]
            sib = matched_row
            for _ in range(_TOC_CONTEXT_ROWS_AFTER):
                sib = sib.find_next_sibling("tr")
                if sib is None:
                    break
                context_parts.append(sib.get_text(" ", strip=True))
            entries.append(TocEntry(
                item_no=_normalize_item_label(m.group(1)), anchor_id=anchor_id, order=idx,
                row_text=" ".join(context_parts).lower(),
            ))
    return entries


def find_anchor_offset(html_text: str, anchor_id: str, after: int = 0) -> int | None:
    """Find the raw-HTML character offset where `id="anchor_id"` or
    `name="anchor_id"` is actually DEFINED (not merely referenced by an
    `href="#anchor_id"`, a different attribute name that this pattern
    doesn't match).
    """
    pat = re.compile(r'(?:id|name)\s*=\s*["\']' + re.escape(anchor_id) + r'["\']', re.IGNORECASE)
    m = pat.search(html_text, after)
    return m.start() if m else None


def _end_of_enclosing_tag(html_text: str, offset: int) -> int:
    """Given an offset that falls INSIDE an opening tag (e.g. right at the
    start of an `id="..."` attribute), return the offset just past that
    tag's closing '>'. Needed because find_anchor_offset() returns the
    attribute's own position, not the end of the tag it's part of --
    slicing html_text starting at the attribute position leaves a dangling
    `id="foo">` fragment that isn't valid markup, which BeautifulSoup then
    (correctly, since it's not actually a tag at that point) treats as
    literal text and leaks into the extracted output.
    """
    gt = html_text.find(">", offset)
    return gt + 1 if gt != -1 else offset


def _start_of_enclosing_tag(html_text: str, offset: int) -> int:
    """Inverse of _end_of_enclosing_tag(): given an offset inside an opening
    tag, return the offset of that tag's opening '<'. Used for the section's
    END boundary -- without this, the slice ends with a dangling partial
    tag like "...end of real content.\n<div" (cut right before the `id="..."`
    attribute of the NEXT section's marker div), which BeautifulSoup again
    has no choice but to render as literal trailing text ("<div") since it's
    not a complete tag. Excluding the whole dangling tag from the slice
    entirely avoids this.
    """
    lt = html_text.rfind("<", 0, offset)
    return lt if lt != -1 else offset


def locate_item_section_by_anchor(
    html_text: str, toc_entries: list[TocEntry], target_item_no: str,
    required_keywords: tuple[str, ...] = (),
) -> tuple[int, int] | None:
    """Returns (start_offset, end_offset) in `html_text` for the section
    starting at the first TOC entry matching `target_item_no`, ending at the
    next TOC entry (in document order) whose item number differs -- this
    skips duplicate/nested sub-entries under the same item (seen in both
    AAPL's and JPM's real TOCs) without needing to know the exact expected
    terminating item number for every form type.

    `required_keywords`, if given, additionally requires the matched entry's
    row text to contain at least one of these substrings (case-insensitive,
    and whitespace-insensitive on BOTH sides -- confirmed real case: JNJ's
    TOC renders as "management's d iscussion and a nalysis", with stray
    spaces mid-word from letter-spacing markup, which a plain substring
    check against "discussion and analysis" would never match; comparing
    with all whitespace stripped from both sides matches "discussionand
    analysis"-shaped text either way). This is NOT optional in practice for
    numeric-only item numbers like "2" -- confirmed real case: UNH's Notes-
    to-financial-statements sub-index numbers each note "1.", "2.", "3."
    with no "Note" prefix, in exactly the same bare "N. Title ... pagenum"
    shape as a real Item TOC row, and appears BEFORE the real "Item 2.
    Management's Discussion and Analysis" in document order (nested under
    Item 1 Financial Statements). Without a keyword check, "first
    occurrence of item_no=='2'" silently matched "2. Investments" (a
    balance-sheet footnote) instead -- confidently wrong output, not an
    error, caught only by manually reading the sample review.
    """
    idxs = matching_toc_entry_indices(toc_entries, target_item_no, required_keywords)
    if not idxs:
        return None
    return anchor_span_from_entry(html_text, toc_entries, idxs[0])


def matching_toc_entry_indices(
    toc_entries: list[TocEntry], target_item_no: str,
    required_keywords: tuple[str, ...] = (),
) -> list[int]:
    """Indices of every TOC entry the anchor locator would consider for this
    item -- same item number, and (when required) a title keyword in the row.

    Split out of `locate_item_section_by_anchor` at P5 so callers can tell the
    two very different reasons that function returns None apart:
      * no matching entry at all -> the item is genuinely not in the anchor TOC
      * matching entries exist but none yields a usable span -> an extractor
        failure (P3 measured 148 FAIL rows; P4b measured 83 more that were
        being reported as EXPECTED_ABSENT).
    """
    out = []
    for i, entry in enumerate(toc_entries):
        if entry.item_no != target_item_no:
            continue
        if required_keywords:
            row_text_nospace = re.sub(r"\s+", "", entry.row_text)
            if not any(re.sub(r"\s+", "", kw) in row_text_nospace for kw in required_keywords):
                continue
        out.append(i)
    return out


def anchor_span_from_entry(
    html_text: str, toc_entries: list[TocEntry], start_idx: int,
) -> tuple[int, int] | None:
    """The (start, end) span arithmetic for ONE matching TOC entry: from that
    entry's anchor definition to the next TOC anchor with a different item
    number. Returns None when the anchor id is never DEFINED (a dangling
    reference) or when the resulting span is degenerate."""
    start_entry = toc_entries[start_idx]
    start_offset = find_anchor_offset(html_text, start_entry.anchor_id)
    if start_offset is None:
        return None
    start_offset = _end_of_enclosing_tag(html_text, start_offset)

    end_offset = len(html_text)
    for entry in toc_entries[start_idx + 1:]:
        if entry.item_no != start_entry.item_no:
            candidate = find_anchor_offset(html_text, entry.anchor_id, after=start_offset)
            if candidate is not None and candidate > start_offset:
                end_offset = _start_of_enclosing_tag(html_text, candidate)
            break

    if end_offset <= start_offset:
        return None
    return start_offset, end_offset


def locate_item_section_by_resolving_anchor(
    html_text: str, toc_entries: list[TocEntry], target_item_no: str,
    required_keywords: tuple[str, ...] = (),
) -> tuple[int, int] | None:
    """F1' -- the first matching TOC entry whose anchor actually RESOLVES.

    The shipped locator takes the FIRST matching entry, full stop, and gives up
    if that entry's `<a href="#id">` points at an id nothing ever defines. The
    Workiva-family filer templates put two ids on each TOC row, only one of
    which is defined, and repeat the row; a later identical entry carries the
    live id. P3 measured 116 FAIL rows of this shape; P4b measured 71 more
    inside the EXPECTED_ABSENT population.

    Identical to `locate_item_section_by_anchor` whenever that function
    succeeds (both take the first matching entry), so this is only ever
    consulted after the shipped path has returned None.
    """
    for i in matching_toc_entry_indices(toc_entries, target_item_no, required_keywords):
        span = anchor_span_from_entry(html_text, toc_entries, i)
        if span is not None:
            return span
    return None


# ---------------------------------------------------------------------------
# Fallback: tightly-scoped heading regex (used only when no TOC anchor works)
# ---------------------------------------------------------------------------

# Gap between "Item N" and the expected title is capped at a handful of
# whitespace/punctuation characters -- enough for "Item 7.    Management's
# Discussion..." (real heading) but not enough for "Item 7 of this Form
# 10-K under the heading 'Management's Discussion...'" (prose cross-
# reference), which has several words in between.
def _heading_pattern(item_no: str, keyword: str) -> re.Pattern:
    return re.compile(
        rf"item\s*{re.escape(item_no)}\.?[\s\xa0.:]{{0,20}}{keyword}",
        re.IGNORECASE,
    )


FALLBACK_SECTIONS = {
    ("10-K", "MDA"): (_heading_pattern("7", r"management.?s\s+discussion"),
                       [_heading_pattern("7A", r"quantitative"), _heading_pattern("8", r"financial\s+statements")]),
    ("10-K", "RISK_FACTORS"): (_heading_pattern("1A", r"risk\s+factors"),
                                [_heading_pattern("1B", r"unresolved"), _heading_pattern("2", r"properties")]),
    ("10-Q", "MDA"): (_heading_pattern("2", r"management.?s\s+discussion"),
                       [_heading_pattern("3", r"quantitative"), _heading_pattern("4", r"controls\s+and\s+procedures")]),
    ("10-Q", "RISK_FACTORS"): (_heading_pattern("1A", r"risk\s+factors"),
                                [_heading_pattern("2", r"unregistered"), _heading_pattern("3", r"defaults"),
                                 _heading_pattern("4", r"mine\s+safety"), _heading_pattern("5", r"other\s+information"),
                                 _heading_pattern("6", r"exhibits")]),
}


def _fallback_candidate_spans(text: str, form: str, section: str) -> list[tuple[int, int]]:
    """Every start-pattern match, in document order, paired with the nearest
    subsequent end-pattern match, keeping only spans over MIN_SECTION_CHARS."""
    start_pat, end_pats = FALLBACK_SECTIONS[(form, section)]
    out = []
    for sm in start_pat.finditer(text):
        s_end = sm.end()
        end_offset = len(text)
        for ep in end_pats:
            em = ep.search(text, s_end)
            if em and em.start() < end_offset:
                end_offset = em.start()
        if end_offset - s_end >= MIN_SECTION_CHARS:
            out.append((sm.start(), end_offset))
    return out


def locate_item_section_by_heading_regex(
    text: str, form: str, section: str,
) -> tuple[int, int] | None:
    """Fallback for documents without a usable anchor-linked TOC. Takes the
    LAST start-pattern match in the document (real content sections appear
    after the TOC, which is always near the top) with a resulting span to
    the nearest subsequent end-pattern match of at least MIN_SECTION_CHARS.

    P5 / N5 -- THE FLOOR RESCUE, the one amendment to that rule.
    P3 §7.2 measured what "last match" costs when a filer repeats the heading
    as a running page header: all 34 AT&T 10-Q MD&As came out at the LAST page
    (43-819 words, median 333, against a 9,325-word anchor median) and 25 more
    rows came out as bare heading lines (Disney's 13-word slices). So when the
    last-match slice lands BELOW the already-calibrated `MIN_SECTION_WORDS`
    floor for this (form, section), scan the matches in document order and take
    the earliest one that clears the floor.

    Why the floor and not "prefer the first match": the plain first-match rule
    was measured on all 1,140 heading_regex rows and hand-read on 38 of the
    rows it changed (`data/f3/p5_fixes/n5_read_verdicts.csv`). It is not safe
    -- 15 rows got better, 12 got worse and 11 were wrong either way, because
    position does not decide which match is a section start; in a 10-Q the
    early "Item 1A. Risk Factors" hits are cross-references in the
    forward-looking preamble (PayPal +11.4k words of wrong text, Micron +15k,
    Waste Management +9.6k). Length does decide: every damaged row already had
    a plausible 7.8k-32k-word slice, and every row of the named defect was
    below its floor. Gating on the floor therefore changes ONLY rows that are
    already flagged `below_length_floor` -- 58 rows corpus-wide, all in named
    classes (AT&T 34, Disney 10, Abbott 7, eBay 4, Berkshire/Micron/Shire 1
    each), 21 of them hand-read. No new constant is introduced.
    """
    cands = _fallback_candidate_spans(text, form, section)
    if not cands:
        return None
    shipped = cands[-1]
    floor = MIN_SECTION_WORDS.get((form, section), 0)
    if len(text[shipped[0]:shipped[1]].split()) < floor:
        for span in cands:
            # A rescue candidate must begin a LINE. Without this the rescue
            # picks the first cross-reference that happens to be followed by
            # enough text, which measurably makes four rows worse than doing
            # nothing: Valero `0001035002-22-000007` and Concho
            # `0001358071-16-000026` / `-17-000005` come back with 16k-23k words
            # of Item 1 Business labelled as MD&A, and Abbott
            # `0001104659-22-025141` returns 7,258 words of "Patents,
            # Trademarks, and Licenses" instead of the 4,320-word Item 1A that
            # sits 20k characters later and does start a line.
            if (_fallback_span_starts_a_line(span, text)
                    and len(text[span[0]:span[1]].split()) >= floor):
                return span
    return shipped


# ---------------------------------------------------------------------------
# P5 fix 1: the guarded recovery ladder for TOC-present-but-unresolved items
# ---------------------------------------------------------------------------
#
# Population: attempts where the anchor TOC DOES carry a matching entry for the
# target item (right number, right title keyword) but the shipped anchor path
# still returns None -- P3's 148 FAIL rows (116 R2 + 32 R3) and P4b's 83
# EXPECTED_ABSENT rows (71 R2 + 12 R3).
#
# Two guards decide admission, measured by P4b over the whole 779-row
# EXPECTED_ABSENT population with a ~62-section hand read:
#
#   G1  the recovered span must OPEN on the item's own heading, within the
#       first HEAD_GUARD_CHARS characters. This is what stops the Eversource
#       dialect, where the later-resolving anchor points at the start of Part
#       II and the span is "Item 1. Legal Proceedings" concatenated with Item
#       1A -- plausible-looking, floor-clearing and wrong (13 rows).
#   G2  the span must not run to end-of-document. A real Part II Item 1A is
#       always followed by Item 2/3/4/5/6, so a span that reaches EOF with no
#       following item has its START in the wrong place. An anchor span that
#       already closed on a later resolving TOC anchor has a real boundary and
#       passes; one that reached EOF passes only if an end pattern closes it.
#       This is what stops the 12 AIG rows, whose "recovery" is a truncated
#       cross-reference clause followed by share-repurchase tables, exhibits
#       and signature pages.
#   G3  the recovered span must clear the (form, section) `MIN_SECTION_WORDS`
#       floor. ADDED AT P5 -- P4b's two guards were calibrated on
#       (10-Q, RISK_FACTORS), where the floor is 15 and the genuine sections
#       really are 29-40 words; on the 148-row FAIL population, which spans all
#       four targets, they let five hand-read failures through: Weyerhaeuser
#       `0001564590-20-004822` (54 w -- the MD&A's own sub-table-of-contents),
#       PNC `0001193125-15-277885` and `-17-155839` (77/89 w -- the same,
#       PNC's Financial Review index page) and Concho `0001358071-18-000008`
#       / `-19-000003` (905/914 w -- truncated at an Item 8 cross-reference).
#       No floor constant moves: this uses the shipped values as an ADMISSION
#       test on a new path, which is strictly the safe direction -- a declined
#       row keeps failing exactly as it does today.
#
# HONEST CAVEAT, carried from P4b §5 and repeated in P5's report: G2's rule was
# chosen AFTER seeing this population and separates it perfectly (58/12, zero
# disagreements against the hand read) partly because of that. Its mechanism is
# principled, but on an independent slice it will not be perfect. It is
# therefore wired so that it can only ever DECLINE TO ADD a row -- it never
# removes text that would otherwise be in the corpus. A declined row keeps
# failing loudly under its own reason code (`toc_recovery_declined`), which is
# a review queue entry, not a silent drop. And where the raw span had NO
# natural boundary and only the end guard closed it (37 of P4b's 58), the row
# additionally carries `toc_recovery_end_guarded`, which downgrades its
# confidence from `medium` to `low`.
#
# SCOPE, and it is load-bearing: the ladder fires ONLY when a matching TOC
# entry exists. P4b ran the identical guards over the 696 rows with NO matching
# entry and they admitted 131 rows of which 89 were garbage (68% wrong), versus
# 71/71 correct on the TOC-present arm. The guards are necessary; the
# item-is-in-the-TOC precondition is what makes them sufficient.

HEAD_GUARD_CHARS = 40

# Deliberately looser than `_heading_pattern`: this is a GUARD on text that has
# already been located, not a locator, so it accepts the dash and
# parenthesised-letter dialects ("ITEM 1A - RISK FACTORS", "ITEM 1(A).") that
# the tight locator gap class rejects.
def _head_guard_pattern(item_no: str, keyword: str) -> re.Pattern:
    label = re.escape(item_no[0]) + (r"\s*\(?\s*" + re.escape(item_no[1:]) + r"\s*\)?"
                                      if len(item_no) > 1 else "")
    return re.compile(rf"item\s*{label}[\s\xa0.:|\-–—]{{0,20}}{keyword}", re.IGNORECASE)


HEAD_GUARD_PATTERNS: dict[tuple[str, str], re.Pattern] = {
    ("10-K", "MDA"): _head_guard_pattern("7", r"management.?s\s+discussion"),
    ("10-K", "RISK_FACTORS"): _head_guard_pattern("1A", r"risk\s*factors"),
    ("10-Q", "MDA"): _head_guard_pattern("2", r"management.?s\s+discussion"),
    ("10-Q", "RISK_FACTORS"): _head_guard_pattern("1A", r"risk\s*factors"),
}


def span_opens_on_item_heading(text: str, form: str, section: str) -> bool:
    """G1: the rendered span opens on the target item's own heading."""
    pat = HEAD_GUARD_PATTERNS.get((form, section))
    if pat is None:
        return False
    m = pat.search(text[:400])
    return m is not None and m.start() < HEAD_GUARD_CHARS


def end_guard_span(text: str, form: str, section: str) -> tuple[str, bool]:
    """G2, for a raw ANCHOR span: close it on the first of this (form,
    section)'s end patterns -- the same patterns the heading-regex path already
    uses, which the anchor path does not apply at all (it ends at the next
    differing TOC anchor, or at EOF).

    Returns (guarded_text, closed_by_an_end_pattern). `False` means no
    following item was found anywhere after the start, i.e. the span runs to
    end-of-document -- which for a Part II Item 1A or an Item 7 MD&A means the
    START is in the wrong place.

    (The heading-regex path applies these patterns itself, so its own G2 test
    is "did the located span stop short of EOF", not a second application of
    the patterns -- see `_fallback_span_is_end_guarded`.)
    """
    _, end_pats = FALLBACK_SECTIONS[(form, section)]
    pat = HEAD_GUARD_PATTERNS.get((form, section))
    m = pat.search(text[:400]) if pat else None
    search_from = m.end() if m else MIN_SECTION_CHARS
    end = len(text)
    closed = False
    for ep in end_pats:
        em = ep.search(text, search_from)
        if em and em.start() < end:
            end = em.start()
            closed = True
    return text[:end].strip(), closed


def _fallback_span_is_end_guarded(span: tuple[int, int], text: str) -> bool:
    """G2 for a heading-regex span: it must not terminate at end-of-document.
    `locate_item_section_by_heading_regex` sets `end = len(text)` exactly when
    none of the end patterns matched after the start."""
    return span[1] < len(text) - 2


def _fallback_span_starts_a_line(span: tuple[int, int], text: str) -> bool:
    """G1, completed, for a heading-regex span: A HEADING BEGINS A LINE.

    On the anchor rung G1 is a real test, because the rendered span can open on
    anything. On the heading-regex rung the span starts AT the regex match by
    construction, so the plain "does it open on the item heading" test is
    vacuous -- and the match may well be a cross-reference embedded in a
    sentence. Requiring the match to sit at the start of a rendered line is the
    structural form of the same question, and it is not a word list.

    Measured on all 37 heading-regex recoveries the ladder produces (the whole
    population, not a sample): 32 start a line and 5 do not, and those 5 are
    exactly the 5 I hand-read as wrong -- Honeywell `0000930413-16-005457`,
    `-18-000292`, `-19-000366` 10-K MDA (the match sits inside "...that drive
    our business and future results in Item 7. Management's Discussion...", so
    the slice is the tail of Item 1A plus Items 2-6) and Concho
    `0001358071-18-000008`, `-19-000003` 10-K RISK_FACTORS (the match sits
    inside 'See "Item 1A. Risk Factors" for a description of the factors...').
    All 13 Eversource rows and all 12 Welltower rows pass.

    Same caveat as G2: validated after seeing the population. It can only ever
    decline a recovery, never remove a row that is in the corpus today.
    """
    return span[0] == 0 or text[span[0] - 1] == "\n"


def recover_toc_present_section(
    html_text: str, toc_entries: list[TocEntry], form: str, section: str,
    target_item_no: str, required_keywords: tuple[str, ...], full_text: "_LazyFullText",
) -> tuple[str, str, str, bool] | str:
    """The ladder. Returns (text, method, reason_code, end_guard_was_needed) on
    a successful recovery, or a short string explaining which guard declined it.

    Rung 1 (F1'): the first matching TOC entry whose anchor resolves, rendered
                  and then closed by the end guard.
    Rung 2 (F2'): the shipped heading-regex fallback -- tried only where F1'
                  fails G1, which is exactly the Eversource case (F1' resolves
                  to the wrong section, F2' gets it right 13 for 13).
    """
    floor = MIN_SECTION_WORDS.get((form, section), 0)
    why = []
    try_f2 = True
    span = locate_item_section_by_resolving_anchor(
        html_text, toc_entries, target_item_no, required_keywords)
    if span is None:
        why.append("F1:no_resolving_anchor")
    else:
        raw = html_fragment_to_text(html_text[span[0]:span[1]])
        # G2 is about END-OF-DOCUMENT, not about whether an end pattern happens
        # to sit inside the span. An anchor span that already closed on a later
        # resolving TOC anchor HAS a real boundary and keeps it; one that ran to
        # the end of the document has no boundary at all, and passes only if an
        # end pattern can supply one.
        #
        # The end guard is applied ONLY in that second case, and that ordering
        # is measured, not stylistic: 10-K MD&A prose routinely cross-references
        # `Item 8. Financial Statements` in its own opening paragraph, so
        # applying the end patterns to a span that already has a boundary
        # truncates it there -- Coca-Cola `0000021344-18-000008` came back at 73
        # words and Zoetis `0001555280-17-000044` at 74. P4b's 58 R2 survivors
        # are unaffected: it recorded 21 rows whose span already closed (guard
        # not needed, and a no-op) and 37 that ran to EOF (guard load-bearing).
        runs_to_eof = span[1] >= len(html_text)
        text = end_guard_span(raw, form, section)[0] if runs_to_eof else raw.strip()
        if not span_opens_on_item_heading(raw, form, section):
            why.append("F1:G1_head_not_on_item_heading")
        else:
            # F1' found the right START. From here the row is F1's to win or
            # to lose: falling through to F2' would change the start, which
            # cannot fix an end-boundary problem and measurably makes it worse
            # (Coca-Cola `0000021344-18-000008`: F1 opens on the real Item 7
            # heading and is truncated to 73 words by an `Item 8` cross-
            # reference in its own first paragraph; F2 then returns 4,916 words
            # that START on a cross-reference inside Item 1 Business). So F2'
            # is reached only where F1' has no resolving anchor at all or fails
            # G1 -- the Eversource case, and the ordering the P4b fix package
            # specifies.
            try_f2 = False
            if runs_to_eof and not end_guard_span(raw, form, section)[1]:
                why.append("F1:G2_span_runs_to_eof")
            elif len(text.split()) < floor or len(text) < MIN_SECTION_CHARS:
                why.append(f"F1:G3_below_floor({len(text.split())}w<{floor})")
            else:
                return text, "anchor_resolving_entry", "toc_recovered_f1", runs_to_eof

    if not try_f2:
        return "; ".join(why)

    text_all = full_text.get()
    fb = locate_item_section_by_heading_regex(text_all, form, section)
    if fb is None:
        why.append("F2:no_heading_match")
    else:
        raw = text_all[fb[0]:fb[1]].strip()
        if not span_opens_on_item_heading(raw, form, section):
            why.append("F2:G1_head_not_on_item_heading")
        elif not _fallback_span_starts_a_line(fb, text_all):
            why.append("F2:G1_match_is_mid_line_cross_reference")
        elif not _fallback_span_is_end_guarded(fb, text_all):
            why.append("F2:G2_span_runs_to_eof")
        elif len(raw.split()) < floor or len(raw) < MIN_SECTION_CHARS:
            why.append(f"F2:G3_below_floor({len(raw.split())}w<{floor})")
        else:
            return raw, "heading_regex_toc_present", "toc_recovered_f2", False
    return "; ".join(why)


def body_heading_passes_guards(
    full_text: "_LazyFullText", form: str, section: str,
) -> bool:
    """P5 fix 2, review marker only -- NEVER a recovery.

    True when the document body carries something that looks like the target
    section (it passes both recovery guards) even though the anchor TOC has no
    matching entry at all. P4b hand-read this population: of the 131 rows the
    guards admit here, 42 are genuine sections the TOC never indexed (SBA
    `0001034054-16-000022` is 12,855 words of real Risk Factors) and 89 are
    cross-reference continuations that would import garbage (Williams
    `0000107263-17-000006` returns 21,241 words starting mid-sentence). At 32%
    precision this is a pointer for review, not a basis for extraction -- which
    is why it sets a flag on a row that still fails.
    """
    if (form, section) not in FALLBACK_SECTIONS:
        return False
    text_all = full_text.get()
    span = locate_item_section_by_heading_regex(text_all, form, section)
    if span is None:
        return False
    raw = text_all[span[0]:span[1]].strip()
    return (span_opens_on_item_heading(raw, form, section)
            and _fallback_span_starts_a_line(span, text_all)
            and _fallback_span_is_end_guarded(span, text_all))


# ---------------------------------------------------------------------------
# 10-K MD&A "incorporated by reference elsewhere in this document" resolver
# ---------------------------------------------------------------------------
#
# Fix 3 (second Opus-tier review, corrective pass): CVX, XOM, and JPM's 10-Ks
# don't write Item 7 inline -- they write a one-sentence pointer ("The index
# to Management's Discussion and Analysis ... is presented in the Financial
# Table of Contents." / "Reference is made to the section entitled ... in the
# Financial Section of this report." / "... entitled 'Management's discussion
# and analysis,' appears on pages 46-160.") and the REAL, substantive MD&A
# text lives elsewhere in the SAME primary document (verified: CVX ~15-17K
# words, XOM ~17-22K words, JPM ~60-65K words per filing). The anchor-based
# extractor has no way to know this from the Item-7-to-Item-7A anchor match
# alone -- it correctly finds and slices exactly what's there, which just
# happens to be the pointer sentence, not the real content.
#
# Two independent resolution strategies, tried in order:
#
#   1. resolve_mda_via_anchor_hop() -- CVX and (for its most recent filing
#      format) XOM embed an actual `<a href="#...">` inside the pointer
#      sentence. Following it lands either directly on the real heading (XOM
#      2026) or on a SECONDARY index/TOC page for a "Financial
#      Section"/"Financial Table of Contents" that itself links to the real
#      heading (CVX, all 3 years) -- handled by hopping up to 3 anchor
#      references deep, at each hop checking whether the landing region
#      still looks like an index (has its own further MD&A-labeled link) or
#      real content (starts with the MD&A heading text).
#
#   2. resolve_mda_via_text_heuristic() -- XOM's older filings (2024, 2025)
#      and JPM (all 3 years) have NO hyperlink in the pointer sentence at
#      all, just plain text ("... appears on pages 46-160."). Falls back to
#      scanning the whole document's plain text for a line matching the MD&A
#      heading that (a) is NOT itself the Item 7 stub or a TOC-listing row
#      (both already excluded by their own arms), and (b) looks like a
#      genuine standalone heading rather than a mid-sentence cross-reference
#      -- confirmed real false-positive risk: CVX's Item 1 Business section
#      contains "... some of which are also discussed in the section
#      Management's Discussion and Analysis of Financial Condition and
#      Results of Operations, are presented below." which matches the same
#      heading text but is a grammatically-continuing clause, not a heading;
#      excluded via _prev_line_looks_like_heading_boundary()'s check that the
#      PRECEDING line ends in terminal punctuation, is blank, or is itself a
#      lone running-header page number (this is why CVX resolves via anchor-
#      hop in practice and never needs this fallback, but the guard is kept
#      general rather than assuming it'll never be reached for a similar
#      future filer).
#
# Both strategies determine the END boundary the same way:
# _slice_to_next_audit_report_heading() scans forward for the first REAL
# "Report of Independent Registered Public Accounting Firm" heading (an
# almost-universal 10-K heading immediately preceding the financial
# statements) -- confirmed present, in this exact position, in all 9 known
# stub filings.
#
# If neither strategy resolves, extract_item_section() keeps the original
# short stub text but marks it explicitly (extraction_method =
# 'incorporated_by_reference_unresolved', confidence = 'low') rather than
# ever silently keeping a stub at high confidence -- see extract_item_section().

MDA_STUB_WORD_CEILING = 1500  # E1: "below this + reference-language present,
                                # treat an Item-7 extraction as a candidate
                                # stub" (real E1 stubs were 36-53 words; the
                                # smallest genuine E1 10-K MD&A is 2,441).
                                #
                                # E2/F3 (R4, F3_SPEC §C7/§8.4): this is now a
                                # RESOLVER TRIGGER ONLY -- word count alone
                                # decides whether to *try* to resolve, and the
                                # reference-language regex no longer gates it.
                                # A false trigger therefore costs ~1.5s of
                                # compute, not correctness, so an over-wide
                                # ceiling is the safe direction. P3 re-reads
                                # the band between this and the (10-K, MDA)
                                # floor against the measured distribution --
                                # the E1 "45x gap either side" does not
                                # survive 244 filers (pilot genuine p5 is
                                # ~1,199 words, i.e. the two OVERLAP).

# DEMOTED FROM GATE TO EVIDENCE (R4). Measured on a 144-filing E2 pilot, this
# regex matched 0 of the 4 real short-MD&A rows it met:
#   Sempra 2017    `0000086521-17-000017`  43w  "...is set forth in ... the
#                                                Annual Report, on pages 2
#                                                through 78."
#   US Bancorp 2017 `0001193125-17-053947` 50w  "...incorporated INTO THIS
#                                                REPORT by reference"
#   JPMorgan 2017  `0000019617-17-000314`  55w  "appears on\npages 36-138"
#                                                (line break inside the phrase)
#   HPE 2019       `0001645590-19-000044` 102w  not a stub at all -- a wrong
#                                                slice, catchable only by the
#                                                floor.
# Three of those four came out `anchor`/HIGH confidence under E1's rules.
# The three phrasings are added below (C12) so the evidence field is at
# least correct, and the regex now feeds two things only: the stored
# `stub_language_present` column, and the same-document vs. external-document
# discrimination in `classify_stub_reason()`.
STUB_REFERENCE_LANGUAGE_RE = re.compile(
    r"incorporated[\s\S]{0,20}by\s+reference|reference is made to|"
    r"is\s+(?:presented|set\s+forth)\s+in|appears\s+on\s+pages?|the index to",
    re.IGNORECASE,
)

# An unresolved stub whose language points at a DIFFERENT DOCUMENT (Sempra's
# "in the Annual Report, on pages 2 through 78"; US Bancorp's "in the
# Company's 2016 Annual Report") is not recoverable at 0 GETs: no 10-K
# exhibit is cached and `filing_documents` indexes 8-K accessions only
# (F3_SPEC §1.3). It gets its own reason code so the class can be counted
# and the fetch decision made by the main session with a number in hand.
STUB_EXTERNAL_DOCUMENT_RE = re.compile(
    r"annual report|exhibit 13|separate|accompanying", re.IGNORECASE
)


def classify_stub_reason(text: str) -> str:
    """`mda_stub_external_document` vs `mda_stub_unresolved_same_doc` (C7)."""
    if STUB_REFERENCE_LANGUAGE_RE.search(text) and STUB_EXTERNAL_DOCUMENT_RE.search(text):
        return "mda_stub_external_document"
    return "mda_stub_unresolved_same_doc"

_MDA_HEADING_LINE_RE = re.compile(
    r"^(item\s*7\.?\s*)?management.?s\s+discussion\s+and\s+analysis"
    r"(\s+of\s+financial\s+condition\s+and\s+results\s+of\s+operations)?\.?\s*$",
    re.IGNORECASE,
)
_MDA_LINKTEXT_RE = re.compile(r"management.?s\s+discussion\s+and\s+analysis", re.IGNORECASE)
_FIRST_HASH_HREF_RE = re.compile(r'href="(#[^"]+)"')
_AUDIT_REPORT_HEADING_RE = re.compile(
    r"report of independent registered public accounting firm", re.IGNORECASE
)
_AUDIT_OPINION_CONTEXT_RE = re.compile(
    r"to the (board of directors|shareholders|stockholders)|opinion", re.IGNORECASE
)
_TOC_PAGENUM_ONLY_LINE_RE = re.compile(r"^\d{1,4}$")


def _slice_to_next_audit_report_heading(text_from_start: str) -> str | None:
    """Given plain text starting at a resolved MD&A start, return the
    substring up to (not including) the first REAL "Report of Independent
    Registered Public Accounting Firm" heading -- a near-universal 10-K
    heading that immediately precedes the financial statements, confirmed
    to reliably bound the end of the real MD&A/Financial-Section content in
    all 9 known CVX/XOM/JPM stub filings. Skips mentions of the same phrase
    inside a TOC listing (a bare page number or nothing substantive
    immediately following) rather than a real heading (immediately followed
    by audit-opinion language).
    """
    for m in _AUDIT_REPORT_HEADING_RE.finditer(text_from_start):
        after = text_from_start[m.end(): m.end() + 300]
        first_line_after = after.split("\n", 1)[0].strip()
        if _TOC_PAGENUM_ONLY_LINE_RE.match(first_line_after) or not first_line_after:
            if not _AUDIT_OPINION_CONTEXT_RE.search(after):
                continue
        end_local = m.start()
        if end_local < 500:  # too close to the start to be real content
            return None
        return text_from_start[:end_local].strip()
    return None


def _first_hash_href_in(html_slice: str) -> str | None:
    m = _FIRST_HASH_HREF_RE.search(html_slice)
    return m.group(1)[1:] if m else None


def _find_mda_link_target_nearby(html_text: str, region_start: int, region_len: int = 20000) -> str | None:
    """Look for an `<a href="#...">` whose link text matches the MD&A
    heading within a raw-HTML region right after `region_start` -- used to
    detect (and hop through) a secondary index/TOC page rather than mistake
    it for real content."""
    region = html_text[region_start: region_start + region_len]
    soup = BeautifulSoup(region, _PARSER)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("#"):
            continue
        if _MDA_LINKTEXT_RE.search(a.get_text(" ", strip=True)):
            return href[1:]
    return None


def resolve_mda_via_anchor_hop(html_text: str, stub_start: int, stub_end: int) -> str | None:
    """Strategy 1 -- follow an internal hyperlink embedded in the Item 7
    pointer sentence itself (up to 3 hops, to handle a secondary index/TOC
    page in between), then bound the end via
    _slice_to_next_audit_report_heading(). Returns None if the pointer
    sentence has no hyperlink at all, or if the hopped-to content doesn't
    look like a real MD&A heading."""
    anchor_id = _first_hash_href_in(html_text[stub_start:stub_end])
    if anchor_id is None:
        return None

    offset = None
    for _hop in range(3):
        offset = find_anchor_offset(html_text, anchor_id)
        if offset is None:
            return None
        offset = _end_of_enclosing_tag(html_text, offset)

        next_anchor_id = _find_mda_link_target_nearby(html_text, offset)
        if next_anchor_id is not None and next_anchor_id != anchor_id:
            anchor_id = next_anchor_id
            continue

        sample = html_fragment_to_text(html_text[offset: offset + 4000])
        sample_lines = [l for l in sample.split("\n") if l.strip()]
        if any(_MDA_HEADING_LINE_RE.match(l.strip()) for l in sample_lines[:5]):
            break
        return None
    else:
        return None

    tail_text = html_fragment_to_text(html_text[offset:])
    return _slice_to_next_audit_report_heading(tail_text)


def _prev_line_looks_like_heading_boundary(prev_line: str) -> bool:
    """True if `prev_line` (the line immediately before a candidate MD&A
    heading line) is consistent with the heading being a real, standalone
    heading rather than a mid-sentence cross-reference that happens to
    contain the same words. Real headings in these filings are preceded by
    either nothing, a running-header page number, or the end of an unrelated
    sentence/heading (terminal punctuation) -- confirmed real false-positive
    this excludes: CVX's Item 1 Business section text "... some of which are
    also discussed in the section [heading text], are presented below." --
    the preceding line there ends mid-clause, with no terminal punctuation.
    """
    prev_line = prev_line.strip()
    if not prev_line:
        return True
    if _TOC_PAGENUM_ONLY_LINE_RE.match(prev_line):
        return True
    return prev_line[-1] in ".!?:”\")'"


def resolve_mda_via_text_heuristic(full_text: str) -> str | None:
    """Strategy 2 (fallback, used only when strategy 1 finds no hyperlink at
    all in the pointer sentence -- confirmed real case: XOM's 2024/2025
    10-Ks and all 3 of JPM's). Scans the whole document's plain text for a
    standalone MD&A heading line that isn't the Item-7 stub itself, a
    TOC-listing row, or a mid-sentence cross-reference (see
    _prev_line_looks_like_heading_boundary()), and requires the next several
    lines to be prose-dense (real content), not another sparse index row.
    """
    lines = full_text.split("\n")
    offsets = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1

    for i, line in enumerate(lines):
        if not _MDA_HEADING_LINE_RE.match(line.strip()):
            continue
        prev_line = lines[i - 1] if i > 0 else ""
        next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
        if not _prev_line_looks_like_heading_boundary(prev_line):
            continue
        if STUB_REFERENCE_LANGUAGE_RE.search(next_line):
            continue  # this IS the Item 7 stub occurrence itself
        if _TOC_PAGENUM_ONLY_LINE_RE.match(next_line):
            continue  # a TOC-listing row (heading immediately followed by a bare page number)
        lookahead = lines[i + 1: i + 8]
        dense_lines = sum(1 for l in lookahead if len(l.strip()) > 150)
        if dense_lines < 2:
            continue  # doesn't look like the start of real prose content
        return _slice_to_next_audit_report_heading("\n".join(lines[i:]))

    return None


def resolve_incorporated_by_reference_mda(
    html_text: str, stub_start: int, stub_end: int, full_text: str | None = None,
) -> str | None:
    """Try both strategies in order. `html_text` is the full document's raw
    (SGML-wrapper-stripped) HTML; `stub_start`/`stub_end` are the raw-HTML
    offsets of the Item 7 anchor-based match that turned out to be a stub.
    Returns the real MD&A text if found, else None.

    `full_text` is an optional already-computed plain-text rendering of the
    whole document (R7: the caller may already have paid for it), used only
    by strategy 2. Passing it changes nothing about the result.
    """
    text = resolve_mda_via_anchor_hop(html_text, stub_start, stub_end)
    if text is not None:
        return text
    if full_text is None:
        full_text = html_fragment_to_text(html_text)
    return resolve_mda_via_text_heuristic(full_text)


# ---------------------------------------------------------------------------
# HTML -> clean text
# ---------------------------------------------------------------------------


_SGML_WRAPPER_RE = re.compile(r"<TEXT>\r?\n?(.*?)\r?\n?</TEXT>", re.IGNORECASE | re.DOTALL)


def strip_sgml_document_wrapper(raw: str) -> str:
    """Some older filings' per-document URLs (confirmed on a 2023 Apple
    8-K exhibit fetched directly from sec.gov, not a caching artifact --
    same content over an uncached curl) are served with the as-submitted
    SGML `<DOCUMENT><TYPE>...<SEQUENCE>...<FILENAME>...<DESCRIPTION>...
    <TEXT>...actual HTML...</TEXT></DOCUMENT>` wrapper still attached,
    instead of bare HTML. BeautifulSoup has no way to know `<TYPE>`,
    `<SEQUENCE>`, etc. aren't real tags with meaningful text content, so
    without stripping this first, the header field VALUES (e.g. literally
    "EX-99.1", a sequence number, the filename) leak into the extracted
    text as if they were part of the document. Only strips when the
    wrapper is actually present -- most documents fetched this way are
    plain HTML with no wrapper at all, and are returned unchanged.
    """
    if not raw.lstrip()[:11].upper().startswith("<DOCUMENT>"):
        return raw
    m = _SGML_WRAPPER_RE.search(raw)
    return m.group(1) if m else raw


_DISPLAY_NONE_RE = re.compile(r"display\s*:\s*none", re.IGNORECASE)


def html_fragment_to_text(html_fragment: str) -> str:
    """Parse an HTML fragment (a whole document, or a byte-slice of one) and
    return clean, whitespace-normalized plain text. Drops <script>/<style>
    content and, importantly, hidden iXBRL metadata -- modern SEC filings
    wrap a block of machine-readable-only tagging (`<ix:header>`, containing
    XBRL `<xbrli:context>`/member-dimension noise like "us-gaap:
    CommonStockMember") inside `<div style="display:none">`, meant to never
    render in a browser. BeautifulSoup's `.get_text()` doesn't know about
    CSS `display:none` and includes this noise as if it were visible body
    text (confirmed on a real BAC 8-K: ~30 lines of raw XBRL member-tag
    names prepended before the actual filing text) -- so it's stripped
    explicitly here, along with `<head>` (title/meta, not body content).
    bs4's `.get_text()` already HTML-entity-decodes and drops all tags.
    Collapses repeated blank lines and in-line whitespace runs (including
    non-breaking spaces, common in SEC filings) without collapsing
    paragraph breaks entirely, so the result is prose-readable, not a
    single wall of text.
    """
    soup = BeautifulSoup(html_fragment, _PARSER)
    for tag in soup(["script", "style", "head"]):
        tag.decompose()
    for tag in soup.find_all("ix:header"):
        tag.decompose()
    for tag in soup.find_all(style=_DISPLAY_NONE_RE):
        tag.decompose()
    raw = soup.get_text("\n")
    raw = raw.replace("\xa0", " ").replace("​", "")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in raw.split("\n")]
    lines = [line for line in lines if line]  # drop now-empty lines
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Extraction orchestration
# ---------------------------------------------------------------------------


@dataclass
class ExtractionResult:
    """One section ATTEMPT. Every attempt produces one of these -- including
    the ones that failed (R9), which carry `text=""` and a FAIL reason code.

    `flags` is the full list; `reason_code` is the single highest-precedence
    entry in it (C5). Never construct this directly for a real extraction --
    go through `_finish_section()`, which applies the length floor, the two
    head checks and the confidence invariant (C6).
    """

    text: str
    method: str  # 'anchor' | 'heading_regex' | 'whole_document' |
                  # 'item202_slice' | 'none' |
                  # 'incorporated_by_reference_resolved' |
                  # 'incorporated_by_reference_unresolved'
    confidence: str  # 'high' | 'medium' | 'low'
    form: str = ""
    section_type: str = ""
    flags: list[str] = field(default_factory=list)
    stub_language_present: bool = False
    # P5 / N1: stored per row so the garble screen is re-auditable from the
    # artifact, without a re-extraction.
    ctrl_ratio: float | None = None
    eng_word_share: float | None = None
    # earnings-only measurements (None on periodic rows)
    population_gate: str | None = None
    quarter_cell_size: int | None = None
    results_signature_present: bool | None = None
    item202_prefix_chars: int | None = None
    item202_block_words: int | None = None
    supplemental_tail_share: float | None = None
    note: str = ""

    @property
    def reason_code(self) -> str:
        return primary_reason_code(self.flags)

    @property
    def status(self) -> str:
        base = status_for(self.reason_code, self.form, self.section_type)
        if base in (STATUS_FAIL, STATUS_ITEM_ABSENT_FROM_TOC):
            return base
        # A row whose PRIMARY code is an OK code but which still carries a
        # FLAGGED code somewhere in `flags` is FLAGGED. Deliberately the
        # safe direction: a flag can never be hidden by precedence.
        if any(REASON_STATUS.get(f) == STATUS_FLAGGED for f in self.flags):
            return STATUS_FLAGGED
        return base

    @property
    def located(self) -> bool:
        return self.status in (STATUS_OK, STATUS_FLAGGED)


def failed_result(form: str, section: str, reason_code: str, note: str = "") -> ExtractionResult:
    return ExtractionResult(
        text="", method="none", confidence="low", form=form, section_type=section,
        flags=[reason_code], note=note,
    )


# ---------------------------------------------------------------------------
# F3: the two head checks (C14) -- measured on 263 pilot sections
# ---------------------------------------------------------------------------
#
# `head_foreign_item` fired 1/263 (0.4%) and that one fire was a real defect:
# `0001628280-26-026673`, a 10-Q whose "MD&A" slice opens "ITEM 3.
# QUANTITATIVE AND QUALITATIVE DISCLOSURES ABOUT MARKET RISK" -- 1,770 words,
# anchor/high, ABOVE the (10-Q, MDA) floor, i.e. invisible to every other
# guard in this file.
#
# The rule compares the FIRST "Item N" token anywhere in text[:200] on its
# NUMBER ONLY. A stricter variant (label anchored at the very start, compared
# exactly "1A" vs "1A") was measured on the same 263 rows and was worse: it
# produced a false positive on the ICE "ITEM 1(A). RISK FACTORS" dialect and
# missed the real defect below, whose head starts "PART II. OTHER
# INFORMATION...".
#
# KNOWN MISS, stated rather than closed with a cleverer regex:
# `0001628280-26-032278` is a "RISK_FACTORS" slice opening "PART II. OTHER
# INFORMATION ITEM 1. LEGAL PROCEEDINGS" (422 words, anchor/high). Its first
# item number is "1", which EQUALS the 1A target's number, so neither variant
# catches it. It is caught only by `head_keyword_absent` and by the manual QA
# sample. This is the E1 loose-heading-regex lesson applied to the guard.
_HEAD_ITEM_TOKEN_RE = re.compile(r"item\s*\(?\s*([0-9]{1,2})", re.IGNORECASE)
HEAD_ITEM_CHECK_CHARS = 200
HEAD_KEYWORD_CHECK_CHARS = 300
# Number-only targets: RISK_FACTORS is item 1A, whose NUMBER is "1".
_HEAD_TARGET_ITEM_NUMBER = {
    ("10-K", "MDA"): "7", ("10-Q", "MDA"): "2",
    ("10-K", "RISK_FACTORS"): "1", ("10-Q", "RISK_FACTORS"): "1",
}
_SECTION_TITLE_KEYWORD = {"MDA": "discussion and analysis", "RISK_FACTORS": "risk factor"}


def head_foreign_item(text: str, form: str, section: str) -> bool:
    target = _HEAD_TARGET_ITEM_NUMBER.get((form, section))
    if target is None:
        return False
    m = _HEAD_ITEM_TOKEN_RE.search(text[:HEAD_ITEM_CHECK_CHARS])
    if m is None:
        return False
    return m.group(1).lstrip("0") != target


def head_keyword_absent(text: str, section: str) -> bool:
    """INFORMATIONAL ONLY (C14): fired 10/263 in the pilot, of which ~3 were
    real defects and 7 were benign slices that simply start one sub-heading
    in ("CRITICAL ACCOUNTING POLICIES...", "WHAT YOU WILL FIND IN THIS
    MD&A"). A good sampling frame for the QA read, a bad verdict.

    Compared with all whitespace removed on both sides, for the same reason
    `locate_item_section_by_anchor` does it: JNJ renders headings with
    letter-spacing markup ("management's d iscussion and a nalysis").
    """
    keyword = _SECTION_TITLE_KEYWORD.get(section)
    if keyword is None:
        return False
    head = re.sub(r"\s+", "", text[:HEAD_KEYWORD_CHECK_CHARS].lower())
    return re.sub(r"\s+", "", keyword) not in head


# ---------------------------------------------------------------------------
# P5 fix 3 (N1): the garbled-text screen -- a UNION of two measurements
# ---------------------------------------------------------------------------
#
# The class: sections whose character stream is not readable prose at all.
# Ford `0000037996-18-000082` (3,333 w) and `0000037996-19-000065` (2,609 w)
# are Caesar-shifted PDF font maps -- ")RUG\x03'HOLYHUV" is "Ford Delivers" --
# and shipped at OK / high / zero flags with `prose_word_share = 1.0`, i.e.
# they would have been packed into labeling chunks as clean prose.
#
# Neither single screen finds the whole class, which is why this is a union:
#   * P1 proposed `nonascii_ratio`. REFUTED at P3: Freeport
#     `0000831259-24-000026` scores 0.0136, below the corpus 99th percentile.
#   * P3 proposed `ctrl_ratio >= 0.02` (n=4, 60x margin). REFUTED at P4:
#     Digital Realty `0001297996-18-000125` (2,063 words of font-map garbage,
#     prose share 0.93) scores EXACTLY 0.00000 on it.
#   * P4 proposed an English-word-share screen at < 0.12. It finds the Digital
#     Realty row (0.036) but not Digital Realty `0001297996-16-000203`, whose
#     garbage is Wingdings bullet glyphs around a legible table (eng share
#     0.333, ctrl ratio 0.0157).
#
# Shipped: `ctrl_ratio >= 0.01` OR `eng_word_share < 0.12`. The ctrl threshold
# is P3's, LOWERED from 0.02 with the count stated: 0.02 selects 3 rows, 0.01
# selects 4 (the fourth being the Digital Realty 2016 row above) and the next
# row in the corpus sits at 0.00365, a 4.3x margin. Moving a threshold in the
# direction that catches MORE bad rows, on a flag that can never filter, is
# the safe direction; the counts are in `data/f3/status/P5_fixes.md`.
#
# BOTH thresholds are fitted on a class of five hand-read rows. This is a
# FLAG that downgrades confidence and routes to review; it never drops a row,
# and both metrics are stored per row so the screen can be re-fitted later
# without re-extracting. Known false positive, named rather than tuned away:
# Emerson `0000032604-25-000094`, a clean numeric table (eng share 0.111).
GARBLE_CTRL_RATIO = 0.01
GARBLE_ENG_WORD_SHARE = 0.12
GARBLE_MIN_ALPHA_TOKENS = 50  # below this the word share is too noisy to use
_ALPHA_TOKEN_RE = re.compile(r"[A-Za-z]{2,}")
# P4's list (`data/f3/p4_redteam/p4_garble_scan.py`), reproduced verbatim so
# the corpus-wide re-census reproduces its measurement exactly.
_COMMON_WORDS = frozenset("""the of and to in a is for that on as with by are be this or from at
it was an we our its will not have has had were which their they may us can
also been more other such any all than into no if under about report company
year quarter results net income loss cash total share shares per revenue
revenues operating financial statements business risk factors management
discussion analysis condition operations period periods three six nine months
ended december march june september increase decrease compared primarily due
million billion percent tax taxes interest debt equity assets liabilities
customers products services market markets growth costs expenses margin
including related certain new during first second third fourth
""".split())


def garble_stats(text: str) -> tuple[float, float | None]:
    """(ctrl_ratio, eng_word_share). The share is None when the section has
    fewer than GARBLE_MIN_ALPHA_TOKENS alphabetic tokens."""
    if not text:
        return 0.0, None
    ctrl = sum(1 for ch in text
               if unicodedata.category(ch) in ("Cc", "Co", "Cn") and ch not in "\n\t")
    toks = _ALPHA_TOKEN_RE.findall(text[:200_000])
    share = None
    if len(toks) >= GARBLE_MIN_ALPHA_TOKENS:
        share = round(sum(1 for w in toks if w.lower() in _COMMON_WORDS) / len(toks), 5)
    return round(ctrl / len(text), 5), share


def text_is_garbled(ctrl_ratio: float, eng_word_share: float | None) -> bool:
    return (ctrl_ratio >= GARBLE_CTRL_RATIO
            or (eng_word_share is not None and eng_word_share < GARBLE_ENG_WORD_SHARE))


def _finish_section(result: ExtractionResult) -> ExtractionResult:
    """Apply the length floor, the head checks, the garble screen and the
    confidence invariant.

    R3: the floor FLAGS, it never filters -- nothing here can drop a row.
    C6: a FLAGGED row may never carry confidence='high'. This is the direct
    fix for the four pilot rows of 43/50/55/102 words that came out
    anchor/high under E1's rules.
    """
    words = len(result.text.split())
    floor = MIN_SECTION_WORDS.get((result.form, result.section_type), 0)
    if words < floor:
        result.flags.append("below_length_floor")
    result.ctrl_ratio, result.eng_word_share = garble_stats(result.text)
    if text_is_garbled(result.ctrl_ratio, result.eng_word_share):
        result.flags.append("garbled_text")
    if result.section_type in _SECTION_TITLE_KEYWORD:
        if head_foreign_item(result.text, result.form, result.section_type):
            result.flags.append("head_foreign_item")
        if head_keyword_absent(result.text, result.section_type):
            result.flags.append("head_keyword_absent")
    if result.status == STATUS_FLAGGED and result.confidence == "high":
        result.confidence = "medium"
    return result


# ---------------------------------------------------------------------------
# F3: periodic (10-K / 10-Q) section location -- parse once (R7 / C4)
# ---------------------------------------------------------------------------

PERIODIC_SECTIONS = ("MDA", "RISK_FACTORS")


class _LazyFullText:
    """One whole-document `html_fragment_to_text()` per document, at most.

    The whole-document parse is the expensive step (measured: 1.05s of a
    1.42s filing), and up to three code paths want it -- the heading-regex
    fallback for each of the two sections, and the stub resolver.
    """

    def __init__(self, html_text: str):
        self._html = html_text
        self._text: str | None = None

    def get(self) -> str:
        if self._text is None:
            self._text = html_fragment_to_text(self._html)
        return self._text


def _maybe_resolve_mda_stub(
    text: str, form: str, section: str, html_text: str,
    span: tuple[int, int] | None, full_text: _LazyFullText,
    extra_flags: tuple[str, ...] = (),
) -> ExtractionResult | None:
    """R4/C7: the stub resolver is triggered by WORD COUNT ALONE.

    E1 additionally required `STUB_REFERENCE_LANGUAGE_RE` to match before it
    would even try, and that gate rejected every real stub it met in the E2
    pilot (0 of 4: Sempra, US Bancorp, JPMorgan-2017, plus a wrong slice).
    Returns None when this is not a `(10-K, MDA)` extraction under the
    ceiling -- i.e. not a stub candidate at all.

    Applies to BOTH location paths, because one of the four measured stubs
    (US Bancorp `0001193125-17-053947`) is located by the heading-regex
    fallback, not by an anchor. When there is no usable anchor TOC
    (`span is None`) the anchor-hop strategy has nothing to hop through, so
    only the text heuristic runs.
    """
    if not (form == "10-K" and section == "MDA"):
        return None
    if len(text.split()) >= MDA_STUB_WORD_CEILING:
        return None

    stub_language = bool(STUB_REFERENCE_LANGUAGE_RE.search(text))
    if span is not None:
        resolved_text = resolve_incorporated_by_reference_mda(
            html_text, span[0], span[1], full_text=full_text.get(),
        )
    else:
        resolved_text = resolve_mda_via_text_heuristic(full_text.get())

    if resolved_text and len(resolved_text.split()) >= MIN_SECTION_WORDS.get((form, section), 0):
        return _finish_section(ExtractionResult(
            text=resolved_text, method="incorporated_by_reference_resolved",
            confidence="medium", form=form, section_type=section,
            flags=["mda_stub_resolved", *extra_flags],
            stub_language_present=stub_language,
        ))
    # Couldn't confidently locate the real content elsewhere in this
    # document -- keep the short text as filed but mark it, so it can never
    # be mistaken for a real, substantive MD&A downstream.
    # `classify_stub_reason` separates "points elsewhere in THIS document"
    # (recoverable in principle) from "points at ANOTHER document"
    # (unrecoverable at 0 GETs -- §1.3, main-session item §13.1).
    return _finish_section(ExtractionResult(
        text=text, method="incorporated_by_reference_unresolved",
        confidence="low", form=form, section_type=section,
        flags=[classify_stub_reason(text), *extra_flags],
        stub_language_present=stub_language,
    ))


def _locate_one_section(
    html_text: str, toc_entries: list[TocEntry], form: str, section: str,
    full_text: _LazyFullText, cik: int = 0, fired: dict | None = None,
) -> ExtractionResult:
    target_item_no = "7" if section == "MDA" and form == "10-K" else (
        "2" if section == "MDA" else "1A"
    )
    # Required so a same-numbered non-Item TOC entry (confirmed real case:
    # UNH's Notes-to-financial-statements index also uses bare "N. Title"
    # rows) can't be silently mistaken for the real Item heading -- see
    # locate_item_section_by_anchor()'s docstring.
    required_keywords = ("discussion and analysis",) if section == "MDA" else ("risk factor",)

    def _out(result: ExtractionResult) -> ExtractionResult:
        """Per-filer edge handlers run HERE, not in `extract_filing`, because
        this is the only scope that still holds the document (P5 / N6)."""
        return apply_edge_handlers(result, cik, form, section, fired=fired, ctx=EdgeContext(
            html_text=html_text, toc_entries=toc_entries, full_text=full_text))

    span = locate_item_section_by_anchor(html_text, toc_entries, target_item_no, required_keywords)
    if span is not None:
        start, end = span
        text = html_fragment_to_text(html_text[start:end])
        if len(text) < MIN_SECTION_CHARS:
            return failed_result(form, section, "anchor_span_below_min_chars")

        stub = _maybe_resolve_mda_stub(text, form, section, html_text, (start, end), full_text)
        if stub is not None:
            return _out(stub)
        return _out(_finish_section(ExtractionResult(
            text=text, method="anchor", confidence="high", form=form, section_type=section,
        )))

    if toc_entries:
        # This document DOES have a working anchor-linked TOC, and it was
        # parsed successfully (non-empty). Two very different things can have
        # happened, and before P5 both were reported as `item_absent_from_toc`.
        if matching_toc_entry_indices(toc_entries, target_item_no, required_keywords):
            # (a) The item IS listed, with the right number and the right title
            # keyword, and the anchor path still failed -- a dangling anchor id
            # or a degenerate span. This is an extractor defect, not an absent
            # item: 148 FAIL rows (P3 §2.2) and 83 rows that were being filed
            # under EXPECTED_ABSENT (P4b). Run the guarded recovery ladder.
            got = recover_toc_present_section(
                html_text, toc_entries, form, section, target_item_no,
                required_keywords, full_text)
            if isinstance(got, str):
                return failed_result(form, section, "toc_recovery_declined", note=got)
            text, method, code, end_guarded = got
            flags = [code] + (["toc_recovery_end_guarded"] if end_guarded else [])
            return _out(_finish_section(ExtractionResult(
                # F1' spans are anchor-located but end-guarded, F2' spans come
                # from the heading regex: neither is ever better than `medium`,
                # and an end-guard-rescued span drops to `low`.
                text=text, method=method,
                confidence="low" if (end_guarded or code == "toc_recovered_f2") else "medium",
                form=form, section_type=section, flags=flags,
            )))
        # (b) The TOC simply doesn't list `target_item_no` at all. Confirmed on
        # real filings (GS, XOM, ABBV, JNJ, MRK 10-Qs): some filers omit "Item
        # 1A. Risk Factors" from Part II entirely when there's nothing new to
        # disclose, rather than including a short "no material changes"
        # paragraph. Falling back to the heading regex here is actively
        # dangerous, not just lower-confidence: on XOM's 2023-10-31 10-Q, the
        # ONLY "Item 1A" text in the whole document turned out to be a compact
        # cross-reference sentence ("...Item 1A. Risk Factors of ExxonMobil's
        # 2022 Form 10-K.") immediately followed, in the same paragraph, by the
        # start of the (unrelated) Item 1 Legal Proceedings text -- the regex
        # fallback would silently merge the two into a single
        # plausible-looking but WRONG "Risk Factors" section. P4b measured that
        # intuition at scale: the recovery guards admit 131 rows here and 89 of
        # them are garbage. So the ladder does NOT run; the row keeps failing,
        # and all that changes is that a body heading which passes both guards
        # is recorded as a review marker.
        flags = ["item_absent_from_toc"]
        if body_heading_passes_guards(full_text, form, section):
            flags.append("item_body_heading_present")
        return ExtractionResult(text="", method="none", confidence="low",
                                form=form, section_type=section, flags=flags)

    # Only reached when this document has NO working anchor-linked TOC at
    # all (confirmed real cause on COP/CVX/JNJ 10-Ks, before a bare-number
    # TOC row format fix: those filers' TOC rows read "7. Management's
    # Discussion..." instead of "Item 7. Management's Discussion...").
    # Fall back to the tight-gap heading regex, working off the
    # whole-document plain text since it doesn't need to distinguish markup.
    text_all = full_text.get()
    span = locate_item_section_by_heading_regex(text_all, form, section)
    if span is not None:
        start, end = span
        text = text_all[start:end].strip()
        if len(text) >= MIN_SECTION_CHARS:
            stub = _maybe_resolve_mda_stub(
                text, form, section, html_text, None, full_text,
                extra_flags=("heading_regex_fallback",))
            if stub is not None:
                return _out(stub)
            # D5: this path fired 0 times in E1's 884 sections and 10 times
            # in 288 E2 pilot attempts. Always low confidence, always
            # flagged, deliberately over-sampled by the QA read.
            return _out(_finish_section(ExtractionResult(
                text=text, method="heading_regex", confidence="low",
                form=form, section_type=section, flags=["heading_regex_fallback"],
            )))

    return failed_result(form, section, "no_toc_and_no_heading_match")


def periodic_relative_path(cik: int, accession_number: str, primary_document: str) -> str:
    return f"/Archives/edgar/data/{cik}/{accession_number.replace('-', '')}/{primary_document}"


def extract_periodic_sections(
    read, cik: int, accession_number: str, primary_document: str, form: str,
    fired: dict | None = None,
) -> dict[str, ExtractionResult]:
    """Both sections of one 10-K/10-Q from ONE parse of the document (R7).

    `read` is a callable `(relative_path) -> str`; it defaults to nothing
    on purpose -- the caller decides, and F3's caller is always
    `read_cached_document`, which cannot fetch.
    """
    html_text = strip_sgml_document_wrapper(
        read(periodic_relative_path(cik, accession_number, primary_document))
    )
    soup = BeautifulSoup(html_text, _PARSER)  # ONCE, for both sections
    toc_entries = find_toc_item_anchors(soup)
    full_text = _LazyFullText(html_text)
    return {
        section: _locate_one_section(html_text, toc_entries, form, section, full_text,
                                      cik=cik, fired=fired)
        for section in PERIODIC_SECTIONS
    }


def extract_item_section(
    read, cik: int, accession_number: str, primary_document: str,
    form: str, section: str,
) -> ExtractionResult:
    """Single-section wrapper, kept so call sites and tests that want one
    section keep working. `extract_periodic_sections` is what `run()` uses.
    """
    return extract_periodic_sections(read, cik, accession_number, primary_document, form)[section]


# ---------------------------------------------------------------------------
# F3: 8-K earnings documents (C8) -- item-2.02 slicing, population gate,
# supplemental dilution
# ---------------------------------------------------------------------------

ITEM_202_RE = re.compile(r"item\s*2\.02", re.IGNORECASE)
_ANY_ITEM_NUMBER_RE = re.compile(r"item\s*(\d)\.(\d\d)", re.IGNORECASE)

ITEM202_THIN_BLOCK_WORDS = 200
ITEM202_PREFIX_LARGE_CHARS = 4000

# The results-announcement signature. NOT a suppressor (R1): the gate fires
# on the multi-filing (CIK, quarter) cell alone, and this only splits the
# WARN into two severities. Marker set as measured at P0 -- over all 10,567
# selections it splits 1,519 multi-cell rows into 890 WARN_MULTI / 629
# WARN_MULTI_NOSIG.
#
# Why it is not allowed to suppress: H4's narrowed variant was re-measured on
# H4's own 155-row ledger at recall 8/9, not 9/9. The row it drops is
# `0001104659-22-112514` -- Intercontinental Exchange furnishing BAKKT's
# results, not its own. That text contains "quarterly results", "per share",
# "press release" and "months ended": a results-announcement signature cannot
# tell WHOSE results are being announced, which is precisely the error class.
RESULTS_SIGNATURE_MARKERS = (
    "today reported", "today announced", "announced today",
    "for immediate release", "announced results",
    "reports first", "reports second", "reports third", "reports fourth",
    "reports results",
    "announces first", "announces second", "announces third", "announces fourth",
    "per diluted share",
)

# CALIBRATED AT P1 (`data/f3/p1_calibrate/p1_supplemental_markers.py`), on a
# seeded 1,500-row EX-99 sample + all Simon Property / AvalonBay / Prologis
# rows = 1,613 documents read. F2 §5's deck-title rule: a marker stays only if
# its measured hits are dominated by true positives, with the false positive
# NAMED.
#
#   marker                              hits   flagged (share >= 0.5)
#   supplemental information              92        41
#   supplemental financial information    46        14
#   supplemental data                     12         1
#   supplemental operating                 8         0
#   supplemental package                   0         0   <- REMOVED, DEAD
#
# Named FALSE POSITIVE (2 of 158 hits, both BELOW the flag threshold):
# ConocoPhillips `0001157523-15-002627` / `0001157523-15-003543`, where a line
# break split a sentence into the fragment "supplemental information, go to"
# (shares 0.322 / 0.329). Left in rather than special-cased -- naming it is
# this project's standard (F2 §5, Danaher), and no FLAGGED row is affected.
#
# Named MISS, measured not fixed: Simon Property `0001104659-21-013702` --
# H4 §8.4's own anchor -- scores 0.000. Its 14,916-word EX-99.1 IS the
# combined "EARNINGS RELEASE AND SUPPLEMENTAL INFORMATION" book: the only
# whole-line "SUPPLEMENTAL INFORMATION" heading is on the title page (inside
# the first 20%) and the rest is marked solely by a repeating page header
# ("4Q 2020 SUPPLEMENTAL"). There is no tail boundary to find, which is
# exactly why §6 forbids truncating this class. That row stays visible
# through `prose_word_share` (0.233) and `word_count`, and the class census
# is P3's. Widening the marker to a bare "supplemental" is NOT the fix: the
# same document contains the prose line "Supplemental information on our
# fourth quarter 2020 performance is available at investors.simon.com".
# (That 165-char line is already excluded by the heading-length guard below,
# which is doing real work.)
# AvalonBay (40 rows) and Prologis (44 rows) score 0.000 throughout, as their
# clean two-exhibit shape predicts.
SUPPLEMENTAL_MARKERS = (
    "supplemental information",
    "supplemental financial information",
    "supplemental operating",
    "supplemental data",
)
SUPPLEMENTAL_MIN_POSITION_SHARE = 0.20
SUPPLEMENTAL_DILUTED_SHARE = 0.50
_SUPPLEMENTAL_HEADING_MAX_CHARS = 60
_EDGE_PUNCT_RE = re.compile(r"^[^0-9a-z]+|[^0-9a-z]+$")


def filing_quarter(filing_date: str) -> str:
    """'2021-02-08' -> '2021Q1'. The population gate's cell key is
    (cik, calendar quarter of FILING date) -- filing date, never report
    date (HANDOFF §7 point-in-time discipline)."""
    year, month = int(filing_date[:4]), int(filing_date[5:7])
    return f"{year}Q{(month - 1) // 3 + 1}"


def results_signature_present(text: str) -> bool:
    collapsed = re.sub(r"\s+", " ", text.lower())
    return any(marker in collapsed for marker in RESULTS_SIGNATURE_MARKERS)


def population_gate_level(quarter_cell_size: int, signature_present: bool) -> str:
    """OK | WARN_MULTI | WARN_MULTI_NOSIG (§4.3). Both WARN levels are flags
    on rows that are still EXTRACTED -- the gate never drops text."""
    if quarter_cell_size is None or quarter_cell_size <= 1:
        return "OK"
    return "WARN_MULTI" if signature_present else "WARN_MULTI_NOSIG"


def item202_block_words(text: str, match: re.Match) -> int | None:
    """Words between the first 'Item 2.02' and the next DIFFERENT item
    heading; None if no other item heading follows.

    This number is RECORDED, never used as a boundary (R2). Ending the
    slice there would leave under 200 words in 45 of 210 sections -- Humana
    8 words, BAC 12, Xcel 14, Goldman 8, Emerson 30 -- because those filers
    put the substance under 7.01/8.01 and incorporate it into 2.02 by
    reference. Cutting there is exactly the silent-mangling this project's
    hard rules forbid; flagging it is the honest version.
    """
    for m in _ANY_ITEM_NUMBER_RE.finditer(text, match.end()):
        if f"{m.group(1)}.{m.group(2)}" != "2.02":
            return len(text[match.start():m.start()].split())
    return None


def supplemental_tail_share(text: str) -> float:
    """Share of characters after a supplemental-package heading (§6).

    F3 MEASURES this class; it never truncates the text. Truncating at a
    guessed boundary is exactly "extraction that mangles content", and the
    release narrative's end is not reliably marked across filers.
    """
    if not text:
        return 0.0
    total = len(text)
    min_offset = SUPPLEMENTAL_MIN_POSITION_SHARE * total
    offset = 0
    for line in text.split("\n"):
        line_start = offset
        offset += len(line) + 1
        if line_start < min_offset:
            continue
        norm = _EDGE_PUNCT_RE.sub("", re.sub(r"\s+", " ", line.strip().lower()))
        if len(norm) > _SUPPLEMENTAL_HEADING_MAX_CHARS:
            continue
        if any(norm == marker or norm.startswith(marker) for marker in SUPPLEMENTAL_MARKERS):
            return (total - line_start) / total
    return 0.0


def extract_earnings_document(
    read, relative_path: str, section_type: str, gate_context: dict | None = None,
) -> ExtractionResult:
    """The already-selected earnings document. F3 NEVER re-resolves exhibits
    (`ingest_metadata.select_earnings_document` owns that choice, H4 §7).

    `gate_context` carries `quarter_cell_size` -- a corpus-level quantity
    computed once by `run()` over the whole earnings population, so a shard
    can never mis-compute it from its own slice.
    """
    gate_context = gate_context or {}
    cell = gate_context.get("quarter_cell_size")
    cell = int(cell) if cell is not None else 1

    html_text = strip_sgml_document_wrapper(read(relative_path))
    text = html_fragment_to_text(html_text)

    # Measured on the WHOLE document text, before any item-2.02 slicing, so
    # the 890/629 severity split reproduces P0's corpus census exactly.
    signature = results_signature_present(text)
    gate = population_gate_level(cell, signature)

    def base(result: ExtractionResult) -> ExtractionResult:
        result.population_gate = gate
        result.quarter_cell_size = cell
        result.results_signature_present = signature
        return result

    if len(text) < MIN_SECTION_CHARS:
        # F2 §5's P5 near-empty class, by name: 12 EX-99 selections (Ford,
        # MetLife, PNC x7, Cigna, Linde x2) are image-only or empty
        # exhibits. F2 wrote that they SHOULD fail F3's floor; they do,
        # loudly, before anything is recalibrated.
        return base(failed_result(
            "8-K", section_type, "empty_after_extraction",
            note=f"{len(text)} chars of extractable text",
        ))

    flags: list[str] = []
    if cell > 1:
        flags.append("earnings_population_gate")

    prefix_chars: int | None = None
    block_words: int | None = None
    method = "whole_document"
    if section_type == "8K_BODY":
        m = ITEM_202_RE.search(text)
        if m is None:
            # 0 of 210 today. Keep the whole document -- never an empty
            # section -- and say so.
            flags.append("earnings_item202_missing")
        else:
            prefix_chars = m.start()
            block_words = item202_block_words(text, m)
            if block_words is not None and block_words < ITEM202_THIN_BLOCK_WORDS:
                flags.append("earnings_item202_block_thin")
            if prefix_chars > ITEM202_PREFIX_LARGE_CHARS:
                flags.append("earnings_item202_prefix_large")
            text = text[m.start():]  # R2: to END OF DOCUMENT, never to the next item
            method = "item202_slice"

    if len(text) < EARNINGS_THIN_DOCUMENT_CHARS:
        flags.append("earnings_thin_document")
    tail_share = supplemental_tail_share(text)
    if tail_share >= SUPPLEMENTAL_DILUTED_SHARE:
        flags.append("earnings_supplemental_diluted")

    return base(_finish_section(ExtractionResult(
        text=text, method=method, confidence="high", form="8-K",
        section_type=section_type, flags=flags,
        item202_prefix_chars=prefix_chars, item202_block_words=block_words,
        supplemental_tail_share=round(tail_share, 4),
    )))


# ---------------------------------------------------------------------------
# F3: prose-share measurement (C16) -- input to F4, not a change to the text
# ---------------------------------------------------------------------------


def prose_stats(text: str) -> tuple[int, float]:
    """(n_prose_paragraphs, prose_word_share) using chunk.py's OWN
    `MIN_PROSE_WORDS`, imported rather than re-implemented.

    Why F3 measures this: a section with zero >=40-word lines produces ZERO
    labeling chunks -- verified on E1's frozen artifacts, n_prose == 0 =>
    n_chunks == 0 in 97 of 97 cases. The cause is structural, not a bug: SEC
    press releases are frequently laid out as tables, so `get_text("\\n")`
    emits one short line per cell, and the zero-prose share for earnings
    sections rises from E1's 4.6% to ~14.7% in an E2 sample. F3 does NOT
    change the text for this (it would break the E1 byte-identity pin and
    `MIN_PROSE_WORDS` is chunk.py's constant, not extract.py's) -- it hands
    F4 the measurement and the decision.
    """
    total = 0
    prose_words = 0
    n_prose = 0
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        words = len(line.split())
        total += words
        if words >= chunk_module.MIN_PROSE_WORDS:
            n_prose += 1
            prose_words += words
    share = (prose_words / total) if total else 0.0
    return n_prose, round(share, 4)


# ---------------------------------------------------------------------------
# F3: per-filer / per-dialect edge handlers (R8 / C11)
# ---------------------------------------------------------------------------
#
# One small named registry, deliberately narrow predicates, exactly like
# F2's `earnings_doc_overrides.csv`. The lazy-elite rule: one documented
# handler per dialect beats one clever universal regex.
#
# Rules, enforced by `test_extract_e2.py`:
#   * `applies_to` is a `(cik, form, section_type)` predicate. A handler that
#     tries to be general belongs in the locator, not here.
#   * every handler carries a docstring naming the filer, the filing that
#     motivated it, and what it was verified against;
#   * every handler has a test and a fired-count line in the P1/P3 report;
#   * a handler that fires 0 times in a full run is reported DEAD.
#
# The registry was EMPTY at P1, deliberately: the five dialect classes P0
# found are all handled where they belong instead -- D1 ("Item 1(A).") and D3
# ("appears on\npages") are shared-across-filers regex dialects fixed in the
# patterns above (C12); D2 (MD&A incorporated from a DIFFERENT document) is a
# reason code because it is unrecoverable at 0 GETs; D4 (anchor lands on a
# foreign item) is the `head_foreign_item` check; D5 (heading-regex fallback)
# is a confidence level. P3's per-filer triage over the real 30,475-attempt
# audit produced its first member (N6 / NIKE, below).

EdgeHandler = namedtuple("EdgeHandler", "name applies_to reason handler")


@dataclass
class EdgeContext:
    """What a handler is allowed to look at. Handlers run inside
    `_locate_one_section`, so unlike at P1 they can re-locate rather than only
    relabel -- which is what N6 needs."""

    html_text: str
    toc_entries: list
    full_text: "_LazyFullText"


def _nike_10q_mda_shared_toc_anchor(result, cik, form, section_type, ctx):
    """NIKE, Inc. (CIK 320187), 10-Q, Part I Item 2 MD&A -- 21 filings,
    2019-10-04 to 2026-04-01 (P3 §7.4 / spot-read card 42).

    THE DIALECT. NIKE's 10-Q table of contents gives several different TOC rows
    the SAME `<a href="#id">` target; from 2019 on, the Part I Item 2 (MD&A)
    row and the Part II Item 1A (Risk Factors) row share one id, and by 2025
    all 25 rows of the TOC share a single id. That id is DEFINED once, at the
    Part II Item 1A heading. So the anchor path resolves the MD&A entry to the
    wrong place and returns Part II: "ITEM 1A. RISK FACTORS ... ITEM 2.
    UNREGISTERED SALES ..." -- 389-1,318 words where the real MD&A is
    7,873-12,961. The Risk Factors extraction on the same documents is correct
    by luck (the shared id happens to sit on its own heading), which is why
    only 21 of NIKE's 66 10-Q attempts are affected.

    VERIFIED AGAINST: `0000320187-19-000071` (2019-10-04, anchor slice 465 w /
    fallback 7,873 w), `0000320187-22-000017` (12,961 w) and
    `0000320187-25-000151` (10,412 w) -- in all three the document's plain text
    holds exactly two "Item 2 ... Management's Discussion" matches, a 66-char
    TOC row and the real section.

    PREDICATE: this CIK, this form, this section, AND the shipped slice must
    already have raised `head_foreign_item` -- so the handler is inert on the
    12 NIKE 10-Q MD&As that extract correctly, and it cannot fire on any other
    filer. It replaces the wrong slice with the heading-regex fallback's, at
    `low` confidence with the fallback's own flag, never at `high`.
    """
    if "head_foreign_item" not in result.flags:
        return None
    text_all = ctx.full_text.get()
    span = locate_item_section_by_heading_regex(text_all, form, section_type)
    if span is None:
        return None
    text = text_all[span[0]:span[1]].strip()
    if len(text) < MIN_SECTION_CHARS:
        return None
    return _finish_section(ExtractionResult(
        text=text, method="heading_regex", confidence="low", form=form,
        section_type=section_type, flags=["heading_regex_fallback"],
    ))


EDGE_HANDLERS: list[EdgeHandler] = [
    EdgeHandler(
        name="nike_10q_mda_shared_toc_anchor",
        applies_to=lambda cik, form, section: (
            cik == 320187 and form == "10-Q" and section == "MDA"),
        reason="NIKE 10-Q TOC rows share one anchor id, defined at Part II Item 1A",
        handler=_nike_10q_mda_shared_toc_anchor,
    ),
]


def apply_edge_handlers(
    result: ExtractionResult, cik: int, form: str, section_type: str,
    handlers: list[EdgeHandler] | None = None, fired: dict | None = None,
    ctx: "EdgeContext | None" = None,
) -> ExtractionResult:
    """Run every handler whose predicate matches, in registry order."""
    for handler in (EDGE_HANDLERS if handlers is None else handlers):
        if not handler.applies_to(cik, form, section_type):
            continue
        replacement = handler.handler(result, cik, form, section_type, ctx)
        if replacement is not None:
            result = replacement
            if fired is not None:
                fired[handler.name] = fired.get(handler.name, 0) + 1
    return result


def dead_edge_handlers(fired: dict) -> list[str]:
    """Registered handlers that fired zero times this run (F2's
    override-file discipline: a DEAD override is reported, not left to rot)."""
    return [h.name for h in EDGE_HANDLERS if not fired.get(h.name)]


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------


SEGMENTS = ("earnings", "10-K", "10-Q")

# §10.2: measured segmentation. Each shard is ~5-8 minutes of work, which
# satisfies HANDOFF §4's "checkpoint ~= 10 minutes". 8 + 10 + 16 = 34 shards.
DEFAULT_SHARD_SIZE: dict[str, int] = {"earnings": 1500, "10-K": 250, "10-Q": 500}

# E1's predicate, unchanged.
_TARGET_PREDICATE = (
    "(f.form IN ('10-K','10-Q') OR (f.form = '8-K' AND f.has_earnings_item = 1 "
    "AND f.earnings_doc_section_type IS NOT NULL))"
)
_SEGMENT_PREDICATE = {
    "earnings": "f.form = '8-K'",
    "10-K": "f.form = '10-K'",
    "10-Q": "f.form = '10-Q'",
    "all": "1=1",
}


def open_readonly(db_path) -> sqlite3.Connection:
    """The metadata DB is an INPUT to F3 and is never written by it."""
    return sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)


def load_target_filings(conn: sqlite3.Connection, segment: str = "all") -> pd.DataFrame:
    """Target filings for one segment, in the deterministic shard order.

    CIK-keyed (R6): `filings.ticker` is NULL for all 45,545 rows of the E2
    DB and `companies.ticker` is NULL for all 244, so a `ticker` column
    would be entirely NULL. `company_name`/`sector`/`stratum` are joined
    here, once, because the per-filer rollup and both QA sampling frames
    need them and joining at three downstream sites is more fragile.

    ORDER BY (form, accession_number) is the shard plan's determinism (C9).
    """
    query = f"""
        SELECT f.accession_number, f.cik, f.form, f.filing_date, f.report_date,
               f.primary_document, f.earnings_doc_filename,
               f.earnings_doc_relative_path, f.earnings_doc_section_type,
               f.earnings_doc_selection_confidence,
               c.company_name, c.sector, c.stratum
        FROM filings f JOIN companies c ON c.cik = f.cik
        WHERE {_TARGET_PREDICATE} AND {_SEGMENT_PREDICATE[segment]}
        ORDER BY f.form, f.accession_number
    """
    return pd.read_sql_query(query, conn)


def load_quarter_cells(conn: sqlite3.Connection) -> dict[tuple[int, str], int]:
    """(cik, filing-date quarter) -> number of earnings selections in it.

    Computed over the WHOLE earnings population every run, never over a
    shard's own slice -- otherwise a shard boundary would silently change a
    row's gate level. Reproduces H4's census exactly: 1,519 of 10,567
    selections (14.37%) sit in a multi-filing cell.
    """
    rows = conn.execute(
        "SELECT cik, filing_date FROM filings WHERE form = '8-K' "
        "AND has_earnings_item = 1 AND earnings_doc_section_type IS NOT NULL"
    ).fetchall()
    cells: dict[tuple[int, str], int] = {}
    for cik, filing_date in rows:
        key = (int(cik), filing_quarter(filing_date))
        cells[key] = cells.get(key, 0) + 1
    return cells


def plan_shards(filings: pd.DataFrame, shard_size: int) -> list[pd.DataFrame]:
    """Contiguous slices of the already-sorted frame. A pure function of
    `(form, accession_number)` order and `shard_size` -- so re-running the
    identical command reproduces the identical shard boundaries (C9)."""
    if shard_size <= 0:
        raise ValueError("shard_size must be positive")
    return [filings.iloc[i:i + shard_size] for i in range(0, len(filings), shard_size)]


# ---------------------------------------------------------------------------
# F3: one filing -> its attempts
# ---------------------------------------------------------------------------

# C3. `ticker` is deliberately ABSENT (R6): it is NULL for all 45,545 rows of
# the E2 `filings` table and all 244 rows of `companies`, so an E1-shaped
# `ticker` column would be entirely null and every downstream join on it would
# silently produce nothing.
#
# F4 COUPLING, named here so it is not discovered by crash (C3). `chunk.py`
# reads `row["ticker"]` at line 101 (`extract_prose_paragraphs`) and writes
# `home_ticker` (188), `source_tickers` (193) and `occurrence_tickers` (226);
# its home tie-break sorts on `o.ticker` (133, 177). F4 must switch those to
# `cik`. One line each, and it is F4's edit -- F3 does not touch `chunk.py`
# beyond importing `MIN_PROSE_WORDS`.
OUTPUT_COLUMNS = [
    "cik", "company_name", "sector", "stratum", "accession_number", "form",
    "filing_date", "report_date", "section_type", "text", "word_count",
    "char_count", "n_prose_paragraphs", "prose_word_share", "extraction_method",
    "extraction_confidence", "extraction_status", "flags", "source_document",
    "below_length_floor", "population_gate", "quarter_cell_size",
    "results_signature_present", "item202_prefix_chars", "item202_block_words",
    "supplemental_tail_share", "stub_language_present",
    "ctrl_ratio", "eng_word_share",  # P5 / N1
    "extractor_version", "run_id",
]

# §7.2. One row per ATTEMPT -- 30,475 of them, including every failure.
AUDIT_COLUMNS = [
    "cik", "company_name", "sector", "stratum", "accession_number", "form",
    "filing_date", "section_type", "extraction_status", "reason_code", "flags",
    "extraction_method", "extraction_confidence", "word_count", "prose_word_share",
    "ctrl_ratio", "eng_word_share",  # P5 / N1
    "source_document", "note",
]

_NULLABLE_INT_COLUMNS = ("quarter_cell_size", "item202_prefix_chars", "item202_block_words")
_NULLABLE_BOOL_COLUMNS = ("results_signature_present",)
_NULLABLE_FLOAT_COLUMNS = ("supplemental_tail_share", "ctrl_ratio", "eng_word_share")
# Declared nullable-string rather than left as object, so a shard in which a
# column happens to be entirely null (e.g. `report_date` on an earnings-only
# shard) still concatenates to the same dtype as every other shard.
_NULLABLE_STR_COLUMNS = ("report_date", "population_gate", "note", "stratum",
                          "sector", "company_name", "source_document")


def earnings_relative_path(f) -> str:
    """The stored path, or the standard one for the `8K_BODY` synthetic
    fallback branch of `select_earnings_document()` (no `filing_documents`
    row exists for those)."""
    stored = f["earnings_doc_relative_path"]
    if stored:
        return stored
    return (f"/Archives/edgar/data/{int(f['cik'])}/"
            f"{f['accession_number'].replace('-', '')}/{f['earnings_doc_filename']}")


def extract_filing(read, f, quarter_cells: dict, fired: dict | None = None
                   ) -> list[tuple[str, ExtractionResult, str]]:
    """Every attempt for one filing: [(section_type, result, source_document)].

    A cache miss or a decode/parse exception becomes a FAIL row with a named
    reason (R9) -- never a fetch, never a dropped row, never a print.
    """
    form = f["form"]
    cik = int(f["cik"])

    if form in ("10-K", "10-Q"):
        source = f["primary_document"]
        try:
            # Edge handlers for periodic sections run INSIDE
            # `_locate_one_section` (P5 / N6): a handler that has to re-locate
            # needs the document, which is out of scope by the time control
            # returns here. `fired` is threaded down so the manifest's
            # fired-count / DEAD-handler discipline is unchanged.
            results = extract_periodic_sections(
                read, cik, f["accession_number"], source, form, fired=fired,
            )
        except CacheMiss as exc:
            results = {s: failed_result(form, s, "cache_miss", note=str(exc))
                       for s in PERIODIC_SECTIONS}
        except Exception as exc:  # noqa: BLE001
            results = {s: failed_result(form, s, "document_read_error",
                                        note=f"{type(exc).__name__}: {exc}")
                       for s in PERIODIC_SECTIONS}
        return [(s, results[s], source) for s in PERIODIC_SECTIONS]

    section_type = f["earnings_doc_section_type"]
    source = f["earnings_doc_filename"]
    cell = quarter_cells.get((cik, filing_quarter(f["filing_date"])), 1)
    try:
        result = extract_earnings_document(
            read, earnings_relative_path(f), section_type,
            {"quarter_cell_size": cell},
        )
    except CacheMiss as exc:
        result = failed_result("8-K", section_type, "cache_miss", note=str(exc))
        result.quarter_cell_size = cell
    except Exception as exc:  # noqa: BLE001
        result = failed_result("8-K", section_type, "document_read_error",
                               note=f"{type(exc).__name__}: {exc}")
        result.quarter_cell_size = cell
    return [(section_type, apply_edge_handlers(result, cik, "8-K", section_type, fired=fired), source)]


def build_rows(f, section_type: str, result: ExtractionResult, source: str, run_id: str
               ) -> tuple[dict | None, dict]:
    """(corpus row or None if the attempt failed, audit row -- always)."""
    words = len(result.text.split())
    n_prose, prose_share = prose_stats(result.text)
    common = {
        "cik": int(f["cik"]), "company_name": f["company_name"], "sector": f["sector"],
        "stratum": f["stratum"], "accession_number": f["accession_number"],
        "form": f["form"],
        # HANDOFF §7 point-in-time discipline: both dates are carried through
        # UNCHANGED from the `filings` table. Nothing downstream may sort on
        # report_date.
        "filing_date": f["filing_date"],
        "section_type": section_type,
        "extraction_method": result.method,
        "extraction_confidence": result.confidence,
        "extraction_status": result.status,
        "flags": list(result.flags),
        "source_document": source,
        "word_count": words,
        "prose_word_share": prose_share,
        "ctrl_ratio": result.ctrl_ratio,
        "eng_word_share": result.eng_word_share,
    }
    audit = {k: common[k] for k in AUDIT_COLUMNS if k in common}
    audit["reason_code"] = result.reason_code
    audit["note"] = result.note
    if not result.located:
        return None, audit
    row = dict(common)
    row.pop("prose_word_share", None)
    row.update({
        "report_date": f["report_date"],
        "text": result.text,
        "char_count": len(result.text),
        "n_prose_paragraphs": n_prose,
        "prose_word_share": prose_share,
        "below_length_floor": "below_length_floor" in result.flags,
        "population_gate": result.population_gate,
        "quarter_cell_size": result.quarter_cell_size,
        "results_signature_present": result.results_signature_present,
        "item202_prefix_chars": result.item202_prefix_chars,
        "item202_block_words": result.item202_block_words,
        "supplemental_tail_share": result.supplemental_tail_share,
        "stub_language_present": result.stub_language_present,
        "extractor_version": EXTRACTOR_VERSION,
        "run_id": run_id,
    })
    return {k: row[k] for k in OUTPUT_COLUMNS}, audit


def _frame(rows: list[dict], columns: list[str]) -> pd.DataFrame:
    out = pd.DataFrame(rows, columns=columns)
    for col in _NULLABLE_INT_COLUMNS:
        if col in out.columns:
            out[col] = out[col].astype("Int64")
    for col in _NULLABLE_BOOL_COLUMNS:
        if col in out.columns:
            out[col] = out[col].astype("boolean")
    for col in _NULLABLE_FLOAT_COLUMNS:
        if col in out.columns:
            out[col] = out[col].astype("Float64")
    for col in _NULLABLE_STR_COLUMNS:
        if col in out.columns:
            out[col] = out[col].astype("string")
    return out


# ---------------------------------------------------------------------------
# F3: resumable sharded run (C9) + manifest (C10)
# ---------------------------------------------------------------------------


def _atomic_write_parquet(df: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def _atomic_write_text(text: str, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _sha256(path: Path) -> str | None:
    if not Path(path).exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _git_rev() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True,
            text=True, timeout=10, check=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def shard_paths(out_dir: Path, segment: str, index: int) -> tuple[Path, Path, Path]:
    shards = Path(out_dir) / "shards"
    stem = f"{segment}_{index:04d}"
    return (shards / f"{stem}.parquet", shards / f"{stem}.audit.parquet",
            shards / f"{stem}.done")


def _done_marker_matches(done_path: Path, limit: int | None) -> tuple[bool, dict]:
    """A `.done` marker is honoured only if it records the SAME `--limit` as
    this invocation. That is what stops a `--limit 5` debugging run from
    leaving a truncated shard that a later full run would skip."""
    if not done_path.exists():
        return False, {}
    try:
        marker = json.loads(done_path.read_text())
    except Exception:  # noqa: BLE001
        return False, {}
    return marker.get("limit") == limit, marker


def run_shard(read, filings: pd.DataFrame, quarter_cells: dict, out_dir: Path,
              segment: str, index: int, run_id: str, limit: int | None = None,
              fired: dict | None = None, quiet: bool = False) -> dict:
    """Extract one shard and write it atomically, then its `.done` marker.

    The blast radius of a SIGTERM is therefore exactly one shard: both
    output files land via `os.replace` before the marker exists at all.
    """
    sections_path, audit_path, done_path = shard_paths(out_dir, segment, index)
    sections_path.parent.mkdir(parents=True, exist_ok=True)

    started = time.time()
    section_rows: list[dict] = []
    audit_rows: list[dict] = []
    for _, f in filings.iterrows():
        for section_type, result, source in extract_filing(read, f, quarter_cells, fired=fired):
            row, audit = build_rows(f, section_type, result, source, run_id)
            audit_rows.append(audit)
            if row is not None:
                section_rows.append(row)

    _atomic_write_parquet(_frame(section_rows, OUTPUT_COLUMNS), sections_path)
    _atomic_write_parquet(_frame(audit_rows, AUDIT_COLUMNS), audit_path)

    audit_frame = pd.DataFrame(audit_rows, columns=AUDIT_COLUMNS)
    status_counts = (audit_frame["extraction_status"].value_counts().to_dict()
                     if not audit_frame.empty else {})
    cache_misses = int((audit_frame["reason_code"] == "cache_miss").sum()) if not audit_frame.empty else 0
    stats = {
        "segment": segment, "shard": index, "limit": limit, "run_id": run_id,
        "filings": int(len(filings)), "attempts": len(audit_rows),
        "sections": len(section_rows), "status_counts": status_counts,
        "cache_miss": cache_misses, "elapsed_s": round(time.time() - started, 1),
        "extractor_sha256": _sha256(Path(__file__)),
    }
    _atomic_write_text(json.dumps(stats, indent=1, default=str), done_path)
    if not quiet:
        print(f"  shard {segment}_{index:04d}: {stats['filings']} filings -> "
              f"{stats['attempts']} attempts / {stats['sections']} sections  "
              f"{status_counts}  cache_miss={cache_misses}  "
              f"{stats['elapsed_s']}s  network_gets=0")
    return stats


def merge_shards(out_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Concatenate every completed shard and check the audit arithmetic.

    Returns (sections, audit, warnings). Refuses to return a corpus with a
    duplicate (accession_number, section_type).
    """
    shards = Path(out_dir) / "shards"
    done = sorted(shards.glob("*.done"))
    section_frames, audit_frames = [], []
    warnings_out: list[str] = []
    for done_path in done:
        stem = done_path.name[:-len(".done")]
        sections_path = shards / f"{stem}.parquet"
        audit_path = shards / f"{stem}.audit.parquet"
        if not sections_path.exists() or not audit_path.exists():
            warnings_out.append(f"{stem}: .done present but an output file is missing")
            continue
        section_frames.append(pd.read_parquet(sections_path))
        audit_frames.append(pd.read_parquet(audit_path))

    # Drop empty shard frames before concat: an all-empty frame contributes
    # no rows but does drag every column to `object` dtype, which would break
    # the schema pin (T17) on a run where one shard happened to locate
    # nothing.
    section_frames = [f for f in section_frames if not f.empty]
    audit_frames = [f for f in audit_frames if not f.empty]
    sections = (pd.concat(section_frames, ignore_index=True) if section_frames
                else _frame([], OUTPUT_COLUMNS))
    audit = (pd.concat(audit_frames, ignore_index=True) if audit_frames
             else _frame([], AUDIT_COLUMNS))

    dupes = sections.duplicated(subset=["accession_number", "section_type"]).sum()
    if dupes:
        raise ValueError(f"merge: {dupes} duplicate (accession_number, section_type) rows")
    counts = audit["extraction_status"].value_counts().to_dict() if not audit.empty else {}
    total = sum(counts.get(s, 0) for s in (STATUS_OK, STATUS_FLAGGED,
                                            STATUS_ITEM_ABSENT_FROM_TOC, STATUS_FAIL))
    if total != len(audit):
        raise ValueError(f"merge: attempts {len(audit)} != OK+FLAGGED+ITEM_ABSENT_FROM_TOC+FAIL {total}")
    expected_sections = counts.get(STATUS_OK, 0) + counts.get(STATUS_FLAGGED, 0)
    if len(sections) != expected_sections:
        raise ValueError(f"merge: {len(sections)} corpus rows != OK+FLAGGED {expected_sections}")
    return sections, audit, warnings_out


# ---------------------------------------------------------------------------
# F3: audit artifacts (§7.3 - §7.5)
# ---------------------------------------------------------------------------

# The candidate ladder published beside the measured distribution, so a
# proposed floor move is always argued from a table that already exists
# (§8.1(2)(a)) rather than from a number invented to fit a failure.
FLOOR_CANDIDATE_LADDER = (15, 50, 100, 250, 400, 500, 750, 1000, 1500, 2000, 3000)


def per_filer_rollup(audit: pd.DataFrame) -> pd.DataFrame:
    """The mandatory triage instrument (§7.3): one row per
    (cik, form, section_type), sorted by fail_rate desc.

    Nobody reads ~1,600 failure rows; 244 filers sorted by failure rate is a
    morning. Every FAIL, FLAGGED and below-floor row is triaged from here.
    """
    if audit.empty:
        return pd.DataFrame(columns=[
            "cik", "company_name", "sector", "stratum", "form", "section_type",
            "n_attempt", "n_ok", "n_flagged", "n_item_absent_from_toc", "n_fail",
            "fail_rate", "flag_rate", "n_pre2019", "fail_rate_pre2019",
            "fail_rate_2019plus", "top_reason_code", "n_low_confidence", "median_words",
        ])
    df = audit.copy()
    df["pre2019"] = df["filing_date"] < "2019-01-01"
    rows = []
    for (cik, form, section), g in df.groupby(["cik", "form", "section_type"], sort=False):
        pre, post = g[g["pre2019"]], g[~g["pre2019"]]
        non_ok = g[g["extraction_status"] != STATUS_OK]["reason_code"]
        rows.append({
            "cik": int(cik), "company_name": g["company_name"].iloc[0],
            "sector": g["sector"].iloc[0], "stratum": g["stratum"].iloc[0],
            "form": form, "section_type": section,
            "n_attempt": len(g),
            "n_ok": int((g["extraction_status"] == STATUS_OK).sum()),
            "n_flagged": int((g["extraction_status"] == STATUS_FLAGGED).sum()),
            "n_item_absent_from_toc": int((g["extraction_status"] == STATUS_ITEM_ABSENT_FROM_TOC).sum()),
            "n_fail": int((g["extraction_status"] == STATUS_FAIL).sum()),
            "fail_rate": round((g["extraction_status"] == STATUS_FAIL).mean(), 4),
            "flag_rate": round((g["extraction_status"] == STATUS_FLAGGED).mean(), 4),
            "n_pre2019": int(len(pre)),
            "fail_rate_pre2019": (round((pre["extraction_status"] == STATUS_FAIL).mean(), 4)
                                   if len(pre) else None),
            "fail_rate_2019plus": (round((post["extraction_status"] == STATUS_FAIL).mean(), 4)
                                    if len(post) else None),
            "top_reason_code": (non_ok.value_counts().index[0] if len(non_ok) else "ok"),
            "n_low_confidence": int((g["extraction_confidence"] == "low").sum()),
            "median_words": float(g["word_count"].median()),
        })
    return pd.DataFrame(rows).sort_values(
        ["fail_rate", "n_attempt"], ascending=[False, False]
    ).reset_index(drop=True)


def population_gate_table(sections: pd.DataFrame) -> pd.DataFrame:
    """§7.4: every gate-flagged selection, with empty verdict columns for
    P3's triage to fill -- the H4 ledger pattern."""
    columns = ["cik", "company_name", "accession_number", "filing_date", "quarter",
               "quarter_cell_size", "section_type", "results_signature_present",
               "gate_level", "words", "prose_word_share", "verdict", "verdict_note"]
    if sections.empty or "population_gate" not in sections.columns:
        return pd.DataFrame(columns=columns)
    flagged = sections[sections["population_gate"].isin(["WARN_MULTI", "WARN_MULTI_NOSIG"])]
    if flagged.empty:
        return pd.DataFrame(columns=columns)
    out = pd.DataFrame({
        "cik": flagged["cik"], "company_name": flagged["company_name"],
        "accession_number": flagged["accession_number"],
        "filing_date": flagged["filing_date"],
        "quarter": [filing_quarter(d) for d in flagged["filing_date"]],
        "quarter_cell_size": flagged["quarter_cell_size"],
        "section_type": flagged["section_type"],
        "results_signature_present": flagged["results_signature_present"],
        "gate_level": flagged["population_gate"],
        "words": flagged["word_count"],
        "prose_word_share": flagged["prose_word_share"],
        "verdict": "", "verdict_note": "",
    })
    return out.sort_values(["gate_level", "cik", "filing_date"]).reset_index(drop=True)


def length_distribution(sections: pd.DataFrame) -> pd.DataFrame:
    """§7.5: the evidence table any floor recalibration must argue from,
    published BEFORE any floor moves. Per (form, section_type) x slice."""
    columns = (["form", "section_type", "slice", "n", "min", "p1", "p5", "p10", "p25",
                "p50", "p75", "p90", "p99", "max", "current_floor",
                "n_below_current_floor"]
               + [f"n_below_{v}" for v in FLOOR_CANDIDATE_LADDER])
    if sections.empty:
        return pd.DataFrame(columns=columns)
    rows = []
    for (form, section), g in sections.groupby(["form", "section_type"], sort=True):
        slices = {"all": g,
                  "era<=2018": g[g["filing_date"] < "2019-01-01"],
                  "era>=2019": g[g["filing_date"] >= "2019-01-01"]}
        for stratum, sg in g.groupby("stratum", dropna=False, sort=True):
            slices[f"stratum={stratum}"] = sg
        floor = MIN_SECTION_WORDS.get((form, section), 0)
        for name, sl in slices.items():
            if sl.empty:
                continue
            w = sl["word_count"]
            row = {"form": form, "section_type": section, "slice": name, "n": len(sl),
                   "min": int(w.min()), "max": int(w.max()), "current_floor": floor,
                   "n_below_current_floor": int((w < floor).sum())}
            for q in (1, 5, 10, 25, 50, 75, 90, 99):
                row[f"p{q}"] = round(float(w.quantile(q / 100)), 1)
            for v in FLOOR_CANDIDATE_LADDER:
                row[f"n_below_{v}"] = int((w < v).sum())
            rows.append(row)
    return pd.DataFrame(rows, columns=columns)


def write_manifest(out_dir: Path, entry: dict) -> Path:
    """C10. Appends to a `runs` list rather than overwriting, so a resumed
    run never erases the record of the run it is resuming."""
    path = Path(out_dir) / "run_manifest.json"
    manifest = {"runs": []}
    if path.exists():
        try:
            manifest = json.loads(path.read_text())
        except Exception:  # noqa: BLE001
            manifest = {"runs": []}
    manifest.setdefault("runs", []).append(entry)
    _atomic_write_text(json.dumps(manifest, indent=1, default=str), path)
    return path


def assert_not_e1_path(*paths) -> None:
    """E1's artifacts are frozen (§1.4). Refuse them by NAME, the same guard
    `ingest_prices.main` carries."""
    for p in paths:
        if p is None:
            continue
        resolved = Path(p).resolve()
        if resolved in E1_FROZEN_PATHS:
            raise SystemExit(
                f"[FATAL] {resolved} is an E1 frozen artifact and is never read as F3's "
                f"input or written as F3's output. E2 paths: --db {DB_PATH} "
                f"--out-dir {OUT_DIR} --out-parquet {PARQUET_PATH}."
            )



def run(
    db_path=DB_PATH,
    out_dir=OUT_DIR,
    out_parquet=PARQUET_PATH,
    segment: str = "all",
    shard_size: int | None = None,
    shard: int | None = None,
    limit: int | None = None,
    merge: bool = False,
    cache_dir=RAW_DOCS,
    read=None,
    quiet: bool = False,
) -> dict:
    """Extract one segment (or all three) into resumable shards, then
    optionally merge every completed shard into the F3 artifacts.

    Resume = re-run the IDENTICAL command. A shard whose `.done` marker
    exists (and records the same `--limit`) is skipped, so a re-run with all
    shards present does nothing but re-merge. Idempotent by construction.

    ZERO network GETs, structurally (R5): `read` defaults to
    `read_cached_document`, `EdgarClient` is not imported on this path, and
    a cache miss becomes a FAIL row rather than a fetch.
    """
    db_path, out_dir, out_parquet = Path(db_path), Path(out_dir), Path(out_parquet)
    assert_not_e1_path(db_path, out_parquet, out_dir / "extraction_audit.parquet")
    if segment not in _SEGMENT_PREDICATE:
        raise SystemExit(f"[FATAL] --segment must be one of {sorted(_SEGMENT_PREDICATE)}")
    if merge and limit is not None:
        raise SystemExit("[FATAL] --merge with --limit would publish a truncated corpus.")

    if read is None:
        read = lambda rel: read_cached_document(rel, cache_dir=cache_dir)  # noqa: E731

    run_id = datetime.now(timezone.utc).strftime("f3-%Y%m%dT%H%M%SZ")
    started = datetime.now(timezone.utc)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "shards").mkdir(parents=True, exist_ok=True)

    conn = open_readonly(db_path)
    quarter_cells = load_quarter_cells(conn)
    segments = list(SEGMENTS) if segment == "all" else [segment]
    fired: dict[str, int] = {}
    shard_stats: list[dict] = []

    for seg in segments:
        filings = load_target_filings(conn, seg)
        if limit is not None:
            filings = filings.head(limit)
        size = shard_size or DEFAULT_SHARD_SIZE[seg]
        planned = plan_shards(filings, size)
        if not quiet:
            print(f"[{seg}] {len(filings)} filings -> {len(planned)} shards of {size}")
        for index, chunk_df in enumerate(planned):
            if shard is not None and index != shard:
                continue
            _, _, done_path = shard_paths(out_dir, seg, index)
            ok, marker = _done_marker_matches(done_path, limit)
            if ok:
                if marker.get("extractor_sha256") not in (None, _sha256(Path(__file__))):
                    print(f"  WARNING: shard {seg}_{index:04d} was produced by a DIFFERENT "
                          f"extract.py (sha {marker.get('extractor_sha256')[:12]}...); "
                          f"delete its .done to recompute.")
                if not quiet:
                    print(f"  shard {seg}_{index:04d}: done, skipped")
                shard_stats.append({**marker, "skipped": True})
                continue
            shard_stats.append(run_shard(
                read, chunk_df, quarter_cells, out_dir, seg, index, run_id,
                limit=limit, fired=fired, quiet=quiet,
            ))
    expected_shards = {
        seg: len(plan_shards(load_target_filings(conn, seg),
                              shard_size or DEFAULT_SHARD_SIZE[seg]))
        for seg in SEGMENTS
    }
    conn.close()

    cache_misses = sum(int(s.get("cache_miss", 0) or 0) for s in shard_stats)
    summary: dict = {
        "run_id": run_id,
        "started_utc": started.isoformat(),
        "ended_utc": datetime.now(timezone.utc).isoformat(),
        "argv": sys.argv[1:],
        "segments": segments,
        "shard_size": shard_size,
        "shard": shard,
        "limit": limit,
        "merge": merge,
        "git_rev": _git_rev(),
        "extract_py_sha256": _sha256(Path(__file__)),
        "db_sha256": _sha256(db_path),
        "db_path": str(db_path),
        "out_parquet": str(out_parquet),
        "network_gets": 0,
        "cache_miss": cache_misses,
        "extractor_version": EXTRACTOR_VERSION,
        "constants": {
            "MIN_SECTION_CHARS": MIN_SECTION_CHARS,
            "MIN_SECTION_WORDS": {f"{k[0]}|{k[1]}": v for k, v in MIN_SECTION_WORDS.items()},
            "MDA_STUB_WORD_CEILING": MDA_STUB_WORD_CEILING,
            "EARNINGS_THIN_DOCUMENT_CHARS": EARNINGS_THIN_DOCUMENT_CHARS,
            "ITEM202_THIN_BLOCK_WORDS": ITEM202_THIN_BLOCK_WORDS,
            "ITEM202_PREFIX_LARGE_CHARS": ITEM202_PREFIX_LARGE_CHARS,
            "SUPPLEMENTAL_DILUTED_SHARE": SUPPLEMENTAL_DILUTED_SHARE,
            "SUPPLEMENTAL_MARKERS": list(SUPPLEMENTAL_MARKERS),
            "RESULTS_SIGNATURE_MARKERS": list(RESULTS_SIGNATURE_MARKERS),
            "MIN_PROSE_WORDS": chunk_module.MIN_PROSE_WORDS,
        },
        "shards": shard_stats,
        "edge_handlers_fired": dict(fired),
        "edge_handlers_dead": dead_edge_handlers(fired),
    }

    if cache_misses:
        # R5: a nonzero count is a run-level FATAL, because F2 verified all
        # 20,521 target documents present. It is reported, never repaired by
        # a fetch.
        print(f"[FATAL] {cache_misses} cache_miss FAIL row(s) -- F3 never fetches. "
              f"See extraction_failures.csv.")

    if merge:
        sections, audit, merge_warnings = merge_shards(out_dir)
        expected = expected_shards
        found = {seg: len(list((out_dir / "shards").glob(f"{seg}_*.done"))) for seg in SEGMENTS}
        complete = all(found[s] == expected[s] for s in SEGMENTS)
        if not complete:
            print(f"[WARNING] merge is PARTIAL: shards done/expected = "
                  f"{ {s: (found[s], expected[s]) for s in SEGMENTS} }")
        for w in merge_warnings:
            print(f"[WARNING] {w}")

        _atomic_write_parquet(sections, out_parquet)
        _atomic_write_parquet(audit, out_dir / "extraction_audit.parquet")
        failures = audit[audit["extraction_status"].isin([STATUS_FAIL, STATUS_FLAGGED])].copy()
        failures["flags"] = failures["flags"].apply(
            lambda v: "|".join(v) if isinstance(v, (list, tuple, pd.Series)) or hasattr(v, "tolist") else v
        )
        failures.to_csv(out_dir / "extraction_failures.csv", index=False)
        per_filer_rollup(audit).to_csv(out_dir / "per_filer_rollup.csv", index=False)
        population_gate_table(sections).to_csv(out_dir / "population_gate.csv", index=False)
        length_distribution(sections).to_csv(out_dir / "length_distribution.csv", index=False)

        counts = audit["extraction_status"].value_counts().to_dict() if not audit.empty else {}
        summary["merge"] = {
            "complete": complete, "shards_found": found, "shards_expected": expected,
            "attempts": int(len(audit)), "sections": int(len(sections)),
            "status_counts": counts, "warnings": merge_warnings,
        }
        if not quiet:
            print(f"\nMerged: {len(audit)} attempts -> {len(sections)} sections  {counts}")
            print(f"Wrote {out_parquet}")
            print(f"Wrote {out_dir/'extraction_audit.parquet'}, extraction_failures.csv, "
                  f"per_filer_rollup.csv, population_gate.csv, length_distribution.csv")

    write_manifest(out_dir, summary)
    if not quiet:
        print(f"Total EDGAR network GETs this run: 0 (cache-only by construction)")
        if EDGE_HANDLERS:
            print(f"Edge handlers fired: {fired or '{}'}; DEAD: {dead_edge_handlers(fired)}")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="F3 extraction over the E2 corpus (cache-only, resumable, 0 GETs)."
    )
    parser.add_argument("--db", default=str(DB_PATH), help="E2 metadata DB (read-only).")
    parser.add_argument("--out-dir", default=str(OUT_DIR), help="Shards + audit artifacts.")
    parser.add_argument("--out-parquet", default=str(PARQUET_PATH), help="The section corpus.")
    parser.add_argument("--segment", default="all", choices=sorted(_SEGMENT_PREDICATE))
    parser.add_argument("--shard-size", type=int, default=None,
                        help="Override the per-segment default (earnings 1500 / 10-K 250 / 10-Q 500).")
    parser.add_argument("--shard", type=int, default=None,
                        help="Run only this shard index (the N-worker knob; 2 workers max).")
    parser.add_argument("--limit", type=int, default=None,
                        help="Debugging only: first N filings per segment. Recorded in the "
                             "manifest and in every .done marker so a truncated run can "
                             "never be mistaken for a full one.")
    parser.add_argument("--merge", action="store_true",
                        help="Merge every completed shard into the F3 artifacts.")
    parser.add_argument("--cache-dir", default=str(RAW_DOCS))
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        run(db_path=args.db, out_dir=args.out_dir, out_parquet=args.out_parquet,
            segment=args.segment, shard_size=args.shard_size, shard=args.shard,
            limit=args.limit, merge=args.merge, cache_dir=args.cache_dir,
            quiet=args.quiet)
    except SystemExit as exc:
        if exc.code in (0, None):
            raise
        print(exc.code if isinstance(exc.code, str) else "[FATAL]")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
