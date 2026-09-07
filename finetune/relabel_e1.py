#!/usr/bin/env python3
"""
relabel_e1.py — have an epoch-2 student re-label ALL 6,746 labeled E1 chunks,
segmented and per-row resumable, for hardening items H3 / H3v2 (labeler
attenuation).

TWO CAMPAIGNS, ONE RUNNER
-------------------------
H3   (2026-08-25, DONE): the rubric-**v1.1** student
     (`checkpoints/…-lora-mlx-epoch2`) over `finetune/mlx_data/`, scored against
     `data/labels.parquet`, written to `data/hardening/e1_relabel_*`.
     Those artifacts are a ruled record — this tool never overwrites them.
H3v2 (2026-08-27, owner-ratified, HANDOFF §3): the repaired rubric-**v1.2**
     student (`checkpoints/…-lora-mlx-v12-epoch2`) over
     `finetune/mlx_data_v12/`, scored against `data/labels_v12.parquet`,
     written to `data/hardening/h3v2/e1_relabel_*_v12`.
     One flag — `--v12` — flips every path together (data, teacher, adapter,
     training manifest, reference eval, out-dir, filename suffix, run id), so a
     v1.1 adapter can never be paired with v1.2 data by a mistyped path. Each
     value stays individually overridable, and all of them are re-recorded with
     sha256s in the run manifest.

The two runs are NOT comparable as accuracy: each is measured against its own
teacher, and rubric v1.2 moved red_flags on 27.48% of rows (exact-set). A
v1.1-vs-v1.2 read is instrument-vs-instrument — does the repaired student track
its own teacher better — never like-for-like (see CAVEATS).

WHAT THIS IS FOR
----------------
`HARDENING_PROGRESS.md` H3 / `data/reevaluation_2026-08-25/alternatives.md` §(b):
E2's MDE bracket was computed under CLAUDE's label quality, but E2's labels will
come from the student. Nobody has computed the net. This script produces the one
artifact that lets someone compute it: the same 6,746 E1 chunks, labeled by the
student instead of the teacher, in a drop-in-compatible schema, so features can
be re-derived and the E1 backtest re-run on student labels.

It measures a labeler swap. It is not a new labeling run of new text, it does not
touch `data/labels.parquet` (E1's frozen labels — opened READ-ONLY here), and it
costs $0: local MLX inference, zero Anthropic API calls (HANDOFF §5).

WHAT IT DOES NOT DO
-------------------
No comparison, no IC, no retention rho. That is quant-modeler's follow-up over
the parquet this writes. The only scoring here is a compact teacher-agreement
summary in the manifest, for sanity-checking the run — and agreement with the
teacher is NOT accuracy (see CAVEATS).

THE PROMPT
----------
Token-exact reproduction of `convert_to_mlx.py`'s `prompt_rendering_contract`,
by CONSTRUCTION rather than by restatement: rows are read from
`finetune/mlx_data/{train,valid}.jsonl` — the exact rendered records the trainer
consumed — and the prompt is `eval.py::render_prompt_token_ids`, which calls
`convert_to_mlx.to_messages()` + `convert_to_mlx.render()` and slices the
generation-prompt prefix. system=instruction / user=passage, nothing appended.

Why mlx_data and not `data/labeling_corpus.parquet` directly: 51 of the 6,746
passages were head-truncated to fit max_seq_length 2048 at conversion time.
Re-rendering from the corpus with a different truncation budget would put those
rows outside the length regime the student was trained in and would break
byte-identity with the epoch-2 eval. Instead the corpus provenance is VERIFIED,
not bypassed: the sidecar step re-reads `data/labeling_corpus.parquet` and
asserts every rendered passage is a head-prefix of the corpus text for that
chunk_id (0 violations at build time), and the mlx_data file hashes are checked
against the epoch-2 training manifest before a single token is generated.

TWO INTERPRETERS, ON PURPOSE
----------------------------
`finetune/.mlx_venv` has mlx/mlx-lm/transformers but NOT pandas/pyarrow; the
system python3 has pandas/pyarrow but no mlx. So, exactly like
`eval.py --write-section-types`:

  step 0  --write-sidecar   system python3   reads the parquets, writes
                                             data/hardening/e1_relabel_sidecar.json
                                             (canonical row order + the
                                             corpus<->mlx_data verification)
  step 1  (generate)        .mlx_venv/bin/python   GPU work; stdlib + mlx only;
                                             appends the .jsonl journal
  step 2  --finalize-only   system python3   journal -> parquet + agreement
                                             summary; loads no model

RESUME SEMANTICS (HANDOFF §4 — the auto-resume chain)
-----------------------------------------------------
Never launch this from a subagent shell. The main session runs step 1 as a
background task; assume it can be SIGTERMed at any time. Every row is appended
to the journal and fsync'd before the next row starts, so a kill loses at most
the in-flight row (~3 s). Re-run the IDENTICAL command to resume: rows already
in the journal are skipped, a torn final line is ignored, and every row stores
the sha256 of the exact prompt token sequence it came from — if the data or the
rendering ever changed under a resume, the run stops hard rather than mixing two
prompt versions into one artifact. Exit code 0 = all target rows generated;
2 = partial, re-run to resume.

CAVEATS THAT MUST TRAVEL WITH THE OUTPUT (also written into the manifest)
-------------------------------------------------------------------------
1. 5,736 of the 6,746 chunks (85.0%) are the student's own TRAINING rows. Their
   agreement with the teacher is inflated by memorization, so any retention /
   attenuation number computed over the pooled corpus is OPTIMISTIC. The `split`
   column exists so the comparison can be reported pooled AND eval-only (n=1,010,
   the only unbiased slice).
2. `distress_tier` was never a training target (HANDOFF §7): the student is never
   asked for it and the column is uniformly empty here. It exists for schema
   compatibility only and carries no information — do not compare it.
3. Every agreement figure is agreement with the TEACHER, not accuracy. The
   teacher's own red_flags carry ~36.6% set-level error (sample-pooled) / ~25%
   base-rate-representative / 7.5% per-category.
4. `guidance_direction`: the missing->NONE post-rule is PROPOSED, NOT ADOPTED.
   Raw student output is stored. (For the feature join it is a no-op: features.py
   maps both "NONE" and null to NaN.)
5. 8K_BODY (n=8, 2 tickers) and WITHDRAWN (n=1, train-split) are not evaluable
   and are excluded from the headline agreement tables, reported separately.

USAGE
-----
    # 0. sidecar (system python3, seconds, no GPU)
    python3 finetune/relabel_e1.py --write-sidecar            # H3   (v1.1)
    python3 finetune/relabel_e1.py --v12 --write-sidecar      # H3v2 (v1.2)

    # 1. generate (mlx venv; main session background task; resume by re-running)
    caffeinate -dims finetune/.mlx_venv/bin/python finetune/relabel_e1.py --v12

    # 2. finalize (system python3, seconds, no GPU)
    python3 finetune/relabel_e1.py --v12 --finalize-only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import eval as ev  # noqa: E402  (finetune/eval.py — scoring + provenance helpers)

# --- frozen inputs (all READ-ONLY) ------------------------------------------
CORPUS_PARQUET = REPO / "data" / "labeling_corpus.parquet"
LABELS_PARQUET = REPO / "data" / "labels.parquet"           # E1 v1.1, FROZEN. never written.
LABELS_PARQUET_V12 = REPO / "data" / "labels_v12.parquet"   # rubric v1.2, FROZEN. never written.
MLX_DATA_DIR = HERE / "mlx_data"                            # E1 / rubric v1.1
MLX_DATA_DIR_V12 = HERE / "mlx_data_v12"                    # rubric v1.2
MLX_TRAIN = MLX_DATA_DIR / "train.jsonl"
MLX_VALID = MLX_DATA_DIR / "valid.jsonl"
DEFAULT_TRAIN_MANIFEST = HERE / "runs" / "2026-08-21-epoch2" / "manifest.json"
DEFAULT_ADAPTER = HERE / "checkpoints" / "qwen2.5-7b-finscreen-lora-mlx-epoch2"
EPOCH2_EVAL_PREDICTIONS = HERE / "runs" / "2026-08-22-eval-epoch2" / "predictions.jsonl"

# --- outputs ----------------------------------------------------------------
DEFAULT_OUT_DIR = REPO / "data" / "hardening"
SIDECAR_NAME = "e1_relabel_sidecar.json"
JOURNAL_NAME = "e1_relabel_student.jsonl"
PARQUET_NAME = "e1_relabel_student.parquet"
MANIFEST_NAME = "e1_relabel_manifest.json"

TARGET_ROWS = 6746
RUN_ID = "H3-e1-relabel-epoch2"
RUN_ID_V12 = "H3v2-e1-relabel-v12-epoch2"


def artifact_name(base: str, suffix: str) -> str:
    """`e1_relabel_student.jsonl` + `_v12` -> `e1_relabel_student_v12.jsonl`.

    The suffix is how H3v2's outputs stay collision-free with H3's ruled
    artifacts even if someone points both runs at the same directory.
    """
    stem, dot, ext = base.partition(".")
    return f"{stem}{suffix}{dot}{ext}"


# Every path the two campaigns disagree about, in one place. `--v12` swaps the
# whole set; anything passed explicitly on the command line wins over both.
# E1_DEFAULTS is H3 exactly as it ran on 2026-08-25 — omitting every new flag
# reproduces that invocation byte for byte (pinned by a test).
E1_DEFAULTS = {
    "mlx_data_dir": MLX_DATA_DIR,
    "labels_parquet": LABELS_PARQUET,
    "adapter_path": DEFAULT_ADAPTER,
    "train_manifest": DEFAULT_TRAIN_MANIFEST,
    "reference_predictions": EPOCH2_EVAL_PREDICTIONS,
    "out_dir": DEFAULT_OUT_DIR,
    "name_suffix": "",
    "run_id": RUN_ID,
}

V12_PROFILE = {
    "mlx_data_dir": MLX_DATA_DIR_V12,
    "labels_parquet": LABELS_PARQUET_V12,
    "adapter_path": HERE / "checkpoints" / "qwen2.5-7b-finscreen-lora-mlx-v12-epoch2",
    "train_manifest": HERE / "runs" / "2026-08-27-v12-epoch2" / "manifest.json",
    "reference_predictions": HERE / "runs" / "2026-08-28-v12-eval-epoch2" / "predictions.jsonl",
    "out_dir": REPO / "data" / "hardening" / "h3v2",
    "name_suffix": "_v12",
    "run_id": RUN_ID_V12,
}

CAVEATS = [
    "85.0% of these rows (5,736/6,746) are the student's own TRAINING rows; their "
    "teacher-agreement is inflated by memorization. Report retention/attenuation "
    "pooled AND eval-only (split=='eval', n=1,010 — the only unbiased slice).",
    "distress_tier was never a training target (HANDOFF §7). The column is "
    "uniformly empty for schema compatibility and carries no information.",
    "Every rate here is agreement with the TEACHER (Claude bootstrap labels), not "
    "accuracy. Teacher red_flags carry ~36.6% set-level error (sample-pooled), "
    "~25% base-rate-representative (Tier C), 7.5% per-category.",
    "guidance_direction is stored RAW. The missing->NONE post-rule is PROPOSED, "
    "NOT ADOPTED (gate G1). It is a no-op for the feature join: features.py maps "
    "both 'NONE' and null to NaN.",
    "8K_BODY (n=8, 2 tickers) and WITHDRAWN (n=1, in train) are not evaluable and "
    "are excluded from headline agreement tables (HANDOFF §7).",
    "E1's data/labels.parquet was opened read-only and is untouched. This artifact "
    "is a separate labeler, not a replacement for the frozen labels.",
]

# Appended whenever the teacher is NOT E1's v1.1 labels (i.e. the H3v2 run).
V12_CAVEATS = [
    "The comparison teacher for this run is data/labels_v12.parquet (rubric v1.2), "
    "NOT E1's data/labels.parquet (rubric v1.1). Every agreement figure below is "
    "against the v1.2 teacher.",
    "Cross-rubric framing: H3's v1.1 numbers and this run's v1.2 numbers are each "
    "measured against their OWN teacher, so comparing them is "
    "INSTRUMENT-VS-INSTRUMENT (does the repaired student track its own teacher "
    "better?), never like-for-like accuracy. Rubric v1.2 moved red_flags on 27.48% "
    "of rows exact-set / 5.86% per-category, so the two teachers are not the same "
    "target (data/hardening/LABEL_SHIFT_v11_v12.md).",
    "14 of the 6,746 prompts (2 train / 12 eval) are not token-identical to E1's: "
    "convert_to_mlx.py head-truncates the passage to fit 2,048 tokens INCLUDING the "
    "answer, and v1.2 answers differ in length. Only the passage TAIL moved (strict "
    "head-prefix either way, -505..+33 chars); the system turn is byte-identical on "
    "all 6,746 (data/hardening/status/G1_repair_dataset.md §3).",
]

LABELING_CONFIG = (
    "student={student},backend=mlx,decoding=greedy(temp=0.0),max_tokens={max_tokens}"
)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_profile(args) -> dict:
    """Fill every unset path from E1's defaults, or from --v12's profile.

    Explicit command-line values always win, so this only ever supplies a
    default. Returns the resolved set so it can be printed and manifested —
    the run should never have to guess which corpus it labeled.
    """
    profile = V12_PROFILE if getattr(args, "v12", False) else {}
    for key, e1_default in E1_DEFAULTS.items():
        if getattr(args, key, None) is None:
            setattr(args, key, str(profile.get(key, e1_default)))
    return {key: getattr(args, key) for key in E1_DEFAULTS}


def caveats_for(labels_parquet) -> list:
    """The v1.2 caveats travel with the v1.2 TEACHER, not with the flag name."""
    is_v11 = Path(labels_parquet).resolve() == LABELS_PARQUET.resolve()
    return CAVEATS if is_v11 else CAVEATS + V12_CAVEATS


# ===========================================================================
# step 0 — sidecar (system python3: pandas/pyarrow live here)
# ===========================================================================

def read_mlx_rows(mlx_dir=None) -> list:
    """The 6,746 rendered training/eval records, tagged with their split.

    These are the artifacts the trainer actually consumed; nothing is
    re-rendered from source here. `mlx_dir` selects the campaign:
    `finetune/mlx_data` (v1.1, the default) or `finetune/mlx_data_v12`.
    """
    mlx_dir = Path(mlx_dir) if mlx_dir else MLX_DATA_DIR
    rows = []
    for split, path in (("train", mlx_dir / "train.jsonl"), ("eval", mlx_dir / "valid.jsonl")):
        if not path.exists():
            raise FileNotFoundError(f"{path} not found — run convert_to_mlx.py first")
        with open(path) as f:
            for i, line in enumerate(f):
                rec = json.loads(line)
                msgs = rec["messages"]
                roles = [m["role"] for m in msgs]
                if roles != ["system", "user", "assistant"]:
                    raise AssertionError(
                        f"{path.name}[{i}] chunk={rec['chunk_id']}: roles are {roles}, but the "
                        f"rendering contract is [system, user, assistant] "
                        f"(convert_to_mlx.py::to_messages)"
                    )
                rows.append(
                    {
                        "chunk_id": rec["chunk_id"],
                        "split": split,
                        "instruction": msgs[0]["content"],
                        "passage": msgs[1]["content"],
                        "gold_text": msgs[2]["content"],
                        "messages": msgs,
                    }
                )
    return rows


def write_sidecar(out_dir: Path, mlx_dir=None, labels_parquet=None,
                  name_suffix: str = "") -> dict:
    """Verify the corpus <-> mlx_data chain and freeze the canonical row order.

    Run with the SYSTEM python3 (needs pandas). Writes
    `<out-dir>/e1_relabel_sidecar<suffix>.json`, which the GPU step consumes so
    it never needs pandas.

    It deliberately does NOT read a training manifest: the sidecar's job is the
    corpus↔rendered-data chain and the row order. The "these rendered files are
    the ones the adapter was trained on" check belongs at RELABEL time, where it
    can hash the files that are actually about to be fed to the model — see
    `preflight()`. So a sidecar written before training finishes stays valid.
    """
    import pandas as pd  # lazy: only this entry point needs it

    mlx_dir = Path(mlx_dir) if mlx_dir else MLX_DATA_DIR
    labels_parquet = Path(labels_parquet) if labels_parquet else LABELS_PARQUET

    rows = read_mlx_rows(mlx_dir)
    by_id = {r["chunk_id"]: r for r in rows}
    if len(by_id) != len(rows):
        raise AssertionError(f"duplicate chunk_id across {mlx_dir.name}/{{train,valid}}.jsonl")
    if len(by_id) != TARGET_ROWS:
        raise AssertionError(
            f"{mlx_dir} renders {len(by_id)} rows, expected the frozen {TARGET_ROWS} "
            f"(train 5,736 + eval 1,010). The split is frozen — refusing to relabel a "
            f"corpus that is not E1's."
        )

    corpus = pd.read_parquet(CORPUS_PARQUET)          # READ-ONLY
    labels = pd.read_parquet(labels_parquet, columns=["chunk_id", "parse_ok"])  # READ-ONLY
    labeled = set(labels.loc[labels["parse_ok"], "chunk_id"])

    # Every rendered row must carry a usable teacher label, or the agreement
    # summary would be scored against a hole. The reverse is NOT required: the
    # teacher file legitimately holds rows the frozen split excludes — under
    # v1.1 the refusal chunk failed to parse, under v1.2 it parsed but the
    # frozen split manifest still keeps it out of both splits.
    unlabeled = sorted(set(by_id) - labeled)
    if unlabeled:
        raise AssertionError(
            f"{len(unlabeled)} rendered chunk_ids have no usable label in "
            f"{labels_parquet.name} (e.g. {unlabeled[:3]}). Refusing to relabel against an "
            f"incomplete teacher."
        )
    excluded = sorted(set(labels["chunk_id"]) - set(by_id))

    order, n_equal, n_trunc, bad = [], 0, 0, []
    for chunk_id, text in zip(corpus["chunk_id"], corpus["text"]):
        row = by_id.get(chunk_id)
        if row is None:
            continue  # the excluded refusal chunk
        order.append(chunk_id)
        if row["passage"] == text:
            n_equal += 1
        else:
            n_trunc += 1
            if not text.startswith(row["passage"]):
                bad.append(chunk_id)
    if bad:
        raise AssertionError(
            f"{len(bad)} rendered passages are NOT head-prefixes of their "
            f"labeling_corpus.parquet text (e.g. {bad[:3]}). convert_to_mlx.py only ever "
            f"drops a passage TAIL, so the artifacts disagree about the text itself."
        )
    if len(order) != len(by_id):
        raise AssertionError(
            f"{len(by_id) - len(order)} labeled chunk_ids are missing from "
            f"{CORPUS_PARQUET.name}"
        )

    instructions = {r["instruction"] for r in rows}
    if len(instructions) != 1:
        raise AssertionError(
            f"the system instruction is NOT byte-identical across the 6,746 rows "
            f"({len(instructions)} distinct values). PROMPT_TEMPLATE.md requires exactly one."
        )

    sidecar = {
        "generated_utc": utcnow(),
        "purpose": "labeler-attenuation relabel: canonical row order + corpus<->mlx_data verification",
        "corpus_parquet": {
            "path": str(CORPUS_PARQUET),
            "sha256": ev.sha256_file(CORPUS_PARQUET),
            "n_rows": int(len(corpus)),
        },
        "labels_parquet": {
            "path": str(labels_parquet),
            "sha256": ev.sha256_file(labels_parquet),
            "n_rows": int(len(labels)),
            "n_labeled": len(labeled),
            "excluded_chunk_ids": excluded,
            "excluded_note": (
                "in the teacher file but NOT in the frozen split, so never relabeled here"
            ),
            "access": "READ-ONLY — the teacher labels are frozen and are never written by this tool",
        },
        "mlx_data": {
            "dir": str(mlx_dir),
            "train_jsonl_sha256": ev.sha256_file(mlx_dir / "train.jsonl"),
            "valid_jsonl_sha256": ev.sha256_file(mlx_dir / "valid.jsonl"),
            "n_train": sum(1 for r in rows if r["split"] == "train"),
            "n_eval": sum(1 for r in rows if r["split"] == "eval"),
        },
        "instruction_sha256": ev.sha256_text(next(iter(instructions))),
        "verification": {
            "n_rows": len(order),
            "n_passages_identical_to_corpus_text": n_equal,
            "n_passages_head_truncated_to_fit_2048": n_trunc,
            "n_passages_not_a_head_prefix": 0,
        },
        "order": order,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / artifact_name(SIDECAR_NAME, name_suffix)
    path.write_text(json.dumps(sidecar, indent=2) + "\n")
    print(
        f"wrote {path}\n  data      {mlx_dir}\n  teacher   {labels_parquet}\n"
        f"  {len(order)} rows in corpus order · "
        f"{n_equal} passages identical to corpus text · {n_trunc} head-truncated · "
        f"0 non-prefix",
        file=sys.stderr,
    )
    return sidecar


def load_sidecar(out_dir: Path, explicit: str = None, name_suffix: str = "") -> dict:
    path = Path(explicit) if explicit else out_dir / artifact_name(SIDECAR_NAME, name_suffix)
    if not path.exists():
        raise SystemExit(
            f"{path} not found. Run the sidecar step FIRST, with the system python3:\n"
            f"    python3 {Path(__file__).relative_to(REPO)} --write-sidecar"
        )
    return json.loads(path.read_text())


# ===========================================================================
# rows + preflight (no pandas: this half runs under .mlx_venv)
# ===========================================================================

def load_rows(sidecar: dict, split: str = "all", limit: int = 0, mlx_dir=None) -> list:
    """Rows in the sidecar's canonical (corpus) order, hard-verified against it."""
    mlx_dir = Path(mlx_dir) if mlx_dir else MLX_DATA_DIR
    rows = read_mlx_rows(mlx_dir)
    by_id = {r["chunk_id"]: r for r in rows}
    order = sidecar["order"]
    if set(order) != set(by_id):
        raise SystemExit(
            f"the sidecar's row set does not match {mlx_dir}/{{train,valid}}.jsonl. "
            f"Re-run --write-sidecar (and check you are not pairing one campaign's "
            f"sidecar with the other campaign's data)."
        )
    for name, path in (("train_jsonl_sha256", mlx_dir / "train.jsonl"),
                       ("valid_jsonl_sha256", mlx_dir / "valid.jsonl")):
        actual = ev.sha256_file(path)
        if actual != sidecar["mlx_data"][name]:
            raise SystemExit(
                f"{path} sha256 {actual} != the sidecar's {sidecar['mlx_data'][name]} "
                f"(sidecar data dir: {sidecar['mlx_data'].get('dir', 'unrecorded')}). "
                f"The rendered data changed after the corpus verification, or the sidecar "
                f"belongs to the other campaign. Re-run --write-sidecar and inspect why it "
                f"moved before generating anything."
            )
    out = [by_id[c] for c in order]
    if split != "all":
        out = [r for r in out if r["split"] == split]
    if limit:
        out = out[:limit]
    return out


