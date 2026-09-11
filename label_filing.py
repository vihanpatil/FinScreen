#!/usr/bin/env python3
"""label_filing.py -- L2.2 of the APP LANE: label ONE company's store.

PRODUCT_PLAN.md P1a. `ingest_one.py` writes a per-company store; this labels its
`chunks.parquet` with **the same v1.2 student, the same adapter, the same
instruction, the same prompt renderer and the same decoding** the F4 campaign
used on the 317,081-chunk research corpus, and writes `labels.parquet` in the
F4 label schema.

WHAT IS REUSED, NOT REBUILT
---------------------------
Everything that decides what the model sees and how the answer is stored:

    label_e2.read_instruction        the frozen training system turn
    label_e2.render_prompt_ids       convert_to_mlx's own renderer, sliced at
                                     the generation-prompt offset
    label_e2.fit_prompt              the ANSWER TOKEN RESERVE (256) head-
                                     truncation, binary search, tail-only
    label_e2.prompt_input_sha        the resume identity
    label_e2.f4_label_row            the writer, including the owner-ruled
                                     guidance missing->NONE + its audit flag
    label_e2.output_schema           the 43-column F4 label schema
    eval.append_prediction           append + flush + fsync, per row
    relabel_e1.ensure_trailing_newline   torn-line repair before a resume

`label_e2.py` is IMPORTED. It is never invoked as a process, and
`label_e2.py --segment` is never run from here -- that command drives the F4
campaign's segment directories and must not be touched (F4_campaign.md §4).

THE THREE REFUSALS
------------------
1. **The repro canary.** Before the first real label on this machine, 10 rows
   of the frozen v1.2 eval split are re-generated through this code path and
   compared BYTE FOR BYTE with `runs/2026-08-28-v12-eval-epoch2/predictions.jsonl`
   -- the eval gate G1 was ruled on. Anything short of 10/10 identical and this
   module refuses to label. The verdict is cached (keyed on the adapter sha, the
   reference sha and the instruction sha), so it runs ONCE and re-runs by itself
   the moment any of those three moves.
2. **The adapter.** Its `adapters.safetensors` sha256 must equal the sha in
   `data/f4/campaign_manifest.json` -- the adapter that produced every label in
   the research corpus. A different adapter is a different model and its labels
   would not carry the measured error the report discloses.
3. **A live campaign.** If any `label_e2.py --segment` or
   `run_campaign_chain.sh` process is alive, this exits rather than share the
   GPU or risk a double-drive.

Cost: $0. No network, no API. Local GPU only.

RUN IT IN THE MLX VENV:
    finetune/.mlx_venv/bin/python label_filing.py --store data/app/companies/<cik>
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "finetune"))

import eval as ev            # noqa: E402
import label_e2 as L2        # noqa: E402
import relabel_e1 as r1      # noqa: E402

DATA_DIR = REPO_ROOT / "data"
COMPANIES_DIR = DATA_DIR / "app" / "companies"
CAMPAIGN_MANIFEST = DATA_DIR / "f4" / "campaign_manifest.json"
CANARY_STATE = DATA_DIR / "app" / "cache" / "repro_canary_app.json"

JOURNAL_NAME = "labels.jsonl"
LABELS_NAME = "labels.parquet"
MANIFEST_NAME = "label_manifest.json"

RUN_ID = "L2.2-label-filing"
CANARY_ROWS = 10

# Any of these alive means a labeling campaign owns the GPU.
CAMPAIGN_PROCESS_PATTERNS = ("run_campaign_chain.sh", "label_e2.py")


class LabelRefusal(RuntimeError):
    """A refusal with a named cause. Printed, recorded, never worked around."""


# ---------------------------------------------------------------------------
# refusal 3 -- nothing else is driving the GPU
# ---------------------------------------------------------------------------
def campaign_is_alive() -> list[str]:
    """Process command lines that look like a live F4 labeling campaign.

    This process is excluded by PID, so `label_filing.py` never sees itself.
    """
    hits = []
    try:
        out = subprocess.run(["ps", "-Ao", "pid=,command="], capture_output=True,
                             text=True, timeout=20).stdout
    except Exception:  # noqa: BLE001
        return hits
    me = str(os.getpid())
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        pid, _, command = line.partition(" ")
        if pid == me or "label_filing.py" in command:
            continue
        if any(pat in command for pat in CAMPAIGN_PROCESS_PATTERNS):
            hits.append(command.strip())
    return hits


def assert_no_campaign() -> None:
    alive = campaign_is_alive()
    if alive:
        raise LabelRefusal(
            "a labeling campaign process is alive; refusing to share the GPU "
            "(F4_campaign.md §4: never run a labeling process while "
            "run_campaign_chain.sh is alive).\n  " + "\n  ".join(alive))


# ---------------------------------------------------------------------------
# refusal 2 -- the adapter and the instruction are the campaign's
# ---------------------------------------------------------------------------
def campaign_inputs(path: Path = CAMPAIGN_MANIFEST) -> dict:
    if not path.exists():
        raise LabelRefusal(f"{path} is missing: there is nothing to pin the adapter to")
    return json.loads(path.read_text())["inputs"]


def assert_labeler_identity(adapter_path: Path, model_path: str,
                            instruction_sha: str) -> dict:
    """The adapter and system turn must be the campaign's, sha for sha."""
    want = campaign_inputs()
    prov = ev._adapter_provenance(str(adapter_path), model_path)
    got = prov["adapters_sha256"]
    if got != want["adapter_sha256_expected"]:
        raise LabelRefusal(
            "ADAPTER MISMATCH -- refusing to label.\n"
            f"  about to label with : {adapter_path}\n                        {got}\n"
            f"  the campaign used   : {want['adapter_sha256_expected']}\n"
            "These are different weights; the labels would not carry the error "
            "the report discloses.")
    if instruction_sha != want["instruction_sha256"]:
        raise LabelRefusal(
            f"INSTRUCTION MISMATCH: {instruction_sha} != the campaign's "
            f"{want['instruction_sha256']}. Refusing to label with a different "
            "system turn.")
    return {"adapter": prov, "campaign_adapter_sha256": want["adapter_sha256_expected"],
            "instruction_sha256": instruction_sha,
            "campaign_manifest": str(CAMPAIGN_MANIFEST)}


