# S1 completion report — F2 recon + implementation spec

**Stage:** S1 (recon + spec). **Agent:** data-engineer (Opus).
**Date:** 2026-08-24. **Status: DONE.**
**Deliverable:** `data/f2/F2_SPEC.md` (written, complete, 10 sections).

This is the resume state for S1. If a later session finds S1 marked IN
FLIGHT with this file present, S1 is done and the ledger row is stale.

---

## 1. What was read

In the brief's order, all from files on disk (no prior-session summary was
trusted for any number):

- `HANDOFF.md` — full file (1,117 lines): §2a binding traps (a)–(d), §3
  decision log incl. the 2026-08-20/21 E2 ratifications, §4 incident rules
  (auto-resume chain; never long compute in a subagent), §5 spend freeze,
  §7 hard rules, §8 file map.
- `EXPANSION_PLAN.md` — full file: §2c survivorship/censoring, §3 standing
  rulings (3.5 fundamentals, 3.6 validation), §4 phases + gates G1–G4,
  §5 coupling workplan, §7 out-of-scope.
- `F2_PROGRESS.md` — full file: §3 stage table, §4 hard rules, §5 the two
  proposed build rulings, §6 owner-visible items.
- `data/E2_UNIVERSE_REPORT.md` — §1 PIT discipline, §2/2a window +
  live-EDGAR deltas, §3.1–3.8 (hybrid136, option record, manual exclusions,
  the two ratified float-integrity rules), §5 censoring census, §6.2 the
  XOM lesson + the Alphabet mirror case, §6.3 multi-class, §9 provenance /
  open items.
- Universe artifacts: `hybrid136.{csv,parquet}`,
  `hybrid136_panel.{csv,parquet}`, `manual_exclusions.csv`,
  `price_censoring_census.parquet`, `option_record_checksums.json`.
- Code, in full: `edgar_client.py` (380), `ingest_metadata.py` (999),
  `ingest_fundamentals.py` (647), `pit.py` (131), `ingest_prices.py` (374),
  `price_client.py` (391). `extract.py` interfaces only (949 lines,
  symbol-level). `build_universe_e2.py` output schemas (via its artifacts).
- Tests, at the level needed to find the tripwires: `test_ingest_prices.py`,
  `test_ingest_fundamentals.py`, `test_build_universe_e2.py`,
  `test_diagnose.py`, plus a repo-wide collect.

## 2. What was verified (and how)

Everything below was computed this session. **The verify-artifact rule was
applied first, before anything else was consumed.**

1. **`option_record_checksums.json`: all 8 sha256 MATCH** the shipped
   `continuity5.{csv,parquet}`, `continuity5_panel.{csv,parquet}`,
   `broad8.{csv,parquet}`, `broad8_panel.{csv,parquet}`. The option record
   behind the owner's 2026-08-21 decision is intact.
2. **That file does not cover `hybrid136*`** — by design (its `_what` scopes
   it to the pre-rules option record). So hybrid136 was verified directly:
   244 distinct CIKs, 299 spells, 1,496 panel rows, **exactly 136 members at
   each of the 11 reconstitution dates**, 176 core / 68 extension,
   **0 rows with `float_filed >= recon_date`** (PIT re-assertion clean),
   136 open spells (`member_to == ''`). Its sha256s are recorded in
   F2_SPEC §1.1 so S2 can pin them in code.
3. **Filing census, 244 members, 2015-07-01 → 2026-08-31**, from the cached
   submissions + all 351 pagination chunks (0 missing from cache, 0 network):
   2,452 10-K / 7,532 10-Q / 35,638 8-K = **45,622** target filings;
   **10,569** earnings 8-Ks (item 2.02). At a 2016-01-01 floor: 43,445 and
   10,092 — the extra six months costs +5.0%.
4. **Per-company window feasibility:** **0 of 244** members' EDGAR history
   starts after their derived `coverage_start`, so the redesigned
   `history_reaches_cutoff` is expected to fire on nothing.
