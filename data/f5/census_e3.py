#!/usr/bin/env python3
"""E3 Step 1 -- the pre-registration census for the NUMERIC-FAMILIES signal
program (PRODUCT_PLAN P3 item 2; an "E3" under the ratified §13 stopping rule).

THE FREEZE, inherited from F5_PLAN §1 and from `backtest_e2.py` §0. This
module computes NO information coefficient, no correlation, no model fit and no
feature-versus-outcome association on E2 data. `target_excess_63` is read only to COUNT
completeness (`.isna()` / `.notna()`); its values are never
ranked against, regressed on or compared with any feature. The PIT trailing
rank transform (`spec.pit_trailing_rank_frame`) is a feature-only transform
and reads no outcome. `data/f5/E3_RATIFIED.json` does NOT exist and is not
created here.

What it measures, every number keyed to its artifact (sha256 in `input_sha256`):
  (1) the three candidate frames -- target x numeric on all forms (C); the
      10-K/10-Q subset (A); the E2 run-time frame, i.e. C restricted to filings
      that also carry a text row (B) -- each with the ratified GLD exclusion
      (G3 decision 2) and the 229-style null-target drop;
  (2) coverage of each numeric FAMILY per row -- raw levels and PIT trailing
      ranks (180 d, min 2 comparators, same-day in) -- overall, by form, by
      sector, and inside each of the 33 ratified fold quarters on the dedup
      test rows;
  (3) the fold populations under the SAME 33-quarter walk-forward E2 used
      (2018Q1..2026Q1, purge rule and dedup gap 5 read from the ratified
      G3 parameter block), dedup beside raw;
  (4) the honest MDE for the proposed primary metric (mean per-fold dedup
      Spearman IC of a no-fit, sign-fixed family composite), mirroring the
      G3 §1 / census_e2 §2 algebra but with LEVEL-IC noise anchors that are
      READ from artifacts already on disk, never computed here;
  (5) what has ALREADY been observed about these features against this target
      (the G3 numeric-only block, H1 T2a/T2b) -- read from results files, so
      the pre-registration can state its contamination honestly.

Run (from the repo root, $0, no network):
    python3 data/f5/census_e3.py [--data-root /path/to/data]
`--data-root` exists because the parquet artifacts are git-excluded and a
worktree checkout has no copy; the default is this checkout's `data/`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import backtest_e2 as BE  # noqa: E402  (fold + dedup + sha helpers only)
import spec  # noqa: E402  (frozen pure transform)

OUT_PATH = ROOT / "data" / "f5" / "census_e3.json"
KEY = ["cik", "accession_number"]
OUTCOME_COL = "target_excess_63"  # named here once; read only via .isna()/.notna()

# --------------------------------------------------------------------------
# Constants QUOTED from their source, never invented here.
# --------------------------------------------------------------------------
G3_DOC = ROOT / "data" / "f5" / "G3_PREREGISTRATION.md"     # ratified; parsed for fold list, spec, dedup
RESULTS_HEAD1 = ROOT / "data" / "f5" / "results_head1.json"  # the E2 run: zero-info SDs, observed ICs
CONTROLS = ROOT / "data" / "hardening" / "controls_results.json"  # H1: T0 floor, T2a/T2b SDs
CENSUS_E2 = ROOT / "data" / "f5" / "census_e2.json"

MDE_MULTIPLIER = 2.8          # H2 §4: two-sided 5%, 80% power (z_.975 + z_.80 = 2.80)
POWER_DIVISOR = 2.487         # z_.95 + z_.80; G3 margin rule SE <= Delta / 2.487
RHO_F_ASSUMED = 0.3           # H2 §4's assumed fold autocorrelation; measured in E2 at -0.042
ALPHA = 0.05
PROPOSED_LADDER = [0.03, 0.04, 0.05]  # G3's ratified ladder, inherited unchanged (never above 0.05; red-team M3)

# The family map is a MODEL JUDGMENT (main-session design), reproduced verbatim
# in E3_PREREGISTRATION.md §4. Signs: +1 = higher value expected to go with
# higher excess return; -1 the reverse; None = no pre-registered sign
# (exploratory). Nothing here is read from an outcome.
FAMILIES = {
    "momentum":      {"members": {"momentum_126": +1}, "tier": "confirmatory",
                      "note": "126-session (~6-month) price momentum ending before the news session; "
                              "P3 names 12-1 momentum, which the artifact does not carry (see §5)."},
    "value":         {"members": {"book_to_market": +1}, "tier": "confirmatory",
                      "note": "book equity / market cap at pre_session; earnings yield is not in the artifact."},
    "profitability": {"members": {"net_margin": +1, "operating_margin": +1,
                                  "operating_cashflow_to_revenue": +1}, "tier": "confirmatory",
                      "note": "three margin ratios; accruals are not in the artifact. "
                              "operating_margin is ~20% covered for financials (manifest coverage_by_sector)."},
    "low_volatility": {"members": {"realized_vol_63": -1}, "tier": "confirmatory",
                       "note": "63-session realized volatility (ddof 1); sign negative = low-vol anomaly."},
    "growth":        {"members": {"revenue_yoy_growth": None, "net_income_yoy_growth": None,
                                  "eps_diluted_yoy_growth": None}, "tier": "exploratory",
                      "note": "literature sign is contested; no pre-registered direction."},
    "balance_sheet": {"members": {"leverage_liabilities_to_assets": None, "equity_to_assets": None,
                                  "cash_to_assets": None}, "tier": "exploratory",
                      "note": "no pre-registered direction."},
    "size":          {"members": {"log_total_assets": None}, "tier": "comparator",
                      "note": "G3's zero-information comparator (size_only), not a family under test."},
}
ALL_NUMERIC = sorted({m for f in FAMILIES.values() for m in f["members"]})


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _f(x) -> float | None:
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else float(x)


# --------------------------------------------------------------------------
# §1 Frames
# --------------------------------------------------------------------------

def join_target_numeric(target: pd.DataFrame, numeric: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Mirror of `backtest_e2.join_frames` without the text table: in-membership
    target rows inner-joined to the numeric table on (cik, accession_number),
    sorted deterministically, null targets dropped (counted, never imputed)."""
    diag = {"n_target_rows": int(len(target)), "n_numeric_rows": int(len(numeric))}
    tgt = target[target["in_membership"].astype(bool)].copy()
    diag["n_target_in_membership"] = int(len(tgt))
    dupes = [c for c in ("filing_date", "form", "acceptance_datetime", "info_date",
                         "post_close", "news_session") if c in numeric.columns]
    df = tgt.merge(numeric.drop(columns=dupes), on=KEY, how="inner")
    diag["n_joined"] = int(len(df))
    df["filing_date"] = pd.to_datetime(df["filing_date"])
    df = df.sort_values(["filing_date", "cik", "accession_number"], kind="mergesort").reset_index(drop=True)
    diag["n_target_null_dropped"] = int(df[OUTCOME_COL].isna().sum())
    modeling = df[df[OUTCOME_COL].notna()].copy().reset_index(drop=True)
    diag["n_modeling_rows"] = int(len(modeling))
    diag["n_ciks"] = int(modeling["cik"].nunique())
    diag["forms"] = {k: int(v) for k, v in modeling["form"].value_counts().items()}
    diag["first_filing_date"] = str(modeling["filing_date"].min().date())
    diag["last_filing_date"] = str(modeling["filing_date"].max().date())
    return modeling, diag


