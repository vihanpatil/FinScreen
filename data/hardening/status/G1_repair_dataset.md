# G1 repair — v1.2 training data BUILT, retrain READY TO LAUNCH

**Written 2026-08-26 by the finetune-engineer. Zero API calls, $0 spent.**
**No training was launched.** The only compute run here was ~23 s of CPU
tokenization for the MLX conversion (plus a 10-row smoke of the same).

Authorization: `HANDOFF.md` §3, 2026-08-26 (F2.5 closure ruling 1 — repair the
instrument). Run directory: `finetune/runs/2026-08-26-v12-epoch1/`.

**Amended 2026-08-26 (later, same day)** on the coordinator's follow-up: the
`eval.py` path blocker this report found is now **fixed**, and
`RUN_COMMANDS.md` carries the whole campaign — train epoch 1, eval, train
epoch 2, final eval — as copy-paste commands. See §6a and §6b.

> **State note.** This task began under the one-row train gap
> (`CHK-1c1812ed45219a3a`, 5,735/5,736). Mid-task the owner funded the
> 1-request completion batch (`msgbatch_01RvQpZofwP2yrHNnuJVmFZu`, $0.0014) and
> the gap closed. **Everything below was rebuilt from scratch against the
> completed `data/labels_v12.parquet` (6,747/6,747).** The gap-handling code
> path stayed — it is the guard, not a workaround, and it is still exercised by
> synthetic tests.

---

## 0. Headline

| Item | Value |
|---|---|
| **Split counts** | **train 5,736 / eval 1,010** — the frozen split **exactly**, delta 0 / 0 |
| Label gaps | **NONE.** All 6,746 frozen manifest rows carry a usable v1.2 label |
| `split.py` | **NOT run.** Membership joined from the frozen `finetune/splits/manifest.parquet` |
| Refusal chunk | `CHK-8e69547e0900a8dd` labeled successfully under v1.2 — **still excluded from both splits** (frozen manifest) |
| Prompt-rendering contract | **6,732/6,732** unaffected shared rows have a **token-identical** inference prompt vs E1; 14 differ by head-truncation length only (§3) |
| Training instruction | `ebc45a85…`, 1,825 chars, **byte-identical across all rows** and **unchanged from E1 epoch-1/epoch-2** |
| Config diff vs E1 epoch-1 | **3 lines**: `data`, `save_every`, `adapter_path` |
| Label shift | red_flags **27.48%** of rows changed (exact-set) / **5.86%** per-category; sentiment 4.59%; guidance 1.19% |
| Projected wall-clock | **~9.2 h per epoch** (band 9.0–9.9 h), measured. Two epochs = two overnights. |
| Tests | **154 passed, 5 skipped** across 9 targeted suites (63 of them new); + 36/36 under the mlx venv incl. the tokenizer group |
| Eval blocker | **FIXED** — `eval.py` gained `--mlx-data-dir` / `--prepared-dir` / `--splits-eval-parquet`; E1 defaults byte-compatible, fail-safe preserved (§6a) |
| Campaign | fully copy-paste in `RUN_COMMANDS.md` §6: train e1 → eval e1 → **owner gate** → train e2 → eval e2 → **G1**. ≈20.2 h machine time, $0 |

---

## 1. The split build (task 1)

