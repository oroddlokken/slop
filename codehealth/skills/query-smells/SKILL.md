---
name: query-smells
description: "Find database query issues: N+1 queries, raw SQL in loops, missing parameterization, scattered queries outside the data access layer, and missing transaction management."
args:
  - name: path
    description: The directory to scan (optional, defaults to cwd)
    required: false
user-invokable: true
---

# Find Query Smells
This skill scans code and reports findings — it does not modify code. It can run standalone or as part of `/codehealth`. Examples are Python; apply equivalent patterns for your target language.

Scan the codebase for database query patterns that cause performance problems, security vulnerabilities, or maintenance headaches.

## What to Look For

### N+1 queries
The #1 database performance killer. Loading a list, then querying for each item in a loop:

```python
# BAD: N+1 — one query for users, then one query PER user for their orders
users = db.query("SELECT * FROM users")
for user in users:
    orders = db.query(f"SELECT * FROM orders WHERE user_id = {user.id}")
```

Should be: a single JOIN, a subquery, or eager loading via ORM (`select_related`, `joinedload`, `include`)

### Raw SQL with string interpolation (SQL injection risk)
```python
# BAD: SQL injection vulnerability
db.execute(f"SELECT * FROM users WHERE name = '{name}'")
db.execute("SELECT * FROM users WHERE name = '" + name + "'")
db.execute("SELECT * FROM users WHERE name = '%s'" % name)
```

Should use: parameterized queries (`?`, `%s`, `:name` placeholders)

### Queries in loops (beyond N+1)
```python
# BAD: Individual inserts in a loop instead of bulk
for item in items:
    db.execute("INSERT INTO orders (item_id, qty) VALUES (?, ?)", item.id, item.qty)
```

Should be: bulk insert, batch operation, or `executemany`

### Missing transaction management
- Multiple related writes without a transaction — partial failures leave inconsistent state
- Long-running transactions holding locks unnecessarily
- No rollback handling on error

### Queries scattered outside data access layer
- Raw SQL in route handlers, CLI scripts, templates, or utility functions
- Same query written differently in multiple places
- No repository/DAO/query module pattern — queries are everywhere

### ORM anti-patterns
- Lazy loading in loops (ORM version of N+1 — accessing relationships in a for loop)
- Loading entire objects when only one field is needed (`SELECT *` via ORM)
- Using ORM for bulk operations that should be raw SQL
- Chaining excessive ORM filters that produce suboptimal SQL

### Missing indexes (inferred)
- Queries filtering on columns that are likely unindexed (non-PK, non-FK columns in WHERE clauses)
- Queries sorting on columns without indexes (`ORDER BY created_at` on large tables)
- Pattern: slow query likelihood based on query structure

### Connection management
- Creating new connections per request instead of using a pool
- Not closing connections/cursors after use
- Missing connection pool configuration

## How to Scan

1. **Search for SQL keywords**: `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `cursor.execute`, `db.query`, `db.execute`, raw SQL strings
2. **Search for ORM query patterns**: `.filter(`, `.where(`, `.find(`, `.query(`, `.objects.`, `.select(`, `.join(`
3. **Look for queries inside loops**: `for`/`while` blocks containing database calls
4. **Search for string interpolation near SQL**: f-strings, `%s`, `.format(`, `+` concatenation near SQL keywords
5. **Check for transaction usage**: `BEGIN`, `COMMIT`, `ROLLBACK`, `atomic`, `transaction`, `session.commit`
6. **Check migration files** for index creation — compare against query patterns
7. **Look for connection creation**: `connect(`, `create_engine(`, pool configuration

## Report Findings

For each query smell:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Type** | N+1 / SQL injection / Query in loop / Missing transaction / Scattered query / ORM anti-pattern / Missing index / Connection issue |
| **Query** | The problematic query or pattern (sanitized) |
| **Impact** | Performance (how bad — O(n) queries?), security (injection?), correctness (partial writes?) |
| **Fix** | Concrete solution — show what the fixed version looks like |

### Severity Guide

- **Critical**: SQL injection vulnerabilities — immediate security risk
- **Critical**: Missing transactions on multi-step writes — data corruption risk
- **High**: N+1 queries on frequently-hit endpoints — performance degradation at scale
- **Medium**: Queries in loops for batch operations — works at small scale but won't scale
- **Medium**: Scattered queries outside data access layer — maintenance burden
- **Low**: Minor ORM inefficiencies, possible missing indexes

## Output Format

After scanning, output:

```
## Query Smells

### {Severity}: {short description}

**Location**: `{file}:{line}`
**Type**: {N+1 | SQL injection | Query in loop | ...}
**Current**: {what the code does now}
**Impact**: {performance/security/correctness impact}
**Fix**: {concrete solution with code example}
```

End with a Findings Summary table:

| # | Severity | File:Line | Type | Impact | Fix |
|---|----------|-----------|------|--------|-----|
| 1 | Critical | path:line | SQL injection | RCE risk | Use parameterized query |

## Rules

- **SQL injection is always Critical** — no exceptions, even if the input "looks safe"
- **Distinguish N+1 from acceptable loops** — a loop that makes 3 API calls is different from a loop that makes 10,000 DB queries
- **Suggest the right fix for the ORM** — Django uses `select_related`/`prefetch_related`, SQLAlchemy uses `joinedload`/`selectinload`, ActiveRecord uses `includes`
- **Consider scale** — a query-in-loop that processes 10 items is different from one that processes 10,000
