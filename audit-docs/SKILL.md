---
name: audit-docs
description: "Audit agent-facing documentation (CLAUDE.md, AGENTS.md, copilot-instructions.md) for redundancies, contradictions, gaps, and misplaced content. Supports Claude Code, OpenAI Codex, and GitHub Copilot. Use when the user wants to review or improve their agent instructions."
---

# Audit Docs

Spin up parallel sub-agents to audit agent-facing documentation from multiple critical angles, then distill findings into concrete proposed edits.

## Key Principle

This is documentation **for AI agents**, not humans. Agents can read source code. Do NOT flag things an agent could derive by reading the codebase (function signatures, file structure, fixture details, config options, CSS conventions, etc.). Focus only on:

- **Redundancies** that waste tokens and risk contradictions
- **Contradictions** between files
- **Behavioral rules** that can't be derived from code (don't-do-X rules, non-obvious consequences)
- **Information in the wrong file** (behavioral rules in architecture docs, architecture in behavioral docs)
- **Genuinely missing context** that agents repeatedly get wrong and can't figure out from code alone

## Lenses

Each lens is a sub-agent with a specific critical angle. The user can run all or pick specific ones.

### Core Lenses (default)

1. **Redundancy** — Find duplicated information across files. For each: cite both locations, classify as exact/paraphrase/partial, recommend which location is canonical.

2. **Contradictions** — Find conflicting instructions, inconsistent terminology, garbled text. Pay special attention to **cross-tool contradictions** when a project has instructions for multiple tools (e.g., CLAUDE.md says "use pytest" but .cursorrules says "use unittest"). For each: quote both passages, explain the conflict, recommend which version wins.

3. **Gaps** — Find genuinely missing information that agents need and can't derive from code. Focus on: non-obvious consequences (e.g. "missing X causes startup failure"), behavioral rules, workflow steps that are implied but not stated. Skip anything an agent can learn by reading source files.

4. **Actionability** — Find vague, weak, or unenforceable instructions. Flag these specific anti-patterns:

   **Framing principle**: Positive directives outperform negative prohibitions. LLMs attend to what you mention — saying "NEVER use X" activates X in the model's attention, making it *more* likely (the "Pink Elephant" effect, documented in arxiv 2402.07896, 2503.22395). Anthropic's own docs say: "Tell Claude what to do instead of what not to do." Rewrite rules as positive directives with reasoning wherever possible.

   - **Negative framing → positive rewrite**: "NEVER close issues without user approval" → "Wait for explicit user approval before closing any issue." "Do NOT combine these into one question" → "Always ask these as separate questions." "Don't use `any` type" → "Use interfaces and type guards for all function parameters." The only exception: keep NEVER/DO NOT for truly catastrophic, irreversible actions (force-push, deleting production data) where the shock value is warranted.
   - **Negative-only rules**: "don't do X" / "never do X" without stating what to do instead. Every prohibition MUST include the positive alternative — what the agent should do in that situation. A rule that only says "no" leaves the agent guessing.
   - **Missing reasoning**: Rules without a "why" are weaker. Agents generalize from explanations — "TTS engines cannot pronounce ellipses, so use complete sentences" is more robust than "NEVER use ellipses" because the agent can apply the principle to novel situations.
   - **Weak modals**: "should", "consider", "try to", "ideally", "prefer to" — rewrite as clear positive directives. If it's truly optional, say so explicitly ("MAY ... but only when ...").
   - **Weasel phrases**: "use appropriate...", "if it works", "when relevant", "as needed", "if possible", "usually", "sometimes", "typically", "generally", "normally", "occasionally", "frequently" — these give agents an escape hatch from every rule. Rewrite with concrete conditions.
   - **Unmeasurable quality**: "write clean code", "keep it simple", "use best practices", "be careful with" — agents can't evaluate these. Replace with specific, checkable criteria or delete.
   - **Aggressive emphasis**: "CRITICAL!", "YOU MUST", "NEVER EVER", "ABSOLUTELY DO NOT" — calm, direct instructions perform better on modern Claude models. Reserve emphasis (caps, bold) for the 2-3 most important rules; overuse dilutes all of them.
   - For each: quote the instruction, explain why it's weak, propose a concrete rewrite as a positive directive with reasoning.

5. **Information Architecture** — Check if content is in the right file. Behavioral instructions belong in CLAUDE.md, system design in architecture docs, DB conventions in DB docs. Flag misplaced content and propose where it should move.

