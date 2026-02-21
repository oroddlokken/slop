#!/usr/bin/env python3
"""Fetch Claude Code usage data, cached for 10 minutes."""

import fcntl
import json
import os
import pty
import re
import select
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CACHE_DIR = Path.home() / ".cache" / "macsetup" / "claude"
CACHE_FILE = CACHE_DIR / "usage.json"
CACHE_MAX_AGE = 600  # 10 minutes
HISTORY_FILE = Path.home() / ".claude" / "history.jsonl"
CLAUDE_DIR = Path.home() / ".claude"
CLAUDE_JSON = Path.home() / ".claude.json"
# Run /usage sessions from the cache dir (must be trusted in ~/.claude.json)
USAGE_CWD = CACHE_DIR


def ensure_trusted_workspace() -> None:
    """Ensure USAGE_CWD is marked as trusted in ~/.claude.json.

    Reads the global config, adds a minimal project entry with
    hasTrustDialogAccepted=true for USAGE_CWD if missing, and writes back.
    """
    USAGE_CWD.mkdir(parents=True, exist_ok=True)
    if not CLAUDE_JSON.exists():
        return

    try:
        config = json.loads(CLAUDE_JSON.read_text())
    except (json.JSONDecodeError, OSError):
        return

    projects = config.get("projects", {})
    cwd_key = str(USAGE_CWD)
    entry = projects.get(cwd_key, {})
    if entry.get("hasTrustDialogAccepted"):
        return

    entry.setdefault("allowedTools", [])
    entry.setdefault("mcpContextUris", [])
    entry.setdefault("mcpServers", {})
    entry.setdefault("enabledMcpjsonServers", [])
    entry.setdefault("disabledMcpjsonServers", [])
    entry["hasTrustDialogAccepted"] = True
    entry.setdefault("projectOnboardingSeenCount", 1)
    entry.setdefault("hasClaudeMdExternalIncludesApproved", False)
    entry.setdefault("hasClaudeMdExternalIncludesWarningShown", False)
    entry.setdefault("hasCompletedProjectOnboarding", True)
    projects[cwd_key] = entry
    config["projects"] = projects

    try:
        CLAUDE_JSON.write_text(json.dumps(config, indent=2) + "\n")
    except OSError:
        pass


def find_claude() -> str | None:
    """Find the claude executable in PATH or common install locations."""
    if (claude := shutil.which("claude")) is not None:
        return claude

    home = Path.home()
    candidates = [
        home / ".npm-global" / "bin" / "claude",
        home / ".local" / "bin" / "claude",
        Path("/usr/local/bin/claude"),
        Path("/usr/bin/claude"),
    ]
    for p in candidates:
        if p.is_file():
            return str(p)

    # Check nvm versions
    nvm_dir = home / ".nvm" / "versions" / "node"
    if nvm_dir.is_dir():
        for node_ver in nvm_dir.iterdir():
            claude_path = node_ver / "bin" / "claude"
            if claude_path.exists():
                return str(claude_path)

    if shutil.which("npx"):
        return "npx claude"

    return None



def strip_ansi(text: str) -> str:
    """Strip ANSI escape sequences, preserving spatial layout.

    Cursor positioning sequences are converted to whitespace/newlines
    so the text retains its rendered structure.
    """
    # Cursor position (CSI row;col H) -> newline
    text = re.sub(r"\x1b\[\d+;\d+H", "\n", text)
    text = re.sub(r"\x1b\[\d*H", "\n", text)
    # Cursor forward (CSI n C) -> spaces
    text = re.sub(r"\x1b\[(\d+)C", lambda m: " " * int(m.group(1)), text)
    # Cursor up/down/back -> newline
    text = re.sub(r"\x1b\[\d*[ABD]", "\n", text)
    # All other CSI sequences (colors, clearing, etc.) -> empty
    text = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", text)
    # OSC sequences
    text = re.sub(r"\x1b\][^\x07]*\x07", "", text)
    # Other escape sequences
    text = re.sub(r"\x1b[^[\]].?", "", text)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _parse_time(time_part: str, ampm: str) -> tuple[int, int]:
    """Parse '2:59' or '3' with am/pm into 24h (hour, minute)."""
    if ":" in time_part:
        hour, minute = int(time_part.split(":")[0]), int(time_part.split(":")[1])
    else:
        hour, minute = int(time_part), 0
    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    return hour, minute


