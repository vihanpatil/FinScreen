# S7 report note — what was written, from what, and what was not traceable

**Stage:** S7 (report half). **Agent:** docs-writer (Opus).
**Date:** 2026-08-24. **Status: DONE.**
**Brief:** `data/f2/status/S7_brief_report.md`.
**Deliverable:** `data/F2_INGESTION_REPORT.md` (new, owner-facing, stands
alone). This note is the resume state for the report half of S7.

**Mode:** read-only over the repo plus one new file and this note. No code
touched, no DB opened, no run executed, no network, no Anthropic API use.
`F2_PROGRESS.md` not edited (the ledger row is the main session's to flip).
The red-team half of S7 (`data/f2/status/S7_redteam.md`) is a separate
agent and was not written, read, or waited on here.

---

## 1. What the report contains

Ten sections, in the order an owner reads them:

- **§0 — the two queued owner decisions, first**: (a) SPDR Gold Trust
  membership (with the MLP/REIT context showing GLD is the sole anomaly),
  (b) the epoch-2 eval read for G1's conditional acceptance, including the
  missing post-ruled guidance line and the queued patch. Plus the two
  visibility items (Yahoo default, the censoring pairs).
- **§1** what was ingested, every number beside its log line; the
  45,622 → 45,632 reconciliation; distress events with the 25-NSE noise
  stated.
- **§2** the two censoring pairs, labelled FETCH / OPERATIVE, with EA as
  the concrete §2c residual and the F1 census reconciliation.
- **§3** what "in the corpus" does not mean: 20,218 outside-membership
  filings (by design), and the co-registrant rule.
- **§4** the fundamentals resolution profile, the empty blocker table under
  the 4-entry ledger with each exemption's reason, the two F5 notes, and
  what stays unfixed and firing.
- **§5** the EX-99 story honestly: the systematic Prologis error that
  confidence scoring missed, the six-part fix package, the 4 overrides,
  final unresolved 0.00%, Netflix as the one benign flag, and a full
  paragraph on what the read does **not** cover.
- **§6** Yahoo provenance + AEP wobble + EIDP-not-actioned + price
  validation.
- **§7** parked proposals (P4 → F3, interleaved stitching,
  just-below-threshold line, thin-span flag).
- **§8** verification: the 731/0/5 final gate, per-stage validation results,
  every stage report named, and an explicit "what F2 does not establish"
  block (no performance numbers; E1/E2 backtest incomparability; E1's
  label-quality constants are E1's and are model-consensus measurements;
  the labeler-contamination flag still owed).
- **§9** the caveat list that travels with the corpus; **§10** file map,
  re-run pointer, and the known docs debt.

## 2. Sources used, in the brief's order

| source | what was taken from it |
|---|---|
| `HANDOFF.md` (§2a, §3, §5, §7) | E1 label-quality constants and their epistemic status; the 8K_BODY / WITHDRAWN not-evaluable rule; the provenance rule that model judgments are never the owner's; trap (a)/(b) context |
| `EXPANSION_PLAN.md` (§2c, §3, §4) | the censoring residual's pre-registration; benchmark incomparability; labeler-contamination flag; gates G1–G4 and F2's scope |
| `F2_PROGRESS.md` (§3 stage table, §5 rulings, §6 owner items) | every dated build ruling, the queued owner items, the epoch-2 headline numbers and the derived post-ruled guidance figure |
| `data/f2/status/S6_runs.md` | segment-by-segment outcomes, 42 GB, 41.3 MB, the final 731/0/5 gate |
| `data/f2/F2_SPEC.md` §11 (A1–A8) | the amendments: enumeration window, co-registrant side table, AEP override, EA/`resolved_no_coverage` and the two pairs, 244-scale calibration, the EX-99 fix package and its two supersessions |
| `S1_recon.md`, `S2_membership.md`, `S3_metadata_documents.md`, `S4_fundamentals.md`, `S5_prices.md`, `S6_ex99_manual_read.md` | stage measurements, test counts, deviations, and the manual read's verdicts and coverage limits |
| `data/f2/s6_segment1_metadata_attempt6.log` | filings 45,632 / 45,545 / 87, forms, 10,569 earnings 8-Ks, unresolved 0 (0.00%), the selection distribution, the 62-CIK worklist with 42 uncovered, distress events, 20,218 outside-membership, max filing_date |
| `data/f2/s6_segment2_documents.log` + `_delta2.log` | 20,522 targets / 0 FAILED and the target decomposition |
| `data/f2/s6_segment3_fundamentals_attempt2.log` | 622,661 rows, 30 tags / 14 families, the per-family table, 497 UNRESOLVED of 3,416, the empty blocker table and the 4 exemptions with their suppressed-cell counts and reasons |
| `data/f2/s6_segment4_prices.log` | 213 fetchable (211 + 2 override) / 31 censored, 1,960,738 rows, GLD ETF WARN, EA missing_in_window WARN, both wobble WARNs, `0 FATAL, 3003 WARN, 0 INFO` |
| `data/PRICES_NOTES.md` §1 | the canonical Yahoo/Stooq provenance caveat |
| `finetune/runs/2026-08-22-eval-epoch2/eval_report.md` | every epoch-2 number re-read at source rather than taken from a summary |

## 3. Numbers I checked at source rather than trusting a summary

- The epoch-2 eval figures (83.5% / 0.487 / 58.8% / 64.87% / 92.42% /
  1,337 chunks-h / 0.00% parse+schema) were re-read from the eval report
  itself, not from `F2_PROGRESS.md` §6. They agree.
- Segment-2's final document state came from the **delta-2** log
  (20,522 targets, 1 fetched, 20,521 cached, 0 FAILED), not from the first
  segment-2 run's 20,523/19,896 figures, which predate the fix package's
  45 pick changes and the AT&T exclusion. This is why the report says
  20,522 and not 20,523.
- The 497/3,416 split and the four exemption reasons were taken from the
  attempt-2 run log, not from S4's prediction file — the run matched the
  prediction on all 3,416 pairs, so both agree, but the log is the fact.

## 4. Things I deliberately did NOT do

- **No performance claim appears anywhere**, because F2 produced none. The
  report says so explicitly and states that E1 and E2 backtest numbers will
  be numerically incomparable (different benchmark) when E2 has any.
- **Every ruling is attributed to the main session**, never to the owner.
  The only owner rulings referenced are the dated ones already in
  `HANDOFF.md` §3 (E2 scope, hybrid136 amendment, G1's conditional
  acceptance), and they are cited as such.
- **The two censoring pairs are never merged** and never appear as a union;
  each is labelled with the question it answers.
- **The EX-99 read's coverage cap is stated as a limitation**, not
  softened: 20 of 71 CIKs read, 51 unread, 52 of 62 8K_BODY CIKs and 217 of
  227 8K_BODY filings unread, plus the medium-confidence blind spot
  (16 selections, all Eversource, never on the worklist).
- No file other than `data/F2_INGESTION_REPORT.md` and this note was
  created or modified. `F2_PROGRESS.md`'s S7 row was left NOT STARTED for
  the main session to flip once the red-team half also lands.

## 5. What I could not trace, and how I handled it

Two items only. Neither is a number in dispute; both are stated in the
report the way the sources state them.

1. **The 42 GB document-cache size and the 41.3 MB prices parquet size**
   appear only in `data/f2/status/S6_runs.md` (the main session's own
   completion entries). They are not in any segment log I could read, and I
   have no shell to measure the tree. The report cites S6_runs.md as the
   source rather than presenting them as re-derived.
2. **The post-ruled guidance figure, 561/570 = 98.4%**, is a derivation
   recorded in `F2_PROGRESS.md` §6 from the eval report's own confusion
   table; the eval report itself does not print that line (which is exactly
   the G1 gap). The report labels it as a derived build-side reading and
   names the queued regeneration patch, rather than quoting it as a
   measured metric.

Additionally, three figures moved during F2 and the report quotes the
**final** value with the superseded one named where a reader would
otherwise trip:

- Prologis blast radius **39 → 41 → 42 of 45** (report quotes 42, and
  quotes 39/37-at-high-confidence as the state at discovery, because that
  is the fact that falsifies "confidence tracks correctness").
- Rule-level ticker resolution **212/32 → 211/33** with overrides 1 → 2;
  the **fetch pair 213/31 never moved**.
- P5 thin selections **44 → 50** (49 by the re-verifier's own count over
  the complete population, ±1 boundary case explained in
  `S6_ex99_manual_read.md` §V.4); the 12-under-100 figure never moved.

## 6. Resume state

Nothing is partial. If a fresh session finds `data/F2_INGESTION_REPORT.md`
and this note on disk, the report half of S7 is DONE; the remaining S7 work
is the red-team pass (`data/f2/status/S7_redteam.md`) and then the owner's
read. If the red-team pass finds a numeric error in the report, fix the
report — the run logs win over both of us.

---

# ADDENDUM — 2026-08-24 (later): red-team corrections applied

The red-team pass landed (`data/f2/status/S7_redteam.md`) and the main
session relayed eight corrections plus one mitigating fact. All are applied
to `data/F2_INGESTION_REPORT.md`. Same mode as before: read-only over the
repo, no code, no DB, no network. Findings are cited in the report by ID.

## A1. Sections changed, by finding

| finding | what changed, and where |
|---|---|
| — | **New "Status of the numbers" block in the header**: names the B1 defect, says a fix is in flight, and defines the ⏳ marker used on every figure that the re-run will move. |
| **B4** | **New §0(c), an owner-read item** carrying the full membership-time panel table (14.0% / 16.2% / 12.5% in the 2016/2017/2018 cohorts → 0.0% by 2026; 6.35% of 1,496 cells; energy 16.4%, utilities 0%; core 7.7% vs extension 2.5%), with the reason it matters — time-decaying **and** outcome-correlated deletion makes early folds differ from late folds for a non-alpha reason. Cross-linked from §2 (the CIK pair is labelled the wrong denominator for a walk-forward) and added as §9 item 2. |
| **B9** | §9 item 12 rewritten: the current-SIC look-ahead **does** propagate into membership, because the quota is fixed per sector (20/20/20/20/12/12/20/12 = 136 at all 11 dates) and `sector` is constant per CIK, so a 2016 bucket is decided by a 2026 SIC. Stated as a design limitation of the ratified universe rule, magnitude explicitly unmeasured. Added as §0 visibility item 3. |
| **B10** | Two item-1.03 filings (`0001104659-20-077745`, 2020-06-29; `0000895126-21-000016`, 2021-01-19), not one dated 2020-06-28. Fixed in §1's distress table and in §3.1, where the argument is now the stronger true one (**both** filings fall outside CIK 895126's 2024-07-01 → 2026-08-31 window). Both places note that `F2_SPEC.md` §11 and `F2_PROGRESS.md` still carry the wrong date. |
| **B2 / B1** | §5's "8K_BODY tail is probably fine" prior **deleted** and replaced with the measured defect: 19 of 225 `8K_BODY`/high picks have an unselected non-8-K row, 14 release-shaped, 3 read in full (Aon / Illumina / HPE cover pages, 2,260–4,231 chars), the affected filers named, why every guard missed it, and the fix-in-flight status. The unread-tail bullet now says the tail is where the defect lives. |
| **B20** | Enumerated **45,632** vs stored **45,545 (+87)** stated wherever the count appears (§1 gains a dedicated paragraph; §3.2 says "of the 45,632 enumerated"). Outside-membership given on both bases (20,218/45,632 enumerated; 20,165/45,545 = 44.3% stored) with the instruction to say which. Thin exhibits now "50 DB WARN rows over 49 distinct documents" with the ±1 explained. Prologis P6 corrected to **45 measured, 0 missing** (was "0 of 44"). |
| **B8** | **New §3.3**, "Point-in-time conventions F2 leaves open (pre-register at G3)": the 45% post-close acceptance fact (20,715/45,545), the two Salesforce filing-date-precedes-acceptance anomalies, and the 7.3% multi-value restatement groups (20,027/273,268) resolvable only by `pit.value_as_of()`'s filed-date rule. Framed as conventions to pre-register, not resolved facts. Also §9 item 7. |
| **B14** | §6's adjustment paragraph now carries **two** caveats: split-adjusted **as of fetch** (level-side look-ahead; returns invariant, level screens not) beside the dividend caveat. Also folded into §9 item 4. |
| **B16** | §1 gains the correction: the spec's "a re-run in October yields the same corpus" is false until 2026-08-31 passes, because the freeze date is in the future — 45,622 → 45,632 is that already happening. Repeated as an operational warning in §10. |
| Section A item 11 | §3.2 gains the mitigating fact: **0 of the 87 co-registrant accessions is an earnings 8-K**, so the keeper rule costs the text corpus nothing. |

