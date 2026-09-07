"""Offline tests for extract.py's E2 / phase-F3 extensions.

Test plan: `data/f3/F3_SPEC.md` §11 (T1-T21). Every test is OFFLINE -- no
socket, no network import on the F3 path, zero EDGAR GETs. Real-byte fixtures
live in `data/f3/fixtures/` (built by its `build_fixtures.py` from
`data/raw/documents/`); the pins that must hold against the WHOLE cached
corpus read `data/raw/documents/` directly and skip, loudly, if it is absent.

Run:  python3 -m pytest test_extract_e2.py -q
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest
from bs4 import BeautifulSoup

import extract as E

REPO_ROOT = Path(__file__).resolve().parent
FIXTURES = REPO_ROOT / "data" / "f3" / "fixtures"
REAL_CACHE = REPO_ROOT / "data" / "raw" / "documents"
REAL_DB = REPO_ROOT / "data" / "filings_metadata_e2.db"
E1_PARQUET = REPO_ROOT / "data" / "filings.parquet"

needs_cache = pytest.mark.skipif(
    not REAL_CACHE.exists(),
    reason="data/raw/documents/ absent -- corpus-pinning tests need F2's cache (still 0 GETs)",
)
needs_db = pytest.mark.skipif(
    not REAL_DB.exists(), reason="data/filings_metadata_e2.db absent",
)

# --- the fixture filings, and the cache keys their documents live under -----
ICE_BAKKT = "0001104659-22-112514"   # H4 verdict C: ICE furnishing BAKKT's results
HUMANA = "0000049071-16-000113"      # 8-word item-2.02 block before Item 7.01
SMALL_10Q = "0001193125-17-021855"
USBANCORP_10K = "0001193125-17-053947"

FIXTURE_FILINGS = [
    # accession, cik, form, filing_date, report_date, primary_document,
    # earnings filename, earnings relative path, earnings section type, fixture file
    (SMALL_10Q, 1222333, "10-Q", "2017-01-27", "2016-12-31", "d289743d10q.htm",
     None, None, None, "smallest10q_0001193125-17-021855_10q.htm"),
    (USBANCORP_10K, 36104, "10-K", "2017-02-23", "2016-12-31", "d291857d10k.htm",
     None, None, None, "usbancorp_0001193125-17-053947_10k.htm"),
    (ICE_BAKKT, 1571949, "8-K", "2022-11-08", None, "tm2229179d1_8k.htm",
     "tm2229179d1_8k.htm",
     "/Archives/edgar/data/1571949/000110465922112514/tm2229179d1_8k.htm",
     "8K_BODY", "ice_bakkt_0001104659-22-112514_8k.htm"),
    # Same CIK, same calendar quarter as the row above -> cell size 2, so the
    # broad gate fires; its document is deliberately NOT in the fixture cache,
    # which is also T2's cache_miss row.
    ("9999999999-22-000001", 1571949, "8-K", "2022-12-01", None, "missing_8k.htm",
     "missing_8k.htm",
     "/Archives/edgar/data/1571949/999999999922000001/missing_8k.htm",
     "EX99_PRESS_RELEASE", None),
    (HUMANA, 49071, "8-K", "2016-01-08", None, "humana8-k01082016.htm",
     "humana8-k01082016.htm",
     "/Archives/edgar/data/49071/000004907116000113/humana8-k01082016.htm",
     "8K_BODY", "humana_0000049071-16-000113_8k.htm"),
    # A periodic filing whose primary document is missing from the cache.
    ("9999999999-17-000002", 1222333, "10-Q", "2017-04-28", "2017-03-31",
     "missing_10q.htm", None, None, None, None),
]

FIXTURE_COMPANIES = [
    (1222333, "core", "technology", "FIXTURE SMALL FILER INC"),
    (36104, "core", "financials", "US BANCORP \\DE\\"),
    (1571949, "core", "financials", "Intercontinental Exchange, Inc."),
    (49071, "extension", "healthcare", "HUMANA INC"),
]


def _cache_key(relative_path: str) -> str:
    return relative_path.strip("/").replace("/", "_")


@pytest.fixture(scope="session")
def fixture_cache(tmp_path_factory) -> Path:
    """A documents cache holding only the fixture bytes, keyed exactly the way
    `EdgarClient.get_archive_document` keys its cache."""
    cache = tmp_path_factory.mktemp("f3_cache")
    for acc, cik, form, _fd, _rd, pdoc, _fn, rel, _sect, fixture in FIXTURE_FILINGS:
        if fixture is None:
            continue
        src = FIXTURES / fixture
        if not src.exists():
            pytest.skip(f"fixture {fixture} missing -- run data/f3/fixtures/build_fixtures.py")
        path = rel or E.periodic_relative_path(cik, acc, pdoc)
        (cache / _cache_key(path)).write_bytes(src.read_bytes())
    return cache


@pytest.fixture(scope="session")
def fixture_db(tmp_path_factory) -> Path:
    db = tmp_path_factory.mktemp("f3_db") / "filings_metadata_fixture.db"
    conn = sqlite3.connect(db)
    conn.execute("""CREATE TABLE companies (cik INTEGER PRIMARY KEY, ticker TEXT,
                    sector TEXT, company_name TEXT, stratum TEXT)""")
    conn.execute("""CREATE TABLE filings (accession_number TEXT PRIMARY KEY, cik INTEGER,
                    ticker TEXT, form TEXT, filing_date TEXT, report_date TEXT,
                    primary_document TEXT, items TEXT, has_earnings_item BOOLEAN,
                    earnings_doc_filename TEXT, earnings_doc_relative_path TEXT,
                    earnings_doc_section_type TEXT, earnings_doc_selection_confidence TEXT)""")
    for cik, stratum, sector, name in FIXTURE_COMPANIES:
        conn.execute("INSERT INTO companies VALUES (?,NULL,?,?,?)", (cik, sector, name, stratum))
    for acc, cik, form, fd, rd, pdoc, fn, rel, sect, _fx in FIXTURE_FILINGS:
        conn.execute(
            "INSERT INTO filings VALUES (?,?,NULL,?,?,?,?,NULL,?,?,?,?,?)",
            (acc, cik, form, fd, rd, pdoc, 1 if sect else 0, fn, rel, sect,
             "high" if sect else None),
        )
    conn.commit()
    conn.close()
    return db


@pytest.fixture()
def fixture_read(fixture_cache):
    return lambda rel: E.read_cached_document(rel, cache_dir=fixture_cache)


def _run(fixture_db, fixture_cache, tmp_path, **kwargs):
    out_dir = kwargs.pop("out_dir", tmp_path / "f3")
    return E.run(db_path=fixture_db, out_dir=out_dir,
                 out_parquet=tmp_path / "filings_e2.parquet",
                 cache_dir=fixture_cache, quiet=True, **kwargs), Path(out_dir)


# ===========================================================================
# T1 / T2 / T5 -- the cache-only reader and the 0-GET guarantee (R5, R9)
# ===========================================================================


def test_t1_read_cached_document_raises_cache_miss_and_never_fetches(tmp_path, monkeypatch):
    with pytest.raises(E.CacheMiss):
        E.read_cached_document("/Archives/edgar/data/1/2/nope.htm", cache_dir=tmp_path)

    # The F3 path must not construct (or even import) EdgarClient. Poison the
    # module in sys.modules so any import-and-use inside extract.py explodes.
    class Poison:
        def __getattr__(self, name):
            raise AssertionError(f"F3 touched edgar_client.{name} -- R5 forbids it")

    monkeypatch.setitem(sys.modules, "edgar_client", Poison())
    assert "EdgarClient" not in vars(E), "extract.py must not import EdgarClient on the F3 path"
    (tmp_path / _cache_key("/a/b.htm")).write_text("<p>hello</p>", encoding="utf-8")
    assert E.read_cached_document("/a/b.htm", cache_dir=tmp_path) == "<p>hello</p>"


def test_t1_cache_key_matches_edgar_client_rule(tmp_path):
    """Same key rule as EdgarClient.get_archive_document: leading slash
    normalised, then '/' -> '_'. A drift here silently re-reads nothing."""
    rel = "/Archives/edgar/data/49071/000004907116000113/humana8-k01082016.htm"
    (tmp_path / "Archives_edgar_data_49071_000004907116000113_humana8-k01082016.htm").write_text("x")
    assert E.read_cached_document(rel, cache_dir=tmp_path) == "x"
    assert E.read_cached_document(rel.lstrip("/"), cache_dir=tmp_path) == "x"


def test_t2_end_to_end_run_records_zero_gets_and_a_cache_miss_fail(fixture_db, fixture_cache, tmp_path):
    summary, out_dir = _run(fixture_db, fixture_cache, tmp_path, merge=True)
    assert summary["network_gets"] == 0
    audit = pd.read_parquet(out_dir / "extraction_audit.parquet")
    misses = audit[audit["reason_code"] == "cache_miss"]
    # 1 earnings attempt + 2 periodic attempts, all FAIL rows, none fetched
    assert len(misses) == 3
    assert set(misses["extraction_status"]) == {"FAIL"}
    assert summary["cache_miss"] == 3
    sections = pd.read_parquet(tmp_path / "filings_e2.parquet")
    assert "9999999999-22-000001" not in set(sections["accession_number"])


# ===========================================================================
# T3 -- E1's frozen artifacts are refused by name
# ===========================================================================


@pytest.mark.parametrize("argv", [
    ["--db", "data/filings_metadata.db"],
    ["--out-parquet", "data/filings.parquet"],
    ["--db", str(REPO_ROOT / "data" / "filings_metadata.db")],
])
def test_t3_e1_paths_exit_2(argv, capsys):
    assert E.main(argv) == 2
    assert "frozen artifact" in capsys.readouterr().out


def test_t3_assert_not_e1_path_accepts_e2_paths():
    E.assert_not_e1_path(E.DB_PATH, E.PARQUET_PATH, E.OUT_DIR)


# ===========================================================================
# T4 -- parse once == parse twice (R7 / C4)
# ===========================================================================


def _double_parse_reference(read, cik, accession, primary_document, form):
    """What the E1 code did: a fresh read + soup + TOC scan PER SECTION."""
    out = {}
    for section in E.PERIODIC_SECTIONS:
        html_text = E.strip_sgml_document_wrapper(
            read(E.periodic_relative_path(cik, accession, primary_document)))
        soup = BeautifulSoup(html_text, E._PARSER)
        toc = E.find_toc_item_anchors(soup)
        out[section] = E._locate_one_section(
            html_text, toc, form, section, E._LazyFullText(html_text))
    return out


@pytest.mark.parametrize("acc,cik,pdoc,form", [
    (SMALL_10Q, 1222333, "d289743d10q.htm", "10-Q"),
    (USBANCORP_10K, 36104, "d291857d10k.htm", "10-K"),
])
def test_t4_parse_once_equals_parse_twice(fixture_read, acc, cik, pdoc, form):
    once = E.extract_periodic_sections(fixture_read, cik, acc, pdoc, form)
    twice = _double_parse_reference(fixture_read, cik, acc, pdoc, form)
    for section in E.PERIODIC_SECTIONS:
        a, b = once[section], twice[section]
        assert a.text == b.text
        assert (a.method, a.confidence, a.reason_code, a.status) == \
               (b.method, b.confidence, b.reason_code, b.status)


def test_t4_extract_item_section_wrapper_agrees(fixture_read):
    both = E.extract_periodic_sections(fixture_read, 1222333, SMALL_10Q, "d289743d10q.htm", "10-Q")
    for section in E.PERIODIC_SECTIONS:
        one = E.extract_item_section(fixture_read, 1222333, SMALL_10Q, "d289743d10q.htm",
                                      "10-Q", section)
        assert one.text == both[section].text


def test_t4_full_document_text_is_computed_at_most_once():
    lazy = E._LazyFullText("<p>alpha beta</p>")
    calls = []
    original = E.html_fragment_to_text
    try:
        E.html_fragment_to_text = lambda frag: (calls.append(frag), original(frag))[1]
        assert lazy.get() == lazy.get() == "alpha beta"
    finally:
        E.html_fragment_to_text = original
    assert len(calls) == 1


# ===========================================================================
# T5 / T6 -- the population gate ships BROAD (R1, §4)
# ===========================================================================


def test_t5_gate_levels_and_cell_key():
    assert E.filing_quarter("2021-02-08") == "2021Q1"
    assert E.filing_quarter("2022-11-08") == "2022Q4"
    assert E.population_gate_level(1, False) == "OK"
    assert E.population_gate_level(1, True) == "OK"
    assert E.population_gate_level(2, True) == "WARN_MULTI"
    assert E.population_gate_level(2, False) == "WARN_MULTI_NOSIG"
    assert E.population_gate_level(None, False) == "OK"


@needs_db
def test_t5_all_nine_h4_c_rows_are_flagged_by_the_shipped_gate():
    """The gate's whole justification: recall 9/9 on H4's C (wrong-population)
    rows. The narrowed variant re-measured 8/9 -- see T6."""
    ledger = pd.read_csv(REPO_ROOT / "data" / "hardening" / "h4_verdict_ledger.csv")
    c_rows = ledger[ledger["verdict"] == "C"]
    assert len(c_rows) == 9
    conn = E.open_readonly(REAL_DB)
    cells = E.load_quarter_cells(conn)
    conn.close()
    for _, r in c_rows.iterrows():
        cell = cells[(int(r["cik"]), E.filing_quarter(r["filing_date"]))]
        # The shipped gate is multi-cell alone; the signature only ranks.
        for signature in (True, False):
            assert E.population_gate_level(cell, signature).startswith("WARN_MULTI"), \
                f"{r['accession_number']} ({r['company_name']}) not flagged"


@needs_db
def test_t5_gate_census_reproduces_h4(tmp_path):
    """1,519 multi-cell selections of 10,567 (14.37%) -- H4's number exactly."""
    conn = E.open_readonly(REAL_DB)
    cells = E.load_quarter_cells(conn)
    rows = conn.execute(
        "SELECT cik, filing_date FROM filings WHERE form='8-K' AND has_earnings_item=1 "
        "AND earnings_doc_section_type IS NOT NULL").fetchall()
    conn.close()
    assert len(rows) == 10567
    multi = sum(1 for cik, fd in rows if cells[(int(cik), E.filing_quarter(fd))] > 1)
    assert multi == 1519


