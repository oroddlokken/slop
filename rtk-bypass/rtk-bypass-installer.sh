#!/bin/bash
# rtk-bypass — manage rtk rewrite bypasses for Claude Code hooks.
#
# Installs a hook at ~/.claude/hooks/rtk-bypass.sh that wraps rtk-rewrite.sh.
# Bypassed commands run directly; everything else delegates to rtk-rewrite.
# Survives rtk updates since rtk only overwrites rtk-rewrite.sh.
#
# Bypass list stored in ~/.claude/rtk-bypass.conf (one command per line).

set -euo pipefail

SETTINGS="$HOME/.claude/settings.json"
HOOKS_DIR="$HOME/.claude/hooks"
INSTALLED_HOOK="$HOOKS_DIR/rtk-bypass.sh"
BYPASS_CONF="$HOME/.claude/rtk-bypass.conf"
RTK_REWRITE="$HOOKS_DIR/rtk-rewrite.sh"

usage() {
  cat <<EOF
Usage: $(basename "$0") <command> [args]

Commands:
  status              Show installation status and bypassed commands
  install             Install the bypass hook (requires rtk hooks already set up)
  uninstall           Remove bypass hook, restore rtk-rewrite
  disable <command>   Disable rtk rewriting for a command (e.g. curl, wget)
  enable <command>    Re-enable rtk rewriting for a command
EOF
  exit 1
}

# --- Hook generation ---

generate_hook() {
  cat > "$INSTALLED_HOOK" <<'HOOK'
#!/bin/bash
# rtk-bypass hook — installed by rtk-bypass-installer.sh. Do not edit.
# Bypasses rtk rewriting for commands listed in ~/.claude/rtk-bypass.conf.

RTK_REWRITE="$HOME/.claude/hooks/rtk-rewrite.sh"
BYPASS_CONF="$HOME/.claude/rtk-bypass.conf"

INPUT=$(cat) || exit 0
CMD=$(printf '%s\n' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0

[ -z "$CMD" ] && exit 0

# Strip leading env var assignments, get first word, then basename for path commands
MATCH_CMD=$(printf '%s' "$CMD" | sed -E 's/^([A-Za-z_][A-Za-z0-9_]*=[^ ]* +)*//')
FIRST_WORD=${MATCH_CMD%% *}
FIRST_WORD=$(basename "$FIRST_WORD")

# Check if this command is bypassed
if [[ -f "$BYPASS_CONF" ]] && grep -qxF "$FIRST_WORD" "$BYPASS_CONF" 2>/dev/null; then
  exit 0
fi

# Delegate to rtk-rewrite
if [[ -x "$RTK_REWRITE" ]]; then
  printf '%s\n' "$INPUT" | "$RTK_REWRITE"
else
  exit 0
fi
HOOK
  chmod +x "$INSTALLED_HOOK"
}

# --- Commands ---

cmd_status() {
  echo "rtk-bypass status"
  echo "================="

  # Installation
  if [[ -f "$INSTALLED_HOOK" ]] && grep -q "rtk-bypass hook" "$INSTALLED_HOOK" 2>/dev/null; then
    # Check settings.json points to us
    if jq -e --arg cmd "$INSTALLED_HOOK" '
      .hooks.PreToolUse // [] | any(.hooks[]?.command == $cmd)
    ' "$SETTINGS" >/dev/null 2>&1; then
      echo "Status:   installed"
    else
      echo "Status:   file exists but NOT in settings.json"
    fi
  else
    echo "Status:   not installed"
  fi

  echo "Hook:     $INSTALLED_HOOK"
  echo "Config:   $BYPASS_CONF"
  echo "Wraps:    $RTK_REWRITE"

  # Bypass list
  if [[ -f "$BYPASS_CONF" ]] && [[ -s "$BYPASS_CONF" ]]; then
    echo "Bypassed: $(paste -sd', ' "$BYPASS_CONF")"
  else
    echo "Bypassed: (none)"
  fi
}

cmd_install() {
  if [[ ! -f "$SETTINGS" ]]; then
    echo "Error: $SETTINGS not found" >&2
    exit 1
  fi

  # Check rtk hooks exist
  HAS_HOOKS=$(jq -e '.hooks.PreToolUse // empty | length > 0' "$SETTINGS" 2>/dev/null || echo "false")
  if [[ "$HAS_HOOKS" == "false" ]]; then
    echo "No PreToolUse hooks found in settings.json."
    echo "Run: rtk init --global --auto-patch"
    echo "Then re-run this installer."
    exit 1
  fi

  # Generate hook
  mkdir -p "$HOOKS_DIR"
  generate_hook

  # Seed default bypass list if empty
  if [[ ! -f "$BYPASS_CONF" ]] || [[ ! -s "$BYPASS_CONF" ]]; then
    echo "curl" > "$BYPASS_CONF"
    echo "Created $BYPASS_CONF with default: curl"
  fi

  # Replace rtk-rewrite with rtk-bypass in settings.json
  jq --arg cmd "$INSTALLED_HOOK" '
    .hooks.PreToolUse = [
      (.hooks.PreToolUse // [] | .[] | select(
        (.hooks // []) | all((.command // "") | test("rtk-rewrite|rtk-bypass") | not)
      )),
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": $cmd }]
      }
    ]
  ' "$SETTINGS" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"

  echo "Installed. Bypassing: $(paste -sd', ' "$BYPASS_CONF")"
}

