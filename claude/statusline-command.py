#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Claude Code status line — Python implementation for performance.

Receives JSON via stdin, outputs a formatted status line to stdout.

AUDIT: All calculations are documented in claude/CLAUDE.md.
       When changing any calculation, caching, or data format here,
       update CLAUDE.md to match.

Layout adapts to terminal width. Claude Code sets $COLUMNS itself (v2.1.153+);
/dev/tty is only a fallback for direct invocation. See LAYOUT_WIDE_COLS:
  >= 150 columns: 2 lines (top+session | usage+costs)
  <  150 columns: 4 lines (top | session | usage | costs)

Toggle sections via environment variables (1=enabled, 0=disabled):
  CLAUDE_STATUSLINE_MODEL_BANNER            — colored banner showing the active model (default 0)
  CLAUDE_STATUSLINE_RED                     — recolor entire status line red, any model (default 0)
  CLAUDE_STATUSLINE_HAIKU_RED               — recolor entire status line red when on Haiku
  CLAUDE_STATUSLINE_TIMESTAMP               — HH:MM invocation timestamp
  CLAUDE_STATUSLINE_SESSION_ID              — short session UUID
  CLAUDE_STATUSLINE_HOSTNAME                — green hostname (default 0)
  CLAUDE_STATUSLINE_DIR                     — blue project directory
  CLAUDE_STATUSLINE_SANDBOX                 — sbx/!sbx badge from merged Claude settings
  CLAUDE_STATUSLINE_DSP                     — orange DSP marker when started with --dangerously-skip-permissions
  CLAUDE_STATUSLINE_GIT                     — branch + indicators
    CLAUDE_STATUSLINE_GIT_DIFFSTAT          — working-tree +N-N inside the git indicators
  CLAUDE_STATUSLINE_DOGCAT                  — dcat issue tracker counts
  CLAUDE_STATUSLINE_CHANGES                 — cumulative lines added/removed (entire invocation) (default 0)
  CLAUDE_STATUSLINE_RENDER_TIME             — how long this render took (0.235s) (default 0)
  CLAUDE_STATUSLINE_SESSION                 — model, context window %
    CLAUDE_STATUSLINE_COST                  — session cost
    CLAUDE_STATUSLINE_CACHE_HIT             — cache hit rate % (default 0)
    CLAUDE_STATUSLINE_EFFORT                — reasoning effort level, as (xhigh); folded into MODEL_BANNER when that is on
    CLAUDE_STATUSLINE_THINKING              — nothink marker when thinking is off
  CLAUDE_STATUSLINE_USABLE_CTX               — base ctx% on the usable window (nominal minus the ~33k auto-compact reserve)
  CLAUDE_STATUSLINE_APPLE_SILICON            — macmon temps/power (requires macmon) (default 0)
  CLAUDE_STATUSLINE_BATTERY                 — battery % / state / time remaining (pmset) (default 0)
  CLAUDE_STATUSLINE_SESSIONS                — active sessions in last 15 min (default 0)
  CLAUDE_STATUSLINE_USAGE                   — Claude usage (session/week % with countdowns)
    CLAUDE_STATUSLINE_WEEKLY_PACE            — weekly pace indicator (D3/7: On Pace)
    CLAUDE_STATUSLINE_SONNET                — Sonnet usage %
    CLAUDE_STATUSLINE_SONNET_THRESHOLD      — hide Sonnet below this % (default 25)
    CLAUDE_STATUSLINE_SCOPED                — per-model weekly limit (label from the model)
    CLAUDE_STATUSLINE_SCOPED_THRESHOLD      — hide scoped limit below this % (default 25)
    CLAUDE_STATUSLINE_SCOPED_MODE           — always / off / current: show the scoped
                                              segment regardless, never, or only when the
                                              session runs the capped model (default current)
    CLAUDE_STATUSLINE_EXTRA                 — Extra usage spent/limit + per-window deltas (S/W)
    CLAUDE_STATUSLINE_EXTRA_SESSION_THRESHOLD — show Extra when S% >= this (default 60)
    CLAUDE_STATUSLINE_TTL                   — time until next usage fetch (default 0;
                                              only when S/W are not on stdin, which on
                                              Pro/Max is the pre-first-message render)
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
  CF_BADGE                                  — cyan CF badge after the model name (set by the cf wrapper)
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
from pricing import (
    ROLLING_WINDOWS,
    SESSION_WINDOW_S,
    WEEK_WINDOW_S,
    compute_costs,
    compute_project_rolling_costs,
    compute_session_cost,
    rolling_cost_keys,
    window_start_epoch,
)

# --- Config ---

# Thresholds and layout constants
TEMP_WARN_C = 75           # °C — yellow warning for CPU/GPU temp
TEMP_CRIT_C = 90           # °C — red alert for CPU/GPU temp
BATT_WARN_PCT = 40         # % — yellow warning when discharging
BATT_CRIT_PCT = 20         # % — red alert when discharging
STALE_THRESHOLD_S = 3600   # seconds before usage data is considered too old
STALE_GRACE_S = 1800       # age the stale marker waits for when S/W have no native source
USAGE_FETCH_INTERVAL_S = 600    # normal cadence when the API is actually needed
USAGE_HEARTBEAT_S = 3600   # ceiling on API staleness when nothing needs it now
NEAR_THRESHOLD_MARGIN = 10  # % below a display threshold that still warrants fetching
COST_SUMMARY_MAX_AGE = 900  # seconds the cached compute_costs() result stays usable
EXTRA_ACCRUAL_PCT = 90     # session % from which extra credits could start accruing
LAYOUT_WIDE_COLS = 150     # terminal columns threshold for 2-line layout
SESSION_WINDOW_MS = 900_000  # 15 min — active sessions lookback

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

_ANSI_RE = re.compile(r"\033\[[0-9;]*m")
# A model badge: bold white on a background, opened and closed in one run.
_BADGE_RE = re.compile(r"\033\[1;97;[0-9;]+m[^\033]*\033\[0m")


