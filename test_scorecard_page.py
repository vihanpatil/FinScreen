"""Offline tests for scorecard_page.py: a 2-company fixture JSON in tmp_path."""
import ast
import hashlib
import json
import re
from html import unescape
from pathlib import Path

import pytest

import scorecard_page as SP
from scorecard_e2 import DISCLOSURE_ORDER

DISCLOSURES = {key: f"Disclosure text for {key}, verbatim from the run." for key, _ in DISCLOSURE_ORDER}
BLOCK = {"n_rows": 10, "n_calls": 8, "n_correct": 5, "n_outperform": 4, "n_underperform": 4,
         "hit_rate": 0.625, "wilson_lo": 0.3057, "wilson_hi": 0.8632, "n_no_call": 2,
         "n_tied_no_call": 0, "n_unresolved": 0, "chance_from_call_counts": 0.5,
         "chance_sentence": "Chance under this call rule: 0.50.", "denominator": "Denominator = 8."}


def _row(q, acc, x, model, numeric, size):
    """model/numeric/size: (call, result) per block, distinct so a column swap fails."""
    r = {"test_quarter": q, "form": "10-Q", "filing_date": "2020-01-30", "accession_number": acc,
         "excess_return_pct": x}
    for b, (call, result) in zip(("text_and_numeric", "numeric_only", "size_only"),
                                 (model, numeric, size)):
        r[f"{b}_call"], r[f"{b}_result"] = call, result
    return r


OUT_R, OUT_W = ("outperform peers", "right"), ("outperform peers", "wrong")
UND_R, UND_W = ("underperform peers", "right"), ("underperform peers", "wrong")
NONE = ("no call", None)


FIXTURE = {
    "universe": {
        "generated_utc": "2026-11-05T22:22:19+00:00",
        "blocks": {"text_and_numeric": dict(BLOCK, label="the model"),
                   "numeric_only": dict(BLOCK, label="numeric only", n_calls=9, n_correct=4,
                                        hit_rate=0.4444, wilson_lo=0.1888, wilson_hi=0.7333,
                                        n_no_call=1, n_tied_no_call=1),
                   "size_only": dict(BLOCK, label="size only", n_calls=7, n_correct=3,
                                     hit_rate=0.4286, wilson_lo=0.1582, wilson_hi=0.7495,
                                     n_no_call=3, n_tied_no_call=2)},
        "n_filings_scored": 10, "n_companies": 2, "n_test_quarters": 2,
        "outcome_mix_positive_excess": 0.5, "outcome_mix_label": "outcome mix (share positive)",
        "chance_sentence": "Universe chance sentence.", "call_rule": "tercile_within_test_quarter",
        "tie_rule": "average_rank_straddle_no_call", "correct_rule": "sign_match_nonzero",
        "ci": "wilson_95", "scope_sentence": "Scope sentence S.",
        "inference_sentence": "Inference sentence I.",
        "prices_sentence": "Prices: snapshot, 31 of 244 universe members without usable prices; peers.",
        "arm": "pit_trailing_rank", "eval_set": "dedup", "min_calls_for_company_hit_rate": 6,
        "disclosures": DISCLOSURES,
        "margin": {"status": "POWERED", "delta_selected": 0.04, "note": "margin note N."},
        "files": {},
    },
    "companies": [
        {"cik": 222, "name": "Zeta Corp", "ticker": None,
         "summary": {"n_rows": 3, "n_calls": 2, "n_correct": None, "n_outperform": None,
                     "n_underperform": None, "hit_rate": None, "wilson_lo": None, "wilson_hi": None,
                     "n_no_call": 1, "n_tied_no_call": 0, "n_unresolved": 0, "chance_sentence": None,
                     "denominator": "Denominator = 2 scored calls out of 3 rows.",
                     "outcome_mix": 0.3333, "n_filings": 3, "min_calls_for_hit_rate": 6,
                     "block": "text_and_numeric"},
         "rows": [_row("2020Q1", "0000000222-20-000001", -1.5, UND_R, NONE, OUT_W),
                  _row("2020Q2", "0000000222-20-000002", 2.0, NONE, UND_W, OUT_R)]},
        {"cik": 333, "name": "Alpha Inc.", "ticker": "ALPH",
         "summary": {"n_rows": 9, "n_calls": 7, "n_correct": 5, "n_outperform": 4,
                     "n_underperform": 3, "hit_rate": 0.7142857142857143,
                     "wilson_lo": 0.3589, "wilson_hi": 0.9178, "n_no_call": 2,
                     "n_tied_no_call": 0, "n_unresolved": 0,
                     "chance_sentence": "Chance under this call rule: 0.50; from counts: 0.510.",
                     "denominator": "Denominator = 7 scored calls out of 9 rows.",
                     "outcome_mix": 0.5556, "n_filings": 9, "min_calls_for_hit_rate": 6,
                     "block": "text_and_numeric"},
         "rows": [_row("2020Q1", "0000000333-20-000001", 3.14159, OUT_R, UND_W, NONE),
                  _row("2020Q2", "0000000333-20-000002", -0.5, OUT_W, NONE, UND_R)]},
    ],
}


