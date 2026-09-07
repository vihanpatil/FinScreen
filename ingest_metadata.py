"""
ingest_metadata.py -- pull 10-K/10-Q/8-K filing metadata for the E2
hybrid136 membership universe
(data/universe_e2_candidates/hybrid136.parquet) and store it in
data/filings_metadata_e2.db (SQLite).

Scope: metadata (accession numbers, real EDGAR public filing dates, form
types, and -- for 8-Ks -- the resolved earnings-release document, via the
filing_documents table / selection policy in this module), plus EDGAR-native
distress events, plus -- since F2 stage S3 -- an optional document PREFETCH
segment.

  --stage metadata   (default)  enumerate + validate + write the DB rows.
                                No filing text is downloaded, exactly as E1.
  --stage documents             download every 10-K/10-Q primary document and
                                every resolved earnings-exhibit path into the
                                cache-forever data/raw/documents/ cache.
                                Parses NOTHING and stores nothing but the
                                cache.
  --stage all                   both, in that order.

Why the E1-era line "no filing text is downloaded here" no longer holds
(F2_SPEC §4.6, ruling 10): extract.py fetched each document lazily while
parsing it. At E1's 639 documents that was invisible; at E2's ~20,553
documents / ~26 GB it welds a multi-hour network walk onto the extraction
pass, so a kill mid-run loses parsing progress and a re-run re-derives
sections nobody asked for. Splitting the walk out makes each half separately
resumable and lets F3's extract.py run at 0 GETs. `metadata` stays the
DEFAULT so the bare command still costs what it always did -- the ~26 GB
segment is opt-in, never a surprise.

Extraction (parsing documents into sections) is still extract.py's job, and
nothing in this module reads a document's bytes.

Point-in-time discipline: every row's `filing_date` is EDGAR's own recorded
public filing date for that accession (the `filingDate` field from
submissions.json), never a fiscal period end date. `report_date` (the fiscal
period end) is also stored, but only for reference -- it must never be used
as the point-in-time timestamp downstream.

-----------------------------------------------------------------------
E2 UNIVERSE (this module's input changed in F2 stage S2 -- read this)
-----------------------------------------------------------------------
E1 read a fixed 25-row `data/universe.csv` keyed on TICKER. E2 reads the
ratified dated membership table `hybrid136.parquet` keyed on **CIK**: 244
distinct member CIKs, 299 membership spells, 136 members at each of 11
annual point-in-time reconstitution dates (2016-07-01 .. 2026-07-01).

- `data/universe.csv` and `data/filings_metadata.db` are E1's FROZEN record.
  Nothing in this module reads or writes either of them any more; run()
  refuses to open E1's DB path.
- `load_universe()` verifies `hybrid136_checksums.json` on EVERY load
  (verify-artifact rule, HANDOFF §7) and pins the table's own invariants.
  A mismatch raises -- the hashes are re-pinned only by a deliberate edit,
  never auto-rebaselined.
- Membership is CIK-keyed everywhere. A member's ticker is NOT authoritative
  and is never a join key (F1 finding: a dead member's former symbol can
  resolve to a different company -- APC->ARKO, EMC->ETF). The `filings`
  table's `ticker` column is nullable and informational only.

Survivorship bias: E2 materially improves on E1 here but does not eliminate
it. The membership table is reconstructed point-in-time from pre-date
filings, so companies that were large caps in 2016 and were later acquired
or delisted ARE members for the dates they qualified (108 of the 244 member
CIKs are no longer members at 2026-07-01). What remains is outcome-side:
some of those names have no fetchable price series, which is counted and
reported rather than silently dropped (EXPANSION_PLAN §2c).

Idempotency: re-running this script does not force new network requests --
EdgarClient's own submissions-cache staleness policy (24h) governs whether
the underlying data.sec.gov call happens at all. This script always
recomputes the SQLite rows from whatever's in the cache (cheap, local,
no network), and uses INSERT OR REPLACE keyed on accession_number so re-runs
are safe.

validate_universe() (see below) is a hard-fail pass that runs against every
company's cached submissions data *before* the ingestion loop writes
anything to the DB. It exists because two narrow Week-1 patches (the XOM
CIK override and the exhibit-filename-unreliable fix) turned out to be
symptoms of the same underlying gap: nothing verified a resolved CIK's data
was actually *complete*. See INGESTION_NOTES.md for the full writeup and the
concrete JPM/BAC/GS bug this caught. In E2 every check runs against the
company's OWN coverage window, because a late entrant and a delisted exit
are expected states, not failures (F2_SPEC §3.1).
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from edgar_client import DEFAULT_MAX_AGE_HOURS, EdgarClient

REPO_ROOT = Path(__file__).resolve().parent
UNIVERSE_DIR = REPO_ROOT / "data" / "universe_e2_candidates"
HYBRID136_PARQUET = UNIVERSE_DIR / "hybrid136.parquet"
HYBRID136_CHECKSUMS = UNIVERSE_DIR / "hybrid136_checksums.json"
VALIDATION_EXCEPTIONS_PATH = REPO_ROOT / "data" / "f2" / "validation_exceptions.csv"
EX99_AUDIT_PATH = REPO_ROOT / "data" / "f2" / "ex99_selection_audit.csv"
EARNINGS_DOC_OVERRIDES_PATH = REPO_ROOT / "data" / "f2" / "earnings_doc_overrides.csv"

# E2 writes a NEW database. E1's is frozen as its record, exactly like
# data/labels.parquet (F2_SPEC §1.4 / ruling 4).
DB_PATH = REPO_ROOT / "data" / "filings_metadata_e2.db"
E1_DB_PATH = REPO_ROOT / "data" / "filings_metadata.db"
E1_UNIVERSE_CSV = REPO_ROOT / "data" / "universe.csv"

TARGET_FORMS = {"10-K", "10-Q", "8-K"}
# The two periodic forms, whose primary document `--stage documents`
# prefetches. 8-K text is reached through the resolved earnings-document path
# instead (an EX-99 exhibit or the 8-K body), never through primary_document.
PERIODIC_FORMS = ("10-K", "10-Q")

STAGES = ("metadata", "documents", "all")
# `metadata` is the DEFAULT deliberately: --stage documents is a ~20,553-GET /
# ~26 GB walk (F2_SPEC §4.6), and a bare `python3 ingest_metadata.py` must not
# silently become that. The S6 runbook names its stage explicitly either way.
DEFAULT_STAGE = "metadata"

# ---------------------------------------------------------------------------
# EDGAR-native distress events (F2_SPEC §4.5, EXPANSION_PLAN §2c)
# ---------------------------------------------------------------------------
# These rows are ALREADY inside the submissions JSON the enumeration pass
# parses, so collecting them costs exactly ZERO extra network requests. They
# exist so a member that leaves the universe stays visible as a delisting /
# deregistration / bankruptcy rather than as a silent gap -- the outcome-side
# survivorship residual EXPANSION_PLAN §2c makes it mandatory to mitigate.
#
# `25-NSE` is filed by the EXCHANGE, not the company, and fires for preferreds
# and notes as well as common stock: it is stored, but it is a NOISY series and
# is reported separately from the meaningful three (Form 25, Form 15, item
# 1.03). MEASURED in-window over the 244 members: Form 25 37 filings / 30 CIKs;
# 25-NSE 510 / 131; 15-12B 65 / 42; 15-12G 22 / 21; 15-15D 32 / 13; 8-K item
# 1.03 2 filings / 1 CIK (895126, Expand Energy / Chesapeake).
DISTRESS_EVENT_KINDS = {
    "25": "delisting_form_25",
    "25-NSE": "delisting_form_25_nse_exchange_filed",
    "15-12B": "deregistration_form_15",
    "15-12G": "deregistration_form_15",
    "15-15D": "deregistration_form_15",
    "15F-12B": "deregistration_form_15",
    "15F-12G": "deregistration_form_15",
}
BANKRUPTCY_ITEM_CODE = "1.03"
BANKRUPTCY_EVENT_KIND = "bankruptcy_8k_item_1_03"
NOISY_DISTRESS_EVENT_KINDS = ("delisting_form_25_nse_exchange_filed",)

# ---------------------------------------------------------------------------
# EX-99 earnings-exhibit selection audit (F2_SPEC §4.4)
# ---------------------------------------------------------------------------
# 219 of the 244 member CIKs are filers E1's selection policy has never seen,
# and three whole sectors are new. The policy itself is NOT changed
# speculatively -- it is audited on real output, and its failures are COUNTED
# instead of being printed and forgotten (E1 printed a WARN and moved on,
# leaving the earnings_doc_* columns untouched and the failure untracked).
EARNINGS_DOC_UNRESOLVED_FATAL_RATE = 0.01  # >1% of earnings 8-Ks -> FATAL
# The §4.4(4) manual read is capped at this many filers, worst-first by
# low-confidence count; the untouched remainder is reported honestly rather
# than silently dropped. The read itself happens at S6, by a human.
EX99_MANUAL_READ_CAP = 20

# ---------------------------------------------------------------------------
# Fixed corpus window (F2_SPEC §2). These are LITERALS on purpose.
# ---------------------------------------------------------------------------
# E1 derived its window from date.today() (`lookback_cutoff(today, 12
# quarters)`), which made the corpus a function of when you happened to run
# the script. E2 pins both ends so a re-run in October reproduces the same
# corpus. Nothing in F2 derives a window boundary from date.today().
#
# 2015-07-01, not 2016-01-01: the first reconstitution date is 2016-07-01,
# and a trailing-four-quarter text feature evaluated at a company's first
# membership date needs its filings back to ~2015-07-01. Measured cost of
# the extra six months: +5.0% target filings (45,622 vs 43,445).
#
# 2026-08-31: the E2 corpus freeze date. Enumeration filters
# `filing_date <= CORPUS_WINDOW_END`; the run report states the OBSERVED max
# filing_date beside it so the gap between freeze date and run date is
# visible rather than assumed to be zero.
CORPUS_WINDOW_START = date(2015, 7, 1)
CORPUS_WINDOW_END = date(2026, 8, 31)
#
# ENUMERATION WINDOW vs COVERAGE WINDOW -- read this before changing either.
#
# The ingestion loop enumerates every member CIK over the SHARED
# [CORPUS_WINDOW_START, CORPUS_WINDOW_END], NOT over that member's own
# per-company coverage window. The per-company window
# (coverage_start/coverage_end, §1.2) governs VALIDATION only (F2_SPEC §3.1:
# "each check now runs over [coverage_start(cik), coverage_end(cik)]"), because
# a late entrant and a delisted exit are expected states for a CHECK. It does
# not govern what gets ingested.
#
# Why (F2_SPEC ruling §9.1 items 1-2 / §4.2): "ingest the full E2 window for
# every CIK that is ever a member; do not clip fetches to membership spells",
# and §2 names CORPUS_WINDOW_START "documents/metadata enumeration floor".
# §4.1's prose sentence writes the filter as
# `coverage_start <= filing_date <= CORPUS_WINDOW_END`, which disagrees with
# the ruling; re-measured 2026-08-24 against the cached submissions, the SHARED
# window is what every MEASURED number in the plan of record was computed on:
#
#            enumeration filter        10-K   10-Q    8-K   total  earnings 8-K
#   shared   [2015-07-01, 2026-08-31]  2,452  7,532  35,638  45,622  10,569  <- F2_SPEC §4.1 exactly
#   clipped  [coverage_start, cov_end] 1,883  5,830  27,936  35,649   8,242
#
# and the same holds for §4.5's distress table (shared window reproduces
# 25:37/30, 25-NSE:510/131, 15-12B:65/42, 15-12G:22/21, 15-15D:32/13 and
# item 1.03:2/1 exactly; clipping loses the bankruptcy entirely) and for §7's
# runbook budget (9,984 periodic primaries = 2,452 + 7,532).
#
# The bankruptcy case is the concrete reason clipping is WRONG here, not just
# off-budget: CIK 895126 (Expand Energy, ex-Chesapeake) first qualifies as a
# member at 2026-07-01, so its coverage_start is 2024-07-01 and its 2020-06-28
# item-1.03 filing falls outside its own window. EXPANSION_PLAN §2c makes
# ingesting exactly that event mandatory.
#
# Ingesting wider than the universe is PIT-safe -- breadth never implies
# membership -- but it does mean "present in `filings`" is NOT "in the
# universe". F5 joins on `universe_membership`, and every run prints the count
# of ingested filings outside every membership spell (§4.2's binding
# condition).
# Fundamentals and prices keep FULL available history (as E1 did) and are
# point-in-time-selected downstream, so they take no window at all.
FUNDAMENTALS_HISTORY = "full"
PRICES_HISTORY = "full"

# Per-company coverage window derivation (F2_SPEC §1.2).
# 730 days: hybrid136's own eligibility rule already guarantees >=1 10-K/10-Q
# in each of the 8 calendar quarters before every reconstitution date, so
# this is the interval the company is *known* to have filed across.
# 400 days: ~one annual reporting cycle past the last date the company was a
# member, so its final 10-K lands inside the window.
COVERAGE_LOOKBACK_DAYS = 730
COVERAGE_TAIL_DAYS = 400

# Exact pins re-derived from the ratified table (F2_SPEC §1.3). These replace
# E1's `20 <= len(df) <= 30` range with the same "refuse to proceed silently
# on a scope change" intent, one level stricter.
EXPECTED_MEMBER_CIKS = 244
EXPECTED_MEMBERSHIP_SPELLS = 299
EXPECTED_MEMBERS_PER_DATE = 136
EXPECTED_RECONSTITUTION_DATES = 11

# -- validate_universe() thresholds -------------------------------------
# Every number below was re-derived against the real 244-member x 11-year
# distribution from the cached submissions (F2_SPEC §3.1), not carried over
# from E1's 25 always-filing mega-caps. The measured figures are stated
# beside each threshold so a future recalibration can see what it is moving.

# Max gap between consecutive 10-K/10-Q filings, measured only INSIDE the
# company's own coverage window. MEASURED per-member max-gap distribution
# over 244 members: median 114, p90 124, p95 126, p99 142, max 266.
#   > 135 d yields 5 WARN findings across 4 members: CIK 849399 Gen Digital
#     266 d, 1637459 Kraft Heinz 217 d, 1393612 Discover 145 d, 77476 PepsiCo
#     139 d and 136 d (two gaps) -- all fiscal-calendar quirks, so WARN.
#     (F2_SPEC §3.1 reports 5 MEMBERS including Autodesk at 189 d; that gap
#     is in Autodesk's FULL history, outside its 2019-07-02..2023-08-05
#     coverage window, so the spec's own "measured only inside the coverage
#     window" rule excludes it. Re-measured 2026-08-24.)
#   > 300 d fires on 0 members. The FATAL arm's real job is catching a
#     silently truncated filings.files[] fetch (the JPM/BAC/GS bug), which
#     shows up as >=3 consecutive missed quarters.
MAX_FILING_GAP_DAYS = 135          # WARN above this
FATAL_FILING_GAP_DAYS = 300        # FATAL above this

# Staleness of the most recent filing of ANY form, measured against
# CORPUS_WINDOW_END and only for CURRENT members. MEASURED: max 48 days
# across the 136 current members, so 80 fires on none of them. WARN, never
# FATAL -- an ordinary quiet filing period is not a stopped filer.
MAX_STALE_ANY_FILING_DAYS = 80
RECENT_ACTIVITY_ANY_FORM_SEVERITY = "WARN"

# Staleness of the most recent 10-K/10-Q, measured against CORPUS_WINDOW_END.
# FATAL only for a current member; for a former member this is the expected
# delisting/acquisition exit and is reported as `member_stopped_filing` at
# INFO (EXPANSION_PLAN §2c: censored names stay visible, never silent).
# MEASURED at 2026-08-31: current members' max staleness is 104 days, so the
# FATAL arm fires on 0 of 136; 29 former members are stale by >135 days --
# and by >200 days, and by >250 -- i.e. the count is threshold-insensitive
# across that whole band and equals F1's independently derived 29
# delisting-censored members.
MAX_STALE_10K_10Q_DAYS = 135
RECENT_ACTIVITY_10K10Q_SEVERITY = "FATAL"

# Periodic (10-K + 10-Q) filings per coverage-year. E1's absolute floors
# (2 10-K / 7 10-Q per fixed 12-quarter window) are meaningless on churning
# membership with per-company windows of very different lengths, so this is
# a RATE.
#
# The denominator is the span from `coverage_start` to the company's LAST
# in-window periodic filing -- not the full coverage window. This matters:
# `coverage_end` for a former member runs 400 days past its last membership
# date, and an acquired company files nothing in that tail. Charging that
# tail against the rate would FATAL 19 delisted members for the fact of
# being delisted, which `recent_activity_10k_10q`/`member_stopped_filing`
# already reports and which EXPANSION_PLAN §3.6 explicitly calls an expected
# state. This check's job is to catch a truncated fetch (a hole in the
# middle), not to re-flag a delisting.
#
# MEASURED over the 244 members on that definition: min 4.01, p5 4.05,
# median 4.08, max 4.53 -- all 244 pass both bands. 3.5 = min-observed -10%,
# the same calibration discipline E1 used.
MIN_PERIODIC_FILINGS_PER_YEAR_FATAL = 3.5
MIN_PERIODIC_FILINGS_PER_YEAR_WARN = 3.9

# The `member_stopped_filing` INFO threshold is the same staleness number as
# the FATAL arm -- one measurement, two dispositions depending on whether
# the company is still a member.

# Every check name validate_universe() can emit at FATAL severity. Kept as an
# explicit allowlist, not derived by introspection, so adding a new FATAL
# check elsewhere in this file can't silently become exception-eligible
# without a deliberate edit here too. This is the set
# data/f2/validation_exceptions.csv may name; anything else is refused at
# load time.
FATAL_CHECK_NAMES = {
    "entity_resolves",
    "history_reaches_cutoff",
    "plausible_filing_counts",
    "no_large_filing_gap",
    "recent_activity_10k_10q",
    # Emitted by the EX-99 selection audit (F2_SPEC §4.4): WARN per failed
    # earnings-document resolution, FATAL if the aggregate failure rate
    # exceeds 1% of earnings 8-Ks. Named here so the exceptions file's
    # validation knows about it in one place.
    "earnings_doc_unresolved",
    # Also the EX-99 audit (F2_SPEC §4.4 item 5): every one of the 8 sectors
    # must show at least one HIGH-confidence EX99_PRESS_RELEASE selection. A
    # sector with none means the selection policy does not work on that
    # sector's filers -- "a blocker, not a footnote".
    "ex99_sector_coverage",
}

# The two checks above are computed AFTER the ingestion loop (they are about
# its output), unlike everything validate_universe() emits. Kept as an explicit
# set so the run summary can say which findings are post-ingestion, and so a
# reader knows a FATAL here means "the rows are written, now go read the
# audit", not "nothing was written".
POST_INGESTION_CHECK_NAMES = {"earnings_doc_unresolved", "ex99_sector_coverage"}

# A ValidationProblem that is about the whole run rather than one member
# (only `cik_map_fetch` today) carries this sentinel. 0 is not a valid EDGAR
# CIK, so it is unambiguous, and it keeps the DB column NOT NULL.
RUN_SCOPE_CIK = 0

# Parses the EDGAR filing index HTML's document tables ("Document Format
# Files" and "Data Files"). Rows look like:
#   <tr> <td>seq</td> <td>description</td>
#        <td><a href="...">FILENAME</a></td> <td>TYPE</td> <td>size</td> </tr>
_TABLE_RE = re.compile(r'<table[^>]*summary="([^"]*)"[^>]*>(.*?)</table>', re.S | re.IGNORECASE)
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.IGNORECASE)
_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_HREF_RE = re.compile(r'href="([^"]+)"')

POSITIVE_DESC_KEYWORDS = ("PRESS RELEASE", "NEWS RELEASE", "EARNINGS RELEASE")
NEGATIVE_DESC_KEYWORDS = ("PRESENTATION", "SUPPLEMENTAL", "COMMENTARY", "DATA SUMMARY")


# ---------------------------------------------------------------------------
# Universe: the hybrid136 dated membership table (F2_SPEC §1)
# ---------------------------------------------------------------------------

# Columns hybrid136.parquet must carry for F2 to consume it. The remaining
# columns (n_reconstitutions, entry_sector_rank, ...) are descriptive and are
# deliberately not depended on.
MEMBERSHIP_COLUMNS = (
    "cik", "name", "tickers", "sector", "stratum", "sic", "member_from", "member_to",
)


def verify_universe_checksums(path: Path = HYBRID136_CHECKSUMS) -> dict[str, str]:
    """Re-hash every file `hybrid136_checksums.json` pins and raise on any
    mismatch (verify-artifact rule, HANDOFF §7).

    Deliberately a SEPARATE file from `option_record_checksums.json`, which
    guards the frozen continuity5/broad8 option record behind the owner's
    2026-08-21 decision and must not be disturbed. If F1 is ever legitimately
    re-run, these hashes are re-pinned by a deliberate edit -- never
    auto-rebaselined from whatever happens to be on disk.
    """
    doc = json.loads(path.read_text())
    pinned: dict[str, str] = doc["sha256"]
    mismatches: list[str] = []
    for name, expected in sorted(pinned.items()):
        target = path.parent / name
        if not target.exists():
            mismatches.append(f"  {name}: MISSING from {path.parent}")
            continue
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != expected:
            mismatches.append(f"  {name}:\n    pinned {expected}\n    actual {actual}")
    if mismatches:
        raise ValueError(
            f"{path.name}: {len(mismatches)} universe artifact(s) do not match "
            f"their pinned sha256. Refusing to build E2 on an artifact that is "
            f"not the one the plan of record was written against.\n"
            + "\n".join(mismatches)
        )
    return pinned


def load_membership(verify: bool = True) -> pd.DataFrame:
    """The membership SPELLS table -- one row per (cik, contiguous run of
    reconstitution dates). 299 rows over 244 CIKs.

    `member_to` is EXCLUSIVE -- it is the first reconstitution date at which
    the CIK is no longer a member, not the last one at which it was.
    (F2_SPEC §1.2's prose says "last reconstitution date"; the artifact
    disagrees and the artifact wins. Verified against the panel: for all 299
    spells, `len([d for d in recon_dates if member_from <= d < member_to])`
    equals the spell's own `n_reconstitutions`, and the spells reproduce the
    panel's membership set exactly at all 11 dates. Example: PG spell
    2016-07-01 -> 2020-07-01 has n_reconstitutions=4 and PG is absent from
    the 2020-07-01 panel.) `member_to == ''` means the spell is still open,
    i.e. the CIK is a member at 2026-07-01.

    Read in place from F1's output directory, never copied: two copies drift.
    """
    if verify:
        verify_universe_checksums()
    df = pd.read_parquet(HYBRID136_PARQUET)
    missing = [c for c in MEMBERSHIP_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{HYBRID136_PARQUET.name} missing column(s): {missing}")
    if len(df) != EXPECTED_MEMBERSHIP_SPELLS:
        raise ValueError(
            f"{HYBRID136_PARQUET.name} has {len(df)} membership spells -- "
            f"expected exactly {EXPECTED_MEMBERSHIP_SPELLS}. Refusing to proceed "
            f"silently on a scope change; either F1's artifact moved (re-pin the "
            f"checksums and this constant deliberately) or the wrong file is on disk."
        )
    df = df.copy()
    df["cik"] = df["cik"].astype(int)
    df["member_from"] = df["member_from"].astype(str)
    df["member_to"] = df["member_to"].fillna("").astype(str)
    return df


def load_universe(verify: bool = True) -> pd.DataFrame:
    """One row per member CIK -- the ingestion loop's input.

    Collapses the 299 spells into 244 CIK rows and derives the per-company
    coverage window every E2 validation check and enumeration runs against
    (F2_SPEC §1.2):

      coverage_start = max(CORPUS_WINDOW_START, min(member_from) - 730 d)
      coverage_end   = CORPUS_WINDOW_END                       if still a member
                     = min(CORPUS_WINDOW_END, max(member_to) + 400 d) otherwise
      is_current_member = any spell has member_to == ''

    Note `member_to` is exclusive (see load_membership()), so the tail is in
    practice ~1 year + 400 days past the last date the company was actually a
    member. That is wider than F2_SPEC §1.2's prose describes and strictly
    conservative: the window is a superset, so no filing that matters is
    excluded, and membership itself is still joined from
    `universe_membership` downstream, never inferred from this window.

    `cik` is the join key for the entire E2 pipeline. There is deliberately
    no `ticker` column: a member's ticker is not authoritative (31 member
    CIKs have none at all in EDGAR's own submissions) and mapping a dead
    member by its former symbol is the F1 trap. Price-side ticker resolution
    is CIK-verified separately in ingest_prices.py.
    """
    spells = load_membership(verify=verify)
    rows: list[dict] = []
    for cik, g in spells.groupby("cik", sort=True):
        first_from = min(date.fromisoformat(d) for d in g["member_from"])
        is_current = bool((g["member_to"] == "").any())
        coverage_start = max(
            CORPUS_WINDOW_START, first_from - timedelta(days=COVERAGE_LOOKBACK_DAYS)
        )
        if is_current:
            coverage_end = CORPUS_WINDOW_END
        else:
            last_to = max(date.fromisoformat(d) for d in g["member_to"])
            coverage_end = min(
                CORPUS_WINDOW_END, last_to + timedelta(days=COVERAGE_TAIL_DAYS)
            )
        rows.append(
            {
                "cik": int(cik),
                "name": g["name"].iloc[0],
                "sector": g["sector"].iloc[0],
                "stratum": g["stratum"].iloc[0],
                "coverage_start": coverage_start,
                "coverage_end": coverage_end,
                "is_current_member": is_current,
            }
        )
    df = pd.DataFrame(rows)
    if len(df) != EXPECTED_MEMBER_CIKS:
        raise ValueError(
            f"hybrid136 collapses to {len(df)} member CIKs -- expected exactly "
            f"{EXPECTED_MEMBER_CIKS}. Refusing to proceed silently on a scope "
            f"change (this replaces E1's 20-30 range bound with an exact pin; "
            f"see F2_SPEC §1.3)."
        )
    return df


def init_db(conn: sqlite3.Connection) -> None:
    """Create the E2 schema (F2_SPEC §1.4). Every change against E1's schema
    is additive-or-widening, and it lands in a NEW database file --
    data/filings_metadata.db is E1's frozen record and is never migrated in
    place.

    `ticker` is nullable in both `companies` and `filings` and is
    informational only: 31 member CIKs have no ticker at all in EDGAR's
    submissions, and shared-CIK multi-class names break a ticker key. `cik`
    is the join key everywhere.
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS companies (
            cik INTEGER PRIMARY KEY,
            ticker TEXT,                     -- nullable, informational only
            sector TEXT NOT NULL,
            company_name TEXT NOT NULL,
            stratum TEXT,                    -- 'core' | 'extension'
            coverage_start TEXT,             -- per-company window, F2_SPEC §1.2
            coverage_end TEXT,
            is_current_member INTEGER        -- 1 if a member at the last recon date
        );

        -- The membership spells themselves, so downstream can join membership
        -- without re-reading the parquet. F5 joins on THIS table, never on
        -- "present in filings" -- the ingested corpus is deliberately wider
        -- than the universe (F2_SPEC §4.2).
        CREATE TABLE IF NOT EXISTS universe_membership (
            cik INTEGER NOT NULL,
            sector TEXT,
            stratum TEXT,
            member_from TEXT NOT NULL,
            member_to TEXT,                  -- '' / NULL = still a member
            PRIMARY KEY (cik, member_from)
        );

        -- EDGAR-native distress outcomes, so censored names stay visible
        -- (EXPANSION_PLAN §2c). Populated by S3 while enumerating, at zero
        -- extra network cost -- the rows are already in submissions.json.
        CREATE TABLE IF NOT EXISTS distress_events (
            cik INTEGER NOT NULL,
            accession_number TEXT NOT NULL,
            form TEXT NOT NULL,
            filing_date TEXT NOT NULL,
            items TEXT,
            event_kind TEXT NOT NULL,
            PRIMARY KEY (accession_number, event_kind)
        );

        CREATE TABLE IF NOT EXISTS filings (
            accession_number TEXT PRIMARY KEY,
            cik INTEGER NOT NULL,
            ticker TEXT,                     -- nullable, informational only
            form TEXT NOT NULL,
            filing_date TEXT NOT NULL,       -- EDGAR public filing date (point-in-time field)
            report_date TEXT,                -- fiscal period end -- reference only, NEVER point-in-time
            acceptance_datetime TEXT,
            primary_document TEXT,
            items TEXT,                      -- raw 8-K item codes, e.g. "2.02,9.01"
            has_earnings_item BOOLEAN,        -- item 2.02 present (proxy for an earnings-release 8-K)
            ex99_1_document TEXT,             -- filename of a resolved EX-99.x exhibit ONLY
                                               -- (NULL if no exhibit exists for this filing --
                                               -- see earnings_doc_* columns for the general case,
                                               -- which also covers the 8K_BODY fallback)
            exhibit_lookup_done BOOLEAN DEFAULT 0,  -- whether we've checked the filing index yet
            earnings_doc_filename TEXT,        -- resolved earnings document filename (exhibit OR
                                               -- primary 8-K body -- see select_earnings_document())
            earnings_doc_relative_path TEXT,   -- path under /Archives/edgar/data/... for the above
            earnings_doc_section_type TEXT,    -- 'EX99_PRESS_RELEASE' or '8K_BODY'
            earnings_doc_selection_confidence TEXT,  -- 'high' | 'medium' | 'low'
            FOREIGN KEY (cik) REFERENCES companies(cik)
        );

        -- Co-registrant attributions dropped by `filings`' accession-keyed
        -- primary key (main session ruling, 2026-08-24; F2_PROGRESS §5).
        -- EDGAR lists co-registrants on ONE accession -- a parent and its
        -- subsidiary file a single 8-K together -- so when BOTH are members,
        -- `filings` can hold the row only once. The row is kept under
        -- `kept_cik` (the deterministic keeper: the numerically LOWEST member
        -- CIK on that accession) and every dropped attribution is recorded
        -- here, one row per (accession, co_cik).
        --
        -- BINDING DOWNSTREAM RULE: absence from `filings` alone is NEVER
        -- evidence a company did not file. Any per-company filing or coverage
        -- question consults `filings` UNION `co_registrant_filings`, and F5's
        -- accession -> company attribution must yield BOTH member CIKs for
        -- these accessions.
        CREATE TABLE IF NOT EXISTS co_registrant_filings (
            accession_number TEXT NOT NULL,
            kept_cik INTEGER NOT NULL,   -- the CIK the `filings` row is stored under
            co_cik INTEGER NOT NULL,     -- the member CIK whose attribution was dropped
            form TEXT NOT NULL,
            filing_date TEXT NOT NULL,
            PRIMARY KEY (accession_number, co_cik)
        );

        CREATE TABLE IF NOT EXISTS filing_documents (
            accession_number TEXT NOT NULL,
            seq INTEGER,
            doc_type TEXT,
            description TEXT,
            filename TEXT,
            relative_path TEXT,
            source_table TEXT,               -- 'Document Format Files' or 'Data Files'
            FOREIGN KEY (accession_number) REFERENCES filings(accession_number)
        );

        CREATE TABLE IF NOT EXISTS universe_validation_problems (
            run_date TEXT NOT NULL,
            cik INTEGER NOT NULL,            -- 0 = whole-run scope, not a member
            ticker TEXT,                     -- nullable, informational only
            stage TEXT NOT NULL,             -- 'metadata' | 'documents'
            check_name TEXT NOT NULL,
            severity TEXT NOT NULL,          -- 'FATAL' | 'WARN' | 'INFO'
            message TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_co_registrant_co_cik
            ON co_registrant_filings(co_cik);
        CREATE INDEX IF NOT EXISTS idx_filings_cik ON filings(cik);
        CREATE INDEX IF NOT EXISTS idx_filings_form ON filings(form);
        CREATE INDEX IF NOT EXISTS idx_filings_date ON filings(filing_date);
        CREATE INDEX IF NOT EXISTS idx_filings_cik_date ON filings(cik, filing_date);
        CREATE INDEX IF NOT EXISTS idx_filing_documents_accession
            ON filing_documents(accession_number);
        """
    )
    conn.commit()


def upsert_company(conn: sqlite3.Connection, row: pd.Series) -> None:
    """`row` is one row of load_universe()'s CIK-keyed frame. `ticker` is
    written as NULL here: E2's universe carries no authoritative ticker (see
    load_universe()'s docstring); ingest_prices.py resolves one CIK-verified
    per member for price fetching only.
    """
    conn.execute(
        "INSERT INTO companies "
        "(cik, ticker, sector, company_name, stratum, coverage_start, coverage_end, "
        " is_current_member) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(cik) DO UPDATE SET sector=excluded.sector, "
        "company_name=excluded.company_name, stratum=excluded.stratum, "
        "coverage_start=excluded.coverage_start, coverage_end=excluded.coverage_end, "
        "is_current_member=excluded.is_current_member",
        (
            int(row["cik"]), None, row["sector"], row["name"], row["stratum"],
            row["coverage_start"].isoformat(), row["coverage_end"].isoformat(),
            int(bool(row["is_current_member"])),
        ),
    )


def write_membership(conn: sqlite3.Connection, spells: pd.DataFrame) -> None:
    """Persist the 299 membership spells verbatim. Idempotent: full replace,
    since the table is a copy of a checksum-pinned artifact."""
    conn.execute("DELETE FROM universe_membership")
    conn.executemany(
        "INSERT INTO universe_membership (cik, sector, stratum, member_from, member_to) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (int(r["cik"]), r["sector"], r["stratum"], r["member_from"],
             r["member_to"] or None)
            for _, r in spells.iterrows()
        ],
    )
    conn.commit()


def extract_target_filings(recent: dict, start: date, end: date) -> list[dict]:
    """`recent` is a filings.recent-shaped dict of parallel arrays -- either
    the raw `submissions["filings"]["recent"]` or the pagination-merged
    result of EdgarClient.get_effective_recent().

    Filters to TARGET_FORMS with `start <= filing_date <= end`. Both bounds
    are inclusive and both are required: E2's window has a FIXED end
    (CORPUS_WINDOW_END), so a re-run on a later date yields the same corpus.
    Rows carry no ticker -- the caller attaches the CIK.
    """
    n = len(recent["form"])
    out = []
    for i in range(n):
        form = recent["form"][i]
        if form not in TARGET_FORMS:
            continue
        filing_date_str = recent["filingDate"][i]
        filing_date = date.fromisoformat(filing_date_str)
        if filing_date < start or filing_date > end:
            continue
        items = recent.get("items", [""] * n)[i]
        items_list = [x.strip() for x in items.split(",")] if items else []
        out.append(
            {
                "accession_number": recent["accessionNumber"][i],
                "form": form,
                "filing_date": filing_date_str,
                "report_date": recent.get("reportDate", [""] * n)[i] or None,
                "acceptance_datetime": recent.get("acceptanceDateTime", [""] * n)[i] or None,
                "primary_document": recent.get("primaryDocument", [""] * n)[i] or None,
                "items": items or None,
                # Split-and-compare-exactly, not a substring check -- a
                # substring match on raw "items" text has a theoretical
                # false-positive risk (e.g. a hypothetical future item code
                # containing "2.02" as a substring of a longer code).
                "has_earnings_item": "2.02" in items_list,
            }
        )
    return out


def extract_distress_events(recent: dict, cik: int, start: date, end: date) -> list[dict]:
    """EDGAR-native distress outcomes for one company, read out of the SAME
    `filings.recent`-shaped dict extract_target_filings() consumes (F2_SPEC
    §4.5). Zero extra network requests -- these rows are already in the
    submissions JSON.

    Two disjoint sources, both windowed to the company's own coverage window
    so the corpus and the event series describe the same interval:

      - a form in DISTRESS_EVENT_KINDS (Form 25 / 25-NSE delisting, Form 15
        deregistration and its foreign-private-issuer 15F variants);
      - an 8-K carrying item 1.03 (bankruptcy or receivership). Matched by
        exact item code against the split list, never as a substring of the
        raw items text -- "11.03" must not read as "1.03".

    An 8-K with item 1.03 is also a TARGET_FORM, so it legitimately appears in
    both `filings` and `distress_events`; the tables answer different
    questions and the accession number joins them.
    """
    n = len(recent["form"])
    items_col = recent.get("items", [""] * n)
    out: list[dict] = []
    for i in range(n):
        form = recent["form"][i]
        filing_date_str = recent["filingDate"][i]
        filing_date = date.fromisoformat(filing_date_str)
        if filing_date < start or filing_date > end:
            continue
        items = items_col[i] or ""
        items_list = [x.strip() for x in items.split(",")] if items else []
        kind = DISTRESS_EVENT_KINDS.get(form)
        if kind is None and form == "8-K" and BANKRUPTCY_ITEM_CODE in items_list:
            kind = BANKRUPTCY_EVENT_KIND
        if kind is None:
            continue
        out.append(
            {
                "cik": int(cik),
                "accession_number": recent["accessionNumber"][i],
                "form": form,
                "filing_date": filing_date_str,
                "items": items or None,
                "event_kind": kind,
            }
        )
    return out


def write_distress_events(conn: sqlite3.Connection, events: list[dict]) -> None:
    """Idempotent on re-run: INSERT OR REPLACE on the (accession_number,
    event_kind) primary key, same discipline as the filings upsert."""
    if not events:
        return
    conn.executemany(
        "INSERT OR REPLACE INTO distress_events "
        "(cik, accession_number, form, filing_date, items, event_kind) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            (e["cik"], e["accession_number"], e["form"], e["filing_date"],
             e["items"], e["event_kind"])
            for e in events
        ],
    )


def write_co_registrant_filings(conn: sqlite3.Connection, rows: list[dict]) -> None:
    """Persist every co-registrant attribution `filings` could not hold.

    Idempotent on re-run: INSERT OR REPLACE on the (accession_number, co_cik)
    primary key, same discipline as the filings and distress upserts.
    """
    if not rows:
        return
    conn.executemany(
        "INSERT OR REPLACE INTO co_registrant_filings "
        "(accession_number, kept_cik, co_cik, form, filing_date) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (r["accession_number"], int(r["kept_cik"]), int(r["co_cik"]),
             r["form"], r["filing_date"])
            for r in rows
        ],
    )


def summarize_distress_events(events: list[dict]) -> str:
    """One line per event kind, with the noisy exchange-filed 25-NSE series
    labelled as such rather than pooled with the meaningful three."""
    if not events:
        return "  (none in the corpus window for any member)"
    by_kind: dict[str, set[int]] = {}
    counts: dict[str, int] = {}
    for e in events:
        counts[e["event_kind"]] = counts.get(e["event_kind"], 0) + 1
        by_kind.setdefault(e["event_kind"], set()).add(e["cik"])
    lines = []
    for kind in sorted(counts):
        noise = "  [NOISY: filed by the exchange, fires for preferreds/notes too]" \
            if kind in NOISY_DISTRESS_EVENT_KINDS else ""
        lines.append(
            f"  {kind:<42} {counts[kind]:>6} filing(s) / "
            f"{len(by_kind[kind]):>4} CIK(s){noise}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Filing index HTML parsing + earnings-document selection (Phase A3)
# ---------------------------------------------------------------------------


def _clean_cell(raw_html: str) -> str:
    """Strip tags, then HTML-entity-unescape, then whitespace-strip a table
    cell's inner HTML. Order matters: the "Complete submission text file"
    row's Type cell is the literal markup `&nbsp;` (not a tag) -- unescaping
    first turns that into a real non-breaking-space character, which
    `str.strip()` correctly treats as whitespace, yielding a clean empty
    string instead of the 6-character literal "&nbsp;" a tag-strip-only
    parse would produce.
    """
    text = _TAG_RE.sub("", raw_html)
    text = html.unescape(text)
    return text.strip()


def parse_index_html_documents(html_text: str, primary_document: str | None = None) -> list[dict]:
    """Parse both index tables (Document Format Files + Data Files) on an
    EDGAR `-index.html` page into structured document rows: {"seq",
    "description", "filename", "relative_path", "doc_type", "source_table"}.

    Hardening, per the Opus review that found the underlying "nothing
    verifies completeness" gap:
      - Cell text is tag-stripped AND HTML-entity-unescaped (see
        _clean_cell) before any comparison.
      - Every index data row (>=5 <td> cells) must yield a parsed row: a
        data row whose Document cell carries no hyperlink would be silently
        dropped by this href-required parse, so it raises instead. This is
        the exact failure mode the guard exists for, measured directly
        rather than inferred from a row count.
      - At least one row must parse.
      - If `primary_document` is given, asserts it appears among the parsed
        filenames, else raises -- a parse that can't even find the filing's
        own primary document is broken, and a future EDGAR layout change
        should fail loudly here rather than silently resolving to "no
        exhibit found" (which looks identical to the legitimate no-exhibit
        case downstream).

    RECALIBRATED 2026-08-24 (S6 segment-1 diagnosis). The guard used to
    require >=3 parsed rows across both tables. That threshold was
    calibrated on E1's 25 mega-caps, which always attach an EX-99.1 press
    release, so their indices always carry >=3 rows (body + exhibit +
    "Complete submission text file"). At E2's 244-member scale it produced
    64 FALSE parse failures, every one of them the same dialect: a
    SINGLE-DOCUMENT 8-K that carries its earnings release in the 8-K body
    with no exhibit at all, whose index legitimately has exactly 2 rows
    (body + complete-submission) and whose Filing Detail header declares
    "Documents: 1". Measured over all 10,233 cached E2 filing indices, the
    dropped-row condition this now checks fired ZERO times and the >=3
    condition fired 64 times -- i.e. the threshold caught no real broken
    parse and only ever mislabelled legitimately sparse filings, which then
    lost their 8K_BODY fallback and became holes in the corpus.
    """
    out: list[dict] = []
    dropped: list[str] = []
    for summary_raw, table_html in _TABLE_RE.findall(html_text):
        source_table = _clean_cell(summary_raw) or "unknown"
        for row_html in _ROW_RE.findall(table_html):
            tds = _TD_RE.findall(row_html)
            if len(tds) < 5:
                continue
            seq_cell, desc_cell, doc_cell, type_cell, _size_cell = tds[:5]
            href_match = _HREF_RE.search(doc_cell)
            if not href_match:
                dropped.append(
                    f"[{source_table}] seq={_clean_cell(seq_cell)!r} "
                    f"type={_clean_cell(type_cell)!r} "
                    f"description={_clean_cell(desc_cell)!r}"
                )
                continue
            href = href_match.group(1)
            # iXBRL-wrapped primary documents link through the inline
            # viewer, e.g. "/ix?doc=/Archives/edgar/data/.../foo.htm" --
            # unwrap to the actual archive path so relative_path points at
            # real fetchable content, not a viewer URL.
            if href.startswith("/ix?doc="):
                href = href[len("/ix?doc="):]
            filename = href.rsplit("/", 1)[-1]
            seq_text = _clean_cell(seq_cell)
            out.append(
                {
                    "seq": int(seq_text) if seq_text.isdigit() else None,
                    "description": _clean_cell(desc_cell),
                    "filename": filename,
                    "relative_path": href,
                    "doc_type": _clean_cell(type_cell),
                    "source_table": source_table,
                }
            )

    if dropped:
        raise ValueError(
            f"{len(dropped)} filing-index data row(s) carried no document "
            f"hyperlink and would have been silently dropped: {dropped}. "
            f"Treating as a parse failure rather than trusting an incomplete "
            f"parse (see parse_index_html_documents docstring)."
        )
    if not out:
        raise ValueError(
            "Parsed 0 document rows from filing index HTML -- no index table "
            "was recognised at all. Treating as a parse failure (see "
            "parse_index_html_documents docstring)."
        )
    if primary_document:
        parsed_filenames = {d["filename"] for d in out}
        if primary_document not in parsed_filenames:
            raise ValueError(
                f"primary_document {primary_document!r} not found among "
                f"parsed index rows {sorted(parsed_filenames)} -- treating "
                f"parse as failed rather than risk silently reporting "
                f"'no exhibit found'."
            )
    return out


# P1 (S6 manual read, F2_PROGRESS §5 ruling 2026-08-24): some filers type the
# exhibit as a bare `EX-99` and put the sub-number in the DESCRIPTION column
# instead ("EXHIBIT 99.1", "EX-99.1"). MEASURED over the corpus: this demotes
# 11 of the 32 low-confidence selections that are in fact correct picks
# (Sempra, Weyerhaeuser, Welltower, BlackRock, ...).
_DESC_EXHIBIT_NUMBER_RE = re.compile(r"\bEX(?:HIBIT)?[-\s.]*99[.\s-]*(\d+)\b", re.I)


def _exhibit_number_from_description(description: str) -> Optional[str]:
    """`"EXHIBIT 99.1"` / `"EX-99.1"` -> `"EX-99.1"`; anything else -> None.

    CONFIDENCE ONLY -- this never changes which document is picked. It reads
    the number a filer put one column over from where the policy looks, so a
    correct pick stops being labelled `low` for a cosmetic reason. The pick
    itself stays the lowest-seq rule, and `select_earnings_document()` only
    upgrades confidence when the description-identified EX-99.1 IS the
    document lowest-seq already chose. MEASURED: 11 upgrades, **0 pick
    changes**, over the real 32 low-confidence selections.
    """
    m = _DESC_EXHIBIT_NUMBER_RE.search(description or "")
    return f"EX-99.{m.group(1)}" if m else None


def _effective_exhibit_type(doc: dict) -> str:
    """The document's EX-99 sub-type: the canonical type column
    (`_canonical_exhibit_type`, which un-pads `EX-99.01`), falling back to the
    number in the DESCRIPTION when the type column is a bare `EX-99`."""
    canonical = _canonical_exhibit_type(doc.get("doc_type") or "")
    if canonical == "EX-99":
        return _exhibit_number_from_description(doc.get("description", "")) or canonical
    return canonical


# P2 (S6 manual read, F2_PROGRESS §5 ruling 2026-08-24) -- ONE named per-filer
# handler, deliberately not a general "prefer the exhibit that reads like a
# release" scorer, which would re-open all ~9,981 currently-correct picks.
PROLOGIS_CIK = 1045609
# From this filing date onward Prologis's EX-99.1 is the *Supplemental
# Information* tables package and the press release is EX-99.2.
#
# 2026-08-24: moved 2016-07-19 -> 2016-04-19 by the content re-verification
# (F2_PROGRESS §5; S6_ex99_manual_read.md §V.3). The 2016-04-19 filing keeps a
# TEMPLATE-LEFTOVER title -- "Prologis Earnings Release and Supplemental
# Information" -- over a body with no release in it at all. Re-verified here
# against raw bytes: across the whole 113,158-character document there is
# exactly ONE release-language hit, at character offset 64, inside that title;
# zero hits for "Prologis Reports", "today reported", "FOR IMMEDIATE RELEASE",
# "press release", "conference call" or "webcast", and its table of contents
# runs straight from "Highlights" to "Company Profile" with no release entry.
# Blast radius 41 -> 42 of 45.
PROLOGIS_SUPPLEMENTAL_SPLIT = date(2016, 4, 19)


def _prologis_earnings_document(docs: list[dict], filing_date: date) -> Optional[dict]:
    """Prologis (CIK 1045609): from 2016-07-19, take EX-99.2, not EX-99.1.

    CONTENT-CONFIRMED 2026-08-24 across all 45 of the filer's cached earnings
    8-Ks, offline (the rival EX-99.2 bytes are not cached and could not be
    read, so the confirmation is by complement + the filer's own label):

    - Through 2016-01-26 (**3** filings: 2015-07-21, 2015-10-20, 2016-01-26)
      the EX-99.1 is self-titled "Earnings Release **and** Supplemental
      Information" and genuinely contains the release -- "Prologis Reports
      ... Results", a "Press Release" entry in its own table of contents, and
      the dateline. Those 3 keep EX-99.1; this handler does not fire on them.
    - **The exception, and the reason the split date is 2016-04-19 and not
      2016-07-19:** `0001564590-16-016339` (2016-04-19) carries the SAME
      "Earnings Release and Supplemental Information" title but no release
      whatsoever -- a template leftover. Its one release-language hit in
      113,158 characters is that title (offset 64); its ToC has no release
      entry. So it is treated like the post-split filings and takes EX-99.2
      (`pld-ex992_7.htm`). An earlier pass of this docstring claimed all four
      pre-split filings "genuinely contain the release"; that was true of
      three and false of this one, and it generalised from the title string --
      precisely the signal this filing breaks.
    - From 2016-04-19 (**42** filings, continuously to 2026-07-16) the release
      is EX-99.2. From 2016-07-19 the title also drops "Earnings Release and"
      and reads "Prologis Supplemental Information <quarter> Unaudited". All
      42 EX-99.1 documents were read: zero contain release narrative.
    - Every one of those 41 filings carries an EX-99.2 row, and the filer
      names it itself in 0001564590-19-036903, where the EX-99.2 description
      is literally "PRESS RELEASE, DATED OCTOBER 15, 2019." while EX-99.1's is
      the generic "EX-99.1".

    Two of the 42 (2018-01-23, 2018-04-17) were reported as carrying release
    language by the S6 read's screen; re-read in context, both are Supplemental
    documents whose guidance footnote merely CITES "the Press Release dated
    January 17, 2018". They are handled like the rest, so the corrected blast
    radius went 39 -> 41 (those two) -> **42** (the 2016-04-19 boundary case
    above).

    EX-99.2 is located by _effective_exhibit_type(), because two of the 42
    (2018-07-17, 2023-04-18) type both exhibits as a bare `EX-99` and put the
    numbers in the description -- those are exactly the two the manual read
    caught, and a type-only lookup would miss them.
    """
    if filing_date < PROLOGIS_SUPPLEMENTAL_SPLIT:
        return None
    ex992 = [d for d in docs if _effective_exhibit_type(d) == "EX-99.2"]
    if len(ex992) != 1:
        return None
    return _resolved(ex992[0], "EX99_PRESS_RELEASE", "high")


# P-PSEG (S6 manual read §W ADDENDUM, ruled 2026-08-24) -- the Prologis shape
# one rung lower, and F2's largest single-filer content defect.
PSEG_CIK = 788784


def _pseg_earnings_document(docs: list[dict], filing_date: date) -> Optional[dict]:
    """PSEG (CIK 788784): take the bare `EX-99`, not the `EX-99.1`.

    THE DEFECT: all 45 of this filer's earnings selections were the earnings
    CALL DECK, at high confidence. Every one of the 45 filings has the identical
    two-candidate shape -- seq 2 bare `EX-99` (never selected, never cached) and
    seq 3 `EX-99.1` (the deck) -- and the ladder prefers a sub-numbered exhibit
    over a bare one while `_best_by_description()` cannot break the tie, because
    both descriptions are content-free: literally "EX-99" and "EX-99.1".

    EVIDENCE (all offline; verified here, not taken on trust):
    - the shape is `{('EX-99', 'EX-99.1'): 45}` -- uniform 2015-07-31 to
      2026-08-04, no exceptions;
    - all 45 filings are `items=2.02,7.01,9.01`, the standard utility pattern of
      release under 2.02 and call deck furnished under 7.01 -- the policy took
      the 7.01 artifact;
    - all 45 selected documents are provably decks: 43 open "PSEG Earnings
      Conference Call …" or "… Financial Results Presentation", and the other 2
      (2021-11-02, 2022-02-24) open "Financial Results and Conference Call" --
      each followed by forward-looking-statement boilerplate, with 37-46
      per-slide GRAPHIC rows in the index;
    - the deck-title screen below flags 45/45 of them and nothing else.

    Like the Prologis handler, the complement is what is proven: the bare
    `EX-99` bytes are NOT cached (never selected, and fetching is out of scope),
    so they are content-verified post-delta by the extraction-qa pass -- the
    same standard on which the Prologis finding was raised and later confirmed
    exactly.

    Deliberately NOT a blanket bare-before-sub-numbered preference: other filers
    may order the opposite way, and flipping the ladder globally would gamble
    ~10,500 correct picks to fix 45. Measure, don't gamble.
    """
    bare = [d for d in docs if _effective_exhibit_type(d) == "EX-99"]
    sub_numbered = [d for d in docs if _effective_exhibit_type(d) == "EX-99.1"]
    if len(bare) == 1 and len(sub_numbered) == 1:
        return _resolved(bare[0], "EX99_PRESS_RELEASE", "high")
    return None


# cik -> handler(docs, filing_date) -> selection | None. A dict, not a plugin
# framework: one entry, added because a systematic 41-filing error was measured
# on a real filer, and each entry carries its evidence in its docstring.
PER_FILER_EARNINGS_HANDLERS = {
    PROLOGIS_CIK: _prologis_earnings_document,
    PSEG_CIK: _pseg_earnings_document,
}


# ---------------------------------------------------------------------------
# Malformed-exhibit candidate screen (S7 red-team B1, ruled 2026-08-24)
# ---------------------------------------------------------------------------
# THE DEFECT THIS EXISTS FOR: the 8K_BODY fallback used to fire
# UNCONDITIONALLY whenever nothing matched `^EX-99(\.\d+)?$`, with no check
# that the index still held an unselected candidate. MEASURED: 20 of the 225
# 8K_BODY/high selections had one, and the stored "earnings document" was the
# SEC Form 8-K COVER PAGE -- whose own Item 2.02 text says, verbatim, "A copy
# of the press release is attached hereto as Exhibit 99.1" (read in the stored
# bytes for Aon, Illumina x2, Pioneer, HPE, Pioneer, TI, Arista). Every guard
# missed it: P5's floor is 1,500 chars and these are 2,260-4,231; P3 needs a
# release-shaped DESCRIPTION and these say "EXHIBIT 99..1"/"EXHIBIT 1"; P6 is a
# per-CIK majority; the confidence was `high` by construction; and the 1%
# unresolved ceiling counted a cover-page pick as RESOLVED, so it was blind.
#
# THIS IS NOT FAMILY-REGEX WIDENING, which stays prohibited. `_EX99_FAMILY_RE`
# and `_canonical_exhibit_type()` are untouched: a malformed type is still not
# a member of the EX-99 family and never wins the normal ladder. What changes
# is only the FALLBACK: before settling for the body, look at what is still
# unselected, and select a SPECIFIC candidate only on index/description
# evidence. Anything not confirmable is UNRESOLVED and loud -- never the body
# at high confidence.
#
# A row whose description self-labels as exhibit 99 in ANY malformation. The
# trailing junk ("(A)", ".Q120 EARNINGS", "..1") does not change that the filer
# is naming exhibit 99.
_DESC_EXHIBIT_99_RE = re.compile(r"\bEX(?:HIBIT)?[-\s.]*99\b", re.I)
# A BARE `EX-<n>` type with no sub-number. Real securities exhibits are
# EX-1.1 / EX-2.1 / EX-4.2 / EX-10.1; a bare EX-1 or EX-2 is itself a
# malformation, and MEASURED it is the Illumina / HPE / Kraft Heinz shape.
# This distinction is what keeps Dominion's EX-1.1 underwriting agreement,
# Emerson's EX-2.1 merger agreement, Danaher's EX-3.1 certificate and
# Marathon/MPLX's EX-10.1 leases OUT of the candidate set -- their 8K_BODY
# pick is correct and must stay untouched.
_BARE_EX_NUMBER_RE = re.compile(r"^EX-\d+$", re.I)
# Row types that are not candidate documents at all.
_NON_DOCUMENT_ROW_PREFIXES = ("GRAPHIC", "XML", "ZIP", "JSON", "EX-101", "EX-100", "EX-96")


def _is_document_row(doc: dict) -> bool:
    doc_type = (doc.get("doc_type") or "").upper().strip()
    if not doc_type:
        return False
    return not any(doc_type.startswith(p) for p in _NON_DOCUMENT_ROW_PREFIXES)


def earnings_candidate_rows(docs: list[dict], selected_filename: Optional[str]) -> list[dict]:
    """Unselected, non-body document rows that could plausibly be the earnings
    release. Narrow ON PURPOSE: an ordinary securities exhibit is not a
    candidate, so a genuine exhibit-less 8-K keeps its 8K_BODY fallback."""
    out = []
    for d in docs:
        if not _is_document_row(d):
            continue
        doc_type = (d.get("doc_type") or "").upper().strip()
        if doc_type.startswith("8-K"):
            continue
        if selected_filename and d["filename"] == selected_filename:
            continue
        description = d.get("description") or ""
        if (
            _DESC_EXHIBIT_99_RE.search(description)
            or _DESC_EXHIBIT_99_RE.search(doc_type)
            or _BARE_EX_NUMBER_RE.match(doc_type)
            or _PRESS_RELEASE_DESC_RE.search(description)
        ):
            out.append(d)
    return out


def confirmable_release_candidate(candidates: list[dict]) -> Optional[dict]:
    """The one candidate whose own DESCRIPTION confirms it is the release --
    either by self-labelling as exhibit 99, or by being release-shaped.

    Index/description evidence only, exactly the standard the NVIDIA / ONEOK /
    Micron override rows were written to. The document's TYPE is deliberately
    not evidence here (that would be family widening), and neither is its
    filename (E1 already found filename-pattern guessing unreliable -- see the
    module docstring).

    Returns None when nothing is confirmable OR when more than one row is:
    ambiguity is reported loudly as UNRESOLVED, never guessed.
    """
    confirmed = [
        d for d in candidates
        if _DESC_EXHIBIT_99_RE.search(d.get("description") or "")
        or _PRESS_RELEASE_DESC_RE.search(d.get("description") or "")
    ]
    return confirmed[0] if len(confirmed) == 1 else None


def _score_description(description: str) -> int:
    d = description.upper()
    score = 0
    if any(k in d for k in POSITIVE_DESC_KEYWORDS):
        score += 1
    if any(k in d for k in NEGATIVE_DESC_KEYWORDS):
        score -= 1
    return score


def _seq_sort_key(doc: dict):
    # None-seq rows sort last so a real sequence number always wins a
    # "lowest seq" tiebreak.
    return (doc["seq"] is None, doc["seq"] if doc["seq"] is not None else 0)


# -- named per-filer-dialect handlers (S6 segment-1 diagnosis, 2026-08-24) ---
# Each one is a small, named, measured rule for ONE observed filer dialect.
# None of them is a general-purpose regex over exhibit types: an exhibit type
# this file does not recognise stays unrecognised and falls through to the
# lowest-seq / low-confidence arm, which is what the §4.4 manual read is for.

_ZERO_PADDED_EX99_RE = re.compile(r"^EX-99\.0+(\d+)$")


def _canonical_exhibit_type(doc_type: str) -> str:
    """DIALECT: zero-padded exhibit sub-numbers (`EX-99.01`, `EX-99.02`).

    Six E2 members type their exhibits with a leading zero -- Intuit (53
    earnings 8-Ks), Gen Digital (43), Xcel Energy (43), Southern Co (40),
    Eversource (15), Sempra (4). `EX-99.01` IS exhibit 99.1; EDGAR's own
    numbering has no separate "exhibit 99.01". Before this handler those 198
    filings all fell through to the lowest-seq arm at LOW confidence -- the
    pick was right every time (verified by offline replay: not one filename
    changes), only the confidence label was wrong, which put four of the six
    filers at the top of the §4.4 manual-read worklist for nothing. That is
    exactly the crying-wolf failure HANDOFF §4 warns about.

    Only a LEADING zero is stripped, so `EX-99.10` stays `EX-99.10` and is
    never conflated with `EX-99.1`. Anything that is not an `EX-99.<digits>`
    type (e.g. J&J's `EX-99.2O`, letter O) is returned unchanged and stays
    unrecognised.
    """
    canonical = doc_type.strip().upper()
    match = _ZERO_PADDED_EX99_RE.match(canonical)
    return f"EX-99.{match.group(1)}" if match else canonical


def _drop_pdf_renditions(rows: list[dict]) -> list[dict]:
    """DIALECT: one exhibit filed twice, as HTML and as a scanned PDF.

    Ford files each earnings release as two rows both typed `EX-99.1`
    (`exhibit991to<month>earn.htm` + `...earnings.pdf`), 11 filings. Same
    exhibit, two renditions -- not two exhibits. `extract.py` has no PDF
    reader, so the HTML rendition is also the only usable one.

    Returns the non-PDF rows when dropping PDFs leaves at least one
    candidate, else the input unchanged (never turns a set of candidates
    into an empty one).
    """
    kept = [d for d in rows if not d["filename"].lower().endswith(".pdf")]
    return kept if kept else rows


def _best_by_description(rows: list[dict]) -> dict | None:
    """The description-keyword score already used for the EX-99.2/.3 arm,
    factored out so the duplicate-exhibit arms can use it too.

    Returns the unique positively-scoring row, or None if there is a tie or
    nothing scores positively. Eversource types three different exhibits as
    a bare `EX-99` in one filing ('NEWS RELEASE' / "BROKER'S STATEMENTS" /
    'SLIDE PRESENTATION', 15 filings) -- the scorer names the release
    outright, where lowest-seq only happened to agree with it.
    """
    scored = [(_score_description(d["description"]), d) for d in rows]
    best = max(s for s, _ in scored)
    winners = [d for s, d in scored if s == best]
    return winners[0] if best > 0 and len(winners) == 1 else None


def _resolved(doc: dict, section_type: str, confidence: str) -> dict:
    return {
        "filename": doc["filename"],
        "relative_path": doc["relative_path"],
        "seq": doc["seq"],
        "section_type": section_type,
        "selection_confidence": confidence,
        "is_exhibit": section_type == "EX99_PRESS_RELEASE",
    }


def select_earnings_document(
    docs: list[dict],
    primary_document: str | None,
    subject: str = "",
    accession_number: str = "",
    cik: Optional[int] = None,
    filing_date: Optional[str] = None,
) -> dict | None:
    """Selection policy over a filing's parsed document rows. First matching
    rule wins:

      0. A named PER-FILER handler for this `cik` (PER_FILER_EARNINGS_HANDLERS)
         claims the filing -- today only Prologis, whose EX-99.1 is the
         Supplemental tables package from 2016-07-19 onward. Needs both `cik`
         and `filing_date`; without them the generic rules run, so a caller
         that forgets them degrades to E1 behaviour rather than crashing.

      1. Exactly one EX-99.1 -> take it (high confidence).
      2. >1 EX-99.1 -> if they are one exhibit in two renditions (HTML +
         scanned PDF, `_drop_pdf_renditions`) take the readable one at high
         confidence; else prefer a unique description-keyword winner at
         medium; else take lowest seq at low confidence and log a canary.
      3. No EX-99.1, exactly one bare EX-99 -> take it (high confidence).
         >1 bare EX-99 -> same duplicate-resolution ladder as rule 2.
      4. No EX-99.1/EX-99, but EX-99.2/.3/etc. present -> score by
         description keywords (PRESS RELEASE/NEWS RELEASE/EARNINGS RELEASE
         beat PRESENTATION/SUPPLEMENTAL/COMMENTARY/DATA SUMMARY); a unique
         positive-scoring winner is taken at medium confidence, otherwise
         (tie, or nothing scores positively) take lowest seq at low
         confidence.
      5. No EX-99.x at all -> look at what the index still holds
         (`earnings_candidate_rows`). If a candidate's DESCRIPTION confirms it
         is the release, take it at MEDIUM confidence. If candidates exist but
         none is confirmable, return None = UNRESOLVED, counted against the 1%
         ceiling -- never the body at high confidence (S7 B1).
      6. No candidates either (a genuine exhibit-less 8-K) -> fall back to
         `primary_document` (from submissions.json, always populated),
         section_type='8K_BODY'. Unchanged. Never
         resolved by scanning the index for a row typed "8-K" -- some
         filers (MCD confirmed) carry two such rows (the real iXBRL primary
         document AND a scanned PDF copy), which would be a nondeterministic
         pick.

    Exhibit types are compared through `_canonical_exhibit_type()`, so the
    zero-padded `EX-99.01` dialect is read as the `EX-99.1` it is.

    `subject` is a display label for the CANARY lines only (E2 passes
    "CIK 18230"; it was called `ticker` in E1, when a ticker was still a key
    -- it is not one in E2 and the name was a trap).

    Returns None only if there are no EX-99.x candidates AND no
    primary_document was supplied (shouldn't happen in practice --
    primary_document comes straight from submissions.json). A None return is
    an UNRESOLVED case and is counted as one by the §4.4 audit, never
    silently skipped.
    """

    handler = PER_FILER_EARNINGS_HANDLERS.get(int(cik)) if cik is not None else None
    if handler is not None and filing_date:
        per_filer = handler(docs, date.fromisoformat(filing_date))
        if per_filer is not None:
            return per_filer

    def by_type(*type_names: str) -> list[dict]:
        wanted = {t.upper() for t in type_names}
        return [d for d in docs if _canonical_exhibit_type(d["doc_type"]) in wanted]

    def resolve_duplicates(rows: list[dict], label: str) -> dict:
        """The shared ladder rules 2 and 3 use once a filing carries more
        than one row of the SAME exhibit type. Loud at the bottom rung only:
        a canary is a claim that the pick was arbitrary, so it is printed
        when -- and only when -- the pick really was lowest-seq."""
        readable = _drop_pdf_renditions(rows)
        if len(readable) == 1:
            return _resolved(readable[0], "EX99_PRESS_RELEASE", "high")
        by_description = _best_by_description(readable)
        if by_description is not None:
            return _resolved(by_description, "EX99_PRESS_RELEASE", "medium")
        chosen = min(readable, key=_seq_sort_key)
        # P1 -- CONFIDENCE ONLY. When the filer typed bare `EX-99` rows and
        # put the sub-numbers in the description, and the row described
        # "EX-99.1" is the one lowest-seq ALREADY chose, the pick was never
        # arbitrary: relabel it high and do not cry wolf. The `is the same
        # file` guard is what makes this provably zero-pick-change (MEASURED:
        # 11 upgrades, 0 pick changes over the real 32 low-confidence rows).
        if label == "bare EX-99":
            described_991 = [
                d for d in readable
                if _exhibit_number_from_description(d["description"]) == "EX-99.1"
            ]
            if len(described_991) == 1 and described_991[0]["filename"] == chosen["filename"]:
                return _resolved(chosen, "EX99_PRESS_RELEASE", "high")
        print(
            f"  CANARY: {subject} {accession_number} has {len(rows)} {label} "
            f"rows ({[d['filename'] for d in rows]}) -- they are neither one "
            f"exhibit in two renditions nor separable by description, so "
            f"taking lowest seq {chosen['filename']!r}, "
            f"selection_confidence=low. This did not occur across E1's 331 "
            f"earnings 8-Ks -- treat as a canary, not expected behavior. "
            f"(E2's window has 10,569 earnings 8-Ks across 244 members, 219 "
            f"of them filers this policy has never seen, so S3's EX-99 audit "
            f"counts these rather than only printing them -- F2_SPEC §4.4.)"
        )
        return _resolved(chosen, "EX99_PRESS_RELEASE", "low")

    exact_991 = by_type("EX-99.1")
    if len(exact_991) == 1:
        return _resolved(exact_991[0], "EX99_PRESS_RELEASE", "high")
    if len(exact_991) > 1:
        return resolve_duplicates(exact_991, "EX-99.1")

    bare_99 = by_type("EX-99")
    if len(bare_99) == 1:
        return _resolved(bare_99[0], "EX99_PRESS_RELEASE", "high")
    if len(bare_99) > 1:
        return resolve_duplicates(bare_99, "bare EX-99")

    other_99x = [
        d for d in docs
        if re.match(r"^EX-99\.\d+$", _canonical_exhibit_type(d["doc_type"]))
    ]
    if other_99x:
        by_description = _best_by_description(other_99x)
        if by_description is not None:
            return _resolved(by_description, "EX99_PRESS_RELEASE", "medium")
        chosen = min(other_99x, key=_seq_sort_key)
        return _resolved(chosen, "EX99_PRESS_RELEASE", "low")

    # -- CONDITIONAL 8K_BODY fallback (S7 B1, ruled 2026-08-24) -------------
    # Before settling for the body, check what the index still holds. The old
    # code returned ("8K_BODY", "high") here unconditionally, which is how 14
    # SEC cover pages became "earnings documents" at high confidence.
    candidates = earnings_candidate_rows(docs, primary_document)
    if candidates:
        chosen = confirmable_release_candidate(candidates)
        if chosen is not None:
            # Description evidence, not a canonical type -> medium, never high.
            return _resolved(chosen, "EX99_PRESS_RELEASE", "medium")
        print(
            f"  UNRESOLVED: {subject} {accession_number} has no EX-99-family "
            f"exhibit, but {len(candidates)} unselected candidate row(s) whose "
            f"description does not confirm which is the release: "
            f"{[(d['doc_type'], d['description'], d['filename']) for d in candidates]}. "
            f"Refusing to fall back to the 8-K body at high confidence -- the "
            f"body is usually the cover page, whose own Item 2.02 says the "
            f"release is attached elsewhere. Counted as earnings_doc_unresolved "
            f"against the 1% ceiling; resolve it with an evidenced row in "
            f"{EARNINGS_DOC_OVERRIDES_PATH.name}."
        )
        return None

    if primary_document:
        primary_rows = [d for d in docs if d["filename"] == primary_document]
        if primary_rows:
            return _resolved(primary_rows[0], "8K_BODY", "high")
        # parse_index_html_documents() already asserts primary_document is
        # present when it's passed in, so this branch shouldn't be
        # reachable in practice -- but return a synthetic row rather than
        # None so a caller can't mistake "not reachable" for "no exhibit".
        return {
            "filename": primary_document,
            "relative_path": None,
            "seq": None,
            "section_type": "8K_BODY",
            "selection_confidence": "high",
            "is_exhibit": False,
        }

    return None


def resolve_earnings_document(
    client: EdgarClient, cik: int, accession_number: str, primary_document: str | None,
    subject: str = "", filing_date: Optional[str] = None,
) -> tuple[list[dict], dict | None]:
    """Fetch (cached) the filing index HTML, parse it into document rows,
    and run the selection policy. Returns (parsed_document_rows, selection).

    Raises on a fetch or parse failure. The caller counts that failure into
    the §4.4 `earnings_doc_unresolved` accounting rather than only printing
    it -- an unresolved earnings document is a hole in the corpus, not a log
    line.
    """
    html_text = client.get_filing_index_html(cik, accession_number)
    docs = parse_index_html_documents(html_text, primary_document=primary_document)
    selection = select_earnings_document(
        docs, primary_document, subject=subject, accession_number=accession_number,
        cik=cik, filing_date=filing_date,
    )
    return docs, selection


def write_filing_documents(conn: sqlite3.Connection, accession_number: str, docs: list[dict]) -> None:
    # Idempotent on rerun: the index HTML is immutable once cached, so a
    # full delete+reinsert per accession is cheap and avoids needing a
    # synthetic primary key / dedup logic.
    conn.execute("DELETE FROM filing_documents WHERE accession_number = ?", (accession_number,))
    conn.executemany(
        """
        INSERT INTO filing_documents
            (accession_number, seq, doc_type, description, filename, relative_path, source_table)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (accession_number, d["seq"], d["doc_type"], d["description"], d["filename"],
             d["relative_path"], d["source_table"])
            for d in docs
        ],
    )


