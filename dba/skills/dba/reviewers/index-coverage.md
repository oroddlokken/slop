# Find Missing Index Coverage

Cross-reference query patterns against schema/migration-defined indexes to find columns that are filtered, sorted, or joined on but lack indexes.

## What to Look For

### WHERE clause columns without indexes
```sql
-- If users.email has no index, this is a full table scan
SELECT * FROM users WHERE email = 'foo@bar.com'
```

```python
# Django ORM
User.objects.filter(email='foo@bar.com')

# SQLAlchemy
User.query.filter_by(email='foo@bar.com')
```

### ORDER BY columns without indexes
```sql
-- Sorting without an index requires a filesort
SELECT * FROM orders ORDER BY created_at DESC LIMIT 20
```

### JOIN columns without indexes
```sql
-- If orders.user_id has no index, the join scans the full orders table
SELECT * FROM users JOIN orders ON users.id = orders.user_id
```

MySQL auto-creates indexes on FK columns. PostgreSQL does not — explicit indexes on FK columns are needed for efficient JOINs (PostgreSQL only creates internal indexes for constraint checking, not query optimization).

### Composite query patterns needing composite indexes
```sql
-- Needs a composite index on (status, created_at), not just individual indexes
SELECT * FROM orders WHERE status = 'pending' ORDER BY created_at
```

```python
Order.objects.filter(status='pending').order_by('created_at')
```

### COUNT/GROUP BY columns
```sql
-- Counting by unindexed column
SELECT status, COUNT(*) FROM orders GROUP BY status
```

### Partial/conditional index opportunities
```sql
-- If 95% of orders are status='completed', a partial index on non-completed is more efficient
SELECT * FROM orders WHERE status = 'pending'
```

### Redundant indexes
Multiple indexes that overlap:
- Index on `(user_id)` AND index on `(user_id, created_at)` — the first is redundant
- Multiple single-column indexes used together when a composite would be better

## How to Scan

1. **Collect all indexes**: Read migration files and schema definitions. Build a map of `table -> [indexed columns]`. Include:
   - Explicit `CREATE INDEX` statements
   - `db_index=True`, `index=True` in ORM models
   - Primary key indexes (implicit)
   - Unique constraint indexes (implicit)
   - Foreign key indexes (check if DB creates these automatically — PostgreSQL does NOT, MySQL does)
2. **Collect all query patterns**: Grep for SQL queries and ORM query chains. Extract:
   - WHERE clause columns
   - ORDER BY columns
   - JOIN ON columns
   - GROUP BY columns
   - Columns in subquery WHERE clauses
3. **Cross-reference**: For each queried column, check if an appropriate index exists. Consider:
   - Single-column indexes for simple filters
   - Composite indexes for multi-column WHERE + ORDER BY patterns
   - Covering indexes for frequently-accessed column sets
4. **Estimate table size**: Look for hints about data volume — pagination limits, batch sizes, comments mentioning scale, seed data size
5. **Check for redundant indexes**: Look for indexes that are prefixes of other indexes

## Severity Guide

- **High**: Missing index on a column in WHERE/JOIN of a frequently-hit endpoint (API routes, list views) — full table scans on every request
- **High**: Missing index on a foreign key column in PostgreSQL — joins become expensive as tables grow
- **Medium**: Missing index on ORDER BY columns used with LIMIT — filesort on large tables
- **Medium**: Missing composite index where query always filters + sorts on the same columns
- **Low**: Missing index on columns only used in admin/batch queries
- **Low**: Redundant indexes — waste write performance and storage but don't cause incorrect behavior

## Output Format

After scanning, output:

```
## Index Coverage

### {Severity}: {short description}

**Query location**: `{file}:{line}`
**Query pattern**: {the WHERE/ORDER BY/JOIN that needs an index}
**Table.column**: {table and column that's missing an index}
**Existing indexes**: {what indexes the table currently has}
**Impact**: {full table scan, filesort, slow join — with estimated severity based on likely table size}
**Fix**: {exact CREATE INDEX statement or ORM equivalent}
```

End with a Findings Summary table:

| # | Severity | File:Line | Table.Column | Query Pattern | Fix |
|---|----------|-----------|-------------|---------------|-----|
| 1 | High | routes/users.py:42 | users.email | WHERE email = ? | CREATE INDEX idx_users_email ON users(email) |

## Rules

- **Don't flag primary key lookups** — every table has a PK index
- **Check for unique constraints** — these create implicit indexes
- **Consider the database**: PostgreSQL doesn't auto-index FKs, MySQL does. Adjust findings accordingly.
- **Suggest composite indexes when the query pattern warrants it** — `WHERE status = ? ORDER BY created_at` needs `(status, created_at)`, not two separate indexes
- **Note that adding indexes has a write cost** — for write-heavy tables, explicitly mention the tradeoff
