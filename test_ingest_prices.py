"""
test_ingest_prices.py -- tests for ingest_prices.py: E2's CIK-verified ticker
resolution, the evidenced override file, census reconciliation, and the
coverage/return validation logic (F2 stage S5, `data/f2/F2_SPEC.md` §6 + §8.2).

HARD CONSTRAINT: no network calls anywhere in this file. Every EDGAR-shaped
input is either a synthetic dict built in-memory or read from the local
`data/raw/` cache through a client stub that RAISES on a cache miss -- there is
no request path in this file at all. Tests that need the real cache SKIP loudly
when it is absent (`data/raw/` is gitignored) rather than fetching it.

Run with: python3 -m pytest test_ingest_prices.py -v
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

import ingest_prices as ip

REPO_ROOT = Path(__file__).resolve().parent
RAW_DIR = REPO_ROOT / "data" / "raw"


# ---------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------


def _business_days(start: date, n: int) -> list[date]:
    """n consecutive Mon-Fri calendar dates starting at `start` (which must
    itself be a Monday) -- a simple stand-in trading calendar for tests.
    """
    days = []
    d = start
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def _res(
    cik: int,
    ticker: str | None = None,
    *,
    status: str = "resolved",
    stratum: str = "core",
    name: str | None = None,
    coverage_start: date | None = None,
    coverage_end: date | None = None,
    is_current_member: bool = True,
) -> ip.TickerResolution:
    return ip.TickerResolution(
        cik=cik,
        name=name or f"Company {cik}",
        stratum=stratum,
        chosen_ticker=ticker,
        all_candidates=ticker or "",
        status=status,
        reason="test fixture",
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        is_current_member=is_current_member,
    )


def _make_prices_df(resolutions, calendar_days, close=100.0) -> pd.DataFrame:
    rows = []
    for r in resolutions:
        for d in calendar_days:
            rows.append(
                {
                    "cik": r.cik,
                    "ticker": r.chosen_ticker,
                    "date": d,
                    "open": close,
                    "high": close + 1,
                    "low": close - 1,
                    "close": close,
                    "volume": 1_000_000,
                    "source": "yahoo_finance_chart",
                    "fetched_at": "2026-08-24T00:00:00+00:00",
                }
            )
    return pd.DataFrame(rows, columns=ip.PARQUET_COLUMNS)


def _subs(tickers) -> dict:
    return {"tickers": list(tickers)}


class _CacheOnlyEdgar:
    """EdgarClient stand-in that only ever reads `data/raw/`. A cache miss
    RAISES instead of fetching, so no test can silently open a socket.
    """

    def __init__(self, raw_dir: Path = RAW_DIR):
        self.raw_dir = raw_dir

    def get_submissions(self, cik: int, force: bool = False) -> dict:
        path = self.raw_dir / "submissions" / f"CIK{cik:010d}.json"
        if not path.exists():
            raise RuntimeError(f"cache miss (a real client would GET): {path}")
        return json.loads(path.read_text())

    def get_company_tickers(self, force: bool = False) -> dict:
        path = self.raw_dir / "company_tickers.json"
        if not path.exists():
            raise RuntimeError(f"cache miss (a real client would GET): {path}")
        return json.loads(path.read_text())


class _StubEdgar:
    """Fully synthetic submissions + bulk map, for the rule's own tests."""

    def __init__(self, submissions: dict[int, dict], bulk: dict[str, int]):
        self.submissions = submissions
        self.bulk = bulk

    def get_submissions(self, cik: int, force: bool = False) -> dict:
        return self.submissions[cik]

    def get_company_tickers(self, force: bool = False) -> dict:
        return {
            str(i): {"ticker": t, "cik_str": c, "title": f"Company {c}"}
            for i, (t, c) in enumerate(self.bulk.items())
        }


def _universe(rows) -> pd.DataFrame:
    """rows: iterable of (cik, name, stratum)."""
    return pd.DataFrame(
        [
            {
                "cik": cik,
                "name": name,
                "sector": "tech",
                "stratum": stratum,
                "coverage_start": date(2015, 7, 1),
                "coverage_end": date(2026, 8, 31),
                "is_current_member": True,
            }
            for cik, name, stratum in rows
        ]
    )


# =====================================================================
# S5 -- the ticker rule (F2_SPEC §6.1)
# =====================================================================


def test_preferreds_only_is_censored():
    """EIDP's real shape: only CTA-PA / CTA-PB remain listed."""
    chosen, status, reason = ip.resolve_ticker(_subs(["CTA-PB", "CTA-PA"]), 30554, {})
    assert chosen is None
    assert status == "censored"
    assert "CTA-PB" in reason  # named, never silent


@pytest.mark.parametrize(
    "suffixed",
    ["ACME-P", "ACME-PA", "ACME-WT", "ACME-WTA", "ACME-RI", "ACME-U", "ACME-W"],
)
def test_every_non_common_suffix_is_dropped(suffixed):
    chosen, status, _ = ip.resolve_ticker(_subs([suffixed]), 1, {})
    assert (chosen, status) == (None, "censored")


def test_share_class_dashes_are_kept_and_edgar_ordering_wins():
    """`-A`/`-B` are share classes, not preferreds -- this is what lets
    Berkshire resolve to BRK-B, and Yahoo uses the same dash convention."""
    chosen, status, _ = ip.resolve_ticker(_subs(["BRK-B", "BRK-A"]), 1067983, {})
    assert (chosen, status) == ("BRK-B", "resolved")


def test_bulk_map_contradiction_censors():
    chosen, status, reason = ip.resolve_ticker(_subs(["APC"]), 773910, {"APC": 2080921})
    assert chosen is None
    assert status == "censored"
    assert "2080921" in reason


def test_bulk_map_absence_still_resolves():
    """MEASURED: EA (712515) is absent from the cached company_tickers.json
    (AEP was too, before the 2026-08-24 refresh). Requiring presence would
    censor a live large cap for an SEC file's gap -- the bulk map is a
    contradiction detector only."""
    chosen, status, reason = ip.resolve_ticker(_subs(["EA"]), 712515, {"MSFT": 789019})
    assert (chosen, status) == ("EA", "resolved")
    assert "absence never censors" in reason


def test_dead_member_former_symbol_is_never_fetched():
    """The F1 trap, directly: APC -> ARKO (CIK 2080921) and EMC -> nothing.
    EDGAR clears a dead registrant's tickers[], so the rule censors both --
    and the reassigned symbol is never reachable, because candidates only ever
    come from the member's own submissions.
    """
    bulk = {"APC": 2080921, "ARKO": 1823794}  # EMC is absent from the real map too
    universe = _universe([(773910, "ANADARKO PETROLEUM CORP", "core"), (790070, "EMC CORP", "core")])
    client = _StubEdgar({773910: _subs([]), 790070: _subs([])}, bulk)
    res = ip.resolve_universe_tickers(client, universe, overrides={}, bulk_map=bulk)

    assert [r.status for r in res] == ["censored", "censored"]
    assert all(r.chosen_ticker is None for r in res)
    assert [r.chosen_ticker for r in res if r.fetchable] == []


