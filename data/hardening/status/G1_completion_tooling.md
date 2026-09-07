# G1 completion tooling — `--complete-missing` (2026-08-26)

**Status: IMPLEMENTED + TESTED OFFLINE. NOT SUBMITTED.**
Zero API calls were made building this. The submission is a MAIN SESSION
action under the standing §4/§7 money gate.

## What and why

The owner-ratified v1.2 re-label batch
(`msgbatch_01UdoUkZfuaTRJzokZDfbFYN`) ended 6,746/6,747: the final request
errored `credit balance too low`, leaving **`CHK-1c1812ed45219a3a`** (OXY,
MDA, 10-K filed 2026-02-18 — a *train*-split row) with a row in
`data/labels_v12.parquet` that carries no labels and no `stop_reason`.
The owner authorized completing exactly that row in chat, 2026-08-26:
*"yes please complete that single missing row for a perfect whole dataset."*

`submit_labeling_batch.py` gains a guarded `--complete-missing` mode plus a
`--poll --merge-into` return path. Everything else in the file is
unchanged; `--poll` without `--merge-into` behaves exactly as before (pinned
by a regression test).

## Main-session command sequence

```bash
# 0. PREVIEW — prints the count + estimated cost, submits NOTHING, exits 1.
python3 submit_labeling_batch.py --complete-missing \
    --against data/labels_v12.parquet --variant v12_relabel

# 1. SUBMIT (only after the preview reads: 1 request, CHK-1c1812ed45219a3a)
python3 submit_labeling_batch.py --complete-missing \
    --against data/labels_v12.parquet --variant v12_relabel \
    --confirm-complete
# -> writes data/v12_completion_batch_meta.json (NEW file; v12_relabel's meta
#    and E1's full_batch_meta.json are untouched). Note the printed batch id.

# 2. POLL + MERGE IN PLACE (synchronous, main session — no background watcher)
python3 submit_labeling_batch.py --poll <COMPLETION_BATCH_ID> \
    --variant v12_relabel --merge-into data/labels_v12.parquet \
    --max-wait-s 1800
# -> backs up data/labels_v12.parquet -> data/labels_v12.parquet.pre_completion
# -> writes the batch's own rows to data/labels_v12_completion.parquet (audit)
# -> fills the one row in place, stamped completion_batch_id=<id>
# -> prints "Rows still unanswered in data/labels_v12.parquet: 0"
```

**Prerequisite the tooling cannot satisfy:** the account balance is ≈ $0
(HARDENING_PROGRESS "G1 REPAIR CAMPAIGN": *"the spend freeze is RE-SEALED"*).
Step 1 needs a credit purchase by the owner. The tooling refuses politely
either way — an errored submit leaves the parquet untouched.

## Estimated cost — one row

Measured off the actual request body in `data/batch_requests_v12.jsonl`
(system prefix 1,893 tok, passage+schema 776 tok) and the v1.2 batch's own
mean output for MDA rows (68.3 tok over 3,961 answered rows):

| tier | one-row cost |
|---|---|
| intro ($2/$10, live through 2026-08-31) | **$0.004904** |
| standard ($3/$15) | $0.007355 |

Batch discount applied; conservatively charges a full 1h **cache write** on
the system prefix (a 1-request batch has no warm cache to read). Half a
cent, as HARDENING_PROGRESS estimated when the row was first deferred.

## Guards (each one mutation-tested — removing it fails a test)

1. **`--max-missing` (default 3)** — refuses outright above that many
   unanswered rows. This mode completes bounced singletons; it is not a
   campaign re-runner. Raising it requires a visible CLI flag.
2. **"Unanswered" is a narrow predicate** — `stop_reason` null AND all of
   sentiment/guidance_direction/red_flags/distress_tier null. A refusal
   (`stop_reason="refusal"`, E1's `CHK-8e69547e0900a8dd`) and a truncation
   (`stop_reason="max_tokens"`) are *answers* and are excluded, but are
   printed under "answered-but-flagged rows NOT completed by this mode" so
   nothing is silently swept in or out. An empty `red_flags` list is an
   answer, not a gap.
3. **Both existing submit guards run** — `assert_requests_match_variant`
   (max_tokens/thinking/effort) and, because `v12_relabel` is in
   `RUBRIC_PINNED_VARIANTS`, `assert_requests_use_current_system_prompt`
   (rubric sha256 + model id). Completion gets no discount on either.
4. **`--confirm-complete`** — the preview always prints the request count,
   the exact custom_ids and the per-tier cost *before* the gate, and
   without the flag exits 1 having constructed no client at all.
5. **Meta-path protection** — refuses to write over a meta file whose
   recorded `mode` is not `complete-missing` (the 2026-08-11 class of bug:
   a meta file is the only record of what a batch actually was).
6. **Merge is validate-then-backup-then-write** — refuses if a completed
   chunk_id is absent from the target, refuses if that row already carries
   an answer (that would be a re-label, needing its own ratification),
   refuses if `.pre_completion` already exists (it is the only surviving
   pre-merge copy), and skips a completion row that bounced *again* rather
   than merging another blank. Only the 17 label/provenance columns are
   written; the frozen corpus columns (text, section_type, home_*,
   source_*) are never touched.
7. **Per-row provenance** — merged rows get `batch_id` = the completion
   batch and a new `completion_batch_id` column set on those rows only
   (null elsewhere), so the one repaired row stays identifiable forever.

## Tests

`test_submit_complete_missing.py` — **37 tests, all passing**, no network,
no `.env`, no client (every refusal path asserts `get_client` was never
called). Groups: missing-row detection (7, incl. one read-only assertion
against the real `data/labels_v12.parquet` → exactly
`CHK-1c1812ed45219a3a`), request extraction (2), cost estimate (4),
submit gates (9), merge semantics (8), CLI wiring (7).

Full suite for the touched module: **91 passing**
(`test_submit_variant_wiring.py` 25 + `test_rubric_v12_sync.py` 29 +
`test_submit_complete_missing.py` 37) — no regressions.

## Files

- `submit_labeling_batch.py` — new mode + merge path (only file changed).
- `test_submit_complete_missing.py` — new.
- Not touched: `finetune/` (sibling agent), F2/F3 ledgers, E1's
  `data/labels.parquet`, `data/batch_requests_v12.jsonl`,
  `data/v12_relabel_batch_meta.json`.
- Not yet created (they appear only when the main session runs the
  commands): `data/v12_completion_batch_meta.json`,
  `data/labels_v12_completion.parquet`,
  `data/labels_v12.parquet.pre_completion`.

## Ledger

`HARDENING_PROGRESS.md`'s "G1 REPAIR CAMPAIGN" section was deliberately
**not** edited here — the main session owns that ledger and should add the
completion line when the row actually lands.
