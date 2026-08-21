"""
split.py — Week 4 held-out eval split, carved before any training artifacts
exist (ROADMAP Week 4 / DISCOVERY.md §5).

Reads (read-only): ../data/labels.parquet, ../data/paragraph_occurrence_map.parquet
Writes: splits/manifest.parquet (chunk_id -> split), splits/train.parquet,
        splits/eval.parquet (full label rows, split for convenience only —
        the manifest is the source of truth).

Leakage rule (binding)
-----------------------
A chunk's text is built (chunk.py) from deduplicated paragraphs that can
recur, verbatim, across many filings (see paragraph_occurrence_map.parquet
and each chunk's own `source_accession_numbers`, which is already the union
of every filing any constituent paragraph appears in anywhere in the
corpus — chunk.py's `flush()` computes this at build time, no re-derivation
needed here).

Two chunks that share ANY paragraph_id, or that share ANY source accession
number, must not straddle the train/eval boundary — if they did, the model
could see (a slight paraphrase of) an eval passage during training just
because it recurred in a different filing that happened to land in train.

We therefore build an undirected graph over chunk_ids:
  - edge (c1, c2) if c1 and c2 share a paragraph_id
  - edge (c1, c2) if c1 and c2 share a source_accession_number
and split at the CONNECTED-COMPONENT level, never at the row level. Every
chunk in a component goes to the same side.

Exclusions
----------
- Rows failing `parse_ok & schema_valid` are dropped entirely (neither train
  nor eval) — currently exactly 1 row, CHK-8e69547e0900a8dd. See
  SPLIT_DESIGN.md for why "excluded via the refusal chunk_id" is the wrong
  frame: the underlying predicate is truncation/parse failure, not a content
  refusal, verified directly against parse_error / schema_valid, and this
  script asserts that predicate drops exactly 1 row rather than hardcoding
  the chunk_id (check_leakage.py re-asserts this).
- distress_tier is NOT excluded from the split or from either output
  parquet (it stays as a data column) — it is excluded from TRAINING
  TARGETS in prepare_dataset.py and from headline eval metrics in eval.py,
  per DISCOVERY.md §3. Keeping the column here just means downstream
  scripts have it available if they ever want to report it separately.

Split-axis decision: see SPLIT_DESIGN.md for the full company/time
analysis. Summary: connected-component-level split, stratified to preserve
rare labels in eval, NOT additionally partitioned by company or by time —
documented as an explicit limitation relative to the Week 5 walk-forward
design (DISCOVERY.md §5), not silently glossed over.

Run: `python3 split.py` from the finetune/ directory or repo root (path
resolution handles either).
"""

from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

SEED = 42
EVAL_FRACTION = 0.15  # target share of *chunks* (not components) in eval

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
LABELS_PATH = REPO_ROOT / "data" / "labels.parquet"
SPLITS_DIR = HERE / "splits"

# Rare-label stratification targets: (source_column, label_value) -> target
# eval fraction of *occurrences* of that label. WITHDRAWN (n=1 in the whole
# corpus) cannot be split at all — it's handled as a special case below, not
# silently included in this dict as if a fractional target were meaningful.
GUIDANCE_STRATIFY = {"RAISED": 0.20, "MAINTAINED": 0.20, "LOWERED": 0.20}
RED_FLAG_STRATIFY_TARGET = 0.15  # applied to all 6 red-flag categories
DISTRESS_STRATIFY_TARGET = 0.15  # informational only; distress excluded from training


class UnionFind:
    def __init__(self, items):
        self.parent = {x: x for x in items}

    def find(self, x):
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def build_components(df: pd.DataFrame) -> dict[str, list[str]]:
    """Connected components over shared paragraph_id / shared source
    accession number. Returns {component_root: [chunk_id, ...]}."""
    uf = UnionFind(df["chunk_id"].tolist())

    para_owner: dict[str, str] = {}
    acc_owner: dict[str, str] = {}
    for row in df.itertuples(index=False):
        cid = row.chunk_id
        for pid in row.paragraph_ids:
            if pid in para_owner:
                uf.union(cid, para_owner[pid])
            else:
                para_owner[pid] = cid
        for acc in row.source_accession_numbers:
            if acc in acc_owner:
                uf.union(cid, acc_owner[acc])
            else:
                acc_owner[acc] = cid

    comps: dict[str, list[str]] = defaultdict(list)
    for cid in df["chunk_id"]:
        comps[uf.find(cid)].append(cid)
    return comps