def _parse_reset_date(
    date_str: str,
    year_str: str | None,
    hour: int,
    minute: int,
) -> str | None:
    """Parse 'Feb 24' with optional year and time into ISO datetime."""
    try:
        now = datetime.now(tz=timezone.utc).astimezone()
        month_day = datetime.strptime(f"{date_str} {now.year}", "%b %d %Y")
        year = int(year_str) if year_str else now.year
        if not year_str:
            test_target = datetime(
                year, month_day.month, month_day.day, hour, minute,
                tzinfo=now.tzinfo,
            )
            if test_target < now:
                year += 1
        target = datetime(
            year, month_day.month, month_day.day, hour, minute,
            tzinfo=now.tzinfo,
        )
        return target.isoformat()
    except Exception:  # noqa: BLE001
        return None


def parse_usage_output(text: str) -> dict[str, Any]:
    """Parse usage percentages and reset times from stripped PTY output.

    Args:
        text: ANSI-stripped text from the claude /usage command.

    Returns:
        Dictionary with session/week/sonnet/extra usage fields.
    """
    data: dict[str, Any] = {}

    # PTY mangles text: "Current" -> "rrent", "Resets" -> "Rese s",
    # "2am" -> "2 m" (terminal escape sequences eat letters like t, C, a)
    # Bound each section so regexes can't leak across sections.
    _week_start = re.search(r"week", text, re.IGNORECASE)
    _session_text = text[: _week_start.start()] if _week_start else text

    # --- Current session ---
    if (m := re.search(r"session.+?(\d+)%\s*used", _session_text, re.DOTALL | re.IGNORECASE)):
        data["session_percent"] = int(m.group(1))

    # Match mangled am/pm: "am" may become " m", "pm" may become " m"
    if (m := re.search(
        r"Rese[\w\s]*?(\d+(?::\d+)?)\s*([ap]?\s*m)",
        _session_text, re.DOTALL | re.IGNORECASE,
    )):
        ampm_raw = re.sub(r"\s", "", m.group(2)).lower()
        ampm = "pm" if ampm_raw.startswith("p") else "am"
        hour, minute = _parse_time(m.group(1), ampm)
        now = datetime.now(tz=timezone.utc).astimezone()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target = target.replace(day=target.day + 1)
        data["session_reset"] = target.isoformat()

    # --- Current week (all models) ---
    if (m := re.search(
        r"Current\s+week\s*\(all\s*models\).+?(\d+)%\s*used", text, re.DOTALL,
    )):
        data["week_percent"] = int(m.group(1))

    if (m := re.search(
        r"Current\s+week\s*\(all\s*models\).*?Resets?\s+"
        r"([A-Za-z]+\s+\d+)(?:,?\s*(\d{4}))?\s*(?:at\s+)?(\d+(?::\d+)?)\s*(am|pm)",
        text, re.DOTALL | re.IGNORECASE,
    )):
        hour, minute = _parse_time(m.group(3), m.group(4).lower())
        if (iso := _parse_reset_date(m.group(1), m.group(2), hour, minute)):
            data["week_reset"] = iso

    # --- Current week (Sonnet only) ---
    if (m := re.search(
        r"Current\s+week\s*\(Sonnet\s*only\).+?(\d+)%\s*used", text, re.DOTALL,
    )):
        data["sonnet_percent"] = int(m.group(1))

    if (m := re.search(
        r"Current\s+week\s*\(Sonnet\s*only\).*?Resets?\s+"
        r"([A-Za-z]+\s+\d+)(?:,?\s*(\d{4}))?\s*(?:at\s+)?(\d+(?::\d+)?)\s*(am|pm)",
        text, re.DOTALL | re.IGNORECASE,
    )):
        hour, minute = _parse_time(m.group(3), m.group(4).lower())
        if (iso := _parse_reset_date(m.group(1), m.group(2), hour, minute)):
            data["sonnet_reset"] = iso

    # --- Extra usage ---
    if (m := re.search(r"Extra\s+usage.+?(\d+)%\s*used", text, re.DOTALL)):
        data["extra_percent"] = int(m.group(1))

    if (m := re.search(r"\$([0-9.]+)\s*/\s*\$([0-9.]+)\s*spent", text, re.DOTALL)):
        data["extra_spent"] = float(m.group(1))
        data["extra_limit"] = float(m.group(2))

    if (m := re.search(
        r"Extra\s+usage.*?Resets?\s+"
        r"([A-Za-z]+\s+\d+)(?:,?\s*(\d{4}))?\s*(?:at\s+)?(?:(\d+(?::\d+)?)\s*(am|pm))?",
        text, re.DOTALL | re.IGNORECASE,
    )) and m.group(1):
        hour, minute = 0, 0
        if m.group(3):
            hour, minute = _parse_time(m.group(3), (m.group(4) or "am").lower())
        if (iso := _parse_reset_date(m.group(1), m.group(2), hour, minute)):
            data["extra_reset"] = iso

    return data


