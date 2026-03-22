---
name: error-gaps
description: "Find missing, swallowed, or inconsistent error handling. Detects bare except blocks, ignored return values, missing error paths, and inconsistent error patterns across the codebase."
args:
  - name: path
    description: The directory to scan (optional, defaults to cwd)
    required: false
user-invokable: true
---

# Find Error Handling Gaps
This skill scans code and reports findings — it does not modify code. It can run standalone or as part of `/codehealth`. Examples are Python; apply equivalent patterns for your target language.

Scan the codebase for missing, swallowed, or inconsistent error handling that could cause silent failures, data corruption, or confusing user experiences.

## What to Look For

### Swallowed errors
```python
# BAD: Catch and ignore
try:
    process_payment(order)
except Exception:
    pass  # silently swallowed — payment may have failed
```

```javascript
// BAD: Empty catch block
try {
  await saveUser(data);
} catch (e) {
  // nothing
}
```

### Bare / overly broad catches
```python
# BAD: Catches everything including KeyboardInterrupt, SystemExit
try:
    result = do_thing()
except:
    log.error("failed")

# BAD: Catches too broadly — hides programming errors
try:
    user = get_user(user_id)
    send_email(user.email)
except Exception as e:
    return {"error": "something went wrong"}
```

### Missing error handling on I/O
- Network calls (`requests.get`, `fetch`, `http.get`) without try/catch
- File operations (`open`, `read`, `write`) without error handling
- Database operations without transaction management or error handling
- External process execution (`subprocess`, `exec`) without checking return codes
- Queue/message publishing without confirming delivery

### Inconsistent error patterns
- Some functions return error codes, others throw exceptions
- Some API endpoints return `{"error": "..."}`, others return HTTP status codes only
- Some modules use custom exceptions, others use built-in exceptions
- Logging vs raising vs returning `None` for the same kind of error
- Different error formats for the same type of failure

### Missing error propagation
- Functions that catch errors and return `None` instead of propagating — callers don't know something failed
- Functions that log errors but don't raise/return — the error is noted but nothing acts on it
- Middleware/decorators that catch and transform errors, losing the original context

### Missing validation
- Functions that accept external input without validation
- API handlers that trust request data without checking types, ranges, or formats
- Database queries built from unvalidated input

### Resource cleanup gaps
- Open file handles, database connections, or network sockets without proper cleanup (missing `with`, `finally`, `defer`, or equivalent)
- Transactions started but not committed/rolled back in error paths

## How to Scan

1. **Search for bare except/catch blocks**: `except:`, `except Exception`, `catch (e) {}`, `catch { }`
2. **Search for `pass` / empty blocks after except/catch**
3. **Search for I/O operations**: `requests.`, `fetch(`, `open(`, `cursor.`, `subprocess.`
4. **Check if I/O operations are inside try/except blocks**
5. **Compare error handling patterns across similar functions** — are they consistent?
6. **Check API route handlers** — do all routes handle errors the same way?
7. **Look for `# TODO` or `# FIXME` near error handling** — often marks known gaps
8. **Check for `return None` patterns** — often hides errors from callers

## Report Findings

For each error handling gap:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Type** | Swallowed / Bare catch / Missing handling / Inconsistent / Missing cleanup |
| **Risk** | What can go wrong — be specific (data loss, silent failure, security issue) |
| **Suggestion** | Concrete fix — what error handling should be added |
| **Pattern** | If this is part of a systemic pattern, note it |

### Severity Guide

- **Critical**: Swallowed errors on data mutation (payment, writes, deletes) — could cause data loss or corruption with no indication
- **High**: Missing error handling on external I/O in production paths — will cause unhandled exceptions in production
- **Medium**: Overly broad catches that hide programming errors — makes debugging harder
- **Low**: Missing error handling on non-critical paths, or inconsistencies that don't affect correctness

## Output Format

After scanning, output:

```
## Error Handling Gaps

### {Severity}: {short description}

**Location**: `{file}:{line}`
**Type**: {Swallowed | Bare catch | Missing handling | Inconsistent | Missing cleanup}
**Currently**: {what the code does now}
**Risk**: {what can go wrong}
**Suggestion**: {concrete fix}
```

If there are systemic patterns (e.g., "no route handlers have error handling"), call them out in a **Systemic Issues** section before the individual findings.

End with a Findings Summary table:

| # | Severity | File:Line | Type | Risk | Suggestion |
|---|----------|-----------|------|------|-----------|
| 1 | Critical | path:line | Swallowed | Silent payment failure | Re-raise or return error to caller |

## Rules

- **Focus on meaningful gaps** — a missing catch on `print()` isn't worth reporting; a missing catch on `db.execute()` is
- **Suggest specific error types to catch** — not "add error handling" but "catch `ConnectionError` and `Timeout`, retry once, then raise `ServiceUnavailableError`"
- **Note systemic patterns** — if the whole codebase swallows errors, say that once rather than reporting 50 individual instances
- **Consider the language idioms** — Go uses error returns, Python uses exceptions, Rust uses Result. Judge by the language's conventions.
