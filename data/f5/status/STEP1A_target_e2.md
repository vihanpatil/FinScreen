# F5 Step 1A — `target_e2.py`: the 63-session forward excess-return target

Status: BUILT and on disk. Session of 2026-09-10. Scope: the target table only.
**Zero information coefficients, correlations or feature-versus-outcome
associations were computed, in code, in tests, or interactively** (`F5_PLAN.md`
§1, the E2 freeze). No feature table was read or joined. `$0` — no network, no
API call.

E1 and E2 backtest numbers are numerically incomparable (different benchmark);
this table implements E2's §3.3 **proposal**, which is still awaiting the
owner's ratification at G3.

## 1. What was built

| file | role |
|---|---|
| `/Users/vihanpatil/personal/projects/FinScreen/target_e2.py` | the module (new sibling; no frozen E1 module edited) |
| `/Users/vihanpatil/personal/projects/FinScreen/test_target_e2.py` | 18 tests: 13 synthetic + 5 real-data smoke (≤ 300 filings) |
| `/Users/vihanpatil/personal/projects/FinScreen/data/f5/target_e2.parquet` | 29,271 rows × 18 columns, sha256 `c35956b784b9f0985796ed9dbb772360c043d2d77f1f300905c90b4d4757ece8` (git-ignored by the existing `data/f5/*.parquet` rule) |
| `/Users/vihanpatil/personal/projects/FinScreen/data/f5/target_e2_manifest.json` | input shas, price-snapshot pin, row-count census, per-quarter complete/incomplete census (versioned) |

All date logic is **imported** from the byte-frozen `controls.py`, never copied:
`load_membership`, `load_price_matrix`, `build_membership_matrix`,
`align_membership`, `excess_return`, `resolve_sessions`, and the horizon
constant `controls.HOLDING_DAYS = 63`. `controls.py` sha256 recorded in the
manifest: `b44358c389134dd9f5fc80b9a0d00be624d829b67d3d7f10d7e5e636c71dc32c`
(unchanged; `git status` shows no modification to any frozen module).

Session chain, as implemented (and as `controls.py` documents it):
`info_date = max(filing_date, acceptance_date_ET)` →
`news_session = first session ≥ info_date` (pre-close) / `> info_date`
(post-close, acceptance hour ET ≥ 16) → `window_open_session = news_session + 1`
→ `window_close_session = window_open + 63 sessions`.
Benchmark = equal-weighted mean of the **same** 63-session window return over
the universe members on the **window-open** session, **excluding self**,
membership-dated; unpriced members counted, never imputed.

## 2. Assertions enforced, with measured values

Every one of these runs on every build (`assert_target_invariants`, called
inside `build_targets`) or in the test suite; all passed on the full 29,271-row
frame.

| # | assertion | measured on the shipped run |
|---|---|---|
| A1 | input sha256s equal the committed record (`data/hardening/controls_results.json` `provenance.inputs`) | MATCH, all three: db `61dcefaa…`, prices `744e1cc5…`, fundamentals `f6064adf…` |
| A2 | `news_session ≥ info_date`, always | 0 violations / 29,271 rows |
| A3 | rows TREATED as post-close have `news_session > info_date` | 0 violations / 17,623 rows treated as post-close under the ported rule (60.21% of scoped rows; 59.22% of in-membership rows). That is a treatment share, **not** a measured post-close rate — see §3 and §5 item 4 |
| A4 | `window_open_session > info_date`, always | 0 violations / 29,265 rows with a window open |
| A5 | `window_open_session > news_session`, always | 0 violations |
| A6 | `window_close − window_open = 63 sessions exactly` (index distance on the price calendar) | observed set of spans = {63} over all 28,684 complete rows |
| A7 | incomplete rows carry no close session and no return | 587 incomplete rows, all null on close/subject/benchmark/excess |
| A8 | `target_excess_63 = subject_return_63 − benchmark_return_63` | max abs residual 0.0 (tolerance 1e-12) |
| A9 | the subject is never in its own benchmark (re-derived by hand on real rows) | 5 real rows re-derived cell-by-cell; benchmark, `n_benchmark_members`, `n_benchmark_unpriced` all reproduce; the with-self value differs |
| A10 | unpriced members counted, never imputed: `n_benchmark_members + n_benchmark_unpriced = members on that session ex-self` | holds on 20 real rows and on all synthetic fixtures |
| A11 | the module contains no association machinery (freeze tripwire) | source scan for `spearman`/`pearson`/`corrcoef`/`.corr(`/`linregress`/`ols(`/`polyfit`: none present |
| A12 | `controls.load_price_matrix`'s own guard: every retained session carries ≥ 50 priced CIKs | passed (inherited, unmodified) |

