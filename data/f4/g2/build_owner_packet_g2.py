#!/usr/bin/env python3
"""Build data/f4/g2/OWNER_RULING_PACKET.md from the MODEL-CONSENSUS stage.

Mirrors data/hardening/spotcheck_v12/OWNER_RULING_PACKET.md in structure:
PART A = the needs_human rows (grouped by adjudicator pattern slug),
PART B = the 20-row S-PROBE of the uncontested set, then HOW TO RECORD.

Reads only; writes only OWNER_RULING_PACKET.md. No network, no API, $0.

Blindness (design §5.1): the packet prints chunk_id + text + labels only.
section_type is loaded to apply the §1.2 applicability mask and is never
printed; sector / CIK / company / filing date are never loaded.
"""
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# ONE definition of the §6.3 / ruling (vii) escort guard, imported rather than
# copied. A ported copy would drift; the guard that matters is the one
# analyze_g2.py enforces on report_g2.md, and the packet is the artifact the
# owner actually rules from, so the SAME predicate must run over it.
from analyze_g2 import guidance_verdict_is_escorted  # noqa: E402

F4 = HERE.parent
LABELS = F4 / "labels_e2_v1.parquet"
CHUNKS = F4 / "chunks_v1.parquet"
ARMS = F4 / "g2_draw_arms.csv"          # sidecar, outside this directory (§5.1)
OUT = HERE / "OWNER_RULING_PACKET.md"

GATE = ("sentiment", "guidance_direction")
APPLICABLE = {"sentiment": {"MDA", "EX99_PRESS_RELEASE"},
              "guidance_direction": {"EX99_PRESS_RELEASE"}}
Z = 1.96


def pct(x):
    return f"{100 * x:.2f}%"


def a8_scan(text, label):
    """§6.3 / ruling (vii) OPTION 1, ported to the PACKET (A8 equivalent).

    analyze_g2.py's A8 scans report_g2.md and results_g2.json only. The packet is
    the artifact the owner rules from and had no such guard, so it could drift
    out of compliance with nothing to catch it. Line-by-line, same predicate.
    """
    bad = [ln for ln in text.splitlines() if not guidance_verdict_is_escorted(ln)]
    assert not bad, (
        f"A8_PACKET ({label}): a guidance verdict is stated without "
        "guidance_active_precision AND guidance_false_none_rate on the same line "
        f"(§6.3 / ruling (vii) Option 1):\n  " + "\n  ".join(b[:240] for b in bad[:5]))


def a8_negative_test():
    """A guard that cannot be shown to FIRE is not a guard.

    Runs on every build, before the real scan, on the exact row shape the packet
    emits. Asserts the guard passes WITH the escort and fires WITHOUT it.
    """
    escorted = ("| `guidance_direction` | 115 / 119 | 109 | 93 | 3 | 115-118 | PASS "
                "only. Never quotable alone (ruling (vii)): guidance_active_precision "
                "68.67% [58.17%, 77.55%]; guidance_false_none_rate 0/80 = 0.00% |")
    stripped = escorted.split(". Never quotable")[0] + " |"
    assert guidance_verdict_is_escorted(escorted), \
        "A8_PACKET negative test broken: the guard rejects a correctly escorted row"
    assert not guidance_verdict_is_escorted(stripped), \
        "A8_PACKET negative test FAILED TO FIRE: the guard accepted a guidance " \
        "verdict row with the escort removed — the guard is not guarding"
    # and it must fire through a8_scan(), not only through the predicate
    try:
        a8_scan(stripped, "negative-test")
    except AssertionError:
        return True
    raise AssertionError("A8_PACKET negative test FAILED TO FIRE via a8_scan()")


def wilson_p(p, n, z=Z):
    """§10.0 Wilson with p supplied instead of k/n (used for the G-A n_eff CI)."""
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def ga_pooled(by_dir, weights):
    """§14.4 corpus re-weighted quota estimator: (point, lo, hi, n_eff)."""
    p = sum(weights[d] * k / n for d, (k, n) in by_dir.items())
    pt_d = {d: (k + Z * Z / 2) / (n + Z * Z) for d, (k, n) in by_dir.items()}
    var = sum(weights[d] ** 2 * pt_d[d] * (1 - pt_d[d]) / by_dir[d][1] for d in by_dir)
    pt = sum(weights[d] * pt_d[d] for d in by_dir)
    n_eff = pt * (1 - pt) / var
    lo, hi = wilson_p(p, n_eff)
    return p, lo, hi, n_eff


