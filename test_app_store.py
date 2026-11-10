"""test_app_store.py -- L2.2 plumbing: ingest_one, label_filing, --store.

SCOPE, stated first because PRODUCT_PLAN §0.5 is binding: **these fixtures are
synthetic and they test PLUMBING ONLY.** Not one number anybody reads comes
from them. Whether the pipeline works is settled by
`data/app/status/L2_2_external_companies.md` -- ten real companies the builder
did not choose, every failure recorded. What this file pins is the machinery
underneath that run:

  * the store's three tables are written in the SAME arrow schemas as
    data/filings_e2_v2.parquet, data/f4/chunks_v1.parquet and
    data/f4/labels_e2_v1.parquet -- asserted against the real files' schemas,
    so "same schema" is a comparison and not a claim;
  * the store's sqlite answers `report_filing`'s own two queries;
  * every ingest failure is RECORDED rather than dropped;
  * the labeler refuses on a wrong adapter, on a failed canary, and while a
    campaign is alive;
  * the prompt input carries the passage and nothing identifying;
  * `--store` redirects the seven readers and NOTHING else, adds exactly one
    disclosure line, and leaves every refusal green;
  * the fundamentals a store ingests for itself (P1a.2) are parsed and
    classified by `ingest_fundamentals`'s own code, keep every filed
    occurrence, resolve point-in-time through `pit.value_as_of`, never resolve
    an UNRESOLVED family, and never write F2's committed records.

The synthetic store is built by the REAL code: `build_f4_chunks.build` chunks
it, `label_filing.write_labels` writes its labels through
`label_e2.output_schema` and `label_e2.f4_label_row`. Only the model's answers
are canned -- there is no GPU in a test.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import pytest

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "finetune"))

import build_f4_chunks as BFC  # noqa: E402
import ingest_one as IO  # noqa: E402
import label_e2 as L2  # noqa: E402
import label_filing as LF  # noqa: E402
import report_filing as RF  # noqa: E402

E2_SECTIONS = REPO_ROOT / "data" / "filings_e2_v2.parquet"
E2_FUNDAMENTALS = REPO_ROOT / "data" / "fundamentals_e2.parquet"
F2_RESOLUTION = REPO_ROOT / "data" / "f2" / "concept_resolution.csv"
F4_CHUNKS = REPO_ROOT / "data" / "f4" / "chunks_v1.parquet"
F4_LABELS = REPO_ROOT / "data" / "f4" / "labels_e2_v1.parquet"

corpus_present = pytest.mark.skipif(
    not (E2_SECTIONS.exists() and F4_CHUNKS.exists() and F4_LABELS.exists()),
    reason="the research corpus is not on this machine")


# ---------------------------------------------------------------------------
# no test may leak a store into the next one
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _no_store_leaks():
    RF.use_store(None)
    yield
    RF.use_store(None)


# ---------------------------------------------------------------------------
# synthetic fixtures
# ---------------------------------------------------------------------------
WORDS = ("the company recorded higher net revenue in the period while gross "
         "margin narrowed on freight and tariff costs management continues to "
         "invest in direct to consumer channels and expects the wholesale "
         "channel to remain uneven across regions during the remainder of the "
         "fiscal year as inventory positions normalise").split()


def paragraph(seed: int, n_words: int = 60) -> str:
    """A >=40-word line, so `reflow_v1` keeps it as its own paragraph."""
    return " ".join(WORDS[(seed + i) % len(WORDS)] for i in range(n_words)) + f" p{seed}."


def section_text(seeds) -> str:
    return "\n".join(paragraph(s) for s in seeds)


def section_row(accession: str, form: str, section_type: str, filing_date: str,
                text: str, cik: int = 5550001, name: str = "SYNTHETIC CO") -> dict:
    return {
        "cik": cik, "company_name": name, "sector": IO.EXTERNAL_SECTOR,
        "stratum": IO.EXTERNAL_STRATUM, "accession_number": accession,
        "form": form, "filing_date": filing_date, "report_date": filing_date,
        "section_type": section_type, "text": text,
        "word_count": len(text.split()), "char_count": len(text),
        "n_prose_paragraphs": len(text.split("\n")), "prose_word_share": 1.0,
        "extraction_method": "anchor", "extraction_confidence": "high",
        "extraction_status": "OK", "flags": [], "source_document": "doc.htm",
        "below_length_floor": False, "population_gate": None,
        "quarter_cell_size": None, "results_signature_present": None,
        "item202_prefix_chars": None, "item202_block_words": None,
        "supplemental_tail_share": None, "stub_language_present": False,
        "ctrl_ratio": 0.0, "eng_word_share": 0.9,
        "extractor_version": "test", "run_id": "test",
    }


CIK = 5550001
ACC_NOW = "0005550001-26-000002"
ACC_PRIOR = "0005550001-25-000001"
ACC_8K = "0005550001-26-000003"


def synthetic_sections() -> pd.DataFrame:
    """Two 10-Ks and an earnings 8-K.

    The prior 10-K SHARES paragraphs 1-3 with the current one and carries three
    of its own (30-32), so the chunker really deduplicates and containment has
    a right answer that is not a restatement of the code. Its RISK_FACTORS
    section (50-53) is the one block the current filing does not carry at all,
    and it is the only way a whole CHUNK can be REMOVED: the chunker packs a
    section's new paragraphs together, so 30-32 ride inside a chunk the current
    filing also sources (through 1-3) and are dropped by containment rather
    than by the chunk-level diff.
    """
    rows = [
        section_row(ACC_NOW, "10-K", "MDA", "2026-02-10",
                    section_text([1, 2, 3, 10, 11, 12])),
        section_row(ACC_NOW, "10-K", "RISK_FACTORS", "2026-02-10",
                    section_text([20, 21, 22, 23])),
        section_row(ACC_PRIOR, "10-K", "MDA", "2025-02-11",
                    section_text([1, 2, 3, 30, 31, 32])),
        section_row(ACC_PRIOR, "10-K", "RISK_FACTORS", "2025-02-11",
                    section_text([50, 51, 52, 53])),
        section_row(ACC_8K, "8-K", "EX99_PRESS_RELEASE", "2026-02-09",
                    section_text([40, 41, 42, 43])),
    ]
    return IO.EX._frame(rows, IO.EX.OUTPUT_COLUMNS)


def filing_rows() -> list[dict]:
    return [
        {"accession_number": ACC_NOW, "cik": CIK, "ticker": "SYN", "form": "10-K",
         "filing_date": "2026-02-10", "report_date": "2025-12-31",
         "acceptance_datetime": "2026-02-10T16:31:00.000Z",
         "primary_document": "syn-20251231.htm", "items": None,
         "has_earnings_item": False, "company_name": "SYNTHETIC CO"},
        {"accession_number": ACC_PRIOR, "cik": CIK, "ticker": "SYN", "form": "10-K",
         "filing_date": "2025-02-11", "report_date": "2024-12-31",
         "acceptance_datetime": "2025-02-11T16:05:00.000Z",
         "primary_document": "syn-20241231.htm", "items": None,
         "has_earnings_item": False, "company_name": "SYNTHETIC CO"},
        {"accession_number": ACC_8K, "cik": CIK, "ticker": "SYN", "form": "8-K",
         "filing_date": "2026-02-09", "report_date": "2025-12-31",
         "acceptance_datetime": "2026-02-09T21:02:00.000Z",
         "primary_document": "syn-8k.htm", "items": "2.02,9.01",
         "has_earnings_item": True, "company_name": "SYNTHETIC CO",
         "earnings_doc_filename": "ex991.htm",
         "earnings_doc_section_type": "EX99_PRESS_RELEASE",
         "earnings_doc_selection_confidence": "high",
         "earnings_doc_relative_path":
             f"/Archives/edgar/data/{CIK}/{ACC_8K.replace('-', '')}/ex991.htm"},
    ]


def canned_answer(chunk_id: str, i: int, omit_guidance: bool = False) -> dict:
    """One journal record. The row the fixture marks `omit_guidance` leaves
    guidance_direction OUT on purpose, so the owner-ruled missing->NONE rule
    and its audit flag are exercised. The fixture picks that row by
    guidance_applicable, never by position -- a changed chunk order must not
    quietly move the omission onto a section where imputation is forbidden."""
    payload = {"sentiment": ["POSITIVE", "NEUTRAL", "NEGATIVE"][i % 3],
               "red_flags": []}
    if not omit_guidance:
        payload["guidance_direction"] = "NONE"
    return {"chunk_id": chunk_id, "segment_id": "test",
            "raw_output": json.dumps(payload),
            "prompt_input_sha256": "x" * 64, "prompt_sha256": "y" * 64,
            "prompt_tokens": 400, "generation_tokens": 30,
            "finish_reason": "stop", "latency_s": 1.0,
            "passage_was_head_truncated": False, "passage_chars_kept": 900,
            "generated_utc": "2026-09-11T00:00:00Z"}


@pytest.fixture(scope="module")
def store(tmp_path_factory) -> Path:
    """A complete synthetic store, built by the production code."""
    root = tmp_path_factory.mktemp("store") / str(CIK)
    root.mkdir(parents=True)
    IO.write_sections(synthetic_sections(), root / "sections.parquet")
    IO.write_metadata_db(root / "metadata.db", CIK, "SYNTHETIC CO", "SYN",
                         filing_rows())
    IO.build_chunks(root / "sections.parquet", root / "chunks.parquet")

    built = pq.read_table(root / "chunks.parquet",
                          columns=["chunk_id", "guidance_applicable"])
    chunk_ids = built["chunk_id"].to_pylist()
    applicable = built["guidance_applicable"].to_pylist()
    omit_at = applicable.index(True)      # the one row that omits the key
    with open(root / LF.JOURNAL_NAME, "w") as fh:
        for i, cid in enumerate(chunk_ids):
            fh.write(json.dumps(
                canned_answer(cid, i, omit_guidance=(i == omit_at))) + "\n")
    LF.write_labels(root)
    (root / "manifest.json").write_text(json.dumps(
        {"cik": CIK, "ticker": "SYN", "company_name": "SYNTHETIC CO",
         "store_version": IO.STORE_VERSION}) + "\n")
    return root


# ===========================================================================
# ingest_one -- selection, paths, failure recording
# ===========================================================================
def _history() -> list[dict]:
    return [
        {"accession_number": "a-10k-new", "form": "10-K", "filing_date": "2026-02-10",
         "has_earnings_item": False},
        {"accession_number": "a-10k-old", "form": "10-K", "filing_date": "2025-02-11",
         "has_earnings_item": False},
        {"accession_number": "a-10q", "form": "10-Q", "filing_date": "2026-05-01",
         "has_earnings_item": False},
        {"accession_number": "a-8k-earn", "form": "8-K", "filing_date": "2026-04-28",
         "has_earnings_item": True},
        {"accession_number": "a-8k-other", "form": "8-K", "filing_date": "2026-06-01",
         "has_earnings_item": False},
    ]


def test_select_filings_takes_the_newest_of_each_form():
    picked = {r["accession_number"] for r in IO.select_filings(_history(), per_form=1)}
    assert picked == {"a-10k-new", "a-10q", "a-8k-earn"}


def test_select_filings_never_takes_a_non_earnings_8k():
    picked = [r["accession_number"] for r in IO.select_filings(_history(), per_form=5)]
    assert "a-8k-other" not in picked, "an 8-K without item 2.02 is not an earnings 8-K"


def test_select_filings_per_form_two_reaches_the_prior_filing():
    picked = [r["accession_number"] for r in IO.select_filings(_history(), per_form=2)]
    assert "a-10k-old" in picked, "per-form 2 is what gives the report a prior filing"


def test_select_filings_is_order_independent():
    rows = _history()
    a = IO.select_filings(list(reversed(rows)), per_form=2)
    b = IO.select_filings(rows, per_form=2)
    assert [r["accession_number"] for r in a] == [r["accession_number"] for r in b]


def test_document_paths_for_a_periodic_filing_is_the_primary_document():
    row = filing_rows()[0]
    assert IO.document_paths(row) == [
        f"/Archives/edgar/data/{CIK}/{ACC_NOW.replace('-', '')}/syn-20251231.htm"]


def test_document_paths_for_an_8k_is_the_selected_earnings_document():
    assert IO.document_paths(filing_rows()[2]) == [
        f"/Archives/edgar/data/{CIK}/{ACC_8K.replace('-', '')}/ex991.htm"]


def test_document_paths_is_empty_when_the_earnings_document_never_resolved():
    row = dict(filing_rows()[2])
    row.pop("earnings_doc_filename")
    assert IO.document_paths(row) == []


def test_an_unresolved_earnings_document_is_recorded_not_dropped():
    """PRODUCT_PLAN §0.5: failures are recorded, never filtered out."""
    row = dict(filing_rows()[2])
    for key in ("earnings_doc_filename", "earnings_doc_section_type",
                "earnings_doc_relative_path"):
        row.pop(key, None)
    row["earnings_doc_unresolved_reason"] = "no EX-99.x and no confirmable candidate"
    frame, audit = IO.extract_sections([row])
    assert frame.empty
    assert len(audit) == 1
    assert audit[0]["reason_code"] == "earnings_doc_unresolved"
    assert audit[0]["accession_number"] == ACC_8K
    assert "confirmable" in audit[0]["note"]


def test_a_cache_miss_becomes_a_named_audit_row_not_an_exception():
    row = dict(filing_rows()[0])
    row["primary_document"] = "this-document-was-never-fetched.htm"
    frame, audit = IO.extract_sections([row])
    assert frame.empty
    assert {a["reason_code"] for a in audit} == {"cache_miss"}
    assert len(audit) == 2, "both periodic sections are attempted and both audited"


# ===========================================================================
# ingest_one -- the APP-LANE filer-dialect normalizer (L2.4)
# ===========================================================================
# CBKM (CIK 1006830) is the real company that forced this: its filing agent
# writes `Item&#160;7&#8212;Management&#8217;s Discussion` in the TOC and
# `<b>Item</b>&#160;<b>7</b>&#8212;<b>Management</b>&#8217;<b>s ...</b>` in the
# body, and neither of `extract.py`'s locators can match either spelling. The
# fix normalizes the HTML the app lane READS; `extract.py` is untouched, and
# the retry only ever runs where the frozen extractor already produced nothing.
CBKM_BODY_HEADING = (
    '<p><b>Item</b>&#160;<b>7</b>&#8212;<b>Management</b>&#8217;'
    '<b>s Discussion and Analysis of Financial Condition</b></p>')
CBKM_TOC_ROW = (
    '<td><p>Item&#160;1A&#8212;Risk Factors</p></td>')


def test_the_dialect_normalizer_repairs_the_two_things_it_names():
    body = IO.normalize_filer_dialect(CBKM_BODY_HEADING)
    assert "Item 7. Management’s Discussion and Analysis" in body
    assert "<b>" not in body and "</b>" not in body
    assert IO.EX._heading_pattern("7", r"management.?s\s+discussion").search(
        IO.EX.html_fragment_to_text(body)), (
        "the whole point: extract.py's own pattern now matches the heading")

    toc = IO.normalize_filer_dialect(CBKM_TOC_ROW)
    assert "Item 1A. Risk Factors" in toc
    assert IO.EX._heading_pattern("1A", r"risk\s+factors").search(
        IO.EX.html_fragment_to_text(toc))


def test_the_normalizer_leaves_prose_and_escaped_markup_alone():
    """It rewrites an item SEPARATOR, not every dash, and it must never invent
    a tag out of a filing's own escaped angle brackets."""
    prose = "revenue &#8212; excluding freight &#8212; rose, per &lt;b&gt; note 4"
    assert IO.normalize_filer_dialect(prose) == (
        "revenue — excluding freight — rose, per &lt;b&gt; note 4")
    assert "<b>" not in IO.normalize_filer_dialect(prose)
    # a table cell is structure, not inline formatting: it stays
    assert "<td>" in IO.normalize_filer_dialect("<td><span>x</span></td>")


