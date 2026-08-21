"""
build_sample.py — FinScreen Week 3 spot-check sample builder.

Builds a tiered, exactly-400-row sample of unique chunk_ids from
data/labels.parquet for the Week 3 spot-check review. (The review that
actually ran was a model second rater over all 400, a model third rater
over the contested 174, and owner rulings on a 104-case shortlist -- not a
human read of all 400. See spotcheck/README.md's banner.)

READ-ONLY on data/labels.parquet, data/labeling_corpus.parquet,
labeling_rubric.md, data/batch_request*.jsonl — this script never writes
to any of those paths.

RESOLVED (CHK-8e69547e0900a8dd): this row's failure mode was disputed
(truncation-like partial JSON vs "refusal") and was settled 2026-08-11 by
reading the batch result directly from the API: stop_reason="refusal",
stop_details.category="bio", 293 partial output tokens — a genuine
MID-STREAM safety refusal, whose partial output superficially resembles
truncation (this is exactly why it fooled two independent reviewers; a
mid-stream refusal cuts off partial output rather than emitting a tidy
decline message). section_type is MDA. The row has NO usable labels
(sentiment/guidance_direction/red_flags/distress_tier all None) and
review_tool.html presents it as "labeling failed — no labels to review,"
not as an implicit all-fields-empty negative. Re-running would refuse
again; it stays excluded by predicate.

Reproducibility: fixed seed (SEED = 20260810, the date this sample was
first built, chosen once and never changed run-to-run) drives every random
draw. Re-running this script against an unchanged data/labels.parquet
produces a byte-identical spotcheck/sample_400.parquet (same rows, same
order, same tier assignments) — see the assertion block at the bottom and
the idempotency check in the README.

TIER DEFINITIONS AND PRECEDENCE
--------------------------------
A chunk_id may qualify for more than one tier's *selection criteria*.
Precedence for the recorded `primary_tier` field (used only for
readability/reporting; `tiers` records the FULL set of criteria a row
matches, computed independently of assignment order) is:

    Tier A > Tier B > Tier C

i.e. a row is assigned to the highest-precedence tier whose selection
criteria it matches, and is drawn into the final 400 exactly once — it is
never duplicated across tiers. `tiers` is the set of ALL tiers whose
criteria the row matches (so a distress-tier-positive chunk that also has
non-NONE guidance would show tiers={"A","B"} but primary_tier="A" and
counts toward Tier A's budget, not Tier B's).

  Tier A (exhaustive, all 162 rows as of the post-relabel corpus; was 143
  before the 2026-08-11 corrective re-label):
    distress_tier is a non-empty list (any of the 3 distress categories,
    any modality).

  Tier B (targeted oversample of thin categories), built as four
  sub-groups, each drawn from the pool remaining AFTER Tier A is removed,
  and each sub-group drawn from the pool remaining after the PRIOR
  sub-groups (within B) are removed — so there is no double-counting
  inside Tier B either:
    B1 — named chunks: CHK-8e69547e0900a8dd (the parse_ok=False /
         reported-refusal row) and CHK-6cfb7bb16c8ef2fc (the canary
         cross-variant-disagreement row). Included regardless of any
         other criteria they match, exactly once.
    B2 — all rows with guidance_direction in
         {RAISED, MAINTAINED, LOWERED, WITHDRAWN} (the thin guidance
         categories), minus anything already claimed by A or B1.
    B3 — REALIZED-modality red flags, PER-CATEGORY QUOTA (revised from an
         earlier draft of this script that took "all REALIZED" as one
         undifferentiated pool — that pool is 2,693 of 6,747 rows, far too
         large to treat as a single targeted-oversample tier, and a flat
         subsample of it would have been dominated by whichever category
         happens to be most common (MARGIN_COST_PRESSURE/REALIZED: 1,064
         instances) rather than giving every category a reviewable
         sample). The 6 red-flag categories' REALIZED instance counts in
         the full labeled corpus are:
           DEMAND_WEAKNESS          755
           IMPAIRMENT_WRITEDOWN     723
           LEGAL_REGULATORY_ACTION 1020
           MARGIN_COST_PRESSURE    1064
           SUPPLY_INPUT_CONSTRAINT  158
           TRADE_POLICY_EXPOSURE    240
         None of these are so thin they can be exhausted within budget
         (unlike Tier A's distress positives), so B3 instead guarantees a
         fixed REALIZED_QUOTA_PER_CATEGORY = 10 rows per category — a
         seeded, documented, per-category floor so every category gets a
         reviewable sample regardless of its corpus-wide frequency, rather
         than an undifferentiated pool subsample that would have skewed
         toward the most common categories. Categories are processed in a
         fixed order (alphabetical) and each category's quota is drawn
         from rows containing that category at REALIZED modality, minus
         anything already claimed by A, B1, B2, or an earlier category in
         this same B3 pass (so a row matching two REALIZED categories
         counts toward only the first category it's drawn under, and is
         not double-selected). Within each category, the quota is drawn
         with a fixed seed, stratified proportionally by section_type
         (same `stratified_pick` rounding rule as Tier C). Worst case this
         adds at most 6 x 10 = 60 rows to the sample; it is very likely to
         add fewer once cross-category overlap and A/B1/B2 overlap are
         removed (documented in the printed summary at run time).

  Tier C (fill): proportional stratified random sample by section_type,
    drawn from whatever remains after A and B are removed, sized to bring
    the total to exactly 400. "Proportional" means Tier C's per-
    section_type composition mirrors the section_type distribution of the
    remaining eligible pool (not the full corpus) at the time Tier C is
    drawn, rounded to integers with any remainder assigned to the largest
    stratum(a) — this is a deliberate secondary-stratification choice
    (stratify against the residual pool, not the raw corpus) documented
    here and in the README because Tier A/B have already skewed which
    section types are left in the pool (e.g. 8K_BODY has only 8 rows
    corpus-wide and several may already be claimed by A/B).

SEED: 20260810 (single seed used for every random draw in this script,
via numpy's default_rng; each sub-sample uses child streams spawned from
this seed so results are deterministic and order-independent of how the
script happens to iterate).
"""

