"""
test_scorecard_e2.py -- tests for the §14 historical scorecard.

Every test here runs on a SYNTHETIC record frame built in-process. No test
reads a `data/f5` table, a real price, a real filing or a real return, and
nothing here fits a model -- the scorecard is a description of head 1's own
out-of-fold predictions, so its tests need only those records.

The last section runs head 1 ONCE on that synthetic frame (through the
module's own synthetic pre-registration fixture, never the repo's) to pin the
three properties the pre-registration cites against this file: the records
cover every test row, the scorecard is written after the margin block, and a
missing scorecard key refuses.

What is pinned here:
  * the tercile call rule, and the pre-registered tie rule: a tie group that
    straddles a tercile boundary is "no call" in FULL (red-team M3);
  * "correct" = a sign match, with an exactly-zero excess NOT correct, and
    "no call" (declined) kept apart from "unresolved outcome" (red-team S5);
  * chance under this call rule is 0.50 BY CONSTRUCTION -- measured against a
    random-call simulation whose outcome mix is 0.30 (red-team M4);
  * the Wilson interval against a hand-computed value;
  * below the pre-registered minimum number of calls a company gets ROWS ONLY
    -- no rate, no numerator, no interval (red-team M1);
  * every scorecard page carries the mandatory sentences verbatim AND the
    fixed disclosure block, with "G2 caveats unavailable" rather than a
    missing line when the artifact cannot be read (red-team M5);
  * `build_scorecard` refuses without the margin block, so the page cannot
    reach disk before the equivalence margin (red-team N2).
"""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

import backtest as B
import backtest_e2 as E
import scorecard_e2 as SC
import spec as S


# ---------------------------------------------------------------------------
# fixtures -- synthetic records only
# ---------------------------------------------------------------------------


def _params(min_calls: int = 6) -> dict:
    return {
        "scorecard": {
            "arm": S.PRIMARY_SPEC,
            "eval_set": "dedup",
            "model_block": "text_and_numeric",
            "comparators": ["numeric_only", "size_only"],
            "call_rule": "tercile_within_test_quarter",
            "outcome_col": "target_excess_63",
            "correct_rule": "sign_match_nonzero",
            "tie_rule": "average_rank_straddle_no_call",
            "min_calls_for_company_hit_rate": min_calls,
            "ci": "wilson_95",
        }
    }


def _margin(status: str = "UNPOWERED") -> dict:
    """The shape `build_scorecard` needs: enough of a margin block to prove one
    was computed first (red-team N2)."""
    return {"status": status, "delta_selected": None, "k_folds": 6}


def _disclosures(**over) -> dict:
    """A disclosure block shaped like `backtest_e2.build_disclosures`'s."""
    block = {key: f"{label} disclosure for a test." for key, label in SC.DISCLOSURE_ORDER}
    block.update(over)
    return block


def _records(
    predictions,
    excess=None,
    quarter: str = "2020Q1",
    block: str = "text_and_numeric",
    arm: str = S.PRIMARY_SPEC,
    in_dedup=True,
    ciks=None,
    start_cik: int = 100,
) -> pd.DataFrame:
    """A record frame shaped exactly like `backtest_e2.evaluate_arm`'s."""
    n = len(predictions)
    excess = [0.01] * n if excess is None else list(excess)
    ciks = list(range(start_cik, start_cik + n)) if ciks is None else list(ciks)
    dedup = [in_dedup] * n if isinstance(in_dedup, bool) else list(in_dedup)
    return pd.DataFrame(
        {
            "test_quarter": [quarter] * n,
            "block": [block] * n,
            "arm": [arm] * n,
            "cik": ciks,
            "accession_number": [f"{quarter}-{i:03d}" for i in range(n)],
            "form": ["10-Q"] * n,
            "filing_date": pd.to_datetime([f"{quarter[:4]}-02-{1 + i % 27:02d}" for i in range(n)]),
            "prediction": list(predictions),
            SC.OUTCOME_COL: excess,
            "in_dedup": dedup,
            "in_dedup_no_overlap": dedup,
        }
    )


# ---------------------------------------------------------------------------
# 1. The call rule
# ---------------------------------------------------------------------------


