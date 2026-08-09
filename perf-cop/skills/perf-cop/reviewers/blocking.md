# Find Blocking and Contention

Scan the codebase for time spent waiting: synchronous calls on an async path, locks held longer than they need to be, and independent work run one after another that could have run at once. You own **waiting**. How many calls are made belongs to `io-batching`; how much CPU each does belongs to `hot-loops`.

The distinguishing question for this lens is not "is this slow?" but "is something idle while this runs, and did it have to be?"

## What to Look For

### Sync I/O inside an async function

The highest-impact async bug: one blocking call in a coroutine stalls the entire event loop, so every other in-flight request waits on it — the damage is proportional to concurrency, not to the call's own duration.

```python
# BAD: blocks the whole loop for the duration of the request
async def handler(request):
    data = requests.get(url).json()        # sync HTTP in a coroutine
    rows = psycopg2_conn.execute(sql)      # sync DB driver
    text = open(path).read()               # sync file read
    time.sleep(1)                          # sync sleep

# GOOD
async def handler(request):
    data = (await client.get(url)).json()          # async client
    text = await asyncio.to_thread(path.read_text) # or offload it
    await asyncio.sleep(1)
```

The tells: `requests`/`urllib` in an async codebase, a sync DB driver alongside an async framework, `time.sleep`, `open()`/`read()`/`write()`, `subprocess.run`, `os.system`, and any call into a library with no async variant — all inside `async def`, or inside a function reachable from one. **Follow the call chain**: a sync helper three levels below the coroutine blocks just as hard.

Also CPU-bound work in a coroutine: a large parse, a hash over a big buffer, a sort of a large list. Same effect, no I/O involved.

### Serial awaits over independent work

Sequential `await` on operations that do not depend on each other. The wall time is the sum where it could have been the max.

```python
# BAD: three round trips back to back
user = await fetch_user(uid)
prefs = await fetch_prefs(uid)
flags = await fetch_flags(uid)

# GOOD
user, prefs, flags = await asyncio.gather(fetch_user(uid), fetch_prefs(uid), fetch_flags(uid))
```

Same shape without async: three subprocess calls in a row, three HTTP requests in a synchronous script, N independent file reads — a thread pool or a concurrent map replaces the sum with the max. Check dependency honestly: if the second call takes the first's result, it is serial by necessity.

### Locks held across I/O

A lock held while a network call, a database query, a file write, or a subprocess runs serializes every other holder behind an unbounded wait.

```python
# BAD: every caller queues behind one network round trip
with self._lock:
    value = fetch_from_api(key)     # I/O inside the critical section
    self._cache[key] = value

# GOOD: compute outside, mutate inside
value = fetch_from_api(key)
with self._lock:
    self._cache[key] = value
```

