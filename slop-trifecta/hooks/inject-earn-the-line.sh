#!/usr/bin/env bash
set -euo pipefail
# Emits the earn-the-line skill body as SessionStart additionalContext, so the
# artifact-prose rules load without a per-session forced read.
SKILL="${EARN_THE_LINE_SKILL:-$HOME/.claude/skills/earn-the-line/SKILL.md}"

# A moved or dangling symlink must not break session startup.
[ -r "$SKILL" ] || exit 0

# The frontmatter is skill-dispatch metadata; injected as context it only costs
# tokens.
body=$(awk 'NR==1 && $0=="---" {fm=1; next} fm && $0=="---" {fm=0; next} !fm' "$SKILL")
[ -n "$body" ] || exit 0

preamble='These rules govern the prose you write into artifacts this session,
and reviews of that prose. They do not govern your replies, which follow the
active output style — cut-the-crap in this setup; its Overrides section carries
the priority order. An instruction from the user outranks these rules, as that
order says. A request to document or comment is a request for prose under these
rules, not a waiver of them; when an instruction does override a rule, name the
rule you dropped in one clause. If you edit these rules this session, reread the
file on disk before applying them — this text is a snapshot taken at session
start.'

jq -nc --arg ctx "$preamble

$body" \
  '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$ctx}}'
