"""
test_phase_c_leakage.py -- the four leakage-critical properties that
HANDOFF.md §7's standing rules and ROADMAP.md Phase C treat as
non-negotiable for the walk-forward backtest. Four properties, covered by
35 tests in this file:

  1. Target window starts strictly after filing_date.
  2. The PIT join (features.py's concept-family resolution, built on top of
     pit.value_as_of()) returns the pre-restatement value for as-of dates
     before a restatement's filed date, and the restated value after.
  3. Every-occurrence attribution never attaches a label to a filing dated
     before the label's own source text existed (no backward flow).
  4. Walk-forward folds never contain training rows with filing_date >= any
     test row's filing_date.

Added for Phase C; it does not modify any existing pipeline/spotcheck/
finetune file or test. SLOW (~90s): several tests re-read the full corpus
(labels.parquet, fundamentals.parquet, prices.parquet) rather than a
fixture, deliberately, so the invariants are checked at real scale.

Run with: python3 -m pytest test_phase_c_leakage.py -v
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import backtest as B
import features as F


# ---------------------------------------------------------------------------
# 1. Target window starts strictly after filing_date
# ---------------------------------------------------------------------------


def test_target_start_date_always_strictly_after_filing_date_synthetic():
    """Synthetic price panel with a price ON the filing_date itself, to make
    sure the off-by-one direction is right (a naive `searchsorted(...,
    side="left")` or an unguarded `>=` would return the filing_date itself
    as the entry date)."""
    dates = pd.date_range("2024-01-01", periods=20, freq="B")
    prices = pd.Series(np.linspace(100, 119, 20), index=dates)
    panel = {"AAA": prices, "BBB": prices * 1.01, "CCC": prices * 0.99}

    filing_date = dates[5]  # a date that IS itself a trading day in the panel
    base = pd.DataFrame(
        [{"ticker": "AAA", "accession_number": "ACC-1", "filing_date": filing_date}]
    )
    target = F.build_target(base, panel, ["AAA", "BBB", "CCC"], holding_days=5)
    row = target.iloc[0]
    assert row["target_start_date"] > filing_date
    assert row["target_start_date"] == dates[6]  # first trading day strictly after


def test_target_start_date_never_on_or_before_filing_date_real_data():
    df = pd.read_parquet(F.FEATURES_OUTPUT)
    usable = df[df["target_start_date"].notna()]
    assert len(usable) > 0
    violations = usable[pd.to_datetime(usable["target_start_date"]) <= pd.to_datetime(usable["filing_date"])]
    assert violations.empty, f"{len(violations)} observations have a target start_date on or before filing_date"


def test_target_end_date_after_start_date_real_data():
    df = pd.read_parquet(F.FEATURES_OUTPUT)
    usable = df[df["target_excess_return"].notna()]
    assert len(usable) > 0
    bad = usable[pd.to_datetime(usable["target_end_date"]) <= pd.to_datetime(usable["target_start_date"])]
    assert bad.empty


def test_target_never_uses_a_filing_date_that_is_a_weekend_as_entry():
    """The searchsorted-based entry point should always land on an actual
    priced trading day, never silently invent one."""
    df = pd.read_parquet(F.FEATURES_OUTPUT)
    panel = F.load_price_panel()
    usable = df[df["target_start_date"].notna()]
    for ticker, sub in usable.groupby("ticker"):
        s = panel[ticker]
        starts = pd.to_datetime(sub["target_start_date"].dropna().unique())
        missing = [d for d in starts if d not in s.index]
        assert not missing, f"{ticker} has target_start_date values absent from its own price index: {missing[:5]}"


# ---------------------------------------------------------------------------
# 2. PIT join: pre-restatement value before, restated value after
# ---------------------------------------------------------------------------


def _make_synthetic_fundamentals() -> pd.DataFrame:
    """One concept, one company, one period, reported originally and then
    restated with a materially different value at a later filed date."""
    rows = [
        {
            "ticker": "ZZZ", "cik": 999999, "taxonomy": "us-gaap", "concept": "NetIncomeLoss",
            "unit": "USD", "value": 100.0, "fy": 2024.0, "fp": "Q1",
            "period_start": "2024-01-01", "period_end": "2024-03-31",
            "form": "10-Q", "accession_number": "0000000000-24-000001", "filed": "2024-05-01",
        },
        {
            # Restatement: same period, later filed, different value.
            "ticker": "ZZZ", "cik": 999999, "taxonomy": "us-gaap", "concept": "NetIncomeLoss",
            "unit": "USD", "value": 55.0, "fy": 2024.0, "fp": "Q1",
            "period_start": "2024-01-01", "period_end": "2024-03-31",
            "form": "10-Q", "accession_number": "0000000000-24-000099", "filed": "2024-08-15",
        },
    ]
    return pd.DataFrame(rows)


def test_pit_returns_original_value_before_restatement_filed():
    fund = _make_synthetic_fundamentals()
    row, concept = F.resolve_family_value(fund, "NetIncomeLoss", "ZZZ", 999999, as_of="2024-06-01")
    assert row is not None
    assert row["value"] == 100.0
    assert concept == "NetIncomeLoss"


def test_pit_returns_restated_value_on_and_after_restatement_filed():
    fund = _make_synthetic_fundamentals()
    row, _ = F.resolve_family_value(fund, "NetIncomeLoss", "ZZZ", 999999, as_of="2024-08-15")
    assert row is not None
    assert row["value"] == 55.0

    # "Well after" the restatement, but still deliberately inside
    # STALENESS_MAX_DAYS of the fact's own period_end (2024-03-31) --
    # updated for the BLOCKER #1 staleness-guard fix (red-team review):
    # this fixture's original as_of ("2025-01-01", 276 days past period_end)
    # predates that guard and would now be legitimately discarded as stale,
    # which is a DIFFERENT property than the one this test exists to check
    # (restatement-acceptance timing, not staleness). "2024-10-01" is 184
    # days past period_end (< STALENESS_MAX_DAYS=200) and still 47 days
    # after the restatement's filed date -- "well after" for this test's
    # actual purpose, without conflating the two concerns.
    row_later, _ = F.resolve_family_value(fund, "NetIncomeLoss", "ZZZ", 999999, as_of="2024-10-01")
    assert row_later is not None
    assert row_later["value"] == 55.0


def test_pit_returns_none_before_original_filed_date():
    fund = _make_synthetic_fundamentals()
    row, concept = F.resolve_family_value(fund, "NetIncomeLoss", "ZZZ", 999999, as_of="2024-04-01")
    assert row is None
    assert concept is None


def test_pit_alt_tag_family_uses_freshest_period_end_not_first_priority():
    """Regression test for the bug caught while building features.py:
    resolve_family_value/resolve_concept_family must pick the candidate
    with the most recent period_end across the whole family, not
    "primary tag if it returns anything at all, even a decade-stale row."""
    rows = [
        {
            "ticker": "MIGRATE", "cik": 111, "taxonomy": "us-gaap", "concept": "NetIncomeLoss",
            "unit": "USD", "value": 1.0, "fy": 2014.0, "fp": "Q1",
            "period_start": "2014-01-01", "period_end": "2014-03-31",
            "form": "10-Q", "accession_number": "0000000000-14-000001", "filed": "2014-05-01",
        },
        {
            "ticker": "MIGRATE", "cik": 111, "taxonomy": "us-gaap", "concept": "ProfitLoss",
            "unit": "USD", "value": 999.0, "fy": 2024.0, "fp": "Q1",
            "period_start": "2024-01-01", "period_end": "2024-03-31",
            "form": "10-Q", "accession_number": "0000000000-24-000001", "filed": "2024-05-01",
        },
    ]
    fund = pd.DataFrame(rows)
    alt_map = {"NetIncomeLoss": {"MIGRATE": ["ProfitLoss"]}}
    old_map = dict(F.ALT_TAG_FAMILIES)
    F.ALT_TAG_FAMILIES = {**old_map, **alt_map}
    try:
        row, concept = F.resolve_family_value(fund, "NetIncomeLoss", "MIGRATE", 111, as_of="2024-06-01")
    finally:
        F.ALT_TAG_FAMILIES = old_map
    assert concept == "ProfitLoss", "must prefer the fresher alt tag over a stale primary-tag row"
    assert row["value"] == 999.0


