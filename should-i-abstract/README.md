# Should I Abstract?

Pragmatic DRY review. Finds both under-DRY (true knowledge duplication worth consolidating) and over-DRY (wrong abstractions worth inlining). A single focused agent that makes judgment calls — when to share, when to split, and when to leave it alone.

## What you get

A single agent reviews your codebase through a decision framework with six tests applied in order:

1. **True or Incidental?** — Will these change for the same reason?
2. **Rule of Three** — Enough instances to see the right abstraction?
3. **Existing Abstraction?** — Does a utility already handle this?
4. **Boundary Check** — Would sharing cross a service/team boundary?
5. **Conditional Accumulation** — Has a good abstraction grown barnacles?
6. **Articulation Test** — Can you cleanly separate what varies from what's shared?

Findings are organized into three categories:

- **Abstract This** — True knowledge duplication worth consolidating
- **Inline This** — Wrong abstractions that cost more than the duplication they prevent
- **Leave Alone** — Incidental duplication that is correctly separate (prevents bad refactors)

## Installation

Tell your agent to read this repository and ask it to help you integrate it into your Claude Code setup as a skill.
