# SPOTCHECK v1.2 — OWNER RULING PACKET (generated 2026-08-27)

Model-consensus P1: **87/200 = 43.50% [36.82, 50.43] — DEMOTE fires on consensus** (boundary k>=84). Your rulings below supersede the adjudicator; k moves down 1 for each needs_human row you rule "stored label is RIGHT". 4+ such rulings put k at/below 83 = no demote. Rule on the merits, not the consequence — the boundary was pinned before any data.

## PART A — the 22 needs_human rows (rule each: STORED-RIGHT / ADJUDICATOR-RIGHT / OTHER)

### A1. `CHK-7ac2fc7a617e9668`  [pattern: supply-chain-complexity-vs-constraint]
**Stored:** [["DEMAND_WEAKNESS", "HYPOTHETICAL"], ["IMPAIRMENT_WRITEDOWN", "REALIZED"], ["SUPPLY_INPUT_CONSTRAINT", "HYPOTHETICAL"]]  
**Auditor:** [["DEMAND_WEAKNESS", "HYPOTHETICAL"], ["IMPAIRMENT_WRITEDOWN", "REALIZED"], ["MARGIN_COST_PRESSURE", "HYPOTHETICAL"]]  
**Adjudicator (disagree, medium):** [["DEMAND_WEAKNESS", "HYPOTHETICAL"], ["IMPAIRMENT_WRITEDOWN", "REALIZED"], ["MARGIN_COST_PRESSURE", "HYPOTHETICAL"]]
**Adjudicator brief:** "We have incurred and may in the future incur inventory provisions or impairments" is an occurrence claim, so IMPAIRMENT_WRITEDOWN is REALIZED, and "Customers may delay purchasing existing products" carries DEMAND_WEAKNESS as HYPOTHETICAL. The stored SUPPLY_INPUT_CONSTRAINT is hard to support: the passage says the company is *increasing* "supply and capacity purchases" and describes only added "complexity," not a shortage or disruption limiting production. Meanwhile "may cause us to incur additional costs" names no supply or tariff cause, which the section 4 disambiguation note routes to MARGIN_COST_PRESSURE; the owner should weigh whether supply-chain complexity plus "quality or production issues" is enough to earn SUPPLY_INPUT_CONSTRAINT.
<details><summary>chunk text (3893 chars)</summary>

```
The following discussion and analysis of our financial condition and results of operations should be read in conjunction with “Item 1A. Risk Factors,” our Consolidated Financial Statements and related Notes thereto, as well as other cautionary statements and risks described elsewhere in this Annual Report on Form 10-K, before deciding to purchase, hold, or sell shares of our common stock.

NVIDIA pioneered accelerated computing to help solve the most challenging computational problems. Since our original focus on PC graphics, we have expanded to several other large and important computationally intensive fields. Fueled by the sustained demand for exceptional 3D graphics and the scale of the gaming market, NVIDIA has leveraged its GPU architecture to create platforms for scientific computing, AI, data science, AV, robotics, and digital twin applications.

Revenue growth in fiscal year 2025 was driven by data center compute and networking platforms for accelerated computing and AI solutions. Demand for our Hopper architecture drove our significant growth for the full year. We began shipping production systems of the Blackwell architecture in the fourth quarter of fiscal year 2025.

We continue to increase our supply and capacity purchases with existing and new suppliers to support our demand projections and increasing complexity of our data center products. With these additions, we have also entered and may continue to enter into prepaid manufacturing and capacity agreements to supply both current and future products. The increased purchase volumes and integration of new suppliers and contract manufacturers into our supply chain creates more complexity in managing multiple suppliers with variations in production planning, execution and logistics. Our expanding product portfolio and varying component compatibility and quality may lead to increased inventory levels. We have incurred and may in the future incur inventory provisions or impairments if our inventory or supply or capacity commitments exceed demand for our products or demand declines.

Product transitions are complex and we often ship both new and prior architecture products simultaneously as our channel partners prepare to ship and support new products. We are generally in various stages of transitioning the architectures of our Data Center, Gaming, Professional Visualization, and Automotive products. The computing industry is experiencing a broader and faster launch cadence of accelerated computing platforms to meet a growing and diverse set of AI opportunities. We have introduced a new product and architecture cadence of our Data Center solutions where we seek to complete new computing solutions each year and provide a greater variety of Data Center offerings. The increased frequency of these transitions and the larger number of products and product configurations may magnify the challenges associated with managing our supply and demand which may further create volatility in our revenue. The increased frequency and complexity of newly introduced products could result in quality or production issues that could increase inventory provisions, warranty, or other costs or result in product delays. We incur significant engineering development resources for new products, and changes to our product roadmap may impact our ability to develop other products or adequately manage our supply chain cost. Customers may delay purchasing existing products as we increase the frequency of new products or may not be able to adopt our new products as fast as forecasted, both impacting the timing of our revenue and supply chain cost. While we have managed prior product transitions and have sold multiple product architectures at the same time, these transitions are difficult, may impair our ability to predict demand and impact our supply mix, and may cause us to incur additional costs.
```
</details>

### A2. `CHK-8b0f62bfc6175763`  [pattern: loan-carrying-value-writedown-as-impairment]
**Stored:** [] (no flags)  
**Auditor:** [["IMPAIRMENT_WRITEDOWN", "REALIZED"]]  
**Adjudicator (disagree, medium):** [["IMPAIRMENT_WRITEDOWN", "REALIZED"]]
**Adjudicator brief:** The passage states that "$82 million, or 21 percent, were 180 days or more past due and had been written down to the estimated fair value of the collateral, less costs to sell" — past tense, an actual reduction of an asset's carrying value, which is squarely section 4's IMPAIRMENT_WRITEDOWN ("asset impairments ... wrote down") at REALIZED modality. The rest of the passage is nonperforming and concentration statistics that carry no flag. The owner should weigh the precedent: routine bank credit tables use this write-down-to-collateral wording constantly, so ruling it in will flag many bank chunks.
<details><summary>chunk text (2408 chars)</summary>

```
entire residential mortgage portfolio. In addition, at December 31, 2025, $150 million, or four percent, of outstanding interest-only residential mortgage loans that had entered the amortization period were nonperforming, of which $48 million were contractually current. Loans that have yet to enter the amortization period in our interest-only residential mortgage portfolio are primarily well-collateralized loans to our wealth management clients and have an interest-only period of three years to 10 years. Substantially all of these loans that have yet to enter the amortization period will not be required to make a fully-amortizing payment until 2027 or later.

Table 23 presents outstandings, nonperforming loans and net charge-offs by certain state concentrations for the residential mortgage portfolio. In the New York area, the New York-Northern New Jersey-Long Island Metropolitan Statistical Area (MSA) made up 15 percent of outstandings at both December 31, 2025 and 2024. The Los Angeles-Long Beach-Santa Ana MSA within California represented 14 percent of outstandings at both December 31, 2025 and 2024.

At December 31, 2025, the home equity portfolio made up six percent of the consumer portfolio and was comprised of home equity lines of credit (HELOCs), home equity loans and reverse mortgages. HELOCs generally have an initial draw period of 10 years, and after the initial draw period ends, the loans generally convert to 15- or 20-year amortizing loans. We no longer originate home equity loans or reverse mortgages.

2025 primarily due to draws on existing lines and new originations outpacing paydowns. Of the total home equity portfolio at December 31, 2025 and 2024, $8.9 billion and $9.2 billion, or 33 percent and 36 percent, were in first-lien positions. At December 31, 2025, outstanding balances in the home equity portfolio that were in a second-lien or more junior-lien position and where we also held the first-lien loan totaled $4.8 billion, or 18 percent, of our total home equity portfolio.

to $392 million at December 31, 2025. Of the nonperforming home equity loans at December 31, 2025, $238 million, or 61 percent, were current on contractual payments. In addition, $82 million, or 21 percent, were 180 days or more past due and had been written down to the estimated fair value of the collateral, less costs to sell. Accruing loans that were 30 days or more past d
```
</details>

### A3. `CHK-91cd090467f7fa4b`  [pattern: loan-carrying-value-writedown-as-impairment]
**Stored:** [["MARGIN_COST_PRESSURE", "REALIZED"], ["TRADE_POLICY_EXPOSURE", "HYPOTHETICAL"]]  
**Auditor:** [["IMPAIRMENT_WRITEDOWN", "REALIZED"], ["MARGIN_COST_PRESSURE", "REALIZED"], ["TRADE_POLICY_EXPOSURE", "REALIZED"]]  
**Adjudicator (disagree, medium):** [["IMPAIRMENT_WRITEDOWN", "REALIZED"], ["MARGIN_COST_PRESSURE", "REALIZED"], ["TRADE_POLICY_EXPOSURE", "REALIZED"]]
**Adjudicator brief:** The sentence's main verbs are past tense — trade-policy "developments ... have led to uncertainty ... and have adversely impacted" — so TRADE_POLICY_EXPOSURE is REALIZED, not HYPOTHETICAL, and "higher costs associated with inflationary pressures experienced over the past several years" is causeless cost inflation, which the section 4 note says is always MARGIN_COST_PRESSURE. The passage also states "the carrying value of these loans has been reduced to the estimated collateral value less costs to sell," a realized asset write-down. The owner should weigh the same recurring question as the other bank chunk: whether routine loan carrying-value reduction should count as IMPAIRMENT_WRITEDOWN.
<details><summary>chunk text (2602 chars)</summary>

```
. Credit card-related products were 52 percent and 53 percent of the U.S. small business commercial portfolio at June 30, 2025 and December 31, 2024 and represented 98 percent of net charge-offs for both the three and six months ended June 30, 2025. Accruing loans that were past due 90 days or more remained relatively unchanged during the six months ended June 30, 2025.

Table 31 presents the nonperforming commercial loans, leases and foreclosed properties activity during the three and six months ended June 30, 2025 and 2024. Nonperforming loans do not include loans accounted for under the fair value option. During the six months ended June 30, 2025, nonperforming commercial loans and leases increased $89 million to $3.4 billion. At June 30, 2025, nearly 100 percent of commercial nonperforming loans, leases and foreclosed properties were secured, and 51 percent were contractually current. Commercial nonperforming loans were carried at 82 percent of their unpaid principal balance, as the carrying value of these loans has been reduced to the estimated collateral value less costs to sell.

Commercial credit exposure is diversified across a broad range of industries. Total commercial committed exposure increased $59.4 billion during the six months ended June 30, 2025 to $1.3 trillion. The increase in commercial committed exposure was concentrated in Finance companies, Asset managers and funds and Capital goods.

Finance companies, our second largest industry concentration with committed exposure of $119.8 billion, increased $18.0 billion, or 18 percent, during the six months ended June 30, 2025. The increase in committed exposure was primarily driven by increases in Consumer finance, Thrifts and mortgage finance and Diversified financials.

Capital goods, our third largest industry concentration with committed exposure of $104.1 billion, increased $5.3 billion, or five percent, during the six months ended June 30, 2025. The increase in committed exposure was driven by increases in Trading companies and distributors, Machinery, and Construction and engineering, partially offset by a decrease in Industrial conglomerates.

Various macroeconomic challenges, including geopolitical tensions, higher costs associated with inflationary pressures experienced over the past several years, elevated interest rates and ongoing negotiations and developments regarding international trade policies have led to uncertainty in the U.S. and global economies and have adversely impacted, and may continue to adversely impact, a number of industries. We continue to monitor these risks.
```
</details>

### A4. `CHK-90f40730f8c06857`  [pattern: government-rate-setting-not-legal-action]
**Stored:** [["LEGAL_REGULATORY_ACTION", "REALIZED"], ["MARGIN_COST_PRESSURE", "REALIZED"]]  
**Auditor:** [["MARGIN_COST_PRESSURE", "REALIZED"]]  
**Adjudicator (disagree, medium):** [["MARGIN_COST_PRESSURE", "REALIZED"]]
**Adjudicator brief:** "increased medical costs in 2025 ... have added to the compounding impact of the previous multi-year rate shortfalls" is realized, causeless cost pressure, so that flag stands. The regulatory material, however, is reimbursement rate-setting — "Medicare Advantage rate notices," the "Advanced Notice for 2027," "revisions to the risk adjustment model" — and section 4's LEGAL_REGULATORY_ACTION covers litigation, investigations, enforcement, fines or new requirements creating compliance burden, none of which is asserted. The owner must weigh whether adverse government payment-rate actions should count as regulatory action, since this recurs across healthcare filings.
<details><summary>chunk text (2530 chars)</summary>

```
The health care market continues to change based on demographic shifts, new regulations, political forces and both payer and patient expectations. Health plans and care providers are being called upon to work together to close gaps in care and improve overall care quality and patient experience, improve the health of populations and reduce costs. We are working to accelerate realization of these benefits through the innovation and integration of our care delivery models, including in-clinic, in-home, behavioral and virtual care, and by using our data, analytics and AI to provide clinicians with the information necessary to provide the best possible care in the most cost-efficient setting. We continue to see a greater number of people enrolled in fully accountable value-based plans that reward high-quality, affordable care and foster collaboration.

This trend is creating needs for health management services that can coordinate care around the primary care physician, including new primary care channels, and for investments in new clinical and administrative information and management systems, which we believe provide growth opportunities for our Optum business platform. A key focus of our future growth is to accelerate the transition from fee-for-service care delivery and payment models to fully accountable value-based care. This transition requires initial costs such as system enhancements, integrated care coordination technology, physician training and clinical engagement. Enhanced clinical engagement is a critical step to improving the experience and health outcomes of the people we serve and should result in lower costs to the overall health system over time.

Medicare Advantage rate notices for numerous years have resulted in industry base rates well below the industry forward medical cost trend. While the Final Notice for 2026 approached the expected industry forward medical cost trend, the Advanced Notice for 2027 is far below. Additionally, increased medical costs in 2025, which are expected to continue in future periods, have added to the compounding impact of the previous multi-year rate shortfalls creating sustained pressure on the Medicare Advantage program. Further, substantial revisions to the risk adjustment model, which serves to adjust rates to reflect a patient’s health status and care resource needs, have resulted and will continue to result in reduced funding and potentially benefits for people, especially those with some of the greatest health and social challenges.
```
</details>

