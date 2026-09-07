# F3_PROGRESS — Extraction at scale (E2 phase F3)

**Started 2026-08-26** on the owner's explicit "Begin F3 now" (HANDOFF
§3, 2026-08-26 entry). Same resume discipline as `F2_PROGRESS.md`: a
stage is DONE only when its completion report exists at
`data/f3/status/P<N>_*.md`; long runs are main-session background
auto-resume chains (HANDOFF §4); briefs live in the stage rows'
pointers and are relaunched verbatim if an agent dies.

**Runs in PARALLEL with the G1 repair campaign** (rubric-v1.2 re-label
+ retrain — see HANDOFF §3 2026-08-26; that campaign gates F4, not F3).

## Binding F3 inputs (measured, from F2/F2.5 — the source docs win)

1. **Population gate (H4, recall 9/9 measured):** FAIL/WARN, never
   silently extract, when a selection sits in a multi-filing
   (CIK, quarter) cell AND its text lacks a results-announcement
   signature; sole-filing cells measured clean (0/116). The narrowed
   text-signature variant's recall must be re-measured on H4's 155-row
   ledger before trusting it. (`data/hardening/status/H4_docsample.md`)
2. **8K_BODY slicing:** item-2.02-anchored — median 1,975 chars (up to
   57%) of cover-page boilerplate precedes the first "Item 2.02".
3. **Length is a bad discriminator:** the sample's largest doc (21,009
   words) was an error and two <400-word docs were genuine —
   recalibrate `MIN_SECTION_WORDS` / `MDA_STUB_WORD_CEILING` from the
   new distribution per EXPANSION_PLAN §5 F3, but never as an
   error-catch substitute for the population gate.
4. **Combined release+supplemental EX-99.1 dilution** (e.g. Simon
   Property ~74% tables): handle deliberately, report the class size.
5. EXPANSION_PLAN §5 F3 coupling: pre-2019/pre-iXBRL TOC dialects
   expected; mandatory per-filer failure triage; spot-read sample
   ~30–50 sections weighted toward new filers and pre-2019 filings,
   with a WRITTEN STOPPING RULE for the manual QA before it starts
   (re-evaluation trim); expect new per-filer edge handlers, small and
   named.
6. Extraction consumes the cache at 0 GETs (F2 prefetched everything).
   F4-scale re-derivation from F3's actual section output is a REQUIRED
   F3 deliverable (decision-audit: plan's chunk count low 1.2–2.1×;
   member-spell-vs-full-window labeling decision needs it).

## Stage table

