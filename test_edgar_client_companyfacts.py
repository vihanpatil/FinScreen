"""
test_edgar_client_companyfacts.py -- tests for EdgarClient.get_companyfacts(),
the Phase C XBRL companyfacts extension to edgar_client.py.

HARD CONSTRAINT: no real network calls. requests.get is monkeypatched to a
fake that records what it was called with and returns a canned response --
this exercises the real caching / rate-limiter / User-Agent code paths in
EdgarClient without touching data.sec.gov.

Run with: python3 -m pytest test_edgar_client_companyfacts.py -v
"""
from __future__ import annotations

import json
import time

import pytest

import edgar_client as ec


MOCK_COMPANYFACTS = {
    "cik": 320193,
    "entityName": "Apple Inc.",
    "facts": {
        "us-gaap": {
            "NetIncomeLoss": {
                "label": "Net Income (Loss)",
                "description": "The portion of profit or loss...",
                "units": {
                    "USD": [
                        {
                            "start": "2024-01-01", "end": "2024-03-31",
                            "val": 23636000000, "accn": "0000320193-24-000050",
                            "fy": 2024, "fp": "Q2", "form": "10-Q",
                            "filed": "2024-05-02", "frame": "CY2024Q1",
                        },
                        {
                            "start": "2023-10-01", "end": "2023-12-31",
                            "val": 33916000000, "accn": "0000320193-24-000006",
                            "fy": 2024, "fp": "Q1", "form": "10-Q",
                            "filed": "2024-02-01",
                        },
                    ]
                },
            },
            "Assets": {
                "label": "Assets",
                "units": {
                    "USD": [
                        {
                            "end": "2024-03-31", "val": 337411000000,
                            "accn": "0000320193-24-000050", "fy": 2024,
                            "fp": "Q2", "form": "10-Q", "filed": "2024-05-02",
                        }
                    ]
                },
            },
        },
        "dei": {
            "EntityCommonStockSharesOutstanding": {
                "units": {
                    "shares": [
                        {
                            "end": "2024-04-19", "val": 15334082000,
                            "accn": "0000320193-24-000050", "fy": 2024,
                            "fp": "Q2", "form": "10-Q", "filed": "2024-05-02",
                        }
                    ]
                }
            }
        },
    },
}


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status_code
        self.headers = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _make_client(tmp_path, monkeypatch, calls):
    """Build a real EdgarClient pointed at an isolated tmp cache dir, with
    requests.get monkeypatched to record calls and return MOCK_COMPANYFACTS.
    """

    def fake_get(url, headers=None, params=None, timeout=None):
        calls.append({"url": url, "headers": headers})
        return _FakeResponse(json.dumps(MOCK_COMPANYFACTS))

    monkeypatch.setattr(ec.requests, "get", fake_get)
    client = ec.EdgarClient(cache_dir=tmp_path, verbose=False)
    return client


# ---------------------------------------------------------------------
# Host handling -- must hit data.sec.gov, never www.sec.gov, with the
# correct zero-padded-10-digit CIK.
# ---------------------------------------------------------------------


def test_companyfacts_url_is_data_sec_gov_host(tmp_path, monkeypatch):
    calls = []
    client = _make_client(tmp_path, monkeypatch, calls)

    client.get_companyfacts(320193)

    assert len(calls) == 1
    url = calls[0]["url"]
    assert url.startswith("https://data.sec.gov/"), (
        f"companyfacts must be fetched from data.sec.gov, not www.sec.gov: {url}"
    )
    assert "www.sec.gov" not in url
    assert url == "https://data.sec.gov/api/xbrl/companyfacts/CIK0000320193.json"


def test_companyfacts_sends_required_user_agent_header(tmp_path, monkeypatch):
    calls = []
    client = _make_client(tmp_path, monkeypatch, calls)
    client.get_companyfacts(320193)

    sent_headers = calls[0]["headers"]
    assert "User-Agent" in sent_headers
    assert "@" in sent_headers["User-Agent"]  # contact email present, per SEC policy


# ---------------------------------------------------------------------
# Cache hit / miss behavior -- idempotent by default.
# ---------------------------------------------------------------------


def test_companyfacts_cache_miss_then_hit_makes_one_network_call(tmp_path, monkeypatch):
    calls = []
    client = _make_client(tmp_path, monkeypatch, calls)

    first = client.get_companyfacts(320193)
    assert len(calls) == 1  # cache miss -> one network GET
    assert first["entityName"] == "Apple Inc."

    second = client.get_companyfacts(320193)
    assert len(calls) == 1  # cache hit -> no new network GET
    assert second == first

    cache_path = tmp_path / "companyfacts" / "CIK0000320193.json"
    assert cache_path.exists()


def test_companyfacts_force_refresh_bypasses_cache(tmp_path, monkeypatch):
    calls = []
    client = _make_client(tmp_path, monkeypatch, calls)

    client.get_companyfacts(320193)
    assert len(calls) == 1

    client.get_companyfacts(320193, force=True)
    assert len(calls) == 2  # force=True re-fetches even though cache is fresh


def test_companyfacts_stale_cache_is_refetched(tmp_path, monkeypatch):
    calls = []
    client = _make_client(tmp_path, monkeypatch, calls)

    client.get_companyfacts(320193)
    assert len(calls) == 1

    cache_path = tmp_path / "companyfacts" / "CIK0000320193.json"
    # Back-date the mtime past the 24h staleness window.
    old_time = time.time() - (ec.DEFAULT_MAX_AGE_HOURS + 1) * 3600
    import os
    os.utime(cache_path, (old_time, old_time))

    client.get_companyfacts(320193)
    assert len(calls) == 2  # stale cache -> re-fetched


def test_companyfacts_different_ciks_do_not_collide_in_cache(tmp_path, monkeypatch):
    calls = []
    client = _make_client(tmp_path, monkeypatch, calls)

    client.get_companyfacts(320193)
    client.get_companyfacts(789019)
    assert len(calls) == 2

    assert (tmp_path / "companyfacts" / "CIK0000320193.json").exists()
    assert (tmp_path / "companyfacts" / "CIK0000789019.json").exists()


# ---------------------------------------------------------------------
# Response shape -- one mocked response, structurally realistic.
# ---------------------------------------------------------------------


def test_companyfacts_response_shape_has_facts_by_taxonomy(tmp_path, monkeypatch):
    calls = []
    client = _make_client(tmp_path, monkeypatch, calls)
    data = client.get_companyfacts(320193)

    assert "facts" in data
    assert "us-gaap" in data["facts"]
    assert "dei" in data["facts"]
    assert "NetIncomeLoss" in data["facts"]["us-gaap"]
    units = data["facts"]["us-gaap"]["NetIncomeLoss"]["units"]
    assert "USD" in units
    assert units["USD"][0]["filed"] == "2024-05-02"
    assert units["USD"][0]["accn"] == "0000320193-24-000050"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
