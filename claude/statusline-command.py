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
  CLAUDE_STATUSLINE_SANDBOX                 — sbx/!sbx badge from merged Claude settings
  CLAUDE_STATUSLINE_GIT                     — branch + indicators
  CLAUDE_STATUSLINE_DOGCAT                  — dcat issue tracker counts
  CLAUDE_STATUSLINE_CHANGES                 — cumulative lines added/removed (entire invocation)
  CLAUDE_STATUSLINE_SESSION                 — model, context window %, I/O ratio
    CLAUDE_STATUSLINE_COST                  — session cost
    CLAUDE_STATUSLINE_IO_RATIO              — output/input token ratio
    CLAUDE_STATUSLINE_CACHE_HIT             — cache hit rate %
  CLAUDE_STATUSLINE_USABLE_CTX               — base ctx% on 80% usable window (auto-compact threshold)
  CLAUDE_STATUSLINE_APPLE_SILICON            — macmon temps/power (requires macmon)
  CLAUDE_STATUSLINE_PEAK                    — peak/off-peak indicator with countdown
  CLAUDE_STATUSLINE_SESSIONS                — active sessions in last 15 min
  CLAUDE_STATUSLINE_USAGE                   — Claude usage (session/week % with countdowns)
    CLAUDE_STATUSLINE_WEEKLY_PACE            — weekly pace indicator (D3/7: On Pace)
    CLAUDE_STATUSLINE_SONNET                — Sonnet usage %
    CLAUDE_STATUSLINE_SONNET_THRESHOLD      — hide Sonnet below this % (default 25)
    CLAUDE_STATUSLINE_EXTRA                 — Extra usage spent/limit + per-window deltas (S/W)
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

Other environment variables:
  CLAUDE_CODE_PACE_DAYS                     — pace window in days (1-7, default 7)
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
from typing import NamedTuple

# pricing.py and cache_db.py live in the same directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cache_db import (
    check_fetch_backoff,
    compute_extra_window_deltas,
    read_cache_stats,
    read_usage_for_statusline,
    read_usage_stale,
    write_cache_stats,
)
from pricing import compute_costs, compute_project_rolling_costs, compute_session_cost

# --- Config ---

# Thresholds and layout constants
TEMP_WARN_C = 75           # °C — yellow warning for CPU/GPU temp
TEMP_CRIT_C = 90           # °C — red alert for CPU/GPU temp
STALE_THRESHOLD_S = 3600   # seconds before usage data is considered too old
LAYOUT_WIDE_COLS = 130     # terminal columns threshold for 2-line layout
SESSION_WINDOW_MS = 900_000  # 15 min — active sessions lookback
PEAK_WARN_MIN = 30         # minutes before peak: show yellow warning
PEAK_SHOW_COUNTDOWN_MIN = 300  # minutes before peak: show green countdown

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

# Two-tier dimming: structural/stable info uses SUBDUED (very dim),
# dynamic/changing info uses the standard dim grey (0;90).
SUBDUED = "\033[38;5;242m"  # 256-color dark grey — structural info
RST = "\033[0m"


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
    try:
        procs["status"] = subprocess.Popen([*base, "status", "--porcelain=v1", "-b"], **kw)
        procs["stash"] = subprocess.Popen([*base, "stash", "list"], **kw)
        procs["diffstat"] = subprocess.Popen([*base, "diff", "--shortstat", "HEAD", "--", ":(top,exclude).dogcats"], **kw)
        # rev-parse doesn't need --no-optional-locks
        procs["toplevel"] = subprocess.Popen(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"], **kw
        )
    except FileNotFoundError:
        return {}
    return procs


class GitInfo(NamedTuple):
    status_out: str
    stash_out: str
    toplevel: str
    branch: str
    insertions: int
    deletions: int


_EMPTY_GIT = GitInfo("", "", "", "", 0, 0)