def _vis_len(text: str) -> int:
    """Visible character count — what the terminal renders, ANSI stripped."""
    return len(_ANSI_RE.sub("", text))


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m"


def _force_red(text: str) -> str:
    """Strip existing ANSI color codes and recolor everything bold bright red.

    The model badge keeps its own colors — it is the one token whose background
    still has to read at a glance once the rest of the line is flat red.
    """
    badges: list[str] = []

    def _stash(m: re.Match[str]) -> str:
        badges.append(m.group(0))
        return f"\0{len(badges) - 1}\0"

    out = f"\033[1;91m{_ANSI_RE.sub('', _BADGE_RE.sub(_stash, text))}\033[0m"
    for i, badge in enumerate(badges):
        out = out.replace(f"\0{i}\0", f"{RST}{badge}\033[1;91m")
    return out


# Levels whose own name doesn't capitalize into a word. Only the badge spells
# them out; the plain-name fallback keeps the raw (xhigh).
_EFFORT_BADGE_LABELS = {"xhigh": "Extra"}


def _model_banner(model: str, effort: str = "") -> str:
    """Render an inverse-color banner showing the active model.

    Stands in for the plain model name in the session segment, so it carries the
    whole name rather than just the family. `effort` folds inside the background
    instead of trailing it — the banner has to stay one bold-white run for
    _force_red's _BADGE_RE to stash it whole.
    """
    if not _on("MODEL_BANNER", default=False) or not model:
        return ""
    m_low = model.lower()
    if "haiku" in m_low:
        # Different red than Opus when HAIKU_RED is on, magenta otherwise.
        bg = "48;5;196" if _on("HAIKU_RED") else "45"
    elif "sonnet" in m_low:
        bg = "44"  # blue
    elif "opus" in m_low:
        bg = "48;5;93"    # deep purple
    elif "fable" in m_low:
        bg = "48;5;28"   # green — clear of the reds, blue, purple
    else:
        bg = "100"  # bright black / grey fallback
    # Drops the "(1M context)" suffix Opus carries in display_name.
    label = re.sub(r"\s*\(.*\)\s*$", "", model).strip().upper()
    # Capitalized, no parens: inside the badge the effort needs no bracketing to
    # separate it from the shouted model name, only a different case.
    if effort:
        label = f"{label} {_EFFORT_BADGE_LABELS.get(effort, effort.capitalize())}"
    return f"\033[1;97;{bg}m {label} \033[0m"


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
    if not _on("APPLE_SILICON", default=False):
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


# --- Battery (pmset) ---


