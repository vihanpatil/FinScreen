"""
test_build_universe_e2.py -- offline tests for the E2 phase-F1 universe builder.

No network. Everything up to TestBuiltArtifacts constructs its own facts; the
final class reads the built tables and SKIPS cleanly if the build has not been
run. What is pinned here is what would silently corrupt every downstream
walk-forward result if it broke:

  1. the POINT-IN-TIME rule (a float fact filed on/after the reconstitution
     date must never be used, and the finished table is re-asserted),
  2. the BACKWARD-ONLY eligibility rule (never a forward-looking continuity
     condition -- EXPANSION_PLAN.md §2c),
  3. SIC -> sector determinism (same input, same answer, no overlapping ranges,
     no accidental drift between the taxonomy variants),
  4. STRATUM INTEGRITY for the ratified `hybrid136` universe: its core stratum
     reproduces `continuity5`'s membership exactly at every date, its extension
     stratum reproduces `broad8`'s three non-core buckets exactly and never
     contains a core-sector CIK, and neither option-record variant gains a
     `stratum` column,
  5. MANUAL EXCLUSIONS: honoured, scoped by variant and by date, always logged
     with reason + evidence, never able to encode hindsight (a dated exclusion
     resting on evidence that was not yet public is refused at load time),
  6. DETERMINISM: same inputs -> same table, independent of candidate ordering,
  7. THE TWO RATIFIED FLOAT-INTEGRITY RULES (owner, in chat, 2026-08-21):
     `newer_zero_float` and `min_public_shares` are point-in-time, only ever
     remove, fire only on an unambiguous signal, log their evidence -- and are
     SCOPED TO hybrid136, so continuity5/broad8 come out bit-for-bit identical
     even with the triggering data sitting in front of them,
  8. THE FROZEN OPTION RECORD: the continuity5/broad8 artifacts still hash to
     the values captured before those rules existed, and the
     `superseded_by_rule` annotations on manual_exclusions.csv are backed by an
     actual rule firing at every date they claim.

Run: python3 -m pytest test_build_universe_e2.py -q
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from build_universe_e2 import (
    BROAD8_K,
    BROAD8_SECTORS,
    CONTINUITY5_K,
    CONTINUITY5_SECTORS,
    EXCLUDED,
    HYBRID136_CORE_K,
    HYBRID136_CORE_SECTORS,
    HYBRID136_EXTENSION_K,
    HYBRID136_EXTENSION_SECTORS,
    HYBRID136_K,
    HYBRID136_SECTORS,
    HYBRID136_STRATUM,
    AUDIT_MAX_FLOAT_TO_ASSETS,
    AUDIT_MIN_PUBLIC_SHARES,
    FLOAT_INTEGRITY_RULESET,
    FLOAT_INTEGRITY_RULE_NAMES,
    FLOAT_RULE_MIN_SHARES,
    FLOAT_RULE_NEWER_ZERO,
    LEGACY_RULESET,
    MANUAL_EXCLUSION_COLUMNS,
    MAX_FLOAT_STALENESS_DAYS,
    MIN_ELIGIBLE_QUARTERS,
    MIN_PUBLIC_SHARES_FOR_MEMBERSHIP,
    MIN_SHARES_MAX_STALENESS_DAYS,
    NON_OPERATING_SIC,
    OPTION_RECORD_VARIANTS,
    RATIFIED_VARIANT,
    SIC_EXACT,
    SIC_RANGES,
    STRATUM_CORE,
    STRATUM_EXTENSION,
    TAXONOMIES,
    TAXONOMY_STRATA,
    CikProfile,
    FloatFact,
    ManualExclusion,
    VARIANT_RULESETS,
    _assert_ranges_disjoint,
    _concept_rows,
    _match_concept_value,
    assert_pit_membership,
    below_min_public_shares_asof,
    build_membership,
    build_spells,
    count_periodic_in_window,
    eligible_quarters_covered,
    exclusions_in_force,
    is_eligible,
    load_manual_exclusions,
    newer_zero_float_asof,
    newest_public_float_facts,
    parse_float_facts,
    pit_float_asof,
    pit_shares_asof,
    quarters_preceding,
    reconstitution_dates,
    ruleset_for,
    sanitize_facts,
    sanitize_facts_with_reasons,
    sic_to_sector,
    stratum_of,
    verify_option_record_checksums,
)

D = date(2020, 7, 1)  # a representative reconstitution date


def ff(instant: str, filed: str, val: float = 100e9, accn: str = "a", form: str = "10-K") -> FloatFact:
    return FloatFact(
        cik=1, instant=date.fromisoformat(instant), filed=date.fromisoformat(filed),
        val=val, accn=accn, form=form,
    )


# ---------------------------------------------------------------------------
# 1. Point-in-time
# ---------------------------------------------------------------------------


class TestPointInTime:
    def test_fact_filed_after_recon_date_is_rejected(self):
        """The core guarantee. A float measured BEFORE the reconstitution date
        but DISCLOSED after it was not public information at that date."""
        future = ff(instant="2020-06-30", filed="2021-02-20")
        assert pit_float_asof([future], D) is None

    def test_fact_filed_on_recon_date_is_rejected(self):
        """Strictly-before, not on-or-before: intraday publication time is
        unknown, so a same-day filing is excluded (conservative direction)."""
        same_day = ff(instant="2019-06-28", filed="2020-07-01")
        assert pit_float_asof([same_day], D) is None

    def test_fact_filed_one_day_before_is_accepted(self):
        one_day = ff(instant="2019-06-28", filed="2020-06-30")
        got = pit_float_asof([one_day], D)
        assert got is not None and got.filed == date(2020, 6, 30)

    def test_picks_latest_public_fact_not_latest_measured(self):
        """Realistic Apple-shaped case: the newest measurement is not yet
        filed, so the older-but-public one must win."""
        stale_public = ff(instant="2019-06-28", filed="2019-10-31", val=90e9)
        fresh_secret = ff(instant="2020-03-27", filed="2020-10-30", val=150e9)
        got = pit_float_asof([stale_public, fresh_secret], D)
        assert got is not None
        assert got.val == 90e9, "used a value that was not public at the date"

    def test_amendment_supersedes_original_for_same_instant(self):
        original = ff(instant="2019-06-28", filed="2019-08-01", val=90e9)
        amended = ff(instant="2019-06-28", filed="2019-09-15", val=93e9)
        got = pit_float_asof([original, amended], D)
        assert got.val == 93e9

    def test_staleness_cap_excludes_ancient_facts(self):
        ancient = ff(instant="2016-06-30", filed="2016-08-01")
        assert pit_float_asof([ancient], D) is None
        edge_ok = ff(
            instant=(D - timedelta(days=MAX_FLOAT_STALENESS_DAYS)).isoformat(),
            filed="2018-08-01",
        )
        assert pit_float_asof([edge_ok], D) is not None

    def test_empty_history_returns_none(self):
        assert pit_float_asof([], D) is None

    def test_assert_pit_membership_raises_on_a_violating_row(self):
        bad = pd.DataFrame(
            [{"recon_date": "2020-07-01", "float_filed": "2020-07-02",
              "float_instant": "2020-06-30", "cik": 1}]
        )
        with pytest.raises(AssertionError, match="POINT-IN-TIME VIOLATION"):
            assert_pit_membership(bad)

    def test_assert_pit_membership_raises_on_same_day_filing(self):
        same = pd.DataFrame(
            [{"recon_date": "2020-07-01", "float_filed": "2020-07-01",
              "float_instant": "2019-06-28", "cik": 1}]
        )
        with pytest.raises(AssertionError):
            assert_pit_membership(same)

    def test_assert_pit_membership_passes_clean_table(self):
        ok = pd.DataFrame(
            [{"recon_date": "2020-07-01", "float_filed": "2020-02-20",
              "float_instant": "2019-06-28", "cik": 1}]
        )
        assert_pit_membership(ok)  # must not raise

    def test_parse_float_facts_keeps_the_filed_date(self):
        """Regression guard for the reason companyconcept is used at all:
        frames data points carry no `filed`, so anything that loses the filed
        date silently destroys the PIT guarantee."""
        concept = {
            "units": {
                "USD": [
                    {"end": "2019-06-28", "val": 1.0e11, "accn": "x", "filed": "2019-10-31",
                     "form": "10-K"},
                    {"end": "2020-03-27", "val": 1.5e11, "accn": "y", "filed": "2020-10-30",
                     "form": "10-K"},
                ]
            }
        }
        facts = parse_float_facts(320193, concept)
        assert len(facts) == 2
        assert all(f.filed is not None for f in facts)
        assert pit_float_asof(facts, D).accn == "x"

    def test_parse_float_facts_ignores_non_usd_units(self):
        concept = {"units": {"EUR": [{"end": "2019-06-28", "val": 1e11, "accn": "z",
                                      "filed": "2019-10-31", "form": "10-K"}]}}
        assert parse_float_facts(1, concept) == []


# ---------------------------------------------------------------------------
# 2. Eligibility (backward-only)
# ---------------------------------------------------------------------------


def quarterly_filings(start: date, n: int) -> list[date]:
    """n filings, one per quarter, ~91 days apart."""
    return [start + pd.Timedelta(days=91 * i) for i in range(n)]


def _d(x) -> date:
    return x.date() if hasattr(x, "date") else x


class TestEligibility:
    def test_quarters_preceding_are_the_eight_completed_calendar_quarters(self):
        qs = quarters_preceding(date(2020, 7, 1), 8)
        assert qs == [(2018, 3), (2018, 4), (2019, 1), (2019, 2),
                      (2019, 3), (2019, 4), (2020, 1), (2020, 2)]
        assert (2020, 3) not in qs, "the quarter containing D must not count"

    def test_eight_clean_quarters_is_eligible(self):
        dates = [_d(x) for x in quarterly_filings(date(2018, 8, 1), 8)]
        assert is_eligible(dates, D)
        assert eligible_quarters_covered(dates, D) == MIN_ELIGIBLE_QUARTERS

    def test_seven_quarters_is_not_eligible(self):
        dates = [_d(x) for x in quarterly_filings(date(2018, 11, 1), 7)]
        assert not is_eligible(dates, D)
        assert eligible_quarters_covered(dates, D) == 7

    def test_gap_in_the_middle_fails_even_with_enough_filings(self):
        """Two filings bunched into one quarter do not pay for a missed one --
        that is the difference between the strict and lenient rules."""
        dates = [_d(x) for x in quarterly_filings(date(2018, 8, 1), 8)]
        dates[3] = dates[2] + pd.Timedelta(days=5)  # move Q into the previous one
        dates = [_d(x) for x in dates]
        assert not is_eligible(dates, D)
        assert count_periodic_in_window(dates, D) >= MIN_ELIGIBLE_QUARTERS

    def test_filings_after_the_recon_date_never_count(self):
        """THE look-ahead test. A company whose filings all land after D must
        be ineligible AT D, no matter how healthy it looks later."""
        dates = [_d(x) for x in quarterly_filings(date(2020, 7, 2), 12)]
        assert not is_eligible(dates, D)
        assert eligible_quarters_covered(dates, D) == 0

    def test_company_that_dies_right_after_D_is_still_eligible_at_D(self):
        """The whole survivorship point: eligibility at D cannot depend on
        anything after D (EXPANSION_PLAN.md §2c rejects forward continuity)."""
        dates = [_d(x) for x in quarterly_filings(date(2018, 8, 1), 8)]
        assert is_eligible(dates, D)
        # adding no future filings at all changes nothing
        assert is_eligible(dates + [], D)

    def test_a_later_reconstitution_correctly_drops_the_dead_company(self):
        dates = [_d(x) for x in quarterly_filings(date(2018, 8, 1), 8)]
        assert not is_eligible(dates, date(2023, 7, 1))

    def test_extra_history_far_in_the_past_does_not_help(self):
        dates = [_d(x) for x in quarterly_filings(date(2010, 1, 1), 20)]
        assert not is_eligible(dates, D)


# ---------------------------------------------------------------------------
# 3. SIC -> sector determinism
# ---------------------------------------------------------------------------


class TestSicMapping:
    def test_ranges_are_disjoint(self):
        _assert_ranges_disjoint()  # must not raise

    def test_deterministic_across_calls(self):
        for sic in range(0, 10000):
            a = sic_to_sector(sic, "broad8")
            b = sic_to_sector(sic, "broad8")
            assert a == b
        assert sic_to_sector(2911, "broad8") == sic_to_sector(2911, "broad8")

    def test_every_sic_maps_to_a_known_sector_or_excluded(self):
        allowed = set(BROAD8_SECTORS) | {EXCLUDED}
        for sic in range(0, 10000):
            assert sic_to_sector(sic, "broad8") in allowed

    def test_continuity5_is_broad8_restricted_to_five_sectors(self):
        """The two variants must never DISAGREE about a company's sector, only
        about whether that sector exists."""
        for sic in range(0, 10000):
            b = sic_to_sector(sic, "broad8")
            c = sic_to_sector(sic, "continuity5")
            if b in CONTINUITY5_SECTORS:
                assert c == b
            else:
                assert c == EXCLUDED

    @pytest.mark.parametrize(
        "sic,expected",
        [
            (3571, "tech"),        # Apple - electronic computers
            (7372, "tech"),        # Microsoft - prepackaged software
            (7370, "tech"),        # Alphabet - computer programming/data processing
            (3674, "tech"),        # NVIDIA - semiconductors
            (3576, "tech"),        # Cisco - computer communications equipment
            (6021, "financials"),  # JPMorgan / Bank of America - national commercial banks
            (6211, "financials"),  # Goldman Sachs - security brokers
            (7389, "financials"),  # Visa / Mastercard - services-business services NEC
            (2834, "healthcare"),  # Pfizer / J&J / Merck / AbbVie - pharma preparations
            (6324, "healthcare"),  # UnitedHealth - hospital & medical service plans
            (2911, "energy"),      # Exxon / Chevron / ConocoPhillips - petroleum refining
            (1389, "energy"),      # SLB - oil & gas field services
            (1311, "energy"),      # Occidental - crude petroleum & natural gas
            (2840, "consumer"),    # Procter & Gamble - soaps & detergents
            (2080, "consumer"),    # Coca-Cola - beverages
            (5331, "consumer"),    # Walmart - retail variety stores
            (5211, "consumer"),    # Home Depot - retail building materials
            (5812, "consumer"),    # McDonald's - retail eating places
        ],
    )
    def test_e1_universe_sics_map_to_their_e1_sectors(self, sic, expected):
        """Every SIC code actually present in E1's 25-company universe (read
        from the cached submissions.json documents) must map to the sector E1
        assigned it -- under BOTH variants. If this breaks, continuity5 has
        stopped being continuous with E1."""
        assert sic_to_sector(sic, "broad8") == expected
        assert sic_to_sector(sic, "continuity5") == expected

    @pytest.mark.parametrize("sic", sorted(NON_OPERATING_SIC))
    def test_non_operating_sics_are_excluded_in_both_variants(self, sic):
        assert sic_to_sector(sic, "broad8") == EXCLUDED
        assert sic_to_sector(sic, "continuity5") == EXCLUDED

    def test_exact_overrides_beat_the_enclosing_range(self):
        # 3559 sits inside the 3500-3558/3560-3569 machinery neighbourhood but
        # is semicap equipment; 6324 sits inside the insurance block.
        assert sic_to_sector(3559, "broad8") == "tech"
        assert sic_to_sector(3558, "broad8") == "industrials"
        assert sic_to_sector(6324, "broad8") == "healthcare"
        assert sic_to_sector(6323, "broad8") == "financials"
        for sic, (sector, _why) in SIC_EXACT.items():
            assert sic_to_sector(sic, "broad8") == sector

    def test_broad8_only_sectors_vanish_under_continuity5(self):
        for sic, sector in [(3721, "industrials"), (4911, "utilities"),
                            (6798, "materials_realestate"), (3312, "materials_realestate")]:
            assert sic_to_sector(sic, "broad8") == sector
            assert sic_to_sector(sic, "continuity5") == EXCLUDED

    def test_bad_inputs_are_excluded_not_crashes(self):
        for bad in (None, 0, -5, "", "abc", float("nan")):
            assert sic_to_sector(bad, "broad8") == EXCLUDED

    def test_unknown_taxonomy_raises(self):
        with pytest.raises(ValueError):
            sic_to_sector(2911, "gics11")

    def test_mapping_table_covers_every_e1_sector(self):
        mapped = {sec for _, _, sec, _ in SIC_RANGES} | {v[0] for v in SIC_EXACT.values()}
        assert set(CONTINUITY5_SECTORS) <= mapped
        assert set(BROAD8_SECTORS) <= mapped


# ---------------------------------------------------------------------------
# 4. Supporting machinery
# ---------------------------------------------------------------------------


class TestSanitizeFacts:
    def test_scale_error_is_dropped_not_rescaled(self):
        """The real CY2022Q2I case: M&T Bank tagged its float 1e6x too large.
        An unsanitized top-K would have ranked it as the largest company in
        America."""
        good = [ff("2018-06-30", "2019-02-01", 27.3e9), ff("2019-06-30", "2020-02-01", 25.0e9)]
        bad = ff("2022-06-30", "2023-02-01", 2.73e16)
        clean, suspect = sanitize_facts(good + [bad])
        assert bad in suspect and bad not in clean
        assert all(f.val < 1e13 for f in clean)

    def test_relative_outlier_is_flagged(self):
        base = [ff("2018-06-30", "2019-02-01", 10e9), ff("2019-06-30", "2020-02-01", 11e9)]
        odd = ff("2020-06-30", "2021-02-01", 5e12)  # 500x the median, under the hard ceiling
        clean, suspect = sanitize_facts(base + [odd])
        assert odd in suspect

    def test_hypergrowth_is_not_flagged_nvidia_regression(self):
        """REGRESSION: an earlier median-based rule flagged NVIDIA's genuine
        $1.1T/$2.7T/$4.0T floats as scale errors, because its 2014-2020
        history drags the median to ~$10B. Dropping those facts would have
        silently deleted the largest company in the universe from the most
        recent reconstitutions. Adjacent-disclosure ratios must not do that.
        """
        series = [
            ("2014-06-30", 8e9), ("2015-06-30", 11e9), ("2016-06-30", 25e9),
            ("2017-06-30", 82e9), ("2018-06-30", 140e9), ("2019-06-30", 96e9),
            ("2020-06-30", 230e9), ("2021-06-30", 467e9), ("2022-06-30", 380e9),
            ("2023-07-28", 1.1e12), ("2024-07-26", 2.7e12), ("2025-07-25", 4.0e12),
        ]
        facts = [ff(inst, "2026-01-01", val) for inst, val in series]
        clean, suspect = sanitize_facts(facts)
        assert suspect == [], f"false positives on genuine growth: {suspect}"
        assert len(clean) == len(series)

    def test_in_band_scale_error_is_caught_by_neighbours(self):
        """PEDEVCO-shaped: a $3.4B value sitting between $30M neighbours is
        inside the absolute plausibility band but is still a tagging error."""
        facts = [
            ff("2018-06-30", "2019-03-01", 30e6),
            ff("2019-06-30", "2020-03-01", 3.36e9),
            ff("2020-06-30", "2021-03-01", 28e6),
        ]
        clean, suspect = sanitize_facts(facts)
        assert [f.val for f in suspect] == [3.36e9]

    def test_consecutive_thousandfold_error_run_is_fully_unwound(self):
        """Universal Display tagged 2022-2025 at ~1000x. A median-of-both-
        neighbours rule lets consecutive bad years vouch for each other, so it
        caught only the first; the iterative min-of-neighbours rule must unwind
        the whole run. Left unfixed, UDC entered the 2026 universe as the
        LARGEST company in America at $6.79T (its real float is ~$7B)."""
        series = [
            ("2019-06-28", 7.95e9), ("2020-06-30", 6.38e9), ("2021-06-30", 9.59e9),
            ("2022-06-30", 4.384e12), ("2023-06-30", 320.5e9),
            ("2024-06-28", 9.245e12), ("2025-06-30", 6.792e12),
        ]
        facts = [ff(inst, "2026-01-01", val) for inst, val in series]
        clean, suspect = sanitize_facts_with_reasons(facts)
        assert [f.instant.year for f, _ in suspect] == [2022, 2023, 2024, 2025]
        assert max(f.val for f in clean) == 9.59e9

    def test_bankruptcy_emergence_recovery_is_kept(self):
        """Expand Energy (ex-Chesapeake) went $48M -> $1.6B (33x) emerging from
        Chapter 11 in 2021. That is real, and distressed names are precisely
        what the universe design wants to keep in-sample (EXPANSION_PLAN §2c) --
        so a big multiple at SMALL size must not be flagged."""
        facts = [
            ff("2019-06-28", "2020-02-27", 2.2e9),
            ff("2020-06-30", "2021-03-01", 48e6),
            ff("2021-06-30", "2022-02-24", 1.6e9),
            ff("2022-06-30", "2023-02-22", 3.6e9),
        ]
        clean, suspect = sanitize_facts_with_reasons(facts)
        assert suspect == [], "deleted a genuine post-bankruptcy recovery"

    def test_ten_x_jump_into_megacap_territory_is_flagged(self):
        """The level-aware arm: the same 33x multiple that is fine at $1.6B is
        not fine landing at $320B."""
        facts = [
            ff("2020-06-30", "2021-02-01", 6.4e9),
            ff("2021-06-30", "2022-02-01", 9.6e9),
            ff("2022-06-30", "2023-02-01", 320.5e9),
            ff("2023-06-30", "2024-02-01", 10.1e9),
        ]
        clean, suspect = sanitize_facts_with_reasons(facts)
        assert [f.val for f, _ in suspect] == [320.5e9]

    def test_normal_growth_is_not_flagged(self):
        facts = [ff("2018-06-30", "2019-02-01", 10e9), ff("2019-06-30", "2020-02-01", 30e9),
                 ff("2020-06-30", "2021-02-01", 60e9)]
        clean, suspect = sanitize_facts(facts)
        assert suspect == [] and len(clean) == 3


class TestReconstitutionDates:
    def test_eleven_annual_dates_spanning_a_decade(self):
        ds = reconstitution_dates(2016, 2026)
        assert len(ds) == 11
        assert ds[0] == date(2016, 7, 1) and ds[-1] == date(2026, 7, 1)
        assert all((b.year - a.year) == 1 for a, b in zip(ds, ds[1:]))

    def test_window_is_parameterized_not_hardcoded(self):
        ds = reconstitution_dates(2018, 2022, month=1, day=15)
        assert ds == [date(y, 1, 15) for y in range(2018, 2023)]


class TestSpells:
    def test_contiguous_membership_becomes_one_open_spell(self):
        dates = reconstitution_dates(2016, 2018)
        panel = pd.DataFrame(
            [
                {"recon_date": d.isoformat(), "cik": 1, "name": "N", "tickers": "T",
                 "sector": "tech", "sic": 3571, "sector_rank": 1, "float_usd": 1e11}
                for d in dates
            ]
        )
        sp = build_spells(panel, dates)
        assert len(sp) == 1
        assert sp.iloc[0]["member_from"] == "2016-07-01"
        assert sp.iloc[0]["member_to"] == ""  # still a member at the last date
        assert bool(sp.iloc[0]["all_dates"]) is True

    def test_exit_sets_an_exclusive_member_to(self):
        dates = reconstitution_dates(2016, 2018)
        panel = pd.DataFrame(
            [
                {"recon_date": d.isoformat(), "cik": 1, "name": "N", "tickers": "T",
                 "sector": "tech", "sic": 3571, "sector_rank": 1, "float_usd": 1e11}
                for d in dates[:2]
            ]
        )
        sp = build_spells(panel, dates)
        assert sp.iloc[0]["member_to"] == "2018-07-01"
        assert bool(sp.iloc[0]["all_dates"]) is False

    def test_reentry_produces_two_spells(self):
        dates = reconstitution_dates(2016, 2019)
        keep = [dates[0], dates[3]]
        panel = pd.DataFrame(
            [
                {"recon_date": d.isoformat(), "cik": 1, "name": "N", "tickers": "T",
                 "sector": "tech", "sic": 3571, "sector_rank": 1, "float_usd": 1e11}
                for d in keep
            ]
        )
        sp = build_spells(panel, dates)
        assert len(sp) == 2
        assert sp.iloc[0]["member_to"] == "2017-07-01"
        assert sp.iloc[1]["member_from"] == "2019-07-01"


# ---------------------------------------------------------------------------
# 5. hybrid136: the two-stratum taxonomy itself
# ---------------------------------------------------------------------------


class TestHybrid136Taxonomy:
    def test_k_totals_136_and_splits_100_36(self):
        assert sum(HYBRID136_K.values()) == 136
        assert sum(HYBRID136_K[s] for s in HYBRID136_CORE_SECTORS) == 100
        assert sum(HYBRID136_K[s] for s in HYBRID136_EXTENSION_SECTORS) == 36

    def test_core_stratum_is_exactly_continuity5s_sectors_and_k(self):
        """The ratified design word-for-word: 'exactly continuity5's rule'."""
        assert set(HYBRID136_CORE_SECTORS) == set(CONTINUITY5_SECTORS)
        for s in CONTINUITY5_SECTORS:
            assert HYBRID136_K[s] == CONTINUITY5_K[s] == HYBRID136_CORE_K == 20

    def test_extension_stratum_is_exactly_the_broad8_only_sectors_at_k12(self):
        assert set(HYBRID136_EXTENSION_SECTORS) == set(BROAD8_SECTORS) - set(CONTINUITY5_SECTORS)
        for s in HYBRID136_EXTENSION_SECTORS:
            assert HYBRID136_K[s] == HYBRID136_EXTENSION_K == 12

    def test_strata_partition_the_eight_sectors(self):
        assert set(HYBRID136_SECTORS) == set(BROAD8_SECTORS)
        assert set(HYBRID136_STRATUM) == set(HYBRID136_SECTORS)
        assert not set(HYBRID136_CORE_SECTORS) & set(HYBRID136_EXTENSION_SECTORS)
        assert set(HYBRID136_CORE_SECTORS) | set(HYBRID136_EXTENSION_SECTORS) == set(
            HYBRID136_SECTORS
        )
        assert set(HYBRID136_STRATUM.values()) == {STRATUM_CORE, STRATUM_EXTENSION}

    def test_hybrid136_sic_mapping_is_identical_to_broad8(self):
        """hybrid136 must never re-decide WHERE a company belongs. If this
        breaks, the core stratum has stopped reproducing continuity5 and the
        three ratified SIC sub-decisions have silently moved."""
        for sic in range(0, 10000):
            assert sic_to_sector(sic, "hybrid136") == sic_to_sector(sic, "broad8")

    def test_stratum_of_agrees_with_the_sic_mapping_for_every_sic(self):
        for sic in range(0, 10000):
            sec = sic_to_sector(sic, "hybrid136")
            if sec == EXCLUDED:
                assert stratum_of(sec) == ""
                continue
            st = stratum_of(sec)
            assert st in (STRATUM_CORE, STRATUM_EXTENSION)
            assert (st == STRATUM_CORE) == (sic_to_sector(sic, "continuity5") != EXCLUDED)

    @pytest.mark.parametrize(
        "sic,sector,stratum",
        [
            (4813, "utilities", STRATUM_EXTENSION),    # AT&T / Verizon -- telecom default
            (4812, "utilities", STRATUM_EXTENSION),    # T-Mobile
            (7389, "financials", STRATUM_CORE),        # Visa / Mastercard -- card networks
            (6324, "healthcare", STRATUM_CORE),        # UnitedHealth -- managed care
        ],
    )
    def test_the_three_ratified_sic_subdecisions_stay_at_their_defaults(self, sic, sector, stratum):
        """The 2026-08-21 amendment explicitly kept these at the report's
        defaults. Moving any of them moves names BETWEEN strata, so they are
        ratified inputs, not implementation details."""
        assert sic_to_sector(sic, RATIFIED_VARIANT) == sector
        assert stratum_of(sector) == stratum

    def test_only_the_ratified_variant_is_stratified(self):
        assert set(TAXONOMY_STRATA) == {RATIFIED_VARIANT}
        for v in OPTION_RECORD_VARIANTS:
            assert stratum_of("tech", v) == ""

    def test_all_three_variants_are_registered(self):
        assert set(TAXONOMIES) == {RATIFIED_VARIANT, *OPTION_RECORD_VARIANTS}


