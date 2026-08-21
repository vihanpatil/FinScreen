> **READER NOTE (2026-08-18):** this document accumulated in layers as the
> labeling runs unfolded. **The `FINAL CONSOLIDATED STATE` section at the
> bottom supersedes every earlier number it restates** (earlier sections
> say $23.45 spend and 143 distress positives — those were true mid-stream;
> final is $33.51 and 162). Kept intact as the audit trail. Current state
> lives in `HANDOFF.md`. Four caveats on that supersession:
>
> 1. **The FINAL section's own budget line is superseded in turn.** It
>    reads "$33.51 of $50 ($16.49 remaining)". There is no remaining
>    budget: the owner's standing rule (`HANDOFF.md` §5) is **no further
>    Anthropic API spend, period** — not "spend the remaining $16.49."
>    Read the $33.51 total as final and the "/ $50" framing as dead.
> 2. **§3's red-flag numbers had no current replacement until now.** The
>    FINAL section never restated §3's per-category red-flag table, its
>    modality split, or its "rows with ≥1 flag" rate — all three are
>    pre-relabel. Current values are published below in a dated
>    **2026-08-18 CURRENT PER-CATEGORY COUNTS** block appended to the FINAL
>    section. §3's own table is left as written.
> 3. **§6 points at "`spotcheck/README.md`'s hold banner".** That banner is
>    long gone — `spotcheck/README.md` now carries a ✅ COMPLETE banner, so
>    the pointer resolves to the opposite message. The spot-check ran and
>    finished on 2026-08-18.
> 4. **§4's spot-check design describes 143 distress positives and a
>    3-tier sample.** The sample as actually built is A=162 / B=142 / D=60
>    / C=36 = 400, with a Tier D that did not exist when §4 was written.

# Labeling Run Report — CONSOLIDATED FINAL (original + corrective pass)

**Output:** `data/labels.parquet` — 6,747 rows, one per corpus chunk, merged from two Batch API passes.

| Pass | Batch ID | Config (as originally documented — SUPERSEDED, see correction below) | Requests | Ended |
|---|---|---|---|---|
| Original full run | `msgbatch_01QAM68H5YWLEDJNcyFcB22L` | ~~`disabled`, `max_tokens=800`~~ → **actually `adaptive` (thinking ON), `max_tokens=500`** | 6,747 | 2026-08-11T00:44:52Z |
| Corrective re-run | `msgbatch_01Mw3sFCi3fZXnV5U86PJR1o` | `disabled-4000`, `max_tokens=4000` | 2,528 (exact `parse_ok=False` set from the original run) | 2026-08-11T02:33:42Z |

Every row in `data/labels.parquet` carries `batch_id`, `max_tokens_used`, and `labeled_at` provenance columns so it's traceable which pass produced which label. **Correction (2026-08-10): the `max_tokens_used=800` value stored for the 4,219 rows from the original full run is FALSE — see the root-cause correction immediately below.**

---

## CORRECTION (2026-08-10) — root cause of the original run's truncation was misdiagnosed; this section supersedes the "canary didn't sample the long tail" narrative below

**What actually happened:** `run_full()` in `submit_labeling_batch.py` (line 582) takes no arguments and calls `load_requests_by_custom_id()` with the module-level default `REQUESTS_JSONL_PATH = "data/batch_requests.jsonl"`. It **ignores `args.variant` entirely.** The owner's command, `--full --confirm-full --variant disabled`, was therefore silently submitted against the *original, unfixed* `data/batch_requests.jsonl` — not the canaried `disabled`/800-token config the flag named. There was no config-selection bug in the canary or in the labeling logic; the bug is that the full-run submission path never read the variant flag at all.

**Evidence (three independent lines):**
1. **Code.** `run_full()` at `submit_labeling_batch.py:582` has no parameter for variant and hardcodes the default `REQUESTS_JSONL_PATH`.
2. **Request file contents.** `data/batch_requests.jsonl` line 1 carries `max_tokens=500` and no `thinking` key (i.e., adaptive thinking was ON) — this is the file that was actually submitted. `data/batch_requests_disabled.jsonl` (the file the `--variant disabled` flag was supposed to select) carries `max_tokens=800` and `thinking={'type':'disabled'}`.
3. **API usage records.** Output-token counts for all 6,747 results in the original run cap at exactly 500 (max=500, p95=500) — impossible under an 800-token cap. 2,537 of the 6,747 results hit exactly 500 tokens.

**This retracts the "canary sampling gap" explanation entirely.** The canary did not fail to sample the long tail — the 36% failure rate the first canary measured at `max_tokens=500` **correctly predicted** the full run's 37.6% truncation rate, because the full run silently used that same 500-token config. The canary methodology was accurate; the bug was a config-delivery bug downstream of it, in the submission code path, not a validation gap. (See the corresponding correction appended to REDTEAM_WEEK3.md finding #8.)

