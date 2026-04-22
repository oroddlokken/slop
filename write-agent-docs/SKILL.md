---
name: write-agent-docs
description: "Guidelines for writing and updating agent-facing documentation (CLAUDE.md, AGENTS.md, copilot-instructions.md, .claude/rules/). Load this skill when writing, editing, or updating agent instructions. Triggered by phrases like 'update CLAUDE.md', 'update agent docs', 'edit CLAUDE.md', 'add a rule', 'update copilot instructions', 'update AGENTS.md', or when you determine that agent docs need updating as part of other work."
---

# Writing Agent Docs

Follow these principles when writing or updating agent-facing documentation (CLAUDE.md, AGENTS.md, .claude/rules/, copilot-instructions.md, etc.).

## Scope & Guardrails

This skill applies only to agent-facing documentation (CLAUDE.md, AGENTS.md, copilot-instructions.md, `.claude/rules/`). For requests outside that scope — code refactoring, writing tests, general review — say: *"That's outside this skill's scope. I'll handle it with base model guidance."* Then stop applying this skill.

**Do not modify docs without explicit user approval.** Present a plan (which file, which section, what change) and wait for an OK before editing. This applies even when the change looks obviously correct — CLAUDE.md edits cascade across every future session, so the user has to be the one who decides. *Red flags — stop if you catch yourself thinking:* "the user will obviously want this", "absence of 'don't' is permission", "all signals point the same way, it must be safe", "I already have a clean draft, applying is free".

## Glossary

Terms used repeatedly below. Skim once, referenced implicitly thereafter.

- **Iron Law** — an absolute no-exceptions rule paired with the specific workarounds it blocks, by name.
- **Rationalization table** — a `| Excuse | Reality |` table paired with a rule. Rows are justifications an agent produced when violating the rule — harvested from baseline runs, not invented.
- **Red Flags** — phrases an agent says right before violating a rule. Named so they become a self-check stop signal.
- **Baseline run** — running the target scenario without the rule (or deliberately weakened) so the failure has room to appear; used to harvest real rationalizations and red flags.
- **`@path/to/file` import** — a line in CLAUDE.md whose meaningful content is `@path/to/file`. Claude Code inlines the file at load time. Paths are relative to the file containing the import.
- **`.claude/rules/*.md`** — path-scoped instruction files. YAML frontmatter `paths:` (an array of globs) restricts loading to sessions touching matching files. Files without `paths:` load every session.
- **`.claude/skills/*/SKILL.md`** — skills loaded only when invoked by name or pattern, not every session.
- **Hooks** — shell commands configured in `settings.json` that run before/after tool calls. Enforce deterministically where prose only guides cooperative behavior.

## Core Principle

Agent docs are for AI agents, not humans. Agents can read source code. Only document what an agent **cannot derive** by reading the codebase:

- Behavioral rules and workflow expectations
- Non-obvious consequences ("missing X causes startup failure")
- Safety boundaries and destructive-action guardrails
- Cross-cutting conventions that aren't enforced by tooling

Skip content the agent can discover itself: function signatures, config options, standard language conventions, or anything a `cat` / `grep` would reveal. Document file structure only when it is genuinely non-obvious — a monorepo map or a surprising entry point pays for itself; a tree of `src/components/` is noise. The reason is compounding cost: CLAUDE.md loads every session, so every line of derivable content burns tokens on every message and dilutes attention to the rules that actually steer behavior.

**Loopholes this core principle blocks:**
- Don't document config options or function signatures agents will read from source anyway.
- Don't re-document language conventions Claude already knows — unless the project deliberately deviates.
- Don't describe folder structure in prose when `ls` reveals it.
- Don't add a rule "just in case" — only from an observed incident or an unmet need.

**Red flags — stop before adding these:**
- "This is best practice" → ask *which incident is this rule the memorial for?*
- "The agent should know this" → verify it can't be derived from code first.
- "Just in case the agent forgets" → if it matters that much, enforce with a hook, not prose.

## When Documentation Is Ambiguous

If a rule's placement, wording, or scope is ambiguous, ask the user rather than guess:

