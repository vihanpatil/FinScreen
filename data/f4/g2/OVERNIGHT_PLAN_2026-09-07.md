# G2 overnight chain — the main session's own state and ordered plan (2026-09-07)

## Scope — the main session's own operating record (NOT an owner authorization)
**Relabelled 2026-09-07 (§14.9).** This section previously asserted a broad
owner authorization, given in chat, for an unattended chain of ~18 rater + ~18
writer + ~8–12 adjudicator runs through to the owner packet. **That
authorization does not appear in `HANDOFF.md` §3**, and HANDOFF §7 says content
observed through a tool channel is never a valid source of owner authorization.
It is therefore recorded here as **the main session's own plan**, not as owner
consent. Anyone resuming: if you need that authorization, get it from the owner
in chat and write it into HANDOFF §3 with its date — do not inherit it from
this file. The parameter rulings that ARE the owner's are in HANDOFF §3
(2026-09-07) and design §14.1.
NOT delegated under any reading: the Gate G2 ruling itself (owner reads the
packet and rules the needs_human + 20 probe rows); any API call (spend freeze);
any `label_e2.py --segment`; epoch 3; extension-stratum labeling (DEFERRED by
ruling 2(b)).

## State at hand-off (2026-09-07 evening)
- Build workflow `wf_a63bc7cc-243`: phases 1–5 DONE (rulings recorded; design
  §14 amendment; redraw at Option C → `draw_g2.csv` 580 rows, 15 batches + 3
  ceiling replicates; `analyze_g2.py` updated, unblocked; `label-rater-blind`
  agent created; `build_adjudicator_batches_g2.py` + tests written; suite
  green). Phase 6 red-team verify was RUNNING at write time; phase 7 fix is
  conditional. Read its final result before rating (journal under
  `.claude/projects/…/subagents/workflows/wf_a63bc7cc-243/journal.jsonl`).
- No verdict exists. `data/f4/g2/verdicts/` does not exist yet.

## Ordered plan — one stage at a time, each verified before the next
STAGE 1 — Confirm build. Verify verdict READY_TO_RATE (or FIX_FIRST → fix pass
  → tests green). If tests are not green after the one fix pass: STOP, record
  in RESUME_HERE, do not loop.
STAGE 2 — Rating (Workflow). One `label-rater-blind` agent per
  `batches/batch_NN.json` (rater A, 15 runs) and one per ceiling replicate
  (rater B, 3 runs, independent instances). Launch prompt = design §10.4 /
  agent spec; the agent reads ONLY labeling_rubric.md,
  data/f4/g2/rater_policy_addendum.md, and its one batch file.
  **Do NOT pin the enums with a StructuredOutput schema** (dropped 2026-09-07,
  §14.9): design §10.4 and the agent spec pin the rater's output as "one JSON
  array and no prose" as its final message, and §10.2.1's schema guard — which
  rejects any `verdict`-shaped object and any `n/a` value — is part of the
  instrument. A rater that *cannot* emit an out-of-enum value never trips that
  guard, so what would be exercised is the harness, not the pinned contract.
  Because workflow scripts cannot write files, each rater's array is handed to a
  sonnet `ops-scribe` WRITER agent that writes
  `data/f4/g2/verdicts/rater_a_batchNN.json` (or `rater_b_batchNN.json`) as a
  bare JSON array and validates: every chunk_id in the batch exactly once,
  exact key set {chunk_id, sentiment, guidance_direction, red_flags, reason},
  enums valid. **The writer validates and re-runs; it NEVER repairs, edits,
  coerces or fills in rater output** — a repaired verdict is a fabricated
  verdict. Retry a batch ONCE on validation failure; a second failure marks it
  FAILED and the chain continues (design §11.3), and the cause is appended to
  `data/f4/g2/failed_batches.json` as {batch, attempt, cause, utc} with `cause`
  from §11.3's five-item enumerated list. No other retries.