# ---------------------------------------------------------------------------
# 2b. Staleness guard (BLOCKER #1 fix, red-team review): a resolved fact
# must never be used if its period_end is stale beyond STALENESS_MAX_DAYS
# relative to its observation's as_of/filing_date.
# ---------------------------------------------------------------------------


def test_staleness_guard_discards_fact_older_than_max_days_synthetic():
    """A family with exactly one member, whose only row is stale beyond
    STALENESS_MAX_DAYS, must resolve to None -- the JNJ OperatingIncomeLoss
    failure mode in miniature."""
    rows = [
        {
            "ticker": "STALE", "cik": 222, "taxonomy": "us-gaap", "concept": "OperatingIncomeLoss",
            "unit": "USD", "value": 42.0, "fy": 2015.0, "fp": "Q1",
            "period_start": "2015-01-01", "period_end": "2015-03-31",
            "form": "10-Q", "accession_number": "0000000000-15-000001", "filed": "2015-05-01",
        },
    ]
    fund = pd.DataFrame(rows)
    row, concept = F.resolve_family_value(fund, "OperatingIncomeLoss", "STALE", 222, as_of="2024-01-01")
    assert row is None
    assert concept is None


def test_staleness_guard_boundary_exactly_at_threshold_is_allowed():
    """period_end exactly STALENESS_MAX_DAYS before as_of is NOT stale
    (_is_stale() fires on strictly MORE than STALENESS_MAX_DAYS); one day
    further is discarded."""
    period_end = pd.Timestamp("2024-01-01")
    as_of_exact = period_end + pd.Timedelta(days=F.STALENESS_MAX_DAYS)
    as_of_over = period_end + pd.Timedelta(days=F.STALENESS_MAX_DAYS + 1)
    rows = [
        {
            "ticker": "EDGE", "cik": 333, "taxonomy": "us-gaap", "concept": "Assets",
            "unit": "USD", "value": 7.0, "fy": 2024.0, "fp": "Q1",
            "period_start": None, "period_end": "2024-01-01",
            "form": "10-Q", "accession_number": "0000000000-24-000001", "filed": "2024-01-02",
        },
    ]
    fund = pd.DataFrame(rows)
    row_exact, _ = F.resolve_single_concept(fund, "Assets", "EDGE", 333, as_of=as_of_exact)
    assert row_exact is not None, "exactly STALENESS_MAX_DAYS old must still be usable"
    row_over, _ = F.resolve_single_concept(fund, "Assets", "EDGE", 333, as_of=as_of_over)
    assert row_over is None, f"{F.STALENESS_MAX_DAYS + 1} days stale must be discarded"


