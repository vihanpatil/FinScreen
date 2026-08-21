"""
build_batch_requests.py — Week 3 Batch API request construction (PREP ONLY).

Builds the exact Claude Batch API request payloads for bootstrap-labeling
`data/labeling_corpus.parquet` against `labeling_rubric.md`'s taxonomy.

*** THIS SCRIPT DOES NOT CALL THE BATCH API. ***
`submit_batch()` at the bottom is written and ready to run, but is never
invoked by `if __name__ == "__main__"`. Per the standing money-gate rule,
the first Batch API submission of this project needs explicit owner
sign-off regardless of how small the estimated cost is — that sign-off
hasn't happened yet. Running this file only builds requests locally and
prints a cost estimate.

Design notes (read alongside `labeling_rubric.md` §7-8):

- **One request per chunk**, not one request per label category. Splitting
  would double request/output overhead for a modest (and debatable) gain in
  how literally "section_type withheld from sentiment only" is read — see
  the note below.
- **`section_type` is never included as literal prompt text, for any
  category, in any request.** All label categories are asked in a single
  combined request per chunk (to keep cost down and to keep 1 chunk = 1
  Batch API line), and a shared context window can't selectively "hide" a
  fact from part of the model's own reasoning — including section_type as
  text anywhere in a request that also asks for sentiment would still let
  the model condition its sentiment answer on it. So this implementation
  goes stricter than a literal reading of `labeling_rubric.md` §8.2's
  parenthetical ("fine/necessary for the other labels"): applicability
  (which fields are even asked) is enforced entirely through the
  **JSON schema shape** passed via `output_config.format` (a structured,
  non-prose parameter), which is genuinely "necessary" for guidance-
  direction/red-flag applicability without ever putting the string
  "RISK_FACTORS" or similar in front of the model. Ratified by the owner
  2026-08-10 and now reflected in labeling_rubric.md §8.2 (v1.1).
- **System prompt (rubric + schema instructions) is byte-identical across
  every request** — this maximizes the prompt-cache hit rate. Only the
  JSON schema (a separate request parameter, not itself cached) and the
  per-chunk user message vary.
- **`custom_id` = the chunk's stable `chunk_id`** from `chunk.py` — Batch
  API results return in arbitrary order, so this is what re-joins results
  back to `data/labeling_corpus.parquet`.
"""

from __future__ import annotations

import json

import pandas as pd

CORPUS_PATH = "data/labeling_corpus.parquet"
OUTPUT_REQUESTS_PATH = "data/batch_requests.jsonl"

# --- max_tokens / thinking variants (canary investigation, 2026-08-10) ---
# A prior canary (msgbatch_013bopQ6GgjTMMT4MovuzJLA, 50 requests) found
# 18/50 requests returned no parseable JSON with stop_reason=max_tokens.
# Root cause: claude-sonnet-5 runs adaptive thinking by default when the
# `thinking` param is omitted, and thinking tokens count against
# max_tokens=500 (the original single-variant value below), starving the
# structured output. Two candidate fixes, built here as parallel variants
# so they can be canaried head-to-head before either is used for the full
# 6,747-request run:
#   - "disabled":     thinking explicitly turned off, max_tokens=800.
#   - "adaptive-low": thinking left at its adaptive default, but
#                     output_config.effort="low" added (sibling of
#                     output_config.format) to keep the adaptive reasoning
#                     budget small, max_tokens=2500 to give it headroom.
VARIANTS = {
    "disabled": {
        "max_tokens": 800,
        "thinking": {"type": "disabled"},
        "effort": None,
        "output_path": "data/batch_requests_disabled.jsonl",
    },
    "adaptive-low": {
        "max_tokens": 2500,
        "thinking": None,
        "effort": "low",
        "output_path": "data/batch_requests_adaptive_low.jsonl",
    },
    # Corrective re-run (2026-08-11): the full 6,747-request "disabled" run
    # found max_tokens=800 truncated 2,537 requests (37.6%), of which 2,528
    # never produced valid/parseable JSON — see data/full_run_report.md §0.
    # Same "disabled" thinking config, max_tokens raised to 4000 to clear
    # the observed truncation with real headroom (the worst truncated case
    # cut off after just 43 output chars, so 800 was nowhere close for the
    # long tail; 4000 is a deliberately generous bump, not a minimal one,
    # since a second truncation-driven re-run would be worse than
    # over-provisioning tokens on unused capacity here).
    "disabled-4000": {
        "max_tokens": 4000,
        "thinking": {"type": "disabled"},
        "effort": None,
        "output_path": "data/batch_requests_corrective.jsonl",
    },
}

