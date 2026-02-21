#!/usr/bin/env bash
# Claude Code status line — inspired by Starship prompt config
# Receives JSON via stdin, outputs a formatted status line to stdout.
#
# Toggle sections via environment variables (1=enabled, 0=disabled):
#   CLAUDE_STATUSLINE_HOSTNAME  — green hostname
#   CLAUDE_STATUSLINE_DIR       — blue project directory
#   CLAUDE_STATUSLINE_GIT       — branch + indicators
#   CLAUDE_STATUSLINE_DOGCAT    — dcat issue tracker counts
#   CLAUDE_STATUSLINE_CHANGES   — lines added/removed
#   CLAUDE_STATUSLINE_SESSION   — model, context window %
#   CLAUDE_STATUSLINE_USAGE     — Claude usage (session/week %)
#   CLAUDE_STATUSLINE_COST      — session cost

# --- Config defaults ---
: "${CLAUDE_STATUSLINE_HOSTNAME:=0}"
: "${CLAUDE_STATUSLINE_DIR:=1}"
: "${CLAUDE_STATUSLINE_GIT:=1}"
: "${CLAUDE_STATUSLINE_DOGCAT:=1}"
: "${CLAUDE_STATUSLINE_CHANGES:=1}"
: "${CLAUDE_STATUSLINE_SESSION:=1}"
: "${CLAUDE_STATUSLINE_USAGE:=1}"
: "${CLAUDE_STATUSLINE_COST:=1}"

# --- Input parsing ---

# Read JSON from stdin.
read_input() {
  input=$(cat)
}

# Extract fields from JSON into global variables.
parse_json() {
  cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
  model=$(echo "$input" | jq -r '.model.display_name // empty')
  used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
  cost=$(echo "$input" | jq -r '.cost.total_cost_usd // empty')
  ctx_size=$(echo "$input" | jq -r '.context_window.context_window_size // empty')
  lines_added=$(echo "$input" | jq -r '.cost.total_lines_added // empty')
  lines_removed=$(echo "$input" | jq -r '.cost.total_lines_removed // empty')
  host=$(hostname -s)
  # Show repo-name/subdir when inside a git repo, otherwise just the basename.
  local repo_root
  repo_root=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null)
  if [ -n "$repo_root" ]; then
    local repo_name rel_path
    repo_name=$(basename "$repo_root")
    rel_path="${cwd#"$repo_root"}"
    dir="${repo_name}${rel_path}"
  else
    dir=$(basename "$cwd")
  fi

  if [ "$CLAUDE_STATUSLINE_GIT" != "0" ]; then
    git_status=$(git -C "$cwd" --no-optional-locks status --porcelain=v1 -b 2>/dev/null)
    branch=$(echo "$git_status" | head -1 | sed 's/^## //;s/\.\.\..*//;s/ \[.*//')
    stash_list=$(git -C "$cwd" --no-optional-locks stash list 2>/dev/null)
  fi
}

# --- Section renderers ---

# Green hostname (e.g. "macbook").
render_hostname() {
  [ "$CLAUDE_STATUSLINE_HOSTNAME" = "0" ] && return
  printf '\033[0;32m%s\033[0m' "$host"
}

# Blue project directory basename (e.g. "my-project").
render_dir() {
  [ "$CLAUDE_STATUSLINE_DIR" = "0" ] && return
  printf '\033[0;34m%s\033[0m' "$dir"
}

