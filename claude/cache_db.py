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
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path.home() / ".cache" / "macsetup" / "claude" / "cache.db"

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
    session_id TEXT PRIMARY KEY,
    file_size  INTEGER NOT NULL,
    cost       REAL NOT NULL
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
    _conn = sqlite3.connect(str(DB_PATH), timeout=10)
    _conn.execute("PRAGMA journal_mode = WAL")
    _conn.execute("PRAGMA synchronous = NORMAL")
    _conn.execute("PRAGMA foreign_keys = ON")
    _conn.execute("PRAGMA cache_size = -2000")
    _conn.executescript(_SCHEMA_SQL)
    # Migrate: add project cost columns to existing usage tables
    for col in (
        "six_hour_project_cost", "twelve_hour_project_cost",
        "twenty_four_hour_project_cost", "seven_day_project_cost",
        "thirty_day_project_cost", "all_time_project_cost",
    ):
        try:
            _conn.execute(f"ALTER TABLE usage ADD COLUMN {col} REAL")
        except sqlite3.OperationalError:
            pass  # column already exists
    atexit.register(close_connection)
    return _conn


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


def read_usage_for_statusline() -> dict[str, Any] | None:
    """Fast read of usage data for statusline (same validation as read_usage_cache)."""
    return read_usage_cache(600)


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
    conn.commit()


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


def load_all_dedup_keys() -> set[str]:
    """Bulk load all dedup keys into a Python set."""
    conn = get_connection()
    rows = conn.execute("SELECT dk FROM dedup_keys").fetchall()
    return {r[0] for r in rows}


def load_dedup_keys_for_file(path: str) -> list[str]:
    """Load dedup keys for a single file."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT dk FROM dedup_keys WHERE file_path = ?", (path,)
    ).fetchall()
    return [r[0] for r in rows]


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

def read_session_cost(session_id: str) -> tuple[int, float] | None:
    """Read (file_size, cost) or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT file_size, cost FROM session_costs WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    return row


def write_session_cost(session_id: str, file_size: int, cost: float) -> None:
    """Upsert session cost entry."""
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO session_costs (session_id, file_size, cost) "
        "VALUES (?, ?, ?)",
        (session_id, file_size, cost),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# ccreport cache
# ---------------------------------------------------------------------------

def check_ccreport_valid(version: int, script_hash: str) -> bool:
    """Check if ccreport cache is valid (version + script_hash match)."""
    conn = get_connection()
    stored_version = _get_meta(conn, "ccreport_version")
    stored_hash = _get_meta(conn, "ccreport_script_hash")
    return stored_version == str(version) and stored_hash == script_hash


def invalidate_ccreport() -> None:
    """Delete all ccreport data and reset meta."""
    conn = get_connection()
    conn.execute("DELETE FROM ccreport_files")
    conn.execute("DELETE FROM meta WHERE key IN ('ccreport_version', 'ccreport_script_hash')")
    conn.commit()


def init_ccreport_meta(version: int, script_hash: str) -> None:
    """Set version and script_hash in meta table."""
    conn = get_connection()
    _set_meta(conn, "ccreport_version", str(version))
    _set_meta(conn, "ccreport_script_hash", script_hash)
    conn.commit()


def get_ccreport_file(path: str) -> tuple[int, int] | None:
    """Get (mtime_ns, size) for a cached file, or None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT mtime_ns, size FROM ccreport_files WHERE path = ?", (path,)
    ).fetchone()
    return row


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


def delete_ccreport_stale(live_paths: set[str]) -> bool:
    """Delete entries for files not in live_paths. Returns True if any deleted."""
    conn = get_connection()
    rows = conn.execute("SELECT path FROM ccreport_files").fetchall()
    stale = [r[0] for r in rows if r[0] not in live_paths]
    if not stale:
        return False
    conn.executemany(
        "DELETE FROM ccreport_files WHERE path = ?", [(p,) for p in stale]
    )
    conn.commit()
    return True


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
    all_records: list[dict] = []
    for path in orphaned:
        all_records.extend(get_ccreport_records(path))
    return all_records


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
