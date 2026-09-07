# Owner annotation-policy rulings — spot-check v1.2 (2026-08-27, in chat)

**Provenance: these are the OWNER'S OWN rulings**, made row-by-row on the
42-row ruling packet (22 needs_human + 20 probe). They supersede the model
adjudications on those rows and are the binding interpretation of rubric
v1.2 §4/§6 wherever they speak. Any future rubric revision (v1.3) or F4
labeling QA must be consistent with them. Full per-row record:
`owner_rulings.json` / `probe_rulings.json`; final numbers:
`results_v12.json`.

## The eight locked-in policy rules (owner's own words, lightly formatted)

1. **Complex supply chain ≠ supply constraint.** There must be shortage,
   unavailable inputs, supplier disruption, inability to procure,
   constrained production, etc. (Changed A1.)
2. **Market-wide commodity supply disruption ≠ automatically the
   producer's SUPPLY_INPUT_CONSTRAINT.** (Changed A6.)
3. **Realized applies to the labeled event, not its potential
   consequence.** Existing investigation + possible fine → legal
   REALIZED. Future investigation → hypothetical.
4. **But don't infer an existing legal event from anaphora.** "Financial
   protections against such judgments" doesn't prove a judgment exists.
   (Changed A7 to stored/HYPOTHETICAL.)
5. **Safe-harbor noun/enumeration lists should generally fail mining
   depth.** Makes B6, A14, A20 and — most importantly — A8/A22
   consistent (A8 and A22 are materially the same Occidental enumeration
   and must get the same treatment: no flags).
6. **Once loan carrying-value reductions count as impairments, apply
   that consistently.** A2, A3 and A18 are all
   IMPAIRMENT_WRITEDOWN / REALIZED (includes receivable write-offs).
7. **Regulation-driven costs can double-label.** Existing regulation +
   already-incurred compliance cost → LEGAL_REGULATORY_ACTION / REALIZED
   **and** MARGIN_COST_PRESSURE / REALIZED. (A10/A16/A17 establish this.)
8. **If government payment-rate decisions count as regulatory action,
   adverse product approval/labeling decisions do too.** A4 kept stored
   (rate actions count); A12 therefore kept stored with HYPOTHETICAL
   modality — the difference is modality, not whether an agency decision
   is regulatory.

## The A4 reimbursement-policy ruling (owner's reasoning, preserved)

Adverse government payment-rate actions COUNT as regulatory action in a
healthcare-filing taxonomy, but as a **specific subtype**, not by folding
every reimbursement change into generic "regulatory action". The owner's
recommended hierarchy for any future taxonomy revision:

```
Government / Regulatory Action
  → new regulation / compliance requirement
  → enforcement / investigation
  → approval or licensing decision
  → government reimbursement/payment policy
      → adverse rate/payment change
```

Rationale (owner's, condensed): in healthcare the government is
simultaneously regulator and payer — CMS payment methodologies arrive by
statute/rulemaking, so a rate cut is causally "agency → formal rule →
mandatory change → adverse impact", and excluding it creates a
healthcare-specific blind spot. But the narrow reading (action concerning
the company's conduct or status — warning letters, investigations,
penalties, exclusions) is also defensible, and two failure modes argue
for the subtype: some rate changes are **legislative** (sequestration)
and some are **mechanical** (an existing statutory formula producing a
lower rate — no new action at all). The subtype captures both readings
without conflating regulatory/enforcement risk with government payer
risk. Boundary fixed by B13: **ordinary compliance with an existing tax
regime is NOT a regulatory action** — the line is a government
affirmatively changing policy vs. a company merely owing under standing
law.

## Watch-list

- **B11** (JPMorgan repurchase-demand/litigation-reserve chunk): ruled
  AGREE but explicitly **low-confidence — never use as a pristine
  positive training example.**

## Outcome executed with these rulings

Owner-ratified P1: **84/200 = 42.00% [35.37, 48.93]** → k = 84 = the
pre-pinned boundary → **DEMOTE = True** under the ratified §7
pre-commitment 1 (G1 council advisory, ratified 2026-08-27): the E2
red-flag feature family is **exploratory/disclosure-only in G3**,
regardless of sunk cost. Sentiment and composition features unaffected.
Probe: 0/20 overturns — no escalation; campaign complete per design §8.
