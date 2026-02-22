#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["orjson", "rich"]
# ///
"""Analyze Claude Code token usage and costs from local JSONL session logs."""

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import orjson

# Per-token pricing for Claude models (time-aware).
# Source: https://github.com/BerriAI/litellm model_prices_and_context_window.json
# Each period lists models introduced or whose pricing changed on that date.
# Lookup walks periods in reverse to find the most recent entry for a model.
LAST_CHECKED = "2026-02-22"

PRICING_HISTORY: list[dict] = [
    {
        # Models available before Opus 4.6 / Sonnet 4.6 releases.
        "effective": "2025-01-01",
        "models": {
            "claude-opus-4-5-20251101": {
                "input": 5e-06,
                "output": 25e-06,
                "cache_create": 6.25e-06,
                "cache_read": 0.5e-06,
            },
            "claude-sonnet-4-20250514": {
                "input": 3e-06,
                "output": 15e-06,
                "cache_create": 3.75e-06,
                "cache_read": 0.3e-06,
                "input_200k": 6e-06,
                "output_200k": 22.5e-06,
                "cache_create_200k": 7.5e-06,
                "cache_read_200k": 0.6e-06,
            },
            "claude-haiku-4-5-20251001": {
                "input": 1e-06,
                "output": 5e-06,
                "cache_create": 1.25e-06,
                "cache_read": 0.1e-06,
            },
            "claude-sonnet-4-5-20250929": {
                "input": 3e-06,
                "output": 15e-06,
                "cache_create": 3.75e-06,
                "cache_read": 0.3e-06,
                "input_200k": 6e-06,
                "output_200k": 22.5e-06,
                "cache_create_200k": 7.5e-06,
                "cache_read_200k": 0.6e-06,
            },
            "<synthetic>": {
                "input": 0.0,
                "output": 0.0,
                "cache_create": 0.0,
                "cache_read": 0.0,
            },
        },
    },
    {
        # Claude Opus 4.6 released
        "effective": "2026-02-05",
        "models": {
            "claude-opus-4-6": {
                "input": 5e-06,
                "output": 25e-06,
                "cache_create": 6.25e-06,
                "cache_read": 0.5e-06,
                "input_200k": 10e-06,
                "output_200k": 37.5e-06,
                "cache_create_200k": 12.5e-06,
                "cache_read_200k": 1e-06,
            },
        },
    },
    {
        # Claude Sonnet 4.6 released
        "effective": "2026-02-17",
        "models": {
            "claude-sonnet-4-6": {
                "input": 3e-06,
                "output": 15e-06,
                "cache_create": 3.75e-06,
                "cache_read": 0.3e-06,
                "input_200k": 6e-06,
                "output_200k": 22.5e-06,
                "cache_create_200k": 7.5e-06,
                "cache_read_200k": 0.6e-06,
            },
        },
    },
]

# Aliases: map model IDs to their pricing key
MODEL_ALIASES: dict[str, str] = {
    "claude-opus-4-5": "claude-opus-4-5-20251101",
    "claude-sonnet-4": "claude-sonnet-4-20250514",
    "claude-sonnet-4-5": "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5": "claude-haiku-4-5-20251001",
}

TIER_THRESHOLD = 200_000


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


def _parse_effective(date_str: str) -> datetime:
    """Parse an effective date string to a timezone-aware datetime."""
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def find_pricing(model: str, ts: datetime | None = None) -> dict[str, float] | None:
    """Find pricing for a model at a given timestamp.

    Walks PRICING_HISTORY in reverse chronological order, returning the first
    match for a period whose effective date is <= *ts*.
    """
    resolved = MODEL_ALIASES.get(model, model)

    for period in reversed(PRICING_HISTORY):
        effective = _parse_effective(period["effective"])
        if ts is not None and effective > ts:
            continue
        models = period["models"]
        # Exact match
        if resolved in models:
            return models[resolved]
        # Substring match: e.g. "claude-opus-4-6" <-> "claude-opus-4-6-20260101"
        for key, prices in models.items():
            if key in resolved or resolved in key:
                return prices
    return None


def _tiered_cost(count: int, base_rate: float, tiered_rate: float | None) -> float:
    """Calculate cost for a single token type with per-type 200K tiering."""
    if count > TIER_THRESHOLD and tiered_rate is not None:
        below = min(count, TIER_THRESHOLD)
        above = count - below
        return below * base_rate + above * tiered_rate
    return count * base_rate


