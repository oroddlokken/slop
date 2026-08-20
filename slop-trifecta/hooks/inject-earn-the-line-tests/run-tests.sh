#!/bin/bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="${HOOK_PATH:-$DIR/../inject-earn-the-line.sh}"

if ! command -v jq >/dev/null 2>&1; then
  echo "FATAL: jq not found on PATH (required by the hook)" >&2
  exit 1
fi

if [ ! -x "$HOOK" ]; then
  echo "hook not executable: $HOOK" >&2
  exit 1
fi

pass=0
fail=0

report() {
  local status=PASS
  [ "$1" = "$2" ] || status=FAIL
  if [ "$status" = "PASS" ]; then pass=$((pass + 1)); else fail=$((fail + 1)); fi
  printf '%-4s %-46s expect=%-24s got=%s\n' "$status" "$3" "$1" "$2"
}

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

cat >"$TMP/SKILL.md" <<'EOF'
---
name: earn-the-line
description: 'Discipline for the prose you write into artifacts.'
---

# earn-the-line

Default to no comment. A line earns its place by carrying what the code cannot
show: a rationale, a gotcha, an ordering constraint.
EOF

out=$(EARN_THE_LINE_SKILL="$TMP/SKILL.md" "$HOOK" </dev/null)

report SessionStart \
  "$(jq -r '.hookSpecificOutput.hookEventName // "missing"' <<<"$out")" \
  'hookEventName is SessionStart'

report yes \
  "$(jq -r 'if (.hookSpecificOutput.additionalContext // "") | test("# earn-the-line") then "yes" else "no" end' <<<"$out")" \
  'body reaches additionalContext'

report no \
  "$(jq -r 'if (.hookSpecificOutput.additionalContext // "") | test("description:") then "yes" else "no" end' <<<"$out")" \
  'frontmatter stripped'

report yes \
  "$(jq -r 'if (.hookSpecificOutput.additionalContext // "") | test("govern the prose you write into artifacts") then "yes" else "no" end' <<<"$out")" \
  'preamble prefixed'

rc=0
out=$(EARN_THE_LINE_SKILL="$TMP/missing.md" "$HOOK" </dev/null) || rc=$?
report "0/" "$rc/$out" 'missing skill file exits 0 and prints nothing'

# A file that is all frontmatter leaves nothing worth injecting.
printf -- '---\nname: x\n---\n' >"$TMP/empty.md"
rc=0
out=$(EARN_THE_LINE_SKILL="$TMP/empty.md" "$HOOK" </dev/null) || rc=$?
report "0/" "$rc/$(tr -d '[:space:]' <<<"$out")" 'body-less skill exits 0 and prints nothing'

printf '\n%d passed, %d failed\n' "$pass" "$fail"
exit $fail
