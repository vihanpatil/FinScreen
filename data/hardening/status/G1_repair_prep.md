# G1 repair — rubric v1.2 re-label, PREPARATION COMPLETE

**Written 2026-08-26 by the finetune-engineer. PREPARATION ONLY.**
**Zero API calls were made. Nothing was submitted. Nothing was spent.**

Authorization boundary: `HANDOFF.md` §3, 2026-08-26 entry ("F2.5 closure
rulings", ruling 1). The §5 spend freeze is lifted for exactly ONE
purpose — a single Batch API re-label of E1's 6,747 chunks under rubric
v1.2 — hard-capped at $25 estimated. Submission and all post-batch
processing run in the MAIN SESSION only (§4/§7).

---

## 0. Headline for the main session

| Item | Value |
|---|---|
| Rubric | **v1.2, applied and synced** (`labeling_rubric.md` + `SYSTEM_PROMPT`) |
| Categories changed | **red_flags (all 6) + modality**. sentiment, guidance_direction, distress-tier definitions unchanged — proven byte-identical to v1.1. |
| Model id recovered | **`claude-sonnet-5`** |
| Config recovered | **`max_tokens=4000`, `thinking={"type":"disabled"}`, no `effort`** |
| Request file | `data/batch_requests_v12.jsonl`, **6,747 requests**, sha256 `312f585d64c2409e44ae2ef595d85f15ef4dd6434789764878ec389fac276027` |
| Guards | variant guard PASS, new rubric/model guard PASS, count PASS, coverage PASS, single-axis PASS |
| Cost estimate | **$11.95–$19.30 at intro pricing; $17.92–$28.96 at standard pricing** |
| **Cap verdict** | ⚠️ **THE CONSERVATIVE ESTIMATE EXCEEDS $25 — see §4. Do NOT submit on this prep alone.** |
| Tests | 60 passed (`test_rubric_v12_sync.py` 29 new, `test_submit_variant_wiring.py` 25, `finetune/test_prepare_dataset.py` 6) |

---

## 1. Rubric v1.2 — what changed, and in which categories

Source: `RED_FLAGS_LIMITATION.md`'s "Proposed rubric revision", built on
the owner-ratified P1/P2/P3 principles (2026-08-18). Exactly the three
proposed items were applied — no more, no less.

### Changed

**`red_flags` — §4, all six categories.** New *mining-depth* rule (P3):
in an enumerated risk-factor list, a clause earns a flag only if it
asserts the risk specifically enough to stand alone as a sentence about
this company; single-word category mentions inside a boilerplate
enumeration do not qualify. The "What does not count" paragraph was
rewritten to point at this rule instead of the old "still label it if it
fits a category" wording, while preserving the original intent
(boilerplate that *does* clear the bar is still flagged, with
`HYPOTHETICAL` modality doing the separating work).

**`red_flags` — §4, `MARGIN_COST_PRESSURE` specifically.** The
disambiguation note's causeless-cost-inflation clause was strengthened
from "label only `MARGIN_COST_PRESSURE`" to "**always** and only
`MARGIN_COST_PRESSURE`", explicitly including inside enumerations that
clear the mining-depth rule (P3 corollary). This is the single largest
error mode in the record: 20 spurious + 23 missed corrections.

**Modality — §6 (shared by `red_flags` AND `distress_tier`).** New
*realized-controls* rule (P1): a statement that an event exists or has
occurred — pending litigation, completed audits with consequences,
regulation already in effect — is `REALIZED` even inside a
forward-looking or safe-harbor sentence; only its projected consequences
are `HYPOTHETICAL`. Four worked examples added. This addresses 43
wrong-modality corrections, 26 of them `LEGAL_REGULATORY_ACTION`.

**Because §6's modality vocabulary is shared, this change reaches
`distress_tier` modality as well as `red_flags` modality.** Stated
plainly rather than glossed. `distress_tier` remains excluded from
training targets and headline metrics either way (`HANDOFF.md` §7).

### Not changed

- **§2 sentiment** — unchanged. Pinned byte-identical to the v1.1 prompt
  E1 actually shipped (`test_categories_v12_did_not_touch_are_byte_identical_to_v11`).
- **§3 guidance direction** — unchanged, same byte-identity pin.
- **§5 distress-tier category definitions** — unchanged, same pin.
- **§1 applicability matrix, §7 output schema, §8 look-ahead
  constraints** — unchanged. The six red-flag category names and the JSON
  schema enums are pinned unchanged too: v1.2 changes how categories are
  *applied*, never the taxonomy.

### Deliberately NOT encoded: principle P2

P2 (liquidity-stress threshold — affirmed adequacy defeats the flag)
governs `distress_tier`. `RED_FLAGS_LIMITATION.md`'s proposed revision
explicitly routes P2 to the distress-tier addendum and proposes **no §5
rubric edit** for it, and the owner's ratification names that proposal.
Encoding it would have been scope creep past the authorization, on a
field that is neither a training target nor a headline metric. It is
called out in `labeling_rubric.md` §9 as an open item needing its own
owner ruling if wanted.

### Sync rule honored (HANDOFF §3, 2026-08-10)

`SYSTEM_PROMPT` in `build_batch_requests.py` received three matching
hand-synced edits, checked side by side against the rubric — a leaner
restatement, not a verbatim embed:

| Rubric | `SYSTEM_PROMPT` |
|---|---|
| §4 mining-depth rule | `MINING DEPTH:` sentence after the six red-flag bullets |
| §4 disambiguation-note emphasis | `MARGIN_COST_PRESSURE:` bullet, "ALWAYS this category, and only this category" |
| §6 realized-controls rule | `REALIZED CONTROLS:` sentence in the `MODALITY` paragraph |

Prompt grew 7,748 → 9,521 chars (+22.4% in tokens). Still clears the
1,024-token prompt-cache minimum. §0's look-ahead prohibition survives
verbatim in substance; no `section_type` string appears anywhere in the
prompt (rubric §8.2, ratified 2026-08-10) — both pinned by tests.

Revision-log entry added at `labeling_rubric.md` §9, dated, naming the
ratification (HANDOFF §3, 2026-08-26). `RED_FLAGS_LIMITATION.md` carries
a dated amendment marking the proposal RATIFIED AND APPLIED and
superseding its "no re-label occurs regardless" paragraph.

---

## 2. Single-axis discipline — model id and config recovered

Recovered from the batch metadata E1 actually wrote at submission time,
cross-checked against the request files on disk and against
`data/labels.parquet`'s own provenance columns.

| Source | Evidence |
|---|---|
| `data/relabel_batch_meta.json` | `model: claude-sonnet-5`, `variant: disabled-4000`, `asserted_max_tokens: 4000`, `asserted_thinking: disabled`, 4,219 submitted, batch `msgbatch_01KrfTWXeVN79Us9wthnGLaG` |
| `data/corrective_batch_meta.json` | `model: claude-sonnet-5`, `variant: disabled-4000`, 2,528 submitted, batch `msgbatch_01Mw3sFCi3fZXnV5U86PJR1o` |
| `data/batch_requests_relabel.jsonl` (request bodies) | `model: claude-sonnet-5`, `max_tokens: 4000`, `thinking: {"type":"disabled"}`, no `output_config.effort` |
| `data/labels.parquet` | all 6,747 rows: `labeling_config = thinking=disabled,max_tokens=4000`, `max_tokens_used = 4000`; `batch_id` = 4,219 relabel + 2,528 corrective; `stop_reason` = 6,746 `end_turn` + 1 `refusal` |

**Recovered config, used verbatim for v1.2:**
`model="claude-sonnet-5"`, `max_tokens=4000`,
`thinking={"type":"disabled"}`, no `effort`,
`system[0].cache_control={"type":"ephemeral","ttl":"1h"}`.

The new `v12_relabel` variant is byte-for-byte the same as
`disabled-4000` except for its output path — pinned by
`test_v12_variant_config_is_identical_to_e1s_final_variant`.

**Machine-verified across all 4,219 chunks shared with E1's final pass**
(`build_v12_requests.py::verify_single_axis`): model, `max_tokens`,
`thinking`, `output_config.format` schema, and the passage text are all
IDENTICAL; the system prompt is asserted to DIFFER (a no-op edit would
mean re-buying E1's labels). System-prompt sha256
`d717d76e…` (v1.1) → `30605197…` (v1.2).

### Servability — read this before submitting

`claude-sonnet-5` **is present in the installed SDK's `Model` literal**
(`anthropic` 0.121.0), which is offline evidence that it is a known,
current alias. That is **not proof of servability** — only a live call
can establish that, and I make none.

**Residual that the ratification's wording does not close:**
`claude-sonnet-5` is an **alias, not a dated snapshot**. E1's metadata
records only the alias. If the alias has been repointed since
2026-08-11, "same model id" would not mean "same model", and a second
axis would be moving silently alongside the rubric. This is not
resolvable from local artifacts.

Mitigation, free and read-only, added to the existing verifier:
`--verify-config` now also reports the **resolved** model id from a
batch's results (`report["resolved_model_ids"]`). Batch results are
retained ~29 days and E1's final batch is 15 days old, so it is still
recoverable:

```
python3 submit_labeling_batch.py --verify-config msgbatch_01KrfTWXeVN79Us9wthnGLaG --variant disabled-4000
```

Run the same command against the v1.2 batch afterward and compare. If
the resolved ids differ, say so in the G1 read — the comparison is then
rubric-plus-model, not rubric-only. **This is optional and does not
block submission; it costs nothing.**

---

## 3. The v1.2 request file and its guards

Built by `data/hardening/build_v12_requests.py` (re-runnable, zero API
calls). Provenance manifest: `data/hardening/v12_request_manifest.json`.

- `data/batch_requests_v12.jsonl` — **6,747 requests**, 93,079,725 bytes,
  sha256 `312f585d64c2409e44ae2ef595d85f15ef4dd6434789764878ec389fac276027`
- Corpus sha256 `5067494c870f82e5…`, rubric sha256 `46dea3c886846849…`,
  builder sha256 `ca60479b38561b80…`, system-prompt sha256
  `30605197ca56c23138de34743d780c19fd62e31c80b1eb5b58115fbde8ae5924`

Every guard runs against the file **re-read from disk**, never the
in-memory list that produced it (HANDOFF §7).

| Guard | Result |
|---|---|
| `assert_requests_match_variant(..., "v12_relabel")` | PASS — all 6,747 at `max_tokens=4000 / thinking=disabled / effort=None` |
| `assert_requests_use_current_system_prompt` (**new**) | PASS — all 6,747 carry rubric v1.2 and `model="claude-sonnet-5"` |
| Request count | PASS — 6,747 == corpus 6,747 |
| Chunk coverage | PASS — exact set equality with the corpus, 0 duplicate `custom_id`s |
| Refusal chunk | PASS — `CHK-8e69547e0900a8dd` is **included and will be submitted** |
| Schema shape | PASS — matches `section_type` for all 6,747 (MDA 3,962 / RISK_FACTORS 1,606 / EX99_PRESS_RELEASE 1,171 / 8K_BODY 8) |
| Prompt exactness | PASS — user turn is the raw passage verbatim and nothing else; system prompt byte-identical across every request |
| Look-ahead safety | PASS — no `section_type` string in the prompt; params carry no ticker/CIK/accession/form/filing-date |
| Single-axis vs E1 | PASS — see §2 |

### The new guard, and why it exists

`assert_requests_match_variant` inspects `max_tokens`/`thinking`/`effort`
and **nothing else** — correctly, because that was the axis of the
2026-08-11 incident. But the v1.2 re-label moves a *different* axis. A
stale v1.1 request file has an **identical** config, so it sails through
the variant guard, costs the full run, and returns E1's labels again.

`assert_requests_use_current_system_prompt()` (new, in
`submit_labeling_batch.py`) closes that: every request body's system
prompt must sha256-match the current `SYSTEM_PROMPT`, and every request's
model must match `MODEL`. It runs inside `run_full()` for any variant in
`RUBRIC_PINNED_VARIANTS` (`{"v12_relabel"}`), and prints an explicit
"NOT APPLICABLE" line for legacy variants — never a silent skip.
`test_rubric_guard_rejects_the_v11_request_file` demonstrates the exact
failure: E1's real file passes the variant guard and is caught here.

### The refusal chunk, handled as E1 did

E1 submitted all 6,747 including `CHK-8e69547e0900a8dd`, got
`stop_reason=refusal` / `parse_ok=False` back, and **excluded it by
predicate — never deleted the row**. Same here: it is in the request
file. Pre-filtering it would assume the v1.2 outcome instead of measuring
it. `run_poll` now records `stop_reason` per row and prints a loud
SAFETY REFUSALS block naming any chunk that refuses.

### Sample (eyeball verification)

```
--- custom_id=CHK-000e4d64449624b3  (section_type=RISK_FACTORS, not in the request) ---
model           : claude-sonnet-5
max_tokens      : 4000
thinking        : {'type': 'disabled'}
output_config   : effort=None schema.required=['red_flags', 'distress_tier']
system[0].cache : {'type': 'ephemeral', 'ttl': '1h'}
system[0].text  : 9521 chars, sha256=30605197ca56c231...
user content    : 3606 chars
  first 220     : 'We have entered and may in the future enter into commercial arrangements, ...'

--- custom_id=CHK-00127fcf9c6ce339  (section_type=MDA) ---
output_config   : effort=None schema.required=['red_flags', 'distress_tier', 'sentiment']

--- custom_id=CHK-0034343a36e11097  (section_type=EX99_PRESS_RELEASE) ---
output_config   : effort=None schema.required=['red_flags', 'distress_tier', 'sentiment', 'guidance_direction']

--- custom_id=CHK-111f131795b0afcf  (section_type=8K_BODY) ---
output_config   : effort=None schema.required=['red_flags', 'distress_tier', 'sentiment', 'guidance_direction']
```

Schema shape tracks `section_type` exactly per the applicability matrix,
and `section_type` never appears in the prompt. Re-run
`python3 data/hardening/build_v12_requests.py` to reprint, including the
three changed v1.2 passages in full.

---

## 4. ⚠️ COST — THE CONSERVATIVE ESTIMATE EXCEEDS THE $25 CAP

**Read this before submitting. Per HANDOFF §3 (2026-08-26): if the
pre-submission estimate exceeds $25, STOP and re-confirm with the owner.**

### Method

Not a token-proxy guess. Anchored on E1's **real billed usage** under
this exact model and config. `data/full_run_report.md` publishes the
corrective run's full token breakdown (2,296,084 input / 265,014 output /
13,383 cache-write / 8,430,488 cache-read over 2,528 requests), and those
four numbers reproduce its reported **$4.491 exactly** through
`compute_real_cost` — asserted in code, so the formula and the pricing
constants are validated against a real bill before anything is projected.

From them: Claude's real per-request system-prompt cost is **~3,340
tokens** for v1.1 (cache-write and cache-read tokens independently agree
on that figure), and the tokenizer ratio for request bodies is 1.0822×
the local cl100k proxy.

### The fitted model was cross-validated — and FAILED

Predicted against E1's *other* run at the same config (4,219 requests,
reported $10.06): **$6.28, a 37.5% under-prediction.**