# ---------------------------------------------------------------------------
# refusal 1 -- the 10-row repro canary against the G1 eval
# ---------------------------------------------------------------------------
def canary_key(adapter_sha: str, instruction_sha: str, reference_dir: Path) -> dict:
    ref = Path(reference_dir) / "predictions.jsonl"
    return {"adapter_sha256": adapter_sha, "instruction_sha256": instruction_sha,
            "reference_predictions_sha256": ev.sha256_file(ref),
            "reference": str(ref), "n_rows": CANARY_ROWS}


def cached_canary(key: dict, state_path: Path = CANARY_STATE) -> Optional[dict]:
    """A previous PASS for exactly these three artifacts, or None.

    The canary runs ONCE (the ruling's word). "Once" is scoped to the artifacts
    it proves: move the adapter, the instruction or the reference predictions
    and the cache misses, so the proof can never outlive what it proved.
    """
    if not Path(state_path).exists():
        return None
    try:
        state = json.loads(Path(state_path).read_text())
    except Exception:  # noqa: BLE001
        return None
    if state.get("key") != key or not state.get("result", {}).get("verified"):
        return None
    return state["result"]


def run_canary(args, key: dict, state_path: Path = CANARY_STATE) -> dict:
    """`label_e2.repro_canary` -- the same function, the same reference."""
    result = L2.repro_canary(args, CANARY_ROWS)
    Path(state_path).parent.mkdir(parents=True, exist_ok=True)
    Path(state_path).write_text(json.dumps(
        {"key": key, "result": result, "ran_by": "label_filing.py",
         "checked_utc": L2.utcnow()}, indent=2) + "\n")
    return result