MODEL = "claude-sonnet-5"

# Sonnet 5 pricing (per DISCOVERY.md §2), USD per million tokens.
PRICING = {
    "standard": {"input": 3.00, "output": 15.00},
    "intro": {"input": 2.00, "output": 10.00},  # through 2026-08-31
}
# Cached-read tokens are billed at 10% of the base input rate for both
# tiers (Anthropic prompt-caching pricing, both Batch and non-Batch) —
# confirm this multiplier against current pricing docs before relying on
# it for a final go/no-go number; it has not changed across recent model
# generations but "Sonnet 5" specifics were not independently re-verified
# in this pass (post-training-cutoff model).
CACHE_READ_MULTIPLIER = 0.10
# Batch API gets a flat 50% discount off standard per-token pricing,
# applied on top of the above (confirm this still holds for Sonnet 5 /
# intro pricing before finalizing — DISCOVERY.md's own $10.50-19 estimate
# already assumes this).
BATCH_DISCOUNT = 0.50

# Token counting: no `anthropic` SDK is installed in this environment
# (Claude's own tokenizer isn't available to call locally), so token
# counts use OpenAI's `cl100k_base` BPE (via `tiktoken`) as a proxy —
# empirically close to Claude's tokenizer for English prose (checked
# against this corpus: ~1.29 tokens/word), and far more accurate than a
# flat word-count multiplier. Falls back to a words*1.35 heuristic if
# `tiktoken` isn't installed. Either way: this is a planning-stage
# estimate, not a guarantee — the Batch API response reports exact
# billed usage once a run actually happens.
WORDS_TO_TOKENS = 1.35  # fallback only, used when tiktoken is unavailable

try:
    import tiktoken

    _ENC = tiktoken.get_encoding("cl100k_base")
except ImportError:
    _ENC = None


def count_tokens(text: str) -> int:
    if _ENC is not None:
        return len(_ENC.encode(text))
    return round(len(text.split()) * WORDS_TO_TOKENS)