# ---------------------------------------------------------------------------
# 6. Stratum integrity, exclusions and determinism, on a synthetic universe
# ---------------------------------------------------------------------------
#
# The fixture is deliberately synthetic: it fixes the float ranking by
# construction so a failure means the SELECTION logic changed, not that EDGAR
# moved. Real-artifact checks against the built tables live in
# TestBuiltArtifacts below and skip cleanly when the build has not been run.

SECTOR_SIC = {
    "tech": 3571,
    "financials": 6021,
    "healthcare": 2834,
    "energy": 2911,
    "consumer": 5331,
    "industrials": 3721,
    "utilities": 4911,
    "materials_realestate": 6798,
}
N_PER_SECTOR = 30  # deep enough to fill K=20 and K=12 with room to spare


def _synthetic_inputs(dates, n_per_sector: int = N_PER_SECTOR):
    """(shortlist, profiles, facts_by_cik, periodic) for a toy universe with
    `n_per_sector` operating registrants in each of the 8 sectors, floats
    strictly descending within a sector and non-overlapping between sectors."""
    profiles: dict[int, CikProfile] = {}
    facts: dict[int, list[FloatFact]] = {}
    periodic: dict[int, list[date]] = {}
    rows = []
    cik = 1000
    for si, sector in enumerate(sorted(SECTOR_SIC)):
        for j in range(n_per_sector):
            cik += 1
            profiles[cik] = CikProfile(
                cik=cik,
                name=f"{sector.upper()}-{j:02d}",
                sic=SECTOR_SIC[sector],
                sic_desc=sector,
                entity_type="operating",
                tickers=[f"T{cik}"],
                has_float_concept=True,
            )
            ff_list, pds = [], []
            for d in dates:
                # PIT-valid: measured ~1 year before D, filed ~4 months before D
                ff_list.append(
                    FloatFact(
                        cik=cik,
                        instant=date(d.year - 1, 6, 30),
                        filed=date(d.year, 3, 1),
                        # sector band keeps buckets non-overlapping; index makes
                        # the within-sector order deterministic
                        val=(100 - si * 10) * 1e9 - j * 1e8,
                        accn=f"acc-{cik}-{d.year}",
                        form="10-K",
                    )
                )
                # one periodic filing in each of the 8 quarters before D
                for q in quarters_preceding(d, MIN_ELIGIBLE_QUARTERS):
                    pds.append(date(q[0], (q[1] - 1) * 3 + 2, 15))
            facts[cik] = ff_list
            periodic[cik] = sorted(set(pds))
            for d in dates:
                rows.append({"cik": cik, "recon_date": d.isoformat(),
                             "superset_rank": si * n_per_sector + j + 1})
    return pd.DataFrame(rows), profiles, facts, periodic


