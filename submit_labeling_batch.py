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

G1 REPAIR — rubric v1.2 re-label (2026-08-26)
---------------------------------------------
The §5 spend freeze is lifted for exactly ONE run: a single Batch API
re-label of all 6,747 E1 chunks under rubric v1.2 (owner ratification:
HANDOFF §3, 2026-08-26). Prepared by data/hardening/build_v12_requests.py
(build + guards + cost, zero API calls); the report is
data/hardening/status/G1_repair_prep.md.

    python3 submit_labeling_batch.py --full --confirm-full --variant v12_relabel
    python3 submit_labeling_batch.py --poll <BATCH_ID> --variant v12_relabel \
        --out data/labels_v12.parquet --max-wait-s 86400

Single-axis discipline: v12_relabel's max_tokens/thinking/model are
byte-identical to E1's final pass ("disabled-4000"); the ONLY difference
is SYSTEM_PROMPT. Because the variant guard cannot see the prompt, a
second guard (assert_requests_use_current_system_prompt) runs for every
variant in RUBRIC_PINNED_VARIANTS. Outputs land at NEW paths only —
data/labels_v12.parquet and data/v12_relabel_batch_meta.json. E1's
data/labels.parquet and data/full_batch_meta.json stay frozen.

--complete-missing --against <labels.parquet> --variant <name>
---------------------------------------------------------------
Finishes the rows an existing labels parquet never got answers for. The
v1.2 re-label ended 6,746/6,747: its last request errored with "credit
balance too low", leaving CHK-1c1812ed45219a3a with a row in
data/labels_v12.parquet carrying no labels and no stop_reason. The owner
authorized completing exactly that row (in chat, 2026-08-26).

    # 1. preview — prints the count and the estimated cost, submits NOTHING
    python3 submit_labeling_batch.py --complete-missing \
        --against data/labels_v12.parquet --variant v12_relabel
    # 2. submit (add --confirm-complete once the preview looks right)
    python3 submit_labeling_batch.py --complete-missing \
        --against data/labels_v12.parquet --variant v12_relabel \
        --confirm-complete
    # 3. poll + merge in place (backup taken first)
    python3 submit_labeling_batch.py --poll <BATCH_ID> --variant v12_relabel \
        --merge-into data/labels_v12.parquet --max-wait-s 1800

Scope is guarded, not merely documented: --max-missing (default 3)
refuses the run outright above that many unanswered rows, so this mode
can never quietly become a campaign re-run; "unanswered" means no
stop_reason AND no labels, so genuine refusals and truncations are
answers and are left alone; the merge refuses to overwrite any row that
already carries a label, refuses to clobber an existing
<target>.pre_completion backup, and stamps every filled row with
`completion_batch_id`.

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
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

import pandas as pd

from build_batch_requests import (
    BATCH_DISCOUNT,
    CACHE_READ_MULTIPLIER,
    MODEL,
    PRICING,
    RUBRIC_VERSION,
    VARIANTS,
    _SCHEMA_CACHE,
    count_tokens,
    system_prompt_sha256,
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
    # G1 repair re-label under rubric v1.2 (owner ratification: HANDOFF §3,
    # 2026-08-26). Same model id and same max_tokens/thinking config as
    # E1's final passes — only the rubric (SYSTEM_PROMPT) changes. Every
    # output path here is NEW: E1's data/labels.parquet and
    # data/full_batch_meta.json are frozen and must not be touched.
    "v12_relabel": {
        "requests_file": "data/batch_requests_v12.jsonl",
        "canary_meta": "data/v12_relabel_batch_meta.json",
        "canary_labels": "data/labels_v12.parquet",
        "full_meta": "data/v12_relabel_batch_meta.json",
    },
}

# Variants whose request file must carry the CURRENT SYSTEM_PROMPT (i.e.
# the current labeling_rubric.md revision) byte-for-byte. The v1.2
# re-label's whole point is the rubric change, and the variant guard
# below deliberately checks only max_tokens/thinking/effort — so without
# this second guard, submitting a stale v1.1 request file would sail
# straight through and produce a very expensive no-op.
RUBRIC_PINNED_VARIANTS = {"v12_relabel"}

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

# --- --complete-missing (2026-08-26) -------------------------------------
# Completing bounced SINGLETONS, never re-running a campaign. The v1.2
# re-label batch ended 6,746/6,747: its last request errored with
# "credit balance too low" and left CHK-1c1812ed45219a3a with a row in
# data/labels_v12.parquet that has no labels and no stop_reason. The owner
# authorized completing exactly that row (2026-08-26, in chat). The
# --max-missing guard is what keeps this mode from ever quietly becoming a
# re-run of the whole corpus: 3 is a hard, low default and the operator has
# to raise it on purpose, in the command line, where it is visible.
DEFAULT_MAX_MISSING = 3
V12_COMPLETION_META_PATH = "data/v12_completion_batch_meta.json"
V12_COMPLETION_LABELS_PATH = "data/labels_v12_completion.parquet"
COMPLETION_META_MODE = "complete-missing"
COMPLETION_BACKUP_SUFFIX = ".pre_completion"

