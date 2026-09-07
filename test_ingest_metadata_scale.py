"""test_ingest_metadata_scale.py -- F2 stage S3 tests: enumeration at scale
over per-company coverage windows, the --stage {metadata,documents,all} split,
the EX-99 selection audit + earnings_doc_unresolved accounting, distress-event
ingestion, and edgar_client's max_age_hours passthrough.

Covers the whole F2_SPEC §8.2 "S3" block. S2's own block lives in
test_ingest_metadata_universe.py; nothing here duplicates it.

Everything here is OFFLINE -- no test opens a socket:
  - EDGAR interactions go through fakes built from synthetic dicts, or through
    a real EdgarClient whose _get() is monkeypatched to raise / return canned
    bytes;
  - the real-world fixtures under data/f2/fixtures/filing_index_CIK*.html are
    byte-identical copies of data/raw/filing_index/ entries, produced by
    data/f2/fixtures/build_fixtures.py and never re-fetched. The baseline one
    (CIK 18230, 0000018230-16-000702, sha256
    582488d3aad791b104b908b81493dcc6d7844cbfb527681bf7218e3f4a63e654) was
    captured by the S1 probe on 2026-08-24: CAT's 2016-10-25 earnings 8-K
    index, a pre-iXBRL vintage, an extension-stratum filer, and a sector E1
    never touched. The other six are the filer dialects the S6 segment-1
    diagnosis found (2026-08-24) -- see the FILER DIALECTS block near the
    bottom of this file, and data/f2/status/S6_seg1_ex99_diagnosis.md.

Run with: python3 -m pytest test_ingest_metadata_scale.py -v
"""
from __future__ import annotations

import os
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

import edgar_client as ec
import ingest_metadata as im


REPO_ROOT = Path(__file__).resolve().parent
FIXTURES = REPO_ROOT / "data" / "f2" / "fixtures"
CAT_INDEX_FIXTURE = FIXTURES / "filing_index_CIK0000018230_0000018230-16-000702.html"
CAT_CIK = 18230
CAT_ACCESSION = "0000018230-16-000702"
CAT_PRIMARY_DOCUMENT = "cat_8-kxq3x2016xearningsxr.htm"

# The six filer-dialect fixtures from the S6 segment-1 diagnosis (2026-08-24).
# (fixture stem, cik, accession, primary_document) -- primary_document is the
# real one from submissions.json, so the parser's own primary-document
# assertion runs exactly as it does in production.
DIALECT_SINGLE_DOC_8K = (45012, "0000045012-17-000039", "hal_12312016-er8k.htm")
DIALECT_ZERO_PADDED = (92122, "0000092122-24-000011", "so-20240215.htm")
DIALECT_PDF_PAIR_991 = (18230, "0001104659-16-091860", "a16-2992_18k.htm")
DIALECT_PDF_PAIR_BARE = (37996, "0000037996-15-000044",
                         "earnings8-kdatedjuly282015.htm")
DIALECT_BARE_BY_DESCRIPTION = (72741, "0000072741-18-000056",
                               "form8kq32018earningsreleasee.htm")
DIALECT_UNRECOGNISED = (200406, "0000200406-19-000004", "a20184qcover.htm")


def _dialect_index(cik: int, accession: str) -> Path:
    return FIXTURES / f"filing_index_CIK{cik:010d}_{accession}.html"


def _select_from_fixture(case: tuple[int, str, str]) -> dict:
    """Parse a dialect fixture and run the real selection policy over it."""
    cik, accession, primary = case
    docs = im.parse_index_html_documents(
        _dialect_index(cik, accession).read_text(), primary_document=primary
    )
    return im.select_earnings_document(
        docs, primary, subject=f"CIK {cik}", accession_number=accession
    )


# ---------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------


def _recent(rows: list[dict], filer: int = 0) -> dict:
    """`filings.recent`-shaped parallel arrays from a list of row dicts with
    keys form / date / (optional) items, accession, primary.

    Generated accession numbers are scoped by `filer` because
    `filings.accession_number` is the table's PRIMARY KEY -- real EDGAR
    accessions are globally unique, and two synthetic companies sharing one
    would silently collapse into one company's rows.
    """
    n = len(rows)
    return {
        "form": [r["form"] for r in rows],
        "filingDate": [r["date"].isoformat() for r in rows],
        "accessionNumber": [
            r.get("accession", f"{filer:010d}-00-{i:06d}") for i, r in enumerate(rows)
        ],
        "reportDate": [""] * n,
        "acceptanceDateTime": [""] * n,
        "primaryDocument": [r.get("primary", f"doc{i}.htm") for i, r in enumerate(rows)],
        "items": [r.get("items", "") for r in rows],
    }


def _submissions(
    rows: list[dict], tickers: list[str] | None = None, filer: int = 0,
) -> dict:
    return {
        "tickers": tickers or [],
        "filings": {"recent": _recent(rows, filer=filer), "files": []},
    }


def _periodic(start: date, end: date, n: int) -> list[dict]:
    """n evenly spaced 10-K/10-Q filings across [start, end] -- enough to keep
    validate_universe() clean (rate >= 3.9/yr, no gap > 135 d)."""
    span = (end - start).days
    out = []
    for i in range(n):
        offset = round(i * span / (n - 1)) if n > 1 else 0
        out.append(
            {"form": "10-K" if i % 4 == 0 else "10-Q", "date": start + timedelta(days=offset)}
        )
    return out


def _healthy(start: date, end: date) -> list[dict]:
    """A filing history that spans [start, end] at ~4.1 periodic filings/yr."""
    years = max((end - start).days / 365.25, 0.25)
    return _periodic(start, end, max(int(round(years * 4.1)), 2))


def _universe_row(
    cik: int, coverage_start: date, coverage_end: date, is_current: bool = True,
    name: str = "TEST CO", sector: str = "tech", stratum: str = "core",
) -> dict:
    return {
        "cik": cik, "name": name, "sector": sector, "stratum": stratum,
        "coverage_start": coverage_start, "coverage_end": coverage_end,
        "is_current_member": is_current,
    }


def _spell_row(cik: int, member_from: str, member_to: str = "", sector: str = "tech") -> dict:
    return {
        "cik": cik, "sector": sector, "stratum": "core",
        "member_from": member_from, "member_to": member_to,
    }


class FakeClient:
    """Stands in for EdgarClient. Never touches the network. Records every
    call so a test can assert cache-first / exactly-once behaviour."""

    def __init__(
        self, submissions_by_cik: dict[int, dict],
        index_html: dict[str, str] | None = None,
        cache_dir: Path | None = None,
        ticker_map: dict[str, int] | None = None,
    ):
        self.submissions_by_cik = submissions_by_cik
        self.index_html = index_html or {}
        self.cache_dir = Path(cache_dir) if cache_dir else Path("/nonexistent-cache")
        self.ticker_map = ticker_map or {}
        self.request_count = 0
        self.effective_recent_calls: list[int] = []
        self.index_calls: list[tuple[int, str]] = []
        self.document_calls: list[str] = []
        self.fail_documents: set[str] = set()
        self.fail_index: set[str] = set()

    def get_company_tickers(self, force: bool = False) -> dict:
        return {
            str(i): {"cik_str": cik, "ticker": t}
            for i, (t, cik) in enumerate(self.ticker_map.items())
        }

    def get_submissions(self, cik: int, force: bool = False, max_age_hours=None) -> dict:
        return self.submissions_by_cik[cik]

    def get_effective_recent(
        self, cik: int, cutoff: date, force: bool = False, max_age_hours=None,
    ) -> dict:
        self.effective_recent_calls.append(cik)
        return self.submissions_by_cik[cik]["filings"]["recent"]

    def get_filing_index_html(self, cik: int, accession_number: str, force: bool = False) -> str:
        self.index_calls.append((cik, accession_number))
        if accession_number in self.fail_index:
            raise RuntimeError("synthetic index fetch failure")
        return self.index_html[accession_number]

    def get_archive_document(self, relative_path: str, force: bool = False) -> str:
        self.document_calls.append(relative_path)
        if relative_path in self.fail_documents:
            raise RuntimeError("synthetic document fetch failure")
        path = im.document_cache_path(self, relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("<html>doc</html>")
        return "<html>doc</html>"


def _drive(
    monkeypatch, tmp_path: Path, universe_rows: list[dict], spell_rows: list[dict],
    client: FakeClient, stage: str = "metadata", db: Path | None = None,
    overrides_path: Path | None = None,
):
    """Run im.run() end-to-end against a synthetic universe. Nothing opens a
    socket and nothing writes to a real repo artifact."""
    monkeypatch.setattr(im, "load_universe", lambda *a, **k: pd.DataFrame(universe_rows))
    monkeypatch.setattr(im, "load_membership", lambda *a, **k: pd.DataFrame(spell_rows))
    monkeypatch.setattr(im, "EdgarClient", lambda *a, **k: client)
    db = db or (tmp_path / "e2.db")
    im.run(
        db_path=db,
        exceptions_path=tmp_path / "no_such_exceptions.csv",
        ex99_audit_path=tmp_path / "ex99_selection_audit.csv",
        overrides_path=overrides_path or (tmp_path / "no_such_overrides.csv"),
        stage=stage,
    )
    return db


def _rows(db: Path, sql: str) -> list[tuple]:
    conn = sqlite3.connect(db)
    out = conn.execute(sql).fetchall()
    conn.close()
    return out


# =====================================================================
# §4.1 -- enumeration at scale, over PER-COMPANY coverage windows
# =====================================================================


def test_enumeration_uses_the_shared_corpus_window_not_the_member_window(
    monkeypatch, tmp_path
):
    """F2_SPEC ruling §9.1(1-2)/§4.2: "ingest the full E2 window for every CIK
    that is ever a member; do not clip fetches to membership spells", and §2
    names CORPUS_WINDOW_START the "documents/metadata enumeration floor".

    So a former member and a late entrant with very different coverage windows
    both get the SAME ingested span. The per-company window still governs
    VALIDATION (§3.1) -- see test_ingest_metadata_universe.py -- and is still
    written to `companies`.

    Re-measured on the real 244 members (2026-08-24): the shared window
    reproduces §4.1's MEASURED table exactly (2,452 / 7,532 / 35,638 = 45,622,
    10,569 earnings 8-Ks); per-company clipping yields 35,649 / 8,242 and loses
    §4.5's bankruptcy event entirely.
    """
    early_cik, late_cik = 111, 222
    history = _healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1))
    universe = [
        # A former member whose coverage window ends in 2020...
        _universe_row(early_cik, im.CORPUS_WINDOW_START, date(2020, 1, 1), is_current=False),
        # ...and a late entrant whose coverage window starts in 2022.
        _universe_row(late_cik, date(2022, 1, 1), im.CORPUS_WINDOW_END, is_current=True),
    ]
    spells = [
        _spell_row(early_cik, "2016-07-01", "2019-07-01"),
        _spell_row(late_cik, "2024-07-01"),
    ]
    client = FakeClient({
        early_cik: _submissions(history, filer=early_cik),
        late_cik: _submissions(history, filer=late_cik),
    })
    db = _drive(monkeypatch, tmp_path, universe, spells, client)

    got = _rows(
        db, "SELECT cik, COUNT(*), MIN(filing_date), MAX(filing_date) "
            "FROM filings GROUP BY cik"
    )
    spans = {cik: (n, lo, hi) for cik, n, lo, hi in got}
    assert spans[early_cik] == spans[late_cik], (
        "the same filing history must ingest identically regardless of the "
        "member's own coverage window"
    )
    n, lo, hi = spans[early_cik]
    assert n == len(history)
    assert lo >= im.CORPUS_WINDOW_START.isoformat()
    assert hi <= im.CORPUS_WINDOW_END.isoformat()
    # The per-company window is still recorded, just not used to clip.
    assert _rows(db, f"SELECT coverage_end FROM companies WHERE cik={early_cik}") \
        == [("2020-01-01",)]


def test_enumeration_still_honours_the_fixed_corpus_bounds(monkeypatch, tmp_path):
    """Wider than membership, but NOT unbounded: the fixed literals are what
    make a re-run in October reproduce the same corpus."""
    cik = 121212
    history = [
        {"form": "10-K", "date": date(2014, 1, 2)},          # before the floor
        *_healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)),
        {"form": "10-K", "date": date(2026, 9, 30)},         # after the freeze
    ]
    client = FakeClient({cik: _submissions(history)})
    db = _drive(
        monkeypatch, tmp_path,
        [_universe_row(cik, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END)],
        [_spell_row(cik, "2016-07-01")], client,
    )
    lo, hi = _rows(db, "SELECT MIN(filing_date), MAX(filing_date) FROM filings")[0]
    assert lo >= im.CORPUS_WINDOW_START.isoformat()
    assert hi <= im.CORPUS_WINDOW_END.isoformat()
    assert "2014-01-02" != lo and "2026-09-30" != hi


def test_pagination_cutoff_is_the_corpus_floor_so_the_floor_is_reachable(
    monkeypatch, tmp_path
):
    """If get_effective_recent() were asked only for a late entrant's own
    coverage_start, the filings.files[] chunks older than it would never be
    pulled and the corpus floor would be unreachable by construction."""
    cik = 131313
    seen: list[date] = []
    client = FakeClient({cik: _submissions(_healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)))})
    original = client.get_effective_recent

    def spy(c, cutoff, force=False, max_age_hours=None):
        seen.append(cutoff)
        return original(c, cutoff, force=force, max_age_hours=max_age_hours)

    client.get_effective_recent = spy
    _drive(
        monkeypatch, tmp_path,
        # A late entrant: coverage_start 2024-07-01, far above the floor.
        [_universe_row(cik, date(2024, 7, 1), im.CORPUS_WINDOW_END)],
        [_spell_row(cik, "2026-07-01")], client,
    )
    assert im.CORPUS_WINDOW_START in seen


def test_co_registrant_filings_are_counted_and_named_not_silently_dropped(
    monkeypatch, tmp_path
):
    """EDGAR lists co-registrants on ONE accession -- a parent and its
    subsidiary file a single 8-K together. `filings.accession_number` is the
    PRIMARY KEY, so when both are members the second CIK's attribution is
    lost. MEASURED on the real universe: 87 of 45,622 filings across three
    pairs (Dow, Williams, Exelon). It must be counted, never silent."""
    parent, sub = 29915, 1751788
    shared = {"form": "8-K", "date": date(2021, 5, 3), "accession": "0001751788-21-000001",
              "items": ""}
    parent_rows = _healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)) + [shared]
    sub_rows = _healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)) + [shared]
    client = FakeClient({
        parent: _submissions(parent_rows, filer=parent),
        sub: _submissions(sub_rows, filer=sub),
    })
    db = _drive(
        monkeypatch, tmp_path,
        [_universe_row(parent, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END, name="DOW CHEMICAL"),
         _universe_row(sub, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END, name="DOW INC.")],
        [_spell_row(parent, "2016-07-01"), _spell_row(sub, "2019-07-01")], client,
    )
    got = _rows(
        db, "SELECT cik, severity, message FROM universe_validation_problems "
            "WHERE check_name='co_registrant_filing'"
    )
    assert len(got) == 1
    # The WARN is filed against the CIK whose attribution was LOST.
    assert got[0][0] == sub and got[0][1] == "WARN"
    assert str(parent) in got[0][2] and "0001751788-21-000001" in got[0][2]
    # ...and the row itself is stored exactly once, under the first (lowest,
    # so deterministic) CIK.
    assert _rows(
        db, "SELECT cik FROM filings WHERE accession_number='0001751788-21-000001'"
    ) == [(parent,)]


def test_no_co_registrant_warning_when_accessions_are_unique():
    assert im.coregistrant_problems({}) == []


def _co_registrant_run(monkeypatch, tmp_path, universe_order: list[int]):
    """Two members that co-file ONE 8-K, plus their own separate filings.
    `universe_order` controls the row order of the universe frame, so a test
    can prove the keeper rule does not depend on it."""
    low, high = 29915, 1751788
    shared = {"form": "8-K", "date": date(2021, 5, 3),
              "accession": "0001751788-21-000001", "items": ""}
    client = FakeClient({
        low: _submissions(
            _healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)) + [shared], filer=low),
        high: _submissions(
            _healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)) + [shared], filer=high),
    })
    rows = {
        low: _universe_row(low, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END,
                           name="DOW CHEMICAL CO /DE/"),
        high: _universe_row(high, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END,
                            name="DOW INC."),
    }
    db = _drive(
        monkeypatch, tmp_path, [rows[c] for c in universe_order],
        [_spell_row(low, "2016-07-01"), _spell_row(high, "2019-07-01")], client,
    )
    return db, low, high, shared["accession"]


def test_co_registered_accession_lands_one_filings_row_and_one_side_table_row(
    monkeypatch, tmp_path
):
    """The ruled shape (2026-08-24): `filings` keeps ONE row under the
    deterministic keeper, and the dropped attribution is a real row in
    `co_registrant_filings` -- not just a WARN string."""
    db, low, high, accession = _co_registrant_run(monkeypatch, tmp_path, [29915, 1751788])
    assert _rows(db, f"SELECT cik FROM filings WHERE accession_number='{accession}'") \
        == [(low,)]
    assert _rows(
        db, "SELECT accession_number, kept_cik, co_cik, form, filing_date "
            "FROM co_registrant_filings"
    ) == [(accession, low, high, "8-K", "2021-05-03")]


