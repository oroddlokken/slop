---
name: audit-agent-docs
description: "Audit agent-facing documentation (CLAUDE.md, AGENTS.md, copilot-instructions.md) for redundancies, contradictions, gaps, and misplaced content. Supports Claude Code, OpenAI Codex, and GitHub Copilot. Use when the user wants to review or improve their agent instructions."
---

# Audit Docs

Spin up parallel sub-agents to audit agent-facing documentation from multiple critical angles, then distill findings into concrete proposed edits.

**Workflow at a glance:** (1) ask the user for target path and scope *before* launching anything — layouts vary too widely to guess; (2) discover docs inside the project root; (3) launch one sub-agent per lens; (4) distill combined findings; (5) self-verify the report; (6) wait for explicit approval before applying edits.

## Scope & Guardrails

This skill performs no file modifications or state changes. Every finding is a proposal; nothing is applied until the user explicitly approves the edits. The user picks which changes ship.

**In scope**: agent-facing documentation files inside the project root — CLAUDE.md, AGENTS.md, copilot-instructions.md, `.claude/rules/`, `.claude/agents/`, `.claude/skills/`, `.cursorrules`, and files imported by those via `@` references.

**Out of scope** — if the target appears to be something other than agent-facing docs (a GitHub PR template, CI/CD config, source code documentation for humans), confirm with the user: "This doesn't look like agent-facing documentation. Do you still want me to audit it as one?" Then stop and wait.

## Definitions

This skill uses specialized terms; skim once, referenced implicitly thereafter.

- **`@` import** — a line in CLAUDE.md / AGENTS.md / `.claude/rules/*.md` whose meaningful content is `@path/to/file`. Claude Code inlines the referenced file at load time. Paths are relative to the file that contains the reference.
- **`.claude/rules/*.md`** — path-scoped instruction files. YAML frontmatter keyed `paths:` (an array of globs) restricts loading to sessions that touch matching files. Files without `paths:` always load.
- **`.claude/agents/*.md`** — agent definitions (custom subagents Claude Code can delegate to). Have a `description` field Claude uses to decide when to delegate, and optional `tools`/`disallowedTools` frontmatter to restrict tool access.
- **`.claude/skills/*/SKILL.md`** — user-triggered skills loaded only when invoked by name or pattern, not on every session.
- **Hooks** — shell commands configured in `settings.json` that run automatically before/after tool calls (e.g., `eslint --fix` after writes). Enforce deterministically where prose only guides cooperative behavior.
- **Explore subagent** — Claude Code's read-only subagent type: file reading, directory listing, grep, but no write or execute-with-side-effect tools.
- **Iron Law** — a rule that carries real cost if violated (data loss, compliance breach, broken deploy), meriting special hardening.
- **Enumerated loopholes** — a rule followed by the specific workarounds it blocks, by name. Harvested from observed baseline behavior, not invented.
- **Rationalization table** — a `| Excuse | Reality |` table paired with a rule. Rows are justifications the agent actually produced when violating the rule.
- **Red Flags** — phrases or thought patterns the agent says right before violating a rule, named so they become a self-check stop-signal.
- **Lens** — an audit perspective (e.g., Redundancy, Contradictions, Guardrails). Each lens runs as an independent sub-agent.

## Key Principle

This is documentation **for AI agents**, not humans. Agents can read source code. Focus the audit exclusively on material agents cannot derive by reading the codebase:

- **Redundancies** that waste tokens and risk contradictions
- **Contradictions** between files
- **Behavioral rules** that can't be derived from code (don't-do-X rules, non-obvious consequences)
- **Information in the wrong file** (behavioral rules in architecture docs, architecture in behavioral docs)
- **Genuinely missing context** that agents repeatedly get wrong and can't figure out from code alone

Skip anything an agent could discover by reading source: function signatures, file structure, fixture details, config options, CSS conventions.

## Lenses

