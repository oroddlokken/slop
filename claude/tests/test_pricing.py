"""Tests for pricing.py — pure cost calculation and lookup functions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from pricing import (
    PRICING_HISTORY,
    ROLLING_WINDOWS,
    SESSION_WINDOW_S,
    TIER_THRESHOLD,
    WEEK_WINDOW_S,
    MODEL_ALIASES,
    _bucket_rolling_cost,
    _CacheResult,
    _FileContext,
    _ScanResult,
    _parse_effective,
    _rolling_thresholds,
    _scan_jsonl_file,
    _try_cached_file,
    calc_cost,
    extract_assistant_fields,
    find_pricing,
    tiered_cost,
    window_start_epoch,
    _parse_window_starts,
    _rec_cost,
)


# ---------------------------------------------------------------------------
# _parse_effective
# ---------------------------------------------------------------------------

class TestParseEffective:
    def test_date_only(self):
        dt = _parse_effective("2025-01-01")
        assert dt == datetime(2025, 1, 1, tzinfo=timezone.utc)

    def test_date_with_hour(self):
        dt = _parse_effective("2026-03-13T18")
        assert dt == datetime(2026, 3, 13, 18, tzinfo=timezone.utc)

    def test_returns_utc(self):
        dt = _parse_effective("2025-06-15")
        assert dt.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# find_pricing
# ---------------------------------------------------------------------------

class TestFindPricing:
    def test_exact_model_name(self):
        prices = find_pricing("claude-sonnet-4-20250514")
        assert prices is not None
        assert "input" in prices
        assert "output" in prices

    def test_alias_resolution(self):
        for alias, canonical in MODEL_ALIASES.items():
            prices = find_pricing(alias)
            assert prices is not None, f"Alias {alias!r} returned None"

    def test_unknown_model_returns_none(self):
        assert find_pricing("nonexistent-model-xyz") is None

    def test_historical_lookup_before_first_period(self):
        very_old = datetime(2020, 1, 1, tzinfo=timezone.utc)
        assert find_pricing("claude-sonnet-4-20250514", ts=very_old) is None

    def test_historical_lookup_in_first_period(self):
        ts = datetime(2025, 6, 1, tzinfo=timezone.utc)
        prices = find_pricing("claude-sonnet-4-20250514", ts=ts)
        assert prices is not None
        assert prices["input"] == 3e-06

    def test_pricing_period_transition(self):
        """Opus 4.6 had 200k tier before 2026-03-13T18, flat after."""
        before = datetime(2026, 3, 13, 17, tzinfo=timezone.utc)
        after = datetime(2026, 3, 13, 19, tzinfo=timezone.utc)

        prices_before = find_pricing("claude-opus-4-6", ts=before)
        prices_after = find_pricing("claude-opus-4-6", ts=after)

        assert prices_before is not None
        assert prices_after is not None
        # Before: had 200k tier keys
        assert "input_200k" in prices_before
        # After: flat pricing, no 200k keys
        assert "input_200k" not in prices_after

    def test_substring_matching(self):
        """Models with version suffixes should match via substring."""
        prices = find_pricing("claude-opus-4-6")
        assert prices is not None


# ---------------------------------------------------------------------------
# tiered_cost
# ---------------------------------------------------------------------------

class TestTieredCost:
    def test_below_threshold_no_tier(self):
        cost = tiered_cost(100_000, 3e-06, 6e-06)
        assert cost == pytest.approx(100_000 * 3e-06)

    def test_below_threshold_with_none_tier(self):
        cost = tiered_cost(100_000, 3e-06, None)
        assert cost == pytest.approx(100_000 * 3e-06)

    def test_at_threshold_exact(self):
        cost = tiered_cost(TIER_THRESHOLD, 3e-06, 6e-06)
        assert cost == pytest.approx(TIER_THRESHOLD * 3e-06)

    def test_above_threshold_with_tier(self):
        count = TIER_THRESHOLD + 50_000
        cost = tiered_cost(count, 3e-06, 6e-06)
        expected = TIER_THRESHOLD * 3e-06 + 50_000 * 6e-06
        assert cost == pytest.approx(expected)

    def test_above_threshold_none_tier_uses_base(self):
        count = TIER_THRESHOLD + 50_000
        cost = tiered_cost(count, 3e-06, None)
        assert cost == pytest.approx(count * 3e-06)

    def test_zero_tokens(self):
        assert tiered_cost(0, 3e-06, 6e-06) == 0.0

    def test_one_token(self):
        assert tiered_cost(1, 5e-06, 10e-06) == pytest.approx(5e-06)


# ---------------------------------------------------------------------------
# calc_cost
# ---------------------------------------------------------------------------

class TestCalcCost:
    def test_unknown_model_returns_zero(self):
        assert calc_cost(1000, 1000, 1000, 1000, "nonexistent") == 0.0

    def test_basic_cost_calculation(self):
        """Verify cost with known Sonnet 4 pricing (first period)."""
        ts = datetime(2025, 6, 1, tzinfo=timezone.utc)
        cost = calc_cost(
            input_tokens=10_000,
            output_tokens=5_000,
            cache_create_tokens=0,
            cache_read_tokens=0,
            model="claude-sonnet-4-20250514",
            ts=ts,
        )
        # input: 10_000 * 3e-06 = 0.03, output: 5_000 * 15e-06 = 0.075
        assert cost == pytest.approx(0.105)

    def test_all_token_types(self):
        ts = datetime(2025, 6, 1, tzinfo=timezone.utc)
        cost = calc_cost(
            input_tokens=1000,
            output_tokens=1000,
            cache_create_tokens=1000,
            cache_read_tokens=1000,
            model="claude-sonnet-4-20250514",
            ts=ts,
        )
        expected = (
            1000 * 3e-06     # input
            + 1000 * 15e-06  # output
            + 1000 * 3.75e-06  # cache_create
            + 1000 * 0.3e-06   # cache_read
        )
        assert cost == pytest.approx(expected)

    def test_tiered_pricing_kicks_in(self):
        """With 250K input tokens on Sonnet 4, tiered rate should apply."""
        ts = datetime(2025, 6, 1, tzinfo=timezone.utc)
        cost = calc_cost(
            input_tokens=250_000,
            output_tokens=0,
            cache_create_tokens=0,
            cache_read_tokens=0,
            model="claude-sonnet-4-20250514",
            ts=ts,
        )
        expected = TIER_THRESHOLD * 3e-06 + 50_000 * 6e-06
        assert cost == pytest.approx(expected)

    def test_no_tiered_rate_uses_flat(self):
        """Haiku has no 200k tier — flat rate for all tokens."""
        ts = datetime(2025, 6, 1, tzinfo=timezone.utc)
        cost = calc_cost(
            input_tokens=250_000,
            output_tokens=0,
            cache_create_tokens=0,
            cache_read_tokens=0,
            model="claude-haiku-4-5-20251001",
            ts=ts,
        )
        assert cost == pytest.approx(250_000 * 1e-06)

    def test_zero_tokens(self):
        assert calc_cost(0, 0, 0, 0, "claude-sonnet-4-20250514") == 0.0

    def test_flat_pricing_after_transition(self):
        """After 2026-03-13T18, Opus 4.6 uses flat pricing."""
        ts = datetime(2026, 4, 1, tzinfo=timezone.utc)
        cost = calc_cost(
            input_tokens=250_000,
            output_tokens=0,
            cache_create_tokens=0,
            cache_read_tokens=0,
            model="claude-opus-4-6",
            ts=ts,
        )
        # No tiered rate → all at base rate
        assert cost == pytest.approx(250_000 * 5e-06)


# ---------------------------------------------------------------------------
# window_start_epoch
# ---------------------------------------------------------------------------

class TestWindowStartEpoch:
    NOW = 1_700_000_000.0

    def test_past_reset_is_the_window_start(self):
        past = datetime.fromtimestamp(self.NOW - 600, tz=timezone.utc).isoformat()
        assert window_start_epoch(past, SESSION_WINDOW_S, self.NOW) == self.NOW - 600

    def test_future_reset_subtracts_the_window(self):
        future = datetime.fromtimestamp(self.NOW + 3600, tz=timezone.utc).isoformat()
        assert window_start_epoch(future, SESSION_WINDOW_S, self.NOW) == (
            self.NOW + 3600 - SESSION_WINDOW_S
        )
        assert window_start_epoch(future, WEEK_WINDOW_S, self.NOW) == (
            self.NOW + 3600 - WEEK_WINDOW_S
        )

    def test_naive_reset_counts_as_local_time(self):
        # Claude Code's stdin rate limits reach us as naive local ISO.
        naive = datetime.fromtimestamp(self.NOW + 3600).isoformat()  # noqa: DTZ006
        assert window_start_epoch(naive, SESSION_WINDOW_S, self.NOW) == (
            self.NOW + 3600 - SESSION_WINDOW_S
        )

    @pytest.mark.parametrize("value", [None, "", "not-a-date"])
    def test_unusable_input_returns_none(self, value):
        assert window_start_epoch(value, SESSION_WINDOW_S, self.NOW) is None

    def test_window_lengths(self):
        assert SESSION_WINDOW_S == 5 * 3600
        assert WEEK_WINDOW_S == 7 * 86400


# ---------------------------------------------------------------------------
# _parse_window_starts
# ---------------------------------------------------------------------------

class TestParseWindowStarts:
    def test_no_resets_returns_none_session_and_monday(self):
        session_start, week_start = _parse_window_starts(None, None)
        assert session_start is None
        assert week_start is not None
        # Week start should be a Monday at midnight
        assert week_start.weekday() == 0
        assert week_start.hour == 0
        assert week_start.minute == 0

    def test_past_session_reset_used_directly(self):
        past_iso = "2020-01-01T00:00:00+00:00"
        session_start, _ = _parse_window_starts(past_iso, None)
        assert session_start is not None
        assert session_start.year == 2020

    def test_future_session_reset_subtracts_window(self):
        future_iso = "2099-12-31T23:59:59+00:00"
        session_start, _ = _parse_window_starts(future_iso, None)
        assert session_start is not None
        # Should be 5 hours before the future reset
        expected_year = 2099
        assert session_start.year == expected_year

    def test_invalid_session_reset_returns_none(self):
        session_start, _ = _parse_window_starts("not-a-date", None)
        assert session_start is None

    def test_past_week_reset_used_directly(self):
        past_iso = "2020-01-06T00:00:00+00:00"
        _, week_start = _parse_window_starts(None, past_iso)
        assert week_start.year == 2020

    def test_future_week_reset_subtracts_7_days(self):
        future_iso = "2099-12-31T00:00:00+00:00"
        _, week_start = _parse_window_starts(None, future_iso)
        assert week_start.year == 2099
        assert week_start.day == 24  # 31 - 7

    def test_invalid_week_reset_falls_back_to_monday(self):
        _, week_start = _parse_window_starts(None, "garbage")
        assert week_start.weekday() == 0


# ---------------------------------------------------------------------------
# _rolling_thresholds / _bucket_rolling_cost
# ---------------------------------------------------------------------------

class TestRollingHelpers:
    def test_thresholds_has_all_window_names(self):
        now = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
        t = _rolling_thresholds(now)
        for w in ROLLING_WINDOWS:
            assert w.name in t

    def test_thresholds_are_ordered_oldest_first(self):
        now = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
        t = _rolling_thresholds(now)
        values = [t[w.name] for w in ROLLING_WINDOWS]
        # ROLLING_WINDOWS is longest→shortest, so thresholds should be ascending
        assert values == sorted(values)

    def test_bucket_accumulates_into_all_matching_windows(self):
        now = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
        t = _rolling_thresholds(now)
        totals: dict[str, float] = {}
        # Timestamp = now (within all windows)
        _bucket_rolling_cost(1.0, now.timestamp(), t, totals)
        for w in ROLLING_WINDOWS:
            assert totals[w.name] == 1.0

    def test_bucket_skips_windows_outside_range(self):
        now = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
        t = _rolling_thresholds(now)
        totals: dict[str, float] = {}
        # Timestamp = 20 days ago (only in thirty_day and seven_day? No, 20 > 7)
        old_ts = (now - timedelta(days=20)).timestamp()
        _bucket_rolling_cost(1.0, old_ts, t, totals)
        assert totals.get("thirty_day") == 1.0
        assert totals.get("seven_day") is None
        assert totals.get("six_hour") is None

    def test_bucket_with_project(self):
        now = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
        t = _rolling_thresholds(now)
        totals: dict[str, float] = {}
        proj: dict[str, float] = {}
        _bucket_rolling_cost(2.5, now.timestamp(), t, totals, proj, is_project=True)
        assert totals["six_hour"] == 2.5
        assert proj["six_hour"] == 2.5

    def test_bucket_no_project_when_false(self):
        now = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
        t = _rolling_thresholds(now)
        totals: dict[str, float] = {}
        proj: dict[str, float] = {}
        _bucket_rolling_cost(2.5, now.timestamp(), t, totals, proj, is_project=False)
        assert totals["six_hour"] == 2.5
        assert proj.get("six_hour") is None


# ---------------------------------------------------------------------------
# _rec_cost
# ---------------------------------------------------------------------------

class TestRecCost:
    def test_returns_stored_cost_if_present(self):
        rec = {"cost": 1.23, "t": [100, 200, 300, 400], "model": "x"}
        assert _rec_cost(rec) == 1.23

    def test_zero_cost_recomputes(self):
        rec = {
            "cost": 0,
            "t": [10_000, 5_000, 0, 0],
            "model": "claude-sonnet-4-20250514",
            "ts": datetime(2025, 6, 1, tzinfo=timezone.utc).timestamp(),
        }
        result = _rec_cost(rec)
        assert result > 0
        assert result == pytest.approx(0.105)  # 10k*3e-6 + 5k*15e-6

    def test_none_cost_recomputes(self):
        rec = {
            "cost": None,
            "t": [1000, 0, 0, 0],
            "model": "claude-sonnet-4-20250514",
            "ts": datetime(2025, 6, 1, tzinfo=timezone.utc).timestamp(),
        }
        assert _rec_cost(rec) == pytest.approx(1000 * 3e-06)

    def test_missing_tokens_returns_zero(self):
        assert _rec_cost({}) == 0.0
        assert _rec_cost({"t": [1, 2]}) == 0.0
        assert _rec_cost({"t": None}) == 0.0

    def test_missing_ts_still_computes(self):
        rec = {"cost": None, "t": [1000, 0, 0, 0], "model": "claude-sonnet-4-20250514"}
        assert _rec_cost(rec) > 0


# ---------------------------------------------------------------------------
# Data integrity
# ---------------------------------------------------------------------------

class TestPricingDataIntegrity:
    def test_pricing_history_chronological(self):
        """PRICING_HISTORY entries should be in chronological order."""
        dates = [_parse_effective(p["effective"]) for p in PRICING_HISTORY]
        for i in range(1, len(dates)):
            assert dates[i] > dates[i - 1], (
                f"Period {i} ({dates[i]}) is not after period {i-1} ({dates[i-1]})"
            )

    def test_all_models_have_required_keys(self):
        """Every model pricing must have at least input and output."""
        for period in PRICING_HISTORY:
            for model, prices in period["models"].items():
                assert "input" in prices, f"{model} missing 'input'"
                assert "output" in prices, f"{model} missing 'output'"

    def test_all_aliases_resolve_to_known_model(self):
        """Every alias target must exist in at least one pricing period."""
        all_models = set()
        for period in PRICING_HISTORY:
            all_models.update(period["models"].keys())
        for alias, target in MODEL_ALIASES.items():
            assert target in all_models, f"Alias {alias!r} → {target!r} not in any period"

    def test_tiered_rates_are_higher_than_base(self):
        """200k tier rates should be >= base rates (they're premiums)."""
        for period in PRICING_HISTORY:
            for model, prices in period["models"].items():
                for key in ("input", "output", "cache_create", "cache_read"):
                    tiered_key = f"{key}_200k"
                    if tiered_key in prices:
                        assert prices[tiered_key] >= prices[key], (
                            f"{model}.{tiered_key} ({prices[tiered_key]}) < "
                            f"{model}.{key} ({prices[key]})"
                        )

    def test_tier_threshold_is_200k(self):
        assert TIER_THRESHOLD == 200_000


# ---------------------------------------------------------------------------
# extract_assistant_fields
# ---------------------------------------------------------------------------

class TestExtractAssistantFields:
    def _make_rec(self, **overrides):
        rec = {
            "type": "assistant",
            "timestamp": "2025-06-15T12:00:00+00:00",
            "requestId": "req-1",
            "message": {
                "id": "msg-1",
                "model": "claude-sonnet-4-20250514",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                },
            },
        }
        rec.update(overrides)
        return rec

    def test_valid_record(self):
        result = extract_assistant_fields(self._make_rec())
        assert result is not None
        msg, usage, mid, rid, dk, ts = result
        assert mid == "msg-1"
        assert rid == "req-1"
        assert dk == "msg-1:req-1"
        assert usage["input_tokens"] == 100
        assert ts.tzinfo is not None

    def test_non_assistant_returns_none(self):
        assert extract_assistant_fields(self._make_rec(type="human")) is None

    def test_missing_message_returns_none(self):
        rec = self._make_rec()
        rec["message"] = None
        assert extract_assistant_fields(rec) is None

    def test_missing_usage_returns_none(self):
        rec = self._make_rec()
        rec["message"]["usage"] = None
        assert extract_assistant_fields(rec) is None

    def test_invalid_timestamp_returns_none(self):
        assert extract_assistant_fields(self._make_rec(timestamp="nope")) is None

    def test_missing_ids_gives_none_dedup_key(self):
        rec = self._make_rec()
        rec["message"]["id"] = ""
        result = extract_assistant_fields(rec)
        assert result is not None
        assert result[4] is None  # dedup_key

    def test_naive_timestamp_gets_utc(self):
        rec = self._make_rec(timestamp="2025-06-15T12:00:00")
        result = extract_assistant_fields(rec)
        assert result is not None
        assert result[5].tzinfo is not None