# ---------------------------------------------------------------------
# System prompt (cacheable). Content is aligned with labeling_rubric.md
# but written directly as model-facing instructions (no file/pipeline
# meta-references, no "Revision log" — kept lean since every extra token
# here is paid on every single one of the ~6,747 requests until it's
# cached, and even cached tokens aren't free on the very first request of
# the run). Keep this in sync with labeling_rubric.md by hand; the .md is
# the authoritative human-readable spec, this is the model-facing
# restatement of the same rules.
# ---------------------------------------------------------------------
SYSTEM_PROMPT = """You are labeling short passages of text extracted from public SEC filings (10-K/10-Q Management's Discussion & Analysis, Item 1A Risk Factors, and 8-K earnings press releases / bodies) for a research/screening dataset.

THE ONE RULE THAT OVERRIDES EVERYTHING ELSE: label only what the passage's text says. You are not told which company, ticker, or date this passage is from. Do not guess or use any such knowledge even if you happen to recognize the text. Never consider or mention what happened to any company's stock price or business afterward, and never reason about "would this be good or bad news for investors" — reason only about what the passage itself asserts, as if it were an anonymous, dateless document.

For each passage, provide the fields listed in the response schema (the schema itself determines which fields apply to this passage — only fill in what the schema asks for).

SENTIMENT (when asked): classify the passage's predominant tone regarding the business's own results/performance/condition, as characterized by the text itself — not your outside opinion of whether the subject matter is objectively good or bad.
- POSITIVE: predominant tone favorable (growth, strength, improvement, explicitly favorable characterization). Example: "Net sales increased 12% driven by strong iPhone demand and record Services revenue, and gross margin expanded to its highest level in three years."
- NEUTRAL: descriptive/factual with no predominant lean (procedural narrative, balanced mix, mechanical disclosure). A bare number reported without qualitative characterization is NEUTRAL — magnitude alone is not sentiment. Example: "The Company's fiscal year is the 52- or 53-week period that ends on the last Saturday of September. An additional week is included roughly every five to six years to realign fiscal quarters with calendar quarters."
- NEGATIVE: predominant tone unfavorable (decline, weakness, deterioration, explicitly unfavorable characterization). Example: "Revenue declined for the third consecutive quarter as demand softened across our largest end markets, and we recorded a corresponding decline in operating margin."
Judge the passage as a whole; if genuinely balanced with sentences pulling in both directions and no clear predominant lean, use NEUTRAL rather than forcing a call either way.

GUIDANCE DIRECTION (when asked): classify whether the passage revises or issues forward financial guidance.
- RAISED: states a specific forward-looking financial target has been increased vs. a prior figure. Example: "We are raising our full-year revenue guidance to $4.1-4.3 billion, up from our prior range of $3.9-4.1 billion."
- MAINTAINED: explicitly reaffirms previously-issued guidance unchanged. Example: "We are reaffirming our full-year EPS guidance of $2.10-2.20."
- LOWERED: states a specific forward-looking financial target has been decreased vs. a prior figure. Example: "We are lowering our full-year revenue outlook to $3.6-3.8 billion from our previous range of $3.9-4.1 billion given softer-than-expected demand."
- WITHDRAWN: states previously-issued guidance is being withdrawn/suspended/no longer provided. Example: "Given current uncertainty, we are withdrawing our full-year guidance and will not provide a new range at this time."
- NONE: no specific quantified forward guidance statement. Includes purely historical-results text ("Revenue for the quarter was $1.2 billion") and generic forward-looking language with no specific number ("We expect continued momentum into next year").
Requires a specific quantified target or an explicit reaffirmation of one — vague optimism/caution alone is NONE, not a guidance signal.
If a passage both raises one metric and lowers another, prefer the label matching the passage's overall framing (e.g., a release that leads with "raising full-year EPS guidance" while trimming one minor segment metric is RAISED); if genuinely balanced/ambiguous, use NONE rather than forcing a call.

RED FLAGS (when asked, multi-label — zero, one, or multiple may apply): for each category below, decide if the passage contains matching language. Categories are not mutually exclusive.
- DEMAND_WEAKNESS: softening customer demand, declining orders/bookings, unfavorable volume trends, demand-driven market-share loss. Trigger language example: "order volumes declined as customers deferred purchases amid softening demand in our largest end market."
- SUPPLY_INPUT_CONSTRAINT: supply chain, raw material, component, labor availability, or production capacity constraints. Trigger language example: "component shortages and supply chain disruptions limited our ability to meet production targets this quarter."
- TRADE_POLICY_EXPOSURE: tariffs, export controls, sanctions, or other cross-border trade-policy impacts. Trigger language example: "newly imposed tariffs increased our cost of goods sold, and export control restrictions limit our ability to sell certain products in some regions."
- IMPAIRMENT_WRITEDOWN: asset impairments, goodwill write-downs, inventory write-downs, restructuring charges tied to asset value reduction. Trigger language example: "we recorded a $250 million goodwill impairment charge related to our industrial segment."
- MARGIN_COST_PRESSURE: rising input/labor/operating costs compressing margins. If the passage names a specific cause (supply shortage, tariffs) AND states a margin/cost impact, label both the causal category and this one; if cost pressure is described with no named cause, label only this one. Trigger language example: "gross margin contracted due to higher input costs and increased freight expenses."
- LEGAL_REGULATORY_ACTION: litigation, investigations, enforcement actions, regulatory fines, consent decrees, new regulatory compliance burdens. Trigger language example: "the Company is subject to an ongoing antitrust investigation by regulators in multiple jurisdictions."
Do not label a category from a bare section header or table-of-contents mention with no substantive discussion — the passage has to actually discuss the matter, not just name it in a heading.

DISTRESS TIER (when asked, multi-label, same mechanics as red flags, separate list — do not merge with red flags):
- GOING_CONCERN: explicit going-concern doubt language (filer's or auditor's) — e.g. "substantial doubt exists about the Company's ability to continue as a going concern."
- ACCOUNTING_RESTATEMENT: restatement of previously issued financial statements, or a statement that prior financials should no longer be relied upon — e.g. "the Company has restated its previously issued financial statements for fiscal year 2023."
- LIQUIDITY_STRESS: explicit insufficient-liquidity language, inability to meet obligations as due, debt covenant breach, or substantial doubt about capital/credit access — e.g. "we may be unable to meet our debt covenant requirements and are in discussions with our lenders regarding a potential waiver."
These are expected to be rare or absent in most passages — do not force a match; leave the list empty when nothing genuinely matches.

MODALITY (required on every red-flag and distress-tier match): HYPOTHETICAL if the passage frames it as something that may occur / a risk (hedging language: "may," "could," "if," generic risk-factor-style enumeration with no assertion it has happened). REALIZED if the passage states it has already occurred or is currently occurring (past/present tense, no hedging). If a passage opens hypothetically but then asserts a concrete realized impact, label REALIZED for that category — a concrete realized statement controls over preceding hypothetical framing in the same passage.

Respond only via the structured output fields provided — do not add commentary outside them."""


