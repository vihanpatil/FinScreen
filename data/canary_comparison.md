> **READER NOTE (2026-08-18):** historical record of the 2026-08-11
> two-variant canary, preserved as the audit trail. **Its measurements are
> sound; its recommendation and cost projections are NOT current.**
> Specifically:
>
> - **§5 recommends `max_tokens=800` for the full run. The corpus was
>   actually labeled at `max_tokens=4000`** (thinking disabled), uniform
>   across all 6,747 rows. Do not read 800 as the corpus config — see
>   `data/full_run_report.md`'s FINAL CONSOLIDATED STATE section.
> - **The cost projections (~$38.55 / ~$48.12) are superseded.** The real
>   full run cost $18.05; total project spend is frozen at $33.51 and **no
>   further Anthropic API spend is permitted** (`HANDOFF.md` §5). The
>   "$50 total ceiling" and "the QLoRA fine-tune still needs GPU budget"
>   rationales behind that recommendation are both dead — fine-tuning, if
>   it happens, is a local $0 MLX run.
> - The **per-variant agreement measurements below are still worth
>   reading** — in particular §3's point that per-category agreement
>   (92-100%) and exact-set agreement (82%) are different metrics, which
>   is exactly the distinction the Week 3 spot-check later turned on.
>
> Current state lives in `HANDOFF.md`.

# Canary Comparison — max_tokens / thinking variants

**Date:** 2026-08-11
**Purpose:** compare two candidate fixes for the prior canary's 18/50 no-JSON
failures (root cause: adaptive thinking tokens counting against
`max_tokens=500`, starving structured output). Both variants ran the *same*
seed-42, stratified 50-chunk sample from `data/labeling_corpus.parquet` so
results are directly comparable chunk-for-chunk.

| Variant | Batch ID | Config |
|---|---|---|
| `disabled` | `msgbatch_01YF5tPu4pgQtd5zAAy2WbHm` | `thinking: {"type": "disabled"}`, `max_tokens=800` |
| `adaptive-low` | `msgbatch_01M15h4xhNsSDGHNp3tKmkbi` | `thinking` omitted (adaptive default), `output_config.effort="low"`, `max_tokens=2500` |

Outputs: `data/labels_canary_disabled.parquet`, `data/labels_canary_adaptive_low.parquet`.

---

## 1. Parse success / stop_reason anomalies

| Variant | Total | API-level not-succeeded | JSON parse failures | Schema-invalid | Clean rate |
|---|---|---|---|---|---|
| disabled | 50 | 0 | 0 | 0 | **50/50 = 100.0%** |
| adaptive-low | 50 | 0 | 0 | 0 | **50/50 = 100.0%** |

Both variants fully resolved the original failure mode — no `max_tokens`
stop_reason truncations, no malformed JSON, no schema violations, in either
variant. The fix works either way; the choice below comes down to cost and
label agreement, not correctness.

---

## 2. Real billed usage & cost (this 50-request canary)

| Metric | disabled | adaptive-low |
|---|---|---|
| Input tokens | 42,083 | 42,083 |
| Output tokens | 3,582 | 3,700 |
| Cache creation (write) tokens | 109,974 | 147,014 |
| Cache read tokens | 57,034 | 19,994 |
| Real cost @ intro pricing | **$0.2856** | **$0.3566** |
| Real cost @ standard pricing | $0.4285 | $0.5349 |
| Avg cost/request @ intro | $0.005713 | $0.007132 |

Combined real spend for both canaries: **$0.2856 + $0.3566 = $0.6422** at
intro pricing (well under the ~$1 estimate).

Input and output token counts are nearly identical between variants (as
expected — same prompts, similar-length structured JSON responses).
The cost difference is driven almost entirely by cache behavior:
`adaptive-low` had far more cache **writes** (147,014 vs. 109,974) and far
fewer cache **reads** (19,994 vs. 57,034) than `disabled`, despite both
canaries using the identical system prompt and running back-to-back. This
is very likely just a scheduling/concurrency artifact of two 50-request
batches with a small number of parallel workers each — not a structural
property of one variant vs. the other (there's no reason the "adaptive-low"
config itself would change caching behavior). Flagging it rather than
reading meaning into it.

