"""Tests for ccreport.py — record filtering, aggregation, summary rows.

`load_all_records` runs against a temp cache DB and a temp JSONL tree; nothing
here reads the real log or the real cache.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import io
import json
import types
from pathlib import Path

import pytest
from rich.console import Console

import cache_db

_CCREPORT = Path(__file__).resolve().parent.parent / "ccreport.py"


def _load_ccreport():
    """ccreport.py is a script, not an importable module name."""
    spec = importlib.util.spec_from_file_location("ccreport", _CCREPORT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ccr = _load_ccreport()
UTC = dt.timezone.utc


def _rec(**kw):
    defaults = dict(
        message_id="m1", model="claude-opus-5",
        tokens=ccr.TokenCounts(input=10, output=20, cache_create=30, cache_read=40),
        timestamp=dt.datetime(2026, 6, 15, 12, tzinfo=UTC),
        session_id="s1", project="proj", cost_usd=1.0, dedup_key=None,
    )
    return ccr.UsageRecord(**{**defaults, **kw})


def _filters(**kw):
    base = dict(since=None, until=None, project_filter=None,
                seen_keys=set(), override=None)
    return {**base, **kw}


class TestKeep:
    def test_bare_record_is_kept(self):
        assert ccr._keep(_rec(), **_filters()) is True

    def test_since_and_until_bound_the_window(self):
        rec = _rec(timestamp=dt.datetime(2026, 6, 15, tzinfo=UTC))
        assert ccr._keep(rec, **_filters(since=dt.datetime(2026, 6, 16, tzinfo=UTC))) is False
        assert ccr._keep(rec, **_filters(until=dt.datetime(2026, 6, 14, tzinfo=UTC))) is False
        assert ccr._keep(rec, **_filters(since=dt.datetime(2026, 6, 1, tzinfo=UTC),
                                        until=dt.datetime(2026, 6, 30, tzinfo=UTC))) is True

    def test_project_filter_is_a_case_insensitive_substring(self):
        rec = _rec(project="MacSetup")
        assert ccr._keep(rec, **_filters(project_filter="setup")) is True
        assert ccr._keep(rec, **_filters(project_filter="other")) is False

    def test_dedup_keeps_the_first_occurrence_only(self):
        seen: set[str] = set()
        f = _filters(seen_keys=seen)
        assert ccr._keep(_rec(dedup_key="dk1"), **f) is True
        assert ccr._keep(_rec(dedup_key="dk1"), **f) is False
        assert seen == {"dk1"}

    def test_a_record_with_no_dedup_key_falls_back_to_its_content(self):
        """dk is NULL when the log carried no message id or requestId."""
        f = _filters()
        assert ccr._keep(_rec(dedup_key=None), **f) is True
        assert ccr._keep(_rec(dedup_key=None), **f) is False

    def test_one_differing_token_count_makes_it_a_different_record(self):
        f = _filters()
        assert ccr._keep(_rec(dedup_key=None), **f) is True
        chunk = _rec(dedup_key=None,
                     tokens=ccr.TokenCounts(input=10, output=21,
                                            cache_create=30, cache_read=40))
        assert ccr._keep(chunk, **f) is True

    def test_a_zero_token_record_still_dedupes_on_its_message_id(self):
        """<synthetic> rows carry no tokens but do carry an id."""
        f = _filters()
        empty = dict(dedup_key=None, model="<synthetic>",
                     tokens=ccr.TokenCounts())
        assert ccr._keep(_rec(**empty), **f) is True
        assert ccr._keep(_rec(**empty), **f) is False
        assert ccr._keep(_rec(message_id="m2", **empty), **f) is True

    def test_no_id_and_no_tokens_is_never_a_duplicate(self):
        """Session and timestamp alone are not enough to drop a record on."""
        f = _filters()
        blank = dict(dedup_key=None, message_id="", tokens=ccr.TokenCounts())
        assert ccr._keep(_rec(**blank), **f) is True
        assert ccr._keep(_rec(**blank), **f) is True

    def test_override_renames_before_the_project_filter_runs(self):
        rec = _rec(project="old-name")
        kept = ccr._keep(rec, **_filters(project_filter="new",
                                        override=lambda _repo, _cwd, _n: "new-name"))
        assert kept is True
        assert rec.project == "new-name"


@pytest.fixture
def loader(tmp_path, monkeypatch):
    """load_all_records wired to a temp DB and a temp project tree."""
    monkeypatch.setenv("CLAUDE_CACHE_SNAPSHOT_DISABLE", "1")
    monkeypatch.setattr(cache_db, "DB_PATH", tmp_path / "cache.db")
    monkeypatch.setattr(cache_db, "_conn", None)
    projects = tmp_path / "projects" / "-tmp-live"
    projects.mkdir(parents=True)
    monkeypatch.setattr(ccr, "discover_jsonl_files", lambda: sorted(projects.glob("*.jsonl")))
    monkeypatch.setattr(ccr, "_ensure_cache_valid", lambda _live_paths: None)
    # Stubbing _ensure_cache_valid out skips the meta stamp along with the
    # invalidation, and the readers return nothing without a matching schema
    # salt. Stamped here rather than inside the stub so it costs no COMMIT the
    # save-batching tests would count.
    cache_db.init_ccreport_meta(ccr.CACHE_VERSION, "test-hash")
    monkeypatch.setattr(cache_db, "get_project_overrides", lambda: [])
    yield projects
    cache_db.get_connection().close()
    cache_db._conn = None


def _write_jsonl(path: Path, *, when: str, project_cwd: str, ids: list[str]) -> None:
    lines = []
    for i, mid in enumerate(ids):
        lines.append(json.dumps({
            "type": "assistant", "timestamp": when, "sessionId": "sess-1",
            "cwd": project_cwd, "requestId": f"req-{i}",
            "message": {"id": mid, "model": "claude-opus-5",
                        "usage": {"input_tokens": 10, "output_tokens": 20,
                                  "cache_creation_input_tokens": 0,
                                  "cache_read_input_tokens": 0}},
            "costUSD": 1.0,
        }))
    path.write_text("\n".join(lines) + "\n")


def test_cache_invalidation_sees_every_discovered_file(loader, monkeypatch):
    """A path missing from this set gets treated as purged and left stale."""
    _write_jsonl(loader / "a.jsonl", when="2026-06-15T12:00:00Z",
                 project_cwd="/tmp/live", ids=["msg-1"])
    seen: list[set[str]] = []
    monkeypatch.setattr(ccr, "_ensure_cache_valid", seen.append)
    ccr.load_all_records()
    assert seen == [{str(loader / "a.jsonl")}]


class TestLoadAllRecordsFiltersOrphans:
    """The point of one _keep: purged-file history obeys the same filters."""

    def test_orphaned_records_survive_the_source_file_and_obey_since(self, loader):
        live = loader / "a.jsonl"
        _write_jsonl(live, when="2026-06-15T12:00:00Z", project_cwd="/tmp/live",
                     ids=["msg-old", "msg-new"])
        assert len(ccr.load_all_records()) == 2

        # Claude Code purges the JSONL; the cache still holds its records.
        live.unlink()
        orphaned = ccr.load_all_records()
        assert len(orphaned) == 2, "cached history should outlive its file"

        # A window that excludes them must exclude them on the orphan path too.
        assert ccr.load_all_records(since=dt.datetime(2026, 7, 1, tzinfo=UTC)) == []
        assert ccr.load_all_records(until=dt.datetime(2026, 6, 1, tzinfo=UTC)) == []
        assert ccr.load_all_records(project_filter="nothing-matches") == []
        assert len(ccr.load_all_records(project_filter="live")) == 2

    def test_a_live_record_is_not_counted_twice_via_the_cache(self, loader):
        _write_jsonl(loader / "a.jsonl", when="2026-06-15T12:00:00Z",
                     project_cwd="/tmp/live", ids=["msg-1"])
        ccr.load_all_records()
        assert len(ccr.load_all_records()) == 1

    def test_live_and_purged_files_both_load_in_one_run(self, loader):
        """Orphans come out of the bulk load, so a mixed corpus must still add up."""
        for name, mid in (("a.jsonl", "msg-a"), ("b.jsonl", "msg-b")):
            _write_jsonl(loader / name, when="2026-06-15T12:00:00Z",
                         project_cwd="/tmp/live", ids=[mid])
        assert len(ccr.load_all_records()) == 2

        (loader / "b.jsonl").unlink()
        ids = {r.message_id for r in ccr.load_all_records()}
        assert ids == {"msg-a", "msg-b"}


class TestSaveBatching:
    """A full re-parse commits per batch, not per file (macsetup-92y0)."""

    def _commits(self, conn):
        seen: list[str] = []
        conn.set_trace_callback(seen.append)
        return lambda: sum(1 for s in seen if s.strip().upper().startswith("COMMIT"))

    def _corpus(self, loader, n: int) -> None:
        for i in range(n):
            _write_jsonl(loader / f"f{i}.jsonl", when="2026-06-15T12:00:00Z",
                         project_cwd="/tmp/live", ids=[f"msg-{i}"])

    def test_a_whole_corpus_under_one_batch_commits_once(self, loader):
        self._corpus(loader, 12)
        commits = self._commits(cache_db.get_connection())
        assert len(ccr.load_all_records()) == 12
        assert commits() == 1

    def test_the_batch_size_bounds_each_transaction(self, loader, monkeypatch):
        monkeypatch.setattr(ccr, "_SAVE_BATCH", 5)
        self._corpus(loader, 12)
        commits = self._commits(cache_db.get_connection())
        ccr.load_all_records()
        assert commits() == 3  # 5 + 5 + the trailing 2

    def test_batching_caches_every_file_and_then_writes_nothing(self, loader, monkeypatch):
        monkeypatch.setattr(ccr, "_SAVE_BATCH", 5)
        self._corpus(loader, 12)
        ccr.load_all_records()
        file_meta, by_file = cache_db.bulk_load_ccreport_cache()
        assert len(file_meta) == 12
        assert sum(len(v) for v in by_file.values()) == 12

        commits = self._commits(cache_db.get_connection())
        assert len(ccr.load_all_records()) == 12
        assert commits() == 0, "an all-hit run must not write"


class _FlakyFile:
    """A file that hands back *lines*, then dies mid-read like a bad disk."""

    def __init__(self, lines: list[bytes]):
        self._lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def __iter__(self):
        yield from self._lines
        raise OSError("read failed mid-file")


class TestPartialParseNeverOverwritesTheCache:
    """A truncated parse saved over a complete cache entry is silent loss."""

    def test_parse_jsonl_file_propagates_a_mid_file_read_error(self, loader, monkeypatch):
        path = loader / "a.jsonl"
        _write_jsonl(path, when="2026-06-15T12:00:00Z", project_cwd="/tmp/live",
                     ids=["msg-1", "msg-2"])
        first_line = path.read_bytes().splitlines()[0]
        monkeypatch.setattr(ccr, "open", lambda *_a, **_kw: _FlakyFile([first_line]),
                            raising=False)
        with pytest.raises(OSError):
            ccr.parse_jsonl_file(path)

    def test_a_failed_reparse_leaves_the_cached_records_whole(self, loader, monkeypatch):
        path = loader / "a.jsonl"
        _write_jsonl(path, when="2026-06-15T12:00:00Z", project_cwd="/tmp/live",
                     ids=["msg-1", "msg-2"])
        assert len(ccr.load_all_records()) == 2

        # Grow the file so its fingerprint misses and a re-parse is forced,
        # then make that re-parse fail after the first line.
        _write_jsonl(path, when="2026-06-15T12:00:00Z", project_cwd="/tmp/live",
                     ids=["msg-1", "msg-2", "msg-3"])
        real_open, failing = open, [True]

        def flaky_open(*args, **kwargs):
            if failing[0]:
                failing[0] = False
                return _FlakyFile(path.read_bytes().splitlines()[:1])
            return real_open(*args, **kwargs)

        monkeypatch.setattr(ccr, "open", flaky_open, raising=False)
        # This run under-reports the unreadable file...
        assert ccr.load_all_records() == []
        # ...but its cache entry is untouched, so nothing is lost for good.
        _meta, by_file = cache_db.bulk_load_ccreport_cache()
        assert len(by_file[str(path)]) == 2
        assert len(ccr.load_all_records()) == 3


class TestExplicitJsonNulls:
    """A key present with JSON null defeats a get() default and hits NOT NULL."""

    @staticmethod
    def _write_null_jsonl(path: Path) -> None:
        path.write_text(json.dumps({
            "type": "assistant", "timestamp": "2026-06-15T12:00:00Z",
            "sessionId": None, "cwd": "/tmp/live", "requestId": "req-0",
            "message": {"id": "msg-null", "model": None,
                        "usage": {"input_tokens": None, "output_tokens": None,
                                  "cache_creation_input_tokens": None,
                                  "cache_read_input_tokens": None}},
        }) + "\n")

    def test_nulls_parse_to_the_intended_defaults(self, loader):
        path = loader / "nulls.jsonl"
        self._write_null_jsonl(path)
        rec, = ccr.parse_jsonl_file(path)
        assert rec.session_id == path.stem
        assert rec.model == "unknown"
        assert rec.tokens.total == 0
        assert (rec.tokens.input, rec.tokens.output) == (0, 0)
        assert (rec.tokens.cache_create, rec.tokens.cache_read) == (0, 0)

    def test_a_record_of_nulls_round_trips_through_the_cache(self, loader):
        """One IntegrityError aborts the whole file's insert, every run."""
        self._write_null_jsonl(loader / "nulls.jsonl")
        assert len(ccr.load_all_records()) == 1
        _meta, by_file = cache_db.bulk_load_ccreport_cache()
        cached, = by_file[str(loader / "nulls.jsonl")]
        assert cached["sid"] == "nulls"
        assert cached["model"] == "unknown"
        assert cached["t"] == [0, 0, 0, 0]

    def test_a_null_record_does_not_take_its_file_down_with_it(self, loader):
        """The good records in the same file must still land."""
        path = loader / "mixed.jsonl"
        good = json.dumps({
            "type": "assistant", "timestamp": "2026-06-15T12:00:00Z",
            "sessionId": "sess-1", "cwd": "/tmp/live", "requestId": "req-1",
            "message": {"id": "msg-good", "model": "claude-opus-5",
                        "usage": {"input_tokens": 10, "output_tokens": 20,
                                  "cache_creation_input_tokens": 0,
                                  "cache_read_input_tokens": 0}},
        })
        bad = json.dumps({
            "type": "assistant", "timestamp": "2026-06-15T12:01:00Z",
            "sessionId": None, "cwd": "/tmp/live", "requestId": "req-2",
            "message": {"id": "msg-bad", "model": None, "usage": {"input_tokens": None}},
        })
        path.write_text(good + "\n" + bad + "\n")
        assert len(ccr.load_all_records()) == 2


