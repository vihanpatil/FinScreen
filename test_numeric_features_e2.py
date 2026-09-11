"""
test_numeric_features_e2.py -- leakage/semantics suite for the E2 numeric
feature builder (F5 Step 1A).

Two layers:
  * synthetic fixtures that prove the point-in-time semantics exactly (a
    restatement filed after info_date is invisible; the staleness guard
    fires; YoY is duration- and period-matched; the price windows end
    STRICTLY before the news session; an UNRESOLVED family nulls its features
    and is logged);
  * a real-data smoke on a deterministic, time-ordered stride sample of 200
    filings drawn across the WHOLE row universe (not the first 200 rows of the
    lowest-numbered CIK), pinning the corpus-level conventions (key
    uniqueness, the 7.33% multi-valued restatement census, no fact filed after
    info_date ever reaches a row).

Nothing here computes, or can compute, a feature-versus-outcome association
(F5_PLAN §1 freeze): no return, target or IC appears anywhere in this file.
"""

from __future__ import annotations

from unittest import mock

import numpy as np
import pandas as pd
import pytest

import features as F1
import numeric_features_e2 as M
from pit import value_as_of

FUND_COLS = ["ticker", "cik", "taxonomy", "concept", "unit", "value", "fy", "fp",
             "period_start", "period_end", "form", "accession_number", "filed"]


def _fact(cik, concept, value, period_end, filed, period_start=None,
          unit="USD", taxonomy="us-gaap", form="10-Q", accn=None):
    return {
        "ticker": str(cik), "cik": cik, "taxonomy": taxonomy, "concept": concept,
        "unit": unit, "value": float(value), "fy": 2020, "fp": "Q1",
        "period_start": pd.Timestamp(period_start) if period_start else pd.NaT,
        "period_end": pd.Timestamp(period_end), "form": form,
        "accession_number": accn or f"{cik}-{concept}-{filed}", "filed": pd.Timestamp(filed),
    }


def _frame(rows):
    return pd.DataFrame(rows, columns=FUND_COLS)


# ---------------------------------------------------------------------------
# 1. As-of semantics: the restatement must not travel backwards
# ---------------------------------------------------------------------------


def test_restatement_filed_after_info_date_is_invisible():
    """The defining test: a period reported at 100, restated to 999 in a
    filing made AFTER our info_date. The as-of path must return 100; a
    latest-value groupby (prohibited) would return 999."""
    cik = 42
    rows = [
        _fact(cik, "Assets", 100, "2020-03-31", "2020-04-20"),
        _fact(cik, "Assets", 999, "2020-03-31", "2020-11-01"),  # restatement, later
    ]
    slices = M.slice_by_cik_tag(_frame(rows))
    row, tag = M.resolve_family_value(slices, ["Assets"], cik, "2020-05-01")
    assert row["value"] == 100.0
    assert tag == "Assets"

    naive = _frame(rows).sort_values("filed").groupby(["cik", "concept"]).tail(1)
    assert float(naive["value"].iloc[0]) == 999.0, "fixture must distinguish the two paths"

    # Once filed AND still inside the staleness guard, the restatement IS
    # knowable and must be used.
    rows.append(_fact(cik, "Assets", 999, "2020-03-31", "2020-08-01", accn="restate2"))
    slices2 = M.slice_by_cik_tag(_frame(rows))
    after = M.resolve_family_value(slices2, ["Assets"], cik, "2020-09-01")[0]
    assert after["value"] == 999.0


def test_fact_filed_after_as_of_never_used_at_all():
    cik = 7
    rows = [_fact(cik, "Assets", 500, "2021-06-30", "2021-07-25")]
    slices = M.slice_by_cik_tag(_frame(rows))
    assert M.resolve_family_value(slices, ["Assets"], cik, "2021-07-24") == (None, None)
    assert M.resolve_family_value(slices, ["Assets"], cik, "2021-07-25")[0]["value"] == 500.0


