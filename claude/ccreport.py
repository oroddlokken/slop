#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["orjson", "rich"]
# ///
"""Analyze Claude Code token usage and costs from local JSONL session logs.

AUDIT: All calculations are documented in claude/CLAUDE.md.
When changing any calculation, caching, or data format here,
update CLAUDE.md to match.
"""

import argparse
import calendar
import hashlib
import json
import os
import re
import subprocess
import sys
import tomllib
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import orjson
from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

# pricing.py and cache_db.py live in the same directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cache_db import (
    add_project_override,
    bulk_load_ccreport_cache,
    check_ccreport_valid,
    delete_project_override,
    get_ccreport_orphaned_records,
    get_project_overrides,
    init_ccreport_meta,
    invalidate_ccreport,
    save_ccreport_file,
)
from exchange import get_rate, load_rates, to_oslo_date
from pricing import calc_cost, extract_assistant_fields

_PROJECT_ROOTS = (
    Path.home() / ".claude" / "projects",
    Path.home() / ".config" / "claude" / "projects",
)

# Repos live directly beneath repo-root container dirs. A session's project
# is the segment just under the deepest matching root, so subdirectories and
# git worktrees collapse into their repo (e.g. ~/git/ren.no/web -> ren.no)
# and a repo opened from two places stays one. ~/git is always a repo root;
# per-machine layouts (~/dev and friends) are added via the config file,
# which can only ever add roots, never remove the baseline.
_CONFIG_PATH = Path(
    os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
) / "macsetup" / "claude" / "ccreport.toml"

_BASELINE_REPO_ROOT = Path.home() / "git"


def _load_repo_roots() -> tuple[str, ...]:
    """Return the ~/git baseline plus repo_roots from the config file.

    Sorted deepest-first, which makes matching longest-prefix regardless of
    config order. No config file (or no repo_roots key) leaves just the
    baseline; a malformed file warns instead of taking the reports down
    with it.
    """
    roots = {str(_BASELINE_REPO_ROOT)}
    try:
        with open(_CONFIG_PATH, "rb") as f:
            extra = tomllib.load(f).get("repo_roots", [])
    except FileNotFoundError:
        extra = []
    except (tomllib.TOMLDecodeError, OSError) as e:
        print(f"warning: ignoring {_CONFIG_PATH}: {e}", file=sys.stderr)
        extra = []
    roots.update(str(Path(r).expanduser()) for r in extra if isinstance(r, str))
    return tuple(sorted(roots, key=len, reverse=True))


_REPO_ROOTS = _load_repo_roots()


def _repo_from_path(cwd: str) -> str | None:
    """Return the repo directory name for a cwd under a repo root.

    None leaves the caller free to fall back to the plain basename for paths
    outside every repo root.
    """
    for root in _REPO_ROOTS:
        prefix = root + "/"
        if cwd.startswith(prefix):
            repo = cwd[len(prefix):].split("/", 1)[0]
            if repo:
                return repo
    return None


# Git remote is the durable project identity: it survives a folder being moved
# or deleted, where a path does not. Resolved lazily at parse time (only while
# the working dir still exists) and cached per cwd within a run.
_remote_cache: dict[str, str | None] = {}


def _normalize_remote(url: str) -> str:
    """Reduce a git remote URL to a stable host/path key.

    Handles scp-style (git@host:org/repo.git), ssh:// (with optional port),
    and https:// forms; strips credentials, port, and the .git suffix.
    """
    url = url.strip()
    url = re.sub(r"\.git$", "", url)
    m = re.match(r"^[\w.+-]+@([^:/]+):(.+)$", url)  # scp-style: git@host:path
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    m = re.match(r"^[a-z][a-z0-9+.-]*://(?:[^@/]+@)?([^:/]+)(?::\d+)?/(.+)$", url)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return url


