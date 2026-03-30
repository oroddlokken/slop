# Test My Tests

Test quality deep-dive. Spins up parallel agents — each reviewing tests through a different lens — then distills all findings into prioritized action points.

## What you get

Up to 10 agents independently analyze your test suite, each through a different quality lens. Goes beyond "do tests exist?" to ask "do these tests actually catch real bugs?" After all finish, findings are deduplicated and distilled into:

- **Fix Now** — correctness, security, data integrity issues
- **Should Address** — maintainability and reliability concerns
- **Consider** — valid but non-urgent improvements
- **Skipped Noise** — subjective or trivial findings (ignored)

Every action item includes a file path and line number.

## Lenses

| Lens | Focus |
|------|-------|
| coverage-gaps | Critical code paths with zero test coverage |
| happy-path-only | Tests that only verify the sunny-day scenario |
| user-flows | Multi-step real-world workflows not tested end-to-end |
| mock-debt | Mocks that diverge from reality, over-mocking |
| assertion-quality | Weak or missing assertions, no side-effect verification |
| fragile-tests | Tests coupled to implementation, break on harmless refactors |
| data-realism | Test data too simple for production scenarios |
| error-paths | Failure modes untested (network, permissions, timeouts) |
| boundary-values | Off-by-one, empty collections, limits, type boundaries |
| flaky-risks | Time-dependent, order-dependent, shared state, race conditions |

## Modes

| Mode | What runs |
|------|-----------|
| Full | All 10 lenses in parallel (default) |
| Quick | 5 high-impact lenses: coverage-gaps, user-flows, happy-path-only, error-paths, assertion-quality |
| Pick | You choose which lenses to run |

## Installation

Tell your agent to read this repository and ask it to help you integrate it into your Claude Code setup as a skill.