class TestOverrideReachesPurgedHistory:
    """Orphan records carry no repo and no cwd; only a name can reach them."""

    @staticmethod
    def _fn(monkeypatch, *rules):
        # The builder reads the table through cache_db at call time, so that is
        # where the stub goes — pricing calls the same builder.
        monkeypatch.setattr(cache_db, "get_project_overrides", lambda: [
            {"id": i, "match_kind": k, "match_value": v, "target": t}
            for i, (k, v, t) in enumerate(rules, 1)
        ])
        return ccr._build_override_fn()

    def test_no_rules_costs_the_hot_loop_nothing(self, monkeypatch):
        monkeypatch.setattr(cache_db, "get_project_overrides", lambda: [])
        assert ccr._build_override_fn() is None

    def test_a_remote_rule_follows_its_live_records_onto_the_orphans(self, monkeypatch):
        fn = self._fn(monkeypatch, ("remote", "github.com/org/foo", "bar"))
        assert fn("github.com/org/foo", "/tmp/foo", "foo") == "bar"
        assert fn(None, None, "foo") == "bar", "orphan of the same repo"
        assert fn(None, None, "unrelated") == "unrelated"

    def test_a_cwd_prefix_rule_reaches_orphans_under_its_repo_name(self, monkeypatch):
        under_root = str(Path.home() / "git" / "macsetup")
        fn = self._fn(monkeypatch, ("cwd_prefix", under_root, "tools"))
        assert fn(None, under_root + "/claude", "macsetup") == "tools"
        assert fn(None, None, "macsetup") == "tools"

    def test_a_cwd_prefix_outside_every_repo_root_implies_its_basename(self, monkeypatch):
        fn = self._fn(monkeypatch, ("cwd_prefix", "/tmp/live/", "archive"))
        assert fn(None, None, "live") == "archive"
        # Named after its own subdirectory, so still out of reach by design.
        assert fn(None, None, "sub") == "sub"

    def test_a_record_with_a_cwd_is_not_treated_as_an_orphan(self, monkeypatch):
        """It has a signal; matching it by implied name would regroup live rows."""
        fn = self._fn(monkeypatch, ("remote", "github.com/org/foo", "bar"))
        assert fn(None, "/somewhere/else/foo", "foo") == "foo"

    def test_first_rule_in_insertion_order_still_wins_for_orphans(self, monkeypatch):
        fn = self._fn(monkeypatch,
                      ("remote", "github.com/org/foo", "first"),
                      ("name", "foo", "second"))
        assert fn("github.com/org/foo", "/tmp/foo", "foo") == "first"
        assert fn(None, None, "foo") == "first", "orphan lands where live rows land"

        flipped = self._fn(monkeypatch,
                           ("name", "foo", "second"),
                           ("remote", "github.com/org/foo", "first"))
        assert flipped("github.com/org/foo", "/tmp/foo", "foo") == "second"
        assert flipped(None, None, "foo") == "second"

    def test_implied_name_mirrors_how_parse_derives_a_project(self):
        assert ccr._implied_name("remote", "github.com/org/foo") == "foo"
        assert ccr._implied_name("cwd_prefix", "/tmp/live/") == "live"
        assert ccr._implied_name("name", "foo") is None


