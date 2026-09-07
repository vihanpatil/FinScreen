# RESUME_HERE — stopping point set 2026-09-06

**If you are a fresh session: read this file first** (then `HANDOFF.md`
for depth). **STATE AS OF 2026-09-06 ~15:30 — handoff written by the main session at the
owner's request (owner returns in a few hours).**

**STATE AS OF 2026-09-07 ~20:30 — GATE G2 RULED "PROCEED UNDER THE LADDER";
2(b) RULED "EXTEND (promotion waits on own spot-check)". NEXT PHASE = F5, plan
in `F5_PLAN.md`. NOTHING IS RUNNING. READ `data/f4/g2/G2_FINAL_REPORT.md` §1.**
- Owner ruled all 39 Part A + 20 Part B rows in chat 2026-09-07 (HANDOFF
  §3 "G2 OWNER ROW RULINGS RECORDED"); files `data/f4/g2/owner_rulings.json`
  + `probe_rulings.json`; analyzer re-run once → `results_g2.json` /
  `report_g2.md` stage `owner_ratified` (19 assertions, 0 API calls).
- `sentiment` 293/337 = 86.94% [82.93, 90.13] → INDETERMINATE at 0.85
  (k* PASS 300 / FAIL 273; A39 moved k 292→293).
- `guidance_direction` 115/119 = 96.64% [91.68, 98.69] → PASS at 0.85,
  never quotable without `guidance_active_precision` 68.67% [58.17, 77.55]
  (n_eff 84.8), `guidance_false_none_rate` 0/80 [0, 4.58], AND the owner's
  interpretation paragraph (`G2_FINAL_REPORT.md` §0: the 68.67% is partly
  directional-label precision under a rubric with no value for newly
  issued guidance — not evidence of hallucinated guidance).
- Probe 0/20 overturned → no sweep. `red_flags` 28.0% exploratory, unchanged.
- **Binding Rule 9 (owner):** new quantified guidance with no direction
  established relative to PRIOR guidance = NONE (`G2_FINAL_REPORT.md` §3).
- **RULED 2026-09-07 evening (HANDOFF §3):** Gate G2 = proceed under the
  ladder (no demotion); 2(b) = extend — extension labeling runs on nights
  AFTER the wrapper lock fix, and its labels are promoted into F5 only after
  their own spot-check. Rubric v1.3 change (ISSUED/INITIATED or
  `guidance_present`) recommended, not scheduled.
  DO NOT re-run any rater/adjudicator, the draw, or the analyzer
  (design §11; the owner-ratified stage is final).
- After the gate: F5 is blocked on design §3.4 (`features.py` must mask
  sentiment on RISK_FACTORS and guidance on MDA/RISK_FACTORS before
  aggregation) — not started.

**1. F4 — COMPLETE, integrity red-team-verified.** `data/f4/labels_e2_v1.parquet`
(317,081 rows, sha `f236f421…`), manifest `data/f4/campaign_manifest.json`.
Corrected close-out: `data/f4/status/F4_campaign.md` — read its §2 (the same
adapter behaves differently on E2 than on E1: flag incidence −9/−14/−7 pts by
section, guidance key omitted 33%→51%, sentiment emitted on 8.4% of
RISK_FACTORS) and §4 (seg-013 wrapper race, data intact; **2,826 rows carry
guidance on non-applicable sections → always filter `guidance_applicable`**).
Offline tests 118 green.

**2. G2 — OWNER-RATIFIED STAGE 2026-09-07 (see the STATE block above; gate pronouncement pending). The package below was built 09-06 and ratified 09-07; historical detail:** `data/f4/g2/`:
`G2_SPOTCHECK_design.md` (§13 = the owner menu), `build_draw_g2.py` (already
ran PROVISIONALLY at Option B → 420 chunks = P 300 + G-A 60 + G-N 60, seed
20260906, 11 blind batches + replicate; `draw_manifest.json.parameters_status
= PROVISIONAL_UNRATIFIED`), `analyze_g2.py` (selftest 59 checks; **exits 2
"BLOCKED" until `ratified_bars` is written — anti bar-shopping, do not
"fix"**), `finetune/test_g2_spotcheck.py` (20 tests).