def calc_cost(tokens: TokenCounts, model: str, ts: datetime | None = None) -> float:
    """Calculate cost for token counts using model-specific pricing.

    The 200K tier is applied per token type independently: each type's count
    is checked against the threshold separately (matching ccusage behavior).
    """
    prices = find_pricing(model, ts)
    if not prices:
        return 0.0

    return (
        _tiered_cost(tokens.input, prices.get("input", 0.0), prices.get("input_200k"))
        + _tiered_cost(tokens.output, prices.get("output", 0.0), prices.get("output_200k"))
        + _tiered_cost(tokens.cache_create, prices.get("cache_create", 0.0), prices.get("cache_create_200k"))
        + _tiered_cost(tokens.cache_read, prices.get("cache_read", 0.0), prices.get("cache_read_200k"))
    )


def record_cost(rec: UsageRecord) -> float:
    """Return cost for a record: use pre-calculated costUSD if available, else compute."""
    if rec.cost_usd is not None:
        return rec.cost_usd
    return calc_cost(rec.tokens, rec.model, rec.timestamp)


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
    dirs = []
    claude_dir = Path.home() / ".claude" / "projects"
    config_dir = Path.home() / ".config" / "claude" / "projects"
    if claude_dir.is_dir():
        dirs.append(claude_dir)
    if config_dir.is_dir():
        dirs.append(config_dir)

    files = []
    for d in dirs:
        files.extend(d.rglob("*.jsonl"))
    return sorted(files)


