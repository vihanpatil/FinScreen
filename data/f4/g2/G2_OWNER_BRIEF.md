# G2 — the owner's decision brief, in plain English (2026-09-07)

**RULED 2026-09-07 — see HANDOFF.md §3. This brief is now historical context.**

Read this instead of the 1,600-line design when deciding. Every section
says WHAT you are deciding, WHERE the detail lives, the OPTIONS with pros
and cons, and a RECOMMENDATION. Nothing here is ratified until you say so
in chat; the next session records your rulings in `HANDOFF.md` §3 and in
`data/f4/g2/draw_manifest.json` (`ratified_bars`), which unblocks
`analyze_g2.py`.

## 0. What G2 is, in one paragraph

The fine-tuned student model labeled 317,081 chunks of E2 filings (F4). Nobody
has checked whether those labels are right. G2 is the check: draw a sample,
have an independent BLIND rater (a Claude agent that sees only the text) label
the same chunks, compare mechanically, send disagreements to an adjudicator
agent, and have you rule the hard cases. The output is an agreement rate per
field with a 95% confidence interval. You then rule whether label quality is
good enough to build features on (F5). Two fields matter for the gate:
`sentiment` and `guidance_direction` ("gate-bearing" — they become features).
`red_flags` is measured only for disclosure; you demoted it on 2026-08-27 and
nothing in G2 can re-promote it.

The sample is already drawn (provisionally, at Option B) and sits in
`data/f4/g2/batches/`. Nothing has been rated. The analyzer refuses to run
until you set the bar, so the bar cannot be picked after seeing results.

Design: `data/f4/g2/G2_SPOTCHECK_design.md` (section numbers below refer to it).

## 1. The seven menu items (design §13)

### (i) Sample size — design §4.2, owner load §9

"Owner items" = rows YOU must personally read and rule on (disputed rows the
adjudicator escalates, plus a 20-row probe). That is the real cost; machine
time is $0 and there are no API calls.

| option | chunks rated | sentiment CI half-width | chance of catching a real failure* | owner items |
|---|---|---|---|---|
| A — lean | 280 (200 primary + 40 + 40) | ±5.4 pts | 80% | ~54 |
| **B — recommended, already drawn** | 420 (300 + 60 + 60) | ±4.4 | 93% | ~71 |
| B-lite | same 420, raters skip red_flags | ±4.4 | 93% | ~71 |
| C — full | 590 (400 + 80 + 80) | ±3.8 | 97% | ~86 |

*probability of a DECISIVE FAIL at a 0.90 bar if true sentiment agreement is 0.83.

- **A** — pro: least of your time. Con: one in five chance of an
  INDETERMINATE result on the one field that matters, which wastes the pass.
- **B** — pro: the knee of the curve; the draw already exists. Con: ~17 more
  rows for you than A.
- **B-lite** — pro: saves 3–5 adjudicator agent runs and calendar. Con: saves
  none of YOUR time (red_flags never reaches you), and E2 ends with "student
  red-flag error unmeasured" as its only red-flag statement.
- **C** — pro: tighter intervals. Con: +15 owner items for +4 points of power;
  flat part of the curve. Picking A or C means re-running the draw script.

**Recommendation: B.**

### (ii) The bar per field: 0.85 or 0.90 — design §6.1–6.4

The rule: PASS if the whole confidence interval sits above the bar; DECISIVE
FAIL if the whole interval sits below it; INDETERMINATE otherwise. One bar per
field, fixed before any rating, written into the manifest.

