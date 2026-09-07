"""
analyze_g2.py — THE PINNED ANALYSIS for the G2 E2 student-label spot-check.

2026-09-07: owner rulings §14 — bars ratified (0.85 both gate-bearing fields,
so the un-ratified refusal path lifts), three ceiling batches pooled for
S-NOISE, and the ONE added estimator the G-A quota requires: the corpus
re-weighted active precision of §14.4, with per-direction disclosure carrying
`bar: null`. Still written before any verdict exists (verdicts/ absent).

2026-09-07 (fix pass, design §14.9 — model amendment, NOT an owner ruling, made
while verdicts/ is still absent). Five changes, each with its reason:
  * §6.6's paragraph now carries the SAME two guidance terms `_guidance_line()`
    carries, and A8 became a FIELD scan — owner ruling (vii) OPTION 1 was
    enforced only on the machine-formatted line, so the most quotable sentence
    in the report stated the guidance verdict alone.
  * §6.6's opening clause is the pre-registered one again ("did not trigger a
    decisive failure"), and the paragraph is verdict-gated — "returned PASS"
    was an unlabelled strengthening of the sentence §6.6 exists to weaken.
  * the "[UB, 0.94]" clause is deleted: 0.94 was a literal inherited from a
    different (n, bar) and nothing recomputed it, so it shipped as a malformed
    interval with one measured endpoint and one undocumented constant.
  * the guidance base-rate caveat and the ceiling arm's evaluable sizes are
    computed from the REALIZED draw instead of quoting planning approximations.
  * `arm` is read from the sidecar outside data/f4/g2/ (§14.9), and the
    non-decisional-bar appendix prints only what actually differs at the
    non-ratified bar (k*, p_hat-required) rather than a second copy of the
    ratified bar's p_hat and CI.

Written 2026-09-06, BEFORE any rater verdict, adjudication or owner ruling
exists. This file IS the pre-registration in code (design §10.2): the
applicability mask, the Wilson convention, the omission conventions, the
unsure rule and its sensitivity bracket, the k* arithmetic, the clustered
bootstrap and the seeded owner-probe draw are all fixed here so that no
degree of freedom can be chosen after seeing results.

Design prose: data/f4/g2/G2_SPOTCHECK_design.md (pre-registered 2026-09-06).
Precedent: data/hardening/spotcheck_v12/analyze_v12.py.

READ-ONLY inputs (never written, never modified):
  data/f4/labels_e2_v1.parquet     stored student labels, joined HERE only
  data/f4/chunks_v1.parquet        section_type + provenance + text
  finetune/splits_v12/train.parquet  frozen retrain split (overlap flag)
  data/f4/g2/draw_g2.csv           rank,batch,chunk_id  (from build_draw_g2.py)
  data/f4/g2_draw_arms.csv         chunk_id,arm — OUTSIDE the rater-pointed
                                   tree by §14.9, joined here
  data/f4/g2/draw_manifest.json    ratified n / bars / probe strata / shas
  data/f4/g2/batches/batch_NN.json rater batch files ({chunk_id,text} only)
  data/f4/g2/verdicts/rater_a_batchNN.json    blind rater A (required)
  data/f4/g2/verdicts/rater_b_batchNN.json    ceiling replicate  (optional)
  data/f4/g2/adjudications/adjudications.json (optional)
  data/f4/g2/failed_batches.json              (optional, §11.3 re-run record)
  data/f4/g2/owner_rulings.json               (optional, supersedes)
  data/f4/g2/probe_rulings.json               (optional)

WRITES (only under data/f4/g2/):
  results_g2.json          every estimator, machine-readable (design §10.2.6)
  report_g2.md             the printed report
  probe_ids.json           the seeded S-PROBE draw of uncontested rows
  draw_g2_provenance.csv   per-drawn-row provenance, written at ANALYSIS time

Any input that does not exist yet is reported as "not yet available" and the
script degrades gracefully — it never invents a number and never fails on a
missing artifact. It DOES hard-fail on: a changed frame (sha mismatch), an
un-ratified bar, a rater file that violates the §10.2.1 schema guard, and any
of the §10.2.7 assertions.

Cost: 0 API calls, 0 GPU seconds, 0 network. Runtime ~40 s (one streaming
pass over chunks_v1.parquet for the train-overlap / self-id flags).

PROVENANCE RULE (HANDOFF §3/§7): every rate produced here is model-consensus
agreement, with owner rulings superseding on the escalated subset. It is NOT
human validation of ground truth. For the gate-bearing fields the rater's
model family is the teacher's model family, so teacher error the student
memorized is invisible here and the estimate is plausibly OPTIMISTIC
(design §12.1).

red_flags is EXPLORATORY / DISCLOSURE-ONLY (owner ruling 2026-08-27). Nothing
in this file can re-promote it. distress_tier is never scored.
"""

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from math import comb, sqrt
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

# ----------------------------------------------------------------- paths
ROOT = Path(__file__).resolve().parents[3]   # data/f4/g2/<this file> -> repo root
G2 = ROOT / "data" / "f4" / "g2"
LABELS = ROOT / "data" / "f4" / "labels_e2_v1.parquet"          # READ-ONLY
CHUNKS = ROOT / "data" / "f4" / "chunks_v1.parquet"             # READ-ONLY
TRAIN = ROOT / "finetune" / "splits_v12" / "train.parquet"      # READ-ONLY

# ------------------------------------------------------------- constants
Z = 1.96                       # exactly, per design §10.0
SEED = 20260906                # probe draw AND cluster bootstrap
BOOT = 10000
PROBE_N = 20
PROBE_ESCALATION_K = 2
PROBE_STRATA_DEFAULT = {"P": 12, "G-A": 4, "G-N": 4}
CANDIDATE_BARS = (0.85, 0.90)  # §13-ii menu; a VERDICT is emitted only at the ratified bar

# ---- OWNER-RATIFIED PARAMETERS (owner, 2026-09-07, design §14.1; §10.1 block).
# This script READS them from draw_manifest.json and asserts they equal the copy
# below (§10.0). It contains no default that would let it run un-ratified: an
# unset bar or a parameters_status other than OWNER_RATIFIED is a REFUSAL (exit
# 2), and a manifest that disagrees with this block is a HARD FAIL — that is the
# guard against a bar or an n edited after the data exists.
PARAMETERS_STATUS = "OWNER_RATIFIED"
RATIFIED = {
    "seed": 20260906,
    "option": "C",
    "n_primary": 400,
    "n_ga": 80,
    "n_ga_total": 100,
    "n_ga_floor": {"LOWERED": 15, "MAINTAINED": 20, "WITHDRAWN": 15},
    "n_gn": 80,
    "n_total": 580,
    "batch_size": 40,
    "ceiling_batches": ["batch_01", "batch_02", "batch_03"],
    "rate_red_flags": True,
    "ratified_bars": {"sentiment": 0.85, "guidance_direction": 0.85},
    "ga_corpus_counts": {"RAISED": 3716, "MAINTAINED": 1940,
                         "LOWERED": 757, "WITHDRAWN": 66},
    "probe_strata": {"P": 12, "G-A": 4, "G-N": 4},
}
# §14.6 planning n, so a realized-vs-planned drift is visible rather than silent.
# The verdict is ALWAYS recomputed at the realized n (§6.1); these never gate.
DESIGN_PLANNED_N = {"sentiment": 337, "guidance_direction": 119}
# §14.5 PLANNING expectation for the applicability-masked ceiling arm, kept only
# so planned-vs-realized drift is visible. The realized sizes are deterministic
# from the draw and are computed at run time by ceiling_realized_n() (§14.9);
# nothing here is quoted as if it were a measurement.
CEILING_PLANNED_N = {"sentiment": 107, "guidance_direction": 62}

# §11.3's exhaustive list of what "failed" may mean. A batch may NEVER be
# re-run because of what its verdicts say, so the cause is checked against this
# closed set rather than accepted as free text (§14.9 gave the record a file).
FAILED_BATCH_CAUSES = frozenset({
    "agent_errored", "non_parsing_json", "chunk_id_set_mismatch",
    "missing_required_field", "schema_violation"})

GATE_FIELDS = ("sentiment", "guidance_direction")
RED = "red_flags"
FIELDS_ALL = ("sentiment", "guidance_direction", RED)

# §1.2 applicability matrix, applied at analysis time from section_type
APPLICABLE = {
    "sentiment": {"MDA", "EX99_PRESS_RELEASE"},
    "guidance_direction": {"EX99_PRESS_RELEASE"},
    RED: {"MDA", "RISK_FACTORS", "EX99_PRESS_RELEASE"},
}
SECTIONS = ("MDA", "EX99_PRESS_RELEASE", "RISK_FACTORS")
ACTIVE_GUIDANCE = ("RAISED", "MAINTAINED", "LOWERED", "WITHDRAWN")
SENTIMENT_VALUES = ("POSITIVE", "NEUTRAL", "NEGATIVE")
GUIDANCE_VALUES = ("RAISED", "MAINTAINED", "LOWERED", "WITHDRAWN", "NONE")
CATS = ("DEMAND_WEAKNESS", "SUPPLY_INPUT_CONSTRAINT", "TRADE_POLICY_EXPOSURE",
        "IMPAIRMENT_WRITEDOWN", "MARGIN_COST_PRESSURE", "LEGAL_REGULATORY_ACTION")
MISSING = "__MISSING_FIELD__"   # the finetune/eval.py omission sentinel (§1.3)

RED_FLAGS_STATUS = ("exploratory / disclosure-only (owner ruling 2026-08-27); "
                    "this pass cannot change it.")
PROVENANCE = ("model-consensus agreement (blind rater + adjudicator, both "
              "Claude-family) with owner rulings superseding on the escalated "
              "subset; NOT human validation of ground truth (HANDOFF §3).")

# Design-pinned frame facts, re-derived from the artifacts on 2026-09-06 and
# checked again at run time. A mismatch is REPORTED, never silently absorbed.
FRAME_EXPECT = {
    "n_corpus": 317081, "n_frame": 316291, "excluded_8k_body": 790,
    "section_counts": {"MDA": 172098, "EX99_PRESS_RELEASE": 94545, "RISK_FACTORS": 49648},
    "ga_frame": 6479, "gn_frame": 48293,
    "offmatrix_sentiment_risk_factors": 4177,
    "offmatrix_guidance_mda": 2803, "offmatrix_guidance_risk_factors": 23,
    "offmatrix_guidance_active": 230,
    "train_overlap_rows": 14342, "train_overlap_share": 0.04535,
    "selfid_share": 0.4646,
}

# Comparison rows — DESCRIPTIVE ONLY, no decision reads them (design §7).
COMPARISONS = [
    {"name": "epoch-2 eval, sentiment exact match (student vs TEACHER, E1 eval split)",
     "other_value": {"k": 725, "n": 867, "point": 725 / 867},
     "g2_key": "sentiment"},
    {"name": "epoch-2 eval, guidance raw exact match (student vs TEACHER, E1 eval split)",
     "other_value": {"k": 297, "n": 570, "point": 297 / 570},
     "g2_key": "guidance_direction"},
    {"name": "epoch-2 eval, red-flag exact-set agreement (student vs TEACHER, E1)",
     "other_value": {"point": 0.6307}, "g2_key": "red_flags"},
    {"name": "H3v2 retention, sentiment_mean_score (filing-level Pearson, n=630 filings)",
     "other_value": {"point": 0.8696, "ci": [0.8153, 0.9109]}, "g2_key": "sentiment"},
    {"name": "H3v2 retention, guidance_any_present (filing-level Pearson, n=630 filings)",
     "other_value": {"point": 0.7534, "ci": [0.5356, 0.9114]}, "g2_key": "guidance_direction"},
    {"name": "v1.2 TEACHER spot-check, owner-ratified exact-set ERROR (P1)",
     "other_value": {"k": 84, "n": 200, "point": 0.42, "ci": [0.3537, 0.4893]},
     "g2_key": "red_flags"},
]
COMPARISON_CAVEAT = (
    "DESCRIPTIVE ONLY. Different reference (teacher / feature vector / different "
    "labeler), different corpus, different protocol, and in the H3v2 rows a "
    "different UNIT (filing-level correlation vs chunk-level proportion). No "
    "difference interval is computed — newcombe() is struck (design §7).")

# §3.3 anchor 2: same student, same adapter, different corpus.
E1_STUDENT_OMISSION = {"k": 390, "n": 1179, "point": 390 / 1179}
E2_STUDENT_OMISSION_FRAME = {"k": 48790, "n": 95335, "point": 48790 / 95335}

def guidance_base_caveat(n_ex99, n_imputed_none, n_active):
    """§6.3's binding caveat, with the counts COMPUTED from the realized draw.

    2026-09-07 (§14.9): these were shipped as the planning approximations
    "~61 / ~8" while the draw was fixed and the true values computable. A
    projection where a measurement exists is exactly what this caveat is
    supposed to stop other people doing.
    """
    return (
        "A PASS on guidance-P is a statement about the NONE mass only. Of the "
        f"{n_ex99} EX99 rows in P (realized draw), {n_imputed_none} are "
        "guidance_imputed_none=true rows scored AS NONE by the §1.3 writer rule "
        f"and only {n_active} carry an active direction, so the bar can be "
        "cleared almost entirely by the writer rule being right about the NONE "
        "mass. It is NOT evidence about the RAISED / LOWERED / MAINTAINED / "
        "WITHDRAWN calls that drive guidance_signed_mean. G-A's active precision "
        "(pooled, corpus-re-weighted) and G-N's false-NONE rate must be quoted in "
        "every table where the guidance verdict appears, and no headline may cite "
        "the guidance verdict alone.")
GA_POOLED_ESTIMAND = (
    "P(adjudicated reference == the stored active value | stored is that active "
    "value), re-weighted to the corpus direction shares w_d = N_d/6479 because "
    "G-A is a QUOTA arm after the owner's 2026-09-07 ruling (vi): LOWERED is "
    "11.7% of the corpus and 15% of the arm, WITHDRAWN 1.0% and 15%. The "
    "unweighted pooled proportion would answer a different question (§14.4).")
GA_DIRECTION_DISCLOSURE = (
    "disclosure only; no bar (owner rulings 2026-09-07 items (iv) and (vi)). "
    "Per-direction Wilson half-widths at p_hat=0.80 are +-11.3 (RAISED), +-15.4 "
    "(MAINTAINED), +-19.1 (LOWERED), +-19.1 (WITHDRAWN) points — the quota buys "
    "that the value GUIDANCE_MAP sends to -1 stops being literally unmeasured, "
    "NOT that it becomes resolved (§14.3). No per-direction number satisfies "
    "§6.3's binding caveat; only the pooled re-weighted estimate does.")
SENTIMENT_CAVEAT = (
    "Chunk-level label accuracy under the §1.2 applicability mask (MDA + "
    "EX99_PRESS_RELEASE). Omitted stored values are scored as errors (§1.3); "
    "S-OMIT restates the rate with them excluded. This is NOT EXPANSION_PLAN "
    "§2a's feature-level reliability lambda and must not be used as one (§6.5).")

STOP_TOKENS = {"inc", "inc.", "corp", "corp.", "corporation", "company", "co", "co.",
               "the", "of", "and", "group", "holdings", "holding", "ltd", "llc", "plc",
               "&", "/de/", "international", "industries", "systems", "technologies", "com"}
_WS = re.compile(r"\s+")
FORBIDDEN_RESULT_KEYS = {"lambda", "reliability", "attenuation_denominator"}
NETWORK_MODULES = ("requests", "httpx", "aiohttp", "urllib3", "anthropic", "openai")


# ------------------------------------------------------ statistical core
def wilson_p(p, n, z=Z):
    """The §10.0 Wilson formula with p supplied instead of k/n.

    Used by wilson() and by the §14.4 stratified interval (p_hat_active on an
    effective n). It is the SAME three lines, not a second interval method.
    """
    if n <= 0:
        return (float("nan"), float("nan"))
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (min(1.0, max(0.0, c - h)), min(1.0, max(0.0, c + h)))


def wilson(k, n, z=Z):
    """95% Wilson score interval, no continuity correction, no FPC, clipped."""
    if n == 0:
        return (float("nan"), float("nan"))
    return wilson_p(k / n, n, z)


def kstar_pass(n, b):
    """Smallest agreement count k whose Wilson LOWER bound >= b (PASS)."""
    for k in range(n + 1):
        if wilson(k, n)[0] >= b:
            return k
    return None


def kstar_fail(n, b):
    """Largest agreement count k whose Wilson UPPER bound < b (DECISIVE FAIL)."""
    for k in range(n, -1, -1):
        if wilson(k, n)[1] < b:
            return k
    return -1


def _binom_tail(n, q, lo, hi):
    return sum(comb(n, i) * q ** i * (1 - q) ** (n - i) for i in range(lo, hi + 1))


def p_pass(n, q, b):
    """Exact binomial P(PASS) if true agreement is q."""
    k = kstar_pass(n, b)
    return 0.0 if (k is None or n == 0) else _binom_tail(n, q, k, n)


def p_fail(n, q, b):
    """Exact binomial P(DECISIVE FAIL) if true agreement is q."""
    k = kstar_fail(n, b)
    return 0.0 if (k < 0 or n == 0) else _binom_tail(n, q, 0, k)


def verdict_of(k, n, b):
    if n == 0:
        return "NO_DATA"
    lo, hi = wilson(k, n)
    if lo >= b:
        return "PASS"
    if hi < b:
        return "DECISIVE_FAIL"
    return "INDETERMINATE"


def cluster_bootstrap(per_chunk_errors, decisions_per_chunk, seed=SEED, boot=BOOT):
    """Chunk-clustered percentile bootstrap for the per-decision error rate.

    per_chunk_errors: array of wrong-decision counts, one entry per chunk.
    The chunk is the cluster; resampling chunks (not decisions) is the honest
    interval. The naive binomial over n*decisions is ANTI-CONSERVATIVE.
    """
    a = np.asarray(per_chunk_errors, dtype=float)
    if a.size == 0:
        return None
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, a.size, size=(boot, a.size))
    draws = a[idx].sum(axis=1) / (a.size * decisions_per_chunk)
    return [float(np.percentile(draws, 2.5)), float(np.percentile(draws, 97.5))]


# --------------------------------------------------------------- helpers
def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 22), b""):
            h.update(block)
    return h.hexdigest()


def load_json(relpath, default=None):
    p = G2 / relpath
    if not p.exists():
        return default
    return json.loads(p.read_text())


def as_set(flags):
    """Normalize red_flags to a frozenset of (CATEGORY, MODALITY)."""
    if flags is None:
        return None
    if isinstance(flags, float):          # NaN from pandas
        return None
    out = []
    for e in flags:
        if isinstance(e, dict):
            out.append((e["category"], e["modality"]))
        else:
            out.append((e[0], e[1]))
    return frozenset(out)


def norm_text(t):
    return _WS.sub(" ", t).strip().lower()


def company_token(name):
    """First token of the company name longer than 2 chars and not a generic
    suffix, punctuation-stripped, lowercased (design §5.1/§10.1).

    Punctuation stripping is required to reproduce the design's pinned 46.46%
    ('Tesla, Inc.' -> 'tesla', not 'tesla,'); re-derived 2026-09-06:
    46.4629% frame / EX99 71.1407% / MDA 39.0254% / RISK_FACTORS 25.2498%.
    """
    if not isinstance(name, str):
        return None
    for raw in name.lower().split():
        t = raw.strip(".,&/-'\"()")
        if len(t) > 2 and t not in STOP_TOKENS:
            return t
    return None