def test_tercile_call_rule():
    """Within a (test_quarter, block): top third -> outperform, bottom third
    -> underperform, middle third -> no call. Ties go through the pinned tie
    rule (see `test_tie_group_straddling_a_boundary_is_no_call`), never through
    the record frame's row order."""
    records = _records(predictions=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    called = SC.make_calls(records, _params())
    assert list(called["call"]) == [SC.CALL_UNDER] * 3 + [SC.CALL_NONE] * 3 + [SC.CALL_OUT] * 3
    assert called["percentile"].is_monotonic_increasing
    assert not called["tied_no_call"].any()
    assert set(called["tie_rule"]) == {"average_rank_straddle_no_call"}

    # ... and the tercile is per quarter AND per block, not pooled
    other = _records(predictions=[10.0, 11.0, 12.0], quarter="2020Q2", start_cik=200)
    both = pd.concat([records, other], ignore_index=True)
    calls = SC.make_calls(both, _params())
    q2 = calls[calls["test_quarter"] == "2020Q2"]
    assert list(q2["call"]) == [SC.CALL_UNDER, SC.CALL_NONE, SC.CALL_OUT]


def test_tie_group_straddling_a_boundary_is_no_call():
    """Tie rule `average_rank_straddle_no_call` (red-team M3).

    A tie group whose ordinal positions span a tercile boundary is "no call" in
    FULL -- no member of it may be called by an accident of filing order. A tie
    group that sits entirely inside one third keeps that third's call."""
    # 9 rows; three tied predictions occupy ordinal positions 6-8, which span
    # the top-third boundary (0.611 is the middle third, 0.833 is the top).
    preds = [0.0, 1.0, 2.0, 3.0, 4.0, 9.0, 9.0, 9.0, 20.0]
    called = SC.make_calls(_records(predictions=preds), _params())
    straddling = called.iloc[5:8]
    assert list(straddling["call"]) == [SC.CALL_NONE] * 3, "the whole tie group is 'no call'"
    assert straddling["tied_no_call"].all()
    # ... every member shares one percentile, so no ordering could split them
    assert straddling["percentile"].nunique() == 1
    # ... and the untied rows are unaffected, above and below
    assert list(called.iloc[:5]["call"]) == [SC.CALL_UNDER] * 3 + [SC.CALL_NONE] * 2
    assert called.iloc[8]["call"] == SC.CALL_OUT
    assert not called.iloc[[0, 1, 2, 3, 4, 8]]["tied_no_call"].any()

    # a tie group entirely inside one third KEEPS its call: positions 1 and 2
    # of 9 are both in the bottom third.
    inside = SC.make_calls(
        _records(predictions=[0.0, 0.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]), _params()
    )
    assert list(inside.iloc[:2]["call"]) == [SC.CALL_UNDER, SC.CALL_UNDER]
    assert not inside["tied_no_call"].any()

    # and the tie rule is pre-registered like every other named rule
    bad = _params()
    bad["scorecard"]["tie_rule"] = "break_by_filing_date"
    with pytest.raises(ValueError) as exc:
        SC.make_calls(_records(predictions=[0.0, 1.0, 2.0]), bad)
    assert "no implementation" in str(exc.value)


def test_chance_line_is_half_by_construction():
    """Red-team M4: the comparison is 0.50 under this call rule when the calls
    are balanced, NOT the outcome mix. A random call rule on a fixture whose
    outcome mix is 0.30 scores ~0.50, which is exactly why the base rate is not
    the yardstick. Red-team NF-7: the printed line is COMPUTED from the call
    counts, and on a balanced fixture the computation returns 0.50."""
    assert "0.50 when the calls are balanced" in SC.CHANCE_SENTENCE_PREFIX
    assert "computed from the call counts" in SC.CHANCE_SENTENCE_PREFIX
    rng = np.random.default_rng(11)
    n = 3000
    excess = np.where(rng.random(n) < 0.30, 0.05, -0.05)   # outcome mix 0.30
    records = _records(
        predictions=list(rng.normal(size=n)),               # calls at random
        excess=list(excess),
        ciks=list(rng.integers(100, 140, size=n)),
    )
    scored = SC.score_calls(SC.make_calls(records, _params()))
    summary = SC.universe_summary(scored)
    model = summary["blocks"]["text_and_numeric"]
    assert summary["outcome_mix_positive_excess"] == pytest.approx(0.30, abs=0.03)
    assert model["hit_rate"] == pytest.approx(0.50, abs=0.04), "random calls score chance"
    # red-team SH-7: 0.50 is DOCUMENTATION, not a payload key -- it shipped
    # beside the computed value and invited the two being read as one number
    assert SC.CHANCE_UNDER_CALL_RULE == 0.5, "the documented balanced-case value"
    assert "chance_under_call_rule" not in model
    assert "chance_under_call_rule" not in summary
    # the calls really are balanced here -- that is where the computed 0.50 comes from
    assert model["n_outperform"] == model["n_underperform"]
    assert model["chance_from_call_counts"] == pytest.approx(0.50, abs=1e-9)
    assert summary["chance_sentence"] == SC.chance_sentence(model["chance_from_call_counts"])
    assert summary["chance_sentence"].endswith("0.500.")
    counts = scored["call"].value_counts()
    assert counts[SC.CALL_OUT] == pytest.approx(counts[SC.CALL_UNDER], rel=0.02)


def test_chance_line_moves_when_calls_are_unbalanced():
    """Red-team NF-7: `0.5` is not a constant to print. When the straddle-tie
    rule (or any imbalance) leaves more "outperform" than "underperform" calls,
    the call-count-matched random baseline moves off 0.50 toward the outcome
    mix, and the printed sentence carries the computed value.

    Fixture: an outcome mix of 0.20 among the called rows, 8 outperform calls
    and 2 underperform calls -> (8*0.2 + 2*0.8)/10 = 0.32, not 0.50."""
    calls = [SC.CALL_OUT] * 8 + [SC.CALL_UNDER] * 2
    excess = [0.05, 0.05, -0.05, -0.05, -0.05, -0.05, -0.05, -0.05, -0.05, -0.05]
    sub = pd.DataFrame(
        {
            "call": calls,
            SC.OUTCOME_COL: excess,
            "cik": list(range(10)),
            "accession_number": [f"A{i}" for i in range(10)],
            "tied_no_call": [False] * 10,
        }
    )
    scored = SC.score_calls(sub)
    entry = SC._hit_rate(scored)
    assert (entry["n_outperform"], entry["n_underperform"]) == (8, 2)
    assert entry["outcome_mix_among_calls"] == pytest.approx(0.20)
    assert entry["chance_from_call_counts"] == pytest.approx(0.32)
    assert entry["chance_sentence"].endswith("0.320.")
    assert "chance_under_call_rule" not in entry, "documented, never shipped (SH-7)"
    assert SC.CHANCE_UNDER_CALL_RULE == 0.5, "the balanced case is still documented"
    # and the same computation reached through the public path
    assert SC.chance_from_call_counts(8, 2, 0.2, 10) == pytest.approx(0.32)
    assert SC.chance_from_call_counts(5, 5, 0.2, 10) == pytest.approx(0.50)
    assert SC.chance_from_call_counts(0, 0, None, 0) is None


def test_only_the_primary_arms_deduplicated_rows_are_scored():
    primary = _records(predictions=[0.0, 1.0, 2.0])
    other_arm = _records(predictions=[9.0, 9.1, 9.2], arm=S.SECONDARY_SPEC, start_cik=400)
    not_dedup = _records(predictions=[3.0, 4.0, 5.0], in_dedup=False, start_cik=500)
    exploratory = _records(
        predictions=[1.0, 2.0, 3.0], block="text_and_numeric_exploratory", start_cik=600
    )
    called = SC.make_calls(
        pd.concat([primary, other_arm, not_dedup, exploratory], ignore_index=True), _params()
    )
    assert set(called["arm"]) == {S.PRIMARY_SPEC}
    assert set(called["block"]) == {"text_and_numeric"}
    assert called["in_dedup"].all()
    assert len(called) == 3


def test_an_unimplemented_named_rule_is_refused():
    params = _params()
    params["scorecard"]["call_rule"] = "whatever_sounds_right"
    with pytest.raises(ValueError) as exc:
        SC.make_calls(_records(predictions=[0.0, 1.0, 2.0]), params)
    assert "no implementation" in str(exc.value)

    params = _params()
    params["scorecard"]["outcome_col"] = "some_other_return"
    with pytest.raises(ValueError):
        SC.make_calls(_records(predictions=[0.0, 1.0, 2.0]), params)


# ---------------------------------------------------------------------------
# 2. The scoring rule
# ---------------------------------------------------------------------------


def test_correct_rule_zero_excess_is_not_correct():
    """`sign_match_nonzero`: an excess of EXACTLY zero is not a correct call,
    for either direction, and a "no call" row is never scored at all."""
    records = _records(
        predictions=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
        excess=[0.0, -0.02, 0.03, 0.05, -0.05, 0.0, 0.0, 0.04, -0.01],
    )
    scored = SC.score_calls(SC.make_calls(records, _params()))
    by_call = list(zip(scored["call"], scored[SC.OUTCOME_COL], scored["correct"]))

    under_zero = [c for call, ex, c in by_call if call == SC.CALL_UNDER and ex == 0.0]
    out_zero = [c for call, ex, c in by_call if call == SC.CALL_OUT and ex == 0.0]
    assert under_zero == [0.0], "underperform + exactly zero excess is NOT correct"
    assert out_zero == [0.0], "outperform + exactly zero excess is NOT correct"

    assert [c for call, ex, c in by_call if call == SC.CALL_UNDER and ex < 0] == [1.0]
    assert [c for call, ex, c in by_call if call == SC.CALL_OUT and ex > 0] == [1.0]
    assert [c for call, ex, c in by_call if call == SC.CALL_OUT and ex < 0] == [0.0]
    # every "no call" row is shown and unscored
    no_call = scored[scored["call"] == SC.CALL_NONE]
    assert len(no_call) == 3 and no_call["correct"].isna().all()
    assert set(scored["correct_rule"]) == {"sign_match_nonzero"}

    # red-team S5: "no call" (the model declined) and "unresolved outcome"
    # (the model called, the outcome is missing) are DIFFERENT things and are
    # counted apart; neither is in the hit-rate denominator.
    with_gap = _records(
        predictions=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0],
        excess=[np.nan, -0.02, 0.03, 0.05, -0.05, 0.0, 0.0, 0.04, -0.01],
    )
    gapped = SC.score_calls(SC.make_calls(with_gap, _params()))
    assert list(gapped["is_unresolved"]) == [True] + [False] * 8
    assert list(gapped["is_no_call"]) == [False] * 3 + [True] * 3 + [False] * 3
    assert gapped.loc[0, "correct"] != gapped.loc[0, "correct"]  # NaN, not "wrong"
    summary = SC.universe_summary(gapped)["blocks"]["text_and_numeric"]
    assert summary["n_calls"] == 5
    assert summary["n_no_call"] == 3 and summary["n_unresolved"] == 1
    assert summary["n_tied_no_call"] == 0
    assert summary["n_calls"] + summary["n_no_call"] + summary["n_unresolved"] == 9
    for piece in ("5 scored calls", "3 'no call'", "1 with an unresolved outcome"):
        assert piece in summary["denominator"]


