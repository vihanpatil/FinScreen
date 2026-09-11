"""
scorecard_e2.py -- the per-company, per-quarter historical scorecard
(G3 decision 3, owner ruling 2026-09-11; pre-registration §14).

This is a DESCRIPTION of what the pre-registered walk-forward already did,
not a second analysis and not an inference. It re-reads head 1's own
out-of-fold predictions -- nothing here fits a model, chooses a fold, or
touches a row the primary estimand did not already score -- and answers the
owner's question in their own words: *"was my model correct or wrong?"*, one
company and one quarter at a time.

Hard boundaries, all of them load-bearing:

  * The rows are head 1's primary-arm, DEDUPLICATED test rows -- exactly the
    rows the primary estimand uses. No forward-looking row, no company
    outside the run, no separate fit.
  * The call is a within-test-quarter tercile of the out-of-fold prediction,
    fixed before any result was seen (`tercile_within_test_quarter`).
  * "Correct" is a sign match against the realized 63-session excess return
    versus the membership-dated peer benchmark; an excess of exactly zero is
    NOT correct (`sign_match_nonzero`). "No call" rows are shown, never
    scored.
  * Hit rates are DESCRIPTIVE. The inference is the pre-registered IC margin
    ladder. Every page says so, verbatim, beside the numbers.
  * Nothing here is a trading signal, an expected return, or advice.

Pure functions over pandas/numpy; no scipy, no framework, no state. The
caller (`backtest_e2.run_head1`) owns the freeze guard, the fitting and the
ordering rule -- this module is only reached after the margin block exists.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent

#: Company display names/tickers, in lookup order. The E2 metadata DB covers
#: all 244 universe members (its `ticker` column is nullable and often NULL);
#: E1's DB covers 25 of them and does carry tickers. Both are read, the first
#: hit wins for the name and the first non-null wins for the ticker, and a CIK
#: in neither falls back to the CIK itself (both files are git-excluded, so a
#: fresh clone legitimately has neither).
COMPANY_DB_PATHS = (
    REPO_ROOT / "data" / "filings_metadata_e2.db",
    REPO_ROOT / "data" / "filings_metadata.db",
)

#: The implemented named rules. A pre-registered name with no implementation
#: here is a refusal, never a silent fallback (same rule as backtest_e2.py).
IMPLEMENTED_CALL_RULES = ("tercile_within_test_quarter",)
IMPLEMENTED_CORRECT_RULES = ("sign_match_nonzero",)
IMPLEMENTED_CI_RULES = ("wilson_95",)
IMPLEMENTED_EVAL_SETS = ("dedup",)

#: Column the out-of-fold records carry the realized target in
#: (`backtest_e2.E2_TARGET_COL`'s values; the pre-registration pins the name
#: as `scorecard.outcome_col` and `make_calls` refuses a mismatch).
OUTCOME_COL = "realized_excess"
OUTCOME_NAME = "target_excess_63"

CALL_OUT = "outperform peers"
CALL_UNDER = "underperform peers"
CALL_NONE = "no call"

#: §14's minimum number of calls before a per-company hit rate gets an
#: interval. `run_head1` always passes the ratified value explicitly; this
#: default exists so the function is usable in a test without a params block.
DEFAULT_MIN_CALLS = 6

#: Display names for the three blocks §14 prints side by side.
BLOCK_LABELS = {
    "text_and_numeric": "the model",
    "numeric_only": "numeric only",
    "size_only": "size only",
}

#: Printed verbatim at the top of every scorecard page (decision 3 + §11).
INFERENCE_SENTENCE = (
    "Hit rates are descriptive. The inference is the pre-registered IC margin ladder "
    "(§1, decision 15); a per-company hit rate over at most 33 quarters has a wide "
    "interval and proves nothing on its own."
)
#: The no-price counts are READ from the target manifest at write time (measured
#: `n_universe_member_ciks_absent_from_price_matrix` = 31 of 244 on 2026-09-11; an
#: earlier council summary said 32), so the sentence can never disagree with the
#: artifact. Absent manifest (selftest, tests) -> "n/a".
TARGET_MANIFEST_PATH = Path(__file__).resolve().parent / "data" / "f5" / "target_e2_manifest.json"


def prices_sentence(manifest_path: Path = TARGET_MANIFEST_PATH) -> str:
    absent, total = "n/a", "n/a"
    try:
        m = json.loads(Path(manifest_path).read_text())
        absent = _dig(m, "n_universe_member_ciks_absent_from_price_matrix")
        total = _dig(m, "n_universe_member_ciks_all_strata")
    except (OSError, ValueError):
        pass
    return (
        f"Prices: the 2026-08-24 Yahoo snapshot, split-adjusted only, {absent} of {total} universe "
        "members without usable prices; peers = the equal-weighted universe average "
        "excluding the company. Not advice; no trade is recommended; owner's own use."
    )


def _dig(obj, key):
    """First value of `key` anywhere in a nested dict, else 'n/a'."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            found = _dig(v, key)
            if found != "n/a":
                return found
    return "n/a"


