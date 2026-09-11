"""Tests for `text_families_e2.py` (F5 Step 1b, the two zero-labeling families).

Everything except the one `@pytest.mark.slow` smoke runs on SYNTHETIC frames
written into `tmp_path`: no `data/f5` parquet, no real return, no fold, no
association of any kind (F5_PLAN §1, the freeze).  The smoke reads the real
corpus text and FOUR key columns of the target table (`cik`,
`accession_number`, `filing_date`, `in_membership`) for at most 20 filings --
never a return column.

Run the fast suite with:  python3 -m pytest -q test_text_families_e2.py -m "not slow"
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import text_families_e2 as T


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def reference_shingles(text: str, n: int = 5) -> set:
    """An INDEPENDENT 5-word-shingle implementation (tuples of words, no
    hashing) used to check the hashed one."""
    words = T.normalize_text(text).split()
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def reference_jaccard(a: str, b: str, n: int = 5) -> float:
    A, B = reference_shingles(a, n), reference_shingles(b, n)
    if not A or not B:
        return float("nan")
    return len(A & B) / len(A | B)


def write_corpus(path: Path, rows) -> Path:
    """A synthetic corpus parquet with the columns this module reads."""
    df = pd.DataFrame(rows, columns=["cik", "accession_number", "section_type",
                                     "filing_date", "text"])
    df["form"] = "10-Q"      # the corpus carries `form`; the index reads it
    df.to_parquet(path, index=False)
    return path


class StubTokenizer:
    """Whitespace tokenizer: one 'token' per word, decode rejoins them."""

    def __call__(self, text, add_special_tokens=False):
        return {"input_ids": text.split()}

    def decode(self, ids):
        return " ".join(ids)


class StubModel:
    """Deterministic stand-in for the sentence-transformer: the k-th window
    of a call maps to a vector that is easy to reason about."""

    def __init__(self, dim=T.EMB_DIM):
        self.dim = dim
        self.tokenizer = StubTokenizer()
        self.n_encode_calls = 0
        self.n_windows_seen = 0

    def encode(self, windows, batch_size=32, convert_to_numpy=True,
               show_progress_bar=False):
        self.n_encode_calls += 1
        self.n_windows_seen += len(windows)
        out = np.zeros((len(windows), self.dim), dtype=np.float32)
        for i, w in enumerate(windows):
            out[i, 0] = float(len(w.split()))   # window length in words
            out[i, 1] = float(len(w))           # window length in chars
        return out


# ---------------------------------------------------------------------------
# FAMILY A -- normalization, shingles, Jaccard
# ---------------------------------------------------------------------------


def test_normalize_lowercases_strips_digits_collapses_whitespace():
    assert T.normalize_text("  Q1  2024\nRevenue\tGREW 12.5% ") == "q revenue grew .%"
    assert T.normalize_text("") == ""
    assert T.normalize_text(None) == ""


def test_shingle_hashes_match_an_independent_implementation():
    text = ("the company faces risks from supply chain disruption and from "
            "rising interest rates in the coming fiscal year 2024")
    h = T.shingle_hashes(text)
    ref = reference_shingles(text)
    assert h.size == len(ref)                      # no hash collision here
    assert h.size == len(T.normalize_text(text).split()) - T.SHINGLE_N + 1
    assert np.array_equal(h, np.unique(h))         # sorted unique set


def test_shingle_set_ignores_multiplicity():
    once = "alpha beta gamma delta epsilon"
    twice = once + " " + once
    # the repeated span re-emits shingles that already exist, plus the 4
    # straddling ones
    assert T.shingle_hashes(once).size == 1
    assert T.shingle_hashes(twice).size == 1 + 4


def test_shingle_hash_is_deterministic_across_processes():
    # blake2b, not python's salted hash(): the same text must give the same
    # ids in a fresh interpreter, or the artifact is not reproducible.
    import subprocess
    import sys
    code = ("import text_families_e2 as T;"
            "print(int(T.shingle_hashes('alpha beta gamma delta epsilon')[0]))")
    out = subprocess.run([sys.executable, "-c", code], cwd=str(T.REPO_ROOT),
                         capture_output=True, text=True, check=True)
    assert int(out.stdout.strip()) == int(
        T.shingle_hashes("alpha beta gamma delta epsilon")[0])


def test_jaccard_known_value_and_novelty_complement():
    a = "alpha beta gamma delta epsilon zeta"       # 2 shingles
    b = "alpha beta gamma delta epsilon eta"        # 2 shingles, 1 shared
    assert T.jaccard_from_hashes(T.shingle_hashes(a), T.shingle_hashes(b)) == \
        pytest.approx(1 / 3)
    assert T.novelty_from_texts(a, b) == pytest.approx(2 / 3)
    assert T.novelty_from_texts(a, b) == pytest.approx(1 - reference_jaccard(a, b))


def test_identical_text_is_zero_novelty_and_disjoint_is_one():
    a = "alpha beta gamma delta epsilon zeta eta"
    assert T.novelty_from_texts(a, a) == pytest.approx(0.0)
    b = "one two three four five six seven"
    assert T.novelty_from_texts(a, b) == pytest.approx(1.0)


def test_text_shorter_than_the_shingle_is_nan():
    short = "alpha beta gamma delta"    # 4 words < n = 5
    long = "alpha beta gamma delta epsilon"
    assert T.shingle_hashes(short).size == 0
    assert math.isnan(T.novelty_from_texts(short, long))
    assert math.isnan(T.novelty_from_texts(long, short))
    assert math.isnan(T.jaccard_from_hashes(T.shingle_hashes(short),
                                            T.shingle_hashes(long)))


# ---------------------------------------------------------------------------
# FAMILY A -- prior-filing selection
# ---------------------------------------------------------------------------


def _index(rows) -> pd.DataFrame:
    idx = pd.DataFrame(rows, columns=["cik", "accession_number", "section_type",
                                      "filing_date"])
    idx["filing_date"] = pd.to_datetime(idx["filing_date"])
    idx["form"] = "10-Q"
    idx["row"] = np.arange(len(idx), dtype=np.int64)
    return idx


def test_prior_is_same_cik_same_section_and_strictly_earlier():
    idx = _index([
        (1, "a-old", "MDA", "2020-01-01"),          # the right answer
        (1, "a-older", "MDA", "2019-01-01"),        # earlier, but not the max
        (1, "a-same-day", "MDA", "2021-01-01"),     # same day -> NOT strictly earlier
        (1, "a-future", "MDA", "2022-01-01"),       # later -> never
        (1, "a-rf", "RISK_FACTORS", "2020-06-01"),  # other section
        (2, "b-old", "MDA", "2020-06-01"),          # other cik
        (1, "a-cur", "MDA", "2021-01-01"),
    ])
    prior = T.select_prior(idx, 1, "MDA", pd.Timestamp("2021-01-01"))
    assert prior["accession_number"] == "a-old"


def test_no_prior_returns_none():
    idx = _index([(1, "a-cur", "MDA", "2021-01-01"),
                  (1, "a-later", "MDA", "2022-01-01")])
    assert T.select_prior(idx, 1, "MDA", pd.Timestamp("2021-01-01")) is None
    assert T.select_prior(idx, 99, "MDA", pd.Timestamp("2030-01-01")) is None


def test_prior_date_ties_break_on_smallest_accession_number():
    idx = _index([(1, "zzz", "MDA", "2020-01-01"),
                  (1, "aaa", "MDA", "2020-01-01"),
                  (1, "cur", "MDA", "2021-01-01")])
    assert T.select_prior(idx, 1, "MDA", pd.Timestamp("2021-01-01"))[
        "accession_number"] == "aaa"


def test_build_prior_pairs_agrees_with_select_prior_and_gap_days():
    idx = _index([
        (1, "a1", "MDA", "2019-02-01"),
        (1, "a2", "MDA", "2020-02-01"),
        (1, "a3", "MDA", "2021-02-01"),
        (1, "a3", "RISK_FACTORS", "2021-02-01"),
        (2, "b1", "MDA", "2020-03-01"),
    ])
    scoped = {(1, "a3"), (2, "b1")}
    pairs = T.build_prior_pairs(idx, scoped)
    got = {(r.cik, r.accession_number, r.section_type): (r.prior_row, r.prior_gap_days)
           for r in pairs.itertuples(index=False)}
    assert set(got) == {(1, "a3", "MDA"), (1, "a3", "RISK_FACTORS"), (2, "b1", "MDA")}
    # MDA of a3 -> a2 (row 1), 366 days (2020 is a leap year)
    assert got[(1, "a3", "MDA")] == (1, 366.0)
    # RISK_FACTORS of a3 has no prior; b1 is the cik's first MDA
    assert got[(1, "a3", "RISK_FACTORS")][0] == -1
    assert math.isnan(got[(1, "a3", "RISK_FACTORS")][1])
    assert got[(2, "b1", "MDA")][0] == -1
    for r in pairs.itertuples(index=False):
        ref = T.select_prior(idx, r.cik, r.section_type,
                             idx.loc[idx["row"] == r.row, "filing_date"].iloc[0])
        assert (r.prior_row == -1) == (ref is None)
        if ref is not None:
            assert r.prior_row == ref["row"]


def test_compute_novelty_end_to_end_on_a_synthetic_corpus(tmp_path):
    base = " ".join(f"w{i}" for i in range(40))
    changed = base + " " + " ".join(f"x{i}" for i in range(40))
    corpus = write_corpus(tmp_path / "corpus.parquet", [
        (1, "acc-2019", "MDA", "2019-02-01", base),
        (1, "acc-2020", "MDA", "2020-02-01", changed),
        (1, "acc-2020", "RISK_FACTORS", "2020-02-01", base),   # first 1A: no prior
        (2, "acc-b", "MDA", "2020-05-01", base),               # cik 2: no prior
    ])
    idx = T.load_corpus_index(corpus)
    scope = pd.DataFrame({"cik": [1, 2], "accession_number": ["acc-2020", "acc-b"],
                          "filing_date": pd.to_datetime(["2020-02-01", "2020-05-01"])})
    nov, diag = T.compute_novelty(scope, idx, corpus_path=corpus)
    r = nov.set_index("accession_number")
    expected = 1 - reference_jaccard(changed, base)
    assert r.loc["acc-2020", "novelty_mda_yoy"] == pytest.approx(expected)
    assert r.loc["acc-2020", "prior_gap_days_mda"] == 365.0
    assert math.isnan(r.loc["acc-2020", "novelty_risk_factors_yoy"])
    assert math.isnan(r.loc["acc-2020", "prior_gap_days_risk_factors"])
    assert math.isnan(r.loc["acc-b", "novelty_mda_yoy"])
    assert diag["n_with_prior"] == 1 and diag["n_without_prior"] == 2
    # the digits inside "w0 w1 ..." are stripped by normalization, so the
    # measured value is a real number in [0, 1], not a degenerate 0/1
    assert 0.0 < r.loc["acc-2020", "novelty_mda_yoy"] < 1.0


def test_prior_text_is_never_from_a_later_filing(tmp_path):
    """A future filing that is nearly identical must NOT be chosen; the
    novelty must come from the earlier one."""
    old = " ".join(f"o{i}" for i in range(30))
    cur = " ".join(f"c{i}" for i in range(30))
    corpus = write_corpus(tmp_path / "corpus.parquet", [
        (1, "old", "MDA", "2019-01-01", old),
        (1, "cur", "MDA", "2020-01-01", cur),
        (1, "future", "MDA", "2021-01-01", cur),   # identical to cur
    ])
    idx = T.load_corpus_index(corpus)
    scope = pd.DataFrame({"cik": [1], "accession_number": ["cur"],
                          "filing_date": pd.to_datetime(["2020-01-01"])})
    nov, _ = T.compute_novelty(scope, idx, corpus_path=corpus)
    # if the future filing leaked in, novelty would be 0.0
    assert nov.loc[0, "novelty_mda_yoy"] == pytest.approx(
        1 - reference_jaccard(cur, old))
    assert nov.loc[0, "novelty_mda_yoy"] > 0.9
    assert nov.loc[0, "prior_gap_days_mda"] == 365.0


# ---------------------------------------------------------------------------
# FAMILY B -- windowing, pooling, checkpointing
# ---------------------------------------------------------------------------


def test_window_cap_and_window_size():
    tok = StubTokenizer()
    text = " ".join(f"t{i}" for i in range(254 * 100))   # 100 windows' worth
    # NO explicit arguments: the pinned defaults are what ships, so the
    # constants themselves are under test.
    wins, n_uncapped = T.token_windows(tok, text)
    assert (T.WINDOW_CONTENT_TOKENS, T.MAX_WINDOWS_PER_SECTION) == (254, 64)
    assert T.MAX_SEQ_LENGTH == 256 and T.EMB_DIM == 384 and T.SHINGLE_N == 5
    assert n_uncapped == 100
    assert len(wins) == 64                      # the cap bites
    assert all(len(w.split()) == 254 for w in wins)
    assert wins[0].split()[0] == "t0"           # the FIRST windows are kept
    assert wins[63].split()[-1] == f"t{254 * 64 - 1}"


def test_window_cap_does_not_bite_short_sections_and_last_window_is_partial():
    tok = StubTokenizer()
    text = " ".join(f"t{i}" for i in range(300))
    wins, n_uncapped = T.token_windows(tok, text, window_tokens=254, max_windows=64)
    assert (n_uncapped, len(wins)) == (2, 2)
    assert len(wins[0].split()) == 254 and len(wins[1].split()) == 46
    assert T.token_windows(tok, "", window_tokens=254, max_windows=64) == ([], 0)


def test_pooling_is_mean_of_windows_then_mean_of_sections():
    # section 1 has three windows, section 2 has one: an unweighted mean over
    # SECTIONS is not the mean over windows, and the difference is the test.
    s1 = [np.full(4, 1.0), np.full(4, 2.0), np.full(4, 6.0)]   # mean 3
    s2 = [np.full(4, 11.0)]                                    # mean 11
    assert T.pool_mean(s1).tolist() == [3.0] * 4
    filing = T.pool_filing([T.pool_mean(s1), T.pool_mean(s2)])
    assert filing.tolist() == [7.0] * 4          # (3 + 11) / 2, NOT 5.0
    assert filing.dtype == np.float32


def _emb_fixture(tmp_path):
    text = " ".join(f"w{i}" for i in range(600))
    corpus = write_corpus(tmp_path / "corpus.parquet", [
        (1, "a", "MDA", "2020-01-01", text),
        (1, "a", "EX99_PRESS_RELEASE", "2020-01-01", "short press release text"),
        (2, "b", "RISK_FACTORS", "2020-02-01", text),
    ])
    idx = T.load_corpus_index(corpus)
    scope = pd.DataFrame({"cik": [1, 2], "accession_number": ["a", "b"],
                          "filing_date": pd.to_datetime(["2020-01-01", "2020-02-01"])})
    return corpus, idx, scope


def test_embedding_counts_and_pooling_on_a_synthetic_corpus(tmp_path):
    corpus, idx, scope = _emb_fixture(tmp_path)
    model = StubModel()
    emb, diag = T.compute_embeddings(scope, idx, model=model, corpus_path=corpus,
                                     partial_path=tmp_path / "partial.parquet",
                                     progress=False)
    r = emb.set_index("accession_number")
    # 600 words -> ceil(600/254) = 3 windows; plus 1 window for the press release
    assert r.loc["a", "n_windows_embedded"] == 4
    assert r.loc["a", "n_sections_embedded"] == 2
    assert r.loc["b", "n_windows_embedded"] == 3
    assert r.loc["b", "n_sections_embedded"] == 1
    assert diag["n_windows_total"] == 7
    # filing "a": MDA section mean of word counts (254, 254, 92)/3 = 200;
    # press release = 4 words; filing = (200 + 4) / 2 = 102
    assert r.loc["a", "emb"][0] == pytest.approx((254 + 254 + 92) / 3 / 2 + 4 / 2)
    assert len(r.loc["a", "emb"]) == T.EMB_DIM


def test_checkpoint_written_and_resume_skips_finished_filings(tmp_path):
    corpus, idx, scope = _emb_fixture(tmp_path)
    partial = tmp_path / "partial.parquet"
    model = StubModel()
    emb1, _ = T.compute_embeddings(scope, idx, model=model, corpus_path=corpus,
                                   partial_path=partial, checkpoint_every=1,
                                   progress=False)
    assert partial.exists() and len(pd.read_parquet(partial)) == 2

    model2 = StubModel()
    emb2, diag2 = T.compute_embeddings(scope, idx, model=model2, corpus_path=corpus,
                                       partial_path=partial, resume=True,
                                       progress=False)
    assert model2.n_encode_calls == 0                      # nothing re-embedded
    assert diag2["n_filings_resumed_from_partial"] == 2
    assert diag2["n_filings_embedded_this_run"] == 0
    assert sorted(emb2["accession_number"]) == sorted(emb1["accession_number"])

    # ... and with resume off, everything is recomputed
    model3 = StubModel()
    _, diag3 = T.compute_embeddings(scope, idx, model=model3, corpus_path=corpus,
                                    partial_path=partial, resume=False,
                                    progress=False)
    assert diag3["n_filings_embedded_this_run"] == 2 and model3.n_encode_calls >= 1


# ---------------------------------------------------------------------------
# Output schema and invariants
# ---------------------------------------------------------------------------


def _frame(n=3, gap=365.0):
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        "cik": np.arange(n, dtype=np.int64),
        "accession_number": [f"acc-{i}" for i in range(n)],
        "filing_date": pd.to_datetime(["2020-01-01"] * n),
        "novelty_risk_factors_yoy": [0.1] * n,
        "novelty_mda_yoy": [0.2] * n,
        "prior_gap_days_risk_factors": [gap] * n,
        "prior_gap_days_mda": [gap] * n,
        "emb": [rng.normal(size=T.EMB_DIM).astype(np.float32) for _ in range(n)],
        "n_sections_embedded": np.full(n, 2, dtype=np.int64),
        "n_windows_embedded": np.full(n, 5, dtype=np.int64),
    })[T.OUTPUT_COLUMNS]


def test_output_schema_is_the_pinned_one(tmp_path):
    tbl = T.to_arrow(_frame())
    assert tbl.column_names == T.OUTPUT_COLUMNS
    assert tbl.schema.field("emb").type == pa.list_(pa.float32(), T.EMB_DIM)
    assert pa.types.is_fixed_size_list(tbl.schema.field("emb").type)
    assert tbl.schema.field("cik").type == pa.int64()
    assert tbl.schema.field("accession_number").type == pa.string()
    for c in ("novelty_risk_factors_yoy", "novelty_mda_yoy",
              "prior_gap_days_risk_factors", "prior_gap_days_mda"):
        assert tbl.schema.field(c).type == pa.float64()
    out = tmp_path / "out.parquet"
    pq.write_table(tbl, out)
    back = pq.read_table(out)
    assert back.schema.field("emb").type == pa.list_(pa.float32(), T.EMB_DIM)
    assert len(np.asarray(back.column("emb")[0].as_py())) == T.EMB_DIM


def test_invariants_reject_a_non_positive_prior_gap():
    with pytest.raises(AssertionError, match="strictly earlier"):
        T.assert_output_invariants(_frame(gap=0.0))


def test_invariants_reject_a_duplicate_filing_key():
    f = pd.concat([_frame(1), _frame(1)], ignore_index=True)
    with pytest.raises(AssertionError, match="duplicate"):
        T.assert_output_invariants(f)


def test_invariants_measure_what_they_promise():
    m = T.assert_output_invariants(_frame())
    assert m["n_rows"] == 3 and m["emb_widths"] == [T.EMB_DIM]
    assert m["min_prior_gap_days_mda"] == 365.0
    assert m["n_novelty_mda_yoy_non_null"] == 3


# ---------------------------------------------------------------------------
# Freeze tripwires
# ---------------------------------------------------------------------------


def test_module_contains_no_association_machinery():
    """F5_PLAN §1: no IC, correlation or fit may exist in a code path that
    can run before G3 ratification."""
    src = (T.REPO_ROOT / "text_families_e2.py").read_text().lower()
    for token in ("spearman", "pearson", "corrcoef", ".corr(", "linregress",
                  "ols(", "polyfit", "xgboost", "sklearn", "regress"):
        assert token not in src, f"association machinery in the module: {token}"


def test_module_never_reads_a_return_column():
    src = (T.REPO_ROOT / "text_families_e2.py").read_text()
    # the three return columns of target_e2.parquet appear only in the
    # docstring's statement that they are NOT read
    body = src.split('"""', 2)[2]
    for col in ("target_excess_63", "subject_return_63", "benchmark_return_63"):
        assert col not in body, f"{col} referenced in module code"
    assert '"in_membership"' in body      # the four key columns are what it reads