Each lens is a sub-agent with a specific critical angle. The user can run all or pick specific ones.

### Core Lenses (default)

1. **Redundancy** — Find duplicated information across files. For each: cite both locations, classify as exact/paraphrase/partial, recommend which location is canonical.

2. **Contradictions** — Find conflicting instructions, inconsistent terminology, garbled text. Pay special attention to **cross-tool contradictions** when a project has instructions for multiple tools (e.g., CLAUDE.md says "use pytest" but .cursorrules says "use unittest"). For each: quote both passages, explain the conflict, recommend which version wins.

3. **Gaps** — Find genuinely missing information that agents need and can't derive from code. Focus on: non-obvious consequences (e.g. "missing X causes startup failure"), behavioral rules, workflow steps that are implied but not stated. Skip anything an agent can learn by reading source files.

4. **Actionability** — Find vague, weak, or unenforceable instructions. Flag these specific anti-patterns:

   **Framing principle**: Positive directives outperform negative prohibitions. LLMs attend to what you mention — saying "NEVER use X" activates X in the model's attention, making it *more* likely (the "Pink Elephant" effect). Anthropic's own prompting docs say: "Tell Claude what to do instead of what not to do." Rewrite rules as positive directives with reasoning wherever possible.

   - **Negative framing → positive rewrite**: "NEVER close issues without user approval" → "Wait for explicit user approval before closing any issue." "Do NOT combine these into one question" → "Always ask these as separate questions." "Don't use `any` type" → "Use interfaces and type guards for all function parameters." The only exception: keep NEVER/DO NOT for truly catastrophic, irreversible actions (force-push, deleting production data) where the shock value is warranted.
   - **Negative-only rules**: "don't do X" / "never do X" without stating what to do instead. Every prohibition MUST include the positive alternative — what the agent should do in that situation. A rule that only says "no" leaves the agent guessing.
   - **Missing reasoning**: Rules without a "why" are weaker. Agents generalize from explanations — "TTS engines cannot pronounce ellipses, so use complete sentences" is more robust than "NEVER use ellipses" because the agent can apply the principle to novel situations.
   - **Weak modals**: "should", "consider", "try to", "ideally", "prefer to" — rewrite as clear positive directives. If a rule is optional, state the exact situations where it applies ("MAY ... only when ...").
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
   - **Stale rules globs**: For each `.claude/rules/*.md` file with `paths:` frontmatter, verify the glob patterns match at least one existing file in the project. Stale globs mean the rule silently stopped loading — dead weight that misleads anyone reading the rules directory.
   - **Unscoped rules files**: Flag `.claude/rules/*.md` files that lack `paths:` frontmatter. These load every session regardless of which files the agent works on — same token cost as CLAUDE.md. Either add `paths:` to scope them, or move the content into CLAUDE.md where always-loaded rules belong.
   - **Skills boundary**: Claude Code skills (`.claude/skills/*/SKILL.md`) only load when invoked by the user. Flag domain knowledge in CLAUDE.md that loads every session but applies only to specific directories, workflows, or named tasks — these should be skills instead.
   - **Broken `@` imports**: Verify that all `@path/to/file` references in CLAUDE.md actually resolve to existing files.
   - **Lost in the middle**: In documents >= 20 lines, check if critical rules are buried in the 40-60% zone of the file. LLMs pay more attention to the beginning and end of long documents (Liu et al., 2023). Recommend moving critical rules to the top or bottom.
   - **README duplication**: Compare CLAUDE.md content against adjacent README.md files. Flag high overlap — README content is for humans and wastes agent tokens when duplicated into CLAUDE.md.

