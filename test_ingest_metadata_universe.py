"""test_ingest_metadata_universe.py -- F2 stage S2 tests: hybrid136
membership adoption, the fixed corpus window, the per-company-window
validation redesign, and the evidenced validation-exceptions file that
replaced `--allow-incomplete-universe`.

Everything here is OFFLINE. No test opens a socket: the real universe
artifacts are read from disk (they are checksum-pinned, so reading them IS
the point), and every EDGAR interaction goes through a fake client built from
synthetic dicts. Pattern follows test_ingest_fundamentals.py.

Covers F2_SPEC §8.1 row 2 (the removed 20-30 universe-size bound) and the
whole §8.2 "S2" block.

Run with: python3 -m pytest test_ingest_metadata_universe.py -v
"""
from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

import ingest_metadata as im


# ---------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------


def _recent(filings: list[tuple[str, date]], items: dict[int, str] | None = None) -> dict:
    """Build a `filings.recent`-shaped dict of parallel arrays from a list of
    (form, filing_date)."""
    items = items or {}
    n = len(filings)
    return {
        "form": [f for f, _ in filings],
        "filingDate": [d.isoformat() for _, d in filings],
        "accessionNumber": [f"0000000000-00-{i:06d}" for i in range(n)],
        "reportDate": [""] * n,
        "acceptanceDateTime": [""] * n,
        "primaryDocument": [f"doc{i}.htm" for i in range(n)],
        "items": [items.get(i, "") for i in range(n)],
    }


def _submissions(filings: list[tuple[str, date]], tickers: list[str] | None = None) -> dict:
    return {
        "tickers": tickers or [],
        "filings": {"recent": _recent(filings), "files": []},
    }


class FakeClient:
    """Stands in for EdgarClient. Never touches the network; counts calls so
    a test can assert cache-first behaviour."""

    def __init__(self, submissions_by_cik: dict[int, dict], ticker_map: dict[str, int] | None = None):
        self.submissions_by_cik = submissions_by_cik
        self.ticker_map = ticker_map or {}
        self.request_count = 0
        self.effective_recent_calls = 0

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
        self.effective_recent_calls += 1
        return self.submissions_by_cik[cik]["filings"]["recent"]


def _universe_row(
    cik: int, coverage_start: date, coverage_end: date, is_current: bool,
    name: str = "TEST CO", sector: str = "tech", stratum: str = "core",
) -> dict:
    return {
        "cik": cik, "name": name, "sector": sector, "stratum": stratum,
        "coverage_start": coverage_start, "coverage_end": coverage_end,
        "is_current_member": is_current,
    }