### A5. `CHK-a577c2ef70bba5da`  [pattern: noun-list-subject-with-company-specific-cost-predicate]
**Stored:** [["LEGAL_REGULATORY_ACTION", "HYPOTHETICAL"], ["MARGIN_COST_PRESSURE", "HYPOTHETICAL"], ["SUPPLY_INPUT_CONSTRAINT", "HYPOTHETICAL"], ["TRADE_POLICY_EXPOSURE", "HYPOTHETICAL"]]  
**Auditor:** [["LEGAL_REGULATORY_ACTION", "REALIZED"]]  
**Adjudicator (disagree, medium):** [["LEGAL_REGULATORY_ACTION", "REALIZED"], ["MARGIN_COST_PRESSURE", "HYPOTHETICAL"]]
**Adjudicator brief:** I land between the two raters. "Compliance with these evolving regulatory regimes and legal requirements depends on our ability to improve ... our processes, controls, surveillance" presupposes regimes already imposing obligations, so LEGAL_REGULATORY_ACTION is REALIZED; but the auditor goes too far in dropping cost pressure, because the same sentence ends "could increase our compliance costs," a company-specific projected cost increase that the section 4 note routes to MARGIN_COST_PRESSURE. The stored SUPPLY and TRADE flags come only from the bare noun string "labor shortages, wage pressures, supply chain disruptions and higher inflation," which is the mining-depth rule's own negative example; the owner must weigh whether a noun-list subject with a company-specific cost predicate clears that bar.
<details><summary>chunk text (2675 chars)</summary>

```
increasing speed and novel ways in which funds circulate could make it more challenging to track the movement of funds and heighten financial crimes risk. Compliance with these evolving regulatory regimes and legal requirements depends on our ability to improve and/or evolve our processes, controls, surveillance, detection and reporting and analytic capabilities and could be adversely impacted by operational failures.

In the U.S., the political uncertainty around the federal government’s debt ceiling, a growing federal budget deficit and government debt levels could create the possibility of U.S. government defaults on its debt and/or further downgrades to its credit ratings, and prolonged government shutdowns, which could weaken the U.S. dollar, cause market volatility, negatively impact the global economy and banking system and adversely affect our financial condition, including our liquidity. Also, changes in fiscal, monetary, regulatory, trade and/or foreign policy, labor shortages, wage pressures, supply chain disruptions and higher inflation, could increase our compliance costs and adversely affect our business operations, organizational structure and results of operations. Emerging market currency values and monetary policy settings are particularly sensitive to such changes in U.S. monetary policy. Also, elevated or rising U.S. interest rate levels or high tariff rates, could result in additional currency volatility and recessionary conditions in a number of non-U.S. markets.

We are also subject to geopolitical risks, including economic sanctions, acts or threats of international or domestic terrorism, including responses by the U.S. or other governments thereto, corporate espionage, increased state-sponsored cyberattacks or campaigns, civil unrest and/or military conflicts, including the escalation of tensions between China and Taiwan, which could adversely affect business, market trade and general economic conditions abroad and in the U.S. The Russia/Ukraine conflict and the conflicts in the Middle East have magnified such risks and resulted in regional instability, and adverse developments in or expansion of these conflicts could negatively impact commodity and other financial markets, as well as economic conditions. Widening regional conflicts resulting in the involvement of neighboring countries and/or North Atlantic Treaty Organization member countries and/or military conflicts in other areas of the world could result in additional economic disruptions, financial market volatility, higher inflation and changes to asset valuations, which could disrupt our operations and adversely affect our results of operations.
```
</details>

### A6. `CHK-2d6b130dae96d639`  [pattern: market-level-supply-disruption-for-a-producer]
**Stored:** [["DEMAND_WEAKNESS", "HYPOTHETICAL"], ["TRADE_POLICY_EXPOSURE", "HYPOTHETICAL"]]  
**Auditor:** [["MARGIN_COST_PRESSURE", "HYPOTHETICAL"], ["SUPPLY_INPUT_CONSTRAINT", "REALIZED"], ["TRADE_POLICY_EXPOSURE", "REALIZED"]]  
**Adjudicator (disagree, medium):** [["MARGIN_COST_PRESSURE", "HYPOTHETICAL"], ["SUPPLY_INPUT_CONSTRAINT", "REALIZED"], ["TRADE_POLICY_EXPOSURE", "REALIZED"]]
**Adjudicator brief:** "Recent U.S. trade policy actions, including the introduction of tariff replacement measures" is an existence claim, so section 6 makes TRADE_POLICY_EXPOSURE REALIZED while its consequence — "could increase costs over time" — is the named-cause cost impact that section 4 labels MARGIN_COST_PRESSURE at HYPOTHETICAL. The stored DEMAND_WEAKNESS rests on "could affect demand," which states no direction and does not assert softening. The owner must weigh the supply call: "have resulted in the suspension of substantial supply" is realized, but it describes the global commodity market rather than this filer's own inputs or production.
<details><summary>chunk text (3365 chars)</summary>

```
Additional information concerning these and other factors that may cause the Company's results of operations and financial position to differ from expectations can be found in the Company's other filings with the SEC, including the Company's 2025 Form 10-K, Quarterly Reports on Form 10-Q and Current Reports on Form 8-K.

The Company's financial results are significantly influenced by oil prices and, to a lesser extent, NGL and natural gas prices and commodity market differentials. The average WTI price per barrel for the three months ended March 31, 2026 was $71.93, compared

Changes in oil prices could result in adjustments to the Company's capital investment levels and allocation, which may in turn impact production volumes. Oil prices are expected to remain volatile due to a number of factors, including heightened geopolitical risk, the evolving macroeconomic environment and its effects on global energy demand, future actions by OPEC and non-OPEC oil-producing nations, and ongoing shifts in U.S. trade policy.

The ongoing conflict with Iran has significantly disrupted global crude oil and natural gas markets. Actions impacting commercial shipping through the Strait of Hormuz and regional energy infrastructure have resulted in the suspension of substantial supply and higher commodity prices. The duration and trajectory of the conflict remains uncertain, contributing to ongoing commodity price volatility.

Recent U.S. trade policy actions, including the introduction of tariff replacement measures, could also have implications for Occidental's business operations and financial performance. While the Company has not experienced a material impact to date, tariffs or tariff replacement measures imposed on the Company's suppliers could increase costs over time, and broader macroeconomic effects of policy changes and uncertainty could affect demand for the Company's products and its realized prices.

The Company is focused on delivering a unique shareholder value proposition with its portfolio of oil and gas and midstream and marketing assets, as well as its ongoing development of carbon management and sequestration solutions and GHG emissions reduction efforts. The Company conducts its operations with an emphasis on technical expertise, HSE, sustainability and social responsibility. In order to maximize shareholder returns, the Company will

The Company completed the sale of OxyChem on January 2, 2026 in an all-cash transaction for an adjusted purchase price of $9.5 billion, subject to additional post-closing adjustments, resulting in a gain of $3.1 billion, net of taxes. OxyChem's results of operations, cash flows and the related retained liabilities and indemnification obligations are reported as discontinued operations in the Company's Consolidated Statements of Operations and Cash Flows for all periods presented, with its assets and liabilities reclassified as held for sale in the Company's Consolidated Balance Sheets as of December 31, 2025. There are post-closing indemnification obligations for (i) such legacy environmental liabilities and (ii) pre-closing liabilities of OxyChem, including pre-closing environmental liabilities, in each case subject to certain limitations and procedures, and Occidental entered into a guaranty in favor of Berkshire Hathaway to guarantee these indemnification obligations.
```
</details>

### A7. `CHK-91f8865d5d329ba0`  [pattern: anaphoric-litigation-reference-across-chunk-boundary]
**Stored:** [["LEGAL_REGULATORY_ACTION", "HYPOTHETICAL"]]  
**Auditor:** [["LEGAL_REGULATORY_ACTION", "REALIZED"]]  
**Adjudicator (disagree, medium):** [["LEGAL_REGULATORY_ACTION", "REALIZED"]]
**Adjudicator brief:** The passage states as present fact that "we have certain financial protections pursuant to the respective retrospective responsibility plans" and treats the covered "settlements, judgments, losses, or liabilities" as given, with only the plans' failure conditional — section 6's realized-controls rule says the existence claim survives the surrounding "could materially harm" framing. The owner must weigh that the chunk begins mid-sentence and the referent of "such settlements, judgments" lies outside the passage, so the existence claim is inferred from anaphora rather than stated in view.
<details><summary>chunk text (2550 chars)</summary>

```
of this report, we have certain financial protections pursuant to the respective retrospective responsibility plans. The two retrospective responsibility plans are different in the protections they provide and the mechanisms by which we are protected. The failure of one or both of the retrospective responsibility plans to adequately insulate us from the impact of such settlements, judgments, losses, or liabilities could materially harm our financial condition or cash flows, or even cause us to become insolvent.

The global payments space is intensely competitive. As technology evolves and consumer expectations change, new competitors or methods of payment emerge, and existing clients and competitors assume different roles. Our products compete with cash, checks, electronic payments, virtual currency payments, global or multi-regional networks, other domestic and closed-loop payments systems, digital wallets and alternative payments providers primarily focused on enabling payments through ecommerce and mobile channels. As the global payments space becomes more complex, we face increasing competition from our clients, other emerging payment providers such as fintechs, other digital payments, technology companies that have developed payments systems

enabled through online activity in ecommerce, social media, and mobile channels, other providers of new flows and value-added service offerings, as well as governments in a number of jurisdictions (e.g., Brazil and India) as discussed above, that are developing, supporting and/or operating national schemes, RTP networks and other payment platforms. For more information, please see

Our competitors may acquire, develop, or make better use of substantially better technology, have more widely adopted delivery channels, or have greater financial resources. They may offer more effective, innovative or a wider range of programs, products and services. They may use more effective advertising and marketing strategies that result in broader brand recognition and greater use, including with respect to issuance and merchant acceptance. They may also develop better security solutions or more favorable pricing arrangements. Moreover, even if we successfully adapt to technological change and the proliferation of alternative types of payment services by developing and offering our own services in these areas, such services may provide less favorable financial terms for us than we currently receive from VisaNet transactions, which could hurt our financial results and prospects.
```
</details>

### A8. `CHK-4da9940a27679b8d`  [pattern: pending-or-future-litigation-modality]
**Stored:** [["LEGAL_REGULATORY_ACTION", "HYPOTHETICAL"], ["SUPPLY_INPUT_CONSTRAINT", "HYPOTHETICAL"]]  
**Auditor:** [["LEGAL_REGULATORY_ACTION", "REALIZED"], ["SUPPLY_INPUT_CONSTRAINT", "HYPOTHETICAL"]]  
**Adjudicator (disagree, medium):** [["LEGAL_REGULATORY_ACTION", "REALIZED"], ["SUPPLY_INPUT_CONSTRAINT", "HYPOTHETICAL"]]
**Adjudicator brief:** The safe-harbor item "potential liability resulting from pending or future litigation, government investigations and other proceedings" uses "pending," which under the §6 realized-controls rule is an existence claim that survives forward-looking framing (only the "potential liability" is projected). The production-disruption item supports SUPPLY_INPUT_CONSTRAINT as hypothetical, and the bare "supply, transportation and labor constraints" item alone would fail mining depth. The disjunction "pending OR future" is what makes this close: it is weaker than the rubric's example "We are subject to pending investigations."
<details><summary>chunk text (1575 chars)</summary>

```
provincial, tribal, local and international HSE laws, regulations, and litigation (including related to climate change or remedial actions or assessments); legislative or regulatory changes, including changes relating to hydraulic fracturing or other oil and natural gas operations, retroactive royalty or production tax regimes, and deep-water and onshore drilling and permitting regulations; Occidental's ability to recognize intended benefits from its business strategies and initiatives, such as Occidental's low-carbon ventures businesses or announced greenhouse gas emissions reduction targets or net-zero goals; potential liability resulting from pending or future litigation, government investigations and other proceedings; disruption or interruption of production or manufacturing or facility damage due to accidents, chemical releases, labor unrest, weather, power outages, natural disasters, cyber-attacks, terrorist acts or insurgent activity; the scope and duration of global or regional health pandemics or epidemics and actions taken by government authorities and other third parties in connection therewith; the creditworthiness and performance of Occidental's counterparties, including financial institutions, operating partners and other parties; failure of risk management; Occidental’s ability to retain and hire key personnel; supply, transportation and labor constraints; reorganization or restructuring of Occidental’s operations; changes in state, federal or international tax rates; and actions by third parties that are beyond Occidental's control.
```
</details>

### A9. `CHK-fd959732ed4e547c`  [pattern: credit-loss-chargedown-as-impairment]
**Stored:** [["MARGIN_COST_PRESSURE", "REALIZED"]]  
**Auditor:** [] (no flags)  
**Adjudicator (disagree, medium):** [] (no flags)
**Adjudicator brief:** Nothing here asserts rising input, labor or operating costs, so the stored MARGIN_COST_PRESSURE has no textual basis; the passage is loan-accounting policy narrative ("charged down to the lower of amortized cost or the fair value of their underlying collateral", "modifications ... to borrowers experiencing financial difficulty"). The residual question is whether generic policy language that loans "have been charged down" counts as IMPAIRMENT_WRITEDOWN; I read it as policy mechanics with no specific recorded event, so no flag. The owner should decide whether bank credit-loss charge-downs fall inside the §4 impairment category at all.
<details><summary>chunk text (2548 chars)</summary>

```
% of the total revolving loans are senior lien loans; the remaining balance are junior lien loans. The lien position the Firm holds is considered in the Firm’s allowance for credit losses. Revolving loans that have been converted to term loans have higher delinquency rates than those that are still within the revolving period. That is primarily because the fully-amortizing payment that is generally required for those products is higher than the minimum payment options available for revolving loans within the revolving period.

ncludes collateral-dependent residential real estate loans that are charged down to the fair value of the underlying collateral less costs to sell. The Firm reports, in accordance with regulatory guidance, residential real estate loans that have been discharged under Chapter 7 bankruptcy and not reaffirmed by the borrower (“Chapter 7 loans”) as collateral-dependent nonaccrual loans, regardless of their delinquency status. At September 30, 2023, approximately

Generally, all consumer nonaccrual loans have an allowance. In accordance with regulatory guidance, certain nonaccrual loans that are considered collateral-dependent have been charged down to the lower of amortized cost or the fair value of their underlying collateral less costs to sell. If the value of the underlying collateral improves subsequent to charge down, the related allowance may be negative.

Represents the aggregate unpaid principal balance of loans divided by the estimated current property value. Current property values are estimated, at a minimum, quarterly, based on home valuation models using nationally recognized home price index valuation estimates incorporating actual data to the extent available and forecasted data where actual data is not available. Current estimated combined LTV for junior lien home equity loans considers all available lien positions, as well as unused lines, related to the property.

The Firm grants certain modifications of residential real estate loans to borrowers experiencing financial difficulty, which effective January 1, 2023, are reported as FDMs. The Firm's proprietary modification programs as well as government programs, including U.S. GSE programs, that generally provide various modifications to borrowers experiencing financial difficulty including, but not limited to, interest rate reductions, term extensions, other-than-insignificant payment delay and principal forgiveness that would otherwise have been required under the terms of the original agreement, are considered FDMs.
```
</details>

