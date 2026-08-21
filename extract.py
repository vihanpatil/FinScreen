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
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup

from edgar_client import EdgarClient

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
DB_PATH = REPO_ROOT / "data" / "filings_metadata.db"
PARQUET_PATH = REPO_ROOT / "data" / "filings.parquet"

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
MIN_SECTION_WORDS: dict[tuple[str, str], int] = {
    ("10-K", "MDA"): 1500,
    ("10-K", "RISK_FACTORS"): 2000,
    ("10-Q", "MDA"): 1000,
    ("10-Q", "RISK_FACTORS"): 15,
    ("8-K", "8K_BODY"): 500,
    ("8-K", "EX99_PRESS_RELEASE"): 50,
}

# ---------------------------------------------------------------------------
# TOC-anchor-based section location
# ---------------------------------------------------------------------------

_ITEM_LABEL_PREFIX_RE = re.compile(r"^item\s*([0-9]{1,2}[a-c]?)\.?\b", re.IGNORECASE)
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
                item_no=m.group(1).upper(), anchor_id=anchor_id, order=idx,
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
    start_idx = None
    for i, entry in enumerate(toc_entries):
        if entry.item_no != target_item_no:
            continue
        if required_keywords:
            row_text_nospace = re.sub(r"\s+", "", entry.row_text)
            if not any(re.sub(r"\s+", "", kw) in row_text_nospace for kw in required_keywords):
                continue
        start_idx = i
        break
    if start_idx is None:
        return None

    start_entry = toc_entries[start_idx]
    start_offset = find_anchor_offset(html_text, start_entry.anchor_id)
    if start_offset is None:
        return None
    start_offset = _end_of_enclosing_tag(html_text, start_offset)

    end_offset = len(html_text)
    for entry in toc_entries[start_idx + 1:]:
        if entry.item_no != target_item_no:
            candidate = find_anchor_offset(html_text, entry.anchor_id, after=start_offset)
            if candidate is not None and candidate > start_offset:
                end_offset = _start_of_enclosing_tag(html_text, candidate)
            break

    if end_offset <= start_offset:
        return None
    return start_offset, end_offset


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


def locate_item_section_by_heading_regex(
    text: str, form: str, section: str,
) -> tuple[int, int] | None:
    """Fallback for documents without a usable anchor-linked TOC. Takes the
    LAST start-pattern match in the document (real content sections appear
    after the TOC, which is always near the top) with a resulting span to
    the nearest subsequent end-pattern match of at least MIN_SECTION_CHARS.
    """
    start_pat, end_pats = FALLBACK_SECTIONS[(form, section)]
    starts = list(start_pat.finditer(text))
    if not starts:
        return None
    for sm in reversed(starts):  # last match first
        s_end = sm.end()
        end_offset = len(text)
        for ep in end_pats:
            em = ep.search(text, s_end)
            if em and em.start() < end_offset:
                end_offset = em.start()
        if end_offset - s_end >= MIN_SECTION_CHARS:
            return sm.start(), end_offset
    return None


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

MDA_STUB_WORD_CEILING = 1500  # below this + reference-language present, treat
                                # an Item-7 extraction as a candidate stub
                                # (real stubs found were 36-53 words; the
                                # smallest genuine 10-K MD&A in this universe
                                # is 2,441 words -- huge margin either side)

STUB_REFERENCE_LANGUAGE_RE = re.compile(
    r"incorporated by reference|reference is made to|is presented in|"
    r"appears on page|the index to",
    re.IGNORECASE,
)

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


def resolve_incorporated_by_reference_mda(html_text: str, stub_start: int, stub_end: int) -> str | None:
    """Try both strategies in order. `html_text` is the full document's raw
    (SGML-wrapper-stripped) HTML; `stub_start`/`stub_end` are the raw-HTML
    offsets of the Item 7 anchor-based match that turned out to be a stub.
    Returns the real MD&A text if found, else None.
    """
    text = resolve_mda_via_anchor_hop(html_text, stub_start, stub_end)
    if text is not None:
        return text
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
    text: str
    method: str  # 'anchor' | 'heading_regex' | 'whole_document' |
                  # 'incorporated_by_reference_resolved' |
                  # 'incorporated_by_reference_unresolved'
    confidence: str  # 'high' | 'medium' | 'low'


