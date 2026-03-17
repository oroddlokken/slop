# Audit Docs

Audit agent-facing documentation (CLAUDE.md, AGENTS.md, copilot-instructions.md) for redundancies, contradictions, gaps, and misplaced content. Supports Claude Code, OpenAI Codex, and GitHub Copilot.

## What you get

Parallel sub-agents audit your agent instructions from multiple critical angles, then findings are deduplicated and distilled into concrete proposed edits:

- **Remove** — redundant or outdated content wasting tokens
- **Move** — content in the wrong file (behavioral rules in architecture docs, etc.)
- **Rewrite** — vague, contradictory, or weak instructions that need fixing
- **Add** — genuinely missing context agents can't derive from code

Every finding includes the exact file, line range, and proposed new text.

## Lenses

| Lens | Focus |
|------|-------|
| Redundancy | Duplicated information across files |
| Contradictions | Conflicting instructions, including cross-tool conflicts |
| Gaps | Missing context agents need and can't derive from code |
| Actionability | Vague rules, weak modals, negative framing, missing reasoning |
| Information Architecture | Content in the wrong file or layer |
| Structure | Token budget, `@` imports, `.claude/rules/` opportunities, lost-in-the-middle |
| Hygiene | Secrets, stale instructions, self-evident rules, hook-enforceable rules |
| Guardrails | Missing or vague safety boundaries for destructive actions |
| Cold Start | First-time agent confusion points |
| Domain | Deep-dive gap analysis for a specific area (DB, frontend, testing, etc.) |
| Agent Quality | Audit `.claude/agents/` definitions for scope, tools, and contradictions |

## Options

| Option | Values | Default |
|--------|--------|---------|
| Scope | `standard` (8 core lenses), `full` (all 11), or pick specific lenses | `standard` |
| Path | Which files/directories to audit | Project root |
| Domain | Area for domain deep-dive (full scope only) | Asked at runtime |

## Key principle

This audits documentation **for AI agents**, not humans. Agents can read source code. The skill aggressively filters out anything an agent could derive by reading the codebase — it only flags what genuinely needs to be written down.

## Installation

Tell your agent to read this repository and ask it to help you integrate it into your Claude Code setup as a skill.
