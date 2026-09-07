# Auto-resume recipe — epoch1-final-from-2250

Context: harness-owned background tasks were SIGTERMed at unpredictable
runtimes (51 min / 2h58m / 6.5 min); daemonization is not permitted in this
environment (auto-mode classifier). Strategy: accept kills, resume on each
kill notification. `save_every: 100` bounds any loss to ≤100 iters (~10 min).

On a kill notification for this run:

1. `ls checkpoints/qwen2.5-7b-finscreen-lora-mlx-epoch1-final-from-2250/*_adapters.safetensors | sort | tail -1`
   → latest numbered checkpoint N (7 digits). If none exist, N=0 and the
   resume file stays `...-resume-from-500/0001750_adapters.safetensors`.
2. Read the LR at iter N from this run's launcher.log (`grep '^Iter N:'`).
3. New continuation schedule: `arguments: [<LR at N>, 829 - N/4]`, `warmup: 0`.
4. New iters: `3486 - N`. New tag/run-dir/adapter-path suffix: `final-from-<2250+N>`.
5. Same resolve dance: temp-edit `config_mlx.yaml`'s lr_schedule → wrapper
   `--print-command` with the values above (keep `--save-every 100`) →
   verify the resolved yaml → revert `config_mlx.yaml` → launch
   `caffeinate -dims .mlx_venv/bin/mlx_lm.lora -c <resolved>` as a
   main-session background task (`run_in_background`).
6. Epoch END state = a run whose log reaches its final iter and saves
   `adapters.safetensors` with a clean process exit (code 0). Then: run the
   eval per `finetune/runs/EVAL_RUNBOOK.md` (~1h — fits inside typical kill
   windows; if killed, eval resumes via its own predictions.jsonl
   checkpointing). Do NOT start a second epoch (owner gate).

Accounting so far: overall iters 0–2250 trained under runs
2026-08-20-epoch1 (0–500) and 2026-08-21-epoch1-resume-from-500
(500–2250); this run covers 2250–5736 as its local iters 0–3486.