def test_deliberately_censored_cik_is_never_mapped_even_if_edgar_publishes_a_ticker():
    """CIK 29915 (Dow Chemical) must never become today's DOW (Dow Inc, CIK
    1751788, a 2019 spin-off). Belt and braces: even a ticker appearing in its
    own submissions does not resolve it."""
    universe = _universe([(29915, "DOW CHEMICAL CO /DE/", "extension")])
    client = _StubEdgar({29915: _subs(["DOW"])}, {"DOW": 29915})
    (res,) = ip.resolve_universe_tickers(client, universe, overrides={}, bulk_map={"DOW": 29915})
    assert res.status == "censored"
    assert res.chosen_ticker is None
    assert "1751788" in res.reason


# =====================================================================
# S5 -- the override file (F2_SPEC §6.2)
# =====================================================================


def test_shipped_override_file_holds_exactly_the_two_ratified_rows():
    """34088 -> XOM (successor-CIK reorganisation) and 4904 -> AEP (the
    2026-08-24 upstream wobble, ruled by the main session). Both evidenced,
    both ratified in code, nothing else."""
    overrides = ip.load_ticker_overrides()
    assert sorted(overrides) == [4904, 34088]
    assert overrides[34088].ticker == "XOM"
    assert overrides[4904].ticker == "AEP"
    assert overrides[4904].reason == "upstream_ticker_wobble"
    for ov in overrides.values():
        assert len(ov.evidence) >= ip.MIN_OVERRIDE_EVIDENCE_CHARS
    assert ip.RATIFIED_OVERRIDE_CIKS == {34088, 4904}


def _write_overrides(path: Path, rows: list[str]) -> Path:
    header = "cik,ticker,reason,evidence,added,successor_reorg\n"
    path.write_text(header + "".join(rows))
    return path


_GOOD_EVIDENCE = (
    "submissions.json for CIK 34088 carries an empty tickers[] while the "
    "registrant still files 10-Qs; the bulk map points XOM at CIK 2115436."
)


def test_override_resolves_34088_and_only_34088(tmp_path):
    path = _write_overrides(
        tmp_path / "ov.csv", [f'34088,XOM,successor_cik,"{_GOOD_EVIDENCE}",2026-08-24,\n']
    )
    overrides = ip.load_ticker_overrides(path)
    universe = _universe([(34088, "EXXON MOBIL CORP", "core"), (4447, "HESS CORP", "core")])
    client = _StubEdgar({34088: _subs([]), 4447: _subs([])}, {})
    res = ip.resolve_universe_tickers(client, universe, overrides=overrides, bulk_map={})

    by_cik = {r.cik: r for r in res}
    assert by_cik[34088].status == "override"
    assert by_cik[34088].chosen_ticker == "XOM"
    assert by_cik[4447].status == "censored"  # the override does not leak sideways
    assert by_cik[4447].chosen_ticker is None


def test_undocumented_row_for_the_censored_cik_fails_load_time_validation(tmp_path):
    path = _write_overrides(
        tmp_path / "ov.csv",
        [
            f'34088,XOM,successor_cik,"{_GOOD_EVIDENCE}",2026-08-24,\n',
            "29915,DOW,looks_right,,2026-08-24,\n",
        ],
    )
    with pytest.raises(ValueError, match="29915"):
        ip.load_ticker_overrides(path)


def test_a_third_undocumented_row_is_still_refused(tmp_path):
    """The file grew from one ratified row to two on 2026-08-24; the load-time
    validation is unchanged, so an un-ratified third row still cannot enter."""
    path = _write_overrides(
        tmp_path / "ov.csv",
        [
            f'34088,XOM,successor_cik,"{_GOOD_EVIDENCE}",2026-08-24,\n',
            f'4904,AEP,upstream_ticker_wobble,"{_GOOD_EVIDENCE}",2026-08-24,\n',
            "790070,EMC,looks_right,,2026-08-24,\n",
        ],
    )
    with pytest.raises(ValueError, match="790070"):
        ip.load_ticker_overrides(path)


def test_unratified_cik_is_refused_even_when_fully_evidenced(tmp_path):
    path = _write_overrides(
        tmp_path / "ov.csv", [f'1105705,WBD,successor_cik,"{_GOOD_EVIDENCE}",2026-08-24,\n']
    )
    with pytest.raises(ValueError, match="not a ratified override case"):
        ip.load_ticker_overrides(path)


def test_evidence_below_the_floor_is_refused(tmp_path):
    path = _write_overrides(tmp_path / "ov.csv", ['34088,XOM,successor_cik,"obvious",2026-08-24,\n'])
    with pytest.raises(ValueError, match="evidence"):
        ip.load_ticker_overrides(path)


def test_duplicate_override_row_is_refused(tmp_path):
    path = _write_overrides(
        tmp_path / "ov.csv",
        [
            f'34088,XOM,successor_cik,"{_GOOD_EVIDENCE}",2026-08-24,\n',
            f'34088,XON,successor_cik,"{_GOOD_EVIDENCE}",2026-08-24,\n',
        ],
    )
    with pytest.raises(ValueError, match="duplicate"):
        ip.load_ticker_overrides(path)


def test_missing_override_file_raises_rather_than_silently_censoring(tmp_path):
    with pytest.raises(FileNotFoundError):
        ip.load_ticker_overrides(tmp_path / "does-not-exist.csv")


# =====================================================================
# S5 -- the successor-reorg guard (S7 finding B3, ruled 2026-08-24)
#   "bulk-symbol-maps-elsewhere is the trap SIGNATURE; an override over it
#    requires successor-reorg evidence + a continuity check + a standing WARN."
# =====================================================================

_XOM_BULK = {"XOM": 2115436}   # the real bulk map: NOT the member CIK 34088


def test_shipped_xom_row_carries_the_marker_and_aep_does_not():
    overrides = ip.load_ticker_overrides()
    assert overrides[34088].successor_reorg is True
    assert overrides[4904].successor_reorg is False
    assert ip.RATIFIED_SUCCESSOR_REORG_CIKS == {34088}
    # And the shipped file passes the guard against the REAL bulk map shape.
    ip.validate_overrides_against_bulk_map(overrides, _XOM_BULK)


def test_override_whose_symbol_bulk_maps_elsewhere_is_refused_without_the_marker(tmp_path):
    path = _write_overrides(
        tmp_path / "ov.csv", [f'34088,XOM,successor_cik,"{_GOOD_EVIDENCE}",2026-08-24,false\n']
    )
    overrides = ip.load_ticker_overrides(path)          # static load is fine
    with pytest.raises(ValueError, match="trap SIGNATURE"):
        ip.validate_overrides_against_bulk_map(overrides, _XOM_BULK)
    with pytest.raises(ValueError, match="trap SIGNATURE"):
        ip.load_ticker_overrides(path, bulk_map=_XOM_BULK)


