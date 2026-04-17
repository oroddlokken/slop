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
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import orjson
from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

# pricing.py and cache_db.py live in the same directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cache_db import (
    bulk_load_ccreport_cache,
    check_ccreport_valid,
    get_ccreport_orphaned_records,
    init_ccreport_meta,
    invalidate_ccreport,
    save_ccreport_file,
)
from pricing import calc_cost, extract_assistant_fields

_PROJECT_ROOTS = (
    Path.home() / ".claude" / "projects",
    Path.home() / ".config" / "claude" / "projects",
)

# --- File-level cache ---
CACHE_VERSION = 1


def _script_hash() -> str:
    """SHA256 of this script file, used to invalidate cache on code changes."""
    try:
        return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    except OSError:
        return ""


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


@dataclass
class AggBucket:
    tokens: TokenCounts = field(default_factory=TokenCounts)
    cost: float = 0.0
    models: set[str] = field(default_factory=set)
    count: int = 0


def record_cost(rec: UsageRecord) -> float:
    """Return cost for a record: use pre-calculated costUSD if available, else compute."""
    if rec.cost_usd is not None:
        return rec.cost_usd
    return calc_cost(
        rec.tokens.input, rec.tokens.output,
        rec.tokens.cache_create, rec.tokens.cache_read,
        rec.model, rec.timestamp,
    )


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


def _derive_project(path: Path) -> str:
    """Derive project display name from a JSONL file's location.

    The project key is the first directory component under a projects root:
      projects/project-key/session.jsonl → project-key
      projects/project-key/session-id/sub.jsonl → project-key
    """
    for root in _PROJECT_ROOTS:
        try:
            rel = path.relative_to(root)
            if rel.parts:
                return project_display_name(rel.parts[0])
        except ValueError:
            continue
    return project_display_name(path.parent.name)


def parse_jsonl_file(path: Path) -> list[UsageRecord]:
    """Parse a single JSONL file and extract usage records."""
    records = []
    project = _derive_project(path)

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
                    project=project,
                    cost_usd=cost_usd,
                    dedup_key=dedup_key,
                ))
    except (OSError, UnicodeDecodeError):
        pass

    return records


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

        for rec in records:
            if since and rec.timestamp < since:
                continue
            if until and rec.timestamp > until:
                continue
            if project_filter and project_filter.lower() not in rec.project.lower():
                continue
            if rec.dedup_key is not None:
                if rec.dedup_key in seen_keys:
                    continue
                seen_keys.add(rec.dedup_key)
            all_records.append(rec)

    # Load records from files that were purged from disk but cached in SQLite
    for raw in _deserialize_records(get_ccreport_orphaned_records(live_paths)):
        if since and raw.timestamp < since:
            continue
        if until and raw.timestamp > until:
            continue
        if project_filter and project_filter.lower() not in raw.project.lower():
            continue
        if raw.dedup_key is not None:
            if raw.dedup_key in seen_keys:
                continue
            seen_keys.add(raw.dedup_key)
        all_records.append(raw)

    all_records.sort(key=lambda r: r.timestamp)
    return all_records


# --- Formatting ---

console = Console(soft_wrap=True)
NARROW_WIDTH = 100


def _is_narrow() -> bool:
    return console.width < NARROW_WIDTH


