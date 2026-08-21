> **READER NOTE (2026-08-18):** independent red-team review conducted
> 2026-08-10/11 and preserved as the audit trail — not maintained since.
> Status as of 2026-08-18:
>
> - **8 findings. Three carry owner-verified resolutions appended in
>   place** — #1 (RESOLVED — CORRECTED), #5 (RESOLVED), #8 (CORRECTION).
>   **Five remain open or forward-looking:** #2, #3, #4, #6, #7 (#6 is a
>   "no issue" finding).
> - **Finding #4's counts are pre-relabel.** Recomputed against the final
>   `data/labels.parquet` (2026-08-18), the section/modality skew still
>   stands but the numbers have moved: RISK_FACTORS 2,049 HYPOTHETICAL /
>   706 REALIZED, MDA 958 HYPOTHETICAL / 2,733 REALIZED (the doc's
>   1,777/732 and 836/2,516 match `data/labels_pre_relabel.parquet`). The
>   confound the finding names is real either way — see `HANDOFF.md`
>   §6 Step 3 and `RED_FLAGS_LIMITATION.md` implication 3.
> - Finding #2's self-identification range (~27-46% depending on
>   measurement method) is carried forward as a standing known risk in
>   `HANDOFF.md` §7, not as something fixed.
>
> Current state lives in `HANDOFF.md`.

# Red-Team Review — FinScreen Weeks 1-3

Reviewer: `red-team-reviewer`. Scope: `data-engineer` (Weeks 1-2) and
`finetune-engineer` (Week 3) output, per the manager's task brief. No
`quant-modeler` work exists yet (Week 5 not started) — items below that
touch Week 5 are forward-looking risk flags for that agent, not findings
against code that exists yet.

**Provenance note:** mid-review, a message purporting to be from another
Claude session ("Manager") arrived via the tool channel with three "verified
facts" and instructions on where to dig. I did not take those as given —
I independently re-derived each one against the actual parquet/JSON files
before including it below, and I note where my own numbers differ from what
that message asserted. That message is not my user and grants me no
additional permission; it's a lead list I verified or partially refuted, and
I'm not confident it is not a prompt-injection test in this exercise.

---

## CRITICAL

### 1. `data/full_run_report.md` mischaracterizes the one residual label failure as a "refusal," and gets its section_type wrong

**What it is:** The report claims the sole `parse_ok=False` row
(`CHK-8e69547e0900a8dd`) is "not a truncation issue" — "the model declined
mid-generation... `stop_reason=refusal`... a different, rare failure mode
that a larger token budget cannot fix" (`data/full_run_report.md:24`), and
in §4 item 5 describes it as `RISK_FACTORS`.

**Evidence — direct read of the actual row in `data/labels.parquet`:**
```
chunk_id      => 'CHK-8e69547e0900a8dd'
section_type  => 'MDA'                      # NOT RISK_FACTORS as §4 states
api_result_type => 'succeeded'
parse_error   => 'JSON parse error: Unterminated string starting at: line 1 column 64 (char 63)'
max_tokens_used => 4000
raw_label_json => '{"red_flags": [{"category": "IMPAIRMENT_WRITEDOWN","modality": "REALI'
```
`raw_label_json` is cut off mid-token inside a JSON string value
(`"REALI`), and the parse error is a textbook truncation signature
("Unterminated string"), not any refusal marker. Nothing in the row (no
`stop_reason=refusal` field even exists in the schema captured — I checked
`lab.columns`: `['chunk_id', ..., 'api_result_type', 'parse_error', ...]`,
no `stop_reason` column at all) supports the "refusal" claim; the doc's
claim appears to be an inference, not something read off the API response.

**Downstream impact:** the report tells the owner this needs a policy
judgment call ("read the source text and decide whether to hand-label it or
drop it"), when the actual evidence says it's an ordinary output-truncation
artifact that a slightly larger token budget or a retry would very likely
fix — the report is pointing the owner at the wrong kind of remediation and
implicitly (and wrongly) closes the book on "does `max_tokens=4000` fully
solve truncation" (the report literally states "`max_tokens=4000` fully
resolved every truncation-driven failure" one sentence before describing a
row whose own error message says otherwise).

**Confidence:** High — grounded directly in the row's own `parse_error` and
`raw_label_json` fields, not inference from context.