# Git branch with status indicators:
#   = merge conflicts   ⇡N ahead   ⇣N behind   ⇕⇡N⇣M diverged
#   $ stashed   + staged   » renamed   ✘ deleted   ! modified   ? untracked
render_git() {
  [ "$CLAUDE_STATUSLINE_GIT" = "0" ] && return
  [ -z "$branch" ] && return

  local indicators=""
  local branch_line files
  branch_line=$(echo "$git_status" | head -1)
  files=$(echo "$git_status" | tail -n +2)

  # = merge conflicts (UU, AA, DD, AU, UA, DU, UD)
  echo "$files" | grep -q '^[UD][UD]\|^AA' && indicators="${indicators}$(printf '\033[0;31m=\033[0m')"

  # ahead/behind/diverged
  local ahead=0 behind=0
  case "$branch_line" in
    *\[ahead\ *behind\ *) ahead=$(echo "$branch_line" | sed 's/.*ahead \([0-9]*\).*/\1/'); behind=$(echo "$branch_line" | sed 's/.*behind \([0-9]*\).*/\1/') ;;
    *\[ahead\ *)           ahead=$(echo "$branch_line" | sed 's/.*ahead \([0-9]*\).*/\1/') ;;
    *\[behind\ *)          behind=$(echo "$branch_line" | sed 's/.*behind \([0-9]*\).*/\1/') ;;
  esac
  if [ "$ahead" -gt 0 ] && [ "$behind" -gt 0 ]; then
    indicators="${indicators}$(printf '\033[0;33m⇕⇡%s⇣%s\033[0m' "$ahead" "$behind")"
  elif [ "$ahead" -gt 0 ]; then
    indicators="${indicators}$(printf '\033[0;32m⇡%s\033[0m' "$ahead")"
  elif [ "$behind" -gt 0 ]; then
    indicators="${indicators}$(printf '\033[0;31m⇣%s\033[0m' "$behind")"
  fi

  # $ stashed
  [ -n "$stash_list" ] && indicators="${indicators}$(printf '\033[0;35m$\033[0m')"
  # + staged (first char is M, A, R, C, D but not U or ?)
  echo "$files" | grep -q '^[MARCD]' && indicators="${indicators}$(printf '\033[0;32m+\033[0m')"
  # » renamed
  echo "$files" | grep -q '^R' && indicators="${indicators}$(printf '\033[0;33m»\033[0m')"
  # ✘ deleted
  echo "$files" | grep -q '^D' && indicators="${indicators}$(printf '\033[0;31m✘\033[0m')"
  # ! modified (unstaged)
  echo "$files" | grep -q '^.[MD]' && indicators="${indicators}$(printf '\033[0;31m!\033[0m')"
  # ? untracked
  echo "$files" | grep -q '^??' && indicators="${indicators}$(printf '\033[0;37m?\033[0m')"

  if [ -n "$indicators" ]; then
    printf '\033[0;33m%s\033[0m[%s]' "$branch" "$indicators"
  else
    printf '\033[0;33m%s\033[0m' "$branch"
  fi
}

# Resolve dcat: PATH, local dcat.py, or ~/git/dogcat/dcat.py.
# Mirrors the zsh dcat() function resolution logic.
_find_dcat() {
  if command -v dcat >/dev/null 2>&1; then
    echo "dcat"
  elif [ -f "$cwd/dcat.py" ]; then
    echo "uv run $cwd/dcat.py"
  elif [ -f "$HOME/git/dogcat/dcat.py" ]; then
    echo "uv run --project $HOME/git/dogcat $HOME/git/dogcat/dcat.py"
  fi
}

# dcat issue tracker — shows in-progress and in-review counts.
render_dogcat() {
  [ "$CLAUDE_STATUSLINE_DOGCAT" = "0" ] && return
  [ -z "$cwd" ] && return

  local dcat_cmd dcat_json
  dcat_cmd=$(_find_dcat)
  [ -z "$dcat_cmd" ] && return
  dcat_json=$($dcat_cmd status --json --dogcats-dir "$cwd/.dogcats" 2>/dev/null)
  [ -z "$dcat_json" ] && return

  local in_progress in_review dcat_parts=""
  in_progress=$(echo "$dcat_json" | jq -r '.by_status.in_progress // 0')
  in_review=$(echo "$dcat_json" | jq -r '.by_status.in_review // 0')

  [ "$in_progress" -gt 0 ] || [ "$in_review" -gt 0 ] || return
  [ "$in_progress" -gt 0 ] && dcat_parts="${dcat_parts}$(printf '\033[0;33m◐ %s\033[0m' "$in_progress")"
  [ "$in_review" -gt 0 ] && dcat_parts="${dcat_parts}$(printf '\033[0;36m?%s\033[0m' "$in_review")"
  printf 'dc[%s]' "$dcat_parts"
}

# Lines added/removed: [+N -M].
render_changes() {
  [ "$CLAUDE_STATUSLINE_CHANGES" = "0" ] && return
  [ -z "$lines_added" ] && [ -z "$lines_removed" ] && return
  printf '[\033[0;32m+%s\033[0m \033[0;31m-%s\033[0m]' "${lines_added:-0}" "${lines_removed:-0}"
}