def fmt_tokens(n: int) -> str:
    """Format token count with K/M suffix."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def fmt_cost(c: float) -> str:
    """Format cost in USD."""
    if c >= 1.0:
        return f"${c:.2f}"
    return f"${c:.4f}"


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


def _make_report_table(
    title: str,
    label_col: str,
    *,
    narrow: bool = False,
    compact: bool = False,
    label_style: str = "white",
) -> Table:
    """Create a standard report table with label + token + optional Models columns."""
    table = Table(title=title, title_style="bold", box=box.ROUNDED, expand=False, show_lines=False)
    table.add_column(label_col, style=label_style, no_wrap=True)
    _add_token_columns(table, compact=compact, narrow=narrow)
    if not narrow:
        table.add_column("Models", style="dim", no_wrap=True)
    return table


def _add_token_columns(table: Table, *, compact: bool = False, narrow: bool = False) -> None:
    """Add the standard token + cost columns to a table."""
    if narrow:
        table.add_column("Cost", justify="right", no_wrap=True)
        table.add_column("Tokens", justify="right", style="bold", no_wrap=True)
        table.add_column("Calls", justify="right", style="dim", no_wrap=True)
        return
    table.add_column("Input", justify="right", style="cyan", no_wrap=True)
    table.add_column("Output", justify="right", style="cyan", no_wrap=True)
    if not compact:
        table.add_column("Cache W", justify="right", style="blue", no_wrap=True)
        table.add_column("Cache R", justify="right", style="blue", no_wrap=True)
    table.add_column("Total", justify="right", style="bold", no_wrap=True)
    table.add_column("Cost", justify="right", no_wrap=True)
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


def _token_row(b: "AggBucket", total_cost: float = 0.0, *, compact: bool = False, narrow: bool = False) -> list:
    """Build the token/cost cells for a bucket."""
    cost_text = Text(fmt_cost(b.cost), style=cost_style(b.cost))
    if narrow:
        return [cost_text, fmt_tokens(b.tokens.total), str(b.count)]
    row = [
        fmt_tokens(b.tokens.input),
        fmt_tokens(b.tokens.output),
    ]
    if not compact:
        row += [fmt_tokens(b.tokens.cache_create), _fmt_cache_read(b.tokens)]
    row += [
        fmt_tokens(b.tokens.total),
        cost_text,
        fmt_pct(b.cost, total_cost),
        str(b.count),
    ]
    return row


# --- Reports ---


def _add_summary_rows(
    table: Table,
    total_agg: "AggBucket",
    n_buckets: int,
    *,
    narrow: bool,
    compact: bool = False,
    avg_label: str = "",
) -> None:
    """Append TOTAL and optional AVG rows to a report table."""
    table.add_section()
    total_row = [Text("TOTAL", style="bold"), *_token_row(total_agg, compact=compact, narrow=narrow)]
    if not narrow:
        total_row.append(f"{len(total_agg.models)} models")
    table.add_row(*total_row, style="bold")
    if n_buckets > 1:
        avg_cost = total_agg.cost / n_buckets
        if narrow:
            table.add_row(
                Text("AVG", style="dim bold"),
                Text(fmt_cost(avg_cost), style=cost_style(avg_cost)),
                "", "",
                style="dim",
            )
        elif avg_label:
            n_empty = 4 if not compact else 2
            table.add_row(
                Text("AVERAGE", style="dim bold"),
                *[""] * n_empty, "",
                Text(fmt_cost(avg_cost), style=cost_style(avg_cost)),
                "", "",
                avg_label,
                style="dim",
            )


def report_daily(records: list[UsageRecord], breakdown: bool = False) -> None:
    """Print daily usage report."""
    narrow = _is_narrow()
    buckets: dict[str, AggBucket] = defaultdict(AggBucket)
    model_buckets: dict[str, dict[str, AggBucket]] = defaultdict(lambda: defaultdict(AggBucket))

    for rec in records:
        day = rec.timestamp.astimezone().strftime("%Y-%m-%d")
        b = buckets[day]
        b.tokens += rec.tokens
        b.cost += record_cost(rec)
        if rec.model != "<synthetic>":
            b.models.add(rec.model)
        b.count += 1

        if breakdown:
            mb = model_buckets[day][rec.model]
            mb.tokens += rec.tokens
            mb.cost += record_cost(rec)
            mb.count += 1

    table = _make_report_table(f"Daily Usage ({len(buckets)} days)", "Date", narrow=narrow)

    total_cost = sum(b.cost for b in buckets.values())
    total_agg = AggBucket()
    for day in sorted(buckets):
        b = buckets[day]
        row = [day, *_token_row(b, total_cost, narrow=narrow)]
        if not narrow:
            row.append(", ".join(sorted(short_model(m) for m in b.models)))
        table.add_row(*row)
        total_agg.tokens += b.tokens
        total_agg.cost += b.cost
        total_agg.count += b.count
        total_agg.models |= b.models

        if breakdown:
            for model in sorted(model_buckets[day]):
                mb = model_buckets[day][model]
                brow = [f"  [dim]{short_model(model)}[/dim]", *_token_row(mb, total_cost, narrow=narrow)]
                if not narrow:
                    brow.append("")
                table.add_row(*brow)

    _add_summary_rows(table, total_agg, len(buckets), narrow=narrow, avg_label="per day")

    console.print()
    console.print(table)
    console.print()


def report_monthly(records: list[UsageRecord]) -> None:
    """Print monthly usage report."""
    narrow = _is_narrow()
    buckets: dict[str, AggBucket] = defaultdict(AggBucket)

    for rec in records:
        month = rec.timestamp.astimezone().strftime("%Y-%m")
        b = buckets[month]
        b.tokens += rec.tokens
        b.cost += record_cost(rec)
        if rec.model != "<synthetic>":
            b.models.add(rec.model)
        b.count += 1

    table = _make_report_table(f"Monthly Usage ({len(buckets)} months)", "Month", narrow=narrow)

    total_cost = sum(b.cost for b in buckets.values())
    total_agg = AggBucket()
    for month in sorted(buckets):
        b = buckets[month]
        row = [month, *_token_row(b, total_cost, narrow=narrow)]
        if not narrow:
            row.append(", ".join(sorted(short_model(m) for m in b.models)))
        table.add_row(*row)
        total_agg.tokens += b.tokens
        total_agg.cost += b.cost
        total_agg.count += b.count
        total_agg.models |= b.models

    _add_summary_rows(table, total_agg, len(buckets), narrow=narrow, avg_label="per month")

    # Projected cost for the current (latest) partial month
    latest_month = max(buckets)
    today = datetime.now().astimezone()
    current_month_key = today.strftime("%Y-%m")
    if latest_month == current_month_key:
        table.add_section()
        days_elapsed = today.day
        days_in_month = calendar.monthrange(today.year, today.month)[1]
        if days_elapsed < days_in_month:
            projected = buckets[latest_month].cost / days_elapsed * days_in_month
            if narrow:
                table.add_row(
                    Text("PROJ", style="dim bold italic"),
                    Text(fmt_cost(projected), style=cost_style(projected)),
                    "", "",
                    style="dim",
                )
            else:
                table.add_row(
                    Text("PROJECTED", style="dim bold italic"),
                    "", "", "", "", "",
                    Text(fmt_cost(projected), style=cost_style(projected)),
                    "", "",
                    f"({days_elapsed}/{days_in_month} days in {today.strftime('%B')})",
                    style="dim",
                )

            # Projected based on trailing 14-day daily average
            # Window: the 14 days ending yesterday (today is incomplete)
            window = 14
            end_14d = today.replace(hour=0, minute=0, second=0, microsecond=0)
            start_14d = end_14d - timedelta(days=window)
            cost_14d = 0.0
            for rec in records:
                rec_local = rec.timestamp.astimezone()
                if start_14d <= rec_local < end_14d:
                    cost_14d += record_cost(rec)
            if cost_14d > 0:
                avg_daily_14d = cost_14d / window
                projected_14d = avg_daily_14d * days_in_month
                if narrow:
                    table.add_row(
                        Text("PROJ 14d", style="dim bold italic"),
                        Text(fmt_cost(projected_14d), style=cost_style(projected_14d)),
                        "", "",
                        style="dim",
                    )
                else:
                    table.add_row(
                        Text("PROJECTED", style="dim bold italic"),
                        "", "", "", "", "",
                        Text(fmt_cost(projected_14d), style=cost_style(projected_14d)),
                        "", "",
                        f"Last {window} days avg",
                        style="dim",
                    )

    console.print()
    console.print(table)
    console.print()


def report_project(records: list[UsageRecord], limit: int | None = 20) -> None:
    """Print per-project usage report."""
    narrow = _is_narrow()
    buckets: dict[str, AggBucket] = defaultdict(AggBucket)

    for rec in records:
        b = buckets[rec.project]
        b.tokens += rec.tokens
        b.cost += record_cost(rec)
        if rec.model != "<synthetic>":
            b.models.add(rec.model)
        b.count += 1

    sorted_projects = sorted(buckets, key=lambda p: buckets[p].cost, reverse=True)
    if limit and len(sorted_projects) > limit:
        shown = f"top {limit} of {len(sorted_projects)}"
        sorted_projects = sorted_projects[:limit]
    else:
        shown = str(len(sorted_projects))

    table = _make_report_table(f"Projects ({shown})", "Project", narrow=narrow, compact=True, label_style="magenta")

    total_cost = sum(buckets[p].cost for p in sorted_projects)
    total_agg = AggBucket()
    for proj in sorted_projects:
        b = buckets[proj]
        row = [proj, *_token_row(b, total_cost, compact=True, narrow=narrow)]
        if not narrow:
            row.append(", ".join(sorted(short_model(m) for m in b.models)))
        table.add_row(*row)
        total_agg.tokens += b.tokens
        total_agg.cost += b.cost
        total_agg.count += b.count
        total_agg.models |= b.models

    _add_summary_rows(table, total_agg, len(sorted_projects), narrow=narrow, compact=True,
                      avg_label=f"per project (top {len(sorted_projects)})")
    # Average across ALL projects
    all_n = len(buckets)
    if all_n > 1:
        all_cost = sum(b.cost for b in buckets.values())
        all_avg = all_cost / all_n
        if narrow:
            table.add_row(
                Text("AVG", style="dim bold"),
                Text(fmt_cost(all_avg), style=cost_style(all_avg)),
                f"all {all_n}", "",
                style="dim",
            )
        else:
            table.add_row(
                Text("AVERAGE", style="dim bold"),
                "", "", "",
                Text(fmt_cost(all_avg), style=cost_style(all_avg)),
                "", "",
                f"per project (all {all_n})",
                style="dim",
            )

    console.print()
    console.print(table)
    console.print()


def report_session(records: list[UsageRecord], limit: int | None = 20) -> None:
    """Print per-session usage report."""
    narrow = _is_narrow()
    buckets: dict[str, AggBucket] = defaultdict(AggBucket)
    session_meta: dict[str, dict] = {}

    for rec in records:
        sid = rec.session_id
        b = buckets[sid]
        b.tokens += rec.tokens
        b.cost += record_cost(rec)
        if rec.model != "<synthetic>":
            b.models.add(rec.model)
        b.count += 1

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
        _add_token_columns(table, narrow=True)
    else:
        table.add_column("Session", style="dim", no_wrap=True)
        table.add_column("Project", style="magenta", no_wrap=True)
        table.add_column("Date", style="white", no_wrap=True)
        table.add_column("Input", justify="right", style="cyan", no_wrap=True)
        table.add_column("Output", justify="right", style="cyan", no_wrap=True)
        table.add_column("Total", justify="right", style="bold", no_wrap=True)
        table.add_column("Cost", justify="right", no_wrap=True)
        table.add_column("%", justify="right", style="dim", no_wrap=True)
        table.add_column("Calls", justify="right", style="dim", no_wrap=True)
        table.add_column("Models", style="dim", no_wrap=True)

    total_cost = sum(buckets[s].cost for s in sorted_sessions)
    total_agg = AggBucket()
    for sid in sorted_sessions:
        b = buckets[sid]
        meta = session_meta[sid]
        cost_text = Text(fmt_cost(b.cost), style=cost_style(b.cost))
        if narrow:
            table.add_row(
                meta["project"],
                meta["last"].astimezone().strftime("%m-%d %H:%M"),
                cost_text,
                fmt_tokens(b.tokens.total),
                str(b.count),
            )
        else:
            short_sid = sid[-8:] if len(sid) > 8 else sid
            models_str = ", ".join(sorted(short_model(m) for m in b.models))
            table.add_row(
                short_sid,
                meta["project"],
                meta["last"].astimezone().strftime("%Y-%m-%d %H:%M"),
                fmt_tokens(b.tokens.input),
                fmt_tokens(b.tokens.output),
                fmt_tokens(b.tokens.total),
                cost_text,
                fmt_pct(b.cost, total_cost),
                str(b.count),
                models_str,
            )
        total_agg.tokens += b.tokens
        total_agg.cost += b.cost
        total_agg.count += b.count

    table.add_section()
    total_cost_text = Text(fmt_cost(total_agg.cost), style=cost_style(total_agg.cost))
    if narrow:
        table.add_row(
            Text("TOTAL", style="bold"),
            f"({shown})",
            total_cost_text,
            fmt_tokens(total_agg.tokens.total),
            str(total_agg.count),
            style="bold",
        )
    else:
        table.add_row(
            Text("TOTAL", style="bold"),
            "",
            f"({shown})",
            fmt_tokens(total_agg.tokens.input),
            fmt_tokens(total_agg.tokens.output),
            fmt_tokens(total_agg.tokens.total),
            total_cost_text,
            "",
            str(total_agg.count),
            "",
            style="bold",
        )
    n = len(sorted_sessions)
    if n > 1:
        avg_cost = total_agg.cost / n
        if narrow:
            table.add_row(
                Text("AVG", style="dim bold"),
                "",
                Text(fmt_cost(avg_cost), style=cost_style(avg_cost)),
                "", "",
                style="dim",
            )
        else:
            table.add_row(
                Text("AVERAGE", style="dim bold"),
                "", "", "", "", "",
                Text(fmt_cost(avg_cost), style=cost_style(avg_cost)),
                "", "",
                f"per session (top {n})",
                style="dim",
            )
    # Average across ALL sessions
    all_n = len(buckets)
    if all_n > 1:
        all_cost = sum(b.cost for b in buckets.values())
        all_avg = all_cost / all_n
        if narrow:
            table.add_row(
                Text("AVG", style="dim bold"),
                f"all {all_n}",
                Text(fmt_cost(all_avg), style=cost_style(all_avg)),
                "", "",
                style="dim",
            )
        else:
            table.add_row(
                Text("AVERAGE", style="dim bold"),
                "", "", "", "", "",
                Text(fmt_cost(all_avg), style=cost_style(all_avg)),
                "", "",
                f"per session (all {all_n})",
                style="dim",
            )

    console.print()
    console.print(table)
    console.print()


def report_json(records: list[UsageRecord]) -> None:
    """Output all records as JSON for programmatic use."""
    output = []
    for rec in records:
        output.append({
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
            "cost_usd": round(record_cost(rec), 6),
        })
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
        if name == "daily":
            p.add_argument("--breakdown", "-b", action="store_true", help="Show per-model breakdown")
        if name == "project":
            p.add_argument("--limit", "-l", type=int, default=20, help="Max projects to show (0=all)")
        if name == "session":
            p.add_argument("--limit", "-l", type=int, default=20, help="Max sessions to show (0=all)")

    # Default: show all three reports
    parser.add_argument("--since", help="Start date (YYYYMMDD or YYYY-MM-DD)")
    parser.add_argument("--until", help="End date (YYYYMMDD or YYYY-MM-DD)")
    parser.add_argument("--project", "-p", help="Filter by project name")
    parser.add_argument("--json", "-j", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    since = parse_date(args.since) if args.since else None
    until = parse_date(args.until) if args.until else None
    project_filter = args.project if hasattr(args, "project") else None

    records = load_all_records(since=since, until=until, project_filter=project_filter)

    if not records:
        print("No usage records found.", file=sys.stderr)
        sys.exit(1)

    if hasattr(args, "json") and args.json:
        report_json(records)
        return

    command = args.command

    if command == "daily":
        report_daily(records, breakdown=args.breakdown)
    elif command == "monthly":
        report_monthly(records)
    elif command == "project":
        lim = args.limit if args.limit != 0 else None
        report_project(records, limit=lim)
    elif command == "session":
        lim = args.limit if args.limit != 0 else None
        report_session(records, limit=lim)
    else:
        # No subcommand: show daily + monthly summary
        report_daily(records)
        report_monthly(records)
        report_project(records)
        report_session(records)


if __name__ == "__main__":
    main()
