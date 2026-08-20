#!/bin/bash
set -euo pipefail

# Fixtures are built inline, the idiom in ../block-git-stash-tests/run-tests.sh:
# every payload is one file path plus a few lines of text, so a file per case
# would bury the thing under test.

DIR="$(cd "$(dirname "$0")" && pwd)"
HOOK="${HOOK_PATH:-$DIR/../lint-slop.py}"

if ! command -v jq >/dev/null 2>&1; then
  echo "FATAL: jq not found on PATH (required to build the payloads)" >&2
  exit 1
fi

if [ ! -r "$HOOK" ]; then
  echo "hook not readable: $HOOK" >&2
  exit 1
fi

pass=0
fail=0

# check expect payload_json label
#   expect: "block" (exit 2) or "pass" (exit 0)
check() {
  local expect="$1" payload="$2" label="$3"
  local rc got

  rc=0
  printf '%s' "$payload" | python3 "$HOOK" >/dev/null 2>&1 || rc=$?
  case "$rc" in
    0) got=pass ;;
    2) got=block ;;
    *) got="exit$rc" ;;
  esac

  local status=PASS
  [ "$expect" = "$got" ] || status=FAIL
  if [ "$status" = "PASS" ]; then pass=$((pass + 1)); else fail=$((fail + 1)); fi
  printf '%-4s %-52s expect=%-5s got=%s\n' "$status" "$label" "$expect" "$got"
}

# Command substitution, not a pipe: `check` must run in this shell or its
# pass/fail counters (and the exit status built from them) are lost.
write_case() {
  check "$1" "$(jq -nc --arg p "$2" --arg c "$3" \
    '{tool_name:"Write",tool_input:{file_path:$p,content:$c}}')" "$4"
}

edit_case() {
  check "$1" "$(jq -nc --arg p "$2" --arg s "$3" \
    '{tool_name:"Edit",tool_input:{file_path:$p,new_string:$s}}')" "$4"
}

# -- Doc files: every line is prose --
write_case block /tmp/p/README.md 'A robust parser for the feed.' 'md: puffery blocks'
write_case block /tmp/p/notes.rst 'Simply run the migration first.'  'rst: softener blocks'
write_case block /tmp/p/notes.txt 'Note that the lock is held here.' 'txt: throat-clearing blocks'
write_case block /tmp/p/README.md 'We leverage the cache on cold start.' 'md: inflated verb blocks'
write_case block /tmp/p/README.md 'It retries twice, ensuring delivery.' 'md: participle tail blocks'
write_case block /tmp/p/README.md 'Rule 9 restored 2026-08-10 in the style.' 'md: edit annotation blocks'
write_case block /tmp/p/README.md 'The blast radius is one table.'    'md: coding-assistant tic blocks'
write_case block /tmp/p/README.md 'A powerful, crucial guarantee.'    'md: added puffery blocks'
write_case block /tmp/p/README.md 'The runner orchestrates the pool.' 'md: orchestrate blocks'
write_case block /tmp/p/README.md 'The flag unlocks the fast path.'    'md: unlock blocks'
write_case block /tmp/p/README.md 'An essential step before deploy.'   'md: essential blocks'
write_case block /tmp/p/README.md 'The cap: this moved into the style.' 'md: subject + moved blocks'
write_case block /tmp/p/notes.txt 'Keep in mind the lock is held.'     'txt: keep in mind blocks'
write_case pass  /tmp/p/README.md 'The parser moved to the new dir.'   'md: bare "moved to" passes'
write_case pass  /tmp/p/README.md 'Retries on 5xx, up to three times.' 'md: plain prose passes'
write_case pass  /tmp/p/README.md 'The key is rotated every 90 days.'  'md: everyday word passes'

# -- Negation shapes: the corrective pair, and a negation as the whole payload --
write_case block /tmp/p/README.md 'It is not a cache — it is a queue.' 'md: corrective framing, em dash blocks'
write_case block /tmp/p/README.md "This isn't the default. This is opt-in."  'md: corrective framing, two sentences blocks'
write_case block /tmp/p/README.md 'It is not a firewall, it is a route table.' 'md: corrective framing, comma blocks'
write_case block /tmp/p/README.md 'Not just the parser but the writer reads it.' 'md: not just X but Y blocks'
write_case block /tmp/p/README.md 'It retries not only on 5xx but also on 429.' 'md: not only X but also Y blocks'
write_case block /tmp/p/README.md '- Not chosen.'                       'md: bullet payload is a negation blocks'
write_case block /tmp/p/README.md 'One /32 per tier; not chosen'        'md: trailing not chosen blocks'
write_case block /tmp/p/README.md 'The tier list does not apply.'       'md: full-sentence dismissal blocks'
write_case block /tmp/p/parse.py  '# not needed'                        'py: comment payload is a negation blocks'
write_case pass  /tmp/p/README.md 'The value is not cached on the first read.' 'md: plain negation passes'
write_case pass  /tmp/p/README.md 'The parser masks rather than divides.' 'md: "rather than" passes'
write_case pass  /tmp/p/README.md 'It masks instead of dividing by two.' 'md: "instead of" passes'
write_case pass  /tmp/p/README.md 'The rule does not apply until the lock clears.' 'md: mid-sentence "does not apply" passes'
write_case pass  /tmp/p/README.md 'This is not the only reader of the file.' 'md: negation without the pair passes'
write_case pass  /tmp/p/README.md 'The check that is not run is the drift one.' 'md: mid-line negated relative clause passes'
write_case pass  /tmp/p/parse.py  '# retries are not needed above three'  'py: negation a sentence continues past passes'

