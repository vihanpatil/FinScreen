"""
edgar_client.py -- thin, rate-limited wrapper over SEC EDGAR's public JSON API.

Covers three surfaces (per DISCOVERY.md §1):
  - data.sec.gov/submissions/CIK##########.json  (per-company filing history,
      plus its filings.files[] paginated chunk files for companies whose
      filings.recent array doesn't reach back far enough -- see
      get_effective_recent() and INGESTION_NOTES.md's "filings.files[]
      pagination" section)
  - data.sec.gov/api/xbrl/companyfacts/CIK##########.json  (every disclosed
      XBRL fact -- us-gaap + dei concepts -- for one company's entire filing
      history; see get_companyfacts(), added for Phase C numeric-fundamentals
      sourcing. Same host as submissions -- data.sec.gov, NOT www.sec.gov --
      same zero-padded-10-digit CIK convention, one request per company, no
      pagination needed.)
  - www.sec.gov/files/company_tickers.json        (bulk ticker -> CIK map)
  - www.sec.gov/Archives/edgar/data/{cik}/{accession}/{accession}-index.html
      (per-filing document index HTML -- used to locate 8-K exhibits, e.g.
      EX-99.1, without downloading exhibit text yet; that's Week 2's job)

Non-negotiables enforced here, for every code path, including throwaway
scripts (see AGENTS scope doc):
  - Mandatory User-Agent header identifying the project + a real contact
    email, on every single request.
  - A hard client-side 10 requests/second rate limit (a sliding-window
    limiter, not a "best effort" sleep).
  - Retry with exponential backoff specifically on HTTP 429.
  - Idempotent local caching: cached responses are reused instead of
    re-fetched unless they're stale (or the caller forces a refresh).

This module does not know about the company universe or extraction --
that's data/universe.csv and extract.py (Week 2). It only knows how to talk
to EDGAR politely and cache what it gets back.
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from datetime import date
from pathlib import Path
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Real project-owner contact info, required by SEC's fair-access policy for
# data.sec.gov / www.sec.gov. This is NOT a placeholder -- use verbatim.
USER_AGENT = "FinScreen Research vihanpatil7@gmail.com"

SUBMISSIONS_URL_TMPL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
# filings.files[] entries in submissions.json are just a bare filename (e.g.
# "CIK0000019617-submissions-001.json") that lives directly under this same
# data.sec.gov/submissions/ path -- these are the paginated older-history
# chunks for high-filing-volume companies whose filings.recent (~most recent
# 1000 filings of ANY type) doesn't reach back to our lookback cutoff.
SUBMISSIONS_CHUNK_URL_TMPL = "https://data.sec.gov/submissions/{chunk_name}"
# XBRL "companyfacts" -- every us-gaap/dei concept a company has ever
# disclosed, across its full filing history, in one JSON document. Host is
# data.sec.gov (same as submissions), NOT www.sec.gov (which serves the
# ticker map and raw filing archive documents) -- do not conflate the two
# hosts when adding new endpoints here.
COMPANYFACTS_URL_TMPL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
# The human-facing -index.html page carries an authoritative per-document
# "Type" column (e.g. "EX-99.1") straight from the filer's own SEC-HEADER
# tags. index.json's "type" field is just an icon filename (text.gif etc.),
# NOT the document/exhibit type -- filename-pattern guessing at exhibit type
# turned out to be unreliable (see INGESTION_NOTES.md), so this is the
# endpoint actually used to identify EX-99.1 exhibits.
FILING_INDEX_HTML_URL_TMPL = (
    "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{accession}-index.html"
)

RATE_LIMIT_PER_SECOND = 10  # SEC EDGAR's documented hard cap, per DISCOVERY.md §1
DEFAULT_MAX_RETRIES = 5
DEFAULT_BACKOFF_BASE_SECONDS = 1.0

REPO_ROOT = Path(__file__).resolve().parent
DEFAULT_CACHE_DIR = REPO_ROOT / "data" / "raw"

# "Stale" cache policy: metadata that can change day to day (submissions,
# the bulk ticker map) is re-fetched if the cached copy is older than this.
# Immutable, already-filed documents (filing indices) never go stale once
# fetched -- SEC doesn't retroactively edit a filed accession's document
# list -- so they use max_age_hours=None (cache forever) by default.
DEFAULT_MAX_AGE_HOURS = 24.0


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """Thread-safe sliding-window limiter: at most `max_per_second` calls to
    `.acquire()` return within any trailing 1-second window. Blocks (sleeps)
    the caller as needed rather than trusting callers to pace themselves.
    """

    def __init__(self, max_per_second: int = RATE_LIMIT_PER_SECOND):
        self.max_per_second = max_per_second
        self._lock = threading.Lock()
        self._timestamps: deque[float] = deque()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            self._evict_old(now)
            if len(self._timestamps) >= self.max_per_second:
                sleep_for = 1.0 - (now - self._timestamps[0])
                if sleep_for > 0:
                    time.sleep(sleep_for)
                now = time.monotonic()
                self._evict_old(now)
            self._timestamps.append(now)

    def _evict_old(self, now: float) -> None:
        while self._timestamps and now - self._timestamps[0] >= 1.0:
            self._timestamps.popleft()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class EdgarRequestError(RuntimeError):
    pass


class EdgarClient:
    def __init__(
        self,
        user_agent: str = USER_AGENT,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        max_retries: int = DEFAULT_MAX_RETRIES,
        rate_limiter: Optional[RateLimiter] = None,
        verbose: bool = True,
    ):
        if "@" not in user_agent:
            # Cheap sanity check -- EDGAR requires a contact email in the UA.
            raise ValueError(
                "User-Agent must include a contact email per SEC EDGAR policy"
            )
        self.headers = {
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        }
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "submissions").mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "filing_index").mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "documents").mkdir(parents=True, exist_ok=True)
        (self.cache_dir / "companyfacts").mkdir(parents=True, exist_ok=True)
        self.max_retries = max_retries
        self.rate_limiter = rate_limiter or RateLimiter()
        self.verbose = verbose
        self.request_count = 0  # incremented only on actual network GETs

    # -- low-level, always goes through the rate limiter + backoff ---------

    def _get(self, url: str, params: Optional[dict] = None) -> requests.Response:
        backoff = DEFAULT_BACKOFF_BASE_SECONDS
        for attempt in range(self.max_retries + 1):
            self.rate_limiter.acquire()
            self.request_count += 1
            if self.verbose:
                print(f"[EDGAR GET] {url}")
            resp = requests.get(url, headers=self.headers, params=params, timeout=30)
            if resp.status_code == 429:
                if attempt == self.max_retries:
                    raise EdgarRequestError(
                        f"429 rate-limited after {self.max_retries} retries: {url}"
                    )
                retry_after = resp.headers.get("Retry-After")
                wait = max(backoff, float(retry_after)) if retry_after else backoff
                if self.verbose:
                    print(f"  -> 429, backing off {wait:.1f}s (attempt {attempt + 1})")
                time.sleep(wait)
                backoff *= 2
                continue
            if resp.status_code == 403:
                raise EdgarRequestError(
                    f"403 from EDGAR for {url} -- check User-Agent header is set "
                    f"and well-formed; EDGAR blocks requests without one."
                )
            resp.raise_for_status()
            return resp
        raise EdgarRequestError(f"Exhausted retries: {url}")

    # -- cache helpers -------------------------------------------------------

    @staticmethod
    def _is_stale(path: Path, max_age_hours: Optional[float]) -> bool:
        if not path.exists():
            return True
        if max_age_hours is None:
            return False  # cache-forever policy (immutable content)
        age_hours = (time.time() - path.stat().st_mtime) / 3600.0
        return age_hours > max_age_hours

    # -- public endpoints ------------------------------------------------

    def get_company_tickers(self, force: bool = False) -> dict:
        """Bulk ticker -> CIK map. Cached; re-fetched if >24h stale."""
        path = self.cache_dir / "company_tickers.json"
        if force or self._is_stale(path, DEFAULT_MAX_AGE_HOURS):
            resp = self._get(COMPANY_TICKERS_URL)
            path.write_text(resp.text)
        return json.loads(path.read_text())

    def get_submissions(self, cik: int, force: bool = False) -> dict:
        """Per-company filing history (data.sec.gov/submissions). Cached;
        re-fetched if >24h stale (SEC updates this near-real-time as new
        filings post, so a day-old cache can miss the most recent filing).
        """
        path = self.cache_dir / "submissions" / f"CIK{cik:010d}.json"
        if force or self._is_stale(path, DEFAULT_MAX_AGE_HOURS):
            url = SUBMISSIONS_URL_TMPL.format(cik=cik)
            resp = self._get(url)
            path.write_text(resp.text)
        return json.loads(path.read_text())

    def get_submissions_chunk(self, chunk_name: str, force: bool = False) -> dict:
        """Fetch one paginated older-history chunk file listed under a
        company's submissions.json `filings.files[]` array (e.g.
        "CIK0000019617-submissions-001.json"). Same shape as
        `filings.recent` (parallel arrays keyed by accessionNumber,
        filingDate, form, ...), just for an older date range.

        Same 24h staleness cache policy as get_submissions() -- these
        describe a closed historical date range so in practice they should
        never change once posted, but there's no documented guarantee SEC
        never appends/corrects an entry near a chunk boundary, so this
        treats them the same as the live submissions.json rather than
        assuming "cache forever" without confirming that with EDGAR.
        """
        path = self.cache_dir / "submissions" / chunk_name
        if force or self._is_stale(path, DEFAULT_MAX_AGE_HOURS):
            url = SUBMISSIONS_CHUNK_URL_TMPL.format(chunk_name=chunk_name)
            resp = self._get(url)
            path.write_text(resp.text)
        return json.loads(path.read_text())

    def get_effective_recent(self, cik: int, cutoff: date, force: bool = False) -> dict:
        """Return a `filings.recent`-shaped dict (parallel arrays: form,
        filingDate, accessionNumber, ...) that reaches back to at least
        `cutoff`, transparently pulling in filings.files[] pagination chunks
        when filings.recent alone doesn't get there.

        Why this exists: filings.recent is NOT a fixed time window -- it's
        the most recent ~1000 filings of *any* form type, newest first. For
        high-filing-volume companies (large banks especially -- JPM/BAC/GS
        file thousands of Section 16 / debt-program / structured-note
        filings a year), that ~1000-entry cap can correspond to well under
        a year of history, silently truncating the 10-K/10-Q/8-K history
        this pipeline actually needs. See INGESTION_NOTES.md for the
        concrete JPM/BAC/GS case this was built to fix.
        """
        submissions = self.get_submissions(cik, force=force)
        recent = submissions["filings"]["recent"]
        files = submissions["filings"].get("files", [])

        dates = recent.get("filingDate", [])
        if not dates or not files:
            return recent

        min_recent_date = min(date.fromisoformat(d) for d in dates)
        if min_recent_date <= cutoff:
            return recent

        # filings.recent doesn't reach the cutoff and there are pagination
        # chunks available -- pull in chunks until we cover the cutoff.
        # Observed (and documented by SEC's own filenames) to be ordered
        # newest-first, each chunk covering a closed [filingFrom, filingTo]
        # range strictly older than the previous chunk.
        merged = {key: list(values) for key, values in recent.items()}
        for entry in files:
            chunk_to = date.fromisoformat(entry["filingTo"])
            if chunk_to < cutoff:
                # This chunk (and, if ordering holds, everything after it)
                # is entirely older than what we need -- stop fetching.
                break
            chunk = self.get_submissions_chunk(entry["name"], force=force)
            for key in merged:
                merged[key].extend(chunk.get(key, [None] * len(chunk.get("form", []))))
            chunk_from = date.fromisoformat(entry["filingFrom"])
            if chunk_from <= cutoff:
                break  # this chunk's range already reaches back past cutoff

        return merged

    def get_companyfacts(self, cik: int, force: bool = False) -> dict:
        """SEC XBRL "companyfacts" API: every disclosed XBRL fact (us-gaap +
        dei concepts) for one company, across its ENTIRE filing history (not
        windowed) -- data.sec.gov/api/xbrl/companyfacts/CIK##########.json.

        Host note: this is data.sec.gov, exactly like get_submissions() --
        NOT www.sec.gov (which serves company_tickers.json, the filing index
        HTML, and raw archive documents elsewhere in this class). Reuses the
        same zero-padded-10-digit CIK formatting, the same rate limiter,
        User-Agent header, and 429 backoff via `_get()` -- nothing about this
        method forks those conventions.

        Cached under data/raw/companyfacts/CIK##########.json; same 24h
        staleness policy as get_submissions() -- SEC republishes a company's
        XBRL facts shortly after each new filing posts (a newly-filed
        10-Q/10-K's facts appear here, not only in submissions.json), so a
        multi-day-old cache risks missing the most recent filing's facts,
        same reasoning as get_submissions().

        One request per company -- companyfacts is not paginated the way
        filings.recent/filings.files[] is; the whole fact history comes back
        in a single JSON document. Ingesting the full 25-company universe
        therefore costs exactly 25 network requests (fewer on a warm cache),
        trivially inside the 10 req/sec limit.
        """
        path = self.cache_dir / "companyfacts" / f"CIK{cik:010d}.json"
        if force or self._is_stale(path, DEFAULT_MAX_AGE_HOURS):
            url = COMPANYFACTS_URL_TMPL.format(cik=cik)
            resp = self._get(url)
            path.write_text(resp.text)
        return json.loads(path.read_text())

    def get_filing_index_html(self, cik: int, accession_number: str, force: bool = False) -> str:
        """The human-facing filing index page, which lists each document's
        authoritative Type (e.g. "EX-99.1", "8-K", "GRAPHIC") alongside its
        filename. Cached forever once fetched (immutable once filed).
        """
        accession_nodash = accession_number.replace("-", "")
        cache_key = f"{cik}_{accession_nodash}.html"
        path = self.cache_dir / "filing_index" / cache_key
        if force or self._is_stale(path, None):
            url = FILING_INDEX_HTML_URL_TMPL.format(
                cik=cik, accession_nodash=accession_nodash, accession=accession_number
            )
            resp = self._get(url)
            path.write_text(resp.text)
        return path.read_text()

    def get_archive_document(self, relative_path: str, force: bool = False) -> str:
        """Fetch a raw filing document (10-K/10-Q primary document, EX-99.x
        exhibit, 8-K body, etc.) by its EDGAR archive path, e.g.
        "/Archives/edgar/data/886982/000088698226000004/gs-20260107.htm" --
        exactly the `relative_path` shape stored in ingest_metadata.py's
        `filing_documents` table, or easily constructed for a filing's
        `primary_document` as
        f"/Archives/edgar/data/{cik}/{accession_nodash}/{primary_document}".

        Cached forever once fetched (immutable once filed, same reasoning as
        get_filing_index_html()). Cache key is the relative path with
        slashes replaced, so distinct filings' same-named documents (e.g.
        every 10-K having a document literally named "R1.htm") don't
        collide.
        """
        if not relative_path.startswith("/"):
            relative_path = "/" + relative_path
        cache_key = relative_path.strip("/").replace("/", "_")
        path = self.cache_dir / "documents" / cache_key
        if force or self._is_stale(path, None):
            url = f"https://www.sec.gov{relative_path}"
            resp = self._get(url)
            path.write_bytes(resp.content)
        return path.read_text(encoding="utf-8", errors="replace")


if __name__ == "__main__":
    # Minimal smoke test -- still goes through the same rate-limited,
    # User-Agent-headered client as everything else.
    client = EdgarClient()
    tickers = client.get_company_tickers()
    print(f"Loaded {len(tickers)} ticker entries from company_tickers.json")
    aapl = client.get_submissions(320193)
    print(f"AAPL entity name per EDGAR: {aapl['name']}")