@pytest.fixture(scope="module")
def synthetic():
    dates = reconstitution_dates(2020, 2022)
    return (dates, *_synthetic_inputs(dates))


def _build(variant, synthetic, exclusions=()):
    dates, shortlist, profiles, facts, periodic = synthetic
    return build_membership(
        variant, dates, shortlist, profiles, facts, periodic, exclusions=exclusions
    )


class TestStratumIntegrity:
    def test_hybrid136_emits_136_members_per_date_with_a_stratum_column(self, synthetic):
        dates = synthetic[0]
        panel, _ = _build(RATIFIED_VARIANT, synthetic)
        assert "stratum" in panel.columns
        assert set(panel["stratum"]) == {STRATUM_CORE, STRATUM_EXTENSION}
        for d in dates:
            g = panel[panel.recon_date == d.isoformat()]
            assert len(g) == 136
            assert (g["stratum"] == STRATUM_CORE).sum() == 100
            assert (g["stratum"] == STRATUM_EXTENSION).sum() == 36

    def test_core_rows_equal_continuity5_members_exactly_at_every_date(self, synthetic):
        """THE stratum invariant: the core stratum does not approximate
        continuity5, it reproduces it, date by date and CIK by CIK."""
        dates = synthetic[0]
        hy, _ = _build(RATIFIED_VARIANT, synthetic)
        c5, _ = _build("continuity5", synthetic)
        core = hy[hy["stratum"] == STRATUM_CORE]
        for d in dates:
            ds = d.isoformat()
            assert set(core[core.recon_date == ds]["cik"]) == set(c5[c5.recon_date == ds]["cik"]), (
                f"core stratum diverged from continuity5 at {ds}"
            )

    def test_core_rows_match_continuity5_sector_by_sector_and_rank_by_rank(self, synthetic):
        hy, _ = _build(RATIFIED_VARIANT, synthetic)
        c5, _ = _build("continuity5", synthetic)
        core = hy[hy["stratum"] == STRATUM_CORE]
        a = core.set_index(["recon_date", "cik"])[["sector", "sector_rank", "float_usd"]]
        b = c5.set_index(["recon_date", "cik"])[["sector", "sector_rank", "float_usd"]]
        assert a.sort_index().equals(b.sort_index())

    def test_extension_rows_equal_broad8s_three_non_core_buckets(self, synthetic):
        dates = synthetic[0]
        hy, _ = _build(RATIFIED_VARIANT, synthetic)
        b8, _ = _build("broad8", synthetic)
        ext = hy[hy["stratum"] == STRATUM_EXTENSION]
        b8ext = b8[b8["sector"].isin(HYBRID136_EXTENSION_SECTORS)]
        for d in dates:
            ds = d.isoformat()
            assert set(ext[ext.recon_date == ds]["cik"]) == set(
                b8ext[b8ext.recon_date == ds]["cik"]
            )

    def test_extension_never_contains_a_core_sector_cik(self, synthetic):
        profiles = synthetic[2]
        hy, _ = _build(RATIFIED_VARIANT, synthetic)
        ext = hy[hy["stratum"] == STRATUM_EXTENSION]
        assert set(ext["sector"]) <= set(HYBRID136_EXTENSION_SECTORS)
        for cik in set(ext["cik"]):
            assert sic_to_sector(profiles[int(cik)].sic, "continuity5") == EXCLUDED, (
                f"CIK {cik} is in the extension stratum but its SIC maps into a "
                "continuity5 sector"
            )
        # and the converse
        core = hy[hy["stratum"] == STRATUM_CORE]
        assert set(core["sector"]) <= set(HYBRID136_CORE_SECTORS)
        assert not set(core["cik"]) & set(ext["cik"])

    def test_option_record_variants_gain_no_stratum_column(self, synthetic):
        """continuity5/broad8 are the frozen audit trail behind the owner's
        decision. Adding a column to them is a silent artifact change."""
        for variant in OPTION_RECORD_VARIANTS:
            panel, _ = _build(variant, synthetic)
            assert "stratum" not in panel.columns

    def test_spells_carry_the_stratum_through(self, synthetic):
        dates = synthetic[0]
        panel, _ = _build(RATIFIED_VARIANT, synthetic)
        sp = build_spells(panel, dates)
        assert "stratum" in sp.columns
        assert set(sp["stratum"]) == {STRATUM_CORE, STRATUM_EXTENSION}
        for variant in OPTION_RECORD_VARIANTS:
            p, _ = _build(variant, synthetic)
            assert "stratum" not in build_spells(p, dates).columns

    def test_selection_is_deterministic(self, synthetic):
        a, ra = _build(RATIFIED_VARIANT, synthetic)
        b, rb = _build(RATIFIED_VARIANT, synthetic)
        assert a.equals(b)
        assert ra.equals(rb)

    def test_determinism_is_independent_of_shortlist_row_order(self, synthetic):
        """Membership must be a function of the DATA, not of the order pandas
        happened to hand the candidates over."""
        dates, shortlist, profiles, facts, periodic = synthetic
        a, _ = build_membership(RATIFIED_VARIANT, dates, shortlist, profiles, facts, periodic)
        shuffled = shortlist.sample(frac=1.0, random_state=1234).reset_index(drop=True)
        b, _ = build_membership(RATIFIED_VARIANT, dates, shuffled, profiles, facts, periodic)
        key = ["recon_date", "cik"]
        assert (
            a.sort_values(key).reset_index(drop=True)[["recon_date", "cik", "sector", "stratum"]]
            .equals(
                b.sort_values(key).reset_index(drop=True)[
                    ["recon_date", "cik", "sector", "stratum"]
                ]
            )
        )

    def test_pit_assertion_passes_on_the_hybrid_panel(self, synthetic):
        panel, _ = _build(RATIFIED_VARIANT, synthetic)
        assert_pit_membership(panel)