5. **Filing-gap recalibration:** max 10-K/10-Q gap inside each member's own
   coverage window — median 115 d, p90 125, p95 126, p99 170, **max 266**.
   5 members exceed E1's 135-day FATAL; **0** exceed 300 d.
6. **Coverage recalibration:** periodic filings per coverage-year across all
   244 — min **3.91**, p5 4.04, median 4.07, max 4.51. E1's absolute floors
   (2 10-K / 7 10-Q per 12 quarters) are meaningless on churning membership.
7. **Stopped filers:** 29 members' last periodic filing is >200 d before the
   freeze date — exactly F1's 29 delisting-censored count. Independent
   agreement between two different derivations.
8. **Ticker resolution rule, run over all 244 members:** 212 CIK-verified
   tickers, 32 censored (31 with no ticker in submissions + EIDP with
   preferreds only), **0 bulk-map contradictions**. Reproduces all 25 E1
   ticker↔CIK pairs except XOM, which needs the one evidenced override.
   Verified the traps concretely in the cached `company_tickers.json`:
   `APC` → CIK 2080921 (a different company), `EMC` → absent,
   `XOM` → 2115436 (successor), and `AEP`/`EA` **absent from the bulk map
   entirely** — which is why the bulk map must be a contradiction detector,
   never a requirement.
9. **Concept-family availability** across the 25 cached companyfacts: every
   proposed tag exists in real data, including all four HANDOFF §2a trap (b)
   tags — `ProfitLoss` 19/25, `CashCashEquivalentsRestrictedCash…` 24/25,
   `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`
   17/25, `CashAndDueFromBanks` 3/25.
10. **Distress-event census** (zero extra network, already in submissions):
    Form 25 37/30 CIKs, 25-NSE 510/131, 15-12B 65/42, 15-12G 22/21,
    15-15D 32/13, 8-K item 1.03 2 filings / 1 CIK (895126, Expand Energy).
11. **Cache + disk state:** `data/raw/` = 1.7 GB today
    (documents 639 files / 1.20 GB, submissions 2,522 / 456 MB,
    companyfacts 25 / 106 MB, filing_index 640 / 5.8 MB). All 244 member
    CIKs already have a cached submissions doc; only 25/244 have
    companyfacts. **341 GB free** on the volume.
12. **Live probe — 2 EDGAR GETs total**, both through `EdgarClient` (10 r/s
    sliding-window limiter, project User-Agent), cached under `data/raw/`:
    CAT (CIK 18230) 8-K `0000018230-16-000702` index HTML = 8.3 KB in
    0.15 s, parsed to 6 rows, EX-99.1 selected at **high** confidence on a
    new filer / new sector / pre-iXBRL vintage; CAT's 2016 10-K primary
    document = **7.90 MB in 0.19 s (~40 MB/s)**. Conclusion: per-request
    latency, not bandwidth, is the binding constraint on S6.
