# v1.2 retrain — the exact MAIN-SESSION commands

**Prepared 2026-08-26 by the finetune-engineer. Nothing here was executed.**
The data build (splits → prepared → MLX chat format) IS done and verified;
only the GPU work is left, and per `HANDOFF.md` §4/§7 the main session runs it,
never an agent.

**Cost: $0. Zero Anthropic API calls.** Local MLX only.

```
FS=/Users/vihanpatil/personal/projects/FinScreen
R=$FS/finetune/runs/2026-08-26-v12-epoch1
M=/Users/vihanpatil/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed
```

---

## 0. What changed vs the 2026-08-21 epoch-1 run

**Almost nothing, by design.** After the 2026-08-26 completion batch closed the
one unanswered row, `data/labels_v12.parquet` is 6,747/6,747 labeled and the
splits are the frozen split **exactly**: train 5,736 / eval 1,010.

| | 2026-08-21 epoch-1 | this run |
|---|---|---|
| labels | `data/labels.parquet` (rubric v1.1) | `data/labels_v12.parquet` (rubric **v1.2**) |
| train / eval rows | 5,736 / 1,010 | **5,736 / 1,010** — identical membership |
| split membership | `split.py` | **JOIN onto the frozen `splits/manifest.parquet`** — `split.py` NOT run |
| base model | Qwen2.5-7B-Instruct-4bit `c26a38f6…` | same |
| LoRA | r16 / scale 2.0 / dropout 0.05 / **q+v** / top-16 layers | same |
| batch / seq / masking | 1 × 4 grad-accum, 2048, `mask_prompt`, `grad_checkpoint`, seed 42 | same |
| training instruction | sha `ebc45a85…` | **same sha `ebc45a85…`** — deliberately frozen |
| schedule | 5736 iters / 1434 updates, cosine [2e-4, 1391], warmup 43 | **identical** |
| `save_every` | 250 | **100** (≈ 9.6 min of work, measured) |

The resolved training config differs from `runs/2026-08-20-epoch1/mlx_lora_config.yaml`
in exactly **three lines** — `data`, `save_every`, `adapter_path`. Diff them
yourself; that three-line diff is the single-axis claim.

---

## 1. Pre-flight (free, ~1 minute, run all of it)

```bash
# a. the data build is reproducible — these must reprint the shas in
#    dataset_manifest.json
python3 $FS/finetune/build_splits_v12.py
python3 $FS/finetune/prepare_dataset.py --splits-dir $FS/finetune/splits_v12 \
                                        --out-dir    $FS/finetune/prepared_v12

# b. offline test suites (expect 154 passed, 5 skipped)
python3 -m pytest $FS/finetune/test_build_splits_v12.py \
                  $FS/finetune/test_eval_dataset_paths.py \
                  $FS/finetune/test_train_qlora_v12_flags.py \
                  $FS/finetune/test_prepare_dataset.py \
                  $FS/finetune/test_leakage.py \
                  $FS/finetune/test_eval_real.py \
                  $FS/data/hardening/test_label_shift_v11_v12.py \
                  $FS/test_rubric_v12_sync.py \
                  $FS/test_submit_variant_wiring.py -q

# the tokenizer-dependent rendering-contract tests skip under system python;
# run them once in the mlx venv too (expect 36 passed, 0 skipped)
$FS/finetune/.mlx_venv/bin/python $FS/finetune/test_eval_real.py

# c. the single-axis check, by eye
diff $FS/finetune/runs/2026-08-20-epoch1/mlx_lora_config.yaml \
     $R/plan-epoch1/mlx_lora_config.yaml

# d. nothing else is on the GPU
ps aux | grep -E 'mlx_lm|eval\.py' | grep -v grep     # expect no output
```

The MLX conversion is already done and cross-checked
(`finetune/mlx_data_v12/conversion_report.json`, 23 s of CPU tokenization);
re-run it only if `prepared_v12/*.jsonl` changed:

```bash
$FS/finetune/.mlx_venv/bin/python $FS/finetune/convert_to_mlx.py \
  --model $M --prepared-dir $FS/finetune/prepared_v12 \
  --out-dir $FS/finetune/mlx_data_v12 \
  --report $FS/finetune/mlx_data_v12/conversion_report.json
```

---

## 2. THE EPOCH-1 COMMAND

`train_qlora.py` re-hashes `mlx_data_v12/{train,valid}.jsonl`, cross-checks
them against `conversion_report.json`, refuses `batch_size != 1`, refuses
`iters` above one epoch, writes `manifest.json` + the resolved
`mlx_lora_config.yaml` into the run dir, then launches `mlx_lm.lora`.

