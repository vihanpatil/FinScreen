#!/bin/bash
# F4 campaign self-driving chain — written and launched by the MAIN SESSION
# 2026-08-31 under the owner's Fable-outage continuity order ("use an agent /
# continue everything until I say resume Fable operations"). Implemented as a
# zero-model-turn shell loop instead of a model agent: usage exhaustion stops
# model calls, not running OS processes, so this survives the outage window.
#
# Behavior: waits for the currently-running segment process (launched
# separately) to exit, then drives seg-011..seg-024 sequentially:
# finalize-if-complete -> prepare -> generate (resume-by-identical-command on
# nonzero exit, max 5 attempts) -> finalize. Idempotent per label_e2.py
# semantics; a SIGTERM at any instant loses at most one in-flight row and the
# whole chain is resumable by re-running this script.
FS=/Users/vihanpatil/personal/projects/FinScreen
F4=$FS/data/f4
VP=$FS/finetune/.mlx_venv/bin/python
LOG=$F4/campaign_chain.log
log(){ echo "[$(date '+%F %T')] $*" >> "$LOG"; }

log "chain wrapper started (pid $$)"

# 1. never double-drive: wait for any live segment process to exit first
while pgrep -f 'label_e2.py --segment' >/dev/null 2>&1; do sleep 60; done
log "no live segment process; wrapper owns the chain from here"

for i in $(seq 11 24); do
  SEG=$(printf 'seg-%03d' "$i")
  DIR=$F4/segments/$SEG
  mkdir -p "$DIR"
  if [ -f "$DIR/labels_$SEG.parquet" ]; then
    log "$SEG already finalized; skipping"
    continue
  fi
  # finalize handles the case where a prior process completed generation but
  # nothing finalized (e.g. seg-011 finishing during the outage)
  if python3 "$FS/finetune/label_e2.py" --finalize-segment "$SEG" >> "$LOG" 2>&1; then
    if [ -f "$DIR/labels_$SEG.parquet" ]; then log "$SEG finalized from existing journal"; continue; fi
  fi
  python3 "$FS/finetune/label_e2.py" --prepare-segment "$SEG" >> "$LOG" 2>&1 || { log "FATAL: prepare $SEG failed; halting"; exit 1; }
  tries=0
  while true; do
    log "$SEG generate attempt $((tries+1))"
    caffeinate -dims "$VP" "$FS/finetune/label_e2.py" --segment "$SEG" >> "$DIR/seg.log" 2>&1
    rc=$?
    log "$SEG generate exit $rc"
    [ "$rc" -eq 0 ] && break
    tries=$((tries+1))
    if [ "$tries" -ge 5 ]; then log "FATAL: $SEG failed $tries attempts; halting chain safely (everything resumable)"; exit 1; fi
    sleep 30
  done
  python3 "$FS/finetune/label_e2.py" --finalize-segment "$SEG" >> "$LOG" 2>&1 || { log "FATAL: finalize $SEG failed; halting"; exit 1; }
  log "$SEG finalized"
done
log "CAMPAIGN CHAIN COMPLETE (seg-011..seg-024 all finalized)"
