# PROMPT_TEMPLATE — QLoRA instruction-tuning format

Governs `prepare_dataset.py`. Mirrors the look-ahead-bias-safe conventions
established in `build_batch_requests.py` / `labeling_rubric.md` §8 for the
bootstrap labeling prompts — the fine-tuning prompt is deliberately built
the same way, not re-derived from scratch, so training-time and
labeling-time text exposure stay consistent.

## Format

Each training/eval example is one instruction-tuning record:

```json
{
  "chunk_id": "CHK-...",
  "instruction": "<INSTRUCTION, byte-identical across every example>",
  "input": "<the raw passage text, and NOTHING else>",
  "output": "<deterministic-key-order JSON string, fields conditional on section_type — see below>"
}
```

At training time this is rendered into whatever chat/instruction template
the base model expects (see `MODEL_CHOICE.md` / `train_qlora.py`); the JSON
fields above are the framework-agnostic source of truth `prepare_dataset.py`
produces, kept separate from any model-specific chat-template rendering so
switching base models doesn't require re-deriving the dataset.

## What is deliberately NEVER in `instruction` or `input`

Per `labeling_rubric.md` §8 (look-ahead-bias-safe prompt construction) and
`DISCOVERY.md` §5's look-ahead-bias rule, and exactly mirroring
`build_batch_requests.py`'s construction:

- **No ticker, company name, or CIK** — not from `home_ticker`/`home_cik`/
  `universe.csv`, not synthesized, not referenced indirectly.
- **No filing date** — not `home_filing_date`, not any derived quarter/year
  string.
- **No `section_type` string, in any example, for any field.** This is
  stricter than "just don't tell it for sentiment" — per the ratified v1.1
  rubric (`labeling_rubric.md` §8.2) and `build_batch_requests.py`'s own
  design note, section_type never appears as literal text anywhere in a
  labeling request, because a shared context can't selectively "hide" a
  fact from part of a model's reasoning. The fine-tuning prompt follows the
  same rule for the same reason: even though `guidance_direction`/`sentiment`
  applicability legitimately depends on section_type, that dependency is
  encoded ONLY in **which output fields appear in the target JSON for a
  given training example** — never as prompt text the model reads. The
  model is expected to learn "this looks like risk-factor register prose,
  don't emit a sentiment field" from the *content* of many such examples,
  the same way the rubric intends a human or an unprompted-on-metadata model
  to.
- **No outcome framing.** The instruction never asks about stock reaction,
  investor sentiment, or "what happened next" — only what the passage
  itself states.

## `instruction` (fixed, byte-identical across every example)

```
You are extracting structured signals from a short passage of text taken from a public SEC filing (10-K/10-Q Management's Discussion & Analysis, Item 1A Risk Factors, or an 8-K earnings press release / body). You are not told which company, ticker, or date this passage is from, and must not guess. Judge only what the passage's own text asserts about the business's results, performance, condition, and forward guidance -- never what happened to any company's stock price or business afterward.

Respond with a single JSON object. Only include the fields that genuinely apply to this passage's content and section register -- omit a field entirely rather than guessing or defaulting it if it doesn't apply:

- "sentiment": one of "POSITIVE", "NEUTRAL", "NEGATIVE" -- the passage's predominant tone about the business's own results/condition, as characterized by the text itself. Omit for passages that are purely a statutory risk-factor enumeration (negative-by-construction register, not a real signal).
- "guidance_direction": one of "RAISED", "MAINTAINED", "LOWERED", "WITHDRAWN", "NONE" -- only include this field for passages that are (or could be) issuing/revising specific quantified forward financial guidance, such as earnings press releases or 8-K bodies. Omit for narrative MD&A or risk-factor text, which never issues guidance.
- "red_flags": a list of {"category": ..., "modality": ...} objects, zero or more, from categories DEMAND_WEAKNESS, SUPPLY_INPUT_CONSTRAINT, TRADE_POLICY_EXPOSURE, IMPAIRMENT_WRITEDOWN, MARGIN_COST_PRESSURE, LEGAL_REGULATORY_ACTION, each with modality HYPOTHETICAL (framed as something that may occur) or REALIZED (stated as having already occurred or currently occurring). Always include this field, with an empty list if nothing matches.

Output only the JSON object, no other text.
```

(Note: `distress_tier` is asked in the original labeling rubric/schema, but
is deliberately **excluded from the fine-tuning target** entirely — see
"distress_tier exclusion" below. The instruction text above does not mention
it, so the model is never trained to expect or emit it.)

## `input`

The chunk's raw `text` field from `data/labels.parquet`, verbatim, and
nothing else appended or prepended.

## `output` — conditional target fields, deterministic key order

Fixed key order when present: `sentiment`, `guidance_direction`, `red_flags`.
A field is included **only if the source label row's `section_type` makes it
applicable**, matching `labeling_rubric.md` §1's applicability matrix
exactly — never emitted as `null` or a placeholder, simply absent from the
JSON object:

| section_type | sentiment | guidance_direction | red_flags |
|---|---|---|---|
| MDA | yes | **no** | yes |
| RISK_FACTORS | **no** | **no** | yes |
| EX99_PRESS_RELEASE | yes | yes | yes |
| 8K_BODY | yes | yes | yes |

`red_flags` is always present (as `[]` if no category matched), for every
section_type, per the rubric. Within `red_flags`, entries are sorted by
`(category, modality)` for determinism (the source label JSON's array order
isn't guaranteed stable across a re-run of the labeling batch, so this
avoids spurious diffs in the prepared dataset from re-running
`prepare_dataset.py` against an unchanged `labels.parquet`).

### `distress_tier` exclusion (binding, not a default)

`distress_tier` is asked in the rubric and present in `data/labels.parquet`,
but is **excluded from every training-target JSON produced here**, per
`DISCOVERY.md` §3 ("explicitly excluded from fine-tuning and from
agreement-rate reporting, since there isn't enough real signal in this
universe/window to learn or evaluate it honestly") and this task's own
instructions. `prepare_dataset.py` never reads `distress_tier` into an
`output` field. `eval.py` may report it informationally, separately, never
as part of headline metrics.

## Applicability matrix enforced in code

`prepare_dataset.py::APPLICABILITY` is the single source of truth for the
table above, and `test_prepare_dataset.py::test_applicability_matrix_matches_rubric`
asserts it matches `labeling_rubric.md` §1's matrix field-for-field (minus
`distress_tier`, which is asserted to never appear at all).
