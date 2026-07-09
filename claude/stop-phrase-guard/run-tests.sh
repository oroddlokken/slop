#!/bin/bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
GUARD="$DIR/stop-phrase-guard.sh"
pass=0
fail=0

check() {
  local label="$1" file="$2" expect_warn="$3"
  local out rc
  out=$($GUARD < "$file" 2>&1) && rc=$? || rc=$?

  local got_warn="false"
  local detail=""
  if [ -n "$out" ] && jq -e '.systemMessage' <<< "$out" >/dev/null 2>&1; then
    got_warn="true"
    detail=$(jq -r '.systemMessage // ""' <<< "$out")
  fi

  local status reason_ok="true"
  # When warning, the message must surface the matched regex so false
  # positives can be identified and tuned.
  if [ "$got_warn" = "true" ] && ! grep -q '\[matched: ' <<< "$detail"; then
    reason_ok="false"
  fi

  if [ "$expect_warn" = "$got_warn" ] && [ "$reason_ok" = "true" ]; then
    pass=$((pass + 1))
    status="PASS"
  else
    fail=$((fail + 1))
    status="FAIL"
  fi

  printf "%-4s %-40s expect=%-5s got=%-5s %s\n" "$status" "$label" "$expect_warn" "$got_warn" "$detail"
}

# -- Original regression tests --
check "clean_message"               $DIR/test_clean.json              false
check "ownership_dodge"             $DIR/test_violation.json          true
check "stop_hook_active_still_warns" $DIR/test_loop_guard.json        true
check "session_quit_combo"          $DIR/test_session_quit.json       true
check "empty_message"               $DIR/test_empty.json              false

# -- False positive tests (should NOT block) --
check "fp:known_issue_legit"        $DIR/test_fp_known_issue_legit.json   false
check "fp:future_work_legit"        $DIR/test_fp_future_work_legit.json   false
check "fp:come_back_legit"          $DIR/test_fp_come_back_legit.json     false
check "fp:pause_legit"              $DIR/test_fp_pause_legit.json         false
check "fp:existing_issue_legit"     $DIR/test_existing_issue_legit.json   false
check "fp:existing_bug_legit"       $DIR/test_existing_bug_legit.json     false
check "fp:prioritization_legit"     $DIR/test_fp_prioritization_legit.json false
check "fp:meta_quoting_legit"       $DIR/test_fp_meta_quoting_legit.json   false
check "fp:commit_confirmation"      $DIR/test_fp_commit_confirmation_legit.json false
check "fp:push_confirmation"        $DIR/test_fp_push_confirmation_legit.json   false
check "fp:pr_confirmation"          $DIR/test_fp_pr_confirmation_legit.json     false

# -- True positive tests (SHOULD block) --
check "tp:known_issue_dodge"        $DIR/test_fp_known_issue_dodge.json   true
check "tp:future_work_dodge"        $DIR/test_fp_future_work_dodge.json   true
check "tp:come_back_dodge"          $DIR/test_fp_come_back_dodge.json     true
check "tp:pause_dodge"              $DIR/test_fp_pause_dodge.json         true
check "tp:consolidated_shall"       $DIR/test_consolidated_shall.json     true
check "tp:consolidated_should"      $DIR/test_consolidated_should.json    true
check "tp:refactor_dodge"           $DIR/test_fp_refactor_dodge.json      true

printf "\n%d passed, %d failed\n" "$pass" "$fail"
exit $fail
