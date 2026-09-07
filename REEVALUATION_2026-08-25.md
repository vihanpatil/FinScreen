# RE-EVALUATION — 2026-08-25 (owner-commissioned)

**Commissioned by the owner in these words:** *"I don't want to be going
down a hole, making a product that is not really useful, outdated and
just a waste of code and tokens. I need a brutally honest re-evaluation."*

**Method:** four independent Opus lenses (kill-case / methodology /
decision-audit / alternatives), each working read-only from artifacts
and re-deriving numbers rather than trusting reports, synthesized here
by the main session. Full lens reports:
`data/reevaluation_2026-08-25/{kill_case,methodology_audit,decision_audit,alternatives}.md`.
Every number below was independently re-derived by a lens this session
unless marked otherwise.

---

## 1. The verdict

**Continue — the kill case loses. But it wins a narrower claim that
matters more: the current trajectory is optimizing the wrong
deliverable, and the fixes are days and $0, not weeks.**

You are not in a hole. Forward cash is $0, the heaviest sunk cost
(ingestion) is the most reusable asset, E1's null had a real diagnosed
cause (MDE 0.077 exceeded every effect ever observed in the data), and
E2 genuinely fixes that cause — the panel *verified the power design
exists*: a mean of 96.1 price-usable core companies per quarter (min 84)
across 30 quarters, re-derived from the E2 database this session.

But three things are true that no document said before today:

1. **E2, as currently specified, cannot answer its own question.** One
   routine, look-ahead-free preprocessing choice (PIT cross-sectional
   ranks instead of raw levels) moves E1's headline text-vs-numeric
   delta by **0.056 — three times E2's optimistic MDE** — and ranking
   companies by size alone beats both fitted models (IC 0.224 vs 0.097
   / 0.088), because size-like features have ICC ≈ 0.99 and both arms
   mostly encode company identity. Until the specification is
   pre-registered and zero-information benchmarks are standing report
   rows, a bounded null is not defensible. (Methodology lens; its
   replication reproduced the published per-fold deltas exactly first.)
2. **The measuring instrument got worse while the sample got bigger,
   and the trade was never priced.** The MDE bracket was computed
   2026-08-20; the labeler evidence arrived 2026-08-21/22. Simulated
   through the student's own confusion matrices, the feature most
   likely to carry signal (`sentiment_negative_share`) retains only
   ρ ≈ 0.57 of its Claude-labeled version; honest unmodelled power loss
   ~15–25%. The published MDE is also ~1.5× optimistic on its own terms
   (a ddof=0 population-std over six numbers whose 95% CI spans 3.9×;
   measured model-model ρ = 0.828, not the assumed 0.92). One genuinely
   good discovery: a within-fold bootstrap identifies the regime-noise
   floor at **zero**, so more companies DO buy power. Honest achievable
   MDE: ~0.029–0.049 in true-construct units.
3. **There is no stopping rule.** ROADMAP ends at "G4: final read."
   E1 nulled → diagnosed underpowered → 10× bigger experiment. The same
   locally-valid reasoning is available after E2 (labeler noise, no
   mid-cap arm, floor arguments), and nothing pre-commits what a null,
   a positive, or — most dangerous — an ambiguous result *does*. The
   ladder has no top because nobody built one. One ratified paragraph
   fixes this.

## 2. Direct answers to your questions

**"Am I going down a hole?"** No — but the panel found the canonical
sunk-cost signature in our own decision log and named it: the fine-tune
gate ("only if Week 5 shows real signal") inverted into the reason to
expand when Week 5 showed none. The re-justification was legitimate
($0 local labeler is the only labeler under the spend freeze), but the
*shape* is the warning, and the missing stopping rule is how holes
happen. Strong counter-evidence was also recorded: this project
pre-committed a null, produced one, published it unspun, and red-teams
itself into worse results — that is the opposite of hole-digging.

**"Is it outdated?"** The core stack is sound 2026 practice
(frontier-bootstrap → local distillation, GBDT on small tabular, honest
walk-forward). What IS dated is the **text representation**: 22
hand-designed rate features (52.2% of E1 observations carried no
MDA/Risk-Factors text at all; guidance NaN on 90.2% of rows), no
embeddings, and — the sharpest gap — **zero year-over-year
language-change features**, which is the best-surviving text→return
effect in the literature ("Lazy Prices"), costs no labeling at all, and
is computable from the 42 GB already on disk. The numeric baseline is
also a strawman: no momentum, no volatility, no valuation ratio, no
size — no price information on the right-hand side at all.

**"Is it duplicative / not useful?"** The question E2 asks (LLM-labeled
tone in LARGE caps, quarterly horizon) is the most-trodden
configuration in the field and the literature's answer is "barely, and
less every year." The genuinely scarce assets are: the
survivorship-safe PIT membership panel with its measured censoring
profile; the EDGAR failure taxonomy (PSEG's 45/45 decks, the cover
pages, float mis-scalings, dead-ticker traps — *nobody writes this
down*); and the teacher-noise-ceiling eval pattern. The publishable
piece is the infrastructure-and-failure-taxonomy write-up with the
bounded null as epilogue — not the null as thesis. Notably: **zero
prior-work references exist anywhere in the repo** — a gap to fix
whichever direction you choose.

