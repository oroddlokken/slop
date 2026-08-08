"""Tests for statusline-command.py helpers that encode a rule, not a layout."""

from __future__ import annotations

import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "statusline-command.py"


def _load():
    """statusline-command.py is a script, not an importable module name."""
    spec = importlib.util.spec_from_file_location("statusline_command", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sl = _load()


@pytest.fixture(autouse=True)
def _clean_statusline_env(monkeypatch):
    """Every render helper reads the real environment, and this user's profile
    exports several of these — CLAUDE_CODE_PACE_DAYS=5 alone moves every pace
    figure off the default the tests assert (macsetup-133f). Tests state what
    they need; nothing is inherited from the shell running pytest.
    """
    for name in [k for k in os.environ if k.startswith("CLAUDE_STATUSLINE_")]:
        monkeypatch.delenv(name, raising=False)
    for name in ("CLAUDE_CODE_PACE_DAYS", "CF_BADGE", "CLAUDE_CACHE_DB_TIMEOUT"):
        monkeypatch.delenv(name, raising=False)
    # main() puts this one into the real environ itself. Set then deleted so
    # monkeypatch has an entry to undo — otherwise any test that renders end to
    # end leaves it behind for every test file that runs after this one.
    monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DEFER", "")
    monkeypatch.delenv("CLAUDE_CACHE_SNAPSHOT_DEFER")


class TestPctStr:
    """0% is a reading; _ustr's `or` would erase it."""

    @pytest.mark.parametrize(("raw", "expected"), [
        (0, "0"), ("0", "0"), (42, "42"), ("42", "42"), (0.0, "0.0"),
        (None, ""), ("", ""),
    ])
    def test_values(self, raw, expected):
        assert sl._pct_str({"p": raw}, "p") == expected

    def test_missing_key(self):
        assert sl._pct_str({}, "p") == ""

    def test_differs_from_ustr_on_zero(self):
        d = {"p": 0}
        assert sl._pct_str(d, "p") == "0"
        assert sl._ustr(d, "p") == ""


class TestExtraThresholdMet:
    @pytest.mark.parametrize(("pct", "threshold", "expected"), [
        (60, "60", True), (59, "60", False), (100, "60", True),
        (0, "0", True), (0, "60", False), ("75", "60", True),
    ])
    def test_comparison(self, monkeypatch, pct, threshold, expected):
        monkeypatch.setenv("CLAUDE_STATUSLINE_EXTRA_SESSION_THRESHOLD", threshold)
        assert sl._extra_threshold_met(pct) is expected

    @pytest.mark.parametrize("pct", [None, "", "bogus", object()])
    def test_no_reading_is_never_over_the_line(self, monkeypatch, pct):
        """Even with the threshold pinned to 0, unknown must not read as 0%."""
        monkeypatch.setenv("CLAUDE_STATUSLINE_EXTRA_SESSION_THRESHOLD", "0")
        assert sl._extra_threshold_met(pct) is False


class TestExtraVisibility:
    """The render, the fetch decision and the stale marker share one rule."""

    USAGE = {"session_percent": 80, "extra_spent": 3.5, "extra_limit": 200.0}

    def test_material_and_rendered_agree(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_STATUSLINE_EXTRA_SESSION_THRESHOLD", "60")
        assert sl._extra_is_material(dict(self.USAGE)) is True
        assert "E:$3.5" in sl._render_extra_usage(dict(self.USAGE), 0.0)

    @pytest.mark.parametrize("usage_patch", [
        {"session_percent": 10},          # below the threshold
        {"extra_spent": 0.0},             # nothing spent
        {"session_percent": None},        # no reading
    ])
    def test_hidden_cases_are_also_immaterial(self, monkeypatch, usage_patch):
        monkeypatch.setenv("CLAUDE_STATUSLINE_EXTRA_SESSION_THRESHOLD", "60")
        usage = {**self.USAGE, **usage_patch}
        assert sl._extra_is_material(usage) is False
        assert sl._render_extra_usage(usage, 0.0) == ""

    def test_extra_off_hides_and_demotes(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_STATUSLINE_EXTRA", "0")
        assert sl._extra_is_material(dict(self.USAGE)) is False
        assert sl._render_extra_usage(dict(self.USAGE), 0.0) == ""


class TestWindowSize:
    @pytest.mark.parametrize(("ctx_size", "expected"), [
        (200_000, "200k"), (1_000_000, "1M"), (1_500_000, "1.5M"), (2_000_000, "2M"),
    ])
    def test_fractional_windows_keep_their_half(self, monkeypatch, ctx_size, expected):
        monkeypatch.setenv("CLAUDE_STATUSLINE_USABLE_CTX", "0")
        out = sl._render_session("Opus 5", "", False, ctx_size // 2, ctx_size, 0, 0, 0, "")
        assert out.endswith(f"/{expected}\033[0m")


class TestCfBadge:
    """The wrapper's own name is the label, so cf and co sessions read apart."""

    @pytest.mark.parametrize(("value", "label"), [
        ("CF", "CF"), ("CO", "CO"),
        # cf exported a bare 1 before the value carried a label; sessions
        # launched under that wrapper keep it until they are restarted.
        ("1", "CF"),
    ])
    def test_value_is_the_label(self, monkeypatch, value, label):
        monkeypatch.setenv("CF_BADGE", value)
        out = sl._render_session("Opus 5", "", False, 0, 200_000, 0, 0, 0, "")
        assert f"\033[1;97;46m {label} \033[0m" in out

    def test_badge_stays_stashable_by_force_red(self, monkeypatch):
        monkeypatch.setenv("CF_BADGE", "CO")
        out = sl._render_session("Opus 5", "", False, 0, 200_000, 0, 0, 0, "")
        assert " CO " in sl._BADGE_RE.search(out).group(0)

    @pytest.mark.parametrize("value", ["", None])
    def test_no_value_renders_no_badge(self, monkeypatch, value):
        if value is not None:
            monkeypatch.setenv("CF_BADGE", value)
        out = sl._render_session("Opus 5", "", False, 0, 200_000, 0, 0, 0, "")
        assert "1;97;46m" not in out


class TestKill:
    def test_none_is_a_no_op(self):
        assert sl._kill(None) is None

    def test_kills_a_live_process(self):
        proc = subprocess.Popen(["sleep", "30"])
        sl._kill(proc)
        assert proc.wait(timeout=5) != 0

    def test_already_dead_does_not_raise(self):
        proc = subprocess.Popen(["true"])
        proc.wait(timeout=5)
        sl._kill(proc)
        sl._kill(proc)


class TestFetchDcat:
    """Counts are read from dogcat's append log, not from the dogcat library.

    Verified against `dcat list --expand` across all 23 .dogcats repos in ~/git.
    """

    @pytest.fixture(autouse=True)
    def _toggle_on(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_STATUSLINE_DOGCAT", "1")

    def _repo(self, tmp_path, *records):
        import json

        dogcats = tmp_path / ".dogcats"
        dogcats.mkdir()
        (dogcats / "issues.jsonl").write_text(
            "".join(json.dumps(r) + "\n" for r in records), encoding="utf-8"
        )
        return str(tmp_path)

    def _issue(self, id_, status, **extra):
        return {"record_type": "issue", "id": id_, "status": status, **extra}

    def test_counts_by_status(self, tmp_path):
        cwd = self._repo(
            tmp_path,
            self._issue("a", "open"),
            self._issue("b", "open"),
            self._issue("c", "in_review"),
        )
        assert sl._fetch_dcat(cwd) == {"by_status": {"open": 2, "in_review": 1}}

    def test_later_record_supersedes(self, tmp_path):
        cwd = self._repo(
            tmp_path, self._issue("a", "open"), self._issue("a", "closed")
        )
        assert sl._fetch_dcat(cwd) == {"by_status": {"closed": 1}}

    def test_tombstoned_issue_is_dropped(self, tmp_path):
        cwd = self._repo(
            tmp_path,
            self._issue("a", "open"),
            self._issue("b", "open", deleted_at="2026-08-03T12:00:00"),
        )
        assert sl._fetch_dcat(cwd) == {"by_status": {"open": 1}}

    def test_non_issue_records_ignored(self, tmp_path):
        cwd = self._repo(
            tmp_path,
            self._issue("a", "open"),
            {"record_type": "event", "id": "zzz", "status": "open"},
            {"record_type": "dependency", "id": "yyy"},
        )
        assert sl._fetch_dcat(cwd) == {"by_status": {"open": 1}}

    def test_toggle_off_skips_the_read(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CLAUDE_STATUSLINE_DOGCAT", "0")
        assert sl._fetch_dcat(self._repo(tmp_path, self._issue("a", "open"))) == {}

    @pytest.mark.parametrize("cwd_of", [
        pytest.param(lambda p: str(p), id="no-dogcats-dir"),
        pytest.param(lambda p: "", id="empty-cwd"),
    ])
    def test_missing_storage_is_not_an_error(self, tmp_path, cwd_of):
        assert sl._fetch_dcat(cwd_of(tmp_path)) == {}

    def test_corrupt_log_degrades_to_empty(self, tmp_path):
        """A format change must hide the badge, never break the statusline."""
        dogcats = tmp_path / ".dogcats"
        dogcats.mkdir()
        (dogcats / "issues.jsonl").write_text("{not json\n", encoding="utf-8")
        assert sl._fetch_dcat(str(tmp_path)) == {}


class TestScopedCountdown:
    """The scoped quota resets with the weekly one, so only W carries the clock.

    Both segments run the same pace helper, so a shared reset used to print the
    countdown twice on one line (macsetup-4raz).
    """

    @pytest.fixture()
    def render(self, monkeypatch):
        import datetime as dt
        import re
        import time

        monkeypatch.setenv("CLAUDE_STATUSLINE_SCOPED_THRESHOLD", "0")
        now = time.time()

        def _render(scoped_offset_s, week_offset_s=353000):
            def iso(s):
                return dt.datetime.fromtimestamp(now + s, dt.timezone.utc).isoformat()

            usage = {
                "week_percent": "62", "week_reset": iso(week_offset_s),
                "scoped_percent": "9", "scoped_model": "Fable",
                "scoped_reset": iso(scoped_offset_s),
                "_current_model": "Fable 5", "_native_rl": True,
            }
            inners, _, sc_shown = sl._render_rate_limits(usage, now)
            assert sc_shown
            return re.sub(r"\x1b\[[0-9;]*m", "", inners[-1])

        return _render

    def test_shared_reset_drops_the_parenthetical(self, render):
        assert render(353000) == "Fa:9% 2d21h/7d -33%"

    def test_sub_minute_drift_still_reads_as_shared(self, render):
        """W comes from stdin and the scoped reset from a fetch; they can differ."""
        assert render(353047) == "Fa:9% 2d21h/7d -33%"

    def test_own_reset_keeps_its_countdown(self, render):
        assert render(600000) == "Fa:9% 0d1h/7d(6d22h) +8%"

    def test_pace_off_leaves_the_scoped_segment_bare(self, render, monkeypatch):
        monkeypatch.setenv("CLAUDE_STATUSLINE_WEEKLY_PACE", "0")
        assert render(353000) == "Fa:9%"
        assert render(600000) == "Fa:9% 6d22h"


class TestMergeCostData:
    """The cold-start recompute must get the window bounds from stdin.

    Without them compute_costs has no session window and omits its total, so
    the S segment renders bare on the first call of a session (macsetup-4uja).
    """

    @pytest.fixture()
    def calls(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_STATUSLINE_HISTORIC_COST", "1")
        seen: list[dict] = []

        def fake_compute(**kwargs):
            seen.append(kwargs)
            return {"session_window_cost": 3.5}

        monkeypatch.setattr(sl, "compute_costs", fake_compute)
        monkeypatch.setattr(sl, "compute_project_rolling_costs", lambda cwd: {})
        return seen

    def test_native_resets_passed_through(self, calls):
        usage: dict = {}
        native = {"session_reset": "2026-08-03T18:00:00", "week_reset": "2026-08-07T09:00:00"}
        sl._merge_cost_data(usage, "sid", "/tmp/proj", native)
        assert calls[0]["session_reset_iso"] == native["session_reset"]
        assert calls[0]["week_reset_iso"] == native["week_reset"]
        assert usage["session_window_cost"] == 3.5

    def test_no_native_rl_still_computes(self, calls):
        sl._merge_cost_data({}, "sid", "/tmp/proj", None)
        assert calls[0]["session_reset_iso"] is None

    def test_skipped_when_usage_present(self, calls):
        sl._merge_cost_data({"session_percent": 10}, "sid", "", None)
        assert calls == []

    def test_summary_values_win_over_the_usage_row(self, calls):
        usage = {"session_percent": 10, "week_cost": 1.0}
        sl._merge_cost_data(usage, "sid", "", None, {"week_cost": 9.0})
        assert usage["week_cost"] == 9.0


class TestRefreshEnv:
    """The detached refresh inherits neither the render's timeout nor its deferral.

    It is the writer every render waits on, and — since it is off the render
    path entirely — the process the day's DB snapshot is handed to.
    """

    def test_our_own_short_timeout_is_dropped(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_CACHE_DB_TIMEOUT", sl.RENDER_DB_TIMEOUT_S)
        assert "CLAUDE_CACHE_DB_TIMEOUT" not in sl._refresh_env()

    def test_a_deliberate_setting_from_the_shell_is_kept(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_CACHE_DB_TIMEOUT", "45")
        assert sl._refresh_env()["CLAUDE_CACHE_DB_TIMEOUT"] == "45"

    def test_the_snapshot_deferral_is_dropped(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DEFER", "1")
        assert "CLAUDE_CACHE_SNAPSHOT_DEFER" not in sl._refresh_env()

    def test_disabling_snapshots_outright_is_passed_through(self, monkeypatch):
        # Deferring says "not in this process"; disabling says "not at all".
        monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DISABLE", "1")
        assert sl._refresh_env()["CLAUDE_CACHE_SNAPSHOT_DISABLE"] == "1"

    def test_the_rest_of_the_environment_is_passed_through(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_STATUSLINE_EXTRA", "0")
        assert sl._refresh_env()["CLAUDE_STATUSLINE_EXTRA"] == "0"


class TestRenderDefersTheDailySnapshot:
    """The deferral is only worth anything if it beats the first DB touch.

    get_connection reads it once, when it opens the singleton connection, so
    setting it later in the render would be setting it after the copy.
    """

    def test_it_is_set_before_the_first_connection(self, monkeypatch, capsys):
        import json

        import cache_db

        seen: list[str | None] = []
        real = cache_db.get_connection

        def spy():
            seen.append(os.environ.get("CLAUDE_CACHE_SNAPSHOT_DEFER"))
            return real()

        monkeypatch.setattr(cache_db, "get_connection", spy)
        monkeypatch.setattr(sl.sys, "argv", ["statusline-command.py", "-t"])
        monkeypatch.setenv("CLAUDE_STATUSLINE_USAGE_JSON", json.dumps(
            {"session_percent": 23, "week_percent": 41},
        ))
        for off in ("GIT", "DSP", "HISTORIC_COST", "SANDBOX", "SESSIONS"):
            monkeypatch.setenv(f"CLAUDE_STATUSLINE_{off}", "0")

        sl.main()
        capsys.readouterr()

        assert seen, "the render never opened the DB; the spy proves nothing"
        assert all(v == "1" for v in seen)


class TestFetchUsageReadsTheRowOnce:
    """Three reads of the singleton row per render is three too many (macsetup-2xfb)."""

    @pytest.fixture()
    def traced(self, monkeypatch):
        import cache_db

        monkeypatch.setattr(sl, "_spawn_usage_refresh", lambda *a, **k: None)
        conn = cache_db.get_connection()

        def _run(row, **kwargs):
            cache_db.write_usage_cache(row)
            seen: list[str] = []
            conn.set_trace_callback(seen.append)
            try:
                sl._fetch_usage("sid", "/tmp/proj", kwargs.get("native_rl", {}), None)
            finally:
                conn.set_trace_callback(None)
            return sum("FROM usage WHERE id = 1" in s for s in seen)

        return _run

    def _iso(self, offset_s):
        import datetime as dt

        return dt.datetime.fromtimestamp(
            __import__("time").time() + offset_s, dt.timezone.utc,
        ).astimezone().isoformat()

    def test_fresh_row(self, traced):
        assert traced({"session_percent": 5, "last_updated": self._iso(0)}) == 1

    def test_expired_row_that_triggers_a_fetch(self, traced):
        assert traced({"session_percent": 5, "last_updated": self._iso(-4000)}) == 1

    def test_expired_row_while_a_fetch_is_blocked(self, traced):
        import cache_db

        cache_db.record_fetch_failure()
        assert traced({"session_percent": 5, "last_updated": self._iso(-4000)}) == 1

    def test_a_blocked_fetch_still_flags_the_row_as_stale(self, monkeypatch):
        import cache_db

        monkeypatch.setattr(sl, "_spawn_usage_refresh", lambda *a, **k: None)
        cache_db.write_usage_cache(
            {"session_percent": 5, "last_updated": self._iso(-4000)},
        )
        cache_db.record_fetch_failure()
        assert sl._fetch_usage("sid", "/tmp/proj", {}, None)["_stale"] is True


class TestRenderSurvivesContention:
    """A busy database costs the render a statistic, never the whole line."""

    @pytest.fixture()
    def blocked_db(self, monkeypatch):
        import sqlite3

        import cache_db

        monkeypatch.setenv("CLAUDE_CACHE_DB_TIMEOUT", "0.1")
        cache_db.get_connection()
        cache_db.close_connection()  # reopen under the short timeout
        other = sqlite3.connect(str(cache_db.DB_PATH), timeout=5)
        other.execute("BEGIN IMMEDIATE")
        yield
        other.rollback()
        other.close()

    def test_cache_stats_write_raises_when_the_db_is_held(self, blocked_db):
        """The guard in main() is only worth having if this is what it catches."""
        import sqlite3

        with pytest.raises(sqlite3.OperationalError):
            sl._accumulate_cache_stats("sid", 1, 1, 1, 100)

    def test_the_line_is_still_printed(self, monkeypatch, capsys, blocked_db):
        """-t renders the mock payload end to end, cache-stats write and all."""
        import json
        import re

        monkeypatch.setattr(sl.sys, "argv", ["statusline-command.py", "-t"])
        # Keeps the render off the network: no refresh subprocess to spawn.
        monkeypatch.setenv("CLAUDE_STATUSLINE_USAGE_JSON", json.dumps(
            {"session_percent": 23, "week_percent": 41},
        ))
        for off in ("GIT", "DSP", "HISTORIC_COST", "SANDBOX", "SESSIONS"):
            monkeypatch.setenv(f"CLAUDE_STATUSLINE_{off}", "0")

        sl.main()

        out = re.sub(r"\x1b\[[0-9;]*m", "", capsys.readouterr().out)
        assert re.search(r"S:\d+%", out)
        assert re.search(r"W:\d+%", out)
        assert "427k/967k" in out  # the session segment survived too


class TestCaptureAccount:
    """The render is the only capture point, so it must never cost the line."""

    ACC = {
        "accountUuid": "uuid-work",
        "emailAddress": "me@work.example",
        "organizationUuid": "org-work",
        "organizationName": "Work AS",
    }

    @pytest.fixture()
    def config(self, tmp_path, monkeypatch):
        """A stand-in ~/.claude.json the test writes; returns its path."""
        path = tmp_path / "claude.json"
        monkeypatch.setattr(sl, "CLAUDE_CONFIG_JSON", path)
        return path

    def _log(self):
        import cache_db

        return cache_db.load_account_events()

    def test_the_account_is_recorded_from_the_config(self, config):
        import json

        config.write_text(json.dumps({"numStartups": 3, "oauthAccount": self.ACC}))
        sl._capture_account()
        (event,) = self._log()
        assert event["account_uuid"] == "uuid-work"
        assert event["email"] == "me@work.example"
        assert event["organization_name"] == "Work AS"

    def test_repeat_renders_do_not_grow_the_log(self, config):
        import json

        config.write_text(json.dumps({"oauthAccount": self.ACC}))
        for _ in range(5):
            sl._capture_account()
        assert len(self._log()) == 1

    def test_a_switch_between_renders_is_captured(self, config):
        import json

        config.write_text(json.dumps({"oauthAccount": self.ACC}))
        sl._capture_account()
        config.write_text(json.dumps({"oauthAccount": {
            "accountUuid": "uuid-home", "emailAddress": "me@home.example",
        }}))
        sl._capture_account()
        assert [e["email"] for e in self._log()] == [
            "me@work.example", "me@home.example",
        ]

    @pytest.mark.parametrize("body", [
        None,                       # file absent entirely
        "",                         # zero bytes
        "{not json",                # half-written
        "{}",                       # no oauthAccount
        '{"oauthAccount": null}',   # present but null
        '{"oauthAccount": "nope"}',  # present but not an object
        '{"oauthAccount": {}}',     # no accountUuid to key on
    ])
    def test_an_unusable_config_records_nothing_and_does_not_raise(self, config, body):
        if body is not None:
            config.write_text(body)
        sl._capture_account()
        assert self._log() == []

    def test_a_held_database_costs_the_log_a_sample_not_the_render(self, config, monkeypatch):
        import json
        import sqlite3

        import cache_db

        config.write_text(json.dumps({"oauthAccount": self.ACC}))
        monkeypatch.setenv("CLAUDE_CACHE_DB_TIMEOUT", "0.1")
        cache_db.get_connection()
        cache_db.close_connection()  # reopen under the short timeout
        other = sqlite3.connect(str(cache_db.DB_PATH), timeout=5)
        other.execute("BEGIN IMMEDIATE")
        try:
            sl._capture_account()  # must not raise
        finally:
            other.rollback()
            other.close()
        assert self._log() == []


class TestRateLimitSamples:
    """What the render offers the snapshot gate, and what it refuses to invent."""

    NOW = 1_000_000.0
    RESETS = NOW + 8100

    def _stdin(self, **windows):
        return {"rate_limits": windows}

    def _iso(self, epoch):
        import datetime as dt

        return dt.datetime.fromtimestamp(epoch).isoformat()  # noqa: DTZ006

    def test_stdin_percentages_are_passed_through_unrounded(self):
        """_native_rate_limits rounds for the display; the fill rate needs the float."""
        data = self._stdin(
            five_hour={"used_percentage": 23.47, "resets_at": self.RESETS},
            seven_day={"used_percentage": 41.02, "resets_at": self.RESETS + 400_000},
        )
        assert sl._rl_samples(data, {}, self.NOW) == [
            ("session", 23.47, self.RESETS, None, "stdin"),
            ("week", 41.02, self.RESETS + 400_000, None, "stdin"),
        ]

    def test_api_resets_are_converted_from_iso(self):
        usage = {
            "sonnet_percent": 12, "sonnet_reset": self._iso(self.RESETS),
            "scoped_percent": 7, "scoped_reset": self._iso(self.RESETS),
            "scoped_model": "claude-opus-4-5",
        }
        assert sl._rl_samples({}, usage, self.NOW) == [
            ("sonnet", 12.0, self.RESETS, None, "api"),
            ("scoped", 7.0, self.RESETS, "claude-opus-4-5", "api"),
        ]

    def test_a_passed_reset_records_nothing(self):
        """The percentage on hand belongs to the window that just ended."""
        data = self._stdin(
            five_hour={"used_percentage": 80.0, "resets_at": self.NOW - 1},
        )
        usage = {"sonnet_percent": 80, "sonnet_reset": self._iso(self.NOW - 1)}
        assert sl._rl_samples(data, usage, self.NOW) == []

    @pytest.mark.parametrize("window", [
        {},                                          # neither field
        {"used_percentage": 23.5},                   # no reset to key the instance on
        {"resets_at": RESETS},                       # no reading
        {"used_percentage": None, "resets_at": RESETS},
        {"used_percentage": 23.5, "resets_at": None},
        {"used_percentage": "n/a", "resets_at": RESETS},
        {"used_percentage": 23.5, "resets_at": "soon"},
    ])
    def test_an_incomplete_stdin_window_is_skipped(self, window):
        assert sl._rl_samples(self._stdin(five_hour=window), {}, self.NOW) == []

    def test_a_missing_rate_limits_block_is_not_an_error(self):
        """Pro/Max only, and absent until the session's first API response."""
        assert sl._rl_samples({}, {}, self.NOW) == []
        assert sl._rl_samples({"rate_limits": None}, {}, self.NOW) == []

    def test_one_unusable_window_does_not_take_the_others_with_it(self):
        data = self._stdin(
            five_hour={"used_percentage": None, "resets_at": self.RESETS},
            seven_day={"used_percentage": 41.0, "resets_at": self.RESETS},
        )
        assert [s.window for s in sl._rl_samples(data, {}, self.NOW)] == ["week"]

    def test_a_scoped_reading_with_no_model_still_samples(self):
        """The plan may scope a limit the cache has no model name for."""
        usage = {"scoped_percent": 7, "scoped_reset": self._iso(self.RESETS)}
        assert sl._rl_samples({}, usage, self.NOW) == [
            ("scoped", 7.0, self.RESETS, None, "api"),
        ]


class TestSnapshotRateLimitsGating:
    """Fabricated readings must never reach a table no later render can correct."""

    NOW = 1_000_000.0

    @pytest.fixture()
    def spy(self, monkeypatch):
        calls: list[tuple] = []
        monkeypatch.setattr(
            sl, "record_rate_limit_snapshots",
            lambda samples, now: calls.append((samples, now)),
        )
        return calls

    def _data(self):
        return {"rate_limits": {
            "five_hour": {"used_percentage": 23.5, "resets_at": self.NOW + 8100},
        }}

    def test_a_real_render_records(self, spy):
        sl._snapshot_rate_limits(self._data(), {}, self.NOW, test_mode=False)
        assert [s.window for s in spy[0][0]] == ["session"]

    def test_test_mode_records_nothing(self, spy):
        sl._snapshot_rate_limits(self._data(), {}, self.NOW, test_mode=True)
        assert spy == []

    def test_pre_provided_usage_json_records_nothing(self, spy, monkeypatch):
        monkeypatch.setenv("CLAUDE_STATUSLINE_USAGE_JSON", '{"session_percent": 23}')
        sl._snapshot_rate_limits(self._data(), {}, self.NOW, test_mode=False)
        assert spy == []

    def test_nothing_to_sample_takes_no_db_call(self, spy):
        sl._snapshot_rate_limits({}, {}, self.NOW, test_mode=False)
        assert spy == []

    @pytest.fixture()
    def blocked_db(self, monkeypatch):
        import sqlite3

        import cache_db

        monkeypatch.setenv("CLAUDE_CACHE_DB_TIMEOUT", "0.1")
        cache_db.get_connection()
        cache_db.close_connection()  # reopen under the short timeout
        other = sqlite3.connect(str(cache_db.DB_PATH), timeout=5)
        other.execute("BEGIN IMMEDIATE")
        yield
        other.rollback()
        other.close()

    def test_the_write_raises_when_the_db_is_held(self, blocked_db):
        """The guard is only worth having if this is what it catches."""
        import sqlite3

        with pytest.raises(sqlite3.OperationalError):
            sl.record_rate_limit_snapshots(
                sl._rl_samples(self._data(), {}, self.NOW), self.NOW,
            )

    def test_a_held_database_costs_the_table_a_sample_not_the_render(self, blocked_db):
        import cache_db

        sl._snapshot_rate_limits(self._data(), {}, self.NOW, test_mode=False)
        rows = cache_db.get_connection().execute(
            "SELECT COUNT(*) FROM rate_limit_snapshots").fetchone()[0]
        assert rows == 0