# ---------------------------------------------------------------------------
# 3. Intervals
# ---------------------------------------------------------------------------


def test_wilson_interval_known_value():
    lo, hi = SC.wilson_interval(7, 10)
    assert lo == pytest.approx(0.3968, abs=5e-4)
    assert hi == pytest.approx(0.8922, abs=5e-4)
    # the interval is inside [0, 1] at the extremes and undefined at n = 0
    assert SC.wilson_interval(0, 5)[0] >= 0.0
    assert SC.wilson_interval(5, 5)[1] <= 1.0
    assert all(np.isnan(v) for v in SC.wilson_interval(0, 0))
    # a wider z gives a wider interval
    wide = SC.wilson_interval(7, 10, z=2.575829)
    assert wide[0] < lo and wide[1] > hi


# ---------------------------------------------------------------------------
# 4. Company tables
# ---------------------------------------------------------------------------


def _scored_for_two_companies(n_a: int, n_b: int, calls=None) -> pd.DataFrame:
    """Company A gets `n_a` scored model calls, company B gets `n_b`; each row
    is a separate test quarter so the tercile rule is bypassed and the calls
    are set directly (this test is about the interval rule, not the calls).

    `calls` overrides the per-company call direction: `{cik: call}`. The default
    is all-"outperform", which is exactly the ONE-DIRECTIONAL case red-team MF-2
    is about."""
    calls = calls or {}
    rows = []
    for cik, n in ((111, n_a), (222, n_b)):
        for i in range(n):
            rows.append(
                {
                    "test_quarter": f"20{20 + i // 4}Q{i % 4 + 1}",
                    "block": "text_and_numeric",
                    "arm": S.PRIMARY_SPEC,
                    "cik": cik,
                    "accession_number": f"{cik}-{i:03d}",
                    "form": "10-Q",
                    "filing_date": pd.Timestamp("2020-01-01") + pd.Timedelta(days=90 * i),
                    "prediction": float(i),
                    SC.OUTCOME_COL: 0.02 if i % 2 == 0 else -0.03,
                    "in_dedup": True,
                    "in_dedup_no_overlap": True,
                    "percentile": 0.9,
                    "call": calls.get(cik, SC.CALL_OUT),
                }
            )
    return SC.score_calls(pd.DataFrame(rows))