def preflight(args, rows: list, sidecar: dict) -> dict:
    """Everything that can fail is made to fail here, before the GPU is touched."""
    mlx_dir = Path(args.mlx_data_dir)
    tman_path = Path(args.train_manifest)
    if not tman_path.exists():
        raise FileNotFoundError(f"training manifest not found: {tman_path}")
    tman = json.loads(tman_path.read_text())

    for key in ("train.jsonl", "valid.jsonl"):
        path = mlx_dir / key
        expected = tman["data"]["files"][key]["sha256"]
        actual = ev.sha256_file(path)
        if actual != expected:
            raise SystemExit(
                f"{path} sha256 {actual} does not match the training manifest's {expected} "
                f"({tman_path}). The student would be labeling data it was not trained on. "
                f"Refusing to run."
            )

    model_path = args.model or tman["model"]["resolved_snapshot_path"]
    adapter_prov = ev._adapter_provenance(args.adapter_path, model_path)

    # The reference eval that this run's eval-split rows must reproduce
    # byte-for-byte. Its manifest sits beside its predictions.jsonl.
    ref_predictions = Path(args.reference_predictions)
    ref_manifest = ref_predictions.parent / "manifest.json"
    eval_instr_sha = ref_adapter_sha = None
    if ref_manifest.exists():
        refman = json.loads(ref_manifest.read_text())
        eval_instr_sha = refman.get("data", {}).get("instruction_sha256")
        ref_adapter_sha = refman.get("adapter", {}).get("adapters_sha256")

    # HANDOFF §7, verify-artifact: the adapter about to label 6,746 chunks must
    # be the adapter the reference eval actually tested. This is the guard for
    # the segmented-training trap — if the run was killed and resumed, the FINAL
    # adapter lives in the last segment's checkpoint dir, not the one the
    # campaign plan named.
    if ref_adapter_sha and ref_adapter_sha != adapter_prov["adapters_sha256"]:
        raise SystemExit(
            f"ADAPTER MISMATCH — refusing to run.\n"
            f"  about to relabel with : {args.adapter_path}\n"
            f"                          adapters.safetensors {adapter_prov['adapters_sha256']}\n"
            f"  reference eval used   : {refman.get('adapter', {}).get('path')}\n"
            f"                          adapters.safetensors {ref_adapter_sha}\n"
            f"  reference manifest    : {ref_manifest}\n"
            f"These are different weights, so the eval-split reproduction check could not "
            f"pass and this artifact would not be the artifact that was tested. If training "
            f"was segmented by kills, pass --adapter-path/--train-manifest for the LAST "
            f"segment (the reference manifest's adapter.path / train_manifest.path)."
        )
    if not ref_predictions.exists():
        print(
            f"\n  !! WARNING: reference predictions {ref_predictions} do not exist yet.\n"
            f"  !! The eval-split reproduction check (the verify-artifact check) cannot run\n"
            f"  !! at finalize time unless they are there. The relabel is supposed to run\n"
            f"  !! AFTER the eval it reproduces.\n",
            file=sys.stderr,
        )

    instr_sha = sidecar["instruction_sha256"]
    return {
        "model_path": model_path,
        "train_manifest": {
            "path": str(tman_path),
            "sha256": ev.sha256_file(tman_path),
            "run_id": tman.get("run_id"),
        },
        "model": {"path": model_path, "weights_sha256": tman["model"].get("weights_sha256")},
        "adapter": adapter_prov,
        "data": {
            "source": f"{mlx_dir}/{{train,valid}}.jsonl (the records the trainer consumed)",
            "mlx_data_dir": str(mlx_dir),
            "train_jsonl_sha256": sidecar["mlx_data"]["train_jsonl_sha256"],
            "valid_jsonl_sha256": sidecar["mlx_data"]["valid_jsonl_sha256"],
            "sha_matches_train_manifest": True,
            "corpus_parquet": sidecar["corpus_parquet"],
            "labels_parquet": sidecar["labels_parquet"],
            "corpus_verification": sidecar["verification"],
            "instruction_sha256": instr_sha,
            "reference_eval_manifest": str(ref_manifest) if ref_manifest.exists() else None,
            "instruction_sha256_matches_reference_eval": (
                None if eval_instr_sha is None else instr_sha == eval_instr_sha
            ),
            "adapter_sha256_matches_reference_eval": (
                None if ref_adapter_sha is None else ref_adapter_sha == adapter_prov["adapters_sha256"]
            ),
            "n_rows_targeted": len(rows),
        },
    }


