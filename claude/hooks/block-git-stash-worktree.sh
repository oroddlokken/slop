#!/usr/bin/env bash
set -euo pipefail
# Block mutating git stash/worktree on every surface that reaches them: Bash
# `git stash|worktree`, Agent(isolation:"worktree"), and the same request inside
# a Workflow script. Allow read-only: stash list/show, worktree list.
# The EnterWorktree/ExitWorktree tools are denied in settings.json instead.
# Both default to 0 (blocking). Set ALLOW_WORKTREES=1 or ALLOW_STASH=1 to allow.
ALLOW_WORKTREES="${ALLOW_WORKTREES:-0}"
ALLOW_STASH="${ALLOW_STASH:-0}"

input=$(cat)
# Unreadable payload falls through to exit 0 — fail open, as before.
get() { jq -r "$1 // empty" <<<"$input" 2>/dev/null || true; }
decide() {
  jq -nc --arg d "$1" --arg r "${2-}" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:$d,permissionDecisionReason:$r}}'
  exit 0
}

# Reads the Bash command on stdin, prints one "<subcommand>\t<next word>" line
# per *executed* git invocation. Matching the raw command text instead denies
# `git commit -m "...git stash..."`, where the words are message data and no
# subcommand ever runs. So walk the string the way a shell does: quotes and
# heredoc bodies are data, `; && || | ( )` start a new command, `$(…)`, backticks
# and `sh -c` payloads are commands in their own right, and `sudo`/`timeout`/
# `xargs` pass command position through to what follows them.
read -r -d '' GIT_INVOCATIONS <<'PERL' || true
use strict;
use warnings;

my @found;
# git global options that swallow the following word, so the subcommand is not
# mistaken for an option value (`git -C /tmp/repo stash`).
my %GITVAL = map { $_ => 1 } qw(
  -c -C --git-dir --work-tree --namespace --exec-path --attr-source
  --super-prefix --config-env
);
# After these, the next word is still the start of a command.
my %KEYWORD = map { $_ => 1 } qw(
  if then else elif fi while until do done for select in case esac function ! time
);
my %PREFIX = map { $_ => 1 } qw(
  sudo doas env nice ionice nohup stdbuf timeout xargs command builtin exec
);
my %PREFIXVAL = map { $_ => 1 } qw(
  -u -g -U -n -P -I -d -s -a -E -c -o -e --user --group --unset
);

# A heredoc body is data, never a command. Drop it before anything else looks
# at the string. `<<<` here-strings are not heredocs and must survive.
sub strip_heredocs {
  my ($s) = @_;
  return $s unless $s =~ /<</;
  my @out;
  my @pending;
  for my $ln (split /\n/, $s, -1) {
    if (@pending) {
      shift @pending if $ln =~ /^\s*\Q$pending[0]\E\s*$/;
      next;
    }
    push @out, $ln;
    while ($ln =~ /<<-?\s*(?:'([^']+)'|"([^"]+)"|([A-Za-z_][A-Za-z0-9_]*))/g) {
      push @pending, defined $1 ? $1 : defined $2 ? $2 : $3;
    }
  }
  return join "\n", @out;
}

# Index of the ")" closing the "(" at $open, honouring nesting and quotes.
sub match_paren {
  my ($s, $open) = @_;
  my $depth = 0;
  my $i = $open;
  my $n = length $s;
  my $sq = 0;
  my $dq = 0;
  while ($i < $n) {
    my $c = substr($s, $i, 1);
    if ($sq) { $sq = 0 if $c eq "'"; $i++; next; }
    if ($c eq "\\") { $i += 2; next; }
    if ($c eq "'" && !$dq) { $sq = 1; $i++; next; }
    if ($c eq '"') { $dq = !$dq; $i++; next; }
    if (!$dq) {
      $depth++ if $c eq '(';
      if ($c eq ')') { $depth--; return $i if $depth == 0; }
    }
    $i++;
  }
  return undef;
}

