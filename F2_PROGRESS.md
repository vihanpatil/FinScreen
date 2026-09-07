# F2_PROGRESS — Ingestion at scale (E2 phase F2)

**Started 2026-08-24** on the owner's explicit "start F2" in chat. This file
is the **resume ledger** for F2: the owner's Claude Max token limit may stop
any session mid-work, so every stage flips its status HERE and writes a
completion report under `data/f2/status/` before it counts as done. A fresh
session resumes from this file alone.

**Read order for a fresh session:** `HANDOFF.md` → `EXPANSION_PLAN.md`
(§3 rulings, §4 F2, §5 coupling) → this file → `data/f2/status/*.md` →
`data/f2/F2_SPEC.md` (once S1 lands).

**Ledger discipline (binding on every agent doing F2 work):**
1. A stage is DONE only when its completion report exists on disk at
   `data/f2/status/S<N>_*.md` (what was done, what was verified, exact
   file paths touched, how to resume/re-run).
2. All ingestion commands must be **idempotent and cache-first** — killed
   halfway and re-run, they complete without redoing network work
   (`data/raw/` cache = the checkpoint; the hybrid136 build's 0-GET
   re-run property is the standard).
3. Long-running runs (network ingestion, anything > ~15 min) execute as
   **main-session background tasks in an auto-resume chain** — never
   inside a subagent (HANDOFF §4 incident rule; subagent cleanup reaps
   detached processes).

---

## 1. What F2 is (plan of record: EXPANSION_PLAN.md §4, §5)

Ingestion at scale for the ratified hybrid136 universe:

- **Metadata + documents**: filings (10-K/10-Q/8-K + earnings exhibits)
  for every E2 member CIK over the E2 window; EX-99 selection audited per
  new filer.
- **Fundamentals, systematic** (EXPANSION_PLAN §3.5): broadened concept
  set (adds `ProfitLoss`, `CashAndDueFromBanks`, restricted-cash and
  NCI-equity variants — closes HANDOFF §2a trap (b)) + an automated
  alias/migration classifier whose UNRESOLVED cases **fail loudly** per
  (company, concept), never resolve stale.
- **Prices** for all members: **never map dead members by former ticker**
  (F1 finding: APC→ARKO, EMC→ETF resolve to WRONG companies on Yahoo);
  CIK-verified mapping or censor-and-count. Delisted-price censoring is
  counted and reported, never silently dropped.
- **Validation** (EXPANSION_PLAN §3.6): per-company `[member_from,
  member_to]` windows (IPO-late entry and delisting exit are expected
  states, not FATALs); the per-check-only override design flaw gets fixed,
  not worked around; no blanket `--allow-incomplete-universe`.
- **Recalibration**: filing-gap/coverage thresholds window-relative;
  `CORPUS_WINDOW_*` literals → derived; the 20–30 universe-size bound
  removed deliberately; corpus tripwires re-pinned (never deleted).
- **Owner-visibility**: the Yahoo price-provenance caveat
  (`data/PRICES_NOTES.md` §1) restated to the owner at F2 (done — see §6).

## 2. Inputs (frozen upstream state — verify before consuming)

- **Universe**: `data/universe_e2_candidates/hybrid136.{csv,parquet}` +
  `hybrid136_panel.{csv,parquet}` (per-date membership), built 2026-08-21.
  ~244 distinct CIKs (176 core / 68 extension), 299 membership spells,
  136 members at each of 11 annual reconstitution dates (first
  2016-07-01). **Verify `option_record_checksums.json` before consuming**
  (verify-artifact rule, HANDOFF §7).
- `data/universe_e2_candidates/manual_exclusions.csv` — 6 evidenced
  float-mis-scaling exclusions + the owner-ratified
  `float_integrity_2026-08-21` ruleset (2 rules, hybrid136-only).
- `data/universe_e2_candidates/price_censoring_census.{csv,parquet}` —
  29 member-CIKs plausibly delisting-censored (F1 census; S5 re-verifies
  at fetch time).
- Full F1 narrative: `data/E2_UNIVERSE_REPORT.md`.
- E1 artifacts (`data/labels.parquet`, finetune split, spot-check record)
  stay **frozen** — E2 rebuilds the corpus but never edits E1's record.

## 3. Stage table

