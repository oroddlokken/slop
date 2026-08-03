#!/usr/bin/env bash
# Seam both profiles' settings.json point at. Segment defaults live in
# statusline-command.py; per-machine CLAUDE_STATUSLINE_* overrides go here.

exec "$(dirname "${BASH_SOURCE[0]}")/statusline-command.py" "$@"