def test_frozen_modules_are_not_imported_for_anything_but_hashing():
    src = (T.REPO_ROOT / "text_families_e2.py").read_text()
    assert "import controls as C" in src
    assert "features.py" not in src.split('"""', 2)[2]


# ---------------------------------------------------------------------------
# Real-data smoke (slow, <= 20 filings)
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_real_data_smoke_twenty_filings(tmp_path):
    """End-to-end on <= 20 real filings with the real model.  Reads the
    corpus text and the target table's key columns only -- no return column,
    no fold, no association."""
    if not T.CORPUS_PATH.exists() or not T.TARGET_PATH.exists():
        pytest.skip("E2 corpus / target table not present")
    pytest.importorskip("sentence_transformers")
    frame, man = T.build(limit_filings=20,
                         out_parquet=tmp_path / "smoke.parquet",
                         out_manifest=tmp_path / "smoke_manifest.json",
                         partial_path=tmp_path / "smoke_partial.parquet",
                         resume=False)
    assert 0 < len(frame) <= 20
    assert list(frame.columns) == T.OUTPUT_COLUMNS
    assert man["inputs"]["matches_committed"] is True
    assert man["model"]["revision"] and man["model"]["weight_file_sha256"]
    assert man["freeze"]["return_columns_read"] == []
    embs = np.vstack([np.asarray(v) for v in frame["emb"]])
    assert embs.shape[1] == T.EMB_DIM and np.isfinite(embs).all()
    assert (frame["n_windows_embedded"] >= 1).all()
    gaps = pd.concat([frame["prior_gap_days_risk_factors"],
                      frame["prior_gap_days_mda"]]).dropna()
    assert (gaps >= 1).all()                      # PIT: prior is strictly earlier
    nov = pd.concat([frame["novelty_risk_factors_yoy"],
                     frame["novelty_mda_yoy"]]).dropna()
    assert nov.between(0.0, 1.0).all()
    assert (tmp_path / "smoke.parquet").exists()
    schema = pq.read_schema(tmp_path / "smoke.parquet")
    assert schema.field("emb").type == pa.list_(pa.float32(), T.EMB_DIM)


