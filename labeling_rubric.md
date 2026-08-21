# Labeling Rubric — FinScreen Bootstrap Labels

Version 1.1 (Week 3; see §9). Governs every Batch API labeling request built by
`build_batch_requests.py`. A model-facing restatement of this document
(same rules, leaner wording — no file references or revision log) is
embedded as the cacheable system-prompt prefix in every labeling request;
this .md is the authoritative human-readable spec, and the two are kept in
sync by hand — see `SYSTEM_PROMPT` in `build_batch_requests.py`.

FinScreen is a research/screening tool. Labels describe **what the filing
text says**, nothing else.

---

## 0. The one rule that overrides everything else below

**Label only what the text says. Never consider, mention, or infer what
happened to the company's stock price or business afterward.**

You are not told which company, ticker, or date this text is from, and you
must not guess or use any such knowledge if you happen to recognize the
text anyway. Judge sentiment, guidance direction, and red flags purely from
the semantic content of the passage in front of you — as if it were an
anonymous, dateless document. Do not reason about "would this be good or
bad news for investors" or "how did the market react" — reason about "what
does this text assert."

This rule exists because the labeling model has training-data knowledge of
real companies' subsequent performance. Framing a judgment around market
reaction, rather than text content, would bake outcome knowledge into
labels that are later used to train a model and evaluate a backtest — a
direct look-ahead-bias risk. See `DISCOVERY.md` §5.

---

## 1. Applicability matrix

Not every label category applies to every chunk. The labeling request for
a given chunk only asks for the categories that apply to its
`section_type`; other fields are omitted from the request entirely (not
asked-and-nulled).

| Label category | MDA | RISK_FACTORS | EX99_PRESS_RELEASE | 8K_BODY |
|---|---|---|---|---|
| Sentiment (3-class) | Yes | **No — never asked** | Yes | Yes |
| Guidance direction | No | No | Yes | Yes |
| Red-flag taxonomy (6 categories) + modality | Yes | Yes | Yes | Yes |
| Distress tier (3 categories) + modality | Yes | Yes | Yes | Yes |

**Why sentiment skips Risk Factors:** Item 1A is negative by statutory
construction — SEC rules require issuers to enumerate things that could go
wrong, so a Risk Factors passage is close to negative-by-definition
regardless of the company's actual condition. Asking for sentiment there
would train the model to learn "risk-factor register ⇒ negative," a
shortcut that teaches nothing about the company. This is not "ask and
default to neutral" — the sentiment question is not asked for these chunks
at all.

**Why guidance direction is press-release/8-K-only:** MD&A "we expect"
language is generic forward-looking prose required by Item 7, not an
issued guidance figure. Guidance direction (raised/maintained/lowered/
withdrawn) is a claim about a specific, quantified forward-looking
commitment — the kind of statement that actually appears in earnings
press releases and 8-K bodies, not routine MD&A narrative.

---

## 2. Sentiment (3-class)

Applies to: MDA, EX99_PRESS_RELEASE, 8K_BODY chunks only.

Classify the **overall tone of the passage regarding the business's
current results and condition**, as asserted by the text itself:

| Label | Definition |
|---|---|
| `POSITIVE` | The passage's predominant tone describes results, performance, or condition favorably — growth, strength, achievement, improvement, or explicitly favorable characterization by the filer. |
| `NEUTRAL` | The passage is descriptive/factual without a predominant favorable or unfavorable characterization — e.g., procedural narrative, a balanced mix of favorable and unfavorable statements with no clear lean, or purely mechanical disclosure (accounting policy description, fiscal calendar explanation). |
| `NEGATIVE` | The passage's predominant tone describes results, performance, or condition unfavorably — decline, weakness, disappointment, deterioration, or explicitly unfavorable characterization by the filer. |

