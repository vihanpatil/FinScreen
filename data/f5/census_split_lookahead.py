#!/usr/bin/env python3
"""census_split_lookahead.py -- how many ratified head-1 rows carry the
book-to-market split look-ahead (REVIEW_p5_packet_2026-11-10.md, finding M3).

The defect, recorded here and never patched: `numeric_features_e2.py` computes
book_to_market = equity / (shares * pre_close), with the share count as reported
at the time and the close from a price snapshot adjusted retroactively for every
split up to the fetch date. A filing made before a split therefore carries a
value too large by the split factor.

Read-only. It fits nothing, runs no runner, and modifies no frozen or ratified
artifact. Method (also written into the JSON):
  shares_as_used = equity / book_to_market / close at pre_session, where
  equity = equity_to_assets * exp(log_total_assets); one value per
  (cik, filing_date) (the median); a ratio >= THRESHOLD or <= 1/THRESHOLD
  between consecutive filing dates of one company is a split-like event; a row
  is "before a later event" when the product of the ratios of that company's
  events dated strictly after its filing date is >= THRESHOLD or <= 1/THRESHOLD.
Rows counted: the deduplicated rows (`in_dedup`) of head1_oof_predictions,
per block.

The tracked JSON holds NO call, outcome or hit rate (the repository is public;
legal baseline #4). `--show-private` prints, to stdout only and without writing
anything, the calls and hit rate on affected versus other rows per block.

    python3 data/f5/census_split_lookahead.py                 write the JSON
    python3 data/f5/census_split_lookahead.py --show-private  print, write nothing
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
NUMERIC = DATA / "f5" / "numeric_features_e2.parquet"
PRICES = DATA / "prices_e2.parquet"
OOF = DATA / "f5" / "head1_oof_predictions.parquet"
OUT = DATA / "f5" / "split_lookahead_census.json"
THRESHOLD = 1.8
BLOCKS = ("text_and_numeric", "numeric_only", "size_only")

METHOD = (
    "shares_as_used = equity / book_to_market / close at pre_session (equity = "
    "equity_to_assets * exp(log_total_assets)); one value per (cik, filing_date), the "
    "median; a ratio >= threshold or <= 1/threshold between consecutive filing dates of "
    "a company is a split-like event, dated at the first filing date showing it; a row "
    "is before a later event when the product of the ratios of that company's events "
    "dated strictly after its filing date is >= threshold or <= 1/threshold. Counted "
    "over the deduplicated rows (in_dedup) of head1_oof_predictions, per block. A lower "
    "bound: splits below the threshold, and rows whose book_to_market is NaN, are not "
    "seen.")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def shares_as_used(nf: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """(cik, filing_date, shares_used): the share count book_to_market implies."""
    d = nf.dropna(subset=["book_to_market", "equity_to_assets", "log_total_assets"])
    px = prices.rename(columns={"date": "pre_session", "close": "pre_close"})
    d = d.merge(px[["cik", "pre_session", "pre_close"]], on=["cik", "pre_session"],
                how="left")
    d = d[d.pre_close > 0]
    equity = d.equity_to_assets * np.exp(d.log_total_assets)
    d = d.assign(shares_used=equity / d.book_to_market / d.pre_close)
    return (d.groupby(["cik", "filing_date"]).shares_used.median().reset_index()
            .sort_values(["cik", "filing_date"], kind="mergesort"))


def detect_events(shares: pd.DataFrame, threshold: float = THRESHOLD) -> pd.DataFrame:
    """Rows (cik, filing_date, ratio) where the implied share count jumps by the threshold."""
    s = shares.sort_values(["cik", "filing_date"], kind="mergesort").copy()
    s["ratio"] = s.groupby("cik").shares_used.transform(lambda x: x / x.shift(1))
    jump = (s.ratio >= threshold) | (s.ratio <= 1 / threshold)
    return s.loc[jump, ["cik", "filing_date", "ratio"]].reset_index(drop=True)


def later_factor(events: pd.DataFrame, cik: int, filing_date) -> float:
    """Product of the ratios of `cik`'s events dated strictly after `filing_date`."""
    e = events[(events.cik == cik) & (events.filing_date > filing_date)]
    return float(np.prod(e.ratio.to_numpy())) if len(e) else 1.0


