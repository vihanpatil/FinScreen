"""text_families_e2.py -- the two ZERO-LABELING text families of E2 (F5 Step 1b).

EXPANSION_PLAN.md §8 item 4 / F5_PLAN.md §2 Step 1: two feature families that
need no student label at all, built directly from the filing text.

  FAMILY A -- year-over-year novelty.  For each scoped filing's
  RISK_FACTORS (Item 1A) and MDA (Item 7) section: the novelty of that
  section against the SAME CIK's most recent PRIOR filing of the SAME
  section type, `novelty = 1 - Jaccard(5-word shingles)` over normalized
  text.  Columns `novelty_risk_factors_yoy`, `novelty_mda_yoy`,
  `prior_gap_days_risk_factors`, `prior_gap_days_mda`; NaN when there is no
  prior.

  FAMILY B -- pooled document embeddings.  Each section is embedded as the
  MEAN of its 256-token window embeddings (capped at the first
  `MAX_WINDOWS_PER_SECTION` windows); the filing embedding is the MEAN over
  its sections.  Model: `sentence-transformers/all-MiniLM-L6-v2` (384-d,
  Apache-2.0), run locally on MPS if available, else CPU.  Column `emb`
  (fixed-width `list<float32>[384]`), with `n_sections_embedded` and
  `n_windows_embedded` beside it.

-----------------------------------------------------------------------
The freeze (F5_PLAN §1) -- what this module does NOT do
-----------------------------------------------------------------------
NOTHING here computes an information coefficient, a correlation, a model
fit, or any feature-versus-outcome association, and nothing here reads a
return.  `data/f5/target_e2.parquet` is opened for FOUR key columns only --
`cik`, `accession_number`, `filing_date`, `in_membership` -- and never for
`target_excess_63`, `subject_return_63` or `benchmark_return_63`.  No price
and no fundamental is read at all.  `test_text_families_e2.py` carries a
source-scan tripwire over this file for association machinery.

-----------------------------------------------------------------------
Point-in-time
-----------------------------------------------------------------------
Family A is the only place where one filing's row sees another filing's
bytes, and the direction is strictly backwards: the comparison partner is
selected with `filing_date` STRICTLY EARLIER than the current filing's
`filing_date` (same CIK, same section type).  `prior_gap_days_* >= 1` is
asserted on the written frame.  Family B touches only the filing's own
text.  No `report_date` is read anywhere in this module.

-----------------------------------------------------------------------
Scope
-----------------------------------------------------------------------
Rows = the IN-MEMBERSHIP core-stratum filings of `data/f5/target_e2.parquet`
that have at least one section in `data/filings_e2_v2.parquet`, joined on
(`cik`, `accession_number`).  Filings with no extracted text get no row (the
three-way join in F5_PLAN §3 decision 4 drops them anyway); the coverage gap
is counted in the manifest, never hidden.

The PRIOR-filing candidate pool for family A is the WHOLE corpus for that
CIK and section type -- including filings outside the membership spells and
outside the scoped set.  Every candidate is a real earlier filing by the
same company, so this is PIT-safe and strictly increases coverage; it is
pinned as an argument (`prior_candidate_pool`) because it is a convention
G3 could rule differently.

-----------------------------------------------------------------------
Frozen modules
-----------------------------------------------------------------------
`controls.py` (and through it `pit.py`, `spec.py`) stay byte-frozen; this
module imports `controls._sha256_file` rather than restating it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import resource
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import controls as C  # frozen; imported, never edited

DATA_DIR = REPO_ROOT / "data"
CORPUS_PATH = DATA_DIR / "filings_e2_v2.parquet"
CAMPAIGN_MANIFEST = DATA_DIR / "f4" / "campaign_manifest.json"
OUT_DIR = DATA_DIR / "f5"
STATUS_DIR = OUT_DIR / "status"
TARGET_PATH = OUT_DIR / "target_e2.parquet"
TARGET_MANIFEST = OUT_DIR / "target_e2_manifest.json"
OUT_PARQUET = OUT_DIR / "text_families_e2.parquet"
OUT_PARTIAL = OUT_DIR / "text_families_e2_partial.parquet"
OUT_MANIFEST = OUT_DIR / "text_families_e2_manifest.json"

# --- pinned arguments -------------------------------------------------------
# Every knob below is written into the manifest verbatim (`ARGS`), because a
# named transform is not a pre-registration (H2: seven implementations of one
# name spanned 0.059).  G3 §1 pins these for the confirmatory block.

SHINGLE_N = 5
NOVELTY_SECTIONS = ("RISK_FACTORS", "MDA")
NOVELTY_COLUMN = {
    "RISK_FACTORS": ("novelty_risk_factors_yoy", "prior_gap_days_risk_factors"),
    "MDA": ("novelty_mda_yoy", "prior_gap_days_mda"),
}
SHINGLE_PRIME = np.uint64(1000003)  # polynomial rolling hash multiplier

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMB_DIM = 384
MAX_SEQ_LENGTH = 256          # the model's own configured maximum
WINDOW_CONTENT_TOKENS = 254   # 256 minus [CLS] and [SEP]: no silent truncation
MAX_WINDOWS_PER_SECTION = 64
EMBED_SECTION_TYPES = ("MDA", "RISK_FACTORS", "EX99_PRESS_RELEASE", "8K_BODY")
ENCODE_BATCH_SIZE = 128
FILINGS_PER_ENCODE_GROUP = 32
CHECKPOINT_EVERY = 500
READ_BATCH_ROWS = 128

OUTPUT_COLUMNS = [
    "cik", "accession_number", "filing_date",
    "novelty_risk_factors_yoy", "novelty_mda_yoy",
    "prior_gap_days_risk_factors", "prior_gap_days_mda",
    "emb", "n_sections_embedded", "n_windows_embedded",
]

_DIGITS_RE = re.compile(r"\d+")


def pinned_args() -> dict:
    """Every argument this module's two families are defined by."""
    return {
        "family_a_novelty": {
            "function": "novelty = 1 - jaccard(shingles(normalize(cur)), "
                        "shingles(normalize(prior)))",
            "shingle_n_words": SHINGLE_N,
            "normalization": "str.lower(); remove all unicode digit runs "
                             "(regex \\d+); split on whitespace and rejoin "
                             "with single spaces (in that order)",
            "tokenization": "whitespace split of the normalized text",
            "shingle_identity": "64-bit polynomial hash of the 5 word ids "
                                f"(id = blake2b-8 of the word, P={int(SHINGLE_PRIME)}, "
                                "arithmetic mod 2**64); set = np.unique of those "
                                "hashes (a shingle's MULTIPLICITY is ignored)",
            "jaccard": "|A ∩ B| / |A ∪ B| over those sets",
            "sections": list(NOVELTY_SECTIONS),
            "prior_rule": "same cik AND same section_type AND filing_date "
                          "STRICTLY EARLIER than the current filing_date; the "
                          "MAXIMUM such filing_date; ties on that date broken "
                          "by the SMALLEST accession_number",
            "prior_candidate_pool": "every row of data/filings_e2_v2.parquet "
                                    "for that cik and section_type (not "
                                    "restricted to in-membership or scoped "
                                    "filings)",
            "nan_rule": "NaN when the filing has no such section, when no "
                        "prior exists, or when either side yields 0 shingles "
                        "(fewer than 5 words after normalization)",
            "prior_gap_days": "(current filing_date - prior filing_date).days",
        },
        "family_b_embeddings": {
            "model_name": MODEL_NAME,
            "dim": EMB_DIM,
            "max_seq_length": MAX_SEQ_LENGTH,
            "window_content_tokens": WINDOW_CONTENT_TOKENS,
            "windowing": "tokenizer(text, add_special_tokens=False) then "
                         "consecutive non-overlapping slices of "
                         f"{WINDOW_CONTENT_TOKENS} token ids, each decoded back "
                         "to text and encoded with the special tokens added by "
                         "the model (254 + [CLS] + [SEP] = 256 = max_seq_length, "
                         "so no window is truncated)",
            "max_windows_per_section": MAX_WINDOWS_PER_SECTION,
            "window_vectors_l2_normalized": True,
            "window_normalization_source": "the model's own Normalize module "
                                           "(all-MiniLM-L6-v2 ships mean "
                                           "pooling + L2 normalize)",
            "section_pooling": "unweighted mean over that section's window "
                               "vectors",
            "filing_pooling": "unweighted mean over that filing's section "
                              "vectors (sections weighted equally regardless "
                              "of length)",
            "renormalize_pooled": False,
            "section_types_embedded": list(EMBED_SECTION_TYPES),
            "encode_batch_size": ENCODE_BATCH_SIZE,
            "dtype": "float32",
        },
        "scope": {
            "rows": "in-membership core-stratum filings of "
                    "data/f5/target_e2.parquet with >= 1 corpus section",
            "join_key": ["cik", "accession_number"],
        },
        "checkpoint_every_filings": CHECKPOINT_EVERY,
    }