**Judging rules:**
- Judge the passage's own characterization of *its own subject matter*
  (the company's results/operations/condition), not your outside opinion of
  whether that subject matter is objectively good or bad for a reader.
- A passage reporting a large positive number in a flat tone, with no
  qualitative characterization either way, is `NEUTRAL` — magnitude of a
  number alone isn't sentiment; the text has to characterize it.
- Mixed passages: label by the predominant tone across the passage as a
  whole, not by counting positive vs. negative sentences. If genuinely
  balanced with no lean, use `NEUTRAL`.
- Never use knowledge of what actually happened to the company afterward.
  Judge only the passage's own words.

**Examples (illustrative, not exhaustive):**
- "Net sales increased 12% driven by strong iPhone demand and record
  Services revenue" → `POSITIVE`.
- "The Company's fiscal year is the 52- or 53-week period ending on the
  last Saturday of September" → `NEUTRAL` (procedural).
- "Revenue declined for the third consecutive quarter as demand softened
  across our largest end markets" → `NEGATIVE`.

---

## 3. Guidance direction

Applies to: EX99_PRESS_RELEASE, 8K_BODY chunks only.

Classify whether the passage revises previously-issued forward guidance,
issues new guidance, or contains no guidance statement at all:

| Label | Definition |
|---|---|
| `RAISED` | The passage states that a specific forward-looking financial target (revenue, EPS, margin, unit volume, etc.) has been increased versus a prior figure. |
| `MAINTAINED` | The passage explicitly reaffirms previously-issued guidance without changing it. |
| `LOWERED` | The passage states that a specific forward-looking financial target has been decreased versus a prior figure. |
| `WITHDRAWN` | The passage states that previously-issued guidance is being withdrawn, suspended, or no longer being provided. |
| `NONE` | The passage contains no specific, quantified forward guidance statement — including passages that only describe historical/current-period results, or that use general forward-looking language ("we expect continued growth") without a specific reaffirmed, raised, lowered, or withdrawn figure. |

**Judging rules:**
- Requires a *specific quantified target* (a number, a range, or an
  explicit reaffirmation of a previously-stated number) — vague optimism or
  caution about the future is `NONE`, not a guidance signal.
- If a passage both raises one metric and lowers another, prefer the label
  matching the passage's overall framing (e.g., a press release that leads
  with "raising full-year EPS guidance" while trimming one minor segment
  metric is `RAISED`); if genuinely balanced/ambiguous, use `NONE` and note
  it rather than force a call — a bootstrap label is meant to be a
  first-pass signal, not a forced binary.
- `WITHDRAWN` requires explicit withdrawal/suspension language, not merely
  the absence of a guidance restatement in this particular passage.

---

## 4. Red-flag taxonomy (6 categories)

Applies to: MDA, RISK_FACTORS, EX99_PRESS_RELEASE, 8K_BODY — all four
section types.

For each category, determine whether the passage contains language
matching that category. A passage may match **zero, one, or multiple**
categories — this is a multi-label field, not a single choice. Each
positive match also requires a **modality** value (§6).

| Category | What it covers | Example trigger language |
|---|---|---|
| `DEMAND_WEAKNESS` | Softening customer demand, declining orders/bookings, unfavorable volume trends, market-share loss attributed to demand. | "order volumes declined," "customers deferred purchases," "softening demand in our largest end market" |
| `SUPPLY_INPUT_CONSTRAINT` | Constraints on supply chain, raw materials, components, labor availability, or production capacity. | "component shortages," "supply chain disruptions limited production," "difficulty sourcing raw materials" |
| `TRADE_POLICY_EXPOSURE` | Tariffs, export controls, sanctions, trade restrictions, or other cross-border trade-policy impacts. | "tariffs increased our cost of goods sold," "export control restrictions limit our ability to sell in [region]," "new sanctions affected our supply chain" |
| `IMPAIRMENT_WRITEDOWN` | Asset impairments, goodwill write-downs, inventory write-downs, restructuring charges tied to asset value reduction. | "recorded a goodwill impairment charge," "wrote down inventory," "impairment of long-lived assets" |
| `MARGIN_COST_PRESSURE` | Rising input/labor/operating costs compressing margins, independent of the supply-constraint or trade-policy categories above (use those instead when the *cause* is explicitly supply or tariffs — see disambiguation note below). | "gross margin contracted due to higher input costs," "increased freight and labor expenses pressured operating margin" |
| `LEGAL_REGULATORY_ACTION` | Litigation, investigations, enforcement actions, regulatory fines, consent decrees, or new regulatory requirements creating compliance burden/cost. | "the Company is subject to an ongoing antitrust investigation," "received a subpoena from the SEC," "settled litigation for $X million" |

