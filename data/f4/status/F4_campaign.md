# F4 campaign — close-out record (written 2026-09-06, main session; corrected same day after independent red-team verification, §5)

**Status: F4 COMPLETE.** All 24 segments finalized; campaign parquet
written and independently verified row-for-row; enum sweep done (§3).
Nothing is running on the GPU. Next: Gate G2 (owner) — the E2 student-label
spot-check, pre-registered package under `data/f4/g2/`.

## 1. Facts (main-session, re-derived independently by the red-team pass)

| item | value |
|---|---|
| chain end | `data/f4/campaign_chain.log` 2026-09-06 02:32:07 "CAMPAIGN CHAIN COMPLETE (seg-011..seg-024 all finalized)" |
| segments finalized | 24 / 24 (every `segments/seg-0NN/manifest.json` carries `finalized_utc`) |
| close-out command | `python3 finetune/label_e2.py --finalize-campaign` → exit 0, 2.6 s; re-run into a scratch path reproduces the parquet byte-for-byte |
| campaign parquet | `data/f4/labels_e2_v1.parquet` — 317,081 rows × 43 top-level fields (45 leaf columns: `red_flags`/`distress_tier` are list-of-struct), sha256 `f236f421096c665b…` |
| campaign manifest | `data/f4/campaign_manifest.json` — `COMPLETE: true`, 0 API calls, $0 |
| row identity | chunk_id unique; set- AND order-identical to `data/f4/chunks_v1.parquet` (sha `d67395ec…`); all 317,081 `prompt_sha256` re-hash exactly from corpus text + frozen instruction `ebc45a85…`; journal↔parquet agree on every field |
| parse failures | 0 |
| finish reasons | `stop`: 317,081 — zero `length` |
| schema violations | 23 rows kept with `schema_valid=false`, issues in `schema_issues` (§3) |
| guidance imputed NONE | 48,790 / 95,335 applicable rows (51.18%) — EX99 51.1%; drifts smoothly 0.543 (seg-001) → 0.469 (seg-024) |
| **guidance on NON-applicable sections** | **2,826 rows** (2,803 MDA + 23 RISK_FACTORS; 230 carry an ACTIVE direction). Tracked per segment as `n_emitted_on_non_applicable_section`, NOT aggregated by `finalize_campaign`. **Any consumer must filter on `guidance_applicable`.** |
| head-truncated passages | 2,487 (0.784%), reserve 256; plus 1 passage (seg-021, `E2CHK-d86100e6c592dbdc`, a numeric table dense in U+2003/U+2007) whose kept text is not a byte-prefix — tokenizer round-trip, negligible |
| throughput (corrected) | row-latency sum 216.97 h → **1,461 chunks/h**; end-to-end first→last `labeled_at` 217.85 h (9.08 days) → **1,455 chunks/h**; per-night range 900–1,683 (seg-020 took 14.7 h). The manifest's 210.48 h / 1,506.5 figure is per-process wall time that omits two killed seg-013 processes (§4) — do not quote it |
| schema metadata | `f4_red_flags_status` (EXPLORATORY/DISCLOSURE-ONLY), `f4_labeler`, `f4_guidance_rule`, `f4_teacher` present |
| offline tests | 118 passed 2026-09-06 (`test_build_f4_chunks` 22 + `test_label_e2` 40 + `test_relabel_e1` 36 + `test_g2_spotcheck` 20); MLX venv untouched |

8K_BODY (790 chunks): not evaluable (RUN_COMMANDS trap 7); no per-class
number is reported for it anywhere in this record.

## 2. Council pre-commitment §7 item 3 — checked, with one OPEN item for the owner

Trigger: "finish=length runs, parse-failure rate above 0 sustained, or
per-section agreement drift beyond the H3v2 bands → stop." The first two:
not observed. The third cannot be an *agreement* on E2 (no teacher labels),
but a like-for-like comparator exists: the **same adapter** (`cadca849…`)
labeling E1's 6,746 chunks, `data/hardening/h3v2/e1_relabel_student_v12.parquet`.
Holding the labeler constant, the student's behaviour on E2 differs from its
behaviour on E1 by more than the E1 Wilson CIs:

| section | flag_present: student-on-E1 [95% CI] → student-on-E2 | flags/chunk | notes |
|---|---|---|---|
| MDA | 0.548 [0.533, 0.564] → **0.460** | 0.892 → 0.652 | sentiment omitted on 1.5% (2,630 rows; E1: 0) |
| EX99_PRESS_RELEASE | 0.561 [0.533, 0.589] → **0.424** | 1.003 → 0.598 (−40%) | guidance key omitted 32.9% → **51.1%**; conditional on emission, active rate 10.3% → 14.0% (the raw 6.85% vs teacher 6.92% "stability" is two offsetting shifts) |
| RISK_FACTORS | 0.901 [0.885, 0.915] → **0.828** | 1.597 → 1.310 | sentiment EMITTED on 8.4% of rows (4,177; rubric: N/A; student-on-E1: 1.0%) |