**"Evaluate my decisions."** ~24 consequential decisions graded: **14
SOUND, 7 DEFENSIBLE-BUT-DEBATABLE, 3 SHOULD-REVISIT.** The record is
genuinely strong — decisions made after measurement, provenance held
through 1,222 judgments. The three SHOULD-REVISITs: (a) the **spend
freeze priced as a pricing exercise** — a rubric-v1.2 re-label of all
6,747 training rows costs ~$16.09 at measured rates and is 10× cheaper
now than after F4; not a recommendation to spend, but the trade should
be decided, not inherited; (b) **document-selection error was patched,
never estimated** — apply the project's own Tier-C protocol (random
sample + Wilson CI) to EX-99 selections before F3; (c) **F4's scale is
understated 1.2–2.1×** (measured novelty rates: ~122k chunks
member-spell-only, ~220k full-window, vs the plan's ~105k) — and
cross-company dedup is a myth (exactly 1 of 28,504 paragraphs is shared
across tickers), so the choice of labeling window is the largest
untested cost lever.

## 3. Measured closures (open items you can stop carrying)

- **Enbridge**: its float is the corpus's only CAD float fact; at ~0.78
  it is ~USD 66–67B → ranks 4th–5th in energy core → **membership
  unchanged under conversion**. Your USD ruling needs a few lines plus
  a FATAL-on-second-non-USD-reporter, not an FX subsystem.
- **SIC look-ahead**: measurable from cached filing-index headers
  (declared "unmeasured" wrongly): **10 of 243 members changed SIC
  in-window, ≥4 crossing sector buckets** (~1.6%) — a bounded footnote
  now, not an open wound.
- **GLD**: holds 2 of 1,100 core member-date seats, filed zero earnings
  8-Ks (structurally text-empty), 7/14 fundamentals families ABSENT.
  Your retention ruling stands complete; the one live question is its
  treatment in the G3 benchmark average.

## 4. The recommended path (synthesis of all four lenses)

**Pre-F3 hardening package (~1 week, $0, all on data already on disk):**
1. **Positive controls** — T1: do 5,552 in-membership earnings events
   show the known announcement-return/surprise relation? T2: does a
   documented numeric anomaly (PEAD, momentum) appear in this exact
   harness? If not, there's a plumbing bug and E2 is dead before F3
   spends a session. Near-strictly dominant over starting F3 first.
2. **Specification pre-registration** — PIT cross-sectional ranks as
   primary, raw levels as mandatory secondary; two standing
   zero-information benchmark rows in every report; ddof fix; bootstrap
   noise anchor; honest MDE restated in EXPANSION_PLAN before G3.
3. **Attenuation check** — one overnight: student relabels E1's 6,746
   chunks, re-run E1's backtest, measure what the labeler downgrade
   does to features and IC. Retires the largest unexamined threat
   before F4, not at G4.
4. **Doc-selection Tier-C sample** — ~60–100 random selections, Wilson
   CI, half a day.
5. **Stopping rule ratified** — pre-committed responses to all three E2
   outcomes, including the ambiguous branch and an explicit E3 policy.
6. **Prior-work section** — position against Loughran-McDonald, Lazy
   Prices, FinBERT-era results; one honest page.

**Plan amendments (decided by owner, below):** defer extension-stratum
labeling until after G2 (28% of F4 cost, 0% of primary power); add the
two zero-labeling text families (filing-change + embeddings) and the
missing numeric factors before F4; run three heads at F5 (the
pre-registered return target, the volatility/informativeness event
study on 5,552 events, exit prediction on 86 exit CIKs) — two of the
three test hypotheses the literature says are TRUE.

**G1 (yours, now informed):** sentiment 83.5% is ~6.5 points under the
plan's own ~0.90 floor with NEGATIVE recall 0.487; red_flags is at the
teacher's ceiling; guidance is a non-issue post-rule (98.4%, but
majority-class-carried — 11/17 on real guidance). The gate's stated
floor is failed and the honest options are: accept with a declared
attenuation caveat, train a third epoch first (~1 night; epoch 1→2
moved NEGATIVE recall 0.425→0.487), or hold. A gate with no failure
branch is not a gate — this one now has branches.

**Identity (yours):** the charter says research instrument; your
commissioning language says product. They demand different work, and
the charter forbids advice and execution — *not usefulness*. The panel's
view: keep the charter, treat the pipeline + corpus + methods trail as
the asset, let the backtest be one application, and ship the
failure-taxonomy write-up whatever the result. But this is the decision
that shapes everything downstream, and it is yours.

---

*Advisory provenance: all four lens verdicts are model judgments
(Opus), synthesized by the main session (Fable). Nothing here is the
owner's ruling until the owner rules. The tech-council agent
(`.claude/agents/tech-council.md`) now exists for exactly these
decisions going forward.*
