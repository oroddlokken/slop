---
name: test-gaps
description: "Find critical code paths lacking test coverage: auth, payments, data mutations, error handling, and business logic with no corresponding tests."
args:
  - name: path
    description: The directory to scan (optional, defaults to cwd)
    required: false
user-invokable: true
---

# Find Test Gaps
This skill scans code and reports findings — it does not modify code. It can run standalone or as part of `/codehealth`. Examples are Python; apply equivalent patterns for your target language.

Scan the codebase for critical code that lacks test coverage. Not every line needs a test — focus on code where bugs would cause the most damage.

## What to Look For (Priority Order)

### 1. Authentication and authorization (CRITICAL)
- Login/logout flows
- Permission checks and role-based access
- Token generation, validation, and refresh
- Password hashing, reset flows
- Session management
- API key validation

### 2. Money and payments (CRITICAL)
- Price calculations, discounts, taxes
- Payment processing and webhooks
- Billing cycles, subscription logic
- Refund processing
- Currency conversion
- Invoice generation

### 3. Data mutations with business rules (HIGH)
- Create/update/delete operations with validation
- State machine transitions (order status, approval workflows)
- Cascading operations (delete user → delete all their data)
- Data transformations that must preserve invariants
- Bulk operations

### 4. External integrations (HIGH)
- API client code — are error cases tested?
- Webhook handlers — are all event types handled?
- Email/SMS sending — are templates and conditions tested?
- File upload/download — are edge cases tested?

### 5. Error handling paths (MEDIUM)
- What happens when an API call fails?
- What happens when a database query returns no results?
- What happens when input validation fails?
- What happens when a required service is unavailable?

### 6. Edge cases in business logic (MEDIUM)
- Boundary values (zero, negative, max values)
- Empty collections (no items in cart, no users in group)
- Concurrent operations (two users editing the same resource)
- Time-dependent logic (expiration, scheduling, timezones)

### 7. Data access layer (MEDIUM)
- Complex queries (JOINs, aggregations, subqueries)
- Pagination logic
- Search/filter functionality
- Sorting and ordering

## How to Scan

1. **Map test files to source files** — for each source file, check if a corresponding test file exists
2. **Read critical source files** (auth, payments, core business logic) and check what's tested
3. **Compare test function names to source function names** — which source functions have no corresponding test?
4. **Check test quality signals**:
   - Do tests assert behavior or just call functions without assertions?
   - Do tests cover error cases or only happy paths?
   - Are there parameterized tests for boundary conditions?
5. **Look at test directory structure** — does it mirror the source structure?
6. **Check for test utilities** — are there factories, fixtures, mocks that make testing easy?
7. **Look for `# TODO: add tests` or `@skip` markers**

### Test Coverage Tiers

| Source Code | Expected Coverage |
|-------------|------------------|
| Auth, payments, core business rules | Every function tested, including error paths |
| Data access, API handlers | Happy path + main error cases |
| Utilities, helpers | Tested if complex, skip if trivial |
| Configuration, constants | No tests needed |
| Generated code, migrations | No tests needed |

## Report Findings

For each test gap:

| Field | Content |
|-------|---------|
| **Source file** | file:line range |
| **Function/method** | The untested function |
| **Why it matters** | What could go wrong without tests |
| **What to test** | Specific test cases that should exist |
| **Priority** | Based on risk tier above |

### Severity Guide

- **Critical**: Auth or payment logic with no tests — bugs here cause security incidents or financial loss
- **High**: Data mutation logic with no tests — bugs here cause data corruption
- **Medium**: API handlers or business logic with only happy-path tests — error cases will surprise you in production
- **Low**: Utility functions or non-critical paths without tests — nice to have

## Output Format

After scanning, output:

```
## Test Coverage Gaps

### Coverage Map

| Source File | Test File | Coverage Assessment |
|------------|-----------|-------------------|
| `{source}` | `{test}` | {Tested | Partial | No tests} |
| `{source}` | — | No test file exists |

### Critical Gaps

#### {Severity}: {short description}

**Source**: `{file}:{line_range}`
**Function**: `{function_name}`
**Current tests**: {None | Happy path only | Missing error cases}
**Risk**: {what could go wrong}
**Suggested test cases**:
1. {specific test case — what input, what expected behavior}
2. {error case — what happens when X fails}
3. {edge case — boundary condition}
```

End with a Findings Summary table:

| # | Severity | Source File:Line | Function | Current Tests | Risk |
|---|----------|-----------------|----------|--------------|------|
| 1 | Critical | auth.py:45 | verify_token | None | Auth bypass |

## Rules

- **Focus on risk, not coverage percentage** — 80% coverage that misses all the auth code is worse than 40% coverage that tests auth thoroughly
- **Suggest specific test cases** — not "add tests for this function" but "test that expired tokens return 401, test that invalid signatures raise SecurityError"
- **Don't flag trivial code** — getters, setters, data classes, config, and simple wrappers don't need dedicated tests
- **Check for integration tests too** — unit tests aren't the only coverage. API tests, integration tests, and E2E tests count.
- **Note test quality issues** — tests that exist but don't assert anything, or that mock so heavily they test nothing, are gaps too