New: `finetune/build_splits_v12.py` (+ `finetune/test_build_splits_v12.py`,
19 offline tests). It **joins** `data/labels_v12.parquet` onto the frozen
`finetune/splits/manifest.parquet` and never re-derives membership.
`split.py` was not invoked, and its `LABELS_PATH` (E1's frozen labels) was not
read.

Hard stops it enforces before writing anything:

| Guard | Result |
|---|---|
| the manifest on disk really is the frozen split (5,736 / 1,010) | PASS |
| no duplicate `chunk_id`s in the manifest | PASS |
| `CHK-8e69547e0900a8dd` is absent from the manifest | PASS |
| every manifest `chunk_id` has a v1.2 row | PASS (6,746/6,746) |
| `section_type` agrees between manifest and v1.2 labels | PASS (6,746/6,746) |
| passage text byte-identical to `data/labels.parquet` | PASS (all 6,747) |
| E1's drop predicate `parse_ok & schema_valid` re-applied | **0 rows dropped** |

The refusal-chunk exclusion is maintained deliberately and loudly: the script
prints "labels under v1.2: True" next to "KEPT OUT of both splits anyway", and
it **hard-fails** if that chunk_id ever appears in the manifest. Any dropped
row would be printed inside a `!!!!!` banner and **kept in the output manifest**
with `v12_labeled = False` rather than deleted — so
`finetune/splits_v12/manifest.parquet` always carries all 6,746 frozen rows.

Verified membership identity: joining the frozen manifest against
`splits_v12/manifest.parquet` on `chunk_id` gives 6,746 rows with
`split_frozen == split_v12` everywhere. Field presence in the prepared JSONL is
now **identical to E1's, exactly**:

| | train sentiment | train guidance | train red_flags | eval sentiment | eval guidance | eval red_flags |
|---|---|---|---|---|---|---|
| E1 | 4,265 | 601 | 5,736 | 875 | 578 | 1,010 |
| v1.2 | 4,265 | 601 | 5,736 | 875 | 578 | 1,010 |

E1's artifacts are provably untouched — `finetune/prepared/train.jsonl` and
`finetune/mlx_data/{train,valid}.jsonl` still hash to the values recorded in
the 2026-08-21 epoch-1 manifest (`59a4221f…`, `d4dc4ec8…`, `deb63b76…`).

Outputs: `finetune/splits_v12/{train,eval,manifest}.parquet` +
`build_report.json`.

---

## 2. prepare_dataset + convert_to_mlx (task 2)

Modules were **extended**, not forked; every default is unchanged and pinned:

- `prepare_dataset.py` — added `--splits-dir` / `--out-dir`. `INSTRUCTION` is
  deliberately **not** parameterised; see §4.
- `convert_to_mlx.py` — added `--prepared-dir` and `--limit` (smoke only). The
  conversion report now records the instruction's sha256/char count and stamps
  `SMOKE_RUN` when limited.
- `train_qlora.py` — added `--expect-train` / `--expect-eval` (the 5,736
  contract was hardcoded), `--lr-peak` / `--lr-decay-steps` / `--lr-warmup`
  (so continuation segments no longer temp-edit the shared `config_mlx.yaml`,
  as `runs/2026-08-21-epoch1-final-from-2250/RESUME_RECIPE.md` step 5 required),
  and `--authorization` (so this campaign's manifest records *its* ratification
  rather than the stale 2026-08-20 quote).

MLX conversion (`finetune/mlx_data_v12/`, 23 s wall clock, tokenizer only — no
model weights loaded, no GPU):

| | rows | head-truncated | mean rendered tok | loss-bearing tok |
|---|---|---|---|---|
| train | 5,736 | 2 | 999.7 | 214,334 (mean 37.4) |
| valid | 1,010 | 50 | 1,148.3 | 43,270 (mean 42.8) |

Every record was re-tokenized and asserted (a) ≤ 2,048 tokens, (b) non-empty
loss mask, (c) **the target JSON survives intact inside the loss-bearing
region** — the tail-truncation trap is never reached. Leakage check: 0
chunk_ids shared between train and valid.

**Smoke test** (task requirement): a 10-row-per-split conversion into the
scratch dir ran first and passed all the same assertions, with the report
stamped `SMOKE_RUN`.

---

## 3. Prompt-rendering exactness — verified, with one honest caveat

Contract per record, unchanged: `system` = the training instruction
(byte-identical always), `user` = the raw passage and nothing else,
`assistant` = the target JSON. No ticker, CIK, filing date, `section_type`
string, or outcome framing anywhere. Look-ahead-safe by construction.

Measured against E1's `mlx_data/` over all 6,746 rows, with the real Qwen2.5
tokenizer:

| check | result |
|---|---|
| rows only in E1 / only in v1.2 | **0 / 0** |
| split side (train/valid) differs | **0** |
| `system` turn differs | **0** |
| `user` (passage) turn differs | **14** |
| `assistant` JSON differs | 2,034 — **the single axis that is supposed to move** |
| inference prompt token-identical (`apply_chat_template(messages[:2], add_generation_prompt=True)`) | **6,732 / 6,732** of the rows not affected below |

**The caveat, stated plainly.** `convert_to_mlx.py` head-truncates a passage
until the rendered sequence **including the answer** fits 2,048. A longer
v1.2 answer therefore keeps slightly less passage. All 14 differing rows are
among the 52 head-truncated rows (E1 truncated 51; v1.2's set is a strict
superset), they split **2 train / 12 eval**, and all 14 are a **strict
head-prefix relation** — only the passage *tail* moved, by −505 to +33
characters.

So the v1.2 retrain is single-axis on 99.79% of rows and *nearly* single-axis
on 0.21%. On the eval side that is **12 / 1,010 = 1.19%** of prompts that are
not literally the prompts epoch-2 saw. It is small, it is not zero, and it
belongs in the G1 read rather than in a footnote.

---

## 4. The training instruction is NOT the labeling system prompt

The brief asked to verify that "the v1.2 SYSTEM instruction (sha
`30605197ca56c231…`) is the training instruction". **It is not, it never was,
and it should not be made so.** Two distinct artifacts:

