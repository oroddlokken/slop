## Boundary Values

Find tests missing boundary and edge-value coverage — where off-by-one errors and overflow bugs hide.

### What to Look For

1. **Empty collections**: Functions accepting lists/arrays/sets never tested with `[]`
2. **Zero and negative**: Numeric parameters never tested with `0`, `-1`, or negative values
3. **Max/min values**: Integer parameters never tested near MAX_INT, MIN_INT, or very large numbers
4. **Empty strings**: String parameters never tested with `""`, whitespace-only `"   "`, or very long strings
5. **Off-by-one in pagination**: Page 0, page -1, page beyond last, exact boundary of page size
6. **Exact boundary of limits**: If max items is 100, is 99/100/101 tested?
7. **Single vs multiple**: Function works with N items but only tested with 1
8. **None/null/undefined**: Optional parameters never tested with their absence
9. **Date boundaries**: Midnight, end of month, end of year, leap day, epoch
10. **Float precision**: `0.1 + 0.2`, very small numbers, NaN, Infinity

### How to Evaluate

For each missing boundary test:
- What specific value would trigger a bug? (trace the code path, not theoretical)
- Is this boundary enforced by validation, or does the code assume valid ranges?
- Would a real user or system ever produce this boundary value?

### Severity Guide

- **Critical**: Numeric boundaries on financial calculations or data indexing
- **High**: Empty/null input on core functions that don't validate
- **Medium**: Pagination or limit boundaries that could produce wrong results
- **Low**: Boundary values that are validated before reaching the function

### Output Format

| # | Severity | File:Line | Issue | What to Test | Suggestion |
|---|----------|-----------|-------|-------------|------------|
| 1 | High | source_path:line | description | the boundary value to test | exact test input and expected behavior |
