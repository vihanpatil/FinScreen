#!/usr/bin/env python3
"""Offline tests for build_f4_chunks.py — no model, no GPU, no network, $0.

    python3 -m pytest finetune/test_build_f4_chunks.py -q

Every real artifact is opened READ-ONLY; nothing is written outside tmp_path.
The load-bearing test is `test_e1_regression_*`: this builder rebuilds E1's
frozen `data/labeling_corpus.parquet` from `data/filings.parquet` and the
6,747 chunk_ids, texts, word counts and paragraph_ids come back identical —
which is what licenses the streaming re-expression of chunk.py's packing.
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
for p in (str(HERE), str(REPO)):
    if p not in sys.path:
        sys.path.insert(0, p)

import chunk as C
import build_f4_chunks as B


# ===========================================================================
# reflow_v1 — the ratified line rule
# ===========================================================================

PROSE = " ".join(f"w{i}" for i in range(60))          # a 60-word line
SHORT = "Revenue"                                     # a 1-word table cell


def test_reflow_keeps_long_lines_byte_identical():
    text = "\n".join([PROSE, PROSE])
    assert B.reflow_v1(text) == [PROSE, PROSE]


def test_reflow_equals_the_shipped_rule_when_there_are_no_short_lines():
    text = "\n".join([PROSE, PROSE, PROSE])
    assert B.reflow_v1(text) == B.as_is_lines(text) == [PROSE] * 3


def test_reflow_flushes_a_below_floor_run_when_a_long_line_follows():
    """The wrinkle in P3's ratified implementation, pinned rather than fixed:
    a run that has not reached the floor is still emitted when the next
    >=40-word line arrives. 13.6% of the shipped chunk table's paragraphs are
    below-floor because of it (build_f4_chunks.reflow_v1's docstring carries
    the corpus-scale measurement). Changing it would move the ruled scope."""
    text = "\n".join([PROSE, "too short", PROSE, "also short"])
    assert B.reflow_v1(text) == [PROSE, "too short", PROSE]
    assert B.as_is_lines(text) == [PROSE, PROSE]        # the shipped rule drops both


def test_reflow_glues_a_run_of_short_lines_into_a_block():
    text = "\n".join([SHORT] * 45)
    out = B.reflow_v1(text)
    assert len(out) == 1
    assert len(out[0].split()) == 40           # emitted as soon as it reaches the floor
    assert B.as_is_lines(text) == []           # the shipped rule recovers nothing


def test_reflow_drops_a_trailing_run_that_never_reaches_the_floor():
    assert B.reflow_v1("\n".join([SHORT] * 39)) == []


def test_reflow_is_strictly_additive():
    """Every line the shipped rule keeps, reflow keeps — same bytes, same order."""
    text = "\n".join([SHORT] * 5 + [PROSE] + [SHORT] * 50 + [PROSE] + [SHORT] * 2)
    kept = B.reflow_v1(text)
    for line in B.as_is_lines(text):
        assert line in kept
    assert len(kept) > len(B.as_is_lines(text))


def test_reflow_v1_reproduces_p3s_own_implementation():
    """P3's `p3_scale.prose_lines_reflow` is the ratified definition. This
    module productionises it; the two must agree line for line."""
    spec = importlib.util.spec_from_file_location(
        "p3_scale", REPO / "data" / "f3" / "p3_qa" / "p3_scale.py")
    p3 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p3)
    import random
    rnd = random.Random(20260828)
    for _ in range(200):
        lines = []
        for _ in range(rnd.randint(0, 40)):
            n = rnd.choice([0, 1, 2, 3, 5, 12, 39, 40, 41, 90])
            lines.append(" ".join("x" for _ in range(n)))
        text = "\n".join(lines)
        assert B.reflow_v1(text) == p3.prose_lines_reflow(text)


# ===========================================================================
# id scheme
# ===========================================================================

def test_paragraph_and_chunk_ids_follow_e1s_construction():
    norm = C.normalize_paragraph("  Some   TEXT here ")
    assert B.paragraph_id("E2P-", norm) == "E2P-" + hashlib.sha1(
        norm.encode()).hexdigest()[:16]
    pids = ["E2P-aaaa", "E2P-bbbb"]
    assert B.chunk_id_for("E2CHK-", pids) == "E2CHK-" + hashlib.sha1(
        "|".join(pids).encode()).hexdigest()[:16]


def test_e2_prefixes_cannot_collide_with_e1s_namespace():
    assert B.CHUNK_PREFIX != "CHK-" and B.PARA_PREFIX != "P-"
    assert not B.CHUNK_PREFIX.startswith("CHK-")


# ===========================================================================
# packing arithmetic == chunk.py's
# ===========================================================================

def _synthetic_corpus(path: Path, n_sections=12, seed=7):
    import random
    import pandas as pd
    rnd = random.Random(seed)
    vocab = [f"t{i}" for i in range(400)]
    rows = []
    for s in range(n_sections):
        paras = []
        for _ in range(rnd.randint(1, 14)):
            n = rnd.choice([45, 60, 120, 360, 400])
            # deliberate cross-section duplicates, so dedup/home selection bites
            if paras and rnd.random() < 0.3:
                paras.append(paras[0])
            else:
                paras.append(" ".join(rnd.choice(vocab) for _ in range(n)))
        rows.append({
            "ticker": rnd.choice(["AAA", "BBB"]),
            "cik": rnd.choice([11, 22]),
            "accession_number": f"acc-{s:04d}",
            "form": "10-K",
            "filing_date": f"2020-{1 + s % 12:02d}-01",
            "section_type": rnd.choice(["MDA", "RISK_FACTORS"]),
            "text": "\n".join(paras),
        })
    pd.DataFrame(rows).to_parquet(path, index=False)
    return pd.DataFrame(rows)


def test_streaming_packer_reproduces_chunk_pack_windows(tmp_path):
    src = tmp_path / "synthetic.parquet"
    df = _synthetic_corpus(src)
    cfg = B.e1_regression_config(tmp_path / "out.parquet")
    cfg.corpus_path = src
    B.build(cfg, verbose=False)

    import pandas as pd
    got = pd.read_parquet(tmp_path / "out.parquet")
    canon = C.build_canonical_paragraphs(df)
    want = C.pack_windows(canon)
    assert set(got.chunk_id) == set(want.chunk_id)
    g = got.set_index("chunk_id").sort_index()
    w = want.set_index("chunk_id").sort_index()
    assert (g.text == w.text).all()
    assert (g.word_count == w.word_count).all()
    assert (g.n_paragraphs == w.n_paragraphs).all()
    assert (g.home_accession_number == w.home_accession_number).all()
    assert all(list(a) == list(b) for a, b in zip(g.paragraph_ids, w.paragraph_ids))
    assert (g.n_source_filings == w.n_source_filings).all()


def test_source_filings_collapse_per_filing_not_per_section(tmp_path):
    """chunk.py keys the back-reference union on (ticker, accession). A
    paragraph in both the MD&A and the Risk Factors of ONE filing is one source
    filing, not two — otherwise every every-occurrence count is inflated."""
    import pandas as pd
    para = " ".join(f"z{i}" for i in range(200))
    df = pd.DataFrame([
        {"ticker": "AAA", "cik": 1, "accession_number": "acc-1", "form": "10-K",
         "filing_date": "2020-01-01", "section_type": "MDA", "text": para},
        {"ticker": "AAA", "cik": 1, "accession_number": "acc-1", "form": "10-K",
         "filing_date": "2020-01-01", "section_type": "RISK_FACTORS", "text": para},
    ])
    src = tmp_path / "c.parquet"
    df.to_parquet(src, index=False)
    cfg = B.e1_regression_config(tmp_path / "o.parquet")
    cfg.corpus_path = src
    B.build(cfg, verbose=False)
    out = pd.read_parquet(tmp_path / "o.parquet")
    assert len(out) == 1                       # one home, one chunk
    assert out.n_source_filings.iloc[0] == 1
    assert list(out.source_accession_numbers.iloc[0]) == ["acc-1"]


# ===========================================================================
# THE regression: rebuild E1's frozen corpus
# ===========================================================================

@pytest.fixture(scope="module")
def e1_rebuild(tmp_path_factory):
    out = tmp_path_factory.mktemp("e1") / "e1.parquet"
    if not (REPO / "data" / "filings.parquet").exists():
        pytest.skip("E1's frozen corpus is not on this machine")
    B.build(B.e1_regression_config(out), verbose=False)
    import pandas as pd
    got = pd.read_parquet(out).set_index("chunk_id").sort_index()
    want = pd.read_parquet(REPO / "data" / "labeling_corpus.parquet").set_index(
        "chunk_id").sort_index()
    return got, want


def test_e1_regression_chunk_ids_are_identical(e1_rebuild):
    got, want = e1_rebuild
    assert len(got) == len(want) == 6747
    assert list(got.index) == list(want.index)


def test_e1_regression_text_and_counts_are_identical(e1_rebuild):
    got, want = e1_rebuild
    for col in ("text", "word_count", "n_paragraphs", "home_accession_number",
                "home_form", "home_filing_date", "home_cik", "section_type",
                "n_source_filings"):
        assert (got[col] == want[col]).all(), col
    assert all(list(a) == list(b) for a, b in zip(got.paragraph_ids, want.paragraph_ids))


def test_e1_regression_source_sets_are_identical(e1_rebuild):
    """Sets, not order: E1 sorted by (filing_date, ticker) with Python's stable
    sort, so ties kept dict-insertion order; this builder sorts fully by
    (filing_date, cik, accession). Exactly ONE of 6,747 chunks orders
    differently, and the (accession -> date, form) mapping is identical for all
    6,747 — which is what every downstream consumer reads."""
    got, want = e1_rebuild
    n_order_diff = 0
    for a, b in zip(got.source_accession_numbers, want.source_accession_numbers):
        assert set(a) == set(b)
        n_order_diff += int(list(a) != list(b))
    assert n_order_diff == 1
    for ga, gd, gf, wa, wd, wf in zip(
        got.source_accession_numbers, got.source_filing_dates, got.source_forms,
        want.source_accession_numbers, want.source_filing_dates, want.source_forms,
    ):
        assert dict(zip(ga, zip(gd, gf))) == dict(zip(wa, zip(wd, wf)))


# ===========================================================================
# determinism + the sha pin
# ===========================================================================

def test_two_builds_are_byte_identical(tmp_path):
    src = tmp_path / "s.parquet"
    _synthetic_corpus(src, n_sections=30, seed=3)
    shas = []
    for i in (1, 2):
        cfg = B.e1_regression_config(tmp_path / f"out{i}.parquet")
        cfg.corpus_path = src
        shas.append(B.build(cfg, verbose=False)["parquet"]["sha256"])
    assert shas[0] == shas[1]


def test_corpus_sha_pin_hard_fails_on_a_mismatch(tmp_path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"hello")
    with pytest.raises(SystemExit) as e:
        B.assert_sha(f, "0" * 64, "corpus")
    assert "MISMATCH" in str(e.value)
    assert B.assert_sha(f, "", "corpus") == hashlib.sha256(b"hello").hexdigest()


def test_the_pinned_p5_corpus_sha_is_the_ruled_one():
    assert B.CORPUS_SHA256 == (
        "15853e9f54902a933f0372869209a353ab3f052cb5c7dc1f897297f75b53f417")
    assert B.AUDIT_SHA256 == (
        "207f392aa54c5151015093ecb34e5c57319f17e1ce22a3375ec1ac7f18e81eef")


# ===========================================================================
# the shipped artifact
# ===========================================================================

@pytest.fixture(scope="module")
def shipped():
    if not B.OUT_PARQUET.exists():
        pytest.skip("data/f4/chunks_v1.parquet has not been built on this machine")
    import pyarrow.parquet as pq
    return pq.ParquetFile(B.OUT_PARQUET)


def test_shipped_chunk_ids_are_unique_and_disjoint_from_e1(shipped):
    import pandas as pd
    import pyarrow.parquet as pq
    ids = pq.read_table(B.OUT_PARQUET, columns=["chunk_id"])["chunk_id"].to_pylist()
    assert len(set(ids)) == len(ids)
    e1 = set(pd.read_parquet(B.E1_CORPUS_PARQUET, columns=["chunk_id"])["chunk_id"])
    assert not (set(ids) & e1)
    assert all(i.startswith(B.CHUNK_PREFIX) for i in ids[:1000])


def test_shipped_table_is_w1_core_and_chronological(shipped):
    import pyarrow.parquet as pq
    t = pq.read_table(B.OUT_PARQUET, columns=["home_stratum", "home_filing_date",
                                              "window_rule", "line_rule"])
    strata = set(t["home_stratum"].to_pylist())
    assert strata == {"core"}                       # W1 CORE: stratum filter
    dates = t["home_filing_date"].to_pylist()
    assert dates == sorted(dates)                   # chronological output order
    assert dates[0] < "2016-01-01" and dates[-1] > "2026-01-01"   # W1: no date filter
    assert set(t["window_rule"].to_pylist()) == {"W1_core"}
    assert set(t["line_rule"].to_pylist()) == {"reflow_v1"}


def test_shipped_table_never_splits_a_filing_across_rows(shipped):
    """Every home accession's chunks are contiguous — this is what lets the F4
    campaign cut nightly segments on filing boundaries."""
    import pyarrow.parquet as pq
    accs = pq.read_table(B.OUT_PARQUET,
                         columns=["home_accession_number"])["home_accession_number"].to_pylist()
    seen, prev, noncontig = set(), None, 0
    for a in accs:
        if a != prev:
            noncontig += int(a in seen)
            seen.add(a)
            prev = a
    assert noncontig == 0


def test_shipped_guidance_applicable_matches_the_applicability_matrix(shipped):
    import pyarrow.parquet as pq
    t = pq.read_table(B.OUT_PARQUET, columns=["section_type", "guidance_applicable"])
    pairs = set(zip(t["section_type"].to_pylist(), t["guidance_applicable"].to_pylist()))
    for sec, flag in pairs:
        assert flag == (sec in B.GUIDANCE_APPLICABLE_SECTION_TYPES)


def test_the_applicability_matrix_is_the_one_in_the_frozen_training_targets():
    """GUIDANCE_APPLICABLE_SECTION_TYPES is not a guess: it is exactly the set
    of section types whose v1.2 training targets carry the key."""
    import json
    import pandas as pd
    mlx = HERE / "mlx_data_v12"
    if not (mlx / "train.jsonl").exists():
        pytest.skip("mlx_data_v12 is not on this machine")
    st = pd.read_parquet(REPO / "data" / "labeling_corpus.parquet",
                         columns=["chunk_id", "section_type"])
    sec = dict(zip(st.chunk_id, st.section_type))
    with_key, without = set(), set()
    for name in ("train.jsonl", "valid.jsonl"):
        for line in open(mlx / name):
            rec = json.loads(line)
            gold = json.loads(rec["messages"][2]["content"])
            (with_key if "guidance_direction" in gold else without).add(sec[rec["chunk_id"]])
    assert with_key == set(B.GUIDANCE_APPLICABLE_SECTION_TYPES)
    assert not (with_key & without)          # applicability is a clean partition
