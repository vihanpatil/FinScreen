"""P3 §9 spot-read verdicts — one row per drawn section, written after the card
was read, frozen per row (F3_SPEC §9.2). Model judgements (HANDOFF §7), not the
owner's.

Path deviation, declared: the spec names data/f3/qa_verdicts.csv; this brief
restricts writes to data/f3/p3_qa/.
"""
import json, sys
from pathlib import Path
import pandas as pd

OUT = Path(__file__).resolve().parent
man = json.loads((OUT / "qa_manifest.json").read_text())["rows"]

# (card_no, verdict, note quoting the bytes that decided it)
V = {
 1:  ("CORRECT", "AMD Q1-18 release, head 'AMD Reports First Quarter 2018 Financial Results', tail is the non-GAAP free-cash-flow note. Whole exhibit, correct."),
 2:  ("CORRECT", "Head is the literal 'Item 2. Management's Discussion and Analysis...'; tail ends on the long-term-debt bullet at page 65, i.e. the end of MD&A before Item 3."),
 3:  ("CORRECT", "59 w. The legitimate 10-Q cross-reference class: 'Information about risk factors ... does not differ materially from that set forth ... pages 20 through 25 of the company's 2021 Annual Report'. Complete section."),
 4:  ("CORRECT", "'ITEM 1A. RISK FACTORS' head, tail ends inside the regulatory-demand risk, no Item 1B bleed."),
 5:  ("CORRECT", "Autodesk FY22 Q4 release; tail is the GAAP/non-GAAP EPS reconciliation table, page 15 of the exhibit."),
 6:  ("CORRECT", "'Item 1A. Risk Factors' head; tail ends on the 2024 Notes credit-rating risk."),
 7:  ("CORRECT", "'CON EDISON REPORTS 2023 EARNINGS'; tail is footnote b of the adjusted-earnings table."),
 8:  ("CORRECT", "'Item 2.\\nManagement's Discussion and Analysis...' head; tail is the critical-accounting-estimates paragraph at page 36."),
 9:  ("CORRECT", "Booking 10-Q MD&A; tail is the forward-looking-statements close that Booking places at the END of MD&A ('at the end of Management's Discussion and Analysis ... in this Quarterly Report' per the head)."),
 10: ("CORRECT", "MercadoLibre Q2-15 release; tail is the adjusted-EPS table plus IR contact block."),
 11: ("CORRECT", "Humana Q2-16 release; tail is the FY guidance membership bullets, page 24."),
 12: ("CORRECT", "Apache Q1-17 release, complete. BUT rendered ONE WORD PER LINE ('Delivered\\nfirst-quarter\\nproduction\\nof\\n481,000') -> 4,546 words yield 1 prose paragraph, prose_share 0.0101. Extraction correct; ZERO labeling chunks. Named class: word-per-line rendering."),
 13: ("CORRECT", "'ITEM 1A. RISK FACTORS' head, 42,268 w, tail on FX risk. Palantir's real 10-Q Item 1A."),
 14: ("CORRECT", "Regeneron Q2-19 release; tail is the collaborator net-sales table footnote."),
 15: ("CORRECT", "Uber 10-K Item 1A; tail on internal-control material weakness."),
 16: ("CORRECT", "Targa FY18 release; tail is the forward-looking disclaimer + IR contacts."),
 17: ("CORRECT", "31 w: 'There have been no material changes to the risk factors described in our Annual Report...'. The legitimate 10-Q cross-reference; complete."),
 18: ("CORRECT", "19 w cross-reference, complete. Sits 4 w above the (10-Q, RISK_FACTORS) floor of 15 -- the row class that floor exists to protect."),
 19: ("CORRECT", "'ITEM 2.\\nMANAGEMENT'S DISCUSSION...' head; tail is the unbilled-deferred-revenue glossary entry at page 43."),
 20: ("CORRECT", "Head carries one 'TABLE OF CONTENTS' running-header line before 'ITEM 2.' -- cosmetic, 3 words. Tail is the forward-looking close. Pre-2019, new filer, anchor method."),
 21: ("CORRECT", "Head carries the 'Table of Contents / McKESSON CORPORATION / FINANCIAL REVIEW (UNAUDITED)' running header before 'Item 2.'; body and tail are MD&A."),
 22: ("CORRECT", "'Item 2.\\nManagement's Discussion...' head; tail is the forward-looking close at page 48."),
 23: ("CORRECT", "Emerson Q3-17 release; tail is the segment-EBIT-margin reconciliation and the '###' end-of-release mark."),
 24: ("CORRECT", "Lam Q4-FY17 release; tail is the non-GAAP operating-margin table, page 9."),
 25: ("CORRECT", "Northrop Q1-17 release; tail is the segment-operating-margin definition + address block."),
 26: ("CORRECT", "Energy Transfer Q2-16 release; tail is the limited-partners' interest table, page 9. Note the exhibit's own 'SUPPLEMENTAL INFORMATION' section is inside the release, correctly NOT truncated (F3_SPEC §6)."),
 27: ("CORRECT", "CrowdStrike Q3-FY22 release; tail is the 'Magic Number' definition."),
 28: ("CORRECT", "Uber 10-Q Item 1A; tail on the exclusive-forum provision."),
 29: ("CORRECT", "EIDP/Corteva 10-K Item 1A; head has one 'Table Of Contents / Part I' running-header line; tail on the Proposed Separation tax risk, page 23."),
 30: ("CORRECT", "149 w D2 stub, correctly identified: 'The information required by this item is incorporated herein by reference to the material under Management's Discussion and Analysis ... in the 2022 Annual Report.' FLAGGED mda_stub_external_document + below_length_floor, confidence low. Failing visibly is the right outcome at 0 GETs."),
 31: ("CORRECT", "Realty Income 10-K Item 1A; tail on inflation risk, page 35."),
 32: ("CORRECT", "Vistra 10-Q Item 2; tail on 'CHANGES IN ACCOUNTING STANDARDS' -- the last MD&A subsection."),
 33: ("CORRECT", "Tesla Q3-24 Production & Deliveries, 285 w. Genuinely NOT an earnings release ('Our net income and cash flow results will be announced along with the rest of our financial performance when we announce Q3 earnings'). The population gate flagged exactly the right row; text extraction itself is complete and correct."),
 34: ("CORRECT", "WM 10-Q Item 2, located by the heading-regex fallback; head and tail are both MD&A. NOTE the tail is word-per-line rendered ('We\\ntake\\nproactive\\nsteps') -- same class as card 12, inside an otherwise prose section."),
 35: ("CORRECT", "Head is 'Regulatory Considerations', a genuine Truist MD&A subsection, not a foreign item; mid is 'Note 18. Operating Segments', tail is the Risk-Management close. head_keyword_absent fired benignly -- the C14-predicted 7-of-10 benign class."),
 36: ("WRONGLY-FAILED", "Emerson 10-K 2021. The document DOES contain \"ITEM 7 - MANAGEMENT'S DISCUSSION AND ANALYSIS OF FINANCIAL CONDITION AND RESULTS OF OPERATIONS\" as a real heading line (verified in the cached emr-20210930.htm). It fails only because the shipped fallback gap class [\\s\\xa0.:]{0,20} does not admit the ' - ' separator. Dialect D9."),
 37: ("WRONGLY-FAILED", "AEP 10-Q 2016-Q3. MD&A is present; the TOC row reads 'Items 1, 2, 3 and 4 - Financial Statements, Management's Discussion and Analysis of Financial Condition and Results of Operations, ...' -- a COMBINED-item row that _ITEM_LABEL_PREFIX_RE ('^item\\s*[0-9]') cannot match because of the plural 'Items'. Dialect D10."),
 38: ("CORRECT", "Union Pacific Q3-15 release, complete; the flagged 'supplemental' tail is UNP's own freight-revenue/financial statistics appendix inside the release. Flag is a dilution measurement, not an error -- §6 correctly does not truncate."),
 39: ("EMPTY-OR-BOILERPLATE", "15 w: 'Item 2.\\nManagement's Discussion and Analysis of Financial Condition and Results of Operations\\n20\\n\\ufeff'. That trailing '20' is a PAGE NUMBER -- the heading-regex fallback matched a table-of-contents row, not the section. Correctly FLAGGED (below_length_floor + heading_regex_fallback, confidence low) so it fails visibly, but it is a wrong slice, not a thin section."),
 40: ("CORRECT", "37 w D2 stub: 'The information required by this item is incorporated by reference to Nucor's 2016 Annual Report, page 4'. Correctly FLAGGED mda_stub_external_document, low confidence."),
}

