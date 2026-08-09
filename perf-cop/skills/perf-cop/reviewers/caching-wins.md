# Find Cacheable Recomputation

Scan the codebase for expensive work repeated with the same inputs on a path that runs often, where memoization would remove it outright. You own **the absence of a cache where one would pay**. Whether an existing cache is *correct* — key completeness, invalidation, cross-user leaks, unbounded growth — belongs to codehealth's `caching`; a correct cache that still misses a hot recomputation is yours.

The lens has one governing constraint: caching trades memory and staleness for time. A cache proposed where reuse is unsafe is not a performance win, it is a correctness bug you introduced. Every finding here must clear both bars — **the work recurs with identical inputs**, and **reusing the result is safe**.

## What to Look For

### The same pure computation repeated per item or per call

Deterministic work recomputed with inputs that repeat:

```python
# BAD: the rate table is rebuilt for every record, and it is the same table every time
for record in records:
    rates = load_exchange_rates()          # identical result, once per record
    record.nok = record.usd * rates[record.day]

# GOOD: compute once, reuse
rates = load_exchange_rates()
for record in records:
    record.nok = record.usd * rates[record.day]
```

When the repetition is inside one function, the fix is hoisting and it is `hot-loops`' finding. When it recurs **across calls** — a helper called from many places, each rebuilding the same table — the fix is memoization and it is yours.

### Derived values recomputed on every access

A property, formatter, or accessor that recomputes a value from unchanged fields on every read: parsing a timestamp, deriving a project key from a path, normalizing a name, computing a hash of a stable object, rebuilding a lookup dict from a static config. `functools.cached_property` or a module-level memo removes them.

### Repeated identical reads of unchanging data

The same config file, schema, template, pricing table, or lookup dataset read and parsed by several call sites in one run. Read once, hold the parsed result.

Note the boundary: if the same *code path* fetches per item with different keys, the fix is batching and it belongs to `io-batching`. Memoization helps when the *inputs repeat*; batching helps when they differ.

### Recompilation and reconstruction of expensive objects

Regexes, template objects, parsers, serializers, HTTP clients, `Decimal` contexts, timezone objects, and formatters rebuilt per call. Constructing a client per call also costs a connection, which makes it an `io-batching` concern too — say which half you are claiming.

### Aggregations recomputed from raw data every run

A total, rollup, or report rebuilt by scanning the full corpus each time, where the inputs for older windows can no longer change. Precomputed rollups, materialized views, or an incremental accumulator turn a full scan into a small read. Only propose it where the older data is genuinely immutable — otherwise the "cache" is a stale-data bug.

### Cross-invocation work in a per-invocation process

A CLI or hook that re-derives the same result on every run, where the result could persist to disk or SQLite between runs: a parsed corpus, a resolved dependency graph, a fetched exchange rate, a fingerprinted scan. The cost is paid on every invocation, so at a per-prompt cadence it is the dominant cost. Include an invalidation key (content hash, mtime, script hash) in the proposal — a persisted cache with no invalidation story is a bug, not a win.

### A cache that exists but is bypassed

A memoized helper called around, a cache checked on one path and not another, a `cached_property` recomputed by calling the underlying method directly, a rollup table available but the query still scanning raw rows. The infrastructure is already there; the hot path does not use it.

## What NOT to Flag

- **The speculative version of this lens: caching work that runs once.** A value computed at startup, in a one-shot command's main, or at config load has no second call to serve from cache. Adding a cache there is pure complexity.
- **Caching where the inputs do not repeat.** Memoizing a function called once per unique id, over an unbounded id space, buys nothing and leaks memory. Show that the same inputs recur before proposing it — that is the whole finding.
- **Caching non-deterministic or time-dependent results.** Anything reading the clock, random state, the filesystem's current contents, or a mutable global. If the result can differ between calls, reuse changes behavior.
- **Caching per-user, per-tenant, or permission-sensitive data as a shortcut.** The identity has to be in the key, and the moment the fix requires a careful key, it is a correctness design and codehealth's `caching` owns the review of it. Do not hand-wave it.
- **Caching fast-changing data to save a cheap computation.** Staleness risk for a few microseconds is a bad trade. The work must be genuinely expensive: I/O, parsing, a large computation, a network call.
- **Cheap arithmetic and attribute access.** Memoizing `a + b` costs more in dict lookups and memory than it saves.
- **Work already cached.** Check for `lru_cache`, `cached_property`, an existing store, a rollup table, or framework-level caching before flagging. Re-proposing an existing cache is the most embarrassing false positive in this lens.
- **The correctness of an existing cache.** Wrong key, missing invalidation, unbounded growth, stale reads — all real, all codehealth's `caching`. Mention it in one line and move on.

