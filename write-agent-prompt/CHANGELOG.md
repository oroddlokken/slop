# Changelog

## 2026-08-14

- Made the "don't restate defaults" rule name its moving target: the default set
  shifts with each model generation, so it gets rechecked at every migration.
  Self-verification is the current example — frontier models check their own
  work, and instructing it again costs tokens for nothing.
- Told the writer to check the target model before adding self-check
  instructions: for Claude Opus 5 and its generation, delete them rather than
  reword, since they add cost and can trigger over-verification.
- Marked the pre-ship checklist as the writer's own; none of it ships inside the
  prompt.

## 2026-08-10

- Extended the skill to the files a Claude Code harness loads as instruction —
  `SKILL.md`, `output-styles/*.md`, `.claude/commands/`, `.claude/agents/` —
  and added the trigger phrases for them. The frontmatter `description` decides
  whether the body is ever injected, so both are written under these rules.

## 2026-07-30

- Added the adjective test: "the lock is held across the retry" is a fact, "the
  lock is critical" is a mood, and moods carry nothing the agent can apply.
- Added the one-name-per-thing rule — rotating "payload", "request body" and
  "incoming data" breaks the mapping to the field the agent must emit. Padding
  rules to equal length loses the caveat that resisted the mold.
- Added the polish-below-correctness check: verify a rule is still true before
  rewording it.

## 2026-07-03

- Dropped the model version from the reasoning-model caveats: "Claude with
  extended thinking" rather than a pinned release.

## 2026-04-22

- Added the skill-priority order against `write-agent-docs` and `claude-api`,
  and a glossary for Iron Law, baseline run, rationalization table, Red Flags,
  long-context deployment and scripted redirect.
- Added the three hardening moves, the harvest loop that supplies them
  (baseline, record, write, pressure-test, refactor), and the counterweight:
  when *not* to harden, since hardening everything makes hardening invisible.
- Turned rule economy into an Iron Law with its own loophole list, excuse table
  and red flags, and mirrored critical rules at the tail for long-context
  deployments.
- Replaced "never ask more than one question" with an ordering rule: resolve the
  highest-impact ambiguity first, circle back later, and re-read the user's
  message before asking anything.
- Added worked refusal and clarification examples, the tool-boundary
  disambiguation pattern with a tie-breaker, this skill's own persona as a
  worked example, and a pre-ship self-check list.
- Reframed example drift: when an example and a rule disagree, the example shows
  what the prompt actually produces, so fix the rule.

## 2026-04-21

- Added internal consistency (persona versus output shape, scope versus tools,
  clarification policy versus output shape), cold-start readability, and the
  reasoning-model caveats — no "think step by step", minimal few-shot, constrain
  only the final answer.
- Added the redundancy rule and XML structuring for anything the model must
  parse, and sent strict formats to structured-output schemas instead of prose.
- Added and then removed a prompt-injection section the same day: token-level
  defenses are not a security boundary, and the advice belonged at the
  architecture layer rather than in prompt prose.

## 2026-04-11

- Added the skill: one `SKILL.md` on the prose that defines a general agent —
  persona, scope, clarification policy, output shape, uncertainty, escalation,
  tool descriptions and examples.
