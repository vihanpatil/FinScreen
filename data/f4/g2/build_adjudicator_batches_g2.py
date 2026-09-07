"""
build_adjudicator_batches_g2.py — turn the G2 blind rater's disagreements into
label-adjudicator batches (design §10.3 step 3, schema §10.2.2).

Mechanical: no judgement here. A (chunk, field) cell is CONTESTED iff the
stored student label differs from blind rater A's own label on a field the
§1.2 applicability matrix asks for on that chunk's section_type. The rater
never saw the stored label and never self-reported agreement (§5.1), so this
comparison is made here, in code.

Design: data/f4/g2/G2_SPOTCHECK_design.md (pre-registered 2026-09-06;
parameters owner-ratified 2026-09-07 §14; this script APPROVED §14.1 item 3.2).
Precedent: data/hardening/spotcheck_v12/build_adjudicator_batches_v12.py.

READS (all READ-ONLY; nothing under data/f4/ is ever written except this
script's own output directory):
  data/f4/g2/draw_g2.csv                    rank,batch,chunk_id (§14.9:
                                            `arm` moved out of this tree)
  data/f4/g2/draw_manifest.json             rate_red_flags (Option C: true)
  data/f4/g2/batches/batch_NN.json          {chunk_id,text} — the passage the
                                            rater actually saw, reused verbatim
  data/f4/g2/verdicts/rater_a_batchNN.json  §10.2.1 blind rater A
  data/f4/labels_e2_v1.parquet              stored student labels (joined here)
  data/f4/chunks_v1.parquet                 section_type only (the mask)

WRITES (only inside data/f4/g2/adjudicator_batches/):
  adj_batch_NN.json           JSON array, ≤ 40 objects, key set EXACTLY
                              {chunk_id, field, text, stored_label, rater_label}
                              (§10.2.2). No section_type, no sector, no cik, no
                              filing date, no company name, no arm, no batch.
  adj_manifest_g2.json        counts per field + provenance.

Three pinned choices, each with its citation, so no one has to re-derive them:

  * §1.2 masking. sentiment is evaluable on MDA / EX99_PRESS_RELEASE,
    guidance_direction on EX99_PRESS_RELEASE, red_flags on MDA /
    RISK_FACTORS / EX99_PRESS_RELEASE. Off-matrix rater values are collected
    and DISCARDED — that is what keeps the rater blind, not waste.
  * §1.3 omissions. A stored null on an applicable field is PRE-REGISTERED as
    an error; analyze_g2.py scores it `omission_pinned_error` and explicitly
    IGNORES any adjudication on such a row. Sending them to an adjudicator
    would buy nothing and would ask it whether a null is "correct", so they
    are excluded here and counted in the manifest instead. `guidance_imputed
    _none=true` rows carry a stored "NONE" and are compared as NONE (§1.3
    writer rule); branch on the stored columns, never on `schema_valid`.
  * §5.3 escalation. Gate-bearing fields (sentiment, guidance_direction) can
    escalate to the owner via the adjudicator's needs_human flag; `red_flags`
    NEVER escalates — it is adjudicator-final and disclosure-only (owner
    ruling 2026-08-27). Gate-bearing and red_flags rows are therefore batched
    separately, which is also how §9/§14.7 price the adjudicator runs.

ADJUDICATOR ANCHORING (disclosed, not closed — design §12 item 11, 2026-09-07):
the two candidates ship under the keys `stored_label` and `rater_label`, so the
adjudicator always knows which side is the student's incumbent label. Anchoring
on the incumbent biases adjudications toward "agree", which lowers measured
error and raises measured agreement — the same direction as the shared
model-family bias of §12.1. The key set is PINNED by §10.2.2, so closing this
(randomised label_a / label_b with the key map held outside the adjudicator's
view) is a schema amendment and an owner call, and it would have to be ruled
before rating, not after. It is therefore disclosed.

SCHEMA NOTE (2026-09-07): the blind rater's `reason` string is NOT carried
into the batch files. §10.2.2 pins the key set "exactly" at the five keys
above and this file is a pre-registered contract; adding a sixth key is an
owner call, not an implementer's. Recorded in adj_manifest_g2.json.notes.

distress_tier is never built, never scored, never mentioned to the adjudicator.
0 API calls, 0 GPU seconds, 0 network calls. System python3, pandas/stdlib.

    python3 data/f4/g2/build_adjudicator_batches_g2.py
    python3 data/f4/g2/build_adjudicator_batches_g2.py --selftest
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# ----------------------------------------------------------------- paths
ROOT = Path("/Users/vihanpatil/personal/projects/FinScreen")
G2 = ROOT / "data" / "f4" / "g2"
LABELS = ROOT / "data" / "f4" / "labels_e2_v1.parquet"   # READ-ONLY
CHUNKS = ROOT / "data" / "f4" / "chunks_v1.parquet"      # READ-ONLY

# ------------------------------------------------------------- constants
BATCH_SIZE = 40                 # §10.2.2: ≤ 40 contested rows per file
GATE_FIELDS = ("sentiment", "guidance_direction")
RED = "red_flags"
MISSING = "__MISSING_FIELD__"   # the finetune/eval.py omission sentinel (§1.3)
ADJ_KEYS = ("chunk_id", "field", "text", "stored_label", "rater_label")

# §1.2 applicability matrix — identical to analyze_g2.py's APPLICABLE.
APPLICABLE = {
    "sentiment": {"MDA", "EX99_PRESS_RELEASE"},
    "guidance_direction": {"EX99_PRESS_RELEASE"},
    RED: {"MDA", "RISK_FACTORS", "EX99_PRESS_RELEASE"},
}
# §5.3: red_flags verdicts are adjudicator-final; only gate-bearing rows can
# reach the owner. analyze_g2.py hard-fails on an owner ruling over red_flags.
ESCALATES_TO_OWNER = {"sentiment": True, "guidance_direction": True, RED: False}
FAMILY = {"sentiment": "gate_bearing", "guidance_direction": "gate_bearing",
          RED: "red_flags"}


# ------------------------------------------------------------- helpers
def as_set(flags):
    """Normalize red_flags to a frozenset of (CATEGORY, MODALITY)."""
    if flags is None or isinstance(flags, float):     # None / NaN from pandas
        return None
    out = []
    for e in flags:
        out.append((e["category"], e["modality"]) if isinstance(e, dict)
                   else (e[0], e[1]))
    return frozenset(out)


def stored_values(row, rate_red_flags):
    """Stored student label per field, with the §1.3 omission conventions."""
    out = {}
    s = row.get("sentiment")
    out["sentiment"] = s if isinstance(s, str) and s else MISSING
    g = row.get("guidance_direction")
    out["guidance_direction"] = g if isinstance(g, str) and g else MISSING
    if rate_red_flags:
        rf = as_set(row.get(RED))
        out[RED] = frozenset() if rf is None else rf
    return out


def jsonable(field, value):
    """Batch-file rendering of a label value: sets become sorted pair lists."""
    if field == RED:
        return [[c, m] for c, m in sorted(value)]
    return value


def contested_rows(draw_ids, stored, section_of, rater, text_of, fields):
    """The ordered contested (chunk, field) list, plus per-field counts.

    Order is the draw order of `draw_ids` then the `fields` order, so the same
    inputs always produce the same batches.
    """
    rows = []
    counts = {f: {"rated": 0, "masked": 0, "omission_excluded": 0,
                  "uncontested": 0, "contested": 0} for f in fields}
    for cid in draw_ids:
        if cid not in rater:                      # batch not rated yet
            continue
        sec = section_of.get(cid)
        for f in fields:
            c = counts[f]
            c["rated"] += 1
            if sec not in APPLICABLE[f]:          # §1.2 mask
                c["masked"] += 1
                continue
            sv = stored[cid][f]
            if sv == MISSING:                     # §1.3 pinned error
                c["omission_excluded"] += 1
                continue
            rv = rater[cid].get(f)
            if sv == rv:
                c["uncontested"] += 1
                continue
            c["contested"] += 1
            rows.append({"chunk_id": cid, "field": f, "text": text_of[cid],
                         "stored_label": jsonable(f, sv),
                         "rater_label": jsonable(f, rv)})
    return rows, counts


def split_batches(rows):
    """Batches of ≤ BATCH_SIZE rows, gate-bearing first, families never mixed
    (§5.3: only gate-bearing rows can escalate to the owner; §9 prices the two
    families as separate adjudicator runs)."""
    out = []
    for family in ("gate_bearing", RED):
        fam = [r for r in rows if FAMILY[r["field"]] == family]
        for i in range(0, len(fam), BATCH_SIZE):
            out.append((family, fam[i:i + BATCH_SIZE]))
    return out


def sha256_file(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rel_to_root(p):
    try:
        return str(Path(p).relative_to(ROOT))
    except ValueError:
        return str(p)                        # a test fixture path, never a repo path


def verdict_file(g2, b):
    """rater_a_batch01.json, with the underscore spelling as a fallback —
    the same two candidates analyze_g2.py accepts."""
    for cand in (f"rater_a_{b.replace('_', '')}.json", f"rater_a_{b}.json"):
        p = g2 / "verdicts" / cand
        if p.exists():
            return p
    return None


# ------------------------------------------------------------- main flow
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Build G2 adjudicator batches from blind rater A (read-only, $0).")
    ap.add_argument("--selftest", action="store_true",
                    help="run the in-memory contested-set check and exit")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    return build()


def build():
    out_dir = G2 / "adjudicator_batches"
    if not (G2 / "draw_g2.csv").exists() or not (G2 / "draw_manifest.json").exists():
        print("no draw yet — data/f4/g2/draw_g2.csv or draw_manifest.json is "
              "absent; design §10.3 step 1 has not run. Nothing built.")
        return 0

    man = json.loads((G2 / "draw_manifest.json").read_text())
    rate_red_flags = bool(man.get("rate_red_flags", True))
    fields = list(GATE_FIELDS) + ([RED] if rate_red_flags else [])

    draw = pd.read_csv(G2 / "draw_g2.csv")
    assert set(draw.columns) == {"rank", "batch", "chunk_id"}, \
        f"draw_g2.csv columns {sorted(draw.columns)} != rank,batch,chunk_id (§5.1/§14.9)"

    # ---- rater A verdicts; the passage text is reused from the rater's own batch
    rater, text_of, consumed, unrated = {}, {}, [], []
    for b in sorted(draw.batch.unique()):
        p = verdict_file(G2, b)
        if p is None:
            unrated.append(b)
            continue
        objs = json.loads(p.read_text())
        for o in objs:
            v = {"sentiment": o["sentiment"],
                 "guidance_direction": o["guidance_direction"]}
            if rate_red_flags:
                v[RED] = as_set(o[RED])
            rater[o["chunk_id"]] = v
        consumed.append({"file": f"verdicts/{p.name}", "n": len(objs),
                         "sha256": sha256_file(p)})
        bp = G2 / "batches" / f"{b}.json"
        for o in json.loads(bp.read_text()):
            text_of[o["chunk_id"]] = o["text"]

    if not rater:
        print("no verdicts yet — data/f4/g2/verdicts/rater_a_batchNN.json does "
              "not exist. Design §10.3 step 2 (blind rater agents) has not run; "
              "nothing is built and nothing is invented.")
        return 0
    if unrated:
        print(f"[WARN] {len(unrated)} of {draw.batch.nunique()} batches are "
              f"unrated and are skipped: {', '.join(unrated)}. Re-run this "
              "script when they land; chunks are never replaced (§11.3).")

    # ---- stored labels + the section_type mask, joined HERE and nowhere else.
    # Same sha re-check analyze_g2.py makes: a changed frame is a new
    # pre-registration, not a re-run.
    shas = {}
    for p in (LABELS, CHUNKS):
        rel = rel_to_root(p)
        shas[rel] = sha256_file(p)
        pinned = ((man.get("inputs") or {}).get(rel) or {}).get("sha256")
        if pinned and pinned != shas[rel]:
            raise AssertionError(f"{rel}: sha256 {shas[rel]} != draw_manifest.json "
                                 f"{pinned}. A changed frame is a new pre-registration.")

    drawn = set(draw.chunk_id)
    lab = pd.read_parquet(LABELS, columns=["chunk_id", "sentiment",
                                           "guidance_direction", RED])
    lab = lab[lab.chunk_id.isin(drawn)]
    stored = {r["chunk_id"]: stored_values(r, rate_red_flags)
              for r in lab.to_dict("records")}
    ch = pd.read_parquet(CHUNKS, columns=["chunk_id", "section_type"])
    ch = ch[ch.chunk_id.isin(drawn)]
    section_of = dict(zip(ch.chunk_id, ch.section_type))
    assert not any(s == "8K_BODY" for s in section_of.values()), \
        "8K_BODY row in the draw — excluded from the frame by predicate (§2.3)"
    missing_ids = [c for c in rater if c not in stored or c not in text_of]
    assert not missing_ids, f"rated chunks absent from labels/batches: {missing_ids[:5]}"

    rows, counts = contested_rows(list(draw.chunk_id), stored, section_of,
                                  rater, text_of, fields)
    batches = split_batches(rows)

    # ---- write
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in sorted(out_dir.glob("adj_batch_*.json")):
        stale.unlink()                       # this script's own prior output
    written = []
    for i, (family, rows_b) in enumerate(batches, start=1):
        for r in rows_b:
            assert tuple(r) == ADJ_KEYS, f"row key set {sorted(r)} != {list(ADJ_KEYS)} (§10.2.2)"
        name = f"adj_batch_{i:02d}.json"
        (out_dir / name).write_text(
            json.dumps(rows_b, indent=1, ensure_ascii=False) + "\n")
        per_field = {f: sum(1 for r in rows_b if r["field"] == f) for f in fields}
        written.append({"file": name, "family": family, "n": len(rows_b),
                        "escalates_to_owner": ESCALATES_TO_OWNER[rows_b[0]["field"]],
                        "fields": {k: v for k, v in per_field.items() if v}})

    manifest = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_by": "data/f4/g2/build_adjudicator_batches_g2.py",
        "design_doc": "data/f4/g2/G2_SPOTCHECK_design.md",
        "design_sections": ["10.3 step 3", "10.2.2", "1.2", "1.3", "5.3"],
        "rate_red_flags": rate_red_flags,
        "batch_size_cap": BATCH_SIZE,
        "n_drawn": int(len(draw)),
        "n_rated_chunks": len(rater),
        "unrated_batches": unrated,
        "verdicts_consumed": consumed,
        "inputs_read_only_sha256": shas,     # re-hashed here, matched to draw_manifest
        "draw_manifest_sha256": sha256_file(G2 / "draw_manifest.json"),
        "cells_by_field": counts,
        "contested_by_field": {f: counts[f]["contested"] for f in fields},
        "contested_rate_by_field": {
            f: (counts[f]["contested"] /
                (counts[f]["contested"] + counts[f]["uncontested"]))
            if (counts[f]["contested"] + counts[f]["uncontested"]) else None
            for f in fields},
        "escalates_to_owner": {f: ESCALATES_TO_OWNER[f] for f in fields},
        "batches": written,
        "notes": [
            "The contested RATE is not the error rate; it becomes one only after "
            "adjudication (analyze_g2.py §10.2.4).",
            "Omission rows (stored null on an applicable field) are EXCLUDED from "
            "adjudication and pre-registered as errors (§1.3); analyze_g2.py "
            "ignores any adjudication on them. They are counted in cells_by_field "
            "as omission_excluded.",
            "red_flags is EXPLORATORY / DISCLOSURE-ONLY (owner ruling 2026-08-27); "
            "its adjudications are final and never escalate to the owner (§5.3). "
            "Nothing here can re-promote it.",
            "distress_tier is never built or scored (HANDOFF §7).",
            "Batch objects carry the §10.2.2 key set exactly; the blind rater's "
            "`reason` string is NOT carried, because §10.2.2 pins the key set at "
            "five keys and widening a pre-registered contract is an owner call.",
        ],
        "api_calls": 0, "gpu_seconds": 0, "network_calls": 0,
    }
    (out_dir / "adj_manifest_g2.json").write_text(json.dumps(manifest, indent=1) + "\n")

    n_gate = sum(counts[f]["contested"] for f in GATE_FIELDS)
    print(f"rated {len(rater)}/{len(draw)} drawn chunks -> "
          f"{len(rows)} contested (chunk, field) rows in {len(written)} batch(es)")
    for f in fields:
        c = counts[f]
        den = c["contested"] + c["uncontested"]
        rate = f"{c['contested'] / den:.1%}" if den else "n/a"
        print(f"  {f:<19} contested {c['contested']:>4}/{den:<4} = {rate:<6} "
              f"(masked {c['masked']}, omissions excluded {c['omission_excluded']})"
              + ("" if ESCALATES_TO_OWNER[f] else "   [never escalates, §5.3]"))
    print(f"  gate-bearing contested = {n_gate}; written to {out_dir}")
    print("NOTE: contested is not error. Adjudication (design §10.3 step 4) turns "
          "these into verdicts; analyze_g2.py turns verdicts into rates.")
    return 0


# ------------------------------------------------------------- selftest
def selftest():
    """Two fabricated rater rows covering all three §10.2.4 dispositions:
    an agree cell, a contested cell, and a cell masked by applicability."""
    fields = list(GATE_FIELDS) + [RED]
    draw_ids = ["C1", "C2"]
    section_of = {"C1": "MDA", "C2": "EX99_PRESS_RELEASE"}
    stored = {
        # C1 (MDA): sentiment agrees; guidance is OFF-MATRIX on MDA -> masked
        "C1": stored_values({"sentiment": "NEUTRAL", "guidance_direction": "NONE",
                             RED: []}, True),
        # C2 (EX99): sentiment differs -> the one contested cell
        "C2": stored_values({"sentiment": "POSITIVE", "guidance_direction": "RAISED",
                             RED: [{"category": "DEMAND_WEAKNESS",
                                    "modality": "HYPOTHETICAL"}]}, True),
    }
    rater = {
        "C1": {"sentiment": "NEUTRAL", "guidance_direction": "LOWERED",
               RED: frozenset()},
        "C2": {"sentiment": "NEGATIVE", "guidance_direction": "RAISED",
               RED: frozenset({("DEMAND_WEAKNESS", "HYPOTHETICAL")})},
    }
    text_of = {"C1": "passage one", "C2": "passage two"}
    rows, counts = contested_rows(draw_ids, stored, section_of, rater, text_of, fields)

    got = [(r["chunk_id"], r["field"]) for r in rows]
    assert got == [("C2", "sentiment")], got
    assert counts["sentiment"] == {"rated": 2, "masked": 0, "omission_excluded": 0,
                                   "uncontested": 1, "contested": 1}, counts["sentiment"]
    # C1's guidance disagrees loudly (NONE vs LOWERED) and is masked anyway.
    assert counts["guidance_direction"]["masked"] == 1
    assert counts["guidance_direction"]["contested"] == 0
    assert counts[RED]["contested"] == 0 and counts[RED]["uncontested"] == 2
    assert tuple(rows[0]) == ADJ_KEYS
    assert rows[0]["stored_label"] == "POSITIVE" and rows[0]["rater_label"] == "NEGATIVE"

    # An omission is excluded from adjudication and counted, never contested (§1.3).
    stored["C2"]["sentiment"] = MISSING
    rows2, counts2 = contested_rows(draw_ids, stored, section_of, rater, text_of, fields)
    assert rows2 == [] and counts2["sentiment"]["omission_excluded"] == 1

    # The ≤40 cap and the family split.
    many = [{"chunk_id": f"X{i}", "field": "sentiment", "text": "t",
             "stored_label": "POSITIVE", "rater_label": "NEGATIVE"} for i in range(41)]
    many += [{"chunk_id": "Y", "field": RED, "text": "t",
              "stored_label": [], "rater_label": [["DEMAND_WEAKNESS", "REALIZED"]]}]
    b = split_batches(many)
    assert [(fam, len(rs)) for fam, rs in b] == [("gate_bearing", 40),
                                                 ("gate_bearing", 1), (RED, 1)], b
    print("selftest OK — contested set {('C2','sentiment')}; masking, the §1.3 "
          "omission exclusion, the 40-row cap and the §5.3 family split all hold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