def test_slicing_does_not_change_value_as_of():
    """The per-(cik, tag) pre-slice is a performance move only."""
    cik = 3
    rows = [_fact(cik, "Assets", 1, "2020-03-31", "2020-04-20"),
            _fact(cik, "Assets", 2, "2020-06-30", "2020-07-20"),
            _fact(9, "Assets", 77, "2020-06-30", "2020-07-20"),
            _fact(cik, "Liabilities", 3, "2020-06-30", "2020-07-20")]
    full = _frame(rows)
    sliced = M.slice_by_cik_tag(full)[(cik, "Assets")]
    a = value_as_of(full, "Assets", "2020-08-01", cik=cik, taxonomy="us-gaap")
    b = value_as_of(sliced, "Assets", "2020-08-01", cik=cik, taxonomy="us-gaap")
    assert a["value"] == b["value"] == 2.0


def test_port_matches_e1_resolver():
    """The CIK-keyed port agrees with the frozen E1 resolver on a case E1 can
    express (us-gaap, one ticker)."""
    cik = 11
    rows = [_fact(cik, "NetIncomeLoss", 5, "2019-12-31", "2020-02-10"),
            _fact(cik, "ProfitLoss", 6, "2020-03-31", "2020-04-25")]
    fund = _frame(rows)
    e1_row, e1_tag = F1.resolve_concept_family(
        fund, ["NetIncomeLoss", "ProfitLoss"], str(cik), cik, "2020-05-01")
    p_row, p_tag = M.resolve_family_value(
        M.slice_by_cik_tag(fund), ["NetIncomeLoss", "ProfitLoss"], cik, "2020-05-01")
    assert (e1_tag, e1_row["value"]) == (p_tag, p_row["value"]) == ("ProfitLoss", 6.0)


# ---------------------------------------------------------------------------
# 2. Staleness guard
# ---------------------------------------------------------------------------


def test_staleness_guard_discards_and_logs():
    cik = 5
    stale_end = pd.Timestamp("2020-01-31")
    as_of = stale_end + pd.Timedelta(days=F1.STALENESS_MAX_DAYS + 1)
    rows = [_fact(cik, "Assets", 12, stale_end, stale_end + pd.Timedelta(days=10))]
    slices = M.slice_by_cik_tag(_frame(rows))
    log: list[dict] = []
    out = M.resolve_family_value(slices, ["Assets"], cik, as_of, staleness_log=log,
                                 family="assets")
    assert out == (None, None)
    assert len(log) == 1 and log[0]["days_stale"] == F1.STALENESS_MAX_DAYS + 1

    fresh_as_of = stale_end + pd.Timedelta(days=F1.STALENESS_MAX_DAYS)
    row, _ = M.resolve_family_value(slices, ["Assets"], cik, fresh_as_of)
    assert row is not None and row["_days_stale"] == F1.STALENESS_MAX_DAYS


# ---------------------------------------------------------------------------
# 3. YoY alignment
# ---------------------------------------------------------------------------


def test_yoy_is_period_and_duration_matched():
    cik = 8
    rows = [
        _fact(cik, "Revenues", 120, "2021-03-31", "2021-04-20", period_start="2021-01-01"),
        _fact(cik, "Revenues", 100, "2020-03-31", "2020-04-20", period_start="2020-01-01"),
        # a same-period-end ANNUAL fact must not be picked as the prior quarter
        _fact(cik, "Revenues", 400, "2020-03-31", "2020-04-20", period_start="2019-04-01",
              accn="annual"),
    ]
    slices = M.slice_by_cik_tag(_frame(rows))
    cur, tag = M.resolve_family_value(slices, ["Revenues"], cik, "2021-05-01")
    g, prior_tag = M.yoy_growth_family(slices, ["Revenues"], cik, "2021-05-01", cur, tag)
    assert g == pytest.approx(0.2)
    assert prior_tag == "Revenues"


