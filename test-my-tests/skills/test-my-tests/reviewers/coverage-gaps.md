## Coverage Gaps

Find critical source code that has **zero test coverage** — no test file, no test function, nothing.

**Note**: This overlaps with codehealth's `test-gaps` reviewer. This reviewer focuses on untested critical paths within a dedicated test quality review. Codehealth's test-gaps provides a lighter check as part of a broader code health scan.

### What to Look For

1. **Business logic without tests**: Service functions, domain models, calculation logic, state transitions
2. **API endpoints without tests**: Routes, controllers, handlers with no corresponding test
3. **Auth/authz without tests**: Login, permission checks, role-based access, token validation
4. **Data mutations without tests**: Create, update, delete operations on persistent data
5. **Error handlers without tests**: Custom error handlers, fallback logic, retry mechanisms
6. **Complex conditionals without tests**: Functions with multiple branches where no branch is tested
7. **Recently changed code without tests**: Files in git log that changed recently but have no test updates

### How to Evaluate

For each source file/function without tests:
- How critical is this code path? (auth > data mutation > display logic)
- How complex is it? (10-line function < 100-line function with 5 branches)
- How likely is a bug to go unnoticed? (internal tool < public API)

### Severity Guide

- **Critical**: Auth, payments, data integrity code with zero tests
- **High**: Core business logic or API endpoints with zero tests
- **Medium**: Utility functions with complex logic and no tests
- **Low**: Simple CRUD operations or configuration with no tests

### Output Format

| # | Severity | File:Line | Issue | What to Test | Suggestion |
|---|----------|-----------|-------|-------------|------------|
| 1 | Critical | path:line | description | the untested scenario | what the test should verify |
