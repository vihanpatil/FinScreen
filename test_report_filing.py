"""test_report_filing.py -- the enforcement suite for the L2.1 renderer.

Two layers, mirroring `test_features_e2.py`:

  * SYNTHETIC fixtures for every behaviour that has a right answer independent
    of the corpus -- containment, the section mask, the prior-filing diff,
    shared-boilerplate marking, the disclosure header's contents, the refusal
    scans, the source-scan, determinism.
  * `@pytest.mark.slow` smoke tests that render two REAL filings (Apple's
    FY2024 10-K and the Q1-FY2025 earnings 8-K) end to end and re-scan the
    output.

The refusals the owner ruled on 2026-09-11 are enforced HERE, in code, not in
the module's prose. A refusal with no test is not a refusal.

Three of the scans below were rewritten after a red-team review found them
vacuous or blind:

  * `chrome_only` used to delete the WHOLE text-col div, which took the
    report's own markers out of the scanned chrome along with the filing's
    quoted words. It now deletes only the quoted paragraphs (the `<p>`
    elements with no class); every marker the report writes stays in the scan.
  * the cross-company assertion used to test a string that could not appear;
    it now names the seven issuers that really did leak onto the Apple 10-K
    page before the containment filter existed.
  * the vocabulary scan now whitelists HTML TAG NAMES by tag, so `<summary>`
    is markup while the word "summary" in prose still fails.
"""

from __future__ import annotations

import ast
import builtins
import hashlib
import json
import re
import sqlite3
import time
from html import unescape
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest

import features_e2 as FE
import report_filing as RF

REPO_ROOT = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# The refusal vocabulary. Matched as whole words, case-insensitively, so
# "score_labels" (a function name) and "shareholders" (a real English word in
# the filings) do not trip a scan that is looking for "score" and "hold".
# ---------------------------------------------------------------------------
ACTION_VOCABULARY = [
    "buy", "sell", "hold", "overweight", "underweight", "outperform",
    "underperform", "accumulate", "recommend", "recommendation", "rating",
    "conviction", "bullish", "bearish", "upside", "downside",
]
QUANTITY_VOCABULARY = ["score", "composite", "rank", "ranking", "percentile",
                       "alert", "portfolio", "watchlist", "summary",
                       "summaries"]
MARKET_VOCABULARY = ["price", "prices", "return", "returns", "ticker symbol",
                     "market cap", "share price", "stock"]
REFUSED_VOCABULARY = ACTION_VOCABULARY + QUANTITY_VOCABULARY + MARKET_VOCABULARY

# Modules and artifacts the report layer must never import or read
# (HANDOFF §3, 2026-09-11; council Q4's "source-scan test").
FORBIDDEN_NAMES = ["prices_e2", "target_e2", "backtest_e2", "heads_e2",
                   "controls", "data/f5"]
FORBIDDEN_IMPORTS = {"prices_e2", "target_e2", "backtest_e2", "heads_e2",
                     "controls", "price_client", "ingest_prices", "backtest"}

# Item 5: the E1 outcome layer IS in the transitive closure (features_e2 ->
# controls -> backtest) and is allowed to be -- the mask has to stay derived.
# What must hold is that no function of either module is REACHABLE from a
# render, and that no outcome artifact is opened while one runs.
TRANSITIVE_CLOSURE = {
    "backtest", "controls", "edgar_client", "features", "features_e2",
    "ingest_fundamentals", "ingest_metadata", "numeric_features_e2", "pit",
    "report_filing", "spec",
}
OUTCOME_MODULES = {"controls", "backtest", "prices_e2", "target_e2",
                   "backtest_e2", "heads_e2", "price_client", "ingest_prices"}

# Artifacts no render path may open, at all (council Q4's kill criterion:
# "report layer found reading an outcome table or IC").
FORBIDDEN_ARTIFACT_FRAGMENTS = [
    "prices_e2.parquet", "target_e2.parquet", "backtest_report.md",
    "/data/f5/", "text_features_e2", "numeric_features_e2.parquet",
    "results_head", "backtest_e2", "heads_e2",
]

# Everything a render IS allowed to open. A new read cannot enter silently.
ALLOWED_ARTIFACT_FRAGMENTS = [
    "data/app/cache/chunk_index_v1.parquet",
    "data/f4/campaign_manifest.json",
    "data/f4/chunks_v1.parquet",
    "data/f4/labels_e2_v1.parquet",
    "data/f4/g2/results_g2.json",
    "data/f4/g2/G2_FINAL_REPORT.md",
    "data/hardening/spotcheck_v12/results_v12.json",
    "finetune/splits_v12/train.parquet",
    "finetune/runs/2026-08-28-v12-eval-epoch2/metrics.json",
    "data/filings_metadata_e2.db",
    "data/filings_e2_v2.parquet",
    "data/fundamentals_e2.parquet",
    "data/f2/concept_resolution.csv",
    "data/f2/price_ticker_map.csv",
]

# String constants in report_filing.py that ARE the mandatory disclosure and
# are therefore exempt from the action-vocabulary scan (the allow-list the
# ruling requires).
DISCLOSURE_CONSTANT_NAMES = {
    "IDENTITY_LINE", "FOOTER_LINE", "NO_PRICE_LINE",
    "PREDICTIVE_VALIDITY_TEMPLATE", "CONFIG_SENSITIVITY_TEXT",
    "CONFIG_SENSITIVITY_COUNT", "CONFIG_SENSITIVITY_SUBJECT",
    "SELFID_STRICT_TEXT", "SELFID_LOOSE_TEXT", "SELFID_SUBJECT",
    "SENTIMENT_ESTIMAND", "CSS",
}

MODULE_SOURCE = (REPO_ROOT / "report_filing.py").read_text()
MODULE_AST = ast.parse(MODULE_SOURCE)
# The module DOCSTRING is documentation, and documenting the transitive import
# closure honestly means naming `controls` and `backtest` in it. Everything
# else -- code and comments alike -- is held to the forbidden-name scan.
MODULE_DOCSTRING = ast.get_docstring(MODULE_AST, clean=False) or ""
assert MODULE_DOCSTRING
MODULE_SOURCE_NO_DOCSTRING = MODULE_SOURCE.replace(MODULE_DOCSTRING, "", 1)

# HTML tag names are MARKUP, not the report's prose. They are whitelisted by
# TAG -- `<summary>` is stripped, the word "summary" written in a sentence is
# not -- and attribute text is deliberately left in the scan.
ALLOWED_TAG_NAMES = {
    "html", "head", "body", "meta", "title", "style", "div", "p", "section",
    "ul", "ol", "li", "b", "i", "em", "strong", "span", "code", "blockquote",
    "table", "thead", "tbody", "tr", "th", "td", "h1", "h2", "h3", "h4",
    "details", "summary", "a", "br", "hr",
}
HTML_TAG = re.compile(r"</?([A-Za-z][A-Za-z0-9]*)((?:\s[^<>]*?)?)/?>", re.S)


def strip_tag_names(html: str) -> str:
    """Drop whitelisted tag names, keep their attributes in the scan."""
    def repl(match: re.Match) -> str:
        name, attrs = match.group(1), match.group(2) or ""
        if name.lower() in ALLOWED_TAG_NAMES:
            return " " + attrs + " "
        return " " + match.group(0) + " "
    return HTML_TAG.sub(repl, html)


def word_hits(text: str, vocabulary=REFUSED_VOCABULARY) -> list[str]:
    low = strip_tag_names(text).lower()
    return sorted({w for w in vocabulary
                   if re.search(r"\b" + re.escape(w) + r"\b", low)})


# ---------------------------------------------------------------------------
# synthetic fixtures
# ---------------------------------------------------------------------------
HERE = "0000000001-24-000001"
PRIOR = "0000000001-23-000001"
OTHER = "0000000002-20-000001"


def _chunk(row_index, chunk_id, section, sources, *, home=HERE,
           sentiment="NEUTRAL", guidance="NONE", applicable=True,
           imputed=False, schema_valid=True, issues=(), flags=(),
           home_form="10-K", home_date="2024-11-01",
           company="Synthetic Industries Inc", n_paragraphs=1, word_count=12):
    return {
        "chunk_id": chunk_id,
        "section_type": section,
        "home_cik": 1,
        "home_company_name": company,
        "home_accession_number": home,
        "home_form": home_form,
        "home_filing_date": home_date,
        "home_extraction_status": "OK",
        "home_extraction_confidence": "high",
        "home_extraction_method": "anchor",
        "home_flags": np.array([], dtype=object),
        "word_count": word_count,
        "n_paragraphs": n_paragraphs,
        "source_accession_numbers": np.array(list(sources), dtype=object),
        "n_source_filings": len(sources),
        "sentiment": sentiment,
        "guidance_direction": guidance,
        "guidance_applicable": applicable,
        "guidance_imputed_none": imputed,
        "schema_valid": schema_valid,
        "schema_issues": np.array(list(issues), dtype=object),
        "red_flags": np.array(
            [{"category": c, "modality": m} for c, m in flags], dtype=object),
        "row_index": row_index,
        "train_overlap_home": False,
        "train_overlap_source": False,
        "train_overlap_accession": False,
    }


