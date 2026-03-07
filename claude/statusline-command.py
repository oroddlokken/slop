#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["dogcat"]
# ///
"""Claude Code status line — Python implementation for performance.

Receives JSON via stdin, outputs a formatted status line to stdout.

AUDIT: All calculations are documented in claude/CLAUDE.md.
       When changing any calculation, caching, or data format here,
       update CLAUDE.md to match.

Layout adapts to terminal width (detected via $COLUMNS or /dev/tty):
  >= 130 columns: 2 lines (top+session | usage+costs)
  <  130 columns: 4 lines (top | session | usage | costs)

Toggle sections via environment variables (1=enabled, 0=disabled):
  CLAUDE_STATUSLINE_TIMESTAMP               — HH:MM invocation timestamp
  CLAUDE_STATUSLINE_SESSION_ID              — short session UUID
  CLAUDE_STATUSLINE_HOSTNAME                — green hostname
  CLAUDE_STATUSLINE_DIR                     — blue project directory
  CLAUDE_STATUSLINE_GIT                     — branch + indicators
  CLAUDE_STATUSLINE_DOGCAT                  — dcat issue tracker counts
  CLAUDE_STATUSLINE_CHANGES                 — cumulative lines added/removed (entire invocation)
  CLAUDE_STATUSLINE_SESSION                 — model, context window %, I/O ratio
    CLAUDE_STATUSLINE_COST                  — session cost
    CLAUDE_STATUSLINE_IO_RATIO              — output/input token ratio
    CLAUDE_STATUSLINE_CACHE_HIT             — cache hit rate %
  CLAUDE_STATUSLINE_SESSIONS                — active sessions in last 15 min
  CLAUDE_STATUSLINE_USAGE                   — Claude usage (session/week % with countdowns)
    CLAUDE_STATUSLINE_SONNET                — Sonnet usage %
    CLAUDE_STATUSLINE_SONNET_THRESHOLD      — hide Sonnet below this % (default 25)
    CLAUDE_STATUSLINE_EXTRA                 — Extra usage spent/limit
    CLAUDE_STATUSLINE_EXTRA_SESSION_THRESHOLD — show Extra when S% >= this (default 60)
    CLAUDE_STATUSLINE_TTL                   — time until next usage fetch
    CLAUDE_STATUSLINE_HISTORIC_COST         — entire historic cost line (6H/12H/24H/7D/30D/AT)
      CLAUDE_STATUSLINE_6H_COST            — rolling 6-hour cost (default 0)
      CLAUDE_STATUSLINE_12H_COST           — rolling 12-hour cost (default 0)
      CLAUDE_STATUSLINE_24H_COST           — rolling 24-hour cost
      CLAUDE_STATUSLINE_7D_COST            — rolling 7-day cost
      CLAUDE_STATUSLINE_30D_COST           — rolling 30-day cost
      CLAUDE_STATUSLINE_AT_COST            — all-time cost (when > 30D)
  CLAUDE_STATUSLINE_USAGE_JSON              — pre-provided usage JSON (skips get_claude_usage.py)
"""

from __future__ import annotations

import json
import math
import os
import re
import socket
import subprocess
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path

# pricing.py and cache_db.py live in the same directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cache_db import (
    check_fetch_backoff,
    read_cache_stats,
    read_usage_for_statusline,
    write_cache_stats,
)
from pricing import compute_costs, compute_project_rolling_costs, compute_session_cost

# --- Config ---

def _env(name: str, default: str = "1") -> str:
    return os.environ.get(f"CLAUDE_STATUSLINE_{name}", default)


def _on(name: str, default: bool = True) -> bool:
    return _env(name, "1" if default else "0") != "0"


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _get_terminal_cols() -> int:
    """Get terminal width. Tries $COLUMNS first, then /dev/tty ioctl."""
    cols_env = os.environ.get("COLUMNS", "")
    if cols_env:
        try:
            return int(cols_env)
        except ValueError:
            pass
    try:
        import fcntl
        import struct
        import termios

        with open("/dev/tty") as tty:
            packed = fcntl.ioctl(tty.fileno(), termios.TIOCGWINSZ, b"\x00" * 8)
            _, cols, _, _ = struct.unpack("HHHH", packed)
            if cols > 0:
                return cols
    except (OSError, ImportError):
        pass
    return 80


