"""P4b: turn `census_rows.jsonl` into the 779-row verdict CSV + the report's
tables. Read-only over the census output; writes only inside
`data/f3/p4b_ea_census/`.

Derived columns:
  * `head_opens_on_item1a`  -- does the recovered/fallback text START on an
    Item 1A heading (offset < 40 chars, allowing a "Table of Contents" prefix)?
    The 13 Eversource rows fail this: their later-resolvable anchor lands on
    "PART II. OTHER INFORMATION / ITEM 1. LEGAL PROCEEDINGS".
  * `best_words` / `best_source` -- the defensible span: for R2 the anchor
    span closed with the shipped end-patterns (`rec_guarded_words`), for R3
    the shipped fallback span.
  * `band_p4`   -- P4's 0.5-2x-(form,section)-anchor-median verdict, kept for
    comparability. For (10-Q, RISK_FACTORS) the median is 97 w, so the band is
    [48.5, 194] -- reported, and argued against in the report, because this
    section's anchor distribution is strongly BIMODAL.
  * `band_bimodal` -- the recalibrated verdict against the measured modes.
  * `defensible`   -- head opens on Item 1A AND the span sits inside the
    measured corpus range AND (R2 only) the end guard closed the span.
"""
from __future__ import annotations

import os
import re
import sys

import numpy as np
import pandas as pd

ROOT = "/Users/vihanpatil/personal/projects/FinScreen"
OUT = os.path.join(ROOT, "data/f3/p4b_ea_census")

# --- measured (10-Q, RISK_FACTORS) anchor-located distribution -------------
audit = pd.read_parquet(os.path.join(ROOT, "data/f3/extraction_audit.parquet"))
anch = audit[(audit.form == "10-Q") & (audit.section_type == "RISK_FACTORS")
             & (audit.extraction_method == "anchor")].word_count.astype(float)
MED = float(anch.median())          # 97
LO_P4, HI_P4 = 0.5 * MED, 2.0 * MED  # P4's band
CORPUS_MIN, CORPUS_MAX = float(anch.min()), float(anch.max())  # 19, 51295
ANTIMODE = 250.0                     # measured trough (see report)
SUBSTANTIVE = 2000.0

HEAD_RE = re.compile(r"item\s*1\s*\(?a\)?[\s\xa0.:|\-–—]{0,20}risk\s*factors", re.I)


def head_offset(t):
    if not isinstance(t, str) or not t:
        return None
    m = HEAD_RE.search(t[:400])
    return m.start() if m else -1


def band_p4(w):
    if w is None or (isinstance(w, float) and np.isnan(w)):
        return ""
    if w < LO_P4:
        return "BELOW_0.5x_MEDIAN"
    if w > HI_P4:
        return "ABOVE_2x_MEDIAN"
    return "IN_0.5-2x_BAND"


def band_bimodal(w):
    if w is None or (isinstance(w, float) and np.isnan(w)):
        return ""
    if w < CORPUS_MIN:
        return "OUT_LOW_below_corpus_min"
    if w > CORPUS_MAX:
        return "OUT_HIGH_above_corpus_max"
    if w <= ANTIMODE:
        return "BAND_STUB(19-250w)"
    if w <= SUBSTANTIVE:
        return "BAND_MID(250-2000w)"
    return "BAND_SUBSTANTIVE(2000-51295w)"


d = pd.read_json(os.path.join(OUT, "census_rows.jsonl"), lines=True)
assert len(d) == 779 and d.accession_number.nunique() == 779, "census must be 779 unique rows"
assert d.shipped_span_is_none.all(), "every row must really be on the EXPECTED_ABSENT path"

is_r2 = d.verdict == "R2_first_dangling_later_resolves"
is_r3 = d.verdict == "R3_all_matching_dangling"

d["best_source"] = np.where(is_r2, "F1_anchor_later_entry_end_guarded",
                            np.where(is_r3, "F2_heading_regex_fallback", "none"))
d["best_words"] = np.where(is_r2, d.get("rec_guarded_words"),
                           np.where(is_r3, d.get("fb_words"), np.nan))
d["best_head"] = np.where(is_r2, d.get("rec_head"),
                          np.where(is_r3, d.get("fb_head"), ""))
d["best_end_ran_to_eof"] = np.where(is_r2, d.get("rec_end_at_eof"),
                                    np.where(is_r3, d.get("fb_end_at_eof"), np.nan))
d["head_char_offset"] = d.best_head.map(head_offset)
d["head_opens_on_item1a"] = d.head_char_offset.map(
    lambda o: None if o is None else (o is not None and o >= 0 and o < 40))
d["end_guard_shortened_span"] = np.where(
    is_r2, d.get("rec_guarded_words") < d.get("rec_words"), np.nan)

# GUARD 2. An END-GUARDED span that STILL terminates at end-of-document is
# prima facie wrong: a real Part II Item 1A is always followed by Item 2
# (Unregistered Sales) or a later Part II item, so if none of the shipped
# end-patterns matched after the start, the START is in the wrong place.
# Measured on this population it separates cleanly (58 clean / 12 garbage,
# zero errors against the hand read -- see the report's spot-read section).
#  * R2: the guard is applied here, so "still at EOF" == guard never fired
#        AND the raw span ran to EOF.
#  * R3: `locate_item_section_by_heading_regex` already applies the end
#        patterns, so `fb_end_at_eof` IS this condition. All 12 R3 rows
#        (every one AIG) fail it.
d["guarded_span_still_ends_at_eof"] = np.where(
    is_r2, (d.get("rec_end_at_eof") == True) & ~(d.get("rec_guarded_words") < d.get("rec_words")),  # noqa: E712
    np.where(is_r3, d.get("fb_end_at_eof") == True, np.nan))                                        # noqa: E712

