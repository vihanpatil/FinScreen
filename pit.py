"""
pit.py -- the point-in-time (PIT) selection helper over
`data/fundamentals.parquet`-shaped DataFrames (see ingest_fundamentals.py).

Why this file exists (HANDOFF.md §7 hard rule): `data/fundamentals.parquet`
stores EVERY filed occurrence of every XBRL fact -- never deduplicated, never
overwritten on restatement (a restatement is a new row with a later `filed`
date, same period). That is deliberate: it is the only way to answer "what
was known as of date X" without look-ahead bias. But it means naive
consumption (e.g. "the row with the latest `filed` for this concept") is
wrong for two different reasons depending on what a caller wants:
  - it doesn't scope by as-of date (would leak future filings), and
  - it doesn't pick the right value for a period once more than one filing
    reports it (the common case: nearly every quarter's figure is reported
    once as the current period, then again as a prior-period comparative in
    the following quarter's 10-Q, and occasionally restated with a changed
    value).

`value_as_of()` is the one tested helper that does this correctly. Read its
docstring for the exact selection rule -- it is deliberately spelled out in
full because getting this wrong silently reintroduces exactly the look-ahead
bias the point-in-time discipline exists to prevent.

Selection-rule note -- a deliberate deviation from the requirement as it was
originally worded, restated here in full so it can be checked without any
external document. The requirement had two clauses:

  (i)  pick the "earliest filed row" for the latest period; and
  (ii) restatement behavior: "original value returned for as-of dates
       before the restatement's filed date, restated value after."

Clause (i) read literally fails clause (ii) -- taking the *earliest* filed row for a
period would return the stale original value forever, even long after a
restated value became public knowledge, which is the wrong PIT semantics for
a research tool (the whole point of `filed <= as_of` is "everything publicly
knowable by that date," and a restatement that has already been filed by
as_of date IS knowable by then). This implementation follows the explicit
restatement test (clause ii) instead: within the most recent period whose
data is knowable by `as_of`, it returns the value from the LATEST filed row
that is still `<= as_of` -- i.e. the most up-to-date publicly known figure
for that period as of that date. The deviation from clause (i) is flagged
here deliberately, not silently resolved either way; the PIT discipline it
serves is the standing hard rule in `HANDOFF.md` §7.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd


def value_as_of(
    df: pd.DataFrame,
    concept: str,
    as_of,
    ticker: Optional[str] = None,
    cik: Optional[int] = None,
    taxonomy: Optional[str] = None,
) -> Optional[dict]:
    """Return the fact row for `concept` that was "as originally knowable"
    on `as_of`, scoped to one company via `ticker` and/or `cik` (at least one
    of them should normally be given -- a concept name alone is not unique
    across the universe).

    Selection rule (exact, in order):
      1. Filter `df` to rows matching `concept` (exact string match against
         the `concept` column -- callers pick one specific XBRL tag, e.g.
         "NetIncomeLoss"; this function does NOT resolve revenue aliases --
         that reconciliation is features.py's job per the "no derived
         metrics in ingestion" scope boundary), and to `taxonomy`/`ticker`/
         `cik` if given.
      2. Filter to rows where `filed <= as_of` -- i.e. rows that were
         publicly available by the as-of date. Rows filed after `as_of` are
         invisible to this function, full stop; this is what prevents
         look-ahead bias.
      3. Among the rows surviving step 2, group by period identity
         (`period_end` alone -- see the "period identity" caveat below) and
         find the single most recent `period_end`. This is "the latest
         period whose data had been disclosed by as_of."
      4. Within that period's rows (still all `filed <= as_of`), take the
         one with the LATEST `filed` date -- i.e. the most recently known
         value for that period as of `as_of`. If a restatement for that
         exact period was itself filed on or before `as_of`, this returns
         the restated value; if not, it returns the original. Ties on
         `filed` (same calendar date) are broken deterministically by
         `accession_number` (lexicographically largest wins -- EDGAR
         accession numbers are date-ordered within a filer, so this is a
         stable, reproducible tiebreak, not an arbitrary one).
      5. Returns the full row as a dict (all original columns), or `None` if
         no row survives step 2.

    Period-identity caveat (documented, not silently papered over): grouping
    by `period_end` alone can, in principle, collide a full-year duration
    fact with a Q4 duration fact that happens to share the same end date
    (both would have `period_end` on the fiscal year-end date, but different
    `period_start`). This function does not attempt to disambiguate
    annual-vs-quarterly amounts for a shared end date -- callers needing
    that distinction should additionally filter by `form`/`fp`/
    `period_start` before or after calling this, since resolving that
    ambiguity is a feature-engineering decision (features.py's scope), not a
    point-in-time-correctness one (this function's scope).
    """
    subset = df[df["concept"] == concept]
    if taxonomy is not None:
        subset = subset[subset["taxonomy"] == taxonomy]
    if ticker is not None:
        subset = subset[subset["ticker"] == ticker]
    if cik is not None:
        subset = subset[subset["cik"] == int(cik)]

    if subset.empty:
        return None

    as_of_ts = pd.Timestamp(as_of)
    filed_ts = pd.to_datetime(subset["filed"])
    subset = subset[filed_ts.values <= as_of_ts.to_datetime64()]
    if subset.empty:
        return None

    period_end_ts = pd.to_datetime(subset["period_end"])
    max_period_end = period_end_ts.max()
    period_rows = subset[period_end_ts.values == max_period_end.to_datetime64()]

    # Deterministic ordering: filed date ascending, then accession_number
    # ascending -- the last row after sorting is "latest filed, tie broken by
    # largest accession_number", exactly matching step 4's tiebreak rule.
    period_rows = period_rows.assign(_filed_ts=pd.to_datetime(period_rows["filed"]))
    period_rows = period_rows.sort_values(["_filed_ts", "accession_number"])
    chosen = period_rows.iloc[-1].drop(labels=["_filed_ts"])
    return chosen.to_dict()
