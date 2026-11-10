# P5 forward scorecard loop — owner packet — **WITHDRAWN 2026-11-10, NOT FOR RULING**

**This draft failed its red-team the day it was written (`data/f5/status/REVIEW_p5_packet_2026-11-10.md`: 7 must-fix). Two are design facts: the universe and filing set named here are not the ones the ratified model scored, and the ratified `book_to_market` feature carries future stock splits, so "the ratified procedure, unchanged" cannot honestly be continued forward. Kept for the record only. Do not rule on it.**

---

# (withdrawn draft) P5 forward scorecard loop — owner packet (one page; reply with the numbers, e.g. "1 yes, 2 yes, 3 yes, 4 yes")

**DRAFT 2026-11-10, written on the owner's words "Draft it". Nothing is built, fetched, fit or pinned. $0 so far.
Every rule below is the main session's judgment until you rule; your words are quoted verbatim before they are
read into anything.**

**The problem.** The scorecard on your pages is a snapshot. Prices end 2026-08-24, the last test quarter is
2026Q1, and no fitted model was saved. A filing made today can never get a row, so the thing you called the value
goes stale every day. A forward loop fixes that: the model's output for each new filing is written down when the
filing appears, and the row is marked right or wrong once the next 63 sessions of prices exist.

**Three facts that shape the design (each checked in the code or data on 2026-11-10).**
1. **The forward model cannot use text.** The ratified §13 outcome reads "text is not used as a signal". The
   loop therefore runs the **numeric-only** model, which is already a column on your scorecard pages, with the
   size-only yardstick beside it. The labeler is not involved, so a run takes minutes and no GPU.
2. **Nothing forward can be computed without new prices, not even the call.** Three of the numeric features
   (`momentum_126`, `realized_vol_63`, `book_to_market`) are built from prices up to the filing date.
3. **This loop is a record, not a test, and it will stay one.** The numeric-only model's rank correlation over the
   33 historical quarters has mean +0.025 and a quarter-to-quarter standard deviation of 0.186 (recomputed from
   `head1_oof_predictions.parquet`, deduplicated rows). At the repository's own multiplier (2.8 × sd / √quarters),
   8 forward quarters could detect a mean of about **0.18**, and even 33 could detect only about **0.09**. The
   model showed 0.025. **Correction to what I told you on 2026-11-09:** rows that were independent would swing by
   only about 0.086 at 136 rows a quarter, so most of the 0.186 is quarter-to-quarter variation that adding
   companies does not remove. A wider universe would help less than I implied. Calendar time is the constraint.

## Your four decisions (recommendation first; "yes" accepts it)

1. **Prices: allow a fresh fetch from Yahoo's free chart endpoint, $0, private use only.** Your words on
   2026-09-11 were: *"Free version of Yahoo, if Yahoo isn't free."* The main session read that as "ratify the stored
   snapshot; no new Yahoo fetch", and pointed later prices at the paid feed, which you declined on 2026-11-05
   (*"B. No"*). Together those two leave the product with no prices after 2026-08-24. A fresh fetch is the same
   source and the same split-adjusted, price-return-only definition as every historical row, so old and new rows
   stay comparable. What you accept: the endpoint's `robots.txt` disallows automated access and it has no published
   terms; the legal-reviewer memo (a language model, not a lawyer) rated a private run low exposure and said
   nothing derived from it should go public; the endpoint is unofficial and can break, in which case rows wait
   unresolved and say so. **Recommend yes.** If no, the alternatives are a paid feed (about $199 to $299 a year,
   which you have ruled against) or no forward loop.
2. **Model: the ratified numeric-only procedure, continued unchanged.** Same parameters, same expanding
   refit before each quarter, same purge, same call rule (top third, bottom third, middle is no call), same
   right-or-wrong rule. No text, no new features, no tuning. **Recommend yes.**
3. **Run it knowing it will never prove an edge at this size** (fact 3). What you get is the living
   per-company, per-quarter record you described, with calls that provably existed before the outcome, and the
   machinery any future signal would need. Evidence accrues only with calendar time, so the clock is the one
   thing that cannot be bought later. **Recommend yes.**
4. **Commit only a sha256 of the private log to the public repository after each run.** The hash reveals no
   call and no number; it makes the record impossible to backdate. The log itself stays git-ignored and personal
   use only. **Recommend yes.**

## Design decisions I have taken (logged as main-session decisions; name one to veto)

- **Timing.** A weekday-morning job. For each new 10-K, 10-Q or 8-K from a universe member it computes the
  features as of the filing's information date and appends the model's raw output to an append-only log. The
  call (which third) is assigned at quarter close from outputs already in the log. The outcome resolves no
  earlier than 64 sessions after the filing. A row logged after its return window opened is flagged late and
  reported separately.
- **Universe.** The 136 current members (membership of 2026-07-01), all of which have prices to the snapshot's
  end. Members that later stop trading stay in the log as unresolved and are counted. The annual reconstitution
  rule is written into the pre-registration before July 2027. Successor registrants (Exxon's 2026 CIK change is
  the one known case) are mapped through a small evidenced override file.
- **Storage.** Everything new goes under `data/p5/` as dated snapshots. No sealed or ratified file is
  touched; G3 is never re-pinned or re-run.
- **The gap.** 2026Q2 to the ratification date is filled as ordinary walk-forward rows, marked "computed after
  the fact", never as forward rows.
- **Where you see it.** A separate "forward rows" table on each company's scorecard page, watermarked *pre-paper
  — not for action under the charter* (PRODUCT_PLAN P4), personal use only, never shared. No money metric.
- **Length.** 8 quarters minimum, labelled a pipeline check on every report (PRODUCT_PLAN P5's own wording for
  a period that cannot reach the detection threshold).

## Cost, and what you owe

Money: $0 under decision 1. Compute: minutes a day, no GPU. Build: an estimated two builder sessions and one
reviewer pass. From you: these four rulings; later one diff to read and the word below; and installing the
scheduled job (two commands, `data/app/launchd/README.md` pattern), because a loop that does not run unattended
does not exist.

## Then: the word

After your rulings the `builder` writes `data/f5/P5_PREREGISTRATION.md`, the pin script and the forward runner
(which refuses to run without the pin), and the `reviewer` red-teams them. I then put the full pin diff in chat.
Only after you have read it do I ask for the one word only you type: **ratify**. Nothing before that fetches a
price or computes a forward number.
