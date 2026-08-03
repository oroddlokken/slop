#!/bin/bash
set -euo pipefail

# Fixtures are built inline rather than stored as JSON files (the sibling
# block-quoted-flags-tests idiom): every payload here is a one-line command
# string, so a file per case would bury the thing under test.

DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="${HOOK_PATH:-$DIR/../hooks/block-git-stash-worktree.sh}"

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

# check expect payload_json label
#   expect: "allow", "deny", or "none" (hook emitted no decision)
check() {
  local expect="$1" payload="$2" label="$3"
  local out got

  out=$(printf '%s' "$payload" | "$HOOK" 2>/dev/null || true)
  if [ -z "$out" ]; then
    got="none"
  else
    got=$(jq -r '.hookSpecificOutput.permissionDecision // "malformed"' <<<"$out" 2>/dev/null || echo malformed)
  fi

  local status=PASS
  [ "$expect" = "$got" ] || status=FAIL
  if [ "$status" = "PASS" ]; then pass=$((pass + 1)); else fail=$((fail + 1)); fi
  printf '%-4s %-46s expect=%-6s got=%s\n' "$status" "$label" "$expect" "$got"
}

# Command substitution, not a pipe: `check` must run in this shell or its
# pass/fail counters (and the exit status built from them) are lost.
bash_case() {
  check "$1" "$(jq -nc --arg c "$2" '{tool_name:"Bash",tool_input:{command:$c}}')" "$2"
}

# -- Plain form --
bash_case deny  'git stash'
bash_case deny  'git stash push -u'
bash_case deny  'git stash pop'
bash_case deny  'git worktree add ../x'

# -- Read-only carve-out --
bash_case allow 'git stash list'
bash_case allow 'git stash show -p'
bash_case allow 'git worktree list'

# -- Global options before the subcommand (macsetup-2k3s). Each of these
# bypassed the hook before the normalization step existed. --
bash_case deny  'git -C /tmp/repo stash'
bash_case deny  'git -C /tmp/repo stash push -u'
bash_case deny  'git --git-dir=/tmp/r/.git stash save wip'
bash_case deny  'git --git-dir /tmp/r/.git stash'
bash_case deny  'git -c user.name=x stash pop'
bash_case deny  'git --no-pager stash'
bash_case deny  'git -C /tmp/repo worktree add ../x'
bash_case allow 'git -C /tmp/repo stash list'
bash_case allow 'git -c user.name=x worktree list'

# -- Normalization must not over-reach: options after a non-option token are
# left alone, so an unrelated command that merely mentions stash stays clean. --
bash_case none  'git branch -d stash'
bash_case none  'git log --oneline --grep=stash'
bash_case none  'git -C /tmp/repo log --grep=stash'
bash_case none  'ls -la'
bash_case none  'echo git worktrees are fine as a word'

# -- The words as data, not as a subcommand (macsetup-28nu3). The first case is
# the reported repro: a commit message describing the hook was denied. --
bash_case none  'git commit -m "explain the git stash and git worktree bypass"'
bash_case none  "git commit -m 'git worktree add is blocked'"
bash_case none  'echo git stash'
bash_case none  'echo "git stash pop"'
bash_case none  'grep -rn "git worktree add" .'
bash_case none  'dcat comment x add -t "git stash bypass, see git worktree"'
bash_case none  'git commit -F - <<EOF
mentions git stash and git worktree add
EOF'

# -- ...but a real invocation next to the data still denies --
bash_case deny  'git commit -m "a git stash note" && git stash'
bash_case deny  'echo "git stash"; git worktree add ../x'

# -- Command position: quoted or nested, these all execute --
bash_case deny  'bash -c "git stash"'
bash_case deny  "sh -c 'git worktree add ../x'"
bash_case deny  'eval "git stash pop"'
bash_case deny  'x=$(git stash list && git stash pop)'
bash_case deny  'sudo git stash'
bash_case deny  'timeout 5 git worktree add ../x'
bash_case deny  'xargs git stash'
bash_case deny  '/usr/bin/git stash'
bash_case deny  'cd /tmp/repo && git stash'
bash_case deny  '(git stash)'
bash_case allow 'echo "git stash"; git stash list'
bash_case allow 'x=$(git worktree list)'

# -- Non-Bash surfaces --
check deny  '{"tool_name":"Agent","tool_input":{"isolation":"worktree"}}'      'Agent isolation:worktree'
check none  '{"tool_name":"Agent","tool_input":{"prompt":"do a thing"}}'       'Agent without isolation'
check deny  '{"tool_name":"Workflow","tool_input":{"script":"agent(p, {isolation: \"worktree\"})"}}' 'Workflow isolation:worktree'
check none  '{"tool_name":"Workflow","tool_input":{"script":"agent(p, {label: \"x\"})"}}'            'Workflow without isolation'

# -- Input handling: an unreadable payload fails open (exit 0, no decision) --
check none  'not json at all'                                                 'malformed payload fails open'
check none  '{}'                                                              'empty object'

printf '\n%d passed, %d failed\n' "$pass" "$fail"
exit $fail
