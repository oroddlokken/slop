#!/usr/bin/env zsh
# Claude Code Usage — terminal dashboard similar to the /usage screen.
# Calls get_usage.py and renders progress bars with reset countdowns.
#
# Usage: ccu.zsh [--force|-f]

set -euo pipefail

SETUP_DIR="${SETUP_DIR:-$HOME/git/macsetup}"

# --- Fetch usage JSON ---

local force_flag=""
[[ "${1:-}" == "--force" || "${1:-}" == "-f" ]] && force_flag="--force"

local py=python3
local p
for p in python3.14 python3.13 python3.12 python3.11 python3.10; do
  command -v "$p" >/dev/null 2>&1 && py="$p" && break
done

local script_dir="${0:a:h}"
local usage_script="$script_dir/get_usage.py"
if [[ ! -f "$usage_script" ]]; then
  usage_script="$SETUP_DIR/claude/get_usage.py"
fi

local json
json=$("$py" "$usage_script" $force_flag 2>/dev/null) || true
if [[ -z "$json" ]]; then
  echo "Failed to fetch usage data" >&2
  exit 1
fi

# --- Parse fields ---

local s_pct=$(echo "$json" | jq -r '.session_percent // empty')
local w_pct=$(echo "$json" | jq -r '.week_percent // empty')
local so_pct=$(echo "$json" | jq -r '.sonnet_percent // empty')
local e_pct=$(echo "$json" | jq -r '.extra_percent // empty')
local e_spent=$(echo "$json" | jq -r '.extra_spent // empty')
local e_limit=$(echo "$json" | jq -r '.extra_limit // empty')
local s_reset=$(echo "$json" | jq -r '.session_reset // empty')
local w_reset=$(echo "$json" | jq -r '.week_reset // empty')
local so_reset=$(echo "$json" | jq -r '.sonnet_reset // empty')
local e_reset=$(echo "$json" | jq -r '.extra_reset // empty')
local last_updated=$(echo "$json" | jq -r '.last_updated // empty')

if [[ -z "$s_pct" && -z "$w_pct" ]]; then
  echo "No usage data available" >&2
  exit 1
fi

# --- Timezone ---

local tz_name
tz_name=$(readlink /etc/localtime 2>/dev/null | sed 's|.*/zoneinfo/||' || true)
[[ -z "$tz_name" ]] && tz_name=$(date +%Z)

# --- Helpers ---

# Progress bar: green filled, dark gray empty.
ccu_bar() {
  local pct=${1:-0} width=50
  local filled=$(( pct * width / 100 ))
  local empty=$(( width - filled ))
  printf '\033[0;32m'
  (( filled > 0 )) && printf '%.0s█' {1..$filled}
  printf '\033[0;90m'
  (( empty > 0 )) && printf '%.0s█' {1..$empty}
  printf '\033[0m'
}

# Compact countdown from epoch delta: "1d2h", "3h14m", "42m".
ccu_countdown() {
  local epoch=$1
  [[ -z "$epoch" ]] && return 0
  local now_epoch diff_s
  now_epoch=$(date +%s)
  diff_s=$(( epoch - now_epoch ))
  (( diff_s <= 0 )) && return 0

  local d=$(( diff_s / 86400 ))
  local h=$(( (diff_s % 86400) / 3600 ))
  local m=$(( (diff_s % 3600) / 60 ))

  local out=""
  if (( d > 0 )); then
    out="${d} day"
    (( d != 1 )) && out="${out}s"
    if (( h > 0 )); then
      out="${out} and ${h} hour"
      (( h != 1 )) && out="${out}s"
    fi
  elif (( h > 0 )); then
    out="${h} hour"
    (( h != 1 )) && out="${out}s"
    if (( m > 0 )); then
      out="${out} and ${m} minute"
      (( m != 1 )) && out="${out}s"
    fi
  else
    out="${m} minute"
    (( m != 1 )) && out="${out}s"
  fi
  printf '%s' "$out"
}