def test_t6_narrowed_variant_would_have_dropped_the_ice_bakkt_row(fixture_read):
    """WHY V1 was rejected, encoded as a test.

    `0001104659-22-112514` is ICE furnishing BAKKT's results -- H4's loudest
    error and the row it named as "worth naming loudly". H4's proposed
    narrowing suppresses it, because the text says "quarterly results": a
    results-announcement signature cannot tell WHOSE results are announced.
    """
    text = E.html_fragment_to_text(E.strip_sgml_document_wrapper(fixture_read(
        "/Archives/edgar/data/1571949/000110465922112514/tm2229179d1_8k.htm")))
    h4_markers = ("today reported", "announced results", "per diluted share", "quarterly results")
    assert any(m in text.lower() for m in h4_markers), "H4's markers do match this text"

    result = E.extract_earnings_document(
        fixture_read, "/Archives/edgar/data/1571949/000110465922112514/tm2229179d1_8k.htm",
        "8K_BODY", {"quarter_cell_size": 2})
    # V1 (narrowed) would have suppressed it; the shipped V0 gate flags it.
    assert result.population_gate == "WARN_MULTI_NOSIG"
    assert "earnings_population_gate" in result.flags
    assert result.status == "FLAGGED"


def test_t6_signature_is_a_severity_field_never_a_suppressor(fixture_read):
    rel = "/Archives/edgar/data/49071/000004907116000113/humana8-k01082016.htm"
    sole = E.extract_earnings_document(fixture_read, rel, "8K_BODY", {"quarter_cell_size": 1})
    multi = E.extract_earnings_document(fixture_read, rel, "8K_BODY", {"quarter_cell_size": 3})
    assert sole.population_gate == "OK"
    assert multi.population_gate.startswith("WARN_MULTI")
    # Same document, same text: the gate never changes what is extracted.
    assert sole.text == multi.text


# ===========================================================================
# T7 / T8 / T9 -- 8K_BODY item-2.02 slicing (R2, §5)
# ===========================================================================


def test_t7_humana_slice_starts_at_item_202_and_ends_at_end_of_document(fixture_read):
    rel = "/Archives/edgar/data/49071/000004907116000113/humana8-k01082016.htm"
    whole = E.html_fragment_to_text(E.strip_sgml_document_wrapper(fixture_read(rel)))
    result = E.extract_earnings_document(fixture_read, rel, "8K_BODY", {"quarter_cell_size": 1})

    assert result.extraction_method if False else result.method == "item202_slice"
    assert result.item202_prefix_chars == 1269
    assert result.text == whole[1269:]              # to END OF DOCUMENT
    assert result.text.lower().startswith("item 2.02")
    assert result.text.endswith(whole[-40:])         # nothing trimmed off the tail
    # The 2.02 block itself is 8 words before Item 7.01 -- recorded, and
    # flagged, but NEVER used as the end boundary (R2).
    assert result.item202_block_words == 8
    assert "earnings_item202_block_thin" in result.flags
    assert len(result.text.split()) > 400


def test_t8_missing_item_202_keeps_the_whole_document(tmp_path):
    (tmp_path / _cache_key("/a/no202.htm")).write_text(
        "<p>" + ("Corporate news release with no item heading at all. " * 30) + "</p>",
        encoding="utf-8")
    read = lambda rel: E.read_cached_document(rel, cache_dir=tmp_path)  # noqa: E731
    result = E.extract_earnings_document(read, "/a/no202.htm", "8K_BODY", {"quarter_cell_size": 1})
    assert result.method == "whole_document"
    assert "earnings_item202_missing" in result.flags
    assert result.item202_prefix_chars is None
    assert result.text.strip(), "never an empty section"
    assert result.status == "FLAGGED"


def test_t9_slicing_does_not_apply_to_ex99_press_releases(fixture_read):
    rel = "/Archives/edgar/data/49071/000004907116000113/humana8-k01082016.htm"
    whole = E.html_fragment_to_text(E.strip_sgml_document_wrapper(fixture_read(rel)))
    as_ex99 = E.extract_earnings_document(fixture_read, rel, "EX99_PRESS_RELEASE",
                                           {"quarter_cell_size": 1})
    assert as_ex99.method == "whole_document"
    assert as_ex99.text == whole
    assert as_ex99.item202_prefix_chars is None
    assert not any(f.startswith("earnings_item202") for f in as_ex99.flags)