def _universe(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def _evenly_spaced(start: date, span_days: int, n: int) -> list[tuple[str, date]]:
    """n periodic filings from `start` to `start + span_days`, evenly spaced.
    Every 4th is a 10-K; the check counts 10-K and 10-Q identically."""
    out = []
    for i in range(n):
        offset = round(i * span_days / (n - 1)) if n > 1 else 0
        out.append(("10-K" if i % 4 == 0 else "10-Q", start + timedelta(days=offset)))
    return out


def _checks(problems, name):
    return [p for p in problems if p.check == name]


def _fatals(problems):
    return [p for p in problems if p.severity == "FATAL"]


# ---------------------------------------------------------------------
# §1 -- checksum guard on the real artifacts
# ---------------------------------------------------------------------


def test_real_universe_artifacts_match_pinned_checksums():
    # The verify-artifact rule, exercised against the shipped files. If this
    # fails, F1's output moved and every downstream E2 number is suspect.
    pinned = im.verify_universe_checksums()
    assert set(pinned) == {
        "hybrid136.csv", "hybrid136.parquet",
        "hybrid136_panel.csv", "hybrid136_panel.parquet",
        "manual_exclusions.csv",
        "price_censoring_census.csv", "price_censoring_census.parquet",
    }


def test_checksum_mismatch_raises(tmp_path: Path):
    src = im.HYBRID136_CHECKSUMS.parent
    doc = json.loads(im.HYBRID136_CHECKSUMS.read_text())
    for name in doc["sha256"]:
        shutil.copy(src / name, tmp_path / name)
    copied_json = tmp_path / im.HYBRID136_CHECKSUMS.name
    shutil.copy(im.HYBRID136_CHECKSUMS, copied_json)

    # Untampered copy verifies.
    im.verify_universe_checksums(copied_json)

    # Tamper one byte of the parquet -> raises, naming the file.
    tampered = tmp_path / "hybrid136.parquet"
    tampered.write_bytes(tampered.read_bytes() + b"\x00")
    with pytest.raises(ValueError, match="hybrid136.parquet"):
        im.verify_universe_checksums(copied_json)


def test_missing_artifact_raises(tmp_path: Path):
    shutil.copy(im.HYBRID136_CHECKSUMS, tmp_path / im.HYBRID136_CHECKSUMS.name)
    with pytest.raises(ValueError, match="MISSING"):
        im.verify_universe_checksums(tmp_path / im.HYBRID136_CHECKSUMS.name)


# ---------------------------------------------------------------------
# §1.3 -- the exact pins that replace E1's `20 <= len(df) <= 30`
# ---------------------------------------------------------------------


def test_load_universe_pins_244_member_ciks():
    df = im.load_universe()
    assert len(df) == 244 == im.EXPECTED_MEMBER_CIKS
    assert df["cik"].is_unique
    assert list(df.columns) == [
        "cik", "name", "sector", "stratum",
        "coverage_start", "coverage_end", "is_current_member",
    ]
    # Deliberately NOT a ticker key -- see load_universe()'s docstring.
    assert "ticker" not in df.columns


def test_load_membership_pins_299_spells_136_per_date_over_11_dates():
    spells = im.load_membership()
    assert len(spells) == 299 == im.EXPECTED_MEMBERSHIP_SPELLS
    assert spells["cik"].nunique() == 244

    dates = sorted(
        {d for d in spells["member_from"]} | {d for d in spells["member_to"] if d}
    )
    assert len(dates) == 11 == im.EXPECTED_RECONSTITUTION_DATES
    assert dates[0] == "2016-07-01" and dates[-1] == "2026-07-01"

    # `member_to` is EXCLUSIVE -- the first reconstitution date at which the
    # CIK is no longer a member. Cross-checked against the panel below.
    for d in dates:
        members = spells[
            (spells["member_from"] <= d)
            & ((spells["member_to"] == "") | (spells["member_to"] > d))
        ]
        assert members["cik"].nunique() == 136 == im.EXPECTED_MEMBERS_PER_DATE, d

    assert (spells["member_to"] == "").sum() == 136


def test_spells_reproduce_the_panel_membership_exactly():
    """The spells table is the only membership input F2 reads. This pins that
    it agrees with F1's per-date panel at every reconstitution date, and that
    `member_to` really is exclusive (F2_SPEC §1.2's prose says otherwise)."""
    spells = im.load_membership()
    panel = pd.read_parquet(im.UNIVERSE_DIR / "hybrid136_panel.parquet")
    assert len(panel) == 1496
    for d in sorted(panel["recon_date"].unique()):
        from_spells = set(
            spells.loc[
                (spells["member_from"] <= d)
                & ((spells["member_to"] == "") | (spells["member_to"] > d)),
                "cik",
            ]
        )
        assert from_spells == set(panel.loc[panel["recon_date"] == d, "cik"]), d
    for _, r in spells.iterrows():
        covered = [
            d for d in panel["recon_date"].unique()
            if d >= r["member_from"] and (r["member_to"] == "" or d < r["member_to"])
        ]
        assert len(covered) == r["n_reconstitutions"], (r["cik"], r["member_from"])


def test_universe_size_range_bound_is_replaced_by_an_exact_pin(monkeypatch):
    # E1's 20-30 range bound is deliberately gone (F2_SPEC §8.1 row 2).
    # Behavioural pin: any collapse that is not exactly 244 CIKs refuses to
    # proceed, rather than being quietly accepted as "close enough".
    assert im.EXPECTED_MEMBER_CIKS == 244
    real = im.load_membership()
    monkeypatch.setattr(
        im, "load_membership", lambda *a, **k: real[real["cik"] < 900000].copy()
    )
    with pytest.raises(ValueError, match="expected exactly 244"):
        im.load_universe()


def test_wrong_spell_count_refuses_to_load(monkeypatch, tmp_path: Path):
    truncated = im.load_membership().head(10)
    monkeypatch.setattr(pd, "read_parquet", lambda *a, **k: truncated)
    with pytest.raises(ValueError, match="expected exactly 299"):
        im.load_membership(verify=False)


# ---------------------------------------------------------------------
# §1.2 -- derived coverage windows
# ---------------------------------------------------------------------


def test_coverage_windows_match_the_derivation():
    spells = im.load_membership()
    universe = im.load_universe().set_index("cik")
    for cik, g in spells.groupby("cik"):
        row = universe.loc[int(cik)]
        first_from = min(date.fromisoformat(d) for d in g["member_from"])
        expected_start = max(
            im.CORPUS_WINDOW_START, first_from - timedelta(days=730)
        )
        assert row["coverage_start"] == expected_start

        if (g["member_to"] == "").any():
            assert bool(row["is_current_member"]) is True
            assert row["coverage_end"] == im.CORPUS_WINDOW_END
        else:
            last_to = max(date.fromisoformat(d) for d in g["member_to"])
            assert bool(row["is_current_member"]) is False
            assert row["coverage_end"] == min(
                im.CORPUS_WINDOW_END, last_to + timedelta(days=400)
            )


def test_coverage_start_is_clipped_at_the_corpus_floor():
    universe = im.load_universe()
    # Every member whose first membership date is 2016-07-01 or 2017-07-01
    # would derive a pre-2015-07-01 start; all must be clipped to the floor.
    assert (universe["coverage_start"] >= im.CORPUS_WINDOW_START).all()
    assert (universe["coverage_start"] == im.CORPUS_WINDOW_START).any()
    assert (universe["coverage_end"] <= im.CORPUS_WINDOW_END).all()
    assert universe["is_current_member"].sum() == 136


# ---------------------------------------------------------------------
# §2 -- fixed window constants, nothing derived from today()
# ---------------------------------------------------------------------


def test_window_constants_are_fixed_literals():
    assert im.CORPUS_WINDOW_START == date(2015, 7, 1)
    assert im.CORPUS_WINDOW_END == date(2026, 8, 31)
    assert im.FUNDAMENTALS_HISTORY == "full"
    assert im.PRICES_HISTORY == "full"
    # E1's today()-derived cutoff is deleted, not parameterised.
    assert not hasattr(im, "lookback_cutoff")
    assert not hasattr(im, "LOOKBACK_QUARTERS")


def test_nothing_but_the_run_stamp_calls_today():
    """`date.today()` may be CALLED exactly once in this module -- the
    provenance stamp on the validation-problems rows. No window, cutoff, or
    threshold derives from it, which is what makes a re-run on a different
    day reproduce the same corpus. (AST-based, so prose about the deleted
    E1 behaviour in comments/docstrings doesn't trip it.)"""
    import ast

    tree = ast.parse(Path(im.__file__).read_text())
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "today"
    ]
    assert len(calls) == 1
    assigns = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Assign) and n.value in calls
    ]
    assert [t.id for a in assigns for t in a.targets] == ["run_date"]


