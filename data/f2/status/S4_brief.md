# S4 brief — fundamentals systematic re-ingest (issued 2026-08-24)

Agent: data-engineer (Opus). Runs IN PARALLEL with S3 and S5 (disjoint
files). If S4 shows IN FLIGHT in `F2_PROGRESS.md` with no
`S4_fundamentals.md` completion report, the agent died — check `git diff`
for partial edits, relaunch with this brief verbatim.

## Task

Implement F2 stage S4 exactly as specified in `data/f2/F2_SPEC.md`
**§5** (ratified 2026-08-24, `F2_PROGRESS.md` §5), plus the S4 test block
in spec §8.2 and the §8.1 re-pins for `test_ingest_fundamentals.py`.
S2 is DONE (read `data/f2/status/S2_membership.md`): universe loading is
CIK-keyed, window constants importable, §3.4 validation re-scoping is
already in `ingest_fundamentals.py` — build on it, don't redo it.

## Read first

`data/f2/F2_SPEC.md` §5 + §8 → `data/f2/status/S2_membership.md` →
`HANDOFF.md` §2a traps (a)–(d) + §7 → `ingest_fundamentals.py` (post-S2),
`test_ingest_fundamentals.py`, `pit.py`.

## Scope

1. **`CONCEPT_FAMILIES` replaces the flat `CONCEPTS` list** (spec §5.2,
   exact families/tags as tabled). Every tag ingested and stored as-is
   under its own tag name — no unification in the ingestion layer.
2. **Delete the three hand-curated maps**
   (`BANK_TICKERS_MISSING_INDUSTRIAL_CONCEPTS`, `BANK_EXEMPT_CONCEPTS`,
   `KNOWN_MIDWINDOW_MIGRATIONS`), preserving them verbatim in your
   completion report as the record of what the classifier must
   reproduce.
3. **The five-state alias/migration classifier** (spec §5.3, exact
   states/conditions/thresholds as tabled): per (cik, family), operating
   forms only (10-K/10-Q/8-K + /A; DEF 14A excluded — trap (c)),
   UNRESOLVED → `fundamentals_alias_unresolved` FATAL rows, never a
   stale fallback. Output `data/f2/concept_resolution.csv` with the
   spec's columns.
4. **Sector-concentration BLOCKER rule**: UNRESOLVED >20% of a sector's
   members for a family → BLOCKER surfaced at the top of the run
   report/output.
5. **Tests**: rewrite `test_ingest_fundamentals.py`'s 12 affected tests
   against families + classifier states; the acceptance tests
   reproducing every deleted hand-map case (JPM/BAC/GS cash, MA/OXY
   net_income, SLB operating_income, CVX restricted cash) run against
   fixtures sliced from the cached companyfacts — never live. Sector
   BLOCKER boundary tests (21% fires / 19% doesn't). All offline.

## Parallel-run coordination (binding)

- Do NOT edit `F2_PROGRESS.md` — the main session flips statuses.
- Do NOT touch `ingest_metadata.py`, `edgar_client.py`,
  `ingest_prices.py`, `price_client.py`, or their test files (owned by
  S3/S5, running now). Import from `ingest_metadata` read-only.
- Do NOT run the full pytest suite (siblings are editing concurrently).
  Run YOUR test files + `test_pit.py`. The main session runs the full
  gate after all three stages land.
- Zero live network GETs. The 25 cached companyfacts under
  `data/raw/companyfacts/` are your fixture source; the 244-CIK fetch is
  S6's job.

## Constraints

Lazy-elite (minimal diffs; the classifier is ~one function + one dict,
not a framework); no Anthropic API; E1 frozen artifacts untouched
(`data/fundamentals.parquet` is E1's — E2 output path per spec).

## Deliverables (BOTH before returning)

1. Code + your targeted tests green (exact counts).
2. `data/f2/status/S4_fundamentals.md` — completion report: files
   touched, the three preserved hand-maps verbatim, test counts,
   deviations from spec (expected none), resume instructions if partial.