def _attempt(section: str, reason: str, text: str = ""):
    return (section,
            IO.EX.ExtractionResult(text=text, method="none", confidence="low",
                                   form="10-K", section_type=section,
                                   flags=[reason]),
            "doc.htm")


def test_a_section_the_frozen_extractor_located_is_never_retried(monkeypatch):
    """The retry exists to rescue FAILURES. A located section -- even a
    FLAGGED, below-floor one -- keeps exactly the row extract.py wrote."""
    called = []
    monkeypatch.setattr(IO.EX, "extract_filing",
                        lambda *a, **k: called.append(a) or [])
    attempts = [_attempt("MDA", "below_length_floor", "short but real"),
                _attempt("RISK_FACTORS", "heading_regex_fallback", "text")]
    out = IO.retry_failed_on_normalized_html(attempts, {}, {})
    assert out is attempts and not called


def test_a_cache_miss_is_not_a_dialect_problem_and_is_not_retried(monkeypatch):
    called = []
    monkeypatch.setattr(IO.EX, "extract_filing",
                        lambda *a, **k: called.append(a) or [])
    out = IO.retry_failed_on_normalized_html(
        [_attempt("MDA", "cache_miss")], {}, {})
    assert not called and out[0][1].reason_code == "cache_miss"


def test_a_retry_that_fails_too_leaves_the_original_failure_standing():
    """No failure is hidden: if the normalizer does not rescue the section,
    the frozen extractor's own FAIL row is what the manifest records."""
    original = _attempt("MDA", "no_toc_and_no_heading_match")
    IO_extract = IO.EX.extract_filing
    try:
        IO.EX.extract_filing = lambda *a, **k: [
            _attempt("MDA", "no_toc_and_no_heading_match")]
        out = IO.retry_failed_on_normalized_html([original], {}, {})
    finally:
        IO.EX.extract_filing = IO_extract
    assert out[0][1] is original[1]
    assert IO.DIALECT_NOTE not in (out[0][1].note or "")


