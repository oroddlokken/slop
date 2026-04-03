#!/usr/bin/env bash
# Wrapper that calls statusline-command.py with env vars.

export CLAUDE_STATUSLINE_HOSTNAME=0
export CLAUDE_STATUSLINE_CHANGES=0
export CLAUDE_STATUSLINE_12H_COST=0
export CLAUDE_STATUSLINE_24H_COST=0

# Detect terminal width via /dev/tty (stdin/stdout are pipes from Claude Code)
COLUMNS=$(stty size </dev/tty 2>/dev/null | awk '{print $2}')
export COLUMNS="${COLUMNS:-80}"

exec "$(dirname "${BASH_SOURCE[0]}")/statusline-command.py" "$@"