def pct(x):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.2%}"


def fmt_rate(k, n):
    if not n:
        return "n=0 — not yet available"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {k/n:.2%}  95% Wilson [{lo:.2%}, {hi:.2%}]  (+-{(hi-lo)/2:.2%})"


# --------------------------------------------------------------- scoring
def stored_values(row, rate_red_flags):
    """Stored student label per field, with the §1.3 omission conventions.

    sentiment null on an applicable row -> MISSING (scored as error).
    guidance_direction null (bad enum)  -> MISSING (scored as error).
    guidance_imputed_none=true rows carry stored 'NONE' and are scored AS NONE
      (the writer rule is adopted); branch on the stored columns, never on
      schema_valid (design §1.3 implementer's trap).
    """
    out = {}
    s = row.get("sentiment")
    out["sentiment"] = s if isinstance(s, str) and s else MISSING
    g = row.get("guidance_direction")
    out["guidance_direction"] = g if isinstance(g, str) and g else MISSING
    if rate_red_flags:
        rf = as_set(row.get("red_flags"))
        out[RED] = frozenset() if rf is None else rf
    return out


def score(draw, stored, section_of, rater_a, adj, owner, rate_red_flags):
    """Build the long (chunk, field) scoring frame — the pinned §10.2.4 table.

    draw       : DataFrame with columns rank, batch, arm, chunk_id
    stored     : {chunk_id: {field: value}}   value MISSING for omissions
    section_of : {chunk_id: section_type}
    rater_a    : {chunk_id: {field: value}}
    adj, owner : {(chunk_id, field): ruling dict}
    Returns a DataFrame; err is 1.0 / 0.0 / NaN (NaN = non-evaluable).
    """
    fields = list(GATE_FIELDS) + ([RED] if rate_red_flags else [])
    rows = []
    for r in draw.itertuples():
        cid = r.chunk_id
        if cid not in rater_a:
            continue
        sec = section_of.get(cid)
        for f in fields:
            applicable = sec in APPLICABLE[f]
            sv = stored[cid][f]
            rv = rater_a[cid].get(f)
            contested = bool(sv != rv)
            key = (cid, f)
            ruling = owner.get(key) or adj.get(key)
            src = "owner" if key in owner else ("adjudicator" if key in adj else None)
            omission = (sv == MISSING)
            if not applicable:
                err, basis, ref = np.nan, "masked", None
            elif omission:
                # §1.3: pre-registered as an error. Any adjudication on an
                # omission row is IGNORED — the convention is pre-registered.
                err, basis, ref = 1.0, "omission_pinned_error", None
            elif not contested and ruling is None:
                err, basis, ref = 0.0, "uncontested", sv
            elif not contested:
                # only reachable after the §5.5 probe-escalation sweep
                ref = _reference(ruling, sv, f)
                if ref is None:
                    err, basis = np.nan, "unsure"
                else:
                    err = float(ref != sv)
                    basis = f"escalation_{src}"
            elif ruling is None:
                err, basis, ref = np.nan, "contested_unadjudicated", None
            else:
                ref = _reference(ruling, sv, f)
                if ref is None:
                    err, basis = np.nan, "unsure"
                else:
                    err, basis = float(ref != sv), src
            rows.append(dict(chunk_id=cid, arm=r.arm, batch=r.batch, field=f,
                             section_type=sec, applicable=applicable, stored=sv,
                             rater=rv, ref=ref, err=err, basis=basis,
                             contested=contested, omission=omission))
    return pd.DataFrame(rows)


def _reference(ruling, stored_val, field):
    """The adjudicated/owner reference value, or None if unsure/unusable.

    Owner rulings carry {correct_label} and no verdict word — an owner ruling
    IS the reference. Adjudications carry verdict in {agree, disagree, unsure}.
    """
    if "verdict" in ruling:
        v = ruling["verdict"]
        if v == "agree":
            return stored_val
        if v == "unsure":
            return None
        cl = ruling.get("correct_label")
        return as_set(cl) if field == RED else cl
    cl = ruling.get("correct_label")
    if cl is None:
        return None
    return as_set(cl) if field == RED else cl


def counts(sub):
    """(k_agree, k_err, n_evaluable, n_unsure, n_unadjudicated, n_nonevaluable)."""
    ev = sub[sub.err.notna()]
    k_agree = int((ev.err == 0).sum())
    k_err = int((ev.err == 1).sum())
    n = len(ev)
    n_unsure = int((sub.basis == "unsure").sum())
    n_unadj = int((sub.basis == "contested_unadjudicated").sum())
    return k_agree, k_err, n, n_unsure, n_unadj, n_unsure + n_unadj


def rate_block(sub, count_errors=False, interval="naive_binomial"):
    """A k/n rate with its Wilson interval. Agreement by default; error if asked."""
    k_agree, k_err, n, n_unsure, n_unadj, n_non = counts(sub)
    k = k_err if count_errors else k_agree
    lo, hi = wilson(k, n) if n else (None, None)
    return {"k": k, "n": n, "p_hat": (k / n) if n else None,
            "wilson_lo": lo, "wilson_hi": hi,
            "wilson_95": [lo, hi], "interval": interval,
            "n_unsure": n_unsure, "n_unadjudicated": n_unadj,
            "n_nonevaluable": n_non,
            "scale": "error" if count_errors else "agreement"}


def primary_block(sub, bar, caveat):
    """The gate-bearing primary: agreement rate, verdict at the ONE ratified bar."""
    b = rate_block(sub)
    k, n, n_non = b["k"], b["n"], b["n_nonevaluable"]
    b["bar"] = bar
    b["kstar_pass"] = kstar_pass(n, bar) if n else None
    b["kstar_fail"] = kstar_fail(n, bar) if n else None
    b["verdict"] = verdict_of(k, n, bar)
    b["verdict_rule"] = ("PASS iff Wilson lower bound >= bar; DECISIVE_FAIL iff "
                         "Wilson upper bound < bar; INDETERMINATE otherwise")
    b["sens_all_error"] = list(wilson(k, n + n_non)) if (n + n_non) else None
    b["sens_all_agree"] = list(wilson(k + n_non, n + n_non)) if (n + n_non) else None
    b["provisional"] = bool(b["n_unadjudicated"] > 0)
    b["n_omission_pinned_errors"] = int((sub.basis == "omission_pinned_error").sum())
    b["operating_characteristics_at_realized_n"] = {
        "P_DECISIVE_FAIL_if_q_0.83": p_fail(n, 0.83, bar) if n else None,
        "P_DECISIVE_FAIL_if_q_0.85": p_fail(n, 0.85, bar) if n else None,
        "P_PASS_if_q_0.90": p_pass(n, 0.90, bar) if n else None,
        "P_PASS_if_q_0.95": p_pass(n, 0.95, bar) if n else None,
    }
    b["caveat"] = caveat
    return b


def subgroup(sub, by, count_errors=False):
    """Naive-binomial subgroup rates. Ignores company clustering — labelled."""
    out = {}
    for lvl, g in sub.groupby(sub[by].astype(str), dropna=False):
        out[str(lvl)] = rate_block(g, count_errors=count_errors)
    return out


def ga_weights_from_counts(counts_by_direction):
    """w_d = N_d / sum(N_d) over the four ACTIVE_GUIDANCE values (§14.4)."""
    tot = sum(counts_by_direction[d] for d in ACTIVE_GUIDANCE)
    assert tot > 0, "G-A corpus counts sum to zero"
    return {d: counts_by_direction[d] / tot for d in ACTIVE_GUIDANCE}, tot


def ga_pooled(k_by_dir, n_by_dir, weights):
    """The §14.4 arithmetic, on counts only — no DataFrame, no pandas.

    Kept separate so the pre-registered BEHAVIOUR of the estimator (§14.4's
    three pinned cases, computed before data) is checkable by --selftest at the
    real arm sizes, where p_hat_d = 0.80 implies a non-integer k_d.
    """
    p_hat = sum(weights[d] * (k_by_dir[d] / n_by_dir[d]) for d in ACTIVE_GUIDANCE)
    p_tilde_d, V = {}, 0.0
    for d in ACTIVE_GUIDANCE:
        n = n_by_dir[d]
        pt = (k_by_dir[d] + Z * Z / 2) / (n + Z * Z)
        p_tilde_d[d] = pt
        V += weights[d] ** 2 * pt * (1 - pt) / n
    p_tilde = sum(weights[d] * p_tilde_d[d] for d in ACTIVE_GUIDANCE)
    n_eff = p_tilde * (1 - p_tilde) / V
    lo, hi = wilson_p(p_hat, n_eff)
    return {"point": p_hat, "wilson_lo": lo, "wilson_hi": hi,
            "n_eff": n_eff, "p_tilde": p_tilde}


def ga_reweighted(ga_rows, weights, complete):
    """§14.4's pinned quota estimator — the ONE estimator this pass adds.

    G-A stopped being proportional when the owner bought the direction quota
    (ruling 2026-09-07 (vi)), so the unweighted pooled proportion would
    over-weight LOWERED and WITHDRAWN. Pinned, before data:

        p_hat_active = SUM_d w_d * p_hat_d
        p_tilde_d    = (k_d + z^2/2) / (n_d + z^2)     Wilson centre; never 0/1
        V            = SUM_d w_d^2 * p_tilde_d*(1 - p_tilde_d) / n_d
        p_tilde      = SUM_d w_d * p_tilde_d
        n_eff        = p_tilde*(1 - p_tilde) / V       reported ALWAYS
        CI           = wilson_p(p_hat_active, n_eff)

    The plain delta-method interval p_hat +- z*sqrt(V) is NOT implemented: it
    returns zero width when a direction lands at p_hat_d == 1, which at n_d = 15
    is not a remote outcome.

    `complete` is True only when every drawn chunk is rated and no G-A row is
    contested-and-unadjudicated. A direction with n_d == 0 in that state is a
    HARD FAIL, never a silent renormalisation — dropping a stratum changes the
    estimand (§10.2.4). Before that state the pooled point is simply not
    computed; nothing is invented.

    Returns (pooled_block, by_direction_block).
    """
    by_dir, empty = {}, []
    for d in ACTIVE_GUIDANCE:
        blk = rate_block(ga_rows[ga_rows.stored == d])
        blk["corpus_weight"] = weights[d]
        blk["bar"] = None
        blk["note"] = GA_DIRECTION_DISCLOSURE
        by_dir[d] = blk
        if not blk["n"]:
            empty.append(d)

    n_nominal = sum(by_dir[d]["n"] for d in ACTIVE_GUIDANCE)
    pooled = {
        "point": None, "wilson_lo": None, "wilson_hi": None,
        "n_eff": None, "n_nominal": n_nominal,
        "n_applicable": int(len(ga_rows)),
        "n_nonevaluable": int(len(ga_rows)) - n_nominal,
        "weights": {d: weights[d] for d in ACTIVE_GUIDANCE},
        "bar": None,
        "estimand": GA_POOLED_ESTIMAND,
        "interval": "stratified_wilson_via_n_eff",
        "weights_are_never_renormalised": True,
        "note": ("the POOLED re-weighted number is what §6.3's binding caveat "
                 "requires on the guidance verdict's line; no per-direction "
                 "number satisfies it. No bar (rulings (iv), (vi))."),
    }
    if empty:
        if complete:
            raise AssertionError(
                f"G-A direction(s) {empty} have n_d == 0 after applicability masking "
                "and unsure removal, with every drawn chunk rated and every contested "
                "G-A row adjudicated. The weights are NOT renormalised — a dropped "
                "stratum changes the estimand (§10.2.4). Report the arm as incomplete "
                "and restate n; never re-spread w_d over the surviving directions.")
        pooled["not_yet_available"] = True
        pooled["empty_directions"] = empty
        pooled["blocked_reason"] = (
            f"directions {empty} have no evaluable row yet; the pooled point is NOT "
            "computed and the weights are NOT renormalised (§10.2.4)")
        return pooled, by_dir

    core = ga_pooled({d: by_dir[d]["k"] for d in ACTIVE_GUIDANCE},
                     {d: by_dir[d]["n"] for d in ACTIVE_GUIDANCE}, weights)
    pooled.update(core)
    pooled["design_effect"] = (n_nominal / core["n_eff"]) if core["n_eff"] else None
    pooled["p_hat_unweighted_do_not_quote"] = (
        sum(by_dir[d]["k"] for d in ACTIVE_GUIDANCE) / n_nominal)
    return pooled, by_dir


# ------------------------------------------------------- frame-level scan
def scan_frame(drawn_ids):
    """One streaming pass over chunks_v1.parquet (READ-ONLY).

    Returns (per-drawn-row flags DataFrame, frame-level census dict).
    Builds the train-overlap flag and the self-id flag from the §10.1
    definitions rather than inheriting them — EXPANSION_PLAN §3 item 2's
    provenance flag was never populated in the F4 artifacts (design §2.5).
    Paragraph-id joins are FORBIDDEN: E1 ids are 'P-...' and E2's are
    'E2P-...', so such a join returns a structurally meaningless 0%.
    """
    tr = pd.read_parquet(TRAIN, columns=["home_accession_number", "text"])
    train_acc = set(tr.home_accession_number.dropna())
    train_txt = {hashlib.sha1(norm_text(t).encode()).hexdigest() for t in tr.text}

    drawn = set(drawn_ids)
    rows, census = [], Counter()
    sec_tot, sec_sel, sec_ov = Counter(), Counter(), Counter()
    pf = pq.ParquetFile(CHUNKS)
    cols = ["chunk_id", "section_type", "text", "home_company_name",
            "home_accession_number", "source_accession_numbers"]
    for batch in pf.iter_batches(batch_size=25000, columns=cols):
        d = batch.to_pandas()
        d = d[d.section_type != "8K_BODY"]
        if not len(d):
            continue
        low = d.text.str.lower().tolist()
        toks = [company_token(x) for x in d.home_company_name]
        selfid = [bool(t) and (t in l) for t, l in zip(toks, low)]
        home_hit = d.home_accession_number.isin(train_acc).tolist()
        src_hit = [any(a in train_acc for a in (list(x) if x is not None else []))
                   for x in d.source_accession_numbers]
        txt_hit = [hashlib.sha1(norm_text(t).encode()).hexdigest() in train_txt
                   for t in d.text]
        overlap = [h or s or t for h, s, t in zip(home_hit, src_hit, txt_hit)]
        census["n_frame"] += len(d)
        census["selfid"] += sum(selfid)
        census["overlap_home_accession"] += sum(home_hit)
        census["overlap_any_source_accession"] += sum(src_hit)
        census["overlap_normalized_text"] += sum(txt_hit)
        census["overlap_union"] += sum(overlap)
        for st, si, ov in zip(d.section_type, selfid, overlap):
            sec_tot[st] += 1
            sec_sel[st] += si
            sec_ov[st] += ov
        for cid, si, ov in zip(d.chunk_id, selfid, overlap):
            if cid in drawn:
                rows.append((cid, bool(ov), bool(si)))
    flags = pd.DataFrame(rows, columns=["chunk_id", "train_overlap", "selfid"])
    cen = dict(census)
    cen["selfid_share"] = cen["selfid"] / cen["n_frame"]
    cen["overlap_union_share"] = cen["overlap_union"] / cen["n_frame"]
    cen["by_section"] = {s: {"n": sec_tot[s],
                             "selfid_share": sec_sel[s] / sec_tot[s],
                             "overlap_share": sec_ov[s] / sec_tot[s]}
                         for s in sec_tot}
    return flags, cen


def offmatrix_census(lab_frame):
    """§3.4 S-MASK: stored values the rubric declares N/A, by section and value."""
    rf = lab_frame[lab_frame.section_type == "RISK_FACTORS"]
    mda = lab_frame[lab_frame.section_type == "MDA"]
    off_g = pd.concat([mda, rf])
    return {
        "sentiment_on_RISK_FACTORS": {
            "n": int(rf.sentiment.notna().sum()),
            "by_value": {k: int(v) for k, v in rf.sentiment.value_counts().items()}},
        "guidance_on_MDA": {
            "n": int(mda.guidance_direction.notna().sum()),
            "by_value": {k: int(v) for k, v in mda.guidance_direction.value_counts().items()}},
        "guidance_on_RISK_FACTORS": {
            "n": int(rf.guidance_direction.notna().sum()),
            "by_value": {k: int(v) for k, v in rf.guidance_direction.value_counts().items()}},
        "guidance_active_off_matrix": int(off_g.guidance_direction.isin(ACTIVE_GUIDANCE).sum()),
        "f5_blocker": (
            "REQUIRED F5 CHANGE, filed as a G2 finding (design §3.4): features.py "
            "must null sentiment on RISK_FACTORS and guidance_direction on "
            "MDA/RISK_FACTORS BEFORE aggregation, with an assertion that the masked "
            "count matches this census. Sites: features.py:596 sentiment_mean_score, "
            ":602 sentiment_negative_share, :603 guidance_signed_mean, :604 "
            "guidance_any_present (all four aggregate with no section filter), and "
            "the now-false property statement at features.py:1159."),
        "interval": "counts_no_ci",
    }


# ----------------------------------------------------------- probe (S8)
def probe_draw(scored, strata, seed=SEED, n_probe=PROBE_N):
    """Seeded draw of uncontested rows for the owner probe (design §5.5).

    Frame = chunks with >= 1 APPLICABLE gate-bearing field on which the rater
    matched the stored label on EVERY such field. Condition (a) is not
    decoration: RISK_FACTORS has no applicable gate-bearing field, so without
    it ~3-4 probe rows would carry zero gate-bearing information.
    Frame membership uses rater-vs-stored matching only, so it is stable
    across the model-consensus / owner-ratified / escalated stages.
    """
    gate = scored[(scored.field.isin(GATE_FIELDS)) & (scored.applicable)]
    if not len(gate):
        return [], {"eligible_by_arm": {}, "quotas": {}, "realized": {}}
    per_chunk = gate.groupby("chunk_id").agg(arm=("arm", "first"),
                                             n_gate=("field", "size"),
                                             n_contested=("contested", "sum"))
    elig = per_chunk[(per_chunk.n_gate >= 1) & (per_chunk.n_contested == 0)]
    by_arm = {a: sorted(g.index.tolist()) for a, g in elig.groupby("arm")}
    quotas = dict(strata)
    for arm in list(quotas):
        if arm == "P":
            continue
        deficit = quotas[arm] - len(by_arm.get(arm, []))
        if deficit > 0:
            quotas[arm] -= deficit
            quotas["P"] = quotas.get("P", 0) + deficit
    rng = np.random.default_rng(seed)
    picked = []
    for arm in ("P", "G-A", "G-N"):
        pool = by_arm.get(arm, [])
        take = min(quotas.get(arm, 0), len(pool))
        if take:
            idx = rng.choice(len(pool), size=take, replace=False)
            picked += [pool[i] for i in sorted(idx)]
    # §11 (one draw, one n): the quotas must SUM to n_probe. Truncating the
    # realized list would drop rows lexicographically by chunk_id — i.e. by hash
    # prefix — which is a silent selection channel in the one arm whose whole
    # purpose is to be uncurated. Hard-fail on the invariant instead. (Realized
    # picks may still be FEWER than n_probe if a pool is short; that is visible
    # in `realized` and is not a hidden selection.)
    assert sum(quotas.values()) == n_probe, (
        f"probe quotas {quotas} sum to {sum(quotas.values())}, not n_probe={n_probe}; "
        "the draw is never silently truncated (§11)")
    picked = sorted(set(picked))
    realized = Counter(per_chunk.loc[c, "arm"] for c in picked)
    info = {"eligible_by_arm": {a: len(v) for a, v in by_arm.items()},
            "quotas": quotas, "realized": dict(realized),
            "n_eligible": int(len(elig)),
            "n_gate_applicable_chunks": int(len(per_chunk))}
    return picked, info


