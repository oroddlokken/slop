"""Unified SQLite cache for Claude Code usage, costs, and reporting.

Single database at ~/.cache/macsetup/claude/cache.db.

Consumers:
  - get_claude_usage.py  (usage data + cost cache)
  - statusline-command.py (usage read + session stats/costs)
  - ccreport.py          (file-level record cache)
"""

from __future__ import annotations

import atexit
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path.home() / ".cache" / "macsetup" / "claude" / "cache.db"

# Snapshots live outside ~/.cache so aggressive cache cleanup can't take out
# the live DB and all its backups in one sweep.
_DEFAULT_SNAPSHOT_DIR = Path.home() / ".local" / "share" / "macsetup" / "claude" / "snapshots"
_SNAPSHOT_KEEP_DEFAULT = 14
_SANITY_DROP_THRESHOLD_PCT = 10.0
_SANITY_MIN_PRIOR_COUNT = 100

_conn: sqlite3.Connection | None = None

_SCHEMA_SQL = """\
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS usage (
    id                    INTEGER PRIMARY KEY CHECK (id = 1),
    session_percent       INTEGER,
    session_reset         TEXT,
    week_percent          INTEGER,
    week_reset            TEXT,
    sonnet_percent        INTEGER,
    sonnet_reset          TEXT,
    extra_percent         INTEGER,
    extra_spent           REAL,
    extra_limit           REAL,
    extra_reset           TEXT,
    last_updated          TEXT,
    session_cost          REAL,
    session_window_cost   REAL,
    week_cost             REAL,
    month_cost            REAL,
    six_hour_cost         REAL,
    twelve_hour_cost      REAL,
    twenty_four_hour_cost REAL,
    seven_day_cost        REAL,
    thirty_day_cost       REAL,
    all_time_cost         REAL,
    six_hour_project_cost         REAL,
    twelve_hour_project_cost      REAL,
    twenty_four_hour_project_cost REAL,
    seven_day_project_cost        REAL,
    thirty_day_project_cost       REAL,
    all_time_project_cost         REAL,
    meta_json             TEXT
);

CREATE TABLE IF NOT EXISTS file_costs (
    path          TEXT PRIMARY KEY,
    mtime_ns      INTEGER NOT NULL,
    size          INTEGER NOT NULL,
    week_cost     REAL NOT NULL DEFAULT 0,
    month_cost    REAL NOT NULL DEFAULT 0,
    all_time_cost REAL NOT NULL DEFAULT 0,
    session_cost  REAL
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS dedup_keys (
    dk        TEXT NOT NULL,
    file_path TEXT NOT NULL REFERENCES file_costs(path) ON DELETE CASCADE,
    PRIMARY KEY (dk, file_path)
) WITHOUT ROWID;

CREATE INDEX IF NOT EXISTS idx_dedup_file ON dedup_keys(file_path);

CREATE TABLE IF NOT EXISTS cache_stats (
    session_id       TEXT PRIMARY KEY,
    total_in_tokens  INTEGER NOT NULL,
    cum_fresh        INTEGER NOT NULL,
    cum_cache_create INTEGER NOT NULL,
    cum_cache_read   INTEGER NOT NULL
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS session_costs (
    session_id  TEXT PRIMARY KEY,
    fingerprint INTEGER NOT NULL,
    cost        REAL NOT NULL
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS ccreport_files (
    path     TEXT PRIMARY KEY,
    mtime_ns INTEGER NOT NULL,
    size     INTEGER NOT NULL
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS ccreport_records (
    id            INTEGER PRIMARY KEY,
    file_path     TEXT NOT NULL REFERENCES ccreport_files(path) ON DELETE CASCADE,
    mid           TEXT,
    model         TEXT NOT NULL,
    ts            REAL NOT NULL,
    sid           TEXT NOT NULL,
    project       TEXT NOT NULL,
    dk            TEXT,
    cost          REAL,
    input_tokens  INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cache_create  INTEGER NOT NULL,
    cache_read    INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ccr_file ON ccreport_records(file_path);
CREATE INDEX IF NOT EXISTS idx_ccr_ts ON ccreport_records(ts);

CREATE TABLE IF NOT EXISTS extra_usage_snapshots (
    ts    REAL PRIMARY KEY,
    spent REAL NOT NULL
) WITHOUT ROWID;
"""


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """Return a module-level singleton connection, creating the DB if needed."""
    global _conn
    if _conn is not None:
        return _conn
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db_existed = DB_PATH.exists() and DB_PATH.stat().st_size > 0
    _conn = sqlite3.connect(str(DB_PATH), timeout=10)
    _conn.execute("PRAGMA journal_mode = WAL")
    _conn.execute("PRAGMA synchronous = NORMAL")
    _conn.execute("PRAGMA foreign_keys = ON")
    _conn.execute("PRAGMA cache_size = -2000")
    # Snapshot before any schema changes or data migrations touch the DB.
    if db_existed:
        _maybe_snapshot(_conn)
    _conn.executescript(_SCHEMA_SQL)
    # Migrate: add project cost columns to existing usage tables
    for col in (
        "six_hour_project_cost", "twelve_hour_project_cost",
        "twenty_four_hour_project_cost", "seven_day_project_cost",
        "thirty_day_project_cost", "all_time_project_cost",
    ):
        try:
            _conn.execute(f"ALTER TABLE usage ADD COLUMN {col} REAL")
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise
    migration_ran = _run_migrations(_conn)
    if db_existed and migration_ran:
        _sanity_check(_conn)
    atexit.register(close_connection)
    return _conn


