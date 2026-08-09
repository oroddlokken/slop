# Find Allocation Waste

Scan the codebase for memory spent on work that produced nothing: copies nobody needed, strings rebuilt character by character, whole datasets materialized to read one field, and collections that grow without a bound. You own **memory volume in process**. The size of data crossing a boundary belongs to `payloads`; the cost of iterating belongs to `hot-loops`.

Memory findings split cleanly into two kinds, and only one of them is ever Critical: **waste** (transient garbage, more allocation than needed) and **growth** (something that never gets released). Growth takes the process down; waste just costs.

## What to Look For

### Unbounded collections (the growth case)

A structure that accumulates and is never trimmed, evicted, or scoped to a request. Module-level lists and dicts are the usual carrier, because their lifetime is the process.

```python
# BAD: one entry per record, forever, for the life of the process
_seen = []
def record(entry):
    _seen.append(entry)      # nothing ever removes from _seen
```

Also: history or audit lists on long-lived objects, `list` accumulators inside `while True` loops, dedupe sets keyed on unbounded input, registries appended to on every call, closures capturing large objects held by a long-lived callback. Ask one question — **what removes an entry?** No answer means the answer is nothing.

(Caches specifically are shared ground: unbounded *cache* growth as a correctness bug is codehealth's `caching`. Flag it here as memory growth when the structure is an accumulator rather than a cache.)

### Whole datasets materialized to read a slice

Loading everything into a list when the code consumes it once, or filters it to a handful:

```python
# BAD: every line in memory to keep the ones from today
lines = path.read_text().splitlines()
today = [l for l in lines if l.startswith(prefix)]

# GOOD: streams, peak memory is one line
with path.open() as fh:
    today = [l for l in fh if l.startswith(prefix)]
```

The tells: `.read()`/`read_text()` on a file whose size is not bounded, `list(cursor.fetchall())`, `list(generator)` immediately consumed once, `json.load` of a growing document, a comprehension where a generator expression feeds the same consumer.

### String building in a loop

Concatenating in a loop reallocates and copies the accumulated string each iteration — O(n²) bytes copied for n appends.

```python
# BAD: rebuilds the whole string per row
out = ""
for row in rows:
    out += render(row) + "\n"

# GOOD
out = "\n".join(render(row) for row in rows)
```

Same shape: `bytes` `+=` in a loop, repeated `str.replace` chains over a large document, f-string assembly of a report row by row into one accumulator, building a query string by concatenation across thousands of values.

### Defensive copies nobody needed

`list(x)`, `dict(x)`, `x[:]`, `copy.deepcopy(x)` where the copy is never mutated and the original never escapes. Per call on a hot path, over a large structure, this is pure garbage. `deepcopy` is the expensive one — flag it specifically when it appears per item or per request over a nested structure.

The inverse is a correctness bug, not a perf finding: if the copy is what stops a caller mutating shared state, it stays. Confirm before flagging.

### Repeated conversions and re-parsing

The same value converted back and forth per item: `str(x)` then `int(...)` again, `json.dumps`/`json.loads` round-tripping to copy a structure, `list(d.keys())` where `d` would iterate, `Decimal(str(float))` chains, encoding and decoding the same bytes. Also re-parsing a document per call that a module constant could hold once — though if the parse is at import, it is `startup`'s.

### Per-item object construction on a large parse

Building a full validated model instance per row over a million rows, when the code reads two fields. Also intermediate lists between every stage of a pipeline (`sorted(list(filter(...)))` chains), each holding a full copy of the data at that stage.

### Objects that outlive their use

Large locals held alive by a long function, a big response body retained on an object after the fields were extracted, references kept in an exception traceback path, a `self._raw` that nothing reads after `__init__`.

## What NOT to Flag

- **The speculative version of this lens: copies in code that runs once.** A `deepcopy` at config load, a `list()` of settings at import, a defensive copy in a CLI's argument parsing — one allocation of a small structure, one time. This is the noise this lens generates by default; do not.
- **Small fixed-size copies anywhere.** Copying a 10-element list per request is not a finding at any cadence. Size matters as much as frequency.
- **Copies that exist for safety.** A copy protecting a caller from mutating a cached or shared structure is load-bearing. If you are unsure, do not flag it — a memory saving that introduces aliasing is a bug you created.
- **Idiomatic short-lived garbage.** A comprehension that builds a list the next line consumes, a temporary tuple, an f-string. Runtimes are built for this; the allocator is not the bottleneck.
- **Generator-versus-list preference with no size behind it.** "Use a generator" over a collection you cannot show is large is style. The Measurement Rule applies: no size, no severity above Low.
- **Interning, `__slots__`, and object-layout tuning** unless the workload map shows millions of instances alive at once. Otherwise it is a micro-optimization that costs readability.
- **Bounded caches doing their job.** An `lru_cache(maxsize=512)` is not unbounded growth. Check for the bound before flagging.
- **Test data and fixtures.** A test that builds 10K objects is fine.

## How to Scan

1. **Split your search in two from the start**: growth (what is never released) and waste (what is allocated and thrown away). They get different severities.
2. **Find module-level mutable state**: module-scope `[]`, `{}`, `set()`, `defaultdict`, class attributes that are containers. For each, find every write and ask what removes.
3. **Grep for whole-file and whole-result reads**: `read()`, `read_text()`, `readlines()`, `fetchall()`, `json.load`, `list(` wrapping a generator or cursor.
4. **Grep for `+=` on a string or bytes inside a loop**, and for `join` absent where a loop builds text.
5. **Grep for copies**: `deepcopy`, `copy(`, `list(`, `dict(`, `[:]`, `.clone()`, `{...spread}` — then check whether the result is mutated.
6. **Trace pipelines** for stacked intermediates: `sorted(list(filter(map(...))))` and its equivalents.
7. **For every candidate, get the size** from the workload map's data-source table: how many rows, how many files, how large the document. No size, no finding above Low.
8. **Check what is already bounded** before claiming growth — a TTL, a `maxsize`, a periodic clear, a request-scoped lifetime.

## Report Findings

For each allocation finding:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Kind** | Growth (never released) / Waste (allocated and discarded) |
| **Workload** | Entry point + cadence + how large the structure gets (cite the workload map) |
| **Volume** | What is allocated, how much per invocation, whether it scales with input |
| **Fix** | Concrete change — stream instead of materialize, `join` instead of `+=`, drop the copy, bound the collection |

### Severity Guide

- **Critical**: Unbounded growth in a long-lived process — an accumulator with no eviction, on a service or daemon. The process dies; it does not merely slow down.
- **High**: Memory proportional to a growing dataset on a hot path — materializing an unbounded file or result set per request, O(n²) string building over real data.
- **Medium**: Real waste on a warm path — per-item `deepcopy`, stacked intermediate lists over a large collection, repeated conversions per record.
- **Low**: Small or cold-path copies, generator-versus-list preferences, and anything whose size you could not establish.

An unbounded accumulator in a short-lived CLI is **not** Critical — the process exits and the memory goes with it. Say so and rate it Medium or Low.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Workload | Kind | Volume | Fix |
|---|----------|-----------|----------|------|--------|-----|
| 1 | High | reader.py:60 | ccreport run, all sessions, glob grows without bound | Waste | full record list held to filter 14 days | Stream and filter per line |

## Rules

- **Growth and waste are different findings with different ceilings.** Only growth reaches Critical, and only in a process that lives long enough to reach the ceiling.
- **Name the size or stay at Low.** "Allocates a list" is not a finding; "allocates one list per JSONL line across a directory with no bound" is.
- **Check for a bound before calling anything unbounded** — TTL, maxsize, periodic clear, request scope.
- **Verify a copy is not load-bearing before proposing its removal.** Aliasing bugs are worse than the memory they save.
- **Process lifetime changes severity.** The same accumulator is Critical in a daemon and a non-issue in a script that exits in 200 ms. Read the workload map's entry points first.
- **Do not invent byte counts.** "One full copy of the parsed record set per call" is a measurement you can defend; "about 40MB" is not.
- **`payloads` owns bytes crossing a boundary; you own bytes in the heap.** If the fix is fetching fewer rows rather than holding them differently, it is theirs.