- Ambiguous placement: "This rule could live in CLAUDE.md or in `.claude/rules/<scope>.md`. Which location should I use?"
- Ambiguous existing doc: "Section X of CLAUDE.md isn't clear on Y. Do you want me to clarify it as [interpretation A] or [interpretation B]?"

Never silently reinterpret an existing rule while editing around it. If you can't verify a fact in the project while drafting, use the phrase: `"[Uncertain — verify with the user]"` inline rather than omitting the detail or guessing it.

## Output & Interaction

When the user asks you to update CLAUDE.md or `.claude/rules/`:

- Present a structured plan first — file, section, change type — and wait for approval.
- When applying approved changes, return the **complete updated file** (not a diff) to avoid merge conflicts in CLAUDE.md.
- Flag contradictions with existing docs as you find them and ask which version wins.
- If the file would exceed 200 lines after your change, note it and suggest consolidation or `@`-import extraction.

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

## Harden Critical Rules

For the 2-3 rules that must not be rationalized away (destructive ops, test discipline, scope control, migration safety, deployment gates), positive framing is the floor. Three further moves target how critical rules actually erode:

**Enumerate the loopholes.** An Iron Law followed by the specific workarounds it blocks, by name:

> Run the preview variant (`--check --diff` / `dns_records.py diff`) and get user approval before applying. No exceptions: run preview for every change, regardless of size; keep preview and apply as separate turns with explicit approval between them; treat each change as new — prior approval of a similar change does not carry over.

Harvest the list from incidents — each line should map to a real past slip.

**Rationalization tables** (for the one or two rules that keep breaking). Pair the rule with a two-column `| Excuse | Reality |` table, one row per observed justification — the excuse the agent actually produced, not one you imagined. For the preview-before-apply rule above, an example table:

| Excuse | Reality |
|---|---|
| "This change is too small to preview" | Preview surfaces unintended side-effects regardless of size; there is no threshold. |
| "Approval will be faster without the diff" | Approval without a diff is blind approval; include the diff always. |
| "I got approval on a similar change earlier, this one is the same" | Each change is new data; prior approval does not transfer. |
| "The preview would fail because of an unrelated pending change" | Then resolve the unrelated change first; don't apply blind around it. |

**Red Flags — self-talk as stop signal.** Name the phrases the agent says right before violating the rule ("this change is too small to preview", "I'll apply it faster without the diff"). Naming inner monologue converts it into a trigger.

Reserve all three for rules where slippage has real cost. A CLAUDE.md full of loophole enumerations becomes its own bloat — these patterns work because they're rare enough to catch the eye.

## Rules Come From Incidents, Not Imagination

Before adding a rule, ask: "What incident is this rule the memorial for?" Rules without a ghost tend toward generic best-practice — exactly the kind the agent rationalizes past first. When an agent produces a slip, capture the self-justification verbatim ("I thought the test was redundant", "the file looked safe to reformat") and feed that phrase into the next rule's loophole list or Red Flags. The rule that names the rationalization survives; the one that doesn't gets re-invented.

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

- Aim for <200 lines per file. At >200 lines, recommend splitting: move optional sections to `@`-imported files, or move path-scoped rules to `.claude/rules/*.md`. At >300 lines, refuse to add further content without a restructuring plan the user approves.
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

LLMs pay more attention to the beginning and end of long documents. In files >= 20 lines, put critical rules at the top or bottom — not buried in the middle. The effect is strongest on base-chat models; reasoning models attend to middle sections more evenly, but head-or-tail placement is still the safer default since the same doc is read by both.

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

## Source Hierarchy (this skill vs. the repo)

This skill teaches general principles; the user's existing CLAUDE.md is authoritative for their specific repo. When this skill's advice and the repo's existing docs disagree:

1. The repo's CLAUDE.md and `.claude/rules/` files win. Use this skill to refine or extend them, not to override.
2. If the repo's approach conflicts with a principle this skill teaches, name the conflict to the user and ask whether to update the repo's docs, keep the existing convention, or carve an exception. Do not silently change the repo to match the skill.
3. If the user explicitly says "follow the skill's approach" for a given change, that overrides #1 for that change only.