def test_fundamentals_imports_the_window_rather_than_redeclaring_it():
    import ingest_fundamentals as ifund
    assert ifund.CORPUS_WINDOW_START is im.CORPUS_WINDOW_START
    assert ifund.CORPUS_WINDOW_END is im.CORPUS_WINDOW_END


# ---------------------------------------------------------------------
# §3.1 -- per-company-window validation
# ---------------------------------------------------------------------


def test_late_ipo_member_produces_no_history_fatal():
    # member_from 2024-07-01 -> coverage_start 2022-07-02. The company's
    # first filing is 2021-01-15: AFTER the corpus floor (so E1's single
    # global cutoff would have FATALed it) but comfortably before its own
    # coverage_start.
    coverage_start = date(2024, 7, 1) - timedelta(days=730)
    filings = _evenly_spaced(date(2021, 1, 15), 2000, 23)
    assert filings[0][1] > im.CORPUS_WINDOW_START
    assert filings[0][1] < coverage_start

    client = FakeClient({777: _submissions(filings)})
    universe = _universe(_universe_row(777, coverage_start, im.CORPUS_WINDOW_END, True))
    problems = im.validate_universe(client, universe)

    assert _checks(problems, "history_reaches_cutoff") == []


def test_history_not_reaching_own_coverage_start_is_fatal():
    coverage_start = date(2016, 1, 1)
    filings = _evenly_spaced(date(2018, 1, 1), 2000, 23)  # starts AFTER coverage_start
    client = FakeClient({778: _submissions(filings)})
    universe = _universe(_universe_row(778, coverage_start, im.CORPUS_WINDOW_END, True))
    problems = im.validate_universe(client, universe)

    hits = _checks(problems, "history_reaches_cutoff")
    assert len(hits) == 1 and hits[0].severity == "FATAL"
    assert hits[0].cik == 778