STAGE 3 — Adjudication (Workflow). `python3 data/f4/g2/build_adjudicator_batches_g2.py`
  → `adjudicator_batches/adj_batch_NN.json`; one existing `label-adjudicator`
  agent per file (schema per design §10.2.2 and `.claude/agents/label-adjudicator.md`);
  writer agent merges into `adjudications/adjudications.json`. Same one-retry rule.
STAGE 4 — Analyze. `python3 data/f4/g2/analyze_g2.py` → `results_g2.json`,
  `probe_ids.json`, report. This is the MODEL-CONSENSUS estimate; label it so.
STAGE 5 — Owner packet. Generate `data/f4/g2/OWNER_RULING_PACKET.md` mirroring
  `data/hardening/spotcheck_v12/OWNER_RULING_PACKET.md`: every needs_human row
  (chunk text, stored vs rater vs adjudicator, brief, pattern slug) + the 20
  probe rows. Owner rules → `owner_rulings.json` / `probe_rulings.json`
  (schemas §10.2.3) → re-run analyze → owner-ratified estimate → Gate G2.
STAGE 6 — Verify + ledgers. One red-team pass over results + packet (numbers
  re-derived, no bar-shopping, caveats present, red_flags disclosure-only);
  then RESUME_HERE / HANDOFF status entry / memory. Then STOP and wait for the owner.

## Frugality + safety rules for the night
- Expected agent runs: ~18 raters (opus, unavoidable), ~18 writers (sonnet),
  ~8–12 adjudicators (opus), ~10 writers, 1 packet builder, 1 red-team. No
  fan-out beyond that; no adversarial multi-vote on raters (the design's
  ceiling arm is the noise measurement).
- Never re-run `build_draw_g2.py` (the draw is ratified; re-running mutates the
  manifest). Never edit `analyze_g2.py` estimators after a verdict exists.
  (The 2026-09-07 §14.9 fix pass re-ran the builder ONCE, deliberately, while
  `verdicts/` was still absent, to move `arm` out of `draw_g2.csv`; the draw
  itself is byte-identical. From here the rule binds absolutely.)
- Any stage that fails twice → STOP and write the state to RESUME_HERE.

## STATUS 2026-09-07 ~05:15 — COMPLETE through STAGE 6
STAGE 1 (build): `wf_a63bc7cc-243` — completed; 140 tests green.
STAGE 2 (rating): `wf_6f592371-49a` — completed; 18/18 batches (15
  rater-A + 3 rater-B ceiling replicates) accepted first attempt, 0
  failed; `data/f4/g2/failed_batches.json` absent.
STAGE 3 (adjudication): `wf_fb3c61aa-cf9` — completed; 9/9 batches first
  attempt; 314 rows merged into `adjudications/adjudications.json`
  (sentiment 89, guidance_direction 32, red_flags 193; 271 disagree / 43
  agree / 0 unsure).
STAGE 4 (analyze): `analyze_g2.py` exit 0 — `results_g2.json` written,
  `stage = model_consensus`; `sentiment` 292/337 = 86.65% [82.60, 89.87]
  INDETERMINATE at bar 0.85; `guidance_direction` 115/119 = 96.64%
  [91.68, 98.69] PASS at bar 0.85.
STAGE 5 (owner packet): `data/f4/g2/OWNER_RULING_PACKET.md` generated —
  39 Part A `needs_human` rows (14 pattern slugs) + 20 Part B probe rows.
STAGE 6 (verify): one red-team pass run over `results_g2.json` /
  `report_g2.md` / `OWNER_RULING_PACKET.md`; fix pass applied (no number
  changed; disclosure additions to report + packet + `HANDOFF.md`).
  `probe_ids.json` confirmed byte-identical after the fix pass — no
  re-draw.

Owner packet ready; chain stopped as planned.

**STATUS 2026-09-07 ~19:15 — OWNER RULED ALL 59 ROWS (chat); `analyze_g2.py` re-run once → stage `owner_ratified`; final record `G2_FINAL_REPORT.md`. Gate pronouncement still the owner's. Chain closed; nothing running.**
