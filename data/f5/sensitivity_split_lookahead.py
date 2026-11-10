#!/usr/bin/env python3
"""The post-hoc split arm for head 1 (owner 2026-11-10: "Run it").

Specification: HANDOFF.md §3, "2026-11-10 -- POST-HOC SPLIT ARM AUTHORISED", rules
0-5, written before this script existed. The defect (REVIEW_p5_packet_2026-11-10
M3): `numeric_features_e2.py` computes book_to_market = equity / (shares x close)
with an as-reported share count and a close the vendor adjusted retroactively for
every split up to the 2026-08-24 fetch. Every figure here is EXECUTED AFTER THE
PRIMARY WAS SEEN and can never be selected as the primary; the ratified G3 result
stands whatever this shows.

What it does, and nothing else:
  * `backtest_e2.load_g3_params` -- the freeze guard; exit 2 on refusal.
  * the run-time frame: `load_analysis_frame` + `exclude_gld_rows` (rule 3).
  * GATE (rule 0, and the size_only gate of rule 4): the primary is recomposed from
    backtest_e2's own functions; its per-fold dedup delta must equal
    `results_head1.json` EXACTLY, its calls must equal the ratified
    `head1_oof_predictions.parquet` row for row, and every arm's size_only
    universe counts must equal `head1_scorecard.json`'s -- or nothing is written.
  * ARM B (rule 1): book_to_market / f, f = product of the ratios of every split
    in the ticker's cached Yahoo `events.splits` effective strictly after the
    pre-session. Since the stored value is equity / (shares x adjusted close) and
    the unadjusted close is adjusted close x f, the value as printed on the day is
    stored / f. In memory only; no other input is re-derived.
  * ARM A (rule 2): book_to_market removed from both fitted blocks' columns.
  * per arm: the primary's folds/purge, dedup, PIT rank, PCA, seed-0 fit, and the
    §14 call rule (`scorecard_e2.make_calls` / `score_calls` / `universe_summary`).
  * validity check (rule 1, reported, not gated): the census's split-like jump
    count recomputed on the corrected feature.

Writes ONLY `sensitivity_split_lookahead.json` (tracked; universe level),
`sensitivity_split_lookahead_private.json` (git-ignored; the affected companies)
and one appended `run_log.jsonl` line. Offline, no labeler, $0, a few minutes.

Run:  python3 data/f5/sensitivity_split_lookahead.py              (from the repo root)
      python3 data/f5/sensitivity_split_lookahead.py --gate-only  (gate, no arm, writes nothing)
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import backtest_e2 as BE  # noqa: E402
import scorecard_e2 as SC  # noqa: E402
import spec as S  # noqa: E402

F5 = ROOT / "data" / "f5"
YAHOO_DIR = ROOT / "data" / "raw" / "prices" / "yahoo"
PRICES_PATH = ROOT / "data" / "prices_e2.parquet"
RESULTS_HEAD1 = BE.RESULTS_PATH
SCORECARD_JSON = BE.SCORECARD_JSON_PATH
OOF_PATH = BE.OOF_PREDICTIONS_PATH
CENSUS_SCRIPT = F5 / "census_split_lookahead.py"
CENSUS_JSON = F5 / "split_lookahead_census.json"
OUT_PATH = F5 / "sensitivity_split_lookahead.json"
PRIVATE_PATH = F5 / "sensitivity_split_lookahead_private.json"
RUN_LOG = F5 / "run_log.jsonl"

LABEL = "POST-HOC — EXECUTED AFTER THE PRIMARY WAS SEEN; never selectable"
BM = "book_to_market"
SCORECARD_BLOCKS = ("text_and_numeric", "numeric_only", "size_only")
FITTED = ("numeric_only", "text_and_numeric")
GATE_KEYS = ("n_calls", "n_correct", "hit_rate")
UNIVERSE_KEYS = ("n_calls", "n_correct", "hit_rate", "wilson_lo", "wilson_hi")
CALL_KEY = ["block", "test_quarter", "cik", "accession_number"]
RULE5_SD_MULTIPLE = 2.0   # rule 5: "a move of at most 2 sd"
RULE5_MARGIN = 0.04       # rule 5: "outside ±0.04"


def _load_census():
    spec = importlib.util.spec_from_file_location("census_split_lookahead", CENSUS_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# rule 1: split factors from the cached Yahoo payloads (no fetch)
# ---------------------------------------------------------------------------

def parse_split_ratio(text: str) -> float:
    """"10:1" -> 10.0, "3:2" -> 1.5, "1998:1000" -> 1.998, "1:10" -> 0.1."""
    num, den = (float(x) for x in str(text).split(":"))
    if not (num > 0 and den > 0):
        raise ValueError(f"split ratio {text!r} is not two positive numbers")
    return num / den


def splits_from_payload(payload: dict) -> Optional[list]:
    """[(effective date, ratio)] from `chart.result[0].events.splits`, or None when the
    payload has no events block or no splits in it. The effective date is the event's
    epoch-second `date` taken in New York (the exchange's calendar day)."""
    events = (payload["chart"]["result"][0].get("events") or {}).get("splits")
    if not events:
        return None
    out = []
    for ev in events.values():
        ratio = parse_split_ratio(ev["splitRatio"])
        if "numerator" in ev and "denominator" in ev and \
                not np.isclose(ratio, float(ev["numerator"]) / float(ev["denominator"])):
            raise ValueError(f"splitRatio {ev['splitRatio']!r} disagrees with numerator/denominator")
        day = (pd.Timestamp(int(ev["date"]), unit="s", tz="UTC")
               .tz_convert("America/New_York").tz_localize(None).normalize())
        out.append((day, ratio))
    return sorted(out)


def split_factor(splits: Optional[list], pre_session) -> float:
    """Product of the ratios of every split effective STRICTLY after `pre_session`."""
    day = pd.Timestamp(pre_session).normalize()
    return float(np.prod([r for d, r in (splits or []) if d > day]))


def ticker_splits(tickers, yahoo_dir: Path = YAHOO_DIR) -> tuple[dict, dict]:
    """{ticker: splits or None} and {"no_payload": [...], "no_events": [...]}."""
    splits, missing = {}, {"no_payload": [], "no_events": []}
    for t in sorted(set(tickers)):
        path = Path(yahoo_dir) / f"{t}.json"
        if not path.exists():
            splits[t] = None
            missing["no_payload"].append(t)
            continue
        splits[t] = splits_from_payload(json.loads(path.read_text()))
        if splits[t] is None:
            missing["no_events"].append(t)
    return splits, missing


def split_factors(numeric: pd.DataFrame, cik_to_ticker: dict,
                  yahoo_dir: Path = YAHOO_DIR) -> tuple[np.ndarray, dict, dict]:
    """One factor per `numeric` row (columns cik, pre_session). Factor 1 -- counted and
    named -- for a CIK with no ticker, a ticker with no payload, or no events block.
    Returns (factors, diagnostics, {ticker: splits or None})."""
    splits, missing = ticker_splits(cik_to_ticker.values(), yahoo_dir)
    no_ticker = sorted({int(c) for c in numeric["cik"] if int(c) not in cik_to_ticker})
    factors = np.array([split_factor(splits.get(cik_to_ticker.get(int(c))), d)
                        for c, d in zip(numeric["cik"], numeric["pre_session"])], dtype=float)
    diag = {
        "n_tickers": len(splits),
        "n_tickers_no_payload": len(missing["no_payload"]),
        "tickers_no_payload": missing["no_payload"],
        "n_tickers_no_events_block": len(missing["no_events"]),
        "tickers_no_events_block": missing["no_events"],
        "n_ciks_without_ticker": len(no_ticker),
        "ciks_without_ticker": no_ticker,
        "treatment": "factor 1 (split-free) for all three kinds, counted and named here",
    }
    return factors, diag, splits


def last_split_on_or_before(splits: Optional[list], day) -> Optional[dict]:
    """The latest split record effective on or before `day` (a residual event's context)."""
    day = pd.Timestamp(day).normalize()
    prior = [(d, r) for d, r in (splits or []) if d <= day]
    if not prior:
        return None
    d, r = prior[-1]
    return {"effective": d.date().isoformat(), "ratio": r, "days_before_event": int((day - d).days)}


def corrected_book_to_market(stored: pd.Series, factors: np.ndarray) -> pd.Series:
    """stored = equity / (shares x adjusted close); as printed on the day =
    equity / (shares x adjusted close x factor) = stored / factor."""
    return stored / np.asarray(factors, dtype=float)


# ---------------------------------------------------------------------------
# rule 2: arm A's blocks
# ---------------------------------------------------------------------------

def blocks_without_bm(blocks: dict) -> dict:
    """book_to_market out of both fitted blocks; a new dict, the input untouched."""
    return {name: [c for c in cols if c != BM] if name in FITTED else list(cols)
            for name, cols in blocks.items()}


# ---------------------------------------------------------------------------
# rule 3: the primary's own composition (as sensitivity_decision11 composes it)
# ---------------------------------------------------------------------------

def run_blocks(frame: pd.DataFrame, params: dict, blocks: dict) -> tuple[list, pd.DataFrame]:
    """The three scorecard blocks on `frame` (GLD already excluded): folds, purge,
    dedup, PIT rank, per-fold PCA, seed 0. Returns (IC rows, out-of-fold records)."""
    blocks = {k: blocks[k] for k in SCORECARD_BLOCKS}
    all_cols = sorted({c for cols in blocks.values() for c in cols})
    folds, _ = BE.build_folds(frame, params["fold_quarters"], params["purge_rule"])
    keep = BE.dedup_keep_mask_cik(frame, int(params["dedup"]["gap_days"])).values.astype(bool)
    spec_kwargs = {
        "window_days": int(params["spec"]["window_days"]),
        "min_comparators": int(params["spec"]["min_comparators"]),
        "include_same_day": bool(params["spec"]["include_same_day"]),
        "ticker_col": BE.CIK_COL,
        "date_col": BE.FILING_DATE_COL,
    }
    ranked = S.pit_trailing_rank_frame(frame, all_cols, **spec_kwargs)
    emb = BE.embedding_matrix(frame)
    pinned_k = int(params["embedding"]["pca_k"])
    if pinned_k > 0 and emb is None:
        raise BE.G3Refusal("BLOCKED: embedding.pca_k is ratified but the frame has no embedding.")
    fframes = BE.build_fold_frames(
        ranked, folds, emb, pinned_k if emb is not None else 0,
        bool(params["embedding"]["rank_transform_components"]), spec_kwargs,
    )
    BE.assert_pinned_components(fframes, pinned_k, "split_lookahead")
    rows, diag = BE.evaluate_arm(
        ranked, fframes, blocks, keep, params["overlap"]["column"],
        float(params["overlap"]["threshold"]), int(params["seeds"]["primary"]),
    )
    records = pd.DataFrame(diag["oof_records"]).assign(arm=params["scorecard"]["arm"])
    return rows, records


def score(records: pd.DataFrame, params: dict) -> pd.DataFrame:
    """The ratified §14 call rule, scorecard_e2's own functions."""
    return SC.score_calls(SC.make_calls(records, params))


def universe(scored: pd.DataFrame) -> dict:
    blocks = SC.universe_summary(scored)["blocks"]
    return {b: {k: blocks[b][k] for k in UNIVERSE_KEYS} for b in SCORECARD_BLOCKS}


def dedup_ics(rows: list, block: str) -> list:
    df = pd.DataFrame(rows)
    sub = df[(df["eval_set"] == "dedup") & (df["block"] == block)]
    return [{"test_quarter": q, "ic": float(ic)} for q, ic in zip(sub["test_quarter"], sub["spearman_ic"])]


def calls_changed(scored: pd.DataFrame, ratified: pd.DataFrame) -> dict:
    """Per block: dedup rows whose call differs from the ratified call. The two row
    sets must be identical (asserted) -- the arms change features, never rows."""
    m = scored[CALL_KEY + ["call"]].merge(ratified[CALL_KEY + ["call"]], on=CALL_KEY,
                                          how="outer", suffixes=("_arm", "_ratified"),
                                          indicator=True)
    if not (m["_merge"] == "both").all():
        raise AssertionError("the arm's dedup rows are not the ratified dedup rows")
    diff = m[m["call_arm"] != m["call_ratified"]]
    return {b: int((diff["block"] == b).sum()) for b in SCORECARD_BLOCKS}


def rule5(arm_delta: float, ratified_delta: float, band_sd: float) -> dict:
    move = abs(arm_delta - ratified_delta)
    bound = RULE5_SD_MULTIPLE * band_sd
    return {
        "abs_move_from_ratified_delta": move,
        "two_seed_band_sd": bound,
        "abs_move_at_most_two_seed_band_sd": bool(move <= bound),
        "margin": RULE5_MARGIN,
        "arm_delta_outside_plus_minus_margin": bool(abs(arm_delta) > RULE5_MARGIN),
    }


def company_calls(scored: pd.DataFrame, ciks) -> dict:
    """{cik: {block: {"n_correct", "n_calls"}}} -- PRIVATE file only."""
    out = {}
    for cik in ciks:
        sub = scored[(scored["cik"] == int(cik)) & scored["correct"].notna()]
        out[str(int(cik))] = {b: {"n_correct": int(sub.loc[sub["block"] == b, "correct"].sum()),
                                  "n_calls": int((sub["block"] == b).sum())}
                              for b in SCORECARD_BLOCKS}
    return out


# ---------------------------------------------------------------------------
# the gate (rule 0, and rule 4's size_only gate)
# ---------------------------------------------------------------------------

def gate_universe(got: dict, ratified: dict, blocks) -> list:
    """Mismatches of n_calls / n_correct / hit_rate against the ratified scorecard."""
    return [f"{b}.{k}: {got[b][k]!r} != ratified {ratified[b][k]!r}"
            for b in blocks for k in GATE_KEYS if got[b][k] != ratified[b][k]]


def reproduction_gate(frame, params, head1, ratified_universe, ratified_scored) -> dict:
    rows, records = run_blocks(frame, params, BE._blocks_from_params(params, frame))
    deltas = BE.fold_deltas(rows, "dedup", "text_and_numeric")
    recorded = pd.DataFrame(head1["per_fold_primary_delta_dedup"])
    same_q = list(deltas["test_quarter"]) == list(recorded["test_quarter"])
    max_diff = float(np.max(np.abs(deltas["delta"].values - recorded["delta"].values))) \
        if same_q else float("inf")
    scored = score(records, params)
    mismatches = gate_universe(universe(scored), ratified_universe, SCORECARD_BLOCKS)
    changed = calls_changed(scored, ratified_scored)
    ok = same_q and max_diff == 0.0 and not mismatches and not any(changed.values())
    return {"pass": ok, "quarters_equal": same_q, "max_abs_diff_per_fold_delta": max_diff,
            "universe_mismatches": mismatches, "calls_differing_from_ratified": changed}


# ---------------------------------------------------------------------------
# one arm
# ---------------------------------------------------------------------------

def run_arm(frame, params, blocks, ratified_universe, ratified_scored, ratified_deltas,
            ratified_delta, band_sd, affected_ciks) -> tuple[dict, dict]:
    rows, records = run_blocks(frame, params, blocks)
    scored = score(records, params)
    uni = universe(scored)
    bad = gate_universe(uni, ratified_universe, ("size_only",))
    if bad:
        raise AssertionError(f"size_only does not reproduce under this arm: {bad}; nothing written.")
    deltas = BE.fold_deltas(rows, "dedup", "text_and_numeric")
    if list(deltas["test_quarter"]) != [d["test_quarter"] for d in ratified_deltas]:
        raise AssertionError("the arm's folds are not the primary's folds")
    mean_delta = float(deltas["delta"].mean())
    out = {
        "columns": {b: list(blocks[b]) for b in FITTED},
        "k_folds": int(len(deltas)),
        "mean_fold_delta_dedup": mean_delta,
        "per_fold_delta_dedup": [{"test_quarter": r["test_quarter"], "delta_ratified": float(p["delta"]),
                                  "delta_arm": float(r["delta"])}
                                 for r, p in zip(deltas.to_dict("records"), ratified_deltas)],
        "mean_fold_dedup_ic": {b: float(np.mean([x["ic"] for x in dedup_ics(rows, b)])) for b in FITTED},
        "universe_calls": uni,
        "n_dedup_rows_call_differs_from_ratified": calls_changed(scored, ratified_scored),
        "rule5_reading": rule5(mean_delta, ratified_delta, band_sd),
    }
    return out, company_calls(scored, affected_ciks)


# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gate-only", action="store_true",
                    help="run the reproduction gate, print PASS/FAIL, fit no arm, write nothing")
    args = ap.parse_args(argv)
    try:
        params, guard = BE.load_g3_params()
    except BE.G3Refusal as exc:
        print(str(exc))
        return 2
    started = datetime.now(timezone.utc)
    head1 = json.loads(RESULTS_HEAD1.read_text())
    if head1["run"]["doc_sha256"] != guard["doc_sha256"] or \
            head1["run"]["params_sha256"] != guard["params_sha256"]:
        raise BE.G3Refusal("BLOCKED: results_head1.json was not produced under this pin.")
    if params["scorecard"]["arm"] != S.PRIMARY_SPEC:
        raise AssertionError("the ratified scorecard arm is not the primary spec")
    ratified_universe = json.loads(SCORECARD_JSON.read_text())["universe"]["blocks"]
    CS = _load_census()
    nf, prices, oof = CS.load()  # numeric features, prices_e2 closes, ratified OOF calls
    ratified_scored = oof[oof["in_dedup"].astype(bool)]

    frame, diag = BE.load_analysis_frame()
    frame, gld = BE.exclude_gld_rows(frame, params)

    gate = reproduction_gate(frame, params, head1, ratified_universe, ratified_scored)
    if args.gate_only:
        print(("PASS" if gate["pass"] else "FAIL") + f" reproduction gate: {json.dumps(gate)}")
        return 0 if gate["pass"] else 1
    if not gate["pass"]:
        raise AssertionError(f"reproduction gate FAILED, nothing written: {gate}")

    # ARM B's corrected column (in memory only), keyed (cik, accession_number).
    pairs = pd.read_parquet(PRICES_PATH, columns=["cik", "ticker"]).drop_duplicates()
    if pairs["cik"].duplicated().any() or pairs["ticker"].duplicated().any():
        raise AssertionError("prices_e2.parquet's (cik, ticker) pairs are not one-to-one")
    cik_to_ticker = {int(c): str(t) for c, t in zip(pairs["cik"], pairs["ticker"])}
    factors, factor_diag, splits = split_factors(nf, cik_to_ticker)
    nf_b = nf.assign(**{BM: corrected_book_to_market(nf[BM], factors).values})
    fac = pd.DataFrame({"cik": nf["cik"].astype(int).values,
                        "accession_number": nf["accession_number"].astype(str).values,
                        "factor": factors})
    if fac.duplicated(BE.KEY).any():
        raise AssertionError("numeric features carry a duplicated (cik, accession_number)")
    f_frame = frame[BE.KEY].astype({"cik": int, "accession_number": str}).merge(
        fac, on=BE.KEY, how="left")["factor"].values
    if np.isnan(f_frame).any():
        raise AssertionError("a run-time frame row has no numeric-feature row")
    frame_b = frame.assign(**{BM: corrected_book_to_market(frame[BM], f_frame).values})
    corrected_rows = (f_frame != 1.0) & frame[BM].notna().values
    factor_diag.update({
        "n_frame_rows_factor_not_1_with_bm": int(corrected_rows.sum()),
        "n_frame_ciks_factor_not_1_with_bm": int(frame.loc[corrected_rows, BE.CIK_COL].nunique()),
    })

    # rule 1 validity check: the census method on the corrected feature.
    stored_events = CS.detect_events(CS.shares_as_used(nf, prices))
    residual = CS.detect_events(CS.shares_as_used(nf_b, prices))
    validity = {
        "method": CS.METHOD,
        "threshold": CS.THRESHOLD,
        "n_events_stored_feature": int(len(stored_events)),
        "n_events_corrected_feature": int(len(residual)),
        "residual_events": [{"cik": int(r.cik), "ticker": cik_to_ticker.get(int(r.cik)),
                             "filing_date": r.filing_date.date().isoformat(),
                             "ratio": round(float(r.ratio), 4),
                             "last_split_record_on_or_before": last_split_on_or_before(
                                 splits.get(cik_to_ticker.get(int(r.cik))), r.filing_date)}
                            for r in residual.itertuples()],
        "note": "Rule 1 un-adjusts the close only; the share count is the one reported as of the "
                "filing. A filing after a split's effective date but before the next reported share "
                "count therefore pairs a pre-split count with a post-split close under both the "
                "stored and the corrected feature; such rows show as an event pair (ratio ~1/r on "
                "the first such filing, ~r when the new count is reported). That value is computable "
                "on the day (no look-ahead) and is left as rule 1 defines it.",
        "gated": False,
    }

    head1_ic = head1[f"per_fold_ic__{S.PRIMARY_SPEC}"]
    ratified_deltas = head1["per_fold_primary_delta_dedup"]
    ratified_delta = float(head1["margin"]["mean_fold_delta"])
    if float(head1["margin"]["delta_selected"]) != RULE5_MARGIN:
        raise AssertionError("the ratified margin is not the ±0.04 rule 5 names")
    band_sd = float(head1["seed_band"]["band_sd"])
    affected = sorted(int(c) for c in json.loads(CENSUS_JSON.read_text())["affected_rows_by_cik"])
    blocks = BE._blocks_from_params(params, frame)
    arm_b, priv_b = run_arm(frame_b, params, blocks, ratified_universe, ratified_scored,
                            ratified_deltas, ratified_delta, band_sd, affected)
    arm_a, priv_a = run_arm(frame, params, blocks_without_bm(blocks), ratified_universe,
                            ratified_scored, ratified_deltas, ratified_delta, band_sd, affected)

    out = {
        "label": LABEL,
        "specification": "HANDOFF.md §3, 2026-11-10 -- POST-HOC SPLIT ARM AUTHORISED, rules 0-5 "
                         "(main-session design written before this script; owner ruling \"Run it\")",
        "never_the_primary": "The ratified G3 result stands whatever this shows; no branch is "
                             "re-labelled; the outcome is an erratum and the owner's read.",
        "run": {
            "utc": started.isoformat(timespec="seconds"),
            "doc_sha256": guard["doc_sha256"],
            "params_sha256": guard["params_sha256"],
            "seed": int(params["seeds"]["primary"]),
            "module_sha256": {p: BE.sha256_file(ROOT / p) for p in (
                "data/f5/sensitivity_split_lookahead.py", "backtest_e2.py", "scorecard_e2.py",
                "spec.py", "numeric_features_e2.py", "data/f5/census_split_lookahead.py")},
            "backtest_e2_sha256_in_head1_run": head1["run"]["module_sha256"],
            "input_sha256": dict(diag["input_sha256"], **{
                "prices_e2.parquet": BE.sha256_file(PRICES_PATH),
                "results_head1.json": BE.sha256_file(RESULTS_HEAD1),
                "head1_scorecard.json": BE.sha256_file(SCORECARD_JSON),
                "head1_oof_predictions.parquet": BE.sha256_file(OOF_PATH),
                "split_lookahead_census.json": BE.sha256_file(CENSUS_JSON),
                "yahoo_payloads_sha256_of_shas": BE.sha256_obj(
                    {p.name: BE.sha256_file(p) for p in sorted(YAHOO_DIR.glob("*.json"))}),
            }),
        },
        "frame": {"n_run_time_rows": int(len(frame)), "n_gld_rows_excluded": gld["n_gld_rows_excluded"]},
        "reproduction_gate": gate,
        "size_only_gate": "each arm's size_only n_calls / n_correct / hit_rate equal "
                          "head1_scorecard.json universe.blocks.size_only (else nothing is written): passed",
        "ratified": {
            "mean_fold_delta_dedup": ratified_delta,
            "per_fold_delta_dedup": [{"test_quarter": d["test_quarter"], "delta": float(d["delta"])}
                                     for d in ratified_deltas],
            "mean_fold_dedup_ic": {b: float(np.mean([x["ic"] for x in dedup_ics(head1_ic, b)]))
                                   for b in FITTED},
            "universe_calls": {b: {k: ratified_universe[b][k] for k in UNIVERSE_KEYS}
                               for b in SCORECARD_BLOCKS},
            "seed_band_sd": band_sd,
            "source": "results_head1.json (margin.mean_fold_delta, per_fold_primary_delta_dedup, "
                      "per_fold_ic__pit_trailing_rank, seed_band.band_sd); head1_scorecard.json "
                      "universe.blocks",
        },
        "arm_b_book_to_market_as_printed": dict(arm_b, definition=(
            "book_to_market / f, f = product of splitRatio of every split in the ticker's cached "
            "Yahoo events.splits effective strictly after the pre-session (New York date); "
            "shares and equity unchanged"), split_factors=factor_diag, validity_check=validity),
        "arm_a_book_to_market_removed": dict(arm_a, definition=(
            "book_to_market removed from the numeric columns of numeric_only and text_and_numeric")),
        "rule5_text": "|arm delta - ratified delta| <= 2 x seed_band.band_sd -> \"inside seed noise -- "
                      "the text conclusion is unaffected at this run's resolution\"; larger -> \"moved "
                      "beyond seed noise\"; arm delta outside ±0.04 -> the bounded-null label would not "
                      "have been reached under the corrected feature. Level ICs and hit rates: no "
                      "threshold.",
        "inference_note": "A mean of per-fold deltas, one fit per fold at seed 0. No SE, no TOST, "
                          "no branch: the margin procedure applies to the primary only.",
        "private_file": "data/f5/sensitivity_split_lookahead_private.json (git-ignored): the "
                        f"{len(affected)} census-affected companies' calls, ratified vs each arm",
    }
    private = {
        "label": LABEL + " -- PRIVATE, per company (legal baseline #4); never committed",
        "companies": {c: {"ticker": cik_to_ticker.get(int(c)),
                          "ratified": company_calls(ratified_scored, [int(c)])[c],
                          "arm_b": priv_b[c], "arm_a": priv_a[c]}
                      for c in (str(x) for x in affected)},
    }
    out["runtime_seconds"] = round((datetime.now(timezone.utc) - started).total_seconds(), 1)
    OUT_PATH.write_text(json.dumps(out, indent=1) + "\n")
    PRIVATE_PATH.write_text(json.dumps(private, indent=1) + "\n")
    BE.append_run_log(RUN_LOG, {
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "artifact": OUT_PATH.name,
        "sha256": BE.sha256_file(OUT_PATH),
        "private_sha256": BE.sha256_file(PRIVATE_PATH),
        "doc_sha256": guard["doc_sha256"],
        "params_sha256": guard["params_sha256"],
        "module_sha256s": out["run"]["module_sha256"],
        "note": LABEL,
    })
    print(f"{LABEL}\nratified mean delta {ratified_delta:+.4f} | arm B {arm_b['mean_fold_delta_dedup']:+.4f}"
          f" | arm A {arm_a['mean_fold_delta_dedup']:+.4f} | split-like events "
          f"{validity['n_events_stored_feature']} -> {validity['n_events_corrected_feature']} | wrote "
          f"{OUT_PATH} and {PRIVATE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