def _drain_pty(master: int, timeout: float = 0.2) -> bytes:
    """Read all available bytes from a PTY master fd."""
    buf = b""
    while True:
        ready, _, _ = select.select([master], [], [], timeout)
        if not ready:
            break
        try:
            chunk = os.read(master, 4096)
            if not chunk:
                break
            buf += chunk
        except OSError:
            break
    return buf


def fetch_usage_via_pty() -> tuple[dict[str, Any], str]:
    """Spawn claude /usage in a PTY and parse the rendered output.

    Uses --session-id with a known UUID so the session can be cleaned up
    immediately, preventing clutter in the resume picker.

    Returns:
        Tuple of (parsed data dict with _meta timing, stripped raw text).
    """
    claude_cmd = find_claude()
    if not claude_cmd:
        return {"error": "Claude not found"}, ""

    ensure_trusted_workspace()

    master, slave = pty.openpty()
    cmd_parts = (
        [claude_cmd] if " " not in claude_cmd else claude_cmd.split()
    )
    session_id = str(uuid.uuid4())
    cmd_parts += ["--session-id", session_id]
    cmd_parts.append("/usage")
    cmd = cmd_parts

    t_start = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        stdin=slave,
        stdout=slave,
        stderr=slave,
        cwd=USAGE_CWD,
        preexec_fn=os.setsid,
        env={**os.environ, "TERM": "xterm-256color"},
    )
    os.close(slave)

    # Poll aggressively: drain PTY, parse every 0.5s until data is ready
    output = b""
    deadline = t_start + 15
    last_check = 0.0
    seen_fields: dict[str, float] = {}
    done = False
    while time.monotonic() < deadline:
        ready, _, _ = select.select([master], [], [], 0.1)
        if ready:
            try:
                chunk = os.read(master, 4096)
                if chunk:
                    output += chunk
            except OSError:
                break

        now = time.monotonic()
        if now - last_check >= 0.5:
            last_check = now
            elapsed = now - t_start
            text = strip_ansi(output.decode("utf-8", errors="ignore"))
            data = parse_usage_output(text)
            for key in data:
                if key not in seen_fields:
                    seen_fields[key] = round(elapsed, 2)
            if "session_percent" in data and "week_percent" in data:
                done = True
                output += _drain_pty(master)
                break

    try:
        os.write(master, b"/exit\n")
        time.sleep(0.3)
    except OSError:
        pass

    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
    os.close(master)

    total_elapsed = round(time.monotonic() - t_start, 2)
    text = strip_ansi(output.decode("utf-8", errors="ignore"))
    data = parse_usage_output(text)

    for key in data:
        if key not in seen_fields:
            seen_fields[key] = total_elapsed

    data["_meta"] = {
        "fetch_duration_s": total_elapsed,
        "field_timings": seen_fields,
        "completed_early": done,
        "session_id": session_id,
    }

    # Clean up the throwaway session so it doesn't pollute the resume picker
    cleaned = clean_session(session_id)
    if cleaned:
        data["_cleaned_session"] = cleaned

    return data, text