# The label columns a completed row must fill. A row counts as MISSING only
# when its stop_reason is null AND every one of these is null — i.e. the API
# returned nothing at all. A refusal (stop_reason="refusal") and a
# truncation (stop_reason="max_tokens") are ANSWERS, not bounces; they are
# deliberately NOT swept in here.
COMPLETION_LABEL_COLUMNS = (
    "sentiment",
    "guidance_direction",
    "red_flags",
    "distress_tier",
)

# Exactly the columns a merge writes back into the target parquet. Written
# out longhand rather than derived, so a schema change to either side is a
# loud KeyError-free no-op instead of a silent corpus-column overwrite: the
# frozen corpus columns (chunk_id, text, section_type, home_*, source_*)
# are not in this list and are never touched by a merge.
COMPLETION_RESULT_COLUMNS = (
    "parse_ok",
    "schema_valid",
    "api_result_type",
    "parse_error",
    "raw_label_json",
    "sentiment",
    "guidance_direction",
    "red_flags",
    "distress_tier",
    "stop_reason",
    "output_tokens",
    "batch_id",
    "max_tokens_used",
    "labeling_config",
    "rubric_version",
    "system_prompt_sha256",
    "labeled_at",
)

# Planning fallback when the target parquet carries no measured output
# tokens to average (build_batch_requests.estimate_cost's own constant).
FALLBACK_OUTPUT_TOKENS_PER_REQUEST = 90

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


def _extract_system_text(params: dict) -> str | None:
    """The system prompt as actually serialized into a request body.

    build_batch_requests.build_request() writes it as a one-element list
    of content blocks; a bare string is accepted too so the guard reads
    whatever shape is really on disk rather than assuming one.
    """
    system = params.get("system")
    if isinstance(system, str):
        return system
    if isinstance(system, list) and len(system) == 1 and isinstance(system[0], dict):
        return system[0].get("text")
    return None