def test_t7_large_prefix_is_flagged_not_hidden(tmp_path):
    body = "cover page boilerplate " * 260          # > 4,000 chars
    (tmp_path / _cache_key("/a/big.htm")).write_text(
        f"<p>{body}</p><p>Item 2.02 Results of Operations.</p><p>{'result detail ' * 400}</p>",
        encoding="utf-8")
    read = lambda rel: E.read_cached_document(rel, cache_dir=tmp_path)  # noqa: E731
    result = E.extract_earnings_document(read, "/a/big.htm", "8K_BODY", {"quarter_cell_size": 1})
    assert result.item202_prefix_chars > E.ITEM202_PREFIX_LARGE_CHARS
    assert "earnings_item202_prefix_large" in result.flags


# ===========================================================================
# T10 -- the stub resolver triggers on WORD COUNT alone (R4 / C7)
# ===========================================================================

STUB_PHRASINGS = {
    # filer / filing -> the exact phrasing E1's language gate could not see
    "sempra_0000086521-17-000017":
        "The information required by Item 7 is set forth in Management's Discussion "
        "and Analysis of Financial Condition and Results of Operations in the Annual "
        "Report, on pages 2 through 78.",
    "usbancorp_0001193125-17-053947":
        "Information in response to this Item 7 can be found in the Company's 2016 "
        "Annual Report on pages 22 to 71, which is incorporated into this report by "
        "reference.",
    "jpmorgan_0000019617-17-000314":
        "Management's discussion and analysis\nappears on\npages 36-138.",
}


@pytest.mark.parametrize("name,phrasing", sorted(STUB_PHRASINGS.items()))
def test_t10_all_three_phrasings_enter_the_resolver_on_word_count_alone(name, phrasing, tmp_path):
    html = f"<html><body><p>Item 7. Management's Discussion and Analysis</p><p>{phrasing}</p></body></html>"
    result = E._maybe_resolve_mda_stub(
        E.html_fragment_to_text(html), "10-K", "MDA", html, None, E._LazyFullText(html))
    assert result is not None, f"{name} did not enter the resolver"
    assert result.method == "incorporated_by_reference_unresolved"
    assert result.confidence == "low"
    assert result.reason_code in ("mda_stub_external_document", "mda_stub_unresolved_same_doc")
    assert result.status == "FLAGGED"


@pytest.mark.parametrize("name,phrasing", sorted(STUB_PHRASINGS.items()))
def test_t10_c12_makes_the_evidence_regex_right_too(name, phrasing):
    """The regex is demoted to evidence (R4), but it should still be correct:
    all three phrasings now match, where E1's version matched none."""
    assert E.STUB_REFERENCE_LANGUAGE_RE.search(phrasing), name


def test_t10_external_document_phrasing_gets_its_own_reason_code():
    external = ("The information required by this item is incorporated by reference to "
                "Nucor's 2017 Annual Report to Stockholders, page 3.")
    same_doc = ("The index to Management's Discussion and Analysis is presented in the "
                "Financial Table of Contents of this report.")
    assert E.classify_stub_reason(external) == "mda_stub_external_document"
    assert E.classify_stub_reason(same_doc) == "mda_stub_unresolved_same_doc"


def test_t10_a_long_mda_never_enters_the_resolver():
    long_text = "word " * (E.MDA_STUB_WORD_CEILING + 10)
    assert E._maybe_resolve_mda_stub(long_text, "10-K", "MDA", "<html></html>", None,
                                      E._LazyFullText("<html></html>")) is None
    # and the resolver is 10-K MD&A only
    assert E._maybe_resolve_mda_stub("short", "10-Q", "MDA", "<html></html>", None,
                                      E._LazyFullText("<html></html>")) is None


def test_t10_usbancorp_real_bytes_are_a_flagged_external_document_stub(fixture_read):
    """The measured case that E1 shipped at heading_regex/low with no stub
    reason at all -- and which reaches the resolver only because C7 dropped
    the language gate AND the resolver now runs on the fallback path too."""
    result = E.extract_periodic_sections(
        fixture_read, 36104, USBANCORP_10K, "d291857d10k.htm", "10-K")["MDA"]
    assert result.reason_code == "mda_stub_external_document"
    assert result.confidence == "low"
    assert result.stub_language_present is True
    assert "heading_regex_fallback" in result.flags


# ===========================================================================
# T11 / T12 -- flag, never filter; flagged is never high confidence (R3 / C6)
# ===========================================================================


@pytest.mark.parametrize("flag", sorted(
    code for code, status in E.REASON_STATUS.items() if status == E.STATUS_FLAGGED))
def test_t11_no_flagged_row_is_ever_high_confidence(flag):
    result = E._finish_section(E.ExtractionResult(
        text="word " * 5000, method="anchor", confidence="high",
        form="10-K", section_type="MDA", flags=[flag]))
    assert result.status == E.STATUS_FLAGGED
    assert result.confidence != "high"


def test_t11_ok_rows_keep_high_confidence():
    # Real prose, not `"word " * 5000`: since P5 the garble screen (N1) reads
    # the English-word share of the text, and a repeated nonsense token scores
    # like a font-map dump.
    result = E._finish_section(E.ExtractionResult(
        text="Management's discussion and analysis. " + (
            "Net revenue for the three months ended June 30 increased due to "
            "higher demand in all of our markets and the company reported "
            "operating income of one billion for the quarter. " * 300),
        method="anchor", confidence="high", form="10-K", section_type="MDA"))
    assert result.status == E.STATUS_OK
    assert result.confidence == "high"
    assert result.reason_code == "ok"


def test_t11_a_flag_can_never_be_hidden_by_reason_precedence():
    """`mda_stub_resolved` is an OK code, but a row that also carries a
    FLAGGED code is FLAGGED -- precedence picks the primary reason, it does
    not decide the status."""
    result = E.ExtractionResult(text="x", method="anchor", confidence="high",
                                form="10-K", section_type="MDA",
                                flags=["mda_stub_resolved", "head_foreign_item"])
    assert result.reason_code == "mda_stub_resolved"
    assert result.status == E.STATUS_FLAGGED


def test_t12_below_floor_rows_are_flagged_but_never_dropped(fixture_db, fixture_cache, tmp_path, monkeypatch):
    baseline, out_a = _run(fixture_db, fixture_cache, tmp_path / "a", merge=True)
    sections_a = pd.read_parquet(tmp_path / "a" / "filings_e2.parquet")

    # Raise every floor absurdly high: the SAME rows must still be present,
    # with byte-identical text -- only the flag/status/confidence change.
    monkeypatch.setattr(E, "MIN_SECTION_WORDS",
                        {k: 10 ** 9 for k in E.MIN_SECTION_WORDS})
    _run(fixture_db, fixture_cache, tmp_path / "b", merge=True)
    sections_b = pd.read_parquet(tmp_path / "b" / "filings_e2.parquet")

    key = ["accession_number", "section_type"]
    assert sorted(map(tuple, sections_a[key].values)) == sorted(map(tuple, sections_b[key].values))
    merged = sections_a.merge(sections_b, on=key, suffixes=("_a", "_b"))
    assert (merged["text_a"] == merged["text_b"]).all(), "a floor change must never alter text"
    assert bool(merged["below_length_floor_b"].all())
    assert not (merged["extraction_confidence_b"] == "high").any()


def test_t12_min_section_words_is_the_only_thing_the_flag_reads():
    text = "word " * 100
    assert "below_length_floor" in E._finish_section(E.ExtractionResult(
        text=text, method="anchor", confidence="high", form="10-K",
        section_type="MDA")).flags
    assert "below_length_floor" not in E._finish_section(E.ExtractionResult(
        text=text, method="anchor", confidence="high", form="10-Q",
        section_type="RISK_FACTORS")).flags


# ===========================================================================
# T13 -- point-in-time discipline (HANDOFF §7)
# ===========================================================================

F2_FREEZE_DATE = "2026-08-31"


def test_t13_dates_are_carried_through_unchanged(fixture_db, fixture_cache, tmp_path):
    _run(fixture_db, fixture_cache, tmp_path, merge=True)
    sections = pd.read_parquet(tmp_path / "filings_e2.parquet")
    db_rows = {a: (fd, rd) for a, _c, _f, fd, rd, *_ in FIXTURE_FILINGS}
    for _, row in sections.iterrows():
        expected_filing, expected_report = db_rows[row["accession_number"]]
        assert row["filing_date"] == expected_filing
        assert (row["report_date"] == expected_report
                or (expected_report is None and pd.isna(row["report_date"])))
    assert (sections["filing_date"] <= F2_FREEZE_DATE).all()


@needs_db
def test_t13_no_target_filing_postdates_the_f2_freeze():
    conn = E.open_readonly(REAL_DB)
    latest = conn.execute(
        f"SELECT max(filing_date) FROM filings WHERE {E._TARGET_PREDICATE.replace('f.', '')}"
    ).fetchone()[0]
    conn.close()
    assert latest <= F2_FREEZE_DATE


def test_t13_nothing_in_the_f3_path_sorts_on_report_date():
    source = (REPO_ROOT / "extract.py").read_text()
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or "report_date" not in stripped:
            continue
        assert "sort" not in stripped.lower() and "ORDER BY" not in stripped, stripped


# ===========================================================================
# T14 -- E1 regression: the locator's behaviour is unchanged (R7 / C13)
# ===========================================================================