13. **Test baseline:** `pytest --collect-only` = **399 tests**
    (`F2_PROGRESS.md`'s "394" is the 2026-08-21 figure).

**No Anthropic API calls. No new external data sources. No pipeline code
modified in S1.** Total network use: 2 EDGAR GETs.

## 3. Spec section index (`data/f2/F2_SPEC.md`)

| § | contents |
|---|---|
| 1 | Canonical membership artifact + adoption path; `hybrid136_checksums.json`; schema contract; `load_universe()`/`load_membership()`; removal of the 20–30 bound; SQLite schema changes + new `filings_metadata_e2.db` |
| 2 | Fixed window dates: `CORPUS_WINDOW_START = 2015-07-01`, `CORPUS_WINDOW_END = 2026-08-31`, fundamentals/prices full history |
| 3 | Per-company-window validation redesign; recalibrated thresholds with their measured basis; the per-`(cik, check)` evidenced exceptions file replacing `--allow-incomplete-universe`; two latent bugs |
| 4 | S3 metadata + documents: enumeration counts, confirmation of the full-window ruling, cache layout + honest idempotency statement, EX-99 per-filer audit plan, distress events, the documents prefetch segment + size estimate |
| 5 | S4 fundamentals: concept families (zero extra network), the five-state alias/migration classifier, UNRESOLVED semantics, sector-concentration blocker, supersession of the hand-curated maps |
| 6 | S5 prices: the CIK-verified rule with measured outcomes, the one-row successor override, census reconciliation, fetch changes incl. the Yahoo default |
| 7 | S6 runbook: 4 ordered segments, exact commands, measured GET counts, wall-clock estimates, resume properties |
| 8 | Tests: which pinned tripwires break and what re-pins them; new tests per stage; all offline |
| 9 | Decisions: 10 build-level rulings incl. verdicts on both §5 proposals; **owner items: none**; two owner-visibility flags |
| 10 | Out of scope |

## 4. Verdict on `F2_PROGRESS.md` §5's two proposals

1. **Full-window ingestion per member CIK (no spell clipping) — CONFIRM.**
   Clipping is not just fussier, it is wrong for the data F5 needs (a member
   at *t* needs pre-*t* history), and 299 spells over 244 CIKs means 55 CIKs
   re-enter, so clipping requires multi-interval enumeration logic for no
   benefit. Storage measured at ~26 GB vs 341 GB free. One binding condition
   attached: the F2 report must count ingested filings that fall outside
   every membership spell, and F5 must join on `universe_membership`.
2. **Fixed generous window — CONFIRM with one amendment.** Move the document
   floor to **2015-07-01** (12 months before the first reconstitution date)
   so trailing-four-quarter features are complete at first membership;
   measured cost +5.0% filings. Fixed end **2026-08-31**.
   Fundamentals/prices stay full available history.

## 5. Open questions / things S2–S6 must watch

None require the owner. In descending order of risk:

1. **EX-99 selection on 219 unseen filers is the largest residual unknown.**
   One probe on one new filer passed at high confidence; that is one data
   point. The §4.4 audit (counted failures, >1% FATAL, per-sector
   high-confidence assertion, mandatory manual read) is the control. If the
   failure rate lands materially above 1%, that is an S3 finding, not
   something to loosen.
2. **The classifier's 75%/40%/20% thresholds are reasoned, not measured** —
   only 25/244 companyfacts documents exist locally today, so the
   UNRESOLVED rate cannot be estimated before segment 3 runs. S4 must report
   the realised distribution and re-justify the thresholds against it, the
   same way E1 calibrated its coverage bands after a live pull.
3. **Document volume is the estimate with the widest band (18–40 GB).**
   The measured mix is 2016-vintage 10-Ks at 7.9 MB and E1-vintage
   non-EX-99 at 2.27 MB mean; 10-Q sizes are extrapolated. Segment 2 should
   print running totals so the estimate is corrected in flight, not after.
4. **CIK is not a stable company identity across 10 years** (E2 report §6.2,
   Alphabet/Google, Exxon/ExxonMobil Holdings). F1 deliberately does not
   stitch predecessor↔successor CIKs, so E2 sees those as churn. F2 does not
   change that; S5's one-row XOM price override is the only place the
   question touches F2, and it is confined to a price series. If F5 ever
   wants stitched entities, that is a new, evidenced decision — flag it
   there, do not let it leak in through a price map.
5. **`data/raw/submissions/` holds 2,522 documents** but only 244 are member
   CIKs — the rest are F1 diligence. Harmless, but do not infer member
   counts from directory listings.
6. **The Yahoo provenance exposure grows to 213 tickers.** Already restated
   to the owner 2026-08-24 (`F2_PROGRESS.md` §6); no new gate, but the F2
   report restates it beside the price-source default change.