### A10. `CHK-87d7f6be8a95c376`  [pattern: compliance-cost-double-label-with-legal]
**Stored:** [["LEGAL_REGULATORY_ACTION", "HYPOTHETICAL"], ["MARGIN_COST_PRESSURE", "HYPOTHETICAL"]]  
**Auditor:** [["LEGAL_REGULATORY_ACTION", "REALIZED"], ["SUPPLY_INPUT_CONSTRAINT", "HYPOTHETICAL"]]  
**Adjudicator (disagree, medium):** [["LEGAL_REGULATORY_ACTION", "REALIZED"], ["MARGIN_COST_PRESSURE", "REALIZED"], ["SUPPLY_INPUT_CONSTRAINT", "HYPOTHETICAL"]]
**Adjudicator brief:** "rising climate change concerns have led to additional regulation ... that have increased ... the operating costs" is an occurrence claim, so LEGAL_REGULATORY_ACTION is REALIZED under §6, and the same sentence explicitly states an already-incurred operating-cost increase, which §4 says should be labeled alongside the causal category (the redirect in the disambiguation note only covers supply and tariff causes). Supplier language ("the failure to obtain raw materials at reasonable prices ... could expose us to costs") is a standalone but conditional supply assertion. My set matches neither rater; the owner should rule once on whether regulation-driven compliance costs get a separate MARGIN_COST_PRESSURE flag.
<details><summary>chunk text (3440 chars)</summary>

```
If Group Inc.’s proposed resolution strategy were not successful, Group Inc.’s financial condition would be adversely impacted and Group Inc.’s security holders, including debtholders, may as a consequence be in a worse position than if the strategy had not been implemented. In all cases, any payments to debtholders are dependent on our ability to make such payments and are therefore subject to our credit risk.

As a result of our recovery and resolution planning processes, including incorporating feedback from our regulators, we may incur increased operational, funding or other costs and face limitations on our ability to structure our internal organization or engage in internal or external activities in a manner that we may otherwise deem most operationally efficient.

As part of our commodities business, we purchase and sell certain physical commodities, arrange for their storage and transport, and engage in market making of commodities. The commodities involved in these activities may include crude oil, refined oil products, natural gas, liquefied natural gas, electric power, agricultural products, metals (base and precious), minerals (including unenriched uranium), emission credits, coal, freight and related products and indices.

These activities subject us and/or the entities in which we invest to extensive and evolving federal, state and local energy, environmental, antitrust and other governmental laws and regulations worldwide, including environmental laws and regulations relating to, among others, air quality, water quality, waste management, transportation of hazardous substances, natural resources, site remediation and health and safety. Additionally, rising climate change concerns have led to additional regulation, regulatory scrutiny and disclosure obligations that have increased and could further increase the operating costs and could adversely affect the profitability of certain of our investments and activities.

There may be substantial costs in complying with current or future laws and regulations relating to our commodities-related activities and investments. Compliance with these laws and regulations requires significant commitments of capital toward environmental monitoring, renovation of storage facilities or transport vessels, payment of emission fees and carbon or other taxes, and application for, and holding of, permits and licenses.

Commodities involved in our intermediation activities and investments are also subject to the risk of unforeseen or catastrophic events, which are likely to be outside of our control, including those arising from the breakdown or failure of transport vessels, storage facilities or other equipment or processes or other mechanical malfunctions, fires, leaks, spills or release of hazardous substances, performance below expected levels of output or efficiency, terrorist attacks, extreme weather events or other natural disasters or other hostile or catastrophic events. In addition, we rely on third-party suppliers or service providers to perform their contractual obligations and any failure on their part, including the failure to obtain raw materials at reasonable prices or to safely transport or store commodities, could expose us to costs or losses. Also, while we seek to insure against potential risks, we do not have insurance to cover some of these risks and the insurance that we have may be inadequate to cover our losses.
```
</details>

### A11. `CHK-6e267dc8121bfffd`  [pattern: expense-variance-narrative-as-margin-cost-pressure]
**Stored:** [["MARGIN_COST_PRESSURE", "REALIZED"]]  
**Auditor:** [] (no flags)  
**Adjudicator (disagree, low):** [] (no flags)
**Adjudicator brief:** Most expense movement here is growth- or one-off-driven ("a higher number of employees and compensation focused on areas that will drive higher long-term growth", "severance costs ... to realign our organizational structure"), which is not the cost inflation §4 describes, and no margin compression is asserted. But the passage does say G&A "increased ... primarily due to higher usage of travel related card benefits and higher indirect taxes," a realized operating-cost increase, so the stored flag is not obviously wrong. The owner should rule once on whether routine expense-variance narrative without margin framing earns MARGIN_COST_PRESSURE.
<details><summary>chunk text (2548 chars)</summary>

```
Service revenue in a given quarter is primarily assessed based on nominal payments volume in the prior quarter. Therefore, service revenue reported for the three and six months ended March 31, 2025 and 2024, respectively, was based on nominal payments volume reported by our financial institution clients for the three and six months ended December 31, 2024 and 2023, respectively. On occasion, previously presented volume information may be updated. Prior period updates are not material.

Our net revenue is impacted by the overall strengthening or weakening of the U.S. dollar as payments volume and related revenue denominated in local currencies are converted to U.S. dollars. For the three and six months ended March 31, 2025, exchange rate movements lowered our net revenue growth by approximately two percentage points and one percentage point, respectively.

increased over the three and six-month prior-year comparable periods primarily due to growth in payments volume. The amount of client incentives we record in future periods will vary based on changes in performance expectations, actual client performance, amendments to existing contracts or the execution of new contracts.

For the three months ended March 31, 2025 and 2024, revenue from value-added services was $2.6 billion and $2.1 billion, respectively. For the six months ended March 31, 2025 and 2024, revenue from value-added services was $5.0 billion and $4.2 billion, respectively. Value-added services revenue increased 23% and 20% over the three and six-month prior-year comparable periods, respectively, primarily due to growth in issuing solutions, advisory and other services and acceptance solutions.

increased over the three and six-month prior-year comparable periods primarily due to a higher number of employees and compensation focused on areas that will drive higher long-term growth, including acquisitions. The increase over the six-month prior-year comparable period was also due to severance costs in the current period to realign our organizational structure.

decreased over the three-month prior-year comparable period primarily due to the absence of lease consolidation costs and favorable foreign currency fluctuations, partially offset by higher usage of travel related card benefits and higher indirect taxes. General and administrative expenses increased over the six-month prior-year comparable period primarily due to higher usage of travel related card benefits and higher indirect taxes, partially offset by lower lease consolidation costs.
```
</details>

### A12. `CHK-f09548e1be417f33`  [pattern: product-approval-decisions-as-legal-regulatory-action]
**Stored:** [["LEGAL_REGULATORY_ACTION", "HYPOTHETICAL"]]  
**Auditor:** [] (no flags)  
**Adjudicator (disagree, medium):** [] (no flags)
**Adjudicator brief:** The list is R&D, trial-data and business-development uncertainty ("the possibility of unfavorable pre-clinical and clinical trial results", "regulatory decisions impacting labeling, approval or authorization"); §4's LEGAL_REGULATORY_ACTION covers litigation, investigations, enforcement, fines, consent decrees, or new requirements creating compliance burden, none of which is asserted here. The owner should weigh whether ordinary product-approval/labeling decisions count as regulatory action at all, since that reading recurs across pharma chunks.
<details><summary>chunk text (2768 chars)</summary>

```
the outcome of research and development (R&D) activities, including the ability to meet anticipated pre-clinical or clinical endpoints, commencement and/or completion dates for our pre-clinical or clinical trials, regulatory submission dates, and/or regulatory approval and/or launch dates; the possibility of unfavorable pre-clinical and clinical trial results, including the possibility of unfavorable new pre-clinical or clinical data and further analyses of existing pre-clinical or clinical data; risks associated with preliminary, early stage or interim data; the risk that pre-clinical and clinical trial data are subject to differing interpretations and assessments, including during the peer review/publication process, in the scientific community generally, and by regulatory authorities; whether and when additional data from our pipeline programs will be published in scientific journal publications, and if so, when and with what modifications and interpretations; and uncertainties regarding the future development of our product candidates, including whether or when our product candidates will advance to future studies or phases of development or whether or when regulatory applications may be filed for any of our product candidates;

regulatory decisions impacting labeling, approval or authorization, including the scope of indicated patient populations, product dosage, manufacturing processes, safety and/or other matters, including decisions relating to emerging developments regarding potential product impurities; uncertainties regarding the ability to obtain or maintain, and the scope of, recommendations by technical or advisory committees, and the timing of, and ability to obtain, pricing approvals and product launches, all of which could impact the availability or commercial potential of our products and product candidates;

the success and impact of external business development activities, including the ability to identify and execute on potential business development opportunities; the ability to satisfy the conditions to closing of announced transactions in the anticipated time frame or at all; the ability to realize the anticipated benefits of any such transactions in the anticipated time frame or at all; the potential need for and impact of additional equity or debt financing to pursue these opportunities, which has in the past and could in the future result in

increased leverage and/or a downgrade of our credit ratings and could limit our ability to obtain future financing; challenges integrating the businesses and operations; disruption to business or operations relationships; risks related to growing revenues for certain acquired or partnered products; significant transaction costs; and unknown liabilities;
```
</details>

### A13. `CHK-72fe97f6760077fe`  [pattern: volume-decline-as-demand-weakness]
**Stored:** [] (no flags)  
**Auditor:** [["DEMAND_WEAKNESS", "REALIZED"]]  
**Adjudicator (disagree, medium):** [["DEMAND_WEAKNESS", "REALIZED"]]
**Adjudicator brief:** "lower revenues in advisory, reflecting a decline in completed mergers and acquisitions transactions" states an already-occurred decline in client transaction volume, which fits §4's "unfavorable volume trends" and is past-tense, so DEMAND_WEAKNESS / REALIZED; the stored empty set misses it. The overall "essentially unchanged" framing does not matter, since red flags are not sentiment. The owner should rule once on whether declining market/transaction volumes at a financial firm count as demand weakness.
<details><summary>chunk text (2570 chars)</summary>

```
Net revenues in the consolidated statements of earnings were $11.82 billion for the third quarter of 2023, essentially unchanged compared with the third quarter of 2022, reflecting significantly lower net interest income and lower commissions and fees, offset by higher market making revenues and investment management revenues.

Investment banking revenues in the consolidated statements of earnings were $1.56 billion for the third quarter of 2023, essentially unchanged compared with the third quarter of 2022, due to higher revenues in debt underwriting, primarily driven by leveraged finance activity, and higher revenues in equity underwriting, primarily from initial public offerings, offset by lower revenues in advisory, reflecting a decline in completed mergers and acquisitions transactions.

Investment management revenues in the consolidated statements of earnings were $2.41 billion for the third quarter of 2023, 6% higher than the third quarter of 2022, due to higher management and other fees, primarily reflecting the impact of higher average assets under supervision (AUS).

intermediation. The increase from financing activities reflected significantly higher revenues in equity financing products. The decrease from intermediation activities reflected significantly lower revenues in commodities, equity derivatives and currencies, partially offset by significantly improved results in mortgages and higher revenues in interest rate products

Other principal transactions revenues in the consolidated statements of earnings were $465 million for the third quarter of 2023, essentially unchanged compared with the third quarter of 2022, reflecting significantly lower net revenues from equity investments, largely offset by net gains from derivatives related to our borrowings and significantly improved results in relationship lending and acquisition financing activities.

Net interest income in the consolidated statements of earnings was $1.55 billion for the third quarter of 2023, 24% lower than the third quarter of 2022, reflecting a significant increase in interest expense primarily related to other interest-bearing liabilities, collateralized financings, deposits, and borrowings, each reflecting the impact of higher average interest rates. The increase in interest expense was largely offset by a significant increase in interest income primarily related to collateralized agreements, other interest-earning assets, deposits with banks and loans, each reflecting the impact of higher average interest rates. See “Statistical Disclosures
```
</details>

### A14. `CHK-b74c6da3ee7bf9cc`  [pattern: boilerplate-semicolon-enumeration-mining-depth]
**Stored:** [["LEGAL_REGULATORY_ACTION", "HYPOTHETICAL"]]  
**Auditor:** [] (no flags)  
**Adjudicator (disagree, low):** [] (no flags)
**Adjudicator brief:** The legal item sits in a semicolon boilerplate list ("significant adverse litigation or government action, including related to product liability claims") that names a risk type without any company-specific mechanism, which reads as the §4 mining-depth failure case rather than a standalone assertion. The close call is the neighboring item "product efficacy or safety concerns resulting in product recalls or regulatory action," which does supply a mechanism and could be argued to clear the bar. The owner should set the elaboration threshold for safe-harbor semicolon lists, since it recurs across many press-release chunks.
<details><summary>chunk text (3135 chars)</summary>

```
Significant innovation including approvals of INLEXZO for high-risk non-muscle invasive bladder cancer and TREMFYA subcutaneous in ulcerative colitis, submission of icotrokinra for plaque psoriasis, landmark data for RYBREVANT plus LAZCLUZE overall survival in non-small cell lung cancer, and DanGer Shock long-term survival benefit of Impella Heart Pump

– Johnson & Johnson (NYSE: JNJ) today announced results for third-quarter 2025. “Johnson & Johnson delivered another strong performance in the third quarter fueled by the depth and strength of our portfolio and significant progress across our pipeline,” said Joaquin Duato, Chairman and Chief Executive Officer, Johnson & Johnson. “With a sharpened focus on the six priority areas of Oncology, Immunology, Neuroscience, Cardiovascular, Surgery and Vision, Johnson & Johnson is in a new era of accelerated growth and innovation, with pioneering treatments that will continue to transform lives.”

Innovative Medicine worldwide operational sales grew 5.3%*, with net acquisitions and divestitures positively impacting growth by 1.6% due to CAPLYTA. Growth was primarily driven by DARZALEX, CARVYKTI, ERLEADA and RYBREVANT/LAZCLUZE in Oncology, TREMFYA and SIMPONI/SIMPONI ARIA in Immunology, and SPRAVATO in Neuroscience. Growth was partially offset by an approximate (1,070) basis points impact from STELARA in Immunology, as well as IMBRUVICA in Oncology.

This press release contains “forward-looking statements” as defined in the Private Securities Litigation Reform Act of 1995 regarding, among other things: future operating and financial performance, product development, and market position and business strategy. The reader is cautioned not to rely on these forward-looking statements. These statements are based on current expectations of future events. If underlying assumptions prove inaccurate or known or unknown risks or uncertainties materialize, actual results could vary materially from the expectations and projections of Johnson & Johnson. Risks and uncertainties include, but are not limited to: economic factors, such as interest rate and currency exchange rate fluctuations or changes to applicable laws and regulations; competition, including technological advances, new products and patents attained by competitors; challenges inherent in new product research and development, including uncertainty of clinical success and obtaining regulatory approvals; uncertainty of commercial success for new and existing products; challenges to patents; the impact of patent expirations; the ability of the Company to successfully execute strategic plans, including restructuring plans; the impact of business combinations and divestitures; manufacturing difficulties or delays, internally or within the supply chain; product efficacy or safety concerns resulting in product recalls or regulatory action; significant adverse litigation or government action, including related to product liability claims; changes to applicable laws and regulations, including tax laws and global health care reforms; trends toward health care cost containment; changes in behavior and
```
</details>