# Drawn with random.Random(20260826) over data/filings.parquet's `anchor` and
# `whole_document` rows, excluding 8K_BODY (which R2's slicing legitimately
# changes). Pinned by accession so a future locator change has to break a test.
E1_BYTE_IDENTICAL_ROWS = [
    ("0001104659-23-111585", 310158, "8-K", "EX99_PRESS_RELEASE"),
    ("0001193125-26-191457", 789019, "8-K", "EX99_PRESS_RELEASE"),
    ("0001628280-25-051071", 797468, "10-Q", "RISK_FACTORS"),
    ("0001551152-24-000026", 1551152, "8-K", "EX99_PRESS_RELEASE"),
    ("0000034088-23-000054", 34088, "8-K", "EX99_PRESS_RELEASE"),
    ("0000070858-23-000264", 70858, "8-K", "EX99_PRESS_RELEASE"),
    ("0000078003-24-000103", 78003, "8-K", "EX99_PRESS_RELEASE"),
    ("0000200406-23-000102", 200406, "10-Q", "MDA"),
    ("0000858877-24-000007", 858877, "10-Q", "MDA"),
    ("0000950170-24-087835", 789019, "8-K", "EX99_PRESS_RELEASE"),
    ("0000093410-26-000110", 93410, "8-K", "EX99_PRESS_RELEASE"),
    ("0001163165-25-000025", 1163165, "10-Q", "MDA"),
]

# The classes that legitimately DO change, enumerated with their reason.
E1_CLASSES_THAT_CHANGE = {
    "8K_BODY": "R2: the slice now starts at the first Item 2.02, not at the cover page.",
    "incorporated_by_reference_*": "R4: the stub resolver now triggers on word count alone, "
                                    "so more short 10-K MD&As enter it (E1's own 9 resolved "
                                    "stubs still resolve byte-identically -- pinned below).",
}


@needs_cache
@pytest.mark.skipif(not E1_PARQUET.exists(), reason="data/filings.parquet absent")
@pytest.mark.parametrize("accession,cik,form,section", E1_BYTE_IDENTICAL_ROWS)
def test_t14_e1_rows_re_extract_byte_identical(accession, cik, form, section):
    e1 = pd.read_parquet(E1_PARQUET)
    row = e1[(e1["accession_number"] == accession) & (e1["section_type"] == section)].iloc[0]
    read = E.read_cached_document
    if form in ("10-K", "10-Q"):
        result = E.extract_periodic_sections(read, cik, accession, row["source_document"], form)[section]
    else:
        result = E.extract_earnings_document(
            read, E.periodic_relative_path(cik, accession, row["source_document"]),
            section, {"quarter_cell_size": 1})
    assert result.text == row["text"]


@needs_cache
@pytest.mark.skipif(not E1_PARQUET.exists(), reason="data/filings.parquet absent")
def test_t14_e1_resolved_stubs_still_resolve_byte_identical():
    """E1's 9 CVX/XOM/JPM resolved stubs -- the class C7 most plausibly could
    have broken."""
    e1 = pd.read_parquet(E1_PARQUET)
    stubs = e1[e1["extraction_method"] == "incorporated_by_reference_resolved"]
    assert len(stubs) == 9
    for _, row in stubs.iterrows():
        result = E.extract_periodic_sections(
            E.read_cached_document, int(row["cik"]), row["accession_number"],
            row["source_document"], row["form"])["MDA"]
        assert result.text == row["text"], row["accession_number"]
        assert result.reason_code == "mda_stub_resolved"


def test_t14_the_changing_classes_are_named():
    assert set(E1_CLASSES_THAT_CHANGE) == {"8K_BODY", "incorporated_by_reference_*"}


# ===========================================================================
# T15 -- shard determinism, atomicity, idempotent resume (C9)
# ===========================================================================


def test_t15_plan_shards_is_a_pure_function_of_the_sorted_order(fixture_db):
    conn = E.open_readonly(fixture_db)
    filings = E.load_target_filings(conn, "all")
    conn.close()
    assert list(filings["form"]) == sorted(filings["form"])
    a = E.plan_shards(filings, 2)
    b = E.plan_shards(filings, 2)
    assert [list(x["accession_number"]) for x in a] == [list(x["accession_number"]) for x in b]
    assert sum(len(x) for x in a) == len(filings)
    assert E.plan_shards(filings, 10 ** 6)[0].equals(filings)


def test_t15_two_runs_produce_byte_identical_shards_and_resume_is_a_no_op(
        fixture_db, fixture_cache, tmp_path):
    out_dir = tmp_path / "f3"
    first, _ = _run(fixture_db, fixture_cache, tmp_path, out_dir=out_dir, shard_size=2)
    shard_files = sorted((out_dir / "shards").glob("*.parquet"))
    before = {p.name: p.read_bytes() for p in shard_files}
    assert before, "no shards written"

    second, _ = _run(fixture_db, fixture_cache, tmp_path, out_dir=out_dir, shard_size=2)
    after = {p.name: p.read_bytes() for p in sorted((out_dir / "shards").glob("*.parquet"))}
    assert before == after, "a resume rewrote shard bytes"
    assert all(s.get("skipped") for s in second["shards"]), "resume re-extracted a done shard"
    assert any(not s.get("skipped") for s in first["shards"])


def test_t15_deleting_one_done_marker_recomputes_exactly_that_shard(
        fixture_db, fixture_cache, tmp_path):
    out_dir = tmp_path / "f3"
    _run(fixture_db, fixture_cache, tmp_path, out_dir=out_dir, shard_size=2)
    markers = sorted((out_dir / "shards").glob("*.done"))
    victim = markers[0]
    victim.unlink()
    summary, _ = _run(fixture_db, fixture_cache, tmp_path, out_dir=out_dir, shard_size=2)
    recomputed = [s for s in summary["shards"] if not s.get("skipped")]
    assert len(recomputed) == 1
    assert f"{recomputed[0]['segment']}_{recomputed[0]['shard']:04d}.done" == victim.name


def test_t15_a_limited_run_never_satisfies_a_full_run(fixture_db, fixture_cache, tmp_path):
    out_dir = tmp_path / "f3"
    _run(fixture_db, fixture_cache, tmp_path, out_dir=out_dir, shard_size=10, limit=1)
    summary, _ = _run(fixture_db, fixture_cache, tmp_path, out_dir=out_dir, shard_size=10)
    assert all(not s.get("skipped") for s in summary["shards"]), \
        "a --limit shard was mistaken for a full one"


def test_t15_merge_refuses_duplicate_sections(fixture_db, fixture_cache, tmp_path):
    out_dir = tmp_path / "f3"
    _run(fixture_db, fixture_cache, tmp_path, out_dir=out_dir, shard_size=10)
    shards = out_dir / "shards"
    original = sorted(p for p in shards.glob("*.parquet") if not p.name.endswith(".audit.parquet"))[0]
    stem = original.name[: -len(".parquet")]
    (shards / "dupe_9999.parquet").write_bytes(original.read_bytes())
    (shards / "dupe_9999.audit.parquet").write_bytes((shards / f"{stem}.audit.parquet").read_bytes())
    (shards / "dupe_9999.done").write_text(json.dumps({"limit": None}))
    with pytest.raises(ValueError, match="duplicate"):
        E.merge_shards(out_dir)


def test_t15_no_tmp_files_survive_a_run(fixture_db, fixture_cache, tmp_path):
    _, out_dir = _run(fixture_db, fixture_cache, tmp_path, merge=True)
    assert not list(out_dir.rglob("*.tmp"))


def test_t15_segment_shard_sizes_match_the_spec():
    assert E.DEFAULT_SHARD_SIZE == {"earnings": 1500, "10-K": 250, "10-Q": 500}


@needs_db
def test_t15_the_real_corpus_plans_34_shards():
    """3 segments / 34 shards -- the plan P2 executes."""
    conn = E.open_readonly(REAL_DB)
    counts, shards = {}, {}
    for segment in E.SEGMENTS:
        filings = E.load_target_filings(conn, segment)
        counts[segment] = len(filings)
        shards[segment] = len(E.plan_shards(filings, E.DEFAULT_SHARD_SIZE[segment]))
    conn.close()
    assert counts == {"earnings": 10567, "10-K": 2445, "10-Q": 7509}
    assert shards == {"earnings": 8, "10-K": 10, "10-Q": 16}
    assert sum(shards.values()) == 34


# ===========================================================================
# T16 -- audit arithmetic (§7.3)
# ===========================================================================


def test_t16_attempts_equal_the_status_sum_and_the_rollup_reconciles(
        fixture_db, fixture_cache, tmp_path):
    _, out_dir = _run(fixture_db, fixture_cache, tmp_path, merge=True)
    audit = pd.read_parquet(out_dir / "extraction_audit.parquet")
    sections = pd.read_parquet(tmp_path / "filings_e2.parquet")

    counts = audit["extraction_status"].value_counts()
    assert len(audit) == sum(counts.get(s, 0) for s in
                             ("OK", "FLAGGED", "ITEM_ABSENT_FROM_TOC", "FAIL"))
    assert len(sections) == counts.get("OK", 0) + counts.get("FLAGGED", 0)
    # 3 periodic filings x 2 sections + 3 earnings filings x 1
    assert len(audit) == 9

    rollup = pd.read_csv(out_dir / "per_filer_rollup.csv")
    assert rollup["n_attempt"].sum() == len(audit)
    for col in ("n_ok", "n_flagged", "n_item_absent_from_toc", "n_fail"):
        assert rollup[col].sum() == int(counts.get(col.replace("n_", "").upper(), 0))
    assert list(rollup["fail_rate"]) == sorted(rollup["fail_rate"], reverse=True)


