## User Flows

Find real multi-step user workflows that aren't tested end-to-end. Unit tests check pieces in isolation — this lens checks whether the full journey works.

### What to Look For

1. **Registration -> activation -> first action**: Is the full onboarding flow tested as a sequence?
2. **CRUD lifecycles**: Create -> read -> update -> delete — tested as a connected flow, not isolated operations?
3. **Auth flows**: Login -> access protected resource -> token refresh -> logout
4. **Payment/transaction flows**: Select -> configure -> pay -> confirm -> receipt
5. **Multi-step form flows**: Step 1 -> validation -> step 2 -> back -> step 3 -> submit
6. **State machine transitions**: Full sequence of valid states, not just individual transitions
7. **Cross-service flows**: Service A calls B calls C — is the full chain tested?
8. **Concurrent user scenarios**: Two users acting on the same resource simultaneously
9. **Failure-and-recovery flows**: Start -> fail midway -> retry -> succeed
10. **Batch/bulk operations**: Upload 100 items -> process -> verify all succeeded or handled partial failure

### How to Evaluate

For each missing flow test:
- Is this a flow a real user would perform regularly?
- How many individual units does this flow cross? (more units = higher integration risk)
- Are there integration tests that partially cover this, or is it completely untested?

### Severity Guide

- **Critical**: Core business flows (checkout, signup, data export) with no integration/e2e test
- **High**: Common user journeys (search -> filter -> act, settings -> save -> verify) untested as flows
- **Medium**: Secondary flows (password reset, account deletion) untested
- **Low**: Admin or edge-case flows untested

### Output Format

| # | Severity | File:Line | Issue | What to Test | Suggestion |
|---|----------|-----------|-------|-------------|------------|
| 1 | Critical | source_path:line | description | the untested flow | what each step should verify |
