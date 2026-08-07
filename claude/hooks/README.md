# Claude Code Hooks

Hooks for Claude Code. Symlinked to `~/.claude/hooks/`.

| Hook | Event | What it does |
|------|-------|--------------|
| block-git-stash-worktree.sh | PreToolUse (Bash\|Agent\|Task\|Workflow) | Blocks mutating `git stash` / `git worktree`, plus `isolation: "worktree"` on subagents and in workflow scripts |

`block-git-stash-worktree.sh` parses the Bash command with an embedded perl
scanner so only *executed* git invocations count — a `git stash` inside a commit
message, an `echo`, or a heredoc body is data and passes. Without perl it falls
back to a bare substring match, which over-blocks rather than under-blocks.

A fixture suite lives one level up: `../block-git-stash-tests/run-tests.sh`.
It takes a `HOOK_PATH` override and exits with the failure count.
