---
name: dep-hygiene
description: "Find dependency issues: unused imports, unnecessary packages, outdated dependencies, and overly heavy dependencies for what they provide."
args:
  - name: path
    description: The directory to scan (optional, defaults to cwd)
    required: false
user-invokable: true
---

# Find Dependency Issues
This skill scans code and reports findings — it does not modify code. It can run standalone or as part of `/codehealth`. Examples are Python; apply equivalent patterns for your target language.

Scan the codebase for dependency problems — unused packages, unnecessary imports, outdated deps, and heavyweight libraries used for trivial tasks.

## What to Look For

### Unused imports
- Modules imported at the top of a file but never referenced in the file body
- `from X import Y` where `Y` is never used
- Star imports (`from X import *`) that pollute the namespace

### Unnecessary packages
- Packages in `requirements.txt` / `pyproject.toml` / `package.json` / `Cargo.toml` that are never imported in source code
- Dev dependencies that aren't used by any linter, test, or tool
- Packages that were added for a feature that was later removed
- Transitive dependencies explicitly listed that are already pulled in by another dep

### Heavyweight dependencies for trivial use
- Importing `pandas` to read one CSV file (use `csv` module)
- Importing `requests` for a single HTTP call (use `urllib` or `httpx` if already present)
- Importing `lodash` for one utility function (use native JS)
- Large frameworks pulled in for one small feature

### Duplicate dependencies
- Multiple packages that do the same thing (`requests` and `httpx` and `urllib3` all used directly)
- Multiple date libraries (`moment`, `dayjs`, `date-fns` in the same project)
- Multiple test runners or assertion libraries

### Outdated / unmaintained dependencies
- Packages with known security vulnerabilities
- Packages that haven't been updated in 2+ years
- Packages that are archived or deprecated
- Packages pinned to very old versions without reason

### Circular imports
- Module A imports from Module B which imports from Module A
- These cause import errors, confusing behavior, or force code structure workarounds

### Import organization
- No clear pattern for import ordering (stdlib → third-party → local)
- Relative imports mixed with absolute imports inconsistently
- Deep import paths that suggest tight coupling (`from app.services.user.impl.v2.UserService import ...`)

## How to Scan

1. **Read the dependency manifest** (pyproject.toml, package.json, Cargo.toml, go.mod, etc.)
2. **For each declared dependency**, search for imports of that package across source files
3. **For each source file**, check if all imports at the top are used in the file body
4. **Check for multiple packages solving the same problem** (HTTP clients, date libraries, etc.)
5. **Look at dependency age** — check when each dep was last updated (if tooling allows)
6. **Check for circular imports** — look for import errors or `if TYPE_CHECKING:` patterns (often used to work around circular imports)
7. **Compare dependency count to project size** — more than 30 direct deps for a small project is notable

## Report Findings

For each dependency issue:

| Field | Content |
|-------|---------|
| **Location** | file:line for imports; manifest file for package-level issues |
| **Type** | Unused import / Unused package / Heavyweight dep / Duplicate dep / Outdated / Circular |
| **Package** | The dependency in question |
| **Suggestion** | Remove / Replace with X / Update to Y / Consolidate on Z |
| **Impact** | Bundle size, security risk, maintenance burden, confusion |

### Severity Guide

- **Critical**: Dependencies with known security vulnerabilities
- **High**: Unused packages — adds to install time, attack surface, and confusion
- **High**: Circular imports causing runtime issues
- **Medium**: Heavyweight deps for trivial use — unnecessary bloat
- **Medium**: Duplicate deps solving the same problem — maintenance burden
- **Low**: Unused imports in individual files — minor clutter
- **Low**: Import ordering inconsistencies

## Output Format

After scanning, output:

```
## Dependency Issues

### Package-Level Issues

#### {Severity}: {short description}
**Package**: `{package_name}`
**Declared in**: `{manifest_file}`
**Used in**: {list of files that import it, or "nowhere"}
**Suggestion**: {Remove | Replace with X | Update}
**Impact**: {what you gain}

### File-Level Import Issues

#### {file_path}
- Line {N}: `import {X}` — unused in this file
- Line {N}: `from {X} import {Y}` — {Y} never referenced
```

End with a Findings Summary table:

| # | Severity | Location | Type | Package | Suggestion |
|---|----------|----------|------|---------|-----------|
| 1 | High | pyproject.toml | Unused package | pandas | Remove — never imported |

## Rules

- **Check for dynamic usage** before declaring a package unused — some packages are used via CLI tools, pytest plugins, or runtime discovery
- **Check framework plugins** — packages like `pytest-xdist` are used by the test runner, not imported directly
- **Don't flag standard library imports** as unnecessary dependencies
- **Distinguish dev deps from prod deps** — unused dev deps are lower severity than unused prod deps