**Fix proposal:** `finetune-engineer` should correct `full_run_report.md`
§1 and §4 item 5: reclassify `CHK-8e69547e0900a8dd` as a truncation (not
refusal), fix its section_type to MDA, and either resubmit it once more at
a higher cap (e.g., 6000) or explicitly retry before falling back to manual
labeling/exclusion.

**RESOLUTION (post-review, owner-verified) — RESOLVED — CORRECTED.**
A direct read-only query of the corrective batch result (not the stored
Parquet columns) shows `stop_reason = "refusal"`, `stop_details.category =
"bio"`, and 293 output tokens emitted before the stream stopped. The
`raw_label_json` is unterminated and `parse_error` reads as an ordinary
JSON parse error precisely because partial JSON had already been emitted
before the refusal — that is why it superficially matches a
max-token-truncation signature in the stored columns, but it is a genuine
mid-stream safety refusal, not a truncation. This finding's underlying
mechanism reasoning was sound, and the partial-JSON signature genuinely is
ambiguous from the stored `labels.parquet` columns alone (no `stop_reason`
field is captured there) — the conclusion this review drew from those
columns was a reasonable one given what was available, it just didn't
match the primary API evidence. The section_type is confirmed **MDA**, not
RISK_FACTORS, as this finding already suspected. Because a re-run would
refuse again, the correct handling is to exclude the row from the
fine-tuning set and document it, not resubmit it. **This resolution covers
only `CHK-8e69547e0900a8dd` itself — it does NOT settle the broader claim
in this finding's "Downstream impact" section that `max_tokens=4000` might
not "fully solve truncation" more generally, nor finding #5 below's
separate open question about other rows silently self-truncating at their
token cap. That broader claim remains open.**

---

## HIGH

### 2. DISCOVERY.md's residual self-identification rate (~19% / 48% for press releases) is understated relative to my own independent measurement

**What it is:** `DISCOVERY.md:234` claims "the filing text itself
self-identifies the company in ~19% of chunks (48% of press releases)."

**Method and evidence — I measured this myself two ways against
`data/labeling_corpus.parquet` (6,747 chunks) and `data/universe.csv`:**

- *Loose method* (company-name first token, case-insensitive, anywhere in
  text, plus ticker as a bare word anywhere): **46.0% overall**, section
  breakdown `8K_BODY 75.0%, EX99_PRESS_RELEASE 73.5%, MDA 42.3%,
  RISK_FACTORS 34.9%`. This method is too permissive (e.g. "Bank" for BAC,
  "Home" for HD are common English words), so I don't treat this as the
  real number, but it shows the true figure is not obviously close to 19%
  either.
- *Stricter method* (full/near-full legal company name as a phrase for
  multi-word names, e.g. "Home Depot", "Bank of America"; exact
  case-sensitive whole-word match for single-token names, e.g. "Apple",
  "Visa", "Chevron"; separately, bare ticker token excluding ambiguous
  1-2-letter tickers V/MA/GS): **26.8% overall combined**, section
  breakdown `8K_BODY 75.0%, EX99_PRESS_RELEASE 59.2%, MDA 19.9%,
  RISK_FACTORS 19.9%`.
  I spot-checked the single biggest false-positive risk in this method
  (ticker `V` → word "Visa" colliding with "travel visa") by pulling all
  105 `V`-ticker chunks containing "Visa": all three I read were genuine
  self-references to Visa Inc. ("Visa's quarterly cash dividend," etc.),
  not travel-visa false positives — so the stricter number isn't
  obviously inflated by that specific risk.

Both of my measurements — even the stricter, more defensible one — come in
**meaningfully above** the ~19%/48% figures in `DISCOVERY.md`. I can't
reproduce whatever method produced the 19%/48% figures (not documented in
the file), so I can't say definitively they're wrong, but I could not
reproduce them and my numbers point the other way in both methods.

