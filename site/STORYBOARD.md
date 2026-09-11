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
- Show the goal: **a personal investment advice tool** — and the centrepiece is the
  historical scorecard: for a company's past reports, what the model would have said at
  the time, what the stock then did, and whether the call was right, across many
  companies. Every beat should lead to that.
