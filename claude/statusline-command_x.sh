#!/usr/bin/env bash
# Seam both profiles' settings.json point at. Segment defaults live in
# statusline-command.py; per-machine CLAUDE_STATUSLINE_* overrides go here.

export CLAUDE_STATUSLINE_SCOPED_THRESHOLD=0
export CLAUDE_STATUSLINE_SCOPED_MODE=current

export CLAUDE_STATUSLINE_CHANGES=0
export CLAUDE_STATUSLINE_GIT_DIFFSTAT=0
export CLAUDE_STATUSLINE_DOGCAT=0

exec "$(dirname "${BASH_SOURCE[0]}")/statusline-command.py" "$@"