# Claude usage: session %, session reset countdown, week %.
render_usage() {
  [ "$CLAUDE_STATUSLINE_USAGE" = "0" ] && return

  local script_dir usage_json py
  script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # get_usage.py needs Python 3.10+; find one explicitly to avoid macOS system 3.9
  py=python3
  for p in python3.14 python3.13 python3.12 python3.11 python3.10; do
    command -v "$p" >/dev/null 2>&1 && py="$p" && break
  done
  usage_json=$("$py" "$script_dir/get_usage.py" 2>/dev/null)
  [ -z "$usage_json" ] && return

  local s_pct w_pct s_reset parts=""
  s_pct=$(echo "$usage_json" | jq -r '.session_percent // empty')
  w_pct=$(echo "$usage_json" | jq -r '.week_percent // empty')
  s_reset=$(echo "$usage_json" | jq -r '.session_reset // empty')

  [ -z "$s_pct" ] && [ -z "$w_pct" ] && return

  # Session percent
  if [ -n "$s_pct" ]; then
    parts="$(printf '\033[0;36mS:\033[0;93m%s%%\033[0m' "$s_pct")"
  fi

  # Session reset countdown
  if [ -n "$s_reset" ]; then
    local now_epoch reset_epoch diff_s hours mins countdown
    now_epoch=$(date +%s)
    # macOS date -j for ISO parsing
    reset_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$s_reset" +%s 2>/dev/null) \
      || reset_epoch=$(date -d "$s_reset" +%s 2>/dev/null)
    if [ -n "$reset_epoch" ] && [ "$reset_epoch" -gt "$now_epoch" ]; then
      diff_s=$(( reset_epoch - now_epoch ))
      hours=$(( diff_s / 3600 ))
      mins=$(( (diff_s % 3600) / 60 ))
      if [ "$hours" -gt 0 ]; then
        countdown="${hours}h${mins}m"
      else
        countdown="${mins}m"
      fi
      parts="${parts} $(printf '\033[0;36mR:\033[0;90m%s\033[0m' "$countdown")"
    fi
  fi

  # Week percent
  if [ -n "$w_pct" ]; then
    parts="${parts} $(printf '\033[0;36mW:\033[0;93m%s%%\033[0m' "$w_pct")"
  fi

  printf '\033[0;34m[\033[0m%s\033[0;34m]\033[0m' "$parts"
}

# Session info: model name, context window %.
render_session() {
  [ "$CLAUDE_STATUSLINE_SESSION" = "0" ] && return
  local session_parts=""

  [ -n "$model" ] && session_parts="$(printf '\033[0;36m%s\033[0m' "$model")"

  if [ -n "$used" ]; then
    local used_int ctx used_k total_k
    used_int=${used%.*}
    if [ -n "$ctx_size" ] && [ "$ctx_size" -gt 0 ] 2>/dev/null; then
      used_k=$(( (ctx_size * used_int + 99999) / 100000 ))
      total_k=$(( (ctx_size + 999) / 1000 ))
    fi
    local color
    if [ "$used_int" -ge 80 ] 2>/dev/null; then
      color="31"
    elif [ "$used_int" -ge 65 ] 2>/dev/null; then
      color="33"
    else
      color=""
    fi
    if [ -n "$used_k" ]; then
      if [ -n "$color" ]; then
        ctx="$(printf '\033[0;90m%sk/%sk(\033[0;%sm%s%%\033[0;90m)\033[0m' "$used_k" "$total_k" "$color" "$used_int")"
      else
        ctx="$(printf '\033[0;90m%sk/%sk(%s%%)\033[0m' "$used_k" "$total_k" "$used_int")"
      fi
    else
      if [ -n "$color" ]; then
        ctx="$(printf '\033[0;%sm%s%%\033[0m' "$color" "$used_int")"
      else
        ctx="$(printf '\033[0;90m%s%%\033[0m' "$used_int")"
      fi
    fi
    session_parts="${session_parts}, ${ctx}"
  fi

  printf '\033[0;34m[\033[0m%s\033[0;34m]\033[0m' "$session_parts"
}

# Session cost: [$N.NN].
render_cost() {
  [ "$CLAUDE_STATUSLINE_COST" = "0" ] && return
  [ -z "$cost" ] && return
  local cost_fmt
  cost_fmt=$(printf '%.2f' "$cost")
  printf '\033[0;34m[\033[0m\033[0;35m$%s\033[0m\033[0;34m]\033[0m' "$cost_fmt"
}

# --- Main ---

main() {
  read_input "$@"
  parse_json

  local parts="" section

  section=$(render_hostname)
  [ -n "$section" ] && parts="$section"

  section=$(render_dir)
  [ -n "$section" ] && parts="${parts:+$parts }$section"

  section=$(render_git)
  [ -n "$section" ] && parts="${parts:+$parts }$section"

  section=$(render_dogcat)
  [ -n "$section" ] && parts="${parts:+$parts }$section"

  section=$(render_changes)
  [ -n "$section" ] && parts="${parts:+$parts }$section"

  section=$(render_session)
  parts="${parts:+$parts }$section"

  section=$(render_usage)
  [ -n "$section" ] && parts="${parts:+$parts }$section"

  section=$(render_cost)
  [ -n "$section" ] && parts="${parts:+$parts }$section"

  printf '%b\n' "$parts"
}

main "$@"