def test_keeper_is_the_lowest_member_cik_regardless_of_universe_row_order(
    monkeypatch, tmp_path
):
    """The keeper rule must be a property of the ingestion loop, not of the
    caller's row ordering: feed the universe HIGH-CIK-first and the lowest CIK
    must still keep the row."""
    db, low, high, accession = _co_registrant_run(monkeypatch, tmp_path, [1751788, 29915])
    assert _rows(db, f"SELECT cik FROM filings WHERE accession_number='{accession}'") \
        == [(low,)]
    assert _rows(db, "SELECT kept_cik, co_cik FROM co_registrant_filings") == [(low, high)]


def test_single_registrant_accessions_produce_no_side_table_rows(monkeypatch, tmp_path):
    """The side table must stay empty for the 99.8% ordinary case."""
    a, b = 111, 222
    client = FakeClient({
        a: _submissions(_healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)), filer=a),
        b: _submissions(_healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)), filer=b),
    })
    db = _drive(
        monkeypatch, tmp_path,
        [_universe_row(a, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END),
         _universe_row(b, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END)],
        [_spell_row(a, "2016-07-01"), _spell_row(b, "2016-07-01")], client,
    )
    assert _rows(db, "SELECT COUNT(*) FROM co_registrant_filings") == [(0,)]
    assert _rows(db, "SELECT COUNT(*) FROM universe_validation_problems "
                     "WHERE check_name='co_registrant_filing'") == [(0,)]


def test_side_table_and_filings_together_answer_the_coverage_question(
    monkeypatch, tmp_path
):
    """The binding downstream rule, expressed as the query F5 must use:
    absence from `filings` alone is NOT evidence a company did not file."""
    db, low, high, accession = _co_registrant_run(monkeypatch, tmp_path, [29915, 1751788])
    filings_only = _rows(
        db, f"SELECT COUNT(*) FROM filings WHERE cik={high} "
            f"AND accession_number='{accession}'"
    )
    assert filings_only == [(0,)]          # the naive query says "did not file"
    union = _rows(
        db,
        f"SELECT COUNT(*) FROM ("
        f"  SELECT accession_number FROM filings WHERE cik={high} "
        f"  UNION SELECT accession_number FROM co_registrant_filings WHERE co_cik={high}"
        f") WHERE accession_number='{accession}'"
    )
    assert union == [(1,)]                 # the correct query finds it


def test_side_table_write_is_idempotent(tmp_path):
    conn = sqlite3.connect(tmp_path / "e2.db")
    im.init_db(conn)
    rows = [{"accession_number": "A-1", "kept_cik": 1, "co_cik": 2,
             "form": "8-K", "filing_date": "2021-05-03"}]
    im.write_co_registrant_filings(conn, rows)
    im.write_co_registrant_filings(conn, rows)
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM co_registrant_filings").fetchone() == (1,)
    conn.close()


def test_load_universe_is_cik_ascending():
    """The keeper rule reads as 'the lowest member CIK' only because the
    universe arrives sorted; the loop re-sorts defensively, and this pins the
    source too."""
    ciks = list(im.load_universe()["cik"])
    assert ciks == sorted(ciks)


def test_enumeration_keeps_only_target_forms(monkeypatch, tmp_path):
    cik = 333
    rows = _healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)) + [
        {"form": "4", "date": date(2020, 5, 1)},
        {"form": "S-8", "date": date(2021, 5, 1)},
        {"form": "8-K", "date": date(2022, 5, 1)},
        {"form": "DEF 14A", "date": date(2023, 5, 1)},
    ]
    client = FakeClient({cik: _submissions(rows)})
    db = _drive(
        monkeypatch, tmp_path,
        [_universe_row(cik, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END)],
        [_spell_row(cik, "2016-07-01")], client,
    )
    forms = {f for (f,) in _rows(db, "SELECT DISTINCT form FROM filings")}
    assert forms <= im.TARGET_FORMS
    assert "8-K" in forms


# =====================================================================
# §4.5 -- distress events, at zero extra network cost
# =====================================================================


DISTRESS_FORMS_IN_SPEC = [
    "25", "25-NSE", "15-12B", "15-12G", "15-15D", "15F-12B", "15F-12G",
]


def test_extract_distress_events_covers_all_seven_forms_plus_item_1_03():
    d = date(2020, 1, 1)
    rows = [{"form": f, "date": d} for f in DISTRESS_FORMS_IN_SPEC]
    rows.append({"form": "8-K", "date": d, "items": "1.03,2.02"})
    events = im.extract_distress_events(
        _recent(rows), 999, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END
    )
    assert len(events) == 8
    by_form = {e["form"]: e["event_kind"] for e in events}
    assert by_form["25"] == "delisting_form_25"
    assert by_form["25-NSE"] == "delisting_form_25_nse_exchange_filed"
    for f in ("15-12B", "15-12G", "15-15D", "15F-12B", "15F-12G"):
        assert by_form[f] == "deregistration_form_15"
    assert by_form["8-K"] == im.BANKRUPTCY_EVENT_KIND
    assert all(e["cik"] == 999 for e in events)


def test_ordinary_8k_is_not_a_distress_event():
    d = date(2020, 1, 1)
    rows = [
        {"form": "8-K", "date": d, "items": "2.02,9.01"},
        {"form": "8-K", "date": d, "items": ""},
        {"form": "10-K", "date": d},
        {"form": "10-Q", "date": d},
        # The exact-code match: "11.03" must not read as item "1.03".
        {"form": "8-K", "date": d, "items": "11.03"},
    ]
    assert im.extract_distress_events(
        _recent(rows), 1, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END
    ) == []


def test_distress_events_are_windowed_like_the_filings():
    rows = [
        {"form": "25", "date": date(2014, 1, 1)},   # before the window
        {"form": "25", "date": date(2020, 1, 1)},   # inside
        {"form": "25", "date": date(2027, 1, 1)},   # after the freeze date
    ]
    events = im.extract_distress_events(
        _recent(rows), 7, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END
    )
    assert [e["filing_date"] for e in events] == ["2020-01-01"]


def test_distress_events_land_in_the_db_and_cost_no_extra_requests(monkeypatch, tmp_path):
    cik = 895126  # Expand Energy / Chesapeake -- the real item-1.03 filer
    rows = _healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)) + [
        {"form": "25-NSE", "date": date(2021, 3, 1), "accession": "0000000000-21-000001"},
        {"form": "15-12B", "date": date(2021, 4, 1), "accession": "0000000000-21-000002"},
        {"form": "8-K", "date": date(2020, 6, 28), "items": "1.03",
         "accession": "0000000000-20-000003"},
    ]
    client = FakeClient({cik: _submissions(rows)})
    db = _drive(
        monkeypatch, tmp_path,
        [_universe_row(cik, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END)],
        [_spell_row(cik, "2016-07-01")], client,
    )
    got = _rows(db, "SELECT form, event_kind FROM distress_events ORDER BY form")
    assert got == [
        ("15-12B", "deregistration_form_15"),
        ("25-NSE", "delisting_form_25_nse_exchange_filed"),
        ("8-K", im.BANKRUPTCY_EVENT_KIND),
    ]
    # The bankruptcy 8-K is BOTH a filing and a distress event -- same
    # accession number joins them, no double count of either.
    assert _rows(db, "SELECT COUNT(*) FROM filings WHERE accession_number='0000000000-20-000003'") \
        == [(1,)]
    # Zero extra network requests: only the ONE submissions read per company.
    assert client.effective_recent_calls.count(cik) == 2  # validate + ingest, both cached
    assert client.request_count == 0


def test_distress_event_write_is_idempotent(tmp_path):
    conn = sqlite3.connect(tmp_path / "e2.db")
    im.init_db(conn)
    events = im.extract_distress_events(
        _recent([{"form": "25", "date": date(2020, 1, 1), "accession": "A-1"}]),
        5, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END,
    )
    im.write_distress_events(conn, events)
    im.write_distress_events(conn, events)
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM distress_events").fetchone() == (1,)
    conn.close()


def test_summary_labels_the_noisy_25_nse_series():
    events = im.extract_distress_events(
        _recent([
            {"form": "25-NSE", "date": date(2020, 1, 1), "accession": "A-1"},
            {"form": "25", "date": date(2020, 1, 2), "accession": "A-2"},
        ]),
        5, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END,
    )
    text = im.summarize_distress_events(events)
    noisy_line = [ln for ln in text.splitlines() if "25_nse" in ln][0]
    clean_line = [ln for ln in text.splitlines()
                  if "delisting_form_25 " in ln or ln.strip().startswith("delisting_form_25 ")][0]
    assert "NOISY" in noisy_line
    assert "NOISY" not in clean_line


# =====================================================================
# §4.4 -- earnings_doc_unresolved accounting (the >1% rule)
# =====================================================================


def _failures(n: int) -> list[dict]:
    return [
        {"cik": 100 + i, "accession_number": f"0000000000-00-{i:06d}", "reason": "boom"}
        for i in range(n)
    ]


def test_one_failure_in_200_is_warn_only():
    problems = im.earnings_doc_unresolved_problems(_failures(1), 200)
    assert len(problems) == 1
    assert problems[0].severity == "WARN"
    assert problems[0].check == "earnings_doc_unresolved"
    assert not [p for p in problems if p.severity == "FATAL"]


def test_three_failures_in_200_is_fatal():
    problems = im.earnings_doc_unresolved_problems(_failures(3), 200)
    assert len(problems) == 4  # 3 per-case WARNs + 1 run-scoped FATAL
    assert sum(p.severity == "WARN" for p in problems) == 3
    fatal = [p for p in problems if p.severity == "FATAL"]
    assert len(fatal) == 1
    assert fatal[0].cik == im.RUN_SCOPE_CIK
    assert "1.50%" in fatal[0].message


def test_exactly_one_percent_is_not_fatal():
    """The rule is `> 1%`, not `>= 1%`. 2/200 sits exactly on the line."""
    problems = im.earnings_doc_unresolved_problems(_failures(2), 200)
    assert [p.severity for p in problems] == ["WARN", "WARN"]


def test_zero_failures_emits_nothing():
    assert im.earnings_doc_unresolved_problems([], 200) == []


def test_a_failed_index_parse_is_counted_not_just_printed(monkeypatch, tmp_path):
    """E1 printed a WARN and moved on, leaving the failure untracked. It must
    now land in universe_validation_problems."""
    cik = 555
    accession = "0000000000-20-000099"
    rows = _healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)) + [
        {"form": "8-K", "date": date(2020, 5, 1), "items": "2.02", "accession": accession},
    ]
    client = FakeClient({cik: _submissions(rows)})
    client.fail_index.add(accession)
    # 1 failure out of this company's 1 earnings 8-K is a 100% failure rate, so
    # the run also hard-fails on the aggregate arm -- and its findings must
    # still be on disk afterwards.
    with pytest.raises(SystemExit) as exc:
        _drive(
            monkeypatch, tmp_path,
            [_universe_row(cik, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END)],
            [_spell_row(cik, "2016-07-01")], client,
        )
    assert exc.value.code == 1
    db = tmp_path / "e2.db"
    got = _rows(
        db,
        "SELECT cik, severity, message FROM universe_validation_problems "
        "WHERE check_name='earnings_doc_unresolved' AND severity='WARN'",
    )
    assert len(got) == 1
    assert got[0][0] == cik and got[0][1] == "WARN"
    assert accession in got[0][2]
    # The filing itself is still stored -- with NULL earnings_doc_* columns.
    assert _rows(
        db, f"SELECT earnings_doc_filename FROM filings WHERE accession_number='{accession}'"
    ) == [(None,)]


# =====================================================================
# §4.4 -- the audit artifact
# =====================================================================


def _selection(cik: int, section_type: str, confidence: str, filing_date: str) -> dict:
    return {
        "cik": cik, "section_type": section_type,
        "selection_confidence": confidence, "filing_date": filing_date,
    }


def _tiny_universe() -> pd.DataFrame:
    return pd.DataFrame([
        _universe_row(320193, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END,
                      name="Apple Inc.", sector="tech"),
        _universe_row(18230, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END,
                      name="CATERPILLAR INC", sector="industrials", stratum="extension"),
    ])


def test_audit_aggregates_per_cik_section_type_and_confidence():
    audit = im.build_ex99_audit(
        [
            _selection(320193, "EX99_PRESS_RELEASE", "high", "2019-01-30"),
            _selection(320193, "EX99_PRESS_RELEASE", "high", "2017-05-02"),
            _selection(320193, "8K_BODY", "high", "2021-01-27"),
            _selection(18230, "EX99_PRESS_RELEASE", "low", "2016-10-25"),
        ],
        _tiny_universe(), e1_ciks={320193},
    )
    assert list(audit.columns) == list(im.EX99_AUDIT_COLUMNS)
    assert len(audit) == 3
    apple_high = audit[
        (audit["cik"] == 320193) & (audit["section_type"] == "EX99_PRESS_RELEASE")
    ].iloc[0]
    assert apple_high["n_filings"] == 2
    assert apple_high["first_seen_year"] == 2017     # earliest, not first-seen-in-list
    assert bool(apple_high["new_filer"]) is False    # one of E1's 25
    cat = audit[audit["cik"] == 18230].iloc[0]
    assert bool(cat["new_filer"]) is True
    assert cat["sector"] == "industrials" and cat["stratum"] == "extension"


def test_audit_csv_is_written_by_a_real_run(monkeypatch, tmp_path):
    cik = CAT_CIK
    accession = CAT_ACCESSION
    rows = _healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)) + [
        {"form": "8-K", "date": date(2016, 10, 25), "items": "2.02,9.01",
         "accession": accession, "primary": CAT_PRIMARY_DOCUMENT},
    ]
    client = FakeClient(
        {cik: _submissions(rows)},
        index_html={accession: CAT_INDEX_FIXTURE.read_text()},
    )
    _drive(
        monkeypatch, tmp_path,
        [_universe_row(cik, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END,
                       name="CATERPILLAR INC", sector="industrials", stratum="extension")],
        [_spell_row(cik, "2016-07-01", sector="industrials")], client,
    )
    audit = pd.read_csv(tmp_path / "ex99_selection_audit.csv")
    assert list(audit.columns) == list(im.EX99_AUDIT_COLUMNS)
    assert len(audit) == 1
    row = audit.iloc[0]
    assert row["cik"] == cik
    assert row["section_type"] == "EX99_PRESS_RELEASE"
    assert row["selection_confidence"] == "high"
    assert row["first_seen_year"] == 2016
    assert bool(row["new_filer"]) is True


def test_a_run_never_writes_the_real_audit_artifact(monkeypatch, tmp_path):
    """Guard against a test (or a stray run) clobbering
    data/f2/ex99_selection_audit.csv, which is a real run's output."""
    before = im.EX99_AUDIT_PATH.exists()
    cik = 777
    client = FakeClient({cik: _submissions(_healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)))})
    _drive(
        monkeypatch, tmp_path,
        [_universe_row(cik, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END)],
        [_spell_row(cik, "2016-07-01")], client,
    )
    assert im.EX99_AUDIT_PATH.exists() == before


# -- §4.4 item 5: sector coverage -------------------------------------


def test_sector_with_no_high_confidence_selection_is_a_blocker():
    universe = _tiny_universe()
    audit = im.build_ex99_audit(
        [
            _selection(320193, "EX99_PRESS_RELEASE", "high", "2019-01-30"),
            _selection(18230, "EX99_PRESS_RELEASE", "low", "2016-10-25"),
        ],
        universe, e1_ciks={320193},
    )
    problems = im.check_ex99_sector_coverage(
        audit, universe, {"tech": 40, "industrials": 40}
    )
    assert [p.severity for p in problems] == ["FATAL"]
    assert "industrials" in problems[0].message
    assert problems[0].check == "ex99_sector_coverage"


def test_sector_with_a_high_confidence_selection_is_clean():
    universe = _tiny_universe()
    audit = im.build_ex99_audit(
        [
            _selection(320193, "EX99_PRESS_RELEASE", "high", "2019-01-30"),
            _selection(18230, "EX99_PRESS_RELEASE", "high", "2016-10-25"),
        ],
        universe, e1_ciks={320193},
    )
    assert im.check_ex99_sector_coverage(
        audit, universe, {"tech": 40, "industrials": 40}
    ) == []


def test_sector_that_filed_no_earnings_8ks_warns_rather_than_blocking():
    """"The policy failed here" and "there was nothing to select from" are
    different findings and must not be conflated."""
    universe = _tiny_universe()
    audit = im.build_ex99_audit(
        [_selection(320193, "EX99_PRESS_RELEASE", "high", "2019-01-30")],
        universe, e1_ciks={320193},
    )
    problems = im.check_ex99_sector_coverage(audit, universe, {"tech": 40})
    assert [p.severity for p in problems] == ["WARN"]
    assert "zero earnings 8-Ks" in problems[0].message


def test_manual_read_worklist_names_the_low_confidence_filers(capsys):
    universe = _tiny_universe()
    audit = im.build_ex99_audit(
        [_selection(18230, "EX99_PRESS_RELEASE", "low", "2016-10-25"),
         _selection(18230, "8K_BODY", "high", "2017-10-25"),
         _selection(320193, "EX99_PRESS_RELEASE", "high", "2019-01-30")],
        universe, e1_ciks={320193},
    )
    im.print_ex99_audit_report(audit, _failures(1), 200, Path("/tmp/x.csv"))
    out = capsys.readouterr().out
    assert "CIKs needing the §4.4 manual read" in out
    assert "CIK 18230" in out
    assert "CIK 320193" not in out.split("manual read")[1]