# --- ANSI helpers ---


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m"


# --- ISO timestamp helpers ---


def _parse_iso_epoch(iso: str) -> float | None:
    """Parse ISO 8601 timestamp to epoch seconds."""
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso).timestamp()
    except (ValueError, OSError):
        return None


# --- Git ---


def _start_git(cwd: str) -> dict[str, subprocess.Popen[bytes]]:
    """Start git commands as non-blocking subprocesses."""
    procs: dict[str, subprocess.Popen[bytes]] = {}
    if not _on("GIT"):
        return procs
    base = ["git", "-C", cwd, "--no-optional-locks"]
    kw: dict = {"stdout": subprocess.PIPE, "stderr": subprocess.DEVNULL}
    procs["status"] = subprocess.Popen([*base, "status", "--porcelain=v1", "-b"], **kw)
    procs["stash"] = subprocess.Popen([*base, "stash", "list"], **kw)
    procs["diffstat"] = subprocess.Popen([*base, "diff", "--shortstat", "HEAD", "--", ":(top,exclude).dogcats"], **kw)
    # rev-parse doesn't need --no-optional-locks
    procs["toplevel"] = subprocess.Popen(
        ["git", "-C", cwd, "rev-parse", "--show-toplevel"], **kw
    )
    return procs


def _collect_git(
    procs: dict[str, subprocess.Popen[bytes]],
) -> tuple[str, str, str, str, int, int]:
    """Collect git results → (status_out, stash_out, toplevel, branch, insertions, deletions)."""
    if not procs:
        return "", "", "", "", 0, 0
    status_out = (procs["status"].communicate()[0] or b"").decode()
    stash_out = (procs["stash"].communicate()[0] or b"").decode().strip()
    toplevel = (procs["toplevel"].communicate()[0] or b"").decode().strip()
    diffstat = (procs["diffstat"].communicate()[0] or b"").decode().strip()
    branch = ""
    if status_out:
        first = status_out.split("\n", 1)[0].removeprefix("## ")
        first = re.sub(r"^No commits yet on ", "", first)
        branch = first.split("...", 1)[0].split(" [", 1)[0]
    insertions = deletions = 0
    if diffstat:
        m = re.search(r"(\d+) insertion", diffstat)
        if m:
            insertions = int(m.group(1))
        m = re.search(r"(\d+) deletion", diffstat)
        if m:
            deletions = int(m.group(1))
    return status_out, stash_out, toplevel, branch, insertions, deletions


# --- Usage data ---


def _try_cache_bypass() -> dict | None:
    """Read usage data from SQLite cache if fresh."""
    return read_usage_for_statusline()


def _fetch_usage(session_id: str, cwd: str) -> dict:
    """Get usage data: env var → cache bypass → get_claude_usage.py subprocess."""
    pre = os.environ.get("CLAUDE_STATUSLINE_USAGE_JSON", "")
    if pre:
        try:
            return json.loads(pre)
        except json.JSONDecodeError:
            return {}
    cached = _try_cache_bypass()
    if cached is not None:
        return cached
    script = Path(__file__).resolve().parent / "get_claude_usage.py"
    if not script.exists():
        return {}
    try:
        r = subprocess.run(
            [sys.executable, str(script), "--session", session_id, "--cwd", cwd],
            capture_output=True,
            text=True,
            timeout=12,
        )
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return {}


# --- Dcat status ---


def _fetch_dcat(cwd: str) -> dict:
    """Get dcat issue counts using dogcat library (in-process)."""
    if not _on("DOGCAT") or not cwd:
        return {}
    try:
        from dogcat.cli._helpers import get_storage

        storage = get_storage(f"{cwd}/.dogcats")
        by_status: dict[str, int] = {}
        for issue in storage.list():
            s = issue.status.value
            by_status[s] = by_status.get(s, 0) + 1
        return {"by_status": by_status}
    except Exception:  # noqa: BLE001
        return {}


# --- Cache stats accumulation ---


