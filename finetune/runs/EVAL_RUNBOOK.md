# EVAL_RUNBOOK — running the held-out eval after the 1-epoch fine-tune

Operational runbook for the **main session**. Everything below was implemented
and tested offline on 2026-08-21 while training was still on the GPU; no model
was loaded and no GPU work was done to produce it. The only thing left is to
run it.

**Cost: $0. Zero Anthropic API calls.** Local MLX inference only.

---

## 0. Preconditions — check all four before starting

```bash
# 1. Training has actually EXITED (not just "looks finished"). Expect no output.
ps aux | grep 'mlx_lm.lora' | grep -v grep

# 2. The log's last lines show the final save, not a mid-run iteration.
tail -3 /Users/vihanpatil/personal/projects/FinScreen/finetune/runs/2026-08-21-epoch1-resume-from-500/launcher.log
#    want: "Iter 5236: ..." then "Saved final weights to .../adapters.safetensors."

# 3. The final adapter exists and was written after that last log line.
ls -l --time-style=full-iso /Users/vihanpatil/personal/projects/FinScreen/finetune/checkpoints/qwen2.5-7b-finscreen-lora-mlx-epoch1-resume-from-500/ 2>/dev/null \
  || ls -lT /Users/vihanpatil/personal/projects/FinScreen/finetune/checkpoints/qwen2.5-7b-finscreen-lora-mlx-epoch1-resume-from-500/

# 4. Nothing else is using the GPU.
```

> **Note on `adapters.safetensors` having no numbered twin.** `mlx_lm` writes a
> numbered checkpoint only on `save_every` boundaries; the final
> "Saved final weights" write at the end of training updates
> `adapters.safetensors` alone. `iters: 5236` is not a multiple of
> `save_every: 250`, so a *correctly completed* run has a final
> `adapters.safetensors` with no `0005236_adapters.safetensors` beside it.
> `eval.py` reports this explicitly in `manifest.json` rather than treating it
> as an anomaly — but it also means you must confirm precondition 1 yourself,
> because "unnumbered" and "half-written by a live trainer" look the same from
> the file alone.

---

## 1. Optional 20-row smoke first (~2 minutes, strongly recommended)

Catches a broken adapter load, a wrong path or a model that ignores the JSON
format before you commit an hour. It writes to its own directory so it can
never contaminate the real run's `predictions.jsonl`.

```bash
mkdir -p /Users/vihanpatil/personal/projects/FinScreen/finetune/runs/2026-08-21-eval-smoke

/Users/vihanpatil/personal/projects/FinScreen/finetune/.mlx_venv/bin/python \
  /Users/vihanpatil/personal/projects/FinScreen/finetune/eval.py \
  --backend mlx --limit 20 \
  --out-dir /Users/vihanpatil/personal/projects/FinScreen/finetune/runs/2026-08-21-eval-smoke
```

Look at `runs/2026-08-21-eval-smoke/predictions.jsonl`: `raw_output` should be
a bare JSON object per row, `finish_reason` should be `stop`, and
`generation_tokens` should be tens, not hundreds. The report will carry a
`SMOKE RUN` banner — those 20 rows are the first 20 in split order, not a
random sample, and their rates are not a result.

---

## 2. THE COMMAND

