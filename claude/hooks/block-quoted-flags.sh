#!/usr/bin/env bash
# Prevent commands that trigger Claude Code's "Do you want to proceed" prompts.
# Re-audited 2026-07-09 on Claude Code 2.1.205 (see docs/prompt-corpus.md):
# the original rules for quoted flag values, quoted echo/printf, brace-with-
# quote, for/while/until/if constructs, and compound chains were removed —
# those prompts are gone upstream. Still firing despite allowlists:
#   - "Contains ansi_c_string"   $'...' literal    → rule B5
#   - "Contains case_statement"  case ... esac     → rule B9
# Upstream: https://github.com/anthropics/claude-code/issues/27957
set -euo pipefail
# POSIX locale: predictable [[:space:]] semantics and byte-level matching.
export LC_ALL=C

# Every rule-specific block below routes through this. It leads with a fixed
# preamble, then appends the rule's guidance read from stdin (a heredoc), then
# exits 2. The preamble fixes the "silent block" failure mode: a blocked
# command emits no stdout, and an agent can mistake that emptiness for a real
# answer — e.g. concluding a folder is absent because `ls foo && echo yes` was
# blocked and printed nothing. State plainly that nothing executed and that the
# empty output is not a finding. The literal "BLOCKED:" must stay in the
# preamble: the test runner asserts it on every block outcome.
block() {
  {
    printf 'BLOCKED: this command did NOT run and produced NO output.\n'
    printf 'Do not treat the empty result as a finding — it is not "file missing",\n'
    printf '"no match", or "not installed". Only the command form was rejected, not\n'
    printf 'your question. Reformulate as below and retry.\n\n'
    cat
  } >&2
  exit 2
}

# Read stdin once so we can distinguish a parse failure from a payload that
# simply lacks the expected fields.
input=$(cat)

# Tool guard. PreToolUse hooks fire for every tool, but this hook only knows
# about Bash command syntax. If tool_name is present and not Bash, no-op.
# tool_name absent → assume Bash (backward-compat for older payload shapes).
tool_name=$(printf '%s' "$input" | jq -r '.tool_name // ""' 2>/dev/null || true)
if [ -n "$tool_name" ] && [ "$tool_name" != "Bash" ]; then
  exit 0
fi

# Malformed JSON → fail-closed (rc=2). Missing .tool_input.command → // ""
# yields an empty cmd; we proceed to the schema-drift tripwire below.
if ! cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""' 2>/dev/null); then
  printf 'BLOCKED: hook received malformed JSON on stdin.\n' >&2
  exit 2
fi

# Schema-drift tripwire: warn only when .tool_input.command is missing/null
# (suggesting the upstream payload shape changed) AND the JSON has other
# top-level data (so a payload of `{}` or `null` does not warn). An explicit
# empty-string command is legitimate — no warning.
if [ -z "$cmd" ]; then
  if printf '%s' "$input" | jq -e '.tool_input.command == null and (keys | length) > 0' >/dev/null 2>&1; then
    printf 'WARNING: block-quoted-flags hook extracted empty command from non-trivial JSON (possible schema drift).\n' >&2
  fi
  exit 0
fi

# Normalize whitespace before any matching: real newlines (from JSON \n) and
# non-breaking space (U+00A0 = c2 a0) are not in [[:space:]] under LC_ALL=C, so
# without this step a multiline case statement would bypass B9's anchors.
cmd_norm=$(printf '%s' "$cmd" | tr '\n\r\t' '   ' | sed $'s/\xc2\xa0/ /g')

# Strip ASCII single- and double-quoted regions for B9, so a literal keyword
# sequence inside a quoted string (`var='case x in a) y;; esac'`) does not
# false-block.
stripped=$(printf '%s' "$cmd_norm" | sed -e "s/'[^']*'//g" -e 's/"[^"]*"//g')

# B5: ANSI-C string literal `$'...'`. Trivial detection: $ immediately followed
# by '. Positional refs ($1, $2) and "$VAR" are unaffected — they don't have
# `'` directly after the `$`.
if printf '%s' "$cmd_norm" | grep -Eq -- $'\\$\''; then
  block <<'EOF'
ANSI-C quoted string ($'...') triggers the "ansi_c_string" prompt.
Reformulate: use a heredoc, or printf with a literal newline in the format
string — plain ASCII, no $'...'.
EOF
fi

# B9: case statement. `case ... in ... esac`. Anchored by whitespace-or-start
# on the left and whitespace/`;`/end on the right so substrings like `esac`
# inside longer words are not matched.
if printf '%s' "$stripped" | grep -Eq -- '(^|[[:space:]])case[[:space:]].*[[:space:]]in([[:space:]]|;).*[[:space:]]esac([[:space:]]|;|$)'; then
  block <<'EOF'
case construct triggers the "case_statement" prompt.
Reformulate: use if/elif (no longer blocked), run each branch as a separate
Bash tool call, or move the dispatch into a small script file invoked by a
single command.
EOF
fi

exit 0