def load_all():
    res = json.loads((HERE / "results_g2.json").read_text())
    adj = json.loads((HERE / "adjudications" / "adjudications.json").read_text())
    probe = json.loads((HERE / "probe_ids.json").read_text())
    contested = {}   # (chunk_id, field) -> {text, stored_label, rater_label}
    for f in sorted((HERE / "adjudicator_batches").glob("adj_batch_*.json")):
        for r in json.loads(f.read_text()):
            contested[(r["chunk_id"], r["field"])] = r
    rater, text = {}, {}
    for f in sorted((HERE / "verdicts").glob("rater_a_batch*.json")):
        for r in json.loads(f.read_text()):
            rater[r["chunk_id"]] = r
    for f in sorted((HERE / "batches").glob("batch_*.json")):
        if "replicate" in f.name:
            continue
        for r in json.loads(f.read_text()):
            text[r["chunk_id"]] = r["text"]
    arm = dict(pd.read_csv(ARMS).itertuples(index=False, name=None))
    ch = pd.read_parquet(CHUNKS, columns=["chunk_id", "section_type"])
    sec = dict(ch[ch.chunk_id.isin(arm)].itertuples(index=False, name=None))
    lab = pd.read_parquet(LABELS, columns=["chunk_id", "sentiment", "guidance_direction",
                                           "guidance_imputed_none"])
    stored = {r["chunk_id"]: r for r in lab[lab.chunk_id.isin(arm)].to_dict("records")}
    return res, adj, probe, contested, rater, text, arm, sec, stored


def sweep_size(rater, arm, sec, stored):
    """Realized size of the §5.5 escalation sweep: (chunks, (chunk,field) rows).

    Same predicate as probe_ids.json's frame: >=1 applicable gate-bearing field,
    rater matched the stored value on every one of them.
    """
    chunks, pairs = 0, 0
    for cid in arm:
        fields = [f for f in GATE if sec[cid] in APPLICABLE[f]]
        if not fields:
            continue
        sv = {f: (stored[cid][f] if isinstance(stored[cid][f], str) else None)
              for f in fields}
        if all(sv[f] == rater[cid].get(f) for f in fields):
            chunks += 1
            pairs += len(fields)
    return chunks, pairs


def movability(field, res, needs_human, arm, sec):
    """What Part A rulings can do to this field's primary, in k units.

    A STORED-RIGHT ruling on a row the adjudicator overturned moves k UP 1.
    An OTHER ruling on a row the adjudicator upheld moves k DOWN 1.
    Rows outside the P arm are not in the primary base at all.
    """
    pr = res["primary"][field]
    base = [r for r in needs_human
            if r["field"] == field and arm[r["chunk_id"]] == "P"
            and sec[r["chunk_id"]] in APPLICABLE[field]]
    up = sum(1 for r in base if r["verdict"] == "disagree")
    down = sum(1 for r in base if r["verdict"] == "agree")
    off = sum(1 for r in needs_human if r["field"] == field) - len(base)
    return dict(k=pr["k"], n=pr["n"], kpass=pr["kstar_pass"], kfail=pr["kstar_fail"],
                verdict=pr["verdict"], n_base=len(base), up=up, down=down, off=off,
                k_max=pr["k"] + up, k_min=pr["k"] - down,
                need_pass=pr["kstar_pass"] - pr["k"],
                need_fail=pr["k"] - pr["kstar_fail"])


def sentiment_error_structure(res):
    """The COMPOSITION of the 86.65% headline (results_g2.json secondaries['S-ERR']).

    Nothing is recomputed here: S-ERR was computed and stored on the first run and
    simply never reached an owner-facing surface. A single agreement proportion
    over a 3-value field hides which value carries it, and the surviving E2
    features consume the per-value quantities, not the pooled one.
    """
    s = res["secondaries"]["S-ERR"]["sentiment"]
    cm = s["confusion_stored_x_reference"]
    by_st, hit = Counter(), Counter()
    for key, v in cm.items():
        a, b = key.split("->")
        by_st[a] += v
        if a == b:
            hit[a] += v
    n_scored = sum(cm.values())
    n_om = s.get("n_omitted", 0)
    n_err = n_scored - sum(hit.values()) + n_om
    to_neutral = sum(v for k, v in cm.items()
                     if k.split("->")[0] != k.split("->")[1]
                     and k.split("->")[1] == "NEUTRAL")
    return {"cm": cm, "by_st": by_st, "hit": hit, "n_scored": n_scored,
            "n_om": n_om, "n_err": n_err, "to_neutral": to_neutral}


# The three adjudicator slugs that are one and the same rubric question:
# a quantified forward outlook carrying no explicit revision language.
FRESH_GUIDANCE_SLUGS = ("fresh-quantified-guidance-no-prior-comparison",
                        "quantified-outlook-without-revision-language",
                        "new-or-initiated-guidance-not-raised")