# ---------------------------------------------------------------------------
# validate_universe() -- Phase A2
# ---------------------------------------------------------------------------


SEVERITIES = ("FATAL", "WARN", "INFO")


class ValidationProblem:
    """One finding about one member (or, with cik=RUN_SCOPE_CIK, about the
    run as a whole).

    E2 keys findings on `cik`; `ticker` is an optional display label kept so
    the fundamentals-side pass (which is still ticker-labelled until S4) can
    reuse the same object. `stage` separates the metadata and documents
    segments so their rows can't stomp each other in the DB.

    INFO is a real severity, not a softer WARN: `member_stopped_filing` is an
    expected state for a delisted member and must still be counted and named
    (EXPANSION_PLAN §2c), never silently dropped.
    """

    __slots__ = ("cik", "check", "severity", "message", "ticker", "stage")

    def __init__(
        self, cik: int, check: str, severity: str, message: str,
        ticker: Optional[str] = None, stage: str = "metadata",
    ):
        assert severity in SEVERITIES, f"unknown severity {severity!r}"
        self.cik = int(cik)
        self.check = check
        self.severity = severity
        self.message = message
        self.ticker = ticker
        self.stage = stage

    @property
    def subject(self) -> str:
        if self.cik == RUN_SCOPE_CIK:
            return "*"
        return f"{self.cik}" + (f"/{self.ticker}" if self.ticker else "")

    def __repr__(self) -> str:
        return f"{self.subject} | {self.severity} | {self.check} | {self.message}"