CENSUS = {"n_rows": 10, "n_rows_before_later_event": 3, "n_companies": 2,
          "n_companies_affected": 1, "threshold": 1.8, "affected_rows_by_cik": {"333": 2},
          "events": [{"cik": 333, "filing_date": "2020-06-01", "ratio": 4.0}]}


# The post-hoc seed-matched measurement, in the committed artifact's own shape.
SEEDS = {"seed_matched_arm_minus_primary": {"arm_b": {
             "delta": {"n_seeds": 100, "mean": 0.0026},
             "ic_text_and_numeric": {"mean": -0.0107},
             "ic_numeric_only": {"mean": -0.0133}}},
         "factor_reach": {"n_scored_dedup_rows": 10,
                          "factor_not_1_with_book_to_market": {"n_rows": 4, "n_companies": 2}},
         "calls_differing_from_ratified_seed0": {"primary": {"text_and_numeric": {
             "min": 2, "median": 3.5, "max": 5}}}}


def _write(tmp_path, data, name="head1_scorecard.json", census=CENSUS, seeds=SEEDS):
    """The scorecard JSON, with the split census and the post-hoc measurement beside it."""
    js = tmp_path / name
    js.write_text(json.dumps(data))
    if census is not None:
        (tmp_path / SP.CENSUS_NAME).write_text(json.dumps(census))
    if seeds is not None:
        (tmp_path / SP.SEEDS_NAME).write_text(json.dumps(seeds))
    return js


@pytest.fixture
def rendered(tmp_path):
    js = _write(tmp_path, FIXTURE)
    out, companies = tmp_path / "reports", tmp_path / "companies"
    (out / "333").mkdir(parents=True)
    (out / "333" / "0000000333-20-000001.html").write_text("filing page")
    (companies / "222").mkdir(parents=True)
    (companies / "222" / "manifest.json").write_text(json.dumps({"ticker": "ZETA"}))
    SP.render_all(js, out, companies)
    pages = {"333": out / "333" / "scorecard.html", "222": out / "222" / "scorecard.html",
             "universe": out / "scorecard.html"}
    return js, {k: unescape(p.read_text()) for k, p in pages.items()}


def test_all_three_pages_render(rendered):
    _, pages = rendered
    assert "Alpha Inc. (ALPH) — historical scorecard, E2 head 1" in pages["333"]
    assert "Zeta Corp (ZETA) — historical scorecard, E2 head 1" in pages["222"]  # manifest fallback
    assert "every company" in pages["universe"]


def test_hit_rate_is_the_fixture_value_to_4dp(rendered):
    _, pages = rendered
    assert "hit rate 0.7143, 95% Wilson interval [0.3589, 0.9178]" in pages["333"]
    assert "5 of 7 calls right" in pages["333"]
    assert "0.7143 [0.3589, 0.9178]" in pages["universe"]


