## Flaky Risks

Find tests at risk of intermittent failure — tests that sometimes pass, sometimes fail, without code changes.

### What to Look For

1. **Time-dependent tests**: Using `datetime.now()`, `time.time()`, `Date.now()` — could fail at midnight, month boundaries, or slow CI
2. **Sleep-based synchronization**: `sleep(1)` or `setTimeout` waiting for async instead of proper await/poll
3. **Order-dependent tests**: Pass alone but fail in different order (shared database state, global variables)
4. **Non-deterministic output**: Asserting on output with random values, UUIDs, timestamps, or auto-increment IDs without controlling them
5. **Network-dependent tests**: Unit tests hitting real network endpoints — fail when offline or service is down
6. **Concurrency-dependent tests**: Threads/goroutines with assertions on timing-dependent outcomes
7. **Filesystem-dependent tests**: Writing to `/tmp` without unique paths, or reading files other tests modify
8. **Port collision**: Starting servers on hardcoded ports that collide in parallel test runs
9. **Uncontrolled randomness**: Random values without seeding — different behavior every run
10. **Resource leaks between tests**: Open connections, files, or processes not cleaned up — later tests fail from exhaustion

### How to Evaluate

For each flakiness risk:
- Under what specific conditions would this test fail intermittently?
- How hard would this be to debug in CI? (reproducible vs timing-dependent nightmare)
- Is this test currently retried in CI or on a "known flaky" list?

### Severity Guide

- **Critical**: Flaky tests in the critical path that block deployments or train developers to ignore failures
- **High**: Clear race conditions or time-dependency that WILL fail eventually
- **Medium**: Hardcoded resources (ports, paths) that fail in parallel execution
- **Low**: Minor non-determinism that rarely causes issues

### Output Format

| # | Severity | File:Line | Issue | What to Test | Suggestion |
|---|----------|-----------|-------|-------------|------------|
| 1 | High | test_path:line | description | the flakiness trigger | how to make the test deterministic |