# ---------------------------------------------------------------------------
# Evidenced per-(cik, check) validation exceptions (F2_SPEC §3.2)
# ---------------------------------------------------------------------------
# E1 had `--allow-incomplete-universe=check1,check2`, which downgraded a check
# for the WHOLE run. At 25 companies that was already a compromise; at 244 it
# is exactly the bug it was built to avoid, one level up -- accepting one
# known-OK finding for one delisted member would disarm that check for the
# other 243. The flag is DELETED, not parameterised.
#
# Its replacement is an evidenced file modelled column-for-column on F1's
# manual_exclusions.csv, so there is one pattern to learn:
#   1. an exception downgrades FATAL -> WARN for exactly one (cik, check)
#      pair; it can never widen;
#   2. a dated exception (effective_from set) is REJECTED at load time unless
#      evidence_filed < effective_from -- the same point-in-time guard F1 put
#      on dated exclusions, so nobody can quietly encode hindsight;
#   3. every exception is printed in the run report whether it fired or not;
#      one that never fires is reported as DEAD -- a bug in the file, not a
#      harmless leftover;
#   4. there is no blanket switch and no CLI escape hatch. A new FATAL means
#      either the data is wrong or the check is wrong; both get fixed.
VALIDATION_EXCEPTION_COLUMNS = (
    "cik", "check_name", "reason", "effective_from", "effective_to",
    "evidence_filed", "evidence", "added",
)