def test_a_rescued_section_says_so_in_its_audit_note():
    original = _attempt("MDA", "no_toc_and_no_heading_match")
    rescued = _attempt("MDA", "heading_regex_fallback", "real text here")
    IO_extract = IO.EX.extract_filing
    try:
        IO.EX.extract_filing = lambda *a, **k: [rescued]
        out = IO.retry_failed_on_normalized_html([original], {}, {})
    finally:
        IO.EX.extract_filing = IO_extract
    assert out[0][1] is rescued[1]
    assert IO.DIALECT_NOTE in out[0][1].note
    assert "extract.py is unchanged" in IO.DIALECT_NOTE


def test_the_app_lane_never_writes_into_the_frozen_extractor():
    """extract.py is frozen because the sealed E2 corpus depends on it. The
    normalizer is a READER passed in, never a monkeypatch of the module."""
    import ast

    tree = ast.parse(Path(IO.__file__).read_text())
    writes = [ast.unparse(t) for node in ast.walk(tree)
              if isinstance(node, (ast.Assign, ast.AugAssign))
              for t in (node.targets if isinstance(node, ast.Assign) else [node.target])
              if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
              and t.value.id == "EX"]
    assert not writes, writes
    assert "setattr(EX" not in Path(IO.__file__).read_text()


# ===========================================================================
# ingest_one -- the chunk config is F4's, with the four declared differences
# ===========================================================================
def test_chunk_config_keeps_f4s_line_rule_and_id_namespace(tmp_path):
    cfg = IO.chunk_config(tmp_path / "s.parquet", tmp_path / "c.parquet")
    assert cfg.line_rule == BFC.LINE_RULE == "reflow_v1"
    assert cfg.chunk_prefix == BFC.CHUNK_PREFIX
    assert cfg.para_prefix == BFC.PARA_PREFIX
    assert cfg.tie_slot == "cik10"


def test_chunk_config_differs_from_f4_in_exactly_the_declared_ways(tmp_path):
    f4 = BFC.BuildConfig()
    app = IO.chunk_config(tmp_path / "s.parquet", tmp_path / "c.parquet")
    differing = {name for name in vars(f4)
                 if getattr(f4, name) != getattr(app, name)}
    assert differing == {"corpus_path", "corpus_sha256", "stratum",
                         "window_rule", "out_parquet", "membership_db"}


def test_an_external_company_is_never_marked_a_universe_member(store):
    chunks = pd.read_parquet(store / "chunks.parquet")
    assert (chunks.home_stratum == IO.EXTERNAL_STRATUM).all()
    assert not chunks.in_member_spell.any()
    assert not chunks.in_member_spell_plus12m.any()
    assert (chunks.window_rule == IO.WINDOW_RULE).all()


def test_the_chunker_really_deduplicates_inside_the_store(store):
    """The shared MD&A paragraphs must produce chunks whose occurrence array
    names BOTH 10-Ks -- otherwise the diff below proves nothing."""
    chunks = pd.read_parquet(store / "chunks.parquet")
    shared = chunks[chunks.n_source_filings > 1]
    assert not shared.empty
    for accs in shared.source_accession_numbers:
        assert ACC_NOW in list(accs) and ACC_PRIOR in list(accs)


# ===========================================================================
# the three schemas ARE the research corpus's schemas
# ===========================================================================
@corpus_present
def test_store_sections_schema_equals_the_research_corpus_schema(store):
    got = pq.read_schema(store / "sections.parquet").remove_metadata()
    want = pq.read_schema(E2_SECTIONS).remove_metadata()
    assert got.equals(want)


@corpus_present
def test_store_chunks_schema_equals_the_f4_chunk_schema(store):
    got = pq.read_schema(store / "chunks.parquet").remove_metadata()
    want = pq.read_schema(F4_CHUNKS).remove_metadata()
    assert got.equals(want)


@corpus_present
def test_store_labels_schema_equals_the_f4_label_schema(store):
    got = pq.read_schema(store / "labels.parquet").remove_metadata()
    want = pq.read_schema(F4_LABELS).remove_metadata()
    assert got.equals(want)


def test_store_sqlite_answers_report_filings_own_queries(store):
    con = sqlite3.connect(store / "metadata.db")
    try:
        rows = pd.read_sql(
            "SELECT accession_number, cik, form, filing_date, report_date, "
            "acceptance_datetime, items, has_earnings_item FROM filings WHERE cik = ?",
            con, params=(CIK,))
        name = con.execute("SELECT company_name FROM companies WHERE cik = ?",
                           (CIK,)).fetchone()
    finally:
        con.close()
    assert set(rows.accession_number) == {ACC_NOW, ACC_PRIOR, ACC_8K}
    assert name[0] == "SYNTHETIC CO"


# ===========================================================================
# label_filing -- the three refusals
# ===========================================================================
def test_a_live_campaign_process_is_refused(monkeypatch):
    monkeypatch.setattr(LF, "campaign_is_alive",
                        lambda: ["/x/python finetune/label_e2.py --segment 7"])
    with pytest.raises(LF.LabelRefusal, match="campaign process is alive"):
        LF.assert_no_campaign()


def test_campaign_scan_does_not_see_this_process():
    """`label_filing.py` appears in this very process's command line under
    pytest often enough that a naive scan would refuse to run at all."""
    assert not any("label_filing.py" in hit for hit in LF.campaign_is_alive())


def test_a_different_adapter_is_refused(monkeypatch):
    monkeypatch.setattr(LF.ev, "_adapter_provenance",
                        lambda *a, **k: {"adapters_sha256": "d" * 64})
    with pytest.raises(LF.LabelRefusal, match="ADAPTER MISMATCH"):
        LF.assert_labeler_identity(Path("/x"), "/model", L2.INSTRUCTION_SHA256)


def test_a_different_instruction_is_refused(monkeypatch):
    want = LF.campaign_inputs()["adapter_sha256_expected"]
    monkeypatch.setattr(LF.ev, "_adapter_provenance",
                        lambda *a, **k: {"adapters_sha256": want})
    with pytest.raises(LF.LabelRefusal, match="INSTRUCTION MISMATCH"):
        LF.assert_labeler_identity(Path("/x"), "/model", "e" * 64)


def test_the_campaign_adapter_is_accepted(monkeypatch):
    want = LF.campaign_inputs()["adapter_sha256_expected"]
    monkeypatch.setattr(LF.ev, "_adapter_provenance",
                        lambda *a, **k: {"adapters_sha256": want})
    out = LF.assert_labeler_identity(Path("/x"), "/model", L2.INSTRUCTION_SHA256)
    assert out["campaign_adapter_sha256"] == want


def _canary_state(tmp_path, key, verified=True, n=10) -> Path:
    path = tmp_path / "canary.json"
    path.write_text(json.dumps({"key": key, "result": {
        "verified": verified, "n_identical": n, "n_compared": 10}}))
    return path