def _collect_git(
    procs: dict[str, subprocess.Popen[bytes]],
) -> GitInfo:
    """Collect git results into a GitInfo NamedTuple."""
    if not procs:
        return _EMPTY_GIT
    GIT_TIMEOUT = 5

    def _read(name: str) -> str:
        try:
            return (procs[name].communicate(timeout=GIT_TIMEOUT)[0] or b"").decode()
        except subprocess.TimeoutExpired:
            procs[name].kill()
            return ""

    status_out = _read("status")
    stash_out = _read("stash").strip()
    toplevel = _read("toplevel").strip()
    diffstat = _read("diffstat").strip()
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
    return GitInfo(status_out, stash_out, toplevel, branch, insertions, deletions)


# --- Apple Silicon stats (macmon) ---


def _start_macmon() -> subprocess.Popen[bytes] | None:
    """Start macmon pipe as a non-blocking subprocess."""
    if not _on("APPLE_SILICON"):
        return None
    try:
        return subprocess.Popen(
            ["macmon", "pipe", "-s", "1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return None


def _collect_macmon(proc: subprocess.Popen[bytes] | None) -> dict:
    """Collect macmon JSON output."""
    if proc is None:
        return {}
    try:
        out, _ = proc.communicate(timeout=5)
        if out:
            return json.loads(out.strip())
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        proc.kill()
    return {}


def _render_macmon(data: dict) -> str:
    """Render Apple Silicon temps and power: CPU:53°C/0.8W GPU:49°C/0.1W ANE:0W"""
    if not data:
        return ""
    temp = data.get("temp", {})
    cpu_t = temp.get("cpu_temp_avg")
    gpu_t = temp.get("gpu_temp_avg")
    cpu_w = data.get("cpu_power")
    gpu_w = data.get("gpu_power")
    ane_w = data.get("ane_power")

    parts: list[str] = []

    if cpu_t is not None:
        t = int(cpu_t)
        # Alert colors only for hot temps; otherwise subdued
        if t >= TEMP_CRIT_C:
            val_col = "\033[0;31m"
        elif t >= TEMP_WARN_C:
            val_col = "\033[0;33m"
        else:
            val_col = SUBDUED
        w_str = f"/{cpu_w:.1f}W" if cpu_w is not None else ""
        parts.append(f"{SUBDUED}CPU:{val_col}{t}°C{w_str}{RST}")

    mem = data.get("memory", {})
    ram_usage = mem.get("ram_usage")
    ram_total = mem.get("ram_total")
    if ram_usage is not None and ram_total is not None:
        used_gb = ram_usage / (1024 ** 3)
        total_gb = ram_total / (1024 ** 3)
        parts.append(f"{SUBDUED}RAM:{used_gb:.0f}GB/{total_gb:.0f}GB{RST}")

    if gpu_t is not None:
        t = int(gpu_t)
        if t >= TEMP_CRIT_C:
            val_col = "\033[0;31m"
        elif t >= TEMP_WARN_C:
            val_col = "\033[0;33m"
        else:
            val_col = SUBDUED
        w_str = f"/{gpu_w:.1f}W" if gpu_w is not None else ""
        parts.append(f"{SUBDUED}GPU:{val_col}{t}°C{w_str}{RST}")

    if ane_w is not None and ane_w > 0.05:
        parts.append(f"{SUBDUED}ANE:{ane_w:.1f}W{RST}")

    if not parts:
        return ""
    return " ".join(parts)


# --- Usage data ---


def _try_cache_bypass() -> dict | None:
    """Read usage data from SQLite cache if fresh."""
    return read_usage_for_statusline()


def _fetch_usage(session_id: str, cwd: str) -> dict:
    """Get usage data: env var → cache bypass → detached get_claude_usage.py.

    The fetch subprocess is detached (start_new_session=True) so it survives
    the parent being killed by the statusline framework (e.g. tmux interval).
    Stale cached data is returned for this render; fresh data appears next call.
    """
    pre = os.environ.get("CLAUDE_STATUSLINE_USAGE_JSON", "")
    if pre:
        try:
            return json.loads(pre)
        except json.JSONDecodeError:
            return {}
    cached = _try_cache_bypass()
    if cached is not None:
        return cached
    # Cache is stale — spawn detached fetch (survives parent kill)
    script = Path(__file__).resolve().parent / "get_claude_usage.py"
    if script.exists():
        try:
            subprocess.Popen(
                [sys.executable, str(script), "--wait-timeout", "4", "--session", session_id, "--cwd", cwd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            pass
    # Return stale data for this render; fresh data will be in cache next call
    return read_usage_stale() or {}


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
    return f"{SUBDUED}{ts}{RST}"


def _render_session_id(session_id: str) -> str:
    if not _on("SESSION_ID") or not session_id:
        return ""
    return f"{SUBDUED}{session_id.rsplit('-', 1)[-1]}{RST}"


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


def _render_sandbox(cwd: str, toplevel: str) -> str:
    """Show sbx/!sbx from merged Claude settings.

    Walks local → project → user settings; first file with sandbox.enabled wins.
    Empty when unset everywhere (same state clax shows as "(unset)").
    """
    if not _on("SANDBOX"):
        return ""
    files: list[Path] = []
    root = Path(toplevel) if toplevel else (Path(cwd) if cwd else None)
    if root:
        files.append(root / ".claude" / "settings.local.json")
        files.append(root / ".claude" / "settings.json")
    files.append(Path.home() / ".claude" / "settings.json")
    for path in files:
        try:
            with open(path) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        sb = data.get("sandbox")
        if isinstance(sb, dict) and "enabled" in sb:
            return _c("0;32", "sbx") if sb["enabled"] else f"{SUBDUED}!sbx{RST}"
    return ""


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


AUTOCOMPACT_BUFFER = 33_000  # tokens reserved by Claude Code before auto-compact


def _render_ctx_pct(used: str, ctx_size: int) -> str:
    if not used:
        return ""
    used_f = float(used)
    # Usable context: auto-compact reserves ~33k tokens, scale to usable range
    if _on("USABLE_CTX") and ctx_size > AUTOCOMPACT_BUFFER:
        usable_ratio = (ctx_size - AUTOCOMPACT_BUFFER) / ctx_size
        used_f = min(100.0, used_f / usable_ratio)
    used_int = math.ceil(used_f)
    col = "31" if used_int >= 70 else "33" if used_int >= 50 else "32"
    return f"\033[0;90mctx:\033[0;{col}m{used_int}%\033[0m"


def _render_changes(lines_added: int, lines_removed: int) -> str:
    if not _on("CHANGES"):
        return ""
    if not lines_added and not lines_removed:
        return ""
    return f'{_c("0;32", f"+{lines_added}")} {_c("0;31", f"-{lines_removed}")}'


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



def _pace_days() -> int:
    """Return the pace window in days from CLAUDE_CODE_PACE_DAYS env var (default 7)."""
    try:
        d = int(os.environ.get("CLAUDE_CODE_PACE_DAYS", "7"))
        return d if 1 <= d <= 7 else 7
    except ValueError:
        return 7


def _weekly_pace(w_pct_s: str, reset_iso: str, now: float) -> str:
    """Weekly pace indicator: compare actual usage % to expected % based on elapsed time.

    Expected = how far through the PACE_DAYS window we are (time-based, not day-based).
    Display: "{el_d}d{el_h}h/{N}d {sign}{delta}%"
    """
    if not _on("WEEKLY_PACE"):
        return ""
    if not w_pct_s:
        return ""
    reset_epoch = _parse_iso_epoch(reset_iso)
    if reset_epoch is None:
        return ""
    try:
        actual = int(w_pct_s)
    except ValueError:
        return ""
    pace = _pace_days()
    week_start = reset_epoch - 7 * 86400
    elapsed_s = now - week_start
    elapsed_frac = elapsed_s / (7 * 86400)
    if elapsed_frac <= 0 or elapsed_frac > 1:
        return ""
    # Expected usage: consume 100% in pace_days, not 7 (cap at 100)
    expected = min((elapsed_s / (pace * 86400)) * 100, 100)
    delta = actual - expected
    # Compact elapsed time: "3d14h" or "0d5h" or "6d"
    el_d = int(elapsed_s // 86400)
    el_h = int((elapsed_s % 86400) // 3600)
    if el_h > 0:
        elapsed_str = f"{el_d}d{el_h}h"
    else:
        elapsed_str = f"{el_d}d"
    # Remaining time until reset
    remain_s = int(reset_epoch - now)
    if remain_s > 0:
        cd = _usage_countdown(reset_iso, now)
        time_part = f"{elapsed_str}/7d({cd})"
    else:
        time_part = f"{elapsed_str}/7d"
    d_round = round(delta)
    sign = "+" if d_round >= 0 else ""
    return f"\033[0;90m{time_part} {sign}{d_round}%\033[0m"


def _usage_combined(
    label: str, pct_s: str, reset_iso: str, cost_s: str, now: float,
    *, pace: str = "",
) -> str:
    """Render compact usage: W:26% $293 1d6h/7d 5d17h"""
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
    if pace:
        parts.append(pace)
    else:
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
    DIM = "\033[0;90m"
    # Show label $project/$total when project cost differs from total
    if project_val and project_val not in ("0", "0.0", "0.0000", ""):
        try:
            p_rounded = math.ceil(float(project_val))
            if 0 < p_rounded < rounded:
                return f"{SUBDUED}{label} {DIM}${p_rounded}/${rounded}{RST}"
        except ValueError:
            pass
    return f"{SUBDUED}{label} {DIM}${rounded}{RST}"



def _fmt_money(v: str) -> str:
    f = f"{float(v):.2f}"
    f = re.sub(r"\.00$", "", f)
    return re.sub(r"(\.[^0])0$", r"\1", f)


def _render_peak(_now_epoch: float) -> str:
    """Peak/off-peak indicator with countdown to next flip."""
    if not _on("PEAK"):
        return ""
    from get_claude_usage import compute_peak_info

    info = compute_peak_info()
    peak = info["peak_is_peak"]
    mins = info["peak_flip_seconds"] // 60
    hrs, m = divmod(mins, 60)
    countdown = f"{hrs}h{m:02d}m" if hrs else f"{m}m"

    if peak:
        return f"\033[0;31mPeak\033[0;90m({countdown})\033[0m"
    if mins < PEAK_WARN_MIN:
        return f"\033[0;33mOffPk\033[0;90m({countdown})\033[0m"
    if mins < PEAK_SHOW_COUNTDOWN_MIN:
        return f"\033[0;32mOffPk\033[0;90m({countdown})\033[0m"
    return f"\033[0;32mOffPk\033[0m"


def _render_sessions(cwd: str, now: float) -> str:
    """Active sessions: distinct projects from history in last 15 min."""
    if not _on("SESSIONS"):
        return ""
    history = Path.home() / ".claude" / "history.jsonl"
    if not history.exists():
        return ""
    try:
        cutoff_ms = int(now * 1000) - SESSION_WINDOW_MS
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
            col = "31" if count >= 4 else "33" if count >= 2 else ""
            if col:
                return f"{SUBDUED}+\033[0;{col}m{count}{SUBDUED}sess{RST}"
            return f"{SUBDUED}+{count}sess{RST}"
    except OSError:
        pass
    return ""


def _extra_deltas(current_spent: float, usage: dict, now: float) -> dict[str, float | None]:
    """Compute extra usage deltas for session window (5h) and week (7d)."""
    from datetime import timedelta

    session_start_epoch: float | None = None
    sr_iso = usage.get("session_reset", "")
    if sr_iso:
        sr_epoch = _parse_iso_epoch(str(sr_iso))
        if sr_epoch is not None:
            if sr_epoch <= now:
                session_start_epoch = sr_epoch
            else:
                session_start_epoch = sr_epoch - 5 * 3600

    week_start_epoch: float | None = None
    wr_iso = usage.get("week_reset", "")
    if wr_iso:
        wr_epoch = _parse_iso_epoch(str(wr_iso))
        if wr_epoch is not None:
            if wr_epoch <= now:
                week_start_epoch = wr_epoch
            else:
                week_start_epoch = wr_epoch - 7 * 86400

    return compute_extra_window_deltas(
        current_spent, session_start_epoch, week_start_epoch,
    )


def _ustr(d: dict, key: str) -> str:
    """Safely extract a string value from a usage dict."""
    return str(d.get(key, "") or "")


def _render_rate_limits(usage: dict, now: float) -> tuple[list[str], bool]:
    """Build rate-limit inner sections (S/W/So + TTL).

    Returns (rl_inners, have_rate_limits). *have_rate_limits* may be set to
    False if data is too stale, even when it was True on entry.
    """
    s_pct_raw = usage.get("session_percent", "")
    w_pct_raw = usage.get("week_percent", "")
    s_pct = str(s_pct_raw) if s_pct_raw is not None and s_pct_raw != "" else ""
    w_pct = str(w_pct_raw) if w_pct_raw is not None and w_pct_raw != "" else ""
    if not (s_pct or w_pct):
        return [], False

    rl_inners: list[str] = []

    session_line = _usage_combined(
        "S", s_pct, usage.get("session_reset", ""),
        _ustr(usage, "session_window_cost"), now,
    )
    if session_line:
        rl_inners.append(session_line)

    pace = _weekly_pace(w_pct, usage.get("week_reset", ""), now)
    week_line = _usage_combined(
        "W", w_pct, usage.get("week_reset", ""),
        _ustr(usage, "week_cost"), now,
        pace=pace,
    )
    if week_line:
        rl_inners.append(week_line)

    # Sonnet (hidden below threshold)
    so_pct_raw = usage.get("sonnet_percent", "")
    so_pct = str(so_pct_raw) if so_pct_raw is not None and so_pct_raw != "" else ""
    if _on("SONNET") and so_pct:
        try:
            if int(so_pct) >= _env_int("SONNET_THRESHOLD", 25):
                sonnet_line = _usage_combined("So", so_pct, usage.get("sonnet_reset", ""), "", now)
                if sonnet_line:
                    rl_inners.append(sonnet_line)
        except ValueError:
            pass

    # TTL or staleness age
    have_rate_limits = True
    if _on("TTL"):
        upd_epoch = _parse_iso_epoch(_ustr(usage, "last_updated"))
        if upd_epoch is not None:
            ttl_s = int(600 - (now - upd_epoch))
            if ttl_s > 0:
                rl_inners.insert(0, f"{SUBDUED}TTL:{ttl_s // 60}m{ttl_s % 60}s{RST}")
            else:
                age_s = int(now - upd_epoch)
                if age_s >= STALE_THRESHOLD_S:
                    rl_inners.clear()
                    have_rate_limits = False
                else:
                    age_fmt = f"{age_s // 60}m"
                    rl_inners.insert(0, f"\033[0;31mstale:{age_fmt}\033[0m")

    return rl_inners, have_rate_limits


def _render_extra_usage(usage: dict, now: float) -> str:
    """Render Extra usage section (only when session % >= threshold)."""
    s_pct_raw = usage.get("session_percent", "")
    s_pct = str(s_pct_raw) if s_pct_raw is not None and s_pct_raw != "" else ""
    if not (_on("EXTRA") and s_pct):
        return ""
    try:
        if int(s_pct) < _env_int("EXTRA_SESSION_THRESHOLD", 60):
            return ""
    except ValueError:
        return ""

    es = _ustr(usage, "extra_spent")
    if not es:
        return ""

    el = _ustr(usage, "extra_limit")
    if el:
        extra_str = f"\033[0;90mE:${_fmt_money(es)}/${_fmt_money(el)}\033[0m"
    else:
        extra_str = f"\033[0;90mE:${_fmt_money(es)}\033[0m"

    deltas = _extra_deltas(float(es), usage, now)
    delta_parts: list[str] = []
    sd = deltas.get("extra_session_delta")
    if sd is not None:
        delta_parts.append(f"S:${_fmt_money(str(sd))}")
    wd = deltas.get("extra_week_delta")
    if wd is not None:
        delta_parts.append(f"W:${_fmt_money(str(wd))}")
    if delta_parts:
        extra_str += f" \033[0;90m{' '.join(delta_parts)}\033[0m"

    return extra_str


def _render_cost_windows(usage: dict) -> str:
    """Render historic cost window line (6H/12H/24H/7D/30D/AT)."""
    SEP = f"{SUBDUED} · {RST}"
    cost_parts: list[str] = []
    _COST_WINDOWS = [
        ("6H_COST",  False, "6H",  "six_hour_cost",         "six_hour_project_cost"),
        ("12H_COST", False, "12H", "twelve_hour_cost",       "twelve_hour_project_cost"),
        ("24H_COST", True,  "24H", "twenty_four_hour_cost",  "twenty_four_hour_project_cost"),
        ("7D_COST",  True,  "7D",  "seven_day_cost",         "seven_day_project_cost"),
        ("30D_COST", True,  "30D", "thirty_day_cost",        "thirty_day_project_cost"),
    ]
    for env_key, default, label, total_key, proj_key in _COST_WINDOWS:
        if _on(env_key, default=default):
            cost_line = _usage_cost(label, _ustr(usage, total_key),
                            _ustr(usage, proj_key))
            if cost_line:
                cost_parts.append(cost_line)

    # All-time (only when cost beyond 30D)
    if _on("AT_COST"):
        at_val = _ustr(usage, "all_time_cost")
        td_val = _ustr(usage, "thirty_day_cost")
        if at_val and td_val:
            try:
                if float(at_val) - float(td_val) >= 0.005:
                    at_line = _usage_cost("AT", at_val,
                                    _ustr(usage, "all_time_project_cost"))
                    if at_line:
                        cost_parts.append(at_line)
            except ValueError:
                pass

    return SEP.join(cost_parts) if cost_parts else ""


def _render_usage(usage: dict, now: float) -> tuple[str, str, str]:
    """Render usage data as session line, rate-limit sections, and cost line.

    Returns (session_rl, rest_rl_line, cost_line). Any may be empty.
    """
    if not _on("USAGE") or not usage:
        return "", "", ""

    SEP = f"{SUBDUED} · {RST}"

    rl_inners, have_rate_limits = _render_rate_limits(usage, now)
    session_rl = SEP.join(rl_inners) if rl_inners else ""

    rl_line = ""
    if have_rate_limits:
        extra = _render_extra_usage(usage, now)
        if extra:
            rl_line = extra

    cost_line = _render_cost_windows(usage) if _on("HISTORIC_COST") else ""

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
        # "Opus 4.6 (1M context)" → "Opus 4.6 1M"
        short_model = re.sub(r"\s*\((\d+\w+)\s+context\)", r" \1", model)
        parts.append(f"{SUBDUED}{short_model}{RST}")

    # Per-session cost (dynamic — standard dim)
    if _on("COST") and session_cost:
        try:
            fmt = f"{float(session_cost):.2f}"
            if fmt != "0.00":
                parts.append(f"\033[0;90m${fmt}\033[0m")
        except ValueError:
            pass

    # I/O ratio (structural)
    if _on("IO_RATIO") and total_in > 0 and total_out > 0:
        ratio = (total_out * 10 + total_in // 2) // total_in
        w, f = divmod(ratio, 10)
        parts.append(f"{SUBDUED}I/O:{w}.{f}x{RST}")

    # Cumulative cache hit rate (structural)
    if _on("CACHE_HIT"):
        ti = cum_fresh + cum_create + cum_read
        if ti > 0:
            ch = cum_read * 100 // ti
            parts.append(f"{SUBDUED}CH:{ch}%{RST}")

    # Context window token counts (structural)
    if used and ctx_size > 0:
        used_int = math.ceil(float(used))
        used_k = (ctx_size * used_int + 99999) // 100000
        effective_size = max(1, ctx_size - AUTOCOMPACT_BUFFER) if _on("USABLE_CTX") else ctx_size
        total_k = (effective_size + 999) // 1000
        total_str = f"{total_k // 1000}M" if total_k >= 1000 else f"{total_k}k"
        parts.append(f"{SUBDUED}{used_k}k/{total_str}{RST}")

    if not parts:
        return ""
    return " ".join(parts)


# --- Main ---


def _merge_cost_data(usage_data: dict, session_id: str, cwd: str) -> None:
    """Enrich usage_data with cost data from JSONL and cost summary cache."""
    if not usage_data and _on("HISTORIC_COST"):
        try:
            usage_data.update(compute_costs(session_id=session_id, cwd=cwd))
        except Exception:  # noqa: BLE001
            pass
    if usage_data and _on("HISTORIC_COST"):
        try:
            from cache_db import read_cost_summary
            cost_summary = read_cost_summary(max_age=900, cwd=cwd)
            if cost_summary:
                for k in (
                    "six_hour_cost", "twelve_hour_cost", "twenty_four_hour_cost",
                    "seven_day_cost", "thirty_day_cost", "all_time_cost",
                    "six_hour_project_cost", "twelve_hour_project_cost",
                    "twenty_four_hour_project_cost", "seven_day_project_cost",
                    "thirty_day_project_cost", "all_time_project_cost",
                ):
                    if k in cost_summary:
                        usage_data[k] = cost_summary[k]
        except Exception:  # noqa: BLE001
            pass
    if cwd and _on("HISTORIC_COST") and usage_data:
        usage_data.update(compute_project_rolling_costs(cwd))


class _InputData(NamedTuple):
    """Parsed input fields from Claude status JSON."""
    cwd: str
    model: str
    used: str
    ctx_size: int
    lines_added: int
    lines_removed: int
    cache_create: int
    cache_read: int
    input_fresh: int
    total_in: int
    total_out: int
    session_id: str


def _parse_input(data: dict) -> _InputData:
    """Extract all needed fields from Claude status JSON."""
    cwd = data.get("workspace", {}).get("current_dir") or data.get("cwd", "")
    model = data.get("model", {}).get("display_name", "")
    used_raw = data.get("context_window", {}).get("used_percentage", "")
    used = str(used_raw) if used_raw is not None and used_raw != "" else ""
    ctx_size = int(data.get("context_window", {}).get("context_window_size", 0) or 0)
    cost_obj = data.get("cost", {})
    cur = data.get("context_window", {}).get("current_usage", {})
    return _InputData(
        cwd=cwd,
        model=model,
        used=used,
        ctx_size=ctx_size,
        lines_added=int(cost_obj.get("total_lines_added", 0) or 0),
        lines_removed=int(cost_obj.get("total_lines_removed", 0) or 0),
        cache_create=int(cur.get("cache_creation_input_tokens", 0) or 0),
        cache_read=int(cur.get("cache_read_input_tokens", 0) or 0),
        input_fresh=int(cur.get("input_tokens", 0) or 0),
        total_in=int(data.get("context_window", {}).get("total_input_tokens", 0) or 0),
        total_out=int(data.get("context_window", {}).get("total_output_tokens", 0) or 0),
        session_id=data.get("session_id", ""),
    )


def _layout_and_print(
    top: list[str],
    session: str,
    usage_session_rl: str,
    usage_rl: str,
    usage_cost: str,
    usage_data: dict,
    macmon_str: str,
    sessions: str,
    now_epoch: float,
    _t_start: float,
) -> None:
    """Assemble rendered sections into adaptive layout and print."""
    # Show failure/stale indicator when usage is empty or outdated
    usage_stale_1h = False
    if usage_data:
        upd = _parse_iso_epoch(str(usage_data.get("last_updated", "") or ""))
        if upd is not None and (now_epoch - upd) >= STALE_THRESHOLD_S:
            usage_stale_1h = True
    if usage_stale_1h or (not usage_session_rl and (check_fetch_backoff() or usage_data.get("session_percent") is None)):
        if usage_data and usage_data.get("_stale"):
            usage_session_rl = f"\033[0;33musage stale\033[0m"
        else:
            usage_session_rl = f"\033[0;31musage fetch failed\033[0m"

    DOT = f"{SUBDUED} · {RST}"

    top = [s for s in top if s]
    top_str = " ".join(top)
    peak_str = _render_peak(now_epoch)
    session_parts = [s for s in [session, peak_str] if s]
    session_str = DOT.join(session_parts) if session_parts else ""
    usage_parts = [s for s in [usage_session_rl, usage_rl, usage_cost] if s]
    usage_str = DOT.join(usage_parts) if usage_parts else ""

    # Adaptive layout based on terminal width
    term_cols = _get_terminal_cols()
    if term_cols >= LAYOUT_WIDE_COLS:
        line1_parts = [s for s in [top_str, session_str] if s]
        line2_parts = [s for s in [usage_str] if s]
        lines = [DOT.join(line1_parts)]
        if line2_parts:
            lines.append(" ".join(line2_parts))
    else:
        lines = [top_str]
        if session_str:
            lines.append(session_str)
        if usage_session_rl:
            lines.append(usage_session_rl)
        rest = [s for s in [usage_rl, usage_cost] if s]
        if rest:
            lines.append(DOT.join(rest))

    _t_elapsed = time.monotonic() - _t_start
    last_parts: list[str] = []
    if macmon_str:
        last_parts.append(macmon_str)
    last_parts.append(f"{SUBDUED}{_t_elapsed:.3f}s{RST}")
    if sessions:
        last_parts.append(sessions)
    lines.append(DOT.join(last_parts))
    print("\n".join(lines))


def main() -> None:
    _t_start = time.monotonic()
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

    inp = _parse_input(data)
    now_epoch = time.time()

    # Start external commands (non-blocking) — runs while we do in-process work
    git_procs = _start_git(inp.cwd)
    macmon_proc = _start_macmon()
    try:
        # In-process: usage cache + dcat library (no subprocess)
        usage_data = _fetch_usage(inp.session_id, inp.cwd)
        # Strip project-scoped costs from usage cache — they belong to
        # whichever project last wrote the singleton row (macsetup-1zeq)
        if usage_data:
            for k in list(usage_data):
                if "project_cost" in k:
                    del usage_data[k]
        _merge_cost_data(usage_data, inp.session_id, inp.cwd)
        dcat_data = _fetch_dcat(inp.cwd)

        # Collect git results and macmon data
        git = _collect_git(git_procs)
        macmon_data = _collect_macmon(macmon_proc)
    finally:
        for p in git_procs.values():
            try:
                p.kill()
            except OSError:
                pass
        if macmon_proc:
            try:
                macmon_proc.kill()
            except OSError:
                pass

    # Cache stats
    cum_fresh, cum_create, cum_read = _accumulate_cache_stats(
        inp.session_id, inp.cache_read, inp.cache_create, inp.input_fresh, inp.total_in
    )

    # Render all sections
    top = [
        _render_timestamp(),
        _render_sandbox(inp.cwd, git.toplevel),
        _render_session_id(inp.session_id),
        _render_hostname(),
        _render_dir(inp.cwd, git.toplevel),
        _render_git(git.status_out, git.stash_out, git.branch, git.insertions, git.deletions),
        _render_dogcat(dcat_data),
        _render_changes(inp.lines_added, inp.lines_removed),
        _render_ctx_pct(inp.used, inp.ctx_size),
    ]
    chat_cost_val = compute_session_cost(inp.session_id, inp.cwd)
    chat_cost = str(chat_cost_val) if chat_cost_val > 0 else ""
    session = _render_session(
        inp.model, inp.used, inp.ctx_size, inp.total_in, inp.total_out,
        cum_fresh, cum_create, cum_read, chat_cost,
    )
    sessions = _render_sessions(inp.cwd, now_epoch)
    macmon_str = _render_macmon(macmon_data)
    usage_session_rl, usage_rl, usage_cost = _render_usage(usage_data, now_epoch)

    _layout_and_print(
        top, session, usage_session_rl, usage_rl, usage_cost,
        usage_data, macmon_str, sessions, now_epoch, _t_start,
    )


if __name__ == "__main__":
    main()
