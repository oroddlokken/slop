"""USD/NOK exchange rate lookups using Norges Bank daily spot rates.

Fetches from the Norges Bank SDMX-JSON API, caches in SQLite, and provides
rate lookups with automatic fallback for weekends and holidays.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

OSLO_TZ = ZoneInfo("Europe/Oslo")
_MAX_WALKBACK_DAYS = 10

_API_BASE = (
    "https://data.norges-bank.no/api/data/EXR/B.USD.NOK.SP"
    "?format=sdmx-json&locale=no"
)


def _parse_sdmx_rates(data: dict[str, Any]) -> dict[str, float]:
    """Parse SDMX-JSON response into {date_str: rate} dict."""
    rates: dict[str, float] = {}
    try:
        structure = data["data"]["structure"]
        time_periods = structure["dimensions"]["observation"][0]["values"]
        series = data["data"]["dataSets"][0]["series"]
        # Single series key "0:0:0:0" for USD/NOK spot
        obs = next(iter(series.values()))["observations"]
        for idx_str, values in obs.items():
            idx = int(idx_str)
            if idx < len(time_periods):
                date_str = time_periods[idx]["id"]
                rates[date_str] = float(values[0])
    except (KeyError, IndexError, StopIteration, ValueError, TypeError):
        pass
    return rates


def _fetch_api(start: date, end: date) -> dict[str, float]:
    """Fetch rates from Norges Bank API for a date range."""
    url = f"{_API_BASE}&startPeriod={start}&endPeriod={end}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return _parse_sdmx_rates(data)
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError):
        return {}


def _load_cached_rates() -> dict[str, float]:
    """Load all cached exchange rates from SQLite."""
    from cache_db import get_connection
    conn = get_connection()
    rows = conn.execute("SELECT date, rate FROM exchange_rates").fetchall()
    return {r[0]: r[1] for r in rows}


def _save_rates(rates: dict[str, float]) -> None:
    """Upsert exchange rates into SQLite cache."""
    if not rates:
        return
    from cache_db import get_connection
    conn = get_connection()
    conn.executemany(
        "INSERT OR REPLACE INTO exchange_rates (date, rate) VALUES (?, ?)",
        rates.items(),
    )
    conn.commit()


def to_oslo_date(ts: datetime) -> date:
    """Convert a timestamp to its Oslo-local date (canonical FX date)."""
    return ts.astimezone(OSLO_TZ).date()


def _find_missing_range(
    needed: set[date], cached: dict[str, float]
) -> tuple[date, date] | None:
    """Find the contiguous range of dates not yet cached."""
    missing = {d for d in needed if d.isoformat() not in cached}
    # Also include walkback dates that might be needed
    for d in list(missing):
        for i in range(1, _MAX_WALKBACK_DAYS + 1):
            wb = d - timedelta(days=i)
            if wb.isoformat() not in cached:
                missing.add(wb)
    if not missing:
        return None
    return min(missing), max(missing)


def load_rates(dates: set[date]) -> dict[str, float]:
    """Load exchange rates for a set of dates, fetching missing ones from API.

    Returns a dict of {date_str: rate} covering all cached rates.
    Dates on weekends/holidays won't have entries — use get_rate() for fallback.
    """
    if not dates:
        return {}
    cached = _load_cached_rates()
    missing_range = _find_missing_range(dates, cached)
    if missing_range:
        start, end = missing_range
        # Extend range slightly to cover walkback needs
        start = start - timedelta(days=_MAX_WALKBACK_DAYS)
        fetched = _fetch_api(start, end)
        if fetched:
            _save_rates(fetched)
            cached.update(fetched)
    return cached


def get_rate(rates: dict[str, float], d: date, _max_date: str | None = None) -> tuple[float | None, bool]:
    """Look up the rate for a date, walking back for weekends/holidays.

    Returns (rate, estimated) where estimated is True only when the rate
    is at the trailing edge of our data — i.e., we walked back and there
    is no later rate in the dataset. Gaps between two known rates (e.g.,
    weekends) are NOT estimated since the prior business day rate is the
    definitive rate for those dates.

    Returns (None, False) if no rate found within the walkback window.
    """
    for i in range(_MAX_WALKBACK_DAYS + 1):
        key = (d - timedelta(days=i)).isoformat()
        if key in rates:
            if i == 0:
                return rates[key], False
            # Walked back: only mark estimated if at the trailing edge
            # (no later rate exists), meaning the true rate is unknown.
            # Gaps between two known rates (weekends) use the prior
            # business day rate definitively.
            latest = _max_date if _max_date is not None else max(rates)
            return rates[key], d.isoformat() >= latest
    return None, False