# ---------------------------------------------------------------------------
# Provenance -- every input is sha-asserted before it is used
# ---------------------------------------------------------------------------


def assert_input_shas(strict: bool = True) -> dict:
    """Assert the corpus and the target table against their committed pins.

    The corpus sha is pinned by the F4 campaign manifest
    (`inputs.corpus_parquet_sha256`); the target table is pinned by its own
    manifest's `output_sha256`.  A mismatch means the artifact moved under
    us, so it raises.
    """
    measured = {
        "data/filings_e2_v2.parquet": C._sha256_file(CORPUS_PATH),
        "data/f5/target_e2.parquet": C._sha256_file(TARGET_PATH),
    }
    expected = {
        "data/filings_e2_v2.parquet":
            json.loads(CAMPAIGN_MANIFEST.read_text())["inputs"]["corpus_parquet_sha256"],
        "data/f5/target_e2.parquet":
            json.loads(TARGET_MANIFEST.read_text())["output_sha256"],
    }
    mismatches = {k: {"expected": expected[k], "measured": v}
                  for k, v in measured.items() if expected[k] != v}
    if mismatches and strict:
        raise AssertionError("input sha256 mismatch: "
                             + json.dumps(mismatches, indent=2))
    return {
        "measured": measured,
        "expected_sources": {
            "data/filings_e2_v2.parquet": "data/f4/campaign_manifest.json "
                                          "inputs.corpus_parquet_sha256",
            "data/f5/target_e2.parquet": "data/f5/target_e2_manifest.json "
                                         "output_sha256",
        },
        "matches_committed": not mismatches,
    }


# ---------------------------------------------------------------------------
# FAMILY A -- normalization, shingles, Jaccard
# ---------------------------------------------------------------------------

_WORD_ID: Dict[str, int] = {}