def _resolve_remote(cwd: str) -> str | None:
    """Return the normalized origin remote for a cwd, or None.

    None when the dir is gone, it isn't a git repo, or there is no origin —
    callers then fall back to the path-based name.
    """
    if cwd in _remote_cache:
        return _remote_cache[cwd]
    result: str | None = None
    if Path(cwd).is_dir():
        try:
            out = subprocess.run(
                ["git", "-C", cwd, "config", "--get", "remote.origin.url"],
                capture_output=True, text=True, timeout=5,
            )
            if out.returncode == 0 and out.stdout.strip():
                result = _normalize_remote(out.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            result = None
    _remote_cache[cwd] = result
    return result

# --- File-level cache ---
CACHE_VERSION = 2


def _script_hash() -> str:
    """SHA256 of this script plus the repo-roots config, used to invalidate cache.

    The config participates because repo_roots shapes the project names frozen
    into cached records at parse time — editing it must trigger a re-parse
    just like a code change does.
    """
    h = hashlib.sha256()
    try:
        h.update(Path(__file__).read_bytes())
    except OSError:
        return ""
    try:
        h.update(_CONFIG_PATH.read_bytes())
    except OSError:
        pass  # no config is a valid state; hash covers just the script
    return h.hexdigest()


def _ensure_cache_valid() -> None:
    """Ensure ccreport cache is valid; invalidate and reinitialize if stale."""
    sh = _script_hash()
    if not check_ccreport_valid(CACHE_VERSION, sh):
        invalidate_ccreport()
        init_ccreport_meta(CACHE_VERSION, sh)


def _serialize_records(records: list) -> list[dict]:
    """Convert UsageRecords to compact cache dicts."""
    return [
        {
            "mid": r.message_id,
            "model": r.model,
            "ts": r.timestamp.timestamp(),
            "sid": r.session_id,
            "project": r.project,
            "cwd": r.cwd,
            "repo": r.repo,
            "dk": r.dedup_key,
            "cost": r.cost_usd,
            "t": [r.tokens.input, r.tokens.output, r.tokens.cache_create, r.tokens.cache_read],
        }
        for r in records
    ]


def _deserialize_records(raw: list[dict]) -> list:
    """Convert compact cache dicts back to UsageRecords."""
    return [
        UsageRecord(
            message_id=r["mid"],
            model=r["model"],
            timestamp=datetime.fromtimestamp(r["ts"], tz=timezone.utc),
            session_id=r["sid"],
            project=r["project"],
            cwd=r.get("cwd"),
            repo=r.get("repo"),
            dedup_key=r.get("dk"),
            cost_usd=r.get("cost"),
            tokens=TokenCounts(
                input=r["t"][0], output=r["t"][1],
                cache_create=r["t"][2], cache_read=r["t"][3],
            ),
        )
        for r in raw
    ]


@dataclass
class TokenCounts:
    input: int = 0
    output: int = 0
    cache_create: int = 0
    cache_read: int = 0

    @property
    def total(self) -> int:
        return self.input + self.output + self.cache_create + self.cache_read

    def __iadd__(self, other: "TokenCounts") -> "TokenCounts":
        self.input += other.input
        self.output += other.output
        self.cache_create += other.cache_create
        self.cache_read += other.cache_read
        return self


@dataclass
class UsageRecord:
    message_id: str
    model: str
    tokens: TokenCounts
    timestamp: datetime
    session_id: str
    project: str
    cost_usd: float | None = None  # pre-calculated cost from Claude Code
    dedup_key: str | None = None  # message_id:request_id for deduplication
    cwd: str | None = None  # original cwd from JSONL; lets future migrations re-derive project
    repo: str | None = None  # normalized git remote captured at parse time (durable identity)


@dataclass
class AggBucket:
    tokens: TokenCounts = field(default_factory=TokenCounts)
    cost: float = 0.0
    cost_nok: float = 0.0
    nok_estimated: bool = False
    models: set[str] = field(default_factory=set)
    count: int = 0

    def __iadd__(self, other: "AggBucket") -> "AggBucket":
        """Fold another bucket in — how every report builds its TOTAL row."""
        self.tokens += other.tokens
        self.cost += other.cost
        self.cost_nok += other.cost_nok
        self.nok_estimated = self.nok_estimated or other.nok_estimated
        self.models |= other.models
        self.count += other.count
        return self


def record_cost(rec: UsageRecord) -> float:
    """Return cost for a record: use pre-calculated costUSD if available, else compute."""
    if rec.cost_usd is not None:
        return rec.cost_usd
    return calc_cost(
        rec.tokens.input, rec.tokens.output,
        rec.tokens.cache_create, rec.tokens.cache_read,
        rec.model, rec.timestamp,
    )


@dataclass(frozen=True)
class NokCtx:
    """Everything the NOK column needs, as one value instead of four parameters.

    ``enabled`` is derived rather than stored: a separate has_nok flag could
    disagree with the rates it is supposed to describe.
    """

    rates: dict[str, float] = field(default_factory=dict)
    max_rate_date: str | None = None
    mva: bool = True

    @property
    def enabled(self) -> bool:
        return bool(self.rates)

    @property
    def label(self) -> str:
        return "NOK+MVA" if self.mva else "NOK"


def record_cost_nok(rec: UsageRecord, cost_usd: float, nok: NokCtx) -> tuple[float | None, bool]:
    """Convert a record's USD cost to NOK using its day's exchange rate.

    With nok.mva (the default), applies 25% Norwegian VAT (MVA) on top.
    Returns (nok_amount, estimated) where estimated is True only at the
    trailing edge of rate data (the true rate is not yet known).
    """
    d = to_oslo_date(rec.timestamp)
    rate, estimated = get_rate(nok.rates, d, _max_date=nok.max_rate_date)
    if rate is None:
        return None, False
    multiplier = 1.25 if nok.mva else 1.0
    return cost_usd * rate * multiplier, estimated


def _accum_nok(bucket: "AggBucket", rec: UsageRecord, cost_usd: float, nok: NokCtx) -> None:
    """Accumulate NOK cost into a bucket, setting estimated flag if needed."""
    amount, estimated = record_cost_nok(rec, cost_usd, nok)
    if amount is not None:
        bucket.cost_nok += amount
        if estimated:
            bucket.nok_estimated = True


def _bucket_by(
    records: list[UsageRecord],
    key_fn: "Callable[[UsageRecord], Any]",
    nok: NokCtx,
) -> dict[Any, AggBucket]:
    """Aggregate *records* into buckets keyed by ``key_fn(rec)``.

    Every report differs only in that key: a date, a month, a project, a
    session, or a (date, model) pair for the breakdown rows.
    """
    buckets: dict[Any, AggBucket] = defaultdict(AggBucket)
    for rec in records:
        b = buckets[key_fn(rec)]
        b.tokens += rec.tokens
        cost = record_cost(rec)
        b.cost += cost
        if nok.enabled:
            _accum_nok(b, rec, cost, nok)
        if rec.model != "<synthetic>":
            b.models.add(rec.model)
        b.count += 1
    return buckets


def load_rates_for_records(records: list[UsageRecord], *, mva: bool = True) -> tuple[NokCtx, bool]:
    """Bulk-load exchange rates for all record dates.

    Returns (nok_context, has_full_coverage). The context is empty — and so
    reports as disabled — when no rates could be loaded.
    """
    from datetime import date as date_type
    if not records:
        return NokCtx(mva=mva), False
    dates: set[date_type] = {to_oslo_date(r.timestamp) for r in records}
    rates = load_rates(dates)
    if not rates:
        return NokCtx(mva=mva), False
    max_rate_date = max(rates)
    # Check coverage: every unique date must resolve via walkback
    missing = 0
    for d in dates:
        rate, _ = get_rate(rates, d, _max_date=max_rate_date)
        if rate is None:
            missing += 1
    return NokCtx(rates, max_rate_date, mva), missing == 0


def project_display_name(project_dir: str) -> str:
    """Convert directory name like '-Users-ove-git-foo' to 'foo'."""
    # Strip leading dash and split
    parts = project_dir.strip("-").split("-")
    # Return last meaningful segment
    if parts:
        return parts[-1]
    return project_dir


def discover_jsonl_files() -> list[Path]:
    """Find all JSONL session logs across known Claude config directories."""
    files = []
    for d in _PROJECT_ROOTS:
        if d.is_dir():
            files.extend(d.rglob("*.jsonl"))
    return sorted(files)


def _resolve_from_filesystem(dir_name: str) -> str | None:
    """Reconstruct a real project name from a dash-encoded directory name.

    Claude Code encodes both '/' and '-' as '-' in projects-dir names, so a
    project at /Users/ove/git/project-name-v2 lands as
    -Users-ove-git-project-name-v2 — ambiguous without context. Try every
    possible split point and pick the one whose reconstructed path exists
    on disk; prefer the longest tail (most dashes preserved in the name).
    """
    parts = dir_name.strip("-").split("-")
    if not parts:
        return None
    for i in range(len(parts)):
        prefix = Path("/" + "/".join(parts[:i])) if i > 0 else Path("/")
        name = "-".join(parts[i:])
        if name and (prefix / name).is_dir():
            return name
    return None


def _derive_project(path: Path) -> str:
    """Derive project display name from a JSONL file's location.

    Used as fallback when records lack a cwd field. Tries to reconstruct
    the real project name against the filesystem; falls back to the
    last-segment heuristic if no real path matches.
    """
    for root in _PROJECT_ROOTS:
        try:
            rel = path.relative_to(root)
            if rel.parts:
                dir_name = rel.parts[0]
                return _resolve_from_filesystem(dir_name) or project_display_name(dir_name)
        except ValueError:
            continue
    return project_display_name(path.parent.name)


def parse_jsonl_file(path: Path) -> list[UsageRecord]:
    """Parse a single JSONL file and extract usage records."""
    records = []
    cwd_from_records: str | None = None

    try:
        with open(path, "rb") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = orjson.loads(line)
                except orjson.JSONDecodeError:
                    continue

                if cwd_from_records is None:
                    c = rec.get("cwd")
                    if isinstance(c, str) and c:
                        cwd_from_records = c

                fields = extract_assistant_fields(rec)
                if fields is None:
                    continue
                msg, usage, message_id, request_id, dedup_key, ts = fields

                tokens = TokenCounts(
                    input=usage.get("input_tokens", 0),
                    output=usage.get("output_tokens", 0),
                    cache_create=usage.get("cache_creation_input_tokens", 0),
                    cache_read=usage.get("cache_read_input_tokens", 0),
                )

                cost_usd = rec.get("costUSD")
                if cost_usd is not None:
                    try:
                        cost_usd = float(cost_usd)
                    except (ValueError, TypeError):
                        cost_usd = None

                records.append(UsageRecord(
                    message_id=message_id,
                    model=msg.get("model", "unknown"),
                    tokens=tokens,
                    timestamp=ts,
                    session_id=rec.get("sessionId", path.stem),
                    project="",
                    cost_usd=cost_usd,
                    dedup_key=dedup_key,
                ))
    except (OSError, UnicodeDecodeError):
        pass

    repo = _resolve_remote(cwd_from_records) if cwd_from_records else None
    if repo:
        # Group by the repo's own name, not the full remote, so a host/org move
        # (e.g. GitLab -> GitHub) keeps history together. A true repo rename is
        # a manual `ccreport merge` away.
        project = repo.rsplit("/", 1)[-1]
    elif cwd_from_records:
        project = _repo_from_path(cwd_from_records) or Path(cwd_from_records).name
    else:
        project = _derive_project(path)
    for r in records:
        r.project = project
        r.cwd = cwd_from_records
        r.repo = repo

    return records


def _build_override_fn():
    """Compile the override table into a (repo, cwd, name) -> name function.

    Rules apply in insertion order; first match wins. Returns None when there
    are no rules so the hot loop pays nothing.
    """
    rules = get_project_overrides()
    if not rules:
        return None

    def resolve(repo: str | None, cwd: str | None, name: str) -> str:
        for r in rules:
            kind, value = r["match_kind"], r["match_value"]
            if kind == "name" and name == value:
                return r["target"]
            if kind == "remote" and repo == value:
                return r["target"]
            if kind == "cwd_prefix" and cwd and (
                cwd == value or cwd.startswith(value.rstrip("/") + "/")
            ):
                return r["target"]
        return name

    return resolve


def _keep(
    rec: UsageRecord,
    *,
    since: datetime | None,
    until: datetime | None,
    project_filter: str | None,
    seen_keys: set[str],
    override: "Callable[[str | None, str | None, str], str] | None",
) -> bool:
    """Whether this record belongs in the report.

    Two side effects, both deliberate: the override renames *rec*'s project
    before the filter sees it, and a first-seen dedup key is added to
    *seen_keys*. Live and purged-file records go through this one copy, so a
    filter added here cannot silently miss the older half of the corpus.
    """
    if override:
        rec.project = override(rec.repo, rec.cwd, rec.project)
    if since and rec.timestamp < since:
        return False
    if until and rec.timestamp > until:
        return False
    if project_filter and project_filter.lower() not in rec.project.lower():
        return False
    if rec.dedup_key is not None:
        if rec.dedup_key in seen_keys:
            return False
        seen_keys.add(rec.dedup_key)
    return True


def load_all_records(
    since: datetime | None = None,
    until: datetime | None = None,
    project_filter: str | None = None,
) -> list[UsageRecord]:
    """Load and deduplicate all usage records.

    Uses a SQLite cache keyed by (mtime_ns, size) to avoid re-parsing
    unchanged files.  Deduplication uses a composite key of message_id +
    request_id (matching ccusage).  First occurrence wins.
    """
    files = discover_jsonl_files()
    _ensure_cache_valid()
    seen_keys: set[str] = set()
    filters = {
        "since": since, "until": until, "project_filter": project_filter,
        "seen_keys": seen_keys, "override": _build_override_fn(),
    }
    all_records: list[UsageRecord] = []
    live_paths: set[str] = set()

    # Bulk-load cache (2 queries instead of N+1)
    file_meta, records_by_file = bulk_load_ccreport_cache()

    for path in files:
        key = str(path)
        live_paths.add(key)
        try:
            st = path.stat()
        except OSError:
            continue
        cached = file_meta.get(key)

        if cached and cached[0] == st.st_mtime_ns and cached[1] == st.st_size:
            records = _deserialize_records(records_by_file.get(key, []))
        else:
            try:
                records = parse_jsonl_file(path)
            except OSError:
                continue
            save_ccreport_file(key, st.st_mtime_ns, st.st_size, _serialize_records(records))

        all_records += [r for r in records if _keep(r, **filters)]

    # Load records from files that were purged from disk but cached in SQLite
    orphaned = _deserialize_records(get_ccreport_orphaned_records(live_paths))
    all_records += [r for r in orphaned if _keep(r, **filters)]

    all_records.sort(key=lambda r: r.timestamp)
    return all_records


# --- Formatting ---

console = Console(soft_wrap=True)
NARROW_WIDTH = 100


def _is_narrow() -> bool:
    return console.width < NARROW_WIDTH


def fmt_tokens(n: int) -> str:
    """Format token count with K/M suffix. Past 100 the decimal is noise."""
    for suffix, size in (("M", 1_000_000), ("K", 1_000)):
        if n >= size:
            scaled = n / size
            # Branch on the rounded value, else 99.96 renders as "100.0K".
            return f"{scaled:.0f}{suffix}" if round(scaled, 1) >= 100 else f"{scaled:.1f}{suffix}"
    return str(n)


def fmt_cost(c: float) -> str:
    """Format cost in USD. Cents stop mattering above $10; sub-10-cent amounts
    keep extra precision so small costs don't render as $0.0."""
    if round(c, 2) >= 10.0:  # rounded, else $9.996 renders as "$10.00"
        return f"${c:.0f}"
    if c >= 1.0:
        return f"${c:.2f}"
    if c >= 0.1:
        return f"${c:.1f}"
    if c == 0.0:
        return "$0.0"
    return f"${c:.4f}"


def fmt_nok(c: float, estimated: bool = False) -> str:
    """Format cost in NOK incl. MVA. Appends * when rate is estimated."""
    star = "*" if estimated else ""
    if c >= 10.0:
        return f"kr {c:.0f}{star}"
    if c >= 1.0:
        return f"kr {c:.1f}{star}"
    return f"kr {c:.2f}{star}"


def fmt_pct(cost: float, total: float) -> str:
    """Format cost as percentage of total."""
    if total <= 0:
        return ""
    pct = cost / total * 100
    if pct >= 10:
        return f"{pct:.0f}%"
    return f"{pct:.1f}%"


def cost_style(c: float) -> str:
    """Return a color style based on cost magnitude."""
    if c >= 50:
        return "bold red"
    if c >= 10:
        return "yellow"
    if c >= 1:
        return "green"
    return "dim green"


def short_model(model: str) -> str:
    """Shorten model name for display."""
    m = model.replace("claude-", "")
    # Strip -YYYYMMDD date suffix
    if len(m) > 9 and m[-9] == "-" and m[-8:].isdigit():
        m = m[:-9]
    return m


MODELS_MIN_WIDTH = 12
"""Below this a Models column shows nothing but an ellipsis, so drop it."""


def _flex_cell(text: str) -> Text:
    """Build a cell for the Models column, the only column Rich may shrink.

    Rich takes width from wrappable columns first. When every column is no_wrap
    it instead shaves all of them evenly, which is what turned the numbers into
    '14.…'. The cell keeps no_wrap so a shrunk column truncates on one line
    rather than wrapping onto two.
    """
    return Text(text, no_wrap=True, overflow="ellipsis")


def _models_cell(models: set[str]) -> Text:
    """Render a bucket's model set as a single-line, truncatable cell."""
    return _flex_cell(", ".join(sorted(short_model(m) for m in models)))


def _column_width(column) -> int:
    """Natural width of a column: its widest cell, header included."""
    widths = [Text.from_markup(str(column.header)).cell_len]
    widths += [
        cell.cell_len if isinstance(cell, Text) else Text.from_markup(str(cell)).cell_len
        for cell in column._cells  # noqa: SLF001 - Rich exposes no public accessor
    ]
    return max(widths)


def _print_report(table: Table) -> None:
    """Print a report table, dropping Models when the terminal is too narrow.

    Rich empties the wrappable Models column before shaving anything else, but it
    takes it all the way to zero and then shaves the numbers regardless, leaving a
    dead column behind. Removing it first keeps the rest of the table readable.
    """
    if table.columns and str(table.columns[-1].header) == "Models":
        padding = table.padding[1] + table.padding[3]
        fixed = sum(_column_width(c) + padding for c in table.columns[:-1])
        if console.width - fixed - table._extra_width < MODELS_MIN_WIDTH:  # noqa: SLF001
            table.columns.pop()
    console.print()
    console.print(table)
    console.print()


def _make_report_table(
    title: str,
    label_col: str,
    *,
    narrow: bool = False,
    compact: bool = False,
    label_style: str = "white",
    nok: NokCtx,
) -> Table:
    """Create a standard report table with label + token + optional Models columns."""
    table = Table(title=title, title_style="bold", box=box.ROUNDED, expand=False, show_lines=False)
    table.add_column(label_col, style=label_style, no_wrap=True)
    _add_token_columns(table, compact=compact, narrow=narrow, nok=nok)
    if not narrow:
        # The only wrappable column, so Rich takes width from here first.
        table.add_column("Models", style="dim")
    return table


def _add_token_columns(table: Table, *, compact: bool = False, narrow: bool = False, nok: NokCtx) -> None:
    """Add the standard token + cost columns to a table."""
    cost_label = "USD" if nok.enabled else "Cost"
    if narrow:
        table.add_column(cost_label, justify="right", no_wrap=True)
        if nok.enabled:
            table.add_column(nok.label, justify="right", style="cyan", no_wrap=True)
        table.add_column("Tokens", justify="right", style="bold", no_wrap=True)
        table.add_column("Calls", justify="right", style="dim", no_wrap=True)
        return
    table.add_column("Input", justify="right", style="cyan", no_wrap=True)
    table.add_column("Output", justify="right", style="cyan", no_wrap=True)
    if not compact:
        table.add_column("Cache W", justify="right", style="blue", no_wrap=True)
        table.add_column("Cache R", justify="right", style="blue", no_wrap=True)
    table.add_column("Total", justify="right", style="bold", no_wrap=True)
    table.add_column(cost_label, justify="right", no_wrap=True)
    if nok.enabled:
        table.add_column(nok.label, justify="right", style="cyan", no_wrap=True)
    table.add_column("%", justify="right", style="dim", no_wrap=True)
    table.add_column("Calls", justify="right", style="dim", no_wrap=True)


def _fmt_cache_read(t: TokenCounts) -> str:
    """Format cache read tokens with hit rate: '9.0M (87%)'."""
    s = fmt_tokens(t.cache_read)
    total_input = t.input + t.cache_create + t.cache_read
    if total_input > 0 and t.cache_read > 0:
        pct = t.cache_read / total_input * 100
        s += f" ({pct:.0f}%)"
    return s


def _token_row(b: "AggBucket", total_cost: float = 0.0, *, compact: bool = False, narrow: bool = False, nok: NokCtx) -> list:
    """Build the token/cost cells for a bucket."""
    cost_text = Text(fmt_cost(b.cost), style=cost_style(b.cost))
    if narrow:
        cells = [cost_text]
        if nok.enabled:
            cells.append(Text(fmt_nok(b.cost_nok, b.nok_estimated), style="cyan"))
        cells += [fmt_tokens(b.tokens.total), str(b.count)]
        return cells
    row = [
        fmt_tokens(b.tokens.input),
        fmt_tokens(b.tokens.output),
    ]
    if not compact:
        row += [fmt_tokens(b.tokens.cache_create), _fmt_cache_read(b.tokens)]
    row += [
        fmt_tokens(b.tokens.total),
        cost_text,
    ]
    if nok.enabled:
        row.append(Text(fmt_nok(b.cost_nok, b.nok_estimated), style="cyan"))
    row += [
        fmt_pct(b.cost, total_cost),
        str(b.count),
    ]
    return row


# --- Reports ---


def _summary_row(
    table: Table,
    label: str,
    cost: float,
    *,
    narrow: bool,
    nok: NokCtx,
    nok_cost: float = 0.0,
    nok_estimated: bool = False,
    lead: Sequence = (),
    after: Sequence = ("", ""),
    note: str | Text = "",
    style: str = "dim",
    label_style: str = "dim bold",
) -> None:
    """Append one padded summary row — AVG, PROJECTED, AVERAGE across all.

    The run of empty cells between the label and the cost comes from
    ``len(table.columns)``, so a column added anywhere shifts every summary row
    at once instead of leaving hand-counted padding to re-derive per caller.

    *lead* fills label columns after the first (Session/Project/Date tables);
    *after* the two cells past the money block (%/Calls, or Tokens/Calls when
    narrow); *note* the trailing Models cell, which narrow tables do not have.
    """
    head: list = [Text(label, style=label_style), *lead]
    money: list = [Text(fmt_cost(cost), style=cost_style(cost))]
    if nok.enabled:
        money.append(Text(fmt_nok(nok_cost, nok_estimated), style=f"{style} cyan"))
    tail: list = [] if narrow else [note]
    pad = len(table.columns) - len(head) - len(money) - len(after) - len(tail)
    table.add_row(*head, *[""] * pad, *money, *after, *tail, style=style)


def _add_summary_rows(
    table: Table,
    total_agg: "AggBucket",
    n_buckets: int,
    *,
    narrow: bool,
    compact: bool = False,
    avg_label: str = "",
    nok: NokCtx,
) -> None:
    """Append TOTAL and optional AVG rows to a report table."""
    table.add_section()
    total_row = [Text("TOTAL", style="bold"), *_token_row(total_agg, compact=compact, narrow=narrow, nok=nok)]
    if not narrow:
        total_row.append(_flex_cell(f"{len(total_agg.models)} models"))
    table.add_row(*total_row, style="bold")
    if n_buckets > 1 and (narrow or avg_label):
        _summary_row(
            table, "AVG" if narrow else "AVERAGE", total_agg.cost / n_buckets,
            narrow=narrow, nok=nok,
            nok_cost=total_agg.cost_nok / n_buckets if nok.enabled else 0.0,
            nok_estimated=total_agg.nok_estimated,
            note=_flex_cell(avg_label),
        )


def report_daily(records: list[UsageRecord], breakdown: bool = False, *, nok: NokCtx) -> None:
    """Print daily usage report."""
    narrow = _is_narrow()

    def day_of(rec: UsageRecord) -> str:
        return rec.timestamp.astimezone().strftime("%Y-%m-%d")

    buckets = _bucket_by(records, day_of, nok)
    # Breakdown rows are the same aggregation one level finer, so they come from
    # the same helper keyed by (day, model) rather than a nested copy of it.
    model_buckets = (
        _bucket_by(records, lambda r: (day_of(r), r.model), nok)
        if breakdown else {}
    )
    models_per_day: dict[str, list[str]] = defaultdict(list)
    for day, model in model_buckets:
        models_per_day[day].append(model)

    table = _make_report_table(f"Daily Usage ({len(buckets)} days)", "Date", narrow=narrow, nok=nok)

    total_cost = sum(b.cost for b in buckets.values())
    total_agg = AggBucket()
    for day in sorted(buckets):
        b = buckets[day]
        row = [day, *_token_row(b, total_cost, narrow=narrow, nok=nok)]
        if not narrow:
            row.append(_models_cell(b.models))
        table.add_row(*row)
        total_agg += b

        for model in sorted(models_per_day[day]):
            mb = model_buckets[day, model]
            brow = [f"  [dim]{short_model(model)}[/dim]", *_token_row(mb, total_cost, narrow=narrow, nok=nok)]
            if not narrow:
                brow.append("")
            table.add_row(*brow)

    _add_summary_rows(table, total_agg, len(buckets), narrow=narrow, avg_label="per day", nok=nok)

    _print_report(table)


def report_monthly(records: list[UsageRecord], *, nok: NokCtx) -> None:
    """Print monthly usage report."""
    narrow = _is_narrow()
    buckets = _bucket_by(
        records, lambda r: r.timestamp.astimezone().strftime("%Y-%m"), nok,
    )

    table = _make_report_table(f"Monthly Usage ({len(buckets)} months)", "Month", narrow=narrow, nok=nok)

    total_cost = sum(b.cost for b in buckets.values())
    total_agg = AggBucket()
    for month in sorted(buckets):
        b = buckets[month]
        row = [month, *_token_row(b, total_cost, narrow=narrow, nok=nok)]
        if not narrow:
            row.append(_models_cell(b.models))
        table.add_row(*row)
        total_agg += b

    _add_summary_rows(table, total_agg, len(buckets), narrow=narrow, avg_label="per month", nok=nok)

    # Projected cost for the current (latest) partial month
    latest_month = max(buckets)
    today = datetime.now().astimezone()
    current_month_key = today.strftime("%Y-%m")
    latest_est = buckets[latest_month].nok_estimated if nok.enabled else False
    if latest_month == current_month_key:
        table.add_section()
        days_elapsed = today.day
        days_in_month = calendar.monthrange(today.year, today.month)[1]
        if days_elapsed < days_in_month:
            projected = buckets[latest_month].cost / days_elapsed * days_in_month
            projected_nok = buckets[latest_month].cost_nok / days_elapsed * days_in_month if nok.enabled else 0.0
            _summary_row(
                table, "PROJ" if narrow else "PROJECTED", projected,
                narrow=narrow, nok=nok,
                nok_cost=projected_nok, nok_estimated=latest_est,
                note=f"({days_elapsed}/{days_in_month} days in {today.strftime('%B')})",
                label_style="dim bold italic",
            )

            # Projected based on trailing 14-day daily average
            window = 14
            end_14d = today.replace(hour=0, minute=0, second=0, microsecond=0)
            start_14d = end_14d - timedelta(days=window)
            recent = [r for r in records if start_14d <= r.timestamp.astimezone() < end_14d]
            b14 = _bucket_by(recent, lambda _r: "14d", nok)
            agg_14d = b14.get("14d", AggBucket())
            if agg_14d.cost > 0:
                projected_14d = agg_14d.cost / window * days_in_month
                projected_14d_nok = (agg_14d.cost_nok / window) * days_in_month if nok.enabled else 0.0
                _summary_row(
                    table, "PROJ 14d" if narrow else "PROJECTED", projected_14d,
                    narrow=narrow, nok=nok,
                    nok_cost=projected_14d_nok, nok_estimated=agg_14d.nok_estimated,
                    note=_flex_cell(f"Last {window} days avg"),
                    label_style="dim bold italic",
                )

    _print_report(table)


def report_project(records: list[UsageRecord], limit: int | None = 20, *, nok: NokCtx) -> None:
    """Print per-project usage report."""
    narrow = _is_narrow()
    buckets = _bucket_by(records, lambda r: r.project, nok)

    sorted_projects = sorted(buckets, key=lambda p: buckets[p].cost, reverse=True)
    if limit and len(sorted_projects) > limit:
        shown = f"top {limit} of {len(sorted_projects)}"
        sorted_projects = sorted_projects[:limit]
    else:
        shown = str(len(sorted_projects))

    table = _make_report_table(f"Projects ({shown})", "Project", narrow=narrow, compact=True, label_style="magenta", nok=nok)

    total_cost = sum(buckets[p].cost for p in sorted_projects)
    total_agg = AggBucket()
    for proj in sorted_projects:
        b = buckets[proj]
        row = [proj, *_token_row(b, total_cost, compact=True, narrow=narrow, nok=nok)]
        if not narrow:
            row.append(_models_cell(b.models))
        table.add_row(*row)
        total_agg += b

    _add_summary_rows(table, total_agg, len(sorted_projects), narrow=narrow, compact=True,
                      avg_label=f"per project (top {len(sorted_projects)})", nok=nok)
    # Average across ALL projects
    all_n = len(buckets)
    all_any_est = any(b.nok_estimated for b in buckets.values()) if nok.enabled else False
    if all_n > 1:
        all_cost = sum(b.cost for b in buckets.values())
        all_nok = sum(b.cost_nok for b in buckets.values())
        _summary_row(
            table, "AVG" if narrow else "AVERAGE", all_cost / all_n,
            narrow=narrow, nok=nok,
            nok_cost=all_nok / all_n if nok.enabled else 0.0, nok_estimated=all_any_est,
            after=(f"all {all_n}", "") if narrow else ("", ""),
            note=_flex_cell(f"per project (all {all_n})"),
        )

    _print_report(table)


def report_session(records: list[UsageRecord], limit: int | None = 20, *, nok: NokCtx) -> None:
    """Print per-session usage report."""
    narrow = _is_narrow()
    buckets = _bucket_by(records, lambda r: r.session_id, nok)
    session_meta: dict[str, dict] = {}

    for rec in records:
        sid = rec.session_id
        meta = session_meta.setdefault(sid, {"project": rec.project, "first": rec.timestamp, "last": rec.timestamp})
        if rec.timestamp < meta["first"]:
            meta["first"] = rec.timestamp
        if rec.timestamp > meta["last"]:
            meta["last"] = rec.timestamp

    sorted_sessions = sorted(buckets, key=lambda s: buckets[s].cost, reverse=True)
    if limit:
        sorted_sessions = sorted_sessions[:limit]

    if limit and len(buckets) > limit:
        shown = f"top {limit} of {len(buckets)}"
    else:
        shown = str(len(buckets))

    table = Table(title=f"Sessions ({shown})", title_style="bold", box=box.ROUNDED, expand=False, show_lines=False)
    if narrow:
        table.add_column("Project", style="magenta", no_wrap=True)
        table.add_column("Date", style="white", no_wrap=True)
        _add_token_columns(table, narrow=True, nok=nok)
    else:
        table.add_column("Session", style="dim", no_wrap=True)
        table.add_column("Project", style="magenta", no_wrap=True)
        table.add_column("Date", style="white", no_wrap=True)
        # Same token columns as every other wide report, minus the cache pair.
        _add_token_columns(table, compact=True, nok=nok)
        table.add_column("Models", style="dim")

    total_cost = sum(buckets[s].cost for s in sorted_sessions)
    total_agg = AggBucket()
    for sid in sorted_sessions:
        b = buckets[sid]
        meta = session_meta[sid]
        cost_text = Text(fmt_cost(b.cost), style=cost_style(b.cost))
        if narrow:
            cells = [
                meta["project"],
                meta["last"].astimezone().strftime("%m-%d %H:%M"),
                cost_text,
            ]
            if nok.enabled:
                cells.append(Text(fmt_nok(b.cost_nok, b.nok_estimated), style="cyan"))
            cells += [fmt_tokens(b.tokens.total), str(b.count)]
            table.add_row(*cells)
        else:
            short_sid = sid[-8:] if len(sid) > 8 else sid
            models_str = _models_cell(b.models)
            cells = [
                short_sid,
                meta["project"],
                meta["last"].astimezone().strftime("%Y-%m-%d %H:%M"),
                fmt_tokens(b.tokens.input),
                fmt_tokens(b.tokens.output),
                fmt_tokens(b.tokens.total),
                cost_text,
            ]
            if nok.enabled:
                cells.append(Text(fmt_nok(b.cost_nok, b.nok_estimated), style="cyan"))
            cells += [
                fmt_pct(b.cost, total_cost),
                str(b.count),
                models_str,
            ]
            table.add_row(*cells)
        total_agg += b

    table.add_section()
    total_cost_text = Text(fmt_cost(total_agg.cost), style=cost_style(total_agg.cost))
    if narrow:
        cells = [
            Text("TOTAL", style="bold"),
            f"({shown})",
            total_cost_text,
        ]
        if nok.enabled:
            cells.append(Text(fmt_nok(total_agg.cost_nok, total_agg.nok_estimated), style="bold cyan"))
        cells += [fmt_tokens(total_agg.tokens.total), str(total_agg.count)]
        table.add_row(*cells, style="bold")
    else:
        cells = [
            Text("TOTAL", style="bold"),
            "",
            f"({shown})",
            fmt_tokens(total_agg.tokens.input),
            fmt_tokens(total_agg.tokens.output),
            fmt_tokens(total_agg.tokens.total),
            total_cost_text,
        ]
        if nok.enabled:
            cells.append(Text(fmt_nok(total_agg.cost_nok, total_agg.nok_estimated), style="bold cyan"))
        cells += ["", str(total_agg.count), ""]
        table.add_row(*cells, style="bold")
    n = len(sorted_sessions)
    if n > 1:
        _summary_row(
            table, "AVG" if narrow else "AVERAGE", total_agg.cost / n,
            narrow=narrow, nok=nok,
            nok_cost=total_agg.cost_nok / n if nok.enabled else 0.0,
            nok_estimated=total_agg.nok_estimated,
            lead=("",), note=_flex_cell(f"per session (top {n})"),
        )
    # Average across ALL sessions
    all_n = len(buckets)
    all_any_est = any(b.nok_estimated for b in buckets.values()) if nok.enabled else False
    if all_n > 1:
        all_cost = sum(b.cost for b in buckets.values())
        all_nok = sum(b.cost_nok for b in buckets.values())
        _summary_row(
            table, "AVG" if narrow else "AVERAGE", all_cost / all_n,
            narrow=narrow, nok=nok,
            nok_cost=all_nok / all_n if nok.enabled else 0.0, nok_estimated=all_any_est,
            lead=(f"all {all_n}",) if narrow else ("",),
            note=_flex_cell(f"per session (all {all_n})"),
        )

    _print_report(table)


def report_json(records: list[UsageRecord], *, nok: NokCtx) -> None:
    """Output all records as JSON for programmatic use."""
    output = []
    for rec in records:
        cost = record_cost(rec)
        entry: dict[str, Any] = {
            "message_id": rec.message_id,
            "model": rec.model,
            "timestamp": rec.timestamp.isoformat(),
            "session_id": rec.session_id,
            "project": rec.project,
            "input_tokens": rec.tokens.input,
            "output_tokens": rec.tokens.output,
            "cache_creation_tokens": rec.tokens.cache_create,
            "cache_read_tokens": rec.tokens.cache_read,
            "total_tokens": rec.tokens.total,
            "cost_usd": round(cost, 6),
        }
        if nok.enabled:
            amount, estimated = record_cost_nok(rec, cost, nok)
            if amount is not None:
                entry["cost_nok"] = round(amount, 4)
                if estimated:
                    entry["cost_nok_estimated"] = True
        output.append(entry)
    print(json.dumps(output, indent=2))


def parse_date(s: str) -> datetime:
    """Parse YYYYMMDD or YYYY-MM-DD into a timezone-aware datetime (local midnight)."""
    from zoneinfo import ZoneInfo

    s = s.replace("-", "")
    dt = datetime.strptime(s, "%Y%m%d")
    try:
        from pricing import _local_tz
        tz = _local_tz()
    except Exception:  # noqa: BLE001
        tz = ZoneInfo("UTC")
    return dt.replace(tzinfo=tz)


def cmd_overrides(args) -> None:
    """Manage the local project-grouping override rules."""
    if args.command == "merge":
        add_project_override(args.kind, args.source, args.target)
        label = args.source if args.kind == "name" else f"{args.kind}:{args.source}"
        print(f"Grouping {label} -> {args.target}")
        return
    if args.command == "unmerge":
        n = delete_project_override(args.source, args.kind)
        print(f"Removed {n} rule(s) matching {args.source!r}")
        return
    # overrides: list
    rules = get_project_overrides()
    if not rules:
        print("No override rules. Add one with: ccreport merge <from> <into>")
        return
    width = max(len(r["match_value"]) for r in rules)
    for r in rules:
        kind = "" if r["match_kind"] == "name" else f"[{r['match_kind']}] "
        print(f"  {kind}{r['match_value']:<{width}}  ->  {r['target']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze Claude Code token usage and costs from local JSONL logs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  ccusage.py daily --since 20260201\n"
               "  ccusage.py monthly\n"
               "  ccusage.py session --limit 10\n"
               "  ccusage.py daily --breakdown --project myapp\n",
    )
    sub = parser.add_subparsers(dest="command", help="Report type")

    # Common args
    for name in ["daily", "monthly", "project", "session"]:
        p = sub.add_parser(name)
        p.add_argument("--since", help="Start date (YYYYMMDD or YYYY-MM-DD)")
        p.add_argument("--until", help="End date (YYYYMMDD or YYYY-MM-DD)")
        p.add_argument("--project", "-p", help="Filter by project name (substring match)")
        p.add_argument("--json", "-j", action="store_true", help="Output as JSON")
        p.add_argument("--no-mva", action="store_true", help="Show NOK without 25%% MVA")
        if name == "daily":
            p.add_argument("--breakdown", "-b", action="store_true", help="Show per-model breakdown")
        if name == "project":
            p.add_argument("--limit", "-l", type=int, default=20, help="Max projects to show (0=all)")
        if name == "session":
            p.add_argument("--limit", "-l", type=int, default=20, help="Max sessions to show (0=all)")

    # Project-grouping overrides (manual merges/renames, stored locally)
    sub.add_parser("overrides", help="List manual project-grouping rules")
    pm = sub.add_parser("merge", help="Group one project name into another")
    pm.add_argument("source", help="Name to remap (or remote/cwd-prefix with --kind)")
    pm.add_argument("target", help="Project name to group it under")
    pm.add_argument("--kind", choices=["name", "remote", "cwd_prefix"], default="name",
                    help="What 'source' matches against (default: name)")
    pu = sub.add_parser("unmerge", help="Remove a grouping rule")
    pu.add_argument("source", help="The rule's match value to remove")
    pu.add_argument("--kind", choices=["name", "remote", "cwd_prefix"],
                    help="Restrict removal to this match kind")

    # Default: show all three reports
    parser.add_argument("--since", help="Start date (YYYYMMDD or YYYY-MM-DD)")
    parser.add_argument("--until", help="End date (YYYYMMDD or YYYY-MM-DD)")
    parser.add_argument("--project", "-p", help="Filter by project name")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")
    parser.add_argument("--no-mva", action="store_true", help="Show NOK without 25%% MVA")

    args = parser.parse_args()

    if args.command in ("overrides", "merge", "unmerge"):
        cmd_overrides(args)
        return

    mva = not args.no_mva

    since = parse_date(args.since) if args.since else None
    until = parse_date(args.until) if args.until else None
    project_filter = args.project if hasattr(args, "project") else None

    records = load_all_records(since=since, until=until, project_filter=project_filter)

    if not records:
        print("No usage records found.", file=sys.stderr)
        sys.exit(1)

    # Bulk-load exchange rates for all records
    nok, has_full_coverage = load_rates_for_records(records, mva=mva)
    if nok.enabled and not has_full_coverage:
        print("⚠ Some dates lack exchange rate data; NOK values are partial.", file=sys.stderr)

    if hasattr(args, "json") and args.json:
        report_json(records, nok=nok)
        return

    command = args.command

    if command == "daily":
        report_daily(records, breakdown=args.breakdown, nok=nok)
    elif command == "monthly":
        report_monthly(records, nok=nok)
    elif command == "project":
        lim = args.limit if args.limit != 0 else None
        report_project(records, limit=lim, nok=nok)
    elif command == "session":
        lim = args.limit if args.limit != 0 else None
        report_session(records, limit=lim, nok=nok)
    else:
        # No subcommand: show daily + monthly summary
        report_daily(records, nok=nok)
        report_monthly(records, nok=nok)
        report_project(records, nok=nok)
        report_session(records, nok=nok)


if __name__ == "__main__":
    main()
