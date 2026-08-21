"""
ingest_metadata.py -- pull 10-K/10-Q/8-K filing metadata for the fixed
FinScreen company universe (data/universe.csv) and store it in
data/filings_metadata.db (SQLite).

Week 1 scope: metadata (accession numbers, real EDGAR public filing dates,
form types, and -- for 8-Ks -- the resolved earnings-release document, via
the filing_documents table / selection policy in this module). No filing
text is downloaded or extracted here; that's extract.py in Week 2.

Point-in-time discipline: every row's `filing_date` is EDGAR's own recorded
public filing date for that accession (the `filingDate` field from
submissions.json), never a fiscal period end date. `report_date` (the fiscal
period end) is also stored, but only for reference -- it must never be used
as the point-in-time timestamp downstream.

Universe note (survivorship bias, flagged not solved -- see DISCOVERY.md §5):
this universe was deliberately built from companies that are large-cap and
long-listed *today*, which is a convenience choice to reduce the odds of a
ticker not existing across the full lookback window. It does NOT correct for
survivorship bias -- companies that were prominent in this window but were
later delisted, acquired, or collapsed are absent by construction. That bias
is inherited by every downstream result from this universe and is restated
in INGESTION_NOTES.md; it is not addressed further in this script.

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
concrete JPM/BAC/GS bug this caught.
"""

from __future__ import annotations

import argparse
import html
import re
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from edgar_client import EdgarClient

REPO_ROOT = Path(__file__).resolve().parent
UNIVERSE_CSV = REPO_ROOT / "data" / "universe.csv"
DB_PATH = REPO_ROOT / "data" / "filings_metadata.db"

TARGET_FORMS = {"10-K", "10-Q", "8-K"}
LOOKBACK_QUARTERS = 12  # ~3 years, per DISCOVERY.md §3 (8-12 quarters)

# -- validate_universe() thresholds (see INGESTION_NOTES.md for the full
# rationale/calibration behind each number) -----------------------------
MAX_FILING_GAP_DAYS = 135  # calibrated off the healthy 22 companies; UNH's
                            # observed max gap is 125 days
# Calibrated against the real 3-year inter-filing-gap distribution across all
# 25 companies (not guessed): the max observed "any form" gap is 70 days
# (SLB). 80 = max-observed + ~15% headroom, the same calibration discipline
# already used for MAX_FILING_GAP_DAYS/MAX_STALE_10K_10Q_DAYS above. At the
# previous value (45 days) this check fired on ~10% of possible run-dates
# (HD tripped it on 2026-08-10 with a genuine, non-buggy 47-day quiet
# period) -- see INGESTION_NOTES.md. This check's severity is WARN (see
# RECENT_ACTIVITY_ANY_FORM_SEVERITY below), not FATAL: it is NOT the check
# that actually detects a stopped-filing entity -- MAX_STALE_10K_10Q_DAYS is,
# and stays FATAL, since a 135-day gap with no 10-K/10-Q at all is a much
# stronger signal than a quiet period with no filing of ANY form.
MAX_STALE_ANY_FILING_DAYS = 80    # most recent filing of any form
RECENT_ACTIVITY_ANY_FORM_SEVERITY = "WARN"  # was FATAL; see comment above
MAX_STALE_10K_10Q_DAYS = 135      # most recent 10-K/10-Q -- stays FATAL,
                                   # this is the check that actually detects
                                   # a genuinely stopped-filing entity
RECENT_ACTIVITY_10K10Q_SEVERITY = "FATAL"
MIN_10K_HARD_FLOOR = 2
MIN_10Q_HARD_FLOOR = 7
MIN_10K_EXPECTED = 3
MIN_10Q_EXPECTED = 8