def _word_id(word: str) -> int:
    """A deterministic 64-bit id for a word (blake2b-8; NOT python `hash`,
    which is salted per process and would break reproducibility)."""
    wid = _WORD_ID.get(word)
    if wid is None:
        wid = int.from_bytes(
            hashlib.blake2b(word.encode("utf-8"), digest_size=8).digest(), "big")
        _WORD_ID[word] = wid
    return wid


def normalize_text(text: str) -> str:
    """lowercase -> strip digit runs -> collapse whitespace (in that order)."""
    if text is None:
        return ""
    return " ".join(_DIGITS_RE.sub("", text.lower()).split())


def shingle_hashes(text: str, n: int = SHINGLE_N) -> np.ndarray:
    """The SET of n-word shingles of `text`, as sorted unique uint64 hashes.

    Empty (size 0) when the normalized text has fewer than `n` words.
    """
    words = normalize_text(text).split()
    m = len(words) - n + 1
    if m <= 0:
        return np.empty(0, dtype=np.uint64)
    ids = np.fromiter((_word_id(w) for w in words), dtype=np.uint64,
                      count=len(words))
    with np.errstate(over="ignore"):  # wrap-around IS the hash (mod 2**64)
        h = np.zeros(m, dtype=np.uint64)
        for k in range(n):
            h = h * SHINGLE_PRIME + ids[k:k + m]
    return np.unique(h)


def jaccard_from_hashes(a: np.ndarray, b: np.ndarray) -> float:
    """|A ∩ B| / |A ∪ B|; NaN if either side is empty."""
    if a.size == 0 or b.size == 0:
        return float("nan")
    inter = int(np.intersect1d(a, b, assume_unique=True).size)
    union = int(a.size + b.size - inter)
    return inter / union


def novelty_from_texts(current: str, prior: str, n: int = SHINGLE_N) -> float:
    """1 - Jaccard over n-word shingles; NaN if either side has no shingle."""
    return 1.0 - jaccard_from_hashes(shingle_hashes(current, n),
                                     shingle_hashes(prior, n))


def select_prior(index: pd.DataFrame, cik: int, section_type: str,
                 filing_date: pd.Timestamp) -> Optional[pd.Series]:
    """The prior filing's index row: same cik, same section, STRICTLY earlier.

    `index` needs columns cik, section_type, filing_date, accession_number.
    Among candidates the MAXIMUM filing_date wins; ties on that date are
    broken by the SMALLEST accession_number.  None when no candidate exists.
    """
    cand = index[(index["cik"] == cik)
                 & (index["section_type"] == section_type)
                 & (index["filing_date"] < filing_date)]
    if cand.empty:
        return None
    best_date = cand["filing_date"].max()
    cand = cand[cand["filing_date"] == best_date]
    return cand.sort_values("accession_number").iloc[0]


def build_prior_pairs(index: pd.DataFrame, scoped_keys: set) -> pd.DataFrame:
    """Vectorized `select_prior` over every scoped (cik, section) row.

    Returns one row per scoped corpus row of a novelty section, with the
    chosen prior's corpus row id (`prior_row`, -1 when none) and the gap in
    days.  The selection rule is identical to `select_prior` (tested against
    it on synthetic frames): the index is sorted by
    (cik, section_type, filing_date, accession_number), so `searchsorted`
    on filing_date gives the strictly-earlier block and its first row at the
    maximum earlier date is the smallest accession_number at that date.
    """
    idx = index.sort_values(["cik", "section_type", "filing_date",
                            "accession_number"], kind="stable").reset_index(drop=True)
    out = []
    n_ties = 0
    for (cik, sec), g in idx.groupby(["cik", "section_type"], sort=False):
        if sec not in NOVELTY_SECTIONS:
            continue
        dates = g["filing_date"].values
        rows = g["row"].values
        forms = g["form"].values
        for pos in range(len(g)):
            if (cik, g["accession_number"].values[pos]) not in scoped_keys:
                continue
            d = dates[pos]
            hi = int(np.searchsorted(dates, d, side="left"))  # first row with date >= d
            if hi == 0:
                out.append((cik, g["accession_number"].values[pos], sec,
                            forms[pos], int(rows[pos]), -1, np.nan))
                continue
            best_date = dates[hi - 1]
            lo = int(np.searchsorted(dates, best_date, side="left"))
            if hi - 1 > lo:
                n_ties += 1
            gap = (pd.Timestamp(d) - pd.Timestamp(best_date)).days
            out.append((cik, g["accession_number"].values[pos], sec,
                        forms[pos], int(rows[pos]), int(rows[lo]), float(gap)))
    pairs = pd.DataFrame(out, columns=["cik", "accession_number", "section_type",
                                       "form", "row", "prior_row",
                                       "prior_gap_days"])
    pairs.attrs["n_ties_on_prior_date"] = n_ties
    return pairs


# ---------------------------------------------------------------------------
# FAMILY B -- windowing and pooling (pure; the model is injected)
# ---------------------------------------------------------------------------


def token_windows(tokenizer, text: str,
                  window_tokens: int = WINDOW_CONTENT_TOKENS,
                  max_windows: int = MAX_WINDOWS_PER_SECTION) -> Tuple[List[str], int]:
    """Split `text` into at most `max_windows` decoded windows of
    `window_tokens` content tokens each.

    Returns (windows, n_windows_uncapped) so the cap's bite is measurable.
    """
    ids = tokenizer(text, add_special_tokens=False)["input_ids"]
    n_uncapped = int(math.ceil(len(ids) / window_tokens)) if ids else 0
    n = min(n_uncapped, max_windows)
    windows = [tokenizer.decode(ids[i * window_tokens:(i + 1) * window_tokens])
               for i in range(n)]
    return windows, n_uncapped