class TestManualExclusions:
    def test_excluded_cik_is_absent_from_the_panel(self, synthetic):
        hy, _ = _build(RATIFIED_VARIANT, synthetic)
        victim = int(hy[hy["stratum"] == STRATUM_EXTENSION].iloc[0]["cik"])
        ex = ManualExclusion(cik=victim, name="V", reason="test", evidence="test")
        out, _ = _build(RATIFIED_VARIANT, synthetic, exclusions=[ex])
        assert victim not in set(out["cik"])

    def test_excluded_cik_is_logged_never_silently_dropped(self, synthetic):
        dates = synthetic[0]
        hy, _ = _build(RATIFIED_VARIANT, synthetic)
        victim = int(hy.iloc[0]["cik"])
        ex = ManualExclusion(cik=victim, name="V", reason="why", evidence="the evidence")
        _out, rej = _build(RATIFIED_VARIANT, synthetic, exclusions=[ex])
        logged = rej[(rej["cik"] == victim) & (rej["reason"] == "manual_exclusion")]
        assert len(logged) == len(dates)
        assert set(logged["exclusion_reason"]) == {"why"}
        assert set(logged["exclusion_evidence"]) == {"the evidence"}

    def test_the_bucket_refills_so_the_universe_does_not_shrink(self, synthetic):
        dates = synthetic[0]
        hy, _ = _build(RATIFIED_VARIANT, synthetic)
        victim = int(hy.iloc[0]["cik"])
        ex = ManualExclusion(cik=victim, name="V", reason="r", evidence="e")
        out, _ = _build(RATIFIED_VARIANT, synthetic, exclusions=[ex])
        for d in dates:
            assert len(out[out.recon_date == d.isoformat()]) == 136

    def test_exclusion_is_scoped_to_the_variants_it_names(self, synthetic):
        hy, _ = _build(RATIFIED_VARIANT, synthetic)
        victim = int(hy[hy["stratum"] == STRATUM_CORE].iloc[0]["cik"])
        ex = ManualExclusion(cik=victim, name="V", reason="r", evidence="e",
                             applies_to=(RATIFIED_VARIANT,))
        c5, _ = _build("continuity5", synthetic, exclusions=[ex])
        b8, _ = _build("broad8", synthetic, exclusions=[ex])
        hy2, _ = _build(RATIFIED_VARIANT, synthetic, exclusions=[ex])
        assert victim in set(c5["cik"]), "an exclusion leaked into the option record"
        assert victim in set(b8["cik"]), "an exclusion leaked into the option record"
        assert victim not in set(hy2["cik"])

    def test_exclusion_is_scoped_in_time(self, synthetic):
        dates = synthetic[0]
        hy, _ = _build(RATIFIED_VARIANT, synthetic)
        victim = int(hy.iloc[0]["cik"])
        ex = ManualExclusion(cik=victim, name="V", reason="r", evidence="e",
                             effective_from=dates[1])
        out, _ = _build(RATIFIED_VARIANT, synthetic, exclusions=[ex])
        present = set(out[out.recon_date == dates[0].isoformat()]["cik"])
        assert victim in present, "a dated exclusion bit before its effective_from"
        for d in dates[1:]:
            assert victim not in set(out[out.recon_date == d.isoformat()]["cik"])

    def test_effective_to_closes_the_window(self, synthetic):
        dates = synthetic[0]
        ex = ManualExclusion(cik=1, name="V", reason="r", evidence="e",
                             effective_from=dates[0], effective_to=dates[0])
        assert ex.applies(RATIFIED_VARIANT, dates[0])
        assert not ex.applies(RATIFIED_VARIANT, dates[1])

    def test_no_exclusions_means_identical_to_the_plain_build(self, synthetic):
        a, _ = _build(RATIFIED_VARIANT, synthetic)
        b, _ = _build(RATIFIED_VARIANT, synthetic, exclusions=[])
        assert a.equals(b)

    def test_exclusions_in_force_filters_by_variant_and_date(self):
        exs = [
            ManualExclusion(cik=1, reason="r", evidence="e", applies_to=("hybrid136",)),
            ManualExclusion(cik=2, reason="r", evidence="e", applies_to=("continuity5",)),
            ManualExclusion(cik=3, reason="r", evidence="e", applies_to=("hybrid136",),
                            effective_from=date(2021, 7, 1)),
        ]
        at2020 = exclusions_in_force(exs, "hybrid136", date(2020, 7, 1))
        assert set(at2020) == {1}
        at2022 = exclusions_in_force(exs, "hybrid136", date(2022, 7, 1))
        assert set(at2022) == {1, 3}
        assert set(exclusions_in_force(exs, "continuity5", date(2022, 7, 1))) == {2}