# All FATAL check names validate_universe() can raise -- used to validate
# --allow-incomplete-universe's scoped override list (see Fix 2 in
# INGESTION_NOTES.md's Week 2-corrective-pass notes / run()'s argparse help).
# Kept as an explicit allowlist, not derived by introspection, so adding a
# new FATAL check elsewhere in this file can't silently become overridable
# without a deliberate edit here too.
#
# NOTE: the old "recent_activity" check name covered two very different
# things (an any-form-staleness arm and a 10-K/10-Q-staleness arm) under one
# name. That's split into "recent_activity_any_form" (WARN, NOT in this set
# -- it never blocks a run, so there's nothing for --allow-incomplete-
# universe to override) and "recent_activity_10k_10q" (FATAL, IS in this
# set). The split matters even though only one arm is currently FATAL:
# it guarantees --allow-incomplete-universe=recent_activity_any_form can
# never be typed (it's simply not a recognized override target) in a way
# that would ALSO happen to downgrade the FATAL arm, if a future change to
# either check's severity is made without revisiting this allowlist.
ALL_FATAL_CHECK_NAMES = {
    "entity_resolves",
    "history_reaches_cutoff",
    "plausible_filing_counts",
    "no_large_filing_gap",
    "recent_activity_10k_10q",
}

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


def lookback_cutoff(today: date, quarters: int = LOOKBACK_QUARTERS) -> date:
    return today - timedelta(days=quarters * 91)  # ~91 days/quarter, generous


