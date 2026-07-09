# Find Caching Problems

Scan the codebase for caching that returns wrong data, leaks memory, exposes one user's data to another, or is missing where it would prevent repeated expensive work. Cover both application-level caches (memoization, in-memory dicts, `lru_cache`, Redis/Memcached) and HTTP response caching.

## What to Look For

### Per-user or sensitive data in a shared cache
The highest-impact caching bug: a cache keyed without the user/tenant identity, so one user is served another user's data. Treat this as a data-leak vulnerability, not a performance issue.

```python
# BAD: cache key omits the user — every caller gets the first user's profile
@lru_cache
def get_profile():
    return db.fetch_profile(current_user.id)

# GOOD: identity is part of the key
@lru_cache
def get_profile(user_id):
    return db.fetch_profile(user_id)
```

Also flag: auth tokens, permissions, or session data cached with a long TTL — a revoked token keeps working until the entry expires.

### Cache keys that miss inputs (stale or wrong results)
The cached value depends on an input that isn't in the key, so the cache returns a value computed for different inputs.

```python
# BAD: result depends on `currency` and `region`, but the key is just `product_id`
def price(product_id, currency, region):
    return _price_cache.get_or_set(product_id, lambda: compute(product_id, currency, region))
```

The key must capture every input the cached value depends on. A key that's too narrow returns wrong results; a key that includes irrelevant or non-deterministic parts (timestamps, request IDs) never hits.

### Missing invalidation (serving stale data after a write)
A value is cached on read but the cache isn't cleared when the underlying data changes, so writes don't take effect until the entry expires. Flag write paths (update/delete/save) that touch data which is cached elsewhere with no matching invalidation, and indefinitely-cached data that does change (no TTL, no eviction on write).

### Negative caching done wrong (caching absence, misses, and errors)
Caching "no result" — `None`, empty, 404, a raised exception — has its own failure modes distinct from caching real values:

- **A negative entry that outlives the condition.** Caching "user X does not exist", then X is created, but the negative entry persists with no TTL and no invalidation on the create path — so the new record stays invisible until the entry expires. Negative entries need a short TTL *and* invalidation on the corresponding write.
- **A cached transient error.** A timeout or 5xx gets stored and served long after the dependency recovers, turning a blip into a sustained outage. Errors should not be cached, or only with a very short TTL.

```python
# BAD: a missed lookup is cached forever; once it's a miss, it stays a miss
def get_user(user_id):
    if user_id in _cache:           # caches None on miss, never expires
        return _cache[user_id]
    user = db.find(user_id)         # user created later never becomes visible
    _cache[user_id] = user
    return user
```

The flip side is a finding too: **no negative caching where missing keys are hot.** Repeated lookups for keys that will never hit (probing random IDs, a hot absent key) bypass the cache every time and hammer the backend (cache penetration). A short-TTL negative entry protects against it. Also flag **sentinel ambiguity** — using `None`/falsy both for "not cached" and "cached as absent", so a miss can't be told from a cached absence.

### Unbounded caches (memory growth)
A cache with no size limit and no expiry grows until the process runs out of memory — common with module-level dicts used as caches and with `lru_cache(maxsize=None)` over an unbounded key space (e.g. keyed on request payloads or user IDs).

```python
# BAD: grows forever, one entry per distinct argument, never evicted
_cache = {}
def expensive(arg):
    if arg not in _cache:
        _cache[arg] = compute(arg)
    return _cache[arg]
```

Bound it: `lru_cache(maxsize=N)`, a TTL/size-capped store (`cachetools.TTLCache`, Redis with expiry), or an explicit eviction policy.

### `lru_cache` on instance methods
`functools.lru_cache` on a method keys on `self`, so it holds a reference to every instance the method was ever called on — the instances can never be garbage-collected (a memory leak), and the cache is shared across all instances rather than per-instance. Prefer `functools.cached_property` for per-instance memoization, or cache on a key derived from the relevant fields rather than the whole object.

### Caching shared mutable objects
Returning a cached mutable object (list, dict, dataframe, model instance) hands every caller the same reference. One caller's mutation silently corrupts the cached value for everyone else. Flag caches that store and return mutable values without copying; the value should be immutable or returned as a copy.

### Cache stampede on miss
On a cold or expired entry, many concurrent requests all miss and recompute the same expensive value at once (thundering herd), spiking load exactly when the cache was supposed to protect against it. High-traffic recompute paths should single-flight the work (a lock, a "compute once" primitive, or staggered/early refresh).