# ---------------------------------------------------------------------------
# _try_cached_file
# ---------------------------------------------------------------------------

class TestTryCachedFile:
    """Tests for the cache-hit helper extracted from compute_costs."""

    NOW = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)

    @pytest.fixture()
    def thresholds(self):
        return _rolling_thresholds(self.NOW)

    @pytest.fixture()
    def accumulators(self):
        return {"rolling": {}, "proj": {}, "seen": set()}

    def _make_ctx(self, **overrides) -> _FileContext:
        defaults = dict(
            key="/tmp/test.jsonl",
            is_session_file=False,
            is_project_file=False,
            in_session_window=False,
            in_rolling_window=False,
            file_unchanged=True,
            ccr_fresh=False,
        )
        defaults.update(overrides)
        return _FileContext(**defaults)

    def _make_cached(self, **overrides) -> dict:
        defaults = {
            "mtime_ns": 100,
            "size": 200,
            "week_cost": 1.5,
            "month_cost": 2.0,
            "all_time_cost": 10.0,
            "session_cost": 0.5,
            "dedup_keys": ["k1", "k2"],
        }
        defaults.update(overrides)
        return defaults

    def test_returns_none_when_file_changed(self, thresholds, accumulators):
        ctx = self._make_ctx(file_unchanged=False)
        result = _try_cached_file(
            ctx, self._make_cached(), {}, accumulators["seen"],
            thresholds, None, thresholds["thirty_day"],
            accumulators["rolling"], accumulators["proj"],
        )
        assert result is None

    def test_returns_none_when_no_cache_entry(self, thresholds, accumulators):
        ctx = self._make_ctx()
        result = _try_cached_file(
            ctx, None, {}, accumulators["seen"],
            thresholds, None, thresholds["thirty_day"],
            accumulators["rolling"], accumulators["proj"],
        )
        assert result is None

    def test_cache_hit_outside_all_windows(self, thresholds, accumulators):
        ctx = self._make_ctx(in_rolling_window=False, in_session_window=False)
        rolling = accumulators["rolling"]
        result = _try_cached_file(
            ctx, self._make_cached(), {}, accumulators["seen"],
            thresholds, None, thresholds["thirty_day"],
            rolling, accumulators["proj"],
        )
        assert result is not None
        assert result.week == 1.5
        assert result.month == 2.0
        assert result.session_window == 0.0
        assert rolling["all_time"] == 10.0
        assert accumulators["seen"] == {"k1", "k2"}

    def test_cache_hit_session_file_returns_session_cost(self, thresholds, accumulators):
        ctx = self._make_ctx(is_session_file=True)
        result = _try_cached_file(
            ctx, self._make_cached(), {}, accumulators["seen"],
            thresholds, None, thresholds["thirty_day"],
            accumulators["rolling"], accumulators["proj"],
        )
        assert result is not None
        assert result.session == 0.5

    def test_cache_hit_non_session_file_zero_session(self, thresholds, accumulators):
        ctx = self._make_ctx(is_session_file=False)
        result = _try_cached_file(
            ctx, self._make_cached(), {}, accumulators["seen"],
            thresholds, None, thresholds["thirty_day"],
            accumulators["rolling"], accumulators["proj"],
        )
        assert result is not None
        assert result.session == 0.0

    def test_returns_none_when_in_rolling_and_no_ccr(self, thresholds, accumulators):
        ctx = self._make_ctx(in_rolling_window=True, ccr_fresh=False)
        result = _try_cached_file(
            ctx, self._make_cached(), {}, accumulators["seen"],
            thresholds, None, thresholds["thirty_day"],
            accumulators["rolling"], accumulators["proj"],
        )
        assert result is None

    def test_branch3_ccr_fresh_computes_rolling(self, thresholds, accumulators):
        now_ts = self.NOW.timestamp()
        ctx = self._make_ctx(
            in_rolling_window=True, ccr_fresh=True, is_project_file=True,
        )
        ccr_records = {
            ctx.key: [
                {"dk": "r1", "ts": now_ts, "cost": 3.0, "t": [1, 1, 0, 0], "model": "x"},
            ]
        }
        rolling = accumulators["rolling"]
        proj = accumulators["proj"]
        result = _try_cached_file(
            ctx, self._make_cached(), ccr_records, accumulators["seen"],
            thresholds, None, thresholds["thirty_day"],
            rolling, proj,
        )
        assert result is not None
        assert result.week == 1.5  # from cache
        assert rolling.get("six_hour", 0.0) == 3.0
        assert proj.get("six_hour", 0.0) == 3.0
        assert "r1" in accumulators["seen"]

    def test_branch3_skips_duplicate_keys(self, thresholds, accumulators):
        now_ts = self.NOW.timestamp()
        ctx = self._make_ctx(in_rolling_window=True, ccr_fresh=True)
        accumulators["seen"].add("dup1")
        ccr_records = {
            ctx.key: [
                {"dk": "dup1", "ts": now_ts, "cost": 5.0, "t": [1, 1, 0, 0], "model": "x"},
            ]
        }
        rolling = accumulators["rolling"]
        _try_cached_file(
            ctx, self._make_cached(), ccr_records, accumulators["seen"],
            thresholds, None, thresholds["thirty_day"],
            rolling, accumulators["proj"],
        )
        assert rolling.get("six_hour", 0.0) == 0.0