def _run_migrations(conn: sqlite3.Connection) -> bool:
    """Run one-time data migrations, tracked by meta flags.

    Returns True if any migration actually executed this invocation. The
    caller uses this to decide whether to run the post-migration sanity
    check — we don't want to pay that cost on every statusline render.
    Future migrations that DELETE rows from ccreport_records must keep
    setting this flag so the sanity check runs.
    """
    ran = False
    # Migration 1: Opus 4.6 / Sonnet 4.6 switched to flat pricing (no 200k tier)
    # on 2026-03-13T18:00 UTC. Cached costs for files modified after that date
    # used inflated tiered rates. Only clear those — older files had correct
    # pricing and their JSONL sources may already be purged from disk.
    if not _get_meta(conn, "migrated_flat_pricing_2026_03_13"):
        cutoff_ns = 1773424800000000000  # 2026-03-13T18:00 UTC in nanoseconds
        conn.execute("DELETE FROM file_costs WHERE mtime_ns >= ?", (cutoff_ns,))
        conn.execute("DELETE FROM session_costs")
        conn.execute("DELETE FROM meta WHERE key IN ('cost_summary', 'cost_summary_time')")
        _set_meta(conn, "migrated_flat_pricing_2026_03_13", "1")
        conn.commit()
        ran = True

    # Migration 2: Also NULL out cached costs in ccreport_records for
    # post-flat-pricing Opus/Sonnet 4.6 records so _rec_cost and record_cost
    # recompute from tokens with the new flat pricing.
    if not _get_meta(conn, "migrated_flat_pricing_ccreport"):
        cutoff_ts = 1773424800.0  # 2026-03-13T18:00 UTC
        conn.execute(
            "UPDATE ccreport_records SET cost = NULL "
            "WHERE ts >= ? AND model IN ('claude-opus-4-6', 'claude-sonnet-4-6')",
            (cutoff_ts,),
        )
        conn.execute("DELETE FROM session_costs")
        conn.execute("DELETE FROM meta WHERE key IN ('cost_summary', 'cost_summary_time')")
        _set_meta(conn, "migrated_flat_pricing_ccreport", "1")
        conn.commit()
        ran = True

    # Migration 3: Rename misleading file_size → fingerprint in session_costs
    if not _get_meta(conn, "migrated_rename_fingerprint"):
        try:
            conn.execute("ALTER TABLE session_costs RENAME COLUMN file_size TO fingerprint")
        except sqlite3.OperationalError:
            pass  # Column already renamed or table structure differs
        _set_meta(conn, "migrated_rename_fingerprint", "1")
        conn.commit()
        ran = True
    return ran


# ---------------------------------------------------------------------------
# Snapshot & sanity guard
# ---------------------------------------------------------------------------
#
# One daily snapshot of the live DB, written with SQLite's online backup API
# so WAL-mode writers won't corrupt it. Default location lives outside
# ~/.cache/ so cache-cleanup sweeps can't take the backups out with the
# original. The sanity guard runs after migrations (only when one actually
# executed) and warns if the irreplaceable ccreport_records table has lost
# a material fraction of its rows compared to the most recent prior snapshot.
#
# Env overrides:
#   CLAUDE_CACHE_SNAPSHOT_DIR       — destination directory
#   CLAUDE_CACHE_SNAPSHOT_KEEP      — retention count (default 14)
#   CLAUDE_CACHE_SNAPSHOT_DISABLE=1 — skip snapshots entirely
#   CLAUDE_CACHE_SANITY_DISABLE=1   — skip sanity check
#   CLAUDE_CACHE_SANITY_ABORT=1     — raise instead of warn on drop


