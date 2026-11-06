#!/bin/bash
# Resumable watchlist build: one `bin/fs report TICKER` at a time (CLAUDE.md rule 6), in
# watchlist order. Re-running is safe: tickers with a "done" line in the status file are
# skipped, and `bin/fs report` itself skips ingest/labeling that is already current.
# Resume: `bash data/app/run_watchlist.sh` (background). Log: data/app/status/WATCHLIST_BUILD.log
cd "$(dirname "$0")/../.." || exit 1
LIST=data/app/watchlist.txt
DONE=data/app/status/WATCHLIST_DONE.tsv      # ticker <tab> exit <tab> seconds <tab> finished-at
LOG=data/app/status/WATCHLIST_BUILD.log
mkdir -p data/app/status; touch "$DONE"
if pgrep -fl "label_filing|label_e2|ingest_one" >/dev/null; then
  echo "$(date -u +%FT%TZ) REFUSED: a labeling/ingest process is alive" | tee -a "$LOG"; exit 2
fi
echo "$(date -u +%FT%TZ) chain start pid $$" >> "$LOG"
grep -v '^#' "$LIST" | grep -v '^\s*$' | while read -r T; do
  if awk -F'\t' -v t="$T" '$1==t && $2==0{f=1} END{exit !f}' "$DONE"; then
    echo "$(date -u +%FT%TZ) $T already done; skipped" >> "$LOG"; continue
  fi
  S=$(date +%s)
  echo "$(date -u +%FT%TZ) $T start" >> "$LOG"
  bin/fs report "$T" >> "$LOG" 2>&1; RC=$?
  printf '%s\t%s\t%s\t%s\n' "$T" "$RC" "$(( $(date +%s) - S ))" "$(date -u +%FT%TZ)" >> "$DONE"
  echo "$(date -u +%FT%TZ) $T exit $RC" >> "$LOG"
done
echo "$(date -u +%FT%TZ) chain end" >> "$LOG"