def read_cache() -> dict[str, Any] | None:
    """Read cached usage data if fresh enough (based on file mtime)."""
    if not CACHE_FILE.exists():
        return None
    age = time.time() - CACHE_FILE.stat().st_mtime
    if age > CACHE_MAX_AGE:
        return None
    with open(CACHE_FILE) as f:
        return json.load(f)


def write_cache(data: dict[str, Any]) -> None:
    """Write usage data to the cache file."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, indent=2)


def clean_history() -> int:
    """Remove /usage lines from Claude's history.jsonl.

    Opens the file with an exclusive lock, filters in memory, then
    truncates and rewrites.  The lock serialises concurrent get_usage.py
    runs; the window where an unlocked Claude append could be lost is
    reduced to the truncate+write (microseconds).

    Returns:
        Number of lines removed.
    """
    if not HISTORY_FILE.exists():
        return 0

    fd = os.open(str(HISTORY_FILE), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        with os.fdopen(os.dup(fd), "r") as f:
            lines = f.readlines()

        kept = [l for l in lines if '"display":"/usage"' not in l]
        removed = len(lines) - len(kept)

        if removed:
            os.lseek(fd, 0, os.SEEK_SET)
            os.ftruncate(fd, 0)
            os.write(fd, "".join(kept).encode())

        return removed
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def clean_session(session_id: str) -> list[str]:
    """Remove all Claude artifacts for a given session ID.

    Cleans up:
      - debug/{session_id}.txt
      - session-env/{session_id}/
      - todos/{session_id}-*.json
      - file-history/{session_id}/
      - projects/*/{session_id}.jsonl
      - projects/*/{session_id}/  (subagents, tool-results)

    Returns:
        List of paths that were removed.
    """
    removed: list[str] = []

    # Simple file/dir patterns under ~/.claude/
    for pattern, is_dir in [
        (f"debug/{session_id}.txt", False),
        (f"session-env/{session_id}", True),
        (f"file-history/{session_id}", True),
    ]:
        p = CLAUDE_DIR / pattern
        if is_dir and p.is_dir():
            shutil.rmtree(p)
            removed.append(str(p))
        elif not is_dir and p.exists():
            p.unlink()
            removed.append(str(p))

    # todos/{session_id}-*.json
    todos_dir = CLAUDE_DIR / "todos"
    if todos_dir.is_dir():
        for f in todos_dir.glob(f"{session_id}-*.json"):
            f.unlink()
            removed.append(str(f))

    # projects/*/{session_id}.jsonl and projects/*/{session_id}/
    projects_dir = CLAUDE_DIR / "projects"
    if projects_dir.is_dir():
        for project in projects_dir.iterdir():
            if not project.is_dir():
                continue
            session_file = project / f"{session_id}.jsonl"
            if session_file.exists():
                session_file.unlink()
                removed.append(str(session_file))
            session_sub = project / session_id
            if session_sub.is_dir():
                shutil.rmtree(session_sub)
                removed.append(str(session_sub))

    return removed


def main() -> None:
    """Fetch and print Claude usage data, using cache when fresh."""
    raw_mode = "--raw" in sys.argv
    force = "--force" in sys.argv

    if not force:
        cached = read_cache()
        if cached:
            print(json.dumps(cached, indent=2))
            return

    data, raw = fetch_usage_via_pty()

    if raw_mode:
        print("--- RAW PTY OUTPUT ---", file=sys.stderr)
        print(raw, file=sys.stderr)
        print("--- END RAW ---", file=sys.stderr)

    if "error" in data:
        print(f"Error: {data['error']}", file=sys.stderr)
        sys.exit(1)

    if not any(k for k in data if not k.startswith("_")):
        print("Could not parse usage data", file=sys.stderr)
        print(f"Raw output:\n{raw}", file=sys.stderr)
        sys.exit(1)

    data["last_updated"] = datetime.now(tz=timezone.utc).astimezone().isoformat()
    write_cache(data)

    cleaned: dict[str, Any] = {}
    history_removed = clean_history()
    if history_removed:
        cleaned["history_lines"] = history_removed
    if cleaned:
        data["_cleaned"] = cleaned

    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