def pool_mean(vectors: Sequence[np.ndarray]) -> np.ndarray:
    """Unweighted mean of a non-empty sequence of equal-length vectors."""
    return np.mean(np.vstack(vectors).astype(np.float64), axis=0)


def pool_filing(section_vectors: Sequence[np.ndarray]) -> np.ndarray:
    """Filing vector = unweighted mean over SECTION vectors (not windows)."""
    return pool_mean(section_vectors).astype(np.float32)


def load_model(device: Optional[str] = None):
    """Load the pinned sentence-transformers model (local cache; no training)."""
    from sentence_transformers import SentenceTransformer
    import torch
    from transformers.utils import logging as hf_logging

    # the corpus sections are far longer than 256 tokens BY DESIGN (that is
    # what the windowing is for); silence the tokenizer's per-section
    # "sequence longer than the maximum" notice, which is not about us.
    hf_logging.set_verbosity_error()

    if device is None:
        device = "mps" if torch.backends.mps.is_available() else "cpu"
    model = SentenceTransformer(MODEL_NAME, device=device,
                                local_files_only=True)
    model.max_seq_length = MAX_SEQ_LENGTH
    model.eval()
    return model, device


def model_provenance() -> dict:
    """Model name, resolved revision hash, and the sha256 of the weight file."""
    from huggingface_hub import snapshot_download

    path = Path(snapshot_download(MODEL_NAME, local_files_only=True))
    revision = path.name  # snapshots/<commit sha> in the default HF cache
    weights = path / "model.safetensors"
    return {
        "name": MODEL_NAME,
        "revision": revision,
        "license": "Apache-2.0",
        "cache_path": str(path),
        "in_repo": str(path).startswith(str(REPO_ROOT)),
        "weight_file": "model.safetensors",
        "weight_file_sha256": C._sha256_file(weights),
        "weight_file_bytes": weights.stat().st_size,
        "tokenizer_json_sha256": C._sha256_file(path / "tokenizer.json"),
    }


def package_versions() -> dict:
    import torch
    import transformers
    import sentence_transformers
    import tokenizers
    import huggingface_hub
    return {
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "pyarrow": pa.__version__,
        "torch": torch.__version__,
        "sentence-transformers": sentence_transformers.__version__,
        "transformers": transformers.__version__,
        "tokenizers": tokenizers.__version__,
        "huggingface-hub": huggingface_hub.__version__,
    }


# ---------------------------------------------------------------------------
# Corpus access -- streamed, never a whole-text-column read
# ---------------------------------------------------------------------------

META_COLUMNS = ["cik", "accession_number", "section_type", "filing_date", "form"]


def load_corpus_index(path: Path = CORPUS_PATH) -> pd.DataFrame:
    """The corpus metadata (no `text`), with a positional `row` id."""
    idx = pq.read_table(path, columns=META_COLUMNS).to_pandas()
    idx["filing_date"] = pd.to_datetime(idx["filing_date"])
    idx["row"] = np.arange(len(idx), dtype=np.int64)
    return idx


def stream_texts(needed_rows: set, path: Path = CORPUS_PATH,
                 batch_rows: int = READ_BATCH_ROWS):
    """Yield (row_id, text) for the needed rows only, streaming by batch.

    The `text` column is never materialized whole: `iter_batches` hands back
    `batch_rows` rows at a time and each batch is dropped after use.
    """
    f = pq.ParquetFile(path)
    row = 0
    for batch in f.iter_batches(batch_size=batch_rows, columns=["text"]):
        col = batch.column("text")
        for i in range(batch.num_rows):
            if row in needed_rows:
                yield row, col[i].as_py()
            row += 1


# ---------------------------------------------------------------------------
# Scope
# ---------------------------------------------------------------------------


def load_scope(target_path: Path = TARGET_PATH,
               corpus_index: Optional[pd.DataFrame] = None,
               limit_filings: Optional[int] = None) -> Tuple[pd.DataFrame, dict]:
    """The scoped filings: in-membership core rows that have corpus text.

    Reads FOUR columns of the target table and no return column (the freeze).
    """
    t = pd.read_parquet(target_path,
                        columns=["cik", "accession_number", "filing_date",
                                 "in_membership"])
    t = t[t["in_membership"]].copy()
    t["filing_date"] = pd.to_datetime(t["filing_date"])
    idx = corpus_index if corpus_index is not None else load_corpus_index()
    with_text = set(map(tuple, idx[["cik", "accession_number"]].values.tolist()))
    keys = list(zip(t["cik"].tolist(), t["accession_number"].tolist()))
    t["has_text"] = [k in with_text for k in keys]
    counts = {
        "n_in_membership_target_rows": int(len(t)),
        "n_scoped_filings_with_text": int(t["has_text"].sum()),
        "n_in_membership_filings_without_text": int((~t["has_text"]).sum()),
    }
    scope = (t[t["has_text"]]
             .sort_values(["filing_date", "cik", "accession_number"],
                          kind="stable")
             .reset_index(drop=True)
             [["cik", "accession_number", "filing_date"]])
    if limit_filings is not None:
        scope = scope.head(limit_filings).reset_index(drop=True)
        counts["limit_filings"] = int(limit_filings)
    return scope, counts


