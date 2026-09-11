#!/usr/bin/env python3
"""F5 Step 2 — the pre-run census that fills the G3 document's "measured
population" column (F5_PLAN.md §2 Step 2).

THE FREEZE (F5_PLAN §1). This module computes NO information coefficient, no
correlation, no model fit and no feature-versus-outcome association on E2 data.
`target_excess_63` is touched only to COUNT completeness/censoring (`.isna()`,
`.notna()`); its values are never correlated with, regressed on, or ranked
against any feature. Feature-versus-COMPANY-IDENTITY statistics (the §6 ICCs)
are allowed and are the H2 §2 identification argument re-measured on E2.

It REUSES the Step 1a/1b measurements rather than recomputing them; every number
it emits carries a `source` path. The genuinely new measurements here are:
  (1) per-fold populations for the three fold options of decision 4;
  (2) the per-fold, two-channel price-censoring count (F5_PLAN §2 calls this
      "the genuinely unmeasured part");
  (3) the MDE re-derivation at the ratified fold count and the MEASURED n_dd;
  (4) the ladder feasibility for decision 15;
  (5) the 10 CIKs whose periodic filings were never extracted;
  (6) the E2 ICCs against company identity;
  (7) the WITHDRAWN per-year/quarter distribution and its frame-row footprint.

Run:  python3 data/f5/census_e2.py     (from the repo root; $0, no network)
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import backtest_e2 as BE  # noqa: E402  (frozen Step-1b runner, census-safe helpers)
import spec  # noqa: E402  (frozen pure transform)

OUT_PATH = ROOT / "data" / "f5" / "census_e2.json"

# --------------------------------------------------------------------------
# Constants that are QUOTED FROM a source, never invented here.
# --------------------------------------------------------------------------

# H2 §4 / EXPANSION_PLAN §2a amendment — the MDE algebra's inputs.
H2 = {
    "mde_multiplier": 2.8,                       # 2.8 x SE; two-sided 5%, 80% power
    "n_dd_reference": 39.5,                      # E1 dedup rows/fold the bootstrap SD was measured at
    "within_fold_bootstrap_sd_mean": {           # H2 §3.2, 4,000 resamples/fold
        "raw_levels": 0.1046,
        "pit_trailing_rank": 0.1149,
    },
    "implied_regime_floor": {                    # H2 §3.2 / EXPANSION_PLAN §2a amendment
        "raw_levels": 0.0000,
        "pit_trailing_rank": 0.0992,
    },
    "rho_f_assumed": 0.3,
    "planning_n_dd": 158,                        # 100 co x 1.58 E1 dedup rows/co/fold
    "planning_k": 26,
    "lambda_true_construct": 0.8,
    "per_family_mde_scaling": [0.4, 2.4],
    "source": "data/hardening/status/H2_spec.md §4 + EXPANSION_PLAN.md §2a AMENDMENT 2026-08-25",
}

LADDER = [0.03, 0.04, 0.05]          # F5_PLAN §3 decision 15, pre-registered
POWER_DIVISOR = 2.487                # z_0.95 + z_0.80; SE <= Delta/2.487 (H2 §4)

NUMERIC_RAW_FEATURES = [
    "log_total_assets", "leverage_liabilities_to_assets", "equity_to_assets",
    "cash_to_assets", "net_margin", "operating_margin",
    "operating_cashflow_to_revenue", "revenue_yoy_growth",
    "net_income_yoy_growth", "eps_diluted_yoy_growth", "momentum_126",
    "realized_vol_63", "book_to_market",
]

FOLD_OPTIONS = {
    "default_33":            ("2018Q1", "2026Q1"),
    "default_33_post2019_29": ("2019Q1", "2026Q1"),
    "default_33_post2019_25": ("2020Q1", "2026Q1"),
    "alt_26":                ("2019Q4", "2026Q1"),
    "alt_26_post2019_26":    ("2019Q4", "2026Q1"),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def quarters(a: str, b: str) -> list[str]:
    return [str(q) for q in pd.period_range(a, b, freq="Q")]


# --------------------------------------------------------------------------
# §1 Fold options (decision 4)
# --------------------------------------------------------------------------

def fold_options(head1: dict, censor_by_quarter: pd.DataFrame) -> dict:
    rows = {r["candidate_test_quarter"]: r for r in head1["per_candidate_quarter"]}
    out = {}
    for name, (a, b) in FOLD_OPTIONS.items():
        ql = quarters(a, b)
        per = []
        for q in ql:
            r = rows[q]
            c = censor_by_quarter.loc[q]
            per.append({
                "test_quarter": q,
                "n_rows": r["n_test"],
                "n_dd": r["n_test_dedup"],
                "n_ciks": r["n_test_ciks"],
                "n_rows_10x": r["n_test_forms_10x"],
                "n_rows_train_overlap": r["n_test_overlap_rows"],
                "n_train_expanding": r["n_train_expanding"],
                "n_train_purged": r["n_train_purged"],
                "share_train_purged": r["share_train_purged"],
                "n_rows_null_target_dropped": int(c["n_rows_null_target"]),
                "censor_A_n_ciks_no_price_column": int(c["n_ciks_A"]),
                "censor_A_n_rows_no_price_column": int(c["n_rows_A"]),
                "censor_B_n_ciks_priced_no_usable_target": int(c["n_ciks_all_null"]),
                "censor_B_n_rows_priced_no_usable_target": int(c["n_rows_null_target"]),
                "would_be_cik_panel": int(r["n_test_ciks"] + c["n_ciks_A"]),
                "censor_A_share_of_would_be_panel": float(
                    c["n_ciks_A"] / (r["n_test_ciks"] + c["n_ciks_A"])),
            })
        ndd = np.array([p["n_dd"] for p in per], float)
        nrow = np.array([p["n_rows"] for p in per], float)
        ncik = np.array([p["n_ciks"] for p in per], float)
        shp = np.array([p["share_train_purged"] for p in per], float)
        cA = np.array([p["censor_A_n_ciks_no_price_column"] for p in per], float)
        out[name] = {
            "first_test_quarter": ql[0], "last_test_quarter": ql[-1],
            "k_folds": len(ql), "quarter_list": ql,
            "n_dd": {"mean": float(ndd.mean()), "harmonic_mean": float(len(ndd) / np.sum(1 / ndd)),
                     "min": int(ndd.min()), "max": int(ndd.max())},
            "n_rows": {"mean": float(nrow.mean()), "min": int(nrow.min()), "max": int(nrow.max()),
                       "total": int(nrow.sum())},
            "n_ciks": {"mean": float(ncik.mean()), "min": int(ncik.min()), "max": int(ncik.max())},
            "purge": {"total_row_fold_instances": int(sum(p["n_train_purged"] for p in per)),
                      "share_mean": float(shp.mean()), "share_min": float(shp.min()),
                      "share_max": float(shp.max())},
            "target_completeness": {
                "n_rows_joined_in_membership": int(nrow.sum() + sum(p["n_rows_null_target_dropped"] for p in per)),
                "n_rows_with_target_scored": int(nrow.sum()),
                "n_rows_null_target_dropped": int(sum(p["n_rows_null_target_dropped"] for p in per)),
                "share_complete": float(nrow.sum() / (nrow.sum() + sum(p["n_rows_null_target_dropped"] for p in per))),
            },
            "price_censoring_channel_A_no_price_column": {
                "n_ciks_first_fold": int(cA[0]), "n_ciks_last_fold": int(cA[-1]),
                "n_ciks_mean": float(cA.mean()), "n_ciks_max": int(cA.max()),
                "share_of_would_be_panel_first_fold": per[0]["censor_A_share_of_would_be_panel"],
                "share_of_would_be_panel_last_fold": per[-1]["censor_A_share_of_would_be_panel"],
                "n_rows_total": int(sum(p["censor_A_n_rows_no_price_column"] for p in per)),
            },
            "per_fold": per,
        }
    return out


# --------------------------------------------------------------------------
# §1b Price censoring, two channels, per candidate quarter (NEW)
# --------------------------------------------------------------------------

def price_censoring_census(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Channel A: core CIK has NO column in the sha-pinned price snapshot, so
    `target_e2.py` never wrote a row for it -- it is invisible to the joined
    frame and to `n_benchmark_unpriced`.  Channel B: the CIK is priced but the
    row's 63-session target is unresolvable (coverage gap, or the window has
    not closed under the snapshot).

    Channel A is measured on the text x numeric intersection under the
    membership spells, which is PRICE-INDEPENDENT by construction -- that is
    the only way to see rows the target table cannot contain.  Membership is
    evaluated on `filing_date` (the target table uses
    `info_date = max(filing_date, acceptance_ET)`; the two differ on 4 of
    29,271 scoped rows per STEP1A_target_e2.md §3, so the spell assignment is
    identical except at most there).
    """
    con = sqlite3.connect(ROOT / "data" / "filings_metadata_e2.db")
    mem = pd.read_sql("select cik, sector, stratum, member_from, member_to from universe_membership", con)
    con.close()
    mem["cik"] = mem["cik"].astype(str)
    core = mem[mem.stratum == "core"].copy()
    core["member_from"] = pd.to_datetime(core.member_from)
    core["member_to"] = pd.to_datetime(core.member_to).fillna(pd.Timestamp("2262-01-01"))

    priced = set(pq.read_table(ROOT / "data" / "prices_e2.parquet",
                               columns=["cik"]).to_pandas().cik.astype(str).unique())

    num = pd.read_parquet(ROOT / "data/f5/numeric_features_e2.parquet",
                          columns=["cik", "accession_number"])
    txt = pd.read_parquet(ROOT / "data/f5/text_features_e2.parquet",
                          columns=["cik", "accession_number", "filing_date", "form"])
    num["cik"] = num["cik"].astype(str)
    txt["cik"] = txt["cik"].astype(str)
    tn = txt.merge(num, on=["cik", "accession_number"], how="inner")
    tn["filing_date"] = pd.to_datetime(tn.filing_date)

    m = tn.merge(core[["cik", "member_from", "member_to", "sector"]], on="cik", how="inner")
    m = m[(m.filing_date >= m.member_from) & (m.filing_date < m.member_to)]
    m = m.drop_duplicates(["cik", "accession_number"]).copy()
    m["q"] = m.filing_date.dt.to_period("Q").astype(str)
    m["unpriced"] = ~m.cik.isin(priced)

    A = (m[m.unpriced].groupby("q")
         .agg(n_rows_A=("accession_number", "size"), n_ciks_A=("cik", "nunique")))

    # Channel B needs the joined frame BEFORE the null-target drop.
    tgt = pd.read_parquet(ROOT / "data/f5/target_e2.parquet")
    tgt["cik"] = tgt["cik"].astype(str)
    im = tgt[tgt.in_membership.astype(bool)].copy()
    im["filing_date"] = pd.to_datetime(im.filing_date)
    tkeys = set(zip(txt.cik, txt.accession_number))
    im["has_text"] = [(c, a) in tkeys for c, a in zip(im.cik, im.accession_number)]
    J = im[im.has_text].copy()
    J["q"] = J.filing_date.dt.to_period("Q").astype(str)
    J["null_t"] = J.target_excess_63.isna()
    B = J.groupby("q").apply(lambda g: pd.Series({
        "n_rows_joined": len(g),
        "n_rows_null_target": int(g.null_t.sum()),
        "n_ciks_joined": g.cik.nunique(),
        "n_ciks_all_null": int(g.groupby("cik").null_t.all().sum()),
    }), include_groups=False)

    tab = B.join(A, how="left").fillna(0).astype(int)

    unpriced_core = sorted(set(core.cik) - priced)
    sect = core.drop_duplicates("cik").set_index("cik")["sector"]
    summary = {
        "channel_A_definition": "core CIK absent from data/prices_e2.parquet; no target row exists at all",
        "channel_B_definition": "CIK priced, row joined, but target_excess_63 is null (coverage gap or window not closed under the snapshot)",
        "n_core_ciks": int(core.cik.nunique()),
        "n_core_ciks_no_price_column": len(unpriced_core),
        "n_core_ciks_no_price_column_by_sector": sect.loc[unpriced_core].value_counts().to_dict(),
        "n_text_x_numeric_in_membership_rows_on_unpriced_ciks": int(m.unpriced.sum()),
        "n_text_x_numeric_in_membership_rows": int(len(m)),
        "corroborates": {
            "STEP1A_target_e2.md §3": "3,016 filings across 27 core CIKs excluded solely for missing subject prices",
            "F2_INGESTION_REPORT.md §0(c)": "14.0/16.2/12.5% of the 2016/2017/2018 member-date cohorts; 95/1,496 = 6.35% pooled; energy 16.4%",
        },
    }
    return tab, summary