def test_a_cached_canary_pass_is_reused(tmp_path):
    key = LF.canary_key("a" * 64, "b" * 64, Path(L2.REFERENCE_EVAL_DIR))
    assert LF.cached_canary(key, _canary_state(tmp_path, key)) is not None


def test_a_cached_canary_does_not_survive_a_moved_adapter(tmp_path):
    key = LF.canary_key("a" * 64, "b" * 64, Path(L2.REFERENCE_EVAL_DIR))
    path = _canary_state(tmp_path, key)
    moved = LF.canary_key("c" * 64, "b" * 64, Path(L2.REFERENCE_EVAL_DIR))
    assert LF.cached_canary(moved, path) is None


def test_a_cached_canary_FAILURE_is_never_reused_as_a_pass(tmp_path):
    key = LF.canary_key("a" * 64, "b" * 64, Path(L2.REFERENCE_EVAL_DIR))
    path = _canary_state(tmp_path, key, verified=False, n=9)
    assert LF.cached_canary(key, path) is None


def test_a_failing_canary_refuses_to_label(tmp_path, monkeypatch):
    monkeypatch.setattr(L2, "repro_canary", lambda args, n: {
        "verified": False, "n_identical": 9, "n_compared": 10,
        "differing": ["CHK-x"]})
    args = LF.build_args(tmp_path)
    with pytest.raises(LF.LabelRefusal, match="REPRO CANARY FAILED"):
        LF.ensure_canary(args, "a" * 64, "b" * 64,
                         state_path=tmp_path / "canary.json")


def test_the_canary_key_covers_the_three_things_it_proves():
    key = LF.canary_key("a" * 64, "b" * 64, Path(L2.REFERENCE_EVAL_DIR))
    assert set(key) >= {"adapter_sha256", "instruction_sha256",
                        "reference_predictions_sha256"}
    assert key["n_rows"] == 10


# ===========================================================================
# label_filing -- the prompt input, and the writer
# ===========================================================================
FORBIDDEN_IN_A_PROMPT_ROW = ("cik", "company", "name", "ticker", "date",
                             "section", "form", "accession")


def test_prepare_writes_the_passage_and_nothing_identifying(store):
    prep = LF.prepare_rows(store)
    rows = [json.loads(line) for line in open(store / LF.ROWS_NAME)]
    assert prep["n_rows"] == len(rows)
    for row in rows:
        assert set(row) == {"chunk_id", "passage", "guidance_applicable"}
        for banned in FORBIDDEN_IN_A_PROMPT_ROW:
            assert banned not in {k.lower() for k in row}


def test_the_prompt_input_hash_is_the_instruction_plus_the_passage():
    a = L2.prompt_input_sha("i" * 64, "hello")
    assert a == L2.prompt_input_sha("i" * 64, "hello")
    assert a != L2.prompt_input_sha("i" * 64, "hello ")
    assert a != L2.prompt_input_sha("j" * 64, "hello")


def test_the_writer_applies_missing_to_none_with_its_audit_flag(store):
    labels = pd.read_parquet(store / "labels.parquet")
    imputed = labels[labels.guidance_imputed_none]
    assert len(imputed) >= 1, "the canned row that omits the key must be imputed"
    assert (imputed.guidance_direction == "NONE").all()
    assert (imputed.guidance_applicable).all(), \
        "missing->NONE is scoped to guidance-applicable sections only"


def test_the_writer_never_imputes_on_a_non_applicable_section(store):
    labels = pd.read_parquet(store / "labels.parquet")
    assert not labels[~labels.guidance_applicable].guidance_imputed_none.any()


def test_every_label_row_carries_the_ruled_provenance_columns(store):
    labels = pd.read_parquet(store / "labels.parquet")
    assert (labels.rubric_version == L2.RUBRIC_VERSION).all()
    assert (labels.system_prompt_sha256 == L2.INSTRUCTION_SHA256).all()
    assert labels.schema_valid.all() and labels.parse_ok.all()
    assert (labels.api_result_type == "student_local_mlx").all()


def test_the_label_writer_is_resumable_over_its_journal(store, tmp_path):
    """A journal missing rows yields a labels table missing exactly those rows
    -- never a silently complete-looking one."""
    root = tmp_path / "partial"
    root.mkdir()
    for name in ("chunks.parquet", "sections.parquet", "metadata.db"):
        (root / name).write_bytes((store / name).read_bytes())
    lines = (store / LF.JOURNAL_NAME).read_text().splitlines()
    (root / LF.JOURNAL_NAME).write_text("\n".join(lines[:3]) + "\n")
    LF.write_labels(root)
    assert len(pd.read_parquet(root / "labels.parquet")) == 3


# ===========================================================================
# report_filing --store
# ===========================================================================
def test_without_a_store_every_reader_is_the_research_corpus():
    assert RF.ACTIVE_STORE is None
    assert RF.chunks_path() == RF.CHUNKS_PATH
    assert RF.labels_path() == RF.LABELS_PATH
    assert RF.sections_path() == RF.SECTIONS_PATH
    assert RF.metadata_db_path() == RF.METADATA_DB
    assert RF.cache_path() == RF.CHUNK_INDEX_CACHE


def test_a_store_redirects_exactly_the_five_readers(store):
    RF.use_store(store)
    assert RF.chunks_path() == store / "chunks.parquet"
    assert RF.labels_path() == store / "labels.parquet"
    assert RF.sections_path() == store / "sections.parquet"
    assert RF.metadata_db_path() == store / "metadata.db"
    assert RF.cache_path() == store / "chunk_index.parquet"


def test_releasing_the_store_restores_the_research_corpus(store):
    RF.use_store(store)
    RF.use_store(None)
    assert RF.chunks_path() == RF.CHUNKS_PATH


def test_an_incomplete_store_is_refused(tmp_path):
    (tmp_path / "chunks.parquet").write_bytes(b"x")
    with pytest.raises(SystemExit, match="not a complete company store"):
        RF.use_store(tmp_path)


def _render(store, accession, out_dir):
    RF.use_store(store)
    index = RF.load_cache(rebuild=True, verbose=False)
    occ = RF.occurrence_map(index)
    return RF.render_filing(index, occ, CIK, accession, out_dir)


def test_a_store_filing_renders_end_to_end(store, tmp_path):
    out = _render(store, ACC_NOW, tmp_path)
    html = out.read_text()
    assert out.exists() and len(html) > 2000
    assert "SYNTHETIC CO" in html
    assert "Management&#x27;s Discussion and Analysis" in html or "Management" in html


def test_the_store_report_adds_the_one_outside_universe_line(store, tmp_path):
    html = _render(store, ACC_NOW, tmp_path).read_text()
    assert RF.OUTSIDE_UNIVERSE_LINE in html
    assert html.count(RF.OUTSIDE_UNIVERSE_LINE) == 1, "one line, not two"


def test_the_store_report_prints_ITS_OWN_guidance_imputation_share(store, tmp_path):
    """L2.4: the share of NONEs the model never emitted is counted off THIS
    store's labels, not quoted from the research corpus. The fixture omits the
    guidance key on exactly one of its guidance-applicable chunks, so the
    page must read "1 of N"."""
    from html import unescape

    labels = pd.read_parquet(store / "labels.parquet",
                             columns=["guidance_applicable", "guidance_imputed_none"])
    n_applicable = int(labels.guidance_applicable.fillna(False).sum())
    n_imputed = int((labels.guidance_applicable.fillna(False)
                     & labels.guidance_imputed_none.fillna(False)).sum())
    assert n_imputed == 1 and n_applicable >= 1

    html = unescape(_render(store, ACC_NOW, tmp_path).read_text())
    assert (f"{n_imputed:,} of {n_applicable:,} guidance-applicable passages "
            "carry an imputed NONE (the model emitted no guidance key)") in html
    assert "this company's store" in html
    block = html.split('<section class="disclosure">')[1].split("</section>")[0]
    assert "Imputed guidance" in block


def test_the_outside_universe_line_says_the_three_ruled_things():
    line = RF.OUTSIDE_UNIVERSE_LINE
    assert "outside the 244-company research universe" in line
    assert "no spot-check" in line
    assert "model-consensus error at best" in line