# ---------------------------------------------------------------------------
# Family A driver
# ---------------------------------------------------------------------------


def compute_novelty(scope: pd.DataFrame, index: pd.DataFrame,
                    corpus_path: Path = CORPUS_PATH) -> Tuple[pd.DataFrame, dict]:
    """Family A over the scoped filings.  Two passes: pair selection on
    metadata, then ONE streamed pass over the texts those pairs need."""
    t0 = time.time()
    scoped_keys = set(zip(scope["cik"].tolist(), scope["accession_number"].tolist()))
    pairs = build_prior_pairs(index, scoped_keys)
    t_pairs = time.time() - t0

    needed = set(pairs["row"].tolist()) | {r for r in pairs["prior_row"].tolist() if r >= 0}
    t1 = time.time()
    shingles: Dict[int, np.ndarray] = {}
    for row, text in stream_texts(needed, corpus_path):
        shingles[row] = shingle_hashes(text)
    t_shingle = time.time() - t1

    t2 = time.time()
    vals = {}
    n_empty_side = 0
    detail = []
    for rec in pairs.itertuples(index=False):
        col, gap_col = NOVELTY_COLUMN[rec.section_type]
        d = vals.setdefault((rec.cik, rec.accession_number), {})
        if rec.prior_row < 0:
            d[col], d[gap_col] = np.nan, np.nan
            continue
        j = jaccard_from_hashes(shingles[rec.row], shingles[rec.prior_row])
        if math.isnan(j):
            n_empty_side += 1
        d[col] = np.nan if math.isnan(j) else 1.0 - j
        d[gap_col] = rec.prior_gap_days
        detail.append((rec.section_type, rec.form, rec.prior_gap_days, d[col],
                       min(shingles[rec.row].size, shingles[rec.prior_row].size)))
    t_compare = time.time() - t2

    nov = pd.DataFrame(
        [{"cik": k[0], "accession_number": k[1], **v} for k, v in vals.items()],
        columns=(["cik", "accession_number"]
                 + [c for pair in NOVELTY_COLUMN.values() for c in pair]))
    for _, (col, gap_col) in NOVELTY_COLUMN.items():
        for c in (col, gap_col):
            if c not in nov.columns:
                nov[c] = np.nan
    det = pd.DataFrame(detail, columns=["section_type", "form", "gap_days",
                                        "novelty", "min_shingles"])
    diagnostics = {
        "n_pairs_considered": int(len(pairs)),
        "n_with_prior": int((pairs["prior_row"] >= 0).sum()),
        "n_without_prior": int((pairs["prior_row"] < 0).sum()),
        "n_ties_on_prior_date": int(pairs.attrs.get("n_ties_on_prior_date", 0)),
        "n_nan_from_empty_shingle_side": int(n_empty_side),
        "n_sections_shingled": int(len(shingles)),
        # What the "most recent prior filing" rule actually compares, measured:
        # for a quarterly filer the prior filing is the previous QUARTER, not
        # the previous year.  The column name says "yoy"; the gap census below
        # is the measured object (an open question for G3, not a defect this
        # module decides).
        "prior_gap_days_census": {
            sec: {"n": int(len(g)),
                  "min": float(g["gap_days"].min()),
                  "p25": float(g["gap_days"].quantile(0.25)),
                  "median": float(g["gap_days"].median()),
                  "p75": float(g["gap_days"].quantile(0.75)),
                  "max": float(g["gap_days"].max()),
                  "median_by_form_of_the_current_filing": {
                      str(k): float(v) for k, v in
                      g.groupby("form")["gap_days"].median().items()}}
            for sec, g in det.groupby("section_type")} if len(det) else {},
        # Degenerate values concentrate on SHORT sections (10-Q Item 1A stubs
        # such as "no material changes"): a stub that shares no 5-gram with a
        # full section scores 1.0, and an unchanged stub scores 0.0.
        "novelty_degenerate_census": {
            sec: {"n": int(len(g)),
                  "n_exactly_0": int((g["novelty"] == 0.0).sum()),
                  "n_exactly_1": int((g["novelty"] == 1.0).sum()),
                  "n_pairs_with_a_side_under_50_shingles":
                      int((g["min_shingles"] < 50).sum()),
                  "min_shingles_median": float(g["min_shingles"].median())}
            for sec, g in det.groupby("section_type")} if len(det) else {},
        "runtimes_seconds": {
            "pair_selection": round(t_pairs, 2),
            "stream_and_shingle": round(t_shingle, 2),
            "jaccard": round(t_compare, 2),
        },
    }
    return nov, diagnostics


# ---------------------------------------------------------------------------
# Family B driver
# ---------------------------------------------------------------------------


def _empty_partial() -> pd.DataFrame:
    return pd.DataFrame({"cik": pd.Series(dtype="int64"),
                         "accession_number": pd.Series(dtype="object"),
                         "emb": pd.Series(dtype="object"),
                         "n_sections_embedded": pd.Series(dtype="int64"),
                         "n_windows_embedded": pd.Series(dtype="int64")})


