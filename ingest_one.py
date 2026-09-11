#!/usr/bin/env python3
"""ingest_one.py -- L2.2 of the APP LANE: one company, on demand, from EDGAR.

PRODUCT_PLAN.md P1a. A ticker (or CIK) goes in; a per-company STORE comes out,
carrying exactly the four tables `report_filing.py` reads for the 244-company
research corpus, in exactly the same schemas:

    data/app/companies/<cik>/
        metadata.db      sqlite -- `ingest_metadata.init_db`'s own schema
        sections.parquet the extracted sections, schema of data/filings_e2_v2.parquet
        chunks.parquet   the labeling windows, schema of data/f4/chunks_v1.parquet
        manifest.json    every input and output sha256, the draw, the timings
        (labels.parquet is written later, by label_filing.py)

NOTHING HERE IS REIMPLEMENTED. The five steps are the project's own modules,
called in order:

  1. ticker -> CIK          `edgar_client.EdgarClient.get_company_tickers`
  2. filing history         `EdgarClient.get_effective_recent`
                            `ingest_metadata.extract_target_filings`
  3. earnings document      `EdgarClient.get_filing_index_html`
                            `ingest_metadata.parse_index_html_documents`
                            `ingest_metadata.select_earnings_document`
  4. documents              `EdgarClient.get_archive_document` (rate-limited,
                            cached under data/raw/documents/ -- the SAME cache
                            and the SAME cache-key rule F2 wrote)
  5. sections              `extract.extract_filing` + `extract.build_rows`
  6. chunks                `finetune/build_f4_chunks.build` under a config whose
                            only differences from F4's are the corpus path, the
                            disabled sha pin (this corpus is new), no stratum
                            filter and no membership DB (an external company has
                            no membership spell -- the columns are written False,
                            which is the truth).

WHAT IS DIFFERENT FROM THE RESEARCH CORPUS, AND SAID OUT LOUD
-------------------------------------------------------------
*  The occurrence arrays (`source_accession_numbers`) span THIS COMPANY'S
   ingested filings only. In F4 they span 244 companies' core sections, so a
   shared boilerplate paragraph is deduplicated across issuers. Here the
   dedup universe is one company, which means: (a) no other issuer's words can
   ever reach this company's page, and (b) `n_source_filings` counts only the
   filings in this store. Both are recorded in the manifest.
*  `home_stratum` is written `external`, never `core`. The store is outside
   the 244-company universe; `report_filing --store` renders one extra
   disclosure line saying so.
*  `window_rule` is `APP_single_company`. The LINE rule is F4's `reflow_v1`
   unchanged -- the labeler must see the same shaped passages it was measured on.
*  No fundamentals are ingested. `report_filing` resolves them out of F2's
   committed concept resolution, which covers the 244 companies only, so an
   external company's five families render UNRESOLVED. That is honest and is
   left honest.

Cost: $0. EDGAR only, through the existing rate-limited client with the
project's real-contact User-Agent. No API, no GPU, no price data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import extract as EX
import ingest_metadata as IM
from edgar_client import EdgarClient

sys.path.insert(0, str(Path(__file__).resolve().parent / "finetune"))
import build_f4_chunks as BFC  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
COMPANIES_DIR = DATA_DIR / "app" / "companies"
E2_METADATA_DB = DATA_DIR / "filings_metadata_e2.db"
E2_SECTIONS_PARQUET = DATA_DIR / "filings_e2_v2.parquet"
F4_CHUNKS_PARQUET = DATA_DIR / "f4" / "chunks_v1.parquet"

STORE_VERSION = "app-store-v1"
RUN_ID = "L2.2-ingest-one"
WINDOW_RULE = "APP_single_company"
EXTERNAL_STRATUM = "external"
EXTERNAL_SECTOR = "UNCLASSIFIED"

# Forms the store carries, and how many of each (newest first).
STORE_FORMS = ("10-K", "10-Q", "8-K")
DEFAULT_PER_FORM = 1
# How far back to look for them. Wide enough that a company that files late
# still yields its latest of each form; the SELECTION is always "newest first",
# never "everything in the window".
DEFAULT_LOOKBACK_DAYS = 1100


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def store_dir(cik: int, root: Path = COMPANIES_DIR) -> Path:
    return Path(root) / str(int(cik))


class IngestError(RuntimeError):
    """A named, recorded failure. Never swallowed, never filtered out."""

    def __init__(self, cause: str, detail: str = ""):
        super().__init__(f"{cause}: {detail}" if detail else cause)
        self.cause = cause
        self.detail = detail


# ---------------------------------------------------------------------------
# step 1 -- ticker / CIK resolution, and the universe exclusion
# ---------------------------------------------------------------------------
def ticker_table(client: EdgarClient) -> pd.DataFrame:
    """SEC's bulk ticker -> CIK map as a frame: cik, ticker, title.

    This is the file the acceptance draw samples from, and the only place a
    ticker is resolved. It is fetched through the rate-limited client and
    cached under data/raw/company_tickers.json like every other EDGAR object.
    """
    raw = client.get_company_tickers()
    rows = [{"cik": int(v["cik_str"]), "ticker": str(v["ticker"]).upper(),
             "title": str(v["title"])} for v in raw.values()]
    return pd.DataFrame(rows).drop_duplicates(subset=["ticker"]).reset_index(drop=True)


def resolve_ticker(client: EdgarClient, ticker: str) -> tuple[int, str]:
    """(cik, company title) for a ticker, from SEC's own map."""
    table = ticker_table(client)
    hit = table[table.ticker == ticker.upper()]
    if hit.empty:
        raise IngestError("ticker_not_in_sec_map",
                          f"{ticker!r} is not in company_tickers.json")
    return int(hit.iloc[0].cik), str(hit.iloc[0].title)


