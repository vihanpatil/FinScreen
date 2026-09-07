"""P0 offline probe: timing + anchor-coverage pilot for F3 spec. Zero GETs."""
import json
import random
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path("/Users/vihanpatil/personal/projects/FinScreen")
sys.path.insert(0, str(ROOT))
import extract as E  # noqa: E402

DOCS = ROOT / "data/raw/documents"


class CacheClient:
    """Cache-only stand-in for EdgarClient: never touches the network."""

    request_count = 0

    def get_archive_document(self, relative_path: str) -> str:
        if not relative_path.startswith("/"):
            relative_path = "/" + relative_path
        p = DOCS / relative_path.strip("/").replace("/", "_")
        if not p.exists():
            raise FileNotFoundError(relative_path)
        return p.read_text(encoding="utf-8", errors="replace")


def sample_periodic(per_cell=6, seed=20260826):
    con = sqlite3.connect(f"file:{ROOT}/data/filings_metadata_e2.db?mode=ro", uri=True)
    rows = con.execute(
        "SELECT accession_number, cik, ticker, form, filing_date, primary_document "
        "FROM filings WHERE form IN ('10-K','10-Q') ORDER BY accession_number"
    ).fetchall()
    con.close()
    cells = {}
    for r in rows:
        cells.setdefault((r[3], r[4][:4]), []).append(r)
    rnd = random.Random(seed)
    out = []
    for k in sorted(cells):
        pool = cells[k]
        out += rnd.sample(pool, min(per_cell, len(pool)))
    return out


def main():
    cl = CacheClient()
    picks = sample_periodic(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
    print(f"probe filings: {len(picks)}")
    recs = []
    t_all0 = time.time()
    for acc, cik, ticker, form, fdate, pdoc in picks:
        for section in ("MDA", "RISK_FACTORS"):
            t0 = time.time()
            err = None
            try:
                res = E.extract_item_section(cl, int(cik), acc, pdoc, form, section)
            except Exception as e:  # noqa: BLE001
                res = None
                err = f"{type(e).__name__}: {e}"
            dt = time.time() - t0
            recs.append({
                "acc": acc, "cik": cik, "ticker": ticker, "form": form,
                "year": fdate[:4], "section": section, "secs": round(dt, 3),
                "ok": res is not None,
                "method": res.method if res else None,
                "conf": res.confidence if res else None,
                "words": len(res.text.split()) if res else 0,
                "err": err,
                "bytes": (DOCS / f"Archives_edgar_data_{cik}_{acc.replace('-', '')}_{pdoc}").stat().st_size,
            })
    print(f"wall: {time.time() - t_all0:.1f}s")
    out = Path(__file__).parent / "probe_periodic.json"
    out.write_text(json.dumps(recs, indent=1))
    print("wrote", out)


if __name__ == "__main__":
    main()