**3. OWNER RULED 2026-09-07 (HANDOFF §3): Option C + direction floor + 15-row WITHDRAWN quota; bar 0.85 both fields; ladder ratified; no floors; ceiling n=120; guidance framing Option 1; council §7-3 "does not fire"; extension DEFERRED until G2 passes on core. Brief: data/f4/g2/G2_OWNER_BRIEF.md.**

**4. (HISTORICAL — this whole chain COMPLETED 2026-09-07; every file named below exists; do NOT re-run any step, design §11. Kept as the record of the planned order.) THEN, in order (design §10.3):** the redraw at Option C (re-running
`python3 data/f4/g2/build_draw_g2.py` for Option C; re-running at B is
pointless and mutates the manifest's `outputs` list — avoid) is being done
by the 2026-09-07 workflow; write the
rulings into `draw_manifest.json` per §10.2.3 → ship
`.claude/agents/label-rater-blind.md` (shipped 2026-09-07; body = design
§10.4 verbatim, ~30 lines; do NOT use `label-auditor`, its schema leaks
applicability) → write `data/f4/g2/build_adjudicator_batches_g2.py` (shipped 2026-09-07; mirror `data/hardening/spotcheck_v12/build_adjudicator_batches_v12.py`)
→ one blind rater per batch (11, plus batch_01_replicate as rater_b) →
`data/f4/g2/verdicts/rater_a_batchNN.json` → adjudicator →
`adjudications/adjudications.json` → `python3 data/f4/g2/analyze_g2.py`
(model-consensus estimate + `probe_ids.json`) → owner rules needs_human + the
20 probe rows → re-run analyze → owner-ratified estimate → **Gate G2**.

**5. DO NOT:** run `label_e2.py --segment` (nothing to label); launch any
rater before the §13 rulings; call any API (freeze re-sealed); quote the
manifest's 1,506.5 chunks/h (wrong — 1,455–1,461, see close-out §1). Lanes:
Fable plans/verifies, Opus executes (agent frontmatter already set), Sonnet
for ledger chores.

**UPDATE 2026-08-27 00:18: owner ruled epoch-2 GO and F3-P2 GO
(HANDOFF §3 2026-08-27). EPOCH 2 IS RUNNING** (run dir
`finetune/runs/2026-08-27-v12-epoch2/`, launched 00:18, ~9.2 h; on a
kill resume per `runs/2026-08-26-v12-epoch1/RESUME_RECIPE.md`, same
shape, tag `v12-epoch2-from-<N>`). **STATE AS OF 2026-08-27 ~13:10:** epoch 2 DONE (clean, val loss
0.076) · eval e2 DONE (sanity green — `runs/2026-08-28-v12-eval-epoch2/`,
red-flag macro F1 0.802) · **F3 P2 DONE 12:56** (28,900 sections, all
invariants held — `data/f3/status/P2_runs.md`) · **H3v2 full relabel
RUNNING** (~4.7 h from 13:05, log `data/hardening/h3v2/e1_relabel_v12.log`,
smoke passed 10/10 repro; resume = identical `relabel_e1.py --v12`
command; then `--v12 --finalize-only`) · **P3 QA agent IN FLIGHT**.
**OVERNIGHT CHAIN COMPLETE 2026-08-27 ~18:15. NOTHING RUNNING.
Everything is on disk awaiting the owner:**
- **G1 ruling package**: eval e2 `runs/2026-08-28-v12-eval-epoch2/`
  (beside `runs/2026-08-22-eval-epoch2/`); retention
  `data/hardening/status/H3v2_attenuation.md` §3 (family 0.6694 →
  0.8078 [0.7503, 0.8528], band inside CI; ~⅔ of the gain is the
  rubric per the 2×2; v1.2 teacher error UNMEASURED); council
  advisory `data/hardening/status/G1_council_advisory.md`
  (ACCEPT-WITH-CONDITIONS 5–0, sequencing split 3–2, §7
  pre-commitments proposed). Read LABEL_SHIFT first, as before.
- **F3 COMPLETE P0–P4** (`F3_PROGRESS.md`): corpus
  `data/filings_e2.parquet` 28,900 sections; P4's 2 blocking
  owner-visible items (`data/f3/status/P4_redteam.md` §11) are F4
  inputs, not G1 inputs.
- **RULED 2026-08-27 evening (HANDOFF §3): G1 = accept-with-
  conditions, B1; F4 config = W1-core + full reflow + missing→NONE
  at writer (≈314k chunks, 21–29 overnights).**
- **SPOTCHECK v1.2 COMPLETE AND OWNER-RULED same night: final P1 =
  84/200 = 42.00% [35.37, 48.93] — k exactly at the boundary →
  DEMOTE FIRED per the ratified pre-commitment. The E2 red-flag
  feature family is exploratory/disclosure-only in G3.** Sentiment/
  composition unaffected. Owner's 8 binding annotation-policy rules:
  `data/hardening/spotcheck_v12/OWNER_POLICY_RULINGS.md`. Probe
  0/20 overturns; campaign closed per its stopping rule. **B1
  SATISFIED. F4 scope RE-CONFIRMED post-demotion (owner, same
  night): KEEP W1-core + full reflow (~314k chunks, 21–29 nights).**
  **P5 DONE + verified. F4 PREP DONE + verified 2026-08-28 ~01:30**
  (105 tests green main-session-re-run; chunk table
  `data/f4/chunks_v1.parquet` sha `d67395ec…` — **317,081 chunks, 24
  accession-aligned chronological segments**; answer reserve 256;
  runner = `finetune/label_e2.py`, a sibling importing the
  byte-unchanged `relabel_e1.py`). **SMOKE PASSED ~01:40**: repro
  canary **10/10 byte-identical** to the G1 eval + all checklist
  items. **(HISTORICAL — campaign finished 2026-09-06)** **F4 CAMPAIGN IN PROGRESS — SELF-DRIVING since 2026-08-31 18:30:
  `data/f4/run_campaign_chain.sh` (a zero-model-turn shell loop,
  launched by the main session under the owner's Fable-outage
  continuity order) owns the chain for seg-011 → seg-024: it waits
  for the live segment process, then finalize→prepare→generate→
  finalize sequentially, resume-on-nonzero (5-attempt cap, halts
  safely), log `data/f4/campaign_chain.log`. CRITICAL: while the
  wrapper runs, NO ONE (model or human) may launch `label_e2.py
  --segment` manually — double-driving a segment corrupts its
  journal. If the wrapper died (`pgrep -f run_campaign_chain`),
  re-running the script resumes everything safely. Owner's phrase to
  restore normal supervision: "resume Fable operations."**
  Continuous chaining per owner ruling (nights-only hold offered,
  declined). Loop per
  `data/f4/RUN_COMMANDS.md` §5: prepare → background generate →
  finalize → next; resume = identical command; never from a
  subagent. **Progress: check `data/f4/segments/seg-0NN/manifest.json`
  (finalized = done) — seg-001 DONE 2026-08-28 08:50 (13,227/13,227,
  0 parse fails, 1 benign out-of-taxonomy enum recorded, 1,621.6
  ch/h → ~8 days continuous / ~20 nights at measured rate); seg-002
  launched 08:55.** Traps in `F4_prep.md`:
  chronological order is load-bearing; 12.9% of chunks come from
  FLAGGED sections (filterable by join, no exclusion ruled); 8K_BODY
  (790 chunks) not evaluable. **G1 is ruled by the owner
on the eval-e2 report + the H3v2 retention numbers** (beside
`runs/2026-08-21-eval-epoch1/` + `runs/2026-08-22-eval-epoch2/`;
read `data/hardening/LABEL_SHIFT_v11_v12.md` first).
Epoch-1 record + numbers: `HARDENING_PROGRESS.md`.
**OVERNIGHT AUTONOMY GRANTED (HANDOFF §3 2026-08-27 item 5):** the
chain above runs unattended to completion, incl. a tech-council G1
advisory and P4 after P3 if time allows. NOT delegated: the G1
ruling, API calls, live fetches, F4, epoch 3. A fresh session
resuming mid-chain: find the running/last task via `ps aux | grep -E
'mlx_lm|eval.py|extract.py|relabel_e1'` + each run dir's log, then
continue the sequence exactly as written here.

## State in one screen

- **E2 corpus: COMPLETE and verified** (F2 + F2.5 hardening). 45,632
  filings / 42 GB documents / 622,661 fundamentals rows / 1.96M price
  rows. Ledgers: `F2_PROGRESS.md`, `HARDENING_PROGRESS.md`.
- **G1 repair: labels bought, dataset staged, retrain epoch 1 RUNNING
  (launched 2026-08-26 12:07 on the owner's command).**
  Rubric v1.2 re-label complete — `data/labels_v12.parquet`,
  **6,747/6,747, zero gaps** (cost ~$24.92 + $0.0014; account has ~$5
  loaded; **spend freeze RE-SEALED** — any API call needs a new owner
  ratification). v1.2 splits/MLX data/configs all built and sha-pinned;
  label-shift record at `data/hardening/LABEL_SHIFT_v11_v12.md`.
- **F3 extraction: code DONE (P1), runs (P2) NOT started.** Ledger:
  `F3_PROGRESS.md`.
- **Stopping rule: RATIFIED** (Option 1 + margin procedure — HANDOFF §3
  2026-08-26). **Gate G1: HELD** — ruled by the owner after the
  retrain's re-eval.

## Campaign 1 — the v1.2 RETRAIN (launch on the owner's command)

**The entire campaign is copy-paste from
`finetune/runs/2026-08-26-v12-epoch1/RUN_COMMANDS.md`** (sections 0–6:
pre-flight with expected test counts → epoch 1 → eval 1 → OWNER READ →
epoch 2 → eval 2 → OWNER RULES G1). ~9.2 h per epoch + ~57 min per
eval ≈ 20.2 h machine time total, $0, zero API calls.

Non-negotiables baked into the runbook: training runs as a
MAIN-SESSION background auto-resume chain (HANDOFF §4 — never from a
subagent; on a kill, re-run the identical command; if segmented, point
`--train-manifest` at the LAST segment's manifest — the one real trap,
documented in RUN_COMMANDS §8). The training instruction is FROZEN at
E1's (`ebc45a85…`) — the v1.2 change is the LABELS ONLY (single-axis;
see `data/hardening/status/G1_repair_dataset.md` for why the
instruction must not be swapped).

**For the owner's G1 read** (after eval 2): put the new reports beside
`runs/2026-08-21-eval-epoch1/` + `runs/2026-08-22-eval-epoch2/` — same
epochs, same frozen 1,010 rows, same instruction, different rubric.
Read `data/hardening/LABEL_SHIFT_v11_v12.md` first; note especially
that the REALIZED liquidity-stress class the owner emptied at the E1
spot-check repopulated to 15 under v1.2 (P2 was deliberately not
encoded — flagged in `labeling_rubric.md` §9).

## Campaign 2 — F3 P2 extraction runs (also awaiting go)

Four commands, in `F3_PROGRESS.md` + `data/f3/status/P1_impl.md`:
`extract.py --segment earnings` (~21 min) → `--segment 10-K` (~45–75)
→ `--segment 10-Q` (~55–90) → `--merge`. Main-session background
tasks, resume = identical command, `cache_miss` must be 0 (nonzero =
FATAL stop, never a fetch). **Do NOT run concurrently with training**
— both compete for the same 16 GB M5; sequence them (extraction fits
easily before or after a training night).

## Owner decisions pending (nothing else blocks)

1. ~~Go for Campaign 1~~ — **GIVEN 2026-08-26; epoch 1 running.** The
   epoch-1 → epoch-2 step remains its own owner gate (RUN_COMMANDS §4).
2. After its re-eval: **the G1 ruling** on the repaired labeler.
3. Go for Campaign 2 (F3 P2) — sequenced around training.

## Standing constraints (verify at HANDOFF §4/§5/§7 before acting)

No Anthropic API calls (freeze re-sealed; ~$5 balance is NOT
authorization). Long compute = main-session chain only. E1 artifacts
frozen (incl. `data/labels.parquet`, `finetune/splits/`,
`data/filings_metadata.db`). Model tiering: Fable orchestrates, Opus
executes, Sonnet simplest. Lazy-elite engineering. Every ledger flip
needs its on-disk completion report.

## Ledger map

`HANDOFF.md` (charter + decision log §3) · `EXPANSION_PLAN.md` (+§8
amendments) · `REEVALUATION_2026-08-25.md` (the honest verdict) ·
`HARDENING_PROGRESS.md` (F2.5 + G1 repair campaign) · `F2_PROGRESS.md`
· `F3_PROGRESS.md` · `TEAM.md` (agent roster; `tech-council` for
big decisions) · `PRIOR_WORK.md` (citations unverified) · run docs in
`finetune/runs/2026-08-26-v12-epoch1/`.