7. **Hygiene** — Catch quality and safety issues:
   - **Secrets**: Scan for API keys, connection strings, tokens, credentials, passwords in any doc file.
   - **Self-evident instructions**: Flag platitudes and instructions that state facts the base model already knows from language training or the agent would read from source. Examples: "write clean code", "follow best practices", "handle errors appropriately", "use meaningful variable names", "write tests for your code", "ensure code quality". These waste tokens and dilute real rules. Also flag standard language conventions Claude already knows (e.g., "use camelCase in JavaScript", "add type hints in Python" — unless the project deliberately deviates from convention).
   - **Hook-enforceable rules**: Claude Code supports hooks — shell commands that run automatically before/after tool calls (e.g., run `eslint --fix` after every file edit, run `pytest` after writes to `tests/`). Identify linting, formatting, or procedural rules stated as prose in CLAUDE.md that would be more reliable as hooks. Prose rules depend on the LLM remembering; hooks enforce deterministically. For each, recommend the prose rule be removed from CLAUDE.md and suggest what kind of hook would replace it (do not generate the hook config — just describe the intent, e.g., "run formatter after file writes" or "lint check before commit").
   - **Stale instructions**: Cross-reference documented commands, paths, and patterns against the actual codebase to find instructions that no longer match reality.
   - **Rules maintenance gap**: If the project uses `.claude/rules/` files, check whether CLAUDE.md instructs the agent to keep them up to date as the codebase evolves (e.g., "Update `.claude/rules/` files when refactoring changes the conventions they describe"). Without this, rules files become stale as code moves or patterns change, and the agent won't know it's responsible for maintaining them.

8. **Guardrails** — Audit explicit prohibitions and safety boundaries:
   - Are critical safety boundaries stated explicitly, or just implied? (e.g., destructive operations, external API calls, data mutations)
   - **Prefer positive framing** — apply the same framing criterion from the Actionability lens. Reserve NEVER/DO NOT only for catastrophic, irreversible actions (force-push to main, dropping tables, deleting production data) where the shock value is warranted; everything else gets a positive rewrite.
   - Are guardrails specific and unambiguous? Flag vague ones like "be careful with...", "avoid if possible", "try not to" — these are suggestions, not boundaries. Rewrite as concrete positive directives with scope.
   - Are there destructive or irreversible actions the agent could take that lack explicit boundaries? (Consider: deleting data, force-pushing, modifying shared state, sending external messages)
   - Do guardrails include reasoning? Rules with a **why** are more robust — agents generalize from explanations to novel situations instead of following the letter while violating the spirit.
   - Are there contradictions between guardrails and other instructions? (e.g., "wait for approval before modifying X" but a workflow step says "update X automatically")
   - **Tool restrictions need enforcement, not just prose**: Flag when docs rely solely on prose instructions to restrict dangerous commands (e.g., "never run kubectl delete", "don't git push --force"). Prose restrictions guide cooperative behavior but are not security boundaries — research shows they have high variance and can backfire via the pink elephant effect. For each prose-only tool restriction found:
     - Recommend reframing as a positive directive with reasoning (e.g., "Use `kubectl get/describe/logs` for cluster inspection. Present a plan and wait for approval before any resource modifications" instead of "NEVER kubectl delete")
     - Note whether the project has any enforcement layer (hooks, deny rules, sandboxing) backing it up — if not, flag that the restriction is guidance only
     - Flag stacked negative prohibitions (3+ NEVER/DO NOT rules about tools) — compliance degrades as these accumulate

9. **Rule Hardening** — For rules that carry real cost if violated (destructive ops, test discipline, scope control, migration safety, deployment gates), check whether they're hardened beyond bare positive framing:
   - **Enumerated loopholes** — does the rule list the specific workarounds it blocks, or just state the rule? Iron Laws without an enumeration fall to the first clever exception the agent invents. Flag rules where slippage has real cost and the exceptions aren't named.
   - **Rationalization tables** (for rules that keep breaking) — is there a `| Excuse | Reality |` table paired with the rule? Flag repeatedly-violated rules without one.
   - **Red Flags / self-talk list** — does the doc name the phrases the agent would say right before violating the rule ("this change is small enough to skip preview", "the file looked safe to reformat")? These convert the agent's own reasoning into a stop signal.

   Apply this lens **selectively**. A CLAUDE.md full of loophole enumerations is bloat — these patterns work because they're rare enough to catch the eye. Recommend hardening only where incidents have shown the rule actually erodes under pressure. For each finding: quote the rule, note which moves are missing, propose what to add (and flag that the table/Red Flags rows should be harvested from real incidents, not invented).