class TestMergeWarnsAboutUnreachableHistory:
    def _orphan_rows(self, n: int) -> None:
        cache_db.save_ccreport_file("/gone.jsonl", 1, 1, [
            {"mid": f"m{i}", "model": "claude-opus-5", "ts": 1.0, "sid": "s",
             "project": "foo", "cwd": None, "repo": None, "t": [1, 1, 1, 1]}
            for i in range(n)
        ])

    def _merge(self, kind: str, source: str, target: str = "bar") -> None:
        ccr.cmd_overrides(types.SimpleNamespace(
            command="merge", kind=kind, source=source, target=target))

    def test_a_remote_rule_reports_what_it_cannot_reach(self, capsys):
        self._orphan_rows(3)
        self._merge("remote", "github.com/org/foo")
        err = capsys.readouterr().err
        assert "3 cached record(s)" in err
        assert "'foo'" in err
        assert "ccreport merge <that-name> bar" in err

    def test_a_name_rule_needs_no_warning(self, capsys):
        self._orphan_rows(3)
        self._merge("name", "foo")
        assert capsys.readouterr().err == ""

    def test_nothing_to_warn_about_when_every_record_has_a_cwd(self, capsys):
        cache_db.save_ccreport_file("/live.jsonl", 1, 1, [
            {"mid": "m1", "model": "claude-opus-5", "ts": 1.0, "sid": "s",
             "project": "foo", "cwd": "/tmp/foo", "repo": "github.com/org/foo",
             "t": [1, 1, 1, 1]},
        ])
        self._merge("cwd_prefix", "/tmp/foo")
        assert capsys.readouterr().err == ""


