## Happy Path Only

Find tests that only verify the sunny-day scenario. The test exists, but it only checks "does this work when everything is perfect?"

### What to Look For

1. **Single-case tests**: Test functions with one assertion that only tests the default/expected input
2. **No error case companions**: A test for `create_user(valid_data)` exists but no test for `create_user(invalid_data)`, `create_user(duplicate_email)`, `create_user(missing_fields)`
3. **Success-only HTTP tests**: Tests that only check 200/201 responses, never 400/401/403/404/500
4. **Missing negative tests**: Tests verify what SHOULD happen, never what should NOT happen
5. **One-item tests**: Tests that use a single item when the code handles collections (pagination, batching, empty sets, large sets)
6. **Optimistic async tests**: Tests that assume async operations succeed, never test timeout/failure/partial completion
7. **Perfect-input-only**: Tests always use well-formed, complete, correctly-typed inputs

### How to Evaluate

For each happy-path-only test:
- What's the most likely failure mode that's untested?
- What would a real user do differently from the test data?
- Which error path is most dangerous if it breaks silently?

### Severity Guide

- **Critical**: Auth or data mutation tests with no negative cases
- **High**: API endpoint tests with no error response testing
- **Medium**: Business logic tests missing edge case scenarios
- **Low**: Utility function tests missing unusual inputs

### Output Format

| # | Severity | File:Line | Issue | What to Test | Suggestion |
|---|----------|-----------|-------|-------------|------------|
| 1 | High | test_path:line | description | the missing scenario | what the test should verify |
