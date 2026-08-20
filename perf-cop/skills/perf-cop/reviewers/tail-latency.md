# Find Tail Latency

Scan the codebase for the cost of its slowest calls: work whose duration varies per caller, and paths where requests arrive faster than one server drains them. You own **the spread** — how far p99 sits from the median under normal load, and what widens the gap. Whether anyone waits at all, how a pool is sized and whether a lock is held over I/O, belongs to `blocking`; the same queue while a dependency is unwell is out of scope.

The distinguishing question is not "is this slow?" but "this is fast for most callers — which caller, which key, or which moment pays ten times the median, and why?"

A mean over a mixed distribution describes no request anyone was actually served. Every finding here names the dimension the spread runs along, and who sits at the far end of it.

## What to Look For

### Per-request cost that scales with what the caller owns

The highest-value pattern in the lens. Work proportional to a quantity the caller controls — a tenant's row count, a cart's line items, a document's length — has a median set by the median account and a p99 set by the largest one.

```python
# BAD: cost is the account's history; the biggest account is a different endpoint
@app.get("/dashboard")
async def dashboard(user):
    orders = await db.fetch_all(ORDERS_FOR_USER, user.id)   # 3 rows or 300,000
    return [enrich(o) for o in orders]                       # per-row work on top

# GOOD: bound what one request can carry
    orders = await db.fetch_all(ORDERS_PAGE, user.id, limit=100, offset=page)
```

The tells: a query filtered only by owner with no `LIMIT`, a serializer over a full relation, a sort or a group-by over a per-user collection, a loop whose n comes from one account's data. Say what bounds the quantity — a plan cap, a retention window, nothing at all.

### The miss path nobody times

A cache at a 95% hit rate leaves a median that measures the hit and a p99 that measures the miss. The miss pays the full uncached cost, and the tail is made entirely of misses.

Look for a cached read whose miss branch fans out into several calls, TTLs that expire together across keys, a working set larger than `maxsize`, and a cold store after every deploy or restart. Whether a cache should exist at all is `caching-wins`'; the cost of the branch that runs when it does not hit is yours.

### Retries stacked onto calls that were already slow

A retry fires where the first attempt timed out — on the tail, never on the median. Adding one moves p99 to timeout plus backoff plus a second attempt while p50 does not move at all.

```python
# BAD: p99 becomes 3 × 10 s of timeout plus the backoff between attempts
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def fetch(url):
    return requests.get(url, timeout=10)
```

Compare the retry total against the budget the caller sits inside. Whether the timeout exists is `blocking`'s; what the retry ladder does to the distribution is yours.

### A serialized path every request crosses

One lock, one connection, one single-threaded worker, one queue consumer. Queue delay does not rise linearly with load: the last tenth of a path's capacity costs more waiting than the first eight tenths, because each arrival waits behind whatever is already in front of it.

Variance is the other half. Two paths with the same mean service time queue differently — the one whose durations spread out builds a longer line at the same arrival rate. So a serialized path crossed by the variable work above is the compounding case, and worth its own finding.

Name the arrival rate from the workload map and the service time from the code. Where the map gives neither, say so; an unnamed utilization is not a finding.

### Background work sharing the request path

A cron, a report, a nightly export, a bulk flush or a reindex running against the same pool, loop or database as live requests. The distribution grows a second bump at that cadence: the median holds all day and p99 triples at the top of the hour.

Also in scope: a checkpoint, a compaction, a log rotation or a garbage-collection pause on the process that serves requests. Name the cadence and what the two workloads share.

### Fan-out where the slowest branch sets the total

A request that waits on N sub-calls finishes when the slowest returns. As N rises, the odds that no branch is slow fall, so a per-call tail becomes the request's median.

```python
# 10 branches, each with a rare slow case — most requests now contain one
results = await asyncio.gather(*[fetch(shard) for shard in shards])
```

Say what N is and where it comes from. The fixes are a bound on N, a per-branch deadline the caller enforces, or returning partial results.

### Measurement that records only the mean

A metric that stores a count and a sum, a log line reporting average duration, an alert threshold on a mean, a benchmark reporting one number. The tail this lens is about is invisible to all of them, so nothing in the codebase can show a regression in it.

This is a finding when the path is one you flagged above — the instrumentation gap is what keeps the other finding unmeasurable. Propose a histogram or percentile summary on that path, not across the codebase.

## What NOT to Flag

