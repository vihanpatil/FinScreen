"""
submit_labeling_batch.py — Week 3 Batch API submission + polling/join.

This is the *only* file in this project that actually calls the Claude
Batch API. `build_batch_requests.py::submit_batch()` remains an
intentional NotImplementedError stub; this script is the real, gated
submission path.

Modes
-----
--canary [--n N] [--seed S]
    Submit a deterministic, stratified-by-section_type sample of N
    (default 50) requests drawn from data/batch_requests.jsonl /
    data/labeling_corpus.parquet. Writes data/canary_batch_meta.json
    (batch id + the exact custom_ids submitted, so a later --poll run
    can be checked against exactly what was asked for).

--poll <batch_id> [--out labels_canary.parquet]
    Poll `<batch_id>` until it's no longer in_progress (bounded retries,
    ~30 min ceiling), download results, validate each result's parsed
    JSON against the expected schema shape for its chunk's section_type,
    join back onto the corpus on custom_id == chunk_id, and write the
    labeled parquet. Prints a full report: parse success rate, schema
    validation failures, label distribution, real billed token usage,
    real cost, and a projection to the full 6,747-request run.

--full --confirm-full --variant <name>
    Submits every request in the requests file for the named --variant
    (see VARIANT_PATHS / build_batch_requests.py VARIANTS). --variant is
    now REQUIRED for --full (2026-08-11 fix): the prior version silently
    ignored --variant and always loaded the hardcoded default
    data/batch_requests.jsonl regardless of what was requested, which is
    exactly how 4,219 rows of data/labels.parquet ended up mislabeled
    with a false max_tokens_used=800 provenance. Refuses to run without
    --confirm-full even if --full is passed alone, and refuses to run if
    the loaded requests file's actual max_tokens/thinking/effort don't
    match the named variant (see assert_requests_match_variant()).

--full-corrective --confirm-full
    Submits data/batch_requests_corrective.jsonl (the 2,528-request
    'disabled-4000' re-run for chunks truncated in the original full run).

--full-relabel --confirm-full
    Submits data/batch_requests_relabel.jsonl (the 4,219-request re-run
    for chunk_ids corrupted by the run_full() variant-wiring bug — see
    msgbatch_01QAM68H5YWLEDJNcyFcB22L in data/labels.parquet). Writes only
    to data/relabel_batch_meta.json / data/labels_relabel.parquet, never
    touching data/labels.parquet or any other artifact.

Security
--------
ANTHROPIC_API_KEY is loaded from the project .env via python-dotenv and
is NEVER printed, logged, echoed, or included in any written file
(including canary_batch_meta.json and the report). If .env or the key
is missing, the script exits before constructing a client or touching
the API at all.

Look-ahead-bias safety
-----------------------
This script does not read or forward any of the corpus's home_ticker /
home_cik / home_filing_date / source_* metadata columns into any
request. Those columns exist in labeling_corpus.parquet for the later
join-back step only; build_batch_requests.py already built each
request's `params.messages` from chunk text alone, and this script
submits those pre-built request lines verbatim rather than
reconstructing them.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import pandas as pd

from build_batch_requests import (
    BATCH_DISCOUNT,
    CACHE_READ_MULTIPLIER,
    MODEL,
    PRICING,
    VARIANTS,
    _SCHEMA_CACHE,
)

CORPUS_PATH = "data/labeling_corpus.parquet"
REQUESTS_JSONL_PATH = "data/batch_requests.jsonl"
CANARY_META_PATH = "data/canary_batch_meta.json"
CANARY_LABELS_PATH = "data/labels_canary.parquet"
FULL_LABELS_PATH = "data/labels.parquet"

# max_tokens/thinking variant canary (2026-08-10) — see
# build_batch_requests.py VARIANTS for what each config changes. Maps a
# short --variant flag to its request file + default canary meta/labels
# output paths, so both variants can be canaried from the same stratified
# sample (same seed=42) without colliding on output filenames.
VARIANT_PATHS = {
    "disabled": {
        "requests_file": "data/batch_requests_disabled.jsonl",
        "canary_meta": "data/canary_batch_meta_disabled.json",
        "canary_labels": "data/labels_canary_disabled.parquet",
    },
    "adaptive-low": {
        "requests_file": "data/batch_requests_adaptive_low.jsonl",
        "canary_meta": "data/canary_batch_meta_adaptive_low.json",
        "canary_labels": "data/labels_canary_adaptive_low.parquet",
    },
    # Corrective re-run (2026-08-11) — see build_batch_requests.py VARIANTS
    # and data/full_run_report.md §0. Only 2,528 requests (the exact
    # parse_ok=False set from the full "disabled" run), not the full
    # 6,747-chunk corpus.
    "disabled-4000": {
        "requests_file": "data/batch_requests_corrective.jsonl",
        "canary_meta": "data/corrective_batch_meta.json",  # reused as the --full-corrective meta path too
        "canary_labels": "data/labels_corrective.parquet",
    },
}

CORRECTIVE_META_PATH = "data/corrective_batch_meta.json"
CORRECTIVE_REQUESTS_PATH = "data/batch_requests_corrective.jsonl"
CORRECTIVE_LABELS_PATH = "data/labels_corrective.parquet"

# Relabel re-run (2026-08-10) — see build_batch_requests_relabel construction
# note below. Covers the 4,219 chunk_ids whose labels.parquet rows are
# attributed to batch_id msgbatch_01QAM68H5YWLEDJNcyFcB22L, which the
# 2026-08-11 audit found were actually submitted under the UNFIXED
# "disabled" (max_tokens=500, adaptive thinking) config due to the
# run_full() variant-wiring bug — NOT the "disabled-4000" config the
# labels.parquet max_tokens_used=800 column falsely records. Deliberately
# separate output paths from every corrective/full artifact so this re-run
# can never silently overwrite the (still-in-use) original labels.parquet.
RELABEL_VARIANT = "disabled-4000"
RELABEL_REQUESTS_PATH = "data/batch_requests_relabel.jsonl"
RELABEL_META_PATH = "data/relabel_batch_meta.json"
RELABEL_LABELS_PATH = "data/labels_relabel.parquet"

DEFAULT_CANARY_N = 50
DEFAULT_SEED = 42

# Cache-write premium for the 1h TTL requested in build_batch_requests.py.
CACHE_WRITE_1H_MULTIPLIER = 2.0

REQUIRED_FIELDS_BY_SECTION_TYPE = {
    st: schema["required"] for st, schema in _SCHEMA_CACHE.items()
}


# ---------------------------------------------------------------------
# API key handling — never print/log the key or any prefix of it.
# ---------------------------------------------------------------------
def load_api_key() -> str:
    env_path = Path(".env")
    if not env_path.exists():
        print(
            "No .env file found in the project root. Not submitting anything.\n"
            "Create .env with ANTHROPIC_API_KEY=<key> and re-run.",
            file=sys.stderr,
        )
        sys.exit(1)

    from dotenv import load_dotenv

    load_dotenv(dotenv_path=env_path)
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print(
            "ANTHROPIC_API_KEY not found in .env (or empty). Not submitting anything.",
            file=sys.stderr,
        )
        sys.exit(1)
    return key  # caller must not print this


def get_client():
    import anthropic

    key = load_api_key()
    client = anthropic.Anthropic(api_key=key)
    del key  # don't keep it bound any longer than needed
    return client


# ---------------------------------------------------------------------
# Stratified canary sampling
# ---------------------------------------------------------------------
def stratified_sample_custom_ids(
    corpus_df: pd.DataFrame, n: int = DEFAULT_CANARY_N, seed: int = DEFAULT_SEED
) -> list[str]:
    """Deterministic, proportional-by-section_type sample of chunk_ids.

    Proportional allocation via largest-remainder method so the strata
    sizes sum exactly to n even with rounding, then a seeded per-stratum
    sample for reproducibility.
    """
    counts = corpus_df["section_type"].value_counts()
    total = counts.sum()

    raw_alloc = {st: n * cnt / total for st, cnt in counts.items()}
    base_alloc = {st: int(v) for st, v in raw_alloc.items()}
    remainder = n - sum(base_alloc.values())

    # Largest-remainder method: give the leftover slots to the strata
    # with the biggest fractional part, tie-broken by section_type name
    # for determinism.
    remainders = sorted(
        raw_alloc.items(), key=lambda kv: (-(kv[1] - int(kv[1])), kv[0])
    )
    for st, _ in remainders[:remainder]:
        base_alloc[st] += 1

    sampled_ids: list[str] = []
    for st, k in base_alloc.items():
        stratum = corpus_df[corpus_df["section_type"] == st]
        k = min(k, len(stratum))
        picked = stratum.sample(n=k, random_state=seed)
        sampled_ids.extend(picked["chunk_id"].tolist())

    return sorted(sampled_ids)


def load_requests_by_custom_id(path: str = REQUESTS_JSONL_PATH) -> dict[str, dict]:
    by_id = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            req = json.loads(line)
            by_id[req["custom_id"]] = req
    return by_id


class VariantMismatchError(RuntimeError):
    """Raised by assert_requests_match_variant when a requests file's
    actual request bodies do not match the max_tokens/thinking/effort
    config named by --variant. This is the single choke point every
    submit path (canary, full, full-corrective, full-relabel) must pass
    through before calling batches.create() — see the 2026-08-11
    postmortem: the bug class here is "submitted artifact != tested
    artifact", not any one function's logic, so the guard belongs here,
    not bolted onto one function."""


def _extract_actual_config(params: dict) -> dict:
    return {
        "max_tokens": params.get("max_tokens"),
        "thinking": params.get("thinking"),  # None means "absent from request"
        "effort": params.get("output_config", {}).get("effort"),  # None means "absent"
    }


def assert_requests_match_variant(
    requests: list[dict], variant: str, requests_file: str
) -> None:
    """Inspects every loaded request body's actual max_tokens/thinking/
    effort against VARIANTS[variant]'s expected config (from
    build_batch_requests.py, the single source of truth for what each
    variant name means). Aborts loudly with a full expected-vs-actual
    diff BEFORE any API call if even one request's real body disagrees —
    inspecting the request bodies themselves, never trusting the
    filename or a --variant flag alone to mean what it says.

    This is precisely the check that would have caught the 2026-08-11
    bug: run_full() loaded data/batch_requests.jsonl (max_tokens=500, no
    thinking key = adaptive default) while claiming/recording the
    "disabled" variant (max_tokens=800, thinking=disabled) had been used.
    """
    if variant not in VARIANTS:
        raise VariantMismatchError(
            f"Unknown variant {variant!r}. Known variants: {sorted(VARIANTS)}"
        )
    expected_cfg = VARIANTS[variant]
    expected = {
        "max_tokens": expected_cfg["max_tokens"],
        "thinking": expected_cfg["thinking"],
        "effort": expected_cfg["effort"],
    }

    if not requests:
        raise VariantMismatchError(
            f"Requests file {requests_file!r} is empty — nothing to submit."
        )

    mismatches = []
    for req in requests:
        actual = _extract_actual_config(req.get("params", {}))
        if actual != expected:
            mismatches.append((req.get("custom_id"), actual))

    if mismatches:
        sample = mismatches[:5]
        diff_lines = "\n".join(
            f"  custom_id={cid!r}: expected {expected} but got {actual}"
            for cid, actual in sample
        )
        raise VariantMismatchError(
            f"\n\nREFUSING TO SUBMIT — variant/artifact mismatch.\n"
            f"requests_file={requests_file!r} claims to be variant={variant!r}, "
            f"which per build_batch_requests.py VARIANTS[{variant!r}] should "
            f"give every request:\n  {expected}\n\n"
            f"But {len(mismatches)}/{len(requests)} requests in that file do "
            f"NOT match. First {len(sample)} mismatch(es):\n{diff_lines}\n\n"
            f"Nothing was submitted. This is exactly the bug class from the "
            f"2026-08-11 postmortem (submitted artifact != tested/claimed "
            f"artifact) — fix the requests file or the --variant/--requests-file "
            f"pairing before retrying."
        )

    print(
        f"Variant guard OK: all {len(requests)} requests in {requests_file!r} "
        f"match variant={variant!r} ({expected})."
    )


# ---------------------------------------------------------------------
# Canary submission
# ---------------------------------------------------------------------
def run_canary(n: int, seed: int, requests_file: str = REQUESTS_JSONL_PATH,
               meta_path: str = CANARY_META_PATH, variant: str | None = None) -> None:
    corpus_df = pd.read_parquet(CORPUS_PATH)
    all_requests = load_requests_by_custom_id(path=requests_file)

    # Same stratified sample (same seed) regardless of which variant's
    # request file is being drawn from, so the two canaries are directly
    # comparable chunk-for-chunk.
    sample_ids = stratified_sample_custom_ids(corpus_df, n=n, seed=seed)
    missing = [cid for cid in sample_ids if cid not in all_requests]
    if missing:
        print(
            f"ERROR: {len(missing)} sampled chunk_id(s) not found in "
            f"{requests_file} (corpus/jsonl out of sync). Aborting, "
            "nothing submitted.",
            file=sys.stderr,
        )
        sys.exit(1)

    stratum_counts = (
        corpus_df[corpus_df["chunk_id"].isin(sample_ids)]["section_type"]
        .value_counts()
        .to_dict()
    )
    print(f"Canary sample: {len(sample_ids)} requests (seed={seed}, variant={variant}, requests_file={requests_file})")
    print(f"Stratum breakdown: {stratum_counts}")

    batch_requests = [all_requests[cid] for cid in sample_ids]

    if variant is not None:
        assert_requests_match_variant(batch_requests, variant, requests_file)
    else:
        print(
            f"WARNING: no --variant given for this canary (requests_file="
            f"{requests_file!r}) — the variant-mismatch guard has nothing to "
            "check against and is SKIPPED. Prefer --variant whenever the "
            "requests file corresponds to a named variant."
        )

    client = get_client()
    batch = client.messages.batches.create(requests=batch_requests)

    meta = {
        "batch_id": batch.id,
        "mode": "canary",
        "variant": variant,
        "requests_file": requests_file,
        "n_requested": n,
        "n_submitted": len(sample_ids),
        "seed": seed,
        "stratum_counts": stratum_counts,
        "custom_ids": sample_ids,
        "model": MODEL,
        "submitted_at": batch.created_at.isoformat()
        if hasattr(batch.created_at, "isoformat")
        else str(batch.created_at),
        "processing_status": batch.processing_status,
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, default=str)

    print(f"Submitted canary batch: {batch.id}")
    print(f"Wrote {meta_path}")


# ---------------------------------------------------------------------
# Polling + result parsing/validation/join
# ---------------------------------------------------------------------
def poll_until_ended(client, batch_id: str, max_wait_s: int = 1800, poll_every_s: int = 20):
    waited = 0
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        print(
            f"  [{waited}s] status={batch.processing_status} "
            f"counts={batch.request_counts}"
        )
        if batch.processing_status != "in_progress":
            return batch
        if waited >= max_wait_s:
            print(
                f"Still in_progress after {max_wait_s}s ceiling. "
                "Re-run --poll later to check again.",
                file=sys.stderr,
            )
            return batch
        time.sleep(poll_every_s)
        waited += poll_every_s


def validate_result(parsed: dict, section_type: str) -> list[str]:
    """Returns a list of validation problems (empty = valid)."""
    problems = []
    expected_required = set(REQUIRED_FIELDS_BY_SECTION_TYPE.get(section_type, []))
    got_keys = set(parsed.keys())

    missing = expected_required - got_keys
    if missing:
        problems.append(f"missing required fields: {sorted(missing)}")

    extra = got_keys - expected_required
    if extra:
        problems.append(f"unexpected fields for section_type={section_type}: {sorted(extra)}")

    if "sentiment" in parsed and parsed["sentiment"] not in ("POSITIVE", "NEUTRAL", "NEGATIVE"):
        problems.append(f"bad sentiment value: {parsed['sentiment']!r}")
    if "guidance_direction" in parsed and parsed["guidance_direction"] not in (
        "RAISED", "MAINTAINED", "LOWERED", "WITHDRAWN", "NONE",
    ):
        problems.append(f"bad guidance_direction value: {parsed['guidance_direction']!r}")
    for list_field, valid_categories in (
        ("red_flags", {"DEMAND_WEAKNESS", "SUPPLY_INPUT_CONSTRAINT", "TRADE_POLICY_EXPOSURE",
                        "IMPAIRMENT_WRITEDOWN", "MARGIN_COST_PRESSURE", "LEGAL_REGULATORY_ACTION"}),
        ("distress_tier", {"GOING_CONCERN", "ACCOUNTING_RESTATEMENT", "LIQUIDITY_STRESS"}),
    ):
        if list_field in parsed:
            if not isinstance(parsed[list_field], list):
                problems.append(f"{list_field} is not a list")
            else:
                for item in parsed[list_field]:
                    if not isinstance(item, dict) or "category" not in item or "modality" not in item:
                        problems.append(f"{list_field} entry malformed: {item!r}")
                        continue
                    if item["category"] not in valid_categories:
                        problems.append(f"{list_field} bad category: {item['category']!r}")
                    if item["modality"] not in ("HYPOTHETICAL", "REALIZED"):
                        problems.append(f"{list_field} bad modality: {item['modality']!r}")
    return problems


def compute_real_cost(usage_rows: list[dict], tier: str = "intro") -> dict:
    """usage_rows: list of dicts with input_tokens, output_tokens,
    cache_creation_input_tokens, cache_read_input_tokens (raw, per
    Batch API result, already Batch-discounted by Anthropic's billing —
    we apply BATCH_DISCOUNT ourselves since the API reports raw token
    counts, not pre-discounted dollar amounts)."""
    in_price = PRICING[tier]["input"]
    out_price = PRICING[tier]["output"]

    total_input = sum(r["input_tokens"] for r in usage_rows)
    total_output = sum(r["output_tokens"] for r in usage_rows)
    total_cache_write = sum(r["cache_creation_input_tokens"] for r in usage_rows)
    total_cache_read = sum(r["cache_read_input_tokens"] for r in usage_rows)

    cost = (
        total_input * in_price
        + total_output * out_price
        + total_cache_write * in_price * CACHE_WRITE_1H_MULTIPLIER
        + total_cache_read * in_price * CACHE_READ_MULTIPLIER
    ) / 1e6 * BATCH_DISCOUNT

    return {
        "tier": tier,
        "n_requests": len(usage_rows),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cache_creation_input_tokens": total_cache_write,
        "total_cache_read_input_tokens": total_cache_read,
        "real_cost_usd": round(cost, 4),
        "avg_cost_per_request_usd": round(cost / len(usage_rows), 6) if usage_rows else 0.0,
    }


def run_poll(batch_id: str, out_path: str, max_wait_s: int) -> None:
    client = get_client()

    print(f"Polling batch {batch_id} (ceiling {max_wait_s}s)...")
    batch = poll_until_ended(client, batch_id, max_wait_s=max_wait_s)

    if batch.processing_status == "in_progress":
        print("Batch not yet ended; exiting without writing results.")
        return

    print(f"Batch ended: status={batch.processing_status} counts={batch.request_counts}")

    corpus_df = pd.read_parquet(CORPUS_PATH)
    section_type_by_id = dict(zip(corpus_df["chunk_id"], corpus_df["section_type"]))

    rows = []
    usage_rows = []
    n_total = 0
    n_succeeded = 0
    n_parse_failed = 0
    n_schema_invalid = 0
    n_not_succeeded = 0  # errored/expired/canceled at the API level

    for item in client.messages.batches.results(batch_id):
        n_total += 1
        custom_id = item.custom_id
        section_type = section_type_by_id.get(custom_id)

        result_type = item.result.type
        if result_type != "succeeded":
            n_not_succeeded += 1
            rows.append({
                "chunk_id": custom_id,
                "parse_ok": False,
                "schema_valid": False,
                "api_result_type": result_type,
                "parse_error": f"batch result type={result_type}, not 'succeeded'",
                "raw_label_json": None,
            })
            continue

        message = item.result.message
        usage = message.usage
        usage_rows.append({
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_creation_input_tokens": usage.cache_creation_input_tokens or 0,
            "cache_read_input_tokens": usage.cache_read_input_tokens or 0,
        })

        text_blocks = [b.text for b in message.content if getattr(b, "type", None) == "text"]
        raw_text = text_blocks[0] if text_blocks else ""

        try:
            parsed = json.loads(raw_text)
            n_succeeded += 1
        except (json.JSONDecodeError, IndexError) as e:
            n_parse_failed += 1
            rows.append({
                "chunk_id": custom_id,
                "parse_ok": False,
                "schema_valid": False,
                "api_result_type": result_type,
                "parse_error": f"JSON parse error: {e}",
                "raw_label_json": raw_text,
            })
            continue

        problems = validate_result(parsed, section_type)
        schema_valid = len(problems) == 0
        if not schema_valid:
            n_schema_invalid += 1

        rows.append({
            "chunk_id": custom_id,
            "parse_ok": True,
            "schema_valid": schema_valid,
            "api_result_type": result_type,
            "parse_error": "; ".join(problems) if problems else None,
            "raw_label_json": raw_text,
            "sentiment": parsed.get("sentiment"),
            "guidance_direction": parsed.get("guidance_direction"),
            "red_flags": parsed.get("red_flags"),
            "distress_tier": parsed.get("distress_tier"),
        })

    labels_df = pd.DataFrame(rows)
    joined = corpus_df.merge(labels_df, on="chunk_id", how="right")
    joined.to_parquet(out_path)
    print(f"Wrote {len(joined)} labeled rows to {out_path}")

    # --- Report ---
    print("\n=== CANARY REPORT ===" if "canary" in out_path else "\n=== LABELING REPORT ===")
    print(f"Total results returned: {n_total}")
    print(f"API-level not-succeeded (errored/expired/canceled): {n_not_succeeded}")
    print(f"JSON parse failures (among succeeded API results): {n_parse_failed}")
    print(f"Schema validation failures (among JSON-parsed results): {n_schema_invalid}")
    clean = n_succeeded - n_schema_invalid
    denom = n_total if n_total else 1
    print(f"Clean (parsed + schema-valid) rate: {clean}/{n_total} = {clean/denom:.1%}")

    if "sentiment" in labels_df.columns:
        print("\nSentiment distribution (non-null):")
        print(labels_df["sentiment"].dropna().value_counts())
    if "guidance_direction" in labels_df.columns:
        print("\nGuidance direction distribution (non-null):")
        print(labels_df["guidance_direction"].dropna().value_counts())
    n_with_red_flags = labels_df["red_flags"].apply(lambda v: bool(v)).sum() if "red_flags" in labels_df.columns else 0
    n_with_distress = labels_df["distress_tier"].apply(lambda v: bool(v)).sum() if "distress_tier" in labels_df.columns else 0
    print(f"\nRows with >=1 red flag: {n_with_red_flags}/{n_total}")
    print(f"Rows with >=1 distress-tier match: {n_with_distress}/{n_total}")

    if usage_rows:
        print("\n--- Real billed usage / cost ---")
        for tier in PRICING:
            cost_report = compute_real_cost(usage_rows, tier=tier)
            print(f"[{tier} pricing] {json.dumps(cost_report, indent=2)}")

            if "intro" in tier:
                full_n = 6747
                projected = cost_report["avg_cost_per_request_usd"] * full_n
                print(
                    f"  -> Projected full-run ({full_n} requests) cost at "
                    f"[{tier}] pricing, using this canary's *average measured* "
                    f"per-request cost: ${projected:.2f}\n"
                    f"     NOTE: this canary is small and its cache-write/read "
                    f"mix is not representative of a 6,747-request run's "
                    f"concurrency pattern (see build_batch_requests.py's "
                    f"cache_write_tokens_realistic note) — treat as a rough, "
                    f"not precise, projection."
                )
    else:
        print("\nNo successful results with usage data — cannot compute real cost.")


# ---------------------------------------------------------------------
# Post-submission verification (TASK 4, 2026-08-11) — the check that
# would have caught the original run_full() variant-wiring bug AFTER the
# fact, by looking at what was actually billed/returned rather than
# trusting recorded metadata. The original bug's signature: requests
# were submitted with max_tokens=500 (wrong config) while labels.parquet
# recorded max_tokens_used=800 (the intended "disabled" config) — so the
# giveaway is a hard ceiling in observed output_tokens sitting at the
# WRONG (lower) config's cap, not the intended one.
# ---------------------------------------------------------------------
def verify_batch_config(result_records: list[dict], variant: str) -> dict:
    """Given a completed batch's result records (each a dict with at
    least an 'output_tokens' key — see `_output_tokens_from_result` for
    how real SDK result objects are reduced to this shape), checks the
    observed output_tokens ceiling against VARIANTS[variant]'s intended
    max_tokens.

    Does NOT call the API itself — pass in already-fetched/stubbed
    records. Pure function, unit-testable without a client.

    Returns a report dict:
      {
        "variant": ..., "intended_max_tokens": ...,
        "n_results": ..., "observed_max_output_tokens": ...,
        "n_at_observed_ceiling": ...,
        "ceiling_below_intended": bool,  # THE original-bug signature
        "verdict": "OK" | "SUSPECT_WRONG_CONFIG",
        "message": <human-readable explanation>,
      }
    """
    if variant not in VARIANTS:
        raise VariantMismatchError(
            f"Unknown variant {variant!r}. Known variants: {sorted(VARIANTS)}"
        )
    intended_max_tokens = VARIANTS[variant]["max_tokens"]

    if not result_records:
        return {
            "variant": variant,
            "intended_max_tokens": intended_max_tokens,
            "n_results": 0,
            "observed_max_output_tokens": None,
            "n_at_observed_ceiling": 0,
            "ceiling_below_intended": False,
            "verdict": "NO_RESULTS",
            "message": "No result records supplied — nothing to verify.",
        }

    output_tokens = [r["output_tokens"] for r in result_records]
    observed_max = max(output_tokens)
    n_at_ceiling = sum(1 for t in output_tokens if t == observed_max)

    # ------------------------------------------------------------------
    # Heuristic v2 (2026-08-11). v1 flagged `observed_max <
    # intended_max_tokens` as the bug signature. That was WRONG and made
    # the checker fire on every healthy run: a well-configured batch
    # almost always finishes well under its cap (the 4,219-request
    # re-label ran a median of 47 output tokens against a 4,000 cap and
    # was incorrectly flagged SUSPECT_WRONG_CONFIG). A checker that cries
    # wolf on every good run is worse than no checker, because people
    # learn to ignore it.
    #
    # The REAL signature of the original incident is truncation: requests
    # actually submitted against a smaller cap than claimed run out of
    # output budget, so a material fraction of results come back with
    # stop_reason == "max_tokens", all piled up at the same ceiling
    # (incident: 2,537/6,747 = 37.6% at exactly 500). Healthy runs have a
    # near-zero truncation rate at any ceiling.
    # ------------------------------------------------------------------
    TRUNCATION_RATE_THRESHOLD = 0.01  # >1% truncation is not normal

    stop_reasons = [r.get("stop_reason") for r in result_records]
    have_stop_reasons = any(s is not None for s in stop_reasons)
    n_truncated = sum(1 for s in stop_reasons if s == "max_tokens")
    truncation_rate = n_truncated / len(result_records)
    n_truncated_at_ceiling = sum(
        1
        for r in result_records
        if r.get("stop_reason") == "max_tokens" and r["output_tokens"] == observed_max
    )
    ceiling_below_intended = observed_max < intended_max_tokens

    if not have_stop_reasons:
        verdict = "INCONCLUSIVE"
        message = (
            "Result records carry no stop_reason, so truncation cannot be "
            "measured. Re-fetch with stop_reason included; do not infer "
            "config correctness from the output-token ceiling alone."
        )
    elif truncation_rate > TRUNCATION_RATE_THRESHOLD:
        verdict = "SUSPECT_WRONG_CONFIG"
        message = (
            f"{n_truncated}/{len(result_records)} results "
            f"({truncation_rate:.1%}) stopped on max_tokens, "
            f"{n_truncated_at_ceiling} of them piled at output_tokens="
            f"{observed_max} — the truncation signature from the "
            f"2026-08-11 postmortem. The batch was very likely submitted "
            f"against a smaller max_tokens than variant={variant!r} claims "
            f"({intended_max_tokens}). Do not merge without investigating."
        )
    else:
        verdict = "OK"
        message = (
            f"Truncation rate {truncation_rate:.2%} "
            f"({n_truncated}/{len(result_records)}) is within tolerance; "
            f"responses completed naturally under the variant={variant!r} cap "
            f"of {intended_max_tokens} (observed ceiling {observed_max}, "
            f"{n_at_ceiling} result(s) there). A ceiling far below the cap is "
            f"expected and healthy — it means responses finished on their own."
        )

    return {
        "variant": variant,
        "intended_max_tokens": intended_max_tokens,
        "n_results": len(result_records),
        "observed_max_output_tokens": observed_max,
        "n_at_observed_ceiling": n_at_ceiling,
        "ceiling_below_intended": ceiling_below_intended,  # informational only
        "n_truncated": n_truncated,
        "truncation_rate": round(truncation_rate, 4),
        "verdict": verdict,
        "message": message,
    }


def _output_tokens_from_result(item) -> int | None:
    """Reduces one real Batch API result item (as returned by
    client.messages.batches.results(batch_id)) down to an output_tokens
    int, or None if the result wasn't a succeeded message (errored/
    expired/canceled results carry no usage and are skipped)."""
    if getattr(item.result, "type", None) != "succeeded":
        return None
    return item.result.message.usage.output_tokens


def run_verify_config(batch_id: str, variant: str) -> None:
    """CLI entry point for --verify-config. Calls the API to fetch the
    named batch's results (read-only — does not submit/create anything),
    reduces them to output_tokens, and prints verify_batch_config()'s
    report. NEVER RUN AUTOMATICALLY BY THIS SCRIPT'S OWNER-FACING
    postmortem work — this function is written and unit-tested against
    synthetic records only; the owner runs it explicitly when ready."""
    client = get_client()
    result_records = []
    for item in client.messages.batches.results(batch_id):
        out_tokens = _output_tokens_from_result(item)
        if out_tokens is not None:
            msg = getattr(item.result, "message", None)
            result_records.append(
                {
                    "output_tokens": out_tokens,
                    "stop_reason": getattr(msg, "stop_reason", None),
                }
            )

    report = verify_batch_config(result_records, variant)
    print(json.dumps(report, indent=2))
    if report["verdict"] == "SUSPECT_WRONG_CONFIG":
        print(
            "\nVERDICT: SUSPECT_WRONG_CONFIG — this looks like the original "
            "run_full() variant-wiring bug's signature. Do not merge these "
            "labels without further investigation.",
            file=sys.stderr,
        )


def main():
    parser = argparse.ArgumentParser(description="Submit/poll the labeling Batch API run.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--canary", action="store_true", help="Submit a stratified canary sample.")
    mode.add_argument("--poll", metavar="BATCH_ID", help="Poll a batch id until ended, then parse/join/report.")
    mode.add_argument(
        "--verify-config", metavar="BATCH_ID",
        help="Post-submission verification (read-only, no submission): fetch "
             "BATCH_ID's results and check the observed output_tokens ceiling "
             "against the intended max_tokens for --variant. Flags the "
             "original run_full() bug's signature (observed ceiling below "
             "intended cap). Requires --variant.",
    )
    mode.add_argument("--full", action="store_true", help="Submit the full run. Requires --confirm-full.")
    mode.add_argument(
        "--full-corrective", action="store_true",
        help="Submit all 2,528 requests in data/batch_requests_corrective.jsonl "
             "(the 'disabled-4000' corrective re-run for the truncated chunks "
             "from the original full run). Requires --confirm-full.",
    )
    mode.add_argument(
        "--full-relabel", action="store_true",
        help="Submit all 4,219 requests in data/batch_requests_relabel.jsonl "
             "(re-run for the chunk_ids corrupted by the run_full() "
             "variant-wiring bug — see msgbatch_01QAM68H5YWLEDJNcyFcB22L in "
             "data/labels.parquet). Requires --confirm-full. Writes only to "
             "data/relabel_batch_meta.json / data/labels_relabel.parquet.",
    )

    parser.add_argument("--n", type=int, default=DEFAULT_CANARY_N, help="Canary sample size (default 50).")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Sampling seed (default 42).")
    parser.add_argument("--out", default=None, help="Output parquet path override.")
    parser.add_argument("--confirm-full", action="store_true", help="Required alongside --full.")
    parser.add_argument("--max-wait-s", type=int, default=1800, help="Poll ceiling in seconds (default 1800 = 30min).")
    parser.add_argument("--poll-every-s", type=int, default=20, help="Sleep between polls (default 20s).")
    parser.add_argument(
        "--variant",
        choices=sorted(VARIANT_PATHS.keys()),
        default=None,
        help="Shortcut for --requests-file + default meta/labels output paths "
             "(max_tokens/thinking canary variants — see build_batch_requests.py).",
    )
    parser.add_argument(
        "--requests-file",
        default=None,
        help="Explicit path to a requests .jsonl (overrides the default/variant path).",
    )

    args = parser.parse_args()

    if args.variant and args.requests_file:
        print("Pass either --variant or --requests-file, not both.", file=sys.stderr)
        sys.exit(1)

    if args.full:
        if not args.confirm_full:
            print(
                "--full requires --confirm-full (orchestrator-level gate). "
                "Refusing to submit the full 6,747-request run.",
                file=sys.stderr,
            )
            sys.exit(1)
        if args.variant:
            vp = VARIANT_PATHS[args.variant]
            run_full(variant=args.variant, requests_file=vp["requests_file"])
        elif args.requests_file:
            print(
                "--full --requests-file requires --variant too, so the guard "
                "has a named config to check the file against (the exact "
                "failure mode this guard exists to prevent). Pass --variant.",
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            print(
                "--full requires --variant (no bare default requests file — "
                "see the 2026-08-11 postmortem for why an implicit default "
                "path here caused a 4,219-row corruption). Pass --variant.",
                file=sys.stderr,
            )
            sys.exit(1)
        return

    if args.full_corrective:
        if not args.confirm_full:
            print(
                "--full-corrective requires --confirm-full (orchestrator-level gate). "
                "Refusing to submit the 2,528-request corrective run.",
                file=sys.stderr,
            )
            sys.exit(1)
        run_full_corrective()
        return

    if args.full_relabel:
        if not args.confirm_full:
            print(
                "--full-relabel requires --confirm-full (orchestrator-level gate). "
                "Refusing to submit the 4,219-request relabel run.",
                file=sys.stderr,
            )
            sys.exit(1)
        run_full_relabel()
        return

    if args.canary:
        if args.variant:
            vp = VARIANT_PATHS[args.variant]
            run_canary(
                n=args.n, seed=args.seed,
                requests_file=vp["requests_file"],
                meta_path=vp["canary_meta"],
                variant=args.variant,
            )
        elif args.requests_file:
            run_canary(n=args.n, seed=args.seed, requests_file=args.requests_file)
        else:
            run_canary(n=args.n, seed=args.seed)
        return

    if args.verify_config:
        if not args.variant:
            print(
                "--verify-config requires --variant (the config to check the "
                "batch's actual observed output_tokens ceiling against).",
                file=sys.stderr,
            )
            sys.exit(1)
        run_verify_config(args.verify_config, args.variant)
        return

    if args.poll:
        # Default to the canary output path unless the caller explicitly
        # names a different one (e.g. for a later full-run poll). --variant
        # picks the variant-specific default labels path.
        if args.out:
            out = args.out
        elif args.variant:
            out = VARIANT_PATHS[args.variant]["canary_labels"]
        else:
            out = CANARY_LABELS_PATH
        run_poll(args.poll, out_path=out, max_wait_s=args.max_wait_s)
        return


def run_full(
    variant: str,
    requests_file: str,
    meta_path: str = "data/full_batch_meta.json",
) -> None:
    """Submits every request in `requests_file`. Only reached if --full
    --confirm-full were both passed.

    2026-08-11 postmortem fix: this function previously took NO arguments
    and always loaded the module-level default REQUESTS_JSONL_PATH
    ("data/batch_requests.jsonl"), silently ignoring whatever --variant
    the caller passed on the CLI. That is exactly how the 4,219-row
    corruption happened (the "disabled" variant was requested and
    recorded, but the untouched, unfixed original 500-max-tokens/
    adaptive-thinking file was what actually got submitted). This now
    mirrors run_full_corrective()'s pattern: explicit requests_file,
    variant recorded in meta, and passed through the single
    assert_requests_match_variant() choke point before any API call.
    """
    all_requests = list(load_requests_by_custom_id(path=requests_file).values())
    assert_requests_match_variant(all_requests, variant, requests_file)

    client = get_client()
    batch = client.messages.batches.create(requests=all_requests)
    meta = {
        "batch_id": batch.id,
        "mode": "full",
        "variant": variant,
        "requests_file": requests_file,
        "n_submitted": len(all_requests),
        "model": MODEL,
        "processing_status": batch.processing_status,
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, default=str)
    print(f"Submitted FULL batch: {batch.id} ({len(all_requests)} requests, variant={variant})")


def run_full_corrective():
    """Submits every line of data/batch_requests_corrective.jsonl (the
    2,528-request 'disabled-4000' corrective re-run for chunks that were
    truncated/unparseable in the original full 'disabled' (max_tokens=800)
    run — see data/full_run_report.md §0). Only reached if
    --full-corrective --confirm-full were both passed."""
    all_requests = list(load_requests_by_custom_id(path=CORRECTIVE_REQUESTS_PATH).values())
    assert_requests_match_variant(all_requests, "disabled-4000", CORRECTIVE_REQUESTS_PATH)

    client = get_client()
    batch = client.messages.batches.create(requests=all_requests)
    meta = {
        "batch_id": batch.id,
        "mode": "full-corrective",
        "variant": "disabled-4000",
        "requests_file": CORRECTIVE_REQUESTS_PATH,
        "n_submitted": len(all_requests),
        "model": MODEL,
        "processing_status": batch.processing_status,
    }
    with open(CORRECTIVE_META_PATH, "w") as f:
        json.dump(meta, f, indent=2, default=str)
    print(f"Submitted FULL-CORRECTIVE batch: {batch.id} ({len(all_requests)} requests)")


def run_full_relabel():
    """Submits every line of data/batch_requests_relabel.jsonl — the
    4,219-request re-run for the chunk_ids whose labels.parquet rows are
    attributed to batch_id msgbatch_01QAM68H5YWLEDJNcyFcB22L (the
    run_full() variant-wiring bug's victims: actually submitted at
    max_tokens=500/adaptive-thinking despite being recorded as
    max_tokens=800/disabled). Built with the 'disabled-4000' variant, same
    as the corrective re-run. Only reached if --full-relabel
    --confirm-full were both passed.

    Deliberately writes to its OWN meta/labels paths
    (data/relabel_batch_meta.json, data/labels_relabel.parquet) and never
    touches data/labels.parquet, data/full_batch_meta.json, or any
    corrective artifact — the owner reviews/merges labels_relabel.parquet
    into labels.parquet as a separate, explicit step, not automatically.
    """
    all_requests = list(load_requests_by_custom_id(path=RELABEL_REQUESTS_PATH).values())
    assert_requests_match_variant(all_requests, RELABEL_VARIANT, RELABEL_REQUESTS_PATH)

    client = get_client()
    batch = client.messages.batches.create(requests=all_requests)
    meta = {
        "batch_id": batch.id,
        "mode": "full-relabel",
        "variant": RELABEL_VARIANT,
        "requests_file": RELABEL_REQUESTS_PATH,
        "n_submitted": len(all_requests),
        "model": MODEL,
        "processing_status": batch.processing_status,
        "note": (
            "Re-run of the 4,219 chunk_ids corrupted by the run_full() "
            "variant-wiring bug (originally attributed to batch_id "
            "msgbatch_01QAM68H5YWLEDJNcyFcB22L). Does not touch "
            "data/labels.parquet or data/full_batch_meta.json."
        ),
    }
    with open(RELABEL_META_PATH, "w") as f:
        json.dump(meta, f, indent=2, default=str)
    print(f"Submitted FULL-RELABEL batch: {batch.id} ({len(all_requests)} requests)")


if __name__ == "__main__":
    main()
