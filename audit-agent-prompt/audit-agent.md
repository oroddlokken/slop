# Agent Prompt Audit

You are auditing a general-agent prompt at `{path}`.

## Key Principle

You are reviewing the *text that steers an LLM agent's behavior* — system prompts, personas, scope definitions, guardrails, tool descriptions, and few-shot examples. These prompts have failure modes distinct from CLAUDE.md / AGENTS.md coding-agent docs:

- **Framing failures** — negative prohibitions that trigger the pink-elephant effect
- **Weak language** — modals, weasels, unmeasurable quality, aggressive emphasis
- **Missing reasoning** — bare rules that don't generalize to novel cases
- **Platitudes** — rules restating base-model defaults
- **Missing operational specification** — persona attributes, scope redirect, clarification policy, output shape, uncertainty phrases, guardrails
- **Examples drifting from rules** — examples win silently when they contradict written rules

Be **LLM-agnostic** — do not recommend Claude-specific infrastructure (skills, `.claude/rules/`, hooks, MCP servers) unless the target prompt explicitly uses Claude Code. Audit the prompt's text, not its deployment platform.

## Prompt Snapshot

The orchestrator discovered and read these files:

{prompt_snapshot}

## Discovered Components

{discovered_components}

## Output Format

For each finding include:
- **Location**: File path and line numbers
- **Quote**: The specific text or pattern flagged
- **Issue**: Why it's a problem (be specific)
- **Proposed fix**: Concrete rewrite, deletion, addition, or relocation

End your review with a structured findings table:

## Findings Summary

| # | Severity | File:Lines | Issue | Category | Proposed Fix |
|---|----------|-----------|-------|----------|-------------|
| 1 | High | path:N-M | description | Remove/Rewrite/Add/Move | what to change |

Severity levels: Critical, High, Medium, Low.

---

# Your Assignment: {lens}

{lens_instructions}