def test_report_names_the_8k_body_class_and_counts_it(capsys):
    """The benign class the 2026-08-24 parse recalibration moved OUT of
    `earnings_doc_unresolved` has to be counted and named in the run
    summary, not folded silently into a total."""
    universe = _tiny_universe()
    audit = im.build_ex99_audit(
        [_selection(18230, "8K_BODY", "high", "2017-01-23"),
         _selection(18230, "8K_BODY", "high", "2017-04-23"),
         _selection(320193, "EX99_PRESS_RELEASE", "high", "2019-01-30")],
        universe, e1_ciks={320193},
    )
    im.print_ex99_audit_report(audit, [], 200, Path("/tmp/x.csv"))
    out = capsys.readouterr().out
    assert "of which 8K_BODY fallbacks: 2 filing(s) across 1 CIK(s)" in out
    assert "no EX-99 exhibit at all" in out


def test_report_says_nothing_about_8k_body_when_there_is_none(capsys):
    universe = _tiny_universe()
    audit = im.build_ex99_audit(
        [_selection(320193, "EX99_PRESS_RELEASE", "high", "2019-01-30")],
        universe, e1_ciks={320193},
    )
    im.print_ex99_audit_report(audit, [], 200, Path("/tmp/x.csv"))
    assert "8K_BODY fallbacks" not in capsys.readouterr().out


# =====================================================================
# §8.2 -- the 2016-era CAT index fixture (captured, never re-fetched)
# =====================================================================


def test_cat_2016_index_fixture_parses_to_six_rows():
    docs = im.parse_index_html_documents(
        CAT_INDEX_FIXTURE.read_text(), primary_document=CAT_PRIMARY_DOCUMENT
    )
    assert len(docs) == 6
    assert [d["doc_type"] for d in docs] == [
        "8-K", "EX-99.1", "GRAPHIC", "GRAPHIC", "GRAPHIC", "",
    ]


def test_cat_2016_selection_is_a_high_confidence_ex99_1():
    docs = im.parse_index_html_documents(
        CAT_INDEX_FIXTURE.read_text(), primary_document=CAT_PRIMARY_DOCUMENT
    )
    selection = im.select_earnings_document(
        docs, CAT_PRIMARY_DOCUMENT, subject=f"CIK {CAT_CIK}",
        accession_number=CAT_ACCESSION,
    )
    assert selection["filename"] == "cat_exx991xq3x2016xearning.htm"
    assert selection["section_type"] == "EX99_PRESS_RELEASE"
    assert selection["selection_confidence"] == "high"
    assert selection["is_exhibit"] is True
    assert selection["relative_path"].startswith("/Archives/edgar/data/18230/")


def test_fixture_is_byte_identical_to_the_cache_copy_if_the_cache_is_present():
    """Provenance guard: the fixture is a COPY of the S1 probe's cached index,
    not a hand-written approximation. Skips if the cache was cleared -- the
    cache is gitignored and regenerable, the fixture is not."""
    cached = REPO_ROOT / "data" / "raw" / "filing_index" / "18230_000001823016000702.html"
    if not cached.exists():
        pytest.skip("data/raw/ cache not present (gitignored, regenerable)")
    assert CAT_INDEX_FIXTURE.read_bytes() == cached.read_bytes()


# =====================================================================
# FILER DIALECTS -- the S6 segment-1 diagnosis (2026-08-24)
#
# Segment 1 ingested cleanly but tripped F2_SPEC §4.4's 1% ceiling:
# 400/10,569 earnings 8-Ks (3.78%) unresolved. Triage of all 400 against
# data/raw/filing_index/ found exactly two causes -- 64 index-parse
# failures, all one dialect, and 336 transient EDGAR 5xx/timeouts with no
# retry arm. Everything below pins the parser/policy half. Full write-up
# and the offline-replay numbers: data/f2/status/S6_seg1_ex99_diagnosis.md.
#
# One fixture per named handler, plus a NEGATIVE case: a dialect no handler
# claims must stay low-confidence, so these handlers can never quietly grow
# into "call everything high".
# =====================================================================


def test_dialect_fixtures_are_byte_identical_to_the_cache():
    """Same provenance guard as the CAT fixture, for all six dialect cases:
    every one is a copy of a real cached index, not a hand-written sample."""
    cache = REPO_ROOT / "data" / "raw" / "filing_index"
    if not cache.exists():
        pytest.skip("data/raw/ cache not present (gitignored, regenerable)")
    checked = 0
    for cik, accession, _ in (
        DIALECT_SINGLE_DOC_8K, DIALECT_ZERO_PADDED, DIALECT_PDF_PAIR_991,
        DIALECT_PDF_PAIR_BARE, DIALECT_BARE_BY_DESCRIPTION,
        DIALECT_UNRECOGNISED,
    ):
        cached = cache / f"{cik}_{accession.replace('-', '')}.html"
        if not cached.exists():
            continue
        assert _dialect_index(cik, accession).read_bytes() == cached.read_bytes()
        checked += 1
    if checked == 0:
        pytest.skip("no dialect index cached locally")


# -- dialect 1: the single-document 8-K (the whole 64-case parse FATAL) ----


def test_single_document_8k_index_parses_instead_of_raising():
    """The 64 parse failures were ALL this shape: an earnings 8-K that
    carries its release in the body with no exhibit, whose index has
    exactly two rows. The old >=3-row guard called that a broken parse."""
    cik, accession, primary = DIALECT_SINGLE_DOC_8K
    docs = im.parse_index_html_documents(
        _dialect_index(cik, accession).read_text(), primary_document=primary
    )
    assert len(docs) == 2
    assert [d["doc_type"] for d in docs] == ["8-K", ""]
    assert docs[0]["filename"] == primary


def test_single_document_8k_resolves_to_the_8k_body():
    selection = _select_from_fixture(DIALECT_SINGLE_DOC_8K)
    assert selection["filename"] == "hal_12312016-er8k.htm"
    assert selection["section_type"] == "8K_BODY"
    assert selection["selection_confidence"] == "high"
    assert selection["is_exhibit"] is False


def test_a_row_with_no_hyperlink_is_still_a_parse_failure():
    """The recalibration must not have removed the guard, only made it
    exact. A data row whose Document cell has no <a href> WOULD be dropped
    by this parser, so it still raises -- that is the failure mode the
    old >=3 threshold was standing in for."""
    html_text = """
    <table summary="Document Format Files">
      <tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th><th>Size</th></tr>
      <tr><td>1</td><td>8-K</td><td><a href="/Archives/edgar/data/1/2/a.htm">a.htm</a></td><td>8-K</td><td>1</td></tr>
      <tr><td>2</td><td>PRESS RELEASE</td><td>b.htm</td><td>EX-99.1</td><td>2</td></tr>
      <tr><td>&nbsp;</td><td>Complete submission text file</td><td><a href="/Archives/edgar/data/1/2/c.txt">c.txt</a></td><td>&nbsp;</td><td>3</td></tr>
    </table>
    """
    with pytest.raises(ValueError, match="no document hyperlink"):
        im.parse_index_html_documents(html_text)


def test_an_index_with_no_recognisable_table_is_still_a_parse_failure():
    with pytest.raises(ValueError, match="Parsed 0 document rows"):
        im.parse_index_html_documents("<html><body>nothing here</body></html>")


# -- dialect 2: zero-padded exhibit sub-numbers ---------------------------


def test_zero_padded_ex99_01_is_read_as_ex99_1():
    """Six E2 members type exhibit 99.1 as `EX-99.01` (198 earnings 8-Ks).
    The old policy picked the right file anyway, by lowest seq, but graded
    itself LOW -- putting four of them at the top of the §4.4 manual-read
    worklist for a pick that was never in doubt."""
    selection = _select_from_fixture(DIALECT_ZERO_PADDED)
    assert selection["filename"] == "ex9901-pressreleaseq42023.htm"
    assert selection["section_type"] == "EX99_PRESS_RELEASE"
    assert selection["selection_confidence"] == "high"


def test_canonical_exhibit_type_strips_only_a_leading_zero():
    assert im._canonical_exhibit_type("EX-99.01") == "EX-99.1"
    assert im._canonical_exhibit_type("EX-99.02") == "EX-99.2"
    assert im._canonical_exhibit_type("ex-99.01") == "EX-99.1"
    # EX-99.10 is a DIFFERENT exhibit from EX-99.1 -- never conflate them.
    assert im._canonical_exhibit_type("EX-99.10") == "EX-99.10"
    assert im._canonical_exhibit_type("EX-99.1") == "EX-99.1"
    assert im._canonical_exhibit_type("EX-99") == "EX-99"
    # Types the handler does not claim come back untouched.
    assert im._canonical_exhibit_type("EX-99.2O") == "EX-99.2O"
    assert im._canonical_exhibit_type("EX-99.0") == "EX-99.0"
    assert im._canonical_exhibit_type("8-K") == "8-K"


# -- dialect 3: one exhibit, two renditions (HTML + scanned PDF) ----------


def test_duplicate_ex99_1_html_and_pdf_takes_the_html_at_high_confidence():
    selection = _select_from_fixture(DIALECT_PDF_PAIR_991)
    assert selection["filename"] == "a16-2992_1ex99d1.htm"
    assert selection["selection_confidence"] == "high"


def test_duplicate_bare_ex99_html_and_pdf_takes_the_html_at_high_confidence():
    selection = _select_from_fixture(DIALECT_PDF_PAIR_BARE)
    assert selection["filename"] == "newsreleasea01.htm"
    assert selection["selection_confidence"] == "high"


def test_dropping_pdfs_never_empties_the_candidate_set():
    """A PDF-only exhibit is still the exhibit -- the handler breaks ties,
    it never deletes the only candidate."""
    only_pdf = [{"filename": "release.pdf"}]
    assert im._drop_pdf_renditions(only_pdf) == only_pdf


# -- dialect 4: several bare EX-99 exhibits, separable by description -----


def test_three_bare_ex99_exhibits_are_separated_by_description():
    """Eversource types the release, the financial report and the slide
    deck all as a bare `EX-99` (15 earnings 8-Ks). Lowest-seq happened to
    agree with the description scorer; the scorer says so on purpose."""
    selection = _select_from_fixture(DIALECT_BARE_BY_DESCRIPTION)
    assert selection["filename"] == "esthirdquarter2018earningsne.htm"
    assert selection["selection_confidence"] == "medium"


# -- the negative case: an unrecognised dialect must STAY low ------------


def test_unrecognised_exhibit_types_stay_low_confidence():
    """J&J types its 2018-2019 earnings exhibits `EX-99.15` and `EX-99.2O`
    (letter O). No handler claims either. The policy must keep grading
    itself LOW and send the filer to the §4.4 manual read rather than
    guessing -- 18 earnings 8-Ks."""
    selection = _select_from_fixture(DIALECT_UNRECOGNISED)
    assert selection["filename"] == "a2018q4exhibit9915.htm"
    assert selection["selection_confidence"] == "low"


def test_a_genuinely_ambiguous_duplicate_still_prints_a_canary(capsys):
    """The canary is a claim that the pick was arbitrary. Two distinct
    HTML EX-99.1 exhibits with unscoreable descriptions is exactly that."""
    docs = [
        {"filename": "a.htm", "relative_path": "/a.htm", "seq": 2,
         "doc_type": "EX-99.1", "description": "EXHIBIT 99.1"},
        {"filename": "b.htm", "relative_path": "/b.htm", "seq": 3,
         "doc_type": "EX-99.1", "description": "EXHIBIT 99.1"},
    ]
    selection = im.select_earnings_document(
        docs, "primary.htm", subject="CIK 1", accession_number="0000000000-00-000000"
    )
    assert selection["filename"] == "a.htm"
    assert selection["selection_confidence"] == "low"
    assert "CANARY" in capsys.readouterr().out


def test_a_resolved_duplicate_does_not_print_a_canary(capsys):
    """Corollary: once a handler resolves the duplicate, the canary must go
    quiet. A canary that fires on 208 filings the policy is sure about is
    the crying-wolf failure HANDOFF §4 already paid for once."""
    _select_from_fixture(DIALECT_PDF_PAIR_991)
    _select_from_fixture(DIALECT_BARE_BY_DESCRIPTION)
    assert "CANARY" not in capsys.readouterr().out


# =====================================================================
# §4.6 -- --stage documents
# =====================================================================


def _db_with_filings(tmp_path: Path, filings: list[tuple]) -> Path:
    """filings: (accession, cik, form, filing_date, primary_document,
    earnings_doc_relative_path)."""
    db = tmp_path / "e2.db"
    conn = sqlite3.connect(db)
    im.init_db(conn)
    conn.executemany(
        "INSERT INTO filings (accession_number, cik, form, filing_date, "
        "primary_document, earnings_doc_relative_path) VALUES (?, ?, ?, ?, ?, ?)",
        filings,
    )
    conn.commit()
    conn.close()
    return db


def test_document_targets_are_periodic_primaries_plus_resolved_earnings_paths(tmp_path):
    db = _db_with_filings(tmp_path, [
        ("0000320193-20-000001", 320193, "10-K", "2020-10-30", "aapl-20200926.htm", None),
        ("0000320193-20-000002", 320193, "10-Q", "2020-07-31", "aapl-20200627.htm", None),
        # An 8-K contributes its RESOLVED earnings path, never primary_document.
        ("0000320193-20-000003", 320193, "8-K", "2020-07-30", "a8-kq32020.htm",
         "/Archives/edgar/data/320193/000032019320000003/ex991.htm"),
        # An 8-K with no resolved earnings document contributes nothing.
        ("0000320193-20-000004", 320193, "8-K", "2020-02-18", "a8-k.htm", None),
    ])
    conn = sqlite3.connect(db)
    targets = im.document_prefetch_targets(conn)
    conn.close()
    paths = [t["relative_path"] for t in targets]
    assert paths == [
        "/Archives/edgar/data/320193/000032019320000003/ex991.htm",
        "/Archives/edgar/data/320193/000032019320000002/aapl-20200627.htm",
        "/Archives/edgar/data/320193/000032019320000001/aapl-20200926.htm",
    ]
    assert {t["kind"] for t in targets} == {"10-K", "10-Q", "earnings_doc"}
    assert not any("a8-k" in p for p in paths)


def test_document_targets_are_deduplicated(tmp_path):
    shared = "/Archives/edgar/data/1/000000000000000001/doc.htm"
    db = _db_with_filings(tmp_path, [
        ("0000000000-00-000001", 1, "10-K", "2020-01-01", "doc.htm", shared),
        ("0000000000-00-000002", 1, "10-Q", "2020-04-01", "other.htm", shared),
    ])
    conn = sqlite3.connect(db)
    targets = im.document_prefetch_targets(conn)
    conn.close()
    assert [t["relative_path"] for t in targets].count(shared) == 1


def test_stage_documents_requests_each_path_exactly_once(tmp_path):
    db = _db_with_filings(tmp_path, [
        ("0000000000-00-000001", 1, "10-K", "2020-01-01", "a.htm", None),
        ("0000000000-00-000002", 1, "10-Q", "2020-04-01", "b.htm", None),
        ("0000000000-00-000003", 1, "8-K", "2020-05-01", "c.htm",
         "/Archives/edgar/data/1/000000000000000003/ex991.htm"),
    ])
    client = FakeClient({}, cache_dir=tmp_path / "raw")
    conn = sqlite3.connect(db)
    problems = im.run_documents_stage(client, conn, date(2026, 8, 24))
    conn.close()
    assert len(client.document_calls) == 3
    assert len(set(client.document_calls)) == 3
    assert problems == []


def test_stage_documents_makes_zero_requests_for_already_cached_paths(tmp_path):
    """The idempotency property the whole cache-first rule rests on: a
    re-run's second pass must not touch the network AT ALL."""
    db = _db_with_filings(tmp_path, [
        ("0000000000-00-000001", 1, "10-K", "2020-01-01", "a.htm", None),
        ("0000000000-00-000002", 1, "10-Q", "2020-04-01", "b.htm", None),
    ])
    client = FakeClient({}, cache_dir=tmp_path / "raw")
    conn = sqlite3.connect(db)
    im.run_documents_stage(client, conn, date(2026, 8, 24))
    assert len(client.document_calls) == 2

    client.document_calls.clear()
    im.run_documents_stage(client, conn, date(2026, 8, 24))
    conn.close()
    assert client.document_calls == []


def test_stage_documents_counts_and_names_a_fetch_failure(tmp_path):
    bad = "/Archives/edgar/data/1/000000000000000002/b.htm"
    db = _db_with_filings(tmp_path, [
        ("0000000000-00-000001", 1, "10-K", "2020-01-01", "a.htm", None),
        ("0000000000-00-000002", 1, "10-Q", "2020-04-01", "b.htm", None),
    ])
    client = FakeClient({}, cache_dir=tmp_path / "raw")
    client.fail_documents.add(bad)
    conn = sqlite3.connect(db)
    problems = im.run_documents_stage(client, conn, date(2026, 8, 24))
    rows = conn.execute(
        "SELECT cik, stage, check_name, severity, message FROM "
        "universe_validation_problems"
    ).fetchall()
    conn.close()
    assert len(problems) == 1
    assert rows[0][:4] == (1, "documents", "document_fetch_failed", "WARN")
    assert bad in rows[0][4]
    # The walk continued -- the good document was still fetched.
    assert len(client.document_calls) == 2


def test_stage_documents_parses_nothing_and_writes_no_filing_text(tmp_path):
    db = _db_with_filings(tmp_path, [
        ("0000000000-00-000001", 1, "10-K", "2020-01-01", "a.htm", None),
    ])
    client = FakeClient({}, cache_dir=tmp_path / "raw")
    conn = sqlite3.connect(db)
    before = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("filings", "filing_documents", "companies", "distress_events")}
    im.run_documents_stage(client, conn, date(2026, 8, 24))
    after = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
             for t in ("filings", "filing_documents", "companies", "distress_events")}
    conn.close()
    assert before == after