# The code-side ratification gate its two sibling override files already had
# (S7 red-team B17: the asymmetry was the finding). A row here downgrades a
# FATAL, so -- exactly like RATIFIED_OVERRIDE_CIKS in ingest_prices.py and
# RATIFIED_EARNINGS_DOC_OVERRIDES above -- it takes a deliberate edit to this
# set AND an evidenced CSV row. A row alone is refused at load.
# EMPTY BY DESIGN: MEASURED, all 244 members pass every FATAL check, so the
# file ships with a header and no rows and this set has nothing to hold.
RATIFIED_VALIDATION_EXCEPTIONS: set[tuple[int, str]] = set()


@dataclass(frozen=True)
class ValidationException:
    cik: int
    check_name: str
    reason: str
    evidence: str
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    evidence_filed: Optional[date] = None
    added: str = ""

    @property
    def key(self) -> tuple[int, str]:
        return (self.cik, self.check_name)

    def applies(self, cik: int, check_name: str, as_of: date) -> bool:
        if (cik, check_name) != self.key:
            return False
        if self.effective_from is not None and as_of < self.effective_from:
            return False
        if self.effective_to is not None and as_of > self.effective_to:
            return False
        return True

    def window_str(self) -> str:
        lo = self.effective_from.isoformat() if self.effective_from else "…"
        hi = self.effective_to.isoformat() if self.effective_to else "…"
        return "all corpus vintages" if lo == "…" and hi == "…" else f"{lo} → {hi}"


def _opt_date(v) -> Optional[date]:
    s = str(v or "").strip()
    if not s or s.lower() in ("nan", "none"):
        return None
    return date.fromisoformat(s)


