# P2 completion report — F3 extraction runs

**Stage:** P2. **Executor:** main session (HANDOFF §4 — background
chain, no agent). **Date:** 2026-08-27. **Status: DONE.**
Owner go: HANDOFF §3 2026-08-27 entry; run under the overnight-autonomy
grant (item 5). Commands exactly as staged in `P1_impl.md` §6, run
sequentially, each as a main-session background task.

## Invariants — all held

| invariant | result |
|---|---|
| `cache_miss` | **0 on every shard and every run** (fatal-stop rule never triggered) |
| network GETs | **0** on all 4 runs ("cache-only by construction" printed every time) |
| merge completeness | `merge.complete: true`; shards found = expected: earnings 8/8, 10-K 10/10, 10-Q 16/16 |
| E1 frozen artifacts | untouched (extract.py refuses them by name; nothing written outside `data/f3/` + `data/filings_e2.parquet`) |
| kills / resumes | **none needed** — all 4 runs completed on their first invocation |

## Timeline (2026-08-27, local)

| run | wall clock | result |
|---|---|---|
| `--segment earnings` | ~10:12 → 10:31 (~19 min) | 10,567 filings → 10,567 attempts / 10,555 sections; OK 8,675 / FLAGGED 1,880 / FAIL 12 |
| `--segment 10-K` | ~10:32 → 11:29 (~57 min) | 2,445 filings → 4,890 attempts / 4,646 sections; FAIL 244 |
| `--segment 10-Q` | ~11:30 → 12:52 (~82 min) | 7,509 filings → 15,018 attempts / 13,699 sections; FAIL 540*, EXPECTED_ABSENT 779 |
| `--merge` | ~12:53 → 12:56 (~3 min) | wrote corpus + 5 audit artifacts |

*Per-status totals by segment are derivable from `extraction_audit.parquet`;
the segment rows above are the shard-log sums (see `data/f3/p2_*.log`).

## Merged totals (from `run_manifest.json`, last run entry)

- **30,475 attempts → 28,900 sections** (P0's corrected scale: ≈28,840 —
  within 0.2%).
- Status: **OK 25,245 (87.3%) / FLAGGED 3,655 (12.6%) / FAIL 796 /
  EXPECTED_ABSENT 779** (FAIL+EXPECTED_ABSENT rows are attempts that
  produced no section; they are in the audit artifact, not the corpus).
- Corpus: `data/filings_e2.parquet` (620.9 MB, 28,900 rows).
- Audit artifacts (all in `data/f3/`): `extraction_audit.parquet`
  (30,475 rows), `extraction_failures.csv`, `per_filer_rollup.csv`,
  `population_gate.csv`, `length_distribution.csv`, `run_manifest.json`
  (4 run entries; `extract.py` sha `b9acceea…` = P1's shipped sha,
  git rev `b6546bf8`, E2 DB sha `61dcefaa…`).

## Handed to P3 (per spec, decided nowhere here)

Per-filer failure triage over the 796 FAILs + gate verdicts +
spot-reads per the pre-committed protocol + floor recalibration from
`length_distribution.csv` + the F4-scale re-derivation + the P1-named
censuses (D2 incorporated-by-reference class, mojibake class, Simon
combined-book class, Tesla thin-P&D false-alarm class).