Root cause is **not** tokenization — the re-label's passages (799 proxy
tokens/request) and outputs (57 tokens/request) are both *smaller* than
the corrective run's (839 / 105). Solving the residual: **~599 of its
4,219 requests (14.2%) paid a 1h-TTL prompt-cache WRITE at 2× input
price**, versus **4 of 2,528 (0.16%)** in the corrective run.

**Batch API cache fan-out varied ~90× between two runs of this same
project at identical config.** It is the dominant cost uncertainty, it is
not under our control, and there is no engineering fix — the only lever
is a shorter system prompt, which the sync rule constrains. So the
estimate is a scenario table, not a point.

### Scenario table — 6,747 requests, v1.2 prompt, +25% output headroom

| Cache-write rate | intro ($2/$10) | standard ($3/$15) |
|---|---|---|
| 0.16% — best E1 observed | $11.95 | $17.92 |
| **14.2% — worst E1 observed** | **$19.30** | **$28.96** ⚠️ |
| 100% — cold-cache bound | $64.29 | $96.44 |

Cross-checks: E1's own per-request rate scaled to 6,747 gives $16.09
(re-label rate) / $11.99 (corrective rate) at intro.
`build_batch_requests.estimate_cost`'s independent proxy model gives
$10.16 intro / $15.25 standard "cached realistic".