def _snapshot_dir() -> Path:
    override = os.environ.get("CLAUDE_CACHE_SNAPSHOT_DIR")
    return Path(override).expanduser() if override else _DEFAULT_SNAPSHOT_DIR


def _snapshot_keep() -> int:
    raw = os.environ.get("CLAUDE_CACHE_SNAPSHOT_KEEP")
    if not raw:
        return _SNAPSHOT_KEEP_DEFAULT
    try:
        return max(1, int(raw))
    except ValueError:
        return _SNAPSHOT_KEEP_DEFAULT


def _today_utc() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")


def _maybe_snapshot(conn: sqlite3.Connection) -> Path | None:
    """Take today's snapshot if it doesn't already exist. Rotate old ones.

    Returns the snapshot path on success (existing or newly written),
    None if skipped or failed. Failures never raise — snapshots are a
    safety net, not a prerequisite. The tmp file is PID-suffixed so two
    processes racing the first-of-day snapshot don't clobber each other.
    """
    if os.environ.get("CLAUDE_CACHE_SNAPSHOT_DISABLE") == "1":
        return None
    snap_dir = _snapshot_dir()
    target = snap_dir / f"{_today_utc()}.db"
    if target.exists():
        return target
    tmp = target.with_suffix(target.suffix + f".{os.getpid()}.tmp")
    try:
        snap_dir.mkdir(parents=True, exist_ok=True)
        dst = sqlite3.connect(str(tmp))
        try:
            conn.backup(dst)
        finally:
            dst.close()
        tmp.replace(target)
    except (sqlite3.Error, OSError) as e:
        try:
            print(f"Warning: cache.db snapshot failed: {e}", file=sys.stderr)
        except OSError:
            pass
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return None
    try:
        snapshots = sorted(snap_dir.glob("????-??-??.db"))
        keep = _snapshot_keep()
        for old in snapshots[:-keep]:
            try:
                old.unlink()
            except OSError:
                pass
    except OSError:
        pass
    return target


def _sanity_check(conn: sqlite3.Connection) -> None:
    """Warn if ccreport_records count fell materially vs the prior snapshot.

    Uses the most recent snapshot from a day before today so a same-run
    snapshot can't mask a wipe. Requires a meaningful prior count before
    acting so a small dev DB doesn't raise false alarms. Only called from
    get_connection() when a migration actually ran — so statusline renders
    without pending migrations pay nothing.
    """
    if os.environ.get("CLAUDE_CACHE_SANITY_DISABLE") == "1":
        return
    snap_dir = _snapshot_dir()
    if not snap_dir.is_dir():
        return
    today_name = f"{_today_utc()}.db"
    snapshots = sorted(snap_dir.glob("????-??-??.db"))
    prior = [s for s in snapshots if s.name != today_name]
    if not prior:
        return
    compare_snap = prior[-1]
    try:
        src = sqlite3.connect(f"file:{compare_snap}?mode=ro", uri=True)
        try:
            prev_count = src.execute(
                "SELECT COUNT(*) FROM ccreport_records"
            ).fetchone()[0]
        finally:
            src.close()
    except sqlite3.Error:
        return
    if prev_count < _SANITY_MIN_PRIOR_COUNT:
        return
    cur_count = conn.execute("SELECT COUNT(*) FROM ccreport_records").fetchone()[0]
    drop_pct = 100.0 * (prev_count - cur_count) / prev_count
    if drop_pct < _SANITY_DROP_THRESHOLD_PCT:
        return
    msg = (
        f"cache.db lost ccreport_records rows: "
        f"{drop_pct:.1f}% drop ({prev_count} -> {cur_count}).\n"
        f"  Prior snapshot: {compare_snap}\n"
        f"  Restore with:   cp '{compare_snap}' '{DB_PATH}'"
    )
    if os.environ.get("CLAUDE_CACHE_SANITY_ABORT") == "1":
        raise RuntimeError(msg)
    try:
        print(f"Warning: {msg}", file=sys.stderr)
    except OSError:
        pass


def close_connection() -> None:
    """Explicitly close the module-level connection."""
    global _conn
    if _conn is not None:
        _conn.close()
        _conn = None


# ---------------------------------------------------------------------------
# Usage data
# ---------------------------------------------------------------------------

