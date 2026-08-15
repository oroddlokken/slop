# Find Docstring Gaps on Public API

Scan the code that other people call — exported functions, public classes/methods, package entry points — for docstrings that are absent, incomplete, or wrong in structure. This lens is about the *contract*: a caller should be able to use the thing correctly from its docstring without reading the body. It complements `missing-why` (which covers inline rationale, not API docs).

## What to Look For

### Missing docstrings on public surface
- Exported/public functions, classes, and methods with no docstring at all
- Package `__init__` exports, CLI command handlers, HTTP route handlers — the entry points a newcomer reads first
- A public module with no module docstring stating its purpose

### Incomplete contracts
- Parameters not documented (especially non-obvious ones — flags, optional behavior-changing args)
- Return value undocumented, or the *shape* of a complex return (a dict/tuple/named structure) left unexplained
- Exceptions the function deliberately raises not listed (`raises`)
- Side effects not mentioned (writes a file, mutates an argument, makes a network call)
- Units / formats not stated (seconds vs ms, UTC vs local, 0-indexed vs 1-indexed)

### Structural / style violations
- Inconsistent docstring style across the codebase (Google vs NumPy vs reST vs bare prose mixed)
- No one-line summary line (PEP 257: first line is a short summary)
- Multi-line docstrings whose summary doesn't fit on the first line
- Params documented in the wrong order, or documenting params that don't exist (overlaps `contradicts-code` — defer stale-param cases there; here flag *absence* and *structure*)

## How to Scan

1. **Identify the public surface first.** Use exports (`__all__`, package `__init__`, non-underscore names), route decorators, CLI registration, published entry points. Internal helpers (`_foo`) have a lower bar — don't demand full docstrings on obvious private helpers.
2. **For each public callable, check for a docstring.** Missing → finding (severity scaled by how public / how non-obvious).
3. **For each present docstring, check contract completeness** — every param, the return shape, raised exceptions, side effects, units.
4. **Detect the dominant docstring style** in the codebase and flag inconsistency against it.
5. **Check the summary line** exists and is a real summary, not a restatement of the name (a name-echo is `restates-code`; here flag *absence* of any summary).
6. **Calibrate to project norms.** If the project documents only public API and leaves helpers bare, honor that — don't demand docstrings the house style doesn't want.

## Report Findings

For each gap:

| Field | Content |
|-------|---------|
| **Location** | file:line of the definition |
| **Surface** | How public (exported / route / CLI / public method / internal) |
| **Gap** | Missing docstring / undocumented param / return shape / raises / side effect / style |
| **Suggestion** | The specific docstring content to add (name the params/return to document) |

### Severity Guide

- **High**: A widely-used public API (exported function, route, CLI command) with no docstring, or one that omits a behavior-changing param / a raised exception a caller must handle.
- **Medium**: Public method missing return-shape or side-effect documentation; inconsistent docstring style across the codebase (systemic).
- **Low**: Missing summary line, minor style deviation, undocumented obvious param on a minor helper.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | High | app.py:54 | Public route handler `create_graph` has no docstring; request/response shape undocumented | Add docstring stating accepted params, return JSON shape, and 4xx conditions |

## Rules

- **Say what to document, not "add a docstring."** Name the params, the return shape, the exceptions that need covering.
- **Scale the bar by visibility.** Public/exported = high bar; private helper = only flag if confusing. Don't carpet-bomb every `_helper`.
- **Don't reward padding.** A docstring that merely restates the signature does not close the gap — if the fix would just echo the name, the real need is a *contract* (params/returns/raises), say so. (A pure name-echo docstring is `restates-code`'s finding.)
- **Wrong/stale docs are `contradicts-code`.** This lens owns *absence* and *structure*; that lens owns *inaccuracy*.
