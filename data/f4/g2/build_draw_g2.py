"""
build_draw_g2.py — the G2 E2 student-label spot-check draw (design §10.1).

2026-09-07: owner rulings §14 — re-run at OPTION C (P=400, G-A=80 proportional
+ the ruled direction quota = 100, G-N=80), b=0.85 both gate-bearing fields,
three ceiling batches. The provisional Option-B draw is SUPERSEDED (§14.8).

2026-09-07 (fix pass, design §14.9 — model amendment, NOT an owner ruling, made
before any rating exists): `arm` leaves the rater-pointed tree (draw_g2.csv is
now `rank,batch,chunk_id`; the arm map is a sibling file OUTSIDE data/f4/g2/),
and the unused cik-coverage Monte Carlo and the dead `--provisional` flag are
deleted. Reason: `arm` was a per-row disclosure of stored guidance status for
180 of 580 drawn rows, guarded only by a prompt sentence — the exact
"instruct-against-it" pattern §5.1 rejects for every other column.

Design: data/f4/g2/G2_SPOTCHECK_design.md (pre-registered 2026-09-06;
parameters owner-ratified 2026-09-07, §14).
Precedent: data/hardening/spotcheck_v12/build_draw_v12.py.

WRITES (data/f4/g2/, plus the one arm sidecar outside it):
  draw_g2.csv                   the draw manifest, LABEL-FREE and
                                METADATA-FREE by design §5.1: exactly three
                                columns `rank,batch,chunk_id`. Stored labels,
                                section_type, sector, cik, filing date AND the
                                arm are re-joined at ANALYSIS time by
                                analyze_g2.py, so a rater that reads this file
                                learns nothing that breaks blindness.
  ../g2_draw_arms.csv           `chunk_id,arm` — written OUTSIDE data/f4/g2/
                                (§14.9) so it does not sit beside the batch
                                files a rater is pointed at. arm='G-A' implies
                                the stored guidance_direction is active and
                                arm='G-N' implies an imputed NONE, so this is a
                                per-row disclosure of stored guidance status
                                for 180 of the 580 rows; analysis reads it,
                                raters never do.
  batches/batch_NN.json         JSON array; every object's key set is exactly
                                {chunk_id, text} (§10.1.2 item 7). No stored
                                label, no section type, no sector, no ticker,
                                no company name, no date.
  batches/batch_NN_replicate.json
                                byte-identical copy of each CEILING_BATCHES
                                entry — the two-rater ceiling arm (§5.4,
                                §14.5: three batches, n = 120 rows).
  rater_policy_addendum.md      the eight owner policy rules + the A4
                                hierarchy from
                                data/hardening/spotcheck_v12/OWNER_POLICY_RULINGS.md,
                                with exemplar ids and company names REDACTED
                                (§5.2). Those rules are the OWNER'S OWN
                                rulings of 2026-08-27; the §14 parameters are
                                the OWNER'S rulings of 2026-09-07; nothing
                                else in this repo's G2 output is an owner
                                ruling.
  draw_manifest.json            seeds, input sha256s, allocation, realized
                                composition, assertions passed (§10.1.1).

READ-ONLY (sha256-pinned, hard-fail on mismatch):
  data/f4/labels_e2_v1.parquet
  data/f4/chunks_v1.parquet
  labeling_rubric.md
  data/hardening/spotcheck_v12/OWNER_POLICY_RULINGS.md
  finetune/splits_v12/train.parquet

0 API calls, 0 GPU seconds, 0 network calls. System python3, pandas/numpy/
stdlib only.

PARAMETERS ARE OWNER-RATIFIED (§14.1, 2026-09-07): OPTION = "C" and
RATIFIED_BARS = {sentiment 0.85, guidance_direction 0.85} are the owner's own
rulings, not model recommendations. The script hard-fails unless
PARAMETERS_STATUS == "OWNER_RATIFIED" (§10.1). The G-A sub-arm ("G-A" =
proportional base, "G-A-floor" = LOWERED floor purchase, "G-A-withdrawn" = the
WITHDRAWN quota) is per-row deterministic from the seeded two-stage draw and is
reported as COUNTS in draw_manifest.json — never per row anywhere, because a
row tagged "G-A-withdrawn" would hand its reader the stored guidance_direction
for exactly the 15 rows the quota was bought to measure. §14.9 extends the same
argument one step: `arm` itself carries that disclosure for the whole G-A and
G-N arms, so it moved out of the rater-pointed tree into the sidecar above.
"""

import argparse
import hashlib
import json
import re
import string
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------
# module constants — OWNER-RATIFIED 2026-09-07 (design §14.1, §10.1). No value
# below is a default and none may be inferred; they are copied verbatim into
# draw_manifest.json and analyze_g2.py re-asserts them against its own copy.
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[3]   # data/f4/g2/<this file> -> repo root
OUT = ROOT / "data" / "f4" / "g2"
BATCH_DIR = OUT / "batches"
ARMS_NAME = "g2_draw_arms.csv"   # written to OUT.parent — see §14.9
DESIGN_DOC = "data/f4/g2/G2_SPOTCHECK_design.md"

SEED = 20260906
BATCH_SIZE = 40
PARAMETERS_STATUS = "OWNER_RATIFIED"   # owner ruling 2026-09-07, §14.1
OPTION = "C"                           # §14.1 item (i)
N_PRIMARY = 400                        # two-way section x sector Hamilton (§14.2)
N_GA = 80                              # proportional BASE in the active EX99 stratum
N_GA_FLOOR = {"LOWERED": 15, "MAINTAINED": 20, "WITHDRAWN": 15}   # §14.1 item (vi)
N_GA_WITHDRAWN = 15                    # == N_GA_FLOOR["WITHDRAWN"]; named because it
                                       # is the 2026-09-07 amendment to the +30 floor