# The synthetic corpus's passage text, paragraph by paragraph. The two filings'
# section texts below are BUILT from these lists, so containment has a right
# answer that is not a restatement of the code under test.
PARAGRAPHS = {
    "C-mda-keep": ["Demand held steady across the period.",
                   "Segment margins were flat year on year."],
    "C-rf-keep": ["Our operations depend on a small number of suppliers."],
    "C-mda-new": ["We opened a second fulfilment centre this year."],
    "C-mda-gone": ["Last year we operated a single fulfilment centre."],
    "C-shared": ["Forward-looking statements speak only as of the date made.",
                 "Contact our investor relations department for details."],
    "C-ex99-active": ["We now expect full-year revenue above the prior range."],
    "C-bad-enum": ["Quarterly results are summarised in the tables that follow."],
    "C-8k": ["The registrant issued the press release furnished as Exhibit 99.1."],
    "C-ex99-na": ["The company will host a conference call at five o'clock."],
    # Attributed to HERE by its occurrence array, but not one of its paragraphs
    # is in HERE's text: the union-array case the containment filter exists for.
    "C-foreign": ["Our semiconductor fabrication yields improved this quarter.",
                  "Wafer starts increased at the Boise facility."],
    # Attributed to BOTH filings; its text is only in the prior one.
    "C-prior-only": ["The legacy distribution agreement remains in force."],
    # Attributed to BOTH filings; its text is only in this one.
    "C-here-only": ["A new distribution agreement took effect in October."],
}

# Which paragraphs of which chunk appear in which filing's section text.
# (chunk_id -> paragraph indices) per (accession, section).
HERE_SECTIONS = {
    "MDA": [("C-mda-keep", [0, 1]), ("C-mda-new", [0]), ("C-here-only", [0])],
    "RISK_FACTORS": [("C-rf-keep", [0])],
    # C-shared is PARTIAL here: only its first paragraph is in this filing.
    "EX99_PRESS_RELEASE": [("C-shared", [0]), ("C-ex99-active", [0]),
                           ("C-bad-enum", [0]), ("C-ex99-na", [0])],
    "8K_BODY": [("C-8k", [0])],
}
PRIOR_SECTIONS = {
    "MDA": [("C-mda-keep", [0, 1]), ("C-mda-gone", [0]), ("C-prior-only", [0])],
    "RISK_FACTORS": [("C-rf-keep", [0])],
    "EX99_PRESS_RELEASE": [("C-shared", [0])],
}


def _section_text(spec: dict) -> dict:
    return {section: "\n\n".join(PARAGRAPHS[cid][i] for cid, idx in members
                                 for i in idx)
            for section, members in spec.items()}


@pytest.fixture
def index() -> pd.DataFrame:
    """A tiny corpus: one filing, its prior same-form filing, one passage of
    shared boilerplate homed in a third company's older filing, one passage
    attributed here that is wholly some other company's words."""
    rows = [
        # 0-1: homed here, in both filings -> UNCHANGED
        _chunk(0, "C-mda-keep", "MDA", [PRIOR, HERE], home=PRIOR,
               home_date="2023-11-03", sentiment="POSITIVE", n_paragraphs=2,
               flags=[("DEMAND_WEAKNESS", "HYPOTHETICAL")]),
        _chunk(1, "C-rf-keep", "RISK_FACTORS", [PRIOR, HERE], home=PRIOR,
               home_date="2023-11-03", sentiment="NEGATIVE"),
        # 2: homed here, only in this filing -> NEW
        _chunk(2, "C-mda-new", "MDA", [HERE], sentiment="NEGATIVE",
               flags=[("IMPAIRMENT_WRITEDOWN", "REALIZED")]),
        # 3: only in the prior filing -> REMOVED
        _chunk(3, "C-mda-gone", "MDA", [PRIOR], home=PRIOR,
               home_date="2023-11-03", sentiment="NEUTRAL",
               flags=[("TRADE_POLICY_EXPOSURE", "HYPOTHETICAL")]),
        # 4: shared boilerplate first seen in another company's filing, and
        #    only PARTLY contained in this one
        _chunk(4, "C-shared", "EX99_PRESS_RELEASE", [OTHER, PRIOR, HERE],
               home=OTHER, home_date="2020-02-02", home_form="8-K",
               company="Elsewhere Holdings", sentiment="NEUTRAL",
               guidance="NONE", imputed=True, n_paragraphs=2),
        # 5: guidance-applicable EX-99 passage with an active direction
        _chunk(5, "C-ex99-active", "EX99_PRESS_RELEASE", [HERE],
               sentiment="POSITIVE", guidance="RAISED"),
        # 6: schema-invalid guidance enum
        _chunk(6, "C-bad-enum", "EX99_PRESS_RELEASE", [HERE],
               sentiment="NEUTRAL", guidance=None, schema_valid=False,
               issues=["bad_enum:guidance_direction"]),
        # 7: 8K_BODY -- never evaluable
        _chunk(7, "C-8k", "8K_BODY", [HERE], sentiment="POSITIVE",
               guidance="RAISED", flags=[("DEMAND_WEAKNESS", "REALIZED")]),
        # 8: EX-99 passage that is not guidance-applicable
        _chunk(8, "C-ex99-na", "EX99_PRESS_RELEASE", [HERE],
               sentiment="NEUTRAL", guidance=None, applicable=False),
        # 9: attributed here by its occurrence array; WHOLLY another company's
        #    words. Must never render.
        _chunk(9, "C-foreign", "MDA", [OTHER, HERE], home=OTHER,
               home_date="2020-02-02", home_form="10-K",
               company="Elsewhere Holdings", sentiment="NEGATIVE",
               n_paragraphs=2, flags=[("SUPPLY_INPUT_CONSTRAINT", "REALIZED")]),
        # 10-11: attributed to both filings, contained in only one of them
        _chunk(10, "C-prior-only", "MDA", [PRIOR, HERE], home=PRIOR,
               home_date="2023-11-03", sentiment="NEUTRAL"),
        _chunk(11, "C-here-only", "MDA", [PRIOR, HERE], home=PRIOR,
               home_date="2023-11-03", sentiment="NEUTRAL"),
    ]
    return pd.DataFrame(rows)


@pytest.fixture
def occ(index) -> dict:
    return RF.occurrence_map(index)


@pytest.fixture
def texts(index) -> dict:
    return {int(r.row_index): "\n\n".join(PARAGRAPHS[r.chunk_id])
            for r in index.itertuples()}


@pytest.fixture
def sections() -> dict:
    return _section_text(HERE_SECTIONS)


@pytest.fixture
def prior_sections() -> dict:
    return _section_text(PRIOR_SECTIONS)


def _contained(index, occ, texts, sections, accession=HERE):
    frame = RF.filing_frame(index, occ, accession)
    return RF.apply_containment(frame, texts, sections)


@pytest.fixture
def contained(index, occ, texts, sections):
    frame, rendered, stats = _contained(index, occ, texts, sections)
    return frame, rendered, stats


# ---------------------------------------------------------------------------
# 0. CONTAINMENT -- the filter that makes "attributed" mean "in this filing"
# ---------------------------------------------------------------------------
def test_collapse_whitespace_is_the_only_normalisation():
    assert RF.collapse_whitespace("  a\n b\t\tc ") == "a b c"
    assert RF.collapse_whitespace(None) == ""


def test_split_paragraphs_uses_the_blank_line_separator():
    assert RF.split_paragraphs("a\n\nb\n\n\n\nc") == ["a", "b", "c"]
    assert RF.split_paragraphs("   ") == []


def test_contained_paragraphs_ignores_whitespace_differences():
    section = RF.collapse_whitespace("The margin   improved.\nDemand fell.")
    kept = RF.contained_paragraphs("The margin\nimproved.\n\nUnrelated text.",
                                   section)
    assert kept == ["The margin\nimproved."]


def test_every_rendered_paragraph_is_inside_the_filing_text(contained, sections):
    """The property the whole fix exists for, on the synthetic filing."""
    frame, rendered, _ = contained
    assert len(frame) > 0
    for row in frame.itertuples():
        section = sections[row.section_type]
        paragraphs = RF.split_paragraphs(rendered[int(row.row_index)])
        assert paragraphs
        for paragraph in paragraphs:
            assert RF.collapse_whitespace(paragraph) in section, paragraph


def test_a_chunk_with_no_contained_paragraph_never_renders(contained):
    frame, rendered, stats = contained
    # C-foreign is wholly another company's words; C-prior-only is real text
    # that belongs to the PRIOR filing. Neither is in this filing.
    assert {"C-foreign", "C-prior-only"} & set(frame.chunk_id) == set()
    assert stats["chunks_dropped"] == 2


def test_a_chunk_homed_in_another_company_renders_only_if_contained(
        index, occ, texts, sections):
    """`C-foreign` and `C-shared` are both homed at Elsewhere Holdings. The one
    whose words are in this filing renders; the one whose words are not, does
    not."""
    frame, rendered, _ = _contained(index, occ, texts, sections)
    homed_elsewhere = frame[frame.home_accession_number == OTHER]
    assert set(homed_elsewhere.chunk_id) == {"C-shared"}
    assert RF.split_paragraphs(rendered[4]) == [PARAGRAPHS["C-shared"][0]]


def test_partial_chunks_keep_only_their_contained_paragraphs(contained):
    frame, rendered, stats = contained
    shared = frame[frame.chunk_id == "C-shared"].iloc[0]
    assert int(shared.n_rendered_paragraphs) == 1
    assert int(shared.n_source_paragraphs) == 2
    assert PARAGRAPHS["C-shared"][1] not in rendered[4]
    assert stats["chunks_partial"] == 1


def test_partial_marker_says_how_many_paragraphs_survived(contained):
    frame, rendered, _ = contained
    row = next(r for r in frame.itertuples() if r.chunk_id == "C-shared")
    html = RF.passage_html(row, rendered[int(row.row_index)], HERE, "note")
    assert "Partial: 1 of 2 paragraphs" in html
    assert "not shown" in html