def extract_item_section(
    client: EdgarClient, cik: int, accession_number: str, primary_document: str,
    form: str, section: str,
) -> ExtractionResult | None:
    relative_path = f"/Archives/edgar/data/{cik}/{accession_number.replace('-', '')}/{primary_document}"
    html_text = strip_sgml_document_wrapper(client.get_archive_document(relative_path))

    target_item_no = "7" if section == "MDA" and form == "10-K" else (
        "2" if section == "MDA" else "1A"
    )
    # Required so a same-numbered non-Item TOC entry (confirmed real case:
    # UNH's Notes-to-financial-statements index also uses bare "N. Title"
    # rows) can't be silently mistaken for the real Item heading -- see
    # locate_item_section_by_anchor()'s docstring.
    required_keywords = ("discussion and analysis",) if section == "MDA" else ("risk factor",)

    soup = BeautifulSoup(html_text, _PARSER)
    toc_entries = find_toc_item_anchors(soup)
    span = locate_item_section_by_anchor(html_text, toc_entries, target_item_no, required_keywords)
    if span is not None:
        start, end = span
        text = html_fragment_to_text(html_text[start:end])
        if len(text) >= MIN_SECTION_CHARS:
            # Fix 3: a 10-K MD&A extraction that's short AND phrased as a
            # cross-reference is a candidate "incorporated by reference
            # elsewhere in this document" stub (confirmed real case: CVX,
            # XOM, JPM), not a legitimate short MD&A -- never trust this
            # combination as high-confidence at face value. See the
            # "10-K MD&A incorporated-by-reference resolver" section above.
            is_stub_candidate = (
                form == "10-K" and section == "MDA"
                and len(text.split()) < MDA_STUB_WORD_CEILING
                and STUB_REFERENCE_LANGUAGE_RE.search(text)
            )
            if is_stub_candidate:
                resolved_text = resolve_incorporated_by_reference_mda(html_text, start, end)
                if resolved_text and len(resolved_text.split()) >= MIN_SECTION_WORDS.get((form, section), 0):
                    return ExtractionResult(
                        text=resolved_text,
                        method="incorporated_by_reference_resolved",
                        confidence="medium",
                    )
                # Couldn't confidently locate the real content elsewhere in
                # the document -- keep the short stub text (it's still the
                # literal Item 7 text as filed) but mark it explicitly so it
                # can never be mistaken for a real, substantive MD&A
                # downstream. Reported by name in the run() summary below.
                return ExtractionResult(
                    text=text,
                    method="incorporated_by_reference_unresolved",
                    confidence="low",
                )
            return ExtractionResult(text=text, method="anchor", confidence="high")

    if toc_entries:
        # This document DOES have a working anchor-linked TOC, and it was
        # parsed successfully (non-empty), but simply doesn't list
        # `target_item_no` at all. Confirmed on real filings (GS, XOM,
        # ABBV, JNJ, MRK 10-Qs): some filers omit "Item 1A. Risk Factors"
        # from Part II entirely when there's nothing new to disclose,
        # rather than including a short "no material changes" paragraph.
        # Falling back to the heading regex here is actively dangerous, not
        # just lower-confidence: on XOM's 2023-10-31 10-Q, the ONLY "Item
        # 1A" text in the whole document turned out to be a compact
        # cross-reference sentence ("...Item 1A. Risk Factors of
        # ExxonMobil's 2022 Form 10-K.") immediately followed, in the same
        # paragraph, by the start of the (unrelated) Item 1 Legal
        # Proceedings text -- the regex fallback would silently merge the
        # two into a single plausible-looking but WRONG "Risk Factors"
        # section. Better to correctly report "not present" than to return
        # confidently-wrong merged content.
        return None

    # Only reached when this document has NO working anchor-linked TOC at
    # all (confirmed real cause on COP/CVX/JNJ 10-Ks, before a bare-number
    # TOC row format fix: those filers' TOC rows read "7. Management's
    # Discussion..." instead of "Item 7. Management's Discussion...").
    # Fall back to the tight-gap heading regex, working off the
    # whole-document plain text since it doesn't need to distinguish markup.
    full_text = html_fragment_to_text(html_text)
    span = locate_item_section_by_heading_regex(full_text, form, section)
    if span is not None:
        start, end = span
        text = full_text[start:end].strip()
        if len(text) >= MIN_SECTION_CHARS:
            return ExtractionResult(text=text, method="heading_regex", confidence="low")

    return None


def extract_earnings_document(client: EdgarClient, relative_path: str) -> ExtractionResult | None:
    html_text = strip_sgml_document_wrapper(client.get_archive_document(relative_path))
    text = html_fragment_to_text(html_text)
    if len(text) < MIN_SECTION_CHARS:
        return None
    return ExtractionResult(text=text, method="whole_document", confidence="high")


# ---------------------------------------------------------------------------
# Main run
# ---------------------------------------------------------------------------


def load_target_filings(conn: sqlite3.Connection) -> pd.DataFrame:
    query = """
        SELECT accession_number, cik, ticker, form, filing_date, report_date,
               primary_document, earnings_doc_filename, earnings_doc_relative_path,
               earnings_doc_section_type
        FROM filings
        WHERE form IN ('10-K', '10-Q')
           OR (form = '8-K' AND has_earnings_item = 1 AND earnings_doc_section_type IS NOT NULL)
        ORDER BY ticker, filing_date
    """
    return pd.read_sql_query(query, conn)