N_GA_TOTAL = 100                       # asserted == sum of the targets below
N_GN = 80                              # §14.1 item (i); no floor (item (iv))
N_TOTAL = N_PRIMARY + N_GA_TOTAL + N_GN            # 580 -> 15 batches (14 x 40 + 1 x 20)
RATE_RED_FLAGS = True                  # Option C, not B-lite (standing owner item)
CEILING_BATCHES = ["batch_01", "batch_02", "batch_03"]   # §14.1 item (v): n = 120 rows
RATIFIED_BARS = {"sentiment": 0.85, "guidance_direction": 0.85}   # §14.1 item (ii)
GA_CORPUS_COUNTS = {"RAISED": 3716, "MAINTAINED": 1940,  # N_d in the 6,479-row active
                    "LOWERED": 757, "WITHDRAWN": 66}     # EX99 frame; w_d = N_d/6479
GA_WEIGHTS = {"RAISED": 0.573545, "MAINTAINED": 0.299429,      # §14.4, to 6 dp,
              "LOWERED": 0.116839, "WITHDRAWN": 0.010187}      # re-derived + asserted
GA_TARGETS = {"RAISED": 46, "MAINTAINED": 24,          # §14.3's pinned final arm,
              "LOWERED": 15, "WITHDRAWN": 15}          # asserted to the row

# SECTIONS order is the one pinned in code on 2026-09-06 and is NOT display
# order: it fixes which named child RNG stream serves which cell, so permuting
# it would re-draw P. §14.8 licenses only N_PRIMARY, the G-A targets and
# CEILING_BATCHES to change, so it stands.
SECTIONS = ["EX99_PRESS_RELEASE", "MDA", "RISK_FACTORS"]
SECTORS = ["consumer", "energy", "financials", "healthcare", "tech"]
ACTIVE_GUIDANCE = ["RAISED", "MAINTAINED", "LOWERED", "WITHDRAWN"]
PROBE_STRATA = {"P": 12, "G-A": 4, "G-N": 4}

# G-A target rule, pinned (§14.3): Hamilton within the active stratum at N_GA,
# then the elementwise maximum against the floor vector,
#     target_d = max(hamilton_d(N_GA), N_GA_FLOOR.get(d, 0))
# No direction is reduced below its proportional count, and the UNSPENT
# remainder of the +30-row floor budget is NOT reallocated to any other
# direction. Realized: RAISED 46 (proportional) / MAINTAINED 24 (proportional;
# floor 20 already met) / LOWERED 15 (9 + 6 floor) / WITHDRAWN 15 (1 + 14
# quota) = 100 = N_GA_TOTAL.

INPUT_SHA256 = {
    "data/f4/labels_e2_v1.parquet":
        "f236f421096c665b373addb9ffdbb6cf45454027761838361cf179cbb7b538df",
    "data/f4/chunks_v1.parquet":
        "d67395ece6126045e851e05f4b8fe5c8c49bd69069c44a08b9ee8f9d67bf0857",
    "labeling_rubric.md":
        "46dea3c886846849c82ae2b65d8e29ef95016dece706cd19a2e00b8d99c30b25",
    "data/hardening/spotcheck_v12/OWNER_POLICY_RULINGS.md":
        "eb59c6d3418c28539de1f7f0e39b0a9645dc2bbe00845ca3b2fca0b74a415cef",
    # pinned at implementation time (2026-09-06), 5,736 rows asserted
    "finetune/splits_v12/train.parquet":
        "5e56076e3948cf9598b6cf61ad7307961735c19af2a0932f981ea6ee3dd4cb10",
}

# pre-registered frame numbers (§2.1, §2.5, §3.2, §3.3, §5.1) — all asserted
N_CORPUS, N_FRAME = 317081, 316291
N_GA_FRAME, N_GN_FRAME = 6479, 48293
N_TRAIN_OVERLAP = 14342
N_SELFID = 146958            # 46.46% of the frame

# manifest keys that identify the parameter set a prior draw was taken under.
# A14 (byte-for-byte reproducibility) is only meaningful against a prior run at
# the SAME parameters; a parameter change is a supersession (§14.8), recorded
# as such rather than reported as a reproducibility failure.
PARAM_KEYS = ["seed", "option", "parameters_status", "n_primary", "n_ga",
              "n_ga_total", "n_gn", "n_total", "batch_size", "ceiling_batches",
              "rate_red_flags", "ratified_bars", "draw_schema"]
# §14.9 moved `arm` out of draw_g2.csv into the sidecar. The DRAW is unchanged
# (same seed, same 580 chunk_ids, same order, byte-identical batches), but the
# CSV's schema is not, so the schema is versioned here and travels in PARAM_KEYS
# — that turns the change into a recorded supersession, exactly as §14.8 did for
# the parameter change, instead of a silent A14 reproducibility failure.
DRAW_SCHEMA = "rank,batch,chunk_id;arms_sidecar"

# §5.1 / §10.1.2 item 13. The check is on KEYS / column names, never on the
# passage text: a press release may legitimately contain the word "sentiment".
FORBIDDEN_KEYS = [
    "sentiment", "guidance_direction", "red_flags", "distress_tier",
    "section_type", "home_sector", "home_cik", "home_filing_date",
    "home_company_name", "date",
]
# the addendum is prose the rater must read, and the protocol requires it to
# name the three fields; what it may never carry is a metadata column or a
# chunk_id.
FORBIDDEN_IN_PROSE = ["section_type", "home_sector", "home_cik",
                      "home_filing_date", "home_company_name"]
BATCH_KEYS = {"chunk_id", "text"}

