#!/usr/bin/env python3
"""validate_verdict.py — gate one rater candidate on its way into verdicts/.

usage: python3 data/f4/g2/validate_verdict.py CANDIDATE BATCH OUT [--no-red-flags]
       python3 data/f4/g2/validate_verdict.py --selftest

The ONLY normalization is: strip surrounding whitespace and ONE optional
markdown code fence. Nothing else is ever altered — no reordering, no repair, no
filled-in field: a repaired verdict is a fabricated verdict (design §11.3,
OVERNIGHT_PLAN stage 2). The schema is analyze_g2.check_rater_objects(),
IMPORTED rather than re-implemented, so the writer and the analysis cannot
drift; that function raises AssertionError and returns the sorted chunk_ids it
saw. It does not check batch COVERAGE (a short file passes it), so the
set-equality check is added here. Every rejection is mapped onto exactly one of
analyze_g2.FAILED_BATCH_CAUSES, so the cause can be copied straight into
failed_batches.json.

Exit: 0 written / 2 non-parsing JSON / 3 rejected. 0 API calls, 0 network.
"""

import argparse
import ast
import copy
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

ANALYZE = Path("/Users/vihanpatil/personal/projects/FinScreen/data/f4/g2/analyze_g2.py")


def load_analyze():
    spec = importlib.util.spec_from_file_location("analyze_g2", ANALYZE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def unwrap(raw):
    """Strip whitespace and ONE surrounding ```/```json fence. Nothing else."""
    t = raw.strip()
    if t.startswith("```") and t.endswith("```") and "\n" in t:
        t = t[t.index("\n") + 1:-3].strip()
    return t


def cause_of(msg):
    """Map one check_rater_objects AssertionError onto ONE enumerated cause."""
    if "is not in that batch" in msg or "duplicate chunk_id" in msg:
        return "chunk_id_set_mismatch"
    if "key set" in msg:
        # "key set ['a', ...] != ['b', ...]" — a required key absent is an
        # omission (§11.3 "omitted a required field"); anything else is schema.
        try:
            have, want = (ast.literal_eval(s) for s in re.findall(r"\[[^\]]*\]", msg)[:2])
        except (SyntaxError, ValueError):
            return "schema_violation"
        return "missing_required_field" if set(want) - set(have) else "schema_violation"
    return "schema_violation"


def validate(text, batch_ids, mod, rate_red_flags=True):
    """Return (objs, None) on success, else (None, '<cause>: <detail>')."""
    t = unwrap(text)
    if not t:
        return None, "agent_errored: candidate is empty after fence/whitespace strip"
    try:
        objs = json.loads(t)
    except ValueError as e:
        return None, f"non_parsing_json: {e}"
    try:
        seen = mod.check_rater_objects("candidate", objs, batch_ids, rate_red_flags)
    except AssertionError as e:
        return None, f"{cause_of(str(e))}: {e}"
    missing = sorted(set(batch_ids) - set(seen))
    extra = sorted(set(seen) - set(batch_ids))
    if missing or extra:
        return None, f"chunk_id_set_mismatch: missing={missing} extra={extra}"
    return objs, None


def selftest():
    """One good and five bad candidates against a synthetic 3-chunk batch.

    Five, not the four asked for, because the coverage case (a dropped row)
    exercises the set-equality check this file ADDS on top of the imported
    guard; without it that check is untested.
    """
    mod = load_analyze()
    ids = ["E2CHK-aaa", "E2CHK-bbb", "E2CHK-ccc"]
    good = [{"chunk_id": c, "sentiment": "NEUTRAL", "guidance_direction": "NONE",
             "red_flags": [], "reason": "synthetic"} for c in ids]
    no_cid = copy.deepcopy(good); no_cid[0].pop("chunk_id")
    na = copy.deepcopy(good); na[1]["sentiment"] = "n/a"
    verdict = copy.deepcopy(good); verdict[2]["verdict"] = "agree"
    cases = [
        ("good (fenced)", "```json\n" + json.dumps(good) + "\n```", "OK"),
        ("prose-wrapped non-JSON", "Here are my verdicts:\n" + json.dumps(good), "non_parsing_json"),
        ("missing chunk_id key", json.dumps(no_cid), "missing_required_field"),
        ("'n/a' sentiment", json.dumps(na), "schema_violation"),
        ("extra 'verdict' key", json.dumps(verdict), "schema_violation"),
        ("dropped row (extra case)", json.dumps(good[:2]), "chunk_id_set_mismatch"),
    ]
    bad = 0
    for name, text, want in cases:
        objs, err = validate(text, set(ids), mod)
        got = "OK" if err is None else err.split(":", 1)[0]
        assert want == "OK" or want in mod.FAILED_BATCH_CAUSES, want
        if got == want and (want != "OK" or objs == good):
            print(f"  ok: {name} -> {got}")
        else:
            bad += 1
            print(f"  FAILED: {name} -> {got} (expected {want})")
    print("SELFTEST PASSED" if not bad else f"SELFTEST FAILED — {bad} case(s)")
    return 0 if not bad else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate one G2 rater candidate.")
    for name in ("candidate", "batch", "out"):
        ap.add_argument(name, nargs="?")
    ap.add_argument("--no-red-flags", action="store_true", help="B-lite key set")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not (a.candidate and a.batch and a.out):
        ap.error("need <candidate_text_file> <batch_file> <out_path>")
    batch_ids = {o["chunk_id"] for o in json.loads(Path(a.batch).read_text())}
    objs, err = validate(Path(a.candidate).read_text(), batch_ids,
                         load_analyze(), not a.no_red_flags)
    if err:
        if err.startswith("non_parsing_json"):
            print("FAIL non_parsing_json")
            print(err, file=sys.stderr)
            return 2
        print("FAIL " + err)
        return 3
    out = Path(a.out)
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(objs, indent=1, ensure_ascii=False) + "\n")
    os.replace(tmp, out)
    print(f"OK {len(objs)} rows -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
