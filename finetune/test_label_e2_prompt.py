#!/usr/bin/env python3
"""The tokenizer-dependent half of label_e2.py's test suite.

Run it with the MLX venv's interpreter, which has `transformers` but neither
pytest nor pyarrow (exactly like `test_eval_real.py`, which is why this file
carries its own runner instead of using pytest):

    finetune/.mlx_venv/bin/python finetune/test_label_e2_prompt.py

NO GPU, no model weights, no mlx import, no network (`local_files_only=True`).
Only the tokenizer and its chat template are loaded. $0.

What it pins:
  1. `label_e2.render_prompt_ids` (no answer) reproduces
     `eval.render_prompt_token_ids` (answer-bearing, the path the epoch-2 eval
     and H3v2 ran) TOKEN FOR TOKEN on real v1.2 eval rows. If these diverge,
     F4 would label 317,081 chunks with a prompt the student never saw.
  2. The assistant slot cannot leak into the prompt.
  3. The fixed answer-token reserve truncates only the passage TAIL, respects
     the budget, and is a no-op on rows that already fit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import eval as ev
import label_e2 as L

MODEL = ("/Users/vihanpatil/.cache/huggingface/hub/models--mlx-community--"
         "Qwen2.5-7B-Instruct-4bit/snapshots/c26a38f6a37d0a51b4e9a1eb3026530fa35d9fed")
VALID = L.MLX_DATA_DIR / "valid.jsonl"


# 2026-09-07: Skip is a PYTEST skip when pytest is importable. This file is
# also collected by the repo-wide `python3 -m pytest` run, where `transformers`
# is absent by design (it lives in .mlx_venv), so a plain exception made all six
# tokenizer tests fail RED on every healthy system-python3 run — a check that
# cries wolf on healthy behaviour. The standalone runner below still catches
# `Skip` first, so `finetune/.mlx_venv/bin/python finetune/test_label_e2_prompt.py`
# is unchanged, and nothing about what the tests assert is weakened.
try:
    import pytest as _pytest
    _SkipBase = _pytest.skip.Exception
except ImportError:          # .mlx_venv has pytest neither installed nor needed
    _SkipBase = Exception


class Skip(_SkipBase):
    pass


_TOK = None


def tokenizer():
    global _TOK
    if _TOK is None:
        if not Path(MODEL).exists():
            raise Skip("the base snapshot is not on this machine")
        try:
            from transformers import AutoTokenizer
        except ImportError:
            raise Skip("transformers lives in .mlx_venv — run this with that interpreter")
        _TOK = AutoTokenizer.from_pretrained(MODEL, local_files_only=True)
    return _TOK


def eval_rows(n=40):
    if not VALID.exists():
        raise Skip("mlx_data_v12/valid.jsonl is not on this machine")
    out = []
    with open(VALID) as f:
        for line in f:
            out.append(json.loads(line))
            if len(out) >= n:
                break
    return out


# --------------------------------------------------------------------------

def test_render_prompt_ids_reproduces_the_answer_bearing_eval_path():
    tok = tokenizer()
    for rec in eval_rows(40):
        msgs = rec["messages"]
        want = ev.render_prompt_token_ids(tok, {
            "chunk_id": rec["chunk_id"], "instruction": msgs[0]["content"],
            "passage": msgs[1]["content"], "gold_text": msgs[2]["content"],
            "messages": msgs,
        })
        got = L.render_prompt_ids(tok, msgs[0]["content"], msgs[1]["content"])
        assert got == want, f"{rec['chunk_id']}: {len(got)} vs {len(want)} tokens"


def test_the_assistant_slot_cannot_leak_into_the_prompt():
    import convert_to_mlx as c2m
    tok = tokenizer()
    a = L.render_prompt_ids(tok, "instr", "passage text")
    ids, off = c2m.render(tok, c2m.to_messages("instr", "passage text", "SECRET ANSWER"))
    assert list(ids[:off]) == a
    assert L.render_prompt_ids(tok, "instr", "passage text") == a       # deterministic


def test_the_instruction_alone_is_425_prompt_tokens():
    """Measured, and it is what makes the 1,792-token budget comfortable."""
    tok = tokenizer()
    instr = L.read_instruction()
    n = len(L.render_prompt_ids(tok, instr, ""))
    assert n == 425, n


def test_fit_prompt_is_a_noop_on_a_row_that_already_fits():
    tok = tokenizer()
    instr = L.read_instruction()
    rec = eval_rows(1)[0]
    passage = rec["messages"][1]["content"]
    kept, ids, truncated, ok = L.fit_prompt(tok, instr, passage)
    assert truncated is False and ok is True and kept == passage
    assert len(ids) <= L.MAX_SEQ_LEN - L.ANSWER_TOKEN_RESERVE


def test_fit_prompt_drops_only_the_tail_and_respects_the_budget():
    tok = tokenizer()
    instr = L.read_instruction()
    long_passage = " ".join(r["messages"][1]["content"] for r in eval_rows(8))
    kept, ids, truncated, ok = L.fit_prompt(tok, instr, long_passage)
    budget = L.MAX_SEQ_LEN - L.ANSWER_TOKEN_RESERVE
    assert truncated is True
    assert len(ids) <= budget
    assert ok is True and long_passage.startswith(kept)
    assert len(kept) < len(long_passage)
    # and it keeps as much as it can: one more token would not fit
    assert len(ids) > budget - 64


def test_a_bigger_reserve_keeps_less_text():
    tok = tokenizer()
    instr = L.read_instruction()
    long_passage = " ".join(r["messages"][1]["content"] for r in eval_rows(8))
    a, _, _, _ = L.fit_prompt(tok, instr, long_passage, reserve=128)
    b, _, _, _ = L.fit_prompt(tok, instr, long_passage, reserve=512)
    assert len(b) < len(a)
    assert a.startswith(b)


def test_the_reserve_clears_every_measured_generation_length():
    assert L.ANSWER_TOKEN_RESERVE == 256
    assert L.MAX_SEQ_LEN - L.ANSWER_TOKEN_RESERVE == 1792
    assert L.MAX_TOKENS == 520          # the reserve is a length regime, not a cap


# --------------------------------------------------------------------------

def main() -> int:
    tests = [(n, f) for n, f in sorted(globals().items())
             if n.startswith("test_") and callable(f)]
    passed = failed = skipped = 0
    failures = []
    for name, fn in tests:
        try:
            fn()
        except Skip as e:
            skipped += 1
            print(f"SKIP {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            failures.append((name, e))
            print(f"FAIL {name}: {type(e).__name__}: {e}")
        else:
            passed += 1
            print(f"ok   {name}")
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    if failures:
        import traceback
        for name, e in failures:
            print(f"\n--- {name} ---")
            traceback.print_exception(type(e), e, e.__traceback__)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