Mutation checks (run in the scratchpad against throw-away copies; the repo
files were never mutated) — each caught:
opening the window on the news session instead of the next one → 11 tests fail;
zeroing `n_benchmark_unpriced` → 3 tests fail; clamping an over-long window to
the last session instead of marking it incomplete → 1 test fails.

## 3. Population, as measured

Scope = filings by the 176 core-stratum CIKs (218 core spells). The benchmark
member set is the whole universe membership table (both strata, 244 CIKs) —
exactly what `controls.py` used for the published H1 numbers; the core stratum
governs which **filings** are scored, not who is in the average.

| quantity | value |
|---|---|
| filings by core CIKs | 32,287 |
| **excluded solely for missing subject prices** (CIK has no column in the price snapshot) | **3,016 filings across 27 core CIKs** |
| rows written | 29,271 (149 core CIKs with price coverage) |
| in-membership rows (`info_date` inside a core spell) | 16,859 (148 CIKs; 8-K 13,096 / 10-Q 2,842 / 10-K 921); span `info_date` 2016-07-01 → 2026-08-24 |
| out-of-membership rows, kept and flagged | 12,412 |
| complete targets (all rows / in-membership) | 28,684 / 16,471 |
| incomplete targets (all rows / in-membership) | 587 / 388 |
| non-null `target_excess_63`, in-membership | 16,397 |
| in-membership complete rows whose subject price is missing at an endpoint (CIK priced, coverage gap) | 74 |
| rows with no window open at all (filed at the snapshot edge) | 6 |
| `info_date > filing_date` (acceptance after filing date) | 4 (CIK 1108524 Salesforce ×2, 80424, 723125) |
| **rows treated as post-close under the ported rule** (`controls.resolve_sessions`: ET acceptance hour ≥ 16, or a missing acceptance timestamp) — manifest `n_rows_treated_post_close_under_ported_rule` / `share_…`. A **treatment count, not a measured post-close rate**: it is a superset of the filings whose bytes could only have been read after that session's close | 17,623 of 29,271 scoped rows (0.6021) |
| carried beside it: rows whose **ET acceptance date precedes `filing_date`** (the evening-before family; manifest `n_rows_acceptance_et_date_before_filing_date`) | 1,751 scoped rows, of which **1,717** are flagged `post_close` and so open one session later than the information arguably requires (§5 item 4) |
| GLD rows (CIK 1222333, SPDR GOLD TRUST), kept and flagged `is_gld` | 65 scoped / 14 in-membership |
| benchmark members used, complete in-membership rows | median 128, min 113, max 135 |
| benchmark member-cells counted as unpriced (never imputed), all rows | 10,926 (in-membership: median 0/row, max 1/row) |
| universe member CIKs with **no price column at all** (invisible to `n_benchmark_unpriced`) | 31 CIKs; median 5 such member-cells per session, max 21 |

Per-calendar-quarter complete/incomplete census (`info_date` quarter) is in the
manifest for both the in-membership and the all-scoped frames. Its load-bearing
fact for the G3 fold decision: under the sha-pinned snapshot
(`prices_e2.parquet` `744e1cc5…`, last session **2026-08-24**, 3,179 sessions,
213 priced CIKs), **every quarter through 2026Q1 is 100% complete; 2026Q2 is
327 complete / 124 incomplete; 2026Q3 is 0 / 264.** In-membership rows per
quarter range 346–521 over the 40 complete quarters; the partial 2026Q3
carries 264.

