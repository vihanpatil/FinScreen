# E3 — owner packet (one page; reply with the numbers, e.g. "1 yes, 2 yes, 3 keep, 4 yes yes")

**What this is.** The text arm (E2) closed on 2026-11-05 as a bounded null. The plan's null
branch continues on the **numeric factor families** (PRODUCT_PLAN P3 item 2). Before any
number is computed, the rules are written down — the same gate as G3. On disk: a **census** of
what the frozen data can support (`data/f5/census_e3.json`, table
`data/f5/status/E3_CENSUS_2026-11-06.md`) and a **draft pre-registration**
(`data/f5/E3_PREREGISTRATION.md`), red-teamed once (3 must-fix, 11 should, all applied).
**No model has been fit, nothing has been run, no sha is pinned, nothing frozen was touched,
$0.** Every rule is my judgment until you rule; your words are quoted verbatim before they are
read into anything.

**The one thing to know first — the power is poor, and the document says so.** On this
universe (about 100 large companies a quarter, 33 quarters) a single factor's quarterly rank
correlation swings with a standard deviation of 0.15–0.25, measured on E2's own zero-information
predictors and on H1's momentum and earnings-drift tests. A family would need a true mean IC
of about **0.07–0.16** to be detected; the inherited margin ladder (capped at 0.05, as G3's was)
is not reachable at that noise. **Honest expectation: the inference comes back "not resolvable
at this design's power" — it will not be dressed up as a null or a positive.** What the run
delivers either way, at $0 and in minutes: the per-company, per-quarter scorecard of what a
fixed, sign-only factor composite would have said and whether it was right — the thing you
called the value — with its intervals, beside the size yardstick and beside the numeric model
G3 already fitted (read from disk, nothing refit).

**Already known, so you rule with it in view (pre-registration §12):** G3's fitted
numeric-only model, scored on the 10-K/10-Q rows that are 96% of the proposed frame, reached a
mean IC of **+0.025** (below the noise floor 0.047); its hit rate on the E2 rows was 0.510
[0.492, 0.528]; H1 found 12-1 momentum at +0.029 and earnings drift at +0.028, both ambiguous.
The E3 "model" is a different quantity (a no-fit composite), but it is pre-registered after
those were seen.

## Your four decisions (recommendation first; "yes" accepts it)

1. **Unit = one 10-K/10-Q per company per quarter** (3,053 rows in the 33 quarters, 80–99
   companies a quarter). The E2 rows run as a sensitivity arm. **Recommend yes.**
2. **Run it knowing the inference is expected to be unpowered** — i.e. the value of this run
   is the descriptive scorecard of known factors plus an honest "not resolvable" on the
   signal question, at $0. The alternative is to leave the numeric families untested and the
   product as a reading aid. **Recommend yes.**
3. **Momentum definition: keep the 126-session momentum already in the frozen table**
   (nothing new built; it has no skip month, stated). Alt: build a 12-1 column — PIT by
   construction, one builder change, but chosen after H1's 12-1 result was seen.
   **Recommend keep.**
4. Two readings of your own words, confirm or correct each:
   **(a)** the pre-registration is written after G3's pooled numeric fit and H1's results on
   these data were seen; accepted as a disclosed limitation. **Recommend yes.**
   **(b)** On 2026-11-05 you typed **"B. No"** to the EODHD question. The main session read
   that as *no new spend, prices stay the 2026-08-24 snapshot, no money metric* (no portfolio
   return, Sharpe, drawdown, P&L; the frozen helper's top-minus-bottom return spread is
   suppressed). The scorecard still prints each row's realized excess return as the
   right/wrong label, as G3's did. **Recommend yes.**

## Design decisions I have taken under the low-touch policy (logged in HANDOFF §3; name one to veto)

Families and signs: momentum (+), value book/market (+), profitability — three margin ratios
(+), low volatility (−); growth and balance sheet not tested; size is the yardstick. The
"model": the average of the four families' point-in-time percentile ranks with those signs,
at least 3 of 4 present (99.6% of rows), no fit, no weights. Headline: mean over 33 quarters of
its rank correlation with the next-63-session excess return, one two-sided test; the four
families Holm-corrected as secondaries. Margin ladder inherited from G3 unchanged
({0.03, 0.04, 0.05}, never above 0.05). Same 33 quarters as E2. Censoring counted per fold
and a post-2019 arm, as in G3. Scorecard rules as in G3 §14 through a thin wrapper; private
files git-ignored. Outcome map: bounded null / positive / wrong-sign / unpowered, in that
order; nothing acted on in any branch; E4 needs a new ratification.

## Then: the word

Your rulings turn the draft into a ratification-ready document. Next the `builder` writes
Step 3 — `backtest_e3.py` (will refuse to run without the pin; reuses the E2 fold, dedup and
bootstrap code), `pin_e3.py`, the scorecard wrapper, tests — and the `reviewer` red-teams it.
**Then I run `pin_e3.py --show` and put its full diff in chat for you to read. Only after you
have seen it** do I ask for the one word, which only you type:

> **ratify**

On that word, with that day's date, the pin command will be run from the repo root:

```bash
/Library/Developer/CommandLineTools/usr/bin/python3 data/f5/pin_e3.py --pin --owner-word ratify --date YYYY-MM-DD
```

It will write `data/f5/E3_RATIFIED.json` with the document's sha256 and the census file's,
and will refuse if the document still reads as a draft or a pin already exists. Then the run
(minutes), the per-fold table and the scorecard come to you to read yourself. Nothing before
that computes a single E3 number.
