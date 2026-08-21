# MLX_FEASIBILITY — can Qwen2.5-7B-Instruct 4-bit QLoRA run on the M5?

**Status: paper study, 2026-08-18. Nothing installed, nothing downloaded,
no weights, no model, no packages.** This document exists so that whether
Phase D happens at all — and if so, in what configuration — is decided
against real numbers instead of a guess. The gate itself is `ROADMAP.md`
Phase C's GO/NO-GO (`HANDOFF.md` §6 Step 4, the owner's backtest read);
the MLX run this document sizes is Step 5, downstream of it. Phase D
remains gated on the owner's GO and is not started.

**Scope note:** this file only *describes* what `config.yaml` would need to
become. It does not modify `config.yaml`, `README.md`, or any code.

---

## 0. Verdict

**Feasible — but only in a narrow configuration, and not at the settings
`config.yaml` currently specifies.**

The honest one-line answer:

> **Feasible at `batch_size: 1`, `max_seq_length: 2048`,
> `grad_checkpoint: true`, `num_layers: 16`, with
> `grad_accumulation_steps: 4` to recover the effective batch size of 4 that
> `config.yaml` wants. Estimated steady-state peak **~6.7–8.6 GiB** (the
> rollup in §3.5, restated in §9) against a ~10.7–12 GiB practical GPU
> ceiling on a 16 GB Mac. `batch_size: 2` is marginal (~9–11 GiB, right at
> the ceiling). `batch_size: 4` — the current `config.yaml` value — will not
> fit and should be assumed to fail.**

Wall-clock is the bigger practical constraint, not memory: **one epoch over
the 5,736 training examples is estimated at 5–13 hours (best guess ~6–10 h)**,
so `config.yaml`'s `num_train_epochs: 3` is a **15–39 hour** job, not an
overnight run. Plan for one epoch first.

Confidence: **memory — high** (derived from the model's own published
config, arithmetic shown in §3). **Wall-clock — low-to-moderate**; there is
no published `mlx-lm` LoRA training benchmark for a base M5 with a 7B 4-bit
model. §4 gives the measurement procedure that replaces the estimate with a
real number in about two minutes of runtime.

### Blockers found: none. Traps found: five.

| # | Trap | Where |
|---|---|---|
| 1 | Sequences are **~1,220 tokens, not ~350 words** — the fixed instruction adds ~470 tokens to every example | §2 |
| 2 | `mlx-lm` **truncates over-length sequences from the end**, which silently destroys the JSON answer on ~0.5% of train / ~6% of eval rows | §2.3 |
| 3 | The prepared JSONL schema (`instruction`/`input`/`output`) **is not a format `mlx-lm` accepts** | §5 |
| 4 | `lora_alpha` has **no meaning in MLX** — it uses a direct `scale`, so a naive port silently changes the effective LoRA strength | §5 |
| 5 | `optim: paged_adamw_8bit`, `nf4`, and double-quant **do not exist in MLX** and cannot be carried over | §5 |

---

## 1. The machine, verified on-box

Read directly from the owner's Mac on 2026-08-18, not assumed:

| Property | Value | How obtained |
|---|---|---|
| Chip | Apple M5 | `sysctl machdep.cpu.brand_string` |
| GPU | 10 cores, Metal 4 | `system_profiler SPDisplaysDataType` |
| Unified memory | 16 GB | `sysctl hw.memsize` |
| macOS | 26.5.1 (build 25F80) | `sw_vers` |
| Free disk | 348 GiB | `df -h` |
| `iogpu.wired_limit_mb` | `0` (i.e. system default, not raised) | `sysctl iogpu` |
| System Python | 3.9.6 | `python3 -V` |
| mlx / mlx-lm / torch / transformers | **none installed** | import check |

