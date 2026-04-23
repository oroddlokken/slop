#!/usr/bin/env python3
"""Fetch Claude Code usage data via the Anthropic OAuth API, cached for 10 minutes.

Uses GET https://api.anthropic.com/api/oauth/usage with the user's OAuth token
sourced from macOS Keychain or ~/.claude/.credentials.json.

AUDIT: All calculations are documented in claude/CLAUDE.md.
When changing any calculation, caching, or data format here,
update CLAUDE.md to match.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cache_db import (
    clear_fetch_failures,
    read_usage_cache,
    record_fetch_failure,
    release_fetch_lock,
    try_acquire_fetch_lock,
    write_usage_cache,
)
from pricing import compute_costs

CACHE_MAX_AGE = 600  # 10 minutes

USAGE_API_URL = "https://api.anthropic.com/api/oauth/usage"
USAGE_API_TIMEOUT = 5  # seconds per attempt
USAGE_API_RETRIES = 2  # max retries on transient errors
USAGE_API_RETRY_DELAY = 1.0  # seconds between retries
CREDENTIALS_SERVICE = "Claude Code-credentials"

# HTTP status codes worth retrying
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


# ---------------------------------------------------------------------------
# OAuth token retrieval
# ---------------------------------------------------------------------------


def _read_token_from_keychain(service: str = CREDENTIALS_SERVICE) -> str | None:
    """Read OAuth token from macOS Keychain."""
    try:
        raw = subprocess.run(
            ["security", "find-generic-password", "-s", service, "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if raw.returncode != 0 or not raw.stdout.strip():
            return None
        return _parse_token(raw.stdout.strip())
    except (subprocess.TimeoutExpired, OSError):
        return None


def _list_keychain_candidates() -> list[str]:
    """List Claude Code credential service names from keychain, newest first."""
    try:
        raw = subprocess.run(
            ["security", "dump-keychain"],
            capture_output=True, timeout=10,
        )
        if raw.returncode != 0:
            return []
    except (subprocess.TimeoutExpired, OSError):
        return []

    # Decode with replacement to handle non-UTF8 output (macsetup-60yx)
    output = raw.stdout.decode("utf-8", errors="replace")

    import re
    services: list[tuple[str, str | None]] = []
    # Split on individual keychain item boundaries instead of keychain file
    # boundaries, so multiple entries within one keychain are found (macsetup-1ypj)
    items = re.split(r'(?=class:)', output)
    for item in items:
        svc_m = re.search(r'"svce"<blob>="([^"]+)"', item)
        if not svc_m:
            continue
        svc = svc_m.group(1)
        if not svc.startswith(CREDENTIALS_SERVICE) or svc == CREDENTIALS_SERVICE:
            continue
        # Extract modification date for sorting
        mdat_m = re.search(r'"mdat"<timedate>=(?:0x[0-9A-Fa-f]+\s+)?"([^"]+)"', item)
        mdat = mdat_m.group(1).replace("\\000", "").strip() if mdat_m else None
        services.append((svc, mdat))

    # Sort by modification date descending (newest first)
    services.sort(key=lambda x: x[1] or "", reverse=True)
    return [svc for svc, _ in services]


def _read_token_from_credentials_file() -> str | None:
    """Read OAuth token from ~/.claude/.credentials.json."""
    cred_file = Path.home() / ".claude" / ".credentials.json"
    try:
        return _parse_token(cred_file.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _parse_token(raw: str) -> str | None:
    """Extract claudeAiOauth.accessToken from JSON string."""
    try:
        data = json.loads(raw)
        return data.get("claudeAiOauth", {}).get("accessToken")
    except (json.JSONDecodeError, AttributeError):
        return None


def get_usage_token() -> str | None:
    """Get OAuth token: Keychain (primary + candidates) → credentials file."""
    if sys.platform == "darwin":
        token = _read_token_from_keychain()
        if token:
            return token
        for svc in _list_keychain_candidates():
            token = _read_token_from_keychain(svc)
            if token:
                return token
    return _read_token_from_credentials_file()


# ---------------------------------------------------------------------------
# Peak window
# ---------------------------------------------------------------------------


def compute_peak_info() -> dict[str, Any]:
    """Compute current peak/off-peak status and countdown to next flip.

    Peak hours: weekdays 13:00-19:00 UTC (1 PM-7 PM GMT).
    Weekends are always off-peak.
    """
    from datetime import timedelta

    now = datetime.now(tz=timezone.utc)
    h = now.hour
    wd = now.weekday()  # 0=Mon ... 6=Sun
    weekend = wd >= 5

    peak_start, peak_end = 13, 19
    is_peak = not weekend and peak_start <= h < peak_end

    if weekend:
        days_until_mon = (7 - wd) % 7 or 7  # Sat=2, Sun=1
        target = now.replace(hour=peak_start, minute=0, second=0, microsecond=0) + timedelta(days=days_until_mon)
    elif is_peak:
        target = now.replace(hour=peak_end, minute=0, second=0, microsecond=0)
    elif h >= peak_end:
        # After peak ends — next peak is tomorrow, unless tomorrow is a weekend
        days_ahead = 1
        next_wd = (wd + 1) % 7
        if next_wd >= 5:  # Saturday or Sunday
            days_ahead = 7 - wd  # skip to Monday
        target = now.replace(hour=peak_start, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
    else:
        target = now.replace(hour=peak_start, minute=0, second=0, microsecond=0)

    flip_seconds = max(0, int((target - now).total_seconds()))

    return {
        "peak_is_peak": is_peak,
        "peak_flip_seconds": flip_seconds,
    }


# ---------------------------------------------------------------------------
# API fetch
# ---------------------------------------------------------------------------


def fetch_usage_api(token: str) -> dict[str, Any]:
    """Fetch usage data from the Anthropic API.

    Returns dict with session_percent, week_percent, etc. mapped to our format.
    Raises on HTTP/network errors after exhausting retries for transient failures.
    """
    req = Request(
        USAGE_API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
        },
    )

    last_exc: Exception | None = None
    for attempt in range(1 + USAGE_API_RETRIES):
        try:
            resp = urlopen(req, timeout=USAGE_API_TIMEOUT)  # noqa: S310
            body = json.loads(resp.read().decode())
            break
        except HTTPError as e:
            if e.code not in _RETRYABLE_STATUS or attempt == USAGE_API_RETRIES:
                raise
            last_exc = e
            delay = USAGE_API_RETRY_DELAY
            # Respect Retry-After header (seconds only)
            retry_after = e.headers.get("Retry-After") if e.headers else None
            if retry_after:
                try:
                    delay = max(delay, min(float(retry_after), 5.0))
                except ValueError:
                    pass
            time.sleep(delay)
        except (URLError, OSError, TimeoutError) as e:
            if attempt == USAGE_API_RETRIES:
                raise
            last_exc = e
            time.sleep(USAGE_API_RETRY_DELAY)
    else:
        raise last_exc  # type: ignore[misc]

    data: dict[str, Any] = {}

    # five_hour → session
    five_hour = body.get("five_hour", {})
    if five_hour.get("utilization") is not None:
        data["session_percent"] = int(five_hour["utilization"])
    if five_hour.get("resets_at"):
        data["session_reset"] = five_hour["resets_at"]

    # seven_day → week
    seven_day = body.get("seven_day", {})
    if seven_day.get("utilization") is not None:
        data["week_percent"] = int(seven_day["utilization"])
    if seven_day.get("resets_at"):
        data["week_reset"] = seven_day["resets_at"]

    # seven_day_sonnet → sonnet
    sonnet = body.get("seven_day_sonnet", {})
    if sonnet and sonnet.get("utilization") is not None:
        data["sonnet_percent"] = int(sonnet["utilization"])
    if sonnet and sonnet.get("resets_at"):
        data["sonnet_reset"] = sonnet["resets_at"]

    # extra_usage
    extra = body.get("extra_usage", {})
    if extra.get("utilization") is not None:
        data["extra_percent"] = int(extra["utilization"])
    if extra.get("used_credits") is not None:
        # API returns cents; convert to dollars for our format
        data["extra_spent"] = extra["used_credits"] / 100
    if extra.get("monthly_limit") is not None:
        data["extra_limit"] = extra["monthly_limit"] / 100

    return data


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _enrich_and_emit(
    data: dict[str, Any],
    session_id: str | None,
    cwd: str | None,
    *,
    warn_on_error: bool = True,
) -> None:
    """Merge cost info and peak info into *data*, then print as JSON."""
    try:
        costs = compute_costs(
            session_id=session_id, cwd=cwd,
            session_reset_iso=data.get("session_reset"),
            week_reset_iso=data.get("week_reset"),
        )
        data.update(costs)
    except Exception as e:  # noqa: BLE001
        if warn_on_error:
            print(f"Warning: cost computation failed: {e}", file=sys.stderr)
    data.update(compute_peak_info())
    print(json.dumps(data, indent=2))


def _parse_cli_args() -> tuple[bool, int, str | None, str | None]:
    """Parse CLI arguments. Returns (force, wait_timeout, session_id, cwd)."""
    force = "--force" in sys.argv
    wait_timeout = 30
    if "--wait-timeout" in sys.argv:
        idx = sys.argv.index("--wait-timeout")
        if idx + 1 < len(sys.argv):
            try:
                wait_timeout = int(sys.argv[idx + 1])
            except ValueError:
                pass
    session_id: str | None = None
    if "--session" in sys.argv:
        idx = sys.argv.index("--session")
        if idx + 1 < len(sys.argv):
            session_id = sys.argv[idx + 1]
    cwd: str | None = None
    if "--cwd" in sys.argv:
        idx = sys.argv.index("--cwd")
        if idx + 1 < len(sys.argv):
            cwd = sys.argv[idx + 1]
    return force, wait_timeout, session_id, cwd


def _wait_for_leader(
    wait_timeout: int,
    session_id: str | None,
    cwd: str | None,
) -> None:
    """Poll for fresh cache while another process is fetching. Exits on result."""
    for _ in range(wait_timeout * 2):  # poll every 0.5s
        time.sleep(0.5)
        cached = read_usage_cache(CACHE_MAX_AGE)
        if cached:
            _enrich_and_emit(cached, session_id, cwd)
            sys.exit(0)
    # Leader failed — emit stale data if available (macsetup-348k)
    from cache_db import read_usage_stale
    stale = read_usage_stale()
    if stale:
        stale["_stale"] = True
        _enrich_and_emit(stale, session_id, cwd)
        sys.exit(0)
    print("Error: fetch timed out waiting for leader", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    """Fetch and print Claude usage data, using cache when fresh."""
    force, wait_timeout, session_id_arg, cwd_arg = _parse_cli_args()

    if not force:
        cached = read_usage_cache(CACHE_MAX_AGE)
        if cached:
            _enrich_and_emit(cached, session_id_arg, cwd_arg)
            return

    acquired_lock = force or try_acquire_fetch_lock()
    if not acquired_lock:
        _wait_for_leader(wait_timeout, session_id_arg, cwd_arg)
        return

    try:
        token = get_usage_token()
        if not token:
            record_fetch_failure()
            print("Error: no OAuth token found", file=sys.stderr)
            sys.exit(1)

        t_start = time.monotonic()
        data = fetch_usage_api(token)
        fetch_duration = round(time.monotonic() - t_start, 2)

        if not data or ("session_percent" not in data and "week_percent" not in data):
            record_fetch_failure()
            print("Error: API returned no usage data", file=sys.stderr)
            sys.exit(1)

        clear_fetch_failures()
        data["last_updated"] = datetime.now(tz=timezone.utc).astimezone().isoformat()
        data["_meta"] = {"fetch_duration_s": fetch_duration, "method": "api"}

        try:
            costs = compute_costs(
                session_id=session_id_arg, cwd=cwd_arg,
                session_reset_iso=data.get("session_reset"),
                week_reset_iso=data.get("week_reset"),
            )
            data.update(costs)
        except Exception as e:  # noqa: BLE001
            print(f"Warning: cost computation failed: {e}", file=sys.stderr)

        write_usage_cache(data)
        data.update(compute_peak_info())
        print(json.dumps(data, indent=2))

    except HTTPError as e:
        # Don't enter backoff for permanent auth errors — the token is bad,
        # retrying with the same token won't help, but a fresh token (after
        # re-login) should work immediately.
        if e.code in (401, 403):
            print(f"Error: API returned {e.code} (auth)", file=sys.stderr)
        else:
            record_fetch_failure()
            print(f"Error: API returned {e.code}", file=sys.stderr)
        sys.exit(1)
    except (URLError, OSError, json.JSONDecodeError) as e:
        record_fetch_failure()
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if acquired_lock and not force:
            release_fetch_lock()


if __name__ == "__main__":
    main()