def test_staleness_guard_logs_discarded_candidate():
    rows = [
        {
            "ticker": "LOGGED", "cik": 444, "taxonomy": "us-gaap", "concept": "OperatingIncomeLoss",
            "unit": "USD", "value": 1.0, "fy": 2015.0, "fp": "Q1",
            "period_start": "2015-01-01", "period_end": "2015-03-31",
            "form": "10-Q", "accession_number": "0000000000-15-000001", "filed": "2015-05-01",
        },
    ]
    fund = pd.DataFrame(rows)
    log: list = []
    row, concept = F.resolve_family_value(
        fund, "OperatingIncomeLoss", "LOGGED", 444, as_of="2024-01-01", staleness_log=log
    )
    assert row is None
    assert len(log) == 1
    assert log[0]["ticker"] == "LOGGED"
    assert log[0]["days_stale"] > F.STALENESS_MAX_DAYS


def test_staleness_guard_does_not_fire_on_fresh_data_synthetic():
    """Sanity check on the other direction: a fresh row must NOT be
    discarded (the guard must not be over-eager)."""
    rows = [
        {
            "ticker": "FRESH", "cik": 555, "taxonomy": "us-gaap", "concept": "Assets",
            "unit": "USD", "value": 100.0, "fy": 2024.0, "fp": "Q1",
            "period_start": None, "period_end": "2024-03-31",
            "form": "10-Q", "accession_number": "0000000000-24-000001", "filed": "2024-05-01",
        },
    ]
    fund = pd.DataFrame(rows)
    log: list = []
    row, _ = F.resolve_single_concept(fund, "Assets", "FRESH", 555, as_of="2024-06-01", staleness_log=log)
    assert row is not None
    assert row["value"] == 100.0
    assert log == []


