"""
ingest_prices.py -- E2 daily-price ingestion (F2 stage S5, `data/f2/F2_SPEC.md`
§6). Feeds the backtest target ratified 2026-08-18 (HANDOFF.md §3): forward
excess return vs. the universe average, aligned to filing dates.

WHAT THIS DOES
  1. Resolves a PRICE TICKER PER MEMBER CIK, CIK-verified (§6.1). The universe
     is the hybrid136 dated membership table (244 CIKs, read through
     `ingest_metadata.load_universe()`, checksum-verified on every load) -- it
     has no ticker column on purpose, because a member's ticker is not
     authoritative: 31 member CIKs carry no ticker at all in EDGAR's own
     submissions, and a dead member's former symbol is routinely REASSIGNED to
     an unrelated company (F1's finding: `APC` now maps to CIK 2080921 "ARKO
     Petroleum Corp.", not Anadarko's 773910; `EMC` is absent from the bulk map
     entirely). Mapping a dead member by its former symbol would silently fetch
     a different company's price history into this pipeline. So the ONLY
     admissible source of a member's ticker is EDGAR's own CIK-keyed
     `submissions.json`, plus the evidenced overrides in
     `data/f2/price_ticker_overrides.csv` -- today exactly two, both ratified
     and both printed on every run: CIK 34088 -> XOM (successor-CIK
     reorganisation) and CIK 4904 -> AEP (a 2026-08-24 upstream wobble in
     which EDGAR's submissions for a listed, actively-filing mega-cap dropped
     to empty tickers[] while SEC's own bulk map still mapped AEP -> 4904).
     Wobbles of that shape are WARNed on every run and NEVER auto-resolved.
  2. Counts and NAMES every member it cannot resolve (§6.3). A censored CIK is
     not a price failure -- it is a counted, reported exclusion that must
     accompany every E2 result (EXPANSION_PLAN §2c). The map is written to
     `data/f2/price_ticker_map.csv` and reconciled against F1's
     `price_censoring_census.parquet` with a PRE-REGISTERED expected delta; any
     other delta is reported as a finding, never reconciled away.
  3. Fetches full available daily-OHLCV history per resolved ticker via
     `price_client.PriceClient` (`--price-source`, default `yahoo`; see §5
     below and `data/PRICES_NOTES.md` §1).
  4. Writes `data/prices_e2.parquet`: one row per (cik, trading day), columns
     cik, ticker, date, open, high, low, close, volume, source, fetched_at.
     **`cik` is the join key downstream, never `ticker`.** E1's
     `data/prices.parquet` is its frozen record and is never written here.
  5. Runs a validation pass over each member's OWN coverage window and prints a
     loud INFO/WARN/FATAL report, in the same spirit as
     `ingest_metadata.validate_universe()`.

PRICE SOURCE (F2_SPEC §6.4, build-level ruling §9.1 item 8 -- flagged for
owner VISIBILITY because the 2026-08-18 target ratification named Stooq by
example): Stooq has been bot-gated site-wide since 2026-08-18 (JS
proof-of-work + `robots.txt: Disallow: /`), so attempting it 213 times to fail
213 times is both wasteful and impolite. `--price-source` therefore defaults to
`yahoo`; the Stooq path is fully intact and one flag away (`--price-source
stooq-first`). Yahoo's own robots.txt caveat is unchanged and documented in
`data/PRICES_NOTES.md` §1.

ADJUSTMENT SEMANTICS (unchanged from E1; see `data/PRICES_NOTES.md`): both
sources' OHLC series are SPLIT-ADJUSTED but NOT DIVIDEND-ADJUSTED. Because the
target is an EXCESS return vs. the universe average, a universe-wide missing
dividend income effect largely nets out, but differences in dividend yield
ACROSS members do not -- a real, documented limitation, not silently assumed
away.

Point-in-time note: `date` here is the trading/quote date of the bar itself,
not a filing date -- this file has no opinion on filing dates. Full history is
stored deliberately; the "never look before the filing date" rule belongs to
the feature/backtest code that consumes this file.

NO Anthropic API calls anywhere in this file. No trading/order/execution logic
of any kind -- this is a read-only market-data ingestion script for research.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional, Sequence

import pandas as pd

from edgar_client import EdgarClient
from ingest_metadata import CORPUS_WINDOW_END, CORPUS_WINDOW_START, load_universe
from price_client import PriceClient, PriceFetchError

REPO_ROOT = Path(__file__).resolve().parent
OVERRIDES_CSV = REPO_ROOT / "data" / "f2" / "price_ticker_overrides.csv"
TICKER_MAP_CSV = REPO_ROOT / "data" / "f2" / "price_ticker_map.csv"
CENSUS_PARQUET = (
    REPO_ROOT / "data" / "universe_e2_candidates" / "price_censoring_census.parquet"
)
# E2 writes a NEW parquet. data/prices.parquet is E1's frozen record, exactly
# like data/labels.parquet and data/filings_metadata.db (F2_SPEC §1.4 spirit).
OUTPUT_PARQUET = REPO_ROOT / "data" / "prices_e2.parquet"
E1_OUTPUT_PARQUET = REPO_ROOT / "data" / "prices.parquet"

PARQUET_COLUMNS = [
    "cik", "ticker", "date", "open", "high", "low", "close", "volume",
    "source", "fetched_at",
]


@dataclass
class Issue:
    """One reported finding. `cik` is the identity that matters; `ticker` is a
    label (and is None for a run-scope finding)."""

    severity: str  # "FATAL" | "WARN" | "INFO"
    ticker: Optional[str]
    check: str
    message: str
    cik: Optional[int] = None

# ---------------------------------------------------------------------------
# CIK-verified ticker resolution (F2_SPEC §6.1)
# ---------------------------------------------------------------------------

# Preferreds / warrants / rights / units. `-A` and `-B` are deliberately NOT
# matched: they are share classes, not non-common instruments, which is what
# lets Berkshire resolve to BRK-B -- and Yahoo uses the same dash convention.
NON_COMMON = re.compile(r"-(P[A-Z]?|WT[A-Z]?|RI|U|W)$")

# Pinned expectations, MEASURED 2026-08-24 by running exactly this rule over
# all 244 members of the cached submissions (F2_SPEC §6.1/§6.3). These are not
# decoration: a deviation means EDGAR's identity data moved under us, which is
# a membership/identity change and must never be adopted silently. A deviation
# is reported as a FATAL finding in the validation report (non-zero exit) --
# the fetch still runs, because the fetched bars are still valid data and
# re-paying for them adds nothing.
# AMENDED 2026-08-24 (main session ruling, F2_PROGRESS.md §5): re-measured
# against the cache AFTER S6 segment 1's TTL refresh, at which point EDGAR's
# submissions.json for AEP (CIK 4904) dropped to empty tickers/exchanges. The
# rule-level split moved 212/32 -> 211/33; the second evidenced override (4904
# -> AEP) puts it back, so the FINAL PAIR IS UNCHANGED: 213 fetchable, 31
# censored (27 core / 4 extension). See `submissions_ticker_missing_but_bulk_has`
# below -- the wobble is surfaced on every run, never auto-resolved.
EXPECTED_RESOLVED = 211          # CIK-verified from submissions alone
EXPECTED_OVERRIDES_APPLIED = 2   # 34088 -> XOM, 4904 -> AEP
EXPECTED_FETCHABLE = 213
EXPECTED_CENSORED = 31
EXPECTED_CENSORED_BY_STRATUM = {"core": 27, "extension": 4}

# --- TWO CENSORING NUMBERS, NEVER CONFLATED (main session ruling 2026-08-24,
#     F2_PROGRESS.md §5, on segment 4's real run) ------------------------------
# The FETCH pair answers "did we get a symbol and ask for its series?":
#   213 fetched / 31 unfetchable (27 core / 4 extension).
# The OPERATIVE pair answers the only question an analysis cares about, "does
# this member have usable prices inside the window it was a member?":
#   32 with NO usable prices (28 core / 4 extension) = the 31 unfetchable PLUS
#   EA (CIK 712515), which resolved, fetched, and came back with 6 rows dated
#   2026-07-17..2026-08-10 -- all AFTER its 2015-07-02..2022-08-05 coverage
#   window, flatlined at the take-private price with volume 0, because Yahoo
#   purged the delisted name's history. That is EXPANSION_PLAN §2c's
#   outcome-censoring residual materialising for a core member.
# Every report line states WHICH pair it is quoting.
EXPECTED_FETCHED = 213
EXPECTED_UNFETCHABLE = 31
EXPECTED_NO_USABLE_PRICES = 32
EXPECTED_NO_USABLE_BY_STRATUM = {"core": 28, "extension": 4}
# MEASURED from data/prices_e2.parquet (1,960,738 rows / 213 CIKs, segment 4):
# EA is the ONLY fetched member with zero in-window rows -- the next smallest
# in-window count is 539. A second CIK appearing here is a finding to report by
# name, never a number to absorb.
EXPECTED_NO_COVERAGE_CIKS = {712515}

# The override file may only name a CIK that has been ratified as an override
# case. Adding one is a deliberate edit HERE plus an evidenced row there --
# never a row that appears in the CSV alone (same discipline as
# manual_exclusions.csv: membership/identity changes are evidenced or they do
# not happen).
RATIFIED_OVERRIDE_CIKS = {34088, 4904}

# --- THE TRAP SIGNATURE, AND THE ONLY WAY PAST IT (S7 finding B3, ruled
#     2026-08-24) -------------------------------------------------------------
# A symbol that bulk-maps to a CIK OTHER than the member's is the APC signature:
# `APC -> 2080921 "ARKO Petroleum Corp."` while Anadarko is 773910. It is ALSO
# the shape of the XOM override: `XOM -> 2115436 "ExxonMobil Holdings Corp"`
# while the member is 34088 (absent from the bulk map). The honest rule is NOT
# "the override is not the trap shape" -- it IS the trap shape. The rule is:
#
#   bulk-symbol-maps-elsewhere is the trap SIGNATURE. An override over it
#   requires (a) an explicit, code-ratified successor-reorg marker on the row,
#   (b) a series-continuity check against the fetched prices, and (c) a
#   standing per-run WARN. Absent any of the three, the member stays censored.
#
# Only these CIKs may carry `successor_reorg=true`. Adding one is a deliberate
# edit HERE plus an evidenced row + a passing continuity check -- exactly the
# discipline RATIFIED_OVERRIDE_CIKS applies to the override itself.
RATIFIED_SUCCESSOR_REORG_CIKS = {34088}

# Continuity floor for a successor-reorg override (§6.2 as amended). The
# failure mode being excluded is the reassigned-symbol / stub signature: EA's
# purged series is 6 rows; the smallest GENUINE series in this corpus is 604
# (a young registrant). 1,250 (~5 years of daily bars) sits far above a stub
# and far below any real long history. MEASURED for XOM: 14,282 rows.
SUCCESSOR_MIN_SERIES_ROWS = 1250
# The substantive arm: a successor symbol must carry the predecessor's history
# ACROSS the member's own coverage window, so its first bar may not post-date
# the window's opening by more than this (same grace as the
# `starts_after_coverage_start` WARN).
SUCCESSOR_REACH_GRACE_DAYS = 45

# Members that must NEVER be mapped to a symbol, even if one looks available.
# This is the F1 trap written down (F2_SPEC §6.2).
DELIBERATELY_CENSORED_CIKS = {
    29915: (
        "Dow Chemical Co /DE/ is deliberately censored, never mapped to DOW: "
        "today's DOW is Dow Inc (CIK 1751788), a 2019 spin-off whose price "
        "history does not contain Dow Chemical's pre-2019 series. MEASURED "
        "2026-08-24: CIK 29915's submissions carry an empty tickers[]; the "
        "bulk map resolves DOW to CIK 1751788 'DOW INC.'"
    ),
}

OVERRIDE_COLUMNS = ("cik", "ticker", "reason", "evidence", "added", "successor_reorg")
_TRUE_WORDS = {"true", "yes", "1"}
_FALSE_WORDS = {"false", "no", "0", ""}
# An override that cites no primary-source facts is not auditable. 80 chars is
# a floor against a one-word placeholder, not a quality bar.
MIN_OVERRIDE_EVIDENCE_CHARS = 80

# `status` is the OPERATIVE classification; `fetched` / `has_usable_prices` are
# the two pair memberships spelled out per row so neither number can be derived
# by accident from the other (2026-08-24 ruling).
TICKER_MAP_COLUMNS = [
    "cik", "name", "stratum", "chosen_ticker", "all_candidates", "status",
    "fetched", "has_usable_prices", "reason",
]

# Pre-registered census delta (F2_SPEC §6.3), stated here so an UNexpected one
# is visible rather than absorbed. F1's census counted `has_current_ticker`;
# E2's rule differs in exactly two documented places.
CENSUS_EXPECTED_RESOLVED_BY_E2 = {34088}   # F1 censored it; E2's override fetches it
CENSUS_EXPECTED_CENSORED_BY_E2 = {30554}   # EIDP: preferreds only (CTA-PA/CTA-PB)


@dataclass
class TickerOverride:
    cik: int
    ticker: str
    reason: str
    evidence: str
    added: str
    # True = this row knowingly overrides a symbol that bulk-maps to a DIFFERENT
    # CIK (the APC trap signature) on successor-reorganisation grounds. It is
    # REQUIRED for such a row, refused for any CIK not in
    # RATIFIED_SUCCESSOR_REORG_CIKS, and it costs the row a standing per-run
    # WARN plus a series-continuity check (S7 B3).
    successor_reorg: bool = False


def _parse_bool(raw: str, path: Path, line: int, column: str) -> bool:
    value = str(raw).strip().lower()
    if value in _TRUE_WORDS:
        return True
    if value in _FALSE_WORDS:
        return False
    raise ValueError(
        f"{path} line {line}: `{column}` must be true/false (got {raw!r})"
    )


def load_ticker_overrides(
    path: Path = OVERRIDES_CSV, bulk_map: Optional[dict[str, int]] = None
) -> dict[int, TickerOverride]:
    """Read `data/f2/price_ticker_overrides.csv` with load-time validation.

    Same discipline as `manual_exclusions.csv`: every row is
    primary-source-evidenced, and every row is printed in the run report
    whether or not it fires. A malformed, unevidenced, or unratified row RAISES
    -- a silently-accepted override row is exactly the failure this mechanism
    exists to prevent, because an override is the one place where a symbol
    enters the pipeline without CIK verification.

    Pass `bulk_map` to enforce the S7-B3 rule at load time: an override whose
    symbol maps to a DIFFERENT CIK in `company_tickers.json` carries the APC
    trap signature and is REFUSED unless the row declares `successor_reorg`
    (and that marker is itself code-ratified). `resolve_universe_tickers()`
    always enforces this, so no run can apply an unmarked one.

    A MISSING file raises too: absent overrides, XOM would be silently
    censored, and "silently" is the part that is unacceptable.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"{path} is missing. It is a required, versioned input (F2_SPEC "
            f"§6.2): without it CIK 34088 is censored, which is a real change "
            f"in the fetched universe and must not happen by a missing file."
        )
    df = pd.read_csv(path, dtype=str, keep_default_na=False, comment="#")
    missing = [c for c in OVERRIDE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing required column(s) {missing}")

    out: dict[int, TickerOverride] = {}
    for i, r in enumerate(df.to_dict("records"), start=2):  # +1 header, +1 1-based
        cik_raw = str(r["cik"]).strip()
        if not cik_raw:
            continue
        try:
            cik = int(cik_raw)
        except ValueError as exc:
            raise ValueError(f"{path} line {i}: cik {cik_raw!r} is not an integer") from exc
        ticker = str(r["ticker"]).strip().upper()
        reason = str(r["reason"]).strip()
        evidence = str(r["evidence"]).strip()
        added = str(r["added"]).strip()
        if cik in out:
            raise ValueError(f"{path} line {i}: duplicate row for cik {cik}")
        if cik not in RATIFIED_OVERRIDE_CIKS:
            raise ValueError(
                f"{path} line {i}: cik {cik} is not a ratified override case. "
                f"Ratified: {sorted(RATIFIED_OVERRIDE_CIKS)}. An override bypasses "
                f"CIK verification -- adding one takes a deliberate edit to "
                f"RATIFIED_OVERRIDE_CIKS in ingest_prices.py alongside the "
                f"evidenced row, not a new line in this CSV."
            )
        if cik in DELIBERATELY_CENSORED_CIKS:
            raise ValueError(
                f"{path} line {i}: cik {cik} is DELIBERATELY censored and may "
                f"never be overridden. {DELIBERATELY_CENSORED_CIKS[cik]}"
            )
        if not ticker or not reason:
            raise ValueError(
                f"{path} line {i} (cik {cik}): both `ticker` and `reason` are mandatory"
            )
        if len(evidence) < MIN_OVERRIDE_EVIDENCE_CHARS:
            raise ValueError(
                f"{path} line {i} (cik {cik}): `evidence` is mandatory and must "
                f"cite primary-source facts (got {len(evidence)} chars, need "
                f"{MIN_OVERRIDE_EVIDENCE_CHARS}). An override without written "
                f"evidence is not auditable and is refused."
            )
        if not added:
            raise ValueError(f"{path} line {i} (cik {cik}): `added` (a date) is mandatory")
        successor_reorg = _parse_bool(r["successor_reorg"], path, i, "successor_reorg")
        if successor_reorg and cik not in RATIFIED_SUCCESSOR_REORG_CIKS:
            raise ValueError(
                f"{path} line {i} (cik {cik}): `successor_reorg` is not ratified for "
                f"this CIK. Ratified: {sorted(RATIFIED_SUCCESSOR_REORG_CIKS)}. That "
                f"marker is what lets a row override a symbol carrying the APC trap "
                f"signature, so it takes a deliberate edit to "
                f"RATIFIED_SUCCESSOR_REORG_CIKS, not a word in a CSV."
            )
        out[cik] = TickerOverride(
            cik=cik, ticker=ticker, reason=reason, evidence=evidence, added=added,
            successor_reorg=successor_reorg,
        )
    if bulk_map is not None:
        validate_overrides_against_bulk_map(out, bulk_map, path=path)
    return out


def validate_overrides_against_bulk_map(
    overrides: dict[int, TickerOverride],
    bulk_map: dict[str, int],
    path: Path = OVERRIDES_CSV,
) -> None:
    """Refuse any override whose symbol bulk-maps to a DIFFERENT CIK unless the
    row declares (code-ratified) `successor_reorg` (S7 finding B3).

    This is the guard that was missing: overrides used to be applied whenever
    the rule censored a member, regardless of WHY it censored -- including a
    bulk-map contradiction, which is precisely the APC trap signature.
    """
    for cik, ov in sorted(overrides.items()):
        mapped = bulk_map.get(ov.ticker)
        if mapped is None or mapped == cik:
            continue
        if not ov.successor_reorg:
            raise ValueError(
                f"{path} (cik {cik}): override symbol {ov.ticker} bulk-maps to CIK "
                f"{mapped}, not {cik}. That is the APC trap SIGNATURE (APC -> "
                f"2080921 while Anadarko is 773910). Overriding it requires an "
                f"explicit `successor_reorg=true` marker, ratified in "
                f"RATIFIED_SUCCESSOR_REORG_CIKS, plus the series-continuity check "
                f"and the standing per-run WARN. Without the marker the member "
                f"stays censored."
            )


def load_bulk_ticker_map(client: EdgarClient, force: bool = False) -> dict[str, int]:
    """`company_tickers.json` as {TICKER: cik}. Used ONLY as a contradiction
    detector (§6.1): a ticker that maps to a different CIK censors the member;
    a ticker that is ABSENT from the file never censors anything. MEASURED
    2026-08-24 on the post-refresh cache: EA (CIK 712515) is simply absent, and
    requiring presence would censor a live large cap for an SEC file's gap.
    (Pre-refresh, AEP was absent here too; post-refresh the two SEC files swapped
    roles -- the bulk map gained AEP -> 4904 while AEP's own submissions lost the
    symbol. Neither file is authoritative on its own, which is exactly why the
    bulk map may only veto and the wobble gets a WARN.)
    """
    raw = client.get_company_tickers(force=force)
    return {str(rec["ticker"]).upper(): int(rec["cik_str"]) for rec in raw.values()}


def bulk_symbols_by_cik(bulk_map: dict[str, int]) -> dict[int, tuple[str, ...]]:
    """Reverse index of the bulk map: cik -> every symbol SEC maps to it."""
    out: dict[int, list[str]] = {}
    for ticker, cik in bulk_map.items():
        out.setdefault(cik, []).append(ticker)
    return {cik: tuple(sorted(v)) for cik, v in out.items()}


def resolve_ticker(
    submissions: dict, cik: int, bulk_map: dict[str, int]
) -> tuple[Optional[str], str, str]:
    """The §6.1 rule, exactly as written. Returns
    (chosen_ticker, status in {resolved, censored}, reason).

    Candidates come from EDGAR's own CIK-keyed submissions and nowhere else,
    in EDGAR's own ordering; non-common instruments are dropped; the bulk map
    can only VETO, never supply.
    """
    raw = [str(t).strip().upper() for t in (submissions.get("tickers") or []) if str(t).strip()]
    candidates = [t for t in raw if not NON_COMMON.search(t)]
    if not candidates:
        if raw:
            return None, "censored", (
                f"no common-share ticker in submissions (non-common only: {', '.join(raw)})"
            )
        return None, "censored", "submissions.json carries no ticker at all"
    chosen = candidates[0]
    mapped = bulk_map.get(chosen)
    if mapped is not None and mapped != cik:
        return None, "censored", (
            f"bulk-map contradiction: company_tickers.json maps {chosen} to CIK "
            f"{mapped}, not {cik} -- refusing to fetch another company's series"
        )
    if mapped is None:
        return chosen, "resolved", (
            "CIK-verified from submissions.json (absent from company_tickers.json; "
            "absence never censors)"
        )
    return chosen, "resolved", "CIK-verified from submissions.json"


@dataclass
class TickerResolution:
    cik: int
    name: str
    stratum: str
    chosen_ticker: Optional[str]
    all_candidates: str            # raw submissions tickers, comma-joined
    # OPERATIVE status: resolved | override | censored | resolved_no_coverage.
    # `resolved_no_coverage` is set only after the fetch, by
    # apply_no_coverage_status(): the member has a CIK-verified symbol and was
    # fetched, but the returned series has ZERO rows inside its own coverage
    # window, so it contributes nothing to any analysis.
    status: str
    reason: str
    coverage_start: Optional[date] = None
    coverage_end: Optional[date] = None
    is_current_member: bool = True
    # What the §6.1 rule said on its OWN, before any override or deliberate
    # censoring was applied, plus every symbol the bulk map maps to this CIK.
    # Kept so an AEP-shaped upstream wobble stays visible on every run even
    # after an evidenced override covers it (see ticker_wobble_issues()).
    rule_status: str = "resolved"   # resolved | censored
    bulk_symbols: tuple = ()
    # What company_tickers.json says the CHOSEN symbol belongs to (None = the
    # symbol is absent from the bulk map). A value that is neither None nor this
    # member's own cik is the APC trap signature -- see S7 B3 and
    # ticker_wobble_issues()'s second arm.
    chosen_bulk_cik: Optional[int] = None
    # The fetch-side classification, fixed at resolution time and NEVER mutated
    # (resolved | override | censored). `status` may later be refined to
    # `resolved_no_coverage`; keeping both is what lets the FETCH pair and the
    # OPERATIVE pair be reported as the two distinct facts they are.
    fetch_status: str = ""

    def __post_init__(self) -> None:
        if not self.fetch_status:
            self.fetch_status = self.status

    @property
    def fetched(self) -> bool:
        """FETCH pair: a symbol existed and its series was requested."""
        return self.fetch_status in ("resolved", "override")

    # Kept as the name the fetch path and validation use.
    fetchable = fetched

    @property
    def has_usable_prices(self) -> bool:
        """OPERATIVE pair: fetched AND the series actually covers the window
        this member was in the universe."""
        return self.fetched and self.status != "resolved_no_coverage"


def resolve_universe_tickers(
    client: EdgarClient,
    universe: pd.DataFrame,
    overrides: Optional[dict[int, TickerOverride]] = None,
    bulk_map: Optional[dict[str, int]] = None,
    force: bool = False,
) -> list[TickerResolution]:
    """One TickerResolution per member CIK, in CIK order. Reads the cached
    submissions (0 GETs when they are fresh from S6 segment 1).
    """
    if overrides is None:
        overrides = load_ticker_overrides()
    if bulk_map is None:
        bulk_map = load_bulk_ticker_map(client, force=force)
    # The S7-B3 guard, enforced on EVERY run regardless of how the overrides
    # were loaded: no unmarked override may sit on top of the trap signature.
    validate_overrides_against_bulk_map(overrides, bulk_map)

    by_cik = bulk_symbols_by_cik(bulk_map)
    out: list[TickerResolution] = []
    for row in universe.sort_values("cik").itertuples():
        cik = int(row.cik)
        subs = client.get_submissions(cik, force=force)
        raw = [str(t).strip().upper() for t in (subs.get("tickers") or []) if str(t).strip()]
        chosen, status, reason = resolve_ticker(subs, cik, bulk_map)
        rule_status = status

        if cik in DELIBERATELY_CENSORED_CIKS:
            # Belt and braces: even if EDGAR started publishing a symbol for
            # this CIK tomorrow, it is not the same traded security.
            chosen, status, reason = None, "censored", DELIBERATELY_CENSORED_CIKS[cik]
        elif cik in overrides:
            ov = overrides[cik]
            if status == "censored":
                chosen, status = ov.ticker, "override"
                mapped = bulk_map.get(ov.ticker)
                marker = (
                    f" [successor_reorg: {ov.ticker} bulk-maps to CIK {mapped}, "
                    f"the trap signature, overridden on reorganisation evidence + a "
                    f"series-continuity check + a standing WARN]"
                    if ov.successor_reorg
                    else ""
                )
                reason = f"evidenced override ({ov.reason}){marker}; {reason}"
            elif chosen != ov.ticker:
                reason = (
                    f"{reason}; NOTE override row wants {ov.ticker} but the CIK "
                    f"resolves to {chosen} on its own -- CIK verification wins"
                )
            else:
                reason = f"{reason}; override row for {ov.ticker} not needed"

        out.append(
            TickerResolution(
                cik=cik,
                name=str(row.name),
                stratum=str(row.stratum),
                chosen_ticker=chosen,
                all_candidates=",".join(raw),
                status=status,
                reason=reason,
                coverage_start=row.coverage_start,
                coverage_end=row.coverage_end,
                is_current_member=bool(row.is_current_member),
                rule_status=rule_status,
                bulk_symbols=by_cik.get(cik, ()),
                chosen_bulk_cik=bulk_map.get(chosen) if chosen else None,
            )
        )
    return out


def ticker_wobble_issues(
    resolutions: Sequence[TickerResolution],
    overrides: Optional[dict[int, TickerOverride]] = None,
) -> list[Issue]:
    """Two standing per-run WARNs about ticker identity. Both fire on every run;
    neither is ever auto-resolved.

    **Arm 1 -- `submissions_ticker_missing_but_bulk_has`** (ruled 2026-08-24):
    the member's submissions carry no admissible ticker while SEC's own bulk map
    maps some symbol to that SAME CIK.

    **Arm 2 -- `override_symbol_bulk_maps_elsewhere`** (S7 finding B3, ruled
    2026-08-24): an APPLIED override whose symbol bulk-maps to a DIFFERENT CIK.
    This arm exists because arm 1 skips a CIK with no bulk symbols of its own,
    and CIK 34088 has none -- so XOM, the one override actually carrying the trap
    signature, used to produce no WARN at all while AEP (where the bulk map
    AGREES with our CIK, the safe direction) warned every run. Exactly backwards;
    now both warn, each for its own real reason.

    This is the AEP shape: on 2026-08-24 EDGAR's submissions for CIK 4904
    dropped to empty tickers/exchanges while `company_tickers.json` still mapped
    AEP -> 4904 and AEP was a listed, actively-filing current member. The two
    SEC files disagreeing about a live company is an upstream wobble, and it
    must SURFACE on every run -- it is never auto-resolved, because
    auto-adopting a bulk-map symbol would re-open the APC trap from the other
    side. The only remedy is an evidenced override row, added by hand.

    The WARN distinguishes the two shapes it can catch: a bulk symbol that the
    rule COULD have used (admissible / common), and bulk symbols that are all
    non-common (EIDP's CTA-PA/CTA-PB), where censoring is the correct answer.
    """
    issues: list[Issue] = []
    for r in resolutions:
        if r.rule_status != "censored" or not r.bulk_symbols:
            continue
        admissible = [t for t in r.bulk_symbols if not NON_COMMON.search(t)]
        covered = (
            f"covered by the evidenced override -> {r.chosen_ticker}"
            if r.fetch_status == "override"
            else "NOT covered by an override -- this member is censored"
        )
        if admissible:
            detail = (
                f"bulk map offers admissible symbol(s) {', '.join(admissible)} for this "
                f"CIK -- an upstream wobble between two SEC files, not a resolution; "
                f"{covered}"
            )
        else:
            detail = (
                f"bulk map offers only non-common symbol(s) "
                f"{', '.join(r.bulk_symbols)} for this CIK, so censoring is correct; "
                f"{covered}"
            )
        issues.append(
            Issue(
                "WARN",
                None,
                "submissions_ticker_missing_but_bulk_has",
                f"{r.name}: submissions.json carries no admissible ticker "
                f"(tickers[]={r.all_candidates or 'empty'}) but {detail}",
                cik=r.cik,
            )
        )

    for r in resolutions:
        if r.fetch_status != "override":
            continue
        if r.chosen_bulk_cik is None or r.chosen_bulk_cik == r.cik:
            continue
        ov = (overrides or {}).get(r.cik)
        cited = (
            f" Evidence on file ({ov.reason}, added {ov.added}): "
            f"{ov.evidence[:240]}{'...' if len(ov.evidence) > 240 else ''}"
            if ov
            else f" Evidence: see {OVERRIDES_CSV.name}."
        )
        issues.append(
            Issue(
                "WARN",
                r.chosen_ticker,
                "override_symbol_bulk_maps_elsewhere",
                f"{r.name}: member CIK {r.cik} is fetched as {r.chosen_ticker}, but "
                f"company_tickers.json maps {r.chosen_ticker} to CIK "
                f"{r.chosen_bulk_cik}. That is the APC trap SIGNATURE -- the same "
                f"shape as APC -> 2080921 while Anadarko is 773910. It is permitted "
                f"here ONLY as a ratified successor-reorganisation override, with a "
                f"series-continuity check and this standing WARN."
                f"{cited}",
                cik=r.cik,
            )
        )
    return issues


def successor_continuity_issues(
    resolutions: Sequence[TickerResolution],
    prices: pd.DataFrame,
    overrides: Optional[dict[int, TickerOverride]] = None,
) -> list[Issue]:
    """Check the fetched series behind every successor-reorg override, and say
    what it measured either way (S7 finding B3, ruled 2026-08-24).

    A successor-CIK override claims the symbol still carries the SAME traded
    security across the member's history. That claim is checkable against the
    bars we just fetched, and until now nothing checked it -- the one fact that
    corroborates the XOM mapping (an unbroken series back to 1970) was neither
    cited nor verified.

    Two FATAL arms, both aimed at the reassigned-symbol / stub signature:

    - **reach**: the series must start no later than the member's own coverage
      window opens (+45 d grace). A reassigned symbol carries the NEW company's
      history and starts late -- ARKO's begins in 2020 while Anadarko was a
      member from 2016.
    - **length**: at least `SUCCESSOR_MIN_SERIES_ROWS` bars. EA's purged series
      is 6 rows; a stub must never pass as continuity.

    On success it emits an INFO stating rows / span / largest gap, so the run
    report carries the corroborating measurement instead of asserting it.
    """
    issues: list[Issue] = []
    overrides = overrides or {}
    for r in resolutions:
        ov = overrides.get(r.cik)
        if r.fetch_status != "override" or ov is None or not ov.successor_reorg:
            continue
        tdf = prices[prices["cik"] == r.cik].sort_values("date")
        if tdf.empty:
            issues.append(
                Issue("FATAL", r.chosen_ticker, "successor_series_missing",
                      f"{r.name}: successor-reorg override fetched no rows at all -- "
                      f"the continuity claim is unverifiable", cik=r.cik)
            )
            continue
        first, last = tdf["date"].min(), tdf["date"].max()
        window_start = r.coverage_start or CORPUS_WINDOW_START
        late_days = (first - window_start).days
        days = [d for d in tdf["date"]]
        max_gap = max((b - a).days for a, b in zip(days, days[1:])) if len(days) > 1 else 0
        measured = (
            f"{len(tdf)} rows {first}..{last}, largest gap {max_gap} calendar days"
        )
        if len(tdf) < SUCCESSOR_MIN_SERIES_ROWS:
            issues.append(
                Issue("FATAL", r.chosen_ticker, "successor_series_too_short",
                      f"{r.name}: successor-reorg override has only {len(tdf)} rows "
                      f"(floor {SUCCESSOR_MIN_SERIES_ROWS}) -- the short-history "
                      f"signature of a REASSIGNED symbol, not a continuous security. "
                      f"Measured: {measured}", cik=r.cik)
            )
        elif late_days > SUCCESSOR_REACH_GRACE_DAYS:
            issues.append(
                Issue("FATAL", r.chosen_ticker, "successor_series_starts_late",
                      f"{r.name}: successor-reorg override's first bar {first} is "
                      f"{late_days} days after its coverage window opens "
                      f"({window_start}) -- the series does not carry the "
                      f"predecessor's history. Measured: {measured}", cik=r.cik)
            )
        else:
            issues.append(
                Issue("INFO", r.chosen_ticker, "successor_series_continuous",
                      f"{r.name}: continuity check PASSED for the successor-reorg "
                      f"override -- {measured}, reaching back "
                      f"{-late_days} days before its coverage window opens "
                      f"({window_start})", cik=r.cik)
            )
    return issues


def apply_no_coverage_status(
    resolutions: Sequence[TickerResolution],
    prices: pd.DataFrame,
    window_start: date = CORPUS_WINDOW_START,
    window_end: date = CORPUS_WINDOW_END,
) -> list[TickerResolution]:
    """Refine `status` to `resolved_no_coverage` for every FETCHED member whose
    series has zero rows inside its own coverage window, and return them.

    Ruled by the main session 2026-08-24 (F2_PROGRESS.md §5) on segment 4's real
    run. The case that forced it: **EA (CIK 712515)**, a core/tech member
    2017-07 -> 2021-07, resolved to `EA` and fetched fine -- but Yahoo returned
    6 rows dated 2026-07-17..2026-08-10, flatlined at the ~$209.70 take-private
    price with volume 0 and `meta.firstTradeDate` reset to 2026-07-17. It is the
    right company (Yahoo's `longName` confirms Electronic Arts); Yahoo simply
    purged the delisted name's history. So the member is fetched and yet
    contributes nothing to any analysis -- EXPANSION_PLAN §2c's outcome-
    censoring residual, made concrete.

    Such a member KEEPS its fetch record (it stays in the FETCH pair and its
    rows stay in the parquet) and joins the OPERATIVE no-usable-prices
    accounting. The two numbers are reported separately, never merged.
    """
    flipped: list[TickerResolution] = []
    for r in resolutions:
        if not r.fetched:
            continue
        start = max(window_start, r.coverage_start or window_start)
        end = min(window_end, r.coverage_end or window_end)
        tdf = prices[prices["cik"] == r.cik]
        in_window = tdf[(tdf["date"] >= start) & (tdf["date"] <= end)]
        if len(in_window) > 0:
            continue
        span = (
            f"{tdf['date'].min()}..{tdf['date'].max()}" if len(tdf) else "no rows at all"
        )
        r.status = "resolved_no_coverage"
        r.reason = (
            f"{r.reason}; FETCHED as {r.chosen_ticker} but 0 of {len(tdf)} rows fall "
            f"inside its coverage window [{start}, {end}] (series spans {span}) -- "
            f"no usable prices, counted in the OPERATIVE censoring pair"
        )
        flipped.append(r)
    return flipped


def distress_events_for(cik: int, db_path: Path) -> list[tuple]:
    """Read-only lookup of a CIK's EDGAR-native distress events (Form 25 /
    Form 15 / 8-K item 1.03) from S3's `distress_events` table. Opened
    `mode=ro`: this module never writes the metadata DB.
    """
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = con.execute(
            "SELECT form, filing_date, event_kind, accession_number "
            "FROM distress_events WHERE cik = ? ORDER BY filing_date",
            (cik,),
        ).fetchall()
    finally:
        con.close()
    return rows


def no_coverage_distress_issues(
    resolutions: Sequence[TickerResolution], db_path: Optional[Path]
) -> list[Issue]:
    """Cross-reference every `resolved_no_coverage` member against
    `distress_events` (EXPANSION_PLAN §2c's visibility mechanism, built for
    exactly this case): if a member's prices vanished because it was taken
    private or delisted, EDGAR's own Form 25 / Form 15 must say so, and the
    report cites those rows. A no-coverage member with NO distress events is a
    WARN -- it means the price gap has no EDGAR-side explanation and needs a
    human look, not an assumption.
    """
    issues: list[Issue] = []
    if db_path is None:
        return issues
    no_coverage = [r for r in resolutions if r.status == "resolved_no_coverage"]
    if not no_coverage:
        return issues
    if not Path(db_path).exists():
        return [
            Issue("WARN", None, "distress_crosscheck_unavailable",
                  f"{db_path} not found -- could not confirm the §2c distress-event "
                  f"visibility for {len(no_coverage)} no-coverage member(s)")
        ]
    for r in no_coverage:
        try:
            rows = distress_events_for(r.cik, Path(db_path))
        except sqlite3.Error as exc:  # locked / mid-write / schema not there yet
            issues.append(
                Issue("WARN", r.chosen_ticker, "distress_crosscheck_unavailable",
                      f"could not read distress_events ({exc})", cik=r.cik)
            )
            continue
        if rows:
            cited = "; ".join(f"{f} {d} [{k}] {a}" for f, d, k, a in rows)
            issues.append(
                Issue("INFO", r.chosen_ticker, "no_coverage_explained_by_distress_events",
                      f"{r.name}: no usable prices, and EDGAR says why -- {cited}",
                      cik=r.cik)
            )
        else:
            issues.append(
                Issue("WARN", r.chosen_ticker, "no_coverage_without_distress_events",
                      f"{r.name}: fetched but zero in-window prices, and NO Form 25 / "
                      f"Form 15 / item 1.03 rows explain it -- look before assuming a "
                      f"delisting", cik=r.cik)
            )
    return issues


def ticker_map_frame(resolutions: Sequence[TickerResolution]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "cik": r.cik,
                "name": r.name,
                "stratum": r.stratum,
                "chosen_ticker": r.chosen_ticker or "",
                "all_candidates": r.all_candidates,
                "status": r.status,
                "fetched": r.fetched,
                "has_usable_prices": r.has_usable_prices,
                "reason": r.reason,
            }
            for r in resolutions
        ],
        columns=TICKER_MAP_COLUMNS,
    )