def test_yoy_prior_filed_after_as_of_is_invisible():
    cik = 9
    rows = [
        _fact(cik, "Revenues", 120, "2021-03-31", "2021-04-20", period_start="2021-01-01"),
        _fact(cik, "Revenues", 100, "2020-03-31", "2021-06-01", period_start="2020-01-01"),
    ]
    slices = M.slice_by_cik_tag(_frame(rows))
    cur, tag = M.resolve_family_value(slices, ["Revenues"], cik, "2021-05-01")
    g, _ = M.yoy_growth_family(slices, ["Revenues"], cik, "2021-05-01", cur, tag)
    assert np.isnan(g)


def test_yoy_crosses_a_migration_tag():
    """A MIGRATION family's prior-year figure sits under the predecessor tag."""
    cik = 10
    rows = [
        _fact(cik, "ProfitLoss", 110, "2021-03-31", "2021-04-20", period_start="2021-01-01"),
        _fact(cik, "NetIncomeLoss", 100, "2020-03-31", "2020-04-20", period_start="2020-01-01"),
    ]
    slices = M.slice_by_cik_tag(_frame(rows))
    cur, tag = M.resolve_family_value(slices, ["NetIncomeLoss", "ProfitLoss"], cik, "2021-05-01")
    assert tag == "ProfitLoss"
    g, prior_tag = M.yoy_growth_family(slices, ["NetIncomeLoss", "ProfitLoss"], cik,
                                       "2021-05-01", cur, tag)
    assert g == pytest.approx(0.1) and prior_tag == "NetIncomeLoss"


# ---------------------------------------------------------------------------
# 3b. Period identity: FY vs Q4 on the same period_end (decision 22 DEFECT,
#     fixed 2026-09-11). The fixture is the shape the app lane measured on
#     CIK 1494259 (revenue) and 1438943 (net income): both facts in the same
#     filing, same accession, same filed date, same period_end -- so every
#     tiebreak in pit.value_as_of ties and row order used to decide.
# ---------------------------------------------------------------------------


def _fy_and_q4(cik=1494259, concept="Revenues", year=906980000.0, quarter=241094000.0,
               accn="0001-26-000001"):
    return [
        _fact(cik, concept, year, "2025-12-31", "2026-02-19",
              period_start="2025-01-01", form="10-K", accn=accn),
        _fact(cik, concept, quarter, "2025-12-31", "2026-02-19",
              period_start="2025-10-01", form="10-K", accn=accn),
    ]


def test_annual_and_quarterly_are_both_reachable_on_one_colliding_period_end():
    """The fix, in one test: the annual preference returns the YEAR, the
    quarterly preference returns the QUARTER, from the same two facts."""
    rows = _fy_and_q4()
    slices = M.slice_by_cik_tag(_frame(rows))

    annual, tag = M.resolve_family_value(slices, ["Revenues"], 1494259, "2026-02-19")
    assert annual["value"] == 906980000.0
    assert annual["_duration_bucket"] == "FY"
    assert annual["_duration_alternatives"] == ("Q", "FY")
    assert tag == "Revenues"

    quarterly, _ = M.resolve_family_value(slices, ["Revenues"], 1494259, "2026-02-19",
                                          prefer_duration="quarterly")
    assert quarterly["value"] == 241094000.0
    assert quarterly["_duration_bucket"] == "Q"


def test_row_order_no_longer_decides():
    """The defect was that the choice fell through to row order. Reversing the
    frame must not move the value under either preference."""
    rows = _fy_and_q4()
    for frame in (_frame(rows), _frame(rows[::-1])):
        slices = M.slice_by_cik_tag(frame)
        assert M.resolve_family_value(
            slices, ["Revenues"], 1494259, "2026-02-19")[0]["value"] == 906980000.0
        assert M.resolve_family_value(
            slices, ["Revenues"], 1494259, "2026-02-19",
            prefer_duration="quarterly")[0]["value"] == 241094000.0


