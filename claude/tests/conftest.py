"""Shared fixtures for claude/ tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the claude/ package root is importable.
_CLAUDE_DIR = Path(__file__).resolve().parent.parent
if str(_CLAUDE_DIR) not in sys.path:
    sys.path.insert(0, str(_CLAUDE_DIR))


@pytest.fixture(autouse=True)
def isolate_cache_db(tmp_path, monkeypatch):
    """Keep every test off the real ~/.cache cache.db.

    The modules under test reach cache_db through helpers that open the
    singleton connection on demand, several levels below what a test thinks
    it stubbed. Without this, a test that forgets to redirect DB_PATH runs
    schema work and data migrations against the user's real usage history —
    which holds orphaned records no re-parse can rebuild. Tests that need a
    DB of their own still redirect DB_PATH themselves; being autouse, this
    fixture is set up first, so theirs wins.
    """
    import cache_db

    monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DISABLE", "1")
    monkeypatch.setattr(cache_db, "DB_PATH", tmp_path / "isolated-cache.db")
    monkeypatch.setattr(cache_db, "_conn", None)
    yield
    cache_db.close_connection()