# G-N coupling probe. Deliberately over-inclusive lexical screens, stated in full
# so the owner can see exactly what was counted; they are an upper bound on
# exposure, not a judgement about any chunk.
_GN_VOCAB = re.compile(
    r"\b(outlook|guidance|expects?|expected|anticipat\w*|forecast\w*)\b", re.I)
_GN_FWD = re.compile(
    r"\b((?:the\s+)?[Cc]ompany|[Ww]e|management)\s+(?:currently\s+|now\s+|continues?\s+"
    r"to\s+)?(?:expects?|anticipates?|projects?|forecasts?|sees|estimates?)\b"
    r"|\bexpects?\s+to\b|\bis\s+expected\s+to\b|\bexpected\s+to\s+be\b", re.I)
_GN_NUM = re.compile(
    r"(\$\s?\d[\d,\.]*\s?(?:billion|million|thousand)?"
    r"|\d[\d,\.]*\s?(?:%|percent)|\bper\s+share\b)", re.I)


def gn_coupling_bound(arm, text, window=200):
    """Bound the G-N arm's exposure to the same unresolved rubric convention.

    G-N had ZERO contested rows, so it was never adjudicated: the 0/80 was
    produced by the same blind rater applying the same convention that produced
    G-A's 27 errors. The coupling is therefore not zero and it should not be
    presented as if it were. This screens the 80 G-N passages lexically to bound
    how many rows a convention reversal could plausibly reach.
    """
    gn = sorted(c for c, a in arm.items() if a == "G-N")
    vocab = [c for c in gn if c in text and _GN_VOCAB.search(text[c])]
    near = []
    for c in gn:
        t = text.get(c, "")
        for m in _GN_FWD.finditer(t):
            if _GN_NUM.search(t[max(0, m.start() - window):m.end() + window]):
                near.append(c)
                break
    return {"n_gn": len(gn), "n_vocab": len(vocab), "n_near": len(near),
            "near_ids": near, "window": window}


