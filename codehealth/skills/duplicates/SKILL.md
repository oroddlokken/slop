---
name: duplicates
description: "Find duplicated and near-identical code blocks across the codebase. Detects copy-paste patterns, repeated logic, and similar implementations that should be consolidated."
args:
  - name: path
    description: The directory to scan (optional, defaults to cwd)
    required: false
user-invokable: true
---

# Find Duplicated Code
This skill scans code and reports findings — it does not modify code. It can run standalone or as part of `/codehealth`. Examples are Python; apply equivalent patterns for your target language.

Scan the codebase for copy-pasted and near-identical code blocks that should be consolidated into shared functions, methods, or modules.

## What Counts as Duplication

### Exact duplicates
Identical code blocks (3+ lines) appearing in multiple locations. Copy-paste with no modification.

### Near-duplicates
Code blocks that are structurally identical but differ in:
- Variable names (`user_id` vs `account_id`)
- String literals (`"users"` vs `"accounts"`)
- Minor variations (one extra field, slightly different ordering)
- Type annotations or comments

### Structural duplicates
Different code that follows the exact same pattern:
- Same sequence of operations with different targets (fetch → validate → transform → save, repeated for different entities)
- Same error handling structure wrapped around different operations
- Same CRUD pattern implemented independently for each model

### NOT duplication (skip these)
- Test setup code that's intentionally repeated per test for clarity
- Boilerplate required by a framework (route decorators, model definitions)
- Simple one-liners that happen to be similar (`return None`, `raise ValueError`)
- Import blocks

## How to Scan

1. **Read key source files** (prioritize large files and files with similar names)
2. **Compare across files**: Look for blocks of 3+ lines that appear in multiple files
3. **Compare within files**: Look for repeated patterns within a single file
4. **Check for pattern duplication**: Same multi-step workflow implemented for different entities
5. **Check utility files**: Are there helper functions that already exist but aren't being used?

### Signals to look for
- Files with very similar names (`user_service.py`, `account_service.py`) — often contain parallel implementations
- Functions with the same structure but different names
- Multiple files importing the same set of dependencies and using them the same way
- Large blocks of code between `# ---` or similar separators that look alike

## Report Findings

For each duplicate found:

| Field | Content |
|-------|---------|
| **Locations** | All file:line locations where the duplicate appears |
| **Lines** | How many lines are duplicated |
| **Similarity** | Exact / Near / Structural |
| **Suggestion** | Extract to where? What should the shared version look like? |
| **Risk** | What breaks if these diverge? (bugs from updating one but not the other) |

### Severity Guide

- **Critical**: Duplicated business logic (validation rules, price calculations, permission checks) — these WILL diverge and cause bugs
- **High**: Duplicated data access patterns (same query built in multiple places) — maintenance burden and consistency risk
- **Medium**: Duplicated utility code (same helper logic in multiple modules) — annoying but lower risk
- **Low**: Duplicated boilerplate that's hard to abstract cleanly — note it but don't force extraction

## Output Format

After scanning, output:

```
## Duplicates Found

### {Severity}: {short description}

**Locations:**
- `{file_1}:{start_line}-{end_line}`
- `{file_2}:{start_line}-{end_line}`

**Similarity**: Exact | Near (differs in: {what}) | Structural
**Lines duplicated**: {count}
**Suggestion**: {how to consolidate — be specific about where to extract and what the shared interface looks like}
**Risk**: {what happens if these stay duplicated}
```

End with a Findings Summary table:

| # | Severity | File:Line | Duplicate Of | Lines | Type | Suggestion |
|---|----------|-----------|-------------|-------|------|------------|
| 1 | Critical | path:line | path:line | 15 | Near | Extract to shared function in X |

## Rules

- **Minimum 3 lines** to count as duplication — shorter than that is usually not worth extracting
- **Suggest concrete consolidation** — don't just say "deduplicate this", say where the shared version should live and what it should look like
- **Consider the cost of abstraction** — if extracting would require a complex interface to handle all variations, note that the cure might be worse than the disease
- **Check if a shared version already exists** — sometimes duplication exists because people don't know about an existing utility