def before_later_event(rows: pd.DataFrame, events: pd.DataFrame,
                       threshold: float = THRESHOLD) -> pd.Series:
    f = np.array([later_factor(events, c, d) for c, d in zip(rows.cik, rows.filing_date)])
    return pd.Series((f >= threshold) | (f <= 1 / threshold), index=rows.index)


def load(data: Path = DATA):
    nf = pd.read_parquet(data / "f5" / NUMERIC.name)
    prices = pd.read_parquet(data / PRICES.name, columns=["cik", "date", "close"])
    oof = pd.read_parquet(data / "f5" / OOF.name)
    for frame, cols in ((nf, ["filing_date", "pre_session"]), (prices, ["date"]),
                        (oof, ["filing_date"])):
        for c in cols:
            frame[c] = pd.to_datetime(frame[c])
    return nf, prices, oof


def census(data: Path = DATA) -> dict:
    nf, prices, oof = load(data)
    events = detect_events(shares_as_used(nf, prices))
    per_block, affected_rows = {}, None
    for block in BLOCKS:
        rows = oof[(oof.block == block) & oof.in_dedup]
        hit = before_later_event(rows, events)
        per_block[block] = {"n_rows": int(len(rows)),
                            "n_rows_before_later_event": int(hit.sum())}
        if block == BLOCKS[0]:
            main, affected_rows = rows, rows[hit]
    if len({json.dumps(v, sort_keys=True) for v in per_block.values()}) != 1:
        raise SystemExit(f"blocks disagree on the dedup population: {per_block}")
    by_cik = affected_rows.groupby("cik").size()
    return {
        "what": "book_to_market split look-ahead census (REVIEW_p5_packet_2026-11-10 M3); "
                "no call, outcome or hit rate is recorded here",
        "method": METHOD,
        "threshold": THRESHOLD,
        "input_sha256": {p.name: sha256(data / p.relative_to(DATA)) for p in (NUMERIC, PRICES, OOF)},
        "n_events": int(len(events)),
        "n_event_companies": int(events.cik.nunique()),
        "events": [{"cik": int(r.cik), "filing_date": r.filing_date.date().isoformat(),
                    "ratio": round(float(r.ratio), 4)} for r in events.itertuples()],
        "n_rows": int(len(main)),
        "n_rows_before_later_event": int(len(affected_rows)),
        "n_companies": int(main.cik.nunique()),
        "n_companies_affected": int(by_cik.size),
        "affected_rows_by_cik": {str(int(c)): int(n) for c, n in by_cik.items()},
        "per_block": per_block,
    }


def show_private(data: Path = DATA) -> None:
    """Stdout only: calls and hit rate on affected vs other rows, per block."""
    nf, prices, oof = load(data)
    events = detect_events(shares_as_used(nf, prices))
    print("PRIVATE -- stdout only, never written to a tracked file (legal baseline #4)")
    for block in BLOCKS:
        rows = oof[(oof.block == block) & oof.in_dedup]
        hit = before_later_event(rows, events)
        for label, sub in (("before a later split", rows[hit]), ("all other", rows[~hit])):
            calls = sub[~sub.is_no_call & ~sub.is_unresolved]
            rate = calls.correct.mean() if len(calls) else float("nan")
            print(f"{block:<17} {label:<21} rows {len(sub):>5}  calls {len(calls):>5}  "
                  f"hit rate {rate:.4f}  mix {calls.call.value_counts().to_dict()}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--show-private", action="store_true")
    a = ap.parse_args(argv)
    if a.show_private:
        show_private()
        return 0
    result = census()
    OUT.write_text(json.dumps(result, indent=1) + "\n")
    print(f"{result['n_events']} events in {result['n_event_companies']} companies; "
          f"{result['n_rows_before_later_event']} of {result['n_rows']} rows; "
          f"{result['n_companies_affected']} of {result['n_companies']} companies -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
