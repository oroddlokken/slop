#!/usr/bin/env bash
# Seam both profiles' settings.json point at. Segment defaults live in
# statusline_command.py; per-machine CLAUDE_STATUSLINE_* overrides go here.

export CLAUDE_STATUSLINE_SCOPED_THRESHOLD="${CLAUDE_STATUSLINE_SCOPED_THRESHOLD:-0}"
export CLAUDE_STATUSLINE_SCOPED_MODE="${CLAUDE_STATUSLINE_SCOPED_MODE:-current}"

export CLAUDE_STATUSLINE_CHANGES="${CLAUDE_STATUSLINE_CHANGES:-0}"
export CLAUDE_STATUSLINE_GIT_DIFFSTAT="${CLAUDE_STATUSLINE_GIT_DIFFSTAT:-0}"
export CLAUDE_STATUSLINE_DOGCAT="${CLAUDE_STATUSLINE_DOGCAT:-0}"

export CLAUDE_STATUSLINE_BATTERY="${CLAUDE_STATUSLINE_BATTERY:-0}"
export CLAUDE_STATUSLINE_RENDER_TIME="${CLAUDE_STATUSLINE_RENDER_TIME:-0}"

# ${var%/*} leaves a slashless path untouched, where dirname would answer "."
DIR="${BASH_SOURCE[0]%/*}"
[[ "$DIR" == "${BASH_SOURCE[0]}" ]] && DIR="."
SCRIPT="$DIR/statusline_command.py"

# CPython writes and reads __pycache__ only for modules it imports, never for
# the file named on its command line: run as a script, the whole 83 KB is
# tokenized and compiled again on every render, before main() even reaches the
# fast-path check. Importing it instead caches the bytecode and leaves only
# this one-line -c string to compile. It pops the directory back off argv so
# the module still sees `-t` at sys.argv[1] the way a script invocation did.
BOOT='import sys; sys.path.insert(0, sys.argv.pop(1)); import statusline_command; statusline_command.main()'

# The uv shebang costs ~40ms of resolver per render, so resolve the script
# env's interpreter once and cache the path. Two invalidators, both by mtime:
# the script, because editing it can change its dependencies and so which
# environment answers for it, and this wrapper, because a fix to the resolution
# below only reaches a machine whose cache an earlier version already filled if
# it can throw that entry away. (-nt handles a deleted cache file too, so no
# separate existence check.)
PY_CACHE="${TMPDIR:-/tmp}/claude-statusline-python-$EUID"
PY=""
if [[ -r "$PY_CACHE" && ! "$SCRIPT" -nt "$PY_CACHE" \
      && ! "${BASH_SOURCE[0]}" -nt "$PY_CACHE" ]]; then
  PY="$(<"$PY_CACHE")"
fi
if [[ ! -x "$PY" ]]; then
  # `uv python find` only locates an interpreter — it never creates the
  # script's PEP 723 environment. This script's dependency list is empty today,
  # so a bare interpreter happens to run it, but the first dependency added
  # here would make find answer with one that cannot: executable, so the
  # shebang fallback below would not catch it, and the render would die on
  # ModuleNotFoundError. That is exactly how ccreport broke on a second
  # machine. `uv sync --script` builds the environment, which is the step
  # `uv run --script` performs on every run.
  if uv sync --script "$SCRIPT" >/dev/null 2>&1; then
    PY="$(uv python find --script "$SCRIPT" 2>/dev/null)"
    # Cached only once both halves have succeeded. A path stored after a failed
    # sync is the bare-interpreter bug, made permanent.
    [[ -x "$PY" ]] && printf '%s' "$PY" >"$PY_CACHE"
  fi
fi
if [[ ! -x "$PY" ]]; then
  # No uv, a uv too old for `sync --script`, or a sync that failed. The shebang
  # pays the resolver on every render but installs what it needs, so it works.
  exec "$SCRIPT" "$@"
fi

# The render-time segment's second figure: time the whole Python invocation
# from out here — no in-process clock can see its own startup and exit — and
# substitute the result over the token the render embeds. Exporting the token
# is also the render's go-ahead to embed it. $EPOCHREALTIME is bash 5 and has
# exactly six fractional digits, so stripping the separator (locale may make
# it a comma) gives integer microseconds; under an older bash it expands
# empty and the segment shows the in-process time alone.
#
# Timing costs the render a forked subshell, a pipe, a parent that stays
# resident and a whole-output command substitution — so the default is the
# plain exec below, and the price is paid only by someone who asked to see the
# figure. `!= 0` matches the render's own _on().
if [[ "$CLAUDE_STATUSLINE_RENDER_TIME" == 0 || -z "$EPOCHREALTIME" ]]; then
  exec "$PY" -c "$BOOT" "$DIR" "$@"
fi
export CLAUDE_STATUSLINE_TOTAL_TOKEN="__SL_TOTAL__"
t0=${EPOCHREALTIME/[.,]/}
out="$("$PY" -c "$BOOT" "$DIR" "$@")"
us=$(( ${EPOCHREALTIME/[.,]/} - t0 ))
printf -v dt '%d.%03ds' $(( us / 1000000 )) $(( us % 1000000 / 1000 ))
# An empty render (e.g. unparsable stdin) must stay empty — an empty *line*
# would render as a blank status row where no output means none at all.
[[ -n "$out" ]] && printf '%s\n' "${out//__SL_TOTAL__/$dt}"