def test_stage_documents_on_an_empty_filings_table_fails_loudly(tmp_path, capsys):
    db = _db_with_filings(tmp_path, [])
    conn = sqlite3.connect(db)
    with pytest.raises(SystemExit) as exc:
        im.run_documents_stage(FakeClient({}, cache_dir=tmp_path / "raw"), conn,
                               date(2026, 8, 24))
    conn.close()
    assert exc.value.code == 1
    assert "--stage metadata" in capsys.readouterr().out


def test_document_cache_path_agrees_with_the_client(tmp_path, monkeypatch):
    """THE guard on duplicating the client's cache-key derivation. If
    get_archive_document() ever writes somewhere else, the prefetch's skip
    check silently stops working and re-downloads ~26 GB -- so pin it."""
    client = ec.EdgarClient(cache_dir=tmp_path, verbose=False)
    rel = "/Archives/edgar/data/18230/000001823016000410/cat_10-kx12312015.htm"

    class FakeResponse:
        content = b"<html>hi</html>"
        text = "<html>hi</html>"

    monkeypatch.setattr(client, "_get", lambda url, params=None: FakeResponse())
    client.get_archive_document(rel)
    expected = im.document_cache_path(client, rel)
    assert expected.exists()
    assert expected.read_bytes() == b"<html>hi</html>"
    # And a leading-slash-less path resolves to the same file.
    assert im.document_cache_path(client, rel.lstrip("/")) == expected


def test_archive_document_path_matches_edgar_layout():
    assert im.archive_document_path(320193, "0000320193-20-000096", "aapl-20200926.htm") == \
        "/Archives/edgar/data/320193/000032019320000096/aapl-20200926.htm"


# -- stage selection ---------------------------------------------------


def test_stage_metadata_downloads_no_documents(monkeypatch, tmp_path):
    cik = 888
    accession = CAT_ACCESSION
    rows = _healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)) + [
        {"form": "8-K", "date": date(2016, 10, 25), "items": "2.02",
         "accession": accession, "primary": CAT_PRIMARY_DOCUMENT},
    ]
    client = FakeClient({cik: _submissions(rows)},
                        index_html={accession: CAT_INDEX_FIXTURE.read_text()},
                        cache_dir=tmp_path / "raw")
    _drive(monkeypatch, tmp_path,
           [_universe_row(cik, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END)],
           [_spell_row(cik, "2016-07-01")], client, stage="metadata")
    assert client.document_calls == []


def test_stage_all_runs_metadata_then_documents(monkeypatch, tmp_path):
    cik = 999
    accession = CAT_ACCESSION
    rows = _healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)) + [
        {"form": "8-K", "date": date(2016, 10, 25), "items": "2.02",
         "accession": accession, "primary": CAT_PRIMARY_DOCUMENT},
    ]
    client = FakeClient({cik: _submissions(rows)},
                        index_html={accession: CAT_INDEX_FIXTURE.read_text()},
                        cache_dir=tmp_path / "raw")
    _drive(monkeypatch, tmp_path,
           [_universe_row(cik, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END)],
           [_spell_row(cik, "2016-07-01")], client, stage="all")
    # Every 10-K/10-Q primary plus the one resolved EX-99.1.
    assert any("cat_exx991xq3x2016xearning.htm" in p for p in client.document_calls)
    assert len(client.document_calls) > 1


def test_stage_documents_alone_does_not_re_enumerate(monkeypatch, tmp_path):
    """Segment 2 must not re-pay segment 1's cost: no submissions reads, no
    validation, no universe walk."""
    cik = 1010
    client = FakeClient({cik: _submissions(_healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)))},
                        cache_dir=tmp_path / "raw")
    db = _drive(monkeypatch, tmp_path,
                [_universe_row(cik, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END)],
                [_spell_row(cik, "2016-07-01")], client, stage="metadata")
    client.effective_recent_calls.clear()
    _drive(monkeypatch, tmp_path,
           [_universe_row(cik, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END)],
           [_spell_row(cik, "2016-07-01")], client, stage="documents", db=db)
    assert client.effective_recent_calls == []
    assert client.document_calls, "the documents stage fetched nothing"


def test_unknown_stage_is_refused(tmp_path):
    with pytest.raises(ValueError, match="unknown --stage"):
        im.run(db_path=tmp_path / "e2.db", stage="everything")


def test_stage_choices_are_exactly_the_spec_three():
    assert im.STAGES == ("metadata", "documents", "all")
    assert im.DEFAULT_STAGE == "metadata"


# =====================================================================
# §4.2 -- the binding condition on full-window ingestion
# =====================================================================


def test_run_reports_filings_outside_every_membership_spell(monkeypatch, tmp_path, capsys):
    cik = 1212
    client = FakeClient({cik: _submissions(_healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)))})
    _drive(monkeypatch, tmp_path,
           [_universe_row(cik, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END)],
           # A member only from 2024-07-01: everything before that is ingested
           # (for trailing features) but is NOT universe membership.
           [_spell_row(cik, "2024-07-01")], client)
    out = capsys.readouterr().out
    assert "outside EVERY membership spell" in out
    assert "F5 must join on universe_membership" in out


def test_spell_containment_uses_exclusive_member_to():
    intervals = im._spell_intervals(pd.DataFrame([
        _spell_row(1, "2016-07-01", "2020-07-01"),
    ]))[1]
    assert im._inside_any_spell(intervals, date(2016, 7, 1)) is True
    assert im._inside_any_spell(intervals, date(2020, 6, 30)) is True
    # member_to is EXCLUSIVE (S2's measured clarification).
    assert im._inside_any_spell(intervals, date(2020, 7, 1)) is False
    assert im._inside_any_spell(intervals, date(2016, 6, 30)) is False


def test_open_spell_contains_every_later_date():
    intervals = im._spell_intervals(pd.DataFrame([_spell_row(1, "2024-07-01")]))[1]
    assert im._inside_any_spell(intervals, im.CORPUS_WINDOW_END) is True


# =====================================================================
# §4.3 -- edgar_client's max_age_hours passthrough (the ONLY change there)
# =====================================================================


class _FakeResponse:
    text = '{"ok": 1}'
    content = b'{"ok": 1}'


def _client_with_stale_cache(tmp_path: Path, monkeypatch, rel: str, age_hours: float):
    client = ec.EdgarClient(cache_dir=tmp_path, verbose=False)
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"cached": 1}')
    old = time.time() - age_hours * 3600
    os.utime(path, (old, old))
    calls: list[str] = []

    def fake_get(url, params=None):
        calls.append(url)
        return _FakeResponse()

    monkeypatch.setattr(client, "_get", fake_get)
    return client, calls


def test_get_submissions_default_ttl_is_still_24h(tmp_path, monkeypatch):
    client, calls = _client_with_stale_cache(
        tmp_path, monkeypatch, "submissions/CIK0000000123.json", age_hours=48
    )
    client.get_submissions(123)
    assert len(calls) == 1, "a 48h-old cache must still be refetched by default"


def test_get_submissions_max_age_hours_reuses_a_stale_cache(tmp_path, monkeypatch):
    client, calls = _client_with_stale_cache(
        tmp_path, monkeypatch, "submissions/CIK0000000123.json", age_hours=48
    )
    got = client.get_submissions(123, max_age_hours=168)
    assert calls == []
    assert got == {"cached": 1}


def test_get_submissions_max_age_hours_none_is_cache_forever(tmp_path, monkeypatch):
    client, calls = _client_with_stale_cache(
        tmp_path, monkeypatch, "submissions/CIK0000000123.json", age_hours=10_000
    )
    client.get_submissions(123, max_age_hours=None)
    assert calls == []


def test_get_submissions_chunk_and_companyfacts_take_max_age_hours(tmp_path, monkeypatch):
    client, calls = _client_with_stale_cache(
        tmp_path, monkeypatch, "submissions/CIK0000000123-submissions-001.json",
        age_hours=48,
    )
    client.get_submissions_chunk("CIK0000000123-submissions-001.json", max_age_hours=168)
    assert calls == []

    facts_path = tmp_path / "companyfacts" / "CIK0000000123.json"
    facts_path.parent.mkdir(parents=True, exist_ok=True)
    facts_path.write_text('{"cached": 1}')
    old = time.time() - 48 * 3600
    os.utime(facts_path, (old, old))
    client.get_companyfacts(123, max_age_hours=168)
    assert calls == []
    client.get_companyfacts(123)  # default 24h -> stale -> fetch
    assert len(calls) == 1


# =====================================================================
# TRANSIENT-FAILURE RETRY -- the other 336 of the S6 segment-1 failures
#
# Segment 1 took 309 bare `503 Service Unavailable` and 27 read timeouts
# across 10,841 GETs, with ZERO 429s. `_get()` retried 429 only, so every
# one became a permanently unresolved earnings document. These pin the
# retry arm, and pin that 403/4xx are still NOT retried.
# =====================================================================


class _StatusResponse:
    text = "ok"
    content = b"ok"
    headers: dict = {}

    def __init__(self, status_code: int):
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ec.requests.HTTPError(f"{self.status_code} error")


def _retry_client(monkeypatch, tmp_path, responses):
    """A real EdgarClient whose transport yields `responses` in order.
    Each entry is an int status code or an exception instance to raise.
    Sleep and the rate limiter are stubbed out so the test is instant."""
    client = ec.EdgarClient(cache_dir=tmp_path, verbose=False)
    calls: list[str] = []

    def fake_requests_get(url, headers=None, params=None, timeout=None):
        calls.append(url)
        nxt = responses[len(calls) - 1]
        if isinstance(nxt, Exception):
            raise nxt
        return _StatusResponse(nxt)

    monkeypatch.setattr(ec.requests, "get", fake_requests_get)
    monkeypatch.setattr(ec.time, "sleep", lambda s: None)
    monkeypatch.setattr(client.rate_limiter, "acquire", lambda: None)
    return client, calls


def test_a_503_is_retried_and_then_succeeds(monkeypatch, tmp_path):
    client, calls = _retry_client(monkeypatch, tmp_path, [503, 503, 200])
    resp = client._get("https://www.sec.gov/x")
    assert resp.status_code == 200
    assert len(calls) == 3


def test_a_read_timeout_is_retried_and_then_succeeds(monkeypatch, tmp_path):
    client, calls = _retry_client(
        monkeypatch, tmp_path, [ec.requests.ReadTimeout("read timed out"), 200]
    )
    assert client._get("https://www.sec.gov/x").status_code == 200
    assert len(calls) == 2


def test_a_persistent_503_still_fails_loudly(monkeypatch, tmp_path):
    """Retrying makes transient failures rare; it must not make them
    silent. After the retries are spent the caller still sees an error, so
    §4.4's earnings_doc_unresolved accounting still counts the case."""
    client, calls = _retry_client(monkeypatch, tmp_path, [503] * 10)
    with pytest.raises(ec.EdgarRequestError, match="HTTP 503 after"):
        client._get("https://www.sec.gov/x")
    assert len(calls) == client.max_retries + 1


def test_a_persistent_timeout_still_fails_loudly(monkeypatch, tmp_path):
    client, calls = _retry_client(
        monkeypatch, tmp_path, [ec.requests.ConnectTimeout("nope")] * 10
    )
    with pytest.raises(ec.EdgarRequestError, match="transient network failure"):
        client._get("https://www.sec.gov/x")
    assert len(calls) == client.max_retries + 1


def test_a_403_is_never_retried(monkeypatch, tmp_path):
    """403 means the User-Agent / fair-access policy is the problem.
    Hammering EDGAR with retries would be both useless and rude."""
    client, calls = _retry_client(monkeypatch, tmp_path, [403, 200])
    with pytest.raises(ec.EdgarRequestError, match="check User-Agent"):
        client._get("https://www.sec.gov/x")
    assert len(calls) == 1


def test_a_404_is_never_retried(monkeypatch, tmp_path):
    """A bad URL does not get better on the second try."""
    client, calls = _retry_client(monkeypatch, tmp_path, [404, 200])
    with pytest.raises(ec.requests.HTTPError):
        client._get("https://www.sec.gov/x")
    assert len(calls) == 1


def test_429_backoff_behaviour_is_unchanged(monkeypatch, tmp_path):
    client, calls = _retry_client(monkeypatch, tmp_path, [429, 200])
    assert client._get("https://www.sec.gov/x").status_code == 200
    assert len(calls) == 2


def test_get_effective_recent_threads_max_age_hours_to_both_reads(tmp_path, monkeypatch):
    client = ec.EdgarClient(cache_dir=tmp_path, verbose=False)
    seen: list[tuple[str, float | None]] = []

    def fake_submissions(cik, force=False, max_age_hours=ec.DEFAULT_MAX_AGE_HOURS):
        seen.append(("submissions", max_age_hours))
        return {
            "filings": {
                "recent": {"filingDate": ["2024-01-01"], "form": ["10-K"]},
                "files": [{"name": "chunk-1.json", "filingFrom": "2015-01-01",
                           "filingTo": "2023-12-31"}],
            }
        }

    def fake_chunk(name, force=False, max_age_hours=ec.DEFAULT_MAX_AGE_HOURS):
        seen.append(("chunk", max_age_hours))
        return {"filingDate": ["2016-01-01"], "form": ["10-K"]}

    monkeypatch.setattr(client, "get_submissions", fake_submissions)
    monkeypatch.setattr(client, "get_submissions_chunk", fake_chunk)
    client.get_effective_recent(123, date(2016, 1, 1), max_age_hours=168)
    assert seen == [("submissions", 168), ("chunk", 168)]


def test_cache_max_age_hours_reaches_the_client_from_run(monkeypatch, tmp_path):
    cik = 1313
    seen: list[float | None] = []
    client = FakeClient({cik: _submissions(_healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)))})

    def spy(c, cutoff, force=False, max_age_hours=None):
        seen.append(max_age_hours)
        return client.submissions_by_cik[c]["filings"]["recent"]

    client.get_effective_recent = spy
    monkeypatch.setattr(im, "load_universe",
                        lambda *a, **k: pd.DataFrame(
                            [_universe_row(cik, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END)]))
    monkeypatch.setattr(im, "load_membership",
                        lambda *a, **k: pd.DataFrame([_spell_row(cik, "2016-07-01")]))
    monkeypatch.setattr(im, "EdgarClient", lambda *a, **k: client)
    im.run(
        db_path=tmp_path / "e2.db",
        exceptions_path=tmp_path / "none.csv",
        ex99_audit_path=tmp_path / "audit.csv",
        max_age_hours=168,
    )
    assert seen and set(seen) == {168}


def test_default_cache_ttl_is_unchanged_at_24h():
    assert ec.DEFAULT_MAX_AGE_HOURS == 24.0
    assert im.DEFAULT_MAX_AGE_HOURS is ec.DEFAULT_MAX_AGE_HOURS


def test_edgar_client_document_and_index_caches_are_still_cache_forever(tmp_path, monkeypatch):
    """§4.3's cache table: filing_index/ and documents/ are immutable-once-filed
    and must NOT be affected by the submissions TTL knob."""
    client = ec.EdgarClient(cache_dir=tmp_path, verbose=False)
    idx = tmp_path / "filing_index" / "1_000000000000000002.html"
    idx.parent.mkdir(parents=True, exist_ok=True)
    idx.write_text("<html/>")
    old = time.time() - 10_000 * 3600
    os.utime(idx, (old, old))
    calls: list[str] = []
    monkeypatch.setattr(client, "_get", lambda url, params=None: calls.append(url) or _FakeResponse())
    client.get_filing_index_html(1, "0000000000-00-000002")
    assert calls == []


# =====================================================================
# Cross-cutting: the E1 CIK set used only for the new_filer flag
# =====================================================================


def test_e1_ciks_are_read_only_for_the_new_filer_flag():
    ciks = im.load_e1_ciks()
    assert len(ciks) == 25
    assert 320193 in ciks          # AAPL
    assert CAT_CIK not in ciks     # CAT is an E2 extension-stratum newcomer


def test_missing_e1_universe_csv_flags_everyone_as_a_new_filer(tmp_path):
    assert im.load_e1_ciks(tmp_path / "nope.csv") == set()


# =====================================================================
# S6 EX-99 manual-read fix package (F2_PROGRESS §5 ruling 2026-08-24)
#
# Fixtures are byte-identical copies of cached filing indices (verified by
# test_fix_package_fixtures_match_the_cache below). Zero network.
# =====================================================================

PLD_CIK = 1045609
PLD_POST_SPLIT = "filing_index_CIK0001045609_0001564590-19-036903.html"   # 2019-10-15
PLD_POST_SPLIT_BARE = "filing_index_CIK0001045609_0000950170-23-013170.html"  # 2023-04-18
PLD_PRE_SPLIT = "filing_index_CIK0001045609_0001564590-16-016339.html"    # 2016-04-19
NVDA_TYPO = "filing_index_CIK0001045810_0001045810-19-000168.html"        # 2019-11-14
T_NO_RELEASE = "filing_index_CIK0000732717_0000732717-19-000048.html"     # AT&T 2019-10-28
OKE_TYPO = "filing_index_CIK0001039684_0001039684-15-000073.html"         # ONEOK 2015-11-03
MU_TYPO = "filing_index_CIK0000723125_0000723125-19-000172.html"          # Micron 2019-12-18
PLD_PIONEER_DECK = "filing_index_CIK0001038357_0001193125-18-111008.html"  # Pioneer IPAA deck


def _fixture_docs(name: str, primary_document: str | None = None) -> list[dict]:
    return im.parse_index_html_documents(
        (FIXTURES / name).read_text(), primary_document=primary_document
    )


