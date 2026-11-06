# Watchlist refresh (launchd user agent)

`com.finscreen.watchlist-refresh.plist` runs `data/app/run_watchlist.sh --refresh` on the
1st and 15th of every month at 03:00 local time, under `caffeinate -dims` so the Mac does
not idle-sleep mid-run. Refresh mode archives the done-ledger
(`data/app/status/WATCHLIST_DONE.tsv` → `data/app/status/archive/WATCHLIST_DONE_<UTC>.tsv`)
and runs `bin/fs report TICKER --refresh` for every ticker in `data/app/watchlist.txt`, one
at a time. `--refresh` re-ingests each store from EDGAR (the newest two filings per form,
submissions cached at most 24 h) and refreshes its fundamentals; labeling then runs only if
the chunk table changed, and the labeler's journal skips passages it has already labeled, so
only passages from newly filed reports cost GPU time. The store keeps a rolling window: a
filing that falls out of the newest two leaves the store (its old HTML page stays on disk).
If a labeling/ingest process is alive at 03:00, or another chain holds the lock, the chain
refuses (exit 2, logged) and leaves the ledger alone; the next scheduled run tries again.
It is not installed by default.

Install (copy into LaunchAgents, then load):

    cp /Users/vihanpatil/personal/projects/FinScreen/data/app/launchd/com.finscreen.watchlist-refresh.plist ~/Library/LaunchAgents/
    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.finscreen.watchlist-refresh.plist

Uninstall:

    launchctl bootout gui/$(id -u)/com.finscreen.watchlist-refresh
    rm ~/Library/LaunchAgents/com.finscreen.watchlist-refresh.plist

Run it now (manual trigger, once installed):

    launchctl kickstart -k gui/$(id -u)/com.finscreen.watchlist-refresh

Logs: the chain's own log is `data/app/status/WATCHLIST_BUILD.log` (per-ticker start/exit
lines and `bin/fs` output); launchd's stdout/stderr go to `data/app/status/launchd.out.log`
and `data/app/status/launchd.err.log`. Check status with
`launchctl print gui/$(id -u)/com.finscreen.watchlist-refresh`.

If the Mac is asleep at 03:00, launchd runs the job at the next wake; if it is shut down,
that run is skipped until the next scheduled date. If you edit the plist, `bootout`,
re-copy it, and `bootstrap` again.

One chain at a time: `run_watchlist.sh` takes the lock directory
`data/app/status/.chain.lock` (the chain's pid is in `.chain.lock/pid`) and removes it on
exit. After a crash or a `kill -9` the lock stays behind and every later run refuses; check
the pid is gone, then remove it by hand:

    rm -r /Users/vihanpatil/personal/projects/FinScreen/data/app/status/.chain.lock