# ---------------------------------------------------------------------------
# _scan_jsonl_file
# ---------------------------------------------------------------------------

class TestScanJsonlFile:
    """Tests for the JSONL scanning helper extracted from compute_costs."""

    NOW = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)

    @pytest.fixture()
    def thresholds(self):
        return _rolling_thresholds(self.NOW)

    def test_empty_file(self, tmp_path, thresholds):
        f = tmp_path / "empty.jsonl"
        f.write_text("")
        result = _scan_jsonl_file(
            f, is_session_file=False, session_window_start=None,
            week_window_start=self.NOW - timedelta(days=7),
            month_window_start=self.NOW.replace(day=1),
            thresholds=thresholds, seen_keys=set(),
        )
        assert result.all_time_cost == 0.0
        assert result.dedup_keys == []

    def test_nonexistent_file(self, tmp_path, thresholds):
        f = tmp_path / "nope.jsonl"
        result = _scan_jsonl_file(
            f, is_session_file=False, session_window_start=None,
            week_window_start=self.NOW - timedelta(days=7),
            month_window_start=self.NOW.replace(day=1),
            thresholds=thresholds, seen_keys=set(),
        )
        assert result.all_time_cost == 0.0


# ---------------------------------------------------------------------------
# compute_costs — session-window key presence
# ---------------------------------------------------------------------------

