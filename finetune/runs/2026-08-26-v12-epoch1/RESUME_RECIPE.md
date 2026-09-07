# Auto-resume recipe — v12-epoch1 (and v12-epoch2, same shape)

Same discipline as `runs/2026-08-21-epoch1-final-from-2250/RESUME_RECIPE.md`,
with the segment-schedule step done by **flag** instead of by temp-editing
`config_mlx.yaml` (that dance mutated a shared file mid-campaign; `--lr-peak`
/ `--lr-decay-steps` / `--lr-warmup` now do the same job on the resolved copy
only).

Context: harness-owned background tasks get SIGTERMed at unpredictable
runtimes, and daemonization is not permitted here. Strategy: **accept kills,
resume on each kill notification.** `save_every: 100` bounds any loss to
≤ 100 iters — **9.6 minutes**, measured from the 2026-08-21 epoch-2
checkpoint timestamps.

```
FS=/Users/vihanpatil/personal/projects/FinScreen
M=/Users/vihanpatil/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed
CK=$FS/finetune/checkpoints
```

## Epoch-1 run constants

| | value |
|---|---|
| total iters | **5736** (one epoch, batch_size 1) |
| grad accumulation | 4 → **1434 optimizer updates** |
| fresh schedule | peak `2.0e-4`, `decay_steps 1391`, `warmup 43` (= `config_mlx.yaml`'s default; epoch 1 needs no `--lr-*` flag) |
| `save_every` | 100 iters ≈ 9.6 min |
| first adapter dir | `$CK/qwen2.5-7b-finscreen-lora-mlx-v12-epoch1` |

## On a kill notification

1. **Find the last numbered checkpoint** in the CURRENT segment's adapter dir:

   ```bash
   ls -1 $CK/qwen2.5-7b-finscreen-lora-mlx-v12-epoch1*/0*_adapters.safetensors | sort | tail -1
   ```

   Its 7-digit prefix is the segment-local iter `n`. Keep a running
   **cumulative** total `N` = (iters completed in all earlier segments) + `n`.
   If no numbered checkpoint exists in this segment, `N` is unchanged and you
   resume from the previous segment's file.

2. **Read the LR at that point** from the segment's log:

   ```bash
   grep "^Iter ${n}:" <that segment's launcher.log>
   ```

   Take the `Learning Rate` value → `LR_N`.

3. **Launch the next segment.** Units below are the ones each flag actually
   takes: `--iters` in micro-batches, the two LR flags in **optimizer
   updates** (= iters / 4).

   ```bash
   SEG=v12-epoch1-from-$N
   R=$FS/finetune/runs/2026-08-26-$SEG
   mkdir -p $R
   caffeinate -dims $FS/finetune/.mlx_venv/bin/python $FS/finetune/train_qlora.py \
     --backend mlx \
     --run-dir $R \
     --tag $SEG \
     --model $M \
     --weights-sha256 86110f368236b53cf4c2336f991a85703b17bcc60bb75f292b4002ec0219f071 \
     --data-dir $FS/finetune/mlx_data_v12 \
     --expect-train 5736 --expect-eval 1010 \
     --iters $((5736 - N)) \
     --save-every 100 \
     --lr-peak <LR_N> --lr-decay-steps $((1391 - N/4)) --lr-warmup 0 \
     --resume-adapter-file <the checkpoint file from step 1> \
     --authorization $FS/finetune/runs/2026-08-26-v12-epoch1/authorization.json \
     >> $R/launcher.log 2>&1
   ```

   `--lr-warmup 0` because this is a mid-epoch continuation, not a fresh run.
   The adapter path is derived from `--tag`, so each segment writes its own
   checkpoint directory and no earlier segment is ever overwritten.

4. **Repeat** until a segment's log reaches its final iter and prints
   `Saved final weights to .../adapters.safetensors` with a clean process exit
   (code 0). That file, in the LAST segment's adapter dir, is the epoch-1
   adapter.

5. **Then, and only then:** run the eval (`RUN_COMMANDS.md` §3). Do not start
   epoch 2 automatically — see `RUN_COMMANDS.md` §4, it is an owner call.

## The honest limitations of an mlx-lm resume (unchanged since 2026-08-20)

- **Restored:** LoRA adapter weights.
- **NOT restored:** AdamW first/second moments (mlx-lm 0.31.3 saves only
  `model.trainable_parameters()`); the LR-schedule position (the optimizer's
  step counter restarts at 0 — hence step 3's hand-set continuation
  schedule); the data-order permutation (a resumed run re-permutes, so within
  a nominal "one epoch" some examples may be seen twice and others not at
  all).
- **A killed segment therefore loses** up to 100 iters (~9.6 min) plus
  optimizer-momentum warm-up and exact LR continuity. It does **not** lose the
  trained adapter.
- Record the segment boundaries in the final run's manifest so the epoch's
  accounting (which iters ran under which segment and which schedule) is
  legible at the G1 read. The 2026-08-21 epoch-1 did this in its
  RESUME_RECIPE's "Accounting so far" footer; do the same here.

## Watching, without a background watcher

`HANDOFF.md` §4/§7: no daemon watchers. Poll the filesystem from the main
session between other work:

```bash
tail -3 $R/launcher.log
ls -1t $CK/qwen2.5-7b-finscreen-lora-mlx-v12-epoch1*/0*_adapters.safetensors | head -3
```