_USAGE_FIELDS = [
    "session_percent", "session_reset", "week_percent", "week_reset",
    "sonnet_percent", "sonnet_reset", "extra_percent", "extra_spent",
    "extra_limit", "extra_reset", "last_updated",
    "session_cost", "session_window_cost", "week_cost", "month_cost",
    "six_hour_cost", "twelve_hour_cost", "twenty_four_hour_cost",
    "seven_day_cost", "thirty_day_cost", "all_time_cost",
    "six_hour_project_cost", "twelve_hour_project_cost",
    "twenty_four_hour_project_cost", "seven_day_project_cost",
    "thirty_day_project_cost", "all_time_project_cost",
]


def _usage_row_to_dict(row: tuple) -> dict[str, Any]:
    """Convert a usage table row to a dict matching the old usage.json shape."""
    # Columns: id, <_USAGE_FIELDS>, meta_json
    d: dict[str, Any] = {}
    for i, field in enumerate(_USAGE_FIELDS):
        val = row[i + 1]  # skip id column
        if val is not None:
            d[field] = val
    meta_json = row[len(_USAGE_FIELDS) + 1]
    if meta_json:
        try:
            extra = json.loads(meta_json)
            for k, v in extra.items():
                d[k] = v
        except (json.JSONDecodeError, TypeError):
            pass
    return d


def _check_usage_freshness(d: dict[str, Any], max_age: int) -> bool:
    """Check if usage data is fresh (not expired, windows not shifted)."""
    last_updated = d.get("last_updated")
    if not last_updated:
        return False
    try:
        lu_dt = datetime.fromisoformat(last_updated)
        age = time.time() - lu_dt.timestamp()
        if age > max_age:
            return False
    except (ValueError, TypeError):
        return False
    now = datetime.now(tz=timezone.utc).astimezone()
    for key in ("session_reset", "week_reset"):
        iso = d.get(key)
        if iso:
            try:
                if datetime.fromisoformat(iso) <= now:
                    return False
            except (ValueError, TypeError):
                pass
    return True


def read_usage_cache(max_age: int = 600) -> dict[str, Any] | None:
    """Read cached usage data if fresh enough.

    Returns None if no data, age > max_age, or any reset time has passed.
    """
    conn = get_connection()
    cols = ", ".join(["id", *_USAGE_FIELDS, "meta_json"])
    row = conn.execute(f"SELECT {cols} FROM usage WHERE id = 1").fetchone()
    if row is None:
        return None
    d = _usage_row_to_dict(row)
    if not _check_usage_freshness(d, max_age):
        return None
    return d


def read_usage_stale() -> dict[str, Any] | None:
    """Read cached usage data regardless of freshness."""
    conn = get_connection()
    cols = ", ".join(["id", *_USAGE_FIELDS, "meta_json"])
    row = conn.execute(f"SELECT {cols} FROM usage WHERE id = 1").fetchone()
    if row is None:
        return None
    return _usage_row_to_dict(row)


# ---------------------------------------------------------------------------
# Fetch lock & error backoff
# ---------------------------------------------------------------------------

_BACKOFF_SCHEDULE = [45, 120, 240]  # seconds, indexed by consecutive failures
_LOCK_STALE_TIMEOUT = 30  # seconds before a held lock is considered abandoned


_lock_owner: str | None = None  # UUID token set when this process holds the lock


def _check_backoff_in_txn(conn: sqlite3.Connection, now: float) -> bool:
    """Check if we're in error backoff. Must be called inside a transaction."""
    count_str = _get_meta(conn, "fetch_fail_count")
    if not count_str:
        return False
    try:
        count = int(count_str)
    except ValueError:
        return False
    if count <= 0:
        return False
    fail_time_str = _get_meta(conn, "fetch_fail_time")
    if not fail_time_str:
        return False
    try:
        elapsed = now - float(fail_time_str)
    except ValueError:
        return False
    idx = min(count - 1, len(_BACKOFF_SCHEDULE) - 1)
    return elapsed < _BACKOFF_SCHEDULE[idx]


