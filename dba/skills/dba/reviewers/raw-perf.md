# Find Raw Query Performance Issues

Scan for SQL query patterns that cause poor performance regardless of indexing — query shapes that prevent the database optimizer from working efficiently.

## What to Look For

### Leading wildcard LIKE
```sql
-- BAD: Leading wildcard can't use a B-tree index — full table scan
SELECT * FROM users WHERE name LIKE '%smith'
SELECT * FROM products WHERE description LIKE '%keyword%'
```

Should use: full-text search (GIN index + `tsvector`), trigram index (`pg_trgm`), or application-level filtering.

### Functions on indexed columns
```sql
-- BAD: Function on the column prevents index usage
SELECT * FROM orders WHERE YEAR(created_at) = 2024
SELECT * FROM users WHERE LOWER(email) = 'foo@bar.com'
SELECT * FROM events WHERE DATE(timestamp) = '2024-01-01'
```

Should use: range conditions (`created_at >= '2024-01-01' AND created_at < '2025-01-01'`), functional indexes, or computed columns.

### Implicit type casts
```sql
-- BAD: Comparing string column to integer — implicit cast prevents index usage
SELECT * FROM users WHERE phone = 5551234
-- phone is VARCHAR, 5551234 is INT — DB casts every row's phone to INT for comparison
```

### SELECT * when few columns needed
```sql
-- BAD: Loading all 30 columns when you need 2
SELECT * FROM users WHERE id = 1
-- Especially bad with: large TEXT/BLOB columns, wide tables, queries that return many rows
```

### Unbounded queries
```sql
-- BAD: No LIMIT on a query that could return millions of rows
SELECT * FROM events WHERE type = 'page_view'
-- Should have LIMIT, pagination, or WHERE on a bounded range
```

### Subquery instead of JOIN
```sql
-- BAD: Correlated subquery — executes once per outer row
SELECT *, (SELECT COUNT(*) FROM orders WHERE orders.user_id = users.id) as order_count
FROM users
```

Should use: LEFT JOIN with GROUP BY, or a window function.

### DISTINCT as a band-aid
```sql
-- BAD: Using DISTINCT to hide a bad JOIN that produces duplicates
SELECT DISTINCT users.* FROM users
JOIN orders ON users.id = orders.user_id
JOIN order_items ON orders.id = order_items.order_id
WHERE order_items.product_id = 42
```

The DISTINCT is hiding the fact that the JOIN produces multiple rows per user. Should use EXISTS or a subquery.

### OR conditions that prevent index usage
```sql
-- BAD: OR on different columns — can't use a single index efficiently
SELECT * FROM users WHERE email = 'foo@bar.com' OR phone = '555-1234'
```

Should use: UNION of two indexed queries, or a composite approach.

### Large IN lists
```sql
-- BAD: Huge IN list — plan instability, parameter limit risk
SELECT * FROM products WHERE id IN (1, 2, 3, ... 10000)
```

Should use: temporary table, VALUES list with JOIN, or ANY(ARRAY[...]).

### ORDER BY without index support
```sql
-- BAD: Sorting a large result set without an index on the sort column
SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at
-- If no index on (status, created_at), this is a filesort
```

### Offset pagination on large tables
```sql
-- BAD: OFFSET scans and discards rows — O(offset) cost
SELECT * FROM events ORDER BY id LIMIT 20 OFFSET 100000
```

Should use: cursor-based pagination (`WHERE id > ? ORDER BY id LIMIT 20`). Offset pagination degrades linearly with page depth — at offset 100K it scans 100K+ rows to return 20.

### COUNT(*) on large tables without WHERE
```sql
-- BAD: Full table count in PostgreSQL is always a full scan
SELECT COUNT(*) FROM events
-- PostgreSQL doesn't maintain a row count — this scans the entire table
```

Alternatives: approximate count via `pg_stat_live_tuples` (within ~10%), materialized view for frequently-counted results, or trigger-maintained counter table.

## How to Scan

1. **Extract all SQL queries**: Raw SQL strings, ORM-generated SQL (if debug/logging shows it), and query builder patterns
2. **Check LIKE patterns**: Grep for `LIKE '%` — leading wildcard
3. **Check functions on columns**: Grep for `WHERE LOWER(`, `WHERE UPPER(`, `WHERE DATE(`, `WHERE YEAR(`, `WHERE CAST(`, `WHERE EXTRACT(` — functions wrapping column names in WHERE clauses
4. **Check for SELECT ***: Count columns in the table vs columns actually used in the code
5. **Find unbounded queries**: SELECT without LIMIT on tables that could be large
6. **Find correlated subqueries**: Subqueries in SELECT or WHERE that reference the outer query
7. **Check for DISTINCT + JOIN combinations**: DISTINCT used to deduplicate JOIN results
8. **Find OR patterns on different columns**: OR in WHERE clauses with different columns

## Severity Guide

- **High**: Leading wildcard LIKE on user-facing search — full table scan on every search request
- **High**: Unbounded SELECT on a large table — can OOM the application or timeout
- **High**: Correlated subquery on a list endpoint — O(N*M) performance
- **Medium**: Functions on indexed columns — index bypassed, slow on large tables
- **Medium**: SELECT * on wide tables with large columns — unnecessary network/memory
- **Medium**: Large IN lists — plan instability, potential parameter limits
- **Low**: DISTINCT used to mask duplicate JOINs — correctness is fine, just wasteful
- **Low**: OR on different columns — often acceptable, depends on table size

## Output Format

After scanning, output:

```
## Query Performance

### {Severity}: {short description}

**Location**: `{file}:{line}`
**Query pattern**: {the problematic SQL pattern}
**Why it's slow**: {what the DB optimizer can't do}
**Impact**: {full table scan, filesort, OOM, timeout, O(N*M)}
**Fix**: {rewritten query, index suggestion, alternative approach}
```

End with a Findings Summary table:

| # | Severity | File:Line | Pattern | Why Slow | Fix |
|---|----------|-----------|---------|----------|-----|
| 1 | High | search.py:42 | LIKE '%term%' | Full scan | Use full-text search with GIN index |

## Rules

- **Defer missing index issues to index-coverage** — this reviewer owns query shape problems, not missing indexes
- **Consider the database**: PostgreSQL supports functional indexes (fixes function-on-column). MySQL has limited support. Note what's available.
- **Consider table size**: SELECT * on a 100-row config table is fine. SELECT * on a million-row events table is not. Scale matters.
- **Show the rewritten query** — don't just say "rewrite this." Show what the better version looks like.