class TestComputeCostsSessionWindowKey:
    """session_window_cost must be absent, not 0.0, without a reset time.

    Callers merge the result over existing data, so a placeholder zero would
    overwrite a real total computed by a caller that had the reset (macsetup-4uja).
    """

    @pytest.fixture()
    def isolated(self, monkeypatch, tmp_path):
        import cache_db
        import pricing

        projects = tmp_path / "projects"
        projects.mkdir()
        (projects / "chat.jsonl").write_text("")
        monkeypatch.setattr(pricing, "_get_projects_dirs", lambda: [projects])
        monkeypatch.setattr(cache_db, "load_cost_cache", lambda *a, **k: {})
        monkeypatch.setattr(cache_db, "bulk_load_ccreport_cache", lambda: ({}, {}))
        monkeypatch.setattr(cache_db, "bulk_save_file_costs", lambda *a, **k: None)
        written: list[dict] = []
        monkeypatch.setattr(
            cache_db, "write_cost_summary", lambda costs, cwd=None: written.append(costs),
        )
        return written

    def test_omitted_without_reset(self, isolated):
        from pricing import compute_costs

        result = compute_costs()
        assert "session_window_cost" not in result
        assert "week_cost" in result
        assert isolated and "session_window_cost" not in isolated[-1]

    def test_present_with_reset(self, isolated):
        from pricing import compute_costs

        reset = (datetime.now(tz=timezone.utc) + timedelta(hours=2)).isoformat()
        result = compute_costs(session_reset_iso=reset)
        assert result["session_window_cost"] == 0.0
        assert "session_window_cost" in isolated[-1]


# ---------------------------------------------------------------------------
# compute_costs — incremental saves
# ---------------------------------------------------------------------------

class TestComputeCostsSavesOnlyChangedFiles:
    """One appended line must not rewrite the whole cost cache (macsetup-5vsf)."""

    @pytest.fixture()
    def projects(self, monkeypatch, tmp_path):
        import pricing

        d = tmp_path / "projects" / "-tmp-proj"
        d.mkdir(parents=True)
        monkeypatch.setattr(pricing, "_get_projects_dirs", lambda: [d])
        return d

    def _append(self, path, mid: str) -> None:
        import json

        with open(path, "a") as fh:
            fh.write(json.dumps({
                "type": "assistant",
                "timestamp": datetime.now(tz=timezone.utc).isoformat(),
                "requestId": f"req-{mid}", "sessionId": "s1", "cwd": "/tmp/proj",
                "message": {"id": mid, "model": "claude-opus-5",
                            "usage": {"input_tokens": 10, "output_tokens": 5}},
            }) + "\n")

    def _saves(self, monkeypatch) -> list:
        import cache_db

        calls: list = []
        real = cache_db.bulk_save_file_costs

        def spy(entries, week_key, month_key, changed=None, **kwargs):
            calls.append(changed)
            real(entries, week_key, month_key, changed=changed, **kwargs)

        monkeypatch.setattr(cache_db, "bulk_save_file_costs", spy)
        return calls

    def test_only_the_grown_file_is_rewritten(self, projects, monkeypatch):
        import cache_db
        from pricing import compute_costs

        a, b = projects / "a.jsonl", projects / "b.jsonl"
        self._append(a, "msg-a")
        self._append(b, "msg-b")
        compute_costs()

        conn = cache_db.get_connection()
        # A key only the table knows about: it survives iff b's row is left alone.
        conn.execute(
            "INSERT INTO dedup_keys (dk, file_path) VALUES ('ghost', ?)", (str(b),))
        conn.commit()

        calls = self._saves(monkeypatch)
        self._append(a, "msg-a2")
        compute_costs()

        assert calls == [{str(a)}]
        keys = dict(conn.execute("SELECT file_path, count(*) FROM dedup_keys GROUP BY 1"))
        assert keys[str(b)] == 2, "b keeps its own key and the ghost"
        assert keys[str(a)] == 2, "a is rebuilt from its two messages"

    def test_a_departed_file_leaves_the_cache(self, projects, monkeypatch):
        import cache_db
        from pricing import compute_costs

        a, b = projects / "a.jsonl", projects / "b.jsonl"
        self._append(a, "msg-a")
        self._append(b, "msg-b")
        compute_costs()

        b.unlink()
        compute_costs()
        conn = cache_db.get_connection()
        paths = {r[0] for r in conn.execute("SELECT path FROM file_costs")}
        assert paths == {str(a)}
        assert conn.execute(
            "SELECT count(*) FROM dedup_keys WHERE file_path = ?", (str(b),)
        ).fetchone()[0] == 0


# ---------------------------------------------------------------------------
# Per-render reads scoped to one project (macsetup-45iv)
# ---------------------------------------------------------------------------