@corpus_present
def test_the_research_corpus_report_never_carries_that_line(tmp_path):
    """The F4 path's behaviour is unchanged -- the extra line is a store fact."""
    RF.use_store(None)
    disclosure = RF.disclosure_html(RF.load_disclosure(), None)
    assert RF.OUTSIDE_UNIVERSE_LINE not in disclosure


@corpus_present
def test_the_store_line_is_inside_the_disclosure_block(store, tmp_path):
    html = _render(store, ACC_NOW, tmp_path).read_text()
    block = html.split('<section class="disclosure">')[1].split("</section>")[0]
    assert RF.OUTSIDE_UNIVERSE_LINE in block


def test_every_paragraph_on_a_store_page_is_inside_that_filing(store, tmp_path):
    RF.use_store(store)
    index = RF.load_cache(rebuild=True, verbose=False)
    occ = RF.occurrence_map(index)
    sections = RF.filing_sections(ACC_NOW)
    frame, texts, _, _ = RF.contained_filing(index, occ, ACC_NOW, sections)
    haystack = RF.section_texts(sections)
    for row in frame.itertuples():
        for para in RF.split_paragraphs(texts[int(row.row_index)]):
            assert RF.collapse_whitespace(para) in haystack[str(row.section_type)]


def test_a_store_page_never_shows_the_prior_filings_own_paragraphs(store, tmp_path):
    """Paragraphs 30-32 are only in the PRIOR 10-K. Containment must keep them
    off this page even though the chunker attributed some shared chunk to it."""
    html = _render(store, ACC_NOW, tmp_path).read_text()
    body = html.split("The filing, section by section")[1]
    assert "p30." not in body and "p31." not in body and "p32." not in body
    assert "p10." in body


def test_the_store_diff_splits_new_from_unchanged(store, tmp_path):
    RF.use_store(store)
    index = RF.load_cache(rebuild=True, verbose=False)
    occ = RF.occurrence_map(index)
    now, _, _, _ = RF.contained_filing(index, occ, ACC_NOW)
    prior, _, _, _ = RF.contained_filing(index, occ, ACC_PRIOR)
    diff = RF.diff_vs_prior(now, prior)
    assert len(diff["new"]) > 0, "the 2026 10-K has paragraphs the 2025 one lacks"
    assert len(diff["removed"]) > 0, "and the 2025 one has a block it dropped"
    assert len(diff["unchanged"]) > 0, "and the two share the MD&A opening"
    # The removed block is the prior filing's own RISK_FACTORS, not a chunk the
    # current filing merely trimmed: no removed chunk may be sourced to ACC_NOW.
    for accs in diff["removed"].source_accession_numbers:
        assert ACC_NOW not in list(accs)


def test_a_store_page_keeps_every_refusal(store, tmp_path):
    """The rendered-output refusals are the F4 page's, re-run on a store page:
    no refused vocabulary outside the disclosure block, and no script."""
    import test_report_filing as TRF

    html = _render(store, ACC_NOW, tmp_path).read_text()
    assert TRF.word_hits(TRF.chrome_only(html)) == []
    assert "<script" not in html.lower() and "javascript:" not in html.lower()


def test_a_store_page_carries_no_price_or_outcome_column(store, tmp_path):
    html = _render(store, ACC_NOW, tmp_path).read_text()
    for banned in ("prices_e2", "target_e2", "backtest", "excess return",
                   "information coefficient"):
        assert banned not in html


def test_the_store_index_page_renders(store, tmp_path):
    RF.use_store(store)
    index = RF.load_cache(rebuild=True, verbose=False)
    occ = RF.occurrence_map(index)
    out = RF.render_index(index, occ, CIK, tmp_path)
    html = out.read_text()
    assert ACC_NOW in html and ACC_8K in html
    assert RF.OUTSIDE_UNIVERSE_LINE in html


def test_the_store_cache_lives_in_the_store_not_the_shared_cache(store, tmp_path):
    RF.use_store(store)
    RF.load_cache(rebuild=True, verbose=False)
    assert (store / "chunk_index.parquet").exists()


def test_the_store_cache_is_rebuilt_when_the_store_tables_move(store):
    RF.use_store(store)
    RF.load_cache(rebuild=True, verbose=False)
    meta = pq.ParquetFile(store / "chunk_index.parquet").schema_arrow.metadata
    stamped = json.loads(meta[b"input_sha256"])
    assert set(stamped) == {str(store / "chunks.parquet"),
                            str(store / "labels.parquet")}


def test_ticker_resolution_on_a_store_is_the_stores_own_company(store):
    RF.use_store(store)
    assert RF.resolve_ticker("SYN") == CIK
    assert RF.resolve_ticker("syn") == CIK
    with pytest.raises(SystemExit, match="not this store's company"):
        RF.resolve_ticker("AAPL")


def test_fundamentals_are_unresolved_for_a_store_that_never_ingested_them(store):
    """A store built before P1a.2 carries no fundamentals. The panel must say
    so -- every family unresolved, with the reason, and never a blank or an
    invented number."""
    RF.use_store(store)
    panel = RF.fundamentals_panel(CIK, "2026-02-10")
    assert len(panel) == len(RF.FUNDAMENTAL_FAMILIES)
    assert all(entry["state"] == "unresolved" for entry in panel)
    assert all(entry["detail"] == RF.NO_STORE_FUNDAMENTALS_DETAIL
               for entry in panel)


# ===========================================================================
# fundamentals (P1a.2) -- ingest_one --fundamentals, and the store's own panel
#
# SYNTHETIC, and PLUMBING ONLY, like everything else in this file: the facts
# below are made up so the six classifier states and the point-in-time rule
# have an answer that is checkable by hand. The numbers anybody reads come
# from data/app/status/L2_3_external_fundamentals.md -- ten real companies.
# ===========================================================================
FUND_CIK = CIK            # the synthetic store's own company
QUARTER_ENDS = ("03-31", "06-30", "09-30", "12-31")


def _quarter_end(i: int, first_year: int = 2023) -> str:
    return f"{first_year + i // 4}-{QUARTER_ENDS[i % 4]}"


def _quarter_start(i: int, first_year: int = 2023) -> str:
    return f"{first_year + i // 4}-{('01-01', '04-01', '07-01', '10-01')[i % 4]}"


def _filed(i: int, first_year: int = 2023) -> str:
    """~45 days after the quarter ends, which is when a 10-Q shows up."""
    return str((pd.Timestamp(_quarter_end(i, first_year))
                + pd.Timedelta(days=45)).date())


def _accn(i: int) -> str:
    return f"{FUND_CIK:010d}-{str(23 + i // 4)[-2:]}-{i:06d}"


def _fact(i: int, val: float, *, duration: bool, filed: str = None,
          form: str = "10-Q", accn: str = None) -> dict:
    fact = {"val": val, "fy": 2023 + i // 4, "fp": f"Q{i % 4 + 1}",
            "end": _quarter_end(i), "form": form,
            "accn": accn or _accn(i), "filed": filed or _filed(i)}
    if duration:
        fact["start"] = _quarter_start(i)
    return fact


# The 2025Q4 revenue as first filed, and as restated three months later. The
# store's own 10-K is filed 2026-02-10, between the two.
REVENUE_ORIGINAL = 100_000_000.0
REVENUE_RESTATED = 90_000_000.0
REVENUE_ORIGINAL_FILED = "2026-02-05"
REVENUE_RESTATED_FILED = "2026-05-01"
RESTATEMENT_ACCN = f"{FUND_CIK:010d}-26-000099"


def synthetic_companyfacts() -> dict:
    """One company's companyfacts, shaped so each panel family lands in a
    different classifier state:

      assets   12 of 12 quarters under one tag           -> SINGLE, resolved
      revenue  12 of 12, with 2025Q4 restated later      -> SINGLE, resolved
      equity   3 of 12 quarters                          -> PARTIAL, UNRESOLVED
      net_income / operating_cash_flow  no tag at all    -> ABSENT, UNRESOLVED
    """
    assets = [_fact(i, 1_000_000_000.0 + i, duration=False) for i in range(12)]
    revenue = [_fact(i, 50_000_000.0 + i, duration=True) for i in range(11)]
    revenue.append(_fact(11, REVENUE_ORIGINAL, duration=True, form="10-K",
                         filed=REVENUE_ORIGINAL_FILED))
    revenue.append(_fact(11, REVENUE_RESTATED, duration=True, form="10-Q",
                         filed=REVENUE_RESTATED_FILED, accn=RESTATEMENT_ACCN))
    equity = [_fact(i, 400_000_000.0 + i, duration=False) for i in range(3)]
    return {"cik": FUND_CIK, "entityName": "SYNTHETIC CO", "facts": {"us-gaap": {
        "Assets": {"units": {"USD": assets}},
        "Revenues": {"units": {"USD": revenue}},
        "StockholdersEquity": {"units": {"USD": equity}},
    }}}


