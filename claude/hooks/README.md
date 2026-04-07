# Claude Code Hooks

PreToolUse hooks for Claude Code's Bash tool. Guard against command patterns that waste tokens or break your workflow.

## What you get

- **block-git-stash-worktree.sh** — blocks mutating `git stash` and `git worktree` commands. Read-only variants (`stash list`, `stash show`, `worktree list`) are allowed.
- **block-quoted-flags.sh** — blocks command patterns that trigger the ["quoted characters in flag names"](https://github.com/anthropics/claude-code/issues/27957) confirmation prompt: flags with embedded quotes (`--flag="value"`), `echo`/`printf` with quoted strings, and optionally compound commands via `BLOCK_COMPOUND_COMMANDS=1`.

## Installation

Tell your agent to read this repository and ask it to help you integrate the hooks into your Claude Code setup.