Run it **synchronously, in the foreground**, per HANDOFF §7 ("no background
watchers for post-batch or long-running work"). No `&`, no watcher process.
`caffeinate -dims` keeps the machine awake for the duration, the same way the
training launcher did.

```bash
mkdir -p /Users/vihanpatil/personal/projects/FinScreen/finetune/runs/2026-08-21-eval-epoch1

caffeinate -dims \
  /Users/vihanpatil/personal/projects/FinScreen/finetune/.mlx_venv/bin/python \
  /Users/vihanpatil/personal/projects/FinScreen/finetune/eval.py \
  --backend mlx \
  --out-dir /Users/vihanpatil/personal/projects/FinScreen/finetune/runs/2026-08-21-eval-epoch1 \
  2>&1 | tee /Users/vihanpatil/personal/projects/FinScreen/finetune/runs/2026-08-21-eval-epoch1/eval.log
```

`--out-dir` is passed explicitly on purpose: the default is dated from *today*,
so if the run starts before midnight and you re-run after, the default would
silently move to a new directory and the resume would find nothing.

Defaults it uses, all deliberate:

| flag | default | why |
|---|---|---|
| `--train-manifest` | `runs/2026-08-21-epoch1-resume-from-500/manifest.json` | supplies the base-model path, the adapter path, and the expected `valid.jsonl` hash |
| decoding | greedy, `temperature 0.0` → argmax sampler | deterministic; re-running gives the same predictions |
| `--max-tokens` | `520` | measured teacher answers are 40.3 tokens mean / 129 p99 / **150 max**, so 520 is ~3.5× the longest real answer — ample margin while still capping a runaway generation |
| `--resume` | on | already-generated rows are skipped |
| `--progress-every` | 25 | a progress line with running chunks/hour every 25 rows |

Before the first token is generated the script hard-fails if: the instruction
is not byte-identical across eval **and** train; `mlx_data/valid.jsonl`'s
sha256 differs from the training manifest's; `adapter_config.json` names a
different base model, a non-LoRA type, or a different `max_seq_length`; or any
eval passage disagrees with `prepared/eval.jsonl`. That is ~5 seconds of
checks against an hour of generation.

---

## 3. Expected wall-clock — honest arithmetic

Token counts below are **measured**, not estimated: rendered with the real
Qwen2.5 tokenizer over all 1,010 rows of `mlx_data/valid.jsonl`.

| quantity | mean | p50 | p95 | p99 | max | total |
|---|---|---|---|---|---|---|
| prompt tokens (the inference prompt) | 1,105.6 | 986 | 1,969 | 2,024 | 2,024 | **1,116,622** |
| teacher answer tokens (what the model should emit) | 40.3 | 33 | 102 | 129 | 150 | 40,677 |

At the speeds supplied by the timed probe (**~600 tok/s prefill, ~25 tok/s
decode**), and assuming the student's answers are about as long as the
teacher's (≈41 tokens including EOS):

- prefill: 1,116,622 / 600 = **1,861 s ≈ 31.0 min**
- decode: (41.3 × 1,010) / 25 = 41,713 / 25 = **1,669 s ≈ 27.8 min**
- generation subtotal: **≈ 59 min**
- fixed overhead: model+adapter load ~0.5–1.5 min, rendering all 1,010 prompts
  2.2 s (measured), hashing ~2 s

### **Point estimate: ~1.0 hour (55–65 min). Implied throughput ≈ 1,030 chunks/hour.**

Sensitivity — quote the band, not the point:

| scenario | prefill | decode | total |
|---|---|---|---|
| central (600 / 25 tok/s) | 31.0 min | 27.8 min | **~59 min** |
| decode is really 20 tok/s | 31.0 min | 34.8 min | ~66 min |
| prefill is really 400 tok/s | 46.5 min | 27.8 min | ~74 min |
| both slower (400 / 20) | 46.5 min | 34.8 min | ~81 min |
| 5% of rows run away to `--max-tokens` | 31.0 min | 44.0 min | ~75 min |
| pathological: *every* row runs to 520 tokens | 31.0 min | 350 min | **~6.4 h** |

The last row is the ceiling `--max-tokens 520` imposes. It should not happen —
training loss is ~0.05–0.08 and the format is short — but if the progress lines
show `finish_reason=length` and `gen_tok` near 520, **stop the run**: the model
is not terminating, and that is itself the finding. Do not let it grind for six
hours.

If the run comes in far off this estimate, the report's throughput section
records the actual prefill/decode tok/s it observed — use those, not these.

---

## 4. What "done" looks like

Exit code **0**. (Exit code **2** means partial — some rows have no prediction;
re-run the identical command and it resumes.)

Four files in `runs/2026-08-21-eval-epoch1/`:

| file | what it is |
|---|---|
| `predictions.jsonl` | one record per eval row: raw model text + per-row latency/token/finish-reason telemetry. Appended and `fsync`'d per row. |
| `eval_report.md` | the human-readable held-out report |
| `metrics.json` | every number in the report, machine-readable |
| `manifest.json` | run provenance: adapter + data hashes, decoding settings, versions, throughput |
| `eval.log` | the `tee`'d console output (from the command above) |

Verification one-liner:

```bash
cd /Users/vihanpatil/personal/projects/FinScreen/finetune/runs/2026-08-21-eval-epoch1
python3 - <<'PY'
import json, collections
recs=[json.loads(l) for l in open('predictions.jsonl')]
ids={r['chunk_id'] for r in recs}
man=json.load(open('manifest.json'))
print('records:', len(recs), '| unique chunk_ids:', len(ids), '(want 1010 / 1010)')
print('finish reasons:', collections.Counter(r['finish_reason'] for r in recs))
print('partial:', man['partial'], '| scored:', man['n_scored'])
print('data sha matches training manifest:', man['data']['sha_matches_train_manifest'])
print('instruction byte-identical to train:', man['data']['instruction_byte_identical_to_train'])
print('adapter sha:', man['adapter']['adapters_sha256'][:16], '| checkpoint:', man['adapter']['matches_checkpoint'][:60])
print('chunks/hour:', man['throughput']['chunks_per_hour'])
PY
```

Green means:

- `records == unique chunk_ids == 1010`
- `finish_reason` is overwhelmingly `stop`. A material `length` count means
  answers were cut at `--max-tokens` and their JSON is probably truncated —
  those rows will show up as parse failures; say so rather than quoting the
  rate as a model-quality number.
- `partial: False`
- `sha_matches_train_manifest: True` and
  `instruction_byte_identical_to_train: True`
- the adapter sha matches what you verified in §0

To re-render the report without regenerating anything (e.g. after a report
tweak), add `--score-only`; it loads no model and touches no GPU:

```bash
/Users/vihanpatil/personal/projects/FinScreen/finetune/.mlx_venv/bin/python \
  /Users/vihanpatil/personal/projects/FinScreen/finetune/eval.py \
  --backend mlx --score-only \
  --out-dir /Users/vihanpatil/personal/projects/FinScreen/finetune/runs/2026-08-21-eval-epoch1
```

---

## 5. If it gets interrupted

Re-run the **identical command**. Rows already in `predictions.jsonl` are
skipped; a torn final line from a `kill -9` is detected and ignored. Every row
also stores the sha256 of the exact prompt token sequence it was generated
from — if the dataset or the rendering ever changed under a resume, the run
stops hard rather than mixing two prompt versions in one result file.

Do **not** delete `predictions.jsonl` to "start clean" unless the script tells
you to; you would throw away finished GPU-hours.

---

## 6. Reading the report — standing rules it already enforces

The report states these itself, but so nobody re-derives them at review time:

- Every number is **agreement with the teacher**, not accuracy. The eval labels
  are Claude's bootstrap labels. A perfectly-agreeing student has reproduced
  the teacher including its errors.
- The teacher's own red-flag labels carry **~36.6% set-level error**
  (sample-pooled) / **~25%** base-rate-representative (Tier C) / **7.5%**
  per-category. A red-flag number near that noise floor is not separable from
  teacher noise by this eval.
- `red_flags` is reported on **both** bases — exact-set *and* per-category —
  because they differ by tens of points and quoting only the exact-set figure
  next to sentiment's single-value rate is precisely the error HANDOFF §2a
  calls out.
- **`distress_tier` is not reported at all.** The student was never trained on
  it.
- **8K_BODY (n=8, 2 tickers) is excluded from every headline table** and shown
  separately, marked not evaluable. **`WITHDRAWN` has zero eval support** (its
  single corpus-wide example is in train) and is listed as not evaluable rather
  than shown as a P/R/F1 row of zeros.
- Macro averages are taken over classes **with support in this split**, so an
  absent class does not drag the headline down as a structural zero.
- **Parse-failure rate and schema-violation rate are first-class metrics**, not
  footnotes. Unparseable rows stay in every denominator.
- Weak categories are printed with a `WEAK` / low-support marker. There is no
  single "it works" number in this report by design. Do not manufacture one for
  the gate-G1 write-up.

The throughput section doubles as **EXPANSION_PLAN F4's labeling-throughput
probe** — it is n=1,010 on this machine with this adapter, 20× the 50-chunk
probe §2b asked for, so it should *replace* the reasoned ~950 chunks/h band
rather than sit next to it. The projections printed there are single-stream,
with no prefix cache and no batching (both still-unused free levers).

---

## 7. What NOT to do

- Do not run this while training (or anything else) is on the GPU.
- Do not edit `labels.parquet`, `splits/`, `prepared/`, or `mlx_data/`. The
  eval hard-fails if `valid.jsonl` no longer matches the training manifest —
  that check exists to catch exactly this.
- Do not put a synthetic/test `predictions.jsonl` in the real run directory;
  the resume logic would treat those rows as done.
- Do not report a single headline number. Gate G1 is an owner read of the
  per-category table, including the weak rows.
- This is a research/screening classifier. It does not predict prices,
  recommend trades, or connect to any brokerage — the report says so and that
  framing should survive into the model card.

---

## 8. Files this runbook refers to

| path | role |
|---|---|
| `/Users/vihanpatil/personal/projects/FinScreen/finetune/eval.py` | the evaluator (`--dry-run` behaviour unchanged; `--backend mlx` is the real path) |
| `/Users/vihanpatil/personal/projects/FinScreen/finetune/test_eval_real.py` | 36 offline tests of the real path — no model, no GPU |
| `/Users/vihanpatil/personal/projects/FinScreen/finetune/convert_to_mlx.py` | owns the rendering contract; `eval.py` imports it rather than restating it |
| `/Users/vihanpatil/personal/projects/FinScreen/finetune/eval_section_types.json` | chunk_id → section_type sidecar (read-only derivation of `splits/eval.parquet`), needed to exclude 8K_BODY. Regenerate with the **system** python3: `python3 finetune/eval.py --write-section-types` |
| `/Users/vihanpatil/personal/projects/FinScreen/finetune/runs/2026-08-21-epoch1-resume-from-500/manifest.json` | the training run being evaluated |