**Disambiguation note (MARGIN_COST_PRESSURE vs. SUPPLY_INPUT_CONSTRAINT vs.
TRADE_POLICY_EXPOSURE):** if the passage names a specific cause (supply
shortage, tariff) for cost/margin pressure, label **both** the causal
category and `MARGIN_COST_PRESSURE` if margin/cost impact is explicitly
stated — categories are not mutually exclusive. If the passage describes
cost pressure with no named cause (e.g., generic "input cost inflation"),
label only `MARGIN_COST_PRESSURE`.

**What does *not* count:** a category name appearing in a section header or
table of contents with no substantive discussion; a purely hypothetical
risk-factor sentence that is boilerplate generic language shared across
nearly all filers in an industry with no company-specific detail (still
label it if it fits a category — see modality below — but this is exactly
what the modality field exists to distinguish from a realized event).

---

## 5. Distress tier (3 categories)

Applies to: MDA, RISK_FACTORS, EX99_PRESS_RELEASE, 8K_BODY — same scope as
the red-flag taxonomy. Labeled the same way (zero, one, or multiple
matches, each with a modality value), and kept as a **separate field**
from the 6-category red-flag taxonomy above — do not merge them.

| Category | What it covers |
|---|---|
| `GOING_CONCERN` | Explicit going-concern doubt language — the filer's or its auditor's statement that there is substantial doubt about the company's ability to continue as a going concern. |
| `ACCOUNTING_RESTATEMENT` | Restatement of previously issued financial statements, or an admission that prior financials should no longer be relied upon. |
| `LIQUIDITY_STRESS` | Explicit statements of insufficient liquidity, inability to meet obligations as they come due, breach of debt covenants, or substantial doubt about access to capital/credit. |

**Why this is labeled even though it's expected to be almost empty here:**
this corpus is drawn from 25 currently-healthy mega-cap filers, so real
positives in this tier are expected to be rare-to-none. The rubric still
asks the question on every chunk rather than assuming the answer, so the
label schema doesn't silently encode "this can't happen" — a decision about
whether to exclude this tier from fine-tuning or agreement-rate reporting
downstream (because there isn't enough support to learn or evaluate it
honestly) is made later, by the fine-tuning/eval pipeline, not baked into
the rubric or the labeling request itself.

**That decision has since been made (and this open question is closed):**
`distress_tier` is **excluded** from fine-tuning targets and from every
headline eval/agreement number — a standing hard rule (`HANDOFF.md` §7),
enforced in code by `prepare_dataset.py`/`eval.py`'s exclusion and by
`compute_agreement.py`'s `assert_distress_excluded_from_headline()`. It is
still labeled and still reported, separately. Two further findings from the
2026-08-18 spot-check: `GOING_CONCERN` has **zero** instances corpus-wide,
and all 9 REALIZED `LIQUIDITY_STRESS` labels were owner-ruled incorrect, so
every REALIZED distress class is empty or near-empty
(`RED_FLAGS_LIMITATION.md`, distress-tier addendum).

---

## 6. Modality (`HYPOTHETICAL` vs. `REALIZED`)

Required on **every** positive red-flag-taxonomy or distress-tier match
(both fields, all 9 possible categories share the same modality
vocabulary). Not applicable / omitted when a category has no match.

| Value | Definition |
|---|---|
| `HYPOTHETICAL` | The passage describes something that **may** occur, is a risk, or is generic forward-looking risk language — "may," "could," "if," "in the event that," or an itemized risk-factor-style enumeration with no assertion that it has actually happened. |
| `REALIZED` | The passage describes something that **has already occurred or is currently occurring** — stated in the past or present tense as an actual event, with no hedging language framing it as merely possible. |