### Full Lenses (add to core)

10. **Cold Start** — Pretend to be a fresh agent with zero context. What assumptions does the documentation make that would confuse a first-time reader? Skip things derivable from code.

11. **Domain: {area}** — Deep-dive gap analysis for a specific domain (e.g., "database", "frontend", "pipeline", "testing"). Reads both docs AND relevant source code to find where the docs mislead or where non-obvious patterns aren't captured.

12. **Agent Quality** — Audit `.claude/agents/` definitions:
    - Missing or vague `description` field (Claude uses this to decide when to delegate — must be specific)
    - Overly broad tool access (should restrict to minimum needed via `tools`/`disallowedTools`)
    - Agents trying to do too many things (should be focused on one task)
    - Contradictions between agent instructions and CLAUDE.md rules

## Workflow

### Step 1: Determine Target

Ask the user for target path and scope before launching agents — running on assumed defaults misfires because doc layouts vary too widely to guess:
- **Path**: Which files/directories to audit? (suggest: the project root — discovery will find CLAUDE.md files, agent_docs/, etc. automatically)
- **Scope**: Ask the user to pick one:
  - `standard` — runs the 9 core checks: duplicated info, conflicting instructions, missing context, vague rules, misplaced content, file size/structure issues, secrets/stale content, guardrails/prohibitions, and hardening of critical rules
  - `full` — everything above plus: cold-start readability, a domain deep-dive (ask which area), and agent definition quality checks
  - Or the user can name specific areas if they know what they want (e.g., "just check for contradictions and stale content")

Present this as a simple choice — do NOT list lens numbers or internal names. If the user says "full", ask which domain area to deep-dive (e.g., database, frontend, testing).

Wait for the user's response before moving to Step 2.

### Step 2: Discover Documentation Files

Use the user's target path as the **project root** for all resolution.

**Scope boundary**: Discover and audit only files that exist on disk within the project root. Treat any reference to a file outside the project root — global configs (`~/.claude/CLAUDE.md`, `~/.codex/instructions.md`), user home directories, or content injected into the conversation by Claude Code's own config loading (e.g., `@agents.md` from a global CLAUDE.md) — as out of scope and skip it; the user can't act on findings tied to files they don't own in this repo.

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

Use the agent template (`audit-agent.md`). The template places shared content (key principle, documentation snapshot, output format) before the `---` divider to form a cacheable prompt prefix.

**Launch strategy** — Ask the user:

- **Sequential** (default) — Launch agents one at a time, each after the previous completes. First agent primes the cache; every subsequent agent reads the shared prefix at ~90% cheaper input. Slowest, cheapest.
- **1+Parallel** — Launch one agent first to prime the cache, then launch remaining agents in parallel batches of at most 5. Anthropic rate-limits large simultaneous bursts, so batching past 5 triggers 429s mid-run and wastes the work of any agent that already completed. Nearly as cheap as Sequential, much faster.

If the user doesn't specify, use **Sequential**.

**Placeholder resolution:**
1. In `audit-agent.md`: replace `{docs_snapshot}` with all discovered documentation file contents (with filenames and line numbers)
2. In `audit-agent.md`: replace `{path}` with the project root
3. In `audit-agent.md`: replace `{discovered_tools}` with the tools report from Step 2e

For each selected lens:
1. Read `audit-agent.md` from this skill's directory
2. Replace shared placeholders as above
3. Replace `{lens}` with the lens name (e.g., `Redundancy`)
4. Replace `{lens_instructions}` with the lens-specific instructions from the Lenses section above
5. Pass the result as the agent prompt