**Consequence — mixed provenance, PENDING remediation:** `data/labels.parquet`'s `max_tokens_used=800` value for the 4,219 rows from batch `msgbatch_01QAM68H5YWLEDJNcyFcB22L` is **false**; the actual config for those rows was `max_tokens=500` with adaptive thinking on. The corpus therefore currently has **mixed provenance**: 4,219 rows labeled at 500/adaptive, and 2,528 rows labeled at 4000/thinking-disabled (the corrective pass, which used the correct file and is not affected by this bug). **The owner has approved re-labeling the 4,219 affected rows with the disabled/4000 config, at an estimated $5-9, so the whole corpus has homogeneous provenance. This re-label has NOT been submitted yet — status: PENDING.** Everything below this point in the document reflects the pre-correction understanding and should be read with the above in mind; numeric label-distribution results are unaffected (they're measured from the actual returned data, not from the mistaken config label), but any text describing *why* rows truncated, or asserting the original run's config was `disabled`/800, is superseded by this section.

---

## 1. Final parse rate

| Metric | Value |
|---|---|
| Total rows | 6,747 |
| **Final parse_ok** | **6,746 / 6,747 = 99.99%** |
| Original-pass clean (before correction) | 4,219 / 6,747 = 62.5% |
| Corrective-pass clean | 2,527 / 2,528 = 99.96% |
| Residual failures after both passes | **1** |

**The one residual failure is not a truncation issue.** `chunk_id=CHK-8e69547e0900a8dd` (`MDA`, `IMPAIRMENT_WRITEDOWN` category) came back with `stop_reason=refusal` on the corrective run (re-queried directly from the Batch API, read-only) — `stop_details.category=bio`, with 293 output tokens of partial JSON emitted before the stream stopped. The stored `raw_label_json` is therefore an unterminated string and `parse_error` reads as a JSON parse error, which makes it superficially resemble a max-token truncation — it is not one. `max_tokens=4000` fully resolved every truncation-driven failure (2,527 of the 2,528 resubmitted requests hit clean `end_turn` completion); this single refusal is a different, rare failure mode that a larger token budget cannot fix. **Not resubmitted, per instructions** — a re-run would refuse again, so the correct handling is to exclude it and document it here rather than attempt further resubmission.

---

## 2. Real billed cost & cumulative project spend

| Component | Real cost (intro pricing) |
|---|---|
| First canary (pre-session, max_tokens=500, single variant) | $0.27 |
| Dual-variant canary (`disabled` $0.2856 + `adaptive-low` $0.3566) | $0.64 |
| Original full run (`disabled`, 6,747 requests) | $18.05 |
| **Corrective re-run** (`disabled-4000`, 2,528 requests) | **$4.49** |
| **Cumulative total** | **$23.45 / $50** |

Corrective run detail (real billed usage, intro pricing): 2,296,084 input tokens, 265,014 output tokens, 13,383 cache-write tokens, 8,430,488 cache-read tokens → $4.491 at intro / $6.7365 at standard pricing. Cache behavior was again excellent (minimal writes, heavy reuse of the 1h-TTL system-prompt cache).

**$26.55 remaining against the $50 ceiling** — comfortable headroom for the QLoRA fine-tune's GPU rental, still gated on its own explicit sign-off (provider/instance/estimated hours) per the standing rule.

---

## 3. Final label distributions (n=6,746 clean rows) — and how the correction shifted them

The original 62.5%-clean view was a **biased subset**: rows that truncated were systematically the ones needing more output tokens, which correlates with longer text and more red-flag/distress-tier matches. The corrective pass recovers that missing tail. Comparing the two:

### Sentiment

| Label | Truncated-only view (n=4,219) | **Final (n=6,746)** |
|---|---|---|
| NEUTRAL | 2,434 (57.7%) | 3,444 (51.1%) |
| POSITIVE | 678 (16.1%) | 1,035 (15.3%) |
| NEGATIVE | 168 (4.0%) | 661 (9.8%) |

NEGATIVE more than tripled in absolute count and roughly 2.5x'd in share (4.0% → 9.8%) once the previously-truncated chunks were recovered — the clearest evidence of the bias the earlier report flagged: chunks with more to say (including negative characterizations) were exactly the ones more likely to need more than the (as now corrected, see the section above) actual 500-token cap the original run used. **The final distribution should be treated as the more trustworthy one for downstream modeling.**

By section_type (final): MDA — 2,811 NEUTRAL / 627 POSITIVE / 523 NEGATIVE; EX99_PRESS_RELEASE — 627 NEUTRAL / 408 POSITIVE / 136 NEGATIVE; 8K_BODY — 6 NEUTRAL / 2 NEGATIVE (tiny n=8).