class TestPerRenderScoping:
    """The statusline renders one project, so it must read only that project.

    Both functions here run on every render and used to load the whole
    ccreport_records table — ~89K rows on a real machine — to keep one
    project's or one session's share of it.
    """

    CWD = "/tmp/proj"
    # cwd → projects-dir name is a "/"→"-" swap, so this sibling project's
    # directory has the target's directory name as a string prefix.
    SIBLING_CWD = "/tmp/proj-other"

    @pytest.fixture()
    def projects_dir(self, monkeypatch, tmp_path):
        import cache_db
        import pricing

        d = tmp_path / "projects"
        (d / "-tmp-proj").mkdir(parents=True)
        (d / "-tmp-proj-other").mkdir(parents=True)
        monkeypatch.setattr(pricing, "_get_projects_dirs", lambda: [d])
        cache_db.init_ccreport_meta(1, "test-hash")
        return d

    def _orphan(self, path: str, *, sid: str, cost: float, ts: float | None = None) -> None:
        """Cache a record under *path* with no file on disk to back it."""
        import cache_db

        cache_db.save_ccreport_file(path, 1, 1, [{
            "mid": "m", "model": "claude-opus-5",
            "ts": ts if ts is not None else datetime.now(tz=timezone.utc).timestamp(),
            "sid": sid, "project": "proj", "cwd": self.CWD, "repo": None,
            "dk": None, "cost": cost, "t": [1, 1, 0, 0],
        }])

    def test_orphaned_project_costs_still_reach_the_totals(self, projects_dir):
        from pricing import compute_project_rolling_costs

        self._orphan(str(projects_dir / "-tmp-proj" / "gone.jsonl"), sid="s1", cost=3.0)
        totals = compute_project_rolling_costs(self.CWD)
        assert totals["all_time_project_cost"] == 3.0
        assert totals["twenty_four_hour_project_cost"] == 3.0

    def test_a_sibling_project_sharing_the_prefix_is_not_counted(self, projects_dir):
        from pricing import compute_project_rolling_costs

        self._orphan(str(projects_dir / "-tmp-proj" / "gone.jsonl"), sid="s1", cost=3.0)
        self._orphan(
            str(projects_dir / "-tmp-proj-other" / "gone.jsonl"), sid="s1", cost=99.0)
        assert compute_project_rolling_costs(self.CWD)["all_time_project_cost"] == 3.0
        assert compute_project_rolling_costs(
            self.SIBLING_CWD)["all_time_project_cost"] == 99.0

    def test_a_live_file_is_not_also_counted_as_an_orphan(self, projects_dir):
        import json

        from pricing import compute_project_rolling_costs

        live = projects_dir / "-tmp-proj" / "live.jsonl"
        live.write_text(json.dumps({
            "type": "assistant",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "requestId": "r1", "sessionId": "s1", "cwd": self.CWD,
            "message": {"id": "msg-1", "model": "claude-opus-5",
                        "usage": {"input_tokens": 10, "output_tokens": 5}},
        }) + "\n")
        self._orphan(str(live), sid="s1", cost=50.0)
        # The cached row is for a path still on disk, so the JSONL scan owns it
        # and the orphan pass must skip it — 50.0 would be the double count.
        assert compute_project_rolling_costs(self.CWD)["all_time_project_cost"] < 1.0

    def test_the_project_scan_reads_no_other_projects_rows(self, projects_dir, monkeypatch):
        import cache_db
        from pricing import compute_project_rolling_costs

        self._orphan(str(projects_dir / "-tmp-proj" / "gone.jsonl"), sid="s1", cost=3.0)
        self._orphan(
            str(projects_dir / "-tmp-proj-other" / "gone.jsonl"), sid="s1", cost=99.0)

        def no_full_scans():
            raise AssertionError("a render must not load the whole table")

        monkeypatch.setattr(cache_db, "bulk_load_ccreport_cache", no_full_scans)
        assert compute_project_rolling_costs(self.CWD)["all_time_project_cost"] == 3.0

    def test_the_purged_session_fallback_sums_only_that_session(self, projects_dir):
        from pricing import compute_session_cost

        self._orphan(str(projects_dir / "-tmp-proj" / "a.jsonl"), sid="s1", cost=3.0)
        self._orphan(str(projects_dir / "-tmp-proj" / "b.jsonl"), sid="s2", cost=7.0)
        assert compute_session_cost("s1", self.CWD) == 3.0
        assert compute_session_cost("s2", self.CWD) == 7.0

    def test_the_purged_session_fallback_stays_inside_the_project(self, projects_dir):
        from pricing import compute_session_cost

        # Same session id, other project's directory: the loader is not scoped
        # by path, so compute_session_cost's own prefix filter has to hold.
        self._orphan(str(projects_dir / "-tmp-proj" / "a.jsonl"), sid="s1", cost=3.0)
        self._orphan(
            str(projects_dir / "-tmp-proj-other" / "a.jsonl"), sid="s1", cost=99.0)
        assert compute_session_cost("s1", self.CWD) == 3.0

    def test_the_session_fallback_reads_no_other_sessions_rows(
        self, projects_dir, monkeypatch,
    ):
        import cache_db
        from pricing import compute_session_cost

        self._orphan(str(projects_dir / "-tmp-proj" / "a.jsonl"), sid="s1", cost=3.0)

        def no_full_scans():
            raise AssertionError("a render must not load the whole table")

        monkeypatch.setattr(cache_db, "bulk_load_ccreport_cache", no_full_scans)
        assert compute_session_cost("s1", self.CWD) == 3.0

    def test_a_mismatched_salt_degrades_to_no_orphans(self, projects_dir):
        import cache_db
        from pricing import compute_project_rolling_costs, compute_session_cost

        self._orphan(str(projects_dir / "-tmp-proj" / "gone.jsonl"), sid="s1", cost=3.0)
        conn = cache_db.get_connection()
        cache_db._set_meta(conn, "ccreport_schema_salt", "not-the-salt")
        conn.commit()
        assert compute_project_rolling_costs(self.CWD)["all_time_project_cost"] == 0.0
        assert compute_session_cost("s1", self.CWD) == 0.0
        # Degraded, not repaired: the row a re-parse could never rebuild is intact.
        assert conn.execute(
            "SELECT cost FROM ccreport_records").fetchone()[0] == 3.0


# ---------------------------------------------------------------------------
# One definition of which project a record belongs to (macsetup-2qrp)
# ---------------------------------------------------------------------------

class TestPathInProject:
    def test_a_sibling_sharing_the_string_prefix_is_excluded(self):
        from pathlib import Path

        from pricing import path_in_project, project_path_prefixes

        prefixes = project_path_prefixes("/tmp/proj", [Path("/root")])
        assert prefixes == ["/root/-tmp-proj/"]
        assert path_in_project("/root/-tmp-proj/s.jsonl", prefixes)
        # The separator every prefix ends in is the whole defence here, and it
        # is also what makes cache_db.prefix_range's bounds agree with this.
        assert not path_in_project("/root/-tmp-proj-other/s.jsonl", prefixes)

    def test_no_prefixes_matches_nothing(self):
        from pricing import path_in_project

        assert not path_in_project("/root/-tmp-proj/s.jsonl", [])