6. **Structure** — Quantitative and architectural checks:
   - **Token budget**: Count lines per file. Warn at >200 lines, critical at >300. Estimate token count (chars / 4). CLAUDE.md loads every session, so every line costs tokens on every message. Keeping it lean directly improves instruction adherence — research shows compliance degrades as instruction count grows.
   - **Progressive disclosure via `@` imports**: CLAUDE.md can reference other files with `@path/to/file` lines. These are inlined at load time. Flag monolithic CLAUDE.md files that could split sections into separate files loaded via `@` imports — this keeps the root file scannable and lets sections be reused or conditionally loaded.
   - **Path-scoped rules via `.claude/rules/`**: Claude Code supports `.claude/rules/*.md` files with `paths:` frontmatter — these rules only load when working on files matching the specified globs. Example:
     ```markdown
     # .claude/rules/api-testing.md
     ---
     paths:
       - src/api/**
       - tests/api/**
     ---
     Use integration tests with a real database for API routes.
     ```
     Flag instructions in CLAUDE.md that only apply to specific directories (e.g., "when working in `src/api/`...") — these waste tokens in every session and should be `.claude/rules/` files instead.
   - **Skills boundary**: Claude Code skills (`.claude/skills/*/SKILL.md`) only load when invoked by the user. Flag domain knowledge in CLAUDE.md that loads every session but is only relevant sometimes — these should be skills instead.
   - **Broken `@` imports**: Verify that all `@path/to/file` references in CLAUDE.md actually resolve to existing files.
   - **Lost in the middle**: In documents >= 20 lines, check if critical rules are buried in the 40-60% zone of the file. LLMs pay more attention to the beginning and end of long documents (Liu et al., 2023). Recommend moving critical rules to the top or bottom.
   - **README duplication**: Compare CLAUDE.md content against adjacent README.md files. Flag high overlap — README content is for humans and wastes agent tokens when duplicated into CLAUDE.md.

7. **Hygiene** — Catch quality and safety issues:
   - **Secrets**: Scan for API keys, connection strings, tokens, credentials, passwords in any doc file.
   - **Self-evident instructions**: Flag platitudes and instructions that add zero information. Examples: "write clean code", "follow best practices", "handle errors appropriately", "use meaningful variable names", "write tests for your code", "ensure code quality". These waste tokens and dilute real rules. Also flag standard language conventions Claude already knows (e.g., "use camelCase in JavaScript", "add type hints in Python" — unless the project deliberately deviates from convention).
   - **Hook-enforceable rules**: Claude Code supports hooks — shell commands that run automatically before/after tool calls (e.g., run `eslint --fix` after every file edit, run `pytest` after writes to `tests/`). Identify linting, formatting, or procedural rules stated as prose in CLAUDE.md that would be more reliable as hooks. Prose rules depend on the LLM remembering; hooks enforce deterministically. For each, recommend the prose rule be removed from CLAUDE.md and suggest what kind of hook would replace it (do not generate the hook config — just describe the intent, e.g., "run formatter after file writes" or "lint check before commit").
   - **Stale instructions**: Cross-reference documented commands, paths, and patterns against the actual codebase to find instructions that no longer match reality.
   - **Rules maintenance gap**: If the project uses `.claude/rules/` files, check whether CLAUDE.md instructs the agent to keep them up to date as the codebase evolves (e.g., "Update `.claude/rules/` files when refactoring changes the conventions they describe"). Without this, rules files become stale as code moves or patterns change, and the agent won't know it's responsible for maintaining them.

8. **Guardrails** — Audit explicit prohibitions and safety boundaries:
   - Are critical safety boundaries stated explicitly, or just implied? (e.g., destructive operations, external API calls, data mutations)
   - **Prefer positive framing**: Most guardrails work better as positive directives. "Wait for user confirmation before closing issues" beats "NEVER close issues without approval." Reserve NEVER/DO NOT only for catastrophic, irreversible actions (force-push to main, dropping tables, deleting production data) where the shock value is warranted.
   - Are guardrails specific and unambiguous? Flag vague ones like "be careful with...", "avoid if possible", "try not to" — these are suggestions, not boundaries. Rewrite as concrete positive directives with scope.
   - Are there destructive or irreversible actions the agent could take that lack explicit boundaries? (Consider: deleting data, force-pushing, modifying shared state, sending external messages)
   - Do guardrails include reasoning? Rules with a **why** are more robust — agents generalize from explanations to novel situations instead of following the letter while violating the spirit.
   - Are there contradictions between guardrails and other instructions? (e.g., "wait for approval before modifying X" but a workflow step says "update X automatically")

9. **Cold Start** — Pretend to be a fresh agent with zero context. What assumptions does the documentation make that would confuse a first-time reader? Skip things derivable from code.

10. **Domain: {area}** — Deep-dive gap analysis for a specific domain (e.g., "database", "frontend", "pipeline", "testing"). Reads both docs AND relevant source code to find where the docs mislead or where non-obvious patterns aren't captured.

11. **Agent Quality** — Audit `.claude/agents/` definitions:
    - Missing or vague `description` field (Claude uses this to decide when to delegate — must be specific)
    - Overly broad tool access (should restrict to minimum needed via `tools`/`disallowedTools`)
    - Agents trying to do too many things (should be focused on one task)
    - Contradictions between agent instructions and CLAUDE.md rules

## Workflow

### Step 1: Determine Target

