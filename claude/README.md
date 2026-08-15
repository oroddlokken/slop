# Claude Code tooling

Launchers, a memory browser and hooks for Claude Code. Public copy of what I
run on my own machines. The private setup repo it comes from links all of this
into `~/.claude/` from a symlink manifest; the setup below is the manual
version of that, and works from a clone in any directory.

The status line, `ccreport` and `ccu` used to live here. They are their own
project now: [oroddlokken/ccreport](https://github.com/oroddlokken/ccreport).

## What's here

| Path | What it is |
|---|---|
| `claudemem` | TUI for browsing the Claude Code memories belonging to the current git repo — navigate, edit, delete with undo. `--json` prints them instead. |
| `claudem` | Launcher: `claudem <haiku\|sonnet\|opus\|fable> [low\|medium\|high\|xhigh\|max]` starts Claude Code with an explicit model and reasoning effort (default high). Single-letter shorthands, arguments in any order, everything else passed through to `claude`. |
| `cf`, `co` | Orchestrator wrappers, one script under two names: `cf` starts `claudem f` and `co` starts `claudem o`, each with an injected system prompt telling the session to delegate implementation work to the `cfcoder` agent. The two prompts differ only in the reason for the split — `cf` reserves a cheaper session model for judgment, `co` is already Opus and splits for context isolation. The script dispatches on its invoked name (`c<model>[<effort>]`), so symlinks like `cfl` or `com` give other model/effort combos — only the bare names `cf` and `co` inject. |
| `ccap` | Launcher: starts `claude` with [ccreport](https://github.com/oroddlokken/ccreport)'s `quota-guard.sh` armed — a warning past 80% of a usage window, a halted turn past 90%. `CCQUOTA_STOP` is what arms the guard and the hook reads the environment its session started with, so `CCQUOTA_STOP=95 ccap` moves the line for one session, and a session already running cannot be capped. Without the hook wired into `settings.json` it exports two variables nothing reads. |
| `cfcoder.md` | The agent definition `cf` and `co` delegate to: Opus at high effort doing the implementation. Only takes effect from an agents dir Claude Code reads — see below. |
| `hooks/` | `block-git-stash-worktree.sh`, a `PreToolUse` hook that blocks stash and worktree commands. Test suite in `hooks/block-git-stash-tests/` (payloads built inline — no fixture files). |

Requirements: `uv` (`claudemem` resolves its own dependencies through a PEP 723
shebang), `zsh` for `claudem`, `cf`/`co` and `ccap`, and `jq` for the git-stash
hook.
That hook also wants `perl` — without it, it falls back to substring matching
and over-blocks.

## cf and co

`cf` needs `claudem` (and `claude`) on `PATH`, and `cfcoder.md` in an agents
directory Claude Code actually loads — `~/.claude/agents/` for all projects, or
`.claude/agents/` in the repo you run it from:

```bash
cp /path/to/slop/claude/cfcoder.md ~/.claude/agents/
```

Without the agent installed, the injected prompt tells the session to delegate
to an agent that doesn't exist.

`cf` and `co` are the same script under two names — it reads its own invoked
name to pick model and effort, so the name is the whole configuration. Any
other combination is a symlink away:

```bash
ln -s /path/to/slop/claude/cf ~/bin/cfl   # fable, low effort, no injection
ln -s /path/to/slop/claude/cf ~/bin/com   # opus, medium effort, no injection
```

## Hooks

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash|Agent|Task|Workflow",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/slop/claude/hooks/block-git-stash-worktree.sh",
            "statusMessage": "Checking for blocked git commands..."
          }
        ]
      }
    ]
  }
}
```

The test suite takes a `HOOK_PATH` override and exits with the failure count:

```bash
claude/hooks/block-git-stash-tests/run-tests.sh
```
