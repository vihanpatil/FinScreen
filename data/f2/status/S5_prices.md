# S5 completion report — prices at scale (CIK-verified ticker resolution + fetch changes)

**Stage:** S5. **Agent:** data-engineer (Opus). **Date:** 2026-08-24.
**Status: DONE.** Brief: `data/f2/status/S5_brief.md`.
**Scope implemented:** `data/f2/F2_SPEC.md` §6.1–§6.4, the §8.2 "S5" test block,
and the §8.1 row-1 re-pin of `test_ingest_prices.py`.

> **READ §7, §8 AND §9 FIRST.** §9 (S7 finding B3) **retracts a safety property
> §7 and the override file asserted**: a symbol that bulk-maps to a different
> CIK is the APC trap *signature*, not an automatic disqualifier — XOM is that
> shape, and it is now admitted only via a ratified `successor_reorg` marker, a
> series-continuity check (measured: 14,282 rows, 1970→2026, max gap 7 days) and
> a standing per-run WARN. **No count moved.**
> §1–§6 record the state at
> 12:22, before S6 segment 1's TTL refresh. §7 implements the AEP ruling
> (rule-level 212/32 → **211/33**, overrides 1 → **2**; fetch pair unchanged).
> §8 implements the EA ruling from segment 4's real run: there are now **two
> censoring numbers and they are never conflated** — the **FETCH pair 213
> fetched / 31 unfetchable (27 core / 4 extension)** and the **OPERATIVE
> no-usable-prices pair 32 (28 core / 4 extension)**, which is the one every E2
> result quotes.

**Network: ZERO live GETs — no Yahoo, no Stooq, no EDGAR.** No request path in
any file I ran was executed: the real-data measurements came from a cache-only
client stub that RAISES on a cache miss (kept in scratch, not the repo — it is a
measurement harness, not pipeline code, same discipline as S2), and every test
either builds synthetic dicts or reads `data/raw/` through the same
raise-on-miss stub. `python3 ingest_prices.py` was never run without `--help`.
The 213-ticker fetch is S6's job, main session only. No Anthropic API use.

**E1's frozen record is untouched:** `data/prices.parquet` is never written by
this code — E2's output path is `data/prices_e2.parquet`, and `main()` refuses
`--output data/prices.parquet` with exit code 2 (pinned by a test).
`data/universe.csv` is read only by a test, as E1's regression record.

**Parallel-run coordination honoured:** `F2_PROGRESS.md` not edited;
`ingest_metadata.py` / `edgar_client.py` / `ingest_fundamentals.py` and their
test files not touched (imported read-only); only `test_ingest_prices.py` and
`test_price_client.py` were run, never the full suite.

---

## 1. Measured resolution counts vs the spec's expectations

Ran the §6.1 rule, verbatim as specified, over all 244 hybrid136 members from
the cached submissions. **Every number matches the spec exactly — no STOP
condition.**

| quantity | spec §6.1/§6.2 | MEASURED here | |
|---|---|---|---|
| members | 244 | **244** | match |
| CIK-verified ticker chosen | 212 | **212** | match |
| censored by the rule alone | 32 | **32** | match |
| contradicted by the bulk map | 0 | **0** | match |
| of the censored: no ticker at all | 31 | **31** | match |
| of the censored: preferreds only | 1 (CIK 30554, EIDP) | **1** (CIK 30554, `CTA-PB`,`CTA-PA`) | match |
| overrides applied | 1 (34088 → XOM) | **1** | match |
| **fetchable** | **213** | **213** | match |
| **censored** | **31 (27 core / 4 extension)** | **31 (27 core / 4 extension)** | match |
| E1 regression | all 25 CIK↔ticker pairs, XOM via override | **25/25**, XOM `status=override` | match |

Census reconciliation (§6.3) against F1's `price_censoring_census.parquet`
(247 rows, checksum-verified through `load_universe()`):

- F1 no-current-ticker members **inside the 244-member universe: 31**.
- E2 censored: **31**. Delta = **−{34088} (overridden in), +{30554} (preferreds
  only)** — **exactly the pre-registration, nothing else**.
- The 3 census CIKs outside the universe (1616314, 1690881, 1853513) are F1's
  three undated `manual_exclusions.csv` rows; reported, not treated as a delta.

Reconciles cleanly with F1's headline "29": of the 31 censored, **29 have
stopped filing** (the delisting-censored population F1 counted) and 2 are still
filing — CIK 29915 (Dow Chemical, deliberately censored) and CIK 30554 (EIDP,
no public common equity).