def test_t16_every_reason_code_is_in_the_closed_enum(fixture_db, fixture_cache, tmp_path):
    _, out_dir = _run(fixture_db, fixture_cache, tmp_path, merge=True)
    audit = pd.read_parquet(out_dir / "extraction_audit.parquet")
    assert set(audit["reason_code"]) <= set(E.REASON_STATUS)
    assert set(E.REASON_PRECEDENCE) == set(E.REASON_STATUS)
    for _, row in audit.iterrows():
        assert E.primary_reason_code(list(row["flags"])) == row["reason_code"]


def test_t16_failures_csv_and_gate_and_length_tables_exist(fixture_db, fixture_cache, tmp_path):
    _, out_dir = _run(fixture_db, fixture_cache, tmp_path, merge=True)
    failures = pd.read_csv(out_dir / "extraction_failures.csv")
    audit = pd.read_parquet(out_dir / "extraction_audit.parquet")
    assert len(failures) == int(audit["extraction_status"].isin(["FAIL", "FLAGGED"]).sum())

    gate = pd.read_csv(out_dir / "population_gate.csv")
    assert set(gate["gate_level"]) <= {"WARN_MULTI", "WARN_MULTI_NOSIG"}
    assert list(gate.columns[-2:]) == ["verdict", "verdict_note"]
    assert gate[["verdict", "verdict_note"]].isna().all().all()

    lengths = pd.read_csv(out_dir / "length_distribution.csv")
    assert {"form", "section_type", "slice", "current_floor", "n_below_current_floor"} \
        <= set(lengths.columns)
    assert {f"n_below_{v}" for v in E.FLOOR_CANDIDATE_LADDER} <= set(lengths.columns)
    assert "all" in set(lengths["slice"])


def test_t16_manifest_records_the_run(fixture_db, fixture_cache, tmp_path):
    summary, out_dir = _run(fixture_db, fixture_cache, tmp_path, merge=True)
    manifest = json.loads((out_dir / "run_manifest.json").read_text())
    entry = manifest["runs"][-1]
    assert entry["network_gets"] == 0
    assert entry["run_id"] == summary["run_id"]
    assert entry["extractor_version"] == E.EXTRACTOR_VERSION
    assert entry["constants"]["MDA_STUB_WORD_CEILING"] == E.MDA_STUB_WORD_CEILING
    assert entry["constants"]["MIN_SECTION_WORDS"]["8-K|EX99_PRESS_RELEASE"] == 250
    assert entry["constants"]["MIN_PROSE_WORDS"] == 40
    assert entry["db_sha256"] and entry["extract_py_sha256"]
    # a second run APPENDS rather than erasing the record it resumed
    _run(fixture_db, fixture_cache, tmp_path, out_dir=out_dir, merge=True)
    assert len(json.loads((out_dir / "run_manifest.json").read_text())["runs"]) >= 2


def test_t16_limit_is_recorded_so_a_truncated_run_is_obvious(fixture_db, fixture_cache, tmp_path):
    summary, out_dir = _run(fixture_db, fixture_cache, tmp_path, limit=1)
    assert summary["limit"] == 1
    marker = json.loads(sorted((out_dir / "shards").glob("*.done"))[0].read_text())
    assert marker["limit"] == 1
    with pytest.raises(SystemExit):
        _run(fixture_db, fixture_cache, tmp_path, limit=1, merge=True)


# ===========================================================================
# T17 -- schema pin (C3)
# ===========================================================================


def test_t17_output_and_audit_schemas_are_pinned(fixture_db, fixture_cache, tmp_path):
    _, out_dir = _run(fixture_db, fixture_cache, tmp_path, merge=True)
    sections = pd.read_parquet(tmp_path / "filings_e2.parquet")
    audit = pd.read_parquet(out_dir / "extraction_audit.parquet")

    assert list(sections.columns) == E.OUTPUT_COLUMNS
    assert list(audit.columns) == E.AUDIT_COLUMNS
    # R6: CIK-keyed. `ticker` is NULL for all 45,545 E2 rows, so it is absent.
    assert "ticker" not in sections.columns and "ticker" not in audit.columns
    assert "cik" in sections.columns

    assert sections["cik"].dtype.kind == "i"
    assert sections["below_length_floor"].dtype == bool
    assert str(sections["quarter_cell_size"].dtype) == "Int64"
    assert str(sections["results_signature_present"].dtype) == "boolean"
    assert sections["word_count"].dtype.kind == "i"
    assert all(isinstance(v, (list, tuple)) or hasattr(v, "tolist") for v in sections["flags"])
    assert set(sections["extraction_status"]) <= {"OK", "FLAGGED"}
    assert (sections["extractor_version"] == E.EXTRACTOR_VERSION).all()
    assert sections["run_id"].nunique() == 1


# ===========================================================================
# T18 -- the edge-handler registry (R8 / C11)
# ===========================================================================


def test_t18_the_registry_holds_exactly_the_named_p5_handlers():
    """The registry was empty at P1 by design (P0's five dialect classes are
    all handled where they belong). P3's triage produced its first member:
    N6 / NIKE. Any further growth is a deliberate, documented act."""
    assert [h.name for h in E.EDGE_HANDLERS] == ["nike_10q_mda_shared_toc_anchor"]
    assert E.dead_edge_handlers({}) == ["nike_10q_mda_shared_toc_anchor"]
    assert E.dead_edge_handlers({"nike_10q_mda_shared_toc_anchor": 21}) == []


def test_t18_every_registered_handler_has_a_name_docstring_and_predicate():
    for handler in E.EDGE_HANDLERS:
        assert handler.name and isinstance(handler.name, str)
        assert callable(handler.applies_to) and callable(handler.handler)
        assert (handler.handler.__doc__ or "").strip(), f"{handler.name} has no docstring"
        assert handler.reason and len(handler.reason) > 20


def test_t18_handlers_fire_only_on_their_predicate_and_are_counted():
    def _tag(result, cik, form, section_type, ctx=None):
        """Test handler. Filer: fixture CIK 42, motivated by nothing real,
        verified against this test only."""
        result.flags.append("head_keyword_absent")
        return result

    handler = E.EdgeHandler(
        name="fixture_cik42_tag",
        applies_to=lambda cik, form, section: cik == 42 and form == "10-K",
        reason="A synthetic handler exercising the registry mechanism only.",
        handler=_tag)

    fired: dict = {}
    matched = E.apply_edge_handlers(
        E.ExtractionResult(text="x", method="anchor", confidence="high",
                           form="10-K", section_type="MDA"),
        42, "10-K", "MDA", handlers=[handler], fired=fired)
    assert "head_keyword_absent" in matched.flags
    assert fired == {"fixture_cik42_tag": 1}

    fired2: dict = {}
    unmatched = E.apply_edge_handlers(
        E.ExtractionResult(text="x", method="anchor", confidence="high",
                           form="10-Q", section_type="MDA"),
        42, "10-Q", "MDA", handlers=[handler], fired=fired2)
    assert unmatched.flags == []
    assert fired2 == {}


def test_t18_a_handler_that_never_fires_is_reported_dead(monkeypatch):
    handler = E.EdgeHandler(name="never_fires", applies_to=lambda *a: False,
                            reason="A handler that matches nothing, to test DEAD detection.",
                            handler=lambda *a: None)
    monkeypatch.setattr(E, "EDGE_HANDLERS", [handler])
    assert E.dead_edge_handlers({}) == ["never_fires"]
    assert E.dead_edge_handlers({"never_fires": 3}) == []


# ===========================================================================
# T19 -- the dialect regexes (C12)
# ===========================================================================


@pytest.mark.parametrize("row_text,expected", [
    ("Item 1(A). Risk Factors 61", "1A"),
    ("ITEM 1(a). RISK FACTORS", "1A"),
    ("Item 1 (A). Risk Factors", "1A"),
    ("Item 1A. Risk Factors 61", "1A"),
    ("Item 7. Management's Discussion and Analysis 45", "7"),
    ("Item 10. Directors 88", "10"),
])
def test_t19_item_label_dialects_normalise(row_text, expected):
    match = E._ITEM_LABEL_PREFIX_RE.match(row_text)
    assert match, row_text
    assert E._normalize_item_label(match.group(1)) == expected


@pytest.mark.parametrize("row_text", ["Items 7 and 8", "Itemized list", "1A. Risk Factors 18"])
def test_t19_item_label_prefix_still_rejects_non_item_rows(row_text):
    assert E._ITEM_LABEL_PREFIX_RE.match(row_text) is None


def test_t19_toc_parsing_handles_the_parenthesised_dialect():
    html = """<table>
      <tr><td><a href="#a1">Item 1(A). Risk Factors</a></td><td>61</td></tr>
      <tr><td><a href="#a2">Item 2. Unregistered Sales</a></td><td>62</td></tr>
    </table>"""
    entries = E.find_toc_item_anchors(BeautifulSoup(html, E._PARSER))
    assert [e.item_no for e in entries] == ["1A", "2"]


def test_t19_e1_toc_dialects_are_unchanged():
    """The bare-number (COP/CVX) and split-row (JPM) dialects E1 depends on."""
    bare = """<table><tr><td><a href="#x">7. Management's Discussion and Analysis</a></td>
              <td>22</td></tr></table>"""
    assert [e.item_no for e in E.find_toc_item_anchors(BeautifulSoup(bare, E._PARSER))] == ["7"]
    split = """<table><tr><td>Item 7</td></tr>
               <tr><td><a href="#y">Management's Discussion and Analysis</a></td><td>62</td></tr>
               </table>"""
    assert [e.item_no for e in E.find_toc_item_anchors(BeautifulSoup(split, E._PARSER))] == ["7"]