Use `subagent_type: "Explore"` for all agents so they can read source files if needed.

For the Domain lens: also instruct the agent to scan relevant source directories and compare patterns found in code vs what's documented.

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
- {N} critical rules lacking hardening (enumerated loopholes, rationalization tables, Red Flags)
```

**Example finding (to show the shape of a filled entry):**

```
### File: CLAUDE.md

#### Rewrite: "handle errors gracefully" is unmeasurable
**Flagged by**: Actionability, Hygiene
**Current** (lines 45-47):
> Always handle errors gracefully. Use best judgment for recovery strategies.
**Proposed**:
> For network errors, retry with exponential backoff (3 attempts, base 250ms). For parsing errors, log and skip to the next input. For system errors, escalate to the user with a diagnostic.
**Why**: "Be graceful" and "use best judgment" can't be checked; the rewrite names each error class and its action.
```

### Step 5: Self-Verification

Before presenting the distilled report to the user, check:

- Every finding cites a file path and specific line numbers.
- Every quote is copy-pasted from the documentation, not paraphrased.
- Deduplication is complete — no finding appears twice under different titles.
- The summary table is present, sorted by file then by starting line.
- Severity labels are justified against the scale (Critical / High / Medium / Low).

If any of the above fails, fix it before returning the report. Do not ship a half-formed audit.

5. After outputting, ask the user: "Want me to apply these changes?"

**If the user declines**, offer: "Would you like to adjust the scope or pick a subset of lenses and re-run, or drop the audit?" Do not re-apply changes, do not re-run silently, and do not nag. The report stays in the conversation for reference.

## Rules

- **Determine launch strategy with the user** (Sequential or 1+Parallel). Default to Sequential for cost savings.
- **Each agent audits independently** — if a later agent can see earlier findings, it anchors to them and covers fewer novel angles. Cross-lens agreement at the distill step is the real signal that a finding is robust. Run agents in the chosen strategy's isolation model; do not paste one agent's output into another's context.

  Loopholes to refuse:
  - "This finding is clearly from lens X too, so I'll reference lens X's output" — no; stay in your own lens, let the distill step merge duplicates.
  - "The user asked me to cross-check" — the cross-check happens at distill; run your lens independently first.
  - "I'll just cite another lens for emphasis" — say what *your* lens sees; leave attribution of overlap to distillation.

- **Distill runs after all agents complete** — multiple lenses often flag the same issue from different angles, and deduplication needs all findings in hand.

- **Include only information agents cannot derive from source** — behavioral rules, non-obvious consequences, cross-cutting constraints. For each proposed finding, verify it represents non-derivable context; exclude anything a `cat` / `grep` / `ls` would reveal.

  Use this boundary table when classifying a finding:

  | Code-derivable (exclude) | Non-derivable (include) |
  |---|---|
  | Function signatures, parameter types, return types | When to call each function; error-recovery choices |
  | Directory structure, module exports | Which patterns live where, and why |
  | Config file schema and available options | Non-obvious config consequences ("timeout=0 blocks forever") |
  | Docstrings, README quick-start | Unwritten team conventions that aren't in docstrings |
  | Examples already in the repo | Why certain patterns are forbidden or required |

- **Propose edits and wait for user approval before applying them** — the user is the arbiter of which changes are worth the code churn.

  Red Flags — if you notice yourself thinking any of these about this rule, stop and re-read it:
  - "This is a minor formatting fix, the user will obviously want it."
  - "The user didn't explicitly tell me *not* to apply changes." (Absence of "don't" is not permission.)
  - "All lenses agreed this was a problem, so it must be safe to apply."
  - "I already have a good draft, applying it is trivial."

- **Respect the doc hierarchy**: CLAUDE.md = behavioral rules; architecture/system docs = what the system is; DB docs = DB conventions. Routing a finding to the wrong file just moves the noise without reducing it.