def compute_embeddings(scope: pd.DataFrame, index: pd.DataFrame,
                       model=None, device: Optional[str] = None,
                       corpus_path: Path = CORPUS_PATH,
                       partial_path: Path = OUT_PARTIAL,
                       checkpoint_every: int = CHECKPOINT_EVERY,
                       resume: bool = True,
                       progress: bool = True) -> Tuple[pd.DataFrame, dict]:
    """Family B over the scoped filings, checkpointed every
    `checkpoint_every` filings so a crash resumes where it stopped."""
    done = _empty_partial()
    if resume and partial_path.exists():
        done = pd.read_parquet(partial_path)
    done_keys = set(zip(done["cik"].tolist(), done["accession_number"].tolist()))

    if model is None:
        model, device = load_model(device)
    tokenizer = model.tokenizer

    sec = index[index["section_type"].isin(EMBED_SECTION_TYPES)]
    by_filing: Dict[Tuple[int, str], List[Tuple[str, int]]] = {}
    for cik, acc, stype, row in zip(sec["cik"], sec["accession_number"],
                                    sec["section_type"], sec["row"]):
        by_filing.setdefault((cik, acc), []).append((stype, int(row)))

    todo = [k for k in zip(scope["cik"].tolist(), scope["accession_number"].tolist())
            if k not in done_keys]
    needed = {r for k in todo for _, r in by_filing.get(k, [])}
    texts: Dict[int, str] = {}

    results = list(done.itertuples(index=False, name=None))
    t0 = time.time()
    n_windows_total = int(done["n_windows_embedded"].sum()) if len(done) else 0
    n_capped_sections = 0
    n_windows_uncapped = 0
    section_type_counts: Dict[str, int] = {}
    n_done_here = 0

    def flush_group(group: List[Tuple[int, str]]):
        nonlocal n_windows_total, n_capped_sections, n_windows_uncapped, n_done_here
        wins: List[str] = []
        owner: List[Tuple[int, int]] = []  # (filing position in group, section ordinal)
        per_filing_sections: List[int] = [0] * len(group)
        for gi, key in enumerate(group):
            for stype, row in sorted(by_filing.get(key, []), key=lambda x: x[1]):
                w, n_unc = token_windows(tokenizer, texts[row])
                if not w:
                    continue
                n_windows_uncapped += n_unc
                if n_unc > MAX_WINDOWS_PER_SECTION:
                    n_capped_sections += 1
                section_type_counts[stype] = section_type_counts.get(stype, 0) + 1
                sec_ord = per_filing_sections[gi]
                per_filing_sections[gi] += 1
                owner.extend([(gi, sec_ord)] * len(w))
                wins.extend(w)
        if wins:
            vecs = model.encode(wins, batch_size=ENCODE_BATCH_SIZE,
                                convert_to_numpy=True, show_progress_bar=False)
        else:
            vecs = np.empty((0, EMB_DIM), dtype=np.float32)
        buckets: Dict[Tuple[int, int], List[np.ndarray]] = {}
        for (gi, so), v in zip(owner, vecs):
            buckets.setdefault((gi, so), []).append(v)
        for gi, key in enumerate(group):
            svecs = [pool_mean(buckets[(gi, so)])
                     for so in range(per_filing_sections[gi])]
            nw = sum(len(buckets[(gi, so)]) for so in range(per_filing_sections[gi]))
            if not svecs:
                continue
            results.append((key[0], key[1], pool_filing(svecs).astype(np.float32),
                            len(svecs), int(nw)))
            n_windows_total += int(nw)
            n_done_here += 1

    group: List[Tuple[int, str]] = []
    pending_rows: set = set()
    last_ckpt = 0
    text_iter = stream_texts(needed, corpus_path)
    # Texts are streamed in corpus order, so they are collected first and then
    # consumed in scope order; only the needed rows are held.
    for row, text in text_iter:
        texts[row] = text

    for key in todo:
        group.append(key)
        if len(group) >= FILINGS_PER_ENCODE_GROUP:
            flush_group(group)
            for k in group:
                for _, r in by_filing.get(k, []):
                    texts.pop(r, None)
            group = []
            if n_done_here - last_ckpt >= checkpoint_every:
                _write_partial(results, partial_path)
                last_ckpt = n_done_here
                if progress:
                    rate = n_done_here / max(time.time() - t0, 1e-9)
                    print(f"  … {n_done_here}/{len(todo)} filings "
                          f"({rate:.1f} filings/s, "
                          f"{n_windows_total} windows) checkpointed",
                          flush=True)
    if group:
        flush_group(group)
    _write_partial(results, partial_path)

    emb = pd.DataFrame(results, columns=["cik", "accession_number", "emb",
                                         "n_sections_embedded",
                                         "n_windows_embedded"])
    elapsed = time.time() - t0
    diagnostics = {
        "device": device,
        "n_filings_embedded_this_run": int(n_done_here),
        "n_filings_resumed_from_partial": int(len(done)),
        "n_windows_this_run": int(n_windows_total - (int(done["n_windows_embedded"].sum()) if len(done) else 0)),
        "n_windows_total": int(emb["n_windows_embedded"].sum()) if len(emb) else 0,
        "n_sections_embedded_total": int(emb["n_sections_embedded"].sum()) if len(emb) else 0,
        # THIS RUN only: sections embedded before a resume point were counted
        # by the run that embedded them and are not recounted here.
        "n_sections_hitting_the_window_cap_this_run": int(n_capped_sections),
        "n_windows_uncapped_this_run": int(n_windows_uncapped),
        "sections_embedded_by_type_this_run": section_type_counts,
        "runtime_seconds": round(elapsed, 1),
        "throughput_windows_per_second": round(
            (n_windows_total - (int(done["n_windows_embedded"].sum()) if len(done) else 0))
            / max(elapsed, 1e-9), 1),
        "throughput_filings_per_second": round(n_done_here / max(elapsed, 1e-9), 2),
    }
    return emb, diagnostics


