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


@pytest.fixture
def rendered(tmp_path):
    js = tmp_path / "head1_scorecard.json"
    js.write_text(json.dumps(FIXTURE))
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
    js = tmp_path / "bad.json"
    js.write_text(json.dumps(bad))
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


def test_identity_scopes_public_data_and_carries_self_identification(rendered):
    _, pages = rendered
    for html in pages.values():
        assert "fundamentals and prices as they were public at that filing date" in html
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
    js = tmp_path / "one.json"
    js.write_text(json.dumps(one))
    SP.render_all(js, tmp_path / "out", tmp_path / "companies")
    html = unescape((tmp_path / "out" / "222" / "scorecard.html").read_text())
    assert "no hit rate: 1 call, fewer than the 6" in html and "1 calls" not in html
    assert "no hit rate (1 call < 6)" in unescape((tmp_path / "out" / "scorecard.html").read_text())