- **The speculative version of this lens: "this will not scale."** A percentile claim with no arrival rate, no size range and no named caller at the far end is the noise the Measurement Rule exists to kill. Report it at Low or not at all.
- **Uniform cost.** Where every call does the same fixed work over data that does not vary per caller, the median is the tail. Making it faster belongs to `hot-loops`, `io-batching` or `payloads`.
- **The mean cost itself.** A slow average call relabelled with a percentile is another lens's finding wearing this one's costume. Yours starts with a spread.
- **A path with one caller.** A CLI run by hand, a one-shot script, a migration: nothing arrives while it runs, so nothing queues and there is no distribution.
- **Pool starvation, lock scope and missing timeouts as such.** `blocking` owns whether the wait exists and how the resource is sized. You own what the wait's distribution looks like once it does.
- **A queue that backs up because a dependency is unwell.** That is failure behavior, not latency spread. Yours is the distribution when every dependency answers normally.
- **Work dropped, shed or expired under load.** Loss is not latency. Say which it is and file it where it belongs.
- **Percentiles you did not read.** No benchmark ran here. "p99 is 400 ms" is invented; "the tail is one query per order row, unbounded per account" is evidence.

## How to Scan

1. **Start from the workload map's entry points and cadence.** A path with no concurrent arrivals cannot produce a queueing finding, whatever its code looks like.
2. **For each hot entry point, name what varies per call.** Rows owned, items posted, bytes uploaded, keys requested, shards fanned out. Something the caller — not the codebase — sets.
3. **Bound each of those.** Find the `LIMIT`, the page size, the plan cap, the max upload. Where nothing bounds it, that is the finding and the range is "unbounded".
4. **Trace every cached read to its miss branch** and count what the miss does. Check `maxsize`, TTL and what a restart leaves behind.
5. **Find every retry ladder** — `@retry`, `tenacity`, `for attempt in range`, client-level retries — and add attempts times timeout plus backoff.
6. **Find the serialized crossings**: a single lock, a pool of one, a single consumer, a global rate limiter, a leader-only write path. For each, name arrival rate and service time or say `UNKNOWN`.
7. **List everything scheduled** — cron, timers, `@repeat_every`, queue workers — and check which share a pool, loop or database with the request path.
8. **Find fan-out**: `gather`, `Promise.all`, a thread-pool map, a loop of calls awaited together. Name N and its source.
9. **Read what the code measures.** Grep for `histogram`, `percentile`, `p95`, `p99`, `timing`, `observe`, and for mean-only counters and sum/count pairs.
10. **For every finding, name who is at the tail**: the largest tenant, the cold key, the request that arrived at :00, the fan-out that drew one slow shard.

## Report Findings

For each tail-latency finding:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Kind** | Per-caller size / Miss path / Retry stacking / Serialized path / Background interference / Fan-out max / Mean-only measurement |
| **Workload** | Entry point + cadence + data size (cite the workload map) |
| **What varies** | The dimension the spread runs along, and its range from the snapshot |
| **Who is at the tail** | The caller, key, shard or moment that pays it |
| **Fix** | Concrete change — bound the per-caller quantity, page it, cap the retry total, give fan-out a deadline, move the batch job off the request pool, record a histogram |

### Severity Guide

- **Critical**: A spread that compounds with load rather than settling — a serialized path whose arrival rate reaches its service rate, or a retry ladder feeding the queue it is waiting on. The tail does not lengthen, it runs away.
- **High**: A user-facing tail on a hot path with a named unbounded dimension — a per-account query with no `LIMIT` on a request route, a miss branch that fans out, a nightly job sharing the request pool.
- **Medium**: Spread on a warm path, or on a hot path at concurrency the codebase has not reached yet. Mean-only measurement of a path you flagged above.
- **Low**: Cold paths, single-caller processes, and any spread whose dimension or range you could not establish.

The Critical/High split is the general one: Critical degrades further as load rises, High is a long wait that one caller feels at today's load.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Workload | Kind | What varies | Who is at the tail | Fix |
|---|----------|-----------|----------|------|-------------|--------------------|-----|
| 1 | High | api/dashboard.py:31 | GET /dashboard, per request | Per-caller size | rows per account, 3 to unbounded | the largest account, on every load | Paginate the query and enrich one page |

## Rules

- **Name the dimension, or it is not a tail finding.** "This could be slow" is a guess; "the cost is one row per order, unbounded per account" is a finding.
- **Name who is at the tail.** A percentile with no caller behind it is a statistic nobody can act on.
- **A spread needs two ends.** Give the cheap case and the expensive case from the snapshot. One number is a mean finding, and a mean finding belongs to another lens.
- **No arrivals, no queueing finding.** Check the cadence before writing anything about utilization.
- **Say `UNKNOWN` for a rate or a bound you did not read.** An asserted arrival rate is how this lens produces confident nonsense.
- **Do not invent percentiles, timings or hit rates.** Nothing here was measured; say what the code shows.
- **Hand the average call to the other lenses.** If the fix makes every request faster by the same amount, it is `hot-loops`', `io-batching`' or `payloads`'.
- **Hand the resource itself to `blocking`.** Pool size, lock scope and missing timeouts are theirs; the distribution across them is yours.
- **Never propose a bound that silently truncates results.** Pagination, a deadline and partial results each change what the caller receives — say which, or do not propose it.