class FakeFactsClient:
    """Stands in for EdgarClient in the fundamentals tests. No network."""

    def __init__(self, cache_dir: Path, facts: dict):
        self.cache_dir = Path(cache_dir)
        self._facts = facts
        self.request_count = 0
        self.headers = {"User-Agent": "test test@example.com"}

    def get_companyfacts(self, cik, force=False, **kw):
        self.request_count += 1
        path = self.cache_dir / "companyfacts" / f"CIK{int(cik):010d}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._facts))
        return self._facts

    def get_company_tickers(self, force=False):
        return {"0": {"cik_str": FUND_CIK, "ticker": "SYN",
                      "title": "SYNTHETIC CO"}}


@pytest.fixture(scope="module")
def fundamentals_store(tmp_path_factory, store) -> Path:
    """The synthetic store, copied, with step 7 run over synthetic facts.

    A copy so the no-fundamentals store above keeps testing the "never
    ingested" path in the same session.
    """
    root = tmp_path_factory.mktemp("fundstore") / str(FUND_CIK)
    shutil.copytree(store, root)
    client = FakeFactsClient(tmp_path_factory.mktemp("rawcache"),
                             synthetic_companyfacts())
    block = IO.ingest_fundamentals_for(FUND_CIK, "SYN", "SYNTHETIC CO", root,
                                       client=client, verbose=False)
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["fundamentals"] = block
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return root


# -- what ingest_one --fundamentals writes ----------------------------------
def test_fundamentals_ingest_writes_both_files(fundamentals_store):
    assert (fundamentals_store / IO.FUNDAMENTALS_NAME).exists()
    assert (fundamentals_store / IO.CONCEPT_RESOLUTION_NAME).exists()


def test_every_filed_occurrence_is_kept_never_deduplicated(fundamentals_store):
    """The point-in-time guarantee starts here: a restatement is a NEW row,
    same period, later filed date -- it never overwrites the original."""
    facts = pd.read_parquet(fundamentals_store / IO.FUNDAMENTALS_NAME)
    q4 = facts[(facts.concept == "Revenues") & (facts.period_end == "2025-12-31")]
    assert len(q4) == 2
    assert sorted(q4.value) == [REVENUE_RESTATED, REVENUE_ORIGINAL]
    assert sorted(q4.filed) == [REVENUE_ORIGINAL_FILED, REVENUE_RESTATED_FILED]


@pytest.mark.skipif(not E2_FUNDAMENTALS.exists(),
                    reason="the research fundamentals table is not on this machine")
def test_store_fundamentals_schema_equals_the_research_schema(fundamentals_store):
    """"Same schema as data/fundamentals_e2.parquet" is a comparison, not a
    claim."""
    assert (pq.read_schema(fundamentals_store / IO.FUNDAMENTALS_NAME)
            .remove_metadata()
            .equals(pq.read_schema(E2_FUNDAMENTALS).remove_metadata()))


@pytest.mark.skipif(not F2_RESOLUTION.exists(),
                    reason="F2's concept resolution is not on this machine")
def test_store_concept_resolution_columns_equal_f2s(fundamentals_store):
    ours = pd.read_csv(fundamentals_store / IO.CONCEPT_RESOLUTION_NAME)
    theirs = pd.read_csv(F2_RESOLUTION, nrows=1)
    assert list(ours.columns) == list(theirs.columns)


def test_every_family_gets_a_row_resolved_or_not(fundamentals_store):
    """One row per (cik, family), always -- a family with no fact at all is
    ABSENT on the record rather than missing from it."""
    res = pd.read_csv(fundamentals_store / IO.CONCEPT_RESOLUTION_NAME)
    assert set(res.family) == set(IO.IF.CONCEPT_FAMILIES)
    assert set(res.cik) == {FUND_CIK}


def test_the_classifier_states_are_f2s_own(fundamentals_store):
    res = pd.read_csv(fundamentals_store / IO.CONCEPT_RESOLUTION_NAME
                      ).set_index("family")
    assert res.loc["assets", "state"] == IO.IF.STATE_SINGLE
    assert res.loc["assets", "tags"] == "Assets"
    assert res.loc["revenue", "state"] == IO.IF.STATE_SINGLE
    assert res.loc["equity", "state"] == IO.IF.STATE_PARTIAL
    assert res.loc["net_income", "state"] == IO.IF.STATE_ABSENT
    assert res.loc["equity", "severity"] == IO.IF.SEVERITY_UNRESOLVED
    assert res.loc["net_income", "severity"] == IO.IF.SEVERITY_UNRESOLVED


def test_an_unresolved_family_is_never_called_resolved(fundamentals_store):
    """`resolved_tags` is empty by construction for an UNRESOLVED pair: no
    store-side fallback, no "most rows wins", no override map."""
    res = pd.read_csv(fundamentals_store / IO.CONCEPT_RESOLUTION_NAME)
    unresolved = res[res.severity == IO.IF.SEVERITY_UNRESOLVED]
    assert not unresolved.empty
    RF.use_store(fundamentals_store)
    with RF.fundamentals_source():
        loaded = RF.NF.load_resolution({FUND_CIK})
    assert not loaded[~loaded.resolved].resolved.any()
    # ...and the panel never calls one of them resolved: a PARTIAL family may
    # show its latest filed fact, marked partial; an ABSENT one shows nothing.
    unresolved_families = set(unresolved.family)
    absent = set(res[res.state == IO.IF.STATE_ABSENT].family)
    panel = RF.fundamentals_panel(FUND_CIK, "2026-02-10")
    for entry in panel:
        if entry["family"] in unresolved_families:
            assert entry["state"] in ("unresolved", "partial")
        if entry["state"] == "partial":
            state = res[res.family == entry["family"]].state.iloc[0]
            assert f"this family is {state} " in entry["note"]
        if entry["family"] in absent:
            assert entry["state"] == "unresolved"
            assert "value" not in entry and "concept" not in entry


def test_the_manifest_carries_the_classifiers_own_reason(fundamentals_store):
    block = json.loads((fundamentals_store / "manifest.json").read_text()
                       )["fundamentals"]
    reasons = {row["family"]: row["reason"] for row in block["families"]}
    assert reasons["assets"] is None
    assert "PARTIAL" in reasons["equity"]
    assert "coverage bar" in reasons["equity"]
    assert "ABSENT" in reasons["net_income"]
    assert block["network"]["cost_usd"] == 0.0


def test_f2s_committed_records_are_never_written(tmp_path, monkeypatch):
    """Step 7 writes into the store and nowhere else. F2's fundamentals table,
    F2's concept resolution and the E2 database are frozen records; `IF.run()`
    -- the function that writes all three -- is never called from here."""
    forbidden = {str(RF.NF.FUNDAMENTALS_PATH), str(RF.NF.CONCEPT_RESOLUTION_CSV),
                 str(IO.E2_METADATA_DB)}
    written: list[str] = []
    for module, attr in ((Path, "write_text"), (Path, "write_bytes")):
        real = getattr(module, attr)

        def traced(self, *a, _real=real, **kw):
            written.append(str(self))
            return _real(self, *a, **kw)
        monkeypatch.setattr(module, attr, traced)
    real_write_table = IO.pq.write_table
    monkeypatch.setattr(IO.pq, "write_table",
                        lambda t, p, *a, **k: (written.append(str(p)),
                                               real_write_table(t, p, *a, **k))[1])
    client = FakeFactsClient(tmp_path / "cache", synthetic_companyfacts())
    IO.ingest_fundamentals_for(FUND_CIK, "SYN", "SYNTHETIC CO", tmp_path / "store",
                               client=client, verbose=False)
    assert written, "the recorder saw nothing; the patching is broken"
    assert not (set(written) & forbidden)
    assert all(str(tmp_path) in p for p in written), written