def _start_battery() -> subprocess.Popen[bytes] | None:
    """Start pmset battery query as a non-blocking subprocess."""
    if not _on("BATTERY", default=False):
        return None
    try:
        return subprocess.Popen(
            ["pmset", "-g", "batt"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        return None


_BATT_RE = re.compile(r"(\d+)%;\s*([\w ]+?);(?:\s*(\d+:\d+)\s+remaining)?")


def _collect_battery(proc: subprocess.Popen[bytes] | None) -> dict:
    """Parse pmset -g batt output into {pct, state, time}."""
    if proc is None:
        return {}
    try:
        out, _ = proc.communicate(timeout=2)
    except (subprocess.TimeoutExpired, OSError):
        proc.kill()
        return {}
    if not out:
        return {}
    m = _BATT_RE.search(out.decode("utf-8", errors="replace"))
    if not m:
        return {}
    return {"pct": int(m.group(1)), "state": m.group(2), "time": m.group(3) or ""}


def _render_battery(batt: dict) -> str:
    """Render battery stats: BAT:65%↓3:43 (discharging) / BAT:80%⚡0:31 (charging)."""
    if not batt:
        return ""
    pct = batt["pct"]
    state = batt["state"]
    discharging = state == "discharging"
    # Alert colors only when discharging and low; otherwise subdued
    if discharging and pct <= BATT_CRIT_PCT:
        val_col = "\033[0;31m"
    elif discharging and pct <= BATT_WARN_PCT:
        val_col = "\033[0;33m"
    else:
        val_col = SUBDUED
    sym = "↓" if discharging else "⚡" if state == "charging" else ""
    t = batt["time"]
    t_str = t if t and t != "0:00" and state in ("discharging", "charging") else ""
    return f"{SUBDUED}BAT:{val_col}{pct}%{sym}{t_str}{RST}"


# --- Permission mode ---


def _start_dsp_check() -> subprocess.Popen[bytes] | None:
    """Start ps to walk the ancestor chain for --dangerously-skip-permissions.

    Claude Code may spawn the statusline through one or more shells, so the
    immediate parent isn't necessarily the claude binary. ps -Aww gives us
    untruncated args for every process; we walk pid→ppid until we hit init.
    """
    if not _on("DSP"):
        return None
    try:
        return subprocess.Popen(
            ["ps", "-Awwo", "pid=,ppid=,args="],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, FileNotFoundError):
        return None


def _kill(proc: subprocess.Popen[bytes] | None) -> None:
    """Kill a helper subprocess if it is still around. Never raises."""
    if proc is None:
        return
    try:
        proc.kill()
    except OSError:
        pass


def _collect_dsp(proc: subprocess.Popen[bytes] | None) -> bool:
    if proc is None:
        return False
    try:
        out, _ = proc.communicate(timeout=2)
    except (subprocess.TimeoutExpired, OSError):
        try:
            proc.kill()
        except OSError:
            pass
        return False
    if not out:
        return False
    procs: dict[int, tuple[int, str]] = {}
    for line in out.decode("utf-8", errors="replace").splitlines():
        parts = line.strip().split(None, 2)
        if len(parts) < 2:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
        except ValueError:
            continue
        procs[pid] = (ppid, parts[2] if len(parts) > 2 else "")
    cur = os.getppid()
    while cur > 1:
        entry = procs.get(cur)
        if not entry:
            break
        ppid, args = entry
        if "--dangerously-skip-permissions" in args:
            return True
        cur = ppid
    return False


def _render_dsp(active: bool) -> str:
    if not active:
        return ""
    return "\033[38;5;208mDSP\033[0m"


# --- Usage data ---


def _adjust_passed_resets(data: dict, now: float) -> dict:
    """Zero out percentages for rate limit windows whose reset time has passed.

    When stale data shows e.g. S:80% but the session has already reset,
    the actual utilization is near 0. Showing the old value is misleading.
    """
    if not data:
        return data
    for pct_key, reset_key in [
        ("session_percent", "session_reset"),
        ("week_percent", "week_reset"),
        ("sonnet_percent", "sonnet_reset"),
        ("scoped_percent", "scoped_reset"),
    ]:
        reset_iso = data.get(reset_key)
        if reset_iso:
            epoch = _parse_iso_epoch(str(reset_iso))
            if epoch is not None and epoch <= now:
                data[pct_key] = 0
                del data[reset_key]
    return data


def _native_rate_limits(data: dict) -> dict:
    """Rate limits Claude Code sends on stdin — current on every render, no fetch.

    Pro/Max only, and absent until the first API response of the session; each
    window can be absent on its own. resets_at is epoch seconds here, converted
    to ISO so the rest of the pipeline reads it like the cached OAuth values.
    Percentages arrive as floats and are rounded to match the cache's ints.
    """
    rl = data.get("rate_limits") or {}
    out: dict = {}
    for window, pct_key, reset_key in (
        ("five_hour", "session_percent", "session_reset"),
        ("seven_day", "week_percent", "week_reset"),
    ):
        w = rl.get(window) or {}
        try:
            pct = w.get("used_percentage")
            if pct is None:
                continue
            out[pct_key] = int(round(float(pct)))
        except (TypeError, ValueError):
            continue
        resets = w.get("resets_at")
        if resets:
            try:
                out[reset_key] = datetime.fromtimestamp(float(resets)).isoformat()  # noqa: DTZ006
            except (TypeError, ValueError, OSError, OverflowError):
                pass
    return out


def _api_fetch_needed(usage: dict, native_rl: dict, now: float) -> bool:
    """Whether the usage API can still change what the render shows.

    S and W arrive natively on stdin, so the API is only worth calling for the
    fields it alone supplies: Sonnet %, the scoped per-model limit, and Extra
    spend. When none of those can surface, the call is skipped and costs are
    refreshed locally instead.

    A heartbeat still fires every USAGE_HEARTBEAT_S. Without it the cached
    Sonnet/scoped percentages could only ever justify a fetch using their own
    frozen values — a quota climbing past its threshold would never be noticed.
    """
    if not native_rl:
        return True  # no native S/W — the API is the only source for them
    upd_epoch = _parse_iso_epoch(str(usage.get("last_updated", "") or ""))
    if upd_epoch is None:
        return True  # cold cache — fetch once to learn what applies
    if now - upd_epoch >= USAGE_HEARTBEAT_S:
        return True
    # Extra is displayed once the session window crosses its threshold — which
    # some profiles set to 0, making it permanent. A frozen $0 is still harmless
    # there: extra credits only accrue after the 5-hour window is exhausted. So
    # refresh it when spend has actually started, or when the window is close
    # enough that spend could start before the next heartbeat.
    if _on("EXTRA"):
        try:
            s_pct = int(native_rl.get("session_percent", 0) or 0)
        except (TypeError, ValueError):
            s_pct = 0
        # The threshold comparison is the render's, against the native reading
        # rather than the cached one.
        if _extra_threshold_met(s_pct):
            try:
                spent = float(usage.get("extra_spent") or 0)
            except (TypeError, ValueError):
                spent = 0.0
            if spent > 0 or s_pct >= EXTRA_ACCRUAL_PCT:
                return True
    # Sonnet and scoped: track once the cached value is within reach of showing.
    for on_key, pct_key, thr_key in (
        ("SONNET", "sonnet_percent", "SONNET_THRESHOLD"),
        ("SCOPED", "scoped_percent", "SCOPED_THRESHOLD"),
    ):
        if not _on(on_key):
            continue
        raw = usage.get(pct_key)
        if raw is None or raw == "":
            continue  # null on this plan — nothing to track
        try:
            pct = int(raw)
        except (TypeError, ValueError):
            continue
        if pct >= _env_int(thr_key, 25) - NEAR_THRESHOLD_MARGIN:
            return True
    return False


def _spawn_usage_refresh(session_id: str, cwd: str, usage: dict, *, costs_only: bool) -> None:
    """Spawn the detached refresh subprocess (survives parent kill)."""
    script = Path(__file__).resolve().parent / "get_claude_usage.py"
    if not script.exists():
        return
    cmd = [sys.executable, str(script), "--session", session_id, "--cwd", cwd]
    if costs_only:
        # Pass the native window bounds so session_window_cost is computed
        # against the real window rather than the cached reset times.
        cmd.append("--costs-only")
        for flag, key in (("--session-reset", "session_reset"), ("--week-reset", "week_reset")):
            val = _ustr(usage, key)
            if val:
                cmd += [flag, val]
    else:
        cmd += ["--wait-timeout", "4"]
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        pass


def _fetch_usage(session_id: str, cwd: str, native_rl: dict) -> dict:
    """Get usage data: env var → cache bypass → detached get_claude_usage.py.

    The refresh subprocess is detached (start_new_session=True) so it survives
    the parent being killed by the statusline framework (e.g. tmux interval).
    Stale cached data is returned for this render; fresh data appears next call.

    When the API cannot affect the render the spawn becomes --costs-only, which
    skips the network entirely but keeps the cost windows current.
    """
    now = time.time()
    pre = os.environ.get("CLAUDE_STATUSLINE_USAGE_JSON", "")
    if pre:
        try:
            return _adjust_passed_resets(json.loads(pre), now)
        except json.JSONDecodeError:
            return {}
    stale = read_usage_stale() or {}
    want_api = _api_fetch_needed(stale, native_rl, now)
    cached = read_usage_for_statusline()
    if cached is not None:
        return _adjust_passed_resets(cached, now)
    if not want_api:
        # API data is deliberately left to age; only refresh costs, and only
        # when the summary the render reads has actually expired.
        from cache_db import read_cost_summary

        if read_cost_summary(max_age=COST_SUMMARY_MAX_AGE, cwd=cwd) is None:
            _spawn_usage_refresh(session_id, cwd, stale, costs_only=True)
        return _adjust_passed_resets(stale, now)
    _spawn_usage_refresh(session_id, cwd, stale, costs_only=False)
    # Return stale data for this render; fresh data will be in cache next call
    return _adjust_passed_resets(stale, now)


# --- Dcat status ---


def _fetch_dcat(cwd: str) -> dict:
    """Count dcat issues by status, reading .dogcats/issues.jsonl directly.

    Parsing dogcat's own storage instead of importing the library keeps this
    script free of third-party dependencies, so the statusline still renders on
    machines without dogcat. The trade is a coupling to the on-disk format: if
    that changes, the dc[] badge disappears rather than the statusline breaking.

    issues.jsonl is an append log — later records for an id supersede earlier
    ones, and tombstoned issues are dropped. Archived issues live in
    .dogcats/archive/ and are excluded, which matches plain `dcat list`.
    """
    if not _on("DOGCAT") or not cwd:
        return {}
    try:
        latest: dict[str, dict] = {}
        with open(f"{cwd}/.dogcats/issues.jsonl", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get("record_type") == "issue":
                    latest[rec["id"]] = rec
        by_status: dict[str, int] = {}
        for rec in latest.values():
            if rec.get("deleted_at"):
                continue
            status = rec.get("status")
            if status:
                by_status[status] = by_status.get(status, 0) + 1
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
    """Accumulate per-message cache stats. Returns (cum_fresh, cum_create, cum_read).

    total_in_tokens is the change key, not a running total: since v2.1.132 it is
    the current context input, which equals the sum of the three current_usage
    input fields. Compared with != rather than >, so a context that shrinks
    after /compact still accumulates. Equality means the same API response we
    already counted — the guard that keeps repeat renders (refreshInterval, mode
    changes) from double-counting. Two consecutive responses with an identical
    input total undercount by one; the payload carries no per-message id to key
    on instead.
    """
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
    Empty when unset everywhere.
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
    if (insertions or deletions) and _on("GIT_DIFFSTAT"):
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


# Tokens reserved by Claude Code before auto-compact. Estimate, not documented
# anywhere: calibrated against a 200k window and applied flat, so a 1M window
# reads as 967k. Verify against /context before trusting it at 1M.
AUTOCOMPACT_BUFFER = 33_000


def _usable_ctx(ctx_size: int) -> int:
    """Window the session can actually fill, minus the auto-compact reserve."""
    if _on("USABLE_CTX") and ctx_size > AUTOCOMPACT_BUFFER:
        return ctx_size - AUTOCOMPACT_BUFFER
    return ctx_size


def _used_tokens(used: str, ctx_size: int, total_in: int) -> int | None:
    """Input tokens in context, exact where possible. None when unknown.

    total_input_tokens is the sum of the three current_usage input fields, the
    same input-only basis used_percentage reports, so preferring it costs nothing
    and avoids reconstructing tokens from an integer percentage — 1% is 10k
    tokens on a 1M window. It reads 0 before the first API response and again
    after /compact until the next call, which is where used_percentage fills in.
    """
    if total_in > 0:
        return total_in
    if used and ctx_size > 0:
        return round(ctx_size * float(used) / 100)
    return None


def _render_ctx_pct(used_tokens: int | None, ctx_size: int) -> str:
    if used_tokens is None or ctx_size <= 0:
        return ""
    used_int = min(100, math.ceil(used_tokens * 100 / _usable_ctx(ctx_size)))
    col = "31" if used_int >= 70 else "33" if used_int >= 50 else "32"
    return f"\033[0;90mctx:\033[0;{col}m{used_int}%\033[0m"


def _render_changes(lines_added: int, lines_removed: int) -> str:
    if not _on("CHANGES", default=False):
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


def _usage_reset_clock(reset_iso: str, now_epoch: float) -> str:
    """Local wall-clock time the window resets at, e.g. "16:30"."""
    epoch = _parse_iso_epoch(reset_iso)
    if epoch is None or epoch <= now_epoch:
        return ""
    return datetime.fromtimestamp(epoch).strftime("%H:%M")  # noqa: DTZ006


def _pace_days() -> int:
    """Return the pace window in days from CLAUDE_CODE_PACE_DAYS env var (default 7)."""
    try:
        d = int(os.environ.get("CLAUDE_CODE_PACE_DAYS", "7"))
        return d if 1 <= d <= 7 else 7
    except ValueError:
        return 7


def _weekly_pace(
    w_pct_s: str, reset_iso: str, now: float, *, countdown: bool = True,
) -> str:
    """Weekly pace indicator: compare actual usage % to expected % based on elapsed time.

    Expected = how far through the PACE_DAYS window we are (time-based, not day-based).
    Display: "{el_d}d{el_h}h/{N}d {sign}{delta}%"

    countdown=False drops the "(4d2h)" parenthetical, for a second segment sharing
    a reset with one already on screen.
    """
    if not _on("WEEKLY_PACE"):
        return ""
    if not w_pct_s:
        return ""
    reset_epoch = _parse_iso_epoch(reset_iso)
    week_start = window_start_epoch(reset_iso, WEEK_WINDOW_S, now)
    if reset_epoch is None or week_start is None:
        return ""
    try:
        actual = int(w_pct_s)
    except ValueError:
        return ""
    pace = _pace_days()
    elapsed_s = now - week_start
    elapsed_frac = elapsed_s / WEEK_WINDOW_S
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
    if remain_s > 0 and countdown:
        cd = _usage_countdown(reset_iso, now)
        time_part = f"{elapsed_str}/7d({cd})"
    else:
        time_part = f"{elapsed_str}/7d"
    d_round = round(delta)
    sign = "+" if d_round >= 0 else ""
    return f"\033[0;90m{time_part} {sign}{d_round}%\033[0m"


def _usage_combined(
    label: str, pct_s: str, reset_iso: str, cost_s: str, now: float,
    *, pace: str = "", clock: bool = False, countdown: bool = True,
) -> str:
    """Render compact usage: W:26% $293 1d6h/7d 5d17h

    clock appends the wall-clock reset time to the countdown: "1h20m(16:30)".
    countdown=False drops it, for a segment whose reset is already on screen.
    """
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
    elif countdown:
        cd = _usage_countdown(reset_iso, now)
        if cd:
            at = _usage_reset_clock(reset_iso, now) if clock else ""
            parts.append(f"\033[0;90m{cd}({at})\033[0m" if at else f"\033[0;90m{cd}\033[0m")
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


def _render_sessions(cwd: str, now: float) -> str:
    """Active sessions: distinct projects from history in last 15 min."""
    if not _on("SESSIONS", default=False):
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
    return compute_extra_window_deltas(
        current_spent,
        window_start_epoch(usage.get("session_reset", ""), SESSION_WINDOW_S, now),
        window_start_epoch(usage.get("week_reset", ""), WEEK_WINDOW_S, now),
    )


def _ustr(d: dict, key: str) -> str:
    """Safely extract a string value from a usage dict."""
    return str(d.get(key, "") or "")


def _pct_str(d: dict, key: str) -> str:
    """A percentage as a string. 0 is a reading; absent is not — unlike _ustr.

    _ustr collapses 0 to "" via `or`, which is right for a cost and wrong for a
    quota: 0% means the window just reset, and the segment should render it.
    """
    raw = d.get(key, "")
    return str(raw) if raw is not None and raw != "" else ""


def _extra_threshold_met(session_percent: object) -> bool:
    """Whether the session window is far enough along for Extra to matter.

    One comparison for the fetch decision and the render decision: if they
    disagree, a fetch spends a subprocess on a field the render then drops. A
    missing or unreadable percentage is not a reading, so the answer is no — a
    threshold pinned to 0 must not turn "unknown" into "over the line". A real
    0 does count.
    """
    if session_percent is None or session_percent == "":
        return False
    try:
        pct = int(session_percent)
    except (TypeError, ValueError):
        return False
    return pct >= _env_int("EXTRA_SESSION_THRESHOLD", 60)


def _extra_is_material(usage: dict) -> bool:
    """Whether the Extra segment is both displayed and carrying real spend.

    Some profiles pin EXTRA_SESSION_THRESHOLD to 0, so being on screen says
    nothing on its own; only actual spend makes its age worth flagging.
    """
    if not _on("EXTRA"):
        return False
    try:
        if float(usage.get("extra_spent") or 0) <= 0:
            return False
    except (TypeError, ValueError):
        return False
    return _extra_threshold_met(usage.get("session_percent"))


def _fetch_ttl(usage: dict, now: float) -> str:
    """Countdown to the next usage-API fetch, empty when overdue or unknown."""
    upd_epoch = _parse_iso_epoch(_ustr(usage, "last_updated"))
    if upd_epoch is None:
        return ""
    ttl_s = int(USAGE_FETCH_INTERVAL_S - (now - upd_epoch))
    if ttl_s <= 0:
        return ""
    return f"{SUBDUED}TTL:{ttl_s // 60}m{ttl_s % 60}s{RST}"


def _render_rate_limits(usage: dict, now: float) -> tuple[list[str], bool, bool]:
    """Build rate-limit inner sections (S/W/So + TTL).

    Returns (rl_inners, have_rate_limits, sc_shown). *have_rate_limits* may be
    set to False if data is too stale, even when it was True on entry.
    """
    s_pct = _pct_str(usage, "session_percent")
    w_pct = _pct_str(usage, "week_percent")
    if not (s_pct or w_pct):
        return [], False

    rl_inners: list[str] = []

    session_line = _usage_combined(
        "S", s_pct, usage.get("session_reset", ""),
        _ustr(usage, "session_window_cost"), now,
        clock=True,
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
    so_pct = _pct_str(usage, "sonnet_percent")
    so_shown = False
    if _on("SONNET") and so_pct:
        try:
            if int(so_pct) >= _env_int("SONNET_THRESHOLD", 25):
                sonnet_line = _usage_combined("So", so_pct, usage.get("sonnet_reset", ""), "", now)
                if sonnet_line:
                    rl_inners.append(sonnet_line)
                    so_shown = True
        except ValueError:
            pass

    # Per-model weekly limit — a quota separate from W, scoped to one model.
    # Label comes from the API's display_name ("Fable" → Fa) since which model
    # is capped varies; skipped when it would duplicate the Sonnet segment.
    sc_pct = _pct_str(usage, "scoped_percent")
    sc_model = _ustr(usage, "scoped_model")
    sc_shown = False
    sc_mode = _env("SCOPED_MODE", "current").lower()
    sc_wanted = sc_mode == "always" or (
        sc_mode == "current"
        and sc_model.lower() in _ustr(usage, "_current_model").lower()
    )
    if _on("SCOPED") and sc_wanted and sc_pct and sc_model:
        if not (so_shown and sc_model.lower().startswith("sonnet")):
            try:
                if int(sc_pct) >= _env_int("SCOPED_THRESHOLD", 25):
                    sc_reset = usage.get("scoped_reset", "")
                    # The scoped quota usually resets with the weekly one, and then
                    # both segments print the same countdown. Compare the rendered
                    # strings, not the epochs: identical characters is the actual
                    # redundancy, and it survives the sub-minute drift between a
                    # reset that arrives on stdin and one that comes from a fetch.
                    dup_cd = bool(week_line) and _usage_countdown(
                        sc_reset, now,
                    ) == _usage_countdown(usage.get("week_reset", ""), now)
                    sc_pace = _weekly_pace(
                        sc_pct, sc_reset, now, countdown=not dup_cd,
                    )
                    scoped_line = _usage_combined(
                        sc_model[:2].title(), sc_pct,
                        sc_reset, "", now,
                        pace=sc_pace, countdown=not dup_cd,
                    )
                    if scoped_line:
                        rl_inners.append(scoped_line)
                        sc_shown = True
            except ValueError:
                pass

    # TTL and staleness. S/W arrive on stdin every render, so the fetch clock
    # only earns space when it still drives something: TTL when the API is the
    # source for S/W at all, the red marker when a fetched field is actually on
    # screen and overdue. A displayed E:$0 with no spend does not count — it
    # cannot move until the window is exhausted.
    have_rate_limits = True
    upd_epoch = _parse_iso_epoch(_ustr(usage, "last_updated"))
    if upd_epoch is not None:
        age_s = int(now - upd_epoch)
        if not usage.get("_native_rl"):
            ttl_s = int(USAGE_FETCH_INTERVAL_S - age_s)
            if _on("TTL", default=False) and ttl_s > 0:
                rl_inners.insert(0, f"{SUBDUED}TTL:{ttl_s // 60}m{ttl_s % 60}s{RST}")
            elif age_s >= STALE_THRESHOLD_S:
                rl_inners.clear()
                have_rate_limits = False
            elif age_s >= STALE_GRACE_S or check_fetch_backoff():
                # Past the fetch interval is not yet worth a warning here: the
                # session's first render has no native S/W either, and the
                # refresh it spawns lands on the next one. Wait for the grace
                # age, or for a recorded failure that says it will not land.
                rl_inners.insert(0, f"\033[0;31mstale:{age_s // 60}m\033[0m")
        elif age_s >= STALE_THRESHOLD_S and (so_shown or sc_shown or _extra_is_material(usage)):
            rl_inners.insert(0, f"\033[0;31mstale:{age_s // 60}m\033[0m")

    return rl_inners, have_rate_limits, sc_shown


def _render_extra_usage(usage: dict, now: float) -> str:
    """Render Extra usage section (only when session % >= threshold)."""
    if not _extra_is_material(usage):
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


# Env toggle and default per rolling window. Written out so `6H_COST` is
# greppable; the key names and labels are derived from ROLLING_WINDOWS.
_COST_WINDOW_TOGGLES = {
    "six_hour": ("6H_COST", False),
    "twelve_hour": ("12H_COST", False),
    "twenty_four_hour": ("24H_COST", True),
    "seven_day": ("7D_COST", True),
    "thirty_day": ("30D_COST", True),
}


def _render_cost_windows(usage: dict) -> str:
    """Render historic cost window line (6H/12H/24H/7D/30D/AT)."""
    SEP = f"{SUBDUED} · {RST}"
    cost_parts: list[str] = []
    # Shortest window first, the order the line reads in. Labels and key names
    # come from pricing.ROLLING_WINDOWS; only the toggle and its default are a
    # per-window choice, so only those live here.
    for w in reversed(ROLLING_WINDOWS):
        env_key, default = _COST_WINDOW_TOGGLES[w.name]
        if _on(env_key, default=default):
            cost_line = _usage_cost(w.label, _ustr(usage, f"{w.name}_cost"),
                            _ustr(usage, f"{w.name}_project_cost"))
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

    rl_inners, have_rate_limits, sc_shown = _render_rate_limits(usage, now)
    session_rl = SEP.join(rl_inners) if rl_inners else ""

    rl_line = ""
    if have_rate_limits:
        extra = _render_extra_usage(usage, now)
        if extra:
            rl_line = extra

    cost_line = _render_cost_windows(usage) if _on("HISTORIC_COST") else ""
    # The scoped segment's numbers come from the fetch, so while it is on
    # screen the cost line carries the countdown to the next fetch.
    if cost_line and sc_shown:
        ttl = _fetch_ttl(usage, now)
        if ttl:
            cost_line = f"{cost_line}{SEP}{ttl}"

    return session_rl, rl_line, cost_line


def _render_effort(level: str) -> str:
    """Reasoning effort for the session. Ultracode is not distinct — it reads as xhigh."""
    if not _on("EFFORT") or not level:
        return ""
    return f"{SUBDUED}({level}){RST}"


def _render_thinking(thinking_off: bool) -> str:
    """Flag extended thinking being off — the state worth noticing."""
    if not _on("THINKING") or not thinking_off:
        return ""
    return _c("0;33", "nothink")


def _render_session(
    model: str,
    effort: str,
    thinking_off: bool,
    used_tokens: int | None,
    ctx_size: int,
    cum_fresh: int,
    cum_create: int,
    cum_read: int,
    session_cost: str,
) -> str:
    if not _on("SESSION"):
        return ""
    parts: list[str] = []

    effort_seg = _render_effort(effort)
    banner = _model_banner(model, effort if effort_seg else "")
    if model:
        # Opus carries a "(1M context)" suffix in display_name; strip it so the
        # name reads the same across models.
        base = re.sub(r"\s*\(\d+\w+\s+context\)", "", model)
        parts.append(banner or f"{SUBDUED}{base}{RST}")

    # cf orchestrator sessions (claudem-shorthand exports CF_BADGE=1). Cyan —
    # no model banner uses it, and the 1;97 run lets _BADGE_RE stash it whole.
    # Glued to the model part so the two badges sit flush.
    if os.environ.get("CF_BADGE") == "1":
        badge = "\033[1;97;46m CF \033[0m"
        if parts:
            parts[-1] += badge
        else:
            parts.append(badge)

    # Reasoning config sits with the model it configures. The banner already
    # carries the effort, so only the plain-name fallback repeats it here.
    for seg in ("" if banner else effort_seg, _render_thinking(thinking_off)):
        if seg:
            parts.append(seg)

    # Per-session cost (dynamic — standard dim)
    if _on("COST") and session_cost:
        try:
            fmt = f"{float(session_cost):.2f}"
            if fmt != "0.00":
                parts.append(f"\033[0;90m${fmt}\033[0m")
        except ValueError:
            pass

    # Cumulative cache hit rate (structural)
    if _on("CACHE_HIT", default=False):
        ti = cum_fresh + cum_create + cum_read
        if ti > 0:
            ch = cum_read * 100 // ti
            parts.append(f"{SUBDUED}CH:{ch}%{RST}")

    # Context window token counts (structural)
    if used_tokens is not None and ctx_size > 0:
        used_k = (used_tokens + 999) // 1000
        total_k = (_usable_ctx(ctx_size) + 999) // 1000
        # 1000/1000 renders "1M", 1500/1000 renders "1.5M" — a truncating //
        # turned a 1.5M window into 1M.
        total_str = f"{total_k / 1000:g}M" if total_k >= 1000 else f"{total_k}k"
        parts.append(f"{SUBDUED}{used_k}k/{total_str}{RST}")

    if not parts:
        return ""
    return " ".join(parts)


# --- Main ---


def _merge_cost_data(
    usage_data: dict, session_id: str, cwd: str, native_rl: dict | None = None,
) -> None:
    """Enrich usage_data with cost data from JSONL and cost summary cache."""
    if not usage_data and _on("HISTORIC_COST"):
        # Cold start: no cached row, so the window bounds can only come from
        # stdin. Without them compute_costs has no session window to total.
        rl = native_rl or {}
        try:
            usage_data.update(compute_costs(
                session_id=session_id, cwd=cwd,
                session_reset_iso=rl.get("session_reset"),
                week_reset_iso=rl.get("week_reset"),
            ))
        except Exception:  # noqa: BLE001
            pass
    if usage_data and _on("HISTORIC_COST"):
        try:
            from cache_db import read_cost_summary
            cost_summary = read_cost_summary(max_age=COST_SUMMARY_MAX_AGE, cwd=cwd)
            if cost_summary:
                for k in (
                    # The S/W window costs come from here too, not just the usage
                    # row, so they stay current when the API fetch is skipped.
                    "session_window_cost", "week_cost", *rolling_cost_keys(),
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
    effort: str
    thinking_off: bool
    used: str
    ctx_size: int
    lines_added: int
    lines_removed: int
    cache_create: int
    cache_read: int
    input_fresh: int
    total_in: int
    session_id: str


def _parse_input(data: dict) -> _InputData:
    """Extract all needed fields from Claude status JSON."""
    # `or {}` throughout, not `.get(k, {})`: Claude Code sends several of these
    # as explicit null rather than omitting them, and a default never applies to
    # a key that is present. current_usage is null before the first API call and
    # again after /compact until the next one.
    cw = data.get("context_window") or {}
    cur = cw.get("current_usage") or {}
    cost_obj = data.get("cost") or {}
    cwd = (data.get("workspace") or {}).get("current_dir") or data.get("cwd", "")
    model = (data.get("model") or {}).get("display_name", "")
    used = _pct_str(cw, "used_percentage")
    ctx_size = int(cw.get("context_window_size", 0) or 0)
    # effort is absent when the model has no effort parameter; thinking only
    # counts as off when explicitly false, not when the field is missing
    effort = str((data.get("effort") or {}).get("level", "") or "")
    thinking_off = (data.get("thinking") or {}).get("enabled") is False
    return _InputData(
        cwd=cwd,
        model=model,
        effort=effort,
        thinking_off=thinking_off,
        used=used,
        ctx_size=ctx_size,
        lines_added=int(cost_obj.get("total_lines_added", 0) or 0),
        lines_removed=int(cost_obj.get("total_lines_removed", 0) or 0),
        cache_create=int(cur.get("cache_creation_input_tokens", 0) or 0),
        cache_read=int(cur.get("cache_read_input_tokens", 0) or 0),
        input_fresh=int(cur.get("input_tokens", 0) or 0),
        total_in=int(cw.get("total_input_tokens", 0) or 0),
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
    battery_str: str,
    sessions: str,
    now_epoch: float,
    _t_start: float,
    force_red: bool = False,
) -> None:
    """Assemble rendered sections into adaptive layout and print."""
    # Show failure/stale indicator when usage is empty or outdated
    usage_stale_1h = False
    if usage_data:
        upd = _parse_iso_epoch(str(usage_data.get("last_updated", "") or ""))
        if upd is not None and (now_epoch - upd) >= STALE_THRESHOLD_S:
            usage_stale_1h = True
    # Never claim the usage line is stale or failed while S/W come from stdin;
    # the stale:Nm marker inside the line covers the fetched fields instead.
    if usage_data.get("_native_rl"):
        pass
    elif usage_stale_1h or (not usage_session_rl and (check_fetch_backoff() or usage_data.get("session_percent") is None)):
        if usage_data and usage_data.get("_stale"):
            usage_session_rl = f"\033[0;33musage stale\033[0m"
        else:
            usage_session_rl = f"\033[0;31musage fetch failed\033[0m"

    DOT = f"{SUBDUED} · {RST}"

    top = [s for s in top if s]
    # Render time and active-session count trail the top line
    if _on("RENDER_TIME", default=False):
        top.append(f"{SUBDUED}{time.monotonic() - _t_start:.3f}s{RST}")
    if sessions:
        top.append(sessions)
    top_str = " ".join(top)
    usage_parts = [s for s in [usage_session_rl, usage_rl, usage_cost] if s]
    usage_str = DOT.join(usage_parts) if usage_parts else ""

    # Adaptive layout based on terminal width
    term_cols = _get_terminal_cols()
    if term_cols >= LAYOUT_WIDE_COLS:
        line1_parts = [s for s in [top_str, session] if s]
        line2_parts = [s for s in [usage_str] if s]
        # A badge opens the session segment with its own background, which
        # separates it from git on its own — the dot there reads as clutter.
        sep = " " if _BADGE_RE.match(session) else DOT
        lines = [sep.join(line1_parts)]
        if line2_parts:
            lines.append(" ".join(line2_parts))
    else:
        lines = [top_str]
        if session:
            # Same badge rule as the wide layout; join onto the top line
            # whenever the pair fits the terminal, else fall back to its
            # own line.
            sep = " " if _BADGE_RE.match(session) else DOT
            joined = sep.join(s for s in (top_str, session) if s)
            if _vis_len(joined) <= term_cols:
                lines = [joined]
            else:
                lines.append(session)
        if usage_session_rl:
            lines.append(usage_session_rl)
        rest = [s for s in [usage_rl, usage_cost] if s]
        if rest:
            lines.append(DOT.join(rest))

    last_parts = [s for s in (macmon_str, battery_str) if s]
    if last_parts:
        lines.append(DOT.join(last_parts))
    if force_red:
        lines = [_force_red(line) for line in lines]
    print("\n".join(lines))


def main() -> None:
    _t_start = time.monotonic()
    now_epoch = time.time()
    test_null = "-t0" in sys.argv  # pre-first-API-call / post-compact null state
    test_mode = "-t" in sys.argv or test_null

    if test_mode:
        cwd = os.getcwd()
        data = {
            "session_id": "mock-session-id",
            "session_name": "mock-session",
            "version": "2.1.220",
            "workspace": {"current_dir": cwd},
            "model": {"id": "claude-opus-5[1m]", "display_name": "Opus 5 (1M context)"},
            "effort": {"level": "xhigh"},
            "thinking": {"enabled": True},
            "fast_mode": False,
            "context_window": {
                "used_percentage": 42.7,
                "remaining_percentage": 57.3,
                "context_window_size": 1000000,
                # total_input_tokens is the sum of the three current_usage
                # input fields, and used_percentage is that over the window
                "total_input_tokens": 427_000,
                "total_output_tokens": 15177,
                "current_usage": {
                    "input_tokens": 494,
                    "output_tokens": 15177,
                    "cache_creation_input_tokens": 6_500,
                    "cache_read_input_tokens": 420_006,
                },
            },
            "cost": {
                "total_cost_usd": 1.37,
                "total_lines_added": 128,
                "total_lines_removed": 34,
            },
            "rate_limits": {
                "five_hour": {"used_percentage": 23.5, "resets_at": now_epoch + 8100},
                "seven_day": {"used_percentage": 41.2, "resets_at": now_epoch + 401_400},
            },
        }
        if test_null:
            data["context_window"].update(
                used_percentage=None, remaining_percentage=None,
                current_usage=None, total_input_tokens=0, total_output_tokens=0,
            )
    else:
        raw = sys.stdin.read()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

    inp = _parse_input(data)

    # Start external commands (non-blocking) — runs while we do in-process work
    git_procs = _start_git(inp.cwd)
    macmon_proc = _start_macmon()
    battery_proc = _start_battery()
    dsp_proc = _start_dsp_check()
    try:
        # Computed before the fetch decision (it gates whether the API is worth
        # calling) but applied after the cost merge — see below.
        native_rl = _native_rate_limits(data)
        # In-process: usage cache + .dogcats log (no subprocess)
        usage_data = _fetch_usage(inp.session_id, inp.cwd, native_rl)
        # Strip project-scoped costs from usage cache — they belong to
        # whichever project last wrote the singleton row (macsetup-1zeq)
        if usage_data:
            for k in list(usage_data):
                if "project_cost" in k:
                    del usage_data[k]
        _merge_cost_data(usage_data, inp.session_id, inp.cwd, native_rl)
        # S and W come from stdin when Claude Code sends them — always current,
        # so they win over the cache. Applied after the cost merge, which keys
        # its compute-vs-read choice on usage_data being empty. Sonnet, Extra
        # and the scoped limit still come from the fetch.
        if native_rl:
            usage_data.update(native_rl)
            usage_data["_native_rl"] = True
        dcat_data = _fetch_dcat(inp.cwd)

        # Collect git results and macmon data
        git = _collect_git(git_procs)
        macmon_data = _collect_macmon(macmon_proc)
        battery_data = _collect_battery(battery_proc)
        dsp_active = _collect_dsp(dsp_proc)
    finally:
        for p in (*git_procs.values(), macmon_proc, battery_proc, dsp_proc):
            _kill(p)

    # Cache stats
    cum_fresh, cum_create, cum_read = _accumulate_cache_stats(
        inp.session_id, inp.cache_read, inp.cache_create, inp.input_fresh, inp.total_in
    )

    # Render all sections
    top = [
        _render_timestamp(),
        _render_dsp(dsp_active),
        _render_sandbox(inp.cwd, git.toplevel),
        _render_session_id(inp.session_id),
        _render_hostname(),
        _render_dir(inp.cwd, git.toplevel),
        _render_git(git.status_out, git.stash_out, git.branch, git.insertions, git.deletions),
        _render_dogcat(dcat_data),
        _render_changes(inp.lines_added, inp.lines_removed),
    ]
    chat_cost_val = compute_session_cost(inp.session_id, inp.cwd)
    chat_cost = str(chat_cost_val) if chat_cost_val > 0 else ""
    used_tokens = _used_tokens(inp.used, inp.ctx_size, inp.total_in)
    session = _render_session(
        inp.model, inp.effort, inp.thinking_off, used_tokens, inp.ctx_size,
        cum_fresh, cum_create, cum_read, chat_cost,
    )
    # ctx% trails the token counts it summarizes; stays independent of SESSION
    session = " ".join(s for s in (session, _render_ctx_pct(used_tokens, inp.ctx_size)) if s)
    sessions = _render_sessions(inp.cwd, now_epoch)
    macmon_str = _render_macmon(macmon_data)
    battery_str = _render_battery(battery_data)
    # The scoped segment's "current" mode compares against the session model.
    usage_data["_current_model"] = inp.model
    usage_session_rl, usage_rl, usage_cost = _render_usage(usage_data, now_epoch)

    _layout_and_print(
        top, session, usage_session_rl, usage_rl, usage_cost,
        usage_data, macmon_str, battery_str, sessions, now_epoch, _t_start,
        force_red=_on("RED", default=False)
        or (_on("HAIKU_RED") and "haiku" in inp.model.lower()),
    )


if __name__ == "__main__":
    main()
