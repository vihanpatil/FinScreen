# G2 — E2 student-label spot-check — OWNER-RATIFIED FINAL REPORT (2026-09-07)

**Status: owner row rulings RECORDED and applied (stage `owner_ratified`,
`results_g2.json` generated 2026-09-07T19:03:27Z). Gate G2 RULED: proceed under the ladder; 2(b) RULED: extend — see §1.**

Provenance: model-consensus agreement (blind Claude-family rater + Claude-family
adjudicator vs the Qwen student), **with the owner's own rulings superseding on
all 39 escalated rows and all 20 probe rows**. Still NOT human validation of
ground truth on the ~78% of gate-applicable chunks that were never contested (§5.5 probe
bounds that). The numbers below are the printed report's (`report_g2.md`,
same timestamp); nothing here is recomputed.

---

## 0. READ THIS FIRST — the owner's binding interpretation of the guidance number

> Do not interpret the 68.67% active-guidance precision as evidence that the
> model usually hallucinates the existence of guidance. A substantial share of
> those errors arise because the current guidance_direction label set has no
> representation for newly issued, directionless guidance. Under the present
> rubric those passages correctly map to NONE for direction, even though real
> quantified guidance is present.
>
> That preserves the integrity of the direction labels without artificially
> inflating the metric to 96.7% by blessing unsupported RAISED/MAINTAINED/LOWERED
> calls. In a next-version rubric, I would fix this structurally with
> ISSUED/INITIATED or a separate guidance-presence dimension.
>
> The real problem is downstream naming/interpretation: 68.67%
> "guidance_active_precision" is partly measuring directional-label precision,
> not simply whether the student detected that guidance exists. If you
> ultimately need presence of active guidance, I would add ISSUED/INITIATED or a
> separate guidance_present field in a future rubric revision rather than
> retroactively calling new guidance RAISED.

