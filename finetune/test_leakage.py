"""
test_leakage.py — thin pytest/script wrapper around check_leakage.py, so the
leakage check is part of the standard local test run (`python3 test_leakage.py`
or `python3 -m pytest finetune/`) and not just a standalone script someone
has to remember to run separately.

Run: `python3 test_leakage.py`
"""

from __future__ import annotations

import check_leakage


def test_leakage_check_passes():
    exit_code = check_leakage.main()
    assert exit_code == 0, "check_leakage.py reported failures -- see stdout above"
    print("PASS: test_leakage_check_passes")


if __name__ == "__main__":
    test_leakage_check_passes()
    print("\nALL TESTS PASSED")