def load_universe() -> pd.DataFrame:
    # NOTE on XOM's CIK (34088): company_tickers.json currently maps ticker
    # "XOM" to CIK 2115436 ("ExxonMobil Holdings Corp"), a newly created
    # successor/holding entity with exactly one filing on record -- NOT the
    # entity with Exxon's actual 3-year filing history. universe.csv
    # deliberately uses the legacy CIK 34088 ("Exxon Mobil Corp") instead,
    # confirmed manually via data.sec.gov/submissions/CIK0000034088.json.
    # See INGESTION_NOTES.md finding #4: the bulk ticker map is a good
    # starting point for CIK lookup but isn't reliable as the sole source of
    # truth around corporate restructurings -- don't "fix" this row back to
    # the company_tickers.json value without re-checking that note.
    # validate_universe()'s "CIK map agreement" check WARNs on this
    # disagreement every run, by design -- it's a known, reviewed override,
    # not something to silently resolve either direction.
    df = pd.read_csv(UNIVERSE_CSV)
    expected_cols = {"ticker", "cik", "sector", "company_name"}
    missing = expected_cols - set(df.columns)
    if missing:
        raise ValueError(f"universe.csv missing columns: {missing}")
    if not (20 <= len(df) <= 30):
        raise ValueError(
            f"universe.csv has {len(df)} companies -- expected 20-30 per "
            f"DISCOVERY.md §3. Refusing to proceed silently; fix the "
            f"universe file or explicitly flag the scope change."
        )
    return df


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS companies (
            cik INTEGER PRIMARY KEY,
            ticker TEXT NOT NULL,
            sector TEXT NOT NULL,
            company_name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS filings (
            accession_number TEXT PRIMARY KEY,
            cik INTEGER NOT NULL,
            ticker TEXT NOT NULL,
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
            ticker TEXT NOT NULL,
            check_name TEXT NOT NULL,
            severity TEXT NOT NULL,
            message TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_filings_cik ON filings(cik);
        CREATE INDEX IF NOT EXISTS idx_filings_form ON filings(form);
        CREATE INDEX IF NOT EXISTS idx_filings_date ON filings(filing_date);
        CREATE INDEX IF NOT EXISTS idx_filing_documents_accession
            ON filing_documents(accession_number);
        """
    )
    conn.commit()


def upsert_company(conn: sqlite3.Connection, row: pd.Series) -> None:
    conn.execute(
        "INSERT INTO companies (cik, ticker, sector, company_name) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(cik) DO UPDATE SET ticker=excluded.ticker, sector=excluded.sector, "
        "company_name=excluded.company_name",
        (int(row["cik"]), row["ticker"], row["sector"], row["company_name"]),
    )


def extract_target_filings(recent: dict, ticker: str, cutoff: date) -> list[dict]:
    """`recent` is a filings.recent-shaped dict of parallel arrays -- either
    the raw `submissions["filings"]["recent"]` or the pagination-merged
    result of EdgarClient.get_effective_recent().
    """
    n = len(recent["form"])
    out = []
    for i in range(n):
        form = recent["form"][i]
        if form not in TARGET_FORMS:
            continue
        filing_date_str = recent["filingDate"][i]
        filing_date = date.fromisoformat(filing_date_str)
        if filing_date < cutoff:
            continue
        items = recent.get("items", [""] * n)[i]
        items_list = [x.strip() for x in items.split(",")] if items else []
        out.append(
            {
                "accession_number": recent["accessionNumber"][i],
                "ticker": ticker,
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
      - Requires >=3 total parsed rows across both tables, else raises --
        guards against EDGAR serving non-hyperlinked rows for some filing,
        which this href-required parse would otherwise silently drop,
        indistinguishable from a legitimately sparse filing.
      - If `primary_document` is given, asserts it appears among the parsed
        filenames, else raises -- a parse that can't even find the filing's
        own primary document is broken, and a future EDGAR layout change
        should fail loudly here rather than silently resolving to "no
        exhibit found" (which looks identical to the legitimate no-exhibit
        case downstream).
    """
    out: list[dict] = []
    for summary_raw, table_html in _TABLE_RE.findall(html_text):
        source_table = _clean_cell(summary_raw) or "unknown"
        for row_html in _ROW_RE.findall(table_html):
            tds = _TD_RE.findall(row_html)
            if len(tds) < 5:
                continue
            seq_cell, desc_cell, doc_cell, type_cell, _size_cell = tds[:5]
            href_match = _HREF_RE.search(doc_cell)
            if not href_match:
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

    if len(out) < 3:
        raise ValueError(
            f"Parsed only {len(out)} document row(s) from filing index HTML "
            f"-- expected >=3. Treating as a parse failure rather than "
            f"trusting a possibly-broken parse (see parse_index_html_documents "
            f"docstring)."
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
    ticker: str = "",
    accession_number: str = "",
) -> dict | None:
    """Selection policy over a filing's parsed document rows. First matching
    rule wins:

      1. Exactly one EX-99.1 -> take it (high confidence).
      2. >1 EX-99.1 -> take lowest seq, confidence=low, log loudly (canary --
         not expected to occur across the current universe/window).
      3. No EX-99.1, exactly one bare EX-99 -> take it (high confidence).
      4. No EX-99.1/EX-99, but EX-99.2/.3/etc. present -> score by
         description keywords (PRESS RELEASE/NEWS RELEASE/EARNINGS RELEASE
         beat PRESENTATION/SUPPLEMENTAL/COMMENTARY/DATA SUMMARY); a unique
         positive-scoring winner is taken at medium confidence, otherwise
         (tie, or nothing scores positively) take lowest seq at low
         confidence.
      5. No EX-99.x at all -> fall back to `primary_document` (from
         submissions.json, always populated), section_type='8K_BODY'. Never
         resolved by scanning the index for a row typed "8-K" -- some
         filers (MCD confirmed) carry two such rows (the real iXBRL primary
         document AND a scanned PDF copy), which would be a nondeterministic
         pick.

    Returns None only if there are no EX-99.x candidates AND no
    primary_document was supplied (shouldn't happen in practice --
    primary_document comes straight from submissions.json).
    """

    def by_type(*type_names: str) -> list[dict]:
        wanted = {t.upper() for t in type_names}
        return [d for d in docs if d["doc_type"].upper() in wanted]

    exact_991 = by_type("EX-99.1")
    if len(exact_991) == 1:
        return _resolved(exact_991[0], "EX99_PRESS_RELEASE", "high")
    if len(exact_991) > 1:
        chosen = min(exact_991, key=_seq_sort_key)
        print(
            f"  CANARY: {ticker} {accession_number} has {len(exact_991)} "
            f"EX-99.1 rows ({[d['filename'] for d in exact_991]}) -- taking "
            f"lowest seq {chosen['filename']!r}, selection_confidence=low. "
            f"This was not expected to occur across the current 331 "
            f"earnings 8-Ks -- treat as a canary, not expected behavior."
        )
        return _resolved(chosen, "EX99_PRESS_RELEASE", "low")

    bare_99 = by_type("EX-99")
    if len(bare_99) == 1:
        return _resolved(bare_99[0], "EX99_PRESS_RELEASE", "high")
    if len(bare_99) > 1:
        chosen = min(bare_99, key=_seq_sort_key)
        print(
            f"  CANARY: {ticker} {accession_number} has {len(bare_99)} bare "
            f"EX-99 rows -- taking lowest seq {chosen['filename']!r}, "
            f"selection_confidence=low."
        )
        return _resolved(chosen, "EX99_PRESS_RELEASE", "low")

    other_99x = [d for d in docs if re.match(r"^EX-99\.\d+$", d["doc_type"].upper())]
    if other_99x:
        scored = [(_score_description(d["description"]), d) for d in other_99x]
        best_score = max(s for s, _ in scored)
        winners = [d for s, d in scored if s == best_score]
        if len(winners) == 1 and best_score > 0:
            return _resolved(winners[0], "EX99_PRESS_RELEASE", "medium")
        chosen = min(other_99x, key=_seq_sort_key)
        return _resolved(chosen, "EX99_PRESS_RELEASE", "low")

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
    ticker: str = "",
) -> tuple[list[dict], dict | None]:
    """Fetch (cached) the filing index HTML, parse it into document rows,
    and run the selection policy. Returns (parsed_document_rows, selection).
    """
    html_text = client.get_filing_index_html(cik, accession_number)
    docs = parse_index_html_documents(html_text, primary_document=primary_document)
    selection = select_earnings_document(
        docs, primary_document, ticker=ticker, accession_number=accession_number
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


class ValidationProblem:
    __slots__ = ("ticker", "check", "severity", "message")

    def __init__(self, ticker: str, check: str, severity: str, message: str):
        assert severity in ("FATAL", "WARN")
        self.ticker = ticker
        self.check = check
        self.severity = severity
        self.message = message

    def __repr__(self) -> str:
        return f"{self.ticker} | {self.severity} | {self.check} | {self.message}"


def validate_universe(
    client: EdgarClient, universe: pd.DataFrame, cutoff: date, today: date,
    force_refresh: bool = False,
) -> list[ValidationProblem]:
    """Run every per-company completeness/sanity check against cached (or
    freshly-fetched-and-then-cached) submissions data, BEFORE the ingestion
    loop writes anything to the DB. See the module docstring and
    INGESTION_NOTES.md for why this exists.

    Every problem across all companies is collected and returned -- callers
    decide whether to hard-fail, print, and/or persist them.
    """
    problems: list[ValidationProblem] = []

    # Bulk ticker->CIK map, fetched/cached once for the whole pass.
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
                "*", "cik_map_fetch", "WARN",
                f"Could not fetch/parse company_tickers.json for the CIK-agreement "
                f"check: {e}. CIK map agreement check skipped for all companies.",
            )
        )

    for _, row in universe.iterrows():
        ticker = row["ticker"]
        cik = int(row["cik"])

        # -- Entity resolves (FATAL) --------------------------------------
        try:
            submissions = client.get_submissions(cik, force=force_refresh)
        except Exception as e:  # noqa: BLE001
            problems.append(
                ValidationProblem(
                    ticker, "entity_resolves", "FATAL",
                    f"submissions.json fetch failed for CIK {cik}: {e}",
                )
            )
            continue  # nothing else can be checked without submissions data

        if "filings" not in submissions or "recent" not in submissions.get("filings", {}):
            problems.append(
                ValidationProblem(
                    ticker, "entity_resolves", "FATAL",
                    f"submissions.json for CIK {cik} has no filings.recent key -- "
                    f"malformed or unexpected response shape.",
                )
            )
            continue

        # -- History reaches cutoff (FATAL) -------------------------------
        # This is exactly what A1's pagination fixes -- get_effective_recent
        # transparently pulls filings.files[] chunks if filings.recent alone
        # doesn't reach back far enough. If it STILL doesn't reach cutoff
        # after that, something is genuinely wrong (or the company's whole
        # history is shorter than our window).
        try:
            effective_recent = client.get_effective_recent(cik, cutoff, force=force_refresh)
        except Exception as e:  # noqa: BLE001
            problems.append(
                ValidationProblem(
                    ticker, "history_reaches_cutoff", "FATAL",
                    f"Failed fetching filings.files[] pagination chunks for CIK {cik}: {e}",
                )
            )
            continue

        recent = submissions["filings"]["recent"]
        dates = effective_recent.get("filingDate", [])
        if not dates:
            problems.append(
                ValidationProblem(
                    ticker, "history_reaches_cutoff", "FATAL",
                    f"CIK {cik} has zero filings in filings.recent at all.",
                )
            )
            continue
        min_date = min(date.fromisoformat(d) for d in dates)
        if min_date > cutoff:
            problems.append(
                ValidationProblem(
                    ticker, "history_reaches_cutoff", "FATAL",
                    f"CIK {cik}: earliest filing found ({min_date.isoformat()}) does not "
                    f"reach the {cutoff.isoformat()} cutoff, even after checking "
                    f"filings.files[] pagination chunks "
                    f"({len(submissions['filings'].get('files', []))} chunk(s) available).",
                )
            )

        # -- Plausible filing counts (FATAL below hard floor, WARN below expected) --
        target_filings = extract_target_filings(effective_recent, ticker, cutoff)
        n_10k = sum(1 for f in target_filings if f["form"] == "10-K")
        n_10q = sum(1 for f in target_filings if f["form"] == "10-Q")

        if n_10k < MIN_10K_HARD_FLOOR:
            problems.append(
                ValidationProblem(
                    ticker, "plausible_filing_counts", "FATAL",
                    f"Only {n_10k} 10-K(s) in window (hard floor: {MIN_10K_HARD_FLOOR}).",
                )
            )
        elif n_10k < MIN_10K_EXPECTED:
            problems.append(
                ValidationProblem(
                    ticker, "plausible_filing_counts", "WARN",
                    f"Only {n_10k} 10-K(s) in window (expected >= {MIN_10K_EXPECTED} for a "
                    f"{LOOKBACK_QUARTERS}-quarter window).",
                )
            )
        if n_10q < MIN_10Q_HARD_FLOOR:
            problems.append(
                ValidationProblem(
                    ticker, "plausible_filing_counts", "FATAL",
                    f"Only {n_10q} 10-Q(s) in window (hard floor: {MIN_10Q_HARD_FLOOR}).",
                )
            )
        elif n_10q < MIN_10Q_EXPECTED:
            problems.append(
                ValidationProblem(
                    ticker, "plausible_filing_counts", "WARN",
                    f"Only {n_10q} 10-Q(s) in window (expected >= {MIN_10Q_EXPECTED} for a "
                    f"{LOOKBACK_QUARTERS}-quarter window).",
                )
            )

        # -- No large filing gap (FATAL) ----------------------------------
        in_window_10k10q_dates = sorted(
            date.fromisoformat(f["filing_date"])
            for f in target_filings
            if f["form"] in ("10-K", "10-Q")
        )
        for i in range(1, len(in_window_10k10q_dates)):
            gap = (in_window_10k10q_dates[i] - in_window_10k10q_dates[i - 1]).days
            if gap > MAX_FILING_GAP_DAYS:
                problems.append(
                    ValidationProblem(
                        ticker, "no_large_filing_gap", "FATAL",
                        f"{gap}-day gap between 10-K/10-Q filings "
                        f"{in_window_10k10q_dates[i - 1].isoformat()} -> "
                        f"{in_window_10k10q_dates[i].isoformat()} exceeds "
                        f"{MAX_FILING_GAP_DAYS}-day threshold.",
                    )
                )

        # -- Recent activity (FATAL) --------------------------------------
        any_form_dates = recent.get("filingDate", [])
        if any_form_dates:
            most_recent_any = max(date.fromisoformat(d) for d in any_form_dates)
            staleness_any = (today - most_recent_any).days
            if staleness_any > MAX_STALE_ANY_FILING_DAYS:
                problems.append(
                    ValidationProblem(
                        ticker, "recent_activity_any_form", RECENT_ACTIVITY_ANY_FORM_SEVERITY,
                        f"Most recent filing of any form is {most_recent_any.isoformat()} "
                        f"({staleness_any} days old, threshold {MAX_STALE_ANY_FILING_DAYS}) "
                        f"-- most likely an ordinary quiet filing period (WARN, not FATAL: "
                        f"this arm of the check isn't the one that reliably detects a "
                        f"stopped-filing entity -- see MAX_STALE_10K_10Q_DAYS below).",
                    )
                )
        if in_window_10k10q_dates or target_filings:
            all_10k10q_dates = [
                date.fromisoformat(f["filing_date"])
                for f in extract_target_filings(effective_recent, ticker, date(1900, 1, 1))
                if f["form"] in ("10-K", "10-Q")
            ]
            if all_10k10q_dates:
                most_recent_10k10q = max(all_10k10q_dates)
                staleness_10k10q = (today - most_recent_10k10q).days
                if staleness_10k10q > MAX_STALE_10K_10Q_DAYS:
                    problems.append(
                        ValidationProblem(
                            ticker, "recent_activity_10k_10q", RECENT_ACTIVITY_10K10Q_SEVERITY,
                            f"Most recent 10-K/10-Q is {most_recent_10k10q.isoformat()} "
                            f"({staleness_10k10q} days old, threshold {MAX_STALE_10K_10Q_DAYS}) "
                            f"-- this IS the check that detects a genuinely stopped-filing "
                            f"entity; stays FATAL.",
                        )
                    )

        # -- Current ticker matches (WARN) --------------------------------
        submission_tickers = {t.upper() for t in submissions.get("tickers", [])}
        if ticker.upper() not in submission_tickers:
            problems.append(
                ValidationProblem(
                    ticker, "current_ticker_matches", "WARN",
                    f"universe.csv ticker {ticker!r} not found in submissions.json's "
                    f"tickers list {sorted(submission_tickers)} for CIK {cik}.",
                )
            )

        # -- CIK map agreement (WARN) -------------------------------------
        if ticker_to_cik:
            mapped_cik = ticker_to_cik.get(ticker.upper())
            if mapped_cik is not None and int(mapped_cik) != cik:
                problems.append(
                    ValidationProblem(
                        ticker, "cik_map_agreement", "WARN",
                        f"company_tickers.json maps {ticker!r} -> CIK {mapped_cik}, but "
                        f"universe.csv uses CIK {cik}. Both reported, neither silently "
                        f"preferred -- see INGESTION_NOTES.md for the reviewed XOM case.",
                    )
                )

    return problems