def family_coverage(df: pd.DataFrame, label: str) -> dict:
    """Per family: share of rows with ANY member non-null and ALL members
    non-null; per member share. Feature-only counts."""
    n = len(df)
    out = {"frame": label, "n_rows": int(n), "families": {}}
    for fam, meta in FAMILIES.items():
        cols = list(meta["members"])
        present = df[cols].notna()
        out["families"][fam] = {
            "tier": meta["tier"],
            "members": {c: round(float(present[c].mean()), 4) for c in cols},
            "any_member": round(float(present.any(axis=1).mean()), 4),
            "all_members": round(float(present.all(axis=1).mean()), 4),
            "n_any_member": int(present.any(axis=1).sum()),
        }
    conf = [f for f, m in FAMILIES.items() if m["tier"] == "confirmatory"]
    any_by_fam = pd.DataFrame({f: df[list(FAMILIES[f]["members"])].notna().any(axis=1) for f in conf})
    out["confirmatory_families_present_per_row"] = {
        str(k): int(v) for k, v in any_by_fam.sum(axis=1).value_counts().sort_index().items()
    }
    out["share_rows_with_all_4_confirmatory_families"] = round(float((any_by_fam.sum(axis=1) == 4).mean()), 4)
    out["share_rows_with_at_least_3_confirmatory_families"] = round(float((any_by_fam.sum(axis=1) >= 3).mean()), 4)
    return out


def coverage_by(df: pd.DataFrame, by: str) -> dict:
    out = {}
    for key, sub in df.groupby(by, sort=True):
        row = {"n_rows": int(len(sub))}
        for fam, meta in FAMILIES.items():
            row[fam] = round(float(sub[list(meta["members"])].notna().any(axis=1).mean()), 4)
        row["members"] = {c: round(float(sub[c].notna().mean()), 4) for c in ALL_NUMERIC}
        out[str(key)] = row
    return out


def pit_rank_frame(df: pd.DataFrame, spec_params: dict) -> tuple[pd.DataFrame, dict]:
    """The ratified primary specification, applied to the 13 numeric columns
    exactly as `backtest_e2` applies it (window, comparators, same-day rule
    read from the G3 block). Feature-only; no outcome enters."""
    t = time.time()
    ranked = spec.pit_trailing_rank_frame(
        df, ALL_NUMERIC,
        window_days=int(spec_params["window_days"]),
        date_col=spec_params["date_col"],
        ticker_col=spec_params["ticker_col"],
        min_comparators=int(spec_params["min_comparators"]),
        include_same_day=bool(spec_params["include_same_day"]),
    )
    lost = {}
    for c in ALL_NUMERIC:
        raw_ok, rank_ok = df[c].notna(), ranked[c].notna()
        lost[c] = {"raw_nonnull": int(raw_ok.sum()), "rank_nonnull": int(rank_ok.sum()),
                   "lost_to_min_comparators": int((raw_ok & ~rank_ok).sum())}
    return ranked, {"spec": spec_params, "rank_pool": "this frame's own rows only (each frame is ranked within itself; red-team S6)",
                    "per_column": lost, "seconds": round(time.time() - t, 2)}


# --------------------------------------------------------------------------
# §2 Folds (the ratified 33), dedup beside raw, per-fold family coverage
# --------------------------------------------------------------------------