### Verdict

**It exceeds $25 in exactly one corner: standard pricing × the worst
cache-write rate E1 actually observed → $28.96.** Under intro pricing it
does not breach at any observed cache rate (worst case $19.30).

**So the decision hinges on which Batch price tier is live, which I
cannot resolve offline.** `build_batch_requests.PRICING` records intro
($2/$10 per Mtok) as running "through 2026-08-31" and standard at $3/$15,
and the module's own comments flag both as unverified for Sonnet 5.

**Recommended sequence for the main session:**
1. Confirm current Sonnet-5 Batch pricing (free, read-only).
2. If **intro** is live: the estimate is $12–19, comfortably inside the
   cap. Proceed.
3. If **standard** is live: the conservative estimate is $28.96 and the
   central estimate $24.13 leaves only 3.5% headroom. **Stop and
   re-confirm with the owner** per the ratified hard-cap rule.

### Correction to the ratified $16.09

The owner's ratified estimate scaled the re-label run's $2.385/1k rate to
6,747 rows. That **understates**, for two reasons found here: (a) the
re-label subset averaged 57.0 output tokens/request while the full
6,747-chunk corpus measured **74.9** (+31%) — the expensive long chunks
were in the *other* batch; (b) it predates the v1.2 prompt, which is
22.4% longer. Both push the true number up. Worth stating plainly at the
re-confirm, whichever way the pricing question lands.

