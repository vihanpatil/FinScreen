# S2 completion report — membership adoption + window constants + validation redesign

**Stage:** S2. **Agent:** data-engineer (Opus). **Date:** 2026-08-24.
**Status: DONE.** Brief: `data/f2/status/S2_brief.md`.
**Scope implemented:** `data/f2/F2_SPEC.md` §1, §2, §3, plus the §8.1 row-2 and
§8.2 "S2" test block.

**Network: ZERO live GETs.** No `EdgarClient` request path executed at any
point (the two files in `data/raw/{filing_index,documents}/` dated 11:18 are
S1's CAT probe, predating this session's 11:28 start). No Anthropic API use.
Every measurement below was computed from files already on disk, through a
cache-only client that RAISES on a cache miss rather than fetching.

**E1's frozen record is untouched:** `data/universe.csv`,
`data/filings_metadata.db`, `data/labels.parquet` all carry their pre-session
mtimes (Aug 10 / Aug 18 / Aug 11). `data/filings_metadata_e2.db` does not
exist yet — S6 creates it.

---

## 1. Test counts (exact, full repo suite)

| | collected | passed | failed | skipped |
|---|---|---|---|---|
| **Before** (`python3 -m pytest -q`, this session's own baseline) | **399** | 394 | 0 | 5 |
| **After** | **444** | **439** | **0** | 5 |

+45 tests, all in the new `test_ingest_metadata_universe.py`, all offline.
**Nothing was deleted or weakened to make the suite pass.** The 5 skips are
the pre-existing ones (unchanged). `pyflakes` is clean on both changed
modules and the new test file.

The 399 baseline matches F2_SPEC §7's MEASURED figure exactly.

## 2. Checksum re-measurement (the STOP-and-report gate)

Re-hashed all 7 files myself before writing anything:

| file | sha256 | vs F2_SPEC §1.1 |
|---|---|---|
| hybrid136.csv | `e72ea90…c09c7` | **MATCH** |
| hybrid136.parquet | `8a026f2…a4f135` | **MATCH** |
| hybrid136_panel.csv | `15dd221…178e3d` | **MATCH** |
| hybrid136_panel.parquet | `14851a0…e53dd1` | **MATCH** |
| manual_exclusions.csv | `19299c2…f50bad` | **MATCH** |
| price_censoring_census.csv | `525d412…72a26e` | **MATCH** |
| price_censoring_census.parquet | `5a5e4a6…65a8d6` | **MATCH** |

All 7 match the spec's pinned values. No STOP condition. Independently
re-derived invariants: 244 distinct CIKs (176 core / 68 extension), 299
spells, 1,496 panel rows, exactly 136 members at each of 11 reconstitution
dates 2016-07-01…2026-07-01, 136 open spells, 0 CIKs with more than one
stratum/sector/name.

## 3. Files touched

**New**

| path | what / why |
|---|---|
| `data/universe_e2_candidates/hybrid136_checksums.json` | The §1.1 guard. 7 pinned sha256s + the invariants, re-measured this session. Separate from `option_record_checksums.json` so the frozen continuity5/broad8 option record is not disturbed. |
| `data/f2/validation_exceptions.csv` | The evidenced per-`(cik, check)` mechanism that replaces `--allow-incomplete-universe`. **Header only — no rows**, as §3.2 predicted, now confirmed empirically (§5 below). Carries the full rules-of-the-file comment block, modelled on `manual_exclusions.csv`. |
| `test_ingest_metadata_universe.py` | 45 offline tests: the checksum guard (incl. tamper + missing-file), the 244/299/136/11 pins, the coverage-window derivation, the fixed window constants, every §3.1 check's severity behaviour, the whole exceptions mechanism, and the §3.3 persistence regression. |

**Modified**

| path | what / why |
|---|---|
| `ingest_metadata.py` | The bulk of S2. Universe input switched from E1's 25-row ticker CSV to hybrid136 read in place, CIK-keyed, checksum-verified on every load (`verify_universe_checksums`, `load_membership`, `load_universe`). Four §2 window literals added and `lookback_cutoff`/`LOOKBACK_QUARTERS` deleted. `validate_universe()` redesigned per-company with the §3.1 thresholds, INFO severity, and `member_stopped_filing`. `--allow-incomplete-universe` + `parse_allow_incomplete_universe_arg` + `ALL_FATAL_CHECK_NAMES` deleted; `ValidationException` loader/applier/reporter added. `write_validation_problems()` now always called (the §3.3 bug). §1.4 schema: new `universe_membership` + `distress_events` tables, nullable/informational `ticker`, `cik`+`stage` on `universe_validation_problems`, `idx_filings_cik_date`. New `--db` (default `data/filings_metadata_e2.db`) and `--validation-exceptions`; E1's DB path is refused. Run summary now prints the observed max `filing_date` beside the constant (§2). |
| `ingest_fundamentals.py` | §3.4 only, deliberately minimal (S4 owns CONCEPTS). Imports `CORPUS_WINDOW_START/END` from `ingest_metadata` instead of re-declaring 2023/2026 literals; validation is CIK-keyed with `ticker` demoted to a display label; the coverage denominator is now the company's own `[coverage_start, coverage_end]` when the universe row carries them, falling back to the shared window otherwise (which is why all 12 pre-existing tests still pass untouched); `--db` added with the same E1-DB guard; validation-problems table gains `cik` and a nullable `ticker`. **`CONCEPTS`, `BANK_*`, and `KNOWN_MIDWINDOW_MIGRATIONS` are untouched — S4's job.** |

## 4. Spec §8.1 tripwire dispositions

- **Row 2** (`20 <= len(df) <= 30`): removed. Replaced by
  `EXPECTED_MEMBER_CIKS = 244` enforced at load, plus pins on 299 spells /
  136 members per date / 11 dates. Two *behavioural* tests
  (`test_universe_size_range_bound_is_replaced_by_an_exact_pin`,
  `test_wrong_spell_count_refuses_to_load`) prove a wrong-size table refuses
  to load, rather than grepping the source.
- **Row 4** (`test_diagnose.py::test_universe_csv_tickers_match_features_parquet_tickers`,
  `assert len(universe_df) == 25`): **deliberately left alone**, per the spec.
  It guards E1's frozen artifacts, which E2 does not rebuild. A future reader
  should not "fix" it.
- **Row 1** (`test_ingest_prices.py::test_load_universe_returns_all_25_tickers`)
  still passes and is **untouched** — `ingest_prices.py` still has its own
  `load_universe()` reading E1's `universe.csv`. That is S5's re-pin (§6.1),
  not S2's.
- **Row 3** (`test_ingest_fundamentals.py`, 12 tests): all still pass
  unchanged. They are S4's re-pin.

## 5. What was MEASURED this session (cache-only, no network)

Ran the redesigned `validate_universe()` over all 244 real members:
**34 findings — 0 FATAL, 5 WARN, 29 INFO.**

| check | result |
|---|---|
| `entity_resolves` | 0 |
| `history_reaches_cutoff` | **0** (matches F2_SPEC §3.1's "expected to fire on nothing") |
| `plausible_filing_counts` | **0** |
| `no_large_filing_gap` | 5 WARN across **4** members (PepsiCo 139 d and 136 d; Gen Digital 266 d; Kraft Heinz 217 d; Discover 145 d); **0 FATAL** |
| `recent_activity_10k_10q` | **0** (no current member is stale) |
| `member_stopped_filing` | **29 INFO** — exactly F1's independently derived 29 delisting-censored members |
| `recent_activity_any_form` | 0 (max current-member staleness 48 d vs an 80 d threshold) |
| `cik_map_agreement` | **0 contradictions** across 244 members (matches §3.1) |

**This is the empirical confirmation that `validation_exceptions.csv` can
legitimately ship empty**, and that S6 segment 1 should hard-fail on nothing.

## 6. Deviations from spec — none in substance; four clarifications recorded

None of these changes a ratified ruling, a threshold, or a formula. Each is a
place where the spec was silent or its prose disagreed with the artifact, and
each was resolved by re-measurement rather than assumption.

1. **`member_to` is EXCLUSIVE, not inclusive.** F2_SPEC §1.2 describes it as
   "last reconstitution date"; the artifact says otherwise. Verified on all
   299 spells: `len([d for d in recon_dates if member_from <= d < member_to])`
   equals each spell's own `n_reconstitutions`, and the spells reproduce F1's
   panel membership set **exactly at all 11 dates** (PG's 2016-07-01 →
   2020-07-01 spell has `n_reconstitutions=4` and PG is absent from the
   2020-07-01 panel). The §1.2 *formula* is implemented verbatim
   (`min(CORPUS_WINDOW_END, member_to + 400 d)`), which makes `coverage_end`
   about one year more generous than the prose implies — strictly
   conservative (a superset window), and membership itself is still joined
   from `universe_membership` downstream, never inferred from the window.
   Documented in `load_membership()`'s docstring and pinned by
   `test_spells_reproduce_the_panel_membership_exactly`.

2. **`plausible_filing_counts` needed its denominator defined.** §3.1 fixes
   the thresholds (3.5 FATAL / 3.9 WARN) and quotes a MEASURED distribution
   (min 3.91, p5 4.04, median 4.07, max 4.51) but does not say what the rate
   is divided by. I measured both readings:
   - denominator = **full coverage-window length** → min **1.61**, p5 2.95,
     median 4.03, max 4.20, with **19 members below the 3.5 FATAL floor** —
     every one of them a delisted name whose window carries a 400-day tail in
     which an acquired company files nothing. That contradicts the spec's own
     distribution AND §3.2's "expected initial contents: empty" AND
     EXPANSION_PLAN §3.6's "delisting exits are expected states".
   - denominator = **coverage_start → the company's last in-window periodic
     filing** → min **4.01**, p5 4.05, median 4.08, max 4.53, **0 members
     below either band** — reproducing the spec's quoted distribution to
     within definitional rounding.
   Implemented the second. Thresholds unchanged. Rationale is written into
   the constant's comment: this check exists to catch a hole in the middle
   (a truncated fetch), not to re-flag a delisting, which
   `member_stopped_filing` already reports. Pinned by
   `test_delisted_member_rate_is_measured_over_its_filed_span_not_its_window`.

3. **`no_large_filing_gap`: 5 findings across 4 members, not 5 members.**
   §3.1 names 5 members >135 d including Autodesk at 189 d. Measured
   in-window — which is what the same table's E2 rule mandates ("gaps
   measured only *inside* the coverage window") — Autodesk's 189-day gap
   falls **outside** its 2019-07-02…2023-08-05 coverage window, and PepsiCo
   has two qualifying gaps. So: 5 WARN findings, 4 distinct members, p99
   142 d (not 170), max 266 d (matches). The FATAL arm is 0 either way, so
   nothing about the design changes. Recorded in the constant's comment.

4. **`recent_activity_10k_10q` threshold.** §3.1's table does not restate a
   number (implying E1's 135 stands) while its rationale cell cites a 200-day
   measurement. I kept **135**, having established the choice is empirically
   inert: across thresholds 135/150/180/200/250 the counts are identical —
   **0 current members fire at any of them** (max current-member staleness is
   104 days) and **29 former members fire at all of them**. Keeping E1's
   constant means one fewer unexplained number.

Two smaller implementation notes, flagged so nobody reads them as drift:

- §1.3 writes `assert len(df) == 244`; implemented as an explicit
  `raise ValueError` with the spec's own "refuse to proceed silently on a
  scope change" message. Same pin, strictly stronger (survives `python -O`),
  and it is E1's existing idiom in the same function.
- §2 says nothing derives from `date.today()`. `date.today()` is **called
  exactly once**, as the `run_date` provenance stamp on the
  validation-problems rows — no window, cutoff, threshold, or filter derives
  from it, so a re-run on a different day produces an identical corpus and
  identical findings. `test_nothing_but_the_run_stamp_calls_today` pins this
  with an AST walk (so prose about E1's deleted behaviour can't satisfy it).

## 7. Deliberately NOT done (deferred, with reasons)

- **§3.3 second bullet — the doubled `get_effective_recent()` parse.** Spec
  marks it optional ("only if S3 measures it as material"); the brief says
  "only if trivially clean". It is not trivially clean: threading the fetched
  dict through changes `validate_universe()`'s contract for a saving that has
  not been measured. Left for S3 **with a measurement first**. Note the cost
  is parse-time only — it is 0 extra GETs.
- **Everything S3/S4/S5 owns**: `--stage`, distress-event extraction (the
  table exists and is empty), the EX-99 audit + `earnings_doc_unresolved`
  emission (the check name is registered in `FATAL_CHECK_NAMES` so S3 only
  has to emit), `CONCEPT_FAMILIES` + the alias classifier, the price ticker
  map, `--cache-max-age-hours`.
- **Docs.** `INGESTION_NOTES.md` still describes `--allow-incomplete-universe`
  as live. It is an audit-trail doc (HANDOFF §2's preserved set), so it was
  not rewritten; flagging it here so the F2 report or S7 can decide.

## 8. Interface changes S3/S4/S5 must know

- `load_universe() -> DataFrame[cik, name, sector, stratum, coverage_start,
  coverage_end, is_current_member]` (244 rows, **no `ticker` column**);
  `load_membership() -> DataFrame` (299 spells). Both verify checksums on
  every call; pass `verify=False` only in a test that has already verified.
- `extract_target_filings(recent, start, end)` — signature changed (was
  `(recent, ticker, cutoff)`); returned rows no longer carry `ticker`, and
  the **end bound is now enforced**.
- `ValidationProblem(cik, check, severity, message, ticker=None,
  stage="metadata")` — cik-first, `ticker` optional, severity now includes
  `"INFO"`. `write_validation_problems(conn, problems, run_date, stage=...)`.
- `validate_universe(client, universe, force_refresh=False)` — the `cutoff`
  and `today` parameters are gone; both come from the module constants and
  the per-company window.
- `select_earnings_document(..., ticker=...)` is unchanged but now receives
  `f"CIK {cik}"` as a display label. S3 may want to rename that parameter.
- `run(force_refresh=False, db_path=DB_PATH, exceptions_path=...)` in both
  `ingest_metadata` and (as `run(force_refresh, db_path)`)
  `ingest_fundamentals`; both refuse `data/filings_metadata.db`.

## 9. Resume instructions

**Nothing is left partial.** S2 is complete and the suite is green. To
re-verify from scratch:

```bash
cd /Users/vihanpatil/personal/projects/FinScreen
python3 -m pytest -q                                  # expect 439 passed / 5 skipped
python3 -m pytest test_ingest_metadata_universe.py -v  # the 45 S2 tests
python3 ingest_metadata.py --help                      # no --allow-incomplete-universe
```

To re-derive §5's real-data numbers without touching the network, re-run
`validate_universe()` with a client that reads `data/raw/submissions/`
directly and raises on a cache miss (the pattern is described in §5; it is
~30 lines and was kept out of the repo deliberately — it is a measurement
harness, not pipeline code).

**One operational note for S6:** `data/raw/submissions/` is currently ~84 h
old, i.e. past the 24 h TTL. Segment 1 will therefore legitimately re-fetch
244 submissions documents plus their pagination chunks (~0.5 GB, ~10 min)
before doing anything else. That is F2_SPEC §4.3's documented behaviour, not
a fault — `--cache-max-age-hours` (S3) is the lever if a cheaper re-run is
ever wanted.