def test_t19_appears_on_pages_matches_across_a_line_break():
    assert E.STUB_REFERENCE_LANGUAGE_RE.search("appears on\npages 36-138")
    assert E.STUB_REFERENCE_LANGUAGE_RE.search("appears on page 46")
    assert E.STUB_REFERENCE_LANGUAGE_RE.search("incorporated into this report by reference")
    assert E.STUB_REFERENCE_LANGUAGE_RE.search("is set forth in the Annual Report")


# ===========================================================================
# T14b / C14 -- the head checks
# ===========================================================================


def test_c14_head_foreign_item_fires_on_a_wrong_numbered_item():
    tesla_head = ("Table of Contents\nITEM 3. QUANTITATIVE AND QUALITATIVE DISCLOSURES "
                  "ABOUT MARKET RISK\nForeign Currency Risk\n")
    assert E.head_foreign_item(tesla_head, "10-Q", "MDA") is True


def test_c14_head_foreign_item_does_not_fire_on_the_ice_parenthesised_dialect():
    """The false positive the stricter variant produced (F3_SPEC C14)."""
    ice_head = ('ITEM 1(A). RISK FACTORS\nDuring the three months ended March 31, 2024, '
                'there were no significant new risk factors')
    assert E.head_foreign_item(ice_head, "10-Q", "RISK_FACTORS") is False


def test_c14_the_known_miss_is_documented_not_silently_caught():
    """`0001628280-26-032278`: a RISK_FACTORS slice opening "PART II. OTHER
    INFORMATION ITEM 1. LEGAL PROCEEDINGS". Its first item number equals the
    1A target's, so the check cannot catch it -- only `head_keyword_absent`
    and the manual QA read do. Stated, not closed with a cleverer regex."""
    head = ('PART II. OTHER INFORMATION\nITEM 1. LEGAL PROCEEDINGS\nWe are parties to '
            'various legal proceedings.')
    assert E.head_foreign_item(head, "10-Q", "RISK_FACTORS") is False
    assert E.head_keyword_absent(head, "RISK_FACTORS") is True


def test_c14_head_keyword_absent_is_whitespace_insensitive():
    """JNJ renders headings with letter-spacing markup."""
    assert E.head_keyword_absent("management's d iscussion and a nalysis of ...", "MDA") is False
    assert E.head_keyword_absent("CRITICAL ACCOUNTING POLICIES AND ESTIMATES", "MDA") is True


# ===========================================================================
# T20 -- prose share uses chunk.py's own constant (C16)
# ===========================================================================


def test_t20_prose_stats_reads_chunk_min_prose_words(monkeypatch):
    import chunk as chunk_module
    text = "\n".join(["short line", "word " * 45, "word " * 10])
    assert E.prose_stats(text)[0] == 1
    monkeypatch.setattr(chunk_module, "MIN_PROSE_WORDS", 5)
    assert E.prose_stats(text)[0] == 2, "prose_stats must read chunk.MIN_PROSE_WORDS live"
    monkeypatch.setattr(chunk_module, "MIN_PROSE_WORDS", 2)
    assert E.prose_stats(text)[0] == 3


def test_t20_prose_stats_matches_chunk_extract_prose_paragraphs():
    import chunk as chunk_module
    text = "\n".join(["a b c", "word " * 50, "d e", "word " * 41])
    row = {"text": text, "ticker": "X", "cik": 1, "accession_number": "a", "form": "10-K",
           "filing_date": "2020-01-01", "section_type": "MDA"}
    assert E.prose_stats(text)[0] == len(chunk_module.extract_prose_paragraphs(row))


def test_t20_zero_prose_sections_are_visible_to_f4(fixture_db, fixture_cache, tmp_path):
    """n_prose == 0 => n_chunks == 0 (97/97 on E1's frozen artifacts). F3 does
    NOT rewrite the text for this; it records the count so F4 cannot discover
    a missing slice of the corpus by accident."""
    assert E.prose_stats("")[0] == 0
    assert E.prose_stats("| a | b |\n| c | d |") == (0, 0.0)
    _run(fixture_db, fixture_cache, tmp_path, merge=True)
    sections = pd.read_parquet(tmp_path / "filings_e2.parquet")
    assert "n_prose_paragraphs" in sections.columns
    assert (sections["prose_word_share"] >= 0).all() and (sections["prose_word_share"] <= 1).all()


# ===========================================================================
# T21 -- the 12 named near-empty EX-99 selections FAIL by name (§2.2, §8.1(3))
# ===========================================================================

# F2 §5's P5 near-empty class, pinned by accession so a future floor or reader
# change that silently "rescues" them breaks a test.
NEAR_EMPTY_EX99 = [
    ("0000037996-19-000005", 37996, "FORD MOTOR CO"),
    ("0001099219-23-000041", 1099219, "METLIFE INC"),
    ("0000713676-17-000017", 713676, "PNC"),
    ("0000713676-19-000020", 713676, "PNC"),
    ("0001193125-16-556144", 713676, "PNC"),
    ("0001193125-16-709397", 713676, "PNC"),
    ("0001193125-16-758662", 713676, "PNC"),
    ("0001193125-17-073082", 713676, "PNC"),
    ("0001193125-17-283876", 713676, "PNC"),
    ("0000950159-22-000107", 1739940, "Cigna"),
    ("0001654954-19-012971", 1707925, "LINDE PLC"),
    ("0001654954-24-013519", 1707925, "LINDE PLC"),
]


@needs_cache
@needs_db
@pytest.mark.parametrize("accession,cik,filer", NEAR_EMPTY_EX99)
def test_t21_named_near_empty_ex99_selections_fail_loudly(accession, cik, filer):
    conn = E.open_readonly(REAL_DB)
    row = conn.execute(
        "SELECT earnings_doc_relative_path, earnings_doc_section_type, earnings_doc_filename, cik "
        "FROM filings WHERE accession_number = ?", (accession,)).fetchone()
    conn.close()
    assert row, f"{accession} not in the E2 DB"
    rel = row[0] or f"/Archives/edgar/data/{row[3]}/{accession.replace('-', '')}/{row[2]}"
    result = E.extract_earnings_document(E.read_cached_document, rel, row[1],
                                          {"quarter_cell_size": 1})
    assert result.reason_code == "empty_after_extraction", filer
    assert result.status == "FAIL"
    assert result.located is False


@needs_db
def test_t21_the_named_short_release_survivors_clear_the_raised_floor():
    """H4 §8.1 forbids failing these two "without arguing past them by name".
    The EX-99 floor was RAISED 50 -> 250 at P1; both stay above it."""
    assert E.MIN_SECTION_WORDS[("8-K", "EX99_PRESS_RELEASE")] == 250
    census = pd.read_parquet(REPO_ROOT / "data" / "f3" / "p0_measure" / "gate_corpus.parquet")
    for accession, words, who in [("0001564590-22-013264", 276, "Tesla Q1-22 P&D"),
                                   ("0001140361-19-006520", 384, "KKR monetization update")]:
        row = census[census["acc"] == accession]
        assert not row.empty, accession
        assert int(row["words"].iloc[0]) == words, who
        assert words >= E.MIN_SECTION_WORDS[("8-K", "EX99_PRESS_RELEASE")], who


@needs_db
def test_t21_the_ex99_floor_raise_before_and_after_counts_are_the_measured_ones():
    """§8.1(2)(d): the recalibration's before/after numbers, pinned."""
    census = pd.read_parquet(REPO_ROOT / "data" / "f3" / "p0_measure" / "gate_corpus.parquet")
    ex99 = census[census["section_type"] == "EX99_PRESS_RELEASE"]
    assert len(ex99) == 10357
    assert int((ex99["words"] < 50).sum()) == 12      # E1's floor
    assert int((ex99["words"] < 250).sum()) == 53     # the raised floor
    # every row under the old floor is one of the 12 that FAIL outright
    assert int((ex99["chars"] < E.MIN_SECTION_CHARS).sum()) == 12


# ===========================================================================
# T22 -- P5 fix 1: the guarded TOC recovery ladder
# ===========================================================================