def test_fix_package_fixtures_match_the_cache():
    """Provenance: every fixture below is a COPY of a cached filing index, not
    a hand-written approximation. Skips if the gitignored cache was cleared."""
    pairs = {
        PLD_POST_SPLIT: "1045609_000156459019036903.html",
        PLD_POST_SPLIT_BARE: "1045609_000095017023013170.html",
        PLD_PRE_SPLIT: "1045609_000156459016016339.html",
        NVDA_TYPO: "1045810_000104581019000168.html",
        T_NO_RELEASE: "732717_000073271719000048.html",
        OKE_TYPO: "1039684_000103968415000073.html",
        MU_TYPO: "723125_000072312519000172.html",
    }
    cache = REPO_ROOT / "data" / "raw" / "filing_index"
    if not cache.exists():
        pytest.skip("data/raw/ cache not present (gitignored, regenerable)")
    for fixture, cached in pairs.items():
        if not (cache / cached).exists():
            continue
        assert (FIXTURES / fixture).read_bytes() == (cache / cached).read_bytes(), fixture


# -- P1: exhibit number from description (confidence only) -------------


@pytest.mark.parametrize("description,expected", [
    ("EX-99.1", "EX-99.1"),
    ("EXHIBIT 99.1", "EX-99.1"),
    ("Exhibit 99.2", "EX-99.2"),
    ("EX-99.10", "EX-99.10"),
    ("2020 Q1 EXHIBIT 99.1 PRESS RELEASE", "EX-99.1"),
    ("GRAPHIC", None),
    ("", None),
    ("PRESS RELEASE", None),
])
def test_exhibit_number_from_description(description, expected):
    assert im._exhibit_number_from_description(description) == expected


def _bare_ex99_docs():
    """Two bare EX-99 rows whose numbers live in the description column --
    the Sempra / Weyerhaeuser / Welltower / BlackRock shape."""
    return [
        {"seq": 1, "doc_type": "8-K", "description": "8-K", "filename": "f8k.htm",
         "relative_path": "/a/f8k.htm", "source_table": "Document Format Files"},
        {"seq": 2, "doc_type": "EX-99", "description": "EXHIBIT 99.1",
         "filename": "release.htm", "relative_path": "/a/release.htm",
         "source_table": "Document Format Files"},
        {"seq": 3, "doc_type": "EX-99", "description": "EXHIBIT 99.2",
         "filename": "slides.htm", "relative_path": "/a/slides.htm",
         "source_table": "Document Format Files"},
    ]


def test_p1_upgrades_confidence_without_changing_the_pick():
    docs = _bare_ex99_docs()
    sel = im.select_earnings_document(docs, "f8k.htm", accession_number="A-1")
    assert sel["filename"] == "release.htm"       # the pick lowest-seq already made
    assert sel["selection_confidence"] == "high"  # ...now labelled honestly


def test_p1_does_not_fire_when_the_described_991_is_not_the_lowest_seq_pick():
    """The zero-pick-change guarantee: if the description numbering points at a
    DIFFERENT document than lowest-seq chose, P1 must stay silent rather than
    move the pick."""
    docs = _bare_ex99_docs()
    docs[1]["description"] = "EXHIBIT 99.2"   # seq 2 is now 99.2 ...
    docs[2]["description"] = "EXHIBIT 99.1"   # ... and seq 3 is 99.1
    sel = im.select_earnings_document(docs, "f8k.htm", accession_number="A-1")
    assert sel["filename"] == "release.htm"        # unchanged: still lowest seq
    assert sel["selection_confidence"] == "low"    # and still honestly uncertain


def test_p1_leaves_a_single_bare_ex99_alone():
    docs = [d for d in _bare_ex99_docs() if d["seq"] != 3]
    sel = im.select_earnings_document(docs, "f8k.htm")
    assert sel["filename"] == "release.htm" and sel["selection_confidence"] == "high"


# -- P2: the Prologis handler ------------------------------------------


def test_prologis_post_split_takes_ex99_2():
    """2019-10-15: the filer's own index calls EX-99.2 'PRESS RELEASE, DATED
    OCTOBER 15, 2019.' while EX-99.1 is the Supplemental."""
    docs = _fixture_docs(PLD_POST_SPLIT, "pld-8k_20191015.htm")
    sel = im.select_earnings_document(
        docs, "pld-8k_20191015.htm", cik=PLD_CIK, filing_date="2019-10-15")
    assert sel["filename"] == "pld-ex992_68.htm"
    assert sel["section_type"] == "EX99_PRESS_RELEASE"
    assert sel["selection_confidence"] == "high"


def test_prologis_post_split_bare_ex99_rows_still_reach_ex99_2():
    """2023-04-18 types BOTH exhibits a bare `EX-99` and puts the numbers in
    the description. A type-only lookup would miss it -- and these are exactly
    the two filings the manual read happened to catch."""
    docs = _fixture_docs(PLD_POST_SPLIT_BARE, "pld-20230418.htm")
    assert {d["doc_type"] for d in docs if d["doc_type"].startswith("EX-99")} == {"EX-99"}
    sel = im.select_earnings_document(
        docs, "pld-20230418.htm", cik=PLD_CIK, filing_date="2023-04-18")
    assert sel["filename"] == "pld-ex99_2.htm"
    assert sel["selection_confidence"] == "high"


def test_prologis_pre_split_keeps_ex99_1():
    """Before the split the EX-99.1 IS the release ("Earnings Release and
    Supplemental Information", with a Press Release ToC entry and a dateline),
    so the handler must not fire.

    Dated 2016-01-26 -- the last genuinely-combined filing. This test used to
    use 2016-04-19, which the 2026-08-24 content re-verification showed is a
    template-leftover title over a body with no release, moving the split date
    onto it (see test_prologis_2016_04_19_now_takes_ex99_2)."""
    docs = _fixture_docs(PLD_PRE_SPLIT, "pld-8k_20160419.htm")
    sel = im.select_earnings_document(
        docs, "pld-8k_20160419.htm", cik=PLD_CIK, filing_date="2016-01-26")
    assert sel["filename"] == "pld-ex991_6.htm"


def test_prologis_split_date_boundary_is_exact():
    docs = _fixture_docs(PLD_POST_SPLIT, "pld-8k_20191015.htm")
    day_before = im.PROLOGIS_SUPPLEMENTAL_SPLIT - timedelta(days=1)
    assert im._prologis_earnings_document(docs, day_before) is None
    assert im._prologis_earnings_document(docs, im.PROLOGIS_SUPPLEMENTAL_SPLIT) is not None


def test_prologis_handler_is_scoped_to_prologis_only():
    """A named per-filer handler must not touch any other filer: the same
    document shape under a different CIK keeps the generic EX-99.1 pick."""
    docs = _fixture_docs(PLD_POST_SPLIT, "pld-8k_20191015.htm")
    sel = im.select_earnings_document(
        docs, "pld-8k_20191015.htm", cik=CAT_CIK, filing_date="2019-10-15")
    assert sel["filename"] == "pld-ex991_69.htm"
    assert im.PER_FILER_EARNINGS_HANDLERS.keys() == {im.PROLOGIS_CIK, im.PSEG_CIK}


def test_prologis_handler_needs_both_cik_and_filing_date():
    """A caller that omits either degrades to the generic policy rather than
    crashing -- the E1 call shape must stay safe."""
    docs = _fixture_docs(PLD_POST_SPLIT, "pld-8k_20191015.htm")
    assert im.select_earnings_document(docs, "pld-8k_20191015.htm")["filename"] \
        == "pld-ex991_69.htm"
    assert im.select_earnings_document(
        docs, "pld-8k_20191015.htm", cik=PLD_CIK)["filename"] == "pld-ex991_69.htm"


def test_prologis_handler_declines_when_there_is_no_ex99_2():
    """If the expected EX-99.2 is absent the handler returns None and the
    generic ladder runs -- it never invents a pick."""
    docs = [d for d in _fixture_docs(PLD_POST_SPLIT) if d["filename"] != "pld-ex992_68.htm"]
    assert im._prologis_earnings_document(docs, date(2019, 10, 15)) is None


# -- The evidenced override file ---------------------------------------


def test_shipped_overrides_file_has_exactly_the_nine_ratified_rows():
    """Nine rows: seven `select_document` and TWO `exclude`. The mechanism
    absorbs measured singletons so that no new policy route is needed --
    future instances of these shapes stay loud-UNRESOLVED or loud-mis-labelled
    until a human rules on them."""
    overrides = im.load_earnings_doc_overrides()
    assert set(overrides) == im.RATIFIED_EARNINGS_DOC_OVERRIDES
    assert set(overrides) == {
        "0001045810-19-000168",   # NVIDIA    EX-95.1
        "0001039684-15-000073",   # ONEOK     EX-95.1
        "0000723125-19-000172",   # Micron    EX-99..1
        "0001110803-16-000185",   # Illumina  EX-1
        "0001110803-16-000194",   # Illumina  EX-1
        "0001645590-17-000006",   # HPE       EX-1 (two candidates)
        "0001637459-19-000050",   # Kraft Heinz EX-1
        "0000732717-19-000048",   # AT&T      no release present
        "0001193125-18-111008",   # Pioneer   IPAA slide deck, not a release
    }
    assert len(overrides) == 9
    assert len([a for a, o in overrides.items() if o.excludes]) == 2
    assert overrides["0001045810-19-000168"].document == "q3fy20pr.htm"
    assert overrides["0001039684-15-000073"].document == "okeq32015earningsreleasenr.htm"
    assert overrides["0000723125-19-000172"].document == "a2020q1exhibit991-pres.htm"
    assert len([a for a, o in overrides.items() if o.action == "select_document"]) == 7
    assert overrides["0000732717-19-000048"].action == "exclude"
    assert overrides["0000732717-19-000048"].excludes is True
    for ov in overrides.values():
        assert len(ov.evidence) >= im.MIN_EARNINGS_OVERRIDE_EVIDENCE_CHARS
        assert ov.reason and ov.added


def _overrides_csv(tmp_path: Path, *rows: str) -> Path:
    p = tmp_path / "earnings_doc_overrides.csv"
    p.write_text(",".join(im.EARNINGS_DOC_OVERRIDE_COLUMNS) + "\n" + "\n".join(rows) + "\n")
    return p


EV = "x" * im.MIN_EARNINGS_OVERRIDE_EVIDENCE_CHARS


def test_missing_overrides_file_is_a_legitimate_empty_state(tmp_path: Path):
    assert im.load_earnings_doc_overrides(tmp_path / "nope.csv") == {}


def test_undocumented_accession_is_refused_at_load(tmp_path: Path):
    p = _overrides_csv(tmp_path, f"9999999999-99-999999,select_document,x.htm,r,{EV},2026-08-24")
    with pytest.raises(ValueError, match="not a ratified override case"):
        im.load_earnings_doc_overrides(p)


def test_override_without_evidence_is_refused(tmp_path: Path):
    p = _overrides_csv(tmp_path, "0001045810-19-000168,select_document,q3fy20pr.htm,r,short,2026-08-24")
    with pytest.raises(ValueError, match="evidence"):
        im.load_earnings_doc_overrides(p)


def test_unknown_action_is_refused(tmp_path: Path):
    p = _overrides_csv(tmp_path, f"0001045810-19-000168,delete,,r,{EV},2026-08-24")
    with pytest.raises(ValueError, match="unknown action"):
        im.load_earnings_doc_overrides(p)


def test_exclude_row_may_not_name_a_document(tmp_path: Path):
    p = _overrides_csv(tmp_path, f"0000732717-19-000048,exclude,x.htm,r,{EV},2026-08-24")
    with pytest.raises(ValueError, match="must leave `document` empty"):
        im.load_earnings_doc_overrides(p)


def test_select_document_row_must_name_a_document(tmp_path: Path):
    p = _overrides_csv(tmp_path, f"0001045810-19-000168,select_document,,r,{EV},2026-08-24")
    with pytest.raises(ValueError, match="requires"):
        im.load_earnings_doc_overrides(p)


def test_duplicate_override_rows_are_refused(tmp_path: Path):
    row = f"0001045810-19-000168,select_document,q3fy20pr.htm,r,{EV},2026-08-24"
    with pytest.raises(ValueError, match="duplicate"):
        im.load_earnings_doc_overrides(_overrides_csv(tmp_path, row, row))


def test_nvidia_override_selects_the_ex95_1_typo_release():
    docs = _fixture_docs(NVDA_TYPO, "form8-kq3fy20.htm")
    policy = im.select_earnings_document(docs, "form8-kq3fy20.htm", cik=1045810,
                                         filing_date="2019-11-14")
    assert policy["filename"] == "q3fy20cfocommentary.htm"      # the defect
    ov = im.load_earnings_doc_overrides()["0001045810-19-000168"]
    fixed = im.apply_earnings_doc_override(ov, docs)
    assert fixed["filename"] == "q3fy20pr.htm"
    assert fixed["selection_confidence"] == "high"
    assert fixed["section_type"] == "EX99_PRESS_RELEASE"


def test_oneok_override_replaces_an_8k_cover_page_with_the_real_release():
    """The defect this row fixes is worse than NVIDIA's: with no EX-99 row at
    all the policy fell through to 8K_BODY and took the 8-K COVER PAGE, at
    HIGH confidence."""
    docs = _fixture_docs(OKE_TYPO, "okeq32015earningsrelease.htm")
    # The B1 candidate screen (2026-08-24) now resolves this filing on its own:
    # the EX-95.1 row's description, "OKE Q3 2015 EARNINGS RELEASE NEWS
    # RELEASE", is release-shaped, so the general fix reaches the same document
    # the override names -- at MEDIUM, since description evidence is not a
    # canonical type. Before that fix the policy took the 8-K COVER PAGE at
    # 8K_BODY/high, which is the defect this row was written for.
    policy = im.select_earnings_document(
        docs, "okeq32015earningsrelease.htm", cik=1039684, filing_date="2015-11-03")
    assert policy["filename"] == "okeq32015earningsreleasenr.htm"
    assert policy["selection_confidence"] == "medium"

    ov = im.load_earnings_doc_overrides()["0001039684-15-000073"]
    fixed = im.apply_earnings_doc_override(ov, docs)
    assert fixed["filename"] == "okeq32015earningsreleasenr.htm"
    assert fixed["section_type"] == "EX99_PRESS_RELEASE"
    assert fixed["selection_confidence"] == "high"


def test_micron_override_handles_the_double_dot_type_string():
    docs = _fixture_docs(MU_TYPO, "a2020q18-kearningsrele.htm")
    assert "EX-99..1" in {d["doc_type"] for d in docs}
    # As with ONEOK, the B1 candidate screen now reaches the same document the
    # override names (description "2020 Q1 EXHIBIT 99.1 PRESS RELEASE"), at
    # medium. Pre-fix this was the 8-K cover page at 8K_BODY/high.
    policy = im.select_earnings_document(
        docs, "a2020q18-kearningsrele.htm", cik=723125, filing_date="2019-12-18")
    assert policy["filename"] == "a2020q1exhibit991-pres.htm"
    assert policy["selection_confidence"] == "medium"

    ov = im.load_earnings_doc_overrides()["0000723125-19-000172"]
    fixed = im.apply_earnings_doc_override(ov, docs)
    assert fixed["filename"] == "a2020q1exhibit991-pres.htm"
    assert fixed["section_type"] == "EX99_PRESS_RELEASE"


def test_malformed_types_stay_outside_the_family_but_are_now_candidates():
    """The type family is still NOT widened -- but that alone is no longer the
    whole story, and the docstring this test used to carry had the reasoning
    backwards (S7 red-team B1).

    It claimed non-recognition prevented "a silent mis-pick generator". The
    measurement says the opposite: NOT recognising these types is what sent 14
    filings to the unconditional 8K_BODY fallback and stored SEC cover pages as
    earnings documents at HIGH confidence. Non-recognition is correct for the
    SELECTION LADDER (a malformed type must never win it on type alone); the
    missing piece was the FALLBACK, which now checks for unselected candidates
    instead of silently taking the body."""
    for malformed in ("EX-99..1", "EX-95.1", "EX-99.2O", "EX-99.1PRE", "EX-1"):
        assert not im._EX99_FAMILY_RE.match(im._canonical_exhibit_type(malformed)), malformed
    assert im._canonical_exhibit_type("EX-99..1") == "EX-99..1"
    # ...and they ARE reachable as fallback candidates, which is the fix.
    row = {"seq": 2, "doc_type": "EX-99..1", "description": "EXHIBIT 99..1",
           "filename": "ex991pressrelease.htm", "relative_path": "/a/x.htm",
           "source_table": "t"}
    assert im.earnings_candidate_rows([row], "body.htm") == [row]


def test_att_override_excludes_rather_than_mislabelling():
    docs = _fixture_docs(T_NO_RELEASE, "ex99_1.htm")
    ov = im.load_earnings_doc_overrides()["0000732717-19-000048"]
    assert im.apply_earnings_doc_override(ov, docs) is None


def test_stale_override_fails_loudly_instead_of_resolving_to_nothing(tmp_path: Path):
    docs = _fixture_docs(NVDA_TYPO)
    stale = im.EarningsDocOverride(
        "0001045810-19-000168", "select_document", "gone.htm", "r", EV, "2026-08-24")
    with pytest.raises(ValueError, match="stale or"):
        im.apply_earnings_doc_override(stale, docs)


def test_dead_override_is_reported(capsys):
    overrides = im.load_earnings_doc_overrides()
    im.print_earnings_doc_override_report(overrides, fired=set())
    out = capsys.readouterr().out
    assert "9 row(s), 0 fired, 9 DEAD" in out
    for accession in im.RATIFIED_EARNINGS_DOC_OVERRIDES:
        assert accession in out