def test_the_window_is_the_companys_own_xbrl_life(fundamentals_store):
    block = json.loads((fundamentals_store / "manifest.json").read_text()
                       )["fundamentals"]
    assert block["window"]["start"] == "2023-03-31"     # first period end
    assert block["window"]["end"] >= "2026-09-11"       # today, never clipped


def test_a_company_with_no_xbrl_facts_is_absent_everywhere_not_a_crash(tmp_path):
    client = FakeFactsClient(tmp_path / "cache", {"cik": 1, "facts": {}})
    block = IO.ingest_fundamentals_for(1, None, "NO FACTS CO", tmp_path / "s",
                                       client=client, verbose=False)
    assert block["failure"]["cause"] == "no_facts_under_any_family_tag"
    assert block["parquet"]["n_rows"] == 0
    assert {f["state"] for f in block["families"]} == {IO.IF.STATE_ABSENT}


# -- what the panel does with them ------------------------------------------
def test_the_panel_resolves_from_the_stores_own_files(fundamentals_store):
    RF.use_store(fundamentals_store)
    panel = {e["family"]: e for e in RF.fundamentals_panel(FUND_CIK, "2026-02-10")}
    assert panel["assets"]["state"] == "resolved"
    assert panel["assets"]["concept"] == "Assets"
    assert panel["assets"]["unit"] == "USD"
    assert panel["revenue"]["state"] == "resolved"


def test_the_panel_is_point_in_time_and_shows_the_restatement(fundamentals_store):
    """The whole point of keeping every filed occurrence: as of the 10-K's own
    filing date the ORIGINAL figure is what was knowable; three months later
    the restated one is, and the filed date beside it says which is which."""
    RF.use_store(fundamentals_store)
    before = {e["family"]: e for e in
              RF.fundamentals_panel(FUND_CIK, "2026-02-10")}["revenue"]
    after = {e["family"]: e for e in
             RF.fundamentals_panel(FUND_CIK, "2026-06-01")}["revenue"]
    assert before["value"] == REVENUE_ORIGINAL
    assert before["filed"] == REVENUE_ORIGINAL_FILED
    assert after["value"] == REVENUE_RESTATED
    assert after["filed"] == REVENUE_RESTATED_FILED
    assert before["period_end"] == after["period_end"] == "2025-12-31"


def test_a_fact_filed_after_the_as_of_date_is_invisible(fundamentals_store):
    """Look-ahead, stated as a test: on 2026-02-04 the 2025Q4 revenue had not
    been filed yet, so the freshest knowable period is 2025Q3."""
    RF.use_store(fundamentals_store)
    panel = {e["family"]: e for e in RF.fundamentals_panel(FUND_CIK, "2026-02-04")}
    assert panel["revenue"]["period_end"] == "2025-09-30"


def test_an_unresolved_family_renders_unresolved_with_its_reason(fundamentals_store):
    RF.use_store(fundamentals_store)
    panel = {e["family"]: e for e in RF.fundamentals_panel(FUND_CIK, "2026-02-10")}
    assert panel["net_income"]["state"] == "unresolved"
    assert "ABSENT" in panel["net_income"]["detail"]
    assert "value" not in panel["net_income"]


def test_a_partial_family_shows_its_latest_filed_fact_marked_partial(
        fundamentals_store):
    """(b) PARTIAL is a time-series verdict, not "no fact": the reader is shown
    the freshest knowable fact, with the classifier's state and coverage."""
    RF.use_store(fundamentals_store)
    res = pd.read_csv(fundamentals_store / IO.CONCEPT_RESOLUTION_NAME)
    coverage = float(res[res.family == "equity"].coverage.iloc[0])
    equity = {e["family"]: e for e in
              RF.fundamentals_panel(FUND_CIK, "2024-01-01")}["equity"]
    assert equity["state"] == "partial"
    assert equity["value"] == 400_000_002.0          # 2023Q3, filed 2023-11-14
    assert equity["concept"] == "StockholdersEquity"
    assert equity["period_end"] == "2023-09-30"
    assert equity["note"] == (
        "single fact as filed; as a time series this family is PARTIAL "
        f"(union coverage {coverage:.0%}), so the research path leaves it "
        "unresolved")
    # older than the staleness limit: still partial, and the age is said
    old = {e["family"]: e for e in
           RF.fundamentals_panel(FUND_CIK, "2026-02-10")}["equity"]
    assert old["state"] == "partial"
    assert old["note"].endswith("; 864 days old at this filing date")
    html = RF.fundamentals_html([old], "2026-02-10")
    assert '<span class="tag">partial</span>' in html
    assert "864 days old at this filing date" in html
    assert "masked" not in html


def test_a_stale_resolved_family_shows_the_fact_marked_stale(fundamentals_store):
    """(c) resolved, but the freshest knowable fact is past the research
    path's staleness limit: shown, with its age and the limit."""
    RF.use_store(fundamentals_store)
    assets = {e["family"]: e for e in
              RF.fundamentals_panel(FUND_CIK, "2027-06-01")}["assets"]
    assert assets["state"] == "stale"
    assert assets["period_end"] == "2025-12-31"
    assert assets["value"] == 1_000_000_011.0
    assert assets["note"] == (
        f"517 days old at this filing date; the research path discards facts "
        f"older than {RF.NF.F1.STALENESS_MAX_DAYS} days")
    html = RF.fundamentals_html([assets], "2027-06-01")
    assert '<span class="tag">stale</span>' in html and "517 days old" in html


def test_a_fresher_alias_fact_beats_the_resolved_tag(fundamentals_store,
                                                     monkeypatch):
    """Costco's 10-Q: the resolution lists only `Revenues`, whose last quarter
    is still inside the staleness limit, while the filing itself reports a
    later quarter under another alias of the family. The page must show the
    later period, marked partial, and say which tag it came from."""
    RF.use_store(fundamentals_store)
    alias = "RevenueFromContractWithCustomerExcludingAssessedTax"
    real = RF.fundamentals_slices

    def with_alias(cik):
        slices = real(cik)
        fresh = slices[(FUND_CIK, "Revenues")].copy()
        fresh["concept"] = alias
        fresh["period_start"] = pd.Timestamp("2026-01-01")
        fresh["period_end"] = pd.Timestamp("2026-03-31")
        fresh["filed"] = pd.Timestamp("2026-04-20")
        return {**slices, (FUND_CIK, alias): fresh}
    monkeypatch.setattr(RF, "fundamentals_slices", with_alias)
    # as of 2026-04-25 the resolved Revenues quarter (2025-12-31) is 115 days
    # old -- fresh enough for the research path -- but older than the alias
    revenue = {e["family"]: e for e in
               RF.fundamentals_panel(FUND_CIK, "2026-04-25")}["revenue"]
    assert revenue["state"] == "partial"
    assert revenue["concept"] == alias
    assert revenue["period_end"] == "2026-03-31"
    assert revenue["note"] == (
        f"filed under {alias}, a tag the stored concept resolution does not "
        "list for this family (Revenues); single fact as filed")
    # without the alias the same date shows the resolved listed-tag fact
    monkeypatch.setattr(RF, "fundamentals_slices", real)
    resolved = {e["family"]: e for e in
                RF.fundamentals_panel(FUND_CIK, "2026-04-25")}["revenue"]
    assert resolved["state"] == "resolved" and resolved["concept"] == "Revenues"


def test_freshest_fact_breaks_a_tie_toward_the_first_listed_alias():
    """One filing carrying two aliases for the same period and filed date
    (XOM's NetIncomeLoss and ProfitLoss): the family's preferred tag, listed
    first, wins -- not whichever happens to sort last."""
    def fact(tag, value):
        return pd.DataFrame([{
            "ticker": "SYN", "cik": FUND_CIK, "taxonomy": "us-gaap",
            "concept": tag, "unit": "USD", "value": value, "fy": 2026.0,
            "fp": "Q3", "period_start": pd.Timestamp("2026-07-01"),
            "period_end": pd.Timestamp("2026-09-30"), "form": "10-Q",
            "accession_number": "0000000001-26-000001",
            "filed": pd.Timestamp("2026-11-02")}])
    slices = {(FUND_CIK, "NetIncomeLoss"): fact("NetIncomeLoss", 15.0),
              (FUND_CIK, "ProfitLoss"): fact("ProfitLoss", 16.0)}
    for order in (["NetIncomeLoss", "ProfitLoss"], ["ProfitLoss", "NetIncomeLoss"]):
        row, tag = RF.freshest_fact(slices, order, FUND_CIK, "2026-11-05")
        assert tag == order[0]
        assert row["value"] == {"NetIncomeLoss": 15.0, "ProfitLoss": 16.0}[order[0]]


