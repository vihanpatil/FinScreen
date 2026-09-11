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
  * the tercile call rule, including its stable tie-break;
  * "correct" = a sign match, with an exactly-zero excess NOT correct, and
    "no call" rows shown but never scored;
  * the Wilson interval against a hand-computed value;
  * the per-company interval is withheld below the pre-registered minimum
    number of calls;
  * every scorecard page carries the three mandatory sentences verbatim.
"""

from __future__ import annotations

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
            "min_calls_for_company_hit_rate": min_calls,
            "ci": "wilson_95",
        }
    }


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
    -> underperform, middle third -> no call. Ties break by stable rank order
    (`rank(method="first")` over the record frame's own row order)."""
    records = _records(predictions=[0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    called = SC.make_calls(records, _params())
    assert list(called["call"]) == [SC.CALL_UNDER] * 3 + [SC.CALL_NONE] * 3 + [SC.CALL_OUT] * 3
    assert called["percentile"].is_monotonic_increasing

    # ... and the tercile is per quarter AND per block, not pooled
    other = _records(predictions=[10.0, 11.0, 12.0], quarter="2020Q2", start_cik=200)
    both = pd.concat([records, other], ignore_index=True)
    calls = SC.make_calls(both, _params())
    q2 = calls[calls["test_quarter"] == "2020Q2"]
    assert list(q2["call"]) == [SC.CALL_UNDER, SC.CALL_NONE, SC.CALL_OUT]

    # ties: three identical predictions are ordered by the frame's row order
    tied = _records(predictions=[5.0, 5.0, 5.0], start_cik=300)
    tied_calls = SC.make_calls(tied, _params())
    assert list(tied_calls["call"]) == [SC.CALL_UNDER, SC.CALL_NONE, SC.CALL_OUT]
    assert list(tied_calls["accession_number"]) == list(tied["accession_number"])


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


def _scored_for_two_companies(n_a: int, n_b: int) -> pd.DataFrame:
    """Company A gets `n_a` scored model calls, company B gets `n_b`; each row
    is a separate test quarter so the tercile rule is bypassed and the calls
    are set directly (this test is about the interval rule, not the calls)."""
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
                    "call": SC.CALL_OUT,
                }
            )
    return SC.score_calls(pd.DataFrame(rows))


def test_company_hit_rate_needs_min_calls():
    scored = _scored_for_two_companies(n_a=6, n_b=3)
    tables = SC.company_tables(scored, names={}, min_calls=6)
    by_cik = {e["cik"]: e for e in tables}

    a = by_cik[111]["summary"]
    assert a["n_calls"] == 6 and a["hit_rate"] == pytest.approx(3 / 6)
    assert a["wilson_lo"] is not None and a["wilson_hi"] is not None
    assert (a["wilson_lo"], a["wilson_hi"]) == SC.wilson_interval(3, 6)

    b = by_cik[222]["summary"]
    assert b["n_calls"] == 3
    assert b["hit_rate"] == pytest.approx(2 / 3), "the rate is still shown"
    assert b["wilson_lo"] is None and b["wilson_hi"] is None, "the interval is withheld"
    assert "fewer than 6 calls" in b["interval_withheld"]
    # the base rate is that company's own share of positive excess returns
    assert b["base_rate"] == pytest.approx(2 / 3)

    # the threshold is the pre-registered parameter, not a constant here
    relaxed = {e["cik"]: e for e in SC.company_tables(scored, names={}, min_calls=3)}
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
    assert summary["base_rate_positive_excess"] == pytest.approx(1 / 3)
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


@pytest.fixture(scope="module")
def head1_run(tmp_path_factory, synth, synth_params):
    """ONE head-1 invocation on the synthetic frame, against a SYNTHETIC
    pre-registration pair written into a temp directory -- never the repo's
    (which has no ratification, and must keep refusing)."""
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


def test_scorecard_is_written_after_the_margin_block(head1_run):
    doc, out, params = head1_run
    keys = list(doc.keys())
    assert keys[0] == "margin"
    assert keys.index("scorecard_summary") > keys.index("per_fold_primary_delta_dedup")

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
    # ... and it never wrote into the repo's data/f5
    assert not (E.F5_DIR / E.SCORECARD_MD_NAME).exists()
    assert not (E.F5_DIR / E.OOF_PREDICTIONS_NAME).exists()


def test_missing_scorecard_key_is_a_refusal(tmp_path, synth_params):
    """The scorecard's parameters are pre-registered like every other one: a
    missing key, or a named rule with no implementation, refuses."""

    def _doc(name: str, params: dict):
        path = tmp_path / name
        path.mkdir(parents=True, exist_ok=True)
        return E.write_synthetic_g3(path, params)

    for group, key in (
        ("scorecard", "call_rule"),
        ("scorecard", "min_calls_for_company_hit_rate"),
        ("scorecard", "comparators"),
        ("fold_sensitivity", "train_window_quarters"),
        ("families", "novelty_sequential_exploratory"),
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
                       ("correct_rule", "any_direction"), ("eval_set", "raw")):
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