def test_company_below_min_calls_has_no_rate(tmp_path):
    """§14, red-team M1 + MF-2: below `min_calls_for_company_hit_rate` a company
    gets ROWS ONLY -- no hit rate, no numerator, no interval, AND no chance
    line, call counts or called-row outcome mix, in the JSON and on the page.

    The fixture is the case that forced MF-2: company B makes 3 calls, all in
    ONE direction. Then the chance line is (3·p + 0·(1−p))/3 = p, and p -- the
    share of positive excess among the called rows -- is numerically the hit
    rate that was just withheld. Publishing it would have published the rate in
    a different column. (This test used to assert the opposite: that the rate
    was still shown while only the interval was withheld.)"""
    scored = _scored_for_two_companies(n_a=6, n_b=3)
    tables = SC.company_tables(scored, names={}, min_calls=6)
    by_cik = {e["cik"]: e for e in tables}

    a = by_cik[111]["summary"]
    assert a["n_calls"] == 6 and a["hit_rate"] == pytest.approx(3 / 6)
    assert a["wilson_lo"] is not None and a["wilson_hi"] is not None
    assert (a["wilson_lo"], a["wilson_hi"]) == SC.wilson_interval(3, 6)
    assert "rate_withheld" not in a

    b = by_cik[222]["summary"]
    assert b["n_calls"] == 3, "the call COUNT is still shown"
    assert b["hit_rate"] is None and b["n_correct"] is None, "no rate, no numerator"
    assert b["wilson_lo"] is None and b["wilson_hi"] is None, "no interval"
    assert b["rate_withheld"] == "rows only (fewer than 6 calls, §14)"
    # red-team MF-2: every quantity that reconstructs the rate is null too
    for key in ("chance_from_call_counts", "chance_sentence", "outcome_mix_among_calls",
                "n_outperform", "n_underperform"):
        assert key in b, f"{key} must be PRESENT and null, not absent"
        assert b[key] is None, key
    assert set(SC.WITHHELD_WITH_THE_RATE) == {
        "hit_rate", "n_correct", "wilson_lo", "wilson_hi", "chance_from_call_counts",
        "chance_sentence", "outcome_mix_among_calls", "n_outperform", "n_underperform",
    }
    # the outcome mix over that company's FILINGS is a different quantity and stays
    assert b["outcome_mix"] == pytest.approx(2 / 3)

    # ... and the rendered page prints no rate for that company either
    text = SC.write_scorecard(
        scored, SC.universe_summary(scored), tables,
        tmp_path / "s.md", tmp_path / "s.json", tmp_path / "s.parquet",
    )
    section = text.split("### CIK 222")[1]
    head = section.split("| quarter |")[0]
    assert "rows only (fewer than 6 calls, §14)" in section
    assert "hit rate" not in head
    # MF-2 on the PAGE: no chance sentence, no call counts, no reconstruction
    assert "Chance under this call rule" not in head, head
    assert "outperform," not in head and "underperform)" not in head, head
    # The OUTCOME MIX stays on the page by design: it is a property of the
    # period (what this company's stock did), not of the model's calls, and §14
    # requires it. On this deliberately degenerate fixture -- every row called,
    # every call in one direction -- it happens to equal the withheld rate; that
    # coincidence is a property of the fixture, not of the disclosure, and the
    # ruled withholding set is `WITHHELD_WITH_THE_RATE` above.
    assert "Outcome mix (share of this company's scored filings" in head
    # the company that clears the threshold still gets all of it
    a_head = text.split("### CIK 111")[1].split("| quarter |")[0]
    assert "hit rate 0.5000" in a_head
    assert "Chance under this call rule" in a_head
    assert "(6 outperform, 0 underperform)" in a_head

    # and the JSON twin carries the same nulls
    written = json.loads((tmp_path / "s.json").read_text())
    b_json = {e["cik"]: e for e in written["companies"]}[222]["summary"]
    for key in SC.WITHHELD_WITH_THE_RATE:
        assert b_json[key] is None, key

    # the threshold is the pre-registered parameter, not a constant here
    relaxed = {e["cik"]: e for e in SC.company_tables(scored, names={}, min_calls=3)}
    assert relaxed[222]["summary"]["hit_rate"] == pytest.approx(2 / 3)
    assert relaxed[222]["summary"]["wilson_lo"] is not None


