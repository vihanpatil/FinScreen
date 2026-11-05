#!/usr/bin/env python3
"""Render `data/f5/report_head1_addendum.md` from the head-1 results (review S4 + S5).

`report_head1.md` is a render of `results_head1.json` by `backtest_e2.write_report`,
and `backtest_e2.py` is frozen for the 2026-11-05 run. So the missing pieces are
rendered HERE, from the same documents, as a separate addendum -- no refit, no
edit of any head-1 artifact:

  S4  the mean per-fold dedup delta of every always-reported arm beside the
      primary, and the §11 escort block -- the very sentences the scorecard page
      carries, rebuilt by `backtest_e2.build_disclosures` from the same
      artifacts and checked verbatim against `head1_scorecard.md` when present;
  S5  an override paragraph for the stale E1-era boilerplate (frozen `spec.py`)
      and the noise-anchor scope note.

Every number is read from an artifact; nothing is typed. Refuses (exit 2) unless
the pin holds, and refuses to render a `results_head1.json` whose sha is not the
one run_log recorded. Appends one run_log line with the addendum's sha.

Run:  python3 data/f5/render_head1_addendum.py      (from the repo root; ~2 s)
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import backtest_e2 as BE  # noqa: E402

F5 = ROOT / "data" / "f5"
RESULTS = F5 / "results_head1.json"
REPORT = F5 / "report_head1.md"
SCORECARD_MD = F5 / "head1_scorecard.md"
SENSITIVITY = F5 / "sensitivity_decision11.json"
OUT = F5 / "report_head1_addendum.md"
RUN_LOG = F5 / "run_log.jsonl"

# (label, results key, where the per-fold records live, stored-mean key or None)
ARMS = [
    ("PRIMARY: pit_trailing_rank, dedup (the estimand)", "per_fold_primary_delta_dedup", None, None),
    ("secondary (mandatory): raw_levels, dedup", "per_fold_delta__raw_levels__dedup__text_and_numeric",
     None, None),
    ("sensitivity: include_same_day=False, dedup",
     "per_fold_delta__pit_trailing_rank_no_same_day__dedup__text_and_numeric", None, None),
    ("overlap arm: dedup, no train-overlap rows",
     "per_fold_delta__pit_trailing_rank__dedup_no_overlap__text_and_numeric", None, None),
    ("raw (non-dedup) evaluation set", "per_fold_delta__pit_trailing_rank__raw__text_and_numeric",
     None, None),
    ("form-controlled ablation (10-Q/10-K only), dedup", "form_controlled_ablation",
     "per_fold_delta_dedup", "mean_fold_delta_dedup"),
    ("rolling 8-quarter training window, dedup", "per_fold_delta__rolling_8q", "records",
     "mean_fold_delta_dedup"),
    ("rolling 16-quarter training window, dedup", "per_fold_delta__rolling_16q", "records",
     "mean_fold_delta_dedup"),
    ("GLD-included frame, dedup", "per_fold_delta__gld_included", "records", "mean_fold_delta_dedup"),
]

# Stale E1-era sentences in the rendered report (their source is frozen spec.py).
STALE_PHRASES = [
    "there is no embargo/purge, and the population has never been stated",
    "Whether to embargo is a G3 pre-registration decision; this report only measures it.",
    "exactly the same non-embargoed-label property the fitted models have",
    "at k = 6 neither tail is anywhere near significant",
    "At E2's ~26 folds",
    "the standard deviation of six numbers",
]


def arm_rows(results: dict) -> list[dict]:
    """One row per always-reported arm: k, mean, positive folds -- recomputed from
    the per-fold records and asserted equal to any mean the run stored itself."""
    out = []
    for label, key, sub, stored_key in ARMS:
        block = results[key]
        if isinstance(block, dict) and block.get("status"):
            out.append({"arm": label, "source": key, "status": block["status"]})
            continue
        records = block[sub] if sub else block
        deltas = [float(r["delta"]) for r in records]
        mean = sum(deltas) / len(deltas)
        if stored_key is not None and not math.isclose(mean, float(block[stored_key]),
                                                       rel_tol=0, abs_tol=1e-12):
            raise AssertionError(f"{key}: recomputed mean {mean} != stored {block[stored_key]}")
        out.append({"arm": label, "source": key + (f".{sub}" if sub else ""), "k": len(deltas),
                    "mean": mean, "n_positive": sum(d > 0 for d in deltas)})
    primary = float(results["margin"]["mean_fold_delta"])
    if not math.isclose(out[0]["mean"], primary, rel_tol=0, abs_tol=1e-12):
        raise AssertionError(f"primary mean {out[0]['mean']} != margin.mean_fold_delta {primary}")
    return out


def escorts(results: dict, scorecard_md: Optional[Path]) -> dict:
    """The scorecard page's disclosure block, rebuilt from the same artifacts by
    the same function, on the run-time frame and the run's own diagnostics."""
    frame, _ = BE.load_analysis_frame()
    frame, _ = BE.exclude_gld_rows(frame, results["params"])
    disc = BE.build_disclosures(frame, results["frame"],
                                emb_calls=results.get("missing_embedding_calls"))
    if scorecard_md is not None and Path(scorecard_md).exists():
        page = Path(scorecard_md).read_text()
        drift = [k for k, v in disc.items() if v not in page]
        if drift:
            raise AssertionError(f"disclosures {drift} differ from {Path(scorecard_md).name}; "
                                 "an artifact changed since the run -- render nothing")
    return disc


