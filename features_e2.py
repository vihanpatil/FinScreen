"""features_e2.py -- the TEXT side of the E2 feature table (F5 Step 1).

Writes `data/f5/text_features_e2.parquet`: one row per (cik,
accession_number) filing, carrying the 22 pre-registered text features under
the SAME definitions as E1's `features.py` (comparability), plus the two G2
provenance shares. Numeric fundamentals, prices and the return target are
SEPARATE modules (`target_e2.py` and the numeric module); nothing here reads
a price or a fundamental, and NOTHING here computes an information
coefficient, a correlation, or any feature-versus-outcome association --
F5_PLAN.md §1 (the freeze) forbids it until `data/f5/G3_RATIFIED.json`
exists.

E1's `features.py`, `backtest.py`, `diagnose.py`, `spec.py`, `pit.py` and
`controls.py` are byte-frozen. This module IMPORTS the E1 definitions it
reuses (`SENTIMENT_MAP`, `GUIDANCE_MAP`, `RED_FLAG_CATEGORIES`,
`TEXT_SECTION_TYPES`, `TEXT_FEATURE_NAMES_NON_REDFLAG`,
`RED_FLAG_FEATURE_NAMES`) rather than restating them, so a definition can
only drift if E1 drifts. It also imports `controls._sha256_file` and the
three E2 input paths for the provenance block.

-----------------------------------------------------------------------
Unit of observation and the company key
-----------------------------------------------------------------------
One row per (cik, accession_number); `filing_date` and `form` ride along.
**CIK is the company key end to end.** E2 labels carry no ticker by design,
and E1's accession->ticker 1:1 map (`features.build_accession_to_company_map`)
has no E2 analogue. Measured on this corpus: 14,446 filings, 176 core CIKs,
and no accession number maps to more than one CIK (0 violations).

-----------------------------------------------------------------------
Every-occurrence attribution -- the baked arrays ARE the primitive
-----------------------------------------------------------------------
A label attaches to EVERY filing its paragraph(s) occur in, not only the
"home" filing it was deduplicated into (HANDOFF §3, 2026-08-11). In E1 that
rule was re-derivable from `data/paragraph_occurrence_map.parquet`.

**There is no E2 occurrence map.** The parallel arrays baked into the
corpus -- `source_accession_numbers`, `source_filing_dates`, `source_forms`
(labels + chunks, verified identical) and `source_ciks` (chunks only) -- are
the primitive: they are the only statement of E2 occurrence attribution that
exists, and they cannot be cross-checked against a second artifact the way
E1's could. This module explodes them positionally and states that
limitation rather than implying a verification it cannot perform.
`source_tickers` (labels) is a DEDUPLICATED per-chunk list and is NOT
parallel to the occurrence arrays; it is never read here.

No backward flow (E1's `attach_company_and_verify_no_backward_flow`), restated
for E2: no occurrence may attach to a filing dated BEFORE its own chunk's
home filing date. E1 raised on `occurrence_filing_date < home_filing_date`
after resolving ownership through the accession->ticker map; E2 resolves
ownership from `source_ciks` and enforces the identical date predicate.
Measured here: 0 violations over all 854,933 frame occurrences. This is the
property that makes every-occurrence attribution a coverage fix and not a
look-ahead shortcut: every occurrence carries its own real filing date, and
the text of an attributed chunk is physically present in the filing it is
attributed to, so no information dated after a filing's own filing_date can
enter that filing's text features.

A measured attribution property that G3 must see (NOT a defect this module
decides): a chunk's occurrence set is the UNION over its paragraphs, so a
company-specific passage that also contains one widely-shared boilerplate
paragraph inherits that paragraph's whole occurrence set. 5,706 frame chunks
(1.80%) have occurrences under >1 CIK, and 99,636 of 854,933 occurrence rows
(11.65%) attach a chunk to a filing of a DIFFERENT company than its home.
The extreme case is a Wells Fargo press-release chunk carrying a generic
forward-looking-statements sentence: 6,220 filings across 169 CIKs. E1 saw
one such case; E2 sees this. The per-filing diagnostic `cross_cik_share` is
written so the disposition is an owner ruling at G3, not a silent default.

-----------------------------------------------------------------------
Section masks (G2 §3.4) -- applied BEFORE aggregation
-----------------------------------------------------------------------
The G2 spot-check filed a blocker against `features.py:596-604`: those four
aggregations have no section filter. That was harmless on E1 (its teacher
never emitted off-matrix fields, `features.py:1159`) and is FALSE on E2's
student labels. Discharged here, not in `features.py`:

  * `sentiment` nulled on RISK_FACTORS -- 4,177 stored values masked
    (NEUTRAL 3,452 / NEGATIVE 688 / POSITIVE 37).
  * `guidance_direction` nulled on MDA and RISK_FACTORS -- 2,826 masked
    (2,803 MDA + 23 RISK_FACTORS), of which 230 are ACTIVE values that
    `GUIDANCE_MAP` would otherwise have scored at +/-1/0.

Both counts are asserted against the G2 census, not assumed.

-----------------------------------------------------------------------
`guidance_applicable`, and nulls that stay null
-----------------------------------------------------------------------
Guidance is read only where the stored `guidance_applicable` flag is true --
explicitly, as its own predicate, even though after the section mask the two
are coextensive on this corpus (asserted). Branching is on the STORED label
columns, never on `schema_valid` (the G2 implementer trap: `schema_valid ==
false` does not imply a null guidance value -- 1 of the 23 invalid rows
carries a usable one).

Nulls are nulls. Nothing is remapped or imputed here. The 23 schema
violations are disclosure counts only: 17 guidance-enum nulls (all EX99,
applicable, `guidance_imputed_none = false`), 4 red-flag-category and 2
red-flag-modality pair drops.

Imputed NONEs (`guidance_imputed_none`, 48,790 rows = 51.18% of the 95,335
guidance-applicable rows corpus-wide; 48,293 of 94,545 in the frame) are
NONE by the F4 writer rule and are counted as NONE -- i.e. exactly as a
stored NONE: `GUIDANCE_MAP` has no "NONE" key, so they are excluded from
`guidance_signed_mean` and do not set `guidance_any_present`. That is E1's
semantics preserved, and it is disclosed, not hidden.

-----------------------------------------------------------------------
Frame
-----------------------------------------------------------------------
The frame is the 317,081-row corpus minus the 790 8K_BODY chunks =
316,291 rows, matching G2's frame exactly (F5_PLAN §3 decision 9 default:
exclude; the student was trained on 0 8K_BODY examples). `share_chunks_8k_body`
is therefore identically 0.0 and is written but tagged `dropped` in the
feature dictionary, never confirmatory, never exploratory.

-----------------------------------------------------------------------
Feature partition (F5_PLAN §3 decision 3; owner ruling 2026-08-27)
-----------------------------------------------------------------------
confirmatory (8): the 9 legacy non-red-flag columns minus share_chunks_8k_body.
exploratory (13): every red-flag column. The DEMOTE pre-commitment fired on
the v1.2 teacher spot-check; these student red flags reproduce a teacher
measured at 42.00% exact-set error. They are computed, kept and disclosed --
never confirmatory.
Caveat constants are read from `results_g2.json` and
`spotcheck_v12/results_v12.json` at build time. E1's 36.6% / 63.4% strings
are NEVER carried onto Qwen labels.

Cost: $0. No network, no API, no GPU.
"""