def test_company_rows_carry_every_block_and_are_filing_date_ordered():
    records = pd.concat(
        [
            _records(predictions=[0.0, 1.0, 2.0], ciks=[111, 111, 111]),
            _records(predictions=[2.0, 1.0, 0.0], block="numeric_only", ciks=[111, 111, 111]),
            _records(predictions=[1.0, 0.0, 2.0], block="size_only", ciks=[111, 111, 111]),
        ],
        ignore_index=True,
    )
    scored = SC.score_calls(SC.make_calls(records, _params()))
    entry = SC.company_tables(scored, names={111: {"name": "Test Co", "ticker": "TST"}}, min_calls=2)[0]
    assert entry["name"] == "Test Co" and entry["ticker"] == "TST"
    dates = [r["filing_date"] for r in entry["rows"]]
    assert dates == sorted(dates)
    row = entry["rows"][0]
    for block in ("text_and_numeric", "numeric_only", "size_only"):
        assert f"{block}_call" in row and f"{block}_result" in row
    assert row["excess_return_pct"] == pytest.approx(1.0)  # 0.01 -> 1.00 %


def test_company_name_falls_back_to_the_cik_when_unknown():
    scored = _scored_for_two_companies(n_a=2, n_b=2)
    tables = SC.company_tables(scored, names={}, min_calls=6)
    assert {e["name"] for e in tables} == {"CIK 111", "CIK 222"}
    assert all(e["ticker"] is None for e in tables)


# ---------------------------------------------------------------------------
# 5. Universe summary + the written page
# ---------------------------------------------------------------------------


def test_universe_summary_covers_every_block_and_the_mandatory_sentences():
    records = pd.concat(
        [
            _records(predictions=[0.0, 1.0, 2.0], excess=[-0.01, 0.0, 0.02]),
            _records(predictions=[0.0, 1.0, 2.0], excess=[-0.01, 0.0, 0.02], block="numeric_only"),
            _records(predictions=[2.0, 1.0, 0.0], excess=[-0.01, 0.0, 0.02], block="size_only"),
        ],
        ignore_index=True,
    )
    scored = SC.score_calls(SC.make_calls(records, _params()))
    summary = SC.universe_summary(scored)
    assert set(summary["blocks"]) == {"text_and_numeric", "numeric_only", "size_only"}
    model = summary["blocks"]["text_and_numeric"]
    assert model["n_calls"] == 2 and model["n_correct"] == 2
    assert (model["wilson_lo"], model["wilson_hi"]) == SC.wilson_interval(2, 2)
    assert summary["n_filings_scored"] == 3 and summary["n_companies"] == 3
    assert summary["outcome_mix_positive_excess"] == pytest.approx(1 / 3)
    assert summary["inference_sentence"] == SC.INFERENCE_SENTENCE
    assert summary["prices_sentence"] == SC.prices_sentence()
    from backtest_e2 import SCOPE_SENTENCE

    assert summary["scope_sentence"] == SCOPE_SENTENCE


def test_write_scorecard_page_carries_the_three_sentences(tmp_path):
    records = pd.concat(
        [
            _records(predictions=[0.0, 1.0, 2.0], excess=[-0.01, 0.0, 0.02], ciks=[111, 222, 333]),
            _records(
                predictions=[2.0, 1.0, 0.0], excess=[-0.01, 0.0, 0.02],
                block="numeric_only", ciks=[111, 222, 333],
            ),
            _records(
                predictions=[1.0, 2.0, 0.0], excess=[-0.01, 0.0, 0.02],
                block="size_only", ciks=[111, 222, 333],
            ),
        ],
        ignore_index=True,
    )
    summary, scored = SC.build_scorecard(
        records,
        _params(min_calls=2),
        _margin(),
        _disclosures(),
        tmp_path / "head1_scorecard.md",
        tmp_path / "head1_scorecard.json",
        tmp_path / "head1_oof_predictions.parquet",
    )
    text = (tmp_path / "head1_scorecard.md").read_text()
    from backtest_e2 import SCOPE_SENTENCE

    assert SCOPE_SENTENCE in text
    assert SC.INFERENCE_SENTENCE in text
    assert SC.prices_sentence() in text
    # the sentences come first, then the universe table, then the companies
    assert text.index(SCOPE_SENTENCE) < text.index(SC.INFERENCE_SENTENCE) < text.index(
        SC.prices_sentence()
    ) < text.index("## Universe") < text.index("## Companies")
    assert "the model (`text_and_numeric`)" in text
    assert "size only (`size_only`)" in text

    written = json.loads((tmp_path / "head1_scorecard.json").read_text())
    assert written["universe"]["blocks"]["text_and_numeric"]["n_calls"] == summary["blocks"][
        "text_and_numeric"
    ]["n_calls"]
    assert [c["cik"] for c in written["companies"]] == [111, 222, 333]

    rows = pd.read_parquet(tmp_path / "head1_oof_predictions.parquet")
    assert len(rows) == len(scored) == 9
    assert set(rows["block"]) == {"text_and_numeric", "numeric_only", "size_only"}
    assert "correct" in rows.columns and "call" in rows.columns