def test_delisted_member_is_info_not_fatal_and_current_member_is_fatal():
    # Last 10-Q 2019-05-01; member_to 2019-07-01 -> coverage_end 2020-08-04.
    member_to = date(2019, 7, 1)
    coverage_start = member_to - timedelta(days=730)
    coverage_end = member_to + timedelta(days=400)
    filings = _evenly_spaced(coverage_start, (date(2019, 5, 1) - coverage_start).days, 8)
    client = FakeClient({901: _submissions(filings)})

    former = _universe(_universe_row(901, coverage_start, coverage_end, False))
    problems = im.validate_universe(client, former)
    stopped = _checks(problems, "member_stopped_filing")
    assert len(stopped) == 1 and stopped[0].severity == "INFO"
    assert _checks(problems, "recent_activity_10k_10q") == []
    assert _fatals(problems) == []

    # Exactly the same filing history, but the member is still in the
    # universe at the last reconstitution date -> a stopped filer IS a FATAL.
    current = _universe(_universe_row(901, coverage_start, im.CORPUS_WINDOW_END, True))
    problems = im.validate_universe(client, current)
    stale = _checks(problems, "recent_activity_10k_10q")
    assert len(stale) == 1 and stale[0].severity == "FATAL"
    assert _checks(problems, "member_stopped_filing") == []


def _gap_problems(gap_days: int):
    coverage_start = date(2016, 1, 1)
    filings = [("10-Q", coverage_start + timedelta(days=91 * i)) for i in range(8)]
    last = filings[-1][1]
    filings += [("10-Q", last + timedelta(days=gap_days + 91 * i)) for i in range(8)]
    client = FakeClient({500: _submissions(filings)})
    universe = _universe(
        _universe_row(500, coverage_start, im.CORPUS_WINDOW_END, False)
    )
    return _checks(im.validate_universe(client, universe), "no_large_filing_gap")


def test_gap_of_200_days_is_warn_not_fatal():
    hits = _gap_problems(200)
    assert len(hits) == 1
    assert hits[0].severity == "WARN"
    assert "200-day gap" in hits[0].message


def test_gap_of_350_days_is_fatal():
    hits = _gap_problems(350)
    assert len(hits) == 1
    assert hits[0].severity == "FATAL"


def test_gap_below_threshold_is_clean():
    assert _gap_problems(120) == []


def _rate_problems(n_filings: int):
    """n periodic filings spread over exactly 10.0014 years, so the rate is
    n / 10.0014 -- 34 -> 3.40/yr, 36 -> 3.60/yr, 41 -> 4.10/yr."""
    coverage_start = date(2016, 1, 1)
    filings = _evenly_spaced(coverage_start, 3653, n_filings)
    client = FakeClient({600: _submissions(filings)})
    universe = _universe(
        _universe_row(600, coverage_start, im.CORPUS_WINDOW_END, False)
    )
    return _checks(im.validate_universe(client, universe), "plausible_filing_counts")


def test_filing_rate_below_fatal_floor():
    hits = _rate_problems(34)          # 3.40/yr
    assert len(hits) == 1 and hits[0].severity == "FATAL"
    assert "3.40/yr" in hits[0].message


def test_filing_rate_between_floors_is_warn():
    hits = _rate_problems(36)          # 3.60/yr
    assert len(hits) == 1 and hits[0].severity == "WARN"


def test_healthy_filing_rate_is_clean():
    assert _rate_problems(41) == []    # 4.10/yr


def test_zero_periodic_filings_in_window_is_fatal():
    coverage_start = date(2016, 1, 1)
    client = FakeClient({601: _submissions([("8-K", date(2017, 3, 1))])})
    universe = _universe(
        _universe_row(601, coverage_start, im.CORPUS_WINDOW_END, False)
    )
    hits = _checks(im.validate_universe(client, universe), "plausible_filing_counts")
    assert len(hits) == 1 and hits[0].severity == "FATAL"


