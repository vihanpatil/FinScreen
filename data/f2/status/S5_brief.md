# S5 brief — prices at scale (issued 2026-08-24)

Agent: data-engineer (Opus). Runs IN PARALLEL with S3 and S4 (disjoint
files). If S5 shows IN FLIGHT in `F2_PROGRESS.md` with no
`S5_prices.md` completion report, the agent died — check `git diff` for
partial edits, relaunch with this brief verbatim.

## Task

Implement F2 stage S5 exactly as specified in `data/f2/F2_SPEC.md`
**§6** (ratified 2026-08-24, `F2_PROGRESS.md` §5), plus the S5 test block
in spec §8.2 and the §8.1 re-pin of `test_ingest_prices.py`. S2 is DONE
(read `data/f2/status/S2_membership.md`): universe loading is CIK-keyed;
import window constants and universe helpers from `ingest_metadata`
read-only.

## Read first

`data/f2/F2_SPEC.md` §6 + §8 → `data/f2/status/S2_membership.md` →
`HANDOFF.md` §7 + `data/PRICES_NOTES.md` §1 → `ingest_prices.py`,
`price_client.py`, `test_ingest_prices.py`,
`data/universe_e2_candidates/price_censoring_census.parquet`.

## Scope

1. **CIK-verified ticker resolution** (spec §6.1, exact rule as written:
   submissions-only candidates, NON_COMMON regex, share-class dashes
   kept, bulk map as contradiction-detector-only — absence never
   censors).
2. **`data/f2/price_ticker_overrides.csv`** with exactly one evidenced
   row (34088 → XOM), load-time validation rejecting undocumented rows;
   CIK 29915 (Dow Chemical) deliberately censored — never mapped to the
   2019 spin-off's `DOW` (spec §6.2).
3. **Census reconciliation** (spec §6.3): re-derive at resolution time,
   diff against F1's `price_censoring_census.parquet` with the
   pre-registered expected delta (−XOM, +EIDP → 31); any other delta is
   a reported finding. Output `data/f2/price_ticker_map.csv` with the
   spec's columns. Expected: 212 resolved + 1 override = 213 fetchable,
   31 censored (27 core / 4 extension) — if your run of the rule
   produces different counts, that is a STOP-and-report finding, not a
   number to silently adopt.
4. **Fetch changes** (spec §6.4): parquet gains `cik` (join key);
   `--price-source {yahoo,stooq-first}` default `yahoo` (Stooq path
   intact); full history (`period1=0`); Yahoo `meta.symbol` /
   `instrumentType` sanity tripwire → WARN; `missing_entirely` FATAL
   only for resolved tickers — censored CIKs appear in the censoring
   report, never as FATALs; no benchmark work (F5/G3).
5. **Tests** (spec §8.2 S5 block), all offline, synthetic submissions
   fixtures; re-pin `test_ingest_prices.py::test_load_universe_returns_
   all_25_tickers` per spec §8.1 (counts + the 25 E1 CIK↔ticker pairs,
   XOM via override).

## Parallel-run coordination (binding)

- Do NOT edit `F2_PROGRESS.md` — the main session flips statuses.
- Do NOT touch `ingest_metadata.py`, `edgar_client.py`,
  `ingest_fundamentals.py`, or their test files (owned by S3/S4, running
  now). `price_client.py` is yours if needed; prefer parse-time checks
  in `ingest_prices.py`.
- Do NOT run the full pytest suite (siblings are editing concurrently).
  Run YOUR test files (`test_ingest_prices.py`, `test_price_client.py`).
  The main session runs the full gate after all three stages land.
- **Zero live network GETs** — resolution runs off cached submissions;
  the 213-ticker Yahoo fetch is S6's job, main session only. Do not hit
  Yahoo or Stooq at all in S5.

## Constraints

Lazy-elite (minimal diffs, no frameworks); no Anthropic API; E1 frozen
artifacts untouched (`data/prices.parquet` is E1's — E2 output path per
spec).

## Deliverables (BOTH before returning)

1. Code + your targeted tests green (exact counts).
2. `data/f2/status/S5_prices.md` — completion report: files touched,
   the measured resolution counts vs the spec's expectations, test
   counts, deviations from spec (expected none), resume instructions if
   partial.