# ===========================================================================
# step 1 — generation (checkpointed per row)
# ===========================================================================

def ensure_trailing_newline(path: Path) -> bool:
    """Terminate a torn final line before appending to it.

    A `kill -9` mid-write leaves a half-written record with no newline.
    `load_predictions` correctly ignores that fragment on READ — but appending
    straight onto it glues the next record to the fragment, so the resume would
    silently lose one GOOD row per kill (observed in the resume smoke:
    9/10 instead of 10/10). Writing the missing newline first turns the fragment
    into its own ignorable line and keeps every later record intact.
    """
    if not path.exists() or path.stat().st_size == 0:
        return False
    with open(path, "rb") as f:
        f.seek(-1, os.SEEK_END)
        if f.read(1) == b"\n":
            return False
    with open(path, "a") as f:
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    print(f"  [resume] terminated a torn final line in {path.name} before appending", file=sys.stderr)
    return True


def generate(rows: list, args, journal_path: Path) -> dict:
    """One JSON answer per row, greedy, appended + fsync'd row by row.

    Returns this process's segment record. Mirrors eval.py::mlx_generate's
    decoding and telemetry exactly so the two runs are comparable (and so the
    eval-split rows reproduce the epoch-2 eval byte-for-byte).
    """
    from mlx_lm import load as mlx_load
    from mlx_lm.generate import stream_generate
    from mlx_lm.sample_utils import make_sampler
    from transformers import AutoTokenizer

    if not args.resume and journal_path.exists():
        raise SystemExit(
            f"{journal_path} exists and --no-resume was given. Appending would mix two "
            f"generations in one artifact. Move it aside first."
        )
    existing = ev.load_predictions(journal_path) if args.resume else {}

    # The RENDERING tokenizer is the plain HF tokenizer from the same snapshot
    # convert_to_mlx.py used — not mlx_lm's wrapper, whose apply_chat_template
    # injects an `enable_thinking` kwarg. Identical code path == identical bytes.
    render_tok = AutoTokenizer.from_pretrained(args.model, local_files_only=True)

    t_render = time.perf_counter()
    for row in rows:
        row["_prompt_sha256"] = ev.sha256_text(
            json.dumps(ev.render_prompt_token_ids(render_tok, row))
        )
    todo = ev.select_rows_to_generate(rows, existing, journal_path)
    n_done_before = len(rows) - len(todo)
    print(
        f"rendered {len(rows)} prompts in {time.perf_counter() - t_render:.1f}s · "
        f"{n_done_before} already in {journal_path.name} · {len(todo)} to generate",
        file=sys.stderr,
    )
    if args.max_rows_per_segment:
        todo = todo[: args.max_rows_per_segment]
        print(f"segment cap: generating at most {len(todo)} rows this process", file=sys.stderr)
    if not todo:
        return {"n_generated": 0, "note": "nothing to do — journal already covers every target row"}

    print("loading base model + adapter (the only GPU work) ...", file=sys.stderr)
    t_load = time.perf_counter()
    model, tokenizer = mlx_load(args.model, adapter_path=args.adapter_path)
    load_s = time.perf_counter() - t_load
    print(f"  loaded in {load_s:.1f}s", file=sys.stderr)

    sampler = make_sampler(temp=0.0)  # temp==0 -> mx.argmax: fully deterministic
    repaired = ensure_trailing_newline(journal_path)
    started = utcnow()
    fresh = []
    t0 = time.perf_counter()
    with open(journal_path, "a") as fh:
        for i, row in enumerate(todo, 1):
            prompt_ids = ev.render_prompt_token_ids(render_tok, row)
            prompt_sha = ev.sha256_text(json.dumps(prompt_ids))
            if prompt_sha != row["_prompt_sha256"]:
                raise SystemExit(
                    f"chunk {row['chunk_id']}: prompt rendering is not deterministic within "
                    f"one process. Stopping rather than writing two prompt versions."
                )
            t_row = time.perf_counter()
            text, last = "", None
            for resp in stream_generate(
                model, tokenizer, prompt_ids, max_tokens=args.max_tokens, sampler=sampler
            ):
                text += resp.text
                last = resp
            latency = time.perf_counter() - t_row

            rec = {
                "chunk_id": row["chunk_id"],
                "split": row["split"],
                "raw_output": text,
                "prompt_sha256": prompt_sha,
                "prompt_tokens": int(last.prompt_tokens) if last else len(prompt_ids),
                "generation_tokens": int(last.generation_tokens) if last else 0,
                "prompt_tps": float(last.prompt_tps) if last else None,
                "generation_tps": float(last.generation_tps) if last else None,
                "finish_reason": last.finish_reason if last else "no_response",
                "peak_memory_gb": round(float(last.peak_memory), 3) if last else None,
                "latency_s": round(latency, 3),
                "generated_utc": utcnow(),
            }
            ev.append_prediction(fh, rec)
            fresh.append(rec)

            if i % args.progress_every == 0 or i == len(todo):
                elapsed = time.perf_counter() - t0
                cph = i / elapsed * 3600.0
                done_all = n_done_before + i
                eta_h = (len(rows) - done_all) / cph if cph else float("nan")
                print(
                    f"  [{i}/{len(todo)} this segment · {done_all}/{len(rows)} overall] "
                    f"{latency:.2f}s/row · {cph:.0f} chunks/h · ETA {eta_h:.2f}h to finish "
                    f"the corpus · last finish={rec['finish_reason']} "
                    f"gen_tok={rec['generation_tokens']}",
                    file=sys.stderr, flush=True,
                )

    wall = time.perf_counter() - t0
    seg = {
        "started_utc": started,
        "ended_utc": utcnow(),
        "n_generated": len(fresh),
        "torn_final_line_repaired_before_append": repaired,
        "model_load_seconds": round(load_s, 1),
        "wall_seconds": round(wall, 1),
        "chunks_per_hour": round(len(fresh) / wall * 3600.0, 1) if wall else None,
        "finish_reasons": dict(ev.Counter(r["finish_reason"] for r in fresh)),
        "versions": ev._versions(),
    }
    return seg


