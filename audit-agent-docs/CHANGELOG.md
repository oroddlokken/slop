# Changelog

## 2026-08-14

- Renamed the agent's "Self-Verification" section to "Output Contract" and the
  skill's Step 5 to "Report Conformance". Both check the report's shape, which
  is not the same thing as an instruction to verify.

## 2026-08-12

- Dropped `disable-model-invocation: true`, so the skill can load on its own
  trigger again.

## 2026-08-09

- Added the hardcoded-count check: a number in prose mirroring a set defined
  elsewhere — files in a directory, rows in the table below, entries in
  `.claude/rules/`. The fix is deleting the number, not correcting it, since a
  corrected count drifts again on the next addition.

## 2026-08-03

- Added the spawn contract and the background-agent rules.

## 2026-07-30

- Added the prose-tics lens: mechanical greps first (curly quotes inside a
  command, unfilled placeholders, tool artifacts, chat residue), then sentence
  shapes — copulative avoidance, negative parallelism, rule of three, uniform
  rhythm, participle tails, elegant variation, promotional register, changelog
  voice. It ranks below contradictions, gaps and the stale-instruction check,
  and never launders a false claim by rewriting the prose around it.
- Carved out bullet density: dense bullets are the correct form for
  `CLAUDE.md`, `AGENTS.md` and `.claude/rules/`, so the density check applies to
  prose docs only and never proposes turning a rule list into paragraphs.
- Capped each lens at 12 findings, batched systemic patterns into one counted
  row, and replaced the bare severity list with a scale that says what each
  level means.
- Added the what-not-to-flag list to actionability: a hedge carrying a real
  condition is a scoped rule, a definite claim is a commitment.

## 2026-07-03

- Split the `.claude/agents/*.md` boundary: frontmatter and tool scoping are
  this skill's, the prompt prose belongs to `audit-agent-prompt`.
- Replaced the loose summary with a mandatory findings table sorted by file and
  line, with severity and flagging lenses per row.

## 2026-04-22

- Added the scope statement, the definitions block (`@` import,
  `.claude/rules/`, hooks, Iron Law, rationalization table, Red Flags, lens),
  and the rule-hardening lens with its selectivity warning.
- Added the code-derivable boundary table, the red flags that precede applying
  edits unasked, the anchoring loopholes an agent uses to peek at another lens,
  the worked example finding, the self-verification step, and what to do when
  the user declines the changes.

## 2026-04-21

- Split the lens list into core and full, and rewrote the rules to say why each
  holds — independent agents avoid anchoring, distill needs every finding in
  hand, misrouted findings move noise rather than reduce it.

## 2026-04-11

- Fixed `1+Parallel` to batch at most five agents, and dropped the arXiv ids
  from the pink-elephant citation.

## 2026-04-07

- Fixed the scope-boundary example to name a real global-config import.

## 2026-04-06

- Added two `.claude/rules/` checks: a `paths:` glob matching no file means the
  rule silently stopped loading, and a rules file with no `paths:` at all costs
  the same tokens as CLAUDE.md every session.

## 2026-03-30

- Extracted the agent prompt into `audit-agent.md` and added the launch-strategy
  question, replacing "always run lenses in parallel".

## 2026-03-17

- Renamed the skill from `audit-docs` to `audit-agent-docs`.
- Added the tool-restriction check: prose alone is not a security boundary, so a
  "never run `kubectl delete`" rule gets a positive rewrite and a note about
  whether any hook or deny rule backs it.

## 2026-03-16

- Added the structure, hygiene, guardrails and agent-quality lenses: token
  budget with a 200/300-line threshold, progressive disclosure through `@`
  imports, path-scoped `.claude/rules/`, the skills boundary, secrets, stale
  instructions, hook-enforceable rules and lost-in-the-middle placement.
- Added the framing principle to actionability — positive directives over
  prohibitions, with NEVER reserved for catastrophic irreversible actions — and
  the weak-modal, weasel-phrase and unmeasurable-quality patterns.
- Widened discovery beyond Claude Code to AGENTS.md and copilot-instructions.md,
  with `@` imports resolved recursively to five hops, a project-root scope
  boundary, and a report of which tools were found.

## 2026-03-15

- Added the skill as `audit-docs`: one `SKILL.md` auditing CLAUDE.md and
  `agent_docs/` for redundancy, contradictions, gaps, actionability and
  misplaced content.