def test_delisted_member_rate_is_measured_over_its_filed_span_not_its_window():
    """The regression this denominator exists for: a member that stopped
    filing at its exit date must not FATAL on filing rate for the 400-day
    empty tail of its own coverage window. Measured against the real
    universe, the naive window-length denominator FATALs 19 delisted
    members; the filed-span denominator FATALs none."""
    member_to = date(2017, 7, 1)
    coverage_start = im.CORPUS_WINDOW_START
    coverage_end = member_to + timedelta(days=400)
    last_filing = date(2016, 11, 1)   # acquired; stops filing well before exit
    filings = _evenly_spaced(coverage_start, (last_filing - coverage_start).days, 6)
    client = FakeClient({902: _submissions(filings)})
    universe = _universe(_universe_row(902, coverage_start, coverage_end, False))
    assert _checks(im.validate_universe(client, universe), "plausible_filing_counts") == []


def test_current_ticker_matches_check_is_gone_and_cik_map_contradiction_warns():
    coverage_start = date(2016, 1, 1)
    filings = _evenly_spaced(coverage_start, 3653, 41)
    # EDGAR says CIK 903 carries ticker "APC"; the bulk map says APC is a
    # different company (the reassigned-former-symbol trap).
    client = FakeClient(
        {903: _submissions(filings, tickers=["APC"])}, ticker_map={"APC": 2080921}
    )
    universe = _universe(
        _universe_row(903, coverage_start, im.CORPUS_WINDOW_END, False)
    )
    problems = im.validate_universe(client, universe)

    assert _checks(problems, "current_ticker_matches") == []
    hits = _checks(problems, "cik_map_agreement")
    assert len(hits) == 1 and hits[0].severity == "WARN"
    assert hits[0].ticker == "APC"

    # A ticker simply ABSENT from the bulk map (AEP/EA in the real file) is
    # never a contradiction.
    client2 = FakeClient({903: _submissions(filings, tickers=["AEP"])}, ticker_map={})
    assert _checks(im.validate_universe(client2, universe), "cik_map_agreement") == []


def test_staleness_is_measured_against_the_frozen_corpus_end_not_today():
    """Same fixture, same result, regardless of when the suite runs: the
    check compares to CORPUS_WINDOW_END."""
    coverage_start = date(2016, 1, 1)
    filings = _evenly_spaced(
        coverage_start, (im.CORPUS_WINDOW_END - timedelta(days=30) - coverage_start).days, 41
    )
    client = FakeClient({904: _submissions(filings)})
    universe = _universe(
        _universe_row(904, coverage_start, im.CORPUS_WINDOW_END, True)
    )
    problems = im.validate_universe(client, universe)
    assert _checks(problems, "recent_activity_10k_10q") == []
    assert _checks(problems, "recent_activity_any_form") == []


# ---------------------------------------------------------------------
# §3.2 -- the evidenced exceptions file
# ---------------------------------------------------------------------


HEADER = "cik,check_name,reason,effective_from,effective_to,evidence_filed,evidence,added\n"


def _write_exceptions(monkeypatch, tmp_path: Path, *rows: str) -> Path:
    """Write a synthetic exceptions file AND ratify exactly the (cik, check)
    pairs it names.

    The ratification is required by the code-side gate S7 red-team finding B17
    added (`RATIFIED_VALIDATION_EXCEPTIONS`), which these tests must exercise
    through, not around: a row alone is refused, by design. Ratifying only the
    pairs the test itself writes keeps the gate live for everything else.
    """
    p = tmp_path / "validation_exceptions.csv"
    p.write_text(HEADER + "".join(r if r.endswith("\n") else r + "\n" for r in rows))
    pairs = set()
    for r in rows:
        fields = r.split(",")
        if len(fields) >= 2 and fields[0].strip().isdigit():
            pairs.add((int(fields[0].strip()), fields[1].strip()))
    monkeypatch.setattr(im, "RATIFIED_VALIDATION_EXCEPTIONS",
                        im.RATIFIED_VALIDATION_EXCEPTIONS | pairs)
    return p


def test_shipped_exceptions_file_is_empty():
    # F2_SPEC §3.2: "Expected initial contents: empty."
    assert im.VALIDATION_EXCEPTIONS_PATH.exists()
    assert im.load_validation_exceptions() == []


def test_missing_exceptions_file_is_a_legitimate_empty_state(tmp_path: Path):
    assert im.load_validation_exceptions(tmp_path / "nope.csv") == []