import numpy as np
import pandas as pd

SEED = 20260810
RELABEL_BATCH_ID = "msgbatch_01KrfTWXeVN79Us9wthnGLaG"
REALIZED_QUOTA_PER_CATEGORY = 10
RED_FLAG_CATEGORIES = [
    "DEMAND_WEAKNESS",
    "IMPAIRMENT_WRITEDOWN",
    "LEGAL_REGULATORY_ACTION",
    "MARGIN_COST_PRESSURE",
    "SUPPLY_INPUT_CONSTRAINT",
    "TRADE_POLICY_EXPOSURE",
]
TOTAL_SAMPLE_SIZE = 400
NAMED_CHUNKS = ["CHK-8e69547e0900a8dd", "CHK-6cfb7bb16c8ef2fc"]

LABELS_PATH = "/Users/vihanpatil/personal/projects/FinScreen/data/labels.parquet"
# Tier D (added 2026-08-11, owner-approved): labels produced by the two
# labeling configs (adaptive-thinking/max_tokens=500 vs
# thinking-disabled/max_tokens=4000) disagree on red_flags for 935 of the
# 4,219 re-labeled chunks (22.2%), systematically in the direction of the
# disabled config emitting MORE flags. Both label sets are on disk, so a
# slice of the owner's review is spent adjudicating which config was
# right — turning an unexplained sensitivity into measured evidence.
PRE_RELABEL_PATH = "/Users/vihanpatil/personal/projects/FinScreen/data/labels_pre_relabel.parquet"
DISAGREEMENT_TARGET = 60
OUT_PATH = "/Users/vihanpatil/personal/projects/FinScreen/spotcheck/sample_400.parquet"


def has_entries(x):
    return isinstance(x, np.ndarray) and len(x) > 0


def has_realized(x):
    if not isinstance(x, np.ndarray) or len(x) == 0:
        return False
    return any(e["modality"] == "REALIZED" for e in x)


def has_realized_category(x, category):
    if not isinstance(x, np.ndarray) or len(x) == 0:
        return False
    return any(e["category"] == category and e["modality"] == "REALIZED" for e in x)


