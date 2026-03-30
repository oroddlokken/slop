## Fragile Tests

Find tests tightly coupled to implementation details that will break on harmless refactors.

### What to Look For

1. **Testing private methods**: Tests that reach into internals (`_private_method()`, internal state)
2. **Exact output matching**: Asserting on exact string output, HTML structure, or log messages that could change cosmetically
3. **Mock-verifying call counts**: `mock.assert_called_once()` on internal implementation that could reasonably change to two calls
4. **Order-dependent assertions**: Requiring results in a specific order when the contract doesn't guarantee order
5. **Hardcoded IDs/timestamps**: `assert id == 42` or exact timestamps that depend on auto-increment or execution time
6. **CSS selector / DOM path testing**: Coupled to specific CSS classes or DOM hierarchy instead of accessible roles/labels
7. **File path assertions**: Checking absolute paths that break on different machines or CI
8. **Import-path testing**: Verifying internal module structure rather than public API behavior
9. **Database schema coupling**: Depending on specific column names, table structure, or migration state

### How to Evaluate

For each fragile test:
- Would a safe refactor (rename, restructure, optimize) break this test?
- Does this test verify behavior (what it does) or implementation (how it does it)?
- How often has this pattern caused false test failures?

### Severity Guide

- **Critical**: Tests that prevent safe refactoring of critical paths
- **High**: Tests coupled to implementation that break on routine maintenance
- **Medium**: Tests with hardcoded values that work now but are brittle
- **Low**: Minor coupling unlikely to cause problems soon

### Output Format

| # | Severity | File:Line | Issue | What to Test | Suggestion |
|---|----------|-----------|-------|-------------|------------|
| 1 | High | test_path:line | description | what behavior to test instead | how to decouple the test |