def test_scorecard_page_carries_the_disclosure_block(tmp_path, synth):
    """Red-team M5: the page the owner reads STANDALONE carries the fixed
    disclosure block -- label quality, train overlap at both grains, the
    extraction hole, the unconverted CAD reporter, price censoring, what the
    returns are and what the peers are. The sentences are built by the runner
    from its own artifacts; this module types none of them."""
    frame, _diag = synth
    disclosures = E.build_disclosures(
        frame,
        {
            "gld_exclude_from_analysis": True,
            "n_gld_rows_excluded": 28,
            # red-team NF-8: the join count and the modeling-frame count are
            # different numbers and the page states both
            "n_emb_missing_on_join": 45,
            "n_emb_missing_on_modeling_frame": 44,
        },
        emb_calls={"available": True, "n_scorecard_rows_without_embedding": 25,
                   "n_calls_on_rows_without_embedding": 17,
                   "n_scored_calls_on_rows_without_embedding": 17},
    )
    assert set(disclosures) == {key for key, _ in SC.DISCLOSURE_ORDER}

    records = _records(predictions=[0.0, 1.0, 2.0], excess=[-0.01, 0.0, 0.02])
    SC.build_scorecard(
        records, _params(min_calls=1), _margin(), disclosures,
        tmp_path / "card.md", tmp_path / "card.json", tmp_path / "card.parquet",
    )
    text = (tmp_path / "card.md").read_text()

    for _key, label in SC.DISCLOSURE_ORDER:
        assert f"**{label}.**" in text
    for phrase in (
        "model-produced, not human ground truth",
        "NEGATIVE recall",
        "TEACHER spot-check",
        # red-team SH-6: three grains, and the company-level share is the one
        # that says how many companies the labeler had already seen
        "Three different questions, all stated",
        "chunk level",
        "filing level",
        "companies (75.5%) carry at least one overlapping chunk",
        # red-team MF-3: the STORED-NEGATIVE precision, computed from G2's
        # confusion counts -- not the reference-NEGATIVE row that reads 25/25
        "G2 stored-NEGATIVE precision 25/49 (51%)",
        "summed from secondaries.S-ERR.sentiment.confusion_stored_x_reference",
        "never_extracted_periodic",
        "Enbridge (CIK 895728)",
        "decision 7",
        # red-team NF-4: §11's own wording -- the cause is NOT measured, so the
        # missing companies are never called delistings
        "have no usable prices (counts from the target manifest)",
        "the cause is not separately measured, so they are not described as delistings",
        "dead-name exclusion understates downside dispersion and overstates the benchmark",
        # red-team NF-8: the missing-embedding rows and calls are counted and disclosed
        "25 of the rows this scorecard scores sit on filings with no embedding vector, and "
        "17 of them received a published call",
        "44 rows on the modeling frame carry none, 45 on the three-way join",
        "fitted and scored with NaN embedding components under XGBoost's missing-value "
        "handling -- numeric plus the legacy text columns only",
        # red-team NF-12: the false-NONE rate and the §0 citation, every time
        "false-NONE rate",
        "G2_FINAL_REPORT.md §0 (the owner's binding interpretation: NONE may hide newly "
        "issued guidance)",
        "Price return only -- dividends not included",
        "no transaction costs, taxes, slippage or position sizing",
        "out-of-fold, backtested, no money invested",
        "equal-weighted average of all universe members, both strata, GLD excluded, "
        "excluding the company itself",
        "28 GLD rows were removed",
    ):
        assert phrase in text, phrase
    # the measured numbers come from the artifacts, when those exist
    if E.G2_RESULTS_PATH.exists():
        for number in ("86.94%", "INDETERMINATE", "96.64%", "68.67%", "28.00%", "42.00%",
                       "0.00% (0/80)", "4.58%"):
            assert number in text, number
    assert "stored-NEGATIVE upheld" not in text, "the 25/25 reference row is gone (MF-3)"
    # red-team MF-3: the precision is SUMMED from the confusion block, never typed
    g2 = E.load_g2_caveats()
    neg = E.stored_negative_precision(g2)
    assert (neg["k"], neg["n"]) == (25, 49) and neg["keys"] == [
        "NEGATIVE->NEGATIVE", "NEGATIVE->NEUTRAL"
    ]
    assert f"precision {neg['k']}/{neg['n']}" in text
    if E.CENSUS_E2_PATH.exists():
        assert "universe CIKs have no extracted periodic sections" in text
        # red-team SH-6: the company-level share is READ from the census block
        block = json.loads(E.CENSUS_E2_PATH.read_text())[
            "section_1c_run_time_frame_overlap_and_coverage"
        ]["train_overlap_ex_gld_run_time"]
        assert (
            f"company level, {block['cik_level_n']} of {block['n_ciks']} companies" in text
        )
    if SC.TARGET_MANIFEST_PATH.exists():
        # the counts come from the manifest, so this asserts the shape, never a
        # number a parallel rebuild is free to move
        assert "universe members have no usable prices" in text
        assert "n/a of n/a" not in text

    # an unreadable G2 file SAYS SO on the page -- it never drops the line
    blind = E.build_disclosures(
        frame, {}, g2_path=tmp_path / "no_such_results_g2.json"
    )
    assert blind["labels"].startswith("G2 caveats unavailable")
    SC.build_scorecard(
        records, _params(min_calls=1), _margin(), blind,
        tmp_path / "blind.md", tmp_path / "blind.json", tmp_path / "blind.parquet",
    )
    blind_text = (tmp_path / "blind.md").read_text()
    assert "**Label quality.** G2 caveats unavailable" in blind_text
    assert "**Peer benchmark.**" in blind_text

    # an EMPTY disclosure block refuses rather than printing a bare page
    with pytest.raises(ValueError) as exc:
        SC.build_scorecard(
            records, _params(min_calls=1), _margin(), {},
            tmp_path / "never.md", tmp_path / "never.json", tmp_path / "never.parquet",
        )
    assert "disclosure block is empty" in str(exc.value)
    assert not (tmp_path / "never.md").exists()


def test_company_sections_are_sorted_by_display_name(tmp_path):
    scored = _scored_for_two_companies(n_a=2, n_b=2)
    names = {111: {"name": "Zeta Corp", "ticker": None}, 222: {"name": "Alpha Inc", "ticker": "ALP"}}
    tables = SC.company_tables(scored, names, min_calls=2)
    assert [e["name"] for e in tables] == ["Alpha Inc", "Zeta Corp"]
    text = SC.write_scorecard(
        scored,
        SC.universe_summary(scored),
        tables,
        tmp_path / "s.md",
        tmp_path / "s.json",
        tmp_path / "s.parquet",
    )
    assert text.index("Alpha Inc") < text.index("Zeta Corp")


