"""
test_pin_g3.py -- tests for `data/f5/pin_g3.py`, the G3 ratification pin.

The owner ratified G3 on 2026-11-05 ("ratify", HANDOFF §3); the real
`data/f5/G3_RATIFIED.json` and the pinned `data/f5/G3_PREREGISTRATION.md` are
PERMANENT and must NEVER be deleted or re-written (re-pinning is forbidden).

EVERY procedure test runs on a SCRATCH COPY of the PRE-PIN document (git
`41829ad`, sha `42348bfc…`, the text the owner ratified) inside pytest's
`tmp_path`. Nothing here writes to `data/f5`: the real files are only ever
READ, and no test passes `--pin` at the real paths. The last test asserts the
real pin is intact and that the real document is exactly the declared pin of
the pre-pin text.

What is pinned here (red-team NF-9):
  * the substitution set leaves NO residue -- none of "ratification pending",
    "unratified", "RATIFICATION-READY", "not ratified", "______" survives;
  * the pinned scratch document is accepted by all three freeze guards
    (`backtest_e2.require_g3`, `backtest_e2.load_g3_params`,
    `heads_e2.load_ratified_params`), so the pin cannot brick the run;
  * `--show` is read-only -- byte-identical file before and after;
  * `--pin` without the owner's word refuses and writes nothing;
  * `--pin` without an EXPLICIT `--date` refuses and writes nothing -- there is
    no UTC default for the pin (red-team MF-6);
  * the eight rules are lettered (a)-(h), the same letters §0 of the
    pre-registration lists (red-team SH-3);
  * a document that has moved under the procedure refuses rather than being
    partially edited.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import backtest_e2 as BE  # noqa: E402
import heads_e2 as HE  # noqa: E402

_spec = importlib.util.spec_from_file_location("pin_g3", ROOT / "data" / "f5" / "pin_g3.py")
PG = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(PG)

REAL_DOC = ROOT / "data" / "f5" / "G3_PREREGISTRATION.md"
REAL_RATIFIED = ROOT / "data" / "f5" / "G3_RATIFIED.json"
DATE = "2026-09-30"

# The owner ratified G3 on 2026-11-05 (HANDOFF §3). The pin is permanent.
REAL_DOC_SHA256 = "6b99f65ea1da42e81afec2fef814800d18e5748ff7c2e025ec08862aa80c62c6"
REAL_PARAMS_SHA256 = "9ac479818785b6fc835aaf63dc9d73bff9fc3cbb0c5b14a9dac2e3f185b1984f"
PREPIN_COMMIT = "41829ad"
PREPIN_DOC_SHA256 = "42348bfccbe30b14e1380bca9a02820fb1947233079d0bc48bcbb87893de4c7d"
NEVER_DELETE_THE_PIN = (
    "data/f5/G3_RATIFIED.json is the owner's G3 ratification (word 'ratify', HANDOFF §3 "
    "2026-11-05). It and data/f5/G3_PREREGISTRATION.md must NEVER be deleted, edited or "
    "re-written: re-pinning is forbidden (it would be a new pre-registration). If this fails, "
    "restore both files from git commit fa9f5d9 and stop -- do not 'fix' this test."
)


@pytest.fixture(scope="module")
def prepin_text() -> str:
    """The pre-registration as it stood just before the pin (git object, read
    offline from the local repo, sha-verified). Never the real file."""
    out = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{PREPIN_COMMIT}:data/f5/G3_PREREGISTRATION.md"],
        capture_output=True, check=False)
    assert out.returncode == 0, (
        f"cannot read the pre-pin document from git {PREPIN_COMMIT}: {out.stderr!r}")
    assert hashlib.sha256(out.stdout).hexdigest() == PREPIN_DOC_SHA256
    return out.stdout.decode()


@pytest.fixture()
def scratch(tmp_path, prepin_text) -> Path:
    """A copy of the PRE-PIN pre-registration, in tmp_path. Never the real file."""
    dst = tmp_path / "G3_PREREGISTRATION.md"
    dst.write_text(prepin_text)
    return dst


def test_the_substitution_set_leaves_no_residue(scratch):
    before = scratch.read_text()
    after, report = PG.pinned_text(before, DATE)
    assert {r["id"] for r in report} == {r["id"] for r in PG.substitutions(DATE)}
    assert dict((r["id"], r["matches"]) for r in report)["c_table_headers"] == 13
    assert PG.residue(before), "the unpinned document really does carry the residue"
    assert PG.residue(after) == {}, PG.residue(after)
    for pattern in PG.RESIDUE_PATTERNS:
        assert pattern not in after, pattern
    # and the two lines the owner is shown verbatim are exactly these
    assert f'**STATUS: RATIFIED {DATE} — owner\'s word "ratify" in chat' in after
    assert f"\"draft_status\": \"RATIFIED {DATE} -- owner's word 'ratify'; sha pinned\"" in after
    assert f"**Ratified by the owner on {DATE} (HANDOFF §3 entry: {DATE}).**" in after
    assert f"Signature: the owner's word 'ratify' in chat (HANDOFF §3 {DATE})" in after
    assert f"RATIFIED rule (dec.; owner 2026-09-11; ratified {DATE})" in after
    assert f"**pinned at ratification on {DATE}**" in after
    assert f"the document is RATIFIED {DATE}" in after
    assert f"this document is ratified on {DATE}" in after


def test_the_rules_are_lettered_a_to_h_like_the_document(scratch):
    """Red-team SH-3: the script declares EIGHT rules and §0 of the
    pre-registration lists eight letters. Each rule's `id` starts with its own
    letter, in order, so the two lists can be read against each other -- and
    the two signature lines are (f) and (g), not both (f)."""
    rules = PG.substitutions(DATE)
    assert len(rules) == 8
    assert [r["id"][0] for r in rules] == list("abcdefgh")
    by_letter = {r["id"][0]: r["id"] for r in rules}
    assert by_letter["f"] == "f_signature_line_1"
    assert by_letter["g"] == "g_signature_line_2"
    assert by_letter["h"] == "h_header_paragraph_clause"
    assert "EXACTLY THESE EIGHT RULES" in PG.__doc__
    # the document says eight too, and names the same two signature lines
    doc = scratch.read_text()
    assert "EXACTLY the eight substitutions the script declares" in doc


def test_pin_without_an_explicit_date_refuses(scratch, tmp_path, capsys):
    """Red-team MF-6: `--date` has no default under `--pin`. The date is
    written into the document, into `handoff_entry` and into the pinned sha, so
    a UTC default would stamp a day the owner never said the moment the clock
    rolls over. `--show` may default it, because `--show` writes nothing."""
    ratified = tmp_path / "G3_RATIFIED.json"
    before = scratch.read_bytes()

    rc = PG.main(["--pin", "--owner-word", "ratify", "--doc", str(scratch),
                  "--ratified", str(ratified)])
    out = capsys.readouterr().out
    assert rc == 2
    assert "BLOCKED: --pin requires an explicit --date" in out
    assert not ratified.exists()
    assert scratch.read_bytes() == before

    # the flag is not merely unset-by-accident: argparse carries no default
    assert PG._parse_args(["--show"]).date == ""
    # ... and --show still works without one, writing nothing
    assert PG.main(["--show", "--doc", str(scratch)]) == 0
    assert "STATUS: RATIFIED" in capsys.readouterr().out
    assert scratch.read_bytes() == before


def test_pinned_scratch_copy_is_accepted_by_every_guard(scratch, tmp_path):
    ratified = tmp_path / "G3_RATIFIED.json"
    record = PG.pin(scratch, ratified, DATE, "ratify")

    assert record["owner_word"] == "ratify"
    assert record["handoff_entry"] == DATE
    assert set(record) >= {"doc_sha256", "params_sha256", "pinned_utc", "owner_word",
                           "handoff_entry"}
    written = json.loads(ratified.read_text())
    assert written["doc_sha256"] == BE.sha256_file(scratch)

    # guard 1: require_g3
    guard = BE.require_g3(scratch, ratified)
    assert guard["doc_sha256"] == written["doc_sha256"]
    # guard 2: load_g3_params (guard + the full parameter validation)
    params, guard2 = BE.load_g3_params(scratch, ratified)
    assert guard2["params_sha256"] == written["params_sha256"]
    assert params["params_version"] == BE.PARAMS_VERSION
    assert params["draft_status"].startswith(f"RATIFIED {DATE}")
    # guard 3: heads 2/3 read the same object through their own loader
    hparams, sha = HE.load_ratified_params(scratch, ratified)
    assert sha == written["doc_sha256"] and hparams == params

    # the pinned document still parses into the same parameters it did before:
    # `draft_status` is the one documentation-only key the pin is allowed to
    # change, and nothing else in the block moves.
    unpinned = BE.validate_params(BE.extract_params_block(REAL_DOC.read_text()))
    assert {k: v for k, v in params.items() if k != "draft_status"} == {
        k: v for k, v in unpinned.items() if k != "draft_status"
    }


def test_show_is_read_only(scratch, capsys):
    before = scratch.read_bytes()
    text = PG.show(scratch, DATE)
    assert scratch.read_bytes() == before, "--show must not touch the document"
    assert text.startswith("--- ")
    assert "RESIDUE THAT WOULD SURVIVE" not in text
    assert "+**STATUS: RATIFIED" in text
    assert "-**STATUS: RATIFICATION-READY" in text
    # through the CLI, with an explicit scratch path
    rc = PG.main(["--show", "--date", DATE, "--doc", str(scratch)])
    assert rc == 0
    assert scratch.read_bytes() == before
    assert "STATUS: RATIFIED" in capsys.readouterr().out


def test_pin_without_the_owner_word_refuses(scratch, tmp_path, capsys):
    ratified = tmp_path / "G3_RATIFIED.json"
    before = scratch.read_bytes()
    for word in ("", "yes", "Ratify", "ratify please"):
        with pytest.raises(PG.PinRefusal) as exc:
            PG.pin(scratch, ratified, DATE, word)
        assert "is not 'ratify'" in str(exc.value)
    assert not ratified.exists()
    assert scratch.read_bytes() == before

    rc = PG.main(["--pin", "--date", DATE, "--doc", str(scratch), "--ratified", str(ratified)])
    assert rc == 2
    assert "BLOCKED" in capsys.readouterr().out
    assert not ratified.exists()
    assert scratch.read_bytes() == before

    # no action flag at all: usage, exit 2, nothing written
    assert PG.main(["--doc", str(scratch), "--ratified", str(ratified)]) == 2
    assert not ratified.exists()


def test_a_bad_date_and_a_moved_document_both_refuse(scratch, tmp_path):
    ratified = tmp_path / "G3_RATIFIED.json"
    before = scratch.read_bytes()
    with pytest.raises(PG.PinRefusal) as exc:
        PG.pin(scratch, ratified, "September 30", "ratify")
    assert "not YYYY-MM-DD" in str(exc.value)

    moved = tmp_path / "moved.md"
    moved.write_text(scratch.read_text().replace(
        "RULED rule (dec.; owner 2026-09-11; ratification pending)", "SOMETHING ELSE", 1))
    with pytest.raises(PG.PinRefusal) as exc:
        PG.pin(moved, ratified, DATE, "ratify")
    assert "matched 12 times, expected 13" in str(exc.value)
    assert not ratified.exists()
    assert scratch.read_bytes() == before


def test_an_existing_ratification_is_not_overwritten(scratch, tmp_path):
    ratified = tmp_path / "G3_RATIFIED.json"
    ratified.write_text(json.dumps({"doc_sha256": "deadbeef"}) + "\n")
    before = scratch.read_bytes()
    with pytest.raises(PG.PinRefusal) as exc:
        PG.pin(scratch, ratified, DATE, "ratify")
    assert "already exists" in str(exc.value)
    assert json.loads(ratified.read_text())["doc_sha256"] == "deadbeef"
    assert scratch.read_bytes() == before


def test_the_real_ratification_is_intact_and_pins_the_ratified_text(prepin_text):
    """The pin itself (2026-11-05): the real ratification exists, carries the
    owner's word and date, pins the real document's sha, and the real document
    is EXACTLY the eight declared substitutions applied to the pre-pin text.
    Nothing in this suite may delete, edit or re-pin either file."""
    assert REAL_RATIFIED.exists(), NEVER_DELETE_THE_PIN
    record = json.loads(REAL_RATIFIED.read_text())
    assert record["doc_sha256"] == REAL_DOC_SHA256, NEVER_DELETE_THE_PIN
    assert BE.sha256_file(REAL_DOC) == record["doc_sha256"], NEVER_DELETE_THE_PIN
    assert record["params_sha256"] == REAL_PARAMS_SHA256, NEVER_DELETE_THE_PIN
    assert record["owner_word"] == "ratify", NEVER_DELETE_THE_PIN
    assert record["handoff_entry"] == "2026-11-05", NEVER_DELETE_THE_PIN
    assert PG.DOC_PATH == REAL_DOC and PG.RATIFIED_PATH == REAL_RATIFIED
    assert PG.residue(REAL_DOC.read_text()) == {}, NEVER_DELETE_THE_PIN
    pinned, _ = PG.pinned_text(prepin_text, record["handoff_entry"])
    assert pinned == REAL_DOC.read_text(), NEVER_DELETE_THE_PIN