def ensure_canary(args, adapter_sha: str, instruction_sha: str,
                  state_path: Path = CANARY_STATE, force: bool = False) -> dict:
    key = canary_key(adapter_sha, instruction_sha, Path(args.reference_eval_dir))
    cached = None if force else cached_canary(key, state_path)
    if cached is not None:
        return {**cached, "from_cache": True}
    result = run_canary(args, key, state_path)
    if not result.get("verified"):
        raise LabelRefusal(
            "REPRO CANARY FAILED -- refusing to label a single chunk.\n"
            f"  {result.get('n_identical')}/{result.get('n_compared')} rows "
            "byte-identical to the epoch-2 v1.2 eval that gate G1 was ruled on.\n"
            f"  differing: {result.get('differing')}\n"
            "The prompt, the adapter or the decoding moved. Every label this "
            "module could write would be from a model the disclosed error "
            "numbers do not describe.")
    return {**result, "from_cache": False}


# ---------------------------------------------------------------------------
# the store
# ---------------------------------------------------------------------------
def load_store_chunks(store: Path) -> "object":
    import pyarrow.parquet as pq

    path = Path(store) / "chunks.parquet"
    if not path.exists():
        raise LabelRefusal(f"{path} is missing -- run ingest_one.py first")
    return pq.read_table(path, columns=[
        "chunk_id", "section_type", "text", "word_count", "n_paragraphs",
        "paragraph_ids", "home_cik", "home_accession_number", "home_form",
        "home_filing_date", "source_accession_numbers", "source_filing_dates",
        "source_forms", "n_source_filings", "guidance_applicable"]).to_pandas()


# ---------------------------------------------------------------------------
# generation -- label_e2.generate's loop, over a store instead of a segment
# ---------------------------------------------------------------------------
def generate(rows: list, args, journal_path: Path) -> dict:
    """One JSON answer per chunk, greedy, appended + fsync'd row by row.

    Byte-for-byte the same decode as `label_e2.generate`: the same renderer
    tokenizer from the same snapshot, the same `fit_prompt`, the same
    `make_sampler(temp=0.0)` argmax, the same `max_tokens`. Resumable: re-run
    the identical command and finished chunks are skipped.
    """
    from mlx_lm import load as mlx_load
    from mlx_lm.generate import stream_generate
    from mlx_lm.sample_utils import make_sampler
    from transformers import AutoTokenizer

    existing = ev.load_predictions(journal_path)
    todo = L2.select_rows_to_generate(rows, existing, journal_path,
                                      args.instruction_sha256)
    n_done_before = len(rows) - len(todo)
    if not todo:
        return {"n_generated": 0, "n_already_done": n_done_before,
                "note": "journal already covers every chunk in this store"}

    render_tok = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    instruction = L2.read_instruction(Path(args.mlx_data_dir))

    t_load = time.perf_counter()
    model, tokenizer = mlx_load(args.model, adapter_path=args.adapter_path)
    load_s = time.perf_counter() - t_load
    sampler = make_sampler(temp=0.0)
    repaired = r1.ensure_trailing_newline(journal_path)

    started, fresh, n_trunc = L2.utcnow(), [], 0
    t0 = time.perf_counter()
    with open(journal_path, "a") as fh:
        for i, row in enumerate(todo, 1):
            t_row = time.perf_counter()
            passage, prompt_ids, truncated, prefix_ok = L2.fit_prompt(
                render_tok, instruction, row["passage"],
                max_seq_len=args.max_seq_length, reserve=args.answer_token_reserve)
            n_trunc += int(truncated)
            text, last = "", None
            for resp in stream_generate(model, tokenizer, prompt_ids,
                                        max_tokens=args.max_tokens, sampler=sampler):
                text += resp.text
                last = resp
            rec = {
                "chunk_id": row["chunk_id"],
                "segment_id": args.segment_id,
                "raw_output": text,
                "prompt_input_sha256": row["_prompt_input_sha256"],
                "prompt_sha256": ev.sha256_text(json.dumps(prompt_ids)),
                "prompt_tokens": int(last.prompt_tokens) if last else len(prompt_ids),
                "generation_tokens": int(last.generation_tokens) if last else 0,
                "finish_reason": last.finish_reason if last else "no_response",
                "latency_s": round(time.perf_counter() - t_row, 3),
                "passage_was_head_truncated": truncated,
                "passage_chars_kept": len(passage),
                "passage_head_prefix_ok": prefix_ok,
                "generated_utc": L2.utcnow(),
            }
            ev.append_prediction(fh, rec)
            fresh.append(rec)
            if args.progress_every and (i % args.progress_every == 0 or i == len(todo)):
                elapsed = time.perf_counter() - t0
                print(f"  [{i}/{len(todo)}] {elapsed / i:.2f}s/chunk · "
                      f"ETA {(len(todo) - i) * elapsed / i / 60:.1f} min",
                      file=sys.stderr, flush=True)
    wall = time.perf_counter() - t0
    return {
        "started_utc": started, "ended_utc": L2.utcnow(),
        "n_generated": len(fresh), "n_already_done": n_done_before,
        "torn_final_line_repaired_before_append": repaired,
        "model_load_seconds": round(load_s, 1),
        "wall_seconds": round(wall, 1),
        "seconds_per_chunk": round(wall / len(fresh), 2) if fresh else None,
        "finish_reasons": dict(ev.Counter(r["finish_reason"] for r in fresh)),
        "n_passages_head_truncated": n_trunc,
    }


