## Error Paths

Find failure modes that are untested — what happens when things go wrong?

### What to Look For

1. **Network failure handling**: HTTP calls without tests for timeout, connection refused, DNS failure, partial response
2. **Invalid input responses**: Functions accepting user input with no test for malformed, missing, or oversized input
3. **Permission denied scenarios**: Operations requiring auth but never tested with wrong/expired/missing credentials
4. **Database failure handling**: Writes without tests for constraint violations, connection loss, deadlocks
5. **File system errors**: File reads/writes without tests for missing file, permission denied, disk full
6. **Third-party service failures**: External API calls with no test for the service being down or returning errors
7. **Rate limiting**: Rate-limited API calls with no test for 429 responses or backoff behavior
8. **Partial failure in batch operations**: Batch where item 50/100 fails — is the partial state tested?
9. **Timeout behavior**: Long-running operations with no test for timeout boundary
10. **Concurrent modification**: Two operations on the same resource — is the conflict tested?

### How to Evaluate

For each untested error path:
- What does the user see when this fails in production? (crash, hang, wrong data, cryptic error?)
- How often could this realistically happen?
- Is the error path handled in code but never verified by tests, or completely unhandled?

### Severity Guide

- **Critical**: Auth or payment error paths untested
- **High**: External service failures untested for core features
- **Medium**: File/database errors untested for secondary features
- **Low**: Edge-case failures unlikely in normal operation

### Output Format

| # | Severity | File:Line | Issue | What to Test | Suggestion |
|---|----------|-----------|-------|-------------|------------|
| 1 | Critical | source_path:line | description | the failure scenario | what to assert (error type, user message, rollback) |