### Full-run (6,747 requests) projection

Using each canary's own average measured per-request cost, at intro pricing:

| Variant | Projected full-run cost |
|---|---|
| disabled | **~$38.55** |
| adaptive-low | **~$48.12** |

**Caveat (carried over from `build_batch_requests.py`):** a 50-request
canary's cache read/write mix is not representative of a 6,747-request run's
concurrency pattern — treat both projections as rough, not precise. The
~$9.57 gap between them roughly tracks the higher output-token budget
(`max_tokens=2500` vs. 800) and the adaptive-low canary's less favorable
cache-read ratio in this particular run: not a huge difference in absolute
terms, but on a $50 total project ceiling, going with `disabled` leaves more
headroom (both the full labeling run and the later QLoRA fine-tune still
need to fit inside that ceiling).

---

## 3. Cross-variant label agreement (same 50 chunks)

| Category | Agreement |
|---|---|
| Sentiment (of 38 chunks where either variant returned a sentiment field) | 35/38 = **92.1%** |
| Guidance direction (of 9 chunks where either variant returned a guidance field) | 9/9 = **100.0%** |
| Red-flag set, exact match (all 6 categories, all 50 chunks) | 41/50 = **82.0%** |
| Distress-tier set, exact match (all 3 categories, all 50 chunks) | 50/50 = **100.0%** |

### Per-category red-flag agreement (of 50 chunks each)

| Category | Agreement |
|---|---|
| DEMAND_WEAKNESS | 47/50 = 94.0% |
| SUPPLY_INPUT_CONSTRAINT | 50/50 = 100.0% |
| TRADE_POLICY_EXPOSURE | 48/50 = 96.0% |
| IMPAIRMENT_WRITEDOWN | 49/50 = 98.0% |
| MARGIN_COST_PRESSURE | 46/50 = 92.0% |
| LEGAL_REGULATORY_ACTION | 50/50 = 100.0% |

Per-category agreement is decent-to-strong across the board (92–100%); the
82% exact-set number looks worse mainly because red-flag sets often have
2–4 entries per chunk, so a single-category swing on a multi-label chunk
drags the "all-or-nothing" exact-set metric down even when most individual
category calls agree. This is expected multi-label noise, not evidence one
variant is systematically wrong — see disagreements below, none look like a
qualitative failure on either side, just borderline calls (e.g., whether a
named cost driver on top of general margin pressure clears the bar for an
extra category).

### Disagreeing chunk_ids — sentiment (3)

| chunk_id | disabled | adaptive-low |
|---|---|---|
| CHK-6cfb7bb16c8ef2fc | NEGATIVE | NEUTRAL |
| CHK-995038f4b6ac9fc2 | NEUTRAL | POSITIVE |
| CHK-b9f997aa15316a30 | NEUTRAL | NEGATIVE |

### Disagreeing chunk_ids — guidance direction

None (9/9 agree).

### Disagreeing chunk_ids — red flags (9 of 50)

| chunk_id | disabled | adaptive-low |
|---|---|---|
| CHK-1413342df33bc41f | DEMAND_WEAKNESS, MARGIN_COST_PRESSURE, TRADE_POLICY_EXPOSURE | DEMAND_WEAKNESS, TRADE_POLICY_EXPOSURE |
| CHK-20b26591e01f1aed | LEGAL_REGULATORY_ACTION, MARGIN_COST_PRESSURE | DEMAND_WEAKNESS, LEGAL_REGULATORY_ACTION, MARGIN_COST_PRESSURE |
| CHK-69958b32a73db25d | DEMAND_WEAKNESS | (none) |
| CHK-6cfb7bb16c8ef2fc | MARGIN_COST_PRESSURE | (none) |
| CHK-7182b56394fa627b | IMPAIRMENT_WRITEDOWN | (none) |
| CHK-9c3ba09aeb4a196a | DEMAND_WEAKNESS, MARGIN_COST_PRESSURE | DEMAND_WEAKNESS |
| CHK-c5144dfcd54b13d6 | DEMAND_WEAKNESS, LEGAL_REGULATORY_ACTION, TRADE_POLICY_EXPOSURE | LEGAL_REGULATORY_ACTION, TRADE_POLICY_EXPOSURE |
| CHK-ec79aeec33dc375b | IMPAIRMENT_WRITEDOWN, LEGAL_REGULATORY_ACTION, MARGIN_COST_PRESSURE, SUPPLY_INPUT_CONSTRAINT | IMPAIRMENT_WRITEDOWN, LEGAL_REGULATORY_ACTION, SUPPLY_INPUT_CONSTRAINT, TRADE_POLICY_EXPOSURE |
| CHK-ed3880d6eadd1a10 | (none) | TRADE_POLICY_EXPOSURE |