# --------------------------------------------------------------------------
# §2 MDE re-derivation
# --------------------------------------------------------------------------

def ar1_inflation(rho: float, k: int) -> float:
    """H2 §4's finite-k AR(1) VARIANCE inflation 1 + 2*sum_{l=1}^{k-1}(1-l/k)rho^l;
    returned as the SE (standard-deviation) multiplier, i.e. its square root.
    At k=26, rho=0.3 this reproduces H2's published 1.810 / SE x1.345."""
    if rho == 0:
        return 1.0
    return float(np.sqrt(1.0 + 2.0 * sum((1 - l / k) * rho ** l for l in range(1, k))))


def mde_row(spec_name: str, n_dd_per_fold: np.ndarray, rho: float, floor_on: bool) -> dict:
    """The H2 §4 algebra, step by step, at the MEASURED per-fold n_dd.

    step 1  sigma_samp(j) = sigma_boot * sqrt(n_ref / n_dd(j))
    step 2  sigma_tot(j)^2 = sigma_samp(j)^2 + floor^2      (floor branch only)
    step 3  SE = sqrt(sum_j sigma_tot(j)^2) / k  * inflation(rho, k)
    step 4  MDE = 2.8 * SE ; 95% null bound = 1.96 * SE
    """
    k = len(n_dd_per_fold)
    sb = H2["within_fold_bootstrap_sd_mean"][spec_name]
    fl = H2["implied_regime_floor"][spec_name] if floor_on else 0.0
    sig_samp = sb * np.sqrt(H2["n_dd_reference"] / n_dd_per_fold)
    sig_tot2 = sig_samp ** 2 + fl ** 2
    infl = ar1_inflation(rho, k)
    se_het = float(np.sqrt(sig_tot2.sum()) / k * infl)
    # homogeneous comparison at the arithmetic-mean n_dd (what a 1/sqrt(k)
    # rescaling of the published table would give)
    n_bar = float(n_dd_per_fold.mean())
    s_hom = float(np.sqrt(sb ** 2 * H2["n_dd_reference"] / n_bar + fl ** 2))
    se_hom = s_hom / np.sqrt(k) * infl
    mde = H2["mde_multiplier"] * se_het
    return {
        "spec": spec_name, "branch": "implied_floor" if floor_on else "floor_free",
        "rho_f": rho, "k": k,
        "n_dd_mean": n_bar,
        "n_dd_harmonic_mean": float(k / np.sum(1 / n_dd_per_fold)),
        "sigma_boot_sd_e1": sb, "n_dd_reference": H2["n_dd_reference"],
        "implied_floor": fl,
        "sigma_fold_mean": float(np.sqrt(sig_tot2.mean())),
        "ar1_variance_inflation": float(infl ** 2), "ar1_se_multiplier": float(infl),
        "SE": se_het,
        "SE_homogeneous_at_mean_n_dd": float(se_hom),
        "MDE": float(mde),
        "MDE_true_construct_lambda_0.8": float(mde / H2["lambda_true_construct"]),
        "MDE_per_family_low_0.4x": float(mde * H2["per_family_mde_scaling"][0]),
        "MDE_per_family_high_2.4x": float(mde * H2["per_family_mde_scaling"][1]),
        "null_bound_95": float(1.96 * se_het),
    }


