# Find State Left Behind by a Raise

Scan the codebase for functions that raise partway through and leave state no later call can read or undo: a file opened and not closed on the error branch, a flag set before the work and not cleared after it fails, a row inserted whose sibling never lands, a lock or a counter released only on the path that returns. One call, one exception, one process — no crash, no second thread, no batch.

## What to Look For

### The flag set before the work

A marker written to say the work started, and cleared only where the work finished. The failure path leaves a state nothing else can move.

```python
# BAD: a raise in run() leaves the job "running" until a human edits the row
job.status = "running"
db.commit()
run(job)                        # raises
job.status = "done"
db.commit()
```

The same shape without a database: `self._loading = True`, a `.lock` file, a sentinel key in Redis, an entry appended to an in-progress list. Ask which line clears it, and whether the raise happens above that line.

### Two writes with a raise between them

Two stores, or two rows, that only mean something together. The first write commits, the second never runs, and nothing reconciles them.

```python
# BAD: the debit commits, the credit never happens
debit(from_account, amount)     # commits
credit(to_account, amount)      # raises: recipient not found
```

Flag a sequence of writes to different tables, files or services with no transaction, no compensating action and no `finally`. Include the local pair: a file written and a database row that records it, or a record inserted and its search-index entry.

### The resource closed only on the success path

An explicit `open`/`connect`/`acquire` with its `close` at the end of the body, so any raise between them leaks the handle.

```python
# BAD: an exception in parse() leaks the descriptor
f = open(path)
data = parse(f.read())
f.close()
```

The fix is the language's scope form: `with` (Python), `defer` (Go), `try-with-resources` (Java), RAII (C++/Rust), `try/finally` where none applies. Flag cursors, sockets, subprocesses, temp files and pooled connections the same way.

### The release that sits after the raising line

Acquire and release are both present, and the release is unreachable when the body raises.

```python
lock.acquire()
process(item)                   # raises
lock.release()                  # never runs; every later caller blocks
```

Counters are the quiet version: `active += 1` at the top and `active -= 1` at the bottom leaves the gauge climbing one per failure until it trips a limit that nothing will clear.

### Cleanup registered too late

The resource is acquired outside the `try`, so the `finally` covers the body and not the acquisition, or the cleanup assumes work that never started.

```python
# BAD: a raise inside connect() skips the finally entirely
conn = connect()
try:
    use(conn)
finally:
    conn.close()
```

Also flag a `finally` that raises on its own — closing a handle that was never assigned, or rolling back a transaction the failure already rolled back — because the second exception replaces the first and the operator sees the wrong cause.

### Partial mutation of an object still in use

A method that mutates several fields and raises in the middle leaves the object half-updated, and the caller catches the exception and keeps using it.

```python
# BAD: name is updated, email is not, and the caller still holds `user`
user.name = new_name
user.email = validate_email(new_email)   # raises
```

Build the new value first and assign once, or restore on the error path. Flag this only where a caller demonstrably keeps the object after catching.

### NOT a finding (skip these)

- Cleanup missed only on `kill -9`, OOM or power loss — the unclean path is out of scope here
- Cleanup that only runs on the happy path at process exit — SIGTERM, drain and signal handlers are out of scope here
- A loop where item 50 of 100 raises and 1-49 stay written — the half-done batch is out of scope here
- Teardown of running async work, `CancelledError` and timeouts — concurrency teardown is out of scope here
- A raise before any state changed — nothing to clean up
- A process that exits immediately after the raise, where the OS reclaims the resource and no other state was touched
- Test fixtures and scripts whose leaked handle dies with the run

## How to Scan

1. **Find the acquire/release pairs**: `open(`, `connect(`, `acquire(`, `Popen(`, `begin(`, `+= 1` — check whether a scope form or a `finally` covers the body between them
2. **Find the status writes**: assignments of `"running"`, `"in_progress"`, `"pending"`, `_busy`, `_loading`, and lock files — trace which line clears each, and what raises above it
3. **Find sequences of two or more writes** to different stores in one function, and check for a transaction or a compensating action
4. **Read every `try` block's `finally`** — is the acquisition inside the `try`? Can the `finally` itself raise?
5. **For each function that raises**, list what it changed before the raise: fields, files, rows, counters, locks
6. **Check the callers of raising functions** — does anything catch and keep using the half-mutated object?
7. **Check `except` bodies for missing rollback** — a caught exception with no `rollback()` on an open transaction

## Report Findings

For each instance:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Type** | Uncleared flag / Split write / Leaked resource / Unreleased lock / Late cleanup / Half-mutated object |
| **Raises where** | The line that can throw, and what throws there |
| **State left** | What is written, held or set after the raise, and who reads it next |
| **Recovery** | What clears it today — a retry, a later call, a human, or nothing |
| **Fix** | The scope form, transaction, compensating write or `finally` that closes the gap |

### Severity Guide

- **Critical**: A raise between two committed writes leaves data inconsistent — money debited and not credited, a record without the row that makes it valid
- **High**: A flag, lock or marker set and never cleared, so every later call reads a state no code can move; a transaction left open on the error path
- **Medium**: A file handle, connection or cursor closed only on the success path — one leak per failure, exhausting the pool over time
- **Low**: Cleanup missing where only programmer error can raise, or where the process exits immediately after

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Type | State left | Fix |
|---|----------|-----------|------|------------|-----|
| 1 | High | path:line | Uncleared flag | Job stuck at "running"; no retry picks it up | Set the terminal status in a `finally` |

## Rules

- **Name the line that raises** — cite the call and what it throws. "This could fail" is not a finding; `validate_email` raising `ValueError` at line 41 is.
- **Say who reads the leftover state** — a later call, a retry, an operator, or nothing. A half-write nobody reads is Low.
- **One call, one exception.** A concurrent writer, a killed process or a failed batch item belongs to another lens; check the skip list before reporting.
- **Match the fix to the language** — `with` and `contextlib`, `defer`, `try-with-resources`, RAII, `using`. Suggest the form the file already uses elsewhere.
- **Group a systemic pattern once** — if every handler in a module sets a status flag with no `finally`, report the pattern with two or three citations rather than one finding per handler.
- **`error-gaps` owns whether the error is handled; this lens owns what the raise left behind.** A swallowed exception is theirs. An exception that propagates correctly and still leaves a lock held is yours.