class TestAggregationAndRows:
    def test_bucket_by_groups_and_counts(self):
        recs = [_rec(project="a", cost_usd=1.0), _rec(project="a", cost_usd=2.0),
                _rec(project="b", cost_usd=4.0)]
        buckets = ccr._bucket_by(recs, lambda r: r.project, ccr.NokCtx())
        assert buckets["a"].cost == 3.0
        assert buckets["a"].count == 2
        assert buckets["b"].cost == 4.0
        assert buckets["a"].models == {"claude-opus-5": 3.0}

    def test_synthetic_model_is_counted_but_not_listed(self):
        buckets = ccr._bucket_by([_rec(model="<synthetic>")], lambda _r: "k", ccr.NokCtx())
        assert buckets["k"].count == 1
        assert buckets["k"].models == {}

    def test_agg_bucket_iadd_folds_every_field(self):
        a = ccr.AggBucket(tokens=ccr.TokenCounts(1, 2, 3, 4), cost=1.0, cost_nok=10.0,
                          models={"x": 1.0}, count=1)
        b = ccr.AggBucket(tokens=ccr.TokenCounts(1, 1, 1, 1), cost=2.0, cost_nok=20.0,
                          nok_estimated=True, models={"x": 0.5, "y": 1.5}, count=2)
        a += b
        assert (a.cost, a.cost_nok, a.count) == (3.0, 30.0, 3)
        assert a.tokens.total == 14
        assert a.models == {"x": 1.5, "y": 1.5}
        assert a.nok_estimated is True

    def test_computed_cost_is_memoized_without_touching_cost_usd(self):
        # opus-5 has no pricing at the fixture's June timestamp; sonnet-5 does.
        rec = _rec(cost_usd=None, model="claude-sonnet-5")
        first = ccr.record_cost(rec)
        assert first > 0
        assert ccr.record_cost(rec) == first
        # cost_usd means "the log gave us this"; a computed cost must not land
        # there, because that field is what gets written to the SQLite cache.
        assert rec.cost_usd is None
        assert "_cost" not in ccr._serialize_records([rec])[0]

    def test_logged_cost_usd_still_wins_over_computation(self):
        assert ccr.record_cost(_rec(cost_usd=0.25)) == 0.25

    def test_models_cell_lists_cost_priciest_first(self):
        cell = ccr._models_cell({"claude-haiku-4-5": 0.05, "claude-opus-5": 174.0,
                                 "claude-sonnet-5": 1.5})
        assert str(cell) == "opus-5 ($174), sonnet-5 ($1.50), haiku-4-5 ($0.0500)"

    def test_models_cell_breaks_cost_ties_by_name(self):
        cell = ccr._models_cell({"claude-sonnet-5": 2.0, "claude-haiku-4-5": 2.0})
        assert str(cell) == "haiku-4-5 ($2.00), sonnet-5 ($2.00)"

    def test_nok_ctx_enabled_follows_the_rates(self):
        assert ccr.NokCtx().enabled is False
        assert ccr.NokCtx({"2026-06-15": 10.0}).enabled is True
        assert ccr.NokCtx(mva=True).label == "NOK+MVA"
        assert ccr.NokCtx(mva=False).label == "NOK"

    def test_mva_multiplies_the_converted_cost(self):
        rates = {"2026-06-15": 10.0}
        rec = _rec()
        with_mva, _ = ccr.record_cost_nok(rec, 2.0, ccr.NokCtx(rates, "2026-06-15", True))
        without, _ = ccr.record_cost_nok(rec, 2.0, ccr.NokCtx(rates, "2026-06-15", False))
        assert without == pytest.approx(20.0)
        assert with_mva == pytest.approx(25.0)

    @pytest.mark.parametrize("width", [200, 90])
    @pytest.mark.parametrize("rates", [{}, {"2026-06-15": 10.0}])
    def test_summary_row_cell_count_matches_the_columns(self, width, rates):
        """The padding is derived, so every summary row fills the table exactly."""
        buf = io.StringIO()
        ccr.console = Console(file=buf, width=width, no_color=True)
        narrow = width < ccr.NARROW_WIDTH
        nok = ccr.NokCtx(rates, "2026-06-15", True)
        table = ccr._make_report_table("t", "Date", narrow=narrow, nok=nok)
        ccr._summary_row(table, "AVG", 1.0, narrow=narrow, nok=nok, note="note")
        assert len(table.rows) == 1
        for column in table.columns:
            assert len(column._cells) == 1, f"{column.header} has no cell in the row"
