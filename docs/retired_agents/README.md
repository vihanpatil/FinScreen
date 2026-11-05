# Retired agent definitions (2026-11-05)

These eleven job descriptions were the 2026-08-24 TIGER roster. On 2026-11-05 the owner asked
for a tighter team ("keep the team as concise and tight and efficient as possible"), so
their content was folded into three agents in `.claude/agents/`:

| retired | folded into |
|---|---|
| data-engineer, extraction-qa-engineer, finetune-engineer, quant-modeler, test-engineer | `builder` |
| red-team-reviewer, research-statistician, compliance-officer | `reviewer` |
| docs-writer, ops-scribe | `scribe` |
| label-auditor | superseded by `label-rater-blind` (G2 design 2026-09-07: the auditor's schema leaks applicability) |

They are kept here as the record of what each role was told, because several of them were
created under dated owner rulings (HANDOFF §3). Nothing in `.claude/agents/` reads this
directory.