**Why this field exists:** roughly 85% of Risk Factors language is
boilerplate hypothetical risk enumeration ("we may experience supply chain
disruptions..."). Without a modality field, that boilerplate and a genuine
realized event ("supply constraints reduced Q3 revenue by $400M") would
collapse into the same red-flag label, swamping the rare, actually
informative sentence with noise. This is what keeps red-flag detection
useful on Risk Factors text specifically.

**Judging rule:** modality is about the *grammatical/semantic framing of
the passage*, not about how likely the event is to be true. "We are
currently experiencing higher input costs due to tariffs" → `REALIZED`.
"Tariffs or other trade restrictions could increase our costs" →
`HYPOTHETICAL`. A passage that opens hypothetically but then asserts a
concrete realized impact ("Should tariffs increase further... In the
current period, tariffs already imposed increased our cost of goods sold
by $120 million") should be labeled `REALIZED` for that category — the
concrete realized statement controls over a preceding hypothetical framing
in the same passage.

---

## 7. Output schema (structured output)

Every labeling request uses Claude's structured-output (`output_config.format`
with a JSON schema), not prompt-for-JSON. The schema is conditionally
shaped by section_type at request-construction time (see
`build_batch_requests.py`): `sentiment` is omitted from the schema entirely
for RISK_FACTORS chunks, and `guidance_direction` is omitted from the
schema entirely for MDA/RISK_FACTORS chunks — the model is never given the
option to answer a question that doesn't apply.

Conceptual shape (concrete JSON Schema lives in `build_batch_requests.py`):

```
{
  "sentiment": "POSITIVE" | "NEUTRAL" | "NEGATIVE",              # omitted for RISK_FACTORS
  "guidance_direction": "RAISED" | "MAINTAINED" | "LOWERED"
                       | "WITHDRAWN" | "NONE",                    # omitted for MDA/RISK_FACTORS
  "red_flags": [
    {"category": "<one of the 6 red-flag categories>", "modality": "HYPOTHETICAL" | "REALIZED"}
    // zero or more entries
  ],
  "distress_tier": [
    {"category": "<one of the 3 distress categories>", "modality": "HYPOTHETICAL" | "REALIZED"}
    // zero or more entries
  ]
}
```

---

## 8. Look-ahead-bias-safe prompt construction (binding on every request)

These constraints are enforced in `build_batch_requests.py`, not just
stated here — this section documents *why*, the code is what actually
guarantees it:

1. **Never include `ticker`, `company_name`, or `filing_date`** in the
   labeling request (system prompt or user turn). The labeling model
   (Claude Sonnet 5) has training-data knowledge of these 25 specific
   companies' actual subsequent performance; naming the company invites
   outcome-conditioned labeling.
2. **Never include `section_type` as prompt text in any request, for any
   label category.** `section_type` is used only at request-construction
   time to decide which fields the JSON schema asks for (the applicability
   matrix, §1) — it enters the request solely as schema *shape* via
   `output_config.format`, never as a string the model can read. Since all
   categories are asked in one combined request per chunk, a section label
   visible anywhere in the prompt would let the model condition its
   sentiment answer on "this reads like a risk-factor register" instead of
   reading the passage — so it appears nowhere. (Ratified by the owner
   2026-08-10; this is deliberately stricter than the v1 wording, which
   allowed section_type in the red-flag/distress portion.)
3. **No outcome framing anywhere in the prompt.** The instructions ask
   "what does this passage say," never "would this be good or bad news for
   the stock" or any variant. §0 of this rubric is the literal text
   embedded in the system prompt to make this explicit to the labeling
   model itself, not just to whoever reads this doc.

---

## 9. Revision log

- v1 (Week 3): initial rubric, built against the Task 1 chunking corpus and
  the taxonomy locked in `DISCOVERY.md` §3.
- v1.1 (Week 3, 2026-08-10): owner ratified the stricter §8.2 construction
  (section_type never appears as prompt text for any category; schema shape
  only), corrected the header's "embedded verbatim" claim to "restated", and
  the §3 mixed raise/lower judging rule was added to the model-facing
  `SYSTEM_PROMPT` (it was in the rubric but missing from the prompt). No
  label-definition changes.
- **v1.2 (proposed 2026-08-18 — NOT ratified, NOT applied, no re-label):**
  the 400-example spot-check ran and `red_flags` failed the 0.70 agreement
  bar (63.4% exact-set match). Three concrete §4/§6 clarifications are
  drafted against this document — realized-controls-modality, boilerplate
  mining depth, and the causeless-cost-inflation disambiguation — in
  **`RED_FLAGS_LIMITATION.md`** ("Proposed rubric revision"). **Read that
  file before editing §4 or §6.** Nothing in this document has changed on
  account of it, and no re-label is possible regardless (API-spend freeze,
  `HANDOFF.md` §5). If it is ever ratified, the §3 sync rule applies:
  `SYSTEM_PROMPT` in `build_batch_requests.py` gets a matching hand-synced
  edit.