## How to Scan

1. **List what is already cached first**, from the workload map's caching section: decorators, stores, module-level memos, rollup tables, HTTP cache headers. Everything you propose must not already exist.
2. **Find expensive pure functions**: ones doing file I/O, parsing, regex compilation, network calls, or heavy computation, whose result depends only on their arguments.
3. **Count their call sites and the inputs at each.** The finding requires the *same* inputs recurring — trace the arguments, do not assume.
4. **Grep for repeated identical reads**: the same path opened in several modules, the same config parsed more than once, the same query issued from two helpers in one request path.
5. **Grep for per-call construction**: `re.compile`, `Template(`, `Session(`, `client(`, `ZoneInfo(`, `Decimal(` inside functions rather than at module scope.
6. **Look for properties and accessors** that compute rather than return.
7. **For full-corpus aggregations, check immutability**: can the inputs for a past window still change? If yes, a rollup is a bug; if no, it is the highest-value finding in this lens.
8. **For each proposal, state the invalidation story** — what makes the entry wrong, and what clears it. No story, no finding.
9. **Bound every proposal**: `maxsize`, TTL, or a key space you can show is small. An unbounded memo is a leak, which is `allocations`' Critical.

## Report Findings

For each caching-wins finding:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Kind** | Repeated pure call / Recomputed derived value / Repeated read / Per-call construction / Full-corpus recompute / Cross-invocation recompute / Cache bypassed |
| **Workload** | Entry point + cadence + how often the same inputs recur (cite the workload map) |
| **Repetition** | How many times the identical result is computed, and what the work costs each time |
| **Safety** | Why reuse is safe — deterministic, inputs stable, data immutable — and what invalidates the entry |
| **Fix** | Concrete mechanism with a bound — `lru_cache(maxsize=N)`, `cached_property`, hoist to module scope, persist to the existing cache DB keyed on a content hash |

### Severity Guide

- **Critical**: Reserved. A missing cache does not take a system down — it only costs time, and by this skill's definitions Critical means unbounded growth or outage scale. If a recomputation genuinely saturates a shared resource, the finding is `io-batching`'s or `blocking`'s, not this lens's. Report at most High.
- **High**: Expensive work recomputed on every invocation of a hot path with identical inputs and a clean invalidation story — a full-corpus scan per render, a config parse per record, a network fetch per call.
- **Medium**: Repeated work on a warm path; per-call construction of expensive objects; an existing cache bypassed on one path.
- **Low**: Small recomputations, cold-path memoization, and anything where you could not show the inputs recur or the reuse is safe.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Workload | Kind | Repetition | Safety | Fix |
|---|----------|-----------|----------|------|------------|--------|-----|
| 1 | High | exchange.py:70 | per record, all records in run | Repeated read | rate table rebuilt once per record | rates immutable per date | Module-level memo keyed on date, bounded by the window |

## Rules

- **Show the inputs recur.** This lens's finding is not "this is expensive" — `hot-loops` owns that — it is "this is expensive *and computed again with the same arguments*". Without the second half there is nothing to cache.
- **State the invalidation story in every finding.** What makes the cached value wrong, and what clears it. A proposal without one is a stale-data bug.
- **Bound every cache you propose.** `maxsize`, TTL, or a demonstrably small key space. An unbounded memo trades a time cost for a memory leak.
- **Never propose caching per-user, permission, or fast-changing data to save time.** The staleness risk outranks the cycles, every time.
- **Check what is already cached before proposing anything.**
- **Defer to `io-batching` when the fix is batching.** Same inputs recurring → memoize (yours). Different inputs fetched one at a time → batch (theirs).
- **Hoisting inside one function is `hot-loops`'; memoizing across calls is yours.** If the fix is moving a line out of a loop, hand it over.
- **Match the mechanism to the codebase.** Use the memoization and cache infrastructure that already exists here rather than introducing a new dependency.
- **Do not invent hit rates or timings.** "Recomputed once per record, ~N records per run" is defensible; "95% hit rate" is not.