*(One respect in which the estimate is conservative: the system-prompt
uplift is applied to the whole measured 3,340-token cached block. If part
of that block is fixed API framing rather than prompt text, the real
uplift is smaller.)*

---

## 5. Exact commands for the main session

**All of the following run in the MAIN SESSION, synchronously, driven by
the owner's own chat message. No background watchers (HANDOFF §4/§7).**

### 5.1 Pre-flight (free, no submission)

```bash
python3 data/hardening/build_v12_requests.py          # re-verify all guards + cost
python3 -m pytest test_rubric_v12_sync.py test_submit_variant_wiring.py -q
# optional, free, read-only — recover E1's RESOLVED model snapshot:
python3 submit_labeling_batch.py --verify-config msgbatch_01KrfTWXeVN79Us9wthnGLaG --variant disabled-4000
```

### 5.2 THE SUBMISSION COMMAND

```bash
python3 submit_labeling_batch.py --full --confirm-full --variant v12_relabel
```

Gated three ways before any `batches.create()`: `--confirm-full` is
mandatory, the variant guard checks every request's real
config, and the rubric guard checks every request's system-prompt sha256
and model id. Writes **`data/v12_relabel_batch_meta.json`** — carrying
`batch_id`, `variant`, `rubric_version`, `system_prompt_sha256`,
`asserted_max_tokens`, `asserted_thinking`, `model`, `n_submitted`.