class TestMergedProjectsShareTheirCostWindows:
    """`ccreport merge` has to mean one project for the statusline too.

    Before macsetup-2qrp a merge regrouped the reports and left the per-project
    cost windows split, because pricing matched on a path prefix and a cwd
    basename and knew nothing about the override table.
    """

    CWD = "/tmp/proj"
    OTHER_CWD = "/tmp/other"

    @pytest.fixture()
    def projects_dir(self, monkeypatch, tmp_path):
        import cache_db
        import pricing

        d = tmp_path / "projects"
        (d / "-tmp-proj").mkdir(parents=True)
        (d / "-tmp-other").mkdir(parents=True)
        monkeypatch.setattr(pricing, "_get_projects_dirs", lambda: [d])
        cache_db.init_ccreport_meta(1, "test-hash")
        return d

    @staticmethod
    def _merge(monkeypatch, source: str, target: str, kind: str = "name") -> None:
        import cache_db

        monkeypatch.setattr(cache_db, "get_project_overrides", lambda: [
            {"id": 1, "match_kind": kind, "match_value": source, "target": target},
        ])

    @staticmethod
    def _orphan(path: str, *, project: str, cwd: str | None, cost: float) -> None:
        import cache_db

        cache_db.save_ccreport_file(path, 1, 1, [{
            "mid": "m", "model": "claude-opus-5",
            "ts": datetime.now(tz=timezone.utc).timestamp(),
            "sid": "s1", "project": project, "cwd": cwd, "repo": None,
            # Distinct per project: dedup is global, so a shared key would
            # drop the second record and hide whether the scope found it.
            "dk": f"m:{project}", "cost": cost, "t": [1, 1, 0, 0],
        }])

    def _both_projects(self, projects_dir) -> None:
        self._orphan(str(projects_dir / "-tmp-proj" / "gone.jsonl"),
                     project="proj", cwd=self.CWD, cost=3.0)
        self._orphan(str(projects_dir / "-tmp-other" / "gone.jsonl"),
                     project="other", cwd=self.OTHER_CWD, cost=99.0)

    def test_a_merged_projects_costs_reach_the_targets_window(
        self, projects_dir, monkeypatch,
    ):
        from pricing import compute_project_rolling_costs

        self._both_projects(projects_dir)
        self._merge(monkeypatch, "other", "proj")
        assert compute_project_rolling_costs(
            self.CWD)["all_time_project_cost"] == 102.0

    def test_the_merged_side_lands_on_the_target_too(self, projects_dir, monkeypatch):
        """Standing in the directory that was merged away sees the same total."""
        from pricing import compute_project_rolling_costs

        self._both_projects(projects_dir)
        self._merge(monkeypatch, "other", "proj")
        assert compute_project_rolling_costs(
            self.OTHER_CWD)["all_time_project_cost"] == 102.0

    def test_without_a_rule_the_two_projects_stay_apart(self, projects_dir, monkeypatch):
        import cache_db
        from pricing import compute_project_rolling_costs

        self._both_projects(projects_dir)
        monkeypatch.setattr(cache_db, "get_project_overrides", lambda: [])
        assert compute_project_rolling_costs(
            self.CWD)["all_time_project_cost"] == 3.0
        assert compute_project_rolling_costs(
            self.OTHER_CWD)["all_time_project_cost"] == 99.0

    def test_an_unrelated_project_is_not_dragged_in(self, projects_dir, monkeypatch):
        from pricing import compute_project_rolling_costs

        self._both_projects(projects_dir)
        (projects_dir / "-tmp-third").mkdir()
        self._orphan(str(projects_dir / "-tmp-third" / "gone.jsonl"),
                     project="third", cwd="/tmp/third", cost=7.0)
        self._merge(monkeypatch, "other", "proj")
        assert compute_project_rolling_costs(
            self.CWD)["all_time_project_cost"] == 102.0

    def test_a_purged_record_reaches_the_target_by_name_alone(
        self, projects_dir, monkeypatch,
    ):
        """No cwd, no repo, and a path outside every project dir — name only."""
        from pricing import compute_costs

        self._orphan("/gone.jsonl", project="other", cwd=None, cost=42.0)
        self._merge(monkeypatch, "other", "proj")
        assert compute_costs(cwd=self.CWD)["all_time_project_cost"] == 42.0

    def test_the_cwds_own_name_is_resolved_before_the_comparison(
        self, projects_dir, monkeypatch,
    ):
        """Both sides go through the rules, so a merge of the cwd itself holds."""
        from pricing import compute_costs

        self._orphan("/gone.jsonl", project="archive", cwd=None, cost=5.0)
        # The cwd's own project is what gets merged away this time.
        self._merge(monkeypatch, "proj", "archive")
        assert compute_costs(cwd=self.CWD)["all_time_project_cost"] == 5.0

    def test_the_table_is_read_once_per_computation(self, projects_dir, monkeypatch):
        import cache_db
        from pricing import compute_project_rolling_costs

        self._both_projects(projects_dir)
        reads = []
        rules = [{"id": 1, "match_kind": "name",
                  "match_value": "other", "target": "proj"}]

        def counted():
            reads.append(1)
            return rules

        monkeypatch.setattr(cache_db, "get_project_overrides", counted)
        compute_project_rolling_costs(self.CWD)
        assert reads == [1], "one read per compute, not one per record"


class TestTheResolvedScopeIsCachedPerCwd:
    """Resolving a merged scope reads every cached file's identity.

    That GROUP BY was 0.020s of an 0.085s statusline call, repeated on every
    render for an answer that only moves when a rule or a record does
    (macsetup-6cov). These tests pin both halves: the second render skips the
    scan, and a change to either input still reaches it.
    """

    CWD = "/tmp/proj"

    @pytest.fixture()
    def merged(self, monkeypatch, tmp_path):
        """One record in a second project, merged into the cwd's by name."""
        import cache_db
        import pricing

        d = tmp_path / "projects"
        (d / "-tmp-proj").mkdir(parents=True)
        (d / "-tmp-other").mkdir(parents=True)
        monkeypatch.setattr(pricing, "_get_projects_dirs", lambda: [d])
        cache_db.init_ccreport_meta(1, "test-hash")
        cache_db.save_ccreport_file(str(d / "-tmp-other" / "gone.jsonl"), 1, 1, [{
            "mid": "m", "model": "claude-opus-5", "ts": 1.5, "sid": "s1",
            "project": "other", "cwd": "/tmp/other", "repo": None,
            "dk": "dk1", "cost": 1.0, "t": [1, 1, 0, 0],
        }])
        cache_db.add_project_override("name", "other", "proj")
        return d

    @staticmethod
    def _merged_prefix(projects_dir) -> str:
        return str(projects_dir / "-tmp-other") + "/"

    @staticmethod
    def _scope_rows() -> int:
        import cache_db

        return cache_db.get_connection().execute(
            "SELECT COUNT(*) FROM project_scopes").fetchone()[0]

    def test_a_second_call_answers_without_rescanning_the_identities(
        self, merged, monkeypatch,
    ):
        import pricing

        scans = []
        real = pricing._file_identities
        monkeypatch.setattr(
            pricing, "_file_identities",
            lambda: (scans.append(1), real())[1],
        )
        first = pricing.project_scope(self.CWD, [merged])
        second = pricing.project_scope(self.CWD, [merged])
        assert scans == [1], "the identities are scanned once, not once per call"
        assert (second.name, second.prefixes) == (first.name, first.prefixes)
        # The merged directory is the part only the scan could have found, so
        # its survival is what says the cached answer is the real one.
        assert self._merged_prefix(merged) in second.prefixes

    def test_a_rule_change_rederives_the_scope(self, merged):
        import cache_db
        import pricing

        assert pricing.project_scope(self.CWD, [merged]).name == "proj"
        cache_db.delete_project_override("other")
        cache_db.add_project_override("name", "proj", "archive")
        again = pricing.project_scope(self.CWD, [merged])
        assert again.name == "archive"
        assert self._merged_prefix(merged) not in again.prefixes

    def test_a_newly_cached_record_rederives_the_scope(self, merged, tmp_path):
        import cache_db
        import pricing

        (tmp_path / "projects" / "-tmp-third").mkdir()
        assert self._merged_prefix(merged) in pricing.project_scope(
            self.CWD, [merged]).prefixes
        cache_db.add_project_override("name", "third", "proj")
        cache_db.save_ccreport_file(
            str(merged / "-tmp-third" / "gone.jsonl"), 1, 1, [{
                "mid": "m2", "model": "claude-opus-5", "ts": 1.5, "sid": "s2",
                "project": "third", "cwd": "/tmp/third", "repo": None,
                "dk": "dk2", "cost": 1.0, "t": [1, 1, 0, 0],
            }])
        assert str(merged / "-tmp-third") + "/" in pricing.project_scope(
            self.CWD, [merged]).prefixes

    def test_with_no_rules_nothing_is_cached(self, merged):
        import cache_db
        import pricing

        cache_db.delete_project_override("other")
        assert pricing.project_scope(self.CWD, [merged]).name == "proj"
        # Without rules the scope is the cwd's own directory and costs one
        # table read; a row here would be an invalidation liability for nothing.
        assert self._scope_rows() == 0

    def test_a_scope_that_predates_a_projects_dir_is_rederived(
        self, merged, tmp_path,
    ):
        import pricing

        pricing.project_scope(self.CWD, [merged])
        second = tmp_path / "projects2"
        (second / "-tmp-proj").mkdir(parents=True)
        scope = pricing.project_scope(self.CWD, [merged, second])
        assert str(second / "-tmp-proj") + "/" in scope.prefixes

    def test_a_failing_cache_write_still_yields_the_scope(self, merged, monkeypatch):
        import sqlite3

        import cache_db
        import pricing

        def locked(*_args, **_kw):
            raise sqlite3.OperationalError("database is locked")

        monkeypatch.setattr(cache_db, "save_project_scope", locked)
        scope = pricing.project_scope(self.CWD, [merged])
        assert scope.name == "proj"
        assert self._merged_prefix(merged) in scope.prefixes


