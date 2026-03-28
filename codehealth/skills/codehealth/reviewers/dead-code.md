# Find Dead Code
This reviewer scans code and reports findings — it does not modify code.

Scan the codebase for code that's no longer used, reachable, or needed. Dead code adds confusion, increases maintenance burden, and makes the codebase harder to navigate.

## What to Look For

### Unused functions and methods
- Functions defined but never called (grep for the function name across the codebase)
- Methods on classes that are never invoked
- Exported functions with no importers
- Private/internal functions not called within their module

### Unreachable branches
- `if False:` or `if True:` with dead else branch
- Conditions that can never be true given the data flow
- Code after `return`, `raise`, `break`, `continue` in the same block
- Feature flag checks for flags that are permanently on/off
- `except` blocks for exceptions that can never be raised by the try block

### Dead routes / endpoints
- API routes registered but never called by any client code
- URL patterns with no corresponding view or handler
- Routes that point to missing or renamed handlers
- Webhook endpoints for integrations that no longer exist

### Commented-out code
- Large blocks of commented code (>5 lines) — use version control, not comments
- `# TODO: remove this` that's been there for months
- Blocks disabled with `if False:` or `if 0:`

### Orphaned files
- Source files not imported by anything
- Test files for code that no longer exists
- Migration files that have been superseded
- Config files for removed features
- Templates/views for removed pages

### Dead imports (file-level)
- `import X` at the top of a file where X is never used in that file
- `from X import Y` where Y is never referenced
- Dev dependencies used in imports but never actually called

**Note**: Unused packages in manifests (pyproject.toml, package.json) are owned by `/dep-hygiene`.

### Dead configuration
- Environment variables defined but never read
- Config keys set but never accessed
- Feature flags that are always on or always off

## How to Scan

1. **List all function/method definitions** in the codebase
2. **For each, search for its name** across all files — if it appears only at the definition, it's likely dead
3. **Check for `# type: ignore` or `noqa`** — sometimes these suppress "unused" warnings, confirming dead code
4. **Search for large comment blocks** — `#` or `//` spanning 5+ consecutive lines
5. **Check route/URL registrations** against handler functions
6. **Check imports** against actual usage within each file
7. **Look at git blame** for commented-out code — if it's been commented for months, it's dead
8. **Check for `__all__` exports** that reference non-existent names

### Limitations
- Dynamic dispatch (`getattr`, `__getattr__`, reflection) can make functions appear unused when they're called dynamically — flag but note the uncertainty
- Framework magic (decorators like `@app.route`, signal handlers, template tags) can hide usage — check framework-specific patterns
- Public library APIs may be used by external consumers — distinguish internal code from public API

## Report Findings

For each dead code instance:

| Field | Content |
|-------|---------|
| **Location** | file:line (or entire file for orphans) |
| **Type** | Unused function / Unreachable branch / Dead route / Commented-out / Orphaned file / Dead import / Dead config |
| **Confidence** | High (definitely dead) / Medium (likely dead but could be dynamic) / Low (might be used via reflection or external consumers) |
| **Last modified** | When was this code last meaningfully changed (from git blame) |
| **Action** | Delete / Investigate further / Remove comment and decide |

### Severity Guide

- **High**: Dead code in critical paths that confuses readers into thinking it's active — misleading and risky
- **Medium**: Orphaned files and large commented-out blocks — clutter that makes navigation harder
- **Low**: Unused helper functions, dead imports — minor clutter

Note: Dead code is never "Critical" severity — it's not causing bugs (by definition, it doesn't run). But it does accumulate cost.

## Output Format

After scanning, output:

```
## Dead Code Found

### {Type}: {short description}

**Location**: `{file}:{line}` (or `{file}` for orphaned files)
**Confidence**: {High | Medium | Low}
**Last modified**: {date from git blame, if available}
**Action**: {Delete | Investigate | Remove comment}
**Why it's dead**: {how you determined it's unused}
```

End with a summary:

```
## Summary
- **{N} unused functions** — safe to delete
- **{N} commented-out blocks** — {total lines} lines of dead comments
- **{N} orphaned files** — not imported by anything
- **{N} dead imports** — imported but never used
- **{N} uncertain** — might be used dynamically, investigate
```

And a Findings Summary table:

| # | Severity | File:Line | Type | Confidence | Action |
|---|----------|-----------|------|------------|--------|
| 1 | High | path:line | Unused function | High | Delete |

## Rules

- **Mark confidence honestly** — if you're not sure something is dead, say so. Deleting live code is worse than keeping dead code.
- **Check for dynamic usage** before declaring something dead — `getattr`, `importlib`, template tags, signal handlers, CLI entry points
- **Check framework conventions** — Django management commands, Flask CLI, pytest fixtures, and decorators like `@app.route` all register functions without explicit calls
- **Don't flag test fixtures or conftest** functions — they're used by the test framework
