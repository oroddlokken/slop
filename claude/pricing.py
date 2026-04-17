"""Shared Claude model pricing data, cost calculation, and cost aggregation.

Single source of truth for pricing tables, model aliases, cost formulas,
and cost aggregation. get_claude_usage.py, statusline-command.py, and
ccreport.py all import from this module.

AUDIT: All calculations are documented in claude/CLAUDE.md.
When changing any pricing, tiering, or cost logic here, update CLAUDE.md to match.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, NamedTuple, TypedDict
from zoneinfo import ZoneInfo


class UsageData(TypedDict, total=False):
    """Cross-module usage dict flowing through fetch→cache→compute→render.

    All fields are optional since different pipeline stages populate different
    subsets. Use usage.get("key") for safe access.
    """

    # Rate limits (from API fetch)
    session_percent: int
    session_reset: str
    week_percent: int
    week_reset: str
    sonnet_percent: int
    sonnet_reset: str

    # Extra usage (from API fetch)
    extra_percent: int
    extra_spent: float
    extra_limit: float

    # Metadata
    last_updated: str
    _meta: dict[str, Any]
    _stale: bool

    # Cost windows (from compute_costs)
    session_window_cost: float
    week_cost: float
    session_cost: float
    six_hour_cost: float
    six_hour_project_cost: float
    twelve_hour_cost: float
    twelve_hour_project_cost: float
    twenty_four_hour_cost: float
    twenty_four_hour_project_cost: float
    seven_day_cost: float
    seven_day_project_cost: float
    thirty_day_cost: float
    thirty_day_project_cost: float
    all_time_cost: float
    all_time_project_cost: float
    month_cost: float
    project_cost: float

    # Peak info (from compute_peak_info)
    peak_is_peak: bool
    peak_flip_seconds: int


def _local_tz() -> ZoneInfo:
    """Return the system's local timezone using full zone rules (DST-aware)."""
    try:
        import os
        tz_env = os.environ.get("TZ")
        if tz_env:
            return ZoneInfo(tz_env)
        # On macOS/Linux, read /etc/localtime symlink target
        localtime = Path("/etc/localtime")
        if localtime.is_symlink():
            target = str(localtime.resolve())
            # e.g. /usr/share/zoneinfo/Europe/Oslo → Europe/Oslo
            marker = "/zoneinfo/"
            idx = target.find(marker)
            if idx >= 0:
                return ZoneInfo(target[idx + len(marker):])
        # Fallback: current fixed offset (better than crashing)
        return ZoneInfo("UTC")
    except Exception:  # noqa: BLE001
        return ZoneInfo("UTC")