| | training instruction | labeling system prompt |
|---|---|---|
| where | `finetune/prepare_dataset.py::INSTRUCTION` | `build_batch_requests.py::SYSTEM_PROMPT` |
| sha256 | `ebc45a856bff58a5…` | `30605197ca56c231…` |
| size | 1,825 chars / **412 tokens** | 9,521 chars / **1,904 tokens** |
| role | the `system` turn of every training and inference prompt | what the **teacher** was told when it produced `labels_v12.parquet` |

They are related by the 2026-08-10 sync rule as a *leaner hand-synced
restatement*, never a verbatim embed (`PROMPT_TEMPLATE.md`; HANDOFF §3). The
epoch-1 and epoch-2 runs and their evals all used `ebc45a85…`; the epoch-2
eval manifest records exactly that sha
(`data.instruction_sha256 = ebc45a856bff58a5…`).

**Substituting the labeling prompt is infeasible, measured:** rendered with an
empty passage and a minimal answer it already reaches **1,934 of 2,048
tokens**, leaving ~114 tokens for the passage against a measured mean of ~660.
`convert_to_mlx.py` would head-truncate essentially the entire corpus to a
stub. And it would move a second axis, destroying the single-axis
v1.1-student vs v1.2-student comparison the retrain exists to produce.

**Decision taken: the training instruction stays frozen at `ebc45a85…`,
byte-identical across all rows (asserted in code, recorded in the conversion
report and the dataset manifest).** Both shas are recorded side by side in
`dataset_manifest.json`, so the provenance chain reads
`rubric v1.2 → labeling prompt 30605197 → labels_v12 → targets → training
instruction ebc45a85 → student`. If the owner wants the v1.2 *rules* inside
the student's instruction too, that is a separate, deliberate, two-axis change
needing its own ruling.

---

## 5. Label shift v1.1 → v1.2 (task 3)

Full report: `data/hardening/LABEL_SHIFT_v11_v12.md` +
`label_shift_v11_v12.json`; generator `label_shift_v11_v12.py`; 14 offline
tests in `test_label_shift_v11_v12.py`.

Comparable population **6,746** (labeled on both sides). One asymmetric row:
`CHK-8e69547e0900a8dd`, labeled under v1.2 but not v1.1 — and in neither split.

**This is teacher-vs-teacher agreement between two rubric revisions. It is not
an accuracy measurement and neither side is ground truth.** Same corpus, same
model id (`claude-sonnet-5`), same decoding config.

| field | basis | denominator | changed | % |
|---|---|---|---|---|
| sentiment | single value | 5,140 | 236 | **4.59%** |
| guidance_direction | single value | 1,179 | 14 | **1.19%** |
| **red_flags** | **EXACT SET** | 6,746 | 1,854 | **27.48%** |
| **red_flags** | **PER-CATEGORY** | 40,476 | 2,372 | **5.86%** |

The rubric edit did what it was scoped to do: **red_flags moved ~6× more than
sentiment and ~23× more than guidance** on comparable bases, and the two
fields whose §-definitions were pinned byte-identical barely moved.

Decomposition of the 1,854 changed rows: adds only 658, drops only 472,
modality only 410, mixed 314. Rows carrying ≥1 flag 4,416 → 4,513 (+97); total
flags 7,715 → 7,933 (+218).

### Per-category — the two intended effects are visible

| category | v1.1 | v1.2 | Δ | added | dropped | HYP→REAL | REAL→HYP |
|---|---|---|---|---|---|---|---|
| DEMAND_WEAKNESS | 1,318 | 1,313 | −5 | 163 | 168 | 27 | 14 |
| SUPPLY_INPUT_CONSTRAINT | 607 | 567 | **−40** | 46 | 86 | 22 | 4 |
| TRADE_POLICY_EXPOSURE | 699 | 702 | +3 | 64 | 61 | 29 | 7 |
| IMPAIRMENT_WRITEDOWN | 1,015 | 1,028 | +13 | 97 | 84 | 8 | 3 |
| **MARGIN_COST_PRESSURE** | 1,736 | **2,030** | **+294 (+16.9%)** | 479 | 185 | 53 | 24 |
| **LEGAL_REGULATORY_ACTION** | 2,257 | 2,215 | −42 | 170 | 212 | **300** | 10 |