def _write_partial(results: List[tuple], path: Path) -> None:
    df = pd.DataFrame(results, columns=["cik", "accession_number", "emb",
                                        "n_sections_embedded",
                                        "n_windows_embedded"])
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


# ---------------------------------------------------------------------------
# Assembly, assertions, output
# ---------------------------------------------------------------------------


def to_arrow(frame: pd.DataFrame) -> pa.Table:
    """The output table, with `emb` as a FIXED-WIDTH list<float32>[384]."""
    flat = np.concatenate([np.asarray(v, dtype=np.float32)
                           for v in frame["emb"]]) if len(frame) else \
        np.empty(0, dtype=np.float32)
    emb = pa.FixedSizeListArray.from_arrays(pa.array(flat, type=pa.float32()),
                                            EMB_DIM)
    arrays = {
        "cik": pa.array(frame["cik"].to_numpy(np.int64), type=pa.int64()),
        "accession_number": pa.array(frame["accession_number"].tolist(),
                                     type=pa.string()),
        "filing_date": pa.array(pd.to_datetime(frame["filing_date"]),
                                type=pa.timestamp("ns")),
        "emb": emb,
        "n_sections_embedded": pa.array(
            frame["n_sections_embedded"].to_numpy(np.int64), type=pa.int64()),
        "n_windows_embedded": pa.array(
            frame["n_windows_embedded"].to_numpy(np.int64), type=pa.int64()),
    }
    for c in ("novelty_risk_factors_yoy", "novelty_mda_yoy",
              "prior_gap_days_risk_factors", "prior_gap_days_mda"):
        arrays[c] = pa.array(frame[c].to_numpy(np.float64), type=pa.float64())
    return pa.table({c: arrays[c] for c in OUTPUT_COLUMNS})


def assert_output_invariants(frame: pd.DataFrame) -> dict:
    """Every invariant this module promises, measured on the written frame."""
    measured = {}
    assert list(frame.columns) == OUTPUT_COLUMNS, list(frame.columns)
    dup = frame.duplicated(["cik", "accession_number"]).sum()
    assert dup == 0, f"{dup} duplicate (cik, accession_number) rows"
    measured["n_rows"] = int(len(frame))
    measured["n_duplicate_keys"] = int(dup)

    # PIT: the comparison partner is strictly earlier, so every gap is >= 1 day.
    for col in ("prior_gap_days_risk_factors", "prior_gap_days_mda"):
        g = frame[col].dropna()
        bad = int((g < 1).sum())
        assert bad == 0, f"{bad} rows with {col} < 1 (prior not strictly earlier)"
        measured[f"min_{col}"] = float(g.min()) if len(g) else None
        measured[f"n_{col}_non_null"] = int(len(g))

    # Novelty is a similarity complement: it lives in [0, 1].
    for col in ("novelty_risk_factors_yoy", "novelty_mda_yoy"):
        v = frame[col].dropna()
        assert v.between(0.0, 1.0).all(), f"{col} outside [0, 1]"
        measured[f"n_{col}_non_null"] = int(len(v))
        measured[f"{col}_min"] = float(v.min()) if len(v) else None
        measured[f"{col}_max"] = float(v.max()) if len(v) else None
        measured[f"{col}_mean"] = float(v.mean()) if len(v) else None
        measured[f"{col}_median"] = float(v.median()) if len(v) else None

    # A novelty value exists if and only if a gap exists (same pair).
    for nov, gap in (("novelty_risk_factors_yoy", "prior_gap_days_risk_factors"),
                     ("novelty_mda_yoy", "prior_gap_days_mda")):
        mismatch = int((frame[nov].notna() & frame[gap].isna()).sum())
        assert mismatch == 0, f"{mismatch} rows with {nov} but no {gap}"

    # Embeddings: fixed width, finite, at least one section and one window.
    widths = {len(v) for v in frame["emb"]}
    assert widths == {EMB_DIM}, widths
    assert all(np.isfinite(np.asarray(v)).all() for v in frame["emb"])
    assert (frame["n_sections_embedded"] >= 1).all()
    assert (frame["n_windows_embedded"] >= frame["n_sections_embedded"]).all()
    measured["emb_widths"] = sorted(widths)
    measured["n_sections_embedded_total"] = int(frame["n_sections_embedded"].sum())
    measured["n_windows_embedded_total"] = int(frame["n_windows_embedded"].sum())
    norms = np.linalg.norm(np.vstack([np.asarray(v) for v in frame["emb"]]), axis=1)
    measured["emb_l2_norm"] = {"min": float(norms.min()), "max": float(norms.max()),
                               "mean": float(norms.mean())}
    return measured


