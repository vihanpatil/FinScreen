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

def prepare_blocks(frame: pd.DataFrame, params: dict, blocks: dict,
                   names=SCORECARD_BLOCKS) -> dict:
    """Everything before the fit, on `frame` (GLD already excluded): folds, purge,
    dedup, PIT rank, per-fold PCA. Seed-independent, so the seed band builds it once."""
    blocks = {k: blocks[k] for k in names}
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
    return {"ranked": ranked, "fframes": fframes, "keep": keep, "blocks": blocks}


def fit_blocks(prep: dict, params: dict, seed: int) -> tuple[list, pd.DataFrame]:
    """`backtest_e2.evaluate_arm` at one seed (it fits through `fit_predict_seeded`, the
    path `seed_band` uses). Returns (IC rows, out-of-fold records)."""
    rows, diag = BE.evaluate_arm(
        prep["ranked"], prep["fframes"], prep["blocks"], prep["keep"], params["overlap"]["column"],
        float(params["overlap"]["threshold"]), int(seed),
    )
    return rows, pd.DataFrame(diag["oof_records"]).assign(arm=params["scorecard"]["arm"])


def run_blocks(frame: pd.DataFrame, params: dict, blocks: dict) -> tuple[list, pd.DataFrame]:
    """The three scorecard blocks on `frame`, seed 0 (the primary seed)."""
    return fit_blocks(prepare_blocks(frame, params, blocks), params, int(params["seeds"]["primary"]))


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


def arm_b_frame(frame: pd.DataFrame, nf: pd.DataFrame):
    """ARM B's corrected column (in memory only), keyed (cik, accession_number).
    Returns (frame_b, per-frame-row factor, per-nf-row factor, diagnostics, splits,
    cik_to_ticker)."""
    pairs = pd.read_parquet(PRICES_PATH, columns=["cik", "ticker"]).drop_duplicates()
    if pairs["cik"].duplicated().any() or pairs["ticker"].duplicated().any():
        raise AssertionError("prices_e2.parquet's (cik, ticker) pairs are not one-to-one")
    cik_to_ticker = {int(c): str(t) for c, t in zip(pairs["cik"], pairs["ticker"])}
    factors, factor_diag, splits = split_factors(nf, cik_to_ticker)
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
    return frame_b, f_frame, factors, factor_diag, splits, cik_to_ticker


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
# rule 6 (HANDOFF §3, "SPLIT ARM: SEED-0 RESULT ..."): the seed-matched mode.
# Added after the seed-0 arm and a reviewer scratch sweep were seen.
# ---------------------------------------------------------------------------

SEEDS_OUT_PATH = F5 / "sensitivity_split_lookahead_seeds.json"
SEEDS_CACHE_DIR = F5 / "split_seeds_cache"   # git-ignored; one file per seed, so a killed run resumes
SEED0_JSON = OUT_PATH                         # the committed seed-0 artifact, read only
SEEDS_LABEL = ("POST-HOC — added after the seed-0 arm and a reviewer scratch sweep were seen; "
               "never selectable")
ARMS = ("primary", "arm_a", "arm_b")
QUANTITIES = ("delta", "ic_numeric_only", "ic_text_and_numeric")
LARGE_FACTOR = 1.8  # the census threshold (census_split_lookahead.THRESHOLD)


def seed_band_mean(per_fold_deltas) -> float:
    """The cross-fold mean exactly as `backtest_e2.seed_band` takes it (finite folds, numpy)."""
    d = np.asarray([v for v in np.asarray(per_fold_deltas, dtype=float) if np.isfinite(v)], dtype=float)
    return float(d.mean()) if len(d) else float("nan")


def matched_stats(diff) -> dict:
    """Seed-matched differences (arm − primary, one per seed)."""
    x = np.asarray(diff, dtype=float)
    sd = float(x.std(ddof=1)) if len(x) > 1 else float("nan")
    return {"n_seeds": int(len(x)), "mean": float(x.mean()), "sd": sd,
            "se": sd / float(np.sqrt(len(x))), "share_positive": float((x > 0).mean())}