def test_a_fully_contained_chunk_carries_no_partial_marker(contained):
    frame, rendered, _ = contained
    row = next(r for r in frame.itertuples() if r.chunk_id == "C-mda-keep")
    html = RF.passage_html(row, rendered[int(row.row_index)], HERE, "note")
    assert "Partial:" not in html


def test_n_source_filings_is_shown_on_every_passage(contained):
    frame, rendered, _ = contained
    for row in frame.itertuples():
        html = RF.passage_html(row, rendered[int(row.row_index)], HERE, "note")
        n = int(row.n_source_filings)
        word = "filing" if n == 1 else "filings"
        assert f"This passage appears in {n:,} {word} in the corpus." in html


def test_containment_stats_add_up(contained, sections):
    frame, rendered, stats = contained
    assert stats["chunks_attributed"] == 11        # candidates for HERE
    assert stats["chunks_rendered"] == len(frame) == 9
    assert stats["chunks_dropped"] == 2
    assert stats["paragraphs_rendered"] == sum(
        len(RF.split_paragraphs(t)) for t in rendered.values())
    assert stats["paragraphs_rendered"] < stats["paragraphs_attributed"]
    assert stats["words_rendered"] < stats["words_attributed"]
    assert stats["section_words"] == sum(len(t.split()) for t in sections.values())


def test_shared_boilerplate_marker_never_names_another_company(contained):
    """After containment the words below the marker are THIS filing's. Naming
    the issuer the corpus deduplicated them into read as though this filing
    contained that issuer's text, which is what leaked seven companies onto
    the Apple 10-K page."""
    frame, rendered, _ = contained
    row = next(r for r in frame.itertuples() if r.chunk_id == "C-shared")
    html = RF.passage_html(row, rendered[int(row.row_index)], HERE, "note")
    assert "Deduplicated into an earlier filing" in html
    assert OTHER in html
    assert "Elsewhere Holdings" not in html


def test_apply_containment_on_an_empty_frame_is_empty(index, occ, texts):
    frame, rendered, stats = _contained(index, occ, texts, {}, "no-such-accession")
    assert frame.empty and rendered == {} and stats["chunks_rendered"] == 0


def test_a_section_missing_from_the_filing_renders_nothing(index, occ, texts,
                                                           sections):
    """If the extractor recorded no MDA for this filing, no MDA passage can be
    contained in it, so none renders."""
    without_mda = {k: v for k, v in sections.items() if k != "MDA"}
    frame, _, _ = _contained(index, occ, texts, without_mda)
    assert "MDA" not in set(frame.section_type)


# ---------------------------------------------------------------------------
# 1. the section mask -- derived from features_e2, never restated
# ---------------------------------------------------------------------------
def test_mask_hides_sentiment_on_risk_factors_only(index):
    flags = RF.mask_flags(index)
    hidden = set(index.section_type[flags.sentiment_masked.to_numpy()])
    assert hidden == {"RISK_FACTORS"}


def test_mask_hides_guidance_on_mda_risk_factors_and_non_applicable(index):
    flags = RF.mask_flags(index)
    masked = index[flags.guidance_masked.to_numpy()]
    assert set(masked.section_type) == {"MDA", "RISK_FACTORS",
                                        "EX99_PRESS_RELEASE"}
    # the only EX-99 row masked is the one the stored flag says is not
    # guidance-applicable
    ex99 = masked[masked.section_type == "EX99_PRESS_RELEASE"]
    assert set(ex99.chunk_id) == {"C-ex99-na"}
    assert not any(ex99.guidance_applicable)


def test_mask_is_derived_from_features_e2_not_restated(index, monkeypatch):
    """If `features_e2.score_labels` changed, the report's mask must change
    with it. A restated copy of the rule would fail this test."""
    def stricter(frame):
        out = frame.copy()
        out["sentiment_num"] = np.nan          # everything masked
        out["guidance_num"] = np.nan
        return out

    monkeypatch.setattr(FE, "score_labels", stricter)
    flags = RF.mask_flags(index)
    assert flags.sentiment_masked.all()
    assert flags.guidance_masked.all()


def test_mask_does_not_confuse_a_null_label_with_a_masked_one(index):
    """`C-bad-enum` carries a NULL guidance value on an applicable EX-99 row.
    That is 'no value emitted', not 'masked', and the two must render
    differently."""
    flags = RF.mask_flags(index)
    row = index.index[index.chunk_id == "C-bad-enum"][0]
    assert not flags.guidance_masked.iloc[row]


@pytest.mark.parametrize("map_name,probe", [("SENTIMENT_MAP", RF.SENTIMENT_PROBE),
                                            ("GUIDANCE_MAP", RF.GUIDANCE_PROBE)])
def test_mask_probe_refuses_to_run_if_its_label_stops_mapping(
        index, monkeypatch, map_name, probe):
    """The probe reads a NaN as 'masked'. If the map lost the probe's key,
    every field would read as masked and the page would silently show no
    labels at all -- so the probe asserts its own precondition."""
    stripped = {k: v for k, v in getattr(FE, map_name).items() if k != probe}
    monkeypatch.setattr(FE, map_name, stripped)
    with pytest.raises(RuntimeError, match="mask probe"):
        RF.mask_flags(index)


def test_mask_probe_labels_are_live_keys_of_the_imported_maps():
    assert RF.SENTIMENT_PROBE in FE.SENTIMENT_MAP
    assert RF.GUIDANCE_PROBE in FE.GUIDANCE_MAP
    assert not pd.isna(FE.SENTIMENT_MAP[RF.SENTIMENT_PROBE])
    assert not pd.isna(FE.GUIDANCE_MAP[RF.GUIDANCE_PROBE])


# ---------------------------------------------------------------------------
# 2. label rendering
# ---------------------------------------------------------------------------
def _render_labels(index, chunk_id, note="SECTION-ZERO-SENTENCE"):
    frame = index.copy()
    flags = RF.mask_flags(frame)
    frame["sentiment_masked"] = flags.sentiment_masked.to_numpy()
    frame["guidance_masked"] = flags.guidance_masked.to_numpy()
    row = next(r for r in frame.itertuples() if r.chunk_id == chunk_id)
    return RF.label_html(row, note)


def test_imputed_none_is_labelled_and_carries_the_g2_sentence(index):
    html = _render_labels(index, "C-shared")
    assert "NONE (no guidance key emitted)" in html
    assert "SECTION-ZERO-SENTENCE" in html


def test_stored_none_is_not_dressed_up_as_imputed(index):
    html = _render_labels(index, "C-mda-keep")
    assert "no guidance key emitted" not in html


def test_schema_invalid_value_says_invalid_enum_not_remapped(index):
    html = _render_labels(index, "C-bad-enum")
    assert "invalid enum, not remapped" in html


def test_every_red_flag_carries_the_exploratory_tag(index):
    for chunk_id in ("C-mda-keep", "C-mda-new"):
        html = _render_labels(index, chunk_id)
        n_flags = html.count("·")
        assert n_flags >= 1
        assert html.count("exploratory") == n_flags


def test_masked_fields_say_so_rather_than_showing_a_value(index):
    html = _render_labels(index, "C-rf-keep")
    assert "not shown — section mask" in html
    assert "NEGATIVE" not in html


# ---------------------------------------------------------------------------
# 3. passages: 8K_BODY, shared boilerplate
# ---------------------------------------------------------------------------
def test_8k_body_renders_text_but_no_labels(contained):
    frame, rendered, _ = contained
    row = next(r for r in frame.itertuples() if r.section_type == "8K_BODY")
    html = RF.passage_html(row, rendered[int(row.row_index)], HERE, "note")
    assert "not evaluable" in html.lower()
    assert PARAGRAPHS["C-8k"][0] in html
    for value in ("POSITIVE", "RAISED", "DEMAND_WEAKNESS"):
        assert value not in html


def test_a_passage_homed_here_is_not_marked_as_deduplicated(contained):
    frame, rendered, _ = contained
    own = next(r for r in frame.itertuples() if r.chunk_id == "C-mda-new")
    html = RF.passage_html(own, rendered[int(own.row_index)], HERE, "note")
    assert "Deduplicated into an earlier filing" not in html


def test_filing_frame_collects_home_and_inherited_candidates(index, occ):
    frame = RF.filing_frame(index, occ, HERE)
    assert set(frame.chunk_id) == {
        "C-mda-keep", "C-rf-keep", "C-mda-new", "C-shared", "C-ex99-active",
        "C-bad-enum", "C-8k", "C-ex99-na", "C-foreign", "C-prior-only",
        "C-here-only"}
    assert "C-mda-gone" not in set(frame.chunk_id)


def test_filing_frame_order_is_deterministic(index, occ):
    a = list(RF.filing_frame(index, occ, HERE).chunk_id)
    b = list(RF.filing_frame(index, occ, HERE).chunk_id)
    assert a == b
    sections = list(RF.filing_frame(index, occ, HERE).section_type)
    ranks = [RF.SECTION_ORDER.index(s) for s in sections]
    assert ranks == sorted(ranks)


def test_word_count_shown_is_the_rendered_word_count(contained):
    frame, rendered, _ = contained
    row = next(r for r in frame.itertuples() if r.chunk_id == "C-shared")
    html = RF.passage_html(row, rendered[int(row.row_index)], HERE, "note")
    rendered_words = len(PARAGRAPHS["C-shared"][0].split())
    assert f"{rendered_words} words" in html
    assert f"{int(row.word_count)} words" not in html


