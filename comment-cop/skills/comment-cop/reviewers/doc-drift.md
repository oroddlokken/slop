# Find Doc Drift (README / markdown vs code)

Scan external documentation — README, `docs/*.md`, `.rst`, usage guides — for claims that no longer match the code. Users meet the README first; when it lies, they hit errors before they hit success. This lens owns *external* prose; stale in-source docstrings belong to `contradicts-code`.

## What to Look For

### Stale commands and invocations
- Documented CLI commands, flags, or subcommands that were renamed or removed
- Install/setup steps referencing old tooling (a `requirements.txt` when the project moved to `uv`/`pyproject.toml`, a `make` target that no longer exists)
- Example commands whose arguments no longer match the actual parser

### Signature / API drift in examples
- Code snippets in the README calling functions with the wrong name, argument order, or arity
- Import paths that changed (`from foo import bar` after `bar` moved)
- Documented return shapes / JSON schemas that differ from what the code returns now

### Configuration drift
- Documented env vars, config keys, or defaults that don't match the code (a `CHARTROOM_ENTRA_RESOLVE` documented one way, read another)
- A config example listing keys the loader ignores, or omitting keys it requires
- Documented file paths / locations that moved

### Structural staleness
- References to files, directories, or modules that were moved or deleted
- Broken internal doc links / anchors
- A feature list describing capabilities that were removed, or omitting ones that were added
- Architecture docs describing a design the code has since outgrown

### Version / dependency claims
- "Requires Python 3.9" when `pyproject.toml` says 3.11
- Badges, version numbers, or supported-platform lists that drifted

## How to Scan

1. **Extract every concrete claim from the docs** — commands, flags, env vars, config keys, import paths, function calls, file paths, version requirements.
2. **Verify each against the code.** Grep the codebase for the command/flag/env var/symbol. If the doc says it and the code doesn't have it (or has it differently), that's drift.
3. **Run example snippets in your head against the real signatures** — argument order, names, return shapes.
4. **Check setup/install instructions against the actual manifests** (`pyproject.toml`, `package.json`, `justfile`, `Makefile`, Dockerfile).
5. **Follow internal doc links** and confirm targets exist.
6. **Compare the feature list / architecture description to the modules that exist.**

## Report Findings

For each drift:

| Field | Content |
|-------|---------|
| **Location** | doc file:line |
| **Doc claims** | The command / flag / env var / signature / path stated |
| **Code has** | What the code actually exposes (or that it's gone) |
| **User impact** | The error or confusion a reader hits by following the doc |
| **Suggestion** | Update the doc to match the code |

### Severity Guide

- **High**: A documented install/setup/usage step that fails outright — a new user cannot get started (wrong command, wrong env var, dead flag on the happy path).
- **Medium**: A stale example, an outdated config key, a moved file reference — recoverable but wrong.
- **Low**: A broken internal link, a drifted version badge, a minor feature-list omission.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | High | README.md:22 | Documents `pip install -r requirements.txt`; project uses `uv` / pyproject | Update setup steps to `uv sync` |

## Rules

- **Verify against the code, don't guess.** Grep for the symbol/flag/env var before claiming drift. A false drift report sends the user to "fix" correct docs.
- **Fix the doc to match the code** (unless the code is clearly the bug — then note "possible code/doc mismatch, confirm intent" and don't guess which side is right).
- **This lens owns external prose only** (`*.md`, `*.rst`, README, docs sites). In-source docstring drift is `contradicts-code`.
- **Prioritize the happy path.** A broken first-run instruction outranks a stale link deep in an appendix.
