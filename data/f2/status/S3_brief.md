# S3 brief — metadata + documents ingestion at scale (issued 2026-08-24)

Agent: data-engineer (Opus). Runs IN PARALLEL with S4 and S5 (disjoint
files). If S3 shows IN FLIGHT in `F2_PROGRESS.md` with no
`S3_metadata_documents.md` completion report, the agent died — check
`git diff` for partial edits, relaunch with this brief verbatim.

## Task

Implement F2 stage S3 exactly as specified in `data/f2/F2_SPEC.md`
**§4** (ratified 2026-08-24, `F2_PROGRESS.md` §5), plus the S3 test block
in spec §8.2. S2 is DONE: `load_universe()`/`load_membership()` are
CIK-keyed with coverage windows, window constants exist, validation is
per-company-window (see `data/f2/status/S2_membership.md` — read it,
including its four measurement-resolved clarifications).

## Read first

`data/f2/F2_SPEC.md` §4 + §8.2(S3) → `data/f2/status/S2_membership.md` →
`HANDOFF.md` §4+§7 → `ingest_metadata.py` (post-S2), `edgar_client.py`.

## Scope

1. **Enumeration at scale** (spec §4.1): per-CIK enumeration over
   `[coverage_start(cik), min(coverage_end(cik), CORPUS_WINDOW_END)]`,
   TARGET_FORMS filter, pagination via `filings.files[]`.
2. **`--stage {metadata,documents,all}`** on `ingest_metadata.py`
   (spec §4.6): `--stage documents` prefetches every 10-K/10-Q primary
   document and every resolved earnings-exhibit path into the
   cache-forever `data/raw/documents/` cache, parses nothing, so F3 runs
   at 0 GETs. Update the module docstring deliberately.
3. **EX-99 selection audit** (spec §4.4): failures counted into
   `universe_validation_problems` as `earnings_doc_unresolved` (WARN per
   case, FATAL if >1% of earnings 8-Ks); `data/f2/ex99_selection_audit.csv`
   emitted (cik × section_type × confidence + first_seen_year +
   new_filer flag). The mandatory manual read happens at S6, not now —
   your job is to make the audit artifact exist.
4. **Distress events** (spec §4.5): `distress_events` table filled during
   enumeration for Forms 25/25-NSE/15-12B/15-12G/15-15D/15F-12B/15F-12G
   and 8-K item 1.03. Zero extra GETs.
5. **`edgar_client.py`**: the ONLY change is the optional
   `max_age_hours` passthrough exposed as `--cache-max-age-hours`
   (spec §4.3), default 24 unchanged.
6. **Tests** (spec §8.2 S3 block) in a NEW test file
   (`test_ingest_metadata_scale.py`), all offline, fixtures synthetic or
   sliced from cache (the CAT 2016 index fixture per spec — capture from
   `data/raw/` cache, never live).

## Parallel-run coordination (binding)

- Do NOT edit `F2_PROGRESS.md` — the main session flips statuses while
  S3/S4/S5 run in parallel.
- Do NOT touch `ingest_fundamentals.py`, `ingest_prices.py`,
  `price_client.py`, `test_ingest_fundamentals.py`,
  `test_ingest_prices.py` (owned by S4/S5, running now).
- Do NOT run the full pytest suite (siblings are editing their files
  concurrently — it would flake). Run YOUR tests + S2's
  `test_ingest_metadata_universe.py` + any suite for a file you changed
  (`test_edgar_client_companyfacts.py` etc.). The main session runs the
  full gate after all three stages land.
- Zero live network GETs expected (all measured inputs are cached). If
  you believe one is needed, stop and report why.

## Constraints

Lazy-elite (minimal diffs, no frameworks); no Anthropic API; E1 frozen
artifacts untouched; no long-running compute (the S6 runs are the main
session's job — nothing in S3 should execute a full network campaign).

## Deliverables (BOTH before returning)

1. Code + your targeted tests green (exact counts).
2. `data/f2/status/S3_metadata_documents.md` — completion report: files
   touched (one line what/why each), test counts, deviations from spec
   (explained; expected none), resume instructions if anything partial.