# -- Code files: only comment-shaped lines --
write_case pass  /tmp/p/parse.py 'robust_parse = make_parser()'        'py: identifier passes'
write_case pass  /tmp/p/parse.py 'MSG = "simply retry"'                'py: string data passes'
write_case block /tmp/p/parse.py '# Simply retry on a 429.'            'py: comment softener blocks'
write_case block /tmp/p/app.js   '// A comprehensive rewrite.'         'js: // comment blocks'
write_case block /tmp/p/app.js   ' * Utilize the pool here.'           'js: javadoc line blocks'
write_case block /tmp/p/main.go  '/* Obviously the mutex is held. */'  'go: block comment blocks'
write_case block /tmp/p/q.sql    '-- Truly the slowest join.'          'sql: -- comment blocks'
write_case block /tmp/p/parse.py '    """Clearly the fast path."""'    'py: docstring blocks'
write_case block /tmp/p/parse.py '# entries bucket by day (vekt-52r9)' 'py: ticket id blocks'
write_case pass  /tmp/p/parse.py '# decodes utf-8 and iso-8601 stamps' 'py: utf-8 / iso-8601 pass'
write_case pass  /tmp/p/parse.py '# masks instead of dividing'         'py: earned comment passes'

# -- Written to the session, and to a plan the repo does not keep --
write_case block /tmp/p/parse.py '# retry count is three, as requested'  'py: as requested blocks'
write_case block /tmp/p/README.md 'Per your request the writer runs last.' 'md: per your request blocks'
write_case block /tmp/p/parse.py '# as we discussed, the lock is held'   'py: as we discussed blocks'
write_case block /tmp/p/app.js   '// you asked for a second retry here'  'js: you asked for blocks'
write_case block /tmp/p/parse.py '# phase 2 of the plan adds the queue'  'py: plan phase blocks'
write_case block /tmp/p/README.md 'Per the plan, the writer lands second.' 'md: per the plan blocks'
write_case pass  /tmp/p/README.md 'Returns the fields as requested by the caller.' 'md: requested by the caller passes'
write_case pass  /tmp/p/README.md 'Step 2 runs the migration.'           'md: bare step number passes'
write_case pass  /tmp/p/parse.py '# phase 2 of the handshake sends the key' 'py: phase of a protocol passes'

# -- Quoting: the word is named, not used --
write_case pass  /tmp/p/README.md 'The linter flags `robust` on sight.' 'backticked word passes'
write_case pass  /tmp/p/parse.py  '# rejects "seamless" in a comment'   'quoted word in comment passes'
write_case pass  /tmp/p/README.md '```
robust = 1
```'                                                                     'fenced block passes'

# -- Exempt paths: only the files that quote the inventory are exempt --
write_case pass  /Users/x/git/macsetup/claude/output-styles/cut-the-crap.md 'A robust check.' 'the style itself exempt'
write_case pass  /Users/x/git/macsetup/claude/skills/earn-the-line/SKILL.md 'Simply do it.'   'earn-the-line exempt'
write_case pass  /Users/x/git/macsetup/claude/skills/comment-cop/reviewers/llm-slop.md 'A seamless merge.' 'comment-cop exempt'
write_case pass  /Users/x/git/macsetup/claude/skills/write-agent-docs/SKILL.md 'A robust rule.' 'write-agent-docs exempt'
write_case pass  /Users/x/git/macsetup/claude/hooks/lint-slop.py       '# robust'        'lint-slop exempt'
write_case block /Users/x/git/macsetup/claude/skills/perf-cop/SKILL.md 'A robust check.' 'other skill not exempt'
write_case block /Users/x/git/macsetup/claude/output-styles/x.md       'Simply do it.'   'other style not exempt'
write_case block /Users/x/git/macsetup/claude/hooks/other.sh           '# Simply retry.' 'other hook not exempt'

# -- Out of scope file types are skipped entirely --
write_case pass /tmp/p/data.csv  'robust,seamless,elegant'  'csv skipped'
write_case pass /tmp/p/blob.bin  'a robust thing'           'unknown extension skipped'

# -- Edit and MultiEdit carry the added text under other keys --
edit_case  block /tmp/p/README.md 'An elegant fallback.' 'Edit: new_string scanned'
edit_case  pass  /tmp/p/README.md 'The fallback reads the cache.' 'Edit: clean new_string passes'
check block "$(jq -nc '{tool_name:"MultiEdit",tool_input:{file_path:"/tmp/p/a.md",
  edits:[{new_string:"fine line"},{new_string:"A seamless merge."}]}}')" \
  'MultiEdit: second edit scanned'
check block "$(jq -nc '{tool_name:"NotebookEdit",tool_input:{notebook_path:"/tmp/p/a.py",
  new_source:"# Obviously wrong."}}')" 'NotebookEdit: new_source scanned'

# -- The old text is not ours to judge --
check pass "$(jq -nc '{tool_name:"Edit",tool_input:{file_path:"/tmp/p/README.md",
  old_string:"A robust parser.",new_string:"A parser."}}')" 'old_string not scanned'

# -- Input handling: a payload we cannot read fails open --
check pass 'not json at all'  'malformed payload fails open'
check pass '{}'               'empty object'
check pass '[]'               'array payload'
check pass '{"tool_name":"Write"}' 'missing tool_input'
check pass '{"tool_name":"Bash","tool_input":{"command":"echo robust"}}' 'unmatched tool'

printf '\n%d passed, %d failed\n' "$pass" "$fail"
exit $fail