def fold_census(df: pd.DataFrame, ranked: pd.DataFrame, params: dict, label: str) -> dict:
    quarters = list(params["fold_quarters"])
    gap = int(params["dedup"]["gap_days"])
    folds, purge_rows = BE.build_folds(df, quarters, params["purge_rule"])
    keep = BE.dedup_keep_mask_cik(df, gap).values.astype(bool)
    conf = [f for f, m in FAMILIES.items() if m["tier"] == "confirmatory"]
    per_fold = []
    for fold, purge in zip(folds, purge_rows):
        ti = fold["test_idx"]
        dd = ti[keep[ti]]
        row = {
            "test_quarter": str(fold["test_quarter"]),
            "n_test_raw": int(len(ti)),
            "n_test_dedup": int(len(dd)),
            "n_test_ciks": int(df.loc[ti, "cik"].nunique()),
            "n_test_dedup_ciks": int(df.loc[dd, "cik"].nunique()),
            "n_train_expanding": int(purge["n_train_expanding"]),
            "n_train_after_purge": int(purge["n_train_after_purge"]),
            "share_train_purged": round(float(purge["share_purged"]), 4),
            "forms_dedup": {k: int(v) for k, v in df.loc[dd, "form"].value_counts().items()},
            "target_complete_share_dedup": round(float(df.loc[dd, "target_complete"].astype(bool).mean()), 4),
            "coverage_dedup_raw": {}, "coverage_dedup_rank": {},
        }
        for fam in FAMILIES:
            cols = list(FAMILIES[fam]["members"])
            row["coverage_dedup_raw"][fam] = round(float(df.loc[dd, cols].notna().any(axis=1).mean()), 4)
            row["coverage_dedup_rank"][fam] = round(float(ranked.loc[dd, cols].notna().any(axis=1).mean()), 4)
        all4 = pd.DataFrame({f: ranked.loc[dd, list(FAMILIES[f]["members"])].notna().any(axis=1) for f in conf})
        row["n_dedup_rows_with_all_4_confirmatory_ranks"] = int((all4.sum(axis=1) == 4).sum())
        row["n_dedup_rows_with_ge_3_confirmatory_ranks"] = int((all4.sum(axis=1) >= 3).sum())
        per_fold.append(row)
    ndd = np.array([r["n_test_dedup"] for r in per_fold], float)
    nraw = np.array([r["n_test_raw"] for r in per_fold], float)
    in_folds = np.concatenate([f["test_idx"] for f in folds])
    return {
        "frame": label,
        "n_frame_rows": int(len(df)),
        "n_frame_ciks": int(df["cik"].nunique()),
        "n_folds": len(folds),
        "fold_quarters": [r["test_quarter"] for r in per_fold],
        "purge_rule": params["purge_rule"],
        "dedup_gap_days": gap,
        "dedup_rule": "backtest.company_quarter_dedup_keep_mask wrapped on cik (backtest_e2.dedup_keep_mask_cik)",
        "n_rows_in_folds_raw": int(nraw.sum()),
        "n_rows_in_folds_dedup": int(ndd.sum()),
        "dedup_share_in_folds": round(float(ndd.sum() / nraw.sum()), 4),
        "n_whole_frame_dedup": int(keep.sum()),
        "n_distinct_ciks_in_folds": int(df.loc[in_folds, "cik"].nunique()),
        "n_test_dedup_min": int(ndd.min()), "n_test_dedup_max": int(ndd.max()),
        "n_test_dedup_mean": round(float(ndd.mean()), 2),
        "n_test_raw_min": int(nraw.min()), "n_test_raw_max": int(nraw.max()),
        "n_purge_instances": int(sum(p["n_purged"] for p in purge_rows)),
        "purge_note": "no E3 arm fits anything, so no E3 arm has a training set; the purge figures are what "
                      "backtest_e2.build_folds computes on this frame and are recorded for comparability only",
        "n_folds_with_more_rows_than_ciks": int(sum(1 for r in per_fold if r["n_test_raw"] > r["n_test_ciks"])),
        "folds_with_more_rows_than_ciks": [r["test_quarter"] for r in per_fold if r["n_test_raw"] > r["n_test_ciks"]],
        "n_dedup_rows_in_folds_with_all_4_confirmatory_ranks": int(sum(r["n_dedup_rows_with_all_4_confirmatory_ranks"] for r in per_fold)),
        "n_dedup_rows_in_folds_with_ge_3_confirmatory_ranks": int(sum(r["n_dedup_rows_with_ge_3_confirmatory_ranks"] for r in per_fold)),
        "per_fold": per_fold,
    }


# --------------------------------------------------------------------------
# §3 Honest MDE for a LEVEL IC (mirrors census_e2 §2; anchors READ, not computed)
# --------------------------------------------------------------------------

def ar1_inflation(rho: float, k: int) -> float:
    """H2 §4 finite-k AR(1) variance inflation, returned as the SE multiplier."""
    if rho == 0:
        return 1.0
    return float(np.sqrt(1.0 + 2.0 * sum((1 - l / k) * rho ** l for l in range(1, k))))


def level_ic_anchors(head1: dict, controls: dict) -> dict:
    """Cross-fold SDs of per-fold LEVEL ICs already measured on this target or
    on H1's event panel, read from the committed results. Each is the SD of a
    single-predictor (or near-single) rank IC across quarters -- the quantity a
    no-fit family composite's per-fold IC will resemble. None of these numbers
    is computed here."""
    zi = {z["benchmark"]: z for z in head1["standing"]["zero_information_summary"]}
    t2a = controls["controls"]["T2a_pead_core"]["dedup"]
    t2b = controls["controls"]["T2b_momentum_core"]["dedup"]
    return {
        "size_only_rank_e2": {
            "sd": float(zi["size_only_rank"]["std_ic_dedup"]), "k": int(zi["size_only_rank"]["n_folds"]),
            "source": "results_head1.json .standing.zero_information_summary[size_only_rank].std_ic_dedup",
            "what": "cross-fold SD of the dedup per-fold Spearman IC of the one-feature size rank on the E2 33 folds",
        },
        "ticker_training_mean_e2": {
            "sd": float(zi["ticker_training_mean_rank"]["std_ic_dedup"]), "k": int(zi["ticker_training_mean_rank"]["n_folds"]),
            "source": "results_head1.json .standing.zero_information_summary[ticker_training_mean_rank].std_ic_dedup",
            "what": "cross-fold SD of the dedup per-fold IC of the ticker-training-mean zero-information predictor",
        },
        "h1_t2a_pead_core": {
            "sd": float(t2a["sd_ic_ddof1"]), "k": int(t2a["n_periods"]),
            "source": "data/hardening/controls_results.json .controls.T2a_pead_core.dedup.sd_ic_ddof1",
            "what": "cross-quarter SD of the dedup per-quarter IC of SUE at earnings 8-Ks (H1, 40 quarters)",
        },
        "h1_t2b_momentum_core": {
            "sd": float(t2b["sd_ic_ddof1"]), "k": int(t2b["n_periods"]),
            "source": "data/hardening/controls_results.json .controls.T2b_momentum_core.dedup.sd_ic_ddof1",
            "what": "cross-quarter SD of the dedup per-quarter IC of 12-1 momentum at earnings 8-Ks (H1, 40 quarters)",
        },
    }


