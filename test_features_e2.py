"""test_features_e2.py -- tests for the E2 TEXT feature table (F5 Step 1).

Two layers:

  * synthetic fixtures (fast) for every rule the F5 plan binds -- the section
    masks, the explicit `guidance_applicable` filter, nulls-stay-null,
    imputed-NONE handling, the every-occurrence explosion under CIK keys, the
    E1 aggregation definitions, and no-backward-flow;
  * real-data census assertions (`@pytest.mark.slow`) that re-derive the
    pre-registered numbers from `data/f4/` rather than reading them back out
    of the manifest.

Nothing in this file computes an information coefficient, a correlation, or
any feature-versus-outcome association (F5_PLAN §1, the freeze). No target
column is imported, joined, or constructed here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import features_e2 as fe

REPO_ROOT = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# synthetic fixtures
# ---------------------------------------------------------------------------
def make_chunk(chunk_id, section_type, *, sentiment=None, guidance=None,
               guidance_applicable=False, guidance_imputed_none=False,
               schema_valid=True, red_flags=(), home_cik=1, home_date="2020-01-01",
               sources=((1, "acc-1", "2020-01-01", "10-K"),), train_overlap=False,
               selfid=False):
    """One synthetic chunk row. `sources` is the baked parallel-array primitive:
    a tuple of (cik, accession_number, filing_date, form) occurrences."""
    return {
        "chunk_id": chunk_id,
        "section_type": section_type,
        "sentiment": sentiment,
        "guidance_direction": guidance,
        "guidance_applicable": guidance_applicable,
        "guidance_imputed_none": guidance_imputed_none,
        "schema_valid": schema_valid,
        "schema_issues": [],
        "red_flags": [{"category": c, "modality": m} for c, m in red_flags],
        "home_cik": home_cik,
        "home_company_name": "TEST CO",
        "home_accession_number": "home-acc",
        "home_filing_date": home_date,
        "source_ciks": [s[0] for s in sources],
        "source_accession_numbers": [s[1] for s in sources],
        "source_filing_dates": [s[2] for s in sources],
        "source_forms": [s[3] for s in sources],
        "n_source_filings": len(sources),
        "train_overlap": train_overlap,
        "selfid": selfid,
    }


def frame_of(*rows) -> pd.DataFrame:
    return pd.DataFrame(list(rows))


def features_of(*rows) -> pd.DataFrame:
    scored = fe.score_labels(frame_of(*rows))
    occ = fe.explode_occurrences(scored, [])
    fe.verify_no_backward_flow(occ, [])
    return fe.build_text_features(occ, [])


# ---------------------------------------------------------------------------
# section masks (G2 §3.4) -- applied BEFORE aggregation
# ---------------------------------------------------------------------------
def test_sentiment_is_nulled_on_risk_factors():
    scored = fe.score_labels(frame_of(
        make_chunk("c1", "RISK_FACTORS", sentiment="NEGATIVE"),
        make_chunk("c2", "MDA", sentiment="NEGATIVE"),
        make_chunk("c3", "EX99_PRESS_RELEASE", sentiment="POSITIVE"),
    ))
    assert np.isnan(scored.sentiment_num.iloc[0])      # masked, not scored
    assert scored.sentiment_num.iloc[1] == -1.0
    assert scored.sentiment_num.iloc[2] == 1.0


def test_masked_risk_factors_sentiment_never_reaches_the_aggregate():
    """The whole point of masking BEFORE aggregation: an off-matrix NEGATIVE
    must not move sentiment_mean_score or sentiment_negative_share."""
    with_offmatrix = features_of(
        make_chunk("c1", "MDA", sentiment="POSITIVE"),
        make_chunk("c2", "RISK_FACTORS", sentiment="NEGATIVE"),
    )
    assert with_offmatrix.sentiment_mean_score.iloc[0] == 1.0
    assert with_offmatrix.sentiment_negative_share.iloc[0] == 0.0


def test_guidance_is_nulled_on_mda_and_risk_factors():
    scored = fe.score_labels(frame_of(
        make_chunk("c1", "MDA", guidance="RAISED", guidance_applicable=False),
        make_chunk("c2", "RISK_FACTORS", guidance="LOWERED", guidance_applicable=False),
        make_chunk("c3", "EX99_PRESS_RELEASE", guidance="RAISED", guidance_applicable=True),
    ))
    assert scored.guidance_num.isna().iloc[0]
    assert scored.guidance_num.isna().iloc[1]
    assert scored.guidance_num.iloc[2] == 1.0


def test_off_matrix_active_guidance_would_have_scored_without_the_mask():
    """Guards the mask itself: GUIDANCE_MAP maps these values to +/-1/0, so the
    230 off-matrix active E2 rows are exactly what the mask exists to stop."""
    assert fe.GUIDANCE_MAP["RAISED"] == 1.0
    assert fe.GUIDANCE_MAP["LOWERED"] == -1.0
    feats = features_of(
        make_chunk("c1", "EX99_PRESS_RELEASE", guidance="NONE", guidance_applicable=True),
        make_chunk("c2", "MDA", guidance="RAISED", guidance_applicable=False),
    )
    assert feats.guidance_any_present.iloc[0] == 0.0
    assert np.isnan(feats.guidance_signed_mean.iloc[0])


# ---------------------------------------------------------------------------
# the explicit guidance_applicable filter, and nulls that stay null
# ---------------------------------------------------------------------------
def test_guidance_applicable_filter_is_explicit():
    scored = fe.score_labels(frame_of(
        make_chunk("c1", "EX99_PRESS_RELEASE", guidance="RAISED", guidance_applicable=False),
        make_chunk("c2", "EX99_PRESS_RELEASE", guidance="RAISED", guidance_applicable=True),
    ))
    assert scored.guidance_num.isna().iloc[0]
    assert scored.guidance_num.iloc[1] == 1.0


def test_branching_is_never_on_schema_valid():
    """G2's implementer trap: schema_valid == False does not imply a null
    guidance value, and a schema-invalid row with a usable stored value is
    scored exactly like any other."""
    scored = fe.score_labels(frame_of(
        make_chunk("c1", "EX99_PRESS_RELEASE", guidance="LOWERED",
                   guidance_applicable=True, schema_valid=False),
    ))
    assert scored.guidance_num.iloc[0] == -1.0


def test_null_guidance_enum_stays_null_and_is_not_remapped():
    scored = fe.score_labels(frame_of(
        make_chunk("c1", "EX99_PRESS_RELEASE", guidance=None,
                   guidance_applicable=True, schema_valid=False),
    ))
    assert scored.guidance_num.isna().iloc[0]


def test_imputed_none_counts_as_none():
    """An imputed NONE is NONE by the F4 writer rule: no score, no presence,
    and it does not dilute the signed mean toward zero either."""
    scored = fe.score_labels(frame_of(
        make_chunk("c1", "EX99_PRESS_RELEASE", guidance="NONE",
                   guidance_applicable=True, guidance_imputed_none=True),
    ))
    assert scored.guidance_num.isna().iloc[0]

    feats = features_of(
        make_chunk("c1", "EX99_PRESS_RELEASE", guidance="RAISED", guidance_applicable=True),
        make_chunk("c2", "EX99_PRESS_RELEASE", guidance="NONE",
                   guidance_applicable=True, guidance_imputed_none=True),
        make_chunk("c3", "EX99_PRESS_RELEASE", guidance="NONE", guidance_applicable=True),
    )
    assert feats.guidance_any_present.iloc[0] == 1.0
    assert feats.guidance_signed_mean.iloc[0] == 1.0   # NONE excluded, not zero-filled


def test_withdrawn_maps_to_minus_one_like_e1():
    scored = fe.score_labels(frame_of(
        make_chunk("c1", "EX99_PRESS_RELEASE", guidance="WITHDRAWN", guidance_applicable=True),
    ))
    assert scored.guidance_num.iloc[0] == -1.0


# ---------------------------------------------------------------------------
# every-occurrence attribution, CIK-keyed
# ---------------------------------------------------------------------------
def test_every_occurrence_explosion_uses_cik_keys():
    """One chunk, three occurrences, two companies -> three occurrence rows and
    a per-(cik, accession) feature row for each filing. `source_ciks` is the
    ownership key; there is no ticker anywhere."""
    occ = fe.explode_occurrences(fe.score_labels(frame_of(
        make_chunk("c1", "MDA", sentiment="NEGATIVE", home_cik=11,
                   sources=((11, "a1", "2020-01-01", "10-K"),
                            (11, "a2", "2020-05-01", "10-Q"),
                            (22, "b1", "2020-06-01", "10-Q"))),
    )), [])
    assert len(occ) == 3
    assert list(occ.cik) == [11, 11, 22]
    assert "ticker" not in occ.columns
    assert (occ.sentiment_num == -1.0).all()

    feats = fe.build_text_features(occ, [])
    assert len(feats) == 3
    assert set(feats.cik) == {11, 22}
    assert list(feats.columns[:4]) == ["cik", "accession_number", "filing_date", "form"]
    assert (feats.n_text_chunks_attributed == 1).all()
    # the label reaches the other company's filing, and is flagged as such
    other = feats[feats.cik == 22].iloc[0]
    assert other.sentiment_mean_score == -1.0
    assert other.cross_cik_share == 1.0


def test_attribution_covers_a_filing_with_no_home_chunks_of_its_own():
    """The coverage motivation for every-occurrence attribution: filing `a2`
    owns no home chunk yet still receives features."""
    feats = features_of(
        make_chunk("c1", "RISK_FACTORS", sentiment=None, home_date="2020-01-01",
                   red_flags=(("DEMAND_WEAKNESS", "HYPOTHETICAL"),),
                   sources=((7, "a1", "2020-01-01", "10-K"),
                            (7, "a2", "2021-01-01", "10-K"))),
    )
    assert set(feats.accession_number) == {"a1", "a2"}
    assert (feats.redflag_DEMAND_WEAKNESS_rate_risk_factors == 1.0).all()


def test_occurrence_count_equals_sum_of_source_arrays():
    rows = [
        make_chunk("c1", "MDA", sources=((1, "a", "2020-01-01", "10-K"),)),
        make_chunk("c2", "MDA", sources=((1, "a", "2020-01-01", "10-K"),
                                         (1, "b", "2020-02-01", "8-K"))),
    ]
    occ = fe.explode_occurrences(fe.score_labels(frame_of(*rows)), [])
    assert len(occ) == 3


def test_explosion_rejects_a_desynchronised_length_column():
    bad = frame_of(make_chunk("c1", "MDA", sources=((1, "a", "2020-01-01", "10-K"),)))
    bad.loc[0, "n_source_filings"] = 2
    with pytest.raises(AssertionError, match="n_source_filings_matches_array_lengths"):
        fe.explode_occurrences(fe.score_labels(bad), [])


# ---------------------------------------------------------------------------
# no backward flow -- E1's property, restated for E2
# ---------------------------------------------------------------------------
def test_no_backward_flow_passes_when_every_occurrence_is_at_or_after_home():
    occ = fe.explode_occurrences(fe.score_labels(frame_of(
        make_chunk("c1", "MDA", home_date="2020-01-01",
                   sources=((1, "a", "2020-01-01", "10-K"),
                            (1, "b", "2021-01-01", "10-K"))),
    )), [])
    fe.verify_no_backward_flow(occ, [])   # must not raise


def test_no_backward_flow_raises_on_an_earlier_occurrence():
    """E1 (`features.attach_company_and_verify_no_backward_flow`) raises when an
    occurrence attaches to a filing dated BEFORE its own chunk's home filing
    date -- the look-ahead failure mode every-occurrence attribution must never
    produce. Restated for E2 with CIK ownership."""
    occ = fe.explode_occurrences(fe.score_labels(frame_of(
        make_chunk("c1", "MDA", home_date="2021-01-01",
                   sources=((1, "a", "2020-01-01", "10-K"),)),
    )), [])
    with pytest.raises(AssertionError, match="no_backward_flow"):
        fe.verify_no_backward_flow(occ, [])


# ---------------------------------------------------------------------------
# aggregation definitions (E1 parity)
# ---------------------------------------------------------------------------
def test_section_shares_and_counts():
    feats = features_of(
        make_chunk("c1", "MDA"),
        make_chunk("c2", "MDA"),
        make_chunk("c3", "RISK_FACTORS"),
        make_chunk("c4", "EX99_PRESS_RELEASE"),
    )
    row = feats.iloc[0]
    assert row.n_text_chunks_attributed == 4
    assert row.share_chunks_mda == 0.5
    assert row.share_chunks_risk_factors == 0.25
    assert row.share_chunks_ex99_press_release == 0.25
    assert row.share_chunks_8k_body == 0.0
    assert row.n_chunks_mda == 2 and row.n_chunks_risk_factors == 1


def test_sentiment_negative_share_denominator_is_scored_chunks_only():
    feats = features_of(
        make_chunk("c1", "MDA", sentiment="NEGATIVE"),
        make_chunk("c2", "MDA", sentiment="NEUTRAL"),
        make_chunk("c3", "MDA", sentiment=None),           # unlabeled: not a denominator
        make_chunk("c4", "RISK_FACTORS", sentiment="NEGATIVE"),  # masked
    )
    assert feats.sentiment_negative_share.iloc[0] == 0.5
    assert feats.sentiment_mean_score.iloc[0] == -0.5


def test_sentiment_features_are_nan_when_nothing_is_scored():
    feats = features_of(make_chunk("c1", "RISK_FACTORS", sentiment="NEUTRAL"))
    assert np.isnan(feats.sentiment_mean_score.iloc[0])
    assert np.isnan(feats.sentiment_negative_share.iloc[0])
    assert feats.guidance_any_present.iloc[0] == 0.0   # presence is 0.0, never NaN


def test_red_flag_rates_are_per_section_and_nan_without_that_section():
    feats = features_of(
        make_chunk("c1", "MDA", red_flags=(("DEMAND_WEAKNESS", "REALIZED"),)),
        make_chunk("c2", "MDA"),
        make_chunk("c3", "EX99_PRESS_RELEASE",
                   red_flags=(("TRADE_POLICY_EXPOSURE", "HYPOTHETICAL"),)),
    )
    row = feats.iloc[0]
    assert row.redflag_DEMAND_WEAKNESS_rate_mda == 0.5
    assert np.isnan(row.redflag_DEMAND_WEAKNESS_rate_risk_factors)
    assert row.redflag_any_rate_press == 1.0
    # modality is never split into its own feature (E1 binding constraint 2)
    assert not any("REALIZED" in c or "HYPOTHETICAL" in c for c in feats.columns)


def test_provenance_flags_aggregate_to_per_filing_shares():
    feats = features_of(
        make_chunk("c1", "MDA", train_overlap=True, selfid=True),
        make_chunk("c2", "MDA", train_overlap=False, selfid=True),
        make_chunk("c3", "MDA", train_overlap=False, selfid=False),
    )
    assert feats.train_overlap_share.iloc[0] == pytest.approx(1 / 3)
    assert feats.selfid_share.iloc[0] == pytest.approx(2 / 3)


def test_output_carries_the_22_e1_feature_names():
    feats = features_of(make_chunk("c1", "MDA"))
    expected = set(fe.TEXT_FEATURE_NAMES_NON_REDFLAG) | set(fe.RED_FLAG_FEATURE_NAMES)
    assert len(expected) == 22
    assert expected <= set(feats.columns)


def test_feature_partition_is_8_confirmatory_13_exploratory_1_dropped():
    assert len(fe.CONFIRMATORY_FEATURES) == 8
    assert len(fe.EXPLORATORY_FEATURES) == 13
    assert fe.DROPPED_FEATURES == ["share_chunks_8k_body"]
    assert all(c.startswith("redflag_") for c in fe.EXPLORATORY_FEATURES)


# ---------------------------------------------------------------------------
# provenance-flag definitions (G2 §10.1)
# ---------------------------------------------------------------------------
def test_normalization_is_whitespace_collapse_strip_lower():
    assert fe._normalize("  A   B\nC ") == "a b c"
    assert fe._sha1_norm("A  B") == fe._sha1_norm(" a b ")


def test_distinctive_token_skips_generic_suffixes():
    assert fe._distinctive_token("BANK OF AMERICA CORP /DE/") == "bank"
    assert fe._distinctive_token("THE COCA-COLA COMPANY") == "coca-cola"
    assert fe._distinctive_token("Inc. Corp.") == ""


def test_train_overlap_definition_forbids_an_id_join():
    assert "Paragraph-id joins are FORBIDDEN" in fe.TRAIN_OVERLAP_DEFINITION


# ---------------------------------------------------------------------------
# the freeze (F5_PLAN §1)
# ---------------------------------------------------------------------------
def test_module_computes_no_association_statistic():
    src = (REPO_ROOT / "features_e2.py").read_text()
    for token in (".corr(", "spearman", "pearsonr", "information_coefficient",
                  "target_excess", "forward_return"):
        assert token not in src, f"features_e2.py must not reference {token}"


def test_module_reads_no_price_or_fundamental_row():
    """prices_e2 / fundamentals_e2 / the metadata DB are sha-recorded for the
    record, never opened as data by this module."""
    src = (REPO_ROOT / "features_e2.py").read_text()
    assert "read_parquet(PRICES_PATH" not in src
    assert "read_parquet(FUNDAMENTALS_PATH" not in src
    assert "sqlite3" not in src


# ---------------------------------------------------------------------------
# real-data census (slow)
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_real_mask_and_applicable_census():
    """Re-derived from data/f4/labels_e2_v1.parquet, not read back from the
    manifest."""
    lab = pd.read_parquet(fe.LABELS_PATH, columns=[
        "section_type", "sentiment", "guidance_direction", "guidance_applicable",
        "guidance_imputed_none", "schema_valid", "schema_issues"])
    frame = lab[lab.section_type != "8K_BODY"]
    assert len(lab) == fe.N_CORPUS
    assert len(frame) == fe.N_FRAME
    assert int((lab.section_type == "8K_BODY").sum()) == fe.N_8K_BODY

    rf_sent = frame[(frame.section_type == "RISK_FACTORS") & frame.sentiment.notna()]
    assert len(rf_sent) == fe.N_SENTIMENT_MASKED
    assert rf_sent.sentiment.value_counts().to_dict() == {
        "NEUTRAL": 3452, "NEGATIVE": 688, "POSITIVE": 37}

    off = frame[frame.section_type.isin(["MDA", "RISK_FACTORS"])
                & frame.guidance_direction.notna()]
    assert len(off) == fe.N_GUIDANCE_MASKED
    assert off.section_type.value_counts().to_dict() == {
        "MDA": fe.N_GUIDANCE_MASKED_MDA, "RISK_FACTORS": fe.N_GUIDANCE_MASKED_RF}
    assert int(off.guidance_direction.isin(fe.GUIDANCE_MAP).sum()) == fe.N_GUIDANCE_MASKED_ACTIVE

    assert int(lab.guidance_applicable.fillna(False).sum()) == fe.N_APPLICABLE_CORPUS
    assert int(lab.guidance_imputed_none.fillna(False).sum()) == fe.N_IMPUTED_NONE_CORPUS
    assert int(frame.guidance_applicable.fillna(False).sum()) == fe.N_APPLICABLE_FRAME
    assert int((frame.guidance_applicable.fillna(False)
                & frame.guidance_direction.isna()).sum()) == fe.N_GUIDANCE_ENUM_NULL

    issues: dict[str, int] = {}
    for row in lab.loc[~lab.schema_valid, "schema_issues"]:
        for issue in row:
            issues[issue] = issues.get(issue, 0) + 1
    assert int((~lab.schema_valid).sum()) == fe.N_SCHEMA_INVALID
    assert issues["bad_enum:red_flag_category"] == fe.N_RF_CATEGORY_DROPS
    assert issues["bad_enum:red_flag_modality"] == fe.N_RF_MODALITY_DROPS
    assert issues["bad_enum:guidance_direction"] == fe.N_GUIDANCE_ENUM_NULL


@pytest.mark.slow
def test_real_build_reproduces_every_pinned_census_number():
    """Full build (~20 s): all module assertions pass and the G2 provenance
    counts reproduce on the 316,291-row frame."""
    feats, manifest, dictionary = fe.build()
    assert all(a["passed"] for a in manifest["assertions"])
    assert len(manifest["assertions"]) >= 50

    census = manifest["census"]
    assert census["frame_rows"] == fe.N_FRAME
    assert census["occurrence_rows"] == 854933
    assert census["filings"] == len(feats) == 14446
    assert census["distinct_ciks"] == 176
    assert census["train_overlap_frame_chunks"] == fe.N_TRAIN_OVERLAP
    assert census["selfid_frame_chunks"] == fe.N_SELFID
    assert census["selfid_frame_share"] == pytest.approx(0.4646, abs=5e-5)
    assert census["train_overlap_channels"]["frame"]["home_accession"] == 10442
    assert census["train_overlap_channels"]["frame"]["any_source_accession"] == 14341
    assert census["train_overlap_channels"]["frame"]["normalized_text"] == 487
    assert census["guidance_imputed_none_frame"] == 48293
    assert float(feats.share_chunks_8k_body.max()) == 0.0
    assert not feats.duplicated(["cik", "accession_number"]).any()
    assert dictionary["partitions"]["confirmatory"] == fe.CONFIRMATORY_FEATURES


@pytest.mark.slow
def test_artifact_on_disk_matches_this_module_and_its_manifest():
    manifest = json.loads(fe.OUT_MANIFEST.read_text())
    assert manifest["module_sha256"] == fe._sha256_file(REPO_ROOT / "features_e2.py"), \
        "manifest is stale -- re-run `python3 features_e2.py`"
    assert manifest["artifact_sha256"] == fe._sha256_file(fe.OUT_PARQUET)
    assert manifest["no_ic_computed"] is True
    assert manifest["network_calls"] == 0 and manifest["api_calls"] == 0
    for key in ("data/prices_e2.parquet", "data/fundamentals_e2.parquet",
                "data/filings_metadata_e2.db"):
        assert re.fullmatch(r"[0-9a-f]{64}", manifest["inputs_recorded_not_read"][key])


@pytest.mark.slow
def test_dictionary_uses_e2_caveat_constants_and_never_e1s():
    text = fe.OUT_DICTIONARY.read_text()
    assert "36.6" not in text and "63.4" not in text, \
        "E1's teacher constants must never be carried onto Qwen student labels"
    assert "42.00%" in text and "84/200" in text        # v1.2 teacher spot-check
    assert "293/337" in text and "115/119" in text      # G2 student spot-check
    assert "68.67%" in text                             # guidance active precision
    assert "0/80" in text                               # false-NONE rate
    assert "EXPLORATORY" in text

    dictionary = json.loads(text)
    for name in fe.EXPLORATORY_FEATURES:
        assert dictionary["features"][name]["partition"] == "exploratory"
    assert dictionary["features"]["share_chunks_8k_body"]["partition"] == "dropped"
    for name in fe.CONFIRMATORY_FEATURES:
        assert dictionary["features"][name]["partition"] == "confirmatory"