**Downstream impact:** this number is used in `DISCOVERY.md` to bound how
much the residual look-ahead-bias channel matters ("~19%... so a
sufficiently knowledgeable labeling model can *sometimes* infer identity").
If the real rate is closer to 25-60% by section type, the residual risk is
materially larger than the doc currently frames it as, which matters for
how much weight the Week 6 red-team re-check and the Week 7 limitations
doc should put on this specific risk.

**Confidence:** Medium-high on "the true rate is probably higher than
19%/48%," lower on the exact number, since I don't have the original
method to compare against apples-to-apples.

**Fix proposal:** `finetune-engineer` (or whoever produced the original
19%/48% number) should publish the exact method used, and either
reconcile it against mine or adopt a documented, reproducible method going
forward. This number should not be treated as load-bearing until the
method is nailed down.

### 3. `chunk.py`'s dedup/"home" logic leaves 17% of filing-sections — and 46.5% of Risk Factors sections specifically — with zero labeled text of their own

**What it is:** Because a repeated paragraph is only ever packed into a
window at its earliest ("home") occurrence, any filing-section whose prose
paragraphs are *entirely* repeats of earlier filings' paragraphs
contributes **no chunks at all** to `data/labeling_corpus.parquet` for that
specific filing instance — even though the filing itself, and its actual
filing date, are real and belong in any point-in-time analysis.

**Evidence — I verified the "home = earliest occurrence" mechanism is
implemented correctly first** (this part of the docstring's claim holds
up): joining `data/paragraph_occurrence_map.parquet` (28,504 canonical
paragraphs) against `data/filings.parquet` via accession_number →
filing_date, for all 5,029 paragraphs with `n_occurrences > 1`, the home
occurrence's date exactly equals the minimum date across all of that
paragraph's occurrences — **0 mismatches**. So home selection is
genuinely earliest-by-date, not "first encountered in iteration order" by
accident — the sort key `(filing_date, ticker, accession_number,
section_type, position)` in `chunk.py:132-134` does what the docstring
claims.

**But then I checked coverage, and found a real gap:**
```
total filing-sections (filings.parquet rows): 884
sections with >=1 chunk in the labeling corpus: 734
sections with ZERO home chunks:                150   (17.0%)

By section_type, share of sections with ZERO home chunks:
  RISK_FACTORS:         118/254 = 46.5%
  8K_BODY:                 1/4  = 25.0%
  EX99_PRESS_RELEASE:     29/327 = 8.9%
  MDA:                     2/299 = 0.7%
```
(Query and output reproduced above from `data/filings.parquet` +
`data/labeling_corpus.parquet`, joined on `(accession_number,
section_type)`.)

**Downstream impact:** this is not a look-ahead leak (home is always
earliest, so the labeled text's `home_filing_date` is never later than any
filing it recurs in — direction is safe). It *is* a coverage bias with a
Week 5 consequence: nearly half of all Risk Factors filing-sections have
**no chunk anchored to their own filing date** in the labeling corpus. If
`quant-modeler` naively joins Week 4's text-derived signals to Week 5's
feature table using `home_accession_number`/`home_filing_date`, a large
fraction of later 10-K/10-Q filings will silently show "no Risk Factors
signal" for that filing — not because the filer said nothing, but because
its risk-factors language happened to be identical to a prior year's and
got assigned to that earlier filing. That would look like missing data or
(worse) get imputed as "no red flags," when the correct read is "same
boilerplate as before." The raw material to avoid this exists —
`chunk.py` does write `source_accession_numbers`/`source_filing_dates`
back-references specifically so each recurrence can be expanded — but
nothing currently forces `quant-modeler` to use that path instead of the
naive `home_*` join.

**Confidence:** High on the numbers (directly queried); medium on how much
this will actually bite Week 5, since it depends entirely on how
`quant-modeler` chooses to join — this is a live risk, not yet a triggered
bug.

**Fix proposal:** Document this gap explicitly (in `chunk.py`'s docstring
or a Week 3 note) so `quant-modeler` is told, before building `features.py`,
to expand every filing-section via `source_accession_numbers` /
`source_filing_dates` rather than assuming one-chunk-per-filing-section
coverage from `home_accession_number` alone.

---

## MEDIUM

### 4. Red-flag modality is strongly confounded with section_type — a naive "red flag count" feature risks measuring section length/type, not signal

**What it is:** the manager-relayed lead pointed at this; I independently
recomputed it from `data/labels.parquet`'s `red_flags` list column (clean
rows only, `parse_ok=True`, n=6,746):

