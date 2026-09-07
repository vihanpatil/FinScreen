"""
test_controls.py -- offline tests for `controls.py` (H1 positive controls).

No network. Every fixture is synthetic and built in-memory except the two
corpus tripwires at the bottom, which read the FROZEN local artifacts
read-only and pin the measured population so a silent corpus change is
caught rather than absorbed.

The tests that matter most are the leakage ones: `resolve_sessions` and
`build_sue` are the two places where a point-in-time mistake would be
invisible in the headline numbers.

Run: python3 -m pytest test_controls.py -q
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import backtest as B
import controls as C


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Mon 2020-01-06 .. Fri 2020-01-10, then Mon 2020-01-13 .. Fri 2020-01-17
CALENDAR = pd.DatetimeIndex(
    ["2020-01-06", "2020-01-07", "2020-01-08", "2020-01-09", "2020-01-10",
     "2020-01-13", "2020-01-14", "2020-01-15", "2020-01-16", "2020-01-17"]
)


def _events(rows):
    df = pd.DataFrame(rows)
    df["filing_date"] = pd.to_datetime(df["filing_date"])
    return df


# ---------------------------------------------------------------------------
# Session alignment / post-close acceptance handling
# ---------------------------------------------------------------------------


def test_pre_close_filing_reacts_on_the_same_session():
    ev = _events([{"cik": 1, "filing_date": "2020-01-08",
                   "acceptance_datetime": "2020-01-08T15:00:00.000Z"}])  # 10:00 ET
    out = C.resolve_sessions(ev, CALENDAR)
    assert not bool(out.loc[0, "post_close"])
    assert CALENDAR[int(out.loc[0, "news_pos"])] == pd.Timestamp("2020-01-08")
    assert CALENDAR[int(out.loc[0, "pre_pos"])] == pd.Timestamp("2020-01-07")


def test_post_close_filing_reacts_on_the_next_session():
    # 21:30 UTC = 16:30 ET -- after the close.
    ev = _events([{"cik": 1, "filing_date": "2020-01-08",
                   "acceptance_datetime": "2020-01-08T21:30:00.000Z"}])
    out = C.resolve_sessions(ev, CALENDAR)
    assert bool(out.loc[0, "post_close"])
    assert CALENDAR[int(out.loc[0, "news_pos"])] == pd.Timestamp("2020-01-09")
    assert CALENDAR[int(out.loc[0, "pre_pos"])] == pd.Timestamp("2020-01-08")


def test_post_close_friday_rolls_over_the_weekend():
    ev = _events([{"cik": 1, "filing_date": "2020-01-10",
                   "acceptance_datetime": "2020-01-10T21:05:00.000Z"}])
    out = C.resolve_sessions(ev, CALENDAR)
    assert CALENDAR[int(out.loc[0, "news_pos"])] == pd.Timestamp("2020-01-13")


def test_non_trading_day_filing_rolls_forward_without_post_close():
    # Saturday 2020-01-11, 10:00 ET -- not post-close, but no session that day.
    ev = _events([{"cik": 1, "filing_date": "2020-01-11",
                   "acceptance_datetime": "2020-01-11T15:00:00.000Z"}])
    out = C.resolve_sessions(ev, CALENDAR)
    assert CALENDAR[int(out.loc[0, "news_pos"])] == pd.Timestamp("2020-01-13")


def test_acceptance_after_filing_date_wins_the_salesforce_case():
    """`data/F2_INGESTION_REPORT.md` §3.3: two Salesforce filings whose
    filing_date precedes acceptance by 344 and 633 days. The bytes were not
    public on the filing_date, so info_date must follow acceptance."""
    ev = _events([{"cik": 1, "filing_date": "2018-06-01",
                   "acceptance_datetime": "2020-01-08T15:00:00.000Z"}])
    out = C.resolve_sessions(ev, CALENDAR)
    assert out.loc[0, "info_date"] == pd.Timestamp("2020-01-08")
    assert CALENDAR[int(out.loc[0, "news_pos"])] == pd.Timestamp("2020-01-08")


def test_filing_date_after_acceptance_date_wins_too():
    ev = _events([{"cik": 1, "filing_date": "2020-01-09",
                   "acceptance_datetime": "2020-01-07T15:00:00.000Z"}])
    out = C.resolve_sessions(ev, CALENDAR)
    assert out.loc[0, "info_date"] == pd.Timestamp("2020-01-09")


def test_event_before_the_calendar_gets_no_session_rather_than_position_zero():
    """A news session at position 0 has no pre-session, so it must be
    rejected -- never silently evaluated against a missing prior close."""
    ev = _events([{"cik": 1, "filing_date": "2020-01-06",
                   "acceptance_datetime": "2020-01-06T15:00:00.000Z"}])
    out = C.resolve_sessions(ev, CALENDAR)
    assert int(out.loc[0, "news_pos"]) == -1


# ---------------------------------------------------------------------------
# Benchmark: excludes self, membership-dated, censoring counted not imputed
# ---------------------------------------------------------------------------


def _price_fixture():
    prices = pd.DataFrame(
        {10: [100.0, 110.0], 20: [100.0, 120.0], 30: [100.0, 140.0],
         40: [100.0, np.nan]},
        index=CALENDAR[:2],
    )
    return prices


def test_benchmark_excludes_self():
    prices = _price_fixture()
    member = pd.DataFrame(True, index=prices.index, columns=prices.columns)
    arr = C.align_membership(member, prices.columns)
    subj, bench, used, missing = C.excess_return(
        prices.to_numpy(dtype=float), {c: i for i, c in enumerate(prices.columns)},
        arr, 10, 0, 1, 1)
    assert subj == pytest.approx(0.10)
    # peers 20 (+0.20) and 30 (+0.40); 40 has no end price.
    assert bench == pytest.approx(0.30)
    assert used == 2 and missing == 1


def test_benchmark_is_membership_dated():
    prices = _price_fixture()
    member = pd.DataFrame(True, index=prices.index, columns=prices.columns)
    member.loc[:, 30] = False  # 30 is not a member on this session
    arr = C.align_membership(member, prices.columns)
    _, bench, used, _ = C.excess_return(
        prices.to_numpy(dtype=float), {c: i for i, c in enumerate(prices.columns)},
        arr, 10, 0, 1, 1)
    assert bench == pytest.approx(0.20)
    assert used == 1


def test_member_without_price_coverage_is_counted_not_imputed():
    prices = _price_fixture()
    member = pd.DataFrame(True, index=prices.index, columns=prices.columns)
    arr = C.align_membership(member, prices.columns)
    _, bench, used, missing = C.excess_return(
        prices.to_numpy(dtype=float), {c: i for i, c in enumerate(prices.columns)},
        arr, 10, 0, 1, 1)
    assert missing == 1
    # A 0% return for CIK 40 would drag the benchmark to 0.20; it must not.
    assert bench == pytest.approx(0.30)


def test_price_matrix_does_not_forward_fill_past_a_ciks_last_observation(tmp_path):
    """`features.py::_asof_price` would return the last known price forever,
    contributing a fabricated 0% return for a delisted name. This matrix
    must go NaN instead."""
    dates = pd.date_range("2020-01-06", periods=6, freq="B")
    rows = []
    for i, d in enumerate(dates):
        for cik in range(1, 61):  # >= 50 CIKs per session so the guard passes
            if cik == 1 and i >= 3:
                continue  # CIK 1 delists after the third session
            rows.append({"cik": cik, "date": d, "close": 100.0 + i})
    path = tmp_path / "p.parquet"
    pd.DataFrame(rows).to_parquet(path)
    wide = C.load_price_matrix(path, min_date="2019-01-01")
    assert np.isfinite(wide.iloc[2][1])
    assert not np.isfinite(wide.iloc[3][1])
    assert not np.isfinite(wide.iloc[5][1])


def test_price_matrix_rejects_a_thin_pseudo_session(tmp_path):
    dates = pd.date_range("2020-01-06", periods=3, freq="B")
    rows = [{"cik": c, "date": d, "close": 100.0}
            for d in dates for c in range(1, 61)]
    rows.append({"cik": 999, "date": pd.Timestamp("2020-01-11"), "close": 5.0})
    path = tmp_path / "p.parquet"
    pd.DataFrame(rows).to_parquet(path)
    with pytest.raises(AssertionError, match="market sessions"):
        C.load_price_matrix(path, min_date="2019-01-01")


# ---------------------------------------------------------------------------
# SUE: seasonal-difference algebra and the point-in-time rules
# ---------------------------------------------------------------------------


def _eps_series(cik=1, n=16, start="2016-03-31", filed_lag_days=30,
                values=None):
    ends = pd.date_range(start, periods=n, freq="QE")
    vals = values if values is not None else [1.0 + 0.1 * i for i in range(n)]
    return pd.DataFrame({
        "cik": cik,
        "period_end": ends,
        "eps": vals,
        "first_filed": ends + pd.Timedelta(days=filed_lag_days),
        "concept": "EarningsPerShareDiluted",
    })


def test_sue_matches_the_hand_computed_seasonal_random_walk():
    # EPS rises by exactly 0.1 per quarter => every seasonal difference is
    # 0.4, so the trailing sd is 0 and SUE is undefined. Perturb the newest
    # quarter so the numerator differs from the (now non-zero) scale.
    vals = [1.0 + 0.1 * i for i in range(16)]
    vals[15] = vals[11] + 1.0                       # newest seasonal diff = 1.0
    vals[14] = vals[10] + 0.5                       # give the scaler variance
    eps = _eps_series(values=vals)
    ev = pd.DataFrame([{"cik": 1, "info_date": eps["period_end"].iloc[15]
                        + pd.Timedelta(days=20), "stratum": "core"}])
    out = C.build_sue(ev, eps)
    diffs = []
    for i in range(4, 15):
        diffs.append(vals[i] - vals[i - 4])
    trailing = diffs[-C.MAX_TRAILING:]
    expected = 1.0 / float(np.std(trailing, ddof=1))
    assert out.loc[0, "sue"] == pytest.approx(expected)
    assert out.loc[0, "sue_n_trailing"] == C.MAX_TRAILING


def test_sue_requires_the_year_ago_quarter_to_be_public_before_the_event():
    vals = [1.0 + 0.1 * i for i in range(16)]
    vals[15] = vals[11] + 1.0
    vals[14] = vals[10] + 0.5
    eps = _eps_series(values=vals)
    # Push the q-4 quarter's first_filed to AFTER the event date.
    ev_date = eps["period_end"].iloc[15] + pd.Timedelta(days=20)
    eps.loc[11, "first_filed"] = ev_date + pd.Timedelta(days=1)
    ev = pd.DataFrame([{"cik": 1, "info_date": ev_date, "stratum": "core"}])
    out = C.build_sue(ev, eps)
    assert np.isnan(out.loc[0, "sue"])


def test_sue_scaler_ignores_quarters_filed_after_the_event():
    vals = [1.0 + 0.1 * i for i in range(16)]
    vals[15] = vals[11] + 1.0
    vals[14] = vals[10] + 0.5
    eps = _eps_series(values=vals)
    ev_date = eps["period_end"].iloc[15] + pd.Timedelta(days=20)
    full = C.build_sue(pd.DataFrame([{"cik": 1, "info_date": ev_date,
                                      "stratum": "core"}]), eps)
    assert full.loc[0, "sue_n_trailing"] == C.MAX_TRAILING
    # Make five trailing quarters invisible as of the event date (never the
    # q-4 counterpart at index 11, which would kill the numerator instead).
    # The remaining trailing count must drop, proving the filter bites.
    for i in (9, 10, 12, 13, 14):
        eps.loc[i, "first_filed"] = ev_date + pd.Timedelta(days=5)
    trimmed = C.build_sue(pd.DataFrame([{"cik": 1, "info_date": ev_date,
                                         "stratum": "core"}]), eps)
    assert full.loc[0, "sue_n_trailing"] > trimmed.loc[0, "sue_n_trailing"]


def test_sue_is_nan_without_enough_trailing_history():
    eps = _eps_series(n=8)
    ev = pd.DataFrame([{"cik": 1, "info_date": eps["period_end"].iloc[7]
                        + pd.Timedelta(days=20), "stratum": "core"}])
    out = C.build_sue(ev, eps)
    assert np.isnan(out.loc[0, "sue"])


def test_sue_never_uses_a_quarter_ending_on_or_after_the_event_date():
    vals = [1.0 + 0.1 * i for i in range(16)]
    vals[15] = vals[11] + 1.0
    vals[14] = vals[10] + 0.5
    eps = _eps_series(values=vals)
    # Event dated 5 days after the newest period_end: SPEC's window is
    # [event-120d, event-5d], so that quarter is exactly excluded and the
    # match falls back to the prior one.
    ev_date = eps["period_end"].iloc[15] + pd.Timedelta(days=4)
    out = C.build_sue(pd.DataFrame([{"cik": 1, "info_date": ev_date,
                                     "stratum": "core"}]), eps)
    assert out.loc[0, "sue_period_end"] < ev_date


def test_seasonal_lag_match_rejects_a_gap_outside_the_window():
    eps = _eps_series(n=16)
    eps = eps.drop(index=[8, 9, 10, 11]).reset_index(drop=True)  # remove a year
    out = C._seasonal_diffs(eps)
    # The four newest rows now have no counterpart 320-410 days back.
    assert out["eps_lag4"].tail(4).isna().all()


# ---------------------------------------------------------------------------
# Leakage assertions
# ---------------------------------------------------------------------------


def _panel_stub():
    return pd.DataFrame([{
        "cik": 1, "post_close": False,
        "info_date": pd.Timestamp("2020-01-08"),
        "news_date": pd.Timestamp("2020-01-08"),
        "entry_date": pd.Timestamp("2020-01-09"),
        "sue": 1.0, "sue_period_end": pd.Timestamp("2019-12-31"),
    }])


def test_assert_no_lookahead_accepts_a_clean_panel():
    C.assert_no_lookahead(_panel_stub())


def test_assert_no_lookahead_rejects_a_news_session_before_the_info_date():
    p = _panel_stub()
    p.loc[0, "news_date"] = pd.Timestamp("2020-01-07")
    with pytest.raises(AssertionError, match="news_date < info_date"):
        C.assert_no_lookahead(p)


def test_assert_no_lookahead_rejects_an_unapplied_post_close_correction():
    p = _panel_stub()
    p.loc[0, "post_close"] = True
    with pytest.raises(AssertionError, match="post-close"):
        C.assert_no_lookahead(p)


def test_assert_no_lookahead_rejects_a_forward_window_opening_too_early():
    p = _panel_stub()
    p.loc[0, "entry_date"] = pd.Timestamp("2020-01-08")
    with pytest.raises(AssertionError, match="entry_date <= news_date"):
        C.assert_no_lookahead(p)


def test_assert_no_lookahead_rejects_a_fiscal_quarter_ending_after_the_event():
    p = _panel_stub()
    p.loc[0, "sue_period_end"] = pd.Timestamp("2020-01-09")
    with pytest.raises(AssertionError, match="fiscal quarter"):
        C.assert_no_lookahead(p)


# ---------------------------------------------------------------------------
# Dedup, IC machinery, placebo, verdicts
# ---------------------------------------------------------------------------


def test_dedup_is_the_shipped_rule_form_aware():
    df = pd.DataFrame({
        "ticker": ["1", "1", "2"],
        "filing_date": pd.to_datetime(["2020-01-06", "2020-01-06", "2020-01-06"]),
        "form": ["8-K", "10-Q", "8-K"],
        "accession_number": ["9999-99-999999", "0000-00-000001", "z"],
    })
    keep = B.company_quarter_dedup_keep_mask(df)
    # Same-day tie: the 10-Q wins despite the smaller accession number.
    assert list(keep) == [False, True, True]


def test_per_period_ic_recovers_a_perfect_monotone_relation():
    n = 30
    df = pd.DataFrame({
        "sig": np.arange(n, dtype=float),
        "tgt": np.arange(n, dtype=float) ** 3,
        "period": ["2020Q1"] * n,
    })
    out = C.per_period_ic(df, "sig", "tgt", "period")
    assert len(out) == 1
    assert out.loc[0, "ic"] == pytest.approx(1.0)


def test_per_period_ic_drops_thin_periods():
    df = pd.DataFrame({
        "sig": np.arange(5, dtype=float),
        "tgt": np.arange(5, dtype=float),
        "period": ["2020Q1"] * 5,
    })
    assert len(C.per_period_ic(df, "sig", "tgt", "period")) == 0


def test_summarize_ic_uses_the_sample_sd_not_the_population_sd():
    ic_df = pd.DataFrame({"period": ["a", "b", "c"], "n": [10, 10, 10],
                          "ic": [0.0, 0.1, 0.2], "p": [1.0, 1.0, 1.0]})
    df = pd.DataFrame({"sig": [1.0, 2.0, 3.0], "tgt": [1.0, 2.0, 3.0]})
    s = C.summarize_ic(ic_df, df, "sig", "tgt")
    assert s["sd_ic_ddof1"] == pytest.approx(np.std([0.0, 0.1, 0.2], ddof=1))
    assert s["sd_ic_ddof1"] != pytest.approx(np.std([0.0, 0.1, 0.2], ddof=0))
    assert s["se_ic"] == pytest.approx(s["sd_ic_ddof1"] / np.sqrt(3))
    assert s["frac_periods_positive"] == pytest.approx(2 / 3)


def test_placebo_is_deterministic_and_uniform():
    ciks = [1, 2, 3, 1]
    dates = ["2020-01-06", "2020-01-06", "2020-01-06", "2020-01-07"]
    a = C.placebo_signal(ciks, dates)
    b = C.placebo_signal(ciks, dates)
    assert np.array_equal(a, b)
    assert ((a >= 0) & (a < 1)).all()
    assert len(set(a)) == 4


def test_verdict_thresholds_match_the_declared_spec():
    assert C.verdict_t1({"n_periods": 40, "mean_ic": 0.08, "t_stat": 4.1,
                         "frac_periods_positive": 0.8}) == "PASS"
    assert C.verdict_t1({"n_periods": 40, "mean_ic": 0.08, "t_stat": 3.9,
                         "frac_periods_positive": 0.8}) == "FAIL"
    assert C.verdict_t1({"n_periods": 40, "mean_ic": 0.08, "t_stat": 4.1,
                         "frac_periods_positive": 0.7}) == "FAIL"
    assert C.verdict_t2({"n_periods": 40, "mean_ic": 0.05, "t_stat": 2.1}) == "PASS"
    assert C.verdict_t2({"n_periods": 40, "mean_ic": 0.05, "t_stat": 1.2}) == "AMBIGUOUS"
    assert C.verdict_t2({"n_periods": 40, "mean_ic": -0.05, "t_stat": -2.5}) == "FAIL"
    assert C.verdict_t0({"n_periods": 40, "mean_ic": 0.005, "t_stat": 0.3}) == "PASS"
    assert C.verdict_t0({"n_periods": 40, "mean_ic": 0.05, "t_stat": 2.5}) == "FAIL"
    assert C.tripwire({"n_periods": 40, "mean_ic": 0.2})
    assert not C.tripwire({"n_periods": 40, "mean_ic": 0.1})


def test_mde_is_2_8_times_the_standard_error():
    assert C.mde_from_se(0.02) == pytest.approx(0.056)
    assert C.mde_from_se(None) is None


# ---------------------------------------------------------------------------
# Frozen-corpus tripwires (local files only, read-only, no network)
# ---------------------------------------------------------------------------


def test_event_population_is_the_measured_5552():
    """Pins the population the lens report measured. If this moves, the
    controls' numbers describe a different corpus and must be re-run."""
    ev = C.load_earnings_events()
    assert len(ev) == 5903
    priced = pd.read_parquet(C.PRICES_PATH, columns=["cik"])["cik"].unique()
    assert int(ev["cik"].isin(set(priced)).sum()) == 5552


def test_membership_spells_are_the_measured_299():
    m = C.load_membership()
    assert len(m) == 299
    assert m["cik"].nunique() == 244
    assert set(m["stratum"].unique()) == {"core", "extension"}