# The two populations the ladder targets, by name, with the disposition each
# row must get. Every accession below was hand-read at P4b or P5 and the
# verdict is recorded in `data/f3/status/P5_fixes.md`.
LADDER_ROWS = [
    # (accession, cik, form, section, expected reason_code, min words)
    # --- P4b's EXPECTED_ABSENT census, R2 arm, recovered by F1' ---------------
    ("0001108524-16-000066", 1108524, "10-Q", "RISK_FACTORS", "toc_recovered_f1", 11000),
    ("0000008670-18-000007", 8670, "10-Q", "RISK_FACTORS", "toc_recovered_f1", 30),
    ("0000731766-16-000081", 731766, "10-Q", "RISK_FACTORS", "toc_recovered_f1", 100),
    # --- Eversource: F1' resolves to the WRONG section (Part II Item 1),
    #     G1 rejects it, F2' gets it right. The one case the ladder's second
    #     rung exists for.
    ("0000072741-19-000026", 72741, "10-Q", "RISK_FACTORS", "toc_recovered_f2", 100),
    ("0000072741-17-000021", 72741, "10-Q", "RISK_FACTORS", "toc_recovered_f2", 100),
    # --- AIG: no recoverable span by any mechanism. Must stay a loud FAIL. ----
    ("0000005272-16-000041", 5272, "10-Q", "RISK_FACTORS", "toc_recovery_declined", 0),
    ("0000005272-16-000046", 5272, "10-Q", "RISK_FACTORS", "toc_recovery_declined", 0),
    ("0000005272-19-000031", 5272, "10-Q", "RISK_FACTORS", "toc_recovery_declined", 0),
    # --- P3's 148-row FAIL census, R2 arm ------------------------------------
    ("0000313616-16-000145", 313616, "10-K", "RISK_FACTORS", "toc_recovered_f1", 5000),
    ("0000731766-17-000028", 731766, "10-Q", "MDA", "toc_recovered_f1", 4000),
    ("0000049071-16-000117", 49071, "10-K", "RISK_FACTORS", "toc_recovered_f1", 10000),
    # --- R3 arm, recovered by F2' (Welltower / IBM: real sections) -----------
    ("0000766704-16-000082", 766704, "10-Q", "MDA", "toc_recovered_f2", 10000),
    ("0000051143-15-000009", 51143, "10-Q", "MDA", "toc_recovered_f2", 20000),
    # --- rows the guards must DECLINE, each for a named reason ---------------
    #     Coca-Cola: F1' opens on the real Item 7 heading but the end guard
    #     truncates it to 73 words at an `Item 8` cross-reference in its own
    #     first paragraph -> G3. Must NOT fall through to F2', which returns
    #     4,916 words starting inside Item 1 Business.
    ("0000021344-18-000008", 21344, "10-K", "MDA", "toc_recovery_declined", 0),
    #     Weyerhaeuser / PNC: F2' lands on the MD&A's own sub-table-of-contents.
    ("0001564590-20-004822", 106535, "10-K", "MDA", "toc_recovery_declined", 0),
    ("0001193125-15-277885", 713676, "10-Q", "MDA", "toc_recovery_declined", 0),
    #     Honeywell / Concho: the heading-regex match is mid-line, i.e. a
    #     cross-reference inside a sentence, not a heading.
    ("0000930413-19-000366", 773840, "10-K", "MDA", "toc_recovery_declined", 0),
    ("0001358071-19-000003", 1358071, "10-K", "RISK_FACTORS", "toc_recovery_declined", 0),
]


def _locate(cik, accession, form, section):
    conn = E.open_readonly(REAL_DB)
    doc = conn.execute("SELECT primary_document FROM filings WHERE accession_number=?",
                       (accession,)).fetchone()[0]
    conn.close()
    return E.extract_periodic_sections(
        E.read_cached_document, cik, accession, doc, form)[section]


@needs_cache
@needs_db
@pytest.mark.parametrize("accession,cik,form,section,code,min_words", LADDER_ROWS)
def test_t22_the_ladder_disposes_of_each_named_row_as_measured(
        accession, cik, form, section, code, min_words):
    result = _locate(cik, accession, form, section)
    assert result.reason_code == code, result.note
    assert len(result.text.split()) >= min_words
    if code.startswith("toc_recovered"):
        # R3 of the F3 spec, tightened for recoveries: never OK, never `high`.
        assert result.status == E.STATUS_FLAGGED
        assert result.confidence in ("medium", "low")
    else:
        assert result.status == E.STATUS_FAIL
        assert result.text == ""
        assert result.note, "a declined recovery must say which guard declined it"


@needs_cache
@needs_db
def test_t22_the_ladder_never_fires_where_the_item_is_absent_from_the_toc():
    """SCOPE, and it is the load-bearing invariant of the whole fix: the ladder
    runs only when a matching TOC entry EXISTS. P4b ran the same guards over
    the 696 rows with no matching entry and they admitted 131 rows of which 89
    were garbage (Williams `0000107263-17-000006` returns 21,241 words starting
    mid-sentence). These four are R1 rows -- three with a body heading that
    passes every guard, one without -- and not one of them may be recovered."""
    for accession, cik, form, section in [
        ("0001034054-16-000022", 1034054, "10-Q", "RISK_FACTORS"),   # 12,855 w, genuine, unindexed
        ("0001104659-18-030187", 701221, "10-Q", "RISK_FACTORS"),    # Cigna Holding, genuine
        ("0000107263-17-000006", 107263, "10-Q", "RISK_FACTORS"),    # Williams, 21,241 w of garbage
        ("0000037996-15-000064", 37996, "10-Q", "RISK_FACTORS"),     # Ford, cross-reference
    ]:
        result = _locate(cik, accession, form, section)
        assert result.reason_code == "item_absent_from_toc", accession
        assert result.text == "", accession
        assert result.status == E.STATUS_ITEM_ABSENT_FROM_TOC, accession


@needs_cache
@needs_db
def test_t22_a_genuine_unindexed_section_is_marked_for_review_but_not_recovered():
    """P5 fix 2: the 42 rows P4b found where the filer DID disclose Item 1A and
    the anchor TOC simply never indexed it. They are flagged distinctly and
    left failing; the marker's measured precision is 42 of 52."""
    marked = _locate(1034054, "0001034054-16-000022", "10-Q", "RISK_FACTORS")
    assert "item_body_heading_present" in marked.flags
    assert marked.reason_code == "item_absent_from_toc"  # the marker never wins precedence
    unmarked = _locate(107263, "0000107263-17-000006", "10-Q", "RISK_FACTORS")
    assert "item_body_heading_present" not in unmarked.flags


def test_t22_guard_units():
    """G1 / G1-line-start / G2, on synthetic bytes."""
    # G1: opens on the item's own heading, within 40 chars.
    assert E.span_opens_on_item_heading("ITEM 1A. RISK FACTORS\nWe depend on ...",
                                         "10-Q", "RISK_FACTORS")
    assert E.span_opens_on_item_heading("PART II. OTHER INFORMATION ITEM 1A. RISK FACTORS\nWe ...",
                                         "10-Q", "RISK_FACTORS")
    # the Eversource shape: a resolving anchor that points at Part II Item 1
    assert not E.span_opens_on_item_heading(
        "PART II. OTHER INFORMATION ITEM 1. LEGAL PROCEEDINGS We are parties to various "
        "legal proceedings. ITEM 1A. RISK FACTORS ...", "10-Q", "RISK_FACTORS")
    # the dash and parenthesised dialects are accepted by the GUARD even though
    # the tight locator pattern rejects them.
    assert E.span_opens_on_item_heading("ITEM 1A - RISK FACTORS\nWe ...", "10-Q", "RISK_FACTORS")
    assert E.span_opens_on_item_heading("ITEM 1(A). RISK FACTORS\nWe ...", "10-Q", "RISK_FACTORS")

    # G2: an EOF-terminating span has no following item, so its start is wrong.
    body = "Item 1A. Risk Factors\nThere have been no material changes.\n"
    assert E.end_guard_span(body + "Item 2. Unregistered Sales of Equity\nNone.",
                            "10-Q", "RISK_FACTORS")[1] is True
    assert E.end_guard_span(body, "10-Q", "RISK_FACTORS")[1] is False

    # G1, line-start form: a heading begins a line; a cross-reference does not.
    text = 'See "Item 1A. Risk Factors" for a description.\nItem 1A. Risk Factors\nWe ...'
    mid = text.index('Item 1A. Risk Factors"')
    start = text.rindex("Item 1A. Risk Factors")
    assert not E._fallback_span_starts_a_line((mid, len(text)), text)
    assert E._fallback_span_starts_a_line((start, len(text)), text)


def test_t22_every_recovery_code_is_in_the_closed_enum_and_can_never_be_high():
    for code in ("toc_recovered_f1", "toc_recovered_f2", "toc_recovery_end_guarded"):
        assert E.REASON_STATUS[code] == E.STATUS_FLAGGED
        assert code in E.REASON_PRECEDENCE
    assert E.REASON_STATUS["toc_recovery_declined"] == E.STATUS_FAIL
    assert E.REASON_STATUS["item_body_heading_present"] == E.STATUS_FLAGGED
    # a declined recovery is a FAIL for EVERY target, including the one where
    # `item_absent_from_toc` is not a FAIL.
    assert E.status_for("toc_recovery_declined", "10-Q", "RISK_FACTORS") == E.STATUS_FAIL


# ===========================================================================
# T23 -- P5 fix 2: the status rename, and its mapping back to the old view
# ===========================================================================


def test_t23_the_status_asserts_what_was_measured_not_filer_intent():
    assert E.STATUS_ITEM_ABSENT_FROM_TOC == "ITEM_ABSENT_FROM_TOC"
    assert not hasattr(E, "STATUS_EXPECTED_ABSENT")
    assert (E.status_for("item_absent_from_toc", "10-Q", "RISK_FACTORS")
            == E.STATUS_ITEM_ABSENT_FROM_TOC)
    assert E.status_for("item_absent_from_toc", "10-K", "RISK_FACTORS") == E.STATUS_FAIL


@needs_cache
@needs_db
@pytest.mark.skipif(not (REPO_ROOT / "data" / "f3" / "v2" / "extraction_audit.parquet").exists(),
                    reason="P5 corpus not built yet")
def test_t23_the_old_expected_absent_view_is_reconstructible():
    """The audit consumer must be able to rebuild the pre-P5 view exactly:
    old EXPECTED_ABSENT = ITEM_ABSENT_FROM_TOC + the (10-Q, RISK_FACTORS) rows
    the ladder now recovers or declines."""
    old = pd.read_parquet(REPO_ROOT / "data" / "f3" / "extraction_audit.parquet")
    new = pd.read_parquet(REPO_ROOT / "data" / "f3" / "v2" / "extraction_audit.parquet")
    old_keys = set(zip(old[old.extraction_status == "EXPECTED_ABSENT"].accession_number,
                       old[old.extraction_status == "EXPECTED_ABSENT"].section_type))
    rebuilt = new[
        (new.extraction_status == "ITEM_ABSENT_FROM_TOC")
        | ((new.form == "10-Q") & (new.section_type == "RISK_FACTORS")
           & new.reason_code.isin(["toc_recovered_f1", "toc_recovered_f2",
                                    "toc_recovery_declined"]))]
    assert set(zip(rebuilt.accession_number, rebuilt.section_type)) == old_keys