```bash
mkdir -p $R
caffeinate -dims $FS/finetune/.mlx_venv/bin/python $FS/finetune/train_qlora.py \
  --backend mlx \
  --run-dir $R \
  --tag v12-epoch1 \
  --model $M \
  --weights-sha256 86110f368236b53cf4c2336f991a85703b17bcc60bb75f292b4002ec0219f071 \
  --data-dir $FS/finetune/mlx_data_v12 \
  --expect-train 5736 --expect-eval 1010 \
  --iters 5736 \
  --save-every 100 \
  --authorization $R/authorization.json \
  >> $R/launcher.log 2>&1
```

No `--lr-*` flags: at 5,736 iters the fresh cosine in `config_mlx.yaml`
(`[2.0e-4, 1391]`, warmup 43, 1,434 optimizer updates) is already the correct
epoch-1 schedule — the same one the 2026-08-21 run used.

Launch it as a **main-session background task** (`run_in_background`), not
from an agent shell, and treat every kill notification as a resume trigger
(`RESUME_RECIPE.md` in this directory). `save_every 100` bounds the loss from
any kill to ≤ 100 iters ≈ **9.6 minutes**, measured.

The exact resolved config this produces is pre-generated at
`plan-epoch1/mlx_lora_config.yaml`, sha256
`9e35f2fb7ca9f245af72a149e839a3cc92ca84ec9a1566fd356a9ceeb888155f`. If the
launcher's copy differs from it, something moved — stop and find out what.

Adapter output: `finetune/checkpoints/qwen2.5-7b-finscreen-lora-mlx-v12-epoch1/`.

### Projected wall-clock — measured, not guessed

From the 2026-08-21 epoch-2 run's own checkpoint timestamps (56 consecutive
100-iter gaps on this machine, this recipe, this seq length):

| | sec/iter | 5,736 iters |
|---|---|---|
| median | 5.702 | **9.09 h** |
| mean | 5.748 | **9.16 h** |
| p90 | 6.040 | **9.62 h** |

Cross-check: the trainer's own `It/sec` averaged 0.177 over epoch 2 and 0.174
over the epoch-1 remainder → 5.65–5.75 s/iter. Periodic validation
(`steps_per_eval 500`, `val_batches 25`, ~36 s each, 11 times) is already
inside those gaps. Independent confirmation: epoch 2 ran 21:22 → 06:32 =
**9.17 h** end to end.

**Point estimate ≈ 9.2 h; quote the band 9.0–9.9 h.** Add ~1–2 min of model
load per resume segment. One overnight.

---

## 3. THE EVAL COMMAND (after epoch 1)

`eval.py` gained `--mlx-data-dir` / `--prepared-dir` on 2026-08-26 for exactly
this. E1 remains the default, so every pre-existing invocation is byte-
compatible; the v1.2 re-eval names the v12 dirs explicitly.

```bash
E1EVAL=$FS/finetune/runs/2026-08-27-v12-eval-epoch1
mkdir -p $E1EVAL

caffeinate -dims $FS/finetune/.mlx_venv/bin/python $FS/finetune/eval.py \
  --backend mlx \
  --train-manifest $R/manifest.json \
  --mlx-data-dir $FS/finetune/mlx_data_v12 \
  --prepared-dir $FS/finetune/prepared_v12 \
  --section-types $FS/finetune/eval_section_types.json \
  --out-dir $E1EVAL \
  2>&1 | tee $E1EVAL/eval.log
```

`--train-manifest` supplies the base-model path, **the adapter path**, and the
expected `valid.jsonl` sha — so there is no adapter placeholder to fill in.

> **If epoch 1 was segmented by kills**, point `--train-manifest` at the **last
> segment's** `manifest.json` (`runs/2026-08-26-v12-epoch1-from-<N>/manifest.json`),
> because that is the run whose `adapter_path` holds the final
> `adapters.safetensors`. All segments share the same data shas, so the
> verify-artifact check passes either way — but the adapter path must be the
> last one. To evaluate a specific numbered checkpoint instead, add
> `--adapter-path <checkpoint dir>`.

**The section-type sidecar does NOT need regenerating.** `section_type` is
corpus metadata, not a label, and eval membership is frozen — verified twice:
`finetune/eval_section_types.json` covers all 1,010 v1.2 eval chunk_ids with
identical values, and regenerating it from `splits_v12/eval.parquet` reproduces
the shipped mapping exactly (pinned by a test). Passing `--section-types`
above is redundant-but-explicit. If you want it rebuilt from the v1.2 split
anyway (SYSTEM python3 — the mlx venv has no pandas):