def test_midyear_quarter_versus_year_to_date_is_left_exactly_where_it_was():
    """No FY fact at the winning period_end (every mid-year 10-Q: a quarter
    against a year-to-date figure), so BOTH preferences fall through to the
    shortest bucket -- what row order already returned on all 18,300 rows.
    Whether the ratios should duration-match instead is G3 decision 21, and
    this fix must not pre-empt it."""
    cik = 77
    rows = [
        _fact(cik, "Revenues", 300, "2025-09-30", "2025-10-20", period_start="2025-01-01",
              accn="0002-25-000001"),                                    # 9M
        _fact(cik, "Revenues", 100, "2025-09-30", "2025-10-20", period_start="2025-07-01",
              accn="0002-25-000001"),                                    # Q3
    ]
    slices = M.slice_by_cik_tag(_frame(rows))
    for prefer in ("annual", "quarterly"):
        row, _ = M.resolve_family_value(slices, ["Revenues"], cik, "2025-11-01",
                                        prefer_duration=prefer)
        assert row["value"] == 100.0 and row["_duration_bucket"] == "Q"


def test_instant_facts_are_untouched():
    """Balance-sheet facts have no duration; the disambiguation returns before
    a bucket is computed and records no alternatives."""
    cik = 78
    slices = M.slice_by_cik_tag(_frame([_fact(cik, "Assets", 50, "2025-12-31", "2026-02-01")]))
    row, _ = M.resolve_family_value(slices, ["Assets"], cik, "2026-03-01")
    assert row["value"] == 50.0
    assert row["_duration_bucket"] == "instant"
    assert row["_duration_alternatives"] == ()


def test_the_preference_never_moves_the_period():
    """The pre-filter runs only at the period `pit.value_as_of` already chose.
    An older FY fact must never win over the newest quarter."""
    cik = 79
    rows = [
        _fact(cik, "Revenues", 4000, "2024-12-31", "2025-02-15", period_start="2024-01-01"),
        _fact(cik, "Revenues", 1100, "2025-03-31", "2025-04-20", period_start="2025-01-01"),
    ]
    slices = M.slice_by_cik_tag(_frame(rows))
    row, _ = M.resolve_family_value(slices, ["Revenues"], cik, "2025-05-01")
    assert row["value"] == 1100.0
    assert pd.Timestamp(row["period_end"]) == pd.Timestamp("2025-03-31")
    assert row["_duration_alternatives"] == ()


def test_as_of_still_governs_inside_the_preferred_bucket():
    """A restatement of the ANNUAL fact filed after as_of stays invisible; the
    duration pre-filter hands pit.value_as_of a smaller frame, not a different
    as-of rule."""
    cik = 80
    rows = _fy_and_q4(cik=cik) + [
        _fact(cik, "Revenues", 999.0, "2025-12-31", "2026-05-01",
              period_start="2025-01-01", accn="0001-26-000002"),          # restated FY
    ]
    slices = M.slice_by_cik_tag(_frame(rows))
    assert M.resolve_family_value(slices, ["Revenues"], cik,
                                  "2026-02-19")[0]["value"] == 906980000.0
    assert M.resolve_family_value(slices, ["Revenues"], cik,
                                  "2026-05-15")[0]["value"] == 999.0


