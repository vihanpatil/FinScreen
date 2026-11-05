# TEAM — the FinScreen roster (tightened 2026-11-05)

**History.** The TIGER team of fourteen agents was established 2026-08-24 (owner, in chat).
On 2026-11-05 the owner, resuming after two months away, asked for the team to be kept
"as concise and tight and efficient as possible" with "more modern skills" and for maximum
automation. Eleven job descriptions were folded into three (record and mapping:
`docs/retired_agents/README.md`); the shared operating protocol every agent used to carry
now lives once, in `CLAUDE.md`, which Claude Code loads into every session automatically.

## Model tiering (owner policy, 2026-08-20, unchanged)

- **Fable — the main session**: planning, orchestration, verification, owner communication,
  ledgers. Fable does not do brunt work.
- **Opus**: execution — engineering and review.
- **Sonnet**: the simplest chores with clear stop rules.

## Roster (7)

| Role | Agent | Model | Owns |
|---|---|---|---|
| Planner / orchestrator / verifier | (main session, no file) | Fable | phases, gates, owner packets, `RESUME_HERE.md` and `HANDOFF.md` |
| Engineering, all of it | `builder` | Opus | ingestion, extraction, the MLX labeler and its tooling, features and the guarded runners, the app lane (`ingest_one`, `label_filing`, `report_filing`, `finscreen.py`), the pytest suites |
| Adversarial review | `reviewer` | Opus | look-ahead / survivorship / overfitting, statistical re-derivation, charter-spend-provenance-licence checklist, complexity findings |
| Documentation chores | `scribe` | Sonnet | ledger flips, README / MODEL_CARD / LIMITATIONS updates from supplied facts, inventories |
| Legal review (advisory) | `legal-reviewer` | Fable (`model: inherit`, spawn from the main session) | every public surface, disclosure, vendor and model licence before anyone but the owner touches the tool (owner ruling E, 2026-09-11). A language model, not a lawyer; says so on every memo |
| Tech council (advisory) | `tech-council` | Fable (`model: inherit`) | five-seat counsel before owner-level decisions and gates; never the owner's judgment |
| Blind label rater | `label-rater-blind` | Opus | the G2 spot-check protocol (owner-ruled 2026-09-07) for any new label population |
| Label adjudicator | `label-adjudicator` | inherit | third-rater dispute resolution (owner-ruled 2026-08-18) |

## Skills (project slash commands, `.claude/skills/`)

| skill | what it does |
|---|---|
| `/resume` | the fresh-session protocol: read the top block, check for live processes, run `bin/fs doctor`, report what is in flight and what the owner owes |
| `/report TICKER` | the product in one command: ingest → fundamentals → label → HTML reports, opened in the browser |
| `/g3-run` | the pre-registration pin and head runs — refuses without the owner's literal word "ratify" and that day's date |

## Common protocol (now in `CLAUDE.md`; summary)

Read `CLAUDE.md` → the brief → the status file the brief names. No API spend; no two
labeling processes; long compute from the main session only; every number with its
measurement; model judgments never recorded as the owner's; completion report on disk
before returning. Owner touchpoints follow the low-touch policy in `CLAUDE.md`.

## Roles deliberately not created

Marketing (the charter forbids promotional performance claims); trading operations or
brokerage integration (charter-prohibited); a human-lawyer substitute (the `legal-reviewer`
is advisory and says so; real legal calls are the owner's and an attorney's).
