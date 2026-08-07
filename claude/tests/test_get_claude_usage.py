"""Tests for get_claude_usage.py's follower wait loop."""

from __future__ import annotations

import pytest

import get_claude_usage as gcu


class FakeClock:
    """Drives the loop without real time: sleeping advances monotonic()."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        if len(self.sleeps) > 1000:
            raise AssertionError("poll loop did not terminate")
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    """Fake clock plus a follower that never finds anything to emit."""
    c = FakeClock()
    monkeypatch.setattr(gcu.time, "monotonic", c.monotonic)
    monkeypatch.setattr(gcu.time, "sleep", c.sleep)
    monkeypatch.setattr(gcu, "read_usage_cache", lambda _max_age: None)
    monkeypatch.setattr(gcu, "read_usage_stale", lambda: None)
    monkeypatch.setattr(gcu, "_enrich_and_emit", lambda *a, **k: None)
    return c


def _wait(timeout: int) -> None:
    with pytest.raises(SystemExit):
        gcu._wait_for_leader(timeout, None, None)


class TestWaitForLeaderBackoff:
    def test_delays_double_from_the_minimum(self, clock):
        _wait(30)
        assert clock.sleeps[:5] == [0.1, 0.2, 0.4, 0.8, 1.0]

    def test_delay_is_capped(self, clock):
        _wait(30)
        assert max(clock.sleeps) == gcu.LEADER_POLL_MAX_DELAY

    def test_total_wait_does_not_exceed_the_timeout(self, clock):
        _wait(4)
        assert sum(clock.sleeps) == pytest.approx(4.0)
        assert clock.monotonic() == pytest.approx(1004.0)

    def test_backoff_reads_less_than_the_old_flat_half_second_poll(self, clock):
        _wait(30)
        assert len(clock.sleeps) < 60

    def test_zero_timeout_never_polls(self, clock, monkeypatch):
        reads = []
        monkeypatch.setattr(gcu, "read_usage_cache", lambda m: reads.append(m))
        _wait(0)
        assert clock.sleeps == []
        assert reads == []


class TestWaitForLeaderResult:
    def test_emits_and_exits_zero_once_the_leader_writes(self, clock, monkeypatch):
        row = {"session_percent": 12}
        polls = {"n": 0}

        def fake_read(_max_age):
            polls["n"] += 1
            return row if polls["n"] == 3 else None

        emitted = []
        monkeypatch.setattr(gcu, "read_usage_cache", fake_read)
        monkeypatch.setattr(gcu, "_enrich_and_emit", lambda d, s, c: emitted.append(d))

        with pytest.raises(SystemExit) as exc:
            gcu._wait_for_leader(30, "sess", "/tmp")

        assert exc.value.code == 0
        assert emitted == [row]
        assert clock.sleeps == [0.1, 0.2, 0.4]

    def test_timeout_falls_back_to_stale(self, clock, monkeypatch):
        emitted = []
        monkeypatch.setattr(gcu, "read_usage_stale", lambda: {"session_percent": 5})
        monkeypatch.setattr(gcu, "_enrich_and_emit", lambda d, s, c: emitted.append(d))

        with pytest.raises(SystemExit) as exc:
            gcu._wait_for_leader(4, None, None)

        assert exc.value.code == 0
        assert emitted == [{"session_percent": 5, "_stale": True}]

    def test_timeout_with_no_stale_data_exits_one(self, clock):
        with pytest.raises(SystemExit) as exc:
            gcu._wait_for_leader(4, None, None)
        assert exc.value.code == 1


class TestApiQuotaFields:
    """write_usage_cache no longer nulls absent keys, so an omitted quota has to
    be written as an explicit null — and that list has to stay complete."""

    FULL_BODY = {
        "five_hour": {"utilization": 23, "resets_at": "2026-08-07T18:00:00"},
        "seven_day": {"utilization": 41, "resets_at": "2026-08-12T09:00:00"},
        "seven_day_sonnet": {"utilization": 12, "resets_at": "2026-08-12T09:00:00"},
        "limits": [{
            "kind": "weekly_scoped", "percent": 9,
            "resets_at": "2026-08-12T09:00:00",
            "scope": {"model": {"display_name": "Fable"}},
        }],
        "extra_usage": {
            "utilization": 3, "used_credits": 350, "monthly_limit": 20000,
        },
    }

    def test_every_field_the_mapper_can_emit_is_listed(self, monkeypatch):
        monkeypatch.setattr(gcu, "request_usage_body", lambda _t: self.FULL_BODY)
        produced = set(gcu.fetch_usage_api("token"))
        assert produced - set(gcu._API_QUOTA_FIELDS) == set()
        assert produced == set(gcu._API_QUOTA_FIELDS)

    def test_the_list_names_real_columns(self):
        import cache_db

        assert set(gcu._API_QUOTA_FIELDS) <= set(cache_db._USAGE_FIELDS)

    def test_an_omitted_quota_is_written_as_null(self):
        """A plan that loses its Sonnet cap must not keep rendering the old %."""
        import cache_db

        cache_db.write_usage_cache({"sonnet_percent": 55, "session_percent": 10})
        partial = {"session_percent": 20, "week_percent": 30}
        cache_db.write_usage_cache({**dict.fromkeys(gcu._API_QUOTA_FIELDS), **partial})
        row = cache_db.read_usage_stale()
        assert "sonnet_percent" not in row
        assert row["session_percent"] == 20
