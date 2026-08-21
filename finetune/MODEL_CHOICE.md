# MODEL_CHOICE — base model for QLoRA fine-tuning

**No weights have been downloaded.** This document records the planned
choice and its rationale so `train_qlora.py --dry-run` and the eventual
gated real run reference a concrete, documented decision rather than a
placeholder.

## Chosen model

**`Qwen/Qwen2.5-7B-Instruct`** (Hugging Face model id), 7.6B parameters.

## Why this one, among 7-8B open-license instruct models

Candidates considered: `meta-llama/Llama-3.1-8B-Instruct`,
`mistralai/Mistral-7B-Instruct-v0.3`, `Qwen/Qwen2.5-7B-Instruct`.

- **License terms that matter for this project**: Llama 3.1's community
  license carries commercial-use conditions (a >700M-MAU clause, and an
  acceptable-use policy with output-attribution requirements) that are
  irrelevant to this small research project but add license-reading
  overhead. Mistral-7B-v0.3 is Apache-2.0 (no meaningful restriction).
  Qwen2.5-7B-Instruct is **Apache-2.0** — permissive, no field-of-use
  restriction, no attribution requirement beyond standard Apache-2.0 notice
  preservation, safe for a non-commercial research/screening tool and would
  remain safe even if this ever became commercial. Apache-2.0 was preferred
  over Llama's community license specifically to avoid re-reading license
  terms again if the project's status changes later — a boring, unambiguous
  license fits this project's "mature and boring over new and clever" stack
  philosophy (`DISCOVERY.md` §4).
- **Structured-JSON-output track record**: Qwen2.5-Instruct models are
  commonly used and documented for structured/JSON-constrained output tasks
  and function-calling-style fine-tunes, which matches this project's
  fixed-schema extraction task well.
- **Size**: 7.6B fits the "7-8B class" target for `ROADMAP.md` Phase D, and
  — on the ratified path — 4-bit QLoRA-trains on the owner's 16 GB M5 under
  MLX at **$0**, in the narrow configuration `MLX_FEASIBILITY.md` §0
  specifies (`batch_size: 1`, `max_seq_length: 2048`,
  `grad_checkpoint: true`, `num_layers: 16`). It would also QLoRA-train
  comfortably on a single 24 GB-class rented GPU, but that route is a
  **not-pre-approved fallback**, not the plan, and there is no budget line
  for it: the old $50 project ceiling is superseded by the flat spend
  freeze at $33.51 (`HANDOFF.md` §5).
- **Community support / staleness risk**: actively maintained model family
  with wide `transformers`/`peft` compatibility at the time this was chosen
  (within this assistant's training-data familiarity) — but see the caveat
  below.

## License verification — VERIFIED LIVE 2026-08-18

**Status: Apache-2.0 confirmed against the live Hugging Face model page and
the repository's own `LICENSE` file. No blocker. No alternative needed.**

Checked 2026-08-18 (research pass only — no weights downloaded, no packages
installed):

| Check | Result | Source |
|---|---|---|
| Model card license tag | `apache-2.0` | https://huggingface.co/Qwen/Qwen2.5-7B-Instruct |
| API metadata `license` | `apache-2.0` | https://huggingface.co/api/models/Qwen/Qwen2.5-7B-Instruct |
| `gated` / `disabled` | `false` / `false` — **not gated, not removed**, no click-through or access request | same API endpoint |
| `LICENSE` file present in repo listing | Yes, 11.3 kB | https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/tree/main |
| `LICENSE` file contents | Standard **unmodified Apache License 2.0** ("Apache License / Version 2.0, January 2004"). Only customization is `Copyright 2024 Alibaba Cloud` in the trailing boilerplate. **No appended acceptable-use policy, no field-of-use restriction, no extra clauses.** | https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/raw/main/LICENSE |
| Model identity | `Qwen2ForCausalLM`, `model_type: qwen2`, 7,615,616,512 params (BF16), 28 layers, vocab 152,064 | https://huggingface.co/Qwen/Qwen2.5-7B-Instruct/raw/main/config.json |
| Repo last modified | 2025-01-12 | HF API |

This closes the "re-check before Step 5" caveat for **license and
availability**. The original rationale above (Apache-2.0 over Llama's
community license) stands unchanged and is now confirmed rather than
assumed.

### Still open (not a license question)

- **Newer point releases now exist** — the Qwen3 / Qwen3.5 families have
  shipped since this doc was written, and `mlx-lm` carries model code for
  `qwen3`, `qwen3_moe`, `qwen3_next`, `qwen3_5`, `qwen3_5_moe`. **No
  substitution is being made here**; whether to move off Qwen2.5-7B-Instruct
  is the owner's call at the Phase D GO gate, not a research-pass decision.
  One datum that argues *for* staying on Qwen2.5 for a local MLX run:
  Qwen3.5's hybrid-linear architecture currently **fails LoRA training on
  MLX** on the first backward pass, including on M5-generation hardware
  (ml-explore/mlx-lm issue #1206, open as of this check). Qwen2.5 is a plain
  transformer (`model_type: qwen2`) and is not affected. See
  `MLX_FEASIBILITY.md`.
- **A pre-quantized 4-bit MLX build exists**:
  `mlx-community/Qwen2.5-7B-Instruct-4bit`, also tagged `apache-2.0`, 4-bit
  / group_size 64 (~4.0 GiB). Its HF metadata lists `base_model:
  Qwen/Qwen2.5-7B` (the **base**, not `-Instruct`) — that is probably an
  auto-populated metadata slip given the repo id, but it is unverified.
  Confirm the chat template and an instruct-style generation before
  trusting it, or quantize from the official repo instead. See
  `MLX_FEASIBILITY.md` §6.
- **No weights are downloaded by any script in this repo.** `train_qlora.py`
  only references the model id as a config string. Pulling weights happens
  only during a real, owner-approved training run — which on the ratified
  path is a **local, $0 MLX download** (`MLX_FEASIBILITY.md` §6 recommends
  `mlx-community/Qwen2.5-7B-Instruct-4bit`, ~4.0 GiB), not a GPU rental.
  Rental remains the not-pre-approved fallback if local MLX proves
  infeasible.

## Non-goals reaffirmed

This model classifies filing text into the fixed sentiment/red-flag/
guidance-direction schema. It is not used to generate free-text advice,
does not connect to any brokerage or execution system, and its outputs feed
`quant-modeler`'s feature engineering, not any trading decision.