def label_occurrence_index(df: pd.DataFrame) -> dict[str, list[str]]:
    """chunk_id -> list of stratification keys present in that chunk, e.g.
    'guidance:RAISED', 'redflag:DEMAND_WEAKNESS', 'distress:LIQUIDITY_STRESS'."""
    idx: dict[str, list[str]] = defaultdict(list)
    for row in df.itertuples(index=False):
        gd = row.guidance_direction
        if gd is not None and gd not in (None, "NONE"):
            idx[row.chunk_id].append(f"guidance:{gd}")
        for item in row.red_flags:
            idx[row.chunk_id].append(f"redflag:{item['category']}")
        for item in row.distress_tier:
            idx[row.chunk_id].append(f"distress:{item['category']}")
    return idx


def stratified_component_split(
    comps: dict[str, list[str]],
    chunk_labels: dict[str, list[str]],
    seed: int = SEED,
) -> dict[str, str]:
    """Assign each component to 'train' or 'eval'.

    Strategy: greedily satisfy rare-label eval quotas first (processing rarest
    categories first, assigning whole components containing that label to
    eval until the quota is met or no more unassigned components carry it),
    then randomly assign remaining components to hit the overall
    EVAL_FRACTION of total chunks. Fixed seed -> reproducible.
    """
    rng = random.Random(seed)

    # component -> total chunk count, and label -> set of components with it
    comp_size = {root: len(cids) for root, cids in comps.items()}
    comp_labels: dict[str, set[str]] = {}
    label_to_comps: dict[str, set[str]] = defaultdict(set)
    for root, cids in comps.items():
        labels_here = set()
        for cid in cids:
            labels_here.update(chunk_labels.get(cid, []))
        comp_labels[root] = labels_here
        for lb in labels_here:
            label_to_comps[lb].add(root)

    # total occurrence counts per label, across all chunks (not components)
    total_label_chunk_counts = Counter()
    for cid, labs in chunk_labels.items():
        for lb in set(labs):
            total_label_chunk_counts[lb] += 1

    assignment: dict[str, str] = {}  # component root -> 'train'/'eval'
    total_chunks = sum(comp_size.values())
    eval_budget = int(round(total_chunks * EVAL_FRACTION))
    eval_chunks_assigned = 0

    def targets_for(prefix: str, per_label_target: dict[str, float] | float):
        """Yield (label, target_fraction) pairs for labels with this prefix."""
        for lb, comps_with in label_to_comps.items():
            if not lb.startswith(prefix):
                continue
            frac = (
                per_label_target
                if isinstance(per_label_target, float)
                else per_label_target.get(lb.split(":", 1)[1])
            )
            if frac is None:
                continue
            yield lb, frac

    # Ordered stratification passes: guidance (rarest, most important) first,
    # then red flags, then distress (informational only).
    passes = []
    for lb, frac in targets_for("guidance:", GUIDANCE_STRATIFY):
        passes.append((lb, frac))
    for lb, frac in targets_for("redflag:", RED_FLAG_STRATIFY_TARGET):
        passes.append((lb, frac))
    for lb, frac in targets_for("distress:", DISTRESS_STRATIFY_TARGET):
        passes.append((lb, frac))

    # Sort rarest-first (smallest total occurrence count first) so scarce
    # labels get first claim on which components go to eval.
    passes.sort(key=lambda p: total_label_chunk_counts[p[0]])

    for lb, frac in passes:
        total_count = total_label_chunk_counts[lb]
        target_count = max(1, round(total_count * frac)) if total_count > 0 else 0
        # Prefer SMALLEST components first when satisfying a rare-label
        # quota. Components here turn out to be almost entirely
        # single-company (see SPLIT_DESIGN.md — within-company boilerplate
        # reuse chains a company's own chunks into one big component), so
        # an unweighted/random choice here would tend to dump one or two
        # entire large companies into eval to hit a quota cheaply on
        # *label count* while actually spending a huge, lopsided chunk
        # budget and starving ticker diversity. Smallest-first spends the
        # eval budget more evenly across more distinct companies.
        candidate_comps = sorted(
            label_to_comps[lb], key=lambda root: (comp_size[root], rng.random())
        )

        cur_count = sum(
            1
            for root in candidate_comps
            if assignment.get(root) == "eval"
            for cid in comps[root]
            if lb in set(chunk_labels.get(cid, []))
        )
        for root in candidate_comps:
            if cur_count >= target_count:
                break
            if root in assignment:
                continue  # already assigned by an earlier (rarer) pass
            # don't blow the overall eval budget too far past target
            if eval_chunks_assigned + comp_size[root] > eval_budget * 1.5:
                continue
            assignment[root] = "eval"
            eval_chunks_assigned += comp_size[root]
            cur_count += sum(
                1
                for cid in comps[root]
                if lb in set(chunk_labels.get(cid, []))
            )

    # Remaining components: smallest-first (same diversity rationale as
    # above) with a seeded random tie-break, to hit the overall fraction
    # while spreading eval across as many distinct companies/components as
    # the budget allows, rather than a coin-flip that could dump one more
    # giant single-company component into eval and blow past the target.
    remaining = [root for root in comps if root not in assignment]
    remaining.sort(key=lambda root: (comp_size[root], rng.random()))
    for root in remaining:
        if eval_chunks_assigned < eval_budget:
            assignment[root] = "eval"
            eval_chunks_assigned += comp_size[root]
        else:
            assignment[root] = "train"

    # ------------------------------------------------------------------
    # Repair pass (added 2026-08-11, owner decision: "protect training").
    #
    # The quota passes above aim at a target eval FRACTION per rare label,
    # but components are coarse: a single component can carry many
    # occurrences of a scarce label, so one assignment can overshoot
    # badly. The first split did exactly that — guidance:RAISED landed
    # 65.7% in eval, leaving only 12 training examples, i.e. an eval set
    # measuring a category the model never had a fair chance to learn.
    #
    # This pass moves components back from eval to train until every rare
    # label retains a workable training majority. Moving whole components
    # preserves the leakage guarantee by construction (the boundary still
    # falls between components, never inside one).
    # ------------------------------------------------------------------
    MIN_TRAIN_COUNT_PER_RARE_LABEL = 30   # absolute floor where the label allows
    MAX_EVAL_FRACTION_PER_LABEL = 0.35    # no label may be mostly held out

    def label_counts(lb):
        tr = ev = 0
        for root in label_to_comps[lb]:
            n = sum(1 for cid in comps[root] if lb in set(chunk_labels.get(cid, [])))
            if assignment.get(root) == "eval":
                ev += n
            else:
                tr += n
        return tr, ev

    for lb in sorted(label_to_comps, key=lambda x: total_label_chunk_counts[x]):
        if lb.startswith("distress:"):
            continue  # excluded from training targets anyway
        total = total_label_chunk_counts[lb]
        if total == 0:
            continue
        floor = min(MIN_TRAIN_COUNT_PER_RARE_LABEL, int(total * 0.6))
        for _ in range(len(comps)):
            tr, ev = label_counts(lb)
            over_eval = (ev / total) > MAX_EVAL_FRACTION_PER_LABEL
            under_train = tr < floor
            if not (over_eval or under_train):
                break
            movable = [
                root
                for root in label_to_comps[lb]
                if assignment.get(root) == "eval"
                and any(lb in set(chunk_labels.get(cid, [])) for cid in comps[root])
            ]
            if not movable:
                break
            # Move the component carrying the MOST of this label, so each
            # move buys the largest correction for the least eval churn.
            movable.sort(
                key=lambda root: -sum(
                    1 for cid in comps[root] if lb in set(chunk_labels.get(cid, []))
                )
            )
            assignment[movable[0]] = "train"
            eval_chunks_assigned -= comp_size[movable[0]]

    return assignment