class TestManualExclusionsFile:
    def _write(self, tmp_path: Path, body: str) -> Path:
        p = tmp_path / "manual_exclusions.csv"
        p.write_text(",".join(MANUAL_EXCLUSION_COLUMNS) + "\n" + body)
        return p

    def test_missing_file_is_a_legitimate_empty_state(self, tmp_path):
        assert load_manual_exclusions(tmp_path / "nope.csv") == []

    def test_roundtrip_of_a_well_formed_row(self, tmp_path):
        p = self._write(
            tmp_path,
            "42,ACME,float_scaled_1000x,\"tagged 1e12 where the 10-K says 1e9\","
            "2020-02-01,2020-07-01,,hybrid136,2026-08-21\n",
        )
        (ex,) = load_manual_exclusions(p)
        assert ex.cik == 42 and ex.reason == "float_scaled_1000x"
        assert ex.evidence_filed == date(2020, 2, 1)
        assert ex.effective_from == date(2020, 7, 1)
        assert ex.effective_to is None
        assert ex.applies_to == ("hybrid136",)

    def test_evidence_is_mandatory(self, tmp_path):
        p = self._write(tmp_path, "42,ACME,some_reason,,,,,hybrid136,2026-08-21\n")
        with pytest.raises(ValueError, match="mandatory"):
            load_manual_exclusions(p)

    def test_reason_is_mandatory(self, tmp_path):
        p = self._write(tmp_path, "42,ACME,,\"evidence here\",,,,hybrid136,2026-08-21\n")
        with pytest.raises(ValueError, match="mandatory"):
            load_manual_exclusions(p)

    def test_dated_exclusion_on_not_yet_public_evidence_is_refused(self, tmp_path):
        """THE look-ahead guard on the exclusion mechanism itself: a dated row
        may only rest on evidence that was public before it bites."""
        p = self._write(
            tmp_path,
            "42,ACME,r,\"e\",2020-08-01,2020-07-01,,hybrid136,2026-08-21\n",
        )
        with pytest.raises(ValueError, match="POINT-IN-TIME VIOLATION"):
            load_manual_exclusions(p)

    def test_evidence_filed_on_the_effective_date_is_also_refused(self, tmp_path):
        p = self._write(
            tmp_path,
            "42,ACME,r,\"e\",2020-07-01,2020-07-01,,hybrid136,2026-08-21\n",
        )
        with pytest.raises(ValueError, match="POINT-IN-TIME VIOLATION"):
            load_manual_exclusions(p)

    def test_undated_exclusion_needs_no_pit_guard(self, tmp_path):
        p = self._write(tmp_path, "42,ACME,r,\"e\",2026-01-01,,,hybrid136,2026-08-21\n")
        (ex,) = load_manual_exclusions(p)
        assert ex.effective_from is None

    def test_unknown_variant_is_refused(self, tmp_path):
        p = self._write(tmp_path, "42,ACME,r,\"e\",,,,gics11,2026-08-21\n")
        with pytest.raises(ValueError, match="unknown variant"):
            load_manual_exclusions(p)

    def test_missing_column_is_refused(self, tmp_path):
        p = tmp_path / "x.csv"
        p.write_text("cik,reason\n42,r\n")
        with pytest.raises(ValueError, match="missing required column"):
            load_manual_exclusions(p)

    def test_non_integer_cik_is_refused(self, tmp_path):
        p = self._write(tmp_path, "CIK42,ACME,r,\"e\",,,,hybrid136,2026-08-21\n")
        with pytest.raises(ValueError, match="not an integer"):
            load_manual_exclusions(p)

    def test_the_shipped_file_parses_and_every_row_is_evidenced(self):
        """The real data/universe_e2_candidates/manual_exclusions.csv."""
        for ex in load_manual_exclusions():
            assert ex.reason and ex.evidence
            assert len(ex.evidence) > 80, f"CIK {ex.cik}: evidence is too thin to audit"
            assert ex.date_added
            assert set(ex.applies_to) <= set(TAXONOMIES)
            if ex.effective_from and ex.evidence_filed:
                assert ex.evidence_filed < ex.effective_from


# ---------------------------------------------------------------------------
# 6b. The two ratified float-integrity rules (owner, in chat, 2026-08-21)
# ---------------------------------------------------------------------------
#
# What these pin, in order of how much damage a silent break would do:
#   1. the rules are VARIANT-SCOPED -- continuity5/broad8 must be bit-for-bit
#      unaffected even when the triggering data is sitting right there;
#   2. the rules are POINT-IN-TIME -- a disclosure filed on/after D is not
#      evidence at D, for these rules exactly as for float selection;
#   3. the rules only ever REMOVE, and only on an unambiguous signal;
#   4. the `superseded_by_rule` annotations on manual_exclusions.csv are true.


def sh_row(end: str, val: float, filed: str = "", accn: str = "a") -> dict:
    """One dei:EntityCommonStockSharesOutstanding row, as _concept_rows emits."""
    return {
        "end": date.fromisoformat(end),
        "val": float(val),
        "accn": accn,
        "filed": filed,
        "filed_date": date.fromisoformat(filed) if filed else None,
        "form": "10-Q",
    }


class TestFloatRulesets:
    def test_the_ratified_variant_has_both_rules(self):
        rs = ruleset_for(RATIFIED_VARIANT)
        assert rs.newer_zero_float and rs.min_public_shares
        assert set(rs.rules) == set(FLOAT_INTEGRITY_RULE_NAMES)

    def test_the_option_record_variants_have_no_rules(self):
        """The scoping that keeps the frozen audit trail frozen."""
        for v in OPTION_RECORD_VARIANTS:
            rs = ruleset_for(v)
            assert rs is LEGACY_RULESET
            assert rs.rules == ()
            assert not rs.newer_zero_float and not rs.min_public_shares

    def test_every_known_taxonomy_has_an_explicit_ruleset(self):
        """No taxonomy may inherit a ruleset by accident."""
        assert set(VARIANT_RULESETS) == set(TAXONOMIES)

    def test_an_unknown_variant_defaults_to_legacy_not_to_the_ratified_rules(self):
        """Adding a taxonomy must never silently opt it into rules nobody
        ratified for it."""
        assert ruleset_for("gics11_someday") is LEGACY_RULESET

    def test_the_shares_floor_is_one_number_shared_with_the_audit_screen(self):
        assert AUDIT_MIN_PUBLIC_SHARES == MIN_PUBLIC_SHARES_FOR_MEMBERSHIP == 1_000_000


class TestNewerZeroFloatRule:
    def test_fires_when_the_newest_public_disclosure_is_zero(self):
        facts = [ff("2017-06-30", "2018-02-15", 70e9), ff("2018-06-30", "2019-02-11", 0.0)]
        hit = newer_zero_float_asof(facts, date(2019, 7, 1))
        assert hit is not None and hit.val == 0 and hit.instant == date(2018, 6, 30)

    def test_does_not_fire_before_the_zero_is_public(self):
        """THE point-in-time guard on rule 1: a 0 filed on/after D is not
        evidence at D, and the older positive value legitimately stands."""
        facts = [ff("2017-06-30", "2018-02-15", 70e9), ff("2018-06-30", "2019-02-11", 0.0)]
        assert newer_zero_float_asof(facts, date(2018, 7, 1)) is None
        # and not even one day early
        assert newer_zero_float_asof(facts, date(2019, 2, 11)) is None
        assert newer_zero_float_asof(facts, date(2019, 2, 12)) is not None

    def test_does_not_fire_when_a_newer_positive_supersedes_the_zero(self):
        """A registrant that mis-tags one year and then files correctly is
        eligible again -- the rule reads only the MOST RECENT disclosure."""
        facts = [
            ff("2016-06-30", "2017-02-23", 14.6e9),
            ff("2017-06-30", "2018-02-23", 0.0),
            ff("2018-06-30", "2019-02-27", 19.9e9),
        ]
        assert newer_zero_float_asof(facts, date(2018, 7, 1)) is not None
        assert newer_zero_float_asof(facts, date(2019, 7, 1)) is None

    def test_an_amendment_tagging_zero_at_the_same_instant_supersedes(self):
        facts = [ff("2021-06-30", "2022-02-01", 25.6e9), ff("2021-06-30", "2022-04-04", 0.0)]
        assert newer_zero_float_asof(facts, date(2023, 7, 1)) is not None

    def test_an_amendment_tagging_a_positive_value_over_a_zero_clears_it(self):
        facts = [ff("2021-06-30", "2022-02-01", 0.0), ff("2021-06-30", "2022-04-04", 25.6e9)]
        assert newer_zero_float_asof(facts, date(2023, 7, 1)) is None

    def test_a_tie_between_zero_and_nonzero_does_not_fire(self):
        """An ambiguous disclosure must not silently remove a registrant."""
        facts = [ff("2021-06-30", "2022-02-01", 0.0, accn="x"),
                 ff("2021-06-30", "2022-02-01", 25.6e9, accn="y")]
        assert newer_zero_float_asof(facts, date(2023, 7, 1)) is None

    def test_a_negative_float_is_not_treated_as_no_public_float(self):
        """`exactly 0`, not `<= 0`: a negative is a tagging error, not a
        statement about the registrant's equity."""
        facts = [ff("2017-06-30", "2018-02-15", 70e9), ff("2018-06-30", "2019-02-11", -5.0)]
        assert newer_zero_float_asof(facts, date(2019, 7, 1)) is None

    def test_no_facts_and_no_public_facts_are_both_none(self):
        assert newer_zero_float_asof([], D) is None
        assert newer_zero_float_asof([ff("2021-06-30", "2022-02-01", 0.0)], date(2020, 7, 1)) is None

    def test_newest_public_facts_uses_the_same_key_as_pit_float_asof(self):
        facts = [ff("2018-06-30", "2019-02-11", 10e9), ff("2017-06-30", "2019-06-01", 20e9)]
        newest = newest_public_float_facts(facts, date(2020, 7, 1))
        assert len(newest) == 1 and newest[0].instant == date(2018, 6, 30)
        assert pit_float_asof(facts, date(2020, 7, 1)).instant == date(2018, 6, 30)


