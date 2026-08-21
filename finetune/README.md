# finetune/ — Phase D QLoRA scaffolding

> ## ✅ CURRENT — artifacts regenerated 2026-08-11; this README corrected 2026-08-18
>
> `splits/` and `prepared/` were rebuilt after the 4,219-row re-label landed.
> All 6,747 rows now share one labeling config (`thinking=disabled,
> max_tokens=4000`). The split's rare-label allocation was also retuned per
> the owner's "protect training" decision: `guidance:RAISED` now has 27
> training / 7 eval examples (20.6% eval), where the previous split left
> only 12 training examples (65.7% held out). All five leakage assertions
> pass.
>
> **The path changed after this directory was built.** The ratified Phase D
> route is **local MLX 4-bit QLoRA on the owner's 16 GB M5, at $0**
> (`HANDOFF.md` §3, 2026-08-11); GPU rental is a not-pre-approved fallback,
> not the plan. Read **`MLX_FEASIBILITY.md` before any Phase D work** — it
> overturns `config.yaml`'s `batch_size: 4` and the "overnight run"
> framing. Everything in this directory written against a rented GPU and
> the HF `transformers`/`peft`/`bitsandbytes` stack is superseded
> scaffolding.

Owner: `finetune-engineer`. Consumed downstream by `quant-modeler`'s
Phase C walk-forward harness. Read `MLX_FEASIBILITY.md`, `MODEL_CHOICE.md`,
`SPLIT_DESIGN.md`, and `PROMPT_TEMPLATE.md` before touching this
directory — they're the authoritative rationale docs; this README is the
map.

## What runs locally, right now, with zero paid actions

All of the below run on `pandas`/`pyarrow`/`numpy`/`pyyaml` only (the repo's
existing `requirements.txt`), no GPU, no API calls, no downloads:

```bash
cd finetune
python3 split.py                 # carve the leakage-safe held-out eval split
python3 check_leakage.py         # verify the split (exits nonzero on failure)
python3 prepare_dataset.py       # build instruction-tuning JSONL from the split
python3 train_qlora.py --dry-run # validate config + data pipeline + (estimated) token budget
python3 eval.py --dry-run        # validate the eval/metrics pipeline against synthetic predictions
python3 test_prepare_dataset.py  # applicability-matrix + no-leakage + determinism tests
python3 test_leakage.py          # same leakage check, wrapped as a test
```

Or all local tests together:
```bash
python3 -m pytest finetune/ -v      # if pytest is available
# or, without pytest:
python3 finetune/test_prepare_dataset.py && python3 finetune/test_leakage.py
```

## What is GATED and NOT run by anything in this repo

- **Real training is gated on the owner's Phase C GO** (`ROADMAP.md` Phase C
  is the GO/NO-GO gate; `HANDOFF.md` §6 Step 4). On the ratified path it
  runs **locally via MLX at $0** — see `MLX_FEASIBILITY.md` for the only
  configuration that fits 16 GB, and note that `config.yaml`'s
  `num_train_epochs: 3` is ≈15–39 h of wall clock, not an overnight run.
  This directory's `train_qlora.py` is the **superseded HF/peft path**: its
  non-`--dry-run` branch raises `NotImplementedError` by design (it's
  scaffolding — config validation, data pipeline, planned-run printout —
  not a working training loop, because writing a loop that could not be
  run or debugged here would be more likely to hide a bug than catch one).
  GPU rental via `../requirements-finetune.txt`
  (torch/transformers/peft/bitsandbytes/accelerate) survives only as a
  fallback if local MLX proves infeasible, and is **not pre-approved**:
  it would need explicit owner sign-off on provider, instance type, and
  estimated hours. The old "$5 rule" and "$50 ceiling" it was written
  against are both superseded by the flat spend freeze (`HANDOFF.md` §5) —
  no further API spend, period.
- **Real evaluation** (`python3 eval.py --predictions <file>`) requires
  actual model output from a trained checkpoint — none exists yet.
- **No model weights are downloaded** anywhere in this directory.

## File map

| File | Deliverable | Status |
|---|---|---|
| `split.py` | #1 | Runs locally, produces `splits/{manifest,train,eval}.parquet` |
| `SPLIT_DESIGN.md` | #1 | Design doc: leakage rule, company/time tradeoff, honest limitations |
| `check_leakage.py` | #2 | Runs locally, exits nonzero on failure |
| `prepare_dataset.py` | #3 | Runs locally, produces `prepared/{train,eval}.jsonl` |
| `PROMPT_TEMPLATE.md` | #3 | Prompt template spec, look-ahead-bias rules |
| `train_qlora.py` | #4 | `--dry-run` works locally; real run gated on GPU rental approval |
| `config.yaml` | #4 | Model/LoRA/training config; GPU section explicitly marked NOT APPROVED |
| `MODEL_CHOICE.md` | #4 | Base model id, license (Apache-2.0, **verified live 2026-08-18**), rationale, caveats |
| `MLX_FEASIBILITY.md` | — | **Read before any Phase D work.** Paper study (2026-08-18; nothing installed or downloaded): can Qwen2.5-7B-Instruct 4-bit QLoRA run on the owner's 16 GB M5? Verdict: feasible only at `batch_size: 1` / `max_seq_length: 2048` / `grad_checkpoint: true` / `num_layers: 16` with `grad_accumulation_steps: 4`; ≈5–13 h per epoch; `config.yaml`'s `batch_size: 4` will not fit |
| `eval.py` | #5 | `--dry-run` works locally against synthetic predictions |
| `splits/` | #1 | `split.py` output — `manifest.parquet`, `train.parquet` (5,736), `eval.parquet` (1,010). **Authoritative for any per-ticker or per-class count** |
| `prepared/` | #3 | `prepare_dataset.py` output — `train.jsonl` / `eval.jsonl`, instruction format |
| `../requirements-finetune.txt` | #6 | Pinned deps for the superseded rented-GPU path, NOT for local install |
| `test_prepare_dataset.py` | #7 | Applicability-matrix + leakage tests (real data) |
| `test_leakage.py` | #7 | Wraps `check_leakage.py` as a test |