def parse_jsonl_file(path: Path) -> list[UsageRecord]:
    """Parse a single JSONL file and extract usage records."""
    records = []
    # Derive project name from parent directory
    project = project_display_name(path.parent.name)
    # Check if this is a subagent file (nested deeper)
    if path.parent.name == "subagents":
        project = project_display_name(path.parent.parent.parent.name)

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

                if rec.get("type") != "assistant":
                    continue
                msg = rec.get("message")
                if not msg or not isinstance(msg, dict):
                    continue
                usage = msg.get("usage")
                if not usage or not isinstance(usage, dict):
                    continue

                message_id = msg.get("id", "")
                request_id = rec.get("requestId", "")

                # Build composite dedup key (message_id:request_id).
                # If either is missing, dedup_key is None → record is never
                # considered a duplicate (matching ccusage behavior).
                if message_id and request_id:
                    dedup_key = f"{message_id}:{request_id}"
                else:
                    dedup_key = None

                tokens = TokenCounts(
                    input=usage.get("input_tokens", 0),
                    output=usage.get("output_tokens", 0),
                    cache_create=usage.get("cache_creation_input_tokens", 0),
                    cache_read=usage.get("cache_read_input_tokens", 0),
                )

                ts_str = rec.get("timestamp", "")
                try:
                    ts = datetime.fromisoformat(ts_str)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    continue

                # Pre-calculated cost from Claude Code (used in auto mode)
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

    Deduplication uses a composite key of message_id + request_id
    (matching ccusage).  First occurrence wins.  Records lacking either
    ID are never deduplicated — they always pass through.
    """
    files = discover_jsonl_files()
    seen_keys: set[str] = set()
    all_records: list[UsageRecord] = []

    for path in files:
        for rec in parse_jsonl_file(path):
            if since and rec.timestamp < since:
                continue
            if until and rec.timestamp > until:
                continue
            if project_filter and project_filter.lower() not in rec.project.lower():
                continue
            # Dedup: first occurrence wins; records without dedup_key always pass
            if rec.dedup_key is not None:
                if rec.dedup_key in seen_keys:
                    continue
                seen_keys.add(rec.dedup_key)
            all_records.append(rec)

    all_records.sort(key=lambda r: r.timestamp)
    return all_records


# --- Formatting ---

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

console = Console(soft_wrap=True)


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
    for suffix in ["-20251101", "-20250514", "-20251001", "-20250929"]:
        m = m.replace(suffix, "")
    return m


def _add_token_columns(table: Table) -> None:
    """Add the standard token + cost columns to a table."""
    table.add_column("Input", justify="right", style="cyan", no_wrap=True)
    table.add_column("Output", justify="right", style="cyan", no_wrap=True)
    table.add_column("Cache W", justify="right", style="blue", no_wrap=True)
    table.add_column("Cache R", justify="right", style="blue", no_wrap=True)
    table.add_column("Total", justify="right", style="bold", no_wrap=True)
    table.add_column("Cost", justify="right", no_wrap=True)
    table.add_column("Calls", justify="right", style="dim", no_wrap=True)


def _token_row(b: "AggBucket") -> list:
    """Build the token/cost cells for a bucket."""
    cost_text = Text(fmt_cost(b.cost), style=cost_style(b.cost))
    return [
        fmt_tokens(b.tokens.input),
        fmt_tokens(b.tokens.output),
        fmt_tokens(b.tokens.cache_create),
        fmt_tokens(b.tokens.cache_read),
        fmt_tokens(b.tokens.total),
        cost_text,
        str(b.count),
    ]


# --- Reports ---

def report_daily(records: list[UsageRecord], breakdown: bool = False) -> None:
    """Print daily usage report."""
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

    table = Table(title=f"Daily Usage ({len(buckets)} days)", title_style="bold", box=box.ROUNDED, expand=False, show_lines=False)
    table.add_column("Date", style="white", no_wrap=True)
    _add_token_columns(table)
    table.add_column("Models", style="dim", no_wrap=True)

    total_agg = AggBucket()
    for day in sorted(buckets):
        b = buckets[day]
        models_str = ", ".join(sorted(short_model(m) for m in b.models))
        table.add_row(day, *_token_row(b), models_str)
        total_agg.tokens += b.tokens
        total_agg.cost += b.cost
        total_agg.count += b.count
        total_agg.models |= b.models

        if breakdown:
            for model in sorted(model_buckets[day]):
                mb = model_buckets[day][model]
                table.add_row(f"  [dim]{short_model(model)}[/dim]", *_token_row(mb), "")

    table.add_section()
    total_agg.models = total_agg.models  # keep set
    table.add_row(
        Text("TOTAL", style="bold"),
        *_token_row(total_agg),
        f"{len(total_agg.models)} models",
        style="bold",
    )
    n = len(buckets)
    if n > 1:
        avg_cost = total_agg.cost / n
        table.add_row(
            Text("AVERAGE", style="dim bold"),
            "", "", "", "", "",
            Text(fmt_cost(avg_cost), style=cost_style(avg_cost)),
            "",
            f"per day",
            style="dim",
        )

    console.print()
    console.print(table)
    console.print()


def report_monthly(records: list[UsageRecord]) -> None:
    """Print monthly usage report."""
    buckets: dict[str, AggBucket] = defaultdict(AggBucket)

    for rec in records:
        month = rec.timestamp.astimezone().strftime("%Y-%m")
        b = buckets[month]
        b.tokens += rec.tokens
        b.cost += record_cost(rec)
        if rec.model != "<synthetic>":
            b.models.add(rec.model)
        b.count += 1

    table = Table(title=f"Monthly Usage ({len(buckets)} months)", title_style="bold", box=box.ROUNDED, expand=False, show_lines=False)
    table.add_column("Month", style="white", no_wrap=True)
    _add_token_columns(table)
    table.add_column("Models", style="dim", no_wrap=True)

    total_agg = AggBucket()
    for month in sorted(buckets):
        b = buckets[month]
        models_str = ", ".join(sorted(short_model(m) for m in b.models))
        table.add_row(month, *_token_row(b), models_str)
        total_agg.tokens += b.tokens
        total_agg.cost += b.cost
        total_agg.count += b.count
        total_agg.models |= b.models

    table.add_section()
    table.add_row(
        Text("TOTAL", style="bold"),
        *_token_row(total_agg),
        f"{len(total_agg.models)} models",
        style="bold",
    )
    n = len(buckets)
    if n > 1:
        avg_cost = total_agg.cost / n
        table.add_row(
            Text("AVERAGE", style="dim bold"),
            "", "", "", "", "",
            Text(fmt_cost(avg_cost), style=cost_style(avg_cost)),
            "",
            f"per month",
            style="dim",
        )

    console.print()
    console.print(table)
    console.print()


def report_project(records: list[UsageRecord], limit: int | None = 20) -> None:
    """Print per-project usage report."""
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

    table = Table(title=f"Projects ({shown})", title_style="bold", box=box.ROUNDED, expand=False, show_lines=False)
    table.add_column("Project", style="magenta", no_wrap=True)
    _add_token_columns(table)
    table.add_column("Models", style="dim", no_wrap=True)

    total_agg = AggBucket()
    for proj in sorted_projects:
        b = buckets[proj]
        models_str = ", ".join(sorted(short_model(m) for m in b.models))
        table.add_row(proj, *_token_row(b), models_str)
        total_agg.tokens += b.tokens
        total_agg.cost += b.cost
        total_agg.count += b.count
        total_agg.models |= b.models

    table.add_section()
    table.add_row(
        Text("TOTAL", style="bold"),
        *_token_row(total_agg),
        f"{len(total_agg.models)} models",
        style="bold",
    )
    n = len(sorted_projects)
    if n > 1:
        avg_cost = total_agg.cost / n
        table.add_row(
            Text("AVERAGE", style="dim bold"),
            "", "", "", "", "",
            Text(fmt_cost(avg_cost), style=cost_style(avg_cost)),
            "",
            f"per project (top {n})",
            style="dim",
        )
    # Average across ALL projects
    all_n = len(buckets)
    if all_n > 1:
        all_cost = sum(b.cost for b in buckets.values())
        all_avg = all_cost / all_n
        table.add_row(
            Text("AVERAGE", style="dim bold"),
            "", "", "", "", "",
            Text(fmt_cost(all_avg), style=cost_style(all_avg)),
            "",
            f"per project (all {all_n})",
            style="dim",
        )

    console.print()
    console.print(table)
    console.print()


def report_session(records: list[UsageRecord], limit: int | None = 20) -> None:
    """Print per-session usage report."""
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
    table.add_column("Session", style="dim", no_wrap=True)
    table.add_column("Project", style="magenta", no_wrap=True)
    table.add_column("Date", style="white", no_wrap=True)
    table.add_column("Input", justify="right", style="cyan", no_wrap=True)
    table.add_column("Output", justify="right", style="cyan", no_wrap=True)
    table.add_column("Total", justify="right", style="bold", no_wrap=True)
    table.add_column("Cost", justify="right", no_wrap=True)
    table.add_column("Calls", justify="right", style="dim", no_wrap=True)
    table.add_column("Models", style="dim", no_wrap=True)

    total_agg = AggBucket()
    for sid in sorted_sessions:
        b = buckets[sid]
        meta = session_meta[sid]
        short_sid = sid[-8:] if len(sid) > 8 else sid
        cost_text = Text(fmt_cost(b.cost), style=cost_style(b.cost))
        models_str = ", ".join(sorted(short_model(m) for m in b.models))
        table.add_row(
            short_sid,
            meta["project"],
            meta["last"].astimezone().strftime("%Y-%m-%d %H:%M"),
            fmt_tokens(b.tokens.input),
            fmt_tokens(b.tokens.output),
            fmt_tokens(b.tokens.total),
            cost_text,
            str(b.count),
            models_str,
        )
        total_agg.tokens += b.tokens
        total_agg.cost += b.cost
        total_agg.count += b.count

    table.add_section()
    total_cost = Text(fmt_cost(total_agg.cost), style=cost_style(total_agg.cost))
    table.add_row(
        Text("TOTAL", style="bold"),
        "",
        f"({shown})",
        fmt_tokens(total_agg.tokens.input),
        fmt_tokens(total_agg.tokens.output),
        fmt_tokens(total_agg.tokens.total),
        total_cost,
        str(total_agg.count),
        "",
        style="bold",
    )
    n = len(sorted_sessions)
    if n > 1:
        avg_cost = total_agg.cost / n
        table.add_row(
            Text("AVERAGE", style="dim bold"),
            "", "", "", "", "",
            Text(fmt_cost(avg_cost), style=cost_style(avg_cost)),
            "",
            f"per session (top {n})",
            style="dim",
        )
    # Average across ALL sessions
    all_n = len(buckets)
    if all_n > 1:
        all_cost = sum(b.cost for b in buckets.values())
        all_avg = all_cost / all_n
        table.add_row(
            Text("AVERAGE", style="dim bold"),
            "", "", "", "", "",
            Text(fmt_cost(all_avg), style=cost_style(all_avg)),
            "",
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
    """Parse YYYYMMDD or YYYY-MM-DD into a timezone-aware datetime."""
    s = s.replace("-", "")
    dt = datetime.strptime(s, "%Y%m%d")
    return dt.replace(tzinfo=timezone.utc)


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