def test_company_names_come_from_the_metadata_db(tmp_path):
    """The lookup reads `companies(cik, company_name, ticker)`; an absent DB
    and an unknown CIK both fall back silently (the caller prints the CIK)."""
    import sqlite3

    path = tmp_path / "meta.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE companies (cik INTEGER PRIMARY KEY, ticker TEXT, company_name TEXT)")
    con.execute("INSERT INTO companies VALUES (111, NULL, 'One Company')")
    con.execute("INSERT INTO companies VALUES (222, 'TWO', 'Two Company')")
    con.commit()
    con.close()

    names = SC.load_company_names([111, 222, 333], db_paths=(path,))
    assert names[111] == {"name": "One Company", "ticker": None}
    assert names[222] == {"name": "Two Company", "ticker": "TWO"}
    assert 333 not in names
    assert SC.load_company_names([111], db_paths=(tmp_path / "absent.db",)) == {}


# ---------------------------------------------------------------------------
# 6. Inside the guarded run (pre-registration §14's own citations)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def synth():
    tgt, txt, num, fam = E.synthetic_frames(seed=7, n_ciks=12, n_quarters=10, emb_dim=6)
    return E.join_frames(tgt, txt, num, fam)


@pytest.fixture(scope="module")
def synth_params(synth):
    frame, _ = synth
    return E.selftest_params(frame)


def _repo_scorecard_shas() -> dict:
    """sha256 (or None if absent) of the REAL run's scorecard artifacts in
    data/f5. Since the G3 run of 2026-11-05 these hold the real head-1 output
    (git-excluded: not recoverable from git) and must never be deleted."""
    return {
        name: (hashlib.sha256((E.F5_DIR / name).read_bytes()).hexdigest()
               if (E.F5_DIR / name).exists() else None)
        for name in (E.SCORECARD_MD_NAME, E.SCORECARD_JSON_NAME, E.OOF_PREDICTIONS_NAME)
    }


@pytest.fixture(scope="module")
def repo_scorecard_before() -> dict:
    return _repo_scorecard_shas()


@pytest.fixture(scope="module")
def head1_run(tmp_path_factory, synth, synth_params, repo_scorecard_before):
    """ONE head-1 invocation on the synthetic frame, against a SYNTHETIC
    pre-registration pair written into a temp directory -- never the repo's
    real (ratified 2026-11-05) pair. `repo_scorecard_before` is taken first,
    so the real artifacts can be proven untouched by this run."""
    frame, diag = synth
    out = tmp_path_factory.mktemp("head1_scorecard_run")
    doc_path, rat_path = E.write_synthetic_g3(out, synth_params)
    params, guard = E.load_g3_params(doc_path, rat_path)
    doc = E.run_head1(
        params, guard, frame, diag,
        out / "results_head1.json", out / "report_head1.md", out / "run_log.jsonl",
        doc_path=doc_path, ratified_path=rat_path,
    )
    return doc, out, params


def test_oof_records_cover_every_test_row(synth, synth_params):
    """`evaluate_arm` returns one record per fold x block x TEST ROW, carrying
    the filing's identity, the out-of-fold prediction, the realized target and
    the dedup/overlap flags -- the rows the scorecard describes, and no others."""
    frame, _ = synth
    params = json.loads(json.dumps(synth_params))
    folds, _ = E.build_folds(frame, params["fold_quarters"], params["purge_rule"])
    keep = E.dedup_keep_mask_cik(frame, int(params["dedup"]["gap_days"])).values.astype(bool)
    ffs = E.build_fold_frames(frame, folds, None, 0, False, None)
    blocks = E._blocks_from_params(params, frame)
    rows, diag = E.evaluate_arm(frame, ffs, blocks, keep, "train_overlap_share", 0.0, 0)

    records = pd.DataFrame(diag["oof_records"])
    expected = sum(len(f["test_idx"]) for f in folds) * len(blocks)
    assert len(records) == expected > 0
    # exactly one record per (fold, block, filing) -- nothing dropped, nothing doubled
    assert not records.duplicated(subset=["test_quarter", "block", "accession_number"]).any()
    for fold in folds:
        q = str(fold["test_quarter"])
        want = set(frame.loc[fold["test_idx"], "accession_number"])
        for block in blocks:
            got = set(records[(records["test_quarter"] == q) & (records["block"] == block)]
                      ["accession_number"])
            assert got == want
    # the flags are the fold's own masks, not a recomputation
    fold = folds[0]
    masks = E.eval_masks_for_fold(frame, fold, keep, "train_overlap_share", 0.0)
    sub = records[(records["test_quarter"] == str(fold["test_quarter"]))
                  & (records["block"] == "numeric_only")]
    assert list(sub["in_dedup"]) == list(masks["dedup"])
    assert list(sub["in_dedup_no_overlap"]) == list(masks["dedup_no_overlap"])
    # and the realized target is the frame's own target on those rows
    assert list(sub[SC.OUTCOME_COL]) == list(
        frame.loc[fold["test_idx"], B.TARGET_COL].astype(float)
    )
    assert set(records.columns) >= {
        "cik", "accession_number", "form", "filing_date", "test_quarter", "block",
        "prediction", SC.OUTCOME_COL, "in_dedup", "in_dedup_no_overlap",
    }


