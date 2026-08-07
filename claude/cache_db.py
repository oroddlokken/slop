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
from itertools import groupby
from operator import itemgetter
from pathlib import Path
from typing import Any

# pricing.py imports cache_db only inside functions, so this direction is safe.
from pricing import project_key, rolling_cost_keys

DB_PATH = Path.home() / ".cache" / "macsetup" / "claude" / "cache.db"

# Snapshots live outside ~/.cache so aggressive cache cleanup can't take out
# the live DB and all its backups in one sweep.
_DEFAULT_SNAPSHOT_DIR = Path.home() / ".local" / "share" / "macsetup" / "claude" / "snapshots"
_SNAPSHOT_KEEP_DEFAULT = 14
_SANITY_DROP_THRESHOLD_PCT = 10.0
_SANITY_MIN_PRIOR_COUNT = 100

_conn: sqlite3.Connection | None = None

# Stamped into the DB's PRAGMA user_version once the bootstrap below has run to
# completion; get_connection skips the entire bootstrap when the two match.
#
# BUMP THIS on any change to _SCHEMA_SQL, _ADDED_COLUMNS, or the migration list
# in _run_migrations — an existing DB is otherwise never reopened on the slow
# path and never sees the new DDL. A needless bump costs one slow open per DB.
SCHEMA_VERSION = 2

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
    scoped_percent        INTEGER,
    scoped_model          TEXT,
    scoped_reset          TEXT,
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

-- file_path leads the key so the ON DELETE CASCADE and the per-file rewrite in
-- bulk_save_file_costs are PK range scans. Keyed the other way round this table
-- needed a secondary index on file_path, and a secondary index on a WITHOUT
-- ROWID table stores the indexed columns plus the whole PK — i.e. a second copy
-- of the table, on the highest-churn table there is (macsetup-4rpc).
CREATE TABLE IF NOT EXISTS dedup_keys (
    dk        TEXT NOT NULL,
    file_path TEXT NOT NULL REFERENCES file_costs(path) ON DELETE CASCADE,
    PRIMARY KEY (file_path, dk)
) WITHOUT ROWID;

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
    cwd           TEXT,
    repo          TEXT,
    dk            TEXT,
    cost          REAL,
    input_tokens  INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cache_create  INTEGER NOT NULL,
    cache_read    INTEGER NOT NULL
);

-- file_path leads because every scoped read starts from a path: the cascade
-- from ccreport_files, the per-file fetch, and the prefix range the statusline
-- uses to pull one project's records. ts trails it so a cutoff can ride along
-- inside a file scope. There is deliberately no standalone index on ts — no
-- statement filters ts without also bounding file_path (macsetup-3le2).
CREATE INDEX IF NOT EXISTS idx_ccr_file_ts ON ccreport_records(file_path, ts);
CREATE INDEX IF NOT EXISTS idx_ccr_sid ON ccreport_records(sid);

-- Manual project-grouping rules, applied as a pure function over the signals
-- stored on each record (name/remote/cwd) at report time. Local data, never
-- committed: merges and renames live here, not in code.
CREATE TABLE IF NOT EXISTS project_overrides (
    id          INTEGER PRIMARY KEY,
    match_kind  TEXT NOT NULL,   -- 'name' | 'remote' | 'cwd_prefix'
    match_value TEXT NOT NULL,
    target      TEXT NOT NULL,
    UNIQUE (match_kind, match_value)
);

CREATE TABLE IF NOT EXISTS extra_usage_snapshots (
    ts    REAL PRIMARY KEY,
    spent REAL NOT NULL
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS exchange_rates (
    date  TEXT PRIMARY KEY,
    rate  REAL NOT NULL
) WITHOUT ROWID;
"""


# Columns a DB created before them is missing. CREATE TABLE covers new DBs;
# these ALTERs bring an existing one up to the same shape.
#
# - the per-window cost columns, derived so a new rolling window needs no
#   migration of its own (the project half arrived after the totals)
# - ccreport cwd: NULL for orphan rows whose source JSONL is already gone —
#   those names are frozen in `project`
# - ccreport repo: normalized git remote, captured at parse time while the
#   working dir still exists. NULL for orphans parsed before this existed.
# - the weekly_scoped per-model limit, as named columns rather than meta_json
#   so the SELECT built from _USAGE_FIELDS picks them up
_ADDED_COLUMNS: list[tuple[str, str, str]] = [
    *(("usage", key, "REAL") for key in rolling_cost_keys()),
    ("usage", "scoped_percent", "INTEGER"),
    ("usage", "scoped_model", "TEXT"),
    ("usage", "scoped_reset", "TEXT"),
    ("ccreport_records", "cwd", "TEXT"),
    ("ccreport_records", "repo", "TEXT"),
]


def _add_column(
    conn: sqlite3.Connection, table: str, col: str, col_type: str,
) -> None:
    """ALTER TABLE ADD COLUMN, tolerating a column that is already there."""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")
    except sqlite3.OperationalError as e:
        if "duplicate column" not in str(e).lower():
            raise


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Column names of *table*, empty if it does not exist."""
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


# Bound on one statement's parameters. SQLITE_MAX_VARIABLE_NUMBER is 32766
# from SQLite 3.32 but 999 on older builds, so stay under the lower ceiling —
# both path sets these queries bind grow with the corpus and never shrink.
_PARAM_CHUNK = 500


def _param_chunks(paths: set[str]) -> list[list[str]]:
    """*paths* split into batches small enough to bind in one statement."""
    ordered = sorted(paths)
    return [ordered[i:i + _PARAM_CHUNK] for i in range(0, len(ordered), _PARAM_CHUNK)]


def _rollback_if_open(conn: sqlite3.Connection) -> None:
    """ROLLBACK, unless the transaction is already over.

    A failing COMMIT ends the transaction, so an unconditional rollback in the
    handler raises "cannot rollback - no transaction is active" and that
    replaces the real error (macsetup-39g2).
    """
    if conn.in_transaction:
        conn.execute("ROLLBACK")


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

_DEFAULT_DB_TIMEOUT_S = 10.0
# Above this a "timeout" is indistinguishable from a hang, so it reads as a
# typo rather than an intent — and it also filters out inf.
_MAX_DB_TIMEOUT_S = 3600.0


def _db_timeout() -> float:
    """Seconds to wait for the write lock, from CLAUDE_CACHE_DB_TIMEOUT.

    The CLI tools can afford the default; the statusline sets it low, because a
    render that blocks behind a writer prints nothing at all where one that
    gives up prints the same line with a slightly stale stat. Anything
    unparseable, non-positive or absurd falls back to the default rather than
    turning the wait off.
    """
    raw = os.environ.get("CLAUDE_CACHE_DB_TIMEOUT", "")
    if not raw:
        return _DEFAULT_DB_TIMEOUT_S
    try:
        val = float(raw)
    except ValueError:
        return _DEFAULT_DB_TIMEOUT_S
    return val if 0 < val <= _MAX_DB_TIMEOUT_S else _DEFAULT_DB_TIMEOUT_S


def get_connection() -> sqlite3.Connection:
    """Return a module-level singleton connection, creating the DB if needed."""
    global _conn
    if _conn is not None:
        return _conn
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db_existed = DB_PATH.exists() and DB_PATH.stat().st_size > 0
    conn = sqlite3.connect(str(DB_PATH), timeout=_db_timeout())
    # Registered before the bootstrap can fail, so a connection abandoned
    # half-built still gets closed. close_connection no-ops while _conn is None.
    atexit.register(close_connection)
    try:
        # These three are per-connection state SQLite does not persist, so they
        # sit outside the version gate below and are re-applied on every open.
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA cache_size = -2000")
        # Every process pays this bootstrap on its first DB touch — statusline
        # imports this module for every render — and on a warm DB all of it is
        # no-ops: 14 IF NOT EXISTS statements, six ALTERs raising and catching
        # "duplicate column", a SELECT per migration flag. The stamp says the
        # whole thing already ran to completion at this SCHEMA_VERSION.
        bootstrap_needed = _user_version(conn) != SCHEMA_VERSION
        # Snapshot before any schema change or data migration touches the DB.
        # A process that has deferred the daily copy still takes this one: it is
        # the pre-image for the only thing that can rewrite existing rows, and
        # the bootstrap it guards runs at most once per SCHEMA_VERSION.
        snapshot_written = False
        if db_existed and (bootstrap_needed or not _daily_snapshot_deferred()):
            _, snapshot_written = _maybe_snapshot(conn)
        migration_ran = False
        if bootstrap_needed:
            # journal_mode lives in the DB header, so unlike the pragmas above
            # it only needs setting on a DB this build has not opened before.
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(_SCHEMA_SQL)
            for table, col, col_type in _ADDED_COLUMNS:
                _add_column(conn, table, col, col_type)
            migration_ran = _run_migrations(conn)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION:d}")
        # Once a day (the run that writes the snapshot), plus any run that
        # migrated data — damage arrives from both directions. Deliberately
        # outside the gate: the daily cadence is the point, and migration_ran
        # is False on the fast path because nothing migrated. It rides the
        # snapshot rather than the calendar, so deferring the daily copy moves
        # the check onto the same process and off the render with it.
        if db_existed and (snapshot_written or migration_ran):
            _sanity_check(conn)
    except BaseException:
        conn.close()
        raise
    # Published only now. Assigning before the bootstrap leaves a failure
    # visible to every later get_connection() in the process as a working
    # connection over a half-built schema — and the broad `except Exception`
    # handlers in pricing.py and the statusline make that reachable.
    _conn = conn
    return _conn