def try_acquire_fetch_lock() -> bool:
    """Atomically acquire fetch lock with backoff check. Returns True if acquired.

    Uses BEGIN IMMEDIATE to serialise concurrent writers so the
    read-check-write is atomic.  A lock older than _LOCK_STALE_TIMEOUT
    is treated as abandoned (e.g. crashed process).

    The backoff check is folded into the same transaction to prevent
    a failure being recorded between the two checks.

    An owner token (UUID) is stored alongside the lock so that only
    the process that acquired the lock can release it.
    """
    import uuid

    global _lock_owner

    conn = get_connection()
    now = time.time()
    conn.execute("BEGIN IMMEDIATE")
    try:
        if _check_backoff_in_txn(conn, now):
            conn.execute("COMMIT")
            return False

        locked_at_str = _get_meta(conn, "fetch_lock_time")
        if locked_at_str:
            try:
                if now - float(locked_at_str) < _LOCK_STALE_TIMEOUT:
                    conn.execute("COMMIT")
                    return False
            except ValueError:
                # Corrupt lock timestamp — treat as stale and allow acquisition
                import sys
                print(f"Warning: corrupt fetch_lock_time {locked_at_str!r}, treating as stale",
                      file=sys.stderr)
        owner = str(uuid.uuid4())
        _set_meta(conn, "fetch_lock_time", str(now))
        _set_meta(conn, "fetch_lock_owner", owner)
        conn.execute("COMMIT")
        _lock_owner = owner
        return True
    except Exception:
        conn.execute("ROLLBACK")
        raise


def release_fetch_lock() -> None:
    """Release the fetch lock only if this process owns it."""
    global _lock_owner

    conn = get_connection()
    if _lock_owner is not None:
        stored = _get_meta(conn, "fetch_lock_owner")
        if stored != _lock_owner:
            # Not our lock — another process took over after staleness timeout
            _lock_owner = None
            return
    conn.execute(
        "DELETE FROM meta WHERE key IN ('fetch_lock_time', 'fetch_lock_owner')"
    )
    conn.commit()
    _lock_owner = None


def record_fetch_failure() -> None:
    """Increment consecutive failure count and record time."""
    conn = get_connection()
    count_str = _get_meta(conn, "fetch_fail_count") or "0"
    try:
        count = int(count_str) + 1
    except ValueError:
        count = 1
    _set_meta(conn, "fetch_fail_count", str(count))
    _set_meta(conn, "fetch_fail_time", str(time.time()))
    conn.commit()


def clear_fetch_failures() -> None:
    """Clear failure count on successful fetch."""
    conn = get_connection()
    conn.execute(
        "DELETE FROM meta WHERE key IN ('fetch_fail_count', 'fetch_fail_time')"
    )
    conn.commit()


def check_fetch_backoff() -> bool:
    """Return True if we should skip fetching due to error backoff."""
    conn = get_connection()
    count_str = _get_meta(conn, "fetch_fail_count")
    if not count_str:
        return False
    try:
        count = int(count_str)
    except ValueError:
        return False
    if count <= 0:
        return False
    fail_time_str = _get_meta(conn, "fetch_fail_time")
    if not fail_time_str:
        return False
    try:
        elapsed = time.time() - float(fail_time_str)
    except ValueError:
        return False
    idx = min(count - 1, len(_BACKOFF_SCHEDULE) - 1)
    return elapsed < _BACKOFF_SCHEDULE[idx]


def _is_fetch_blocked() -> bool:
    """Check if fetching is blocked by an active lock or error backoff."""
    if check_fetch_backoff():
        return True
    conn = get_connection()
    locked_at_str = _get_meta(conn, "fetch_lock_time")
    if locked_at_str:
        try:
            if time.time() - float(locked_at_str) < _LOCK_STALE_TIMEOUT:
                return True
        except ValueError:
            pass
    return False


def read_usage_for_statusline() -> dict[str, Any] | None:
    """Fast read of usage data for statusline (same validation as read_usage_cache).

    When cache is expired but a fetch is blocked (lock held or error backoff),
    returns stale data with a ``_stale`` flag to avoid spawning a pointless
    subprocess while letting callers show a staleness indicator.
    """
    result = read_usage_cache(600)
    if result is not None:
        return result
    if _is_fetch_blocked():
        stale = read_usage_stale()
        if stale is not None:
            stale["_stale"] = True
        return stale
    return None


def write_usage_cache(data: dict[str, Any]) -> None:
    """Write usage data to the usage table (INSERT OR REPLACE singleton row)."""
    conn = get_connection()
    # Separate structured fields from extra blobs
    extra: dict[str, Any] = {}
    for k in ("_meta", "_cleaned_session", "_cleaned"):
        if k in data:
            extra[k] = data[k]
    meta_json = json.dumps(extra) if extra else None

    vals = [data.get(f) for f in _USAGE_FIELDS]
    placeholders = ", ".join(["?"] * (len(_USAGE_FIELDS) + 2))
    cols = ", ".join(["id", *_USAGE_FIELDS, "meta_json"])
    conn.execute(
        f"INSERT OR REPLACE INTO usage ({cols}) VALUES ({placeholders})",
        [1, *vals, meta_json],
    )

    # Record extra_spent snapshot for per-window delta tracking
    es = data.get("extra_spent")
    if es is not None:
        now_ts = time.time()
        conn.execute(
            "INSERT OR REPLACE INTO extra_usage_snapshots (ts, spent) VALUES (?, ?)",
            (now_ts, float(es)),
        )
        # Prune snapshots older than 31 days
        cutoff = now_ts - 31 * 86400
        conn.execute("DELETE FROM extra_usage_snapshots WHERE ts < ?", (cutoff,))

    conn.commit()


