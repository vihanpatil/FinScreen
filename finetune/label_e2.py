#!/usr/bin/env python3
"""
label_e2.py — the F4 labeling runner: the v1.2 student labels the E2 corpus.

WHY A SIBLING OF relabel_e1.py AND NOT AN `--f4` PROFILE
-------------------------------------------------------
`relabel_e1.py`'s `--v12` profile swaps eight PATHS while every function keeps
its shape. F4 changes the shapes, in four ways that would each need a branch
inside a module whose 36 tests pin a RULED record (H3/H3v2) byte-for-byte:

  1. There is no gold answer. `read_mlx_rows`, `write_sidecar` and
     `load_rows` all require `[system, user, assistant]` records and score
     against them; `render_prompt_token_ids` asserts the stored messages.
     F4 renders from raw corpus text with a fixed ANSWER TOKEN RESERVE.
  2. There is no teacher. No agreement summary, no reproduction check over the
     same rows (F4 gets a separate E1-eval reproduction canary instead, §
     `--repro-canary`).
  3. `TARGET_ROWS = 6746` is asserted. F4 is 317,081 rows over ~22 nights.
  4. **missing->NONE is ADOPTED at the F4 writer** (owner, 2026-08-27). In
     `relabel_e1.py` the same rule is explicitly "PROPOSED, NOT ADOPTED" and
     the raw value is stored — flipping that behaviour inside the shared
     function is how a ruled artifact gets silently rewritten.

So `relabel_e1.py` is imported and REUSED, not forked: the journal +
fsync + torn-line repair, the manifest updater, the taxonomy-safe label
mapping, the teacher-schema copy and the progress/throughput blocks are all
its functions, called from here. Nothing in `relabel_e1.py` or `eval.py` was
edited.

WHAT THE OWNER RULED (HANDOFF §3, 2026-08-27 "F4 CONFIG RULED", re-confirmed
post-demotion the same night)
---------------------------------------------------------------------------
  * window rule **W1 core**, **full reflow_v1** -> `data/f4/chunks_v1.parquet`
    (`build_f4_chunks.py`; 317,081 chunks recomputed from P5's corpus).
  * guidance **missing->NONE ADOPTED AT THE LABELING WRITER, WITH AN AUDIT
    FLAG** (eval report `2026-08-22-eval-epoch2/eval_report.md` A.7). The
    stored label says `NONE`; `guidance_imputed_none = true` says the model
    omitted the key. Never silent, always reversible.
  * `red_flags` is produced under **EXPLORATORY / DISCLOSURE-ONLY** status —
    the owner-ratified DEMOTE pre-commitment fired on the v1.2 spot-check
    (teacher red-flag exact-set error 42.00% [35.37, 48.93]). The status is
    written into the parquet's schema metadata and every manifest.

THE PROMPT — token-exact, by construction
-----------------------------------------
`convert_to_mlx.to_messages()` + `convert_to_mlx.render()`, sliced at the
generation-prompt offset (`render_prompt_ids` below). system = the frozen
training instruction `ebc45a85…` byte-identical / user = the passage /
nothing appended. Look-ahead-safe: no ticker, no CIK, no company name, no
date, no section_type, no outcome ever enters the prompt.

THE ANSWER TOKEN RESERVE (the H3 §1.6 extension point, built here)
------------------------------------------------------------------
At training time `convert_to_mlx.fit_passage` head-truncated the passage so
that instruction + passage + THE ACTUAL ANSWER fits `max_seq_length = 2048`.
At labeling time there is no answer, so a fixed reserve replaces it:

    prompt token budget = 2048 - ANSWER_TOKEN_RESERVE (256) = 1792

chosen from the MEASURED generation lengths of this exact student:
6,746-row H3v2 relabel mean 34.8 / p99.9 130 / max 151, the 1,010-row v1.2
epoch-2 eval mean 36.7 / max 151, and the training targets' own loss-bearing
region max 152. 256 is 1.68x the largest answer ever observed or trained on.
The reserve is a LENGTH-REGIME guarantee, not a cap: generation still runs to
`max_tokens 520`, so an answer longer than the reserve is produced, not
truncated — it just extends past 2,048 positions, which is why the reserve is
set well clear of the observed maximum.

Head truncation uses `convert_to_mlx.fit_passage`'s own method (binary search
on the passage's own token prefix, tail dropped, instruction never touched)
and every truncated row is flagged in the parquet.

RESUME SEMANTICS (HANDOFF §4 — the auto-resume chain)
-----------------------------------------------------
Never launch generation from a subagent shell. One SEGMENT = one night = one
run directory with its own journal and manifest. Every row is appended and
fsync'd before the next starts, so a kill loses at most the in-flight row
(~2.5 s). Re-run the IDENTICAL command to resume; finished rows are skipped, a
torn final line is repaired before appending, and every row stores the sha256
of the exact prompt token sequence it came from. Exit 0 = segment complete,
2 = partial (resume).

TWO INTERPRETERS, ON PURPOSE (exactly as relabel_e1.py)
------------------------------------------------------
  `--plan`, `--prepare-segment`, `--finalize-*`  -> SYSTEM python3 (pyarrow)
  `--segment`, `--repro-canary`                  -> finetune/.mlx_venv (mlx)

$0. Zero Anthropic API calls. Zero network.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import eval as ev            # noqa: E402  scoring/provenance helpers
import relabel_e1 as r1      # noqa: E402  journal + manifest + writer primitives

# --- frozen inputs (all READ-ONLY) -----------------------------------------
CHUNKS_PARQUET = REPO / "data" / "f4" / "chunks_v1.parquet"
CHUNKS_SHA256 = "d67395ece6126045e851e05f4b8fe5c8c49bd69069c44a08b9ee8f9d67bf0857"
CHUNKS_MANIFEST = REPO / "data" / "f4" / "chunks_v1_manifest.json"
CORPUS_SHA256 = "15853e9f54902a933f0372869209a353ab3f052cb5c7dc1f897297f75b53f417"

MLX_DATA_DIR = HERE / "mlx_data_v12"
LABELS_V12 = REPO / "data" / "labels_v12.parquet"   # SCHEMA TEMPLATE ONLY, never a teacher
TRAIN_MANIFEST = HERE / "runs" / "2026-08-27-v12-epoch2" / "manifest.json"
ADAPTER = HERE / "checkpoints" / "qwen2.5-7b-finscreen-lora-mlx-v12-epoch2"
REFERENCE_EVAL_DIR = HERE / "runs" / "2026-08-28-v12-eval-epoch2"

INSTRUCTION_SHA256 = "ebc45a856bff58a562535867e5a1f4173519fe77c58a47b16bfa28e6eea8efe2"
ADAPTER_SHA256 = "cadca8499b66b2e7d60a161f2021a5c5dac51ddd3a0bccea52d055cefb159de3"

# --- outputs ---------------------------------------------------------------
F4_DIR = REPO / "data" / "f4"
SEGMENTS_DIR = F4_DIR / "segments"
PLAN_PATH = F4_DIR / "campaign_plan.json"
CAMPAIGN_MANIFEST = F4_DIR / "campaign_manifest.json"
CAMPAIGN_PARQUET = F4_DIR / "labels_e2_v1.parquet"
CANARY_PATH = F4_DIR / "repro_canary.json"

ROWS_NAME = "rows.jsonl"
JOURNAL_NAME = "labels.jsonl"
MANIFEST_NAME = "manifest.json"

RUN_ID = "F4-e2-label-v1"
RUBRIC_VERSION = "v1.2"
MAX_SEQ_LEN = 2048
ANSWER_TOKEN_RESERVE = 256
MAX_TOKENS = 520
# ~9.4 h of labeling at the PROJECTED 1,412 chunks/h (see data/f4/RUN_COMMANDS.md
# §6): a night's work with margin, so a segment normally finishes inside one
# slot and a kill costs a resume, not a re-plan.
DEFAULT_SEGMENT_ROWS = 13500

LABELING_CONFIG = (
    "student=qwen2.5-7b-finscreen-lora-mlx-v12-epoch2,backend=mlx,"
    "decoding=greedy(temp=0.0),max_tokens={max_tokens},"
    "answer_token_reserve={reserve},guidance_missing_to_none=writer"
)

RED_FLAGS_STATUS = (
    "EXPLORATORY / DISCLOSURE-ONLY. The owner-ratified DEMOTE pre-commitment fired on "
    "the v1.2 spot-check (2026-08-27, HANDOFF §3): the v1.2 TEACHER's red-flag exact-set "
    "error is 84/200 = 42.00% [35.37, 48.93]. These student red_flags reproduce a teacher "
    "measured at that error rate. They are not a confirmatory feature family in G3."
)

CAVEATS = [
    RED_FLAGS_STATUS,
    "These labels are the STUDENT's, produced locally on MLX. They are not Claude labels "
    "and they were never validated against human ground truth. The student's held-out "
    "agreement with its own v1.2 teacher (n=1,010) is: sentiment 0.836, red_flags "
    "exact-set 0.631 / micro F1 0.795, guidance 0.521 raw. Agreement is not accuracy.",
    "guidance_direction: missing->NONE is APPLIED AT THIS WRITER (owner-ruled 2026-08-27), "
    "scoped to guidance-APPLICABLE section types only (EX99_PRESS_RELEASE, 8K_BODY — the "
    "section types the teacher's own JSON schema asked for the field). Every imputed row "
    "carries guidance_imputed_none=true. An explicitly emitted NONE carries false. The "
    "underlying omission rate WORSENED between epochs (321 -> 385 of 6,746 on E1), which is "
    "the disclosed cost of adopting the rule.",
    "distress_tier was never a training target (HANDOFF §7). The column is uniformly empty "
    "for schema compatibility and carries no information.",
    "8K_BODY (n=790 chunks here) is not evaluable as a class — E1 had 8 such chunks from 2 "
    "tickers and the student has effectively no supervision for it (HANDOFF §7). Do not "
    "report a per-class metric on it.",
    "Window rule W1-core: the corpus was restricted to stratum=='core' BEFORE dedup, so a "
    "chunk's source_* back-references cover core-stratum sections only. The extension "
    "stratum is unlabeled this round.",
    "The four population-gate columns in the F3 corpus are NOT point-in-time (P4 §5.1 / P5 "
    "§8.2): they may be set by a LATER-dated filing. Use them for triage, never for "
    "conditioning in a walk-forward.",
    "Passages are head-truncated to fit 2048 tokens including a fixed 256-token answer "
    "reserve. Truncated rows carry passage_was_head_truncated=true; only the passage TAIL "
    "is ever dropped.",
    "E1's data/labels.parquet and data/labels_v12.parquet are frozen and were opened "
    "READ-ONLY (the latter only as an arrow SCHEMA TEMPLATE, never as a teacher for these "
    "rows).",
]


def utcnow() -> str:
    return r1.utcnow()


# ===========================================================================
# the prompt — no answer, fixed reserve
# ===========================================================================

def render_prompt_ids(tokenizer, instruction: str, passage: str) -> list:
    """THE F4 inference prompt, reusing convert_to_mlx.py's own code.

    `convert_to_mlx.render` returns (all_ids, prompt_offset) where
    `prompt_offset = len(apply_chat_template(messages[:-1],
    add_generation_prompt=True))`, so `all_ids[:offset]` is the inference
    prompt and it is byte-identical to the prefix the trainer saw. The
    assistant turn is a placeholder that is sliced away before it is used —
    the prompt cannot depend on it, and `test_label_e2.py` asserts on real E1
    rows that this function reproduces `eval.render_prompt_token_ids` (the
    answer-bearing path) token for token.
    """
    import convert_to_mlx as c2m

    all_ids, offset = c2m.render(tokenizer, c2m.to_messages(instruction, passage, ""))
    if not (0 < offset <= len(all_ids)):
        raise AssertionError(f"nonsensical prompt offset {offset} / {len(all_ids)}")
    return list(all_ids[:offset])


def fit_prompt(tokenizer, instruction: str, passage: str,
               max_seq_len: int = MAX_SEQ_LEN, reserve: int = ANSWER_TOKEN_RESERVE):
    """Head-truncate the PASSAGE until the prompt fits `max_seq_len - reserve`.

    Same method as `convert_to_mlx.fit_passage` (binary search on the
    passage's own token prefix; only the TAIL is ever dropped; the instruction
    is never touched), with the answer replaced by a fixed reserve because
    there is no answer at labeling time.

    Returns (passage, prompt_ids, was_truncated, head_prefix_ok).
    """
    budget = max_seq_len - reserve
    ids = render_prompt_ids(tokenizer, instruction, passage)
    if len(ids) <= budget:
        return passage, ids, False, True

    ptok = tokenizer.encode(passage, add_special_tokens=False)
    empty = render_prompt_ids(tokenizer, instruction, "")
    if len(empty) > budget:
        raise SystemExit(
            f"the instruction alone renders to {len(empty)} prompt tokens, over the "
            f"{budget}-token budget (max_seq_len {max_seq_len} - reserve {reserve}). "
            f"Nothing can be truncated safely."
        )
    lo, hi = 0, len(ptok)
    best_text, best_ids = "", empty
    while lo < hi:
        mid = (lo + hi + 1) // 2
        cand = tokenizer.decode(ptok[:mid])
        cand_ids = render_prompt_ids(tokenizer, instruction, cand)
        if len(cand_ids) <= budget:
            lo, best_text, best_ids = mid, cand, cand_ids
        else:
            hi = mid - 1
    return best_text, best_ids, True, passage.startswith(best_text)


# ===========================================================================
# step 0 — the campaign plan (SYSTEM python3)
# ===========================================================================

def read_instruction(mlx_dir: Path = MLX_DATA_DIR, verify_all: bool = False) -> str:
    """The frozen training instruction, read from the rendered training data.

    stdlib only, so the GPU step can do this too. `verify_all` re-asserts
    byte-identity across all 6,746 rendered rows (the `--plan` step does that
    once; the generate step checks the sha, which is equivalent and instant).
    """
    seen, first = set(), None
    paths = [mlx_dir / "train.jsonl"] + ([mlx_dir / "valid.jsonl"] if verify_all else [])
    for path in paths:
        with open(path) as f:
            for line in f:
                instr = json.loads(line)["messages"][0]["content"]
                if first is None:
                    first = instr
                if verify_all:
                    seen.add(instr)
                else:
                    break
    if verify_all and len(seen) != 1:
        raise AssertionError(
            f"the training instruction is NOT byte-identical across the rendered rows "
            f"({len(seen)} distinct values). PROMPT_TEMPLATE.md requires exactly one."
        )
    return first


def segment_bounds(accessions: list, segment_rows: int) -> list:
    """Contiguous row ranges, cut on `home_accession_number` boundaries.

    Contiguous (not round-robin) so that a campaign stopped early yields
    COMPLETE FILINGS: filing-level features aggregate over every chunk
    attributed to a filing, so a partially-labeled filing is a silently biased
    filing. Accession-aligned so no filing is ever split across two nights.
    """
    n = len(accessions)
    n_segments = max(1, math.ceil(n / segment_rows))
    target = math.ceil(n / n_segments)
    bounds, start = [], 0
    while start < n:
        end = min(start + target, n)
        while end < n and accessions[end] == accessions[end - 1]:
            end += 1              # never split a filing across nights
        bounds.append((start, end))
        start = end
    return bounds


def build_plan(segment_rows: int = DEFAULT_SEGMENT_ROWS, out_path: Path = PLAN_PATH) -> dict:
    import pyarrow.parquet as pq

    for path, expected, what in (
        (CHUNKS_PARQUET, CHUNKS_SHA256, "F4 chunk table"),
        (LABELS_V12, "", "v1.2 schema template"),
    ):
        if not path.exists():
            raise SystemExit(f"{what} not found: {path}")
    actual = ev.sha256_file(CHUNKS_PARQUET)
    if actual != CHUNKS_SHA256:
        raise SystemExit(
            f"CHUNK TABLE MISMATCH — refusing to plan.\n  {CHUNKS_PARQUET}\n"
            f"  expected {CHUNKS_SHA256}\n  actual   {actual}\n"
            f"Re-run finetune/build_f4_chunks.py, or the corpus moved (HANDOFF §7)."
        )
    cman = json.loads(CHUNKS_MANIFEST.read_text())
    if cman["corpus"]["sha256"] != CORPUS_SHA256:
        raise SystemExit(
            f"the chunk table was built from corpus sha {cman['corpus']['sha256']}, not the "
            f"pinned P5 corpus {CORPUS_SHA256}."
        )

    instruction = read_instruction(verify_all=True)
    instr_sha = ev.sha256_text(instruction)
    if instr_sha != INSTRUCTION_SHA256:
        raise SystemExit(
            f"training instruction sha {instr_sha} != the frozen {INSTRUCTION_SHA256}."
        )

    tbl = pq.read_table(CHUNKS_PARQUET, columns=["chunk_id", "section_type",
                                                 "home_accession_number"])
    chunk_ids = tbl["chunk_id"].to_pylist()
    if len(set(chunk_ids)) != len(chunk_ids):
        raise SystemExit("duplicate chunk_id in the F4 chunk table — refusing to plan.")
    accs = tbl["home_accession_number"].to_pylist()
    sects = tbl["section_type"].to_pylist()
    bounds = segment_bounds(accs, segment_rows)

    segments = []
    for i, (lo, hi) in enumerate(bounds, 1):
        counts = {}
        for s in sects[lo:hi]:
            counts[s] = counts.get(s, 0) + 1
        segments.append({
            "segment_id": f"seg-{i:03d}",
            "row_start": lo,
            "row_end": hi,
            "n_rows": hi - lo,
            "first_chunk_id": chunk_ids[lo],
            "last_chunk_id": chunk_ids[hi - 1],
            "n_accessions": len(set(accs[lo:hi])),
            "by_section_type": counts,
            "chunk_id_list_sha256": ev.sha256_text("\n".join(chunk_ids[lo:hi])),
            "dir": str(SEGMENTS_DIR / f"seg-{i:03d}"),
        })

    plan = {
        "run_id": RUN_ID,
        "created_utc": utcnow(),
        "cost_usd": 0.0,
        "anthropic_api_calls": 0,
        "owner_rulings": {
            "window_rule": "W1_core (HANDOFF §3 2026-08-27, re-confirmed post-demotion)",
            "line_rule": "reflow_v1 (full)",
            "guidance_missing_to_none": "ADOPTED AT THE LABELING WRITER, with the "
                                        "guidance_imputed_none audit flag (eval A.7)",
            "red_flags_status": RED_FLAGS_STATUS,
        },
        "inputs": {
            "chunks_parquet": {"path": str(CHUNKS_PARQUET), "sha256": actual,
                               "n_rows": len(chunk_ids)},
            "corpus_parquet_sha256": CORPUS_SHA256,
            "chunks_manifest": {"path": str(CHUNKS_MANIFEST),
                                "sha256": ev.sha256_file(CHUNKS_MANIFEST)},
            "instruction_sha256": instr_sha,
            "instruction_chars": len(instruction),
            "mlx_data_dir": str(MLX_DATA_DIR),
            "train_jsonl_sha256": ev.sha256_file(MLX_DATA_DIR / "train.jsonl"),
            "valid_jsonl_sha256": ev.sha256_file(MLX_DATA_DIR / "valid.jsonl"),
            "adapter_path": str(ADAPTER),
            "adapter_sha256_expected": ADAPTER_SHA256,
            "train_manifest": str(TRAIN_MANIFEST),
            "reference_eval_dir": str(REFERENCE_EVAL_DIR),
            "schema_template": {"path": str(LABELS_V12), "sha256": ev.sha256_file(LABELS_V12),
                                "role": "ARROW SCHEMA ONLY — never a teacher for these rows"},
        },
        "generation": {
            "backend": "mlx",
            "decoding": "greedy (temperature 0.0 -> argmax sampler)",
            "max_tokens": MAX_TOKENS,
            "max_seq_length": MAX_SEQ_LEN,
            "answer_token_reserve": ANSWER_TOKEN_RESERVE,
            "prompt_token_budget": MAX_SEQ_LEN - ANSWER_TOKEN_RESERVE,
            "prompt": "apply_chat_template([system=instruction, user=passage], "
                      "add_generation_prompt=True)",
            "prompt_source": "convert_to_mlx.to_messages()/render() via "
                             "label_e2.render_prompt_ids(); token-exact prefix of the "
                             "training sequence rendering",
        },
        "segmentation": {
            "rule": "contiguous corpus-order row ranges, cut on home_accession_number "
                    "boundaries so no filing is split across nights",
            "target_segment_rows": segment_rows,
            "n_segments": len(segments),
        },
        "segments": segments,
        "caveats": CAVEATS,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, indent=2) + "\n")
    return plan


def read_chunk_rows(columns: list, row_start: int, n_rows: int):
    """The chunk table's rows [row_start, row_start+n_rows), as an arrow table.

    Streamed, not sliced: `pq.read_table(...).slice(...)` would materialise all
    317,081 rows (and the 390 MB text column) to hand back 15,000 of them.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    stop = row_start + n_rows
    pf = pq.ParquetFile(CHUNKS_PARQUET)
    out, pos = [], 0
    for batch in pf.iter_batches(batch_size=2000, columns=columns):
        lo, hi = pos, pos + batch.num_rows
        pos = hi
        if hi <= row_start:
            continue
        if lo >= stop:
            break
        out.append(batch.slice(max(0, row_start - lo), min(hi, stop) - max(lo, row_start)))
    table = pa.Table.from_batches(out) if out else None
    if table is None or table.num_rows != n_rows:
        raise SystemExit(
            f"chunk table gave {0 if table is None else table.num_rows} rows for "
            f"[{row_start}, {stop}) — expected {n_rows}."
        )
    return table