# ---------------------------------------------------------------------------
# 4. the prior-filing diff
# ---------------------------------------------------------------------------
@pytest.fixture
def diff(index, occ, texts, sections, prior_sections):
    here, _, _ = _contained(index, occ, texts, sections, HERE)
    prior, _, _ = _contained(index, occ, texts, prior_sections, PRIOR)
    return RF.diff_vs_prior(here, prior)


def test_diff_on_a_synthetic_pair_is_exact(diff):
    """The whole NEW / REMOVED / UNCHANGED partition, named chunk by chunk.

    `C-here-only` and `C-prior-only` are attributed to BOTH filings by their
    occurrence arrays and would both be UNCHANGED without containment; each is
    physically in exactly one of the two filings, so the diff must split them.
    `C-foreign` is in neither text and appears nowhere at all.
    """
    assert set(diff["new"].chunk_id) == {
        "C-mda-new", "C-here-only", "C-ex99-active", "C-bad-enum", "C-8k",
        "C-ex99-na"}
    assert set(diff["removed"].chunk_id) == {"C-mda-gone", "C-prior-only"}
    assert set(diff["unchanged"].chunk_id) == {
        "C-mda-keep", "C-rf-keep", "C-shared"}
    everywhere = (set(diff["new"].chunk_id) | set(diff["removed"].chunk_id)
                  | set(diff["unchanged"].chunk_id))
    assert "C-foreign" not in everywhere
    assert len(everywhere) == 11


def test_diff_lists_only_newly_appearing_red_flag_categories(diff):
    # IMPAIRMENT_WRITEDOWN is new; DEMAND_WEAKNESS was already there;
    # TRADE_POLICY_EXPOSURE only existed in the prior filing; and
    # SUPPLY_INPUT_CONSTRAINT rides on the passage containment dropped, so it
    # must not appear either.
    assert diff["new_red_flag_categories"] == ["IMPAIRMENT_WRITEDOWN"]


def test_diff_ignores_red_flags_on_the_non_evaluable_section(
        index, occ, texts, sections, prior_sections):
    """`C-8k` carries DEMAND_WEAKNESS, but 8K_BODY labels are never shown and
    must not enter the newly-appearing-category list either."""
    here, _, _ = _contained(index, occ, texts, sections, HERE)
    prior, _, _ = _contained(index, occ, texts, prior_sections, PRIOR)
    # Drop the MDA passage that carries DEMAND_WEAKNESS from BOTH sides, so the
    # only DEMAND_WEAKNESS left anywhere is the one on the 8K_BODY passage.
    here = here[here.chunk_id != "C-mda-keep"]
    prior = prior[prior.chunk_id != "C-mda-keep"]
    assert "DEMAND_WEAKNESS" in {f["category"] for f in
                                 here[here.section_type == "8K_BODY"]
                                 .red_flags.iloc[0]}
    assert "DEMAND_WEAKNESS" not in RF.diff_vs_prior(
        here, prior)["new_red_flag_categories"]


def test_unchanged_block_is_collapsed_by_default(diff, texts):
    prior_row = pd.Series({"accession_number": PRIOR, "form": "10-K",
                           "filing_date": "2023-11-03"})
    html = RF.diff_html(diff, prior_row, texts, texts, HERE, "note")
    unchanged = html[html.index("UNCHANGED passages"):]
    assert "collapsed by default" in unchanged
    # the fold wrapper is a plain <details> with no `open` attribute
    assert re.search(r'<details class="fold"><summary>UNCHANGED', html)


def test_prior_same_form_is_strictly_earlier_and_same_form():
    filings = pd.DataFrame([
        {"accession_number": "A3", "form": "10-K", "filing_date": "2024-11-01"},
        {"accession_number": "A2", "form": "10-Q", "filing_date": "2024-08-01"},
        {"accession_number": "A1", "form": "10-K", "filing_date": "2023-11-03"},
        {"accession_number": "A0", "form": "10-K", "filing_date": "2022-11-03"},
    ])
    prior = RF.prior_same_form(filings, "A3")
    assert prior.accession_number == "A1"
    assert RF.prior_same_form(filings, "A0") is None


def test_prior_same_form_sorts_for_itself_on_an_unsorted_frame():
    """The caller's ordering is not a precondition: the same answer must come
    back from a frame shuffled into any order."""
    rows = [
        {"accession_number": "A0", "form": "10-K", "filing_date": "2022-11-03"},
        {"accession_number": "A3", "form": "10-K", "filing_date": "2024-11-01"},
        {"accession_number": "A1b", "form": "10-K", "filing_date": "2023-11-03"},
        {"accession_number": "A2", "form": "10-Q", "filing_date": "2024-08-01"},
        {"accession_number": "A1a", "form": "10-K", "filing_date": "2023-11-03"},
    ]
    for order in ([0, 1, 2, 3, 4], [4, 3, 2, 1, 0], [2, 0, 4, 1, 3]):
        frame = pd.DataFrame([rows[i] for i in order])
        prior = RF.prior_same_form(frame, "A3")
        # 2023-11-03 is the latest strictly-earlier date; the tie between A1a
        # and A1b breaks by accession DESCENDING
        assert prior.accession_number == "A1b", order


def test_prior_same_form_never_returns_the_same_day_filing():
    filings = pd.DataFrame([
        {"accession_number": "B2", "form": "8-K", "filing_date": "2024-11-01"},
        {"accession_number": "B1", "form": "8-K", "filing_date": "2024-11-01"},
    ])
    assert RF.prior_same_form(filings, "B2") is None


# ---------------------------------------------------------------------------
# 5. the mandatory disclosure header
# ---------------------------------------------------------------------------
def test_disclosure_source_shas_are_pinned():
    """A disclosure artifact cannot change without this test failing, which is
    the ruling's 'numbers verbatim, read from the artifacts' guarantee."""
    drifted = []
    for label, path in RF.DISCLOSURE_SOURCES.items():
        got = RF._sha256(path)
        if got != RF.DISCLOSURE_SOURCE_SHA256[label]:
            drifted.append((label, got, RF.DISCLOSURE_SOURCE_SHA256[label]))
    assert not drifted, (
        "a disclosure source changed; re-read the numbers into the header and "
        f"re-pin the sha: {drifted}")


def test_the_quoted_negative_recall_is_this_labelers_own_number():
    """The adapter named in the campaign manifest IS the one whose eval the
    header quotes. The v1.1 student's 0.487 is a different model, a different
    split and a different rubric, and is not quoted."""
    manifest = json.loads(RF.CAMPAIGN_MANIFEST.read_text())
    adapter = Path(manifest["inputs"]["adapter_path"])
    assert adapter.name.startswith("cadca849") or "v12" in str(adapter).lower(), adapter
    assert "2026-08-28-v12-eval-epoch2" in str(RF.STUDENT_EVAL)
    assert "2026-08-22-eval-epoch2" not in MODULE_SOURCE.replace(
        "finetune/runs/2026-08-22-eval-epoch2", "")  # only ever as prose

    d = RF.load_disclosure()
    assert d["sentiment"]["negative_recall"] == 0.529
    assert d["sentiment"]["negative_recall_support"] == 121
    assert d["sentiment"]["negative_recall_tp"] == 64
    html = RF.disclosure_html(d, None)
    assert "0.529" in html and "64/121" in html
    assert "0.487" not in html


def test_every_disclosure_number_comes_from_its_artifact():
    d = RF.load_disclosure()
    g2 = json.loads(RF.G2_RESULTS.read_text())
    v12 = json.loads(RF.V12_RESULTS.read_text())
    manifest = json.loads(RF.CAMPAIGN_MANIFEST.read_text())
    ev = json.loads(RF.STUDENT_EVAL.read_text())

    assert (d["sentiment"]["k"], d["sentiment"]["n"]) == (
        g2["primary"]["sentiment"]["k"], g2["primary"]["sentiment"]["n"])
    assert d["sentiment"]["verdict"] == g2["primary"]["sentiment"]["verdict"]
    assert d["sentiment"]["artifact_caveat"] == g2["primary"]["sentiment"]["caveat"]
    assert d["sentiment"]["negative_recall"] == (
        ev["headline"]["sentiment"]["per_class"]["NEGATIVE"]["recall"])
    assert (d["guidance"]["k"], d["guidance"]["n"]) == (
        g2["primary"]["guidance_direction"]["k"],
        g2["primary"]["guidance_direction"]["n"])
    assert d["guidance"]["active_precision_pct"] == pytest.approx(
        g2["guidance_active_precision"]["point"] * 100)
    assert (d["red_flags"]["teacher_k"], d["red_flags"]["teacher_n"]) == (
        v12["P1_exact_set_error"]["k"], v12["P1_exact_set_error"]["n"])
    assert d["red_flags"]["student_n"] == (
        g2["constants"]["redflag_exact_set_error"]["n"])
    assert d["adapter_sha256"] == manifest["inputs"]["adapter_sha256_expected"]


def test_disclosure_header_renders_every_ruled_number():
    html = RF.disclosure_html(RF.load_disclosure(), None)
    required = [
        "293/337", "86.9%", "82.9", "90.1", "INDETERMINATE", "0.529", "64/121",
        "115/119", "96.6%", "91.7", "98.7", "68.7%", "58.2", "77.6", "0/80",
        "84/200", "42.0%", "35.4", "48.9", "112/400", "28.0%", "23.8", "32.6",
        "22.2%", "935/4,219 chunks", "26.8%", "46.0%",
        "+0.0177", "-0.0097", "E2: not run",
        "cadca8499b66b2e7d60a161f2021a5c5dac51ddd3a0bccea52d055cefb159de3",
        "model output throughout", "model consensus, not human validation",
        "NONE mass only",
    ]
    missing = [token for token in required if token not in html]
    assert not missing, missing
    assert RF.NO_PRICE_LINE in html
    assert RF.FOOTER_LINE in html
    assert "personal filing-reading aid for one user" in html


