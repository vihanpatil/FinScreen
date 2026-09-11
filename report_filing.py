"""report_filing.py -- L2.1 of the APP LANE: one static HTML report per filing.

The app lane was ruled by the owner on 2026-09-11 (HANDOFF.md §3, "PERSONAL-USE
DIRECTION RULED"). Identity line, as ruled:

    "A personal filing-reading aid for one user, backed by a bounded, closed
    research study -- analysis with disclosed error, never a score or a
    recommendation."

Boundary sentence, as ruled (council advisory Q2, now binding):

    "The tool may show the owner what a filing says, how a labeler with
    disclosed error read it, and what changed since last time -- it may never
    rank, score, compare, or suggest what to do, even when the only reader is
    the owner."

-----------------------------------------------------------------------------
What this module does (the six ruled features, nothing more)
-----------------------------------------------------------------------------
 1. Header: company, CIK, form, filing date, acceptance datetime, and the
    sections present with their extraction confidence / flags.
 2. Full section text, section by section. A chunk is a CANDIDATE if its
    occurrence array names this accession, but candidacy is not enough: that
    array is the UNION over the chunk's paragraphs, so a chunk that merely
    shares one boilerplate paragraph with this filing is attributed to it
    while most of its words are some other company's. Every candidate
    paragraph is therefore checked for physical CONTAINMENT in this filing's
    own section text (data/filings_e2_v2.parquet, this accession, same
    section) and only contained paragraphs are rendered -- see
    `apply_containment`. 8K_BODY is rendered as text only, tagged not
    evaluable, with no labels (HANDOFF §7: 8K_BODY is not evaluable).
 3. Per-chunk student labels beside each passage, under the SAME section mask
    `features_e2.score_labels` applies -- imported, never restated (see
    `mask_flags` below for how the mask is derived rather than copied).
 4. What changed against the prior same-form filing of the same CIK: NEW /
    REMOVED / UNCHANGED passage sets and newly-appearing red-flag categories.
    Deterministic set arithmetic over the two CONTAINED passage sets (the same
    containment filter is applied to the prior filing first, so NEW and
    REMOVED describe the two filings' texts and not their occurrence arrays);
    no similarity score, no threshold, no ranking.
 5. Point-in-time fundamentals as of the filing date (five families), resolved
    through `numeric_features_e2.resolve_family_value` -> `pit.value_as_of`.
    UNRESOLVED is shown as unresolved; the filed date of the chosen fact is
    printed so a restatement is visible.
 6. The mandatory, NON-COLLAPSIBLE disclosure header. Every number in it is
    READ from a committed artifact at render time, EXCEPT the two E1 IC
    deltas and the three prose percentages, which are module constants pinned
    to their source documents by tests -- no outcome artifact is opened on any
    render path (`test_render_opens_no_outcome_artifact`).

-----------------------------------------------------------------------------
Refusals (ruled; enforced by tests in test_report_filing.py, not by prose)
-----------------------------------------------------------------------------
No score, composite, rank, or cross-company table. No market data of any kind.
No action vocabulary anywhere in the rendered chrome outside the disclosure
block. No alerts. No generated prose summaries -- the student emits JSON; this
module renders labels and the filing's own words. No portfolio import. The
label column the standing hard rule (HANDOFF §7) keeps out of every headline is
not in `LABEL_COLUMNS` and is therefore never read, let alone rendered.

This module imports nothing from the price, outcome, or backtest layer
DIRECTLY. `features_e2` and `numeric_features_e2` -- the two modules the
ruling requires be imported rather than restated -- do pull `controls`, and
`controls` pulls `backtest`, for path constants and helpers, so both are in
`sys.modules` transitively. That closure is pinned by a test, no price-loading
function is reachable from any render path (an AST call-graph test), and no
outcome artifact is opened at render time (a file-open guard).

-----------------------------------------------------------------------------
Determinism
-----------------------------------------------------------------------------
The rendered HTML carries NO wall-clock timestamp, so the same inputs produce a
byte-identical file. Provenance travels as input sha256s instead of a run time.

Cost: $0. No network, no API, no GPU. Standard library + pandas/pyarrow.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

import features_e2 as FE
import numeric_features_e2 as NF

REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
APP_DIR = DATA_DIR / "app"
CACHE_DIR = APP_DIR / "cache"
REPORTS_DIR = APP_DIR / "reports"

CHUNKS_PATH = FE.CHUNKS_PATH
LABELS_PATH = FE.LABELS_PATH
TRAIN_SPLIT_PATH = FE.TRAIN_SPLIT_PATH
CAMPAIGN_MANIFEST = FE.CAMPAIGN_MANIFEST
METADATA_DB = DATA_DIR / "filings_metadata_e2.db"
SECTIONS_PATH = DATA_DIR / "filings_e2_v2.parquet"
# F2's universe ticker-resolution table. E2 carries NO ticker anywhere (see
# features_e2's docstring: "E2 labels carry no ticker by design"), so this is
# the only complete CIK<->ticker map for the 244 companies. Only the four
# identity columns in TICKER_MAP_COLUMNS are ever read from it; it holds no
# market data of any kind, and none is read.
TICKER_MAP_CSV = DATA_DIR / "f2" / "price_ticker_map.csv"
TICKER_MAP_COLUMNS = ["cik", "name", "stratum", "chosen_ticker"]

CACHE_VERSION = "app-index-v2"
CHUNK_INDEX_CACHE = CACHE_DIR / "chunk_index_v1.parquet"

# ---------------------------------------------------------------------------
# Disclosure sources. Every number in the mandatory header is read from one of
# these files at render time. Their sha256s are pinned so a silent change to an
# artifact cannot silently change (or fail to change) the header --
# test_report_filing.py recomputes all of them.
# ---------------------------------------------------------------------------
G2_RESULTS = DATA_DIR / "f4" / "g2" / "results_g2.json"
G2_REPORT = DATA_DIR / "f4" / "g2" / "G2_FINAL_REPORT.md"
V12_RESULTS = DATA_DIR / "hardening" / "spotcheck_v12" / "results_v12.json"
# The eval of the adapter that ACTUALLY labeled this corpus. The campaign
# manifest names adapter cadca849...; this is that adapter's own held-out eval.
# The v1.1 student's 0.487 (finetune/runs/2026-08-22-eval-epoch2) is a
# DIFFERENT model on a different split under a different rubric and is not
# quoted here -- see the status report, §7.1, for the owner question it raised.
STUDENT_EVAL = (REPO_ROOT / "finetune" / "runs" / "2026-08-28-v12-eval-epoch2"
                / "metrics.json")

DISCLOSURE_SOURCES = {
    "data/f4/g2/results_g2.json": G2_RESULTS,
    "data/f4/g2/G2_FINAL_REPORT.md": G2_REPORT,
    "data/hardening/spotcheck_v12/results_v12.json": V12_RESULTS,
    "data/f4/campaign_manifest.json": CAMPAIGN_MANIFEST,
    "finetune/runs/2026-08-28-v12-eval-epoch2/metrics.json": STUDENT_EVAL,
}

DISCLOSURE_SOURCE_SHA256 = {
    "data/f4/g2/results_g2.json":
        "d146e5e43586403001eafa3a9eca47d6be19e2a3e7e319c7992808d9992d3eca",
    "data/f4/g2/G2_FINAL_REPORT.md":
        "a1a96992b24d1e2904313a010b82efa07f44eb9c210d2ce6dc594b8e7e6f1529",
    "data/hardening/spotcheck_v12/results_v12.json":
        "082d00ab247d39410ac85a2f0400446f768f91246e79490a2c0b8b33b034c921",
    "data/f4/campaign_manifest.json":
        "76f6bd609948a57ed9abab3d31c90ab4e2313d66502de6fa0e85ae780ffb0557",
    "finetune/runs/2026-08-28-v12-eval-epoch2/metrics.json":
        "21c3360f38a4f85e4fc8e4c135e7aa1d2790ab0c32fd22eaa77031d17c20aefa",
}

# The ONE constant the F6 branch sentence replaces (council Q4 / ruling item 2).
PREDICTIVE_VALIDITY_TEMPLATE = (
    "E1 (25 companies): no fold-robust text signal "
    "({raw:+.4f} raw / {dedup:+.4f} dedup IC delta); E2: not run"
)

# The two E1 IC deltas the ruled disclosure sentence must carry. They are
# CONSTANTS, not a render-time read: the renderer opens no outcome artifact on
# any path (the council's kill criterion is "report layer found reading an
# outcome table or IC"). The regex that lifted them out of the E1 null report
# now lives in test_report_filing.py, which pins that report's sha256 and
# asserts these two numbers still match it.
E1_IC_DELTA_RAW = 0.0177
E1_IC_DELTA_DEDUP = -0.0097

# Prose-documented constants with no machine-readable source, pinned by a test
# that greps HANDOFF.md for the exact SENTENCES they come from (not for a bare
# "22.2%", which would survive any rewording around it).
#
# All three are E1 measurements and are labelled as such wherever they render:
# the config-sensitivity number is E1's TEACHER (Claude) compared against
# itself across two labeling configs on E1's 4,219-chunk corpus -- it is not a
# measurement of the v1.2 student that labeled THIS corpus; the two self-
# identification numbers are E1 measurements of how often a chunk names its own
# company (REDTEAM_WEEK3.md finding #2), strict and loose method.
CONFIG_SENSITIVITY_TEXT = "22.2%"
CONFIG_SENSITIVITY_COUNT = "935/4,219 chunks"
CONFIG_SENSITIVITY_SUBJECT = (
    "E1's teacher labels, compared against themselves across two labeling "
    "configs on E1's 4,219-chunk corpus -- an E1 TEACHER measurement, not a "
    "measurement of the v1.2 student that labeled this corpus"
)
SELFID_STRICT_TEXT = "26.8%"
SELFID_LOOSE_TEXT = "46.0%"
SELFID_SUBJECT = (
    "measured on E1 (REDTEAM_WEEK3.md finding #2), strict and loose method; "
    "not re-measured on E2"
)
PROSE_CONSTANT_SOURCE = REPO_ROOT / "HANDOFF.md"

# What the sentiment agreement number IS, in the ruling's own terms. The
# artifact's own caveat string renders beside it, verbatim.
SENTIMENT_ESTIMAND = (
    "chunk-level label agreement under the applicability mask -- MD&A and "
    "press-release chunks -- against a model-consensus reference; not "
    "accuracy against human ground truth"
)

IDENTITY_LINE = (
    "A personal filing-reading aid for one user, backed by a bounded, closed "
    "research study — analysis with disclosed error, never a score or a "
    "recommendation."
)
FOOTER_LINE = (
    "Not investment advice. No recommendation. No live capital. "
    "Personal use only. Not for distribution."
)
NO_PRICE_LINE = "No price data is used anywhere in this report."

# Columns read from the two F4 parquets. The distress column ruled out of every
# headline (HANDOFF §7) is deliberately absent and is never loaded.
CHUNK_COLUMNS = [
    "chunk_id", "section_type", "home_cik", "home_company_name",
    "home_accession_number", "home_form", "home_filing_date",
    "home_extraction_status", "home_extraction_confidence",
    "home_extraction_method", "home_flags", "word_count", "n_paragraphs",
    "source_accession_numbers", "n_source_filings",
]
LABEL_COLUMNS = [
    "chunk_id", "sentiment", "guidance_direction", "guidance_applicable",
    "guidance_imputed_none", "schema_valid", "schema_issues", "red_flags",
]

SECTION_ORDER = ["MDA", "RISK_FACTORS", "EX99_PRESS_RELEASE", "8K_BODY"]
SECTION_TITLES = {
    "MDA": "Management's Discussion and Analysis",
    "RISK_FACTORS": "Risk Factors (Item 1A)",
    "EX99_PRESS_RELEASE": "Earnings press release (EX-99.x)",
    "8K_BODY": "8-K body",
}
NOT_EVALUABLE_SECTIONS = {"8K_BODY"}

FUNDAMENTAL_FAMILIES = [
    ("assets", "Total assets"),
    ("revenue", "Revenue"),
    ("net_income", "Net income"),
    ("operating_cash_flow", "Operating cash flow"),
    ("equity", "Total equity"),
]


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _as_list(value) -> list:
    """Arrow list columns arrive as numpy arrays; None means empty."""
    if value is None:
        return []
    return list(value)


# ---------------------------------------------------------------------------
# disclosure block -- every number read from an artifact
# ---------------------------------------------------------------------------
def read_g2_section_zero(path: Path = G2_REPORT) -> str:
    """The first paragraph of G2_FINAL_REPORT.md §0, verbatim.

    §0 is the owner's binding interpretation of the guidance number and travels
    with `guidance_active_precision` wherever it is quoted (G2 §0 itself says
    so). Parsed, never transcribed: the first blockquote paragraph after the
    "## 0." heading.
    """
    lines = path.read_text().splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("## 0."))
    out: list[str] = []
    for ln in lines[start + 1:]:
        if not ln.startswith(">"):
            if out:
                break
            continue
        body = ln[1:].strip()
        if not body:
            if out:
                break
            continue
        out.append(body)
    if not out:
        raise RuntimeError(f"{path}: could not parse the §0 first paragraph")
    return " ".join(out)


def first_sentence(paragraph: str) -> str:
    """The §0 SENTENCE the ruling puts beside every imputed NONE (the full §0
    first paragraph stays in the disclosure header)."""
    head, sep, _ = paragraph.partition(". ")
    return head + "." if sep else paragraph


def load_disclosure() -> dict:
    """Assemble the mandatory disclosure numbers from the committed artifacts."""
    g2 = json.loads(G2_RESULTS.read_text())
    v12 = json.loads(V12_RESULTS.read_text())
    manifest = json.loads(CAMPAIGN_MANIFEST.read_text())
    student_eval = json.loads(STUDENT_EVAL.read_text())

    sent = g2["primary"]["sentiment"]
    guid = g2["primary"]["guidance_direction"]
    gap = g2["guidance_active_precision"]
    fnr = g2["guidance_false_none_rate"]
    rf_student = g2["constants"]["redflag_exact_set_error"]
    rf_teacher = v12["P1_exact_set_error"]

    # k is not stored on the red-flag constant; derive it and refuse a
    # non-integral product rather than rounding a fabricated count into view.
    k_float = rf_student["point"] * rf_student["n"]
    if abs(k_float - round(k_float)) > 1e-6:
        raise RuntimeError("redflag_exact_set_error: point * n is not an integer")

    negative = student_eval["headline"]["sentiment"]["per_class"]["NEGATIVE"]

    adapter_sha = manifest["inputs"]["adapter_sha256_expected"]
    adapter_name = Path(manifest["inputs"]["adapter_path"]).name

    return {
        "labeler": adapter_name,
        "adapter_sha256": adapter_sha,
        "provenance": g2["provenance"],
        "red_flags_status": g2["red_flags_status"],
        "sentiment": {
            "k": sent["k"], "n": sent["n"], "pct": sent["p_hat"] * 100,
            "lo": sent["wilson_lo"] * 100, "hi": sent["wilson_hi"] * 100,
            "verdict": sent["verdict"], "bar": sent["bar"],
            "estimand": SENTIMENT_ESTIMAND,
            "artifact_caveat": sent["caveat"],
            "negative_recall": negative["recall"],
            "negative_recall_support": negative["support"],
            "negative_recall_tp": negative["tp"],
            "negative_recall_source":
                "finetune/runs/2026-08-28-v12-eval-epoch2/metrics.json",
        },
        "guidance": {
            "k": guid["k"], "n": guid["n"], "pct": guid["p_hat"] * 100,
            "lo": guid["wilson_lo"] * 100, "hi": guid["wilson_hi"] * 100,
            "verdict": guid["verdict"], "bar": guid["bar"],
            "active_precision_pct": gap["point"] * 100,
            "active_precision_lo": gap["wilson_lo"] * 100,
            "active_precision_hi": gap["wilson_hi"] * 100,
            "false_none_k": fnr["k"], "false_none_n": fnr["n"],
            "section_zero": read_g2_section_zero(),
            "section_zero_sentence": first_sentence(read_g2_section_zero()),
        },
        "red_flags": {
            "teacher_k": rf_teacher["k"], "teacher_n": rf_teacher["n"],
            "teacher_pct": rf_teacher["point"] * 100,
            "teacher_lo": rf_teacher["wilson_95"][0] * 100,
            "teacher_hi": rf_teacher["wilson_95"][1] * 100,
            "student_k": int(round(k_float)), "student_n": rf_student["n"],
            "student_pct": rf_student["point"] * 100,
            "student_lo": rf_student["ci_lo"] * 100,
            "student_hi": rf_student["ci_hi"] * 100,
            "config_sensitivity": CONFIG_SENSITIVITY_TEXT,
            "config_sensitivity_count": CONFIG_SENSITIVITY_COUNT,
            "config_sensitivity_subject": CONFIG_SENSITIVITY_SUBJECT,
        },
        "predictive_validity": PREDICTIVE_VALIDITY_TEMPLATE.format(
            raw=E1_IC_DELTA_RAW, dedup=E1_IC_DELTA_DEDUP),
        "selfid_strict": SELFID_STRICT_TEXT,
        "selfid_loose": SELFID_LOOSE_TEXT,
        "selfid_subject": SELFID_SUBJECT,
    }


# ---------------------------------------------------------------------------
# the cached chunk index
# ---------------------------------------------------------------------------
def _cache_metadata(shas: dict) -> dict:
    return {
        b"app_cache_version": CACHE_VERSION.encode(),
        b"input_sha256": json.dumps(shas, sort_keys=True).encode(),
    }


def build_cache(verbose: bool = True) -> pd.DataFrame:
    """One-time index over the chunk + label tables (no passage text).

    The two F4 parquets' sha256s are asserted against data/f4/campaign_manifest
    .json before a single row is read -- `features_e2.assert_input_shas` is the
    project's own gate and is called, not reimplemented. Its assertions are
    stamped into the cache's Arrow metadata so a stale cache is detected by
    comparison rather than by mtime.
    """
    assertions: list[dict] = []
    shas = FE.assert_input_shas(assertions)

    chunks = pd.read_parquet(CHUNKS_PATH, columns=CHUNK_COLUMNS)
    labels = pd.read_parquet(LABELS_PATH, columns=LABEL_COLUMNS)
    if not (chunks.chunk_id.values == labels.chunk_id.values).all():
        raise RuntimeError("chunk_id order differs between the two F4 parquets")

    for col in LABEL_COLUMNS[1:]:
        chunks[col] = labels[col].values
    chunks["row_index"] = range(len(chunks))

    # Train-overlap: the two ACCESSION channels of features_e2's definition
    # (see FE.TRAIN_OVERLAP_DEFINITION). The third channel is normalized-text
    # identity; it needs the 788 MB text column, so it is computed per filing
    # at render time over that filing's own chunks instead of being baked here.
    train = pd.read_parquet(TRAIN_SPLIT_PATH, columns=["home_accession_number"])
    train_acc = set(train.home_accession_number)
    chunks["train_overlap_home"] = chunks.home_accession_number.isin(train_acc)
    chunks["train_overlap_source"] = chunks.source_accession_numbers.map(
        lambda accs: any(a in train_acc for a in accs))
    # The union is the definition's accession half; the two halves are kept
    # apart because they say different things on a report: "this passage IS a
    # training passage" versus "the corpus also attributes this passage to a
    # training filing", and the second is inflated by the same union-array
    # effect the containment filter exists to undo.
    chunks["train_overlap_accession"] = (
        chunks.train_overlap_home | chunks.train_overlap_source)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(chunks, preserve_index=False)
    table = table.replace_schema_metadata(_cache_metadata(shas))
    pq.write_table(table, CHUNK_INDEX_CACHE, compression="zstd")
    if verbose:
        print(f"cache built: {CHUNK_INDEX_CACHE} "
              f"({len(chunks):,} rows, {len(assertions)} input assertions passed)")
    assert_positional(chunks)
    return chunks


def load_cache(rebuild: bool = False, verbose: bool = True) -> pd.DataFrame:
    if rebuild or not CHUNK_INDEX_CACHE.exists():
        return build_cache(verbose=verbose)
    meta = pq.ParquetFile(CHUNK_INDEX_CACHE).schema_arrow.metadata or {}
    if meta.get(b"app_cache_version") != CACHE_VERSION.encode():
        return build_cache(verbose=verbose)
    assertions: list[dict] = []
    shas = FE.assert_input_shas(assertions)
    if meta.get(b"input_sha256") != json.dumps(shas, sort_keys=True).encode():
        return build_cache(verbose=verbose)
    index = pd.read_parquet(CHUNK_INDEX_CACHE)
    assert_positional(index)
    return index


def assert_positional(index: pd.DataFrame) -> None:
    """`row_index` IS the corpus row position, so `index.iloc[i]` is chunk i.

    Everything downstream (text streaming, occurrence lookup, the diff) relies
    on that, and a cache written out of order would silently attach the wrong
    passage to the wrong label -- so it is asserted, not assumed.
    """
    if not (index.row_index.to_numpy() == np.arange(len(index))).all():
        raise RuntimeError("chunk index is not in corpus row order")


def occurrence_map(index: pd.DataFrame) -> dict[str, list[int]]:
    """accession -> the row indices of every chunk attributed to that filing.

    The baked `source_accession_numbers` arrays ARE E2's occurrence primitive
    (features_e2's docstring); a chunk's home accession is always among them
    (verified on the corpus: 0 exceptions), so this one map yields both the
    filing's own chunks and the shared paragraphs it inherits.
    """
    out: dict[str, list[int]] = {}
    for ri, accs in zip(index.row_index.to_numpy(), index.source_accession_numbers.values):
        for acc in accs:
            out.setdefault(acc, []).append(int(ri))
    return out


def load_texts(row_indices) -> dict[int, str]:
    """Passage text for the given corpus row positions, streamed with an early
    stop. The text column is never loaded whole."""
    wanted = sorted(set(int(i) for i in row_indices))
    if not wanted:
        return {}
    out: dict[int, str] = {}
    pos, cursor = 0, 0
    for batch in pq.ParquetFile(CHUNKS_PATH).iter_batches(
            batch_size=20000, columns=["text"]):
        end = pos + batch.num_rows
        if cursor < len(wanted) and wanted[cursor] < end:
            col = batch.column("text")
            while cursor < len(wanted) and wanted[cursor] < end:
                out[wanted[cursor]] = col[wanted[cursor] - pos].as_py()
                cursor += 1
        pos = end
        if cursor >= len(wanted):
            break
    return out


# ---------------------------------------------------------------------------
# the section mask -- DERIVED from features_e2, never restated
# ---------------------------------------------------------------------------
SENTIMENT_PROBE = "NEUTRAL"      # must be a key of features_e2.SENTIMENT_MAP
GUIDANCE_PROBE = "MAINTAINED"    # must be a key of features_e2.GUIDANCE_MAP


def mask_flags(frame: pd.DataFrame) -> pd.DataFrame:
    """Per-row booleans saying whether the section mask hides each field.

    The mask itself is not written down here. `features_e2.score_labels` is
    called on a PROBE copy of the frame in which every row carries a label
    value that maps to a number; a NaN in the probe's scored column therefore
    means "this row's field was masked", not "this row had no label". So the
    report's mask is `score_labels` by construction and cannot drift from the
    F5 feature table's mask without this function changing with it.

    The probe only works while its two values still map to numbers, so that is
    asserted first: if `SENTIMENT_MAP` or `GUIDANCE_MAP` ever dropped the probe
    key, every field would read as masked and the report would quietly show no
    labels at all. That failure mode is loud instead.
    """
    for value, mapping, name in ((SENTIMENT_PROBE, FE.SENTIMENT_MAP, "SENTIMENT_MAP"),
                                 (GUIDANCE_PROBE, FE.GUIDANCE_MAP, "GUIDANCE_MAP")):
        if value not in mapping or pd.isna(mapping[value]):
            raise RuntimeError(
                f"the mask probe {value!r} no longer maps to a number under "
                f"features_e2.{name}; every field would read as masked and the "
                "report would silently show no labels at all")
    probe = frame.copy()
    probe["sentiment"] = SENTIMENT_PROBE
    probe["guidance_direction"] = GUIDANCE_PROBE
    scored = FE.score_labels(probe)
    return pd.DataFrame({
        "sentiment_masked": scored.sentiment_num.isna().to_numpy(),
        "guidance_masked": scored.guidance_num.isna().to_numpy(),
    }, index=frame.index)


# ---------------------------------------------------------------------------
# filing lookup
# ---------------------------------------------------------------------------
def db_connect() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{METADATA_DB}?mode=ro", uri=True)


def resolve_ticker(ticker: str) -> int:
    if not TICKER_MAP_CSV.exists():
        raise SystemExit(
            f"--ticker needs {TICKER_MAP_CSV.relative_to(REPO_ROOT)}; it is "
            "missing. Use --cik instead (E2 carries no ticker of its own).")
    tmap = pd.read_csv(TICKER_MAP_CSV, usecols=TICKER_MAP_COLUMNS)
    hit = tmap[tmap.chosen_ticker.fillna("").str.upper() == ticker.upper()]
    if hit.empty:
        raise SystemExit(f"ticker {ticker!r} is not in the E2 universe")
    if len(hit) > 1:
        raise SystemExit(f"ticker {ticker!r} maps to {len(hit)} CIKs; use --cik")
    return int(hit.iloc[0].cik)


def company_filings(cik: int, occ: dict[str, list[int]]) -> pd.DataFrame:
    """Every labeled filing of this CIK, with its metadata, newest first."""
    con = db_connect()
    try:
        rows = pd.read_sql(
            "SELECT accession_number, cik, form, filing_date, report_date, "
            "acceptance_datetime, items, has_earnings_item "
            "FROM filings WHERE cik = ?", con, params=(int(cik),))
    finally:
        con.close()
    rows = rows[rows.accession_number.isin(occ.keys())].copy()
    rows["n_chunks"] = rows.accession_number.map(lambda a: len(occ.get(a, [])))
    return rows.sort_values(["filing_date", "accession_number"],
                            ascending=[False, False]).reset_index(drop=True)


def company_name(cik: int) -> str:
    con = db_connect()
    try:
        row = con.execute(
            "SELECT company_name FROM companies WHERE cik = ?", (int(cik),)).fetchone()
    finally:
        con.close()
    return row[0] if row else f"CIK {cik}"


def prior_same_form(filings: pd.DataFrame, accession: str) -> Optional[pd.Series]:
    """The most recent labeled filing of the same CIK and form whose
    filing_date is STRICTLY earlier. Ties on date break by accession number
    descending, so the choice is deterministic.

    The sort happens HERE rather than being inherited from the caller: relying
    on `company_filings`'s ordering would make this function silently wrong for
    any frame that reached it in a different order.
    """
    here = filings[filings.accession_number == accession]
    if here.empty:
        return None
    row = here.iloc[0]
    earlier = filings[(filings.form == row.form)
                      & (filings.filing_date < row.filing_date)]
    if earlier.empty:
        return None
    earlier = earlier.sort_values(["filing_date", "accession_number"],
                                  ascending=[False, False])
    return earlier.iloc[0]


SECTION_COLUMNS = ["accession_number", "section_type", "word_count",
                   "extraction_method", "extraction_confidence",
                   "extraction_status", "flags", "source_document",
                   "below_length_floor", "text"]


def filing_sections(accession: str, path: Path = SECTIONS_PATH) -> pd.DataFrame:
    """THIS filing's own extracted sections, text included, in ONE read.

    `filters=` pushes the accession predicate into the parquet reader, so the
    628 MB text column is only materialized for this filing's two-or-three
    rows (measured: ~0.9 s, a few tens of KB). This frame is the ground truth
    the containment filter below tests every candidate paragraph against, and
    the per-section extraction record the header table prints.
    """
    if not path.exists():
        return pd.DataFrame(columns=SECTION_COLUMNS)
    table = pq.read_table(path, columns=SECTION_COLUMNS,
                          filters=[("accession_number", "=", accession)])
    return table.to_pandas()


def section_texts(sections: pd.DataFrame) -> dict[str, str]:
    """section_type -> that section's whitespace-collapsed text for ONE filing."""
    if sections is None or sections.empty:
        return {}
    return {str(row.section_type): collapse_whitespace(row.text)
            for row in sections.itertuples()}


def section_records(sections: pd.DataFrame) -> pd.DataFrame:
    """The same frame without the text column, for the header table."""
    if sections is None or sections.empty:
        return pd.DataFrame(columns=[c for c in SECTION_COLUMNS if c != "text"])
    return sections.drop(columns=["text"])


# ---------------------------------------------------------------------------
# fundamentals as-of the filing date
# ---------------------------------------------------------------------------
def fundamentals_panel(cik: int, as_of: str) -> list[dict]:
    """Five point-in-time families, resolved exactly as the F5 numeric feature
    table resolves them: `numeric_features_e2.resolve_family_value` over
    `pit.value_as_of`, with F2's committed per-company concept resolution."""
    resolution = NF.load_resolution({int(cik)})
    facts = NF.load_fundamentals({int(cik)})
    slices = NF.slice_by_cik_tag(facts)
    staleness: list[dict] = []

    panel: list[dict] = []
    for family, label in FUNDAMENTAL_FAMILIES:
        hit = resolution[resolution.family == family]
        if hit.empty or not bool(hit.iloc[0].resolved):
            panel.append({"family": family, "label": label, "state": "unresolved",
                          "detail": "UNRESOLVED for this company in F2's "
                                    "concept resolution"})
            continue
        tags = list(hit.iloc[0].tag_list)
        row, tag = NF.resolve_family_value(slices, tags, int(cik), as_of,
                                           staleness_log=staleness, family=family)
        if row is None:
            stale = [s for s in staleness if s["family"] == family]
            detail = ("no fact was knowable as of this filing date"
                      if not stale else
                      f"the freshest knowable fact ended "
                      f"{stale[-1]['period_end'].date()}, "
                      f"{stale[-1]['days_stale']} days before the filing date, "
                      f"and was discarded as stale")
            panel.append({"family": family, "label": label, "state": "unresolved",
                          "detail": detail})
            continue
        panel.append({
            "family": family, "label": label, "state": "resolved",
            "value": row["value"], "unit": row["unit"], "concept": tag,
            "period_end": str(pd.Timestamp(row["period_end"]).date()),
            "filed": str(pd.Timestamp(row["filed"]).date()),
            "form": row.get("form"), "accession": row.get("accession_number"),
            "days_stale": row.get("_days_stale"),
        })
    return panel


def format_amount(value: float, unit: str) -> str:
    if unit == "USD":
        for scale, suffix in ((1e9, "bn"), (1e6, "m"), (1e3, "k")):
            if abs(value) >= scale:
                return f"{value / scale:,.2f} {suffix} USD"
        return f"{value:,.2f} USD"
    return f"{value:,.4f} {unit}"


# ---------------------------------------------------------------------------
# containment -- the filter that makes "attributed" mean "physically present"
# ---------------------------------------------------------------------------
_WHITESPACE = re.compile(r"\s+")


def collapse_whitespace(text) -> str:
    return _WHITESPACE.sub(" ", "" if text is None else str(text)).strip()


def split_paragraphs(text) -> list[str]:
    """The chunker's own paragraph separator is a blank line."""
    return [p for p in str("" if text is None else text).split("\n\n") if p.strip()]


def contained_paragraphs(text, section_text: str) -> list[str]:
    """The paragraphs of `text` that are physically inside `section_text`.

    A chunk's `source_accession_numbers` array is the UNION over its
    paragraphs (finetune/build_f4_chunks.py's every-occurrence attribution;
    features_e2's docstring records the consequence), so "this accession is in
    the array" only means SOME paragraph of the chunk is in this filing. Taken
    as attribution it renders other companies' words under this company's name
    -- measured on Apple's FY2024 10-K before this filter: 30,706 rendered
    words against 12,355 words of actual MD&A + risk factors, 242 of 417
    paragraphs absent from the filing, and seven passages homed at other
    issuers.

    So membership is decided per PARAGRAPH, by whitespace-collapsed substring
    containment in this filing's own section text. It is a physical test, not
    a similarity score: no threshold, no ranking, no degree.
    """
    if not section_text:
        return []
    out = []
    for para in split_paragraphs(text):
        flat = collapse_whitespace(para)
        if flat and flat in section_text:
            out.append(para)
    return out


def apply_containment(frame: pd.DataFrame, texts: dict[int, str],
                      sections: dict[str, str]) -> tuple[pd.DataFrame, dict[int, str], dict]:
    """Keep only what this filing actually contains.

    Returns `(frame, rendered_texts, stats)`:
      * a chunk whose paragraphs are ALL contained survives whole;
      * a chunk whose paragraphs are PARTLY contained survives carrying only
        its contained paragraphs, and is marked "partial: N of M paragraphs
        are in this filing";
      * a chunk with NO contained paragraph is dropped and never renders.
    """
    empty_stats = {"chunks_attributed": int(len(frame)), "chunks_rendered": 0,
                   "chunks_partial": 0, "chunks_dropped": int(len(frame)),
                   "paragraphs_attributed": 0, "paragraphs_rendered": 0,
                   "words_attributed": 0, "words_rendered": 0,
                   "section_words": sum(len(t.split()) for t in sections.values())}
    if frame.empty:
        empty_stats["chunks_dropped"] = 0
        return frame.assign(n_rendered_paragraphs=[], n_source_paragraphs=[],
                            rendered_word_count=[]), {}, empty_stats

    keep_idx, n_kept, n_all, words = [], [], [], []
    rendered: dict[int, str] = {}
    stats = dict(empty_stats)
    for row in frame.itertuples():
        ri = int(row.row_index)
        raw = texts.get(ri, "")
        paragraphs = split_paragraphs(raw)
        kept = contained_paragraphs(raw, sections.get(str(row.section_type), ""))
        stats["paragraphs_attributed"] += len(paragraphs)
        stats["words_attributed"] += sum(len(p.split()) for p in paragraphs)
        if not kept:
            stats["chunks_dropped"] += 1
            continue
        if len(kept) != len(paragraphs):
            stats["chunks_partial"] += 1
        rendered[ri] = "\n\n".join(kept)
        keep_idx.append(row.Index)
        n_kept.append(len(kept))
        n_all.append(len(paragraphs))
        words.append(sum(len(p.split()) for p in kept))
        stats["paragraphs_rendered"] += len(kept)
        stats["words_rendered"] += words[-1]
    stats["chunks_dropped"] = int(len(frame)) - len(keep_idx)
    stats["chunks_rendered"] = len(keep_idx)

    out = frame.loc[keep_idx].copy()
    out["n_rendered_paragraphs"] = n_kept
    out["n_source_paragraphs"] = n_all
    out["rendered_word_count"] = words
    return out.reset_index(drop=True), rendered, stats


def contained_filing(index: pd.DataFrame, occ: dict[str, list[int]],
                     accession: str,
                     sections: Optional[pd.DataFrame] = None):
    """`filing_frame` + `apply_containment`, the only assembly a render uses.

    Returns `(frame, rendered_texts, raw_texts, stats)`. `raw_texts` is kept
    because the train-overlap channel that hashes passage text has to hash the
    WHOLE chunk -- a trimmed passage is not the corpus object the training
    split contains.
    """
    frame = filing_frame(index, occ, accession)
    texts = load_texts(frame.row_index)
    if sections is None:
        sections = filing_sections(accession)
    kept, rendered, stats = apply_containment(frame, texts,
                                              section_texts(sections))
    return kept, rendered, texts, stats


# ---------------------------------------------------------------------------
# assembling one filing's passages
# ---------------------------------------------------------------------------
def filing_frame(index: pd.DataFrame, occ: dict[str, list[int]],
                 accession: str) -> pd.DataFrame:
    """Every chunk the corpus attributes to `accession` -- the CANDIDATE set.

    Candidacy is occurrence-array membership only. `apply_containment` is what
    turns candidates into the rendered set; nothing but that function decides
    whether a passage is really in this filing.

    Order: section (SECTION_ORDER), then chunks homed in this filing in corpus
    order (which is document order for a filing's own chunks -- verified: each
    filing's home chunks are contiguous in the corpus), then shared paragraphs
    ordered by the filing they were first seen in. The reading order of shared
    paragraphs INSIDE the original document is not recoverable from the chunk
    table, and is not guessed at here.
    """
    rows = sorted(occ.get(accession, []))
    frame = index.iloc[rows].copy()
    if frame.empty:
        return frame
    frame["is_home"] = frame.home_accession_number == accession
    frame["section_rank"] = frame.section_type.map(
        {s: i for i, s in enumerate(SECTION_ORDER)}).fillna(len(SECTION_ORDER))
    frame = frame.sort_values(
        ["section_rank", "is_home", "home_filing_date", "home_accession_number",
         "row_index"],
        ascending=[True, False, True, True, True]).reset_index(drop=True)
    flags = mask_flags(frame)
    frame["sentiment_masked"] = flags.sentiment_masked.to_numpy()
    frame["guidance_masked"] = flags.guidance_masked.to_numpy()
    return frame


def red_flag_categories(frame: pd.DataFrame) -> set[str]:
    cats: set[str] = set()
    for section, flags in zip(frame.section_type, frame.red_flags):
        if section in NOT_EVALUABLE_SECTIONS:
            continue
        for entry in _as_list(flags):
            cats.add(str(entry["category"]))
    return cats


def diff_vs_prior(frame: pd.DataFrame, prior_frame: pd.DataFrame) -> dict:
    """Set arithmetic over the two CONTAINED passage sets; no similarity score.

    Both frames have been through `apply_containment`, so membership means
    "this passage's text is physically in that filing", not "the corpus
    attributed it there". A passage the prior filing merely inherited is
    therefore absent from `prior_frame` and lands in NEW, which is the honest
    answer.

    NEW      = in this filing's text, not in the prior filing's.
    REMOVED  = in the prior filing's text, not in this one's.
    UNCHANGED= in both.
    """
    now_ids = list(frame.chunk_id)
    prior_ids = set(prior_frame.chunk_id) if not prior_frame.empty else set()
    now_set = set(now_ids)
    return {
        "new": frame[~frame.chunk_id.isin(prior_ids)],
        "removed": prior_frame[~prior_frame.chunk_id.isin(now_set)]
                   if not prior_frame.empty else prior_frame,
        "unchanged": frame[frame.chunk_id.isin(prior_ids)],
        "new_red_flag_categories": sorted(
            red_flag_categories(frame) - red_flag_categories(prior_frame)
            if not prior_frame.empty else set()),
    }


def train_overlap(frame: pd.DataFrame, texts: dict[int, str], cik: int,
                  accession: str) -> dict:
    """The banner's inputs, under features_e2's overlap definition.

    Channels 1 and 2 (home accession / any source accession) are baked into the
    cache; channel 3 (normalized-text identity) is computed here over this
    filing's own passages. `FE._sha1_norm` is the same normalizer the F5
    feature table uses.

    `frame` is the CONTAINED frame -- a passage the containment filter dropped
    is not on the page and must not raise the banner's counts -- but `texts`
    is the RAW passage text: channel 3 asks whether this corpus passage IS a
    training passage, and a passage trimmed to its contained paragraphs is no
    longer that corpus object.
    """
    train = pd.read_parquet(TRAIN_SPLIT_PATH,
                            columns=["home_cik", "home_accession_number", "text"])
    train_ciks = set(int(c) for c in train.home_cik.unique())
    train_acc = set(train.home_accession_number)
    train_txt = {FE._sha1_norm(t) for t in train.text}
    text_hits = sum(
        1 for ri in frame.row_index
        if FE._sha1_norm(texts.get(int(ri), "")) in train_txt)
    acc_hits = int(frame.train_overlap_accession.sum()) if not frame.empty else 0
    home_hits = (int(frame.train_overlap_home.sum())
                 if not frame.empty and "train_overlap_home" in frame.columns
                 else 0)
    return {
        "cik_in_train": int(cik) in train_ciks,
        "n_train_ciks": len(train_ciks),
        "accession_in_train": accession in train_acc,
        "n_chunks_accession_channel": acc_hits,
        "n_chunks_home_channel": home_hits,
        "n_chunks_text_channel": text_hits,
        "n_chunks": len(frame),
        "definition": FE.TRAIN_OVERLAP_DEFINITION,
        "fires": bool(int(cik) in train_ciks or accession in train_acc
                      or acc_hits or text_hits),
    }


def train_cik_overlap(cik: int) -> dict:
    """The CIK-only channel, for the index page.

    The index lists filings but shows no passage, so only the company-level
    question can be asked there -- and it MUST be asked: an index for one of
    the 22 training CIKs links to reports whose labels are all memorized fits,
    and a page with no banner reads as though that were not so.
    """
    train = pd.read_parquet(TRAIN_SPLIT_PATH, columns=["home_cik"])
    train_ciks = set(int(c) for c in train.home_cik.unique())
    return {
        "cik_in_train": int(cik) in train_ciks,
        "n_train_ciks": len(train_ciks),
        "accession_in_train": False,
        "n_chunks_accession_channel": 0,
        "n_chunks_home_channel": 0,
        "n_chunks_text_channel": 0,
        "n_chunks": 0,
        "definition": FE.TRAIN_OVERLAP_DEFINITION,
        "fires": bool(int(cik) in train_ciks),
    }


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
CSS = """
:root { --ink:#1d1d1f; --muted:#6b6b70; --line:#d9d9dd; --panel:#ffffff;
        --bg:#f6f6f4; --mark:#3a3a3f; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--ink); line-height:1.55;
       font-family:-apple-system,"Segoe UI",Helvetica,Arial,sans-serif; }
.wrap { max-width: 1040px; margin: 0 auto; padding: 24px 20px 80px; }
h1 { font-size: 21px; margin: 0 0 4px; }
h2 { font-size: 16px; margin: 32px 0 10px; padding-bottom:6px;
     border-bottom:1px solid var(--line); }
h3 { font-size: 14px; margin: 20px 0 8px; }
p { margin: 0 0 10px; }
a { color: var(--mark); }
.disclosure { background:var(--panel); border:2px solid var(--mark);
              border-radius:6px; padding:16px 18px; margin-bottom:26px; }
.disclosure h2 { margin-top:18px; font-size:13px; text-transform:uppercase;
                 letter-spacing:.04em; border:0; padding:0; color:var(--muted); }
.disclosure ul { margin:0 0 10px; padding-left:20px; }
.disclosure li { margin-bottom:7px; font-size:13px; }
.identity { font-style:italic; font-size:13.5px; margin-bottom:12px; }
blockquote { margin:8px 0; padding:8px 12px; border-left:3px solid var(--line);
             background:#fafafa; font-size:12.5px; color:#333; }
.footer-line { font-weight:600; font-size:13px; margin-top:12px;
               padding-top:10px; border-top:1px solid var(--line); }
table { border-collapse:collapse; width:100%; font-size:13px;
        background:var(--panel); margin-bottom:12px; }
th, td { border:1px solid var(--line); padding:6px 9px; text-align:left;
         vertical-align:top; }
th { background:#efefec; font-weight:600; }
.small { font-size:12px; color:var(--muted); }
.passage { background:var(--panel); border:1px solid var(--line);
           border-radius:5px; margin-bottom:14px; }
.passage > summary { padding:8px 12px; cursor:pointer; font-size:12px;
                     color:var(--muted); }
.passage-body { display:flex; gap:0; flex-wrap:wrap; border-top:1px solid var(--line); }
.text-col { flex:1 1 58%; min-width:300px; padding:12px 16px; }
.label-col { flex:1 1 34%; min-width:240px; padding:12px 16px;
             border-left:1px solid var(--line); background:#fbfbfa; }
.text-col p { font-family:Georgia,serif; font-size:14.5px; }
.label-row { font-size:12.5px; margin-bottom:8px; }
.label-row b { display:block; font-size:11px; text-transform:uppercase;
               letter-spacing:.04em; color:var(--muted); font-weight:600; }
.tag { display:inline-block; border:1px solid var(--line); border-radius:10px;
       padding:0 7px; font-size:11px; color:var(--muted); margin-right:4px;
       background:#fff; }
.masked, .none-note { color:var(--muted); font-style:italic; }
details.fold > summary { cursor:pointer; font-size:13px; padding:6px 0; }
"""


def passage_html(row, text: str, accession: str, disclosure_note: str,
                 open_by_default: bool = True) -> str:
    section = row.section_type
    evaluable = section not in NOT_EVALUABLE_SECTIONS
    shared = row.home_accession_number != accession

    n_rendered = getattr(row, "n_rendered_paragraphs", None)
    n_source_paragraphs = getattr(row, "n_source_paragraphs", None)
    words = getattr(row, "rendered_word_count", None)
    if words is None or pd.isna(words):
        words = row.word_count

    summary = [f"{esc(section)}", f"{int(words)} words", f"{esc(row.chunk_id)}"]
    partial = (n_rendered is not None and n_source_paragraphs is not None
               and int(n_rendered) != int(n_source_paragraphs))
    if partial:
        summary.append("partial")
    if shared:
        summary.append("shared boilerplate")
    if not evaluable:
        summary.append("not evaluable")

    paragraphs = "".join(
        f"<p>{esc(p.strip())}</p>" for p in split_paragraphs(text))

    # Markers are the REPORT speaking, so they carry class="small" and stay
    # inside the rendered-output refusal scan; the <p> elements above are the
    # filing's own words and are the only thing that scan removes.
    notes: list[str] = []
    if partial:
        notes.append(
            f'<p class="small">Partial: {int(n_rendered)} of '
            f'{int(n_source_paragraphs)} paragraphs of this corpus passage are '
            "in this filing. The rest belong to other filings the chunker "
            "merged into the same passage and are not shown.</p>")
    if shared:
        # The home filing is named by ACCESSION, form and date. The home
        # company is deliberately NOT named: after containment the text below
        # is this filing's own, and printing "first seen in <other issuer>"
        # read as though this filing contained that issuer's words.
        notes.append(
            f'<p class="small">Deduplicated into an earlier filing: the corpus '
            f"stores this text under {esc(row.home_accession_number)} "
            f"({esc(row.home_form)}, {esc(row.home_filing_date)}), the first "
            "filing it appeared in.</p>")
    n_filings = getattr(row, "n_source_filings", None)
    if n_filings is not None and not pd.isna(n_filings):
        n_filings = int(n_filings)
        notes.append(
            f'<p class="small">This passage appears in {n_filings:,} '
            f"{'filing' if n_filings == 1 else 'filings'} in the corpus.</p>")
    marker = "".join(notes)

    if evaluable:
        labels = label_html(row, disclosure_note)
    else:
        labels = ('<div class="label-row"><b>Labels</b>'
                  '<span class="masked">Not evaluable. The student was trained '
                  'on no examples of this section type, so no label is shown '
                  'for it (standing hard rule).</span></div>')

    return (
        f'<details class="passage"{" open" if open_by_default else ""}>'
        f'<summary>{esc(" · ".join(summary))}</summary>'
        f'<div class="passage-body">'
        f'<div class="text-col">{marker}{paragraphs}</div>'
        f'<div class="label-col">{labels}</div>'
        f"</div></details>"
    )


def label_html(row, disclosure_note: str) -> str:
    issues = [str(i) for i in _as_list(row.schema_issues)]
    invalid = not bool(row.schema_valid)

    def invalid_note(field: str) -> str:
        if invalid and any(i.endswith(field) for i in issues):
            return ' <span class="masked">(invalid enum, not remapped)</span>'
        return ""

    parts: list[str] = []

    if row.sentiment_masked:
        value = ('<span class="masked">not shown — section mask '
                 '(features_e2.score_labels)</span>')
    elif pd.isna(row.sentiment):
        value = '<span class="masked">no value emitted</span>'
    else:
        value = esc(row.sentiment) + invalid_note("sentiment")
    parts.append(f'<div class="label-row"><b>Sentiment</b>{value}</div>')

    if row.guidance_masked:
        applicable = bool(row.guidance_applicable)
        value = ('<span class="masked">not shown — section mask '
                 '(features_e2.score_labels); guidance_applicable='
                 f'{str(applicable).lower()}</span>')
    elif pd.isna(row.guidance_direction):
        value = ('<span class="masked">no value emitted</span>'
                 + invalid_note("guidance_direction"))
    elif str(row.guidance_direction) == "NONE" and bool(row.guidance_imputed_none):
        value = ("NONE (no guidance key emitted)"
                 + f'<div class="none-note">{esc(disclosure_note)}</div>')
    else:
        value = esc(row.guidance_direction) + invalid_note("guidance_direction")
    parts.append(f'<div class="label-row"><b>Guidance direction</b>{value}</div>')

    flags = _as_list(row.red_flags)
    if flags:
        items = "".join(
            f'<div>{esc(f["category"])} · {esc(f["modality"])} '
            f'<span class="tag">exploratory</span></div>'
            for f in sorted(flags, key=lambda f: (str(f["category"]), str(f["modality"]))))
        items += invalid_note("red_flag_category") + invalid_note("red_flag_modality")
    else:
        items = '<span class="masked">none emitted</span>'
    parts.append(f'<div class="label-row"><b>Red flags</b>{items}</div>')
    return "".join(parts)


def disclosure_html(d: dict, overlap: Optional[dict]) -> str:
    s, g, r = d["sentiment"], d["guidance"], d["red_flags"]
    banner = ""
    if overlap and overlap["fires"]:
        reasons = []
        if overlap["cik_in_train"]:
            reasons.append(
                f"this company is one of the {overlap['n_train_ciks']} CIKs in "
                "the v1.2 training split")
        if overlap["accession_in_train"]:
            reasons.append("this accession is in the v1.2 training split")
        if overlap.get("n_chunks_home_channel"):
            reasons.append(
                f"{overlap['n_chunks_home_channel']} of {overlap['n_chunks']} "
                "passages are stored under a filing that is itself in the v1.2 "
                "training split")
        inherited = (overlap["n_chunks_accession_channel"]
                     - overlap.get("n_chunks_home_channel", 0))
        if inherited > 0:
            reasons.append(
                f"{inherited} of {overlap['n_chunks']} passages are also "
                "attributed to a training filing by the corpus (a shared "
                "paragraph, not this filing's own text)")
        if overlap["n_chunks_text_channel"]:
            reasons.append(
                f"{overlap['n_chunks_text_channel']} of {overlap['n_chunks']} "
                "passages are text-identical to a training passage")
        banner = (
            '<li><b>TRAIN-OVERLAP WARNING.</b> The labels below are not '
            "out-of-sample for this filing: " + esc("; ".join(reasons)) + ". "
            "Read every label on this page as a memorized fit, not as a "
            "held-out prediction.</li>")

    return f"""
<section class="disclosure">
  <h1>Disclosure — read this before the report</h1>
  <p class="identity">{esc(IDENTITY_LINE)}</p>
  <ul>
    <li><b>Labeler.</b> Every label on this page is <b>model output throughout</b>: the v1.2 local student
      (<code>{esc(d['labeler'])}</code>, adapter sha256
      <code>{esc(d['adapter_sha256'])}</code>). No human read these passages.
      {esc(d['provenance'])}</li>
    {banner}
    <li><b>Sentiment.</b> {s['k']}/{s['n']} = {s['pct']:.1f}%
      [{s['lo']:.1f}, {s['hi']:.1f}] — <b>{esc(s['verdict'])}</b> at the
      {s['bar']} bar. What that number is: {esc(s['estimand'])}. It is
      <b>model consensus, not human validation</b>.
      <blockquote>{esc(s['artifact_caveat'])}</blockquote>
      NEGATIVE recall {s['negative_recall']:.3f}
      ({s['negative_recall_tp']}/{s['negative_recall_support']}) — this
      labeler's own held-out eval
      (<span class="small">{esc(s['negative_recall_source'])}</span>). Roughly
      half the passages a reference rater called NEGATIVE are not called
      NEGATIVE here.</li>
    <li><b>Guidance direction.</b> {g['k']}/{g['n']} = {g['pct']:.1f}%
      [{g['lo']:.1f}, {g['hi']:.1f}] — <b>{esc(g['verdict'])}</b> at the
      {g['bar']} bar, <b>on the NONE mass only</b>. Active-value precision
      {g['active_precision_pct']:.1f}%
      [{g['active_precision_lo']:.1f}, {g['active_precision_hi']:.1f}];
      false-NONE rate {g['false_none_k']}/{g['false_none_n']}.
      <blockquote>{esc(g['section_zero'])}</blockquote></li>
    <li><b>Red flags are EXPLORATORY / disclosure-only.</b> Teacher exact-set
      error {r['teacher_k']}/{r['teacher_n']} = {r['teacher_pct']:.1f}%
      [{r['teacher_lo']:.1f}, {r['teacher_hi']:.1f}]; student exact-set error
      {r['student_k']}/{r['student_n']} = {r['student_pct']:.1f}%
      [{r['student_lo']:.1f}, {r['student_hi']:.1f}].
      {esc(d['red_flags_status'])}
      <span class="small">Config-sensitivity {esc(r['config_sensitivity_count'])}
      ({esc(r['config_sensitivity'])}) is
      {esc(r['config_sensitivity_subject'])}.</span></li>
    <li><b>Predictive validity.</b> {esc(d['predictive_validity'])}</li>
    <li><b>Self-identification.</b> {esc(d['selfid_strict'])} of chunks (strict
      method) / {esc(d['selfid_loose'])} (loose method) name their own company,
      so the labeler may be reading company identity rather than the passage.
      Known, documented, not fixed.
      <span class="small">Both figures are {esc(d['selfid_subject'])}.</span></li>
    <li><b>Extraction confidence.</b> Every section below carries the
      extraction status, confidence and flags the extractor recorded for it;
      a FLAGGED section may be truncated, mis-anchored, or thin.</li>
    <li><b>{esc(NO_PRICE_LINE)}</b></li>
  </ul>
  <p class="footer-line">{esc(FOOTER_LINE)}</p>
</section>"""


def _rendered_words(frame: pd.DataFrame) -> int:
    """Words actually rendered: the contained-paragraph count where the
    containment filter has run, the whole chunk's count otherwise."""
    if frame is None or len(frame) == 0:
        return 0
    if "rendered_word_count" in frame.columns:
        return int(frame.rendered_word_count.sum())
    return int(frame.word_count.sum())


def sections_table_html(frame: pd.DataFrame, records: pd.DataFrame,
                        accession: str) -> str:
    rows = []
    seen = set()
    home = frame[frame.home_accession_number == accession] if not frame.empty \
        else frame
    for section in SECTION_ORDER:
        rec = records[records.section_type == section] if not records.empty \
            else records
        sub = home[home.section_type == section] if not home.empty else home
        attributed = frame[frame.section_type == section] if not frame.empty else frame
        if (rec is None or len(rec) == 0) and len(attributed) == 0:
            continue
        seen.add(section)
        if rec is not None and len(rec):
            r = rec.iloc[0]
            status, confidence = r["extraction_status"], r["extraction_confidence"]
            method = r["extraction_method"]
            # `r.flags` would resolve to pandas' own Series.flags property.
            flags = ", ".join(str(f) for f in _as_list(r["flags"])) or "—"
            words = f"{int(r['word_count']):,}"
        elif len(sub):
            r = sub.iloc[0]
            status, confidence = r.home_extraction_status, r.home_extraction_confidence
            method = r.home_extraction_method
            flags = ", ".join(str(f) for f in _as_list(r.home_flags)) or "—"
            words = f"{int(_rendered_words(sub)):,} (chunked)"
        else:
            status = confidence = method = "—"
            flags = "no paragraph of this section is homed in this filing"
            words = f"{int(_rendered_words(attributed)):,} (rendered)"
        rows.append(
            f"<tr><td>{esc(SECTION_TITLES.get(section, section))}"
            f'<div class="small">{esc(section)}</div></td>'
            f"<td>{esc(status)}</td><td>{esc(confidence)}</td>"
            f"<td>{esc(method)}</td><td>{esc(flags)}</td>"
            f"<td>{esc(words)}</td>"
            f"<td>{len(attributed)} ({len(sub)} homed here)</td>"
            f"<td>{int(_rendered_words(attributed)):,}</td></tr>")
    if not rows:
        return '<p class="small">No extracted section is recorded for this filing.</p>'
    return (
        "<table><thead><tr><th>Section</th><th>Extraction status</th>"
        "<th>Confidence</th><th>Method</th><th>Flags</th><th>Words</th>"
        "<th>Passages rendered</th><th>Words rendered</th>"
        "</tr></thead><tbody>"
        + "".join(rows) + "</tbody></table>")


def fundamentals_html(panel: list[dict], as_of: str) -> str:
    rows = []
    for item in panel:
        if item["state"] == "unresolved":
            rows.append(
                f'<tr><td>{esc(item["label"])}</td>'
                f'<td class="masked">unresolved</td><td colspan="3" '
                f'class="small">{esc(item["detail"])}</td></tr>')
            continue
        rows.append(
            f'<tr><td>{esc(item["label"])}</td>'
            f'<td>{esc(format_amount(item["value"], item["unit"]))}</td>'
            f'<td>{esc(item["concept"])}</td>'
            f'<td>period ending {esc(item["period_end"])}</td>'
            f'<td class="small">latest filed as of {esc(as_of)}: '
            f'{esc(item["filed"])} ({esc(item["form"])} '
            f'{esc(item["accession"])})</td></tr>')
    return (
        f'<p class="small">Point-in-time as of the filing date {esc(as_of)}: '
        "only facts already filed by that date are visible. Where a "
        "restatement had itself been filed by then, the restated value is the "
        "one shown — the filed date beside each row is how you tell.</p>"
        "<table><thead><tr><th>Family</th><th>Value</th><th>XBRL concept</th>"
        "<th>Period</th><th>Provenance</th></tr></thead><tbody>"
        + "".join(rows) + "</tbody></table>")


def diff_html(diff: dict, prior: Optional[pd.Series], texts: dict[int, str],
              prior_texts: dict[int, str], accession: str,
              disclosure_note: str) -> str:
    if prior is None:
        return ('<p class="small">No earlier labeled filing of the same form '
                "exists for this company in the corpus, so there is nothing to "
                "compare against.</p>")
    head = (f'<p class="small">Compared against {esc(prior.accession_number)} '
            f"({esc(prior.form)}, filed {esc(prior.filing_date)}). Paragraph-level "
            "set arithmetic over the corpus's deduplicated paragraphs: "
            "membership only — nothing here is measured by degree, "
            "thresholded, or ordered.</p>")

    new_cats = diff["new_red_flag_categories"]
    cats = ('<p class="small">No red-flag category appears in this filing that '
            "did not appear in the prior one.</p>") if not new_cats else (
        "<p><b>Red-flag categories appearing that were not in the prior "
        "filing:</b> " + " ".join(
            f'<span class="tag">{esc(c)} · exploratory</span>'
            for c in new_cats) + "</p>")

    def block(title: str, frame: pd.DataFrame, src: dict[int, str],
              acc: str, fold: bool) -> str:
        if frame.empty:
            return f'<h3>{esc(title)} (0)</h3><p class="small">None.</p>'
        body = "".join(
            passage_html(row, src.get(int(row.row_index), ""), acc,
                         disclosure_note, open_by_default=not fold)
            for row in frame.itertuples())
        if fold:
            return (f'<details class="fold"><summary>{esc(title)} '
                    f"({len(frame)}) — collapsed by default</summary>"
                    f"{body}</details>")
        return f"<h3>{esc(title)} ({len(frame)})</h3>{body}"

    return (head + cats
            + block("NEW passages in this filing", diff["new"], texts,
                    accession, fold=False)
            + block("REMOVED — in the prior filing, absent here",
                    diff["removed"], prior_texts, prior.accession_number, fold=True)
            + block("UNCHANGED passages", diff["unchanged"], texts,
                    accession, fold=True))


def page(title: str, body: str) -> str:
    return (
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{esc(title)}</title>\n<style>{CSS}</style>\n</head>\n<body>\n"
        f'<div class="wrap">{body}</div>\n</body>\n</html>\n')


# ---------------------------------------------------------------------------
# renderers
# ---------------------------------------------------------------------------
def render_filing(index: pd.DataFrame, occ: dict[str, list[int]], cik: int,
                  accession: str, out_dir: Path = REPORTS_DIR) -> Path:
    filings = company_filings(cik, occ)
    if accession not in set(filings.accession_number):
        raise SystemExit(
            f"{accession} is not a labeled filing of CIK {cik}. "
            f"Run --index to list what is available.")
    meta = filings[filings.accession_number == accession].iloc[0]
    name = company_name(cik)

    sections = filing_sections(accession)
    records = section_records(sections)
    frame, texts, raw_texts, stats = contained_filing(index, occ, accession,
                                                      sections)

    prior = prior_same_form(filings, accession)
    if prior is not None:
        prior_frame, prior_texts, _, _ = contained_filing(
            index, occ, prior.accession_number)
    else:
        prior_frame, prior_texts = frame.iloc[0:0], {}

    disclosure = load_disclosure()
    overlap = train_overlap(frame, raw_texts, cik, accession)
    imputed_note = disclosure["guidance"]["section_zero_sentence"]

    body = [disclosure_html(disclosure, overlap)]
    body.append(
        f"<h1>{esc(name)} — {esc(meta.form)} filed {esc(meta.filing_date)}</h1>"
        f'<p class="small">CIK {int(cik)} · accession {esc(accession)} · '
        f"accepted {esc(meta.acceptance_datetime)} · period ending "
        f"{esc(meta.report_date)}"
        # `meta.items` would resolve to pandas' own Series.items method.
        + (f" · 8-K items {esc(meta['items'])}" if meta["items"] else "")
        + "</p>")

    body.append("<h2>Sections present</h2>")
    body.append(sections_table_html(frame, records, accession))

    body.append("<h2>Fundamentals as of the filing date</h2>")
    body.append(fundamentals_html(fundamentals_panel(cik, meta.filing_date),
                                  meta.filing_date))

    body.append("<h2>What changed since the prior "
                f"{esc(meta.form)}</h2>")
    body.append(diff_html(diff_vs_prior(frame, prior_frame), prior, texts,
                          prior_texts, accession, imputed_note))

    body.append("<h2>The filing, section by section</h2>")
    body.append(
        '<p class="small">Every passage whose text is physically inside this '
        "filing, with the student's labels beside it. "
        f"{stats['chunks_rendered']:,} of {stats['chunks_attributed']:,} "
        "passages the corpus attributes to this accession survive that check "
        f"({stats['paragraphs_rendered']:,} of "
        f"{stats['paragraphs_attributed']:,} paragraphs, "
        f"{stats['words_rendered']:,} of {stats['words_attributed']:,} words); "
        f"the extractor recorded {stats['section_words']:,} words for these "
        "sections. A passage the corpus deduplicated into an earlier filing is "
        "marked; its position inside this document is not recoverable from the "
        "corpus and is not guessed at.</p>")
    for section in SECTION_ORDER:
        sub = frame[frame.section_type == section]
        if sub.empty:
            continue
        tag = (' <span class="tag">not evaluable — no labels shown</span>'
               if section in NOT_EVALUABLE_SECTIONS else "")
        body.append(f"<h3>{esc(SECTION_TITLES.get(section, section))}{tag}</h3>")
        for row in sub.itertuples():
            body.append(passage_html(row, texts.get(int(row.row_index), ""),
                                     accession, imputed_note))

    body.append(f'<p class="footer-line">{esc(FOOTER_LINE)}</p>')

    out = out_dir / str(int(cik)) / f"{accession}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page(f"{name} {meta.form} {meta.filing_date}", "".join(body)))
    return out


def render_index(index: pd.DataFrame, occ: dict[str, list[int]], cik: int,
                 out_dir: Path = REPORTS_DIR) -> Path:
    filings = company_filings(cik, occ)
    name = company_name(cik)
    disclosure = load_disclosure()

    home_counts = index.home_accession_number.value_counts()
    section_by_row = index.section_type.to_numpy()
    rows, skipped = [], 0
    for row in filings.itertuples():
        homed = int(home_counts.get(row.accession_number, 0))
        if homed == 0:
            # Not one paragraph of this filing is stored under its own
            # accession: every passage the corpus attributes to it was
            # deduplicated into some other filing, so a report for it would be
            # assembled entirely out of other filings' rows. Counted, not
            # linked.
            skipped += 1
            continue
        present = {section_by_row[i] for i in occ.get(row.accession_number, [])}
        sections = ", ".join(s for s in SECTION_ORDER if s in present)
        rows.append(
            f'<tr><td>{esc(row.form)}</td><td>{esc(row.filing_date)}</td>'
            f'<td><a href="{esc(row.accession_number)}.html">'
            f"{esc(row.accession_number)}</a></td>"
            f"<td>{esc(sections)}</td>"
            f"<td>{row.n_chunks} ({homed} homed here)</td></tr>")

    body = [disclosure_html(disclosure, train_cik_overlap(cik))]
    body.append(f"<h1>{esc(name)} — labeled filings</h1>"
                f'<p class="small">CIK {int(cik)} · {len(rows)} filings in '
                "the E2 labeled corpus. Listed by form and date only: this page "
                "carries no label-derived quantity and is not sorted by one.</p>")
    body.append("<table><thead><tr><th>Form</th><th>Filed</th>"
                "<th>Accession</th><th>Sections</th><th>Passages</th>"
                "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>")
    body.append(
        f'<p class="small">{skipped} further labeled '
        f"{'filing has' if skipped == 1 else 'filings have'} no passage stored "
        "under their own accession — every paragraph was deduplicated into an "
        f"earlier filing — so {'it is' if skipped == 1 else 'they are'} counted "
        "here and not listed.</p>")
    body.append(f'<p class="footer-line">{esc(FOOTER_LINE)}</p>')

    out = out_dir / str(int(cik)) / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page(f"{name} labeled filings", "".join(body)))
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Render one static HTML report for a filing already "
                    "labeled in the E2 corpus. Personal use only.")
    who = ap.add_mutually_exclusive_group(required=True)
    who.add_argument("--cik", type=int)
    who.add_argument("--ticker", type=str)
    ap.add_argument("--accession", type=str)
    ap.add_argument("--latest", type=str, metavar="FORM",
                    help="10-K, 10-Q or 8-K")
    ap.add_argument("--index", action="store_true",
                    help="render the company's filing index instead")
    ap.add_argument("--out-dir", type=Path, default=REPORTS_DIR)
    ap.add_argument("--rebuild-cache", action="store_true")
    args = ap.parse_args(argv)

    started = time.time()
    cik = args.cik if args.cik is not None else resolve_ticker(args.ticker)
    index = load_cache(rebuild=args.rebuild_cache)
    occ = occurrence_map(index)

    if args.index:
        out = render_index(index, occ, cik, args.out_dir)
    else:
        accession = args.accession
        if accession is None:
            if not args.latest:
                raise SystemExit("give --accession, --latest FORM, or --index")
            filings = company_filings(cik, occ)
            match = filings[filings.form == args.latest]
            if match.empty:
                raise SystemExit(
                    f"CIK {cik} has no labeled {args.latest} in the corpus")
            accession = match.iloc[0].accession_number
        out = render_filing(index, occ, cik, accession, args.out_dir)

    print(f"{out}  ({time.time() - started:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