**Extra integrity measurements I ran that the spec did not ask for** (all
cache-only, all clean):

- **213 fetchable → 213 distinct tickers.** No two member CIKs resolve to the
  same symbol.
- **All 213 fetchable CIKs are still-filing registrants**, most recent periodic
  filing between 2026-05-19 and 2026-08-20. So no fetchable member is a dead
  registrant carrying a stale symbol — the APC/EMC reassignment failure mode is
  structurally absent from this fetch list, not merely unobserved.
- Only **2** fetchable symbols are absent from `company_tickers.json` (AEP 4904,
  EA 712515) — the exact pair the spec names as the reason absence must never
  censor.
- 41 members carry multiple candidates; EDGAR's own ordering puts the common
  class first in all 41 (`BA` over `BA-PA`, `GOOGL` over `GOOG`, `BRK-B` over
  `BRK-A`, `JPM` over 8 preferreds…). No hand-picking was needed anywhere.
- 77 of the 213 fetchable members are FORMER members (still listed, out of the
  top-K) — expected, and the reason `ends_early` is not FATAL for them.

## 2. Files touched

**New**

| path | what / why |
|---|---|
| `data/f2/price_ticker_overrides.csv` | The §6.2 mechanism. **Exactly one row: 34088 → XOM**, with primary-source evidence measured this session (empty `tickers[]`/`exchanges[]` on a still-filing registrant; bulk map points XOM at CIK 2115436 "ExxonMobil Holdings Corp"; E1 already fetched and validated XOM under this CIK). Carries the full rules-of-the-file comment block modelled on `manual_exclusions.csv`, including why CIK 29915 is deliberately absent. |
| `data/f2/price_ticker_map.csv` | The §6.3 output: 244 rows, spec's exact columns (`cik,name,stratum,chosen_ticker,all_candidates,status,reason`). Regenerated byte-identically on a second run. |

**Modified**