def test_a_family_with_no_knowable_fact_stays_unresolved(fundamentals_store):
    """(d) nothing filed yet -- PARTIAL or resolved -- is still "unresolved"."""
    RF.use_store(fundamentals_store)
    panel = {e["family"]: e for e in RF.fundamentals_panel(FUND_CIK, "2023-01-01")}
    assert panel["equity"]["state"] == "unresolved"
    assert "PARTIAL" in panel["equity"]["detail"]
    assert panel["assets"]["state"] == "unresolved"
    assert panel["assets"]["detail"] == "no fact was knowable as of this filing date"
    assert "value" not in panel["equity"] and "value" not in panel["assets"]


def test_the_panel_says_how_long_each_facts_period_is(fundamentals_store):
    """`pit.value_as_of` groups by period_end alone, so a filer tagging both a
    full year and its Q4 under one end date can hand the panel either. The
    page must therefore SAY which period the number covers."""
    RF.use_store(fundamentals_store)
    panel = {e["family"]: e for e in RF.fundamentals_panel(FUND_CIK, "2026-02-10")}
    # Assets' own 2025Q4 fact was not filed until 2026-02-14, so as of the
    # 10-K's filing date the freshest knowable instant is still 2025-09-30 --
    # point-in-time, visible in the period column itself.
    assert panel["assets"]["period"] == "as at 2025-09-30"
    assert panel["revenue"]["period"] == "3 months ending 2025-12-31"


@pytest.mark.parametrize("start,end,expected", [
    (None, "2025-12-31", "as at 2025-12-31"),
    ("2025-10-01", "2025-12-31", "3 months ending 2025-12-31"),
    ("2025-07-01", "2025-12-31", "6 months ending 2025-12-31"),
    ("2025-04-01", "2025-12-31", "9 months ending 2025-12-31"),
    ("2025-01-01", "2025-12-31", "12 months ending 2025-12-31"),
])
def test_period_label_uses_ingest_fundamentals_own_buckets(start, end, expected):
    assert RF.period_label({"period_start": start, "period_end": end}) == expected


def test_the_rendered_panel_carries_value_concept_period_and_provenance(
        fundamentals_store):
    RF.use_store(fundamentals_store)
    html = RF.fundamentals_html(
        RF.fundamentals_panel(FUND_CIK, "2026-02-10"), "2026-02-10")
    assert "100.00 m USD" in html
    assert "Assets" in html
    assert "3 months ending 2025-12-31" in html
    assert REVENUE_ORIGINAL_FILED in html
    assert "unresolved" in html


def test_a_store_page_renders_the_fundamentals_it_ingested(fundamentals_store,
                                                           tmp_path):
    path = _render(fundamentals_store, ACC_NOW, tmp_path)
    html = Path(path).read_text()
    assert "Fundamentals as of the filing date" in html
    assert "100.00 m USD" in html


# -- the redirect itself -----------------------------------------------------
def test_a_store_redirects_the_two_fundamentals_readers(fundamentals_store):
    RF.use_store(fundamentals_store)
    assert RF.fundamentals_path() == fundamentals_store / IO.FUNDAMENTALS_NAME
    assert (RF.concept_resolution_path()
            == fundamentals_store / IO.CONCEPT_RESOLUTION_NAME)


def test_without_a_store_the_two_readers_are_the_research_artifacts():
    assert RF.ACTIVE_STORE is None
    assert RF.fundamentals_path() == RF.NF.FUNDAMENTALS_PATH
    assert RF.concept_resolution_path() == RF.NF.CONCEPT_RESOLUTION_CSV


def test_the_redirect_is_put_back_even_when_the_load_raises(fundamentals_store):
    """`numeric_features_e2` is an F5 module: nothing here may leave its path
    constants pointing at an app store."""
    before = (RF.NF.FUNDAMENTALS_PATH, RF.NF.CONCEPT_RESOLUTION_CSV)
    RF.use_store(fundamentals_store)
    with pytest.raises(RuntimeError):
        with RF.fundamentals_source():
            assert RF.NF.FUNDAMENTALS_PATH != before[0]
            raise RuntimeError("boom")
    assert (RF.NF.FUNDAMENTALS_PATH, RF.NF.CONCEPT_RESOLUTION_CSV) == before


def test_the_research_path_still_reads_f2s_own_records(fundamentals_store):
    RF.use_store(fundamentals_store)
    RF.use_store(None)
    with RF.fundamentals_source():
        assert RF.NF.FUNDAMENTALS_PATH == RF.DATA_DIR / "fundamentals_e2.parquet"
        assert (RF.NF.CONCEPT_RESOLUTION_CSV
                == RF.DATA_DIR / "f2" / "concept_resolution.csv")


# ===========================================================================
# the draw
# ===========================================================================
class FakeClient:
    """Stands in for EdgarClient in the draw tests. No network."""

    def __init__(self, tickers, with_10k):
        self._tickers = tickers
        self._with_10k = set(with_10k)
        self.request_count = 0
        self.headers = {"User-Agent": "test test@example.com"}

    def get_company_tickers(self, force: bool = False) -> dict:
        return {str(i): {"cik_str": cik, "ticker": tic, "title": f"{tic} CORP"}
                for i, (cik, tic) in enumerate(self._tickers)}

    def get_effective_recent(self, cik, cutoff, **kw) -> dict:
        self.request_count += 1
        if int(cik) in self._with_10k:
            return {"form": ["10-K"], "filingDate": ["2026-01-02"]}
        return {"form": ["8-K"], "filingDate": ["2026-01-02"]}


def _fake(n=40):
    tickers = [(900000 + i, f"T{i:03d}") for i in range(n)]
    return FakeClient(tickers, with_10k=[cik for cik, _ in tickers[::2]])


def test_the_draw_is_reproducible_for_a_seed(monkeypatch):
    monkeypatch.setattr(IO, "research_universe_ciks", lambda *a, **k: set())
    a = IO.draw_companies(5, seed=20260911, client=_fake(), verbose=False)
    b = IO.draw_companies(5, seed=20260911, client=_fake(), verbose=False)
    assert [d["ticker"] for d in a["drawn"]] == [d["ticker"] for d in b["drawn"]]


def test_a_different_seed_draws_a_different_sample(monkeypatch):
    monkeypatch.setattr(IO, "research_universe_ciks", lambda *a, **k: set())
    a = IO.draw_companies(5, seed=20260911, client=_fake(), verbose=False)
    b = IO.draw_companies(5, seed=1, client=_fake(), verbose=False)
    assert [d["ticker"] for d in a["drawn"]] != [d["ticker"] for d in b["drawn"]]


def test_the_draw_never_returns_a_research_universe_cik(monkeypatch):
    excluded = {900000 + i for i in range(0, 40, 2)}   # every 10-K filer
    monkeypatch.setattr(IO, "research_universe_ciks", lambda *a, **k: excluded)
    out = IO.draw_companies(5, seed=20260911, client=_fake(), verbose=False)
    assert out["drawn"] == [], "with every eligible CIK excluded, nothing is drawn"
    assert all(rec["cik"] not in excluded for rec in out["examined"])


def test_the_draw_records_every_candidate_it_rejected(monkeypatch):
    monkeypatch.setattr(IO, "research_universe_ciks", lambda *a, **k: set())
    out = IO.draw_companies(5, seed=20260911, client=_fake(), verbose=False)
    rejected = [r for r in out["examined"] if not r["accepted"]]
    assert len(out["examined"]) == len(out["drawn"]) + len(rejected)
    assert all(r["reason"] for r in rejected), "every rejection carries its reason"
    assert "no 10-K" in rejected[0]["reason"]


def test_the_draw_records_its_own_method():
    assert "default_rng" in IO.draw_companies.__doc__
    assert "company_tickers.json" in IO.DRAW_ELIGIBILITY
    assert "244" not in IO.DRAW_ELIGIBILITY or "research-universe" in IO.DRAW_ELIGIBILITY