def main():
    res, adj, probe, contested, rater, text, arm, sec, stored = load_all()
    a8_negative_test()
    assert res["stage"] == "model_consensus", res["stage"]
    needs_human = [r for r in adj if r.get("needs_human")]
    assert not any(r["field"] == "red_flags" for r in needs_human), \
        "red_flags never escalates to the owner (§5.3)"
    gap = res["guidance_active_precision"]
    gnr = res["guidance_false_none_rate"]
    noise = res["secondaries"]["S-NOISE"]
    rf1, rf2 = res["secondaries"]["S-RF1"], res["secondaries"]["S-RF2"]
    mov = {f: movability(f, res, needs_human, arm, sec) for f in GATE}

    ga_line = (f"guidance_active_precision {pct(gap['point'])} "
               f"95% Wilson [{pct(gap['wilson_lo'])}, {pct(gap['wilson_hi'])}] "
               f"(corpus-re-weighted; n_eff {gap['n_eff']:.1f} of nominal n {gap['n_nominal']})")
    gn_line = (f"guidance_false_none_rate {gnr['k']}/{gnr['n']} = {pct(gnr['p_hat'])} "
               f"95% Wilson [{pct(gnr['wilson_lo'])}, {pct(gnr['wilson_hi'])}]")
    head = {}
    for f in GATE:
        p = res["primary"][f]
        line = (f"**`{f}` — bar {p['bar']}: {p['k']}/{p['n']} = {pct(p['p_hat'])} "
                f"95% Wilson [{pct(p['wilson_lo'])}, {pct(p['wilson_hi'])}] "
                f"-> {p['verdict']}**")
        if f == "guidance_direction":
            line += f"  ||  {ga_line}  ||  {gn_line}"
        head[f] = line

    # G-A: the escort the owner's rulings can actually move (§14.4 re-weighting).
    by_dir = {d: (v["k"], v["n"])
              for d, v in res["guidance_active_precision_by_direction"].items()}
    w = gap["weights"]
    ga_up, ga_down = {}, {}
    for r in needs_human:
        if r["field"] != "guidance_direction" or arm[r["chunk_id"]] != "G-A":
            continue
        d = contested[(r["chunk_id"], r["field"])]["stored_label"]
        bucket = ga_up if r["verdict"] == "disagree" else ga_down
        bucket[d] = bucket.get(d, 0) + 1
    hi_dir = {d: (k + ga_up.get(d, 0), n) for d, (k, n) in by_dir.items()}
    lo_dir = {d: (k - ga_down.get(d, 0), n) for d, (k, n) in by_dir.items()}
    ga_hi = ga_pooled(hi_dir, w)
    ga_lo = ga_pooled(lo_dir, w)
    n_ga_rows = sum(ga_up.values()) + sum(ga_down.values())

    L = []
    A = L.append
    utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    A(f"# G2 — OWNER RULING PACKET (generated {utc}) — MODEL-CONSENSUS stage\n")
    A(f"> {res['provenance']}\n>\n> Everything below is **model consensus** — a blind "
      "Claude-family rater plus a Claude-family adjudicator, scored mechanically. "
      "It is not your judgment and it is not human validation of ground truth. "
      "It becomes the owner-ratified stage only where you rule.\n")
    A("Rule on the merits. The bars (0.85, both gate-bearing fields), the k\\* "
      "boundaries and the escalation trigger were pinned on 2026-09-07 **before** any "
      "chunk was rated (design §14.6); the arithmetic below is printed so the "
      "consequence of a ruling is visible, not so it can be aimed at.\n")

    A("## The two gate-bearing primaries (verbatim, `results_g2.json`, "
      f"stage `{res['stage']}`, generated {res['generated_utc']})\n")
    A(head["sentiment"] + "\n")
    # BLOCKING FIX: the headline's composition, beside the headline. Same numbers
    # as results_g2.json secondaries['S-ERR'] — nothing recomputed.
    se = sentiment_error_structure(res)
    A(f"  - **What the 86.65% is made of** (`results_g2.json` → `secondaries['S-ERR']`, "
      f"stored (student) → reference (adjudicated), P arm, {se['n_scored']} scored + "
      f"{se['n_om']} omission-pinned nulls): "
      + "; ".join(f"{k} {v}" for k, v in sorted(se["cm"].items())) + ".")
    A("  - **Precision on each stored value** (rows the reference upheld): "
      + "; ".join(f"**{s} {se['hit'][s]}/{se['by_st'][s]} = "
                  f"{100 * se['hit'][s] / se['by_st'][s]:.1f}%**"
                  for s in sorted(se["by_st"])) + ".")
    A(f"  - **Read this beside the headline.** {se['to_neutral']} of the {se['n_err']} "
      "sentiment errors are the student asserting a DIRECTION on a passage the reference "
      f"calls NEUTRAL. NEUTRAL is {se['by_st']['NEUTRAL']}/{se['n_scored']} = "
      f"{100 * se['by_st']['NEUTRAL'] / se['n_scored']:.0f}% of the scored base and is "
      f"upheld {100 * se['hit']['NEUTRAL'] / se['by_st']['NEUTRAL']:.1f}% of the time, so "
      "the pooled figure is carried by the NEUTRAL mass — structurally the same NONE-mass "
      "problem the whole G-A arm was bought to expose for guidance. The two surviving E2 "
      "sentiment features are `sentiment_mean_score` and `sentiment_negative_share`, and "
      f"**`sentiment_negative_share` consumes exactly the stored-NEGATIVE quantity "
      f"measured at {se['hit']['NEGATIVE']}/{se['by_st']['NEGATIVE']} = "
      f"{100 * se['hit']['NEGATIVE'] / se['by_st']['NEGATIVE']:.1f}% precision.** This "
      "is disclosure, not a bar: no per-value figure carries a bar and none can move the "
      "verdict.\n")
    A(head["guidance_direction"] + "\n")
    A(f"- ceiling (S-NOISE, **two independent runs of the same Claude-family blind rater** "
      "— same agent card `.claude/agents/label-rater-blind.md`, same model family, same "
      "prompt, on byte-identical files in identical row order; it is a run-to-run "
      "reproducibility figure, NOT an instrument validation and NOT two independent "
      f"instruments; **cannot move "
      f"any bar**): sentiment {noise['sentiment']['k']}/{noise['sentiment']['n']} = "
      f"{pct(noise['sentiment']['p_hat'])} [{pct(noise['sentiment']['wilson_95'][0])}, "
      f"{pct(noise['sentiment']['wilson_95'][1])}]; guidance "
      f"{noise['guidance_direction']['k']}/{noise['guidance_direction']['n']} = "
      f"{pct(noise['guidance_direction']['p_hat'])} "
      f"[{pct(noise['guidance_direction']['wilson_95'][0])}, "
      f"{pct(noise['guidance_direction']['wilson_95'][1])}]; red_flags "
      f"{noise['red_flags']['k']}/{noise['red_flags']['n']} = "
      f"{pct(noise['red_flags']['p_hat'])} [{pct(noise['red_flags']['wilson_95'][0])}, "
      f"{pct(noise['red_flags']['wilson_95'][1])}]. Both gate-bearing ceilings' **lower** "
      "bounds clear 0.85, so §6.4 fact 3 (a bar above the instrument's own ceiling) does "
      "**not** fire on this draw. The ceiling is UPPER-biased by an unmeasured amount: "
      "raters A and B saw byte-identical files in the same row order, so any ordering or "
      "context effect is shared (§14.9).")
    sw = res["adjudication_layer"]["sided_with_rater_against_stored"]
    A("- **the third rater, measured** (descriptive; no bar; moves nothing): the "
      "adjudicator sided with the blind rater **against** the stored student label on "
      f"{sw['overall']['k']}/{sw['overall']['n']} = {pct(sw['overall']['p_hat'])} of "
      "contested rows — "
      + "; ".join(f"{f} {v['k']}/{v['n']} = {pct(v['p_hat'])}"
                  for f, v in sorted(sw["by_field"].items()))
      + ". Read it beside the ceiling immediately above: the Claude family agrees with "
        "itself run-to-run at 97–98% and goes against the Qwen student on ~86% of the "
        "rows it is asked to arbitrate. That is consistent with the adjudicator "
        "correctly finding student error AND with within-family agreement, and **this "
        "design cannot separate the two** — which is exactly why §12.1 calls the "
        "estimate plausibly optimistic. It is a free disclosure, not a defect.\n")
    A(f"- `red_flags` — **disclosure-only, exploratory** (your 2026-08-27 ruling; this "
      f"pass cannot change it, and no red-flag row escalates to you): exact-set "
      f"(category+modality) error {rf1['k']}/{rf1['n']} = {pct(rf1['p_hat'])} "
      f"[{pct(rf1['wilson_lo'])}, {pct(rf1['wilson_hi'])}]; per-category-decision error "
      f"{rf2['k']}/{rf2['n_decisions']} = {pct(rf2['p_hat'])} "
      f"[{pct(rf2['cluster_bootstrap_95'][0])}, {pct(rf2['cluster_bootstrap_95'][1])}] "
      f"(chunk-clustered bootstrap over {rf2['n_chunks']} chunks; the naive binomial "
      "interval is anti-conservative and is not the one quoted). Exact-set and "
      "per-category are different bases and are never quoted as each other.\n")

    A("### §6.6 — what a non-FAIL does not mean (pre-registered wording, verbatim)\n")
    for f in GATE:
        A(f"> **{f}.** {res['non_fail_wording'][f]}\n")

    A("### What your Part A rulings can and cannot move (arithmetic)\n")
    A("A STORED-RIGHT ruling on a row the adjudicator overturned moves that field's k "
      "**up 1**; an OTHER ruling on a row the adjudicator upheld moves it **down 1**; an "
      "ADJUDICATOR-RIGHT ruling changes nothing. Only rows in the **P (base-rate) arm** "
      "sit in a primary's denominator — G-A and G-N rows move the guidance escorts "
      "instead, and n never changes (0 unsure, 0 unadjudicated on both primaries).\n")
    A("| field | k / n | k\\* PASS | k\\* FAIL | Part A rows in this base | reachable k | "
      "verdicts attainable across every combination of Part A rulings |")
    A("|---|---|---|---|---|---|---|")
    for f in GATE:
        m = mov[f]
        attainable = {("PASS" if k >= m["kpass"] else
                       "DECISIVE FAIL" if k <= m["kfail"] else "INDETERMINATE")
                      for k in range(m["k_min"], m["k_max"] + 1)}
        cell = " / ".join(sorted(attainable))
        if len(attainable) == 1:
            cell += f" only — **the verdict cannot change**"
        if f == "guidance_direction":
            # Ruling (vii) Option 1 / design §10.2.7 item 8 bind the guidance
            # verdict WHEREVER it is written. This row names the field beside a
            # verdict marker, so the two escorts ride in the same cell — a
            # footnote on another line would not satisfy the line-scan guard.
            cell += (f". Never quotable alone (ruling (vii)): {ga_line}; {gn_line}")
        A(f"| `{f}` | {m['k']} / {m['n']} | {m['kpass']} | {m['kfail']} | "
          f"{m['n_base']} ({m['up']} up-movable, {m['down']} down-movable; "
          f"{m['off']} more sit outside this base) | {m['k_min']}–{m['k_max']} | "
          f"{cell} |")
    A("")
    ms = mov["sentiment"]
    A(f"- **`sentiment` is INDETERMINATE at {ms['k']}/{ms['n']} and no combination of Part "
      f"A rulings changes that.** PASS needs k ≥ {ms['kpass']}, i.e. {ms['need_pass']} more "
      f"agreements; only **{ms['up']}** of the 11 escalated sentiment rows sit in the P base "
      f"with an overturn to reverse, so ruling **all** of them STORED-RIGHT reaches "
      f"k = {ms['k_max']} — still {ms['kpass'] - ms['k_max']} short. **PASS is not "
      f"reachable.** DECISIVE FAIL needs k ≤ {ms['kfail']}, i.e. {ms['need_fail']} more "
      f"errors; only **{ms['down']}** rows can be moved down, floor k = {ms['k_min']}. "
      f"**FAIL is not reachable either.** The other {ms['off']} escalated sentiment rows are "
      "in the G-A / G-N arms and are outside the sentiment primary's base entirely. "
      f"{res['primary']['sentiment']['n_omission_pinned_errors']} of the "
      f"{ms['n'] - ms['k']} errors are pre-registered omission errors (the student emitted "
      "no sentiment, §1.3) and are not adjudicable by anyone.")
    mg = mov["guidance_direction"]
    A(f"- **`guidance_direction` is PASS at {mg['k']}/{mg['n']} ({ga_line}; {gn_line}) and "
      f"no combination of Part A rulings changes that either.** k ranges {mg['k_min']}–"
      f"{mg['k_max']} across all {2 ** mg['n_base']} combinations of the {mg['n_base']} "
      f"P-arm rows, and the floor {mg['k_min']} is still ≥ k\\* PASS {mg['kpass']}. Losing "
      f"the PASS would take {mg['k'] - mg['kpass'] + 1} more errors, and Part A offers "
      f"{mg['down']} rows that could add one (all {mg['n_base']} P-arm guidance rows are "
      "already scored as errors).")
    A(f"- **Where your rulings do bite: the G-A escort.** {n_ga_rows} of the {len(needs_human)} "
      f"Part A rows are G-A active-guidance rows, and they carry "
      f"{sum(ga_up.values())} of G-A's "
      f"{gap['n_applicable'] - sum(k for k, _ in by_dir.values())} errors. Ruling every one "
      f"STORED-RIGHT takes the corpus-re-weighted active precision from "
      f"{pct(gap['point'])} [{pct(gap['wilson_lo'])}, {pct(gap['wilson_hi'])}] to "
      f"{pct(ga_hi[0])} [{pct(ga_hi[1])}, {pct(ga_hi[2])}] (n_eff {ga_hi[3]:.1f}); ruling "
      f"the upheld row OTHER takes it to {pct(ga_lo[0])} [{pct(ga_lo[1])}, "
      f"{pct(ga_lo[2])}] (n_eff {ga_lo[3]:.1f}). This is the number the guidance verdict "
      "may never be quoted without (ruling (vii), Option 1), and it carries no bar. "
      f"**G-N has 0 Part A rows**, so the false-NONE rate stays {gnr['k']}/{gnr['n']} "
      "mechanically whatever you rule here — but see the coupling note directly below; "
      "that is an arithmetic fact about this packet, not a substantive reassurance.")

    # ---- the single rubric question underneath G-A's 68.67%, named.
    ga_err = [r for r in adj
              if r["field"] == "guidance_direction" and arm[r["chunk_id"]] == "G-A"
              and r["verdict"] == "disagree"]
    n_ga_err = len(ga_err)
    n_none = sum(1 for r in ga_err if r["correct_label"] == "NONE")
    slugc = Counter(r["pattern"] for r in ga_err)
    n_fresh = sum(slugc.get(s, 0) for s in FRESH_GUIDANCE_SLUGS)
    # Re-derived, never hardcoded: P-arm rows inside the guidance primary's base
    # whose stored NONE came from the §1.3 writer rule rather than an emitted value.
    n_imputed_none = sum(
        1 for c, a in arm.items()
        if a == "P" and sec[c] in APPLICABLE["guidance_direction"]
        and bool(stored[c].get("guidance_imputed_none")))
    gnb = gn_coupling_bound(arm, text)
    lo_b, hi_b = wilson_p(gnb["n_near"] / gnb["n_gn"], gnb["n_gn"])
    A(f"- **What the {pct(gap['point'])} active precision is mostly measuring: an "
      f"unresolved RUBRIC question, not the student.** Of G-A's {n_ga_err} errors, "
      f"{n_none} resolve to `correct_label = NONE`, and **{n_fresh} of the {n_ga_err} sit "
      "in three adjudicator slugs that are all one and the same question** — "
      + "; ".join(f"`{s}` ({slugc.get(s, 0)})" for s in FRESH_GUIDANCE_SLUGS)
      + ": *a quantified forward outlook issued with no explicit revision language.* "
      "Design §3.3 already records that rubric §3's preamble names \"issue new guidance\" "
      "as a case for which the label set offers **no value**. So this is substantially a "
      "measurement of a rubric gap, and it moves to "
      f"{pct(ga_hi[0])} [{pct(ga_hi[1])}, {pct(ga_hi[2])}] on a single convention ruling "
      "by you. The rubric gap is the thing to rule on; the percentage is downstream of it.")
    A(f"- **The same convention is load-bearing in two other places, and this is "
      f"disclosed rather than left implicit.** (1) The {n_imputed_none} "
      "`guidance_imputed_none` rows inside the guidance primary are scored AS NONE by the "
      "same writer rule. (2) **G-N had zero contested rows, so G-N was never adjudicated "
      "at all** — its 0/80 was produced by the same blind rater applying the same "
      f"convention. Measured bound on that coupling, re-derived here from the {gnb['n_gn']} "
      f"G-N passages: {gnb['n_vocab']} contain any of outlook / guidance / expect / "
      f"anticipate / forecast, and only **{gnb['n_near']} of {gnb['n_gn']}** place a "
      "company-subject forward-expectation phrase within "
      f"{gnb['window']} characters of a quantified figure "
      f"(≈{100 * gnb['n_near'] / gnb['n_gn']:.1f}%, Wilson [{pct(lo_b)}, {pct(hi_b)}]) — "
      "and on inspection those are a tax-refund timing, a buyback execution timing, and a "
      "forward restructuring-charge estimate, none of them a financial-performance "
      "outlook. **A convention reversal could therefore plausibly move G-N from 0/80 to at "
      "most about 3/80; it could not invert it.** The screen is deliberately "
      "over-inclusive and is an upper bound on exposure, not a judgement about any chunk.")
    A("- The only mechanism in this packet that can move either verdict is **Part B**: "
      "≥ 2 of 20 overturns fires the pre-committed sweep of the uncontested set, which can "
      "only add errors (it re-checks rows currently scored as agreements).\n")

    # ---------------------------------------------------------------- PART A
    order, groups = [], {}
    for r in needs_human:
        groups.setdefault(r["pattern"], []).append(r)
    for pat in sorted(groups, key=lambda p: (-len(groups[p]), p)):
        order.append(pat)
    A(f"## PART A — the {len(needs_human)} `needs_human` rows "
      f"({len(order)} pattern slugs)\n")
    A("Grouped by the adjudicator's pattern slug; where a pattern repeats, one ruling can "
      "settle the group — say so in the note and the rest can follow it. Every row: rule "
      "**STORED-RIGHT** (the student's stored label is right) / **ADJUDICATOR-RIGHT** (the "
      "adjudicator's `correct_label` is right) / **OTHER** (give the label). On the "
      f"{sum(1 for r in needs_human if r['verdict'] == 'agree')} rows where the adjudicator "
      "**upheld** the stored label the two are the same ruling — only OTHER moves those.\n")
    i = 0
    for pat in order:
        rows = sorted(groups[pat], key=lambda r: r["chunk_id"])
        A(f"### pattern `{pat}` — {len(rows)} row(s)\n")
        for r in rows:
            i += 1
            cid, fld = r["chunk_id"], r["field"]
            cb = contested[(cid, fld)]
            A(f"#### A{i}. `{cid}`  ·  field `{fld}`  ·  arm {arm[cid]}")
            # Honest labelling of owner attention: a sentiment row in G-A or G-N
            # is outside the sentiment primary (P-only, n=337), outside every
            # sentiment secondary (all computed on P), and outside S-NOISE (rater
            # A vs rater B, no adjudications). Ruling it changes no number
            # anywhere. It is kept only so the escalated set is complete.
            if fld == "sentiment" and arm[cid] != "P":
                A("> **This ruling enters NO reported estimate.** The sentiment primary "
                  "is P-arm only, every sentiment secondary is computed on P, and "
                  "S-NOISE uses rater A vs rater B without adjudications. This row is "
                  "in an off-primary arm and is included solely so the escalated set "
                  "is complete — rule it or skip it, no number moves either way.")
            A(f"**Stored (student):** `{cb['stored_label']}`  ")
            A(f"**Rater (blind):** `{cb['rater_label']}`  ")
            A(f"**Adjudicator ({r['verdict']}, {r['confidence']} confidence):** "
              f"`{r['correct_label']}`")
            A(f"**Adjudicator brief:** {r['brief']}")
            A(f"**Rater's reason (its own words, written before it saw any stored label):** "
              f"{rater[cid].get('reason', '')}")
            A(f"<details><summary>chunk text ({len(text[cid])} chars)</summary>\n")
            A("```")
            A(text[cid])
            A("```")
            A("</details>\n")
            A("**RULE:** STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER (give the label)\n")

    # ---------------------------------------------------------------- PART B
    pids = probe["chunk_ids"]
    strat = " / ".join(f"{probe['realized_stratification'][a]} {a}"
                       for a in ("P", "G-A", "G-N"))
    n_sweep_chunks, n_sweep_pairs = sweep_size(rater, arm, sec, stored)
    assert n_sweep_chunks == probe["frame_size"], (n_sweep_chunks, probe["frame_size"])
    A(f"## PART B — the {len(pids)}-row S-PROBE of the UNCONTESTED set\n")
    A(f"These are rows where the blind rater independently produced **the same** label as "
      f"the student on every applicable gate-bearing field, drawn seeded "
      f"({probe['seed']}) by pinned code after rating from the {probe['frame_size']} "
      f"eligible rows — realized {strat}. They are the design's only "
      "non-model check: the protocol only ever re-examines disagreements, so rows where "
      "student and rater are wrong the same way are otherwise invisible (§5.5). Rule "
      "**AGREE** or **OVERTURN** against the stored label shown.\n")
    A(f"**The trigger and its price.** If **≥ 2 of {len(pids)}** are overturned, the one "
      "pre-committed extension fires: every uncontested row with an applicable "
      "gate-bearing field goes to the adjudicator once on those fields and the primaries "
      f"are recomputed. Realized size of that sweep, re-derived here: "
      f"**{n_sweep_chunks} chunks = {n_sweep_pairs} (chunk, field) rows → "
      f"{math.ceil(n_sweep_pairs / 40)} adjudicator batches** at the pinned ≤ 40 "
      "rows/batch (the design modelled ~10 runs at §14.7 and ~7 at §5.5, on chunk counts "
      "and on expected rather than realized numbers). New disagreements it produces become "
      "new `needs_human` rows for you — §14.7 models **~+19 owner items, band 0–38**. It "
      "adds no chunks, no API calls, and fires at most once. Probe rulings themselves never "
      "enter a primary; only the sweep they trigger does.\n")
    for j, cid in enumerate(pids, 1):
        labels = {f: stored[cid][f] for f in GATE if sec[cid] in APPLICABLE[f]}
        shown = "; ".join(f"`{f}` = `{v}`" for f, v in labels.items())
        A(f"### B{j}. `{cid}`")
        A(f"**Stored (= rater-agreed), gate-bearing fields applicable to this passage:** "
          f"{shown}")
        A(f"<details><summary>chunk text ({len(text[cid])} chars)</summary>\n")
        A("```")
        A(text[cid])
        A("```")
        A("</details>\n")
        A("**RULE:** AGREE / OVERTURN\n")

    # ---------------------------------------------------------------- FOOTER
    A("## HOW TO RECORD\n")
    A("Two files, in this directory, exactly these key sets (§10.2.3 — `analyze_g2.py` "
      "hard-fails on anything else):\n")
    A("`data/f4/g2/owner_rulings.json` — one object per PART A row you rule:\n")
    A("```json\n[\n  {\n    \"chunk_id\": \"E2CHK-...\",\n    \"field\": \"sentiment\","
      "\n    \"correct_label\": \"NEUTRAL\",\n    \"note\": \"owner ruling 2026-09-07 (A1): "
      "...\"\n  }\n]\n```\n")
    A("`correct_label` **is** the reference: put the stored label there for STORED-RIGHT, "
      "the adjudicator's `correct_label` for ADJUDICATOR-RIGHT, or your own value for "
      "OTHER. There is no verdict word. A `red_flags` row in this file is a hard failure "
      "(§5.3: red_flags never escalates).\n")
    A("`data/f4/g2/probe_rulings.json` — one object per PART B row:\n")
    A("```json\n[\n  {\n    \"chunk_id\": \"E2CHK-...\",\n    \"ruling\": \"agree\","
      "\n    \"note\": \"owner ruling 2026-09-07\"\n  }\n]\n```\n")
    A("`ruling` ∈ `{agree, disagree}` — `disagree` = OVERTURN.\n")
    A("Then re-run, from the repo root:\n")
    A("```\npython3 data/f4/g2/analyze_g2.py\n```\n")
    A("It re-reads both files, restamps the stage as `owner_ratified`, and regenerates "
      "`results_g2.json` / `report_g2.md`. If ≥ 2 probe rows are overturned, run the one "
      "pre-committed sweep (§5.5) and re-run it once more; the stage then reads "
      "`owner_ratified_escalated`.\n")
    A("**Until you rule, every number in this packet is model consensus** — a Claude-family "
      "rater and a Claude-family adjudicator agreeing with (or overturning) a Qwen student, "
      "scored mechanically against rubric v1.2 as your 2026-08-27 policy rulings interpret "
      "it. It is not human validation of ground truth, and the estimate is plausibly "
      "optimistic for the reason in §12.1: the rater's family is the teacher's family, so "
      "teacher error the student memorized is invisible to it. Your rulings supersede the "
      "adjudicator on exactly the rows you rule, and nothing else changes.\n")

    packet = "\n".join(L)
    # A8 EQUIVALENT, over the generated packet text — the artifact the owner
    # actually rules from. The negative test above proved this guard can fire.
    a8_scan(packet, "OWNER_RULING_PACKET.md")
    OUT.write_text(packet)
    print(f"wrote {OUT}  ({len(needs_human)} PART A rows / {len(order)} patterns / "
          f"{len(pids)} PART B rows, {OUT.stat().st_size} bytes) "
          "[A8_PACKET scan passed; negative test fired]")


if __name__ == "__main__":
    main()