# ---------------------------------------------------------------------------
# the writer -- label_e2's own schema and its own row mapping
# ---------------------------------------------------------------------------
def write_labels(corpus, journal_path: Path, out_path: Path, args) -> dict:
    """journal -> labels.parquet, in the F4 label schema, columns and all."""
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    records = ev.load_predictions(journal_path)
    if not records:
        raise LabelRefusal(f"{journal_path} has no usable records")
    corpus = corpus[corpus["chunk_id"].isin(set(records))].copy()

    applicable = dict(zip(corpus["chunk_id"], corpus["guidance_applicable"]))
    label_rows = []
    for cid in corpus["chunk_id"]:
        row = L2.f4_label_row(records[cid], bool(applicable[cid]), run_id=args.run_id)
        row["chunk_id"] = cid
        row["max_tokens_used"] = args.max_tokens
        row["labeling_config"] = L2.LABELING_CONFIG.format(
            max_tokens=args.max_tokens, reserve=args.answer_token_reserve)
        row["rubric_version"] = L2.RUBRIC_VERSION
        row["system_prompt_sha256"] = args.instruction_sha256
        row["completion_batch_id"] = None
        row["home_ticker"] = None
        row["source_tickers"] = []
        label_rows.append(row)
    labels = pd.DataFrame(label_rows).set_index("chunk_id")

    df = corpus.drop(columns=["guidance_applicable"]).set_index("chunk_id").join(
        labels, how="inner").reset_index()
    schema, n_teacher, _ = L2.output_schema()
    table = pa.Table.from_pandas(df[[f.name for f in schema]], schema=schema,
                                 preserve_index=False)
    pq.write_table(table, out_path)

    ga, gi = df["guidance_applicable"], df["guidance_imputed_none"]
    return {
        "path": str(out_path), "sha256": ev.sha256_file(out_path),
        "n_rows": int(len(df)), "n_columns": len(schema),
        "schema_source": f"label_e2.output_schema() -- columns 1-{n_teacher} are "
                         "data/labels_v12.parquet's arrow schema (SCHEMA ONLY), "
                         "then the 9 F4 columns",
        "parse_failures": int((~df["parse_ok"]).sum()),
        "schema_violations": int((~df["schema_valid"]).sum()),
        "guidance": {"n_applicable": int(ga.sum()),
                     "n_imputed_none": int(gi.sum()),
                     "n_explicitly_emitted": int(
                         (df["guidance_direction"].notna() & ~gi).sum()),
                     "rule": "missing->NONE at the writer, flagged by "
                             "guidance_imputed_none"},
        "sentiment": {"n_emitted": int(df["sentiment"].notna().sum())},
        "head_truncation": {
            "n_truncated": int(df["passage_was_head_truncated"].sum()),
            "answer_token_reserve": args.answer_token_reserve,
            "prompt_token_budget": args.max_seq_length - args.answer_token_reserve},
        "red_flags_status": L2.RED_FLAGS_STATUS,
    }