def percentile_in_band(value: float, band) -> float:
    """100 x (#band < value + 0.5 x #band == value) / n."""
    b = np.asarray(band, dtype=float)
    return float(100.0 * ((b < value).sum() + 0.5 * (b == value).sum()) / len(b))


def churn_summary(counts) -> dict:
    c = np.asarray(counts, dtype=float)
    return {"min": int(c.min()), "median": float(np.median(c)), "max": int(c.max())}


def seed_gate(per_seed: dict, recorded: list) -> list:
    """Mismatches of the primary's per-seed mean dedup delta against results_head1.json
    seed_band.per_seed (exact float equality); a seed absent on either side is a mismatch."""
    want = {int(r["seed"]): float(r["mean_fold_delta_dedup"]) for r in recorded}
    out = [f"seed {s}: {per_seed.get(s)!r} != recorded {want.get(s)!r}"
           for s in sorted(set(want) | set(per_seed)) if per_seed.get(s) != want.get(s)]
    return out


def factor_reach(scored_rows: pd.DataFrame, factor_by_key: pd.DataFrame) -> dict:
    """Scored deduplicated rows (one block) and companies whose split factor != 1."""
    m = scored_rows[["cik", "accession_number"]].merge(factor_by_key, on=BE.KEY, how="left")
    if m["factor"].isna().any() or len(m) != len(scored_rows):
        raise AssertionError("a scored row has no split factor")
    f = m["factor"].to_numpy()
    large = (f >= LARGE_FACTOR) | (f <= 1.0 / LARGE_FACTOR)
    small = (f != 1.0) & ~large
    pick = lambda mask: {"n_rows": int(mask.sum()), "n_companies": int(m.loc[mask, "cik"].nunique())}
    return {"n_scored_dedup_rows": int(len(m)), "factor_not_1": pick(f != 1.0),
            "factor_ge_1.8_or_le_1/1.8": pick(large), "factor_other_not_1": pick(small),
            "factor_not_1_with_book_to_market": pick((f != 1.0) & m["has_bm"].to_numpy())}


def seed_record(seed: int, preps: dict, params: dict, ratified_scored: pd.DataFrame,
                recorded: dict) -> dict:
    """One seed: primary (three blocks), arm A and arm B (the two fitted blocks; size_only's
    feature is untouched, so its calls are the primary's). Gates the primary first."""
    out = {"seed": int(seed)}
    size_records = None
    for arm in ARMS:
        rows, records = fit_blocks(preps[arm], params, seed)
        deltas = BE.fold_deltas(rows, "dedup", "text_and_numeric")
        mean = seed_band_mean(deltas["delta"].values)
        if arm == "primary":
            if mean != recorded.get(int(seed)):
                raise AssertionError(f"seed gate FAILED at seed {seed}: primary {mean!r} != "
                                     f"results_head1.json {recorded.get(int(seed))!r}; nothing written.")
            size_records = records[records["block"] == "size_only"]
        else:
            records = pd.concat([records, size_records], ignore_index=True)
        scored = score(records, params)
        uni = SC.universe_summary(scored)["blocks"]
        margin = BE.margin_procedure(deltas["delta"].values, params)
        out[arm] = {
            "per_fold_delta_dedup": [float(v) for v in deltas["delta"].values],
            "mean_fold_delta_dedup": mean,
            "mean_fold_dedup_ic": {b: float(np.mean([x["ic"] for x in dedup_ics(rows, b)])) for b in FITTED},
            "universe_calls": {b: {k: uni[b][k] for k in GATE_KEYS} for b in SCORECARD_BLOCKS},
            "n_dedup_rows_call_differs_from_ratified_seed0": {
                b: v for b, v in calls_changed(scored, ratified_scored).items() if b in FITTED},
            "margin_procedure": {"status": margin["status"],
                                 "equivalence": margin["tost"]["equivalence"],
                                 "ci_lo": margin["tost"]["ci_lo"]},
        }
    return out


def load_cached(path: Path, fingerprint: str) -> Optional[dict]:
    """A cached seed record, or None if absent or written under other inputs/code."""
    if not Path(path).exists():
        return None
    rec = json.loads(Path(path).read_text())
    return rec if rec.get("fingerprint") == fingerprint else None


def save_cached(path: Path, rec: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rec) + "\n")
    tmp.replace(path)


