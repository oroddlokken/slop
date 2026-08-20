# Changelog

## 2026-08-14

- Made the self-verification lens direction-dependent on the target model: where
  the model already checks its own work, a named soft-check *is* the finding;
  where it skips the check, absence is. Naming how to verify — the command, the
  file to diff against — always stays, since the model cannot guess it. Step 1
  now asks which model the prompt runs on.

## 2026-08-09

- Added the count-versus-enumeration check to the weak-language lens: "five
  tools available" above six definitions. Both halves sit in the prompt, so the
  audit counts the list, and recommends dropping the number rather than
  correcting it.

## 2026-08-03

- Pinned the spawn contract — `run_in_background: false`, no `name:` — and made
  the findings go into the reply verbatim.

## 2026-07-30

- Added the prose-tics lens: copulative avoidance, negative parallelism, rule of
  three, uniform rhythm, participle tails, elegant variation, editorial filler,
  chat residue, promotional register, plus mechanical greps for curly quotes and
  tool artifacts (`oaicite`, `utm_source=chatgpt.com`). It ranks below
  contradictions and platitudes, requires a cluster rather than a single hit,
  and never speculates about authorship.
- Capped the report at 20 findings and batched systemic patterns into one row
  with a count — forty rules sharing an opening formula is one finding.
- Added the what-not-to-flag list to weak language: a hedge carrying a real
  condition is a scoped rule, and a definite claim is a commitment.

## 2026-07-03

- Split the `.claude/agents/*.md` boundary: the prompt prose is this skill's,
  the frontmatter `description` and tool scoping are `audit-agent-docs`'.
- Added input delimiting to the framing lens — user input, retrieved documents,
  examples and schemas wrapped in semantic tags.
- Added over-hardening as a finding: hardening every rule is bloat, and the
  signal is lost.

## 2026-04-22

- Replaced the parallel fan-out with a single agent applying every selected
  lens in one pass. The target is one small artifact, so per-agent startup and
  coordination dominated the cost.
- Added the rule-hardening lens with the harvest procedures for each of its
  three defenses, and rewrote the pink-elephant exception with its own
  rationalization table and red flags.
- Added the in-scope/out-of-scope statement with the verbatim redirect for a
  CLAUDE.md target, the agent's clarification policy and escalation conditions,
  the false-positive filters, and the severity scale.

## 2026-04-21

- Removed the injection-resilience lens the day it was added: token-level
  defenses are not a security boundary, and the fix belongs at the architecture
  layer.
- Added the skill: `SKILL.md` and `audit-agent.md`, auditing a general agent's
  prompt through 20 lenses.
