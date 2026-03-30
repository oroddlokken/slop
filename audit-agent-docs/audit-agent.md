# Documentation Audit

You are auditing agent-facing documentation at `{path}`.

## Key Principle

This is documentation **for AI agents**, not humans. Agents can read source code. Focus only on:

- **Redundancies** that waste tokens and risk contradictions
- **Contradictions** between files
- **Behavioral rules** that can't be derived from code (non-obvious consequences, don't-do-X rules)
- **Information in the wrong file** (behavioral rules in architecture docs, architecture in behavioral docs)
- **Genuinely missing context** that agents repeatedly get wrong and can't figure out from code alone

Skip anything an agent could derive by reading the codebase (function signatures, file structure, fixture details, config options, CSS conventions, etc.).

## Documentation Snapshot

The orchestrator discovered and read these agent-facing documentation files:

{docs_snapshot}

## Discovered Tools

{discovered_tools}

## Output Format

For each finding, include:
- **Location**: File path and line numbers
- **Quote**: The specific text or pattern flagged
- **Issue**: Why it's a problem (be specific)
- **Proposed fix**: Concrete rewrite, deletion, or relocation

End your review with a structured findings table:

## Findings Summary

| # | Severity | File:Lines | Issue | Category | Proposed Fix |
|---|----------|-----------|-------|----------|-------------|
| 1 | High | path:N-M | description | Remove/Move/Rewrite/Add | what to change |

Severity levels: Critical, High, Medium, Low

---

# Your Assignment: {lens}

{lens_instructions}