def test_scorecard_is_written_after_the_margin_block(head1_run, repo_scorecard_before, tmp_path):
    doc, out, params = head1_run
    keys = list(doc.keys())
    assert keys[0] == "margin"
    assert keys.index("scorecard_summary") > keys.index("per_fold_primary_delta_dedup")

    # red-team N2: the ordering guarantee now covers the DISK WRITE, not only
    # the results payload -- `build_scorecard` takes the margin block itself and
    # refuses without one, so no page can precede the margin through any door.
    for absent in (None, {}):
        with pytest.raises((E.OrderingViolation, ValueError)) as exc:
            SC.build_scorecard(
                _records(predictions=[0.0, 1.0, 2.0]),
                _params(min_calls=1),
                absent,
                _disclosures(),
                tmp_path / "early.md",
                tmp_path / "early.json",
                tmp_path / "early.parquet",
            )
        assert "margin" in str(exc.value)
        assert not (tmp_path / "early.md").exists()
    # the margin block travels onto the page's own JSON summary
    assert doc["scorecard_summary"]["margin"]["status"] == doc["margin"]["status"]

    card = doc["scorecard_summary"]
    assert card["arm"] == S.PRIMARY_SPEC and card["eval_set"] == "dedup"
    assert set(card["blocks"]) == {"text_and_numeric", "numeric_only", "size_only"}
    assert card["scope_sentence"] == E.SCOPE_SENTENCE

    text = (out / E.SCORECARD_MD_NAME).read_text()
    assert E.SCOPE_SENTENCE in text
    assert SC.INFERENCE_SENTENCE in text
    assert SC.prices_sentence() in text
    assert (out / E.SCORECARD_JSON_NAME).exists()
    assert (out / E.OOF_PREDICTIONS_NAME).exists()
    # the scorecard scores the primary arm's DEDUPLICATED rows and nothing else
    rows = pd.read_parquet(out / E.OOF_PREDICTIONS_NAME)
    assert set(rows["arm"]) == {S.PRIMARY_SPEC}
    assert rows["in_dedup"].all()
    assert rows[rows["call"] == SC.CALL_NONE]["correct"].isna().all()
    assert card["blocks"]["text_and_numeric"]["n_calls"] == int(
        rows[(rows["block"] == "text_and_numeric") & (rows["call"] != SC.CALL_NONE)].shape[0]
    )
    # ... and it never wrote into the repo's data/f5: the REAL run's scorecard
    # artifacts (2026-11-05, git-excluded) are byte-unchanged. They must NEVER
    # be deleted to make this pass -- they are the real head-1 output.
    assert _repo_scorecard_shas() == repo_scorecard_before, (
        "the synthetic head-1 run changed data/f5's real scorecard artifacts")


def test_missing_scorecard_key_is_a_refusal(tmp_path, synth_params):
    """The scorecard's parameters are pre-registered like every other one: a
    missing key, or a named rule with no implementation, refuses."""

    def _doc(name: str, params: dict):
        path = tmp_path / name
        path.mkdir(parents=True, exist_ok=True)
        return E.write_synthetic_g3(path, params)

    for group, key in (
        ("scorecard", "call_rule"),
        ("scorecard", "tie_rule"),
        ("scorecard", "min_calls_for_company_hit_rate"),
        ("scorecard", "comparators"),
        ("fold_sensitivity", "train_window_quarters"),
        ("families", "novelty_sequential_exploratory"),
        ("gld", "exclude_from_analysis"),
        ("gld", "included_sensitivity_arm"),
        ("columns", "exploratory_novelty_seq"),
    ):
        bad = json.loads(json.dumps(synth_params))
        del bad[group][key]
        doc, rat = _doc(f"missing_{group}_{key}", bad)
        with pytest.raises(E.G3Refusal) as exc:
            E.load_g3_params(doc, rat)
        assert f"{group}.{key}" in str(exc.value)

    dropped = json.loads(json.dumps(synth_params))
    del dropped["scorecard"]
    doc, rat = _doc("no_scorecard", dropped)
    with pytest.raises(E.G3Refusal) as exc:
        E.load_g3_params(doc, rat)
    assert "scorecard.arm" in str(exc.value)

    for key, value in (("ci", "plus_minus_two_sigma"), ("arm", "raw_levels"),
                       ("correct_rule", "any_direction"), ("eval_set", "raw"),
                       ("tie_rule", "break_by_filing_date")):
        bad = json.loads(json.dumps(synth_params))
        bad["scorecard"][key] = value
        doc, rat = _doc(f"bad_{key}", bad)
        with pytest.raises(E.G3Refusal) as exc:
            E.load_g3_params(doc, rat)
        assert "no implementation" in str(exc.value) and f"scorecard.{key}" in str(exc.value)


def test_prices_sentence_reads_the_no_price_count_from_the_manifest(tmp_path):
    """The no-price count is never typed by hand: it is read from the target
    manifest (measured 31 of 244 on 2026-09-11; a council summary once said 32).
    Absent manifest -> 'n/a', so a fixture can never fabricate a number."""
    import json
    m = tmp_path / "target_e2_manifest.json"
    m.write_text(json.dumps({"price_snapshot": {"n_universe_member_ciks_absent_from_price_matrix": 7},
                             "n_universe_member_ciks_all_strata": 9}))
    assert "7 of 9 universe members without usable prices" in SC.prices_sentence(m)
    assert "n/a of n/a universe members" in SC.prices_sentence(tmp_path / "missing.json")
    real = SC.TARGET_MANIFEST_PATH
    if real.exists():
        sent = SC.prices_sentence(real)
        assert "n/a" not in sent and "of 244 universe members" in sent