def compute_extra_window_deltas(
    current_spent: float,
    session_window_start_epoch: float | None,
    week_window_start_epoch: float | None,
) -> dict[str, float | None]:
    """Compute extra usage deltas for session and week windows.

    Looks up the snapshot closest to (but <=) each window start and returns
    the difference from current_spent.  Returns None for a window if no
    snapshot predates it.  A billing-reset (spent drops) yields 0.
    """
    conn = get_connection()
    result: dict[str, float | None] = {
        "extra_session_delta": None,
        "extra_week_delta": None,
    }

    for key, start_epoch in (
        ("extra_session_delta", session_window_start_epoch),
        ("extra_week_delta", week_window_start_epoch),
    ):
        if start_epoch is None:
            continue
        row = conn.execute(
            "SELECT spent FROM extra_usage_snapshots "
            "WHERE ts <= ? ORDER BY ts DESC LIMIT 1",
            (start_epoch,),
        ).fetchone()
        if row is not None:
            baseline = row[0]
            delta = current_spent - baseline
            # Billing reset: spent dropped below baseline → show 0
            result[key] = max(0.0, delta)
        # No pre-window snapshot → leave as None (unknown, not zero)

    return result


# ---------------------------------------------------------------------------
# Cost cache
# ---------------------------------------------------------------------------

def load_cost_cache(week_key: str, month_key: str) -> dict[str, dict[str, Any]]:
    """Load all file_costs entries. Truncates if week/month keys shifted.

    Returns dict keyed by file path with mtime_ns, size, week_cost,
    month_cost, all_time_cost, session_cost, dedup_keys.
    """
    conn = get_connection()

    # Check if keys match
    stored_week = _get_meta(conn, "cost_week")
    stored_month = _get_meta(conn, "cost_month")
    if stored_week != week_key or stored_month != month_key:
        # Keys shifted — invalidate all file costs
        conn.execute("DELETE FROM file_costs")
        _set_meta(conn, "cost_week", week_key)
        _set_meta(conn, "cost_month", month_key)
        conn.commit()
        return {}

    # Load all entries
    rows = conn.execute(
        "SELECT path, mtime_ns, size, week_cost, month_cost, all_time_cost, session_cost FROM file_costs"
    ).fetchall()

    # Also load dedup_keys per file
    dk_rows = conn.execute("SELECT dk, file_path FROM dedup_keys").fetchall()
    dk_map: dict[str, list[str]] = {}
    for dk, fpath in dk_rows:
        dk_map.setdefault(fpath, []).append(dk)

    result: dict[str, dict[str, Any]] = {}
    for path, mtime_ns, size, wc, mc, atc, sc in rows:
        entry: dict[str, Any] = {
            "mtime_ns": mtime_ns,
            "size": size,
            "week_cost": wc,
            "month_cost": mc,
            "all_time_cost": atc,
            "dedup_keys": dk_map.get(path, []),
        }
        if sc is not None:
            entry["session_cost"] = sc
        result[path] = entry
    return result



def bulk_save_file_costs(
    entries: dict[str, dict[str, Any]],
    week_key: str,
    month_key: str,
) -> None:
    """Atomically replace the entire file_costs + dedup_keys dataset."""
    conn = get_connection()
    conn.execute("BEGIN")
    try:
        # Update meta keys
        _set_meta(conn, "cost_week", week_key)
        _set_meta(conn, "cost_month", month_key)

        # Clear and rebuild
        conn.execute("DELETE FROM file_costs")

        for path, entry in entries.items():
            conn.execute(
                "INSERT INTO file_costs (path, mtime_ns, size, week_cost, month_cost, all_time_cost, session_cost) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    path,
                    entry["mtime_ns"],
                    entry["size"],
                    entry.get("week_cost", 0),
                    entry.get("month_cost", 0),
                    entry.get("all_time_cost", 0),
                    entry.get("session_cost"),
                ),
            )
            dedup_keys = entry.get("dedup_keys", [])
            if dedup_keys:
                conn.executemany(
                    "INSERT OR IGNORE INTO dedup_keys (dk, file_path) VALUES (?, ?)",
                    [(dk, path) for dk in dedup_keys],
                )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