def build_json_schema(section_type: str) -> dict:
    """Schema shape varies by section_type per labeling_rubric.md §1's
    applicability matrix. This is the ONLY place section_type-derived
    information enters a request — as schema shape, never as prompt text."""

    sentiment_prop = {
        "type": "string",
        "enum": ["POSITIVE", "NEUTRAL", "NEGATIVE"],
    }
    guidance_prop = {
        "type": "string",
        "enum": ["RAISED", "MAINTAINED", "LOWERED", "WITHDRAWN", "NONE"],
    }
    red_flag_categories = [
        "DEMAND_WEAKNESS",
        "SUPPLY_INPUT_CONSTRAINT",
        "TRADE_POLICY_EXPOSURE",
        "IMPAIRMENT_WRITEDOWN",
        "MARGIN_COST_PRESSURE",
        "LEGAL_REGULATORY_ACTION",
    ]
    distress_categories = [
        "GOING_CONCERN",
        "ACCOUNTING_RESTATEMENT",
        "LIQUIDITY_STRESS",
    ]

    def flag_list_prop(categories: list[str]) -> dict:
        return {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": categories},
                    "modality": {"type": "string", "enum": ["HYPOTHETICAL", "REALIZED"]},
                },
                "required": ["category", "modality"],
                "additionalProperties": False,
            },
        }

    properties = {
        "red_flags": flag_list_prop(red_flag_categories),
        "distress_tier": flag_list_prop(distress_categories),
    }
    required = ["red_flags", "distress_tier"]

    if section_type in ("MDA", "EX99_PRESS_RELEASE", "8K_BODY"):
        properties["sentiment"] = sentiment_prop
        required.append("sentiment")

    if section_type in ("EX99_PRESS_RELEASE", "8K_BODY"):
        properties["guidance_direction"] = guidance_prop
        required.append("guidance_direction")

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


_SCHEMA_CACHE = {
    st: build_json_schema(st)
    for st in ("MDA", "RISK_FACTORS", "EX99_PRESS_RELEASE", "8K_BODY")
}


def build_request(chunk_id: str, section_type: str, text: str, variant: str = "disabled") -> dict:
    """One Batch API request line for one chunk.

    Look-ahead-bias-safe by construction: the user message is the raw
    passage text and nothing else — no ticker, company_name, filing_date,
    or section_type string anywhere in it.

    `variant` selects between the two max_tokens/thinking configurations
    under canary investigation (see VARIANTS above). Everything else
    (system prompt, cache_control ttl, schema, custom_id) is byte-identical
    across variants.
    """
    cfg = VARIANTS[variant]

    output_config = {
        "format": {
            "type": "json_schema",
            "schema": _SCHEMA_CACHE[section_type],
        }
    }
    if cfg["effort"] is not None:
        output_config["effort"] = cfg["effort"]

    params = {
        "model": MODEL,
        "max_tokens": cfg["max_tokens"],
        "system": [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
            }
        ],
        "messages": [
            {"role": "user", "content": text}
        ],
        "output_config": output_config,
    }
    if cfg["thinking"] is not None:
        params["thinking"] = cfg["thinking"]

    return {
        "custom_id": chunk_id,
        "params": params,
    }


