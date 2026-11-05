# Owner decisions — 2026-11-05 (one page; reply with the letter and yes/no, or a correction)

**Update, same day:** A was ruled ("ratify") and run — see `data/f5/status/G3_RUN_2026-11-05_owner_read.md`. B–F remain open. Two wordings in A below were corrected after the reviewer's pass (calls are within-quarter relative, not real-time; the outcome mix is not a base rate).

**Where the project stands (verified today, nothing in flight).** The pipeline is complete
and green (1,588 root tests pass; the sealed corpus, labels, feature tables and guarded
runners are on disk; no process is running). The one-command product works:
`bin/fs report TICKER` turns any US filer's ticker into reading-aid pages (proved today on ETSY: 260 passages, 9 min 18 s, four pages, $0)
on this Mac. The historical scorecard — the thing you called THE VALUE — is built, tested,
red-teamed three times, and **has never run**, because the runners refuse to fit until you
type one word. Nothing synthetic is involved: 7,381 real filing rows, 143 companies, 33
quarters (2018Q1–2026Q1), real prices (the 2026-08-24 snapshot you ratified as decision 8).

## A. "ratify" — run the historical test and the scorecard   ← the critical one

**Recommendation: reply "ratify".** What you are confirming is the list in
`data/f5/G3_OWNER_RULINGS_2026-09-11.md` §4 — fifteen places where your September words
had to be read into a mechanism (tercile "correct" rule, 6-call minimum per company, the
tie rule, the year-over-year novelty window, which cash-flow ratio is duration-matched, and
so on). Five things to know before saying it:

1. It freezes the rules first and computes second. No number about text-versus-returns
   exists yet; after the pin none of it can be edited.
2. The honest expectation is a **null**: the text features probably do not add a
   detectable edge over the numeric baseline in large caps. If the margin test comes back
   null or unpowered, the text arm closes automatically, by the stopping rule you ratified
   on 2026-08-26. The scorecard is still produced and shown to you in every branch.
3. The scorecard is **descriptive**: for every filing, the model's out-of-fold call (a
   within-quarter relative statement against that quarter's scored peers, drawn after the
   quarter — not a real-time call), what the stock then did over the next 63 sessions
   against the universe average, right or wrong; per company with Wilson intervals, two
   comparators (a size-only yardstick and a numeric-only model), and the outcome mix of
   the period (not a benchmark).
4. It stays private. `data/f5/head1_scorecard.md` is git-excluded; only the universe
   block is committed. Nothing goes on a public page (legal baseline #4).
5. Runtime is tens of minutes to a few hours on this Mac (about 8,500 XGBoost fits);
   I run it in the background and bring you the per-fold tables and the scorecard to read
   yourself.

To correct a line instead, name it (e.g. "ratify, except the 6-call minimum → 4").

## B. Price data — subscribe to EODHD "All World" ($19.99/mo or $199/yr)

You ruled this in September ("cheaper feed without identifier"). It is needed for the
**portfolio simulator** (money metrics: returns with dividends, delisted names, costs) and
for any **forward paper period**. It is **not** needed for A. **Recommendation: subscribe
when A's result is in and you want P2 to start; set `EODHD_API_TOKEN` in your shell and
tell me.** Until then every price number is the ratified 2026-08-24 snapshot.

## C. Friends — what can be shared, and how

- **Now, zero legal work:** the reading-aid pages (labels beside passages, what changed,
  point-in-time fundamentals, the disclosure block; **no prices, no calls, no ranks**).
  You run `bin/fs report TICKER` and send the HTML files, or they clone the public repo
  (they would lack the adapter weights, so running it themselves is not yet possible).
  **Recommendation: yes — share pages privately; I add a one-line "rendered for the
  author's personal use; shared as a demonstration" footer per the legal baseline.**
- **Later, 8–16 hours of work plus a terms page:** a hosted "type a ticker" box that
  returns the reading aid only (legal tier b3; the memo recommends a 1–2 h attorney read
  of the terms). **Recommendation: not now.**
- **Never without a lawyer:** scorecard numbers, per-company calls, or a ranked list in
  anyone else's hands (tiers b4/b5). Friends using your price-data account is forbidden by
  the vendor licence (b6).

## D. How I work from here (confirm or adjust)

Adopted today from your words ("I cannot be too hands on … for ultimate, critical
decisions loop me in"), written into `CLAUDE.md`: I ask you only for **money, anything
public or shared, the word "ratify" and your own read of results, direction or charter
changes, and destructive operations**. Everything else I decide, log as a main-session
decision, and do. One reviewer pass per milestone replaces the four-round red-team cycles
of September. Team cut from 15 agents to 7 (`TEAM.md`). **Recommendation: confirm.**

## E. Two 10-second actions only you can do

1. `sudo xcodebuild -license accept` — a macOS update reset it; until then `python3`
   refuses to start and every tool falls back to the direct interpreter path (`bin/fs`
   handles this, but your own terminal `python3` will not).
2. `git push` — main is 29 commits ahead of GitHub (you push by convention). Or reply
   "push" and I will.

## G. Push, and what goes public with it (added after F6, 2026-11-05)

Main is far ahead of GitHub and the repository is public. The tracked research record now contains the
E2 result (an IC null, a research finding) and, in `data/f5/F6_E2_RESULT.md` and `results_head1.json`,
the scorecard's **universe-level** hit rates (model 0.519 vs numeric-only 0.510 vs size-only 0.486, all
with chance 0.500). The per-company pages are git-excluded and never leave this machine. I removed the
hit rates from README, MODEL_CARD and LIMITATIONS (the pages people read); the legal memo's own fix for
its item #4 permits committing the universe-level block, but a public track record of any kind is the
item the memo says an attorney must confirm. **Recommendation: push as is** (a null result with its
methodology is the honest public record, and no page states a track record); or say "hold" and I keep
main unpushed, or "strip" and I move the universe block out of the tracked files before pushing.

## F. Optional: your watchlist

Name 5–15 tickers you actually follow. I will build their reports now and keep them
refreshed after each earnings season on a schedule, so the product is useful to you from
day one. No tickers = I pick none; the ten random un-curated companies from September stay
as the proof set.

---
*Recommendations are mine, not yours; nothing here is recorded as a ruling until you reply
in chat. Longer record: `RESUME_HERE.md` top block, `HANDOFF.md` §3 (2026-11-05).*