def test_disclosure_states_the_sentiment_estimand():
    html = RF.disclosure_html(RF.load_disclosure(), None)
    import html as _html
    assert _html.escape(RF.SENTIMENT_ESTIMAND, quote=True) in html
    for phrase in ("chunk-level label agreement", "applicability mask",
                   "model-consensus reference",
                   "not accuracy against human ground truth"):
        assert phrase in RF.SENTIMENT_ESTIMAND, phrase
    # the artifact's own caveat travels beside it, verbatim
    caveat = json.loads(RF.G2_RESULTS.read_text())["primary"]["sentiment"]["caveat"]
    assert _html.escape(caveat, quote=True) in html


def test_disclosure_attributes_the_e1_prose_numbers_to_e1():
    html = RF.disclosure_html(RF.load_disclosure(), None)
    assert "E1 TEACHER measurement" in RF.CONFIG_SENSITIVITY_SUBJECT
    assert "not a measurement of the v1.2 student" in RF.CONFIG_SENSITIVITY_SUBJECT
    assert "935/4,219 chunks" in html
    import html as _html
    assert _html.escape(RF.CONFIG_SENSITIVITY_SUBJECT, quote=True) in html
    assert _html.escape(RF.SELFID_SUBJECT, quote=True) in html
    assert "measured on E1" in RF.SELFID_SUBJECT


def test_disclosure_header_carries_the_g2_section_zero_paragraph():
    html = RF.disclosure_html(RF.load_disclosure(), None)
    paragraph = RF.read_g2_section_zero()
    assert paragraph.startswith("Do not interpret the 68.67%")
    assert "newly issued, directionless guidance" in paragraph
    assert "correctly map to NONE for direction" in paragraph
    import html as _html
    assert _html.escape(paragraph, quote=True) in html


def test_disclosure_header_is_not_collapsible():
    html = RF.disclosure_html(RF.load_disclosure(), None)
    assert html.lstrip().startswith('<section class="disclosure">')
    assert "<details" not in html
    assert "<summary" not in html


# ---------------------------------------------------------------------------
# 5b. the E1 null sentence -- CONSTANTS in the module, verified here
# ---------------------------------------------------------------------------
E1_NULL_REPORT = REPO_ROOT / "data" / "backtest_report.md"
E1_NULL_REPORT_SHA256 = (
    "a313cea839810e6c70bd996d8be7784cd23e69787eaa06735cbab420f7e772d8")


def test_e1_ic_deltas_match_the_backtest_report_they_came_from():
    """The renderer holds the two deltas as constants so no render path opens
    an outcome artifact (council Q4's kill criterion). The regex that lifted
    them out of the report lives HERE, together with that report's sha256, so
    the constants cannot drift from their source without a test failing."""
    assert RF._sha256(E1_NULL_REPORT) == E1_NULL_REPORT_SHA256, (
        "data/backtest_report.md changed; re-read the two IC deltas into "
        "report_filing.E1_IC_DELTA_RAW / E1_IC_DELTA_DEDUP and re-pin this sha")
    text = E1_NULL_REPORT.read_text()
    raw = re.search(
        r"Cross-fold mean IC delta, RAW \(text\+numeric minus numeric-only\): "
        r"(-?\d+\.\d+)", text)
    dedup = re.search(r"Cross-fold mean IC delta, DEDUPLICATED: (-?\d+\.\d+)",
                      text)
    assert raw and dedup, "the two E1 delta sentences did not parse"
    assert float(raw.group(1)) == RF.E1_IC_DELTA_RAW
    assert float(dedup.group(1)) == RF.E1_IC_DELTA_DEDUP


def test_the_module_never_names_the_backtest_report():
    assert "backtest_report" not in MODULE_SOURCE


def test_predictive_validity_is_one_replaceable_constant():
    """F6 replaces the sentence by editing exactly one constant."""
    names = [n.id for node in ast.walk(MODULE_AST)
             if isinstance(node, ast.Assign) for n in node.targets
             if isinstance(n, ast.Name) and "PREDICTIVE_VALIDITY" in n.id]
    assert names == ["PREDICTIVE_VALIDITY_TEMPLATE"]
    assert MODULE_SOURCE.count("PREDICTIVE_VALIDITY_TEMPLATE") == 2
    line = RF.PREDICTIVE_VALIDITY_TEMPLATE.format(
        raw=RF.E1_IC_DELTA_RAW, dedup=RF.E1_IC_DELTA_DEDUP)
    assert line.endswith("E2: not run")
    assert "E1 (25 companies)" in line


# ---------------------------------------------------------------------------
# 5c. the prose constants, pinned to the SENTENCES they come from
# ---------------------------------------------------------------------------
# A bare "22.2%" survives any rewording around it, so each constant is pinned
# to the exact HANDOFF clause that gives it its meaning, plus the sha of the
# line range those clauses live in.
HANDOFF_SENTENCES = [
    "`red_flags` changed on 935/4,219 chunks (22.2%)",
    "method 26.8% overall, loose method 46.0% overall",
]


def test_prose_constants_still_match_their_source_document():
    handoff = RF.PROSE_CONSTANT_SOURCE.read_text()
    for sentence in HANDOFF_SENTENCES:
        assert sentence in handoff, sentence
    # and the constants really are the numbers inside those sentences
    assert RF.CONFIG_SENSITIVITY_TEXT == "22.2%"
    assert RF.CONFIG_SENSITIVITY_COUNT == "935/4,219 chunks"
    assert RF.CONFIG_SENSITIVITY_TEXT in HANDOFF_SENTENCES[0]
    assert RF.CONFIG_SENSITIVITY_COUNT in HANDOFF_SENTENCES[0]
    assert RF.SELFID_STRICT_TEXT in HANDOFF_SENTENCES[1]
    assert RF.SELFID_LOOSE_TEXT in HANDOFF_SENTENCES[1]


def test_prose_constant_sentences_are_sha_pinned_in_their_source():
    """The sha of each sentence's own line, so an edit that keeps the number
    but changes what it is a number OF still fails."""
    expected = {
        "`red_flags` changed on 935/4,219 chunks (22.2%)":
            "4ab2e8028b7f4318420f1d396e75122f25997b5ab9bce29a3ad7fe42c83b6f85",
        "method 26.8% overall, loose method 46.0% overall":
            "ccb1831b5d96570135c10f2096b80504453436f35d9334ec87590da79bee63d3",
    }
    handoff = RF.PROSE_CONSTANT_SOURCE.read_text().splitlines()
    for sentence in HANDOFF_SENTENCES:
        lines = [ln for ln in handoff if sentence in ln]
        assert lines, sentence
        got = hashlib.sha256(lines[0].encode()).hexdigest()
        assert got == expected[sentence], (
            f"the HANDOFF line carrying {sentence!r} changed; re-read it and "
            f"re-pin: {got}")


# ---------------------------------------------------------------------------
# 6. the train-overlap banner
# ---------------------------------------------------------------------------
def _overlap(**kw):
    base = {"cik_in_train": False, "n_train_ciks": 22,
            "accession_in_train": False, "n_chunks_accession_channel": 0,
            "n_chunks_home_channel": 0, "n_chunks_text_channel": 0,
            "n_chunks": 10, "definition": FE.TRAIN_OVERLAP_DEFINITION,
            "fires": False}
    base.update(kw)
    base["fires"] = bool(base["cik_in_train"] or base["accession_in_train"]
                         or base["n_chunks_accession_channel"]
                         or base["n_chunks_text_channel"])
    return base


def test_banner_fires_for_a_training_cik():
    html = RF.disclosure_html(RF.load_disclosure(), _overlap(cik_in_train=True))
    assert "TRAIN-OVERLAP WARNING" in html
    assert "22 CIKs in the v1.2 training split" in html


def test_banner_fires_for_a_training_accession():
    html = RF.disclosure_html(RF.load_disclosure(),
                              _overlap(accession_in_train=True))
    assert "TRAIN-OVERLAP WARNING" in html


def test_banner_separates_the_home_channel_from_the_inherited_one():
    """'This passage IS a training passage' and 'the corpus also attributes
    this passage to a training filing' are different claims; the second is
    inflated by the same union-array effect containment undoes."""
    html = RF.disclosure_html(
        RF.load_disclosure(),
        _overlap(n_chunks_accession_channel=5, n_chunks_home_channel=2))
    assert "2 of 10 passages are stored under a filing that is itself in" in html
    assert "3 of 10 passages are also attributed to a training filing" in html


def test_banner_is_silent_when_nothing_overlaps():
    html = RF.disclosure_html(RF.load_disclosure(), _overlap())
    assert "TRAIN-OVERLAP" not in html


def test_overlap_definition_is_imported_from_features_e2():
    assert "TRAIN_OVERLAP_DEFINITION" in MODULE_SOURCE
    assert "Paragraph-id joins are FORBIDDEN" in FE.TRAIN_OVERLAP_DEFINITION


# ---------------------------------------------------------------------------
# 7. source scan -- the report layer imports none of the outcome layer
# ---------------------------------------------------------------------------
def test_source_scan_no_forbidden_name_appears_in_the_module():
    hits = [name for name in FORBIDDEN_NAMES
            if name in MODULE_SOURCE_NO_DOCSTRING]
    assert not hits, f"report_filing.py names a forbidden artifact: {hits}"