# ------------------------------------------------------- rater file guard
def check_rater_objects(fname, objs, batch_ids, rate_red_flags):
    """§10.2.1 schema guard. A violation is a FAILED BATCH (§11.3), not a
    finding to interpret at analysis time — so it hard-fails here."""
    keys_ok = ({"chunk_id", "sentiment", "guidance_direction", "red_flags", "reason"}
               if rate_red_flags else
               {"chunk_id", "sentiment", "guidance_direction", "reason"})
    seen = set()
    if not isinstance(objs, list):
        raise AssertionError(f"{fname}: expected a JSON array")
    for o in objs:
        if not isinstance(o, dict):
            raise AssertionError(f"{fname}: non-object element")
        bad = {"verdict", "my_label", "n/a", "distress_tier"} & set(o)
        if bad:
            raise AssertionError(f"{fname}: forbidden key(s) {sorted(bad)} — the rater "
                                 "fell back to the label-auditor schema; FAILED BATCH")
        if set(o) != keys_ok:
            raise AssertionError(f"{fname}: key set {sorted(o)} != {sorted(keys_ok)}")
        cid = o["chunk_id"]
        if cid in seen:
            raise AssertionError(f"{fname}: duplicate chunk_id {cid}")
        seen.add(cid)
        if batch_ids is not None and cid not in batch_ids:
            raise AssertionError(f"{fname}: chunk_id {cid} is not in that batch")
        for f in ("sentiment", "guidance_direction"):
            v = o[f]
            if v is None or (isinstance(v, str) and v.strip().lower() == "n/a"):
                raise AssertionError(f"{fname}: {cid}.{f} is null/'n/a' — the §1.2 "
                                     "applicability leak; FAILED BATCH")
        if o["sentiment"] not in SENTIMENT_VALUES:
            raise AssertionError(f"{fname}: {cid}.sentiment={o['sentiment']!r} not in enum")
        if o["guidance_direction"] not in GUIDANCE_VALUES:
            raise AssertionError(f"{fname}: {cid}.guidance_direction="
                                 f"{o['guidance_direction']!r} not in enum")
        if rate_red_flags:
            rf = o["red_flags"]
            if rf is None or not isinstance(rf, list):
                raise AssertionError(f"{fname}: {cid}.red_flags must be a list")
            for e in rf:
                if not (isinstance(e, (list, tuple)) and len(e) == 2):
                    raise AssertionError(f"{fname}: {cid}.red_flags entry must be "
                                         "[CATEGORY, MODALITY]")
    return sorted(seen)


# ------------------------------------------------------------- main flow
def main(argv=None):
    ap = argparse.ArgumentParser(description="G2 pinned analysis (read-only, $0).")
    ap.add_argument("--selftest", action="store_true",
                    help="run the in-memory estimator checks and exit")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    return analyze()


def analyze():
    missing = []
    if not (G2 / "draw_g2.csv").exists():
        missing.append("data/f4/g2/draw_g2.csv")
    if not (G2 / "draw_manifest.json").exists():
        missing.append("data/f4/g2/draw_manifest.json")
    if not (G2.parent / "g2_draw_arms.csv").exists():
        missing.append("data/f4/g2_draw_arms.csv")
    if missing:
        print("STATUS: not yet available — " + ", ".join(missing))
        print("build_draw_g2.py has not run; there is nothing to analyse and this "
              "script invents nothing. Design §10.3 step 1.")
        return 0

    man = json.loads((G2 / "draw_manifest.json").read_text())
    bars = man.get("ratified_bars") or {}
    unratified = [f for f in GATE_FIELDS if bars.get(f) is None]
    if man.get("parameters_status") != PARAMETERS_STATUS:
        # Same refusal as an unset bar, for the same reason: a draw whose
        # parameters are not owner-ratified cannot produce a gate number.
        print(f"BLOCKED: draw_manifest.json parameters_status="
              f"{man.get('parameters_status')!r}, expected {PARAMETERS_STATUS!r}.")
        print("The draw's parameters are not owner-ratified. No rate and no verdict "
              "are computed. Unblock with an owner ruling recorded in the manifest "
              "(design §10.0, §14.1).")
        return 2
    if unratified:
        # Deliberate refusal, not a crash. Printing p-hat before the bar is
        # ratified lets the bar be chosen after seeing the result, which is
        # bar-shopping — the one degree of freedom this design exists to close
        # (§6, §13-ii, §10.2.7 item 1). Do NOT "fix" this by adding a default
        # bar: §10.0 forbids a default that would let the script run
        # un-ratified. The fix is an owner ruling on §13-ii.
        print("BLOCKED: draw_manifest.json ratified_bars is unset for "
              f"{unratified} (parameters_status="
              f"{man.get('parameters_status')!r}).")
        print("The owner has not ruled design §13-ii. No rate and no verdict are "
              "computed, because publishing p-hat before the bar is ratified would "
              "permit the bar to be chosen after seeing the result. No default bar "
              "exists in this file by design (§10.0).")
        print("Unblock with: an owner ruling on §13-ii written into "
              "draw_manifest.json ratified_bars (one bar per gate-bearing field).")
        return 2

    # ---- §10.0: the ratified parameters are READ from the manifest and asserted
    # against this file's own copy. Bars are ratified, so from here on the guard
    # that matters is not "is there a bar" but "is it still the ruled one".
    param_mismatch = {k: {"manifest": man.get(k), "analyze_g2": v}
                      for k, v in RATIFIED.items() if man.get(k) != v}
    assert not param_mismatch, (
        "draw_manifest.json disagrees with analyze_g2.py's owner-ratified parameter "
        f"block (§10.0, §14.1): {json.dumps(param_mismatch, sort_keys=True)}. A "
        "parameter that changed after the draw is a NEW pre-registration, not a re-run.")
    rate_red_flags = bool(man.get("rate_red_flags", True))
    strata = man.get("probe_strata") or PROBE_STRATA_DEFAULT

    # ---- sha re-check of the frozen inputs (a changed frame is a NEW pre-registration)
    inputs, sha_notes = {}, []
    for p in (LABELS, CHUNKS, TRAIN):
        rel = str(p.relative_to(ROOT))
        h = sha256_file(p)
        inputs[rel] = h
        pinned = (man.get("inputs") or {}).get(rel, {})
        want = pinned.get("sha256") if isinstance(pinned, dict) else pinned
        if want and want != h:
            raise AssertionError(f"{rel}: sha256 {h} != manifest {want}. A changed "
                                 "frame is a new pre-registration, not a re-run.")
        if not want:
            sha_notes.append(f"{rel}: not pinned in draw_manifest.json inputs")

    draw = pd.read_csv(G2 / "draw_g2.csv")
    assert set(draw.columns) == {"rank", "batch", "chunk_id"}, \
        f"draw_g2.csv columns {sorted(draw.columns)} != rank,batch,chunk_id (§5.1/§14.9)"
    # §14.9: arm lives outside the rater-pointed tree because it discloses stored
    # guidance status for the whole G-A and G-N arms. Joined HERE, at analysis.
    arms = pd.read_csv(G2.parent / "g2_draw_arms.csv")
    assert set(arms.columns) == {"chunk_id", "arm"}, \
        f"g2_draw_arms.csv columns {sorted(arms.columns)} != chunk_id,arm (§14.9)"
    draw = draw.merge(arms, on="chunk_id", how="left")
    assert draw.arm.notna().all(), "a drawn chunk has no arm in g2_draw_arms.csv"
    assert set(draw.arm) == {"P", "G-A", "G-N"}, sorted(set(draw.arm))
    drawn_ids = list(draw.chunk_id)

    # ---- batches + rater verdicts
    batch_ids, status = {}, []
    for b in sorted(draw.batch.unique()):
        p = G2 / "batches" / f"{b}.json"
        if not p.exists():
            status.append(f"batches/{b}.json: not yet available")
            batch_ids[b] = None
            continue
        objs = json.loads(p.read_text())
        for o in objs:
            assert set(o) == {"chunk_id", "text"}, \
                f"batches/{b}.json leaks {sorted(set(o) - {'chunk_id', 'text'})}"
        batch_ids[b] = {o["chunk_id"] for o in objs}

    def verdict_file(prefix, b):
        for cand in (f"{prefix}_{b.replace('_', '')}.json", f"{prefix}_{b}.json"):
            if (G2 / "verdicts" / cand).exists():
                return G2 / "verdicts" / cand
        return None

    rater_a, rater_b, rated_batches = {}, {}, []
    for b in sorted(draw.batch.unique()):
        pa = verdict_file("rater_a", b)
        if pa is None:
            status.append(f"verdicts/rater_a_{b.replace('_', '')}.json: not yet available")
            continue
        objs = json.loads(pa.read_text())
        check_rater_objects(pa.name, objs, batch_ids[b], rate_red_flags)
        for o in objs:
            v = {"sentiment": o["sentiment"], "guidance_direction": o["guidance_direction"]}
            if rate_red_flags:
                v[RED] = as_set(o["red_flags"])
            rater_a[o["chunk_id"]] = v
        rated_batches.append(b)
    # The ceiling arm is THREE batches (owner ruling (v)(b), §14.5): rater B's
    # verdicts are POOLED across them, and a missing replicate is reported by
    # name rather than silently shrinking the arm.
    ceiling_batches = list(man.get("ceiling_batches") or [])
    ceiling_rated = []
    for b in ceiling_batches:
        pb = verdict_file("rater_b", b)
        if pb is None:
            status.append(f"verdicts/rater_b_{b.replace('_', '')}.json: not yet available "
                          "(S-NOISE ceiling arm)")
            continue
        ceiling_rated.append(b)
        objs = json.loads(pb.read_text())
        check_rater_objects(pb.name, objs, batch_ids.get(b), rate_red_flags)
        for o in objs:
            v = {"sentiment": o["sentiment"], "guidance_direction": o["guidance_direction"]}
            if rate_red_flags:
                v[RED] = as_set(o["red_flags"])
            rater_b[o["chunk_id"]] = v

    if not rater_a:
        print("STATUS: not yet available — no verdicts/rater_a_batchNN.json exists.")
        for s in status:
            print("  - " + s)
        print("Design §10.3 step 2 (blind rater agents) has not run.")
        return 0
    if len(rater_a) < len(drawn_ids):
        print(f"[WARN] {len(drawn_ids) - len(rater_a)} of {len(drawn_ids)} drawn chunks "
              "are unrated — the analysis runs on what exists and RESTATES n. "
              "Chunks are never replaced (§11.3).")

    # §11.3's failed-batch record. The design pre-commits that a re-run's cause
    # is written down from the enumerated list; §14.9 gives it a file, because
    # draw_manifest.json is written only by build_draw_g2.py and re-running that
    # after the draw is forbidden. Absent file == no batch ever failed.
    failed_batches = load_json("failed_batches.json", None)
    if failed_batches is None:
        failed_batches = []
    for r in failed_batches:
        assert set(r) >= {"batch", "attempt", "cause", "utc"}, \
            f"failed_batches.json row {r} lacks batch/attempt/cause/utc (§11.3)"
        assert r["cause"] in FAILED_BATCH_CAUSES, (
            f"failed_batches.json cause {r['cause']!r} is not one of §11.3's "
            f"enumerated causes {sorted(FAILED_BATCH_CAUSES)} — an unenumerated "
            "cause is the selection channel §11.3 closes by enumeration")

    adj_raw = load_json("adjudications/adjudications.json", None)
    if adj_raw is None:
        status.append("adjudications/adjudications.json: not yet available")
        adj_raw = []
    owner_raw = load_json("owner_rulings.json", None)
    if owner_raw is None:
        status.append("owner_rulings.json: not yet available (model-consensus stage)")
        owner_raw = []
    probe_raw = load_json("probe_rulings.json", None)
    if probe_raw is None:
        status.append("probe_rulings.json: not yet available (S-PROBE)")
        probe_raw = []
    adj = {(r["chunk_id"], r["field"]): r for r in adj_raw}
    owner = {(r["chunk_id"], r["field"]): r for r in owner_raw}
    probe_rulings = {r["chunk_id"]: r for r in probe_raw}
    assert not any(f == RED for _, f in owner), \
        "owner_rulings.json rules a red_flags row — red_flags never escalates (§5.3)"

    # ---- stored labels + provenance, joined HERE and nowhere else
    lab_cols = ["chunk_id", "section_type", "sentiment", "guidance_direction",
                "guidance_imputed_none", "word_count", "passage_was_head_truncated"]
    lab_frame = pd.read_parquet(LABELS, columns=lab_cols)
    lab_frame = lab_frame[lab_frame.section_type != "8K_BODY"]
    lab_drawn = pd.read_parquet(LABELS, columns=lab_cols + [RED])
    lab_drawn = lab_drawn[lab_drawn.chunk_id.isin(set(drawn_ids))]
    ch = pd.read_parquet(CHUNKS, columns=[
        "chunk_id", "section_type", "home_sector", "home_cik", "home_company_name",
        "home_accession_number", "home_filing_date", "word_count", "n_source_filings",
        "in_member_spell", "home_extraction_status", "home_extraction_confidence"])
    ch_drawn = ch[ch.chunk_id.isin(set(drawn_ids))].copy()
    del ch

    section_of = dict(zip(ch_drawn.chunk_id, ch_drawn.section_type))
    stored = {r["chunk_id"]: stored_values(r, rate_red_flags)
              for r in lab_drawn.to_dict("records")}
    assert not any(section_of.get(c) == "8K_BODY" for c in drawn_ids), \
        "8K_BODY row in the draw — excluded by predicate (§2.3)"

    flags, frame_census = scan_frame(drawn_ids)

    prov = (ch_drawn.merge(lab_drawn[["chunk_id", "passage_was_head_truncated",
                                      "guidance_imputed_none"]], on="chunk_id")
                    .merge(flags, on="chunk_id", how="left"))
    prov["era"] = np.where(prov.home_filing_date.astype(str) >= "2019-01-01",
                           "2019+", "pre-2019")

    scored = score(draw, stored, section_of, rater_a, adj, owner, rate_red_flags)
    scored = scored.merge(
        prov[["chunk_id", "home_sector", "home_cik", "era", "in_member_spell",
              "home_extraction_status", "home_extraction_confidence",
              "train_overlap", "selfid", "word_count", "passage_was_head_truncated",
              "guidance_imputed_none", "n_source_filings"]], on="chunk_id", how="left")

    escalated = bool((scored.basis.str.startswith("escalation_")).any())
    stage = "model_consensus"
    if owner or probe_rulings:
        stage = "owner_ratified"
    if escalated:
        stage = "owner_ratified_escalated"

    # ================================================================ estimators
    P = scored[scored.arm == "P"]
    sent = P[(P.field == "sentiment") & (P.applicable)]
    guid = P[(P.field == "guidance_direction") & (P.applicable)]
    ga = scored[(scored.arm == "G-A") & (scored.field == "guidance_direction")
                & (scored.applicable)]
    gn = scored[(scored.arm == "G-N") & (scored.field == "guidance_direction")
                & (scored.applicable)]
    rf_rows = P[(P.field == RED) & (P.applicable)] if rate_red_flags else P.iloc[0:0]

    # §14.9: the §6.3 caveat's counts come from the realized draw, not from the
    # planning approximations the design was drafted with.
    p_ids = set(draw.loc[draw.arm == "P", "chunk_id"])
    p_ex99 = lab_drawn[lab_drawn.chunk_id.isin(p_ids)
                       & (lab_drawn.section_type == "EX99_PRESS_RELEASE")]
    n_p_ex99 = int(len(p_ex99))
    n_p_imputed_none = int(p_ex99.guidance_imputed_none.fillna(False).astype(bool).sum())
    n_p_active = int(p_ex99.guidance_direction.isin(ACTIVE_GUIDANCE).sum())

    primary = {
        "sentiment": primary_block(sent, bars["sentiment"], SENTIMENT_CAVEAT),
        "guidance_direction": primary_block(
            guid, bars["guidance_direction"],
            guidance_base_caveat(n_p_ex99, n_p_imputed_none, n_p_active)),
    }
    for f in GATE_FIELDS:
        primary[f]["n_planned"] = DESIGN_PLANNED_N[f]
        primary[f]["n_planned_note"] = (
            f"§14.6 pinned the boundaries at n={DESIGN_PLANNED_N[f]} before data; "
            "kstar_pass / kstar_fail above are RECOMPUTED at the realized n (§6.1). "
            "A realized n below plan widens the interval — it never moves the bar.")

    # §14.9: this appendix used to reprint p_hat and the Wilson interval "at 0.9".
    # Neither depends on the bar, so those were byte-identical to the ratified
    # bar's numbers — zero information, and a second surface that read like a
    # result at an un-ratified bar. Only k* and the p_hat it implies actually
    # differ with the bar, so only those ship.
    appendix = {}
    for f in GATE_FIELDS:
        sub = sent if f == "sentiment" else guid
        n = rate_block(sub)["n"]
        appendix[f] = {}
        for cand in CANDIDATE_BARS:
            if abs(cand - bars[f]) < 1e-12:
                continue
            kp = kstar_pass(n, cand) if n else None
            kf = kstar_fail(n, cand) if n else None
            appendix[f][f"{cand}"] = {
                "n": n, "k_required_to_clear": kp,
                "p_hat_required_to_clear": (kp / n) if (kp is not None and n) else None,
                "k_at_or_below_which_decisive": kf,
                "note": ("non-decisional; no verdict is defined at this bar. Only "
                         "the k* boundaries move with the bar — p_hat and its "
                         "Wilson interval do not, so they are NOT reprinted here")}

    # ---- G-A: precision of an active call, corpus-re-weighted (§14.4).
    # w_d is RE-DERIVED from the frame here rather than trusted from the manifest;
    # build_draw_g2.py derived it independently from the same prose, and a
    # disagreement is a finding, not a preference.
    ex_frame = lab_frame[lab_frame.section_type == "EX99_PRESS_RELEASE"]
    ga_counts_frame = {d: int((ex_frame.guidance_direction == d).sum())
                       for d in ACTIVE_GUIDANCE}
    assert ga_counts_frame == RATIFIED["ga_corpus_counts"], (
        f"G-A corpus counts re-derived from the frame {ga_counts_frame} != the pinned "
        f"{RATIFIED['ga_corpus_counts']} (§14.3). A changed frame is a new "
        "pre-registration.")
    ga_weights, ga_frame_total = ga_weights_from_counts(ga_counts_frame)
    man_w = man.get("ga_weights") or {}
    assert all(abs(round(ga_weights[d], 6) - man_w.get(d, -1)) < 5e-7
               for d in ACTIVE_GUIDANCE), (
        f"re-derived w_d {[round(ga_weights[d], 6) for d in ACTIVE_GUIDANCE]} != "
        f"draw_manifest ga_weights {man_w} to 6 dp (§14.4)")
    assert set(ga.stored.unique()) <= set(ACTIVE_GUIDANCE), (
        f"G-A arm carries non-active stored values {sorted(set(ga.stored.unique()))} — "
        "the arm frame predicate is EX99 AND guidance_direction in ACTIVE_GUIDANCE (§3.2)")
    ga_complete = (len(rater_a) == len(drawn_ids)
                   and int((ga.basis == "contested_unadjudicated").sum()) == 0)
    ga_block, ga_by_direction = ga_reweighted(ga, ga_weights, ga_complete)
    ga_block["arm_is_complete"] = bool(ga_complete)
    ga_block["corpus_counts"] = ga_counts_frame
    ga_block["corpus_frame_n"] = ga_frame_total
    ga_block["allocation"] = man.get("allocation_ga")
    ga_block["direction_counts_drawn"] = {k: int(v) for k, v in ga.stored.value_counts().items()}

    gn_block = rate_block(gn, count_errors=True)
    gn_block["estimand"] = ("false-NONE rate r = P(adjudicated reference is an active "
                            "direction | stored is an imputed NONE); an active call is "
                            "missed on 0.511 * r of guidance-applicable rows")
    gn_ev = gn[gn.err.notna()]
    gn_block["reference_active_counts"] = {
        str(k): int(v) for k, v in
        gn_ev[gn_ev.err == 1].ref.value_counts(dropna=False).items()}
    gn_block["calibration_anchors"] = {
        "e2_active_share_when_key_emitted": 6479 / 46252,
        "e1_same_adapter_omission_rate": E1_STUDENT_OMISSION,
        "e2_omission_rate_frame": E2_STUDENT_OMISSION_FRAME,
        "note": ("holding the labeler fixed, guidance-key omission worsens 33.08% (E1) "
                 "-> 51.18% (E2), +18.1 pts — a behavioural/corpus response, which is "
                 "the hypothesis G-N exists to test (§3.3)")}

    # ---------------- secondaries
    sec = {}
    gate_P = P[(P.field.isin(GATE_FIELDS)) & (P.applicable)]

    def per_field(by):
        return {f: subgroup(gate_P[gate_P.field == f], by) for f in GATE_FIELDS}

    sec["S-SEC"] = per_field("section_type")
    sec["S-SECTOR"] = per_field("home_sector")
    sec["S-ERA"] = per_field("era")
    sec["S-CONF"] = {
        "by_extraction_confidence": per_field("home_extraction_confidence"),
        "by_extraction_status": per_field("home_extraction_status"),
        "by_in_member_spell": per_field("in_member_spell"),
        "note": ("in_member_spell is NOT point-in-time (chunks_v1 caveat) — reported as "
                 "a free subgroup, never used to condition (§3.5)")}
    sec["S-OVERLAP"] = {
        **per_field("train_overlap"),
        "powered": False,
        "note": ("discharges EXPANSION_PLAN §3 item 2 ('with and without the overlap "
                 "set'). NOT POWERED AT ANY n THIS PROJECT WILL BUY: ~14 overlap rows of "
                 "300 carry a +-18.2 pt Wilson half-width at p_hat=0.85, and no "
                 "overlap-vs-novel difference of any plausible size is detectable. The "
                 "4.53% accession-level figure is a LOWER BOUND on memorization "
                 "exposure — company-level exposure is 15.85% and boilerplate recurs "
                 "near-verbatim (§2.5). The headline therefore pools memorized and "
                 "novel chunks.")}
    sec["S-SELFID"] = {**per_field("selfid"),
                       "frame_share": frame_census["selfid_share"],
                       "realized_share": float(prov.selfid.mean()) if len(prov) else None,
                       "note": ("discharges HANDOFF §7's 'watch for it in the spot-check' "
                                "instruction; the passage text itself names the company "
                                "on 46.46% of the frame (EX99 71.14%)")}
    sec["S-OMIT"] = _s_omit(sent, guid, gate_P)
    sec["S-ERR"] = _s_err(sent, guid, rf_rows, rate_red_flags)
    sec["S-GNDEC"] = _s_gndec(P, gn, lab_frame)
    sec["S-MASK"] = offmatrix_census(lab_frame)
    sec["S-NOISE"] = _s_noise(rater_a, rater_b, section_of, bars, rate_red_flags,
                              ceiling_batches, ceiling_rated,
                              dict(zip(draw.chunk_id, draw.batch)),
                              ceiling_realized_n(draw, section_of, ceiling_batches))
    if rate_red_flags:
        sec["S-RF1"], sec["S-RF2"] = _s_redflags(rf_rows)
    else:
        sec["S-RF1"] = {"not_rated": True, "note": "Option B-lite: red_flags not rated"}
        sec["S-RF2"] = {"not_rated": True, "interval": "chunk_clustered_bootstrap",
                        "note": "Option B-lite: red_flags not rated"}

    # ---------------- S-PROBE (written even before the owner rules)
    probe_ids, probe_info = probe_draw(scored, strata)
    n_gate_chunks = probe_info.get("n_gate_applicable_chunks", 0)
    unc_share = (probe_info["n_eligible"] / n_gate_chunks) if n_gate_chunks else None
    ruled = [c for c in probe_ids if c in probe_rulings]
    overturned = sum(1 for c in ruled if probe_rulings[c]["ruling"] == "disagree")
    probe_lo, probe_hi = wilson(overturned, len(ruled)) if ruled else (None, None)
    sec["S-PROBE"] = {
        "n_probe": len(probe_ids), "n_ruled": len(ruled), "overturned": overturned,
        "wilson_95_on_hidden_shared_error": [probe_lo, probe_hi],
        "interval": "naive_binomial",
        "uncontested_share_of_gate_applicable_chunks": unc_share,
        "max_hidden_error_share_of_gate_rows":
            (probe_hi * unc_share) if (probe_hi is not None and unc_share) else None,
        "escalation_triggered": (bool(overturned >= PROBE_ESCALATION_K) if ruled else None),
        "escalation_applied_in_this_run": escalated,
        "escalation_rule": (f"if >= {PROBE_ESCALATION_K} of {PROBE_N} uncontested rows are "
                            "overturned, every uncontested row WITH an applicable "
                            "gate-bearing field goes to the adjudicator ONCE on those "
                            "fields and the primaries are recomputed. Fires at most once. "
                            "No re-draw, no n increase (§5.5, §11.2)."),
        "probe_rulings_do_not_enter_the_primary": True,
        "note": ("the only non-model check in the design; it bounds the hidden shared "
                 "error the one-directional protocol cannot see (only disagreements are "
                 "ever checked, so the pipeline can lower the error estimate but never "
                 "raise it)"),
        **probe_info}
    (G2 / "probe_ids.json").write_text(json.dumps(
        {"seed": SEED, "n": len(probe_ids), "stratification": strata,
         "realized_stratification": probe_info["realized"],
         "frame_size": probe_info["n_eligible"],
         "frame_predicate": ("rows with >=1 APPLICABLE gate-bearing field on which the "
                             "rater matched the stored label on EVERY such field"),
         "chunk_ids": probe_ids}, indent=1))

    # ---- pin the layers that PRODUCE k, not just the frame.
    # results_g2.json.inputs used to hash only the three parquets. Every "disagree"
    # behind every error in every primary comes from the adjudication layer, and
    # the S-NOISE ceiling comes from the rater-B layer; neither was hashed
    # anywhere in this file. Hash them here so the adjudication and ceiling
    # layers are tamper-evident from results_g2.json. NOT hashed here (recorded
    # instead in G2_FINAL_REPORT.md §2 for the owner-ratified stage, 2026-09-07):
    # verdicts/rater_a_batch*.json, owner_rulings.json, probe_rulings.json; the
    # draw CSVs are covered transitively via draw_manifest.json's `outputs`.
    # results_g2.json is still not RECOMPUTABLE from itself — see A13.
    for _p in [G2 / "adjudications" / "adjudications.json",
               G2 / "draw_manifest.json",
               G2 / "probe_ids.json",
               *sorted((G2 / "verdicts").glob("rater_b_batch*.json"))]:
        if _p.exists():
            inputs[str(_p.relative_to(ROOT))] = sha256_file(_p)

    # ---- the reference-producing layer, described (counts only; no bar, no CI,
    # moves nothing). How often the adjudicator sided with the blind rater
    # against the stored label bears directly on whether the third rater is an
    # independent arbiter or a second confirmation of the first — which is the
    # load-bearing premise of the model-consensus reference (§12.1).
    _av = Counter(r.get("verdict") for r in adj_raw)
    adjudication_layer = {
        "interval": "counts_no_ci",
        "n_rulings": len(adj_raw),
        "by_verdict": {k: int(v) for k, v in sorted(_av.items())},
        "by_confidence": {k: int(v) for k, v in
                          sorted(Counter(r.get("confidence") for r in adj_raw).items())},
        "n_unsure": int(_av.get("unsure", 0)),
        "sided_with_rater_against_stored": {
            "overall": {"k": int(_av.get("disagree", 0)), "n": len(adj_raw),
                        "p_hat": (_av.get("disagree", 0) / len(adj_raw))
                                 if adj_raw else None},
            "by_field": {}},
        "note": ("'sided_with_rater_against_stored' = the adjudicator overturned the "
                 "stored student label on a contested (chunk, field) row. Both the "
                 "blind rater and the adjudicator are Claude-family; the student is "
                 "Qwen. A high rate is consistent with either a correct student-error "
                 "finding or with within-family agreement, and this design cannot "
                 "separate the two (§12.1). Disclosure only — it moves nothing."),
    }
    for _f in sorted({r.get("field") for r in adj_raw}):
        _rows = [r for r in adj_raw if r.get("field") == _f]
        _k = sum(1 for r in _rows if r.get("verdict") == "disagree")
        adjudication_layer["sided_with_rater_against_stored"]["by_field"][_f] = {
            "k": _k, "n": len(_rows), "p_hat": (_k / len(_rows)) if _rows else None}

    # ---------------- census / comparison / constants
    frame_checks = _frame_checks(lab_frame, frame_census, man)
    comparisons = []
    for c in COMPARISONS:
        g2v = None
        if c["g2_key"] in primary:
            g2v = {"p_hat": primary[c["g2_key"]]["p_hat"], "n": primary[c["g2_key"]]["n"],
                   "scale": "agreement"}
        elif c["g2_key"] == "red_flags" and rate_red_flags:
            g2v = {"p_hat": sec["S-RF1"].get("p_hat"), "n": sec["S-RF1"].get("n"),
                   "scale": "error"}
        comparisons.append({"name": c["name"], "g2_value": g2v,
                            "other_value": c["other_value"],
                            "caveat": COMPARISON_CAVEAT, "interpretable": False})

    red_caveat = _red_flag_caveat(sec["S-RF1"], sec["S-RF2"], rate_red_flags)
    constants = _constants(primary, ga_block, gn_block, sec, frame_census, red_caveat)

    results = {
        "schema_version": "g2-1",
        "generated_utc": now_utc(),
        "stage": stage,
        "provenance": PROVENANCE,
        "red_flags_status": RED_FLAGS_STATUS,
        "inputs": inputs,
        "input_notes": sha_notes,
        "option": man.get("option"),
        "seed": SEED,
        "ratified_bars": bars,
        "n_drawn": len(draw), "n_rated": len(rater_a),
        "not_yet_available": status,
        "primary": primary,
        "appendix_non_decisional_bars": appendix,
        # §10.2.6 pins these at the top level; guidance_false_none_rate rides
        # beside them because §6.3's caveat binds all three together.
        "guidance_active_precision": ga_block,
        "guidance_active_precision_by_direction": ga_by_direction,
        "guidance_false_none_rate": gn_block,
        # Descriptive; not a pre-registered secondary and not gate-bearing.
        "adjudication_layer": adjudication_layer,
        "secondaries": sec,
        "frame_checks": frame_checks,
        "comparison_rows": comparisons,
        "constants": constants,
        "non_fail_wording": {f: _non_fail_wording(f, primary[f], ga_block, gn_block)
                             for f in GATE_FIELDS},
        # §11.3 as amended by §14.9: the enumerated cause of every re-run batch,
        # auditable rather than recorded nowhere.
        "failed_batches": failed_batches,
        "api_calls": 0, "gpu_seconds": 0, "network_calls": 0,
    }

    report = _report(results, man)
    passed = _assertions(results, report, scored, bars, man, rate_red_flags)
    results["assertions_passed"] = passed

    (G2 / "results_g2.json").write_text(json.dumps(results, indent=1, default=float))
    (G2 / "report_g2.md").write_text(report)
    prov_cols = ["rank", "batch", "arm", "chunk_id", "section_type", "home_sector",
                 "home_cik", "home_company_name", "home_filing_date", "word_count",
                 "n_source_filings", "in_member_spell", "home_extraction_status",
                 "home_extraction_confidence", "passage_was_head_truncated",
                 "train_overlap", "selfid"]
    (draw.merge(prov, on="chunk_id", how="left", suffixes=("", "_p"))
         .reindex(columns=prov_cols)
         .sort_values("rank")
         .to_csv(G2 / "draw_g2_provenance.csv", index=False))

    print(report)
    print(f"\nwrote {G2/'results_g2.json'}, {G2/'report_g2.md'}, "
          f"{G2/'probe_ids.json'}, {G2/'draw_g2_provenance.csv'}")
    return 0