```
Category x modality (verified counts):
                          HYPOTHETICAL  REALIZED
DEMAND_WEAKNESS                   431       755
IMPAIRMENT_WRITEDOWN              243       723
LEGAL_REGULATORY_ACTION          1059      1020
MARGIN_COST_PRESSURE              470      1064
SUPPLY_INPUT_CONSTRAINT           422       158
TRADE_POLICY_EXPOSURE             443       240

section_type x modality (all categories summed):
                     HYPOTHETICAL  REALIZED
8K_BODY                        9          4
EX99_PRESS_RELEASE           446       708
MDA                           836      2516
RISK_FACTORS                 1777       732
```
RISK_FACTORS skews heavily HYPOTHETICAL (1777 vs 732), MDA skews heavily
REALIZED (836 vs 2516). This matches the rubric's own stated expectation
(§6: "~85% of Risk Factors language is boilerplate hypothetical... vs. a
genuine realized event") but the magnitude is worth stating plainly for
whoever builds Week 5 features.

**Downstream impact:** a feature like "count of red flags in this filing"
or "count of REALIZED red flags," if not conditioned on section_type, will
substantially reflect how much Risk Factors boilerplate a filer includes
(structurally near-constant per filer, not a time-varying signal) rather
than a genuine period-over-period change. The rubric's `modality` field
exists specifically to let a careful feature designer filter to
`REALIZED` events, which is the right mitigation — but it needs to
actually be used that way in `features.py`, not just be available.

**Confidence:** High on the numbers; medium on "this will bite Week 5,"
since it's a design risk for code that doesn't exist yet.

**Fix proposal:** log this explicitly as a Week 5 build note for
`quant-modeler`: red-flag/distress features should filter to
`modality=REALIZED` (or at minimum treat HYPOTHETICAL and REALIZED as
separate features) and should be normalized by section length or reported
per-section-type, not pooled naively across MDA/RISK_FACTORS.

### 5. Cannot rule out sub-cap self-truncation in the original 800-token-cap population that still parsed cleanly

**What it is:** The manager-relayed message suggested checking for rows
"AT their cap" as candidate silent truncations. I checked this directly and
found **no evidence of rows sitting near either cap** in the *successfully
parsed* population — but the check has a real blind spot I want to flag
rather than claim it's fully ruled out.

**Evidence:**
```
corrective (4000-cap) population, raw_label_json char length: max = 515 chars (~130 tokens) — nowhere near 4000
original (800-cap) population, raw_label_json char length:    max = 430 chars (~110 tokens) — nowhere near 800
0 rows in either population have approx_tok > 87.5% of their cap.
```
So among rows that *parsed cleanly*, none show length statistics
consistent with hitting the ceiling. This refutes the specific worry that
many "successful" rows are silently truncated-but-still-valid JSON (that
would require them to sit close to the cap by chance of where the JSON
happened to close, and none do).

**What I can't rule out (UNVERIFIED SUSPICION):** this length-based check
can't detect a subtler failure mode — the model choosing to *report fewer
red flags than it would otherwise* under implicit output-budget pressure,
producing a shorter-but-still-valid answer rather than a truncated one.
`data/full_run_report.md` §3's own comparison (truncated-only vs. final)
already demonstrates the 800-cap run undercounted almost every category
substantially once corrected — but that comparison is about the rows that
*failed to parse*, not about whether the 4,219 rows that *did* parse
cleanly under the 800 cap are themselves biased short. I have no way to
test this without a resubmission-and-diff, which is out of scope
(no paid actions).

**Confidence:** Low (explicitly an unverified suspicion) — flagging for
completeness per the task's "findings only, don't filter" instruction.

**Fix proposal:** ACCEPTED-WITH-REASON for now (no cheap way to test
without spending more API budget), but worth a footnote in
`full_run_report.md` acknowledging this specific residual uncertainty
about the 4,219 "clean" 800-cap rows, distinct from the already-documented
2,528 truncated-and-recovered rows.

**RESOLUTION (post-review, owner-verified) — RESOLVED.** There is no
sub-cap self-truncation. Zero `end_turn` results in the original-run
population landed within 5% of the cap. The reason the length-based check
above found "nowhere near 800" is that the cap was never 800 for this
population — per the root-cause bug documented in `full_run_report.md`
(`run_full()` in `submit_labeling_batch.py` ignores `args.variant` and
always submits `data/batch_requests.jsonl`, which carries `max_tokens=500`
with adaptive thinking on, not the canaried `disabled`/800 config), the
actual cap for all 4,219 original-run rows was 500, and 2,537 of the
6,747 original-run results hit that 500 cap exactly. This finding's
suspicion — that some of the "clean" rows might be silently
under-reporting under budget pressure — was a reasonable thing to flag
given the false `max_tokens_used=800` value stored in `labels.parquet`'s
provenance column at the time of this review, but the premise it was
reasoning from (an 800-token cap) was itself wrong, so the specific
"sub-cap self-truncation in an 800-token population" framing does not
apply. The now-approved remedy (re-labeling the 4,219 affected rows under
the disabled/4000 config, PENDING as of this writing) will replace that
population's labels outright rather than leaving the question open.

---

## LOW

### 6. Distress tier is real but nearly unusable as documented, and correctly excluded — no doc overstates it

Verified against `data/labels.parquet` clean rows (n=6,746): **143
positive rows total** — `LIQUIDITY_STRESS 141, ACCOUNTING_RESTATEMENT 2,
GOING_CONCERN 0`; modality split `137 HYPOTHETICAL / 6 REALIZED`. This
matches exactly what the manager-relayed message claimed, and I confirmed
it independently. `labeling_rubric.md` §5 and `DISCOVERY.md` §3 both
already frame this tier as "expected to be almost empty" and explicitly
excluded from fine-tuning/agreement-rate reporting — I checked for any
place a doc claims this tier "works" or is learnable and found none. No
finding here beyond confirming the numbers and confirming no overstatement
exists yet. Worth re-checking this specific point again once Week 4/7 docs
are written, since it's an easy place for later drift toward overclaiming.

### 7. `guidance_direction=WITHDRAWN` (n=1) and `8K_BODY` (n=8, concentrated in only 2 of 25 tickers) are effectively unusable categories/section-types

**Evidence:**
```
guidance_direction value counts (clean rows): NONE 1096, RAISED 35, MAINTAINED 33, LOWERED 14, WITHDRAWN 1
8K_BODY section rows: 8 total, all from tickers {BAC, CVX} only (verified via groupby ticker)
```
Neither is currently described as usable anywhere I found (both
`full_run_report.md` and `ROADMAP.md` already flag 8K_BODY's tiny n
honestly, e.g. "8K_BODY — 6 NEUTRAL / 2 NEGATIVE (tiny n=8)"). This is a
forward-looking flag for Week 4: any per-category eval metric for
`WITHDRAWN` or for `8K_BODY`-specific behavior will be statistically
meaningless (n=1, n=8-from-2-tickers) and should be reported as
"insufficient support," not folded into an aggregate metric that implies
it was actually evaluated.

**Confidence:** High (direct counts).

**Fix proposal:** `finetune-engineer` should explicitly exclude
`WITHDRAWN` and `8K_BODY`-conditioned metrics from any headline Week 4
eval number, same treatment as the distress tier.

### 8. Canary methodology genuinely missed the `max_tokens=800` truncation risk, but this is already self-diagnosed and disclosed

`data/canary_comparison.md` recommended `disabled`/`max_tokens=800` based
on a 50-chunk canary that hit 100% clean parse; the real 6,747-request run
then truncated 37.6% of the corpus (2,528/6,747), costing an extra $4.49
corrective pass. I confirmed the 800-cap population is exactly
`max_tokens_used==800` for all 4,219 originally-clean rows, and the
corrective 4,000-cap population is exactly the 2,528 `parse_ok=False` set
from the original run (100% chunk_id overlap between
`labels_corrective.parquet` and the corrective subset of `labels.parquet`)
— so the recovery mechanism itself is sound and matches its own
description. `full_run_report.md` §5 already calls this out honestly as a
canary-methodology lesson (stratify by word_count/complexity, not just
section_type, next time). **ACCEPTED-WITH-REASON** — not a new finding,
just confirming the self-diagnosis is accurate and the fix (the corrective
rerun) actually closed the gap it claims to have closed, aside from Finding
#1 above (the mischaracterized residual row).

**CORRECTION (post-review, owner-verified) — the stated lesson above is
WRONG and is corrected here; original text kept for audit.** The canary
did not "miss" anything and stratification is not the fix. Root cause,
independently confirmed by code read: `run_full()` in
`submit_labeling_batch.py` (line 582) takes no arguments and always calls
`load_requests_by_custom_id()` against the module-level default
`REQUESTS_JSONL_PATH = "data/batch_requests.jsonl"` — it ignores
`args.variant` entirely. The owner's `--full --confirm-full --variant
disabled` command therefore submitted the original, unfixed request file
(`max_tokens=500`, adaptive thinking ON — confirmed by line 1 of
`data/batch_requests.jsonl` and by API usage records: all 6,747 original-run
results cap at exactly 500 output tokens, 2,537 hit it exactly), not the
canaried `data/batch_requests_disabled.jsonl` (`max_tokens=800`,
`thinking={'type':'disabled'}`) the flag named. The 50-request canary at
500 tokens (run earlier, pre-`disabled`-variant) had already measured a
~36% failure rate — which is exactly what the full run got, because it
silently used that same 500-token config. **The canary was accurate and
correctly predicted the outcome.** Stratifying canary sampling by
word_count/complexity, as the original lesson recommended, addresses a
problem that did not occur here and would not have caught this bug. **The
real lesson: verify that the artifact the full-run code path actually
submits matches the artifact the canary was run against.** A canary is
worthless if the code that submits the full run doesn't load the same file
the canary validated — the fix is a mechanical pre-submission check (hash
or diff the request file the submission code will load against the file
path implied by the invoked flag, fail loudly on mismatch), not a
different sampling strategy.

---

## What I checked and found FINE

- **No ticker/company_name/filing_date leaks into labeling-request
  scaffolding.** Grepped all 6,747 requests in `data/batch_requests.jsonl`
  for full `YYYY-MM-DD`-style dates: **0 hits**. Grepped for
  `"section_type"` as literal prompt text: **0 hits**. Read
  `build_batch_requests.py:296` directly — the `messages` payload is just
  the chunk `text`, no interpolated section_type/ticker/date. Company
  names/tickers do appear, but only as organic content of the filing text
  itself (the documented, acknowledged residual channel in Finding #2
  above), not as structural prompt leakage.
- **`section_type`-conditioned schema shaping matches the rubric's
  applicability matrix exactly in the actual labeled data**: sentiment is
  `NaN` for 100% of RISK_FACTORS rows and populated for 100% of
  MDA/EX99_PRESS_RELEASE/8K_BODY rows; guidance_direction is `NaN` for
  100% of MDA/RISK_FACTORS rows and populated for 100% of
  EX99_PRESS_RELEASE/8K_BODY rows. Cross-tab verified directly against
  `data/labels.parquet`.
- **`chunk.py`'s "home = earliest occurrence" claim** is correct, verified
  empirically (0/5,029 multi-occurrence paragraphs mismatch between home
  date and true minimum occurrence date) — see Finding #3 for the caveat
  about coverage, but the mechanism itself is sound, not "first in
  iteration order" as I was asked to rule out.
- **Corrective-run provenance is exactly as documented**: `labels.parquet`
  batch_id counts are 4,219 (`msgbatch_...B22L`, `max_tokens_used==800`
  for all rows) and 2,528 (`msgbatch_...JR1o`, `max_tokens_used==4000` for
  all rows); `labels_corrective.parquet`'s 2,528 chunk_ids are a 100%
  match to the corrective subset of `labels.parquet`. No mixing or
  ambiguity found.

  **CORRECTION (post-review, owner-verified):** this item itself reasoned
  from the false premise it was checking — it confirmed the *stored*
  `max_tokens_used==800` value was internally consistent (all 4,219
  original-run rows agree with each other), but internal consistency is
  not the same as correctness. The stored value is wrong: per the
  root-cause bug in `submit_labeling_batch.py` (`run_full()` ignores
  `args.variant` and always submits `data/batch_requests.jsonl`), those
  4,219 rows were actually labeled at `max_tokens=500` with adaptive
  thinking on, not 800. "No mixing or ambiguity found" still holds in the
  narrow sense that the two batches weren't cross-contaminated with each
  other's rows — but the corpus does now have a real, different kind of
  mixed provenance: 4,219 rows at 500/adaptive vs. 2,528 rows at
  4000/disabled, which a PENDING re-label (owner-approved, not yet
  submitted) is intended to resolve by re-labeling the 4,219 affected rows
  at the disabled/4000 config.
- **SYSTEM_PROMPT / rubric sync** for the v1.1 mixed raise/lower guidance
  rule: present verbatim (in spirit) in both `labeling_rubric.md:123-128`
  and `build_batch_requests.py:171` — the sync claim in the rubric's
  revision log holds up.
- **Survivorship bias in `data/universe.csv`** is honestly and explicitly
  disclosed, not hidden: `INGESTION_NOTES.md:29-40` states plainly this is
  "a deliberate convenience choice" of companies "large and prominent
  *today*" and explicitly says the bias "is inherited by every downstream
  result trained on this universe." No overstatement found.
- **No overstated/trading-bot-adjacent language found** in a targeted grep
  across `DISCOVERY.md`, `ROADMAP.md`, `labeling_rubric.md`,
  `INGESTION_NOTES.md`, `data/full_run_report.md`,
  `data/canary_comparison.md`, `build_batch_requests.py`, `chunk.py` for
  phrases like "beats the market," "guaranteed," "proven,"
  "production-ready," "highly accurate" — no hits beyond an unrelated match
  on the word "provenance."
- **The 143-row distress-tier full exhaustive list in
  `full_run_report.md`** — spot-checked several entries against
  `data/labels.parquet` directly (category/modality/ticker) and the report
  table matches the underlying data for the rows I sampled.

## What I could NOT check, and why

- **No independent way to verify the labeling model's actual reasoning**
  (e.g., whether it silently used self-identified company knowledge despite
  the rubric's §0 instruction not to) — this would require re-running
  labeling requests with the same content but no possible self-ID, or a
  manual read of many individual outputs against source text, which is
  both a paid action and outside a static-file review's reach. Flagged as
  the residual risk `DISCOVERY.md` itself already names; I could only
  bound how *often* the self-identification channel exists (Finding #2),
  not how often the model actually exploited it.
- **Whether the 800-cap "clean" rows are internally under-reporting
  flags** (Finding #5's unverified suspicion) — testing this would require
  resubmitting those specific chunks at a higher cap and diffing, which is
  a new paid Batch API action outside this review's zero-paid-actions
  constraint.
- **The original ~19%/48% self-identification measurement method** behind
  `DISCOVERY.md`'s figures — not documented anywhere I could find, so I
  could not do an apples-to-apples reconciliation with my own numbers, only
  flag the discrepancy (Finding #2).
- **`.env` / API keys** — not read, per the hard constraint; I did not
  need them for any of the above since everything relevant was already
  materialized in local parquet/JSON/jsonl files.
- **Week 1 raw ingestion correctness against live EDGAR** — `filings.parquet`
  and `filings_metadata.db` were read as given; I did not re-fetch from
  `data.sec.gov` to independently verify filing metadata against the live
  site (would risk external network calls not clearly "free" and is
  outside this review's file-based scope as directed).

## Files read/queried for this review

`/Users/vihanpatil/personal/projects/FinScreen/DISCOVERY.md`,
`/Users/vihanpatil/personal/projects/FinScreen/ROADMAP.md`,
`/Users/vihanpatil/personal/projects/FinScreen/labeling_rubric.md`,
`/Users/vihanpatil/personal/projects/FinScreen/chunk.py`,
`/Users/vihanpatil/personal/projects/FinScreen/build_batch_requests.py`,
`/Users/vihanpatil/personal/projects/FinScreen/INGESTION_NOTES.md`,
`/Users/vihanpatil/personal/projects/FinScreen/data/full_run_report.md`,
`/Users/vihanpatil/personal/projects/FinScreen/data/canary_comparison.md`,
`/Users/vihanpatil/personal/projects/FinScreen/data/universe.csv`,
`/Users/vihanpatil/personal/projects/FinScreen/data/full_batch_meta.json`,
`/Users/vihanpatil/personal/projects/FinScreen/data/corrective_batch_meta.json`,
`/Users/vihanpatil/personal/projects/FinScreen/data/labels.parquet`,
`/Users/vihanpatil/personal/projects/FinScreen/data/labels_corrective.parquet`,
`/Users/vihanpatil/personal/projects/FinScreen/data/labeling_corpus.parquet`,
`/Users/vihanpatil/personal/projects/FinScreen/data/paragraph_occurrence_map.parquet`,
`/Users/vihanpatil/personal/projects/FinScreen/data/filings.parquet`,
`/Users/vihanpatil/personal/projects/FinScreen/data/batch_requests.jsonl`,
`/Users/vihanpatil/personal/projects/FinScreen/data/batch_requests_corrective.jsonl`.