from __future__ import annotations

import hashlib
import json
import re
import string
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from controls import (
    FUNDAMENTALS_PATH,
    METADATA_DB,
    PRICES_PATH,
    _sha256_file,
)
from features import (
    GUIDANCE_MAP,
    RED_FLAG_CATEGORIES,
    RED_FLAG_FEATURE_NAMES,
    SENTIMENT_MAP,
    TEXT_FEATURE_NAMES_NON_REDFLAG,
    TEXT_SECTION_TYPES,
)

REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
F4_DIR = DATA_DIR / "f4"
F5_DIR = DATA_DIR / "f5"

CAMPAIGN_MANIFEST = F4_DIR / "campaign_manifest.json"
LABELS_PATH = F4_DIR / "labels_e2_v1.parquet"
CHUNKS_PATH = F4_DIR / "chunks_v1.parquet"
TRAIN_SPLIT_PATH = REPO_ROOT / "finetune" / "splits_v12" / "train.parquet"
G2_RESULTS_PATH = F4_DIR / "g2" / "results_g2.json"
V12_SPOTCHECK_PATH = DATA_DIR / "hardening" / "spotcheck_v12" / "results_v12.json"

OUT_PARQUET = F5_DIR / "text_features_e2.parquet"
OUT_MANIFEST = F5_DIR / "text_features_e2_manifest.json"
OUT_DICTIONARY = F5_DIR / "feature_dictionary_e2.json"

# `finetune/splits_v12/train.parquet` is not covered by campaign_manifest.json;
# its sha is pinned by data/f4/g2/build_draw_g2.py INPUT_SHA256 (2026-09-06).
TRAIN_SPLIT_SHA256 = "5e56076e3948cf9598b6cf61ad7307961735c19af2a0932f981ea6ee3dd4cb10"
TRAIN_SPLIT_ROWS = 5736

# ---------------------------------------------------------------------------
# Pre-registered census constants -- every one is ASSERTED, never assumed.
# Sources: data/f4/g2/G2_SPOTCHECK_design.md §2.5 / §3.4, data/f4/g2/
# results_g2.json frame_checks, data/f4/campaign_manifest.json totals.
# ---------------------------------------------------------------------------
N_CORPUS = 317081
N_FRAME = 316291
N_8K_BODY = 790
N_SENTIMENT_MASKED = 4177                      # all RISK_FACTORS
N_GUIDANCE_MASKED = 2826                       # 2,803 MDA + 23 RISK_FACTORS
N_GUIDANCE_MASKED_MDA = 2803
N_GUIDANCE_MASKED_RF = 23
N_GUIDANCE_MASKED_ACTIVE = 230
N_APPLICABLE_CORPUS = 95335
N_IMPUTED_NONE_CORPUS = 48790                  # 51.18% of applicable
N_APPLICABLE_FRAME = 94545
N_GUIDANCE_ENUM_NULL = 17                      # applicable, not imputed, stored null
N_RF_CATEGORY_DROPS = 4
N_RF_MODALITY_DROPS = 2
N_SCHEMA_INVALID = 23
N_TRAIN_OVERLAP = 14342                        # on the 316,291-row frame
N_SELFID = 146958                              # 46.46% of the frame
SECTION_COUNTS_FRAME = {"MDA": 172098, "EX99_PRESS_RELEASE": 94545, "RISK_FACTORS": 49648}

# G2 §10.1 / build_draw_g2.py -- reimplemented here (two independent
# implementations of one definition; a mismatch is a reportable finding).
SELFID_STOP = {
    "inc", "inc.", "corp", "corp.", "corporation", "company", "co", "co.",
    "the", "of", "and", "group", "holdings", "holding", "ltd", "llc", "plc",
    "&", "/de/", "international", "industries", "systems", "technologies",
    "com",
}
TRAIN_OVERLAP_DEFINITION = (
    "overlap(row) = row.home_accession_number in train_acc or any(a in train_acc "
    "for a in row.source_accession_numbers) or sha1(normalize(row.text)) in "
    "train_txt, where train_acc / train_txt come from finetune/splits_v12/"
    "train.parquet and normalize = collapse whitespace, strip, lower "
    "(G2 §2.5 / build_draw_g2.py). Paragraph-id joins are FORBIDDEN: E1 ids are "
    "'P-...' and E2's are 'E2P-...', so an id-join returns a structurally "
    "meaningless 0."
)
SELFID_DEFINITION = (
    "selfid(row) is true iff the first token of the row's home company name that "
    "is longer than 2 characters (after stripping surrounding punctuation) and "
    "not in the generic-suffix stop list, lowercased, occurs in lower(text)."
)