def research_universe_ciks(db_path: Path = E2_METADATA_DB) -> set[int]:
    """The 244 CIKs of the research corpus. A company in here is NOT external
    and must not be drawn for the acceptance test."""
    if not Path(db_path).exists():
        return set()
    con = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    try:
        return {int(r[0]) for r in con.execute("SELECT cik FROM companies")}
    finally:
        con.close()


# ---------------------------------------------------------------------------
# step 2 -- which filings
# ---------------------------------------------------------------------------
def company_filings(client: EdgarClient, cik: int, lookback_days: int,
                    as_of: Optional[date] = None) -> list[dict]:
    """Every 10-K / 10-Q / 8-K of this company inside the lookback window.

    `get_effective_recent` (not the raw `filings.recent`) because a
    high-volume filer's recent array is ~1000 filings of ANY form and can
    cover well under a year -- INGESTION_NOTES.md's JPM/BAC/GS case. The
    pagination chunks are pulled only when the window needs them.
    """
    as_of = as_of or date.today()
    start = as_of - timedelta(days=lookback_days)
    recent = client.get_effective_recent(cik, start)
    rows = IM.extract_target_filings(recent, start, as_of)
    for row in rows:
        row["cik"] = int(cik)
    return rows


def select_filings(rows: list[dict], per_form: int = DEFAULT_PER_FORM) -> list[dict]:
    """The newest `per_form` of each form the store carries.

    An 8-K counts only if it carries item 2.02 -- `has_earnings_item` is
    `ingest_metadata`'s own earnings proxy and the only 8-K class the labeler
    was measured on. Deterministic: sorted by (filing_date, accession) so two
    filings on one day always pick the same one.
    """
    chosen: list[dict] = []
    for form in STORE_FORMS:
        pool = [r for r in rows if r["form"] == form]
        if form == "8-K":
            pool = [r for r in pool if r.get("has_earnings_item")]
        pool.sort(key=lambda r: (r["filing_date"], r["accession_number"]), reverse=True)
        chosen.extend(pool[:per_form])
    chosen.sort(key=lambda r: (r["filing_date"], r["accession_number"]), reverse=True)
    return chosen