def _accumulate_cache_stats(
    session_id: str,
    cache_read: int,
    cache_create: int,
    input_fresh: int,
    total_in_tokens: int,
) -> tuple[int, int, int]:
    """Accumulate per-message cache stats. Returns (cum_fresh, cum_create, cum_read)."""
    if not session_id:
        return 0, 0, 0
    cached = read_cache_stats(session_id)
    if cached is not None:
        pt, pf, pc, pr = cached
        if total_in_tokens != pt:
            cf, cc, cr = pf + input_fresh, pc + cache_create, pr + cache_read
        else:
            return pf, pc, pr
    else:
        cf, cc, cr = input_fresh, cache_create, cache_read
    write_cache_stats(session_id, total_in_tokens, cf, cc, cr)
    return cf, cc, cr


# --- Section renderers ---


def _render_timestamp() -> str:
    if not _on("TIMESTAMP"):
        return ""
    epoch_env = os.environ.get("CLAUDE_STATUSLINE_TIMESTAMP_EPOCH", "")
    if epoch_env:
        try:
            ts = datetime.fromtimestamp(int(epoch_env)).strftime("%H:%M")  # noqa: DTZ006
        except (ValueError, OSError):
            ts = datetime.now().strftime("%H:%M")  # noqa: DTZ005
    else:
        ts = datetime.now().strftime("%H:%M")  # noqa: DTZ005
    return _c("0;90", ts)


def _render_session_id(session_id: str) -> str:
    if not _on("SESSION_ID") or not session_id:
        return ""
    return _c("0;90", session_id.rsplit("-", 1)[-1])


def _render_hostname() -> str:
    if not _on("HOSTNAME", default=False):
        return ""
    return _c("0;32", socket.gethostname().split(".")[0])


def _render_dir(cwd: str, toplevel: str) -> str:
    if not _on("DIR"):
        return ""
    if toplevel:
        repo = os.path.basename(toplevel)
        rel = cwd.removeprefix(toplevel)
        return _c("0;34", f"{repo}{rel}")
    return _c("0;34", os.path.basename(cwd))


def _render_git(
    git_status: str, stash_out: str, branch: str, insertions: int, deletions: int,
) -> str:
    if not _on("GIT") or not branch:
        return ""
    lines = git_status.strip().split("\n")
    branch_line = lines[0] if lines else ""
    files = lines[1:] if len(lines) > 1 else []

    ind = ""
    # Merge conflicts (UU, AA, DD, AU, UA, DU, UD)
    if any(
        len(f) >= 2 and ("U" in f[:2] or f[:2] in ("DD", "AA")) for f in files
    ):
        ind += _c("0;31", "=")
    # Ahead / behind
    ahead = behind = 0
    if "[" in branch_line:
        m = re.search(r"ahead (\d+)", branch_line)
        if m:
            ahead = int(m.group(1))
        m = re.search(r"behind (\d+)", branch_line)
        if m:
            behind = int(m.group(1))
    if ahead and behind:
        ind += _c("0;33", f"⇕⇡{ahead}⇣{behind}")
    elif ahead:
        ind += _c("0;32", f"⇡{ahead}")
    elif behind:
        ind += _c("0;31", f"⇣{behind}")
    if stash_out:
        ind += _c("0;35", "$")
    if any(f and f[0] in "MARCD" for f in files):
        ind += _c("0;32", "+")
    if any(f and f[0] == "R" for f in files):
        ind += _c("0;33", "»")
    if any(f and f[0] == "D" for f in files):
        ind += _c("0;31", "✘")
    if any(f and len(f) >= 2 and f[1] in "MD" for f in files):
        ind += _c("0;31", "!")
    if any(f.startswith("??") for f in files):
        ind += _c("0;37", "?")
    if insertions or deletions:
        ind += f'{_c("0;32", f"+{insertions}")}{_c("0;31", f"-{deletions}")}'
    if ind:
        return f"{_c('0;33', branch)}[{ind}]"
    return _c("0;33", branch)


def _render_dogcat(dcat_data: dict) -> str:
    if not dcat_data:
        return ""
    by = dcat_data.get("by_status", {})
    ip = by.get("in_progress", 0)
    ir = by.get("in_review", 0)
    if not ip and not ir:
        return ""
    parts = ""
    if ip:
        parts += _c("0;33", f"◐ {ip}")
    if ir:
        parts += _c("0;36", f"?{ir}")
    return f"dc[{parts}]"


def _render_ctx_pct(used: str) -> str:
    if not used:
        return ""
    used_int = math.ceil(float(used))
    col = "31" if used_int >= 70 else "33" if used_int >= 50 else "32"
    return f"\033[0;90mctx:\033[0;{col}m{used_int}%\033[0m"


