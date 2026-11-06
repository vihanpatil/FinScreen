# Watchlist post-earnings refresh + guard-regex fix — builder report (2026-11-05/06)

Not committed. Not installed (nothing under ~/Library touched). No `bin/fs report`, labeler or ingest run.

## Files
| file | lines | change |
|---|---|---|
| data/app/run_watchlist.sh | 37 (was 25) | `--refresh` (archive non-empty WATCHLIST_DONE.tsv to `data/app/status/archive/WATCHLIST_DONE_<UTC %Y%m%dT%H%M%SZ>.tsv`, log "refresh: archived previous ledger to …"); exit 2 + logged REFUSED if `bin/fs` missing/not executable; `FS_SKIP_PROCESS_GUARD=1` test-only bypass; guard regex tightened (below). Plain mode otherwise unchanged (chain-start line gains " --refresh" only in refresh mode). Every write was `.new` + `bash -n` + `chmod +x` + `mv`. |
| data/app/launchd/com.finscreen.watchlist-refresh.plist | 46 | LaunchAgent: `/bin/bash <repo>/data/app/run_watchlist.sh --refresh`; Day 1 and Day 15 at 03:00; WorkingDirectory = repo; PATH = /usr/bin:/bin:/usr/sbin:/sbin:/Library/Developer/CommandLineTools/usr/bin; ProcessType Background; no RunAtLoad; logs data/app/status/launchd.{out,err}.log. HOME not set (launchd provides it; needed for the user-site pandas). bin/fs uses absolute interpreter paths; finscreen.py shells out only to pgrep/ps/open (all on PATH). |
| data/app/launchd/README.md | 33 | what it does, install/uninstall/kickstart, logs, awake-at-03:00 note |
| test_run_watchlist.py | 99 | 6 tests (new) |
| finscreen.py | +7/-2 | LABELERS/BUSY regex (coordinator's mid-task item) |
| test_finscreen_cli.py | +18 | 7-case parametrized regression test for the guard regex (+ `import re`) |

`plutil -lint`: `data/app/launchd/com.finscreen.watchlist-refresh.plist: OK`

## Commands (for the owner)
Install:
    cp /Users/vihanpatil/personal/projects/FinScreen/data/app/launchd/com.finscreen.watchlist-refresh.plist ~/Library/LaunchAgents/
    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.finscreen.watchlist-refresh.plist
Uninstall:
    launchctl bootout gui/$(id -u)/com.finscreen.watchlist-refresh
Manual trigger:
    launchctl kickstart -k gui/$(id -u)/com.finscreen.watchlist-refresh
(Bootstraps the copied file rather than the repo path so the agent also reloads at login.)

## Incident 2026-11-06T03:10:55Z and guard fix
The running chain (pids 93074/93089) was alive immediately after my first `mv` (ps confirmed both).
At 03:10:55Z, after ADBE, `bin/fs report` refused NFLX…COST (18 tickers, exit 2, ~1 s each),
every refusal naming pid 13685 — another builder's `bash -c '… pgrep -fl "label_filing|label_e2|ingest_one" …'`
shell. The old script then ran to its "chain end" line normally. Ledger: 12 exit-0, 18 exit-2.
Cause: the bare-name pattern matched any command line containing the words.

Old regex (finscreen.py): `LABELERS = "label_filing|label_e2"`, `BUSY = LABELERS + "|ingest_one"`;
script: `pgrep -fl "label_filing|label_e2|ingest_one"`.
New regex (both places; script string == `fs.BUSY`, asserted by a test):
`[Pp]ython[^ ]* ([^ ]*/)?(label_filing|label_e2|ingest_one)\.py` (LABELERS: same without ingest_one).
POSIX ERE, `[^ ]*` used in place of `\S` (macOS pgrep's ERE has no `\S`). Checked live against macOS pgrep with a
harmless probe script (`zz_probe_label.py` in the scratchpad): it matched a real `.../MacOS/Python /…/zz_probe_label.py`
process and did not match a `bash -c` shell whose text held the bare names. Doctor's
"no label/ingest process alive" check uses the same `alive(BUSY)`, so it stays consistent.
Not touched: label_filing.py's `campaign_is_alive` (substring "label_e2.py"/"run_campaign_chain.sh"; ignores bare-name pgrep shells already).

Relaunch: plain `bash data/app/run_watchlist.sh` (background) re-runs only the 18 exit-2 tickers; `--refresh` is not needed.

## Tests
- `pytest -q test_run_watchlist.py test_finscreen_cli.py`: 26 passed.
- Full root suite: `1869 passed, 1 warning in 364.29s` (0 failed, 0 skipped).