def run(limit: int | None = None) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    filings = load_target_filings(conn)
    conn.close()

    if limit:
        filings = filings.head(limit)

    client = EdgarClient()
    rows = []
    failures = []

    for i, f in filings.iterrows():
        accession = f["accession_number"]
        cik = int(f["cik"])
        ticker = f["ticker"]
        form = f["form"]
        filing_date = f["filing_date"]
        report_date = f["report_date"]

        if form in ("10-K", "10-Q"):
            for section in ("MDA", "RISK_FACTORS"):
                try:
                    result = extract_item_section(
                        client, cik, accession, f["primary_document"], form, section,
                    )
                except Exception as e:  # noqa: BLE001
                    print(f"  WARN: {ticker} {accession} {form} {section} extraction failed: {e}")
                    failures.append((ticker, accession, form, section, str(e)))
                    continue
                if result is None:
                    print(f"  WARN: {ticker} {accession} {form} {section} -- no section located")
                    failures.append((ticker, accession, form, section, "not located"))
                    continue
                rows.append({
                    "ticker": ticker, "cik": cik, "accession_number": accession,
                    "form": form, "filing_date": filing_date, "report_date": report_date,
                    "section_type": section, "text": result.text,
                    "extraction_method": result.method, "extraction_confidence": result.confidence,
                    "source_document": f["primary_document"],
                })
        else:  # 8-K earnings document
            section_type = f["earnings_doc_section_type"]
            relative_path = f["earnings_doc_relative_path"]
            source_document = f["earnings_doc_filename"]
            if not relative_path:
                # 8K_BODY resolutions with no filing_documents row (the
                # synthetic-fallback branch in select_earnings_document())
                # don't have a relative_path -- construct the standard one.
                relative_path = f"/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{source_document}"
            try:
                result = extract_earnings_document(client, relative_path)
            except Exception as e:  # noqa: BLE001
                print(f"  WARN: {ticker} {accession} 8-K {section_type} extraction failed: {e}")
                failures.append((ticker, accession, "8-K", section_type, str(e)))
                continue
            if result is None:
                print(f"  WARN: {ticker} {accession} 8-K {section_type} -- empty after extraction")
                failures.append((ticker, accession, "8-K", section_type, "empty"))
                continue
            rows.append({
                "ticker": ticker, "cik": cik, "accession_number": accession,
                "form": "8-K", "filing_date": filing_date, "report_date": report_date,
                "section_type": section_type, "text": result.text,
                "extraction_method": result.method, "extraction_confidence": result.confidence,
                "source_document": source_document,
            })

        if (i + 1) % 25 == 0:
            print(f"  ... {i + 1}/{len(filings)} filings processed, {client.request_count} network GETs so far")

    out = pd.DataFrame(rows)
    print(f"\nExtracted {len(out)} sections from {len(filings)} filings.")
    if not out.empty:
        print(out.groupby("section_type").size().to_string())

        # General per-(form, section_type) length-floor plausibility check
        # (Fix 3, item 4): flag, not reject -- MIN_SECTION_CHARS (30) alone
        # is far too low to catch a short-but-plausible-looking extraction
        # that isn't actually the real section content.
        out["word_count"] = out["text"].str.split().str.len()
        out["below_length_floor"] = out.apply(
            lambda r: r["word_count"] < MIN_SECTION_WORDS.get((r["form"], r["section_type"]), 0),
            axis=1,
        )
        flagged = out[out["below_length_floor"]]
        print(f"\nbelow_length_floor: {len(flagged)} row(s) flagged for review "
              f"(per-(form,section_type) word-count floors: {MIN_SECTION_WORDS}):")
        if not flagged.empty:
            print(flagged[["ticker", "accession_number", "form", "section_type",
                            "word_count", "extraction_method", "extraction_confidence"]]
                  .sort_values(["form", "section_type", "word_count"]).to_string(index=False))

        # Fix 3, item 3: report the incorporated-by-reference stub outcome
        # explicitly, by filing, rather than folding it into an aggregate.
        resolved = out[out["extraction_method"] == "incorporated_by_reference_resolved"]
        unresolved = out[out["extraction_method"] == "incorporated_by_reference_unresolved"]
        if not resolved.empty or not unresolved.empty:
            print(f"\nIncorporated-by-reference MD&A stubs handled this run: "
                  f"{len(resolved)} resolved to real content, {len(unresolved)} unresolved.")
            if not resolved.empty:
                print("  RESOLVED (real MD&A text located elsewhere in the same document):")
                for _, r in resolved.iterrows():
                    print(f"    {r['ticker']} {r['accession_number']} ({r['filing_date']}): "
                          f"{r['word_count']} words")
            if not unresolved.empty:
                print("  UNRESOLVED (kept the short stub text, confidence='low' -- "
                      "flag for manual review, do not use as MD&A downstream):")
                for _, r in unresolved.iterrows():
                    print(f"    {r['ticker']} {r['accession_number']} ({r['filing_date']}): "
                          f"{r['word_count']} words -- {r['text']!r}")

    print(f"Failures: {len(failures)}")
    for fail in failures:
        print("  ", fail)
    print(f"Total EDGAR network GETs this run: {client.request_count}")

    out.to_parquet(PARQUET_PATH, index=False)
    print(f"Wrote {PARQUET_PATH}")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N filings (debugging).")
    args = parser.parse_args()
    run(limit=args.limit)