## Known limitations (see the linked docs for full detail, this is a summary)

1. **`SPLIT_DESIGN.md` §3–6**: the leakage-safe connected-component graph
   turns out to force near-company-level granularity for most of the
   universe (boilerplate reuse within a company's own filing history over
   time chains its chunks together). The resulting split is closer to a
   company split than a random split for most tickers, whether or not that
   was the deliberate goal — stated plainly, not hidden. A practical
   consequence is that some tickers land entirely on one side of the split.
   **For the actual per-ticker train/eval presence counts, read
   `splits/train.parquet` and `splits/eval.parquet` — those files are
   authoritative; no count is restated here.** This bullet previously
   carried hardcoded per-ticker counts that no longer matched the live
   split: they were written before the post-re-label regeneration and were
   not updated with it, so the header's "✅ CURRENT" banner was wrong for
   this bullet specifically (recorded in `HANDOFF.md` §2, "Known doc
   staleness"). The stale numbers are removed rather than re-derived,
   because they would go stale again the next time `split.py` is re-run.
2. **This split is not time-ordered.** `home_filing_date` spans both sides
   of the split — it answers "does the model generalize to unseen
   text/companies," not "does it generalize to the future." The Phase C
   walk-forward harness (`backtest.py`; `DISCOVERY.md` §5) is the actual
   test of the latter, on a different axis.
3. **`guidance:WITHDRAWN` (n=1 corpus-wide) cannot be evaluated at all** —
   it's in train, not eval, by necessity, not choice.
4. **`8K_BODY` (n=8 corpus-wide) has 0 train examples and 8 eval examples**
   from only 2 tickers — not a meaningfully learnable or evaluable
   section_type at this corpus size.
5. **`distress_tier` is excluded from training targets and from headline
   eval metrics entirely** — the binding statements are `HANDOFF.md` §7 and
   `labeling_rubric.md` §5, enforced in code by
   `assert_distress_excluded_from_headline()`; the original rationale is
   `DISCOVERY.md` §3. Not enough real signal in this 25-mega-cap universe
   to learn or evaluate it honestly, and every REALIZED class is now empty
   corpus-wide (`LIMITATIONS.md` §2.5). It remains in the raw label data
   (untouched) for anyone who wants to look at it separately later.
6. **Token counts everywhere in this pass (`config.yaml`, `train_qlora.py
   --dry-run`) are ESTIMATED** (`word_count * 1.35`), not measured with the
   real Qwen2.5 tokenizer — no tokenizer can be loaded offline in this
   environment. `MLX_FEASIBILITY.md` §2.1 specifies the free local
   re-measurement (download `tokenizer.json` only, no weights — there is no
   GPU box on the ratified path) and already reports the measured
   character/word distributions and the over-cap counts at 2,048 tokens.
7. **`CHK-8e69547e0900a8dd`'s "refusal" framing is RESOLVED, not open.**
   Confirmed 2026-08-18 by a direct read-only Batch API re-query:
   `stop_reason=refusal`, `stop_details.category=bio`, 293 output tokens
   emitted — a genuine mid-stream safety refusal, not a truncation or parse
   failure. The stored columns *look* like a truncation (unterminated JSON,
   no `stop_reason` in that schema), which is why an earlier reading called
   it one. See `SPLIT_DESIGN.md` §1 (headed "Resolved"),
   `data/full_run_report.md`'s FINAL section, and `LIMITATIONS.md` §2.7.
8. **The base-model license question is CLOSED.**
   `Qwen/Qwen2.5-7B-Instruct` was verified live on 2026-08-18 — model-card
   tag `apache-2.0`, API metadata, `gated: false`, and the repository's own
   unmodified 11.3 kB Apache-2.0 `LICENSE` file. The verification table is
   in `MODEL_CHOICE.md`. What remains open there is not a license question:
   whether to move to a newer Qwen point release is the owner's call at the
   Phase D GO gate.

## Output-format / handoff stability (for `quant-modeler`)

- Label schema: `sentiment` (3-class), `guidance_direction` (5-class),
  `red_flags` (multi-label, 6 categories + modality) — see
  `PROMPT_TEMPLATE.md` for the exact conditional-applicability matrix and
  JSON key order. `distress_tier` is NOT part of the model's output schema.
- Model output is expected as a single JSON object per passage, fields
  conditional on content (never told section_type as text — see
  `PROMPT_TEMPLATE.md`), matching the same field set the model was trained
  to emit.
- `eval.py`'s parsing logic (`parse_model_output`) is the reference
  implementation for turning raw model text back into structured fields,
  including the explicit `UNPARSEABLE` failure mode — reuse it rather than
  re-deriving parsing logic downstream.