## A2. Two corrections I applied beyond the relayed list, and why

Both are cases where the draft asserted something the red-team had shown to
be false or unsupported. Leaving them would have meant knowingly shipping a
false safety property.

1. **B3 — the XOM override.** §6 previously repeated the override file's
   claim that the different-CIK case "is still censored, never
   overridden." The 34088 → XOM row **is** that case (`company_tickers.json`
   maps XOM → CIK 2115436). §6 now states the correction, the three
   consequences (no cross-check in code; XOM never WARNs while AEP does;
   the evidence field argues precedent, not price continuity), **and** the
   corroborating evidence that the mapping is probably still right (14,282
   rows from 1970-01-02, no discontinuity — a reassigned symbol would have
   a short history). Flagged as an open item for the main session, not as a
   demonstrated wrong series; the code/ruling side is not mine.
2. **B6 / B7 — claims of coverage that outran the evidence.** §5's "exactly
   1 flagged CIK" now says what P6 does **not** clear (398 selections lack
   release language; only Netflix's 25 are named; Pioneer 38/77 = 49.4% is
   one filing from flagging and is independently implicated in B1), and
   P3's description is corrected from "armed for future instances" to
   armed against one narrow shape — the defect class is 38 filings, and P3
   sees only the ones with a descriptive description.

