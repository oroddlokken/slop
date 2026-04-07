# Claude Code Hooks

PreToolUse hooks for Claude Code's Bash tool. Guard against command patterns that waste tokens or break your workflow.

## What you get

- **block-git-stash-worktree.sh** — blocks mutating `git stash` and `git worktree` commands. Read-only variants (`stash list`, `stash show`, `worktree list`) are allowed.
- **block-quoted-flags.sh** — blocks command patterns that trigger the ["quoted characters in flag names"](https://github.com/anthropics/claude-code/issues/27957) confirmation prompt: flags with embedded quotes (`--flag="value"`), `echo`/`printf` with quoted strings, and optionally compound commands via `BLOCK_COMPOUND_COMMANDS=1`.

## Installation

1. Copy the hook scripts somewhere persistent (e.g. `~/.claude/hooks/`):

```bash
cp block-quoted-flags.sh block-git-stash-worktree.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/block-*.sh
```

2. Add them to your project's `.claude/settings.json` (or `~/.claude/settings.json` for global use) under `hooks.PreToolUse`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/block-git-stash-worktree.sh",
            "statusMessage": "Checking for blocked git commands..."
          },
          {
            "type": "command",
            "command": "~/.claude/hooks/block-quoted-flags.sh",
            "statusMessage": "Checking for quoted flag patterns..."
          }
        ]
      }
    ]
  }
}
```

The `matcher` field controls which tool triggers the hook — `"Bash"` runs them before every Bash tool call. Each hook receives the tool input as JSON on stdin and can block execution by exiting non-zero with a message on stderr.

## Configuration

**block-quoted-flags.sh** has one optional feature flag:

| Variable | Default | Effect |
|---|---|---|
| `BLOCK_COMPOUND_COMMANDS` | `0` | Set to `1` to also block `&&`, `||`, and `;` chains |

To enable it, set the env var in the hook command:

```json
{
  "type": "command",
  "command": "BLOCK_COMPOUND_COMMANDS=1 ~/.claude/hooks/block-quoted-flags.sh"
}
```