### Missing caching on expensive repeated work
Caching's absence is also a finding. Flag pure, deterministic, expensive work repeated with the same inputs on a hot path with no memoization — repeated identical network/file reads in a request, recomputing a derived value every call. Only flag when the inputs are stable and the result is safe to reuse; don't suggest caching where staleness or per-user data makes it unsafe.

### HTTP and response caching gaps
- Responses for static or slow-changing content served with no `Cache-Control`/`ETag`, forcing every client to refetch.
- User-specific or authenticated responses cached publicly (`Cache-Control: public` on private data) — a shared-cache leak in HTTP form.

## How to Scan

1. **Find cache decorators and helpers**: `lru_cache`, `@cache`, `cached_property`, `memoize`, `@cached`, `cachetools`, `TTLCache`
2. **Find cache stores**: `redis`, `memcache`, `cache.get`/`cache.set`, module-level dicts assigned once and reused as `_cache`/`_CACHE`
3. **Check keys against inputs**: for each cached function, compare the cache key to the function's parameters and any captured globals/`self` — flag inputs that affect the result but aren't in the key
4. **Check bounds**: every cache — does it have a `maxsize`, TTL, or eviction policy? Unbounded ones grow without limit
5. **Check invalidation**: search write paths (`save`, `update`, `delete`, `INSERT`/`UPDATE`/`DELETE`) for whether they invalidate caches that read the same data — including negative entries (a cached "not found" cleared when the record is created)
6. **Check negative caching**: for caches that store `None`/empty/404/errors, confirm those entries have a TTL and aren't served after the condition resolves; for hot missing-key lookups, check whether absence is cached at all
7. **Check identity in keys**: caches of user/tenant/session data — is the user/tenant ID part of the key?
8. **Check HTTP headers**: `Cache-Control`, `ETag`, `Expires`, `max-age`, `public`/`private`

## Report Findings

For each caching problem:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Type** | Shared-cache leak / Incomplete key / Missing invalidation / Negative-cache bug / Unbounded cache / Method lru_cache / Mutable cached value / Stampede / Missing cache / HTTP cache gap |
| **Current** | What the cache does now |
| **Impact** | Data leak (whose data reaches whom?), correctness (stale/wrong results?), memory (growth rate?), or performance (work repeated how often?) |
| **Fix** | Concrete solution — show the corrected key, the bound, the invalidation hook, or the copy |

### Severity Guide

- **Critical**: Per-user/sensitive data served from a shared cache, or public HTTP caching of private data — cross-user data exposure
- **High**: Cache key missing an input that changes the result (wrong data returned); missing invalidation on data that must be current (prices, balances, permissions); a negative entry not cleared on create, so a newly-created record stays invisible; unbounded cache that will exhaust memory in production
- **Medium**: `lru_cache` on instance methods; cached mutable objects shared by reference; stampede risk on a hot path; cached transient errors served after recovery; missing cache (positive or negative) on clearly expensive repeated work
- **Low**: Suboptimal TTL tuning, redundant cache layers, minor missing-cache opportunities

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Type | Impact | Fix |
|---|----------|-----------|------|--------|-----|
| 1 | Critical | path:line | Shared-cache leak | User A sees User B's profile | Add user_id to the cache key |

## Rules

- **A cache that can return another user's data is Critical** — the cost is a data breach, not a slow page, so it outranks every performance finding.
- **Verify the key against the real inputs before flagging a stale-result bug** — read what the function actually depends on (parameters, `self`, captured globals); a key that looks thin may be fine if the omitted value is constant.
- **Missing caching is a finding only when reuse is safe** — the work must be deterministic and the same inputs must recur on a hot path; never suggest caching per-user or fast-changing data, because the staleness risk outweighs the saved cycles.
- **Match the fix to the ecosystem** — Python has `lru_cache`/`cached_property`/`cachetools`; web frameworks have response-cache middleware and `Cache-Control`; distributed caches use Redis/Memcached TTLs. Suggest the mechanism that already fits the codebase.
- **Caching owns the cache layer; query-smells owns the query.** When a database result is cached, query-smells flags the query itself (N+1, injection, missing index); this lens flags the cache around it (key correctness, invalidation, eviction, leak). If a finding is purely about the SQL, defer to query-smells.