def assert_requests_use_current_system_prompt(
    requests: list[dict], requests_file: str
) -> None:
    """Every request body must carry the CURRENT SYSTEM_PROMPT verbatim.

    `assert_requests_match_variant` checks max_tokens/thinking/effort and
    nothing else — by design, because that was the axis of the 2026-08-11
    incident. The 2026-08-26 v1.2 re-label moves a DIFFERENT axis: the
    rubric, which lives entirely inside the system prompt. Submitting a
    request file built against the old rubric would pass the variant
    guard, cost the full run, and return E1's labels again. So the rubric
    gets its own guard, on the same "inspect the artifact, never trust the
    filename" principle.

    Also checks the model id, since single-axis discipline (HANDOFF §3,
    2026-08-26 ruling 1) requires that the model NOT change alongside the
    rubric.
    """
    expected_sha = system_prompt_sha256()
    bad_prompt: list[tuple[str, str]] = []
    bad_model: list[tuple[str, object]] = []

    for req in requests:
        params = req.get("params", {})
        text = _extract_system_text(params)
        if text is None:
            bad_prompt.append((req.get("custom_id"), "<no system prompt in request>"))
        else:
            actual = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if actual != expected_sha:
                bad_prompt.append((req.get("custom_id"), actual))
        if params.get("model") != MODEL:
            bad_model.append((req.get("custom_id"), params.get("model")))

    if bad_prompt or bad_model:
        lines = []
        if bad_prompt:
            lines.append(
                f"{len(bad_prompt)}/{len(requests)} requests carry a system "
                f"prompt that is NOT the current rubric {RUBRIC_VERSION} "
                f"(sha256 {expected_sha[:16]}...). First few: "
                + ", ".join(f"{cid}={sha[:16]}" for cid, sha in bad_prompt[:3])
            )
        if bad_model:
            lines.append(
                f"{len(bad_model)}/{len(requests)} requests name a model other "
                f"than {MODEL!r}. First few: "
                + ", ".join(f"{cid}={m!r}" for cid, m in bad_model[:3])
            )
        raise VariantMismatchError(
            "\n\nREFUSING TO SUBMIT — rubric/model mismatch.\n"
            f"requests_file={requests_file!r}\n  " + "\n  ".join(lines) + "\n\n"
            "Nothing was submitted. Rebuild the request file from the current "
            "build_batch_requests.py before retrying."
        )

    print(
        f"Rubric guard OK: all {len(requests)} requests in {requests_file!r} "
        f"carry rubric {RUBRIC_VERSION} (system-prompt sha256 "
        f"{expected_sha[:16]}...) and model={MODEL!r}."
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


def run_poll(
    batch_id: str,
    out_path: str,
    max_wait_s: int,
    variant: str | None = None,
    merge_into: str | None = None,
) -> None:
    """Polls, parses, joins, and writes the labeled parquet.

    `merge_into` is the --complete-missing return path (2026-08-26): the
    poll still writes its own standalone parquet at `out_path` (the audit
    trail of what the completion batch returned), and THEN merges those
    rows into the named target in place via merge_completion_into(), which
    takes a backup first and refuses to overwrite any row that already
    carries an answer.

    Every output row carries its own provenance (2026-08-26): batch_id,
    stop_reason, output_tokens, labeled_at, and — when `variant` is given
    — max_tokens_used / labeling_config / rubric_version. E1's
    data/labels.parquet grew those columns in an ad-hoc merge step after
    the fact; recording them here means the v1.2 artifact is a complete,
    self-describing labels file straight out of the poll, and the refusal
    chunk is identifiable exactly the way E1 identified it
    (stop_reason == "refusal", excluded by predicate, never deleted).
    """
    cfg = VARIANTS[variant] if variant else None

    client = get_client()

    print(f"Polling batch {batch_id} (ceiling {max_wait_s}s)...")
    batch = poll_until_ended(client, batch_id, max_wait_s=max_wait_s)

    if batch.processing_status == "in_progress":
        print("Batch not yet ended; exiting without writing results.")
        return

    print(f"Batch ended: status={batch.processing_status} counts={batch.request_counts}")

    corpus_df = pd.read_parquet(CORPUS_PATH)
    section_type_by_id = dict(zip(corpus_df["chunk_id"], corpus_df["section_type"]))

    provenance = {"batch_id": batch_id}
    if cfg is not None:
        provenance["max_tokens_used"] = cfg["max_tokens"]
        thinking_mode = (cfg["thinking"] or {}).get("type", "adaptive-default")
        provenance["labeling_config"] = (
            f"thinking={thinking_mode},max_tokens={cfg['max_tokens']}"
        )
        provenance["rubric_version"] = RUBRIC_VERSION
        provenance["system_prompt_sha256"] = system_prompt_sha256()

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
                "stop_reason": None,
                "output_tokens": None,
                **provenance,
            })
            continue

        message = item.result.message
        usage = message.usage
        msg_provenance = {
            "stop_reason": getattr(message, "stop_reason", None),
            "output_tokens": usage.output_tokens,
            **provenance,
        }
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
                **msg_provenance,
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
            **msg_provenance,
        })

    labels_df = pd.DataFrame(rows)
    labels_df["labeled_at"] = pd.Timestamp.now(tz="UTC").isoformat()
    joined = corpus_df.merge(labels_df, on="chunk_id", how="right")
    joined.to_parquet(out_path)
    print(f"Wrote {len(joined)} labeled rows to {out_path}")

    if merge_into:
        print(f"\n--- MERGE INTO {merge_into} ---")
        summary = merge_completion_into(merge_into, joined, batch_id)
        print(json.dumps(summary, indent=2, default=str))

    n_refusals = int((labels_df.get("stop_reason") == "refusal").sum()) if "stop_reason" in labels_df else 0
    if n_refusals:
        refused = labels_df.loc[labels_df["stop_reason"] == "refusal", "chunk_id"].tolist()
        print(
            f"\nSAFETY REFUSALS: {n_refusals} chunk(s) returned "
            f"stop_reason='refusal' — {refused}. E1 handled its single "
            f"refusal (CHK-8e69547e0900a8dd) by EXCLUDING it by predicate "
            f"(parse_ok=False), never deleting the row. Do the same."
        )

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
    resolved_models: dict[str, int] = {}
    for item in client.messages.batches.results(batch_id):
        out_tokens = _output_tokens_from_result(item)
        if out_tokens is not None:
            msg = getattr(item.result, "message", None)
            resolved = getattr(msg, "model", None)
            if resolved:
                resolved_models[resolved] = resolved_models.get(resolved, 0) + 1
            result_records.append(
                {
                    "output_tokens": out_tokens,
                    "stop_reason": getattr(msg, "stop_reason", None),
                }
            )

    report = verify_batch_config(result_records, variant)
    # Single-axis discipline (2026-08-26): MODEL is an ALIAS
    # ('claude-sonnet-5'), not a dated snapshot, and an alias can be
    # repointed between runs. The batch results are the only place the
    # RESOLVED model id is recoverable. Run this against E1's final batch
    # (msgbatch_01KrfTWXeVN79Us9wthnGLaG) and against the v1.2 batch and
    # compare — if they differ, the model moved alongside the rubric and
    # the run is no longer single-axis.
    report["resolved_model_ids"] = resolved_models
    print(json.dumps(report, indent=2))
    if report["verdict"] == "SUSPECT_WRONG_CONFIG":
        print(
            "\nVERDICT: SUSPECT_WRONG_CONFIG — this looks like the original "
            "run_full() variant-wiring bug's signature. Do not merge these "
            "labels without further investigation.",
            file=sys.stderr,
        )