# ---------------------------------------------------------------------------
# A truncated run may not be written under the production name
# ---------------------------------------------------------------------------
# `--limit-filings` is a debug/smoke switch. A truncated table written to
# `data/f5/text_families_e2.parquet` would become a downstream input (the
# backtest runner sha-asserts that path and joins it) whose manifest claims
# full coverage, which is exactly the kind of silent substitution the F5
# provenance chain exists to prevent.

_SENTINEL = "GUARD PASSED -- the build proceeded past the limit/out check"


def _tripwire(monkeypatch):
    """Make the first real step of `build` announce itself, so a test can tell
    'refused at the door' from 'allowed through'."""
    def boom(*a, **kw):
        raise RuntimeError(_SENTINEL)
    monkeypatch.setattr(T, "assert_input_shas", boom)


def test_limit_filings_refuses_to_write_the_production_artifact(monkeypatch):
    _tripwire(monkeypatch)
    with pytest.raises(RuntimeError) as exc:
        T.build(limit_filings=20)
    msg = str(exc.value)
    assert msg.startswith("REFUSED:") and str(T.OUT_PARQUET) in msg
    assert _SENTINEL not in msg          # refused BEFORE any input was read


def test_limit_filings_is_allowed_with_an_explicit_output_path(tmp_path, monkeypatch):
    _tripwire(monkeypatch)
    with pytest.raises(RuntimeError) as exc:
        T.build(limit_filings=20, out_parquet=tmp_path / "smoke.parquet",
                out_manifest=tmp_path / "smoke_manifest.json",
                partial_path=tmp_path / "smoke_partial.parquet")
    assert _SENTINEL in str(exc.value)


