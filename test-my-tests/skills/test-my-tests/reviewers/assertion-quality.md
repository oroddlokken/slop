## Assertion Quality

Find tests with weak, missing, or misleading assertions that could pass even when the code is broken.

### What to Look For

1. **No assertions**: Test functions that call code but never assert anything ("didn't crash" as success)
2. **Existence-only checks**: `assert result is not None` or `assert len(results) > 0` without checking correctness
3. **Status-code-only HTTP tests**: Checks `response.status_code == 200` but not the response body, headers, or side effects
4. **Missing side-effect verification**: Tests a create endpoint but doesn't verify the record was actually persisted
5. **Snapshot abuse**: Snapshot tests on large objects where changes are rubber-stamped without review
6. **Boolean-only assertions**: `assertTrue(result)` when the test should verify specific values
7. **Missing negative assertions**: Verifies what IS returned but not what should NOT be present (sensitive fields, deleted records)
8. **Exception type without message**: `assertRaises(ValueError)` without checking the error message or context
9. **Approximate without reason**: Floating-point approximate comparisons with wide tolerances that hide real bugs
10. **Assert count mismatch**: 50 lines of setup but only 1 trivial assertion

### How to Evaluate

For each weak assertion:
- What could break in the source code while this test still passes?
- What specific value or state should this test verify?
- Is the test providing false confidence?

### Severity Guide

- **Critical**: No assertions on auth or data mutation operations
- **High**: Tests for business logic that only check "didn't crash" or return type
- **Medium**: Tests with assertions but missing side-effect verification
- **Low**: Tests that could be more specific but cover the main case

### Output Format

| # | Severity | File:Line | Issue | What to Test | Suggestion |
|---|----------|-----------|-------|-------------|------------|
| 1 | High | test_path:line | description | what's not being verified | what assertion to add |