class TestMinPublicSharesRule:
    def test_fires_below_the_floor_and_not_at_it(self):
        rows = [sh_row("2019-03-31", 100, "2019-05-08")]
        fires, sh, _ = below_min_public_shares_asof(rows, date(2019, 7, 1))
        assert fires and sh == 100
        rows = [sh_row("2019-03-31", MIN_PUBLIC_SHARES_FOR_MEMBERSHIP, "2019-05-08")]
        assert below_min_public_shares_asof(rows, date(2019, 7, 1))[0] is False
        rows = [sh_row("2019-03-31", MIN_PUBLIC_SHARES_FOR_MEMBERSHIP - 1, "2019-05-08")]
        assert below_min_public_shares_asof(rows, date(2019, 7, 1))[0] is True

    def test_is_point_in_time(self):
        """THE point-in-time guard on rule 2. A cover page filed on/after D
        cannot disqualify a registrant at D."""
        rows = [sh_row("2019-03-31", 100, "2019-07-01")]
        assert pit_shares_asof(rows, date(2019, 7, 1)) == (None, "no_public_shares_fact")
        assert below_min_public_shares_asof(rows, date(2019, 7, 1))[0] is False
        assert below_min_public_shares_asof(rows, date(2019, 7, 2))[0] is True

    def test_the_newest_public_cover_page_wins_not_the_smallest(self):
        rows = [sh_row("2017-03-31", 100, "2017-05-01"),
                sh_row("2019-03-31", 500e6, "2019-05-08")]
        fires, sh, _ = below_min_public_shares_asof(rows, date(2019, 7, 1))
        assert not fires and sh == 500e6
        # ... but at a date where only the old one is public, it does fire
        assert below_min_public_shares_asof(rows, date(2018, 7, 1))[0] is True

    def test_an_amendment_at_the_same_instant_supersedes(self):
        rows = [sh_row("2019-03-31", 100, "2019-05-08", accn="orig"),
                sh_row("2019-03-31", 500e6, "2019-06-01", accn="amend")]
        fires, sh, _ = below_min_public_shares_asof(rows, date(2019, 7, 1))
        assert not fires and sh == 500e6

    def test_multi_class_rows_on_one_cover_page_are_summed(self):
        """Summed, not taken one at a time -- otherwise a dual-class filer with
        two small classes would be disqualified for having two of them."""
        rows = [sh_row("2019-03-31", 600_000, "2019-05-08", accn="t"),
                sh_row("2019-03-31", 700_000, "2019-05-08", accn="t")]
        fires, sh, _ = below_min_public_shares_asof(rows, date(2019, 7, 1))
        assert sh == 1_300_000 and not fires

    def test_a_stale_share_count_is_untestable_not_disqualifying(self):
        rows = [sh_row("2016-03-31", 100, "2016-05-08")]
        sh, how = pit_shares_asof(rows, date(2019, 7, 1))
        assert sh is None and how.startswith("stale_gt_")
        assert below_min_public_shares_asof(rows, date(2019, 7, 1))[0] is False
        # just inside the bound it DOES fire
        inside = date(2016, 3, 31) + timedelta(days=MIN_SHARES_MAX_STALENESS_DAYS)
        assert below_min_public_shares_asof(rows, inside)[0] is True

    def test_zero_shares_is_untestable_not_disqualifying(self):
        """0 on a cover page is far more often a placeholder than a fact, and a
        removal on the strength of an absent number is the wrong error."""
        rows = [sh_row("2019-03-31", 0, "2019-05-08")]
        sh, how = pit_shares_asof(rows, date(2019, 7, 1))
        assert sh is None and how == "value_is_zero"
        assert below_min_public_shares_asof(rows, date(2019, 7, 1))[0] is False

    def test_a_row_with_no_filed_date_cannot_be_shown_to_be_public(self):
        rows = [sh_row("2019-03-31", 100, "")]
        assert pit_shares_asof(rows, date(2019, 7, 1)) == (None, "no_public_shares_fact")

    def test_an_untestable_registrant_does_not_fire(self):
        """The measured ~15% multi-class coverage gap: no undimensioned fact
        means the rule abstains, which is NOT the same as passing."""
        assert below_min_public_shares_asof([], date(2019, 7, 1)) == (
            False, None, "no_public_shares_fact"
        )

    def test_concept_rows_parses_the_filed_date_the_rule_depends_on(self):
        doc = {"units": {"shares": [
            {"end": "2019-03-31", "val": 100, "accn": "a", "filed": "2019-05-08", "form": "10-Q"},
            {"end": "2019-06-30", "val": 200, "accn": "b", "form": "10-Q"},  # no filed
        ]}}
        rows = _concept_rows(doc, "shares")
        assert rows[0]["filed_date"] == date(2019, 5, 8)
        assert rows[1]["filed_date"] is None


# --- the rules inside real selection, on the synthetic universe -------------


def _plant_zero_float(synthetic, cik: int, at: date):
    """Give `cik` a zero-valued float disclosure that is already public at `at`
    and newer than the value it would otherwise be selected on."""
    dates, shortlist, profiles, facts, periodic = synthetic
    facts = {k: list(v) for k, v in facts.items()}
    facts[cik] = facts[cik] + [
        FloatFact(cik=cik, instant=date(at.year - 1, 12, 31),
                  filed=date(at.year, 3, 2), val=0.0, accn=f"zero-{cik}", form="10-K")
    ]
    return (dates, shortlist, profiles, facts, periodic)


class TestRulesInSelection:
    def test_a_newer_zero_removes_a_member_and_the_bucket_refills(self, synthetic):
        dates = synthetic[0]
        base, _ = _build(RATIFIED_VARIANT, synthetic)
        victim = int(base[base.recon_date == dates[1].isoformat()].iloc[0]["cik"])
        planted = _plant_zero_float(synthetic, victim, dates[1])
        out, rej = _build(RATIFIED_VARIANT, planted)
        at = out[out.recon_date == dates[1].isoformat()]
        assert victim not in set(at["cik"])
        assert len(at) == 136, "an exclusion must substitute, not shrink"
        # and it is scoped to the one date the zero is the newest disclosure
        assert victim in set(out[out.recon_date == dates[0].isoformat()]["cik"])
        assert victim in set(out[out.recon_date == dates[2].isoformat()]["cik"])

    def test_a_rule_firing_is_logged_with_its_evidence(self, synthetic):
        """Same contract as a manual exclusion: never silently dropped."""
        dates = synthetic[0]
        base, _ = _build(RATIFIED_VARIANT, synthetic)
        victim = int(base[base.recon_date == dates[1].isoformat()].iloc[0]["cik"])
        _out, rej = _build(RATIFIED_VARIANT, _plant_zero_float(synthetic, victim, dates[1]))
        hit = rej[(rej["cik"] == victim) & (rej["reason"] == FLOAT_RULE_NEWER_ZERO)]
        assert len(hit) == 1
        ev = str(hit.iloc[0]["rule_evidence"])
        assert "most recent public float disclosure is 0" in ev
        assert f"zero-{victim}" in ev, "the evidence must name the accession"

    def test_min_shares_removes_a_member_and_names_the_rule(self, synthetic):
        dates, shortlist, profiles, facts, periodic = synthetic
        base, _ = _build(RATIFIED_VARIANT, synthetic)
        victim = int(base[base.recon_date == dates[1].isoformat()].iloc[0]["cik"])
        shares = {victim: [sh_row(f"{dates[1].year}-03-31", 100, f"{dates[1].year}-05-08")]}
        out, rej = build_membership(
            RATIFIED_VARIANT, dates, shortlist, profiles, facts, periodic,
            shares_by_cik=shares,
        )
        at = out[out.recon_date == dates[1].isoformat()]
        assert victim not in set(at["cik"]) and len(at) == 136
        hit = rej[(rej["cik"] == victim) & (rej["reason"] == FLOAT_RULE_MIN_SHARES)]
        assert "cover-page share count is 100" in str(hit.iloc[0]["rule_evidence"])
        # The cover page is not public at the FIRST date, so the rule cannot
        # fire there; it is the newest public share count at both later ones,
        # so it fires at both (a registrant does not stop having 100 shares
        # because a year passed).
        assert set(hit["recon_date"]) == {dates[1].isoformat(), dates[2].isoformat()}
        assert victim in set(out[out.recon_date == dates[0].isoformat()]["cik"])

    def test_the_rules_do_not_touch_the_option_record(self, synthetic):
        """THE scoping invariant. The triggering data is present and would
        remove this registrant from hybrid136 -- continuity5 and broad8 must
        come out IDENTICAL to a build where it is absent."""
        dates, shortlist, profiles, facts, periodic = synthetic
        c5_base, _ = _build("continuity5", synthetic)
        b8_base, _ = _build("broad8", synthetic)
        victim = int(c5_base[c5_base.recon_date == dates[1].isoformat()].iloc[0]["cik"])
        planted = _plant_zero_float(synthetic, victim, dates[1])
        shares = {victim: [sh_row(f"{dates[1].year}-03-31", 100, f"{dates[1].year}-05-08")]}

        for variant, baseline in (("continuity5", c5_base), ("broad8", b8_base)):
            out, rej = build_membership(
                variant, dates, planted[1], profiles, planted[3], periodic,
                shares_by_cik=shares,
            )
            assert out.equals(baseline), f"{variant} moved: the rules leaked into the option record"
            assert not set(rej["reason"]) & set(FLOAT_INTEGRITY_RULE_NAMES)
            assert "rule_evidence" not in rej.columns

        # ... while the SAME inputs do remove it from the ratified variant
        hy, _ = build_membership(
            RATIFIED_VARIANT, dates, planted[1], profiles, planted[3], periodic,
            shares_by_cik=shares,
        )
        assert victim not in set(hy[hy.recon_date == dates[1].isoformat()]["cik"])

    def test_the_ruleset_override_reproduces_the_legacy_build(self, synthetic):
        """The counterfactual panel the report diffs against has to be exactly
        the pre-adoption build, not an approximation of it."""
        dates, shortlist, profiles, facts, periodic = synthetic
        base, _ = _build(RATIFIED_VARIANT, synthetic)
        victim = int(base[base.recon_date == dates[1].isoformat()].iloc[0]["cik"])
        planted = _plant_zero_float(synthetic, victim, dates[1])
        off, _ = build_membership(
            RATIFIED_VARIANT, dates, planted[1], profiles, planted[3], periodic,
            ruleset=LEGACY_RULESET,
        )
        assert off.equals(base)

    def test_the_rules_can_only_remove_never_add(self, synthetic):
        dates, shortlist, profiles, facts, periodic = synthetic
        base, _ = _build(RATIFIED_VARIANT, synthetic)
        victim = int(base.iloc[0]["cik"])
        planted = _plant_zero_float(synthetic, victim, dates[0])
        on, _ = _build(RATIFIED_VARIANT, planted)
        # every CIK selected WITH the rules was also selectable without them
        assert set(zip(on.recon_date, on.cik)) - set(zip(base.recon_date, base.cik)) != set(), (
            "the refill should introduce a new (date, cik) pair"
        )
        # but no rule-removed registrant comes back
        assert (dates[0].isoformat(), victim) not in set(zip(on.recon_date, on.cik))

    def test_a_rule_is_never_evaluated_without_a_selected_float(self, synthetic):
        """A rule name in the reject log must mean 'this rule removed the row',
        never 'it would have failed something else anyway'."""
        dates, shortlist, profiles, facts, periodic = synthetic
        # a registrant with NO pit-valid float at all, plus a tiny share count
        cik = int(next(iter(profiles)))
        facts2 = {k: list(v) for k, v in facts.items()}
        facts2[cik] = []
        shares = {cik: [sh_row(f"{dates[0].year}-03-31", 100, f"{dates[0].year}-05-08")]}
        _out, rej = build_membership(
            RATIFIED_VARIANT, dates, shortlist, profiles, facts2, periodic,
            shares_by_cik=shares,
        )
        mine = rej[rej["cik"] == cik]
        assert set(mine["reason"]) == {"no_pit_valid_float"}