### A15. `CHK-bed93e2ff380364c`  [pattern: cta-recycling-charge-not-impairment]
**Stored:** [["IMPAIRMENT_WRITEDOWN", "REALIZED"]]  
**Auditor:** [] (no flags)  
**Adjudicator (disagree, medium):** [] (no flags)
**Adjudicator brief:** The charge the stored label rests on is described as "a non-cash charge for accumulated foreign currency translation losses due to the substantial liquidation of operations in Argentina" — a recycling of translation losses, not an asset impairment, goodwill/inventory write-down, or restructuring charge "tied to asset value reduction" as §4 requires. Nothing else in the passage matches a category; "the decrease in net sales" is a bare mention with no demand or cost attribution. The owner should rule on whether currency-translation liquidation charges count as IMPAIRMENT_WRITEDOWN, as the same language recurs.
<details><summary>chunk text (2586 chars)</summary>

```
Operating margin increased 30 basis points to 26.7% due to the increase in gross margin and the decrease in SG&A as a percentage of net sales, as discussed above. Operating income increased $30 million, or 1%, to $5.8 billion for the quarter as the decrease in net sales was more than offset by the increase in operating margin, the components of which are discussed above.

Interest expense was $238 million for the quarter, an increase of $13 million versus the prior year period. Interest income was $135 million for the quarter, an increase of $7 million versus the prior year period. Other non-operating income/(expense) was $(554) million, which is a decrease of $686 million versus the prior year period due primarily to a non-cash charge for accumulated foreign currency translation losses due to the substantial liquidation of operations in Argentina.

The effective income tax rate for the three months ended September 30, 2024, was 22.4%, compared to 21.5% for the three months ended September 30, 2023. The increase in the effective tax rate was driven by a 300 basis-point increase due primarily to the charge for accumulated foreign currency translation losses due to the substantial liquidation of operations in Argentina, partially offset by a 160 basis-point decrease due to higher excess tax benefits of share-based compensation and a decrease driven by favorable geographic mix impacts.

Net earnings decreased $569 million, or 12%, to $4.0 billion due primarily to the decrease in other non-operating income/(expense) discussed above. Foreign exchange had a positive impact of approximately $61 million on net earnings for the quarter, including both transactional and translational impacts from converting earnings from foreign subsidiaries to U.S. dollars. Net earnings attributable to Procter & Gamble decreased $562 million, or 12%, to $4.0 billion for the quarter. Diluted EPS decreased 12% to $1.61 versus the prior year period due to the decrease in net earnings.

The following discussion provides a review of results by reportable business segment. Analysis of the results for the three months ended September 30, 2024, is provided based on a comparison to the three months ended September 30, 2023. The primary financial measures used to evaluate segment performance are net sales and net earnings. The table below provides supplemental information on net sales, earnings before income taxes and net earnings by reportable business segment for the three months ended September 30, 2024, versus the comparable prior year period (dollar amounts in millions):
```
</details>

### A16. `CHK-709fca1998a1ccc7`  [pattern: compliance-cost-double-label-with-legal]
**Stored:** [["IMPAIRMENT_WRITEDOWN", "HYPOTHETICAL"], ["LEGAL_REGULATORY_ACTION", "HYPOTHETICAL"], ["MARGIN_COST_PRESSURE", "HYPOTHETICAL"]]  
**Auditor:** [["DEMAND_WEAKNESS", "HYPOTHETICAL"], ["IMPAIRMENT_WRITEDOWN", "HYPOTHETICAL"], ["LEGAL_REGULATORY_ACTION", "REALIZED"]]  
**Adjudicator (disagree, medium):** [["DEMAND_WEAKNESS", "HYPOTHETICAL"], ["IMPAIRMENT_WRITEDOWN", "HYPOTHETICAL"], ["LEGAL_REGULATORY_ACTION", "REALIZED"], ["MARGIN_COST_PRESSURE", "REALIZED"]]
**Adjudicator brief:** "The Company's operations, properties and assets are subject to extensive health, safety and environmental laws and regulations" whose "[c]osts of compliance ... are significant" is an existence claim, so §6's realized-controls rule makes both the legal flag and the stated operating-cost burden REALIZED, not hypothetical. "decrease demand for the Company's oil, NGL, natural gas and other products" is a standalone conditional demand assertion the stored label misses, and "potentially resulting in impairments" supports the hypothetical impairment flag. My set matches neither rater, and it turns on the same compliance-cost double-label question as the other environmental chunks.
<details><summary>chunk text (3638 chars)</summary>

```
The Company conducts offshore operations in the Gulf of America and international locations through certain subsidiaries. Offshore operations are vulnerable to unique risks in addition to those listed above, including deep-water technical complexity, logistical and security challenges, a limited number of partners available to participate in projects and more stringent permitting and regulatory requirements. The Company may also face longer recovery times and higher remediation costs for offshore incidents compared to onshore operations. Deep-water projects (greater than 1,000 feet) are especially challenging and costly due to limited infrastructure and support services, often requiring more time between discovery and ability to market production, thereby increasing commercial and operational risk. These factors can increase the potential for and impact of catastrophic events, which could result in significant operational disruption, increased costs or loss of production and could have a material adverse effect on the Company’s financial condition, results of operations, cash flows and reserves.

The Company’s operations, properties and assets are subject to extensive health, safety and environmental laws and regulations, including those governing drilling, completions, production, GHG and other air emissions, water use and discharges, waste management, environmental remediation and protection of wildlife and ecosystems. The requirements of these laws and regulations are complex, stringent and expensive to implement. Costs of compliance with these laws and regulations are significant and can be unpredictable and may require significant capital investment and operating costs, and violations can result in penalties, operational restrictions or cessation of operations in affected areas. In addition, evolving climate-related policies, such as those related to CCUS, monitoring, reporting or control of methane and other GHG emissions, and carbon pricing and associated allowances, credits, taxes, fees or incentives, as well as recent legislative developments such as the OBBBA, could increase costs or reduce demand for certain products. Some of these laws and regulations provide for strict, joint and several liability, and the Company could be liable for the actions of others, including prior owners or operators of properties or other assets.

Collectively, international, federal, state and local government and private actions relating to air emissions may require the Company to incur additional operating and maintenance costs, including for service providers and costs to purchase, operate and maintain emissions control systems, acquire emission allowances or credits, pay taxes or fees for methane and other GHG emissions or comply with new regulatory or reporting requirements. They could also affect permitting or other regulatory approvals or prevent the Company from conducting oil and gas development activities in certain areas. In addition, they could promote the use of alternative sources of energy and thereby decrease demand for the Company’s oil, NGL, natural gas and other products. Future legislation or regulatory or market changes could also increase the cost of consuming or reduce demand for the Company’s products and thereby lower the value of the Company’s reserves, potentially resulting in impairments. Consequently, actions designed to reduce GHG or other air emissions could cause the Company to make changes with respect to its business plan, operations or assets that may have an adverse effect on its financial condition, results of operations, cash flows and reserves.
```
</details>

### A17. `CHK-e922e4f7a10dad00`  [pattern: compliance-cost-double-label-with-legal]
**Stored:** [["LEGAL_REGULATORY_ACTION", "REALIZED"], ["MARGIN_COST_PRESSURE", "REALIZED"]]  
**Auditor:** [["LEGAL_REGULATORY_ACTION", "REALIZED"]]  
**Adjudicator (agree, medium):** null
**Adjudicator brief:** "We have incurred and will continue to incur substantial capital, operating and maintenance, and remediation expenditures as a result of these laws and regulations" is both a realized regulatory-burden claim and an explicit realized operating-cost claim, so the stored two-flag set is right and the auditor's decision to fold cost into the legal category is not supported by §4, which says the categories are not mutually exclusive and only redirects when the cause is supply or tariffs. "[I]n 2024, New York and Vermont passed legislation" independently confirms the realized legal modality. The owner should rule once on the compliance-cost double-label so this chunk and the other environmental chunks resolve consistently.
<details><summary>chunk text (2566 chars)</summary>

```
Any of these factors, or other cascading effects of such factors, could materially increase our costs; negatively impact our revenues or ability to implement and advance our Climate-related Risk Strategy; and damage our financial condition, results of operations, cash flows and liquidity position. The full extent and duration of any such impacts cannot be predicted at this time because of the lack of certainty surrounding their sources, causes and outcomes.

We have incurred and will continue to incur substantial capital, operating and maintenance, and remediation expenditures as a result of these laws and regulations. In addition, to the extent these expenditures are assumed by a buyer as a result of a disposition, it may result in our incurring substantial costs if the buyer is unable to satisfy these obligations. Any actual or perceived failure by us to comply with existing or future laws, regulations and other requirements could result in administrative or civil penalties, criminal fines, other enforcement actions or third-party litigation against us. To the extent these expenditures, as with all costs, are not ultimately reflected in the prices of our products, our business, financial condition, results of operations and cash flows in future periods, as well as our ability to implement and advance our Climate-related Risk Strategy could be adversely affected.

Continuing political and societal attention to the issue of global climate change has resulted in both existing and pending international agreements and national, regional or local legislation and regulatory measures to limit GHG emissions, such as cap and trade regimes, specific emission standards, carbon taxes, restrictive permitting, increased fuel efficiency standards and incentives or mandates for renewable and alternative energy. Although we may support the intent of legislative and regulatory measures aimed at addressing climate-related risks, the specifics of how and when they are enacted could result in a material adverse effect to our business, financial condition, results of operations and cash flows in future periods as well as our ability to implement and advance our Climate-related Risk Strategy.

For example, in 2024, New York and Vermont passed legislation seeking to hold certain energy companies financially responsible for state climate change mitigation and adaptation measures, following the "polluter pays" model of existing Superfund laws. This responsibility may include paying into a fund for infrastructure repairs and recovery from extreme
```
</details>

### A18. `CHK-10fa0f637d2af709`  [pattern: credit-loss-chargedown-as-impairment]
**Stored:** [] (no flags)  
**Auditor:** [["IMPAIRMENT_WRITEDOWN", "REALIZED"]]  
**Adjudicator (disagree, low):** [["IMPAIRMENT_WRITEDOWN", "REALIZED"]]
**Adjudicator brief:** The text states a specific, quantified, dated event — "a $469 million write-off during 2017 as a result of the political and economic conditions in Venezuela" — plus "Allowances have been recorded for receivables believed to be uncollectible," both past tense, so under "label only what the text says" a realized write-down is asserted even though the sentence's rhetorical thrust is that write-offs have been rare. The doubt is category scope: §4's examples are goodwill, inventory and long-lived assets, and a receivable write-off may not belong. The owner should rule on receivable/credit write-offs as IMPAIRMENT_WRITEDOWN.
<details><summary>chunk text (2805 chars)</summary>

```
As of December 31, 2024, SLB had $4.67 billion of cash and short-term investments and committed credit facility agreements with commercial banks aggregating $5.0 billion, all of which was available. SLB believes these amounts, along with cash generated by ongoing operations, will be sufficient to meet future business requirements for the next 12 months and beyond.

On October 17, 2024, SLB entered into a definitive agreement to sell its interest in the Palliser APS project in Canada. Under the terms of the agreement, SLB will receive cash proceeds of approximately $430 million, subject to closing adjustments that are typical for such a transaction. The transaction, which is subject to regulatory approval and other customary closing conditions, is expected to close in the first quarter of 2025. SLB recorded revenue of approximately $0.5 billion relating to this project during 2024.

The preparation of financial statements and related disclosures in conformity with accounting principles generally accepted in the United States requires SLB to make estimates and assumptions that affect the reported amounts of assets and liabilities, the disclosure of contingent liabilities and the reported amounts of revenue and expenses. The following accounting policies involve “critical accounting

SLB maintains an allowance for doubtful accounts in order to record accounts receivable at their net realizable value. Judgment is involved in recording and making adjustments to this reserve. Allowances have been recorded for receivables believed to be uncollectible, including amounts for the resolution of potential credit and other collection issues such as disputed invoices. Adjustments to the allowance may be required in future periods depending on how such potential issues are resolved, or if the financial condition of SLB’s customers were to deteriorate resulting in an impairment of their ability to make payments.

As a large multinational company with a long history of operating in a cyclical industry, SLB has extensive experience in working with its customers during difficult times to manage its accounts receivable. During weak economic environments or when there is an extended period of weakness in oil and gas prices, SLB typically experiences delays in the payment of its receivables. However, except for a $469 million write-off during 2017 as a result of the political and economic conditions in Venezuela, SLB has not historically had material write-offs due to uncollectible accounts receivable. SLB has a global footprint in more than 100 countries. As of December 31, 2024, three of those countries individually accounted for greater than 5% of SLB’s net accounts receivable balance, of which only one (the United States) accounted for greater than 10% of such receivables.
```
</details>

### A19. `CHK-7edd7aedaa803873`  [pattern: subject-to-ambient-trade-conditions-modality]
**Stored:** [["MARGIN_COST_PRESSURE", "REALIZED"], ["TRADE_POLICY_EXPOSURE", "HYPOTHETICAL"]]  
**Auditor:** [["MARGIN_COST_PRESSURE", "REALIZED"], ["TRADE_POLICY_EXPOSURE", "REALIZED"]]  
**Adjudicator (agree, low):** null
**Adjudicator brief:** MARGIN_COST_PRESSURE / REALIZED is agreed on both sides ("partially offset by higher input costs"), so the whole dispute is the trade modality. "[T]hey are subject to global trade dynamics that may impact certain components of the company's cost structure" names no specific measure, effective date or imposed tariff — unlike §6's realized examples (pending investigations, regulation already in effect) — so I read it as ambient risk framing with a projected effect, which keeps HYPOTHETICAL. The present-tense "are subject to" plus "At this time, the company expects the impact to be manageable" pull the other way, and this is close enough that the owner should set the rule for "subject to [ambient trade conditions]" phrasing.
<details><summary>chunk text (2754 chars)</summary>