def test_jpm_bac_cash_alt_tag_resolves_fresh_not_stale_real_corpus():
    """Regression test for the JPM/BAC CashAndDueFromBanks fix (BLOCKER #1a):
    with the real ALT_TAG_FAMILIES entry in place, resolve_family_value()
    for CashAndCashEquivalentsAtCarryingValue must resolve to a fresh
    CashAndDueFromBanks row (not the stale base tag, not None) for a
    representative real corpus as_of date."""
    universe = F.load_universe()
    fund_primary = F.load_fundamentals_form_filtered()
    alt = F.load_supplemental_alt_tags(universe)
    fund = pd.concat([fund_primary, alt], ignore_index=True)
    for ticker, cik in (("JPM", 19617), ("BAC", 70858)):
        row, concept = F.resolve_family_value(
            fund, "CashAndCashEquivalentsAtCarryingValue", ticker, cik, as_of="2026-08-06"
        )
        assert row is not None, f"{ticker} cash should resolve to a fresh value, not None"
        assert concept == "CashAndDueFromBanks", (
            f"{ticker} should resolve via the CashAndDueFromBanks alt tag, got {concept}"
        )


def test_jnj_operating_income_resolves_to_none_real_corpus():
    """Regression test for the JNJ OperatingIncomeLoss fix (BLOCKER #1a):
    JNJ has never reported this tag in the corpus window (freshest-ever row
    is 2015-03-29) -- must resolve to None/NaN for a real in-window as_of
    date, not the stale 2015 figure."""
    fund = F.load_fundamentals_form_filtered()
    row, concept = F.resolve_family_value(fund, "OperatingIncomeLoss", "JNJ", 200406, as_of="2024-04-16")
    assert row is None
    assert concept is None