def _render_changes(lines_added: int, lines_removed: int) -> str:
    if not _on("CHANGES"):
        return ""
    if not lines_added and not lines_removed:
        return ""
    return f'[{_c("0;32", f"+{lines_added}")} {_c("0;31", f"-{lines_removed}")}]'


def _usage_color(pct: int) -> str:
    if pct >= 85:
        return "31"
    if pct >= 65:
        return "33"
    return "90"


def _usage_countdown(reset_iso: str, now_epoch: float) -> str:
    epoch = _parse_iso_epoch(reset_iso)
    if epoch is None or epoch <= now_epoch:
        return ""
    d = int(epoch - now_epoch)
    if d >= 86400:
        return f"{d // 86400}d{(d % 86400) // 3600}h"
    if d >= 3600:
        return f"{d // 3600}h{(d % 3600) // 60}m"
    return f"{d // 60}m"


def _usage_section(label: str, pct_s: str, reset_iso: str, now: float) -> str:
    if not pct_s:
        return ""
    try:
        pct = int(pct_s)
    except ValueError:
        return ""
    col = _usage_color(pct)
    cd = _usage_countdown(reset_iso, now)
    if cd:
        return f"\033[0;90m{label}:\033[0;{col}m{pct}%\033[0;90m({cd})\033[0m"
    return f"\033[0;90m{label}:\033[0;{col}m{pct}%\033[0m"


def _usage_combined(
    label: str, pct_s: str, reset_iso: str, cost_s: str, now: float,
) -> str:
    """Render compact usage: S:17% $7 3h3m"""
    if not pct_s:
        return ""
    try:
        pct = int(pct_s)
    except ValueError:
        return ""
    col = _usage_color(pct)
    parts = [f"\033[0;90m{label}:\033[0;{col}m{pct}%\033[0m"]
    if cost_s and cost_s not in ("0", "0.0", "0.0000", ""):
        try:
            rounded = math.ceil(float(cost_s))
            if rounded > 0:
                parts.append(f"\033[0;90m${rounded}\033[0m")
        except ValueError:
            pass
    cd = _usage_countdown(reset_iso, now)
    if cd:
        parts.append(f"\033[0;90m{cd}\033[0m")
    return " ".join(parts)


def _usage_cost(label: str, val: str, project_val: str = "") -> str:
    if not val or val in ("0", "0.0", "0.0000", ""):
        return ""
    try:
        v = float(val)
    except ValueError:
        return ""
    rounded = math.ceil(v)
    if rounded == 0:
        return ""
    # Show $project/$total when project cost differs from total
    if project_val and project_val not in ("0", "0.0", "0.0000", ""):
        try:
            p_rounded = math.ceil(float(project_val))
            if 0 < p_rounded < rounded:
                return f"\033[0;90m{label}:${p_rounded}/${rounded}\033[0m"
        except ValueError:
            pass
    return f"\033[0;90m{label}:${rounded}\033[0m"


def _fmt_money(v: str) -> str:
    f = f"{float(v):.2f}"
    f = re.sub(r"\.00$", "", f)
    return re.sub(r"(\.[^0])0$", r"\1", f)


def _render_sessions(cwd: str, now: float) -> str:
    """Active sessions: distinct projects from history in last 15 min."""
    if not _on("SESSIONS"):
        return ""
    history = Path.home() / ".claude" / "history.jsonl"
    if not history.exists():
        return ""
    try:
        cutoff_ms = int(now * 1000) - 900_000
        projects: set[str] = set()
        with open(history) as f:
            for line in deque(f, maxlen=100):
                try:
                    entry = json.loads(line)
                    if entry.get("timestamp", 0) >= cutoff_ms:
                        proj = entry.get("project", "")
                        if proj and proj != cwd:
                            projects.add(proj)
                except json.JSONDecodeError:
                    continue
        count = len(projects)
        if count > 0:
            col = "31" if count >= 4 else "33" if count >= 2 else "90"
            return f"\033[0;90m+\033[0;{col}m{count}\033[0;90msess\033[0m"
    except OSError:
        pass
    return ""


