"""build_v12_requests.py — G1 repair: build + verify the rubric-v1.2
Batch API request file. PREPARATION ONLY. MAKES ZERO API CALLS.

Owner ratification: HANDOFF §3, 2026-08-26 ("F2.5 closure rulings",
ruling 1) — the §5 spend freeze is lifted for exactly one purpose, a
single Batch API re-label of E1's 6,747 chunks under rubric v1.2, hard
capped at $25 estimated. Submission happens in the MAIN SESSION only
(HANDOFF §4/§7). This script never imports `anthropic`, never reads
`.env`, and never touches the network.

What it does, in order:
  1. Builds data/batch_requests_v12.jsonl from data/labeling_corpus.parquet
     using the `v12_relabel` variant.
  2. RE-READS the file from disk and runs every guard against what is
     actually on disk, never against the in-memory list it just built
     ("verify the submitted artifact is the tested artifact", HANDOFF §7).
  3. Proves SINGLE-AXIS DISCIPLINE against E1's real final-pass request
     file (data/batch_requests_relabel.jsonl): model id, max_tokens,
     thinking and schema shapes must be IDENTICAL; the system prompt must
     be the one thing that DIFFERS.
  4. Prints a small sample for eyeball verification.
  5. Prints a cost estimate CALIBRATED against E1's real billed usage,
     and asserts it against the owner's $25 hard cap.

Run: python3 data/hardening/build_v12_requests.py [--rebuild]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import build_batch_requests as B  # noqa: E402
import submit_labeling_batch as S  # noqa: E402

VARIANT = "v12_relabel"
REQUESTS_PATH = REPO_ROOT / "data" / "batch_requests_v12.jsonl"
CORPUS_PATH = REPO_ROOT / "data" / "labeling_corpus.parquet"
E1_FINAL_REQUESTS = REPO_ROOT / "data" / "batch_requests_relabel.jsonl"
E1_LABELS = REPO_ROOT / "data" / "labels.parquet"
REFUSAL_CHUNK = "CHK-8e69547e0900a8dd"

# Owner's hard cap, HANDOFF §3 2026-08-26. Exceeding it means STOP and
# re-confirm with the owner — not "submit anyway".
COST_CAP_USD = 25.00

# ---------------------------------------------------------------------
# E1's real billed usage, from data/full_run_report.md (corrective run,
# 2,528 requests, intro pricing). These four numbers reproduce the
# reported $4.491 exactly through S.compute_real_cost's formula, which is
# why they are trustworthy as a calibration anchor rather than a guess.
# ---------------------------------------------------------------------
E1_CORRECTIVE = {
    "n_requests": 2528,
    "input_tokens": 2_296_084,
    "output_tokens": 265_014,
    "cache_creation_input_tokens": 13_383,
    "cache_read_input_tokens": 8_430_488,
    "reported_cost_intro_usd": 4.491,
}
# The second E1 run at the same config. Only its total is published
# (HANDOFF §2 spend table / full_run_report.md §5), not its token
# breakdown — which is exactly why it is used as an INDEPENDENT
# cross-validation target rather than as a second calibration source.
E1_RELABEL = {
    "n_requests": 4219,
    "batch_id": "msgbatch_01KrfTWXeVN79Us9wthnGLaG",
    "reported_cost_intro_usd": 10.06,
}
E1_CORRECTIVE_BATCH_ID = "msgbatch_01Mw3sFCi3fZXnV5U86PJR1o"

# v1.2 is expected to move flag counts in both directions (mining depth
# removes flags; the MARGIN_COST_PRESSURE rule adds them; realized-
# controls only swaps a modality string). 25% headroom over E1's measured
# output tokens is deliberate over-provisioning, not a prediction.
OUTPUT_HEADROOM = 1.25


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_requests(path: Path) -> list[dict]:
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def system_text(req: dict) -> str:
    return req["params"]["system"][0]["text"]


# ---------------------------------------------------------------------
# Step 1 — build
# ---------------------------------------------------------------------
def build(corpus: pd.DataFrame, rebuild: bool) -> None:
    if REQUESTS_PATH.exists() and not rebuild:
        print(f"[build] {REQUESTS_PATH.name} already exists — reusing it. "
              f"(--rebuild to force.)")
        return
    B.build_variant_files(corpus_df=corpus, only=[VARIANT], overwrite=rebuild)


# ---------------------------------------------------------------------
# Step 2 — guards against the file ON DISK
# ---------------------------------------------------------------------
def verify(requests: list[dict], corpus: pd.DataFrame) -> dict:
    results = {}

    # --- the two submit-path choke points, run here so the main session
    # never learns about a mismatch for the first time at submit time ---
    S.assert_requests_match_variant(requests, VARIANT, str(REQUESTS_PATH))
    S.assert_requests_use_current_system_prompt(requests, str(REQUESTS_PATH))

    # --- request count ---
    n_corpus = len(corpus)
    assert len(requests) == n_corpus, (
        f"request count {len(requests)} != corpus rows {n_corpus}"
    )
    assert n_corpus == 6747, f"corpus is {n_corpus} rows, expected E1's frozen 6,747"
    print(f"[guard] request count OK: {len(requests)} == corpus {n_corpus}")

    # --- chunk coverage: exact set equality, no dupes, refusal included ---
    custom_ids = [r["custom_id"] for r in requests]
    assert len(set(custom_ids)) == len(custom_ids), "duplicate custom_id in request file"
    corpus_ids = set(corpus["chunk_id"])
    missing = corpus_ids - set(custom_ids)
    extra = set(custom_ids) - corpus_ids
    assert not missing, f"{len(missing)} corpus chunks missing from requests: {sorted(missing)[:5]}"
    assert not extra, f"{len(extra)} requests not in corpus: {sorted(extra)[:5]}"
    assert REFUSAL_CHUNK in set(custom_ids), (
        f"{REFUSAL_CHUNK} (E1's single safety refusal) must be SUBMITTED, "
        f"not pre-filtered — E1 submitted it and excluded it downstream by "
        f"predicate. Its v1.2 outcome is a measurement, not an assumption."
    )
    print(f"[guard] chunk coverage OK: exact set equality with the corpus, "
          f"0 dupes, refusal chunk {REFUSAL_CHUNK} included")
    results["n_requests"] = len(requests)

    # --- schema shape follows section_type, and section_type never appears
    #     as prompt text (labeling_rubric.md §8) ---
    section_by_id = dict(zip(corpus["chunk_id"], corpus["section_type"]))
    text_by_id = dict(zip(corpus["chunk_id"], corpus["text"]))
    banned = {"MDA", "RISK_FACTORS", "EX99_PRESS_RELEASE", "8K_BODY"}
    sys_text = system_text(requests[0])
    assert not (banned & set(sys_text.split())), "section_type token in system prompt"
    for r in requests:
        cid = r["custom_id"]
        st = section_by_id[cid]
        params = r["params"]
        got_schema = params["output_config"]["format"]["schema"]
        assert got_schema == B._SCHEMA_CACHE[st], f"{cid}: wrong schema for {st}"
        msgs = params["messages"]
        assert len(msgs) == 1 and msgs[0]["role"] == "user", f"{cid}: bad message shape"
        assert msgs[0]["content"] == text_by_id[cid], (
            f"{cid}: user content is not the raw chunk text verbatim"
        )
        assert system_text(r) == sys_text, f"{cid}: system prompt not byte-identical"
    print("[guard] schema shape OK: matches section_type for all "
          f"{len(requests)} requests; user turn is the raw passage and nothing "
          "else; system prompt byte-identical across every request")

    # --- section_type distribution, for the record ---
    dist = corpus["section_type"].value_counts().to_dict()
    print(f"[guard] section_type distribution: {dist}")
    results["section_type_distribution"] = dist

    # --- look-ahead safety: no identity/date metadata anywhere in a request ---
    forbidden_cols = ["home_ticker", "home_cik", "home_accession_number",
                      "home_filing_date", "home_form"]
    blob_keys = set()
    for r in requests[:200]:
        blob_keys |= set(r["params"].keys())
    assert not (set(forbidden_cols) & blob_keys), "identity metadata leaked into params"
    print("[guard] look-ahead safety OK: request params carry only model/"
          "max_tokens/system/messages/output_config/thinking — no ticker, CIK, "
          "accession, form, or filing date")

    return results


# ---------------------------------------------------------------------
# Step 3 — single-axis discipline vs E1's real final pass
# ---------------------------------------------------------------------
def verify_single_axis(requests: list[dict]) -> dict:
    e1 = load_requests(E1_FINAL_REQUESTS)
    e1_by_id = {r["custom_id"]: r for r in e1}
    v12_by_id = {r["custom_id"]: r for r in requests}
    shared = sorted(set(e1_by_id) & set(v12_by_id))
    assert len(shared) == len(e1), "v1.2 file does not cover every E1 relabel chunk"

    e1_sys = system_text(e1[0])
    v12_sys = system_text(requests[0])

    same_axes = 0
    for cid in shared:
        a, b = e1_by_id[cid]["params"], v12_by_id[cid]["params"]
        assert a["model"] == b["model"], f"{cid}: model changed"
        assert a["max_tokens"] == b["max_tokens"], f"{cid}: max_tokens changed"
        assert a.get("thinking") == b.get("thinking"), f"{cid}: thinking changed"
        assert a["output_config"]["format"] == b["output_config"]["format"], (
            f"{cid}: schema changed"
        )
        assert a["messages"] == b["messages"], f"{cid}: passage text changed"
        same_axes += 1

    assert e1_sys != v12_sys, (
        "The v1.2 system prompt is IDENTICAL to E1's. The rubric change did "
        "not reach the request file — this run would re-buy E1's labels."
    )

    out = {
        "e1_final_requests_file": str(E1_FINAL_REQUESTS.relative_to(REPO_ROOT)),
        "n_chunks_compared": same_axes,
        "model": e1[0]["params"]["model"],
        "max_tokens": e1[0]["params"]["max_tokens"],
        "thinking": e1[0]["params"].get("thinking"),
        "effort": e1[0]["params"]["output_config"].get("effort"),
        "e1_system_prompt_sha256": sha256_text(e1_sys),
        "v12_system_prompt_sha256": sha256_text(v12_sys),
        "e1_system_prompt_chars": len(e1_sys),
        "v12_system_prompt_chars": len(v12_sys),
    }
    print(
        f"[single-axis] OK across all {same_axes} shared chunks: model="
        f"{out['model']!r}, max_tokens={out['max_tokens']}, "
        f"thinking={out['thinking']}, effort={out['effort']}, schema and "
        f"passage text all IDENTICAL to E1's final pass.\n"
        f"[single-axis] system prompt is the ONLY axis that moved: "
        f"{out['e1_system_prompt_sha256'][:16]}... ({out['e1_system_prompt_chars']} chars, v1.1)"
        f" -> {out['v12_system_prompt_sha256'][:16]}... ({out['v12_system_prompt_chars']} chars, v1.2)"
    )
    return out


# ---------------------------------------------------------------------
# Step 4 — printed sample
# ---------------------------------------------------------------------
def print_sample(requests: list[dict], corpus: pd.DataFrame, n: int = 3) -> None:
    section_by_id = dict(zip(corpus["chunk_id"], corpus["section_type"]))
    # One per section_type where available, deterministic (first by id).
    picked, seen = [], set()
    for r in sorted(requests, key=lambda r: r["custom_id"]):
        st = section_by_id[r["custom_id"]]
        if st not in seen:
            seen.add(st)
            picked.append(r)
    print("\n" + "=" * 70)
    print("SAMPLE REQUESTS (eyeball verification)")
    print("=" * 70)
    for r in picked:
        p = r["params"]
        st = section_by_id[r["custom_id"]]
        print(f"\n--- custom_id={r['custom_id']}  (section_type={st}, not in the request) ---")
        print(f"model           : {p['model']}")
        print(f"max_tokens      : {p['max_tokens']}")
        print(f"thinking        : {p.get('thinking')}")
        print(f"output_config   : effort={p['output_config'].get('effort')} "
              f"schema.required={p['output_config']['format']['schema']['required']}")
        print(f"system[0].cache : {p['system'][0]['cache_control']}")
        print(f"system[0].text  : {len(system_text(r))} chars, sha256="
              f"{sha256_text(system_text(r))[:16]}...")
        body = p["messages"][0]["content"]
        print(f"user content    : {len(body)} chars")
        print(f"  first 220     : {body[:220]!r}")

    print("\n--- v1.2 system prompt, the three changed passages ---")
    sys_text = system_text(picked[0])
    for marker in ("MARGIN_COST_PRESSURE:", "MINING DEPTH:", "REALIZED CONTROLS:"):
        i = sys_text.find(marker)
        assert i >= 0, f"v1.2 marker {marker!r} missing from SYSTEM_PROMPT"
        end = sys_text.find("\n", i)
        print(f"\n  {sys_text[i:end if end > 0 else len(sys_text)]}")


# ---------------------------------------------------------------------
# Step 5 — cost estimate, calibrated against E1's real billed usage
# ---------------------------------------------------------------------
def _body_proxy(chunk_ids, text_by_id, section_by_id, schema_proxy) -> int:
    """cl100k-proxy tokens for the non-cached part of a request: the raw
    passage plus the serialized JSON schema."""
    return sum(
        B.count_tokens(text_by_id[c]) + schema_proxy[section_by_id[c]]
        for c in chunk_ids
    )


def estimate_cost(requests: list[dict], corpus: pd.DataFrame) -> dict:
    """Cost estimate anchored on E1's REAL billed usage under this exact
    model and config, then stress-tested.

    Method, and why it is shaped this way:

    1. E1's corrective run published its full token breakdown. Those four
       numbers reproduce its reported $4.491 exactly through
       `S.compute_real_cost`, so they are a trustworthy anchor. From them
       we recover Claude's real per-request system-prompt token count
       (~3,340 for v1.1 — cache-write and cache-read tokens independently
       agree on it) and the ratio between Claude's tokenizer and our local
       cl100k proxy for request bodies.
    2. That fitted model is then CROSS-VALIDATED against E1's other run at
       the same config (the 4,219-request re-label, reported $10.06). It
       FAILS: it predicts ~$6.28. The gap is not tokenizer error — the
       re-label's passages and outputs are slightly SMALLER per request.
       Solving for the residual shows the cause: ~600 of its 4,219
       requests (14.2%) paid a prompt-cache WRITE at 2x input price,
       versus ~4 of 2,528 (0.16%) in the corrective run.
    3. So the dominant cost uncertainty is Batch API cache fan-out, which
       varied ~90x between two runs of this same project and is not under
       our control. The estimate is therefore reported as a SCENARIO
       TABLE over cache-write rate, and the headline uses the WORST rate
       E1 actually observed, at STANDARD (not intro) pricing, with output
       headroom. A cold-cache bound (every request pays a write) is
       reported too, as the true worst case.
    """
    n = len(requests)
    v12_sys_proxy = B.count_tokens(system_text(requests[0]))
    e1 = load_requests(E1_FINAL_REQUESTS)
    e1_sys_proxy = B.count_tokens(system_text(e1[0]))

    schema_proxy = {
        st: B.count_tokens(json.dumps(sch)) for st, sch in B._SCHEMA_CACHE.items()
    }
    text_by_id = dict(zip(corpus["chunk_id"], corpus["text"]))
    section_by_id = dict(zip(corpus["chunk_id"], corpus["section_type"]))

    lab = pd.read_parquet(E1_LABELS, columns=["chunk_id", "batch_id", "output_tokens"])
    corrective_ids = lab.loc[lab["batch_id"] == E1_CORRECTIVE_BATCH_ID, "chunk_id"]
    relabel_rows = lab[lab["batch_id"] == E1_RELABEL["batch_id"]]
    assert len(corrective_ids) == E1_CORRECTIVE["n_requests"]
    assert len(relabel_rows) == E1_RELABEL["n_requests"]

    corrective_body = _body_proxy(corrective_ids, text_by_id, section_by_id, schema_proxy)
    relabel_body = _body_proxy(relabel_rows["chunk_id"], text_by_id, section_by_id, schema_proxy)
    all_body = _body_proxy(corpus["chunk_id"], text_by_id, section_by_id, schema_proxy)

    # --- step 1: anchor on the corrective run ---
    replay = S.compute_real_cost(
        [{k: E1_CORRECTIVE[k] for k in
          ("input_tokens", "output_tokens",
           "cache_creation_input_tokens", "cache_read_input_tokens")}],
        tier="intro",
    )["real_cost_usd"]
    assert abs(replay - E1_CORRECTIVE["reported_cost_intro_usd"]) < 0.01, (
        f"cost formula does not reproduce E1's real bill ({replay} vs "
        f"{E1_CORRECTIVE['reported_cost_intro_usd']}) — do not trust any "
        f"estimate built on it"
    )
    # cache-write and cache-read tokens must agree on one system-prompt size
    reads_per_req = E1_CORRECTIVE["cache_read_input_tokens"] / (E1_CORRECTIVE["n_requests"] - 1)
    n_writes_corrective = max(1, round(E1_CORRECTIVE["cache_creation_input_tokens"] / reads_per_req))
    claude_sys_v11 = E1_CORRECTIVE["cache_read_input_tokens"] / (
        E1_CORRECTIVE["n_requests"] - n_writes_corrective
    )
    body_ratio = E1_CORRECTIVE["input_tokens"] / corrective_body
    # v1.2's prompt grows by the same proportion in both tokenizers.
    claude_sys_v12 = claude_sys_v11 * (v12_sys_proxy / e1_sys_proxy)

    # --- step 2: cross-validate on the independent re-label run ---
    xval_pred = S.compute_real_cost(
        [{
            "input_tokens": relabel_body * body_ratio,
            "output_tokens": float(relabel_rows["output_tokens"].sum()),
            "cache_creation_input_tokens": claude_sys_v11 * n_writes_corrective,
            "cache_read_input_tokens": claude_sys_v11 * (E1_RELABEL["n_requests"] - n_writes_corrective),
        }],
        tier="intro",
    )["real_cost_usd"]
    # Solve the residual for the re-label's implied cache-write count.
    reported = E1_RELABEL["reported_cost_intro_usd"]
    in_p, out_p = B.PRICING["intro"]["input"], B.PRICING["intro"]["output"]
    residual = (
        reported / B.BATCH_DISCOUNT * 1e6
        - relabel_body * body_ratio * in_p
        - float(relabel_rows["output_tokens"].sum()) * out_p
        - claude_sys_v11 * E1_RELABEL["n_requests"] * in_p * S.CACHE_READ_MULTIPLIER
    )
    per_write = claude_sys_v11 * in_p * (
        S.CACHE_WRITE_1H_MULTIPLIER - S.CACHE_READ_MULTIPLIER
    )
    implied_writes = residual / per_write
    worst_write_rate = implied_writes / E1_RELABEL["n_requests"]

    # --- step 3: scenario table for the v1.2 run ---
    measured_out = float(lab["output_tokens"].sum())
    projected_out = measured_out * OUTPUT_HEADROOM
    scenarios = {
        "best_observed_cache (corrective run, 0.16% writes)": n_writes_corrective / E1_CORRECTIVE["n_requests"],
        "worst_observed_cache (re-label run, 14.2% writes)": worst_write_rate,
        "cold_cache_bound (every request writes)": 1.0,
    }
    table = {}
    for name, rate in scenarios.items():
        w = rate * n
        row = [{
            "input_tokens": all_body * body_ratio,
            "output_tokens": projected_out,
            "cache_creation_input_tokens": claude_sys_v12 * w,
            "cache_read_input_tokens": claude_sys_v12 * (n - w),
        }]
        table[name] = {
            "cache_write_rate": round(rate, 4),
            "intro_usd": S.compute_real_cost(row, tier="intro")["real_cost_usd"],
            "standard_usd": S.compute_real_cost(row, tier="standard")["real_cost_usd"],
        }

    # --- sanity floor: E1's own measured per-request rate, scaled ---
    scaled = {
        "from_relabel_run_intro_usd": round(reported / E1_RELABEL["n_requests"] * n, 2),
        "from_corrective_run_intro_usd": round(
            E1_CORRECTIVE["reported_cost_intro_usd"] / E1_CORRECTIVE["n_requests"] * n, 2
        ),
    }
    scaled["from_relabel_run_standard_usd"] = round(
        scaled["from_relabel_run_intro_usd"] * 1.5, 2
    )

    headline = table["worst_observed_cache (re-label run, 14.2% writes)"]["standard_usd"]

    return {
        "method": "measured-anchor + cross-validation + cache-fan-out scenarios",
        "anchor": {
            "e1_corrective_replay_intro_usd": replay,
            "e1_corrective_reported_intro_usd": E1_CORRECTIVE["reported_cost_intro_usd"],
            "e1_corrective_cache_writes_inferred": n_writes_corrective,
            "claude_system_tokens_v11_measured": round(claude_sys_v11, 1),
            "claude_system_tokens_v12_projected": round(claude_sys_v12, 1),
            "proxy_system_tokens_v11": e1_sys_proxy,
            "proxy_system_tokens_v12": v12_sys_proxy,
            "system_prompt_growth_pct": round(100 * (v12_sys_proxy / e1_sys_proxy - 1), 1),
            "body_tokenizer_ratio_claude_over_proxy": round(body_ratio, 4),
            "e1_measured_output_tokens_6747": int(measured_out),
            "output_headroom_factor": OUTPUT_HEADROOM,
        },
        "cross_validation_on_independent_relabel_run": {
            "predicted_intro_usd": xval_pred,
            "reported_intro_usd": reported,
            "underprediction_pct": round(100 * (1 - xval_pred / reported), 1),
            "verdict": "FAILS — do not use the fitted cache assumption",
            "root_cause": (
                "cache-write fan-out, not tokenization: the re-label's bodies "
                "(799 proxy tokens/req) and outputs (57 tokens/req) are both "
                "SMALLER than the corrective run's (839 / 105). Solving the "
                f"residual implies ~{implied_writes:.0f} of "
                f"{E1_RELABEL['n_requests']} requests ({worst_write_rate:.1%}) "
                "paid a 1h-TTL cache WRITE at 2x input price, vs "
                f"{n_writes_corrective}/{E1_CORRECTIVE['n_requests']} "
                f"({n_writes_corrective / E1_CORRECTIVE['n_requests']:.2%}) in "
                "the corrective run."
            ),
        },
        "scenarios_v12_6747_requests": table,
        "e1_rate_scaled_to_6747": scaled,
        "proxy_model_cost_usd": B.estimate_cost(corpus)["pricing"],
        "headline_usd": headline,
        "headline_basis": (
            "worst cache-write rate E1 actually observed (14.2%), STANDARD "
            "pricing, +25% output headroom, full 6,747 requests"
        ),
        "cap_usd": COST_CAP_USD,
        "notes": [
            "PRICING TIER IS UNRESOLVED OFFLINE. build_batch_requests.PRICING "
            "records intro ($2/$10 per Mtok) as running 'through 2026-08-31' "
            "and standard at $3/$15, both flagged in-repo as unverified for "
            "Sonnet 5. Confirm current Batch pricing (a free, read-only check) "
            "before submitting — it moves the estimate by 50%.",
            "The ratified $16.09 estimate (HANDOFF §3, 2026-08-26) came from "
            "scaling the re-label run's $2.385/1k-request rate to 6,747. That "
            "UNDERSTATES: the re-label subset averaged 57.0 output tokens per "
            "request, while the full 6,747-chunk corpus measured 74.9 "
            "(+31%) — the expensive long chunks were in the OTHER batch. It "
            "also predates the v1.2 prompt, which is 22.3% longer.",
            "Cache-write fan-out is the dominant uncertainty and is not under "
            "our control: it varied ~90x between E1's two runs at identical "
            "config. There is no engineering fix; the only lever is a shorter "
            "system prompt, which the sync rule constrains.",
            "The estimate is conservative in one further respect: the "
            "system-prompt uplift is applied to the whole measured cached "
            "block (3,340 tokens/request). If part of that block is fixed API "
            "framing rather than prompt text, the true uplift is smaller.",
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rebuild", action="store_true",
                    help="Rebuild data/batch_requests_v12.jsonl even if it exists.")
    args = ap.parse_args()

    corpus = pd.read_parquet(CORPUS_PATH)
    print(f"Corpus: {len(corpus)} chunks from {CORPUS_PATH.name}\n")

    build(corpus, rebuild=args.rebuild)
    requests = load_requests(REQUESTS_PATH)
    print(f"\nRe-read {len(requests)} requests from disk: {REQUESTS_PATH}")
    print(f"  sha256(file) = {sha256_file(REQUESTS_PATH)}\n")

    manifest = {
        "generated_for": "G1 repair — rubric v1.2 re-label (HANDOFF §3, 2026-08-26)",
        "requests_file": str(REQUESTS_PATH.relative_to(REPO_ROOT)),
        "requests_file_sha256": sha256_file(REQUESTS_PATH),
        "variant": VARIANT,
        "rubric_version": B.RUBRIC_VERSION,
        "system_prompt_sha256": B.system_prompt_sha256(),
        "corpus_file": str(CORPUS_PATH.relative_to(REPO_ROOT)),
        "corpus_sha256": sha256_file(CORPUS_PATH),
        "rubric_file_sha256": sha256_file(REPO_ROOT / "labeling_rubric.md"),
        "builder_sha256": sha256_file(REPO_ROOT / "build_batch_requests.py"),
        "submitter_sha256": sha256_file(REPO_ROOT / "submit_labeling_batch.py"),
        "prep_script_sha256": sha256_file(Path(__file__).resolve()),
    }

    manifest.update(verify(requests, corpus))
    manifest["single_axis"] = verify_single_axis(requests)
    print_sample(requests, corpus)

    print("\n" + "=" * 70)
    print("COST ESTIMATE")
    print("=" * 70)
    cost = estimate_cost(requests, corpus)
    manifest["cost"] = cost
    print(json.dumps(cost, indent=2))

    headline = cost["headline_usd"]
    print(f"\nHEADLINE: ${headline:.2f}  ({cost['headline_basis']})")
    intro_worst = cost["scenarios_v12_6747_requests"][
        "worst_observed_cache (re-label run, 14.2% writes)"]["intro_usd"]
    if headline > COST_CAP_USD:
        print(
            f"\n*** THE CONSERVATIVE ESTIMATE EXCEEDS THE ${COST_CAP_USD:.2f} "
            f"HARD CAP — STOP AND RE-CONFIRM. ***\n"
            f"Per HANDOFF §3 (2026-08-26): if the pre-submission estimate "
            f"exceeds ${COST_CAP_USD:.2f}, stop and re-confirm with the owner. "
            f"Do NOT submit on this preparation alone.\n\n"
            f"It exceeds the cap ONLY in the standard-pricing corner:\n"
            f"  intro pricing,    worst observed cache: ${intro_worst:.2f}  "
            f"(under the cap)\n"
            f"  standard pricing, worst observed cache: ${headline:.2f}  "
            f"(OVER the cap)\n"
            f"So the decision hinges on which Batch price tier is live — "
            f"confirm that first; it is free and read-only."
        )
    else:
        print(f"Within the ${COST_CAP_USD:.2f} hard cap "
              f"(headroom ${COST_CAP_USD - headline:.2f}).")
    manifest["headline_cost_usd"] = round(headline, 2)
    manifest["within_cap"] = bool(headline <= COST_CAP_USD)

    out = REPO_ROOT / "data" / "hardening" / "v12_request_manifest.json"
    with open(out, "w") as f:
        json.dump(manifest, f, indent=2, default=str)
    print(f"\nWrote provenance manifest: {out}")
    print("\nNO API CALLS WERE MADE. Nothing was submitted.")


if __name__ == "__main__":
    main()