# Source: https://github.com/BerriAI/litellm model_prices_and_context_window.json
LAST_CHECKED = "2026-04-16"

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
    {
        # Opus 4.7 released 2026-04-16, same pricing as 4.6.
        "effective": "2026-04-16",
        "models": {
            "claude-opus-4-7": {
                "input": 5e-06, "output": 25e-06,
                "cache_create": 6.25e-06, "cache_read": 0.5e-06,
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
        if model and not model.startswith("<"):
            print(f"Warning: no pricing found for model '{model}'", file=sys.stderr)
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

# Rolling cost window definitions: (name, timedelta offset from now).
# Order matters — must be longest→shortest so the bucket cascade works
# with early-exit optimisation (if ts < longest, skip all).
ROLLING_WINDOWS: list[tuple[str, timedelta]] = [
    ("thirty_day", timedelta(days=30)),
    ("seven_day", timedelta(days=7)),
    ("twenty_four_hour", timedelta(hours=24)),
    ("twelve_hour", timedelta(hours=12)),
    ("six_hour", timedelta(hours=6)),
]


def _rolling_thresholds(now_local: datetime) -> dict[str, float]:
    """Compute epoch timestamps for each rolling window boundary."""
    return {name: (now_local - delta).timestamp() for name, delta in ROLLING_WINDOWS}


def _bucket_rolling_cost(
    cost: float,
    ts_epoch: float,
    thresholds: dict[str, float],
    totals: dict[str, float],
    proj_totals: dict[str, float] | None = None,
    is_project: bool = False,
) -> None:
    """Accumulate *cost* into the appropriate rolling window buckets.

    Mutates *totals* (and optionally *proj_totals*) in place.
    *thresholds* maps window name → epoch cutoff.
    """
    for name, _ in ROLLING_WINDOWS:
        if ts_epoch >= thresholds[name]:
            totals[name] = totals.get(name, 0.0) + cost
            if is_project and proj_totals is not None:
                proj_totals[name] = proj_totals.get(name, 0.0) + cost


def extract_assistant_fields(
    rec: dict,
) -> tuple[dict, dict, str, str, str | None, datetime] | None:
    """Extract and validate common fields from a parsed JSONL assistant record.

    Returns (message, usage, message_id, request_id, dedup_key, timestamp)
    or None if the record is invalid/incomplete.

    Shared by _iter_jsonl_costs (pricing) and parse_jsonl_file (ccreport).
    """
    if rec.get("type") != "assistant":
        return None
    msg = rec.get("message")
    if not msg or not isinstance(msg, dict):
        return None
    usage = msg.get("usage")
    if not usage or not isinstance(usage, dict):
        return None

    message_id = msg.get("id", "")
    request_id = rec.get("requestId", "")
    dk: str | None = None
    if message_id and request_id:
        dk = f"{message_id}:{request_id}"

    ts_str = rec.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None

    return msg, usage, message_id, request_id, dk, ts


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

                fields = extract_assistant_fields(rec)
                if fields is None:
                    continue
                msg, usage, _mid, _rid, dk, ts = fields

                if dk is not None:
                    if dk in seen_keys:
                        continue
                    seen_keys.add(dk)

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

    Uses a fingerprint-based cache (path+mtime+size) in SQLite to avoid
    re-parsing unchanged files. Falls back to cached ccreport_records
    when JSONL files have been purged.
    """
    import hashlib

    from cache_db import read_session_cost, write_session_cost

    if not session_id or not cwd:
        return 0.0

    files = _find_session_files(session_id, cwd)
    if not files:
        # JSONL files gone — fall back to cached ccreport records (macsetup-2wsk)
        # Scope by project path to avoid cross-project misattribution
        try:
            from cache_db import bulk_load_ccreport_cache
            _, ccr_records_by_file = bulk_load_ccreport_cache()
            project_key = cwd.replace("/", "-")
            proj_dirs = _get_projects_dirs()
            project_prefixes = [str(d / project_key) + "/" for d in proj_dirs]
            total = 0.0
            seen: set[str] = set()
            for fp, recs in ccr_records_by_file.items():
                if not any(fp.startswith(p) for p in project_prefixes):
                    continue
                for rec in recs:
                    if rec.get("sid") != session_id:
                        continue
                    dk = rec.get("dk")
                    if dk:
                        if dk in seen:
                            continue
                        seen.add(dk)
                    cost = _rec_cost(rec)
                    if cost:
                        total += cost
            return total
        except Exception:  # noqa: BLE001
            return 0.0

    # Build fingerprint from sorted (path, mtime_ns, size) tuples
    file_stats: list[tuple[str, int, int]] = []
    for f in sorted(files):
        try:
            st = Path(f).stat()
            file_stats.append((f, st.st_mtime_ns, st.st_size))
        except OSError:
            continue

    if not file_stats:
        return 0.0

    fingerprint = hashlib.md5(
        str(file_stats).encode(), usedforsecurity=False,
    ).hexdigest()

    cached = read_session_cost(session_id)
    if cached is not None and cached[0] == fingerprint:
        return cached[1]

    seen_keys: set[str] = set()
    total_cost = 0.0
    for path in sorted(files):
        for cost, _ts, _dk in _iter_jsonl_costs(path, seen_keys):
            total_cost += cost

    write_session_cost(session_id, fingerprint, total_cost)
    return total_cost


def _accumulate_orphaned_costs(
    ccr_records_by_file: dict[str, list[dict]],
    live_paths: set[str],
    seen_keys: set[str],
    thresholds: dict[str, float],
    totals: dict[str, float],
    proj_totals: dict[str, float] | None = None,
    project_name: str = "",
    project_path_prefixes: list[str] | None = None,
    extra_thresholds: dict[str, float] | None = None,
    extra_totals: dict[str, float] | None = None,
) -> None:
    """Accumulate costs from orphaned ccreport records (deleted JSONL files).

    Mutates *totals*, *proj_totals*, and *extra_totals* in place.
    *extra_thresholds*/*extra_totals* handle non-rolling windows (week, month, session).
    """
    for fp, recs in ccr_records_by_file.items():
        if fp in live_paths:
            continue
        if project_path_prefixes is not None:
            is_ours = any(fp.startswith(p) for p in project_path_prefixes)
        else:
            is_ours = False
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
            totals["all_time"] = totals.get("all_time", 0.0) + cost
            is_project = False
            if project_name and rec.get("project", "") == project_name:
                is_project = True
                if proj_totals is not None:
                    proj_totals["all_time"] = proj_totals.get("all_time", 0.0) + cost
            if is_ours and proj_totals is not None:
                # For project-only scans, all orphaned records from project dirs count
                if not project_name:
                    proj_totals["all_time"] = proj_totals.get("all_time", 0.0) + cost
                    is_project = True
            if ts_epoch:
                _bucket_rolling_cost(cost, ts_epoch, thresholds, totals,
                                     proj_totals, is_project)
                if extra_thresholds and extra_totals:
                    for key, thresh in extra_thresholds.items():
                        if ts_epoch >= thresh:
                            extra_totals[key] = extra_totals.get(key, 0.0) + cost


def compute_project_rolling_costs(cwd: str) -> dict[str, float]:
    """Compute rolling cost totals for a single project directory.

    Lightweight scan of only the project's JSONL files — suitable for
    per-render use in the statusline without touching the shared cache.
    """
    if not cwd:
        return {}

    project_key = cwd.replace("/", "-")
    projects_dirs = _get_projects_dirs()

    now_local = datetime.now(tz=_local_tz())
    thresholds = _rolling_thresholds(now_local)
    totals: dict[str, float] = {}
    seen_keys: set[str] = set()

    for d in projects_dirs:
        proj_dir = d / project_key
        if not proj_dir.is_dir():
            continue
        for jsonl_path in sorted(proj_dir.rglob("*.jsonl")):
            for cost, ts, _dk in _iter_jsonl_costs(jsonl_path, seen_keys):
                totals["all_time"] = totals.get("all_time", 0.0) + cost
                _bucket_rolling_cost(cost, ts.timestamp(), thresholds, totals)

    # Include orphaned cached records for this project (macsetup-59zg)
    try:
        from cache_db import bulk_load_ccreport_cache
        _, ccr_records_by_file = bulk_load_ccreport_cache()
        project_path_prefixes = [str(d / project_key) + "/" for d in projects_dirs]
        # Filter to only orphaned records from this project's directories
        # to avoid inflating project costs with other projects' data.
        project_ccr = {
            fp: recs for fp, recs in ccr_records_by_file.items()
            if any(fp.startswith(p) for p in project_path_prefixes)
        }
        live_paths: set[str] = set()
        for d in projects_dirs:
            proj_dir = d / project_key
            if proj_dir.is_dir():
                live_paths.update(str(p) for p in proj_dir.rglob("*.jsonl"))
        _accumulate_orphaned_costs(
            project_ccr, live_paths, seen_keys, thresholds,
            totals, project_path_prefixes=project_path_prefixes,
        )
    except Exception:  # noqa: BLE001
        pass

    return {
        f"{name}_project_cost": round(totals.get(name, 0.0), 4)
        for name in [n for n, _ in ROLLING_WINDOWS] + ["all_time"]
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
    now = datetime.now(tz=_local_tz())

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


class _FileContext(NamedTuple):
    """Immutable per-file facts used by compute_costs helpers."""
    key: str
    is_session_file: bool
    is_project_file: bool
    in_session_window: bool
    in_rolling_window: bool
    file_unchanged: bool
    ccr_fresh: bool


class _CacheResult(NamedTuple):
    """Return type for _try_cached_file — contributions from a cache hit."""
    week: float
    month: float
    session: float
    session_window: float
    entry: dict[str, Any]


class _ScanResult(NamedTuple):
    """Return type for _scan_jsonl_file — raw totals from parsing JSONL."""
    week_cost: float
    month_cost: float
    session_cost: float
    sw_cost: float
    all_time_cost: float
    file_rolling: dict[str, float]
    dedup_keys: list[str]


def _try_cached_file(
    ctx: _FileContext,
    cached_entry: dict[str, Any] | None,
    ccr_records_by_file: dict[str, list[dict]],
    seen_keys: set[str],
    thresholds: dict[str, float],
    oldest_ts: float,
    sw_ts: float | None,
    td_ts: float,
    rolling_totals: dict[str, float],
    rolling_proj: dict[str, float],
) -> _CacheResult | None:
    """Try to handle a file entirely from caches (branches 1-3).

    Returns a _CacheResult if the file was fully handled, None if a JSONL
    parse is needed. Mutates *seen_keys*, *rolling_totals*, *rolling_proj*.
    """
    if not ctx.file_unchanged or cached_entry is None:
        return None

    # Branches 1+2: unchanged, outside rolling/session windows
    if not ctx.in_session_window and not ctx.in_rolling_window:
        c = cached_entry.get("all_time_cost", 0.0)
        rolling_totals["all_time"] = rolling_totals.get("all_time", 0.0) + c
        if ctx.is_project_file:
            rolling_proj["all_time"] = rolling_proj.get("all_time", 0.0) + c
        seen_keys.update(cached_entry.get("dedup_keys", []))
        return _CacheResult(
            week=cached_entry.get("week_cost", 0.0),
            month=cached_entry.get("month_cost", 0.0),
            session=cached_entry.get("session_cost", 0.0) if ctx.is_session_file else 0.0,
            session_window=0.0,
            entry=cached_entry,
        )

    # Branch 3: unchanged + ccreport records available for rolling costs
    if not ctx.ccr_fresh:
        return None

    c = cached_entry.get("all_time_cost", 0.0)
    rolling_totals["all_time"] = rolling_totals.get("all_time", 0.0) + c
    if ctx.is_project_file:
        rolling_proj["all_time"] = rolling_proj.get("all_time", 0.0) + c
    session = cached_entry.get("session_cost", 0.0) if ctx.is_session_file else 0.0
    sw = 0.0

    for rec in ccr_records_by_file.get(ctx.key, []):
        dk = rec.get("dk")
        if dk:
            if dk in seen_keys:
                continue
            seen_keys.add(dk)
        ts_e = rec.get("ts", 0)
        if not ts_e or ts_e < td_ts:
            if not (ctx.in_session_window and sw_ts and ts_e >= sw_ts):
                continue
        cost = _rec_cost(rec)
        if not cost:
            continue
        _bucket_rolling_cost(cost, ts_e, thresholds,
                             rolling_totals, rolling_proj, ctx.is_project_file)
        if sw_ts and ts_e >= sw_ts:
            sw += cost

    # Merge dedup keys from file_costs cache not seen via ccreport
    seen_keys.update(cached_entry.get("dedup_keys", []))
    return _CacheResult(
        week=cached_entry.get("week_cost", 0.0),
        month=cached_entry.get("month_cost", 0.0),
        session=session,
        session_window=sw,
        entry=cached_entry,
    )


def _scan_jsonl_file(
    jsonl_path: Path,
    is_session_file: bool,
    session_window_start: datetime | None,
    week_window_start: datetime,
    month_window_start: datetime,
    thresholds: dict[str, float],
    seen_keys: set[str],
) -> _ScanResult:
    """Parse a JSONL file and compute cost totals for all windows.

    Mutates *seen_keys* in place (via _iter_jsonl_costs).
    """
    w_cost = 0.0
    s_cost = 0.0
    sw_cost = 0.0
    m_cost = 0.0
    a_cost = 0.0
    file_rolling: dict[str, float] = {}
    file_dedup_keys: list[str] = []

    for cost, ts, dk in _iter_jsonl_costs(jsonl_path, seen_keys):
        if dk:
            file_dedup_keys.append(dk)
        a_cost += cost
        if ts >= month_window_start:
            m_cost += cost
        if ts >= week_window_start:
            w_cost += cost
        _bucket_rolling_cost(cost, ts.timestamp(), thresholds, file_rolling)
        if is_session_file:
            s_cost += cost
        if session_window_start and ts >= session_window_start:
            sw_cost += cost

    return _ScanResult(
        week_cost=w_cost,
        month_cost=m_cost,
        session_cost=s_cost,
        sw_cost=sw_cost,
        all_time_cost=a_cost,
        file_rolling=file_rolling,
        dedup_keys=file_dedup_keys,
    )


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

    now_local = datetime.now(tz=_local_tz())
    month_window_start = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_key = month_window_start.strftime("%Y-%m")

    thresholds = _rolling_thresholds(now_local)

    file_cache = load_cost_cache(week_key, month_key)

    session_files: set[str] = set()
    if session_id and cwd:
        session_files = _find_session_files(session_id, cwd, projects_dirs)

    # Per-project prefixes for identifying files belonging to current cwd
    project_prefixes: list[str] = []
    project_name = ""
    if cwd:
        project_key = cwd.replace("/", "-")
        project_prefixes = [str(d / project_key) + "/" for d in projects_dirs]
        project_name = Path(cwd).name

    # Bulk-load ccreport cache for fast rolling cost computation
    ccr_file_meta, ccr_records_by_file = bulk_load_ccreport_cache()

    week_total = 0.0
    session_total = 0.0
    sw_total = 0.0
    month_total = 0.0
    rolling_totals: dict[str, float] = {}
    rolling_proj: dict[str, float] = {}
    seen_keys: set[str] = set()
    new_entries: dict[str, Any] = {}
    dirty = False

    sw_ts = session_window_start.timestamp() if session_window_start else None
    mw_ts = month_window_start.timestamp()
    ww_ts = week_window_start.timestamp()
    td_ts = thresholds["thirty_day"]
    oldest_ts = min(mw_ts, td_ts)

    live_paths: set[str] = set()

    for projects_dir in projects_dirs:
        for jsonl_path in sorted(projects_dir.rglob("*.jsonl")):
            key = str(jsonl_path)
            live_paths.add(key)
            try:
                st = jsonl_path.stat()
            except OSError:
                continue

            cached_entry = file_cache.get(key)
            ccr_meta = ccr_file_meta.get(key)

            ctx = _FileContext(
                key=key,
                is_session_file=key in session_files,
                is_project_file=any(key.startswith(p) for p in project_prefixes),
                in_session_window=sw_ts is not None and st.st_mtime >= sw_ts,
                in_rolling_window=st.st_mtime >= td_ts,
                file_unchanged=bool(
                    cached_entry
                    and cached_entry.get("mtime_ns") == st.st_mtime_ns
                    and cached_entry.get("size") == st.st_size
                ),
                ccr_fresh=bool(
                    ccr_meta is not None
                    and ccr_meta[0] == st.st_mtime_ns
                    and ccr_meta[1] == st.st_size
                ),
            )

            # --- Try cache-based handling (branches 1-3) ---
            hit = _try_cached_file(
                ctx, cached_entry, ccr_records_by_file, seen_keys,
                thresholds, oldest_ts, sw_ts, td_ts,
                rolling_totals, rolling_proj,
            )
            if hit is not None:
                week_total += hit.week
                month_total += hit.month
                session_total += hit.session
                sw_total += hit.session_window
                new_entries[key] = hit.entry
                continue

            # --- Cache miss: scan JSONL file ---
            scan = _scan_jsonl_file(
                jsonl_path, ctx.is_session_file, session_window_start,
                week_window_start, month_window_start, thresholds, seen_keys,
            )

            if ctx.file_unchanged:
                assert cached_entry is not None  # file_unchanged implies cache hit
                # Reuse cached summary for week/month/all_time/session
                week_total += cached_entry.get("week_cost", 0.0)
                month_total += cached_entry.get("month_cost", 0.0)
                c = cached_entry.get("all_time_cost", 0.0)
                rolling_totals["all_time"] = rolling_totals.get("all_time", 0.0) + c
                if ctx.is_project_file:
                    rolling_proj["all_time"] = rolling_proj.get("all_time", 0.0) + c
                if ctx.is_session_file:
                    session_total += cached_entry.get("session_cost", 0.0)
                new_entries[key] = cached_entry
            else:
                entry: dict[str, Any] = {
                    "mtime_ns": st.st_mtime_ns,
                    "size": st.st_size,
                    "week_cost": round(scan.week_cost, 6),
                    "month_cost": round(scan.month_cost, 6),
                    "all_time_cost": round(scan.all_time_cost, 6),
                    "dedup_keys": scan.dedup_keys,
                }
                if ctx.is_session_file:
                    entry["session_cost"] = round(scan.session_cost, 6)
                new_entries[key] = entry
                week_total += scan.week_cost
                month_total += scan.month_cost
                rolling_totals["all_time"] = rolling_totals.get("all_time", 0.0) + scan.all_time_cost
                if ctx.is_project_file:
                    rolling_proj["all_time"] = rolling_proj.get("all_time", 0.0) + scan.all_time_cost
                session_total += scan.session_cost
                dirty = True

            sw_total += scan.sw_cost
            for name, _ in ROLLING_WINDOWS:
                fc = scan.file_rolling.get(name, 0.0)
                rolling_totals[name] = rolling_totals.get(name, 0.0) + fc
                if ctx.is_project_file:
                    rolling_proj[name] = rolling_proj.get(name, 0.0) + fc

    if dirty or set(new_entries) != set(file_cache):
        try:
            bulk_save_file_costs(new_entries, week_key, month_key)
        except OSError:
            pass

    # Include orphaned records (from deleted JSONL files cached by ccreport)
    extra_thresholds = {"month": mw_ts, "week": ww_ts}
    if sw_ts:
        extra_thresholds["session_window"] = sw_ts
    extra_totals: dict[str, float] = {}
    _accumulate_orphaned_costs(
        ccr_records_by_file, live_paths, seen_keys, thresholds,
        rolling_totals, rolling_proj, project_name,
        extra_thresholds=extra_thresholds, extra_totals=extra_totals,
    )
    month_total += extra_totals.get("month", 0.0)
    week_total += extra_totals.get("week", 0.0)
    sw_total += extra_totals.get("session_window", 0.0)

    result = {
        "session_cost": round(session_total, 4),
        "session_window_cost": round(sw_total, 4),
        "week_cost": round(week_total, 4),
        "month_cost": round(month_total, 4),
        "all_time_cost": round(rolling_totals.get("all_time", 0.0), 4),
        "all_time_project_cost": round(rolling_proj.get("all_time", 0.0), 4),
    }
    for name, _ in ROLLING_WINDOWS:
        result[f"{name}_cost"] = round(rolling_totals.get(name, 0.0), 4)
        result[f"{name}_project_cost"] = round(rolling_proj.get(name, 0.0), 4)

    # Cache for fast reads by statusline
    try:
        from cache_db import write_cost_summary
        write_cost_summary(result, cwd=cwd)
    except Exception:  # noqa: BLE001
        pass

    return result
