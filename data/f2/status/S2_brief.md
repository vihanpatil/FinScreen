# S2 brief — membership adoption + windows + validation redesign (issued 2026-08-24)

Agent: data-engineer (Opus). If S2 shows IN FLIGHT in `F2_PROGRESS.md`
with no `S2_membership.md` completion report beside this file, the agent
died — check `git status`/`git diff` for partial edits, then relaunch with
this brief verbatim (the spec defines the target state, so a relaunch can
finish partial work rather than restarting it).

## Task

Implement F2 stage S2 exactly as specified in `data/f2/F2_SPEC.md`
sections **1, 2, 3** (which the main session ratified 2026-08-24 —
`F2_PROGRESS.md` §5), with the tests in spec §8.1–8.2 (S2 block). The
spec is the plan of record; where the spec and code reality conflict,
stop and report rather than improvising.

## Read first

1. `data/f2/F2_SPEC.md` §1–§3, §8, §9.1 — the ratified spec.
2. `F2_PROGRESS.md` — ledger discipline + the ratification entry.
3. `HANDOFF.md` §4 + §7 (hard rules), `EXPANSION_PLAN.md` §3.6.
4. `ingest_metadata.py`, `ingest_fundamentals.py` (validation parts),
   `test_ingest_fundamentals.py`, and the existing test suites you will
   extend.

## Scope (all from the spec — this list is a checklist, not a redefinition)

1. **Spec §1**: `data/universe_e2_candidates/hybrid136_checksums.json`
   (pin the hashes listed in spec §1.1 — re-measure them yourself first;
   a mismatch with the spec's values is a STOP-and-report finding);
   `load_universe()` / `load_membership()` per §1.3 (CIK-keyed, checksum
   verification on every load, `== 244` pin, `coverage_start`/
   `coverage_end`/`is_current_member` derivation per §1.2); SQLite schema
   changes per §1.4 targeting the NEW `data/filings_metadata_e2.db`
   (default of a new `--db` argument; E1's DB is never touched).
2. **Spec §2**: the four window constants as module-level literals in
   `ingest_metadata.py` (`CORPUS_WINDOW_START = 2015-07-01`,
   `CORPUS_WINDOW_END = 2026-08-31`); delete `lookback_cutoff`-style
   today()-derived logic; nothing anywhere derives from `date.today()`.
3. **Spec §3**: per-company-window validation with the re-derived
   thresholds in §3.1's table; delete `--allow-incomplete-universe`
   and implement `data/f2/validation_exceptions.csv` semantics (§3.2,
   initial file = header only, expected empty); fix the
   `write_validation_problems()` gating bug (§3.3 first bullet — always
   persist; bug confirmed at `ingest_metadata.py:863`); §3.3's second
   bullet (double parse) only if trivially clean; §3.4 fundamentals-side
   validation re-scoping (imports the §2 constants — keep this edit
   minimal since S4 will rework the same file's CONCEPTS separately).
4. **Tests** (spec §8.1 rows 2 and 4, §8.2 S2 block), all offline. Run
   the FULL repo suite; baseline 399 collected (S1 measurement). Every
   pre-existing test must pass or be re-pinned per spec §8.1 — nothing
   deleted to make the suite pass. `test_diagnose.py`'s 25-ticker pin is
   deliberately left alone (it guards E1's frozen artifacts) — note it in
   your report.

## Out of scope for S2

Enumeration/`--stage` changes, distress events, EX-99 audit (S3);
CONCEPT_FAMILIES + classifier (S4); price ticker map (S5); any network
GET beyond what cached data already provides (S2 should need ZERO live
GETs — if you believe one is needed, stop and report why).

## Constraints

- Lazy-elite (owner, 2026-08-24): minimal diffs, extend existing
  functions, no new frameworks, simple readable core logic.
- No Anthropic API calls. E1 frozen artifacts untouched
  (`data/filings_metadata.db`, `data/universe.csv`, labels, splits).
- Long-running work (>~15 min of compute) does not belong in S2; if you
  hit something that big, stop and report.

## Deliverables (write BOTH before returning)

1. Code + tests, full suite green (report exact counts: collected /
   passed / failed / skipped, before and after).
2. `data/f2/status/S2_membership.md` — completion report: files touched
   with a one-line what/why each, checksum re-measurement result, test
   counts, deviations from spec (should be none — any deviation is
   explained), and exact resume instructions if anything is left
   partial.