def _render_usage(usage: dict, now: float) -> tuple[str, str, str]:
    """Render usage data as session line, rate-limit sections, and cost line.

    Returns (session_rl, rest_rl_line, cost_line). Any may be empty.
    """
    if not _on("USAGE") or not usage:
        return "", "", ""
    s_pct_raw = usage.get("session_percent", "")
    w_pct_raw = usage.get("week_percent", "")
    s_pct = str(s_pct_raw) if s_pct_raw is not None and s_pct_raw != "" else ""
    w_pct = str(w_pct_raw) if w_pct_raw is not None and w_pct_raw != "" else ""
    have_rate_limits = s_pct or w_pct

    def _bracket(inner: str) -> str:
        return f"\033[0;34m[\033[0m{inner}\033[0;34m]\033[0m"

    # --- Rate-limit sections: S/W/So in one bracket ---
    rl_inners: list[str] = []
    rl_line = ""

    if have_rate_limits:
        s = _usage_combined(
            "S", s_pct, usage.get("session_reset", ""),
            str(usage.get("session_window_cost", "") or ""), now,
        )
        if s:
            rl_inners.append(s)

        s = _usage_combined(
            "W", w_pct, usage.get("week_reset", ""),
            str(usage.get("week_cost", "") or ""), now,
        )
        if s:
            rl_inners.append(s)

        # Sonnet (hidden below threshold)
        so_pct_raw = usage.get("sonnet_percent", "")
        so_pct = str(so_pct_raw) if so_pct_raw is not None and so_pct_raw != "" else ""
        if _on("SONNET") and so_pct:
            try:
                if int(so_pct) >= _env_int("SONNET_THRESHOLD", 25):
                    s = _usage_combined("So", so_pct, usage.get("sonnet_reset", ""), "", now)
                    if s:
                        rl_inners.append(s)
            except ValueError:
                pass

        # Prepend TTL (or staleness age) inside the S/W bracket
        if _on("TTL"):
            upd_epoch = _parse_iso_epoch(str(usage.get("last_updated", "") or ""))
            if upd_epoch is not None:
                ttl_s = int(600 - (now - upd_epoch))
                if ttl_s > 0:
                    rl_inners.insert(0, f"\033[0;90mTTL:{ttl_s // 60}m{ttl_s % 60}s\033[0m")
                else:
                    age_s = int(now - upd_epoch)
                    if age_s >= 3600:
                        # Data is too old — suppress rate-limit display,
                        # but continue to render historic cost line below
                        rl_inners.clear()
                        have_rate_limits = False
                    else:
                        age_fmt = f"{age_s // 60}m"
                        rl_inners.insert(0, f"\033[0;31mstale:{age_fmt}\033[0m")

        # Extra usage (only when session % >= threshold) — separate line
        extra_sections: list[str] = []
        if _on("EXTRA") and s_pct:
            try:
                if int(s_pct) >= _env_int("EXTRA_SESSION_THRESHOLD", 60):
                    es = str(usage.get("extra_spent", "") or "")
                    el = str(usage.get("extra_limit", "") or "")
                    if es and el:
                        extra = f"\033[0;90mE:${_fmt_money(es)}/${_fmt_money(el)}\033[0m"
                        extra_sections.append(_bracket(extra))
            except ValueError:
                pass

        rl_line = " ".join(extra_sections) if extra_sections else ""

    session_rl = _bracket(" ".join(rl_inners)) if rl_inners else ""

    # --- Cost line: 6H/12H/24H/7D/30D ---
    cost_parts: list[str] = []
    if not _on("HISTORIC_COST"):
        return session_rl, rl_line, ""

    if _on("6H_COST", default=False):
        s = _usage_cost("6H", str(usage.get("six_hour_cost", "") or ""),
                        str(usage.get("six_hour_project_cost", "") or ""))
        if s:
            cost_parts.append(s)

    if _on("12H_COST", default=False):
        s = _usage_cost("12H", str(usage.get("twelve_hour_cost", "") or ""),
                        str(usage.get("twelve_hour_project_cost", "") or ""))
        if s:
            cost_parts.append(s)

    if _on("24H_COST"):
        s = _usage_cost("24H", str(usage.get("twenty_four_hour_cost", "") or ""),
                        str(usage.get("twenty_four_hour_project_cost", "") or ""))
        if s:
            cost_parts.append(s)

    if _on("7D_COST"):
        s = _usage_cost("7D", str(usage.get("seven_day_cost", "") or ""),
                        str(usage.get("seven_day_project_cost", "") or ""))
        if s:
            cost_parts.append(s)

    if _on("30D_COST"):
        s = _usage_cost("30D", str(usage.get("thirty_day_cost", "") or ""),
                        str(usage.get("thirty_day_project_cost", "") or ""))
        if s:
            cost_parts.append(s)

    # All-time cost (shown only when there's cost beyond 30 days)
    if _on("AT_COST"):
        at_val = str(usage.get("all_time_cost", "") or "")
        td_val = str(usage.get("thirty_day_cost", "") or "")
        if at_val and td_val:
            try:
                if float(at_val) - float(td_val) >= 0.005:
                    s = _usage_cost("AT", at_val,
                                    str(usage.get("all_time_project_cost", "") or ""))
                    if s:
                        cost_parts.append(s)
            except ValueError:
                pass

    cost_line = ""
    if cost_parts:
        cost_line = f"\033[0;34m[\033[0m{' '.join(cost_parts)}\033[0;34m]\033[0m"

    return session_rl, rl_line, cost_line