CONFIRMATORY_FEATURES = [f for f in TEXT_FEATURE_NAMES_NON_REDFLAG if f != "share_chunks_8k_body"]
EXPLORATORY_FEATURES = list(RED_FLAG_FEATURE_NAMES)
DROPPED_FEATURES = ["share_chunks_8k_body"]
DIAGNOSTIC_COLUMNS = [
    "n_chunks_risk_factors", "n_chunks_mda", "n_chunks_ex99_press_release",
    "train_overlap_share", "selfid_share", "cross_cik_share",
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _sha1_norm(text: str) -> str:
    return hashlib.sha1(_normalize(text).encode("utf-8")).hexdigest()


def _distinctive_token(name: str) -> str:
    """First company-name token that is not a generic suffix (G2 §5.1)."""
    for tok in str(name).split():
        low = tok.strip(string.punctuation + "\\").lower()
        if len(low) > 2 and low not in SELFID_STOP:
            return low
    return ""


def _check(assertions: list[dict], name: str, ok: bool, measured, expected=None) -> None:
    """Record an assertion WITH its measured value, then raise if it failed."""
    assertions.append({
        "name": name,
        "passed": bool(ok),
        "measured": measured,
        "expected": expected,
    })
    if not ok:
        raise AssertionError(f"{name}: measured={measured!r} expected={expected!r}")


# ---------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------
def assert_input_shas(assertions: list[dict]) -> dict:
    """Every large artifact's sha256 is asserted against the committed
    manifest before a single row is read (controls.provenance() pattern)."""
    manifest = json.loads(CAMPAIGN_MANIFEST.read_text())
    want_labels = manifest["parquet"]["sha256"]
    want_chunks = manifest["inputs"]["chunks_parquet"]["sha256"]

    got_labels = _sha256_file(LABELS_PATH)
    got_chunks = _sha256_file(CHUNKS_PATH)
    got_train = _sha256_file(TRAIN_SPLIT_PATH)
    _check(assertions, "sha256:labels_e2_v1.parquet", got_labels == want_labels,
           got_labels, want_labels)
    _check(assertions, "sha256:chunks_v1.parquet", got_chunks == want_chunks,
           got_chunks, want_chunks)
    _check(assertions, "sha256:finetune/splits_v12/train.parquet",
           got_train == TRAIN_SPLIT_SHA256, got_train, TRAIN_SPLIT_SHA256)
    _check(assertions, "campaign_manifest_COMPLETE", manifest.get("COMPLETE") is True,
           manifest.get("COMPLETE"), True)
    _check(assertions, "campaign_manifest_rows", manifest["n_rows_written"] == N_CORPUS,
           manifest["n_rows_written"], N_CORPUS)
    return {
        "data/f4/labels_e2_v1.parquet": got_labels,
        "data/f4/chunks_v1.parquet": got_chunks,
        "finetune/splits_v12/train.parquet": got_train,
        "data/f4/campaign_manifest.json": _sha256_file(CAMPAIGN_MANIFEST),
    }


def load_corpus(assertions: list[dict]) -> pd.DataFrame:
    """Positional join of the label columns onto the chunk columns.

    Text is NOT loaded here -- it is streamed once, later, for the provenance
    flags only (788 MB of passage text; nothing else needs it).
    """
    labels = pd.read_parquet(LABELS_PATH, columns=[
        "chunk_id", "section_type", "sentiment", "guidance_direction",
        "guidance_applicable", "guidance_imputed_none", "schema_valid",
        "schema_issues", "parse_ok", "red_flags",
        "source_accession_numbers", "source_filing_dates", "source_forms",
    ])
    chunks = pd.read_parquet(CHUNKS_PATH, columns=[
        "chunk_id", "section_type", "home_cik", "home_company_name",
        "home_accession_number", "home_filing_date", "home_stratum",
        "source_ciks", "source_accession_numbers", "source_filing_dates",
        "source_forms", "n_source_filings",
    ])
    _check(assertions, "corpus_rows", len(labels) == N_CORPUS and len(chunks) == N_CORPUS,
           [len(labels), len(chunks)], [N_CORPUS, N_CORPUS])
    _check(assertions, "chunk_id_unique", bool(chunks.chunk_id.is_unique), True, True)
    same = bool((labels.chunk_id.values == chunks.chunk_id.values).all())
    _check(assertions, "chunk_id_set_and_order_equal", same, same, True)
    _check(assertions, "section_type_agrees_across_parquets",
           bool((labels.section_type.values == chunks.section_type.values).all()), True, True)
    _check(assertions, "parse_ok_all", bool(labels.parse_ok.all()), True, True)
    _check(assertions, "home_stratum_all_core",
           set(chunks.home_stratum.unique()) == {"core"},
           sorted(chunks.home_stratum.unique()), ["core"])

    # the occurrence primitive: labels and chunks must agree element-for-element
    # on the three arrays both carry (source_ciks exists only in chunks).
    for col in ("source_accession_numbers", "source_filing_dates", "source_forms"):
        mismatches = int(sum(
            1 for a, b in zip(labels[col].values, chunks[col].values)
            if list(a) != list(b)))
        _check(assertions, f"source_arrays_identical:{col}", mismatches == 0,
               mismatches, 0)

    df = chunks
    for col in ("sentiment", "guidance_direction", "guidance_applicable",
                "guidance_imputed_none", "schema_valid", "schema_issues", "red_flags"):
        df[col] = labels[col].values
    return df


def build_frame(df: pd.DataFrame, assertions: list[dict]) -> pd.DataFrame:
    """Corpus minus 8K_BODY -- G2's frame, F5_PLAN §3 decision 9 default."""
    n_8k = int((df.section_type == "8K_BODY").sum())
    frame = df[df.section_type != "8K_BODY"].reset_index(drop=True)
    _check(assertions, "frame_8k_body_excluded", n_8k == N_8K_BODY, n_8k, N_8K_BODY)
    _check(assertions, "frame_rows", len(frame) == N_FRAME, len(frame), N_FRAME)
    got = frame.section_type.value_counts().to_dict()
    _check(assertions, "frame_section_counts", got == SECTION_COUNTS_FRAME,
           got, SECTION_COUNTS_FRAME)
    return frame


# ---------------------------------------------------------------------------
# section masks + the applicable filter
# ---------------------------------------------------------------------------
def score_labels(frame: pd.DataFrame) -> pd.DataFrame:
    """The masks and the applicable filter, as one pure transform.

      * `sentiment` is nulled on RISK_FACTORS before SENTIMENT_MAP is applied.
      * `guidance_direction` is nulled on MDA / RISK_FACTORS, AND read only
        where the stored `guidance_applicable` flag is true, before
        GUIDANCE_MAP is applied.
      * Branching is on the stored label columns only -- never `schema_valid`.
      * "NONE" (stored or imputed) and null both leave `guidance_num` NaN:
        GUIDANCE_MAP has no "NONE" key. Nothing is remapped.
    """
    out = frame.copy()
    sentiment = out.sentiment.where(out.section_type != "RISK_FACTORS")
    guidance = out.guidance_direction.where(
        ~out.section_type.isin(["MDA", "RISK_FACTORS"])
        & out.guidance_applicable.fillna(False))
    out["sentiment_num"] = sentiment.map(SENTIMENT_MAP)
    out["guidance_num"] = guidance.map(GUIDANCE_MAP)
    return out


def apply_masks(frame: pd.DataFrame, assertions: list[dict]) -> tuple[pd.DataFrame, dict]:
    """`score_labels` plus the pre-registered census assertions (G2 §3.4).

    Returns the scored frame and a census dict of everything that was masked,
    filtered or left null.
    """
    out = frame.copy()

    sent_mask = (out.section_type == "RISK_FACTORS") & out.sentiment.notna()
    n_sent_masked = int(sent_mask.sum())
    masked_values = out.loc[sent_mask, "sentiment"].value_counts().to_dict()
    _check(assertions, "mask_sentiment_on_risk_factors",
           n_sent_masked == N_SENTIMENT_MASKED, n_sent_masked, N_SENTIMENT_MASKED)

    guid_mask = out.section_type.isin(["MDA", "RISK_FACTORS"]) & out.guidance_direction.notna()
    n_guid_masked = int(guid_mask.sum())
    by_section = out.loc[guid_mask, "section_type"].value_counts().to_dict()
    n_active = int(out.loc[guid_mask, "guidance_direction"].isin(GUIDANCE_MAP).sum())
    _check(assertions, "mask_guidance_on_mda_and_risk_factors",
           n_guid_masked == N_GUIDANCE_MASKED, n_guid_masked, N_GUIDANCE_MASKED)
    _check(assertions, "mask_guidance_by_section",
           by_section.get("MDA") == N_GUIDANCE_MASKED_MDA
           and by_section.get("RISK_FACTORS") == N_GUIDANCE_MASKED_RF,
           by_section, {"MDA": N_GUIDANCE_MASKED_MDA, "RISK_FACTORS": N_GUIDANCE_MASKED_RF})
    _check(assertions, "mask_guidance_active_values",
           n_active == N_GUIDANCE_MASKED_ACTIVE, n_active, N_GUIDANCE_MASKED_ACTIVE)

    n_applicable_frame = int(out.guidance_applicable.fillna(False).sum())
    _check(assertions, "guidance_applicable_frame",
           n_applicable_frame == N_APPLICABLE_FRAME, n_applicable_frame, N_APPLICABLE_FRAME)
    # after the section mask the two predicates coincide on this corpus; that is
    # measured, not assumed, and the filter stays in the expression regardless.
    coincide = int((out.guidance_direction.notna() & ~guid_mask
                    & ~out.guidance_applicable.fillna(False)).sum())
    _check(assertions, "guidance_outside_applicable_after_mask", coincide == 0, coincide, 0)

    imputed_frame = int(out.guidance_imputed_none.fillna(False).sum())
    n_enum_null = int((out.guidance_applicable.fillna(False)
                       & out.guidance_direction.isna()).sum())
    _check(assertions, "guidance_enum_nulls_left_null",
           n_enum_null == N_GUIDANCE_ENUM_NULL, n_enum_null, N_GUIDANCE_ENUM_NULL)
    imputed_are_none = int((out.guidance_imputed_none.fillna(False)
                            & (out.guidance_direction == "NONE")).sum())
    _check(assertions, "imputed_nones_stored_as_NONE",
           imputed_are_none == imputed_frame, imputed_are_none, imputed_frame)

    issue_counts: dict[str, int] = {}
    for issues in out.loc[~out.schema_valid, "schema_issues"]:
        for issue in issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
    _check(assertions, "schema_invalid_red_flag_drops",
           issue_counts.get("bad_enum:red_flag_category") == N_RF_CATEGORY_DROPS
           and issue_counts.get("bad_enum:red_flag_modality") == N_RF_MODALITY_DROPS,
           issue_counts,
           {"bad_enum:red_flag_category": N_RF_CATEGORY_DROPS,
            "bad_enum:red_flag_modality": N_RF_MODALITY_DROPS})

    out = score_labels(out)

    census = {
        "sentiment_masked_risk_factors": n_sent_masked,
        "sentiment_masked_values": masked_values,
        "guidance_masked_total": n_guid_masked,
        "guidance_masked_by_section": by_section,
        "guidance_masked_active": n_active,
        "guidance_applicable_frame": n_applicable_frame,
        "guidance_imputed_none_frame": imputed_frame,
        "guidance_imputed_none_share_of_applicable_frame": imputed_frame / n_applicable_frame,
        "guidance_enum_nulls_applicable": n_enum_null,
        "schema_issue_counts": issue_counts,
        "n_schema_invalid": int((~out.schema_valid).sum()),
        "scored_sentiment_rows": int(out.sentiment_num.notna().sum()),
        "scored_active_guidance_rows": int(out.guidance_num.notna().sum()),
    }
    return out, census


# ---------------------------------------------------------------------------
# provenance flags (G2 §2.5 / §10.1)
# ---------------------------------------------------------------------------
def compute_provenance_flags(corpus: pd.DataFrame, assertions: list[dict]) -> tuple[np.ndarray, np.ndarray, dict]:
    """Per-chunk `train_overlap` and `selfid`, computed over the FULL corpus in
    file order (the text stream is positional), then sliced to the frame by the
    caller. An id-join gives 0 and is wrong -- see TRAIN_OVERLAP_DEFINITION."""
    train = pd.read_parquet(TRAIN_SPLIT_PATH, columns=["home_accession_number", "text"])
    _check(assertions, "train_split_rows", len(train) == TRAIN_SPLIT_ROWS,
           len(train), TRAIN_SPLIT_ROWS)
    train_acc = set(train.home_accession_number)
    train_txt = {_sha1_norm(t) for t in train.text}
    del train

    home_hit = corpus.home_accession_number.isin(train_acc).to_numpy()
    src_hit = corpus.source_accession_numbers.map(
        lambda accs: any(a in train_acc for a in accs)).to_numpy()

    tokens = {n: _distinctive_token(n) for n in corpus.home_company_name.unique()}
    tok = corpus.home_company_name.map(tokens).to_numpy()

    txt_hit = np.zeros(len(corpus), dtype=bool)
    selfid = np.zeros(len(corpus), dtype=bool)
    i = 0
    for batch in pq.ParquetFile(CHUNKS_PATH).iter_batches(batch_size=20000, columns=["text"]):
        for j, cell in enumerate(batch.column("text")):
            text = cell.as_py()
            txt_hit[i + j] = _sha1_norm(text) in train_txt
            token = tok[i + j]
            selfid[i + j] = bool(token) and token in text.lower()
        i += batch.num_rows
    _check(assertions, "text_stream_covers_corpus", i == len(corpus), i, len(corpus))

    overlap = home_hit | src_hit | txt_hit
    # per-channel arrays, so counts can be reported on the FRAME (which is what
    # G2 §2.5's published table counts) as well as corpus-wide.
    channels = {
        "home_accession": home_hit,
        "any_source_accession": src_hit,
        "normalized_text": txt_hit,
        "union": overlap,
    }
    return overlap, selfid, channels


# ---------------------------------------------------------------------------
# every-occurrence explosion
# ---------------------------------------------------------------------------
def explode_occurrences(frame: pd.DataFrame, assertions: list[dict]) -> pd.DataFrame:
    """One row per (chunk, occurrence), exploded positionally from the baked
    parallel arrays -- the E2 primitive (module docstring). Scalar chunk-level
    columns are repeated with `n_source_filings`, which is the same operation
    E1's row-wise `explode_label_occurrences()` performs."""
    reps = frame.n_source_filings.to_numpy()
    n_occ = int(reps.sum())
    lengths = frame.source_accession_numbers.map(len).to_numpy()
    _check(assertions, "n_source_filings_matches_array_lengths",
           bool((lengths == reps).all()), int((lengths != reps).sum()), 0)

    occ = pd.DataFrame({
        "cik": np.concatenate(frame.source_ciks.values).astype("int64"),
        "accession_number": np.concatenate(frame.source_accession_numbers.values),
        "filing_date": pd.to_datetime(np.concatenate(frame.source_filing_dates.values)),
        "form": np.concatenate(frame.source_forms.values),
        "home_cik": np.repeat(frame.home_cik.to_numpy(), reps),
        "home_filing_date": pd.to_datetime(np.repeat(frame.home_filing_date.to_numpy(), reps)),
        "section_type": np.repeat(frame.section_type.to_numpy(), reps),
        "sentiment_num": np.repeat(frame.sentiment_num.to_numpy(), reps),
        "guidance_num": np.repeat(frame.guidance_num.to_numpy(), reps),
        "train_overlap": np.repeat(frame.train_overlap.to_numpy(), reps),
        "selfid": np.repeat(frame.selfid.to_numpy(), reps),
    })
    cats = [{f["category"] for f in flags} for flags in frame.red_flags]
    for cat in RED_FLAG_CATEGORIES:
        occ[f"has_{cat}"] = np.repeat(
            np.array([cat in c for c in cats], dtype=bool), reps)
    occ["has_any_red_flag"] = np.repeat(
        np.array([len(c) > 0 for c in cats], dtype=bool), reps)

    _check(assertions, "occurrence_rows", len(occ) == n_occ, len(occ), n_occ)
    return occ


def verify_no_backward_flow(occ: pd.DataFrame, assertions: list[dict]) -> None:
    """E2 restatement of E1's `attach_company_and_verify_no_backward_flow`:
    no occurrence may attach to a filing dated BEFORE its own chunk's home
    filing date."""
    backward = int((occ.filing_date < occ.home_filing_date).sum())
    _check(assertions, "no_backward_flow", backward == 0, backward, 0)
    missing_cik = int(occ.cik.isna().sum()) if occ.cik.dtype.kind == "f" else 0
    _check(assertions, "every_occurrence_has_a_cik", missing_cik == 0, missing_cik, 0)


# ---------------------------------------------------------------------------
# aggregation to one row per (cik, accession_number)
# ---------------------------------------------------------------------------
def build_text_features(occ: pd.DataFrame, assertions: list[dict]) -> pd.DataFrame:
    """The 22 E1 feature definitions, CIK-keyed.

    Every definition below is E1's, restated vectorially:
      share_chunks_<sec>   mean of (section_type == sec)          features.py:590
      sentiment_mean_score mean of sentiment_num, NaN-skipping    features.py:596
      sentiment_negative_share (#== -1) / (# non-null)            features.py:598-602
      guidance_signed_mean mean of guidance_num, NaN-skipping     features.py:603
      guidance_any_present float(any non-null guidance_num)       features.py:604
      redflag_<cat>_rate_<sec> mean of has_<cat> over that filing's
                           chunks IN that section (NaN if none)   features.py:606-613
      redflag_any_rate_press mean of has_any_red_flag over EX99   features.py:615-618
    """
    key = ["cik", "accession_number"]
    df = occ.copy()
    for sec in TEXT_SECTION_TYPES:
        df[f"is_{sec}"] = df.section_type == sec
    df["sent_notna"] = df.sentiment_num.notna()
    df["sent_is_neg"] = df.sentiment_num == -1.0
    df["guid_notna"] = df.guidance_num.notna()
    df["is_cross_cik"] = df.cik != df.home_cik

    grouped = df.groupby(key, sort=True)
    nunique = grouped.agg(nd=("filing_date", "nunique"), nf=("form", "nunique"))
    _check(assertions, "filing_date_and_form_unique_per_key",
           bool(((nunique.nd == 1) & (nunique.nf == 1)).all()),
           {"multi_date": int((nunique.nd > 1).sum()),
            "multi_form": int((nunique.nf > 1).sum())}, 0)

    out = grouped.agg(
        filing_date=("filing_date", "first"),
        form=("form", "first"),
        n_text_chunks_attributed=("cik", "size"),
        sentiment_mean_score=("sentiment_num", "mean"),
        guidance_signed_mean=("guidance_num", "mean"),
        n_sent_notna=("sent_notna", "sum"),
        n_sent_neg=("sent_is_neg", "sum"),
        n_guid_notna=("guid_notna", "sum"),
        train_overlap_share=("train_overlap", "mean"),
        selfid_share=("selfid", "mean"),
        cross_cik_share=("is_cross_cik", "mean"),
        **{f"share_chunks_{sec.lower()}": (f"is_{sec}", "mean") for sec in TEXT_SECTION_TYPES},
    ).reset_index()

    out["sentiment_negative_share"] = np.where(
        out.n_sent_notna > 0, out.n_sent_neg / out.n_sent_notna.replace(0, np.nan), np.nan)
    out["guidance_any_present"] = (out.n_guid_notna > 0).astype(float)
    out = out.drop(columns=["n_sent_notna", "n_sent_neg", "n_guid_notna"])

    for sec in ("RISK_FACTORS", "MDA", "EX99_PRESS_RELEASE"):
        sec_grouped = df[df.section_type == sec].groupby(key, sort=True)
        agg = {f"n_chunks_{sec.lower()}": ("cik", "size")}
        if sec in ("RISK_FACTORS", "MDA"):
            agg.update({f"redflag_{cat}_rate_{sec.lower()}": (f"has_{cat}", "mean")
                        for cat in RED_FLAG_CATEGORIES})
        else:
            agg["redflag_any_rate_press"] = ("has_any_red_flag", "mean")
        out = out.merge(sec_grouped.agg(**agg).reset_index(), on=key, how="left")

    for sec in ("risk_factors", "mda", "ex99_press_release"):
        out[f"n_chunks_{sec}"] = out[f"n_chunks_{sec}"].fillna(0).astype("int64")

    cols = (key + ["filing_date", "form"]
            + [f"share_chunks_{s.lower()}" for s in TEXT_SECTION_TYPES]
            + ["n_text_chunks_attributed", "sentiment_mean_score",
               "sentiment_negative_share", "guidance_signed_mean", "guidance_any_present"]
            + EXPLORATORY_FEATURES + DIAGNOSTIC_COLUMNS)
    out = out[cols].sort_values(key, kind="stable").reset_index(drop=True)

    share_sum = out[[f"share_chunks_{s.lower()}" for s in TEXT_SECTION_TYPES]].sum(axis=1)
    _check(assertions, "section_shares_sum_to_one",
           bool(np.allclose(share_sum, 1.0)), float(share_sum.min()), 1.0)
    max_8k = float(out.share_chunks_8k_body.max())
    _check(assertions, "share_chunks_8k_body_identically_zero", max_8k == 0.0, max_8k, 0.0)
    _check(assertions, "output_key_unique",
           not out.duplicated(key).any(), int(out.duplicated(key).sum()), 0)
    for col in EXPLORATORY_FEATURES + ["train_overlap_share", "selfid_share",
                                       "cross_cik_share", "sentiment_negative_share"]:
        vals = out[col].dropna()
        _check(assertions, f"in_unit_interval:{col}",
               bool(((vals >= 0) & (vals <= 1)).all()),
               [float(vals.min()), float(vals.max())] if len(vals) else None, "[0, 1]")
    return out


# ---------------------------------------------------------------------------
# caveats + feature dictionary (generated from diagnostics, never hand-typed)
# ---------------------------------------------------------------------------
def load_caveat_constants() -> dict:
    g2 = json.loads(G2_RESULTS_PATH.read_text())
    v12 = json.loads(V12_SPOTCHECK_PATH.read_text())
    p1 = v12["P1_exact_set_error"]
    sent = g2["primary"]["sentiment"]
    guid = g2["primary"]["guidance_direction"]
    gap = g2["guidance_active_precision"]
    fnr = g2["guidance_false_none_rate"]

    teacher = (
        f"v1.2 TEACHER red-flag exact-set error {p1['k']}/{p1['n']} = "
        f"{p1['point'] * 100:.2f}% [{p1['wilson_95'][0] * 100:.2f}, "
        f"{p1['wilson_95'][1] * 100:.2f}] (data/hardening/spotcheck_v12/"
        f"results_v12.json). The owner-ratified DEMOTE pre-commitment fired "
        f"(2026-08-27): E2 red flags are EXPLORATORY / disclosure-only in G3. "
        f"These student labels reproduce a teacher measured at that error rate."
    )
    student_sent = (
        f"G2 student spot-check: sentiment agreement {sent['k']}/{sent['n']} = "
        f"{sent['p_hat'] * 100:.1f}% [{sent['wilson_lo'] * 100:.1f}, "
        f"{sent['wilson_hi'] * 100:.1f}]; verdict {sent['verdict']} at the "
        f"owner-ratified 0.85 bar."
    )
    student_guid = (
        f"G2 student spot-check: guidance_direction agreement {guid['k']}/{guid['n']} = "
        f"{guid['p_hat'] * 100:.1f}% [{guid['wilson_lo'] * 100:.1f}, "
        f"{guid['wilson_hi'] * 100:.1f}]; verdict {guid['verdict']} at the 0.85 bar. "
        f"MANDATORY escorts (G2 §0 / §6.3): the PASS is a statement about the NONE "
        f"mass -- active-value precision is {gap['point'] * 100:.2f}% "
        f"[{gap['wilson_lo'] * 100:.2f}, {gap['wilson_hi'] * 100:.2f}] "
        f"(n={gap['n_nominal']}, n_eff={gap['n_eff']:.2f}), and the false-NONE rate is "
        f"{fnr['k']}/{fnr['n']} = {fnr['p_hat'] * 100:.1f}% "
        f"[{fnr['wilson_lo'] * 100:.1f}, {fnr['wilson_hi'] * 100:.2f}]."
    )
    provenance = g2["provenance"]
    return {
        "teacher_red_flag_error": teacher,
        "student_sentiment": student_sent,
        "student_guidance": student_guid,
        "provenance": provenance,
        "e1_constants_not_applicable": (
            "E1's red-flag agreement constants describe E1's Claude teacher on E1's "
            "corpus and are NEVER carried onto these Qwen student labels "
            "(current-era rule); the two measurements above replace them."
        ),
        "raw": {
            "teacher_v12_exact_set_error": p1,
            "g2_sentiment": {k: sent[k] for k in ("k", "n", "p_hat", "wilson_lo", "wilson_hi", "verdict")},
            "g2_guidance": {k: guid[k] for k in ("k", "n", "p_hat", "wilson_lo", "wilson_hi", "verdict")},
            "g2_guidance_active_precision": {k: gap[k] for k in ("point", "wilson_lo", "wilson_hi", "n_nominal", "n_eff")},
            "g2_guidance_false_none_rate": {k: fnr[k] for k in ("k", "n", "p_hat", "wilson_lo", "wilson_hi")},
        },
    }


def build_feature_dictionary(census: dict, caveats: dict) -> dict:
    """One entry per written column: partition, definition, source, caveat."""
    sent_caveat = f"{caveats['student_sentiment']} {caveats['provenance']}"
    guid_caveat = f"{caveats['student_guidance']} {caveats['provenance']}"
    rf_caveat = f"{caveats['teacher_red_flag_error']} {caveats['provenance']}"
    mask_note = (
        f"Section mask applied before aggregation (G2 §3.4): "
        f"{census['sentiment_masked_risk_factors']} RISK_FACTORS sentiment values "
        f"and {census['guidance_masked_total']} MDA/RISK_FACTORS guidance values "
        f"({census['guidance_masked_active']} of them active) are nulled, not scored."
    )
    imputed_note = (
        f"{census['guidance_imputed_none_frame']} frame rows carry "
        f"guidance_imputed_none = true "
        f"({census['guidance_imputed_none_share_of_applicable_frame'] * 100:.2f}% of the "
        f"{census['guidance_applicable_frame']} guidance-applicable frame rows; "
        f"{N_IMPUTED_NONE_CORPUS} = "
        f"{N_IMPUTED_NONE_CORPUS / N_APPLICABLE_CORPUS * 100:.2f}% corpus-wide). They "
        f"count as NONE by the F4 writer rule, i.e. GUIDANCE_MAP gives them no score: "
        f"they neither enter guidance_signed_mean nor set guidance_any_present."
    )

    features: dict[str, dict] = {}

    def add(name, partition, definition, source, caveat):
        features[name] = {"partition": partition, "definition": definition,
                          "source": source, "caveat": caveat}

    add("n_text_chunks_attributed", "confirmatory",
        "Count of labeled chunks attributed to this filing under every-occurrence "
        "attribution (one per (chunk, occurrence) row).",
        "labels_e2_v1 + chunks_v1 baked source_* arrays",
        "Attribution is the union over a chunk's paragraphs; see cross_cik_share.")
    for sec in TEXT_SECTION_TYPES:
        name = f"share_chunks_{sec.lower()}"
        add(name,
            "dropped" if sec == "8K_BODY" else "confirmatory",
            f"Share of this filing's attributed chunks whose section_type is {sec} "
            "(features.py build_text_features definition).",
            "chunks_v1.section_type",
            "Identically 0.0: 8K_BODY chunks are excluded from the frame "
            "(F5_PLAN §3 decision 9 default, 790 chunks). Dropped from both "
            "analysis blocks." if sec == "8K_BODY"
            else "Section mix is confounded with SEC form type (E1 diagnosis: "
                 "section-mix delta is strongly negative once form is controlled).")
    add("sentiment_mean_score", "confirmatory",
        "Mean of SENTIMENT_MAP(sentiment) over attributed chunks, NaN-skipping "
        "(POSITIVE +1 / NEUTRAL 0 / NEGATIVE -1).",
        "labels_e2_v1.sentiment", f"{mask_note} {sent_caveat}")
    add("sentiment_negative_share", "confirmatory",
        "Share of attributed chunks with a non-null sentiment that are NEGATIVE; "
        "NaN when the filing has no scored sentiment chunk.",
        "labels_e2_v1.sentiment", f"{mask_note} {sent_caveat}")
    add("guidance_signed_mean", "confirmatory",
        "Mean of GUIDANCE_MAP(guidance_direction) over guidance-applicable "
        "attributed chunks (RAISED +1 / MAINTAINED 0 / LOWERED -1 / WITHDRAWN -1); "
        "NONE and null are excluded, not zero-filled.",
        "labels_e2_v1.guidance_direction + guidance_applicable",
        f"{mask_note} {imputed_note} WITHDRAWN is kept at -1 per E1's GUIDANCE_MAP; "
        f"F5_PLAN §3 decision 11 (n = 66 on E2) is an owner ruling at G3. {guid_caveat}")
    add("guidance_any_present", "confirmatory",
        "1.0 if the filing has at least one attributed chunk with an ACTIVE "
        "guidance direction, else 0.0.",
        "labels_e2_v1.guidance_direction + guidance_applicable",
        f"{mask_note} {imputed_note} {guid_caveat}")
    for sec in ("risk_factors", "mda"):
        for cat in RED_FLAG_CATEGORIES:
            add(f"redflag_{cat}_rate_{sec}", "exploratory",
                f"Share of this filing's attributed {sec.upper()} chunks carrying a "
                f"{cat} red flag (any modality); NaN when the filing has no "
                f"attributed {sec.upper()} chunk.",
                "labels_e2_v1.red_flags",
                "Category-presence only -- no REALIZED/HYPOTHETICAL split feature is "
                "built (E1 binding constraint 2, carried forward). " + rf_caveat)
    add("redflag_any_rate_press", "exploratory",
        "Share of this filing's attributed EX99_PRESS_RELEASE chunks carrying at "
        "least one red flag; NaN when the filing has no attributed EX99 chunk.",
        "labels_e2_v1.red_flags", rf_caveat)
    add("train_overlap_share", "diagnostic",
        "Share of this filing's attributed chunks flagged train_overlap. "
        + TRAIN_OVERLAP_DEFINITION,
        "finetune/splits_v12/train.parquet vs chunks_v1",
        "Key results are reported with and without the overlap set "
        "(EXPANSION_PLAN §3 item 2). Accession-level overlap is a LOWER BOUND on "
        "memorization exposure: home-CIK exposure is 15.85% (G2 §2.5).")
    add("selfid_share", "diagnostic",
        "Share of this filing's attributed chunks where the company self-identifies "
        "in the passage text. " + SELFID_DEFINITION,
        "chunks_v1.home_company_name vs chunks_v1.text",
        "Disclosure of how often the labeler could see whose filing it was reading.")
    add("cross_cik_share", "diagnostic",
        "Share of this filing's attributed chunks whose HOME filing belongs to a "
        "different CIK.",
        "chunks_v1.source_ciks vs chunks_v1.home_cik",
        "Measures the union-over-paragraphs attribution property described in the "
        "module docstring. Disposition is an open G3 question, not a default.")
    for sec in ("risk_factors", "mda", "ex99_press_release"):
        add(f"n_chunks_{sec}", "diagnostic",
            f"Count of attributed {sec.upper()} chunks -- the denominator of that "
            "section's red-flag rates.",
            "chunks_v1.section_type", "Diagnostic denominator, not a feature.")

    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "unit_of_observation": "one row per (cik, accession_number)",
        "company_key": "cik (E2 labels carry no ticker)",
        "partitions": {
            "confirmatory": CONFIRMATORY_FEATURES,
            "exploratory": EXPLORATORY_FEATURES,
            "dropped": DROPPED_FEATURES,
            "diagnostic": DIAGNOSTIC_COLUMNS,
        },
        "partition_basis": (
            "F5_PLAN §3 decision 3: of the 22 E1 text features the 13 red-flag "
            "columns are exploratory (demoted 2026-08-27), leaving 9; "
            "share_chunks_8k_body is dropped (identically zero under decision 9), "
            "so the confirmatory text block is these 8 legacy features. The two "
            "zero-labeling families (YoY novelty, pooled embeddings) are NOT built "
            "here and are not part of this artifact."
        ),
        "caveats": caveats,
        "features": features,
    }


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
def build() -> tuple[pd.DataFrame, dict, dict]:
    assertions: list[dict] = []
    t0 = datetime.now(timezone.utc)

    input_shas = assert_input_shas(assertions)
    corpus = load_corpus(assertions)
    overlap, selfid, channels = compute_provenance_flags(corpus, assertions)
    corpus["train_overlap"] = overlap
    corpus["selfid"] = selfid

    frame_mask = (corpus.section_type != "8K_BODY").to_numpy()
    channel_counts = {
        "frame": {k: int(v[frame_mask].sum()) for k, v in channels.items()},
        "corpus": {k: int(v.sum()) for k, v in channels.items()},
    }
    # G2 §2.5's published per-channel table, measured on the frame.
    _check(assertions, "train_overlap_channels_frame",
           channel_counts["frame"] == {"home_accession": 10442,
                                       "any_source_accession": 14341,
                                       "normalized_text": 487,
                                       "union": N_TRAIN_OVERLAP},
           channel_counts["frame"],
           {"home_accession": 10442, "any_source_accession": 14341,
            "normalized_text": 487, "union": N_TRAIN_OVERLAP})

    frame = build_frame(corpus, assertions)
    _check(assertions, "train_overlap_frame_count",
           int(frame.train_overlap.sum()) == N_TRAIN_OVERLAP,
           int(frame.train_overlap.sum()), N_TRAIN_OVERLAP)
    _check(assertions, "selfid_frame_count",
           int(frame.selfid.sum()) == N_SELFID, int(frame.selfid.sum()), N_SELFID)

    frame, census = apply_masks(frame, assertions)
    occ = explode_occurrences(frame, assertions)
    verify_no_backward_flow(occ, assertions)

    multi_cik_acc = int((occ.groupby("accession_number").cik.nunique() > 1).sum())
    _check(assertions, "no_accession_maps_to_multiple_ciks",
           multi_cik_acc == 0, multi_cik_acc, 0)

    features = build_text_features(occ, assertions)

    census.update({
        "corpus_rows": N_CORPUS,
        "frame_rows": int(len(frame)),
        "chunks_8k_body_excluded": N_8K_BODY,
        "occurrence_rows": int(len(occ)),
        "filings": int(len(features)),
        "distinct_ciks": int(features.cik.nunique()),
        "filing_date_min": str(features.filing_date.min().date()),
        "filing_date_max": str(features.filing_date.max().date()),
        "forms": occ.form.value_counts().to_dict(),
        "train_overlap_frame_chunks": int(frame.train_overlap.sum()),
        "train_overlap_channels": channel_counts,
        "selfid_frame_chunks": int(frame.selfid.sum()),
        "selfid_frame_share": float(frame.selfid.mean()),
        "cross_cik_occurrence_rows": int((occ.cik != occ.home_cik).sum()),
        "cross_cik_occurrence_share": float((occ.cik != occ.home_cik).mean()),
        "chunks_with_multiple_source_ciks": int(
            frame.source_ciks.map(lambda a: len(set(a)) > 1).sum()),
        "max_occurrences_for_one_chunk": int(frame.n_source_filings.max()),
    })

    caveats = load_caveat_constants()
    dictionary = build_feature_dictionary(census, caveats)

    F5_DIR.mkdir(parents=True, exist_ok=True)
    features.to_parquet(OUT_PARQUET, index=False)
    OUT_DICTIONARY.write_text(json.dumps(dictionary, indent=1) + "\n")

    runtime_s = (datetime.now(timezone.utc) - t0).total_seconds()
    manifest = {
        "artifact": "data/f5/text_features_e2.parquet",
        "artifact_sha256": _sha256_file(OUT_PARQUET),
        "module": "features_e2.py",
        "module_sha256": _sha256_file(Path(__file__)),
        "feature_dictionary": "data/f5/feature_dictionary_e2.json",
        "feature_dictionary_sha256": _sha256_file(OUT_DICTIONARY),
        "generated_utc": t0.isoformat(),
        "runtime_seconds": runtime_s,
        "network_calls": 0,
        "api_calls": 0,
        "no_ic_computed": True,
        "freeze_statement": (
            "No information coefficient, correlation or feature-versus-outcome "
            "association is computed anywhere in this module or its tests "
            "(F5_PLAN §1)."
        ),
        "inputs_asserted": input_shas,
        "inputs_recorded_not_read": {
            "data/prices_e2.parquet": _sha256_file(PRICES_PATH),
            "data/fundamentals_e2.parquet": _sha256_file(FUNDAMENTALS_PATH),
            "data/filings_metadata_e2.db": _sha256_file(METADATA_DB),
        },
        "definitions": {
            "train_overlap": TRAIN_OVERLAP_DEFINITION,
            "selfid": SELFID_DEFINITION,
            "every_occurrence_primitive": (
                "The baked parallel arrays source_accession_numbers / "
                "source_filing_dates / source_forms / source_ciks ARE the primitive: "
                "there is no E2 occurrence map to re-derive them from."
            ),
        },
        "partitions": dictionary["partitions"],
        "census": census,
        "caveat_constants": caveats["raw"],
        "assertions": assertions,
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=1) + "\n")
    return features, manifest, dictionary


def main() -> None:
    features, manifest, _ = build()
    print(f"wrote {OUT_PARQUET} -- {len(features)} filings, "
          f"{manifest['census']['distinct_ciks']} CIKs, "
          f"{manifest['census']['occurrence_rows']} occurrence rows")
    print(f"assertions passed: {sum(a['passed'] for a in manifest['assertions'])}"
          f"/{len(manifest['assertions'])}")
    print(f"runtime: {manifest['runtime_seconds']:.1f}s")


if __name__ == "__main__":
    main()