rows = []
for i, r in enumerate(man, 1):
    v, note = V[i]
    rows.append(dict(card=i, tier=r["tier"], frame=r["why"], cik=r["cik"],
                     company_name=r["company_name"], form=r["form"],
                     section_type=r["section_type"], filing_date=r["filing_date"],
                     accession_number=r["accession_number"],
                     extraction_status=r["extraction_status"],
                     reason_code=r["reason_code"],
                     extraction_method=r["extraction_method"],
                     extraction_confidence=r["extraction_confidence"],
                     word_count=r["word_count"], verdict=v, verdict_note=note))
d = pd.DataFrame(rows)
d.to_csv(OUT / "qa_verdicts.csv", index=False)

print("=== verdicts by tier (never pooled) ===")
print(pd.crosstab(d.tier, d.verdict).to_string())
for t, g in d.groupby("tier"):
    bad = (~g.verdict.isin(["CORRECT", "CORRECTLY-FAILED"])).sum()
    n = len(g)
    # Wilson 95% interval
    import math
    z, p = 1.96, bad / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    print(f"{t}: {bad}/{n} not-CORRECT = {p:.1%}  Wilson95 [{max(0,c-h):.1%}, {min(1,c+h):.1%}]")
print("\nwrote", OUT / "qa_verdicts.csv")