- **P1 (realized-controls)** — `LEGAL_REGULATORY_ACTION` modality inverted:
  HYPOTHETICAL 1,258 → 884 (−374), REALIZED 1,047 → 1,366 (+319), with **300**
  chunks flipping HYP→REAL against 10 the other way. This is the largest single
  effect in the whole re-label and it is exactly the error mode the spot-check
  identified (43 wrong-modality corrections, 26 of them LEGAL). Every category
  moved REALIZED-ward; the shared §6 vocabulary reached all six.
- **P3-corollary (`MARGIN_COST_PRESSURE` "always and only")** — +294 rows
  (479 added, 185 dropped): the largest category-presence move, on the error
  mode `RED_FLAGS_LIMITATION.md` called the single largest in the record.
- **P3 (mining depth) did NOT produce the net pruning its rationale implied.**
  Say this plainly at G1. The only category that lost material presence is
  `SUPPLY_INPUT_CONSTRAINT` (−40, HYPOTHETICAL −55). By section, `RISK_FACTORS`
  is where the exact-set churn concentrates (**41.59%** vs 22.19% MD&A /
  26.05% EX-99) while its total flag count is **flat** (2,755 → 2,753) and its
  ≥1-flag rows are flat too (1,485 → 1,488). Inside risk-factor enumerations
  v1.2 **re-allocated** flags rather than removing them.

### Train and eval moved together

| split | n | exact-set changed | % | total flags Δ | sentiment % changed |
|---|---|---|---|---|---|
| train | 5,736 | 1,571 | 27.39% | +178 | 4.22% |
| eval | 1,010 | 283 | 28.02% | +40 | 6.40% |

No divergence — the retrain and its held-out eval are measuring the same
rubric. (Pinned by a test.)

### sentiment / guidance — small and roughly symmetric

sentiment 236/5,140: NEUTRAL→NEGATIVE 74, NEUTRAL→POSITIVE 68,
POSITIVE→NEUTRAL 47, NEGATIVE→NEUTRAL 44, and 3 sign reversals. Net
distribution 3,436/1,024/680 → 3,385/1,046/709 — a mild move *out of* NEUTRAL
in both directions, not a systematic tilt.

guidance 14/1,179, dominated by MAINTAINED↔NONE (5 out, 3 in). The corpus's
single `WITHDRAWN` label survives, so it remains a train-only class with zero
eval support — still **not evaluable**, exactly as under v1.1.

### distress_tier — the 162 → 129 question, decomposed

`distress_tier` is **never a training target and never a headline metric**
(HANDOFF §7). It is reported here only because rubric v1.2's §6 modality
vocabulary is shared and therefore reaches it.

Over the comparable 6,746: **162 → 129 (−33)**.

| tier / modality | v1.1 | v1.2 | Δ |
|---|---|---|---|
| LIQUIDITY_STRESS / HYPOTHETICAL | 151 | 112 | **−39** |
| LIQUIDITY_STRESS / REALIZED | 9 | **15** | **+6** |
| ACCOUNTING_RESTATEMENT / HYPOTHETICAL | 2 | 2 | 0 |

Row transitions: positive in both 108 (5 of them changed within), dropped 54,
newly added 21, negative in both 6,563. **The net −33 is not a clean pruning —
it is 54 out and 21 in.** The modality mix moved the way P1 predicts (REALIZED
up, HYPOTHETICAL down), which is notable because principle **P2 (affirmed
adequacy defeats the liquidity flag) was deliberately NOT encoded** in v1.2
(`G1_repair_prep.md` §1). The REALIZED class the owner emptied at the
spot-check has been repopulated to 15 by a rubric change that never addressed
it — that is a fact for the G1 read, not a result.

**Correction to `HARDENING_PROGRESS.md`.** Its post-batch summary quotes
"≥1-red-flag rows 4,515" and "distress-tier matches 130". Recomputed the
figures are **4,514** and **129**. Both were one too high because they were
taken while `CHK-1c1812ed45219a3a` was unanswered and carried **NULL, not
empty**, `red_flags`/`distress_tier`, and a null-inclusive predicate counted it
as a positive. The completion batch has since labeled that row with an *empty*
set for both fields, so the corrected figures hold either way. `HARDENING_PROGRESS.md`
has been amended in place with a dated note.

---

## 6. Run directory, configs and commands (task 4)

`finetune/runs/2026-08-26-v12-epoch1/`:

