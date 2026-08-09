# Find Chatty I/O

Scan the codebase for work that crosses a boundary once per item when it could cross once per batch. You own **call volume across boundaries** — network, database, disk, subprocess, IPC. What happens inside the loop between the calls belongs to `hot-loops`; how much data each call carries belongs to `payloads`.

This is usually where the measured time actually is. A round trip costs microseconds to milliseconds and dwarfs everything the process does between them, so N calls per request is the most reliable finding in the skill — provided you can say what N is.

## What to Look For

### A call per item where one call would do

The core pattern, in every flavor of boundary:

```python
# BAD: one query per user
for user in users:
    orders = db.query("SELECT * FROM orders WHERE user_id = ?", user.id)

# GOOD: one query, grouped in memory
rows = db.query("SELECT * FROM orders WHERE user_id IN (...)", [u.id for u in users])
```

```python
# BAD: one HTTP request per id
for item_id in ids:
    resp = client.get(f"/items/{item_id}")

# GOOD: the API's bulk endpoint, or a concurrent gather if there is none
resp = client.get("/items", params={"ids": ",".join(ids)})
```

The database case is the classic N+1 — **flag it here as cost only** (how many round trips, per what request, over what row count). Its shape as a query, and the right ORM fix, belong to codehealth's `query-smells`; for depth, `dba`.

### Per-item writes that should be one batch

Inserts, updates, appends, log writes, index updates, or cache sets executed one at a time in a loop. `executemany`, a bulk insert, a multi-row `VALUES`, a pipelined Redis `MSET`, or a single buffered write replaces N round trips with one. Per-item writes inside a transaction are worse — the lock is held across all N.

### Lazy relationship access in a loop (ORM N+1)

The invisible version: no query is written, but touching `order.customer.name` inside a loop over orders issues a query per row. Look for attribute access on a related object inside any loop over query results, and for the absence of `select_related`/`prefetch_related`/`joinedload`/`includes` on the query that produced it.

### File and filesystem chattiness

`open()`/`read()` per item, `os.path.exists` or `stat` per candidate in a large directory walk, re-globbing the same directory inside a loop, reading the same config file per item, `Path.read_text()` on a file already read this run. Also: writing a file per record where an append-mode handle or one batched write would do.

### Subprocess per item

Spawning a process per item is the most expensive per-call boundary in the list — process creation is milliseconds even when the command is trivial. `git` invoked per file, `curl` per URL, a formatter per source file. Most such tools take a list of arguments; one invocation with N arguments replaces N invocations.

### Repeated identical calls in one request

The same query, the same HTTP GET, or the same file read issued two or three times in one code path because two helpers each fetch what they need. Not a loop, still round trips that a single fetch threaded through would remove. (If the same *inputs* recur across requests rather than within one, it is `caching-wins`.)

### Round trips hidden behind an abstraction

A helper, property, or repository method that looks like a field access and is a query. Count what the call chain does at the boundary, not what the call site looks like — this is the single most-missed case in the lens, because the loop body reads as pure arithmetic.

### Pagination walked one page at a time when it need not be

Sequentially fetching page after page where the API exposes a larger page size, a cursor with prefetch, or parallel range requests. Also: fetching all pages when the caller consumes only the first.

## What NOT to Flag

- **The speculative version of this lens: "batch this" where N is small and fixed.** Three API calls to three different services in a request handler is three calls, not chattiness. A loop over a 5-element config list making one call each is 5 calls forever. Batching has a real cost — a bulk endpoint that does not exist, a larger failure blast radius, harder partial-error handling — and it is not worth paying for a constant.
- **Loops over collections you cannot size.** If the workload map gives no bound on the iterable and the code gives no limit, this is Low. "Potentially N+1" with no N is the noise this lens produces by default.
- **Setup-time I/O.** Loading config files, reading a schema, opening a connection pool at boot. That is `startup`'s, and once per process is not chatty.
- **Calls the framework already batches or pools.** An ORM with query batching configured, an HTTP client with connection reuse and pipelining, a driver with a statement cache. Check the configuration before claiming a round trip per call.
- **Deliberate per-item calls for correctness.** Idempotent per-record processing with per-record commit so a failure resumes cleanly; rate-limited APIs where one-at-a-time is the contract; per-item calls that must be independently retryable. Batching those trades correctness or recoverability for speed — say why it is deliberate and move on.
- **The SQL's shape.** Whether the query is injectable, missing a transaction, or badly indexed is `query-smells`/`dba`. You count the trips.
- **Migrations, one-off scripts, and CI steps** unless the workload map shows one running on a cadence.