# ---------------------------------------------------------------------------
# dk-NULL records still have to dedupe (macsetup-2wgm)
# ---------------------------------------------------------------------------

class TestFallbackDedupIdentity:
    """dk is NULL when the source log carried no message id or requestId.

    Read-time dedup used to skip those records entirely, so a duplicate row
    among them counted twice into every cost total it reached.
    """

    CWD = "/tmp/proj"

    @pytest.fixture()
    def projects_dir(self, monkeypatch, tmp_path):
        import cache_db
        import pricing

        d = tmp_path / "projects"
        (d / "-tmp-proj").mkdir(parents=True)
        monkeypatch.setattr(pricing, "_get_projects_dirs", lambda: [d])
        monkeypatch.setattr(cache_db, "get_project_overrides", lambda: [])
        cache_db.init_ccreport_meta(1, "test-hash")
        return d

    def _rows(self, projects_dir, *rows: dict) -> None:
        import cache_db

        ts = datetime.now(tz=timezone.utc).timestamp()
        cache_db.save_ccreport_file(
            str(projects_dir / "-tmp-proj" / "gone.jsonl"), 1, 1,
            [{"mid": "m", "model": "claude-opus-5", "ts": ts, "sid": "s1",
              "project": "proj", "cwd": self.CWD, "repo": None,
              "dk": None, "cost": 1.0, "t": [1, 1, 0, 0], **r} for r in rows],
        )

    def test_two_identical_dk_null_rows_count_once(self, projects_dir):
        from pricing import compute_project_rolling_costs

        self._rows(projects_dir, {}, {})
        assert compute_project_rolling_costs(
            self.CWD)["all_time_project_cost"] == 1.0

    def test_one_differing_token_count_keeps_them_apart(self, projects_dir):
        """A streaming message's chunks differ exactly here."""
        from pricing import compute_project_rolling_costs

        self._rows(projects_dir, {"t": [1, 1, 0, 0]}, {"t": [1, 2, 0, 0]})
        assert compute_project_rolling_costs(
            self.CWD)["all_time_project_cost"] == 2.0

    def test_a_different_session_keeps_them_apart(self, projects_dir):
        from pricing import compute_project_rolling_costs

        self._rows(projects_dir, {}, {"sid": "s2"})
        assert compute_project_rolling_costs(
            self.CWD)["all_time_project_cost"] == 2.0

    def test_rows_carrying_a_dedup_key_are_untouched(self, projects_dir):
        from pricing import compute_project_rolling_costs

        self._rows(projects_dir, {"dk": "m:r1"}, {"dk": "m:r2"})
        assert compute_project_rolling_costs(
            self.CWD)["all_time_project_cost"] == 2.0

    def test_the_same_dedup_key_still_collapses(self, projects_dir):
        from pricing import compute_project_rolling_costs

        self._rows(projects_dir, {"dk": "m:r1"}, {"dk": "m:r1"})
        assert compute_project_rolling_costs(
            self.CWD)["all_time_project_cost"] == 1.0

    def test_the_purged_session_fallback_dedupes_the_same_way(self, projects_dir):
        from pricing import compute_session_cost

        self._rows(projects_dir, {}, {})
        assert compute_session_cost("s1", self.CWD) == 1.0

    def test_a_live_jsonl_scan_dedupes_the_same_way(self, projects_dir):
        import json

        from pricing import compute_project_rolling_costs

        line = json.dumps({
            "type": "assistant",
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "sessionId": "s1", "cwd": self.CWD,
            "message": {"id": "msg-1", "model": "claude-opus-5",
                        "usage": {"input_tokens": 1000, "output_tokens": 0}},
        })
        live = projects_dir / "-tmp-proj" / "live.jsonl"
        # No requestId, so extract_assistant_fields leaves dk NULL.
        live.write_text(line + "\n" + line + "\n")
        once = 1000 * 5e-06
        assert compute_project_rolling_costs(
            self.CWD)["all_time_project_cost"] == round(once, 4)


# ---------------------------------------------------------------------------
# A render prices an unchanged live file from the cache (macsetup-rn21)
# ---------------------------------------------------------------------------