`main()` was fixed to route this variant's meta to its own path.
Previously `run_full`'s default was `data/full_batch_meta.json` — **E1's
frozen provenance record**, which this run would have silently
overwritten. Pinned by
`test_full_cli_routes_v12_away_from_e1s_frozen_meta`.

### 5.3 Polling and post-processing (synchronous, main session)

```bash
python3 submit_labeling_batch.py --poll <BATCH_ID> --variant v12_relabel \
    --out data/labels_v12.parquet --max-wait-s 1800
```

Re-run as needed — a Batch API run can take up to 24h, and `run_poll`
writes nothing until the batch has ended, so repeated invocations are
safe. Do **not** background it.

Then, free and read-only:

```bash
python3 submit_labeling_batch.py --verify-config <BATCH_ID> --variant v12_relabel
```

Checks the truncation rate against the 4,000 cap (>1% = SUSPECT) and
prints `resolved_model_ids` for the §2 alias comparison.

### 5.4 Where the labels land

**`data/labels_v12.parquet`** — a NEW file. E1's `data/labels.parquet`
is **never touched**; nor is `data/full_batch_meta.json`,
`data/labels_pre_relabel.parquet`, or any E1 request file
(`write_requests_jsonl` now refuses to clobber an existing request file).
The frozen-path set is pinned by
`test_v12_variant_writes_only_to_new_paths`.

`run_poll` now stamps per-row provenance into the artifact —
`batch_id`, `stop_reason`, `output_tokens`, `labeled_at`,
`max_tokens_used`, `labeling_config`, `rubric_version`,
`system_prompt_sha256` — so `labels_v12.parquet` is self-describing
straight out of the poll. E1's equivalent columns were added by an ad-hoc
merge after the fact.