def t_multiplier(k: int) -> float:
    df = k - 1
    return float(stats.t.ppf(0.975, df) + stats.t.ppf(0.80, df))


def mde_table(options: dict) -> dict:
    out = {"algebra": {
        "step_1": "sigma_samp(fold j) = sigma_boot * sqrt(n_dd_reference / n_dd(j))",
        "step_2": "sigma_tot(j)^2 = sigma_samp(j)^2 + implied_floor^2  (floor branch only)",
        "step_3": "SE(mean delta) = sqrt(sum_j sigma_tot(j)^2)/k * sqrt(1 + 2*sum_{l=1}^{k-1}(1-l/k)*rho_f^l)",
        "step_4": "MDE = 2.8 * SE ; 95% null bound = 1.96 * SE ; true-construct = MDE / lambda",
        "inputs": H2,
        "reproduction_check": "at k=26, n_dd=158 this reproduces H2 §4's published SEs to 4 dp: "
                              "0.0103 / 0.0138 (raw_levels, rho 0/0.3), 0.0113 / 0.0152 (pit floor-free), "
                              "0.0225 / 0.0303 (pit implied-floor). H2's printed MDEs multiply the ROUNDED "
                              "SE by 2.8 (0.0152*2.8 = 0.043); the unrounded chain gives 0.0424. The 1-unit "
                              "third-decimal gaps below are that rounding path, not a disagreement.",
    }}
    # the published-planning row, re-derived here so the delta is visible
    planning = np.full(H2["planning_k"], float(H2["planning_n_dd"]))
    out["published_planning_k26_ndd158"] = [
        mde_row(s, planning, r, f)
        for s in ("raw_levels", "pit_trailing_rank")
        for f in (False, True) if not (s == "raw_levels" and f)
        for r in (0.0, H2["rho_f_assumed"])
    ]
    out["at_measured_n_dd"] = {}
    for name, o in options.items():
        ndd = np.array([p["n_dd"] for p in o["per_fold"]], float)
        out["at_measured_n_dd"][name] = {
            "k": o["k_folds"], "quarters": f"{o['first_test_quarter']}..{o['last_test_quarter']}",
            "n_dd_mean": float(ndd.mean()), "n_dd_min": int(ndd.min()), "n_dd_max": int(ndd.max()),
            "t_correction_multiplier_not_applied": t_multiplier(o["k_folds"]),
            "rows": [mde_row(s, ndd, r, f)
                     for s in ("pit_trailing_rank", "raw_levels")
                     for f in (False, True) if not (s == "raw_levels" and f)
                     for r in (0.0, H2["rho_f_assumed"])],
        }
    return out


# --------------------------------------------------------------------------
# §3 Ladder feasibility (decision 15)
# --------------------------------------------------------------------------