```
Operating income grew 3%, which included items impacting comparability and a 4-point currency headwind. Comparable currency neutral operating income (non-GAAP) grew 7%, primarily driven by organic revenue (non-GAAP) growth and the timing of operating expenses, partially offset by higher input costs and marketing investments.

For comparable net revenues (non-GAAP), the company expects a 1% to 2% currency headwind based on the current rates and including the impact of hedged positions, in addition to an approximate 1% headwind from acquisitions, divestitures and structural changes. — Updated

The company’s operations are primarily local, however, they are subject to global trade dynamics that may impact certain components of the company’s cost structure across its markets. At this time, the company expects the impact to be manageable. — No Update

Comparable EPS (non-GAAP) percentage growth is expected to include an approximate 5% currency headwind based on the current rates and including the impact of hedged positions, in addition to an approximate 1% headwind from acquisitions, divestitures and structural changes. — Updated

The company is hosting a conference call with investors and analysts to discuss second quarter 2025 operating results today, July 22, 2025, at 8:30 a.m. ET. The company invites participants to listen to a live webcast of the conference call on the company’s website, http://www.coca-colacompany.com, in the “Investors” section. An audio replay in downloadable digital format and a transcript of the call will be available on the website within 24 hours following the call. Further, the “Investors” section of the website includes certain supplemental information and a reconciliation of non-GAAP financial measures to the company’s results as reported under GAAP, which may be used during the call when discussing financial results.

During the three months ended June 27, 2025, intersegment revenues were $168 million for Europe, Middle East & Africa, $1 million for North America, $108 million for Asia Pacific and $2 million for Bottling Investments. During the three months ended June 28, 2024, intersegment revenues were $155 million for Europe, Middle East & Africa, $4 million for North America, $126 million for Asia Pacific and $2 million for Bottling Investments.

During the six months ended June 27, 2025, intersegment revenues were $344 million for Europe, Middle East & Africa, $3 million for North America, $204 million for Asia Pacific and $4 million for Bottling Investments. During the six months ended June 28, 2024, intersegment revenues were $352 million for Europe, Middle East & Africa, $6 million for North America, $342 million for Asia Pacific and $4 million for Bottling Investments.
```
</details>

### A20. `CHK-e7d89e372a854602`  [pattern: safe-harbor-noun-list-mining-depth]
**Stored:** [["LEGAL_REGULATORY_ACTION", "HYPOTHETICAL"], ["MARGIN_COST_PRESSURE", "HYPOTHETICAL"], ["TRADE_POLICY_EXPOSURE", "HYPOTHETICAL"]]  
**Auditor:** [] (no flags)  
**Adjudicator (disagree, low):** [] (no flags)
**Adjudicator brief:** The passage is a single safe-harbor factor enumeration — 'These include global or regional changes in the supply and demand for oil ...; changes in law, regulations, taxes, trade sanctions, or policies ...' — the §4 mining-depth rule's paradigm list of nouns rather than assertions, and 'trade sanctions' in particular is a bare noun, so TRADE_POLICY_EXPOSURE cannot survive on any reading. Stored is wrong either way: if the list flags nothing, all three entries go; if the named already-existing regimes ('the punitive European taxes on the oil and gas sector', 'standards imposed by various jurisdictions') are what earns the legal flag, then §6's realized-controls rule makes that flag REALIZED, never the stored HYPOTHETICAL.
<details><summary>chunk text (4858 chars)</summary>

```
Statements related to future events; projections; descriptions of strategic, operating, and financial plans and objectives; statements of future ambitions and plans; and other statements of future events or conditions are forward-looking statements. Similarly, discussion of roadmaps or future plans related to carbon capture, transportation and storage, biofuel, hydrogen, lithium and other future plans to reduce emissions and emission intensity of ExxonMobil, its affiliates, companies it is seeking to acquire and third parties are dependent on future market factors, such as continued technological progress, policy support and timely rule-making and permitting, and represent forward-looking statements.

Actual future results, including financial and operating performance; potential earnings, cash flow, dividends or shareholder returns, including the timing and amounts of share repurchases; total capital expenditures and mix, including allocations of capital to low carbon investments; realization and maintenance of structural cost reductions and efficiency gains, including the ability to offset inflationary pressure; plans to reduce future emissions and emissions intensity, including ambitions to reach Scope 1 and Scope 2 net zero from operated assets by 2050, to reach Scope 1 and 2 net zero in Upstream Permian Basin unconventional operated assets by 2030 and in Pioneer Permian assets by 2035, to eliminate routine flaring in-line with World Bank Zero Routine Flaring, and to reach near-zero methane emissions from operated assets and other methane initiatives; meeting ExxonMobil’s divestment and start-up plans, and associated project plans as well as technology advances, including the timing and outcome of projects to capture, transport and store CO2, produce hydrogen, produce biofuels, produce lithium, and use plastic waste as feedstock for advanced recycling; timely granting of governmental permits and certifications; future debt levels and credit ratings; business and project plans, timing, costs, capacities and profitability; resource recoveries and production rates; and planned Denbury and Pioneer integrated benefits, could differ materially due to a number of factors.

These include global or regional changes in the supply and demand for oil, natural gas, petrochemicals, and feedstocks and other market factors, economic conditions and seasonal fluctuations that impact prices and differentials for our products; changes in law, regulations, taxes, trade sanctions, or policies, such as government policies supporting lower carbon investment opportunities such as the U.S. Inflation Reduction Act and the ability for projects to qualify for the financial incentives available thereunder, the punitive European taxes on the oil and gas sector and unequal support for different technological methods of emissions reduction or evolving, ambiguous and unharmonized standards imposed by various jurisdictions related to sustainability and GHG reporting; variable impacts of trading activities on our margins and results each quarter; actions of competitors and commercial counterparties; the outcome of commercial negotiations, including final agreed terms and conditions; the ability to access debt markets on favorable terms or at all; the occurrence, pace, rate of recovery and effects of public health crises, including the responses from governments; reservoir performance, including variability and timing factors applicable to unconventional resources; the level and outcome of exploration projects and decisions to invest in future reserves; timely completion of development and other construction projects; final management approval of future projects and any changes in the scope, terms, costs or assumptions of such projects as approved; the actions of government or other actors against our core business activities and acquisitions, divestitures or financing opportunities; war, civil unrest, attacks against the company or industry, and other geopolitical or security disturbances, including disruption of land or sea transportation routes; expropriations, seizure, or capacity, insurance, shipping or export limitations imposed by governments or laws; opportunities for potential acquisitions, investments or divestments and satisfaction of applicable conditions to closing, including timely regulatory approvals; the capture of efficiencies within and between business lines and the ability to maintain near-term cost reductions as ongoing efficiencies; unforeseen technical or operating difficulties and unplanned maintenance; the development and competitiveness of alternative energy and emission reduction technologies; the results of research programs and the ability to bring new technologies to commercial scale on a cost-competitive basis; and other factors discussed under "Item 1A. Risk Factors."
```
</details>

### A21. `CHK-d8f2f91c7bbfa2cc`  [pattern: segment-decline-in-positive-mda]
**Stored:** [] (no flags)  
**Auditor:** [["DEMAND_WEAKNESS", "REALIZED"]]  
**Adjudicator (disagree, medium):** [["DEMAND_WEAKNESS", "REALIZED"]]
**Adjudicator brief:** 'Professional Visualization revenue was down 24% from a year ago' and 'The year-on-year decrease primarily reflects lower sell-in to partners' is a past-tense, already-occurred decline in partner orders, and §4's DEMAND_WEAKNESS lists 'declining orders/bookings, unfavorable volume trends' disjunctively — it does not require the cause to be end-demand deterioration. Red flags are a presence-based multi-label field (§4), not a predominant-tone judgment like sentiment, so the strong Data Center demand described elsewhere in the same passage does not cancel the match.
<details><summary>chunk text (2417 chars)</summary>

```
We specialize in markets where our computing platforms can provide tremendous acceleration for applications. These platforms incorporate processors, interconnects, software, algorithms, systems, and services to deliver unique value. Our platforms address four large markets where our expertise is critical: Data Center, Gaming, Professional Visualization, and Automotive.

Data Center revenue was up 171% from a year ago and up 141% sequentially, led by CSPs and large consumer internet companies. Strong demand for the NVIDIA HGX platform based on our Hopper and Ampere GPU architectures was primarily driven by the development of large language models and generative AI. Data Center Compute grew 195% from a year ago and 157% sequentially, largely reflecting the strong ramp of our Hopper-based HGX platform. Networking was up 94% from a year ago and up 85% sequentially, primarily on strong growth in InfiniBand infrastructure to support our HGX platform. In the second quarter of fiscal year 2024, CSPs represented slightly more than half of our estimated Data Center end demand, with large consumer internet companies being the next largest end demand, followed by enterprise and high performance computing.

Professional Visualization revenue was down 24% from a year ago and up 28% sequentially. The year-on-year decrease primarily reflects lower sell-in to partners following normalization of channel inventory levels. The sequential increase was primarily due to stronger enterprise workstation demand and the ramp of NVIDIA RTX products based on the Ada Lovelace Architecture.

Data Center revenue for the second quarter of fiscal year 2024 was $10.32 billion, up 171% from a year ago. We announced that the NVIDIA GH200 Grace Hopper Superchip is available in the third quarter of fiscal year 2024; announced the NVIDIA L40S GPU - a universal data center processor for compute-intensive applications, including AI training and inference, is available now; unveiled the NVIDIA MGX server reference design; announced NVIDIA Spectrum-X, an accelerated networking platform for AI; and partnered with a

Gaming revenue for the second quarter of fiscal year 2024 was $2.49 billion, up 22% from a year ago. We began shipping the GeForce RTX 4060 family of GPUs; and announced NVIDIA Avatar Cloud Engine for Games, a custom AI model foundry service using AI-powered natural language interactions to transform games.
```
</details>

### A22. `CHK-a1853548628ae483`  [pattern: safe-harbor-noun-list-mining-depth]
**Stored:** [["LEGAL_REGULATORY_ACTION", "HYPOTHETICAL"], ["SUPPLY_INPUT_CONSTRAINT", "HYPOTHETICAL"]]  
**Auditor:** [] (no flags)  
**Adjudicator (disagree, low):** [] (no flags)
**Adjudicator brief:** The entire passage is a semicolon-separated cautionary noun list ('potential liability resulting from pending or future litigation, government investigations and other proceedings; ... supply, transportation and labor constraints; ... changes in state, federal or international tax rates'), which the §4 mining-depth rule treats as nouns rather than assertions about this company. Stored fails under either reading: if the list flags nothing, both entries go; if 'potential liability resulting from pending ... litigation' does clear the bar, then 'pending' is an existence claim and §6's realized-controls rule makes it REALIZED, not the stored HYPOTHETICAL.
<details><summary>chunk text (1003 chars)</summary>

```
emissions reduction targets or net-zero goals; potential liability resulting from pending or future litigation, government investigations and other proceedings; disruption or interruption of production or manufacturing or facility damage due to accidents, chemical releases, labor unrest, weather, power outages, natural disasters, cyber-attacks, terrorist acts or insurgent activity; the scope and duration of global or regional health pandemics or epidemics and actions taken by government authorities and other third parties in connection therewith; the creditworthiness and performance of Occidental's counterparties, including financial institutions, operating partners and other parties; failure of risk management; Occidental’s ability to retain and hire key personnel; supply, transportation and labor constraints; reorganization or restructuring of Occidental’s operations; changes in state, federal or international tax rates; and actions by third parties that are beyond Occidental's control.
```
</details>


## PART B — the 20-row S8 probe of the UNCONTESTED set (rule each: AGREE / OVERTURN vs the stored label)

These 20 rows are where auditor and teacher AGREED. If you overturn >=2, the pre-committed escalation fires: all 109 uncontested rows get adjudicated once (no new chunks).

### B1. `CHK-0884ab0ec3a75518`
**Stored (= auditor-agreed):** [] (no flags)
<details><summary>chunk text (3429 chars)</summary>

```
First quarter 2026 financial results were impacted by six additional days as compared to first quarter 2025, and fourth quarter 2026 financial results will be impacted by six fewer days as compared to fourth quarter 2025. Unit case volume results for the quarters are not impacted by the variances in days due to the average daily sales computation referenced above.

The company is hosting a conference call with investors and analysts to discuss first quarter 2026 operating results today, April 28, 2026, at 8:30 a.m. ET. The company invites participants to listen to a live webcast of the conference call on the company’s website, http://www.coca-colacompany.com, in the “Investors” section. An audio replay in downloadable digital format and a transcript of the call will be available on the website within 24 hours following the call. Further, the “Investors” section of the website includes certain supplemental information and a reconciliation of non-GAAP financial measures to the company’s results as reported under GAAP, which may be used during the call when discussing financial results.

During the three months ended April 3, 2026, intersegment revenues were $205 million for EMEA, $2 million for North America, $82 million for Asia Pacific and $2 million for Bottling Investments. During the three months ended March 28, 2025, intersegment revenues were $176 million for EMEA, $2 million for North America, $96 million for Asia Pacific and $2 million for Bottling Investments.

The company reports its financial results in accordance with accounting principles generally accepted in the United States (“GAAP” or referred to herein as “reported”). To supplement our consolidated financial statements reported on a GAAP basis, we provide the following non-GAAP financial measures: “comparable net revenues,” “comparable currency neutral net revenues,” “organic revenues,” “comparable operating margin,” “underlying operating margin,” “comparable operating income,” “comparable currency neutral operating income,” “comparable EPS,” “comparable currency neutral EPS,” “comparable currency neutral EPS excluding acquisitions and divestitures,” “underlying effective tax rate” and “free cash flow,” each of which is defined below. Management believes these non-GAAP financial measures provide investors with additional meaningful financial information that should be considered when assessing our underlying business performance and trends. Further, management believes these non-GAAP financial measures also enhance investors’ ability to compare period-to-period financial results. Non-GAAP financial measures should be viewed in addition to, and not as an alternative for, the company’s reported results prepared in accordance with GAAP. Our non-GAAP financial measures do not represent a comprehensive basis of accounting. Therefore, our non-GAAP financial measures may not be comparable to similarly titled measures reported by other companies. Reconciliations of each of these non-GAAP financial measures to GAAP information are also included below. Management uses these non-GAAP financial measures in making financial, operating, compensation and planning decisions and in evaluating the company’s performance. Disclosing these non-GAAP financial measures allows investors and management to view our operating results excluding the impact of items that are not reflective of the underlying operating performance.
```
</details>

### B2. `CHK-12a3b9d1fabc91c4`
**Stored (= auditor-agreed):** [] (no flags)
<details><summary>chunk text (724 chars)</summary>