def test_no_resolved_fact_is_stale_beyond_guard():
    """THE permanent regression test (BLOCKER #1c). Sweeps every REAL
    numeric feature this build actually resolves, for every real filing
    observation in the live corpus (not a synthetic fixture), and asserts
    none of them is more than STALENESS_MAX_DAYS stale relative to its own
    filing_date. Two checks:
      (1) build_numeric_features()'s own staleness_log never logs a
          discard that wasn't actually stale (internal consistency).
      (2) An independent, from-scratch re-resolution of every numeric
          concept family for every real observation confirms every
          NON-discarded (non-None) result is within the guard's threshold
          -- this would fail if the guard were ever bypassed at one call
          site while still logging correctly at others.
    Also asserts the guard actually fires on this build's two known real
    cases (JNJ OperatingIncomeLoss, MRK OCF) so this test cannot silently
    pass by checking nothing.
    """
    universe = F.load_universe()
    filings_base = F.load_filings_base()
    numeric_features, staleness_log = F.build_numeric_features(filings_base, universe)

    for entry in staleness_log:
        assert entry["days_stale"] > F.STALENESS_MAX_DAYS

    fund_primary = F.load_fundamentals_form_filtered()
    alt = F.load_supplemental_alt_tags(universe)
    fund = pd.concat([fund_primary, alt], ignore_index=True) if not alt.empty else fund_primary

    concept_families = [
        ("Assets", None),
        ("Liabilities", None),
        ("StockholdersEquity", F.ALT_TAG_FAMILIES.get("StockholdersEquity", {})),
        ("CashAndCashEquivalentsAtCarryingValue", F.ALT_TAG_FAMILIES.get("CashAndCashEquivalentsAtCarryingValue", {})),
        ("NetIncomeLoss", F.ALT_TAG_FAMILIES.get("NetIncomeLoss", {})),
        ("OperatingIncomeLoss", F.ALT_TAG_FAMILIES.get("OperatingIncomeLoss", {})),
        ("NetCashProvidedByUsedInOperatingActivities", None),
        ("EarningsPerShareDiluted", None),
    ]

    n_checked = 0
    for row in filings_base.itertuples(index=False):
        ticker, cik, as_of = row.ticker, row.cik, row.filing_date
        for base_concept, alt_map in concept_families:
            concepts = [base_concept] + (alt_map.get(ticker, []) if alt_map else [])
            resolved, _ = F.resolve_concept_family(fund, concepts, ticker, cik, as_of)
            n_checked += 1
            if resolved is None:
                continue
            days_stale = (pd.Timestamp(as_of) - pd.Timestamp(resolved["period_end"])).days
            assert days_stale <= F.STALENESS_MAX_DAYS, (
                f"{ticker}/{base_concept} resolved a fact {days_stale} days stale as of "
                f"{as_of} (accession {row.accession_number}) -- staleness guard violated."
            )
        resolved, _ = F.resolve_concept_family(fund, F.REVENUE_FAMILY_ORDER, ticker, cik, as_of)
        n_checked += 1
        if resolved is not None:
            days_stale = (pd.Timestamp(as_of) - pd.Timestamp(resolved["period_end"])).days
            assert days_stale <= F.STALENESS_MAX_DAYS, (
                f"{ticker}/revenue resolved a fact {days_stale} days stale as of {as_of} "
                f"(accession {row.accession_number}) -- staleness guard violated."
            )

    assert n_checked > 0
    logged_pairs = {(e["ticker"], e["concept_family"]) for e in staleness_log}
    assert ("JNJ", "OperatingIncomeLoss") in logged_pairs, (
        "expected the guard to have fired for JNJ/OperatingIncomeLoss on the real corpus -- "
        "if this assertion fails, either the underlying data changed or the guard regressed."
    )
    assert ("MRK", "NetCashProvidedByUsedInOperatingActivities") in logged_pairs, (
        "expected the guard to have fired for MRK's one 208-day-stale OCF observation -- "
        "if this assertion fails, either the underlying data changed or the guard regressed."
    )


# ---------------------------------------------------------------------------
# 3. Every-occurrence attribution: no backward flow
# ---------------------------------------------------------------------------


def test_no_occurrence_predates_its_own_home_filing_date():
    labels = F.load_labels()
    mins = labels["source_filing_dates"].apply(lambda arr: min(arr))
    home = pd.to_datetime(labels["home_filing_date"])
    mins = pd.to_datetime(mins)
    violations = labels[mins.values < home.values]
    assert violations.empty, (
        f"{len(violations)} chunks have an occurrence filing date earlier than their own "
        "home_filing_date -- every-occurrence attribution must never flow backward in time."
    )