# --------------------------------------------------------- secondary bits
def _s_omit(sent, guid, gate_P):
    """Every rate restated with omissions EXCLUDED, plus the omission rate itself.

    Missing-as-error (primary) and missing-as-excluded answer different
    questions — value correctness vs coverage. Both ship; neither is chosen
    after seeing which is kinder (§1.3).
    """
    out = {}
    for f, sub in (("sentiment", sent), ("guidance_direction", guid)):
        keep = sub[~sub.omission]
        b = rate_block(keep)
        n_appl = len(sub)
        n_om = int(sub.omission.sum())
        # guidance coverage also counts the writer-rule imputed NONEs
        has_imp = (f != "sentiment") and ("guidance_imputed_none" in sub.columns)
        n_imputed = int(sub["guidance_imputed_none"].fillna(False).sum()) if has_imp else 0
        out[f] = {"omission_excluded_rate": b,
                  "n_applicable": n_appl,
                  "omission_rate": {"k": n_om, "n": n_appl,
                                    "p_hat": (n_om / n_appl) if n_appl else None,
                                    "wilson_95": list(wilson(n_om, n_appl)) if n_appl else None,
                                    "interval": "naive_binomial"},
                  "n_writer_imputed_none": n_imputed}
    out["note"] = ("'omission' = the student did not emit a value (stored null). The "
                   "guidance_imputed_none rows are NOT omissions here — the writer rule "
                   "is adopted and 'NONE' IS the stored label (§1.3); their count is "
                   "reported separately and arm G-N tests them directly.")
    out["interval"] = "naive_binomial"
    return out


def _s_err(sent, guid, rf_rows, rate_red_flags):
    """Error-mode decomposition — descriptive counts, no CI."""
    out = {"interval": "counts_no_ci"}
    ev = sent[sent.err.notna() & sent.ref.notna()]
    conf = Counter((str(r.stored), str(r.ref)) for r in ev.itertuples())
    neg_ref = sum(v for (s, r), v in conf.items() if r == "NEGATIVE")
    neg_hit = conf.get(("NEGATIVE", "NEGATIVE"), 0)
    out["sentiment"] = {
        "confusion_stored_x_reference": {f"{s}->{r}": v for (s, r), v in sorted(conf.items())},
        # NOT "recall". Named for what it is. The one-directional protocol only
        # ever re-checks DISAGREEMENTS, so the reference-NEGATIVE set is built
        # from contested rows only: a stored-NEUTRAL row that is truly NEGATIVE
        # is visible here only if the blind rater called it NEGATIVE and the
        # adjudicator then sided with the rater. This denominator is therefore
        # definitionally close to the stored-NEGATIVE-and-upheld set, and a value
        # at or near 1.0 is near-structural. No cross-protocol number is placed
        # beside it — §7 puts those in comparison_rows tagged interpretable:false.
        "share_of_reference_NEGATIVE_rows_whose_stored_value_was_NEGATIVE": {
            "k": neg_hit, "n": neg_ref,
            "p_hat": (neg_hit / neg_ref) if neg_ref else None,
            "wilson_95": list(wilson(neg_hit, neg_ref)) if neg_ref else None,
            "interval": "naive_binomial",
            "note": ("NOT recall against an independent NEGATIVE ground truth. "
                     "One-directional verification: only disagreements are ever "
                     "re-checked, so the reference-NEGATIVE set is built from "
                     "contested rows and this denominator is definitionally near "
                     "the stored-NEGATIVE-and-upheld set — a value at or near 1.0 "
                     "is near-structural, not a measurement of NEGATIVE detection.")},
        "n_omitted": int(sent.omission.sum())}
    gev = guid[guid.err.notna() & guid.ref.notna()]
    modes = Counter()
    for r in gev.itertuples():
        s, ref = str(r.stored), str(r.ref)
        if s == ref:
            continue
        if s in ACTIVE_GUIDANCE and ref == "NONE":
            modes["active_to_NONE"] += 1
        elif s == "NONE" and ref in ACTIVE_GUIDANCE:
            modes["NONE_to_active"] += 1
        elif s in ACTIVE_GUIDANCE and ref in ACTIVE_GUIDANCE:
            modes["wrong_active"] += 1
        else:
            modes["other"] += 1
    out["guidance_direction"] = {**{k: int(v) for k, v in modes.items()},
                                 "omitted": int(guid.omission.sum())}
    if rate_red_flags:
        spurious = missed = modality = 0
        for r in rf_rows[rf_rows.err.notna() & rf_rows.ref.notna()].itertuples():
            if r.err != 1:
                continue
            sc = {c for c, _ in r.stored}
            rc = {c for c, _ in r.ref}
            spurious += len(sc - rc)
            missed += len(rc - sc)
            modality += sum(1 for c in sc & rc
                            if {m for cc, m in r.stored if cc == c}
                            != {m for cc, m in r.ref if cc == c})
        out[RED] = {"spurious_flags": spurious, "missed_flags": missed,
                    "wrong_modality": modality,
                    "note": "category-level corrections on error rows; disclosure-only"}
    return out


def _s_gndec(P, gn, lab_frame):
    """G-N omission decomposition, and the P-arm omission rate by word-count
    quartile / head-truncation. Quartile cuts are fixed by the FRAME's
    guidance-applicable rows, not by the sample."""
    ex = lab_frame[lab_frame.section_type == "EX99_PRESS_RELEASE"]
    cuts = [float(x) for x in ex.word_count.quantile([0.25, 0.5, 0.75]).tolist()]
    edges = [-np.inf] + cuts + [np.inf]
    labels = [f"Q1(<= {cuts[0]:.0f})", f"Q2(<= {cuts[1]:.0f})",
              f"Q3(<= {cuts[2]:.0f})", f"Q4(> {cuts[2]:.0f})"]

    pg = P[(P.field == "guidance_direction") & (P.applicable)].copy()
    out = {"frame_word_count_quartile_cuts": cuts,
           "interval": "naive_binomial",
           "e1_same_adapter_baseline": E1_STUDENT_OMISSION,
           "e2_frame_omission_rate": E2_STUDENT_OMISSION_FRAME,
           "note": ("'omission' here = the guidance key was not emitted "
                    "(guidance_imputed_none OR stored null). The P arm is the only "
                    "base-rate-representative arm, so the omission rate is computed "
                    "there; the false-NONE split is computed inside G-N.")}
    if len(pg):
        pg["om"] = (pg.guidance_imputed_none.fillna(False)) | (pg.omission)
        pg["wq"] = pd.cut(pg.word_count, bins=edges, labels=labels)
        out["p_arm_omission_rate"] = {"k": int(pg.om.sum()), "n": int(len(pg)),
                                      "p_hat": float(pg.om.mean()),
                                      "wilson_95": list(wilson(int(pg.om.sum()), len(pg))),
                                      "interval": "naive_binomial"}
        out["p_arm_omission_by_word_count_quartile"] = {
            str(q): {"k": int(g.om.sum()), "n": int(len(g)),
                     "p_hat": float(g.om.mean()) if len(g) else None,
                     "wilson_95": list(wilson(int(g.om.sum()), len(g))) if len(g) else None,
                     "interval": "naive_binomial"}
            for q, g in pg.groupby("wq", observed=False)}
        out["p_arm_omission_by_head_truncated"] = {
            str(t): {"k": int(g.om.sum()), "n": int(len(g)),
                     "p_hat": float(g.om.mean()) if len(g) else None,
                     "interval": "naive_binomial"}
            for t, g in pg.groupby(pg.passage_was_head_truncated.astype(str))}
    if len(gn):
        g = gn.copy()
        g["wq"] = pd.cut(g.word_count, bins=edges, labels=labels)
        out["gn_false_none_by_word_count_quartile"] = {
            str(q): rate_block(sub, count_errors=True)
            for q, sub in g.groupby("wq", observed=False)}
        out["gn_false_none_by_head_truncated"] = {
            str(t): rate_block(sub, count_errors=True)
            for t, sub in g.groupby(g.passage_was_head_truncated.astype(str))}
    return out