Facts you are owed first (§6.4): G1's "~0.90" floor was about a DIFFERENT
number (student vs teacher on E1's eval split). The only evidence on
sentiment is 83.6% student-vs-teacher agreement; rater noise makes the G2
number lower, not higher. So:

| bar | what PASS needs at n=253 | most likely sentiment outcome |
|---|---|---|
| 0.90 | measured ≥ 94.1% | DECISIVE FAIL (93% if truth is 0.83) |
| 0.85 | measured ≥ 89.7% | INDETERMINATE or PASS (61% PASS if truth is 0.90) |

- **0.90** — pro: high, simple, matches the number floated at G1. Con: on the
  evidence you are choosing to trigger the consequence ladder (iii) on the
  last surviving text-feature family, and the bar may sit above what two
  raters can even agree on (see v).
- **0.85** — pro: an outcome space the data can actually resolve; chunk-level
  errors average down when aggregated into filing-level features, so 0.85 at
  chunk level is a usable feature. Con: it will look like lowering the bar to
  pass. The design's own words: the prior "is not an argument for lowering
  the bar; it is the argument for ratifying what a FAIL means before it
  happens."
- Guidance uses the same choice. Note its primary is dominated by NONE rows
  (see vii), so its PASS/FAIL says less than sentiment's.

**Recommendation: 0.85 for both fields**, with (iii) ratified as proposed and
(v) option (b) bought so a FAIL is attributable. If you believe F5 is
meaningless below 0.90 chunk accuracy, choose 0.90 and accept the likely FAIL
→ ladder. Either is defensible; choosing after the data is not.

### (iii) The consequence ladder — design §6.5

What each verdict DOES. Proposed: PASS → field is gate-bearing in F5, its
measured error printed beside every derived number. INDETERMINATE → field
proceeds, its measured error becomes a first-class input to F5 reporting.
DECISIVE FAIL → you rule either (a) demote to exploratory (the red_flags
precedent) or (b) proceed with an attenuation correction on every headline;
never a silent proceed; and not executed at all if the ceiling (v) shows the
instrument could not have measured that high.

"λ row withdrawn": an earlier draft would have plugged G2's number into the
F5 power calculation as a reliability factor. That was wrong (chunk-level vs
filing-level quantities) and was removed.

- **Ratify as proposed** — pro: rules of the game agreed before playing, which
  the charter demands. Con: none real.
- **Decide after results** — con: post-hoc rationalization, exactly what the
  pre-commitment discipline exists to prevent.

**Recommendation: ratify as proposed.**

### (iv) Floors on the two guidance side-arms — design §3.2, §3.3, §6.3

G-A = 60 rows where the student made an ACTIVE guidance call (RAISED /
LOWERED / MAINTAINED / WITHDRAWN); measures how often those calls are right.
G-N = 60 rows where the student omitted the guidance key and the writer rule
wrote NONE; measures how often "omitted" hides a real active call. Half of all
applicable rows are such imputed NONEs, so G-N tests the biggest untested
assumption in the label set. Proposed: no pass/fail floor on either; they are
measurements that must be printed beside every guidance verdict (enforced in
code).

- **No floor (proposed)** — pro: one fewer bar to ratify; the numbers still
  ship. Con: no automatic tripwire on active-call precision.
- **Add a floor (e.g., active precision ≥ 0.80)** — pro: explicit tripwire.
  Con: ±10 points at n=60, so the floor is blunt and mostly INDETERMINATE.

**Recommendation: no floor.**

### (v) The two-rater ceiling — design §5.4, §6.4 fact 3

If two independent raters agree with each other only 88% of the time, no
student can score above ~88% against one of them. So a 0.90 bar could sit
above the instrument's ceiling, and a FAIL would then describe the ruler, not
the student. Today only batch 1 (40 chunks) is double-rated: ±11 points,
which cannot tell.

| option | cost | what you get |
|---|---|---|
| (a) ratify a noise-normalised criterion now | a new rule to define today | fair, but more complex |
| **(b) buy a bigger ceiling arm, n=120** | +3 rater agent runs; 0 new chunks; 0 owner items | ±6.4 pts; first size that separates the ceiling from the expected student score |
| (c) report and ignore | nothing | a FAIL may be instrument noise and you accept that |

**Recommendation: (b), n=120.** Must be ruled before rating starts.

### (vi) WITHDRAWN guidance — design §3.2, §12.5

E2 has 66 press-release chunks labeled WITHDRAWN (E1 had 1, which is why an
old rule called it non-evaluable; that rule was about E1 and does not carry).
Proportional sampling draws at most one, so its precision goes unmeasured;
WITHDRAWN does feed a feature (mapped to −1).

- **Leave unpowered (report the count)** — pro: 66 of 317,081 rows cannot
  move a filing-level feature. Con: an unmeasured value in a feature.
- **Buy a quota** (Option C's +30-row direction floor) — pro: per-direction
  precision at ±12 points. Con: ~+10 owner items and it turns G-A into a quota
  arm whose pooled number must be re-weighted.

**Recommendation: leave unpowered, disclose.**

### (vii) How the guidance primary is framed — design §6.3, §1.3

The guidance primary is computed over ~90 press-release rows, but ~46 of them
are imputed NONEs and only ~6 carry an active direction. A PASS would mostly
say "the writer rule's NONEs are right," not "RAISED / LOWERED calls are
right."

- **Proposed: keep it, with a binding caveat** — the analyzer refuses to print
  the guidance verdict without G-A precision and G-N false-NONE rate on the
  same line. Pro: same information, no extra bar. Con: the headline number is
  still coverage-dominated.
- **Alternative: make the omission-excluded rate co-primary** (only rows where
  the student actually emitted a value). Pro: reads value-correctness. Con: a
  second bar to ratify and a small n (~44 rows → wide interval).

**Recommendation: proposed (caveat route).**

## 2. Two flags outside the menu

### (a) Does the council's stop-trigger fire on the drift?

Where: `data/hardening/status/G1_council_advisory.md` §7 item 3 (you adopted
it with G1); the numbers are in `data/f4/status/F4_campaign.md` §2 and design
§3.3. The pre-commitment: stop if F4 shows behaviour the smoke never showed —
`finish=length`, sustained parse failures, or per-section agreement drift
beyond H3v2's bands. The first two did not happen. The third cannot be
computed literally (no teacher labels on E2), but the same student on E1 vs
E2 flags 9–14 points less per section, omits the guidance key 33% → 51%, and
emits sentiment on RISK_FACTORS 1% → 8%. Real, and larger than the known
under-recall.

- **Rule "does not fire"** — it is distribution drift, not agreement drift; the
  corpus changed too; G2 is precisely the measurement that answers it. Pro:
  consistent, no lost work. Con: could read as waving past a pre-commitment.
- **Rule "fires"** — the campaign is done, so "stop" can only mean "no consumer
  reads these labels before G2," which is already the gate order. Pro: honours
  the letter. Con: changes nothing operationally.

**Recommendation: rule "noted, does not fire as agreement drift; G2 is the
mandated measurement; drift disclosed."** Either way the next step is G2.

### (b) The extension stratum

Where: `HANDOFF.md` §3 entry of 2026-08-21 (~line 714), `EXPANSION_PLAN.md`
§8, design §7 and §12.6. On 2026-08-21 you ruled that the three extension
sectors (industrials, utilities, materials/real estate; 68 companies) would be
labeled only if G2's sector-stratified check shows quality holds there. But
F4 labeled the core stratum only (your W1-core ruling), so G2 cannot measure
extension sectors at all.

- **Defer** — decide after G2 and F5 on core; the extension would need its own
  labeling campaign (~11–16 nights, $0) and its own spot-check. Pro: nothing
  lost; data is ingested. Con: the promotion clause stays open.
- **Drop the extension arm** — pro: closes the item. Con: irreversible in
  spirit and unnecessary now.

**Recommendation: defer.** No action needed today.

## 3. The two build items (design §10.3, §10.4, §5.1)

Neither needs a decision beyond "go"; both are small and the next session
does them once (i)–(vii) are ruled.

1. **`.claude/agents/label-rater-blind.md`** — a ~30-line agent definition
   whose prompt is design §10.4 verbatim. Why new: the existing
   `label-auditor` agent is built to compare against stored labels and may
   answer "n/a"; G2 needs a rater that sees only text and always emits all
   three fields, because an "n/a" option would leak which fields apply to
   which section type. The analyzer hard-fails on any "n/a". Alternative
   (reuse `label-auditor` with a prompt override): rejected by the design as
   schema-incompatible. Cost: minutes.
2. **`data/f4/g2/build_adjudicator_batches_g2.py`** — after the raters finish,
   this script finds every (chunk, field) disagreement and packages it for the
   existing `label-adjudicator` agent; mirror of
   `data/hardening/spotcheck_v12/build_adjudicator_batches_v12.py`. Schemas in
   design §10.2.2. Alternative (adjudicate by hand): no, there will be ~100
   disputes. Cost: a small script plus a test.

If you choose B-lite, item 1's prompt drops the red_flags clauses (design
§10.4 last paragraph).

## 4. What happens after you rule (design §10.3)

1. Rulings recorded in `HANDOFF.md` §3 and `draw_manifest.json`.
2. If A or C: re-run `build_draw_g2.py` for that option. If B: nothing.
3. Build items 1–2 above.
4. Rate 11 batches (plus the ceiling replicates you chose) → `verdicts/`.
5. Adjudicate disagreements → `adjudications/`.
6. `analyze_g2.py` → model-consensus estimate + your 20-row probe list.
7. You rule the escalated rows and the probe (~71 items at B).
8. `analyze_g2.py` again → owner-ratified estimate → you rule Gate G2.
