# FinScreen — website + video storyboard (draft v0, 2026-09-11; owner directs)

**Purpose.** A scroll-driven site that explains FinScreen to anyone interested, in the
spirit of the supply-chain site the owner described: the viewer scrolls, and a 3D model
of a filing's journey flows with them. The same beats become the video. Content rule
(PRODUCT_PLAN §0.5): the site shows what the tool does today and what it is testing; it
never states or implies returns; the demo is a live run on a ticker the viewer names.

**One-line promise the site can honestly make today:** *"Read what a company actually
said, faster, with every claim traceable to the filing and every model label carrying
its own error rate."* The bigger promise (validated signals) is shown as "what we are
testing, and how we make the test honest" until P5 has a record.

---

## The scroll (nine beats)

| # | scene (what the viewer sees) | the 3D model's motion | copy (short) | honest source |
|---|---|---|---|---|
| 1 | **Landing.** A single SEC filing rendered as a paper sheet floating in dark space; the company name is a live input box | idle drift; the sheet turns toward the viewer | "Every quarter, thousands of pages. Most of it never read. FinScreen reads the parts that matter and shows its work." | — |
| 2 | **EDGAR.** The sheet flies into a vast wall of documents (45,632 filings, 244 companies, 2016–2026) | camera pulls back to reveal the wall, then dives to one row | "We pull the filings straight from the SEC, rate-limited and cached. Nothing scraped from anywhere else." | F2 report |
| 3 | **Extraction.** The filing splits into three glowing panels: Risk Factors, MD&A, the earnings release | the sheet unfolds into three planes; boilerplate dims, the sections brighten | "Three sections carry the signal. Extraction is audited per company; failures are counted, not hidden." | F3 QA, the seven-financials hole |
| 4 | **The reader.** Passages stream through a small local model on a laptop; each passage picks up a label chip | text flows through a transparent "reader" block; chips attach | "A 7-billion-parameter model that runs on a laptop reads every passage: tone, guidance direction, risk flags. It cost $0 to run. It is wrong a measured fraction of the time, and we print that fraction." | G2: sentiment 86.9%, guidance 96.6% (NONE mass), red flags exploratory |
| 5 | **Time.** A timeline; a filing lands on it at its acceptance minute; the market opens the next morning | the filing drops onto a calendar rail; a sun rises at the next session | "Reports land after the close. The tool only ever knows what was public at that minute. This is where most backtests cheat, and where we don't." | target_e2 dating rule, 45% after-hours |
| 6 | **What changed.** Two filings side by side; paragraphs that appeared glow green, paragraphs that vanished fade red | the two sheets align; diff bands slide | "Paragraph by paragraph: what the company added, what it quietly removed, since last time." | report_filing diff |
| 7 | **The report.** The rendered page itself, scrolled | camera settles on the real HTML report | "Every label sits beside the passage it came from. The disclosure block cannot be collapsed." | report_filing |
| 8 | **The test.** A walk-forward: quarters advance, a wall between "known" and "future" moves with them | a moving barrier sweeps left to right across the timeline | "Does any of this predict what happens next? We are testing it the hard way: rules frozen before the data, no peeking, results published either way. So far the honest answer is: not yet proven." | F5 / E1 result |
| 9 | **Try it.** The input box from beat 1 returns, live | the model resolves into the live run | "Name a company. Watch it read." + waitlist / contact | P1a |

## The video (2–3 minutes)

1. 0:00 the input box; a real ticker typed by someone other than us; the fetch begins.
2. 0:20 beats 2–5 as animation over the real run's progress log.
3. 1:20 the report appears; scroll it; pause on one label beside its passage; pause on
   the disclosure block.
4. 2:00 the "what changed" view on the same company.
5. 2:30 the honest close: what it is, what it is not, what we are testing.

## Direction questions for the owner

1. **The model.** Options: (a) the filing-as-object journey above; (b) a "city" of
   companies where each building is a filer and the viewer flies into one; (c) an
   abstract data-flow (nodes and edges). Which one felt like the site you saw?
2. **Tone.** Calm and documentary (Bloomberg-terminal quiet) vs kinetic (product-launch
   energy). The honesty rule fits calm better; kinetic is doable.
