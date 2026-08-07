"""Tests for exchange.py — bounded rate loading and rate validation.

The Norges Bank API is never called: every test either patches
``exchange._fetch_api`` or the urlopen underneath it.
"""

from __future__ import annotations

import io
import json
from datetime import date
from typing import Any

import pytest

import cache_db
import exchange
from cache_db import get_exchange_rates, save_exchange_rates
from exchange import _parse_sdmx_rates, get_rate, load_rates


def _sdmx(rates: dict[str, float]) -> dict[str, Any]:
    """Build an SDMX-JSON payload shaped like the Norges Bank EXR response."""
    dates = list(rates)
    return {
        "data": {
            "structure": {
                "dimensions": {"observation": [{"values": [{"id": d} for d in dates]}]}
            },
            "dataSets": [
                {
                    "series": {
                        "0:0:0:0": {
                            "observations": {
                                str(i): [rates[d]] for i, d in enumerate(dates)
                            }
                        }
                    }
                }
            ],
        }
    }


@pytest.fixture
def fake_api(monkeypatch):
    """Serve a canned SDMX payload in place of the live API.

    Patches urlopen rather than _fetch_api so the parse/validate path — the
    thing under test — still runs.
    """

    def install(rates: dict[str, float]) -> None:
        class _Resp(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self.close()
                return False

        def _urlopen(req, timeout=None):
            return _Resp(json.dumps(_sdmx(rates)).encode())

        monkeypatch.setattr(exchange.urllib.request, "urlopen", _urlopen)

    return install


@pytest.fixture
def no_api(monkeypatch):
    """Make every fetch return nothing, so only cached rates are in play."""
    monkeypatch.setattr(exchange, "_fetch_api", lambda start, end: {})


# ---------------------------------------------------------------------------
# DAL
# ---------------------------------------------------------------------------

def test_dal_round_trip():
    save_exchange_rates({"2026-01-05": 10.25, "2026-01-06": 10.5})
    assert get_exchange_rates("2026-01-01") == {
        "2026-01-05": 10.25,
        "2026-01-06": 10.5,
    }


def test_dal_save_empty_is_a_noop():
    save_exchange_rates({})
    assert get_exchange_rates("2000-01-01") == {}


def test_dal_save_upserts_existing_date():
    save_exchange_rates({"2026-01-05": 10.0})
    save_exchange_rates({"2026-01-05": 11.0})
    assert get_exchange_rates("2026-01-05") == {"2026-01-05": 11.0}


def test_dal_since_date_is_inclusive_and_excludes_older():
    save_exchange_rates(
        {"2025-12-20": 9.0, "2026-01-05": 10.0, "2026-01-10": 11.0}
    )
    assert get_exchange_rates("2026-01-05") == {"2026-01-05": 10.0, "2026-01-10": 11.0}


# ---------------------------------------------------------------------------
# Bounded read
# ---------------------------------------------------------------------------

def test_load_rates_stops_at_the_walkback_horizon(no_api):
    save_exchange_rates({"2025-06-01": 9.0, "2026-01-05": 10.0})
    rates = load_rates({date(2026, 1, 15)})
    assert "2025-06-01" not in rates, "read reached past the walkback horizon"
    assert "2026-01-05" in rates


def test_walkback_finds_a_rate_at_the_query_boundary(no_api):
    # 2026-01-05 is exactly _MAX_WALKBACK_DAYS before the requested date: the
    # oldest row the bounded read must still return.
    save_exchange_rates({"2026-01-05": 10.0})
    rates = load_rates({date(2026, 1, 15)})
    rate, _ = get_rate(rates, date(2026, 1, 15))
    assert rate == 10.0


def test_horizon_is_measured_from_the_earliest_requested_date(no_api):
    save_exchange_rates({"2026-01-05": 10.0, "2026-03-02": 11.0})
    rates = load_rates({date(2026, 1, 15), date(2026, 3, 2)})
    assert rates == {"2026-01-05": 10.0, "2026-03-02": 11.0}


def test_load_rates_without_dates_touches_nothing(no_api):
    assert load_rates(set()) == {}


# ---------------------------------------------------------------------------
# Rate validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad", [0.0, -10.0, float("nan"), float("inf"), float("-inf"), 1e9, 4.99, 20.01]
)
def test_parse_drops_implausible_rates(bad):
    assert _parse_sdmx_rates(_sdmx({"2026-01-05": bad})) == {}


@pytest.mark.parametrize("good", [5.0, 10.4321, 20.0])
def test_parse_keeps_plausible_rates(good):
    assert _parse_sdmx_rates(_sdmx({"2026-01-05": good})) == {"2026-01-05": good}


def test_bad_rate_is_not_saved_and_date_stays_missing(fake_api):
    fake_api({"2026-03-02": 0.0})
    rates = load_rates({date(2026, 3, 2)})
    assert "2026-03-02" not in rates
    assert get_exchange_rates("2000-01-01") == {}, "a bad rate reached the cache"


def test_a_bad_rate_does_not_discard_its_good_neighbours(fake_api):
    fake_api({"2026-03-02": 10.5, "2026-03-03": 0.0})
    load_rates({date(2026, 3, 2), date(2026, 3, 3)})
    assert get_exchange_rates("2000-01-01") == {"2026-03-02": 10.5}


def test_a_rejected_date_is_re_requested_next_run(fake_api):
    fake_api({"2026-03-02": 0.0})
    load_rates({date(2026, 3, 2)})
    fake_api({"2026-03-02": 10.5})
    rates = load_rates({date(2026, 3, 2)})
    assert rates["2026-03-02"] == 10.5


def test_exchange_holds_no_sql():
    """The DAL owns the SQL; exchange.py talks to it through cache_db."""
    src = exchange.__file__
    with open(src, encoding="utf-8") as fh:
        text = fh.read()
    assert "sqlite3" not in text
    assert "get_connection" not in text
    assert "SELECT" not in text
    assert cache_db.get_exchange_rates is exchange.cache_db.get_exchange_rates
