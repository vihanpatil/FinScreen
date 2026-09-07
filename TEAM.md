# TEAM — the FinScreen TIGER team

**Established 2026-08-24** (owner, in chat). A standing roster of
specialist Claude agents covering every responsibility this project has,
each defined in `.claude/agents/<name>.md`. This file is the org chart;
the agent files are the job descriptions.

## Model tiering (owner policy, 2026-08-20, reaffirmed 2026-08-24)

- **Fable 5 — main session only**: planning, orchestration, verification,
  owner communication, ledger upkeep. Fable does not do brunt work.
- **Opus 5**: execution — all engineering, research, review work.
- **Sonnet 5**: the simplest delegations — mechanical, checklist-driven
  tasks with clear escalation rules.

## Engineering philosophy: lazy-elite programming (owner, 2026-08-24)

Simple, readable, easy-to-understand core logic. No over-engineering —
the minimal work necessary to work correctly and as well as it can.
Correct and low-latency beats clever. Extend existing modules rather than
building frameworks. Every agent file carries this; every review checks
for it in both directions (bugs AND needless complexity).

## Roster

| Role | Agent | Model | Owns |
|---|---|---|---|
| Planner / orchestrator / verifier | (Fable 5, main session — no agent file) | Fable | Phases, gates, owner comms, `F2_PROGRESS.md`-class ledgers |
| Data engineering | `data-engineer` | Opus | EDGAR ingestion, extraction plumbing, storage, universe artifacts; F2 (S1–S5) |
| Extraction QA | `extraction-qa-engineer` | Opus | F3: extract.py at scale, per-filer triage, floor/ceiling recalibration |
| ML / fine-tune engineering | `finetune-engineer` | Opus | `finetune/`, MLX QLoRA, evals, F4 labeling-campaign implementation |
| Quant modeling | `quant-modeler` | Opus | features.py, backtest.py, numeric baseline; F5 under gate G3 |
| Research statistics | `research-statistician` | Opus | Power/MDE, fold structure analysis, diagnosis (diagnose.py, e2_report.py), verifying statistical claims |
| Test engineering / QA | `test-engineer` | Opus | pytest suites, tripwire re-pinning, regression tests per incident |
| Red team | `red-team-reviewer` | Opus | Adversarial review: look-ahead, survivorship, overfitting, overstated claims |
| Compliance | `compliance-officer` | Sonnet | Charter/spend/provenance/license checklist audits |
| Documentation | `docs-writer` | Opus | README, MODEL_CARD, LIMITATIONS — honest-limitations discipline |
| Ops scribe | `ops-scribe` | Sonnet | Mechanical doc upkeep: status flips, file maps, run/checkpoint inventories |
| Tech council (C-suite advisory) | `tech-council` | Fable (spawn with model=fable; added 2026-08-25 at owner request) | Five-seat advisory panel (CEO/CTO/research/risk/cost) for high-stakes decisions, phase gates, pivots. Advisory only — never the owner's judgment |
| Label second-rater | `label-auditor` | Opus | Blind re-judging of labels (ratified protocol 2026-08-11 — **file untouched by the 2026-08-24 refresh**; G2 reuse gets its own addendum at F4) |
| Label adjudicator | `label-adjudicator` | inherit | Third-rater dispute resolution (ratified 2026-08-18 — **file untouched**) |

## Common operating protocol (embedded in every refreshed agent file)

1. **Read first, every task**: `HANDOFF.md` (state + §7 hard rules) →
   `EXPANSION_PLAN.md` (E2 plan of record) → `F2_PROGRESS.md` when doing
   F2 work. Files on disk beat any prior-session summary.
2. **Hard constraints, always**: no Anthropic API spend, ever; long
   compute (>~15 min) is never run inside an agent's own shell — design
   it resumable, hand it to the main session (HANDOFF §4); loud failures
   over silent fallbacks; every number reported with how it was measured;
   model judgments are never recorded as the owner's.
3. **Resumability**: before returning, write your completion report to
   the path your brief names (F2: `data/f2/status/`). The report on disk
   is the resume state if a session dies at the owner's token limit.
4. **When stuck or misaligned**: escalate to the main session, which asks
   the owner. The owner has explicitly offered to be a resource — use
   them for genuine decision points, not routine judgment.

## Roles deliberately NOT created

- Marketing/sales/promotion — the charter forbids promotional performance
  claims (HANDOFF §1); a role whose job is promotion would fight the
  charter.
- Trading operations/brokerage integration — charter-prohibited,
  unconditionally.
- Legal — license checks sit with `compliance-officer`; real legal calls
  belong to the owner.