def ladder_feasibility(mde: dict) -> dict:
    out = {
        "rule": "Delta = the SMALLEST value in the pre-registered ladder {0.03, 0.04, 0.05} "
                "with SE <= Delta/2.487; if none satisfies it the result is UNPOWERED "
                "(no equivalence claim) -- F5_PLAN §3 decision 15.",
        "se_caps": {str(d): d / POWER_DIVISOR for d in LADDER},
        "kc3_note": "Any selected Delta > 0.03 prints beside its implied MDE 2.8*SE and is flagged "
                    "as the KC3 branch. Delta = 0.05 admits an honest MDE up to "
                    f"{H2['mde_multiplier'] * 0.05 / POWER_DIVISOR:.4f}.",
        "these_are_projections": "SE here is the EX-ANTE projection from E1's within-fold bootstrap SD "
                                 "and E1's implied floor. The ladder executes at Step 4 on the E2-MEASURED "
                                 "block-bootstrap SE. This census cannot and does not select Delta.",
        "by_option": {},
    }
    for name, blk in mde["at_measured_n_dd"].items():
        rows = []
        for r in blk["rows"]:
            sel, satisfied = None, []
            for d in LADDER:
                if r["SE"] <= d / POWER_DIVISOR:
                    satisfied.append(d)
                    if sel is None:
                        sel = d
            rows.append({
                "spec": r["spec"], "branch": r["branch"], "rho_f": r["rho_f"], "SE": r["SE"],
                "rungs_satisfied": satisfied,
                "delta_projected": sel,
                "verdict": "UNPOWERED (no equivalence claim)" if sel is None else f"Delta = {sel:.2f}",
                "implied_mde_at_selected_delta": None if sel is None else H2["mde_multiplier"] * r["SE"],
                "kc3_branch": bool(sel is not None and sel > 0.03),
                "margin_of_miss": {str(d): r["SE"] - d / POWER_DIVISOR for d in LADDER},
            })
        out["by_option"][name] = {"k": blk["k"], "rows": rows}
    return out


# --------------------------------------------------------------------------
# §4 Three-way joined-frame decomposition
# --------------------------------------------------------------------------

def frame_decomposition(frame: pd.DataFrame, diag: dict) -> dict:
    tgt = pd.read_parquet(ROOT / "data/f5/target_e2.parquet")
    txt = pd.read_parquet(ROOT / "data/f5/text_features_e2.parquet",
                          columns=["cik", "accession_number"])
    num = pd.read_parquet(ROOT / "data/f5/numeric_features_e2.parquet",
                          columns=["cik", "accession_number"])
    for d in (tgt, txt, num):
        d["cik"] = d["cik"].astype(str)
    im = tgt[tgt.in_membership.astype(bool)].copy()
    tk, nk = set(zip(txt.cik, txt.accession_number)), set(zip(num.cik, num.accession_number))
    im["has_text"] = [(c, a) in tk for c, a in zip(im.cik, im.accession_number)]
    im["has_num"] = [(c, a) in nk for c, a in zip(im.cik, im.accession_number)]
    lost = im[~(im.has_text & im.has_num)]

    # the 10 CIKs whose periodic filings were never extracted
    per = lost[lost.form.isin(["10-K", "10-Q"])]
    con = sqlite3.connect(ROOT / "data" / "filings_metadata_e2.db")
    co = pd.read_sql("select cik, company_name, sector, stratum from companies", con)
    con.close()
    co["cik"] = co["cik"].astype(str)
    g = (per.groupby("cik").agg(n_missing=("accession_number", "size"),
                                n_10k=("form", lambda s: int((s == "10-K").sum())),
                                n_10q=("form", lambda s: int((s == "10-Q").sum())),
                                first=("filing_date", "min"), last=("filing_date", "max"))
         .reset_index())
    tot = im[im.form.isin(["10-K", "10-Q"])].groupby("cik").size().rename("n_in_membership_periodic")
    g = g.merge(tot, left_on="cik", right_index=True, how="left").merge(co, on="cik", how="left")
    g["share_of_that_ciks_periodic_filings_missing"] = g.n_missing / g.n_in_membership_periodic
    g = g.sort_values("n_missing", ascending=False)

    qtab = (frame.assign(q=frame.filing_date.dt.to_period("Q").astype(str))
            .groupby("q").agg(n_rows=("accession_number", "size"), n_ciks=("cik", "nunique")))
    return {
        "chain": {
            "n_target_rows_all": int(diag["n_target_rows"]),
            "n_target_in_membership": int(diag["n_target_in_membership"]),
            "n_joined_three_way": int(diag["n_joined"]),
            "n_after_families_left_join": int(diag["n_after_families_join"]),
            "n_emb_missing": diag["n_emb_missing"],
            "n_target_null_dropped": int(diag["n_target_null"]),
            "n_modeling_rows": int(diag["n_modeling_rows"]),
            "n_ciks": int(diag["n_ciks"]),
            "source": "backtest_e2.load_analysis_frame / data/f5/census_head1.json .frame",
        },
        "rows_without_text": {
            "n_total": int((~im.has_text).sum()),
            "by_form": im[~im.has_text].groupby("form").size().astype(int).to_dict(),
            "n_without_numeric": int((~im.has_num).sum()),
            "note": "numeric_features_e2 covers ALL 16,859 in-membership target rows; every join loss "
                    "is a TEXT loss. 8-K losses are non-earnings-bearing 8-Ks (F3/F4 extracted text "
                    "only for earnings-bearing 8-Ks); the 145 periodic losses are the never-extracted set.",
        },
        "never_extracted_periodic": {
            "n_filings": int(len(per)),
            "n_ciks": int(per.cik.nunique()),
            "by_form": per.groupby("form").size().astype(int).to_dict(),
            "ciks": json.loads(g.to_json(orient="records", date_format="iso")),
            "sector_concentration": g.sector.value_counts().to_dict(),
        },
        "per_quarter_joined": {
            "n_quarters": int(len(qtab)),
            "n_rows_min": int(qtab.n_rows.min()), "n_rows_max": int(qtab.n_rows.max()),
            "n_ciks_min": int(qtab.n_ciks.min()), "n_ciks_max": int(qtab.n_ciks.max()),
            "table": json.loads(qtab.reset_index().to_json(orient="records")),
        },
        "families_vs_labels_gap": {
            "n_families_rows": int(diag["n_families_rows"]),
            "n_joined": int(diag["n_joined"]),
            "delta": int(diag["n_families_rows"] - diag["n_joined"]),
            "meaning": "text_families_e2 is scoped to in-membership filings with >= 1 CORPUS section; "
                       "the label-derived text_features table is scoped to filings with >= 1 attributed "
                       "LABELED chunk. The gap is filings with corpus text but no attributed labeled chunk.",
        },
    }