def test_marked_override_passes_the_bulk_map_guard(tmp_path):
    path = _write_overrides(
        tmp_path / "ov.csv", [f'34088,XOM,successor_cik,"{_GOOD_EVIDENCE}",2026-08-24,true\n']
    )
    overrides = ip.load_ticker_overrides(path, bulk_map=_XOM_BULK)
    assert overrides[34088].successor_reorg is True


def test_successor_marker_is_refused_for_an_unratified_cik(tmp_path):
    path = _write_overrides(
        tmp_path / "ov.csv",
        [f'4904,AEP,upstream_ticker_wobble,"{_GOOD_EVIDENCE}",2026-08-24,true\n'],
    )
    with pytest.raises(ValueError, match="successor_reorg` is not ratified"):
        ip.load_ticker_overrides(path)


def test_successor_marker_must_be_a_boolean(tmp_path):
    path = _write_overrides(
        tmp_path / "ov.csv", [f'34088,XOM,successor_cik,"{_GOOD_EVIDENCE}",2026-08-24,maybe\n']
    )
    with pytest.raises(ValueError, match="successor_reorg"):
        ip.load_ticker_overrides(path)


def test_resolution_refuses_to_apply_an_unmarked_trap_shaped_override():
    """The guard that was missing: overrides used to apply whenever the rule
    censored a member, regardless of WHY."""
    universe = _universe([(34088, "EXXON MOBIL CORP", "core")])
    overrides = {
        34088: ip.TickerOverride(34088, "XOM", "successor_cik", _GOOD_EVIDENCE,
                                 "2026-08-24", successor_reorg=False)
    }
    client = _StubEdgar({34088: _subs([])}, _XOM_BULK)
    with pytest.raises(ValueError, match="trap SIGNATURE"):
        ip.resolve_universe_tickers(client, universe, overrides=overrides, bulk_map=_XOM_BULK)


def _xom_resolution(rows: int, first: date, coverage_start=date(2015, 7, 2)):
    res = _res(
        34088, "XOM", name="EXXON MOBIL CORP", status="override",
        coverage_start=coverage_start, coverage_end=date(2026, 8, 31),
    )
    res.chosen_bulk_cik = 2115436
    days = [first + timedelta(days=i) for i in range(rows)]
    return res, _make_prices_df([res], days)


_XOM_OVERRIDE = {
    34088: ip.TickerOverride(34088, "XOM", "successor_cik_reorganization",
                             _GOOD_EVIDENCE, "2026-08-24", successor_reorg=True)
}


def test_long_continuous_successor_series_passes_and_the_numbers_are_cited():
    res, prices = _xom_resolution(rows=1400, first=date(2012, 1, 2))
    (issue,) = ip.successor_continuity_issues([res], prices, _XOM_OVERRIDE)
    assert (issue.severity, issue.check) == ("INFO", "successor_series_continuous")
    assert "1400 rows" in issue.message
    assert "largest gap" in issue.message


def test_short_history_successor_series_is_fatal_the_ea_apc_signature():
    res, prices = _xom_resolution(rows=6, first=date(2026, 7, 17))
    (issue,) = ip.successor_continuity_issues([res], prices, _XOM_OVERRIDE)
    assert (issue.severity, issue.check) == ("FATAL", "successor_series_too_short")
    assert "REASSIGNED symbol" in issue.message


def test_late_starting_successor_series_is_fatal_even_when_long():
    """A reassigned long-history symbol (the case B12 says nothing catches):
    plenty of rows, but they start after the member's window opens."""
    res, prices = _xom_resolution(rows=1400, first=date(2020, 1, 2))
    (issue,) = ip.successor_continuity_issues([res], prices, _XOM_OVERRIDE)
    assert (issue.severity, issue.check) == ("FATAL", "successor_series_starts_late")


def test_successor_series_missing_entirely_is_fatal():
    res, _ = _xom_resolution(rows=1400, first=date(2012, 1, 2))
    empty = pd.DataFrame(columns=ip.PARQUET_COLUMNS)
    (issue,) = ip.successor_continuity_issues([res], empty, _XOM_OVERRIDE)
    assert (issue.severity, issue.check) == ("FATAL", "successor_series_missing")


def test_continuity_check_only_looks_at_successor_reorg_overrides():
    res, prices = _xom_resolution(rows=6, first=date(2026, 7, 17))
    plain = {34088: ip.TickerOverride(34088, "XOM", "x", _GOOD_EVIDENCE, "2026-08-24")}
    assert ip.successor_continuity_issues([res], prices, plain) == []
    assert ip.successor_continuity_issues([res], prices, {}) == []


def test_trap_shaped_override_warns_every_run_naming_both_ciks_and_the_evidence():
    res, _ = _xom_resolution(rows=1400, first=date(2012, 1, 2))
    (warn,) = [
        i for i in ip.ticker_wobble_issues([res], _XOM_OVERRIDE)
        if i.check == "override_symbol_bulk_maps_elsewhere"
    ]
    assert warn.severity == "WARN"
    assert warn.cik == 34088
    assert "CIK 2115436" in warn.message          # the bulk-map CIK, named
    assert "trap SIGNATURE" in warn.message
    assert "Evidence on file" in warn.message     # the row's own evidence, cited


def test_an_override_whose_symbol_maps_to_its_own_cik_does_not_get_the_trap_warn():
    aep = _res(4904, "AEP", status="override", name="AMERICAN ELECTRIC POWER CO INC")
    aep.chosen_bulk_cik = 4904
    assert [
        i for i in ip.ticker_wobble_issues([aep]) if i.check == "override_symbol_bulk_maps_elsewhere"
    ] == []


# =====================================================================
# S5 -- the AEP-shaped wobble WARN (main-session ruling 2026-08-24)
# =====================================================================


def test_aep_shaped_wobble_warns_and_is_never_auto_resolved():
    """Submissions lost the ticker; SEC's bulk map still maps AEP -> the SAME
    cik. That must WARN, and the symbol must reach the map ONLY through the
    evidenced override -- never by the code adopting the bulk symbol itself."""
    universe = _universe([(4904, "AMERICAN ELECTRIC POWER CO INC", "extension")])
    client = _StubEdgar({4904: _subs([])}, {"AEP": 4904})

    without_override = ip.resolve_universe_tickers(
        client, universe, overrides={}, bulk_map={"AEP": 4904}
    )
    assert without_override[0].status == "censored"       # no auto-resolution
    assert without_override[0].chosen_ticker is None
    warn = ip.ticker_wobble_issues(without_override)
    assert [(i.severity, i.check, i.cik) for i in warn] == [
        ("WARN", "submissions_ticker_missing_but_bulk_has", 4904)
    ]
    assert "NOT covered by an override" in warn[0].message

    with_override = ip.resolve_universe_tickers(
        client, universe, overrides=ip.load_ticker_overrides(), bulk_map={"AEP": 4904}
    )
    assert (with_override[0].status, with_override[0].chosen_ticker) == ("override", "AEP")
    assert with_override[0].rule_status == "censored"     # the wobble stays visible
    covered = ip.ticker_wobble_issues(with_override)
    assert len(covered) == 1
    assert "covered by the evidenced override" in covered[0].message