def load_validation_exceptions(
    path: Path = VALIDATION_EXCEPTIONS_PATH,
) -> list[ValidationException]:
    """Read data/f2/validation_exceptions.csv. A missing file, or one with
    only a header, is a legitimate state (no exceptions) and returns []. A
    malformed row RAISES -- a silently-ignored exception row is exactly the
    failure this mechanism exists to prevent.
    """
    if not path.exists():
        return []
    df = pd.read_csv(path, dtype=str, keep_default_na=False, comment="#")
    missing = [c for c in VALIDATION_EXCEPTION_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing required column(s) {missing}")
    out: list[ValidationException] = []
    for i, r in enumerate(df.to_dict("records"), start=2):  # +1 header, +1 1-based
        cik_raw = str(r["cik"]).strip()
        if not cik_raw:
            continue
        try:
            cik = int(cik_raw)
        except ValueError as exc:
            raise ValueError(f"{path} line {i}: cik {cik_raw!r} is not an integer") from exc
        check_name = str(r["check_name"]).strip()
        if check_name not in FATAL_CHECK_NAMES:
            raise ValueError(
                f"{path} line {i} (cik {cik}): unknown check {check_name!r}. An "
                f"exception may only downgrade a check that can actually be FATAL: "
                f"{sorted(FATAL_CHECK_NAMES)}."
            )
        if (cik, check_name) not in RATIFIED_VALIDATION_EXCEPTIONS:
            raise ValueError(
                f"{path} line {i}: (cik {cik}, {check_name!r}) is not a ratified "
                f"exception. Ratified: {sorted(RATIFIED_VALIDATION_EXCEPTIONS)}. An "
                f"exception downgrades a FATAL -- adding one takes a deliberate "
                f"edit to RATIFIED_VALIDATION_EXCEPTIONS in ingest_metadata.py "
                f"alongside the evidenced row, not a new line in this CSV. "
                f"(S7 red-team B17: this gate was missing while both sibling "
                f"override files had it.)"
            )
        if not str(r["reason"]).strip() or not str(r["evidence"]).strip():
            raise ValueError(
                f"{path} line {i} (cik {cik}): both `reason` and `evidence` are "
                f"mandatory -- an exception without written evidence is not "
                f"auditable and is refused."
            )
        ex = ValidationException(
            cik=cik,
            check_name=check_name,
            reason=str(r["reason"]).strip(),
            evidence=str(r["evidence"]).strip(),
            effective_from=_opt_date(r["effective_from"]),
            effective_to=_opt_date(r["effective_to"]),
            evidence_filed=_opt_date(r["evidence_filed"]),
            added=str(r["added"]).strip(),
        )
        if ex.effective_from is not None and (
            ex.evidence_filed is None or ex.evidence_filed >= ex.effective_from
        ):
            raise ValueError(
                f"{path} line {i} (cik {cik}): POINT-IN-TIME VIOLATION -- a dated "
                f"exception (effective_from {ex.effective_from}) requires "
                f"`evidence_filed` strictly earlier than it; got "
                f"{ex.evidence_filed}. A dated exception may only rest on evidence "
                f"that was already public at the first corpus vintage it bites."
            )
        out.append(ex)
    seen: set[tuple[int, str]] = set()
    for ex in out:
        if ex.key in seen:
            raise ValueError(
                f"{path}: duplicate exception for (cik {ex.cik}, {ex.check_name}) -- "
                f"one row per (cik, check) pair, so the file reads as the exhaustive "
                f"list it claims to be."
            )
        seen.add(ex.key)
    return out


def apply_validation_exceptions(
    problems: list[ValidationProblem],
    exceptions: list[ValidationException],
    as_of: date = CORPUS_WINDOW_END,
) -> tuple[list[ValidationProblem], set[tuple[int, str]]]:
    """Downgrade FATAL -> WARN for exactly the (cik, check) pairs an in-force
    exception names, and return the set of exception keys that actually bit.

    `as_of` is the corpus vintage (CORPUS_WINDOW_END), not today's date, so
    an exception's date scoping is as reproducible as the corpus it applies
    to. Nothing here can widen a severity, and a non-FATAL problem is never
    touched.
    """
    fired: set[tuple[int, str]] = set()
    out: list[ValidationProblem] = []
    for p in problems:
        hit = next(
            (ex for ex in exceptions if p.severity == "FATAL"
             and ex.applies(p.cik, p.check, as_of)),
            None,
        )
        if hit is None:
            out.append(p)
            continue
        fired.add(hit.key)
        out.append(
            ValidationProblem(
                p.cik, p.check, "WARN",
                f"[DOWNGRADED from FATAL by validation_exceptions.csv "
                f"({hit.reason}; evidence: {hit.evidence})] {p.message}",
                ticker=p.ticker, stage=p.stage,
            )
        )
    return out, fired


def print_exception_report(
    exceptions: list[ValidationException],
    fired: set[tuple[int, str]],
    path: Path = VALIDATION_EXCEPTIONS_PATH,
) -> None:
    """Print every exception, fired or not. A dead exception is a bug in the
    file (the finding it was written for no longer exists), so it is called
    out rather than left to rot."""
    if not exceptions:
        print(
            f"\nvalidation exceptions ({path}): none. Every FATAL hard-fails the "
            f"run; there is no blanket override."
        )
        return
    dead = [ex for ex in exceptions if ex.key not in fired]
    print(f"\nvalidation exceptions ({path}): {len(exceptions)} row(s), "
          f"{len(fired)} fired, {len(dead)} DEAD:")
    for ex in exceptions:
        state = "FIRED" if ex.key in fired else "DEAD (never fired -- fix the file)"
        print(f"  {state}: cik {ex.cik} / {ex.check_name} [{ex.window_str()}] "
              f"-- {ex.reason} | evidence: {ex.evidence}")


# ---------------------------------------------------------------------------
# validate_universe() -- per-company windows (F2_SPEC §3.1)
# ---------------------------------------------------------------------------


def _periodic_dates(filings: list[dict]) -> list[date]:
    return sorted(
        date.fromisoformat(f["filing_date"])
        for f in filings
        if f["form"] in PERIODIC_FORMS
    )


def validate_universe(
    client: EdgarClient, universe: pd.DataFrame, force_refresh: bool = False,
    max_age_hours: Optional[float] = DEFAULT_MAX_AGE_HOURS,
) -> list[ValidationProblem]:
    """Run every completeness/sanity check against cached (or
    freshly-fetched-and-then-cached) submissions data, BEFORE the ingestion
    loop writes anything to the DB. See the module docstring and
    INGESTION_NOTES.md for why this exists.

    E2 change: each check runs over the company's OWN
    `[coverage_start, coverage_end]` window, and staleness is measured
    against the fixed CORPUS_WINDOW_END rather than date.today(), so a re-run
    on a different day produces identical findings. A late entrant and a
    delisted exit are expected states, not failures.

    Every problem across all companies is collected and returned -- callers
    decide whether to hard-fail, print, and/or persist them.

    `max_age_hours` is the submissions-cache TTL for this pass (F2_SPEC §4.3),
    default 24 h. Note this pass and the ingestion loop each call
    get_effective_recent() once per company. MEASURED 2026-08-24 over the real
    244 members: the whole doubled parse is 244 submissions documents (0.05 GB,
    0.2 s) plus 1,042 pagination chunks (0.25 GB, 0.9 s) -- ~1 s against a
    30-50 min segment, i.e. NOT material, so F2_SPEC §3.3's optional
    thread-the-dict-through change is deliberately not made. Both calls are
    cache reads: 0 extra network requests either way.
    """
    problems: list[ValidationProblem] = []

    # Bulk ticker->CIK map, fetched/cached once for the whole pass. In E2 it
    # is a CONTRADICTION DETECTOR only, never a requirement: AEP (CIK 4904)
    # and EA (CIK 712515) are simply absent from it, and requiring presence
    # would censor two live large caps for an SEC file's gap.
    try:
        company_tickers = client.get_company_tickers(force=force_refresh)
        ticker_to_cik = {
            entry["ticker"].upper(): entry["cik_str"] if "cik_str" in entry else entry.get("cik")
            for entry in company_tickers.values()
        }
    except Exception as e:  # noqa: BLE001
        ticker_to_cik = {}
        problems.append(
            ValidationProblem(
                RUN_SCOPE_CIK, "cik_map_fetch", "WARN",
                f"Could not fetch/parse company_tickers.json for the CIK-agreement "
                f"check: {e}. CIK map agreement check skipped for all companies.",
            )
        )

    for _, row in universe.iterrows():
        cik = int(row["cik"])
        name = row["name"]
        coverage_start: date = row["coverage_start"]
        coverage_end: date = row["coverage_end"]
        is_current = bool(row["is_current_member"])
        who = f"CIK {cik} ({name})"

        # -- Entity resolves (FATAL) --------------------------------------
        try:
            submissions = client.get_submissions(
                cik, force=force_refresh, max_age_hours=max_age_hours
            )
        except Exception as e:  # noqa: BLE001
            problems.append(
                ValidationProblem(
                    cik, "entity_resolves", "FATAL",
                    f"{who}: submissions.json fetch failed: {e}",
                )
            )
            continue  # nothing else can be checked without submissions data

        if "filings" not in submissions or "recent" not in submissions.get("filings", {}):
            problems.append(
                ValidationProblem(
                    cik, "entity_resolves", "FATAL",
                    f"{who}: submissions.json has no filings.recent key -- "
                    f"malformed or unexpected response shape.",
                )
            )
            continue

        # -- History reaches the company's own coverage_start (FATAL) -----
        # get_effective_recent transparently pulls filings.files[] chunks if
        # filings.recent alone doesn't reach back far enough. If it STILL
        # doesn't after that, the fetch was truncated (the JPM/BAC/GS bug).
        # MEASURED: 0 of 244 members fire this -- which is what a regression
        # guard should do.
        try:
            effective_recent = client.get_effective_recent(
                cik, coverage_start, force=force_refresh, max_age_hours=max_age_hours,
            )
        except Exception as e:  # noqa: BLE001
            problems.append(
                ValidationProblem(
                    cik, "history_reaches_cutoff", "FATAL",
                    f"{who}: failed fetching filings.files[] pagination chunks: {e}",
                )
            )
            continue

        recent = submissions["filings"]["recent"]
        dates = effective_recent.get("filingDate", [])
        if not dates:
            problems.append(
                ValidationProblem(
                    cik, "history_reaches_cutoff", "FATAL",
                    f"{who} has zero filings in filings.recent at all.",
                )
            )
            continue
        min_date = min(date.fromisoformat(d) for d in dates)
        if min_date > coverage_start:
            problems.append(
                ValidationProblem(
                    cik, "history_reaches_cutoff", "FATAL",
                    f"{who}: earliest filing found ({min_date.isoformat()}) does not "
                    f"reach this member's own coverage_start "
                    f"({coverage_start.isoformat()}), even after checking "
                    f"filings.files[] pagination chunks "
                    f"({len(submissions['filings'].get('files', []))} chunk(s) available).",
                )
            )

        target_filings = extract_target_filings(
            effective_recent, coverage_start, coverage_end
        )
        in_window_periodic = _periodic_dates(target_filings)

        # -- Plausible filing rate (FATAL / WARN) -------------------------
        # Rate, not an absolute floor: coverage windows differ in length by
        # a factor of ~4 across the membership table. The denominator ends at
        # the last in-window periodic filing, not at coverage_end -- see
        # MIN_PERIODIC_FILINGS_PER_YEAR_FATAL's comment for why charging a
        # delisted member's empty tail against its rate would be wrong.
        if not in_window_periodic:
            problems.append(
                ValidationProblem(
                    cik, "plausible_filing_counts", "FATAL",
                    f"{who}: zero 10-K/10-Q filings in its coverage window "
                    f"{coverage_start.isoformat()}..{coverage_end.isoformat()} -- a "
                    f"member that never filed a periodic report in its own window "
                    f"cannot be a large-cap registrant; treat as a fetch or "
                    f"membership error.",
                )
            )
        else:
            filed_span_days = (in_window_periodic[-1] - coverage_start).days
            filed_years = filed_span_days / 365.25
            if filed_years <= 0:
                rate = float(len(in_window_periodic))
            else:
                rate = len(in_window_periodic) / filed_years
            if rate < MIN_PERIODIC_FILINGS_PER_YEAR_FATAL:
                severity, floor = "FATAL", MIN_PERIODIC_FILINGS_PER_YEAR_FATAL
            elif rate < MIN_PERIODIC_FILINGS_PER_YEAR_WARN:
                severity, floor = "WARN", MIN_PERIODIC_FILINGS_PER_YEAR_WARN
            else:
                severity, floor = None, None
            if severity:
                problems.append(
                    ValidationProblem(
                        cik, "plausible_filing_counts", severity,
                        f"{who}: {len(in_window_periodic)} periodic filings over "
                        f"{filed_years:.2f} filed year(s) in "
                        f"{coverage_start.isoformat()}..{coverage_end.isoformat()} = "
                        f"{rate:.2f}/yr, below the {floor}/yr {severity} threshold "
                        f"(measured range across the 244 members: 4.01-4.53/yr).",
                    )
                )

        # -- No large filing gap (WARN > 135 d, FATAL > 300 d) ------------
        # Gaps are measured only INSIDE the coverage window. A gap spanning
        # the window edge is not a data gap, it is the edge.
        for i in range(1, len(in_window_periodic)):
            gap = (in_window_periodic[i] - in_window_periodic[i - 1]).days
            if gap > FATAL_FILING_GAP_DAYS:
                severity, note = "FATAL", (
                    ">=3 missed quarters -- the signature of a truncated "
                    "filings.files[] fetch"
                )
            elif gap > MAX_FILING_GAP_DAYS:
                severity, note = "WARN", (
                    f"fiscal-calendar quirks reach 266 days in this universe; "
                    f"FATAL starts at {FATAL_FILING_GAP_DAYS} days"
                )
            else:
                continue
            problems.append(
                ValidationProblem(
                    cik, "no_large_filing_gap", severity,
                    f"{who}: {gap}-day gap between 10-K/10-Q filings "
                    f"{in_window_periodic[i - 1].isoformat()} -> "
                    f"{in_window_periodic[i].isoformat()}, inside its coverage "
                    f"window ({note}).",
                )
            )

        # -- Recent activity, any form (WARN, current members only) -------
        # Measured against the FIXED corpus end date, not today.
        any_form_dates = recent.get("filingDate", [])
        if is_current and any_form_dates:
            most_recent_any = max(date.fromisoformat(d) for d in any_form_dates)
            staleness_any = (CORPUS_WINDOW_END - most_recent_any).days
            if staleness_any > MAX_STALE_ANY_FILING_DAYS:
                problems.append(
                    ValidationProblem(
                        cik, "recent_activity_any_form", RECENT_ACTIVITY_ANY_FORM_SEVERITY,
                        f"{who}: most recent filing of any form is "
                        f"{most_recent_any.isoformat()} ({staleness_any} days before "
                        f"the {CORPUS_WINDOW_END.isoformat()} corpus freeze, threshold "
                        f"{MAX_STALE_ANY_FILING_DAYS}) -- most likely an ordinary quiet "
                        f"filing period (WARN, not FATAL: this arm isn't the one that "
                        f"reliably detects a stopped filer).",
                    )
                )

        # -- Recent 10-K/10-Q: FATAL for a current member, INFO otherwise --
        # A former member that stopped filing is the expected delisting exit
        # (EXPANSION_PLAN §2c). It is still COUNTED and NAMED at INFO so the
        # censored set stays visible -- never silently dropped.
        all_periodic = _periodic_dates(
            extract_target_filings(effective_recent, date(1900, 1, 1), CORPUS_WINDOW_END)
        )
        if all_periodic:
            most_recent_periodic = all_periodic[-1]
            staleness = (CORPUS_WINDOW_END - most_recent_periodic).days
            if staleness > MAX_STALE_10K_10Q_DAYS:
                if is_current:
                    problems.append(
                        ValidationProblem(
                            cik, "recent_activity_10k_10q", RECENT_ACTIVITY_10K10Q_SEVERITY,
                            f"{who} is a CURRENT member but its most recent 10-K/10-Q is "
                            f"{most_recent_periodic.isoformat()} ({staleness} days before "
                            f"the {CORPUS_WINDOW_END.isoformat()} corpus freeze, threshold "
                            f"{MAX_STALE_10K_10Q_DAYS}) -- a member of the last "
                            f"reconstitution date should still be filing; stays FATAL.",
                        )
                    )
                else:
                    problems.append(
                        ValidationProblem(
                            cik, "member_stopped_filing", "INFO",
                            f"{who} left the universe (coverage_end "
                            f"{coverage_end.isoformat()}) and its most recent 10-K/10-Q is "
                            f"{most_recent_periodic.isoformat()} ({staleness} days before "
                            f"the corpus freeze) -- expected delisting/acquisition exit, "
                            f"counted and named, not a failure.",
                        )
                    )

        # -- CIK map agreement (WARN) -------------------------------------
        # E2 has no authoritative universe ticker to compare, so this checks
        # the other direction: does the bulk map CONTRADICT EDGAR's own
        # submissions tickers for this CIK? MEASURED: 0 contradictions across
        # all 244 members.
        if ticker_to_cik:
            for t in submissions.get("tickers", []):
                mapped_cik = ticker_to_cik.get(str(t).upper())
                if mapped_cik is not None and int(mapped_cik) != cik:
                    problems.append(
                        ValidationProblem(
                            cik, "cik_map_agreement", "WARN",
                            f"{who}: EDGAR's own submissions list ticker {t!r} for this "
                            f"CIK, but company_tickers.json maps {t!r} -> CIK "
                            f"{mapped_cik}. Both reported, neither silently preferred -- "
                            f"this is the reassigned-former-symbol trap (APC->ARKO), so "
                            f"a contradiction censors rather than guesses downstream.",
                            ticker=str(t),
                        )
                    )

    return problems


def print_validation_report(problems: list[ValidationProblem]) -> None:
    if not problems:
        print("\nvalidate_universe(): no problems found across all companies.")
        return
    counts = {s: sum(1 for p in problems if p.severity == s) for s in SEVERITIES}
    print(
        f"\nvalidate_universe(): {len(problems)} problem(s) found "
        f"({counts['FATAL']} FATAL / {counts['WARN']} WARN / {counts['INFO']} INFO):"
    )
    print(f"{'subject':<18} {'severity':<8} {'check':<28} message")
    print("-" * 110)
    order = {s: i for i, s in enumerate(SEVERITIES)}
    for p in sorted(problems, key=lambda p: (order[p.severity], p.cik, p.check)):
        print(f"{p.subject:<18} {p.severity:<8} {p.check:<28} {p.message}")


def write_validation_problems(
    conn: sqlite3.Connection, problems: list[ValidationProblem], run_date: date,
    stage: str = "metadata",
) -> None:
    """Persist this run's findings. Scoped by (run_date, stage) so the
    metadata and documents segments of the same day can't erase each other.

    Called on EVERY run, including a clean one and one that is about to
    hard-fail. E1 only called it when the override flag happened to be
    passed (`if allow_incomplete_universe is not None:`), so a normal run's
    findings were printed and then thrown away -- contradicting the flag's
    own help text. That was F2_SPEC §3.3's first latent bug.
    """
    conn.execute(
        "DELETE FROM universe_validation_problems WHERE run_date = ? AND stage = ?",
        (run_date.isoformat(), stage),
    )
    conn.executemany(
        "INSERT INTO universe_validation_problems "
        "(run_date, cik, ticker, stage, check_name, severity, message) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (run_date.isoformat(), p.cik, p.ticker, p.stage, p.check, p.severity, p.message)
            for p in problems
        ],
    )
    conn.commit()


# ---------------------------------------------------------------------------
# EX-99 earnings-exhibit selection audit (F2_SPEC §4.4)
# ---------------------------------------------------------------------------


def load_e1_ciks(path: Path = E1_UNIVERSE_CSV) -> set[int]:
    """E1's frozen 25-ticker universe, read ONLY to flag which E2 members are
    filers the earnings-document selection policy has never seen. It is not a
    pipeline input and is never written (HANDOFF: E1 artifacts are frozen).

    A missing file yields an empty set -- every member then reads as a new
    filer, which is the conservative direction (more filers flagged for the
    §4.4 manual read, never fewer).
    """
    if not path.exists():
        return set()
    return {int(c) for c in pd.read_csv(path)["cik"]}


EX99_AUDIT_COLUMNS = (
    "cik", "name", "sector", "stratum", "new_filer",
    "section_type", "selection_confidence", "n_filings", "first_seen_year",
    # P6 (F2_PROGRESS §5 ruling 2026-08-24) -- CIK-level, denormalised onto
    # every row of that CIK exactly as `new_filer` already is.
    "n_release_language_measured", "n_release_language_missing",
    # S7 B6: the SHARE is emitted for EVERY CIK, not just the >50% flags --
    # 398 of 10,549 selections lack release language and a per-CIK majority
    # test names only Netflix's 25. The ratio is the analysable column.
    "release_language_missing_share",
    "release_language_flag",
    # Deck-title screen (S6 §W ADDENDUM ruling 2026-08-24), CIK-level.
    "n_deck_shaped", "deck_shaped_flag",
)


def build_ex99_audit(
    selections: list[dict], universe: pd.DataFrame, e1_ciks: set[int],
    release_language_by_cik: Optional[dict[int, dict]] = None,
) -> pd.DataFrame:
    """One row per (cik, section_type, selection_confidence) -- F2_SPEC §4.4
    item 3.

    `selections` is the raw per-filing record the ingestion loop accumulates:
    {"cik", "section_type", "selection_confidence", "filing_date"}. The
    aggregate keeps `n_filings` (so §4.4's "20 worst filers by low-confidence
    count" is answerable) and `first_seen_year` (so a policy that only ever
    fails on pre-iXBRL vintages is visible as such).

    `new_filer` is True for any CIK outside E1's 25 -- MEASURED 219 of the 244
    members. It is the axis the S6 manual read is prioritised on.
    """
    meta = {
        int(r["cik"]): (r["name"], r["sector"], r["stratum"])
        for _, r in universe.iterrows()
    }
    agg: dict[tuple[int, str, str], dict] = {}
    for s in selections:
        key = (int(s["cik"]), s["section_type"], s["selection_confidence"])
        year = int(str(s["filing_date"])[:4])
        cell = agg.get(key)
        if cell is None:
            agg[key] = {"n_filings": 1, "first_seen_year": year}
        else:
            cell["n_filings"] += 1
            cell["first_seen_year"] = min(cell["first_seen_year"], year)
    screen = release_language_by_cik or {}
    rows = []
    for (cik, section_type, confidence), cell in sorted(agg.items()):
        name, sector, stratum = meta.get(cik, ("", "", ""))
        s = screen.get(cik, {})
        rows.append(
            {
                "cik": cik, "name": name, "sector": sector, "stratum": stratum,
                "new_filer": cik not in e1_ciks,
                "section_type": section_type, "selection_confidence": confidence,
                "n_filings": cell["n_filings"],
                "first_seen_year": cell["first_seen_year"],
                "n_release_language_measured": s.get("measured", 0),
                "n_release_language_missing": s.get("missing_release", 0),
                "release_language_missing_share": (
                    round(s["missing_release"] / s["measured"], 4)
                    if s.get("measured") else None
                ),
                "release_language_flag": bool(s.get("flag", False)),
                "n_deck_shaped": s.get("deck_shaped", 0),
                "deck_shaped_flag": bool(s.get("deck_flag", False)),
            }
        )
    return pd.DataFrame(rows, columns=list(EX99_AUDIT_COLUMNS))