def test_attach_company_raises_on_synthetic_backward_flow():
    """attach_company_and_verify_no_backward_flow() must actively detect and
    raise on a backward-flow row, not just happen to pass on real data."""
    filings_base = pd.DataFrame(
        [
            {"ticker": "AAA", "cik": 1, "accession_number": "ACC-EARLY", "filing_date": pd.Timestamp("2024-01-01"), "form": "10-Q"},
            {"ticker": "AAA", "cik": 1, "accession_number": "ACC-LATE", "filing_date": pd.Timestamp("2024-06-01"), "form": "10-Q"},
        ]
    )
    acc_map = F.build_accession_to_company_map(filings_base)

    occ = pd.DataFrame(
        [
            {
                "chunk_id": "CHK-TEST",
                "occurrence_accession_number": "ACC-EARLY",
                # This occurrence claims a filing_date BEFORE its own chunk's
                # home_filing_date -- a synthetic backward-flow violation.
                "occurrence_filing_date": pd.Timestamp("2023-01-01"),
                "occurrence_form": "10-Q",
                "home_accession_number": "ACC-LATE",
                "home_filing_date": pd.Timestamp("2024-06-01"),
                "section_type": "MDA",
                "sentiment": "NEUTRAL",
                "guidance_direction": None,
                "red_flags": [],
            }
        ]
    )
    with pytest.raises(AssertionError, match="backward"):
        F.attach_company_and_verify_no_backward_flow(occ, acc_map)


def test_every_occurrence_accession_number_resolves_to_exactly_one_ticker():
    filings_base = F.load_filings_base()
    acc_map = F.build_accession_to_company_map(filings_base)
    assert acc_map["accession_number"].is_unique


def test_features_output_has_no_backward_flow_in_source_data():
    """End-to-end: re-run the exploded-occurrence attach step against the
    real corpus and confirm it does not raise (it would raise on any
    backward-flow row -- see attach_company_and_verify_no_backward_flow)."""
    filings_base = F.load_filings_base()
    labels = F.load_labels()
    acc_map = F.build_accession_to_company_map(filings_base)
    occ = F.explode_label_occurrences(labels)
    attached = F.attach_company_and_verify_no_backward_flow(occ, acc_map)
    assert len(attached) > 0


# ---------------------------------------------------------------------------
# 4. Walk-forward folds: no training row's filing_date >= any test row's
# ---------------------------------------------------------------------------


def test_walk_forward_folds_no_leakage_real_data():
    df, _ = B.load_modeling_frame()
    folds = B.build_walk_forward_folds(df, B.BURN_IN_END)
    assert len(folds) > 0
    B.assert_no_fold_leakage(df, folds)  # must not raise


def test_walk_forward_folds_are_expanding_not_shuffled():
    df, _ = B.load_modeling_frame()
    folds = B.build_walk_forward_folds(df, B.BURN_IN_END)
    prev_train_size = 0
    for fold in folds:
        assert len(fold["train_idx"]) >= prev_train_size
        prev_train_size = len(fold["train_idx"])
        # every train index must correspond to a filing_date strictly before
        # every test index's filing_date (redundant with assert_no_fold_leakage,
        # checked directly here too because this is the exact invariant
        # HANDOFF.md §7's walk-forward standing rule names).
        train_dates = df.loc[fold["train_idx"], B.FILING_DATE_COL]
        test_dates = df.loc[fold["test_idx"], B.FILING_DATE_COL]
        assert train_dates.max() < test_dates.min()


def test_assert_no_fold_leakage_detects_synthetic_violation():
    dates = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame({B.FILING_DATE_COL: dates, B.TARGET_COL: np.arange(10.0)})
    bad_folds = [{"test_quarter": "FAKE", "train_idx": np.array([0, 1, 8]), "test_idx": np.array([5, 6, 7])}]
    with pytest.raises(AssertionError, match="leakage"):
        B.assert_no_fold_leakage(df, bad_folds)


def test_walk_forward_folds_never_empty_train_or_test():
    df, _ = B.load_modeling_frame()
    folds = B.build_walk_forward_folds(df, B.BURN_IN_END)
    for fold in folds:
        assert len(fold["train_idx"]) > 0
        assert len(fold["test_idx"]) > 0


# ---------------------------------------------------------------------------
# 5. Company-quarter deduplication (MAJOR #3, red-team review)
# ---------------------------------------------------------------------------