Univariate description of the target itself (no feature involved, no
association computed): in-membership `target_excess_63` n = 16,397,
mean −0.0013, sd 0.1362, min −0.660, median −0.0088, max +1.547. Reported only
as a plumbing sanity check on the return arithmetic.

## 4. Runtimes (M5, single process, cold start)

| step | seconds |
|---|---|
| sha assertion of the three inputs | 0.04 |
| load prices + membership + filings + membership matrix | 0.26 |
| build 29,271 targets (per-row `excess_return`) | 0.66 |
| **full `python3 target_e2.py`** | **1.03** (2.1 s wall incl. interpreter start) |
| `python3 -m pytest -q test_target_e2.py` | 1.5 s, 18 passed |
| `python3 -m pytest -q test_controls.py` (pre-existing, imports the module I import) | 1.0 s, 32 passed |

**Byte-identical reproduction, asserted (2026-09-10 red-team fix pass).** The
manifest relabel above changed only manifest text and two new census counters;
no target arithmetic and no written column moved. `target_e2.py` was re-run
twice after the edit and the parquet reproduced byte-identically both times —
sha256 `c35956b784b9f0985796ed9dbb772360c043d2d77f1f300905c90b4d4757ece8`,
equal to the pre-edit sha quoted in §1 and to the manifest's own
`output_sha256`. (It had already reproduced across two runs before the edit.)

## 5. Open questions for G3 (no recommendation attached)

1. **Benchmark member set.** The average is taken over the whole universe
   membership (both strata, median 128 priced members/session), because that is
   what `controls.py` does and it is ported verbatim. If G3 intends "members"
   to mean core-stratum members only, the table must be rebuilt; nothing
   downstream can repair it.
2. **No benchmark-member floor is applied.** `controls.py`'s own T2 arm
   required ≥ 20 members before publishing an excess return; this table applies
   no floor and writes `n_benchmark_members` on every row instead (G2's "no
   floors" ruling was about a different object). 2,744 complete rows have 0
   benchmark members — all of them out-of-membership rows with `info_date`
   before the universe's first reconstitution (max 2016-06-29); no
   in-membership row falls below 113.
3. **Membership interval convention.** `[member_from, member_to)` half-open,
   matching `build_membership_matrix`, so a filing can never be scored
   in-membership on a session where its own CIK is not a benchmark member. The
   brief's closed-bracket notation would add **3 rows** (`info_date` exactly on
   `member_to`).
4. **The post-close rule is one session conservative for the
   accepted-the-evening-before family.** 1,751 scoped rows have an ET
   acceptance date strictly *before* their `filing_date`; 1,717 of those are
   also flagged `post_close`, so their window opens one session later than the
   information arguably requires. This is the ported `controls.py` convention
   and it errs away from look-ahead in every case; whether G3 wants it refined
   is a ruling, not a bug.
5. **Row scope.** The table carries all filings by core CIKs with
   `in_membership` as a flag (16,859 in / 12,412 out). Whether the confirmatory
   population is the in-membership rows, and whether 10-K/10-Q rows are scored
   alongside 8-Ks, is G3's (decision 4 and the form-controlled ablation).
6. **GLD (CIK 1222333) is kept and flagged** (`is_gld`, 65 rows / 14
   in-membership) and it is currently also a benchmark member on its sessions.
   Decision 2 governs both its IC rows and its benchmark membership; the
   benchmark side requires a rebuild if excluded.
7. **Member CIKs with no price column are invisible to
   `n_benchmark_unpriced`.** 31 universe member CIKs never appear in the price
   snapshot (median 5 member-cells per session). They are counted globally in
   the manifest but cannot be counted per row, so a per-fold "excluded solely
   for missing prices" census (Step 2) must read that global count, not the
   per-row column.
8. **`acceptance_datetime` is written as the ET-localized string** (e.g.
   `2026-08-20 16:33:15-04:00`), not the raw UTC `Z` text from the DB, because
   the post-close rule is defined in ET. Round-tripping to the DB's exact
   string is not possible from this column alone.
9. **Yahoo split-adjusted-only prices** (decision 8, unratified) propagate
   directly into this target: dividends are not in the return. Every number
   above inherits that caveat.