def test_override_end_to_end_excludes_and_counts(monkeypatch, tmp_path):
    """The AT&T shape through run(): no earnings doc stored, an INFO row, an
    audit row -- and NOT counted as an unresolved failure."""
    cik = 732717
    accession = "0000732717-19-000048"
    rows = _healthy(im.CORPUS_WINDOW_START, date(2026, 8, 1)) + [
        {"form": "8-K", "date": date(2019, 10, 28), "items": "2.02",
         "accession": accession, "primary": "q3earnings801_8k.htm"},
    ]
    client = FakeClient({cik: _submissions(rows, filer=cik)},
                        index_html={accession: (FIXTURES / T_NO_RELEASE).read_text()},
                        cache_dir=tmp_path / "raw")
    db = _drive(
        monkeypatch, tmp_path,
        [_universe_row(cik, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END,
                       name="AT&T INC.", sector="utilities")],
        [_spell_row(cik, "2016-07-01", sector="utilities")], client,
        overrides_path=im.EARNINGS_DOC_OVERRIDES_PATH,
    )
    assert _rows(db, f"SELECT earnings_doc_filename, earnings_doc_section_type FROM "
                     f"filings WHERE accession_number='{accession}'") == [(None, None)]
    problems = _rows(db, "SELECT check_name, severity FROM universe_validation_problems "
                         "WHERE check_name LIKE 'earnings_doc%'")
    assert ("earnings_doc_excluded_by_override", "INFO") in problems
    assert not [p for p in problems if p[0] == "earnings_doc_unresolved"]
    audit = pd.read_csv(tmp_path / "ex99_selection_audit.csv")
    assert im.EXCLUDED_SECTION_TYPE in set(audit["section_type"])


def test_excluded_section_type_never_reaches_the_db_taxonomy():
    """P4's new section_type was ruled OUT (it touches F4 applicability). The
    exclusion marker lives in the audit artifact only."""
    assert im.EXCLUDED_SECTION_TYPE not in ("EX99_PRESS_RELEASE", "8K_BODY")
    # _resolved() is the only producer of a section_type that reaches the DB,
    # and it can never emit the marker: an exclusion resolves to None.
    docs = _fixture_docs(T_NO_RELEASE, "q3earnings801_8k.htm")
    ov = im.load_earnings_doc_overrides()["0000732717-19-000048"]
    assert im.apply_earnings_doc_override(ov, docs) is None


# -- P3: a press release typed outside the EX-99 family ----------------


def test_p3_fires_on_the_nvidia_ex95_typo():
    docs = _fixture_docs(NVDA_TYPO, "form8-kq3fy20.htm")
    hits = im.press_release_typed_outside_ex99(docs, "q3fy20cfocommentary.htm")
    assert [h["doc_type"] for h in hits] == ["EX-95.1"]
    assert hits[0]["filename"] == "q3fy20pr.htm"


def test_p3_fires_on_the_oneok_ex95_typo_where_the_fallback_took_a_cover_page():
    """A NEW finding this WARN surfaced (the manual read binned it benign):
    ONEOK's release is typed EX-95.1, no EX-99 exists, so the policy fell back
    to the 8-K COVER PAGE -- 3,179 characters of SEC boilerplate."""
    docs = _fixture_docs(OKE_TYPO, "okeq32015earningsrelease.htm")
    hits = im.press_release_typed_outside_ex99(docs, "okeq32015earningsrelease.htm")
    assert [h["doc_type"] for h in hits] == ["EX-95.1"]


def test_p3_ignores_the_8k_cover_row_described_as_an_earnings_release():
    """33 of the 36 raw hits over the corpus were this shape -- the cover row
    is routinely NAMED '...EARNINGS RELEASE'. Not a finding."""
    docs = [
        {"seq": 1, "doc_type": "8-K", "description": "Q3 2015 EARNINGS RELEASE",
         "filename": "f8k.htm", "relative_path": "/a/f8k.htm", "source_table": "t"},
        {"seq": 2, "doc_type": "EX-99.1", "description": "PRESS RELEASE",
         "filename": "ex991.htm", "relative_path": "/a/ex991.htm", "source_table": "t"},
    ]
    assert im.press_release_typed_outside_ex99(docs, "ex991.htm") == []


def test_p3_ignores_graphic_news_release_header_images():
    """15 of the 18 remaining raw hits are Eversource/AvalonBay news-release
    HEADER LOGOS -- images, not documents."""
    docs = [
        {"seq": 2, "doc_type": "GRAPHIC", "description": "NEWS RELEASE HEADER",
         "filename": "hdr.jpg", "relative_path": "/a/hdr.jpg", "source_table": "t"},
        {"seq": 3, "doc_type": "EX-99.1", "description": "EX-99.1",
         "filename": "ex991.htm", "relative_path": "/a/ex991.htm", "source_table": "t"},
    ]
    assert im.press_release_typed_outside_ex99(docs, "ex991.htm") == []


def test_p3_never_changes_the_pick():
    """The WARN is a pointer, not a fix: the selection is untouched and the
    override file is the resolution path."""
    docs = _fixture_docs(NVDA_TYPO, "form8-kq3fy20.htm")
    before = im.select_earnings_document(docs, "form8-kq3fy20.htm", cik=1045810,
                                         filing_date="2019-11-14")
    im.press_release_typed_outside_ex99(docs, before["filename"])
    after = im.select_earnings_document(docs, "form8-kq3fy20.htm", cik=1045810,
                                        filing_date="2019-11-14")
    assert before["filename"] == after["filename"] == "q3fy20cfocommentary.htm"


def test_p3_problems_name_the_accession_and_point_at_the_override_file():
    hits = [{"cik": 1045810, "accession_number": "0001045810-19-000168",
             "doc_type": "EX-95.1", "description": "Q3FY20 PRESS RELEASE",
             "filename": "q3fy20pr.htm", "selected": "q3fy20cfocommentary.htm"}]
    probs = im.press_release_outside_ex99_problems(hits)
    assert len(probs) == 1 and probs[0].severity == "WARN"
    assert probs[0].check == "press_release_typed_outside_ex99"
    assert "0001045810-19-000168" in probs[0].message
    assert "earnings_doc_overrides.csv" in probs[0].message


# -- P5: thin / image-only / empty exhibits ----------------------------


def test_screen_counts_text_images_and_release_language():
    s = im.screen_selected_document(
        "<html><body><h1>ACME CORP EXHIBIT 99.1</h1><p>" + "filler text. " * 30 +
        "</p><p>Acme today reported record results.</p>"
        "<img src='a.jpg'><img src='b.jpg'></body></html>")
    assert s["images"] == 2
    assert s["has_release_language"] is True
    assert s["chars"] > 20


def test_screen_treats_nbsp_only_body_as_empty():
    """Cigna's 454-byte exhibit: two &nbsp; paragraphs and 'Exhibit 99.1'."""
    s = im.screen_selected_document("<html><body><p>&nbsp;</p><p>&nbsp;</p></body></html>")
    assert s["chars"] < im.EMPTY_EXHIBIT_CHARS
    assert s["images"] == 0
    assert s["has_release_language"] is False


def _screen_run(tmp_path: Path, docs_by_path: dict[str, str], selections: list[dict]):
    client = FakeClient({}, cache_dir=tmp_path / "raw")
    for rel, body in docs_by_path.items():
        p = im.document_cache_path(client, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return im.screen_selected_documents(client, selections)


def _sel(cik, i, conf="high", rel=None):
    return {"cik": cik, "accession_number": f"{cik:010d}-00-{i:06d}",
            "filename": f"d{i}.htm", "relative_path": rel or f"/a/{cik}/{i}/d{i}.htm",
            "selection_confidence": conf}


def test_p5_warns_on_an_image_only_exhibit(tmp_path):
    s = _sel(1, 1)
    probs, _ = _screen_run(tmp_path, {s["relative_path"]: "<html><img src='a.jpg'>x</html>"}, [s])
    assert len(probs) == 1 and probs[0].check == "ex99_thin_exhibit"
    assert "IMAGE-ONLY" in probs[0].message
    assert "Under the 100-character floor" in probs[0].message


def test_p5_warns_on_an_empty_at_source_exhibit(tmp_path):
    s = _sel(1, 1)
    probs, _ = _screen_run(tmp_path, {s["relative_path"]: "<html><p>&nbsp;</p></html>"}, [s])
    assert "EMPTY AT SOURCE" in probs[0].message


def test_p5_is_silent_on_a_normal_release(tmp_path):
    s = _sel(1, 1)
    body = "<html>" + ("Acme today reported record quarterly results. " * 80) + "</html>"
    probs, _ = _screen_run(tmp_path, {s["relative_path"]: body}, [s])
    assert probs == []


def test_p5_does_not_lower_f3s_floor():
    """The ruling forbids threshold loosening; P5 exists so these rows are
    NAMED, not so a later pass can argue the floor down."""
    assert im.THIN_EXHIBIT_CHARS == 1500 and im.EMPTY_EXHIBIT_CHARS == 100


# -- P6: the Prologis detector -----------------------------------------


SUPPLEMENTAL = "<html>Prologis Supplemental Information Second Quarter 2018 Unaudited " \
               "Table of Contents Highlights Company Profile Company Performance</html>"
# The release marker must sit in the BODY, past TITLE_REGION_CHARS -- a real
# release's dateline and webcast block do, and the P6 scope fix (2026-08-24)
# deliberately ignores markers inside a document's own leading title region.
RELEASE = ("<html>Prologis Reports Third Quarter Results " + ("filler " * 40) +
           "SAN FRANCISCO -- Prologis, Inc. today reported results for the "
           "quarter. Webcast &amp; conference call information follows.</html>")


def test_p6_flags_a_filer_whose_high_confidence_picks_mostly_lack_release_language(tmp_path):
    """THE ACCEPTANCE TEST. Prologis-before-fix: high-confidence picks that are
    the Supplemental package. No confidence-based trigger could ever catch
    this -- 37 of its 45 wrong picks were HIGH."""
    sels = [_sel(PLD_CIK, i) for i in range(10)]
    docs = {s["relative_path"]: SUPPLEMENTAL for s in sels[:9]}
    docs[sels[9]["relative_path"]] = RELEASE
    _, by_cik = _screen_run(tmp_path, docs, sels)
    assert by_cik[PLD_CIK]["measured"] == 10
    assert by_cik[PLD_CIK]["missing_release"] == 9
    assert by_cik[PLD_CIK]["flag"] is True


def test_p6_does_not_flag_the_fixed_corpus(tmp_path):
    """Prologis-after-fix: the picks are the real releases, so the detector
    goes quiet. A detector that still fired would be useless."""
    sels = [_sel(PLD_CIK, i) for i in range(10)]
    _, by_cik = _screen_run(tmp_path, {s["relative_path"]: RELEASE for s in sels}, sels)
    assert by_cik[PLD_CIK]["missing_release"] == 0
    assert by_cik[PLD_CIK]["flag"] is False


def test_p6_does_not_flag_a_normal_filer(tmp_path):
    """CAT: ordinary press releases, must stay silent."""
    sels = [_sel(CAT_CIK, i) for i in range(8)]
    docs = {s["relative_path"]: RELEASE for s in sels}
    docs[sels[0]["relative_path"]] = SUPPLEMENTAL   # one odd one out is fine
    _, by_cik = _screen_run(tmp_path, docs, sels)
    assert by_cik[CAT_CIK]["flag"] is False


def test_p6_ignores_low_confidence_selections(tmp_path):
    sels = [_sel(7, i, conf="low") for i in range(10)]
    _, by_cik = _screen_run(tmp_path, {s["relative_path"]: SUPPLEMENTAL for s in sels}, sels)
    assert by_cik[7]["measured"] == 0 and by_cik[7]["flag"] is False


def test_p6_needs_a_minimum_number_of_measured_selections(tmp_path):
    """One thin selection must not condemn a filer."""
    sels = [_sel(8, i) for i in range(im.P6_MIN_MEASURED_SELECTIONS - 1)]
    _, by_cik = _screen_run(tmp_path, {s["relative_path"]: SUPPLEMENTAL for s in sels}, sels)
    assert by_cik[8]["flag"] is False


def test_p6_counts_uncached_selections_as_unmeasured_not_clean(tmp_path):
    """Before `--stage documents` most selections have no cached document. A
    screen that reported them clean would be worse than no screen."""
    sels = [_sel(9, i) for i in range(5)]
    _, by_cik = _screen_run(tmp_path, {}, sels)
    assert by_cik[9]["uncached"] == 5
    assert by_cik[9]["measured"] == 0 and by_cik[9]["flag"] is False


def test_p6_screen_makes_zero_network_requests(tmp_path):
    client = FakeClient({}, cache_dir=tmp_path / "raw")
    im.screen_selected_documents(client, [_sel(1, 1), _sel(1, 2)])
    assert client.document_calls == [] and client.request_count == 0


def test_p6_problems_name_the_cik_and_the_share(tmp_path):
    by_cik = {PLD_CIK: {"measured": 43, "missing_release": 37, "uncached": 0, "flag": True}}
    universe = pd.DataFrame([_universe_row(PLD_CIK, im.CORPUS_WINDOW_START,
                                           im.CORPUS_WINDOW_END, name="Prologis, Inc.")])
    probs = im.release_language_problems(by_cik, universe)
    assert len(probs) == 1 and probs[0].severity == "WARN"
    assert probs[0].check == "ex99_release_language_missing"
    assert "37 of 43" in probs[0].message and "86%" in probs[0].message


def test_p6_results_land_in_the_audit_csv(monkeypatch, tmp_path):
    audit = im.build_ex99_audit(
        [_selection(PLD_CIK, "EX99_PRESS_RELEASE", "high", "2019-10-15")],
        pd.DataFrame([_universe_row(PLD_CIK, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END)]),
        e1_ciks=set(),
        release_language_by_cik={PLD_CIK: {"measured": 43, "missing_release": 37,
                                           "uncached": 0, "flag": True}},
    )
    assert list(audit.columns) == list(im.EX99_AUDIT_COLUMNS)
    row = audit.iloc[0]
    assert row["n_release_language_measured"] == 43
    assert row["n_release_language_missing"] == 37
    assert bool(row["release_language_flag"]) is True


# -- Zero drift between the policy and the stored corpus ---------------


def test_stored_selections_match_current_policy_exactly():
    """STANDING TRIPWIRE: replaying the current selection policy over every
    cached earnings-8-K index must reproduce the stored DB selections exactly.
    Any difference means the code and the corpus have silently diverged --
    either the policy changed without a re-run of segment 1, or the DB was
    written by a policy that is no longer in the tree. Both are the kind of
    drift that makes every downstream number un-attributable.

    HISTORY (2026-08-24, why this test is not what it was): it originally
    pinned the fix package's MIGRATION DELTA -- "replaying must move exactly
    45 picks across 5 filers" -- which was true only against the pre-fix
    attempt-2 database. Segment 1 attempts 3+4 regenerated the stored
    selections under the fixed policy, so the delta is now correctly {} and
    the old premise is stale. It was re-pointed at the ENDURING invariant
    rather than deleted or reconstructed against a pre-fix DB.

    The historical 45-change measurement is preserved as the record it is:
    F2_SPEC.md amendments A6/A7 carry the numbers, and each pre-override
    defect is pinned individually against a cached fixture by
    test_prologis_*, test_nvidia_override_*, test_oneok_override_*,
    test_micron_override_* and test_att_override_* above -- those assert both
    the defect AND the corrected pick, so the regressions stay guarded
    without depending on a database snapshot that no longer exists.

    Cache-dependent (both inputs are gitignored and regenerable), so it skips
    rather than fails when they are absent. Zero network by construction --
    it only reads files that already exist.
    """
    idx_dir = REPO_ROOT / "data" / "raw" / "filing_index"
    db = REPO_ROOT / "data" / "filings_metadata_e2.db"
    if not idx_dir.exists() or not db.exists():
        pytest.skip("cached filing indices / E2 DB not present (regenerable)")

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT cik, accession_number, filing_date, primary_document, "
        "earnings_doc_filename, earnings_doc_selection_confidence "
        "FROM filings WHERE has_earnings_item=1"
    ).fetchall()
    conn.close()
    if len(rows) < 10_000:
        pytest.skip(f"E2 DB holds {len(rows)} earnings 8-Ks; expected the full corpus")

    overrides = im.load_earnings_doc_overrides()
    changed_by_cik: dict[int, int] = {}
    confidence_mismatches: list[tuple] = []
    missing_index = 0
    for cik, accession, filing_date, primary, stored_file, stored_conf in rows:
        path = idx_dir / f"{cik}_{accession.replace('-', '')}.html"
        if not path.exists():
            missing_index += 1
            continue
        docs = im.parse_index_html_documents(path.read_text(), primary_document=primary)
        override = overrides.get(accession)
        if override is not None:
            selection = im.apply_earnings_doc_override(override, docs)
        else:
            selection = im.select_earnings_document(
                docs, primary, cik=cik, filing_date=filing_date,
                accession_number=accession, subject=f"CIK {cik}",
            )
        replayed_file = selection["filename"] if selection else None
        if replayed_file != stored_file:
            changed_by_cik[cik] = changed_by_cik.get(cik, 0) + 1
        # An evidenced `exclude` stores NULL in both columns (the DB taxonomy
        # never carries EXCLUDED_BY_OVERRIDE -- P4 was ruled out), while the
        # replay represents it as "no selection". Compare them on that basis
        # rather than letting a NULL-vs-string mismatch pass unnoticed.
        replayed_conf = selection["selection_confidence"] if selection else None
        if replayed_conf != stored_conf:
            confidence_mismatches.append((cik, accession, stored_conf, replayed_conf))

    assert changed_by_cik == {}, (
        f"policy/corpus DRIFT: {sum(changed_by_cik.values())} stored selection(s) "
        f"across {len(changed_by_cik)} CIK(s) disagree with a replay of the "
        f"current policy: {changed_by_cik}. Either re-run segment 1, or the "
        f"policy changed in a way nobody re-ingested."
    )
    assert confidence_mismatches == []
    assert missing_index == 0, f"{missing_index} earnings 8-K(s) have no cached index"