def test_wobble_warn_says_censoring_is_correct_when_bulk_offers_only_preferreds():
    """EIDP's shape: the bulk map maps CTA-PA/CTA-PB to CIK 30554, but both are
    non-common, so the censoring is right and the WARN says so."""
    universe = _universe([(30554, "EIDP, Inc.", "extension")])
    bulk = {"CTA-PA": 30554, "CTA-PB": 30554}
    res = ip.resolve_universe_tickers(
        _StubEdgar({30554: _subs(["CTA-PB", "CTA-PA"])}, bulk), universe,
        overrides={}, bulk_map=bulk,
    )
    (warn,) = ip.ticker_wobble_issues(res)
    assert warn.severity == "WARN"
    assert "only non-common symbol(s)" in warn.message
    assert "censoring is correct" in warn.message


def test_wobble_warn_is_silent_for_resolved_members_and_for_truly_dead_ones():
    universe = _universe(
        [(320193, "Apple Inc.", "core"), (773910, "ANADARKO PETROLEUM CORP", "core")]
    )
    bulk = {"AAPL": 320193, "APC": 2080921}  # nothing in the bulk map points at 773910
    res = ip.resolve_universe_tickers(
        _StubEdgar({320193: _subs(["AAPL"]), 773910: _subs([])}, bulk),
        universe, overrides={}, bulk_map=bulk,
    )
    assert [r.status for r in res] == ["resolved", "censored"]
    assert ip.ticker_wobble_issues(res) == []


# =====================================================================
# S5 -- resolved_no_coverage + the two censoring pairs
#       (main-session ruling 2026-08-24, on segment 4's real run)
# =====================================================================


def _ea() -> ip.TickerResolution:
    """EA's real shape: a core member 2017-07 -> 2021-07 whose fetched series
    exists but sits entirely after its coverage window."""
    return _res(
        712515, "EA", name="ELECTRONIC ARTS INC.", is_current_member=False,
        coverage_start=date(2015, 7, 2), coverage_end=date(2022, 8, 5),
    )


def _six_rows_in_2026(res: ip.TickerResolution) -> pd.DataFrame:
    return _make_prices_df([res], [date(2026, 7, 17) + timedelta(days=i) for i in range(6)],
                           close=209.70)


def test_zero_in_window_rows_flips_to_resolved_no_coverage():
    ea = _ea()
    flipped = ip.apply_no_coverage_status(
        [ea], _six_rows_in_2026(ea), date(2015, 7, 1), date(2026, 8, 31)
    )
    assert flipped == [ea]
    assert ea.status == "resolved_no_coverage"
    assert ea.fetch_status == "resolved"     # the fetch record is kept
    assert ea.fetched is True
    assert ea.has_usable_prices is False
    assert "0 of 6 rows fall inside its coverage window" in ea.reason
    assert "2026-07-17..2026-07-22" in ea.reason


def test_a_member_with_in_window_rows_is_left_alone():
    ok = _res(320193, "AAPL", coverage_start=date(2015, 7, 1), coverage_end=date(2026, 8, 31))
    df = _make_prices_df([ok], _business_days(date(2023, 1, 2), 20))
    assert ip.apply_no_coverage_status([ok], df, date(2015, 7, 1), date(2026, 8, 31)) == []
    assert ok.status == "resolved"
    assert ok.has_usable_prices is True


def test_counts_keep_the_two_pairs_separate():
    ea = _ea()
    ip.apply_no_coverage_status([ea], _six_rows_in_2026(ea), date(2015, 7, 1), date(2026, 8, 31))
    resolutions = [
        ea,
        _res(320193, "AAPL"),
        _res(34088, "XOM", status="override"),
        _res(773910, None, status="censored"),
        _res(29915, None, status="censored", stratum="extension"),
    ]
    c = ip.resolution_counts(resolutions)
    # FETCH pair: EA still counts as resolved AND fetched.
    assert (c["resolved"], c["override"], c["fetched"], c["unfetchable"]) == (2, 1, 3, 2)
    assert (c["censored_core"], c["censored_extension"]) == (1, 1)
    # OPERATIVE pair: EA joins the censored population.
    assert c["resolved_no_coverage"] == 1
    assert c["no_usable_prices"] == 3
    assert (c["no_usable_prices_core"], c["no_usable_prices_extension"]) == (2, 1)


def test_report_states_both_pairs_and_labels_which_is_which(capsys):
    ea = _ea()
    ip.apply_no_coverage_status([ea], _six_rows_in_2026(ea), date(2015, 7, 1), date(2026, 8, 31))
    ip.print_resolution_report([ea, _res(773910, None, status="censored")], {},
                               coverage_applied=True)
    out = capsys.readouterr().out
    assert "FETCH pair      : 1 fetched" in out
    assert "1 unfetchable" in out
    assert "OPERATIVE pair" in out
    assert "2 with NO usable prices" in out
    assert "1 unfetchable + 1 fetched-but-zero-coverage" in out
    assert "ELECTRONIC ARTS INC. (EA)" in out


def test_report_says_the_operative_pair_is_unknown_before_the_fetch(capsys):
    ip.print_resolution_report([_res(320193, "AAPL")], {})
    out = capsys.readouterr().out
    assert "OPERATIVE pair  : not determined yet" in out


def test_ticker_map_row_spells_out_both_memberships():
    ea = _ea()
    ip.apply_no_coverage_status([ea], _six_rows_in_2026(ea), date(2015, 7, 1), date(2026, 8, 31))
    frame = ip.ticker_map_frame([ea, _res(773910, None, status="censored")])
    assert list(frame.columns) == ip.TICKER_MAP_COLUMNS
    ea_row = frame[frame["cik"] == 712515].iloc[0]
    assert (ea_row["status"], ea_row["fetched"], ea_row["has_usable_prices"]) == (
        "resolved_no_coverage", True, False
    )
    cens = frame[frame["cik"] == 773910].iloc[0]
    assert (cens["status"], cens["fetched"], cens["has_usable_prices"]) == (
        "censored", False, False
    )


def test_a_second_no_coverage_member_is_a_named_fatal_finding():
    """'If any other member qualifies, report it, don't just count it.'"""
    other = _res(1045810, "NVDA", name="NVIDIA CORP",
                 coverage_start=date(2015, 7, 1), coverage_end=date(2026, 8, 31))
    other.status = "resolved_no_coverage"
    findings = [
        i for i in ip.resolution_findings([other], coverage_applied=True)
        if i.check == "unexpected_no_coverage_member"
    ]
    assert len(findings) == 1
    assert findings[0].severity == "FATAL"
    assert findings[0].cik == 1045810
    assert "NVIDIA CORP" in findings[0].message