# ===========================================================================
# step 2 — journal -> label rows -> parquet
# ===========================================================================

def student_label_row(rec: dict, run_id: str = RUN_ID) -> dict:
    """One journal record -> the label columns of the teacher parquet's schema.

    Pure function (no I/O): this is the mapping the tests pin. Anything the
    model emitted that is outside the taxonomy is dropped from `red_flags` and
    recorded as a schema issue — inventing a category to keep would corrupt the
    downstream feature counts.
    """
    raw = rec.get("raw_output")
    parsed, err = ev.parse_model_output(raw)
    parse_ok = parsed is not None
    issues = ev.validate_schema(parsed) if parse_ok else []

    sentiment = guidance = None
    red_flags = []
    if parse_ok:
        s = parsed.get("sentiment")
        if s in ev.SENTIMENT_LABELS:
            sentiment = s
        g = parsed.get("guidance_direction")
        if g in ev.GUIDANCE_LABELS:
            guidance = g
        flags = parsed.get("red_flags")
        if isinstance(flags, list):
            for f in flags:
                if not isinstance(f, dict):
                    continue
                cat, mod = f.get("category"), f.get("modality")
                if cat in ev.RED_FLAG_CATEGORIES and mod in ev.RED_FLAG_MODALITIES:
                    red_flags.append({"category": cat, "modality": mod})

    return {
        "parse_ok": parse_ok,
        "schema_valid": parse_ok and not issues,
        "api_result_type": "student_local_mlx",
        "parse_error": err,
        "raw_label_json": raw,
        "sentiment": sentiment,
        "guidance_direction": guidance,
        "red_flags": red_flags,
        "distress_tier": [],  # never a training target — empty by construction
        "batch_id": run_id,
        "labeled_at": rec.get("generated_utc"),
        "stop_reason": rec.get("finish_reason"),
        "output_tokens": int(rec.get("generation_tokens") or 0),
        "split": rec.get("split"),
        "prompt_tokens": int(rec.get("prompt_tokens") or 0),
        "prompt_sha256": rec.get("prompt_sha256"),
        "latency_s": float(rec.get("latency_s") or 0.0),
        "schema_issues": issues,
    }


