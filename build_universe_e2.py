"""
build_universe_e2.py -- E2 phase F1: universe construction.

Builds THREE tables under data/universe_e2_candidates/:

  * `hybrid136` -- the RATIFIED universe (owner, in chat, 2026-08-21). A
    two-stratum union: a CORE stratum that is exactly `continuity5`'s rule
    (E1's five sectors, K=20 -> 100 names) plus an EXTENSION stratum over the
    three sectors that exist only under `broad8` (industrials, utilities,
    materials/real estate, K=12 -> 36 names). Membership rows carry a
    `stratum` column.
  * `continuity5` and `broad8` -- the two pre-decision candidates, rebuilt
    unchanged as the OPTION RECORD the decision cites. They must keep
    reproducing byte-identically; nothing in this file may add a column to
    them or apply a manual exclusion to them by default.

Nothing here modifies data/universe.csv or any E1 pipeline file.

Ratified design being implemented (EXPANSION_PLAN.md §1.3, §2c, HANDOFF §3
2026-08-20, amended 2026-08-21): sector-stratified top-K by
`dei:EntityPublicFloat`, ANNUAL point-in-time reconstitution, large-cap only,
136 members x 11 annual reconstitution dates.

THE POINT-IN-TIME GUARANTEE (the load-bearing property of this file)
--------------------------------------------------------------------
Membership at reconstitution date D is a function of EDGAR facts whose
*public filing date* is strictly < D. Concretely:

  * float values come from `dei:EntityPublicFloat` facts carrying an explicit
    `filed` date from the XBRL companyconcept API, and `pit_float_asof()`
    REJECTS any fact with filed >= D (asserted, not assumed -- see
    `assert_pit_membership()` which re-checks every emitted membership row);
  * eligibility ("has this registrant been filing periodic reports?") counts
    only 10-K/10-Q filings with filingDate < D, over the 8 calendar quarters
    that PRECEDE D. It is backward-only by construction. The tempting
    "still filing at the END of the window" condition is look-ahead and is
    rejected explicitly (EXPANSION_PLAN.md §2c);
  * the only knowingly non-PIT input is the SIC code (submissions.json
    reports the registrant's CURRENT SIC, not its SIC as of D). That is a
    stated, bounded look-ahead confined to the sector LABEL, never to
    membership -- it can move a company between sector buckets, it cannot
    make a company large or small. Documented in the report.

Data sources, all free EDGAR, all through edgar_client.EdgarClient's polite
client (mandatory User-Agent, 10 req/s sliding window, 429 backoff, on-disk
idempotent cache):

  1. XBRL frames  data.sec.gov/api/xbrl/frames/dei/EntityPublicFloat/USD/CY{Y}Q{q}I.json
     -> ENUMERATION only (which registrants are big). Cached under
        data/raw/frames/ (new subdir, same convention as companyfacts/).
     NOTE (verified live 2026-08-20): frames data points carry
     {accn, cik, entityName, loc, end, val} and NO `filed` date, so a frame
     alone CANNOT establish point-in-time validity. See §"recon deltas".
  2. XBRL companyconcept
        data.sec.gov/api/xbrl/companyconcept/CIK##########/dei/EntityPublicFloat.json
     -> the per-CIK float history WITH `filed` dates (~3 KB/CIK). This is the
        "per-CIK patch pass" the recon called for, done with the cheap
        single-concept endpoint instead of the 4 MB companyfacts document.
        Cached under data/raw/companyconcept/.
  3. submissions.json (via the existing EdgarClient.get_effective_recent,
     which transparently pages filings.files[] for heavy filers)
     -> SIC, entityType, current tickers, former names, periodic filing
        history for the eligibility rule.

Both (1) and (2) are fetched with a small helper that calls EdgarClient._get()
so they inherit the same rate limiter / User-Agent / retry path as everything
else; edgar_client.py itself is NOT modified by this phase.

Two mechanisms exist for removing a registrant that the automated rules cannot:

  4. manual_exclusions.csv -- a hand-maintained, evidenced list of registrants
     removed from the RATIFIED variant (see load_manual_exclusions). Every row
     that bites is logged to the reject table and printed in the report.
  5. audit_float_scale() -- the compensating control for the sanitizer's one
     structural blind spot (a registrant that mis-scales its ENTIRE float
     history the same way). It SCREENS and reports; it never removes.

Run:  python3 build_universe_e2.py --stage all --shortlist-per-date 800
Stages are individually re-runnable and idempotent: everything network-fetched
is cached on disk, and every intermediate artifact is written to
data/universe_e2_candidates/_cache/.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from edgar_client import EdgarClient  # noqa: E402

OUT_DIR = REPO_ROOT / "data" / "universe_e2_candidates"
CACHE_DIR = OUT_DIR / "_cache"
RAW_DIR = REPO_ROOT / "data" / "raw"
FRAMES_DIR = RAW_DIR / "frames"
CONCEPT_DIR = RAW_DIR / "companyconcept"
REPORT_PATH = REPO_ROOT / "data" / "E2_UNIVERSE_REPORT.md"
E1_UNIVERSE_CSV = REPO_ROOT / "data" / "universe.csv"  # READ-ONLY here

FRAMES_URL_TMPL = (
    "https://data.sec.gov/api/xbrl/frames/dei/EntityPublicFloat/USD/CY{year}Q{q}I.json"
)
CONCEPT_URL_TMPL = (
    "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/dei/EntityPublicFloat.json"
)
CONCEPT_URL_ANY_TMPL = (
    "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/{taxonomy}/{concept}.json"
)

# The cover-page share count. Used by BOTH the ratified min-shares rule (rule 2
# below) and the float-scale audit's arms A/B, so it lives up here rather than
# inside either of them.
SHARES_CONCEPT = "EntityCommonStockSharesOutstanding"

# ---------------------------------------------------------------------------
# Window / reconstitution convention  (PARAMETERIZED -- exact dates are subject
# to owner gate G3, EXPANSION_PLAN.md §4)
# ---------------------------------------------------------------------------
#
# WHY JULY 1, AND WHY 11 DATES:
#
# `dei:EntityPublicFloat` is the 10-K cover-page "aggregate market value of
# voting equity held by non-affiliates", measured *as of the last business day
# of the registrant's most recently completed SECOND fiscal quarter* and made
# public when the 10-K is filed -- typically 8-10 months AFTER the measurement
# instant (verified: BBBY's float instant 2021-08-28 was first public
# 2022-04-21; Apple's instant 2025-03-28 was first public 2025-10-31).
#
# A July 1 reconstitution date therefore:
#   (a) sits after the Feb-Mar 10-K wave of December-fiscal-year-end filers --
#       the large majority of US large caps -- so their most recent float
#       disclosure (measured the prior June 30) is public and ~12 months old;
#   (b) sits after the Q1 10-Q wave, so the eligibility check sees a complete
#       set of quarters;
#   (c) matches the Russell reconstitution convention the ratified design was
#       modelled on ("Russell-style", EXPANSION_PLAN.md §2, option C), which
#       keeps the universe's rebalance calendar familiar and quarter-aligned
#       (July 1 is the first day of calendar Q3, so the 8 eligibility quarters
#       are exactly the 8 completed calendar quarters before it -- no partial
#       quarter to reason about);
#   (d) is a fixed calendar date, not "trailing from today" -- the coupling
#       audit's F1/F2 requirement (EXPANSION_PLAN.md §5).
# Nothing about the pipeline depends on July specifically; RECON_MONTH/DAY and
# the first/last year are all parameters, because G3 has not yet fixed them.
RECON_MONTH = 7
RECON_DAY = 1
FIRST_RECON_YEAR = 2016
LAST_RECON_YEAR = 2026  # -> 11 annual dates spanning a 10-year window

# How many quarterly frames to union for candidate ENUMERATION at each date.
# The recon's literal "union of the 4 quarterly instant frames preceding the
# date" is NOT sufficient once the point-in-time filter is applied -- see the
# "recon deltas" note in the report generator. 8 quarters (~2 years of instant
# dates) guarantees every annual filer has at least one float fact that was
# already public at D, whatever its fiscal year end.
FRAMES_LOOKBACK_QUARTERS = 8

# A float fact may be at most this old (instant date -> reconstitution date)
# to be usable. 27 months = the widest gap the 8-quarter lookback can produce.
MAX_FLOAT_STALENESS_DAYS = 830

# Filer tagging errors are real and large: the CY2022Q2I float frame's top
# "companies" by raw value are M&T Bank at $2.7e16, First American at $5.4e15
# and ManpowerGroup at $4.0e15 -- each exactly 1e6x its true float. Un-sanitized
# top-K selection would hand the universe to whoever mis-scaled their cover
# page. Facts above this ceiling are EXCLUDED and COUNTED (never silently
# repaired -- we do not know the intended scale).
MAX_PLAUSIBLE_FLOAT_USD = 1.0e13  # $10T; largest genuine float seen is ~$3.3T
MIN_PLAUSIBLE_FLOAT_USD = 1.0e6  # $1M; below this is a shell/typo, not a large cap

# Per-CIK internal consistency, checked against the registrant's own
# TEMPORALLY ADJACENT float disclosures -- not against its long-run median.
# This distinction is load-bearing: a median-based rule flagged NVIDIA's
# genuine $1.1T/$2.7T/$4.0T floats (its 2014-2020 history drags the median to
# ~$10B) and would have silently deleted the largest company in the universe.
# A scale error is a 10^3-10^6 jump that reverts; real growth, even NVIDIA's,
# is smooth from one annual disclosure to the next.
SUSPECT_FLOAT_RATIO = 50.0

# Level-aware second arm of the same rule. Measured justification (over the
# 3,558 adjacent float transitions of the selected members): the 99th
# percentile transition is 3.3x and only SIX exceed 10x. Of those six, every
# legitimate one ENDS at a small float -- Chesapeake/Expand Energy 33.3x
# ($48M -> $1.6B, emerging from its 2020 Chapter 11), Nike 19.0x and AEP 11.2x
# (both off anomalously low early-history values, ending at $38B and $15.5B) --
# while the errors END in mega-cap territory (Universal Display's $320B and
# $9,245B, where its real float is ~$7B). So: a >10x jump is allowed at small
# size, because bankruptcy emergence and IPO seasoning genuinely do that, and
# those distressed names are exactly what EXPANSION_PLAN.md §2c wants kept
# in-sample; but a >10x jump that LANDS above $50B of float has no plausible
# corporate mechanism and is treated as a tagging error.
MEGA_FLOAT_USD = 50e9
MEGA_JUMP_RATIO = 10.0

# Eligibility: >= this many consecutive calendar quarters, immediately before
# the reconstitution date, each containing >= 1 10-K or 10-Q (filed < D).
MIN_ELIGIBLE_QUARTERS = 8
PERIODIC_FORMS = ("10-K", "10-Q")

# How deep to run full diligence (submissions + companyconcept). Sector
# stratification pushes the deepest selected member well past the overall
# top-100, so this is measured, not guessed: `--shortlist-per-date` is raised
# until the deepest selected member's overall float rank has clear headroom
# (reported as "shortlist headroom" in the report).
DEFAULT_SHORTLIST_PER_DATE = 400

TARGET_TOTAL_MEMBERS = 100

# ---------------------------------------------------------------------------
# SIC -> sector taxonomies
# ---------------------------------------------------------------------------
# Two variants, both deterministic pure functions of the SIC integer:
#
#   "continuity5" -- E1's five sectors (tech, financials, healthcare, energy,
#       consumer). Any SIC outside them is EXCLUDED from the universe.
#       K = 20 per sector -> 100 names.
#   "broad8" -- the same five PLUS industrials, utilities and a combined
#       materials/real-estate bucket. K sized to total 100.
#
# The two share ONE mapping table: broad8 is the full table, continuity5 is
# that table restricted to five sector names (everything else -> EXCLUDED).
# This is deliberate: it means the two variants never disagree about where a
# company belongs, only about whether its bucket exists.

SECTOR_TECH = "tech"
SECTOR_FIN = "financials"
SECTOR_HEALTH = "healthcare"
SECTOR_ENERGY = "energy"
SECTOR_CONSUMER = "consumer"
SECTOR_INDUSTRIALS = "industrials"
SECTOR_UTILITIES = "utilities"
SECTOR_MATERIALS_RE = "materials_realestate"

CONTINUITY5_SECTORS = (SECTOR_TECH, SECTOR_FIN, SECTOR_HEALTH, SECTOR_ENERGY, SECTOR_CONSUMER)
BROAD8_SECTORS = CONTINUITY5_SECTORS + (SECTOR_INDUSTRIALS, SECTOR_UTILITIES, SECTOR_MATERIALS_RE)

# K per sector. continuity5: flat 20 x 5 = 100.
# broad8: 13 for the four deepest large-cap sectors, 12 for the rest = 100.
CONTINUITY5_K = {s: 20 for s in CONTINUITY5_SECTORS}
BROAD8_K = {
    SECTOR_TECH: 13,
    SECTOR_FIN: 13,
    SECTOR_HEALTH: 13,
    SECTOR_CONSUMER: 13,
    SECTOR_ENERGY: 12,
    SECTOR_INDUSTRIALS: 12,
    SECTOR_UTILITIES: 12,
    SECTOR_MATERIALS_RE: 12,
}

# ---------------------------------------------------------------------------
# hybrid136 -- the variant the owner RATIFIED in chat on 2026-08-21, replacing
# the earlier continuity5-vs-broad8 either/or with a two-stratum union.
# ---------------------------------------------------------------------------
#
#   CORE stratum      = exactly continuity5's rule: E1's five sectors, K=20 each
#                       -> 100 names, so E1<->E2 sector comparisons stay valid
#                       and the confirmatory analysis runs on a population with
#                       the same sector definitions E1 used.
#   EXTENSION stratum = the three sectors that exist only under broad8
#                       (industrials, utilities incl. telecom, materials/real
#                       estate), K=12 each -> 36 names.
#
# Union = 136 members per reconstitution date. Everything else is unchanged
# from the two option-record variants: same float ranks, same point-in-time
# rule, same backward-only eligibility, same sanitizer, same annual dates, and
# the same SIC table (so the three sub-decisions -- telecom 4812/4813 ->
# utilities, card networks 7389 -> financials, managed care 6324 -> healthcare
# -- keep the report's documented defaults).
#
# Because selection is independent PER SECTOR (top-K inside each bucket over
# the same candidate pool), hybrid136's core stratum reproduces continuity5's
# membership EXACTLY and its extension stratum reproduces broad8's three
# non-core buckets exactly -- modulo the documented manual exclusions below.
# `test_build_universe_e2.py` pins both halves of that identity.
HYBRID136_SECTORS = BROAD8_SECTORS
HYBRID136_CORE_SECTORS = CONTINUITY5_SECTORS
HYBRID136_EXTENSION_SECTORS = (SECTOR_INDUSTRIALS, SECTOR_UTILITIES, SECTOR_MATERIALS_RE)
HYBRID136_CORE_K = 20
HYBRID136_EXTENSION_K = 12
HYBRID136_K = {
    **{s: HYBRID136_CORE_K for s in HYBRID136_CORE_SECTORS},
    **{s: HYBRID136_EXTENSION_K for s in HYBRID136_EXTENSION_SECTORS},
}

STRATUM_CORE = "core"
STRATUM_EXTENSION = "extension"
HYBRID136_STRATUM = {
    **{s: STRATUM_CORE for s in HYBRID136_CORE_SECTORS},
    **{s: STRATUM_EXTENSION for s in HYBRID136_EXTENSION_SECTORS},
}

# Variants that emit a `stratum` column. continuity5/broad8 deliberately do
# NOT: they are the frozen option record behind the owner's decision, and
# adding a column would silently change the artifacts the decision cites.
TAXONOMY_STRATA: dict[str, dict[str, str]] = {"hybrid136": HYBRID136_STRATUM}

if sum(HYBRID136_K.values()) != 136:
    raise AssertionError(
        f"hybrid136 must total 136 members per date, got {sum(HYBRID136_K.values())}"
    )

# Non-operating registrants: funds, trusts, shells, securitization vehicles.
# These file 10-K/10-Q and disclose a float, so neither the eligibility rule
# nor the float rank excludes them -- an explicit SIC filter must.
NON_OPERATING_SIC = {
    6189: "asset-backed securities (securitization trusts)",
    6199: "finance services (catch-all; incl. many non-operating vehicles)",
    6722: "management investment offices, open-end (mutual funds)",
    6726: "investment offices NEC (closed-end funds, ETFs, unit trusts)",
    6733: "trusts, except educational/religious/charitable",
    6770: "blank checks (SPACs, shells)",
    6792: "oil royalty traders",
    6795: "mineral royalty traders",
    9995: "non-classifiable establishments",
}

# Exact-SIC overrides, applied BEFORE the range table. Each exists because the
# range it sits inside would put the company in a visibly wrong bucket.
SIC_EXACT: dict[int, tuple[str, str]] = {
    2842: (SECTOR_MATERIALS_RE, "specialty cleaning/polishing preparations (Ecolab-type) -- specialty chemicals, not household staples"),
    2843: (SECTOR_MATERIALS_RE, "surface active agents -- specialty chemicals"),
    2844: (SECTOR_CONSUMER, "perfumes & cosmetics (Colgate, Estee Lauder)"),
    3559: (SECTOR_TECH, "special industry machinery NEC -- semiconductor capital equipment (Applied Materials, Lam)"),
    3826: (SECTOR_HEALTH, "laboratory analytical instruments (Thermo Fisher, Agilent)"),
    5047: (SECTOR_HEALTH, "wholesale medical/dental/hospital equipment"),
    5122: (SECTOR_HEALTH, "wholesale drugs & proprietaries (McKesson, Cencora, Cardinal)"),
    5171: (SECTOR_ENERGY, "wholesale petroleum bulk stations"),
    5172: (SECTOR_ENERGY, "wholesale petroleum products NEC"),
    6324: (SECTOR_HEALTH, "hospital & medical service plans (UnitedHealth, Elevance, CVS) -- managed care, not insurance-as-financials"),
    6798: (SECTOR_MATERIALS_RE, "real estate investment trusts"),
    7389: (SECTOR_FIN, "services-business services NEC -- EDGAR's SIC for the card networks (Visa, Mastercard) and payment processors; E1 classifies V/MA as financials"),
}

# Ordered, non-overlapping SIC ranges (inclusive). Asserted non-overlapping at
# import time by _assert_ranges_disjoint().
SIC_RANGES: list[tuple[int, int, str, str]] = [
    (100, 999, SECTOR_CONSUMER, "agriculture, forestry, fishing"),
    (1000, 1119, SECTOR_MATERIALS_RE, "metal mining"),
    (1220, 1241, SECTOR_ENERGY, "coal mining"),
    (1300, 1399, SECTOR_ENERGY, "crude petroleum, natural gas, oilfield services"),
    (1400, 1499, SECTOR_MATERIALS_RE, "mining & quarrying of nonmetallic minerals"),
    (1520, 1799, SECTOR_INDUSTRIALS, "construction & engineering"),
    (2000, 2141, SECTOR_CONSUMER, "food, beverages, tobacco"),
    (2200, 2399, SECTOR_CONSUMER, "textiles & apparel"),
    (2400, 2499, SECTOR_MATERIALS_RE, "lumber & wood products"),
    (2510, 2599, SECTOR_CONSUMER, "furniture & fixtures"),
    (2600, 2679, SECTOR_MATERIALS_RE, "paper & converted paper products"),
    (2700, 2799, SECTOR_CONSUMER, "publishing & printing (media)"),
    (2800, 2824, SECTOR_MATERIALS_RE, "industrial & agricultural chemicals, plastics/resins"),
    (2833, 2836, SECTOR_HEALTH, "pharmaceutical preparations, biologics, diagnostics"),
    (2840, 2841, SECTOR_CONSUMER, "soaps & detergents (Procter & Gamble)"),
    (2850, 2899, SECTOR_MATERIALS_RE, "paints, industrial organic chemicals, misc chemicals"),
    (2900, 2999, SECTOR_ENERGY, "petroleum refining & related (Exxon, Chevron, ConocoPhillips)"),
    (3000, 3089, SECTOR_CONSUMER, "rubber & plastics products (incl. Nike's 3021)"),
    (3090, 3199, SECTOR_CONSUMER, "leather & footwear"),
    (3200, 3299, SECTOR_MATERIALS_RE, "stone, clay, glass, concrete"),
    (3300, 3399, SECTOR_MATERIALS_RE, "primary metal industries"),
    (3400, 3499, SECTOR_INDUSTRIALS, "fabricated metal products"),
    (3500, 3558, SECTOR_INDUSTRIALS, "industrial & commercial machinery"),
    (3560, 3569, SECTOR_INDUSTRIALS, "general industrial machinery"),
    (3570, 3579, SECTOR_TECH, "computer & office equipment (Apple 3571, Cisco 3576)"),
    (3580, 3599, SECTOR_INDUSTRIALS, "service industry & misc machinery"),
    (3600, 3629, SECTOR_INDUSTRIALS, "electrical industrial apparatus (GE 3600)"),
    (3630, 3651, SECTOR_CONSUMER, "household appliances & audio/video equipment"),
    (3652, 3660, SECTOR_CONSUMER, "prerecorded media"),
    (3661, 3699, SECTOR_TECH, "communications equipment, electronic components, semiconductors (NVIDIA 3674)"),
    (3700, 3710, SECTOR_INDUSTRIALS, "transportation equipment NEC"),
    (3711, 3716, SECTOR_CONSUMER, "motor vehicles & car bodies (Tesla, GM, Ford)"),
    (3720, 3799, SECTOR_INDUSTRIALS, "aerospace, defense, rail & ship equipment"),
    (3800, 3825, SECTOR_INDUSTRIALS, "search/navigation, measuring & control instruments"),
    (3827, 3840, SECTOR_INDUSTRIALS, "optical & measuring instruments"),
    (3841, 3851, SECTOR_HEALTH, "medical & surgical instruments, ophthalmic goods"),
    (3860, 3899, SECTOR_INDUSTRIALS, "photographic & misc instruments"),
    (3900, 3999, SECTOR_CONSUMER, "misc manufacturing: jewelry, toys, sporting goods"),
    (4000, 4099, SECTOR_INDUSTRIALS, "railroads"),
    (4100, 4299, SECTOR_INDUSTRIALS, "transit & trucking"),
    (4400, 4499, SECTOR_INDUSTRIALS, "water transportation"),
    (4500, 4599, SECTOR_INDUSTRIALS, "air transportation"),
    (4600, 4699, SECTOR_ENERGY, "pipelines except natural gas (crude/refined products)"),
    (4700, 4789, SECTOR_INDUSTRIALS, "transportation services"),
    (4812, 4813, SECTOR_UTILITIES, "telephone & wireless carriers (AT&T, Verizon) -- see report DECISION note"),
    (4820, 4831, SECTOR_CONSUMER, "telegraph & radio broadcasting"),
    (4832, 4841, SECTOR_CONSUMER, "TV broadcasting & cable (Comcast, Charter)"),
    (4899, 4899, SECTOR_UTILITIES, "communications services NEC"),
    (4900, 4921, SECTOR_UTILITIES, "electric & combination utilities"),
    (4922, 4923, SECTOR_ENERGY, "natural gas transmission (interstate midstream: Williams, Kinder Morgan)"),
    (4924, 4991, SECTOR_UTILITIES, "gas distribution, water supply, sanitary services, cogeneration"),
    (5000, 5099, SECTOR_INDUSTRIALS, "wholesale-durable goods (Grainger 5080)"),
    (5100, 5199, SECTOR_CONSUMER, "wholesale-nondurable goods"),
    (5200, 5999, SECTOR_CONSUMER, "retail (Walmart 5331, Home Depot 5211, McDonald's 5812, Amazon 5961)"),
    (6020, 6199, SECTOR_FIN, "depository institutions & credit (JPMorgan/BofA 6021)"),
    (6200, 6299, SECTOR_FIN, "security & commodity brokers, exchanges (Goldman 6211)"),
    (6300, 6323, SECTOR_FIN, "insurance carriers"),
    (6325, 6411, SECTOR_FIN, "insurance carriers & agents"),
    (6500, 6599, SECTOR_MATERIALS_RE, "real estate operators & developers"),
    (7000, 7099, SECTOR_CONSUMER, "hotels & lodging"),
    (7200, 7299, SECTOR_CONSUMER, "personal services"),
    (7310, 7319, SECTOR_CONSUMER, "advertising & marketing services"),
    (7320, 7369, SECTOR_INDUSTRIALS, "credit reporting, staffing & business support"),
    (7370, 7379, SECTOR_TECH, "computer programming, data processing, IT services (Alphabet 7370, Microsoft 7372)"),
    (7380, 7388, SECTOR_INDUSTRIALS, "misc business services"),
    (7390, 7399, SECTOR_INDUSTRIALS, "business services NEC"),
    (7500, 7699, SECTOR_CONSUMER, "automotive & misc repair services"),
    (7800, 7999, SECTOR_CONSUMER, "movies, entertainment & recreation (Disney 7990, Netflix 7841)"),
    (8000, 8099, SECTOR_HEALTH, "health services (hospitals, HCA 8062)"),
    (8100, 8199, SECTOR_INDUSTRIALS, "legal services"),
    (8200, 8299, SECTOR_CONSUMER, "educational services"),
    (8300, 8399, SECTOR_INDUSTRIALS, "social services"),
    (8600, 8699, SECTOR_INDUSTRIALS, "membership organizations"),
    (8700, 8730, SECTOR_INDUSTRIALS, "engineering, accounting & management services"),
    (8731, 8734, SECTOR_HEALTH, "commercial physical & biological research (biotech R&D, CROs)"),
    (8740, 8748, SECTOR_INDUSTRIALS, "management & consulting services"),
    (8800, 8899, SECTOR_INDUSTRIALS, "private households / services NEC"),
]

EXCLUDED = "EXCLUDED"


def _assert_ranges_disjoint() -> None:
    ordered = sorted(SIC_RANGES, key=lambda r: r[0])
    for (lo1, hi1, s1, _), (lo2, hi2, s2, _) in zip(ordered, ordered[1:]):
        if lo1 > hi1:
            raise AssertionError(f"inverted SIC range {lo1}-{hi1} ({s1})")
        if lo2 <= hi1:
            raise AssertionError(
                f"overlapping SIC ranges: {lo1}-{hi1} ({s1}) and {lo2}-{hi2} ({s2})"
            )


_assert_ranges_disjoint()


def sic_to_sector(sic: Optional[int], taxonomy: str = "broad8") -> str:
    """Deterministic, pure SIC -> sector. Returns EXCLUDED for non-operating
    registrants, unmapped SICs, and (under 'continuity5') any sector outside
    E1's five. No company-specific special cases -- if a name lands somewhere
    surprising, the fix belongs in SIC_EXACT/SIC_RANGES where it is visible in
    the report's printed mapping table.

    'hybrid136' uses the SAME full table as 'broad8' -- the two never disagree
    about where a company belongs, only about how deep each bucket runs. That
    is what makes hybrid136's core stratum reproduce continuity5 exactly.
    """
    if taxonomy not in ("broad8", "continuity5", "hybrid136"):
        raise ValueError(f"unknown taxonomy {taxonomy!r}")
    if sic is None:
        return EXCLUDED
    try:
        sic = int(sic)
    except (TypeError, ValueError):
        return EXCLUDED
    if sic <= 0:
        return EXCLUDED
    if sic in NON_OPERATING_SIC:
        return EXCLUDED
    sector = None
    if sic in SIC_EXACT:
        sector = SIC_EXACT[sic][0]
    else:
        for lo, hi, sec, _ in SIC_RANGES:
            if lo <= sic <= hi:
                sector = sec
                break
    if sector is None:
        return EXCLUDED
    if taxonomy == "continuity5" and sector not in CONTINUITY5_SECTORS:
        return EXCLUDED
    return sector


TAXONOMIES = {
    "continuity5": (CONTINUITY5_SECTORS, CONTINUITY5_K),
    "broad8": (BROAD8_SECTORS, BROAD8_K),
    "hybrid136": (HYBRID136_SECTORS, HYBRID136_K),
}

# The variant the owner ratified (HANDOFF §3, 2026-08-21). The other two are
# built unchanged as the option record behind that decision.
RATIFIED_VARIANT = "hybrid136"
OPTION_RECORD_VARIANTS = ("continuity5", "broad8")


def stratum_of(sector: str, taxonomy: str = RATIFIED_VARIANT) -> str:
    """'core' / 'extension' for a stratified taxonomy, '' otherwise."""
    return TAXONOMY_STRATA.get(taxonomy, {}).get(sector, "")


# ---------------------------------------------------------------------------
# Float-integrity rulesets -- PER VARIANT, on purpose
# ---------------------------------------------------------------------------
#
# The owner ratified two extra float-integrity rules in chat on 2026-08-21
# ("Yes, please adopt both, as you recommended"), scoped to the LIVE
# `hybrid136` path ONLY. `continuity5` and `broad8` are the frozen option
# record behind the 2026-08-21 universe decision and must keep reproducing
# byte-identically, so they keep the LEGACY behaviour. That scoping is not a
# style choice -- a rule that quietly changed the option-record tables would
# destroy the audit trail the decision cites.
#
#   RULE 1  newer_zero_float ("a newer zero beats an older positive")
#       If a registrant's MOST RECENT publicly-filed dei:EntityPublicFloat
#       disclosure as of D is exactly 0, the registrant has NO PUBLIC FLOAT at
#       D and is ineligible -- instead of the legacy behaviour, where the
#       sanitizer discards the 0 as `zero_or_negative` and pit_float_asof()
#       falls back to a superseded positive value. This generalises the
#       date-scoped EIDP / Dow Chemical / Energy Transfer Operating manual
#       exclusions into a systematic rule: all three are the same mechanism --
#       the registrant became a wholly-owned subsidiary, correctly tagged 0,
#       and its fossil pre-merger float won anyway.
#
#   RULE 2  min_public_shares ("100 shares is not a public float")
#       If a registrant's own most recent publicly-filed cover-page share count
#       (dei:EntityCommonStockSharesOutstanding) as of D is below
#       MIN_PUBLIC_SHARES_FOR_MEMBERSHIP, it has no publicly traded common
#       equity at D and is ineligible. This is the EIDP 100-shares case.
#
# Both rules are POINT-IN-TIME by construction: they read only facts with
# `filed < D`, exactly like every other input to membership.
#
# Rule 2 is deliberately NOT allowed to reach for the network. It uses only
# already-cached companyconcept documents; where a registrant's share count is
# untestable -- multi-class filers that tag one row per class behind an XBRL
# axis and so expose no undimensioned fact at all (the ~15% coverage gap
# measured in the report's 6.7) -- the rule simply does not fire. Closing that
# gap by fetching aggressively was considered and rejected: it would trade a
# measured, documented blind spot for an unmeasured EDGAR bill.
FLOAT_RULE_NEWER_ZERO = "newer_zero_float"
FLOAT_RULE_MIN_SHARES = "min_public_shares"
FLOAT_INTEGRITY_RULE_NAMES = (FLOAT_RULE_NEWER_ZERO, FLOAT_RULE_MIN_SHARES)

# A cover page reporting fewer than this many common shares outstanding is a
# wholly-owned subsidiary's cover page, not a large cap's. Same number the
# 6.7 screen already used as its arm-B floor (AUDIT_MIN_PUBLIC_SHARES), kept
# as one constant below so the screen and the rule can never drift apart.
MIN_PUBLIC_SHARES_FOR_MEMBERSHIP = 1_000_000

# A share count may be at most this old (measurement date -> D) to disqualify a
# registrant. Same bound as the float staleness cap. This can only ever PREVENT
# rule 2 from firing, never cause it: a registrant that stopped tagging the
# concept years ago is treated as untestable rather than as disqualified.
MIN_SHARES_MAX_STALENESS_DAYS = MAX_FLOAT_STALENESS_DAYS


@dataclass(frozen=True)
class FloatRuleset:
    """Which float-integrity rules a variant is built under."""

    name: str
    newer_zero_float: bool = False
    min_public_shares: bool = False
    min_public_shares_threshold: int = MIN_PUBLIC_SHARES_FOR_MEMBERSHIP

    @property
    def rules(self) -> tuple[str, ...]:
        return tuple(
            r
            for r, on in (
                (FLOAT_RULE_NEWER_ZERO, self.newer_zero_float),
                (FLOAT_RULE_MIN_SHARES, self.min_public_shares),
            )
            if on
        )


# The behaviour every variant had before 2026-08-21. Frozen for the option
# record: continuity5 / broad8 must keep reproducing byte-identically.
LEGACY_RULESET = FloatRuleset(name="legacy")

# The owner-ratified ruleset, live on hybrid136 only.
FLOAT_INTEGRITY_RULESET = FloatRuleset(
    name="float_integrity_2026-08-21",
    newer_zero_float=True,
    min_public_shares=True,
)

VARIANT_RULESETS: dict[str, FloatRuleset] = {
    "continuity5": LEGACY_RULESET,
    "broad8": LEGACY_RULESET,
    "hybrid136": FLOAT_INTEGRITY_RULESET,
}


def ruleset_for(variant: str) -> FloatRuleset:
    """The float-integrity ruleset a variant is built under. An unknown variant
    gets LEGACY rather than an exception, so adding a taxonomy can never
    silently opt it into rules nobody ratified for it."""
    return VARIANT_RULESETS.get(variant, LEGACY_RULESET)


# ---------------------------------------------------------------------------
# Dates / quarters
# ---------------------------------------------------------------------------


def reconstitution_dates(
    first_year: int = FIRST_RECON_YEAR,
    last_year: int = LAST_RECON_YEAR,
    month: int = RECON_MONTH,
    day: int = RECON_DAY,
) -> list[date]:
    return [date(y, month, day) for y in range(first_year, last_year + 1)]


def quarter_key(d: date) -> tuple[int, int]:
    return (d.year, (d.month - 1) // 3 + 1)


def prev_quarter(qk: tuple[int, int]) -> tuple[int, int]:
    y, q = qk
    return (y - 1, 4) if q == 1 else (y, q - 1)


def quarters_preceding(d: date, n: int) -> list[tuple[int, int]]:
    """The n calendar quarters strictly preceding the quarter that contains d,
    oldest first. For d = 2026-07-01 (start of Q3) and n = 4 this is
    2025Q3, 2025Q4, 2026Q1, 2026Q2.
    """
    qk = quarter_key(d)
    out = []
    for _ in range(n):
        qk = prev_quarter(qk)
        out.append(qk)
    return list(reversed(out))


def all_frame_quarters(dates: Iterable[date], lookback: int) -> list[tuple[int, int]]:
    qs: set[tuple[int, int]] = set()
    for d in dates:
        qs.update(quarters_preceding(d, lookback))
    return sorted(qs)


# ---------------------------------------------------------------------------
# Polite fetch helpers (reuse EdgarClient's limiter/UA/backoff; new cache dirs)
# ---------------------------------------------------------------------------


def fetch_frame(client: EdgarClient, year: int, q: int, force: bool = False) -> Optional[dict]:
    """One quarterly instant frame for dei:EntityPublicFloat. Cached forever
    (a closed historical quarter's frame only ever gains late filers; the
    enumeration is re-derivable by deleting the cache file). Returns None on
    404 -- a frame with no data points is a legitimate answer for very recent
    quarters, not an error.
    """
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    path = FRAMES_DIR / f"dei_EntityPublicFloat_USD_CY{year}Q{q}I.json"
    if force or not path.exists():
        url = FRAMES_URL_TMPL.format(year=year, q=q)
        try:
            resp = client._get(url)  # same rate limiter + User-Agent + backoff
        except Exception as exc:  # noqa: BLE001
            if "404" in str(exc):
                return None
            raise
        path.write_text(resp.text)
    return json.loads(path.read_text())


def fetch_concept(
    client: EdgarClient, cik: int, taxonomy: str, concept: str, force: bool = False
) -> Optional[dict]:
    """One XBRL companyconcept document (~3 KB for the `dei` cover-page facts,
    tens of KB for a `us-gaap` statement line). Cached forever under
    data/raw/companyconcept/CIK##########_<taxonomy>_<concept>.json, so a
    re-run costs zero requests. A 404 means the registrant has never tagged
    that concept: it is recorded as a `_missing` sentinel (so the negative
    answer is cached too) and returned as None -- counted, never swallowed.
    """
    CONCEPT_DIR.mkdir(parents=True, exist_ok=True)
    path = CONCEPT_DIR / f"CIK{cik:010d}_{taxonomy}_{concept}.json"
    if force or not path.exists():
        url = CONCEPT_URL_ANY_TMPL.format(cik=cik, taxonomy=taxonomy, concept=concept)
        try:
            resp = client._get(url)  # same rate limiter + User-Agent + backoff
        except Exception as exc:  # noqa: BLE001
            if "404" in str(exc):
                path.write_text(json.dumps({"_missing": True}))
                return None
            raise
        path.write_text(resp.text)
    data = json.loads(path.read_text())
    return None if data.get("_missing") else data


def fetch_float_concept(client: EdgarClient, cik: int, force: bool = False) -> Optional[dict]:
    """Per-CIK dei:EntityPublicFloat history WITH `filed` dates (~3 KB)."""
    return fetch_concept(client, cik, "dei", "EntityPublicFloat", force=force)


# ---------------------------------------------------------------------------
# Point-in-time float selection
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FloatFact:
    cik: int
    instant: date  # `end`: the measurement instant (fiscal Q2 end)
    filed: date  # PUBLIC filing date of the document that disclosed it
    val: float
    accn: str
    form: str


def parse_float_facts(cik: int, concept: dict) -> list[FloatFact]:
    facts: list[FloatFact] = []
    for unit, rows in (concept.get("units") or {}).items():
        if unit != "USD":
            continue
        for r in rows:
            try:
                facts.append(
                    FloatFact(
                        cik=cik,
                        instant=date.fromisoformat(r["end"]),
                        filed=date.fromisoformat(r["filed"]),
                        val=float(r["val"]),
                        accn=r.get("accn", ""),
                        form=r.get("form", ""),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
    return facts


def suspect_value_flags(
    instants: list[date], values: list[float], ratio: float = SUSPECT_FLOAT_RATIO
) -> list[bool]:
    """Shared scale-error detector, used on both the frames panel and the
    per-CIK companyconcept history. Returns one flag per input value.

    Two rules:
      1. absolute band -- outside [MIN, MAX]_PLAUSIBLE_FLOAT_USD. Catches the
         big ones (M&T Bank's $2.7e16, eBay's $3.1e19 10-K/A).
      2. neighbour ratio -- a value >= `ratio` x the median of the
         registrant's own float at the immediately ADJACENT disclosure
         instants. Catches in-band errors (PEDEVCO's $3.4B where its
         neighbours are ~$30M) without punishing genuine hypergrowth
         (NVIDIA's $1.1T sits between $0.3T and $2.7T -- ratio ~1).

    Rule 2 is deliberately ONE-SIDED (upward only). A downward outlier is
    either a filer scaling error that merely costs us a candidate, or a
    genuine collapse in market value -- and genuinely collapsing companies are
    exactly the observations this universe design exists to keep in-sample
    (EXPANSION_PLAN.md §2c). Flagging downward moves would quietly delete
    them, so it is not done; the absolute floor in rule 1 is the only
    downward guard.

    Known blind spot, stated rather than papered over: a registrant that
    mis-scales the SAME way in two consecutive years validates itself under
    rule 2, so only rule 1 can catch it (M&T Bank mis-tagged both 2022 and
    2023 -- both are >1e13, so rule 1 does catch that particular pair).
    """
    return [r is not None for r in suspect_value_reasons(instants, values, ratio)]


def suspect_value_reasons(
    instants: list[date], values: list[float], ratio: float = SUSPECT_FLOAT_RATIO
) -> list[Optional[str]]:
    """Same as suspect_value_flags(), but says WHY. The distinction matters
    for honest reporting: the overwhelming majority of rejected data points
    are `zero_or_negative` -- registrants (wholly-owned financing/subsidiary
    filers with no publicly traded equity) that correctly tag a float of 0.
    Those are not tagging errors, they are simply not large caps. The rarer
    `above_ceiling` / `neighbour_jump` cases are the genuine mis-scalings.
    """
    n = len(values)
    flags: list[Optional[str]] = [None] * n
    in_band_idx = []
    for i, v in enumerate(values):
        if v <= 0:
            flags[i] = "zero_or_negative"
        elif v < MIN_PLAUSIBLE_FLOAT_USD:
            flags[i] = "below_floor"
        elif v > MAX_PLAUSIBLE_FLOAT_USD:
            flags[i] = "above_ceiling"
        else:
            in_band_idx.append(i)
    if len(in_band_idx) < 2:
        return flags
    # Iterative, MIN-of-neighbours. Both details are load-bearing:
    #   * min, not median: filers mis-scale for SEVERAL CONSECUTIVE years
    #     (Onto Innovation 2022-2025, Champion Homes 2022-2025, CoreCivic
    #     2017-2019 -- each exactly 1000x too large), and a median of the two
    #     neighbours lets two bad years vouch for each other;
    #   * iterative: once the first bad year is removed, the next one's
    #     neighbour becomes the last CLEAN value, so the whole run unwinds.
    active = set(in_band_idx)
    while True:
        by_instant: dict[date, list[float]] = defaultdict(list)
        for i in active:
            by_instant[instants[i]].append(values[i])
        ordered = sorted(by_instant)
        med_at = {d: statistics.median(by_instant[d]) for d in ordered}
        pos = {d: k for k, d in enumerate(ordered)}
        newly_bad = []
        for i in active:
            k = pos[instants[i]]
            neigh = [med_at[ordered[j]] for j in (k - 1, k + 1) if 0 <= j < len(ordered)]
            neigh = [v for v in neigh if v > 0]
            if not neigh:
                continue
            jump = values[i] / min(neigh)
            if jump >= ratio or (values[i] >= MEGA_FLOAT_USD and jump >= MEGA_JUMP_RATIO):
                newly_bad.append(i)
        if not newly_bad:
            break
        for i in newly_bad:
            flags[i] = "neighbour_jump"
            active.discard(i)
        if len(active) < 2:
            break
    return flags


def sanitize_facts(facts: list[FloatFact]) -> tuple[list[FloatFact], list[FloatFact]]:
    """Split a CIK's float facts into (clean, suspect). Suspect facts are
    DROPPED from selection and REPORTED -- never rescaled, because the intended
    magnitude is not recoverable from the filing's XBRL.
    """
    clean, suspect_pairs = sanitize_facts_with_reasons(facts)
    return clean, [f for f, _ in suspect_pairs]


def sanitize_facts_with_reasons(
    facts: list[FloatFact],
) -> tuple[list[FloatFact], list[tuple[FloatFact, str]]]:
    if not facts:
        return [], []
    ordered = sorted(facts, key=lambda f: (f.instant, f.filed))
    reasons = suspect_value_reasons([f.instant for f in ordered], [f.val for f in ordered])
    clean = [f for f, r in zip(ordered, reasons) if r is None]
    suspect = [(f, r) for f, r in zip(ordered, reasons) if r is not None]
    return clean, suspect


def pit_float_asof(
    facts: list[FloatFact],
    asof: date,
    max_staleness_days: int = MAX_FLOAT_STALENESS_DAYS,
) -> Optional[FloatFact]:
    """THE point-in-time primitive.

    Returns the float fact that was the most recent PUBLIC information at
    `asof`, or None. A fact qualifies only if `filed < asof` -- strictly
    before, so a filing made ON the reconstitution date is not used (intraday
    publication time is unknown; the conservative direction is to exclude).
    Among qualifying facts the latest measurement instant wins, and for the
    same instant the latest `filed` wins (i.e. an amended 10-K/A supersedes
    the original). Facts whose instant is older than `max_staleness_days` are
    not usable.
    """
    usable = [
        f
        for f in facts
        if f.filed < asof
        and f.instant < asof
        and (asof - f.instant).days <= max_staleness_days
    ]
    if not usable:
        return None
    return max(usable, key=lambda f: (f.instant, f.filed))


# ---------------------------------------------------------------------------
# The two ratified float-integrity rules (owner, in chat, 2026-08-21).
# Live on `hybrid136` only -- see FloatRuleset / VARIANT_RULESETS above.
# ---------------------------------------------------------------------------


def newest_public_float_facts(facts: list[FloatFact], asof: date) -> list[FloatFact]:
    """Every fact tied for "the registrant's most recent float disclosure that
    was already public at `asof`".

    Ordering is the SAME key pit_float_asof() ranks by -- (instant, filed) --
    so "newest" means the same thing to both, and a 10-K/A supersedes the 10-K
    it amends. NO staleness filter is applied here, and that is deliberate: a
    staleness cap would be a no-op anyway (if the newest disclosure is too old
    to use, every older one is older still, so pit_float_asof() already returns
    None), and leaving it out keeps this function a literal reading of "the
    most recent public disclosure".

    Returns a LIST, not a single fact, so that a tie can be adjudicated by the
    caller rather than by whichever row max() happened to see first.
    """
    public = [f for f in facts if f.filed < asof and f.instant < asof]
    if not public:
        return []
    key = max((f.instant, f.filed) for f in public)
    return [f for f in public if (f.instant, f.filed) == key]


def newer_zero_float_asof(facts: list[FloatFact], asof: date) -> Optional[FloatFact]:
    """RULE 1. The zero-valued fact that makes this registrant "no public
    float" at `asof`, or None.

    Fires only when the registrant's most recent ALREADY-PUBLIC float
    disclosure is exactly 0. Exactly, not `<= 0`: a NEGATIVE float is a tagging
    error, not a registrant saying "I have no public float", and the legacy
    `zero_or_negative` sanitizer keeps handling those (there are none anywhere
    in this build's diligence set, so the distinction costs nothing here and is
    only stated so a future maintainer does not widen it by accident).

    If the newest key is a tie between a zero and a nonzero fact the rule does
    NOT fire -- the disclosure is ambiguous, and an ambiguous signal must not
    silently remove a registrant.
    """
    newest = newest_public_float_facts(facts, asof)
    if not newest or not all(f.val == 0 for f in newest):
        return None
    return newest[0]


def _concept_rows(concept: Optional[dict], unit: str) -> list[dict]:
    """Flatten one companyconcept document into dated rows. `filed_date` is the
    parsed `filed` string (None when EDGAR omitted it) -- the point-in-time
    filter for rule 2 depends on it, so it is parsed once, here."""
    rows: list[dict] = []
    for u, rr in ((concept or {}).get("units") or {}).items():
        if u != unit:
            continue
        for r in rr:
            try:
                filed = str(r.get("filed", "") or "")
                rows.append(
                    {
                        "end": date.fromisoformat(r["end"]),
                        "val": float(r["val"]),
                        "accn": str(r.get("accn", "")),
                        "filed": filed,
                        "filed_date": date.fromisoformat(filed) if filed else None,
                        "form": str(r.get("form", "")),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
    return sorted(rows, key=lambda r: (r["end"], r["filed"]))


def cached_concept(cik: int, taxonomy: str, concept: str) -> tuple[Optional[dict], bool]:
    """Read a companyconcept document from the on-disk cache. NEVER fetches.

    Returns (document, was_cached). `(None, True)` means the negative answer is
    cached -- the registrant has never tagged that concept. `(None, False)`
    means nobody has ever asked, so the rule that depends on it must abstain
    rather than guess.
    """
    path = CONCEPT_DIR / f"CIK{cik:010d}_{taxonomy}_{concept}.json"
    if not path.exists():
        return None, False
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return None, False
    return (None, True) if data.get("_missing") else (data, True)


def load_cached_shares(ciks: Iterable[int]) -> dict[int, list[dict]]:
    """Cover-page share-count histories for every CIK whose companyconcept
    document is ALREADY on disk. Zero network requests, by design (see the
    FloatRuleset comment block). A CIK absent from the returned mapping is
    "untestable", which is materially different from "tested and passed", and
    the two are reported separately.
    """
    out: dict[int, list[dict]] = {}
    for cik in ciks:
        doc, cached = cached_concept(int(cik), "dei", SHARES_CONCEPT)
        if not cached:
            continue
        out[int(cik)] = _concept_rows(doc, "shares")
    return out


def pit_shares_asof(
    rows: list[dict],
    asof: date,
    max_staleness_days: int = MIN_SHARES_MAX_STALENESS_DAYS,
) -> tuple[Optional[float], str]:
    """The registrant's most recent PUBLIC cover-page share count at `asof`.

    Returns (shares, source) or (None, why-not). Point-in-time on the same
    terms as the float primitive: a row counts only if `filed < asof` and
    `end < asof`. A row EDGAR gave no `filed` date for cannot be shown to have
    been public and is not used.

    Multi-class registrants that tag one undimensioned row per share class on
    the same cover page are SUMMED, matching `_match_concept_value()`'s
    convention so the rule and the 6.7 screen agree by construction.

    A total of exactly 0 returns (None, "value_is_zero") -- untestable, not
    disqualifying. 0 shares outstanding on a cover page is far more often a
    placeholder than a fact, and treating it as disqualifying would be a
    removal on the strength of an absent number. (Energy Transfer Operating is
    the live example in this build: it tags 0 units on its final covers, and it
    is rule 1, not rule 2, that establishes it has no public equity.)
    """
    public = [
        r
        for r in rows
        if r.get("filed_date") is not None and r["filed_date"] < asof and r["end"] < asof
    ]
    if not public:
        return None, "no_public_shares_fact"
    end = max(r["end"] for r in public)
    if (asof - end).days > max_staleness_days:
        return None, f"stale_gt_{max_staleness_days}d"
    at_end = [r for r in public if r["end"] == end]
    filed = max(r["filed_date"] for r in at_end)
    latest = [r for r in at_end if r["filed_date"] == filed]
    total = sum({r["val"] for r in latest})
    if total <= 0:
        return None, "value_is_zero"
    return total, f"{end.isoformat()}/filed {filed.isoformat()}/{latest[0]['accn']}"


def below_min_public_shares_asof(
    rows: list[dict], asof: date, threshold: int = MIN_PUBLIC_SHARES_FOR_MEMBERSHIP
) -> tuple[bool, Optional[float], str]:
    """RULE 2. (fires?, shares, source). Fires only on a resolvable, public,
    non-stale, positive share count strictly below `threshold`."""
    shares, how = pit_shares_asof(rows, asof)
    if shares is None:
        return False, None, how
    return shares < threshold, shares, how


# ---------------------------------------------------------------------------
# Eligibility (backward-only)
# ---------------------------------------------------------------------------


def eligible_quarters_covered(
    periodic_filing_dates: Iterable[date], asof: date, n_quarters: int = MIN_ELIGIBLE_QUARTERS
) -> int:
    """How many of the `n_quarters` calendar quarters immediately preceding
    `asof` contain at least one 10-K/10-Q filed strictly before `asof`.

    Backward-only by construction: nothing after `asof` is consulted, so a
    company that stops filing the day after `asof` is still eligible AT
    `asof` -- which is the point (EXPANSION_PLAN.md §2c: no forward-looking
    continuity condition, ever).
    """
    wanted = set(quarters_preceding(asof, n_quarters))
    seen = {quarter_key(d) for d in periodic_filing_dates if d < asof and quarter_key(d) in wanted}
    return len(seen)


def is_eligible(
    periodic_filing_dates: Iterable[date], asof: date, n_quarters: int = MIN_ELIGIBLE_QUARTERS
) -> bool:
    dates = list(periodic_filing_dates)
    return eligible_quarters_covered(dates, asof, n_quarters) == n_quarters


def count_periodic_in_window(
    periodic_filing_dates: Iterable[date], asof: date, n_quarters: int = MIN_ELIGIBLE_QUARTERS
) -> int:
    """Lenient comparison rule: total periodic filings in the same window
    (>= 8 filings in 8 quarters, without requiring one per quarter). Reported
    alongside the strict rule so the owner can see what the choice costs."""
    qs = set(quarters_preceding(asof, n_quarters))
    return sum(1 for d in periodic_filing_dates if d < asof and quarter_key(d) in qs)


# ---------------------------------------------------------------------------
# Manual exclusions (documented, versioned, never silent)
# ---------------------------------------------------------------------------
#
# WHY THIS EXISTS. The automated sanitizer is a WITHIN-REGISTRANT rule: it
# compares a float fact against the same registrant's temporally adjacent
# disclosures. A registrant that mis-scales its ENTIRE float history the same
# way has no clean neighbour, so the rule is structurally blind to it -- this
# was recorded as the open residual risk in E2_UNIVERSE_REPORT.md's "not
# verified" list, and the F1 audit found three live instances. The compensating
# control (`audit_float_scale()` below) is a SCREEN, not an authority: it can
# only say "this looks wrong". Anything actually removed from the universe is
# removed HERE, from a hand-maintained CSV, with the evidence written down.
#
# RULES OF THE FILE
#   * one row per (cik, scope); a row removes that CIK from the candidate pool
#     at the reconstitution dates it covers;
#   * an excluded CIK is written to the variant's reject log with the reason
#     `manual_exclusion` and printed in the report -- never dropped silently;
#   * `applies_to` scopes the row to specific variants (semicolon-separated).
#     It defaults to the ratified variant only, because continuity5/broad8 are
#     the frozen option record behind the owner's decision and must keep
#     reproducing byte-identically;
#   * `effective_from` / `effective_to` (inclusive, ISO reconstitution dates,
#     blank = unbounded) scope the row in TIME. A company that was a genuine
#     large cap and later stopped having public equity gets a dated row, not a
#     blanket one;
#   * POINT-IN-TIME GUARD: if a row carries both `evidence_filed` and
#     `effective_from`, the evidence must have been PUBLIC before the first
#     date the exclusion bites (`evidence_filed < effective_from`), otherwise
#     loading raises. This stops a future maintainer from quietly encoding
#     hindsight ("we now know it was acquired") as a selection rule.
#
# An UNBOUNDED row (no effective_from) is reserved for the case where the datum
# was never valid at any date -- a tagging error, not a change in the world.
# Correcting a wrong input is not look-ahead: it imports no information about
# the registrant's future, only about its XBRL. Dated rows are the ones that
# need the PIT guard, and they get it.
#
# SUPERSEDED-BY-RULE ANNOTATION (added 2026-08-21 with the two float-integrity
# rules). Three of these rows -- EIDP, Dow Chemical, Energy Transfer Operating
# -- were the DISCOVERY that motivated rules 1 and 2. Now that the rules exist,
# a systematic filter covers those cases. The rows are deliberately NOT
# deleted: deleting them would erase the discovery and leave the report
# claiming a rule appeared from nowhere. Instead they carry
# `superseded_by_rule`, naming the rule that now covers them, so the audit
# trail shows BOTH the hand-found case and its generalisation. A superseded row
# still bites (it is still a correct removal); the annotation is provenance,
# not a switch. The three 1000x mis-scaling rows (MedEquities, Mister Car Wash,
# ASV Holdings) are NOT covered by either rule and stay unannotated and active.
MANUAL_EXCLUSIONS_PATH = OUT_DIR / "manual_exclusions.csv"
MANUAL_EXCLUSION_COLUMNS = (
    "cik",
    "name",
    "reason",
    "evidence",
    "evidence_filed",
    "effective_from",
    "effective_to",
    "applies_to",
    "date_added",
)
# Optional because its absence cannot cause a wrong removal -- it is pure
# provenance. A file written before 2026-08-21 still loads.
MANUAL_EXCLUSION_OPTIONAL_COLUMNS = ("superseded_by_rule",)


@dataclass(frozen=True)
class ManualExclusion:
    cik: int
    name: str = ""
    reason: str = ""
    evidence: str = ""
    evidence_filed: Optional[date] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    applies_to: tuple[str, ...] = (RATIFIED_VARIANT,)
    date_added: str = ""
    # Names of the ratified float-integrity rules that now cover this row.
    # Empty = the row is the only thing removing this registrant.
    superseded_by_rule: tuple[str, ...] = ()

    def applies(self, variant: str, d: date) -> bool:
        if variant not in self.applies_to:
            return False
        if self.effective_from is not None and d < self.effective_from:
            return False
        if self.effective_to is not None and d > self.effective_to:
            return False
        return True

    def window_str(self) -> str:
        lo = self.effective_from.isoformat() if self.effective_from else "…"
        hi = self.effective_to.isoformat() if self.effective_to else "…"
        return "all dates" if lo == "…" and hi == "…" else f"{lo} → {hi}"


def _opt_date(v) -> Optional[date]:
    s = str(v or "").strip()
    if not s or s.lower() in ("nan", "none"):
        return None
    return date.fromisoformat(s)


def load_manual_exclusions(path: Optional[Path] = None) -> list[ManualExclusion]:
    """Read data/universe_e2_candidates/manual_exclusions.csv. A missing file
    is a legitimate state (no exclusions) and returns []. A malformed row
    RAISES -- a silently-ignored exclusion row is exactly the failure this
    mechanism exists to prevent."""
    path = path or MANUAL_EXCLUSIONS_PATH
    if not path.exists():
        return []
    df = pd.read_csv(path, dtype=str, keep_default_na=False, comment="#")
    missing = [c for c in MANUAL_EXCLUSION_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing required column(s) {missing}")
    out: list[ManualExclusion] = []
    for i, r in enumerate(df.to_dict("records"), start=2):  # +1 header, +1 1-based
        cik_raw = str(r["cik"]).strip()
        if not cik_raw:
            continue
        try:
            cik = int(cik_raw)
        except ValueError as exc:
            raise ValueError(f"{path} line {i}: cik {cik_raw!r} is not an integer") from exc
        if not str(r["reason"]).strip() or not str(r["evidence"]).strip():
            raise ValueError(
                f"{path} line {i} (cik {cik}): both `reason` and `evidence` are "
                "mandatory -- an exclusion without written evidence is not "
                "auditable and is refused."
            )
        ex = ManualExclusion(
            cik=cik,
            name=str(r["name"]).strip(),
            reason=str(r["reason"]).strip(),
            evidence=str(r["evidence"]).strip(),
            evidence_filed=_opt_date(r["evidence_filed"]),
            effective_from=_opt_date(r["effective_from"]),
            effective_to=_opt_date(r["effective_to"]),
            applies_to=tuple(
                v.strip() for v in str(r["applies_to"] or RATIFIED_VARIANT).split(";") if v.strip()
            )
            or (RATIFIED_VARIANT,),
            date_added=str(r["date_added"]).strip(),
            superseded_by_rule=tuple(
                v.strip()
                for v in str(r.get("superseded_by_rule", "") or "").split(";")
                if v.strip()
            ),
        )
        for v in ex.applies_to:
            if v not in TAXONOMIES:
                raise ValueError(f"{path} line {i} (cik {cik}): unknown variant {v!r} in applies_to")
        for v in ex.superseded_by_rule:
            if v not in FLOAT_INTEGRITY_RULE_NAMES:
                raise ValueError(
                    f"{path} line {i} (cik {cik}): unknown rule {v!r} in "
                    f"superseded_by_rule; known rules are "
                    f"{', '.join(FLOAT_INTEGRITY_RULE_NAMES)}"
                )
        if ex.evidence_filed and ex.effective_from and ex.evidence_filed >= ex.effective_from:
            raise ValueError(
                f"{path} line {i} (cik {cik}): POINT-IN-TIME VIOLATION -- evidence "
                f"filed {ex.evidence_filed} is not public before effective_from "
                f"{ex.effective_from}. A dated exclusion may only rest on evidence "
                "that was already public at the first date it bites."
            )
        out.append(ex)
    return out


def exclusions_in_force(
    exclusions: Iterable[ManualExclusion], variant: str, d: date
) -> dict[int, ManualExclusion]:
    return {ex.cik: ex for ex in exclusions if ex.applies(variant, d)}


# ---------------------------------------------------------------------------
# Stage 1: frames enumeration
# ---------------------------------------------------------------------------


def stage_frames(client: EdgarClient, dates: list[date], lookback: int) -> pd.DataFrame:
    quarters = all_frame_quarters(dates, lookback)
    rows = []
    missing = []
    for (y, q) in quarters:
        data = fetch_frame(client, y, q)
        if data is None:
            missing.append(f"CY{y}Q{q}I")
            continue
        for r in data.get("data", []):
            rows.append(
                {
                    "cik": int(r["cik"]),
                    "entity_name": r.get("entityName", ""),
                    "instant": r["end"],
                    "val": float(r["val"]),
                    "accn": r.get("accn", ""),
                    "frame": f"CY{y}Q{q}I",
                    "loc": r.get("loc", ""),
                }
            )
    df = pd.DataFrame(rows)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(CACHE_DIR / "frames_panel.parquet", index=False)
    (CACHE_DIR / "frames_missing.json").write_text(json.dumps(missing, indent=1))
    block = coregistrant_float_blocklist(df)
    pd.DataFrame(
        [{"cik": c, "accn": a} for c, a in sorted(block)]
    ).to_parquet(CACHE_DIR / "coregistrant_blocklist.parquet", index=False)
    print(f"[frames] co-registrant float blocklist: {len(block)} (cik, accession) pairs")
    print(
        f"[frames] {len(quarters)} quarterly frames "
        f"({quarters[0]} .. {quarters[-1]}), {len(missing)} empty/404, "
        f"{len(df):,} data points, {df['cik'].nunique():,} distinct CIKs"
    )
    return df


def coregistrant_float_blocklist(frames_panel: pd.DataFrame) -> set[tuple[int, str]]:
    """(cik, accession) pairs whose float value is NOT that registrant's own.

    Utilities and holding companies file COMBINED 10-Ks covering a parent and
    several wholly-owned subsidiary co-registrants. The subsidiaries have no
    publicly traded equity at all, but their XBRL carries the PARENT's
    cover-page float -- verified case: Kentucky Utilities (CIK 55387) reports
    $19.73B for 2015-06-30 under accession 0000922224-16-000130, which is
    PPL Corporation's (CIK 922224) own accession and PPL's own float. Nothing
    in the float value, the SIC code (4911, a real utility), or `entityType`
    ("operating") distinguishes it -- and with only one float fact ever, the
    within-registrant plausibility rule has nothing to compare against. So
    Kentucky Utilities entered the 2016 broad8 utilities bucket as a "large
    cap" despite having no public shares.

    Detector: the identical (accession, instant, value) triple reported by
    more than one CIK. The registrant whose CIK matches the accession's own
    filer prefix keeps the value; the co-registrants lose it. If no CIK
    matches the prefix (an agent-transmitted combined filing) the value cannot
    be attributed and every CIK in the triple loses it -- conservative, and
    rare enough to be worth counting rather than guessing.

    This is exact and PIT-safe: it uses only the contents of one filing.
    """
    block: set[tuple[int, str]] = set()
    grouped = frames_panel.groupby(["accn", "instant", "val"])["cik"].unique()
    for (accn, _instant, _val), ciks in grouped.items():
        if len(ciks) < 2:
            continue
        try:
            filer = int(str(accn)[:10])
        except (TypeError, ValueError):
            filer = -1
        ciks = [int(c) for c in ciks]
        if filer in ciks:
            block.update((c, accn) for c in ciks if c != filer)
        else:
            block.update((c, accn) for c in ciks)
    return block


def shortlist_per_date(
    frames_panel: pd.DataFrame, dates: list[date], per_date: int
) -> pd.DataFrame:
    """Superset shortlist: at each date, the top `per_date` CIKs by float among
    facts whose INSTANT precedes the date (a superset of the PIT-valid set,
    because filed >= instant always). Diligence is then run on the union.

    Why a superset: PIT validity needs `filed`, which frames do not carry, so
    the shortlist has to be deliberately generous and the real PIT filter runs
    later on companyconcept data. Selection can only ever REMOVE candidates
    relative to this list, so as long as no selected member sits near the
    `per_date` boundary (reported as "shortlist headroom") the truncation
    cannot have changed membership.
    """
    fp = frames_panel.copy()
    fp["instant_d"] = pd.to_datetime(fp["instant"]).dt.date
    # Sanitize at ENUMERATION too, not only at selection: an in-band scale
    # error (e.g. a $1T value from a company whose real float is $10M) would
    # otherwise occupy one of the top-N shortlist slots and push a genuine
    # large cap out of the diligence set entirely.
    keep = []
    reason_counts: Counter = Counter()
    for cik, g in fp.groupby("cik", sort=False):
        g = g.sort_values("instant_d")
        reasons = suspect_value_reasons(list(g["instant_d"]), [float(v) for v in g["val"]])
        reason_counts.update(r for r in reasons if r)
        keep.extend(idx for idx, r in zip(g.index, reasons) if r is None)
    fp = fp.loc[sorted(keep)]
    (CACHE_DIR / "frames_sanitation.json").write_text(
        json.dumps({"total_points": len(frames_panel), "dropped": dict(reason_counts)}, indent=1)
    )
    print(
        f"[shortlist] frames sanitation dropped {sum(reason_counts.values()):,} of "
        f"{len(frames_panel):,} data points: {dict(reason_counts)}"
    )
    out = []
    cut_rows = []
    for d in dates:
        lo = d - timedelta(days=MAX_FLOAT_STALENESS_DAYS)
        sub = fp[(fp["instant_d"] < d) & (fp["instant_d"] >= lo)]
        # MAX over the window, not the latest instant: the latest instant in
        # the window may be a fact that was not yet FILED at d (frames carry no
        # `filed`), and for a shrinking company the older value is the larger
        # one. Taking the max is the most inclusive choice, so the superset
        # property ("selection can only remove") is preserved in both
        # directions.
        best = sub.sort_values(["cik", "val"]).groupby("cik", as_index=False).last()
        best = best.sort_values("val", ascending=False).head(per_date)
        best = best.reset_index(drop=True)
        best["superset_rank"] = best.index + 1
        best["recon_date"] = d.isoformat()
        out.append(best[["cik", "entity_name", "val", "superset_rank", "recon_date"]])
        ranked_all = (
            sub.sort_values(["cik", "val"]).groupby("cik", as_index=False).last()
            .sort_values("val", ascending=False).reset_index(drop=True)
        )
        cut_rows.append(
            {
                "recon_date": d.isoformat(),
                "n_candidates": len(ranked_all),
                "shortlist_n": per_date,
                "first_excluded_float_usd": (
                    float(ranked_all.iloc[per_date]["val"]) if len(ranked_all) > per_date else 0.0
                ),
            }
        )
    sl = pd.concat(out, ignore_index=True)
    sl.to_parquet(CACHE_DIR / "shortlist_per_date.parquet", index=False)
    # The float of the first registrant NOT shortlisted at each date. Any CIK
    # outside the shortlist has a point-in-time float no larger than this
    # (PIT value <= window-max value), so if the weakest selected member's
    # float exceeds it, the shortlist truncation provably cannot have changed
    # membership. Reported as "shortlist headroom" (§6.5).
    pd.DataFrame(cut_rows).to_parquet(CACHE_DIR / "shortlist_cutoff.parquet", index=False)
    print(
        f"[shortlist] top {per_date}/date over {len(dates)} dates -> "
        f"{sl['cik'].nunique():,} distinct CIKs for full diligence"
    )
    return sl


# ---------------------------------------------------------------------------
# Stage 2: per-CIK diligence (companyconcept + submissions)
# ---------------------------------------------------------------------------


@dataclass
class CikProfile:
    cik: int
    name: str = ""
    sic: Optional[int] = None
    sic_desc: str = ""
    entity_type: str = ""
    tickers: list[str] = field(default_factory=list)
    exchanges: list[str] = field(default_factory=list)
    former_names: list[str] = field(default_factory=list)
    periodic_dates: list[date] = field(default_factory=list)
    last_periodic: Optional[date] = None
    first_periodic: Optional[date] = None
    n_float_facts: int = 0
    n_suspect_facts: int = 0
    has_float_concept: bool = False
    fetch_error: str = ""


def stage_diligence(
    client: EdgarClient, ciks: list[int], history_cutoff: date
) -> tuple[dict[int, CikProfile], dict[int, list[FloatFact]], list[dict]]:
    profiles: dict[int, CikProfile] = {}
    facts_by_cik: dict[int, list[FloatFact]] = {}
    suspect_rows: list[dict] = []
    for i, cik in enumerate(ciks, 1):
        p = CikProfile(cik=cik)
        try:
            sub = client.get_submissions(cik)
            p.name = sub.get("name", "")
            p.sic = int(sub["sic"]) if str(sub.get("sic", "")).strip().isdigit() else None
            p.sic_desc = sub.get("sicDescription", "") or ""
            p.entity_type = sub.get("entityType", "") or ""
            # EDGAR returns nulls inside these arrays for some registrants
            # (e.g. an exchange-less OTC listing), so coerce rather than trust.
            p.tickers = [str(t) for t in (sub.get("tickers") or []) if t]
            p.exchanges = [str(e) for e in (sub.get("exchanges") or []) if e]
            p.former_names = [
                str(fn.get("name") or "") for fn in (sub.get("formerNames") or [])
            ]
            recent = client.get_effective_recent(cik, history_cutoff)
            forms = recent.get("form", [])
            fdates = recent.get("filingDate", [])
            pds = [
                date.fromisoformat(fd)
                for f, fd in zip(forms, fdates)
                if f in PERIODIC_FORMS and fd
            ]
            p.periodic_dates = sorted(pds)
            if p.periodic_dates:
                p.first_periodic = p.periodic_dates[0]
                p.last_periodic = p.periodic_dates[-1]
        except Exception as exc:  # noqa: BLE001
            p.fetch_error = f"submissions: {exc!r}"
        try:
            concept = fetch_float_concept(client, cik)
            if concept is not None:
                p.has_float_concept = True
                raw = parse_float_facts(cik, concept)
                clean, suspect = sanitize_facts_with_reasons(raw)
                # RAW facts are what get persisted and passed to selection --
                # sanitation is re-run per reconstitution date, backward-only.
                # `clean`/`suspect` here are the whole-history diagnostic used
                # for the report's data-quality section.
                facts_by_cik[cik] = raw
                p.n_float_facts = len(clean)
                p.n_suspect_facts = len(suspect)
                for f, reason in suspect:
                    suspect_rows.append(
                        {
                            "cik": cik,
                            "name": p.name,
                            "instant": f.instant.isoformat(),
                            "filed": f.filed.isoformat(),
                            "val": f.val,
                            "accn": f.accn,
                            "form": f.form,
                            "reason": reason,
                        }
                    )
            else:
                facts_by_cik[cik] = []
        except Exception as exc:  # noqa: BLE001
            p.fetch_error += f" | concept: {exc!r}"
            facts_by_cik[cik] = []
        profiles[cik] = p
        if i % 50 == 0:
            print(f"  [diligence] {i}/{len(ciks)} CIKs (net GETs so far: {client.request_count})")
    _persist_diligence(profiles, facts_by_cik, suspect_rows)
    return profiles, facts_by_cik, suspect_rows


def _persist_diligence(profiles, facts_by_cik, suspect_rows) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "cik": p.cik,
                "name": p.name,
                "sic": p.sic,
                "sic_desc": p.sic_desc,
                "entity_type": p.entity_type,
                "tickers": ",".join(p.tickers),
                "exchanges": ",".join(p.exchanges),
                "former_names": " | ".join(p.former_names),
                "n_periodic": len(p.periodic_dates),
                "first_periodic": p.first_periodic.isoformat() if p.first_periodic else "",
                "last_periodic": p.last_periodic.isoformat() if p.last_periodic else "",
                "n_float_facts": p.n_float_facts,
                "n_suspect_facts": p.n_suspect_facts,
                "has_float_concept": p.has_float_concept,
                "fetch_error": p.fetch_error,
            }
            for p in profiles.values()
        ]
    ).to_parquet(CACHE_DIR / "cik_profiles.parquet", index=False)
    pd.DataFrame(
        [
            {
                "cik": f.cik,
                "instant": f.instant.isoformat(),
                "filed": f.filed.isoformat(),
                "val": f.val,
                "accn": f.accn,
                "form": f.form,
            }
            for fs in facts_by_cik.values()
            for f in fs
        ]
    ).to_parquet(CACHE_DIR / "float_facts_pit.parquet", index=False)
    pd.DataFrame(suspect_rows).to_parquet(CACHE_DIR / "suspect_float_facts.parquet", index=False)
    pd.DataFrame(suspect_rows).to_csv(CACHE_DIR / "suspect_float_facts.csv", index=False)


def load_diligence() -> tuple[dict[int, CikProfile], dict[int, list[FloatFact]], list[dict]]:
    prof_df = pd.read_parquet(CACHE_DIR / "cik_profiles.parquet")
    facts_df = pd.read_parquet(CACHE_DIR / "float_facts_pit.parquet")
    susp_df = pd.read_parquet(CACHE_DIR / "suspect_float_facts.parquet")
    profiles: dict[int, CikProfile] = {}
    for r in prof_df.to_dict("records"):
        profiles[int(r["cik"])] = CikProfile(
            cik=int(r["cik"]),
            name=r["name"],
            sic=int(r["sic"]) if pd.notna(r["sic"]) else None,
            sic_desc=r["sic_desc"],
            entity_type=r["entity_type"],
            tickers=[t for t in str(r["tickers"]).split(",") if t],
            exchanges=[t for t in str(r["exchanges"]).split(",") if t],
            former_names=[t for t in str(r["former_names"]).split(" | ") if t],
            periodic_dates=[],
            last_periodic=date.fromisoformat(r["last_periodic"]) if r["last_periodic"] else None,
            first_periodic=date.fromisoformat(r["first_periodic"]) if r["first_periodic"] else None,
            n_float_facts=int(r["n_float_facts"]),
            n_suspect_facts=int(r["n_suspect_facts"]),
            has_float_concept=bool(r["has_float_concept"]),
            fetch_error=r["fetch_error"],
        )
    facts_by_cik: dict[int, list[FloatFact]] = defaultdict(list)
    for r in facts_df.to_dict("records"):
        facts_by_cik[int(r["cik"])].append(
            FloatFact(
                cik=int(r["cik"]),
                instant=date.fromisoformat(r["instant"]),
                filed=date.fromisoformat(r["filed"]),
                val=float(r["val"]),
                accn=r["accn"],
                form=r["form"],
            )
        )
    # periodic dates are re-read from the (already cached) submissions files
    return profiles, dict(facts_by_cik), susp_df.to_dict("records")


def load_periodic_dates(client: EdgarClient, ciks: list[int], history_cutoff: date) -> dict[int, list[date]]:
    """Re-read periodic filing dates from the on-disk submissions cache (no
    network unless a cache file is stale/absent)."""
    out: dict[int, list[date]] = {}
    for cik in ciks:
        try:
            recent = client.get_effective_recent(cik, history_cutoff)
            out[cik] = sorted(
                date.fromisoformat(fd)
                for f, fd in zip(recent.get("form", []), recent.get("filingDate", []))
                if f in PERIODIC_FORMS and fd
            )
        except Exception:  # noqa: BLE001
            out[cik] = []
    return out


# ---------------------------------------------------------------------------
# Stage 3: selection
# ---------------------------------------------------------------------------


def build_membership(
    taxonomy: str,
    dates: list[date],
    shortlist: pd.DataFrame,
    profiles: dict[int, CikProfile],
    facts_by_cik: dict[int, list[FloatFact]],
    periodic: dict[int, list[date]],
    coregistrant_blocklist: Optional[set[tuple[int, str]]] = None,
    exclusions: Iterable[ManualExclusion] = (),
    shares_by_cik: Optional[dict[int, list[dict]]] = None,
    ruleset: Optional[FloatRuleset] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (panel, rejects). `panel` has one row per (recon_date, member).

    `exclusions` are the documented manual removals (see MANUAL_EXCLUSIONS_PATH).
    They are applied FIRST in the reason chain so that an excluded registrant
    always shows up in the reject log as `manual_exclusion` rather than being
    attributed to whatever filter it would also have failed.

    The two ratified float-integrity rules are applied ONLY if this variant's
    FloatRuleset turns them on (`ruleset_for`). continuity5 / broad8 are on the
    LEGACY ruleset and are therefore bit-for-bit unaffected by this argument or
    by `shares_by_cik`.

    `shares_by_cik` is the already-cached cover-page share history that rule 2
    reads (see load_cached_shares -- zero network). Omitting it does not
    silently disable the rule's bookkeeping: every candidate the rule could not
    test is counted, and the counts are reported.

    A stratified taxonomy (TAXONOMY_STRATA) additionally emits a `stratum`
    column; the unstratified option-record variants emit exactly the columns
    they always did.
    """
    sectors, K = TAXONOMIES[taxonomy]
    strata = TAXONOMY_STRATA.get(taxonomy)
    # `ruleset` is an explicit override for counterfactual builds only (the
    # "what would this variant look like WITHOUT the ratified rules?" panel the
    # report prints). Production builds pass None and get the variant's own.
    ruleset = ruleset if ruleset is not None else ruleset_for(taxonomy)
    shares_by_cik = shares_by_cik or {}
    exclusions = list(exclusions)
    sl_by_date = {
        d: dict(zip(g["cik"], g["superset_rank"]))
        for d, g in shortlist.assign(
            _d=pd.to_datetime(shortlist["recon_date"]).dt.date
        ).groupby("_d")
    }
    panel_rows, reject_rows = [], []
    for d in dates:
        excluded_now = exclusions_in_force(exclusions, taxonomy, d)
        cand = []
        for cik, srank in sl_by_date.get(d, {}).items():
            p = profiles.get(cik)
            if p is None:
                continue
            reason = None
            # Sanitation is itself POINT-IN-TIME: a float value is judged for
            # plausibility only against disclosures that were ALREADY PUBLIC
            # at d. Sanitizing against the registrant's full (post-d) history
            # would let a later filing decide an earlier date's membership,
            # which is exactly the kind of quiet look-ahead this phase exists
            # to prevent.
            blocked = coregistrant_blocklist or set()
            facts_pre_d = [
                f
                for f in facts_by_cik.get(cik, [])
                if f.filed < d and (cik, f.accn) not in blocked
            ]
            clean_pre_d, _ = sanitize_facts_with_reasons(facts_pre_d)
            fact = pit_float_asof(clean_pre_d, d)
            sector = sic_to_sector(p.sic, taxonomy)
            # ---- the two ratified float-integrity rules (hybrid136 only) ----
            # Both are evaluated only once a positive float has actually been
            # selected, so a `newer_zero_float` / `below_min_public_shares`
            # entry in the reject log always means "THIS RULE is what removed
            # the row", never "it would have failed something else anyway".
            # BOTH rules are evaluated even when the first already fires: a row
            # that two independent signals condemn is a materially stronger
            # audit record than one that stops at the first hit, and the
            # supersession table in the report needs to know which of the two
            # covers which date.
            rule_hits: list[str] = []
            rule_notes: list[str] = []
            if fact is not None and ruleset.newer_zero_float:
                z = newer_zero_float_asof(facts_pre_d, d)
                if z is not None:
                    rule_hits.append(FLOAT_RULE_NEWER_ZERO)
                    rule_notes.append(
                        f"most recent public float disclosure is 0 (instant "
                        f"{z.instant.isoformat()}, filed {z.filed.isoformat()}, "
                        f"{z.form} {z.accn}); it supersedes ${fact.val:,.0f} "
                        f"measured {fact.instant.isoformat()}"
                    )
            if fact is not None and ruleset.min_public_shares:
                fires, sh, how = below_min_public_shares_asof(
                    shares_by_cik.get(cik, []), d, ruleset.min_public_shares_threshold
                )
                if fires:
                    rule_hits.append(FLOAT_RULE_MIN_SHARES)
                    rule_notes.append(
                        f"most recent public cover-page share count is {sh:,.0f} "
                        f"(< {ruleset.min_public_shares_threshold:,}) at {how}"
                    )
            rule_hit = rule_hits[0] if rule_hits else ""
            rule_evidence = " | ".join(rule_notes)
            if cik in excluded_now:
                reason = "manual_exclusion"
            elif p.fetch_error:
                reason = "fetch_error"
            elif not p.has_float_concept:
                reason = "no_float_concept"
            elif fact is None:
                reason = "no_pit_valid_float"
            elif rule_hit:
                reason = rule_hit
            elif p.entity_type and p.entity_type != "operating":
                reason = f"entity_type={p.entity_type}"
            elif p.sic in NON_OPERATING_SIC:
                reason = f"non_operating_sic_{p.sic}"
            elif sector == EXCLUDED:
                reason = f"sector_excluded_sic_{p.sic}"
            elif not is_eligible(periodic.get(cik, []), d):
                reason = "ineligible_filing_history"
            if reason is not None:
                reject_rows.append(
                    {
                        "recon_date": d.isoformat(),
                        "cik": cik,
                        "name": p.name,
                        "sic": p.sic,
                        "superset_rank": srank,
                        "float_usd": fact.val if fact else None,
                        "reason": reason,
                        "quarters_covered": eligible_quarters_covered(periodic.get(cik, []), d),
                        "periodic_in_window": count_periodic_in_window(periodic.get(cik, []), d),
                        **(
                            {
                                "sector": sector,
                                "exclusion_reason": excluded_now[cik].reason,
                                "exclusion_evidence": excluded_now[cik].evidence,
                                # Provenance for the generalisation: this row
                                # was found by hand, and a systematic rule now
                                # covers it. Both facts belong in the log.
                                "exclusion_superseded_by_rule": ";".join(
                                    excluded_now[cik].superseded_by_rule
                                ),
                                "rule_would_also_reject": ";".join(rule_hits),
                            }
                            if cik in excluded_now
                            else {}
                        ),
                        **({"rule_evidence": rule_evidence} if rule_hit else {}),
                    }
                )
                continue
            cand.append((cik, sector, fact, srank))
        # overall PIT rank at this date, then top-K within each sector
        cand.sort(key=lambda t: -t[2].val)
        overall = {c[0]: i + 1 for i, c in enumerate(cand)}
        per_sector: dict[str, int] = Counter()
        for cik, sector, fact, srank in cand:
            if sector not in sectors:
                continue
            per_sector[sector] += 1
            if per_sector[sector] > K[sector]:
                # Passed every filter, just not big enough for its bucket at
                # this date. Recorded (with its within-sector rank) so the
                # report can say exactly how far short a name fell rather than
                # just "absent".
                reject_rows.append(
                    {
                        "recon_date": d.isoformat(),
                        "cik": cik,
                        "name": profiles[cik].name,
                        "sic": profiles[cik].sic,
                        "superset_rank": srank,
                        "float_usd": fact.val,
                        "reason": "below_sector_K",
                        "quarters_covered": MIN_ELIGIBLE_QUARTERS,
                        "periodic_in_window": count_periodic_in_window(periodic.get(cik, []), d),
                        "sector": sector,
                        "sector_rank": per_sector[sector],
                    }
                )
                continue
            p = profiles[cik]
            panel_rows.append(
                {
                    "recon_date": d.isoformat(),
                    "cik": cik,
                    "name": p.name,
                    "tickers": ",".join(p.tickers),
                    "sic": p.sic,
                    "sic_desc": p.sic_desc,
                    "sector": sector,
                    **({"stratum": strata[sector]} if strata else {}),
                    "sector_rank": per_sector[sector],
                    "float_usd": fact.val,
                    "float_instant": fact.instant.isoformat(),
                    "float_filed": fact.filed.isoformat(),
                    "float_accn": fact.accn,
                    "float_form": fact.form,
                    "float_staleness_days": (d - fact.instant).days,
                    "float_pit_lag_days": (d - fact.filed).days,
                    "overall_float_rank": overall[cik],
                    "superset_rank": srank,
                    "quarters_covered": eligible_quarters_covered(periodic.get(cik, []), d),
                }
            )
    return pd.DataFrame(panel_rows), pd.DataFrame(reject_rows)


def assert_pit_membership(panel: pd.DataFrame) -> None:
    """Re-check the point-in-time guarantee on the FINAL emitted table, not
    just inside the selection loop: every membership row's float source filing
    date must be strictly before its reconstitution date. This is the assertion
    the whole downstream walk-forward design rests on (EXPANSION_PLAN.md §2c).
    """
    if panel.empty:
        return
    rd = pd.to_datetime(panel["recon_date"])
    fd = pd.to_datetime(panel["float_filed"])
    bad = panel[fd >= rd]
    if len(bad):
        raise AssertionError(
            f"POINT-IN-TIME VIOLATION: {len(bad)} membership rows use a float "
            f"fact filed on/after the reconstitution date, e.g.\n{bad.head().to_string()}"
        )
    inst = pd.to_datetime(panel["float_instant"])
    bad2 = panel[inst >= rd]
    if len(bad2):
        raise AssertionError(f"float instant on/after recon date for {len(bad2)} rows")


def build_spells(panel: pd.DataFrame, dates: list[date]) -> pd.DataFrame:
    """Collapse the per-date panel into membership spells.

    member_from = the reconstitution date at which the company entered.
    member_to   = the reconstitution date at which it was no longer a member
                  (EXCLUSIVE upper bound), or empty for a still-open spell at
                  the final reconstitution date.
    A company can have several spells (exit then re-entry) -- that is real
    churn, not an error, and is reported as such.
    """
    if panel.empty:
        return pd.DataFrame()
    ds = [d.isoformat() for d in dates]
    order = {d: i for i, d in enumerate(ds)}
    rows = []
    for cik, g in panel.groupby("cik"):
        g = g.sort_values("recon_date")
        idxs = sorted(order[d] for d in g["recon_date"])
        last = g.iloc[-1]
        spells: list[list[int]] = []
        for i in idxs:
            if spells and i == spells[-1][-1] + 1:
                spells[-1].append(i)
            else:
                spells.append([i])
        for sp in spells:
            first_row = g[g["recon_date"] == ds[sp[0]]].iloc[0]
            rows.append(
                {
                    "cik": cik,
                    "name": last["name"],
                    "tickers": last["tickers"],
                    "sector": first_row["sector"],
                    # carried through only when the variant is stratified, so
                    # the option-record spells tables keep their exact schema
                    **({"stratum": first_row["stratum"]} if "stratum" in panel.columns else {}),
                    "sic": first_row["sic"],
                    "member_from": ds[sp[0]],
                    "member_to": ds[sp[-1] + 1] if sp[-1] + 1 < len(ds) else "",
                    "n_reconstitutions": len(sp),
                    "entry_sector_rank": int(first_row["sector_rank"]),
                    "exit_sector_rank": int(
                        g[g["recon_date"] == ds[sp[-1]]].iloc[0]["sector_rank"]
                    ),
                    "median_sector_rank": float(
                        g[g["recon_date"].isin([ds[i] for i in sp])]["sector_rank"].median()
                    ),
                    "median_float_usd": float(
                        g[g["recon_date"].isin([ds[i] for i in sp])]["float_usd"].median()
                    ),
                    "all_dates": len(sp) == len(ds),
                }
            )
    return pd.DataFrame(rows).sort_values(["sector", "member_from", "entry_sector_rank"])


def churn_stats(panel: pd.DataFrame, dates: list[date]) -> pd.DataFrame:
    ds = [d.isoformat() for d in dates]
    by_date = {d: set(panel[panel["recon_date"] == d]["cik"]) for d in ds}
    rows = []
    prev: Optional[set] = None
    for d in ds:
        cur = by_date[d]
        entries = len(cur - prev) if prev is not None else len(cur)
        exits = len(prev - cur) if prev is not None else 0
        rows.append(
            {
                "recon_date": d,
                "n_members": len(cur),
                "entries": entries,
                "exits": exits,
                "turnover_pct": round(100.0 * entries / len(cur), 1) if cur else 0.0,
            }
        )
        prev = cur
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Stage 4: censoring census + diligence flags
# ---------------------------------------------------------------------------


def price_census(
    panel: pd.DataFrame,
    profiles: dict[int, CikProfile],
    sample_n: int = 15,
    probe: bool = True,
    today: Optional[date] = None,
    probe_ciks: Optional[set[int]] = None,
) -> tuple[pd.DataFrame, list[dict]]:
    """`probe_ciks` restricts which census rows the Yahoo sample is drawn from.
    It is set to the option-record variants' members so that adding a third
    variant does not reshuffle the seeded sample (and so cost fresh price
    requests) for a table that is about the censoring population, not about
    which variant was ratified."""
    today = today or date.today()
    members = sorted(set(panel["cik"]))
    rows = []
    for cik in members:
        p = profiles[cik]
        last = p.last_periodic
        still_filing = bool(last and (today - last).days <= 200)
        rows.append(
            {
                "cik": cik,
                "name": p.name,
                "tickers": ",".join(p.tickers),
                "has_current_ticker": bool(p.tickers),
                "exchanges": ",".join(p.exchanges),
                "last_periodic": last.isoformat() if last else "",
                "still_filing": still_filing,
                "former_names": " | ".join(p.former_names),
                # Censoring risk = no ticker resolvable today. XOM-style
                # successor-CIK reorganizations produce the SAME symptom while
                # the company is very much alive, so the two are separated by
                # `still_filing` and re-checked by hand in the report.
                "censoring_risk": (not p.tickers),
            }
        )
    census = pd.DataFrame(rows)
    probes: list[dict] = []
    former: list[dict] = []
    n_price_requests = 0
    if probe:
        frame = census if probe_ciks is None else census[census["cik"].isin(probe_ciks)]
        probes, n_price_requests = probe_prices(frame.reset_index(drop=True), sample_n)
        former = probe_former_tickers(frame)
    return census, probes, former, n_price_requests


# Hand-identified former ticker symbols for member CIKs that no longer resolve.
# EDGAR records NO historical ticker for a dead registrant, so this list cannot
# be derived -- it was typed by hand from public knowledge of each acquisition,
# and every entry is checked against the registrant's EDGAR entity name below.
# USED ONLY FOR THE §5 CENSORING PROBE. It never touches membership, ranking or
# eligibility; deleting it changes nothing except that the censoring claim goes
# back to being an assumption instead of a measurement.
FORMER_TICKERS_MANUAL: dict[int, tuple[str, str]] = {
    773910: ("APC", "Anadarko Petroleum -- acquired by Occidental, Aug 2019"),
    816284: ("CELG", "Celgene -- acquired by Bristol-Myers Squibb, Nov 2019"),
    1418091: ("TWTR", "Twitter -- taken private by Musk, Oct 2022"),
    718877: ("ATVI", "Activision Blizzard -- acquired by Microsoft, Oct 2023"),
    1038357: ("PXD", "Pioneer Natural Resources -- acquired by ExxonMobil, May 2024"),
    4447: ("HES", "Hess -- acquired by Chevron, Jul 2024"),
    1393612: ("DFS", "Discover Financial -- acquired by Capital One, May 2025"),
    804753: ("CERN", "Cerner -- acquired by Oracle, Jun 2022"),
    790070: ("EMC", "EMC Corp -- acquired by Dell, Sep 2016"),
    1271024: ("LNKD", "LinkedIn -- acquired by Microsoft, Dec 2016"),
}


def _yahoo_symbol_identity(ticker: str) -> dict:
    """What the cached Yahoo chart response says the symbol IS today
    (instrument type, name, first trade date). Read from the on-disk cache the
    fetch just populated -- no extra network request."""
    path = RAW_DIR / "prices" / "yahoo" / f"{ticker.upper()}.json"
    out = {"symbol_now_type": "", "symbol_now_name": "", "symbol_first_trade": ""}
    try:
        meta = json.loads(path.read_text())["chart"]["result"][0]["meta"]
    except Exception:  # noqa: BLE001
        return out
    out["symbol_now_type"] = str(meta.get("instrumentType") or "")
    out["symbol_now_name"] = str(meta.get("longName") or meta.get("shortName") or "")
    ft = meta.get("firstTradeDate")
    if ft:
        try:
            out["symbol_first_trade"] = datetime.utcfromtimestamp(int(ft)).date().isoformat()
        except Exception:  # noqa: BLE001
            pass
    return out


def probe_former_tickers(census: pd.DataFrame, limit: int = 10) -> list[dict]:
    """Ask the existing Yahoo client for the LAST KNOWN symbols of censored
    members. This is the measurement behind the design's central caveat: the
    recon asserted that Yahoo "generally has no data for delisted tickers",
    and that assertion decides how much of E2's outcome side is censored.
    Sequential, cached, <= `limit` symbols.
    """
    from price_client import PriceClient, PriceFetchError

    censored = census[census["censoring_risk"]].set_index("cik")
    client = PriceClient(verbose=False)
    out: list[dict] = []
    for cik, (ticker, note) in list(FORMER_TICKERS_MANUAL.items())[:limit]:
        if cik not in censored.index:
            continue
        row = {"cik": cik, "name": censored.loc[cik, "name"], "former_ticker": ticker,
               "event": note, "last_periodic": censored.loc[cik, "last_periodic"]}
        try:
            df, src = client.get_daily_bars(ticker)
            last_bar = str(df["date"].max())[:10] if len(df) else ""
            row.update({"result": "DATA_RETURNED", "n_bars": len(df),
                        "last_bar": last_bar, "source": src})
            # A returned series is NOT evidence the symbol still means this
            # company: exchanges recycle tickers. Record what the price source
            # thinks the symbol is now, so the report can show the mismatch
            # instead of counting it as a successful match.
            row.update(_yahoo_symbol_identity(ticker))
        except PriceFetchError as exc:
            row.update({"result": "NO_DATA", "n_bars": 0, "last_bar": "",
                        "source": str(exc)[:120]})
        except Exception as exc:  # noqa: BLE001
            row.update({"result": "ERROR", "n_bars": 0, "last_bar": "",
                        "source": repr(exc)[:120]})
        out.append(row)
    return out


def probe_prices(census: pd.DataFrame, sample_n: int) -> tuple[list[dict], int]:
    """Probe the EXISTING Yahoo price client for a small sample. Sparingly:
    `sample_n` tickers total, sequential, through price_client.PriceClient's
    own throttle. Uses its on-disk cache, so re-runs are free."""
    from price_client import PriceClient, PriceFetchError  # local import: optional dep

    no_ticker = census[~census["has_current_ticker"]]
    with_ticker_old = census[
        census["has_current_ticker"] & (~census["still_filing"])
    ]
    with_ticker_live = census[census["has_current_ticker"] & census["still_filing"]]
    rng = random.Random(20260820)

    def take(df, n):
        recs = df.to_dict("records")
        rng.shuffle(recs)
        return recs[:n]

    sample = take(no_ticker, min(len(no_ticker), sample_n // 2))
    sample += take(with_ticker_old, min(len(with_ticker_old), max(0, sample_n - len(sample) - 3)))
    sample += take(with_ticker_live, max(0, sample_n - len(sample)))

    client = PriceClient(verbose=False)
    out = []
    for rec in sample:
        tick = (rec["tickers"].split(",")[0] if rec["tickers"] else "")
        row = {
            "cik": rec["cik"],
            "name": rec["name"],
            "ticker_probed": tick,
            "has_current_ticker": rec["has_current_ticker"],
            "still_filing": rec["still_filing"],
        }
        if not tick:
            row.update(
                {
                    "result": "NO_TICKER_TO_PROBE",
                    "n_bars": 0,
                    "first_bar": "",
                    "last_bar": "",
                    "detail": "EDGAR submissions lists no current ticker; EDGAR "
                    "carries no historical ticker for dead registrants, so there "
                    "is nothing to ask Yahoo for.",
                }
            )
        else:
            try:
                df, src = client.get_daily_bars(tick)
                row.update(
                    {
                        "result": "OK",
                        "n_bars": len(df),
                        "first_bar": str(df["date"].min())[:10] if len(df) else "",
                        "last_bar": str(df["date"].max())[:10] if len(df) else "",
                        "detail": f"source={src}",
                    }
                )
            except PriceFetchError as exc:
                row.update(
                    {"result": "FETCH_FAILED", "n_bars": 0, "first_bar": "", "last_bar": "",
                     "detail": str(exc)[:200]}
                )
            except Exception as exc:  # noqa: BLE001
                row.update(
                    {"result": "ERROR", "n_bars": 0, "first_bar": "", "last_bar": "",
                     "detail": repr(exc)[:200]}
                )
        out.append(row)
    return out, client.request_count


# ---------------------------------------------------------------------------
# Stage 4b: float-scale audit -- the compensating control for the sanitizer's
# one structural blind spot
# ---------------------------------------------------------------------------
#
# `suspect_value_reasons()` is a WITHIN-REGISTRANT rule: it judges a float fact
# against the same registrant's temporally adjacent disclosures. A registrant
# that mis-scales its ENTIRE float history the same way therefore has no clean
# neighbour and is invisible to it -- E2_UNIVERSE_REPORT.md listed exactly this
# as an open residual risk, with only an eyeball cross-sectional check behind
# it. This function replaces the eyeball with four arms, three of which use
# data the build has already paid for:
#
#   A. IMPLIED PRICE. Divide the selected float by the share count reported on
#      the SAME cover page (dei:EntityCommonStockSharesOutstanding, ~3 KB per
#      registrant). float / shares is a per-share price, and a US large cap's
#      is essentially never outside [$3, $1000]. A 1,000x float mis-scale
#      lands the quotient at ~1,000x a real price.
#   B. SHARES-SERIES SANITY. Run the SAME scale detector on the registrant's
#      own share-count series. This catches the nastier variant where the 10-K
#      cover mis-scales float AND shares together (so arm A's quotient looks
#      perfectly normal) while the registrant's own 10-Qs carry the right
#      number -- ASV Holdings, verified. The same arm flags a share count
#      below AUDIT_MIN_PUBLIC_SHARES, which means "this registrant has no
#      publicly traded common equity at all" (EIDP: 100 shares, wholly owned).
#   C. FLOAT-TO-ASSETS ADJUDICATION. Arms A and B are screens and they do
#      produce honest false alarms (Amazon pre-split, Booking, MercadoLibre all
#      genuinely trade in four figures). Only for the registrants a screen
#      flagged, fetch us-gaap:Assets and compare. A genuine large cap's float
#      is a single-digit multiple of its balance sheet; a 1,000x mis-scale is a
#      several-hundred-fold multiple.
#   D. SUPERSEDED-BY-ZERO. Costs nothing: a membership row whose selected float
#      is older than an ALREADY-PUBLIC float disclosure of exactly 0. Zero is
#      not noise, it is the registrant saying "I have no public float"; the
#      sanitizer drops zeros as `zero_or_negative`, after which pit_float_asof
#      falls back to a stale positive value. Catches wholly-owned successors
#      (Dow Chemical, Energy Transfer Operating) with no look-ahead whatsoever.
#
# THE AUDIT DECIDES NOTHING. It writes a CSV and a report table. Removing a
# registrant from the universe happens only via manual_exclusions.csv, by hand,
# with the evidence written down.
ASSETS_CONCEPT = "Assets"
AUDIT_MIN_IMPLIED_PRICE_USD = 3.0
AUDIT_MAX_IMPLIED_PRICE_USD = 1000.0
# ONE number, shared with the ratified min-shares rule (rule 2). The screen and
# the selection rule must not be able to drift apart: if the floor moves, it
# moves for both.
AUDIT_MIN_PUBLIC_SHARES = MIN_PUBLIC_SHARES_FOR_MEMBERSHIP
AUDIT_MAX_FLOAT_TO_ASSETS = 25.0
AUDIT_MATCH_MAX_DAYS = 400


def _match_concept_value(
    rows: list[dict], accn: str, instant: date, prefer: str = "last"
) -> tuple[Optional[float], str]:
    """Value from the SAME accession as the float fact if the registrant tagged
    one there (that is literally the same cover page / same filing), else the
    nearest measurement within AUDIT_MATCH_MAX_DAYS. Multi-class registrants
    tag one row per class on the same (accn, end): those are SUMMED."""
    if not rows:
        return None, "no_concept"
    same = [r for r in rows if r["accn"] == accn]
    if same:
        by_end: dict[date, set] = defaultdict(set)
        for r in same:
            by_end[r["end"]].add(r["val"])
        end = max(by_end) if prefer == "last" else min(by_end)
        total = sum(by_end[end])
        if not total:
            return None, "same_accn_value_is_zero"
        return total, f"same_accn@{end.isoformat()}"
    best = min(rows, key=lambda r: abs((r["end"] - instant).days))
    gap = abs((best["end"] - instant).days)
    if gap > AUDIT_MATCH_MAX_DAYS:
        return None, f"no_fact_within_{AUDIT_MATCH_MAX_DAYS}d"
    if not best["val"]:
        return None, "nearest_value_is_zero"
    return best["val"], f"nearest@{best['end'].isoformat()}({gap}d)"


def audit_float_scale(
    client: EdgarClient,
    panel: pd.DataFrame,
    facts_by_cik: dict[int, list[FloatFact]],
    adjudicate: bool = True,
) -> tuple[pd.DataFrame, dict]:
    """Run arms A-D over every membership row of `panel`. Returns
    (per-row audit table, summary dict). Network cost: one ~3 KB
    companyconcept GET per distinct member CIK for the share count (cached
    forever), plus one us-gaap:Assets GET per registrant a screen flagged."""
    if panel.empty:
        return pd.DataFrame(), {"rows": 0}
    ciks = sorted({int(c) for c in panel["cik"]})
    shares_rows: dict[int, list[dict]] = {}
    shares_flags: dict[int, dict[tuple[str, date], Optional[str]]] = {}
    n_no_shares = 0
    for i, cik in enumerate(ciks, 1):
        rows = _concept_rows(fetch_concept(client, cik, "dei", SHARES_CONCEPT), "shares")
        shares_rows[cik] = rows
        if not rows:
            n_no_shares += 1
        pos = [r for r in rows if r["val"] > 0]
        if len(pos) >= 2:
            reasons = suspect_value_reasons([r["end"] for r in pos], [r["val"] for r in pos])
        else:
            reasons = [None] * len(pos)
        shares_flags[cik] = {(r["accn"], r["end"]): rr for r, rr in zip(pos, reasons)}
        if i % 50 == 0:
            print(f"  [audit] {i}/{len(ciks)} share counts (net GETs so far: {client.request_count})")

    out: list[dict] = []
    for r in panel.to_dict("records"):
        cik = int(r["cik"])
        instant = date.fromisoformat(r["float_instant"])
        d = date.fromisoformat(r["recon_date"])
        sh, how = _match_concept_value(shares_rows[cik], r["float_accn"], instant)
        implied = (float(r["float_usd"]) / sh) if sh else None
        flags: list[str] = []
        # arm A
        if implied is not None and not (
            AUDIT_MIN_IMPLIED_PRICE_USD <= implied <= AUDIT_MAX_IMPLIED_PRICE_USD
        ):
            flags.append("implied_price_out_of_band")
        # arm B
        if sh is not None and sh < AUDIT_MIN_PUBLIC_SHARES:
            flags.append("no_public_common_equity")
        if how.startswith("same_accn@"):
            end = date.fromisoformat(how.split("@", 1)[1])
            if shares_flags[cik].get((r["float_accn"], end)):
                flags.append("shares_scale_error_on_same_cover")
        # arm D -- costs nothing, uses facts already on disk
        zeros = [
            f
            for f in facts_by_cik.get(cik, [])
            if f.filed < d and f.instant > instant and f.val <= 0
        ]
        if zeros:
            z = max(zeros, key=lambda f: f.instant)
            flags.append("superseded_by_public_zero_float")
        else:
            z = None
        out.append(
            {
                "recon_date": r["recon_date"],
                "cik": cik,
                "name": r["name"],
                "sector": r["sector"],
                "stratum": r.get("stratum", ""),
                "float_usd": float(r["float_usd"]),
                "float_instant": r["float_instant"],
                "float_accn": r["float_accn"],
                "shares_outstanding": sh,
                "shares_source": how,
                "implied_price_usd": implied,
                "zero_float_instant": z.instant.isoformat() if z else "",
                "zero_float_filed": z.filed.isoformat() if z else "",
                "flags": ";".join(flags),
            }
        )
    audit = pd.DataFrame(out)

    # ---- arm C: adjudicate ONLY the flagged registrants ---------------------
    audit["float_to_assets"] = None
    flagged = sorted({int(c) for c in audit[audit["flags"] != ""]["cik"]})
    if adjudicate and flagged:
        print(f"  [audit] adjudicating {len(flagged)} flagged registrant(s) against us-gaap:Assets")
        for cik in flagged:
            arows = [
                a
                for a in _concept_rows(
                    fetch_concept(client, cik, "us-gaap", ASSETS_CONCEPT), "USD"
                )
                if a["val"] > 0
            ]
            for idx in audit.index[audit["cik"] == cik]:
                assets, _how = _match_concept_value(
                    arows, audit.at[idx, "float_accn"], date.fromisoformat(audit.at[idx, "float_instant"])
                )
                if assets:
                    audit.at[idx, "float_to_assets"] = float(audit.at[idx, "float_usd"]) / assets
    ratio = pd.to_numeric(audit["float_to_assets"], errors="coerce")
    audit["scale_verdict"] = [
        (
            "SCALE ERROR (float is a several-hundred-fold multiple of total assets)"
            if pd.notna(x) and x > AUDIT_MAX_FLOAT_TO_ASSETS
            else ("corroborated by balance sheet" if pd.notna(x) else "")
        )
        for x in ratio
    ]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    audit.to_parquet(CACHE_DIR / "float_scale_audit.parquet", index=False)
    audit.to_csv(CACHE_DIR / "float_scale_audit.csv", index=False)
    flag_counts: Counter = Counter()
    for f in audit["flags"]:
        flag_counts.update(x for x in str(f).split(";") if x)
    summary = {
        "rows": len(audit),
        "registrants": int(audit["cik"].nunique()),
        "rows_with_shares": int(audit["shares_outstanding"].notna().sum()),
        "registrants_without_shares_concept": n_no_shares,
        "flag_counts": dict(flag_counts),
        "flagged_rows": int((audit["flags"] != "").sum()),
        "flagged_registrants": len(flagged),
        "confirmed_scale_errors": sorted(
            {int(c) for c in audit[audit["scale_verdict"].str.startswith("SCALE ERROR")]["cik"]}
        ),
    }
    (CACHE_DIR / "float_scale_audit_summary.json").write_text(json.dumps(summary, indent=1))
    print(
        f"[audit] {summary['rows']} membership rows over {summary['registrants']} registrants; "
        f"share count resolved for {summary['rows_with_shares']}; "
        f"flags {summary['flag_counts']}"
    )
    return audit, summary


def diligence_flags(
    panels: dict[str, pd.DataFrame],
    profiles: dict[int, CikProfile],
    facts_by_cik: dict[int, list[FloatFact]],
    client: EdgarClient,
) -> dict:
    """CIK-level oddities that would silently corrupt downstream ingestion if
    not surfaced now (the XOM lesson: the bulk ticker map is not truth)."""
    flags: dict = {}
    all_members = sorted({c for p in panels.values() for c in p["cik"]})
    prof = {c: profiles[c] for c in all_members}

    # (a) multi-class / missing dei facts
    flags["no_float_concept"] = [
        {"cik": c, "name": prof[c].name} for c in all_members if not prof[c].has_float_concept
    ]
    flags["suspect_float_facts"] = [
        {"cik": c, "name": prof[c].name, "n": prof[c].n_suspect_facts}
        for c in all_members
        if prof[c].n_suspect_facts
    ]
    flags["multi_ticker_share_classes"] = [
        {"cik": c, "name": prof[c].name, "tickers": prof[c].tickers}
        for c in all_members
        if len(prof[c].tickers) > 1
    ]

    # (b) legacy-CIK oddities: a member with no current ticker but still
    # actively filing (XOM-style successor reorganization), and members whose
    # entity name has changed (post-bankruptcy shells, mergers).
    today = date.today()
    flags["no_ticker_but_active"] = [
        {
            "cik": c,
            "name": prof[c].name,
            "last_periodic": prof[c].last_periodic.isoformat() if prof[c].last_periodic else "",
            "former_names": prof[c].former_names[:3],
        }
        for c in all_members
        if not prof[c].tickers
        and prof[c].last_periodic
        and (today - prof[c].last_periodic).days <= 200
    ]
    flags["renamed_entities"] = [
        {"cik": c, "name": prof[c].name, "former_names": prof[c].former_names[:3]}
        for c in all_members
        if prof[c].former_names and not prof[c].tickers
    ]

    # (c) ticker-map collisions: does company_tickers.json point the member's
    # own ticker at a DIFFERENT CIK? (exactly the XOM/34088 vs 2115436 case)
    try:
        tmap = client.get_company_tickers()
        by_ticker: dict[str, list[int]] = defaultdict(list)
        for row in tmap.values():
            by_ticker[str(row["ticker"]).upper()].append(int(row["cik_str"]))
        collisions = []
        for c in all_members:
            for t in prof[c].tickers:
                ciks_for_t = by_ticker.get(t.upper(), [])
                if ciks_for_t and c not in ciks_for_t:
                    collisions.append(
                        {"cik": c, "name": prof[c].name, "ticker": t, "map_cik": ciks_for_t}
                    )
        flags["ticker_map_disagreement"] = collisions
        # the reverse XOM check: a member with NO ticker whose name matches a
        # ticker-map entry pointing at another CIK
        name_hits = []
        for c in all_members:
            if prof[c].tickers:
                continue
            base = prof[c].name.upper().split()[0] if prof[c].name else ""
            if len(base) < 4:
                continue
            for row in tmap.values():
                if str(row.get("title", "")).upper().startswith(base) and int(row["cik_str"]) != c:
                    name_hits.append(
                        {
                            "cik": c,
                            "name": prof[c].name,
                            "map_cik": int(row["cik_str"]),
                            "map_title": row.get("title"),
                            "map_ticker": row.get("ticker"),
                        }
                    )
                    break
        flags["successor_cik_candidates"] = name_hits
    except Exception as exc:  # noqa: BLE001
        flags["ticker_map_error"] = repr(exc)

    # (d) cross-variant and E1 overlap
    sets = {k: set(v["cik"]) for k, v in panels.items()}
    for a, b in [OPTION_RECORD_VARIANTS, (RATIFIED_VARIANT, OPTION_RECORD_VARIANTS[0])]:
        if a in sets and b in sets:
            flags[f"variant_overlap_{a}_vs_{b}"] = {
                "both": len(sets[a] & sets[b]),
                f"{a}_only": sorted(sets[a] - sets[b]),
                f"{b}_only": sorted(sets[b] - sets[a]),
            }
    e1 = pd.read_csv(E1_UNIVERSE_CSV)
    e1_ciks = {int(c) for c in e1["cik"]}
    flags["e1_coverage"] = {
        k: {
            "present": sorted(e1_ciks & s),
            "missing": sorted(e1_ciks - s),
        }
        for k, s in sets.items()
    }
    flags["e1_names"] = {int(r["cik"]): (r["ticker"], r["sector"]) for _, r in e1.iterrows()}
    return flags


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


OPTION_RECORD_CHECKSUMS_PATH = OUT_DIR / "option_record_checksums.json"


def verify_option_record_checksums(path: Optional[Path] = None) -> dict[str, str]:
    """The option record is FROZEN. `continuity5` / `broad8` are the artifacts
    the owner's 2026-08-21 universe decision cites, and every later change to
    this builder -- including the two float-integrity rules ratified the same
    day -- must leave them byte-identical.

    That is a claim worth checking rather than asserting, so the sha256 of each
    file as it stood in the pre-rules build is recorded in
    `option_record_checksums.json` and re-verified on every run.

    Returns {filename: "ok" | "MISMATCH..." | "missing"}; RAISES on a mismatch.
    A missing manifest is a legitimate state (returns {}) -- it is a guard, not
    a dependency -- but a mismatch never is: if a change moves one of these
    files, that change has leaked into the audit trail behind a ratified
    decision and must be scoped out of it, not re-baselined.
    """
    import hashlib

    path = path or OPTION_RECORD_CHECKSUMS_PATH
    if not path.exists():
        return {}
    expected = (json.loads(path.read_text()) or {}).get("sha256") or {}
    status: dict[str, str] = {}
    bad: list[str] = []
    for name, want in expected.items():
        f = OUT_DIR / name
        if not f.exists():
            status[name] = "missing"
            continue
        got = hashlib.sha256(f.read_bytes()).hexdigest()
        if got == want:
            status[name] = "ok"
        else:
            status[name] = f"MISMATCH expected {want[:12]} got {got[:12]}"
            bad.append(name)
    if bad:
        raise AssertionError(
            "OPTION RECORD CHANGED -- these files back the owner's 2026-08-21 "
            "decision and must reproduce byte-identically:\n  "
            + "\n  ".join(f"{n}: {status[n]}" for n in bad)
            + f"\nManifest: {path}"
        )
    return status


def write_outputs(variant: str, panel: pd.DataFrame, spells: pd.DataFrame, rejects: pd.DataFrame) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    spells.to_parquet(OUT_DIR / f"{variant}.parquet", index=False)
    spells.to_csv(OUT_DIR / f"{variant}.csv", index=False)
    panel.to_parquet(OUT_DIR / f"{variant}_panel.parquet", index=False)
    panel.to_csv(OUT_DIR / f"{variant}_panel.csv", index=False)
    rejects.to_parquet(CACHE_DIR / f"{variant}_rejects.parquet", index=False)
    rejects.to_csv(CACHE_DIR / f"{variant}_rejects.csv", index=False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", default="all",
                    choices=["all", "frames", "diligence", "select", "census", "report"])
    ap.add_argument("--shortlist-per-date", type=int, default=DEFAULT_SHORTLIST_PER_DATE)
    ap.add_argument("--first-year", type=int, default=FIRST_RECON_YEAR)
    ap.add_argument("--last-year", type=int, default=LAST_RECON_YEAR)
    ap.add_argument("--frames-lookback", type=int, default=FRAMES_LOOKBACK_QUARTERS)
    ap.add_argument("--price-probe-n", type=int, default=15)
    ap.add_argument("--no-price-probe", action="store_true")
    ap.add_argument("--no-scale-audit", action="store_true",
                    help="skip the float-scale compensating control (§6.7). It costs one "
                         "cached ~3 KB companyconcept GET per member CIK on a cold cache.")
    ap.add_argument("--ignore-manual-exclusions", action="store_true",
                    help="build the ratified variant as if manual_exclusions.csv were "
                         "empty. Diagnostic only -- the report always shows both.")
    ap.add_argument("--quiet-http", action="store_true", default=True)
    args = ap.parse_args(argv)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dates = reconstitution_dates(args.first_year, args.last_year)
    client = EdgarClient(verbose=not args.quiet_http)
    print(f"[config] {len(dates)} reconstitution dates: {dates[0]} .. {dates[-1]} "
          f"(every {RECON_MONTH:02d}-{RECON_DAY:02d})")

    run_all = args.stage == "all"

    if run_all or args.stage == "frames":
        frames_panel = stage_frames(client, dates, args.frames_lookback)
        shortlist = shortlist_per_date(frames_panel, dates, args.shortlist_per_date)
        if args.stage == "frames":
            print(f"[done] network GETs this run: {client.request_count}")
            return 0
    else:
        shortlist = pd.read_parquet(CACHE_DIR / "shortlist_per_date.parquet")

    ciks = sorted(set(int(c) for c in shortlist["cik"]))
    # E1's 25 are force-included in DILIGENCE (not in membership) so the report
    # can say exactly why any of them fails to rank in, rather than silently
    # never looking at it.
    e1_ciks = sorted({int(c) for c in pd.read_csv(E1_UNIVERSE_CSV)["cik"]})
    diligence_ciks = sorted(set(ciks) | set(e1_ciks))
    history_cutoff = date(dates[0].year - 3, 1, 1)

    if run_all or args.stage == "diligence":
        print(f"[diligence] {len(diligence_ciks)} CIKs (incl. {len(set(e1_ciks) - set(ciks))} "
              f"E1 names not in the frames shortlist); history cutoff {history_cutoff}")
        profiles, facts_by_cik, suspects = stage_diligence(client, diligence_ciks, history_cutoff)
    else:
        profiles, facts_by_cik, suspects = load_diligence()

    if args.stage in ("frames", "diligence"):
        print(f"[done] network GETs this run: {client.request_count}")
        return 0

    periodic = load_periodic_dates(client, diligence_ciks, history_cutoff)

    try:
        _bl = pd.read_parquet(CACHE_DIR / "coregistrant_blocklist.parquet")
        blocklist = {(int(r["cik"]), r["accn"]) for _, r in _bl.iterrows()}
    except Exception:  # noqa: BLE001
        blocklist = set()

    exclusions = [] if args.ignore_manual_exclusions else load_manual_exclusions()
    print(
        f"[exclusions] {len(exclusions)} manual exclusion row(s) loaded from "
        f"{MANUAL_EXCLUSIONS_PATH.name}"
        + (" (IGNORED: --ignore-manual-exclusions)" if args.ignore_manual_exclusions else "")
    )
    for ex in exclusions:
        sup = f" [superseded by {'+'.join(ex.superseded_by_rule)}]" if ex.superseded_by_rule else ""
        print(f"             CIK {ex.cik} {ex.name} — {ex.reason} [{ex.window_str()}] "
              f"-> {'/'.join(ex.applies_to)}{sup}")

    # Cover-page share counts for rule 2, read from the on-disk companyconcept
    # cache ONLY -- zero network requests, by ratified design. A shortlist CIK
    # with no cached document is untestable and the rule abstains on it.
    shares_by_cik = load_cached_shares(diligence_ciks)
    n_empty = sum(1 for v in shares_by_cik.values() if not v)
    print(
        f"[rules] float-integrity rulesets: "
        + ", ".join(
            f"{v}={ruleset_for(v).name}"
            f"({'+'.join(ruleset_for(v).rules) or 'none'})"
            for v in (*OPTION_RECORD_VARIANTS, RATIFIED_VARIANT)
        )
    )
    print(
        f"[rules] cover-page share history available for {len(shares_by_cik)}/"
        f"{len(diligence_ciks)} diligence CIKs from cache (0 GETs); of those "
        f"{n_empty} never tagged the concept, so rule "
        f"`{FLOAT_RULE_MIN_SHARES}` cannot speak for them"
    )

    panels: dict[str, pd.DataFrame] = {}
    spells_by_variant: dict[str, pd.DataFrame] = {}
    rejects_by_variant: dict[str, pd.DataFrame] = {}
    # Order matters only for the log: the option-record variants are rebuilt
    # first and must come out byte-identical to the tables the owner's decision
    # cites (no exclusion row scopes itself to them by default).
    for variant in (*OPTION_RECORD_VARIANTS, RATIFIED_VARIANT):
        panel, rejects = build_membership(
            variant, dates, shortlist, profiles, facts_by_cik, periodic, blocklist,
            exclusions=exclusions, shares_by_cik=shares_by_cik,
        )
        assert_pit_membership(panel)
        spells = build_spells(panel, dates)
        write_outputs(variant, panel, spells, rejects)
        panels[variant] = panel
        spells_by_variant[variant] = spells
        rejects_by_variant[variant] = rejects
        strata_note = ""
        if "stratum" in panel.columns:
            counts = panel.groupby("stratum")["cik"].nunique().to_dict()
            strata_note = f", distinct CIKs by stratum {counts}"
        print(
            f"[select:{variant}] {len(panel)} membership rows, "
            f"{panel['cik'].nunique()} distinct CIKs over the decade, "
            f"PIT assertion PASSED{strata_note}"
        )

    # The option record must not have moved. Checked on every run, immediately
    # after it is written, so a leak is caught here and not months later.
    _ck = verify_option_record_checksums()
    if _ck:
        print(
            f"[frozen] option record verified byte-identical against "
            f"{OPTION_RECORD_CHECKSUMS_PATH.name}: {len(_ck)} file(s), "
            f"{sum(1 for v in _ck.values() if v == 'ok')} ok"
        )

    # Counterfactual build of the ratified variant with the exclusions switched
    # off, so the report can say exactly what each exclusion removed and who
    # took the vacated slot -- "logged, never silently dropped".
    shadow_panel, _shadow_rejects = build_membership(
        RATIFIED_VARIANT, dates, shortlist, profiles, facts_by_cik, periodic, blocklist,
        exclusions=(), shares_by_cik=shares_by_cik,
    )
    assert_pit_membership(shadow_panel)
    shadow_panel.to_parquet(CACHE_DIR / f"{RATIFIED_VARIANT}_shadow_panel.parquet", index=False)

    # SECOND counterfactual: the ratified variant with the two float-integrity
    # rules switched OFF but the manual exclusions still in force. This is what
    # answers "did adopting the rules move any member?" as a measurement rather
    # than an assertion -- and it is the panel the report's rule-impact section
    # diffs against. It costs nothing (no network, in-memory only).
    rules_off_panel, _ro_rejects = build_membership(
        RATIFIED_VARIANT, dates, shortlist, profiles, facts_by_cik, periodic, blocklist,
        exclusions=exclusions, shares_by_cik=shares_by_cik, ruleset=LEGACY_RULESET,
    )
    assert_pit_membership(rules_off_panel)
    rules_off_panel.to_parquet(
        CACHE_DIR / f"{RATIFIED_VARIANT}_rules_off_panel.parquet", index=False
    )
    # And the same with BOTH switched off: the pre-2026-08-21 build exactly.
    rules_and_exclusions_off, _rxo = build_membership(
        RATIFIED_VARIANT, dates, shortlist, profiles, facts_by_cik, periodic, blocklist,
        exclusions=(), shares_by_cik=shares_by_cik, ruleset=LEGACY_RULESET,
    )
    rules_and_exclusions_off.to_parquet(
        CACHE_DIR / f"{RATIFIED_VARIANT}_legacy_panel.parquet", index=False
    )
    _hy_key = set(zip(panels[RATIFIED_VARIANT]["recon_date"], panels[RATIFIED_VARIANT]["cik"]))
    _ro_key = set(zip(rules_off_panel["recon_date"], rules_off_panel["cik"]))
    print(
        f"[rules] membership delta from adopting the rules "
        f"(exclusions held constant): {len(_hy_key ^ _ro_key)} row(s) differ"
    )

    census, probes, former_probes, n_price_requests = price_census(
        pd.concat(panels.values()),
        profiles,
        args.price_probe_n,
        probe=not args.no_price_probe,
        probe_ciks={int(c) for v in OPTION_RECORD_VARIANTS for c in panels[v]["cik"]},
    )
    census.to_csv(OUT_DIR / "price_censoring_census.csv", index=False)
    census.to_parquet(OUT_DIR / "price_censoring_census.parquet", index=False)
    pd.DataFrame(probes).to_csv(OUT_DIR / "price_probe_sample.csv", index=False)
    pd.DataFrame(former_probes).to_csv(OUT_DIR / "price_probe_former_tickers.csv", index=False)

    flags = diligence_flags(panels, profiles, facts_by_cik, client)
    (CACHE_DIR / "diligence_flags.json").write_text(json.dumps(flags, indent=1, default=str))

    # The compensating control runs over the UNION of the ratified table and
    # BOTH of its counterfactuals. All three are needed, for one reason stated
    # three ways -- an audit must never be graded on its own homework:
    #   * the SHADOW rows (exclusions off), because auditing only the
    #     post-exclusion table would make the registrants the exclusions removed
    #     vanish from the very output that justifies removing them;
    #   * the LEGACY rows (rules AND exclusions off), for exactly the same
    #     reason one level up: from 2026-08-21 the two float-integrity rules
    #     also remove registrants, and arm D would otherwise report "no
    #     superseded-by-zero rows found" -- true, but only because rule 1 had
    #     already deleted them upstream. That would read as evidence the problem
    #     does not exist, when it is evidence the fix works;
    #   * the FINAL rows, because a registrant that backfilled a vacated bucket
    #     slot is a member of the ratified universe and has never been screened.
    if args.no_scale_audit:
        scale_audit, scale_summary = pd.DataFrame(), {}
    else:
        audit_panel = (
            pd.concat(
                [rules_and_exclusions_off, shadow_panel, panels[RATIFIED_VARIANT]],
                ignore_index=True,
            )
            .drop_duplicates(subset=["recon_date", "cik"], keep="first")
            .sort_values(["recon_date", "cik"])
            .reset_index(drop=True)
        )
        scale_audit, scale_summary = audit_float_scale(client, audit_panel, facts_by_cik)

    from e2_report import render_report  # local module written alongside this one

    render_report(
        dates=dates,
        panels=panels,
        spells=spells_by_variant,
        rejects=rejects_by_variant,
        profiles=profiles,
        shortlist=shortlist,
        census=census,
        probes=probes,
        former_probes=former_probes,
        flags=flags,
        suspects=suspects,
        args=args,
        request_count=client.request_count,
        price_request_count=n_price_requests,
        exclusions=exclusions,
        shadow_panel=shadow_panel,
        scale_audit=scale_audit,
        scale_summary=scale_summary,
        rules_off_panel=rules_off_panel,
        legacy_panel=rules_and_exclusions_off,
        shares_coverage={
            "diligence_ciks": len(diligence_ciks),
            "cached": len(shares_by_cik),
            "never_tagged": n_empty,
        },
    )
    print(f"[done] report -> {REPORT_PATH}")
    print(f"[done] network GETs this run: {client.request_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