def render(results: dict, report_text: str, disclosures: dict, shas: dict,
           sensitivity: Optional[dict], unruled: list) -> str:
    rows = arm_rows(results)
    lines = [
        "# E2 head 1 -- report addendum (render-only; review S4 + S5)",
        "",
        f"Rendered {datetime.now(timezone.utc).isoformat(timespec='seconds')} by "
        "`data/f5/render_head1_addendum.py` from `results_head1.json` "
        f"(sha256 `{shas['results']}`). It adds to `report_head1.md` (sha256 `{shas['report']}`), "
        "which is left untouched; no model was fitted. Every number below is read from an "
        "artifact. Where this addendum and the report disagree, this addendum governs.",
        "",
        "## A. Every always-reported arm beside the primary (mean of per-fold dedup Spearman "
        "IC deltas, text+numeric minus numeric-only)",
        "",
        "| arm | k folds | mean fold delta | folds > 0 | source key in results_head1.json |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        if "status" in r:
            lines.append(f"| {r['arm']} | -- | {r['status']} | -- | `{r['source']}` |")
        else:
            lines.append(f"| {r['arm']} | {r['k']} | {r['mean']:+.4f} | {r['n_positive']} "
                         f"| `{r['source']}` |")
    if sensitivity:
        s = sensitivity["sensitivity"]
        lines.append(
            f"| decision 11, the 2020Q2 sensitivity (WITHDRAWN rows excluded, n = "
            f"{s['n_rows_removed_total']}) -- {sensitivity['label']} | {s['k_folds']} | "
            f"{s['mean_fold_delta_dedup']:+.4f} | "
            f"{sum(f['delta_arm'] > 0 for f in s['per_fold'])} | `sensitivity_decision11.json` |")
        h = sensitivity["home_key_reconciliation"]
        lines.append(
            f"| decision 11 reconciliation: the census's home-filing rule (n = "
            f"{h['n_rows_removed_total']}, the prereg's measured count) -- same label | "
            f"{h['k_folds']} | {h['mean_fold_delta_dedup']:+.4f} | "
            f"{sum(f['delta_arm'] > 0 for f in h['per_fold'])} | `sensitivity_decision11.json` |")
    lines += [
        "",
        "Only the first row drives §13 (decision 15). Every other row is a sensitivity or a "
        "mandatory secondary: reported beside the primary, never selected in its place. A mean "
        "of per-fold deltas carries no SE here; the margin procedure applies to the primary "
        "alone.",
        *([
            "",
            f"Decision 11's row removes the {sensitivity['sensitivity']['n_rows_removed_total']} "
            "rows whose `guidance_signed_mean` contains a WITHDRAWN label under the features' own "
            "same-CIK attribution; the prereg's measured count "
            f"({sensitivity['home_key_reconciliation']['n_rows_removed_total']}) matched only each "
            "chunk's home filing. Both rows are shown; neither can be selected. Its 2020Q2 fold "
            "loses "
            + str(next(f['n_removed_test_rows'] for f in sensitivity['sensitivity']['per_fold']
                       if f['test_quarter'] == '2020Q2'))
            + " test rows.",
        ] if sensitivity else []),
        "",
        "## B. §11 instrument escorts (these travel with every result above)",
        "",
        "Rebuilt by `backtest_e2.build_disclosures` from the artifacts the scorecard page reads "
        "(G2 results, the labeler's own eval, census_e2, the target manifest) and verified "
        "verbatim against the scorecard page's disclosure block.",
        "",
    ]
    names = {"labels": "Label quality", "train_overlap": "Train overlap",
             "extraction": "Extraction coverage", "fx": "Currency (the CAD exception)",
             "missing_embedding": "Missing embeddings", "price_censoring":
             "Price censoring (survivorship direction)", "returns": "What these returns are",
             "peer_benchmark": "Peer benchmark"}
    for key, text in disclosures.items():
        lines.append(f"- **{names.get(key, key)}.** {text}")
    if unruled:
        lines.append(
            f"- **Two unruled ratios.** {', '.join(f'`{u}`' for u in unruled)} stay on the ported "
            "definition (numeric manifest `counters.ocf_to_revenue_duration_match."
            "unruled_ratios_left_as_ported`); a main-session scope boundary, not the owner's "
            "ruling (G3 §11).")
    lines += [
        "- **Model consensus.** Every G2 agreement rate is model consensus over "
        "model-adjudicated fields, not human validation of ground truth (G3 §11).",
        "",
        "## C. Override: stale E1-era sentences in report_head1.md",
        "",
    ]
    found = [p for p in STALE_PHRASES if p in report_text]
    embargo = results["standing"]["embargo_census_post_purge"]
    leaked = sum(int(r["n_train_labels_resolving_in_or_after_test_quarter"]) for r in embargo)
    n_train = sum(int(r["n_train"]) for r in embargo)
    anchor = results["standing"]["bootstrap_anchor"][BE.S.PRIMARY_SPEC]["per_fold"]
    primary = {r["test_quarter"]: float(r["delta"]) for r in results["per_fold_primary_delta_dedup"]}
    gaps = [(a["test_quarter"], float(a["fold_delta_dedup"]), primary[a["test_quarter"]])
            for a in anchor if a["test_quarter"] in primary]
    worst = max(gaps, key=lambda g: abs(g[1] - g[2]))
    first = gaps[0]
    lines += [
        "The report carries boilerplate written for E1 by frozen `spec.py`. These sentences "
        "are stale and are overridden here:",
        "",
        *[f"- \"{p}\"" for p in found],
        "",
        f"The ratified purge (`purge_rule` = `{results['params']['purge_rule']}`) applied to "
        f"every fold: per the report's own label-embargo table, **{leaked} of {n_train:,} "
        "training labels** resolve on or after their fold's test quarter begins. Training "
        "labels are purged, not non-embargoed, and that holds for the `ticker_training_mean_rank` "
        f"benchmark too (it is built on the same purged folds). The run has **k = "
        f"{results['margin']['k_folds']} folds**, not 6 and not ~26, and its lag-1 "
        f"autocorrelation was measured: {results['margin']['measured_lag1_autocorrelation']:+.4f}.",
        "",
        "The noise-anchor section headed **PRIMARY** is not computed on the primary's feature "
        "block. The run's own scope note (`standing.bootstrap_anchor_scope`), quoted:",
        "",
        f"> {results['standing']['bootstrap_anchor_scope']}",
        "",
        "So that section's `fold_delta_dedup` column is a different quantity from §2's primary "
        f"deltas. Examples: {first[0]} {first[1]:+.4f} (anchor) vs {first[2]:+.4f} (primary), and "
        f"the widest gap, {worst[0]}, is {worst[1]:+.4f} vs {worst[2]:+.4f}. Quote §2, never the "
        "anchor table, for a per-fold primary delta.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    try:
        _, guard = BE.load_g3_params()
    except BE.G3Refusal as exc:
        print(str(exc))
        return 2
    results = json.loads(RESULTS.read_text())
    shas = {"results": BE.sha256_file(RESULTS), "report": BE.sha256_file(REPORT)}
    logged = [json.loads(ln) for ln in RUN_LOG.read_text().splitlines() if ln.strip()]
    if shas["results"] not in {e.get("results_sha256") for e in logged}:
        raise BE.G3Refusal("BLOCKED: results_head1.json's sha is not the one run_log recorded.")
    if results["run"]["doc_sha256"] != guard["doc_sha256"]:
        raise BE.G3Refusal("BLOCKED: results_head1.json was not produced under this pin.")
    sensitivity = json.loads(SENSITIVITY.read_text()) if SENSITIVITY.exists() else None
    unruled = (json.loads(BE.NUMERIC_MANIFEST.read_text()).get("counters", {})
               .get("ocf_to_revenue_duration_match", {}).get("unruled_ratios_left_as_ported", []))
    text = render(results, REPORT.read_text(), escorts(results, SCORECARD_MD), shas,
                  sensitivity, unruled)
    OUT.write_text(text)
    BE.append_run_log(RUN_LOG, {
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "artifact": OUT.name,
        "sha256": BE.sha256_file(OUT),
        "renders": {"results_head1.json": shas["results"], "report_head1.md": shas["report"]},
        "module_sha256s": {"data/f5/render_head1_addendum.py": BE.sha256_file(Path(__file__)),
                           "backtest_e2.py": BE.sha256_file(ROOT / "backtest_e2.py")},
    })
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