| Stage | What | Executor (tier) | Status | Report |
|---|---|---|---|---|
| P0 | F3 spec: extractor changes, population gate design, floors plan, QA protocol + stopping rule, run segmentation | extraction-qa-engineer (Opus) | **DONE 2026-08-26, APPROVED by main session** — broad gate ships (9/9 recall; narrowed variant REFUTED on H4's ledger via the ICE/Bakkt case: a signature can't tell WHOSE results); 8K_BODY slices item-2.02→end (census: next-heading would gut 45/210); floors flag-never-filter + flagged rows never high-confidence; stub regex proven broken (0/4 real stubs) → word-count trigger; scale corrected to ≈28,840 sections; 3 segments/34 shards ~2–3.5 h; QA stopping rule pre-committed. Main-session items: MD&A-incorporated-by-reference class measured at P3 before any fetch decision; 1 worker at P2 (measured poor scaling) | `data/f3/status/P0_spec.md` |
| P1 | Implementation + offline tests (extract.py extensions, gate, slicing, audit artifacts) | extraction-qa-engineer (Opus) | **DONE 2026-08-26** — 113/113 tests; E1 corpus-scale regression 880/884 byte-identical (4 diffs = the ruled 8K_BODY slicing); all 4 P0-named stubs fixed (JPM 2017 resolves to 59,855 words) + a 5th found; EX-99 floor 50→250 argued row-by-row; §6 markers calibrated (dead marker removed, Simon miss reported not patched); new mojibake class → P3; zero live GETs (EdgarClient no longer imported). Four documented spec readings, none substantive | `data/f3/status/P1_impl.md` |
| P2 | Extraction runs (main-session background chain, resumable, 0 GETs) | Fable (main session) | **DONE 2026-08-27 12:56** — 30,475 attempts → 28,900 sections (OK 25,245 / FLAGGED 3,655 / FAIL 796 / EXPECTED_ABSENT 779); `cache_miss=0` every shard, 0 GETs all 4 runs, `merge.complete: true` 34/34 shards, zero kills/resumes; corpus `data/filings_e2.parquet` (620.9 MB) + 5 audit artifacts | `data/f3/status/P2_runs.md` |
| P3 | Mandatory QA: per-filer triage, spot-reads per protocol, floor recalibration, F4-scale re-derivation | extraction-qa-engineer (Opus) | **DONE 2026-08-27 ~13:54** — verdict: FIT FOR F4 with must-fix N1 (mojibake `ctrl_ratio` screen; P1's non-ASCII proposal REFUTED) + sized carve-outs; 148/796 FAILs = code defect (F2 fall-through recovers all 148); spot-reads T1/T2 16/16+16/16, T3 extension fired per pre-committed rule (3/8→5/10 own-tier); floors: 0 changed, 4 documented holds; D2 census 121 MDA + 41 RF (N2: RF structurally invisible); F4 scale MEASURED: W2-core 99,965 chunks ≈ 9.4 overnights (plan × 1.30), reflow decision = 2.18× lever; decisions parked for owner/main: N1, D2 fetch, N3 Simon marker, N5 last-match defect, N6 NIKE, window rule W1/W2/W3, reflow | `data/f3/status/P3_qa.md` |
| P4b | Full census of the 779 EXPECTED_ABSENT rows (owner-ordered 2026-08-27) | extraction-qa-engineer (Opus) | **DONE 2026-08-27 ~19:20** — 696 R1 + 71 R2 + 12 R3 = 779 exact; **83 misclassified extractor failures (P4's [61,179] held), 71 recoverable = 125,156 words, 12 (AIG) unrecoverable garbage**; all 779 are 10-Q RISK_FACTORS (structural); era gradient 16.9% pre-2020 vs 3.4% after; P4's fix ordering amended AGAIN by hand-read evidence: **guards G1 (heading-anchored start) + G2 (no-EOF-runout, ships as flag not filter) first, then F1′, then F2′, scoped to TOC-present rows (R2/R3) ONLY** — the same ladder on R1 admits 89 garbage rows; F2 is 0/12 on R3 but 13/13 on R2-where-F1-fails; P4's 0.5–2× band unfit here (bimodal distribution, rejects 49/58 correct spans) — replaced by the guards, 0 disagreements vs ~62 hand-read sections; **+42 R1 rows have genuine unindexed sections** → status rename needed (125/779 status-wrong, 83 extractor defects) | `data/f3/status/P4b_expected_absent_census.md` |
| P5 | Pre-F4 corpus fix package + rebuild + regression (owner-ratified scope: recover what's evidenced, prevent wrong text) | extraction-qa-engineer (Opus) | **DONE 2026-08-28 ~00:40** (~5.2 h) — changed-row reconciliation EXACT (1,055 attempt-rows changed, 276 corpus text changes, 0 unattributed); ladder recovered 197 rows / 1.69M words (EA arm reproduces P4b filer-for-filer; 34 declined stay loud; R1 fired 0×; all recovered ≤ medium confidence); N5 58 rows / +519k words (all 34 AT&T full-length); NIKE 21 rows / +214k words; N1 union 6 fires (all 5 known + 1 named FP); G3 floor-admission guard ADDED on evidence (P4b's two guards admitted 5 failures on the wider population); end-guard scoped to EOF-runout only (Coca-Cola 73-word truncation caught); N5 first-match rule REFUTED by hand-read (15/12/11) → floor-scoped length rule; own regression caught + corpus rebuilt from scratch; the 42 unindexed-genuine rows FLAGGED not recovered (safe branch of a real spec conflict, disclosed). **163 tests pass (main-session re-verified). F4 corpus: `data/filings_e2_v2.parquet` sha `15853e9f…`** (29,097 rows); audit `data/f3/v2/` (696 → honest `ITEM_ABSENT_FROM_TOC`); E1 880/884 byte-identical; P2–P4 record byte-unchanged. NOTE: P3 §8 F4-scale numbers stale by +197 sections / +2.42M words — recompute at F4 prep | `data/f3/status/P5_fixes.md` |
| P4 | Red-team pass + F3 report + owner-visible items | red-team-reviewer (Opus) | **DONE 2026-08-27 ~14:35** — 2 BLOCKING / 3 major / 6 moderate / 7 minor. Blocking: (1) P3's F2 fix would CORRUPT the corpus as ranked (70/148 defensible; F1-first + scoped-F2-with-span-guards is the correct order); (2) 779 EXPECTED_ABSENT rows never censused under the same defective TOC code — est. 61–179 recoverable (Wilson [7.9%,23.0%] on 80-row replay) = the one silent-drop mechanism found. 4 P3 claims broke on recompute (incl. N1 class is ≥5 rows not 4 — 5th garbled row invisible to BOTH proposed screens). HELD: flag-never-filter (exact), no survivorship, F4-scale table reproduces to the row, frozen QA draw byte-identical, charter clean (0 GETs / 0 API). NEW RISK: population-gate cols embed within-quarter hindsight (726 rows flagged solely by later-dated filings) — F4/F5 must NOT condition on them naively. Owner-visible items list at report end | `data/f3/status/P4_redteam.md` |

## P0 brief (relaunch verbatim if needed)

Read: this file top to bottom → `HANDOFF.md` §3 (2026-08-26 entry) +
§4/§7 → `EXPANSION_PLAN.md` §4 F3 + §5 F3 coupling + §8 →
`data/hardening/status/H4_docsample.md` (the gate evidence + 155-row
ledger) → `extract.py` and its tests → `data/F2_INGESTION_REPORT.md`
§5. Produce `data/f3/F3_SPEC.md`: exact extract.py changes (E2 DB
input, per-form section targets, the population gate per binding input
1 — including the re-measured narrowed-signature recall on the H4
ledger, 8K_BODY item-anchored slicing, dilution handling); the audit
artifacts F3 emits (per-section confidence/failure taxonomy, per-filer
rollup); floors/ceilings recalibration PLAN (measured-from-distribution,
never silent); the manual-QA protocol WITH its stopping rule written
before any read; run segmentation for ~23k sections (resumable,
main-session, estimated wall-clock); tests; the F4-scale re-derivation
method. Lazy-elite: extend extract.py, no framework. Zero GETs
(everything cached). Write the spec + `data/f3/status/P0_spec.md`
before returning; the main session reviews before P1.