Memory bandwidth for the base M5 is **153 GB/s**, ~28% above M4's 120 GB/s;
each GPU core carries a Neural Accelerator
([Apple Newsroom, 2025-10-14](https://www.apple.com/newsroom/2025/10/apple-unleashes-m5-the-next-big-leap-in-ai-performance-for-apple-silicon/);
[Apple ML Research, 2025-11-19](https://machinelearning.apple.com/research/exploring-llms-mlx-m5)).

**Two environment facts that block a naive `pip install`:**

- `mlx` 0.32.1 and `transformers` 5.15.0 both declare
  `requires_python >=3.10` (PyPI, checked 2026-08-18). The system Python is
  **3.9.6**, so Phase D needs a Python 3.10+ virtualenv. This is not
  optional.
- `mlx-lm` 0.31.3 depends on `mlx>=0.31.2` and `transformers>=5.0.0`
  ([PyPI mlx-lm](https://pypi.org/pypi/mlx-lm/json), checked 2026-08-18).
  None of this touches `requirements-finetune.txt`'s CUDA stack — see §5.

---

## 2. What the sequences actually look like

This is the single most consequential finding in this document, and it
contradicts the "~350-word chunks" framing carried through `chunk.py`'s
`TARGET_WINDOW_WORDS = 350` and repeated in `README.md` and `ROADMAP.md`:
the packed training records are far longer than the chunk target, because
each record is a constant 260-word instruction plus the passage plus the
answer.

Measured directly over `finetune/prepared/{train,eval}.jsonl` (5,736 /
1,010 records; `instruction` confirmed byte-identical across every record,
as `PROMPT_TEMPLATE.md` requires). **All percentiles are
`numpy.percentile` defaults (linear interpolation)** — the convention is
stated because other conventions shift these cells by up to ~0.3%:

| | train (n=5,736) | eval (n=1,010) |
|---|---|---|
| `instruction` | 1,825 chars / 260 words (**constant**) | same |
| `input` words — mean / p50 / p95 / max | 407 / 394 / 545 / 1,345 | 455 / 408 / 880 / 1,203 |
| `output` chars — mean / max | 110 / 422 | 129 / 467 |
| **Total chars** — mean / p50 / p95 / p99 / max | 4,653 / 4,550 / 5,659 / 6,962 / **11,443** | 5,071 / 4,692 / 8,345 / 10,072 / 10,872 |
| **Total words** — mean / p95 / max | 675 / 815 / 1,611 | 724 / 1,156 / 1,481 |

### 2.1 Token estimate (no tokenizer was loaded)

No tokenizer is available offline and downloading one was out of scope, so
these are **estimates**, presented as a band rather than a number:

| Method | train mean | train p95 | train p99 | train max | epoch total |
|---|---|---|---|---|---|
| `chars / 4.0` | 1,163 | 1,415 | 1,740 | 2,861 | 6.67 M |
| `chars / 3.8` | 1,224 | 1,489 | 1,832 | 3,011 | 7.02 M |
| `words × 1.35` (the multiplier `config.yaml` uses) | 911 | 1,100 | 1,342 | 2,175 | 5.23 M |

The `words × 1.35` figure in `config.yaml` is very likely an
**underestimate**: the corpus is punctuation- and numeral-heavy filing prose
and the target is JSON with uppercase enum tokens, both of which tokenize
worse than plain English. The text averages 6.9 chars/word including
spaces, which at a typical English BPE rate of ~3.8–4.2 chars/token implies
~1.65–1.8 tokens/word, not 1.35.

**Working assumption used throughout this document: ~1,220 tokens mean,
~7.0 M tokens per training epoch.** Treat as ±20%.

> **First Phase D task, and it is free:** download only
> `tokenizer.json` (7.0 MB) + `tokenizer_config.json` from the model repo —
> no weights — and re-measure exactly. This replaces every estimate below
> with a measured number and costs nothing. `config.yaml`'s own comment
> already asks for this ("Re-measure with the real Qwen2.5 tokenizer before
> finalizing max_seq_length for a real run").

### 2.2 ~38% of every sequence is the same 470 tokens

The byte-identical instruction is ~1,825 chars ≈ **~470 tokens**, i.e.
**~38% of the mean 1,224-token sequence**, repeated identically across all
5,736 training examples. `mlx-lm` does **not** cache a shared prompt prefix
during training, so roughly **2.7 M of the ~7.0 M tokens per epoch are spent
re-encoding the same instruction**.

Shortening the instruction for the fine-tune would cut epoch time by roughly
a third. **This is flagged as a tradeoff, not a recommendation** —
`PROMPT_TEMPLATE.md` makes the byte-identical instruction a deliberate,
documented contract that keeps training-time and inference-time text
exposure consistent with the bootstrap labeling prompts. Changing it is a
design decision for the owner, and it would have to be mirrored in
`eval.py`'s inference path or the eval becomes invalid.

### 2.3 Truncation trap (correctness, not just capacity)

`mlx-lm`'s batch builder truncates any sequence longer than
`max_seq_length` — **and it truncates the tail**
([`mlx_lm/tuner/trainer.py`](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/trainer.py),
lines ~149–167: `batch_arr[j, :truncated_length] = batch[j][:truncated_length]`,
emitting only a `[WARNING]`).

For this dataset the answer is the **last ~30 tokens of the sequence**. So a
truncated example is not merely shortened — it becomes a prompt with its
target JSON amputated. With `mask_prompt: true` (recommended, §5) such a row
contributes a degenerate or empty loss mask.

Share of rows exceeding each cap (`chars/3.8` estimate):

| `max_seq_length` | train over-cap | eval over-cap |
|---|---|---|
| 1,024 | 5,494 (95.8%) | 905 (89.6%) |
| 1,536 | 232 (4.04%) | 173 (17.1%) |
| **2,048** | **30 (0.52%)** | **64 (6.34%)** |

**Recommendation:** set `max_seq_length: 2048` *and* pre-process the
over-length rows explicitly rather than letting the tail-truncation fire —
either drop them, or truncate the **`input` passage** (head side) while
preserving the completion intact. Do this in the JSONL conversion step
(§5), where it is visible and testable, not silently inside the trainer.
Note the eval split is materially longer than train (p95 2,196 vs 1,489 est.
tokens), so eval is where this bites.

Do **not** drop to `max_seq_length: 1024` to save memory — it would truncate
96% of the training set.

---

## 3. Memory budget

Arithmetic from Qwen2.5-7B-Instruct's published
[`config.json`](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/raw/main/config.json)
(checked 2026-08-18): `vocab_size` 152,064 · `hidden_size` 3,584 ·
`intermediate_size` 18,944 · 28 layers · 28 heads / 4 KV heads (GQA) ·
`tie_word_embeddings: false` · 7,615,616,512 params.

### 3.1 Weights — 3.99 GiB, fixed

MLX 4-bit uses affine group-wise quantization at `group_size: 64`, giving
`4 + 32/64 = 4.5` effective bits/weight. Confirmed empirically against
`mlx-community/Qwen2.5-7B-Instruct-4bit`'s safetensors metadata: 951,910,400
`U32` (= 7.615 B packed 4-bit values) + 238,310,912 `F16` (= exactly 2 scale/bias
values per 64-weight group). That is **3.99 GiB resident, always**.

Note this is **not** bitsandbytes NF4 and there is no double-quantization —
see §5.

### 3.2 Adapters + optimizer — 14 MB to 404 MB

| LoRA config | Params | bf16 weights | AdamW (m,v) | Total |
|---|---|---|---|---|
| `mlx-lm` default: r=8, 16 layers, q+v | 1.44 M | 2.9 MB | 11.5 MB | **14 MB** |
| r=16, 16 layers, q+v | 2.88 M | 5.8 MB | 23.1 MB | **29 MB** |
| r=16, 16 layers, all 7 projections | 23.07 M | 46.1 MB | 184.5 MB | **231 MB** |
| **`config.yaml`-equivalent: r=16, 28 layers, all 7** | **40.37 M** | 80.7 MB | 323.0 MB | **404 MB** |

Even the heaviest option is a rounding error against the 3.99 GiB of
weights. **Adapter capacity is not the memory constraint** — so there is no
reason to cut LoRA rank or target modules to save memory. Cut `num_layers`
only for the activation saving described in §3.4.

### 3.3 The logits tensor — the real constraint

Qwen2.5's 152,064-token vocabulary makes the output projection the dominant
activation on a 16 GB machine. Per forward+backward, at bf16:

| | seq 1,024 | seq 1,536 | seq 2,048 |
|---|---|---|---|
| **batch 1** | 0.58 GiB | 0.87 GiB | **1.16 GiB** |
| **batch 2** | 1.16 GiB | 1.74 GiB | **2.32 GiB** |
| **batch 4** | 2.32 GiB | 3.48 GiB | **4.64 GiB** |

If cross-entropy materializes an fp32 copy (`trainer.py`'s `default_loss`
does `ce.astype(mx.float32)`), add ~50%: batch 4 at seq 2,048 reaches
**~6.96 GiB for logits alone**.

**This single term is what rules out `batch_size: 4`.** It scales linearly
in batch × sequence and is unaffected by gradient checkpointing.

### 3.4 Activations

With `grad_checkpoint: true`, only layer-boundary activations persist:

| | 16 trainable layers | 28 trainable layers |
|---|---|---|
| batch 1, seq 2,048 | 0.219 GiB | 0.383 GiB |
| batch 2, seq 2,048 | 0.438 GiB | 0.766 GiB |

Without checkpointing, the MLP intermediates alone (gate/up/SiLU at
`intermediate_size` 18,944) come to ~175 MB **per layer** at batch 1 /
seq 1,536 → **~4.55 GiB across 28 layers**. `grad_checkpoint: true` is
therefore mandatory, not an optimization.

`num_layers: 16` (the `mlx-lm` default — adapters on the top 16 layers only)
also means the bottom 12 layers run forward-only, avoiding their backward
graph entirely. That is the main reason to prefer 16 over 28 here.

### 3.5 Rolled up

Batch 1 · seq 2,048 · `grad_checkpoint: true` · `num_layers: 16` · r=16 q+v:

| Component | GiB |
|---|---|
| 4-bit weights | 3.99 |
| LoRA + AdamW state | 0.03 |
| Logits fwd + grad | 1.16 (1.74 if fp32 CE) |
| Checkpointed activations | 0.22 |
| Attention + recompute working set | ~0.3–0.6 |
| MLX allocator cache / fragmentation | ~1–2 |
| **Estimated peak** | **~6.7–8.6** |

Against the ceiling: Metal's `recommendedMaxWorkingSetSize` on a 16 GB Mac
is roughly **10.7–12 GiB** (~2/3 to 3/4 of RAM; sources disagree on the
exact fraction, and it is worth reading on-machine rather than trusting
either figure). `mlx-lm`'s trainer sets the wired limit to exactly that
value at startup (`trainer.py` line ~230:
`mx.set_wired_limit(mx.device_info()["max_recommended_working_set_size"])`).

So batch 1 leaves **roughly 2–5 GiB of headroom**. Batch 2 (~9–11 GiB) lands
on the ceiling with essentially none. Batch 4 exceeds it.

**Because headroom is thin, run headless:** close other apps, and note that
`iogpu.wired_limit_mb` is currently `0` (default) and can be raised with
`sudo sysctl iogpu.wired_limit_mb=<MB>` if needed. Also relevant:
[mlx-lm issue #3267](https://github.com/ml-explore/mlx/issues/3267) reports
the Metal GPU watchdog killing LoRA training when the display is active.

---

## 4. Wall-clock

### 4.1 Published anchors

| Anchor | Throughput | Source |
|---|---|---|
| Mistral-7B QLoRA, batch 1, 4 LoRA layers, **M1 Max 32 GB** | ~250 tok/s | [mlx-examples/lora/README.md](https://github.com/ml-explore/mlx-examples/blob/main/lora/README.md) |
| Llama-7B LoRA, default settings, **M2 Ultra** | ~475 tok/s | same |
| Qwen3-8B **full** fine-tune, batch 1, 16 layers, `--grad-checkpoint`, seq 5,000, **Mac Studio 128 GB** | 250–360 tok/s, peak mem 31.8–34.1 GB | [mlx-lm issue #236](https://github.com/ml-explore/mlx-lm/issues/236) (measured log) |

**No published `mlx-lm` LoRA-training benchmark exists for a base M5.**
Apple's own M5 numbers
([ML Research, 2025-11-19](https://machinelearning.apple.com/research/exploring-llms-mlx-m5))
are **inference only** — 3.19–4.06× faster time-to-first-token vs M4 and
1.19–1.27× faster generation — and are not transferable to a training loop.

Extrapolating is genuinely uncertain in both directions: the base M5 has 10
GPU cores against the M1 Max's 32 (and 153 GB/s against 400 GB/s), which
argues for *slower*; but LoRA training at ~1,200-token sequences is
GEMM-bound rather than bandwidth-bound, and the M5's per-core Neural
Accelerators target exactly that, which argues for *faster*. These roughly
offset, with wide error bars.

**Working band: 150–400 tok/s. Point estimate: ~250 tok/s.**

### 4.2 Epoch time

Over ~7.0 M estimated tokens/epoch (5,736 examples), batch 1:

| Throughput | s/iter (mean 1,224 tok) | 1 epoch | 3 epochs (`config.yaml`) |
|---|---|---|---|
| 150 tok/s | 8.2 s | **13.0 h** | 39.0 h |
| 250 tok/s | 4.9 s | **7.8 h** | 23.4 h |
| 400 tok/s | 3.1 s | **4.9 h** | 14.6 h |

`grad_checkpoint: true` is already assumed in these anchors; if it were not,
subtract roughly 20–30%.

**Consequence for planning:** ROADMAP Step 5 says "run overnight on the M5."
One epoch is an overnight run. **Three epochs is not** — it is one to two
full days. Recommend `iters` for a single epoch first (5,736 at batch 1),
evaluate, and only extend if the eval justifies it.

### 4.3 Replace this estimate before committing

Run 20 iterations and read the real number off `mlx-lm`'s own progress line,
which prints `It/sec`, `Tokens/sec`, and `Peak mem` every
`steps_per_report`. Two minutes of runtime collapses the 5–13 h band to a
single figure and confirms the §3 memory estimate at the same time.

> **Caveat when reading `Tokens/sec`:** `default_loss` computes
> `ntoks = mask.sum()`, so the reported figure counts **loss-bearing tokens,
> not processed tokens**. With `mask_prompt: true` only the ~30-token
> completion is masked in, so the reported Tokens/sec will read ~40× lower
> than the actual compute throughput while wall-clock per iteration is
> unchanged. Use `It/sec` × mean sequence length for the real number, and do
> not panic at a "Tokens/sec: 6" line.

---

## 5. What `config.yaml` would need to become

`config.yaml` was written for a CUDA / bitsandbytes / HF-Trainer stack. It
is not portable to MLX by renaming keys — several of its settings name
things that **do not exist** in MLX. **This section is documentation only;
`config.yaml` is not modified.**

Reference for the target schema:
[`mlx_lm/examples/lora_config.yaml`](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/examples/lora_config.yaml)
and [`LORA.md`](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md).

### 5.1 Settings with no MLX equivalent — must be dropped

| `config.yaml` key | Why it cannot carry over |
|---|---|
| `bnb_4bit_quant_type: "nf4"` | MLX uses affine group-wise quantization, **not NF4**. Not a rename — a different quantizer. |
| `bnb_4bit_use_double_quant: true` | No double-quantization in MLX. |
| `bnb_4bit_compute_dtype: "bfloat16"` | Not exposed; MLX computes in the model's dtype. |
| `load_in_4bit: true` | Not a flag. QLoRA is implicit: *"If `--model` points to a quantized model, then the training will use QLoRA"* (LORA.md). |
| **`optim: "paged_adamw_8bit"`** | **No paged or 8-bit optimizers in MLX.** Only `adamw` / `adam` / `sgd`, with fp32 state. Harmless here (§3.2 shows optimizer state is ≤323 MB), but it cannot be specified. |
| `bf16: true` | Not a flag. |
| `trust_remote_code: false` | Not a training arg (Qwen2.5 does not need it regardless). |
| `lora.bias`, `lora.task_type` | PEFT-only concepts. |
| `save_total_limit: 3` | No equivalent; `mlx-lm` keeps every checkpoint. Adapters are small (≤81 MB), so this is a non-issue on 348 GiB free. |
| `eval_strategy`, `report_to` | No equivalent. |

### 5.2 Renames and semantic changes

| `config.yaml` | MLX key | Note |
|---|---|---|
| `base_model_id` | `model` | Point at a **4-bit** path — see §6. |
| `lora.r: 16` | `lora_parameters.rank: 16` | Same meaning. |
| **`lora.lora_alpha: 32`** | **`lora_parameters.scale`** | ⚠️ **Trap.** MLX has no `alpha`; `scale` is a direct multiplier. The PEFT equivalent is `alpha/r = 32/16 =` **`scale: 2.0`**. The `mlx-lm` example config ships `scale: 20.0`. Copying `32` across, or leaving the default, silently changes effective adapter strength by 10×. (Note [issue #1185](https://github.com/ml-explore/mlx-lm/issues/1185)'s config carries both `alpha` and `scale` — `alpha` is simply ignored.) |
| `lora.lora_dropout: 0.05` | `lora_parameters.dropout: 0.05` | Same. |
| `lora.target_modules` | `lora_parameters.keys` | Needs MLX module paths: `["self_attn.q_proj", "self_attn.k_proj", "self_attn.v_proj", "self_attn.o_proj", "mlp.gate_proj", "mlp.up_proj", "mlp.down_proj"]`. Default is only `q_proj` + `v_proj`. |
| — | `num_layers` | **New, no `config.yaml` analogue.** How many top layers get adapters. Default 16; `config.yaml` implies all 28. Recommend 16 (§3.4). |
| `data.train_path` / `eval_path` | `data: <directory>` | ⚠️ `mlx-lm` takes a **directory** containing `train.jsonl` / `valid.jsonl` / `test.jsonl`. Note **`valid.jsonl`**, not `eval.jsonl` — a rename is required. |
| `data.max_seq_length: 2048` | `max_seq_length: 2048` | Moves to top level. Keep 2048 (§2.3). |
| `num_train_epochs: 3` | `iters` | ⚠️ **`mlx-lm` has no epoch concept.** One epoch at batch 1 = **5,736 iters**. |
| `per_device_train_batch_size: 4` | `batch_size` | ⚠️ **Must drop to 1** (§3.3). |
| `gradient_accumulation_steps: 4` | `grad_accumulation_steps: 4` | Exists; keeps effective batch 4. |
| `gradient_checkpointing: true` | `grad_checkpoint: true` | Mandatory (§3.4). |
| `lr_scheduler_type: cosine` + `warmup_ratio: 0.03` | `lr_schedule: {name: cosine_decay, arguments: [...], warmup: N, warmup_init: ...}` | ⚠️ `warmup` is in **steps**, not a ratio. 0.03 × 5,736 ≈ **172 steps**. |
| `weight_decay: 0.0` | `optimizer_config: {adamw: {weight_decay: 0.0}}` | Nested, not top-level. |
| `logging_steps` / `eval_steps` / `save_steps` | `steps_per_report` / `steps_per_eval` / `save_every` | Direct renames. |
| `output_dir` | `adapter_path` | Adapters only, not a full model. |
| `learning_rate: 2.0e-4` | `learning_rate` | Carries over. (`mlx-lm`'s example default is 1e-5; 2e-4 is a normal LoRA LR, but it interacts with the `scale` fix above — settle `scale` first.) |
| — | `mask_prompt` | **New.** See §5.4. |
| — | `train: true`, `fine_tune_type: lora`, `optimizer: adamw`, `val_batches`, `clear_cache_threshold` | New required/useful keys. |

`gpu_rental_placeholder` is irrelevant on this path — the whole point of MLX
is that it stays at $0 and the "NOT APPROVED" fallback is never invoked.

### 5.3 The dataset needs converting — the current JSONL is not a valid input

`prepare_dataset.py` emits `{chunk_id, instruction, input, output}`.
`mlx-lm` accepts exactly three shapes
([datasets.py](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/datasets.py)):

- `{"messages": [...]}` (chat)
- `{"prompt": ..., "completion": ...}` (completions)
- `{"text": ...}` (raw)

**None of these match.** `prompt_feature` / `completion_feature` are
configurable, but that cannot help here because there are **two** prompt
fields (`instruction` and `input`) that must be concatenated into one. So a
real conversion step is required, not a config rename. It must:

1. Join `instruction` + separator + `input` → `prompt`; `output` → `completion`.
2. Drop `chunk_id` (or keep a sidecar mapping — `mlx-lm` ignores extra keys,
   but the eval path will want the mapping back).
3. Write `train.jsonl` + **`valid.jsonl`** into one directory.
4. Handle the over-length rows from §2.3 explicitly.

**This is new code, and it must not touch `prepare_dataset.py`'s existing
output** — `PROMPT_TEMPLATE.md` defines that format as deliberately
framework-agnostic ("kept separate from any model-specific chat-template
rendering so switching base models doesn't require re-deriving the
dataset"). The MLX conversion is exactly the model-specific rendering step
that document anticipates. Write it as a separate script.

### 5.4 `mask_prompt` — a real modelling decision, not a default

With ~1,190 prompt tokens against a ~30-token completion:

- `mask_prompt: false` (the `mlx-lm` default) trains the model to reproduce
  the instruction and the filing passage as well as the answer. ~97.6% of
  the gradient signal goes to text the model will never need to generate.
- `mask_prompt: true` computes loss on the completion only — standard for
  fixed-schema extraction, and the right choice here: the deliverable is a
  structured extractor, and `eval.py`'s `parse_model_output` scores only
  the emitted JSON.

Worth stating plainly: with masking on, one epoch carries only **~170 K
loss-bearing tokens** across 5,736 examples. That is a small training
signal, and it is a reason to expect modest gains and to hold the
Phase C numeric baseline as the comparison, exactly as ROADMAP Step 5
already requires.

---

## 6. Model artifact: download 4-bit, do not convert locally

Two routes to a 4-bit model:

1. **Convert locally** — `mlx_lm.convert --hf-path Qwen/Qwen2.5-7B-Instruct
   --quantize --q-bits 4`. **Not recommended on this machine.** It requires
   downloading 15.2 GB of bf16 safetensors and holding the unquantized model
   in memory to quantize it, on a box with 16 GB total and a ~10.7–12 GiB
   GPU working-set ceiling. Disk is fine (348 GiB free); RAM is the problem.
2. **Download the pre-quantized build** —
   [`mlx-community/Qwen2.5-7B-Instruct-4bit`](https://huggingface.co/mlx-community/Qwen2.5-7B-Instruct-4bit),
   `apache-2.0`, not gated, `quantization: {group_size: 64, bits: 4}`,
   `model_type: qwen2`, ~4.0 GiB. **Recommended.**

⚠️ **Verify before trusting route 2.** That repo's HF metadata lists
`base_model: Qwen/Qwen2.5-7B` — the **base** model, not `-Instruct`. This is
probably an auto-populated metadata slip (the repo id, config, and tokenizer
all say Instruct), but it is unverified, and per HANDOFF §7's "verify the
submitted artifact is the tested artifact" rule it should be confirmed by
checking the chat template and running one instruct-style generation before
any training run. If it fails that check, fall back to route 1 on a machine
with more RAM, or accept the download-and-convert cost.

---

## 7. Architecture support, and the M5 scare that isn't one

**Qwen2.5 is supported.** `LORA.md` lists supported families as *"Mistral,
Llama, Phi2, Mixtral, Qwen2, Gemma, OLMo, MiniCPM, InternLM2"* — it says
**Qwen2**, not Qwen2.5, which reads like a gap but is not one:
Qwen2.5-7B-Instruct declares `model_type: qwen2` and
`architectures: ["Qwen2ForCausalLM"]`, and `mlx-lm` ships
`mlx_lm/models/qwen2.py`. Same code path. No gap.

**The M5 LoRA crash report does not apply.**
[mlx-lm issue #1206](https://github.com/ml-explore/mlx-lm/issues/1206)
(opened 2026-04) reports LoRA training crashing on the *first backward pass*
on an **M5 Max** with `[METAL] Command buffer execution failed: Insufficient
Memory`, at any batch size, sequence length, or layer count. Alarming for
this project's hardware — but it resolves in our favour on inspection:

- The reporter's own workaround: *"Switching to
  `mlx-community/Qwen3-8B-4bit` (same architecture family, previous
  generation) trains successfully with identical settings."*
- Maintainer-adjacent diagnosis in-thread attributes it to **Qwen3.5's
  hybrid-linear architecture** — recurrent/linear-scan states that MLX's
  graph compiler cannot checkpoint, producing an O(n×d) blow-up in the
  backward pass through the scan op.
- It is **not M5-specific**: another commenter reproduces it on an M1 Pro.
- The related descriptor-leak report
  ([#1185](https://github.com/ml-explore/mlx-lm/issues/1185)) is likewise
  confined to `model_type: qwen3_5`.

Qwen2.5 is a plain transformer with standard GQA attention and is not in
scope for either bug. **This is a concrete argument for staying on Qwen2.5
rather than "upgrading" to a newer Qwen for the local MLX path** — recorded
in `MODEL_CHOICE.md`, decision left to the owner.

### One open upstream issue that *does* apply

[mlx-lm issue #828](https://github.com/ml-explore/mlx-lm/issues/828),
**open**, "Memory during training (LoRA)": MLX's default wired/cache limits
are tuned for inference, and training memory *creeps per iteration* until
hard crashes or forced reboots. The reporter hit this on a **48 GB**
machine. Workarounds from the thread:

- Set the wired limit to ~90% of `max_recommended_working_set_size` rather
  than 100% — *"everything is stable"*.
- Drop `cache_limit` low or to zero — *"my memory never climbs, no crashes
  or memory pressure, and I don't see any performance impact"*.
- Setting all three limits to zero still runs at ~80% speed.

`mlx-lm` exposes `clear_cache_threshold` today (default `0`);
[PR #1312](https://github.com/ml-explore/mlx-lm/pull/1312) proposes
`--wired-limit-ratio` / `--memory-limit-ratio` / `--cache-limit-ratio` but
was not merged as of this check. **On a 16 GB machine this is the most
likely cause of a failed overnight run**, so set a modest
`clear_cache_threshold` and watch `Peak mem` over the first few hundred
iterations for drift rather than assuming a stable first 20 iterations
generalizes.

---

## 8. Recommended starting configuration

To be re-validated by the §4.3 twenty-iteration probe **before** committing
to a long run. Presented as a target for Phase D; **not written to
`config.yaml`**.

```yaml
model: mlx-community/Qwen2.5-7B-Instruct-4bit   # verify per §6 first
train: true
fine_tune_type: lora
optimizer: adamw

data: ./prepared_mlx        # directory: train.jsonl + valid.jsonl (§5.3)
mask_prompt: true           # §5.4 — deliberate, not the default

batch_size: 1               # §3.3 — NOT 4
grad_accumulation_steps: 4  # recovers config.yaml's effective batch of 4
max_seq_length: 2048        # §2.3 — over-length rows pre-handled, not tail-truncated
grad_checkpoint: true       # §3.4 — mandatory
num_layers: 16              # §3.4

iters: 5736                 # ONE epoch at batch 1 — not 3 epochs (§4.2)
learning_rate: 2.0e-4
lr_schedule:
  name: cosine_decay
  arguments: [2.0e-5, 5736]
  warmup: 172               # 0.03 × 5736, in STEPS not ratio
  warmup_init: 1.0e-7

lora_parameters:
  rank: 16
  scale: 2.0                # = alpha/r = 32/16. NOT 32, NOT the 20.0 default (§5.2)
  dropout: 0.05
  keys: ["self_attn.q_proj", "self_attn.v_proj"]

clear_cache_threshold: 10   # §7 — guards the issue-#828 memory creep
val_batches: 25
steps_per_report: 10
steps_per_eval: 500
save_every: 250
seed: 42                    # matches config.yaml
adapter_path: checkpoints/qwen2.5-7b-finscreen-lora-mlx
```

Escalation order if the probe shows headroom, one change at a time:
`keys` → all 7 projections (+231 MB, §3.2) → `num_layers: 28` → only then
`batch_size: 2` (§3.3 says this is marginal).

De-escalation order if it OOMs: lower `clear_cache_threshold` → run headless
/ raise `iogpu.wired_limit_mb` → `num_layers: 8` → `max_seq_length: 1536`
(costs 4% of train rows to §2.3 handling). **Do not go to 1024** — that
truncates 96% of the training set.

---

## 9. Honest summary of what is and is not known

**Well established (arithmetic from published model config, or read
on-box):** weights at 3.99 GiB; the logits term and why batch 4 fails;
adapter/optimizer state being negligible; grad checkpointing being
mandatory; every `config.yaml` incompatibility in §5; the dataset-format
gap; the truncation trap; the machine's actual specs; Qwen2.5 = `qwen2` and
therefore supported; the license (see `MODEL_CHOICE.md`).

**Estimated, with error bars:** token counts (±20%, no tokenizer loaded —
fixable for free, §2.1); peak memory ~6.7–8.6 GiB (allocator behaviour and
whether CE materializes fp32 logits are the uncertain terms); the
~10.7–12 GiB working-set ceiling (sources disagree; read it on-machine).

**Genuinely uncertain:** **wall-clock.** No published `mlx-lm` LoRA training
benchmark exists for a base M5 at this model size. The 5–13 h/epoch band is
extrapolated from M1 Max / M2 Ultra / Mac Studio anchors across different
chip generations and core counts. Do not plan around the midpoint — run the
§4.3 probe.

**Unknowable from a paper study:** whether ~170 K loss-bearing tokens
(§5.4) is enough signal to beat the Phase C numeric baseline. That is what
Phase D would be measuring, and it is downstream of the Step 4 GO anyway.

---

## 10. Sources

All checked **2026-08-18** unless the source carries its own date.

**License and model identity** (see `MODEL_CHOICE.md` for the full
verification table)
- https://huggingface.co/Qwen/Qwen2.5-7B-Instruct
- https://huggingface.co/api/models/Qwen/Qwen2.5-7B-Instruct
- https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/raw/main/LICENSE
- https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/raw/main/config.json
- https://huggingface.co/mlx-community/Qwen2.5-7B-Instruct-4bit

**mlx-lm documentation and source** (`main` branch as of this date)
- https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md
- https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/trainer.py
- https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/tuner/datasets.py
- https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/examples/lora_config.yaml
- https://github.com/ml-explore/mlx-examples/blob/main/lora/README.md
- https://pypi.org/pypi/mlx-lm/json (0.31.3) · https://pypi.org/pypi/mlx/json (0.32.1) · https://pypi.org/pypi/transformers/json (5.15.0)

**Upstream issues**
- https://github.com/ml-explore/mlx-lm/issues/1206 — Qwen3.5 LoRA backward crash on M5 Max (opened 2026-04-27)
- https://github.com/ml-explore/mlx-lm/issues/1185 — Metal descriptor leak, qwen3_5
- https://github.com/ml-explore/mlx-lm/issues/828 — LoRA training memory creep (**open**)
- https://github.com/ml-explore/mlx-lm/issues/236 — measured Qwen3-8B full-FT throughput/memory log (2025-06-16)
- https://github.com/ml-explore/mlx/issues/3267 — Metal GPU watchdog kills LoRA training when display is active

**Apple hardware**
- https://www.apple.com/newsroom/2025/10/apple-unleashes-m5-the-next-big-leap-in-ai-performance-for-apple-silicon/ (2025-10-14)
- https://machinelearning.apple.com/research/exploring-llms-mlx-m5 (2025-11-19) — **inference only**

**Measured from this repo** — `finetune/prepared/{train,eval}.jsonl`,
`prepare_dataset.py`, `PROMPT_TEMPLATE.md`, `config.yaml`; machine specs via
`sysctl` / `system_profiler` / `sw_vers`.
