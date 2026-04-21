---
name: write-agent-docs
description: "Guidelines for writing and updating agent-facing documentation (CLAUDE.md, AGENTS.md, copilot-instructions.md, .claude/rules/). Load this skill when writing, editing, or updating agent instructions. Triggered by phrases like 'update CLAUDE.md', 'update agent docs', 'edit CLAUDE.md', 'add a rule', 'update copilot instructions', 'update AGENTS.md', or when you determine that agent docs need updating as part of other work."
---

# Writing Agent Docs

Follow these principles when writing or updating agent-facing documentation (CLAUDE.md, AGENTS.md, .claude/rules/, copilot-instructions.md, etc.).

## Core Principle

Agent docs are for AI agents, not humans. Agents can read source code. Only document what an agent **cannot derive** by reading the codebase:

- Behavioral rules and workflow expectations
- Non-obvious consequences ("missing X causes startup failure")
- Safety boundaries and destructive-action guardrails
- Cross-cutting conventions that aren't enforced by tooling

Skip content the agent can discover itself: function signatures, config options, standard language conventions, or anything a `cat` / `grep` would reveal. Document file structure only when it is genuinely non-obvious — a monorepo map or a surprising entry point pays for itself; a tree of `src/components/` is noise.

## Framing Rules

**Positive directives outperform negative prohibitions.** LLMs attend to what you mention — "NEVER use X" activates X in the model's attention (the "Pink Elephant" effect). Anthropic's own docs say: "Tell Claude what to do instead of what not to do."

| Instead of | Write |
|---|---|
| "NEVER close issues without user approval" | "Wait for explicit user approval before closing any issue" |
| "Don't use `any` type" | "Use interfaces and type guards for all function parameters" |
| "Do NOT combine these into one question" | "Always ask these as separate questions" |

**Exception**: Keep NEVER/DO NOT for truly catastrophic, irreversible actions (force-push to main, dropping production tables, deleting data) where the shock value is warranted.

Every prohibition must include the positive alternative — what the agent should do instead. A rule that only says "no" leaves the agent guessing.

## Include Reasoning

Rules with a "why" are stronger. Agents generalize from explanations to novel situations.

- Weak: "Use complete sentences in voice responses"
- Strong: "TTS engines cannot pronounce ellipses or markdown, so use complete sentences in voice responses"

## Enable Self-Verification

Tell the agent how to check its own work — the command to run, the file to diff against, the output to expect. Agents that can verify catch their own mistakes; agents that cannot, ship them. Anthropic's guidance flags this as one of the highest-leverage additions to CLAUDE.md.

- Name the test and lint commands, and the preview/diff variant of any destructive action (`ansible-playbook --check --diff`, `terraform plan`, `dns_records.py diff`)
- Point at a canonical example file rather than describing the pattern in prose
- For UI work, say what URL to open and what specifically to look for

## Avoid Weak Language

- **Weak modals**: "should", "consider", "try to", "ideally", "prefer to" — rewrite as clear directives. If truly optional, say so explicitly ("MAY ... but only when ...").
- **Weasel phrases**: "use appropriate...", "as needed", "if possible", "usually", "generally" — these give agents an escape hatch. Use concrete conditions instead.
- **Unmeasurable quality**: "write clean code", "use best practices", "be careful with" — agents can't evaluate these. Replace with specific, checkable criteria or delete.
- **Aggressive emphasis**: "CRITICAL!", "YOU MUST", "NEVER EVER" — calm, direct instructions perform better. Reserve emphasis for the 2-3 most important rules; overuse dilutes all of them.

## Self-Evident Instructions

Do not write platitudes that add zero information:
- "write clean code", "follow best practices", "handle errors appropriately"
- Standard language conventions Claude already knows (camelCase in JS, type hints in Python) — unless the project deliberately deviates

These waste tokens and dilute real rules.

## Token Budget

CLAUDE.md loads every session — every line costs tokens on every message. Keeping it lean improves instruction adherence (compliance degrades as instruction count grows).

- Aim for <200 lines per file. Warn at >200, critical at >300.
- Split with `@path/to/file` imports for sections that don't always apply.

## Information Architecture

Put content in the right place:

| Content type | Where it belongs |
|---|---|
| Behavioral rules, workflow expectations | CLAUDE.md |
| Rules for specific directories only | `.claude/rules/*.md` with `paths:` frontmatter |
| Domain knowledge loaded on-demand | `.claude/skills/*/SKILL.md` |
| Deterministic enforcement (format-on-save, lint-on-commit) | Hooks in `settings.json`, not prose |
| System design, architecture | Architecture docs |
| DB conventions | DB docs |

**Path-scoped rules**: Instructions that only apply to specific directories (e.g., "when working in `src/api/`...") waste tokens in every session. Use `.claude/rules/` files instead:

```markdown
# .claude/rules/api-testing.md
---
paths:
  - src/api/**
  - tests/api/**
---
Use integration tests with a real database for API routes.
```

## Lost in the Middle

LLMs pay more attention to the beginning and end of long documents. In files >= 20 lines, put critical rules at the top or bottom — not buried in the middle.

## Avoid Redundancy

State each fact once, in one canonical location. Duplicated information wastes tokens and creates contradiction risk when one copy gets updated and the other doesn't. If the same rule applies to multiple contexts, put it in the highest-level file and reference it.

## Guardrails

- State safety boundaries explicitly with scope and reasoning, so the agent can apply them to novel situations
- Frame as positive directives with scope ("Use `kubectl get/describe/logs` for cluster inspection. Present a plan and wait for approval before any resource modifications")
- Include reasoning so the agent generalizes correctly
- Consider whether a hook would enforce the rule more reliably than prose

## Cross-Tool Consistency

If the project has instructions for multiple tools (CLAUDE.md, AGENTS.md, copilot-instructions.md, .cursorrules), cross-tool contradictions produce silent bugs — each tool follows its own file, and any drift surfaces as agents making different choices in the same codebase.

Common drift patterns:
- Test framework mismatch (CLAUDE.md says pytest, AGENTS.md says unittest)
- Lint / formatter command mismatch (one file says `ruff check`, another says `flake8`)
- Safety rule mismatch (one file forbids force-push, another is silent on it)
- Workflow step mismatch (one file says "run tests before committing", another omits it)

Pick one file as the source of truth for behavioral rules and have the others forward to it or carry an identical copy. If you keep identical copies, add a pre-commit check that diffs them — the common failure mode is updating one file and forgetting the others.
