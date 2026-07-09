#!/usr/bin/env bash
set -euo pipefail
# Block mutating git stash/worktree commands. Allow read-only: stash list/show, worktree list.
# Set ALLOW_WORKTREES=0 to enable worktree blocking. Defaults to allowing worktrees.
# Set ALLOW_STASH=0 to enable stash blocking. Defaults to allowing stash.
ALLOW_WORKTREES="${ALLOW_WORKTREES:-0}"
ALLOW_STASH="${ALLOW_STASH:-0}"
cmd=$(jq -r '.tool_input.command' 2>/dev/null) || { echo '{"decision":"allow"}'; exit 0; }
if echo "$cmd" | grep -qE '\bgit\s+stash\b'; then
  if [ "$ALLOW_STASH" = "1" ]; then
    echo '{"decision":"allow"}'
  elif echo "$cmd" | grep -qE '\bgit\s+stash\s+(list|show)\b'; then
    echo '{"decision":"allow"}'
  else
    echo '{"decision":"block","reason":"git stash (mutating) is not allowed"}'
  fi
elif echo "$cmd" | grep -qE '\bgit\s+worktree\b'; then
  if [ "$ALLOW_WORKTREES" = "1" ]; then
    echo '{"decision":"allow"}'
  elif echo "$cmd" | grep -qE '\bgit\s+worktree\s+list\b'; then
    echo '{"decision":"allow"}'
  else
    echo '{"decision":"block","reason":"git worktree (mutating) is not allowed"}'
  fi
fi