## How to Scan

1. **Build the boundary inventory first**: every DB client, HTTP client, file API, subprocess helper, cache client, and queue producer in the codebase. Grep for their call sites — that set is your search space.
2. **Grep for calls inside loops**: `.execute(`, `.query(`, `.fetch`, `requests.`, `httpx.`, `urllib`, `fetch(`, `.get(`/`.post(`, `open(`, `read_text`, `stat(`, `exists(`, `glob(`, `subprocess.`, `os.system`, `Popen`.
3. **Follow one level of indirection.** For each loop body, check whether any helper it calls reaches a boundary. Read the helper; do not judge by its name.
4. **Check ORM queries for eager loading** and look for related-attribute access inside loops over their results.
5. **Count the trips per entry point.** For each finding, state N and what sets it: page size, row count, file count, list length from the workload map.
6. **Check whether a bulk API exists** — a `_many`/`bulk_`/`batch` method, an `IN` clause, an `executemany`, a multi-arg CLI. A batching suggestion with no available mechanism is not actionable; say what would have to be built.
7. **Look for repeated identical calls** within a single request path, not just loops.
8. **Note transaction and lock scope** around per-item writes — N round trips inside one transaction is a contention finding too; hand the lock half to `blocking`.

## Report Findings

For each chatty-I/O finding:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Boundary** | DB / HTTP / File / Subprocess / Cache / Queue |
| **Workload** | Entry point + cadence + what sets N (cite the workload map) |
| **Trips** | Calls now versus calls after the fix — e.g. `N+1 → 2`, where N = page size (50) |
| **Fix** | Concrete change — bulk endpoint, `IN` clause, eager loading, `executemany`, one subprocess with N args, concurrent gather |

### Severity Guide

- **Critical**: Round trips growing without a ceiling on a hot path — a per-item call over an unbounded collection, or a per-item write inside a held transaction that will saturate a pool and stall the service.
- **High**: N+1 or per-item calls on a path the map shows is hot, with N tied to a real dataset (page size, row count, file count).
- **Medium**: Per-item calls on a warm path, or on a hot path where N is small today but structurally unbounded; repeated identical fetches in one request.
- **Low**: Small fixed N, cold-path chattiness, and anything whose N you could not establish.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Workload | Boundary | Trips | Fix |
|---|----------|-----------|----------|----------|-------|-----|
| 1 | High | report.py:210 | ccreport run, N = sessions in window | DB | N+1 → 2 | Fetch all rows with `WHERE session_id IN (...)`, group in memory |

## Rules

- **State N and what sets it.** "N+1 query" without N is not a finding. N comes from the workload map: page size, row count, file count, list length.
- **Count trips, not lines.** One call site inside a loop is N trips; three call sites outside a loop are three.
- **Read the helper before judging the loop.** The most-missed N+1 is a property or repository method that looks like a field access.
- **Check that a batch mechanism exists** before recommending one. If it does not, say what would have to be built and cost the finding accordingly.
- **Weigh the boundary.** A subprocess spawn is orders of magnitude more expensive than a local file `stat`, which is more expensive than an in-process call. Rank accordingly.
- **You own the trips; `query-smells` owns the query and `payloads` owns the bytes.** Note the overlap and stay in your lane.
- **Never recommend batching that breaks recoverability or ordering** without saying so. Per-item commits exist for a reason more often than they look like they do.
- **Do not invent latencies.** "N+1 round trips per report run, N = one per session in the window" is defensible; "adds 300ms" is not.