def mde_rows(anchor_name: str, sd: float, ndd: np.ndarray, n_tests: int) -> list[dict]:
    """SE(mean fold IC) = sd / sqrt(k) x AR(1) inflation; MDE = 2.8 x SE for one
    test; Holm-worst-case (Bonferroni at alpha/n_tests) multiplier for the
    per-family secondaries. The anchor SD is treated as homogeneous across
    folds because it was measured that way; the independence lower bound
    below is the only per-fold-heterogeneous row."""
    k = len(ndd)
    out = []
    z80 = stats.norm.ppf(0.80)
    mult_holm = float(stats.norm.ppf(1 - ALPHA / (2 * n_tests)) + z80)
    for rho in (0.0, RHO_F_ASSUMED):
        infl = ar1_inflation(rho, k)
        se = sd / np.sqrt(k) * infl
        out.append({
            "anchor": anchor_name, "rho_f": rho, "k": k, "anchor_sd": round(sd, 4),
            "ar1_se_multiplier": round(infl, 4),
            "SE": round(float(se), 4),
            "MDE_single_test_2p8": round(float(MDE_MULTIPLIER * se), 4),
            f"MDE_holm_worst_case_{n_tests}_tests": round(float(mult_holm * se), 4),
            "holm_worst_case_multiplier": round(mult_holm, 3),
            "null_bound_95": round(float(1.96 * se), 4),
            "ladder_selected": next((d for d in PROPOSED_LADDER if se <= d / POWER_DIVISOR), None),
        })
    return out


def independence_bound_rows(ndd: np.ndarray, n_tests: int) -> list[dict]:
    """The LOWER bound no design can beat: if the per-fold IC were computed
    on n_dd(j) independent rows with no cross-sectional dependence, its
    sampling SD is ~1/sqrt(n_dd(j) - 1). Real per-fold ICs are far more
    dispersed (common factor exposure), which is what the measured anchors
    show; this row exists so the gap is visible."""
    k = len(ndd)
    sig = 1.0 / np.sqrt(ndd - 1.0)
    z80 = stats.norm.ppf(0.80)
    mult_holm = float(stats.norm.ppf(1 - ALPHA / (2 * n_tests)) + z80)
    out = []
    for rho in (0.0, RHO_F_ASSUMED):
        infl = ar1_inflation(rho, k)
        se = float(np.sqrt((sig ** 2).sum()) / k * infl)
        out.append({
            "anchor": "independence_lower_bound_1_over_sqrt_ndd", "rho_f": rho, "k": k,
            "sigma_fold_mean": round(float(sig.mean()), 4),
            "ar1_se_multiplier": round(infl, 4), "SE": round(se, 4),
            "MDE_single_test_2p8": round(MDE_MULTIPLIER * se, 4),
            f"MDE_holm_worst_case_{n_tests}_tests": round(mult_holm * se, 4),
            "null_bound_95": round(1.96 * se, 4),
            "ladder_selected": next((d for d in PROPOSED_LADDER if se <= d / POWER_DIVISOR), None),
        })
    return out


def n_adjusted_sd(sd: float, n_measured: float, n_target: float) -> float:
    """Swap the independent-sampling component 1/(n-1) of a measured cross-fold
    IC variance from the per-fold size it was measured at to the target frame's
    per-fold size (red-team S11). Everything else in the variance (regime
    dispersion) is kept as measured."""
    var = sd ** 2 - 1.0 / (n_measured - 1.0) + 1.0 / (n_target - 1.0)
    return float(np.sqrt(max(var, 0.0)))