def test_null_hit_rate_prints_the_no_hit_rate_text_and_no_chance_line(rendered):
    _, pages = rendered
    assert "no hit rate: 2 calls, fewer than the 6 the pre-registration requires" in pages["222"]
    assert "Chance under this call rule" not in pages["222"]
    assert "no hit rate (2 calls < 6)" in pages["universe"]


def test_companies_are_alphabetical_by_name(rendered):
    """Name order (Alpha, Zeta) is opposite to CIK order (222, 333) and to JSON order."""
    _, pages = rendered
    u = pages["universe"]
    assert u.index("Alpha Inc.") < u.index("Zeta Corp")
    assert [c["cik"] for c in FIXTURE["companies"]] == [222, 333]


def test_every_page_carries_all_8_disclosures_and_the_footer(rendered):
    _, pages = rendered
    for html in pages.values():
        block = html.split('<section class="disclosure">')[1].split("</section>")[0]
        assert SP.DISCLOSURE_HEADING in block and "<details" not in html
        for text in DISCLOSURES.values():
            assert text in block
        assert SP.SCORECARD_FOOTER_LINE in html


def test_run_sentences_are_quoted_verbatim(rendered):
    _, pages = rendered
    u = FIXTURE["universe"]
    for html in pages.values():
        for s in (u["scope_sentence"], u["inference_sentence"], u["prices_sentence"],
                  u["margin"]["note"], SP.RF.predictive_validity_sentence()):
            assert s in html


def test_sha256_line_matches_the_fixture_file(rendered):
    js, pages = rendered
    sha = hashlib.sha256(js.read_bytes()).hexdigest()
    for html in pages.values():
        assert f"sha256 <code>{sha}</code>" in html
        assert "2026-11-05T22:22:19+00:00" in html


def test_accession_is_linked_only_when_its_page_exists(rendered):
    _, pages = rendered
    assert '<a href="0000000333-20-000001.html">0000000333-20-000001</a>' in pages["333"]
    assert 'href="0000000333-20-000002.html"' not in pages["333"]
    assert "0000000333-20-000002" in pages["333"]


def test_row_cells_and_signed_excess_return(rendered):
    _, pages = rendered
    assert "+3.14%" in pages["333"] and "-0.50%" in pages["333"]
    # column order = the model, numeric only, size only; each block's own call per row
    assert ("<td>outperform peers (right)</td><td>underperform peers (wrong)</td>"
            "<td>no call</td></tr>") in pages["333"]
    assert ("<td>outperform peers (wrong)</td><td>no call</td>"
            "<td>underperform peers (right)</td></tr>") in pages["333"]
    assert ("<td>no call</td><td>underperform peers (wrong)</td>"
            "<td>outperform peers (right)</td></tr>") in pages["222"]


def test_rendering_is_deterministic(tmp_path, rendered):
    js, pages = rendered
    out = tmp_path / "again"
    SP.render_all(js, out, tmp_path / "companies")
    assert unescape((out / "scorecard.html").read_text()) == pages["universe"]


def test_missing_disclosure_refuses(tmp_path):
    bad = json.loads(json.dumps(FIXTURE))
    del bad["universe"]["disclosures"]["fx"]
    js = _write(tmp_path, bad, "bad.json")
    with pytest.raises(SystemExit, match="disclosures missing"):
        SP.render_all(js, tmp_path / "out", tmp_path / "companies")


REFUSED = re.compile(r"\b(advice|advis\w*|recommend\w*|buy\w*|sell\w*|should|signal\w*|"
                     r"predict\w*|rank\w*|score[sd]?|scoring)\b", re.I)