# --------------------------------------------------------------------------
# §5 Label-purge / instrument census
# --------------------------------------------------------------------------

def withdrawn_census(frame: pd.DataFrame) -> dict:
    cols = ["home_cik", "home_accession_number", "home_form", "home_filing_date",
            "section_type", "guidance_direction"]
    lab = pd.read_parquet(ROOT / "data/f4/labels_e2_v1.parquet", columns=cols)
    all_w = lab[lab.guidance_direction == "WITHDRAWN"]
    w = all_w[all_w.section_type == "EX99_PRESS_RELEASE"].copy()
    w["fd"] = pd.to_datetime(w.home_filing_date)
    w["home_cik"] = w["home_cik"].astype(str)
    keys = set(zip(w.home_cik, w.home_accession_number))
    hit = np.array([(c, a) in keys for c, a in zip(frame.cik.astype(str), frame.accession_number)])
    return {
        "n_withdrawn_chunks_corpus": int(len(all_w)),
        "corpus_by_section": all_w.groupby("section_type").size().astype(int).to_dict(),
        "n_on_the_feature_frame": int(len(w)),
        "frame_derivation": "71 corpus chunks - 1 in 8K_BODY (decision 9 excludes the register) "
                            "- 4 in MDA (decision 10 masks guidance on MDA/RISK_FACTORS) = 66, "
                            "reproducing F5_PLAN §3 decision 11's n = 66 exactly.",
        "by_year": w.groupby(w.fd.dt.year).size().astype(int).to_dict(),
        "by_quarter": w.groupby(w.fd.dt.to_period("Q").astype(str)).size().astype(int).to_dict(),
        "n_distinct_filings": int(w.home_accession_number.nunique()),
        "n_distinct_ciks": int(w.home_cik.nunique()),
        "n_modeling_rows_touched": int(hit.sum()),
        "modeling_rows_touched_by_quarter":
            frame[hit].filing_date.dt.to_period("Q").astype(str).value_counts().sort_index().astype(int).to_dict(),
    }


def instrument_census(frame: pd.DataFrame) -> dict:
    ov = frame["train_overlap_share"].astype(float)
    gld = frame[frame.is_gld.astype(bool)]
    return {
        "masks_and_enums_quoted_from_STEP1A": {
            "sentiment_masked_on_RISK_FACTORS": 4177,
            "sentiment_masked_breakdown": {"NEUTRAL": 3452, "NEGATIVE": 688, "POSITIVE": 37},
            "guidance_masked_on_MDA_plus_RISK_FACTORS": 2826,
            "guidance_masked_breakdown": {"MDA": 2803, "RISK_FACTORS": 23},
            "guidance_masked_active_values": 230,
            "imputed_NONE_corpus": 48790,
            "imputed_NONE_share_of_applicable_corpus": 0.5118,
            "imputed_NONE_frame": 48293,
            "imputed_NONE_share_of_applicable_frame": 0.5108,
            "guidance_enum_nulls_left_null": 17,
            "schema_violations_disclosure_only": {"total": 23, "guidance_enum": 17,
                                                  "red_flag_category": 4, "red_flag_modality": 2},
            "chunks_8K_BODY_excluded": 790,
            "corpus_rows": 317081, "frame_rows": 316291,
            "source": "data/f5/status/STEP1A_features_e2.md §'Every assertion' (all PASS against "
                      "features_e2.py's own assertions and an independent slow re-derivation)",
        },
        "train_overlap": {
            "chunk_level_n": 14342, "chunk_level_share": 0.04534,
            "chunk_level_channels": {"home_accession": 10442, "any_source_accession": 14341,
                                     "normalized_text": 487, "union": 14342},
            "chunk_level_base": 316291,
            "filing_level_n_modeling_rows": int((ov > 0).sum()),
            "filing_level_share": float((ov > 0).mean()),
            "filing_level_base": int(len(frame)),
            "different_questions": "4.53% is the CHUNK-level accession-channel share; 80.2% is the share "
                                  "of MODELING ROWS containing at least one such chunk. Never quote one "
                                  "as the other. The accession channel is a LOWER bound on labeler "
                                  "exposure (CIK-level exposure is 15.85%).",
            "arm_as_built": "an EVALUATION-side restriction: the fit is unchanged and the scored set "
                            f"shrinks to {int((ov <= 0).sum())} rows (F5_PLAN §3 decision 3's overlap-arm note).",
            "source": "data/f5/status/STEP1A_features_e2.md + STEP1B_backtest_e2.md §2 / §4 item 2",
        },
        "selfid": {"chunk_level_n": 146958, "chunk_level_share": 0.4646,
                   "frame_mean_selfid_share": float(frame["selfid_share"].astype(float).mean()),
                   "source": "data/f5/status/STEP1A_features_e2.md"},
        "cross_cik_attribution": {
            "n_chunks_under_more_than_one_cik": 5706, "share": 0.0180,
            "n_cross_cik_occurrence_rows": 99636, "n_occurrence_rows": 854933, "share_rows": 0.1165,
            "frame_mean_cross_cik_share": float(frame["cross_cik_share"].astype(float).mean()),
            "source": "F5_PLAN §3 decision 20 (surfaced by Step 1a)",
        },
        "gld": {"n_modeling_rows": int(len(gld)), "n_ciks": int(gld.cik.nunique()),
                "by_form": gld.form.value_counts().astype(int).to_dict(),
                "by_quarter": gld.filing_date.dt.to_period("Q").astype(str).value_counts().sort_index().astype(int).to_dict(),
                "scoped_vs_in_membership": "65 scoped / 14 in-membership target rows (STEP1A_target_e2.md §3); "
                                           "8 survive the three-way join."},
        "label_purge_at_E2": {
            "rule": "drop training rows whose 63-session forward window closes on or after the test "
                    "quarter's first session (F5_PLAN §3 decision 5); no additional embargo buffer.",
            "e1_comparator": "H2 §3.3: 313 of 2,425 E1 training labels (12.9%) resolve inside their test quarter.",
            "source": "data/f5/census_head1.json .per_candidate_quarter[*].n_train_purged / share_train_purged",
        },
    }


# --------------------------------------------------------------------------
# §6 ICCs against company identity
# --------------------------------------------------------------------------

