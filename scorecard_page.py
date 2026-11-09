#!/usr/bin/env python3
"""scorecard_page.py -- private HTML pages for the ratified E2 head-1 scorecard.

    python3 scorecard_page.py            every company page + the universe page
    python3 scorecard_page.py --cik N    one company page

Reads ONLY data/f5/head1_scorecard.json (written by backtest_e2.py on the
ratified G3 run, 2026-11-05). It computes nothing: every number on a page is
copied from that JSON, rows keep the JSON's order, and the only ordering this
module applies is alphabetical by company name. The JSON's sha256 is printed on
every page as provenance. No wall clock: the same JSON gives the same bytes.

Personal use only. These pages are not a demonstration surface either: a
per-company historical scorecard stays off every shared surface until the
items in data/legal/ are cleared (SCORECARD_FOOTER_LINE).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Optional

import controls as C
import report_filing as RF
from report_filing import esc, page
from scorecard_e2 import DISCLOSURE_ORDER

SCORECARD_JSON = RF.DATA_DIR / "f5" / "head1_scorecard.json"
COMPANIES_DIR = RF.APP_DIR / "companies"
REPORTS_DIR = RF.REPORTS_DIR

SCORECARD_FOOTER_LINE = (
    "Rendered for the author's personal use only. Not for sharing, not even as "
    "a demonstration: a per-company historical scorecard stays off every shared "
    "surface until the items in data/legal/ are cleared.")
IDENTITY_TEMPLATE = (
    "For each past filing{whose}: what the ratified E2 model would have said, "
    "using fundamentals and prices as they were public at that filing date, and "
    "text labels from a labeler trained in 2026; what the stock then did over "
    "the next {sessions} trading sessions relative to the equal-weighted average "
    "of its universe peers; and whether that call was right. Out-of-fold, "
    "backtested and hypothetical; price return only; no money invested; "
    "descriptive only.")
DISCLOSURE_HEADING = "Disclosures — these travel with every number on this page"
# The labeler can recognise a company and know what happened to it later; the
# figures are report_filing's pinned E1 constants, never retyped here.
SELFID_TEMPLATE = (
    "Self-identification: {strict} of chunks (strict method) / {loose} (loose "
    "method) name their own company, so the labeler, trained in 2026, may "
    "recognise the company and use knowledge of what happened to it later "
    "instead of what the passage says, a look-ahead channel; how often it did "
    "is not known. Both figures are {subject}.")
# Restated from target_e2.py's session chain and scorecard_e2.make_calls.
CALL_RULE_TEMPLATE = (
    "How a call is made. Within each test quarter, and separately for each "
    "column, this filing's out-of-fold model output is placed among the outputs "
    "for every filing of that quarter in the run, across the universe. The top "
    "third is “outperform peers”, the bottom third “underperform "
    "peers”; the middle third, and any group of equal outputs that "
    "straddles a boundary between thirds, is “no call” and leaves the "
    "denominator. A call is right when the sign of the excess return matches it; "
    "an excess of exactly zero is never right. The return window: the "
    "information date is the later of the filing date and the acceptance date "
    "in US Eastern time; the first session that can carry the news is the first "
    "session on or after that date when acceptance came before 16:00 ET, else "
    "the first session after it; the window "
    "opens one session after that and runs {sessions} sessions. The thirds are "
    "drawn across the whole quarter, so a call is a within-quarter statement "
    "relative to peers, never a real-time one.")
LINKED_PAGES_LINE = (
    "A linked accession opens a reading-aid page whose labels were produced now "
    "(2026-11) for the reading aid, not the sealed-corpus labels this run used.")
NO_HIT_RATE = "no hit rate: {n} {calls}, fewer than the {k} the pre-registration requires"
NO_HIT_RATE_SHORT = "no hit rate ({n} {calls} < {k})"
COVERAGE_TEMPLATE = (
    "{n} of the {total} universe companies appear here. The disclosures below "
    "name two of the causes of absence (price censoring: “{clause}”; "
    "extraction coverage); the rest are not decomposed here, and absence can be "
    "correlated with outcomes.")
PRICE_CLAUSE_RE = re.compile(r"\d+ of (\d+) universe members without usable prices")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path = SCORECARD_JSON) -> dict:
    if not path.exists():
        raise SystemExit(f"{path} is missing; it is written only by the ratified "
                         "G3 run (backtest_e2.py) and is git-ignored.")
    data = json.loads(path.read_text())
    missing = [k for k, _ in DISCLOSURE_ORDER if not data["universe"]["disclosures"].get(k)]
    if missing:
        raise SystemExit(f"{path}: disclosures missing {missing}; refusing to render")
    return data


def calls(n: int) -> str:
    return "call" if n == 1 else "calls"


def fmt(value, digits: int = 4) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def ticker_of(entry: dict, companies_dir: Path = COMPANIES_DIR) -> Optional[str]:
    if entry.get("ticker"):
        return entry["ticker"]
    manifest = companies_dir / str(entry["cik"]) / "manifest.json"
    return json.loads(manifest.read_text()).get("ticker") if manifest.exists() else None


def provenance(u: dict, json_path: Path, sha: str) -> str:
    try:
        shown = json_path.resolve().relative_to(RF.REPO_ROOT)
    except ValueError:
        shown = json_path.name
    return (f'<p class="small">Source: <code>{esc(shown)}</code>, sha256 '
            f"<code>{esc(sha)}</code>; generated {esc(u['generated_utc'])} UTC by the "
            f"run itself. Call rule <code>{esc(u['call_rule'])}</code>, tie rule "
            f"<code>{esc(u['tie_rule'])}</code>, correct rule "
            f"<code>{esc(u['correct_rule'])}</code>, intervals "
            f"<code>{esc(u['ci'])}</code>.</p>")


def framing(u: dict, whose: str) -> str:
    """Identity paragraph, then the run's own sentences verbatim, then E2's outcome."""
    quotes = [u["scope_sentence"], u["inference_sentence"], u["prices_sentence"],
              f"Margin ({u['margin']['status']}, {u['margin']['delta_selected']}): "
              f"{u['margin']['note']}",
              "E2 outcome: " + RF.predictive_validity_sentence()]
    identity = IDENTITY_TEMPLATE.format(whose=whose, sessions=C.HOLDING_DAYS)
    selfid = SELFID_TEMPLATE.format(strict=RF.SELFID_STRICT_TEXT,
                                    loose=RF.SELFID_LOOSE_TEXT, subject=RF.SELFID_SUBJECT)
    return (f'<p class="identity">{esc(identity)}</p><p>{esc(selfid)}</p>'
            + "".join(f"<blockquote>{esc(q)}</blockquote>" for q in quotes))


def disclosures(u: dict) -> str:
    items = "".join(f"<li><b>{esc(label)}.</b> {esc(u['disclosures'][key])}</li>"
                    for key, label in DISCLOSURE_ORDER)
    return (f'<section class="disclosure"><h2>{esc(DISCLOSURE_HEADING)}</h2>'
            f"<ul>{items}</ul></section>")


def footer() -> str:
    return f'<p class="footer-line">{esc(SCORECARD_FOOTER_LINE)}</p>'


def summary_html(s: dict, label: str) -> str:
    if s.get("hit_rate") is None:
        head = NO_HIT_RATE.format(n=s["n_calls"], calls=calls(s["n_calls"]),
                                  k=s["min_calls_for_hit_rate"]) + "."
        chance = ""
    else:
        head = (f"{label[:1].upper()}{label[1:]}: {s['n_correct']} of {s['n_calls']} calls right "
                f"({s['n_outperform']} outperform peers, {s['n_underperform']} "
                f"underperform peers) over {s['n_rows']} rows; hit rate "
                f"{fmt(s['hit_rate'])}, 95% Wilson interval [{fmt(s['wilson_lo'])}, "
                f"{fmt(s['wilson_hi'])}].")
        chance = s.get("chance_sentence") or ""
    mix = (f"Outcome mix (share of this company's filings with positive excess): "
           f"{fmt(s.get('outcome_mix'))} over {s['n_filings']} filings — what the "
           "period did, not a benchmark the hit rate is measured against.")
    return "".join(f"<p>{esc(t)}</p>" for t in (head, chance, s.get("denominator"), mix) if t)


def cell(row: dict, block: str) -> str:
    call, result = row[f"{block}_call"], row.get(f"{block}_result")
    return f"{call} ({result})" if result else call


def rows_html(entry: dict, blocks: dict, here: Path) -> str:
    head = "".join(f"<th>{esc(t)}</th>" for t in
                   ["Quarter", "Form", "Filed", "Accession", "Excess return"]
                   + [b["label"] for b in blocks.values()])
    out = []
    for r in entry["rows"]:
        acc = esc(r["accession_number"])
        if (here / f"{r['accession_number']}.html").exists():
            acc = f'<a href="{acc}.html">{acc}</a>'
        cells = "".join(f"<td>{esc(cell(r, b))}</td>" for b in blocks)
        out.append(f"<tr><td>{esc(r['test_quarter'])}</td><td>{esc(r['form'])}</td>"
                   f"<td>{esc(r['filing_date'])}</td><td>{acc}</td>"
                   f"<td>{r['excess_return_pct']:+.2f}%</td>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(out)}</tbody></table>"


def render_company(entry: dict, u: dict, json_path: Path, sha: str,
                   out_dir: Path = REPORTS_DIR, companies_dir: Path = COMPANIES_DIR) -> Path:
    here = out_dir / str(int(entry["cik"]))
    here.mkdir(parents=True, exist_ok=True)
    ticker = ticker_of(entry, companies_dir)
    title = f"{entry['name']}{f' ({ticker})' if ticker else ''} — historical scorecard, E2 head 1"
    s = entry["summary"]
    links = ['<a href="../scorecard.html">all companies</a>']
    if (here / "index.html").exists():
        links.append('<a href="index.html">labeled filings</a>')
    body = [f"<h1>{esc(title)}</h1>",
            f'<p class="small">CIK {int(entry["cik"])} · {" · ".join(links)}</p>',
            framing(u, " of this company"), provenance(u, json_path, sha),
            "<h2>Summary</h2>", summary_html(s, u["blocks"][s["block"]]["label"]),
            "<h2>Universe, for comparison</h2>", blocks_html(u),
            f"<p>{esc(u['chance_sentence'])}</p>",
            "<h2>Filing by filing, in the run's own order</h2>",
            f"<p>{esc(CALL_RULE_TEMPLATE.format(sessions=C.HOLDING_DAYS))}</p>",
            f'<p class="small">{esc(LINKED_PAGES_LINE)}</p>',
            rows_html(entry, u["blocks"], here), disclosures(u), footer()]
    out = here / "scorecard.html"
    out.write_text(page(title, "".join(body)))
    return out


def blocks_html(u: dict) -> str:
    head = "".join(f"<th>{t}</th>" for t in (
        "Block", "Calls", "Outperform", "Underperform", "Correct", "Hit rate",
        "95% Wilson interval", "Chance (from call counts)", "No call (tied)", "Unresolved"))
    rows = "".join(
        f"<tr><td>{esc(b['label'])}</td><td>{b['n_calls']}</td><td>{b['n_outperform']}</td>"
        f"<td>{b['n_underperform']}</td><td>{b['n_correct']}</td><td>{fmt(b['hit_rate'])}</td>"
        f"<td>[{fmt(b['wilson_lo'])}, {fmt(b['wilson_hi'])}]</td>"
        f"<td>{fmt(b['chance_from_call_counts'], 3)}</td>"
        f"<td>{b['n_no_call']} ({b['n_tied_no_call']})</td><td>{b['n_unresolved']}</td></tr>"
        for b in u["blocks"].values())
    return f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"


def company_row(entry: dict, companies_dir: Path) -> str:
    s = entry["summary"]
    rate = (NO_HIT_RATE_SHORT.format(n=s["n_calls"], calls=calls(s["n_calls"]),
                                     k=s["min_calls_for_hit_rate"])
            if s.get("hit_rate") is None else
            f"{fmt(s['hit_rate'])} [{fmt(s['wilson_lo'])}, {fmt(s['wilson_hi'])}]")
    cik = int(entry["cik"])
    correct = "—" if s.get("n_correct") is None else s["n_correct"]
    return (f'<tr><td><a href="{cik}/scorecard.html">{esc(entry["name"])}</a></td>'
            f"<td>{esc(ticker_of(entry, companies_dir) or '')}</td><td>{cik}</td>"
            f"<td>{s['n_calls']}</td><td>{correct}</td><td>{esc(rate)}</td></tr>")


def render_universe(data: dict, json_path: Path, sha: str, out_dir: Path = REPORTS_DIR,
                    companies_dir: Path = COMPANIES_DIR) -> Path:
    u = data["universe"]
    clause = PRICE_CLAUSE_RE.search(u["prices_sentence"])
    if clause is None:
        raise SystemExit("prices_sentence no longer states 'N of M universe members "
                         "without usable prices'; refusing to type the count here")
    title = "E2 head 1 — historical scorecard, every company"
    companies = sorted(data["companies"], key=lambda c: (c["name"].lower(), int(c["cik"])))
    body = [f"<h1>{esc(title)}</h1>", framing(u, ""), provenance(u, json_path, sha),
            "<h2>Universe</h2>", blocks_html(u),
            f"<p>{esc(u['chance_sentence'])}</p>",
            f"<p>{esc(u['outcome_mix_label'].capitalize())}: "
            f"{fmt(u['outcome_mix_positive_excess'])}.</p>",
            "<h2>Companies, alphabetical by name</h2>",
            f"<p>{esc(COVERAGE_TEMPLATE.format(n=u['n_companies'], total=clause.group(1), clause=clause.group(0)))}</p>",
            "<table><thead><tr><th>Company</th><th>Ticker</th><th>CIK</th><th>Calls</th>"
            "<th>Correct</th><th>Hit rate [95% Wilson]</th></tr></thead><tbody>"
            + "".join(company_row(c, companies_dir) for c in companies) + "</tbody></table>",
            disclosures(u), footer()]
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "scorecard.html"
    out.write_text(page(title, "".join(body)))
    return out


def render_all(json_path: Path = SCORECARD_JSON, out_dir: Path = REPORTS_DIR,
               companies_dir: Path = COMPANIES_DIR, cik: Optional[int] = None) -> list[Path]:
    data, sha = load(json_path), sha256(json_path)
    chosen = [c for c in data["companies"] if cik is None or int(c["cik"]) == cik]
    if cik is not None and not chosen:
        raise SystemExit(f"CIK {cik} is not among the {len(data['companies'])} companies "
                         f"in {json_path}")
    pages = [render_company(c, data["universe"], json_path, sha, out_dir, companies_dir)
             for c in chosen]
    if cik is None:
        pages.append(render_universe(data, json_path, sha, out_dir, companies_dir))
    return pages


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cik", type=int)
    a = ap.parse_args(argv)
    pages = render_all(cik=a.cik)
    print(f"{len(pages)} pages written; e.g. {pages[-1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