def ceiling_realized_n(draw, section_of, ceiling_batches):
    """Applicability-masked ceiling-arm size PER FIELD, from the draw alone.

    Deterministic once the draw exists — it does not wait for rater B. §14.9
    replaced §14.5's "~107 / ~62" expectations with this because a projection
    shipped where a measurement exists is the same defect the design names
    elsewhere.
    """
    ids = [c for c in draw.loc[draw.batch.isin(list(ceiling_batches)), "chunk_id"]]
    return {f: sum(1 for c in ids if section_of.get(c) in APPLICABLE[f])
            for f in GATE_FIELDS}


def _s_noise(rater_a, rater_b, section_of, bars, rate_red_flags,
             ceiling_batches, ceiling_rated, batch_of, realized_n):
    """The CEILING: rater-A vs rater-B, POOLED over the three replicate batches
    the owner bought on 2026-09-07 (ruling (v)(b), §14.5) — n = 120 ROWS.

    Reported beside every bar; it CANNOT move any bar or any decision — that
    would be a noise-normalised criterion chosen after the ceiling is known,
    which §5.4 forbids. If the ceiling's upper bound falls below the bar, §6.4
    fact 3 says a DECISIVE FAIL is a statement about the instrument; the flag
    is computed here and the ruling is the owner's.

    120 re-rated ROWS are not 120 evaluable rows PER FIELD: S-NOISE is
    applicability-masked like every other estimate (§10.2.4). §14.5 planned
    ~107 / ~62; the REALIZED draw gives 110 sentiment-evaluable and 65
    guidance-evaluable, computed here by ceiling_realized_n() rather than
    quoted (§14.9). Both are the correction to the '+-6.4 pts' figure the
    ruling was made against. The p_hat a ceiling would need to clear the bar at
    the realized n is printed beside them so nobody has to re-derive it after
    the fact. Computing S-NOISE unmasked on all 120 rows is NOT an option: it
    would mix in RISK_FACTORS sentiment and MDA guidance, fields the rubric
    never poses, and would be an estimator chosen to flatter a number.

    The three replicates are byte-identical to their originals INCLUDING row
    order, so raters A and B see the same passages in the same sequence. Any
    ordering or context effect is therefore shared, which inflates A-vs-B
    agreement: this ceiling is an UPPER-biased estimate of two-rater agreement
    and the true ceiling is at most this (§14.9; magnitude unmeasured).
    """
    both = sorted(set(rater_a) & set(rater_b))
    pooled_from = sorted({batch_of.get(c) for c in both if batch_of.get(c)})
    base = {"ceiling_batches": list(ceiling_batches),
            "ceiling_batches_rated": list(ceiling_rated),
            "ceiling_batches_missing": [b for b in ceiling_batches
                                        if b not in ceiling_rated],
            "pooled_from_batches": pooled_from,
            "planned_evaluable_rows": dict(CEILING_PLANNED_N),
            "planned_evaluable_rows_note": ("§14.5 PLANNING values, kept only so "
                                            "planned-vs-realized drift is visible"),
            "realized_evaluable_rows": dict(realized_n),
            "replicate_row_order": (
                "byte-identical to the originals INCLUDING row order, so raters A "
                "and B share any ordering/context effect; this ceiling is "
                "UPPER-biased and the true two-rater ceiling is at most this "
                "(§14.9, magnitude unmeasured)"),
            "cannot_move_any_bar": True,
            "interval": "naive_binomial"}
    ns, ng = realized_n["sentiment"], realized_n["guidance_direction"]
    sl, sh = wilson_p(0.90, ns)
    gl, gh = wilson_p(0.90, ng)
    if not both:
        return {**base, "n": 0, "n_chunks": 0, "not_yet_available": True,
                "note": "no rater_b verdict file yet (S-NOISE ceiling arm)"}
    out = {**base, "n_chunks": len(both),
           "note": ("no student-vs-rater agreement can exceed two-rater agreement; "
                    "the only prior measurement is v1.2 S7, red_flags, n=40: 0.90 "
                    "[0.7695, 0.9604] — an interval that straddles both candidate bars. "
                    f"At the REALIZED masked n ({ns} / {ng}) a ceiling of p_hat=0.90 "
                    f"gives [{sl:.4f}, {sh:.4f}] and [{gl:.4f}, {gh:.4f}]: NEITHER "
                    "lower bound clears the ratified 0.85 bar, so §6.4 fact 3 is "
                    "narrowed, not closed, for BOTH gate-bearing fields (§14.5).")}
    fields = list(GATE_FIELDS) + ([RED] if rate_red_flags else [])
    for f in fields:
        ids = [c for c in both if section_of.get(c) in APPLICABLE[f]]
        k = sum(1 for c in ids if rater_a[c].get(f) == rater_b[c].get(f))
        lo, hi = wilson(k, len(ids)) if ids else (None, None)
        blk = {"k": k, "n": len(ids), "p_hat": (k / len(ids)) if ids else None,
               "n_rows_pooled": len(both), "n_masked_out": len(both) - len(ids),
               "wilson_95": [lo, hi], "interval": "naive_binomial"}
        if f in CEILING_PLANNED_N:
            blk["n_planned"] = CEILING_PLANNED_N[f]
            blk["n_realized_from_draw"] = realized_n[f]
        if f in bars and hi is not None:
            b = bars[f]
            kp = kstar_pass(len(ids), b) if ids else None
            blk["bar"] = b
            blk["ceiling_upper_bound_below_bar"] = bool(hi < b)
            blk["ceiling_lower_bound_clears_bar"] = bool(lo >= b)
            blk["p_hat_required_to_clear_bar"] = (kp / len(ids)) if kp is not None else None
            blk["k_required_to_clear_bar"] = kp
            blk["p_hat_required_note"] = (
                "the DISCRETE k/n threshold from the §10.0 kstar_pass primitive at the "
                "REALIZED n; the continuous roots at the realized ceiling n "
                f"({ns} / {ng}) are 0.9167 / 0.9368 and are necessarily a shade lower "
                "(§14.5 as amended by §14.9)")
            blk["ceiling_flag_note"] = (
                "if ceiling_upper_bound_below_bar is true, §6.4 fact 3 fires: a DECISIVE "
                "FAIL at this bar is a statement about the instrument, not about the "
                "student, and the §6.5 consequence ladder should not be executed on it. "
                "If ceiling_lower_bound_clears_bar is true the attribution question is "
                "closed. In between — the likeliest region — the ceiling is reported, a "
                "FAIL's attribution is stated as UNRESOLVED, and no bar moves: no "
                "noise-normalised criterion was adopted and none may be adopted now "
                "(§5.4, §14.5). The ruling is the owner's.")
        out[f] = blk
    return out


def _s_redflags(rf_rows):
    """S-RF1 exact-set error + S-RF2 per-category-decision error (clustered).

    DISCLOSURE-ONLY. No kill rule, no gate branch. A favourable result is
    disclosure, NOT evidence for re-promotion (§1.1).
    """
    s1 = rate_block(rf_rows, count_errors=True)
    s1["scale"] = "error"
    s1["construction"] = "v1.2 P1 construction: exact (category, modality) set mismatch"
    s1["status"] = RED_FLAGS_STATUS
    ev = rf_rows[rf_rows.err.notna() & rf_rows.ref.notna()]
    per_chunk = []
    for r in ev.itertuples():
        per_chunk.append(sum(1 for c in CATS
                             if {m for cc, m in r.stored if cc == c}
                             != {m for cc, m in r.ref if cc == c}))
    per_chunk = np.array(per_chunk, dtype=float)
    n_dec = int(per_chunk.size * len(CATS))
    k_dec = int(per_chunk.sum())
    s2 = {"k": k_dec, "n_decisions": n_dec, "n_chunks": int(per_chunk.size),
          "p_hat": (k_dec / n_dec) if n_dec else None,
          "cluster_bootstrap_95": cluster_bootstrap(per_chunk, len(CATS)),
          "interval": "chunk_clustered_bootstrap",
          "bootstrap": {"resamples": BOOT, "seed": SEED, "method": "percentile 2.5/97.5"},
          "naive_binomial_95_ANTICONSERVATIVE": list(wilson(k_dec, n_dec)) if n_dec else None,
          "note": ("the 6 category decisions inside a chunk are not independent; the "
                   "chunk-clustered bootstrap is the honest interval. v1.1's published "
                   "7.5% [91.4, 93.5] was the naive one — that error is not repeated."),
          "status": RED_FLAGS_STATUS}
    return s1, s2


def _red_flag_caveat(s1, s2, rate_red_flags):
    """The rewritten RED_FLAG_CAVEAT (features.py:298-304). MUST contain
    red_flags_status verbatim (§10.2.7 item 9)."""
    if not rate_red_flags:
        body = ("E2 student red-flag error is UNMEASURED (Option B-lite dropped the "
                "red-flag rating arm).")
    elif s1.get("n"):
        lo, hi = s1["wilson_lo"], s1["wilson_hi"]
        body = (f"Measured E2 student exact-set (category+modality) error on a "
                f"base-rate-representative G2 draw: {s1['k']}/{s1['n']} = "
                f"{s1['p_hat']:.1%} [95% Wilson {lo:.1%}, {hi:.1%}], model-consensus "
                f"reference, no owner ratification. The E1 constants 36.6%/63.4% were "
                f"measured on Claude BOOTSTRAP labels and do not describe these labels.")
    else:
        body = "E2 student red-flag error is not yet computed (no evaluable rows)."
    return (f"E2 red-flag labels are {RED_FLAGS_STATUS} {body} This number is "
            "disclosure, not evidence for re-promotion; only the owner can revisit the "
            "2026-08-27 demotion.")


def _constants(primary, ga_block, gn_block, sec, frame_census, red_caveat):
    """The §8 constant block — consumed from results_g2.json, never retyped.
    NO lambda: G2 produces chunk-level label accuracy; EXPANSION_PLAN §2a's
    lambda is a filing-level feature reliability (§6.5 withdrawal)."""
    def c(name, blk, prov_note):
        return {name: {"point": blk.get("p_hat"), "ci_lo": blk.get("wilson_lo"),
                       "ci_hi": blk.get("wilson_hi"), "n": blk.get("n"),
                       "provenance": prov_note}}
    prov_line = PROVENANCE
    out = {}
    out.update(c("sentiment_agreement", primary["sentiment"], prov_line))
    out.update(c("guidance_agreement_base_rate", primary["guidance_direction"],
                 prov_line + " QUOTE ONLY WITH guidance_active_precision AND "
                             "guidance_false_none_rate (§6.3)."))
    # The G-A constant is the POOLED, corpus-re-weighted number (§14.4). Its n is
    # the nominal arm n; n_eff is what the interval was built on and travels with
    # it, because quoting a quota arm's nominal n as if it were an effective n is
    # exactly the overstatement the re-weighting exists to prevent.
    out["guidance_active_precision"] = {
        "point": ga_block.get("point"), "ci_lo": ga_block.get("wilson_lo"),
        "ci_hi": ga_block.get("wilson_hi"), "n": ga_block.get("n_nominal"),
        "n_eff": ga_block.get("n_eff"),
        "provenance": (prov_line + " POOLED over the four active directions and "
                       "re-weighted to corpus shares w_d = N_d/6479 (quota arm, "
                       "§14.4); the interval is the §10.0 Wilson formula on n_eff, "
                       "which is reported beside it ALWAYS. Per-direction precision "
                       "is a DISCLOSURE with no bar.")}
    out.update(c("guidance_false_none_rate", gn_block, prov_line))
    out.update(c("redflag_exact_set_error", sec["S-RF1"],
                 prov_line + " DISCLOSURE-ONLY; " + RED_FLAGS_STATUS))
    out["redflag_per_category_error_clustered"] = {
        "point": sec["S-RF2"].get("p_hat"),
        "ci_lo": (sec["S-RF2"].get("cluster_bootstrap_95") or [None, None])[0],
        "ci_hi": (sec["S-RF2"].get("cluster_bootstrap_95") or [None, None])[1],
        "n": sec["S-RF2"].get("n_decisions"),
        "provenance": prov_line + " chunk-clustered bootstrap; DISCLOSURE-ONLY."}
    om = sec["S-OMIT"]
    for f, key in (("sentiment", "sentiment_omission_rate"),
                   ("guidance_direction", "guidance_omission_rate")):
        blk = om[f]["omission_rate"]
        out[key] = {"point": blk["p_hat"], "ci_lo": (blk["wilson_95"] or [None, None])[0],
                    "ci_hi": (blk["wilson_95"] or [None, None])[1], "n": blk["n"],
                    "provenance": "stored-label coverage on applicable drawn rows (§1.3)"}
    out["offmatrix_emission_census"] = {
        "point": None, "ci_lo": None, "ci_hi": None,
        "n": sec["S-MASK"]["sentiment_on_RISK_FACTORS"]["n"],
        "provenance": "re-derived from labels_e2_v1.parquet over the frame (§3.4)"}
    noise = sec["S-NOISE"]
    out["rater_noise_ceiling"] = {
        "point": (noise.get("sentiment") or {}).get("p_hat"),
        "ci_lo": ((noise.get("sentiment") or {}).get("wilson_95") or [None, None])[0],
        "ci_hi": ((noise.get("sentiment") or {}).get("wilson_95") or [None, None])[1],
        "n": (noise.get("sentiment") or {}).get("n"),
        "provenance": ("rater A vs rater B, sentiment, POOLED over the three replicate "
                       "batches (owner ruling 2026-09-07 (v)(b); 120 rows, masked to "
                       "the sentiment-applicable subset — realized "
                       f"{(noise.get('realized_evaluable_rows') or {}).get('sentiment')}"
                       ", §14.5 planned 107); replicates are identically ordered so "
                       "this ceiling is upper-biased (§14.9); cannot move a bar "
                       "(§5.4, §14.5)")}
    out["train_overlap_census"] = {
        "point": frame_census["overlap_union_share"], "ci_lo": None, "ci_hi": None,
        "n": frame_census["n_frame"],
        "provenance": ("home/source accession OR normalized-text overlap against "
                       "finetune/splits_v12/train.parquet, re-derived here; a LOWER "
                       "BOUND on memorization exposure (§2.5)")}
    out["selfid_census"] = {
        "point": frame_census["selfid_share"], "ci_lo": None, "ci_hi": None,
        "n": frame_census["n_frame"],
        "provenance": "first distinctive company token present in the chunk text (§5.1)"}
    out["red_flags_status"] = {"point": None, "ci_lo": None, "ci_hi": None, "n": None,
                               "provenance": RED_FLAGS_STATUS}
    out["RED_FLAG_CAVEAT_rewritten"] = {"point": None, "ci_lo": None, "ci_hi": None,
                                        "n": None, "provenance": red_caveat}
    return out


def _frame_checks(lab_frame, frame_census, man):
    """Re-derive the design's pinned frame facts. A mismatch is REPORTED (the
    hard assertions on these live in build_draw_g2.py §10.1.2)."""
    sc = lab_frame.section_type.value_counts().to_dict()
    ex = lab_frame[lab_frame.section_type == "EX99_PRESS_RELEASE"]
    obs = {"n_frame": int(len(lab_frame)),
           "section_counts": {k: int(v) for k, v in sc.items()},
           "ga_frame": int(ex.guidance_direction.isin(ACTIVE_GUIDANCE).sum()),
           "gn_frame": int(ex.guidance_imputed_none.sum()),
           "train_overlap_rows": int(frame_census["overlap_union"]),
           "selfid_share": float(frame_census["selfid_share"])}
    checks = {}
    for k, v in obs.items():
        want = FRAME_EXPECT.get(k)
        if isinstance(v, float) and isinstance(want, float):
            ok = abs(v - want) < 5e-4
        else:
            ok = (v == want)
        checks[k] = {"observed": v, "design_expected": want, "match": bool(ok)}
    arm_frames = man.get("arm_frames") or {}
    checks["manifest_arm_frames"] = {"observed": {"G-A": obs["ga_frame"],
                                                  "G-N": obs["gn_frame"],
                                                  "P": obs["n_frame"]},
                                     "design_expected": arm_frames,
                                     "match": bool(
                                         arm_frames.get("G-A") in (None, obs["ga_frame"])
                                         and arm_frames.get("G-N") in (None, obs["gn_frame"])
                                         and arm_frames.get("P") in (None, obs["n_frame"]))}
    # independent-implementation agreement: build_draw_g2.py computed the same
    # two frame censuses from the same §10.1 prose. Disagreement is a finding.
    mf = man.get("frame") or {}
    if mf.get("train_overlap") is not None or mf.get("selfid") is not None:
        checks["vs_build_draw_g2"] = {
            "train_overlap": {"analyze": int(frame_census["overlap_union"]),
                              "build_draw": mf.get("train_overlap"),
                              "match": mf.get("train_overlap") in
                                       (None, int(frame_census["overlap_union"]))},
            "selfid": {"analyze": int(frame_census["selfid"]),
                       "build_draw": mf.get("selfid"),
                       "match": mf.get("selfid") in (None, int(frame_census["selfid"]))},
            "note": ("two independent implementations of the §10.1 flag definitions; "
                     "a mismatch is a reportable finding, not a silent preference")}
    checks["overlap_channels"] = {
        "home_accession": int(frame_census["overlap_home_accession"]),
        "any_source_accession": int(frame_census["overlap_any_source_accession"]),
        "normalized_text": int(frame_census["overlap_normalized_text"]),
        "union": int(frame_census["overlap_union"]),
        "note": ("paragraph-id overlap is structurally ZERO and is not evidence of "
                 "novelty — E1 ids are 'P-...', E2's are 'E2P-...' (§2.5)")}
    checks["by_section"] = frame_census["by_section"]
    return checks


