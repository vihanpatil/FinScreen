# Tech-council advisory — personal-use direction (convened 2026-09-10 by the main session at the owner's request)

> **ADVISORY, written 2026-09-10 before any ruling; its Q5 defaults were RULED by the owner on 2026-09-11 (see the end of this note). Nothing else in it is a ruling.** The owner's verbatim prompt: *"I would rather just position it for personal use. It would be hard to sell to investment banks. That is my utmost priority and help me decide best way to do so. I like your timeline, but have tech council or just you decide on best timeline for this."* Owner rulings, when given, are recorded in HANDOFF §3. **RULED 2026-09-11 — owner, verbatim: "Adopt all three defaults, record it, start the app lane." All three Q5 defaults are now owner rulings; the record is HANDOFF §3 (2026-09-11).**

**Decision restated:** whether to move the already-ratified personal-analysis app (HANDOFF §3 2026-08-25: "post-E2 deliverable direction, not current scope") ahead of E2's close, triggered by the owner's words "position it for personal use … utmost priority."

Brief check: B's freeze claim is accurate but the brief omits GPU contention and owner-attention crowding. "Off the table" over-reads "hard to sell to investment banks" — the ledger should quote the verbatim words and record "distribution not pursued; re-ratification still required," not "never."

## Per-seat positions

**CEO.** The owner has resolved what the 08-25 identity ruling left open: the deliverable is a filing-reading aid for one person. E2 is no longer the goal; it is what lets the aid state honestly what its labels can claim. Making the owner wait ~8 weeks for their stated priority serves the plan, not the owner. B.

**CTO.** This is extension, not a build. `extract.py` is cache-only and CIK-keyed; the chunker's `paragraph_id` dedup is a prior-filing diff for free; `label_e2.py`'s `render_prompt_ids`/`generate` label a filing; `pit.value_as_of` gives fundamentals; `spotcheck/review_tool.html` is the proven static-HTML pattern. New code: two thin entry points (`ingest_one.py`: ticker→CIK→metadata→documents→extract→chunk; `label_filing.py`) and one renderer. No server, no scheduler, no prices. B.

**CRO-research.** The report will put NEGATIVE / LOWERED / IMPAIRMENT beside passages an investor reads before acting, and the only measured evidence on those labels' predictive value is E1's null (+0.0177 raw / −0.0097 dedup, `data/backtest_report.md`). B is acceptable only if that sentence is mandatory on every report and the report layer is test-proven never to read `data/f5/target_e2.parquet`. Dissent on timing: the owner owes 22 G3 rulings and just deprioritized E2; if the first report lands before the G3 packet, G3 is ruled never and E2 dies unclosed by neglect — the hole the re-evaluation named.

**CRO-risk.** A personal-use app triggers nothing: KC5 (`H5_stopping_rule.md` §5) names distribution or a product pivot; a single-user analysis tool sits inside the 08-25 boundary. It *amends* that ruling's timing clause — an owner ruling, not a re-ratification. The real exposure is drift from analysis to advice inside one head: no score, no rank, no action-colors, no prices — which also keeps Yahoo's robots.txt disallow entirely out of the tool (EDGAR-only, rate-limited, real-contact UA). `distress_tier` unrendered (§7). B with those refusals; A if any is dropped.

**CFO.** Remaining cost to close E2 is small — F5 ≈ 4–6 agent sessions + two owner reads, F6 ≈ 3–5 + one read. Naming the sunk cost so nobody uses it: 317k labels and 59 owner-ruled G2 rows are not a reason to continue; the small remaining cost is. C discards the cheap half. B adds ~6–8 sessions and ~1 GPU-hour per new company; the scarce currency, owner attention, spends one 10-minute report read plus reads already owed. B.

## Q1 — Sequence: B (5–0 on direction; CRO-research dissent on ordering)

**A**: touchpoints unchanged (G3, fold read, G4); ~8 weeks to personal use; touches nothing; risk = owner fatigue on gates the owner just deprioritized. **B**: same touchpoints + one 10-min read + today's ruling; ~3 weeks (band 2–5); risks = GPU contention with Track X nights (app labels by day, extension by night), freeze creep (test-enforced), G3 neglect (deadline in Q5); touches no pre-commitment, amends the 08-25 timing clause. **C**: ~3 weeks; but the ratified stopping rule has three outcomes and "abandoned" is not one; F6's write-up cannot state what the tool may claim; contradicts the owner's own "E2 completes as a finite bounded experiment." Refused.

## Q2 — MVP scope

Six features: (1) ticker→CIK→latest 10-K/10-Q/earnings 8-K from EDGAR, cached; (2) full section text (MD&A, Item 1A, EX-99.1) with `extract.py`'s locator/confidence flag; (3) per-chunk student labels beside the passage; (4) what changed vs prior same-form filing — paragraph-level add/remove via `paragraph_id`, newly-appearing red-flag categories marked exploratory; (5) PIT fundamentals as-of filing date, UNRESOLVED shown as unresolved, restatements visible; (6) the non-collapsible disclosure header. **Refuse:** any score/composite/rank or cross-company table sorted by a label-derived quantity; prices, returns, "since the filing the stock…"; buy/hold/sell or synonyms; alerts; generative summaries (student emits JSON only; no API; base Qwen untested); `distress_tier`; portfolio import.

