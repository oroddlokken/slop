# Claude Code Hooks

PreToolUse hooks for Claude Code's Bash tool. Symlinked to `~/.claude/hooks/`.

| Hook | Event | What it does |
|------|-------|--------------|
| block-git-stash-worktree.sh | PreToolUse (Bash) | Blocks mutating `git stash` / `git worktree` |
| block-quoted-flags.sh | PreToolUse (Bash) | Blocks `--flag="value"` patterns |