| Stage | What | Executor (tier) | Status | Report |
|---|---|---|---|---|
| S0 | Kickoff: this ledger + TIGER team refresh (`TEAM.md`, `.claude/agents/`) | Fable (main) | **DONE 2026-08-24** | this file + `TEAM.md` |
| S1 | Recon + implementation spec → `data/f2/F2_SPEC.md` | data-engineer (Opus) | **DONE 2026-08-24** | `data/f2/status/S1_recon.md` |
| S2 | Membership-table adoption + window constants derived + per-company-window validation redesign | data-engineer (Opus) | **DONE 2026-08-24** (0 live GETs; suite 399 → 444 collected, 439 passed / 5 skipped / 0 failed) | `data/f2/status/S2_membership.md` |
| S3 | Metadata + documents ingestion code at scale (+ EX-99 per-filer audit hooks) | data-engineer (Opus) | **DONE 2026-08-24** — both rulings implemented; co_registrant_filings = exactly 87 rows reconciling 45,535+87=45,622; lowest-CIK keeper pinned by tests; 112/112 targeted tests; 0 live GETs; F2_SPEC §11 amendments appended | `data/f2/status/S3_metadata_documents.md` |
| S4 | Fundamentals systematic re-ingest code (broadened CONCEPTS + alias classifier) | data-engineer (Opus) | **DONE 2026-08-24** — four passes (last: the 244-scale calibration §5 ruling: filed-span denominator, 3 measured MLP tags, 4-entry exemption ledger). Predicted re-run profile: UNRESOLVED 693→497, 196 improved / 0 regressed, blocker table empty; 100/100 targeted tests. Parked proposals in S4_fundamentals.md §11: interleaved-substitutes stitching (6 of 8 OVERLAPs), just-below-threshold report line, thin-span flag | `data/f2/status/S4_fundamentals.md` |
| S5 | Prices-at-scale code (CIK-verified mapping, dead-ticker rule, censoring census) | data-engineer (Opus) | **DONE 2026-08-24** (213 fetchable / 31 censored, all counts match spec; 68/68 targeted tests; 0 live GETs; full-suite gate pending at S3+S4 close) | `data/f2/status/S5_prices.md` |
| S6 | **The ingestion runs** (metadata → documents → fundamentals → prices), main-session background auto-resume chain per the S6 runbook in F2_SPEC | Fable (main session) | **DONE 2026-08-24** — all 4 segments + EX-99 fix package + calibrated fundamentals + manual read + content re-verification; final: 45,632 filings / 42 GB docs / 622,661 fundamentals rows / 1.96M price rows; earnings-doc unresolved 0.00%; P6 sole flag = Netflix (benign); **final gate 731 passed / 0 failed / 5 skipped** | `data/f2/status/S6_runs.md` |
| S7 | Red-team pass over S2–S6 + F2 ingestion report + owner read | red-team-reviewer + docs-writer + extraction-qa (Opus) | **DONE 2026-08-24 (awaiting only the OWNER READ)** — red-team B1–B21 all triaged/fixed/or-owner-queued; three late content defects found and closed (B1's 15 cover pages, Pioneer mis-label, PSEG 45/45 decks) with content verification on real bytes each time; final gate **815 / 0 / 5**; report FINAL at `data/F2_INGESTION_REPORT.md`. Honest residual: the red-team's pass predates the B1/Pioneer/PSEG fix cycles (which its findings triggered) — those cycles were verified by measured replays + independent content reads, and F6's full red-team pass covers them fresh | `data/f2/status/S7_redteam.md` + `S7_report_note.md` + `S6_ex99_manual_read.md` §V–§W |

Test gate between code stages and S6: full pytest suite green. Baselines,
measured not remembered: **399 collected** at S1 (2026-08-24; the "394"
figure is 2026-08-21's), **444 collected / 439 passed / 5 skipped / 0
failed** after S2. New tests added per stage; tripwires re-pinned, never
deleted.

## 4. Hard rules binding F2 (pointers, not paraphrases — the source wins)

- **No Anthropic API spend, ever** (HANDOFF §5). F2 touches EDGAR + the
  existing free Yahoo endpoint only. No new external data sources without
  an owner ratification.
- **Long compute = main-session background auto-resume chain** (HANDOFF
  §4, 2026-08-20/21 incident row). Assume any task can be SIGTERMed at any
  time; cheap resumability over segment sizing; never spawn long compute
  from inside a subagent. Recipe pattern:
  `finetune/runs/2026-08-21-epoch1-final-from-2250/RESUME_RECIPE.md`.
- **Dead members are never fetched by former ticker** (F1 finding,
  `data/E2_UNIVERSE_REPORT.md`). CIK-verified identity or
  censor-and-count.
- **Loud failures, no silent drops.** Every exclusion is counted, named,
  and reported (censored CIKs, unresolved concept aliases, extraction
  failures).
- **Verify-artifact rule** (HANDOFF §7): checksum/inspect inputs before
  consequential use — starting with `option_record_checksums.json`.
- **PIT discipline**: `filing_date`, never `report_date`; membership at
  date t decided only from pre-t filings (already true in hybrid136;
  F2 must not undo it downstream).
- **Rate limit + User-Agent** on every EDGAR request, including ad-hoc
  probes.
- **Lazy-elite engineering** (owner, 2026-08-24, in chat): simple,
  readable core logic; no over-engineering; the minimal work necessary to
  work correctly and fast. Extend existing modules; don't build
  frameworks. Correctness is non-negotiable; cleverness is not a goal.

## 5. F2 build-decisions log

Owner-gated items go to HANDOFF §3; build-level rulings live here, dated.

- **2026-08-24 (proposed at kickoff, to be confirmed against S1 spec):**
  ingest the **full E2 window for every CIK that is ever a member**
  (rather than clipping fetches to each membership spell) — simpler, no
  per-window edge bugs, storage is cheap (~10–25 GB); feature
  construction respects membership dates downstream. S1 must confirm or
  argue against this in F2_SPEC.
- **2026-08-24 (proposed):** exact ingestion window = a fixed, generous
  calendar superset of any fold structure G3 could ratify (documents from
  ~2016-01-01; fundamentals/prices = full available history, as E1 did,
  with PIT selection downstream). Exact dates fixed in F2_SPEC; the FOLD
  structure itself remains owner-gate G3 and is untouched by F2.
- **2026-08-24 — RATIFIED (main session, after verification pass): the ten
  build-level rulings in `data/f2/F2_SPEC.md` §9.1.** Both kickoff
  proposals above are CONFIRMED as amended by the spec: proposal 1 with
  the §4.2 binding condition (F2 report counts filings outside every
  membership spell; F5 joins on `universe_membership`, never on presence
  in `filings`); proposal 2 with the documents/metadata floor moved to
  **2015-07-01** (12 months before the first reconstitution date;
  measured cost +5.0% filings) and fixed end **2026-08-31**. Also
  ratified: hybrid136.parquet read in place under a new
  `hybrid136_checksums.json`; universe pin `== 244` replaces the 20–30
  bound; new `data/filings_metadata_e2.db` (E1 DB frozen);
  `--allow-incomplete-universe` deleted in favor of the evidenced
  per-(cik, check) exceptions file (expected empty); concept families +
  five-state alias classifier replace the three hand-curated maps (which
  the classifier must reproduce as acceptance tests); CIK-verified price
  tickers from `submissions.json` only, with exactly one evidenced
  override (34088→XOM) and CIK 29915 (Dow Chemical) deliberately
  censored; Yahoo as default price source with Stooq one flag away
  (owner-visibility item, §6); distress events ingested in S3 at zero
  network cost; documents prefetch as its own S6 segment. Verification
  performed before ratifying: spec read in full by the main session;
  censoring arithmetic re-checked (212+1 resolved / 31 censored); the
  §3.3 `write_validation_problems()` gating bug confirmed directly at
  `ingest_metadata.py:863`.
- **2026-08-24 — RULED (main session): "substitutes-only families +
  explicit dominance" amendment to F2_SPEC §5.2/§5.3.** S4's first pass
  implemented the spec faithfully and measured 86/250 (cik, family)
  pairs UNRESOLVED on E1's own 25 companies with MIGRATION never firing
  — because the spec's families grouped tags that are NOT economic
  substitutes (e.g. `Liabilities` with `LiabilitiesAndStockholdersEquity`
  = total assets; parent-share vs NCI-inclusive income; balance-sheet
  cash vs the ASU-2016-18 cash-flow total) and §5.3 treats legitimate
  co-reporting as ambiguity. Ruling: (1) a family may contain only true
  alternative representations of ONE logical series (aliases/migration
  successors); related-but-distinct concepts become their own single-tag
  families, still ingested; (2) preference order is promoted from
  reporting-only to resolution semantics via a new resolved state
  DOMINANT (highest-preference tag with own coverage ≥75% wins an
  overlap; co-reported alternates recorded); OVERLAP-UNRESOLVED then
  means genuine ambiguity only; (3) UNRESOLVED stays loud, the 20%
  sector-BLOCKER rule and MIGRATION logic unchanged; (4) SLB's E1
  "operating income → ProfitLoss migration" is deliberately NOT
  reproduced as a resolution — it papered over a real concept change;
  SLB going loud-PARTIAL on `operating_income` is correct behavior,
  documented as superseding E1's hand-map. Acceptance bar: every E1
  hand-map case lands in a deliberate documented state; MIGRATION fires
  where E1 documented real migrations (MA/OXY); remaining UNRESOLVED on
  the 25-company preview individually justified, ~zero expected; zero
  unjustified preview BLOCKERs; F2_SPEC gets a dated amendment block
  (appended, not rewritten). Resolution choice is re-visitable at F5
  without re-ingesting — ingestion stores every tag as-is regardless.
- **2026-08-24 — RATIFIED (main session): S3's shared-window enumeration
  deviation.** F2_SPEC contradicted itself (per-company coverage windows
  in §4.1 prose/§8.2 vs the shared `[2015-07-01, 2026-08-31]` everywhere
  else). The shared window is the ratified reading: it is what §9.1(1)
  "no spell clipping" means, it alone reproduces every MEASURED plan-of-
  record count (45,622 filings / 10,569 earnings 8-Ks / the distress
  totals), and clipping would silently lose the corpus's only 8-K item
  1.03 bankruptcy (CIK 895126, filed 2020, outside its own late spell) —
  which EXPANSION_PLAN §2c makes mandatory to keep. Per-company windows
  still govern all §3.1 VALIDATION, unchanged. Enumeration = shared
  window; validation = per-company windows.
- **2026-08-24 — RULED (main session): co-registrant filings get a
  side-table, and a missing `filings` row is NEVER evidence of
  non-filing.** S3 measured 87 of 45,622 filings (Dow Chemical/Dow Inc
  67, Williams/Williams Partners 16, Exelon/Constellation 4) where one
  accession carries two member registrant CIKs and the accession-keyed
  PK drops the second attribution. Re-keying `filings` on
  `(accession, cik)` would ripple into `filing_documents` and F3's grain
  for 0.19% of rows — rejected as over-engineering. Instead: new
  `co_registrant_filings(accession_number, kept_cik, co_cik, form,
  filing_date)` table storing every dropped attribution (deterministic
  keeper rule, documented), populated during enumeration at zero network
  cost. Binding downstream rule, to be restated in the F2 report and at
  F5: any per-company filing/coverage question consults `filings` ∪
  `co_registrant_filings`; absence from `filings` alone is not evidence
  a company did not file. F5's accession→company attribution must yield
  BOTH member CIKs for these accessions.
- **2026-08-24 — RULED (main session): S4 second-pass items.** (1)
  **`us-gaap:Cash` joins the `cash` family at LOWEST preference** with a
  documented definitional caveat (excludes cash equivalents): for a
  filer that never tags any broader cash line (SLB, 49 quarters
  measured), plain `Cash` IS its balance-sheet cash representation;
  dominance guarantees it never displaces a proper tag, and the
  resolution CSV preserves which tag won — a provenance-tracked series
  beats a manufactured gap, at 244 scale especially. (2) **Sector-BLOCKER
  aggregation gains `BLOCKER_EXEMPT_CELLS`** — a single small dict of
  (sector-or-*, family) → reason, printed in every run report whether or
  not it fires (same discipline as the validation-exceptions file);
  per-pair UNRESOLVED rows are NEVER silenced, only excluded from the
  aggregate BLOCKER alarm. Rationale: HANDOFF §4's crying-wolf lesson —
  an alarm carrying 10 structurally-expected cells trains people to
  ignore the real ones. Ruled-in exemptions: (*, minority_interest) and
  (*, net_income_to_common) — concepts that exist only for filers with
  NCI / preferred stock — and (financials, operating_income), the
  E1-documented trap (a) fact. Anything else the measurement suggests is
  proposed in the S4 report, not exempted. New cells at 244 scale still
  fire loud and go to a human in the F2 report, per the spec's
  rule-once-in-the-open design.
- **2026-08-24 — RATIFIED (main session): the segment-1 EX-99 diagnosis
  and fixes** (`data/f2/status/S6_seg1_ex99_diagnosis.md`). Taxonomy of
  the 400 failures: 336 transient EDGAR 503s/timeouts never retried (a
  real `edgar_client` defect — 5xx/timeout now retry on the 429 backoff;
  4xx still never retried), 64 benign single-document 2015–2019 8-Ks
  rejected by an accidental `>=3`-row parse-guard proxy (replaced by the
  exact no-dropped-row invariant; all 64 reclassify to 8K_BODY, counted
  and NAMED in the audit report), 0 genuine selection failures. Offline
  replay over all 10,233 cached indices: 0 failures, 0 changed
  selections on previously-successful filings, expected re-run rate
  0.00%. The 1% FATAL ceiling is untouched — it did its job.
- **2026-08-24 — RULED (main session): AEP (CIK 4904) gets the second
  evidenced price-ticker override.** During segment 1's TTL refresh,
  EDGAR's submissions.json for AEP dropped to empty `tickers`/
  `exchanges`; a live probe (main session, 1 GET) confirmed it has not
  self-healed, while SEC's own bulk `company_tickers.json` maps
  AEP→4904 and AEP is a listed, actively-filing current member. Censoring
  a live mega-cap over an upstream data wobble would be wrong; the
  ratified submissions-only rule stays the default and the evidenced
  override file is its designed exception path. Evidence for the row:
  bulk-map agreement (symbol→our CIK, the safe direction — unlike the
  APC trap where the symbol pointed at a DIFFERENT CIK), S5's 12:22
  pre-refresh resolution record in `price_ticker_map.csv`, and its
  active exchange listing (CORRECTED by S5's measurement: **Nasdaq** per
  EDGAR's pre-wobble `exchanges[]` in F1's census — this entry
  originally said NYSE, which was wrong; nothing in the ruling depended
  on it). S5 FOLLOW-UP RESULT (same day): exactly TWO wobble-shaped
  censored members exist — AEP (override applied; its WARN still fires
  by design, keyed off rule_status) and **EIDP (CIK 30554), reported
  NOT actioned: a live filer whose only SEC-mapped symbols are preferred
  series (no public common equity since the DowDuPont reorg) — censoring
  is CORRECT; an override would pull a preferred-share series into an
  equity-return backtest.** No third case. Final pair re-confirmed
  unchanged: 213 fetchable (211 rule + 2 override) / 31 censored
  (27 core / 4 extension); 74/74 targeted price tests.
- **2026-08-24 — RULED (main session): EA (CIK 712515) is
  fetched-but-effectively-censored, and the two censoring numbers are
  reported as distinct facts.** Segment 4's `missing_in_window` tripwire
  caught it: Yahoo returned only 6 rows for EA (all July–Aug 2026,
  flatlined at the ~$209.70 take-private price, volume 0), with
  `firstTradeDate` reset to 2026-07-17 — Yahoo purged the delisted
  name's history, the exact §2c outcome-censoring residual
  EXPANSION_PLAN pre-registered, now real for a core member (tech,
  2017-07→2021-07). Ruling: S5 adds a `resolved_no_coverage` status;
  the FETCH pair stays 213 fetched / 31 unfetchable, and the operative
  **NO-USABLE-PRICES pair for every E2 analysis becomes 32 (28 core /
  4 extension)** — both quoted, clearly distinguished, wherever either
  appears. EA's delisting must be visible via its distress_events rows
  (the §2c mechanism built for exactly this). IMPLEMENTED + VERIFIED
  same day (S5, `data/f2/status/S5_prices.md` §8): EA is the sole
  no-coverage member (next-smallest in-window count among the 212 is
  539 rows — no boundary case), pinned two-sided (a second instance
  FATALs BY NAME; EA regaining history FATALs too); distress_events
  carries EA's 25-NSE (2026-08-04) + 15-12G (2026-08-14), so the §2c
  visibility loop is closed in code (`no_coverage_distress_issues()`
  runs every time); FETCH vs OPERATIVE pairs labeled everywhere; 89/89
  targeted price tests.
- **2026-08-24 — FINDING for the owner (not ruled — membership is
  owner territory): SPDR GOLD TRUST (CIK 1222333) is a hybrid136
  member, in the CORE financials stratum** (SIC 6221, spells 2017-18
  and 2023-24), caught by segment 4's instrument-type tripwire
  (`meta.instrumentType='ETF'`). A passive commodity trust is not an
  operating company; its float is trust asset value and its filings
  describe gold custody. Whether to exclude it (evidenced,
  entity-type-eligibility rule — a new rule class like
  float_integrity) or deliberately retain it is an OWNER call at the F2
  report read. Context from the same scan: the energy MLPs (Enterprise
  Products, Williams Partners, Energy Transfer entities, Magellan,
  MPLX) and Digital Realty (REIT) are genuine operating companies —
  known, defensible consequences of the ratified float rule; GLD is the
  one anomaly. F2 ingestion treats it as a member meanwhile; its
  fundamentals will classify loudly ABSENT and surface in the 244-scale
  blocker report by design.
- **2026-08-24 — RULED (main session): the 244-scale classifier
  calibration** (from reading segment 3's real run: 3,416 pairs —
  SINGLE 2,192 / DOMINANT 456 / MIGRATION 75 / OVERLAP 8 / ABSENT 353 /
  PARTIAL 332; 693 UNRESOLVED pairs; 18 surviving BLOCKERs). Four
  rulings: (1) **Denominator fix** — reportable quarters = the
  company's own filed span of in-window operating-form data, not the
  full coverage window; the AZEK artifact (fully-covered short-life
  member marked 69% PARTIAL on all 14 families because window quarters
  predate its IPO and postdate its acquisition) is the classifier
  failing to inherit S2's filed-span ruling. STALE-tail protection
  (anchored on own-last-quarter) stays. (2) **MLP tag broadening** —
  partnership issuers represent the same logical series with per-unit /
  partners-capital tags; add the measured partnership variants to the
  affected families (equity, eps_diluted, shares_outstanding,
  pretax_income as data dictates), corporate tags first in preference,
  substitutes-only principle intact. (3) **Two exemption-ledger
  additions, now measured at 244 scale**: ("*", "liabilities") —
  30–56% ABSENT-dominated in 7 sectors, derivable as
  liabilities_and_equity − equity (F5 note attached); and
  ("*", "operating_income") — E1 trap (a) extended beyond financials
  (energy 47%, healthcare 34%, materials 32%, industrials 26%);
  structurally sector-correlated reporting style, so F5 must treat it
  as a non-universal feature; pretax_income is the resolving fallback
  family. Per-pair FATAL rows stay loud for both, as always. (4) The
  8 OVERLAP cases and the multi-class shares_outstanding blockers stay
  UNFIXED and firing — listed individually in the S4 report; the
  dimensioned-facts gap is parked, not papered over. After the code
  lands, the main session re-runs segment 3 (0 GETs, companyfacts
  cached) and reads the new blocker table.
- **2026-08-24 — RULED (main session): the EX-99 manual-read fix
  package** (findings: `data/f2/status/S6_ex99_manual_read.md` — 17
  CORRECT / 2 WRONG / 1 AMBIGUOUS over the worst-20 read, but the
  Prologis WRONG is SYSTEMATIC: ~39 of its 45 earnings selections pick
  the EX-99.1 "Supplemental Information" tables package instead of the
  EX-99.2 press release, 37 of them at HIGH confidence — falsifying
  "confidence tracks correctness"). Ruled IN, all implemented by the
  metadata-code owner before segment 1 re-runs: (1) P2 Prologis
  per-filer handler, gated on first content-confirming EX-99.2 across
  its cached history; (2) a new evidenced
  `data/f2/earnings_doc_overrides.csv` (accession-level, load-time
  validated like every other override file) carrying the two
  singletons — NVIDIA `0001045810-19-000168` (release typed EX-95.1 by
  filer typo; blast radius measured n=1 over all 10,569) and AT&T
  `0000732717-19-000048` (no release present — tables-only, real
  release lives in the same-day sibling accession); (3) P3 as a loud
  WARN when an index row is DESCRIBED as a press release outside the
  EX-99 family (the override file is the resolution path — no
  trust-the-description auto-pick); (4) P1 exhibit-number-from-
  description confidence fix (11 of 32 low rows, no pick changes);
  (5) P5 image-only/empty-exhibit WARN (44 thin selections, 12 under
  100 chars); (6) P6 — generalize what caught Prologis: a corpus-wide
  release-language screen over all cached selections, per-CIK, flagging
  any CIK whose high/medium selections mostly lack release language
  (Prologis is the acceptance test). Ruled OUT for now: P4's new
  `EX99_FINANCIAL_SCHEDULES` section_type — section-type taxonomy
  changes touch F4 labeling applicability (EXPANSION_PLAN §5:
  "APPLICABILITY extended only deliberately"), so it is parked to the
  F3 handoff, and no threshold is loosened. After the package: segment
  1 attempt 3 (cache-warm), then a targeted re-verification of the
  Prologis/NVIDIA/AT&T rows.
- **2026-08-24 — RULED (main session): ONEOK + Micron join the
  earnings-doc override file.** P3's new outside-EX-99 screen
  immediately surfaced two more typo-class filings — ONEOK
  `0001039684-15-000073` (release typed `EX-95.1`) and Micron
  `0000723125-19-000172` (typed `EX-99..1`) — both of which had fallen
  back to selecting the 8-K COVER PAGE as 8K_BODY at HIGH confidence,
  invisible to every prior trigger. Same defect class as NVIDIA (typo
  class now measured n=4 corpus-wide... n≥3 known + NVIDIA), same
  resolution: two more evidenced `select_document` rows (evidence =
  the index rows' own press-release descriptions + the P3 WARN), file
  grows 2 → 4 rows, all load-time validated. P3 remains the permanent
  tripwire for future instances. Also accepted from the fix-package
  measurement: Prologis is 41 of 45 (not the read's 39 — the read's two
  extra "correct" filings merely cite the release), and the P6 screen's
  Netflix flag (53%) is REPORTED-BENIGN — shareholder letters, correct
  picks — with the threshold deliberately NOT moved to hide it.
  Sequence to close S6: segment 1 attempt 3 (regenerate selections +
  audit) → segment 2 delta (~44 newly-selected documents) → P6
  re-screen on the real corpus (0-GET metadata pass) → targeted
  re-verification by extraction-qa of all five ruled filers → final
  full suite.
- **2026-08-24 — RULED (main session): the two residuals from the
  content re-verification** (which was otherwise a full PASS on real
  bytes — all five filers confirmed, distribution reconciled with zero
  residue). (1) **Prologis split moves 2016-07-19 → 2016-04-19**: the
  2016-04-19 filing's EX-99.1 title says "Earnings Release and…" but
  its body contains no release (no ToC "Press Release" entry, zero
  release-language hits outside the title — a template-leftover
  header); blast radius is 42 of 45, one more pick change, its EX-99.2
  fetched by a 1-GET delta. (2) **P6 scope fix**: exclude the leading
  title/self-label region from the marker window — a document whose
  only release-language hit is its own title must not pass; acceptance
  test = the 2016-04-19 EX-99.1 flags under fixed P6 while the corpus
  otherwise keeps exactly one flagged CIK (Netflix, reported-benign;
  if the scope fix moves Netflix either way, that is reported, not
  tuned). A scope change, not a threshold move, per the standing
  principle. Noted without action: the re-verifier corrected its own
  earlier uncached/thin-exhibit counts (10,568/10,568 cached;
  thin = 49).
- **2026-08-24 — S7 red-team TRIAGED (main session; findings B1–B21 in
  `data/f2/status/S7_redteam.md`).** Foundations SURVIVED full
  independent re-derivation (classifier 3,416/3,416 pairs exact;
  enumeration re-derived to the accession; checksums; PIT panel clean;
  suite 731/0). Accepted and dispatched: **B1 (HIGH, corpus content)**
  — 14 filings store the 8-K cover page as the earnings doc at HIGH
  confidence because the 8K_BODY fallback fires unconditionally with
  unselected release-shaped rows present (fix: fallback must check for
  unselected candidates; ceiling must count cover-page picks; NO
  family-regex widening) → S3 owner, with B2/B6/B7/B17. **B3 (HIGH,
  guard)** — the XOM override IS bulk-map-elsewhere-shaped and the
  file's own comment denies it; fix = explicit successor-reorg marker
  + per-run WARN + series-continuity evidence cited (14,282 rows to
  1970), rule wording corrected → S5 owner, with B12/B13 notes.
  **B5/B11/B15/B21** (staleness self-anchoring — Citigroup 2q behind
  scores 0.977; Enbridge 100% CAD invisible to a unit-blind classifier;
  duration-type and 8-K-sourcing notes) → S4 owner. **B4/B9 (owner-
  read items)** — membership-time censoring is 14–16% in the earliest
  cohorts decaying to 0% and outcome-correlated; the current-SIC
  look-ahead DOES propagate into membership under fixed quotas — both
  added to the report as first-class limitations and queued for the
  owner's read; no code change can remove them this round. **B8**
  (acceptance-time/PIT as-of rules) → one anomaly WARN now; the
  convention itself is G3 pre-registration material. **B10 CORRECTION
  to entries above**: distress facts are TWO item-1.03 filings (CIK
  895126: 2020-06-29 and 2021-01-19), not one filing "2020-06-28" —
  the shared-window ratification's conclusion is unchanged (both sit
  outside the CIK's own spell). B16/B18/B19/B20 wording and
  numeric-hygiene items → docs-writer + this correction entry.
  Sequence: fixes land → affected segments re-run (cache-warm) →
  re-gate → extraction-qa spot-check of B1's corrected picks → S7
  closes.
- **2026-08-24 — RULED (main session): Pioneer 2018-04-09
  (0001564590-18-007673-class accession, `d564737dex991a.htm`) gets an
  evidenced `exclude` override row** — the 15-pick content verification
  (S6_ex99_manual_read.md §W: 14 CORRECT / 1 mis-labelled, HPE
  double-check confirmed from the filer's own exhibit map, B1
  population provably drained) found it is an IPAA conference slide
  deck furnished under a defensive Item 2.02 wrapper ("the portions,
  if any, of the Investor Presentation…"), not a release — the same
  ruled class as AT&T's exclusion, stronger evidence. Kraft Heinz's
  pick stands with its scope caveat noted (an annual
  restatement-results release — genuine results content). Also
  ordered: one representative PSEG read (788784, the 46.7% watch-list
  entry no pass has examined) so the watch list's next-worst name is
  read-or-cleared rather than merely named. After both: final 0-GET
  regeneration, gate, S7 close; remaining watch-list names stay
  honestly unread in the report.
- **2026-08-24 — RULED (main session): the PSEG defect + the deck
  screen.** The ordered PSEG read (§W ADDENDUM) found the largest
  single-filer content defect of F2: **45/45 earnings selections are
  conference-call slide decks** ("PSEG Earnings Conference Call …" →
  forward-looking boilerplate; 37–46 per-slide GRAPHIC rows), with the
  actual release sitting UNSELECTED at bare `EX-99` in every one of the
  45 — the Prologis shape one rung lower; root cause: the ladder
  prefers sub-numbered `EX-99.1` over bare `EX-99`, and both
  descriptions are uninformative. Ruled: (1) a **PSEG per-filer
  handler** (Prologis pattern) selecting the bare `EX-99`,
  content-verified post-delta by extraction-qa per the standard; NO
  blanket bare-vs-subnumbered preference flip (other filers may order
  oppositely — measure, don't gamble); (2) a **deck-title screen**
  generalizing what §W measured: title-region deck language
  ("Earnings Conference Call" / "Financial Results Presentation"-class
  markers) flags a selection regardless of body hits — run over all
  10,569 cached selections, every flagged CIK reported, PSEG-pre-fix
  as the must-flag acceptance test; (3) a **two-candidate-shape
  census**: count every filer with the bare-EX-99 + EX-99.1 index
  shape so the defect class is enumerated, not sampled. Also accepted
  from §W: P6 "passers" can pass on contact-slide boilerplate — the
  watch-list share is a floor; stated in the report.
  Also ruled: a new WARN (`submissions_ticker_missing_but_bulk_has`-
  class) naming any member whose submissions carry no ticker while the
  bulk map maps a symbol to that same CIK — AEP-shaped wobbles must
  surface, never auto-resolve; overrides stay manual-and-evidenced.
  Net counts: rule-level 211 resolved / 33 censored; overrides 2
  (XOM, AEP); **final pair unchanged: 213 fetchable / 31 censored
  (27 core / 4 extension)**.
- **2026-08-24 — S2 implementation clarifications (data-engineer, measured
  not assumed; full detail in `data/f2/status/S2_membership.md` §6).** No
  ratified ruling, threshold, or formula changed. (a) `member_to` in
  hybrid136 is **exclusive** — the first reconstitution date at which the
  CIK is no longer a member, not the last at which it was (verified on all
  299 spells against the panel; F2_SPEC §1.2's prose says otherwise, the
  artifact wins). §1.2's formula is implemented verbatim, which makes
  `coverage_end` ~1 year more generous than the prose implies — strictly
  conservative. (b) `plausible_filing_counts`' denominator, which §3.1
  leaves undefined, is `coverage_start` → the company's **last in-window
  periodic filing**, not the full window length: the naive reading FATALs
  19 delisted members for their empty 400-day tails (min 1.61/yr) and
  contradicts both §3.1's own quoted distribution and §3.2's "expected
  empty"; the filed-span reading reproduces §3.1's distribution (min 4.01,
  median 4.08, max 4.53) with 0 members failing. (c) In-window gap
  measurement yields **5 WARN findings across 4 members** (PepsiCo has
  two), not 5 members — Autodesk's 189-day gap is outside its own coverage
  window; FATAL count 0 either way. (d) `recent_activity_10k_10q` keeps
  E1's 135-day threshold; measured, the choice is inert (0 current members
  and the same 29 former members fire at every threshold from 135 to 250).
  **Empirical result: `data/f2/validation_exceptions.csv` ships empty and
  S6 segment 1 should hard-fail on nothing — 0 FATAL / 5 WARN / 29 INFO
  across all 244 members.**

## 6. Owner-visible items raised at F2

**RESOLVED 2026-08-25 — the owner read `data/F2_INGESTION_REPORT.md`
and ruled (HANDOFF §3, 2026-08-25 entry):** GLD stays a member
(deliberate retention); epoch-2 report patch executing before the G1
read (G1 ruling still pending); censoring/SIC read-items acknowledged;
**non-USD fundamentals convert to USD as standard** at the
feature/analysis layer (FX source + PIT semantics specified at F5/G3).
A foundations re-evaluation + decision audit + tech-council agent were
commissioned before F3. Items below preserved as raised.

- **Yahoo provenance caveat restated in chat 2026-08-24** (required by
  EXPANSION_PLAN §6): all prices come from Yahoo Finance's free keyless
  chart endpoint; Yahoo's robots.txt disallows automated access and it
  has no published terms for this use; E2 grows the exposure ~4–5×
  (~130+ live tickers vs 25). Schema stays source-agnostic (`source`
  column) so a provider swap later costs only a re-ingest. Canonical
  write-up: `data/PRICES_NOTES.md` §1.
- **Epoch-2 re-eval is COMPLETE and awaits the owner's G1-conditional
  read** (`finetune/runs/2026-08-22-eval-epoch2/eval_report.md`).
  Headlines vs epoch-1: sentiment 83.5% (was 81.7; NEGATIVE recall 0.487,
  was 0.425), red_flags exact-set 64.87% (was 62.8 — now above the
  teacher's own 63.4% reproducibility ceiling), per-category 92.42%
  (teacher 92.5), guidance raw 58.8% (was 47.7), parse/schema failures
  0.00%, throughput 1,337 chunks/h.
  **Known gap:** the report omits the post-ruled guidance line the G1
  ruling required; derived from its own confusion table it is
  **561/570 = 98.4%** (226 of 235 errors are `NONE→__MISSING_FIELD__`).
  PATCH QUEUED: finetune-engineer to regenerate the report with the
  post-ruled line before the owner's read. F2 does not depend on this;
  F4 does. **PATCH EXECUTED 2026-08-25** (owner-ordered; APPENDIX A of
  the eval report, recomputed from predictions.jsonl, all-additive):
  561/570 verified EXACTLY; the rule rewrote 226 rows, all
  teacher-NONE — nothing laundered. G1-read essentials: the 98.4% is
  majority-class-carried (11/17 = 64.7% on the 17 real-guidance rows);
  epoch-1 post-rule is ALSO 561/570, so epoch 2 bought zero guidance
  semantics; all 7 over-emissions are explicit NONE. The honest G1
  question is SENTIMENT (83.5%, NEGATIVE recall 0.487) + post-rule
  adoption (still PROPOSED, NOT ADOPTED). G1 ruling remains pending.
- **Price-source default (raised 2026-08-24, F2_SPEC §9.1 item 8):**
  Yahoo becomes the default (`--price-source yahoo`); Stooq — which the
  2026-08-18 target ratification named by example — has been bot-gated
  site-wide since that same day, so attempting it 213 times to fail 213
  times would be the wrong default. The Stooq code path stays intact one
  flag away. Visibility item, not a gate.
- **Enbridge float-currency question (raised 2026-08-24, S7 finding
  B11 follow-on, S4 fifth pass):** Enbridge (CIK 895728) is the
  universe's only non-USD reporter — all 13 resolved fundamentals
  families in CAD, now surfaced per-family in
  `data/f2/concept_resolution.csv` with standing WARNs; F2 converts
  nothing. Owner-visible follow-on: its CORE-stratum placement rests on
  F1's float ranking, and whether that ranking compared a CAD-reported
  `EntityPublicFloat` against USD floats without conversion is the same
  currency question one level up — flagged for the owner's F2 report
  read alongside the GLD item; F1 artifacts stay frozen meanwhile.
- **Final price-censoring pair (raised 2026-08-24, F2_SPEC §6):**
  **31 member CIKs have no price series at all (27 core / 4 extension)**
  — this pair must accompany every stratified E2 result. It differs from
  F1's headline 29 for two documented reasons (XOM resolved via the one
  evidenced override; EIDP's preferred-only listing counted as
  resolvable by F1's census but censored by the stricter fetch-time
  rule); S5 re-derives and diffs against F1's census, and any OTHER
  delta is a finding.

## 7. Resume protocol (fresh session, possibly after a token-limit stop)

1. Read this file top to bottom, then `data/f2/status/` (newest first).
2. The stage table above is authoritative for what is DONE. Trust
   completion reports + files on disk over any memory of a prior chat.
3. If a stage is IN FLIGHT with no completion report: its agent died.
   Check `git status` / `git diff` for partial edits; the spec
   (`data/f2/F2_SPEC.md`) defines the target state; relaunch the stage
   agent with the same brief (briefs are reproduced in each status
   report; S1's brief is summarized in `data/f2/status/S1_brief.md`).
4. For S6 runs: check for live processes (`ps aux | grep -i
   "ingest\|python"`), then consult `data/f2/status/S6_runs.md` for the
   exact resume command per segment. All S6 commands are idempotent —
   when in doubt, re-run the current segment's command; the cache makes
   repeats cheap.
5. Never restart a DONE stage; never re-decide a dated decision in §5 or
   HANDOFF §3 without a new owner ruling.