def icc_one_way(y: np.ndarray, g: np.ndarray) -> dict | None:
    """One-way random-effects ICC(1) with the exact F-based 95% CI.
    Feature vs COMPANY IDENTITY only -- no outcome enters."""
    m = np.isfinite(y)
    y, g = y[m], np.asarray(g)[m]
    if len(y) == 0:
        return None
    s = pd.Series(y).groupby(pd.Series(g)).agg(["count", "mean"])
    k, N = len(s), int(s["count"].sum())
    if k < 2 or N - k < 1:
        return None
    gm = y.mean()
    ssb = float((s["count"] * (s["mean"] - gm) ** 2).sum())
    ssw = float(((y - gm) ** 2).sum()) - ssb
    msb, msw = ssb / (k - 1), ssw / (N - k)
    n0 = (N - float((s["count"] ** 2).sum()) / N) / (k - 1)
    if msw == 0:
        return None
    f = msb / msw
    fl, fu = stats.f.ppf(0.975, k - 1, N - k), stats.f.ppf(0.025, k - 1, N - k)
    return {"icc": (msb - msw) / (msb + (n0 - 1) * msw),
            "ci95": [(f / fl - 1) / (f / fl + n0 - 1), (f / fu - 1) / (f / fu + n0 - 1)],
            "n": N, "n_companies": k, "n0": n0, "F": f}


def icc_census(frame: pd.DataFrame) -> dict:
    ranked = spec.pit_trailing_rank_frame(
        frame, NUMERIC_RAW_FEATURES, window_days=180, min_comparators=2,
        include_same_day=True, ticker_col="cik", date_col="filing_date")
    keep = BE.dedup_keep_mask_cik(frame, 5).values.astype(bool)
    rows = []
    for c in NUMERIC_RAW_FEATURES:
        raw = icc_one_way(frame[c].astype(float).values, frame["cik"].values)
        pit = icc_one_way(ranked[c].astype(float).values, ranked["cik"].values)
        raw_dd = icc_one_way(frame.loc[keep, c].astype(float).values, frame.loc[keep, "cik"].values)
        rows.append({"feature": c,
                     "icc_raw_levels": raw, "icc_pit_trailing_rank": pit,
                     "icc_raw_levels_dedup_base": raw_dd})
    return {
        "estimator": "one-way random-effects ICC(1) = (MSB - MSW)/(MSB + (n0-1)MSW), n0 the "
                     "unequal-group-size correction; exact F-based 95% CI.",
        "grouping": "cik (company identity). NO outcome column enters this computation.",
        "base_raw": f"the {len(frame)}-row modeling frame",
        "base_dedup": f"the {int(keep.sum())}-row company-quarter dedup frame (gap_days = 5), "
                      "reported beside the raw base as standing practice",
        "e1_comparator": "H2 §2: E1 log_total_assets ICC 0.987 -- the a-priori rationale for making "
                         "PIT trailing ranks the PRIMARY spec.",
        "rows": rows,
    }


# --------------------------------------------------------------------------
# §7/§8 head 2, head 3, text families -- restatements of existing measurements
# --------------------------------------------------------------------------

def heads_restatement(heads: dict) -> dict:
    h2, h3 = heads["head2"], heads["head3"]
    eq = h2["events_by_quarter_usable"]
    complete = {k: v for k, v in eq.items() if k != "2026Q3"}
    vals = np.array(list(complete.values()), float)
    kinds = h3["exit_rows_still_filing_a_year_later"]
    tab = []
    for kind, d in kinds.items():
        n, later = d["rows_on_panel_ciks"], d["rows_with_a_later_in_membership_filing"]
        tab.append({"event_kind": kind, "rows_on_panel_ciks": n,
                    "rows_with_a_later_in_membership_filing": later,
                    "share_not_an_exit": float(later / n) if n else None,
                    "rows_that_do_end_membership": n - later})
    tot_n = sum(t["rows_on_panel_ciks"] for t in tab)
    tot_l = sum(t["rows_with_a_later_in_membership_filing"] for t in tab)
    return {
        "head2": {
            "events_core": h2["events_core"], "events_all_strata": h2["events_all_strata"],
            "events_usable_for_head2": h2["events_usable_for_head2"],
            "clusters_including_partial": h2["clusters_events_quarters_usable"]
                if "clusters_events_quarters_usable" in h2 else h2["clusters_event_quarters_usable"],
            "partial_quarter": {"quarter": "2026Q3", "usable_events": eq["2026Q3"],
                                "complete_quarter_run_rate_min_max": [int(vals.min()), int(vals.max())],
                                "complete_quarter_mean": float(vals.mean())},
            "default_end_at_last_complete_quarter": {
                "last_quarter": "2026Q2", "n_clusters": int(len(complete)),
                "n_usable_events": int(vals.sum())},
            "exclusions": {k: h2[k] for k in h2 if k.startswith("events_dropped") or k.startswith("events_excluded")},
            "ciks_dropped_no_price_column": h2["ciks_dropped_no_price_column"],
            "events_without_text_features": h2["events_without_text_features"],
            "few_clusters_limitation": "SE by wild-cluster bootstrap over 40 event quarters; with 40 "
                                       "clusters the bootstrap is the honest statistic and the pooled "
                                       "p-value would be anti-conservative (earnings cluster in seasons).",
            "predictor_disclosures": {
                "g2_sentiment_verdict": "INDETERMINATE",
                "g2_sentiment_agreement_owner_ratified": {"k": 293, "n": 337, "point": 0.8694,
                                                          "wilson_ci95": [0.8293, 0.9013], "bar": 0.85},
                "stored_negative_precision": {"k": 25, "n": 49, "point": 0.5102},
                "teacher_negative_recall": 0.487,
                "epistemics": "HANDOFF §3: agreement over model-adjudicated fields is MODEL CONSENSUS "
                              "between a student and an adjudicating model -- not human validation of "
                              "ground truth.",
                "dv_caveat": "prices are split-adjusted only, so the DV is not dividend-immune; an "
                             "ex-dividend session inside [+1, +5] inflates it.",
                "source": "data/f4/g2/G2_FINAL_REPORT.md §0 + the owner-ratified estimator table",
            },
            "source": "data/f5/census_heads.json .head2",
        },
        "head3": {
            "exit_rows_total": h3["exit_rows_total"], "exit_rows_core_stratum": h3["exit_rows_core_stratum"],
            "exit_ciks_total": h3["exit_ciks_total"], "exit_ciks_core_stratum": h3["exit_ciks_core_stratum"],
            "exit_rows_by_kind_and_form": h3["exit_rows_by_kind_and_form"],
            "exit_kind_table": tab,
            "pooled": {"rows_on_panel_ciks": tot_n, "still_filing_a_year_later": tot_l,
                       "share_not_an_exit": float(tot_l / tot_n),
                       "rows_that_do_end_membership": tot_n - tot_l},
            "panel": {
                "latest_in_quarter": {k: h3["panel_latest_in_quarter"][k]
                                      for k in ("panel_rows", "panel_ciks", "panel_rows_without_text")},
                "latest_in_quarter_with_text": {k: h3["panel_latest_in_quarter_with_text"][k]
                                                for k in ("panel_rows", "panel_ciks", "panel_rows_without_text")},
                "share_without_text_under_latest_in_quarter":
                    float(h3["panel_latest_in_quarter"]["panel_rows_without_text"]
                          / h3["panel_latest_in_quarter"]["panel_rows"]),
            },
            "label_cut": {"candidate": h3["candidate_label_cut"],
                          "source": h3["candidate_label_cut_source"],
                          "n_quarters_censored": int(sum(h3["quarter_censorship_under_candidate_cut"].values())),
                          "last_uncensored_quarter": h3["last_uncensored_quarter_under_candidate_cut"]},
            "ma_vs_distress": h3["ma_vs_distress_split"],
            "source": "data/f5/census_heads.json .head3",
        },
    }