Additionally, four red-team findings that are code-side but constrain how
the corpus may be consumed are carried as **§9 item 13** with one line
each, rather than left only in the red-team file: **B11** (Enbridge reports
100% in CAD, no unit column), **B5** (truncated fundamentals tail is
structurally unobservable), **B15** (YTD/annual durations count toward
quarterly coverage), **B21** (8-K-sourced facts count toward coverage).
B12, B13, B17, B18 and B19 are left to `S7_redteam.md` and their stage
owners.

## A3. What I could NOT apply, pending regenerated numbers

The B1 fix changes selections, so every selection-side figure is
provisional. I marked each with **⏳** in place and said so in the header
rather than guessing at post-fix values or quoting a range I could not
measure:

- the selection distribution (`EX99_PRESS_RELEASE` high/low/medium
  10,308 / 19 / 16; `8K_BODY` high 225 across 60 CIKs);
- the `earnings_doc_unresolved` rate (0.00% — and note this metric counts a
  cover-page pick as *resolved*, so it will likely still read 0.00% after
  the fix; that is now stated);
- the P6 measurement (10,549 measured, 1 flagged CIK) and the near-miss
  shares, which move with the selection set;
- the §4.4 manual-read worklist (62 CIKs, 20 named, 42 uncovered);
- the document-cache target count (20,522, of which 10,568 are earnings
  documents) — segment 2 will fetch roughly 14 more.

