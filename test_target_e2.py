"""
test_target_e2.py -- tests for the F5 Step 1A forward excess-return target.

Two layers:
  * SYNTHETIC fixtures with hand-computable prices, where every PIT rule the
    target depends on is checked against an arithmetic answer rather than
    against itself;
  * ONE real-data smoke over <= 300 real core-stratum filings (deterministic
    stride sample, time-ordered -- never a shuffle), which re-derives the
    ex-self benchmark by hand for a few rows and re-checks the invariants on
    real dates.

Nothing here computes an information coefficient, a correlation, or any
feature-versus-outcome association (the E2 freeze, `F5_PLAN.md` §1); one test
enforces that by scanning the module source.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import controls as C
import target_e2 as T

# ---------------------------------------------------------------------------
# Synthetic fixture: a small clean market
# ---------------------------------------------------------------------------

SUBJECT = 10
PEER_UP = 20
PEER_DOWN = 30
PEER_UNPRICED = 40
ALL_CIKS = [SUBJECT, PEER_UP, PEER_DOWN, PEER_UNPRICED]


@pytest.fixture()
def calendar() -> pd.DatetimeIndex:
    # 120 "sessions"; business days are only a stand-in calendar -- the code
    # under test never assumes anything about spacing.
    return pd.DatetimeIndex(pd.bdate_range("2020-01-02", periods=120))


@pytest.fixture()
def prices(calendar) -> pd.DataFrame:
    return pd.DataFrame(100.0, index=calendar, columns=ALL_CIKS)


@pytest.fixture()
def spells() -> pd.DataFrame:
    """Core spells covering the whole synthetic calendar."""
    return pd.DataFrame({
        "cik": ALL_CIKS,
        "sector": "test",
        "stratum": "core",
        "member_from": pd.Timestamp("2019-01-01"),
        "member_to": pd.Timestamp("2200-01-01"),
    })


@pytest.fixture()
def member_mat(spells, calendar) -> pd.DataFrame:
    return C.build_membership_matrix(spells, calendar)


def filing(cik: int, filing_date: str, acceptance: str,
           accession: str = "0000000000-00-000000") -> pd.DataFrame:
    return pd.DataFrame({
        "accession_number": [accession],
        "cik": [cik],
        "form": ["8-K"],
        "filing_date": [pd.Timestamp(filing_date)],
        "acceptance_datetime": [acceptance],
    })


def build(filings, prices, member_mat, spells, holding=T.HOLDING_SESSIONS):
    return T.build_targets(filings, prices, member_mat, spells,
                           holding_sessions=holding)


# ---------------------------------------------------------------------------
# 1. Event dating: post-close and the filing_date-precedes-acceptance anomaly
# ---------------------------------------------------------------------------


def test_post_close_pushes_the_window_one_session(prices, member_mat, spells,
                                                  calendar):
    # Same filing_date; 15:00 ET vs 16:00 ET acceptance (January => EST).
    pre = filing(SUBJECT, "2020-01-08", "2020-01-08T20:00:00.000Z", "A")
    post = filing(SUBJECT, "2020-01-08", "2020-01-08T21:00:00.000Z", "B")
    both = pd.concat([pre, post], ignore_index=True)
    t = build(both, prices, member_mat, spells).set_index("accession_number")

    assert bool(t.loc["A", "post_close"]) is False
    assert bool(t.loc["B", "post_close"]) is True
    # Pre-close reacts on the filing session itself; post-close on the next.
    assert t.loc["A", "news_session"] == pd.Timestamp("2020-01-08")
    assert t.loc["B", "news_session"] == pd.Timestamp("2020-01-09")
    gap = (calendar.get_loc(t.loc["B", "window_open_session"])
           - calendar.get_loc(t.loc["A", "window_open_session"]))
    assert gap == 1


def test_filing_date_before_acceptance_uses_acceptance(prices, member_mat,
                                                       spells):
    """The Salesforce family: bytes were not public on the filing_date."""
    late = filing(SUBJECT, "2020-01-06", "2020-03-02T17:00:00.000Z", "LATE")
    t = build(late, prices, member_mat, spells).iloc[0]
    assert t["info_date"] == pd.Timestamp("2020-03-02")       # not 2020-01-06
    assert t["info_date"] > t["filing_date"]
    assert t["news_session"] >= pd.Timestamp("2020-03-02")
    assert t["window_open_session"] > pd.Timestamp("2020-03-02")


def test_no_window_opens_on_or_before_info_date(prices, member_mat, spells):
    rows = pd.concat([
        filing(SUBJECT, "2020-01-08", "2020-01-08T14:30:00.000Z", "A"),   # pre
        filing(SUBJECT, "2020-01-08", "2020-01-08T23:30:00.000Z", "B"),   # post
        filing(SUBJECT, "2020-01-04", "2020-01-04T14:30:00.000Z", "C"),   # Sat
        filing(SUBJECT, "2020-01-06", "2020-03-02T17:00:00.000Z", "D"),   # late
    ], ignore_index=True)
    t = build(rows, prices, member_mat, spells)
    assert len(t) == 4
    assert (t["window_open_session"] > t["info_date"]).all()
    assert (t["window_open_session"] > t["news_session"]).all()


def test_membership_flag_is_half_open(prices, member_mat, calendar):
    spells = pd.DataFrame({
        "cik": [SUBJECT], "sector": ["test"], "stratum": ["core"],
        "member_from": [pd.Timestamp("2020-01-01")],
        "member_to": [pd.Timestamp("2020-02-03")],
    })
    rows = pd.concat([
        filing(SUBJECT, "2020-01-31", "2020-01-31T14:30:00.000Z", "IN"),
        filing(SUBJECT, "2020-02-03", "2020-02-03T14:30:00.000Z", "EDGE"),
        filing(SUBJECT, "2020-02-04", "2020-02-04T14:30:00.000Z", "OUT"),
    ], ignore_index=True)
    t = build(rows, prices, member_mat, spells).set_index("accession_number")
    assert bool(t.loc["IN", "in_membership"]) is True
    assert bool(t.loc["EDGE", "in_membership"]) is False   # [from, to)
    assert bool(t.loc["OUT", "in_membership"]) is False
    assert T.count_boundary_rows(t.reset_index(), spells) == 1


# ---------------------------------------------------------------------------
# 2. The window and the benchmark
# ---------------------------------------------------------------------------


def _set_window_prices(prices: pd.DataFrame, calendar, open_date,
                       holding=T.HOLDING_SESSIONS) -> pd.Timestamp:
    """Subject +10%, one peer +20%, one peer -20%, one peer unpriced at close."""
    o = calendar.get_loc(pd.Timestamp(open_date))
    c = o + holding
    prices.iloc[o, :] = 100.0
    prices.iloc[c, prices.columns.get_loc(SUBJECT)] = 110.0
    prices.iloc[c, prices.columns.get_loc(PEER_UP)] = 120.0
    prices.iloc[c, prices.columns.get_loc(PEER_DOWN)] = 80.0
    prices.iloc[c, prices.columns.get_loc(PEER_UNPRICED)] = np.nan
    return calendar[c]


def test_window_is_exactly_63_sessions(prices, member_mat, spells, calendar):
    row = filing(SUBJECT, "2020-01-08", "2020-01-08T14:30:00.000Z")
    t = build(row, prices, member_mat, spells).iloc[0]
    o = calendar.get_loc(t["window_open_session"])
    c = calendar.get_loc(t["window_close_session"])
    assert T.HOLDING_SESSIONS == 63 == C.HOLDING_DAYS
    assert c - o == 63


def test_window_length_follows_the_holding_parameter(prices, member_mat,
                                                     spells, calendar):
    row = filing(SUBJECT, "2020-01-08", "2020-01-08T14:30:00.000Z")
    t = build(row, prices, member_mat, spells, holding=5).iloc[0]
    o = calendar.get_loc(t["window_open_session"])
    c = calendar.get_loc(t["window_close_session"])
    assert c - o == 5


def test_benchmark_excludes_self_and_counts_unpriced_members(
        prices, member_mat, spells, calendar):
    row = filing(SUBJECT, "2020-01-08", "2020-01-08T14:30:00.000Z")
    # window opens the session after 2020-01-08
    open_date = calendar[calendar.get_loc(pd.Timestamp("2020-01-08")) + 1]
    close_date = _set_window_prices(prices, calendar, open_date)

    t = build(row, prices, member_mat, spells).iloc[0]
    assert t["window_open_session"] == open_date
    assert t["window_close_session"] == close_date

    assert t["subject_return_63"] == pytest.approx(0.10)
    # ex-self mean of (+0.20, -0.20); WITH self it would be +0.0333.
    assert t["benchmark_return_63"] == pytest.approx(0.0)
    assert t["benchmark_return_63"] != pytest.approx((0.10 + 0.20 - 0.20) / 3)
    assert t["target_excess_63"] == pytest.approx(0.10)

    # The unpriced member is COUNTED, not imputed: it is absent from the mean
    # and present in the census column.
    assert t["n_benchmark_members"] == 2
    assert t["n_benchmark_unpriced"] == 1


def test_unpriced_member_does_not_enter_the_mean_as_zero(
        prices, member_mat, spells, calendar):
    """If the unpriced peer were imputed at 0% the benchmark would move."""
    row = filing(SUBJECT, "2020-01-08", "2020-01-08T14:30:00.000Z")
    open_date = calendar[calendar.get_loc(pd.Timestamp("2020-01-08")) + 1]
    _set_window_prices(prices, calendar, open_date)
    o = calendar.get_loc(open_date)
    prices.iloc[o + T.HOLDING_SESSIONS, prices.columns.get_loc(PEER_DOWN)] = 40.0
    t = build(row, prices, member_mat, spells).iloc[0]
    # ex-self, priced peers only: mean(+0.20, -0.60) = -0.20
    assert t["benchmark_return_63"] == pytest.approx(-0.20)
    # imputing the unpriced peer at 0 would give mean(+0.20, -0.60, 0) = -0.1333
    assert t["benchmark_return_63"] != pytest.approx(-0.4 / 3)
    assert t["n_benchmark_unpriced"] == 1


def test_benchmark_uses_membership_on_the_window_open_session(
        prices, member_mat, calendar):
    """A peer whose spell ended before the window opens is not a benchmark
    member, and contributes nothing."""
    spells = pd.DataFrame({
        "cik": ALL_CIKS,
        "sector": "test",
        "stratum": "core",
        "member_from": pd.Timestamp("2019-01-01"),
        "member_to": [pd.Timestamp("2200-01-01"), pd.Timestamp("2200-01-01"),
                      pd.Timestamp("2020-01-02"), pd.Timestamp("2200-01-01")],
    })
    mm = C.build_membership_matrix(spells, calendar)
    row = filing(SUBJECT, "2020-01-08", "2020-01-08T14:30:00.000Z")
    open_date = calendar[calendar.get_loc(pd.Timestamp("2020-01-08")) + 1]
    _set_window_prices(prices, calendar, open_date)
    t = build(row, prices, mm, spells).iloc[0]
    # PEER_DOWN has left the universe: only PEER_UP is priced and a member.
    assert t["n_benchmark_members"] == 1
    assert t["benchmark_return_63"] == pytest.approx(0.20)
    assert t["n_benchmark_unpriced"] == 1  # PEER_UNPRICED still a member


# ---------------------------------------------------------------------------
# 3. Incompleteness
# ---------------------------------------------------------------------------


def test_incomplete_window_is_null_and_flagged(prices, member_mat, spells,
                                               calendar):
    late = calendar[-10]           # 63 sessions do not fit before the snapshot end
    row = filing(SUBJECT, str(late.date()), f"{late.date()}T14:30:00.000Z")
    t = build(row, prices, member_mat, spells).iloc[0]
    assert bool(t["target_complete"]) is False
    assert pd.isna(t["window_close_session"])
    assert pd.isna(t["subject_return_63"])
    assert pd.isna(t["benchmark_return_63"])
    assert pd.isna(t["target_excess_63"])
    # The dated columns it DOES have are still written -- it is census, not junk.
    assert pd.notna(t["news_session"])
    assert pd.notna(t["window_open_session"])


def test_row_at_the_very_end_of_the_calendar_has_no_window(
        prices, member_mat, spells, calendar):
    last = calendar[-1]
    row = filing(SUBJECT, str(last.date()), f"{last.date()}T21:30:00.000Z")
    t = build(row, prices, member_mat, spells).iloc[0]
    assert pd.isna(t["window_open_session"])
    assert bool(t["target_complete"]) is False


# ---------------------------------------------------------------------------
# 4. The invariants have teeth
# ---------------------------------------------------------------------------


def test_invariants_catch_an_injected_lookahead(prices, member_mat, spells,
                                                calendar):
    row = filing(SUBJECT, "2020-01-08", "2020-01-08T21:30:00.000Z")
    t = build(row, prices, member_mat, spells)
    bad = t.copy()
    bad.loc[0, "window_open_session"] = bad.loc[0, "info_date"]
    with pytest.raises(AssertionError, match="on or before info_date"):
        T.assert_target_invariants(bad, calendar)

    bad2 = t.copy()
    bad2.loc[0, "news_session"] = bad2.loc[0, "info_date"]
    with pytest.raises(AssertionError, match="post-close"):
        T.assert_target_invariants(bad2, calendar)

    bad3 = t.copy()
    o = calendar.get_loc(bad3.loc[0, "window_open_session"])
    bad3.loc[0, "window_close_session"] = calendar[o + 40]
    with pytest.raises(AssertionError, match="window length"):
        T.assert_target_invariants(bad3, calendar)

    bad4 = t.copy()
    bad4.loc[0, "target_excess_63"] = 0.5
    bad4.loc[0, "subject_return_63"] = 0.1
    bad4.loc[0, "benchmark_return_63"] = 0.1
    with pytest.raises(AssertionError, match="subject - benchmark"):
        T.assert_target_invariants(bad4, calendar)


def test_module_computes_no_association_statistic():
    """The E2 freeze, as a test: no IC/correlation machinery in this module."""
    src = (T.REPO_ROOT / "target_e2.py").read_text().lower()
    for token in ("spearman", "pearson", "corrcoef", ".corr(", "linregress",
                  "ols(", "polyfit"):
        assert token not in src, f"forbidden association token in module: {token}"


# ---------------------------------------------------------------------------
# 5. Real-data smoke -- <= 300 filings, deterministic stride, no shuffle
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def real_stack():
    prices = C.load_price_matrix(T.PRICES_PATH)
    members = C.load_membership(T.METADATA_DB)
    mm = C.build_membership_matrix(members, prices.index)
    spells = T.load_core_spells(T.METADATA_DB)
    f = T.load_core_filings(T.METADATA_DB)
    f = f[f["cik"].isin(set(prices.columns))]
    stride = max(1, len(f) // 300)
    sample = f.iloc[::stride].head(300).copy()   # time-ordered, deterministic
    return prices, mm, spells, sample


def test_real_input_shas_match_the_committed_manifest():
    out = T.assert_input_shas()
    assert out["matches_committed"] is True
    assert out["measured"]["prices_e2.parquet"]


def test_real_smoke_target_invariants(real_stack):
    prices, mm, spells, sample = real_stack
    assert 0 < len(sample) <= 300
    t = T.build_targets(sample, prices, mm, spells)   # raises on any violation
    assert len(t) == len(sample)
    assert list(t.columns) == T.OUTPUT_COLUMNS

    open_ok = t["window_open_session"].notna()
    assert (t.loc[open_ok, "window_open_session"] > t.loc[open_ok, "info_date"]).all()
    assert (t["info_date"] >= t["filing_date"]).all()

    both = open_ok & t["window_close_session"].notna()
    o = prices.index.get_indexer(t.loc[both, "window_open_session"])
    c = prices.index.get_indexer(t.loc[both, "window_close_session"])
    assert set((c - o).tolist()) == {63}

    inc = ~t["target_complete"]
    assert t.loc[inc, "target_excess_63"].isna().all()
    assert t.loc[inc, "window_close_session"].isna().all()


def test_real_smoke_benchmark_is_ex_self(real_stack):
    """Re-derive the benchmark by hand for real rows and compare."""
    prices, mm, spells, sample = real_stack
    t = T.build_targets(sample, prices, mm, spells)
    live = t[t["target_complete"] & t["in_membership"]
             & t["benchmark_return_63"].notna()].head(5)
    assert len(live) == 5
    member_arr = C.align_membership(mm, prices.columns)
    for r in live.itertuples(index=False):
        o = prices.index.get_loc(r.window_open_session)
        c = prices.index.get_loc(r.window_close_session)
        p0 = prices.iloc[o].to_numpy(dtype=float)
        p1 = prices.iloc[c].to_numpy(dtype=float)
        with np.errstate(divide="ignore", invalid="ignore"):
            rets = np.where((p0 > 0) & np.isfinite(p0) & np.isfinite(p1),
                            p1 / p0 - 1.0, np.nan)
        peers = member_arr[o].copy()
        col = list(prices.columns).index(r.cik)
        assert peers[col], "the subject must itself be a member on that session"
        peers[col] = False                       # ex-self, by hand
        peer_rets = rets[peers]
        valid = np.isfinite(peer_rets)
        assert r.benchmark_return_63 == pytest.approx(float(peer_rets[valid].mean()))
        assert r.n_benchmark_members == int(valid.sum())
        assert r.n_benchmark_unpriced == int((~valid).sum())
        # including self would change the number (the discriminating check)
        with_self = float(np.nanmean(rets[member_arr[o]]))
        assert r.benchmark_return_63 != pytest.approx(with_self, abs=1e-12)
        if np.isfinite(r.subject_return_63):
            assert r.target_excess_63 == pytest.approx(
                r.subject_return_63 - r.benchmark_return_63)


def test_real_smoke_unpriced_members_are_counted_never_imputed(real_stack):
    prices, mm, spells, sample = real_stack
    t = T.build_targets(sample, prices, mm, spells)
    live = t[t["target_complete"]]
    # Counted: the column exists and is a non-negative integer everywhere.
    assert (live["n_benchmark_unpriced"] >= 0).all()
    # Never imputed: a member cell without price coverage never enters the mean,
    # so members-used + unpriced equals the membership count on that session.
    member_arr = C.align_membership(mm, prices.columns)
    for r in live.head(20).itertuples(index=False):
        o = prices.index.get_loc(r.window_open_session)
        n_members_ex_self = int(member_arr[o].sum()) - int(
            member_arr[o][list(prices.columns).index(r.cik)])
        assert r.n_benchmark_members + r.n_benchmark_unpriced == n_members_ex_self


def test_real_smoke_gld_is_kept_and_flagged(real_stack):
    prices, mm, spells, sample = real_stack
    # The sample may not contain GLD; assert on the full scoped frame instead.
    f = T.load_core_filings(T.METADATA_DB)
    assert (f["cik"] == T.GLD_CIK).any(), "SPDR GOLD TRUST must be in scope"
    gld = f[f["cik"] == T.GLD_CIK].head(3)
    t = T.build_targets(gld, prices, mm, spells)
    assert t["is_gld"].all()
    assert len(t) == 3