| file | role |
|---|---|
| `RUN_COMMANDS.md` | the exact main-session epoch-1 command, pre-flight, eval, and the planned epoch-2 continuation |
| `RESUME_RECIPE.md` | the segmented auto-resume chain (HANDOFF §4) |
| `authorization.json` | the 2026-08-26 ratification this run executes under; hashed into the launcher's manifest |
| `dataset_manifest.json` | sha256 of every upstream artifact (§7) |
| `build_dataset_manifest.py` | regenerates it; read-only, re-runnable |
| `plan-epoch1/`, `plan-epoch2/` | the pre-generated resolved `mlx_lora_config.yaml` + planned manifest for each launch |

**Recipe — identical to the 2026-08-21 epoch-1**: base
`Qwen2.5-7B-Instruct-4bit c26a38f6…`, LoRA r16 / scale 2.0 / dropout 0.05 /
**q+v only** / top-16 of 28 layers, batch 1 × 4 grad-accum, seq 2,048,
`mask_prompt: true`, `grad_checkpoint: true`, seed 42, `iters 5736` = 1,434
optimizer updates, cosine `[2.0e-4, 1391]` with `warmup 43`. The **only**
deliberate change is `save_every: 250 → 100` (≈ **9.6 min** of work, measured
— the brief's ~10 min). Proof:

```
$ diff runs/2026-08-20-epoch1/mlx_lora_config.yaml \
       runs/2026-08-26-v12-epoch1/plan-epoch1/mlx_lora_config.yaml
8c8   data:         .../mlx_data      ->  .../mlx_data_v12
34c34 save_every:   250               ->  100
36c36 adapter_path: ...-epoch1        ->  ...-v12-epoch1
```

### THE EPOCH-1 COMMAND

```bash
FS=/Users/vihanpatil/personal/projects/FinScreen
R=$FS/finetune/runs/2026-08-26-v12-epoch1
M=/Users/vihanpatil/.cache/huggingface/hub/models--mlx-community--Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed

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

No `--lr-*` flags: at 5,736 iters `config_mlx.yaml`'s fresh cosine is already
the correct epoch-1 schedule. Main session, background task, resume on every
kill notification per `RESUME_RECIPE.md`. Adapter →
`finetune/checkpoints/qwen2.5-7b-finscreen-lora-mlx-v12-epoch1/`. Expected
resolved-config sha256
`9e35f2fb7ca9f245af72a149e839a3cc92ca84ec9a1566fd356a9ceeb888155f`.

### Projected wall-clock — measured, not guessed

From the 2026-08-21 epoch-2 run's own 56 consecutive 100-iter checkpoint gaps
on this machine, this recipe, this seq length: median **5.702** s/iter, mean
**5.748**, p90 **6.040**. Cross-checked against the trainer's own `It/sec`
(0.177 mean over epoch 2, 0.174 over the epoch-1 remainder) and against epoch
2's end-to-end 21:32 → 06:32 = **9.17 h**. Periodic validation is already
inside those gaps.

| | 5,736 iters |
|---|---|
| median | **9.09 h** |
| mean | **9.16 h** |
| p90 | **9.62 h** |

**Point estimate ≈ 9.2 h; quote the band 9.0–9.9 h.** Plus ~1–2 min of model
load per resume segment. One overnight per epoch; two epochs ≈ 18.3 h.

### Planned epoch 2

Same modelling choice the owner ratified on 2026-08-21: fresh cosine at
**half** peak LR resuming the epoch-1 final adapter —
`--lr-peak 1.0e-4 --lr-decay-steps 1414 --lr-warmup 20`,
`--resume-adapter-file …-v12-epoch1/adapters.safetensors`, tag `v12-epoch2`.
Full command in `RUN_COMMANDS.md` §4; resolved config pre-generated at
`plan-epoch2/mlx_lora_config.yaml` (sha `2efa4ea4d39101e8…`). It differs from
E1's epoch-2 config in four lines: `data`, `adapter_path`,
`resume_adapter_file`, and the top-level `learning_rate` (0.0002 → 0.0001).
**That last one is cosmetic** — `mlx_lm/lora.py:275` is
`lr = build_schedule(args.lr_schedule) if args.lr_schedule else args.learning_rate`,
so with a schedule present the top-level value is never read; E1's file said
0.0002 while actually training at a 1.0e-4 peak, and `--lr-peak` now sets both
so the file no longer contradicts itself.

**It is planned, not pre-authorized to run unattended.** Run the epoch-1 eval
first; whether a second epoch is needed is the owner's call at G1.

---

## 6a. The `eval.py` blocker — FIXED (2026-08-26, later)

`run_real_eval` used to call `load_eval_rows()` with no path arguments, so it
always read E1's `finetune/mlx_data/valid.jsonl` and
`finetune/prepared/eval.jsonl` (module constants at `eval.py:77-79`), and the
train-instruction cross-check hardcoded `MLX_DATA_DIR / "train.jsonl"`. It
failed *safe* — the training manifest's sha check raised `SystemExit` before
any generation — but the v1.2 re-eval could not run at all.

**What changed (four small edits, no behaviour change on the E1 path):**

| edit | detail |
|---|---|
| `load_eval_rows(..., mlx_train=None)` | new optional param; `None` resolves to `train.jsonl` **beside the `valid.jsonl` being evaluated**, which for E1's defaults is byte-identically the old `MLX_DATA_DIR / "train.jsonl"` |
| `run_real_eval` | resolves `--mlx-data-dir` / `--prepared-dir` (both defaulting to `None` → the E1 constants) and passes `mlx_valid` / `prepared_eval` / `mlx_train` explicitly; records both dirs in `manifest.json`'s `data` block |
| the fail-safe message | now names the file actually loaded **and** the dataset the training manifest expects, so a wrong `--mlx-data-dir` is diagnosable instead of just fatal. It still raises `SystemExit` at the same point, before any model load |
| `write_section_types(out_path, source=...)` | new `--splits-eval-parquet` flag so the sidecar can be rebuilt from `splits_v12/eval.parquet`; default unchanged |

**Byte-compatibility is pinned, not asserted.**
`test_omitting_the_new_flags_resolves_to_the_exact_e1_paths` monkeypatches
`load_eval_rows` and checks that a command line mentioning none of the new
flags hands it exactly `mlx_data/valid.jsonl`, `prepared/eval.jsonl`,
`mlx_data/train.jsonl`.

**The fail-safe is pinned three ways:** a wrong `--mlx-data-dir` `SystemExit`s
with a message naming both datasets; **no `predictions.jsonl` or `metrics.json`
is written**; and a positive control proves the guard is not simply
always-failing (with the *right* dir the run passes the sha check and only then
dies on a fake model path).

**Verified against the real artifacts, offline:** loading
`mlx_data_v12/valid.jsonl` + `prepared_v12/eval.jsonl` yields 1,010 rows,
50 head-truncated, instruction `ebc45a85…` byte-identical **to the v1.2 train
split** (not E1's), the sidecar covers every row, the sha matches
`plan-epoch1/manifest.json`, and it differs from the E1 epoch-2 manifest's —
i.e. a mix-up in either direction would fire the guard.

**The section-type sidecar does NOT need regenerating** — verified twice:
`finetune/eval_section_types.json` covers all 1,010 v1.2 eval chunk_ids with
identical values, and regenerating from `splits_v12/eval.parquet` reproduces
the shipped mapping exactly (`test_write_section_types_from_the_v12_split_reproduces_the_e1_sidecar`).

### The eval command

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

No adapter placeholder is needed — `--train-manifest` supplies the adapter
path. **If epoch 1 was segmented by kills, point it at the LAST segment's
`manifest.json`**, since that is the run whose `adapter_path` holds the final
`adapters.safetensors`. The epoch-2 eval is the same command with `$R2` and its
own out-dir. Measured throughput 1,068 chunks/h → ≈57 min.

---

## 6b. The campaign is now copy-paste end to end

`RUN_COMMANDS.md` §6:

```
 0.  setup      export FS / R / R2 / M, then §1 pre-flight               ~1 min
 1.  TRAIN e1   §2   main-session background task, resume per recipe     ~9.2 h
 2.  EVAL  e1   §3   foreground, resumable                               ~57 min
 3.  ** OWNER GATE ** read the epoch-1 report — is a second epoch wanted?
 4.  TRAIN e2   §4   main-session background task                        ~9.2 h
 5.  EVAL  e2   §5   foreground, resumable                               ~57 min
 6.  ** OWNER GATE — G1 ** rule on the repaired instrument
```

≈**20.2 h** machine time, **$0**, zero API calls at every step. Each run dir's
`manifest.json` is self-describing, so a fresh session resumes from disk alone.
The G1 read should put `runs/2026-08-21-eval-epoch1/eval_report.md` and
`runs/2026-08-22-eval-epoch2/eval_report.md` beside the new reports: same epoch
count, same frozen 1,010 rows, same instruction, different rubric.

---

## 7. Provenance — sha256 of everything

| artifact | sha256 |
|---|---|
| `data/labels_v12.parquet` (6,747/6,747) | `ca373b953504535b2f35ee374a6b6c1a6360000261748db365ee23c231e475e7` |
| `data/labels.parquet` (v1.1, frozen, read-only) | `c3531f03cda602bc2ed7fb7743d5d01f78ed722f2a58bd82922f5b8ccc3daa72` |
| `finetune/splits/manifest.parquet` (**FROZEN**, the membership source) | `dff0a2d0b647cc7c7f5da2d8a9ffe5b1069302190263eb449bb48a72c56816f7` |
| `finetune/splits_v12/train.parquet` (5,736) | `5e56076e3948cf9598b6cf61ad7307961735c19af2a0932f981ea6ee3dd4cb10` |
| `finetune/splits_v12/eval.parquet` (1,010) | `0b98531b35cade544e8b80676bb8005d1570e0f9f5bcd1338b9e05a3d2df9f55` |
| `finetune/splits_v12/manifest.parquet` (6,746) | `b76923b14507bbb1bc76e774e64e39d60fe3967c1bf0bb735edbf0072a2dafd8` |
| `finetune/prepared_v12/train.jsonl` | `91d95653c1fb1a304610bfb948564ef8fc5f4c4d5d8c20a0037bec33e5bae580` |
| `finetune/prepared_v12/eval.jsonl` | `0229d0ba90d8331d0e6b6ead5d72dc1f1ccc5c085998ad5695f7f8e4e35d2ac5` |
| `finetune/mlx_data_v12/train.jsonl` | `396aef131bec0e5cffc22df94fe310e07a8e440d9d5a020b09772699a2931a43` |
| `finetune/mlx_data_v12/valid.jsonl` | `b74efdb326e9b862820453eecfa64307f460499cac0fd92562fdf91eb0b1126b` |
| TRAINING instruction (`prepare_dataset.py::INSTRUCTION`) | `ebc45a856bff58a562535867e5a1f4173519fe77c58a47b16bfa28e6eea8efe2` |
| LABELING system prompt v1.2 (`build_batch_requests.py::SYSTEM_PROMPT`) | `30605197ca56c23138de34743d780c19fd62e31c80b1eb5b58115fbde8ae5924` |
| `labeling_rubric.md` (v1.2) | `46dea3c886846849c82ae2b65d8e29ef95016dece706cd19a2e00b8d99c30b25` |
| base weights `model.safetensors` | `86110f368236b53cf4c2336f991a85703b17bcc60bb75f292b4002ec0219f071` |
| `finetune/build_splits_v12.py` | `31e245168b51b9961dfe078c1d40b827104c348fba5346c9f1f646e82d17e8db` |
| `finetune/prepare_dataset.py` | `bea4ad659cabe8f57a9f5a99a58864860f2d16bb98e7b2da55c20fe41bcc33a0` |
| `finetune/convert_to_mlx.py` | `b81ea81345b4e7f84e6767ce5786464bf1d6739c4823103199263a16152baf54` |
| resolved epoch-1 config (`plan-epoch1/mlx_lora_config.yaml`) | `9e35f2fb7ca9f245af72a149e839a3cc92ca84ec9a1566fd356a9ceeb888155f` |
| resolved epoch-2 config (`plan-epoch2/mlx_lora_config.yaml`) | `2efa4ea4d39101e8273515e90f1e95e632958f248b4a4e08a445a9b5f4d37b17` |

Reference v1.1 student adapters (for the G1 comparison; **not** resumed from —
the v1.2 epoch-1 starts from the base model exactly as the 2026-08-20 epoch-1
did): epoch-1 final `3c6adc9eedaec2ad…`, epoch-2 final `9c08e3cb3f1f917c…`.

Machine-checkable proof E1 is untouched — these still equal the values in the
2026-08-21 epoch-1 manifest: `prepared/train.jsonl` `59a4221fe2db60f8…`,
`mlx_data/train.jsonl` `d4dc4ec8323b19ae…`, `mlx_data/valid.jsonl`
`deb63b76992404ec…`.

Every sha above (plus the corpus, the pre-completion backup, the completion
audit parquet, and the reference adapters) is in
`finetune/runs/2026-08-26-v12-epoch1/dataset_manifest.json`, regenerable with
`build_dataset_manifest.py`.

---

## 8. Tests — 154 passed, 5 skipped, all offline

| suite | n |
|---|---|
| `finetune/test_build_splits_v12.py` (**new**) | 19 |
| `finetune/test_eval_dataset_paths.py` (**new**) | 18 |
| `finetune/test_train_qlora_v12_flags.py` (**new**) | 12 |
| `data/hardening/test_label_shift_v11_v12.py` (**new**) | 14 |
| `finetune/test_prepare_dataset.py` | 6 |
| `finetune/test_leakage.py` | 1 |
| `finetune/test_eval_real.py` | 31 (+5 skipped under system python) |
| `test_rubric_v12_sync.py` + `test_submit_variant_wiring.py` | 54 |

Additionally `finetune/.mlx_venv/bin/python finetune/test_eval_real.py` →
**36 passed, 0 failed, 0 skipped**, which exercises the tokenizer-dependent
rendering-contract group the system-python run skips. That is the check that
the `eval.py` edits did not disturb the prompt contract.

No network, no `anthropic` import, no model load, no GPU in any of them. The
new suites cover the join, the gap path (still exercised synthetically even
though the real build now has zero gaps), the refusal-chunk exclusion in both
directions, corpus-text drift, the row-count guards, the LR-flag overrides
including `warmup 0`, the authorization block, and the dual-modality
red-flag comparison bug described below.

**One real bug found and fixed during this work.** The first label-shift
implementation compared a category's modality as a *scalar* (`the first match`),
which silently reported "unchanged" for chunks carrying the same category at
**both** modalities on one side and one modality on the other. It
mis-classified 40 changed rows. Fixed by comparing modality **sets**
(`modalities_of`), which moved the per-category changed count 2,313 → 2,372
and the "modality only" bucket 370 → 410. Pinned by
`test_dual_modality_row_is_detected_as_changed_not_silently_equal`.

---

## 9. Files touched

**New:** `finetune/build_splits_v12.py`, `finetune/test_build_splits_v12.py`,
`finetune/test_train_qlora_v12_flags.py`,
`finetune/test_eval_dataset_paths.py`,
`data/hardening/label_shift_v11_v12.py`,
`data/hardening/test_label_shift_v11_v12.py`, and the run directory
`finetune/runs/2026-08-26-v12-epoch1/` (6 files + 2 plan dirs).

**Extended (defaults unchanged, E1 behaviour preserved and test-pinned):**
`finetune/prepare_dataset.py`, `finetune/convert_to_mlx.py`,
`finetune/train_qlora.py`, `finetune/eval.py` (§6a), `.gitignore`,
`HARDENING_PROGRESS.md` (the dated 4,514 / 129 correction).

**Generated:** `finetune/splits_v12/`, `finetune/prepared_v12/`,
`finetune/mlx_data_v12/`, `data/hardening/LABEL_SHIFT_v11_v12.md` + `.json`.

**Not touched:** `data/labels.parquet`, `data/labels_v12.parquet`,
`finetune/split.py`, `finetune/splits/`, `finetune/prepared/`,
`finetune/mlx_data/`, `finetune/eval_section_types.json`,
`finetune/config_mlx.yaml`, every E1 checkpoint and run directory.

---

## 10. Open items

1. ~~`eval.py` path flags~~ — **CLOSED 2026-08-26** (§6a). The campaign is
   copy-paste end to end; the resume session only runs commands.
2. **The 14 head-truncation-differing rows** (§3) — 12 on the eval side. Not a
   defect, but a real 1.19% departure from single-axis on the eval prompts;
   belongs in the G1 write-up.
3. **The training-instruction question** (§4) — frozen by decision here. If
   the owner wants v1.2's rules inside the student's instruction, that is a
   separate two-axis change with its own ruling.
4. **Epoch 2 is planned, not authorized to auto-follow** (§6).
5. **P2 and the repopulated REALIZED distress class** (§5) — 9 → 15 REALIZED
   LIQUIDITY_STRESS labels under a rubric revision that deliberately did not
   encode P2, on a field the owner emptied at the spot-check. `distress_tier`
   is not a training target so nothing downstream consumes it, but it is the
   open ruling `labeling_rubric.md` §9 already flags.
6. **What this cannot fix.** A repaired teacher does not guarantee a repaired
   student. Whether the v1.2 retrain lifts H3's measured red-flag family
   retention (0.669 [0.586, 0.742], kill-criterion 2 breached) is unknown until
   the re-eval. Nothing in this report is evidence that it will — and note that
   `red_flags` moved on only **5.86%** of per-category decisions, which is a
   modest perturbation to ask a retrain to convert into a repaired instrument.