def _user_version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def _purge_cost_summaries(conn: sqlite3.Connection) -> None:
    """Drop every cached compute_costs() result, project-scoped ones included.

    A migration that changes what a cost is worth has to clear this cache too,
    or the statusline serves the pre-migration figure until it ages out. The
    keys are not the bare 'cost_summary'/'cost_summary_time' they look like:
    write_cost_summary appends _cost_summary_suffix(cwd), and its only caller
    always passes a cwd, so in practice every stored key is
    cost_summary:<project> (macsetup-3a7f). Match on the prefix, not the two
    literals — migrations 1, 2 and 2b spelled out the literals and therefore
    cleared nothing at all.
    """
    conn.execute("DELETE FROM meta WHERE key LIKE 'cost_summary%'")


def _run_migrations(conn: sqlite3.Connection) -> bool:
    """Run one-time data migrations, tracked by meta flags.

    Returns True if any migration actually executed this invocation, which
    makes the caller run the sanity check on top of its daily cadence — a
    migration is the one moment a bug can wipe rows or costs outside that
    window. Migrations that touch ccreport_records must keep setting it.
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
        _purge_cost_summaries(conn)
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
        _purge_cost_summaries(conn)
        _set_meta(conn, "migrated_flat_pricing_ccreport", "1")
        conn.commit()
        ran = True

    # Migration 2b: Migration 2 matched model names by equality, so dated and
    # bracketed variants ('claude-opus-4-6[1m]') slipped through and kept their
    # inflated pre-flat-pricing costs. find_pricing matches by substring, so it
    # resolves those variants to the flat rates — recomputing from tokens is
    # correct even for orphan records, whose cost can't be re-read from disk.
    if not _get_meta(conn, "migrated_flat_pricing_ccreport_variants"):
        cutoff_ts = 1773424800.0  # 2026-03-13T18:00 UTC
        flat_keys = ("claude-opus-4-6", "claude-sonnet-4-6")
        affected = [
            model
            for (model,) in conn.execute(
                "SELECT DISTINCT model FROM ccreport_records WHERE ts >= ?",
                (cutoff_ts,),
            )
            # The substring rule find_pricing applies, run in reverse.
            if any(key in model or model in key for key in flat_keys)
        ]
        if affected:
            placeholders = ",".join("?" * len(affected))
            conn.execute(
                f"UPDATE ccreport_records SET cost = NULL "
                f"WHERE ts >= ? AND model IN ({placeholders})",
                (cutoff_ts, *affected),
            )
            conn.execute("DELETE FROM session_costs")
            _purge_cost_summaries(conn)
        _set_meta(conn, "migrated_flat_pricing_ccreport_variants", "1")
        conn.commit()
        ran = True

    # Migration 3: Rename misleading file_size → fingerprint in session_costs.
    # The ALTER and its flag go in one transaction: legacy isolation autocommits
    # around DDL, so as two commits a crash between them leaves the flag saying
    # done over an unrenamed table, and every session-cost read then raises
    # "no such column: fingerprint" with no path back.
    if not _get_meta(conn, "migrated_rename_fingerprint"):
        conn.execute("BEGIN IMMEDIATE")
        try:
            try:
                conn.execute(
                    "ALTER TABLE session_costs RENAME COLUMN file_size TO fingerprint"
                )
            except sqlite3.OperationalError as e:
                if not _rename_already_done(e):
                    raise
            # The flag is a claim about the table, so read the table rather than
            # trusting that the ALTER meant what we hoped.
            if "fingerprint" not in _table_columns(conn, "session_costs"):
                raise sqlite3.OperationalError(
                    "session_costs has no fingerprint column after the rename "
                    "migration; refusing to record it as done"
                )
            _set_meta(conn, "migrated_rename_fingerprint", "1")
            conn.execute("COMMIT")
            ran = True
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise

    # Migration 4: drop the three indexes the new DDL replaces. _SCHEMA_SQL
    # only ever creates, so on an existing DB the old ones would otherwise sit
    # there being maintained on every insert and read by nothing:
    #   idx_ccr_file    — a strict prefix of idx_ccr_file_ts, so redundant
    #   idx_ccr_ts      — no live statement has ever filtered ts in SQL
    #                     (macsetup-3le2); only the long-retired migration 2 did
    #   idx_dedup_file  — file_path now leads the dedup_keys PK (macsetup-4rpc)
    if not _get_meta(conn, "migrated_drop_dead_indexes"):
        conn.execute("BEGIN IMMEDIATE")
        try:
            for name in ("idx_ccr_file", "idx_ccr_ts", "idx_dedup_file"):
                conn.execute(f"DROP INDEX IF EXISTS {name}")
            _set_meta(conn, "migrated_drop_dead_indexes", "1")
            conn.execute("COMMIT")
            ran = True
        except BaseException:
            _rollback_if_open(conn)
            raise

    # Migration 5: rebuild dedup_keys with file_path leading the primary key.
    # A WITHOUT ROWID table's primary key cannot be altered in place, so this is
    # the create/copy/drop/rename dance, all inside one transaction so a crash
    # leaves either the old table or the new one and never neither.
    if not _get_meta(conn, "migrated_dedup_keys_pk_order"):
        conn.execute("BEGIN IMMEDIATE")
        try:
            order = _dedup_keys_pk_order(conn)
            # An empty order means there is no dedup_keys table to rebuild.
            # _SCHEMA_SQL creates it in the final shape and runs ahead of this
            # on every real path, so the only way here is _run_migrations
            # called on its own against a partial DB.
            if order and order != ["file_path", "dk"]:
                # dedup_keys is only ever a child, so PRAGMA foreign_keys can
                # stay ON: the DROP below removes a referencing table, not a
                # referenced one, and nothing points at dedup_keys to dangle.
                conn.execute(
                    "CREATE TABLE dedup_keys_new ("
                    "dk TEXT NOT NULL, "
                    "file_path TEXT NOT NULL "
                    "REFERENCES file_costs(path) ON DELETE CASCADE, "
                    "PRIMARY KEY (file_path, dk)) WITHOUT ROWID"
                )
                # Orphans are skipped, not copied: OR IGNORE covers uniqueness
                # but never a FOREIGN KEY violation, so with foreign_keys ON one
                # parentless row in the old table aborts the whole migration —
                # and with it every ccreport run (macsetup-1g9w). Dropping such a
                # key is what the cascade would have done anyway; the cost is one
                # re-parse of its source file.
                conn.execute(
                    "INSERT OR IGNORE INTO dedup_keys_new (dk, file_path) "
                    "SELECT dk, file_path FROM dedup_keys "
                    "WHERE file_path IN (SELECT path FROM file_costs)"
                )
                conn.execute("DROP TABLE dedup_keys")
                conn.execute("ALTER TABLE dedup_keys_new RENAME TO dedup_keys")
                # Same discipline as migration 3: the flag is a claim about the
                # table, so re-read the table rather than trust the DDL above.
                rebuilt = _dedup_keys_pk_order(conn)
                if rebuilt != ["file_path", "dk"]:
                    raise sqlite3.OperationalError(
                        f"dedup_keys primary key is {rebuilt} after the rebuild "
                        "migration; refusing to record it as done"
                    )
                if conn.execute("PRAGMA foreign_key_check(dedup_keys)").fetchall():
                    raise sqlite3.OperationalError(
                        "dedup_keys has rows with no file_costs parent after "
                        "the rebuild migration; refusing to record it as done"
                    )
            _set_meta(conn, "migrated_dedup_keys_pk_order", "1")
            conn.execute("COMMIT")
            ran = True
        except BaseException:
            _rollback_if_open(conn)
            raise

    return ran


def _dedup_keys_pk_order(conn: sqlite3.Connection) -> list[str]:
    """dedup_keys' primary-key columns, in key order. Empty if there is no table.

    PRAGMA table_info reports each column's 1-based position within the primary
    key in its `pk` field, and 0 for columns outside it.
    """
    cols = [
        (row[5], row[1])
        for row in conn.execute("PRAGMA table_info(dedup_keys)")
        if row[5]
    ]
    return [name for _pos, name in sorted(cols)]


def _rename_already_done(err: sqlite3.OperationalError) -> bool:
    """Whether *err* means the fingerprint rename has nothing left to do.

    Either the source column is gone (renamed by an earlier run, or never there
    because CREATE TABLE now ships `fingerprint` outright) or the target is
    already present. Everything else — "database is locked" above all, which is
    the routine failure on a contended cache.db — is a retryable failure and
    must reach the caller, or the migration is marked done and lost forever.
    """
    msg = str(err).lower()
    return ("no such column" in msg and "file_size" in msg) or "duplicate column" in msg


# ---------------------------------------------------------------------------
# Snapshot & sanity guard
# ---------------------------------------------------------------------------
#
# One daily snapshot of the live DB, written with SQLite's online backup API
# so WAL-mode writers won't corrupt it. Default location lives outside
# ~/.cache/ so cache-cleanup sweeps can't take the backups out with the
# original. The sanity guard rides the same once-a-day cadence — the run that
# writes the snapshot also compares the irreplaceable ccreport_records table
# against the most recent snapshot from a *prior* day — and additionally runs
# after any migration. It warns on a material loss of rows or of costs, and on
# records left parentless in ccreport_files.
#
# Who pays for it: whichever process opens the DB first after UTC midnight,
# minus the ones that set CLAUDE_CACHE_SNAPSHOT_DEFER. The statusline sets it,
# because the render is by far the most frequent first-toucher and a full copy
# of the DB is not something a status line should be doing; its detached
# refresh subprocess drops the variable and takes the day's snapshot instead
# (macsetup-3xzh). Deferring never reaches the pre-bootstrap snapshot above.
#
# Env overrides:
#   CLAUDE_CACHE_SNAPSHOT_DIR       — destination directory
#   CLAUDE_CACHE_SNAPSHOT_KEEP      — retention count (default 14)
#   CLAUDE_CACHE_SNAPSHOT_DISABLE=1 — skip snapshots entirely
#   CLAUDE_CACHE_SNAPSHOT_DEFER=1   — skip only the daily one; leave it to a
#                                     process that isn't on a render path
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


def _daily_snapshot_deferred() -> bool:
    """Whether this process leaves the routine daily snapshot to another one.

    Distinct from CLAUDE_CACHE_SNAPSHOT_DISABLE, which turns snapshots off
    including the one taken before a migration. Deferring is a statement about
    *this* process being a bad place to copy the DB, not about wanting fewer
    backups, so it never suppresses the pre-bootstrap copy.
    """
    return os.environ.get("CLAUDE_CACHE_SNAPSHOT_DEFER") == "1"


# A tmp file this old belonged to a process that died mid-copy. Left in place
# it would bar the snapshot for the rest of the day, since the claim below is
# what every other process waits behind.
_SNAPSHOT_TMP_STALE_S = 3600.0

# Pages copied per step of the online backup, and the pause between steps.
# conn.backup() with no arguments copies the whole DB in one uninterrupted call
# holding a read lock; stepping it lets a writer in between batches. 1024 pages
# is 4 MB at the default page size, so even a large DB is a few dozen steps.
_SNAPSHOT_BACKUP_PAGES = 1024
_SNAPSHOT_BACKUP_SLEEP = 0.01


def _claim_snapshot_tmp(tmp: Path) -> bool:
    """Create *tmp* exclusively; True if this process won the right to copy.

    target.exists() alone does not serialise anything — it is checked before a
    copy that takes seconds, so every process that starts within that window
    runs a full copy of the DB and only the last rename wins (macsetup-3xzh).
    An exclusive create makes the losers cheap: they skip the copy entirely.
    """
    def _create() -> None:
        os.close(os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))

    try:
        _create()
        return True
    except FileExistsError:
        pass
    except OSError:
        return False
    try:
        if time.time() - tmp.stat().st_mtime < _SNAPSHOT_TMP_STALE_S:
            return False
        tmp.unlink()
        _create()
        return True
    except OSError:
        return False


def _maybe_snapshot(conn: sqlite3.Connection) -> tuple[Path | None, bool]:
    """Take today's snapshot if it doesn't already exist. Rotate old ones.

    Returns (path, fresh): the snapshot path on success (existing or newly
    written) or None if skipped or failed, and whether this call was the one
    that wrote it. `fresh` is true at most once a day, which is what the
    caller hangs the sanity check off. Failures never raise — snapshots are a
    safety net, not a prerequisite.
    """
    if os.environ.get("CLAUDE_CACHE_SNAPSHOT_DISABLE") == "1":
        return None, False
    snap_dir = _snapshot_dir()
    target = snap_dir / f"{_today_utc()}.db"
    if target.exists():
        return target, False
    tmp = target.with_suffix(target.suffix + ".tmp")
    try:
        snap_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None, False
    if not _claim_snapshot_tmp(tmp):
        return None, False
    try:
        dst = sqlite3.connect(str(tmp))
        try:
            conn.backup(
                dst,
                pages=_SNAPSHOT_BACKUP_PAGES,
                sleep=_SNAPSHOT_BACKUP_SLEEP,
            )
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
        return None, False
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
    return target, True


def _sanity_report(msg: str) -> None:
    """Raise under CLAUDE_CACHE_SANITY_ABORT=1, otherwise warn on stderr."""
    if os.environ.get("CLAUDE_CACHE_SANITY_ABORT") == "1":
        raise RuntimeError(msg)
    try:
        print(f"Warning: {msg}", file=sys.stderr)
    except OSError:
        pass


def _ccr_totals(conn: sqlite3.Connection) -> tuple[int, int]:
    """(row count, rows carrying a cost) for ccreport_records.

    The second number is what catches an over-broad `SET cost = NULL`: it
    leaves every row in place, so a row count alone reads as healthy.
    """
    return conn.execute(
        "SELECT COUNT(*), COUNT(cost) FROM ccreport_records"
    ).fetchone()


def _warn_on_drop(label: str, prev: int, cur: int, snapshot: Path) -> None:
    """Report a material drop in one aggregate against the prior snapshot.

    Requires a meaningful prior value before acting so a small dev DB doesn't
    raise false alarms.
    """
    if prev < _SANITY_MIN_PRIOR_COUNT:
        return
    drop_pct = 100.0 * (prev - cur) / prev
    if drop_pct < _SANITY_DROP_THRESHOLD_PCT:
        return
    _sanity_report(
        f"cache.db lost ccreport_records {label}: "
        f"{drop_pct:.1f}% drop ({prev} -> {cur}).\n"
        f"  Prior snapshot: {snapshot}\n"
        f"  Restore with:   cp '{snapshot}' '{DB_PATH}'"
    )


def _sanity_check(conn: sqlite3.Connection) -> None:
    """Warn if the irreplaceable ccreport data lost rows, costs, or parents.

    Row and cost totals are compared against the most recent snapshot from a
    day before today, so a same-run snapshot can't mask a wipe. Called from
    get_connection() on the run that writes the day's snapshot and on any run
    that migrated data; the referential check needs no snapshot and runs
    whenever this does.
    """
    if os.environ.get("CLAUDE_CACHE_SANITY_DISABLE") == "1":
        return
    # Records whose ccreport_files parent is gone are invisible to every
    # reader — all of them enter through that table — so they read as data
    # loss without being one row short of a count.
    parentless = conn.execute("PRAGMA foreign_key_check(ccreport_records)").fetchall()
    if parentless:
        _sanity_report(
            f"cache.db has {len(parentless)} ccreport_records rows with no "
            "ccreport_files parent; every reader joins through that table, "
            "so those records are unreachable."
        )
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
            prev_rows, prev_costs = _ccr_totals(src)
        finally:
            src.close()
    except sqlite3.Error:
        return
    cur_rows, cur_costs = _ccr_totals(conn)
    _warn_on_drop("rows", prev_rows, cur_rows, compare_snap)
    _warn_on_drop("costs", prev_costs, cur_costs, compare_snap)


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
    "sonnet_percent", "sonnet_reset",
    "scoped_percent", "scoped_model", "scoped_reset", "extra_percent", "extra_spent",
    "extra_limit", "extra_reset", "last_updated",
    "session_cost", "session_window_cost", "week_cost", "month_cost",
    # The rolling window columns come from pricing.ROLLING_WINDOWS, so adding a
    # window there reaches the cache without a second edit. Order is internal —
    # the SELECT, the INSERT and the row mapping all read this one list.
    *rolling_cost_keys(),
]

# The singleton row's column list, in the one order _usage_row_to_dict indexes
# by. Every statement that names these columns builds its text from here — the
# SELECT, the INSERT, and the ON CONFLICT update.
_USAGE_COLS = ["id", *_USAGE_FIELDS, "meta_json"]
_USAGE_SELECT_COLS = ", ".join(_USAGE_COLS)


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


def usage_is_fresh(d: dict[str, Any], max_age: int) -> bool:
    """Whether a usage row is fresh: not expired, and no window has shifted.

    A predicate over an already-read row rather than a query, so the statusline
    can ask it about the row it holds instead of re-reading.
    """
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
    d = read_usage_stale()
    if d is None or not usage_is_fresh(d, max_age):
        return None
    return d


def read_usage_stale() -> dict[str, Any] | None:
    """Read cached usage data regardless of freshness.

    The one place the singleton row is fetched: freshness is a predicate over
    the returned dict, not a second query, so a caller that wants both answers
    pays for one SELECT.
    """
    conn = get_connection()
    row = conn.execute(
        f"SELECT {_USAGE_SELECT_COLS} FROM usage WHERE id = 1"  # noqa: S608
    ).fetchone()
    if row is None:
        return None
    return _usage_row_to_dict(row)


# ---------------------------------------------------------------------------
# Fetch lock & error backoff
# ---------------------------------------------------------------------------

_BACKOFF_SCHEDULE = [45, 120, 240]  # seconds, indexed by consecutive failures
_LOCK_STALE_TIMEOUT = 30  # seconds before a held lock is considered abandoned


# UUID token per lock prefix, set while this process holds that lock.
_lock_owners: dict[str, str] = {}


_BACKOFF_KEYS = ("fetch_fail_count", "fetch_fail_time")


def _backoff_active(
    count_str: str | None, fail_time_str: str | None, now: float,
) -> bool:
    """Whether the recorded failures still bar a fetch at *now*.

    Split from the read so the lock path can decide from meta values it already
    fetched instead of querying the same two keys again.
    """
    if not count_str or not fail_time_str:
        return False
    try:
        count = int(count_str)
        elapsed = now - float(fail_time_str)
    except ValueError:
        return False
    if count <= 0:
        return False
    idx = min(count - 1, len(_BACKOFF_SCHEDULE) - 1)
    return elapsed < _BACKOFF_SCHEDULE[idx]


def _check_backoff_in_txn(conn: sqlite3.Connection, now: float) -> bool:
    """Whether we are inside the error backoff window.

    Reads only, so it is safe outside a transaction; the lock path calls it
    inside its BEGIN IMMEDIATE so a failure cannot be recorded between the
    backoff check and the lock write.
    """
    meta = _get_meta_many(conn, _BACKOFF_KEYS)
    return _backoff_active(meta.get(_BACKOFF_KEYS[0]), meta.get(_BACKOFF_KEYS[1]), now)


def _try_acquire_lock(prefix: str, *, check_backoff: bool) -> bool:
    """Atomically acquire the ``{prefix}_lock``. Returns True if acquired.

    Uses BEGIN IMMEDIATE to serialise concurrent writers so the
    read-check-write is atomic.  A lock older than _LOCK_STALE_TIMEOUT
    is treated as abandoned (e.g. crashed process), and so is one whose
    timestamp does not parse.

    An owner token (UUID) is stored alongside the lock so that only
    the process that acquired the lock can release it.

    A busy database past the connection timeout means another writer holds it,
    which is the same answer as a held lock — so BEGIN IMMEDIATE sits inside
    the try and OperationalError returns False. Callers run in the detached
    refresh subprocess, whose stderr is DEVNULL: raising here would silently
    abandon the refresh and leave costs stale (macsetup-39g2).

    Everything the decision needs is read in one statement and written in
    another: this runs inside BEGIN IMMEDIATE, so each extra round trip here is
    time every other writer on the machine spends blocked.
    """
    import uuid

    conn = get_connection()
    now = time.time()
    time_key = f"{prefix}_lock_time"
    owner_key = f"{prefix}_lock_owner"
    keys = (*_BACKOFF_KEYS, time_key) if check_backoff else (time_key,)
    try:
        conn.execute("BEGIN IMMEDIATE")
        meta = _get_meta_many(conn, keys)
        # Folded into the same transaction so a failure cannot be recorded
        # between the backoff check and the lock write.
        if check_backoff and _backoff_active(
            meta.get(_BACKOFF_KEYS[0]), meta.get(_BACKOFF_KEYS[1]), now,
        ):
            conn.execute("COMMIT")
            return False

        locked_at_str = meta.get(time_key)
        if locked_at_str:
            try:
                if now - float(locked_at_str) < _LOCK_STALE_TIMEOUT:
                    conn.execute("COMMIT")
                    return False
            except ValueError:
                print(f"Warning: corrupt {prefix}_lock_time {locked_at_str!r}, "
                      f"treating as stale", file=sys.stderr)
        owner = str(uuid.uuid4())
        conn.executemany(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
            ((time_key, str(now)), (owner_key, owner)),
        )
        conn.execute("COMMIT")
        _lock_owners[prefix] = owner
        return True
    except sqlite3.OperationalError:
        _rollback_if_open(conn)
        return False
    except Exception:
        _rollback_if_open(conn)
        raise


def _release_lock(prefix: str) -> None:
    """Release the ``{prefix}_lock`` only if this process owns it."""
    conn = get_connection()
    owner = _lock_owners.get(prefix)
    if owner is not None and _get_meta(conn, f"{prefix}_lock_owner") != owner:
        # Not our lock — another process took over after staleness timeout
        _lock_owners.pop(prefix, None)
        return
    conn.execute(
        "DELETE FROM meta WHERE key IN (?, ?)",
        (f"{prefix}_lock_time", f"{prefix}_lock_owner"),
    )
    conn.commit()
    _lock_owners.pop(prefix, None)


def try_acquire_fetch_lock() -> bool:
    """Acquire the API fetch lock, refusing while in error backoff."""
    return _try_acquire_lock("fetch", check_backoff=True)


def release_fetch_lock() -> None:
    """Release the fetch lock only if this process owns it."""
    _release_lock("fetch")


def try_acquire_costs_lock() -> bool:
    """Acquire the costs-only refresh lock. Returns True if acquired.

    Deliberately separate from the fetch lock: a cost recompute must never make
    a real API fetch fall into _wait_for_leader, where it would poll for a
    freshness bump that a costs-only run never makes. Also skips the API error
    backoff, which says nothing about whether local JSONL can be rescanned.
    """
    return _try_acquire_lock("costs", check_backoff=False)


def release_costs_lock() -> None:
    """Release the costs-only lock only if this process owns it."""
    _release_lock("costs")


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
    return _check_backoff_in_txn(get_connection(), time.time())


def is_fetch_blocked() -> bool:
    """Whether an active fetch lock or the error backoff bars a fetch now.

    One SELECT for all three keys — the statusline asks this on every render
    where the cached row has expired.
    """
    now = time.time()
    meta = _get_meta_many(get_connection(), (*_BACKOFF_KEYS, "fetch_lock_time"))
    if _backoff_active(meta.get(_BACKOFF_KEYS[0]), meta.get(_BACKOFF_KEYS[1]), now):
        return True
    locked_at_str = meta.get("fetch_lock_time")
    if locked_at_str:
        try:
            if now - float(locked_at_str) < _LOCK_STALE_TIMEOUT:
                return True
        except ValueError:
            pass
    return False


def write_usage_cache(data: dict[str, Any], *, snapshot_extra: bool = True) -> None:
    """Write usage data to the singleton usage row.

    Only the keys *data* actually carries are written; every other column keeps
    the value it had. The INSERT OR REPLACE this used to be deleted and
    re-inserted the row, so a caller whose cost computation had failed nulled
    all sixteen cost columns and the statusline rendered empty cost segments
    until the next successful run (macsetup-29bl). A caller that means "this
    reading no longer applies" — the API omitting a quota — has to say so with
    an explicit None.

    *snapshot_extra* is False for costs-only refreshes, which carry an
    extra_spent value copied from the existing row rather than a fresh reading.
    Re-snapshotting it would stamp a stale figure with a current timestamp and
    skew the per-window deltas.
    """
    conn = get_connection()
    # Separate structured fields from extra blobs
    extra: dict[str, Any] = {}
    for k in ("_meta", "_cleaned_session", "_cleaned"):
        if k in data:
            extra[k] = data[k]

    present = [f for f in _USAGE_FIELDS if f in data]
    vals: list[Any] = [data[f] for f in present]
    if extra:
        present.append("meta_json")
        vals.append(json.dumps(extra))

    cols = ", ".join(["id", *present])
    placeholders = ", ".join(["?"] * (len(present) + 1))
    # A write naming nothing still has to be a legal upsert; it just keeps the
    # row exactly as it was.
    updates = ", ".join(f"{c} = excluded.{c}" for c in present) or "id = id"
    conn.execute(
        f"INSERT INTO usage ({cols}) VALUES ({placeholders}) "  # noqa: S608
        f"ON CONFLICT(id) DO UPDATE SET {updates}",
        [1, *vals],
    )

    # Record extra_spent snapshot for per-window delta tracking
    es = data.get("extra_spent") if snapshot_extra else None
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

    # Also load dedup_keys per file. file_path leads the primary key, so the
    # ORDER BY is the storage order and costs nothing — it just lets groupby
    # cut each file's list in one slice instead of a setdefault per key, and
    # this table carries a row per assistant message inside the retention
    # window. Files pruned by bulk_save_file_costs are simply absent.
    dk_map = {
        path: [dk for _p, dk in group]
        for path, group in groupby(
            conn.execute("SELECT file_path, dk FROM dedup_keys ORDER BY file_path"),
            key=itemgetter(0),
        )
    }

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



def _delete_departed_paths(conn: sqlite3.Connection, live: set[str]) -> None:
    """Drop file_costs rows whose path is not in *live*, cascading dedup_keys.

    The difference is taken in Python against one indexed read of the path
    column rather than as `path NOT IN (?, ?, …)` over thousands of live
    paths. Files depart rarely, so the usual run issues no DELETE at all.
    """
    existing = {r[0] for r in conn.execute("SELECT path FROM file_costs")}
    for chunk in _param_chunks(existing - live):
        placeholders = ",".join("?" * len(chunk))
        conn.execute(f"DELETE FROM file_costs WHERE path IN ({placeholders})", chunk)


def bulk_save_file_costs(
    entries: dict[str, dict[str, Any]],
    week_key: str,
    month_key: str,
    changed: set[str] | None = None,
    dedup_cutoff_ns: int | None = None,
) -> None:
    """Persist *entries* as the whole file_costs + dedup_keys dataset.

    *changed* names the paths whose entry actually differs from what is
    stored; the rest are written straight back unmodified, so they are
    skipped. Passing None means "assume everything changed".

    *dedup_cutoff_ns* is the oldest mtime whose dedup keys are still worth
    storing — the start of the widest window whose totals those keys can
    change. Keys for files older than it are neither written nor kept, which
    bounds a table that otherwise grows by a row per assistant message and is
    never pruned (macsetup-1jvz). The accepted risk: dedup is
    first-occurrence-wins across files, so a message id shared between a fresh
    file and one that aged out is counted twice in all_time. Claude Code writes
    a message id once, into one session file; the collision needs a copied or
    resumed transcript *and* a month between the two copies. Passing None keeps
    every key.

    Rewriting untouched rows is not merely wasted work: DELETE on a
    file_costs row cascades to its dedup_keys, so the old delete-and-rebuild
    churned one row per assistant message corpus-wide every time a single
    JSONL grew by a line (macsetup-5vsf). ON CONFLICT keeps the parent row
    alive, so unchanged files' dedup keys are never touched.

    A path present in *entries* but absent from both *changed* and the table
    would be dropped — compute_costs cannot produce one, since an entry it
    reuses unchanged came from the table in the first place.
    """
    conn = get_connection()
    to_write = (
        entries if changed is None
        else {p: e for p, e in entries.items() if p in changed}
    )
    conn.execute("BEGIN IMMEDIATE")
    try:
        _set_meta(conn, "cost_week", week_key)
        _set_meta(conn, "cost_month", month_key)

        _delete_departed_paths(conn, set(entries))

        if to_write:
            conn.executemany(
                "INSERT INTO file_costs "
                "(path, mtime_ns, size, week_cost, month_cost, all_time_cost, session_cost) "
                "VALUES (?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(path) DO UPDATE SET "
                "mtime_ns = excluded.mtime_ns, size = excluded.size, "
                "week_cost = excluded.week_cost, month_cost = excluded.month_cost, "
                "all_time_cost = excluded.all_time_cost, "
                "session_cost = excluded.session_cost",
                [
                    (
                        path,
                        entry["mtime_ns"],
                        entry["size"],
                        entry.get("week_cost", 0),
                        entry.get("month_cost", 0),
                        entry.get("all_time_cost", 0),
                        entry.get("session_cost"),
                    )
                    for path, entry in to_write.items()
                ],
            )
            # Replaced wholesale per rewritten file: a re-parse can drop keys
            # as well as add them, and INSERT OR IGNORE alone never removes.
            conn.executemany(
                "DELETE FROM dedup_keys WHERE file_path = ?",
                [(p,) for p in to_write],
            )
            dk_rows = [
                (dk, path)
                for path, entry in to_write.items()
                if dedup_cutoff_ns is None or entry["mtime_ns"] >= dedup_cutoff_ns
                for dk in entry.get("dedup_keys", [])
            ]
            if dk_rows:
                conn.executemany(
                    "INSERT OR IGNORE INTO dedup_keys (dk, file_path) VALUES (?, ?)",
                    dk_rows,
                )
        if dedup_cutoff_ns is not None:
            # Files aged out since the last save, whose keys were written back
            # when they were still in window. One statement: the subquery picks
            # the paths and each delete is a primary-key range scan.
            conn.execute(
                "DELETE FROM dedup_keys WHERE file_path IN "
                "(SELECT path FROM file_costs WHERE mtime_ns < ?)",
                (dedup_cutoff_ns,),
            )
        conn.execute("COMMIT")
    except Exception:
        _rollback_if_open(conn)
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


def accumulate_cache_stats(
    session_id: str,
    total_in_tokens: int,
    fresh_delta: int,
    create_delta: int,
    read_delta: int,
) -> tuple[int, int, int]:
    """Add one message's token counts to a session's totals.

    Returns the totals after the write: (cum_fresh, cum_create, cum_read).

    The addition happens in the statement, not in the caller. Read-modify-write
    across two statements loses an increment whenever two renders of the same
    session interleave — both read the old total, both write old+delta.

    *total_in_tokens* is the change key rather than a delta: an unchanged value
    means the same API response we already counted, so the upsert's WHERE makes
    that render a no-op and the stored totals are reported back unchanged.
    """
    conn = get_connection()
    row = conn.execute(
        "INSERT INTO cache_stats "
        "(session_id, total_in_tokens, cum_fresh, cum_cache_create, cum_cache_read) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(session_id) DO UPDATE SET "
        "total_in_tokens = excluded.total_in_tokens, "
        "cum_fresh = cache_stats.cum_fresh + excluded.cum_fresh, "
        "cum_cache_create = cache_stats.cum_cache_create + excluded.cum_cache_create, "
        "cum_cache_read = cache_stats.cum_cache_read + excluded.cum_cache_read "
        "WHERE cache_stats.total_in_tokens IS NOT excluded.total_in_tokens "
        "RETURNING cum_fresh, cum_cache_create, cum_cache_read",
        (session_id, total_in_tokens, fresh_delta, create_delta, read_delta),
    ).fetchone()
    conn.commit()
    if row is not None:
        return (row[0], row[1], row[2])
    # Suppressed by the change key — no row was written, so report the stored
    # totals. A row that vanished between the two statements reads as zeros.
    stored = read_cache_stats(session_id)
    return (stored[1], stored[2], stored[3]) if stored else (0, 0, 0)


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
CACHE_SCHEMA_SALT = "3"


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


def _ccreport_readable(conn: sqlite3.Connection) -> bool:
    """Whether the stored ccreport rows are in the format this build reads.

    The salt is the only third of check_ccreport_valid a passive reader can
    evaluate: version and script_hash are ccreport.py's own parse contract, and
    the statusline knows neither. The salt is the narrower claim that matters
    here anyway — that the columns mean what _ccr_row_to_dict assumes.

    Every loader below returns an empty result when this is False, and none of
    them repairs anything. Invalidation is the writer's job (ccreport's
    _ensure_cache_valid, which re-parses what it clears); a statusline render
    that took it upon itself to NULL costs would destroy exactly the orphan
    records no re-parse can rebuild. Degrading to "no cached records" costs the
    render its orphan costs until the next ccreport run and nothing more.
    """
    return _get_meta(conn, "ccreport_schema_salt") == CACHE_SCHEMA_SALT


def invalidate_ccreport(live_paths: set[str]) -> None:
    """Invalidate the ccreport cache for *live_paths*, forcing their re-parse.

    Both writes are scoped to files still on disk. Orphaned records — those
    whose JSONL Claude Code has already purged — keep their fingerprints and
    their costs, because a purged file's `cost` came from costUSD in a source
    that no longer exists: NULLing it is permanent loss, not a placeholder
    the next parse refills (macsetup-qn0k, macsetup-4flx).
    """
    conn = get_connection()
    for chunk in _param_chunks(live_paths):
        placeholders = ",".join("?" * len(chunk))
        # Reset fingerprints so live files fail the mtime/size check and get
        # re-parsed, and NULL their costs so they recompute with current
        # pricing — the re-parse restores whatever the JSONL actually said.
        conn.execute(
            f"UPDATE ccreport_files SET mtime_ns = 0, size = 0 "
            f"WHERE path IN ({placeholders})",
            chunk,
        )
        conn.execute(
            f"UPDATE ccreport_records SET cost = NULL "
            f"WHERE file_path IN ({placeholders})",
            chunk,
        )
    conn.execute("DELETE FROM meta WHERE key IN ('ccreport_version', 'ccreport_script_hash', 'ccreport_schema_salt')")
    conn.commit()


def init_ccreport_meta(version: int, script_hash: str) -> None:
    """Set version, script_hash, and schema salt in meta table."""
    conn = get_connection()
    _set_meta(conn, "ccreport_version", str(version))
    _set_meta(conn, "ccreport_script_hash", script_hash)
    _set_meta(conn, "ccreport_schema_salt", CACHE_SCHEMA_SALT)
    conn.commit()


# The record columns every ccreport reader selects and every writer inserts.
# One list, because a column added to any of them and forgotten in the others
# is a silent format drift the salt can't catch. The SELECT text, the INSERT
# text, the placeholder count, the value tuple and the row mapping below are
# all derived from it; a new column means editing this and the CREATE TABLE.
#
# The four token counts trail the rest because a record dict keeps them in one
# compact "t" list instead of under their own keys — every other column is read
# straight off the dict by column name.
_CCR_FIELD_COLS = (
    "mid", "model", "ts", "sid", "project", "cwd", "repo", "dk", "cost",
)
_CCR_TOKEN_COLS = ("input_tokens", "output_tokens", "cache_create", "cache_read")
_CCR_COLS = (*_CCR_FIELD_COLS, *_CCR_TOKEN_COLS)

# What the readers interpolate. bulk_load_ccreport_cache and the scoped loaders
# prepend file_path and strip it off the row before mapping.
_CCR_SELECT = ", ".join(_CCR_COLS)
_CCR_INSERT_COLS = ", ".join(("file_path", *_CCR_COLS))
_CCR_INSERT_PLACEHOLDERS = ", ".join("?" * (len(_CCR_COLS) + 1))


def _ccr_row_to_dict(row: tuple) -> dict:
    """One ccreport_records row in the compact format ccreport.py reads."""
    vals = dict(zip(_CCR_COLS, row, strict=True))
    rec: dict = {name: vals[name] for name in _CCR_FIELD_COLS}
    rec["t"] = [vals[name] for name in _CCR_TOKEN_COLS]
    return rec


def _ccr_record_to_row(path: str, rec: dict) -> tuple:
    """A record dict as an insert row for _CCR_INSERT_COLS."""
    return (
        path,
        *(rec.get(name) for name in _CCR_FIELD_COLS),
        *rec["t"][:len(_CCR_TOKEN_COLS)],
    )


def _group_by_file(rows: list[tuple]) -> dict[str, list[dict]]:
    """Rows of (file_path, *_CCR_COLS) as {path: [record dict]}, order kept."""
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row[0], []).append(_ccr_row_to_dict(row[1:]))
    return grouped


def prefix_range(prefix: str) -> tuple[str, str]:
    """Half-open [lo, hi) bounds selecting exactly the strings starting *prefix*.

    hi is *prefix* with its last character stepped up one code point, which is
    the first string that sorts past every extension of *prefix*. Used instead
    of LIKE or a Python startswith so the range rides the index on file_path —
    and unlike a `>= prefix` scan it stops at the end of the directory rather
    than running to the end of the table.
    """
    if not prefix:
        raise ValueError("prefix_range needs a non-empty prefix")
    return prefix, prefix[:-1] + chr(ord(prefix[-1]) + 1)


def load_ccreport_records_under(prefix: str) -> dict[str, list[dict]]:
    """Cached records whose file path starts with *prefix*, as {path: [record]}.

    The statusline renders one project at a time and threw away everything else
    bulk_load_ccreport_cache handed it — the whole table, on every render
    (macsetup-45iv). Deliberately unbounded in time: the caller's all_time total
    needs every record the prefix covers.

    Empty when the cached rows are not in this build's format; see
    _ccreport_readable.
    """
    conn = get_connection()
    if not _ccreport_readable(conn):
        return {}
    lo, hi = prefix_range(prefix)
    return _group_by_file(conn.execute(
        f"SELECT file_path, {_CCR_SELECT} FROM ccreport_records "
        f"WHERE file_path >= ? AND file_path < ?",
        (lo, hi),
    ).fetchall())


def load_ccreport_records_for_session(session_id: str) -> dict[str, list[dict]]:
    """Cached records for one session id, as {path: [record]}.

    Answers the purged-JSONL fallback in compute_session_cost, which used to
    load the table and drop every row with a different sid in Python. Callers
    still narrow by project prefix themselves — a session id is near-unique, so
    the index on sid does the elimination that matters.

    Empty when the cached rows are not in this build's format; see
    _ccreport_readable.
    """
    conn = get_connection()
    if not _ccreport_readable(conn):
        return {}
    return _group_by_file(conn.execute(
        f"SELECT file_path, {_CCR_SELECT} FROM ccreport_records WHERE sid = ?",
        (session_id,),
    ).fetchall())


def bulk_load_ccreport_cache() -> tuple[dict[str, tuple[int, int]], dict[str, list[dict]]]:
    """Bulk-load all ccreport file metadata and records.

    Returns (file_meta, records_by_file) where:
      file_meta: {path: (mtime_ns, size)}
      records_by_file: {path: [list of record dicts]}

    Both halves come back empty when the cached rows are not in this build's
    format; see _ccreport_readable. Prefer a scoped loader above when the
    caller only wants one project or one session — this reads every row.
    """
    conn = get_connection()
    if not _ccreport_readable(conn):
        return {}, {}
    # File metadata
    file_rows = conn.execute("SELECT path, mtime_ns, size FROM ccreport_files").fetchall()
    file_meta = {r[0]: (r[1], r[2]) for r in file_rows}
    if not file_meta:
        return {}, {}
    # All records
    rec_rows = conn.execute(
        f"SELECT file_path, {_CCR_SELECT} FROM ccreport_records"
    ).fetchall()
    return file_meta, _group_by_file(rec_rows)


def load_ccreport_file_identities() -> list[tuple[str, str | None, str | None, str]]:
    """(file_path, repo, cwd, project) for every cached file, one row each.

    Answers "which files belong to the same project as this one" without
    dragging the records back: parse_jsonl_file stamps one identity onto every
    record in a file, so the bare columns a GROUP BY file_path picks are the
    file's identity whichever row SQLite lands on. Grouping rides
    idx_ccr_file_ts, so this reads the index rather than sorting the table.

    Only pricing's project scoping calls it, and only when merge rules exist —
    without them a project is its own directory and no lookup is needed.

    Empty when the cached rows are not in this build's format; see
    _ccreport_readable.
    """
    conn = get_connection()
    if not _ccreport_readable(conn):
        return []
    return [
        (row[0], row[1], row[2], row[3] or "")
        for row in conn.execute(
            "SELECT file_path, repo, cwd, project FROM ccreport_records "
            "GROUP BY file_path"
        ).fetchall()
    ]


def save_ccreport_files(entries: list[tuple[str, int, int, list[dict]]]) -> None:
    """Save/replace several (path, mtime_ns, size, records) entries at once.

    One transaction for the whole batch. A full rebuild re-parses every file
    in the corpus, and committing per file made that thousands of WAL
    write-lock cycles, each able to stall a rendering statusline for up to the
    busy timeout (macsetup-92y0). Callers batch in chunks so no single
    transaction spans a long stretch of parsing.

    Atomic per call: a crash leaves each file in the batch either fully
    cached or fully stale, never half its records.
    """
    if not entries:
        return
    conn = get_connection()
    conn.execute("BEGIN IMMEDIATE")
    try:
        # Deleting the parent cascades its old records away.
        conn.executemany(
            "DELETE FROM ccreport_files WHERE path = ?",
            [(path,) for path, _m, _s, _r in entries],
        )
        conn.executemany(
            "INSERT INTO ccreport_files (path, mtime_ns, size) VALUES (?, ?, ?)",
            [(path, mtime_ns, size) for path, mtime_ns, size, _r in entries],
        )
        rows = [
            _ccr_record_to_row(path, r)
            for path, _m, _s, records in entries
            for r in records
        ]
        if rows:
            conn.executemany(
                f"INSERT INTO ccreport_records ({_CCR_INSERT_COLS}) "  # noqa: S608
                f"VALUES ({_CCR_INSERT_PLACEHOLDERS})",
                rows,
            )
        conn.execute("COMMIT")
    except Exception:
        _rollback_if_open(conn)
        raise


def save_ccreport_file(
    path: str, mtime_ns: int, size: int, records: list[dict],
) -> None:
    """Save/replace a single file entry and all its records."""
    save_ccreport_files([(path, mtime_ns, size, records)])


def count_ccreport_records_without_signals() -> int:
    """Count records carrying neither cwd nor repo — reachable only by name.

    Both columns were added after the fact and never backfilled, so rows
    written before that keep them NULL forever. ccreport warns on this count
    when a remote or cwd_prefix rule is added, since those rules match on the
    two columns these rows do not have (macsetup-623j).
    """
    conn = get_connection()
    return conn.execute(
        "SELECT COUNT(*) FROM ccreport_records WHERE cwd IS NULL AND repo IS NULL"
    ).fetchone()[0]


# ---------------------------------------------------------------------------
# Project overrides (manual grouping rules)
# ---------------------------------------------------------------------------

def get_project_overrides() -> list[dict]:
    """Return all override rules, lowest id first (insertion order = priority)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, match_kind, match_value, target FROM project_overrides ORDER BY id"
    ).fetchall()
    return [
        {"id": r[0], "match_kind": r[1], "match_value": r[2], "target": r[3]}
        for r in rows
    ]