*(Owner's words, verbatim, in chat 2026-09-07; three passages of one message,
in the owner's order of emphasis. The first paragraph travels with
`guidance_active_precision` wherever it is quoted — F5 headlines, model card,
limitations write-up. Main-session note on the 96.7%: it is the packet's
model-consensus counterfactual — ruling all 24 overturned G-A rows STORED-RIGHT
would have given 96.73% [90.80%, 98.88%], n_eff 91.4 (20 of those 24 are the
fresh-guidance rows); the owner's ruling took that reading off the table.)*

---

## 1. Gate G2 — ladder consequence and the ruling

The ratified §6.5 ladder maps the owner-ratified verdicts mechanically:

| field | owner-ratified result | verdict | ladder consequence |
|---|---|---|---|
| `sentiment` | 293/337 = 86.94% [82.93%, 90.13%] | **INDETERMINATE** at 0.85 | proceeds; measured chunk-level error is a **first-class F5 input** beside every number derived from it; F5 MDE reliability sourced per the §6.5 box (H3v2 retention or the pre-registered m-chunk composition — never this proportion) |
| `guidance_direction` | 115/119 = 96.64% [91.68%, 98.69%] | **PASS** at 0.85 | gate-bearing in G3/F5; measured error ships as the caveat; **never quoted without** `guidance_active_precision` 68.67% [58.17%, 77.55%] (n_eff 84.8) and `guidance_false_none_rate` 0/80 [0.00%, 4.58%], **and §0 above** |
| `red_flags` | 112/400 = 28.0% exact-set error [23.8%, 32.6%] | no bar | exploratory / disclosure-only (2026-08-27 demotion; unchanged) |

No field reached DECISIVE FAIL, so the ladder's (a)/(b) owner choice does not
arise. The two-rater ceiling (sentiment 107/110, guidance 64/65) clears the bar,
so §6.4 fact 3 does not fire.

**GATE G2 RULED (owner, in chat, 2026-09-07 evening): "G2: proceed under the
ladder."** Sentiment proceeds as INDETERMINATE with its measured chunk-level
error a first-class F5 input; guidance is gate-bearing as PASS on the NONE mass
only, never quoted without the two escorts and §0. No override of the ladder
(sentiment is NOT demoted). The owner's stated understanding at ruling time:
"It passed, no?" was answered as *half-passed* (guidance PASS, sentiment
INDETERMINATE) before the ruling was given.

**RULING 2(b) RULED (owner, same message): "Extend. Label the extension
stratum; promotion into F5 waits on its own spot-check."** The owner's
reasoning: the guidance PASS alone suffices to make the core labels worth
extending, and the ladder already lets core sentiment proceed. Binding
consequences, stated to the owner before the ruling: (1) the extension
campaign (3 sectors — industrials, utilities/telecom, materials_realestate;
36 additional members; 8,115 F3-extracted sections, ~35% of core by words;
est. ~110k chunks, 3–4 GPU overnights, $0 API) runs only after the campaign
wrapper's lock fix (`data/f4/status/F4_campaign.md` §4); (2) the 2026-08-21
promotion clause stays unsatisfied — extension labels enter F5 as a promoted
arm only after their own spot-check on the unseen sectors; nothing in G2 may
be quoted as speaking to them. Sequencing (main-session suggestion, accepted
in the same ruling): F5 section-mask fix + core features first; extension
labeling on nights in the background.

---

## 2. What the owner ruled (59 rows) and what moved

Files: `owner_rulings.json` (39 rows, sha `d0ae8a9f…`), `probe_rulings.json`
(20 rows, sha `8bd26918…`). Their `note` fields are the main session's
condensed transcription of the owner's reasoning; the owner's verbatim words
are quoted in this file and live in the chat record. Analyzer: 19/19
assertions, exit 0, 0 API calls.

Input digests not carried inside `results_g2.json` (its `inputs` block hashes
the three parquets, `adjudications.json`, `draw_manifest.json`, `probe_ids.json`
and the three rater-B files only; the draw CSVs are covered transitively through
the manifest's `outputs` block):

| layer | sha256 (first 16) |
|---|---|
| `verdicts/rater_a_batch01..15.json`, concatenated in name order | `af09dbcaa7058c2b` |
| `adjudications/adjudications.json` | `383f90849c62a735` |
| `owner_rulings.json` | `d0ae8a9f78ceeb68` |
| `probe_rulings.json` | `8bd26918fbc0c76a` |
| `draw_g2.csv` / `../g2_draw_arms.csv` | `affc27d3159cc648` / `5335fbadd31e7f50` |
| `results_g2.json` (this stage) | `d146e5e43586403001` |

**Part A (39 `needs_human` rows).** 33 ADJUDICATOR-RIGHT; 4 STORED-RIGHT on rows
the adjudicator had upheld (A23, A25, A30, A35 — no change); **2 STORED-RIGHT
overriding the adjudicator**:

- **A39 → NEGATIVE** (P arm, sentiment). Revenue +12% and better free cash flow,
  but operating income −40%, margin −501 bps, adjusted EBITDA down, net income
  −37%, EPS −31 to −37%, opex +50%; the profitability section enumerates more
  adverse drivers than favorable ones. Owner, verbatim: "Calling that
  genuinely balanced understates the deterioration in the core earnings
  picture."
- **A36 → NEUTRAL** (G-N arm, sentiment). Promotional awards / "Strong Digital
  Usage" / records sit beside materially mixed financials (net income and pretax
  income down, investment-banking fees down sharply; revenue, pre-provision
  income and digital metrics up). Owner, verbatim: "I don't think a corporate
  awards block should mechanically turn a mixed financial passage POSITIVE."

**Part B (20 probe rows): AGREE on all 20. 0 overturns** → the ≥2 escalation
trigger does not fire; the 402-chunk uncontested sweep is NOT run (§5.5). Rows
the owner scrutinized hardest: B1 (mixed guidance, LOWERED stands — the only
directional change is downward), B8 (closest row: GAAP EPS lowered, adjusted
EPS explicitly raised; RAISED stands on the investor-facing emphasis and
explicit "raising" language), B10 (Alimta −38% / −70% ex-U.S. / "rapid and
severe decline" carries NEGATIVE).

**Numeric effect versus the model-consensus stage:**

| estimator | model consensus | owner-ratified | why |
|---|---|---|---|
| sentiment k/n | 292/337 = 86.65% [82.60, 89.87] | **293/337 = 86.94% [82.93, 90.13]** | A39 (P arm); verdict unchanged — INDETERMINATE at 0.85 either way |
| stored-NEGATIVE precision | 24/49 = 49.0% | **25/49 = 51.0%** | A39 |
| stored-POSITIVE / NEUTRAL precision | 53/68 = 77.9% / 215/217 = 99.1% | unchanged | — |
| guidance base rate | 115/119 = 96.64% | unchanged | all 3 P-arm guidance rows ruled ADJUDICATOR-RIGHT |
| `guidance_active_precision` | 68.67% [58.17, 77.55] | unchanged | all 25 G-A rows ruled ADJUDICATOR-RIGHT (24) or upheld (A35) |
| per direction | RAISED 32/46, MAINTAINED 16/24, LOWERED 10/15, WITHDRAWN 15/15 | unchanged | — |
| `guidance_false_none_rate` | 0/80 | unchanged | G-N contributed no Part A `guidance_direction` rows (its 4 Part A rows — A24, A32, A34, A36 — are sentiment) |
| S-PROBE | unruled | **0/20 overturned**, Wilson on hidden shared error [0%, 16.1%]; uncontested share of gate chunks 77.8% → max hidden error share of gate rows 12.5% | Part B |

A36 sits in the G-N arm; sentiment is scored only in the P arm, so it enters no
reported estimator. Both adjudicator overrides restored the student's stored
label, i.e. ran in the student's favour (n = 2; stated as a fact, no inference
drawn — the packet showed the owner both the stored label and the adjudicator's
call on every row). Both verdicts were locked before the rulings (packet
arithmetic) and stayed locked. **`sentiment_negative_share` now rests on a
stored-NEGATIVE precision of 51.0% (25/49).** Sentiment's 44 remaining errors are
still overwhelmingly the student asserting a direction on a passage the
reference calls NEUTRAL (24 NEG→NEU, 15 POS→NEU; 3 are omission-pinned).

---

## 3. Binding annotation-policy ruling — guidance direction on newly issued guidance (owner, 2026-09-07)

Companion to the eight v1.2 rules in
`data/hardening/spotcheck_v12/OWNER_POLICY_RULINGS.md`; same standing (binding
interpretation of rubric v1.2 §3; any v1.3 must be consistent with it). **It is
recorded here and not appended to that file:** the v1.2 file is a sha-pinned
pre-registration input of the G2 draw (`build_draw_g2.py` INPUT_SHA256, checked
by `test_draw_reproduces_byte_for_byte`) and must stay byte-identical.

**Rule 9. `guidance_direction` = NONE when the company issues quantified
guidance but the passage does not establish that the guidance was raised,
lowered, maintained, or withdrawn relative to PRIOR GUIDANCE.** NONE means
"no directional action established", not "no guidance exists".

Corollaries fixed by the row rulings (A1–A22, all fresh guidance → NONE;
A27–A29, A33, A35, A37 → MAINTAINED):

- A comparison against a prior-period **actual** is not a revision of guidance
  (A1: 2017 outlook vs 2016 actual; A17: 2025 capex $2.4B vs 2024 actual $2.6B is
  not a cut; A22: expected YoY growth is not a raise).
- "Now expects" / "updated outlook" proves an update happened, not its
  direction (A11, A13, A19). "Initiates" / "provided" / "initial" guidance is
  the canonical undirected case (A16, A18, A14, A7).
- "Narrowing" a range without the old range does not establish LOWERED; with
  an explicit maintained metric present the row is MAINTAINED, not NONE (A29).
- A restated outlook without explicit reaffirmation language is NONE (A20); a
  guidance table without a prior-guidance column is NONE (A3, A9, A10, A15).
- **Explicit reaffirmation controls mixed line-item revisions** → MAINTAINED
  (A27, A28, A33 "holding our outlook" while steering to the low end, A35
  earnings "remain within prior guidance" even with expected outperformance).
  "Remain on track" for a previously announced quantified target is a
  reaffirmation → MAINTAINED (A37).

Why the owner rejected the alternative (ratifying the student's calls): across
A1–A22 the student calls undirected new guidance RAISED, MAINTAINED and even
LOWERED, usually by comparing to a prior-year actual rather than prior guidance.
That is not a coherent "new guidance" convention; ratifying it would corrupt
the meaning of direction.

**Sentiment corollaries** (rows A23–A39): bare tables, percentage tables and
reconciliations do not manufacture sentiment even when the numbers look strong
(A23–A26); a hypothetical safe-harbor list or a mechanical reserve walk does not
make tone negative (A30, A31); prose that repeatedly narrates realized margin
increases with favorable drivers is POSITIVE (A32); "significant progress" and
"strong strategic and financial position" characterize present condition →
POSITIVE (A34); explicitly "strong" / "excellent" current results stay POSITIVE
beside a COVID-driven guidance withdrawal (A38); an awards block does not
overpower mixed financials (A36 → NEUTRAL); profitability deterioration
dominating top-line growth is NEGATIVE (A39).

---

## 4. What this does and does not settle

- Settles: the owner-ratified G2 numbers and the interpretation in §0; the
  binding NONE convention (Rule 9); that no sweep, re-draw, re-rating or
  re-adjudication happens (design §11 — one draw, one n; the chain is closed).
- Settled later the same day: the Gate G2 pronouncement and ruling 2(b) (§1).
- Does not settle: the F5 blocker recorded in design §3.4 (`features.py` must mask
  sentiment on RISK_FACTORS and guidance on MDA / RISK_FACTORS before
  aggregation — still open); the rubric v1.3 change (ISSUED / INITIATED or a
  `guidance_present` field) — recommended, not scheduled.
- Unchanged standing rules: spend freeze; red_flags exploratory; distress_tier
  never scored; no `label_e2.py --segment`; never re-run a rater or the draw.