# Format ISO reset time: "Resets in 1d2h4m at 2am (Europe/Oslo)".
ccu_reset_fmt() {
  local iso=$1
  [[ -z "$iso" ]] && return 0
  local clean
  clean=$(echo "$iso" | sed 's/\.[0-9]*//;s/[+-][0-9][0-9]:[0-9][0-9]$//')
  local epoch
  epoch=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$clean" +%s 2>/dev/null) || return 0
  [[ -z "$epoch" ]] && return 0

  local countdown
  countdown=$(ccu_countdown "$epoch")

  local raw_h raw_m month_day
  raw_h=$(date -j -f "%s" "$epoch" "+%H" 2>/dev/null)
  raw_m=$(date -j -f "%s" "$epoch" "+%M" 2>/dev/null)
  month_day=$(date -j -f "%s" "$epoch" "+%b %-d" 2>/dev/null)

  # Midnight means no specific time was parsed — show date only.
  if [[ "$raw_h" == "00" && "$raw_m" == "00" ]]; then
    if [[ -n "$countdown" ]]; then
      printf 'Resets in %s on %s (%s)' "$countdown" "$month_day" "$tz_name"
    else
      printf 'Resets %s (%s)' "$month_day" "$tz_name"
    fi
    return
  fi

  local h ampm today tomorrow time_str
  h=$(date -j -f "%s" "$epoch" "+%-I" 2>/dev/null)
  ampm=$(date -j -f "%s" "$epoch" "+%p" 2>/dev/null | tr '[:upper:]' '[:lower:]')
  today=$(date "+%b %-d")
  tomorrow=$(date -v+1d "+%b %-d" 2>/dev/null || true)

  if [[ "$raw_m" == "00" ]]; then
    time_str="${h}${ampm}"
  else
    time_str="${h}:${raw_m}${ampm}"
  fi

  local at_part
  if [[ "$month_day" == "$today" || "$month_day" == "$tomorrow" ]]; then
    at_part="at $time_str"
  else
    at_part="at $time_str on $month_day"
  fi

  if [[ -n "$countdown" ]]; then
    printf 'Resets in %s %s (%s)' "$countdown" "$at_part" "$tz_name"
  else
    printf 'Resets %s (%s)' "$at_part" "$tz_name"
  fi
}

# Render one usage section: title, bar, percentage, reset info.
ccu_section() {
  local title=$1 pct=$2 reset_iso=${3:-} extra_info=${4:-}
  [[ -z "$pct" ]] && return 0
  printf '\033[1;32m%s\033[0m\n' "$title"
  ccu_bar "$pct"
  printf '  \033[1m%d%% used\033[0m\n' "$pct"
  [[ -n "$extra_info" ]] && echo "$extra_info"
  local reset_line
  reset_line=$(ccu_reset_fmt "$reset_iso")
  [[ -n "$reset_line" ]] && echo "$reset_line"
}

# --- Render ---

if [[ -n "$last_updated" ]]; then
  local clean_lu
  clean_lu=$(echo "$last_updated" | sed 's/\.[0-9]*//;s/[+-][0-9][0-9]:[0-9][0-9]$//')
  local lu_epoch
  lu_epoch=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$clean_lu" +%s 2>/dev/null) || true
  if [[ -n "$lu_epoch" ]]; then
    local ago_s=$(( $(date +%s) - lu_epoch ))
    local ago_m=$(( ago_s / 60 ))
    if (( ago_m <= 0 )); then
      printf '\033[0;90mLast fetched just now\033[0m\n'
    elif (( ago_m == 1 )); then
      printf '\033[0;90mLast fetched 1 minute ago\033[0m\n'
    else
      printf '\033[0;90mLast fetched %d minutes ago\033[0m\n' "$ago_m"
    fi
  fi
fi
echo
ccu_section "Current session" "$s_pct" "$s_reset"
if [[ -n "$w_pct" ]]; then
  echo
  ccu_section "Current week (all models)" "$w_pct" "$w_reset"
fi
if [[ -n "$so_pct" ]]; then
  echo
  ccu_section "Current week (Sonnet only)" "$so_pct" "$so_reset"
fi
if [[ -n "$e_pct" ]]; then
  echo
  local extra_info=""
  if [[ -n "$e_spent" && -n "$e_limit" ]]; then
    extra_info=$(printf '$%.2f / $%.2f spent' "$e_spent" "$e_limit")
  fi
  ccu_section "Extra usage" "$e_pct" "$e_reset" "$extra_info"
fi
echo
