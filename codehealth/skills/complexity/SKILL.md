---
name: complexity
description: "Find complexity hotspots: long functions, deep nesting, high branching, and large files that are hardest to maintain and most likely to contain bugs."
args:
  - name: path
    description: The directory to scan (optional, defaults to cwd)
    required: false
user-invokable: true
---

# Find Complexity Hotspots
This skill scans code and reports findings — it does not modify code. It can run standalone or as part of `/codehealth`. Examples are Python; apply equivalent patterns for your target language.

Scan the codebase for mechanically complex code — functions that are too long, too deeply nested, or have too many branches. These are the places where bugs hide and maintenance is most expensive.

## What to Look For

### Long functions
- Functions over 50 lines — hard to hold in your head
- Functions over 100 lines — almost certainly doing too many things
- Methods that scroll past one screen — readers lose context

### Deep nesting
- Code indented 4+ levels deep — hard to trace which branch you're in
- Nested conditionals (`if` inside `if` inside `if`)
- Nested loops (especially with conditionals inside)
- Callback pyramids / promise chains nested 3+ levels

### High branching
- Functions with 5+ `if/elif/else` branches — consider a lookup table or strategy pattern
- Long `switch/case` or `match` statements — often signals missing polymorphism
- Multiple boolean flags controlling flow (`if x and not y or z`)

### Large files
- Files over 500 lines — probably doing too many things
- Files over 1000 lines — almost certainly need splitting
- Files with 10+ function/class definitions — low cohesion

### Complex expressions
- Boolean expressions with 3+ conditions
- Nested ternary operators
- List comprehensions with multiple conditions and nested loops
- Regular expressions without comments explaining what they match
- Long method chains (5+ chained calls)

### God classes / god functions
- Classes with 15+ methods — too many responsibilities
- Functions that accept 6+ parameters — doing too many things
- Functions that modify global state and return values and have side effects

## How to Scan

1. **Sort files by size** — start with the largest source files
2. **Sort functions by line count** — find the longest functions
3. **Search for deep indentation** — 4+ tabs or 16+ spaces at line start
4. **Count branches per function** — `if`, `elif`, `else`, `case`, `when`, `catch`
5. **Check parameter counts** — functions with 5+ parameters
6. **Look for complexity comments** — `# TODO: refactor`, `# this is complex`, `# sorry`

### Complexity Thresholds

| Metric | OK | Warning | Critical |
|--------|-----|---------|----------|
| Function length | < 30 lines | 30-50 lines | > 50 lines |
| Nesting depth | < 3 levels | 3-4 levels | > 4 levels |
| Branch count | < 4 | 4-7 | > 7 |
| Parameters | < 4 | 4-5 | > 5 |
| File length | < 300 lines | 300-500 lines | > 500 lines |
| Class methods | < 10 | 10-15 | > 15 |

These are guidelines, not laws — a 60-line function that reads linearly is fine; a 25-line function with 5 levels of nesting is not.

## Report Findings

For each hotspot:

| Field | Content |
|-------|---------|
| **Location** | file:line range |
| **Metric** | Which metric is violated and by how much |
| **Why it matters** | Specific risk — bugs, maintenance burden, onboarding cost |
| **Suggestion** | Concrete approach to reduce complexity (extract method, use early returns, replace conditional with lookup, split file) |

### Severity Guide

- **Critical**: God functions (100+ lines with deep nesting) in critical paths (auth, payments, data processing) — highest bug risk
- **High**: Functions 50+ lines with 4+ nesting levels — hard to review, hard to test, hard to modify safely
- **Medium**: Large files or classes with low cohesion — maintenance burden but individual functions may be OK
- **Low**: Mildly long functions or borderline nesting — note for awareness

## Output Format

After scanning, output a **Top 10 Hotspots** list (or fewer if the codebase is small):

```
## Complexity Hotspots

### #{rank}: `{function_name}` in `{file}`

**Lines**: {start}-{end} ({count} lines)
**Nesting depth**: {max_depth} levels
**Branches**: {count}
**Parameters**: {count}
**Why it matters**: {specific risk}
**Suggestion**: {concrete approach to simplify}
```

End with a Findings Summary table:

| # | Severity | File:Line | Function | Lines | Nesting | Branches | Suggestion |
|---|----------|-----------|----------|-------|---------|----------|-----------|
| 1 | Critical | path:line | func_name | 120 | 5 | 8 | Split into 3 functions |

## Rules

- **Rank by impact** — a 200-line function in a hot code path matters more than a 200-line function in a one-time migration script
- **Suggest specific decomposition** — don't just say "split this function"; identify the natural seams (each step in a sequence, each branch in a conditional, each responsibility in a god class)
- **Consider readability, not just metrics** — a 60-line function that reads top-to-bottom is often better than 6 tiny functions you have to jump between
- **Check test coverage** — complex code without tests is higher severity than complex code with thorough tests