3. **Live demo on the site** (needs a small server with the labeler; minutes per
   company) vs a pre-recorded run with an "email me a report" form. The live version
   is the real-data-first rule made visible; the recorded one is cheaper and safer.
4. **Who is the viewer.** Friends and peers who might ask to use it, or a general
   audience? It changes how much of the research story we tell.

## Stack (proposal)

Static site in `site/` deployable to GitHub Pages; Three.js for the model; GSAP
ScrollTrigger (or Lenis + native scroll) for the scroll choreography; no backend for
v1; the live demo, if chosen, is a separate small service the owner runs. Prototype
first as a single page with placeholder geometry so the motion and copy can be judged
before any 3D asset is made.


## v1 feedback (owner, 2026-09-11) — binding for v2

- Keep the city, but **more minimalist**; the v1 prototype "is hard to really understand
  what is happening and not as fun to interact with."
- **A distinct 3D model for each pipeline stage** (EDGAR, extraction, the reader, the
  clock, the diff, the test), not one set of boxes reused.
- Reference bar: the immersive Claude + Higgsfield-built sites; **smoothness** first.
- Explain as if the viewer has **no prior understanding**.
- Show the goal: **a personal investing research tool** (the owner's internal words are
  "personal investment tool"; on any public surface the legal baseline's finding #1 bars
  "advice", "advice tool", "should I invest", "calls", "top companies") — and the
  centrepiece is the historical scorecard: for a company's past reports, what the model would have said at
  the time, what the stock then did, and whether the call was right, across many
  companies. Every beat should lead to that.

## Legal baseline (2026-09-11) — binding copy rules for v2

Source: `data/legal/LEGAL_REVIEW_baseline_2026-09-11.md` (a language model in the
legal-reviewer role; not a lawyer; its §4 lists what a human attorney must confirm).
The rules below are adopted by the main session for every public surface (site, video,
README top, resume/LinkedIn blurbs) until an attorney says otherwise.

- **Words never used publicly:** "advice", "advice tool", "should I invest", "calls",
  "top companies", "beats the market", "accuracy". Use "personal investing research
  tool", "filing-reading aid", "research signals", "hit rate against a sign rule".
- **Beat 2** (#5): drop "Nothing scraped from anywhere else." → *"Filings come straight
  from the SEC, rate-limited and cached, with a declared contact address."* (Prices for
  the research run came from a public keyless endpoint and are disclosed as such; the
  product uses a licensed feed.)
- **Beat 3** (#10): *"Three sections are read."* — not "carry the signal".
- **Beat 4** (#10): *"It disagrees with a reference rater a measured share of the time,
  and that share is printed on every report."* — agreement, never "error rate".
- **Beat 5** (#11): *"This is where many backtests go wrong, and where this one is
  careful."* — no "most backtests cheat".
- **Beat 8**: keep "not yet proven" verbatim; no later edit softens it.
- **Beat 9 / the box** (#2, #7, Q6): a hosted box, if any, returns the **reading aid
  only** (labels beside passages, diffs, PIT fundamentals, disclosure block) — never a
  call, a price, a rank. Disclosure sentence directly under the input and above the
  result. Terms-of-use + disclaimer page before it ships.
- **Waitlist / "email me a report"** (#8): only with a one-page privacy notice, stated
  retention, no analytics without disclosure, and no "get investment calls" promise.
  The prototype's "records the request" line is false today → *"In the prototype nothing
  is sent or stored."*
- **The scorecard on a public page** (#2, #4, Q2): withheld until the memo's Q2
  conditions are met (attorney items §4-1/3/4/10, the data vendor's written position on
  derived numbers, public returns recomputed on the licensed feed). When shown: all
  companies, universe block first with both comparators and the base rate, methodology
  beside every number, hypothetical-performance disclosures, Wilson intervals, no
  forward statement, frozen and dated, position disclosure, never paired with a
  "try your company" box.
- **Footer wording on any public artifact** (#15): *"Rendered for the author's personal
  use; shown here as a demonstration."*; prototype line "No live capital" → *"Nothing
  here places a trade."*
- **Example choice** (#16): the default company and the video's ticker are chosen
  before any scorecard is seen, or by the viewer — never by hit rate.
- **Attribution** (#13): every rendered passage names its filing (form, date,
  accession) with an EDGAR link; the containment check stays.