def test_a_full_run_may_still_write_the_production_artifact(monkeypatch):
    _tripwire(monkeypatch)
    with pytest.raises(RuntimeError) as exc:
        T.build()                         # no limit -> the production path is fine
    assert _SENTINEL in str(exc.value)


def test_a_limited_run_that_writes_nothing_is_allowed(monkeypatch):
    _tripwire(monkeypatch)
    with pytest.raises(RuntimeError) as exc:
        T.build(limit_filings=20, write=False)
    assert _SENTINEL in str(exc.value)


def test_the_cli_out_prefix_names_all_three_artifacts(tmp_path, monkeypatch):
    captured = {}

    def fake_build(**kw):
        captured.update(kw)
        return (pd.DataFrame(), {"coverage": {"n_distinct_ciks": 0,
                                              "n_novelty_risk_factors_yoy_present": 0,
                                              "n_novelty_mda_yoy_present": 0},
                                 "family_b_diagnostics": {"n_windows_total": 0,
                                                          "device": "cpu",
                                                          "throughput_windows_per_second": 0},
                                 "runtimes_seconds": {}, "artifact": "x.parquet",
                                 "output_sha256": "0" * 64})

    monkeypatch.setattr(T, "build", fake_build)
    T.main(["--limit-filings", "20", "--out", str(tmp_path / "smoke")])
    assert captured["limit_filings"] == 20
    assert captured["out_parquet"] == tmp_path / "smoke.parquet"
    assert captured["out_manifest"] == tmp_path / "smoke_manifest.json"
    assert captured["partial_path"] == tmp_path / "smoke_partial.parquet"


def test_the_window_cap_counter_is_named_for_the_run_it_counts(tmp_path):
    """Resuming does not recount the sections an earlier run capped, so the
    diagnostic is a THIS-RUN counter and says so in its name."""
    corpus, idx, scope = _emb_fixture(tmp_path)
    _, diag = T.compute_embeddings(scope, idx, model=StubModel(), corpus_path=corpus,
                                   partial_path=tmp_path / "partial.parquet",
                                   progress=False)
    assert "n_sections_hitting_the_window_cap_this_run" in diag
    assert "n_sections_hitting_the_window_cap" not in diag
    for key in ("n_windows_uncapped_this_run", "sections_embedded_by_type_this_run"):
        assert key in diag
