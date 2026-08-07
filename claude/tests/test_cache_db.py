"""Tests for cache_db.py — schema migration, locks, backoff, ccreport rows.

Every test runs against a throwaway DB; nothing here touches the real cache.
"""

from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import pytest

import cache_db
from cache_db import (
    _CCR_COLS,
    bulk_load_ccreport_cache,
    bulk_save_file_costs,
    check_fetch_backoff,
    clear_fetch_failures,
    invalidate_ccreport,
    load_cost_cache,
    record_fetch_failure,
    release_costs_lock,
    release_fetch_lock,
    save_ccreport_file,
    save_ccreport_files,
    try_acquire_costs_lock,
    try_acquire_fetch_lock,
)
from pricing import rolling_cost_keys

# A DB as it looked before the added columns existed, to migrate forward.
_PRE_MIGRATION_SQL = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE usage (id INTEGER PRIMARY KEY CHECK (id = 1), session_percent INTEGER);
CREATE TABLE ccreport_files (
    path TEXT PRIMARY KEY, mtime_ns INTEGER NOT NULL, size INTEGER NOT NULL);
CREATE TABLE ccreport_records (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL REFERENCES ccreport_files(path) ON DELETE CASCADE,
    mid TEXT, model TEXT NOT NULL, ts REAL NOT NULL, sid TEXT NOT NULL,
    project TEXT NOT NULL, dk TEXT, cost REAL,
    input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
    cache_create INTEGER NOT NULL, cache_read INTEGER NOT NULL);
"""


@pytest.fixture
def db(tmp_path, monkeypatch):
    """A connection to an empty DB at a temp path, with snapshots disabled.

    The ccreport schema salt is stamped up front because every ccreport reader
    refuses to return rows without it, and in production ccreport stamps it
    before it writes its first record. Tests about the missing/mismatched salt
    overwrite it themselves.
    """
    monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DISABLE", "1")
    monkeypatch.setattr(cache_db, "DB_PATH", tmp_path / "cache.db")
    monkeypatch.setattr(cache_db, "_conn", None)
    monkeypatch.setattr(cache_db, "_lock_owners", {})
    conn = cache_db.get_connection()
    cache_db.init_ccreport_meta(1, "test-hash")
    yield conn
    conn.close()
    cache_db._conn = None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _count_commits(conn: sqlite3.Connection):
    """Install a trace callback; the returned fn reports COMMITs since then.

    Both the explicit `COMMIT` statements and the ones `conn.commit()` issues
    reach the trace callback, so this counts whole write transactions.
    """
    return _count_statements(conn, "COMMIT")


def _count_statements(conn: sqlite3.Connection, fragment: str):
    """Install a trace callback counting statements containing *fragment*.

    The callback fires once per row of an executemany, so this measures rows
    written, not calls made.
    """
    seen: list[str] = []
    conn.set_trace_callback(seen.append)
    return lambda: sum(1 for s in seen if fragment in s)


class _FailingCommit:
    """A connection whose COMMIT ends the transaction and then fails.

    Reproduces the case that made an unconditional ROLLBACK in the handler
    raise "cannot rollback" over the real error (macsetup-39g2).
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, sql, *args):
        if sql.strip().upper().startswith("COMMIT"):
            self._conn.execute("ROLLBACK")
            raise sqlite3.OperationalError("disk I/O error")
        return self._conn.execute(sql, *args)

    def __getattr__(self, name):
        return getattr(self._conn, name)


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }


_INSERT_RECORD = (
    "INSERT INTO ccreport_records "
    "(file_path, mid, model, ts, sid, project, cost, "
    " input_tokens, output_tokens, cache_create, cache_read) "
    "VALUES (?, ?, ?, ?, 's1', 'proj', ?, 0, 0, 0, 0)"
)


def _seed_ccreport(conn, rows, *, path="/tmp/proj/a.jsonl") -> None:
    """Insert (mid, model, ts, cost) rows under one ccreport_files parent."""
    conn.execute(
        "INSERT OR REPLACE INTO ccreport_files (path, mtime_ns, size) VALUES (?, 1, 1)",
        (path,),
    )
    conn.executemany(_INSERT_RECORD, [(path, *r) for r in rows])
    conn.commit()