**The main session triggers the final-numbers pass** over this report once
segment 1 attempt 7 and its segment-2 delta land; the regenerated
`data/f2/ex99_selection_audit.csv` plus the new attempt log are the
sources for it. Nothing else in the report depends on those figures.

One thing I did **not** re-derive and could not: the red-team's own
measurements (the panel censoring table, the 45%/7.3% PIT figures, the 398
P6-missing count, the 19-of-225 and 14 release-shaped counts). I have no
shell and did not re-run its queries; the report attributes each to
`S7_redteam.md` by finding ID rather than presenting them as mine.

---

# ADDENDUM 2 — 2026-08-24 (final): the final-numbers pass

The regeneration landed and the main session called the numbers final. All
⏳ placeholders are gone from `data/F2_INGESTION_REPORT.md`; every figure
now cites a post-regeneration source. Same mode: read-only, no code, no DB,
no network.

## B1. Every ⏳ replaced, with its final value and source

| what was pending | final value | source |
|---|---|---|
| header status block | rewritten: **B1 fix landed, numbers final**, suite **797 / 5 / 0** | main session (see B3 — not yet on disk) |
| documents cached | 20,522 targets, **15 fetched / 20,507 cached / 0 FAILED** | `s6_segment2_documents_delta3.log:61` |
| `EX99_PRESS_RELEASE` high / medium / low | **10,312 / 27 / 19** (was 10,308 / 16 / 19) | `s6_segment1_metadata_attempt8.log:303-307`, reconciled against `ex99_selection_audit.csv` |
| `8K_BODY` high | **210 across 55 CIKs** (was 225 / 60) | same log:303, 308 |
| earnings-doc overrides | **8 rows, 8 fired, 0 DEAD** (was 4) | same log:332-348 |
| unresolved rate | **0 / 10,569 = 0.00%**, reached *through* 4 printed refusals | same log:294 + the four `UNRESOLVED: CIK …` lines at 211-277 |
| P6 screen | **10,549 measured, 0 uncached, 397 missing release language, 1 flagged CIK (Netflix)** | same log:296-298 |
| P6 near-misses | now an in-pipeline **WATCH LIST**: PSEG 21/45 = 46.7%, Pioneer **37/77 = 48.1%** (the red-team's 38/77 = 49.4% was the pre-regeneration base) | same log:299-301 |
| §4.4 read worklist | **57 CIKs, 20 named, 37 uncovered** (was 62 / 42) | same log:309, 330 |
| medium-confidence blind spot | **27 medium** = Eversource 16 + the 11 new candidate-screen picks, none on any worklist | same log:306 + `S3_metadata_documents.md` §12.8 |
| fundamentals validation | **497 FATAL / 14 WARN / 21 INFO** (13 Enbridge CAD families + Citigroup tail lag; 21 one-filing lags) | `s6_segment3_fundamentals_attempt3.log:283, 285, 786-798` |

## B2. Content added in the same pass

- **§5 gets the B1 ending**: 15 pick changes = **11 candidate-screen at
  medium + 4 evidenced overrides**, 0 left unresolved; the fix described as
  a *conditional fallback, not a family widening*; the Linde 15th case the
  red-team's table missed; the ONEOK/Micron rows now redundant-for-selection
  but retained; future instances stay loud-UNRESOLVED. The **HPE
  wrong-candidate catch** (`S3_metadata_documents.md` §12.9) is written up
  as the reason override rows must verify the exhibit map rather than the
  candidate count — B1's own table named `pressrelease112117.htm`, which is
  the Item 5.02 CEO-appointment release, not the earnings release.
- **§6's B3 passage rewritten to the CLOSED state**: the three-part rule
  (ratified `successor_reorg` marker + continuity check + standing WARN),
  XOM now WARNing on every run, the continuity numbers printed rather than
  asserted (14,282 rows, 1970-01-02 → 2026-08-24, largest gap 7 days, zero
  gaps > 10 days), and the **unverified-holdco residual** stated in those
  words — no cached `submissions` for CIK 2115436, so the holdco story
  rests on the bulk map plus continuity, not a primary filing. B12's
  residual APC surface and B13's clip-to-coverage-window rule folded in
  beside it. Sources: `S5_prices.md` §9, F2_SPEC "A10: the successor-reorg
  guard".
- **§0(d), a second owner-read item: Enbridge's reporting currency** — 13
  resolved families in CAD against a USD price series, F2 converts nothing,
  standing WARNs per family; and the owner-level follow-on that its **core
  placement rests on F1's float ranking**, which may have compared a
  CAD-denominated `EntityPublicFloat` against USD floats. Sourced to
  `F2_PROGRESS.md` §6 (newest entry) and A11.
- **§4** gains the three new resolution-CSV columns (`unit`,
  `units_mixed`, `duration_mix`; 8 → 11) and the new
  `companyfacts_tail_lag` check, with the note that **zero resolution
  states changed**.
- **§8** updated: 797 gate with the 731 predecessor named, the repaired-
  through-the-gate note, the amendment-A10 label collision flagged so
  citations stay unambiguous, and S6_runs.md marked as stopping at the
  pre-red-team state with the three final logs named.
- **§9** items 9, 10 and 13 rewritten to the post-fix facts; §10's
  "B1 re-run pending" removed and the final run state named.

## B3. The one figure I could not trace to a file

**The 797 / 5 / 0 test gate.** It was reported by the main session in-chat;
`data/f2/status/S6_runs.md`'s last recorded gate is still **731 / 5 / 0**
and no attempt-7/8 or delta-3 completion entries exist there. The report
states the 797 figure **and says plainly that it is not yet appended to
`S6_runs.md`**. Recommend the main session append the closing S6 entries
(attempts 7–8, delta 3, fundamentals attempt 3, the final gate) so the
ledger matches the logs.

Two smaller notes:

- **`ex99_thin_exhibit` was not re-measured** after the fix (50 WARN rows /
  49 distinct documents is the pre-fix count; the count is not printed in
  the run summary, it lives in the DB). The report says so. The 15 changed
  picks were 2,260–4,231-character cover pages replaced by longer releases,
  so none of them was in the thin class either way — but that is reasoning,
  not a measurement, and it is labelled as such.
- **Two F2_SPEC §11 amendments are both labelled "A10"** (the
  successor-reorg guard and the bare-`EX-<n>` singletons), and A11 carries
  an in-file note that it was renumbered from a duplicate "A9". The report
  cites both A10s **by title** and flags the collision once in §8.

## B4. State

`data/F2_INGESTION_REPORT.md` is **final-numbered**: no placeholder
remains, every figure has a post-regeneration source, and the only
non-file-backed number in it (797) is labelled as such. The remaining S7
work is the owner's read.

*(Superseded the same day by ADDENDUM 3 — two more ruled fixes landed after
this pass and the numbers moved again.)*

---

# ADDENDUM 3 — 2026-08-24 (final): the Pioneer exclusion and the PSEG defect

Two more ruled fixes landed and regenerated after Addendum 2. Sources read:
`F2_PROGRESS.md` §5 (two newest entries), `S3_metadata_documents.md`
§12.10–§12.11, `S6_ex99_manual_read.md` §W ADDENDUM,
`s6_segment1_metadata_attempt11.log`, `s6_segment2_documents_delta4.log`,
`data/f2/ex99_selection_audit.csv` (read directly for the per-CIK rows),
and `F2_SPEC.md` §11 A13/A14. Same mode: read-only, no code, no DB, no
network.

## C1. Numbers that moved, with sources

| figure | Addendum 2 value | final value | source |
|---|---|---|---|
| segment-1 log of record | attempt 8 | **attempt 11** | `s6_segment1_metadata_attempt11.log` |
| segment-2 delta | delta 3, 15 fetched | **delta 4, 45 fetched / 20,476 cached / 0 FAILED** | `…delta4.log:91` |
| document targets | 20,522 (10,568 earnings docs) | **20,521 (10,567 earnings docs)** — 10,569 filings − 2 exclusions | `…delta4.log:3` |
| excluded by override | 1 | **2** (AT&T, Pioneer 2018-04-09) | `…attempt11.log:295` |
| `EX99_PRESS_RELEASE` medium | 27 | **26** | `…attempt11.log:306` |
| overrides | 8 rows / 8 fired | **9 rows / 9 fired / 0 DEAD** (7 select, 2 exclude) | `…attempt11.log:332-350` |
| P6 measured / missing | 10,549 / 397 | **10,548 / 379** | `…attempt11.log:296-297` |
| watch list | 2 (PSEG 46.7%, Pioneer 48.1%) | **1 — Pioneer 37/76 = 48.7%**; PSEG left it by being fixed (**21/45 = 46.7% → 3/45 = 6.7%**) | `…attempt11.log:300-301`; `ex99_selection_audit.csv:128` |
| deck-title screen | did not exist | **0 deck-shaped selections across 0 CIKs** | `…attempt11.log:299` |
| test gate | 797 | **815 passed / 5 skipped / 0 failed** | main session (see C3) |
| S3 targeted tests | 240 | **258 passed** | `S3_metadata_documents.md` §12.11 |

Unchanged and re-confirmed against attempt 11: EX99 high 10,312, `8K_BODY`
high 210 across 55 CIKs, unresolved 0 (0.00%), 45,632 / 45,545 + 87, the
distress-event counts, 20,218 outside-membership, max `filing_date`
2026-08-24. Totals reconcile: 10,312 + 26 + 19 + 210 + 2 = 10,569.

## C2. Content added

- **§5 gains the PSEG story as the capstone of the manual-read arc** —
  spot read (45/45 decks, every one HIGH confidence, the release sitting
  unselected at bare `EX-99`) → **per-filer handler, no blanket
  preference flip**, with ConocoPhillips as the measured
  empirical case that the index shape alone is not the defect → **deck-title
  screen** whose markers were measured rather than guessed (generic
  "conference call" rejected on 93 hits over 11 CIKs; the corroboration
  requirement exists because of the real Danaher false positive) →
  **two-candidate census run two ways**, with the note that the second
  denominator is the correct one and a single pass would have reported a
  cleaner roster than the truth → class enumerated (2 filers / 46 filings)
  and closed (0 deck-shaped selections corpus-wide).
- **The watch-list-is-a-floor caveat**, stated where it bites: PSEG passed
  the release-language screen on 24 of its 45 filings via
  `"investor relations"` contact-slide boilerplate while being wrong on all
  45, so a sub-50% share is a floor, not an estimate, and every filer below
  the bar is unmeasured rather than clean. Carried into §9 item 9 too.
- **The Pioneer 2018-04-09 exclusion** written up as what it is: a
  resolution the B1 fix got wrong (an IPAA slide deck under a conditional
  Regulation-FD Item 2.02 wrapper), with the report repeating the override's
  own words — *the fix made this one filing less honest* — and the reason
  the disposition is an evidenced exclusion rather than a policy change.
- **§9 item 9 rewritten to three error classes** (Prologis 42/45, B1 15
  filings, PSEG 45/45), each found by a human read or a screen built after
  one, never by the confidence label; plus PSEG never having been on the
  §4.4 worklist, since its picks were `EX99_PRESS_RELEASE`/high.
- **§8** updated: 815 gate with 731 and 797 named as predecessors, the B6
  watch list credited as what led to PSEG, and the amendment note replaced
  — **A1–A14 is now a clean unique sequence** (three amendments carry dated
  renumber notes; A9/A10 sit out of numeric order in the file), so the
  earlier collision warning is gone and citations are by number again.
  §10's final run state updated to attempt 11 / delta 4.

## C3. Still not traceable to a file

**The 815 / 5 / 0 gate**, exactly as with 797 before it: it was reported by
the main session, and `data/f2/status/S6_runs.md` still ends at the 731
entry. The report states 815 **and says the ledger's closing entries are
being written**. When the main session appends them, S6_runs.md should
carry attempts 7–11, deltas 3–4, fundamentals attempt 3 and the final gate,
so the ledger matches the logs.

Unchanged from Addendum 2: `ex99_thin_exhibit` (50 WARN rows / 49 distinct)
is still the pre-B1-fix count and the report still says so. The PSEG swap
replaced 45 decks (24k–36k characters) with releases, so it cannot have
moved the <1,500-character thin class either — again reasoning, not a
measurement, and labelled as such.

## C4. State

`data/F2_INGESTION_REPORT.md` is **complete and final**. Every figure
carries a post-regeneration source; the only non-file-backed number (815)
is labelled; no placeholder or pending marker remains anywhere in the file.
The remaining S7 work is the owner's read.