def test_the_modules_own_strings_carry_no_refused_vocabulary():
    """Every string literal in scorecard_page.py (the JSON's verbatim text is exempt)."""
    tree = ast.parse(Path(SP.__file__).read_text())
    hits = [(n.lineno, n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and REFUSED.search(n.value)]
    assert hits == []


def test_real_json_renders_apple(tmp_path):
    if not SP.SCORECARD_JSON.exists():
        pytest.skip("data/f5/head1_scorecard.json not on this machine (git-ignored)")
    SP.render_all(SP.SCORECARD_JSON, tmp_path, SP.COMPANIES_DIR, cik=320193)
    html = unescape((tmp_path / "320193" / "scorecard.html").read_text())
    assert "20 of 28 calls right" in html and "0.7143" in html


def test_universe_blocks_appear_on_every_company_page(rendered):
    _, pages = rendered
    for key in ("333", "222", "universe"):
        html = pages[key]
        for row in ("<td>the model</td><td>8</td>", "<td>numeric only</td><td>9</td>",
                    "<td>size only</td><td>7</td>"):
            assert row in html
        assert "[0.1888, 0.7333]" in html and "3 (2)" in html
        assert FIXTURE["universe"]["chance_sentence"] in html
    assert "Universe, for comparison" in pages["333"]


def test_company_pages_explain_the_call_rule_and_the_linked_pages(rendered):
    _, pages = rendered
    rule = SP.CALL_RULE_TEMPLATE.format(sessions=SP.C.HOLDING_DAYS)
    for key in ("333", "222"):
        assert rule in pages[key] and SP.LINKED_PAGES_LINE in pages[key]
    assert "16:00 ET" in rule and "63 sessions" in rule and "never a real-time one" in rule


def _in_order(html, *marks):
    at = [html.index(m) for m in marks]
    return at == sorted(at)


def test_own_result_comes_before_universe_provenance_and_disclosures(rendered):
    _, pages = rendered
    for key in ("333", "222"):
        assert _in_order(pages[key], "<h1>", 'class="identity"', SP.RF.SELFID_STRICT_TEXT,
                         "Known defect", "<h2>Summary</h2>",
                         "<h2>Filing by filing", SP.LINKED_PAGES_LINE, "<table>",
                         "<h2>Universe, for comparison</h2>", "<h2>How a call is made</h2>",
                         "Source: <code>", "E2 outcome:",
                         'class="disclosure"', 'class="footer-line"')
    assert _in_order(pages["universe"], "<h1>", 'class="identity"', SP.RF.SELFID_STRICT_TEXT,
                     "Known defect", "<h2>Universe</h2>",
                     "<h2>Companies, alphabetical", "<th>Hit rate [95% Wilson]</th>", "Source: <code>",
                     "E2 outcome:",
                     'class="disclosure"', 'class="footer-line"')


def test_identity_scopes_public_data_and_carries_self_identification(rendered):
    _, pages = rendered
    for html in pages.values():
        assert ("fundamentals and prices dated on or before that filing date (with one known "
                "exception, the book-to-market defect stated below)") in html
        assert "as they were public at that filing date" not in html
        assert "only data public" not in html
        assert SP.RF.SELFID_STRICT_TEXT in html and SP.RF.SELFID_LOOSE_TEXT in html
        assert SP.RF.SELFID_SUBJECT in html


def test_coverage_sentence_does_not_claim_a_full_decomposition(rendered):
    _, pages = rendered
    u = pages["universe"]
    assert "2 of the 244 universe companies appear here" in u
    assert "31 of 244 universe members without usable prices" in u
    assert "the rest are not decomposed here" in u


def test_one_call_is_singular(tmp_path):
    one = json.loads(json.dumps(FIXTURE))
    one["companies"][0]["summary"]["n_calls"] = 1
    js = _write(tmp_path, one, "one.json")
    SP.render_all(js, tmp_path / "out", tmp_path / "companies")
    html = unescape((tmp_path / "out" / "222" / "scorecard.html").read_text())
    assert "no hit rate: 1 call, fewer than the 6" in html and "1 calls" not in html
    assert "no hit rate (1 call < 6)" in unescape((tmp_path / "out" / "scorecard.html").read_text())


# --- the book-to-market split look-ahead (REVIEW_p5_packet_2026-11-10 M3) -----------
def test_known_defect_paragraph_with_census_numbers_on_every_page(rendered):
    _, pages = rendered
    text = SP.DEFECT_TEMPLATE.format(n=4, total=10, k=2, seeds=100, d_model=0.0107,
                                     d_numeric=0.0133, d_delta=0.0026)
    assert "4 of the 10 rows in this run (2 companies) carried an inflated value" in text
    # a fall is printed as a positive size; the tested difference keeps its sign
    assert "the IC of the model falls by 0.011 and of numeric only by 0.013" in text
    assert "moves by +0.0026" in text and "labelled post-hoc" in text
    seed = SP.SEED_TEMPLATE.format(median=4, total=10, lo=2, hi=5, seeds=100)
    assert "alters about 4 of the 10 calls in the model column (between 2 and 5 across 100 seeds)" in seed
    for html in pages.values():
        assert text in html and seed in html
        assert html.index("Known defect") < html.index("How stable one row is") < html.index("<h2>")
        # directly after the identity paragraph, ahead of every figure
        assert html.index("Known defect, found 2026-11-10") < html.index("<h2>")
        assert html.index('class="identity"') < html.index("Known defect")


def test_the_one_of_them_sentence_only_on_an_affected_company(rendered):
    _, pages = rendered
    line = SP.DEFECT_COMPANY_TEMPLATE.format(m=2, threshold=1.8)
    assert line == ("The share-count census flags this company: 2 of its rows below were filed "
                    "before a later change of 1.8 times or more in its reported share count.")
    assert line in pages["333"]
    assert "The share-count census flags this company" not in pages["222"]
    assert "The share-count census flags this company" not in pages["universe"]


def test_census_sha_is_in_the_provenance_line(rendered, tmp_path):
    _, pages = rendered
    sha = hashlib.sha256((tmp_path / SP.CENSUS_NAME).read_bytes()).hexdigest()
    for html in pages.values():
        assert f"Book-to-market census: <code>{SP.CENSUS_NAME}</code>, sha256 <code>{sha}</code>" in html


def test_missing_census_refuses(tmp_path):
    js = _write(tmp_path, FIXTURE, census=None)
    with pytest.raises(SystemExit, match="census_split_lookahead.py"):
        SP.render_all(js, tmp_path / "out", tmp_path / "companies")
    assert not (tmp_path / "out" / "scorecard.html").exists()


def test_incomplete_census_refuses(tmp_path):
    js = _write(tmp_path, FIXTURE, census={"n_rows": 10})
    with pytest.raises(SystemExit, match="missing"):
        SP.render_all(js, tmp_path / "out", tmp_path / "companies")


def test_real_apple_page_carries_the_census_counts(tmp_path):
    census = SP.SCORECARD_JSON.parent / SP.CENSUS_NAME
    if not (SP.SCORECARD_JSON.exists() and census.exists()):
        pytest.skip("real scorecard JSON or census not on this machine")
    seeds = SP.SCORECARD_JSON.parent / SP.SEEDS_NAME
    if not seeds.exists():
        pytest.skip("the post-hoc seed-matched artifact is not on this machine")
    c, s = json.loads(census.read_text()), json.loads(seeds.read_text())
    reach = s["factor_reach"]["factor_not_1_with_book_to_market"]
    SP.render_all(SP.SCORECARD_JSON, tmp_path, SP.COMPANIES_DIR, cik=320193)
    html = unescape((tmp_path / "320193" / "scorecard.html").read_text())
    assert (f"{reach['n_rows']:,} of the {s['factor_reach']['n_scored_dedup_rows']:,} rows in this run "
            f"({reach['n_companies']} companies) carried an inflated value") in html
    assert (f"The share-count census flags this company: {c['affected_rows_by_cik']['320193']} of its "
            "rows below were filed before a later change of 1.8 times or more") in html


def test_missing_post_hoc_measurement_refuses(tmp_path):
    js = _write(tmp_path, FIXTURE, seeds=None)
    with pytest.raises(SystemExit, match="--seed-band"):
        SP.render_all(js, tmp_path / "out", tmp_path / "companies")


def test_incomplete_post_hoc_measurement_refuses(tmp_path):
    js = _write(tmp_path, FIXTURE, seeds={"factor_reach": {}})
    with pytest.raises(SystemExit, match="refusing to render"):
        SP.render_all(js, tmp_path / "out", tmp_path / "companies")
