# REVIEW: scorecard pages, landing page, IN/OUTSIDE universe line (2026-11-09)

Reviewer (Opus) report, saved to disk by the main session verbatim from the agent's hand-back (the reviewer's
session rules forbid it writing report files). The reviewer modified nothing, started no labeler or ingest,
did not run backtest_e2.py or heads_e2.py. Interpreter `/Library/Developer/CommandLineTools/usr/bin/python3`.
Main-session dispositions are appended at the end.

## What was checked, by recomputing it

- sha256 of `data/f5/head1_scorecard.json` = `028f34f5f5f57a6c7ba36c6f92193dcc802b6e686ff37164dac550063296a6e3`
  (shasum), printed on all 140 pages; all 140 carry the 8 disclosures verbatim plus `SCORECARD_FOOTER_LINE`, no
  `<details>` anywhere.
- Five companies (seeded random sample plus Apple): every summary figure and every table row compared with the
  JSON; counts, hit rate, Wilson interval and outcome mix recomputed independently from the rows: 0 mismatches;
  every right/wrong agrees with the sign of the excess return.
  CVX 93410: 22/51, 0.4314 [0.3050, 0.5673], mix 0.4194 over 62. AMZN 1018724: 6/20, 0.3000 [0.1455, 0.5190],
  mix 0.5758 over 33 (ticker from the store manifest). MMC 62709: 7/12, 0.5833 [0.3195, 0.8067], mix 0.3704
  over 27. Gen Digital 849399: hit_rate null → "no hit rate: 1 calls, fewer than the 6…", mix 0.5000 over 2.
  AAPL 320193: 20/28 (26/2), 0.7143 [0.5294, 0.8475], chance 0.622, mix 0.6176 over 34.
- Universe page: 139 rows, order exactly `sorted(name.lower(), cik)`; every rate/interval string matches; the
  three blocks match (0.5187 [0.5008, 0.5366]; 0.5099 [0.4919, 0.5278]; 0.4859 [0.4678, 0.5039]; no-call
  (tied) 1489 (0), 1490 (2), 1548 (115)).
- The module computes nothing (formatting and one sort by name/CIK); does not open the parquet; a fresh render
  to the scratchpad gave a byte-identical universe page.
- IN/OUTSIDE line vs `universe_membership`: 42 stores, 26 members; zero mismatches; manifests'
  `in_research_universe` agree with the db. Research-corpus (no --store) path unchanged.
- Tests: targeted 150 passed; full root suite 1903 passed, 1 warning, 333 s.
- `bin/fs scorecard --cik N` works (`py()` maps str over args).

## MUST-FIX
1. Identity paragraph says the model used "only data public at that filing date" (scorecard_page.py:40-46, all
   140 pages). LIMITATIONS.md:379-384 and MODEL_CARD.md:462-468 document an open look-ahead channel: the labeler,
   trained in 2026, may recognise the company and use post-training knowledge; how often it did is not known.
   The scorecard pages carry no self-identification disclosure. Fix: scope the clause to fundamentals and prices
   as public at the filing date; add the self-identification sentence (`RF.SELFID_*`) beside it.
2. Coverage sentence claims "The rest are absent for reasons the disclosures below state" (scorecard_page.py:
   50-53). 244 − 139 = 105 absent; the disclosures name only price censoring (31) and extraction gaps (10 CIKs,
   possibly overlapping); 40 of the 105 are still current members, 10 left before 2018. Fix: "the disclosures
   name two of the causes; the rest are not decomposed here", no new count.

## SHOULD
3. The within-quarter, relative nature of a call is stated only as the token `tercile_within_test_quarter`.
   Nothing says a call = top/bottom third of that quarter's out-of-fold predictions across the universe; "no
   call" = middle third, excluded from the denominator; window opens the session after the filing was public
   (info_date = max(filing_date, acceptance_date_ET), post-16:00 ET acceptance → next session). Legal Q2 rule 3.
4. `IN_UNIVERSE_LINE` says "is in" for former members: MU (723125) member 2016-07-01→2017-07-01; PLTR joined
   2026-07-01 and is in no scorecard; "244" counts every company ever a member. Suggest "is or was a member of
   the 244-company point-in-time research universe".
5. The landing page is a demonstration surface under ruling C yet links to pages marked "not even as a
   demonstration", under an identity line saying "never a score or a recommendation"; the pattern of links
   reveals scorecard membership. Suggest omitting the links from the demo page or a separate private index.
6. Company pages show no universe block beside the per-company figures (legal Q2 rules 2 and 5: no per-company
   page without the universe block, both comparators and the base rate).
7. Tests that would pass with wrong output: fixture rows give all three blocks the same call/result and the
   three universe blocks identical figures (column or block swaps pass); the alphabetical test's CIK order equals
   the name order (a CIK sort passes); the `n/a` branch in `cell()` is untested and dead against the real JSON.

## NOTE
8. Accession links go to reading-aid pages labeled now (2026-11), not the sealed-corpus labels the run used;
   links are decided at render time (later pages missing until re-render; deleted pages → dead links).
9. Null-hit-rate pages still show per-row right/wrong, so the withheld numerator is recoverable (matches the
   markdown's treatment; not a defect). Grammar: "1 calls".
10. Read-only sqlite URI `f"file:{db}?mode=ro"`: spaces fine; `#`/`?` fail loudly; `%20` is percent-decoded and
    silently opens a different file. Repo path is safe; `Path.as_uri() + "?mode=ro"` would be robust. Missing db
    → None → OUTSIDE (tested).
11. Importing `controls` for `HOLDING_DAYS` pulls in `backtest` and xgboost (~0.93 s of 0.96 s import).
12. Landing sort `int(r[1])` raises on a non-numeric store directory name (all 42 numeric today).
13. Builder report counts inconsistent (28/16 vs 26 members); the two orphan Apple pages are no longer on disk.
14. XOM store is CIK 2115436 "ExxonMobil Holdings Corp" (not a member); member CIK 34088 has a scorecard page;
    no link between them.
15. Fine: no "beats the market", no return estimate, no trade language of the module's own; Yahoo provenance on
    every page via `prices_sentence`; "Margin (POWERED, 0.04)" copied from the JSON.

## Main-session dispositions (2026-11-09; decisions, not owner rulings)
MF1 FIX (clause scoped to fundamentals/prices; self-identification sentence added). MF2 FIX (wording as
proposed). S3 FIX (plain-words paragraph on the call rule and the window, from target_e2.py's own rule). S4 FIX
("is or was a member … point-in-time"). S5 FIX: the landing page becomes the owner's private home page (its
footer is the personal-use-only line; it says which linked pages may be shown as a demonstration — the
per-company reading-aid pages — and which may not); no separate index. S6 FIX (universe block table on every
company page; `blocks_html` already exists). S7 FIX (distinct per-block fixture values; CIK order reversed vs
name order; dead `n/a` branch removed). N8 FIX (one sentence above the table). N9 FIX (plural). N10 FIX
(`as_uri()`). N11 ACCEPT (no-retyping pattern; 1 s). N12 ACCEPT (stores are numeric by construction of
ingest_one). N13 LOGGED: the two orphan Apple pages were ARCHIVED by the main session, not deleted, to
`data/app/status/archive/stale_pages_2026-11-09/`. N14 LOGGED as a known limitation (successor-CIK registrant;
the dead-member ticker rule is the right frame; no fix now). N15 none.
