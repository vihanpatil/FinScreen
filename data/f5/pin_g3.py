#!/usr/bin/env python3
"""pin_g3.py -- the ONE procedure that turns the G3 pre-registration from
RATIFICATION-READY into RATIFIED, and writes `data/f5/G3_RATIFIED.json`.

Why this exists (red-team M9 -> NF-9, 2026-09-11). The pinned sha covers the
WHOLE document, so the text the owner reads and the text whose sha is pinned
must be the same text. Round 2 changed two lines by hand and the reviewer
measured what survived: 13 table headers still saying "ratification pending",
an "unratified" sentence in §0, "RATIFICATION-READY, not ratified" beside the
parameter block, the header paragraph's "ratified only when the owner says so",
and a blank signature line. `backtest_e2.require_g3` refuses any later repair --
editing the document after the pin is a NEW pre-registration -- so residue
cannot be fixed afterwards. This script applies the FULL substitution set in
one pass, shows the owner the exact diff first, and refuses to pin anything
that still reads as unratified.

Usage
-----
    python3 data/f5/pin_g3.py --show
        Print the full unified diff between the document as it stands and its
        pinned form. Reads only; writes nothing, anywhere.

    python3 data/f5/pin_g3.py --pin --owner-word ratify --date YYYY-MM-DD
        Apply the substitutions IN PLACE, then write G3_RATIFIED.json with the
        pinned sha256 of the document and of its parameter block. `--date` is
        REQUIRED here and has NO default: it is the day the owner replied
        "ratify", it is written into the document and into the ratification
        record, and a UTC default would silently roll over at midnight and stamp
        the wrong day on the one artifact that cannot be edited afterwards
        (red-team MF-6). `--show` may default it, because `--show` writes
        nothing.

THE SUBSTITUTION SET IS EXACTLY THESE EIGHT RULES AND NOTHING ELSE. The letters
are the SAME letters §0 of the pre-registration lists, and each rule's `id` is
named for its letter, so the document and this script can be read against each
other. Every rule declares how many matches it expects; a rule that matches a
different number of times REFUSES, because a document that moved under the pin
is not the document the owner read.

  (a) the header STATUS line
  (b) the parameter block's `draft_status`
  (c) every table header cell "RULED rule (dec.; owner 2026-09-11; ratification
      pending)"                                                       (13 cells)
  (d) the §0 sha-pinning row's status sentence
  (e) the "RATIFICATION-READY, not ratified" sentence beside the params block
  (f) the first signature line of §13
  (g) the second signature line of §13
  (h) the header paragraph's "ratified only when the owner says so"

`--pin` additionally refuses when: `--date` was not given; the owner word is not
exactly `ratify`; the date is not YYYY-MM-DD; `G3_RATIFIED.json` already exists
(re-pinning is a new ratification, not a re-run); the pinned text still matches
any of RESIDUE_PATTERNS; or the pinned text's parameter block no longer parses
and validates. Nothing is written until every one of those checks has passed, and
the written file is re-read and re-checked afterwards (restored on failure).

$0, no network, no model, no association of any kind.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import backtest_e2 as BE  # noqa: E402

DOC_PATH = ROOT / "data" / "f5" / "G3_PREREGISTRATION.md"
RATIFIED_PATH = ROOT / "data" / "f5" / "G3_RATIFIED.json"

OWNER_WORD = "ratify"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

#: Anything matching these AFTER the substitutions means the pin left residue.
RESIDUE_PATTERNS = (
    "ratification pending",
    "unratified",
    "RATIFICATION-READY",
    "not ratified",
    "______",
)


class PinRefusal(RuntimeError):
    """A pin precondition failed. Never caught-and-defaulted."""


def substitutions(date: str) -> list[dict]:
    """The eight rules, in application order -- lettered as §0 of the
    pre-registration letters them (a)-(h). `n` is the REQUIRED match count."""
    return [
        {
            "id": "a_header_status",
            "regex": r"^\*\*STATUS: RATIFICATION-READY.*\*\*$",
            "flags": re.M,
            "new": (
                f'**STATUS: RATIFIED {date} — owner\'s word "ratify" in chat; HANDOFF §3 entry '
                "of that date. sha256 pinned in G3_RATIFIED.json.**"
            ),
            "n": 1,
        },
        {
            "id": "b_draft_status",
            "regex": r'"draft_status": "[^"]*"',
            "flags": 0,
            "new": f"\"draft_status\": \"RATIFIED {date} -- owner's word 'ratify'; sha pinned\"",
            "n": 1,
        },
        {
            "id": "c_table_headers",
            "regex": re.escape("RULED rule (dec.; owner 2026-09-11; ratification pending)"),
            "flags": 0,
            "new": f"RATIFIED rule (dec.; owner 2026-09-11; ratified {date})",
            "n": 13,
        },
        {
            "id": "d_section0_sha_sentence",
            "regex": re.escape(
                "**none pinned while this document is unratified** — RATIFICATION-READY is not "
                'ratified, and the sha is written only when the owner replies "ratify" to §4 of '
                "the rulings file"
            ),
            "flags": 0,
            "new": (
                f"**pinned at ratification on {date}** — the owner replied \"ratify\" to §4 of "
                "the rulings file"
            ),
            "n": 1,
        },
        {
            "id": "e_params_block_sentence",
            "regex": re.escape("the document is RATIFICATION-READY, not ratified"),
            "flags": 0,
            "new": f"the document is RATIFIED {date}",
            "n": 1,
        },
        {
            "id": "f_signature_line_1",
            "regex": re.escape(
                "**Ratified by the owner on __________ (HANDOFF §3 entry: "
                "____________________).**"
            ),
            "flags": 0,
            "new": f"**Ratified by the owner on {date} (HANDOFF §3 entry: {date}).**",
            "n": 1,
        },
        {
            "id": "g_signature_line_2",
            "regex": re.escape("Signature: ______________________________"),
            "flags": 0,
            "new": f"Signature: the owner's word 'ratify' in chat (HANDOFF §3 {date})",
            "n": 1,
        },
        {
            "id": "h_header_paragraph_clause",
            # the clause is wrapped across two lines in the source
            "regex": r"ratified\s+only when the owner says so",
            "flags": 0,
            "new": f"ratified on {date}",
            "n": 1,
        },
    ]


def pinned_text(text: str, date: str) -> tuple[str, list[dict]]:
    """Apply the substitution set. Returns (new text, applied-rule report).

    A rule whose match count differs from its declared `n` REFUSES: it means the
    document changed shape since this procedure was written, and a pin that
    silently skips a rule is exactly the residue NF-9 found."""
    if not DATE_RE.match(date or ""):
        raise PinRefusal(f"BLOCKED: --date {date!r} is not YYYY-MM-DD.")
    report = []
    for rule in substitutions(date):
        pattern = re.compile(rule["regex"], rule["flags"])
        found = len(pattern.findall(text))
        if found != rule["n"]:
            raise PinRefusal(
                f"BLOCKED: substitution {rule['id']!r} matched {found} times, expected "
                f"{rule['n']}. The pre-registration is not the document this pinning procedure "
                "was written against; fix the procedure (and re-show the diff) rather than "
                "pinning a partial edit."
            )
        text = pattern.sub(lambda _m, r=rule: r["new"], text)
        report.append({"id": rule["id"], "matches": found})
    return text, report


def residue(text: str) -> dict[str, list[int]]:
    """{pattern: 1-based line numbers} for every residue pattern still present."""
    out: dict[str, list[int]] = {}
    lines = text.splitlines()
    for pat in RESIDUE_PATTERNS:
        hits = [i + 1 for i, line in enumerate(lines) if pat in line]
        if hits:
            out[pat] = hits
    return out


def unified_diff(before: str, after: str, name: str) -> str:
    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile=f"{name} (as it stands: RATIFICATION-READY)",
            tofile=f"{name} (pinned form)",
            n=1,
        )
    )


def show(doc_path: Path, date: str) -> str:
    """The full unified diff. READ-ONLY: this function writes nothing."""
    doc_path = Path(doc_path)
    before = doc_path.read_text()
    after, _report = pinned_text(before, date)
    left = residue(after)
    text = unified_diff(before, after, doc_path.name)
    if left:
        text += "\nRESIDUE THAT WOULD SURVIVE THIS PIN (a --pin would refuse):\n"
        for pat, lineno in left.items():
            text += f"  {pat!r} at lines {lineno}\n"
    return text


def pin(doc_path: Path = DOC_PATH, ratified_path: Path = RATIFIED_PATH,
        date: str = "", owner_word: str = "") -> dict:
    """Write the pinned document IN PLACE and its `G3_RATIFIED.json`.

    Every precondition is checked BEFORE the document is touched; the written
    file is then re-read and re-checked, and restored if anything is wrong."""
    if owner_word != OWNER_WORD:
        raise PinRefusal(
            f"BLOCKED: --owner-word {owner_word!r} is not {OWNER_WORD!r}. The pin is the owner's "
            "word, not a flag anyone else may supply."
        )
    doc_path, ratified_path = Path(doc_path), Path(ratified_path)
    if ratified_path.exists():
        raise PinRefusal(
            f"BLOCKED: {ratified_path} already exists. Re-pinning is a NEW pre-registration, not "
            "a re-run; move the existing ratification aside deliberately if that is what is meant."
        )
    before = doc_path.read_text()
    after, report = pinned_text(before, date)
    left = residue(after)
    if left:
        raise PinRefusal(
            "BLOCKED: the pinned text still reads as unratified: "
            + "; ".join(f"{pat!r} at lines {lines}" for pat, lines in left.items())
            + ". Nothing was written."
        )
    params = BE.validate_params(BE.extract_params_block(after))

    doc_path.write_text(after)
    try:
        written = doc_path.read_text()
        if written != after:
            raise PinRefusal("BLOCKED: the document on disk is not the text that was pinned.")
        still = residue(written)
        if still:
            raise PinRefusal(f"BLOCKED: residue survived the write: {still}.")
        BE.validate_params(BE.extract_params_block(written))
    except Exception:
        doc_path.write_text(before)
        raise

    record = {
        "doc_sha256": BE.sha256_file(doc_path),
        "params_sha256": BE.sha256_obj(params),
        "pinned_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "owner_word": OWNER_WORD,
        "handoff_entry": date,
    }
    ratified_path.write_text(json.dumps(record, indent=2) + "\n")
    record["substitutions"] = report
    return record


def _parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Show or apply the G3 ratification pin (data/f5/G3_PREREGISTRATION.md)."
    )
    p.add_argument("--show", action="store_true",
                   help="print the full unified diff of the pinned form; writes nothing")
    p.add_argument("--pin", action="store_true",
                   help="apply the substitutions in place and write G3_RATIFIED.json")
    p.add_argument("--owner-word", default="",
                   help=f"must be exactly {OWNER_WORD!r}; required with --pin")
    p.add_argument("--date", default="",
                   help="ratification date, YYYY-MM-DD (the HANDOFF §3 entry's date). "
                        "REQUIRED with --pin; --show defaults it to today (UTC)")
    p.add_argument("--doc", type=Path, default=DOC_PATH)
    p.add_argument("--ratified", type=Path, default=RATIFIED_PATH)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    if not args.show and not args.pin:
        print(__doc__.split("Usage\n-----\n")[1].split("THE SUBSTITUTION SET")[0].rstrip())
        print("Pass --show (read-only) or --pin --owner-word ratify --date YYYY-MM-DD "
          "(--date is required with --pin).")
        return 2
    try:
        if args.pin and not args.date:
            # Red-team MF-6: no UTC default for the pin. The date goes into the
            # document, into `handoff_entry` and into the sha; a default that
            # rolls at UTC midnight would stamp a day the owner never said.
            raise PinRefusal(
                "BLOCKED: --pin requires an explicit --date YYYY-MM-DD -- the day the owner "
                "replied 'ratify'. There is no default: the date is written into the pinned "
                "document and into G3_RATIFIED.json, and a UTC default rolls over at midnight. "
                "Nothing was written."
            )
        if args.show:
            print(show(args.doc, args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")))
        if args.pin:
            record = pin(args.doc, args.ratified, args.date, args.owner_word)
            print(f"pinned {args.doc}")
            print(f"wrote  {args.ratified}")
            print(json.dumps(record, indent=2))
    except PinRefusal as exc:
        print(str(exc))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