def families_restatement(man: dict) -> dict:
    cov, fa, fb, inv = man["coverage"], man["family_a_diagnostics"], man["family_b_diagnostics"], man["output_invariants_measured"]
    deg = fa["novelty_degenerate_census"]
    return {
        "scope": man["arguments"]["scope"],
        "coverage": {
            "n_rows_written": cov["n_rows_written"], "n_distinct_ciks": cov["n_distinct_ciks"],
            "n_in_membership_target_rows": cov["n_in_membership_target_rows"],
            "n_in_membership_filings_without_text": cov["n_in_membership_filings_without_text"],
            "novelty_risk_factors_present": [cov["n_novelty_risk_factors_yoy_present"],
                                             cov["share_novelty_risk_factors_yoy_present"]],
            "novelty_mda_present": [cov["n_novelty_mda_yoy_present"], cov["share_novelty_mda_yoy_present"]],
        },
        "decision_23a_prior_gap_days": fa["prior_gap_days_census"],
        "decision_23b_stub_dominance": {
            "RISK_FACTORS": {**deg["RISK_FACTORS"],
                             "share_with_a_side_under_50_shingles":
                                 deg["RISK_FACTORS"]["n_pairs_with_a_side_under_50_shingles"] / deg["RISK_FACTORS"]["n"]},
            "MDA": {**deg["MDA"],
                    "share_with_a_side_under_50_shingles":
                        deg["MDA"]["n_pairs_with_a_side_under_50_shingles"] / deg["MDA"]["n"]},
        },
        "decision_23a_prior_rule": {
            "key": man["arguments"]["family_a_novelty"]["prior_rule_key"],
            "value": man["arguments"]["family_a_novelty"]["prior_rule_value"],
            "rule": man["arguments"]["family_a_novelty"]["prior_rule"],
            "n_with_prior": fa["n_with_prior"], "n_without_prior": fa["n_without_prior"],
        },
        "decision_23b_min_shingles": {
            "key": man["arguments"]["family_a_novelty"]["min_shingles_key"],
            "value": man["arguments"]["family_a_novelty"]["min_shingles"],
            "n_pairs_suppressed": fa["n_suppressed_by_min_shingles"],
            "by_section": {sec: {k: v for k, v in d.items()
                                 if k.startswith(("n_suppressed", "n_written", "n_exactly"))}
                           for sec, d in deg.items()},
        },
        "decision_23_sequential_exploratory": {
            "key": man["arguments"]["family_a_prime_sequential_novelty_EXPLORATORY"]["key"],
            "columns": man["arguments"]["family_a_prime_sequential_novelty_EXPLORATORY"]["columns"],
            "status": "EXPLORATORY -- never in columns.family_novelty, never in the headline",
            "n_with_prior": fa["seq_n_with_prior"],
            "n_pairs_suppressed": fa["seq_n_suppressed_by_min_shingles"],
            "prior_gap_days": fa["prior_gap_days_census_seq"],
            "present": {c: [cov[f"n_{c}_present"], cov[f"share_{c}_present"]]
                        for c in man["arguments"]["family_a_prime_sequential_novelty_EXPLORATORY"]["columns"]},
        },
        "decision_23c_prior_pool": man["arguments"]["family_a_novelty"]["prior_candidate_pool"],
        "decision_23d_8k_body_embedded": fb["sections_embedded_by_type_this_run"]["8K_BODY"],
        "decision_23d_rows_lost_to_the_exclusion":
            fb["n_scoped_filings_with_no_embeddable_section"],
        "decision_23e_filing_pooling": man["arguments"]["family_b_embeddings"]["filing_pooling"],
        "decision_23f_window_cap": {
            "cap": man["arguments"]["family_b_embeddings"]["max_windows_per_section"],
            # renamed by the 2026-09-10 red-team pass; the rebuilt manifest
            # (2026-09-11, decision 23) carries the THIS-RUN name only.
            "n_sections_hitting_cap": fb["n_sections_hitting_the_window_cap_this_run"],
            "n_sections_total": fb["n_sections_embedded_total"],
            "share": fb["n_sections_hitting_the_window_cap_this_run"] / fb["n_sections_embedded_total"],
            "windows_kept_vs_uncapped": [fb["n_windows_this_run"], fb["n_windows_uncapped_this_run"]],
            "share_of_windows_dropped_by_cap":
                1 - fb["n_windows_this_run"] / fb["n_windows_uncapped_this_run"],
        },
        "decision_23g_embedding_norms": {
            "emb_l2_norm": inv["emb_l2_norm"],
            "why_not_1": "filing pooling is an UNWEIGHTED MEAN over section vectors and the pooled vector "
                         "is NOT renormalized (renormalize_pooled = false), so ||emb|| < 1 measures "
                         "within-filing section dispersion; a PCA on these is a PCA on unnormalized means.",
            "emb_width": inv["emb_widths"],
            "n_emb_missing_on_the_frame": "measured in .chain.n_emb_missing (was a hard-coded 0 until 2026-09-11; non-zero after the decision-23d rebuild: filings whose only embeddable section was an 8K_BODY carry no vector)",
        },
        "decision_23h_model": man["model"],
        "novelty_distributions": {k: inv[k] for k in inv if k.startswith("novelty_")},
        "runtimes_seconds": man["runtimes_seconds"],
        "source": "data/f5/text_families_e2_manifest.json",
    }


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main() -> int:
    t_all = time.time()
    rt = {}

    t = time.time()
    head1 = json.loads((ROOT / "data/f5/census_head1.json").read_text())
    heads = json.loads((ROOT / "data/f5/census_heads.json").read_text())
    fam_man = json.loads((ROOT / "data/f5/text_families_e2_manifest.json").read_text())
    rt["read_existing_census_artifacts"] = time.time() - t

    t = time.time()
    frame, diag = BE.load_analysis_frame()      # sha-asserts all four inputs
    rt["load_analysis_frame"] = time.time() - t

    t = time.time()
    censor_tab, censor_summary = price_censoring_census(frame)
    rt["price_censoring_census"] = time.time() - t

    t = time.time()
    opts = fold_options(head1, censor_tab)
    rt["fold_options"] = time.time() - t

    t = time.time()
    mde = mde_table(opts)
    ladder = ladder_feasibility(mde)
    rt["mde_and_ladder"] = time.time() - t

    t = time.time()
    decomp = frame_decomposition(frame, diag)
    rt["frame_decomposition"] = time.time() - t

    t = time.time()
    instr = instrument_census(frame)
    instr["withdrawn"] = withdrawn_census(frame)
    rt["instrument_census"] = time.time() - t

    t = time.time()
    iccs = icc_census(frame)
    rt["icc_census"] = time.time() - t

    t = time.time()
    hd = heads_restatement(heads)
    fams = families_restatement(fam_man)
    rt["heads_and_families_restatement"] = time.time() - t

    sources = {}
    for p in ["data/f5/census_head1.json", "data/f5/census_heads.json",
              "data/f5/text_families_e2_manifest.json", "data/f5/target_e2.parquet",
              "data/f5/text_features_e2.parquet", "data/f5/numeric_features_e2.parquet",
              "data/f5/text_families_e2.parquet", "data/hardening/controls_results.json",
              "data/filings_metadata_e2.db", "data/prices_e2.parquet",
              "data/f4/labels_e2_v1.parquet", "data/f5/census_e2.py"]:
        fp = ROOT / p
        if fp.exists():
            sources[p] = sha256_file(fp)

    census = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "module": "data/f5/census_e2.py",
        "step": "F5_PLAN.md §2 Step 2 -- pre-run census",
        "network_calls": 0,
        "api_spend_usd": 0.0,
        "freeze_statement": (
            "F5_PLAN §1: no information coefficient, correlation, model fit or feature-versus-outcome "
            "association was computed on E2 data. `target_excess_63` was read only to COUNT completeness "
            "and censoring. The §6 ICCs are feature-versus-COMPANY-IDENTITY statistics, which the brief "
            "and the freeze both allow. data/f5/G3_RATIFIED.json does NOT exist and was not created; "
            "data/f5/G3_PREREGISTRATION.md exists UNRATIFIED (its sha is pinned only on the owner's word)."
        ),
        "scope_sentence": (
            "No text-vs-numeric IC improvement of economically relevant size is detectable in this "
            "universe through this labeling schema, these features, this labeler, and this feature "
            "specification."
        ),
        "e1_e2_incomparable": (
            "E1 and E2 backtest numbers are numerically incomparable: E2's benchmark is the "
            "membership-dated equal-weighted average over that date's members excluding self."
        ),
        "standing_power_caveats": [
            "Every MDE below is a LOWER BOUND: folds are not independent (the AR(1) term is an "
            "assumption, not a measurement; rho_f is measured for the first time at Step 4).",
            "The noise anchor (H2 §3.2 within-fold bootstrap SD) was estimated on E1's 2025-2026 "
            "mega-cap folds and may not transfer to 2016-era folds.",
            "Per-family MDEs scale ~0.4x-2.4x around the full-model numbers.",
            "The true-construct bracket divides by labeler reliability lambda ~ 0.8 "
            "(lambda ~ 0.6-0.7 where sections are short, which is worse).",
            "EXPANSION_PLAN §2a's published 0.019-0.037 bracket was SUPERSEDED on 2026-08-25 by the "
            "H2 honest restatement; quote the amendment, never the old bracket.",
        ],
        "input_sha256": sources,
        "section_1_fold_options_decision_4": opts,
        "section_1b_price_censoring": {"summary": censor_summary,
                                       "per_candidate_quarter": json.loads(
                                           censor_tab.reset_index().to_json(orient="records"))},
        "section_2_mde_decision_15_KC3": mde,
        "section_3_ladder_feasibility_decision_15": ladder,
        "section_4_frame_decomposition_decisions_3_4": decomp,
        "section_5_label_purge_and_instrument_census": instr,
        "section_6_iccs_vs_company_identity_decision_3": iccs,
        "section_7_heads_decisions_12_13": hd,
        "section_8_text_families_decision_23": fams,
        "section_9_what_the_census_cannot_say": (
            "This census contains no information coefficient, no IC delta, no per-fold delta, no "
            "fold-delta autocorrelation, no block-bootstrap SE, and therefore no selected equivalence "
            "margin. Every SE and MDE in §2 and §3 is an EX-ANTE PROJECTION built from E1's within-fold "
            "bootstrap SD and E1's implied regime floor, rescaled to E2's measured per-fold n_dd; the "
            "real SE is a block bootstrap over E2's own fold deltas and is measured for the first time "
            "at Step 4, inside the runner, before any delta is printed. The ladder rows in §3 say what "
            "the design could plausibly deliver, not what Delta will be -- selecting Delta from these "
            "projections, or from any realized SE, would be the post-hoc design choice decision 15 "
            "exists to forbid. The census also cannot say whether the rank-spec variance floor is real "
            "(unresolved at 6 folds, chi-square p = 0.16/0.13 in both directions), cannot say whether "
            "fold non-independence exceeds rho_f = 0.3, and says nothing about whether any text feature "
            "carries information about returns."
        ),
        "runtimes_seconds": rt,
    }
    census["runtimes_seconds"]["total"] = time.time() - t_all
    OUT_PATH.write_text(json.dumps(census, indent=2, default=str) + "\n")
    print(f"wrote {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes) in "
          f"{census['runtimes_seconds']['total']:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
