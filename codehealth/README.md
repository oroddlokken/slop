# Code Health

Meta code quality review. Spins up parallel agents — each reviewing through a different lens — then distills all findings into prioritized action points.

## What you get

Up to 12 agents independently scan your codebase, each through a different quality lens. After all finish, findings are deduplicated and distilled into:

- **Fix Now** — correctness, security, data integrity issues
- **Should Address** — maintainability and reliability concerns
- **Consider** — valid but non-urgent improvements
- **Skipped Noise** — subjective or trivial findings (ignored)

Every action item includes a file path and line number.

## Lenses

| Lens | Focus |
|------|-------|
| duplicates | Copy-pasted and near-identical code blocks |
| extract-logic | Inline operations that should be functions/methods |
| simplify-code | Over-engineered solutions, unnecessary abstractions |
| hardcoded | Magic strings, numbers, URLs, credentials in code |
| error-gaps | Missing, swallowed, or inconsistent error handling |
| complexity | Long functions, deep nesting, high branching |
| query-smells | N+1 queries, raw SQL in loops, missing parameterization |
| dead-code | Unused functions, unreachable branches, dead routes |
| naming | Inconsistent naming conventions, ambiguous identifiers |
| dep-hygiene | Unused imports, unnecessary dependencies, outdated deps |
| test-gaps | Critical code paths lacking test coverage |
| type-structs | Raw dicts/lists/tuples that should be typed structures |

## Modes

| Mode | What runs |
|------|-----------|
| Full | All 12 lenses in parallel (default) |
| Quick | 5 high-risk lenses: duplicates, complexity, error-gaps, hardcoded, type-structs |
| Pick | You choose which lenses to run |

## Installation

Tell your agent to read this repository and ask it to help you integrate it into your Claude Code setup as a skill.