def write_ticker_map(
    resolutions: Sequence[TickerResolution], path: Path = TICKER_MAP_CSV
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    ticker_map_frame(resolutions).to_csv(path, index=False)
    return path


# ---------------------------------------------------------------------------
# Census reconciliation (F2_SPEC §6.3)
# ---------------------------------------------------------------------------


@dataclass
class CensusDiff:
    f1_censored: set[int]
    e2_censored: set[int]
    expected_resolved_by_e2: set[int]     # F1 censored, E2 fetches -- pre-registered
    expected_censored_by_e2: set[int]     # F1 resolvable, E2 censors -- pre-registered
    unexpected_resolved_by_e2: set[int]
    unexpected_censored_by_e2: set[int]
    census_ciks_not_in_universe: set[int]

    @property
    def clean(self) -> bool:
        return not (self.unexpected_resolved_by_e2 or self.unexpected_censored_by_e2)


def reconcile_censoring_census(
    resolutions: Sequence[TickerResolution], census_path: Path = CENSUS_PARQUET
) -> CensusDiff:
    """Re-derive the censoring census from THIS run's resolution and diff it
    against F1's `price_censoring_census.parquet`.

    F1's census asked `has_current_ticker`; E2 asks the stricter §6.1 question.
    The two differ in exactly two pre-registered places (XOM overridden in,
    EIDP censored out). Anything else is a finding and is REPORTED, not
    reconciled away -- the caller turns it into a FATAL issue.
    """
    census = pd.read_parquet(census_path)
    universe_ciks = {r.cik for r in resolutions}
    census_ciks = {int(c) for c in census["cik"]}
    in_universe = census[census["cik"].isin(universe_ciks)]
    f1_censored = {int(c) for c in in_universe.loc[~in_universe["has_current_ticker"], "cik"]}
    e2_censored = {r.cik for r in resolutions if not r.fetchable}

    resolved_by_e2 = f1_censored - e2_censored
    censored_by_e2 = e2_censored - f1_censored
    return CensusDiff(
        f1_censored=f1_censored,
        e2_censored=e2_censored,
        expected_resolved_by_e2=resolved_by_e2 & CENSUS_EXPECTED_RESOLVED_BY_E2,
        expected_censored_by_e2=censored_by_e2 & CENSUS_EXPECTED_CENSORED_BY_E2,
        unexpected_resolved_by_e2=resolved_by_e2 - CENSUS_EXPECTED_RESOLVED_BY_E2,
        unexpected_censored_by_e2=censored_by_e2 - CENSUS_EXPECTED_CENSORED_BY_E2,
        census_ciks_not_in_universe=census_ciks - universe_ciks,
    )


def resolution_counts(resolutions: Sequence[TickerResolution]) -> dict[str, int]:
    """Both pairs, under names that cannot be mistaken for each other.

    FETCH pair      -> `fetched` / `unfetchable` (+ `censored_{stratum}`)
    OPERATIVE pair  -> `no_usable_prices` (+ `no_usable_prices_{stratum}`)

    `resolved` / `override` / `censored` count the FETCH-side classification and
    are therefore stable across `apply_no_coverage_status()`.
    """
    counts = {
        "members": len(resolutions),
        "resolved": sum(1 for r in resolutions if r.fetch_status == "resolved"),
        "override": sum(1 for r in resolutions if r.fetch_status == "override"),
        "censored": sum(1 for r in resolutions if r.fetch_status == "censored"),
        "resolved_no_coverage": sum(
            1 for r in resolutions if r.status == "resolved_no_coverage"
        ),
    }
    counts["fetched"] = counts["resolved"] + counts["override"]
    counts["unfetchable"] = counts["censored"]
    counts["no_usable_prices"] = sum(1 for r in resolutions if not r.has_usable_prices)
    # Back-compat alias for the fetch-side count.
    counts["fetchable"] = counts["fetched"]
    for stratum in ("core", "extension"):
        counts[f"censored_{stratum}"] = sum(
            1 for r in resolutions if not r.fetched and r.stratum == stratum
        )
        counts[f"no_usable_prices_{stratum}"] = sum(
            1 for r in resolutions if not r.has_usable_prices and r.stratum == stratum
        )
    return counts


def resolution_findings(
    resolutions: Sequence[TickerResolution],
    diff: Optional[CensusDiff] = None,
    coverage_applied: bool = False,
) -> list[Issue]:
    """FATAL findings for a deviation from the pinned §6.1/§6.3 expectations.
    Never silently adopted: a different count means EDGAR's identity data moved,
    and that is a membership-shaped change.

    `coverage_applied=True` (i.e. after `apply_no_coverage_status()` has seen a
    real price frame) additionally pins the OPERATIVE pair and the identity of
    the no-coverage member(s): a second EA-shaped case must be REPORTED BY NAME,
    not absorbed into a count.
    """
    issues: list[Issue] = []
    counts = resolution_counts(resolutions)
    pinned = {
        "resolved": EXPECTED_RESOLVED,
        "override": EXPECTED_OVERRIDES_APPLIED,
        "fetched": EXPECTED_FETCHED,
        "unfetchable": EXPECTED_UNFETCHABLE,
        "censored": EXPECTED_CENSORED,
        "censored_core": EXPECTED_CENSORED_BY_STRATUM["core"],
        "censored_extension": EXPECTED_CENSORED_BY_STRATUM["extension"],
    }
    if coverage_applied:
        pinned.update(
            {
                "no_usable_prices": EXPECTED_NO_USABLE_PRICES,
                "no_usable_prices_core": EXPECTED_NO_USABLE_BY_STRATUM["core"],
                "no_usable_prices_extension": EXPECTED_NO_USABLE_BY_STRATUM["extension"],
            }
        )
        actual = {r.cik for r in resolutions if r.status == "resolved_no_coverage"}
        for cik in sorted(actual - EXPECTED_NO_COVERAGE_CIKS):
            name = next(r.name for r in resolutions if r.cik == cik)
            issues.append(
                Issue("FATAL", None, "unexpected_no_coverage_member",
                      f"{name} (CIK {cik}) was fetched but has zero rows in its "
                      f"coverage window, and is NOT the pre-registered EA case. "
                      f"Report it; do not fold it into the count.", cik=cik)
            )
        for cik in sorted(EXPECTED_NO_COVERAGE_CIKS - actual):
            issues.append(
                Issue("FATAL", None, "expected_no_coverage_member_missing",
                      f"CIK {cik} is pinned as a no-coverage member but now has "
                      f"in-window rows -- re-check before quoting either pair", cik=cik)
            )
    for key, expected in pinned.items():
        if counts[key] != expected:
            issues.append(
                Issue(
                    "FATAL",
                    None,
                    "resolution_count_deviation",
                    f"{key}={counts[key]}, pinned expectation {expected} "
                    f"(F2_SPEC §6.1/§6.3). Re-derive before consuming this run.",
                )
            )
    if diff is not None:
        for cik in sorted(diff.unexpected_resolved_by_e2):
            issues.append(
                Issue("FATAL", None, "census_delta_unexpected",
                      f"CIK {cik} is censored in F1's census but fetchable here, "
                      f"and is not one of the pre-registered exceptions", cik=cik)
            )
        for cik in sorted(diff.unexpected_censored_by_e2):
            issues.append(
                Issue("FATAL", None, "census_delta_unexpected",
                      f"CIK {cik} is resolvable in F1's census but censored here, "
                      f"and is not one of the pre-registered exceptions", cik=cik)
            )
    return issues


def print_resolution_report(
    resolutions: Sequence[TickerResolution],
    overrides: dict[int, TickerOverride],
    diff: Optional[CensusDiff] = None,
    coverage_applied: bool = False,
) -> None:
    counts = resolution_counts(resolutions)
    print("\n=== Ticker resolution (CIK-verified, F2_SPEC §6.1) ===")
    print(f"{counts['members']} members. TWO censoring numbers, never conflated:")
    print(
        f"  FETCH pair      : {counts['fetched']} fetched "
        f"({counts['resolved']} resolved + {counts['override']} override) / "
        f"{counts['unfetchable']} unfetchable "
        f"({counts['censored_core']} core / {counts['censored_extension']} extension) "
        f"-- did a CIK-verified symbol exist to ask for?"
    )
    if coverage_applied:
        print(
            f"  OPERATIVE pair  : {counts['fetched'] - counts['resolved_no_coverage']} "
            f"with usable prices / {counts['no_usable_prices']} with NO usable prices "
            f"({counts['no_usable_prices_core']} core / "
            f"{counts['no_usable_prices_extension']} extension) = "
            f"{counts['unfetchable']} unfetchable + {counts['resolved_no_coverage']} "
            f"fetched-but-zero-coverage -- **this is the pair every E2 result quotes**"
        )
    else:
        print(
            "  OPERATIVE pair  : not determined yet -- it needs the fetched series "
            "(a member can fetch and still have no rows in its own window)."
        )
    print(
        f"  Pinned          : FETCH {EXPECTED_FETCHED} / {EXPECTED_UNFETCHABLE} "
        f"({EXPECTED_CENSORED_BY_STRATUM['core']} core / "
        f"{EXPECTED_CENSORED_BY_STRATUM['extension']} extension); "
        f"OPERATIVE no-usable-prices {EXPECTED_NO_USABLE_PRICES} "
        f"({EXPECTED_NO_USABLE_BY_STRATUM['core']} core / "
        f"{EXPECTED_NO_USABLE_BY_STRATUM['extension']} extension)"
    )

    if coverage_applied and counts["resolved_no_coverage"]:
        print(
            f"\n-- Fetched but NO usable prices ({counts['resolved_no_coverage']}), "
            f"named (EXPANSION_PLAN §2c outcome censoring) --"
        )
        for r in sorted(resolutions, key=lambda r: r.cik):
            if r.status == "resolved_no_coverage":
                print(f"  {r.cik:>9d} [{r.stratum:9s}] {r.name} ({r.chosen_ticker}) -- {r.reason}")

    print("\n-- Overrides on file (printed whether or not they fire) --")
    applied = {r.cik for r in resolutions if r.fetch_status == "override"}
    if not overrides:
        print("  (none)")
    for cik, ov in sorted(overrides.items()):
        state = "APPLIED" if cik in applied else "on file, did not fire"
        print(f"  CIK {cik} -> {ov.ticker} [{state}] ({ov.reason}, added {ov.added})")
    for cik, why in sorted(DELIBERATELY_CENSORED_CIKS.items()):
        print(f"  CIK {cik}: DELIBERATELY CENSORED, never overridden -- {why}")

    print(
        f"\n-- Unfetchable members ({counts['unfetchable']}), named, never silent "
        f"(FETCH pair) --"
    )
    for r in sorted(resolutions, key=lambda r: r.cik):
        if not r.fetched:
            print(f"  {r.cik:>9d} [{r.stratum:9s}] {r.name} -- {r.reason}")

    if diff is not None:
        print("\n-- Reconciliation vs F1's price_censoring_census.parquet (§6.3) --")
        print(
            f"  F1 no-current-ticker members (in universe): {len(diff.f1_censored)}; "
            f"E2 censored: {len(diff.e2_censored)}"
        )
        print(
            f"  pre-registered: -{sorted(diff.expected_resolved_by_e2)} (overridden), "
            f"+{sorted(diff.expected_censored_by_e2)} (non-common only)"
        )
        if diff.census_ciks_not_in_universe:
            print(
                f"  census rows outside the 244-member universe (expected, F1's "
                f"manual exclusions): {sorted(diff.census_ciks_not_in_universe)}"
            )
        if diff.clean:
            print("  delta matches the pre-registration exactly.")
        else:
            print(
                f"  *** UNEXPECTED DELTA -- fetchable-but-F1-censored "
                f"{sorted(diff.unexpected_resolved_by_e2)}, censored-but-F1-resolvable "
                f"{sorted(diff.unexpected_censored_by_e2)} ***"
            )
        print(
            "  ADDENDUM 2026-08-24 (main session ruling, on segment 4's real run):\n"
            "    this reconciliation is FETCH-side -- it compares ticker resolvability,\n"
            "    which is the question F1's census asked. It is silent on whether a\n"
            "    fetched series covers the member's window. EA (CIK 712515) resolves,\n"
            "    fetches, and still has no usable prices (Yahoo purged the delisted\n"
            f"    name's history), so the OPERATIVE population is "
            f"{EXPECTED_NO_USABLE_PRICES} "
            f"({EXPECTED_NO_USABLE_BY_STRATUM['core']} core / "
            f"{EXPECTED_NO_USABLE_BY_STRATUM['extension']} extension), not "
            f"{EXPECTED_UNFETCHABLE}. Both numbers are real; they answer\n"
            "    different questions and are never merged."
        )

    print(
        "\nNOTE (EXPANSION_PLAN §2c): the universe-average benchmark is NOT built "
        "here (that is F5 / gate G3). When it is, it must be computed over "
        "membership-dated members that have usable prices, and the OPERATIVE "
        "no-usable-prices pair "
        + (
            f"({counts['no_usable_prices']}: {counts['no_usable_prices_core']} core / "
            f"{counts['no_usable_prices_extension']} extension)"
            if coverage_applied
            else f"({EXPECTED_NO_USABLE_PRICES} expected: "
                 f"{EXPECTED_NO_USABLE_BY_STRATUM['core']} core / "
                 f"{EXPECTED_NO_USABLE_BY_STRATUM['extension']} extension)"
        )
        + " accompanies every E2 result -- not the FETCH pair, which is an "
        "ingestion fact, not an analysis one."
    )


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


@dataclass
class TickerResult:
    cik: int
    ticker: str
    source: Optional[str] = None
    rows: int = 0
    first_date: Optional[date] = None
    last_date: Optional[date] = None
    error: Optional[str] = None
    meta_symbol: Optional[str] = None
    meta_instrument_type: Optional[str] = None


def ingest_all(
    client: PriceClient,
    fetchable: Sequence[TickerResolution],
    fetched_at: str,
    force: bool = False,
    price_source: str = "yahoo",
) -> tuple[pd.DataFrame, list[TickerResult]]:
    frames = []
    results: list[TickerResult] = []
    for res in fetchable:
        ticker = res.chosen_ticker
        try:
            df, source = client.get_daily_bars(ticker, force=force, source=price_source)
        except PriceFetchError as e:
            print(f"[FATAL] CIK {res.cik} {ticker}: no data from any source ({e})")
            results.append(TickerResult(cik=res.cik, ticker=ticker, error=str(e)))
            continue
        meta = client.last_yahoo_meta or {}
        if df.empty:
            print(f"[FATAL] CIK {res.cik} {ticker}: source {source} returned zero rows")
            results.append(
                TickerResult(cik=res.cik, ticker=ticker, source=source, error="empty")
            )
            continue
        df = df.copy()
        df["cik"] = res.cik
        df["ticker"] = ticker
        df["source"] = source
        df["fetched_at"] = fetched_at
        frames.append(df)
        results.append(
            TickerResult(
                cik=res.cik,
                ticker=ticker,
                source=source,
                rows=len(df),
                first_date=df["date"].min(),
                last_date=df["date"].max(),
                meta_symbol=meta.get("symbol"),
                meta_instrument_type=meta.get("instrumentType"),
            )
        )
    if frames:
        combined = pd.concat(frames, ignore_index=True)[PARQUET_COLUMNS]
        combined = (
            combined.drop_duplicates(subset=["cik", "date"])
            .sort_values(["cik", "date"])
            .reset_index(drop=True)
        )
    else:
        combined = pd.DataFrame(columns=PARQUET_COLUMNS)
    return combined, results


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


# "missing more than a handful of trading days" INSIDE a member's own series
# -> WARN (E1 constant, kept).
COVERAGE_GAP_WARN_THRESHOLD = 5
# "ending months early" -> FATAL for a CURRENT member; for a former member a
# series that stops is the expected delisting/acquisition exit and is INFO.
ENDING_EARLY_FATAL_DAYS = 45
# A series that starts materially after the member's coverage window opens is
# the shape a REASSIGNED symbol would have (the F1 APC->ARKO trap: ARKO's
# history starts in 2020, Anadarko was a member from 2016). WARN, always
# looked at by a human.
STARTS_LATE_WARN_DAYS = 45

# Sanity bound for single-day |return|, used only to flag outliers for human
# eyeballing -- never to silently drop or "correct" data. Calibrated per-run
# from the fetched data itself (see calibrate_return_bound()) with a floor so a
# very calm sample doesn't produce a hair-trigger threshold.
RETURN_BOUND_FLOOR = 0.15


def build_trading_calendar(df: pd.DataFrame, window_start: date, window_end: date) -> list[date]:
    """Union of every distinct trading date across all fetched series within
    the window -- a stand-in for the real NYSE/NASDAQ calendar, robust to any
    one ticker's own gaps.
    """
    in_window = df[(df["date"] >= window_start) & (df["date"] <= window_end)]
    return sorted(in_window["date"].unique())


def _series_key(df: pd.DataFrame) -> str:
    """`cik` is the E2 join key; fall back to `ticker` so a frame built before
    resolution (or in a test) still groups correctly."""
    return "cik" if "cik" in df.columns else "ticker"


def calibrate_return_bound(df: pd.DataFrame, floor: float = RETURN_BOUND_FLOOR) -> float:
    """Calibrate the single-day-return sanity bound from the data itself: the
    99.5th percentile of |daily return| across the whole fetched history,
    floored so a very calm sample doesn't produce an overly tight threshold.
    """
    if df.empty:
        return floor
    key = _series_key(df)
    d = df.sort_values([key, "date"]).copy()
    d["prev_close"] = d.groupby(key)["close"].shift(1)
    d["ret"] = d["close"] / d["prev_close"] - 1.0
    abs_ret = d["ret"].dropna().abs()
    if abs_ret.empty:
        return floor
    calibrated = float(abs_ret.quantile(0.995))
    return max(floor, calibrated)


def find_return_outliers(df: pd.DataFrame, bound: float) -> pd.DataFrame:
    key = _series_key(df)
    d = df.sort_values([key, "date"]).copy()
    d["prev_close"] = d.groupby(key)["close"].shift(1)
    d["ret"] = d["close"] / d["prev_close"] - 1.0
    cols = [c for c in ("cik", "ticker") if c in d.columns]
    outliers = d[d["ret"].abs() > bound][cols + ["date", "prev_close", "close", "ret"]]
    return outliers.reset_index(drop=True)


def meta_tripwire_issues(results: Sequence[TickerResult]) -> list[Issue]:
    """Free sanity check on the Yahoo response itself (§6.4): the symbol it
    answered with must be the symbol we asked for, and the instrument must be
    an equity. Cheap defence against a symbol silently resolving to a different
    instrument (an ETF, a warrant, another listing). WARN, naming the CIK.
    """
    issues: list[Issue] = []
    for r in results:
        if r.meta_symbol is None and r.meta_instrument_type is None:
            continue  # not a Yahoo response (Stooq path) -- nothing to check
        if r.meta_symbol is not None and r.meta_symbol.upper() != r.ticker.upper():
            issues.append(
                Issue("WARN", r.ticker, "meta_symbol_mismatch",
                      f"requested {r.ticker}, response meta.symbol={r.meta_symbol!r}",
                      cik=r.cik)
            )
        if r.meta_instrument_type is not None and r.meta_instrument_type.upper() != "EQUITY":
            issues.append(
                Issue("WARN", r.ticker, "meta_instrument_type",
                      f"meta.instrumentType={r.meta_instrument_type!r}, expected 'EQUITY'",
                      cik=r.cik)
            )
    return issues


def validate_prices(
    df: pd.DataFrame,
    fetchable: Sequence[TickerResolution],
    window_start: date = CORPUS_WINDOW_START,
    window_end: date = CORPUS_WINDOW_END,
) -> list[Issue]:
    """Coverage/sanity validation, per member, over the member's OWN coverage
    window (F2_SPEC §1.2's per-company window, the same discipline S2 applied
    to metadata validation).

    `missing_entirely` is FATAL for a RESOLVED ticker only -- a censored CIK is
    never passed in here at all: it is a counted exclusion in the censoring
    report, not a price failure (§6.4).
    """
    issues: list[Issue] = []
    if "cik" not in df.columns:
        raise ValueError(
            "prices frame has no `cik` column -- cik is the E2 join key (§6.4)"
        )

    # -- non-positive close, over the FULL fetched history -----------------
    for _, row in df[df["close"] <= 0].iterrows():
        issues.append(
            Issue("FATAL", row["ticker"], "non_positive_close",
                  f"close={row['close']} on {row['date']}", cik=int(row["cik"]))
        )

    calendar = build_trading_calendar(df, window_start, window_end)
    calendar_set = set(calendar)
    global_last = max(calendar) if calendar else None

    for res in fetchable:
        tdf = df[df["cik"] == res.cik]
        if tdf.empty:
            issues.append(
                Issue("FATAL", res.chosen_ticker, "missing_entirely",
                      "no rows from any source", cik=res.cik)
            )
            continue

        start = max(window_start, res.coverage_start or window_start)
        end = min(window_end, res.coverage_end or window_end)
        in_window = tdf[(tdf["date"] >= start) & (tdf["date"] <= end)]
        if in_window.empty:
            issues.append(
                Issue(
                    "FATAL" if res.is_current_member else "WARN",
                    res.chosen_ticker,
                    "missing_in_window",
                    f"has {len(tdf)} rows total but none in its coverage window "
                    f"[{start}, {end}]",
                    cik=res.cik,
                )
            )
            continue

        ticker_dates = set(in_window["date"])
        first, last = min(ticker_dates), max(ticker_dates)

        # Interior holes only: a series that legitimately starts at a listing
        # date or stops at a delisting is reported by its own check below, not
        # as thousands of "missing" days.
        interior_missing = sorted(d for d in calendar_set if first < d < last and d not in ticker_dates)
        if len(interior_missing) > COVERAGE_GAP_WARN_THRESHOLD:
            preview = ", ".join(str(d) for d in interior_missing[:10])
            more = f" (+{len(interior_missing) - 10} more)" if len(interior_missing) > 10 else ""
            issues.append(
                Issue("WARN", res.chosen_ticker, "coverage_gap",
                      f"missing {len(interior_missing)} trading days inside its own "
                      f"series vs. the union calendar: {preview}{more}", cik=res.cik)
            )

        if (first - start).days > STARTS_LATE_WARN_DAYS:
            issues.append(
                Issue("WARN", res.chosen_ticker, "starts_after_coverage_start",
                      f"first bar {first} is {(first - start).days} calendar days "
                      f"after the coverage window opens ({start}) -- check this is a "
                      f"listing date and not a reassigned symbol", cik=res.cik)
            )

        target_last = min(global_last, end) if global_last is not None else end
        days_behind = (target_last - last).days
        if days_behind > ENDING_EARLY_FATAL_DAYS:
            if res.is_current_member:
                issues.append(
                    Issue("FATAL", res.chosen_ticker, "ends_early",
                          f"last bar {last} is {days_behind} calendar days behind "
                          f"{target_last} for a CURRENT member", cik=res.cik)
                )
            else:
                issues.append(
                    Issue("INFO", res.chosen_ticker, "series_ends_before_window_end",
                          f"last bar {last}, {days_behind} calendar days before "
                          f"{target_last} -- expected shape for a former member "
                          f"(delisting/acquisition), not a fetch failure", cik=res.cik)
                )

    # -- single-day return outliers ---------------------------------------
    bound = calibrate_return_bound(df)
    for _, row in find_return_outliers(df, bound).iterrows():
        issues.append(
            Issue("WARN", row["ticker"], "return_outlier",
                  f"{row['date']}: {row['prev_close']:.2f} -> {row['close']:.2f} "
                  f"({row['ret'] * 100:+.1f}%), bound={bound * 100:.1f}%",
                  cik=int(row["cik"]) if "cik" in row else None)
        )

    return issues


def _label(issue: Issue) -> str:
    if issue.cik is not None and issue.ticker:
        return f"CIK {issue.cik} {issue.ticker}"
    if issue.cik is not None:
        return f"CIK {issue.cik}"
    return issue.ticker or "run"


def print_report(issues: list[Issue], bound: Optional[float] = None) -> int:
    fatals = [i for i in issues if i.severity == "FATAL"]
    warns = [i for i in issues if i.severity == "WARN"]
    infos = [i for i in issues if i.severity == "INFO"]

    print("\n=== Validation report ===")
    if bound is not None:
        print(f"Return-outlier sanity bound (calibrated from data): {bound * 100:.1f}%")
    if not issues:
        print("No issues found.")
        return 0
    for i in fatals:
        print(f"[FATAL] {_label(i)}: {i.check} -- {i.message}")
    for i in warns:
        print(f"[WARN]  {_label(i)}: {i.check} -- {i.message}")
    for i in infos:
        print(f"[INFO]  {_label(i)}: {i.check} -- {i.message}")
    print(f"\n{len(fatals)} FATAL, {len(warns)} WARN, {len(infos)} INFO")
    return 1 if fatals else 0


def print_coverage_summary(results: list[TickerResult]) -> None:
    print("\n=== Per-member coverage summary ===")
    print(
        f"{'cik':>9s} {'ticker':8s} {'source':22s} {'rows':>7s} "
        f"{'first_date':12s} {'last_date':12s}"
    )
    for r in sorted(results, key=lambda r: r.cik):
        if r.error:
            print(
                f"{r.cik:>9d} {r.ticker:8s} {'FAILED':22s} {'-':>7s} {'-':12s} "
                f"{'-':12s}  ({r.error})"
            )
        else:
            print(
                f"{r.cik:>9d} {r.ticker:8s} {r.source:22s} {r.rows:7d} "
                f"{str(r.first_date):12s} {str(r.last_date):12s}"
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="bypass cache, re-fetch every ticker"
    )
    parser.add_argument(
        "--fetched-at",
        default=None,
        help="override the ingestion timestamp (ISO 8601, UTC); default: now",
    )
    parser.add_argument("--output", default=str(OUTPUT_PARQUET), help="output parquet path")
    parser.add_argument(
        "--ticker-map", default=str(TICKER_MAP_CSV), help="output ticker-map CSV path"
    )
    parser.add_argument(
        "--overrides", default=str(OVERRIDES_CSV), help="evidenced ticker-override CSV"
    )
    parser.add_argument(
        "--price-source",
        choices=("yahoo", "stooq-first"),
        default="yahoo",
        help=(
            "default 'yahoo' (F2_SPEC §6.4 / ruling §9.1 item 8): Stooq is "
            "bot-gated site-wide since 2026-08-18, so trying it once per ticker "
            "only to fail is wasteful and impolite. 'stooq-first' keeps E1's "
            "behaviour (Stooq, then Yahoo) one flag away."
        ),
    )
    parser.add_argument(
        "--resolve-only",
        action="store_true",
        help="resolve tickers, write the map + census reconciliation, fetch nothing",
    )
    parser.add_argument(
        "--db",
        default=None,
        help=(
            "optional, READ-ONLY: price ingestion writes a parquet, never the "
            "metadata DB. When given, every fetched-but-zero-coverage member is "
            "cross-referenced against its distress_events rows (EXPANSION_PLAN "
            "§2c), so a vanished price series is tied to EDGAR's own Form 25 / "
            "Form 15 evidence -- or WARNs if nothing explains it."
        ),
    )
    parser.add_argument("--quiet", action="store_true", help="suppress per-request GET logging")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    output_path = Path(args.output)
    if output_path.resolve() == E1_OUTPUT_PARQUET.resolve():
        print(
            f"[FATAL] {E1_OUTPUT_PARQUET} is E1's frozen record and is never "
            f"rewritten by E2. Use {OUTPUT_PARQUET}."
        )
        return 2

    universe = load_universe()
    overrides = load_ticker_overrides(Path(args.overrides))
    edgar = EdgarClient(verbose=not args.quiet)
    resolutions = resolve_universe_tickers(edgar, universe, overrides=overrides)
    diff = reconcile_censoring_census(resolutions)
    fetchable = [r for r in resolutions if r.fetchable]

    if args.resolve_only:
        # Classify against an EXISTING parquet if one is on disk (read-only) so
        # a resolve-only pass reproduces the operative pair instead of silently
        # rewriting the map back to its pre-fetch state.
        coverage_applied = False
        continuity: list[Issue] = []
        if output_path.exists():
            existing = pd.read_parquet(output_path)
            apply_no_coverage_status(resolutions, existing)
            continuity = successor_continuity_issues(resolutions, existing, overrides)
            coverage_applied = True
            print(f"Classified coverage against the existing {output_path} (read-only)")
        map_path = write_ticker_map(resolutions, Path(args.ticker_map))
        print_resolution_report(resolutions, overrides, diff, coverage_applied=coverage_applied)
        print(f"\nWrote {len(resolutions)} rows to {map_path}")
        return print_report(
            resolution_findings(resolutions, diff, coverage_applied=coverage_applied)
            + ticker_wobble_issues(resolutions, overrides)
            + continuity
            + no_coverage_distress_issues(resolutions, Path(args.db) if args.db else None)
        )

    # Written BEFORE the fetch too, so a killed run still leaves the map behind;
    # rewritten after the fetch with the operative statuses.
    map_path = write_ticker_map(resolutions, Path(args.ticker_map))
    print_resolution_report(resolutions, overrides, diff)
    print(f"\nWrote {len(resolutions)} rows to {map_path}")

    fetched_at = args.fetched_at or datetime.now(timezone.utc).isoformat()
    print(
        f"\nFetching {len(fetchable)} tickers from "
        f"{'Yahoo' if args.price_source == 'yahoo' else 'Stooq (then Yahoo)'}"
    )
    client = PriceClient(verbose=not args.quiet)
    combined, results = ingest_all(
        client, fetchable, fetched_at=fetched_at, force=args.force,
        price_source=args.price_source,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    combined.to_parquet(output_path, index=False)
    print(f"\nWrote {len(combined)} rows to {output_path}")

    print_coverage_summary(results)

    # Now that real series exist, refine the operative statuses and re-emit both
    # the map and the resolution report so the two pairs are final (§2c).
    flipped = apply_no_coverage_status(resolutions, combined)
    if flipped:
        print(
            f"\n{len(flipped)} fetched member(s) have NO rows inside their own "
            f"coverage window -> status resolved_no_coverage: "
            + ", ".join(f"CIK {r.cik} {r.chosen_ticker}" for r in flipped)
        )
    write_ticker_map(resolutions, Path(args.ticker_map))
    print_resolution_report(resolutions, overrides, diff, coverage_applied=True)

    issues = resolution_findings(resolutions, diff, coverage_applied=True)
    issues += ticker_wobble_issues(resolutions, overrides)
    issues += successor_continuity_issues(resolutions, combined, overrides)
    issues += no_coverage_distress_issues(resolutions, Path(args.db) if args.db else None)
    issues += meta_tripwire_issues(results)
    issues += validate_prices(combined, fetchable)
    bound = calibrate_return_bound(combined)
    return print_report(issues, bound=bound)


if __name__ == "__main__":
    raise SystemExit(main())