# ---------------------------------------------------------------------------
# step 3 -- the earnings document of an 8-K
# ---------------------------------------------------------------------------
def resolve_earnings_document(client: EdgarClient, row: dict) -> dict:
    """Fill the four `earnings_doc_*` columns for one 8-K.

    `select_earnings_document` is `ingest_metadata`'s ruled policy (rules 0-6,
    per-filer handlers included) and is CALLED, never re-expressed. A `None`
    return is UNRESOLVED and is recorded as such -- the row is kept, the
    failure is named, and extraction will report `cache_miss`/no section
    rather than a silent drop.
    """
    cik, accession = int(row["cik"]), row["accession_number"]
    try:
        index_html = client.get_filing_index_html(cik, accession)
    except Exception as exc:  # noqa: BLE001
        row["earnings_doc_unresolved_reason"] = f"filing_index_fetch_failed: {exc}"
        return row
    docs = IM.parse_index_html_documents(index_html, row.get("primary_document"))
    row["_documents"] = docs
    picked = IM.select_earnings_document(
        docs, row.get("primary_document"), subject=f"CIK {cik}",
        accession_number=accession, cik=cik, filing_date=row["filing_date"])
    if picked is None:
        row["earnings_doc_unresolved_reason"] = (
            "select_earnings_document found no EX-99.x and no confirmable "
            "candidate row (ingest_metadata rule 5: UNRESOLVED, never the body "
            "at high confidence)")
        return row
    row["earnings_doc_filename"] = picked.get("filename")
    row["earnings_doc_section_type"] = picked.get("section_type")
    row["earnings_doc_selection_confidence"] = picked.get("selection_confidence")
    row["earnings_doc_relative_path"] = picked.get("relative_path") or IM.archive_document_path(
        cik, accession, picked.get("filename"))
    if picked.get("section_type") == "EX99_PRESS_RELEASE":
        row["ex99_1_document"] = picked.get("filename")
    return row


# ---------------------------------------------------------------------------
# step 4 -- documents into data/raw/documents/
# ---------------------------------------------------------------------------
def document_paths(row: dict) -> list[str]:
    """The archive paths this filing's extraction will read."""
    if row["form"] in ("10-K", "10-Q"):
        if not row.get("primary_document"):
            return []
        return [EX.periodic_relative_path(int(row["cik"]), row["accession_number"],
                                          row["primary_document"])]
    if row.get("earnings_doc_filename"):
        return [EX.earnings_relative_path(row)]
    return []


def fetch_documents(client: EdgarClient, rows: list[dict]) -> dict:
    """Cache every selected document. Failures are recorded per filing."""
    fetched, failures = [], []
    for row in rows:
        for rel in document_paths(row):
            try:
                client.get_archive_document(rel)
                fetched.append(rel)
            except Exception as exc:  # noqa: BLE001
                failures.append({"accession_number": row["accession_number"],
                                 "relative_path": rel,
                                 "cause": "document_fetch_failed",
                                 "detail": f"{type(exc).__name__}: {exc}"})
    return {"n_fetched": len(fetched), "paths": fetched, "failures": failures}


# ---------------------------------------------------------------------------
# the store's metadata DB
# ---------------------------------------------------------------------------
FILING_INSERT_COLUMNS = (
    "accession_number", "cik", "ticker", "form", "filing_date", "report_date",
    "acceptance_datetime", "primary_document", "items", "has_earnings_item",
    "ex99_1_document", "exhibit_lookup_done", "earnings_doc_filename",
    "earnings_doc_relative_path", "earnings_doc_section_type",
    "earnings_doc_selection_confidence",
)


