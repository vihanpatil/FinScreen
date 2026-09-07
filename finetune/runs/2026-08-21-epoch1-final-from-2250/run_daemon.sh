#!/bin/bash
# Daemon wrapper for the epoch1 final-remainder training run (2026-08-21).
# Launched via a python double-fork (new session, PPID 1) because harness-
# owned background tasks were SIGTERMed three times on unpredictable
# session-lifecycle triggers (HANDOFF §4). Writes EXIT_STATUS + a
# TRAINING_DONE marker so the orchestrator can watch the filesystem instead
# of owning the process. To stop manually: kill the mlx_lm.lora PID in
# DAEMON_PID (checkpoints every 250 iters make this safe).
set -u
RUN_DIR="/Users/vihanpatil/personal/projects/FinScreen/finetune/runs/2026-08-21-epoch1-final-from-2250"
echo "$$ $(date '+%F %T')" > "$RUN_DIR/DAEMON_PID"
caffeinate -dims /Users/vihanpatil/personal/projects/FinScreen/finetune/.mlx_venv/bin/mlx_lm.lora \
  -c "$RUN_DIR/mlx_lora_config.yaml" >> "$RUN_DIR/launcher.log" 2>&1
EC=$?
echo "$EC $(date '+%F %T')" > "$RUN_DIR/EXIT_STATUS"
touch "$RUN_DIR/TRAINING_DONE"
exit $EC