def write_ex99_audit(audit: pd.DataFrame, path: Path = EX99_AUDIT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(path, index=False)


def earnings_doc_unresolved_problems(
    failures: list[dict], earnings_8k_total: int,
) -> list[ValidationProblem]:
    """F2_SPEC §4.4 item 2: every failed earnings-document resolution is a
    WARN naming the CIK and accession, and the AGGREGATE failure rate is FATAL
    above 1% of earnings 8-Ks.

    E1 printed these and moved on, leaving the earnings_doc_* columns
    untouched and the failure untracked -- indistinguishable downstream from a
    filing that legitimately has no exhibit. `failures` rows are
    {"cik", "accession_number", "reason"}.

    The rate arm is strictly `>` the threshold: 2 failures in 200 is exactly
    1% and stays WARN-only; 3 in 200 is 1.5% and is FATAL.
    """
    problems = [
        ValidationProblem(
            int(f["cik"]), "earnings_doc_unresolved", "WARN",
            f"CIK {f['cik']} {f['accession_number']}: earnings document "
            f"unresolved -- {f['reason']}. Counted, not just logged: the "
            f"filing's earnings_doc_* columns stay NULL, so F3 has no text for "
            f"this 8-K.",
        )
        for f in failures
    ]
    if not failures or earnings_8k_total <= 0:
        return problems
    rate = len(failures) / earnings_8k_total
    if rate > EARNINGS_DOC_UNRESOLVED_FATAL_RATE:
        problems.append(
            ValidationProblem(
                RUN_SCOPE_CIK, "earnings_doc_unresolved", "FATAL",
                f"{len(failures)} of {earnings_8k_total} earnings 8-Ks "
                f"({rate:.2%}) could not be resolved to an earnings document, "
                f"above the {EARNINGS_DOC_UNRESOLVED_FATAL_RATE:.0%} ceiling. At "
                f"that rate this is a selection-policy or index-format problem "
                f"across filers, not per-filing noise -- read the per-case WARNs "
                f"and {EX99_AUDIT_PATH.name} before trusting the corpus.",
            )
        )
    return problems


def earnings_doc_excluded_problems(exclusions: list[dict]) -> list[ValidationProblem]:
    """An evidenced `exclude` override is an EXPECTED state, not a failure --
    INFO, exactly like `member_stopped_filing`. It is deliberately kept OUT of
    the `earnings_doc_unresolved` rate, which measures the policy failing to
    resolve a document that exists; a human ruling that no document exists is
    a different fact and must not inflate a FATAL threshold.
    """
    return [
        ValidationProblem(
            int(e["cik"]), "earnings_doc_excluded_by_override", "INFO",
            f"CIK {e['cik']} {e['accession_number']} ({e['filing_date']}): no "
            f"earnings document, by evidenced override -- {e['reason']} "
            f"Counted and named; the filing's earnings_doc_* columns stay NULL.",
        )
        for e in exclusions
    ]


def press_release_outside_ex99_problems(hits: list[dict]) -> list[ValidationProblem]:
    """P3's WARN. Loud, and deliberately NOT a fix: picking a document because
    its description says "press release" would make every filer's description
    text part of the selection policy, which is how NVIDIA's typo would become
    a silent mis-pick generator across 10,569 filings. The resolution path is
    an evidenced row in earnings_doc_overrides.csv, added by a human who read
    the filing.
    """
    return [
        ValidationProblem(
            int(h["cik"]), "press_release_typed_outside_ex99", "WARN",
            f"CIK {h['cik']} {h['accession_number']}: index row {h['filename']} is "
            f"typed {h['doc_type']!r} -- outside the EX-99 family the selection "
            f"policy searches -- but its description reads "
            f"{h['description']!r}. Selected instead: {h['selected']!r}. NOT "
            f"auto-picked: resolve it with an evidenced row in "
            f"{EARNINGS_DOC_OVERRIDES_PATH.name} after reading the filing.",
        )
        for h in hits
    ]


def check_ex99_sector_coverage(
    audit: pd.DataFrame, universe: pd.DataFrame,
    earnings_8ks_by_sector: dict[str, int],
) -> list[ValidationProblem]:
    """F2_SPEC §4.4 item 5: each sector in the universe must show at least one
    HIGH-confidence EX99_PRESS_RELEASE selection. A sector with none means the
    policy does not work on that sector's filers -- "a blocker, not a
    footnote" -- and E2's extension stratum is three sectors E1 never saw.

    Two arms, because "the policy failed on this sector" and "this sector
    filed no earnings 8-Ks at all" are different findings and must not be
    conflated:
      - sector HAD earnings 8-Ks but no high-confidence selection -> FATAL.
      - sector had ZERO earnings 8-Ks in any member's window -> WARN. There
        was nothing to select from, so it is not a policy failure, but a whole
        sector of large caps filing no item-2.02 8-K over 11 years is
        surprising enough to say out loud rather than pass silently.
    """
    if audit.empty:
        good_sectors: set[str] = set()
    else:
        hits = audit[
            (audit["section_type"] == "EX99_PRESS_RELEASE")
            & (audit["selection_confidence"] == "high")
            & (audit["n_filings"] > 0)
        ]
        good_sectors = set(hits["sector"])
    problems = []
    for sector in sorted(set(universe["sector"])):
        if sector in good_sectors:
            continue
        seen = earnings_8ks_by_sector.get(sector, 0)
        if seen == 0:
            problems.append(
                ValidationProblem(
                    RUN_SCOPE_CIK, "ex99_sector_coverage", "WARN",
                    f"sector {sector!r}: zero earnings 8-Ks (item 2.02) across all "
                    f"of its members' coverage windows, so the selection policy "
                    f"was never exercised on it. Not a policy failure -- but "
                    f"F3 will have no 8-K earnings text for this sector.",
                )
            )
            continue
        problems.append(
            ValidationProblem(
                RUN_SCOPE_CIK, "ex99_sector_coverage", "FATAL",
                f"sector {sector!r}: {seen} earnings 8-K(s) seen but ZERO "
                f"high-confidence EX99_PRESS_RELEASE selections across all of its "
                f"members. The earnings-exhibit selection policy was calibrated on "
                f"E1's five core sectors; a sector with no clean selection at all "
                f"is a blocker on using that sector's 8-K text, not a footnote "
                f"(F2_SPEC §4.4 item 5).",
            )
        )
    return problems


# ---------------------------------------------------------------------------
# Evidenced per-accession earnings-document overrides (S6 manual read;
# F2_PROGRESS §5 ruling 2026-08-24)
# ---------------------------------------------------------------------------
# Same discipline as price_ticker_overrides.csv and manual_exclusions.csv: an
# evidenced CSV row plus a deliberate code edit to the ratified allowlist
# below. A row alone is refused. Two rows, both from the mandatory §4.4 read.
EARNINGS_DOC_OVERRIDE_COLUMNS = (
    "accession_number", "action", "document", "reason", "evidence", "added",
)
EARNINGS_DOC_OVERRIDE_ACTIONS = ("select_document", "exclude")
RATIFIED_EARNINGS_DOC_OVERRIDES = {
    # The TYPO CLASS: a filer's exhibit type-string puts the real press release
    # outside the EX-99 family the policy searches. Measured n=3 corpus-wide by
    # the P3 screen (press_release_typed_outside_ex99), which stays as the
    # permanent tripwire for future instances.
    "0001045810-19-000168",   # NVIDIA Q3 FY20 -- release typed EX-95.1
    "0001039684-15-000073",   # ONEOK Q3 2015 -- EX-95.1; fell back to the 8-K cover page
    "0000723125-19-000172",   # Micron Q1 FY20 -- `EX-99..1` (double dot); same fallback
    # The BARE-EX-<n> class (S7 red-team B1, ruled 2026-08-24): the release row
    # is typed EX-1/EX-2 and described "EXHIBIT 1"/"EXHIBIT 2", so it
    # self-labels neither as exhibit 99 nor as a release. The fallback candidate
    # screen correctly leaves these UNRESOLVED rather than guessing; the ratified
    # per-accession mechanism absorbs the four singletons instead of a new
    # policy route (the stored cover page's own body text WOULD resolve them,
    # but a third evidence route for 4 filings fails lazy-elite).
    # FUTURE INSTANCES OF THIS SHAPE STAY LOUD-UNRESOLVED, by design.
    "0001110803-16-000185",   # Illumina Q1 2016 -- EX-1 "EXHIBIT 1"
    "0001110803-16-000194",   # Illumina Q2 2016 -- EX-1 "EXHIBIT 1"
    "0001645590-17-000006",   # HPE Q4 FY2017 -- EX-1; TWO candidates, 99.1 is the earnings one
    "0001637459-19-000050",   # Kraft Heinz 2019-06-07 -- EX-1 "EXHIBIT 1"
    # Not typos -- filings that hold no earnings release to select.
    "0000732717-19-000048",   # AT&T Q3 2019 -- no release in this accession
    # An Item 2.02 wrapper over a conference slide deck. The candidate screen
    # RESOLVES this one (its row is described "EX-99.1(A)"), which made the
    # filing less honest than its old 8K_BODY state: a cover page really is a
    # body, a slide deck really is not a press release. Excluded, not re-picked
    # -- the filing has no better candidate (S6 manual read section W.3).
    "0001193125-18-111008",   # Pioneer 2018-04-09 -- IPAA symposium deck
}
MIN_EARNINGS_OVERRIDE_EVIDENCE_CHARS = 40
# The audit CSV's marker for an evidenced exclusion. Deliberately NOT a value
# any `filings.earnings_doc_section_type` ever takes: P4's new
# EX99_FINANCIAL_SCHEDULES section_type was ruled OUT (it would touch F4's
# labeling applicability), so the DB columns for an excluded accession stay
# NULL exactly as an unresolved one does, and only the audit artifact carries
# this marker.
EXCLUDED_SECTION_TYPE = "EXCLUDED_BY_OVERRIDE"


@dataclass(frozen=True)
class EarningsDocOverride:
    accession_number: str
    action: str
    document: str
    reason: str
    evidence: str
    added: str = ""

    @property
    def excludes(self) -> bool:
        return self.action == "exclude"


def load_earnings_doc_overrides(
    path: Path = EARNINGS_DOC_OVERRIDES_PATH,
) -> dict[str, EarningsDocOverride]:
    """Read `data/f2/earnings_doc_overrides.csv` with load-time validation.

    A MISSING file is a legitimate empty state (unlike the price overrides,
    whose absence would silently censor XOM -- here absence just means the
    policy decides everything, which is the default). A MALFORMED,
    unevidenced, or UNRATIFIED row RAISES: a silently-accepted override row is
    exactly the failure this mechanism exists to prevent.
    """
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str, keep_default_na=False, comment="#")
    missing = [c for c in EARNINGS_DOC_OVERRIDE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing required column(s) {missing}")

    out: dict[str, EarningsDocOverride] = {}
    for i, r in enumerate(df.to_dict("records"), start=2):  # +1 header, +1 1-based
        accession = str(r["accession_number"]).strip()
        if not accession:
            continue
        action = str(r["action"]).strip()
        document = str(r["document"]).strip()
        reason = str(r["reason"]).strip()
        evidence = str(r["evidence"]).strip()
        if accession in out:
            raise ValueError(f"{path} line {i}: duplicate row for {accession}")
        if accession not in RATIFIED_EARNINGS_DOC_OVERRIDES:
            raise ValueError(
                f"{path} line {i}: accession {accession!r} is not a ratified "
                f"override case. Ratified: {sorted(RATIFIED_EARNINGS_DOC_OVERRIDES)}. "
                f"An override replaces the selection policy's judgment for one "
                f"filing -- adding one takes a deliberate edit to "
                f"RATIFIED_EARNINGS_DOC_OVERRIDES in ingest_metadata.py alongside "
                f"the evidenced row, not a new line in this CSV."
            )
        if action not in EARNINGS_DOC_OVERRIDE_ACTIONS:
            raise ValueError(
                f"{path} line {i} ({accession}): unknown action {action!r}; "
                f"expected one of {list(EARNINGS_DOC_OVERRIDE_ACTIONS)}."
            )
        if action == "select_document" and not document:
            raise ValueError(
                f"{path} line {i} ({accession}): action=select_document requires "
                f"a `document` filename."
            )
        if action == "exclude" and document:
            raise ValueError(
                f"{path} line {i} ({accession}): action=exclude must leave "
                f"`document` empty -- an exclusion selects nothing."
            )
        if not reason:
            raise ValueError(f"{path} line {i} ({accession}): `reason` is mandatory")
        if len(evidence) < MIN_EARNINGS_OVERRIDE_EVIDENCE_CHARS:
            raise ValueError(
                f"{path} line {i} ({accession}): `evidence` is mandatory and must "
                f"be at least {MIN_EARNINGS_OVERRIDE_EVIDENCE_CHARS} characters of "
                f"primary-source detail; got {len(evidence)}. An override without "
                f"written evidence is not auditable and is refused."
            )
        out[accession] = EarningsDocOverride(
            accession_number=accession, action=action, document=document,
            reason=reason, evidence=evidence, added=str(r["added"]).strip(),
        )
    return out


def apply_earnings_doc_override(
    override: EarningsDocOverride, docs: list[dict],
) -> Optional[dict]:
    """Turn one override row into a selection (or None for `exclude`).

    RAISES if a `select_document` override names a filename that is not among
    the filing's own parsed index rows: a stale override must fail loudly, not
    resolve to nothing and look like an ordinary no-exhibit filing.
    """
    if override.excludes:
        return None
    match = [d for d in docs if d["filename"] == override.document]
    if len(match) != 1:
        raise ValueError(
            f"earnings_doc_overrides.csv ({override.accession_number}): "
            f"document {override.document!r} matches {len(match)} row(s) in the "
            f"filing's index (expected exactly 1). Available: "
            f"{sorted(d['filename'] for d in docs)}. The override is stale or "
            f"wrong -- fix the row rather than letting it resolve silently."
        )
    return _resolved(match[0], "EX99_PRESS_RELEASE", "high")


def print_earnings_doc_override_report(
    overrides: dict[str, EarningsDocOverride], fired: set[str],
    path: Path = EARNINGS_DOC_OVERRIDES_PATH,
) -> None:
    """Print every override, fired or not. A dead override is a bug in the file
    (the filing it names is no longer in the corpus, or its accession is
    mistyped), so it is called out rather than left to rot -- same rule as the
    validation-exceptions and price-override reports."""
    if not overrides:
        print(
            f"\nearnings-document overrides ({path}): none. Every earnings 8-K "
            f"is decided by the selection policy."
        )
        return
    dead = [a for a in overrides if a not in fired]
    print(f"\nearnings-document overrides ({path}): {len(overrides)} row(s), "
          f"{len(fired)} fired, {len(dead)} DEAD:")
    for accession, ov in sorted(overrides.items()):
        state = "FIRED" if accession in fired else "DEAD (never fired -- fix the file)"
        target = ov.document if ov.document else "(exclude: no earnings document)"
        print(f"  {state}: {accession} [{ov.action}] -> {target}")
        print(f"      reason: {ov.reason}")


# ---------------------------------------------------------------------------
# P3 -- a press release typed outside the EX-99 family (WARN, never auto-pick)
# ---------------------------------------------------------------------------
# The NVIDIA shape: a filer typo puts the real release outside the type family
# the policy searches, and the policy silently takes something else. Ruled a
# loud WARN, NOT a description-driven auto-pick -- trusting descriptions is how
# a typo becomes a silent mis-pick generator (S6 read §6, P3).
_PRESS_RELEASE_DESC_RE = re.compile(r"\b(press|news|earnings)\s+release\b", re.I)
# Row types that are not candidate documents at all. GRAPHIC is the big one:
# 15 of the 18 raw hits over the real corpus are news-release HEADER LOGOS
# (Eversource, AvalonBay), which are images, not documents.
_NON_DOCUMENT_TYPES = ("GRAPHIC", "XML", "ZIP", "JSON", "EX-101", "EX-96", "8-K")


def press_release_typed_outside_ex99(
    docs: list[dict], selected_filename: Optional[str],
) -> list[dict]:
    """Index rows DESCRIBED as a press release whose TYPE is outside the EX-99
    family and which were not the row selected.

    Excludes non-document rows and the 8-K cover row itself -- a cover row
    described "Q3 2015 EARNINGS RELEASE" is the normal way filers name an
    earnings 8-K and is not a finding.

    SCOPE -- READ THIS BEFORE QUOTING ITS COUNT (S7 red-team B7). This trigger
    fires 3 times over all 10,569 earnings 8-Ks: NVIDIA `0001045810-19-000168`,
    ONEOK `0001039684-15-000073`, Micron `0000723125-19-000172`. **Those 3 are
    hits for THIS TRIGGER, not the size of the defect class.** The class -- an
    earnings exhibit whose type string falls outside `^EX-99(\\.\\d+)?$` -- is
    **38 filings** corpus-wide (`EX-99..1` x5, `EX-99.2O` x17, `EX-99.1PRE` x6,
    `EX-99.(A)`/`EX-99.A` x3, `EX-99.`, `EX-99..02`, `EX-99.1(A)`,
    `EX-99.Q120 EARNINGS`, ...). P3 sees only the instances whose filer happened
    to write a DESCRIPTIVE description; the 14 cover-page defects in B1 describe
    themselves "EXHIBIT 99..1" / "EX-99.1" / "EXHIBIT 1" and are invisible to
    it. The fallback-side candidate screen (`earnings_candidate_rows`), not this
    WARN, is what covers the class.
    """
    out = []
    for d in docs:
        doc_type = (d.get("doc_type") or "").upper()
        if _EX99_FAMILY_RE.match(_canonical_exhibit_type(doc_type)):
            continue
        if not doc_type or any(doc_type.startswith(t) for t in _NON_DOCUMENT_TYPES):
            continue
        if selected_filename and d["filename"] == selected_filename:
            continue
        if _PRESS_RELEASE_DESC_RE.search(d.get("description") or ""):
            out.append(d)
    return out


_EX99_FAMILY_RE = re.compile(r"^EX-99(\.\d+)?$", re.I)


def coregistrant_problems(
    shared: dict[tuple[int, int], list[str]],
) -> list[ValidationProblem]:
    """One WARN per pair of member CIKs that co-filed the same accession.

    `filings.accession_number` is the PRIMARY KEY (E1's schema, unchanged by
    F2_SPEC §1.4), and EDGAR lists co-registrants on a single accession -- a
    parent and its subsidiary file ONE 8-K together. When both are members,
    the second writer's `cik` attribution is lost: the row keeps the first
    (lowest, so deterministic) CIK. MEASURED over the real 244 members: 87 of
    45,622 filings (0.19%), across exactly three pairs -- Dow Chemical
    (29915) / Dow Inc (1751788) 67, Williams Companies (107263) / Williams
    Partners (1483096) 16, Exelon (1109357) / Constellation (1868275) 4.

    RULED 2026-08-24 (main session, F2_PROGRESS §5): re-keying `filings` on
    (accession_number, cik) would ripple into filing_documents' parent key and
    F3's extraction grain for 0.19% of rows -- rejected as over-engineering.
    Instead every dropped attribution is stored row-by-row in
    `co_registrant_filings`, and these WARNs stay on top as the per-pair
    summary a human actually reads.

    BINDING DOWNSTREAM RULE: absence from `filings` alone is never evidence a
    company did not file. Coverage questions consult `filings` UNION
    `co_registrant_filings`.
    """
    problems = []
    for (kept, lost), accessions in sorted(shared.items()):
        problems.append(
            ValidationProblem(
                lost, "co_registrant_filing", "WARN",
                f"CIK {lost} co-filed {len(accessions)} accession(s) with member "
                f"CIK {kept} (e.g. {accessions[0]}). `filings` is keyed on "
                f"accession_number, so those rows are stored under CIK {kept} "
                f"only and CIK {lost}'s attribution to them is NOT in the table. "
                f"Counted here, never silently dropped; F5 must not read a "
                f"missing row as 'this company did not file'.",
            )
        )
    return problems


# ---------------------------------------------------------------------------
# P5 + P6 -- one screen over the cached selected documents
# ---------------------------------------------------------------------------
# P6 is the generalisation of what caught Prologis: the confidence label does
# NOT track correctness, so the only way to notice a filer whose picks are
# systematically the wrong exhibit is to look at what was actually selected.
# Both P5 (thin/image-only exhibits) and P6 (a filer whose picks mostly lack
# release language) come from the same single pass over the cache, so the cost
# is one read per selected document and ZERO network requests -- documents are
# cache-forever and segment 2 has already fetched them.
_IMG_RE = re.compile(r"<img\b", re.I)
RELEASE_LANGUAGE_MARKERS = (
    "press release", "news release", "earnings release", "today reported",
    "today announced", "announced today", "for immediate release",
    "conference call", "investor relations", "webcast",
)
# P5 thresholds. MEASURED over the 9,981 cached selections: 44 selections have
# <1,500 characters of extractable text and 12 have <100. Both classes are
# defensible picks (it is the only EX-99 present) whose extracted section will
# be empty or near-empty, so they are named HERE, at selection time, instead of
# resurfacing in F3 as anonymous MIN_SECTION_WORDS failures.
THIN_EXHIBIT_CHARS = 1500
EMPTY_EXHIBIT_CHARS = 100
# P6. "MOSTLY lack release language" = a strict majority, and only for filers
# with enough measured selections that the share means something (Prologis has
# 45). A filer below the floor is reported as unmeasured, never as clean.
P6_MIN_MEASURED_SELECTIONS = 4
P6_MISSING_RELEASE_SHARE = 0.5
# S7 B6: a per-CIK MAJORITY test cannot see a systematic mis-picker that is
# wrong on a large minority. MEASURED, Pioneer sits at 38/77 = 49.4% -- ONE
# filing from flagging -- and is independently implicated in B1. So every CIK
# at or above this share is printed as a named WATCH LIST beside the flags.
# This adds visibility; it does NOT move P6_MISSING_RELEASE_SHARE.
P6_WATCH_SHARE = 0.40


# P6 SCOPE (ruled 2026-08-24, F2_PROGRESS §5): release-language markers are
# counted only OUTSIDE the document's leading title/self-label region. A
# document whose ONLY marker hit is its own title does not count as having
# release language.
#
# Why this is a scope fix and not a threshold move: Prologis 2016-04-19 is a
# Supplemental package carrying a template-leftover title, "Prologis Earnings
# Release and Supplemental Information". Its single marker hit in 113,158
# characters IS that title, so P6 passed it as clean and the handler's own
# content-confirmation generalised from the same string. Both guards keyed on
# a document's self-description; neither read its body.
#
# The boundary CANNOT be a plain "first marker must be late" rule: MEASURED
# first-marker offsets are 27-89 for genuine releases and 64 for this false
# positive -- they interleave. What separates them is whether ANY marker
# survives the title region:
#
#   cut at 200 chars   false positive: 0 hits beyond  -> flags (correct)
#                      41 Prologis EX-99.2 releases:  >= 3 hits beyond
#                      NVIDIA / ONEOK / Micron:       10 / 11 / 8
#                      the 3 genuine pre-split combined EX-99.1 docs: 11 / 9 / 1
#
# 200 is chosen with that margin visible: the weakest genuine document
# (2016-01-26, a combined release+supplemental) keeps 1 hit, and the boundary
# must stay <= ~300 -- at 400 that document drops to 0 and would false-flag.
TITLE_REGION_CHARS = 200


# DECK-TITLE SCREEN (S6 §W ADDENDUM, ruled 2026-08-24) -- generalises what
# caught PSEG. A selection whose TITLE names it a conference-call deck is
# deck-shaped REGARDLESS of body marker hits, because P6 cannot see this class:
# a deck's contact slide says "investor relations", so all 24 PSEG selections
# that "passed" P6 passed on that alone.
#
# EVERY MARKER BELOW IS MEASURED IN THE CORPUS -- none is speculative. Over all
# 10,567 cached selections, title-region hits are:
#   'earnings conference call'              26 (PSEG 25, Danaher 1)
#   'financial results presentation'        18 (PSEG only)
#   'financial results and conference call'  2 (PSEG only)
# and 25 + 18 + 2 = 45 = all of PSEG.
#
# The generic phrase "conference call" was MEASURED and REJECTED: 93 hits over
# 11 CIKs, including Texas Instruments 45 and Nike 12 whose releases simply name
# the call in their header. A screen that flags those is worse than no screen.
DECK_TITLE_MARKERS = (
    "earnings conference call",
    "financial results presentation",
    "financial results and conference call",
)
# Corroboration, required in addition to the title marker. Danaher
# `0000313616-20-000081` is a genuine press release headlined "... AND SCHEDULES
# FIRST QUARTER EARNINGS CONFERENCE CALL", so the title marker alone has a
# measured false positive. Requiring the deck's own boilerplate as well drops it
# and keeps all 45 PSEG decks: MEASURED, title-only flags {PSEG 45, Danaher 1},
# title+corroboration flags {PSEG 45} exactly.
DECK_BODY_CORROBORATION = ("forward-looking statement", "this presentation")
DECK_CORROBORATION_CHARS = 1500


def screen_selected_document(text: str) -> dict:
    """Signals for ONE selected document's raw HTML. Pure function, no I/O.

    `has_release_language` is True only when a marker appears BEYOND the
    leading TITLE_REGION_CHARS characters -- see that constant for the
    measurement behind it. The extracted text begins with EDGAR's own
    self-label echo (type, sequence, filename, description) followed by the
    document's title, so that prefix is exactly the region where a document
    describes itself rather than says anything.
    """
    stripped = _TAG_RE.sub(" ", text)
    plain = re.sub(r"\s+", " ", html.unescape(stripped)).strip()
    lowered = plain.lower()
    title = lowered[:TITLE_REGION_CHARS]
    body = lowered[TITLE_REGION_CHARS:]
    return {
        "chars": len(plain),
        "images": len(_IMG_RE.findall(text)),
        "has_release_language": any(m in body for m in RELEASE_LANGUAGE_MARKERS),
        # Deck-shaped: the TITLE names it a call deck AND the deck's own
        # boilerplate corroborates. Independent of has_release_language by
        # design -- a deck's contact slide trips the release markers.
        "deck_shaped": (
            any(m in title for m in DECK_TITLE_MARKERS)
            and any(c in lowered[:DECK_CORROBORATION_CHARS]
                    for c in DECK_BODY_CORROBORATION)
        ),
    }


def screen_selected_documents(
    client: EdgarClient, selections: list[dict],
) -> tuple[list[ValidationProblem], dict[int, dict]]:
    """Read every selected document that is already in the cache and return
    (P5 problems, per-CIK P6 summary).

    A selection with no cached document is COUNTED as unmeasured, never as
    clean -- on a first run (before `--stage documents`) that is most of them,
    and a screen that silently reported "0 problems" for an unread corpus
    would be worse than no screen. Makes ZERO network requests by construction:
    it only ever reads files that exist.
    """
    problems: list[ValidationProblem] = []
    by_cik: dict[int, dict] = {}
    for s in selections:
        cik = int(s["cik"])
        cell = by_cik.setdefault(
            cik, {"measured": 0, "missing_release": 0, "uncached": 0, "flag": False,
                  "seen": 0, "deck_shaped": 0, "deck_flag": False}
        )
        path = (
            document_cache_path(client, s["relative_path"])
            if s.get("relative_path") else None
        )
        if path is None or not path.exists():
            cell["uncached"] += 1
            continue
        try:
            signals = screen_selected_document(
                path.read_text(encoding="utf-8", errors="replace")
            )
        except OSError as e:  # noqa: BLE001 -- unreadable cache file, count it
            cell["uncached"] += 1
            problems.append(
                ValidationProblem(
                    cik, "ex99_thin_exhibit", "WARN",
                    f"CIK {cik} {s['accession_number']}: could not read the cached "
                    f"selected document {s['relative_path']}: {e}.",
                )
            )
            continue

        # -- P5: thin / image-only / empty exhibits ------------------------
        if signals["chars"] < THIN_EXHIBIT_CHARS:
            kind = (
                "IMAGE-ONLY (the exhibit is a wrapper around slide images, so "
                "tag-stripping yields nothing)"
                if signals["images"] > 0
                else "EMPTY AT SOURCE (no images either -- this is what EDGAR holds)"
            )
            severity_note = (
                " Under the 100-character floor." if signals["chars"] < EMPTY_EXHIBIT_CHARS
                else ""
            )
            problems.append(
                ValidationProblem(
                    cik, "ex99_thin_exhibit", "WARN",
                    f"CIK {cik} {s['accession_number']}: selected document "
                    f"{s['filename']} has only {signals['chars']} characters of "
                    f"extractable text ({signals['images']} <img> tags) -- {kind}."
                    f"{severity_note} The pick is defensible (it is the only EX-99 "
                    f"present); the resulting section will be empty or near-empty, "
                    f"and F3's MIN_SECTION_WORDS floor SHOULD fail it. Named here "
                    f"so a future recalibration argues past these, not around them.",
                )
            )

        # -- Deck-title screen: independent of P6, and of confidence. A deck
        # labelled EX99_PRESS_RELEASE is wrong at ANY confidence.
        cell["seen"] += 1
        if signals["deck_shaped"]:
            cell["deck_shaped"] += 1

        # -- P6: does this filer's picks read like press releases? ---------
        if s.get("selection_confidence") in ("high", "medium"):
            cell["measured"] += 1
            if not signals["has_release_language"]:
                cell["missing_release"] += 1

    for cik, cell in by_cik.items():
        cell["flag"] = (
            cell["measured"] >= P6_MIN_MEASURED_SELECTIONS
            and cell["missing_release"] / cell["measured"] > P6_MISSING_RELEASE_SHARE
        )
        # ANY deck-shaped selection flags, with no majority test and no minimum
        # sample: unlike release-language-missing (which has benign shapes --
        # Netflix's shareholder letters), a conference-call deck stored as a
        # press release is simply a false label, so there is no share at which
        # it becomes acceptable.
        cell["deck_flag"] = cell["deck_shaped"] > 0
    return problems, by_cik


def release_language_problems(by_cik: dict[int, dict], universe: pd.DataFrame) -> list[ValidationProblem]:
    """P6's WARN: a filer whose high/medium-confidence selections MOSTLY lack
    press-release language is selecting the wrong exhibit systematically.

    This is the check that would have caught Prologis without a manual read:
    37 of its 45 wrong picks were HIGH confidence, so no confidence-based
    trigger could ever have surfaced them. WARN, not FATAL, and never an
    auto-fix -- the resolution is a named dialect handler or an evidenced
    override, both of which take a human.
    """
    names = {int(r["cik"]): r["name"] for _, r in universe.iterrows()}
    problems = []
    for cik, cell in sorted(by_cik.items()):
        if not cell["flag"]:
            continue
        share = cell["missing_release"] / cell["measured"]
        problems.append(
            ValidationProblem(
                cik, "ex99_release_language_missing", "WARN",
                f"CIK {cik} ({names.get(cik, '?')}): {cell['missing_release']} of "
                f"{cell['measured']} high/medium-confidence selections contain NO "
                f"press-release language ({share:.0%}). A filer whose picks mostly "
                f"do not read like releases is selecting the wrong exhibit "
                f"systematically -- this is the Prologis shape, and confidence "
                f"does NOT track correctness for it. Read one filing's index "
                f"against its selection before trusting this CIK's 8-K text.",
            )
        )
    return problems


def deck_shaped_problems(
    by_cik: dict[int, dict], universe: pd.DataFrame,
) -> list[ValidationProblem]:
    """WARN per CIK with any deck-shaped selection (S6 §W ADDENDUM ruling).

    This is the screen that replaces spot-read luck for this defect class. It is
    deliberately independent of P6: PSEG scored 21/45 release-language-missing
    and therefore sat UNDER the flag bar, while the true rate was 45/45 -- all
    24 "passers" passed on `"investor relations"` from a contact slide. A
    per-CIK majority test cannot see a filer whose every pick is a deck that
    happens to carry release boilerplate.
    """
    names = {int(r["cik"]): r["name"] for _, r in universe.iterrows()}
    problems = []
    for cik, cell in sorted(by_cik.items()):
        if not cell.get("deck_flag"):
            continue
        problems.append(
            ValidationProblem(
                cik, "ex99_deck_shaped_selection", "WARN",
                f"CIK {cik} ({names.get(cik, '?')}): {cell['deck_shaped']} of "
                f"{cell['seen']} screened selection(s) are TITLED as a "
                f"conference-call deck "
                f"('{DECK_TITLE_MARKERS[0]}'-class) and corroborated by the "
                f"deck's own boilerplate. A slide deck stored as "
                f"EX99_PRESS_RELEASE is a false label at any confidence, and F3 "
                f"will extract it as press-release text. Read one filing's index "
                f"against its selection: the release is usually the OTHER "
                f"EX-99 row.",
            )
        )
    return problems


def print_ex99_audit_report(
    audit: pd.DataFrame, failures: list[dict], earnings_8k_total: int,
    path: Path = EX99_AUDIT_PATH,
    exclusions: Optional[list[dict]] = None,
    release_language_by_cik: Optional[dict[int, dict]] = None,
) -> None:
    """Print the audit summary and the S6 manual-read worklist. The read
    itself is a human's job at S6 (F2_SPEC §4.4 item 4); this prints WHO to
    read, worst-first, with the cap and the untouched remainder both stated.
    """
    print(f"\nEX-99 selection audit ({path}):")
    print(f"  earnings 8-Ks seen:        {earnings_8k_total}")
    print(f"  unresolved (counted):      {len(failures)}"
          + (f"  ({len(failures) / earnings_8k_total:.2%})" if earnings_8k_total else ""))
    print(f"  excluded by override:      {len(exclusions or [])}"
          f"   (evidenced, INFO -- not counted as unresolved)")
    if release_language_by_cik:
        measured = sum(c["measured"] for c in release_language_by_cik.values())
        uncached = sum(c["uncached"] for c in release_language_by_cik.values())
        flagged = [c for c, cell in sorted(release_language_by_cik.items()) if cell["flag"]]
        total_missing = sum(c["missing_release"] for c in release_language_by_cik.values())
        print(f"  release-language screen:   {measured} selection(s) measured, "
              f"{uncached} not cached (UNMEASURED, not clean)")
        print(f"    selections with NO release language: {total_missing} "
              f"(the per-CIK share is in {path.name} for every CIK, not just the flagged)")
        print(f"    CIKs whose high/medium picks MOSTLY lack release language: "
              f"{len(flagged)}{(' -> ' + ', '.join(str(c) for c in flagged)) if flagged else ''}")
        # S7 B6: a majority test hides the near-misses; name them.
        watch = [
            (c, cell) for c, cell in sorted(release_language_by_cik.items())
            if not cell["flag"] and cell["measured"] >= P6_MIN_MEASURED_SELECTIONS
            and cell["missing_release"] / cell["measured"] >= P6_WATCH_SHARE
        ]
        decks = [(c, cell) for c, cell in sorted(release_language_by_cik.items())
                 if cell.get("deck_flag")]
        print(f"    DECK-SHAPED selections (title names a conference-call deck): "
              f"{sum(cell['deck_shaped'] for _, cell in decks)} across {len(decks)} CIK(s)"
              + (f" -> {', '.join(str(c) for c, _ in decks)}" if decks else ""))
        print(f"    WATCH LIST (>= {P6_WATCH_SHARE:.0%} but under the "
              f"{P6_MISSING_RELEASE_SHARE:.0%} flag bar): {len(watch)}")
        for c, cell in watch:
            print(f"      CIK {c}: {cell['missing_release']}/{cell['measured']} "
                  f"({cell['missing_release'] / cell['measured']:.1%}) -- not flagged, "
                  f"one systematic mis-picker can sit here indefinitely")
    if audit.empty:
        print("  no selections recorded -- nothing to audit.")
        return
    resolved = int(audit["n_filings"].sum())
    print(f"  resolved selections:       {resolved}")
    combos = (
        audit.groupby(["section_type", "selection_confidence"])["n_filings"]
        .sum().sort_index()
    )
    for (section_type, confidence), n in combos.items():
        print(f"    {section_type:<20} {confidence:<8} {n:>7}")

    # NAME the benign class, don't let it hide inside a total. Segment 1's
    # first attempt (2026-08-24) counted 64 of these as `earnings_doc_
    # unresolved` failures because the index parser's old >=3-row guard
    # rejected their two-row indices; they are legitimately exhibit-less
    # 8-Ks, not holes. They are reclassified, not dropped: each one is a
    # counted 8K_BODY selection here AND lands on the manual-read worklist
    # below (see data/f2/status/S6_seg1_ex99_diagnosis.md).
    body = int(audit.loc[audit["section_type"] == "8K_BODY", "n_filings"].sum())
    if body:
        body_ciks = audit.loc[audit["section_type"] == "8K_BODY", "cik"].nunique()
        print(f"  of which 8K_BODY fallbacks: {body} filing(s) across "
              f"{body_ciks} CIK(s) -- earnings 8-Ks that carry the release in "
              f"the 8-K body with no EX-99 exhibit at all. A benign, named "
              f"class, still on the §4.4 read list below.")

    # Who the S6 human must read: any low-confidence selection or any 8K_BODY
    # fallback (the CANARY lines are printed inline during the run).
    needs_read = audit[
        (audit["selection_confidence"] == "low") | (audit["section_type"] == "8K_BODY")
    ]
    low = (
        audit[audit["selection_confidence"] == "low"]
        .groupby("cik")["n_filings"].sum()
    )
    read_ciks = sorted(set(needs_read["cik"]))
    print(f"  CIKs needing the §4.4 manual read (any low-confidence selection or "
          f"any 8K_BODY fallback): {len(read_ciks)}")
    if read_ciks:
        ranked = sorted(
            read_ciks, key=lambda c: (-int(low.get(c, 0)), c)
        )[:EX99_MANUAL_READ_CAP]
        for c in ranked:
            print(f"    CIK {c}: {int(low.get(c, 0))} low-confidence selection(s)")
        remainder = len(read_ciks) - len(ranked)
        if remainder:
            print(f"    ... capped at the {EX99_MANUAL_READ_CAP} worst filers; "
                  f"{remainder} more CIK(s) are NOT covered by that read and stay "
                  f"unread -- state that in the F2 report rather than implying "
                  f"full coverage.")


# ---------------------------------------------------------------------------
# Main ingestion run
# ---------------------------------------------------------------------------


def archive_document_path(cik: int, accession_number: str, filename: str) -> str:
    """The EDGAR archive path of one document inside one filing, in exactly
    the `/Archives/edgar/data/...` shape EdgarClient.get_archive_document()
    and the `filing_documents.relative_path` column both use."""
    return f"/Archives/edgar/data/{int(cik)}/{accession_number.replace('-', '')}/{filename}"


def document_cache_path(client: EdgarClient, relative_path: str) -> Path:
    """Where get_archive_document() would cache `relative_path`.

    Deliberately mirrors the client's own key derivation instead of adding a
    method to edgar_client.py (F2_SPEC §4.3 pins that module's only S3 change
    to the max_age_hours passthrough). The duplication is guarded by
    test_document_cache_path_agrees_with_the_client, which fetches through a
    monkeypatched client and asserts the byte lands exactly here -- if the two
    ever diverge, that test fails rather than the prefetch silently
    re-downloading ~26 GB.

    This exists so `--stage documents` can skip an already-cached document
    without calling the client at all: get_archive_document() would read and
    UTF-8-decode the whole file just to hand back text the prefetch pass has
    no use for.
    """
    if not relative_path.startswith("/"):
        relative_path = "/" + relative_path
    return Path(client.cache_dir) / "documents" / relative_path.strip("/").replace("/", "_")


def document_prefetch_targets(conn: sqlite3.Connection) -> list[dict]:
    """Every document `--stage documents` must have on disk for F3 to run at
    0 GETs (F2_SPEC §4.6), read out of the `filings` table:

      - each 10-K / 10-Q primary document;
      - each resolved `earnings_doc_relative_path`.

    MEASURED against the real 244 members (2026-08-24, cache-only): the
    enumeration yields 9,984 periodic filings (2,452 + 7,532) and 10,569
    earnings 8-Ks -- F2_SPEC §4.6's counts exactly -- but the `filings` table
    holds 9,954 periodic rows, because 30 of those 9,984 are co-registrant
    accessions shared with another member CIK and collapse onto one row (see
    coregistrant_problems()). So the real prefetch budget is ~30 documents
    below §4.6's 20,553, not a discrepancy to chase.

    Deduplicated on relative_path, keeping the first occurrence, so a path
    reachable two ways is requested exactly once. Order is stable
    (cik, filing_date, accession) so a killed run resumes over the same
    sequence and its progress lines mean the same thing.
    """
    rows = conn.execute(
        "SELECT cik, accession_number, form, primary_document, "
        "       earnings_doc_relative_path "
        "FROM filings ORDER BY cik, filing_date, accession_number"
    ).fetchall()
    seen: set[str] = set()
    out: list[dict] = []
    for cik, accession_number, form, primary_document, earnings_path in rows:
        candidates = []
        if form in PERIODIC_FORMS and primary_document:
            candidates.append(
                (archive_document_path(cik, accession_number, primary_document), form)
            )
        if earnings_path:
            candidates.append((earnings_path, "earnings_doc"))
        for relative_path, kind in candidates:
            if relative_path in seen:
                continue
            seen.add(relative_path)
            out.append(
                {
                    "cik": int(cik), "accession_number": accession_number,
                    "relative_path": relative_path, "kind": kind,
                }
            )
    return out


def run_documents_stage(
    client: EdgarClient, conn: sqlite3.Connection, run_date: date,
    force_refresh: bool = False, progress_every: int = 500,
) -> list[ValidationProblem]:
    """Prefetch-only segment: pull every 10-K/10-Q primary document and every
    resolved earnings-exhibit document into the cache-forever
    data/raw/documents/ cache, so F3's extract.py runs at 0 GETs.

    Parses nothing, writes no filing text anywhere but the cache, and touches
    no table except universe_validation_problems.

    Resume property (stated exactly, not aspirationally): each document is a
    separate cache-forever file, so there is no partial-write failure mode at
    the corpus level, and a re-run's skip scan is a stat() per path -- seconds
    over ~20k paths, ZERO network requests. A fetch failure is counted and
    named per document and never aborts the walk; F3 would otherwise discover
    the hole one document at a time.
    """
    targets = document_prefetch_targets(conn)
    if not targets:
        print(
            "\n--stage documents: the `filings` table is empty, so there is "
            "nothing to prefetch. Run --stage metadata against this database "
            "first (F2_SPEC §7 segment 1 precedes segment 2)."
        )
        sys.exit(1)

    by_kind: dict[str, int] = {}
    for t in targets:
        by_kind[t["kind"]] = by_kind.get(t["kind"], 0) + 1
    print(
        f"\n--stage documents: {len(targets)} document(s) to have on disk "
        f"({by_kind}). Nothing is parsed here; this fills the cache-forever "
        f"data/raw/documents/ cache so extract.py runs at 0 GETs."
    )

    fetched = cached = failed = 0
    problems: list[ValidationProblem] = []
    for i, t in enumerate(targets, start=1):
        if not force_refresh and document_cache_path(client, t["relative_path"]).exists():
            cached += 1
        else:
            try:
                client.get_archive_document(t["relative_path"], force=force_refresh)
                fetched += 1
            except Exception as e:  # noqa: BLE001 -- count it, name it, keep walking
                failed += 1
                problems.append(
                    ValidationProblem(
                        t["cik"], "document_fetch_failed", "WARN",
                        f"CIK {t['cik']} {t['accession_number']}: could not fetch "
                        f"{t['relative_path']} ({t['kind']}): {e}. F3 will find no "
                        f"cached text for this document.",
                        stage="documents",
                    )
                )
                print(f"  WARN: fetch failed {t['relative_path']}: {e}")
        if progress_every and i % progress_every == 0:
            print(
                f"  {i}/{len(targets)} documents "
                f"({fetched} fetched / {cached} already cached / {failed} failed)"
            )

    write_validation_problems(conn, problems, run_date, stage="documents")
    print(
        f"\n--stage documents done: {len(targets)} target(s), {fetched} fetched, "
        f"{cached} already cached, {failed} FAILED."
    )
    if failed:
        print(
            f"  {failed} failure(s) are in universe_validation_problems "
            f"(run_date={run_date.isoformat()}, stage=documents) as "
            f"`document_fetch_failed` WARNs, named per document. Re-running this "
            f"stage retries exactly those -- everything else is a cache hit."
        )
    return problems


def _spell_intervals(spells: pd.DataFrame) -> dict[int, list[tuple[date, Optional[date]]]]:
    """cik -> [(member_from, member_to_exclusive_or_None)]. `member_to` is
    EXCLUSIVE (see load_membership())."""
    out: dict[int, list[tuple[date, Optional[date]]]] = {}
    for _, r in spells.iterrows():
        to = str(r["member_to"] or "")
        out.setdefault(int(r["cik"]), []).append(
            (date.fromisoformat(str(r["member_from"])),
             date.fromisoformat(to) if to else None)
        )
    return out


def _inside_any_spell(intervals: list[tuple[date, Optional[date]]], d: date) -> bool:
    return any(start <= d and (end is None or d < end) for start, end in intervals)


def run(
    force_refresh: bool = False,
    db_path: Path = DB_PATH,
    exceptions_path: Path = VALIDATION_EXCEPTIONS_PATH,
    stage: str = DEFAULT_STAGE,
    max_age_hours: Optional[float] = DEFAULT_MAX_AGE_HOURS,
    ex99_audit_path: Path = EX99_AUDIT_PATH,
    overrides_path: Path = EARNINGS_DOC_OVERRIDES_PATH,
) -> None:
    """Run one or both ingestion stages against `db_path` (default: the E2
    database).

      metadata   enumerate every hybrid136 member CIK over its own coverage
                 window, validate, and write companies/filings/membership/
                 distress_events + the EX-99 selection audit.
      documents  prefetch every 10-K/10-Q primary document and every resolved
                 earnings-exhibit document into the cache. Parses nothing.
      all        both, in that order.

    There is no `--allow-incomplete-universe` any more. A FATAL still hard-
    fails the run; the only way to accept one is an evidenced row in
    `data/f2/validation_exceptions.csv` naming exactly one (cik, check) pair
    (F2_SPEC §3.2). Validation findings are persisted on EVERY run, including
    the run that is about to hard-fail on them.
    """
    if stage not in STAGES:
        raise ValueError(f"unknown --stage {stage!r}; expected one of {list(STAGES)}")
    db_path = Path(db_path)
    if db_path.resolve() == E1_DB_PATH.resolve():
        raise ValueError(
            f"Refusing to write {E1_DB_PATH} -- that is E1's frozen record "
            f"(F2_SPEC §1.4 / ruling 4). E2 writes {DB_PATH.name}."
        )

    client = EdgarClient()
    conn = sqlite3.connect(db_path)
    init_db(conn)
    print(f"stage={stage} -> {db_path} (cache TTL {max_age_hours} h)")
    # Provenance stamp for the problems table only -- NOTHING about what gets
    # ingested or how it is validated depends on it (F2_SPEC §2). This is the
    # ONE date.today() call in this module, by design.
    run_date = date.today()
    try:
        if stage in ("metadata", "all"):
            run_metadata_stage(
                client, conn, run_date, exceptions_path=exceptions_path,
                force_refresh=force_refresh, max_age_hours=max_age_hours,
                ex99_audit_path=ex99_audit_path,
                overrides_path=overrides_path,
            )
        if stage in ("documents", "all"):
            run_documents_stage(client, conn, run_date, force_refresh=force_refresh)
    finally:
        conn.close()
    print(f"Total EDGAR network GETs this run: {client.request_count}")


def run_metadata_stage(
    client: EdgarClient,
    conn: sqlite3.Connection,
    run_date: date,
    exceptions_path: Path = VALIDATION_EXCEPTIONS_PATH,
    force_refresh: bool = False,
    max_age_hours: Optional[float] = DEFAULT_MAX_AGE_HOURS,
    ex99_audit_path: Path = EX99_AUDIT_PATH,
    overrides_path: Path = EARNINGS_DOC_OVERRIDES_PATH,
) -> None:
    """Enumerate + validate + write. No filing text is downloaded here --
    that is `--stage documents`."""
    universe = load_universe()
    spells = load_membership()
    write_membership(conn, spells)
    print(
        f"E2 corpus window {CORPUS_WINDOW_START.isoformat()} .. "
        f"{CORPUS_WINDOW_END.isoformat()} (fixed literals, not derived from today). "
        f"{len(universe)} member CIKs / {len(spells)} membership spells "
        f"-> stage=metadata"
    )

    # Loaded BEFORE anything runs, so a malformed override row fails the run
    # immediately rather than after an hour of enumeration.
    overrides = load_earnings_doc_overrides(overrides_path)

    # -- Validate before writing any filings ---------------------------------
    exceptions = load_validation_exceptions(exceptions_path)
    problems = validate_universe(
        client, universe, force_refresh=force_refresh, max_age_hours=max_age_hours,
    )
    problems, fired = apply_validation_exceptions(problems, exceptions)
    print_validation_report(problems)
    print_exception_report(exceptions, fired, exceptions_path)

    # ALWAYS persist -- before the FATAL check, so a hard-failing run's
    # findings survive for the reader instead of being printed and dropped
    # (the F2_SPEC §3.3 bug: E1 only wrote them when the override flag
    # happened to be passed).
    write_validation_problems(conn, problems, run_date, stage="metadata")

    fatal_problems = [p for p in problems if p.severity == "FATAL"]
    if fatal_problems:
        print(
            f"\n{len(fatal_problems)} FATAL problem(s) on check(s) "
            f"{sorted({p.check for p in fatal_problems})}. Refusing to write filings. "
            f"Every problem (including these) is in universe_validation_problems for "
            f"run_date={run_date.isoformat()}, stage=metadata. A new FATAL means either "
            f"the data is wrong or the check is wrong -- fix one of them, or add an "
            f"evidenced per-(cik, check) row to {exceptions_path}. There is no blanket "
            f"override."
        )
        for p in fatal_problems:
            print(f"    FATAL: {p}")
        sys.exit(1)

    # -- Main ingestion loop --------------------------------------------------
    total_by_form: dict[str, int] = {}
    # F2_SPEC §4.4 accounting: every earnings 8-K is either a recorded
    # selection or a counted failure. Nothing falls between them.
    earnings_8k_total = 0
    earnings_8ks_by_sector: dict[str, int] = {}
    earnings_failures: list[dict] = []
    ex99_selections: list[dict] = []
    # S6 manual-read fix package (F2_PROGRESS §5, 2026-08-24):
    earnings_exclusions: list[dict] = []          # evidenced `exclude` overrides
    override_fired: set[str] = set()
    press_release_outside_ex99: list[dict] = []   # P3
    selected_documents: list[dict] = []           # feeds the P5/P6 screen
    # F2_SPEC §4.5: filled from the same submissions dicts, 0 extra GETs.
    all_distress_events: list[dict] = []
    # F2_SPEC §4.2's binding condition: the ingested corpus is deliberately
    # WIDER than the universe (a member at date t needs pre-t filings), so the
    # run must state how many ingested filings fall outside every membership
    # spell of their own CIK. Nobody downstream may read "in the corpus" as
    # "in the universe"; F5 joins on universe_membership.
    spell_intervals = _spell_intervals(spells)
    filings_outside_membership = 0
    # Co-registrant filings: one accession, two member CIKs (main session
    # ruling 2026-08-24 -- side-table, not a re-key). See
    # coregistrant_problems() and the co_registrant_filings DDL.
    accession_owner: dict[str, int] = {}
    shared_accessions: dict[tuple[int, int], list[str]] = {}
    co_registrant_rows: list[dict] = []

    filing_cols_with_exhibit = """
        accession_number, cik, ticker, form, filing_date, report_date,
        acceptance_datetime, primary_document, items, has_earnings_item,
        ex99_1_document, exhibit_lookup_done, earnings_doc_filename,
        earnings_doc_relative_path, earnings_doc_section_type,
        earnings_doc_selection_confidence
    """
    upsert_with_exhibit_sql = f"""
        INSERT INTO filings ({filing_cols_with_exhibit})
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(accession_number) DO UPDATE SET
            filing_date=excluded.filing_date,
            report_date=excluded.report_date,
            acceptance_datetime=excluded.acceptance_datetime,
            primary_document=excluded.primary_document,
            items=excluded.items,
            has_earnings_item=excluded.has_earnings_item,
            ex99_1_document=excluded.ex99_1_document,
            exhibit_lookup_done=excluded.exhibit_lookup_done,
            earnings_doc_filename=excluded.earnings_doc_filename,
            earnings_doc_relative_path=excluded.earnings_doc_relative_path,
            earnings_doc_section_type=excluded.earnings_doc_section_type,
            earnings_doc_selection_confidence=excluded.earnings_doc_selection_confidence
    """
    # A4 fix: when exhibit lookup wasn't attempted THIS run (not an
    # earnings-item 8-K, or the index-page parse failed this run), the
    # exhibit/earnings-doc columns are simply not mentioned in the UPDATE
    # SET clause -- any previously-stored value (or lack thereof) is left
    # untouched, rather than relying on a COALESCE that can never clear a
    # stale value even when a fresh resolution correctly determines "no
    # exhibit". (Plain assignment above -- not COALESCE -- is what lets a
    # fresh "confirmed no exhibit" NULL actually overwrite a stale value
    # when lookup WAS attempted and completed this run.)
    filing_cols_no_exhibit = """
        accession_number, cik, ticker, form, filing_date, report_date,
        acceptance_datetime, primary_document, items, has_earnings_item
    """
    upsert_no_exhibit_sql = f"""
        INSERT INTO filings ({filing_cols_no_exhibit})
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(accession_number) DO UPDATE SET
            filing_date=excluded.filing_date,
            report_date=excluded.report_date,
            acceptance_datetime=excluded.acceptance_datetime,
            primary_document=excluded.primary_document,
            items=excluded.items,
            has_earnings_item=excluded.has_earnings_item
    """

    observed_max_filing_date: Optional[date] = None

    # CIK-ASCENDING, explicitly. load_universe() already returns rows in this
    # order, but sorting here makes the co-registrant keeper rule ("the
    # lowest member CIK keeps the `filings` row") a property of this loop
    # rather than of its caller's happening to be sorted.
    for _, row in universe.sort_values("cik").iterrows():
        cik = int(row["cik"])
        who = f"CIK {cik}"
        co_start = len(co_registrant_rows)
        upsert_company(conn, row)

        # SHARED enumeration window, not this member's coverage window -- see
        # the CORPUS_WINDOW_START comment block. The pagination cutoff must be
        # the same floor, or filings.files[] chunks older than a late entrant's
        # coverage_start would never be pulled and the floor would be
        # unreachable by construction.
        effective_recent = client.get_effective_recent(
            cik, CORPUS_WINDOW_START, force=force_refresh, max_age_hours=max_age_hours,
        )
        filings = extract_target_filings(
            effective_recent, CORPUS_WINDOW_START, CORPUS_WINDOW_END
        )

        # Distress events come out of the SAME dict -- zero extra GETs -- and
        # over the same window: a delisting or bankruptcy happens AFTER a
        # company leaves the universe, so clipping to membership would hide
        # precisely the events EXPANSION_PLAN §2c makes mandatory.
        distress = extract_distress_events(
            effective_recent, cik, CORPUS_WINDOW_START, CORPUS_WINDOW_END
        )
        write_distress_events(conn, distress)
        all_distress_events.extend(distress)

        intervals = spell_intervals.get(cik, [])

        for f in filings:
            exhibit_attempted_and_resolved = False
            resolution = None

            # KEEPER RULE (deterministic, ruled 2026-08-24): the `filings` row
            # for a co-registered accession is kept under the numerically
            # LOWEST member CIK on it. Guaranteed by construction, not by
            # luck -- the loop above iterates the universe CIK-ascending, so
            # the first writer of any accession is its lowest member CIK, and
            # the upsert never rewrites `cik`. Every dropped attribution is
            # recorded in co_registrant_filings; nothing is silently lost.
            prior_owner = accession_owner.setdefault(f["accession_number"], cik)
            if prior_owner != cik:
                shared_accessions.setdefault((prior_owner, cik), []).append(
                    f["accession_number"]
                )
                co_registrant_rows.append({
                    "accession_number": f["accession_number"],
                    "kept_cik": prior_owner, "co_cik": cik,
                    "form": f["form"], "filing_date": f["filing_date"],
                })

            if f["form"] == "8-K" and f["has_earnings_item"]:
                earnings_8k_total += 1
                earnings_8ks_by_sector[row["sector"]] = (
                    earnings_8ks_by_sector.get(row["sector"], 0) + 1
                )
                accession = f["accession_number"]
                override = overrides.get(accession)
                try:
                    docs, resolution = resolve_earnings_document(
                        client, cik, accession, f["primary_document"],
                        subject=who, filing_date=f["filing_date"],
                    )
                    if override is not None:
                        # An evidenced per-accession override REPLACES the
                        # policy's judgment for this one filing. It raises if
                        # it is stale, rather than resolving to nothing.
                        resolution = apply_earnings_doc_override(override, docs)
                        override_fired.add(accession)
                    write_filing_documents(conn, accession, docs)
                    exhibit_attempted_and_resolved = True
                except Exception as e:  # noqa: BLE001 -- log and continue, don't kill the whole run
                    print(f"  WARN: exhibit lookup failed for {who} {accession}: {e}")
                    earnings_failures.append({
                        "cik": cik, "accession_number": accession,
                        "reason": f"{type(e).__name__}: {e}",
                    })
                    docs = []

                # P3: a row DESCRIBED as a press release, typed outside the
                # EX-99 family, that we did not pick. Never an auto-pick --
                # the override file is the resolution path.
                if docs and override is None:
                    for miss in press_release_typed_outside_ex99(
                        docs, resolution["filename"] if resolution else None
                    ):
                        press_release_outside_ex99.append({
                            "cik": cik, "accession_number": accession,
                            "doc_type": miss["doc_type"],
                            "description": miss["description"],
                            "filename": miss["filename"],
                            "selected": resolution["filename"] if resolution else None,
                        })

                if exhibit_attempted_and_resolved and resolution is None:
                    if override is not None and override.excludes:
                        # An EVIDENCED exclusion, not a failure: this filing
                        # genuinely holds no earnings document. Counted in the
                        # audit and named at INFO -- never a silent NULL, and
                        # deliberately NOT in the earnings_doc_unresolved rate,
                        # which measures the policy failing, not a human ruling.
                        earnings_exclusions.append({
                            "cik": cik, "accession_number": accession,
                            "filing_date": f["filing_date"], "reason": override.reason,
                        })
                        # An evidenced exclusion is not an earnings 8-K the
                        # policy had to resolve, so it leaves the sector-
                        # coverage denominator: otherwise a sector could FATAL
                        # for "zero high-confidence picks" on filings a human
                        # ruled contain nothing to pick.
                        earnings_8ks_by_sector[row["sector"]] -= 1
                        ex99_selections.append({
                            "cik": cik, "section_type": EXCLUDED_SECTION_TYPE,
                            "selection_confidence": "override",
                            "filing_date": f["filing_date"],
                        })
                    else:
                        # Index parsed, but the policy found neither an EX-99.x
                        # nor a primary document to fall back on. A real hole.
                        earnings_failures.append({
                            "cik": cik, "accession_number": accession,
                            "reason": "selection policy returned no document",
                        })
                elif resolution is not None:
                    ex99_selections.append({
                        "cik": cik,
                        "section_type": resolution["section_type"],
                        "selection_confidence": resolution["selection_confidence"],
                        "filing_date": f["filing_date"],
                    })
                    selected_documents.append({
                        "cik": cik, "accession_number": accession,
                        "filename": resolution["filename"],
                        "relative_path": resolution["relative_path"],
                        "selection_confidence": resolution["selection_confidence"],
                    })

            if exhibit_attempted_and_resolved:
                ex99_doc = resolution["filename"] if resolution and resolution["is_exhibit"] else None
                conn.execute(
                    upsert_with_exhibit_sql,
                    (
                        f["accession_number"], cik, None, f["form"], f["filing_date"],
                        f["report_date"], f["acceptance_datetime"], f["primary_document"],
                        f["items"], f["has_earnings_item"],
                        ex99_doc, 1,
                        resolution["filename"] if resolution else None,
                        resolution["relative_path"] if resolution else None,
                        resolution["section_type"] if resolution else None,
                        resolution["selection_confidence"] if resolution else None,
                    ),
                )
            else:
                conn.execute(
                    upsert_no_exhibit_sql,
                    (
                        f["accession_number"], cik, None, f["form"], f["filing_date"],
                        f["report_date"], f["acceptance_datetime"], f["primary_document"],
                        f["items"], f["has_earnings_item"],
                    ),
                )
            total_by_form[f["form"]] = total_by_form.get(f["form"], 0) + 1
            fd = date.fromisoformat(f["filing_date"])
            if observed_max_filing_date is None or fd > observed_max_filing_date:
                observed_max_filing_date = fd
            if not _inside_any_spell(intervals, fd):
                filings_outside_membership += 1

        write_co_registrant_filings(conn, co_registrant_rows[co_start:])
        conn.commit()
        print(
            f"  {who} ({row['name']}): {len(filings)} filings in "
            f"{CORPUS_WINDOW_START.isoformat()}..{CORPUS_WINDOW_END.isoformat()} "
            f"(member window {row['coverage_start'].isoformat()}.."
            f"{row['coverage_end'].isoformat()})"
            + (f", {len(distress)} distress event(s)" if distress else "")
        )

    # -- Post-ingestion accounting (F2_SPEC §4.4) -----------------------------
    # These checks are about the loop's OUTPUT, so they can only run now. The
    # rows ARE written; a FATAL here means "go read the audit", not "nothing
    # happened" -- and re-running is cheap and idempotent either way.
    # P5 + P6: one pass over the CACHED selected documents (0 GETs). On a first
    # run, before `--stage documents`, most are uncached and are reported as
    # unmeasured rather than as clean.
    thin_problems, release_language_by_cik = screen_selected_documents(
        client, selected_documents
    )

    audit = build_ex99_audit(
        ex99_selections, universe, load_e1_ciks(),
        release_language_by_cik=release_language_by_cik,
    )
    write_ex99_audit(audit, ex99_audit_path)
    post_problems = earnings_doc_unresolved_problems(earnings_failures, earnings_8k_total)
    post_problems += check_ex99_sector_coverage(
        audit, universe, earnings_8ks_by_sector
    )
    post_problems += coregistrant_problems(shared_accessions)
    post_problems += earnings_doc_excluded_problems(earnings_exclusions)
    post_problems += press_release_outside_ex99_problems(press_release_outside_ex99)
    post_problems += thin_problems
    post_problems += release_language_problems(release_language_by_cik, universe)
    post_problems += deck_shaped_problems(release_language_by_cik, universe)
    print_ex99_audit_report(
        audit, earnings_failures, earnings_8k_total, ex99_audit_path,
        exclusions=earnings_exclusions,
        release_language_by_cik=release_language_by_cik,
    )
    print_earnings_doc_override_report(overrides, override_fired, overrides_path)

    # Rewrite the (run_date, stage=metadata) slice with pre- AND post-ingestion
    # findings together. write_validation_problems() deletes that slice first,
    # so this must be one combined write, not a second append.
    write_validation_problems(conn, problems + post_problems, run_date, stage="metadata")
    conn.commit()

    print(f"\nDone. Filings by form type: {total_by_form}")
    n_shared = sum(len(v) for v in shared_accessions.values())
    if n_shared:
        print(
            f"Co-registrant filings: {n_shared} accession(s) were enumerated for "
            f"TWO member CIKs each, across {len(shared_accessions)} pair(s). "
            f"`filings` is keyed on accession_number, so the table holds "
            f"{sum(total_by_form.values()) - n_shared} rows for "
            f"{sum(total_by_form.values())} enumerated filings. The dropped "
            f"attributions are stored in `co_registrant_filings` "
            f"({len(co_registrant_rows)} row(s), keeper = the lowest member "
            f"CIK) and summarised as `co_registrant_filing` WARNs -- never a "
            f"silent drop. Absence from `filings` alone is NOT evidence a "
            f"company did not file: consult filings UNION "
            f"co_registrant_filings."
        )
    print("\ndistress_events (F2_SPEC §4.5, zero extra network requests):")
    print(summarize_distress_events(all_distress_events))
    # F2_SPEC §4.2's binding condition, stated every run.
    total_filings = sum(total_by_form.values())
    print(
        f"\nIngested filings outside EVERY membership spell of their own CIK: "
        f"{filings_outside_membership} of {total_filings}. This is BY DESIGN "
        f"(full-window ingestion, no spell clipping -- a member at date t needs "
        f"pre-t filings for trailing features). It also means `present in "
        f"filings` is NOT `in the universe`: F5 must join on "
        f"universe_membership."
    )
    # F2_SPEC §2: report the OBSERVED max filing_date next to the fixed freeze
    # date, so the gap between them is visible rather than assumed to be zero.
    print(
        f"Corpus freeze date (constant): {CORPUS_WINDOW_END.isoformat()}; "
        f"observed max filing_date this run: "
        f"{observed_max_filing_date.isoformat() if observed_max_filing_date else 'n/a'}"
    )

    post_fatals = [p for p in post_problems if p.severity == "FATAL"]
    if post_fatals:
        print(
            f"\n{len(post_fatals)} POST-INGESTION FATAL problem(s) on check(s) "
            f"{sorted({p.check for p in post_fatals})}. The filings rows ARE "
            f"written (these checks are about the output, so they run last); the "
            f"run still fails because the corpus is not fit to consume as-is. "
            f"Every problem is in universe_validation_problems for "
            f"run_date={run_date.isoformat()}, stage=metadata."
        )
        for p in post_fatals:
            print(f"    FATAL: {p}")
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force-refresh", action="store_true",
        help="Ignore submissions cache staleness and re-fetch from EDGAR for every company.",
    )
    parser.add_argument(
        "--db", default=str(DB_PATH),
        help=(
            f"SQLite database to write (default: {DB_PATH.name}, the E2 database). "
            f"{E1_DB_PATH.name} is E1's frozen record and is refused."
        ),
    )
    parser.add_argument(
        "--validation-exceptions", default=str(VALIDATION_EXCEPTIONS_PATH),
        help=(
            "Evidenced per-(cik, check) FATAL->WARN exceptions file (default: "
            f"{VALIDATION_EXCEPTIONS_PATH}). This REPLACES the deleted "
            "--allow-incomplete-universe flag, which downgraded a check for the "
            "whole run; with 244 companies that would disarm a check for 243 "
            "innocent members to accept one known-OK finding. Every row needs "
            "written evidence, every row is printed whether it fires or not, and a "
            "dated row is refused unless its evidence predates the date it bites. "
            "Expected contents: empty."
        ),
    )
    parser.add_argument(
        "--stage", choices=list(STAGES), default=DEFAULT_STAGE,
        help=(
            f"Which segment to run (default: {DEFAULT_STAGE}). `metadata` "
            "enumerates, validates and writes the DB rows -- no filing text. "
            "`documents` downloads every 10-K/10-Q primary document and every "
            "resolved earnings-exhibit document into data/raw/documents/ and "
            "parses nothing, so extract.py later runs at 0 GETs; that is a "
            "~20,553-request / ~26 GB walk, which is exactly why it is opt-in "
            "and not the default. `all` runs both in order."
        ),
    )
    parser.add_argument(
        "--cache-max-age-hours", type=float, default=DEFAULT_MAX_AGE_HOURS,
        help=(
            f"TTL for the submissions cache on this run (default: "
            f"{DEFAULT_MAX_AGE_HOURS:g} h, unchanged from E1). Raise it to "
            "re-run a campaign days later without re-paying ~1.2 GB / ~10 min "
            "of submissions fetches -- at the cost of accepting the corpus as "
            "of the cached fetch, which is sound precisely because the corpus "
            "window is FIXED (F2_SPEC §2/§4.3). The filing_index/ and "
            "documents/ caches are cache-forever and unaffected."
        ),
    )
    args = parser.parse_args()
    run(
        force_refresh=args.force_refresh,
        db_path=Path(args.db),
        exceptions_path=Path(args.validation_exceptions),
        stage=args.stage,
        max_age_hours=args.cache_max_age_hours,
    )
