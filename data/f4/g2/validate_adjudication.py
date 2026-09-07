#!/usr/bin/env python3
"""validate_adjudication.py — gate one adjudicator candidate into adjudications/.

usage: python3 data/f4/g2/validate_adjudication.py CANDIDATE ADJ_BATCH OUT
       python3 data/f4/g2/validate_adjudication.py --merge
       python3 data/f4/g2/validate_adjudication.py --selftest

Schema = design §10.2.2, plus §5.3's rule that red_flags NEVER escalates to the
owner (needs_human is false on every red_flags row) and §10.2.4's requirement
that an `unsure` row carry no reference. Enum vocabularies are IMPORTED from
analyze_g2.py, never re-typed here, so the writer and the analysis cannot drift.

Nothing is repaired, reordered or filled in — a repaired adjudication is a
fabricated one (design §11.3). The only normalization is stripping whitespace
and ONE optional markdown fence before parsing.

Exit 0 written / 2 non-parsing JSON / 3 rejected. 0 API calls, 0 network.
"""

import argparse
import importlib.util
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

G2 = Path("/Users/vihanpatil/personal/projects/FinScreen/data/f4/g2")
ADJ_DIR = G2 / "adjudications"
BATCH_DIR = G2 / "adjudicator_batches"
KEYS = {"chunk_id", "field", "verdict", "correct_label", "confidence", "brief",
        "pattern", "needs_human"}