class TestSupersededByRuleAnnotation:
    def _write(self, tmp_path: Path, header, body: str) -> Path:
        p = tmp_path / "manual_exclusions.csv"
        p.write_text(",".join(header) + "\n" + body)
        return p

    def test_the_annotation_round_trips(self, tmp_path):
        p = self._write(
            tmp_path, (*MANUAL_EXCLUSION_COLUMNS, "superseded_by_rule"),
            "42,ACME,r,\"evidence\",,,,hybrid136,2026-08-21,"
            f"{FLOAT_RULE_NEWER_ZERO};{FLOAT_RULE_MIN_SHARES}\n",
        )
        (ex,) = load_manual_exclusions(p)
        assert ex.superseded_by_rule == (FLOAT_RULE_NEWER_ZERO, FLOAT_RULE_MIN_SHARES)

    def test_the_column_is_optional_so_an_older_file_still_loads(self, tmp_path):
        p = self._write(tmp_path, MANUAL_EXCLUSION_COLUMNS,
                        "42,ACME,r,\"evidence\",,,,hybrid136,2026-08-21\n")
        (ex,) = load_manual_exclusions(p)
        assert ex.superseded_by_rule == ()

    def test_an_unknown_rule_name_is_refused(self, tmp_path):
        """A typo'd annotation would claim a rule covers a case when nothing
        does -- the audit trail would assert something false."""
        p = self._write(
            tmp_path, (*MANUAL_EXCLUSION_COLUMNS, "superseded_by_rule"),
            "42,ACME,r,\"evidence\",,,,hybrid136,2026-08-21,newer_zero_flot\n",
        )
        with pytest.raises(ValueError, match="unknown rule"):
            load_manual_exclusions(p)

    def test_an_annotated_row_still_bites(self, tmp_path):
        """The annotation is provenance, not an off switch."""
        p = self._write(
            tmp_path, (*MANUAL_EXCLUSION_COLUMNS, "superseded_by_rule"),
            f"42,ACME,r,\"evidence\",,,,hybrid136,2026-08-21,{FLOAT_RULE_NEWER_ZERO}\n",
        )
        (ex,) = load_manual_exclusions(p)
        assert ex.applies(RATIFIED_VARIANT, D)
        assert set(exclusions_in_force([ex], RATIFIED_VARIANT, D)) == {42}

    def test_the_shipped_file_annotates_the_generalised_rows_and_only_those(self):
        """The three `no_public_common_equity` rows are the ones the rules
        generalise; the three 1,000x mis-scalings are NOT covered by either
        rule and must stay unannotated, because they are still the only thing
        keeping those registrants out."""
        exs = {ex.cik: ex for ex in load_manual_exclusions()}
        annotated = {c for c, ex in exs.items() if ex.superseded_by_rule}
        assert annotated == {30554, 29915, 1161154}
        for cik in annotated:
            assert exs[cik].reason == "no_public_common_equity"
            assert set(exs[cik].superseded_by_rule) <= set(FLOAT_INTEGRITY_RULE_NAMES)
        for cik in set(exs) - annotated:
            assert "scaled_1000x" in exs[cik].reason
            assert exs[cik].superseded_by_rule == ()


# ---------------------------------------------------------------------------
# 7. The float-scale audit's matching primitive
# ---------------------------------------------------------------------------


def _row(end: str, val: float, accn: str = "a", form: str = "10-K") -> dict:
    return {"end": date.fromisoformat(end), "val": val, "accn": accn, "filed": "", "form": form}


class TestConceptMatching:
    def test_same_accession_wins_over_a_closer_date(self):
        """The float and the share count on ONE cover page are the pair that
        makes the implied-price arm meaningful."""
        rows = [_row("2020-06-30", 999.0, accn="other"), _row("2021-02-15", 100.0, accn="tenk")]
        val, how = _match_concept_value(rows, "tenk", date(2020, 6, 30))
        assert val == 100.0 and how.startswith("same_accn@")

    def test_multi_class_rows_on_one_accession_are_summed(self):
        rows = [_row("2021-02-15", 60.0, accn="t"), _row("2021-02-15", 40.0, accn="t")]
        val, _ = _match_concept_value(rows, "t", date(2020, 6, 30))
        assert val == 100.0

    def test_falls_back_to_the_nearest_fact_within_the_window(self):
        rows = [_row("2020-05-01", 7.0, accn="x"), _row("2023-01-01", 9.0, accn="y")]
        val, how = _match_concept_value(rows, "not-present", date(2020, 6, 30))
        assert val == 7.0 and how.startswith("nearest@")

    def test_refuses_to_match_a_fact_too_far_away(self):
        rows = [_row("2010-05-01", 7.0, accn="x")]
        val, how = _match_concept_value(rows, "not-present", date(2020, 6, 30))
        assert val is None and how == "no_fact_within_400d"

    def test_zero_is_reported_as_unusable_not_as_a_value(self):
        """A cover page reporting 0 shares outstanding must not silently become
        a division by zero or a 'clean' answer."""
        rows = [_row("2021-02-15", 0.0, accn="t")]
        val, how = _match_concept_value(rows, "t", date(2020, 6, 30))
        assert val is None and how == "same_accn_value_is_zero"

    def test_empty_history_is_reported(self):
        val, how = _match_concept_value([], "t", date(2020, 6, 30))
        assert val is None and how == "no_concept"


# ---------------------------------------------------------------------------
# 8. The BUILT artifacts (skipped cleanly if the build has not been run)
# ---------------------------------------------------------------------------

_OUT = Path(__file__).resolve().parent / "data" / "universe_e2_candidates"


def _artifact(name: str):
    p = _OUT / name
    if not p.exists():
        pytest.skip(f"{name} not built yet -- run build_universe_e2.py --stage all")
    return pd.read_parquet(p)