### Guidance direction

| Label | Truncated-only (n subset) | **Final** |
|---|---|---|
| NONE | 645 | 1,096 |
| RAISED | 21 | 35 |
| MAINTAINED | 7 | 33 |
| LOWERED | 4 | 14 |
| WITHDRAWN | 0 | 1 |

MAINTAINED went from a thin 7 to 33 — the previously-truncated view was undercounting explicit reaffirmation language specifically. RAISED:LOWERED is now 35:14 (was 21:4) — still raised-heavy, but less extremely so than the earlier snapshot suggested; worth continuing to spot-check both directions.

### Red flags (all instances, multi-label)

| Category | Truncated-only view | **Final** |
|---|---|---|
| LEGAL_REGULATORY_ACTION | 991 | 2,079 |
| MARGIN_COST_PRESSURE | 279 | 1,534 |
| DEMAND_WEAKNESS | 263 | 1,186 |
| IMPAIRMENT_WRITEDOWN | 230 | 966 |
| TRADE_POLICY_EXPOSURE | 157 | 683 |
| SUPPLY_INPUT_CONSTRAINT | 97 | 580 |

Every category roughly doubled to quintupled in count — confirms the bias was not category-specific; it affected essentially all red-flag types proportionally, consistent with "chunks that trigger flags tend to need more output tokens regardless of which flags." Rows with ≥1 red flag: 4,008/6,746 (59.4%), up from 4,120/6,747 in the earlier *raw* (uncorrected) count — note that earlier "4,120/6,747" figure in the original run's own printed summary counted *all* rows including truncated ones with partial/garbage JSON that happened to contain a flags-like fragment, so it's not directly comparable; the 59.4% figure here is the trustworthy one (clean rows only).