# ---------------------------------------------------------------------------
# Cache stats
# ---------------------------------------------------------------------------

def read_cache_stats(session_id: str) -> tuple[int, int, int, int] | None:
    """Read (total_in_tokens, cum_fresh, cum_create, cum_read) or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT total_in_tokens, cum_fresh, cum_cache_create, cum_cache_read "
        "FROM cache_stats WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    return row


def write_cache_stats(
    session_id: str,
    total_in_tokens: int,
    cum_fresh: int,
    cum_create: int,
    cum_read: int,
) -> None:
    """Upsert cache stats for a session."""
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO cache_stats "
        "(session_id, total_in_tokens, cum_fresh, cum_cache_create, cum_cache_read) "
        "VALUES (?, ?, ?, ?, ?)",
        (session_id, total_in_tokens, cum_fresh, cum_create, cum_read),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Session costs
# ---------------------------------------------------------------------------

def read_session_cost(session_id: str) -> tuple[str, float] | None:
    """Read (fingerprint, cost) or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT fingerprint, cost FROM session_costs WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    if row is None:
        return None
    return (str(row[0]), row[1])


def write_session_cost(session_id: str, fingerprint: str, cost: float) -> None:
    """Upsert session cost entry keyed by fingerprint."""
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO session_costs (session_id, fingerprint, cost) "
        "VALUES (?, ?, ?)",
        (session_id, fingerprint, cost),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# ccreport cache
# ---------------------------------------------------------------------------

# Bump this when schema or serialization changes in cache_db.py affect
# the format of stored ccreport records (macsetup-2tt1).
CACHE_SCHEMA_SALT = "1"


def check_ccreport_valid(version: int, script_hash: str) -> bool:
    """Check if ccreport cache is valid (version + script_hash + schema salt)."""
    conn = get_connection()
    stored_version = _get_meta(conn, "ccreport_version")
    stored_hash = _get_meta(conn, "ccreport_script_hash")
    stored_salt = _get_meta(conn, "ccreport_schema_salt")
    return (
        stored_version == str(version)
        and stored_hash == script_hash
        and stored_salt == CACHE_SCHEMA_SALT
    )


def invalidate_ccreport() -> None:
    """Invalidate ccreport cache, forcing re-parse of live files.

    Resets mtime_ns/size to 0 so all live files get re-parsed on the next run.
    NULLs out cached costs so they recompute with current pricing logic.
    Preserves orphaned records (from JSONL files already purged by Claude Code)
    since those are irrecoverable from disk (macsetup-qn0k).
    """
    conn = get_connection()
    # Reset fingerprints so live files fail the mtime/size check and get
    # re-parsed.  Orphaned files (no longer on disk) keep their records
    # intact — load_all_records skips them for live processing but
    # get_ccreport_orphaned_records still returns them.
    conn.execute("UPDATE ccreport_files SET mtime_ns = 0, size = 0")
    # NULL out cached costs so they recompute with current pricing.
    conn.execute("UPDATE ccreport_records SET cost = NULL")
    conn.execute("DELETE FROM meta WHERE key IN ('ccreport_version', 'ccreport_script_hash', 'ccreport_schema_salt')")
    conn.commit()


def init_ccreport_meta(version: int, script_hash: str) -> None:
    """Set version, script_hash, and schema salt in meta table."""
    conn = get_connection()
    _set_meta(conn, "ccreport_version", str(version))
    _set_meta(conn, "ccreport_script_hash", script_hash)
    _set_meta(conn, "ccreport_schema_salt", CACHE_SCHEMA_SALT)
    conn.commit()