def scope_sentence() -> str:
    """The one fixed scope sentence, READ from `backtest_e2` so it can never
    drift from the runner's copy. Imported inside the function because
    `backtest_e2` imports this module (a module-level import would be a
    cycle)."""
    from backtest_e2 import SCOPE_SENTENCE

    return SCOPE_SENTENCE


# ---------------------------------------------------------------------------
# 1. Calls
# ---------------------------------------------------------------------------


def make_calls(records_df: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Turn head 1's out-of-fold records into per-filing calls.

    Rows: the arm pinned by `scorecard.arm`, evaluation set `scorecard.eval_set`
    (`dedup` -> the deduplicated test rows), blocks = `scorecard.model_block`
    plus `scorecard.comparators`.

    Rule `tercile_within_test_quarter`: inside each (test_quarter, block), the
    prediction's percentile among that quarter's scored rows is
    `(rank - 0.5) / n`, with TIES BROKEN BY STABLE RANK ORDER -- pandas
    `rank(method="first")` over the frame's existing row order, which head 1
    fixes as (filing_date, cik, accession_number). Top third
    (percentile >= 2/3) -> "outperform peers"; bottom third (< 1/3) ->
    "underperform peers"; the middle third -> "no call" (shown, never scored).
    """
    sc = params["scorecard"]
    if sc["call_rule"] not in IMPLEMENTED_CALL_RULES:
        raise ValueError(
            f"scorecard.call_rule {sc['call_rule']!r} has no implementation here "
            f"(implemented: {list(IMPLEMENTED_CALL_RULES)})."
        )
    if sc["eval_set"] not in IMPLEMENTED_EVAL_SETS:
        raise ValueError(
            f"scorecard.eval_set {sc['eval_set']!r} has no implementation here "
            f"(implemented: {list(IMPLEMENTED_EVAL_SETS)})."
        )
    if sc["outcome_col"] != OUTCOME_NAME:
        raise ValueError(
            f"scorecard.outcome_col {sc['outcome_col']!r} is not the target these records "
            f"carry ({OUTCOME_NAME!r}). The scorecard scores the run's own outcome column "
            "or it scores nothing."
        )

    blocks = [sc["model_block"]] + list(sc["comparators"])
    unknown = [b for b in blocks if b not in BLOCK_LABELS]
    if unknown:
        raise ValueError(
            f"scorecard blocks {unknown} have no display rule here (implemented: "
            f"{list(BLOCK_LABELS)}). §14 prints the model and its two zero-text comparators."
        )
    df = records_df[
        (records_df["arm"] == sc["arm"])
        & records_df["in_dedup"].astype(bool)
        & records_df["block"].isin(blocks)
    ].copy()
    if df.empty:
        return df.assign(percentile=[], call=[])

    df = df.reset_index(drop=True)
    rank = df.groupby(["test_quarter", "block"])["prediction"].rank(method="first")
    n = df.groupby(["test_quarter", "block"])["prediction"].transform("size")
    df["percentile"] = (rank - 0.5) / n
    df["call"] = np.where(
        df["percentile"] >= 2.0 / 3.0,
        CALL_OUT,
        np.where(df["percentile"] < 1.0 / 3.0, CALL_UNDER, CALL_NONE),
    )
    df["call_rule"] = sc["call_rule"]
    return df


def score_calls(df: pd.DataFrame) -> pd.DataFrame:
    """Mark each call right or wrong (`sign_match_nonzero`).

    correct = ("outperform peers" and excess > 0) or ("underperform peers" and
    excess < 0). An excess of EXACTLY zero is not correct. "No call" rows carry
    `correct = NaN` -- they are shown and never scored."""
    out = df.copy()
    excess = out[OUTCOME_COL].astype(float)
    correct = (
        ((out["call"] == CALL_OUT) & (excess > 0))
        | ((out["call"] == CALL_UNDER) & (excess < 0))
    ).astype(float)
    correct = correct.where(out["call"] != CALL_NONE, np.nan)
    # An unresolved outcome is not a wrong call; it is not a call at all.
    correct = correct.where(excess.notna(), np.nan)
    out["correct"] = correct
    out["correct_rule"] = "sign_match_nonzero"
    return out


# ---------------------------------------------------------------------------
# 2. Intervals
# ---------------------------------------------------------------------------


def wilson_interval(k: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    """Wilson score interval for k successes in n trials (default z = 95%).

    Used instead of the normal approximation because per-company n is small;
    n = 0 returns (nan, nan) rather than pretending to an interval."""
    n = int(n)
    if n <= 0:
        return (float("nan"), float("nan"))
    p = float(k) / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return (float(centre - half), float(centre + half))


def _hit_rate(sub: pd.DataFrame) -> dict:
    scored = sub[sub["correct"].notna()]
    n_calls = int(len(scored))
    n_correct = int(scored["correct"].sum())
    lo, hi = wilson_interval(n_correct, n_calls)
    return {
        "n_calls": n_calls,
        "n_correct": n_correct,
        "hit_rate": float(n_correct / n_calls) if n_calls else None,
        "wilson_lo": lo if n_calls else None,
        "wilson_hi": hi if n_calls else None,
    }


# ---------------------------------------------------------------------------
# 3. Company + universe tables
# ---------------------------------------------------------------------------


def load_company_names(
    ciks, db_paths: tuple[Path, ...] = COMPANY_DB_PATHS
) -> dict[int, dict]:
    """{cik: {"name", "ticker"}} from the metadata DBs' `companies` table
    (columns `cik`, `company_name`, `ticker`). A CIK absent from every DB --
    or a DB absent from disk -- is simply not in the mapping, and the caller
    falls back to the CIK."""
    wanted = {int(c) for c in ciks}
    out: dict[int, dict] = {}
    for path in db_paths:
        path = Path(path)
        if not path.exists():
            continue
        try:
            con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            rows = con.execute("SELECT cik, company_name, ticker FROM companies").fetchall()
            con.close()
        except sqlite3.Error:
            continue
        for cik, name, ticker in rows:
            cik = int(cik)
            if cik not in wanted:
                continue
            entry = out.setdefault(cik, {"name": None, "ticker": None})
            if entry["name"] is None and name:
                entry["name"] = str(name)
            if entry["ticker"] is None and ticker:
                entry["ticker"] = str(ticker)
    return out


def _display(cik: int, names: dict) -> tuple[str, Optional[str]]:
    entry = names.get(int(cik)) or {}
    return (entry.get("name") or f"CIK {int(cik)}", entry.get("ticker"))


def company_tables(
    scored: pd.DataFrame,
    names: dict,
    min_calls: int = DEFAULT_MIN_CALLS,
    model_block: str = "text_and_numeric",
) -> list[dict]:
    """One entry per company, sorted by display name.

    `rows`: that company's scored filings in filing-date order, each carrying
    the quarter, form, public filing date, the realized excess return AS A
    PERCENTAGE, and the call + right/wrong for the model and both comparators.

    `summary`: the MODEL block's n_calls / n_correct / hit_rate, with a Wilson
    95% interval ONLY when n_calls >= `min_calls` (otherwise None -- rows only,
    per §14), plus that company's base rate: the share of its scored filings
    whose excess return was positive."""
    entries = []
    if scored.empty:
        return entries
    for cik, sub in scored.groupby("cik"):
        name, ticker = _display(cik, names)
        filings = sub.drop_duplicates(subset=["accession_number"]).sort_values(
            ["filing_date", "accession_number"], kind="mergesort"
        )
        by_acc = {
            acc: grp.set_index("block") for acc, grp in sub.groupby("accession_number")
        }
        rows = []
        for _, f in filings.iterrows():
            row = {
                "test_quarter": str(f["test_quarter"]),
                "form": str(f["form"]),
                "filing_date": str(pd.Timestamp(f["filing_date"]).date()),
                "accession_number": str(f["accession_number"]),
                "excess_return_pct": float(f[OUTCOME_COL]) * 100.0,
            }
            blocks = by_acc[f["accession_number"]]
            for block in BLOCK_LABELS:
                if block not in blocks.index:
                    row[f"{block}_call"] = None
                    row[f"{block}_result"] = None
                    continue
                entry = blocks.loc[block]
                call = str(entry["call"])
                correct = entry["correct"]
                row[f"{block}_call"] = call
                row[f"{block}_result"] = (
                    None if pd.isna(correct) else ("right" if float(correct) == 1.0 else "wrong")
                )
            rows.append(row)

        model_rows = sub[sub["block"] == model_block]
        summary = _hit_rate(model_rows)
        if summary["n_calls"] < int(min_calls):
            summary["wilson_lo"] = None
            summary["wilson_hi"] = None
            summary["interval_withheld"] = (
                f"fewer than {int(min_calls)} calls (§14): rows only, no interval"
            )
        excess = model_rows[OUTCOME_COL].astype(float).dropna()
        summary["base_rate"] = float((excess > 0).mean()) if len(excess) else None
        summary["n_filings"] = int(len(excess))
        summary["min_calls_for_hit_rate"] = int(min_calls)
        summary["block"] = model_block
        entries.append(
            {
                "cik": int(cik),
                "name": name,
                "ticker": ticker,
                "summary": summary,
                "rows": rows,
            }
        )
    return sorted(entries, key=lambda e: (e["name"].lower(), e["cik"]))


def universe_summary(scored: pd.DataFrame) -> dict:
    """Hit rate + Wilson 95% interval per block over the whole run, the
    universe base rate, and the three sentences every page carries."""
    blocks = {}
    present = set(scored["block"]) if "block" in scored.columns else set()
    order = [b for b in BLOCK_LABELS if b in present]
    for block in order:
        entry = _hit_rate(scored[scored["block"] == block])
        entry["label"] = BLOCK_LABELS[block]
        blocks[block] = entry
    filings = (
        scored.drop_duplicates(subset=["accession_number"]) if not scored.empty else scored
    )
    excess = (
        filings[OUTCOME_COL].astype(float).dropna() if not filings.empty else pd.Series(dtype=float)
    )
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "blocks": blocks,
        "n_filings_scored": int(len(excess)),
        "n_companies": int(scored["cik"].nunique()) if not scored.empty else 0,
        "n_test_quarters": int(scored["test_quarter"].nunique()) if not scored.empty else 0,
        "base_rate_positive_excess": float((excess > 0).mean()) if len(excess) else None,
        "call_rule": "tercile_within_test_quarter",
        "correct_rule": "sign_match_nonzero",
        "ci": "wilson_95",
        "scope_sentence": scope_sentence(),
        "inference_sentence": INFERENCE_SENTENCE,
        "prices_sentence": prices_sentence(),
    }


# ---------------------------------------------------------------------------
# 4. Writing
# ---------------------------------------------------------------------------


def _fmt(value, digits: int = 4) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "n/a"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _universe_table(summary: dict) -> list[str]:
    lines = [
        "| block | n calls | n correct | hit rate | 95% Wilson interval |",
        "|---|---|---|---|---|",
    ]
    for block, entry in summary["blocks"].items():
        interval = (
            f"[{_fmt(entry['wilson_lo'])}, {_fmt(entry['wilson_hi'])}]"
            if entry["n_calls"]
            else "n/a"
        )
        lines.append(
            f"| {entry['label']} (`{block}`) | {entry['n_calls']} | {entry['n_correct']} | "
            f"{_fmt(entry['hit_rate'])} | {interval} |"
        )
    return lines


def _company_section(entry: dict) -> list[str]:
    s = entry["summary"]
    title = f"### {entry['name']}"
    if entry["ticker"]:
        title += f" ({entry['ticker']})"
    if entry["name"] != f"CIK {entry['cik']}":   # no "CIK x -- CIK x" fallback line
        title += f" -- CIK {entry['cik']}"
    interval = (
        f", 95% Wilson [{_fmt(s['wilson_lo'])}, {_fmt(s['wilson_hi'])}]"
        if s.get("wilson_lo") is not None
        else f" ({s.get('interval_withheld', 'no interval')})"
    )
    lines = [
        title,
        "",
        f"The model: {s['n_correct']}/{s['n_calls']} calls right, hit rate "
        f"{_fmt(s['hit_rate'])}{interval}. Base rate (share of this company's scored "
        f"filings with a positive excess return): {_fmt(s['base_rate'])} over "
        f"{s['n_filings']} filings.",
        "",
        "| quarter | form | filing date | excess return | the model | numeric only | size only |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in entry["rows"]:
        cells = []
        for block in BLOCK_LABELS:
            call = row.get(f"{block}_call")
            result = row.get(f"{block}_result")
            cells.append("n/a" if call is None else (f"{call} ({result})" if result else call))
        lines.append(
            f"| {row['test_quarter']} | {row['form']} | {row['filing_date']} | "
            f"{row['excess_return_pct']:+.2f}% | " + " | ".join(cells) + " |"
        )
    lines.append("")
    return lines


def write_scorecard(
    scored: pd.DataFrame,
    summary: dict,
    tables: list[dict],
    md_path: Path,
    json_path: Path,
    parquet_path: Path,
) -> str:
    """Write the scorecard page (.md), its machine-readable twin (.json) and
    the per-row out-of-fold parquet. Returns the markdown text.

    Every number is read out of `summary`/`tables`, which were computed from
    the run's own out-of-fold records; nothing is hand-carried."""
    md_path, json_path, parquet_path = Path(md_path), Path(json_path), Path(parquet_path)
    for path in (md_path, json_path, parquet_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# E2 head 1 -- historical scorecard (pre-registration §14, decision 3)",
        "",
        f"**Scope sentence.** {summary['scope_sentence']}",
        "",
        f"**{summary['inference_sentence']}**",
        "",
        summary["prices_sentence"],
        "",
        f"Generated {summary['generated_utc']} UTC from the run's own out-of-fold "
        f"predictions: {summary['n_filings_scored']} deduplicated test filings, "
        f"{summary['n_companies']} companies, {summary['n_test_quarters']} test quarters. "
        f"Call rule `{summary['call_rule']}`; correct rule `{summary['correct_rule']}`; "
        f"intervals `{summary['ci']}`. A filing whose excess return was exactly zero is "
        "not scored correct. The tercile boundaries are drawn across that quarter's scored "
        "filings, so every call is a within-quarter relative statement about peers, not a "
        "real-time one.",
        "",
        "## Universe",
        "",
    ]
    lines += _universe_table(summary)
    lines += [
        "",
        f"Base rate (share of scored filings with a positive excess return): "
        f"{_fmt(summary['base_rate_positive_excess'])}.",
        "",
        "## Companies",
        "",
    ]
    for entry in tables:
        lines += _company_section(entry)
    lines += ["_Research screening only; no expected return, no trade, not advice._", ""]

    text = "\n".join(lines)
    md_path.write_text(text + "\n")
    json_path.write_text(
        json.dumps({"universe": summary, "companies": tables}, indent=2, default=str) + "\n"
    )
    if not scored.empty:
        scored.to_parquet(parquet_path, index=False)
    return text


def build_scorecard(
    records_df: pd.DataFrame,
    params: dict,
    md_path: Path,
    json_path: Path,
    parquet_path: Path,
) -> tuple[dict, pd.DataFrame]:
    """The whole §14 pipeline in one call: calls -> scoring -> tables -> files.

    Returns (summary, scored). The summary is what `run_head1` adds to the
    results document as `scorecard_summary` (after the margin block, like every
    other delta-bearing payload)."""
    called = make_calls(records_df, params)
    scored = score_calls(called)
    names = load_company_names(scored["cik"].unique() if not scored.empty else [])
    tables = company_tables(
        scored,
        names,
        int(params["scorecard"]["min_calls_for_company_hit_rate"]),
        params["scorecard"]["model_block"],
    )
    summary = universe_summary(scored)
    summary["arm"] = params["scorecard"]["arm"]
    summary["eval_set"] = params["scorecard"]["eval_set"]
    summary["min_calls_for_company_hit_rate"] = int(
        params["scorecard"]["min_calls_for_company_hit_rate"]
    )
    summary["files"] = {
        "markdown": str(md_path),
        "json": str(json_path),
        "per_row_parquet": str(parquet_path),
    }
    write_scorecard(scored, summary, tables, md_path, json_path, parquet_path)
    return summary, scored
