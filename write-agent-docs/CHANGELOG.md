# Changelog

## 2026-08-14

- Split the self-verification section in two. What belongs in the doc is the
  affordance — the command, the file to diff against, the expected output —
  because that is environment knowledge the agent cannot guess. An instruction
  *to* verify was dropped: current models already check their work, so the line
  cost tokens and changed nothing.

## 2026-08-10

- Widened the hand-off to `write-agent-prompt` to name skill, output-style,
  slash-command and subagent files, which are prompt text rather than repo docs.

## 2026-07-30

- Added the adjective test: does the word name a fact or a mood? "Drops the
  column before the backfill runs" is checkable; "this migration is critical" is
  not.
- Added the one-name-per-thing rule — rotating "deploy script", "release tool"
  and "publish step" breaks the mapping between the doc and the command.
- Ranked polish below correctness: verify a rule still holds before rewording
  it, since a smoothly phrased stale instruction is more convincing than the
  clumsy one.

## 2026-07-03

- Pointed system-prompt, persona and tool-description work at
  `write-agent-prompt`.

## 2026-04-22

- Added the guardrails: the skill covers agent docs only, and never edits them
  without an approved plan — a CLAUDE.md edit cascades into every future
  session. Named the red flags that precede editing anyway ("the user will
  obviously want this", "absence of 'don't' is permission").
- Added the glossary — Iron Law, rationalization table, Red Flags, baseline run,
  `@path` import, `.claude/rules/`, hooks — and the three hardening moves for
  rules that keep breaking, with a worked `| Excuse | Reality |` table.
- Added "rules come from incidents, not imagination": every rule answers what
  incident it is the memorial for, and the agent's verbatim self-justification
  feeds the next rule's loophole list.
- Turned the line budget into an action: over 200 lines, recommend splitting;
  over 300, refuse further content without an approved restructuring plan.
- Added the source hierarchy — the repo's own docs win over this skill's advice,
  and a conflict is named to the user rather than silently resolved.

## 2026-04-21

- Replaced the one-line cross-tool consistency note with the four drift patterns
  that actually bite (test framework, lint command, safety rule, workflow step),
  and the fix: one file is the source of truth, and identical copies get a
  pre-commit diff.
- Softened the sourcing of the self-verification claim from "Anthropic's own
  guidance calls this the single highest-leverage thing" to "one of".

## 2026-04-11

- Added the self-verification section: name the test and lint commands, the
  preview variant of any destructive action, and a canonical example file.
- Allowed file structure back in where it is non-obvious — a monorepo map earns
  its place, a tree of `src/components/` does not.
- Sent deterministic enforcement (format-on-save, lint-on-commit) to hooks in
  `settings.json` rather than prose.

## 2026-04-04

- Added the skill: one `SKILL.md` on writing CLAUDE.md, AGENTS.md,
  copilot-instructions.md and `.claude/rules/` for agents that can already read
  the source.
