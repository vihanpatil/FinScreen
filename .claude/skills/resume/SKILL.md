---
name: resume
description: Resume FinScreen in a fresh session — read the state block, check for live processes, run the environment doctor, and report what is in flight and what the owner owes. Use at the start of any session on this repo, or when the user says "resume", "where were we", "pick this back up".
---

Do these in order, then report in under 15 lines.

1. Read `CLAUDE.md`, then the top block of `RESUME_HERE.md` (down to the first
   "PREVIOUS" heading). The IN FLIGHT table and the "owner owes" list there are the state.
2. `pgrep -fl "label_filing|label_e2|ingest_one|mlx_lm|run_campaign"` — if anything is
   alive, say so and do not start a second labeling or training process.
3. `bin/fs doctor` — paste its FAIL/WARN lines, if any.
4. `git status -sb` and `git log --oneline -5` — note anything uncommitted or unpushed.
5. For each IN FLIGHT row whose expected output is missing and whose agent is not running,
   relaunch it exactly as the row says (never hand-build it in the main session).
6. Report: what is done since the last block, what is running, what the owner owes (money,
   public surfaces, the word "ratify", direction), and the one next step. Then do that step
   unless it is the owner's.