# ===========================================================================
# T24 -- P5 fix 3 (N1): the garbled-text screen must be a UNION
# ===========================================================================

# Every garbled row named across P1 §4c, P3 §6.2 and P4 §4.1, with the score
# that finds it. The point of the table is that NO SINGLE screen finds them all.
KNOWN_GARBLED = [
    ("0000037996-18-000082", "Ford, Caesar-shifted font map, 3,333 w, shipped OK/high"),
    ("0000037996-19-000065", "Ford, same class, 2,609 w, shipped OK/high"),
    ("0000831259-24-000026", "Freeport, the row P1's nonascii_ratio proposal missed"),
    ("0001297996-18-000125", "Digital Realty, ctrl_ratio is EXACTLY 0.0 -- P4's counter-example"),
    ("0001297996-16-000203", "Digital Realty, Wingdings bullets; eng_word_share is 0.33"),
]


@needs_cache
@pytest.mark.skipif(not (REPO_ROOT / "data" / "filings_e2.parquet").exists(),
                    reason="P2 corpus absent")
@pytest.mark.parametrize("accession,why", KNOWN_GARBLED)
def test_t24_the_union_screen_catches_every_known_garbled_row(accession, why):
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(REPO_ROOT / "data" / "filings_e2.parquet")
    for batch in pf.iter_batches(batch_size=400, columns=["accession_number", "text"]):
        d = batch.to_pydict()
        for i, acc in enumerate(d["accession_number"]):
            if acc == accession:
                ctrl, eng = E.garble_stats(d["text"][i])
                assert E.text_is_garbled(ctrl, eng), f"{why}: ctrl={ctrl} eng={eng}"
                return
    pytest.fail(f"{accession} not found in the corpus")


def test_t24_neither_single_screen_would_have_been_enough():
    """The two counter-examples that force the union, as literal thresholds."""
    # Digital Realty 2018: ctrl_ratio is 0.0, eng_word_share 0.036.
    assert not (0.0 >= E.GARBLE_CTRL_RATIO)
    assert E.text_is_garbled(0.0, 0.036)
    # Digital Realty 2016: eng_word_share 0.333, ctrl_ratio 0.0157.
    assert not (0.333 < E.GARBLE_ENG_WORD_SHARE)
    assert E.text_is_garbled(0.0157, 0.333)
    # and the shipped ctrl threshold is the LOWERED one, argued in P5_fixes.md
    assert E.GARBLE_CTRL_RATIO == 0.01
    # clean prose is never flagged
    clean = ("The company reported net revenue for the three months ended June 30 "
             "and operating income increased due to higher demand in all markets. ") * 20
    assert not E.text_is_garbled(*E.garble_stats(clean))
    # a short section is not scored on word share at all (too noisy), and says so
    assert E.garble_stats("net income of $3 per share")[1] is None


# ===========================================================================
# T25 -- P5 fix 4 (N5): the heading-regex last-match defect
# ===========================================================================

# P3 §7.2's named class: 34 AT&T 10-Q MD&As truncated to the LAST running page
# header (43-819 words, median 333, against a 9,325-word anchor median). Five
# of them, with the pre-fix count and the post-fix floor they must clear.
ATT_TRUNCATED = [
    ("0000732717-24-000022", 398), ("0000732717-15-000079", 716),
    ("0000732717-17-000055", 341), ("0000732717-16-000233", 469),
    ("0001193125-18-236782", 221),
]


@needs_cache
@needs_db
@pytest.mark.parametrize("accession,shipped_words", ATT_TRUNCATED)
def test_t25_the_named_att_rows_come_back_full_length(accession, shipped_words):
    result = _locate(732717 if accession.startswith("0000732717") else 732717,
                     accession, "10-Q", "MDA")
    words = len(result.text.split())
    assert words > shipped_words * 5
    assert words >= E.MIN_SECTION_WORDS[("10-Q", "MDA")]
    assert result.text.split("\n")[0].lower().startswith("item 2.")
    assert "- Continued" not in result.text[:200]


def test_t25_the_floor_rescue_fires_only_below_the_floor():
    """The rescue must be inert on any document whose last-match slice is
    already a plausible section -- that is the whole reason it is gated on the
    floor rather than on position (see the 38-row hand read in
    `data/f3/p5_fixes/n5_read_verdicts.csv`)."""
    body = "word " * 3000
    # two matches: a 60-char TOC row, then the real section
    text = ("Item 2. Management's Discussion and Analysis 20\n"
            "Item 3. Quantitative and Qualitative disclosures 21\n"
            "Item 2. Management's Discussion and Analysis\n" + body +
            "\nItem 3. Quantitative and Qualitative Disclosures About Market Risk\n")
    span = E.locate_item_section_by_heading_regex(text, "10-Q", "MDA")
    assert len(text[span[0]:span[1]].split()) >= E.MIN_SECTION_WORDS[("10-Q", "MDA")]
    # when the LAST match already clears the floor, nothing moves
    text2 = ("Item 2. Management's Discussion and Analysis\n" + body +
             "\nItem 2. Management's Discussion and Analysis\n" + body +
             "\nItem 3. Quantitative and Qualitative Disclosures About Market Risk\n")
    span2 = E.locate_item_section_by_heading_regex(text2, "10-Q", "MDA")
    assert span2[0] == text2.rindex("Item 2. Management's Discussion and Analysis")


# ===========================================================================
# T26 -- P5 fix 5 (N6): the NIKE per-filer edge handler
# ===========================================================================

NIKE_CIK = 320187


def test_t26_the_nike_predicate_is_tight_enough_to_fire_on_exactly_that_class():
    handler = next(h for h in E.EDGE_HANDLERS if h.name == "nike_10q_mda_shared_toc_anchor")
    assert handler.applies_to(NIKE_CIK, "10-Q", "MDA")
    for cik, form, section in [(NIKE_CIK, "10-K", "MDA"), (NIKE_CIK, "10-Q", "RISK_FACTORS"),
                               (1318605, "10-Q", "MDA"),   # Tesla, 8 head_foreign_item rows
                               (70858, "10-K", "MDA")]:    # Bank of America, 2 rows
        assert not handler.applies_to(cik, form, section), (cik, form, section)
    # and even inside its own predicate it is inert unless the defect fired
    clean = E.ExtractionResult(text="x", method="anchor", confidence="high",
                               form="10-Q", section_type="MDA", flags=[])
    assert handler.handler(clean, NIKE_CIK, "10-Q", "MDA", None) is None


@needs_cache
@needs_db
@pytest.mark.parametrize("accession,min_words", [
    ("0000320187-19-000071", 7000),   # the 2019 shape: MD&A and Part II Item 1A share one id
    ("0000320187-25-000151", 10000),  # the 2025 shape: ALL 25 TOC rows share one id
    ("0000320187-22-000017", 12000),
])
def test_t26_the_nike_handler_returns_the_real_mdna(accession, min_words):
    result = _locate(NIKE_CIK, accession, "10-Q", "MDA")
    assert "head_foreign_item" not in result.flags
    assert len(result.text.split()) >= min_words
    assert result.text.lstrip().lower().startswith("item 2. management")
    assert result.confidence == "low"


@needs_cache
@needs_db
def test_t26_the_handler_leaves_nikes_correct_extractions_alone():
    """12 of NIKE's 33 10-Q MD&As never raised `head_foreign_item` and must be
    byte-identical to the pre-P5 corpus."""
    corpus = pd.read_parquet(REPO_ROOT / "data" / "filings_e2.parquet",
                             columns=["cik", "accession_number", "form",
                                      "section_type", "text", "flags"])
    ok = corpus[(corpus.cik == NIKE_CIK) & (corpus.section_type == "MDA")
                & (corpus.form == "10-Q")]
    ok = ok[[("head_foreign_item" not in list(f)) for f in ok["flags"]]]
    assert len(ok) >= 10
    row = ok.iloc[0]
    result = _locate(NIKE_CIK, row["accession_number"], "10-Q", "MDA")
    assert result.text == row["text"]


@needs_cache
@needs_db
@pytest.mark.parametrize("accession,cik,form,section,words,why", [
    # A rescue candidate must begin a line. Without that requirement these
    # three come back with 16k-23k words of Item 1 Business labelled as MD&A --
    # measurably WORSE than the pre-P5 slice, which is the one regression the
    # P5 rebuild found in itself.
    ("0001035002-22-000007", 1035002, "10-K", "MDA", 171,
     "Valero: reverts to its pre-P5 stub rather than 16,391 w of Business"),
    ("0001358071-16-000026", 1358071, "10-K", "MDA", 1184, "Concho, same shape"),
    ("0001358071-17-000005", 1358071, "10-K", "MDA", 1238, "Concho, same shape"),
    # and the same requirement makes one row BETTER: the correct Item 1A sits
    # 20k characters after the cross-reference that would otherwise win.
    ("0001104659-22-025141", 1800, "10-K", "RISK_FACTORS", 4320,
     "Abbott: the real ITEM 1A, not 7,258 w of Patents, Trademarks and Licenses"),
])
def test_t25_the_rescue_candidate_must_begin_a_line(accession, cik, form, section, words, why):
    result = _locate(cik, accession, form, section)
    assert len(result.text.split()) == words, why