def _render_session(
    model: str,
    used: str,
    ctx_size: int,
    total_in: int,
    total_out: int,
    cum_fresh: int,
    cum_create: int,
    cum_read: int,
    session_cost: str,
) -> str:
    if not _on("SESSION"):
        return ""
    parts: list[str] = []

    if model:
        col = "0;90" if "Opus" in model else "0;36"
        parts.append(_c(col, model))

    # Per-session cost
    if _on("COST") and session_cost:
        try:
            fmt = f"{float(session_cost):.2f}"
            if fmt != "0.00":
                parts.append(f"\033[0;90m${fmt}\033[0m")
        except ValueError:
            pass

    # I/O ratio
    if _on("IO_RATIO") and total_in > 0 and total_out > 0:
        ratio = (total_out * 10 + total_in // 2) // total_in
        w, f = divmod(ratio, 10)
        parts.append(f"\033[0;90mI/O:{w}.{f}x\033[0m")

    # Cumulative cache hit rate
    if _on("CACHE_HIT"):
        ti = cum_fresh + cum_create + cum_read
        if ti > 0:
            ch = cum_read * 100 // ti
            parts.append(f"\033[0;90mCH:{ch}%\033[0m")

    # Context window token counts (percentage moved to top line)
    if used and ctx_size > 0:
        used_int = math.ceil(float(used))
        used_k = (ctx_size * used_int + 99999) // 100000
        total_k = (ctx_size + 999) // 1000
        parts.append(f"\033[0;90m{used_k}k/{total_k}k\033[0m")

    if not parts:
        return ""
    inner = " ".join(parts)
    return f"\033[0;34m[\033[0m{inner}\033[0;34m]\033[0m"


# --- Main ---


def main() -> None:
    test_mode = "-t" in sys.argv

    if test_mode:
        cwd = os.getcwd()
        data = {
            "session_id": "mock-session-id",
            "workspace": {"current_dir": cwd},
            "model": {"display_name": "Opus 4.6"},
            "context_window": {
                "used_percentage": 42.7,
                "context_window_size": 200000,
                "total_input_tokens": 16378,
                "total_output_tokens": 15177,
                "current_usage": {
                    "input_tokens": 3,
                    "cache_creation_input_tokens": 658,
                    "cache_read_input_tokens": 60106,
                },
            },
            "cost": {
                "total_cost_usd": 1.37,
                "total_lines_added": 128,
                "total_lines_removed": 34,
            },
        }
    else:
        raw = sys.stdin.read()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

    # Extract fields
    cwd = data.get("workspace", {}).get("current_dir") or data.get("cwd", "")
    model = data.get("model", {}).get("display_name", "")
    used_raw = data.get("context_window", {}).get("used_percentage", "")
    used = str(used_raw) if used_raw is not None and used_raw != "" else ""
    ctx_size = int(data.get("context_window", {}).get("context_window_size", 0) or 0)
    cost_obj = data.get("cost", {})
    lines_added = int(cost_obj.get("total_lines_added", 0) or 0)
    lines_removed = int(cost_obj.get("total_lines_removed", 0) or 0)
    cur = data.get("context_window", {}).get("current_usage", {})
    cache_create = int(cur.get("cache_creation_input_tokens", 0) or 0)
    cache_read = int(cur.get("cache_read_input_tokens", 0) or 0)
    input_fresh = int(cur.get("input_tokens", 0) or 0)
    total_in = int(data.get("context_window", {}).get("total_input_tokens", 0) or 0)
    total_out = int(data.get("context_window", {}).get("total_output_tokens", 0) or 0)
    session_id = data.get("session_id", "")

    now_epoch = time.time()

    # Start git commands (non-blocking) — runs while we do in-process work
    git_procs = _start_git(cwd)
    try:
        # In-process: usage cache + dcat library (no subprocess)
        usage_data = _fetch_usage(session_id, cwd)
        # When usage fetch failed, compute costs independently from JSONL files
        if not usage_data and _on("HISTORIC_COST"):
            try:
                usage_data = compute_costs(session_id=session_id, cwd=cwd)
            except Exception:  # noqa: BLE001
                pass
        # Always compute project costs from cwd (independent of shared cache)
        if cwd and _on("HISTORIC_COST") and usage_data:
            usage_data.update(compute_project_rolling_costs(cwd))
        dcat_data = _fetch_dcat(cwd)

        # Collect git results
        git_status, stash_out, toplevel, branch, git_ins, git_del = _collect_git(git_procs)
    finally:
        for p in git_procs.values():
            try:
                p.kill()
            except OSError:
                pass

    # Cache stats
    cum_fresh, cum_create, cum_read = _accumulate_cache_stats(
        session_id, cache_read, cache_create, input_fresh, total_in
    )

    # Render all sections
    top = [
        _render_timestamp(),
        _render_session_id(session_id),
        _render_hostname(),
        _render_dir(cwd, toplevel),
        _render_git(git_status, stash_out, branch, git_ins, git_del),
        _render_dogcat(dcat_data),
        _render_changes(lines_added, lines_removed),
        _render_ctx_pct(used),
    ]
    # Per-chat cost: compute directly from session JSONL file (scoped to session ID).
    chat_cost_val = compute_session_cost(session_id, cwd)
    chat_cost = str(chat_cost_val) if chat_cost_val > 0 else ""
    session = _render_session(
        model,
        used,
        ctx_size,
        total_in,
        total_out,
        cum_fresh,
        cum_create,
        cum_read,
        chat_cost,
    )
    sessions = _render_sessions(cwd, now_epoch)
    usage_session_rl, usage_rl, usage_cost = _render_usage(usage_data, now_epoch)

    # Show failure indicator when usage is empty and fetch is in error backoff
    # Show error when usage is empty and fetch is in backoff, or data is > 1 hour stale
    usage_stale_1h = False
    if usage_data:
        upd = _parse_iso_epoch(str(usage_data.get("last_updated", "") or ""))
        if upd is not None and (now_epoch - upd) >= 3600:
            usage_stale_1h = True
    if usage_stale_1h or (not usage_session_rl and not usage_rl and not usage_cost and check_fetch_backoff()):
        usage_session_rl = (
            f"\033[0;34m[\033[0m\033[0;31musage fetch failed\033[0m\033[0;34m]\033[0m"
        )

    top = [s for s in top if s]
    top_str = " ".join(top)
    session_parts = [s for s in [session, sessions] if s]
    session_str = " ".join(session_parts) if session_parts else ""
    usage_parts = [s for s in [usage_session_rl, usage_rl, usage_cost] if s]
    usage_str = " ".join(usage_parts) if usage_parts else ""

    # Adaptive layout based on terminal width
    term_cols = _get_terminal_cols()
    if term_cols >= 130:
        # Wide: 2 lines — top+session | usage+costs
        line1_parts = [s for s in [top_str, session_str] if s]
        line2_parts = [s for s in [usage_str] if s]
        lines = [" ".join(line1_parts)]
        if line2_parts:
            lines.append(" ".join(line2_parts))
    else:
        # Narrow: 4 lines — top | session | rate-limits | costs
        lines = [top_str]
        if session_str:
            lines.append(session_str)
        if usage_session_rl:
            lines.append(usage_session_rl)
        rest = [s for s in [usage_rl, usage_cost] if s]
        if rest:
            lines.append(" ".join(rest))

    print("\n".join(lines))


if __name__ == "__main__":
    main()