def _non_fail_wording(field, blk, ga, gn):
    """§6.6's pre-registered report wording, with the realized numbers filled in.

    2026-09-07 (§14.9), three corrections, because this paragraph is the most
    copy-pasteable text in the report and each defect pointed the same way:
      * the opening clause is §6.6's PRE-REGISTERED one again. "The G2
        spot-check returned PASS" was an unlabelled strengthening of the exact
        sentence §6.6 exists to weaken, and was incoherent under a
        DECISIVE_FAIL, which this function is called for too — so the FAIL
        branch now says so instead of borrowing the non-FAIL wording.
      * the "[UB, 0.94]" clause is gone. 0.94 was a literal inherited from the
        design template's different (n, bar); nothing recomputed it, so the
        shipped sentence read "[99.62%, 0.94]" — a malformed interval with one
        measured endpoint and one undocumented constant. The point is made with
        the two operating characteristics that ARE computed.
      * for guidance_direction it carries the same two terms _guidance_line()
        carries. Owner ruling (vii) OPTION 1 binds the verdict to G-A active
        precision and the G-N false-NONE rate wherever it is stated, and this
        paragraph states it.
    """
    if not blk["n"]:
        return f"{field}: no evaluable rows yet — not yet available."
    oc = blk["operating_characteristics_at_realized_n"]
    if blk["verdict"] == "DECISIVE_FAIL":
        head = (f"The G2 spot-check DID trigger a decisive failure for `{field}` — "
                "§6.6 is about what a non-FAIL does not mean and does not apply; "
                "§6.5's consequence ladder does, subject to §6.4 fact 3 (read the "
                "S-NOISE ceiling before attributing the failure to the student). ")
    else:
        head = (f"The G2 spot-check did not trigger a decisive failure for `{field}`. ")
    body = (
        f"Measured agreement is {blk['p_hat']:.2%} "
        f"[{blk['wilson_lo']:.2%}, {blk['wilson_hi']:.2%}] "
        f"(n = {blk['n']}, bar {blk['bar']}, model-consensus reference with owner rulings "
        f"on the escalated subset; NOT human validation of ground truth). At this n the "
        f"design would have declared a decisive failure with probability "
        f"{oc['P_DECISIVE_FAIL_if_q_0.83']:.2f} if true agreement were 0.83 and "
        f"{oc['P_DECISIVE_FAIL_if_q_0.85']:.2f} if it were 0.85 — those two numbers are "
        f"the whole of what this result excludes on the low side, and a true value below "
        f"the bar is made less likely at those rates, not ruled out. For the "
        f"gate-bearing fields this estimate is plausibly optimistic "
        f"(§12.1): the rater's family is the teacher's family, so teacher error the "
        f"student memorized is invisible to it, biasing measured error low. This is a "
        f"chunk-level label-accuracy figure; it is NOT the feature-level reliability "
        f"lambda of EXPANSION_PLAN §2a (§6.5) and must not be used as one. Every E2 "
        f"feature derived from `{field}` carries this figure as a stated caveat.")
    if field == "guidance_direction":
        body += (" Binding, ruling (vii): this number is a base rate over the NONE "
                 "mass and is never quoted alone — guidance_active_precision "
                 + fmt_pooled(ga) + "; guidance_false_none_rate "
                 + fmt_rate(gn["k"], gn["n"]) + ".")
    return head + body


def fmt_pooled(ga):
    """The §14.4 pooled estimate, always printed with its n_eff."""
    if ga.get("point") is None:
        return ("not yet available — corpus-re-weighted quota estimator, "
                f"{ga.get('blocked_reason', 'no evaluable rows')}")
    return (f"{ga['point']:.2%} 95% Wilson [{ga['wilson_lo']:.2%}, {ga['wilson_hi']:.2%}] "
            f"(corpus-re-weighted; n_eff {ga['n_eff']:.1f} of nominal n {ga['n_nominal']})")


def _guidance_line(primary, ga, gn):
    """§6.3 enforced mechanically: the base-rate guidance verdict may never be
    printed without active precision and the false-NONE rate ON THE SAME LINE.

    The active-precision term is the POOLED, corpus-re-weighted number of
    §14.4 — no per-direction number satisfies the caveat (owner ruling (vii),
    OPTION 1).
    """
    g = primary["guidance_direction"]
    return ("guidance_agreement_base_rate " + fmt_rate(g["k"], g["n"]) +
            f" -> {g['verdict']} at bar {g['bar']}  ||  "
            "guidance_active_precision " + fmt_pooled(ga) + "  ||  "
            "guidance_false_none_rate " + fmt_rate(gn["k"], gn["n"]))


# ---------------------------------------------------------------- report
def _report(res, man):
    p = res["primary"]
    ga = res["guidance_active_precision"]
    gad = res["guidance_active_precision_by_direction"]
    gn = res["guidance_false_none_rate"]
    sec = res["secondaries"]
    adjl = res["adjudication_layer"]
    foot = (f"> PROVENANCE: {res['provenance']}\n"
            f"> A non-FAIL is not a clearance (§6.6); red_flags is {RED_FLAGS_STATUS}\n")
    L = [f"# G2 — E2 student-label spot-check — results ({res['stage']})", "",
         f"generated {res['generated_utc']} | option {res['option']} | seed {res['seed']} | "
         f"drawn {res['n_drawn']} | rated {res['n_rated']} | "
         f"bars {json.dumps(res['ratified_bars'])}", "",
         "api_calls 0 | gpu_seconds 0 | network_calls 0", ""]

    def head(title):
        L.extend([f"## {title}", "", foot, ""])

    head("0. Completeness")
    if res["not_yet_available"]:
        for s in res["not_yet_available"]:
            L.append(f"- NOT YET AVAILABLE: {s}")
    else:
        L.append("- every pre-registered input is present")
    for f in GATE_FIELDS:
        if p[f]["provisional"]:
            L.append(f"- PROVISIONAL: {p[f]['n_unadjudicated']} contested `{f}` rows are "
                     "unadjudicated and sit outside the denominator; the bracket "
                     "[sens_all_error, sens_all_agree] carries them")
    if res["failed_batches"]:
        for r in res["failed_batches"]:
            L.append(f"- FAILED BATCH (§11.3): {r['batch']} attempt {r['attempt']} — "
                     f"cause `{r['cause']}` at {r['utc']}. A batch is NEVER re-run "
                     "because of what its verdicts say.")
    else:
        L.append("- no batch was re-run (failed_batches.json is empty or absent, §11.3)")
    L.append("")

    head("1. Primaries — gate-bearing, one bar each")
    for f in GATE_FIELDS:
        b = p[f]
        L.append(f"### `{f}` — bar {b['bar']}")
        if f == "guidance_direction":
            L.append(_guidance_line(p, ga, gn))
        else:
            L.append(f"{fmt_rate(b['k'], b['n'])} -> **{b['verdict']}**")
        kp = (b["kstar_pass"] if b["kstar_pass"] is not None
              else f"UNREACHABLE at n={b['n']} (no k can put the Wilson lower bound "
                   f"at or above {b['bar']}; a PASS is impossible at this n)")
        kf = b["kstar_fail"] if b["kstar_fail"] >= 0 else \
            f"UNREACHABLE at n={b['n']} (a DECISIVE FAIL is impossible at this n)"
        L.append(f"- PASS needs k >= {kp}; DECISIVE FAIL needs k <= {kf}; "
                 f"observed k = {b['k']} of n = {b['n']}")
        L.append(f"- non-evaluable {b['n_nonevaluable']} "
                 f"(unsure {b['n_unsure']}, unadjudicated {b['n_unadjudicated']}); "
                 f"omission-pinned errors {b['n_omission_pinned_errors']}")
        se, sa = b["sens_all_error"], b["sens_all_agree"]
        if se and sa:
            line = (f"- unsure/unruled sensitivity: all-error [{se[0]:.2%}, {se[1]:.2%}] "
                    f"vs all-agree [{sa[0]:.2%}, {sa[1]:.2%}]")
            if b["n_nonevaluable"] == 0:
                line += (" — **VACUOUS**: the two-sided bracket is degenerate because "
                         f"this field has 0 non-evaluable rows (the adjudicator emitted "
                         f"{adjl['n_unsure']} 'unsure' verdicts in {adjl['n_rulings']} "
                         "rulings). It is NOT evidence of robustness; there was nothing "
                         "for it to be robust to.")
            L.append(line)
        L.append(f"- caveat: {b['caveat']}")
        L.append("")
    L.append("Non-decisional bars (k* boundaries only — p-hat and its CI do not "
             "depend on the bar and are NOT reprinted; NO verdict word):")
    for f, blk in res["appendix_non_decisional_bars"].items():
        for bar, v in blk.items():
            need = v["p_hat_required_to_clear"]
            need_s = "unreachable at this n" if need is None else f"{need:.2%}"
            L.append(f"- `{f}` at {bar}: clearing it would need k >= "
                     f"{v['k_required_to_clear']} of n = {v['n']} (p-hat >= {need_s}); "
                     f"a decisive failure would need k <= "
                     f"{v['k_at_or_below_which_decisive']} — {v['note']}")
            # Say it plainly rather than leaving the owner to subtract two lines
            # apart. The k* boundaries and the observed k are both printed above;
            # where they touch, that is a consequential fact and it is disclosed.
            k_obs, kd, kc = p[f]["k"], v["k_at_or_below_which_decisive"], \
                v["k_required_to_clear"]
            if kd is not None and kd >= 0 and k_obs <= kd:
                L.append(f"  - **DISCLOSURE:** at this un-ratified {bar} bar the observed "
                         f"k = {k_obs} sits "
                         + ("EXACTLY ON" if k_obs == kd else "at or below")
                         + f" the decisive-failure boundary ({kd}). No verdict is defined "
                         f"at {bar} and none is emitted. The ratified bar for `{f}` is "
                         f"{p[f]['bar']} and was pinned before any chunk was rated (§14.6); "
                         "this line is stated so the fact is not left to be inferred by "
                         "subtraction.")
            # Deliberately ASYMMETRIC: only ADVERSE boundary contact is called out.
            # Both directions are already inferable by subtraction from the two
            # lines above, but promoting a favourable reading at an UN-RATIFIED bar
            # is the bar-shopping this appendix exists to prevent (§14.1). An
            # adverse fact left to inference is a disclosure defect; a favourable
            # one stated plainly is an invitation.
            _ = kc
    L.append("")

    head("2. Guidance arms (never quote the base rate alone)")
    L.append(_guidance_line(p, ga, gn))
    L.append("")
    L.append(f"- G-A estimand: {ga['estimand']}")
    L.append("- G-A weights w_d (corpus shares, re-derived from the frame): "
             + ", ".join(f"{d} {ga['weights'][d]:.6f}" for d in ACTIVE_GUIDANCE)
             + f"; nominal n {ga['n_nominal']}, n_eff "
             + ("n/a" if ga["n_eff"] is None else f"{ga['n_eff']:.1f}")
             + " — the quota's cost in effective rows.")
    L.append("- G-A per direction (DISCLOSURE ONLY, no bar, no verdict — rulings (iv), (vi)):")
    for d in ACTIVE_GUIDANCE:
        b = gad[d]
        L.append(f"  - {d} (corpus weight {b['corpus_weight']:.6f}): {fmt_rate(b['k'], b['n'])}"
                 f" [bar: {b['bar']}]")
    L.append(f"  - {GA_DIRECTION_DISCLOSURE}")
    L.append(f"- G-N estimand: {gn['estimand']}")
    L.append(f"- G-N anchors: {gn['calibration_anchors']['note']}")
    L.append("")

    head("3. Secondaries — none of them can move a gate")
    for f in GATE_FIELDS:
        for sid in ("S-SEC", "S-SECTOR", "S-ERA", "S-OVERLAP", "S-SELFID"):
            blk = sec[sid].get(f, {})
            if not blk:
                continue
            parts = [f"{lvl} {v['k']}/{v['n']}" + (f" {v['p_hat']:.1%}" if v["n"] else "")
                     for lvl, v in sorted(blk.items())]
            L.append(f"- {sid} `{f}` (naive binomial, ignores company clustering): "
                     + "; ".join(parts))
    # S-ERR: the COMPOSITION of the sentiment headline. Printed because a single
    # agreement proportion over a 3-value field hides which value carries it, and
    # the surviving E2 features consume the per-value quantities, not the pooled
    # one. This was computed and stored from the first run and never reached an
    # owner-facing surface; that omission is the defect being fixed here.
    serr = sec.get("S-ERR", {}).get("sentiment", {})
    cm = serr.get("confusion_stored_x_reference") or {}
    if cm:
        n_cm = sum(cm.values())
        L.append("- S-ERR `sentiment` error structure — stored (student) -> reference "
                 f"(adjudicated), P arm, n = {n_cm} scored + "
                 f"{serr.get('n_omitted', 0)} omission-pinned nulls: "
                 + "; ".join(f"{k} {v}" for k, v in sorted(cm.items())))
        by_st, hit = Counter(), Counter()
        for key, v in cm.items():
            s, r = key.split("->")
            by_st[s] += v
            if s == r:
                hit[s] += v
        L.append("  - precision on each STORED value (k/n = rows the reference upheld): "
                 + "; ".join(f"{s} {hit[s]}/{by_st[s]} = {hit[s] / by_st[s]:.1%}"
                             for s in sorted(by_st)))
        off_dir = sum(v for k, v in cm.items()
                      if k.split("->")[0] != k.split("->")[1]
                      and k.split("->")[1] == "NEUTRAL")
        n_err = n_cm - sum(hit.values()) + int(serr.get("n_omitted", 0))
        neu_share = by_st.get("NEUTRAL", 0) / n_cm if n_cm else 0
        L.append(f"  - READ THIS BESIDE THE HEADLINE: {off_dir} of the {n_err} sentiment "
                 "errors are the student asserting a DIRECTION on a passage the reference "
                 f"calls NEUTRAL. NEUTRAL is {by_st.get('NEUTRAL', 0)}/{n_cm} = "
                 f"{neu_share:.0%} of the SCORED stored base and is "
                 f"upheld {hit.get('NEUTRAL', 0)}/{by_st.get('NEUTRAL', 0)} = "
                 f"{hit.get('NEUTRAL', 0) / by_st['NEUTRAL']:.1%} of the time, so the "
                 "pooled agreement figure is carried by the NEUTRAL mass — structurally "
                 "the same NONE-mass problem the G-A arm was bought to expose for "
                 "guidance (§6.3). The two surviving E2 sentiment features are "
                 "`sentiment_mean_score` and `sentiment_negative_share`; the second "
                 f"consumes exactly the stored-NEGATIVE quantity measured at "
                 f"{hit.get('NEGATIVE', 0)}/{by_st.get('NEGATIVE', 0)} = "
                 f"{hit.get('NEGATIVE', 0) / by_st['NEGATIVE']:.1%} precision.")
        nk = serr.get("share_of_reference_NEGATIVE_rows_whose_stored_value_was_NEGATIVE")
        if nk and nk.get("n"):
            L.append(f"  - share of reference-NEGATIVE rows whose stored value was "
                     f"NEGATIVE: {nk['k']}/{nk['n']}. {nk['note']}")
    L.append("- S-ERR `guidance_direction` error modes: "
             + "; ".join(f"{k} {v}" for k, v in
                         sorted(sec.get("S-ERR", {}).get("guidance_direction", {}).items())))
    if RED in sec.get("S-ERR", {}):
        L.append("- S-ERR `red_flags` category-level corrections on error rows "
                 "(disclosure-only): "
                 + "; ".join(f"{k} {v}" for k, v in sorted(sec["S-ERR"][RED].items())
                             if k != "note"))
    # S-CONF: printed rather than silently stored, same reason as S-ERR.
    for f in GATE_FIELDS:
        blk = sec.get("S-CONF", {}).get("by_extraction_confidence", {}).get(f, {})
        if blk:
            L.append(f"- S-CONF `{f}` by extraction confidence (naive binomial, ignores "
                     "company clustering): "
                     + "; ".join(f"{lvl} {v['k']}/{v['n']} {v['p_hat']:.1%}"
                                 for lvl, v in sorted(blk.items())))
        blk = sec.get("S-CONF", {}).get("by_extraction_status", {}).get(f, {})
        if blk:
            L.append(f"- S-CONF `{f}` by extraction status (naive binomial, ignores "
                     "company clustering): "
                     + "; ".join(f"{lvl} {v['k']}/{v['n']} {v['p_hat']:.1%}"
                                 for lvl, v in sorted(blk.items())))
    # S-GNDEC: the guidance-omission decomposition, likewise never printed before.
    gnd = sec.get("S-GNDEC", {})
    if gnd.get("p_arm_omission_rate"):
        pa = gnd["p_arm_omission_rate"]
        L.append(f"- S-GNDEC guidance-key omission, P arm (base-rate-representative): "
                 f"{pa['k']}/{pa['n']} = {pa['p_hat']:.1%} 95% Wilson "
                 f"[{pa['wilson_95'][0]:.1%}, {pa['wilson_95'][1]:.1%}] "
                 f"(naive binomial). {gnd.get('note', '')}")
    L.append(f"- S-OVERLAP: powered = {sec['S-OVERLAP']['powered']}. "
             f"{sec['S-OVERLAP']['note']}")
    L.append(f"- S-OMIT: {sec['S-OMIT']['note']}")
    for f in GATE_FIELDS:
        om = sec["S-OMIT"][f]
        L.append(f"  - `{f}` omission rate {om['omission_rate']['k']}/"
                 f"{om['omission_rate']['n']}; omission-EXCLUDED agreement "
                 f"{fmt_rate(om['omission_excluded_rate']['k'], om['omission_excluded_rate']['n'])}")
    L.append(f"- S-MASK off-matrix census: sentiment on RISK_FACTORS "
             f"{sec['S-MASK']['sentiment_on_RISK_FACTORS']['n']}, guidance on MDA "
             f"{sec['S-MASK']['guidance_on_MDA']['n']}, on RISK_FACTORS "
             f"{sec['S-MASK']['guidance_on_RISK_FACTORS']['n']}, of which "
             f"{sec['S-MASK']['guidance_active_off_matrix']} are active values that "
             f"GUIDANCE_MAP would map to +-1/0")
    L.append(f"  - {sec['S-MASK']['f5_blocker']}")
    noise = sec["S-NOISE"]
    L.append(f"- S-NOISE ceiling arm: batches {noise['ceiling_batches']} "
             f"(rated {noise['ceiling_batches_rated']}, missing "
             f"{noise['ceiling_batches_missing']}); {noise.get('n_chunks', 0)} rows "
             f"pooled from {noise['pooled_from_batches']}")
    if noise.get("n_chunks"):
        for f in GATE_FIELDS:
            b = noise.get(f, {})
            if not b.get("n"):
                continue
            line = (f"- S-NOISE ceiling `{f}`: {fmt_rate(b['k'], b['n'])} "
                    f"(n {b['n']} of {b['n_rows_pooled']} pooled rows after the "
                    f"applicability mask; realized-from-draw "
                    f"{b.get('n_realized_from_draw')}, §14.5 planned "
                    f"{b.get('n_planned')})")
            if "bar" in b:
                need = b["p_hat_required_to_clear_bar"]
                need_s = "unreachable at this n" if need is None else f"{need:.2%}"
                line += (f" — upper bound BELOW the bar {b['bar']}: "
                         f"{b['ceiling_upper_bound_below_bar']}; lower bound clears the "
                         f"bar: {b['ceiling_lower_bound_clears_bar']}; clearing it needs "
                         f"p_hat >= {need_s}")
            L.append(line)
        L.append("  - the ceiling is reported beside every bar and CANNOT move any bar "
                 "or any decision (§5.4). No noise-normalised criterion was adopted and "
                 "none may be adopted now that the ceiling is known.")
        L.append(f"  - {noise['replicate_row_order']}")
    else:
        L.append("- S-NOISE: not yet available (no rater_b file)")
    # Reported beside the ceiling on purpose: the ceiling says the Claude family
    # agrees with itself; this says how often that family, sitting as adjudicator,
    # went against the Qwen student. Both bear on the same premise.
    sw = adjl["sided_with_rater_against_stored"]
    L.append("- ADJUDICATION LAYER (descriptive; no bar, moves nothing): the adjudicator "
             f"sided with the blind rater AGAINST the stored student label on "
             f"{sw['overall']['k']}/{sw['overall']['n']} = {sw['overall']['p_hat']:.1%} of "
             "contested rows — "
             + "; ".join(f"{f} {v['k']}/{v['n']} = {v['p_hat']:.1%}"
                         for f, v in sorted(sw["by_field"].items()))
             + f". Confidence mix {adjl['by_confidence']}; "
             f"{adjl['n_unsure']} 'unsure' verdicts in {adjl['n_rulings']} rulings.")
    L.append(f"  - {adjl['note']}")
    pr = sec["S-PROBE"]
    L.append(f"- S-PROBE: {pr['n_probe']} ids written to probe_ids.json "
             f"(realized {pr['realized']}); ruled {pr['n_ruled']}, overturned "
             f"{pr['overturned']}; escalation_triggered {pr['escalation_triggered']}")
    if pr["max_hidden_error_share_of_gate_rows"] is not None:
        L.append(f"  - at this result the agreed mass could be hiding at most "
                 f"{pr['max_hidden_error_share_of_gate_rows']:.2%} of the "
                 f"gate-bearing-applicable rows (Wilson upper bound scaled by the "
                 f"uncontested share {pr['uncontested_share_of_gate_applicable_chunks']:.2%})")
    L.append("")

    head("4. red_flags — DISCLOSURE-ONLY")
    L.append(f"status: {RED_FLAGS_STATUS}")
    s1, s2 = sec["S-RF1"], sec["S-RF2"]
    if s1.get("not_rated"):
        L.append("- not rated under Option B-lite; E2 student red-flag error is unmeasured")
    else:
        L.append(f"- S-RF1 exact-set ERROR: {fmt_rate(s1['k'], s1['n'])}")
        cb = s2.get("cluster_bootstrap_95")
        L.append(f"- S-RF2 per-category-decision ERROR: {s2['k']}/{s2['n_decisions']}"
                 + (f" = {s2['p_hat']:.2%} chunk-clustered bootstrap "
                    f"[{cb[0]:.2%}, {cb[1]:.2%}]" if cb else "")
                 + f" (naive binomial printed in results_g2.json is ANTI-CONSERVATIVE)")
    L.append(f"- rewritten RED_FLAG_CAVEAT: "
             f"{res['constants']['RED_FLAG_CAVEAT_rewritten']['provenance']}")
    L.append("")

    head("5. Comparison rows — DESCRIPTIVE ONLY, no decision reads them")
    for c in res["comparison_rows"]:
        L.append(f"- {c['name']}: other {c['other_value']} | G2 {c['g2_value']} "
                 f"[interpretable: {c['interpretable']}]")
    L.append(f"- {COMPARISON_CAVEAT}")
    L.append("")

    head("6. What a non-FAIL does not mean")
    for f in GATE_FIELDS:
        L.append(res["non_fail_wording"][f])
        L.append("")

    head("7. Frame re-derivation and limits")
    for k, v in res["frame_checks"].items():
        if isinstance(v, dict) and "match" in v:
            L.append(f"- {k}: observed {v['observed']} vs design {v['design_expected']} "
                     f"-> match {v['match']}")
    L.append("- 8K_BODY (790 chunks, 0.249%) is excluded by predicate; bounded influence "
             "<= 0.25 pts all-section, <= 0.30 sentiment, <= 0.83 guidance (§2.3)")
    L.append("- the occurrence-weighted estimand is out of reach (Kish n_eff ~ 8.9 at "
             "n=300); features consume a weighted rate this design cannot estimate (§2.4)")
    L.append("- the extension stratum was never labeled; the 2026-08-21 'unseen sectors' "
             "promotion clause is DEFERRED, not satisfied (§7)")
    L.append("- G2 supplies chunk-level label accuracy ONLY. It does not supply "
             "EXPANSION_PLAN §2a's feature-level reliability lambda (§6.5).")
    L.append("")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------ assertions