def build(limit_filings: Optional[int] = None, device: Optional[str] = None,
          out_parquet: Path = OUT_PARQUET, out_manifest: Path = OUT_MANIFEST,
          partial_path: Path = OUT_PARTIAL, strict_sha: bool = True,
          resume: bool = True, checkpoint_every: int = CHECKPOINT_EVERY,
          write: bool = True) -> Tuple[pd.DataFrame, dict]:
    if (write and limit_filings is not None
            and Path(out_parquet) == OUT_PARQUET):
        raise RuntimeError(
            f"REFUSED: limit_filings={limit_filings} is a debug/smoke run and may not "
            f"overwrite the production artifact {OUT_PARQUET}. A truncated table under the "
            "production name would silently become a downstream input whose manifest claims "
            "full coverage. Give an explicit --out prefix (or out_parquet=) to write it "
            "somewhere else.")
    t_start = time.time()
    shas = assert_input_shas(strict=strict_sha)
    t_sha = time.time() - t_start

    t0 = time.time()
    index = load_corpus_index()
    scope, scope_counts = load_scope(corpus_index=index,
                                     limit_filings=limit_filings)
    t_load = time.time() - t0

    nov, nov_diag = compute_novelty(scope, index)
    emb, emb_diag = compute_embeddings(scope, index, device=device,
                                       partial_path=partial_path,
                                       checkpoint_every=checkpoint_every,
                                       resume=resume)

    frame = (scope.merge(nov, on=["cik", "accession_number"], how="left")
                  .merge(emb, on=["cik", "accession_number"], how="left"))
    frame = frame[frame["emb"].notna()].reset_index(drop=True)
    frame = frame[OUTPUT_COLUMNS]
    measured = assert_output_invariants(frame)

    coverage = dict(scope_counts)
    coverage["n_rows_written"] = int(len(frame))
    coverage["n_distinct_ciks"] = int(frame["cik"].nunique())
    coverage["filing_date_min"] = str(frame["filing_date"].min().date())
    coverage["filing_date_max"] = str(frame["filing_date"].max().date())
    for col in ("novelty_risk_factors_yoy", "novelty_mda_yoy"):
        coverage[f"n_{col}_present"] = int(frame[col].notna().sum())
        coverage[f"share_{col}_present"] = round(
            float(frame[col].notna().mean()), 4)

    manifest = {
        "artifact": (str(out_parquet.relative_to(REPO_ROOT))
                     if str(out_parquet).startswith(str(REPO_ROOT))
                     else str(out_parquet)),
        "module": "text_families_e2.py",
        "module_sha256": C._sha256_file(Path(__file__)),
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "families": "EXPANSION_PLAN §8 item 4 / F5_PLAN §2 Step 1: (A) YoY "
                    "Item 1A / Item 7 novelty; (B) pooled document embeddings",
        "freeze": {
            "no_ic_computed": True,
            "no_correlation_or_model_fit_computed": True,
            "target_columns_read": ["cik", "accession_number", "filing_date",
                                    "in_membership"],
            "return_columns_read": [],
            "note": "F5_PLAN §1: no E2 feature-versus-outcome association may "
                    "exist before data/f5/G3_RATIFIED.json.",
        },
        "network_calls": "0 at build time (the embedding model is read from "
                         "the local huggingface cache; it was downloaded once)",
        "inputs": shas,
        "arguments": pinned_args(),
        "model": model_provenance(),
        "package_versions": package_versions(),
        "coverage": coverage,
        "family_a_diagnostics": nov_diag,
        "family_b_diagnostics": emb_diag,
        "output_invariants_measured": measured,
        "runtimes_seconds": {
            "sha_assert": round(t_sha, 2),
            "load_index_and_scope": round(t_load, 2),
            "family_a_total": round(sum(nov_diag["runtimes_seconds"].values()), 2),
            "family_b_total": emb_diag["runtime_seconds"],
            "total": round(time.time() - t_start, 1),
        },
        "peak_rss_gb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9, 2),
        "output_sha256": None,
    }

    if write:
        out_parquet.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(to_arrow(frame), out_parquet)
        manifest["output_sha256"] = C._sha256_file(out_parquet)
        out_manifest.write_text(json.dumps(manifest, indent=2, default=str))
    return frame, manifest


def main(argv: Optional[Sequence[str]] = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit-filings", type=int, default=None,
                    help="debug/smoke only: cap the number of scoped filings. "
                         "REFUSES to write the production artifact; pass --out")
    ap.add_argument("--out", default=None,
                    help="output path PREFIX for a non-production run: writes "
                         "PREFIX.parquet, PREFIX_manifest.json and "
                         "PREFIX_partial.parquet. Required with --limit-filings")
    ap.add_argument("--device", default=None, choices=[None, "mps", "cpu"])
    ap.add_argument("--no-resume", action="store_true",
                    help="ignore any existing partial checkpoint")
    args = ap.parse_args(argv)

    paths = {}
    if args.out:
        prefix = Path(args.out)
        paths = {"out_parquet": prefix.with_name(prefix.name + ".parquet"),
                 "out_manifest": prefix.with_name(prefix.name + "_manifest.json"),
                 "partial_path": prefix.with_name(prefix.name + "_partial.parquet")}

    frame, man = build(limit_filings=args.limit_filings, device=args.device,
                       resume=not args.no_resume, **paths)
    print(f"rows written: {len(frame)}  "
          f"ciks: {man['coverage']['n_distinct_ciks']}")
    print(f"novelty present: RISK_FACTORS "
          f"{man['coverage']['n_novelty_risk_factors_yoy_present']}  "
          f"MDA {man['coverage']['n_novelty_mda_yoy_present']}")
    print(f"embeddings: {man['family_b_diagnostics']['n_windows_total']} windows "
          f"on {man['family_b_diagnostics']['device']} at "
          f"{man['family_b_diagnostics']['throughput_windows_per_second']} windows/s")
    print(f"runtimes: {json.dumps(man['runtimes_seconds'])}")
    print(f"wrote {man['artifact']} ({str(man['output_sha256'])[:12]}…)")


if __name__ == "__main__":
    main()