def test_ea_recovering_its_history_is_also_a_fatal_finding():
    """The pin is two-sided: if EA ever gets its series back, both pairs move
    and nobody may quote the old numbers without re-checking."""
    findings = [
        i for i in ip.resolution_findings([_res(320193, "AAPL")], coverage_applied=True)
        if i.check == "expected_no_coverage_member_missing"
    ]
    assert [(i.severity, i.cik) for i in findings] == [("FATAL", 712515)]


def test_operative_pins_are_not_checked_before_the_fetch():
    checks = {i.check for i in ip.resolution_findings([_res(320193, "AAPL")])}
    assert "expected_no_coverage_member_missing" not in checks
    assert "unexpected_no_coverage_member" not in checks


# --- the §2c cross-reference: EDGAR must explain a vanished price series ---


def _distress_db(tmp_path: Path, rows) -> Path:
    db = tmp_path / "meta.db"
    con = sqlite3.connect(db)
    con.execute(
        "CREATE TABLE distress_events (cik INTEGER, accession_number TEXT, form TEXT, "
        "filing_date TEXT, items TEXT, event_kind TEXT)"
    )
    con.executemany("INSERT INTO distress_events VALUES (?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    return db


def test_no_coverage_member_is_cross_referenced_to_its_distress_events(tmp_path):
    ea = _ea()
    ea.status = "resolved_no_coverage"
    db = _distress_db(tmp_path, [
        (712515, "0001354457-26-000757", "25-NSE", "2026-08-04", None,
         "delisting_form_25_nse_exchange_filed"),
        (712515, "0001140361-26-032929", "15-12G", "2026-08-14", None,
         "deregistration_form_15"),
    ])
    (issue,) = ip.no_coverage_distress_issues([ea], db)
    assert issue.severity == "INFO"
    assert issue.check == "no_coverage_explained_by_distress_events"
    assert "25-NSE 2026-08-04" in issue.message
    assert "deregistration_form_15" in issue.message


def test_no_coverage_member_without_distress_events_warns(tmp_path):
    ea = _ea()
    ea.status = "resolved_no_coverage"
    db = _distress_db(tmp_path, [(999999, "x", "25-NSE", "2026-01-01", None, "delisting_form_25")])
    (issue,) = ip.no_coverage_distress_issues([ea], db)
    assert (issue.severity, issue.check) == ("WARN", "no_coverage_without_distress_events")


def test_distress_cross_check_is_skipped_without_a_db_and_warns_if_it_is_missing(tmp_path):
    ea = _ea()
    ea.status = "resolved_no_coverage"
    assert ip.no_coverage_distress_issues([ea], None) == []
    (issue,) = ip.no_coverage_distress_issues([ea], tmp_path / "nope.db")
    assert issue.check == "distress_crosscheck_unavailable"


# =====================================================================
# S5 -- census reconciliation (F2_SPEC §6.3)
# =====================================================================


def _census(path: Path, rows) -> Path:
    """rows: iterable of (cik, has_current_ticker)."""
    pd.DataFrame(
        [{"cik": cik, "name": f"Company {cik}", "has_current_ticker": has} for cik, has in rows]
    ).to_parquet(path, index=False)
    return path


def test_census_delta_matching_the_preregistration_is_clean(tmp_path):
    path = _census(
        tmp_path / "census.parquet",
        [(34088, False), (30554, True), (4447, False), (1800, True), (999999, False)],
    )
    resolutions = [
        _res(34088, "XOM", status="override"),
        _res(30554, None, status="censored"),
        _res(4447, None, status="censored"),
        _res(1800, "ABT"),
    ]
    diff = ip.reconcile_censoring_census(resolutions, path)
    assert diff.clean
    assert diff.expected_resolved_by_e2 == {34088}
    assert diff.expected_censored_by_e2 == {30554}
    assert diff.census_ciks_not_in_universe == {999999}
    assert ip.resolution_findings(resolutions, diff) != []  # counts are pinned, not these 4
    assert [i for i in ip.resolution_findings(resolutions, diff)
            if i.check == "census_delta_unexpected"] == []


def test_unexpected_census_delta_is_reported_as_a_finding(tmp_path):
    path = _census(tmp_path / "census.parquet", [(1800, True), (2488, True)])
    resolutions = [_res(1800, "ABT"), _res(2488, None, status="censored")]
    diff = ip.reconcile_censoring_census(resolutions, path)
    assert not diff.clean
    assert diff.unexpected_censored_by_e2 == {2488}
    findings = [i for i in ip.resolution_findings(resolutions, diff)
                if i.check == "census_delta_unexpected"]
    assert len(findings) == 1
    assert findings[0].severity == "FATAL"
    assert findings[0].cik == 2488


def test_resolution_count_deviation_is_a_fatal_finding():
    resolutions = [_res(1800, "ABT")]
    findings = ip.resolution_findings(resolutions)
    assert all(f.severity == "FATAL" for f in findings)
    assert {f.check for f in findings} == {"resolution_count_deviation"}
    assert any("resolved=1" in f.message for f in findings)


def test_censored_members_are_named_in_the_report(capsys):
    resolutions = [
        _res(1800, "ABT"),
        _res(773910, None, status="censored", name="ANADARKO PETROLEUM CORP"),
        _res(29915, None, status="censored", name="DOW CHEMICAL CO /DE/", stratum="extension"),
    ]
    ip.print_resolution_report(resolutions, ip.load_ticker_overrides())
    out = capsys.readouterr().out
    assert "2 unfetchable (1 core / 1 extension)" in out
    assert "Unfetchable members (2), named, never silent (FETCH pair)" in out
    assert "ANADARKO PETROLEUM CORP" in out
    assert "DOW CHEMICAL CO /DE/" in out
    assert "CIK 34088 -> XOM" in out            # overrides printed whether or not they fire
    assert "DELIBERATELY CENSORED" in out       # so is the 29915 ruling


# =====================================================================
# S5 -- the re-pin of the old load_universe() test (F2_SPEC §8.1 row 1)
# =====================================================================


@pytest.fixture(scope="module")
def real_resolutions():
    """The §6.1 rule run over the REAL 244 members, from the local cache only.
    Replaces `test_load_universe_returns_all_25_tickers`: E1's fixed 25-ticker
    data/universe.csv is no longer any E2 code path's input.
    """
    if not (RAW_DIR / "company_tickers.json").exists():
        pytest.skip("data/raw/ cache absent (gitignored) -- run S6 segment 1 first")
    from ingest_metadata import load_universe

    universe = load_universe()
    client = _CacheOnlyEdgar()
    missing = [
        int(c) for c in universe["cik"]
        if not (RAW_DIR / "submissions" / f"CIK{int(c):010d}.json").exists()
    ]
    if missing:
        pytest.skip(f"submissions cache incomplete ({len(missing)} of {len(universe)} missing)")
    return ip.resolve_universe_tickers(client, universe, bulk_map=ip.load_bulk_ticker_map(client))


def test_price_ticker_map_resolves_211_and_censors_33(real_resolutions):
    """MEASURED 2026-08-24 against the post-segment-1 cache and pinned
    (F2_SPEC §6.1 as amended): the rule alone resolves 211 of 244 and censors
    33 (AEP's submissions lost their ticker in an upstream wobble); the two
    evidenced overrides take that to 213 fetchable / 31 censored (27 core / 4
    extension) -- the FINAL PAIR IS UNCHANGED from the pre-wobble run."""
    counts = ip.resolution_counts(real_resolutions)
    assert counts["members"] == 244
    assert counts["resolved"] == 211
    assert counts["override"] == 2
    assert counts["resolved"] + counts["censored"] + counts["override"] == 244
    # The rule on its own -- before the overrides fire -- censors 33.
    assert counts["censored"] + counts["override"] == 33
    assert sum(1 for r in real_resolutions if r.rule_status == "censored") == 33
    assert counts["fetchable"] == 213
    assert counts["censored"] == 31
    assert counts["censored_core"] == 27
    assert counts["censored_extension"] == 4
    assert ip.resolution_findings(real_resolutions) == []


def test_both_overrides_fire_on_the_real_universe(real_resolutions):
    by_cik = {r.cik: r for r in real_resolutions}
    assert (by_cik[34088].status, by_cik[34088].chosen_ticker) == ("override", "XOM")
    assert (by_cik[4904].status, by_cik[4904].chosen_ticker) == ("override", "AEP")


def test_exactly_two_real_members_are_wobble_shaped(real_resolutions):
    """The measurement the main session asked for: of the 33 rule-censored
    CIKs, which have a bulk-map symbol pointing at their own CIK? Exactly two --
    AEP (admissible symbol, override-covered) and EIDP (preferreds only, so
    censoring is correct). If a third ever appears it is a finding for the
    owner/main session, not an override this code adds by itself."""
    warns = [
        i for i in ip.ticker_wobble_issues(real_resolutions)
        if i.check == "submissions_ticker_missing_but_bulk_has"
    ]
    assert {i.cik for i in warns} == {4904, 30554}
    assert all(i.severity == "WARN" for i in warns)
    by_cik = {i.cik: i for i in warns}
    assert "covered by the evidenced override" in by_cik[4904].message
    assert "censoring is correct" in by_cik[30554].message


def test_xom_warns_on_every_real_run_via_the_trap_signature_arm(real_resolutions):
    """S7 B3's third problem, fixed: 34088 has no bulk symbols of its own, so
    arm 1 skips it and XOM used to produce no WARN at all while AEP -- the SAFE
    direction -- warned every run. Both warn now."""
    overrides = ip.load_ticker_overrides()
    trap = [
        i for i in ip.ticker_wobble_issues(real_resolutions, overrides)
        if i.check == "override_symbol_bulk_maps_elsewhere"
    ]
    assert [(i.severity, i.cik, i.ticker) for i in trap] == [("WARN", 34088, "XOM")]
    assert "CIK 2115436" in trap[0].message
    xom = next(r for r in real_resolutions if r.cik == 34088)
    assert xom.chosen_bulk_cik == 2115436 and xom.status == "override"


def test_all_25_e1_cik_ticker_pairs_reproduce(real_resolutions):
    """Regression against E1: every one of its 25 CIK<->ticker pairs comes back
    from the CIK-verified rule, XOM via the override row (F2_SPEC §8.1)."""
    e1 = pd.read_csv(REPO_ROOT / "data" / "universe.csv")
    by_cik = {r.cik: r for r in real_resolutions}
    assert len(e1) == 25
    for row in e1.itertuples():
        res = by_cik[int(row.cik)]
        assert res.chosen_ticker == row.ticker, f"CIK {row.cik}"
    assert by_cik[34088].status == "override"
    assert {by_cik[int(c)].status for c in e1["cik"]} == {"resolved", "override"}


def test_no_censored_member_ever_carries_a_ticker(real_resolutions):
    assert [r for r in real_resolutions if not r.fetchable and r.chosen_ticker] == []


@pytest.fixture(scope="module")
def real_resolutions_with_coverage(real_resolutions):
    """The real resolution, refined against the REAL fetched parquet written by
    S6 segment 4 (read-only). Skips if the parquet is not on disk."""
    if not ip.OUTPUT_PARQUET.exists():
        pytest.skip(f"{ip.OUTPUT_PARQUET.name} absent -- run S6 segment 4 first")
    prices = pd.read_parquet(ip.OUTPUT_PARQUET)
    ip.apply_no_coverage_status(real_resolutions, prices)
    return real_resolutions


def test_ea_is_the_sole_fetched_member_with_no_usable_prices(real_resolutions_with_coverage):
    """MEASURED against data/prices_e2.parquet (1,960,738 rows / 213 CIKs):
    EA is the ONLY fetched member with zero rows inside its coverage window --
    6 rows, all 2026-07-17..2026-08-10, after a 2015-07-02..2022-08-05 window.
    The next smallest in-window count is 539."""
    no_cov = [r for r in real_resolutions_with_coverage if r.status == "resolved_no_coverage"]
    assert [r.cik for r in no_cov] == [712515]
    assert no_cov[0].chosen_ticker == "EA"
    assert no_cov[0].stratum == "core"
    assert no_cov[0].fetched is True and no_cov[0].has_usable_prices is False
    assert ip.EXPECTED_NO_COVERAGE_CIKS == {712515}


def test_both_real_pairs(real_resolutions_with_coverage):
    """FETCH 213/31 (27 core / 4 extension); OPERATIVE 32 with no usable prices
    (28 core / 4 extension). Two facts, never merged."""
    c = ip.resolution_counts(real_resolutions_with_coverage)
    assert (c["fetched"], c["unfetchable"]) == (213, 31)
    assert (c["censored_core"], c["censored_extension"]) == (27, 4)
    assert c["no_usable_prices"] == 32
    assert (c["no_usable_prices_core"], c["no_usable_prices_extension"]) == (28, 4)
    assert c["no_usable_prices"] == c["unfetchable"] + c["resolved_no_coverage"]
    assert ip.resolution_findings(real_resolutions_with_coverage, coverage_applied=True) == []


def test_real_xom_series_is_long_and_continuous(real_resolutions_with_coverage):
    """The corroborating fact B3 said was never cited or checked, now both.
    MEASURED read-only from data/prices_e2.parquet: 14,282 rows, 1970-01-02 ->
    2026-08-24, largest gap 7 calendar days."""
    prices = pd.read_parquet(ip.OUTPUT_PARQUET)
    xom = prices[prices["cik"] == 34088]
    assert len(xom) == 14282
    assert xom["date"].min() == date(1970, 1, 2)
    days = sorted(xom["date"])
    assert max((b - a).days for a, b in zip(days, days[1:])) == 7

    (issue,) = ip.successor_continuity_issues(
        real_resolutions_with_coverage, prices, ip.load_ticker_overrides()
    )
    assert (issue.severity, issue.check, issue.cik) == (
        "INFO", "successor_series_continuous", 34088
    )
    assert "14282 rows" in issue.message


def test_real_ea_delisting_is_visible_in_distress_events(real_resolutions_with_coverage):
    """EXPANSION_PLAN §2c's mechanism must demonstrably cover this case."""
    db = REPO_ROOT / "data" / "filings_metadata_e2.db"
    if not db.exists():
        pytest.skip("data/filings_metadata_e2.db absent -- run S6 segment 1 first")
    rows = ip.distress_events_for(712515, db)
    kinds = {k for _, _, k, _ in rows}
    assert rows, "EA has no distress_events rows -- §2c visibility gap"
    assert "delisting_form_25_nse_exchange_filed" in kinds
    assert "deregistration_form_15" in kinds
    (issue,) = ip.no_coverage_distress_issues(real_resolutions_with_coverage, db)
    assert issue.severity == "INFO"
    assert issue.cik == 712515


def test_real_census_reconciliation_matches_the_preregistration(real_resolutions):
    diff = ip.reconcile_censoring_census(real_resolutions)
    assert diff.clean
    assert diff.expected_resolved_by_e2 == {34088}
    assert diff.expected_censored_by_e2 == {30554}
    assert len(diff.f1_censored) == 31
    assert len(diff.e2_censored) == 31


# =====================================================================
# S5 -- fetch changes (F2_SPEC §6.4)
# =====================================================================


class _FakePriceClient:
    """`meta="default"` mimics a well-formed Yahoo response; `meta=None`
    mimics the Stooq path, which has no meta block to check."""

    def __init__(self, source_name: str = "yahoo_finance_chart", meta="default"):
        self.calls: list[tuple[str, str]] = []
        self.source_name = source_name
        self.meta = meta
        self.last_yahoo_meta = None

    def get_daily_bars(self, ticker, force=False, source="stooq-first"):
        self.calls.append((ticker, source))
        if self.meta == "default":
            self.last_yahoo_meta = {"symbol": ticker, "instrumentType": "EQUITY"}
        else:
            self.last_yahoo_meta = dict(self.meta) if self.meta else None
        df = pd.DataFrame(
            {
                "date": [date(2024, 1, 2), date(2024, 1, 3)],
                "open": [100.0, 101.0],
                "high": [101.0, 102.0],
                "low": [99.0, 100.0],
                "close": [100.5, 101.5],
                "volume": [1_000_000, 1_100_000],
            }
        )
        return df, self.source_name


def test_parquet_carries_cik_as_the_join_key():
    fetchable = [_res(320193, "AAPL"), _res(34088, "XOM", status="override")]
    client = _FakePriceClient()
    combined, results = ip.ingest_all(client, fetchable, fetched_at="t", price_source="yahoo")
    assert list(combined.columns) == ip.PARQUET_COLUMNS
    assert set(combined["cik"]) == {320193, 34088}
    assert combined.loc[combined["cik"] == 34088, "ticker"].unique().tolist() == ["XOM"]
    assert [r.cik for r in results] == [320193, 34088]


def test_price_source_default_is_yahoo_and_stooq_first_is_still_reachable():
    parser = ip.build_parser()
    assert parser.parse_args([]).price_source == "yahoo"
    assert parser.parse_args(["--price-source", "stooq-first"]).price_source == "stooq-first"

    client = _FakePriceClient()
    ip.ingest_all(client, [_res(320193, "AAPL")], fetched_at="t", price_source="yahoo")
    ip.ingest_all(client, [_res(320193, "AAPL")], fetched_at="t", price_source="stooq-first")
    assert client.calls == [("AAPL", "yahoo"), ("AAPL", "stooq-first")]


def test_e1_prices_parquet_is_refused_as_an_output():
    assert ip.main(["--output", str(ip.E1_OUTPUT_PARQUET)]) == 2


def test_yahoo_meta_symbol_mismatch_warns():
    client = _FakePriceClient(meta={"symbol": "ARKO", "instrumentType": "EQUITY"})
    _, results = ip.ingest_all(client, [_res(773910, "APC")], fetched_at="t", price_source="yahoo")
    issues = ip.meta_tripwire_issues(results)
    assert [(i.severity, i.check, i.cik) for i in issues] == [
        ("WARN", "meta_symbol_mismatch", 773910)
    ]
    assert "ARKO" in issues[0].message


def test_yahoo_meta_instrument_type_mismatch_warns():
    client = _FakePriceClient(meta={"symbol": "SPY", "instrumentType": "ETF"})
    _, results = ip.ingest_all(client, [_res(1, "SPY")], fetched_at="t", price_source="yahoo")
    issues = ip.meta_tripwire_issues(results)
    assert [(i.severity, i.check) for i in issues] == [("WARN", "meta_instrument_type")]


def test_matching_yahoo_meta_is_silent_and_stooq_bars_are_not_meta_checked():
    client = _FakePriceClient()
    _, results = ip.ingest_all(client, [_res(320193, "AAPL")], fetched_at="t", price_source="yahoo")
    assert ip.meta_tripwire_issues(results) == []

    stooq = _FakePriceClient(source_name="stooq", meta=None)
    _, stooq_results = ip.ingest_all(
        stooq, [_res(320193, "AAPL")], fetched_at="t", price_source="stooq-first"
    )
    assert (stooq_results[0].meta_symbol, stooq_results[0].meta_instrument_type) == (None, None)
    assert ip.meta_tripwire_issues(stooq_results) == []


# =====================================================================
# Validation: coverage, censoring, outliers
# =====================================================================


def test_full_coverage_produces_no_issues():
    calendar = _business_days(date(2023, 1, 2), 40)  # a Monday
    fetchable = [_res(1, "AAA"), _res(2, "BBB"), _res(3, "CCC")]
    df = _make_prices_df(fetchable, calendar)

    assert ip.validate_prices(df, fetchable, calendar[0], calendar[-1]) == []


def test_small_gap_is_not_flagged():
    calendar = _business_days(date(2023, 1, 2), 40)
    fetchable = [_res(1, "AAA"), _res(2, "BBB")]
    df = _make_prices_df(fetchable, calendar)
    df = df[~((df["cik"] == 2) & (df["date"].isin(set(calendar[5:8]))))]

    issues = ip.validate_prices(df, fetchable, calendar[0], calendar[-1])
    assert [i for i in issues if i.check == "coverage_gap"] == []


def test_large_interior_gap_is_flagged_warn_with_missing_dates_listed():
    calendar = _business_days(date(2023, 1, 2), 40)
    fetchable = [_res(1, "AAA"), _res(2, "BBB")]
    df = _make_prices_df(fetchable, calendar)
    df = df[~((df["cik"] == 2) & (df["date"].isin(set(calendar[5:15]))))]

    gaps = [i for i in ip.validate_prices(df, fetchable, calendar[0], calendar[-1])
            if i.check == "coverage_gap"]
    assert len(gaps) == 1
    assert (gaps[0].severity, gaps[0].ticker, gaps[0].cik) == ("WARN", "BBB", 2)
    assert "missing 10 trading days" in gaps[0].message


def test_resolved_ticker_missing_entirely_is_fatal():
    calendar = _business_days(date(2023, 1, 2), 40)
    aaa, bbb = _res(1, "AAA"), _res(2, "BBB")
    df = _make_prices_df([aaa], calendar)  # BBB never fetched at all

    fatals = [i for i in ip.validate_prices(df, [aaa, bbb], calendar[0], calendar[-1])
              if i.severity == "FATAL" and i.cik == 2]
    assert [i.check for i in fatals] == ["missing_entirely"]


def test_censored_cik_is_never_a_price_fatal_and_is_counted_instead(capsys):
    """F2_SPEC §6.4: `missing_entirely` is FATAL only for a RESOLVED ticker.
    A censored member is not passed to the fetch at all -- it is a counted,
    named exclusion in the censoring report."""
    calendar = _business_days(date(2023, 1, 2), 40)
    aaa = _res(1, "AAA")
    censored = _res(773910, None, status="censored", name="ANADARKO PETROLEUM CORP")
    resolutions = [aaa, censored]
    fetchable = [r for r in resolutions if r.fetchable]
    df = _make_prices_df(fetchable, calendar)

    issues = ip.validate_prices(df, fetchable, calendar[0], calendar[-1])
    assert issues == []
    assert [i for i in issues if i.check == "missing_entirely"] == []

    ip.print_resolution_report(resolutions, {})
    out = capsys.readouterr().out
    assert "1 unfetchable (1 core / 0 extension)" in out
    assert "ANADARKO PETROLEUM CORP" in out


def test_current_member_ending_months_early_is_fatal():
    calendar = _business_days(date(2023, 1, 2), 120)
    aaa, bbb = _res(1, "AAA"), _res(2, "BBB")
    df = _make_prices_df([aaa, bbb], calendar)
    df = df[~((df["cik"] == 2) & (df["date"] > calendar[-60]))]

    issues = ip.validate_prices(df, [aaa, bbb], calendar[0], calendar[-1])
    assert any(i.check == "ends_early" and i.severity == "FATAL" and i.cik == 2 for i in issues)


def test_former_member_ending_early_is_info_not_fatal():
    """A former member's series stopping is the expected delisting/acquisition
    shape (EXPANSION_PLAN §3.6), not a fetch failure."""
    calendar = _business_days(date(2023, 1, 2), 120)
    aaa = _res(1, "AAA")
    bbb = _res(2, "BBB", is_current_member=False)
    df = _make_prices_df([aaa, bbb], calendar)
    df = df[~((df["cik"] == 2) & (df["date"] > calendar[-60]))]

    issues = ip.validate_prices(df, [aaa, bbb], calendar[0], calendar[-1])
    assert [i.severity for i in issues if i.cik == 2] == ["INFO"]
    assert [i.check for i in issues if i.cik == 2] == ["series_ends_before_window_end"]


def test_series_starting_long_after_the_coverage_window_opens_warns():
    """The shape a REASSIGNED symbol would have (ARKO's history starts 2020;
    Anadarko was a member from 2016)."""
    calendar = _business_days(date(2023, 1, 2), 120)
    aaa = _res(1, "AAA")
    late = _res(2, "BBB", coverage_start=calendar[0])
    df = pd.concat(
        [_make_prices_df([aaa], calendar), _make_prices_df([late], calendar[80:])],
        ignore_index=True,
    )

    issues = ip.validate_prices(df, [aaa, late], calendar[0], calendar[-1])
    assert [i.check for i in issues if i.cik == 2] == ["starts_after_coverage_start"]
    assert [i.severity for i in issues if i.cik == 2] == ["WARN"]


def test_ticker_present_but_zero_rows_in_its_coverage_window_is_fatal():
    calendar = _business_days(date(2023, 1, 2), 40)
    aaa, bbb = _res(1, "AAA"), _res(2, "BBB")
    df = _make_prices_df([aaa, bbb], calendar)
    window_start, window_end = calendar[-5], calendar[-1]
    df = df[~((df["cik"] == 2) & (df["date"] >= window_start))]

    issues = ip.validate_prices(df, [aaa, bbb], window_start, window_end)
    assert any(i.check == "missing_in_window" and i.severity == "FATAL" for i in issues)


def test_validate_prices_refuses_a_frame_without_cik():
    calendar = _business_days(date(2023, 1, 2), 5)
    aaa = _res(1, "AAA")
    df = _make_prices_df([aaa], calendar).drop(columns=["cik"])
    with pytest.raises(ValueError, match="cik"):
        ip.validate_prices(df, [aaa], calendar[0], calendar[-1])


def test_zero_or_negative_close_is_fatal():
    calendar = _business_days(date(2023, 1, 2), 10)
    aaa = _res(1, "AAA")
    df = _make_prices_df([aaa], calendar)
    df.loc[df.index[3], "close"] = 0.0
    df.loc[df.index[5], "close"] = -5.0

    fatals = [i for i in ip.validate_prices(df, [aaa], calendar[0], calendar[-1])
              if i.check == "non_positive_close"]
    assert len(fatals) == 2
    assert all(i.severity == "FATAL" and i.cik == 1 for i in fatals)


# ---------------------------------------------------------------------
# Return outlier detection + calibration.
# ---------------------------------------------------------------------


def test_return_outlier_detected_above_bound():
    calendar = _business_days(date(2023, 1, 2), 10)
    df = _make_prices_df([_res(1, "AAA")], calendar, close=100.0)
    # Inject a +50% single-day move on the LAST day, so there's no subsequent
    # "reverts back to normal" day to also register as its own outlier.
    df.loc[df.index[-1], "close"] = 150.0

    outliers = ip.find_return_outliers(df, bound=0.15)
    assert len(outliers) == 1
    assert outliers["ret"].iloc[0] == pytest.approx(0.5)
    assert outliers["cik"].iloc[0] == 1


def test_calibrate_return_bound_has_a_floor():
    calendar = _business_days(date(2023, 1, 2), 30)
    df = _make_prices_df([_res(1, "AAA")], calendar, close=100.0)
    assert ip.calibrate_return_bound(df) == ip.RETURN_BOUND_FLOOR


def test_calibrate_return_bound_rises_above_floor_for_volatile_data():
    calendar = _business_days(date(2023, 1, 2), 250)
    df = _make_prices_df([_res(1, "AAA")], calendar, close=100.0)
    df["close"] = [100.0 * (1.3 if i % 2 == 0 else 1.0) for i in range(len(calendar))]
    assert ip.calibrate_return_bound(df) > ip.RETURN_BOUND_FLOOR


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