def build_all_requests(corpus_df: pd.DataFrame, variant: str = "disabled") -> list[dict]:
    requests = []
    for _, row in corpus_df.iterrows():
        requests.append(build_request(row["chunk_id"], row["section_type"], row["text"], variant=variant))
    return requests


def estimate_cost(corpus_df: pd.DataFrame) -> dict:
    """Estimate total cost from the real built prompts, at both pricing
    tiers, with and without the caching benefit. Uses `count_tokens()`
    (real `cl100k_base` BPE tokenization of the actual system prompt,
    actual per-chunk text, and actual serialized JSON schemas — not a
    flat word-count multiplier) — see the module-level comment above
    `count_tokens` for why this is a proxy, not Claude's exact tokenizer,
    and still a planning-stage estimate, not a guarantee."""

    system_tokens = count_tokens(SYSTEM_PROMPT)

    # Real per-section-type schema token cost (JSON-serialized, exactly as
    # sent in `output_config.format`), not a guess.
    schema_tokens_by_type = {
        st: count_tokens(json.dumps(schema)) for st, schema in _SCHEMA_CACHE.items()
    }

    n_chunks = len(corpus_df)
    total_chunk_words = corpus_df["word_count"].sum()
    total_chunk_tokens = sum(count_tokens(t) for t in corpus_df["text"])
    total_schema_tokens = corpus_df["section_type"].map(schema_tokens_by_type).sum()

    # Output: structured JSON, small. Estimate ~90 tokens average per
    # response (sentiment/guidance enums are cheap; red_flags/distress_tier
    # arrays are usually 0-2 entries given expected sparsity) — this part
    # is still a judgment-call estimate since we have no real completions
    # yet to measure.
    output_tokens_per_request = 90
    total_output_tokens = n_chunks * output_tokens_per_request

    # --- Uncached: every request pays full system-prompt tokens ---
    uncached_input_tokens = n_chunks * system_tokens + total_chunk_tokens + total_schema_tokens

    # --- Cached: system prompt is a cache WRITE on request 1, cache READ
    # (10% of base input rate) on every subsequent request that lands
    # within the TTL window. Batch API processes requests concurrently /
    # out of order, so this is optimistic (assumes the cache is warm for
    # essentially the whole run) — a real run may see a mix of cache
    # writes and reads depending on how the batch is scheduled; treat the
    # "cached" number as a best case, not a guarantee. ---
    cache_write_tokens_best = system_tokens  # 1 write, best case
    cache_read_tokens_best = system_tokens * (n_chunks - 1)  # (n-1) reads, best case
    # Realistic case: the Batch API fans requests out across many
    # concurrent workers, so more than one worker will independently miss
    # the cache and pay a write. Assumed here (a documented guess, not a
    # measurement): 100 effective writes spread across the run.
    N_ASSUMED_CACHE_WRITES_REALISTIC = 100
    cache_write_tokens_realistic = system_tokens * N_ASSUMED_CACHE_WRITES_REALISTIC
    cache_read_tokens_realistic = system_tokens * (n_chunks - N_ASSUMED_CACHE_WRITES_REALISTIC)
    cached_noncached_input_tokens = total_chunk_tokens + total_schema_tokens

    # Cache-write premium depends on the TTL requested. We request
    # `ttl: "1h"` (see build_request()) specifically because a Batch API
    # run can take up to 24h and the default 5-minute TTL would almost
    # certainly expire between individual request executions, forcing
    # repeated cache re-writes. The 1-hour TTL carries a HIGHER write
    # premium than the 5-minute default (2x base input price vs. 1.25x,
    # per Claude pricing as of this project's training-data cutoff) — using
    # 2x here, not 1.25x. Confirm this multiplier for Sonnet 5 specifically
    # before relying on it; it postdates this assistant's training cutoff.
    CACHE_WRITE_1H_MULTIPLIER = 2.0

    results = {}
    for tier, prices in PRICING.items():
        in_price, out_price = prices["input"], prices["output"]

        uncached_cost = (
            uncached_input_tokens / 1e6 * in_price
            + total_output_tokens / 1e6 * out_price
        ) * BATCH_DISCOUNT

        def cached_cost(write_tokens, read_tokens):
            return (
                (
                    write_tokens * CACHE_WRITE_1H_MULTIPLIER
                    + read_tokens * CACHE_READ_MULTIPLIER
                    + cached_noncached_input_tokens
                )
                / 1e6
                * in_price
                + total_output_tokens / 1e6 * out_price
            ) * BATCH_DISCOUNT

        results[tier] = {
            "uncached_usd": round(uncached_cost, 2),
            "cached_best_case_usd": round(
                cached_cost(cache_write_tokens_best, cache_read_tokens_best), 2
            ),
            "cached_realistic_usd": round(
                cached_cost(cache_write_tokens_realistic, cache_read_tokens_realistic), 2
            ),
        }

    return {
        "n_chunks": n_chunks,
        "tokenizer_used": "cl100k_base (tiktoken proxy)" if _ENC is not None else "words*1.35 fallback",
        "system_prompt_words": len(SYSTEM_PROMPT.split()),
        "system_prompt_tokens": round(system_tokens),
        "clears_1024_token_cache_minimum": system_tokens >= 1024,
        "total_chunk_words": int(total_chunk_words),
        "total_chunk_tokens": round(total_chunk_tokens),
        "schema_tokens_by_section_type": schema_tokens_by_type,
        "total_input_tokens_uncached": round(uncached_input_tokens),
        "total_output_tokens_est": total_output_tokens,
        "pricing": results,
    }