# A8 is a FIELD scan, not a token scan (§14.9). The token version passed while
# §6.6's prose paragraph stated the guidance verdict alone, because that
# paragraph never contains the literal 'guidance_agreement_base_rate'. Owner
# ruling (vii) OPTION 1 binds the VERDICT wherever it is written — in the report
# AND in every string results_g2.json ships. Module-level so the guard itself is
# testable; a guard that cannot be shown to fire is not a guard.
VERDICT_MARKERS = ("PASS", "DECISIVE_FAIL", "INDETERMINATE",
                   "trigger a decisive failure", "Measured agreement is")


def guidance_verdict_is_escorted(text):
    """False iff `text` states the guidance verdict without its two arms (§6.3)."""
    if "guidance_direction" not in text and \
            "guidance_agreement_base_rate" not in text:
        return True
    if "guidance_agreement_base_rate" not in text and \
            not any(w in text for w in VERDICT_MARKERS):
        return True
    return ("guidance_active_precision" in text
            and "guidance_false_none_rate" in text)


def _walk(obj, fn, path=""):
    if isinstance(obj, dict):
        fn(obj, path)
        for k, v in obj.items():
            _walk(v, fn, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _walk(v, fn, f"{path}[{i}]")


def _assertions(res, report, scored, bars, man, rate_red_flags):
    """The §10.2.7 hard assertions. Each one is a real check."""
    passed = []

    n_verdicts = sum(1 for f in GATE_FIELDS if "verdict" in res["primary"][f])
    assert n_verdicts == len(GATE_FIELDS)
    for f, blk in res["appendix_non_decisional_bars"].items():
        for _, v in blk.items():
            assert "verdict" not in v and "no verdict is defined" in v["note"]
    passed.append("A1_one_ratified_bar_per_field_no_bar_shopping")

    assert res["ratified_bars"] == (man.get("ratified_bars") or {})
    passed.append("A2_bars_match_draw_manifest")

    assert not (scored.field == "distress_tier").any()
    assert "distress_tier" not in json.dumps(res)
    passed.append("A3_no_distress_tier_scored")

    assert not (scored.section_type == "8K_BODY").any()
    passed.append("A4_no_8k_body_in_any_arm")

    assert not ((scored.field == RED) & (scored.basis.isin(["owner", "escalation_owner"]))).any()
    passed.append("A5_no_owner_ruling_on_red_flags")

    passed.append("A6_rater_schema_guard_passed_on_every_verdict_file")

    gate = scored[(scored.field.isin(GATE_FIELDS)) & (scored.applicable)]
    probe_ids = set(json.loads((G2 / "probe_ids.json").read_text())["chunk_ids"])
    assert probe_ids <= set(gate.chunk_id)
    passed.append("A7_probe_frame_has_gate_bearing_applicable_field")

    for line in report.splitlines():
        assert guidance_verdict_is_escorted(line), (
            "§6.3 / ruling (vii): a guidance verdict was printed without "
            f"guidance_active_precision AND guidance_false_none_rate: {line[:220]}")
    unescorted = []
    _walk(res, lambda d, path: unescorted.extend(
        f"{path}.{k}" for k, v in d.items()
        if isinstance(v, str) and not guidance_verdict_is_escorted(v)))
    assert not unescorted, (
        "§6.3 / ruling (vii): results_g2.json states a guidance verdict without "
        f"its two arms at {unescorted[:5]}")
    passed.append("A8_guidance_verdict_never_quoted_without_its_two_arms")

    caveat = res["constants"]["RED_FLAG_CAVEAT_rewritten"]["provenance"]
    assert RED_FLAGS_STATUS in caveat
    passed.append("A9_red_flag_caveat_contains_red_flags_status")

    bad = []
    _walk(res, lambda d, p: bad.extend(
        f"{p}.{k}" for k in d if k.lower() in FORBIDDEN_RESULT_KEYS))
    assert not bad, f"§6.5 withdrawal violated: {bad}"
    passed.append("A10_no_lambda_reliability_or_attenuation_denominator")

    problems = []

    def tag_check(d, p):
        if "wilson_95" in d or "cluster_bootstrap_95" in d:
            iv = d.get("interval")
            if iv not in ("naive_binomial", "chunk_clustered_bootstrap"):
                problems.append(p)
    _walk(res["secondaries"], tag_check)
    assert not problems, f"untagged intervals at {problems[:5]}"
    assert res["secondaries"]["S-RF2"]["interval"] == "chunk_clustered_bootstrap"
    passed.append("A11_every_secondary_interval_is_tagged")

    so = res["secondaries"]["S-OVERLAP"]
    assert so["powered"] is False and "NOT POWERED" in so["note"]
    passed.append("A12_s_overlap_present_and_labelled_not_powered")

    # A13 asserts ONLY that each verdict WORD follows from that field's own
    # k / n / bar as printed. It does NOT assert that k itself is reproducible
    # from results_g2.json: k comes from the rating and adjudication layers,
    # which results_g2.json now PINS BY HASH (.inputs) but does not contain.
    # Re-deriving k requires draw_g2.csv + verdicts/ + adjudications/.
    for f in GATE_FIELDS:
        b = res["primary"][f]
        assert b["verdict"] == verdict_of(b["k"], b["n"], b["bar"])
    for req in ("data/f4/g2/adjudications/adjudications.json",
                "data/f4/g2/draw_manifest.json"):
        assert req in res["inputs"], \
            f"{req} is not hashed in results_g2.json.inputs — the chain that " \
            "produces k would be unpinned"
    passed.append("A13_verdict_word_follows_from_its_own_k_n_bar__k_itself_is_only_"
                  "hash_pinned_not_recomputable_from_results_g2_json")

    want_sec = {"S-SEC", "S-SECTOR", "S-ERA", "S-CONF", "S-ERR", "S-OMIT", "S-RF1",
                "S-RF2", "S-MASK", "S-NOISE", "S-OVERLAP", "S-SELFID", "S-GNDEC",
                "S-PROBE"}
    assert want_sec <= set(res["secondaries"]), \
        f"missing pre-registered secondaries: {sorted(want_sec - set(res['secondaries']))}"
    passed.append("A15_all_14_pre_registered_secondaries_present")

    assert res["api_calls"] == 0 and res["network_calls"] == 0
    loaded = [m for m in NETWORK_MODULES if m in sys.modules]
    assert not loaded, f"network module(s) imported: {loaded}"
    passed.append("A14_zero_api_calls_no_network_module_imported")

    # ---- added 2026-09-07 by §14.8, in the same style as the above.
    assert man.get("parameters_status") == PARAMETERS_STATUS
    assert all(man.get(k) == v for k, v in RATIFIED.items())
    passed.append("A16_parameters_owner_ratified_and_match_analyze_g2_constants")

    gap = res["guidance_active_precision"]
    assert "n_eff" in gap and "weights" in gap, \
        "guidance_active_precision must carry n_eff and weights (§14.8)"
    assert gap["bar"] is None and "verdict" not in gap, \
        "G-A carries no bar and no verdict (rulings (iv), (vi))"
    w = gap["weights"]
    assert set(w) == set(ACTIVE_GUIDANCE) and abs(sum(w.values()) - 1.0) < 1e-12, \
        "the four corpus weights must be present and sum to 1 — never renormalised"
    assert all(abs(w[d] - RATIFIED["ga_corpus_counts"][d] / 6479) < 5e-7
               for d in ACTIVE_GUIDANCE), "w_d != N_d/6479 (§14.4)"
    if gap.get("point") is not None:
        chk = sum(w[d] * res["guidance_active_precision_by_direction"][d]["p_hat"]
                  for d in ACTIVE_GUIDANCE)
        assert abs(chk - gap["point"]) < 1e-12, \
            "pooled point is not SUM_d w_d * p_hat_d — the §14.4 estimator was not used"
        lo_re, hi_re = wilson_p(gap["point"], gap["n_eff"])
        assert (abs(lo_re - gap["wilson_lo"]) < 1e-12
                and abs(hi_re - gap["wilson_hi"]) < 1e-12), \
            "the G-A interval is not wilson_p(p_hat_active, n_eff) (§14.4)"
    passed.append("A17_ga_pooled_is_corpus_reweighted_with_n_eff_and_no_bar")

    bydir = res["guidance_active_precision_by_direction"]
    assert set(bydir) == set(ACTIVE_GUIDANCE), \
        f"by-direction disclosure must cover all four directions, got {sorted(bydir)}"
    for d, blk in bydir.items():
        assert blk["bar"] is None and "verdict" not in blk, \
            f"{d} carries a bar or a verdict — rulings (iv) and (vi) forbid both"
        assert "note" in blk and "disclosure only" in blk["note"]
    passed.append("A18_every_guidance_direction_carries_bar_null_and_no_verdict")

    noise = res["secondaries"]["S-NOISE"]
    assert noise["ceiling_batches"] == RATIFIED["ceiling_batches"], \
        "the ceiling arm is the three ruled batches (§14.5); it is not resizable here"
    assert set(noise["pooled_from_batches"]) <= set(RATIFIED["ceiling_batches"]), \
        f"S-NOISE pooled a non-ceiling batch: {noise['pooled_from_batches']}"
    assert noise["cannot_move_any_bar"] is True
    for f in GATE_FIELDS:
        blk = noise.get(f)
        if isinstance(blk, dict) and blk.get("n"):
            assert "verdict" not in blk, "the ceiling emits no verdict (§5.4)"
    passed.append("A19_s_noise_pools_only_the_three_ruled_ceiling_batches")
    return passed


# ------------------------------------------------------------- self-test
def selftest():
    """In-memory checks of every estimator against hand-computed values.

    Touches no parquet, no draw, no network. Run: python3 analyze_g2.py --selftest
    """
    ok = []

    def chk(name, cond):
        assert cond, f"SELFTEST FAILED: {name}"
        ok.append(name)

    # ---- 1. Wilson, hand-computed
    lo, hi = wilson(10, 40)
    chk("wilson(10,40) == [0.1418697, 0.4019426]",
        abs(lo - 0.14186967895549518) < 1e-12 and abs(hi - 0.40194259066970106) < 1e-12)
    # closed-form cross-check, written out independently
    p, n, z = 0.25, 40, 1.96
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    chk("wilson matches an independent closed-form evaluation",
        abs(lo - (c - h)) < 1e-15 and abs(hi - (c + h)) < 1e-15)
    chk("wilson(0,20) upper == 16.11% (the §5.5 probe bound)",
        abs(wilson(0, 20)[1] - 0.16113012549493322) < 1e-12 and wilson(0, 20)[0] == 0.0)
    chk("wilson(36,40) == v1.2 S7 ceiling [0.7695, 0.9604]",
        abs(wilson(36, 40)[0] - 0.7694792561952611) < 1e-12
        and abs(wilson(36, 40)[1] - 0.9604211124044252) < 1e-12)
    chk("wilson(k,0) is nan, not a crash", all(np.isnan(x) for x in wilson(0, 0)))

    chk("wilson_p(k/n, n) is wilson(k, n) — one formula, not two methods",
        wilson_p(10 / 40, 40) == wilson(10, 40)
        and wilson_p(0.9, 107) == wilson_p(0.9, 107))
    chk("wilson_p accepts a NON-INTEGER effective n (the §14.4 use)",
        abs(wilson_p(0.80, 85.18355511291443)[0] - 0.7029599561679926) < 1e-12
        and abs(wilson_p(0.80, 85.18355511291443)[1] - 0.8711489347732643) < 1e-12)

    # ---- 2. k* against the design's published operating characteristics
    for n, b, kp, kf in [(253, 0.85, 227, 203), (253, 0.90, 238, 218),
                         (168, 0.90, 159, 143), (337, 0.90, 315, 292),
                         (168, 0.85, 152, 133), (337, 0.85, 300, 273),
                         (90, 0.90, 87, 75), (90, 0.85, 84, 69),
                         (59, 0.90, 58, 48), (119, 0.90, 114, 100),
                         (119, 0.85, 109, 93)]:
        chk(f"kstar n={n} b={b} -> pass {kp}, fail {kf} (design §6.2/§6.3)",
            kstar_pass(n, b) == kp and kstar_fail(n, b) == kf)
    # §14.6, the boundaries pinned at the RATIFIED (n, b) before any data
    chk("§14.6 sentiment: n=337 b=0.85 -> PASS k>=300 (p>=0.8902), FAIL k<=273 (p<=0.8101)",
        kstar_pass(337, 0.85) == 300 and abs(300 / 337 - 0.8902077) < 1e-6
        and kstar_fail(337, 0.85) == 273 and abs(273 / 337 - 0.8100890) < 1e-6)
    chk("§14.6 guidance: n=119 b=0.85 -> PASS k>=109 (p>=0.9160), FAIL k<=93 (p<=0.7815)",
        kstar_pass(119, 0.85) == 109 and abs(109 / 119 - 0.9159664) < 1e-6
        and kstar_fail(119, 0.85) == 93 and abs(93 / 119 - 0.7815126) < 1e-6)

    # ---- 3. exact binomial power against the design's tables
    for n, q, b, want, which in [(253, 0.90, 0.90, 0.015, "pass"),
                                 (253, 0.95, 0.90, 0.799, "pass"),
                                 (253, 0.83, 0.90, 0.926, "fail"),
                                 (253, 0.85, 0.90, 0.724, "fail"),
                                 (253, 0.90, 0.85, 0.609, "pass"),
                                 (90, 0.95, 0.90, 0.336, "pass"),
                                 (90, 0.80, 0.90, 0.821, "fail"),
                                 (90, 0.85, 0.90, 0.372, "fail"),
                                 (59, 0.95, 0.90, 0.199, "pass")]:
        got = p_pass(n, q, b) if which == "pass" else p_fail(n, q, b)
        chk(f"P({which.upper()} | q={q}) at n={n}, bar={b} == {want}", abs(got - want) < 6e-4)

    # ---- 4. verdict logic at the boundary
    chk("verdict PASS at k=kstar_pass", verdict_of(227, 253, 0.85) == "PASS")
    chk("verdict DECISIVE_FAIL at k=kstar_fail", verdict_of(203, 253, 0.85) == "DECISIVE_FAIL")
    chk("verdict INDETERMINATE between", verdict_of(215, 253, 0.85) == "INDETERMINATE")

    # ---- 5. exact-set logic
    a = as_set([{"category": "DEMAND_WEAKNESS", "modality": "REALIZED"}])
    b_ = as_set([["DEMAND_WEAKNESS", "REALIZED"]])
    chk("as_set normalizes struct-list and list-of-lists identically", a == b_)
    chk("as_set(None) is None and as_set([]) is empty", as_set(None) is None and as_set([]) == frozenset())
    stored_set = frozenset({("DEMAND_WEAKNESS", "REALIZED")})
    ref_set = frozenset({("DEMAND_WEAKNESS", "HYPOTHETICAL"), ("MARGIN_COST_PRESSURE", "REALIZED")})
    chk("exact-set mismatch detected", stored_set != ref_set)
    wrong = sum(1 for c in CATS
                if {m for cc, m in stored_set if cc == c} != {m for cc, m in ref_set if cc == c})
    chk("per-category decisions: 2 of 6 wrong (modality flip + missed flag)", wrong == 2)
    chk("cluster bootstrap is seeded and deterministic",
        cluster_bootstrap([2, 0, 1, 0, 3], 6) == cluster_bootstrap([2, 0, 1, 0, 3], 6))

    # ---- 6. scoring: masking, omissions, unsure, owner supersession
    draw = pd.DataFrame({"rank": range(1, 9),
                         "batch": ["batch_01"] * 8,
                         "arm": ["P"] * 6 + ["G-A", "G-N"],
                         "chunk_id": [f"c{i}" for i in range(1, 9)]})
    section_of = {"c1": "MDA", "c2": "MDA", "c3": "EX99_PRESS_RELEASE",
                  "c4": "EX99_PRESS_RELEASE", "c5": "RISK_FACTORS",
                  "c6": "EX99_PRESS_RELEASE", "c7": "EX99_PRESS_RELEASE",
                  "c8": "MDA"}
    raw = {
        "c1": {"sentiment": "NEUTRAL", "guidance_direction": "NONE", "red_flags": []},
        "c2": {"sentiment": "POSITIVE", "guidance_direction": None, "red_flags": []},
        "c3": {"sentiment": None, "guidance_direction": "NONE", "red_flags": []},
        "c4": {"sentiment": "POSITIVE", "guidance_direction": "RAISED", "red_flags": []},
        "c5": {"sentiment": "NEUTRAL", "guidance_direction": None, "red_flags": []},
        "c6": {"sentiment": "NEUTRAL", "guidance_direction": None, "red_flags": []},
        "c7": {"sentiment": "NEUTRAL", "guidance_direction": "MAINTAINED", "red_flags": []},
        "c8": {"sentiment": "NEGATIVE", "guidance_direction": None, "red_flags": []},
    }
    stored = {c: stored_values(dict(v, chunk_id=c), True) for c, v in raw.items()}
    chk("stored null sentiment becomes the MISSING sentinel", stored["c3"]["sentiment"] == MISSING)
    rater = {
        "c1": {"sentiment": "NEUTRAL", "guidance_direction": "NONE", RED: frozenset()},
        "c2": {"sentiment": "NEGATIVE", "guidance_direction": "NONE", RED: frozenset()},
        "c3": {"sentiment": "POSITIVE", "guidance_direction": "NONE", RED: frozenset()},
        "c4": {"sentiment": "POSITIVE", "guidance_direction": "LOWERED", RED: frozenset()},
        "c5": {"sentiment": "NEGATIVE", "guidance_direction": "NONE", RED: frozenset()},
        "c6": {"sentiment": "NEUTRAL", "guidance_direction": "NONE", RED: frozenset()},
        "c7": {"sentiment": "NEUTRAL", "guidance_direction": "MAINTAINED", RED: frozenset()},
        "c8": {"sentiment": "NEUTRAL", "guidance_direction": "NONE", RED: frozenset()},
    }
    adj = {("c2", "sentiment"): {"verdict": "disagree", "correct_label": "NEGATIVE"},
           ("c4", "guidance_direction"): {"verdict": "unsure", "correct_label": None},
           ("c8", "sentiment"): {"verdict": "disagree", "correct_label": "NEUTRAL"}}
    owner = {("c8", "sentiment"): {"correct_label": "NEGATIVE", "note": "owner supersedes"}}
    sc = score(draw, stored, section_of, rater, adj, owner, True)

    sm = sc[(sc.field == "sentiment")]
    chk("sentiment on RISK_FACTORS is MASKED, not scored",
        sm[sm.chunk_id == "c5"].iloc[0].basis == "masked")
    chk("guidance on MDA is MASKED even though a value is stored",
        sc[(sc.chunk_id == "c1") & (sc.field == "guidance_direction")].iloc[0].basis == "masked")
    chk("omitted stored sentiment is a pinned ERROR (§1.3)",
        sm[sm.chunk_id == "c3"].iloc[0].err == 1.0
        and sm[sm.chunk_id == "c3"].iloc[0].basis == "omission_pinned_error")
    chk("bad-enum guidance null is a pinned ERROR (§1.3)",
        sc[(sc.chunk_id == "c6") & (sc.field == "guidance_direction")].iloc[0].err == 1.0)
    chk("imputed-NONE stored row scored AS NONE and agreeing",
        sc[(sc.chunk_id == "c3") & (sc.field == "guidance_direction")].iloc[0].err == 0.0)
    chk("owner ruling supersedes the adjudicator (c8: NEGATIVE, not NEUTRAL)",
        sm[sm.chunk_id == "c8"].iloc[0].err == 0.0
        and sm[sm.chunk_id == "c8"].iloc[0].basis == "owner")
    chk("unsure is non-evaluable, not an error",
        np.isnan(sc[(sc.chunk_id == "c4") & (sc.field == "guidance_direction")].iloc[0].err))

    sent = sc[(sc.arm == "P") & (sc.field == "sentiment") & (sc.applicable)]
    k, kerr, n, nu, nun, nn = counts(sent)
    chk("sentiment P-arm: k=3 agree, 2 errors, n=5 evaluable (c5 masked out)",
        (k, kerr, n) == (3, 2, 5))
    guid_all = sc[(sc.field == "guidance_direction") & (sc.applicable)]
    kg, kge, ng, nug, _, _ = counts(guid_all)
    chk("guidance applicable rows: k=2 agree, 1 error, n=3, 1 unsure excluded",
        (kg, kge, ng, nug) == (2, 1, 3, 1))

    blk = primary_block(sent, 0.85, "test")
    chk("sens_all_error / sens_all_agree bracket the point estimate",
        blk["sens_all_error"][1] <= wilson(3, 5)[1] + 1e-12
        and blk["sens_all_agree"][0] >= wilson(3, 5)[0] - 1e-12)
    chk("primary_block reports the omission-pinned errors it contains",
        blk["n_omission_pinned_errors"] == 1)
    om = _s_omit(sent, sc[(sc.field == "guidance_direction") & (sc.applicable)], sent)
    chk("S-OMIT excludes omissions from numerator AND denominator",
        om["sentiment"]["omission_excluded_rate"]["n"] == 4
        and om["sentiment"]["omission_rate"]["k"] == 1)

    # ---- 7. probe frame: RISK_FACTORS-only and contested chunks excluded
    ids, info = probe_draw(sc, {"P": 12, "G-A": 4, "G-N": 4})
    chk("probe frame excludes the RISK_FACTORS row (no applicable gate-bearing field)",
        "c5" not in ids)
    chk("probe frame excludes contested chunks", "c2" not in ids and "c4" not in ids)
    chk("probe frame keeps a fully-matched gate-bearing chunk", "c1" in ids)
    chk("probe stratification deficits move to P",
        info["quotas"]["P"] >= 12 and set(info["realized"]) <= {"P", "G-A", "G-N"})
    ids2, _ = probe_draw(sc, {"P": 12, "G-A": 4, "G-N": 4})
    chk("probe draw is seeded and reproducible", ids == ids2)

    # ---- 8. the escalation channel and the rater schema guard
    adj2 = dict(adj)
    adj2[("c1", "sentiment")] = {"verdict": "disagree", "correct_label": "NEGATIVE"}
    sc2 = score(draw, stored, section_of, rater, adj2, owner, True)
    row = sc2[(sc2.chunk_id == "c1") & (sc2.field == "sentiment")].iloc[0]
    chk("an adjudicated UNCONTESTED row becomes an escalation-sweep error",
        row.err == 1.0 and row.basis == "escalation_adjudicator")
    for bad_obj, why in [
        ({"chunk_id": "c1", "verdict": "agree", "sentiment": "NEUTRAL",
          "guidance_direction": "NONE", "red_flags": [], "reason": "x"}, "verdict key"),
        ({"chunk_id": "c1", "sentiment": "n/a", "guidance_direction": "NONE",
          "red_flags": [], "reason": "x"}, "n/a value"),
        ({"chunk_id": "c1", "sentiment": None, "guidance_direction": "NONE",
          "red_flags": [], "reason": "x"}, "null value"),
        ({"chunk_id": "zz", "sentiment": "NEUTRAL", "guidance_direction": "NONE",
          "red_flags": [], "reason": "x"}, "chunk_id not in batch"),
        ({"chunk_id": "c1", "sentiment": "NEUTRAL", "guidance_direction": "MAYBE",
          "red_flags": [], "reason": "x"}, "enum violation"),
    ]:
        try:
            check_rater_objects("t.json", [bad_obj], {"c1"}, True)
            raise SystemExit(f"SELFTEST FAILED: guard missed {why}")
        except AssertionError:
            ok.append(f"rater guard rejects {why}")
    good = {"chunk_id": "c1", "sentiment": "NEUTRAL", "guidance_direction": "NONE",
            "red_flags": [["DEMAND_WEAKNESS", "REALIZED"]], "reason": "x"}
    chk("rater guard accepts a conforming object",
        check_rater_objects("t.json", [good], {"c1"}, True) == ["c1"])

    # ---- 9. the red-flag caveat carries the demotion status verbatim
    s1 = {"k": 90, "n": 300, "p_hat": 0.30, "wilson_lo": 0.25, "wilson_hi": 0.36}
    chk("rewritten RED_FLAG_CAVEAT contains red_flags_status verbatim",
        RED_FLAGS_STATUS in _red_flag_caveat(s1, {}, True)
        and RED_FLAGS_STATUS in _red_flag_caveat({}, {}, False))
    chk("company_token strips punctuation (reproduces the design's 46.46%)",
        company_token("Tesla, Inc.") == "tesla" and company_token("JPMORGAN CHASE & CO") == "jpmorgan")

    # ---- 10. the G-A quota re-weighting (§14.4) — the one estimator this pass adds
    w, tot = ga_weights_from_counts(RATIFIED["ga_corpus_counts"])
    chk("w_d from the 6,479-row active EX99 frame == §14.4's pinned vector to 6 dp",
        tot == 6479 and [round(w[d], 6) for d in ACTIVE_GUIDANCE]
        == [0.573545, 0.299429, 0.116839, 0.010187])
    N_GA = {"RAISED": 46, "MAINTAINED": 24, "LOWERED": 15, "WITHDRAWN": 15}
    chk("the ratified G-A targets sum to 100 (§14.3)", sum(N_GA.values()) == 100)
    # §14.4's three behaviours, computed and published BEFORE data. Reproducing
    # them here is what puts the estimator on the record rather than in prose.
    c80 = ga_pooled({d: 0.80 * N_GA[d] for d in N_GA}, N_GA, w)
    chk("§14.4 case p_d=0.80 all four -> p_hat 0.800, n_eff 85.2, CI [0.703, 0.871]",
        abs(c80["point"] - 0.800) < 5e-4 and abs(c80["n_eff"] - 85.2) < 0.05
        and abs(c80["wilson_lo"] - 0.703) < 5e-4 and abs(c80["wilson_hi"] - 0.871) < 5e-4)
    c100 = ga_pooled({d: 1.0 * N_GA[d] for d in N_GA}, N_GA, w)
    chk("§14.4 case p_d=1.00 all four -> n_eff 89.3, CI [0.959, 1.000], NOT degenerate",
        abs(c100["n_eff"] - 89.3) < 0.05 and abs(c100["wilson_lo"] - 0.959) < 5e-4
        and 0.999 < c100["wilson_hi"] <= 1.0)
    mix = {"RAISED": 0.90, "MAINTAINED": 0.85, "LOWERED": 0.70, "WITHDRAWN": 0.60}
    cmx = ga_pooled({d: mix[d] * N_GA[d] for d in N_GA}, N_GA, w)
    chk("§14.4 case (R .90 / M .85 / L .70 / W .60) -> 0.8586, n_eff 90.9, [0.772, 0.916]",
        abs(cmx["point"] - 0.8586) < 5e-5 and abs(cmx["n_eff"] - 90.9) < 0.05
        and abs(cmx["wilson_lo"] - 0.772) < 5e-4 and abs(cmx["wilson_hi"] - 0.916) < 5e-4)
    unw = sum(mix[d] * N_GA[d] for d in N_GA) / 100
    chk("the re-weighting MOVES the answer: 0.8586 weighted vs 0.813 quota-distorted",
        abs(unw - 0.813) < 1e-12 and cmx["point"] - unw > 0.04)
    chk("the quota costs effective rows: n_eff < nominal 100 in all three cases",
        max(c80["n_eff"], c100["n_eff"], cmx["n_eff"]) < 100)

    def fake_ga(spec):
        """spec = {direction: (k_agree, n)} -> a G-A slice of the scored frame."""
        rows = []
        for d, (k, n) in spec.items():
            for i in range(n):
                rows.append(dict(chunk_id=f"{d}-{i}", arm="G-A", field="guidance_direction",
                                 applicable=True, stored=d, err=0.0 if i < k else 1.0,
                                 basis="uncontested" if i < k else "adjudicator"))
        return pd.DataFrame(rows)

    ga_rows = fake_ga({"RAISED": (8, 10), "MAINTAINED": (5, 10),
                       "LOWERED": (10, 10), "WITHDRAWN": (0, 10)})
    pooled, bydir = ga_reweighted(ga_rows, w, complete=True)
    hand = 0.573545 * 0.8 + 0.299429 * 0.5 + 0.116839 * 1.0 + 0.010187 * 0.0
    chk("pooled p_hat == SUM_d w_d*p_hat_d, hand-computed 0.7253895 (not the raw 0.575)",
        abs(pooled["point"] - hand) < 5e-6 and abs(hand - 0.7253895) < 1e-7
        and abs(pooled["p_hat_unweighted_do_not_quote"] - 0.575) < 1e-12)
    lo_h, hi_h = wilson_p(pooled["point"], pooled["n_eff"])
    chk("the interval is wilson_p(p_hat_active, n_eff), reported with n_eff",
        abs(pooled["wilson_lo"] - lo_h) < 1e-12 and abs(pooled["wilson_hi"] - hi_h) < 1e-12
        and pooled["n_eff"] is not None and pooled["n_nominal"] == 40)
    chk("p_hat_d=1.0 and p_hat_d=0.0 strata do NOT give a zero-width interval "
        "(why the delta-method form is struck)", pooled["wilson_hi"] - pooled["wilson_lo"] > 0.05)
    chk("every direction ships with its own Wilson interval, bar None, and no verdict",
        all(bydir[d]["bar"] is None and "verdict" not in bydir[d]
            and bydir[d]["wilson_lo"] is not None for d in ACTIVE_GUIDANCE))
    chk("WITHDRAWN at 0/10 is reported, not suppressed",
        bydir["WITHDRAWN"]["k"] == 0 and bydir["WITHDRAWN"]["n"] == 10
        and bydir["WITHDRAWN"]["wilson_hi"] > 0)
    chk("corpus weights ride on each direction block",
        abs(bydir["LOWERED"]["corpus_weight"] - 757 / 6479) < 1e-12)

    ga_missing = ga_rows[ga_rows.stored != "WITHDRAWN"]
    pooled2, _ = ga_reweighted(ga_missing, w, complete=False)
    chk("an empty direction on an INCOMPLETE arm: no point, weights NOT renormalised",
        pooled2["point"] is None and pooled2["empty_directions"] == ["WITHDRAWN"]
        and abs(sum(pooled2["weights"].values()) - 1.0) < 1e-12
        and pooled2["weights"]["RAISED"] == w["RAISED"])
    try:
        ga_reweighted(ga_missing, w, complete=True)
        raise SystemExit("SELFTEST FAILED: n_d == 0 on a COMPLETE arm must hard-fail")
    except AssertionError:
        ok.append("empty direction on a COMPLETE arm hard-fails instead of renormalising")

    # ---- 11. the three-batch ceiling arm (§14.5), pooled across CEILING_BATCHES
    ceiling = list(RATIFIED["ceiling_batches"])
    batch_of, sec_of, ra, rb = {}, {}, {}, {}
    for bname in ceiling + ["batch_04"]:
        for i in range(40):
            cid = f"{bname}-{i}"
            batch_of[cid] = bname
            sec_of[cid] = ("MDA" if i < 20 else
                           "EX99_PRESS_RELEASE" if i < 32 else "RISK_FACTORS")
            ra[cid] = {"sentiment": "NEUTRAL", "guidance_direction": "NONE",
                       RED: frozenset()}
            if bname in ceiling:      # rater B re-rates ONLY the ceiling batches
                rb[cid] = {"sentiment": "NEGATIVE" if i % 10 == 0 else "NEUTRAL",
                           "guidance_direction": "NONE", RED: frozenset()}
    tb = {"sentiment": 0.85, "guidance_direction": 0.85}
    # ceiling_realized_n() on this synthetic draw: 3 batches x (20 MDA + 12 EX99)
    ST_CEILING_N = ceiling_realized_n(
        pd.DataFrame({"chunk_id": list(batch_of), "batch": list(batch_of.values())}),
        sec_of, ceiling)
    chk("ceiling_realized_n masks the ceiling arm per field, from the draw alone",
        ST_CEILING_N == {"sentiment": 96, "guidance_direction": 36})
    noise = _s_noise(ra, rb, sec_of, tb, True, ceiling, ceiling, batch_of,
                     ST_CEILING_N)
    chk("S-NOISE pools all THREE ceiling batches: 120 rows, batch_04 excluded",
        noise["n_chunks"] == 120 and noise["pooled_from_batches"] == ceiling
        and noise["ceiling_batches_missing"] == [])
    chk("120 re-rated ROWS are not 120 evaluable rows per field: sentiment 96 "
        "(MDA+EX99), guidance 36 (EX99), 24 / 84 masked out",
        noise["sentiment"]["n"] == 96 and noise["sentiment"]["n_masked_out"] == 24
        and noise["guidance_direction"]["n"] == 36
        and noise["guidance_direction"]["n_masked_out"] == 84)
    chk("pooled ceiling agreement is counted across batches, not per batch",
        noise["sentiment"]["k"] == 84 and noise["guidance_direction"]["k"] == 36)
    chk("the ceiling reports what it would take to clear the bar, and clears nothing "
        "by itself", noise["sentiment"]["ceiling_lower_bound_clears_bar"] is False
        and noise["sentiment"]["ceiling_upper_bound_below_bar"] is False
        and noise["sentiment"]["k_required_to_clear_bar"] == kstar_pass(96, 0.85)
        and noise["cannot_move_any_bar"] is True
        and all("verdict" not in noise[f] for f in GATE_FIELDS))
    chk("a ceiling that clears the bar is reported as clearing it",
        noise["guidance_direction"]["ceiling_lower_bound_clears_bar"] is True)
    rb_partial = {c: v for c, v in rb.items() if batch_of[c] != "batch_03"}
    n2 = _s_noise(ra, rb_partial, sec_of, tb, True, ceiling, ceiling[:2],
                  batch_of, ST_CEILING_N)
    chk("a missing replicate is named, and the arm SHRINKS rather than being faked",
        n2["ceiling_batches_missing"] == ["batch_03"] and n2["n_chunks"] == 80
        and n2["sentiment"]["n"] == 64)
    rb_leak = dict(rb)
    rb_leak["batch_04-0"] = ra["batch_04-0"]
    n3 = _s_noise(ra, rb_leak, sec_of, tb, True, ceiling, ceiling, batch_of,
                  ST_CEILING_N)
    chk("a rater_b row outside CEILING_BATCHES is surfaced (A19 then hard-fails)",
        "batch_04" in n3["pooled_from_batches"])
    n0 = _s_noise(ra, {}, sec_of, tb, True, ceiling, [], batch_of, ST_CEILING_N)
    chk("no rater_b file yet: not_yet_available, no invented ceiling",
        n0["not_yet_available"] is True and n0["n_chunks"] == 0
        and n0["ceiling_batches_missing"] == ceiling)

    print(f"SELFTEST PASSED — {len(ok)} checks")
    for name in ok:
        print("  ok:", name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
