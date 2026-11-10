"""Tests for data/f5/census_split_lookahead.py: synthetic event detection and the
later-factor rule, plus (when the real artifacts are on disk) JSON == fresh run."""
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "census_split_lookahead", ROOT / "data" / "f5" / "census_split_lookahead.py")
CS = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(CS)


def _shares(cik, pairs):
    return pd.DataFrame({"cik": cik, "filing_date": pd.to_datetime([d for d, _ in pairs]),
                         "shares_used": [s for _, s in pairs]})


def _rows(cik, dates):
    return pd.DataFrame({"cik": cik, "filing_date": pd.to_datetime(dates)})


def test_forward_split_is_detected_and_earlier_rows_are_flagged():
    s = _shares(1, [("2020-01-30", 100.0), ("2020-04-30", 101.0), ("2020-10-30", 404.0),
                    ("2021-01-30", 405.0)])
    ev = CS.detect_events(s)
    assert ev.filing_date.dt.strftime("%Y-%m-%d").tolist() == ["2020-10-30"]
    assert ev.ratio.iloc[0] == pytest.approx(4.0)
    hit = CS.before_later_event(_rows(1, ["2020-01-30", "2020-04-30", "2020-10-30",
                                          "2021-01-30"]), ev)
    # the event's own filing date already shows the new count: not before it
    assert hit.tolist() == [True, True, False, False]


def test_reverse_split_is_detected():
    s = _shares(2, [("2020-01-30", 1000.0), ("2020-04-30", 100.0)])
    ev = CS.detect_events(s)
    assert len(ev) == 1 and ev.ratio.iloc[0] == pytest.approx(0.1)
    assert CS.before_later_event(_rows(2, ["2020-01-30"]), ev).tolist() == [True]


def test_two_splits_multiply_and_cancelling_events_do_not_count():
    s = _shares(3, [("2019-01-01", 10.0), ("2020-01-01", 40.0), ("2021-01-01", 400.0)])
    ev = CS.detect_events(s)
    assert len(ev) == 2
    assert CS.later_factor(ev, 3, pd.Timestamp("2019-01-01")) == pytest.approx(40.0)
    assert CS.later_factor(ev, 3, pd.Timestamp("2020-06-01")) == pytest.approx(10.0)
    back = _shares(4, [("2019-01-01", 10.0), ("2020-01-01", 40.0), ("2021-01-01", 10.0)])
    ev2 = CS.detect_events(back)
    assert len(ev2) == 2
    assert CS.before_later_event(_rows(4, ["2019-01-01"]), ev2).tolist() == [False]
    assert CS.before_later_event(_rows(4, ["2020-06-01"]), ev2).tolist() == [True]


def test_a_row_after_the_last_split_and_small_moves_are_not_counted():
    s = _shares(5, [("2020-01-01", 100.0), ("2020-06-01", 170.0), ("2021-01-01", 400.0)])
    ev = CS.detect_events(s)  # 1.7x is below the threshold; 400/170 = 2.35 is an event
    assert ev.filing_date.dt.strftime("%Y-%m-%d").tolist() == ["2021-01-01"]
    assert CS.before_later_event(_rows(5, ["2021-06-01"]), ev).tolist() == [False]
    assert CS.before_later_event(_rows(6, ["2019-01-01"]), ev).tolist() == [False]  # other cik


def test_shares_as_used_inverts_book_to_market():
    nf = pd.DataFrame({"cik": [1, 1], "filing_date": pd.to_datetime(["2020-01-30"] * 2),
                       "pre_session": pd.to_datetime(["2020-01-29"] * 2),
                       "book_to_market": [0.5, 0.25], "equity_to_assets": [0.5, 0.5],
                       "log_total_assets": [0.0, 0.0]})
    px = pd.DataFrame({"cik": [1], "date": pd.to_datetime(["2020-01-29"]), "close": [2.0]})
    out = CS.shares_as_used(nf, px)
    # equity 0.5; shares = 0.5 / bm / 2 -> 0.5 and 1.0; median 0.75
    assert out.shares_used.tolist() == [pytest.approx(0.75)]


REAL = all(p.exists() for p in (CS.NUMERIC, CS.PRICES, CS.OOF, CS.OUT))


@pytest.mark.skipif(not REAL, reason="real parquet artifacts or the census JSON not on disk")
def test_the_tracked_json_equals_a_fresh_computation():
    assert json.loads(CS.OUT.read_text()) == CS.census()


def test_the_tracked_json_holds_no_call_outcome_or_hit_rate():
    if not CS.OUT.exists():
        pytest.skip("census JSON not on disk")
    text = CS.OUT.read_text().lower()
    for word in ("hit_rate", "correct", "outperform", "underperform", "excess", "\"call"):
        assert word not in text
