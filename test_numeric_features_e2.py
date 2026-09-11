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
