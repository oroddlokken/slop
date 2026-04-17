#!/bin/bash
# Stop hook: catches ownership-dodging and session-quitting phrases that
# violate CLAUDE.md golden rules. When triggered, blocks the assistant from
# stopping and forces it to go back and do the work properly.
#
# The assistant's message has already been shown to the user by the time this
# runs, but the assistant is forced to continue — so the correction appears
# immediately after the violation, which is visible and self-documenting.

set -euo pipefail

# Guard: jq is required for JSON parsing.
if ! command -v jq >/dev/null 2>&1; then
  echo "stop-phrase-guard: jq is required but not found on PATH" >&2
  exit 1
fi

INPUT=$(cat)

# Prevent infinite loops: if the hook already fired once this turn, let
# the assistant stop. The correction message from the first firing is
# enough — we don't want to trap the assistant in an endless cycle.
HOOK_ACTIVE=$(jq -r '.stop_hook_active // false' <<< "$INPUT")
if [[ "$HOOK_ACTIVE" == "true" ]]; then
  exit 0
fi

MESSAGE=$(jq -r '.last_assistant_message // empty' <<< "$INPUT")
if [[ -z "$MESSAGE" ]]; then
  exit 0
fi

# Each violation: "regex_pattern:::correction_rule"
# Delimiter is ::: (pipe can't be used — it appears in regex alternation).
# Patterns are extended regex, checked case-insensitively against the full
# assistant message. Ordered by specificity — longer/narrower patterns first
# within each category. First match wins.
VIOLATIONS=(
  # ── Ownership dodging ──────────────────────────────────────────────────
  # The #1 problem: dismissing failures as not-my-fault.
  # Correction varies by what the assistant actually said.

  "(is|was|are|were|seems|looks|'s) pre-existing:::You said 'pre-existing.' NOTHING IS PRE-EXISTING (CLAUDE.md golden rule). All builds and tests are green upstream. If something fails, YOUR work caused it. Investigate and fix it."

  "not (from|caused by|introduced by) my:::You blamed something outside your changes. NOTHING IS PRE-EXISTING. You own the entire codebase state in this session. Investigate the failure and fix it."

  "not my change:::You said 'not my change.' You own every change. Investigate the failure and fix it."

  "already existed before:::You said 'already existed.' NOTHING IS PRE-EXISTING. If you found it broken, fix it or explain exactly what is wrong and what the fix requires."

  "(before|prior to) my changes:::You referenced a state 'before your changes.' There is no before — you own the codebase as it is now. Investigate and fix."

  "unrelated to my changes:::You said 'unrelated.' If it is broken, fix it. If you broke it, fix it. Nothing is unrelated."

  "(this is|it's|that's) an existing (issue|bug):::You called this 'existing.' NOTHING IS PRE-EXISTING. Investigate and fix, or explain exactly what is wrong."

  "is an existing bug:::You called this an 'existing bug.' NOTHING IS PRE-EXISTING. Investigate and fix."

  # ── Known limitation dodging ───────────────────────────────────────────

  "known limitation:::You called this a 'known limitation.' NO KNOWN LIMITATIONS (CLAUDE.md golden rule). Investigate whether it is fixable. Either fix it or explain the specific technical reason it cannot be fixed right now."

  "(this is|it's|that's) a known issue([.,;]| (and|but|so|that|which)| *$):::You called this a 'known issue.' NO KNOWN LIMITATIONS. Explain the specific technical reason or fix it."

  "(as|for|leave.*as|defer.*to) future work:::You deferred this as 'future work.' NO KNOWN LIMITATIONS. Fix it now or describe exactly what the fix requires — not as a TODO, as a technical explanation."

  "left as an exercise:::NO KNOWN LIMITATIONS. Do the work."

  # ── Session-length quitting ────────────────────────────────────────────
  # All of these boil down to: the task isn't done, sessions are unlimited.

  "session (length|depth):::Sessions are unlimited (CLAUDE.md rule). If work remains, continue."

  "given the length of this:::Sessions are unlimited. The length of this session is irrelevant. Continue working."

  "continue in a new session:::There is no 'new session.' This session is unlimited. Continue working."

  "good (place|stopping point|checkpoint) (to stop|given):::The task is not done. Sessions are unlimited. Continue working."

  "(natural|logical) stopping:::The task is not done. Sessions are unlimited. Continue working."

  "(this session has gotten|session has been|conversation is getting|this is getting) long:::Sessions are unlimited. You are a machine. Continue working."

  "lengthy session:::Sessions are unlimited. Continue working."

  # ── Permission-seeking mid-task ────────────────────────────────────────
  # These fire when Claude stops to ask whether it should keep working on
  # something it was already asked to do. If the only possible answer from
  # the user is "yes, obviously" — don't ask.

  "want to continue.*or :::Do not ask. The task is not done. Continue working."

  "or save it for:::Do not ask. The task is not done. Continue working."

  "(should|shall) I (continue|proceed|keep going):::Do not ask permission to continue. The task is not done — continue working. The user will interrupt if they want you to stop."

  "would you like (me to|to) continue:::Do not ask. Continue working."

  "want me to (keep going|continue):::Do not ask. Continue working."

  # ── Deferral to imaginary future sessions ──────────────────────────────

  "save it for next time:::There is no 'next time.' This session is unlimited. Continue working."

  "(in the |^)next (session|conversation)\b:::There is no 'next session.' This session is unlimited. Continue working."

  "pick this up later:::There is no 'later.' Continue working now."

  "(we can|let's|I'll) come back to this:::You suggested deferral. There is no 'coming back.' Continue working now."

  "continue in a follow-up:::There is no 'follow-up.' Continue now."

  # ── Suggesting the user should stop ────────────────────────────────────

  "(let's|we should|I'll) pause here:::Do not suggest pausing. The task is not done. Continue working."

  "stop here for now:::Do not stop. The task is not done. Continue working."

  "wrap up for now:::Do not wrap up. The task is not done. Continue working."

  "(let's|we can|I'll) call it here:::Do not stop. Continue working."
)

# Build a combined regex for a single-pass fast-path check. The common case
# is no violations — this avoids spawning many subprocesses per stop event.
COMBINED=""
for entry in "${VIOLATIONS[@]}"; do
  pattern="${entry%%:::*}"
  if [[ -n "$COMBINED" ]]; then
    COMBINED="$COMBINED|$pattern"
  else
    COMBINED="$pattern"
  fi
done

# Fast path: single grep to check if ANY violation pattern matches.
# LC_ALL=C avoids UTF-8 multibyte overhead — all patterns are ASCII.
if ! LC_ALL=C grep -iqE "$COMBINED" <<< "$MESSAGE"; then
  # No violations — allow the assistant to stop normally.
  exit 0
fi

# A violation was detected. Walk the list to find which pattern matched
# (first match wins). This only runs on the rare violation path.
for entry in "${VIOLATIONS[@]}"; do
  pattern="${entry%%:::*}"
  correction="${entry#*:::}"
  if LC_ALL=C grep -iqE "$pattern" <<< "$MESSAGE"; then
    # Output JSON decision to stdout — Claude Code reads this and forces
    # the assistant to continue with the reason as its next instruction.
    jq -n \
      --arg reason "STOP HOOK VIOLATION: $correction" \
      '{
        decision: "block",
        reason: $reason
      }'
    exit 0
  fi
done

# Shouldn't reach here (the combined grep matched but no individual did),
# but allow stopping rather than trapping the assistant.
exit 0
