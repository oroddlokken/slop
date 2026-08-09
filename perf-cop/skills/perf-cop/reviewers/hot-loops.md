# Find Hot-Loop Cost

Scan the codebase for algorithmic cost in code paths that run per request, per record, or per render. You own **in-process CPU**: how much work happens per item and what complexity class the loop belongs to. Round trips across a boundary belong to `io-batching`.

The lens is not "this loop could be faster". It is "this loop's cost grows with something that grows, on a path the workload map shows is entered often."

## What to Look For

### Quadratic work over I/O-sourced collections

The single highest-value pattern. A nested loop over two collections that came from the outside — query results, parsed files, an API page — is O(n·m) with no ceiling.

```python
# BAD: one pass over records per session; both grow with history
for session in sessions:              # n from a glob over ~/.claude/projects
    for record in all_records:        # m from parsing every JSONL line
        if record.session_id == session.id:
            session.records.append(record)

# GOOD: one pass, index by key
by_session = defaultdict(list)
for record in all_records:
    by_session[record.session_id].append(record)
```

Also count the hidden inner loop: `list.index()`, `in` against a list, `remove()`, `max(... key=)` over a list, a `filter` comprehension — each is O(n) inside whatever encloses it.

### Membership tests against a list

`x in some_list` is a linear scan. Inside a loop over n items against a list of m, that is O(n·m) written as one clean line. A `set` or `dict` makes it O(n). This is the cheapest real fix in the lens and it hides everywhere.

### Sorting, regex compilation, or parsing inside a loop

Work that should happen once, repeated per item:

```python
# BAD: recompiles the pattern n times, re-sorts the same list n times
for line in lines:
    if re.match(r"^\d{4}-\d{2}-\d{2}", line):   # compiled per line
        rows = sorted(all_rows, key=lambda r: r.ts)   # re-sorted per line
```

Hoist the invariant out. Also: `datetime.strptime` on a fixed format, `json.loads` of a config re-read per item, building the same lookup table per iteration, constructing a client or connection object per item.

### Repeated full scans of the same collection

The same list walked three times in one function (`sum()`, then `max()`, then a comprehension) is three passes where one would do — real only when n is large. More serious: a full scan inside a loop that a precomputed index would answer in O(1).

### Recomputation of a loop-invariant value

`len(items)` recomputed per iteration is nothing; `compute_rates()` or a database-derived lookup recomputed per iteration is the finding. Distinguish by the cost of the invariant, not by its position.

### Growth in the wrong dimension

A loop whose per-iteration cost itself grows: appending to a list and re-scanning it, string concatenation building an ever-longer string (see `allocations`), a set difference recomputed against a growing accumulator. n iterations each costing O(current size) is O(n²) with no nested loop in sight.

### Exceptions or heavy machinery as control flow in a loop

Raising and catching per item, constructing a full exception object per miss, deep-copying a structure per item, or instantiating a dataclass-with-validation per row in a million-row parse. Fine once, expensive per record.

## What NOT to Flag

- **Loops over fixed-size collections.** A loop over a 5-element config tuple, a list of 7 window definitions, or a hardcoded set of model names is O(1) with a large constant of 5. Even a triple-nested loop over three such lists is 125 operations, not a finding.
- **Micro-optimizations with no complexity change.** `for i in range(len(x))` versus `enumerate`, a comprehension versus a `for` loop, local-variable lookup caching, `map()` versus a generator expression. If the fix does not change the complexity class or remove real work per item, it is style, and style is codehealth's.
- **The speculative version of this lens: "this could be vectorized."** Suggesting numpy, a different data structure, or a rewrite for a loop you cannot place on a hot path or size is exactly the noise the Measurement Rule exists to kill. If you cannot name n, report it at Low or not at all.
- **One-time setup loops.** A loop at import, at config load, or in a migration that runs once. If it runs before the first request, it belongs to `startup`; if it runs once ever, it is not a finding.
- **Loops in tests, fixtures, and benchmark harnesses.** Slow tests are a real complaint but not this lens's — and a benchmark loop is supposed to run n times.
- **Optimal algorithms that merely look busy.** A single pass with several operations per item is linear. Count passes and nesting, not lines.
- **Cost the language already amortizes.** `list.append` is amortized O(1); `dict` lookup is O(1). Do not flag them as if they were not.

## How to Scan

1. **Start from the workload map, not from the code.** List the entry points with the highest cadence, then trace outward. A loop you cannot reach from a hot entry point cannot be a High.
2. **Find nested loops**: `for` inside `for`, `while` inside `for`, a comprehension inside a loop, a loop inside a function called from a loop (the nesting is often split across two functions — follow the call).
3. **For each loop, name the source of the iterable.** Literal, config constant, function argument, query result, `glob()`, `readlines()`, API response. Only the last four can grow.
4. **Grep for linear operations inside loop bodies**: ` in `, `.index(`, `.remove(`, `sorted(`, `.sort(`, `max(`, `min(`, `sum(`, `re.match`/`re.search`/`re.compile`, `json.loads`, `strptime`, `deepcopy`, `.count(`.
5. **Check what is hoistable.** For each loop, ask which expressions do not depend on the loop variable.
6. **Follow the accumulator.** Does anything inside the loop grow, and is that growing thing read inside the same loop?
7. **Cite a size hint for every finding** from the workload map's data-source table — the glob, the table, the page size, the retention window.

## Report Findings

For each hot-loop finding:

| Field | Content |
|-------|---------|
| **Location** | file:line range |
| **Workload** | Entry point + cadence + what bounds n (cite the workload map) |
| **Complexity** | Current class and the class after the fix — e.g. `O(n·m) → O(n+m)` |
| **Cost** | What the work is per item, and what n plausibly is |
| **Fix** | Concrete change — index by key, hoist the invariant, set instead of list, single pass |

### Severity Guide

- **Critical**: Worse-than-linear complexity over an input with no ceiling, on a path the map shows is hot — the runtime does not degrade, it stops. A nested scan over a directory that grows forever, run per render.
- **High**: Measurable per-request or per-render CPU on a hot path — a recompiled regex or a re-sort inside a loop over a real dataset, an O(n·m) where both are bounded but large.
- **Medium**: Real cost on a warm path, or quadratic behavior over an input that is small today but has no structural bound.
- **Low**: Cold-path loops, micro-optimizations, and anything whose n you could not establish.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Workload | Complexity | Cost | Fix |
|---|----------|-----------|----------|------------|------|-----|
| 1 | High | reader.py:88-104 | statusline render, ~1/s, n = all session files | O(n·m) → O(n+m) | one scan of all records per session | Index records by session_id once |

## Rules

- **Name n or drop the severity.** A complexity claim without a size claim is arithmetic, not a finding. `O(n²)` where n is 6 is 36.
- **Count passes and nesting, not lines.** A dense single-pass loop is cheaper than three tidy ones.
- **Follow the call chain before deciding the loop is flat.** The second loop is often inside a helper the first loop calls; that is the most-missed quadratic.
- **Do not invent timings.** Say "one full scan of the record set per session", never "about 200ms".
- **You own in-process CPU; `io-batching` owns round trips.** A loop that makes a network or database call per item is theirs to count. Flag it here only for the arithmetic around the call, and say so.
- **Never trade correctness for speed.** If the single-pass version changes ordering, dedup behavior, or error semantics, say so in the fix or do not propose it.