class TestBuiltArtifacts:
    def test_hybrid136_panel_has_136_members_at_every_date(self):
        hy = _artifact("hybrid136_panel.parquet")
        counts = hy.groupby("recon_date").size()
        assert set(counts) == {136}, dict(counts)

    def test_built_strata_are_well_formed(self):
        hy = _artifact("hybrid136_panel.parquet")
        assert set(hy["stratum"]) == {STRATUM_CORE, STRATUM_EXTENSION}
        for _, r in hy.iterrows():
            assert HYBRID136_STRATUM[r["sector"]] == r["stratum"]
        per_date = hy.groupby(["recon_date", "stratum"]).size().unstack()
        assert set(per_date[STRATUM_CORE]) == {100}
        assert set(per_date[STRATUM_EXTENSION]) == {36}

    def test_built_extension_holds_no_continuity5_sector(self):
        hy = _artifact("hybrid136_panel.parquet")
        ext = hy[hy["stratum"] == STRATUM_EXTENSION]
        assert set(ext["sector"]) <= set(HYBRID136_EXTENSION_SECTORS)
        for sic in set(ext["sic"].dropna()):
            assert sic_to_sector(int(sic), "continuity5") == EXCLUDED

    def test_built_core_equals_continuity5_minus_the_exclusions_in_force(self):
        """The stratum invariant on the REAL tables. Any divergence must be
        fully accounted for by manual_exclusions.csv -- an unexplained one
        means the core stratum has stopped being continuity5's rule."""
        hy = _artifact("hybrid136_panel.parquet")
        c5 = _artifact("continuity5_panel.parquet")
        exs = load_manual_exclusions()
        core = hy[hy["stratum"] == STRATUM_CORE]
        for d in sorted(set(c5["recon_date"])):
            dd = date.fromisoformat(d)
            gone = set(exclusions_in_force(exs, RATIFIED_VARIANT, dd))
            c5_at = set(c5[c5.recon_date == d]["cik"])
            core_at = set(core[core.recon_date == d]["cik"])
            unexplained = (c5_at - core_at) - gone
            assert not unexplained, (
                f"{d}: continuity5 members missing from the core stratum with no "
                f"exclusion row: {sorted(unexplained)}"
            )
            # the buckets refill 1:1 -- an exclusion never shrinks the core
            # stratum, it only substitutes the next eligible name
            assert len(core_at) == len(c5_at) == 100
            assert len(core_at - c5_at) == len(c5_at - core_at)

    def test_built_extension_equals_broad8s_non_core_buckets_minus_exclusions(self):
        hy = _artifact("hybrid136_panel.parquet")
        b8 = _artifact("broad8_panel.parquet")
        exs = load_manual_exclusions()
        ext = hy[hy["stratum"] == STRATUM_EXTENSION]
        b8ext = b8[b8["sector"].isin(HYBRID136_EXTENSION_SECTORS)]
        for d in sorted(set(b8["recon_date"])):
            gone = set(exclusions_in_force(exs, RATIFIED_VARIANT, date.fromisoformat(d)))
            unexplained = (
                set(b8ext[b8ext.recon_date == d]["cik"]) - set(ext[ext.recon_date == d]["cik"])
            ) - gone
            assert not unexplained, f"{d}: unexplained extension divergence {sorted(unexplained)}"

    def test_every_exclusion_that_bit_is_present_in_the_reject_log(self):
        """'Logged in the report, never silently dropped' -- enforced."""
        p = _OUT / "_cache" / "hybrid136_rejects.parquet"
        if not p.exists():
            pytest.skip("hybrid136 rejects not built yet")
        rej = pd.read_parquet(p)
        logged = rej[rej["reason"] == "manual_exclusion"]
        for ex in load_manual_exclusions():
            if RATIFIED_VARIANT not in ex.applies_to:
                continue
            mine = logged[logged["cik"] == ex.cik]
            assert len(mine), f"CIK {ex.cik} was excluded but never logged"
            assert set(mine["exclusion_reason"]) == {ex.reason}

    def test_option_record_artifacts_still_carry_no_stratum_column(self):
        for name in ("continuity5_panel.parquet", "broad8_panel.parquet",
                     "continuity5.parquet", "broad8.parquet"):
            assert "stratum" not in _artifact(name).columns

    def test_built_hybrid136_is_point_in_time_clean(self):
        assert_pit_membership(_artifact("hybrid136_panel.parquet"))

    def test_audit_thresholds_separate_confirmed_from_cleared_with_headroom(self):
        """Regression guard on the §6.7 compensating control: the shipped
        float-to-assets line must not sit between two adjacent observations. If
        a future build narrows this gap, the threshold needs re-justifying, not
        nudging."""
        p = _OUT / "_cache" / "float_scale_audit.parquet"
        if not p.exists():
            pytest.skip("float scale audit not built yet")
        a = pd.read_parquet(p)
        ratio = pd.to_numeric(a["float_to_assets"], errors="coerce").dropna()
        if ratio.empty:
            pytest.skip("no adjudicated rows in this build")
        confirmed = ratio[ratio > AUDIT_MAX_FLOAT_TO_ASSETS]
        cleared = ratio[ratio <= AUDIT_MAX_FLOAT_TO_ASSETS]
        assert len(confirmed) and len(cleared)
        assert confirmed.min() > 4 * cleared.max(), (
            f"threshold no longer has headroom: cleared max {cleared.max():.1f}x, "
            f"confirmed min {confirmed.min():.1f}x"
        )

    def test_audit_covered_every_ratified_membership_row(self):
        p = _OUT / "_cache" / "float_scale_audit.parquet"
        if not p.exists():
            pytest.skip("float scale audit not built yet")
        a = pd.read_parquet(p)
        # the audit runs on the PRE-exclusion (shadow) panel, so it must cover
        # at least the post-exclusion table plus the rows the exclusions removed
        hy = _artifact("hybrid136_panel.parquet")
        assert len(a) >= len(hy)
        assert set(zip(hy["recon_date"], hy["cik"])) <= set(zip(a["recon_date"], a["cik"]))

    def test_report_records_the_decision_and_the_stratum_rule(self):
        """Tripwire: the report must have been regenerated from THIS build."""
        rp = Path(__file__).resolve().parent / "data" / "E2_UNIVERSE_REPORT.md"
        if not rp.exists():
            pytest.skip("report not generated yet")
        text = rp.read_text()
        assert "DECISION RECORDED" in text and "2026-08-21" in text
        assert "STRATUM ANALYSIS RULE" in text
        assert "hybrid136" in text
        for ex in load_manual_exclusions():
            assert str(ex.cik) in text, f"exclusion CIK {ex.cik} is not visible in the report"

    def test_the_option_record_is_byte_identical_to_the_frozen_manifest(self):
        """THE freeze. `continuity5` / `broad8` are the artifacts the owner's
        2026-08-21 universe decision cites. The sha256 of each was captured
        from the build BEFORE the two float-integrity rules were adopted; if
        any change to the builder moves one, it has leaked into the audit trail
        behind a ratified decision."""
        manifest = _OUT / "option_record_checksums.json"
        if not manifest.exists():
            pytest.skip("checksum manifest not present")
        status = verify_option_record_checksums(manifest)
        assert status, "manifest is empty"
        assert set(status.values()) == {"ok"}, status
        # and it really is covering both option-record variants, all 4 files each
        names = set(json.loads(manifest.read_text())["sha256"])
        for v in OPTION_RECORD_VARIANTS:
            assert {f"{v}.csv", f"{v}.parquet", f"{v}_panel.csv", f"{v}_panel.parquet"} <= names

    def test_rule_firings_are_logged_with_evidence_in_the_built_reject_log(self):
        p = _OUT / "_cache" / f"{RATIFIED_VARIANT}_rejects.parquet"
        if not p.exists():
            pytest.skip("hybrid136 rejects not built yet")
        rej = pd.read_parquet(p)
        fired = rej[rej["reason"].isin(FLOAT_INTEGRITY_RULE_NAMES)]
        if not len(fired):
            pytest.skip("no rule fired in this build")
        for _, r in fired.iterrows():
            assert str(r["rule_evidence"]).strip(), (
                f"CIK {r['cik']} at {r['recon_date']} was removed by "
                f"{r['reason']} with no evidence recorded"
            )

    def test_no_rule_fires_in_the_option_record_reject_logs(self):
        """The scoping invariant, checked on the REAL tables and not just the
        synthetic fixture."""
        for v in OPTION_RECORD_VARIANTS:
            p = _OUT / "_cache" / f"{v}_rejects.parquet"
            if not p.exists():
                pytest.skip(f"{v} rejects not built yet")
            rej = pd.read_parquet(p)
            assert not set(rej["reason"]) & set(FLOAT_INTEGRITY_RULE_NAMES)
            assert "rule_evidence" not in rej.columns

    def test_every_superseded_annotation_is_backed_by_a_real_rule_firing(self):
        """`superseded_by_rule` is a CLAIM about EDGAR data. Verified here on
        the built tables, at every reconstitution date each annotated row
        covers: some rule must actually fire, or the annotation is false."""
        p = _OUT / "_cache" / f"{RATIFIED_VARIANT}_rejects.parquet"
        if not p.exists():
            pytest.skip("hybrid136 rejects not built yet")
        rej = pd.read_parquet(p)
        me = rej[rej["reason"] == "manual_exclusion"]
        if "rule_would_also_reject" not in me.columns:
            pytest.skip("reject log predates the rule annotations")
        for ex in load_manual_exclusions():
            mine = me[me["cik"] == ex.cik]
            fired = {
                d: {x for x in str(v).split(";") if x}
                for d, v in zip(mine["recon_date"], mine["rule_would_also_reject"])
            }
            if ex.superseded_by_rule:
                assert fired, f"CIK {ex.cik} is annotated but never appears in the reject log"
                for d, rules in fired.items():
                    assert rules, (
                        f"CIK {ex.cik} is annotated `superseded_by_rule` but NO rule "
                        f"fires at {d} -- the annotation is false"
                    )
                    assert rules <= set(ex.superseded_by_rule), (
                        f"CIK {ex.cik} at {d}: rule(s) {rules} fire but the "
                        f"annotation only claims {ex.superseded_by_rule}"
                    )
                assert set().union(*fired.values()) == set(ex.superseded_by_rule), (
                    f"CIK {ex.cik}: annotation {ex.superseded_by_rule} does not match "
                    f"the rules that actually fire {set().union(*fired.values())}"
                )
            else:
                for d, rules in fired.items():
                    assert not rules, (
                        f"CIK {ex.cik} at {d} IS covered by rule(s) {rules} but "
                        "carries no `superseded_by_rule` annotation"
                    )

    def test_the_rules_off_counterfactual_exists_and_membership_is_unchanged(self):
        """The report's rule-impact claim, pinned. If a future data refresh
        makes the rules move a member, this fails and the report's §3.8 has to
        be regenerated (which it will be) -- the point is that it can never
        change silently."""
        p = _OUT / "_cache" / f"{RATIFIED_VARIANT}_rules_off_panel.parquet"
        if not p.exists():
            pytest.skip("rules-off counterfactual not built yet")
        off = pd.read_parquet(p)
        hy = _artifact("hybrid136_panel.parquet")
        on_k = set(zip(hy["recon_date"], hy["cik"]))
        off_k = set(zip(off["recon_date"], off["cik"]))
        assert on_k == off_k, (
            "adopting the float-integrity rules moved membership: "
            f"{sorted(on_k ^ off_k)}"
        )

    def test_report_documents_the_two_ratified_rules(self):
        rp = Path(__file__).resolve().parent / "data" / "E2_UNIVERSE_REPORT.md"
        if not rp.exists():
            pytest.skip("report not generated yet")
        text = rp.read_text()
        for rule in FLOAT_INTEGRITY_RULE_NAMES:
            assert rule in text, f"rule {rule} is not documented in the report"
        assert "3.8" in text
        # the two items must have MOVED off the open list, not been left on it
        assert "Adopted — items that have moved off the open list" in text
        open_list = text[text.index("**Not verified / open:**"):]
        assert "left as an explicit recommendation for the owner" not in open_list
        assert "deliberately NOT done in this phase" not in open_list

    def test_no_excluded_cik_survives_anywhere_in_the_ratified_table(self):
        hy = _artifact("hybrid136_panel.parquet")
        for ex in load_manual_exclusions():
            if RATIFIED_VARIANT not in ex.applies_to:
                continue
            rows = hy[hy["cik"] == ex.cik]
            for d in set(rows["recon_date"]):
                assert not ex.applies(RATIFIED_VARIANT, date.fromisoformat(d)), (
                    f"CIK {ex.cik} is a member at {d} despite an exclusion covering it"
                )