```bash
python3 $FS/finetune/eval.py --write-section-types \
  --splits-eval-parquet $FS/finetune/splits_v12/eval.parquet \
  --section-types $FS/finetune/eval_section_types_v12.json
```

### The fail-safe, and what it looks like

If `--mlx-data-dir` names a dataset the adapter was not trained on,
`run_real_eval` raises `SystemExit` on the sha check **before loading a model
or generating a token**, naming both the file it loaded and the dataset the
manifest expects. Pointing the v1.2 manifest at E1's `mlx_data` (or vice
versa) therefore stops immediately rather than silently scoring the v1.2
student against v1.1 targets. Verified offline: v1.2's `valid.jsonl` hashes
`b74efdb326e9b862…`, which matches `plan-epoch1/manifest.json` and differs from
the E1 epoch-2 manifest's.

### Expected

Exit **0**; exit **2** means partial — re-run the identical command and it
resumes from `predictions.jsonl`. Measured throughput from the epoch-1 eval:
**1,068 chunks/h** → 1,010 rows ≈ **57 min**. Sanity block to check in
`manifest.json`: `data.mlx_data_dir` ends in `mlx_data_v12`,
`data.sha_matches_train_manifest: true`,
`data.instruction_byte_identical_to_train: true`,
`data.instruction_sha256 = ebc45a856bff58a5…`,
`data.n_rows: 1010`, `partial: false`.

Reporting rules are unchanged and binding: agreement-with-the-teacher (not
accuracy), `red_flags` on **both** exact-set and per-category bases,
`distress_tier` not reported at all, 8K_BODY (n=8) and WITHDRAWN excluded as
not evaluable, guidance reported raw **and** post-ruled (missing→NONE).

---

## 4. PLANNED epoch-2 continuation

Same modelling choice the owner-ratified 2026-08-21 epoch-2 used: a **fresh
cosine at HALF peak LR** resuming the epoch-1 final adapter.

```bash
R2=$FS/finetune/runs/2026-08-27-v12-epoch2
mkdir -p $R2
caffeinate -dims $FS/finetune/.mlx_venv/bin/python $FS/finetune/train_qlora.py \
  --backend mlx \
  --run-dir $R2 \
  --tag v12-epoch2 \
  --model $M \
  --weights-sha256 86110f368236b53cf4c2336f991a85703b17bcc60bb75f292b4002ec0219f071 \
  --data-dir $FS/finetune/mlx_data_v12 \
  --expect-train 5736 --expect-eval 1010 \
  --iters 5736 \
  --save-every 100 \
  --lr-peak 1.0e-4 --lr-decay-steps 1414 --lr-warmup 20 \
  --resume-adapter-file $FS/finetune/checkpoints/qwen2.5-7b-finscreen-lora-mlx-v12-epoch1/adapters.safetensors \
  --authorization $R/authorization.json \
  >> $R2/launcher.log 2>&1
```

Pre-generated resolved config: `plan-epoch2/mlx_lora_config.yaml`, sha256
`2efa4ea4d39101e8273515e90f1e95e632958f248b4a4e08a445a9b5f4d37b17`. It differs
from `runs/2026-08-21-epoch2/mlx_lora_config.yaml` in four lines: `data`,
`adapter_path`, `resume_adapter_file`, and the top-level `learning_rate`
(0.0002 → 0.0001). **The last one is cosmetic**: `mlx_lm/lora.py:275` is
`lr = build_schedule(args.lr_schedule) if args.lr_schedule else args.learning_rate`,
so with an `lr_schedule` present the top-level value is never read. `--lr-peak`
sets both so the file no longer contradicts itself; E1's epoch-2 file said
0.0002 while actually training at a 1.0e-4 peak.

Projected wall-clock: the same **~9.2 h (9.0–9.9 h)**. Second overnight.

**Gate:** epoch 2 is *planned*, not pre-authorized to run unattended straight
after epoch 1. The 2026-08-26 ratification funds "retrain (~2 nights)", and
the epoch-1 → epoch-2 step on the v1.1 student was itself an explicit owner
call (HANDOFF §3, 2026-08-21). Run the epoch-1 eval first; if it already shows
the red-flag block repaired, a second epoch may be unnecessary — that is the
owner's call at G1, not a default.

---

## 5. THE FINAL EVAL COMMAND (after epoch 2)

Identical to §3 except the manifest and the output directory:

