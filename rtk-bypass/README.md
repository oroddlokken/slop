# rtk-bypass

Manage RTK rewrite bypasses for Claude Code hooks.

RTK rewrites shell commands via a `PreToolUse` hook. Some commands (like `curl`) don't need rewriting and just waste tokens. This tool lets you selectively bypass RTK for specific commands or subcommands.

## How it works

Installs a wrapper hook (`~/.claude/hooks/rtk-bypass.sh`) that sits in front of `rtk-rewrite.sh`. Bypassed commands run directly; everything else delegates to RTK as usual. Survives RTK updates since RTK only overwrites `rtk-rewrite.sh`.

Bypass list is stored in `~/.claude/rtk-bypass.conf` (one entry per line).

## Install

```bash
# Requires RTK hooks already set up (rtk init --global --auto-patch)
./rtk-bypass-installer.sh install
```

## Usage

```bash
rtk-bypass-installer.sh status                       # Show status and bypassed commands
rtk-bypass-installer.sh disable <command>            # Bypass RTK for a command (e.g. curl, wget)
rtk-bypass-installer.sh disable <command> <subcmd>   # Bypass RTK for a subcommand (e.g. git status)
rtk-bypass-installer.sh enable <command>             # Re-enable RTK for a command
rtk-bypass-installer.sh enable <command> <subcmd>    # Re-enable RTK for a subcommand
rtk-bypass-installer.sh uninstall                    # Remove bypass hook, restore rtk-rewrite
```

## Subcommand support

You can bypass specific subcommands while keeping RTK active for other subcommands of the same tool. For example, bypass `git status` but keep RTK rewriting for `git diff` and `git log`.

Matching priority: subcommand match (`git status`) is checked first, then base command (`git`). A base command entry bypasses all subcommands.

## Example

```bash
./rtk-bypass-installer.sh install              # Installs hook, seeds "curl" as default bypass
./rtk-bypass-installer.sh disable wget         # Also bypass wget
./rtk-bypass-installer.sh disable git status   # Bypass git status only (git diff still rewritten)
./rtk-bypass-installer.sh disable gh           # Bypass all gh subcommands
./rtk-bypass-installer.sh status              # Shows: Bypassed: curl, wget, git status, gh
```

The conf file would look like:

```
curl
wget
git status
gh
```