def load_plan(path: Path = PLAN_PATH) -> dict:
    if not Path(path).exists():
        raise SystemExit(
            f"{path} not found. Run the plan step FIRST, with the system python3:\n"
            f"    python3 finetune/label_e2.py --plan"
        )
    return json.loads(Path(path).read_text())


def segment_spec(plan: dict, segment: str) -> dict:
    key = segment if segment.startswith("seg-") else f"seg-{int(segment):03d}"
    for s in plan["segments"]:
        if s["segment_id"] == key:
            return s
    raise SystemExit(f"{key} is not in the plan ({len(plan['segments'])} segments).")


# ===========================================================================
# step 1 — prepare a segment's rows (SYSTEM python3)
# ===========================================================================

def prepare_segment(plan: dict, spec: dict, out_dir: Path = None) -> dict:
    """Materialise the segment's rows as stdlib-readable JSONL.

    The GPU interpreter has no pandas/pyarrow, so the parquet is turned into a
    plain JSONL here — the same split of labour `relabel_e1.py` uses between
    its sidecar step and its generate step.
    """
    out_dir = Path(out_dir or spec["dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_path = out_dir / ROWS_NAME

    tbl = read_chunk_rows(
        ["chunk_id", "section_type", "text", "guidance_applicable"],
        spec["row_start"], spec["n_rows"],
    ).to_pydict()

    if tbl["chunk_id"][0] != spec["first_chunk_id"] or tbl["chunk_id"][-1] != spec["last_chunk_id"]:
        raise SystemExit(
            f"{spec['segment_id']}: the chunk table's rows do not match the plan "
            f"(first/last chunk_id). The chunk table moved under the plan."
        )
    with open(rows_path, "w") as f:
        for i in range(spec["n_rows"]):
            f.write(json.dumps({
                "chunk_id": tbl["chunk_id"][i],
                "section_type": tbl["section_type"][i],
                "guidance_applicable": bool(tbl["guidance_applicable"][i]),
                "passage": tbl["text"][i],
            }, ensure_ascii=False) + "\n")

    ids_sha = ev.sha256_text("\n".join(tbl["chunk_id"]))
    if ids_sha != spec["chunk_id_list_sha256"]:
        raise SystemExit(f"{spec['segment_id']}: chunk_id list sha mismatch vs the plan.")
    return {
        "segment_id": spec["segment_id"],
        "rows_jsonl": str(rows_path),
        "rows_jsonl_sha256": ev.sha256_file(rows_path),
        "n_rows": spec["n_rows"],
        "chunk_id_list_sha256": ids_sha,
        "prepared_utc": utcnow(),
    }


def load_rows(out_dir: Path, spec: dict, limit: int = 0) -> list:
    rows_path = Path(out_dir) / ROWS_NAME
    if not rows_path.exists():
        raise SystemExit(
            f"{rows_path} not found. Run, with the system python3:\n"
            f"    python3 finetune/label_e2.py --prepare-segment {spec['segment_id']}"
        )
    rows = [json.loads(line) for line in open(rows_path) if line.strip()]
    if len(rows) != spec["n_rows"]:
        raise SystemExit(
            f"{rows_path} has {len(rows)} rows, the plan says {spec['n_rows']}."
        )
    ids_sha = ev.sha256_text("\n".join(r["chunk_id"] for r in rows))
    if ids_sha != spec["chunk_id_list_sha256"]:
        raise SystemExit(
            f"{rows_path}: chunk_id list sha {ids_sha} != the plan's "
            f"{spec['chunk_id_list_sha256']}. Re-run --prepare-segment."
        )
    return rows[:limit] if limit else rows


# ===========================================================================
# preflight — everything that can fail, fails before the GPU is touched
# ===========================================================================

def preflight(args, plan: dict, spec: dict, n_rows: int) -> dict:
    tman_path = Path(args.train_manifest)
    if not tman_path.exists():
        raise FileNotFoundError(f"training manifest not found: {tman_path}")
    tman = json.loads(tman_path.read_text())

    mlx_dir = Path(args.mlx_data_dir)
    for key, plan_key in (("train.jsonl", "train_jsonl_sha256"),
                          ("valid.jsonl", "valid_jsonl_sha256")):
        actual = ev.sha256_file(mlx_dir / key)
        expected = tman["data"]["files"][key]["sha256"]
        if actual != expected:
            raise SystemExit(
                f"{mlx_dir / key} sha256 {actual} != the training manifest's {expected}. "
                f"The instruction would not be the one this student was trained with."
            )
        if actual != plan["inputs"][plan_key]:
            raise SystemExit(f"{mlx_dir / key} moved since the plan was written.")

    # The rows this process is about to label must be the rows the previous
    # process labeled — otherwise a resume would splice two passage versions
    # into one journal. The chunk_id list is checked in load_rows(); this checks
    # the TEXT.
    rows_path = Path(args.out_dir) / ROWS_NAME
    rows_sha = ev.sha256_file(rows_path)
    prior = json.loads(Path(args.out_dir, MANIFEST_NAME).read_text()) if \
        Path(args.out_dir, MANIFEST_NAME).exists() else {}
    prior_sha = prior.get("data", {}).get("rows_jsonl_sha256")
    if prior_sha and prior_sha != rows_sha:
        raise SystemExit(
            f"{rows_path} sha256 {rows_sha} != the sha this segment's earlier process "
            f"recorded ({prior_sha}). The passages changed under a resume — refusing to mix "
            f"two prompt versions into one journal."
        )

    instruction = read_instruction(mlx_dir)
    instr_sha = ev.sha256_text(instruction)
    if instr_sha != plan["inputs"]["instruction_sha256"] or instr_sha != INSTRUCTION_SHA256:
        raise SystemExit(
            f"instruction sha {instr_sha} != plan {plan['inputs']['instruction_sha256']} / "
            f"frozen {INSTRUCTION_SHA256}. Refusing to label with a different system turn."
        )

    model_path = args.model or tman["model"]["resolved_snapshot_path"]
    adapter_prov = ev._adapter_provenance(args.adapter_path, model_path)

    ref_manifest = Path(args.reference_eval_dir) / "manifest.json"
    ref_adapter_sha = ref_instr_sha = None
    if ref_manifest.exists():
        refman = json.loads(ref_manifest.read_text())
        ref_adapter_sha = refman.get("adapter", {}).get("adapters_sha256")
        ref_instr_sha = refman.get("data", {}).get("instruction_sha256")

    # HANDOFF §7 verify-artifact: the adapter about to label 317k chunks must be
    # the adapter the epoch-2 eval actually tested, and the one G1 was ruled on.
    for label, expected in (("the reference eval", ref_adapter_sha),
                            ("the pinned G1 adapter", ADAPTER_SHA256)):
        if expected and expected != adapter_prov["adapters_sha256"]:
            raise SystemExit(
                f"ADAPTER MISMATCH — refusing to run.\n"
                f"  about to label with : {args.adapter_path}\n"
                f"                        adapters.safetensors "
                f"{adapter_prov['adapters_sha256']}\n"
                f"  {label} used        : {expected}\n"
                f"These are different weights; the artifact would not be the artifact that "
                f"was evaluated and ruled at G1."
            )
    if ref_instr_sha and ref_instr_sha != instr_sha:
        raise SystemExit(f"instruction sha differs from the reference eval's {ref_instr_sha}.")

    return {
        "model_path": model_path,
        "model": {"path": model_path, "weights_sha256": tman["model"].get("weights_sha256")},
        "adapter": adapter_prov,
        "train_manifest": {"path": str(tman_path), "sha256": ev.sha256_file(tman_path),
                           "run_id": tman.get("run_id")},
        "data": {
            "chunks_parquet": plan["inputs"]["chunks_parquet"],
            "corpus_parquet_sha256": plan["inputs"]["corpus_parquet_sha256"],
            "rows_jsonl": str(Path(args.out_dir) / ROWS_NAME),
            "rows_jsonl_sha256": ev.sha256_file(Path(args.out_dir) / ROWS_NAME),
            "chunk_id_list_sha256": spec["chunk_id_list_sha256"],
            "mlx_data_dir": str(mlx_dir),
            "instruction_sha256": instr_sha,
            "instruction_sha256_matches_reference_eval": (
                None if ref_instr_sha is None else ref_instr_sha == instr_sha),
            "adapter_sha256_matches_reference_eval": (
                None if ref_adapter_sha is None else ref_adapter_sha == adapter_prov["adapters_sha256"]),
            "adapter_sha256_matches_pinned_G1_adapter": (
                adapter_prov["adapters_sha256"] == ADAPTER_SHA256),
            "reference_eval_manifest": str(ref_manifest) if ref_manifest.exists() else None,
            "n_rows_targeted": n_rows,
        },
    }


# ===========================================================================
# step 2 — generation (checkpointed per row)
# ===========================================================================

def prompt_input_sha(instruction_sha256: str, passage: str) -> str:
    """Identity of a prompt's INPUTS, computable without a tokenizer.

    `relabel_e1.py` renders all 6,746 prompts up front so the resume filter can
    compare token-sequence hashes. F4 does not: a segment is 15k rows and the
    fixed-reserve fit does a binary search on the long ones, so a full
    pre-render would double the truncation work every time a night resumes.
    Hashing (instruction sha + passage bytes) identifies exactly the same thing
    — the rendering is a deterministic pure function of those two — and costs
    nothing. The token-sequence sha is still stored per row, for provenance.
    """
    h = hashlib.sha256()
    h.update(instruction_sha256.encode())
    h.update(b"\x00")
    h.update(passage.encode("utf-8"))
    return h.hexdigest()


def select_rows_to_generate(rows: list, existing: dict, journal_path,
                            instruction_sha256: str) -> list:
    """Resume filter. A checkpointed row whose stored prompt-input hash
    disagrees with this run's means the passage or the instruction changed
    under a resume, and the journal would hold two prompt versions. Hard stop,
    never a warning (`eval.select_rows_to_generate`'s contract, over inputs
    instead of token ids)."""
    todo = []
    for row in rows:
        want = prompt_input_sha(instruction_sha256, row["passage"])
        prev = existing.get(row["chunk_id"])
        if prev is None:
            row["_prompt_input_sha256"] = want
            todo.append(row)
            continue
        stored = prev.get("prompt_input_sha256")
        if stored is not None and stored != want:
            raise SystemExit(
                f"chunk {row['chunk_id']}: the checkpointed label was generated from a "
                f"DIFFERENT prompt than the one this run renders. The chunk table or the "
                f"instruction changed under a resume. Move {journal_path} aside and "
                f"restart the segment clean."
            )
    return todo


def generate(rows: list, args, journal_path: Path) -> dict:
    """One JSON answer per row, greedy, appended + fsync'd row by row.

    Decoding and telemetry mirror `relabel_e1.generate` / `eval.mlx_generate`
    exactly, so the eval-reproduction canary can be byte-for-byte.
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
    todo = select_rows_to_generate(rows, existing, journal_path, args.instruction_sha256)
    n_done_before = len(rows) - len(todo)
    print(f"{n_done_before} already in {journal_path.name} · {len(todo)} to generate",
          file=sys.stderr)
    if args.max_rows_per_segment:
        todo = todo[: args.max_rows_per_segment]
        print(f"process cap: at most {len(todo)} rows this process", file=sys.stderr)
    if not todo:
        return {"n_generated": 0, "note": "nothing to do — journal already covers the segment"}

    # The RENDERING tokenizer is the plain HF tokenizer from the same snapshot
    # convert_to_mlx.py used — not mlx_lm's wrapper, whose apply_chat_template
    # injects an `enable_thinking` kwarg. Identical code path == identical bytes.
    render_tok = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    instruction = read_instruction(Path(args.mlx_data_dir))

    print("loading base model + adapter (the only GPU work) ...", file=sys.stderr)
    t_load = time.perf_counter()
    model, tokenizer = mlx_load(args.model, adapter_path=args.adapter_path)
    load_s = time.perf_counter() - t_load
    print(f"  loaded in {load_s:.1f}s", file=sys.stderr)

    sampler = make_sampler(temp=0.0)  # temp==0 -> mx.argmax: fully deterministic
    repaired = r1.ensure_trailing_newline(journal_path)
    started = utcnow()
    fresh, n_trunc, n_bad_prefix = [], 0, 0
    t0 = time.perf_counter()
    with open(journal_path, "a") as fh:
        for i, row in enumerate(todo, 1):
            t_row = time.perf_counter()
            passage, prompt_ids, truncated, prefix_ok = fit_prompt(
                render_tok, instruction, row["passage"],
                max_seq_len=args.max_seq_length, reserve=args.answer_token_reserve,
            )
            n_trunc += int(truncated)
            n_bad_prefix += int(not prefix_ok)
            text, last = "", None
            for resp in stream_generate(
                model, tokenizer, prompt_ids, max_tokens=args.max_tokens, sampler=sampler
            ):
                text += resp.text
                last = resp
            latency = time.perf_counter() - t_row

            rec = {
                "chunk_id": row["chunk_id"],
                "segment_id": args.segment_id,
                "raw_output": text,
                "prompt_input_sha256": row["_prompt_input_sha256"],
                "prompt_sha256": ev.sha256_text(json.dumps(prompt_ids)),
                "prompt_tokens": int(last.prompt_tokens) if last else len(prompt_ids),
                "generation_tokens": int(last.generation_tokens) if last else 0,
                "prompt_tps": float(last.prompt_tps) if last else None,
                "generation_tps": float(last.generation_tps) if last else None,
                "finish_reason": last.finish_reason if last else "no_response",
                "peak_memory_gb": round(float(last.peak_memory), 3) if last else None,
                "latency_s": round(latency, 3),
                "passage_was_head_truncated": truncated,
                "passage_chars_kept": len(passage),
                "passage_head_prefix_ok": prefix_ok,
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
                    f"  [{i}/{len(todo)} this process · {done_all}/{len(rows)} segment] "
                    f"{latency:.2f}s/row · {cph:.0f} chunks/h · ETA {eta_h:.2f}h for the "
                    f"segment · last finish={rec['finish_reason']} "
                    f"gen_tok={rec['generation_tokens']}",
                    file=sys.stderr, flush=True,
                )

    wall = time.perf_counter() - t0
    return {
        "started_utc": started,
        "ended_utc": utcnow(),
        "n_generated": len(fresh),
        "torn_final_line_repaired_before_append": repaired,
        "model_load_seconds": round(load_s, 1),
        "wall_seconds": round(wall, 1),
        "chunks_per_hour": round(len(fresh) / wall * 3600.0, 1) if wall else None,
        "finish_reasons": dict(ev.Counter(r["finish_reason"] for r in fresh)),
        "n_passages_head_truncated": n_trunc,
        "n_passages_not_a_head_prefix": n_bad_prefix,
        "versions": ev._versions(),
    }


# ===========================================================================
# the writer — missing->NONE with its audit flag
# ===========================================================================

def f4_label_row(rec: dict, guidance_applicable: bool, run_id: str = RUN_ID) -> dict:
    """`relabel_e1.student_label_row` + the owner-ruled missing->NONE rule.

    The rule (eval report A.1, adopted at the writer 2026-08-27):
      on a GUIDANCE-APPLICABLE passage, if the student's JSON omits the
      `guidance_direction` key entirely, persist `NONE` and set
      `guidance_imputed_none = True`.

    Scope limits, enforced here and pinned by tests:
      * applicability comes from the corpus's own `section_type`, mirroring the
        teacher's per-section JSON schema (`EX99_PRESS_RELEASE`, `8K_BODY`).
        It is a WRITER-side rule — section_type never enters the prompt
        (rubric v1.1, HANDOFF §3 2026-08-10).
      * it rewrites ONLY the omitted-key case. An unparseable row, an
        out-of-taxonomy value, or any wrong value stays exactly as emitted.
      * it touches nothing else: sentiment, red_flags, parse/schema integrity.
    """
    row = r1.student_label_row(rec, run_id=run_id)
    imputed = False
    if guidance_applicable and row["parse_ok"]:
        parsed, _ = ev.parse_model_output(rec.get("raw_output"))
        if parsed is not None and "guidance_direction" not in parsed:
            row["guidance_direction"] = "NONE"
            imputed = True
    row["guidance_imputed_none"] = imputed
    row["guidance_applicable"] = bool(guidance_applicable)
    row["segment_id"] = rec.get("segment_id")
    row["passage_was_head_truncated"] = bool(rec.get("passage_was_head_truncated"))
    row["passage_chars_kept"] = int(rec.get("passage_chars_kept") or 0)
    return row


STUDENT_ONLY_FIELDS = [
    ("segment_id", "string"),
    ("passage_was_head_truncated", "bool"),
    ("passage_chars_kept", "int64"),
    ("prompt_tokens", "int64"),
    ("prompt_sha256", "string"),
    ("latency_s", "float64"),
    ("schema_issues", "list_string"),
    ("guidance_applicable", "bool"),
    ("guidance_imputed_none", "bool"),
]


def output_schema():
    """`data/labels_v12.parquet`'s own 34-field arrow schema + 9 F4 fields.

    The teacher schema is COPIED from the file (`relabel_e1.teacher_schema`),
    never re-declared, so the downstream join stays a path swap. Two E1-only
    fields have no E2 analogue and are filled explicitly rather than faked:
    `home_ticker` (null) and `source_tickers` (empty) — E2 filings are
    CIK-keyed and inventing a ticker would be false provenance.
    """
    import pyarrow as pa

    fields, widened = r1.teacher_schema(LABELS_V12)
    n_teacher = len(fields)
    types = {"string": pa.string(), "bool": pa.bool_(), "int64": pa.int64(),
             "float64": pa.float64(), "list_string": pa.list_(pa.string())}
    for name, kind in STUDENT_ONLY_FIELDS:
        fields.append(pa.field(name, types[kind]))
    schema = pa.schema(fields, metadata={
        "f4_run_id": RUN_ID,
        "f4_red_flags_status": RED_FLAGS_STATUS,
        "f4_labeler": (
            f"local MLX student qwen2.5-7b-finscreen-lora-mlx-v12-epoch2 "
            f"(adapter {ADAPTER_SHA256})"),
        "f4_guidance_rule": (
            "missing->NONE applied at the writer on guidance-applicable section types; "
            "the guidance_imputed_none column says which rows"),
        "f4_teacher": (
            "NONE - these are STUDENT labels, not Claude labels. "
            "data/labels_v12.parquet supplied the arrow schema only."),
    })
    return schema, n_teacher, widened


def build_segment_parquet(journal_path: Path, parquet_path: Path, spec: dict,
                          rows: list, args) -> dict:
    """Journal -> a parquet whose leading 34 columns ARE the v1.2 teacher schema."""
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq

    records = ev.load_predictions(journal_path)
    if not records:
        raise SystemExit(f"{journal_path} has no usable records.")

    corpus = read_chunk_rows(
        ["chunk_id", "section_type", "text", "word_count", "n_paragraphs",
         "paragraph_ids", "home_cik", "home_accession_number", "home_form",
         "home_filing_date", "source_accession_numbers", "source_filing_dates",
         "source_forms", "n_source_filings", "guidance_applicable"],
        spec["row_start"], spec["n_rows"],
    ).to_pandas()
    corpus = corpus[corpus["chunk_id"].isin(set(records))].copy()

    applicable = dict(zip(corpus["chunk_id"], corpus["guidance_applicable"]))
    label_rows = []
    for cid in corpus["chunk_id"]:
        row = f4_label_row(records[cid], bool(applicable[cid]), run_id=args.run_id)
        row["chunk_id"] = cid
        row["max_tokens_used"] = args.max_tokens
        row["labeling_config"] = LABELING_CONFIG.format(
            max_tokens=args.max_tokens, reserve=args.answer_token_reserve)
        row["rubric_version"] = RUBRIC_VERSION
        row["system_prompt_sha256"] = INSTRUCTION_SHA256
        row["completion_batch_id"] = None
        row["home_ticker"] = None
        row["source_tickers"] = []
        label_rows.append(row)
    labels_df = pd.DataFrame(label_rows).set_index("chunk_id")

    df = corpus.drop(columns=["guidance_applicable"]).set_index("chunk_id").join(
        labels_df, how="inner").reset_index()

    schema, n_teacher, widened = output_schema()
    table = pa.Table.from_pandas(df[[f.name for f in schema]], schema=schema,
                                 preserve_index=False)
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, parquet_path)

    gi = df["guidance_imputed_none"]
    ga = df["guidance_applicable"]
    emitted_guidance = df["guidance_direction"].notna() & (~gi)
    return {
        "path": str(parquet_path),
        "sha256": ev.sha256_file(parquet_path),
        "n_rows": int(len(df)),
        "n_columns": len(schema),
        "schema_source": (
            f"columns 1-{n_teacher} copied verbatim from {LABELS_V12.name}'s arrow schema "
            f"(SCHEMA ONLY — not a teacher for these rows); {len(STUDENT_ONLY_FIELDS)} F4 "
            f"columns appended"
        ),
        "null_typed_columns_widened_to_string": widened,
        "e1_only_columns_filled": {"home_ticker": None, "source_tickers": []},
        "parse_failures": int((~df["parse_ok"]).sum()),
        "schema_violations": int((~df["schema_valid"]).sum()),
        "guidance": {
            "n_applicable": int(ga.sum()),
            "n_imputed_none": int(gi.sum()),
            "imputed_rate_of_applicable": (
                round(float(gi.sum()) / int(ga.sum()), 4) if int(ga.sum()) else None),
            "n_explicitly_emitted": int(emitted_guidance.sum()),
            "n_emitted_on_non_applicable_section": int((emitted_guidance & ~ga).sum()),
            "rule": "missing->NONE at the writer, audit flag guidance_imputed_none",
        },
        "sentiment": {
            "n_emitted": int(df["sentiment"].notna().sum()),
            "n_emitted_on_risk_factors": int(
                (df["sentiment"].notna() & (df["section_type"] == "RISK_FACTORS")).sum()),
        },
        "head_truncation": {
            "n_truncated": int(df["passage_was_head_truncated"].sum()),
            "rate": round(float(df["passage_was_head_truncated"].mean()), 5),
            "answer_token_reserve": args.answer_token_reserve,
            "prompt_token_budget": args.max_seq_length - args.answer_token_reserve,
        },
        "distress_tier": "uniformly empty by construction (HANDOFF §7)",
        "red_flags_status": RED_FLAGS_STATUS,
    }


# ===========================================================================
# the eval-reproduction canary — F4's verify-artifact check
# ===========================================================================

def repro_canary(args, n: int = 10) -> dict:
    """Re-generate N v1.2 EVAL rows through the F4 code path and compare to the
    epoch-2 eval's stored predictions, byte for byte.

    F4 labels unlabeled text, so it has no reference of its own. This is the
    substitute and it is stronger than a schema check: greedy decoding on a
    token-identical prompt with the same adapter is deterministic, so a match
    proves the prompt renderer, the adapter and the decoding are the ones the
    eval — and gate G1 — were ruled on.

    Only rows whose UNTRUNCATED prompt already fits the F4 budget are used, and
    the number skipped is reported: on a longer row F4's reserve legitimately
    truncates and the eval's answer-fitted truncation does not, so a mismatch
    there would be the policy working, not a defect.
    """
    from mlx_lm import load as mlx_load
    from mlx_lm.generate import stream_generate
    from mlx_lm.sample_utils import make_sampler
    from transformers import AutoTokenizer

    ref_path = Path(args.reference_eval_dir) / "predictions.jsonl"
    ref = ev.load_predictions(ref_path)
    valid = [json.loads(line) for line in open(Path(args.mlx_data_dir) / "valid.jsonl")]
    render_tok = AutoTokenizer.from_pretrained(args.model, local_files_only=True)
    budget = args.max_seq_length - args.answer_token_reserve

    picked, n_skipped = [], 0
    for rec in valid:
        if len(picked) >= n:
            break
        instruction = rec["messages"][0]["content"]
        passage = rec["messages"][1]["content"]
        ids = render_prompt_ids(render_tok, instruction, passage)
        if len(ids) > budget:
            n_skipped += 1
            continue
        # the F4 renderer must reproduce the answer-bearing path exactly
        ref_ids = ev.render_prompt_token_ids(render_tok, {
            "chunk_id": rec["chunk_id"], "instruction": instruction, "passage": passage,
            "gold_text": rec["messages"][2]["content"], "messages": rec["messages"],
        })
        if ids != ref_ids:
            raise SystemExit(
                f"chunk {rec['chunk_id']}: label_e2.render_prompt_ids does NOT reproduce "
                f"eval.render_prompt_token_ids. Refusing to label 317k chunks with a prompt "
                f"that is not the trained one."
            )
        picked.append((rec["chunk_id"], ids))

    model, tokenizer = mlx_load(args.model, adapter_path=args.adapter_path)
    sampler = make_sampler(temp=0.0)
    results = []
    for cid, ids in picked:
        text = ""
        for resp in stream_generate(model, tokenizer, ids, max_tokens=args.max_tokens,
                                    sampler=sampler):
            text += resp.text
        results.append({"chunk_id": cid, "identical": text == ref.get(cid, {}).get("raw_output")})

    n_identical = sum(1 for r in results if r["identical"])
    out = {
        "purpose": "F4 verify-artifact check: the artifact being run is the artifact the "
                   "epoch-2 eval tested and gate G1 was ruled on",
        "reference": str(ref_path),
        "reference_sha256": ev.sha256_file(ref_path),
        "adapter": str(args.adapter_path),
        "prompt_renderer_matches_eval_path": True,
        "n_compared": len(results),
        "n_identical": n_identical,
        "verified": bool(results) and n_identical == len(results),
        "n_eval_rows_skipped_as_too_long_for_the_F4_budget": n_skipped,
        "prompt_token_budget": budget,
        "differing": [r["chunk_id"] for r in results if not r["identical"]],
        "checked_utc": utcnow(),
    }
    return out


# ===========================================================================
# campaign finalize
# ===========================================================================

def finalize_campaign(plan: dict, out_parquet: Path = CAMPAIGN_PARQUET,
                      manifest_path: Path = CAMPAIGN_MANIFEST) -> dict:
    """Concatenate the finished segment parquets and accumulate provenance.

    Streams row groups, so peak memory is one row group, not 317k rows.
    Segments that are not finalized yet are listed as missing rather than
    silently dropped — a partial campaign parquet that looks complete is the
    exact failure mode HANDOFF §7 forbids.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    schema, _, _ = output_schema()
    done, missing, per_segment = [], [], []
    for spec in plan["segments"]:
        p = Path(spec["dir"]) / f"labels_{spec['segment_id']}.parquet"
        m = Path(spec["dir"]) / MANIFEST_NAME
        if p.exists() and m.exists():
            done.append((spec, p, json.loads(m.read_text())))
        else:
            missing.append(spec["segment_id"])

    writer = pq.ParquetWriter(out_parquet, schema) if done else None
    n_rows = 0
    totals = {"parse_failures": 0, "schema_violations": 0, "n_imputed_none": 0,
              "n_applicable": 0, "n_truncated": 0, "generated_seconds": 0.0}
    for spec, p, man in done:
        pf = pq.ParquetFile(p)
        for batch in pf.iter_batches(batch_size=5000):
            writer.write_table(pa.Table.from_batches([batch], schema=schema))
            n_rows += batch.num_rows
        pq_block = man.get("parquet", {})
        totals["parse_failures"] += pq_block.get("parse_failures", 0)
        totals["schema_violations"] += pq_block.get("schema_violations", 0)
        totals["n_imputed_none"] += pq_block.get("guidance", {}).get("n_imputed_none", 0)
        totals["n_applicable"] += pq_block.get("guidance", {}).get("n_applicable", 0)
        totals["n_truncated"] += pq_block.get("head_truncation", {}).get("n_truncated", 0)
        totals["generated_seconds"] += sum(
            s.get("wall_seconds", 0) or 0 for s in man.get("segments", []))
        per_segment.append({
            "segment_id": spec["segment_id"],
            "n_rows": pq_block.get("n_rows"),
            "parquet_sha256": pq_block.get("sha256"),
            "journal_sha256": man.get("journal", {}).get("sha256"),
            "n_processes": len(man.get("segments", [])),
            "wall_seconds": sum(s.get("wall_seconds", 0) or 0 for s in man.get("segments", [])),
            "chunks_per_hour": man.get("totals", {}).get(
                "chunks_per_hour_excluding_load_and_gaps"),
            "finalized_utc": man.get("finalized_utc"),
        })
    if writer:
        writer.close()

    manifest = {
        "run_id": plan["run_id"],
        "updated_utc": utcnow(),
        "cost_usd": 0.0,
        "anthropic_api_calls": 0,
        "COMPLETE": not missing,
        "n_segments_planned": len(plan["segments"]),
        "n_segments_finalized": len(done),
        "segments_missing": missing,
        "n_rows_written": n_rows,
        "n_rows_planned": plan["inputs"]["chunks_parquet"]["n_rows"],
        "parquet": ({"path": str(out_parquet), "sha256": ev.sha256_file(out_parquet),
                     "n_rows": n_rows} if done else None),
        "totals": totals,
        "throughput": {
            "chunks_per_hour_overall": (
                round(n_rows / totals["generated_seconds"] * 3600.0, 1)
                if totals["generated_seconds"] else None),
            "generated_hours": round(totals["generated_seconds"] / 3600.0, 2),
        },
        "inputs": plan["inputs"],
        "generation": plan["generation"],
        "owner_rulings": plan["owner_rulings"],
        "per_segment": per_segment,
        "caveats": CAVEATS,
    }
    if not missing and n_rows != plan["inputs"]["chunks_parquet"]["n_rows"]:
        manifest["WARNING"] = (
            f"every segment finalized but {n_rows} rows written vs "
            f"{plan['inputs']['chunks_parquet']['n_rows']} planned"
        )
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


# ===========================================================================
# main
# ===========================================================================

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_argument_group("modes (exactly one)")
    mode.add_argument("--plan", action="store_true",
                      help="SYSTEM python3: verify every sha and write the campaign plan")
    mode.add_argument("--prepare-segment", default=None, metavar="SEG",
                      help="SYSTEM python3: materialise one segment's rows.jsonl "
                           "('3' or 'seg-003'; 'all' prepares every segment)")
    mode.add_argument("--segment", default=None, metavar="SEG",
                      help=".mlx_venv: GENERATE this segment (resume by re-running)")
    mode.add_argument("--finalize-segment", default=None, metavar="SEG",
                      help="SYSTEM python3: journal -> segment parquet + manifest")
    mode.add_argument("--finalize-campaign", action="store_true",
                      help="SYSTEM python3: concatenate finished segments + campaign manifest")
    mode.add_argument("--repro-canary", type=int, default=0, metavar="N",
                      help=".mlx_venv: re-generate N v1.2 eval rows through the F4 path and "
                           "compare byte-for-byte to the epoch-2 eval")

    ap.add_argument("--plan-path", default=str(PLAN_PATH))
    ap.add_argument("--segment-rows", type=int, default=DEFAULT_SEGMENT_ROWS)
    ap.add_argument("--out-dir", default=None,
                    help="default: the plan's directory for this segment (a smoke run "
                         "points somewhere else)")
    ap.add_argument("--limit", type=int, default=0, help="first N rows of the segment (smoke)")
    ap.add_argument("--allow-partial", action="store_true",
                    help="allow --finalize-segment on an incomplete journal (smoke runs)")
    ap.add_argument("--adapter-path", default=str(ADAPTER))
    ap.add_argument("--train-manifest", default=str(TRAIN_MANIFEST))
    ap.add_argument("--mlx-data-dir", default=str(MLX_DATA_DIR))
    ap.add_argument("--reference-eval-dir", default=str(REFERENCE_EVAL_DIR))
    ap.add_argument("--model", default=None, help="default: the training manifest's snapshot")
    ap.add_argument("--run-id", default=RUN_ID)
    ap.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    ap.add_argument("--max-seq-length", type=int, default=MAX_SEQ_LEN)
    ap.add_argument("--answer-token-reserve", type=int, default=ANSWER_TOKEN_RESERVE)
    ap.add_argument("--max-rows-per-segment", type=int, default=0,
                    help="voluntarily exit after N rows (0 = run until done or killed)")
    ap.add_argument("--progress-every", type=int, default=50)
    ap.add_argument("--no-resume", dest="resume", action="store_false")
    return ap


def main() -> int:
    args = build_parser().parse_args()
    plan_path = Path(args.plan_path)

    if args.plan:
        plan = build_plan(args.segment_rows, plan_path)
        print(
            f"wrote {plan_path}\n"
            f"  chunks    {plan['inputs']['chunks_parquet']['n_rows']} rows · sha "
            f"{plan['inputs']['chunks_parquet']['sha256'][:16]}\n"
            f"  segments  {plan['segmentation']['n_segments']} "
            f"(~{args.segment_rows} rows each, accession-aligned)\n"
            f"  adapter   {plan['inputs']['adapter_sha256_expected'][:16]} · instruction "
            f"{plan['inputs']['instruction_sha256'][:16]}",
            file=sys.stderr,
        )
        return 0

    if args.prepare_segment:
        plan = load_plan(plan_path)
        specs = (plan["segments"] if args.prepare_segment == "all"
                 else [segment_spec(plan, args.prepare_segment)])
        for spec in specs:
            info = prepare_segment(plan, spec, args.out_dir if len(specs) == 1 else None)
            print(f"  {info['segment_id']}  {info['n_rows']} rows -> {info['rows_jsonl']} "
                  f"(sha {info['rows_jsonl_sha256'][:16]})", file=sys.stderr)
        return 0

    if args.finalize_campaign:
        plan = load_plan(plan_path)
        man = finalize_campaign(plan)
        print(
            f"\nCAMPAIGN {'COMPLETE' if man['COMPLETE'] else 'PARTIAL'}\n"
            f"  segments  {man['n_segments_finalized']}/{man['n_segments_planned']}"
            + (f" · missing {man['segments_missing']}" if man["segments_missing"] else "") + "\n"
            f"  rows      {man['n_rows_written']}/{man['n_rows_planned']}\n"
            f"  parquet   {(man['parquet'] or {}).get('path')}\n"
            f"  manifest  {CAMPAIGN_MANIFEST}",
            file=sys.stderr,
        )
        return 0 if man["COMPLETE"] else 2

    if args.repro_canary:
        plan = load_plan(plan_path)
        tman = json.loads(Path(args.train_manifest).read_text())
        args.model = args.model or tman["model"]["resolved_snapshot_path"]
        out = repro_canary(args, args.repro_canary)
        CANARY_PATH.write_text(json.dumps(out, indent=2) + "\n")
        print(f"\nREPRO CANARY: {out['n_identical']}/{out['n_compared']} byte-identical · "
              f"verified={out['verified']} · skipped {out['n_eval_rows_skipped_as_too_long_for_the_F4_budget']}"
              f"\n  {CANARY_PATH}", file=sys.stderr)
        return 0 if out["verified"] else 1

    if not (args.segment or args.finalize_segment):
        build_parser().print_usage(sys.stderr)
        raise SystemExit("pick a mode: --plan / --prepare-segment / --segment / "
                         "--finalize-segment / --finalize-campaign / --repro-canary")

    plan = load_plan(plan_path)
    spec = segment_spec(plan, args.segment or args.finalize_segment)
    args.segment_id = spec["segment_id"]
    out_dir = Path(args.out_dir or spec["dir"])
    journal_path = out_dir / JOURNAL_NAME
    manifest_path = out_dir / MANIFEST_NAME
    parquet_path = out_dir / f"labels_{spec['segment_id']}.parquet"
    rows = load_rows(out_dir, spec, args.limit)
    target = len(rows)

    if args.finalize_segment:
        progress = r1.journal_progress(journal_path, target)
        if not progress["complete"] and not args.allow_partial:
            raise SystemExit(
                f"journal has {progress['n_rows']}/{target} rows. The parquet is written on "
                f"COMPLETION only — resume the generation step, or pass --allow-partial if "
                f"this is a smoke run."
            )
        records = ev.load_predictions(journal_path)
        parquet = build_segment_parquet(journal_path, parquet_path, spec, rows, args)
        man = r1.update_manifest(manifest_path, {
            "segment": {k: spec[k] for k in ("segment_id", "row_start", "row_end", "n_rows",
                                             "first_chunk_id", "last_chunk_id")},
            "journal": {**progress, "sha256": ev.sha256_file(journal_path)},
            "totals": r1.totals_from_journal(records),
            "parquet": {**parquet, "partial": not progress["complete"]},
            "finalized_utc": utcnow(),
        }, run_id=args.run_id, caveats=CAVEATS)
        g = parquet["guidance"]
        print(
            f"\nFINALIZED {spec['segment_id']}"
            f"{' (PARTIAL)' if not progress['complete'] else ''}\n"
            f"  parquet   {parquet['path']}\n"
            f"            {parquet['n_rows']} rows · {parquet['n_columns']} cols · "
            f"sha {parquet['sha256'][:16]}\n"
            f"  parse     {parquet['parse_failures']} failures · "
            f"{parquet['schema_violations']} schema violations\n"
            f"  guidance  {g['n_imputed_none']}/{g['n_applicable']} applicable rows "
            f"imputed NONE (flagged)\n"
            f"  truncated {parquet['head_truncation']['n_truncated']} passages "
            f"(reserve {args.answer_token_reserve})\n"
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
            f"    {HERE / '.mlx_venv' / 'bin' / 'python'} {Path(__file__).name} "
            f"--segment {spec['segment_id']}"
        )
    args.out_dir = str(out_dir)
    prov = preflight(args, plan, spec, target)
    args.model = prov["model_path"]
    args.instruction_sha256 = prov["data"]["instruction_sha256"]
    out_dir.mkdir(parents=True, exist_ok=True)
    r1.update_manifest(manifest_path, {
        "purpose": (
            f"F4 E2 labeling ({args.run_id}), segment {spec['segment_id']}: the v1.2 "
            f"epoch-2 student labels rows {spec['row_start']}-{spec['row_end']} of "
            f"{CHUNKS_PARQUET.name}. Local MLX, $0, zero Anthropic API calls."
        ),
        "segment": {k: spec[k] for k in ("segment_id", "row_start", "row_end", "n_rows",
                                         "first_chunk_id", "last_chunk_id")},
        "model": prov["model"], "adapter": prov["adapter"],
        "train_manifest": prov["train_manifest"], "data": prov["data"],
        "generation": {**plan["generation"], "limit": args.limit or None},
        "owner_rulings": plan["owner_rulings"],
        "journal": r1.journal_progress(journal_path, target),
    }, run_id=args.run_id, caveats=CAVEATS)

    segment_rec = generate(rows, args, journal_path)
    progress = r1.journal_progress(journal_path, target)
    r1.update_manifest(manifest_path, {"journal": progress}, segment=segment_rec,
                       run_id=args.run_id, caveats=CAVEATS)
    if progress["complete"]:
        print(
            f"\nSEGMENT {spec['segment_id']} COMPLETE — {progress['n_rows']}/{target} rows.\n"
            f"Now finalize with the SYSTEM python3 (no GPU, seconds):\n"
            f"    python3 finetune/label_e2.py --finalize-segment {spec['segment_id']}",
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
