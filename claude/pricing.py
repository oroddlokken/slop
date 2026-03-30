"""Shared Claude model pricing data, cost calculation, and cost aggregation.

Single source of truth for pricing tables, model aliases, cost formulas,
and cost aggregation. get_claude_usage.py, statusline-command.py, and
ccreport.py all import from this module.

AUDIT: All calculations are documented in claude/CLAUDE.md.
When changing any pricing, tiering, or cost logic here, update CLAUDE.md to match.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# Source: https://github.com/BerriAI/litellm model_prices_and_context_window.json
LAST_CHECKED = "2026-02-22"

PRICING_HISTORY: list[dict[str, Any]] = [
    {
        "effective": "2025-01-01",
        "models": {
            "claude-opus-4-5-20251101": {
                "input": 5e-06, "output": 25e-06,
                "cache_create": 6.25e-06, "cache_read": 0.5e-06,
            },
            "claude-sonnet-4-20250514": {
                "input": 3e-06, "output": 15e-06,
                "cache_create": 3.75e-06, "cache_read": 0.3e-06,
                "input_200k": 6e-06, "output_200k": 22.5e-06,
                "cache_create_200k": 7.5e-06, "cache_read_200k": 0.6e-06,
            },
            "claude-haiku-4-5-20251001": {
                "input": 1e-06, "output": 5e-06,
                "cache_create": 1.25e-06, "cache_read": 0.1e-06,
            },
            "claude-sonnet-4-5-20250929": {
                "input": 3e-06, "output": 15e-06,
                "cache_create": 3.75e-06, "cache_read": 0.3e-06,
                "input_200k": 6e-06, "output_200k": 22.5e-06,
                "cache_create_200k": 7.5e-06, "cache_read_200k": 0.6e-06,
            },
        },
    },
    {
        "effective": "2026-02-05",
        "models": {
            "claude-opus-4-6": {
                "input": 5e-06, "output": 25e-06,
                "cache_create": 6.25e-06, "cache_read": 0.5e-06,
                "input_200k": 10e-06, "output_200k": 37.5e-06,
                "cache_create_200k": 12.5e-06, "cache_read_200k": 1e-06,
            },
        },
    },
    {
        "effective": "2026-02-17",
        "models": {
            "claude-sonnet-4-6": {
                "input": 3e-06, "output": 15e-06,
                "cache_create": 3.75e-06, "cache_read": 0.3e-06,
                "input_200k": 6e-06, "output_200k": 22.5e-06,
                "cache_create_200k": 7.5e-06, "cache_read_200k": 0.6e-06,
            },
        },
    },
    {
        # 2026-03-13 18:00 UTC (19:00 Oslo CET): Opus 4.6 and Sonnet 4.6
        # switched to flat pricing — no 200k tier premium.
        "effective": "2026-03-13T18",
        "models": {
            "claude-opus-4-6": {
                "input": 5e-06, "output": 25e-06,
                "cache_create": 6.25e-06, "cache_read": 0.5e-06,
            },
            "claude-sonnet-4-6": {
                "input": 3e-06, "output": 15e-06,
                "cache_create": 3.75e-06, "cache_read": 0.3e-06,
            },
        },
    },
]

MODEL_ALIASES: dict[str, str] = {
    "claude-opus-4-5": "claude-opus-4-5-20251101",
    "claude-sonnet-4": "claude-sonnet-4-20250514",
    "claude-sonnet-4-5": "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5": "claude-haiku-4-5-20251001",
}

TIER_THRESHOLD = 200_000


def _parse_effective(date_str: str) -> datetime:
    """Parse an effective date string to a timezone-aware datetime.

    Accepts 'YYYY-MM-DD' (midnight UTC) or 'YYYY-MM-DDTHH' (hour-level UTC).
    """
    if "T" in date_str:
        return datetime.strptime(date_str, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def find_pricing(model: str, ts: datetime | None = None) -> dict[str, float] | None:
    """Find pricing for a model at a given timestamp.

    Walks PRICING_HISTORY in reverse chronological order, returning the first
    match for a period whose effective date is <= *ts*.
    """
    resolved = MODEL_ALIASES.get(model, model)

    for period in reversed(PRICING_HISTORY):
        effective = _parse_effective(period["effective"])
        if ts is not None and effective > ts:
            continue
        models = period["models"]
        if resolved in models:
            return models[resolved]
        for key, prices in models.items():
            if key in resolved or resolved in key:
                return prices
    return None


def tiered_cost(count: int, base_rate: float, tiered_rate: float | None) -> float:
    """Calculate cost for a single token type with per-type 200K tiering."""
    if count > TIER_THRESHOLD and tiered_rate is not None:
        return TIER_THRESHOLD * base_rate + (count - TIER_THRESHOLD) * tiered_rate
    return count * base_rate


def calc_cost(
    input_tokens: int,
    output_tokens: int,
    cache_create_tokens: int,
    cache_read_tokens: int,
    model: str,
    ts: datetime | None = None,
) -> float:
    """Calculate total cost for a set of token counts using model-specific pricing.

    The 200K tier is applied per token type independently: each type's count
    is checked against the threshold separately.
    """
    prices = find_pricing(model, ts)
    if not prices:
        return 0.0
    return (
        tiered_cost(input_tokens, prices.get("input", 0.0), prices.get("input_200k"))
        + tiered_cost(output_tokens, prices.get("output", 0.0), prices.get("output_200k"))
        + tiered_cost(cache_create_tokens, prices.get("cache_create", 0.0), prices.get("cache_create_200k"))
        + tiered_cost(cache_read_tokens, prices.get("cache_read", 0.0), prices.get("cache_read_200k"))
    )


# ---------------------------------------------------------------------------
# Cost aggregation — shared JSONL parsing and windowed cost computation
# ---------------------------------------------------------------------------

CLAUDE_DIR = Path.home() / ".claude"
SESSION_WINDOW_HOURS = 5


def _get_projects_dirs() -> list[Path]:
    """Return existing Claude project directories."""
    dirs: list[Path] = []
    for d in [CLAUDE_DIR / "projects", Path.home() / ".config" / "claude" / "projects"]:
        if d.is_dir():
            dirs.append(d)
    return dirs


def _find_session_files(
    session_id: str,
    cwd: str,
    projects_dirs: list[Path] | None = None,
) -> set[str]:
    """Find JSONL files belonging to a session."""
    if projects_dirs is None:
        projects_dirs = _get_projects_dirs()
    project_key = cwd.replace("/", "-")
    files: set[str] = set()
    for d in projects_dirs:
        base = d / project_key
        main = base / f"{session_id}.jsonl"
        if main.exists():
            files.add(str(main))
        sub = base / session_id
        if sub.is_dir():
            for f in sub.rglob("*.jsonl"):
                files.add(str(f))
    return files


def _iter_jsonl_costs(
    path: str | Path,
    seen_keys: set[str],
) -> Iterator[tuple[float, datetime, str | None]]:
    """Yield (cost, timestamp, dedup_key) for each unique assistant record.

    Deduplicates via *seen_keys* (modified in-place).  Records missing either
    message_id or requestId are never considered duplicates.
    """
    try:
        with open(path) as f:
            for line in f:
                if '"assistant"' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("type") != "assistant":
                    continue
                msg = rec.get("message")
                if not msg or not isinstance(msg, dict):
                    continue
                usage = msg.get("usage")
                if not usage or not isinstance(usage, dict):
                    continue

                message_id = msg.get("id", "")
                request_id = rec.get("requestId", "")
                dk: str | None = None
                if message_id and request_id:
                    dk = f"{message_id}:{request_id}"
                    if dk in seen_keys:
                        continue
                    seen_keys.add(dk)

                ts_str = rec.get("timestamp", "")
                try:
                    ts = datetime.fromisoformat(ts_str)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    continue

                cost = calc_cost(
                    usage.get("input_tokens", 0),
                    usage.get("output_tokens", 0),
                    usage.get("cache_creation_input_tokens", 0),
                    usage.get("cache_read_input_tokens", 0),
                    msg.get("model", ""),
                    ts,
                )
                yield cost, ts, dk
    except (OSError, UnicodeDecodeError):
        pass


def compute_session_cost(session_id: str, cwd: str) -> float:
    """Compute total cost for a single session from its JSONL files.

    Uses a size-based cache in SQLite to avoid re-parsing unchanged files.
    """
    from cache_db import read_session_cost, write_session_cost

    if not session_id or not cwd:
        return 0.0

    files = _find_session_files(session_id, cwd)
    if not files:
        return 0.0

    total_size = sum(Path(f).stat().st_size for f in files)
    cached = read_session_cost(session_id)
    if cached is not None and cached[0] == total_size:
        return cached[1]

    seen_keys: set[str] = set()
    total_cost = 0.0
    for path in files:
        for cost, _ts, _dk in _iter_jsonl_costs(path, seen_keys):
            total_cost += cost

    write_session_cost(session_id, total_size, total_cost)
    return total_cost


def compute_project_rolling_costs(cwd: str) -> dict[str, float]:
    """Compute rolling cost totals for a single project directory.

    Lightweight scan of only the project's JSONL files — suitable for
    per-render use in the statusline without touching the shared cache.
    """
    if not cwd:
        return {}

    project_key = cwd.replace("/", "-")
    projects_dirs = _get_projects_dirs()

    now_local = datetime.now(tz=timezone.utc).astimezone()
    six_hour_start = now_local - timedelta(hours=6)
    twelve_hour_start = now_local - timedelta(hours=12)
    twenty_four_hour_start = now_local - timedelta(hours=24)
    seven_day_start = now_local - timedelta(days=7)
    thirty_day_start = now_local - timedelta(days=30)

    h6 = h12 = h24 = sd = td = at = 0.0
    seen_keys: set[str] = set()

    for d in projects_dirs:
        proj_dir = d / project_key
        if not proj_dir.is_dir():
            continue
        for jsonl_path in proj_dir.rglob("*.jsonl"):
            for cost, ts, _dk in _iter_jsonl_costs(jsonl_path, seen_keys):
                at += cost
                if ts >= thirty_day_start:
                    td += cost
                if ts >= seven_day_start:
                    sd += cost
                if ts >= twenty_four_hour_start:
                    h24 += cost
                if ts >= twelve_hour_start:
                    h12 += cost
                if ts >= six_hour_start:
                    h6 += cost

    return {
        "six_hour_project_cost": round(h6, 4),
        "twelve_hour_project_cost": round(h12, 4),
        "twenty_four_hour_project_cost": round(h24, 4),
        "seven_day_project_cost": round(sd, 4),
        "thirty_day_project_cost": round(td, 4),
        "all_time_project_cost": round(at, 4),
    }


def _parse_window_starts(
    session_reset_iso: str | None,
    week_reset_iso: str | None,
) -> tuple[datetime | None, datetime]:
    """Derive rate-limit window start times from reset ISO strings.

    Returns (session_window_start, week_window_start).
    session_window_start is None if the reset time is unavailable.
    week_window_start falls back to Monday 00:00 local time.
    """
    now = datetime.now(tz=timezone.utc).astimezone()

    session_window_start: datetime | None = None
    if session_reset_iso:
        try:
            sr = datetime.fromisoformat(session_reset_iso)
            if sr <= now:
                session_window_start = sr
            else:
                session_window_start = sr - timedelta(hours=SESSION_WINDOW_HOURS)
        except (ValueError, TypeError):
            pass

    week_window_start: datetime
    if week_reset_iso:
        try:
            wr = datetime.fromisoformat(week_reset_iso)
            if wr <= now:
                week_window_start = wr
            else:
                week_window_start = wr - timedelta(days=7)
        except (ValueError, TypeError):
            week_window_start = (now - timedelta(days=now.weekday())).replace(
                hour=0, minute=0, second=0, microsecond=0,
            )
    else:
        week_window_start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )

    return session_window_start, week_window_start


def _rec_cost(rec: dict) -> float:
    """Compute cost for a ccreport record dict, recomputing from tokens if needed."""
    cost = rec.get("cost")
    if cost is not None and cost != 0:
        return cost
    t = rec.get("t")
    if not t or len(t) < 4:
        return 0.0
    ts_epoch = rec.get("ts", 0)
    ts_dt = None
    if ts_epoch:
        try:
            ts_dt = datetime.fromtimestamp(ts_epoch, tz=timezone.utc)
        except (ValueError, OSError):
            pass
    return calc_cost(t[0], t[1], t[2], t[3], rec.get("model", ""), ts_dt)


def compute_costs(
    session_id: str | None = None,
    cwd: str | None = None,
    session_reset_iso: str | None = None,
    week_reset_iso: str | None = None,
) -> dict[str, float]:
    """Compute per-chat, session-window, week-window, and rolling costs.

    Uses ccreport_records cache when available (fast path, ~0.7s) with
    JSONL fallback for uncached files. Falls back to full JSONL scan
    if ccreport cache is empty.

    Cost buckets:
      session_cost          – total cost for the target chat (all time)
      session_window_cost   – cost across ALL chats within the current
                              rate-limit session window (~5 h)
      week_cost             – cost across ALL chats within the current
                              rate-limit week window
      month_cost            – cost since first of current calendar month
      six_hour_cost         – rolling 6-hour cost
      twelve_hour_cost      – rolling 12-hour cost
      twenty_four_hour_cost – rolling 24-hour cost
      seven_day_cost        – rolling 7-day cost
      thirty_day_cost       – rolling 30-day cost
      all_time_cost         – all records, no time filter

    session_cost, week_cost, and month_cost use per-file caching (mtime/size).
    session_window_cost and rolling costs are computed fresh.
    """
    from cache_db import (
        bulk_load_ccreport_cache,
        bulk_save_file_costs,
        load_cost_cache,
    )

    projects_dirs = _get_projects_dirs()

    session_window_start, week_window_start = _parse_window_starts(
        session_reset_iso, week_reset_iso,
    )
    week_key = week_window_start.strftime("%Y-%m-%dT%H")

    now_local = datetime.now(tz=timezone.utc).astimezone()
    month_window_start = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_key = month_window_start.strftime("%Y-%m")

    six_hour_start = now_local - timedelta(hours=6)
    twelve_hour_start = now_local - timedelta(hours=12)
    twenty_four_hour_start = now_local - timedelta(hours=24)
    seven_day_start = now_local - timedelta(days=7)
    thirty_day_start = now_local - timedelta(days=30)

    file_cache = load_cost_cache(week_key, month_key)

    session_files: set[str] = set()
    if session_id and cwd:
        session_files = _find_session_files(session_id, cwd, projects_dirs)

    # Per-project prefixes for identifying files belonging to current cwd
    project_prefixes: list[str] = []
    project_name = ""
    if cwd:
        project_key = cwd.replace("/", "-")
        project_prefixes = [str(d / project_key) for d in projects_dirs]
        project_name = Path(cwd).name

    # Bulk-load ccreport cache for fast rolling cost computation
    ccr_file_meta, ccr_records_by_file = bulk_load_ccreport_cache()

    week_total = 0.0
    session_total = 0.0
    sw_total = 0.0
    month_total = 0.0
    h6_total = 0.0
    h12_total = 0.0
    h24_total = 0.0
    sd_total = 0.0
    td_total = 0.0
    at_total = 0.0
    # Per-project rolling cost accumulators
    h6_proj = 0.0
    h12_proj = 0.0
    h24_proj = 0.0
    sd_proj = 0.0
    td_proj = 0.0
    at_proj = 0.0
    seen_keys: set[str] = set()
    new_entries: dict[str, Any] = {}
    dirty = False

    sw_ts = session_window_start.timestamp() if session_window_start else None
    mw_ts = month_window_start.timestamp()
    td_ts = thirty_day_start.timestamp()
    h6_ts = six_hour_start.timestamp()
    h12_ts = twelve_hour_start.timestamp()
    h24_ts = twenty_four_hour_start.timestamp()
    sd_ts = seven_day_start.timestamp()
    ww_ts = week_window_start.timestamp()
    oldest_ts = min(mw_ts, td_ts)

    live_paths: set[str] = set()

    for projects_dir in projects_dirs:
        for jsonl_path in projects_dir.rglob("*.jsonl"):
            key = str(jsonl_path)
            live_paths.add(key)
            try:
                st = jsonl_path.stat()
            except OSError:
                continue

            is_session_file = key in session_files
            is_project_file = any(key.startswith(p) for p in project_prefixes)
            in_session_window = sw_ts is not None and st.st_mtime >= sw_ts
            in_rolling_window = st.st_mtime >= td_ts

            cached_entry = file_cache.get(key)
            file_unchanged = (
                cached_entry
                and cached_entry.get("mtime_ns") == st.st_mtime_ns
                and cached_entry.get("size") == st.st_size
            )

            # --- Full cache hit: old file, unchanged, not in any rolling window ---
            if st.st_mtime < oldest_ts and not is_session_file:
                if file_unchanged:
                    c = cached_entry.get("all_time_cost", 0.0)
                    at_total += c
                    if is_project_file:
                        at_proj += c
                    new_entries[key] = cached_entry
                    seen_keys.update(cached_entry.get("dedup_keys", []))
                    continue

            if file_unchanged and not in_session_window and not in_rolling_window:
                week_total += cached_entry.get("week_cost", 0.0)
                month_total += cached_entry.get("month_cost", 0.0)
                c = cached_entry.get("all_time_cost", 0.0)
                at_total += c
                if is_project_file:
                    at_proj += c
                if is_session_file:
                    session_total += cached_entry.get("session_cost", 0.0)
                new_entries[key] = cached_entry
                seen_keys.update(cached_entry.get("dedup_keys", []))
                continue

            # --- Partial hit: file unchanged but needs rolling costs ---
            # Try ccreport_records cache first (much faster than JSONL re-parse)
            ccr_meta = ccr_file_meta.get(key)
            ccr_fresh = (
                ccr_meta is not None
                and ccr_meta[0] == st.st_mtime_ns
                and ccr_meta[1] == st.st_size
            )

            if file_unchanged and ccr_fresh:
                # Use file_costs for week/month/all_time, ccreport for rolling
                week_total += cached_entry.get("week_cost", 0.0)
                month_total += cached_entry.get("month_cost", 0.0)
                c = cached_entry.get("all_time_cost", 0.0)
                at_total += c
                if is_project_file:
                    at_proj += c
                if is_session_file:
                    session_total += cached_entry.get("session_cost", 0.0)
                new_entries[key] = cached_entry

                # Compute rolling costs from ccreport records
                for rec in ccr_records_by_file.get(key, []):
                    dk = rec.get("dk")
                    if dk:
                        if dk in seen_keys:
                            continue
                        seen_keys.add(dk)
                    ts_e = rec.get("ts", 0)
                    if not ts_e or ts_e < td_ts:
                        # Outside all rolling windows, skip
                        if not (in_session_window and sw_ts and ts_e >= sw_ts):
                            continue
                    cost = _rec_cost(rec)
                    if not cost:
                        continue
                    if ts_e >= td_ts:
                        td_total += cost
                        if is_project_file:
                            td_proj += cost
                    if ts_e >= sd_ts:
                        sd_total += cost
                        if is_project_file:
                            sd_proj += cost
                    if ts_e >= h24_ts:
                        h24_total += cost
                        if is_project_file:
                            h24_proj += cost
                    if ts_e >= h12_ts:
                        h12_total += cost
                        if is_project_file:
                            h12_proj += cost
                    if ts_e >= h6_ts:
                        h6_total += cost
                        if is_project_file:
                            h6_proj += cost
                    if sw_ts and ts_e >= sw_ts:
                        sw_total += cost
                # Also add any file_costs dedup keys not seen via ccreport records
                seen_keys.update(cached_entry.get("dedup_keys", []))
                continue

            # --- Cache miss: parse JSONL file ---
            w_cost = 0.0
            s_cost = 0.0
            sw_cost = 0.0
            m_cost = 0.0
            h6_cost = 0.0
            h12_cost = 0.0
            h24_cost = 0.0
            sd_cost = 0.0
            td_cost = 0.0
            a_cost = 0.0
            file_dedup_keys: list[str] = []

            for cost, ts, dk in _iter_jsonl_costs(jsonl_path, seen_keys):
                if dk:
                    file_dedup_keys.append(dk)
                a_cost += cost
                if ts >= month_window_start:
                    m_cost += cost
                if ts >= week_window_start:
                    w_cost += cost
                if ts >= thirty_day_start:
                    td_cost += cost
                if ts >= seven_day_start:
                    sd_cost += cost
                if ts >= twenty_four_hour_start:
                    h24_cost += cost
                if ts >= twelve_hour_start:
                    h12_cost += cost
                if ts >= six_hour_start:
                    h6_cost += cost
                if is_session_file:
                    s_cost += cost
                if session_window_start and ts >= session_window_start:
                    sw_cost += cost

            if file_unchanged:
                week_total += cached_entry.get("week_cost", 0.0)
                month_total += cached_entry.get("month_cost", 0.0)
                c = cached_entry.get("all_time_cost", 0.0)
                at_total += c
                if is_project_file:
                    at_proj += c
                if is_session_file:
                    session_total += cached_entry.get("session_cost", 0.0)
                new_entries[key] = cached_entry
            else:
                entry: dict[str, Any] = {
                    "mtime_ns": st.st_mtime_ns,
                    "size": st.st_size,
                    "week_cost": round(w_cost, 6),
                    "month_cost": round(m_cost, 6),
                    "all_time_cost": round(a_cost, 6),
                    "dedup_keys": file_dedup_keys,
                }
                if is_session_file:
                    entry["session_cost"] = round(s_cost, 6)
                new_entries[key] = entry
                week_total += w_cost
                month_total += m_cost
                at_total += a_cost
                if is_project_file:
                    at_proj += a_cost
                session_total += s_cost
                dirty = True

            sw_total += sw_cost
            h6_total += h6_cost
            h12_total += h12_cost
            h24_total += h24_cost
            sd_total += sd_cost
            td_total += td_cost
            if is_project_file:
                h6_proj += h6_cost
                h12_proj += h12_cost
                h24_proj += h24_cost
                sd_proj += sd_cost
                td_proj += td_cost

    if dirty or set(new_entries) != set(file_cache):
        try:
            bulk_save_file_costs(new_entries, week_key, month_key)
        except OSError:
            pass

    # Include orphaned records (from deleted JSONL files cached by ccreport)
    for fp, recs in ccr_records_by_file.items():
        if fp in live_paths:
            continue
        for rec in recs:
            dk = rec.get("dk")
            if dk:
                if dk in seen_keys:
                    continue
                seen_keys.add(dk)
            cost = _rec_cost(rec)
            if not cost:
                continue
            ts_epoch = rec.get("ts", 0)
            at_total += cost
            if project_name:
                proj = rec.get("project", "")
                if proj == project_name:
                    at_proj += cost
            if ts_epoch:
                if ts_epoch >= td_ts:
                    td_total += cost
                if ts_epoch >= sd_ts:
                    sd_total += cost
                if ts_epoch >= h24_ts:
                    h24_total += cost
                if ts_epoch >= h12_ts:
                    h12_total += cost
                if ts_epoch >= h6_ts:
                    h6_total += cost
                if ts_epoch >= mw_ts:
                    month_total += cost
                if ts_epoch >= ww_ts:
                    week_total += cost
                if sw_ts and ts_epoch >= sw_ts:
                    sw_total += cost

    result = {
        "session_cost": round(session_total, 4),
        "session_window_cost": round(sw_total, 4),
        "week_cost": round(week_total, 4),
        "month_cost": round(month_total, 4),
        "six_hour_cost": round(h6_total, 4),
        "twelve_hour_cost": round(h12_total, 4),
        "twenty_four_hour_cost": round(h24_total, 4),
        "seven_day_cost": round(sd_total, 4),
        "thirty_day_cost": round(td_total, 4),
        "all_time_cost": round(at_total, 4),
        "six_hour_project_cost": round(h6_proj, 4),
        "twelve_hour_project_cost": round(h12_proj, 4),
        "twenty_four_hour_project_cost": round(h24_proj, 4),
        "seven_day_project_cost": round(sd_proj, 4),
        "thirty_day_project_cost": round(td_proj, 4),
        "all_time_project_cost": round(at_proj, 4),
    }

    # Cache for fast reads by statusline
    try:
        from cache_db import write_cost_summary
        write_cost_summary(result)
    except Exception:  # noqa: BLE001
        pass

    return result
