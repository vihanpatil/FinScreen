#!/usr/bin/env python3
"""Decision 11 -- the WITHDRAWN-guidance ("2020Q2") sensitivity row for head 1.

The ratified rule (`G3_PREREGISTRATION.md` §10, row "WITHDRAWN guidance"):
WITHDRAWN stays evaluable at -1 in `guidance_signed_mean`, n disclosed, and
**one sensitivity row excluding it, labelled as the 2020Q2 sensitivity it is**.
The G3 run of 2026-11-05 did not execute that row (review finding M1). This
script executes it, late, under the same guard, and labels it so:
EXECUTED AFTER THE PRIMARY WAS SEEN; it can never be selected as the primary.

What it does, and nothing else:
  * `backtest_e2.load_g3_params` -- the freeze guard; exit 2 on refusal.
  * `backtest_e2.load_analysis_frame` + `exclude_gld_rows` -- the run-time frame.
  * REPRODUCTION CHECK: the primary's per-fold dedup delta is recomputed with
    the same composition and must equal `results_head1.json`
    `per_fold_primary_delta_dedup` EXACTLY, or the script refuses to write.
  * the arm: drop the frame rows whose `guidance_signed_mean` carries a
    WITHDRAWN label, then the primary's own folds/purge, dedup mask, PIT rank,
    per-fold PCA and seed-0 fit (all `backtest_e2` functions, composed the way
    `run_head1` composes its GLD-included arm), and the per-fold dedup delta.

Which rows are "WITHDRAWN rows" -- fixed BEFORE the arm was run:
  ARM (attributed): every frame row reached by a scored WITHDRAWN chunk under
    `features_e2`'s own masks (`score_labels`) and decision 20's same-CIK
    every-occurrence attribution -- exactly the rows whose
    `guidance_signed_mean` contains a WITHDRAWN -1.
  RECONCILIATION (home key): the census's count (`census_e2.withdrawn_census`,
    the prereg's "35 of 7,389 rows"), which matches only the chunk's HOME
    filing and so misses later same-CIK filings that re-attach the chunk.
  Both are run and reported; neither can ever be the primary.

Writes ONLY `data/f5/sensitivity_decision11.json` and one appended
`run_log.jsonl` line. Never refits anything else; never touches the head-1
artifacts. ~1-3 minutes, $0, offline.

Run:  python3 data/f5/sensitivity_decision11.py      (from the repo root)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import backtest_e2 as BE  # noqa: E402
import features_e2 as FE  # noqa: E402
import spec as S  # noqa: E402

F5 = ROOT / "data" / "f5"
OUT_PATH = F5 / "sensitivity_decision11.json"
RESULTS_HEAD1 = F5 / "results_head1.json"
RUN_LOG = F5 / "run_log.jsonl"

LABEL = ("EXECUTED AFTER THE PRIMARY WAS SEEN (2026-11-05); pre-registered arm run late; "
         "can never be selected as the primary")
ARM_NAME = "decision 11: the 2020Q2 sensitivity (WITHDRAWN-guidance rows excluded)"


# ---------------------------------------------------------------------------
# which rows carry a WITHDRAWN label
# ---------------------------------------------------------------------------

def withdrawn_keys(labels: pd.DataFrame, chunks: pd.DataFrame) -> dict:
    """{"attributed": set, "home": set} of (cik, accession_number) keys.

    `labels` / `chunks` are row-aligned on chunk_id (asserted). The masks are
    `features_e2.score_labels` itself (8K_BODY dropped first, as `build_frame`
    does), so a WITHDRAWN label that the features never scored -- MDA-masked or
    8K_BODY -- marks nothing."""
    if not (labels["chunk_id"].values == chunks["chunk_id"].values).all():
        raise AssertionError("labels and chunks are not row-aligned on chunk_id")
    df = chunks.assign(**{c: labels[c].values for c in
                          ("section_type", "sentiment", "guidance_direction",
                           "guidance_applicable")})
    df = df[df["section_type"] != "8K_BODY"]
    scored = FE.score_labels(df)
    w = scored[(scored["guidance_direction"] == "WITHDRAWN") & scored["guidance_num"].notna()]
    reps = w["source_ciks"].map(len).to_numpy()
    occ = pd.DataFrame({
        "cik": np.concatenate(w["source_ciks"].values).astype("int64") if len(w) else [],
        "acc": np.concatenate(w["source_accession_numbers"].values) if len(w) else [],
        "home_cik": np.repeat(w["home_cik"].astype("int64").to_numpy(), reps),
    })
    occ = occ[occ["cik"] == occ["home_cik"]]  # decision 20: same-CIK attribution
    return {
        "n_scored_withdrawn_chunks": int(len(w)),
        "attributed": set(zip(occ["cik"].astype(int), occ["acc"].astype(str))),
        "home": set(zip(w["home_cik"].astype(int), w["home_accession_number"].astype(str))),
    }


def load_withdrawn_keys() -> dict:
    labels = pd.read_parquet(FE.LABELS_PATH, columns=[
        "chunk_id", "section_type", "sentiment", "guidance_direction", "guidance_applicable"])
    chunks = pd.read_parquet(FE.CHUNKS_PATH, columns=[
        "chunk_id", "home_cik", "home_accession_number", "source_ciks",
        "source_accession_numbers"])
    return withdrawn_keys(labels, chunks)


def row_mask(frame: pd.DataFrame, keys: set) -> np.ndarray:
    return np.array([(int(c), str(a)) in keys
                     for c, a in zip(frame[BE.CIK_COL], frame["accession_number"])], dtype=bool)


# ---------------------------------------------------------------------------
# the primary's per-fold dedup delta, composed from backtest_e2 (never copied)
# ---------------------------------------------------------------------------

def primary_dedup_deltas(frame: pd.DataFrame, params: dict) -> tuple[pd.DataFrame, list]:
    """Per-fold (text_and_numeric - numeric_only) dedup Spearman IC delta on
    `frame` (already GLD-excluded), primary spec, primary seed. The same calls
    `run_head1` makes for the primary arm and its GLD-included arm."""
    blocks = BE._blocks_from_params(params, frame)
    all_cols = sorted({c for cols in blocks.values() for c in cols})
    folds, purge = BE.build_folds(frame, params["fold_quarters"], params["purge_rule"])
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
    BE.assert_pinned_components(fframes, pinned_k, "decision11")
    rows, _ = BE.evaluate_arm(
        ranked, fframes,
        {k: v for k, v in blocks.items() if k in ("numeric_only", "text_and_numeric")},
        keep, params["overlap"]["column"], float(params["overlap"]["threshold"]),
        int(params["seeds"]["primary"]),
    )
    return BE.fold_deltas(rows, "dedup", "text_and_numeric"), purge


def arm_block(frame: pd.DataFrame, params: dict, mask: np.ndarray,
              primary: pd.DataFrame, primary_purge: list) -> dict:
    """Run the arm on `frame[~mask]` and tabulate it fold by fold beside the primary."""
    removed = frame[mask]
    deltas, purge = primary_dedup_deltas(frame[~mask].reset_index(drop=True), params)
    removed_q = removed[BE.FILING_DATE_COL].dt.to_period("Q").astype(str).value_counts()
    train_after = {p["test_quarter"]: p["n_train_after_purge"] for p in purge}
    per_fold = []
    for prim, (_, arm) in zip(primary.to_dict("records"), deltas.iterrows()):
        q = prim["test_quarter"]
        assert arm["test_quarter"] == q
        per_fold.append({
            "test_quarter": q,
            "n_removed_test_rows": int(removed_q.get(q, 0)),
            "n_removed_train_rows_after_purge":
                int(next(p["n_train_after_purge"] for p in primary_purge if p["test_quarter"] == q)
                    - train_after[q]),
            "n_test_dedup_primary": int(prim["n_test"]),
            "n_test_dedup_arm": int(arm["n_test"]),
            "delta_primary": float(prim["delta"]),
            "delta_arm": float(arm["delta"]),
        })
    return {
        "n_rows_removed_total": int(mask.sum()),
        "n_ciks_removed_from": int(removed[BE.CIK_COL].nunique()),
        "rows_removed_by_filing_quarter": {k: int(v) for k, v in sorted(removed_q.items())},
        "k_folds": int(len(deltas)),
        "mean_fold_delta_dedup": float(deltas["delta"].mean()),
        "per_fold": per_fold,
    }


def prereg_rule_row(doc_text: str) -> str:
    """The ratified decision-11 row, quoted from the pinned document (never retyped)."""
    rows = [ln for ln in doc_text.splitlines() if ln.startswith("| WITHDRAWN guidance |")]
    if len(rows) != 1:
        raise AssertionError(f"expected one WITHDRAWN guidance row in the prereg, found {len(rows)}")
    return rows[0]


def main() -> int:
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

    frame, diag = BE.load_analysis_frame()
    frame, gld = BE.exclude_gld_rows(frame, params)

    # Reproduction check -- loud, before any sensitivity number exists.
    primary, primary_purge = primary_dedup_deltas(frame, params)
    recorded = pd.DataFrame(head1["per_fold_primary_delta_dedup"])
    same_q = list(primary["test_quarter"]) == list(recorded["test_quarter"])
    max_diff = float(np.max(np.abs(primary["delta"].values - recorded["delta"].values))) \
        if same_q else float("inf")
    if not same_q or max_diff != 0.0:
        raise AssertionError(
            f"the recomposed primary does not reproduce results_head1.json (quarters equal: "
            f"{same_q}, max |diff| {max_diff}); no sensitivity number is trustworthy.")

    keys = load_withdrawn_keys()
    attributed = row_mask(frame, keys["attributed"])
    home = row_mask(frame, keys["home"])
    assert not (home & ~attributed).any(), "a home-key row is missing from the attributed set"

    out = {
        "label": LABEL,
        "arm": ARM_NAME,
        "ratified_rule_row": prereg_rule_row(BE.G3_DOC_PATH.read_text()),
        "never_the_primary": "Decision 11 makes this a sensitivity row. The §13 branch is decided "
                             "by the primary alone; this row can change no branch, no label and "
                             "no scorecard.",
        "definition": {
            "arm": "rows whose guidance_signed_mean contains a WITHDRAWN -1: scored WITHDRAWN "
                   "chunks (features_e2.score_labels masks, 8K_BODY dropped) attributed to "
                   "same-CIK filings (decision 20). Fixed before the arm was run.",
            "home_key_reconciliation": "census_e2.withdrawn_census's rule (the chunk's HOME "
                                       "filing only) -- the prereg's '35 of 7,389 rows'. It misses "
                                       "later same-CIK filings that re-attach the chunk.",
            "removal": "rows leave the run-time frame (GLD already excluded) BEFORE folds, purge, "
                       "dedup, PIT ranks, PCA and fits, so they leave both test and training sets.",
        },
        "run": {
            "utc": started.isoformat(timespec="seconds"),
            "doc_sha256": guard["doc_sha256"],
            "params_sha256": guard["params_sha256"],
            "module_sha256": BE.sha256_file(Path(__file__)),
            "backtest_e2_sha256": BE.sha256_file(ROOT / "backtest_e2.py"),
            "backtest_e2_sha256_in_head1_run": head1["run"]["module_sha256"],
            "features_e2_sha256": BE.sha256_file(ROOT / "features_e2.py"),
            "input_sha256": diag["input_sha256"],
            "labels_sha256": BE.sha256_file(FE.LABELS_PATH),
            "chunks_sha256": BE.sha256_file(FE.CHUNKS_PATH),
            "seed": int(params["seeds"]["primary"]),
        },
        "frame": {
            "n_run_time_rows": int(len(frame)),
            "n_gld_rows_excluded": gld["n_gld_rows_excluded"],
            "n_scored_withdrawn_chunks": keys["n_scored_withdrawn_chunks"],
            "n_attributed_filings": len(keys["attributed"]),
            "n_home_filings": len(keys["home"]),
        },
        "reproduction_check": {
            "primary_recomposed_equals_results_head1": True,
            "max_abs_diff_per_fold_delta": max_diff,
        },
        "primary_mean_fold_delta_dedup": float(head1["margin"]["mean_fold_delta"]),
        "primary_mean_source": "results_head1.json margin.mean_fold_delta",
        "sensitivity": arm_block(frame, params, attributed, primary, primary_purge),
        "home_key_reconciliation": arm_block(frame, params, home, primary, primary_purge),
        "inference_note": "A mean of per-fold deltas, one fit per fold at seed 0. No SE, no TOST, "
                          "no branch: the margin procedure applies to the primary only.",
    }
    out["runtime_seconds"] = round((datetime.now(timezone.utc) - started).total_seconds(), 1)
    OUT_PATH.write_text(json.dumps(out, indent=1) + "\n")
    BE.append_run_log(RUN_LOG, {
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "artifact": OUT_PATH.name,
        "sha256": BE.sha256_file(OUT_PATH),
        "doc_sha256": guard["doc_sha256"],
        "params_sha256": guard["params_sha256"],
        "module_sha256s": {"data/f5/sensitivity_decision11.py": out["run"]["module_sha256"],
                           "backtest_e2.py": out["run"]["backtest_e2_sha256"],
                           "features_e2.py": out["run"]["features_e2_sha256"]},
        "note": LABEL,
    })
    s, h = out["sensitivity"], out["home_key_reconciliation"]
    print(f"{LABEL}\nprimary mean {out['primary_mean_fold_delta_dedup']:+.4f} | "
          f"arm (n removed {s['n_rows_removed_total']}) mean {s['mean_fold_delta_dedup']:+.4f} | "
          f"home-key (n removed {h['n_rows_removed_total']}) mean "
          f"{h['mean_fold_delta_dedup']:+.4f} | wrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