class TestSchemaColumns:
    def test_new_db_has_every_added_column(self, db):
        for table, col, _type in cache_db._ADDED_COLUMNS:
            assert col in _columns(db, table), f"{table}.{col}"

    def test_pre_migration_db_is_brought_forward(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DISABLE", "1")
        # Migrations run here, which runs the sanity check — point it at an
        # empty dir so it can't compare against this machine's real snapshots.
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DIR", str(tmp_path / "snaps"))
        path = tmp_path / "old.db"
        old = sqlite3.connect(path)
        old.executescript(_PRE_MIGRATION_SQL)
        old.commit()
        old.close()

        monkeypatch.setattr(cache_db, "DB_PATH", path)
        monkeypatch.setattr(cache_db, "_conn", None)
        conn = cache_db.get_connection()
        try:
            assert set(rolling_cost_keys()) <= _columns(conn, "usage")
            assert {"scoped_percent", "scoped_model", "scoped_reset"} <= _columns(
                conn, "usage")
            assert {"cwd", "repo"} <= _columns(conn, "ccreport_records")
        finally:
            conn.close()
            cache_db._conn = None


class TestSchemaVersionGate:
    """PRAGMA user_version gates the bootstrap every process pays on first touch.

    These lean on the autouse isolate_cache_db fixture for DB_PATH; reopening
    the same file with _conn cleared is what a second process sees.
    """

    @staticmethod
    def _reopen() -> sqlite3.Connection:
        cache_db.close_connection()
        return cache_db.get_connection()

    def test_the_first_open_stamps_the_current_version(self):
        conn = cache_db.get_connection()
        assert cache_db._user_version(conn) == cache_db.SCHEMA_VERSION

    def test_a_stamped_db_skips_the_schema_script(self):
        conn = cache_db.get_connection()
        conn.execute("DROP TABLE exchange_rates")
        conn = self._reopen()
        assert "exchange_rates" not in _tables(conn)

    def test_a_stamped_db_skips_the_alters_and_the_migrations(self, monkeypatch):
        cache_db.get_connection()
        calls: list[str] = []
        monkeypatch.setattr(cache_db, "_add_column", lambda *a: calls.append("alter"))
        monkeypatch.setattr(cache_db, "_run_migrations", lambda c: calls.append("migrate"))
        self._reopen()
        assert calls == []

    def test_a_stale_version_takes_the_slow_path_once(self, monkeypatch):
        conn = cache_db.get_connection()
        conn.execute("DROP TABLE exchange_rates")
        conn.execute(f"PRAGMA user_version = {cache_db.SCHEMA_VERSION - 1}")
        conn = self._reopen()
        assert "exchange_rates" in _tables(conn), "the bump re-ran the schema script"
        assert cache_db._user_version(conn) == cache_db.SCHEMA_VERSION
        calls: list[str] = []
        monkeypatch.setattr(cache_db, "_run_migrations", lambda c: calls.append("migrate"))
        self._reopen()
        assert calls == [], "and the DB is back on the fast path"


class TestBootstrapFailure:
    """A bootstrap that raises must not leave a usable-looking singleton."""

    def test_a_failure_leaves_no_connection_and_the_next_call_retries(self, monkeypatch):
        attempts: list[sqlite3.Connection] = []

        def flaky(conn):
            attempts.append(conn)
            if len(attempts) == 1:
                raise RuntimeError("migration blew up")
            return False

        monkeypatch.setattr(cache_db, "_run_migrations", flaky)
        with pytest.raises(RuntimeError, match="migration blew up"):
            cache_db.get_connection()
        assert cache_db._conn is None
        conn = cache_db.get_connection()
        assert len(attempts) == 2
        assert conn.execute("SELECT 1").fetchone() == (1,)

    def test_the_half_built_connection_is_closed(self, monkeypatch):
        attempts: list[sqlite3.Connection] = []

        def boom(conn):
            attempts.append(conn)
            raise RuntimeError("migration blew up")

        monkeypatch.setattr(cache_db, "_run_migrations", boom)
        with pytest.raises(RuntimeError):
            cache_db.get_connection()
        with pytest.raises(sqlite3.ProgrammingError):
            attempts[0].execute("SELECT 1")

    def test_a_failed_bootstrap_does_not_stamp_the_version(self, monkeypatch):
        def boom(conn):
            raise RuntimeError("migration blew up")

        monkeypatch.setattr(cache_db, "_run_migrations", boom)
        with pytest.raises(RuntimeError):
            cache_db.get_connection()
        # An unstamped DB is what puts the next process back on the slow path.
        stale = sqlite3.connect(cache_db.DB_PATH)
        try:
            assert stale.execute("PRAGMA user_version").fetchone()[0] == 0
        finally:
            stale.close()


class _FailingRename:
    """A connection whose RENAME COLUMN fails the way a contended cache.db does."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, sql, *args):
        if "RENAME COLUMN" in sql:
            raise sqlite3.OperationalError("database is locked")
        return self._conn.execute(sql, *args)

    def __getattr__(self, name):
        return getattr(self._conn, name)


class TestRenameFingerprintMigration:
    """Migration 3 must never mark itself done over a table it did not rename."""

    _EARLIER_FLAGS = [
        "migrated_flat_pricing_2026_03_13",
        "migrated_flat_pricing_ccreport",
        "migrated_flat_pricing_ccreport_variants",
    ]
    _LEGACY = "CREATE TABLE session_costs (session_id TEXT PRIMARY KEY, file_size INTEGER)"

    def _db(self, tmp_path, session_costs_sql: str | None) -> sqlite3.Connection:
        """A DB where migration 3 is the only one with work left to do."""
        conn = sqlite3.connect(tmp_path / "m3.db")
        conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        if session_costs_sql:
            conn.execute(session_costs_sql)
        conn.executemany(
            "INSERT INTO meta (key, value) VALUES (?, '1')",
            [(k,) for k in self._EARLIER_FLAGS],
        )
        conn.commit()
        return conn

    @staticmethod
    def _flag(conn) -> str | None:
        return cache_db._get_meta(conn, "migrated_rename_fingerprint")

    def test_a_legacy_file_size_column_is_renamed(self, tmp_path):
        conn = self._db(tmp_path, self._LEGACY)
        assert cache_db._run_migrations(conn) is True
        assert "fingerprint" in cache_db._table_columns(conn, "session_costs")
        assert self._flag(conn) == "1"

    def test_an_already_renamed_column_still_sets_the_flag(self, tmp_path):
        conn = self._db(
            tmp_path,
            "CREATE TABLE session_costs (session_id TEXT PRIMARY KEY, fingerprint INTEGER)",
        )
        assert cache_db._run_migrations(conn) is True
        assert self._flag(conn) == "1"

    def test_a_table_with_neither_column_leaves_the_flag_unset(self, tmp_path):
        conn = self._db(
            tmp_path, "CREATE TABLE session_costs (session_id TEXT PRIMARY KEY)")
        with pytest.raises(sqlite3.OperationalError, match="no fingerprint column"):
            cache_db._run_migrations(conn)
        assert self._flag(conn) is None

    def test_a_missing_table_propagates_instead_of_being_swallowed(self, tmp_path):
        conn = self._db(tmp_path, None)
        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            cache_db._run_migrations(conn)
        assert self._flag(conn) is None

    def test_a_locked_db_is_retried_rather_than_marked_done(self, tmp_path):
        conn = self._db(tmp_path, self._LEGACY)
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            cache_db._run_migrations(_FailingRename(conn))
        assert self._flag(conn) is None
        assert cache_db._run_migrations(conn) is True
        assert "fingerprint" in cache_db._table_columns(conn, "session_costs")
        assert self._flag(conn) == "1"


class TestLocks:
    def test_held_lock_blocks_a_second_acquire(self, db):
        assert try_acquire_fetch_lock() is True
        assert try_acquire_fetch_lock() is False
        release_fetch_lock()
        assert try_acquire_fetch_lock() is True

    def test_release_clears_both_meta_keys(self, db):
        try_acquire_fetch_lock()
        release_fetch_lock()
        assert cache_db._get_meta(db, "fetch_lock_time") is None
        assert cache_db._get_meta(db, "fetch_lock_owner") is None

    def test_the_two_locks_are_independent(self, db):
        assert try_acquire_fetch_lock() is True
        assert try_acquire_costs_lock() is True
        release_costs_lock()
        assert cache_db._get_meta(db, "fetch_lock_time") is not None

    @pytest.mark.parametrize(
        ("prefix", "acquire"),
        [("fetch", try_acquire_fetch_lock), ("costs", try_acquire_costs_lock)],
    )
    def test_corrupt_timestamp_is_stale_on_both_locks(self, db, prefix, acquire):
        cache_db._set_meta(db, f"{prefix}_lock_time", "not-a-number")
        db.commit()
        assert acquire() is True

    def test_release_leaves_a_lock_another_process_took(self, db):
        try_acquire_fetch_lock()
        cache_db._set_meta(db, "fetch_lock_owner", "someone-else")
        db.commit()
        release_fetch_lock()
        assert cache_db._get_meta(db, "fetch_lock_owner") == "someone-else"
        assert cache_db._get_meta(db, "fetch_lock_time") is not None

    def test_a_busy_database_is_a_refusal_not_a_traceback(self, db):
        """Callers run with stderr at /dev/null; raising here loses the refresh."""
        db.execute("PRAGMA busy_timeout = 50")  # don't sit out the real 10 s
        other = sqlite3.connect(str(cache_db.DB_PATH), timeout=0.05)
        other.execute("BEGIN IMMEDIATE")
        try:
            assert try_acquire_fetch_lock() is False
            assert try_acquire_costs_lock() is False
        finally:
            other.execute("ROLLBACK")
            other.close()
        assert try_acquire_fetch_lock() is True

    def test_a_failed_commit_is_a_refusal_not_a_rollback_error(self, db, monkeypatch):
        monkeypatch.setattr(cache_db, "get_connection", lambda: _FailingCommit(db))
        assert try_acquire_fetch_lock() is False


class TestBackoff:
    def test_no_failures_means_no_backoff(self, db):
        assert check_fetch_backoff() is False

    def test_a_failure_blocks_fetching_and_the_fetch_lock(self, db):
        record_fetch_failure()
        assert check_fetch_backoff() is True
        assert try_acquire_fetch_lock() is False

    def test_costs_lock_ignores_api_backoff(self, db):
        record_fetch_failure()
        assert try_acquire_costs_lock() is True

    def test_clearing_failures_ends_the_backoff(self, db):
        record_fetch_failure()
        clear_fetch_failures()
        assert check_fetch_backoff() is False
        assert try_acquire_fetch_lock() is True

    def test_corrupt_fail_time_is_not_a_backoff(self, db):
        cache_db._set_meta(db, "fetch_fail_count", "2")
        cache_db._set_meta(db, "fetch_fail_time", "whenever")
        db.commit()
        assert check_fetch_backoff() is False


def _cost_entry(mtime: int = 1, size: int = 1, dks: tuple[str, ...] = ()) -> dict:
    return {
        "mtime_ns": mtime, "size": size, "week_cost": 1.0, "month_cost": 2.0,
        "all_time_cost": 3.0, "dedup_keys": list(dks),
    }


class TestBulkSaveFileCosts:
    """Saving one changed file must not churn the rest of the corpus."""

    WEEK = "2026-08-03T00"
    MONTH = "2026-08"

    def _save(self, entries, changed=None) -> None:
        bulk_save_file_costs(entries, self.WEEK, self.MONTH, changed=changed)

    def _dks(self, conn, path: str) -> set[str]:
        return {
            r[0] for r in
            conn.execute("SELECT dk FROM dedup_keys WHERE file_path = ?", (path,))
        }

    def test_a_save_round_trips_through_load(self, db):
        self._save({"/a": _cost_entry(mtime=7, size=8, dks=("k1", "k2"))})
        loaded = load_cost_cache(self.WEEK, self.MONTH)["/a"]
        assert (loaded["mtime_ns"], loaded["size"]) == (7, 8)
        assert sorted(loaded["dedup_keys"]) == ["k1", "k2"]

    def test_an_unchanged_files_dedup_keys_survive(self, db):
        entries = {"/a": _cost_entry(dks=("a1",)), "/b": _cost_entry(dks=("b1",))}
        self._save(entries)
        # A key only the table knows about: it disappears if the save rewrites
        # /b's keys, and stays if the save leaves that row alone.
        db.execute("INSERT INTO dedup_keys (dk, file_path) VALUES ('ghost', '/b')")
        db.commit()

        entries["/a"] = _cost_entry(mtime=2, dks=("a2",))
        self._save(entries, changed={"/a"})

        assert self._dks(db, "/a") == {"a2"}
        assert self._dks(db, "/b") == {"b1", "ghost"}

    def test_a_changed_files_row_is_replaced(self, db):
        self._save({"/a": _cost_entry(mtime=1, size=1, dks=("old",))})
        self._save({"/a": _cost_entry(mtime=9, size=9, dks=("new",))}, changed={"/a"})
        loaded = load_cost_cache(self.WEEK, self.MONTH)["/a"]
        assert (loaded["mtime_ns"], loaded["size"]) == (9, 9)
        assert loaded["dedup_keys"] == ["new"]

    def test_a_departed_path_takes_its_dedup_keys_with_it(self, db):
        self._save({"/a": _cost_entry(dks=("a1",)), "/b": _cost_entry(dks=("b1",))})
        self._save({"/a": _cost_entry(dks=("a1",))}, changed=set())
        assert set(load_cost_cache(self.WEEK, self.MONTH)) == {"/a"}
        assert self._dks(db, "/b") == set()

    def test_no_changed_set_means_rewrite_everything(self, db):
        self._save({"/a": _cost_entry(dks=("a1",))})
        db.execute("INSERT INTO dedup_keys (dk, file_path) VALUES ('ghost', '/a')")
        db.commit()
        self._save({"/a": _cost_entry(dks=("a1",))})
        assert self._dks(db, "/a") == {"a1"}

    def test_one_changed_file_writes_one_row(self, db):
        entries = {f"/f{i}": _cost_entry(dks=(f"k{i}",)) for i in range(50)}
        self._save(entries)
        writes = _count_statements(db, "INTO file_costs")

        entries["/f7"] = _cost_entry(mtime=2, dks=("k7",))
        self._save(entries, changed={"/f7"})
        assert writes() == 1

    def test_a_failed_commit_reports_its_own_error(self, db, monkeypatch):
        monkeypatch.setattr(cache_db, "get_connection", lambda: _FailingCommit(db))
        with pytest.raises(sqlite3.OperationalError, match="disk I/O error"):
            self._save({"/a": _cost_entry()})


class TestDedupKeyPruning:
    """Keys stop being stored once no bounded window can still count the file.

    The table gains a row per assistant message and nothing ever removed one
    (macsetup-1jvz). Costs from an aged-out file survive in file_costs; only
    its dedup keys go.
    """

    WEEK = "2026-08-03T00"
    MONTH = "2026-08"
    CUTOFF = 1_000_000
    OLD = CUTOFF - 1
    FRESH = CUTOFF + 1

    def _save(self, entries, changed=None, cutoff=CUTOFF) -> None:
        bulk_save_file_costs(
            entries, self.WEEK, self.MONTH, changed=changed, dedup_cutoff_ns=cutoff,
        )

    def test_an_aged_out_files_keys_are_never_written(self, db):
        self._save({"/old": _cost_entry(mtime=self.OLD, dks=("k1",))})
        assert load_cost_cache(self.WEEK, self.MONTH)["/old"]["dedup_keys"] == []

    def test_a_fresh_files_keys_survive(self, db):
        self._save({"/new": _cost_entry(mtime=self.FRESH, dks=("k1", "k2"))})
        loaded = load_cost_cache(self.WEEK, self.MONTH)["/new"]
        assert sorted(loaded["dedup_keys"]) == ["k1", "k2"]

    def test_keys_written_in_window_are_pruned_once_the_file_ages_out(self, db):
        entry = _cost_entry(mtime=self.FRESH, dks=("k1",))
        self._save({"/f": entry})
        # The window moves rather than the file: the same mtime is now behind
        # the cutoff, which is what a day passing does to every stored file.
        self._save({"/f": entry}, changed=set(), cutoff=self.FRESH + 1)
        assert load_cost_cache(self.WEEK, self.MONTH)["/f"]["dedup_keys"] == []

    def test_the_aged_out_files_costs_stay(self, db):
        self._save({"/old": _cost_entry(mtime=self.OLD, dks=("k1",))})
        loaded = load_cost_cache(self.WEEK, self.MONTH)["/old"]
        assert (loaded["week_cost"], loaded["all_time_cost"]) == (1.0, 3.0)

    def test_no_cutoff_keeps_everything(self, db):
        self._save({"/old": _cost_entry(mtime=self.OLD, dks=("k1",))}, cutoff=None)
        assert load_cost_cache(self.WEEK, self.MONTH)["/old"]["dedup_keys"] == ["k1"]

    def test_the_grouped_load_keys_every_file_separately(self, db):
        entries = {
            f"/f{i}": _cost_entry(mtime=self.FRESH, dks=(f"k{i}a", f"k{i}b"))
            for i in range(5)
        }
        self._save(entries)
        loaded = load_cost_cache(self.WEEK, self.MONTH)
        assert {p: sorted(e["dedup_keys"]) for p, e in loaded.items()} == {
            f"/f{i}": [f"k{i}a", f"k{i}b"] for i in range(5)
        }


class TestCcreportRows:
    RECORD = {
        "mid": "m1", "model": "claude-opus-5", "ts": 1.5, "sid": "s1",
        "project": "proj", "cwd": "/tmp/proj", "repo": "gh/x", "dk": "dk1",
        "cost": 0.25, "t": [1, 2, 3, 4],
    }
    PATH = "/tmp/proj/a.jsonl"

    def test_a_saved_record_round_trips_field_for_field(self, db):
        """Every column the INSERT names comes back the way it went in.

        The insert list, its placeholders and the mapping back are all derived
        from _CCR_COLS, so this is the test that would catch a column added to
        the table and left out of that tuple.
        """
        save_ccreport_file(self.PATH, 111, 222, [self.RECORD])
        file_meta, by_file = bulk_load_ccreport_cache()
        assert by_file == {self.PATH: [self.RECORD]}
        assert file_meta == {self.PATH: (111, 222)}

    def test_a_batch_save_writes_every_file(self, db):
        other = {**self.RECORD, "mid": "m2"}
        save_ccreport_files([
            (self.PATH, 111, 222, [self.RECORD]),
            ("/tmp/proj/b.jsonl", 333, 444, [other]),
        ])
        file_meta, by_file = bulk_load_ccreport_cache()
        assert file_meta == {self.PATH: (111, 222), "/tmp/proj/b.jsonl": (333, 444)}
        assert by_file == {self.PATH: [self.RECORD], "/tmp/proj/b.jsonl": [other]}

    def test_a_batch_save_replaces_a_files_records(self, db):
        save_ccreport_files([(self.PATH, 111, 222, [self.RECORD])])
        replacement = {**self.RECORD, "mid": "m9"}
        save_ccreport_files([(self.PATH, 555, 666, [replacement])])
        file_meta, by_file = bulk_load_ccreport_cache()
        assert file_meta == {self.PATH: (555, 666)}
        assert by_file == {self.PATH: [replacement]}

    def test_an_empty_batch_writes_nothing(self, db):
        save_ccreport_files([])
        assert bulk_load_ccreport_cache() == ({}, {})

    def test_a_batch_is_one_transaction(self, db):
        commits = _count_commits(db)
        save_ccreport_files([
            (f"/tmp/proj/{i}.jsonl", i, i, [self.RECORD]) for i in range(20)
        ])
        assert commits() == 1

    def test_column_constant_matches_the_table(self, db):
        assert set(_CCR_COLS) <= _columns(db, "ccreport_records")

    def test_every_record_column_is_written_and_read_back(self, db):
        """No column of _CCR_COLS is silently NULLed on the way through.

        A column present in the SELECT but missing from the INSERT reads back
        as None, which a round-trip of one hand-written record only catches if
        that record happens to carry a truthy value for it — so assert the
        stored row directly.
        """
        save_ccreport_file(self.PATH, 111, 222, [self.RECORD])
        stored = db.execute(
            f"SELECT {', '.join(_CCR_COLS)} FROM ccreport_records"
        ).fetchone()
        assert all(v is not None for v in stored)


class TestScopedCcreportLoaders:
    """The scoped loaders must equal a full load filtered in Python.

    That equality is the whole safety argument for macsetup-45iv: the
    statusline used to read all ~89K rows per render and throw away everything
    outside one project.
    """

    PROJ = "/p/-tmp-proj/"
    # Shares PROJ as a string prefix but is a different directory, which is
    # exactly what the half-open range has to exclude and a bare `>=` would not.
    SIBLING = "/p/-tmp-proj-other/"
    OTHER = "/p/-tmp-elsewhere/"

    @pytest.fixture
    def seeded(self, db):
        def rec(**kw):
            return {
                "mid": "m", "model": "claude-opus-5", "ts": 1.5, "sid": "s1",
                "project": "proj", "cwd": "/tmp/proj", "repo": "gh/x",
                "dk": None, "cost": 0.25, "t": [1, 2, 3, 4], **kw,
            }
        save_ccreport_files([
            (self.PROJ + "a.jsonl", 1, 1, [rec(mid="a1"), rec(mid="a2", sid="s2")]),
            (self.PROJ + "sub/b.jsonl", 2, 2, [rec(mid="b1", sid="s2")]),
            (self.SIBLING + "c.jsonl", 3, 3, [rec(mid="c1")]),
            (self.OTHER + "d.jsonl", 4, 4, [rec(mid="d1", sid="s2")]),
        ])
        return db

    def test_a_prefix_load_equals_a_full_load_filtered_by_that_prefix(self, seeded):
        _, everything = bulk_load_ccreport_cache()
        expected = {
            path: recs for path, recs in everything.items()
            if path.startswith(self.PROJ)
        }
        assert cache_db.load_ccreport_records_under(self.PROJ) == expected

    def test_a_sibling_sharing_the_prefix_string_is_excluded(self, seeded):
        loaded = cache_db.load_ccreport_records_under(self.PROJ)
        assert set(loaded) == {self.PROJ + "a.jsonl", self.PROJ + "sub/b.jsonl"}
        assert self.SIBLING + "c.jsonl" not in loaded

    def test_a_session_load_equals_a_full_load_filtered_by_sid(self, seeded):
        _, everything = bulk_load_ccreport_cache()
        expected = {}
        for path, recs in everything.items():
            hits = [r for r in recs if r["sid"] == "s2"]
            if hits:
                expected[path] = hits
        assert cache_db.load_ccreport_records_for_session("s2") == expected

    def test_a_session_load_reaches_across_projects(self, seeded):
        loaded = cache_db.load_ccreport_records_for_session("s2")
        # Scoping to one project is the caller's job, so the loader itself must
        # not do it — compute_session_cost applies the prefixes afterwards.
        assert set(loaded) == {
            self.PROJ + "a.jsonl", self.PROJ + "sub/b.jsonl", self.OTHER + "d.jsonl",
        }

    def test_an_unmatched_prefix_loads_nothing(self, seeded):
        assert cache_db.load_ccreport_records_under("/p/-tmp-nothing/") == {}

    @pytest.mark.parametrize(
        "prefix, expected",
        [("/a/b/", ("/a/b/", "/a/b0")), ("xy", ("xy", "xz"))],
    )
    def test_the_upper_bound_steps_the_last_character(self, prefix, expected):
        assert cache_db.prefix_range(prefix) == expected

    def test_an_empty_prefix_is_refused(self):
        # Silently scanning the whole table is the bug this exists to prevent.
        with pytest.raises(ValueError):
            cache_db.prefix_range("")


class TestCcreportSaltGate:
    """A reader that cannot vouch for the row format degrades; it never repairs.

    Invalidation belongs to ccreport's _ensure_cache_valid, which re-parses
    what it clears. A statusline render doing it would destroy the orphan
    records no re-parse can rebuild.
    """

    PATH = "/p/-tmp-proj/a.jsonl"
    RECORD = {
        "mid": "m1", "model": "claude-opus-5", "ts": 1.5, "sid": "s1",
        "project": "proj", "cwd": "/tmp/proj", "repo": "gh/x", "dk": "dk1",
        "cost": 0.25, "t": [1, 2, 3, 4],
    }

    @pytest.fixture
    def mismatched(self, db):
        save_ccreport_file(self.PATH, 111, 222, [self.RECORD])
        cache_db._set_meta(db, "ccreport_schema_salt", "not-the-salt")
        db.commit()
        return db

    @pytest.mark.parametrize(
        "read",
        [
            pytest.param(lambda: bulk_load_ccreport_cache(), id="bulk"),
            pytest.param(
                lambda: cache_db.load_ccreport_records_under("/p/-tmp-proj/"),
                id="prefix"),
            pytest.param(
                lambda: cache_db.load_ccreport_records_for_session("s1"),
                id="session"),
        ],
    )
    def test_a_mismatched_salt_reads_as_empty(self, mismatched, read):
        result = read()
        assert not any(result) if isinstance(result, tuple) else result == {}

    def test_a_missing_salt_reads_as_empty(self, db):
        save_ccreport_file(self.PATH, 111, 222, [self.RECORD])
        db.execute("DELETE FROM meta WHERE key = 'ccreport_schema_salt'")
        db.commit()
        assert cache_db.load_ccreport_records_under("/p/-tmp-proj/") == {}

    def test_the_degraded_read_deletes_nothing(self, mismatched):
        bulk_load_ccreport_cache()
        cache_db.load_ccreport_records_under("/p/-tmp-proj/")
        cache_db.load_ccreport_records_for_session("s1")
        assert mismatched.execute(
            "SELECT COUNT(*) FROM ccreport_records").fetchone()[0] == 1
        assert mismatched.execute(
            "SELECT COUNT(*) FROM ccreport_files").fetchone()[0] == 1
        # The cost above all: an orphan's came from a JSONL that is gone.
        assert mismatched.execute(
            "SELECT cost FROM ccreport_records").fetchone()[0] == 0.25

    def test_restamping_the_salt_brings_the_rows_back(self, mismatched):
        cache_db.init_ccreport_meta(1, "test-hash")
        assert cache_db.load_ccreport_records_under("/p/-tmp-proj/") == {
            self.PATH: [self.RECORD]
        }


class TestInvalidateCcreport:
    """An orphan's cost came from a JSONL that's gone; it must survive."""

    LIVE = "/tmp/proj/live.jsonl"
    GONE = "/tmp/proj/purged.jsonl"
    RECORD = {
        "mid": "m1", "model": "claude-opus-5", "ts": 1.5, "sid": "s1",
        "project": "proj", "cwd": "/tmp/proj", "repo": "gh/x", "dk": "dk1",
        "cost": 0.25, "t": [1, 2, 3, 4],
    }

    @pytest.fixture
    def two_files(self, db):
        save_ccreport_file(self.LIVE, 111, 222, [dict(self.RECORD)])
        save_ccreport_file(self.GONE, 333, 444, [dict(self.RECORD)])
        return db

    @staticmethod
    def _cost(conn, path):
        """The one record's cached cost, read past the salt gate.

        invalidate_ccreport drops the salt, and every loader returns nothing
        without it, so these assertions go to the table directly.
        """
        return conn.execute(
            "SELECT cost FROM ccreport_records WHERE file_path = ?", (path,)
        ).fetchone()[0]

    def test_only_live_records_lose_their_cached_cost(self, two_files):
        invalidate_ccreport({self.LIVE})
        assert self._cost(two_files, self.LIVE) is None
        assert self._cost(two_files, self.GONE) == 0.25

    def test_only_live_files_lose_their_fingerprint(self, two_files):
        invalidate_ccreport({self.LIVE})
        # invalidate_ccreport drops the salt; ccreport's _ensure_cache_valid
        # restamps it in the next breath, and the readers below need it back.
        cache_db.init_ccreport_meta(1, "test-hash")
        file_meta, _ = bulk_load_ccreport_cache()
        assert file_meta[self.LIVE] == (0, 0)
        assert file_meta[self.GONE] == (333, 444)

    def test_with_no_live_files_it_only_clears_the_meta_keys(self, two_files):
        cache_db.init_ccreport_meta(9, "hash")
        invalidate_ccreport(set())
        assert cache_db.check_ccreport_valid(9, "hash") is False
        assert self._cost(two_files, self.GONE) == 0.25
        assert self._cost(two_files, self.LIVE) == 0.25


class TestFlatPricingVariantsMigration:
    """Migration 2 matched models by equality; find_pricing matches substrings."""

    CUTOFF = 1773424800.0  # 2026-03-13T18:00 UTC
    ROWS = [
        # (mid, model, ts, cost)
        ("bracketed", "claude-opus-4-6[1m]", CUTOFF + 1, 5.0),
        ("bracketed-old", "claude-opus-4-6[1m]", CUTOFF - 1, 5.0),
        ("dated", "claude-sonnet-4-6-20260210", CUTOFF + 1, 5.0),
        ("exact", "claude-opus-4-6", CUTOFF + 1, 5.0),
        ("unrelated", "claude-opus-5", CUTOFF + 1, 5.0),
    ]

    @pytest.fixture
    def migrated(self, tmp_path, monkeypatch):
        """A DB carrying the pre-existing migration flags, then reopened."""
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DISABLE", "1")
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DIR", str(tmp_path / "snaps"))
        path = tmp_path / "cache.db"
        seed = sqlite3.connect(path)
        seed.executescript(cache_db._SCHEMA_SQL)
        _seed_ccreport(seed, self.ROWS)
        seed.execute(
            "INSERT INTO session_costs (session_id, fingerprint, cost) VALUES ('s1', 1, 3.0)")
        seed.execute("INSERT INTO meta (key, value) VALUES ('cost_summary', '{}')")
        # Every real DB already ran migrations 1-3, so only the new one fires.
        seed.executemany(
            "INSERT INTO meta (key, value) VALUES (?, '1')",
            [("migrated_flat_pricing_2026_03_13",), ("migrated_flat_pricing_ccreport",),
             ("migrated_rename_fingerprint",)],
        )
        seed.commit()
        seed.close()

        monkeypatch.setattr(cache_db, "DB_PATH", path)
        monkeypatch.setattr(cache_db, "_conn", None)
        conn = cache_db.get_connection()
        yield conn
        cache_db.close_connection()

    @staticmethod
    def _costs(conn) -> dict[str, float | None]:
        return dict(conn.execute("SELECT mid, cost FROM ccreport_records"))

    def test_missed_variants_past_the_cutoff_are_nulled(self, migrated):
        costs = self._costs(migrated)
        assert costs["bracketed"] is None
        assert costs["dated"] is None
        assert costs["exact"] is None

    def test_pre_cutoff_and_unrelated_models_keep_their_cost(self, migrated):
        costs = self._costs(migrated)
        assert costs["bracketed-old"] == 5.0
        assert costs["unrelated"] == 5.0

    def test_derived_cost_caches_are_dropped(self, migrated):
        assert migrated.execute("SELECT COUNT(*) FROM session_costs").fetchone()[0] == 0
        assert cache_db._get_meta(migrated, "cost_summary") is None

    def test_the_flag_stops_it_running_twice(self, migrated):
        assert cache_db._get_meta(migrated, "migrated_flat_pricing_ccreport_variants") == "1"
        migrated.execute("UPDATE ccreport_records SET cost = 7.0")
        migrated.commit()
        assert cache_db._run_migrations(migrated) is False
        assert self._costs(migrated)["bracketed"] == 7.0


# The index and dedup_keys shapes as they stood before macsetup-45iv/3le2/4rpc.
_OLD_INDEX_SHAPE_SQL = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID;
CREATE TABLE file_costs (
    path TEXT PRIMARY KEY, mtime_ns INTEGER NOT NULL, size INTEGER NOT NULL,
    week_cost REAL NOT NULL DEFAULT 0, month_cost REAL NOT NULL DEFAULT 0,
    all_time_cost REAL NOT NULL DEFAULT 0, session_cost REAL) WITHOUT ROWID;
CREATE TABLE dedup_keys (
    dk TEXT NOT NULL,
    file_path TEXT NOT NULL REFERENCES file_costs(path) ON DELETE CASCADE,
    PRIMARY KEY (dk, file_path)) WITHOUT ROWID;
CREATE INDEX idx_dedup_file ON dedup_keys(file_path);
CREATE TABLE ccreport_files (
    path TEXT PRIMARY KEY, mtime_ns INTEGER NOT NULL, size INTEGER NOT NULL);
CREATE TABLE ccreport_records (
    id INTEGER PRIMARY KEY,
    file_path TEXT NOT NULL REFERENCES ccreport_files(path) ON DELETE CASCADE,
    mid TEXT, model TEXT NOT NULL, ts REAL NOT NULL, sid TEXT NOT NULL,
    project TEXT NOT NULL, dk TEXT, cost REAL,
    input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL,
    cache_create INTEGER NOT NULL, cache_read INTEGER NOT NULL);
CREATE INDEX idx_ccr_file ON ccreport_records(file_path);
CREATE INDEX idx_ccr_ts ON ccreport_records(ts);
"""

_WANTED_CCR_INDEXES = {"idx_ccr_file_ts", "idx_ccr_sid"}
_DEAD_INDEXES = {"idx_ccr_file", "idx_ccr_ts", "idx_dedup_file"}


def _index_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA index_list({table})")}


def _index_columns(conn: sqlite3.Connection, name: str) -> list[str]:
    return [r[2] for r in conn.execute(f"PRAGMA index_info({name})")]


class TestIndexShape:
    """A fresh DB and a migrated one must end up with the same indexes.

    _SCHEMA_SQL only ever creates, so without migration 4 an existing DB would
    keep maintaining the replaced indexes on every insert forever.
    """

    @pytest.fixture
    def old_shaped(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DISABLE", "1")
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DIR", str(tmp_path / "snaps"))
        path = tmp_path / "old.db"
        seed = sqlite3.connect(path)
        seed.executescript(_OLD_INDEX_SHAPE_SQL)
        seed.execute("INSERT INTO file_costs (path, mtime_ns, size) VALUES ('/f', 1, 1)")
        seed.executemany(
            "INSERT INTO dedup_keys (dk, file_path) VALUES (?, '/f')",
            [("k1",), ("k2",)],
        )
        seed.commit()
        seed.close()
        monkeypatch.setattr(cache_db, "DB_PATH", path)
        monkeypatch.setattr(cache_db, "_conn", None)
        conn = cache_db.get_connection()
        yield conn
        cache_db.close_connection()

    def test_a_fresh_db_has_the_new_indexes_and_none_of_the_dead_ones(self, db):
        assert _WANTED_CCR_INDEXES <= _index_names(db, "ccreport_records")
        assert _index_names(db, "ccreport_records") & _DEAD_INDEXES == set()
        assert _index_names(db, "dedup_keys") & _DEAD_INDEXES == set()

    def test_migration_brings_an_old_db_to_the_same_shape(self, old_shaped):
        assert _WANTED_CCR_INDEXES <= _index_names(old_shaped, "ccreport_records")
        assert _index_names(old_shaped, "ccreport_records") & _DEAD_INDEXES == set()
        assert _index_names(old_shaped, "dedup_keys") & _DEAD_INDEXES == set()

    def test_the_composite_index_leads_with_file_path(self, db):
        assert _index_columns(db, "idx_ccr_file_ts") == ["file_path", "ts"]

    @pytest.mark.parametrize("fixture", ["db", "old_shaped"])
    def test_dedup_keys_is_keyed_file_path_first(self, fixture, request):
        conn = request.getfixturevalue(fixture)
        assert cache_db._dedup_keys_pk_order(conn) == ["file_path", "dk"]

    def test_the_rebuild_keeps_every_dedup_row(self, old_shaped):
        rows = set(old_shaped.execute("SELECT dk, file_path FROM dedup_keys"))
        assert rows == {("k1", "/f"), ("k2", "/f")}

    def test_the_rebuilt_table_still_cascades_from_file_costs(self, old_shaped):
        old_shaped.execute("DELETE FROM file_costs WHERE path = '/f'")
        old_shaped.commit()
        assert old_shaped.execute("SELECT COUNT(*) FROM dedup_keys").fetchone()[0] == 0

    def test_the_flags_stop_both_migrations_running_twice(self, old_shaped):
        assert cache_db._get_meta(old_shaped, "migrated_drop_dead_indexes") == "1"
        assert cache_db._get_meta(old_shaped, "migrated_dedup_keys_pk_order") == "1"
        assert cache_db._run_migrations(old_shaped) is False


class TestDedupKeysRebuildWithOrphans:
    """A parentless dedup key must not take the whole migration down.

    The old table was written with foreign_keys OFF for years, so real DBs carry
    rows whose file_costs parent is gone. Copying those into the new table under
    foreign_keys ON raised IntegrityError before the migration's own
    foreign_key_check could report it, and every ccreport run died in
    get_connection (macsetup-1g9w).
    """

    @pytest.fixture
    def orphaned(self, tmp_path, monkeypatch):
        """An old-shaped DB with one live dedup key and one orphan.

        The pk-order flag is seeded so the open itself is quiet; the test clears
        it and runs the migration by hand.
        """
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DISABLE", "1")
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DIR", str(tmp_path / "snaps"))
        path = tmp_path / "orphaned.db"
        seed = sqlite3.connect(path)
        seed.executescript(_OLD_INDEX_SHAPE_SQL)
        seed.execute("INSERT INTO file_costs (path, mtime_ns, size) VALUES ('/live', 1, 1)")
        seed.executemany(
            "INSERT INTO dedup_keys (dk, file_path) VALUES (?, ?)",
            [("kept", "/live"), ("lost", "/gone")],
        )
        seed.execute(
            "INSERT INTO meta (key, value) VALUES ('migrated_dedup_keys_pk_order', '1')"
        )
        seed.commit()
        seed.close()
        monkeypatch.setattr(cache_db, "DB_PATH", path)
        monkeypatch.setattr(cache_db, "_conn", None)
        conn = cache_db.get_connection()
        yield conn
        cache_db.close_connection()

    @staticmethod
    def _migrate(conn) -> None:
        conn.execute("DELETE FROM meta WHERE key = 'migrated_dedup_keys_pk_order'")
        conn.commit()
        assert cache_db._run_migrations(conn) is True
        assert cache_db._get_meta(conn, "migrated_dedup_keys_pk_order") == "1"

    def test_the_rebuild_keeps_the_live_key_and_drops_the_orphan(self, orphaned):
        self._migrate(orphaned)
        rows = set(orphaned.execute("SELECT dk, file_path FROM dedup_keys"))
        assert rows == {("kept", "/live")}

    def test_the_rebuild_still_reorders_the_primary_key(self, orphaned):
        self._migrate(orphaned)
        assert cache_db._dedup_keys_pk_order(orphaned) == ["file_path", "dk"]


class TestPurgeCostSummaries:
    """write_cost_summary scopes its keys by project, so the literals miss.

    Migrations 1, 2 and 2b deleted 'cost_summary'/'cost_summary_time' and
    cleared nothing at all, because the only caller of write_cost_summary
    always passes a cwd (macsetup-3a7f).
    """

    def test_it_removes_the_project_scoped_keys(self, db):
        cache_db.write_cost_summary({"week_cost": 1.0}, cwd="/tmp/proj")
        cache_db.write_cost_summary({"week_cost": 2.0}, cwd="/tmp/other")
        cache_db._purge_cost_summaries(db)
        db.commit()
        assert cache_db.read_cost_summary(cwd="/tmp/proj") is None
        assert cache_db.read_cost_summary(cwd="/tmp/other") is None

    def test_it_removes_the_bare_keys_too(self, db):
        cache_db.write_cost_summary({"week_cost": 1.0})
        cache_db._purge_cost_summaries(db)
        db.commit()
        assert cache_db.read_cost_summary() is None

    def test_it_leaves_everything_else_alone(self, db):
        cache_db._set_meta(db, "ccreport_version", "9")
        cache_db.write_cost_summary({"week_cost": 1.0}, cwd="/tmp/proj")
        cache_db._purge_cost_summaries(db)
        db.commit()
        assert cache_db._get_meta(db, "ccreport_version") == "9"

    def test_a_migration_clears_a_scoped_summary(self, tmp_path, monkeypatch):
        """The regression itself: migration 2b ran and left the real key behind."""
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DISABLE", "1")
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DIR", str(tmp_path / "snaps"))
        path = tmp_path / "cache.db"
        seed = sqlite3.connect(path)
        seed.executescript(cache_db._SCHEMA_SQL)
        _seed_ccreport(seed, [("m", "claude-opus-4-6", 1773424801.0, 5.0)])
        seed.executemany(
            "INSERT INTO meta (key, value) VALUES (?, '1')",
            [("migrated_flat_pricing_2026_03_13",), ("migrated_flat_pricing_ccreport",),
             ("migrated_rename_fingerprint",)],
        )
        seed.execute(
            "INSERT INTO meta (key, value) VALUES ('cost_summary:-tmp-proj', '{}')")
        seed.commit()
        seed.close()

        monkeypatch.setattr(cache_db, "DB_PATH", path)
        monkeypatch.setattr(cache_db, "_conn", None)
        conn = cache_db.get_connection()
        try:
            assert cache_db._get_meta(conn, "cost_summary:-tmp-proj") is None
        finally:
            cache_db.close_connection()


class TestSanityCheck:
    """Warns on lost rows, lost costs, or records orphaned from their file."""

    @pytest.fixture
    def snapshotted(self, tmp_path, monkeypatch):
        """A DB with 200 costed records and yesterday's snapshot beside it."""
        snaps = tmp_path / "snaps"
        snaps.mkdir()
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DIR", str(snaps))
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DISABLE", "1")
        monkeypatch.delenv("CLAUDE_CACHE_SANITY_DISABLE", raising=False)
        monkeypatch.delenv("CLAUDE_CACHE_SANITY_ABORT", raising=False)
        monkeypatch.setattr(cache_db, "DB_PATH", tmp_path / "cache.db")
        monkeypatch.setattr(cache_db, "_conn", None)
        conn = cache_db.get_connection()
        _seed_ccreport(conn, [(f"m{i}", "claude-opus-5", 1.0, 1.0) for i in range(200)])
        yesterday = (datetime.now(tz=timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        dst = sqlite3.connect(str(snaps / f"{yesterday}.db"))
        conn.backup(dst)
        dst.close()
        yield conn
        cache_db.close_connection()

    def test_an_intact_db_says_nothing(self, snapshotted, capsys):
        cache_db._sanity_check(snapshotted)
        assert capsys.readouterr().err == ""

    def test_a_cost_wipe_warns_though_the_row_count_holds(self, snapshotted, capsys):
        snapshotted.execute("UPDATE ccreport_records SET cost = NULL")
        snapshotted.commit()
        cache_db._sanity_check(snapshotted)
        err = capsys.readouterr().err
        assert "lost ccreport_records costs" in err
        assert "lost ccreport_records rows" not in err

    def test_deleted_rows_still_warn(self, snapshotted, capsys):
        snapshotted.execute("DELETE FROM ccreport_records WHERE mid LIKE 'm1%'")
        snapshotted.commit()
        cache_db._sanity_check(snapshotted)
        assert "lost ccreport_records rows" in capsys.readouterr().err

    def test_abort_env_raises_instead_of_warning(self, snapshotted, monkeypatch):
        monkeypatch.setenv("CLAUDE_CACHE_SANITY_ABORT", "1")
        snapshotted.execute("UPDATE ccreport_records SET cost = NULL")
        snapshotted.commit()
        with pytest.raises(RuntimeError, match="lost ccreport_records costs"):
            cache_db._sanity_check(snapshotted)

    def test_parentless_records_are_reported(self, snapshotted, capsys):
        snapshotted.execute("PRAGMA foreign_keys = OFF")
        snapshotted.execute("DELETE FROM ccreport_files")
        snapshotted.commit()
        snapshotted.execute("PRAGMA foreign_keys = ON")
        cache_db._sanity_check(snapshotted)
        assert "no ccreport_files parent" in capsys.readouterr().err

    def test_the_disable_env_silences_everything(self, snapshotted, capsys, monkeypatch):
        monkeypatch.setenv("CLAUDE_CACHE_SANITY_DISABLE", "1")
        snapshotted.execute("DELETE FROM ccreport_records")
        snapshotted.commit()
        cache_db._sanity_check(snapshotted)
        assert capsys.readouterr().err == ""

    def test_a_deferring_process_leaves_the_check_to_whoever_snapshots(
        self, tmp_path, monkeypatch,
    ):
        """The check rides the snapshot, so deferring one defers the other."""
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DIR", str(tmp_path / "snaps"))
        monkeypatch.setattr(cache_db, "DB_PATH", tmp_path / "cache.db")
        monkeypatch.setattr(cache_db, "_conn", None)
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DISABLE", "1")
        cache_db.get_connection()
        cache_db.close_connection()
        monkeypatch.delenv("CLAUDE_CACHE_SNAPSHOT_DISABLE")

        calls: list = []
        monkeypatch.setattr(cache_db, "_sanity_check", calls.append)
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DEFER", "1")
        cache_db.get_connection()
        cache_db.close_connection()
        assert calls == []

    def test_it_runs_once_a_day_off_the_snapshot_not_off_migrations(
        self, tmp_path, monkeypatch,
    ):
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DIR", str(tmp_path / "snaps"))
        monkeypatch.delenv("CLAUDE_CACHE_SNAPSHOT_DEFER", raising=False)
        monkeypatch.setattr(cache_db, "DB_PATH", tmp_path / "cache.db")
        monkeypatch.setattr(cache_db, "_conn", None)
        # Create the DB with snapshots off, so today's is still unwritten and
        # every migration flag is already set — the old trigger is exhausted.
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DISABLE", "1")
        cache_db.get_connection()
        cache_db.close_connection()
        monkeypatch.delenv("CLAUDE_CACHE_SNAPSHOT_DISABLE")

        calls: list = []
        monkeypatch.setattr(cache_db, "_sanity_check", calls.append)
        cache_db.get_connection()
        cache_db.close_connection()
        assert len(calls) == 1, "the run that writes the day's snapshot checks"
        cache_db.get_connection()
        cache_db.close_connection()
        assert len(calls) == 1, "later runs the same day do not"


class _BackupRecorder:
    """Stands in for a connection, recording how conn.backup was called."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def backup(self, dst, **kwargs) -> None:  # noqa: ANN001
        self.calls.append(kwargs)


class TestDailySnapshot:
    """A full copy of the DB is nothing a statusline render should be doing.

    The daily one is deferred out of the render and into its detached refresh
    subprocess; the one taken before a migration is not deferrable at all
    (macsetup-3xzh).
    """

    @pytest.fixture
    def snaps(self, tmp_path, monkeypatch):
        """An existing DB with 200 records, and today's snapshot still unwritten.

        Created with snapshots off, because get_connection only snapshots a DB
        that was already there — a first-ever open has nothing to back up.
        """
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DIR", str(tmp_path / "snaps"))
        monkeypatch.setenv("CLAUDE_CACHE_SANITY_DISABLE", "1")
        monkeypatch.delenv("CLAUDE_CACHE_SNAPSHOT_DEFER", raising=False)
        monkeypatch.setattr(cache_db, "DB_PATH", tmp_path / "cache.db")
        monkeypatch.setattr(cache_db, "_conn", None)
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DISABLE", "1")
        conn = cache_db.get_connection()
        _seed_ccreport(conn, [(f"m{i}", "claude-opus-5", 1.0, 1.0) for i in range(200)])
        cache_db.close_connection()
        monkeypatch.delenv("CLAUDE_CACHE_SNAPSHOT_DISABLE")
        yield tmp_path / "snaps"
        cache_db.close_connection()

    @staticmethod
    def _today(snaps):
        return snaps / f"{datetime.now(tz=timezone.utc).strftime('%Y-%m-%d')}.db"

    @staticmethod
    def _open() -> None:
        cache_db.get_connection()
        cache_db.close_connection()

    def test_a_render_defers_the_daily_copy(self, snaps, monkeypatch):
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DEFER", "1")
        self._open()
        assert not self._today(snaps).exists()

    def test_a_process_that_does_not_defer_takes_it(self, snaps):
        self._open()
        assert self._today(snaps).exists()

    def test_a_pending_bootstrap_snapshots_even_under_defer(self, snaps, monkeypatch):
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DEFER", "1")
        stale = sqlite3.connect(cache_db.DB_PATH)
        stale.execute(f"PRAGMA user_version = {cache_db.SCHEMA_VERSION - 1}")
        stale.close()
        self._open()
        assert self._today(snaps).exists(), "a migration's pre-image is not optional"

    def test_the_snapshot_is_a_complete_and_valid_copy(self, snaps):
        self._open()
        copy = sqlite3.connect(f"file:{self._today(snaps)}?mode=ro", uri=True)
        try:
            assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert copy.execute(
                "SELECT COUNT(*) FROM ccreport_records").fetchone()[0] == 200
        finally:
            copy.close()

    def test_the_copy_is_stepped_rather_than_one_blocking_call(self, snaps):
        """Whole-DB backup() holds a read lock for its entire duration."""
        recorder = _BackupRecorder()
        _path, fresh = cache_db._maybe_snapshot(recorder)
        assert fresh
        assert recorder.calls[0]["pages"] > 0
        assert recorder.calls[0]["sleep"] > 0

    def test_a_copy_already_under_way_is_not_repeated(self, snaps):
        """target.exists() is checked before a copy that takes seconds."""
        snaps.mkdir(parents=True)
        self._today(snaps).with_suffix(".db.tmp").touch()
        recorder = _BackupRecorder()
        assert cache_db._maybe_snapshot(recorder) == (None, False)
        assert recorder.calls == []

    def test_a_tmp_left_by_a_dead_process_is_taken_over(self, snaps):
        snaps.mkdir(parents=True)
        tmp = self._today(snaps).with_suffix(".db.tmp")
        tmp.touch()
        stale = time.time() - cache_db._SNAPSHOT_TMP_STALE_S - 1
        os.utime(tmp, (stale, stale))
        recorder = _BackupRecorder()
        _path, fresh = cache_db._maybe_snapshot(recorder)
        assert fresh, "an abandoned tmp must not bar the snapshot all day"

    def test_an_existing_snapshot_is_not_rewritten(self, snaps):
        self._open()
        recorder = _BackupRecorder()
        path, fresh = cache_db._maybe_snapshot(recorder)
        assert (path, fresh) == (self._today(snaps), False)
        assert recorder.calls == []