def mde_block(fold_blocks: dict, head1: dict, controls: dict, n_confirmatory: int) -> dict:
    anchors = level_ic_anchors(head1, controls)
    n_dd_b = float(head1["standing"]["bootstrap_anchor"]["pit_trailing_rank"]["summary"]["mean_n_test_dedup"])
    for name in ("size_only_rank_e2", "ticker_training_mean_e2"):
        anchors[name]["measured_at_n_dd_mean"] = round(n_dd_b, 2)
    for name in ("h1_t2a_pead_core", "h1_t2b_momentum_core"):
        per = controls["controls"][{"h1_t2a_pead_core": "T2a_pead_core", "h1_t2b_momentum_core": "T2b_momentum_core"}[name]]["dedup"]["per_period"]
        anchors[name]["measured_at_n_per_period_mean"] = round(float(np.mean([x["n"] for x in per])), 1)
    out = {
        "algebra": {
            "step_1": "sigma_anchor = cross-fold SD of a single-predictor per-fold LEVEL IC, READ from a committed artifact",
            "step_2": "SE(mean fold IC) = sigma_anchor / sqrt(k) * sqrt(1 + 2*sum_{l=1}^{k-1}(1-l/k)*rho_f^l)",
            "step_3": f"MDE (one test) = {MDE_MULTIPLIER} * SE; MDE (Holm worst case over n tests) = (z_(1-0.05/(2n)) + z_0.80) * SE",
            "step_4": f"equivalence margin Delta = smallest rung of {PROPOSED_LADDER} with SE <= Delta/{POWER_DIVISOR}; none -> UNPOWERED",
            "why_not_the_h2_delta_anchor": "census_e2 §2 anchors a DELTA between two fitted blocks sharing the numeric features "
                                           "(H2 within-fold bootstrap SD 0.1149 at n_dd 39.5). A level IC of one family has no "
                                           "shared component to cancel; its cross-fold dispersion is the anchor's, not the delta's.",
            "caveats": [
                "Every MDE is a LOWER bound: folds are not independent (overlapping 63-session windows, common regimes). "
                "The AR(1) rho is an assumption at 0.3; E2 measured the fold-delta lag-1 autocorrelation at -0.042 "
                "(results_head1.json .margin.measured_lag1_autocorrelation) -- for a DELTA, not a level.",
                "The anchors are single-predictor ICs. A 4-family equal-weight composite may be less dispersed per fold; "
                "no measurement of that exists before the run, so no smaller anchor is claimed.",
                "The t-correction at k=33 (t_.975(32)+t_.80(32) = 2.890 vs 2.8) is NOT applied, matching census_e2.",
                "The two E2 anchors were measured at frame B's per-fold size (n_dd 135.79); the *_n_adjusted_to_this_frame rows "
                "swap the 1/(n-1) sampling component to each frame's own n_dd (red-team S11). The H1 anchors were measured at "
                "80-97 events per quarter, close to frame A's 92.5, and are not adjusted.",
            ],
        },
        "anchors": anchors,
        "h1_zero_information_floor": {
            "floor_lo": float(head1["noise_floor_h1"]["floor_lo"]),
            "floor_hi": float(head1["noise_floor_h1"]["floor_hi"]),
            "definition": head1["noise_floor_h1"]["definition"],
            "source": "results_head1.json .noise_floor_h1 (from controls_results.json T0 placebo arms)",
        },
        "by_frame": {},
    }
    for label, fb in fold_blocks.items():
        ndd = np.array([r["n_test_dedup"] for r in fb["per_fold"]], float)
        rows = independence_bound_rows(ndd, n_confirmatory)
        for name, a in anchors.items():
            rows += mde_rows(name, a["sd"], ndd, n_confirmatory)
        for name in ("size_only_rank_e2", "ticker_training_mean_e2"):
            adj = n_adjusted_sd(anchors[name]["sd"], n_dd_b, float(ndd.mean()))
            rows += mde_rows(name + "_n_adjusted_to_this_frame", adj, ndd, n_confirmatory)
        out["by_frame"][label] = {
            "k": fb["n_folds"], "n_dd_mean": fb["n_test_dedup_mean"],
            "n_dd_min": fb["n_test_dedup_min"], "n_dd_max": fb["n_test_dedup_max"],
            "rows": rows,
        }
    return out


# --------------------------------------------------------------------------
# §4 What has already been observed (contamination record; READ from files)
# --------------------------------------------------------------------------