def teacher_schema(labels_parquet: Path) -> tuple:
    """The teacher parquet's OWN arrow schema, plus the one repair it needs.

    Copied from the file rather than re-declared so the downstream feature join
    is a path swap and nothing else. One narrow, recorded deviation: a column
    the teacher happened to leave entirely null is typed `null` in its parquet
    — `data/labels_v12.parquet`'s `parse_error`, because every teacher row
    parsed — and a null-typed arrow column cannot hold the student's
    parse-failure message. Those columns are widened to string and the widening
    is returned so it lands in the manifest. `data/labels.parquet` (v1.1) has no
    null-typed column, so this is a no-op on the H3 path.

    Returns (fields, widened_field_names).
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    schema = pq.read_schema(labels_parquet).remove_metadata()
    fields, widened = [], []
    for f in schema:
        if pa.types.is_null(f.type):
            fields.append(pa.field(f.name, pa.string()))
            widened.append(f.name)
        else:
            fields.append(f)
    return fields, widened


def fill_teacher_only_columns(df, fields: list, labels_parquet: Path,
                              instruction_sha256: str) -> dict:
    """Teacher-schema columns a student run has no analogue for.

    v1.1's 31-column schema has none — H3 populated every one of them. v1.2's
    34-column schema adds three, and one of them would carry FALSE PROVENANCE if
    copied from the teacher: `system_prompt_sha256` is the teacher's 9,521-char
    labeling prompt (`30605197…`), whereas the student's system turn is the
    1,825-char training instruction (`ebc45a85…`) — two distinct artifacts,
    `data/hardening/status/G1_repair_dataset.md` §4.

    Mutates `df` and returns {name: value} so every fill is recorded in the
    manifest rather than back-filled silently.
    """
    import pandas as pd

    filled = {}
    for name in [f.name for f in fields if f.name not in df.columns]:
        if name == "system_prompt_sha256":
            value = instruction_sha256          # the STUDENT's system turn
        elif name == "rubric_version":
            # the rubric revision of the TARGETS this student was trained on
            vals = pd.read_parquet(labels_parquet, columns=[name])[name].dropna().unique()
            value = str(vals[0]) if len(vals) == 1 else None
        else:
            value = None                        # e.g. completion_batch_id
        df[name] = value
        filled[name] = value
    return filled


def build_parquet(journal_path: Path, parquet_path: Path, max_tokens: int,
                  mlx_dir=None, labels_parquet=None, run_id: str = RUN_ID,
                  student: str = None, instruction_sha256: str = None) -> dict:
    """Journal -> a parquet whose leading columns ARE the teacher's own schema.

    Six student-only columns are appended after it: 31 + 6 = 37 on the v1.1
    (H3) path, 34 + 6 = 40 on the v1.2 (H3v2) path.
    """
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    labels_parquet = Path(labels_parquet) if labels_parquet else LABELS_PARQUET
    student = student or DEFAULT_ADAPTER.name

    records = ev.load_predictions(journal_path)
    if not records:
        raise SystemExit(f"{journal_path} has no usable records.")

    corpus = pd.read_parquet(CORPUS_PARQUET)                          # READ-ONLY
    corpus = corpus[corpus["chunk_id"].isin(set(records))].copy()      # corpus order preserved
    mlx = {r["chunk_id"]: r for r in read_mlx_rows(mlx_dir)}
    corpus_text = dict(zip(corpus["chunk_id"], corpus["text"]))

    label_rows = []
    for cid in corpus["chunk_id"]:
        row = student_label_row(records[cid], run_id=run_id)
        row["chunk_id"] = cid
        row["max_tokens_used"] = max_tokens
        row["labeling_config"] = LABELING_CONFIG.format(student=student, max_tokens=max_tokens)
        row["passage_was_head_truncated"] = mlx[cid]["passage"] != corpus_text[cid]
        label_rows.append(row)
    labels_df = pd.DataFrame(label_rows).set_index("chunk_id")

    df = corpus.set_index("chunk_id").join(labels_df, how="inner").reset_index()

    fields, widened = teacher_schema(labels_parquet)
    n_teacher_fields = len(fields)
    fields.append(pa.field("split", pa.string()))
    fields.append(pa.field("passage_was_head_truncated", pa.bool_()))
    fields.append(pa.field("prompt_tokens", pa.int64()))
    fields.append(pa.field("prompt_sha256", pa.string()))
    fields.append(pa.field("latency_s", pa.float64()))
    fields.append(pa.field("schema_issues", pa.list_(pa.string())))
    filled = fill_teacher_only_columns(df, fields, labels_parquet, instruction_sha256)
    schema = pa.schema(fields)

    table = pa.Table.from_pandas(df[[f.name for f in fields]], schema=schema, preserve_index=False)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, parquet_path)

    n_by_split = df["split"].value_counts().to_dict()
    return {
        "path": str(parquet_path),
        "sha256": ev.sha256_file(parquet_path),
        "n_rows": int(len(df)),
        "n_by_split": {k: int(v) for k, v in n_by_split.items()},
        "schema_source": (
            f"columns 1-{n_teacher_fields} copied verbatim from {labels_parquet.name}'s arrow "
            f"schema; 6 student-only columns appended"
        ),
        "teacher_parquet": str(labels_parquet),
        "null_typed_columns_widened_to_string": widened,
        "teacher_only_columns_filled_for_the_student": filled,
        "n_columns": len(fields),
        "parse_failures": int((~df["parse_ok"]).sum()),
        "schema_violations": int((~df["schema_valid"]).sum()),
        "join_note": (
            "chunk_id-keyed and drop-in for features.py (which reads chunk_id, "
            "section_type, sentiment, guidance_direction, red_flags and filters parse_ok). "
            "distress_tier is uniformly empty by construction."
        ),
    }


# ===========================================================================
# agreement summary (sanity only — NOT the H3 comparison)
# ===========================================================================

def agreement_summary(records: dict, mlx_dir=None) -> dict:
    """Compact teacher-agreement block, reusing eval.py's own scorers verbatim.

    Split three ways (pooled / train / eval) because the train slice is
    memorized: the eval slice is the only unbiased one, and it should reproduce
    the reference epoch-2 eval report. The gold labels come from the rendered
    records themselves, so they follow `mlx_dir` — v1.1 targets under
    `mlx_data/`, v1.2 targets under `mlx_data_v12/`.
    """
    import pandas as pd

    rows = read_mlx_rows(mlx_dir)
    st = pd.read_parquet(CORPUS_PARQUET, columns=["chunk_id", "section_type"])
    section_type = dict(zip(st["chunk_id"], st["section_type"]))
    scored = [
        {"chunk_id": r["chunk_id"], "split": r["split"], "gold": json.loads(r["gold_text"])}
        for r in rows if r["chunk_id"] in records
    ]
    preds = {cid: rec.get("raw_output") for cid, rec in records.items()}

    headline = [r for r in scored if section_type.get(r["chunk_id"]) not in ev.HEADLINE_EXCLUDED_SECTION_TYPES]
    excluded = [r for r in scored if section_type.get(r["chunk_id"]) in ev.HEADLINE_EXCLUDED_SECTION_TYPES]

    def slice_for(split):
        sub = headline if split == "pooled" else [r for r in headline if r["split"] == split]
        if not sub:
            return None
        out = ev.score_slice(sub, preds)
        out["guidance_post_rule_missing_as_none"] = _guidance_post_rule(sub, preds)
        return out

    return {
        "basis": (
            "AGREEMENT WITH THE TEACHER (Claude bootstrap labels), NOT accuracy. A perfectly "
            "agreeing student has reproduced the teacher including its errors."
        ),
        "teacher_noise_floor": ev.TEACHER_NOISE,
        "headline_excludes": {
            "8K_BODY": ev.NOT_EVALUABLE_REASONS["8K_BODY"],
            "WITHDRAWN": ev.NOT_EVALUABLE_REASONS["WITHDRAWN"],
        },
        "n_scored": len(scored),
        "pooled_MEMORIZATION_INFLATED": slice_for("pooled"),
        "train_MEMORIZED_NOT_A_MEASUREMENT": slice_for("train"),
        "eval_ONLY_UNBIASED_SLICE": slice_for("eval"),
        "excluded_8K_BODY": {"n": len(excluded), "not_evaluable": True},
    }


def _guidance_post_rule(rows: list, preds: dict) -> dict:
    """guidance_direction under the PROPOSED (not adopted) missing->NONE rule."""
    n = agree = n_rewritten = 0
    for r in rows:
        gold = r["gold"]
        if "guidance_direction" not in gold:
            continue
        parsed, err = ev.parse_model_output(preds.get(r["chunk_id"]))
        n += 1
        if parsed is None:
            continue
        value = parsed.get("guidance_direction")
        if value is None:
            value, n_rewritten = "NONE", n_rewritten + 1
        if value == gold["guidance_direction"]:
            agree += 1
    return {
        "status": "PROPOSED, NOT ADOPTED (gate G1). Raw output is what the parquet stores.",
        "n": n,
        "n_agree": agree,
        "rate": round(agree / n, 4) if n else None,
        "n_rows_rewritten_missing_to_NONE": n_rewritten,
    }


def reproduction_check(records: dict, ref_path: Path) -> dict:
    """Do the eval-split rows reproduce the epoch-2 eval predictions byte-for-byte?

    Greedy decoding on identical prompts with an identical adapter should be
    deterministic. This is the verify-artifact check: the artifact being run is
    the artifact that was tested. A missing reference is reported LOUDLY as
    "did not run" — never as a quiet pass — because an unverified artifact that
    looks verified is worse than one that is plainly marked unverified.
    """
    if not Path(ref_path).exists():
        return {
            "STATUS": "MISSING_REFERENCE — THE VERIFY-ARTIFACT CHECK DID NOT RUN",
            "verified": False,
            "reference": str(ref_path),
            "what_this_means": (
                "the eval-split rows were NOT compared against the eval that was actually "
                "reported, so nothing here proves this artifact came from the tested "
                "adapter. Do not consume the parquet until the reference predictions exist "
                "and --finalize-only is re-run (finalize is idempotent and loads no model)."
            ),
        }
    ref = ev.load_predictions(ref_path)
    shared = [c for c in records if c in ref]
    identical = {c for c in shared if records[c].get("raw_output") == ref[c].get("raw_output")}
    differing = [c for c in shared if c not in identical]
    return {
        "reference": str(ref_path),
        "verified": bool(shared) and not differing,
        "meaning": (
            "greedy decoding on a token-identical prompt with the same adapter must be "
            "deterministic; a mismatch means the prompt, the adapter or the decoding moved"
        ),
        "n_compared": len(shared),
        "n_identical": len(identical),
        "n_differing": len(differing),
        "differing_examples": sorted(differing)[:5],
    }


# ===========================================================================
# manifest
# ===========================================================================

def update_manifest(path: Path, updates: dict, segment: dict = None,
                    run_id: str = RUN_ID, caveats: list = None) -> dict:
    man = json.loads(path.read_text()) if path.exists() else {}
    man.setdefault("run_id", run_id)
    man.setdefault("created_utc", utcnow())
    man.setdefault("segments", [])
    man.update(updates)
    man["updated_utc"] = utcnow()
    man["cost_usd"] = 0.0
    man["anthropic_api_calls"] = 0
    man["caveats"] = caveats if caveats is not None else CAVEATS
    if segment is not None:
        man["segments"].append(segment)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(man, indent=2) + "\n")
    return man


def journal_progress(journal_path: Path, target: int) -> dict:
    records = ev.load_predictions(journal_path)
    return {
        "path": str(journal_path),
        "n_rows": len(records),
        "n_target": target,
        "complete": len(records) >= target,
        "pct": round(100.0 * len(records) / target, 2) if target else None,
    }


def totals_from_journal(records: dict) -> dict:
    lat = [r["latency_s"] for r in records.values() if r.get("latency_s") is not None]
    ptok = [r.get("prompt_tokens") or 0 for r in records.values()]
    gtok = [r.get("generation_tokens") or 0 for r in records.values()]
    total_s = sum(lat)
    return {
        "n_rows": len(records),
        "sum_of_row_latencies_seconds": round(total_s, 1),
        "sum_of_row_latencies_hours": round(total_s / 3600.0, 2),
        "chunks_per_hour_excluding_load_and_gaps": round(len(lat) / total_s * 3600.0, 1) if total_s else None,
        "prompt_tokens_total": int(sum(ptok)),
        "generation_tokens_total": int(sum(gtok)),
        "finish_reasons": dict(ev.Counter(r.get("finish_reason") for r in records.values())),
        "note": (
            "row-latency sum, not a fresh wall-clock: it excludes per-segment model load and "
            "idle gaps between segments, so it is an upper bound on sustained throughput."
        ),
    }


# ===========================================================================
# main
# ===========================================================================

def build_parser() -> argparse.ArgumentParser:
    """The CLI. Every campaign-dependent path defaults to None and is filled by
    `resolve_profile()` — from E1's defaults, or from `--v12`'s profile."""
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--v12", action="store_true",
                    help="H3v2: relabel with the rubric-v1.2 student over mlx_data_v12, "
                         "scored against data/labels_v12.parquet, into data/hardening/h3v2/. "
                         "Flips data + teacher + adapter + training manifest + reference eval "
                         "+ out-dir + filename suffix + run id together.")
    ap.add_argument("--out-dir", default=None,
                    help="default: data/hardening (E1) · data/hardening/h3v2 (--v12)")
    ap.add_argument("--name-suffix", default=None,
                    help="appended to every output filename. default: '' (E1) · '_v12' (--v12)")
    ap.add_argument("--run-id", default=None,
                    help=f"batch_id written into the parquet. default: {RUN_ID} · "
                         f"{RUN_ID_V12} (--v12)")
    ap.add_argument("--mlx-data-dir", default=None,
                    help="the rendered records to relabel. default: finetune/mlx_data (E1) · "
                         "finetune/mlx_data_v12 (--v12)")
    ap.add_argument("--labels-parquet", default=None,
                    help="the TEACHER: schema source + agreement comparand. READ-ONLY. "
                         "default: data/labels.parquet (E1) · data/labels_v12.parquet (--v12)")
    ap.add_argument("--sidecar", default=None,
                    help=f"default: <out-dir>/{SIDECAR_NAME} with the name suffix applied "
                         f"(a smoke run points at the real one)")
    ap.add_argument("--write-sidecar", action="store_true",
                    help="step 0: system python3; verify the parquets and freeze the row order")
    ap.add_argument("--finalize-only", action="store_true",
                    help="step 2: system python3; journal -> parquet + agreement summary, no model")
    ap.add_argument("--allow-partial", action="store_true",
                    help="allow --finalize-only on an incomplete journal (smoke runs)")
    ap.add_argument("--adapter-path", default=None)
    ap.add_argument("--train-manifest", default=None)
    ap.add_argument("--model", default=None, help="default: the training manifest's snapshot path")
    ap.add_argument("--max-tokens", type=int, default=520)
    ap.add_argument("--split", choices=["all", "train", "eval"], default="all")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-rows-per-segment", type=int, default=0,
                    help="voluntarily exit after N rows (0 = run until done or killed)")
    ap.add_argument("--progress-every", type=int, default=25)
    ap.add_argument("--no-resume", dest="resume", action="store_false")
    ap.add_argument("--reference-predictions", default=None,
                    help="the eval whose predictions the eval-split rows must reproduce "
                         "byte-for-byte. Its manifest.json (same directory) supplies the "
                         "adapter cross-check.")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    resolved = resolve_profile(args)
    print(
        "relabel_e1 — resolved paths\n  " + "\n  ".join(
            f"{k:<22} {v}" for k, v in resolved.items()
        ),
        file=sys.stderr,
    )

    out_dir = Path(args.out_dir).resolve()
    suffix = args.name_suffix
    journal_path = out_dir / artifact_name(JOURNAL_NAME, suffix)
    parquet_path = out_dir / artifact_name(PARQUET_NAME, suffix)
    manifest_path = out_dir / artifact_name(MANIFEST_NAME, suffix)

    if args.write_sidecar:
        write_sidecar(out_dir, mlx_dir=args.mlx_data_dir,
                      labels_parquet=args.labels_parquet, name_suffix=suffix)
        return 0

    sidecar = load_sidecar(out_dir, args.sidecar, suffix)
    sidecar_path = (Path(args.sidecar) if args.sidecar
                    else out_dir / artifact_name(SIDECAR_NAME, suffix))
    rows = load_rows(sidecar, args.split, args.limit, mlx_dir=args.mlx_data_dir)
    target = len(rows)

    if args.finalize_only:
        progress = journal_progress(journal_path, target)
        if not progress["complete"] and not args.allow_partial:
            raise SystemExit(
                f"journal has {progress['n_rows']}/{target} rows. The parquet is written on "
                f"COMPLETION only — resume the generation step, or pass --allow-partial if this "
                f"is a smoke run."
            )
        records = ev.load_predictions(journal_path)
        parquet = build_parquet(
            journal_path, parquet_path, args.max_tokens,
            mlx_dir=args.mlx_data_dir, labels_parquet=args.labels_parquet,
            run_id=args.run_id, student=Path(args.adapter_path).name,
            instruction_sha256=sidecar["instruction_sha256"],
        )
        man = update_manifest(manifest_path, {
            "journal": {**progress, "sha256": ev.sha256_file(journal_path)},
            "totals": totals_from_journal(records),
            "reproduction_check": reproduction_check(records, Path(args.reference_predictions)),
            "parquet": {**parquet, "partial": not progress["complete"]},
            # sanity only — NOT the H3/H3v2 comparison, which is quant-modeler's
            "agreement_summary": agreement_summary(records, mlx_dir=args.mlx_data_dir),
            "finalized_utc": utcnow(),
        }, run_id=args.run_id, caveats=caveats_for(args.labels_parquet))
        rc = man["reproduction_check"]
        ag = man["agreement_summary"].get("eval_ONLY_UNBIASED_SLICE") or {}
        if "n_compared" in rc:
            repro = (f"{rc['n_identical']}/{rc['n_compared']} eval-split rows byte-identical "
                     f"to {Path(rc['reference']).parent.name}")
        else:
            repro = ("!! DID NOT RUN — reference predictions missing:\n"
                     f"            !! {rc['reference']}\n"
                     "            !! this artifact is UNVERIFIED; re-run --finalize-only "
                     "once it exists")
        print(
            f"\nFINALIZED{' (PARTIAL)' if not progress['complete'] else ''}\n"
            f"  parquet   {parquet['path']}\n"
            f"            {parquet['n_rows']} rows · {parquet['n_columns']} cols · "
            f"sha {parquet['sha256'][:16]}\n"
            f"  teacher   {parquet['teacher_parquet']}\n"
            f"  parse     {parquet['parse_failures']} failures · "
            f"{parquet['schema_violations']} schema violations\n"
            f"  repro     {repro}\n"
            f"  eval-slice agreement (teacher, not accuracy): "
            f"sentiment {(ag.get('sentiment') or {}).get('exact_match')} · "
            f"red_flags exact-set "
            f"{((ag.get('red_flags') or {}).get('exact_set_match_category_modality') or {}).get('rate')}\n"
            f"  manifest  {manifest_path}",
            file=sys.stderr,
        )
        return 0 if progress["complete"] else 2

    # --- generation ---------------------------------------------------------
    try:
        import mlx_lm  # noqa: F401
    except ImportError:
        raise SystemExit(
            "mlx_lm is not importable. Run the generation step with the project venv:\n"
            f"    {HERE / '.mlx_venv' / 'bin' / 'python'} {Path(__file__).name}"
        )

    prov = preflight(args, rows, sidecar)
    args.model = prov["model_path"]
    out_dir.mkdir(parents=True, exist_ok=True)
    update_manifest(manifest_path, {
        "purpose": (
            f"labeler-attenuation check ({args.run_id}): the student "
            f"{Path(args.adapter_path).name} re-labels all {TARGET_ROWS} labeled E1 chunks so "
            f"features can be re-derived and the E1 backtest re-run on student labels. Teacher "
            f"for comparison: {Path(args.labels_parquet).name}."
        ),
        "model": prov["model"],
        "adapter": prov["adapter"],
        "train_manifest": prov["train_manifest"],
        "data": prov["data"],
        "sidecar": {"path": str(sidecar_path), "sha256": ev.sha256_file(sidecar_path)},
        "generation": {
            "backend": "mlx",
            "decoding": "greedy (temperature 0.0 -> argmax sampler)",
            "max_tokens": args.max_tokens,
            "prompt": "apply_chat_template([system=instruction, user=passage], add_generation_prompt=True)",
            "prompt_source": (
                "convert_to_mlx.to_messages()/render() via eval.render_prompt_token_ids(); the "
                "inference prompt is a token-exact prefix of the training sequence for the same row"
            ),
            "split": args.split,
            "limit": args.limit or None,
        },
        "journal": journal_progress(journal_path, target),
    }, run_id=args.run_id, caveats=caveats_for(args.labels_parquet))

    segment = generate(rows, args, journal_path)
    progress = journal_progress(journal_path, target)
    update_manifest(manifest_path, {"journal": progress}, segment=segment,
                    run_id=args.run_id, caveats=caveats_for(args.labels_parquet))

    if progress["complete"]:
        flag = " --v12" if args.v12 else ""
        print(
            f"\nGENERATION COMPLETE — {progress['n_rows']}/{target} rows.\n"
            f"Now run the finalize step with the SYSTEM python3 (no GPU, seconds):\n"
            f"    python3 {Path(__file__).relative_to(REPO)}{flag} --finalize-only",
            file=sys.stderr,
        )
        return 0
    print(
        f"\nPARTIAL — {progress['n_rows']}/{target} rows ({progress['pct']}%). Re-run the "
        f"IDENTICAL command to resume; finished rows are skipped.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