def test_yoy_follows_the_annual_current_fact_to_the_annual_prior_fact():
    """End to end: with the current fact now the YEAR, E1's duration-matched
    prior lookup finds the prior YEAR, never the prior Q4 that shares its
    period_end. 1100/1000 - 1 = 0.1, not 300/250 - 1 = 0.2."""
    cik = 81
    rows = [
        _fact(cik, "Revenues", 1100, "2025-12-31", "2026-02-19", period_start="2025-01-01",
              form="10-K", accn="0003-26-000001"),
        _fact(cik, "Revenues", 300, "2025-12-31", "2026-02-19", period_start="2025-10-01",
              form="10-K", accn="0003-26-000001"),
        _fact(cik, "Revenues", 1000, "2024-12-31", "2025-02-19", period_start="2024-01-01",
              form="10-K", accn="0003-25-000001"),
        _fact(cik, "Revenues", 250, "2024-12-31", "2025-02-19", period_start="2024-10-01",
              form="10-K", accn="0003-25-000001"),
    ]
    slices = M.slice_by_cik_tag(_frame(rows))
    cur, tag = M.resolve_family_value(slices, ["Revenues"], cik, "2026-02-19")
    assert cur["value"] == 1100.0
    g, _ = M.yoy_growth_family(slices, ["Revenues"], cik, "2026-02-19", cur, tag)
    assert g == pytest.approx(0.1)

    cur_q, tag_q = M.resolve_family_value(slices, ["Revenues"], cik, "2026-02-19",
                                          prefer_duration="quarterly")
    g_q, _ = M.yoy_growth_family(slices, ["Revenues"], cik, "2026-02-19", cur_q, tag_q)
    assert g_q == pytest.approx(0.2)


def test_duration_buckets_are_f2s_own_and_not_retyped():
    """`DURATION_BUCKET_DAYS` and the classifier come from
    `ingest_fundamentals`; this pins the labels the fix branches on."""
    import ingest_fundamentals as IF

    assert M.DURATION_BUCKET_DAYS is IF.DURATION_BUCKET_DAYS
    assert M.BUCKET_ORDER == ("Q", "H1", "9M", "FY", "other")
    assert M.ANNUAL_BUCKET == "FY"
    starts = pd.Series([pd.NaT, "2025-10-01", "2025-07-01", "2025-04-01", "2025-01-01"])
    ends = pd.Series(["2025-12-31"] * 5)
    assert list(M.duration_buckets(starts, ends)) == ["instant", "Q", "H1", "9M", "FY"]


def test_unknown_preference_is_refused():
    slices = M.slice_by_cik_tag(_frame(_fy_and_q4()))
    with pytest.raises(ValueError):
        M.resolve_family_value(slices, ["Revenues"], 1494259, "2026-02-19",
                               prefer_duration="trailing_twelve_months")


# ---------------------------------------------------------------------------
# 3c. `operating_cashflow_to_revenue` is duration-matched (G3 decision 21,
#     owner ruling 2026-09-11).
# ---------------------------------------------------------------------------


def test_duration_bucket_of_days_agrees_with_f2s_vectorised_classifier():
    """The scalar helper must be F2's classifier, not a second definition."""
    ends = pd.Series([pd.Timestamp("2025-12-31")] * 8)
    days = [None, 1, 90, 115, 116, 210, 300, 400]
    starts = pd.Series([pd.NaT if d is None else ends[0] - pd.Timedelta(days=d)
                        for d in days])
    expected = list(M.duration_buckets(starts, ends))
    assert [M.duration_bucket_of_days(d) for d in days] == expected
    assert M.duration_bucket_of_days(401) == "other"


def test_a_ytd_cash_flow_is_never_divided_by_a_quarterly_revenue():
    """The defect decision 21 rules on: 273-day (9M) operating cash flow over
    a 92-day (Q) revenue. The ported definition emitted a number; the ruled
    definition emits NaN and says why."""
    value, reason = M.duration_matched_ratio(3.0, 273, 92)
    assert pd.isna(value)
    assert reason == "duration_mismatch:9M_over_Q"

    # H1 over Q is the same defect one quarter earlier.
    assert pd.isna(M.duration_matched_ratio(2.0, 181, 91)[0])
    assert M.duration_matched_ratio(2.0, 181, 91)[1] == "duration_mismatch:H1_over_Q"

    # Matched periods survive, with the bucket named on the row.
    assert M.duration_matched_ratio(0.25, 92, 90) == (0.25, "duration_matched:Q")
    assert M.duration_matched_ratio(0.30, 365, 366) == (0.30, "duration_matched:FY")
    assert M.duration_matched_ratio(0.30, 273, 275) == (0.30, "duration_matched:9M")