**Boundary sentence:** *The tool may show the owner what a filing says, how a labeler with disclosed error read it, and what changed since last time — it may never rank, score, compare, or suggest what to do, even when the only reader is the owner.*

## Q3 — Timeline (medians; bands honest)

- **09-10/11** owner rules Q5 (touchpoint 0, 10 min).
- **Lane 1:** Step 1b close + red-team 09-12 (`STEP1B_backtest_e2.md`, `STEP1B_heads_e2.md` already on disk; text families pending); census 09-14; G3 packet 09-17; **G3 ruled 09-21 (band 09-18–10-02 — the 22 decisions are the critical path)**; run + red-team 09-23; per-fold read 09-25; F6 3–5 sessions → **E2 closed 10-08 (band 10-03–10-22)**; G4 read.
- **Lane 2:** L2.1 renderer over already-labeled E2 companies, 2–3 sessions, **first report opened 09-17**; L2.2 on-demand ingest+label for any ticker, 3–4 sessions + 10-row repro canary vs the G1 eval, 1–2 GPU-h per company-decade (317,081 chunks / 176 CIKs ≈ 1,800 chunks at 1,455/h), minutes per filing, never concurrent with a Track X night → **"company I care about" 09-30 (band 09-24–10-10)**; L2.3 one-line disclosure patch after F6.
- Sessions: Lane 1 ≈ 11–14, Lane 2 ≈ 6–8. Touchpoints: 5, three already owed. Lane 2's main risk: one odd filer (co-registrant, non-USD, exhibit miss) eating a session.

## Q4 — Guardrails for the ledger

Mandatory on every report, numbers verbatim: labeler = v1.2 student, adapter `cadca849…`, model output throughout · sentiment 293/337 = 86.9% [82.9, 90.1] INDETERMINATE, NEGATIVE recall 0.487, model consensus not human validation · guidance 96.6% [91.7, 98.7] NONE-mass, active precision 68.7% [58.2, 77.6], false-NONE 0/80, plus the `G2_FINAL_REPORT.md` §0 sentence (NONE may hide newly issued guidance) · red flags EXPLORATORY: teacher 42.0% [35.4, 48.9], student 28.0% [23.8, 32.6], config-sensitive 22.2% · predictive validity: "E1: no fold-robust text signal; E2: not run" → replaced by the F6 branch sentence verbatim · train-overlap banner when the CIK is an E1 company or the accession is in the v1.2 split · self-identification 26.8%/46.0% · extraction confidence/FLAGGED · "no price data used" · footer: not advice, no recommendation, no live capital, personal use only, not for distribution. **Never render:** scores, ranks, action colors, prices/returns, any E2 IC before `data/f5/G3_RATIFIED.json` exists, `distress_tier`. **Enforcement:** a source-scan test that the report layer imports nothing from target/backtest modules (the A11 pattern in `data/f5/status/STEP1A_target_e2.md`).

**Identity line:** *"A personal filing-reading aid for one user, backed by a bounded, closed research study — analysis with disclosed error, never a score or a recommendation."*

## Q5 — Decisions now

1. Adopt B; amend the 08-25 "post-E2" clause; E2 close stays ratified. **Default: yes.**
2. Ratify the Q2 boundary and Q4 block as mandatory. **Default: yes as drafted.**
3. G3 deadline: rule within 14 days of the packet; if missed, council re-convenes to close E2 on the record as "not run, documented," never drift. **Default: 14 days.**

## Strongest case against B

Two lanes for a one-person project is how the last two months went: every "parallel" track became a gate the owner had to read. The owner just said E2 is not the priority; a plan that takes them at their word picks C (close E2 as not-run, ship the aid, stop pretending 22 rulings will happen) or A (finish the science in one push while attention exists). B risks the worst of both — an app whose disclosure reads "E2 pending" indefinitely and a 90%-built E2 never run. Q5-3 is the council's answer, and it is only as strong as the owner's willingness to honor a deadline they set on themselves.

## Kill criteria (reverse B if)

G3 not ruled within 14 days of the packet → close E2 as not-run on the record. Report layer found reading an outcome table or IC → Lane 2 halts until re-red-teamed. Owner requests a score, rank, or price overlay → that is the product pivot; re-convene under KC5 before code. New-company labeling collides with a Track X night → wrapper lock first (F4 §4). On-demand path exceeds 2 sessions on one filer → scope MVP to the 244-CIK universe until F6.

**Dissent:** CRO-research — B, but the G3 packet reaches the owner before the first report does, even at days' cost to Lane 2. Four seats accept same-week landing plus the deadline.

Key files: `HANDOFF.md` (§1, §3 08-25/08-26/09-07/09-10, §7), `F5_PLAN.md`, `data/hardening/status/H5_stopping_rule.md`, `data/f4/g2/G2_FINAL_REPORT.md`, `data/f4/status/F4_campaign.md`, `finetune/label_e2.py`, `data/PRICES_NOTES.md`.