def test_the_docstring_names_the_outcome_layer_only_to_disclose_the_closure():
    """`controls` / `backtest` may appear in the module's prose exactly where
    it discloses the transitive closure, and nowhere else in the file."""
    paragraph = next(
        block for block in MODULE_DOCSTRING.split("\n\n")
        if "imports nothing from the price, outcome, or backtest layer" in block)
    for name in ("controls", "backtest"):
        assert MODULE_DOCSTRING.count(name) == paragraph.count(name), name
        assert name not in MODULE_SOURCE_NO_DOCSTRING


def test_source_scan_no_forbidden_import_statement():
    imported = set()
    for node in ast.walk(MODULE_AST):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not (imported & FORBIDDEN_IMPORTS), imported & FORBIDDEN_IMPORTS


def test_the_distress_column_is_never_loaded():
    assert not any("distress" in c for c in RF.LABEL_COLUMNS)
    assert not any("distress" in c for c in RF.CHUNK_COLUMNS)


def test_module_chrome_carries_no_action_vocabulary():
    """Every string literal in the module except the allow-listed disclosure
    constants and the docstrings is scanned for the refused vocabulary."""
    docstrings = set()
    for node in ast.walk(MODULE_AST):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", [])
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))

    exempt = set()
    for node in ast.walk(MODULE_AST):
        if isinstance(node, ast.Assign):
            names = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if names & DISCLOSURE_CONSTANT_NAMES:
                exempt.update(id(c) for c in ast.walk(node.value)
                              if isinstance(c, ast.Constant))

    offenders = []
    for node in ast.walk(MODULE_AST):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings and id(node) not in exempt):
            hits = word_hits(node.value, ACTION_VOCABULARY + QUANTITY_VOCABULARY)
            if hits:
                offenders.append((node.lineno, hits, node.value[:70]))
    assert not offenders, offenders


# ---------------------------------------------------------------------------
# 7b. the TRANSITIVE import closure, and what is reachable through it
# ---------------------------------------------------------------------------
FIRST_PARTY = {p.stem for p in REPO_ROOT.glob("*.py")}


def _parse(module: str) -> ast.Module:
    return ast.parse((REPO_ROOT / f"{module}.py").read_text())


def _module_imports(tree: ast.Module) -> set[str]:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module.split(".")[0])
    return {m for m in out if m in FIRST_PARTY}


def test_transitive_import_closure_is_exactly_what_is_documented():
    """`features_e2` -> `controls` -> `backtest` is REAL and is allowed: the
    section mask has to stay derived from features_e2, and that is the price.
    What may not happen is a NEW module entering the closure unnoticed."""
    seen, stack = set(), ["report_filing"]
    while stack:
        module = stack.pop()
        if module in seen:
            continue
        seen.add(module)
        stack.extend(m for m in _module_imports(_parse(module)) if m not in seen)
    assert seen == TRANSITIVE_CLOSURE, {
        "unexpected": sorted(seen - TRANSITIVE_CLOSURE),
        "missing": sorted(TRANSITIVE_CLOSURE - seen)}
    assert {"controls", "backtest"} <= seen       # documented, not accidental
    assert not (seen & {"prices_e2", "target_e2", "backtest_e2", "heads_e2",
                        "price_client", "ingest_prices"})


def _call_graph_reachable(entry_points: list[tuple[str, str]]) -> set[tuple[str, str]]:
    """Every (module, function) reachable from `entry_points` by static calls."""
    trees: dict[str, ast.Module] = {}
    funcs: dict[str, dict[str, ast.AST]] = {}
    aliases: dict[str, tuple[dict, dict]] = {}

    def load(module: str) -> bool:
        if module in trees:
            return True
        if not (REPO_ROOT / f"{module}.py").exists():
            return False
        trees[module] = _parse(module)
        defs: dict[str, ast.AST] = {}
        for node in ast.walk(trees[module]):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                defs.setdefault(node.name, node)
        funcs[module] = defs
        module_alias, symbol_alias = {}, {}
        for node in ast.walk(trees[module]):
            if isinstance(node, ast.Import):
                for a in node.names:
                    base = a.name.split(".")[0]
                    if base in FIRST_PARTY:
                        module_alias[a.asname or base] = base
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                base = node.module.split(".")[0]
                if base in FIRST_PARTY:
                    for a in node.names:
                        symbol_alias[a.asname or a.name] = (base, a.name)
        aliases[module] = (module_alias, symbol_alias)
        return True

    def calls(module: str, name: str) -> set[tuple[str, str]]:
        if not load(module):
            return set()
        node = funcs[module].get(name)
        if node is None:
            return set()
        module_alias, symbol_alias = aliases[module]
        out = set()
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            target = sub.func
            if isinstance(target, ast.Name):
                if target.id in symbol_alias:
                    out.add(symbol_alias[target.id])
                elif target.id in funcs[module]:
                    out.add((module, target.id))
            elif (isinstance(target, ast.Attribute)
                  and isinstance(target.value, ast.Name)
                  and target.value.id in module_alias):
                out.add((module_alias[target.value.id], target.attr))
        return out

    seen, stack = set(), list(entry_points)
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(x for x in calls(*cur) if x not in seen)
    return seen


def test_no_outcome_layer_function_is_reachable_from_a_render():
    """`controls` and `backtest` are LOADED. Nothing in either is CALLED from
    a render path -- an AST call graph out of `render_filing` / `render_index`
    reaches no function of either module, so no price table can be opened."""
    reachable = _call_graph_reachable([("report_filing", "render_filing"),
                                       ("report_filing", "render_index")])
    modules = {module for module, _ in reachable}
    assert modules == {"report_filing", "features_e2", "numeric_features_e2",
                       "features", "pit"}, sorted(modules)
    assert not (modules & OUTCOME_MODULES), sorted(modules & OUTCOME_MODULES)
    assert ("report_filing", "apply_containment") in reachable   # graph is live


# ---------------------------------------------------------------------------
# 8. rendered-output refusal scan
# ---------------------------------------------------------------------------
DISCLOSURE_BLOCK = re.compile(
    r'<section class="disclosure">.*?</section>', re.S)
DISCLOSURE_FOOTER = re.compile(r'<p class="footer-line">.*?</p>', re.S)
TEXT_COL = re.compile(r'(<div class="text-col">)(.*?)(</div>)', re.S)
QUOTED_PARAGRAPH = re.compile(r"<p>.*?</p>", re.S)
STYLE_BLOCK = re.compile(r"<style>.*?</style>", re.S)
H1_BLOCK = re.compile(r"<h1[^>]*>.*?</h1>", re.S)
TITLE_BLOCK = re.compile(r"<title>.*?</title>", re.S)


def chrome_only(html: str) -> str:
    """The report's OWN words.

    Removed as the ruled ALLOW-LIST: the non-collapsible disclosure block and
    the disclosure footer line. Removed because it is not the report speaking:
    the filing's quoted paragraphs -- and ONLY those, the `<p>` elements with
    no class inside a text-col. Every `<p class="small">` marker the report
    writes inside that same div stays in the scan; deleting the whole div was
    the blind spot a red-team mutation walked through. Removed because it is a
    company's own name and not vocabulary: the `<h1>` and the `<title>` (so a
    company called "Best Buy" does not fail the scan).
    """
    html = DISCLOSURE_BLOCK.sub(" ", html)
    html = DISCLOSURE_FOOTER.sub(" ", html)
    html = TEXT_COL.sub(lambda m: " " + QUOTED_PARAGRAPH.sub(" ", m.group(2)) + " ",
                        html)
    html = H1_BLOCK.sub(" ", html)
    html = TITLE_BLOCK.sub(" ", html)
    return STYLE_BLOCK.sub(" ", html)


def _synthetic_page(index, occ, texts, sections, prior_sections) -> str:
    frame, rendered, stats = _contained(index, occ, texts, sections, HERE)
    prior_frame, prior_rendered, _ = _contained(index, occ, texts,
                                                prior_sections, PRIOR)
    prior_row = pd.Series({"accession_number": PRIOR, "form": "10-K",
                           "filing_date": "2023-11-03"})
    body = [
        RF.disclosure_html(RF.load_disclosure(), _overlap()),
        "<h1>Synthetic Industries Inc — 10-K filed 2024-11-01</h1>",
        RF.sections_table_html(frame, pd.DataFrame(), HERE),
        RF.fundamentals_html(
            [{"family": "assets", "label": "Total assets",
              "state": "unresolved", "detail": "UNRESOLVED for this company"},
             {"family": "revenue", "label": "Revenue", "state": "resolved",
              "value": 1.0e9, "unit": "USD", "concept": "Revenues",
              "period_end": "2024-09-28", "filed": "2024-11-01",
              "form": "10-K", "accession": HERE, "days_stale": 3}],
            "2024-11-01"),
        RF.diff_html(RF.diff_vs_prior(frame, prior_frame), prior_row, rendered,
                     prior_rendered, HERE, "note"),
    ]
    body.append("<h2>The filing, section by section</h2>")
    for row in frame.itertuples():
        body.append(RF.passage_html(row, rendered[int(row.row_index)], HERE,
                                    "note"))
    body.append(f'<p class="footer-line">{RF.esc(RF.FOOTER_LINE)}</p>')
    return RF.page("Synthetic Industries Inc 10-K 2024-11-01", "".join(body))


@pytest.fixture
def page(index, occ, texts, sections, prior_sections) -> str:
    return _synthetic_page(index, occ, texts, sections, prior_sections)


def test_rendered_chrome_contains_no_refused_vocabulary(page):
    hits = word_hits(chrome_only(page))
    assert not hits, hits