def test_exception_downgrades_only_its_own_cik_and_check(monkeypatch, tmp_path: Path):
    path = _write_exceptions(
        monkeypatch, tmp_path,
        "111,recent_activity_10k_10q,reviewed_stopped_filer,,,,"
        "Form 25 filed 2019-08-01 (accession 0000000000-19-000001),2026-08-24",
    )
    exceptions = im.load_validation_exceptions(path)
    problems = [
        im.ValidationProblem(111, "recent_activity_10k_10q", "FATAL", "a"),
        im.ValidationProblem(222, "recent_activity_10k_10q", "FATAL", "b"),
        im.ValidationProblem(111, "history_reaches_cutoff", "FATAL", "c"),
        im.ValidationProblem(111, "no_large_filing_gap", "WARN", "d"),
    ]
    out, fired = im.apply_validation_exceptions(problems, exceptions)

    by = {(p.cik, p.check): p.severity for p in out}
    assert by[(111, "recent_activity_10k_10q")] == "WARN"   # downgraded
    assert by[(222, "recent_activity_10k_10q")] == "FATAL"  # other CIK untouched
    assert by[(111, "history_reaches_cutoff")] == "FATAL"   # other check untouched
    assert by[(111, "no_large_filing_gap")] == "WARN"       # never widened
    assert fired == {(111, "recent_activity_10k_10q")}
    downgraded = next(p for p in out if p.cik == 111 and p.check == "recent_activity_10k_10q")
    assert "DOWNGRADED from FATAL" in downgraded.message
    assert "Form 25 filed 2019-08-01" in downgraded.message


def test_dated_exception_with_non_public_evidence_is_rejected_at_load(monkeypatch, tmp_path: Path):
    path = _write_exceptions(
        monkeypatch, tmp_path,
        "111,recent_activity_10k_10q,hindsight,2020-01-01,,2020-06-01,"
        "evidence filed AFTER the date the exception bites,2026-08-24",
    )
    with pytest.raises(ValueError, match="POINT-IN-TIME VIOLATION"):
        im.load_validation_exceptions(path)


def test_dated_exception_without_evidence_date_is_rejected(monkeypatch, tmp_path: Path):
    path = _write_exceptions(
        monkeypatch, tmp_path,
        "111,recent_activity_10k_10q,undated_evidence,2020-01-01,,,"
        "no evidence_filed at all,2026-08-24",
    )
    with pytest.raises(ValueError, match="POINT-IN-TIME VIOLATION"):
        im.load_validation_exceptions(path)


def test_dated_exception_with_public_evidence_loads_and_scopes_by_vintage(monkeypatch, tmp_path: Path):
    path = _write_exceptions(
        monkeypatch, tmp_path,
        "111,recent_activity_10k_10q,reviewed,2020-01-01,2021-01-01,2019-06-01,"
        "Form 15-12B filed 2019-06-01,2026-08-24",
    )
    (ex,) = im.load_validation_exceptions(path)
    problems = [im.ValidationProblem(111, "recent_activity_10k_10q", "FATAL", "a")]

    inside, fired = im.apply_validation_exceptions(problems, [ex], as_of=date(2020, 6, 1))
    assert inside[0].severity == "WARN" and fired == {(111, "recent_activity_10k_10q")}

    outside, fired = im.apply_validation_exceptions(problems, [ex], as_of=date(2026, 8, 31))
    assert outside[0].severity == "FATAL" and fired == set()


def test_unknown_check_name_is_rejected(monkeypatch, tmp_path: Path):
    path = _write_exceptions(
        monkeypatch, tmp_path, "111,not_a_real_check,x,,,,evidence,2026-08-24"
    )
    with pytest.raises(ValueError, match="unknown check"):
        im.load_validation_exceptions(path)


def test_exception_without_evidence_is_rejected(monkeypatch, tmp_path: Path):
    path = _write_exceptions(monkeypatch, tmp_path, "111,recent_activity_10k_10q,reason,,,,,2026-08-24")
    with pytest.raises(ValueError, match="mandatory"):
        im.load_validation_exceptions(path)


def test_duplicate_exception_rows_are_rejected(monkeypatch, tmp_path: Path):
    path = _write_exceptions(
        monkeypatch, tmp_path,
        "111,recent_activity_10k_10q,a,,,,ev one,2026-08-24",
        "111,recent_activity_10k_10q,b,,,,ev two,2026-08-24",
    )
    with pytest.raises(ValueError, match="duplicate exception"):
        im.load_validation_exceptions(path)


