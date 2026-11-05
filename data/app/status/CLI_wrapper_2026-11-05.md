# CLI wrapper (`bin/fs` + `finscreen.py`) -- 2026-11-05

Added files only. No existing module changed, no paid API, no network in `doctor`,
no labeling and no G3 runner executed. Nothing committed.

## Files
| file | lines | what |
|---|---|---|
| `bin/fs` | 30 | bash; picks `$FINSCREEN_PYTHON` (if it runs) -> `/usr/bin/python3` (if it imports pandas within 10 s) -> `/Library/Developer/CommandLineTools/usr/bin/python3` (if it imports pandas); else names all three, prints `sudo xcodebuild -license accept`, exits 3. `exec`s `finscreen.py`. |
| `finscreen.py` | 256 | argparse subcommands `doctor`, `report`, `g3`, `index`; chains the existing CLIs via `[sys.executable, REPO/x.py, ...]`, `cwd=REPO`. No new dependencies. |
| `test_finscreen_cli.py` | 163 | offline; fakes `subprocess.run` and the pgrep helper; paths in `tmp_path`. |

## Behaviour notes
- `report TICKER`: refuses (exit 2) if a `label_filing|label_e2` process is alive, checked at the
  start (before ingest, so a running labeler's store is never re-ingested under it). Ingest is
  skipped when a store manifest with that ticker has `window.per_form == --per-form`; the CIK is
  parsed from ingest_one's `(CIK n)` line, falling back to a manifest scan. `--fundamentals`
  always runs (ingest_one's own 24 h cache makes it cheap). Labeling is skipped when
  `labels.parquet` exists AND `label_manifest.json` `prepare.chunks_parquet_sha256` equals the
  store manifest's `chunks.sha256` -- slightly stricter than "labels.parquet exists", so a
  re-ingest with a new `--per-form` cannot leave stale labels behind a fresh page. The index page
  is required (failure aborts); each `--latest 10-K/10-Q/8-K` failure is recorded as "no page".
- `g3`: refuses (exit 2) unless `--owner-word` is exactly `ratify`, `--date` matches
  `\d{4}-\d{2}-\d{2}`, and `data/f5/G3_RATIFIED.json` is absent. Then `pin_g3.py --show`
  (stdout -> `data/f5/status/PIN_SHOW_<D>.txt`), `pin_g3.py --pin`, `backtest_e2.py`,
  `heads_e2.py --all`, stopping on the first nonzero exit; one JSON line per step to
  `data/f5/status/g3_chain_log.jsonl`.
- `doctor`: the adapter sha is read from `campaign_manifest.json` `inputs.adapter_sha256_expected`
  (the key is nested under `inputs`, the same read `label_filing.campaign_inputs()` does).

## Tests
`/Library/Developer/CommandLineTools/usr/bin/python3 -m pytest -q test_finscreen_cli.py -p no:cacheprovider`
-> **13 passed, 0 failed** (~1 s). Covers: CIK parser (908937 from the SIRI line); g3 refusals
(4 bad word/date cases, existing G3_RATIFIED.json), the 4 steps in order + log + PIN_SHOW file,
stop on first failure; report full chain with a failing `--latest 8-K`, skip ingest+label when
current (+ `--open` on the index page), relabel when the label manifest's chunks sha is stale,
refusal when a labeler is alive; doctor exit 0 on matching sha and 1 on mismatch.

Also exercised by hand: `bin/fs index` (11 stores, all labeled), `bin/fs g3 ... --owner-word nope`
-> exit 2, `FINSCREEN_PYTHON=/nope` -> warning + fallback, and a scratch copy of `bin/fs` with the
CLT path broken -> the error message + exit 3.

## `bin/fs doctor` (real run, exit 0, ~3 s)
```
INFO  interpreter                      /Library/Developer/CommandLineTools/usr/bin/python3 (3.9.6)
PASS  import pandas                    2.2.3
PASS  import pyarrow                   21.0.0
PASS  import xgboost                   2.1.4
PASS  mlx venv: import mlx_lm          /Users/vihanpatil/personal/projects/FinScreen/finetune/.mlx_venv/bin/python
PASS  adapter sha256                   cadca8499b66... == campaign cadca8499b66...
PASS  data file                        data/filings_e2_v2.parquet
PASS  data file                        data/f4/labels_e2_v1.parquet
INFO  G3_RATIFIED.json                 absent (not pinned)
INFO  EODHD_API_TOKEN                  not set
PASS  free disk                        192 GB
PASS  no label/ingest process alive
```

## Not done
- `report` and `g3` were not run end to end (by instruction; the caller runs the proof).
- `/usr/bin/python3` is still blocked by the Xcode licence; `bin/fs` routes around it.
- `pgrep -f` matches any command line containing `label_filing|label_e2|ingest_one`, including a
  shell whose command string merely mentions one; the refusal lists what it matched.