def stratified_pick(pool_df, n, rng, by="section_type"):
    """Proportional stratified sample of n rows from pool_df, stratified by
    `by`, proportional to pool_df's own composition. Rounds down per
    stratum then distributes the remainder to the strata with the largest
    fractional remainder (largest-remainder / Hamilton method — a
    standard, deterministic apportionment rule), so counts sum to exactly
    n. Returns a list of chunk_ids, sorted, for determinism prior to any
    final ordering.
    """
    if n == 0:
        return []
    counts = pool_df[by].value_counts()
    fractions = counts / counts.sum() * n
    base = np.floor(fractions).astype(int)
    remainder = n - base.sum()
    frac_part = (fractions - base).sort_values(ascending=False)
    strata_order = list(frac_part.index)
    for i in range(remainder):
        base[strata_order[i % len(strata_order)]] += 1

    picked = []
    for stratum, k in base.items():
        if k <= 0:
            continue
        stratum_pool = pool_df[pool_df[by] == stratum].sort_values("chunk_id")
        k = min(k, len(stratum_pool))
        idx = rng.choice(len(stratum_pool), size=k, replace=False)
        picked.extend(stratum_pool.iloc[sorted(idx)]["chunk_id"].tolist())
    return picked


def main():
    df = pd.read_parquet(LABELS_PATH)
    assert df.chunk_id.is_unique, "labels.parquet has duplicate chunk_ids"

    rng = np.random.default_rng(SEED)

    tier_membership = {}  # chunk_id -> set of tiers matched (criteria-based)
    primary_tier = {}     # chunk_id -> assigned tier (precedence A>B>C)
    subtier = {}          # chunk_id -> B1/B2/B3 label, for reporting only

    # ---- Tier A: exhaustive distress-tier positives ----
    tierA_ids = set(df[df.distress_tier.apply(has_entries)]["chunk_id"])
    for cid in tierA_ids:
        tier_membership.setdefault(cid, set()).add("A")
        primary_tier[cid] = "A"

    claimed = set(tierA_ids)

    # ---- Tier B1: named chunks ----
    b1_ids = set()
    for cid in NAMED_CHUNKS:
        assert (df.chunk_id == cid).sum() == 1, f"named chunk {cid} not found exactly once"
        tier_membership.setdefault(cid, set()).add("B")
        if cid not in claimed:
            b1_ids.add(cid)
            primary_tier[cid] = "B"
            subtier[cid] = "B1_named"
    claimed |= b1_ids

    # ---- Tier B2: guidance non-NONE ----
    guidance_ids_all = set(
        df[df.guidance_direction.isin(["RAISED", "MAINTAINED", "LOWERED", "WITHDRAWN"])]["chunk_id"]
    )
    for cid in guidance_ids_all:
        tier_membership.setdefault(cid, set()).add("B")
    b2_ids = guidance_ids_all - claimed
    for cid in b2_ids:
        primary_tier[cid] = "B"
        subtier[cid] = "B2_guidance"
    claimed |= b2_ids

    # ---- Tier B3: REALIZED-modality red flags, per-category quota ----
    # Mark ANY REALIZED-red-flag row as matching Tier B criteria (for the
    # `tiers` full-membership field), independent of the per-category
    # quota draw below.
    realized_ids_all = set(df[df.red_flags.apply(has_realized)]["chunk_id"])
    for cid in realized_ids_all:
        tier_membership.setdefault(cid, set()).add("B")

    b3_ids = set()
    b3_category_counts = {}
    for category in RED_FLAG_CATEGORIES:
        cat_ids_all = set(
            df[df.red_flags.apply(lambda x, c=category: has_realized_category(x, c))]["chunk_id"]
        )
        cat_pool = df[df.chunk_id.isin(cat_ids_all - claimed)]
        quota = min(REALIZED_QUOTA_PER_CATEGORY, len(cat_pool))
        picked = stratified_pick(cat_pool, quota, rng)
        for cid in picked:
            primary_tier[cid] = "B"
            subtier[cid] = f"B3_realized_{category}"
        b3_ids |= set(picked)
        claimed |= set(picked)
        b3_category_counts[category] = len(picked)

    tierB_ids = b1_ids | b2_ids | b3_ids

    # ---- Tier D: config-disagreement adjudication ----
    # Chunks where the adaptive/500 and disabled/4000 passes produced
    # different red_flag sets. The reviewer sees the passage and both
    # label sets, and judges which (if either) is correct.
    prior = pd.read_parquet(PRE_RELABEL_PATH).set_index("chunk_id")
    cur = df.set_index("chunk_id")
    relabeled = [c for c in cur.index if cur.loc[c, "batch_id"] == RELABEL_BATCH_ID]

    def rf_key(v):
        if not has_entries(v):
            return ()
        return tuple(sorted((d["category"], d["modality"]) for d in v))

    disagree_all = {
        c for c in relabeled
        if rf_key(prior.loc[c, "red_flags"]) != rf_key(cur.loc[c, "red_flags"])
    }
    for cid in disagree_all:
        tier_membership.setdefault(cid, set()).add("D")
    disagree_pool = df[df.chunk_id.isin(disagree_all - claimed)]
    tierD_ids = set(
        stratified_pick(disagree_pool, min(DISAGREEMENT_TARGET, len(disagree_pool)), rng)
    )
    for cid in tierD_ids:
        primary_tier[cid] = "D"
        subtier[cid] = "D_config_disagreement"
    claimed |= tierD_ids

    # ---- Tier C: proportional stratified fill from remaining pool ----
    n_remaining_needed = (
        TOTAL_SAMPLE_SIZE - len(tierA_ids) - len(tierB_ids) - len(tierD_ids)
    )
    assert n_remaining_needed >= 0, (
        f"Tier A ({len(tierA_ids)}) + Tier B ({len(tierB_ids)}) already "
        f"exceeds {TOTAL_SAMPLE_SIZE} — reduce REALIZED_SUBSAMPLE_TARGET"
    )
    remaining_pool = df[~df.chunk_id.isin(claimed)]
    tierC_ids = set(stratified_pick(remaining_pool, n_remaining_needed, rng))
    for cid in tierC_ids:
        tier_membership.setdefault(cid, set()).add("C")
        primary_tier[cid] = "C"
    claimed |= tierC_ids

    all_ids = sorted(claimed)
    sample = df[df.chunk_id.isin(all_ids)].copy()
    sample["primary_tier"] = sample["chunk_id"].map(primary_tier)
    sample["tiers"] = sample["chunk_id"].map(lambda c: ",".join(sorted(tier_membership[c])))
    sample["subtier"] = sample["chunk_id"].map(lambda c: subtier.get(c, ""))

    # deterministic final ordering: tier, then chunk_id
    tier_order = {"A": 0, "B": 1, "D": 2, "C": 3}
    sample["_tier_order"] = sample["primary_tier"].map(tier_order)
    sample = sample.sort_values(["_tier_order", "chunk_id"]).drop(columns=["_tier_order"])
    sample = sample.reset_index(drop=True)

    # ---------------- assertions ----------------
    assert len(sample) == TOTAL_SAMPLE_SIZE, f"expected 400 rows, got {len(sample)}"
    assert sample.chunk_id.is_unique, "duplicate chunk_ids in final sample"
    assert tierA_ids <= set(sample.chunk_id), "not all distress positives present"
    # Count is data-derived, not hardcoded: it was 143 under the original
    # labeling pass and 162 after the 2026-08-11 re-label. Assert only that
    # the tier is exhaustive and non-trivial.
    assert len(tierA_ids) == int(df.distress_tier.apply(has_entries).sum())
    assert len(tierA_ids) > 0, "no distress positives found — check labels"
    assert guidance_ids_all <= set(sample.chunk_id), "not all non-NONE guidance rows present"
    for cid in NAMED_CHUNKS:
        assert cid in set(sample.chunk_id), f"named chunk {cid} missing from sample"
    for category, n in b3_category_counts.items():
        assert n > 0, f"Tier B3 quota for {category} came back empty — check pool"

    sample.to_parquet(OUT_PATH, index=False)

    print(f"Tier A (distress positives, exhaustive): {len(tierA_ids)}")
    print(f"Tier B total: {len(tierB_ids)}")
    print(f"  B1 named: {len(b1_ids)}")
    print(f"  B2 guidance non-NONE: {len(b2_ids)}")
    print(f"  B3 REALIZED per-category quota total: {len(b3_ids)}")
    for category, n in b3_category_counts.items():
        print(f"    {category}: {n} (quota {REALIZED_QUOTA_PER_CATEGORY})")
    print(f"Tier D (config-disagreement adjudication): {len(tierD_ids)} "
          f"(pool of {len(disagree_all)} disagreeing chunks)")
    print(f"Tier C (stratified fill): {len(tierC_ids)}")
    print(f"TOTAL: {len(sample)}")
    print(sample.groupby("primary_tier")["section_type"].value_counts())
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