def print_validation_report(problems: list[ValidationProblem]) -> None:
    if not problems:
        print("\nvalidate_universe(): no problems found across all companies.")
        return
    print(f"\nvalidate_universe(): {len(problems)} problem(s) found:")
    print(f"{'ticker':<8} {'severity':<8} {'check':<28} message")
    print("-" * 100)
    for p in sorted(problems, key=lambda p: (p.severity != "FATAL", p.ticker, p.check)):
        print(f"{p.ticker:<8} {p.severity:<8} {p.check:<28} {p.message}")


def write_validation_problems(conn: sqlite3.Connection, problems: list[ValidationProblem], run_date: date) -> None:
    conn.execute("DELETE FROM universe_validation_problems WHERE run_date = ?", (run_date.isoformat(),))
    conn.executemany(
        "INSERT INTO universe_validation_problems (run_date, ticker, check_name, severity, message) "
        "VALUES (?, ?, ?, ?, ?)",
        [(run_date.isoformat(), p.ticker, p.check, p.severity, p.message) for p in problems],
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Main ingestion run
# ---------------------------------------------------------------------------


def parse_allow_incomplete_universe_arg(raw: str | None) -> set[str] | None:
    """`--allow-incomplete-universe` takes an explicit, comma-separated list
    of check names to downgrade (e.g.
    `--allow-incomplete-universe=history_reaches_cutoff`), NOT a blanket
    switch. Returns None if the flag wasn't passed at all (no override in
    effect), or the parsed set of check names otherwise (a bare
    `--allow-incomplete-universe` with no `=value`, i.e. an empty string,
    is deliberately rejected below -- see the design note in run()).
    """
    if raw is None:
        return None
    names = {n.strip() for n in raw.split(",") if n.strip()}
    if not names:
        raise ValueError(
            "--allow-incomplete-universe requires at least one explicit check name "
            "(e.g. --allow-incomplete-universe=history_reaches_cutoff) -- an empty "
            "value would downgrade nothing and every FATAL would still hard-fail the "
            "run, which is almost certainly not what was intended."
        )
    unknown = names - ALL_FATAL_CHECK_NAMES
    if unknown:
        raise ValueError(
            f"--allow-incomplete-universe names unknown check(s): {sorted(unknown)}. "
            f"Known FATAL check names: {sorted(ALL_FATAL_CHECK_NAMES)}."
        )
    return names


def run(force_refresh: bool = False, allow_incomplete_universe: set[str] | None = None) -> None:
    """`allow_incomplete_universe`, if not None, is the set of check names
    whose FATAL findings are permitted to be downgraded to WARN for this run
    -- see parse_allow_incomplete_universe_arg() and the module-level design
    note below on why this is scoped rather than a blanket switch.

    Design note (Fix 2 in the corrective pass -- see INGESTION_NOTES.md):
    the earlier version of this flag was a bare boolean that downgraded
    EVERY FATAL finding for the run, not just the one the caller intended to
    override. That's a real safety bug: using it to accept one known-OK
    FATAL (e.g. HD's staleness finding) also silently disarmed unrelated
    FATAL checks for that same run -- including the JPM/BAC/GS-class
    `history_reaches_cutoff` regression guard -- with no way for anyone to
    notice a real regression slipped through on a future run made with the
    same flag. Now: any FATAL whose check name is NOT in the explicitly
    named override set still hard-fails the run, and the checks that WERE
    downgraded are printed loudly (not just logged to the DB) so it's
    impossible to miss in normal run output.
    """
    universe = load_universe()
    client = EdgarClient()
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    today = date.today()
    cutoff = lookback_cutoff(today)
    print(f"Pulling filings from {cutoff.isoformat()} to {today.isoformat()} "
          f"({LOOKBACK_QUARTERS} quarters lookback)")

    # -- Phase A2: validate before writing anything --------------------------
    problems = validate_universe(client, universe, cutoff, today, force_refresh=force_refresh)
    print_validation_report(problems)

    fatal_problems = [p for p in problems if p.severity == "FATAL"]
    if fatal_problems:
        override_names = allow_incomplete_universe or set()
        in_scope = [p for p in fatal_problems if p.check in override_names]
        out_of_scope = [p for p in fatal_problems if p.check not in override_names]

        if out_of_scope:
            out_of_scope_checks = sorted({p.check for p in out_of_scope})
            print(
                f"\n{len(out_of_scope)} FATAL problem(s) fired on check(s) NOT named in "
                f"--allow-incomplete-universe: {out_of_scope_checks}. Refusing to write "
                f"to the DB -- a scoped override only downgrades the checks explicitly "
                f"listed, per-check, never a blanket pass. Re-run with "
                f"--allow-incomplete-universe=<comma-separated check names> naming "
                f"every FATAL check you've reviewed and intend to accept this run."
            )
            for p in out_of_scope:
                print(f"    UNSCOPED FATAL: {p}")
            conn.close()
            sys.exit(1)

        if in_scope:
            downgraded_checks = sorted({p.check for p in in_scope})
            print(
                "\n" + "!" * 78 + "\n"
                f"--allow-incomplete-universe DOWNGRADED {len(in_scope)} FATAL "
                f"problem(s) to WARN for this run, scoped to check name(s): "
                f"{downgraded_checks}. Every problem (not just these) is still "
                f"logged to universe_validation_problems.\n"
                + "\n".join(f"  DOWNGRADED: {p}" for p in in_scope) + "\n"
                + "!" * 78
            )

    if allow_incomplete_universe is not None:
        write_validation_problems(conn, problems, today)

    # -- Main ingestion loop --------------------------------------------------
    total_by_form: dict[str, int] = {}

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

    for _, row in universe.iterrows():
        cik = int(row["cik"])
        ticker = row["ticker"]
        upsert_company(conn, row)

        effective_recent = client.get_effective_recent(cik, cutoff, force=force_refresh)
        filings = extract_target_filings(effective_recent, ticker, cutoff)

        for f in filings:
            exhibit_attempted_and_resolved = False
            resolution = None

            if f["form"] == "8-K" and f["has_earnings_item"]:
                try:
                    docs, resolution = resolve_earnings_document(
                        client, cik, f["accession_number"], f["primary_document"], ticker=ticker,
                    )
                    write_filing_documents(conn, f["accession_number"], docs)
                    exhibit_attempted_and_resolved = True
                except Exception as e:  # noqa: BLE001 -- log and continue, don't kill the whole run
                    print(f"  WARN: exhibit lookup failed for {ticker} {f['accession_number']}: {e}")

            if exhibit_attempted_and_resolved:
                ex99_doc = resolution["filename"] if resolution and resolution["is_exhibit"] else None
                conn.execute(
                    upsert_with_exhibit_sql,
                    (
                        f["accession_number"], cik, ticker, f["form"], f["filing_date"],
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
                        f["accession_number"], cik, ticker, f["form"], f["filing_date"],
                        f["report_date"], f["acceptance_datetime"], f["primary_document"],
                        f["items"], f["has_earnings_item"],
                    ),
                )
            total_by_form[f["form"]] = total_by_form.get(f["form"], 0) + 1

        conn.commit()
        print(f"  {ticker} (CIK {cik}): {len(filings)} filings in window")

    conn.close()
    print(f"\nDone. Filings by form type: {total_by_form}")
    print(f"Total EDGAR network GETs this run: {client.request_count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force-refresh", action="store_true",
        help="Ignore submissions cache staleness and re-fetch from EDGAR for every company.",
    )
    parser.add_argument(
        "--allow-incomplete-universe", metavar="CHECK1,CHECK2,...", default=None,
        help=(
            "Downgrade ONLY the named validate_universe() FATAL check(s) to WARN and "
            "proceed with ingestion anyway -- e.g. "
            "--allow-incomplete-universe=history_reaches_cutoff. This is a SCOPED "
            "override, not a blanket one: any FATAL that fires on a check NOT named "
            "here still hard-fails the run. Known FATAL check names: "
            + ", ".join(sorted(ALL_FATAL_CHECK_NAMES)) + ". "
            "Every problem (not just FATALs) is logged to universe_validation_problems "
            "for the eventual limitations doc, and every downgraded check is printed "
            "loudly in run output, not just written to the DB."
        ),
    )
    args = parser.parse_args()
    try:
        override_set = parse_allow_incomplete_universe_arg(args.allow_incomplete_universe)
    except ValueError as e:
        parser.error(str(e))
    run(force_refresh=args.force_refresh, allow_incomplete_universe=override_set)