```bash
E2EVAL=$FS/finetune/runs/2026-08-28-v12-eval-epoch2
mkdir -p $E2EVAL

caffeinate -dims $FS/finetune/.mlx_venv/bin/python $FS/finetune/eval.py \
  --backend mlx \
  --train-manifest $R2/manifest.json \
  --mlx-data-dir $FS/finetune/mlx_data_v12 \
  --prepared-dir $FS/finetune/prepared_v12 \
  --section-types $FS/finetune/eval_section_types.json \
  --out-dir $E2EVAL \
  2>&1 | tee $E2EVAL/eval.log
```

(Again: if epoch 2 was segmented by kills, use the **last segment's**
`manifest.json` — that is the run whose `adapter_path` holds the final
adapter.)

This is the report the owner rules G1 on. Put the two v1.1 baselines beside
it — `runs/2026-08-21-eval-epoch1/eval_report.md` and
`runs/2026-08-22-eval-epoch2/eval_report.md` — so the read is v1.1-student vs
v1.2-student **at the same epoch count, on the same frozen 1,010 eval rows,
with the same instruction**. Carry forward the two honesty items from
`data/hardening/status/G1_repair_dataset.md`: 12/1,010 eval prompts differ from
epoch-2's by answer-length-dependent head truncation, and every number is
agreement with the teacher, not accuracy.

---

## 6. The whole campaign, in order

Copy-paste for a fresh session. Nothing here needs a decision except the two
marked **OWNER GATE**.

```
 0.  setup      export FS / R / M (top of this file), then §1 pre-flight   ~1 min
 1.  TRAIN e1   §2   main-session background task, resume per RESUME_RECIPE ~9.2 h
 2.  EVAL  e1   §3   foreground, resumable via predictions.jsonl           ~57 min
 3.  ** OWNER GATE ** read the epoch-1 report — is a second epoch wanted?
 4.  TRAIN e2   §4   main-session background task, same resume recipe      ~9.2 h
 5.  EVAL  e2   §5   foreground, resumable                                 ~57 min
 6.  ** OWNER GATE — G1 ** rule on the repaired instrument
```

Also export, once, for §4/§5:

```bash
R2=$FS/finetune/runs/2026-08-27-v12-epoch2
```

Total machine time ≈ **20.2 h** — two overnights plus ~2 h of eval. Total cost
**$0**, zero Anthropic API calls at every step.

| step | run dir written | key artifact produced |
|---|---|---|
| 1 | `runs/2026-08-26-v12-epoch1/` (+ `-from-<N>` segments) | `checkpoints/…-v12-epoch1/adapters.safetensors` |
| 2 | `runs/2026-08-27-v12-eval-epoch1/` | `eval_report.md`, `metrics.json`, `predictions.jsonl` |
| 4 | `runs/2026-08-27-v12-epoch2/` (+ segments) | `checkpoints/…-v12-epoch2/adapters.safetensors` |
| 5 | `runs/2026-08-28-v12-eval-epoch2/` | the G1 report |

Between steps the only state you need is on disk: each run dir's
`manifest.json` names its own adapter, data shas and authorization, and this
directory's `dataset_manifest.json` hashes everything upstream. If a session
dies mid-campaign, `data/hardening/status/G1_repair_dataset.md` plus this file
are the resume state.

---

## 7. Files this run directory holds

| file | what it is |
|---|---|
| `authorization.json` | the owner ratification this run executes under; hashed into `manifest.json` |
| `dataset_manifest.json` | sha256 of every upstream artifact — labels, frozen split manifest, splits_v12, prepared_v12, mlx_data_v12, instruction, labeling system prompt, rubric, base weights, reference v1.1 adapters |
| `build_dataset_manifest.py` | regenerates the above; read-only, re-runnable |
| `plan-epoch1/`, `plan-epoch2/` | pre-generated resolved `mlx_lora_config.yaml` + planned manifest for each launch |
| `RESUME_RECIPE.md` | the segmented auto-resume chain |
| `RUN_COMMANDS.md` | this file |
| `manifest.json`, `mlx_lora_config.yaml`, `train.log`, `launcher.log` | **written by the launcher at launch time**, not by this preparation |

## 8. What NOT to do

- Do not run `finetune/split.py`. Its `LABELS_PATH` is E1's frozen labels and
  it would re-derive membership. The split is frozen.
- Do not write to `data/labels.parquet`, `finetune/splits/`,
  `finetune/prepared/`, or `finetune/mlx_data/`. Those are E1's frozen
  artifacts and the v1.1 student's provenance.
- Do not let the refusal chunk `CHK-8e69547e0900a8dd` into a split just
  because v1.2 labeled it. The frozen manifest excludes it; `build_splits_v12.py`
  hard-fails if it ever appears there.
- Do not report a single headline number at G1. Per-category, including the
  weak classes, both red-flag bases.