def run():
    print(f"Reading {LABELS_PATH} (read-only)")
    labels = pd.read_parquet(LABELS_PATH)
    total_rows = len(labels)

    clean_predicate = labels["parse_ok"] & labels["schema_valid"]
    n_dropped = int((~clean_predicate).sum())
    dropped_ids = labels.loc[~clean_predicate, "chunk_id"].tolist()
    assert n_dropped == 1, (
        f"Expected exactly 1 row to fail parse_ok & schema_valid, got {n_dropped}: {dropped_ids}. "
        "This assumption is asserted here and re-checked in check_leakage.py — if the labeled "
        "corpus changed (e.g. a re-run), re-verify before trusting the split."
    )
    print(f"Dropped {n_dropped} row(s) failing (parse_ok & schema_valid): {dropped_ids}")

    df = labels.loc[clean_predicate].reset_index(drop=True)
    print(f"{len(df)} / {total_rows} rows usable for splitting")

    comps = build_components(df)
    comp_sizes = sorted((len(v) for v in comps.values()), reverse=True)
    print(
        f"Connected components: {len(comps)} (chunk-level rows: {len(df)}). "
        f"Largest component: {comp_sizes[0]} chunks. "
        f"Components with >1 chunk: {sum(1 for s in comp_sizes if s > 1)}."
    )

    chunk_labels = label_occurrence_index(df)
    assignment = stratified_component_split(comps, chunk_labels, seed=SEED)

    chunk_to_split = {}
    for root, cids in comps.items():
        side = assignment[root]
        for cid in cids:
            chunk_to_split[cid] = side

    manifest = pd.DataFrame(
        {
            "chunk_id": list(chunk_to_split.keys()),
            "split": list(chunk_to_split.values()),
        }
    )
    manifest = manifest.merge(
        df[["chunk_id", "section_type", "home_ticker", "home_filing_date"]],
        on="chunk_id",
        how="left",
    )

    n_eval = (manifest["split"] == "eval").sum()
    n_train = (manifest["split"] == "train").sum()
    print(f"\nFinal split: train={n_train} ({n_train/len(manifest):.1%}), "
          f"eval={n_eval} ({n_eval/len(manifest):.1%})")

    SPLITS_DIR.mkdir(exist_ok=True)
    manifest.to_parquet(SPLITS_DIR / "manifest.parquet", index=False)
    print(f"Wrote {SPLITS_DIR / 'manifest.parquet'}")

    for side in ("train", "eval"):
        ids = set(manifest.loc[manifest["split"] == side, "chunk_id"])
        out = df[df["chunk_id"].isin(ids)].reset_index(drop=True)
        out.to_parquet(SPLITS_DIR / f"{side}.parquet", index=False)
        print(f"Wrote {SPLITS_DIR / f'{side}.parquet'} ({len(out)} rows)")

    # Per-label report, both sides.
    report_labels = (
        [f"guidance:{k}" for k in ("RAISED", "MAINTAINED", "LOWERED", "WITHDRAWN")]
        + [f"redflag:{k}" for k in (
            "DEMAND_WEAKNESS", "SUPPLY_INPUT_CONSTRAINT", "TRADE_POLICY_EXPOSURE",
            "IMPAIRMENT_WRITEDOWN", "MARGIN_COST_PRESSURE", "LEGAL_REGULATORY_ACTION",
        )]
        + [f"distress:{k}" for k in ("GOING_CONCERN", "ACCOUNTING_RESTATEMENT", "LIQUIDITY_STRESS")]
    )
    print("\nPer-label chunk counts, train vs eval:")
    print(f"{'label':32s} {'train':>8s} {'eval':>8s} {'eval_frac':>10s}")
    split_by_id = dict(zip(manifest["chunk_id"], manifest["split"]))
    for lb in report_labels:
        comps_with = defaultdict(int)
        for cid, labs in chunk_labels.items():
            if lb in labs:
                comps_with[split_by_id.get(cid, "?")] += 1
        tr, ev = comps_with.get("train", 0), comps_with.get("eval", 0)
        tot = tr + ev
        frac = ev / tot if tot else float("nan")
        print(f"{lb:32s} {tr:8d} {ev:8d} {frac:10.1%}" if tot else f"{lb:32s} {tr:8d} {ev:8d} {'n/a':>10s}")

    print("\nSection-type counts, train vs eval:")
    print(pd.crosstab(manifest["section_type"], manifest["split"]))

    print("\nTicker counts, train vs eval (documents the company overlap, see SPLIT_DESIGN.md):")
    print(pd.crosstab(manifest["home_ticker"], manifest["split"]))

    return manifest


if __name__ == "__main__":
    run()