def test_never_firing_exception_is_reported_dead(monkeypatch, tmp_path: Path, capsys):
    path = _write_exceptions(
        monkeypatch, tmp_path, "111,recent_activity_10k_10q,stale_row,,,,evidence,2026-08-24"
    )
    exceptions = im.load_validation_exceptions(path)
    out, fired = im.apply_validation_exceptions([], exceptions)
    assert out == [] and fired == set()
    im.print_exception_report(exceptions, fired, path)
    printed = capsys.readouterr().out
    assert "DEAD (never fired" in printed
    assert "stale_row" in printed


def test_fired_exception_is_still_printed(monkeypatch, tmp_path: Path, capsys):
    path = _write_exceptions(
        monkeypatch, tmp_path, "111,recent_activity_10k_10q,reviewed,,,,evidence,2026-08-24"
    )
    exceptions = im.load_validation_exceptions(path)
    _, fired = im.apply_validation_exceptions(
        [im.ValidationProblem(111, "recent_activity_10k_10q", "FATAL", "a")], exceptions
    )
    im.print_exception_report(exceptions, fired, path)
    printed = capsys.readouterr().out
    assert "FIRED" in printed
    assert "DEAD (never fired" not in printed


def test_allow_incomplete_universe_flag_is_gone():
    import inspect

    assert not hasattr(im, "parse_allow_incomplete_universe_arg")
    assert not hasattr(im, "ALL_FATAL_CHECK_NAMES")
    params = set(inspect.signature(im.run).parameters)
    assert "allow_incomplete_universe" not in params
    # `stage` and `max_age_hours` were added by S3 (F2_SPEC §4.3/§4.6); the
    # deleted blanket override must stay deleted.
    assert params == {
        "force_refresh", "db_path", "exceptions_path", "stage", "max_age_hours",
        "ex99_audit_path", "overrides_path",
    }
    # ...and its replacement only knows about FATAL-capable checks.
    # `ex99_sector_coverage` is S3's addition (F2_SPEC §4.4 item 5).
    assert im.FATAL_CHECK_NAMES == {
        "entity_resolves", "history_reaches_cutoff", "plausible_filing_counts",
        "no_large_filing_gap", "recent_activity_10k_10q", "earnings_doc_unresolved",
        "ex99_sector_coverage",
    }


# ---------------------------------------------------------------------
# §3.3 -- the write_validation_problems() gating bug
# ---------------------------------------------------------------------


def _fake_run(monkeypatch, tmp_path, filings, is_current=True, exceptions_path=None):
    """Drive run() end-to-end against a one-company synthetic universe with a
    fake client. Nothing here opens a socket."""
    cik = 4242
    coverage_start = date(2016, 1, 1)
    universe = _universe(
        _universe_row(cik, coverage_start, im.CORPUS_WINDOW_END, is_current)
    )
    spells = pd.DataFrame([{
        "cik": cik, "sector": "tech", "stratum": "core",
        "member_from": "2018-07-01", "member_to": "" if is_current else "2020-07-01",
    }])
    client = FakeClient({cik: _submissions(filings)})

    monkeypatch.setattr(im, "load_universe", lambda *a, **k: universe)
    monkeypatch.setattr(im, "load_membership", lambda *a, **k: spells)
    monkeypatch.setattr(im, "EdgarClient", lambda *a, **k: client)

    db = tmp_path / "e2.db"
    im.run(
        db_path=db,
        exceptions_path=exceptions_path or (tmp_path / "no_such_exceptions.csv"),
        # S3's EX-99 audit artifact goes to tmp: a test must never overwrite
        # the real data/f2/ex99_selection_audit.csv. The overrides file is
        # routed to a nonexistent tmp path so these tests stay hermetic.
        ex99_audit_path=tmp_path / "ex99_selection_audit.csv",
        overrides_path=tmp_path / "no_such_overrides.csv",
    )
    return db, cik


def _problem_rows(db: Path):
    conn = sqlite3.connect(db)
    rows = conn.execute(
        "SELECT cik, stage, check_name, severity FROM universe_validation_problems"
    ).fetchall()
    conn.close()
    return rows