VERDICTS = ("agree", "disagree", "unsure")
CONFIDENCE = ("high", "medium", "low")
MODALITIES = ("HYPOTHETICAL", "REALIZED")
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def load_analyze():
    spec = importlib.util.spec_from_file_location("analyze_g2", G2 / "analyze_g2.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def label_ok(mod, field, cl):
    """Is `cl` an admissible correct_label for `field` (verdict != unsure)?"""
    if field == mod.RED:
        return isinstance(cl, list) and all(
            isinstance(e, list) and len(e) == 2
            and e[0] in mod.CATS and e[1] in MODALITIES for e in cl)
    return cl in (mod.SENTIMENT_VALUES if field == "sentiment" else mod.GUIDANCE_VALUES)


def check(o, mod):
    """One row -> None if clean, else the schema_violation detail."""
    if set(o) != KEYS:
        return f"key set {sorted(o)} != {sorted(KEYS)}"
    if o["field"] not in mod.FIELDS_ALL:
        return f"field {o['field']!r} is not one of {list(mod.FIELDS_ALL)}"
    if o["verdict"] not in VERDICTS:
        return f"verdict {o['verdict']!r} not in {list(VERDICTS)}"
    if o["confidence"] not in CONFIDENCE:
        return f"confidence {o['confidence']!r} not in {list(CONFIDENCE)}"
    if not isinstance(o["needs_human"], bool):
        return f"needs_human {o['needs_human']!r} is not a bool"
    if not (isinstance(o["pattern"], str) and SLUG.match(o["pattern"])):
        return f"pattern {o['pattern']!r} is not a kebab-case slug"
    if not (isinstance(o["brief"], str) and o["brief"].strip()):
        return f"brief {o['brief']!r} is not a non-empty string"
    if o["field"] == mod.RED and o["needs_human"]:
        return "needs_human=true on a red_flags row — red_flags never escalates (§5.3)"
    if o["verdict"] == "unsure":
        if not o["needs_human"]:
            return "verdict=unsure with needs_human=false (§10.2.4: unsure is non-evaluable)"
        if o["correct_label"] is not None:
            return f"verdict=unsure with a non-null correct_label {o['correct_label']!r}"
    elif not label_ok(mod, o["field"], o["correct_label"]):
        return f"correct_label {o['correct_label']!r} is not admissible for {o['field']}"
    return None


def validate(text, pairs, mod):
    """Return (rows, None) on success, else (None, '<cause>: <detail>')."""
    t = text.strip()
    if t.startswith("```") and t.endswith("```") and "\n" in t:
        t = t[t.index("\n") + 1:-3].strip()
    try:
        doc = json.loads(t)
    except ValueError as e:
        return None, f"non_parsing_json: {e}"
    rows = doc.get("rows") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        return None, "non_parsing_json: candidate is neither a JSON array nor {'rows': [...]}"
    for o in rows:
        if not isinstance(o, dict):
            return None, f"schema_violation: non-object row {o!r}"
        detail = check(o, mod)
        if detail:
            return None, f"schema_violation: {o.get('chunk_id')}/{o.get('field')}: {detail}"
    got = [(o["chunk_id"], o["field"]) for o in rows]
    dupes = sorted(p for p, c in Counter(got).items() if c > 1)
    missing, extra = sorted(pairs - set(got)), sorted(set(got) - pairs)
    if dupes or missing or extra:
        return None, (f"pair_set_mismatch: missing={missing} extra={extra} "
                      f"duplicates={dupes}")
    return rows, None


def pairs_of(path):
    return {(o["chunk_id"], o["field"]) for o in json.loads(Path(path).read_text())}


def write_atomic(rows, out):
    tmp = out.with_name(out.name + ".tmp")
    tmp.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
    os.replace(tmp, out)
    print(f"OK {len(rows)} rows -> {out}")


def merge():
    """Concatenate adj_batch_NN_result.json in batch order into adjudications.json."""
    rows, want, missing = [], set(), []
    for b in sorted(BATCH_DIR.glob("adj_batch_[0-9][0-9].json")):
        want |= pairs_of(b)
        result = ADJ_DIR / (b.stem + "_result.json")
        if result.exists():
            rows += json.loads(result.read_text())
        else:
            missing.append(result.name)
    if missing:
        print("FAIL missing_batch_results: " + " ".join(missing))
        return 3
    got = [(o["chunk_id"], o["field"]) for o in rows]
    dupes = sorted(p for p, c in Counter(got).items() if c > 1)
    missing, extra = sorted(want - set(got)), sorted(set(got) - want)
    if dupes or missing or extra:
        print(f"FAIL pair_set_mismatch: {len(got)} merged rows vs {len(want)} batch "
              f"pairs; missing={missing} extra={extra} duplicates={dupes}")
        return 3
    for f in sorted({o["field"] for o in rows}):
        sub = [o for o in rows if o["field"] == f]
        c = Counter(o["verdict"] for o in sub)
        nh = sum(1 for o in sub if o["needs_human"])
        print(f"  {f:18s} n={len(sub):4d}  "
              + "  ".join(f"{v}={c[v]}" for v in VERDICTS) + f"  needs_human={nh}")
    write_atomic(rows, ADJ_DIR / "adjudications.json")
    return 0


def selftest():
    """One good and three bad candidates against a synthetic 3-row adj batch."""
    mod = load_analyze()
    batch = [("E2CHK-aaa", "sentiment"), ("E2CHK-bbb", "guidance_direction"),
             ("E2CHK-ccc", "red_flags")]
    labels = {"sentiment": "NEGATIVE", "guidance_direction": "NONE",
              "red_flags": [["DEMAND_WEAKNESS", "REALIZED"]]}
    good = [{"chunk_id": c, "field": f, "verdict": "disagree",
             "correct_label": labels[f], "confidence": "high",
             "brief": "synthetic", "pattern": "synthetic-case",
             "needs_human": False} for c, f in batch]
    bad_rf = json.loads(json.dumps(good))
    bad_rf[2]["needs_human"] = True                    # §5.3 violation
    cases = [
        ("good (fenced, {'rows': ...})",
         "```json\n" + json.dumps({"rows": good}) + "\n```", "OK"),
        ("prose-wrapped non-JSON", "Here you go:\n" + json.dumps(good), "non_parsing_json"),
        ("dropped row", json.dumps(good[:2]), "pair_set_mismatch"),
        ("needs_human on red_flags", json.dumps(bad_rf), "schema_violation"),
    ]
    bad = 0
    for name, text, want in cases:
        rows, err = validate(text, set(batch), mod)
        got = "OK" if err is None else err.split(":", 1)[0]
        if got == want and (want != "OK" or rows == good):
            print(f"  ok: {name} -> {got}")
        else:
            bad += 1
            print(f"  FAILED: {name} -> {got} (expected {want})")
    print("SELFTEST PASSED" if not bad else f"SELFTEST FAILED — {bad} case(s)")
    return 0 if not bad else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate one G2 adjudicator candidate.")
    for name in ("candidate", "adj_batch", "out"):
        ap.add_argument(name, nargs="?")
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.merge:
        return merge()
    if not (a.candidate and a.adj_batch and a.out):
        ap.error("need <candidate_json_file> <adj_batch_file> <out_path>")
    rows, err = validate(Path(a.candidate).read_text(), pairs_of(a.adj_batch),
                         load_analyze())
    if err:
        print("FAIL " + err)
        return 2 if err.startswith("non_parsing_json") else 3
    write_atomic(rows, Path(a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