cmd_uninstall() {
  if [[ ! -f "$SETTINGS" ]]; then
    echo "Error: $SETTINGS not found" >&2
    exit 1
  fi

  # Remove hook file
  rm -f "$INSTALLED_HOOK"

  # Replace rtk-bypass with rtk-rewrite in settings.json
  if [[ -x "$RTK_REWRITE" ]]; then
    jq --arg old "$INSTALLED_HOOK" --arg new "$RTK_REWRITE" '
      .hooks.PreToolUse = [
        (.hooks.PreToolUse // [] | .[] | select(
          (.hooks // []) | all((.command // "") != $old)
        )),
        {
          "matcher": "Bash",
          "hooks": [{ "type": "command", "command": $new }]
        }
      ]
    ' "$SETTINGS" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"
    echo "Uninstalled. Restored rtk-rewrite as hook."
    echo "Note: $BYPASS_CONF preserved (delete manually if unwanted)."
  else
    jq --arg cmd "$INSTALLED_HOOK" '
      .hooks.PreToolUse = [
        .hooks.PreToolUse // [] | .[] | select(
          (.hooks // []) | all((.command // "") != $cmd)
        )
      ]
    ' "$SETTINGS" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"
    echo "Uninstalled. No rtk-rewrite found to restore."
    echo "Note: $BYPASS_CONF preserved (delete manually if unwanted)."
  fi
}

cmd_disable() {
  local cmd="$1"
  if [[ "$cmd" =~ [[:space:]] || -z "$cmd" ]]; then
    echo "Error: '$cmd' is not a valid command name (no spaces allowed)" >&2
    exit 1
  fi
  if [[ -f "$BYPASS_CONF" ]] && grep -qxF "$cmd" "$BYPASS_CONF" 2>/dev/null; then
    echo "rtk already disabled for '$cmd'"
    return
  fi
  echo "$cmd" >> "$BYPASS_CONF"
  echo "Disabled rtk for '$cmd'"
}

cmd_enable() {
  local cmd="$1"
  if [[ ! -f "$BYPASS_CONF" ]] || ! grep -qxF "$cmd" "$BYPASS_CONF" 2>/dev/null; then
    echo "rtk already enabled for '$cmd'"
    return
  fi
  grep -vxF "$cmd" "$BYPASS_CONF" > "$BYPASS_CONF.tmp" && mv "$BYPASS_CONF.tmp" "$BYPASS_CONF"
  echo "Re-enabled rtk for '$cmd'"
}

# --- Main ---

case "${1:-}" in
  -h|--help) usage ;;
  status)    cmd_status ;;
  install)   cmd_install ;;
  uninstall) cmd_uninstall ;;
  disable)
    [[ -z "${2:-}" ]] && { echo "Usage: $(basename "$0") disable <command>" >&2; exit 1; }
    cmd_disable "$2"
    ;;
  enable)
    [[ -z "${2:-}" ]] && { echo "Usage: $(basename "$0") enable <command>" >&2; exit 1; }
    cmd_enable "$2"
    ;;
  *) usage ;;
esac
