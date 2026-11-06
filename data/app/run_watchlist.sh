#!/bin/bash
# Resumable watchlist build: one `bin/fs report TICKER` at a time (CLAUDE.md rule 6), in
# watchlist order. Re-running is safe: tickers with a "done" line in the status file are
# skipped, and `bin/fs report` itself skips ingest/labeling that is already current.
# Resume: `bash data/app/run_watchlist.sh` (background). Log: data/app/status/WATCHLIST_BUILD.log
# Refresh (post-earnings, run by data/app/launchd/): `--refresh` archives the done-ledger
# first and runs `bin/fs report TICKER --refresh` for every ticker, which re-ingests the
# store from EDGAR (the newest filings per form) and labels only passages not yet labeled.
# One chain at a time: the lock dir data/app/status/.chain.lock (pid inside) is taken at
# start and removed on exit; after a crash remove it by hand: rm -r data/app/status/.chain.lock
# FS_SKIP_PROCESS_GUARD=1 is TEST-ONLY (test_run_watchlist.py); never set it for real runs.
cd "$(dirname "$0")/../.." || exit 1
LIST=data/app/watchlist.txt
DONE=data/app/status/WATCHLIST_DONE.tsv      # ticker <tab> exit <tab> seconds <tab> finished-at
LOG=data/app/status/WATCHLIST_BUILD.log
LOCK=data/app/status/.chain.lock
mkdir -p data/app/status
if [ $# -gt 1 ] || { [ $# -eq 1 ] && [ "$1" != "--refresh" ]; }; then
  echo "$(date -u +%FT%TZ) REFUSED: usage: bash data/app/run_watchlist.sh [--refresh] (got: $*)" | tee -a "$LOG" >&2; exit 2
fi
REFRESH_FLAG=${1:-}
if [ ! -x bin/fs ]; then
  echo "$(date -u +%FT%TZ) REFUSED: bin/fs missing or not executable in $(pwd)" | tee -a "$LOG"; exit 2
fi
if ! mkdir "$LOCK" 2>/dev/null; then
  echo "$(date -u +%FT%TZ) REFUSED: another chain holds $LOCK (pid $(cat "$LOCK/pid" 2>/dev/null || echo unknown))" | tee -a "$LOG"; exit 2
fi
echo $$ > "$LOCK/pid"
trap 'rm -f "$LOCK/pid"; rmdir "$LOCK"' EXIT
if [ -z "${FS_SKIP_PROCESS_GUARD:-}" ] && pgrep -fl "[Pp]ython[^ ]* ([^ ]*/)?(label_filing|label_e2|ingest_one)\.py" >/dev/null; then
  echo "$(date -u +%FT%TZ) REFUSED: a labeling/ingest process is alive" | tee -a "$LOG"; exit 2
fi
if [ -n "$REFRESH_FLAG" ] && [ -s "$DONE" ]; then
  ARCH=data/app/status/archive/WATCHLIST_DONE_$(date -u +%Y%m%dT%H%M%SZ).tsv
  mkdir -p data/app/status/archive && mv "$DONE" "$ARCH"
  echo "$(date -u +%FT%TZ) refresh: archived previous ledger to $ARCH" | tee -a "$LOG"
fi
touch "$DONE"
echo "$(date -u +%FT%TZ) chain start pid $$${REFRESH_FLAG:+ $REFRESH_FLAG}" >> "$LOG"
grep -v '^#' "$LIST" | grep -v '^\s*$' | while read -r T; do
  if awk -F'\t' -v t="$T" '$1==t && $2==0{f=1} END{exit !f}' "$DONE"; then
    echo "$(date -u +%FT%TZ) $T already done; skipped" >> "$LOG"; continue
  fi
  S=$(date +%s)
  echo "$(date -u +%FT%TZ) $T start" >> "$LOG"
  bin/fs report "$T" $REFRESH_FLAG >> "$LOG" 2>&1 < /dev/null; RC=$?
  printf '%s\t%s\t%s\t%s\n' "$T" "$RC" "$(( $(date +%s) - S ))" "$(date -u +%FT%TZ)" >> "$DONE"
  echo "$(date -u +%FT%TZ) $T exit $RC" >> "$LOG"
done
echo "$(date -u +%FT%TZ) chain end" >> "$LOG"