def test_every_nan_ocf_ratio_carries_a_reason():
    """No row is ever silently blank -- missing periods and an unavailable
    value each get their own named reason."""
    assert M.duration_matched_ratio(1.0, None, 90)[1] == "no_period_for_numerator"
    assert M.duration_matched_ratio(1.0, 90, None)[1] == "no_period_for_denominator"
    assert M.duration_matched_ratio(1.0, None, None)[1] == "no_period_for_either_flow"
    assert M.duration_matched_ratio(np.nan, 90, 92)[1] == "value_unavailable:Q"
    for args in [(1.0, None, 90), (1.0, 90, None), (1.0, None, None),
                 (np.nan, 90, 92), (3.0, 273, 92)]:
        v, r = M.duration_matched_ratio(*args)
        assert pd.isna(v) and r


def test_only_the_ruled_ratio_is_duration_matched():
    """Decision 21 names one feature. `net_margin` / `operating_margin` keep
    the ported definition -- changing an unruled feature is not this module's
    call -- and the module says so."""
    src = (M.REPO_ROOT / "numeric_features_e2.py").read_text()
    assert src.count("duration_matched_ratio(") == 2      # the def + one call
    assert 'rec["operating_cashflow_to_revenue"] = matched' in src
    assert "unruled_ratios_left_as_ported" in src


# ---------------------------------------------------------------------------
# 4. Price windows end STRICTLY before the news session
# ---------------------------------------------------------------------------


def _ramp(n=400):
    return np.arange(1.0, n + 1.0)


def test_price_windows_never_touch_the_news_session():
    closes = _ramp()
    pre = 300
    mom, vol, px = M.price_factors(closes, pre)
    poisoned = closes.copy()
    poisoned[pre + 1:] = 1e9          # everything from the news session on
    mom2, vol2, px2 = M.price_factors(poisoned, pre)
    assert (mom, vol, px) == (mom2, vol2, px2)
    assert px == closes[pre]


def test_momentum_and_vol_window_lengths():
    closes = _ramp()
    pre = 300
    mom, vol, _ = M.price_factors(closes, pre)
    assert mom == pytest.approx(closes[pre] / closes[pre - M.MOMENTUM_LOOKBACK_SESSIONS] - 1)
    window = closes[pre - M.VOL_WINDOW_SESSIONS: pre + 1]
    rets = np.diff(np.log(window))
    assert len(rets) == M.VOL_WINDOW_SESSIONS
    assert vol == pytest.approx(float(np.std(rets, ddof=M.VOL_DDOF)))


def test_price_factors_nan_when_history_is_short_or_missing():
    closes = _ramp(200)
    assert np.isnan(M.price_factors(closes, 10)[0])          # < 126 sessions back
    assert np.isnan(M.price_factors(closes, 10)[1])          # < 63 sessions back
    assert all(np.isnan(v) for v in M.price_factors(None, 100))
    assert all(np.isnan(v) for v in M.price_factors(closes, -1))


def test_post_close_pushes_the_news_session_one_forward():
    """The session rule is controls.resolve_sessions, imported verbatim; this
    pins the behaviour this module relies on."""
    cal = pd.DatetimeIndex(pd.bdate_range("2021-01-04", periods=20))
    events = pd.DataFrame({
        "accession_number": ["a", "b"],
        "cik": [1, 1],
        "filing_date": pd.to_datetime(["2021-01-08", "2021-01-08"]),
        "acceptance_datetime": ["2021-01-08T14:30:00.000Z",   # 09:30 ET, pre-close
                                "2021-01-08T21:30:00.000Z"],  # 16:30 ET, post-close
    })
    out = M.C.resolve_sessions(events, cal)
    assert list(out["post_close"]) == [False, True]
    assert cal[out["news_pos"].iloc[0]] == pd.Timestamp("2021-01-08")
    assert cal[out["news_pos"].iloc[1]] == pd.Timestamp("2021-01-11")
    assert (cal[out["pre_pos"]] < cal[out["news_pos"]]).all()


