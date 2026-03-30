## Mock Debt

Find tests where mocks, stubs, or fakes diverge from real behavior — making tests pass while production breaks.

### What to Look For

1. **Mocks that always succeed**: External service mocks that return 200/success and never simulate failure
2. **Stale mocks**: Mock responses that don't match the current API contract (outdated shapes, missing fields, wrong types)
3. **Over-mocking**: Tests that mock the thing they're supposed to test (mocking the database in a database integration test)
4. **Mock-heavy tests**: Tests with more mock setup than actual assertions — sign the test isn't testing much
5. **Missing contract tests**: Mocks exist but no test verifies the mock matches the real service
6. **Shallow mocks**: Mocks that return data but don't enforce real constraints (rate limits, auth, validation)
7. **Global mock leaks**: Mocks applied at module level that silently affect other tests
8. **Mock behavior divergence**: Mock returns synchronously when the real service is async, or instantly when the real service has latency

### How to Evaluate

For each mock concern:
- What would break in production that this mock hides?
- Is there a way to verify mock fidelity (contract test, integration test, recorded fixture)?
- How often does the real service change vs how often the mock is updated?

### Severity Guide

- **Critical**: Mock hides a known failure pattern (e.g., mocks auth but real auth rejects tokens)
- **High**: Mock response shape doesn't match current API — tests pass, production fails
- **Medium**: Over-mocking a component that could be tested with a real lightweight instance
- **Low**: Mock is reasonable but could be more realistic

### Output Format

| # | Severity | File:Line | Issue | What to Test | Suggestion |
|---|----------|-----------|-------|-------------|------------|
| 1 | High | test_path:line | description | what the mock hides | how to make the test more realistic |