def assemble_seed_band(recs: list, head1: dict, seed0: dict) -> dict:
    """The tracked document's measurements from the per-seed records (universe level)."""
    seeds = [r["seed"] for r in recs]
    val = {arm: {"delta": [r[arm]["mean_fold_delta_dedup"] for r in recs],
                 **{f"ic_{b}": [r[arm]["mean_fold_dedup_ic"][b] for r in recs] for b in FITTED}}
           for arm in ARMS}
    s0 = {"primary": {"delta": float(head1["margin"]["mean_fold_delta"]),
                      **{f"ic_{b}": seed0["ratified"]["mean_fold_dedup_ic"][b] for b in FITTED}}}
    for arm, key in (("arm_a", "arm_a_book_to_market_removed"),
                     ("arm_b", "arm_b_book_to_market_as_printed")):
        s0[arm] = {"delta": seed0[key]["mean_fold_delta_dedup"],
                   **{f"ic_{b}": seed0[key]["mean_fold_dedup_ic"][b] for b in FITTED}}
    sd = lambda x: float(np.std(np.asarray(x, dtype=float), ddof=1))
    margin_counts = {arm: {
        "n_seeds": len(recs),
        "n_equivalent": sum(r[arm]["margin_procedure"]["equivalence"] is True for r in recs),
        "n_unpowered": sum(r[arm]["margin_procedure"]["status"] == "UNPOWERED" for r in recs),
        "n_ci_lo_above_0": sum(r[arm]["margin_procedure"]["ci_lo"] > 0 for r in recs),
    } for arm in ARMS}
    return {
        "per_seed_mean_fold_delta_dedup": [
            {"seed": s, **{arm: r[arm]["mean_fold_delta_dedup"] for arm in ARMS}}
            for s, r in zip(seeds, recs)],
        "seed_matched_arm_minus_primary": {
            arm: {q: matched_stats(np.subtract(val[arm][q], val["primary"][q])) for q in QUANTITIES}
            for arm in ("arm_a", "arm_b")},
        "band": {arm: {q: {"mean": float(np.mean(val[arm][q])), "sd": sd(val[arm][q])} for q in QUANTITIES}
                 for arm in ARMS},
        "seed0_in_band": {arm: {q: {"seed0_value": s0[arm][q],
                                    "percentile": percentile_in_band(s0[arm][q], val[arm][q])}
                                for q in QUANTITIES} for arm in ARMS},
        "seed0_source": "primary: results_head1.json margin.mean_fold_delta and the seed-0 JSON's "
                        "ratified.mean_fold_dedup_ic; arms: sensitivity_split_lookahead.json",
        "percentile_definition": "100 x (#band seeds below + 0.5 x #equal) / n_seeds",
        "universe_calls_band_mean": {arm: {b: {k: float(np.mean([r[arm]["universe_calls"][b][k] for r in recs]))
                                               for k in GATE_KEYS} for b in SCORECARD_BLOCKS}
                                     for arm in ARMS},
        "universe_note": "size_only's feature is untouched by both arms; its calls under each arm are "
                         "the primary's at the same seed.",
        "calls_differing_from_ratified_seed0": {
            arm: {b: churn_summary([r[arm]["n_dedup_rows_call_differs_from_ratified_seed0"][b]
                                    for r in recs]) for b in FITTED} for arm in ARMS},
        "calls_note": "dedup rows (of 4,481 per block) whose call at seed s differs from the ratified "
                      "seed-0 call (head1_oof_predictions.parquet); for the primary only the seed changes.",
        "margin_procedure_per_seed": margin_counts,
        "margin_procedure_note": "backtest_e2.margin_procedure called unchanged on each seed's per-fold "
                                 "deltas; counts only. n_equivalent = tost.equivalence true; n_ci_lo_above_0 "
                                 "= the tost CI (ci_level from params.tost) lower bound > 0.",
    }