| path | what / why |
|---|---|
| `ingest_prices.py` | The bulk of S5. `load_universe()` (E1's 25-ticker CSV read) **deleted** and replaced by CIK-verified resolution: `NON_COMMON`, `resolve_ticker()`, `resolve_universe_tickers()`, `load_ticker_overrides()` (load-time validation), `load_bulk_ticker_map()` (contradiction detector only), `write_ticker_map()`, `reconcile_censoring_census()`, `resolution_counts()`, `resolution_findings()`, `print_resolution_report()`. Fetch side: parquet gains `cik` (join key) and keeps `ticker`; output path `data/prices_e2.parquet` with E1's path refused; `--price-source {yahoo,stooq-first}` default `yahoo`; `meta.symbol`/`instrumentType` tripwire (`meta_tripwire_issues`); `validate_prices()` rewritten per-company with `missing_entirely` FATAL only for a resolved ticker and INFO/WARN dispositions for former members; `Issue` gains `cik`; `INFO` severity added to the report; `build_parser()` extracted; `--resolve-only` and (unused) `--db` added. |
| `price_client.py` | 33 lines. `get_daily_bars(..., source="stooq-first"\|"yahoo")` — default unchanged so F1's `build_universe_e2.py` call sites keep their behaviour; the Stooq path is untouched and one flag away. `self.last_yahoo_meta` captures the response `meta` block (None on the Stooq path) so the tripwire needs no payload plumbing. |
| `test_ingest_prices.py` | Rewritten: **11 → 42 test functions (48 collected)**. |
| `test_price_client.py` | **+4 tests (16 → 20)**: yahoo-direct touches no Stooq URL and writes no Stooq cache file, meta captured, stooq-first still works and leaves `last_yahoo_meta` None, unknown source raises. |

## 3. Test counts (targeted files only, as the brief requires)

| file | before | after | result |
|---|---|---|---|
| `test_ingest_prices.py` | 11 | **48 collected** (42 functions, one parametrized ×7) | **48 passed** |
| `test_price_client.py` | 16 | **20** | **20 passed** |
| **total** | 27 | **68** | **68 passed, 0 failed, 0 skipped** |

`pyflakes` clean on all four changed files. The one warning is pre-existing
(numpy quantile over a frame containing an injected negative close).

Every §8.2 S5 bullet is covered, plus the §8.1 re-pin:

- preferreds-only → censored; **all 7** non-common suffixes parametrized;
  `BRK-B`/`BRK-A` → `BRK-B`; bulk-map contradiction → censored; bulk-map
  **absence** → still resolved.
- The APC/EMC trap directly: a dead member is censored and the reassigned
  symbol is unreachable, because candidates only ever come from the member's own
  submissions.
- Override file: resolves 34088 and only 34088; a second undocumented row, an
  unratified CIK (even fully evidenced), sub-floor evidence, a duplicate row and
  a **missing file** each fail at load; a row naming CIK 29915 is refused by
  name; and 29915 stays censored even in a synthetic world where EDGAR
  publishes `DOW` for it.
- `missing_entirely` is not FATAL for a censored CIK (it never reaches
  `validate_prices()` at all) and the censored count + names appear in the
  report.
- Yahoo `meta.symbol` and `instrumentType` mismatches → WARN naming the CIK;
  a matching meta and the Stooq path are silent.
- §8.1 row 1: `test_load_universe_returns_all_25_tickers` is replaced by
  `test_price_ticker_map_resolves_212_and_censors_32` (all §6.1 counts) plus
  `test_all_25_e1_cik_ticker_pairs_reproduce`. These read the real
  `data/raw/` cache through the raise-on-miss stub and **skip loudly** if the
  cache is absent (`data/raw/` is gitignored) rather than fetching it.

## 4. Deviations from spec — none in substance; six choices recorded

None changes a ratified ruling, a threshold, or a count. Each is a place the
spec was silent, resolved by measurement or by the least-surprising option.

1. **Output path.** §6 names no E2 parquet path; used `data/prices_e2.parquet`
   by the §1.4 `filings_metadata_e2.db` precedent, and made E1's path an
   explicit refusal (exit 2) rather than a comment.
2. **Count deviations are FATAL findings, not a hard stop.** A measured count
   other than 212/1/213/31/27/4, or an unregistered census delta, is emitted as
   a FATAL `resolution_count_deviation` / `census_delta_unexpected` issue
   (non-zero exit, named CIKs) while the fetch still proceeds — the bars are
   still valid data and re-paying for them buys nothing, but nobody can consume
   the run without seeing the deviation. Never silently adopted.
3. **Validation windows are now per-company.** E1 validated coverage over a
   fixed 2022-12-01 window, which on E2's 11-year × 244-member table would
   manufacture FATALs for every former member. Each member is now validated over
   its own `[coverage_start, coverage_end]` (S2's derivation, imported), and
   coverage gaps count only **interior** holes, so a legitimate listing date or
   delisting is not reported as thousands of missing days. `ends_early` and
   `missing_in_window` are FATAL for a **current** member and INFO/WARN for a
   former one — the same INFO disposition S2 gave `member_stopped_filing`.
4. **One check the spec did not ask for:** `starts_after_coverage_start` (WARN)
   — a series that begins long after the member's window opens is the exact
   shape a reassigned symbol would have (ARKO's history starts 2020; Anadarko
   was a member from 2016). It is the runtime tripwire for the F1 trap, ~8 lines.
5. **`--db` is accepted and unused.** §7's runbook shows
   `ingest_prices.py --db data/filings_metadata_e2.db`; price ingestion writes
   no DB rows, so the flag is accepted (documented as such in `--help`) so the
   runbook command cannot die on an unrecognised argument. Drop it from the
   runbook if the main session prefers.
6. **`--resolve-only`** added (4 lines): resolve, write the map + reconciliation,
   fetch nothing. Useful as an S6 pre-flight.

**Not done, deliberately:** `data/PRICES_NOTES.md` §1 still describes E1's
Stooq-first behaviour and the 25-ticker run. It is the canonical, owner-flagged
write-up of the price-source question, and the default change is item 8 on
§9.1's ruling list flagged for **owner visibility** — so it is surfaced here and
in the F2 report rather than quietly rewritten by me. Same for `INGESTION_NOTES.md`.

## 5. What S6 needs to know

- Command: `python3 ingest_prices.py` (defaults: `--price-source yahoo`,
  `--output data/prices_e2.parquet`, `--ticker-map data/f2/price_ticker_map.csv`).
  Segment 4's **213 Yahoo GETs** matches the runbook; resolution additionally
  reads 244 cached submissions + the bulk map, which cost **0 GETs** if segment 1
  refreshed them inside the 24 h TTL, and are the only EDGAR traffic here.
- Idempotent and cache-first: `PriceClient` caches under
  `data/raw/prices/yahoo/` with a 20 h TTL, so a killed-and-rerun segment 4
  re-fetches nothing within the day; the parquet is rebuilt from cache each run.
- Expect the run report to print, in order: the resolution block (213/31 with
  the pinned expectation beside it), the override row (APPLIED) and the 29915
  ruling, all 31 censored members by name, the census reconciliation, the
  per-member coverage summary, then the validation report. Exit code is 1 if any
  FATAL fires.
- Two visibility items for the F2 report, unchanged from §9.2: the
  **price-source default** (Yahoo, ratification named Stooq by example) and the
  **censoring pair — 31 member CIKs with no price series at all, 27 core / 4
  extension** — which must accompany every E2 result, never as a union.
- F5/G3 unchanged: no benchmark is built here. `print_resolution_report()`
  prints the standing note that the universe-average benchmark must be computed
  over membership-dated, price-resolved members and that 31 members contribute
  none.

## 6. Resume instructions

**Nothing is partial.** To re-verify from scratch, offline:

```bash
cd /Users/vihanpatil/personal/projects/FinScreen
python3 -m pytest test_ingest_prices.py test_price_client.py -q   # expect 68 passed
python3 ingest_prices.py --help                                   # --price-source defaults to yahoo
head -1 data/f2/price_ticker_map.csv                              # cik,name,stratum,chosen_ticker,...
```

To re-derive §1's real-data numbers without touching the network, run
`resolve_universe_tickers()` with a client stub whose `get_submissions()` /
`get_company_tickers()` read `data/raw/` and raise on a cache miss — the same
`_CacheOnlyEdgar` class that lives at the top of `test_ingest_prices.py` (~15
lines; the fixture `real_resolutions` does exactly this).

---

## 7. FOLLOW-UP 2026-08-24 (later) — the AEP wobble, second override, wobble WARN

**Trigger.** During S6 segment 1's TTL refresh, EDGAR's `submissions.json` for
**CIK 4904 (AMERICAN ELECTRIC POWER CO INC)** dropped to empty
`tickers[]`/`exchanges[]`. The submissions-only rule censored it and **two of
this stage's count tests failed against the refreshed cache — the tripwire
working as designed, not a regression.** The main session probed EDGAR live
(1 GET, main session, not me), confirmed it has not self-healed, and **RULED**
(F2_PROGRESS.md §5, 2026-08-24): AEP gets the second evidenced override, plus a
new WARN for wobbles of this shape. Everything below is that ruling implemented;
still **zero live GETs from me** — all re-measurement is cache-only against the
post-segment-1 cache (submissions mtimes 12:56–15:28, `company_tickers.json`
12:56).

**Counts, re-measured on the refreshed cache**

| | pre-refresh (§1, 12:22) | post-refresh | |
|---|---|---|---|
| resolved by the rule alone | 212 | **211** | AEP flipped |
| censored by the rule alone | 32 | **33** | AEP flipped |
| overrides applied | 1 | **2** (XOM, AEP) | |
| **fetchable** | 213 | **213** | **unchanged** |
| **censored** | 31 (27 core / 4 extension) | **31 (27 core / 4 extension)** | **unchanged** |
| census delta vs F1 | −{34088}, +{30554} | **identical, still clean** | |

**The AEP-shaped measurement the main session asked for.** Of the 33
rule-censored CIKs, **exactly two** have a bulk-map symbol pointing at their own
CIK:

| cik | name | stratum | submissions `tickers[]` | bulk symbols → same cik | live filer? | disposition |
|---|---|---|---|---|---|---|
| 4904 | AMERICAN ELECTRIC POWER CO INC | extension | *(empty)* | `AEP` (admissible) | yes, last periodic 2026-07-30 | **override added** (ruled) |
| 30554 | EIDP, Inc. | extension | `CTA-PB,CTA-PA` | `CTA-PA`, `CTA-PB` (both non-common) | yes, last periodic 2026-07-31 | **stays censored** — correct, and pre-registered in §6.3 |

**EIDP is the "besides AEP, a live filer" case, reported not actioned.** It is
wobble-shaped only by the mechanical predicate: every symbol SEC maps to it is a
preferred series (`CTA-PA`/`CTA-PB`), and EIDP has had no public common equity
since it became a DowDuPont subsidiary (F1's `manual_exclusions.csv` row, same
evidence). Overriding it would fetch a preferred-share series into an
equity-return backtest, so **no override was added** — it is WARNed on every run
and counted in the 31. No third CIK of this shape exists.

**Changes made**

| path | change |
|---|---|
| `data/f2/price_ticker_overrides.csv` | Second row `4904,AEP,upstream_ticker_wobble,…` with the three evidence strands (bulk-map agreement pointing at OUR cik; this stage's own 12:22 pre-refresh `price_ticker_map.csv` record; current listing + still-filing status). Header comment gains a "two case classes" block. **§9 corrects that block**: it claimed a symbol mapping to a different CIK "is still censored, never overridden", which was false about the XOM row already on file. |
| `ingest_prices.py` | `RATIFIED_OVERRIDE_CIKS = {34088, 4904}`; `EXPECTED_RESOLVED = 211`, `EXPECTED_OVERRIDES_APPLIED = 2` (fetchable/censored pins untouched); `TickerResolution` gains `rule_status` + `bulk_symbols`; new `bulk_symbols_by_cik()` and `ticker_wobble_issues()` emitting the `submissions_ticker_missing_but_bulk_has` WARN, wired into both the `--resolve-only` and the full run report; override reason prefix generalised from "successor-CIK override" to "evidenced override". |
| `data/f2/price_ticker_map.csv` | Regenerated against the refreshed cache: 211 resolved / 2 override / 31 censored; CIK 4904 now `status=override`. |
| `test_ingest_prices.py` | Re-pinned to 211/33 + 2 overrides + the unchanged 213/31/27/4; new tests for both wobble shapes, for "no auto-resolution without an override", for both overrides firing on the real universe, for exactly-two wobble-shaped real members, and for a **third** undocumented override row still being refused. |
| `data/f2/F2_SPEC.md` §11 | Amendment A3 (third entry; the first two are S3's), stating exactly which sentences of §6.1/§6.2/§6.3/§8.1 it supersedes and which rulings it leaves untouched. |

**Test counts after the follow-up:** `test_ingest_prices.py` **54 passed**
(was 48), `test_price_client.py` **20 passed** (unchanged) — **74 passed, 0
failed, 0 skipped**, pyflakes clean. Targeted files only; no full-suite run, no
`F2_PROGRESS.md` edit, no write to `data/filings_metadata_e2.db`.

**One correction to the follow-up brief, recorded rather than silently
adopted:** the brief cites "AEP's current NYSE listing". EDGAR's own
pre-wobble `exchanges[]`, as captured in F1's `price_censoring_census.parquet`,
says **Nasdaq** (`tickers=AEP, exchanges=Nasdaq, still_filing=True,
last_periodic=2026-07-30`). The evidence row records the measured value and
notes the discrepancy; nothing about the ruling depends on which exchange it is.

**Side note for the main session:** the two SEC files swapped roles across the
refresh. Pre-refresh, AEP was absent from `company_tickers.json` and present in
submissions; post-refresh the reverse. The only remaining
resolved-but-absent-from-the-bulk-map member is **EA (CIK 712515)** — so §6.1's
"absence never censors" asymmetry is still load-bearing for one live member, and
neither SEC file is authoritative on its own. That is the argument for keeping
the bulk map a veto-only input, unchanged.

*(Post-script, same day: that "one live member" is EA — and §8 is about EA for
an entirely unrelated reason. The bulk-map absence had nothing to do with it;
its symbol resolved from submissions correctly and the fetch succeeded.)*

---

## 8. FOLLOW-UP 2026-08-24 (later still) — EA, `resolved_no_coverage`, and two censoring numbers

**Trigger.** Segment 4's real run hit every S5 pin exactly (213 fetched / 31
unfetchable, reconciliation clean, 1,960,738 rows) **and** my
`missing_in_window` check fired on **EA (CIK 712515**, core/tech, member
2017-07 → 2021-07): Yahoo returned 6 rows, all 2026-07-17 → 2026-08-10,
flatlined at the ~$209.70 take-private price with volume 0, `firstTradeDate`
reset to 2026-07-17. Right company, purged history — EXPANSION_PLAN §2c's
outcome-censoring residual, real, for a **core** member. The main session
**RULED** (F2_PROGRESS.md §5): add `resolved_no_coverage`, report the two
numbers separately, and tie the case to `distress_events`. Implemented below.
**Zero live GETs; segment 4 was NOT re-run; `data/prices_e2.parquet` and
`data/filings_metadata_e2.db` were opened READ-ONLY** (the DB via
`file:…?mode=ro`). The only file rewritten is `data/f2/price_ticker_map.csv`.

### 8.1 EA sole-instance verification (measured from the written parquet)

Read `data/prices_e2.parquet` (1,960,738 rows / 213 CIKs) and counted, for each
fetched member, rows inside its own `[coverage_start, coverage_end]`:

| | |
|---|---|
| fetched members with **zero** in-window rows | **1 — EA (712515) only** |
| EA's series | 6 rows, 2026-07-17 → 2026-08-10, window 2015-07-02 → 2022-08-05 |
| next-smallest in-window count among the other 212 | **539** (LNG, HWM, EQT, CRH — short coverage windows, all genuinely covered) |

So it is not a threshold artefact: EA is isolated by a wide margin. Pinned as
`EXPECTED_NO_COVERAGE_CIKS = {712515}`, **two-sided** — a second such member is
a FATAL `unexpected_no_coverage_member` **naming it**, and EA regaining history
is a FATAL `expected_no_coverage_member_missing`.

### 8.2 The two numbers (never conflated)

| pair | value | what it answers | where it is authoritative |
|---|---|---|---|
| **FETCH** | **213 fetched / 31 unfetchable** (27 core / 4 extension) | did a CIK-verified symbol exist to ask for? | ingestion/runbook accounting |
| **OPERATIVE** | 212 usable / **32 with NO usable prices** (**28 core** / 4 extension) | does this member have prices inside the window it was a member? | **every E2 result, benchmark and stratified claim** |

32 = 31 unfetchable + 1 fetched-but-zero-coverage. Both are printed on every
run under the labels `FETCH pair` / `OPERATIVE pair`, with the pinned values
beside them; the §2c benchmark note now names the **operative** pair explicitly
("not the FETCH pair, which is an ingestion fact, not an analysis one"). The
§6.3 reconciliation block gained a dated addendum stating that it is a
FETCH-side comparison (F1's census asked about ticker resolvability) and that EA
is a new axis, not a census delta — the delta itself is still −{34088}/+{30554},
clean.

`price_ticker_map.csv` now carries `fetched` and `has_usable_prices` **as
columns**, so neither population can be inferred by accident from the other:
`status` counts are `resolved 210 / override 2 / resolved_no_coverage 1 /
censored 31`; `fetched` sums to 213; `has_usable_prices` to 212.

### 8.3 `distress_events` cross-check — §2c demonstrably covers this case

Read-only against `data/filings_metadata_e2.db`, EA has **2 rows**:

| form | filing_date | accession | event_kind |
|---|---|---|---|
| `25-NSE` | 2026-08-04 | `0001354457-26-000757` | `delisting_form_25_nse_exchange_filed` |
| `15-12G` | 2026-08-14 | `0001140361-26-032929` | `deregistration_form_15` |

(Corroborated, though not a `distress_events` kind: EA's 2026-08-04 8-K carries
items 1.01, 1.02, 2.01, 3.01, 3.03, 5.01 — the merger-completion set.) **No
visibility gap.** The check is now permanent: `no_coverage_distress_issues()`
emits an INFO citing these rows on every run, and a **WARN** if a no-coverage
member ever has *no* EDGAR-side explanation. This also makes `--db` honest — it
was accepted-and-unused before; it is now the read-only handle for this
cross-check.

### 8.4 Changes made

| path | change |
|---|---|
| `ingest_prices.py` | `TickerResolution` gains immutable `fetch_status` + `fetched` / `has_usable_prices` properties; new `apply_no_coverage_status()`, `distress_events_for()`, `no_coverage_distress_issues()`; `resolution_counts()` returns both pairs under unambiguous keys; `resolution_findings(..., coverage_applied=True)` pins the operative pair and the no-coverage identity; `print_resolution_report(..., coverage_applied=)` prints both pairs, the named no-coverage members, and the §6.3 addendum; `main()` re-writes the map and re-prints the report after the fetch, and `--resolve-only` classifies against an existing parquet read-only. |
| `data/f2/price_ticker_map.csv` | Regenerated read-only from cache + the existing parquet: EA is `resolved_no_coverage`, `fetched=True`, `has_usable_prices=False`, with the reason spelling out "0 of 6 rows … series spans 2026-07-17..2026-08-10". |
| `test_ingest_prices.py` | +15 tests: the flip and its non-firing case, both-pairs counts, report wording for both pairs (and "not determined yet" pre-fetch), map columns, the two-sided identity pins, the distress cross-check (rows / no rows / no DB), plus real-data pins for EA-sole-instance, both real pairs, and EA's real Form 25 + Form 15 rows. |
| `data/f2/F2_SPEC.md` §11 | Amendment **A4**. |

### 8.5 Test counts

`test_ingest_prices.py` **69 passed** (was 54), `test_price_client.py` **20
passed** — **89 passed, 0 failed, 0 skipped**, pyflakes clean. Two older
assertions were updated (not deleted) to the new FETCH-pair report wording.

### 8.6 For whoever writes the F2 report

Quote the **operative** pair — **32 members with no usable prices (28 core / 4
extension)** — wherever an E2 result, benchmark, or stratified claim appears,
and quote the **fetch** pair (213 / 31) only when describing ingestion. EA is
the concrete instance of the §2c residual: selection stayed survivorship-free,
but its *outcome* is censored, and no price vendor can fix that because the
history no longer exists to buy.

*(FYI noted, no action taken: the `meta.instrumentType='ETF'` tripwire on GLD
(SPDR Gold Trust, CIK 1222333) is a membership-level finding queued for the
owner. Its rows are untouched here and it is counted as an ordinary fetched
member in both pairs.)*

---

## 9. FOLLOW-UP 2026-08-24 (S7 red-team B3) — the successor-reorg guard, and a false safety property retracted

**What the red-team found, and it was right.** `company_tickers.json` maps
**`XOM` → CIK 2115436 "ExxonMobil Holdings Corp"** while the member is
**34088**, which is absent from the bulk map — **structurally the same shape as
the APC trap** (`APC` → 2080921 while Anadarko is 773910). Three defects
followed from that, all mine:

1. **A false safety property, asserted in my own words.** The override file's
   comment block said a symbol pointing at a *different* CIK "is still censored,
   never overridden" — directly above the row that does exactly that. The same
   sentence went into F2_SPEC amendment A3 and into `F2_INGESTION_REPORT.md`.
2. **No code enforced anything.** The override applied whenever the rule
   censored a member, *regardless of why* — including a bulk-map contradiction.
3. **The WARN fired on the wrong member.** `ticker_wobble_issues` skipped any
   CIK with no bulk symbols of its own; 34088 has none, so **XOM never WARNed**,
   while AEP — where the bulk map *agrees* with our CIK, the safe direction —
   WARNed every run.

I had also cited the weakest available evidence: a prior E1 decision, "still
filing", and F1's census. The one fact that actually corroborates the mapping —
an unbroken 56-year series — was neither cited nor checked.

**The corrected rule (now in code, in the CSV, and in F2_SPEC A10):**

> bulk-symbol-maps-elsewhere is the trap **SIGNATURE**, not a disqualifier by
> itself. An override over it requires (a) a ratified `successor_reorg=true`
> marker, (b) a series-continuity check against the fetched prices, and (c) a
> standing per-run WARN. Absent any of the three, the member stays censored.

### 9.1 Continuity re-derivation (read-only, `data/prices_e2.parquet`)

| metric | XOM (CIK 34088) |
|---|---|
| rows | **14,282** (reproduces the red-team's figure exactly) |
| span | **1970-01-02 → 2026-08-24** (56.6 years, 252.2 rows/yr) |
| largest gap | **7 calendar days**; **0** gaps > 10 days |
| per decade | 1970s 2,526 · 1980s 2,528 · 1990s 2,528 · 2000s 2,515 · 2010s 2,516 |
| vs the failure shapes | EA's purged stub = 6 rows; a reassigned symbol starts late (ARKO begins 2020) |

The check is now permanent: FATAL `successor_series_too_short` (< 1,250 bars),
FATAL `successor_series_starts_late` (first bar > coverage_start + 45 d), FATAL
`successor_series_missing`, else INFO `successor_series_continuous` **printing
the measured numbers**. Both directions are pinned by synthetic tests, including
the long-but-late-starting case that no existing check would have caught.

### 9.2 XOM now WARNs on every run — measured

```
[WARN] CIK 34088 XOM: override_symbol_bulk_maps_elsewhere -- EXXON MOBIL CORP:
  member CIK 34088 is fetched as XOM, but company_tickers.json maps XOM to CIK
  2115436. That is the APC trap SIGNATURE ... permitted here ONLY as a ratified
  successor-reorganisation override, with a series-continuity check and this
  standing WARN. Evidence on file (successor_cik_reorganization, added
  2026-08-24): ...
[INFO] CIK 34088 XOM: successor_series_continuous -- continuity check PASSED --
  14282 rows 1970-01-02..2026-08-24, largest gap 7 calendar days, reaching back
  16616 days before its coverage window opens (2015-07-01)
```

AEP keeps its own arm-1 WARN, EIDP keeps its, EA keeps its distress INFO: the
offline run now reports **0 FATAL, 3 WARN, 2 INFO**, and **no count moved** —
FETCH pair **213 / 31** (27 core / 4 extension), OPERATIVE pair **32**
(28 core / 4 extension).

### 9.3 What is still NOT established (recorded, not papered over)

There is **no cached `submissions` document for CIK 2115436** in this repo, so
the holding-company story itself rests on the bulk map plus the continuity
measurement — not on a primary filing. The evidence row now says so in those
words. The mapping is very likely correct; the *proof* is continuity plus SEC's
own bulk mapping, and that is exactly how it is written down.

### 9.4 Changes made

| path | change |
|---|---|
| `data/f2/price_ticker_overrides.csv` | New required `successor_reorg` column (XOM `true`, AEP `false`); comment block **retracts the false claim in a dated CORRECTION** and states the three-part rule; XOM's evidence rewritten around the measured continuity, with the 2115436 gap declared and E1's mapping demoted to corroboration. |
| `ingest_prices.py` | `RATIFIED_SUCCESSOR_REORG_CIKS = {34088}`, `SUCCESSOR_MIN_SERIES_ROWS`, `SUCCESSOR_REACH_GRACE_DAYS`; `TickerOverride.successor_reorg`; `validate_overrides_against_bulk_map()` (raises, called on every run); `TickerResolution.chosen_bulk_cik`; `ticker_wobble_issues()` arm 2 + optional `overrides` for evidence citation; `successor_continuity_issues()`; both wired into the full-run and `--resolve-only` paths. |
| `test_ingest_prices.py` | +15 tests: marker required/refused/non-boolean/unratified, run-level refusal of an unmarked trap-shaped override, all four continuity outcomes, the trap WARN naming both CIKs and citing evidence, the no-WARN case for a self-mapping override, and real-data pins for XOM's 14,282-row continuity and its per-run WARN. |
| `data/f2/F2_SPEC.md` | **Amendment A10** (A9 left for S3), plus a `> CORRECTED BY A10` note inside A3 at the false sentence. |

### 9.5 Test counts

`test_ingest_prices.py` **84 passed** (was 69), `test_price_client.py` **20
passed** — **104 passed, 0 failed, 0 skipped**, pyflakes clean. One earlier
assertion was **scoped, not weakened**: `test_exactly_two_real_members_are_
wobble_shaped` now filters to arm 1 by check name, because XOM legitimately
appears in arm 2 — that appearance is the fix, and it has its own test.

### 9.6 B12 / B13 caveats (LOW, report-level, no code)

- **B12 — "absence never censors" is the residual APC surface.** Exactly one
  member ever took that branch: **EA (712515)**, absent from the bulk map,
  fetched, and returned a 6-row stub. It was caught by `missing_in_window`, a
  **coverage** tripwire, not by an identity check. Had Yahoo returned a long
  series for a reassigned `EA`, nothing would have fired — `meta.symbol` would
  match, `instrumentType` would be EQUITY, and `starts_after_coverage_start`
  only triggers on a late start. A10's continuity check closes this **only for
  successor-reorg overrides**; the general absent-from-bulk-map case remains a
  known, unguarded surface, and is stated as such rather than implied safe.
- **B13 — the parquet has no per-CIK validity floor.** Full history is stored
  with no marker of when the CIK's own security began: **DuPont de Nemours (CIK
  1666700, registered 2017) carries `DD` back to 1972-06-01**, history belonging
  to the old E. I. du Pont — whose CIK (30554) is itself censored in this
  corpus. No live defect today (its coverage window opens 2018-07-02, so the
  early rows are out of window), but **any downstream read that does not clip to
  `[coverage_start, coverage_end]` can pick up another company's history under
  this CIK.** Binding note for F5: clip price reads to the coverage window.

### 9.7 Not mine to edit, flagged

`data/F2_INGESTION_REPORT.md` (≈lines 461-464) repeats the retracted safety
property verbatim. It is the docs owner's file; A10 names the lines and the
correction so it can be fixed there in the same pass.