# ---------------------------------------------------------------------
# --complete-missing (2026-08-26) — finish bounced singletons.
#
# Scope discipline, stated once and enforced by the --max-missing guard
# below: this mode exists to complete a handful of rows the API never
# answered (the v1.2 batch's credit-balance bounce), NOT to re-run a
# campaign. Everything here is a pure function over already-read data
# except run_complete_missing(), which is the only part that can submit,
# and it cannot submit without --confirm-complete.
# ---------------------------------------------------------------------
def _is_missing_cell(value) -> bool:
    """True when a labels-parquet cell carries no answer at all.

    An EMPTY list is an answer ("no red flags here"), so any sized,
    non-string value is treated as present. Only None/NaN counts as
    missing.
    """
    if value is None:
        return True
    if isinstance(value, (str, bytes)):
        return False
    if hasattr(value, "__len__"):  # list / ndarray — [] is a real answer
        return False
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _as_optional_bool(value) -> bool | None:
    """numpy.bool_/None/NaN -> a real Python bool or None."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return bool(value)


def find_missing_label_rows(labels_df: pd.DataFrame) -> dict:
    """Rows the API never answered, plus an honest account of what was
    deliberately left out.

    MISSING == stop_reason is null AND all of COMPLETION_LABEL_COLUMNS are
    null. That is the signature of a request that bounced before the model
    ever ran (batch result type=errored/expired/canceled).

    NOT missing, and never completed by this mode:
      - refusals (stop_reason="refusal") — E1's CHK-8e69547e0900a8dd is a
        genuine safety refusal, excluded by predicate, never re-asked;
      - truncations (stop_reason="max_tokens") — an answer that ran out of
        room is a config problem for a variant re-run, not a bounce;
      - parse/schema failures that DID get a response.
    Those land in `excluded_answered_failures` so the operator sees exactly
    what this mode chose not to touch, rather than having to infer it.
    """
    required = ("chunk_id", "stop_reason") + COMPLETION_LABEL_COLUMNS
    absent = [c for c in required if c not in labels_df.columns]
    if absent:
        raise ValueError(
            f"Labels frame is missing required column(s) {absent}; cannot "
            f"identify unanswered rows. Present columns: "
            f"{sorted(labels_df.columns)}"
        )

    missing_ids: list[str] = []
    excluded: list[dict] = []
    for _, row in labels_df.iterrows():
        no_stop = _is_missing_cell(row["stop_reason"])
        no_labels = all(_is_missing_cell(row[c]) for c in COMPLETION_LABEL_COLUMNS)
        if no_stop and no_labels:
            missing_ids.append(row["chunk_id"])
            continue
        # Anything the run itself flagged as not-clean but that DID come
        # back with a response — reported, not completed. Note `is False`
        # would not work here: a pandas bool column yields numpy.bool_,
        # which is never identical to the Python singleton.
        parse_ok = _as_optional_bool(row.get("parse_ok"))
        schema_valid = _as_optional_bool(row.get("schema_valid"))
        if parse_ok is False or schema_valid is False:
            excluded.append(
                {
                    "chunk_id": row["chunk_id"],
                    "stop_reason": row["stop_reason"],
                    "api_result_type": row.get("api_result_type"),
                    "parse_ok": parse_ok,
                    "schema_valid": schema_valid,
                }
            )

    return {
        "n_rows": len(labels_df),
        "missing_ids": missing_ids,
        "n_missing": len(missing_ids),
        "excluded_answered_failures": excluded,
        "n_excluded_answered_failures": len(excluded),
    }


def select_completion_requests(
    missing_ids: list[str], requests_by_id: dict[str, dict], requests_file: str
) -> list[dict]:
    """EXACTLY the named custom_ids' request bodies, in the given order.

    Refuses on any id the requests file doesn't carry: submitting a
    partial set would leave a row unlabeled while the meta file claimed
    the completion was done.
    """
    absent = [cid for cid in missing_ids if cid not in requests_by_id]
    if absent:
        raise VariantMismatchError(
            f"\n\nREFUSING TO SUBMIT — {len(absent)} unanswered chunk_id(s) "
            f"have no request in {requests_file!r}: {absent[:5]}\n"
            f"The labels parquet and the requests file are out of sync. "
            f"Nothing was submitted."
        )
    return [requests_by_id[cid] for cid in missing_ids]


def _request_user_text(params: dict) -> str:
    messages = params.get("messages") or []
    if not messages:
        return ""
    content = messages[0].get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "") for b in content if isinstance(b, dict)
        )
    return ""


def measure_output_tokens_estimate(
    labels_df: pd.DataFrame, section_types: list[str]
) -> tuple[float, int]:
    """Mean measured output_tokens over already-answered rows of the same
    section_type(s). Returns (mean, n_observations).

    Measured beats guessed: this reuses the very batch that bounced, so
    the printed estimate is anchored on that run's own completions rather
    than a planning constant. Falls back to
    FALLBACK_OUTPUT_TOKENS_PER_REQUEST when there is nothing to average.
    """
    if "output_tokens" not in labels_df.columns or not section_types:
        return float(FALLBACK_OUTPUT_TOKENS_PER_REQUEST), 0
    sub = labels_df
    if "section_type" in labels_df.columns:
        sub = labels_df[labels_df["section_type"].isin(section_types)]
    observed = pd.to_numeric(sub["output_tokens"], errors="coerce").dropna()
    if observed.empty:
        return float(FALLBACK_OUTPUT_TOKENS_PER_REQUEST), 0
    return float(observed.mean()), int(len(observed))


def estimate_completion_cost(
    requests: list[dict], output_tokens_per_request: float
) -> dict:
    """Planning cost for a small completion batch, per pricing tier.

    Counted off the REQUEST BODIES actually about to be submitted (system
    text, passage, JSON schema), not off a corpus average — the point of
    printing this before --confirm-complete is that it describes this
    submission and no other.

    Conservative on caching: a batch this small has no warm cache to read
    from, so every request is charged a full 1h cache WRITE on its system
    prefix (the most expensive assumption available). Real billed usage is
    reported by --poll afterwards; this is an estimate, not a quote.
    """
    cache_write_tokens = 0
    plain_input_tokens = 0
    for req in requests:
        params = req.get("params", {})
        cache_write_tokens += count_tokens(_extract_system_text(params) or "")
        plain_input_tokens += count_tokens(_request_user_text(params))
        schema = (params.get("output_config") or {}).get("format", {}).get("schema")
        if schema is not None:
            plain_input_tokens += count_tokens(json.dumps(schema))

    total_output_tokens = output_tokens_per_request * len(requests)

    by_tier = {}
    for tier, price in PRICING.items():
        cost = (
            cache_write_tokens * price["input"] * CACHE_WRITE_1H_MULTIPLIER
            + plain_input_tokens * price["input"]
            + total_output_tokens * price["output"]
        ) / 1e6 * BATCH_DISCOUNT
        by_tier[tier] = round(cost, 6)

    return {
        "n_requests": len(requests),
        "cache_write_input_tokens_est": cache_write_tokens,
        "plain_input_tokens_est": plain_input_tokens,
        "output_tokens_per_request_est": round(output_tokens_per_request, 2),
        "total_output_tokens_est": round(total_output_tokens, 2),
        "cost_usd_by_tier": by_tier,
        "assumptions": (
            "Batch discount applied; every request charged a full 1h cache "
            "WRITE on its system prefix (no warm cache at this batch size); "
            "token counts are the cl100k_base proxy, not Claude's tokenizer."
        ),
    }


def _assert_completion_meta_path_is_safe(meta_path: str) -> None:
    """Never clobber another run's provenance record.

    Same failure class as the 2026-08-11 variant-wiring bug and the
    2026-08-26 full_batch_meta.json fix: a meta file is the only record of
    what a batch actually was, so writing this mode's meta over a
    different mode's meta destroys evidence.
    """
    p = Path(meta_path)
    if not p.exists():
        return
    try:
        existing = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        raise VariantMismatchError(
            f"\n\nREFUSING TO SUBMIT — {meta_path!r} exists but is not readable "
            f"JSON, so it cannot be confirmed to be a completion-batch meta "
            f"file. Move it aside or point --complete-meta somewhere new."
        )
    if existing.get("mode") != COMPLETION_META_MODE:
        raise VariantMismatchError(
            f"\n\nREFUSING TO SUBMIT — {meta_path!r} already holds a "
            f"mode={existing.get('mode')!r} batch's provenance "
            f"(batch_id={existing.get('batch_id')!r}). Writing this "
            f"completion's meta there would erase it. Nothing was submitted."
        )
    print(
        f"NOTE: overwriting a previous completion meta at {meta_path!r} "
        f"(batch_id={existing.get('batch_id')!r})."
    )


def run_complete_missing(
    against: str,
    variant: str,
    requests_file: str,
    meta_path: str = V12_COMPLETION_META_PATH,
    max_missing: int = DEFAULT_MAX_MISSING,
    confirm: bool = False,
) -> int:
    """Submit ONLY the rows an existing labels parquet never got answers
    for. Returns a process exit code.

    Order is deliberate: identify → count-guard → extract → variant guard
    → rubric guard → PRINT count + cost → confirm gate → submit. Every
    refusal happens before a client is ever constructed.
    """
    labels_df = pd.read_parquet(against)
    found = find_missing_label_rows(labels_df)
    missing_ids = found["missing_ids"]

    print(f"--complete-missing against {against!r}: {found['n_rows']} rows")
    print(f"  unanswered (no stop_reason, no labels): {found['n_missing']}")
    print(
        f"  answered-but-flagged rows NOT completed by this mode: "
        f"{found['n_excluded_answered_failures']}"
    )
    for row in found["excluded_answered_failures"][:5]:
        print(f"    - {row['chunk_id']} stop_reason={row['stop_reason']!r} "
              f"api_result_type={row['api_result_type']!r} (left as-is)")

    if not missing_ids:
        print("\nNothing to complete — every row carries an answer. Exiting 0.")
        return 0

    if len(missing_ids) > max_missing:
        print(
            f"\nREFUSING TO SUBMIT — {len(missing_ids)} unanswered rows exceeds "
            f"--max-missing={max_missing}.\nThis mode completes bounced "
            f"singletons; it is not a campaign re-runner. If a re-run is "
            f"genuinely intended, that is a --full run with its own owner "
            f"ratification and its own cost gate. Nothing was submitted.",
            file=sys.stderr,
        )
        return 1

    print(f"\nUnanswered chunk_ids to complete: {missing_ids}")

    requests_by_id = load_requests_by_custom_id(path=requests_file)
    batch_requests = select_completion_requests(
        missing_ids, requests_by_id, requests_file
    )

    # Same two choke points every other submit path passes through — the
    # completion batch is a real submission and gets no discount on guards.
    assert_requests_match_variant(batch_requests, variant, requests_file)
    if variant in RUBRIC_PINNED_VARIANTS:
        assert_requests_use_current_system_prompt(batch_requests, requests_file)
    else:
        print(
            f"Rubric guard NOT APPLICABLE for variant={variant!r} (not in "
            f"RUBRIC_PINNED_VARIANTS)."
        )

    section_types = []
    if "section_type" in labels_df.columns:
        section_types = sorted(
            set(
                labels_df.loc[
                    labels_df["chunk_id"].isin(missing_ids), "section_type"
                ].tolist()
            )
        )
    out_tokens_est, n_observed = measure_output_tokens_estimate(
        labels_df, section_types
    )
    cost = estimate_completion_cost(batch_requests, out_tokens_est)
    cost["output_tokens_basis"] = (
        f"mean measured output_tokens over {n_observed} answered "
        f"section_type={section_types} row(s) in {against}"
        if n_observed
        else f"planning fallback ({FALLBACK_OUTPUT_TOKENS_PER_REQUEST} tokens/request)"
    )

    print("\n--- ABOUT TO SUBMIT ---")
    print(f"  requests: {len(batch_requests)}")
    print(f"  variant: {variant!r}  requests_file: {requests_file!r}")
    print(f"  estimated cost: {json.dumps(cost, indent=2)}")
    print(
        "  (intro-tier pricing runs through 2026-08-31; the standard-tier "
        "figure is what this costs after that.)"
    )

    if not confirm:
        print(
            "\nNOT SUBMITTED — --complete-missing requires --confirm-complete. "
            "Re-run with it once the count and the cost above are what you "
            "expect.",
            file=sys.stderr,
        )
        return 1

    _assert_completion_meta_path_is_safe(meta_path)

    client = get_client()
    batch = client.messages.batches.create(requests=batch_requests)

    meta = {
        "batch_id": batch.id,
        "mode": COMPLETION_META_MODE,
        "variant": variant,
        "requests_file": requests_file,
        "against": against,
        "n_submitted": len(batch_requests),
        "custom_ids": missing_ids,
        "max_missing_guard": max_missing,
        "n_rows_in_target": found["n_rows"],
        "n_excluded_answered_failures": found["n_excluded_answered_failures"],
        "model": MODEL,
        "asserted_max_tokens": VARIANTS[variant]["max_tokens"],
        "asserted_thinking": (VARIANTS[variant]["thinking"] or {}).get(
            "type", "adaptive-default"
        ),
        "rubric_version": RUBRIC_VERSION,
        "system_prompt_sha256": system_prompt_sha256(),
        "estimated_cost": cost,
        "submitted_at": batch.created_at.isoformat()
        if hasattr(batch.created_at, "isoformat")
        else str(batch.created_at),
        "processing_status": batch.processing_status,
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, default=str)

    print(
        f"\nSubmitted COMPLETION batch: {batch.id} "
        f"({len(batch_requests)} request(s), variant={variant})"
    )
    print(f"Wrote {meta_path}")
    return 0


def merge_completion_into(
    target_path: str,
    completion_df: pd.DataFrame,
    batch_id: str,
    backup_suffix: str = COMPLETION_BACKUP_SUFFIX,
) -> dict:
    """Merge completed rows INTO an existing labels parquet, in place.

    Invariants, all checked BEFORE anything is written:
      - every completed chunk_id must exist in the target;
      - every one of them must still be UNANSWERED in the target — a merge
        may never overwrite a label the target already has;
      - a completion row that itself came back unanswered is skipped, not
        merged (retrying a bounce can bounce again).
    Then a backup copy is made (refusing if one already exists, since that
    backup is the only surviving pre-merge state), then the label columns
    are written and each merged row is stamped with `completion_batch_id`.
    """
    target = pd.read_parquet(target_path)
    if "chunk_id" not in target.columns:
        raise ValueError(f"{target_path!r} has no chunk_id column.")

    target_missing = set(find_missing_label_rows(target)["missing_ids"])
    index_by_id = {cid: idx for idx, cid in zip(target.index, target["chunk_id"])}

    incoming = find_missing_label_rows(completion_df)
    still_unanswered = set(incoming["missing_ids"])

    to_merge, skipped = [], []
    for _, row in completion_df.iterrows():
        cid = row["chunk_id"]
        if cid not in index_by_id:
            raise ValueError(
                f"REFUSING TO MERGE — completed chunk_id {cid!r} is not in "
                f"{target_path!r}. Nothing was written."
            )
        if cid in still_unanswered:
            skipped.append(cid)
            continue
        if cid not in target_missing:
            raise ValueError(
                f"REFUSING TO MERGE — {cid!r} already carries an answer in "
                f"{target_path!r}. This mode completes unanswered rows only; "
                f"overwriting existing labels would be a re-label, which needs "
                f"its own ratification. Nothing was written."
            )
        to_merge.append(row)

    backup_path = target_path + backup_suffix
    if to_merge:
        if Path(backup_path).exists():
            raise FileExistsError(
                f"REFUSING TO MERGE — backup {backup_path!r} already exists, so "
                f"a merge has already run against this target. Overwriting it "
                f"would destroy the only pre-merge copy. Move it aside first. "
                f"Nothing was written."
            )
        shutil.copy2(target_path, backup_path)
        print(f"Backed up {target_path} -> {backup_path}")

        if "completion_batch_id" not in target.columns:
            target["completion_batch_id"] = None
        target["completion_batch_id"] = target["completion_batch_id"].astype(object)

        for row in to_merge:
            idx = index_by_id[row["chunk_id"]]
            for col in COMPLETION_RESULT_COLUMNS:
                if col in target.columns and col in completion_df.columns:
                    target.at[idx, col] = row[col]
            target.at[idx, "completion_batch_id"] = batch_id

        target.to_parquet(target_path)
        print(
            f"Merged {len(to_merge)} completed row(s) into {target_path} "
            f"(completion_batch_id={batch_id})"
        )

    remaining = find_missing_label_rows(pd.read_parquet(target_path))
    summary = {
        "target_path": target_path,
        "backup_path": backup_path if to_merge else None,
        "batch_id": batch_id,
        "n_merged": len(to_merge),
        "merged_ids": [r["chunk_id"] for r in to_merge],
        "n_skipped_still_unanswered": len(skipped),
        "skipped_ids": skipped,
        "n_missing_after": remaining["n_missing"],
        "missing_after_ids": remaining["missing_ids"],
    }
    if skipped:
        print(
            f"NOT merged — {len(skipped)} completion row(s) came back "
            f"unanswered again: {skipped}. Target unchanged for those.",
            file=sys.stderr,
        )
    print(f"Rows still unanswered in {target_path}: {remaining['n_missing']}")
    return summary


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
        "--complete-missing", action="store_true",
        help="Complete the rows an existing labels parquet (--against) never "
             "got answers for: extract exactly those custom_ids from the "
             "--variant's request file and submit them as a small batch. "
             "Refuses above --max-missing (default 3) — this completes "
             "bounced singletons, never re-runs a campaign. Prints the "
             "request count and estimated cost, then requires "
             "--confirm-complete to submit anything.",
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
    parser.add_argument(
        "--against",
        default=None,
        help="Existing labels parquet to scan for unanswered rows "
             "(--complete-missing). Required for that mode.",
    )
    parser.add_argument(
        "--max-missing", type=int, default=DEFAULT_MAX_MISSING,
        help=f"--complete-missing refuses to run if more than this many rows "
             f"are unanswered (default {DEFAULT_MAX_MISSING}).",
    )
    parser.add_argument(
        "--confirm-complete", action="store_true",
        help="Required alongside --complete-missing to actually submit.",
    )
    parser.add_argument(
        "--complete-meta", default=V12_COMPLETION_META_PATH,
        help=f"Where --complete-missing writes its batch meta "
             f"(default {V12_COMPLETION_META_PATH}).",
    )
    parser.add_argument(
        "--merge-into",
        default=None,
        help="With --poll: merge the polled results INTO this labels parquet "
             "in place, after copying it to <path>.pre_completion. Only "
             "unanswered rows may be filled; existing labels are never "
             "overwritten.",
    )

    args = parser.parse_args()

    if args.variant and args.requests_file:
        print("Pass either --variant or --requests-file, not both.", file=sys.stderr)
        sys.exit(1)

    if args.merge_into and not args.poll:
        print(
            "--merge-into is only meaningful with --poll (it merges a polled "
            "completion batch's results into an existing labels parquet).",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.complete_missing:
        if not args.against:
            print(
                "--complete-missing requires --against <labels.parquet> (the "
                "artifact whose unanswered rows are being completed).",
                file=sys.stderr,
            )
            sys.exit(1)
        if not args.variant:
            print(
                "--complete-missing requires --variant, so the requests are "
                "pulled from the right file and both submit guards (variant + "
                "rubric) have a named config to check against.",
                file=sys.stderr,
            )
            sys.exit(1)
        sys.exit(
            run_complete_missing(
                against=args.against,
                variant=args.variant,
                requests_file=VARIANT_PATHS[args.variant]["requests_file"],
                meta_path=args.complete_meta,
                max_missing=args.max_missing,
                confirm=args.confirm_complete,
            )
        )

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
            # A variant may declare its own full-run meta path. Without
            # that, run_full's default is data/full_batch_meta.json — E1's
            # frozen provenance record, which must never be overwritten.
            if "full_meta" in vp:
                run_full(
                    variant=args.variant,
                    requests_file=vp["requests_file"],
                    meta_path=vp["full_meta"],
                )
            else:
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
        elif args.merge_into:
            # A completion poll's standalone parquet is an audit artifact,
            # never the merge target itself.
            out = V12_COMPLETION_LABELS_PATH
        elif args.variant:
            out = VARIANT_PATHS[args.variant]["canary_labels"]
        else:
            out = CANARY_LABELS_PATH
        if args.merge_into and out == args.merge_into:
            print(
                "--out and --merge-into must differ: --out is the completion "
                "batch's own result file, --merge-into is the artifact it is "
                "merged into.",
                file=sys.stderr,
            )
            sys.exit(1)
        run_poll(
            args.poll,
            out_path=out,
            max_wait_s=args.max_wait_s,
            variant=args.variant,
            merge_into=args.merge_into,
        )
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

    # Second choke point (2026-08-26): for rubric-pinned variants the
    # system prompt IS the thing under test, and the variant guard above
    # does not look at it. Never silent — say which branch was taken.
    if variant in RUBRIC_PINNED_VARIANTS:
        assert_requests_use_current_system_prompt(all_requests, requests_file)
    else:
        print(
            f"Rubric guard NOT APPLICABLE for variant={variant!r} (not in "
            f"RUBRIC_PINNED_VARIANTS). Its request file is E1-era audit "
            f"trail built against an earlier rubric revision; the current "
            f"revision is {RUBRIC_VERSION}."
        )

    client = get_client()
    batch = client.messages.batches.create(requests=all_requests)
    meta = {
        "batch_id": batch.id,
        "mode": "full",
        "variant": variant,
        "requests_file": requests_file,
        "n_submitted": len(all_requests),
        "model": MODEL,
        "asserted_max_tokens": VARIANTS[variant]["max_tokens"],
        "asserted_thinking": (VARIANTS[variant]["thinking"] or {}).get("type", "adaptive-default"),
        "rubric_version": RUBRIC_VERSION,
        "system_prompt_sha256": system_prompt_sha256(),
        "processing_status": batch.processing_status,
    }
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2, default=str)
    print(f"Submitted FULL batch: {batch.id} ({len(all_requests)} requests, variant={variant})")
    print(f"Wrote {meta_path}")


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