# ---------------------------------------------------------------------------
# the whole thing
# ---------------------------------------------------------------------------
def build_args(store: Path, **over) -> argparse.Namespace:
    """The knobs `label_e2`'s functions read, defaulted to the campaign's."""
    ns = argparse.Namespace(
        store=Path(store),
        adapter_path=str(L2.ADAPTER),
        train_manifest=str(L2.TRAIN_MANIFEST),
        mlx_data_dir=str(L2.MLX_DATA_DIR),
        reference_eval_dir=str(L2.REFERENCE_EVAL_DIR),
        model=None,
        run_id=RUN_ID,
        segment_id=None,
        max_tokens=L2.MAX_TOKENS,
        max_seq_length=L2.MAX_SEQ_LEN,
        answer_token_reserve=L2.ANSWER_TOKEN_RESERVE,
        progress_every=25,
        instruction_sha256=None,
    )
    for key, value in over.items():
        setattr(ns, key, value)
    return ns


def label_store(store: Path, force_canary: bool = False, limit: int = 0,
                verbose: bool = True, **over) -> dict:
    t_all = time.perf_counter()
    store = Path(store)
    args = build_args(store, **over)
    args.segment_id = f"app-{store.name}"

    assert_no_campaign()

    tman = json.loads(Path(args.train_manifest).read_text())
    args.model = args.model or tman["model"]["resolved_snapshot_path"]
    instruction = L2.read_instruction(Path(args.mlx_data_dir))
    args.instruction_sha256 = ev.sha256_text(instruction)
    identity = assert_labeler_identity(Path(args.adapter_path), args.model,
                                       args.instruction_sha256)

    t = time.perf_counter()
    canary = ensure_canary(args, identity["adapter"]["adapters_sha256"],
                           args.instruction_sha256, force=force_canary)
    canary_s = time.perf_counter() - t
    if verbose:
        print(f"repro canary: {canary['n_identical']}/{canary['n_compared']} "
              f"byte-identical against the G1 eval"
              f"{' (cached)' if canary.get('from_cache') else f' ({canary_s:.0f}s)'}")

    corpus = load_store_chunks(store)
    rows = [{"chunk_id": cid, "passage": text}
            for cid, text in zip(corpus["chunk_id"], corpus["text"])]
    if limit:
        rows = rows[:limit]
        corpus = corpus.iloc[:limit].copy()

    t = time.perf_counter()
    gen = generate(rows, args, store / JOURNAL_NAME)
    generate_s = time.perf_counter() - t

    written = write_labels(corpus, store / JOURNAL_NAME, store / LABELS_NAME, args)

    manifest = {
        "run_id": RUN_ID,
        "store": str(store),
        "labeler": {
            "student": "qwen2.5-7b-finscreen-lora-mlx-v12-epoch2",
            "adapter_path": args.adapter_path,
            "adapter_sha256": identity["adapter"]["adapters_sha256"],
            "matches_campaign_adapter": True,
            "instruction_sha256": args.instruction_sha256,
            "model_snapshot": args.model,
            "rubric_version": L2.RUBRIC_VERSION,
            "decoding": "greedy temp=0.0 (argmax), max_tokens "
                        f"{args.max_tokens}, answer token reserve "
                        f"{args.answer_token_reserve}",
        },
        "repro_canary": canary,
        "generation": gen,
        "labels": written,
        "timings_seconds": {"canary_s": round(canary_s, 1),
                            "generate_s": round(generate_s, 1),
                            "total_s": round(time.perf_counter() - t_all, 1)},
        "cost_usd": 0.0,
        "anthropic_api_calls": 0,
        "caveats": L2.CAVEATS + [
            "This company is outside the 244-company research universe. Its "
            "labels have no spot-check of their own; the model-consensus error "
            "measured at G2 on the research corpus is the best case, not a "
            "measurement of this company."],
    }
    (store / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, default=str) + "\n")
    if verbose:
        print(f"{written['n_rows']} labels -> {store / LABELS_NAME}  "
              f"({generate_s:.0f}s generation, "
              f"{gen.get('seconds_per_chunk') or 0:.2f}s/chunk)")
    return manifest


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Label one company store's chunks with the v1.2 student. "
                    "Run under finetune/.mlx_venv/bin/python.")
    ap.add_argument("--store", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=0, help="first N chunks (smoke)")
    ap.add_argument("--force-canary", action="store_true",
                    help="re-run the repro canary even if a cached PASS covers "
                         "exactly these artifacts")
    args = ap.parse_args(argv)
    try:
        label_store(args.store, force_canary=args.force_canary, limit=args.limit)
    except LabelRefusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