class TestLiveFilesPricedFromTheCcreportCache:
    """Re-parsing the project's whole corpus per render was ~93% of it.

    The cached records already hold every time-independent fact the windows
    need, so a file whose (mtime_ns, size) still matches is summed from them.
    Every test here pins the property that makes that substitution legal: the
    two paths have to produce the same number, and a cache that cannot be
    trusted has to fall back rather than answer.
    """

    CWD = "/tmp/proj"

    @pytest.fixture()
    def projects_dir(self, monkeypatch, tmp_path):
        import cache_db
        import pricing

        d = tmp_path / "projects"
        (d / "-tmp-proj").mkdir(parents=True)
        monkeypatch.setattr(pricing, "_get_projects_dirs", lambda: [d])
        monkeypatch.setattr(cache_db, "get_project_overrides", lambda: [])
        cache_db.init_ccreport_meta(1, "test-hash")
        return d

    @staticmethod
    def _record(mid: str, **kw) -> dict:
        """One cached record, in the shape cache_db stores and pricing reads."""
        return {
            "mid": mid, "model": "claude-opus-5",
            "ts": datetime.now(tz=timezone.utc).timestamp(), "sid": "s1",
            "project": "proj", "cwd": "/tmp/proj", "repo": None,
            "dk": f"{mid}:req-1", "cost": 0.5, "t": [1000, 500, 0, 0], **kw,
        }

    @staticmethod
    def _line(rec: dict) -> str:
        """The JSONL line a raw parse must read *rec* back out of."""
        import json

        line: dict = {
            "type": "assistant",
            "timestamp": datetime.fromtimestamp(
                rec["ts"], tz=timezone.utc).isoformat(),
            "sessionId": rec["sid"], "cwd": rec["cwd"],
            "message": {
                "id": rec["mid"], "model": rec["model"],
                "usage": {
                    "input_tokens": rec["t"][0], "output_tokens": rec["t"][1],
                    "cache_creation_input_tokens": rec["t"][2],
                    "cache_read_input_tokens": rec["t"][3],
                },
            },
        }
        if rec["dk"]:
            line["requestId"] = rec["dk"].split(":", 1)[1]
        return json.dumps(line)

    def _file(self, projects_dir, name: str, records: list[dict], *,
              cached: bool = True, fresh: bool = True):
        """Write *records* as a JSONL file, optionally caching them for it."""
        import cache_db

        path = projects_dir / "-tmp-proj" / name
        path.write_text("".join(self._line(r) + "\n" for r in records))
        if cached:
            st = path.stat()
            fp = (st.st_mtime_ns, st.st_size) if fresh else (1, 1)
            cache_db.save_ccreport_file(str(path), *fp, records)
        return path

    @staticmethod
    def _expected(*records: dict) -> float:
        """What both paths owe: every record priced from its own tokens."""
        from pricing import _rec_cost_from_tokens

        return round(sum(_rec_cost_from_tokens(r) for r in records), 4)

    @staticmethod
    def _clear_fingerprints() -> None:
        """Force the raw parse without touching the records or the salt.

        Not invalidate_ccreport: that also drops the salt and NULLs the costs,
        so it could not tell a fingerprint miss from a cache the reader refused.
        """
        import cache_db

        conn = cache_db.get_connection()
        conn.execute("UPDATE ccreport_files SET mtime_ns = 0, size = 0")
        conn.commit()

    def _mixed_project(self, projects_dir) -> list[dict]:
        """Three files: cached and fresh, uncached, cached but stale."""
        fresh = [self._record("msg-a"), self._record("msg-b")]
        uncached = [self._record("msg-c")]
        stale = [self._record("msg-d")]
        self._file(projects_dir, "a.jsonl", fresh)
        self._file(projects_dir, "b.jsonl", uncached, cached=False)
        self._file(projects_dir, "c.jsonl", stale, fresh=False)
        return [*fresh, *uncached, *stale]

    def test_the_cached_path_totals_what_a_full_reparse_totals(self, projects_dir):
        from pricing import compute_project_rolling_costs

        records = self._mixed_project(projects_dir)
        cached = compute_project_rolling_costs(self.CWD)
        self._clear_fingerprints()
        assert cached == compute_project_rolling_costs(self.CWD)
        assert cached["all_time_project_cost"] == self._expected(*records)

    def test_every_window_agrees_not_just_the_total(self, projects_dir):
        """The windows are the reason bucket sums could not be cached."""
        from pricing import ROLLING_COST_NAMES, compute_project_rolling_costs

        self._mixed_project(projects_dir)
        cached = compute_project_rolling_costs(self.CWD)
        self._clear_fingerprints()
        raw = compute_project_rolling_costs(self.CWD)
        assert [cached[f"{n}_project_cost"] for n in ROLLING_COST_NAMES] == \
            [raw[f"{n}_project_cost"] for n in ROLLING_COST_NAMES]
        assert cached["six_hour_project_cost"] == cached["all_time_project_cost"]

    @pytest.mark.parametrize("cached_first", [True, False])
    def test_one_message_in_two_files_counts_once_across_the_two_paths(
        self, projects_dir, cached_first,
    ):
        """seen_keys is shared, so which path reads the twin cannot matter."""
        from pricing import compute_project_rolling_costs

        rec = self._record("msg-a")
        first, second = ("a.jsonl", "b.jsonl") if cached_first else ("b.jsonl", "a.jsonl")
        self._file(projects_dir, first, [rec])
        self._file(projects_dir, second, [rec], cached=False)
        assert compute_project_rolling_costs(
            self.CWD)["all_time_project_cost"] == self._expected(rec)

    def test_a_live_files_stored_cost_loses_to_the_recomputed_one(self, projects_dir):
        """ccreport may have stored the log's costUSD; the raw path never did.

        Serving the stored value would make a file's cost depend on whether
        the render happened to hit the cache, which is the one thing the
        substitution may not change.
        """
        from pricing import compute_project_rolling_costs

        rec = self._record("msg-a", cost=99.0)
        self._file(projects_dir, "a.jsonl", [rec])
        total = compute_project_rolling_costs(self.CWD)["all_time_project_cost"]
        assert total == self._expected(rec)
        assert total < 1.0

    def test_an_orphans_stored_cost_still_wins(self, projects_dir):
        """No JSONL left to re-price from, so the stored cost is the only truth."""
        import cache_db
        from pricing import compute_project_rolling_costs

        rec = self._record("msg-a", cost=99.0)
        cache_db.save_ccreport_file(
            str(projects_dir / "-tmp-proj" / "gone.jsonl"), 1, 1, [rec])
        assert compute_project_rolling_costs(
            self.CWD)["all_time_project_cost"] == 99.0

    def test_a_file_modified_after_caching_is_reparsed(self, projects_dir):
        from pricing import compute_project_rolling_costs

        rec = self._record("msg-a")
        path = self._file(projects_dir, "a.jsonl", [rec])
        # Same path, different content: the cached records now describe a file
        # that no longer exists, and their fingerprint is what says so.
        rewritten = [self._record("msg-b"), self._record("msg-c")]
        path.write_text("".join(self._line(r) + "\n" for r in rewritten))
        assert compute_project_rolling_costs(
            self.CWD)["all_time_project_cost"] == self._expected(*rewritten)

    def test_a_mismatched_salt_falls_back_to_the_raw_parse(self, projects_dir):
        import cache_db
        from pricing import compute_project_rolling_costs

        records = self._mixed_project(projects_dir)
        conn = cache_db.get_connection()
        cache_db._set_meta(conn, "ccreport_schema_salt", "not-the-salt")
        conn.commit()
        assert compute_project_rolling_costs(
            self.CWD)["all_time_project_cost"] == self._expected(*records)

    def test_an_invalidated_cache_falls_back_to_the_raw_parse(self, projects_dir):
        import cache_db
        from pricing import compute_project_rolling_costs

        records = self._mixed_project(projects_dir)
        live = {str(p) for p in (projects_dir / "-tmp-proj").glob("*.jsonl")}
        cache_db.invalidate_ccreport(live)
        assert compute_project_rolling_costs(
            self.CWD)["all_time_project_cost"] == self._expected(*records)

    def test_a_render_writes_nothing_back(self, projects_dir):
        """One WAL writer only — a cache miss costs a parse, not a write."""
        import cache_db
        from pricing import compute_project_rolling_costs

        self._mixed_project(projects_dir)
        conn = cache_db.get_connection()
        before = conn.execute(
            "SELECT path, mtime_ns, size FROM ccreport_files").fetchall()
        compute_project_rolling_costs(self.CWD)
        assert conn.execute(
            "SELECT path, mtime_ns, size FROM ccreport_files").fetchall() == before

    def test_only_the_files_the_cache_cannot_vouch_for_are_read(
        self, projects_dir, monkeypatch,
    ):
        """The point of the change: a fresh fingerprint means no file read."""
        from pathlib import Path

        import pricing

        self._mixed_project(projects_dir)
        parsed: list[str] = []
        real = pricing._iter_jsonl_costs
        monkeypatch.setattr(pricing, "_iter_jsonl_costs", lambda p, seen: (
            parsed.append(Path(p).name) or real(p, seen)))
        pricing.compute_project_rolling_costs(self.CWD)
        assert parsed == ["b.jsonl", "c.jsonl"]