SELFID_STOP = {
    "inc", "inc.", "corp", "corp.", "corporation", "company", "co", "co.",
    "the", "of", "and", "group", "holdings", "holding", "ltd", "llc", "plc",
    "&", "/de/", "international", "industries", "systems", "technologies",
    "com",
}

TRAIN_OVERLAP_DEFINITION = (
    "overlap(row) = row.home_accession_number in train_acc or any(a in "
    "train_acc for a in row.source_accession_numbers) or "
    "sha1(normalize(row.text)) in train_txt, where train_acc = set of "
    "finetune/splits_v12/train.parquet home_accession_number, train_txt = "
    "{sha1(normalize(t)) for t in train.text}, and normalize = collapse "
    "whitespace, strip, lower. Paragraph-id joins are FORBIDDEN: the E1 and "
    "E2 namespaces differ (P-... vs E2P-...) so such a join returns a "
    "structurally meaningless 0%."
)
SELFID_DEFINITION = (
    "selfid(row) is true iff the first token of the row's company name that "
    "is longer than 2 characters (after stripping surrounding punctuation) "
    "and not in the generic-suffix stop list, lowercased, occurs in "
    "lower(text). Stop list: " + ", ".join(sorted(SELFID_STOP)) + "."
)
GA_TARGET_RULE = (
    "target_d = max(hamilton_d(N_GA), N_GA_FLOOR.get(d, 0)) over the 6,479-row "
    "active EX99 frame (design 14.3). No direction is reduced below its "
    "proportional count and the unspent remainder of the +30-row floor budget "
    "is NOT reallocated. The draw is two-stage and seeded: the proportional "
    "base is drawn first from each direction's pool on stream 'G-A|<d>', then "
    "the quota top-up is drawn without replacement from that same pool minus "
    "the already-drawn ids on stream 'G-A-quota|<d>'."
)
SUBARM_DISPOSITION = (
    "The G-A sub-arm (G-A = proportional base, G-A-floor = LOWERED floor "
    "purchase, G-A-withdrawn = the WITHDRAWN quota amendment) is reported here "
    "as counts only, never per row: a file tagging a row 'G-A-withdrawn' would "
    "disclose the stored guidance_direction for exactly the 15 rows the quota "
    "was bought to measure. Section 14.9 applies the same argument to `arm` "
    "itself, which discloses stored guidance status for all 180 G-A + G-N "
    "rows: draw_g2.csv is now rank,batch,chunk_id and the arm map is the "
    "sidecar data/f4/" + ARMS_NAME + ", outside the rater-pointed tree. "
    "Per-row sub-arm membership is deterministic from the seed and no "
    "estimator in section 10.2.4 or 14.4 reads it: the re-weighting is by "
    "direction, not by sub-arm."
)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def normalize(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def sha1_norm(text):
    return hashlib.sha1(normalize(text).encode("utf-8")).hexdigest()


def hamilton(counts, n):
    """Largest-remainder proportional allocation summing to exactly n.

    Ties break on (-fractional_part, key) — for the two-way P allocation the
    key is (section, sector), which is the design's stated rule.
    """
    frac = counts / counts.sum() * n
    base = np.floor(frac).astype(int)
    rem = frac - base
    order = sorted(counts.index, key=lambda k: (-rem[k], k))
    for k in order[: int(n - base.sum())]:
        base[k] += 1
    assert base.sum() == n
    return base


def distinctive_token(name):
    """First company-name token that is not a generic suffix (§5.1)."""
    for tok in str(name).split():
        low = tok.strip(string.punctuation + "\\").lower()
        if len(low) > 2 and low not in SELFID_STOP:
            return low
    return ""


def draw_from(pool_ids, k, rng):
    """SRS without replacement from a chunk_id-sorted pool, order-independent."""
    pool = np.sort(np.asarray(pool_ids))
    idx = rng.choice(len(pool), size=k, replace=False)
    return pool[np.sort(idx)].tolist()


def spawn_streams():
    """One named child RNG stream per stratum, spawned in a fixed order (§10.1).

    The first 22 names are the 2026-09-06 order and keep their streams; the
    four `G-A-quota|<d>` streams are appended, so the §14 quota adds streams
    without re-drawing anything that existed before it.

    `cik_coverage_sim` is RESERVED, not used: §14.9 deleted the Monte Carlo it
    fed, but a SeedSequence child is identified by position, so dropping the
    name would shift every `G-A-quota` stream and silently change the draw.
    """
    names = ([f"P|{s}|{k}" for s in SECTIONS for k in SECTORS]
             + [f"G-A|{d}" for d in ACTIVE_GUIDANCE]
             + ["G-N", "batch_permutation", "cik_coverage_sim__reserved"]
             + [f"G-A-quota|{d}" for d in ACTIVE_GUIDANCE])
    children = np.random.SeedSequence(SEED).spawn(len(names))
    return {name: np.random.default_rng(ss) for name, ss in zip(names, children)}


def build_addendum():
    """The eight owner policy rules + the A4 hierarchy, exemplar ids and
    company names REDACTED (§5.2). Nothing else from OWNER_POLICY_RULINGS.md:
    the watch-list row and the outcome section are dropped because both are
    keyed to a named company."""
    return """\
# Rater policy addendum — binding interpretation of rubric v1.2 sections 4 and 6

Generated by `data/f4/g2/build_draw_g2.py` from the owner's own annotation-policy
rulings of 2026-08-27. Read `labeling_rubric.md` first; this file overrides it
only where it speaks.

**Protocol.** You are rating BLIND. Your batch file carries only `{chunk_id, text}`
— no stored label, no section type, no ticker, no filing date, nothing to agree
with. Produce your own labels from the passage alone, under rubric v1.2. Emit all
three fields on every chunk even where the passage's register makes a field feel
inapplicable; applicability is resolved later, mechanically, by code, and is not
your judgement to make. There is no "N/A" and no "unsure" option. Do not label
distress tier.

**Scope.** Every rule below bears on the rubric's flag taxonomy (sections 4 and
6) only. Sentiment and guidance are untouched by them.

**Redaction.** The source file states several rules against numbered exemplar
rows and one named issuer. Those identifiers are removed here: rubric section 8
forbids issuer identity from reaching a rater, and a passage materially the same
as a cited exemplar can appear in this draw. The rules stand without them.

## The eight rules

1. **Complex supply chain is not a supply constraint.** There must be shortage,
   unavailable inputs, supplier disruption, inability to procure, constrained
   production, or the like.
2. **A market-wide commodity supply disruption is not automatically the
   producer's own supply/input constraint.**
3. **Realized applies to the labeled event, not to its potential consequence.**
   An existing investigation plus a possible penalty is a realized legal event.
   A future investigation is hypothetical.
4. **Do not infer an existing legal event from anaphora.** Wording such as
   "protections against such judgments" does not prove that a judgment exists;
   absent an affirmative statement, treat it as hypothetical.
5. **Safe-harbor noun lists and enumerations should ordinarily fail mining
   depth.** Materially identical enumerations must receive identical treatment:
   no flags.
6. **Once loan carrying-value reductions count as impairments, apply that
   consistently** — impairment / write-down, realized, including receivable
   write-offs.
7. **Regulation-driven costs can double-label.** An existing regulation plus an
   already-incurred compliance cost is both a legal/regulatory action, realized,
   and a margin/cost pressure, realized.
8. **If government payment-rate decisions count as regulatory action, adverse
   product approval or labeling decisions do too.** The difference between them
   is modality, not whether an agency decision is regulatory.

## The reimbursement-policy hierarchy

Adverse government payment-rate actions COUNT as regulatory action in a
healthcare filing, but as a specific subtype rather than by folding every
reimbursement change into a generic "regulatory action":

```
Government / Regulatory Action
  -> new regulation / compliance requirement
  -> enforcement / investigation
  -> approval or licensing decision
  -> government reimbursement/payment policy
      -> adverse rate/payment change
```

Two failure modes argue for the subtype: some rate changes are legislative, and
some are mechanical (an existing statutory formula producing a lower rate — no
new action at all). Boundary: **ordinary compliance with an existing tax regime
is NOT a regulatory action.** The line is a government affirmatively changing
policy versus a filer merely owing under standing law.
"""


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    argparse.ArgumentParser().parse_args()   # no flags: §14.9 deleted the dead
                                             # --provisional acknowledgement
    if PARAMETERS_STATUS != "OWNER_RATIFIED":
        raise SystemExit(
            "REFUSING TO RUN: design section 13 (n, bars, ceiling arm) is not "
            "owner-ratified. Set PARAMETERS_STATUS only on an owner ruling."
        )

    passed = []

    def check(name, cond, msg=""):
        if not cond:
            raise AssertionError(f"{name}: {msg}")
        passed.append(name)

    # ---- A0: the ratified parameter block is internally consistent --------
    check("A0_parameters_owner_ratified",
          PARAMETERS_STATUS == "OWNER_RATIFIED" and OPTION == "C"
          and RATIFIED_BARS == {"sentiment": 0.85, "guidance_direction": 0.85},
          "the §14 parameter block was edited away from the owner's ruling")
    check("A0_ga_targets_sum",
          sum(GA_TARGETS.values()) == N_GA_TOTAL == 100
          and N_TOTAL == 580 and N_GA_WITHDRAWN == N_GA_FLOOR["WITHDRAWN"])

    # ---- A1: inputs unchanged since pre-registration ---------------------
    inputs = {}
    for rel, want in INPUT_SHA256.items():
        got = sha256_file(ROOT / rel)
        check(f"A1_sha256:{rel}", got == want,
              f"{rel} changed since pre-registration ({got} != {want}). A "
              f"changed frame is a NEW pre-registration, not a silent re-draw.")
        inputs[rel] = {"sha256": got}

    lab = pd.read_parquet(ROOT / "data/f4/labels_e2_v1.parquet", columns=[
        "chunk_id", "section_type", "guidance_direction",
        "guidance_imputed_none", "passage_was_head_truncated", "parse_ok",
    ])
    ch = pd.read_parquet(ROOT / "data/f4/chunks_v1.parquet", columns=[
        "chunk_id", "section_type", "text", "home_cik", "home_company_name",
        "home_sector", "home_filing_date", "home_accession_number",
        "source_accession_numbers", "home_extraction_status",
        "home_extraction_confidence", "in_member_spell",
    ])
    train = pd.read_parquet(ROOT / "finetune/splits_v12/train.parquet",
                            columns=["home_accession_number", "text"])
    for rel, n in [("data/f4/labels_e2_v1.parquet", len(lab)),
                   ("data/f4/chunks_v1.parquet", len(ch)),
                   ("finetune/splits_v12/train.parquet", len(train))]:
        inputs[rel]["rows"] = int(n)
    inputs["labeling_rubric.md"]["rows"] = None
    inputs["data/hardening/spotcheck_v12/OWNER_POLICY_RULINGS.md"]["rows"] = None

    # ---- A2: the two parquets are the same corpus, same order ------------
    check("A2_corpus_rows", len(lab) == N_CORPUS and len(ch) == N_CORPUS)
    check("A2_chunk_id_unique", ch.chunk_id.is_unique)
    check("A2_chunk_id_set_and_order_equal",
          bool((lab.chunk_id.values == ch.chunk_id.values).all()))
    check("A2_parse_ok_all", bool(lab.parse_ok.all()))
    check("A2_train_rows", len(train) == 5736)

    # provenance join is positional because A2 pinned the order
    df = ch.copy()
    df["guidance_direction"] = lab.guidance_direction.values
    df["guidance_imputed_none"] = lab.guidance_imputed_none.fillna(False).values
    df["head_truncated"] = lab.passage_was_head_truncated.values

    # ---- A3: the frame is the corpus minus 8K_BODY -----------------------
    frame = df[df.section_type != "8K_BODY"].reset_index(drop=True)
    check("A3_frame_excludes_8k_body",
          len(frame) == N_FRAME and (frame.section_type != "8K_BODY").all(),
          f"frame is {len(frame)} rows, expected {N_FRAME}")

    # ---- A11: train-overlap and self-identification flags -----------------
    train_acc = set(train.home_accession_number)
    train_txt = {sha1_norm(t) for t in train.text}
    frame["train_overlap"] = (
        frame.home_accession_number.isin(train_acc)
        | frame.source_accession_numbers.map(
            lambda accs: any(a in train_acc for a in accs))
        | frame.text.map(lambda t: sha1_norm(t) in train_txt)
    )
    tokens = {n: distinctive_token(n) for n in frame.home_company_name.unique()}
    tok_col = frame.home_company_name.map(tokens)
    frame["selfid"] = [bool(t) and t in txt.lower()
                       for t, txt in zip(tok_col, frame.text)]
    check("A11_train_overlap_count",
          int(frame.train_overlap.sum()) == N_TRAIN_OVERLAP,
          f"{int(frame.train_overlap.sum())} != {N_TRAIN_OVERLAP}")
    check("A11_selfid_count", int(frame.selfid.sum()) == N_SELFID,
          f"{int(frame.selfid.sum())} != {N_SELFID}")

    frame["era"] = np.where(
        frame.home_filing_date.str.slice(0, 4).astype(int) >= 2019,
        "2019+", "pre-2019")

    # ---- allocation ------------------------------------------------------
    cell_counts = frame.groupby(["section_type", "home_sector"]).size()
    alloc_p = hamilton(cell_counts, N_PRIMARY)
    check("A4_allocation_p_sums", int(alloc_p.sum()) == N_PRIMARY)

    ga_frame = frame[(frame.section_type == "EX99_PRESS_RELEASE")
                     & frame.guidance_direction.isin(ACTIVE_GUIDANCE)]
    gn_frame = frame[(frame.section_type == "EX99_PRESS_RELEASE")
                     & frame.guidance_imputed_none]
    check("A5_ga_frame", len(ga_frame) == N_GA_FRAME, str(len(ga_frame)))
    check("A5_gn_frame", len(gn_frame) == N_GN_FRAME, str(len(gn_frame)))

    ga_counts = ga_frame.guidance_direction.value_counts()
    check("A15_ga_corpus_counts",
          all(int(ga_counts.get(d, 0)) == GA_CORPUS_COUNTS[d]
              for d in ACTIVE_GUIDANCE),
          f"active-EX99 direction counts {dict(ga_counts)} != GA_CORPUS_COUNTS")
    ga_weights = {d: round(GA_CORPUS_COUNTS[d] / N_GA_FRAME, 6)
                  for d in ACTIVE_GUIDANCE}
    check("A15_ga_weights_6dp", ga_weights == GA_WEIGHTS,
          f"w_d re-derived from the frame {ga_weights} != §14.4's pinned vector")

    # §14.3: proportional base, then the elementwise maximum against the floor
    ga_hamilton = hamilton(ga_counts, N_GA)
    alloc_ga_prop = {d: int(ga_hamilton[d]) for d in ACTIVE_GUIDANCE}
    alloc_ga = {d: max(alloc_ga_prop[d], N_GA_FLOOR.get(d, 0))
                for d in ACTIVE_GUIDANCE}
    quota_add = {d: alloc_ga[d] - alloc_ga_prop[d] for d in ACTIVE_GUIDANCE}
    check("A4_allocation_ga_sums", sum(alloc_ga.values()) == N_GA_TOTAL)
    check("A15_allocation_ga_targets", alloc_ga == GA_TARGETS,
          f"G-A targets {alloc_ga} != §14.3's pinned {GA_TARGETS}")
    check("A15_ga_proportional_base", sum(alloc_ga_prop.values()) == N_GA)

    # ---- the draw: one named child RNG stream per stratum, fixed order ----
    streams = spawn_streams()
    picked = {"P": [], "G-A": [], "G-N": []}
    subarm_of = {}

    by_cell = {k: g.chunk_id.values
               for k, g in frame.groupby(["section_type", "home_sector"])}
    for section in SECTIONS:
        for sector in SECTORS:
            ids = draw_from(by_cell[(section, sector)],
                            int(alloc_p[(section, sector)]),
                            streams[f"P|{section}|{sector}"])
            picked["P"] += ids
            subarm_of.update(dict.fromkeys(ids, "P"))
    taken = set(picked["P"])

    ga_pool = ga_frame[~ga_frame.chunk_id.isin(taken)]
    for d in ACTIVE_GUIDANCE:
        pool = ga_pool.loc[ga_pool.guidance_direction == d, "chunk_id"].values
        base = draw_from(pool, alloc_ga_prop[d], streams[f"G-A|{d}"])
        picked["G-A"] += base
        subarm_of.update(dict.fromkeys(base, "G-A"))
        if quota_add[d]:
            rest = np.array([c for c in pool if c not in set(base)])
            extra = draw_from(rest, quota_add[d], streams[f"G-A-quota|{d}"])
            picked["G-A"] += extra
            subarm_of.update(dict.fromkeys(
                extra, "G-A-withdrawn" if d == "WITHDRAWN" else "G-A-floor"))
    taken |= set(picked["G-A"])

    gn_pool = gn_frame[~gn_frame.chunk_id.isin(taken)]
    picked["G-N"] = draw_from(gn_pool.chunk_id.values, N_GN, streams["G-N"])
    subarm_of.update(dict.fromkeys(picked["G-N"], "G-N"))

    check("A6_arms_disjoint",
          len(set(picked["P"]) & set(picked["G-A"])) == 0
          and len(set(picked["P"]) & set(picked["G-N"])) == 0
          and len(set(picked["G-A"]) & set(picked["G-N"])) == 0)
    all_ids = picked["P"] + picked["G-A"] + picked["G-N"]
    check("A6_union_size",
          len(all_ids) == N_TOTAL and len(set(all_ids)) == N_TOTAL)

    arm_of = {c: a for a, ids in picked.items() for c in ids}
    drawn = frame[frame.chunk_id.isin(arm_of)].copy()
    drawn["arm"] = drawn.chunk_id.map(arm_of)
    drawn["subarm"] = drawn.chunk_id.map(subarm_of)
    check("A3_no_8k_body_in_draw", (drawn.section_type != "8K_BODY").all())

    p_rows = drawn[drawn.arm == "P"]
    realized_cells = p_rows.groupby(["section_type", "home_sector"]).size()
    cell_keys = [(s, k) for s in SECTIONS for k in SECTORS]
    check("A4_realized_cells_equal_allocation",
          all(int(realized_cells.get(k, 0)) == int(alloc_p[k])
              for k in cell_keys))
    realized_ga = drawn[drawn.arm == "G-A"].guidance_direction.value_counts()
    check("A4_realized_ga_equal_allocation",
          all(int(realized_ga.get(d, 0)) == alloc_ga[d]
              for d in ACTIVE_GUIDANCE),
          f"realized G-A {dict(realized_ga)} != targets {alloc_ga}")
    realized_subarm = drawn.subarm.value_counts()
    check("A15_realized_subarm",
          int(realized_subarm.get("G-A-floor", 0)) == quota_add["LOWERED"]
          and int(realized_subarm.get("G-A-withdrawn", 0)) == quota_add["WITHDRAWN"]
          and int(realized_subarm.get("G-A", 0)) == N_GA,
          f"sub-arm counts {dict(realized_subarm)} != two-stage allocation")

    # ---- batching: seeded permutation across arms ------------------------
    order = streams["batch_permutation"].permutation(sorted(all_ids))
    draw = pd.DataFrame({"chunk_id": order})
    draw["rank"] = np.arange(1, N_TOTAL + 1)
    draw["batch"] = [f"batch_{(r - 1) // BATCH_SIZE + 1:02d}" for r in draw["rank"]]
    draw["arm"] = draw.chunk_id.map(arm_of)

    meta = drawn.set_index("chunk_id")
    b_section = draw.chunk_id.map(meta.section_type)
    b_sector = draw.chunk_id.map(meta.home_sector)
    check("A9_no_homogeneous_batch",
          all(b_section[draw.batch == b].nunique() > 1
              and b_sector[draw.batch == b].nunique() > 1
              and draw.arm[draw.batch == b].nunique() > 1
              for b in draw.batch.unique()))
    check("A9_ceiling_batches_exist",
          set(CEILING_BATCHES) <= set(draw.batch.unique()),
          f"CEILING_BATCHES {CEILING_BATCHES} not all in the realized batching")

    # ---- write -----------------------------------------------------------
    OUT.mkdir(parents=True, exist_ok=True)
    BATCH_DIR.mkdir(parents=True, exist_ok=True)
    repro_paths = ([OUT / "draw_g2.csv", OUT.parent / ARMS_NAME,
                    OUT / "rater_policy_addendum.md"]
                   + sorted(BATCH_DIR.glob("batch_*.json")))
    prior = {p: p.read_bytes() for p in repro_paths if p.exists()}
    prior_params = None
    if (OUT / "draw_manifest.json").exists():
        old_manifest = json.loads((OUT / "draw_manifest.json").read_text())
        prior_params = {k: old_manifest.get(k) for k in PARAM_KEYS}
    # §14.8: the prior draw is superseded. Remove every stale batch file first
    # so a shorter previous draw cannot leave an orphan batch behind.
    for path in sorted(BATCH_DIR.glob("batch_*.json")):
        path.unlink()

    draw[["rank", "batch", "chunk_id"]].to_csv(
        OUT / "draw_g2.csv", index=False, lineterminator="\n")
    # §14.9: the arm map is a per-row disclosure of stored guidance status, so it
    # lives OUTSIDE the directory the raters are pointed at. Analysis re-joins it.
    draw[["chunk_id", "arm"]].to_csv(
        OUT.parent / ARMS_NAME, index=False, lineterminator="\n")
    texts = meta["text"]
    for b in sorted(draw.batch.unique()):
        payload = [{"chunk_id": c, "text": texts[c]}
                   for c in draw.loc[draw.batch == b, "chunk_id"]]
        (BATCH_DIR / f"{b}.json").write_text(
            json.dumps(payload, indent=1, ensure_ascii=False) + "\n")
    for b in CEILING_BATCHES:
        (BATCH_DIR / f"{b}_replicate.json").write_bytes(
            (BATCH_DIR / f"{b}.json").read_bytes())
    (OUT / "rater_policy_addendum.md").write_text(build_addendum())

    # ---- post-write assertions -------------------------------------------
    header = (OUT / "draw_g2.csv").read_text().splitlines()[0]
    check("A8_draw_csv_columns", header == "rank,batch,chunk_id", header)
    check("A8_arm_not_in_rater_pointed_tree", "arm" not in header,
          "the arm map is a stored-guidance disclosure and must not sit beside "
          "the batch files (§14.9)")
    arms_header = (OUT.parent / ARMS_NAME).read_text().splitlines()[0]
    check("A8_arms_sidecar_columns", arms_header == "chunk_id,arm", arms_header)
    check("A8_draw_csv_arm_domain", set(draw.arm) == {"P", "G-A", "G-N"},
          f"arm values {sorted(set(draw.arm))} outside §10.1's pinned domain")

    batch_files = sorted(BATCH_DIR.glob("batch_*.json"))
    n_batches = len([p for p in batch_files if "replicate" not in p.name])
    check("A9_batch_count", n_batches == -(-N_TOTAL // BATCH_SIZE)
          and n_batches == len(draw.batch.unique()), str(n_batches))
    batch_keys_seen = set()
    for path in batch_files:
        payload = json.loads(path.read_text())
        check(f"A7_batch_keys:{path.name}",
              isinstance(payload, list)
              and all(set(o) == BATCH_KEYS for o in payload),
              "a batch object carried keys beyond chunk_id/text")
        batch_keys_seen |= {k for o in payload for k in o}
    check("A13_no_forbidden_key_in_batches",
          not (batch_keys_seen & set(FORBIDDEN_KEYS)),
          f"batch key leak: {batch_keys_seen & set(FORBIDDEN_KEYS)}")
    for b in CEILING_BATCHES:
        check(f"A10_replicate_byte_identical:{b}",
              (BATCH_DIR / f"{b}_replicate.json").read_bytes()
              == (BATCH_DIR / f"{b}.json").read_bytes())

    addendum = (OUT / "rater_policy_addendum.md").read_text()
    low = addendum.lower()
    hits = sorted({t for t in set(tokens.values())
                   if t and re.search(rf"\b{re.escape(t)}\b", low)})
    check("A12_addendum_no_company_token", not hits, f"leaked: {hits}")
    check("A12_addendum_no_exemplar_id",
          not re.search(r"\b[AB]\d+\b", addendum),
          "an exemplar id survived redaction")
    check("A13_no_metadata_column_in_addendum",
          not [k for k in FORBIDDEN_IN_PROSE if k in low],
          "the addendum names a metadata column")

    csv_text = (OUT / "draw_g2.csv").read_text()
    check("A13_no_label_column_in_draw_csv",
          not [k for k in FORBIDDEN_KEYS if k in csv_text.splitlines()[0]])

    current_params = {"seed": SEED, "option": OPTION,
                      "parameters_status": PARAMETERS_STATUS,
                      "n_primary": N_PRIMARY, "n_ga": N_GA,
                      "n_ga_total": N_GA_TOTAL, "n_gn": N_GN,
                      "n_total": N_TOTAL, "batch_size": BATCH_SIZE,
                      "ceiling_batches": CEILING_BATCHES,
                      "rate_red_flags": RATE_RED_FLAGS,
                      "ratified_bars": RATIFIED_BARS,
                      "draw_schema": DRAW_SCHEMA}
    if prior and prior_params == current_params:
        now = {p: p.read_bytes() for p in repro_paths}
        diff = sorted(p.name for p in prior if prior[p] != now.get(p))
        check("A14_reproducible_byte_for_byte", not diff, f"changed: {diff}")
        reproduced = "byte_identical_to_prior_run"
    elif prior:
        changed_params = sorted(k for k in PARAM_KEYS
                                if (prior_params or {}).get(k) != current_params.get(k))
        reproduced = ("prior_artifacts_superseded_parameter_change; A14 not "
                      "applicable — the prior artifacts were written at a "
                      "different parameter/schema set and were replaced. "
                      f"Changed: {changed_params}")
    else:
        reproduced = "first_run_no_prior_artifacts"

    # ---- manifest --------------------------------------------------------
    # only the files THIS script generates; draw_manifest.json is excluded
    # because it is the file being written.
    generated = ([OUT / "draw_g2.csv", OUT.parent / ARMS_NAME,
                  OUT / "rater_policy_addendum.md"]
                 + sorted(BATCH_DIR.glob("batch_*.json")))
    outputs = {str(p.relative_to(ROOT)): sha256_file(p) for p in generated}

    def counts(series):
        return {str(k): int(v) for k, v in series.value_counts().items()}

    manifest = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generated_by": "data/f4/g2/build_draw_g2.py",
        "design_doc": DESIGN_DOC,
        "design_doc_sha256": sha256_file(ROOT / DESIGN_DOC),
        "seed": SEED,
        "option": OPTION,
        "parameters_status": PARAMETERS_STATUS,
        "parameters_note": (
            "OPTION C, b = 0.85 on both gate-bearing fields, the G-A direction "
            "quota, three ceiling batches and RATE_RED_FLAGS are the OWNER'S "
            "rulings of 2026-09-07, recorded in design section 14.1. The "
            "arithmetic implementing them (section 14.2-14.8) is model work, "
            "not owner judgement. This draw SUPERSEDES the provisional "
            "Option-B draw of 2026-09-06 (420 chunks, 11 batches, "
            "ratified_bars null); nothing had been rated when it was replaced, "
            "so no selection channel opens."),
        "n_primary": N_PRIMARY, "n_ga": N_GA, "n_ga_total": N_GA_TOTAL,
        "n_ga_floor": N_GA_FLOOR, "n_ga_withdrawn": N_GA_WITHDRAWN,
        "n_gn": N_GN, "n_total": N_TOTAL,
        "batch_size": BATCH_SIZE, "n_batches": n_batches,
        "draw_schema": DRAW_SCHEMA,
        "ceiling_batches": CEILING_BATCHES,
        "ceiling_rows": int(sum((draw.batch == b).sum() for b in CEILING_BATCHES)),
        "rate_red_flags": RATE_RED_FLAGS,
        "red_flags_status": (
            "EXPLORATORY / DISCLOSURE-ONLY per the owner's 2026-08-27 "
            "demotion ruling. Rated here only to regenerate the caveat "
            "constants; no gate branch, no kill rule, no re-promotion."),
        "ratified_bars": RATIFIED_BARS,
        "ga_corpus_counts": GA_CORPUS_COUNTS,
        "ga_weights": ga_weights,
        "ga_target_rule": GA_TARGET_RULE,
        "subarm_disposition": SUBARM_DISPOSITION,
        "probe_strata": PROBE_STRATA,
        "inputs": inputs,
        "outputs": outputs,
        "frame": {
            "n_corpus": int(len(df)),
            "n_frame": int(len(frame)),
            "excluded_8k_body": int((df.section_type == "8K_BODY").sum()),
            "section_counts": counts(frame.section_type),
            "sector_counts": counts(frame.home_sector),
            "era_counts": counts(frame.era),
            "distinct_home_ciks": int(frame.home_cik.nunique()),
            "distinct_home_accessions": int(frame.home_accession_number.nunique()),
            "train_overlap": int(frame.train_overlap.sum()),
            "selfid": int(frame.selfid.sum()),
        },
        "allocation_p": {f"{s}|{k}": int(alloc_p[(s, k)]) for s, k in cell_keys},
        "allocation_ga": {d: alloc_ga[d] for d in ACTIVE_GUIDANCE},
        "allocation_ga_proportional": {d: alloc_ga_prop[d] for d in ACTIVE_GUIDANCE},
        "allocation_ga_quota_added": {d: quota_add[d] for d in ACTIVE_GUIDANCE},
        "arm_frames": {"P": int(len(frame)), "G-A": int(len(ga_frame)),
                       "G-N": int(len(gn_frame))},
        "realized": {
            "arm_counts": counts(drawn.arm),
            "subarm_counts": counts(drawn.subarm),
            "section_counts": counts(drawn.section_type),
            "sector_counts": counts(drawn.home_sector),
            "era_counts": counts(drawn.era),
            "distinct_home_ciks": int(drawn.home_cik.nunique()),
            "distinct_home_accessions": int(drawn.home_accession_number.nunique()),
            "train_overlap": {
                "overlap": int(drawn.train_overlap.sum()),
                "novel": int((~drawn.train_overlap).sum())},
            "selfid": {"selfid": int(drawn.selfid.sum()),
                       "not_selfid": int((~drawn.selfid).sum())},
            "in_member_spell": counts(drawn.in_member_spell.astype(str).str.lower()),
            "extraction_confidence": counts(drawn.home_extraction_confidence),
            "extraction_status": counts(drawn.home_extraction_status),
            "head_truncated": int(drawn.head_truncated.sum()),
            "guidance_active_directions": {d: int(realized_ga.get(d, 0))
                                           for d in ACTIVE_GUIDANCE},
            "guidance_active_directions_by_subarm": {
                d: counts(drawn.loc[(drawn.arm == "G-A")
                                    & (drawn.guidance_direction == d), "subarm"])
                for d in ACTIVE_GUIDANCE},
            "by_arm": {
                arm: {"n": int((drawn.arm == arm).sum()),
                      "section_counts": counts(drawn.loc[drawn.arm == arm, "section_type"]),
                      "sector_counts": counts(drawn.loc[drawn.arm == arm, "home_sector"]),
                      "era_counts": counts(drawn.loc[drawn.arm == arm, "era"]),
                      "train_overlap": int(drawn.loc[drawn.arm == arm, "train_overlap"].sum()),
                      "selfid": int(drawn.loc[drawn.arm == arm, "selfid"].sum())}
                for arm in ["P", "G-A", "G-N"]},
        },
        "batches": {b: int((draw.batch == b).sum())
                    for b in sorted(draw.batch.unique())},
        "train_overlap_definition": TRAIN_OVERLAP_DEFINITION,
        "selfid_definition": SELFID_DEFINITION,
        "assertion_scope_note": (
            "Design 10.1.2 item 13 is implemented per file: batch files are "
            "checked on KEYS (a passage may legitimately contain the word "
            "'sentiment'), draw_g2.csv on its header, the addendum on strings. "
            "draw_manifest.json is not rater-visible (design 5.1) and carries "
            "the pre-registered aggregate keys rate_red_flags / allocation_ga "
            "by name; it is asserted to contain no drawn chunk_id and no "
            "per-row label."),
        "reproducibility_check": reproduced,
        "assertions_passed": passed,
        "api_calls": 0, "gpu_seconds": 0, "network_calls": 0,
    }
    blob = json.dumps(manifest, indent=1)
    assert not any(c in blob for c in all_ids), \
        "draw_manifest.json leaked a drawn chunk_id"
    (OUT / "draw_manifest.json").write_text(blob + "\n")

    print(json.dumps({k: manifest[k] for k in
                      ["seed", "option", "parameters_status", "n_total",
                       "n_batches", "ceiling_batches", "ratified_bars",
                       "allocation_p", "allocation_ga",
                       "allocation_ga_proportional", "allocation_ga_quota_added",
                       "arm_frames", "realized", "batches",
                       "reproducibility_check"]}, indent=1))
    print(f"\n{len(passed)} assertions passed:")
    for name in passed:
        print(f"  {name}")


if __name__ == "__main__":
    main()
