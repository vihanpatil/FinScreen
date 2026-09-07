# S1 brief — F2 recon + implementation spec (issued 2026-08-24)

Agent: data-engineer (Opus). If S1 shows IN FLIGHT in `F2_PROGRESS.md`
with no `S1_recon.md` beside this file, the agent died — relaunch with
this brief verbatim.

## Task

Produce `data/f2/F2_SPEC.md`: the concrete implementation spec for F2
stages S2–S6 (see `F2_PROGRESS.md` §3). Spec only — do NOT modify any
pipeline code in S1. Sparing live EDGAR probe GETs are allowed
(rate-limited, User-Agent, cached under `data/raw/`).

## Read first (in order)

1. `HANDOFF.md` — §4 incident rules (auto-resume chain, never long
   compute in a subagent), §7 hard rules, §2a binding traps (a)–(d).
2. `EXPANSION_PLAN.md` — §3 standing rulings (esp. 3.5 fundamentals,
   3.6 validation), §4 phase F2, §5 F1/F2 coupling items.
3. `F2_PROGRESS.md` — the ledger; §5 has two proposed build rulings you
   must confirm or argue against.
4. `data/E2_UNIVERSE_REPORT.md` + `data/universe_e2_candidates/` —
   hybrid136 membership (verify `option_record_checksums.json` FIRST,
   verify-artifact rule), `manual_exclusions.csv`,
   `price_censoring_census.*`.
5. Code: `edgar_client.py`, `ingest_metadata.py`, `extract.py`
   (interfaces only), `ingest_fundamentals.py`, `pit.py`,
   `ingest_prices.py`, `price_client.py`, `build_universe_e2.py` (output
   schemas), and the matching tests (`test_ingest_*`,
   `test_edgar_client_companyfacts.py`, `test_price_client.py`,
   `test_pit.py`, `test_build_universe_e2.py`).

## The spec must cover

1. **Canonical membership artifact + adoption path**: which hybrid136
   file becomes the pipeline's universe input, its schema
   `(cik, ticker(s), sector, stratum, member_from, member_to)`-class
   contract, and how `ingest_metadata.py`'s universe loading changes.
   Include the deliberate removal of the 20–30 universe-size bound.
2. **Fixed window dates**: propose exact calendar dates (documents from
   ~2016-01-01; fundamentals/prices full available history as E1 did) as
   a generous superset of any G3 fold structure; `CORPUS_WINDOW_*`
   literals → derived. The fold structure itself stays owner-gate G3 —
   untouched here.
3. **Per-company-window validation redesign** (EXPANSION_PLAN §3.6):
   each company validates against its own `[member_from, member_to]`;
   IPO-late entry and delisting exits are expected states, not FATALs;
   fix the per-check-only override design flaw; no blanket overrides.
   Window-relative recalibration of filing-gap/coverage thresholds.
4. **Metadata + documents at scale** (S3): enumeration strategy for ~244
   CIKs, EX-99 earnings-exhibit selection audit plan per new filer,
   estimated GET counts / bytes / wall-clock, cache layout under
   `data/raw/`.
5. **Fundamentals systematic** (S4, EXPANSION_PLAN §3.5): broadened
   CONCEPTS (adds `ProfitLoss`, `CashAndDueFromBanks`, restricted-cash +
   NCI-equity variants — closes HANDOFF §2a trap (b)); automated
   alias/migration classifier whose UNRESOLVED cases fail loudly per
   (company, concept); how E1's hand-curated per-ticker alt-tag maps are
   superseded.
6. **Prices at scale** (S5): CIK-verified ticker mapping — NEVER fetch a
   dead member by former ticker (APC→ARKO, EMC→ETF trap); integration
   with `price_censoring_census`; censored CIKs counted and reported;
   full-history fetch; `source` column provenance.
7. **S6 runbook skeleton**: ordered run segments (metadata → documents →
   fundamentals → prices), each idempotent + cache-first (killed and
   re-run completes; hybrid136's 0-GET re-run is the standard), designed
   for main-session background execution in an auto-resume chain, with
   the exact resume command per segment and per-segment duration
   estimates.
8. **Tests**: which pinned tripwires break and what re-pins them; new
   tests per stage; everything offline.
9. **Decisions**, split explicitly: (a) build-level rulings the main
   session can ratify (including a verdict on `F2_PROGRESS.md` §5's two
   proposals), vs (b) anything that genuinely needs the OWNER (expected:
   none for F2 — flag if you find one).

## Constraints

- Lazy-elite engineering (owner, 2026-08-24): minimal changes to working
  E1 code, extend existing modules, no new frameworks, simple readable
  core logic. Bug-free and low-latency beat clever.
- No Anthropic API calls. No new external data sources.
- Every estimate labeled as an estimate with its basis.

## Deliverables (write BOTH before returning)

1. `data/f2/F2_SPEC.md` — the spec.
2. `data/f2/status/S1_recon.md` — completion report: what you read, what
   you verified (incl. the checksum verification result), spec section
   index, open questions.
