## Data Realism

Find tests using oversimplified data that doesn't represent production reality.

### What to Look For

1. **Single-item lists**: Tests always use `[item]` when production handles thousands (pagination, batching, performance)
2. **ASCII-only strings**: `"test"` or `"John Doe"` when real users have unicode, emoji, accented characters, CJK text
3. **Perfect data**: Complete, well-formed data when production has missing fields, nulls, legacy formats
4. **Tiny numbers**: `amount=10` when production handles `amount=99999999.99` (overflow, precision)
5. **No dates near boundaries**: `"2024-06-15"` when edge cases happen at midnight, DST, month/year boundaries, leap days
6. **Homogeneous test data**: All test records look identical when production is diverse (user types, tiers, locales)
7. **No concurrent data**: One record when production has millions (query performance, unique constraints)
8. **Clean relational data**: Simple 1:1 relationships when production has many-to-many, orphaned records, circular references
9. **Unrealistic file sizes**: 10-byte files when users upload 500MB
10. **English-only**: Assuming English locale, LTR text, US date format, dollar currency

### How to Evaluate

For each data realism gap:
- What production incident could this miss? (encoding bugs, overflow, performance degradation)
- What's the simplest representative test data that would catch this?
- Is this systemic (all test data is simplistic) or isolated?

### Severity Guide

- **Critical**: Financial or data integrity tests using unrealistic numeric ranges
- **High**: User-facing features tested only with ASCII/English data
- **Medium**: Tests using single items when batch behavior differs
- **Low**: Tests that work but could use more diverse scenarios

### Output Format

| # | Severity | File:Line | Issue | What to Test | Suggestion |
|---|----------|-----------|-------|-------------|------------|
| 1 | High | test_path:line | description | what realistic data to use | specific test data to add |