def seed_band_main(args) -> int:
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
    seed0 = json.loads(SEED0_JSON.read_text())
    lo, hi = (int(v) for v in params["seeds"]["nuisance_band"])
    band_seeds = list(range(lo, hi + 1))  # as run_head1 enumerates it for seed_band
    if [int(r["seed"]) for r in head1["seed_band"]["per_seed"]] != band_seeds:
        raise AssertionError("results_head1.json seed_band.per_seed is not the ratified band")
    recorded = {int(r["seed"]): float(r["mean_fold_delta_dedup"]) for r in head1["seed_band"]["per_seed"]}
    test_mode = args.seeds is not None
    seeds = [int(x) for x in args.seeds.split(",")] if test_mode else band_seeds
    if test_mode:  # seed 0 allowed here only: it checks the arms against the committed seed-0 JSON
        recorded[0] = float(head1["margin"]["mean_fold_delta"])
    if not set(seeds) <= set(band_seeds) | ({0} if test_mode else set()):
        raise AssertionError(f"seeds {seeds} are not all in the ratified band {lo}-{hi}")

    CS = _load_census()
    nf, _prices, oof = CS.load()
    ratified_scored = oof[oof["in_dedup"].astype(bool)]
    frame, diag = BE.load_analysis_frame()
    frame, _gld = BE.exclude_gld_rows(frame, params)
    frame_b, f_frame, _f, _fd, _sp, _c2t = arm_b_frame(frame, nf)
    blocks = BE._blocks_from_params(params, frame)
    preps = {"primary": prepare_blocks(frame, params, blocks),
             "arm_a": prepare_blocks(frame, params, blocks_without_bm(blocks), FITTED),
             "arm_b": prepare_blocks(frame_b, params, blocks, FITTED)}

    inputs = dict(diag["input_sha256"], **{
        "prices_e2.parquet": BE.sha256_file(PRICES_PATH),
        "results_head1.json": BE.sha256_file(RESULTS_HEAD1),
        "head1_scorecard.json": BE.sha256_file(SCORECARD_JSON),
        "head1_oof_predictions.parquet": BE.sha256_file(OOF_PATH),
        "sensitivity_split_lookahead.json": BE.sha256_file(SEED0_JSON),
        "yahoo_payloads_sha256_of_shas": BE.sha256_obj(
            {p.name: BE.sha256_file(p) for p in sorted(YAHOO_DIR.glob("*.json"))}),
    })
    modules = {p: BE.sha256_file(ROOT / p) for p in (
        "data/f5/sensitivity_split_lookahead.py", "backtest_e2.py", "scorecard_e2.py",
        "spec.py", "numeric_features_e2.py", "data/f5/census_split_lookahead.py")}
    fingerprint = BE.sha256_obj({"guard": [guard["doc_sha256"], guard["params_sha256"]],
                                 "inputs": inputs, "modules": modules})

    recs = []
    for seed in seeds:
        path = SEEDS_CACHE_DIR / f"seed_{seed:03d}.json"
        rec = None if test_mode else load_cached(path, fingerprint)
        if rec is None:
            t0 = datetime.now(timezone.utc)
            rec = seed_record(seed, preps, params, ratified_scored, recorded)
            rec["fingerprint"] = fingerprint
            rec["seconds"] = round((datetime.now(timezone.utc) - t0).total_seconds(), 1)
            if not test_mode:
                save_cached(path, rec)
            print(f"seed {seed}: primary {rec['primary']['mean_fold_delta_dedup']:+.6f} == recorded; "
                  f"{rec['seconds']} s", flush=True)
        recs.append(rec)

    # GATE over everything that will be written (cached seeds included).
    bad = seed_gate({r["seed"]: r["primary"]["mean_fold_delta_dedup"] for r in recs},
                    [{"seed": s, "mean_fold_delta_dedup": recorded[s]} for s in seeds])
    if bad:
        raise AssertionError(f"seed gate FAILED, nothing written: {bad[:5]}")
    if test_mode:
        for r in recs:
            if r["seed"] == 0:
                got = {a: r[a]["mean_fold_delta_dedup"] for a in ("arm_a", "arm_b")}
                want = {"arm_a": seed0["arm_a_book_to_market_removed"]["mean_fold_delta_dedup"],
                        "arm_b": seed0["arm_b_book_to_market_as_printed"]["mean_fold_delta_dedup"]}
                print(("PASS" if got == want else "FAIL") + f" seed-0 arms vs committed JSON: {got} vs {want}")
        print(f"PASS seed gate on seeds {seeds} (test mode: nothing written)")
        return 0
    sd = float(np.asarray([r["primary"]["mean_fold_delta_dedup"] for r in recs]).std(ddof=1))
    if sd != float(head1["seed_band"]["band_sd"]):
        raise AssertionError(f"band_sd {sd!r} != results_head1.json {head1['seed_band']['band_sd']!r}")

    factor_by_key = pd.DataFrame({"cik": frame[BE.CIK_COL].astype(int).values,
                                  "accession_number": frame["accession_number"].astype(str).values,
                                  "factor": f_frame, "has_bm": frame[BM].notna().values})
    one_block = ratified_scored[ratified_scored["block"] == "text_and_numeric"]
    out = {
        "label": SEEDS_LABEL,
        "specification": "HANDOFF.md §3, 2026-11-10 -- SPLIT ARM: SEED-0 RESULT, AND WHY ITS PRE-SET "
                         "READING IS NOT A FINDING, rule 6 (main-session decision; no owner word)",
        "never_the_primary": "The ratified G3 result stands; no branch is re-labelled.",
        "run": {"utc": started.isoformat(timespec="seconds"), "doc_sha256": guard["doc_sha256"],
                "params_sha256": guard["params_sha256"], "seeds": seeds,
                "module_sha256": modules, "input_sha256": inputs, "cache_fingerprint": fingerprint},
        "seed_gate": {"pass": True, "n_seeds_equal_to_results_head1": len(recs),
                      "band_sd_recomputed": sd, "band_sd_results_head1": float(head1["seed_band"]["band_sd"])},
        "composition": "per seed: backtest_e2.evaluate_arm (fit_predict_seeded, the seed_band path) on "
                       "the seed-0 run's prepared frames -- folds, purge, dedup, PIT rank, per-fold PCA "
                       "built once per arm; calls by scorecard_e2.make_calls / score_calls",
        **assemble_seed_band(recs, head1, seed0),
        "factor_reach": factor_reach(one_block, factor_by_key),
        "inference_note": "Seed-matched differences over the ratified nuisance band; a spread over the "
                          "model seed, not a sampling distribution. No threshold.",
    }
    out["runtime_seconds_this_invocation"] = round((datetime.now(timezone.utc) - started).total_seconds(), 1)
    SEEDS_OUT_PATH.write_text(json.dumps(out, indent=1) + "\n")
    BE.append_run_log(RUN_LOG, {
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "artifact": SEEDS_OUT_PATH.name,
        "sha256": BE.sha256_file(SEEDS_OUT_PATH),
        "doc_sha256": guard["doc_sha256"],
        "params_sha256": guard["params_sha256"],
        "module_sha256s": modules,
        "note": SEEDS_LABEL,
    })
    m = out["seed_matched_arm_minus_primary"]
    print(f"{SEEDS_LABEL}\nseed-matched delta arm A {m['arm_a']['delta']['mean']:+.4f} "
          f"(se {m['arm_a']['delta']['se']:.4f}) | arm B {m['arm_b']['delta']['mean']:+.4f} "
          f"(se {m['arm_b']['delta']['se']:.4f}) | wrote {SEEDS_OUT_PATH}")
    return 0


# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gate-only", action="store_true",
                    help="run the reproduction gate, print PASS/FAIL, fit no arm, write nothing")
    ap.add_argument("--seed-band", action="store_true",
                    help="rule 6: primary, arm A and arm B at every seed of the ratified nuisance band; "
                         "writes only sensitivity_split_lookahead_seeds.json (+ cache, + run_log line)")
    ap.add_argument("--seeds", default=None,
                    help="with --seed-band: comma-separated seeds; checks the gate only, writes nothing")
    args = ap.parse_args(argv)
    if args.seeds is not None and not args.seed_band:
        ap.error("--seeds needs --seed-band")
    if args.seed_band:
        return seed_band_main(args)
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

    frame_b, f_frame, factors, factor_diag, splits, cik_to_ticker = arm_b_frame(frame, nf)
    nf_b = nf.assign(**{BM: corrected_book_to_market(nf[BM], factors).values})

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