def test_validation_problems_are_persisted_with_no_exceptions_file(monkeypatch, tmp_path):
    """THE §3.3 REGRESSION. E1 wrote the problems table only when
    `--allow-incomplete-universe` happened to be passed, so an ordinary run's
    findings were printed and thrown away. They must now always persist."""
    coverage_start = date(2016, 1, 1)
    # A former member that stopped filing in 2019: no FATAL, so the run
    # COMPLETES -- and its one INFO finding must still be on disk afterwards.
    filings = _evenly_spaced(coverage_start, (date(2019, 1, 1) - coverage_start).days, 13)
    db, cik = _fake_run(monkeypatch, tmp_path, filings, is_current=False)

    rows = _problem_rows(db)
    assert rows, "validation findings were not persisted on a normal run"
    assert {r[1] for r in rows} == {"metadata"}
    member_rows = [r for r in rows if r[0] == cik]
    assert {r[2] for r in member_rows} == {"member_stopped_filing"}
    assert {r[3] for r in member_rows} == {"INFO"}
    # S3 also persists its post-ingestion EX-99 findings in the same
    # (run_date, stage) slice; this synthetic company files no earnings 8-K,
    # so its sector legitimately reports one run-scoped WARN.
    other = [r for r in rows if r[0] != cik]
    assert {(r[0], r[2], r[3]) for r in other} <= {
        (im.RUN_SCOPE_CIK, "ex99_sector_coverage", "WARN")
    }


def test_validation_problems_are_persisted_even_when_the_run_hard_fails(monkeypatch, tmp_path):
    coverage_start = date(2016, 1, 1)
    filings = _evenly_spaced(coverage_start, (date(2019, 1, 1) - coverage_start).days, 13)
    with pytest.raises(SystemExit) as exc:
        _fake_run(monkeypatch, tmp_path, filings, is_current=True)
    assert exc.value.code == 1

    db = tmp_path / "e2.db"
    rows = _problem_rows(db)
    assert any(r[3] == "FATAL" for r in rows), (
        "a hard-failing run must still leave its findings on disk"
    )


def test_run_writes_membership_and_companies(monkeypatch, tmp_path):
    coverage_start = date(2016, 1, 1)
    filings = _evenly_spaced(coverage_start, (date(2026, 8, 1) - coverage_start).days, 43)
    db, cik = _fake_run(monkeypatch, tmp_path, filings)

    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM universe_membership").fetchone()[0] == 1
    company = conn.execute(
        "SELECT cik, ticker, stratum, coverage_start, coverage_end, is_current_member "
        "FROM companies"
    ).fetchone()
    assert company == (cik, None, "core", "2016-01-01", "2026-08-31", 1)
    n_filings, max_date = conn.execute(
        "SELECT COUNT(*), MAX(filing_date) FROM filings"
    ).fetchone()
    assert n_filings == 43
    assert max_date <= im.CORPUS_WINDOW_END.isoformat()
    # Every filing row is CIK-keyed with a NULL, informational ticker.
    assert conn.execute("SELECT COUNT(*) FROM filings WHERE ticker IS NOT NULL").fetchone()[0] == 0
    conn.close()


def test_run_refuses_to_write_e1s_frozen_database():
    with pytest.raises(ValueError, match="frozen record"):
        im.run(db_path=im.E1_DB_PATH)


def test_e2_db_is_a_different_file_from_e1s():
    assert im.DB_PATH.name == "filings_metadata_e2.db"
    assert im.E1_DB_PATH.name == "filings_metadata.db"
    assert im.DB_PATH != im.E1_DB_PATH


# ---------------------------------------------------------------------
# extract_target_filings() -- both window bounds are enforced
# ---------------------------------------------------------------------


def test_extract_target_filings_respects_both_bounds():
    recent = _recent([
        ("10-K", date(2015, 1, 1)),   # before start
        ("10-Q", date(2016, 5, 1)),   # in
        ("8-K", date(2020, 1, 1)),    # in
        ("10-Q", date(2027, 1, 1)),   # after end
        ("DEF 14A", date(2018, 1, 1)),  # not a target form
    ])
    out = im.extract_target_filings(recent, date(2016, 1, 1), date(2026, 8, 31))
    assert [f["form"] for f in out] == ["10-Q", "8-K"]
    assert "ticker" not in out[0]


def test_extract_target_filings_flags_earnings_items_exactly():
    recent = _recent(
        [("8-K", date(2020, 1, 1)), ("8-K", date(2020, 2, 1))],
        items={0: "2.02,9.01", 1: "8.01"},
    )
    out = im.extract_target_filings(recent, date(2016, 1, 1), date(2026, 8, 31))
    assert [f["has_earnings_item"] for f in out] == [True, False]


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