def write_requests_jsonl(requests: list[dict], path: str = OUTPUT_REQUESTS_PATH) -> None:
    with open(path, "w") as f:
        for r in requests:
            f.write(json.dumps(r) + "\n")


def submit_batch(requests_path: str = OUTPUT_REQUESTS_PATH):
    """*** NOT CALLED. Ready to run once the owner signs off. ***

    Would submit `requests_path` (one JSON object per line, already in
    Batch API `custom_id` + `params` shape) via the Claude Batch API's
    message-batch-create endpoint and return the batch ID for polling.
    Left unimplemented against a live client on purpose — wiring this up
    to a real `anthropic.Anthropic().messages.batches.create(...)` call is
    the very last step, deliberately done only after explicit go-ahead,
    not bundled into this prep pass.
    """
    raise NotImplementedError(
        "Batch API submission is gated on explicit owner sign-off "
        "(see ROADMAP.md Week 3 money gate). Not implemented in this pass."
    )


def run():
    corpus_df = pd.read_parquet(CORPUS_PATH)
    print(f"Loaded {len(corpus_df)} chunks from {CORPUS_PATH}")

    # Original default path — unchanged, uses the "disabled" variant's
    # request-shape logic but keeps writing to the original filename so any
    # existing consumer of data/batch_requests.jsonl keeps working. Left in
    # place (not deleted) until a variant is chosen per the canary below.
    requests = build_all_requests(corpus_df, variant="disabled")
    write_requests_jsonl(requests)
    print(f"Wrote {len(requests)} request lines to {OUTPUT_REQUESTS_PATH}")

    estimate = estimate_cost(corpus_df)
    print(json.dumps(estimate, indent=2))

    return requests, estimate


def build_variant_files(corpus_df: pd.DataFrame | None = None) -> dict[str, int]:
    """Builds the full (6,747-row) request file for every entry in
    VARIANTS, writing each to its own path. Local prep only — no API
    calls. Returns {variant_name: n_requests_written}."""
    if corpus_df is None:
        corpus_df = pd.read_parquet(CORPUS_PATH)

    counts = {}
    for variant_name, cfg in VARIANTS.items():
        requests = build_all_requests(corpus_df, variant=variant_name)
        write_requests_jsonl(requests, path=cfg["output_path"])
        counts[variant_name] = len(requests)
        print(f"[{variant_name}] wrote {len(requests)} request lines to {cfg['output_path']}")
    return counts


if __name__ == "__main__":
    run()