# =====================================================================
# 2026-08-24 content re-verification: the 2016-04-19 boundary + the P6
# title-region scope fix (F2_PROGRESS §5; S6_ex99_manual_read.md §V.3).
# =====================================================================

PLD_2016_04_19 = "filing_index_CIK0001045609_0001564590-16-016339.html"
P6_TITLE_ONLY = "p6_title_only_prologis_2016-04-19_ex99-1.prefix.htm"
P6_REAL_RELEASE = "p6_real_release_prologis_2019-10-15_ex99-2.htm"


def test_p6_fixtures_come_from_the_cache():
    """Provenance: the release fixture is a byte-identical copy, the title-only
    one a byte-exact PREFIX of a 138 KB cached document (sliced only for repo
    weight). Skips if the gitignored cache was cleared."""
    docs = REPO_ROOT / "data" / "raw" / "documents"
    if not docs.exists():
        pytest.skip("data/raw/ cache not present (gitignored, regenerable)")
    full = docs / "Archives_edgar_data_1045609_000156459019036903_pld-ex992_68.htm"
    if full.exists():
        assert (FIXTURES / P6_REAL_RELEASE).read_bytes() == full.read_bytes()
    src = docs / "Archives_edgar_data_1045609_000156459016016339_pld-ex991_6.htm"
    if src.exists():
        prefix = (FIXTURES / P6_TITLE_ONLY).read_bytes()
        assert src.read_bytes()[:len(prefix)] == prefix


# -- the split-date correction -----------------------------------------


def test_prologis_split_is_the_2016_04_19_boundary():
    assert im.PROLOGIS_SUPPLEMENTAL_SPLIT == date(2016, 4, 19)


def test_prologis_2016_04_19_now_takes_ex99_2():
    """The template-leftover title case: EX-99.1 is titled "Earnings Release
    and Supplemental Information" but contains no release, so the handler
    fires and takes EX-99.2. Blast radius 41 -> 42 of 45."""
    docs = _fixture_docs(PLD_2016_04_19, "pld-8k_20160419.htm")
    sel = im.select_earnings_document(
        docs, "pld-8k_20160419.htm", cik=PLD_CIK, filing_date="2016-04-19")
    assert sel["filename"] == "pld-ex992_7.htm"
    assert sel["selection_confidence"] == "high"


def test_prologis_2016_01_26_still_keeps_ex99_1():
    """The boundary moved by exactly one filing: the three genuinely-combined
    pre-split documents are untouched."""
    docs = _fixture_docs(PLD_2016_04_19, "pld-8k_20160419.htm")
    assert im._prologis_earnings_document(docs, date(2016, 1, 26)) is None
    assert im._prologis_earnings_document(docs, date(2016, 4, 18)) is None
    assert im._prologis_earnings_document(docs, date(2016, 4, 19)) is not None


# -- P6 scope: markers in the title do not count -----------------------


def test_p6_ignores_a_marker_that_is_only_the_documents_own_title():
    """THE ACCEPTANCE CASE. This document's sole release-language hit across
    113,158 characters is its own title, "Prologis Earnings Release and
    Supplemental Information" -- which is why P6 passed it as clean and the
    handler's content-confirmation generalised from the same string."""
    raw = (FIXTURES / P6_TITLE_ONLY).read_text(encoding="utf-8", errors="replace")
    signals = im.screen_selected_document(raw)
    assert signals["has_release_language"] is False
    # ...and the marker really IS present, in the title region -- otherwise
    # this fixture would prove nothing about the scope fix. Reuse the module's
    # own extraction so the test cannot drift from it.
    import html as _html
    import re as _re
    plain = _re.sub(r"\s+", " ", _html.unescape(_re.sub(r"<[^>]+>", " ", raw))).strip()
    assert "earnings release" in plain[:im.TITLE_REGION_CHARS].lower()


def test_p6_still_passes_a_real_release():
    """A confirmed Prologis EX-99.2 ("FOR IMMEDIATE RELEASE / Prologis Reports
    Third Quarter 2019 ... SAN FRANCISCO (October 15, 2019)") must stay clean:
    its body carries markers well past the title region."""
    signals = im.screen_selected_document(
        (FIXTURES / P6_REAL_RELEASE).read_text(encoding="utf-8", errors="replace"))
    assert signals["has_release_language"] is True


def test_p6_title_region_is_a_scope_not_a_threshold():
    """The fix narrows WHERE markers count, and does not move the flag
    threshold or the minimum-sample floor."""
    assert im.TITLE_REGION_CHARS == 200
    assert im.P6_MISSING_RELEASE_SHARE == 0.5
    assert im.P6_MIN_MEASURED_SELECTIONS == 4


def test_p6_marker_immediately_after_the_title_region_counts():
    """The boundary is exclusive-of-title only: a marker one character past it
    is body text and counts."""
    body_marker = "x" * im.TITLE_REGION_CHARS + " the company today reported results"
    assert im.screen_selected_document(body_marker)["has_release_language"] is True
    title_marker = "today reported " + "x" * 400
    assert im.screen_selected_document(title_marker)["has_release_language"] is False


def test_p6_flags_a_filer_whose_picks_only_self_describe(tmp_path):
    """End-to-end through the screen: ten title-only documents flag the CIK,
    which is what the pre-fix screen could not do."""
    raw = (FIXTURES / P6_TITLE_ONLY).read_text(encoding="utf-8", errors="replace")
    sels = [_sel(PLD_CIK, i) for i in range(10)]
    _, by_cik = _screen_run(tmp_path, {s["relative_path"]: raw for s in sels}, sels)
    assert by_cik[PLD_CIK]["missing_release"] == 10
    assert by_cik[PLD_CIK]["flag"] is True


# =====================================================================
# S7 red-team B1/B6/B7/B17 (ruled 2026-08-24): the conditional 8K_BODY
# fallback and the malformed-exhibit candidate screen.
# =====================================================================

AON = "filing_index_CIK0000315293_0001628280-15-005672.html"        # EX-99..1
ILLUMINA = "filing_index_CIK0001110803_0001110803-16-000185.html"   # EX-1
HPE = "filing_index_CIK0001645590_0001645590-17-000006.html"        # EX-1 / EX-2
MPC = "filing_index_CIK0001510295_0001510295-26-000029.html"        # EX-10.1 (not a release)


def test_b1_fixtures_come_from_the_cache():
    cache = REPO_ROOT / "data" / "raw" / "filing_index"
    if not cache.exists():
        pytest.skip("data/raw/ cache not present (gitignored, regenerable)")
    for fixture, cached in {
        AON: "315293_000162828015005672.html",
        ILLUMINA: "1110803_000111080316000185.html",
        HPE: "1645590_000164559017000006.html",
        MPC: "1510295_000151029526000029.html",
    }.items():
        if (cache / cached).exists():
            assert (FIXTURES / fixture).read_bytes() == (cache / cached).read_bytes()


def _assert_pre_fix_defect_conditions(docs):
    """The old code's precondition: nothing matches the EX-99 family, so the
    unconditional fallback fired and returned ("8K_BODY", "high")."""
    assert not [d for d in docs
                if im._EX99_FAMILY_RE.match(im._canonical_exhibit_type(d["doc_type"]))]


# -- B1: a confirmable candidate is selected --------------------------


def test_aon_cover_page_defect_is_fixed_by_the_candidate_screen():
    """PRE-FIX: no EX-99-family row, so the body -- the SEC Form 8-K cover
    page, 2,260 chars, whose own Item 2.02 reads "A copy of the Press Release
    is attached hereto as Exhibit 99.1" -- was stored at HIGH confidence.
    POST-FIX: the EX-99..1 row is confirmable from its description."""
    docs = _fixture_docs(AON, "form8-kpressreleaseq22015.htm")
    _assert_pre_fix_defect_conditions(docs)
    sel = im.select_earnings_document(
        docs, "form8-kpressreleaseq22015.htm", cik=315293, filing_date="2015-07-31")
    assert sel["filename"] == "ex991pressreleaseq22015.htm"
    assert sel["section_type"] == "EX99_PRESS_RELEASE"
    # Description evidence, not a canonical type -> medium, never high.
    assert sel["selection_confidence"] == "medium"


# -- B1: an unconfirmable candidate becomes UNRESOLVED ----------------


@pytest.mark.parametrize("fixture,primary,cik,date", [
    (ILLUMINA, "a1q168-k.htm", 1110803, "2016-05-03"),
    (HPE, "hpe-q4fy2017x8k.htm", 1645590, "2017-11-21"),
])
def test_unconfirmable_candidate_is_unresolved_not_a_cover_page(fixture, primary, cik, date):
    """Illumina/HPE describe their release row "EXHIBIT 1"/"EXHIBIT 2" -- no
    self-label as exhibit 99 and no release-shaped description -- so nothing is
    confirmable from the index. The ruled disposition is UNRESOLVED (counted,
    loud), NOT the cover page at high confidence."""
    docs = _fixture_docs(fixture, primary)
    _assert_pre_fix_defect_conditions(docs)
    assert im.earnings_candidate_rows(docs, primary), "the candidate row must be seen"
    assert im.confirmable_release_candidate(im.earnings_candidate_rows(docs, primary)) is None
    assert im.select_earnings_document(docs, primary, cik=cik, filing_date=date) is None


def test_unresolved_fallback_is_counted_against_the_ceiling():
    """It must reach earnings_doc_unresolved -- the old behaviour counted a
    cover-page pick as RESOLVED, which is why 0.00% unresolved was blind."""
    problems = im.earnings_doc_unresolved_problems(
        [{"cik": 1110803, "accession_number": "0001110803-16-000185",
          "reason": "selection policy returned no document"}], 10569)
    assert [p.severity for p in problems] == ["WARN"]
    assert problems[0].check == "earnings_doc_unresolved"


# -- B1: the narrowness guard (genuine exhibit-less 8-Ks unchanged) ---


def test_ordinary_securities_exhibits_are_not_candidates():
    """The screen must not turn every exhibit into a release candidate:
    Marathon's EX-10.1 lease agreements keep the 8K_BODY fallback. Dominion's
    EX-1.1/EX-4.2/EX-5.1, Emerson's EX-2.1 and Danaher's EX-3.1 are the same
    shape -- a sub-numbered securities exhibit, correctly ignored."""
    docs = _fixture_docs(MPC, "mpc-20260407.htm")
    assert im.earnings_candidate_rows(docs, "mpc-20260407.htm") == []
    sel = im.select_earnings_document(
        docs, "mpc-20260407.htm", cik=1510295, filing_date="2026-04-13")
    assert sel["section_type"] == "8K_BODY"
    assert sel["selection_confidence"] == "high"


@pytest.mark.parametrize("doc_type", ["EX-1.1", "EX-2.1", "EX-3.1", "EX-4.2", "EX-10.1", "EX-21.1"])
def test_sub_numbered_exhibits_are_never_candidates(doc_type):
    row = {"seq": 2, "doc_type": doc_type, "description": doc_type,
           "filename": "x.htm", "relative_path": "/a/x.htm", "source_table": "t"}
    assert im.earnings_candidate_rows([row], "body.htm") == []


@pytest.mark.parametrize("doc_type", ["EX-1", "EX-2"])
def test_bare_ex_numbers_are_candidates(doc_type):
    """A bare EX-1 has no sub-number, which is itself the malformation -- the
    Illumina / HPE / Kraft Heinz shape."""
    row = {"seq": 2, "doc_type": doc_type, "description": "EXHIBIT 1",
           "filename": "earningsrelease.htm", "relative_path": "/a/x.htm",
           "source_table": "t"}
    assert im.earnings_candidate_rows([row], "body.htm") == [row]


def test_a_genuine_exhibit_less_8k_keeps_the_body_at_high_confidence():
    docs = [
        {"seq": 1, "doc_type": "8-K", "description": "8-K", "filename": "body.htm",
         "relative_path": "/a/body.htm", "source_table": "t"},
        {"seq": 2, "doc_type": "GRAPHIC", "description": "GRAPHIC", "filename": "l.jpg",
         "relative_path": "/a/l.jpg", "source_table": "t"},
    ]
    sel = im.select_earnings_document(docs, "body.htm", cik=1, filing_date="2020-01-01")
    assert sel["section_type"] == "8K_BODY" and sel["selection_confidence"] == "high"


@pytest.mark.parametrize("description,confirmable", [
    ("EXHIBIT 99..1", True),
    ("EX-99.1", True),
    ("EX-99", True),
    ("EX-99.(A)", True),
    ("EXHIBIT 99.Q120 EARNINGS", True),
    ("PRESS RELEASE", True),
    ("EXHIBIT 1", False),
    ("EX-10.1", False),
    ("", False),
])
def test_confirmable_release_candidate_evidence_routes(description, confirmable):
    row = {"seq": 2, "doc_type": "EX-1", "description": description, "filename": "x.htm",
           "relative_path": "/a/x.htm", "source_table": "t"}
    assert (im.confirmable_release_candidate([row]) is not None) is confirmable


def test_ambiguous_candidates_are_unresolved_never_guessed():
    rows = [
        {"seq": 2, "doc_type": "EX-99..1", "description": "EXHIBIT 99..1", "filename": "a.htm",
         "relative_path": "/a/a.htm", "source_table": "t"},
        {"seq": 3, "doc_type": "EX-99..2", "description": "EXHIBIT 99..2", "filename": "b.htm",
         "relative_path": "/a/b.htm", "source_table": "t"},
    ]
    assert im.confirmable_release_candidate(rows) is None


def test_the_fix_does_not_touch_the_normal_ex99_ladder():
    """Blast radius is confined to the fallback: a well-typed EX-99.1 filing
    resolves exactly as before, at high confidence."""
    docs = _fixture_docs(CAT_INDEX_FIXTURE.name, CAT_PRIMARY_DOCUMENT)
    sel = im.select_earnings_document(docs, CAT_PRIMARY_DOCUMENT, cik=CAT_CIK,
                                      filing_date="2016-10-25")
    assert sel["filename"] == "cat_exx991xq3x2016xearning.htm"
    assert sel["selection_confidence"] == "high"


# -- B6: the ratio for every CIK + the near-threshold watch list ------


def test_audit_carries_the_release_language_share_for_every_cik():
    audit = im.build_ex99_audit(
        [_selection(1, "EX99_PRESS_RELEASE", "high", "2019-01-30"),
         _selection(2, "EX99_PRESS_RELEASE", "high", "2019-01-30")],
        pd.DataFrame([_universe_row(1, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END),
                      _universe_row(2, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END)]),
        e1_ciks=set(),
        release_language_by_cik={
            1: {"measured": 77, "missing_release": 38, "uncached": 0, "flag": False},
            2: {"measured": 47, "missing_release": 25, "uncached": 0, "flag": True},
        },
    )
    assert "release_language_missing_share" in audit.columns
    shares = dict(zip(audit["cik"], audit["release_language_missing_share"]))
    # The UNFLAGGED CIK's share is emitted too -- that is the whole point.
    assert shares[1] == pytest.approx(38 / 77, abs=1e-4)
    assert shares[2] == pytest.approx(25 / 47, abs=1e-4)
    assert dict(zip(audit["cik"], audit["release_language_flag"]))[1] is False


def test_near_threshold_ciks_are_printed_as_a_watch_list(capsys):
    """Pioneer at 38/77 = 49.4% is ONE filing from flagging and is
    independently implicated in B1. A majority test alone hides it."""
    audit = im.build_ex99_audit([_selection(1038357, "EX99_PRESS_RELEASE", "high", "2019-01-30")],
                                pd.DataFrame([_universe_row(1038357, im.CORPUS_WINDOW_START,
                                                            im.CORPUS_WINDOW_END)]),
                                e1_ciks=set())
    im.print_ex99_audit_report(
        audit, [], 100, Path("/tmp/x.csv"),
        release_language_by_cik={1038357: {"measured": 77, "missing_release": 38,
                                           "uncached": 0, "flag": False}})
    out = capsys.readouterr().out
    assert "WATCH LIST" in out and "CIK 1038357" in out and "49.4%" in out


def test_watch_list_does_not_move_the_flag_threshold():
    assert im.P6_MISSING_RELEASE_SHARE == 0.5
    assert im.P6_WATCH_SHARE == 0.40
    assert im.P6_WATCH_SHARE < im.P6_MISSING_RELEASE_SHARE


# -- B7: P3's docstring states the class size, not its own hit count --


def test_p3_docstring_distinguishes_trigger_hits_from_the_defect_class():
    doc = im.press_release_typed_outside_ex99.__doc__
    assert "38 filings" in doc
    assert "not the size of the defect class" in doc


# -- B17: the ratification gate the sibling override files had --------


def test_validation_exceptions_have_a_code_side_ratification_gate():
    assert hasattr(im, "RATIFIED_VALIDATION_EXCEPTIONS")
    assert im.RATIFIED_VALIDATION_EXCEPTIONS == set()   # ships empty, by measurement


def test_unratified_validation_exception_row_is_refused(tmp_path: Path):
    p = tmp_path / "validation_exceptions.csv"
    p.write_text(
        ",".join(im.VALIDATION_EXCEPTION_COLUMNS) + "\n"
        "320193,no_large_filing_gap,a reason,,,,some written evidence here,2026-08-24\n")
    with pytest.raises(ValueError, match="not a ratified exception"):
        im.load_validation_exceptions(p)