# ---------------------------------------------------------------------------
# 5. Unresolved families, currency, and module hygiene
# ---------------------------------------------------------------------------


def test_unresolved_family_has_no_fallback_tag():
    """An UNRESOLVED (cik, family) resolves to nothing even when rows exist:
    `resolve_family_value` is only ever called with the classifier's resolved
    tags, and `build()` passes none for an UNRESOLVED pair."""
    assert M.resolve_family_value({}, [], 1, "2020-01-01") == (None, None)


def test_feature_family_map_covers_every_feature():
    for f in M.E1_NUMERIC_FEATURES + ["book_to_market"]:
        assert f in M.FEATURE_FAMILIES and M.FEATURE_FAMILIES[f]
    assert M.E1_NUMERIC_FEATURES == list(F1.NUMERIC_FEATURE_NAMES)
    assert len(M.E1_NUMERIC_FEATURES) == 10
    for fam in M.NEEDED_FAMILIES:
        assert fam in M.CONCEPT_FAMILIES


def test_module_never_reads_report_date_or_groups_to_latest():
    """Executable code only -- docstrings and comments discuss `report_date`
    precisely because it must never be used."""
    import ast

    src = (M.REPO_ROOT / "numeric_features_e2.py").read_text()
    tree = ast.parse(src)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstrings:
            assert "report_date" not in node.value, node.value
        if isinstance(node, ast.Attribute):
            assert node.attr != "report_date"
        # `.tail(1)` / keep="last" after a groupby is the prohibited
        # latest-value shortcut (C2).
        if isinstance(node, ast.Attribute):
            assert node.attr != "tail", "latest-value shortcut"
        if isinstance(node, ast.keyword) and node.arg == "keep":
            assert False, "keep=... on a dedup is the prohibited latest-value path"


def test_shares_outstanding_family_exists_so_book_to_market_is_buildable():
    """Decision 3's gap check: a shares/market-cap concept must EXIST in
    fundamentals_e2 or book_to_market would have to be skipped."""
    fam = M.CONCEPT_FAMILIES["shares_outstanding"]
    assert fam == [("dei", "EntityCommonStockSharesOutstanding")]
    assert M.TAXONOMY_OF_TAG["EntityCommonStockSharesOutstanding"] == "dei"
    f = pd.read_parquet(M.FUNDAMENTALS_PATH, columns=["taxonomy", "concept"])
    n = int(((f["taxonomy"] == "dei")
             & (f["concept"] == "EntityCommonStockSharesOutstanding")).sum())
    assert n == 13793, n


# ---------------------------------------------------------------------------
# 6. Real-data assertions and the 200-filing stride smoke
# ---------------------------------------------------------------------------


def test_restatement_census_on_real_fundamentals():
    """C2: a latest-value groupby is not merely inelegant, it is wrong for
    7.33% of the groups in this artifact."""
    f = pd.read_parquet(M.FUNDAMENTALS_PATH,
                        columns=["cik", "concept", "unit", "period_start",
                                 "period_end", "value"])
    g = f.groupby(["cik", "concept", "unit", "period_start", "period_end"],
                  dropna=False)["value"].nunique()
    frac = float((g > 1).mean())
    assert 0.070 <= frac <= 0.076, frac


def test_input_shas_match_the_committed_record():
    shas = M.assert_input_shas()
    assert shas["prices_e2.parquet"].startswith("744e1cc5")
    assert shas["fundamentals_e2.parquet"].startswith("f6064adf")
    assert shas["filings_metadata_e2.db"].startswith("61dcefaa")


SMOKE_N = 200