def test_the_chrome_scan_still_sees_the_reports_own_markers(page):
    """The regression the red-team mutation exposed: markers live inside
    text-col and must NOT be deleted with the quoted paragraphs."""
    chrome = chrome_only(page)
    assert "This passage appears in" in chrome
    assert "Deduplicated into an earlier filing" in chrome
    assert "Partial: 1 of 2 paragraphs" in chrome
    # ...while the filing's own words are gone
    assert PARAGRAPHS["C-mda-new"][0] not in chrome
    assert PARAGRAPHS["C-rf-keep"][0] not in chrome


def test_the_chrome_scan_catches_a_refused_line_emitted_inside_text_col(
        index, occ, texts, sections, prior_sections, monkeypatch):
    """The red-team's own mutation, as a standing test: a report-voiced line
    carrying a refused quantity and a refused market claim, emitted inside the
    text column, must fail the scan."""
    original = RF.passage_html

    def mutated(row, text, accession, note, open_by_default=True):
        html = original(row, text, accession, note, open_by_default)
        injected = ('<p class="small">' + "sc" + "ore" + " 9.1 — " + "st"
                    + "ock" + " up since filing</p>")
        return html.replace('<div class="text-col">',
                            '<div class="text-col">' + injected, 1)

    monkeypatch.setattr(RF, "passage_html", mutated)
    hits = word_hits(chrome_only(
        _synthetic_page(index, occ, texts, sections, prior_sections)))
    assert "score" in hits and "stock" in hits


def test_html_tag_names_are_whitelisted_by_tag_not_by_word():
    assert word_hits("<summary>section</summary>") == []
    assert word_hits("<p>an executive summary of the filing</p>") == ["summary"]
    assert word_hits("<notatag>fine</notatag>") == []


def test_a_company_name_in_the_h1_or_title_is_not_scanned_as_vocabulary():
    """L2.2 may be asked for any ticker. A company whose NAME contains a word
    on the refusal list -- "Best Buy", "Dollar General", "Advance Auto Parts"
    -- must not fail the scan for being called what it is called. The name
    lives in the <h1> and the <title>; both are excluded. The same word in the
    report's own prose still fails."""
    heading = ('<title>Best Buy Co Inc 10-K 2024-02-01</title>'
               '<h1>Best Buy Co Inc — 10-K filed 2024-02-01</h1>'
               '<p class="small">CIK 764478 · accession 0000764478-24-000012</p>')
    assert word_hits(chrome_only(heading)) == []
    assert word_hits(chrome_only('<p class="small">buy this filing</p>')) == ["buy"]


def test_rendered_page_has_no_javascript(page):
    assert "<script" not in page.lower()
    assert "javascript:" not in page.lower()
    assert not re.search(r"\bon(click|load|change|input|submit)\s*=", page, re.I)


def test_rendered_page_never_shows_the_excluded_label(page):
    assert "distress" not in page.lower()


# The seven issuers whose words really did render on the Apple FY2024 10-K
# page before the containment filter existed.
LEAKING_COMPANIES = ["MICRON", "CELGENE", "STRYKER", "QUALCOMM", "Palo Alto",
                     "LAM RESEARCH", "CADENCE"]


def test_rendered_page_has_no_cross_company_table(page):
    """Every table on the page belongs to ONE filing of ONE company: no table
    header names a second company key, and no other issuer's name appears
    anywhere on the page -- not in the chrome, not in a marker, not in the
    quoted text."""
    for header in re.findall(r"<th>(.*?)</th>", page):
        assert word_hits(header, QUANTITY_VOCABULARY) == [], header
    assert "Elsewhere Holdings" not in page


def quoted_paragraphs(html: str) -> list[str]:
    """Every unclassed `<p>` inside a text-col: the page's QUOTED words."""
    out = []
    for _, body, _ in TEXT_COL.findall(html):
        out.extend(unescape(re.sub(r"<[^>]+>", "", p))
                   for p in QUOTED_PARAGRAPH.findall(body))
    return out


SECTION_BY_SECTION = "<h2>The filing, section by section</h2>"


def test_rendered_html_quotes_only_this_filings_own_words(page, sections,
                                                          prior_sections):
    """The containment property asserted on the HTML, not on the frame: an
    unclassed `<p>` inside a text-col is a FILING speaking, so every one of
    them must be inside this filing's section text -- or, in the REMOVED block
    of the diff, the prior filing's. Below the section-by-section heading only
    this filing's text is allowed. This is what stops a line injected at
    HTML-assembly time from passing itself off as quoted text."""
    here = " ".join(sections.values())
    both = here + " " + " ".join(prior_sections.values())

    quoted = quoted_paragraphs(page)
    assert quoted
    for paragraph in quoted:
        assert RF.collapse_whitespace(paragraph) in both, paragraph[:120]

    _, marker, tail = page.partition(SECTION_BY_SECTION)
    assert marker
    own = quoted_paragraphs(tail)
    assert own
    for paragraph in own:
        assert RF.collapse_whitespace(paragraph) in here, paragraph[:120]


def test_disclosure_block_is_the_only_allow_listed_region(page):
    assert len(DISCLOSURE_BLOCK.findall(page)) == 1
    assert "recommendation" in DISCLOSURE_BLOCK.findall(page)[0]
    # the footer line is the ONLY other allow-listed region, and it is the
    # ruled footer sentence verbatim -- nothing else hides behind the allow-list
    for footer in DISCLOSURE_FOOTER.findall(page):
        assert RF.FOOTER_LINE in footer
        assert len(re.sub(r"<[^>]+>", "", footer).strip()) == len(RF.FOOTER_LINE)


# ---------------------------------------------------------------------------
# 9. determinism
# ---------------------------------------------------------------------------
def test_synthetic_render_is_byte_identical(index, occ, texts, sections,
                                            prior_sections):
    a = _synthetic_page(index, occ, texts, sections, prior_sections)
    b = _synthetic_page(index, occ, texts, sections, prior_sections)
    assert a == b


def test_rendered_page_carries_no_wall_clock_timestamp(page):
    assert not re.search(r"\b20\d\d-\d\d-\d\dT\d\d:\d\d", page)
    assert "generated" not in page.lower()


# ---------------------------------------------------------------------------
# 10. small units
# ---------------------------------------------------------------------------
def test_first_sentence_splits_at_the_first_full_stop():
    assert RF.first_sentence("One. Two. Three.") == "One."
    assert RF.first_sentence("No split here") == "No split here"


def test_format_amount_scales_usd_and_leaves_other_units_alone():
    assert RF.format_amount(3.6498e11, "USD") == "364.98 bn USD"
    assert RF.format_amount(2.4, "USD/shares") == "2.4000 USD/shares"


def test_unresolved_fundamental_is_shown_as_unresolved():
    html = RF.fundamentals_html(
        [{"family": "equity", "label": "Total equity", "state": "unresolved",
          "detail": "UNRESOLVED for this company"}], "2024-11-01")
    assert "unresolved" in html
    assert "UNRESOLVED for this company" in html
    assert "only facts already filed by that date are visible" in html


def test_restatement_provenance_is_visible():
    html = RF.fundamentals_html(
        [{"family": "assets", "label": "Total assets", "state": "resolved",
          "value": 1.0e9, "unit": "USD", "concept": "Assets",
          "period_end": "2023-12-31", "filed": "2024-05-01", "form": "10-Q",
          "accession": "X", "days_stale": 10}], "2024-11-01")
    assert "latest filed as of 2024-11-01: 2024-05-01" in html


def test_occurrence_map_includes_the_home_filing(index):
    occ = RF.occurrence_map(index)
    for row in index.itertuples():
        assert int(row.row_index) in occ[row.home_accession_number]


def test_positional_contract_is_asserted(index):
    RF.assert_positional(index)
    shuffled = index.copy()
    shuffled["row_index"] = shuffled.row_index.to_numpy()[::-1]
    with pytest.raises(RuntimeError):
        RF.assert_positional(shuffled)


def test_section_records_drops_the_text_column():
    frame = pd.DataFrame([{c: "x" for c in RF.SECTION_COLUMNS}])
    assert "text" not in RF.section_records(frame).columns
    assert RF.section_texts(frame) == {"x": "x"}


# ---------------------------------------------------------------------------
# 11. the file-open guard -- no outcome artifact is opened at render time
# ---------------------------------------------------------------------------
class OpenRecorder:
    """Every path a render opens, whatever reader opens it."""

    def __init__(self, monkeypatch):
        self.paths: list[str] = []
        mp = monkeypatch

        def note(target):
            # A Path's `.name` is its BASENAME -- only file OBJECTS get the
            # attribute treatment, or every path collapses to its last segment.
            if isinstance(target, (str, Path)):
                self.paths.append(str(target))
            else:
                self.paths.append(str(getattr(target, "name", target)))

        real_open = builtins.open

        def traced_open(file, *a, **kw):
            note(file)
            return real_open(file, *a, **kw)
        mp.setattr(builtins, "open", traced_open)

        for module, attr in ((pd, "read_parquet"), (pd, "read_csv"),
                             (pq, "read_table"), (sqlite3, "connect")):
            real = getattr(module, attr)

            def traced(path, *a, _real=real, **kw):
                note(path)
                return _real(path, *a, **kw)
            mp.setattr(module, attr, traced)

        real_pf = pq.ParquetFile

        def traced_pf(path, *a, **kw):
            note(path)
            return real_pf(path, *a, **kw)
        mp.setattr(pq, "ParquetFile", traced_pf)

        for attr in ("read_text", "read_bytes"):
            real = getattr(Path, attr)

            def traced_path(self, *a, _real=real, **kw):
                note(self)
                return _real(self, *a, **kw)
            mp.setattr(Path, attr, traced_path)

    def normalised(self) -> list[str]:
        out = []
        for raw in self.paths:
            cleaned = raw.replace("file:", "").split("?")[0]
            try:
                cleaned = str(Path(cleaned).resolve().relative_to(REPO_ROOT))
            except (ValueError, OSError):
                continue
            out.append(cleaned)
        return out