def write_metadata_db(path: Path, cik: int, name: str, ticker: Optional[str],
                      rows: list[dict]) -> None:
    """The store's own sqlite, on `ingest_metadata.init_db`'s schema.

    The schema is IMPORTED, not restated, so `report_filing`'s two queries
    (`filings` and `companies`) are the same queries against the store and
    against the research DB. `universe_membership` and `distress_events` are
    left empty: this company is in no universe and the store makes no claim
    about its outcomes.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()
    con = sqlite3.connect(path)
    try:
        IM.init_db(con)
        con.execute(
            "INSERT OR REPLACE INTO companies (cik, ticker, sector, company_name, "
            "stratum, coverage_start, coverage_end, is_current_member) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (int(cik), ticker, EXTERNAL_SECTOR, name, EXTERNAL_STRATUM,
             min((r["filing_date"] for r in rows), default=None),
             max((r["filing_date"] for r in rows), default=None), 0))
        for row in rows:
            con.execute(
                f"INSERT OR REPLACE INTO filings ({','.join(FILING_INSERT_COLUMNS)}) "
                f"VALUES ({','.join('?' * len(FILING_INSERT_COLUMNS))})",
                tuple(row.get(col) for col in FILING_INSERT_COLUMNS))
            for doc in row.get("_documents", []) or []:
                con.execute(
                    "INSERT INTO filing_documents (accession_number, seq, doc_type, "
                    "description, filename, relative_path, source_table) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (row["accession_number"], doc.get("seq"), doc.get("doc_type"),
                     doc.get("description"), doc.get("filename"),
                     doc.get("relative_path"), doc.get("source_table")))
        con.commit()
    finally:
        con.close()


# ---------------------------------------------------------------------------
# step 5 -- sections
# ---------------------------------------------------------------------------
def sections_schema() -> Optional[pa.Schema]:
    """The research corpus's OWN arrow schema, read off the file.

    Copied rather than re-declared so "same schema as data/filings_e2_v2.parquet"
    is a fact rather than a claim. If the research corpus is absent (a fresh
    clone), the schema falls back to None and pandas' inference writes the
    same column NAMES in the same order -- the store still loads, and the
    manifest records that the pin was unavailable.
    """
    if not E2_SECTIONS_PARQUET.exists():
        return None
    return pq.read_schema(E2_SECTIONS_PARQUET)


def extract_sections(rows: list[dict], run_id: str = RUN_ID) -> tuple[pd.DataFrame, list[dict]]:
    """`extract.extract_filing` over the selected filings; every attempt audited.

    The `f` mapping each call gets is the same shape `extract.run()` builds
    from the research DB, with `sector`/`stratum` set to the external values.
    A filing whose earnings document never resolved has no section_type to
    extract and is recorded as an audit row with reason
    `earnings_doc_unresolved` -- counted, never dropped.
    """
    quarter_cells: dict[tuple[int, str], int] = {}
    for row in rows:
        if row["form"] == "8-K" and row.get("earnings_doc_section_type"):
            key = (int(row["cik"]), EX.filing_quarter(row["filing_date"]))
            quarter_cells[key] = quarter_cells.get(key, 0) + 1

    corpus_rows, audit_rows, fired = [], [], {}
    for row in rows:
        f = {
            "accession_number": row["accession_number"], "cik": int(row["cik"]),
            "form": row["form"], "filing_date": row["filing_date"],
            "report_date": row.get("report_date"),
            "primary_document": row.get("primary_document"),
            "earnings_doc_filename": row.get("earnings_doc_filename"),
            "earnings_doc_relative_path": row.get("earnings_doc_relative_path"),
            "earnings_doc_section_type": row.get("earnings_doc_section_type"),
            "company_name": row["company_name"], "sector": EXTERNAL_SECTOR,
            "stratum": EXTERNAL_STRATUM,
        }
        if row["form"] == "8-K" and not row.get("earnings_doc_section_type"):
            audit_rows.append({
                "cik": int(row["cik"]), "company_name": row["company_name"],
                "sector": EXTERNAL_SECTOR, "stratum": EXTERNAL_STRATUM,
                "accession_number": row["accession_number"], "form": row["form"],
                "section_type": None, "extraction_status": EX.STATUS_FAIL,
                "reason_code": "earnings_doc_unresolved", "flags": [],
                "extraction_method": None, "extraction_confidence": None,
                "word_count": 0, "prose_word_share": 0.0, "ctrl_ratio": None,
                "eng_word_share": None, "source_document": None,
                "note": row.get("earnings_doc_unresolved_reason", ""),
            })
            continue
        for section_type, result, source in EX.extract_filing(
                EX.read_cached_document, f, quarter_cells, fired=fired):
            corpus_row, audit = EX.build_rows(f, section_type, result, source, run_id)
            audit_rows.append(audit)
            if corpus_row is not None:
                corpus_rows.append(corpus_row)

    frame = EX._frame(corpus_rows, EX.OUTPUT_COLUMNS)
    return frame, audit_rows


def write_sections(frame: pd.DataFrame, path: Path) -> dict:
    schema = sections_schema()
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(frame, schema=schema, preserve_index=False)
    pq.write_table(table, path)
    return {"path": str(path), "sha256": sha256_file(path), "n_rows": len(frame),
            "schema_pinned_to": str(E2_SECTIONS_PARQUET) if schema is not None else None}


# ---------------------------------------------------------------------------
# step 6 -- chunks
# ---------------------------------------------------------------------------
def chunk_config(sections_path: Path, out_path: Path) -> BFC.BuildConfig:
    """F4's config with four declared differences, and no others.

    The line rule, the chunk/paragraph id construction, the packing arithmetic
    and the dedup are F4's, unchanged -- a passage this store hands the labeler
    is shaped exactly like the 317,081 the labeler was measured on.
    """
    return BFC.BuildConfig(
        corpus_path=sections_path,
        corpus_sha256="",            # this corpus is new; there is nothing to pin to
        stratum=None,                # the store holds one company, no strata
        line_rule=BFC.LINE_RULE,     # reflow_v1, unchanged
        tie_slot="cik10",
        chunk_prefix=BFC.CHUNK_PREFIX,
        para_prefix=BFC.PARA_PREFIX,
        window_rule=WINDOW_RULE,
        out_parquet=out_path,
        membership_db=None,          # external company: no membership spell
    )


def build_chunks(sections_path: Path, out_path: Path, verbose: bool = False) -> dict:
    if not sections_path.exists():
        raise IngestError("no_sections", "extraction produced no section table")
    info = BFC.build(chunk_config(sections_path, out_path), verbose=verbose)
    return info


# ---------------------------------------------------------------------------
# the whole thing
# ---------------------------------------------------------------------------
def ingest(ticker: Optional[str] = None, cik: Optional[int] = None,
           per_form: int = DEFAULT_PER_FORM,
           lookback_days: int = DEFAULT_LOOKBACK_DAYS,
           root: Path = COMPANIES_DIR, client: Optional[EdgarClient] = None,
           verbose: bool = True) -> dict:
    """ticker|cik -> a company store. Returns the manifest (also written)."""
    t_all = time.perf_counter()
    client = client or EdgarClient(verbose=False)
    timings: dict[str, float] = {}

    t = time.perf_counter()
    if cik is None:
        if not ticker:
            raise IngestError("no_company", "give a ticker or a CIK")
        cik, name = resolve_ticker(client, ticker)
    else:
        cik = int(cik)
        table = ticker_table(client)
        hit = table[table.cik == cik]
        name = str(hit.iloc[0].title) if not hit.empty else f"CIK {cik}"
        ticker = ticker or (str(hit.iloc[0].ticker) if not hit.empty else None)
    timings["resolve_s"] = time.perf_counter() - t

    t = time.perf_counter()
    history = company_filings(client, cik, lookback_days)
    selected = select_filings(history, per_form)
    if not selected:
        raise IngestError(
            "no_target_filings",
            f"CIK {cik} filed no 10-K/10-Q/earnings 8-K in the last "
            f"{lookback_days} days")
    for row in selected:
        row["company_name"] = name
        row["ticker"] = ticker
        row["exhibit_lookup_done"] = 0
        if row["form"] == "8-K":
            resolve_earnings_document(client, row)
            row["exhibit_lookup_done"] = 1
    timings["metadata_s"] = time.perf_counter() - t

    t = time.perf_counter()
    docs = fetch_documents(client, selected)
    timings["documents_s"] = time.perf_counter() - t

    out = store_dir(cik, root)
    out.mkdir(parents=True, exist_ok=True)
    write_metadata_db(out / "metadata.db", cik, name, ticker, selected)

    t = time.perf_counter()
    frame, audit = extract_sections(selected)
    sections_info = write_sections(frame, out / "sections.parquet")
    timings["extract_s"] = time.perf_counter() - t

    t = time.perf_counter()
    if frame.empty:
        chunks_info = None
        chunk_error = "every extraction attempt failed; no chunk table was built"
    else:
        chunks_info = build_chunks(out / "sections.parquet", out / "chunks.parquet")
        chunk_error = None
    timings["chunk_s"] = time.perf_counter() - t
    timings["total_s"] = time.perf_counter() - t_all

    manifest = {
        "store_version": STORE_VERSION,
        "run_id": RUN_ID,
        "cik": int(cik),
        "ticker": ticker,
        "company_name": name,
        "in_research_universe": int(cik) in research_universe_ciks(),
        "window": {"lookback_days": lookback_days, "per_form": per_form,
                   "forms": list(STORE_FORMS)},
        "filings": [
            {"accession_number": r["accession_number"], "form": r["form"],
             "filing_date": r["filing_date"], "items": r.get("items"),
             "primary_document": r.get("primary_document"),
             "earnings_doc_filename": r.get("earnings_doc_filename"),
             "earnings_doc_section_type": r.get("earnings_doc_section_type"),
             "earnings_doc_selection_confidence": r.get("earnings_doc_selection_confidence"),
             "earnings_doc_unresolved_reason": r.get("earnings_doc_unresolved_reason")}
            for r in selected],
        "n_filings_in_history": len(history),
        "documents": {"n_fetched": docs["n_fetched"], "failures": docs["failures"]},
        "sections": sections_info,
        "sections_by_status": (
            frame.extraction_status.value_counts().to_dict() if not frame.empty else {}),
        "extraction_audit": audit,
        "chunks": ({"path": str(out / "chunks.parquet"),
                    "sha256": chunks_info["parquet"]["sha256"],
                    "n_chunks": chunks_info["n_chunks"],
                    "n_sections": chunks_info["n_sections"],
                    "window_rule": chunks_info["window_rule"],
                    "line_rule": chunks_info["line_rule"],
                    "schema_source": "finetune/build_f4_chunks._arrow_schema "
                                     "(the schema data/f4/chunks_v1.parquet was written with)"}
                   if chunks_info else {"error": chunk_error}),
        "metadata_db": {"path": str(out / "metadata.db"),
                        "sha256": sha256_file(out / "metadata.db"),
                        "schema_source": "ingest_metadata.init_db"},
        "dedup_universe": (
            "THIS COMPANY'S ingested filings only -- not the 244-company corpus. "
            "n_source_filings counts occurrences inside this store."),
        "network": {"edgar_requests": client.request_count,
                    "user_agent": client.headers["User-Agent"], "cost_usd": 0.0},
        "timings_seconds": {k: round(v, 2) for k, v in timings.items()},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n")
    if verbose:
        n_chunks = manifest["chunks"].get("n_chunks", 0)
        print(f"{name} (CIK {cik}) -> {out}\n"
              f"  filings {len(selected)} · sections {len(frame)} · chunks {n_chunks} · "
              f"{timings['total_s']:.1f}s · {client.request_count} EDGAR requests")
    return manifest


# ---------------------------------------------------------------------------
# the acceptance draw (PRODUCT_PLAN §0.5 item 2 / §3 P1a)
# ---------------------------------------------------------------------------
DRAW_ELIGIBILITY = (
    "in SEC company_tickers.json (exchange-listed, ticker-bearing); NOT one of "
    "the 244 research-universe CIKs; at least one 10-K filed in the last 730 "
    "days (this is what excludes funds, trusts and foreign private issuers, "
    "which file N-CSR / 20-F and never a 10-K)."
)


def draw_companies(n: int = 10, seed: int = 20260911, recent_10k_days: int = 730,
                   client: Optional[EdgarClient] = None,
                   verbose: bool = True) -> dict:
    """A seeded random draw of `n` external companies -- the builder does not
    choose them.

    Method, fixed before the draw and recorded with it: shuffle the whole
    eligible-by-identity candidate list with `numpy.default_rng(seed)`, walk it
    in that order, and accept the first `n` that pass the ELIGIBILITY screen
    above. The screen is about whether the company is the KIND of filer this
    tool is for; it never looks at whether the pipeline succeeds. Every
    candidate examined is recorded, accepted or rejected, with its reason.
    """
    import numpy as np

    client = client or EdgarClient(verbose=False)
    table = ticker_table(client)
    excluded = research_universe_ciks()
    candidates = table[~table.cik.isin(excluded)].sort_values("ticker").reset_index(drop=True)

    rng = np.random.default_rng(seed)
    order = rng.permutation(len(candidates))
    cutoff = (date.today() - timedelta(days=recent_10k_days)).isoformat()

    accepted, examined = [], []
    for pos in order:
        if len(accepted) >= n:
            break
        row = candidates.iloc[int(pos)]
        record = {"ticker": row.ticker, "cik": int(row.cik), "name": row.title}
        try:
            recent = client.get_effective_recent(
                int(row.cik), date.today() - timedelta(days=recent_10k_days))
            forms = recent.get("form", [])
            dates = recent.get("filingDate", [])
            has10k = any(f == "10-K" and d >= cutoff for f, d in zip(forms, dates))
            record["n_filings_seen"] = len(forms)
            record["accepted"] = bool(has10k)
            record["reason"] = "" if has10k else f"no 10-K filed since {cutoff}"
        except Exception as exc:  # noqa: BLE001
            record["accepted"] = False
            record["reason"] = f"submissions fetch failed: {type(exc).__name__}: {exc}"
        examined.append(record)
        if record["accepted"]:
            accepted.append(record)
        if verbose:
            mark = "ACCEPT" if record["accepted"] else "reject"
            print(f"  {mark} {record['ticker']:<8} CIK {record['cik']:<9} "
                  f"{record['name'][:40]:<40} {record.get('reason','')}")

    return {
        "seed": seed,
        "generator": "numpy.random.default_rng(seed).permutation over the "
                     "ticker-sorted candidate list",
        "source": "SEC company_tickers.json via edgar_client.get_company_tickers",
        "n_in_ticker_file": len(table),
        "n_research_universe_ciks_excluded": len(excluded),
        "n_candidates": len(candidates),
        "eligibility": DRAW_ELIGIBILITY,
        "n_examined": len(examined),
        "examined": examined,
        "drawn": accepted,
        "drawn_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Ingest ONE company from EDGAR into a per-company store "
                    "report_filing.py can read. Personal use only.")
    who = ap.add_mutually_exclusive_group()
    who.add_argument("--ticker", type=str)
    who.add_argument("--cik", type=int)
    ap.add_argument("--per-form", type=int, default=DEFAULT_PER_FORM,
                    help="how many of each of 10-K / 10-Q / earnings 8-K "
                         "(newest first); 2 gives report_filing a prior filing "
                         "to compare against")
    ap.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    ap.add_argument("--root", type=Path, default=COMPANIES_DIR)
    ap.add_argument("--draw", type=int, default=0, metavar="N",
                    help="instead of ingesting: draw N external companies with "
                         "the seeded generator and write the draw to --draw-out")
    ap.add_argument("--seed", type=int, default=20260911)
    ap.add_argument("--draw-out", type=Path,
                    default=DATA_DIR / "app" / "status" / "external_draw.json")
    args = ap.parse_args(argv)

    if args.draw:
        draw = draw_companies(args.draw, args.seed)
        args.draw_out.parent.mkdir(parents=True, exist_ok=True)
        args.draw_out.write_text(json.dumps(draw, indent=2) + "\n")
        print(f"\ndrew {len(draw['drawn'])} of {draw['n_examined']} examined "
              f"-> {args.draw_out}")
        return 0

    if not (args.ticker or args.cik):
        raise SystemExit("give --ticker, --cik, or --draw N")
    try:
        ingest(ticker=args.ticker, cik=args.cik, per_form=args.per_form,
               lookback_days=args.lookback_days, root=args.root)
    except IngestError as exc:
        print(f"FAILED [{exc.cause}] {exc.detail}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