def add_project_override(match_kind: str, match_value: str, target: str) -> None:
    """Insert or replace a rule. (match_kind, match_value) is unique."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO project_overrides (match_kind, match_value, target) "
        "VALUES (?, ?, ?) "
        "ON CONFLICT (match_kind, match_value) DO UPDATE SET target = excluded.target",
        (match_kind, match_value, target),
    )
    conn.commit()


def delete_project_override(match_value: str, match_kind: str | None = None) -> int:
    """Delete rules matching a value (optionally scoped to a kind). Returns count."""
    conn = get_connection()
    if match_kind:
        cur = conn.execute(
            "DELETE FROM project_overrides WHERE match_value = ? AND match_kind = ?",
            (match_value, match_kind),
        )
    else:
        cur = conn.execute(
            "DELETE FROM project_overrides WHERE match_value = ?", (match_value,)
        )
    conn.commit()
    return cur.rowcount


# ---------------------------------------------------------------------------
# Cost summary cache (written by compute_costs, read by statusline)
# ---------------------------------------------------------------------------

def _cost_summary_suffix(cwd: str | None) -> str:
    """Project scope for the cost-summary keys. The writer and the reader must
    agree exactly: a divergence here is a permanent silent cache miss, not an
    error, so both read it from here."""
    return f":{project_key(cwd)}" if cwd else ""


def write_cost_summary(costs: dict[str, Any], cwd: str | None = None) -> None:
    """Cache the latest compute_costs() result for fast statusline reads.

    Scoped by project (cwd) to prevent cross-contamination between terminals.
    """
    conn = get_connection()
    suffix = _cost_summary_suffix(cwd)
    _set_meta(conn, f"cost_summary{suffix}", json.dumps(costs))
    _set_meta(conn, f"cost_summary_time{suffix}", str(time.time()))
    conn.commit()


def read_cost_summary(max_age: int = 600, cwd: str | None = None) -> dict[str, Any] | None:
    """Read cached cost summary if fresh enough, scoped by project.

    Both keys are known up front, so they come back in one statement — the
    statusline is on the other end of this and reads it on every render.
    """
    suffix = _cost_summary_suffix(cwd)
    time_key = f"cost_summary_time{suffix}"
    data_key = f"cost_summary{suffix}"
    meta = _get_meta_many(get_connection(), (time_key, data_key))
    ts_str = meta.get(time_key)
    if not ts_str:
        return None
    try:
        if time.time() - float(ts_str) > max_age:
            return None
    except ValueError:
        return None
    raw = meta.get(data_key)
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


def _get_meta_many(
    conn: sqlite3.Connection, keys: tuple[str, ...],
) -> dict[str, str]:
    """Fetch several meta keys in one statement. Absent keys are simply missing.

    Callers that need a fixed set of keys — the lock path inside BEGIN
    IMMEDIATE, the statusline on every render — pay one round trip instead of
    one per key.
    """
    if not keys:
        return {}
    placeholders = ", ".join("?" * len(keys))
    rows = conn.execute(
        f"SELECT key, value FROM meta WHERE key IN ({placeholders})",  # noqa: S608
        tuple(keys),
    ).fetchall()
    return {k: v for k, v in rows}


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, value)
    )


# ---------------------------------------------------------------------------
# Exchange rates (Norges Bank USD/NOK daily spot, used by exchange.py)
# ---------------------------------------------------------------------------

def get_exchange_rates(since_date: str) -> dict[str, float]:
    """Cached rates from *since_date* (ISO ``YYYY-MM-DD``) on, as {date: rate}.

    The table gains a row per calendar day and is never pruned, so the caller
    passes the oldest date its lookups can still reach rather than reading the
    lot. `date` is the WITHOUT ROWID primary key, making the range a covering
    scan of just that slice.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT date, rate FROM exchange_rates WHERE date >= ?", (since_date,)
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def save_exchange_rates(rates: dict[str, float]) -> None:
    """Upsert {ISO date: rate} into the rate cache.

    Callers must validate before calling: a date present here is never
    re-fetched, so a stored rate is permanent.
    """
    if not rates:
        return
    conn = get_connection()
    conn.executemany(
        "INSERT OR REPLACE INTO exchange_rates (date, rate) VALUES (?, ?)",
        rates.items(),
    )
    conn.commit()