Note `CHK-6cfb7bb16c8ef2fc` disagrees on both sentiment and red flags — the
same chunk pulled a NEGATIVE/MARGIN_COST_PRESSURE call from `disabled` and a
NEUTRAL/no-flag call from `adaptive-low`, i.e. one variant read it as
mildly negative and the other as neutral-with-no-flag, consistently with
each other within that one chunk. Worth a manual look if this chunk_id
comes up again in later spot-checks.

### Disagreeing chunk_ids — distress tier

None (50/50 agree — see below, only one positive total, and both variants
agree on it).

---

## 4. Distress-tier positive rate — sanity check against "rare or absent"

| Variant | Positive rate |
|---|---|
| disabled | 1/50 = 2.0% |
| adaptive-low | 1/50 = 2.0% |

Both variants land on the **same single chunk** (`CHK-5f7e5bdcee022972`,
`LIQUIDITY_STRESS`, modality `HYPOTHETICAL`) and agree exactly. This is
much closer to the rubric's "rare or absent" expectation than the number
quoted in the task brief for the *prior* canary (19/50 chunks with ≥1
distress match) — that earlier number came from a different, unrelated
run (the original 500-max_tokens canary that also had the 18/50 parse
failures) and isn't reproduced here. With both current variants agreeing on
a single, genuinely hedged ("may be unable to meet debt covenant
requirements"-style) hit out of 50 stratified chunks, there's no indication
of a systematic over-triggering problem in either variant's distress-tier
behavior.

Example (the only positive, both variants):
> "Because we operate as a holding company, we are dependent on dividends
> and administrative expense reimbursements from our subsidiaries to fund
> our obligations. Many of these subsidiaries are regulated by state
> departments of insurance or similar regulatory authorities. We are also
> required by law or..." (chunk_id `CHK-5f7e5bdcee022972`)

This reads as boilerplate holding-company liquidity-dependency risk-factor
language — hedged, not an assertion of actual distress — which is exactly
why both variants correctly tagged it `HYPOTHETICAL` rather than
`REALIZED`. Consistent with the rubric's intent.

---

## 5. Recommendation

**Use `disabled` (`thinking: {"type": "disabled"}`, `max_tokens=800`) for
the full 6,747-request run.**

Reasoning:
- Both variants fully fix the original bug: 100% clean parse/schema-valid
  rate, no stop_reason anomalies, in both.
- Label quality is comparable — both variants agree with each other closely
  on sentiment (92%), guidance (100%), and per-category red flags
  (92–100%), and agree exactly on the rare distress-tier category. Neither
  variant shows a systematic quality problem the other doesn't.
- `disabled` is measurably cheaper on this canary (~$0.286 vs. ~$0.357,
  ~20% less) and projects to a meaningfully lower full-run cost (~$38.55 vs.
  ~$48.12 at intro pricing) — the caveat that this projection is rough given
  small-canary cache-mix noise applies to both numbers equally, so the
  relative comparison should still hold even if the absolute numbers move.
- `disabled` is also simpler and more predictable: it removes adaptive
  thinking from the picture entirely rather than trying to cap it via
  `effort="low"`, which removes one more source of run-to-run cost/latency
  variance for a 6,747-request production run.
- Given the project's $50 total ceiling and that the QLoRA fine-tuning step
  still needs GPU budget after labeling, the ~$9.57 projected difference is
  worth taking.

**Not run:** the full 6,747-request labeling batch remains untouched and
un-submitted, per the task scope — this recommendation is for the *next*
gated decision, not something executed here.