def prior_exposure(head1: dict, controls: dict) -> dict:
    """The E2 run and H1 have already reported associations between these
    numeric features and this target (or H1's event-panel target). A clean
    pre-registration is impossible for those quantities; this block records
    them so E3_PREREGISTRATION.md can quote, not hide, them. Arithmetic here
    is a MEAN OF ALREADY-COMPUTED per-fold numbers read from the results file."""
    rows = head1["per_fold_ic__pit_trailing_rank"]
    def mean_of(block, eval_set):
        vals = [r["spearman_ic"] for r in rows if r["block"] == block and r["eval_set"] == eval_set
                and r["spearman_ic"] is not None]
        return {"mean_of_committed_per_fold_ic": round(float(np.mean(vals)), 4), "n_folds": len(vals),
                "positive_folds": int(sum(v > 0 for v in vals))}
    zi = {z["benchmark"]: z for z in head1["standing"]["zero_information_summary"]}
    t2a = controls["controls"]["T2a_pead_core"]["dedup"]
    t2b = controls["controls"]["T2b_momentum_core"]["dedup"]
    fa = head1["form_controlled_ablation"]
    def mean_rows(rws, block, eval_set):
        vals = [r["spearman_ic"] for r in rws if r["block"] == block and r["eval_set"] == eval_set
                and r["spearman_ic"] is not None]
        return {"mean_of_committed_per_fold_ic": round(float(np.mean(vals)), 4), "n_folds": len(vals),
                "positive_folds": int(sum(v > 0 for v in vals))}
    sc = head1["scorecard_summary"]["blocks"]
    return {
        "g3_form_controlled_ablation_10K_10Q_rows": {
            "what": "G3's fitted blocks scored on the 10-K/10-Q rows of the E2 frame ONLY -- 3,497 rows, 96% of frame A -- "
                    "ranked within that periodic-only pool, exactly as the census ranks frame A (red-team M1). "
                    "This is the closest existing observation to E3's primary frame.",
            "n_rows": int(fa["n_rows"]),
            "numeric_only_dedup": mean_rows(fa["per_fold_ic"], "numeric_only", "dedup"),
            "numeric_only_raw": mean_rows(fa["per_fold_ic"], "numeric_only", "raw"),
            "text_and_numeric_dedup": mean_rows(fa["per_fold_ic"], "text_and_numeric", "dedup"),
            "size_only_fitted_dedup": mean_rows(fa["per_fold_ic"], "size_only", "dedup"),
            "source": "results_head1.json .form_controlled_ablation.per_fold_ic",
        },
        "g3_numeric_only_raw_levels_spec_dedup": {**mean_rows(head1["per_fold_ic__raw_levels"], "numeric_only", "dedup"),
                                                 "source": "results_head1.json .per_fold_ic__raw_levels"},
        "g3_numeric_only_no_same_day_arm_dedup": {**mean_rows(head1["per_fold_ic__pit_trailing_rank_no_same_day"], "numeric_only", "dedup"),
                                                  "what": "the include_same_day=False arm, which E3 also runs",
                                                  "source": "results_head1.json .per_fold_ic__pit_trailing_rank_no_same_day"},
        "g3_per_fold_quintile_spread_exists": "every G3 per-fold IC row also carries `quintile_spread` (top-minus-bottom quintile "
                                              "mean realized excess return) for every block; E3 suppresses that column (red-team S3)",
        "g3_scorecard_hit_rates_frame_B": {
            b: {"hit_rate": round(float(sc[b]["hit_rate"]), 4), "wilson_95": [round(float(sc[b]["wilson_lo"]), 4), round(float(sc[b]["wilson_hi"]), 4)],
                "n_calls": int(sc[b]["n_calls"])}
            for b in ("numeric_only", "size_only", "text_and_numeric")
        } | {"source": "results_head1.json .scorecard_summary.blocks (universe block; per-company rows are on disk, git-excluded)"},
        "statement": "These associations EXIST ON DISK before E3 is pre-registered. They were produced under the "
                     "ratified G3 pre-registration (2026-11-05) and under H1 (2026-08-25), not by this census. "
                     "E3's primary is a different estimand (a no-fit, sign-fixed family composite's LEVEL IC) and "
                     "has not been computed; the numbers below are prior knowledge the owner holds when ruling.",
        "g3_numeric_only_block_dedup": {**mean_of("numeric_only", "dedup"),
                                        "what": "XGBoost on all 13 numeric features (PIT ranks), out-of-fold, 33 folds",
                                        "source": "results_head1.json .per_fold_ic__pit_trailing_rank[block=numeric_only, eval_set=dedup].spearman_ic"},
        "g3_numeric_only_block_raw": mean_of("numeric_only", "raw"),
        "g3_size_only_block_dedup": {**mean_of("size_only", "dedup"),
                                     "what": "XGBoost on log_total_assets alone (PIT rank), out-of-fold"},
        "g3_zero_information_size_rank_dedup": {"mean_ic": round(float(zi["size_only_rank"]["mean_ic_dedup"]), 4),
                                                 "positive_folds": int(zi["size_only_rank"]["positive_folds_dedup"]),
                                                 "source": "results_head1.json .standing.zero_information_summary"},
        "g3_zero_information_ticker_mean_dedup": {"mean_ic": round(float(zi["ticker_training_mean_rank"]["mean_ic_dedup"]), 4),
                                                   "positive_folds": int(zi["ticker_training_mean_rank"]["positive_folds_dedup"])},
        "h1_t2b_momentum_12_1_core_dedup": {"mean_ic": round(float(t2b["mean_ic"]), 4), "se_ic": round(float(t2b["se_ic"]), 4),
                                             "t_stat": round(float(t2b["t_stat"]), 3),
                                             "block_bootstrap_ci95": [round(float(x), 4) for x in t2b["block_bootstrap_ci95"]],
                                             "n_periods": int(t2b["n_periods"]), "n_events": int(t2b["n_events_total"]),
                                             "verdict": controls["verdicts"]["T2b_momentum"],
                                             "implied_mde": round(float(controls["implied_mde_two_sided_5pct_80pct_power"]["T2b_momentum_core"]), 4),
                                             "what": "12-1 momentum at earnings 8-Ks vs forward excess return, H1 (2026-08-25); "
                                                     "a different construct (12-1, event panel) from momentum_126 on all filings",
                                             "source": "data/hardening/controls_results.json .controls.T2b_momentum_core.dedup"},
        "h1_t2a_pead_core_dedup": {"mean_ic": round(float(t2a["mean_ic"]), 4), "se_ic": round(float(t2a["se_ic"]), 4),
                                    "t_stat": round(float(t2a["t_stat"]), 3),
                                    "block_bootstrap_ci95": [round(float(x), 4) for x in t2a["block_bootstrap_ci95"]],
                                    "n_periods": int(t2a["n_periods"]), "n_events": int(t2a["n_events_total"]),
                                    "verdict": controls["verdicts"]["T2a_pead"],
                                    "implied_mde": round(float(controls["implied_mde_two_sided_5pct_80pct_power"]["T2a_pead_core"]), 4),
                                    "what": "SUE (seasonal random walk) at earnings 8-Ks vs forward excess return, H1; PEAD is NOT in "
                                            "numeric_features_e2.parquet and would be a build item",
                                    "source": "data/hardening/controls_results.json .controls.T2a_pead_core.dedup"},
        "f6_statement": "F6_E2_RESULT.md §4: 'This run did not test them as a signal. Numeric-only's mean IC of +0.0251 sits "
                        "below the ticker-mean benchmark (+0.0362) and the H1 noise floor (§1.7). Nothing here is evidence for them.'",
    }


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def g3_params() -> dict:
    """The ratified fold list, spec, dedup gap and purge rule, PARSED from the
    pinned document (never retyped). The guard is not called: nothing here fits."""
    params = BE.extract_params_block(G3_DOC.read_text())
    pinned = json.loads((ROOT / "data/f5/G3_RATIFIED.json").read_text())
    assert sha256_file(G3_DOC) == pinned["doc_sha256"], "G3 document sha does not match its pin"
    return params


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", type=Path, default=ROOT / "data",
                    help="directory holding the git-excluded parquet artifacts (default: this checkout's data/)")
    args = ap.parse_args()
    data = args.data_root.resolve()
    f5 = data / "f5"
    t_all = time.time()
    rt = {}

    params = g3_params()
    head1 = json.loads(RESULTS_HEAD1.read_text())
    controls = json.loads(CONTROLS.read_text())
    census_e2 = json.loads(CENSUS_E2.read_text())

    t = time.time()
    numeric_p, target_p, text_p = f5 / "numeric_features_e2.parquet", f5 / "target_e2.parquet", f5 / "text_features_e2.parquet"
    shas = BE.assert_input_shas([
        (target_p, ROOT / "data/f5/target_e2_manifest.json"),
        (numeric_p, ROOT / "data/f5/numeric_features_e2_manifest.json"),
        (text_p, ROOT / "data/f5/text_features_e2_manifest.json"),
    ])
    assert shas["target_e2.parquet"] == head1["frame"]["input_sha256"]["target_e2.parquet"]
    assert shas["numeric_features_e2.parquet"] == head1["frame"]["input_sha256"]["numeric_features_e2.parquet"]
    target = pd.read_parquet(target_p)
    numeric = pd.read_parquet(numeric_p)
    text_keys = pd.read_parquet(text_p, columns=KEY)
    rt["load_and_sha"] = round(time.time() - t, 2)

    t = time.time()
    frame_c, diag_c = join_target_numeric(target, numeric)
    gld_params = {"gld": {"exclude_from_analysis": True}}
    frame_c, gld_c = BE.exclude_gld_rows(frame_c, gld_params)
    frame_c = frame_c.reset_index(drop=True)
    frame_a = frame_c[frame_c["form"].isin(["10-K", "10-Q"])].reset_index(drop=True)
    frame_b = frame_c.merge(text_keys, on=KEY, how="inner").reset_index(drop=True)
    frames = {"C_all_forms_numeric": frame_c, "A_periodic_10K_10Q": frame_a, "B_e2_run_time_frame": frame_b}
    rt["frames"] = round(time.time() - t, 2)

    e2_run_time_rows = int(census_e2["section_1b_ratified_folds_ex_gld"]["n_frame_rows"])
    tman_rows_in_membership = json.loads((ROOT / "data/f5/target_e2_manifest.json").read_text())["row_counts"]["n_in_membership"]
    a_in_b = frame_a.merge(text_keys, on=KEY, how="inner")
    reproduction = {
        "n_frame_A_rows_also_in_frame_B": int(len(a_in_b)),
        "n_frame_A_rows_also_in_frame_B_note": "periodic rows that also carry a text row: the rows on which G3's numeric_only "
                                               "out-of-fold predictions exist and can be read as a same-rows comparator (red-team N13); "
                                               "the in-fold dedup subset is counted by Step 3",
        "e2_run_time_frame_rows_expected": e2_run_time_rows,
        "frame_B_rows_measured": int(len(frame_b)),
        "frame_B_reproduces_e2_run_time_frame": bool(len(frame_b) == e2_run_time_rows),
        "e2_in_membership_target_rows_expected": int(tman_rows_in_membership),
        "in_membership_target_rows_measured": diag_c["n_target_in_membership"],
    }

    frame_desc = {}
    for label, fr in frames.items():
        frame_desc[label] = {
            "n_rows": int(len(fr)), "n_ciks": int(fr["cik"].nunique()),
            "forms": {k: int(v) for k, v in fr["form"].value_counts().items()},
            "sectors": {k: int(v) for k, v in fr["sector"].value_counts().items()},
            "first_filing_date": str(fr["filing_date"].min().date()),
            "last_filing_date": str(fr["filing_date"].max().date()),
            "n_fx_blocked_rows": int((fr["fx_currency"].astype(str) != "USD").sum()) if "fx_currency" in fr else None,
            "target_complete_share": round(float(fr["target_complete"].astype(bool).mean()), 4),
        }
    frame_desc["C_all_forms_numeric"].update({"join_diagnostics": diag_c, "gld_exclusion": gld_c})
    frame_desc["chain"] = (
        f"{diag_c['n_target_rows']} target rows -> {diag_c['n_target_in_membership']} in-membership -> "
        f"{diag_c['n_joined']} joined to the numeric table -> {diag_c['n_modeling_rows']} after "
        f"{diag_c['n_target_null_dropped']} null targets -> {len(frame_c)} after {gld_c['n_gld_rows_excluded']} GLD rows (C); "
        f"A = {len(frame_a)} 10-K/10-Q rows of C; B = {len(frame_b)} rows of C that also carry a text row"
    )

    t = time.time()
    coverage, ranks, rank_diag, fold_blocks = {}, {}, {}, {}
    for label, fr in frames.items():
        coverage[label] = {
            "raw_levels": family_coverage(fr, label),
            "raw_by_form": coverage_by(fr, "form"),
            "raw_by_sector": coverage_by(fr, "sector"),
        }
        ranked, rd = pit_rank_frame(fr, params["spec"])
        ranks[label], rank_diag[label] = ranked, rd
        coverage[label]["pit_trailing_rank"] = family_coverage(ranked, label + "_ranked")
        coverage[label]["rank_by_form"] = coverage_by(ranked, "form")
        coverage[label]["rank_by_sector"] = coverage_by(ranked, "sector")
        coverage[label]["rank_loss"] = rd
    rt["coverage_and_ranks"] = round(time.time() - t, 2)

    t = time.time()
    for label, fr in frames.items():
        fold_blocks[label] = fold_census(fr, ranks[label], params, label)
    rt["folds"] = round(time.time() - t, 2)

    # S1: survivorship / price censoring, carried from census_e2 (same membership, same quarters;
    # channel A = core CIK with no price column at all, so it never enters ANY E3 frame)
    pc = census_e2["section_1b_price_censoring"]
    chan_a = {q["q"]: q for q in pc["per_candidate_quarter"]}
    tman = json.loads((ROOT / "data/f5/target_e2_manifest.json").read_text())
    survivorship = {
        "n_core_ciks": int(pc["summary"]["n_core_ciks"]),
        "n_core_ciks_no_price_column": int(pc["summary"]["n_core_ciks_no_price_column"]),
        "n_core_ciks_no_price_column_by_sector": pc["summary"]["n_core_ciks_no_price_column_by_sector"],
        "n_ciks_in_target_table": int(target["cik"].nunique()),
        "n_core_filings_excluded_solely_missing_subject_prices": int(tman["row_counts"]["n_filings_excluded_solely_missing_subject_prices"]),
        "n_complete_window_missing_subject_price": int(tman["row_counts"]["n_complete_window_missing_subject_price"]),
        "channel_A_per_fold": [{"test_quarter": q, "n_ciks_channel_A": int(chan_a[q]["n_ciks_A"]), "n_rows_channel_A": int(chan_a[q]["n_rows_A"])}
                               for q in params["fold_quarters"] if q in chan_a],
        "channel_A_definition": pc["per_candidate_quarter"] and pc["summary"]["channel_A_definition"],
        "null_target_rows_dropped_before_ranking": {label: int(d) for label, d in
                                                    (("C_all_forms_numeric", diag_c["n_target_null_dropped"]),)},
        "direction_by_family_statement": (
            "Dead-name exclusion removes the worst outcomes from the scored set. Its direction differs by family: "
            "dropping dead high-volatility / low-momentum losers biases the low_volatility and momentum ICs DOWN "
            "(their worst confirming cases are missing); dropping dead distressed high-book-to-market names biases "
            "the value IC UP (its worst disconfirming cases are missing); profitability is ambiguous. The cause of "
            "the missing prices is not separately measured, so none of this is called delisting (G3 §11)."
        ),
        "source": "census_e2.json .section_1b_price_censoring (summary, per_candidate_quarter); target_e2_manifest.json .row_counts",
    }

    n_confirmatory = sum(1 for m in FAMILIES.values() if m["tier"] == "confirmatory")
    mde = mde_block(fold_blocks, head1, controls, n_confirmatory)
    exposure = prior_exposure(head1, controls)

    # what is NOT on the artifact (P3 item 2 names these)
    not_on_artifact = {
        "momentum_12_1": "P3 names 12-1 momentum; the artifact carries momentum_126 (126 sessions, ending at pre_session). "
                         "A 12-1 column is a numeric_features_e2.py build (price-only, PIT by construction) -- Step 3 at the earliest, "
                         "and H1 T2b has already measured 12-1 at earnings events (see prior_exposure).",
        "earnings_yield": "not built; needs PIT net income / market cap -- the same machinery as book_to_market.",
        "accruals": "not built; needs PIT net income minus operating cash flow over assets; operating_cash_flow coverage is 42% (period-mismatch filter).",
        "pead_sue": "not in the artifact; controls.py computes SUE at earnings 8-Ks for H1 and already reported T2a (AMBIGUOUS). "
                    "Porting it is a build item; its E2 association is already observed.",
    }

    sources = {}
    for p in [target_p, numeric_p, text_p]:
        sources[f"data/f5/{p.name}"] = shas[p.name]
    for p in ["data/f5/target_e2_manifest.json", "data/f5/numeric_features_e2_manifest.json",
              "data/f5/text_features_e2_manifest.json", "data/f5/results_head1.json",
              "data/f5/census_e2.json", "data/f5/G3_PREREGISTRATION.md", "data/f5/G3_RATIFIED.json",
              "data/hardening/controls_results.json", "backtest_e2.py", "backtest.py", "spec.py",
              "numeric_features_e2.py", "data/f5/census_e3.py"]:
        fp = ROOT / p
        if fp.exists():
            sources[p] = sha256_file(fp)

    census = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "module": "data/f5/census_e3.py",
        "step": "E3 Step 1 -- numeric-families pre-registration census (PRODUCT_PLAN P3 item 2)",
        "data_root": str(data),
        "network_calls": 0,
        "api_spend_usd": 0.0,
        "freeze_statement": (
            "No information coefficient, correlation, model fit or feature-versus-outcome association was computed. "
            "target_excess_63 was read only to COUNT completeness (.isna()/.notna()). The PIT rank transform reads no "
            "outcome. data/f5/E3_RATIFIED.json does NOT exist and was not created. The 'prior_exposure' block is READ "
            "from results already committed under the ratified G3 run and H1; its arithmetic is a mean of committed "
            "per-fold numbers."
        ),
        "ruling_b_statement": "Owner ruling B (2026-11-05): no EODHD, no new spend; prices stay the 2026-08-24 snapshot. "
                              "No money metric (portfolio return, Sharpe, drawdown, P&L) appears here or in E3.",
        "input_sha256": sources,
        "g3_parameters_read": {"fold_quarters": params["fold_quarters"], "spec": params["spec"],
                               "dedup": params["dedup"], "purge_rule": params["purge_rule"],
                               "source": "data/f5/G3_PREREGISTRATION.md ```json g3-params``` block, sha-checked against G3_RATIFIED.json"},
        "families": {f: {"members": m["members"], "tier": m["tier"], "note": m["note"]} for f, m in FAMILIES.items()},
        "families_note": "MODEL JUDGMENT (main-session design); the owner rules on it in E3_OWNER_PACKET.md decision 2.",
        "section_1_frames": frame_desc,
        "section_1_reproduction_checks": reproduction,
        "section_2_coverage": coverage,
        "section_3_folds": fold_blocks,
        "section_4_mde": mde,
        "section_4b_survivorship_price_censoring": survivorship,
        "section_5_prior_exposure": exposure,
        "section_6_not_on_the_artifact": not_on_artifact,
        "runtimes_seconds": {**rt, "total": round(time.time() - t_all, 2)},
    }
    OUT_PATH.write_text(json.dumps(census, indent=1, default=str) + "\n")
    print(f"wrote {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes) in {census['runtimes_seconds']['total']} s")
    print(frame_desc["chain"])
    print("reproduction:", reproduction)
    for label, fb in fold_blocks.items():
        print(f"{label}: k={fb['n_folds']} rows_in_folds raw={fb['n_rows_in_folds_raw']} dedup={fb['n_rows_in_folds_dedup']} "
              f"n_dd mean={fb['n_test_dedup_mean']} [{fb['n_test_dedup_min']},{fb['n_test_dedup_max']}] ciks={fb['n_distinct_ciks_in_folds']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