def test_assign_company_quarter_clusters_groups_close_same_ticker_filings():
    df = pd.DataFrame(
        {
            "ticker": ["AAA", "AAA", "AAA", "BBB"],
            B.FILING_DATE_COL: pd.to_datetime(
                ["2024-01-01", "2024-01-02", "2024-04-01", "2024-01-01"]
            ),
        }
    )
    clusters = B.assign_company_quarter_clusters(df, gap_days=5)
    # Rows 0,1 (AAA, 1 day apart) share a cluster; row 2 (AAA, ~90 days
    # later) is its own cluster; row 3 (BBB, different ticker) is its own
    # cluster even though its date coincides with row 0's.
    assert clusters.iloc[0] == clusters.iloc[1]
    assert clusters.iloc[2] != clusters.iloc[0]
    assert clusters.iloc[3] != clusters.iloc[0]


def test_company_quarter_dedup_keep_mask_keeps_later_filing():
    df = pd.DataFrame(
        {
            "ticker": ["AAA", "AAA"],
            B.FILING_DATE_COL: pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "form": ["8-K", "10-Q"],
            "accession_number": ["0000000000-24-000001", "0000000000-24-000002"],
        }
    )
    mask = B.company_quarter_dedup_keep_mask(df, gap_days=5)
    assert mask.tolist() == [False, True]


def test_company_quarter_dedup_keep_mask_same_day_tiebreak_is_form_aware():
    """Same filing_date: a 10-Q/10-K must beat any other form REGARDLESS of
    accession-number order. This pins the fix for the real SLB 2025-04-25
    counterexample (different filing agents gave the 8-K the larger
    accession number, so a pure accession tiebreak kept the wrong row --
    caught by the 2026-08-18 re-verification)."""
    df = pd.DataFrame(
        {
            "ticker": ["AAA", "AAA"],
            B.FILING_DATE_COL: pd.to_datetime(["2024-01-01", "2024-01-01"]),
            # 8-K has the LARGER accession (the SLB shape) -- 10-Q must still win.
            "form": ["8-K", "10-Q"],
            "accession_number": ["0001193125-24-000009", "0000950170-24-000001"],
        }
    )
    mask = B.company_quarter_dedup_keep_mask(df, gap_days=5)
    assert mask.tolist() == [False, True]


def test_company_quarter_dedup_keep_mask_same_day_same_form_tiebreak_by_accession():
    """When forms tie (both 10-Q, or both non-10-Q/K), the larger
    accession_number breaks the tie."""
    df = pd.DataFrame(
        {
            "ticker": ["AAA", "AAA"],
            B.FILING_DATE_COL: pd.to_datetime(["2024-01-01", "2024-01-01"]),
            "form": ["8-K", "8-K"],
            "accession_number": ["0000000000-24-000002", "0000000000-24-000001"],
        }
    )
    mask = B.company_quarter_dedup_keep_mask(df, gap_days=5)
    assert mask.tolist() == [True, False]


def test_company_quarter_dedup_keep_mask_singleton_always_kept():
    df = pd.DataFrame(
        {
            "ticker": ["AAA", "BBB"],
            B.FILING_DATE_COL: pd.to_datetime(["2024-01-01", "2024-06-01"]),
            "form": ["10-K", "10-Q"],
            "accession_number": ["A-1", "B-1"],
        }
    )
    mask = B.company_quarter_dedup_keep_mask(df, gap_days=5)
    assert mask.tolist() == [True, True]


def test_company_quarter_clusters_real_data_never_exceed_size_two():
    """Empirical justification check for COMPANY_QUARTER_DEDUP_GAP_DAYS=5:
    on the real backtest frame, no cluster should ever contain 3+ filings
    (verified during development up to gap_days=14) -- if this regresses,
    the dedup keep-mask's 'keep exactly one row' assumption silently
    starts discarding more than intended per event."""
    df, _ = B.load_modeling_frame()
    clusters = B.assign_company_quarter_clusters(df, gap_days=B.COMPANY_QUARTER_DEDUP_GAP_DAYS)
    sizes = clusters.value_counts()
    assert sizes.max() <= 2, f"found a cluster of size {sizes.max()} > 2 at gap_days={B.COMPANY_QUARTER_DEDUP_GAP_DAYS}"


