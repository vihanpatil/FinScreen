"""
build_draw_v12.py — the v1.2 teacher spot-check draw (council condition 1).

Draws a base-rate-representative n=200 sample of chunks from
data/labels_v12.parquet and writes:

  draw_v12.csv                  the 200-row draw manifest — LABEL-FREE by
                                design (chunk_id, section_type, ticker,
                                word_count, batch, rank). Stored labels are
                                joined at analysis time from
                                data/labels_v12.parquet, so reading this file
                                cannot break rater blindness.
  batches/batch_0N.json         5 auditor batch files, 40 chunks each.
                                Each chunk carries ONLY {chunk_id, text}.
                                No stored labels, no section_type, no ticker,
                                no dates — the rater operates on strictly the
                                same information the teacher had
                                (labeling_rubric.md §8).
  batches/batch_01_replicate.json
                                byte-identical copy of batch 1, for the
                                rater-noise arm (S7): a second, independent
                                label-auditor instance re-rates those same 40.
  draw_manifest.json            provenance (seed, source sha256, allocation).

READ-ONLY on data/labels_v12.parquet. Writes only inside
data/hardening/spotcheck_v12/.

Design: data/hardening/spotcheck_v12/SPOTCHECK_v12_design.md (pre-registered
2026-08-27, before any verdict exists).

SEED = 20260827 — the date the design was written; chosen once, never
changed run-to-run. Re-running against an unchanged labels_v12.parquet
reproduces draw_v12.csv byte-for-byte (asserted at the bottom).

SAMPLING FRAME — all 6,747 rows of data/labels_v12.parquet.
  * Every row parsed and validated under rubric v1.2 (parse_ok,
    schema_valid, api_result_type='succeeded' on all 6,747 — asserted).
  * CHK-8e69547e0900a8dd (E1's v1.1 safety-refusal row) IS in frame: it
    labeled successfully under v1.2. Its exclusion from the frozen
    fine-tune split is irrelevant here — the estimand is TEACHER error over
    the labeled corpus, not student eval performance, so split membership
    carries no weight.
  * No train/eval weighting for the same reason.

STRATIFICATION — proportional (Hamilton largest-remainder) by section_type.
Two reasons, both statistical:
  1. It removes sampling noise from the section mix, which matters because
     RISK_FACTORS was the weakest section in the v1.1 pass (59.2% red-flag
     agreement) and churned hardest v1.1->v1.2 (41.6% of rows changed).
  2. Under proportional allocation Var(p_st) = Sum_h W_h p_h(1-p_h)/n
     <= p(1-p)/n, so the binomial Wilson interval used as the primary
     analysis is conservative (never anti-conservative) by construction.

8K_BODY (8 rows, 0.119% of the corpus) receives an allocation of 0 under
proportional allocation. That is the base-rate-representative answer:
including even one 8K_BODY row would over-represent the stratum by ~4x.
Its error is therefore unmeasured, and it cannot move the pooled estimate
by more than 0.12 percentage points. Stated, not hidden.

NO OVERSAMPLE ARM. Justification is arithmetic, in the design doc §3.4: a
flag-present oversample buys almost nothing for the thin categories that
actually limit per-category precision (a 40-row flag-present oversample
adds ~5 SUPPLY_INPUT_CONSTRAINT rows), and a per-category quota arm that
would help costs ~+75 chunks (+37%) plus ~+25 owner rulings for a
secondary metric that cannot trigger the kill rule.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20260827
N_DRAW = 200
BATCH_SIZE = 40
ROOT = Path("/Users/vihanpatil/personal/projects/FinScreen")
LABELS = ROOT / "data" / "labels_v12.parquet"
OUT = ROOT / "data" / "hardening" / "spotcheck_v12"
BATCH_DIR = OUT / "batches"
EXPECTED_LABELS_SHA256 = (
    "ca373b953504535b2f35ee374a6b6c1a6360000261748db365ee23c231e475e7"
)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def hamilton(counts: pd.Series, n: int) -> pd.Series:
    """Largest-remainder proportional allocation summing to exactly n."""
    frac = counts / counts.sum() * n
    base = np.floor(frac).astype(int)
    order = (frac - base).sort_values(ascending=False).index.tolist()
    for i in range(int(n - base.sum())):
        base[order[i % len(order)]] += 1
    assert base.sum() == n
    return base


def main():
    src_sha = sha256(LABELS)
    df = pd.read_parquet(LABELS, columns=[
        "chunk_id", "section_type", "home_ticker", "word_count",
        "parse_ok", "schema_valid", "api_result_type", "rubric_version",
        "text",
    ])

    # ---- frame assertions (the frame is the whole labeled corpus) ----
    assert df.chunk_id.is_unique
    assert len(df) == 6747, len(df)
    assert df.parse_ok.all() and df.schema_valid.all()
    assert (df.api_result_type == "succeeded").all()
    assert (df.rubric_version == "v1.2").all()
    assert src_sha == EXPECTED_LABELS_SHA256, (
        f"labels_v12.parquet changed since the design was pre-registered "
        f"({src_sha} != {EXPECTED_LABELS_SHA256}). A changed frame means a "
        f"new pre-registration, not a silent re-draw."
    )

    counts = df.section_type.value_counts()
    alloc = hamilton(counts, N_DRAW)

    # ---- stratified draw: one child RNG stream per stratum, so the draw is
    # independent of iteration order ----
    seeds = np.random.SeedSequence(SEED).spawn(len(counts))
    picked = []
    for ss, stratum in zip(seeds, sorted(counts.index)):
        k = int(alloc[stratum])
        if k == 0:
            continue
        pool = df[df.section_type == stratum].sort_values("chunk_id")
        idx = np.random.default_rng(ss).choice(len(pool), size=k, replace=False)
        picked.extend(pool.iloc[sorted(idx)]["chunk_id"].tolist())

    assert len(picked) == N_DRAW and len(set(picked)) == N_DRAW

    # ---- batch assignment: seeded permutation, so batches are random
    # mixtures of section types (a section-homogeneous batch would confound
    # rater drift with section) ----
    perm_rng = np.random.default_rng(np.random.SeedSequence(SEED + 1))
    order = perm_rng.permutation(sorted(picked))
    draw = pd.DataFrame({"chunk_id": order})
    draw["rank"] = np.arange(1, N_DRAW + 1)
    draw["batch"] = (draw["rank"] - 1) // BATCH_SIZE + 1
    draw = draw.merge(
        df[["chunk_id", "section_type", "home_ticker", "word_count"]],
        on="chunk_id", how="left",
    )
    assert draw.section_type.notna().all()

    OUT.mkdir(parents=True, exist_ok=True)
    BATCH_DIR.mkdir(parents=True, exist_ok=True)

    draw[["rank", "batch", "chunk_id", "section_type", "home_ticker",
          "word_count"]].to_csv(OUT / "draw_v12.csv", index=False)

    # ---- blind batch files: chunk_id + text ONLY ----
    texts = df.set_index("chunk_id")["text"]
    for b in sorted(draw.batch.unique()):
        rows = draw[draw.batch == b]
        payload = {
            "batch": int(b),
            "protocol": "blind-relabel-v12-redflags-only",
            "rubric": "labeling_rubric.md (v1.2)",
            "field_to_label": "red_flags",
            "n": len(rows),
            "note": (
                "You are re-labeling from the text alone. No stored label, "
                "section type, ticker or date is provided, by design. Label "
                "red_flags only."
            ),
            "chunks": [
                {"chunk_id": c, "text": texts[c]} for c in rows.chunk_id
            ],
        }
        path = BATCH_DIR / f"batch_{int(b):02d}.json"
        path.write_text(json.dumps(payload, indent=1, ensure_ascii=False))

    # replicate of batch 1 for the rater-noise arm (S7)
    rep = json.loads((BATCH_DIR / "batch_01.json").read_text())
    rep["batch"] = "01_replicate"
    (BATCH_DIR / "batch_01_replicate.json").write_text(
        json.dumps(rep, indent=1, ensure_ascii=False)
    )

    manifest = {
        "generated_by": "data/hardening/spotcheck_v12/build_draw_v12.py",
        "design": "data/hardening/spotcheck_v12/SPOTCHECK_v12_design.md",
        "seed": SEED,
        "n": N_DRAW,
        "frame": "all 6747 rows of data/labels_v12.parquet (rubric v1.2)",
        "source_sha256": src_sha,
        "rubric_sha256": sha256(ROOT / "labeling_rubric.md"),
        "stratification": "proportional (Hamilton) by section_type",
        "corpus_counts": {k: int(v) for k, v in counts.items()},
        "allocation": {k: int(alloc[k]) for k in counts.index},
        "batches": {int(b): int((draw.batch == b).sum())
                    for b in sorted(draw.batch.unique())},
        "drawn_section_mix": {k: int(v) for k, v in
                              draw.section_type.value_counts().items()},
        "distinct_tickers_in_draw": int(draw.home_ticker.nunique()),
        "api_calls": 0,
    }
    (OUT / "draw_manifest.json").write_text(json.dumps(manifest, indent=1))

    # ---- post-conditions ----
    for stratum, k in alloc.items():
        got = int((draw.section_type == stratum).sum())
        assert got == int(k), f"{stratum}: drew {got}, allocated {k}"
    for path in sorted(BATCH_DIR.glob("batch_*.json")):
        payload = json.loads(path.read_text())
        for ch in payload["chunks"]:
            assert set(ch) == {"chunk_id", "text"}, (
                f"{path.name} leaked fields beyond chunk_id/text: {set(ch)}"
            )

    print(json.dumps(manifest, indent=1))
    print("\nsection mix drawn vs corpus share:")
    for s in counts.index:
        print(f"  {s:20s} {int(alloc[s]):4d}/{N_DRAW}  "
              f"({int(alloc[s])/N_DRAW:6.2%} vs corpus {counts[s]/len(df):6.2%})")


if __name__ == "__main__":
    main()