```
quarter of 2024, compared with a net benefit of $171 million for the first quarter of 2023 and net provisions of $577 million for the fourth quarter of 2023. Provisions for the first quarter of 2024 reflected net provisions related to

financial results, outlook and related matters will be held at 9:30 am (ET). The call will be open to the public. Members of the public who would like to listen to the conference call should dial 1-800-289-0459 (in the U.S.) or 1-323-794-2095

(outside the U.S.) passcode number 7042022. The number should be dialed at least 10 minutes prior to the start of the conference call. The conference call will also be accessible as an audio webcast through the Investor Relations section of the
```
</details>

### B3. `CHK-305a101bf35c60e7`
**Stored (= auditor-agreed):** [] (no flags)
<details><summary>chunk text (3282 chars)</summary>

```
The Company’s reporting segments are aligned with its strategic priorities and reflect how management reviews and evaluates operating performance. Significant reportable segments include the United States ("U.S.") and International Operated Markets. In addition, there is the International Developmental Licensed Markets & Corporate segment, which includes the results of over 75 countries, as well as Corporate activities.

McDonald’s franchised restaurants are owned and operated under one of the following structures - conventional franchise, developmental license or affiliate. The optimal ownership structure for an individual restaurant, trading area or market (country) is based on a variety of factors, including the availability of individuals with entrepreneurial experience and financial resources, as well as the local legal and regulatory environment in critical areas such as property ownership and franchising. The business relationship between the Company and its independent franchisees is supported by adhering to standards and policies, including McDonald's Global Brand Standards, and is of fundamental importance to overall performance and to protecting the McDonald’s brand.

The Company is primarily a franchisor and believes franchising is paramount to delivering great-tasting food, locally relevant customer experiences and driving profitability. Franchising enables an individual to be their own employer and maintain control over all employment related matters, marketing and pricing decisions, while also benefiting from the strength of McDonald’s global brand, operating system and financial resources.

Directly operating McDonald’s restaurants contributes significantly to the Company's ability to act as a credible franchisor. One of the strengths of the franchising model is that the expertise from operating Company-owned restaurants allows McDonald’s to improve the operations and success of all restaurants while innovations from franchisees can be tested and, when viable, efficiently implemented across relevant restaurants. Having Company-owned and operated restaurants provides Company personnel with a venue for restaurant operations training experience. In addition, in our Company-owned and operated restaurants, and in collaboration with franchisees, the Company is able to further develop and refine operating standards, marketing concepts and product and pricing strategies that will ultimately benefit McDonald’s restaurants.

The Company’s revenues consist of sales by Company-operated restaurants and fees from franchised restaurants operated by conventional franchisees, developmental licensees and affiliates. Fees vary by type of site, amount of Company investment, if any, and local business conditions. These fees, along with occupancy and operating rights, are stipulated in franchise/license agreements that generally have 20-year terms. The Company’s Other revenues are comprised of fees paid by franchisees to recover a portion of costs incurred by the Company for various technology platforms, revenues from brand licensing arrangements to market and sell consumer packaged goods using the McDonald’s brand and, for periods prior to its sale on April 1, 2022, third-party revenues for the Company's Dynamic Yield business.
```
</details>

### B4. `CHK-30c5a4bf715d85f1`
**Stored (= auditor-agreed):** [] (no flags)
<details><summary>chunk text (2413 chars)</summary>

```
The fair value of derivative receivables reported on the Consolidated balance sheets was $54.9 billion and $70.9 billion at December 31, 2023 and 2022, respectively. The decrease was primarily as a result of market movements. Derivative receivables represent the fair value of the derivative contracts after giving effect to legally enforceable master netting agreements and the related cash collateral held by the Firm.

In addition, the Firm holds liquid securities and other cash collateral that may be used as security when the fair value of the client’s exposure is in the Firm’s favor. For these purposes, the definition of liquid securities is consistent with the definition of high quality liquid assets as defined in the LCR rule.

The Firm also holds additional collateral (primarily cash, G7 government securities, other liquid government agency and guaranteed securities, and corporate debt and equity securities) delivered by clients at the initiation of transactions, as well as collateral related to contracts that have a non-daily call frequency and collateral that the Firm has agreed to return but has not yet settled as of the reporting date. Although this collateral does not reduce the receivables balances and is not included in the tables below, it is available as security against potential exposure that could arise should the fair value of the client’s derivative contracts move in the Firm’s favor. Refer to Note 5 for additional information on the Firm’s use of collateral agreements for derivative transactions.

While useful as a current view of credit exposure, the net fair value of the derivative receivables does not capture the potential future variability of that credit exposure. To capture this variability, the Firm calculates, on a client-by-client basis, three measures of potential derivatives-related credit loss: Peak, Derivative Risk Equivalent (“DRE”), and Average exposure (“AVG”). These measures all incorporate netting and collateral benefits, where applicable.

Peak represents a conservative measure of potential derivative exposure, including the benefit of collateral, to a counterparty calculated in a manner that is broadly equivalent to a 97.5% confidence level over the life of the transaction. Peak is the primary measure used by the Firm for setting credit limits for derivative contracts, senior management reporting and derivatives exposure management.
```
</details>

### B5. `CHK-3e14e7fba8cbc18e`
**Stored (= auditor-agreed):** [] (no flags)
<details><summary>chunk text (2124 chars)</summary>

```
$4.6 trillion in assets and $357 billion in stockholders’ equity as of June 30, 2025. The Firm is a leader in investment banking, financial services for consumers and small businesses, commercial banking, financial transaction processing and asset management. Under the J.P. Morgan and Chase brands, the Firm serves millions of customers predominantly in the U.S., and many of the world’s most prominent corporate, institutional and government clients globally. Information about JPMorgan Chase & Co. is available at

JPMorgan Chase & Co. will host a conference call today, July 15, 2025, at 8:30 a.m. (ET) to present second-quarter 2025 financial results. The general public can access the conference call by dialing the following numbers: 1 (888) 324-3618 in the U.S. and Canada; +1 (312) 470-7119 for international callers; use passcode 1364784#. Please dial in 15 minutes prior to the start of the call. The live audio webcast and presentation slides will be available on the Firm’s website,

A replay of the conference call also will be available by telephone beginning at approximately 11:00 a.m. (ET) on July 15, 2025 through 11:59 p.m. (ET) on July 29, 2025 at 1 (800) 841-4034 (U.S. and Canada); +1 (203) 369-3360 (International); use passcode 67371#. The replay will be available via webcast on

This earnings release contains forward-looking statements within the meaning of the Private Securities Litigation Reform Act of 1995. These statements are based on the current beliefs and expectations of JPMorgan Chase & Co.’s management and are subject to significant risks and uncertainties. Actual results may differ from those set forth in the forward-looking statements. Factors that could cause JPMorgan Chase & Co.’s actual results to differ materially from those described in the forward-looking statements can be found in JPMorgan Chase & Co.’s Annual Report on Form 10-K for the year ended December 31, 2024 and Quarterly Report on Form 10-Q for the quarterly period ended March 31, 2025, which have been filed with the Securities and Exchange Commission and are available on JPMorgan Chase & Co.’s website (
```
</details>

### B6. `CHK-3f638f56d6776ec0`
**Stored (= auditor-agreed):** [] (no flags)
<details><summary>chunk text (3231 chars)</summary>

```
today announced financial results for its fiscal 2024 first quarter ended December 30, 2023. The Company posted quarterly revenue of $119.6 billion, up 2 percent year over year, and quarterly earnings per diluted share of $2.18, up 16 percent year over year.

“Today Apple is reporting revenue growth for the December quarter fueled by iPhone sales, and an all-time revenue record in Services,” said Tim Cook, Apple’s CEO. “We are pleased to announce that our installed base of active devices has now surpassed 2.2 billion, reaching an all-time high across all products and geographic segments. And as customers begin to experience the incredible Apple Vision Pro tomorrow, we are committed as ever to the pursuit of groundbreaking innovation — in line with our values and on behalf of our customers.”

“Our December quarter top-line performance combined with margin expansion drove an all-time record EPS of $2.18, up 16 percent from last year,” said Luca Maestri, Apple’s CFO. “During the quarter, we generated nearly $40 billion of operating cash flow, and returned almost $27 billion to our shareholders. We are confident in our future, and continue to make significant investments across our business to support our long-term growth plans.”

Apple’s board of directors has declared a cash dividend of $0.24 per share of the Company’s common stock. The dividend is payable on February 15, 2024 to shareholders of record as of the close of business on February 12, 2024.

This press release contains forward-looking statements, within the meaning of the Private Securities Litigation Reform Act of 1995. These forward-looking statements include without limitation those about payment of the Company’s quarterly dividend. These statements involve risks and uncertainties, and actual results may differ materially from any future results expressed or implied by the forward-looking statements. Risks and uncertainties include without limitation: effects of global and regional economic conditions, including as a result of government policies, war, terrorism, natural disasters, and public health issues; risks relating to the design, manufacture, introduction, and transition of products and services in highly competitive and rapidly changing markets, including from reliance on third parties for components, technology, manufacturing, applications, and content; risks relating to information technology system failures, network disruptions, and failure to protect, loss of, or unauthorized access to, or release of, data; and effects of unfavorable legal proceedings, government investigations, and complex and changing laws and regulations. More information on these risks and other potential factors that could affect the Company’s business, reputation, results of operations, financial condition, and stock price is included in the Company’s filings with the SEC, including in the “Risk Factors” and “Management’s Discussion and Analysis of Financial Condition and Results of Operations” sections of the Company’s most recently filed periodic reports on Form 10-K and Form 10-Q and subsequent filings. The Company assumes no obligation to update any forward-looking statements, which speak only as of the date they are made.
```
</details>

### B7. `CHK-6f517fe795f8a9da`
**Stored (= auditor-agreed):** [] (no flags)
<details><summary>chunk text (1395 chars)</summary>

```
See Note 9 (Debt) to the consolidated financial statements included in Part I, Item 1 for further discussion on our debt and Note 15 (Debt) to the consolidated financial statements included in Part II, Item 8 of our 2024 Form 10-K for further discussion on our debt, the Commercial Paper Program and the Credit Facility.

On February 10, 2025, our Board of Directors declared a quarterly cash dividend of $0.76 per share payable on May 9, 2025 to holders of record as of April 9, 2025 of our Class A common stock and Class B common stock. The aggregate amount of this dividend is $691 million.

Repurchased shares of our common stock are considered treasury stock. In December 2024 and 2023, our Board of Directors approved share repurchase programs of our Class A common stock authorizing us to repurchase up to $12.0 billion and $11.0 billion, respectively. The program approved in 2024 became effective in April 2025 after the completion of the program approved in 2023. The timing and actual number of additional shares repurchased will depend on a variety of factors, including cash requirements to meet the operating needs of the business, legal requirements, as well as the share price and economic and market conditions. The following table summarizes our share repurchase authorizations and repurchase activity of our Class A common stock through March 31, 2025, unless otherwise noted:
```
</details>

### B8. `CHK-71eebcbf1b698f8b`
**Stored (= auditor-agreed):** [] (no flags)
<details><summary>chunk text (2472 chars)</summary>

```
– Chevron Corporation (NYSE: CVX) reported earnings of $3.5 billion ($1.82 per share - diluted) for third quarter 2025, compared with $4.5 billion ($2.48 per share - diluted) in third quarter 2024. Included in the quarter was a net loss of $235 million due to severance and other transaction costs related to the acquisition of Hess Corporation (Hess), partly offset by the fair value measurement of Hess shares. Foreign currency effects increased earnings by $147 million. Adjusted earnings of $3.6 billion ($1.85 per share - diluted) in third quarter 2025 compared to adjusted earnings of $4.5 billion ($2.51 per share - diluted) in third quarter 2024. See Attachment 4 for a reconciliation of adjusted earnings.

“Third quarter results reflect record production, strong cash generation and sustained superior cash returns to shareholders,” said Mike Wirth, Chevron’s chairman and chief executive officer. U.S. and worldwide production hit new company records, up 27 percent and 21 percent, respectively, from last year. Strong cash flow from operations was sustained while the company's adjusted free cash flow increased more than 50 percent from a year ago. The company returned $6 billion of cash to shareholders in the quarter, and over $78 billion in the last 3 years.

Worldwide and U.S. net oil-equivalent production set quarterly records, with the Hess acquisition contributing 495 MBOED. An additional 227 MBOED increase came from legacy Chevron production growth, including gains in the Permian Basin and the ramp-up of projects at the company’s Tengizchevroil LLP (TCO) affiliate and in the Gulf of America.

Cash flow from operations was lower than a year ago mainly due to an unfavorable swing in working capital effects, partly offset by higher cash distributions from TCO. Adjusted FCF benefited from a loan repayment from TCO and higher asset sales proceeds.

The company’s Board of Directors declared a quarterly dividend of one dollar and seventy-one cents ($1.71) per share, payable December 10, 2025, to all holders of common stock as shown on the transfer records of the corporation at the close of business on November 18, 2025.

Net oil-equivalent production during the quarter was up 287,000 barrels per day from a year earlier primarily due to the acquisition of Hess and higher production in Kazakhstan as the Future Growth Project at TCO maintained nameplate capacity, partly offset by impacts from asset sales in Canada and Republic of Congo.
```
</details>

### B9. `CHK-73a21b8063017800`
**Stored (= auditor-agreed):** [["IMPAIRMENT_WRITEDOWN", "REALIZED"], ["LEGAL_REGULATORY_ACTION", "REALIZED"]]
<details><summary>chunk text (2576 chars)</summary>

```
amount included a $771 million favorable final adjustment to the estimated non-cash Paxlovid revenue reversal of $3.5 billion recorded in the fourth quarter of 2023, reflecting 5.1 million Emergency Use Authorization (EUA)-labeled treatment courses returned by the U.S. government through February 29, 2024 versus the estimated 6.5 million treatment courses that were expected to be returned as of December 31, 2023. The 2025

Includes charges/(credits) for employee terminations, asset impairments and other exit costs not associated with acquisitions. The charges for the first quarter of 2025 primarily represent employee termination costs, asset impairments and exit costs associated with our enterprise-wide cost realignment program.

The decrease in net interest expense in the first quarter of 2025, compared to the first quarter of 2024, reflects (i) lower interest expense mainly due to lower long-term debt and commercial paper balances and (ii) an increase in interest income primarily due to higher cash balances from sales of our remaining investment in Haleon plc (Haleon).

The net losses in the first quarter of 2025 include, among other things, a net loss of $144 million related to our investment in Haleon, composed of unrealized losses of $1.0 billion, partially offset by $900 million in realized gains on the sales of our remaining investment.

The amount for the first quarter of 2025 primarily includes certain product liability and other legal expenses related to products discontinued and/or divested by Pfizer. The amount for the first quarter of 2024 primarily included certain product liability expenses related to products discontinued and/or divested by Pfizer.

Our effective tax rates for income from continuing operations were (6.8)% for the first quarter of 2025 and 8.6% for the first quarter of 2024. The negative and lower effective tax rate for the first quarter of 2025, compared to the first quarter of 2024, was primarily due to favorable global income tax resolutions in multiple jurisdictions spanning multiple tax years, as well as a favorable change in the jurisdictional mix of earnings.

Items that reconcile GAAP Reported to non-GAAP Adjusted balances are shown pre-tax. Our effective tax rates for GAAP Reported income from continuing operations were (6.8)% for the first quarter of 2025 and 8.6% for the first quarter of 2024. See Note (6) to the Consolidated Statements of Operations above. Our effective tax rates for non-GAAP Adjusted income were 7.8% for the first quarter of 2025 and 16.6% for the first quarter of 2024.
```
</details>