# ---------------------------------------------------------------------------
# 12. real-data smoke -- slow
# ---------------------------------------------------------------------------
AAPL_CIK = 320193
AAPL_10K = "0000320193-24-000123"      # FY2024 10-K, filed 2024-11-01
AAPL_8K = "0000320193-25-000007"       # Q1 FY2025 earnings 8-K, filed 2025-01-30

corpus_present = pytest.mark.skipif(
    not (RF.CHUNKS_PATH.exists() and RF.LABELS_PATH.exists()),
    reason="F4 corpus not on this machine")


def _corpus():
    index = RF.load_cache(verbose=False)
    return index, RF.occurrence_map(index)


@pytest.mark.slow
@corpus_present
@pytest.mark.parametrize("accession", [AAPL_10K, AAPL_8K])
def test_real_filing_renders_under_ten_seconds(tmp_path, accession):
    index, occ = _corpus()
    started = time.time()
    out = RF.render_filing(index, occ, AAPL_CIK, accession, tmp_path)
    elapsed = time.time() - started
    html = out.read_text()
    assert elapsed < 10.0, f"{accession} took {elapsed:.1f}s"
    assert "Apple Inc." in html
    assert accession in html
    assert RF.FOOTER_LINE in html
    assert "What changed since the prior" in html
    assert DISCLOSURE_BLOCK.search(html)


@pytest.mark.slow
@corpus_present
def test_real_render_is_byte_identical_on_a_second_run(tmp_path):
    index, occ = _corpus()
    first = RF.render_filing(index, occ, AAPL_CIK, AAPL_8K, tmp_path / "a")
    second = RF.render_filing(index, occ, AAPL_CIK, AAPL_8K, tmp_path / "b")
    assert (hashlib.sha256(first.read_bytes()).hexdigest()
            == hashlib.sha256(second.read_bytes()).hexdigest())


@pytest.mark.slow
@corpus_present
@pytest.mark.parametrize("accession", [AAPL_10K, AAPL_8K])
def test_real_every_rendered_paragraph_is_inside_the_filing(accession):
    """The containment property on real data: not one paragraph on the page is
    absent from THIS filing's own extracted section text."""
    index, occ = _corpus()
    sections = RF.section_texts(RF.filing_sections(accession))
    frame, rendered, _, stats = RF.contained_filing(index, occ, accession)
    assert len(frame) > 0
    checked = 0
    for row in frame.itertuples():
        for paragraph in RF.split_paragraphs(rendered[int(row.row_index)]):
            assert RF.collapse_whitespace(paragraph) in sections[row.section_type]
            checked += 1
    assert checked == stats["paragraphs_rendered"] > 0
    # and the rendered word count now tracks what the extractor recorded
    assert stats["words_rendered"] <= stats["section_words"] * 1.05
    assert stats["words_rendered"] >= stats["section_words"] * 0.80


@pytest.mark.slow
@corpus_present
@pytest.mark.parametrize("accession", [AAPL_10K, AAPL_8K])
def test_real_rendered_html_quotes_only_this_filings_own_words(tmp_path, accession):
    """The same property on the real pages: every quoted paragraph in the
    rendered HTML is inside THIS filing's extracted section text."""
    index, occ = _corpus()
    html = RF.render_filing(index, occ, AAPL_CIK, accession, tmp_path).read_text()
    here = " ".join(RF.section_texts(RF.filing_sections(accession)).values())
    prior = RF.prior_same_form(RF.company_filings(AAPL_CIK, occ), accession)
    both = here + " " + " ".join(
        RF.section_texts(RF.filing_sections(prior.accession_number)).values())

    quoted = quoted_paragraphs(html)
    assert len(quoted) > 20
    for paragraph in quoted:
        assert RF.collapse_whitespace(paragraph) in both, paragraph[:160]

    _, marker, tail = html.partition(SECTION_BY_SECTION)
    assert marker
    own = quoted_paragraphs(tail)
    assert len(own) > 20
    for paragraph in own:
        assert RF.collapse_whitespace(paragraph) in here, paragraph[:160]


@pytest.mark.slow
@corpus_present
def test_real_apple_10k_names_no_other_issuer(tmp_path):
    """Seven issuers' words rendered under Apple's name before containment.
    None of their names may appear anywhere on the page now."""
    index, occ = _corpus()
    html = RF.render_filing(index, occ, AAPL_CIK, AAPL_10K, tmp_path).read_text()
    present = [name for name in LEAKING_COMPANIES
               if name.lower() in html.lower()]
    assert not present, present


@pytest.mark.slow
@corpus_present
def test_real_report_chrome_carries_no_refused_vocabulary(tmp_path):
    index, occ = _corpus()
    out = RF.render_filing(index, occ, AAPL_CIK, AAPL_10K, tmp_path)
    hits = word_hits(chrome_only(out.read_text()))
    assert not hits, hits


@pytest.mark.slow
@corpus_present
def test_real_index_page_has_no_label_derived_column(tmp_path):
    index, occ = _corpus()
    out = RF.render_index(index, occ, AAPL_CIK, tmp_path)
    html = out.read_text()
    headers = re.findall(r"<th>(.*?)</th>", html)
    assert headers == ["Form", "Filed", "Accession", "Sections", "Passages"]
    chrome = chrome_only(html)
    for value in ("POSITIVE", "NEGATIVE", "RAISED", "DEMAND_WEAKNESS"):
        assert value not in chrome
    assert not word_hits(chrome)


@pytest.mark.slow
@corpus_present
def test_real_index_page_skips_filings_with_no_homed_passage(tmp_path):
    """A filing whose every paragraph was deduplicated into an earlier one is
    counted in a footnote, not linked."""
    index, occ = _corpus()
    html = RF.render_index(index, occ, AAPL_CIK, tmp_path).read_text()
    filings = RF.company_filings(AAPL_CIK, occ)
    homed = index.home_accession_number.value_counts()
    linked = {a for a in filings.accession_number if int(homed.get(a, 0)) > 0}
    skipped = len(filings) - len(linked)
    assert re.search(rf"{skipped} further labeled filing", html)
    for accession in filings.accession_number:
        assert (f'href="{accession}.html"' in html) is (accession in linked)


@pytest.mark.slow
@corpus_present
def test_real_index_page_fires_the_train_overlap_banner_for_a_training_cik(tmp_path):
    """The index links to reports; if the company is one of the 22 training
    CIKs the index has to say so too."""
    index, occ = _corpus()
    train = pd.read_parquet(RF.TRAIN_SPLIT_PATH, columns=["home_cik"])
    train_ciks = sorted(int(c) for c in train.home_cik.unique())
    assert len(train_ciks) == 22

    overlap = RF.train_cik_overlap(AAPL_CIK)
    assert overlap["n_train_ciks"] == 22
    html = RF.render_index(index, occ, AAPL_CIK, tmp_path).read_text()
    assert ("TRAIN-OVERLAP WARNING" in html) is overlap["cik_in_train"]

    training_cik = train_ciks[0]
    fires = RF.disclosure_html(RF.load_disclosure(),
                               RF.train_cik_overlap(training_cik))
    assert "TRAIN-OVERLAP WARNING" in fires
    assert "22 CIKs in the v1.2 training split" in fires


@pytest.mark.slow
@corpus_present
def test_real_masks_hold_on_the_corpus():
    index, occ = _corpus()
    frame, _, _, _ = RF.contained_filing(index, occ, AAPL_10K)
    rf_rows = frame[frame.section_type == "RISK_FACTORS"]
    assert len(rf_rows) > 0
    assert rf_rows.sentiment_masked.all()
    assert rf_rows.guidance_masked.all()
    mda = frame[frame.section_type == "MDA"]
    assert mda.guidance_masked.all()
    assert not mda.sentiment_masked.any()


@pytest.mark.slow
@corpus_present
def test_real_ticker_resolves_to_the_expected_cik():
    assert RF.resolve_ticker("AAPL") == AAPL_CIK


@pytest.mark.slow
@corpus_present
@pytest.mark.parametrize("what", ["filing", "index"])
def test_render_opens_no_outcome_artifact(tmp_path, monkeypatch, what):
    """The council's kill criterion, enforced at RUNTIME rather than by
    reading the source: every file the render opens is listed, and no price
    table, target table, F5 result or backtest report is among them."""
    index, occ = _corpus()
    recorder = OpenRecorder(monkeypatch)
    if what == "filing":
        RF.render_filing(index, occ, AAPL_CIK, AAPL_10K, tmp_path)
    else:
        RF.render_index(index, occ, AAPL_CIK, tmp_path)
    opened = recorder.normalised()
    assert opened, "the recorder saw nothing; the patching is broken"

    forbidden = sorted({p for p in opened
                        if any(f.strip("/") in p for f in FORBIDDEN_ARTIFACT_FRAGMENTS)})
    assert not forbidden, forbidden

    unexpected = sorted({p for p in opened
                         if not any(a in p for a in ALLOWED_ARTIFACT_FRAGMENTS)
                         and not p.startswith("data/app/reports")})
    assert not unexpected, unexpected
