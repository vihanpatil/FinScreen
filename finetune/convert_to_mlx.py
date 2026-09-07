#!/usr/bin/env python3
"""
convert_to_mlx.py — render `finetune/prepared/{train,eval}.jsonl` into the
chat/messages format `mlx_lm.lora` actually accepts, for the LOCAL MLX
QLoRA path.

WHY THIS SCRIPT EXISTS
----------------------
`prepare_dataset.py` emits `{chunk_id, instruction, input, output}`, which is
deliberately framework-agnostic (`PROMPT_TEMPLATE.md`: "kept separate from any
model-specific chat-template rendering so switching base models doesn't
require re-deriving the dataset"). `mlx_lm` accepts only three shapes —
`{"messages": [...]}`, `{"prompt", "completion"}`, `{"text"}` — so a real
conversion step is required (`MLX_FEASIBILITY.md` §5.3, trap #3).

This script is that model-specific rendering step. It does NOT modify
`prepare_dataset.py` or anything under `finetune/prepared/`; it only reads
them.

THE RENDERING CONTRACT (stable — `eval.py` and any downstream inference MUST
reproduce it byte-for-byte, or training/inference consistency is broken)
-----------------------------------------------------------------------
    messages = [
        {"role": "system",    "content": <instruction, byte-identical always>},
        {"role": "user",      "content": <the raw passage text, nothing else>},
        {"role": "assistant", "content": <the target JSON string>},
    ]

Rationale for system/user (rather than concatenating instruction + input into
one user turn): this mirrors `build_batch_requests.py::build_request`, which
put the fixed instruction in `system` and the raw passage — "and nothing
else" — in the single `user` message. `PROMPT_TEMPLATE.md` states the
fine-tuning prompt is deliberately built the same way as the labeling prompt
rather than re-derived. Keeping the roles split also honours
`PROMPT_TEMPLATE.md`'s rule that `input` is the passage with nothing
"appended or prepended" — no separator string is invented — and it suppresses
Qwen's default "You are Qwen, created by Alibaba Cloud" system prompt, which
the chat template injects only when `messages[0]["role"] != "system"`.

At inference time the equivalent is `apply_chat_template(messages[:2],
add_generation_prompt=True)` with the identical instruction string.

LOOK-AHEAD-BIAS SAFETY: this script is a pure re-serialization. It adds no
text of its own to either message. No ticker, CIK, filing date, section_type
string, or outcome framing can enter here that was not already excluded by
`prepare_dataset.py` — and an assertion below re-checks that the system
message is byte-identical across every record.

THE TAIL-TRUNCATION TRAP (`MLX_FEASIBILITY.md` §2.3, trap #2)
-------------------------------------------------------------
`mlx_lm/tuner/trainer.py::iterate_batches` truncates over-length sequences
from the END (`batch_arr[j, :truncated_length] = batch[j][:truncated_length]`),
emitting only a `[WARNING]`. Our answer is the LAST ~30 tokens, so a
truncated row is not merely shortened — its target JSON is amputated, and
with `mask_prompt: true` the loss mask then covers the tail of the *prompt*
instead of the answer. Silent label corruption.

This script prevents that by pre-truncating the PASSAGE TEXT ONLY (keeping
its head, dropping its tail) until the fully-rendered sequence fits
`--max-seq-length`. The instruction is never touched. The answer is never
touched. Every emitted record is then re-tokenized and asserted to (a) fit
the cap and (b) still contain its complete answer inside the loss-bearing
region. The trainer's truncation path is therefore never reached.

Run:
    python3 convert_to_mlx.py --model <path-or-repo> [--max-seq-length 2048]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREPARED_DIR = HERE / "prepared"
DEFAULT_OUT_DIR = HERE / "mlx_data"

# prepared/<side>.jsonl  ->  mlx_data/<name>.jsonl
# NOTE the rename: mlx_lm looks for train.jsonl / valid.jsonl / test.jsonl in a
# directory. Our held-out split is called "eval"; mlx_lm calls it "valid".
# Same rows, different filename. (MLX_FEASIBILITY.md §5.2.)
SIDE_TO_MLX_NAME = {"train": "train", "eval": "valid"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def to_messages(instruction: str, passage: str, answer: str) -> list[dict]:
    """THE rendering contract. See module docstring."""
    return [
        {"role": "system", "content": instruction},
        {"role": "user", "content": passage},
        {"role": "assistant", "content": answer},
    ]


def render(tokenizer, messages: list[dict]) -> tuple[list[int], int]:
    """Reproduce mlx_lm.tuner.datasets.ChatDataset.process(mask_prompt=True)
    exactly, so what we measure here is what the trainer will actually see.

    Returns (token_ids, prompt_offset). Loss is computed on
    token_ids[prompt_offset:].
    """
    tokens = tokenizer.apply_chat_template(messages, tools=None, return_dict=False)
    offset = len(
        tokenizer.apply_chat_template(
            messages[:-1], tools=None, add_generation_prompt=True, return_dict=False
        )
    )
    return list(tokens), offset


def fit_passage(tokenizer, instruction: str, passage: str, answer: str, max_len: int):
    """Return (possibly head-truncated) passage text whose rendered sequence
    fits `max_len`. Binary-searches on the passage's own token prefix length.

    Only the passage is ever shortened. Never the instruction, never the
    answer.
    """
    tokens, _ = render(tokenizer, to_messages(instruction, passage, answer))
    if len(tokens) <= max_len:
        return passage, len(tokens), False

    ids = tokenizer.encode(passage, add_special_tokens=False)
    lo, hi = 0, len(ids)  # invariant: lo fits (checked below), hi does not
    # Confirm the degenerate floor is feasible before searching.
    empty_tokens, _ = render(tokenizer, to_messages(instruction, "", answer))
    if len(empty_tokens) > max_len:
        raise RuntimeError(
            f"instruction + answer alone render to {len(empty_tokens)} tokens, "
            f"which already exceeds max_seq_length={max_len}. Nothing can be "
            f"truncated safely; raise max_seq_length."
        )
    best_text, best_len = "", len(empty_tokens)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        cand = tokenizer.decode(ids[:mid])
        t, _ = render(tokenizer, to_messages(instruction, cand, answer))
        if len(t) <= max_len:
            lo, best_text, best_len = mid, cand, len(t)
        else:
            hi = mid - 1
    return best_text, best_len, True


def convert(tokenizer, max_len: int, out_dir: Path, prepared_dir: Path = PREPARED_DIR,
            limit: int | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"max_seq_length": max_len, "prepared_dir": str(prepared_dir), "splits": {}}
    chunk_ids_by_side: dict[str, list[str]] = {}
    instruction_seen: set[str] = set()

    for side, mlx_name in SIDE_TO_MLX_NAME.items():
        src = prepared_dir / f"{side}.jsonl"
        if not src.exists():
            raise FileNotFoundError(
                f"{src} not found — run prepare_dataset.py first (it is NOT run by this script)"
            )
        dst = out_dir / f"{mlx_name}.jsonl"

        rows = [json.loads(line) for line in open(src)]
        if limit is not None:
            rows = rows[:limit]
        n_truncated = 0
        truncated_detail = []
        tok_lengths: list[int] = []
        completion_lengths: list[int] = []
        chunk_ids: list[str] = []

        with open(dst, "w") as out:
            for i, rec in enumerate(rows):
                instruction_seen.add(rec["instruction"])
                passage, n_tok, was_trunc = fit_passage(
                    tokenizer, rec["instruction"], rec["input"], rec["output"], max_len
                )
                messages = to_messages(rec["instruction"], passage, rec["output"])

                # --- per-record verification: the answer MUST survive ---
                tokens, offset = render(tokenizer, messages)
                assert len(tokens) == n_tok, f"{side}[{i}]: render is not deterministic"
                assert len(tokens) <= max_len, (
                    f"{side}[{i}] chunk={rec['chunk_id']}: {len(tokens)} tokens > "
                    f"max_seq_length={max_len} after truncation"
                )
                assert offset < len(tokens), (
                    f"{side}[{i}] chunk={rec['chunk_id']}: empty loss mask "
                    f"(offset {offset} >= length {len(tokens)})"
                )
                completion_text = tokenizer.decode(tokens[offset:])
                assert rec["output"] in completion_text, (
                    f"{side}[{i}] chunk={rec['chunk_id']}: the target JSON does NOT "
                    f"survive intact in the loss-bearing region — this is exactly the "
                    f"tail-truncation trap. Got: {completion_text!r}"
                )

                if was_trunc:
                    n_truncated += 1
                    truncated_detail.append(
                        {
                            "chunk_id": rec["chunk_id"],
                            "passage_chars_before": len(rec["input"]),
                            "passage_chars_after": len(passage),
                            "rendered_tokens_after": len(tokens),
                        }
                    )
                tok_lengths.append(len(tokens))
                completion_lengths.append(len(tokens) - offset)
                chunk_ids.append(rec["chunk_id"])

                out.write(
                    json.dumps(
                        {"chunk_id": rec["chunk_id"], "messages": messages},
                        ensure_ascii=False,
                    )
                    + "\n"
                )

        chunk_ids_by_side[side] = chunk_ids
        q = statistics.quantiles(tok_lengths, n=100, method="inclusive")
        report["splits"][side] = {
            "source_file": str(src),
            "source_sha256": sha256_file(src),
            "output_file": str(dst),
            "output_sha256": sha256_file(dst),
            "n_examples": len(rows),
            "n_passage_truncated": n_truncated,
            "truncated": truncated_detail,
            "rendered_tokens": {
                "mean": round(statistics.fmean(tok_lengths), 1),
                "p50": round(q[49]),
                "p95": round(q[94]),
                "p99": round(q[98]),
                "max": max(tok_lengths),
                "total": sum(tok_lengths),
            },
            "loss_bearing_tokens": {
                "mean": round(statistics.fmean(completion_lengths), 1),
                "max": max(completion_lengths),
                "total": sum(completion_lengths),
            },
        }

    # --- corpus-level assertions ---
    assert len(instruction_seen) == 1, (
        f"instruction is NOT byte-identical across records ({len(instruction_seen)} "
        f"distinct values) — PROMPT_TEMPLATE.md requires exactly one"
    )
    instruction = next(iter(instruction_seen))
    report["instruction"] = {
        "sha256": hashlib.sha256(instruction.encode()).hexdigest(),
        "chars": len(instruction),
        "byte_identical_across_all_rows": True,
        "source": "prepare_dataset.py::INSTRUCTION — the TRAINING instruction, "
                  "frozen across E1 and the v1.2 retrain",
    }
    if limit is not None:
        report["SMOKE_RUN"] = (
            f"limit={limit} — the first {limit} rows of each split only. "
            f"NOT a training artifact; row counts and hashes are not the real ones."
        )
    train_ids = set(chunk_ids_by_side["train"])
    eval_ids = set(chunk_ids_by_side["eval"])
    overlap = train_ids & eval_ids
    assert not overlap, f"LEAKAGE: {len(overlap)} chunk_ids appear in both splits: {sorted(overlap)[:5]}"
    assert len(train_ids) == len(chunk_ids_by_side["train"]), "duplicate chunk_ids in train"
    assert len(eval_ids) == len(chunk_ids_by_side["eval"]), "duplicate chunk_ids in eval"
    report["leakage_check"] = {
        "train_chunk_ids": len(train_ids),
        "eval_chunk_ids": len(eval_ids),
        "intersection": 0,
        "instruction_byte_identical": True,
    }
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help="Local model dir or HF repo id (tokenizer source)")
    ap.add_argument("--max-seq-length", type=int, default=2048)
    ap.add_argument("--prepared-dir", default=str(PREPARED_DIR),
                    help="Where prepare_dataset.py wrote {train,eval}.jsonl "
                         "(finetune/prepared_v12 for the rubric-v1.2 retrain)")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    ap.add_argument("--expect-train", type=int, default=5736)
    ap.add_argument("--expect-eval", type=int, default=1010)
    ap.add_argument("--limit", type=int, default=None,
                    help="SMOKE ONLY: convert the first N rows of each split. "
                         "Disables the row-count check and stamps the report SMOKE_RUN.")
    ap.add_argument("--report", default=None, help="Write the JSON report here as well as stdout")
    args = ap.parse_args()

    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    report = convert(tokenizer, args.max_seq_length, Path(args.out_dir),
                     Path(args.prepared_dir), args.limit)
    report["tokenizer_source"] = args.model

    n_train = report["splits"]["train"]["n_examples"]
    n_eval = report["splits"]["eval"]["n_examples"]
    if args.limit is not None:
        print(f"SMOKE RUN: limit={args.limit}; row-count check skipped.", file=sys.stderr)
    elif n_train != args.expect_train or n_eval != args.expect_eval:
        print(
            f"FATAL: row counts changed — train {n_train} (expected {args.expect_train}), "
            f"eval {n_eval} (expected {args.expect_eval})",
            file=sys.stderr,
        )
        sys.exit(1)

    out = json.dumps(report, indent=2)
    print(out)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(out)
    print(
        f"\nOK: {n_train} train / {n_eval} valid rows written to {args.out_dir}; "
        f"every answer verified intact inside the loss mask.",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