### 5.5 Downstream chain (after the labels land)

1. **Sanity:** 6,747 rows; count `parse_ok == False` (the exclusion
   predicate); check the SAFETY REFUSALS block.
2. **The measurement itself:** compare `labels_v12.parquet` against
   `labels.parquet` chunk-by-chunk. Did red-flag modality shift toward
   `REALIZED` for `LEGAL_REGULATORY_ACTION` (P1)? Did boilerplate flags
   drop (P3)? Did causeless `MARGIN_COST_PRESSURE` become consistent?
   This is the evidence the G1 read needs, and it is *not* an accuracy
   measurement — it is agreement between two rubric revisions of the same
   teacher.
3. **Splits stay frozen.** **Do NOT run `finetune/split.py`** — its
   `LABELS_PATH` points at `data/labels.parquet` and it would *re-derive*
   membership. Instead rebuild `finetune/splits/{train,eval}.parquet` by
   joining `labels_v12.parquet` onto the **frozen**
   `finetune/splits/manifest.parquet` (6,746 rows: train 5,736 / eval
   1,010; the refusal chunk is not in it). Membership is
   label-value-independent, exactly as the ratification says.
4. **Edge cases to report, not paper over:** if the refusal chunk now
   labels successfully it still stays out of both splits (the frozen
   manifest excludes it). If *more* chunks fail under v1.2, those rows
   drop out of the prepared JSONL and the train count falls below 5,736 —
   report the delta explicitly.
5. `python3 finetune/prepare_dataset.py`, then retrain on the same recipe
   (epoch 1 → eval → epoch 2 → full re-eval), then **the owner rules G1
   on the repaired instrument**.

---

## 6. Files touched

| File | Change |
|---|---|
| `labeling_rubric.md` | v1.2: header, §4 ×2, §6 ×1, §9 revision-log entry |
| `build_batch_requests.py` | `SYSTEM_PROMPT` ×3 synced edits; `RUBRIC_VERSION`; `system_prompt_sha256()`; `v12_relabel` variant; `write_requests_jsonl(overwrite=)` clobber guard; `build_variant_files(only=)` |
| `submit_labeling_batch.py` | `VARIANT_PATHS["v12_relabel"]` + `full_meta`; `RUBRIC_PINNED_VARIANTS`; `assert_requests_use_current_system_prompt()`; `run_full` guard + provenance stamping; `main()` meta routing; `run_poll` provenance columns + refusal report; `--verify-config` resolved model ids; docstring |
| `RED_FLAGS_LIMITATION.md` | dated 2026-08-26 amendment: proposal RATIFIED AND APPLIED; supersedes its "no re-label" paragraph |
| `test_rubric_v12_sync.py` | **new**, 29 offline tests |
| `data/hardening/build_v12_requests.py` | **new**, prep + guards + cost, zero API calls |
| `data/hardening/v12_request_manifest.json` | **new**, provenance manifest |
| `data/batch_requests_v12.jsonl` | **new**, 6,747 requests (gitignored via `data/*.jsonl`) |

**Not touched:** `data/labels.parquet`, `data/labeling_corpus.parquet`,
`finetune/splits/*`, every E1 batch-meta and request file.

Test status: **60 passed** — `test_rubric_v12_sync.py` (29 new),
`test_submit_variant_wiring.py` (25, unchanged and still green),
`finetune/test_prepare_dataset.py` (6). All offline: no `anthropic`
import at test time, no network, no `.env`.

---

## 7. Open items for the owner / main session

1. **The $25 cap** (§4). Confirm the live Batch price tier. If standard,
   re-confirm with the owner before submitting — and tell them the
   ratified $16.09 understated.
2. **Model alias vs snapshot** (§2). Optional free check; if the resolved
   ids differ between E1 and v1.2, the run is rubric-plus-model.
3. **P2** (§1). Not encoded, by design. Needs its own ruling if wanted.
4. **What this run can and cannot fix.** It repairs the *teacher's*
   red-flag labels. Whether the repaired teacher fixes the student's
   measured retention failure (H3: red-flag family 0.669 [0.586, 0.742],
   kill-criterion 2 breached) is unknown until after the retrain and
   re-eval. Nothing here should be read as evidence that it will.