# Scan $(…) and `…` as commands of their own, then blank them out so the outer
# tokenizer sees only the surrounding text.
sub lift_substitutions {
  my ($s, $d) = @_;
  my $out = '';
  my $i = 0;
  my $n = length $s;
  my $sq = 0;
  my $dq = 0;
  while ($i < $n) {
    my $c = substr($s, $i, 1);
    if ($sq) { $sq = 0 if $c eq "'"; $out .= $c; $i++; next; }
    if ($c eq "\\") { $out .= substr($s, $i, 2); $i += 2; next; }
    if ($c eq "'" && !$dq) { $sq = 1; $out .= $c; $i++; next; }
    if ($c eq '"') { $dq = !$dq; $out .= $c; $i++; next; }
    if ($c eq '$' && substr($s, $i + 1, 1) eq '(') {
      my $j = match_paren($s, $i + 1);
      if (defined $j) {
        scan(substr($s, $i + 2, $j - $i - 2), $d + 1);
        $out .= ' ' x ($j - $i + 1);
        $i = $j + 1;
        next;
      }
    }
    if ($c eq '`') {
      my $j = index($s, '`', $i + 1);
      if ($j >= 0) {
        scan(substr($s, $i + 1, $j - $i - 1), $d + 1);
        $out .= ' ' x ($j - $i + 1);
        $i = $j + 1;
        next;
      }
    }
    $out .= $c;
    $i++;
  }
  return $out;
}

# Words with quoting resolved, plus "op" markers wherever a new command starts.
sub tokenize {
  my ($s) = @_;
  my @res;
  my $cur = '';
  my $has = 0;
  my $i = 0;
  my $n = length $s;
  my $flush = sub {
    if ($has) { push @res, { type => 'w', t => $cur }; $cur = ''; $has = 0; }
  };
  while ($i < $n) {
    my $c = substr($s, $i, 1);
    if ($c eq "\\") { $cur .= substr($s, $i + 1, 1); $has = 1; $i += 2; next; }
    if ($c eq "'") {
      my $j = index($s, "'", $i + 1);
      $j = $n if $j < 0;
      $cur .= substr($s, $i + 1, $j - $i - 1);
      $has = 1;
      $i = $j + 1;
      next;
    }
    if ($c eq '"') {
      my $j = $i + 1;
      while ($j < $n) {
        my $e = substr($s, $j, 1);
        if ($e eq "\\") { $cur .= substr($s, $j + 1, 1); $j += 2; next; }
        last if $e eq '"';
        $cur .= $e;
        $j++;
      }
      $has = 1;
      $i = $j + 1;
      next;
    }
    if ($c =~ /[ \t\r]/)      { $flush->(); $i++; next; }
    if ($c =~ /[\n;&|(){}]/)  { $flush->(); push @res, { type => 'op' }; $i++; next; }
    if ($c =~ /[<>]/)         { $flush->(); $i++; next; }
    $cur .= $c;
    $has = 1;
    $i++;
  }
  $flush->();
  return \@res;
}

# $w->[$i] is `git`. Record the subcommand and the word after it, and return the
# index to resume from.
sub git_call {
  my ($w, $i) = @_;
  my $j = $i + 1;
  while ($j < @$w && $w->[$j]{type} eq 'w' && $w->[$j]{t} =~ /^-/) {
    my $opt = $w->[$j]{t};
    my $name = $opt;
    $name =~ s/=.*//;
    $j++;
    $j++ if $GITVAL{$name} && $opt !~ /=/ && $j < @$w && $w->[$j]{type} eq 'w';
  }
  return $j if $j >= @$w || $w->[$j]{type} ne 'w';
  my $next = ($j + 1 < @$w && $w->[$j + 1]{type} eq 'w') ? $w->[$j + 1]{t} : '';
  push @found, "$w->[$j]{t}\t$next";
  return $j + 1;
}

# `sh -c '…'` and `eval …` carry a command inside an argument: rescan it.
sub shell_call {
  my ($w, $i, $d, $base) = @_;
  my $j = $i + 1;
  if ($base eq 'eval') {
    my @parts;
    while ($j < @$w && $w->[$j]{type} eq 'w') { push @parts, $w->[$j]{t}; $j++; }
    scan(join(' ', @parts), $d + 1) if @parts;
    return;
  }
  while ($j < @$w && $w->[$j]{type} eq 'w') {
    if ($w->[$j]{t} =~ /^-[A-Za-z]*c$/) {
      scan($w->[$j + 1]{t}, $d + 1) if $j + 1 < @$w && $w->[$j + 1]{type} eq 'w';
      return;
    }
    $j++;
  }
}

