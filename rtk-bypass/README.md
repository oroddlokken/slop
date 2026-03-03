# rtk-bypass

Manage RTK rewrite bypasses for Claude Code hooks.

RTK rewrites shell commands via a `PreToolUse` hook. Some commands (like `curl`) don't need rewriting and just waste tokens. This tool lets you selectively bypass RTK for specific commands.

## How it works

Installs a wrapper hook (`~/.claude/hooks/rtk-bypass.sh`) that sits in front of `rtk-rewrite.sh`. Bypassed commands run directly; everything else delegates to RTK as usual. Survives RTK updates since RTK only overwrites `rtk-rewrite.sh`.

Bypass list is stored in `~/.claude/rtk-bypass.conf` (one command per line).

## Install

```bash
# Requires RTK hooks already set up (rtk init --global --auto-patch)
./rtk-bypass-installer.sh install
```

## Usage

```bash
rtk-bypass-installer.sh status              # Show status and bypassed commands
rtk-bypass-installer.sh disable <command>   # Bypass RTK for a command (e.g. curl, wget)
rtk-bypass-installer.sh enable <command>    # Re-enable RTK for a command
rtk-bypass-installer.sh uninstall           # Remove bypass hook, restore rtk-rewrite
```

## Example

```bash
./rtk-bypass-installer.sh install          # Installs hook, seeds "curl" as default bypass
./rtk-bypass-installer.sh disable wget     # Also bypass wget
./rtk-bypass-installer.sh disable gh       # Also bypass gh
./rtk-bypass-installer.sh status           # Shows: Bypassed: curl, wget, gh
```