Decomposition: teacher→student on the SAME corpus (E1) costs only −3.5 /
−4.6 / −2.6 pts (MDA / EX99 / RF); student-E1→student-E2 costs −8.8 / −13.8 /
−7.3. So the corpus/behaviour component is 2–3× the known under-recall
component. Per-feature red-flag retention on E1 spans 0.424–0.974 (weakest:
DEMAND_mda 0.4238, MARGIN_mda 0.6000 — council condition 2: never a family
mean). By sector, flag_present ranges 0.383 (financials) to 0.615
(consumer); by filing year it is flat, 0.45–0.56; per-segment behaviour is
stable (no break at the seg-013 restart).

**OPEN — owner decision:** whether this distribution drift counts as §7 item 3
firing. The campaign is complete, so "stop" now means: **no downstream
consumer reads these labels before G2 measures them**, which is already the
gate order. `red_flags` remains exploratory/disclosure-only regardless.

## 3. Enum sweep — the 23 `schema_valid=false` rows

All 23 rows retained; raw output re-read from each segment's `labels.jsonl`;
stored columns behave as `relabel_e1.student_label_row` + `label_e2.f4_label_row`
specify (bad value → dropped/null, recorded in `schema_issues`, never remapped).

| issue | n | raw values seen | stored effect |
|---|---|---|---|
| `bad_enum:guidance_direction` | 17 | `UPDATED` ×15, `REVIEWED` ×2 (all EX99, applicable) | `guidance_direction` null, `guidance_imputed_none=false` |
| `bad_enum:red_flag_category` | 4 | `LEGAL_REGULATIORY_ACTION` ×1, `FINANCIAL` ×1, `FINANCING` ×2 | that pair dropped; other pairs kept. One of these (`E2CHK-c9502bff4d7a248b`) also omitted the guidance key, so the writer rule fired: `guidance_direction=NONE`, `guidance_imputed_none=true` — the rule working as ruled |
| `bad_enum:red_flag_modality` | 2 | `HYPOTHICAL` ×2 | that pair dropped; other pairs kept |

Per-segment: seg-001..005 one each; 008: 2; 010: 3; 011: 2; 015: 1; 017: 2;
019: 4; 020: 1; 022: 2; 024: 1. **Disposition:** no remap (17 / 95,335 =
0.018% of applicable guidance rows; 6 / 317,081 red-flag rows). Consumers
filter on `schema_valid` or treat nulls as nulls.

## 4. Operational record — including what went wrong

- **seg-013 was generated by THREE processes on 2026-09-01** (attempts
  10:06:00, 15:34:45, 16:38:53). The first two died without logging a
  `generate exit` — their parent wrappers died with them — and the segment
  sat dead ~5.5 h (journal 7,926/13,241 at 15:34). Six wrapper instances were
  started over the campaign, five within 64 minutes on 09-01. Cause: the
  wrapper's only anti-double-drive guard is a startup `pgrep` wait with no
  lock on the wrapper itself, and each new wrapper resets `tries=0`, so the
  5-attempt cap never engaged. **Data integrity survived** (resume-by-journal
  worked: zero duplicate chunk_ids within or across all 24 journals). The
  manifest records `n_processes=1` for seg-013 because killed processes are
  invisible to `update_manifest`.
- **Latent defect to fix before any future campaign** (e.g. an extension-
  stratum labeling): `data/f4/run_campaign_chain.sh` needs a wrapper-level
  lock (flock/pidfile). Not fixed now — no campaign is planned and the script
  is not on any current path.
- No manual `--segment` launch ever overlapped a live one; no API call; no
  change to `finetune/label_e2.py` / `relabel_e1.py` since the smoke (mtimes
  precede the canary; tests green). The wrapper exited on its own after
  seg-024.
- **WITHDRAWN guidance** is n=66 on E2 (E1: n=1, carved out as non-evaluable
  in HANDOFF §7). Whether that carve-out still applies is an owner call
  before any feature consumes it (G2 design §3.2 / decision vi).
- **G2 scope gap:** the 2026-08-21 amendment makes G2's sector-stratified
  check the extension-stratum promotion gate, but every F4 row is
  `home_stratum='core'` (W1-core). G2 cannot speak to the extension stratum;
  that needs its own campaign. Deferred, not waived.

## 5. Verification

Independent red-team pass (workflow `wf_89f6226b-206`, 2026-09-06): every
row-level integrity claim re-derived and held (§1); `finalize_campaign`
reproduced byte-for-byte; canary 10/10 and smoke provenance re-checked
clean. The pass found the reporting gaps now folded into §1, §2 and §4
(throughput mislabel, seg-013 incident, the student-on-E1 baseline, the
family-mean phrasing, the 2,826 non-applicable guidance rows). Verdict:
artifact fit to hand to G2; this record corrected accordingly.