By section_type (final), LEGAL_REGULATORY_ACTION still dominates RISK_FACTORS (968 of that section's positive instances) as expected for Item 1A boilerplate, but is now also the largest category in MDA (813) and EX99_PRESS_RELEASE (294) — a pattern that was present but understated in the truncated view.

Modality split (final): 3,068 HYPOTHETICAL / 3,960 REALIZED — leans more REALIZED than the small canary's near-even split suggested; worth confirming this isn't an artifact of longer/later-in-passage flag mentions skewing toward "REALIZED" framing (the rubric's tie-break rule that a concrete realized statement controls over preceding hypothetical framing) in a spot-check.

### Distress tier — exhaustive positive list, per the owner's spot-check requirement

**143 positives out of 6,746 clean rows (2.12%)** — up from 38/4,219 (0.90%) in the truncated-only view. This is the single largest proportional shift in the whole correction: **the distress-tier category was the most under-counted by the truncation bias**, more than doubling as a share of the corpus once the recovery pass ran. This makes sense mechanically — a chunk that discusses liquidity/going-concern/restatement language in enough depth to trigger the category is also a chunk with more to say, and more likely to have hit the (actual, corrected) 500-token ceiling before finishing its full JSON output (including possibly a red_flags array on top of the distress_tier array).

Category breakdown (final): LIQUIDITY_STRESS 141 instances, ACCOUNTING_RESTATEMENT 2 instances (`CHK-95a7cf23f319ee70` NVDA 10-K, `CHK-d74facbd628dfc96` BAC 10-K — both HYPOTHETICAL), GOING_CONCERN 0. Modality: 137 HYPOTHETICAL / 6 REALIZED.

**Sector concentration** (unchanged pattern from the earlier partial view, now with a much larger n to confirm it): financials and energy names dominate — BAC (37), OXY (25), GS (21), CVX (15), JPM (14), COP (11), with the remaining 20 spread across V, UNH, MA, PG, NVDA, MRK, ABBV, AAPL, HD, KO (1–4 each). This is structurally expected (bank/energy-company risk-factor sections routinely discuss capital/liquidity adequacy as standard disclosure, not necessarily real distress) and the 137:6 HYPOTHETICAL:REALIZED ratio supports "mostly boilerplate, not real distress signal" as the aggregate read — but per the owner's stated review policy every one of the 143 gets looked at, so the full list follows.

**Full exhaustive list (143 rows, sorted by chunk_id):**

| chunk_id | section_type | ticker | form | category/modality |
|---|---|---|---|---|
| CHK-0155a36a6f8dca5a | EX99_PRESS_RELEASE | OXY | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-017223298cafcba7 | RISK_FACTORS | JPM | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-020134297b2edd4b | RISK_FACTORS | GS | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-02c976cdaea2cca2 | EX99_PRESS_RELEASE | COP | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-060bb35a20101e04 | RISK_FACTORS | GS | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-081921fe16eebd72 | EX99_PRESS_RELEASE | BAC | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-08799bc7a67be233 | RISK_FACTORS | AAPL | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-0aa00121664ec198 | MDA | MRK | 10-Q | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-1595d4aad51bb169 | RISK_FACTORS | OXY | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-16d66f458883db87 | MDA | OXY | 10-Q | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-1810787882124c01 | EX99_PRESS_RELEASE | OXY | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-1b3bd0967f01aef3 | EX99_PRESS_RELEASE | BAC | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-1c247a14bc2efbd7 | RISK_FACTORS | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-1cd9f671d9b9a996 | 8K_BODY | CVX | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-1ef2d821873ab79c | EX99_PRESS_RELEASE | COP | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-20ff4cbbb46bfdef | RISK_FACTORS | JPM | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-2466959db0727c06 | RISK_FACTORS | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-2513742ac714c250 | MDA | JPM | 10-Q | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-25405f4c6adb83fc | RISK_FACTORS | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-260ff9f71cde6085 | EX99_PRESS_RELEASE | COP | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-26a8b292ada5a7cb | MDA | OXY | 10-Q | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-277d13a1a638dd8e | RISK_FACTORS | V | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-2a15272aa49b660f | RISK_FACTORS | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-2a4e45fa084522cc | RISK_FACTORS | V | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-2c1f39167b159575 | MDA | GS | 10-Q | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-2f6149132ba17914 | EX99_PRESS_RELEASE | OXY | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-33c05fca1ec9001f | EX99_PRESS_RELEASE | OXY | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-34cc4c61353afc2e | RISK_FACTORS | GS | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-35e65d1df1712d8c | RISK_FACTORS | OXY | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-369139100c47ab26 | EX99_PRESS_RELEASE | CVX | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-36fd4c50691dae2c | RISK_FACTORS | JPM | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-37071b0d23fc00d8 | EX99_PRESS_RELEASE | COP | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-3a402e3474536825 | RISK_FACTORS | OXY | 10-Q | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-3a80c5cce8740b57 | EX99_PRESS_RELEASE | OXY | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-3cceda41247c7e73 | RISK_FACTORS | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-3e2616c8ebae2bb3 | MDA | COP | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-3ff379d9e2a7a646 | RISK_FACTORS | PG | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-4071496a1e144dd2 | EX99_PRESS_RELEASE | CVX | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-43c89a19acfb050e | RISK_FACTORS | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-45ffba5774812498 | RISK_FACTORS | GS | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-48ec091598b2925f | EX99_PRESS_RELEASE | CVX | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-4c3bc718fcfa6db8 | MDA | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-4c89133feeb64a8d | MDA | OXY | 10-Q | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-4d803d67a1a92945 | RISK_FACTORS | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-4f661965fb1e06c9 | MDA | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-508cf9c48703c70b | EX99_PRESS_RELEASE | BAC | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-56d4c158b30b00f2 | RISK_FACTORS | OXY | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-588b3890c88371a5 | RISK_FACTORS | CVX | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-592a524fbc7249dd | RISK_FACTORS | NVDA | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-5a303aa31119b72b | MDA | MA | 10-Q | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-5d312cc4245254cb | 8K_BODY | CVX | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-5f365e62c4a7950c | EX99_PRESS_RELEASE | OXY | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-5f64ddabd40cf75f | MDA | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-5f7e5bdcee022972 | RISK_FACTORS | UNH | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-5fbf95ab7cef5637 | RISK_FACTORS | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-614b5db3c8bfdf5c | EX99_PRESS_RELEASE | CVX | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-61a3aedc5e017159 | RISK_FACTORS | JPM | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-6296a8fd3e0d66b0 | MDA | GS | 10-Q | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-62a07ef9095371ba | RISK_FACTORS | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-633adcb87ea3de35 | EX99_PRESS_RELEASE | CVX | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-63a7cf3758c4a439 | MDA | OXY | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-673bcdde24691f7f | RISK_FACTORS | MA | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-67c694902980a4ad | MDA | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-680ac502fa82dcf7 | RISK_FACTORS | PG | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-6b65cd171cc4e7fb | EX99_PRESS_RELEASE | CVX | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-6b834f5689fe50cb | MDA | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-6fd41b8a9a0a068c | MDA | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-70dca87fa269e140 | RISK_FACTORS | GS | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-712e160926dd0f0f | EX99_PRESS_RELEASE | CVX | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-71ae72a62a6050c2 | RISK_FACTORS | GS | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-72b5eb35cf3bc9e9 | MDA | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-7427bd666a2d164d | RISK_FACTORS | GS | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-797963e890d61222 | EX99_PRESS_RELEASE | BAC | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-79ed6dfdf32fb6a0 | EX99_PRESS_RELEASE | BAC | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-7e1ec04d5a87c813 | RISK_FACTORS | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-808a6628c2a2a073 | RISK_FACTORS | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-80ca7b8667eae9dc | EX99_PRESS_RELEASE | COP | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-85b0d00e0a4be2a2 | EX99_PRESS_RELEASE | BAC | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-87d7f6be8a95c376 | RISK_FACTORS | GS | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-8ae1b96bc6174d32 | MDA | GS | 10-Q | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-8d77e3d537575946 | RISK_FACTORS | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-9244fa69e814c4d9 | RISK_FACTORS | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-94d805b8d6236902 | RISK_FACTORS | GS | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-9562c03212c8cf65 | MDA | JPM | 10-Q | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-95a7cf23f319ee70 | RISK_FACTORS | NVDA | 10-K | ACCOUNTING_RESTATEMENT/HYPOTHETICAL |
| CHK-9793730b210715ea | EX99_PRESS_RELEASE | CVX | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-9d1e0d800fc185ad | RISK_FACTORS | CVX | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-9ecbb75bcc8121dd | MDA | KO | 10-Q | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-a0340f0c3259d6f6 | MDA | JPM | 10-Q | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-a1945d517306b903 | EX99_PRESS_RELEASE | BAC | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-a3195b49ea58cda0 | EX99_PRESS_RELEASE | OXY | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-a4c251cece612b75 | MDA | COP | 10-Q | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-a577c2ef70bba5da | RISK_FACTORS | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-a577d6f06c53b689 | RISK_FACTORS | UNH | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-a5ae56d1c5a0aee6 | RISK_FACTORS | GS | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-a787c4ef45504dd1 | EX99_PRESS_RELEASE | UNH | 8-K | **LIQUIDITY_STRESS/REALIZED** |
| CHK-ac1897ff391a803c | RISK_FACTORS | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-acdfc9342eb16a46 | RISK_FACTORS | GS | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-b0fc6a0be9c4bf27 | MDA | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-b39eeb19737dd1d0 | EX99_PRESS_RELEASE | OXY | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-b4544749a5786416 | EX99_PRESS_RELEASE | BAC | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-b4d83adf862a5660 | EX99_PRESS_RELEASE | CVX | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-b73feda5daaa6dfe | RISK_FACTORS | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-ba1ce66d503b5458 | RISK_FACTORS | V | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-bf0b41252e4ef0df | EX99_PRESS_RELEASE | COP | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-c17d2149a239bbcd | RISK_FACTORS | GS | 10-K | **LIQUIDITY_STRESS/REALIZED** |
| CHK-c660bd098ec54fa1 | RISK_FACTORS | ABBV | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-c95a1d9399ea5a0a | MDA | JPM | 10-K | **LIQUIDITY_STRESS/REALIZED** |
| CHK-c9e269daefe59113 | RISK_FACTORS | GS | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-caba5b31603dddd8 | MDA | OXY | 10-Q | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-cb87c70eb0767692 | MDA | MA | 10-Q | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-cc51004db8216604 | RISK_FACTORS | GS | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-ce2710d1b304bea6 | RISK_FACTORS | GS | 10-K | **LIQUIDITY_STRESS/REALIZED** |
| CHK-cf10074322ae7f8e | RISK_FACTORS | HD | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-cf90587fe93bb404 | EX99_PRESS_RELEASE | BAC | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-d32e016bdbe8baa1 | EX99_PRESS_RELEASE | COP | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-d74facbd628dfc96 | RISK_FACTORS | BAC | 10-K | ACCOUNTING_RESTATEMENT/HYPOTHETICAL |
| CHK-d995c3c66ab97bb5 | RISK_FACTORS | JPM | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-d9f9c2729c76438b | MDA | PG | 10-Q | **LIQUIDITY_STRESS/REALIZED** |
| CHK-dbbb4d5a2318899a | MDA | JPM | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-dc0f344324146c32 | RISK_FACTORS | V | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-dfc4e1148876ddab | RISK_FACTORS | GS | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-e25f70aef007092f | EX99_PRESS_RELEASE | COP | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-e48ff27b818f8f9d | MDA | OXY | 10-Q | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-e6250cd26ed8326f | MDA | OXY | 10-Q | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-e67ce6bc9d4d69d9 | EX99_PRESS_RELEASE | COP | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-e6946ca060d0a8ff | EX99_PRESS_RELEASE | BAC | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-e7538505b191c9fd | RISK_FACTORS | JPM | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-e8b48954fc07604a | EX99_PRESS_RELEASE | OXY | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-eacf8153709cee7f | RISK_FACTORS | CVX | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-ed1212d8058db87d | MDA | JPM | 10-Q | **LIQUIDITY_STRESS/REALIZED** |
| CHK-edee526ead997236 | RISK_FACTORS | JPM | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-f0f41dd27c073ee3 | RISK_FACTORS | JPM | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-f182137ef57e6857 | RISK_FACTORS | GS | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-f48d551bd3a90b44 | EX99_PRESS_RELEASE | OXY | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-f4cc8f311b031de8 | RISK_FACTORS | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-fa4e8fc7905256b1 | RISK_FACTORS | GS | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-fb6b826d4587a845 | RISK_FACTORS | OXY | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-fb7618957d807c18 | EX99_PRESS_RELEASE | OXY | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-fb98288f464dde30 | RISK_FACTORS | BAC | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-fbd6b76434f59dc9 | RISK_FACTORS | OXY | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-fe8029229aaac684 | EX99_PRESS_RELEASE | CVX | 8-K | LIQUIDITY_STRESS/HYPOTHETICAL |
| CHK-fe9199c12d714cd8 | RISK_FACTORS | OXY | 10-K | LIQUIDITY_STRESS/HYPOTHETICAL |

**6 REALIZED instances total** (bolded above): `CHK-a787c4ef45504dd1` (UNH), `CHK-c17d2149a239bbcd` (GS), `CHK-c95a1d9399ea5a0a` (JPM), `CHK-ce2710d1b304bea6` (GS), `CHK-d9f9c2729c76438b` (PG), `CHK-ed1212d8058db87d` (JPM) — these 6, plus the 2 ACCOUNTING_RESTATEMENT hits, are the highest-priority items for the owner's exhaustive distress-tier review, ahead of the 135 HYPOTHETICAL LIQUIDITY_STRESS cases which read as standard sector boilerplate.

---

## 4. Spot-check guidance for the 400-example tiered review (per ROADMAP's design)

Suggested strata, now that the corpus is (effectively) complete:

1. **Proportional random sample across section_types** — the base tier. With final counts MDA≈3,962, RISK_FACTORS≈1,606, EX99_PRESS_RELEASE≈1,171, 8K_BODY≈8, a proportional sample naturally undersamples 8K_BODY (n=8 total in the whole corpus) — worth manually including all 8 of those regardless of the proportional formula, since it's small enough to review exhaustively for free.
2. **Targeted oversampling of thin/rare categories** — SUPPLY_INPUT_CONSTRAINT (580 instances, the rarest red flag) and WITHDRAWN guidance (exactly 1 instance corpus-wide) are the thinnest categories; the single WITHDRAWN example should be checked by hand regardless of any sampling formula, same logic as 8K_BODY.
3. **Every distress-tier positive, exhaustively** — all 143 rows in §3 above, with the 6 REALIZED + 2 ACCOUNTING_RESTATEMENT rows reviewed first as the highest-signal/highest-risk-of-being-wrong subset.
4. **Chunks flagged from the canary cross-variant disagreement, specifically `CHK-6cfb7bb16c8ef2fc`** (KO, MDA) — in the original 50-chunk canary, the `disabled` and `adaptive-low` variants disagreed on both sentiment (NEGATIVE vs. NEUTRAL) and red flags (MARGIN_COST_PRESSURE vs. none) for this same chunk. Its final label (from the `disabled-4000` corrective pass, since it was one of the truncated chunks) is `sentiment=NEUTRAL`, `red_flags=[{MARGIN_COST_PRESSURE, REALIZED}]`, `guidance=None`, `distress_tier=[]` — worth a direct human read given it was already flagged as borderline across two separate model configurations.
5. **The one residual `refusal` failure**, `CHK-8e69547e0900a8dd` (MDA, `stop_reason=refusal`, `stop_details.category=bio`, 293 output tokens of partial JSON emitted before the stop: `{"red_flags": [{"category": "IMPAIRMENT_WRITEDOWN","modality": "REALI...`) — the resulting unterminated JSON resembles a token truncation but is not one. A re-run would refuse again, so the correct handling is to exclude it from the training set and document it here, not resubmit it.
6. **A handful of the EX99_PRESS_RELEASE POSITIVE-sentiment and RAISED-guidance rows** — both categories run meaningfully more optimistic than their MDA/general-corpus counterparts, plausible given press releases are self-selected good-news framing, but worth 2–3 spot-checks to rule out systematic over-reading of "record revenue"-style framing as POSITIVE where a stricter human read might call it NEUTRAL.

---

## 5. Canary-methodology lesson (carried forward for future runs)

> **SUPERSEDED (2026-08-10) — the original text below is preserved for audit but is WRONG. See the correction that follows it.**

**The core lesson from this whole sequence: a small, section_type-stratified canary validates correctness (does the JSON parse, does it match the schema) but does not validate tail behavior at scale (does the output fit in the token budget across the full range of chunk lengths and flag-density).** The 50-request canary for the `disabled` variant hit 100% clean — genuinely accurate for what it tested — but at 6,747 requests, the same config truncated 37.6% of the corpus because the canary's proportional-by-section_type sampling didn't happen to include enough of the longer/multi-flag-heavy chunks that actually stress `max_tokens`.

**Concrete recommendation for future canaries in this project (and worth carrying into `quant-modeler`'s or any future labeling work):** stratify canary sampling by **word_count** and/or an **expected-output-complexity proxy** (e.g., a cheap pre-pass estimate of how many red-flag/distress-tier categories a chunk is likely to trigger, or simply the top-decile-by-length chunks deliberately oversampled), not by `section_type` alone. A canary that includes the corpus's long tail — even just the top 5-10% by word_count — would very likely have surfaced the `max_tokens=800` risk before the full run, at a canary cost of maybe a few cents more. This is a real, cheap process fix worth encoding into any reusable canary tooling for future rounds (weak-supervision passes, a second bootstrap pass on any category the eventual owner spot-check flags as weak, etc.).

---

**CORRECTION (2026-08-10) — the real lesson:** the canary's stratification was never the problem. The 50-request `disabled`-variant canary at `max_tokens=800` was accurate for what it tested — but it never ran on the code path that actually submitted the full run. `run_full()` in `submit_labeling_batch.py` ignores `args.variant` and always loads the default `data/batch_requests.jsonl`, so the full run silently used `max_tokens=500`/adaptive-thinking, a config that was never the one canaried at 800. The 37.6% truncation rate is fully explained by that: it's almost exactly what the *original* 500-token canary (pre-`disabled`-variant, run earlier in the session) had already measured a ~36% failure rate for. **Stratifying canary sampling by word_count/complexity would not have caught this bug and is not the fix — the canary already correctly predicted the failure rate for the config that actually ran.** The real, correct lesson is: **verify that the artifact submitted by the full-run code path is byte-identical to (or at minimum config-identical to) the artifact the canary validated.** A canary is worthless if the code that submits the full run doesn't load the same file the canary tested against. Concretely: before any future full run, diff/hash the request file the submission code will actually load against the file path named in the invoked flag, and fail loudly if they don't match — that's a cheap, mechanical check that would have caught this specific bug immediately, unlike a stratification change which addresses a problem that didn't occur.

---

## 6. Handoff note

`data/labels.parquet` (6,747 rows, 6,746 usable, provenance columns `batch_id`/`max_tokens_used`/`labeled_at`) is now the corpus's labeled state pending the owner's 400-example spot-check per §4 — **but see the CORRECTION section near the top of this document: the `max_tokens_used=800` provenance value for the 4,219 original-run rows is false (actual config was 500/adaptive), the corpus currently has mixed provenance, and an approved re-label of those 4,219 rows to the disabled/4000 config is PENDING and has not yet been submitted.** The 400-example spot-check package should NOT begin review until that re-label lands and the sample is regenerated (see `spotcheck/README.md`'s hold banner). The one remaining gap (`CHK-8e69547e0900a8dd`) and the corrected canary-methodology lesson in §5 should both travel with this dataset into any downstream fine-tuning or `quant-modeler` handoff documentation.

---

# FINAL CONSOLIDATED STATE (2026-08-11)

Supersedes all earlier sections where they conflict.

## Corpus

| Metric | Value |
|---|---|
| Rows | 6,747 |
| Successfully labeled | 6,746 (99.99%) |
| Unlabeled | 1 — `CHK-8e69547e0900a8dd` (MDA), genuine `stop_reason=refusal`, `stop_details.category=bio`, 293 partial output tokens. Confirmed from the API record; re-running would refuse again. Excluded from train/eval by predicate. |
| Labeling config | `thinking=disabled, max_tokens=4000` — **uniform across all 6,747 rows** |
| Truncations | 0 (all responses `end_turn`) |
| Provenance columns | Populated from real API result records (`batch_id`, `stop_reason`, `output_tokens`), not intended values |
| Prior labels | Preserved at `data/labels_pre_relabel.parquet` |

Final distributions: sentiment NEUTRAL 3,436 / POSITIVE 1,024 / NEGATIVE 680 (1,607 n/a = 1,606 RISK_FACTORS never asked + 1 refusal chunk);
guidance non-NONE 83; distress-tier positives 162.

## Spend (actual, from API usage records)

| Run | Cost (intro) |
|---|---|
| Canary 1 (50) | $0.27 |
| Dual canary (100) | $0.64 |
| Full run (6,747) — wrong config, 62.5% usable | $18.05 |
| Corrective (2,528) | $4.49 |
| Re-label (4,219) | $10.06 |
| **Total** | **$33.51 of $50** ($16.49 remaining) |

Roughly $6–7 of the full run was wasted on truncated output caused by the config-delivery bug.

## HEADLINE LIMITATION — red-flag labels are ~22% config-sensitive

Comparing the two labeling passes over the same 4,219 chunks:

| Field | Applicable | Changed | % |
|---|---|---|---|
| sentiment | 3,280 | 119 | 3.6% |
| guidance_direction | 677 | 6 | 0.9% |
| red_flags | 4,219 | 935 | **22.2%** |
| distress_tier | 4,219 | 29 | 0.7% |

The shift is **systematic, not noise**: the thinking-disabled config emitted more red flags in
every category (LEGAL_REGULATORY_ACTION +211, MARGIN_COST_PRESSURE +203, DEMAND_WEAKNESS +138,
IMPAIRMENT_WRITEDOWN +51, SUPPLY_INPUT_CONSTRAINT +35, TRADE_POLICY_EXPOSURE +27). Distress
positives on those rows rose 38 → 57.

This must be carried into the model card as a first-class limitation: **any downstream
red-flag-derived feature inherits ~22% labeling uncertainty**, and the sign of the bias is known
(the retained config flags more liberally). Sentiment and guidance are comparatively stable.

Note also that the 50-chunk dual canary measured 92–100% agreement between configs and therefore
**materially understated** this sensitivity — a reminder that small canaries measure correctness,
not distributional stability.

The owner's 400-example spot-check now includes **Tier D (60 chunks)** drawn from the 935
disagreement cases, judged blind, specifically to adjudicate which config was more accurate.

## Postmortem — root cause of the wasted run

`run_full()` hardcoded `data/batch_requests.jsonl` and ignored `--variant`, so the canaried
`disabled`/800 config was never delivered; the run executed at `max_tokens=500` with adaptive
thinking on. Proven three ways: the code path, the file's contents, and the API's own usage
records (ceiling exactly 500). The canary was accurate — it predicted 36% failure at that config
and the run produced 37.6%. **The real lesson is to verify that the submitted artifact is the
tested artifact**, not to change canary sampling.

Fixes landed: `run_full()` now requires an explicit variant (no default); a pre-submission guard
rejects any file/variant mismatch (verified to reject the exact pairing that caused the incident);
and `--verify-config` reads a completed batch's real stop reasons back from the API. That verifier's
first heuristic was itself wrong (it flagged every healthy run) and was rewritten to key on
truncation rate — regression-tested against both the real incident (flags) and the healthy
re-label (passes).

---

## 2026-08-18 — CURRENT PER-CATEGORY COUNTS (appended; supersedes §3's tables)

Added 2026-08-18 because the FINAL CONSOLIDATED STATE section above never
restated §3's red-flag figures, leaving them with no current replacement
anywhere in the repo — while `RED_FLAGS_LIMITATION.md` implication 3
directs Week 5 to normalize red-flag features "using recomputed
post-relabel counts." These are those counts.

**Source:** recomputed 2026-08-18 directly from `data/labels.parquet`
(6,746 usable rows: `parse_ok & schema_valid`). Basis: **flag instances**,
the same basis §3's table uses. The "doc says" column is §3's pre-relabel
figures, confirmed to match `data/labels_pre_relabel.parquet` exactly.

| Red-flag category | §3 (pre-relabel) | **Current (`labels.parquet`)** |
|---|---|---|
| LEGAL_REGULATORY_ACTION | 2,079 | **2,305** |
| MARGIN_COST_PRESSURE | 1,534 | **1,737** |
| DEMAND_WEAKNESS | 1,186 | **1,326** |
| IMPAIRMENT_WRITEDOWN | 966 | **1,019** |
| TRADE_POLICY_EXPOSURE | 683 | **713** |
| SUPPLY_INPUT_CONSTRAINT | 580 | **616** |

| Metric | §3 (pre-relabel) | **Current** |
|---|---|---|
| Modality split | 3,068 HYPOTHETICAL / 3,960 REALIZED | **3,512 HYPOTHETICAL / 4,204 REALIZED** |
| Rows with ≥1 red flag | 4,008 / 6,746 = 59.4% | **4,416 / 6,746 = 65.5%** |

**Basis note (this trips people up):** the six config-sensitivity deltas
quoted throughout the docs (LEGAL +211, MARGIN +203, DEMAND +138,
IMPAIRMENT +51, SUPPLY +35, TRADE +27) are measured on a **per-chunk
category-presence** basis over the 4,219 re-labeled chunks. Counted as flag
*instances* — the basis of the tables above — the same six deltas are
+226 / +203 / +140 / +53 / +36 / +30. Both are correct; they are not the
same measurement, so do not mix them in one sentence.

**Not superseded here:** these are counts over the frozen `labels.parquet`.
The spot-check separately found those stored red-flag sets to be wrong on
36.6% of the 400-chunk sample (sample-pooled; 25.0% on the
base-rate-representative Tier C slice) — see `RED_FLAGS_LIMITATION.md`
before using any of these counts as ground truth.