@pytest.fixture(scope="module")
def smoke():
    """Build SMOKE_N rows drawn by a deterministic time-ordered stride over the
    WHOLE row universe (same construction as `test_target_e2.py`'s
    `real_stack`). `build(limit=N)` would take the head of a cik-major sort,
    i.e. 200 filings of a single low-numbered CIK -- one company, one sector,
    one contiguous stretch of time. The stride sample spans every year, sector
    and form in the table, so the smoke assertions below run against the real
    spread of the corpus.
    """
    full = (M.load_row_universe()
            .sort_values(["filing_date", "accession_number"])
            .reset_index(drop=True))                  # time-ordered
    stride = max(1, len(full) // SMOKE_N)
    sample = full.iloc[::stride].head(SMOKE_N).copy()  # deterministic
    with mock.patch.object(M, "load_row_universe", lambda **kw: sample):
        df, extra = M.build(verbose=False)
    return df, extra


def test_smoke_sample_spans_the_corpus(smoke):
    """The sample is the stride sample, not one company's head."""
    df, _ = smoke
    assert df["cik"].nunique() > 50
    assert df["filing_date"].dt.year.nunique() >= 10
    assert df["filing_date"].is_monotonic_increasing


def test_smoke_shape_and_key(smoke):
    df, _ = smoke
    assert len(df) == SMOKE_N
    assert not df.duplicated(["cik", "accession_number"]).any()
    for col in M.ALL_FEATURES:
        assert col in df.columns
    assert df["stratum"].eq("core").all()


def test_smoke_no_fact_dated_after_info_date_reaches_a_row(smoke):
    """End-to-end C1/C2 check: for every row and every family it used, the
    fact's `filed` date is <= the row's info_date, and its period_end is
    within the staleness guard."""
    df, _ = smoke
    fund = M.load_fundamentals(set(df["cik"].unique()))
    slices = M.slice_by_cik_tag(fund)
    checked = 0
    for r in df.itertuples(index=False):
        for family in M.NEEDED_FAMILIES:
            tag = getattr(r, f"tag_{family}")
            if not isinstance(tag, str):
                continue
            row, _ = M.resolve_family_value(slices, [tag], int(r.cik), r.info_date)
            assert row is not None
            assert pd.Timestamp(row["filed"]) <= pd.Timestamp(r.info_date)
            assert (pd.Timestamp(r.info_date) - pd.Timestamp(row["period_end"])).days \
                <= F1.STALENESS_MAX_DAYS
            checked += 1
    assert checked > 500, checked


def test_smoke_sessions_are_strictly_ordered(smoke):
    df, _ = smoke
    have = df.dropna(subset=["news_session", "pre_session"])
    assert len(have) == len(df)
    assert (have["pre_session"] < have["news_session"]).all()
    assert (have["info_date"] >= have["filing_date"]).all()
    assert (have["news_session"] >= have["info_date"]).all()


def test_smoke_unresolved_pairs_are_logged_and_null_their_features(smoke):
    df, extra = smoke
    unresolved = extra["unresolved"]
    assert len(unresolved) > 0, "expected at least one UNRESOLVED pair in the smoke"
    for r in unresolved.itertuples(index=False):
        rows = df[df["cik"] == r.cik]
        for feature, fams in M.FEATURE_FAMILIES.items():
            if r.family in fams:
                assert rows[feature].isna().all(), (r.cik, r.family, feature)
        assert r.severity == "UNRESOLVED"


def test_smoke_diagnostics_are_present_and_freeze_clean(smoke):
    _, extra = smoke
    d = extra["diagnostics"]
    assert d["network_calls"] == 0
    assert d["computed_associations_with_returns"] == 0
    assert set(d["coverage_overall"]) == set(M.ALL_FEATURES)
    assert d["staleness_guard"]["constant_STALENESS_MAX_DAYS"] == 200
    assert d["constants"]["momentum_lookback_sessions"] == 126
    assert d["constants"]["vol_window_sessions"] == 63
    # Both price-censoring channels are reported side by side, never merged.
    c = d["counters"]
    assert c["rows_without_price_coverage"] >= 0
    assert c["ciks_without_price_coverage"] >= 0
    assert c["rows_with_price_column_but_no_usable_history"] >= 0
    assert c["ciks_with_price_column_but_no_usable_history"] >= 0