Also: a lock around a whole function where two lines need it, coarse global locks guarding unrelated state, and nested lock acquisition (both a contention and a deadlock risk — say so, but the correctness half is not this lens's to fix).

### Transactions held open across slow work

A database transaction spanning an HTTP call, a loop of computation, or user interaction holds row and table locks for the whole span. Every writer to those rows waits. The fix is to shrink the transaction to the writes.

### Pool starvation and unbounded queueing

A connection pool, thread pool, or semaphore whose size is smaller than the concurrency reaching it — every excess caller waits for a slot. Look for pool sizes set to defaults next to per-request checkouts, connections checked out and held across slow work, and `await`-free code paths that hold a pooled resource while doing something unrelated. The inverse is also a finding: an unbounded queue or unbounded task spawn (`create_task` in a loop with no semaphore) that converts a load spike into memory exhaustion.

### Fire-and-forget and unawaited work

Tasks created and never awaited (results lost, exceptions swallowed, shutdown races), background threads with no join, and `await` missing on a coroutine call — a correctness bug that also usually means the work is not doing what its timing suggests.

### Polling instead of waiting

`while True: check(); sleep(0.1)` where an event, condition variable, or callback exists. Costs latency (up to one interval) and CPU (a wakeup per interval, forever). Note the interval and the cadence — a 100 ms poll in a long-lived process is 36,000 wakeups an hour.

### Retries and timeouts that multiply waiting

Retry loops with no backoff and no cap, nested retries (a retrying client called from a retrying helper: 3 × 3 = 9 attempts), and missing timeouts on network calls — an unbounded wait is the worst blocking case there is, and it is usually one missing keyword argument.

## What NOT to Flag

- **The speculative version of this lens: "make this async."** Proposing an async rewrite of a synchronous codebase, or `gather` over two calls in a CLI that runs once a day, is architecture advice wearing a performance costume. If there is no event loop, or nothing else is waiting, sequential is correct and simpler.
- **Sequential awaits that are genuinely dependent.** Check whether the second call consumes the first's result before calling it serial.
- **Sync I/O in synchronous code.** A blocking read in a script, a CLI, or a worker thread blocks only that thread. That is what threads are for. The finding requires an event loop or a shared resource that others are queued on.
- **Sync I/O at startup, in a lifespan hook, or in a management command,** even in an async framework. Nothing is in flight yet. That is `startup`'s.
- **Locks held over trivial critical sections.** A lock around a dict assignment is doing its job. The finding is I/O or heavy computation inside the section, not the existence of the lock.
- **A lock you cannot show is contended.** One writer and one reader, or a lock on a path entered once per minute, is not contention — it is correctness. Removing it to save nanoseconds is a bug.
- **Missing parallelism where the work is not independent,** where it shares a rate limit, or where ordering matters. Say why, and do not flag.
- **`sleep` used deliberately** for rate limiting, backoff, or debouncing. Read the surrounding comment before flagging.

## How to Scan

1. **Establish whether there is an event loop at all.** `async def`, `asyncio`/`trio`/`anyio`, an ASGI server, goroutines, an async runtime. If the workload map says none, skip every async check and review locks, pools, serial work, and polling only.
2. **List every `async def`** and, for each, grep its body and its callees for sync I/O: `requests.`, `urllib`, `time.sleep`, `open(`, `.read(`, `.write(`, `subprocess.`, `os.system`, sync DB driver names, `psycopg2`, `pymysql`, `sqlite3`.
3. **Follow the call chain out of each coroutine** at least two levels. Sync-in-async almost never appears in the coroutine itself.
4. **Find consecutive `await` statements** and test each pair for a data dependency.
5. **Find every lock**: `Lock`, `RLock`, `Semaphore`, `threading.`, `with self._lock`, `mutex`, `synchronized`. For each, read the whole critical section and ask what I/O or heavy work is inside it.
6. **Find transaction scopes**: `begin`, `atomic`, `transaction`, `with session`. Check what runs inside.
7. **Find pools and their sizes** — `pool_size`, `max_connections`, `ThreadPoolExecutor(max_workers=...)`, semaphore limits — and compare to the concurrency the entry points imply.
8. **Grep for `while True` with a `sleep`**, and for retry loops (`for attempt in range`, `@retry`, `tenacity`) — check backoff, caps, and nesting.
9. **Grep for network calls with no `timeout=`.**
10. **For every finding, name who waits**: the event loop, other holders of this lock, callers queued on the pool, the user.

## Report Findings

For each blocking finding:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Kind** | Sync-in-async / Serial-independent / Lock-over-I/O / Transaction scope / Pool starvation / Polling / Unbounded retry |
| **Workload** | Entry point + cadence + concurrency reaching this path (cite the workload map) |
| **Who waits** | The event loop, other lock holders, pooled callers, the user — and for how long relative to the call |
| **Fix** | Concrete change — async client, `to_thread`, `gather`, shrink the critical section, shrink the transaction, size the pool, event instead of poll, add timeout and backoff |

### Severity Guide

- **Critical**: Waiting that saturates a shared resource under load — sync I/O in a coroutine on a per-request path, a lock or transaction held across a network call on a hot path, unbounded task spawn or a missing timeout that lets one slow dependency stall the whole service.
- **High**: Measurable user-facing wait — serial independent awaits on a request path, an undersized pool at known concurrency, a retry storm with no backoff.
- **Medium**: Contention on a warm path, coarse locks, polling in a long-lived process, transaction scope wider than needed on a low-traffic write path.
- **Low**: Cold-path blocking, single-threaded scripts, and anything where you could not show that anyone waits.

The Critical/High split here is exactly the general one: Critical is degradation that compounds with load (one blocked loop stalls everyone), High is a constant wait one user feels.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Workload | Kind | Who waits | Fix |
|---|----------|-----------|----------|------|-----------|-----|
| 1 | Critical | api/handler.py:44 | per request, all concurrent requests | Sync-in-async | the event loop, for the full HTTP round trip | Use the async client, or `asyncio.to_thread` |

## Rules

- **Name who waits, or it is not a blocking finding.** "This is synchronous" is a description; "this stalls the event loop for every concurrent request" is a finding.
- **No event loop, no sync-in-async findings.** Check first; do not assume a framework.
- **Follow the call chain.** The blocking call is almost never in the coroutine you are reading.
- **Test dependency before calling awaits serial.** Ordering is sometimes the point.
- **Never propose removing a lock, shortening a transaction, or dropping a retry in a way that changes semantics.** If shrinking the critical section moves a check away from the write it guards, the fix is wrong — say what invariant it would break instead.
- **A missing timeout is a blocking finding, not just a robustness one.** Unbounded wait is the worst latency in the codebase.
- **Concurrency changes severity more than duration does.** A 50 ms block at concurrency 1 is nothing; the same block in an event loop serving 200 connections is the whole problem.
- **Do not invent numbers.** "Serializes all callers behind one network round trip" is defensible; "adds 200ms of contention" is not.