d["clears_word_floor_15"] = d.best_words >= 15
d["clears_char_gate_30"] = np.where(is_r2, d.get("rec_guarded_chars") >= 30,
                                    np.where(is_r3, d.get("fb_chars") >= 30, np.nan))
d["band_p4_0.5-2x_median"] = d.best_words.map(band_p4)
d["band_bimodal_recalibrated"] = d.best_words.map(band_bimodal)

# Defensible = the span starts on the item's own heading, sits inside the
# measured corpus range, and clears the shipped gates. Deliberately does NOT
# require the P4 band: this section's distribution is bimodal (see report).
d["defensible_span"] = (
    (d.head_opens_on_item1a == True)                        # GUARD 1  noqa: E712
    & (d.guarded_span_still_ends_at_eof == False)           # GUARD 2  noqa: E712
    & d.clears_word_floor_15.fillna(False)
    & (d.clears_char_gate_30 == True)                       # noqa: E712
    & ~d["band_bimodal_recalibrated"].isin(["OUT_LOW_below_corpus_min",
                                            "OUT_HIGH_above_corpus_max"])
    & d.verdict.isin(["R2_first_dangling_later_resolves", "R3_all_matching_dangling"])
)

# --- hand-read audit trail (see the report's spot-read section). These are
# the two classes I read by eye and ruled NOT defensible; both are caught by
# the guards above, so this list is a CHECK on the guards, not an override.
HAND_NOT_DEFENSIBLE = {
    # 13 Eversource rows: the later-resolvable anchor lands on
    # "PART II. OTHER INFORMATION / ITEM 1. LEGAL PROCEEDINGS", so the span is
    # Legal Proceedings + Item 1A concatenated. Caught by GUARD 1.
    "EVERSOURCE ENERGY",
}
_hand = d[(d.verdict != "R1_genuinely_absent_from_toc")
          & (d.company_name.isin(HAND_NOT_DEFENSIBLE) | (d.verdict == "R3_all_matching_dangling"))]
assert not _hand.defensible_span.any(), (
    "hand-read rows ruled garbage are being marked defensible: "
    f"{_hand[_hand.defensible_span].accession_number.tolist()}")

cols = ["accession_number", "cik", "company_name", "sector", "stratum", "form",
        "filing_date", "section_type", "source_document", "verdict",
        "n_toc_entries", "n_matching", "n_resolvable", "shipped_span_is_none",
        "best_source", "best_words", "best_end_ran_to_eof",
        "rec_words", "rec_guarded_words", "rec_end_at_eof", "end_guard_shortened_span",
        "fb_words", "fb_end_at_eof", "doc_words",
        "head_char_offset", "head_opens_on_item1a",
        "clears_word_floor_15", "clears_char_gate_30",
        "guarded_span_still_ends_at_eof", "band_p4_0.5-2x_median", "band_bimodal_recalibrated", "defensible_span",
        "best_head"]
cols = [c for c in cols if c in d.columns]
out = d[cols].sort_values(["verdict", "company_name", "filing_date"])
out.to_csv(os.path.join(OUT, "ea_census_779.csv"), index=False)

# ---------------------------------------------------------------- reporting
print(f"measured (10-Q,RISK_FACTORS) anchor dist: n={len(anch)} median={MED:.0f} "
      f"min={CORPUS_MIN:.0f} max={CORPUS_MAX:.0f}  P4 band=[{LO_P4:.1f},{HI_P4:.1f}]")
print()
print("=== CENSUS, all 779 ===")
print(out.verdict.value_counts().to_string())
print("reconciles to 779:", len(out) == 779, "| sum =", out.verdict.value_counts().sum())
print()
mis = out[out.verdict != "R1_genuinely_absent_from_toc"]
print(f"MISCLASSIFIED (item IS in the TOC): {len(mis)} of 779 = {100*len(mis)/779:.2f}%")
print(f"  defensible span: {int(mis.defensible_span.sum())}")
print(f"  head does NOT open on Item 1A: {int((mis.head_opens_on_item1a != True).sum())}")
print()
print("--- by arm ---")
for v, g in mis.groupby("verdict"):
    print(f"{v}: n={len(g)} defensible={int(g.defensible_span.sum())} "
          f"head_ok={int((g.head_opens_on_item1a==True).sum())} "
          f"end_ran_to_eof={int(g.best_end_ran_to_eof.fillna(0).sum())}")
print()
print("--- P4 band (0.5-2x median) on the 83 ---")
print(mis["band_p4_0.5-2x_median"].value_counts().to_string())
print()
print("--- recalibrated bimodal band on the 83 ---")
print(mis["band_bimodal_recalibrated"].value_counts().to_string())
print()
print("--- defensible rows by filer ---")
dd = mis[mis.defensible_span]
print(dd.company_name.value_counts().to_string())
print()
print("--- defensible rows by filing year ---")
print(dd.filing_date.astype(str).str[:4].value_counts().sort_index().to_string())
print()
print("--- floor clearing among the defensible ---")
print("clears 15-word floor:", int(dd.clears_word_floor_15.sum()), "/", len(dd))
print("clears 30-char gate :", int((dd.clears_char_gate_30 == True).sum()), "/", len(dd))
print()
print("--- word counts of the defensible spans ---")
print(dd.best_words.describe(percentiles=[.25, .5, .75, .9]).round(1).to_string())
print()
print("wrote", os.path.join(OUT, "ea_census_779.csv"))