def test_dedup_keep_mask_real_data_one_row_per_cluster():
    df, _ = B.load_modeling_frame()
    mask = B.company_quarter_dedup_keep_mask(df)
    clusters = B.assign_company_quarter_clusters(df)
    n_clusters = clusters.nunique()
    assert int(mask.sum()) == n_clusters


# ---------------------------------------------------------------------------
# 6. Form-controlled ablation (MAJOR #4, red-team review)
# ---------------------------------------------------------------------------


def test_form_controlled_ablation_only_contains_10q_10k():
    df, _ = B.load_modeling_frame()
    df_form, folds_form, results_form = B.run_form_controlled_ablation(df, B.BURN_IN_END)
    assert set(df_form["form"].unique()) <= {"10-Q", "10-K"}
    assert "8-K" not in set(df_form["form"].unique())
    assert len(df_form) < len(df)


def test_form_controlled_ablation_folds_no_leakage():
    df, _ = B.load_modeling_frame()
    df_form, folds_form, results_form = B.run_form_controlled_ablation(df, B.BURN_IN_END)
    assert len(folds_form) > 0
    B.assert_no_fold_leakage(df_form, folds_form)  # must not raise


def test_form_controlled_ablation_results_have_both_models():
    df, _ = B.load_modeling_frame()
    df_form, folds_form, results_form = B.run_form_controlled_ablation(df, B.BURN_IN_END)
    assert set(results_form.keys()) == {"numeric_only", "text_and_numeric"}
    assert len(results_form["numeric_only"]) == len(folds_form)
    assert len(results_form["text_and_numeric"]) == len(folds_form)


# ---------------------------------------------------------------------------
# 7. Section-rate red-flag NaN-vs-0 missingness policy (MINOR #8, red-team
# review): redflag_*_rate_riskfactors/_mda/_press must be NaN, not 0, when
# their section has zero attributed chunks for that observation.
# ---------------------------------------------------------------------------


def test_redflag_rate_is_nan_not_zero_when_section_has_no_chunks_real_data():
    df = pd.read_parquet(F.FEATURES_OUTPUT)
    # Every observation with n_chunks_risk_factors == 0 (or, since that
    # count column is 0-filled, equivalently NOT among the filings that had
    # >=1 RISK_FACTORS chunk attributed) must have NaN, not 0.0, for every
    # redflag_<CATEGORY>_rate_riskfactors column.
    riskfactors_rate_cols = [c for c in df.columns if c.startswith("redflag_") and c.endswith("_rate_risk_factors")]
    assert riskfactors_rate_cols, "expected at least one redflag_*_rate_risk_factors column in features.parquet"
    zero_section = df[df["n_chunks_risk_factors"] == 0]
    assert len(zero_section) > 0
    for c in riskfactors_rate_cols:
        assert zero_section[c].isna().all(), (
            f"{c} should be NaN (not 0.0) for every observation with zero attributed "
            "RISK_FACTORS chunks -- MINOR #8 fix regressed."
        )


def test_redflag_any_rate_press_is_nan_when_no_press_chunks_real_data():
    df = pd.read_parquet(F.FEATURES_OUTPUT)
    # A 10-K/10-Q with zero attributed press-release chunks should show NaN,
    # not a confident 0.0, for redflag_any_rate_press.
    no_press = df[(df["form"].isin(["10-Q", "10-K"])) & (df["share_chunks_ex99_press_release"] == 0.0)]
    assert len(no_press) > 0
    assert no_press["redflag_any_rate_press"].isna().all()


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