def test_ratified_validation_exception_row_loads(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(im, "RATIFIED_VALIDATION_EXCEPTIONS", {(320193, "no_large_filing_gap")})
    p = tmp_path / "validation_exceptions.csv"
    p.write_text(
        ",".join(im.VALIDATION_EXCEPTION_COLUMNS) + "\n"
        "320193,no_large_filing_gap,a reason,,,,some written evidence here,2026-08-24\n")
    assert len(im.load_validation_exceptions(p)) == 1


def test_shipped_exceptions_file_still_loads_empty():
    assert im.load_validation_exceptions() == []


# -- S7 B1 singletons: the four bare-EX-<n> override rows --------------


@pytest.mark.parametrize("accession,fixture,primary,expected", [
    ("0001110803-16-000185", ILLUMINA, "a1q168-k.htm", "a1q16earningsrelease.htm"),
    ("0001637459-19-000050", "filing_index_CIK0001637459_0001637459-19-000050.html",
     "a6719form8-k.htm", "a6719exhibit991.htm"),
])
def test_bare_ex_singleton_overrides_select_the_sole_candidate(
    accession, fixture, primary, expected
):
    """The policy leaves these UNRESOLVED (nothing in the index confirms the
    row) and the ratified per-accession mechanism resolves them -- not a new
    policy route."""
    docs = _fixture_docs(fixture, primary)
    assert im.select_earnings_document(docs, primary) is None      # still loud by policy
    ov = im.load_earnings_doc_overrides()[accession]
    fixed = im.apply_earnings_doc_override(ov, docs)
    assert fixed["filename"] == expected
    assert fixed["section_type"] == "EX99_PRESS_RELEASE"
    assert fixed["selection_confidence"] == "high"


def test_hpe_override_takes_exhibit_99_1_not_the_ceo_announcement():
    """HPE is the one filing here with TWO unselected candidates, and S7 B1's
    own table named the WRONG one. Its cover page maps them explicitly:
    Item 2.02 attaches the segment-results release as Exhibit 99.1
    (`ex-991x10312017x8k.htm`), while Item 5.02 furnishes the Antonio Neri
    CEO-appointment release as Exhibit 99.2 (`pressrelease112117.htm`).
    Selecting the Item 5.02 document would store a management announcement as
    the earnings text."""
    docs = _fixture_docs(HPE, "hpe-q4fy2017x8k.htm")
    assert len(im.earnings_candidate_rows(docs, "hpe-q4fy2017x8k.htm")) == 2
    ov = im.load_earnings_doc_overrides()["0001645590-17-000006"]
    fixed = im.apply_earnings_doc_override(ov, docs)
    assert fixed["filename"] == "ex-991x10312017x8k.htm"
    assert fixed["filename"] != "pressrelease112117.htm"


def test_every_select_document_override_names_a_row_in_its_own_index():
    """A stale override must fail loudly, so pin that all seven resolve against
    their real cached indices."""
    cache = REPO_ROOT / "data" / "raw" / "filing_index"
    if not cache.exists():
        pytest.skip("data/raw/ cache not present (gitignored, regenerable)")
    conn = sqlite3.connect(f"file:{REPO_ROOT / 'data' / 'filings_metadata_e2.db'}?mode=ro", uri=True)
    resolved = 0
    for accession, ov in im.load_earnings_doc_overrides().items():
        if ov.excludes:
            continue
        row = conn.execute(
            "SELECT cik, primary_document FROM filings WHERE accession_number=?", (accession,)
        ).fetchone()
        if row is None:
            continue
        path = cache / f"{row[0]}_{accession.replace('-', '')}.html"
        if not path.exists():
            continue
        docs = im.parse_index_html_documents(path.read_text(), primary_document=row[1])
        assert im.apply_earnings_doc_override(ov, docs) is not None, accession
        resolved += 1
    conn.close()
    assert resolved == 7


def test_future_instances_of_the_bare_ex_shape_stay_loud_unresolved():
    """The mechanism absorbs the four measured singletons; it is NOT a policy
    change. An unseen filing of the same shape must still go UNRESOLVED."""
    docs = [
        {"seq": 1, "doc_type": "8-K", "description": "8-K", "filename": "body.htm",
         "relative_path": "/a/body.htm", "source_table": "t"},
        {"seq": 2, "doc_type": "EX-1", "description": "EXHIBIT 1",
         "filename": "someearningsrelease.htm", "relative_path": "/a/x.htm",
         "source_table": "t"},
    ]
    assert im.select_earnings_document(docs, "body.htm", cik=999, filing_date="2024-01-01") is None


def test_pioneer_slide_deck_is_excluded_not_relabelled_as_a_release():
    """S6 manual read section W.3: the candidate screen RESOLVES this filing
    (its sole row is described "EX-99.1(A)", which self-labels as exhibit
    99.1), and in doing so made it LESS honest -- pre-fix it claimed 8K_BODY,
    true of a cover page; post-fix it claimed EX99_PRESS_RELEASE, false of an
    IPAA conference slide deck. Not a mis-pick (there is no better candidate);
    a mis-label, resolved by the same `exclude` mechanism as AT&T."""
    docs = _fixture_docs(PLD_PIONEER_DECK, "d564737d8k.htm")
    # The screen still resolves it -- the exclusion is a human ruling on top,
    # not a policy change, so this must keep working.
    policy = im.select_earnings_document(
        docs, "d564737d8k.htm", cik=1038357, filing_date="2018-04-09")
    assert policy["filename"] == "d564737dex991a.htm"
    assert policy["selection_confidence"] == "medium"

    ov = im.load_earnings_doc_overrides()["0001193125-18-111008"]
    assert ov.excludes is True
    assert im.apply_earnings_doc_override(ov, docs) is None


def test_pioneer_exclusion_evidence_quotes_the_item_2_02_wrapper():
    ov = im.load_earnings_doc_overrides()["0001193125-18-111008"]
    assert "IF ANY" in ov.evidence                      # the conditional wrapper
    assert "Investor Presentation" in ov.evidence
    assert "IPAA Oil & Gas Investment Symposium" in ov.evidence
    assert "7.01" in ov.evidence                        # the substantive item


def test_both_exclusions_are_counted_in_the_audit_not_dropped():
    """Two `exclude` rows now -- both must surface as EXCLUDED_BY_OVERRIDE
    audit rows and INFO problems, never as silent NULLs."""
    exclusions = [
        {"cik": 732717, "accession_number": "0000732717-19-000048",
         "filing_date": "2019-10-28", "reason": "no release present."},
        {"cik": 1038357, "accession_number": "0001193125-18-111008",
         "filing_date": "2018-04-09", "reason": "IPAA slide deck."},
    ]
    problems = im.earnings_doc_excluded_problems(exclusions)
    assert len(problems) == 2
    assert {p.severity for p in problems} == {"INFO"}
    assert {p.check for p in problems} == {"earnings_doc_excluded_by_override"}
    audit = im.build_ex99_audit(
        [{"cik": e["cik"], "section_type": im.EXCLUDED_SECTION_TYPE,
          "selection_confidence": "override", "filing_date": e["filing_date"]}
         for e in exclusions],
        pd.DataFrame([_universe_row(732717, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END),
                      _universe_row(1038357, im.CORPUS_WINDOW_START, im.CORPUS_WINDOW_END)]),
        e1_ciks=set())
    assert len(audit[audit["section_type"] == im.EXCLUDED_SECTION_TYPE]) == 2


def test_an_exclusion_never_counts_against_the_unresolved_ceiling():
    """An evidenced human ruling that no release exists is not the policy
    failing to resolve one -- keeping them apart is what stops two exclusions
    from eating into the 1% FATAL budget."""
    assert im.earnings_doc_unresolved_problems([], 10569) == []


# =====================================================================
# S6 §W ADDENDUM (ruled 2026-08-24): the PSEG handler, the deck-title
# screen, and the two-candidate-shape census.
# =====================================================================

PSEG_INDEX = "filing_index_CIK0000788784_0001193125-15-272287.html"
DECK_POSITIVE = "deck_screen_positive_pseg_2015-07-31_ex99-1.prefix.htm"
DECK_NEGATIVE = "deck_screen_negative_danaher_2020-04-13_release.htm"


def test_pseg_fixtures_come_from_the_cache():
    cache = REPO_ROOT / "data" / "raw"
    if not cache.exists():
        pytest.skip("data/raw/ cache not present (gitignored, regenerable)")
    idx = cache / "filing_index" / "788784_000119312515272287.html"
    if idx.exists():
        assert (FIXTURES / PSEG_INDEX).read_bytes() == idx.read_bytes()
    deck = cache / "documents" / "Archives_edgar_data_81033_000119312515272287_d17140dex991.htm"
    if deck.exists():
        prefix = (FIXTURES / DECK_POSITIVE).read_bytes()
        assert deck.read_bytes()[:len(prefix)] == prefix
    dan = cache / "documents" / "Archives_edgar_data_313616_000031361620000081_dhr-2020413xex991.htm"
    if dan.exists():
        assert (FIXTURES / DECK_NEGATIVE).read_bytes() == dan.read_bytes()


# -- 1. the PSEG per-filer handler -------------------------------------


def test_pseg_takes_the_bare_ex99_not_the_deck():
    """PRE-FIX: the ladder prefers the sub-numbered EX-99.1 over the bare
    EX-99, and `_best_by_description()` cannot break the tie because both
    descriptions are content-free ("EX-99" / "EX-99.1"). All 45 selections
    were the earnings CALL DECK, at high confidence."""
    docs = _fixture_docs(PSEG_INDEX, "d17140d8k.htm")
    types = {im._canonical_exhibit_type(d["doc_type"]) for d in docs}
    assert {"EX-99", "EX-99.1"} <= types          # the two-candidate shape
    sel = im.select_earnings_document(
        docs, "d17140d8k.htm", cik=im.PSEG_CIK, filing_date="2015-07-31")
    assert sel["filename"] == "d17140dex99.htm"   # the bare EX-99 = the release
    assert sel["filename"] != "d17140dex991.htm"  # NOT the deck
    assert sel["selection_confidence"] == "high"


def test_pseg_handler_is_scoped_to_pseg_only():
    """The same shape under a different CIK keeps the ordinary ladder pick --
    a blanket bare-before-sub-numbered flip was explicitly ruled out."""
    docs = _fixture_docs(PSEG_INDEX, "d17140d8k.htm")
    sel = im.select_earnings_document(
        docs, "d17140d8k.htm", cik=CAT_CIK, filing_date="2015-07-31")
    assert sel["filename"] == "d17140dex991.htm"
    assert im.PER_FILER_EARNINGS_HANDLERS.keys() == {im.PROLOGIS_CIK, im.PSEG_CIK}


def test_pseg_handler_declines_when_the_shape_is_absent():
    """It fires on the measured two-candidate shape only; anything else falls
    through to the ordinary ladder rather than inventing a pick."""
    docs = [d for d in _fixture_docs(PSEG_INDEX) if d["filename"] != "d17140dex99.htm"]
    assert im._pseg_earnings_document(docs, date(2015, 7, 31)) is None


def test_no_blanket_bare_before_subnumbered_preference():
    """ConocoPhillips `0001157523-17-001334` has the same shape and its ladder
    pick is CORRECT (its bare EX-99, described "EXHIBIT 99.1", really is the
    release: "ConocoPhillips Reports First-Quarter 2017 Results"). A global
    preference flip would be a gamble on ~10,500 correct picks to fix 45."""
    docs = [
        {"seq": 2, "doc_type": "EX-99", "description": "EXHIBIT 99.1",
         "filename": "ex99_1.htm", "relative_path": "/a/1.htm", "source_table": "t"},
        {"seq": 3, "doc_type": "EX-99.2", "description": "EXHIBIT 99.2",
         "filename": "ex99_2.htm", "relative_path": "/a/2.htm", "source_table": "t"},
    ]
    sel = im.select_earnings_document(docs, "body.htm", cik=1163165,
                                      filing_date="2017-05-02")
    assert sel["filename"] == "ex99_1.htm"


# -- 2. the deck-title screen ------------------------------------------


def test_deck_screen_flags_a_conference_call_deck():
    signals = im.screen_selected_document(
        (FIXTURES / DECK_POSITIVE).read_text(encoding="utf-8", errors="replace"))
    assert signals["deck_shaped"] is True
    # Independent of P6: this deck has NO release language, but the screen must
    # not depend on that either way.
    assert signals["has_release_language"] is False


def test_deck_screen_does_not_flag_a_release_that_merely_schedules_the_call():
    """THE measured false positive the corroboration requirement exists for:
    Danaher's genuine release is headlined "... AND SCHEDULES FIRST QUARTER
    EARNINGS CONFERENCE CALL". Title marker alone flags it; title + the deck's
    own boilerplate does not."""
    raw = (FIXTURES / DECK_NEGATIVE).read_text(encoding="utf-8", errors="replace")
    signals = im.screen_selected_document(raw)
    assert signals["deck_shaped"] is False
    import html as _html
    import re as _re
    plain = _re.sub(r"\s+", " ", _html.unescape(_re.sub(r"<[^>]+>", " ", raw))).strip()
    assert any(m in plain[:im.TITLE_REGION_CHARS].lower() for m in im.DECK_TITLE_MARKERS)


def test_deck_screen_requires_the_title_region_not_just_any_mention():
    body_only = "Acme Reports Q1 Results. " * 20 + " earnings conference call forward-looking statement"
    assert im.screen_selected_document(body_only)["deck_shaped"] is False


def test_deck_markers_exclude_the_generic_conference_call_phrase():
    """MEASURED and rejected: bare "conference call" hits 93 selections across
    11 CIKs, including Texas Instruments 45 and Nike 12 whose releases simply
    name the call in the header."""
    assert "conference call" not in im.DECK_TITLE_MARKERS
    assert im.DECK_TITLE_MARKERS == (
        "earnings conference call",
        "financial results presentation",
        "financial results and conference call",
    )


def test_deck_flag_needs_no_majority_and_no_minimum_sample(tmp_path):
    """Unlike P6 there is no share at which a deck-as-press-release is
    acceptable, so ONE is enough to flag."""
    deck = (FIXTURES / DECK_POSITIVE).read_text(encoding="utf-8", errors="replace")
    release = (FIXTURES / DECK_NEGATIVE).read_text(encoding="utf-8", errors="replace")
    sels = [_sel(5, i) for i in range(6)]
    docs = {s["relative_path"]: release for s in sels}
    docs[sels[0]["relative_path"]] = deck
    _, by_cik = _screen_run(tmp_path, docs, sels)
    assert by_cik[5]["deck_shaped"] == 1
    assert by_cik[5]["deck_flag"] is True


def test_deck_screen_is_silent_on_a_filer_with_no_decks(tmp_path):
    release = (FIXTURES / DECK_NEGATIVE).read_text(encoding="utf-8", errors="replace")
    sels = [_sel(6, i) for i in range(5)]
    _, by_cik = _screen_run(tmp_path, {s["relative_path"]: release for s in sels}, sels)
    assert by_cik[6]["deck_shaped"] == 0 and by_cik[6]["deck_flag"] is False


def test_deck_problems_name_the_cik_and_the_count():
    by_cik = {im.PSEG_CIK: {"measured": 45, "missing_release": 21, "uncached": 0,
                            "flag": False, "seen": 45, "deck_shaped": 45,
                            "deck_flag": True}}
    universe = pd.DataFrame([_universe_row(im.PSEG_CIK, im.CORPUS_WINDOW_START,
                                           im.CORPUS_WINDOW_END, name="PSEG")])
    probs = im.deck_shaped_problems(by_cik, universe)
    assert len(probs) == 1 and probs[0].severity == "WARN"
    assert probs[0].check == "ex99_deck_shaped_selection"
    assert "45 of 45" in probs[0].message


def test_deck_screen_is_independent_of_p6():
    """PSEG scored 21/45 release-language-missing and sat UNDER the P6 bar while
    its true defect rate was 45/45 -- the 24 "passers" passed on a contact
    slide's "investor relations". The deck screen must not be gated on P6."""
    by_cik = {im.PSEG_CIK: {"measured": 45, "missing_release": 21, "uncached": 0,
                            "flag": False,          # P6 did NOT flag
                            "seen": 45, "deck_shaped": 45, "deck_flag": True}}
    universe = pd.DataFrame([_universe_row(im.PSEG_CIK, im.CORPUS_WINDOW_START,
                                           im.CORPUS_WINDOW_END, name="PSEG")])
    assert im.release_language_problems(by_cik, universe) == []   # P6 silent
    assert len(im.deck_shaped_problems(by_cik, universe)) == 1    # deck screen loud


def test_audit_carries_the_deck_columns():
    audit = im.build_ex99_audit(
        [_selection(im.PSEG_CIK, "EX99_PRESS_RELEASE", "high", "2015-07-31")],
        pd.DataFrame([_universe_row(im.PSEG_CIK, im.CORPUS_WINDOW_START,
                                    im.CORPUS_WINDOW_END)]),
        e1_ciks=set(),
        release_language_by_cik={im.PSEG_CIK: {"measured": 45, "missing_release": 21,
                                               "uncached": 0, "flag": False, "seen": 45,
                                               "deck_shaped": 45, "deck_flag": True}})
    assert "n_deck_shaped" in audit.columns and "deck_shaped_flag" in audit.columns
    assert audit.iloc[0]["n_deck_shaped"] == 45
    assert bool(audit.iloc[0]["deck_shaped_flag"]) is True