sub walk {
  my ($w, $d) = @_;
  my $cmdpos = 1;
  my $i = 0;
  while ($i < @$w) {
    if ($w->[$i]{type} eq 'op') { $cmdpos = 1; $i++; next; }
    unless ($cmdpos) { $i++; next; }
    my $t = $w->[$i]{t};
    if ($t =~ /^[A-Za-z_][A-Za-z0-9_]*=/) { $i++; next; }
    my $base = $t;
    $base =~ s{^.*/}{};
    if ($KEYWORD{$base}) { $i++; next; }
    if ($base eq 'git') { $i = git_call($w, $i); $cmdpos = 0; next; }
    if ($base eq 'eval' || $base =~ /^(?:ba|z|k|da|a)?sh$/) {
      shell_call($w, $i, $d, $base);
      $cmdpos = 0;
      $i++;
      next;
    }
    if ($PREFIX{$base}) {
      $i++;
      while ($i < @$w && $w->[$i]{type} eq 'w') {
        my $a = $w->[$i]{t};
        if ($a =~ /^-/) {
          my $name = $a;
          $name =~ s/=.*//;
          $i++;
          $i++ if $PREFIXVAL{$name} && $a !~ /=/ && $i < @$w && $w->[$i]{type} eq 'w';
          next;
        }
        last unless $a =~ /^\d+(?:\.\d+)?[smhd]?$/ || $a =~ /^[A-Za-z_][A-Za-z0-9_]*=/;
        $i++;
      }
      next;
    }
    $cmdpos = 0;
    $i++;
  }
}

sub scan {
  my ($s, $d) = @_;
  return if $d > 6 || !defined $s || $s eq '';
  walk(tokenize(lift_substitutions(strip_heredocs($s), $d)), $d);
}

my $src = do { local $/; <STDIN> };
scan(defined $src ? $src : '', 0);
my %seen;
for my $f (@found) { print "$f\n" unless $seen{$f}++; }
exit 0;
PERL

case "$(get .tool_name)" in
  Bash)
    cmd=$(get .tool_input.command)
    # No perl: fall back to a bare mention of the subcommand anywhere in the
    # text. That over-blocks badly, but the failure direction is the safe one.
    if ! invocations=$(printf '%s' "$cmd" | perl -e "$GIT_INVOCATIONS" 2>/dev/null); then
      invocations=$(grep -oE '\b(stash|worktree)([[:space:]]+[a-z]+)?' <<<"$cmd" |
        tr -s '[:space:]' '\t' || true)
    fi
    # subcommand : read-only pattern : override. The block rule below states
    # itself once; adding a subcommand means adding a line here.
    saw_readonly=0
    while IFS=$'\t' read -r sub arg; do
      [ -n "$sub" ] || continue
      for rule in "stash:^(list|show)$:$ALLOW_STASH" "worktree:^list$:$ALLOW_WORKTREES"; do
        [ "${rule%%:*}" = "$sub" ] || continue
        rest=${rule#*:}
        if [ "${rest##*:}" = "1" ] || grep -qE "${rest%:*}" <<<"$arg"; then
          saw_readonly=1
          continue 2
        fi
        decide deny "git $sub (mutating) is not allowed"
      done
    done <<<"$invocations"
    if [ "$saw_readonly" = "1" ]; then
      decide allow
    fi
    ;;
  Agent|Task)
    if [ "$ALLOW_WORKTREES" = "0" ] && [ "$(get .tool_input.isolation)" = "worktree" ]; then
      decide deny 'Agent isolation:"worktree" is not allowed. Spawn the agent without isolation.'
    fi
    ;;
  Workflow)
    if [ "$ALLOW_WORKTREES" = "0" ] &&
       grep -qE "isolation[[:space:]]*:[[:space:]]*['\"]worktree['\"]" <<<"$(get .tool_input.script)"; then
      decide deny 'Workflow script requests isolation:"worktree". Remove it and re-run.'
    fi
    ;;
esac
exit 0