### B10. `CHK-91a584ef6b2fc23a`
**Stored (= auditor-agreed):** [["LEGAL_REGULATORY_ACTION", "REALIZED"]]
<details><summary>chunk text (1546 chars)</summary>

```
The Company has also continued to make changes to its DMA compliance plan in response to feedback and engagement with the Commission. Although the Company’s DMA compliance plan is intended to address the DMA’s obligations, it has been challenged by the Commission and may be challenged further by private litigants. The DMA provides for significant fines and penalties for noncompliance. While the changes introduced by the Company in the EU are intended to reduce new privacy and security risks that the DMA poses to EU users, many risks will remain. Changes to the Company’s business in response to the DMA or other laws and regulations in the EU or in other jurisdictions, including the U.S., could materially adversely affect the Company’s business, reputation, results of operations, financial condition and stock price.

The Company is also subject to new and changing laws, regulations and other legal obligations regarding online safety, including enhanced protections for minors and mandatory age verification requirements. These obligations can increase regulatory risks by requiring complex compliance measures and significant modifications to the Company’s products, services and operations, and may lead to operational disruptions, heightened privacy and data security risks, and increased costs, all of which can have a material adverse impact on the Company’s business, results of operations, financial condition and stock price. Failure to comply with such changing laws, regulations and other legal obligations can also result in
```
</details>

### B11. `CHK-94449cc2e2406616`
**Stored (= auditor-agreed):** [["LEGAL_REGULATORY_ACTION", "REALIZED"]]
<details><summary>chunk text (3399 chars)</summary>

```
The following table summarizes the contractual amounts and carrying values of off-balance sheet lending-related financial instruments, guarantees and other commitments at March 31, 2024 and December 31, 2023. The amounts in the table below for credit card, home equity and certain scored business banking lending-related commitments represent the total available credit for these products. The Firm has not experienced, and does not anticipate, that all available lines of credit for these products will be utilized at the same time. The Firm can reduce or cancel credit card and certain scored business banking lines of credit by providing the borrower notice or, in some cases as permitted by law, without notice. In addition, the Firm typically closes credit card lines when the borrower is

As of March 31, 2024 and December 31, 2023, primarily includes unfunded commitments to purchase secondary market loans, other equity investment commitments, and unfunded commitments related to certain tax-oriented equity investments, and reflects the impact of adopting updates to the Accounting for Investments in Tax Credit Structures guidance effective January 1, 2024.

For lending-related commitments, the carrying value also includes fees and any purchase discounts or premiums that are deferred and recognized in accounts payable and other liabilities on the Consolidated balance sheets. Deferred amounts for revolving commitments and commitments not expected to fund, are amortized to lending- and deposit-related fees on a straight line basis over the commitment period. For all other commitments the deferred amounts remain deferred until the commitment funds or is sold.

In connection with the Firm’s mortgage loan sale and securitization activities with U.S. GSEs the Firm has made representations and warranties that the loans sold meet certain requirements, and that may require the Firm to repurchase mortgage loans and/or indemnify the loan purchaser if such representations and warranties are breached by the Firm.

The liability related to repurchase demands associated with private label securitizations is separately evaluated by the Firm in establishing its litigation reserves. Refer to Note 24 of this Form 10-Q and Note 30 of JPMorgan Chase’s 2023 Form 10-K for additional information regarding litigation.

The Firm acts as a sponsoring member to clear eligible overnight and term resale and repurchase agreements through the Government Securities Division of the Fixed Income Clearing Corporation (“FICC”) on behalf of clients that become sponsored members under the FICC’s rules. The Firm also guarantees to the FICC the prompt and full payment and performance of its sponsored member clients’ respective obligations under the FICC’s rules. The Firm minimizes its liability under these guarantees by obtaining a security interest in the cash or high-quality securities collateral that the clients place with the clearing house; therefore, the Firm expects the risk of loss to be remote. The Firm’s maximum possible exposure, without taking into consideration the associated collateral, is included in the Exchange & clearing house guarantees and commitments line on page 163. Refer to Note 11 of JPMorgan Chase’s 2023 Form 10-K for additional information on credit risk mitigation practices on resale agreements and the types of collateral pledged under repurchase agreements.
```
</details>

### B12. `CHK-98e4ed139203bc3b`
**Stored (= auditor-agreed):** [] (no flags)
<details><summary>chunk text (2847 chars)</summary>

```
Our cash and cash equivalents decreased by $12.52 billion to $169.58 billion at the end of the third quarter of 2025, due to net cash used for investing and operating activities, partially offset by net cash provided by financing activities and the effect of foreign exchange rate changes on cash and cash equivalents. The net cash used for investing activities primarily reflected an increase in net lending activities (reflecting increases in other collateralized lending and real estate loans) and net purchases of U.S. government obligations accounted for as available-for-sale securities. The net cash used for operating activities primarily reflected cash outflows from trading assets and collateralized transactions (reflecting a decrease in collateralized financings, partially offset by a decrease in collateralized agreements), partially offset by cash inflows from trading liabilities and net earnings. The net cash provided by financing activities primarily reflected cash inflows from deposits (reflecting increases in other deposit and consumer deposit balances) and net issuances of unsecured long-term borrowings, partially offset by common stock repurchases. The increase in cash and cash equivalents, as a result of changes in foreign exchange rates, was due to the U.S. dollar weakening during the nine months ended September 2025.

ur cash and cash equivalents decreased by $86.89 billion to $154.69 billion at the end of the third quarter of 2024, primarily due to net cash used for operating and investing activities, partially offset by net cash provided by financing activities. The net cash used for operating activities primarily reflected cash outflows from trading assets, partially offset by cash inflows from collateralized transactions (reflecting a decrease in collateralized agreements and an increase in collateralized financings), trading liabilities and net earnings. The net cash used for investing activities primarily reflected net purchases of investments (primarily U.S. government and agency obligations accounted for as available-for-sale and held-to-maturity securities). The net cash provided by financing activities primarily reflected cash inflows from deposits (reflecting an increase in consumer deposits, partially offset by a decrease in transaction banking deposits) and cash inflows from other secured financings, partially offset by net repayments of unsecured long-term borrowings.

Our market risk management systems enable us to perform an independent calculation of VaR, Earnings-at-Risk (EaR) and other stress measures, capture risk measures at individual position levels, attribute risk measures to individual risk factors of each position, report many different views of the risk measures (e.g., by desk, business, product type or entity) and produce ad hoc analyses in a timely manner.
```
</details>

### B13. `CHK-9f3013e812996c67`
**Stored (= auditor-agreed):** [] (no flags)
<details><summary>chunk text (1913 chars)</summary>

```
As of March 31, 2024, we had income taxes payable of $4.2 billion, of which $2.1 billion was short-term, related to a one-time transition tax payable incurred as a result of the U.S. Tax Cuts and Jobs Act ("Tax Act"). As permitted by the Tax Act, we will pay the transition tax in annual interest-free installments through 2025. We also have long-term taxes payable of $7.1 billion primarily related to uncertain tax positions as of March 31, 2024.

As of March 31, 2024, we had material purchase commitments and other contractual obligations of $44.0 billion, of which $29.4 billion was short-term. These amounts primarily consist of purchase orders for certain technical infrastructure as well as the non-cancelable portion or the minimum cancellation fee in certain agreements related to commitments to purchase licenses, including content licenses, inventory and network capacity. For those agreements with variable terms, we do not estimate the non-cancelable obligation beyond any minimum quantities and/or pricing as of March 31, 2024. In certain instances, the amount of our contractual obligations may change based on the expected timing of order fulfillment from our suppliers. For more information related to our content licenses, see Note 8 of the Notes to Consolidated Financial Statements included in Item I of this Quarterly Report on Form 10-Q.

, which may be of interest or material to our investors. Further, corporate governance information, including our certificate of incorporation, bylaws, governance guidelines, board committee charters, and code of conduct, is also available on our investor relations website under the heading "Governance." The content of our websites is not incorporated by reference into this Quarterly Report on Form 10-Q or in any other report or document we file with the SEC, and any references to our websites are intended to be inactive textual references only.
```
</details>

### B14. `CHK-a5b77b7a8317416e`
**Stored (= auditor-agreed):** [] (no flags)
<details><summary>chunk text (2761 chars)</summary>

```
Current-period information is preliminary and based on company data available at the time of the presentation. 16 Bank of America Corporation and Subsidiaries Quarterly Results by Business Segment and All Other (Dollars in millions) Second Quarter 2025 Consumer Banking GWIM Global Banking Global Markets All Other Total revenue, net of interest expense $ 10,813 $ 5,937 $ 5,690 $ 5,980 $ (1,812) Provision for credit losses 1,282 20 277 22 (9) Noninterest expense 5,567 4,593 3,070 3,806 147 Net income 2,973 993 1,699 1,528 (77) Return on average allocated capital (1) 27 % 20 % 13 % 13 % n/m Balance Sheet Average Total loans and leases $ 319,142 $ 237,377 $ 387,864 $ 176,368 $ 7,702 Total deposits 951,986 276,825 603,410 38,040 103,500 Allocated capital (1) 44,000 19,750 50,750 49,000 n/m Period end Total loans and leases $ 320,908 $ 241,142 $ 390,691 $ 187,357 $ 6,958 Total deposits 954,373 275,778 643,529 38,232 99,701 First Quarter 2025 Consumer Banking GWIM Global Banking Global Markets All Other Total revenue, net of interest expense $ 10,493 $ 6,016 $ 5,977 $ 6,584 $ (1,559) Provision for credit losses 1,292 14 154 28 (8) Noninterest expense 5,826 4,659 3,184 3,811 290 Net income (loss) 2,531 1,007 1,913 1,949 (4) Return on average allocated capital (1) 23 % 21 % 15 % 16 % n/m Balance Sheet Average Total loans and leases $ 315,038 $ 232,326 $ 378,733 $ 159,625 $ 8,016 Total deposits 947,550 286,399 575,185 38,809 110,389 Allocated capital (1) 44,000 19,750 50,750 49,000 n/m Period end Total loans and leases $ 318,337 $ 234,304 $ 384,208 $ 166,348 $ 7,428 Total deposits 972,064 285,063 591,619 38,268 102,550 Second Quarter 2024 Consumer Banking GWIM Global Banking Global Markets All Other Total revenue, net of interest expense $ 10,206 $ 5,574 $ 6,053 $ 5,459 $ (1,755) Provision for credit losses 1,281 7 235 (13) (2) Noninterest expense 5,464 4,199 2,899 3,486 261 Net income 2,595 1,026 2,116 1,410 (250) Return on average allocated capital (1) 24 % 22 % 17 % 13 % n/m Balance Sheet Average Total loans and leases $ 312,254 $ 222,776 $ 372,738 $ 135,106 $ 8,598 Total deposits 949,180 287,678 525,357 31,944 115,766 Allocated capital (1) 43,250 18,500 49,250 45,500 n/m Period end Total loans and leases $ 312,801 $ 224,837 $ 372,421 $ 138,441 $ 8,285 Total deposits 952,473 281,283 522,525 33,151 121,059 (1) Return on average allocated capital is calculated as net income, adjusted for cost of funds and earnings credits and certain expenses related to intangibles, divided by average allocated capital. Other companies may define or calculate these measures differently. n/m = not meaningful The Company reports the results of operations of its four business segments and All Other on a fully taxable-equivalent (FTE) basis.
```
</details>

### B15. `CHK-a79ecbf6895f948a`
**Stored (= auditor-agreed):** [] (no flags)
<details><summary>chunk text (2927 chars)</summary>

```
The funds transfer pricing process considers the interest rate and liquidity risk characteristics of assets and liabilities and off-balance sheet products. Periodically, the methodology and assumptions utilized in the FTP process are adjusted to reflect economic conditions and other factors, which may

impact the allocation of net interest income to the segments. Effective in the fourth quarter of 2024, the Firm updated its FTP with respect to consumer deposits, which resulted in an increase in the funding benefit reflected within CCB’s net interest income that is fully offset in Corporate, with no effect on the Firm’s net interest income.

Foreign exchange risk is transferred from the LOBs and Other Corporate to Treasury and CIO for certain revenues and expenses. Treasury and CIO manages these risks centrally and reports the impact of foreign exchange rate movements related to the transferred risk in its results.

The amount of capital assigned to each LOB and Corporate is referred to as equity. At least annually, the assumptions, judgments and methodologies used to allocate capital are reassessed and, as a result, the capital allocated to the LOBs and Corporate may change. Refer to Note 32 of JPMorganChase’s 2024 Form 10-K for additional information on capital allocation.

The following table provides a summary of the Firm’s segment results as of or for the three months ended March 31, 2025 and 2024, on a managed basis. The Firm’s definition of managed basis starts with the reported U.S. GAAP results and includes certain reclassifications to present total net revenue for the Firm (and each of the reportable business segments) on an FTE basis. Accordingly, revenue from

investments that receive tax credits and tax-exempt securities is presented in the managed results on a basis comparable to taxable investments and securities. Refer to Note 32 of JPMorganChase’s 2024 Form 10-K for additional information on the Firm’s managed basis.

Certain services are provided by Corporate and used by each of the reportable business segments. The costs of these services, including compensation-related costs, are allocated from Corporate to the respective reportable business segments, with the allocations recorded in noncompensation expense.

We have reviewed the accompanying consolidated balance sheet of JPMorgan Chase & Co. and its subsidiaries (the “Firm”) as of March 31, 2025, and the related consolidated statements of income, comprehensive income, changes in stockholders’ equity and cash flows for the three-month periods ended March 31, 2025 and 2024, including the related notes (collectively referred to as the “interim financial statements”). Based on our reviews, we are not aware of any material modifications that should be made to the accompanying interim financial statements for them to be in conformity with accounting principles generally accepted in the United States of America.
```
</details>