def get_ccreport_file(path: str) -> tuple[int, int] | None:
    """Get (mtime_ns, size) for a cached file, or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT mtime_ns, size FROM ccreport_files WHERE path = ?", (path,)
    ).fetchone()
    return row


def bulk_load_ccreport_cache() -> tuple[dict[str, tuple[int, int]], dict[str, list[dict]]]:
    """Bulk-load all ccreport file metadata and records.

    Returns (file_meta, records_by_file) where:
      file_meta: {path: (mtime_ns, size)}
      records_by_file: {path: [list of record dicts]}
    """
    conn = get_connection()
    # File metadata
    file_rows = conn.execute("SELECT path, mtime_ns, size FROM ccreport_files").fetchall()
    file_meta = {r[0]: (r[1], r[2]) for r in file_rows}
    if not file_meta:
        return {}, {}
    # All records
    rec_rows = conn.execute(
        "SELECT file_path, mid, model, ts, sid, project, dk, cost, "
        "input_tokens, output_tokens, cache_create, cache_read "
        "FROM ccreport_records"
    ).fetchall()
    records_by_file: dict[str, list[dict]] = {}
    for fp, mid, model, ts, sid, project, dk, cost, inp, out, cc, cr in rec_rows:
        rec = {"mid": mid, "model": model, "ts": ts, "sid": sid,
               "project": project, "dk": dk, "cost": cost,
               "t": [inp, out, cc, cr]}
        records_by_file.setdefault(fp, []).append(rec)
    return file_meta, records_by_file


def get_ccreport_records(path: str) -> list[dict]:
    """Fetch all cached records for a file path.

    Returns list of dicts with keys matching the compact format:
    mid, model, ts, sid, project, dk, cost, t.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT mid, model, ts, sid, project, dk, cost, "
        "input_tokens, output_tokens, cache_create, cache_read "
        "FROM ccreport_records WHERE file_path = ?",
        (path,),
    ).fetchall()
    return [
        {
            "mid": r[0], "model": r[1], "ts": r[2], "sid": r[3],
            "project": r[4], "dk": r[5], "cost": r[6],
            "t": [r[7], r[8], r[9], r[10]],
        }
        for r in rows
    ]


def save_ccreport_file(
    path: str, mtime_ns: int, size: int, records: list[dict],
) -> None:
    """Save/replace a file entry and all its records."""
    conn = get_connection()
    # Delete old entry (cascades to records)
    conn.execute("DELETE FROM ccreport_files WHERE path = ?", (path,))
    conn.execute(
        "INSERT INTO ccreport_files (path, mtime_ns, size) VALUES (?, ?, ?)",
        (path, mtime_ns, size),
    )
    if records:
        conn.executemany(
            "INSERT INTO ccreport_records "
            "(file_path, mid, model, ts, sid, project, dk, cost, "
            "input_tokens, output_tokens, cache_create, cache_read) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    path, r["mid"], r["model"], r["ts"], r["sid"],
                    r["project"], r.get("dk"), r.get("cost"),
                    r["t"][0], r["t"][1], r["t"][2], r["t"][3],
                )
                for r in records
            ],
        )
    conn.commit()


def get_ccreport_orphaned_records(live_paths: set[str]) -> list[dict]:
    """Fetch cached records for files no longer on disk.

    Returns records from ccreport_files entries whose path is NOT in
    live_paths, preserving historic data after Claude Code purges JSONL files.
    """
    conn = get_connection()
    rows = conn.execute("SELECT path FROM ccreport_files").fetchall()
    orphaned = [r[0] for r in rows if r[0] not in live_paths]
    if not orphaned:
        return []
    placeholders = ",".join("?" * len(orphaned))
    rows = conn.execute(
        f"SELECT mid, model, ts, sid, project, dk, cost, "
        f"input_tokens, output_tokens, cache_create, cache_read "
        f"FROM ccreport_records WHERE file_path IN ({placeholders})",
        orphaned,
    ).fetchall()
    return [
        {
            "mid": r[0], "model": r[1], "ts": r[2], "sid": r[3],
            "project": r[4], "dk": r[5], "cost": r[6],
            "t": [r[7], r[8], r[9], r[10]],
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Cost summary cache (written by compute_costs, read by statusline)
# ---------------------------------------------------------------------------

def write_cost_summary(costs: dict[str, Any], cwd: str | None = None) -> None:
    """Cache the latest compute_costs() result for fast statusline reads.

    Scoped by project (cwd) to prevent cross-contamination between terminals.
    """
    conn = get_connection()
    suffix = f":{cwd.replace('/', '-')}" if cwd else ""
    _set_meta(conn, f"cost_summary{suffix}", json.dumps(costs))
    _set_meta(conn, f"cost_summary_time{suffix}", str(time.time()))
    conn.commit()


def read_cost_summary(max_age: int = 600, cwd: str | None = None) -> dict[str, Any] | None:
    """Read cached cost summary if fresh enough, scoped by project."""
    conn = get_connection()
    suffix = f":{cwd.replace('/', '-')}" if cwd else ""
    ts_str = _get_meta(conn, f"cost_summary_time{suffix}")
    if not ts_str:
        return None
    try:
        if time.time() - float(ts_str) > max_age:
            return None
    except ValueError:
        return None
    raw = _get_meta(conn, f"cost_summary{suffix}")
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Meta helpers
# ---------------------------------------------------------------------------

def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value)
    )