ALWAYS ask the user before proceeding — do not assume defaults or skip this step:
- **Path**: Which files/directories to audit? (suggest: the project root — discovery will find CLAUDE.md files, agent_docs/, etc. automatically)
- **Scope**: Ask the user to pick one:
  - `standard` (recommended) — runs the 8 core checks: duplicated info, conflicting instructions, missing context, vague rules, misplaced content, file size/structure issues, secrets/stale content, and guardrails/prohibitions
  - `full` — everything above plus: cold-start readability, a domain deep-dive (ask which area), and agent definition quality checks
  - Or the user can name specific areas if they know what they want (e.g., "just check for contradictions and stale content")

Present this as a simple choice — do NOT list lens numbers or internal names. If the user says "full", ask which domain area to deep-dive (e.g., database, frontend, testing).

Wait for the user's response before moving to Step 2.

### Step 2: Discover Documentation Files

Use the user's target path as the **project root** for all resolution.

**Scope boundary**: Only discover and audit files that exist on disk within the project root. Ignore everything outside it — global configs (`~/.claude/CLAUDE.md`, `~/.codex/instructions.md`), user home directories, and any content from the conversation context that was injected by Claude Code's own config loading (e.g., `@RTK.md` from a global CLAUDE.md). If you see references to files outside the project root, skip them entirely.

**2a. Find all agent instruction files across tools:**

| Tool | Glob patterns (all relative to project root) |
|------|----------------------------------------------|
| Claude Code | `**/CLAUDE.md`, `.claude/rules/*.md`, `.claude/agents/*.md`, `.claude/skills/*/SKILL.md`, `.claude/commands/*.md` |
| OpenAI Codex | `**/AGENTS.md`, `.codex/config.json` |
| GitHub Copilot | `.github/copilot-instructions.md`, `.github/copilot/**/*.md` |

Only scan for tools that have files present — skip silently if a tool's patterns match nothing.

**2b. Resolve `@` imports (recursive, max 5 hops):**
- Scan each discovered `.md` file for lines matching `@path/to/file` (a line whose meaningful content is an `@`-prefixed path)
- `@` paths are **relative to the directory containing the file that references them** (e.g., if `CLAUDE.md` contains `@agent_docs/architecture.md`, resolve as `<project_root>/agent_docs/architecture.md`)
- Follow imports recursively — imported files may contain their own `@` references. Stop at 5 hops deep to avoid cycles.
- If an `@` path does not resolve to an existing file, record it as a broken import (fed to the Structure lens)

**2c. Scan additional locations:**
- All `.md` files in directories named `agent_docs/`, `docs/`, or similar under the project root

**2d. Deduplicate:** Files found via multiple paths (e.g., both globbing and `@` import) should only be included once.

**2e. Report discovered tools:** Before launching lenses, list which tools' instruction files were found (e.g., "Found instructions for: Claude Code, Cursor, Codex"). This helps the Contradictions lens — cross-tool conflicts are common when the same project has instructions for multiple tools.

Read all discovered files and pass their contents (with their paths relative to project root) to each lens agent.

### Step 3: Launch Agents

Launch selected lens agents **in parallel** using the Agent tool. Each agent receives:
- The full content of all documentation files (with filenames)
- Its specific lens instructions (from the Lenses section above)
- The key principle (agent docs, not human docs — skip code-derivable stuff)

For domain lens (#7): also instruct the agent to scan relevant source directories and compare patterns found in code vs what's documented.

Use `subagent_type: "Explore"` for all agents so they can read source files if needed.

### Step 4: Distill

After all agents complete, analyze the combined output:

1. **Deduplicate**: Multiple lenses often flag the same issue from different angles. Merge these, noting which lenses flagged it.

2. **Classify** each finding:
   - **Remove**: Content that should be deleted (redundancy, outdated info)
   - **Move**: Content in the wrong file
   - **Rewrite**: Vague or contradictory instructions that need fixing
   - **Add**: Genuinely missing information

3. **Propose concrete edits**: For each finding, specify the exact file, what to change, and the proposed new text. Group by file.

4. Output as:

```
## Audit Results

### File: {filename}

#### {Remove|Move|Rewrite|Add}: {title}
**Flagged by**: {lens names}
**Current** (lines N-M):
> {quoted text}
**Proposed**:
> {new text or "delete" or "move to {target file}"}
**Why**: {one line}

---

### Summary
- {N} redundancies to remove
- {N} contradictions to fix
- {N} rewrites for clarity
- {N} items to add
- {N} items to relocate
- {N} guardrail issues (missing, vague, or contradicted prohibitions)
- {N} structural issues (token budget, progressive disclosure, rules boundary)
- {N} hygiene issues (secrets, self-evident rules, hook-enforceable rules, stale content)
```

5. After outputting, ask the user: "Want me to apply these changes?"

## Rules

- **Always run selected lenses in parallel** — never sequentially
- **Each agent audits independently** — don't share findings between them
- **Distill runs after all agents complete**
- **Propose edits, don't auto-apply** — the user decides what to change
- **Be aggressive about filtering out code-derivable stuff** — if an agent can `cat` a file to learn something, it doesn't need to be documented
- **Respect the doc hierarchy**: CLAUDE.md = behavioral rules; architecture/system docs = what the system is; DB docs = DB conventions. Don't suggest documenting things that belong in a different layer.