### B16. `CHK-ce89dc9ac38baf7a`
**Stored (= auditor-agreed):** [] (no flags)
<details><summary>chunk text (2506 chars)</summary>

```
The Firm acts as a sponsoring member to clear eligible overnight and term resale and repurchase agreements through the Government Securities Division of the Fixed Income Clearing Corporation (“FICC”) on behalf of clients that become sponsored members under the FICC’s rules. The Firm also guarantees to the FICC the prompt and full payment and performance of its sponsored member clients’ respective obligations under the FICC’s rules. The Firm minimizes its liability under these guarantees by obtaining a security interest in the cash or high-quality securities collateral that the clients place with the clearing house therefore the Firm expects the risk of loss to be remote. The Firm’s maximum possible exposure, without taking into consideration the associated collateral, is included in the Exchange & clearing house guarantees and commitments line on page 185. Refer to Note 11 of JPMorgan Chase’s 2022 Form 10-K for additional information on credit risk mitigation practices on resale agreements and the types of collateral pledged under repurchase agreements.

%-owned finance subsidiary. All securities issued by JPMFC are fully and unconditionally guaranteed by the Parent Company and no other subsidiary of the Parent Company guarantees these securities. These guarantees, which rank pari passu with the Firm’s unsecured and unsubordinated indebtedness, are not included in the table on page 185 of this Note. Refer to Note 20 of JPMorgan Chase’s 2022 Form 10-K for additional information.

The Firm pledges financial assets that it owns to maintain potential borrowing capacity at discount windows with Federal Reserve banks, various other central banks and FHLBs. Additionally, the Firm pledges assets for other purposes, including to collateralize repurchase and other securities financing agreements, to cover short sales and to collateralize derivative contracts and deposits. Certain of these pledged assets may be sold or repledged or otherwise used by the secured parties and are parenthetically identified on the Consolidated balance sheets as assets pledged.

Total pledged assets do not include assets of consolidated VIEs; these assets are used to settle the liabilities of those entities. Refer to Note 14 for additional information on assets and liabilities of consolidated VIEs. Refer to Note 11 for additional information on the Firm’s securities financing activities. Refer to Note 20 of JPMorgan Chase’s 2022 Form 10-K for additional information on the Firm’s long-term debt.
```
</details>

### B17. `CHK-e4299d1773883e04`
**Stored (= auditor-agreed):** [] (no flags)
<details><summary>chunk text (5031 chars)</summary>

```
Current-period information is preliminary and based on company data available at the time of the presentation. 20 The Corporation evaluates its business using certain non-GAAP financial measures, including pretax, pre-provision income (as defined in Endnote H on page 11) and ratios that utilize tangible equity and tangible assets, each of which is a non-GAAP financial measure. Tangible equity represents shareholders’ equity or common shareholders’ equity reduced by goodwill and intangible assets (excluding mortgage servicing rights), net of related deferred tax liabilities (“adjusted” shareholders’ equity or common shareholders’ equity). Return on average tangible common shareholders’ equity measures the Corporation’s net income applicable to common shareholders as a percentage of adjusted average common shareholders’ equity. The tangible common equity ratio represents adjusted ending common shareholders’ equity divided by total tangible assets (total assets less goodwill and intangible assets (excluding mortgage servicing rights), net of related deferred tax liabilities). Return on average tangible shareholders’ equity measures the Corporation’s net income as a percentage of adjusted average total shareholders’ equity. The tangible equity ratio represents adjusted ending shareholders’ equity divided by total tangible assets. Tangible book value per common share represents adjusted ending common shareholders’ equity divided by ending common shares outstanding. These measures are used to evaluate the Corporation’s use of equity. In addition, profitability, relationship and investment models all use return on average tangible shareholders’ equity as key measures to support our overall growth goals. See the tables below for reconciliations of these non-GAAP financial measures to the most directly comparable financial measures defined by GAAP for the years ended December 31, 2024 and 2023, and the three months ended December 31, 2024, September 30, 2024 and December 31, 2023. The Corporation believes the use of these non-GAAP financial measures provides additional clarity in understanding its results of operations and trends. Other companies may define or calculate these non-GAAP financial measures differently. Bank of America Corporation and Subsidiaries Reconciliations to GAAP Financial Measures (Dollars in millions, except per share information) Year Ended December 31 Fourth Quarter 2024 Third Quarter 2024 Fourth Quarter 2023 2024 2023 Reconciliation of income before income taxes to pretax, pre-provision income Income before income taxes $ 29,254 $ 28,342 $ 7,108 $ 7,324 $ 3,124 Provision for credit losses 5,821 4,394 1,452 1,542 1,104 Pretax, pre-provision income $ 35,075 $ 32,736 $ 8,560 $ 8,866 $ 4,228 Reconciliation of average shareholders’ equity to average tangible shareholders’ equity and average tangible common shareholders’ equity Shareholders’ equity $ 294,014 $ 283,353 $ 295,134 $ 294,985 $ 288,618 Goodwill (69,021) (69,022) (69,021) (69,021) (69,021) Intangible assets (excluding mortgage servicing rights) (1,961) (2,039) (1,932) (1,951) (2,010) Related deferred tax liabilities 866 893 859 864 886 Tangible shareholders’ equity $ 223,898 $ 213,185 $ 225,040 $ 224,877 $ 218,473 Preferred stock (26,487) (28,397) (23,493) (25,984) (28,397) Tangible common shareholders’ equity $ 197,411 $ 184,788 $ 201,547 $ 198,893 $ 190,076 Reconciliation of period-end shareholders’ equity to period-end tangible shareholders’ equity and period-end tangible common shareholders’ equity Shareholders’ equity $ 295,559 $ 291,646 $ 295,559 $ 296,512 $ 291,646 Goodwill (69,021) (69,021) (69,021) (69,021) (69,021) Intangible assets (excluding mortgage servicing rights) (1,919) (1,997) (1,919) (1,938) (1,997) Related deferred tax liabilities 851 874 851 859 874 Tangible shareholders’ equity $ 225,470 $ 221,502 $ 225,470 $ 226,412 $ 221,502 Preferred stock (23,159) (28,397) (23,159) (24,554) (28,397) Tangible common shareholders’ equity $ 202,311 $ 193,105 $ 202,311 $ 201,858 $ 193,105 Reconciliation of period-end assets to period-end tangible assets Assets $ 3,261,789 $ 3,180,151 $ 3,261,789 $ 3,324,293 $ 3,180,151 Goodwill (69,021) (69,021) (69,021) (69,021) (69,021) Intangible assets (excluding mortgage servicing rights) (1,919) (1,997) (1,919) (1,938) (1,997) Related deferred tax liabilities 851 874 851 859 874 Tangible assets $ 3,191,700 $ 3,110,007 $ 3,191,700 $ 3,254,193 $ 3,110,007 Book value per share of common stock Common shareholders’ equity $ 272,400 $ 263,249 $ 272,400 $ 271,958 $ 263,249 Ending common shares issued and outstanding 7,610.9 7,895.5 7,610.9 7,688.8 7,895.5 Book value per share of common stock $ 35.79 $ 33.34 $ 35.79 $ 35.37 $ 33.34 Tangible book value per share of common stock Tangible common shareholders’ equity $ 202,311 $ 193,105 $ 202,311 $ 201,858 $ 193,105 Ending common shares issued and outstanding 7,610.9 7,895.5 7,610.9 7,688.8 7,895.5 Tangible book value per share of common stock $ 26.58 $ 24.46 $ 26.58 $ 26.25 $ 24.46
```
</details>

### B18. `CHK-f8a3f57bd2c71f2f`
**Stored (= auditor-agreed):** [["LEGAL_REGULATORY_ACTION", "HYPOTHETICAL"]]
<details><summary>chunk text (3333 chars)</summary>

```
Our failure to effectively design and deliver these multi-rail solutions and products and services could make our other offerings less desirable to these customers, or put us at a competitive disadvantage. In addition, if there is a delay in the implementation of our products or services (which could include compliance obligations, such as AML and CFT, and licensing requirements for our products and services that operate under regulatory licenses), if our products or services do not perform as anticipated, or we are unable to otherwise adequately anticipate risks related to new types of customers, we could face additional regulatory scrutiny, fines, sanctions or other penalties, which could materially and adversely affect our overall business and results of operations, as well as negatively impact our brand and reputation.

Information security risks for payments and technology companies such as ours have significantly increased in recent years in part because of the proliferation of new technologies, the use of the Internet and telecommunications technologies to conduct financial transactions, and the increased sophistication and activities of organized crime, hackers, “hacktivists”, terrorists, nation-states, state-sponsored actors and other external parties. These threats may derive from fraud or malice on the part of our employees or third parties, or may result from human error, software bugs, server malfunctions, software or hardware failure or other technological failure. These threats include cyber-attacks such as computer viruses, denial-of-service attacks, malicious code (including ransomware), social-engineering attacks (including phishing attacks) or information security breaches and could lead to the misappropriation or loss of consumer account and other information and identity theft. These types of threats have risen significantly due to a significant portion of our workforce working in a hybrid environment. These threats also may be further enhanced in frequency or effectiveness through threat actors’ use of AI.

Our operations rely on the secure transmission, storage and other processing of confidential, proprietary, sensitive and personal information and technology in our computer systems and networks, as well as the systems of our third-party providers. Our customers and other parties in the payments value chain, as well as account holders, rely on our digital technologies, computer systems, software and networks to conduct their operations. In addition, to access our products and services, our customers and account holders increasingly use personal smartphones, tablet PCs and other mobile devices that may be beyond our control. We, like other financial technology organizations, routinely are subject to cyber-threats and our technologies, systems and networks, as well as the systems of our third-party providers, have been subject to attempted cyber-attacks. Because of our position in the payments value chain, we believe that we are likely to continue to be a target of such threats and attacks. Geopolitical events and resulting government activity could also lead to information security threats and attacks by affected or sympathizing jurisdictions or other actors, which could put our information and assets at risk, as well as result in network disruption.
```
</details>

### B19. `CHK-fa97d43bd7e68b7f`
**Stored (= auditor-agreed):** [] (no flags)
<details><summary>chunk text (2931 chars)</summary>

```
This Quarterly Report on Form 10-Q for the first quarter of 2024 (“Form 10-Q”) should be read together with JPMorgan Chase’s Annual Report on Form 10-K for the year ended December 31, 2023 (“2023 Form 10-K”). Refer to the Glossary of terms and acronyms and line of business metrics on pages 176-184 for definitions of terms and acronyms used throughout this Form 10-Q.

This Form 10-Q contains forward-looking statements within the meaning of the Private Securities Litigation Reform Act of 1995. These forward-looking statements are based on the current beliefs and expectations of JPMorgan Chase’s management, speak only as of the date of this Form 10-Q and are subject to significant risks and uncertainties. Refer to Forward-looking Statements on page 82

of this Form 10-Q and Part I, Item 1A, Risk Factors on pages 9-33 of the 2023 Form 10-K for a discussion of certain of those risks and uncertainties and the factors that could cause JPMorgan Chase’s actual results to differ materially because of those risks and uncertainties. There is no assurance that actual results will be in line with any outlook information set forth herein, and the Firm does not undertake to update any forward-looking statements.

JPMorgan Chase & Co. (NYSE: JPM), a financial holding company incorporated under Delaware law in 1968, is a leading financial services firm based in the United States of America (“U.S.”), with operations worldwide. JPMorgan Chase had $4.1 trillion in assets and $336.6 billion in stockholders’ equity as of March 31, 2024. The Firm is a leader in investment banking, financial services for consumers and small businesses, commercial banking, financial transaction processing and asset management. Under the J.P. Morgan and Chase brands, the Firm serves millions of customers, predominantly in the U.S., and many of the world’s most prominent corporate, institutional and government clients globally.

For management reporting purposes, the Firm’s activities are organized into four major reportable business segments, as well as a Corporate segment. The Firm’s consumer business is the Consumer & Community Banking (“CCB”) segment. The Firm’s wholesale businesses are the Corporate & Investment Bank (“CIB”), Commercial Banking (“CB”), and Asset & Wealth Management (“AWM”) segments. Refer to Business Segment Results on pages 18-36 and Note 25 of this Form 10-Q, and Note 32 of JPMorgan Chase’s 2023 Form 10-K, for a description of the Firm’s business segments and the products and services they provide to their respective client bases. As a result of the organizational changes announced on January 25, 2024, the Firm will be reorganizing its business segments to reflect the manner in which the segments will be managed. The reorganization of the business segments will be effective in the second quarter of 2024. Refer to Recent events on page 52 of JPMorgan Chase's 2023 Form 10-K for additional information.
```
</details>

### B20. `CHK-fad5e7dae193e277`
**Stored (= auditor-agreed):** [] (no flags)
<details><summary>chunk text (2511 chars)</summary>

```
As a result of the First Republic acquisition, the Firm recorded an allowance for credit losses for the loans acquired and lending-related commitments assumed as of May 1, 2023. Given the differences in risk rating methodologies for the First Republic portfolio, and the ongoing integration of products and systems, the allowance for credit losses for the acquired wholesale portfolio was measured based on other facilities underwritten by the Firm with similar risk characteristics and not based on modeled estimates. The acquired wholesale portfolio was incorporated into the Firm's modeled credit loss estimates commencing in the second quarter of 2024, and therefore is now reflected in the wholesale sensitivity analysis below, resulting in an increase of approximately $200 million. Refer to Note 26 for additional information on the First Republic acquisition.

To demonstrate the sensitivity of credit loss estimates to macroeconomic forecasts as of June 30, 2024, the Firm compared the modeled estimates under its relative adverse scenario to its central scenario. Without considering offsetting or correlated effects in other qualitative components of the Firm’s allowance for credit losses, the comparison between these two scenarios for the exposures below reflect the following differences:

Recognizing that forecasts of macroeconomic conditions are inherently uncertain, the Firm believes that its process to consider the available information and associated risks and uncertainties is appropriately governed and that its estimates of expected credit losses were reasonable and appropriate for the period ended June 30, 2024.

For purposes of the table above, the derivative receivables total reflects the impact of netting adjustments; however, the $10.2 billion of derivative receivables classified as level 3 does not reflect the netting adjustment as such netting is not relevant to a presentation based on the transparency of inputs to the valuation of an asset. The level 3 balances would be reduced if netting were applied, including the netting benefit associated with cash collateral.

The credit card rewards liability was $13.8 billion and $13.2 billion at June 30, 2024 and December 31, 2023, respectively, and is recorded in accounts payable and other liabilities on the Consolidated balance sheets. Refer to pages 157-158 of JPMorgan Chase’s 2023 Form 10-K for a description of the significant assumptions and sensitivities, associated with the Firm’s credit card rewards liability.
```
</details>
