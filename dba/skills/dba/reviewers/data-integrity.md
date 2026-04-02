# Find Data Integrity Gaps

Scan for missing database constraints, unsafe delete patterns, and schema design gaps that allow data corruption or orphaned records.

## What to Look For

### Missing foreign key constraints
```sql
-- BAD: Column references another table but no FK constraint
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER  -- No FOREIGN KEY — orphaned orders possible when user is deleted
);
```

```python
# BAD: ORM relationship without DB-level FK
class Order(Model):
    user_id = IntegerField()  # Just an integer, no ForeignKey() — DB won't enforce referential integrity
```

### Missing ON DELETE policy
```sql
-- BAD: FK exists but no ON DELETE — what happens when the parent is deleted?
CREATE TABLE orders (
    user_id INTEGER REFERENCES users(id)
    -- Default is ON DELETE NO ACTION / RESTRICT — blocks parent deletion
    -- But application code may not handle this, leading to errors
);
```

Needs explicit policy: `CASCADE`, `SET NULL`, `SET DEFAULT`, or `RESTRICT` with application-level handling.

### Nullable columns that shouldn't be
```python
# BAD: Email should never be null for active users
class User(Model):
    email = CharField(null=True)  # Why is this nullable?
    status = CharField(null=True, default='active')  # Status should always have a value
```

### Missing unique constraints
```python
# BAD: Email should be unique but no constraint — duplicates possible
class User(Model):
    email = CharField(max_length=255)  # No unique=True — race conditions can create duplicates
```

### Missing CHECK constraints
```sql
-- BAD: No constraint on valid values
CREATE TABLE orders (
    status VARCHAR(20),  -- No CHECK — code could insert 'asdfjkl' as a status
    quantity INTEGER      -- No CHECK — negative quantities possible
);
```

### Orphan-producing deletes
```python
# BAD: Deleting parent without considering children
def delete_user(user_id):
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    # What about their orders, profiles, sessions, comments?
```

```python
# BAD: Django delete without considering related objects
user.delete()  # Django cascades by default — but is that always desired?
```

### Soft delete inconsistencies
```python
# BAD: Some code checks is_deleted, some doesn't
# In one place:
users = User.objects.filter(is_deleted=False)
# In another place:
users = User.objects.all()  # Includes soft-deleted users
```

### Missing NOT NULL with application assumptions
```python
# Code assumes user.name is always present:
greeting = f"Hello, {user.name.upper()}"
# But in the schema: name VARCHAR(100) — nullable by default
# NoneType.upper() will crash
```

### Enum-like columns without constraints
```python
# BAD: Status field with no constraint on valid values
class Order(Model):
    status = CharField(max_length=20)  # Any string goes
    # Code assumes: 'pending', 'processing', 'completed', 'cancelled'
    # But nothing prevents: 'Pending', 'PENDING', 'penidng', ''
```

### Missing default values
```sql
-- BAD: New column added without DEFAULT — existing rows get NULL
ALTER TABLE orders ADD COLUMN priority INTEGER;
-- Application code may assume priority is always set
```

### Timestamp columns without defaults
```python
# BAD: created_at without auto_now_add — application must always set it
class Order(Model):
    created_at = DateTimeField()  # No default — forgotten in some code paths
```

## How to Scan

1. **Read schema/model definitions**: Extract all tables, columns, types, constraints (FK, UNIQUE, NOT NULL, CHECK, DEFAULT)
2. **Check FK coverage**: For every `*_id` column, verify a FK constraint exists at the database level (not just ORM level)
3. **Check ON DELETE policies**: For every FK, what happens when the parent is deleted?
4. **Find nullable columns**: List all nullable columns. Cross-reference with application code — does the code ever assume non-null?
5. **Find missing unique constraints**: Look for columns that should be unique (email, username, slug, external_id) without UNIQUE constraints
6. **Check delete patterns**: Grep for DELETE statements and `.delete()` calls. Check if related data is handled.
7. **Check soft delete consistency**: If soft deletes are used, verify all queries filter on the soft-delete flag
8. **Check enum-like columns**: Columns with a small set of valid values — do they have CHECK constraints or DB-level enums?

## Severity Guide

- **Critical**: Missing FK on a column that references another table with cascade-dependent logic — orphaned records on any delete
- **Critical**: Nullable column that application code dereferences without null check — crashes in production
- **High**: Missing unique constraint on logically-unique columns (email, username) — duplicate data, authentication bugs
- **High**: Missing ON DELETE policy on FKs in tables with parent-delete workflows — undefined behavior
- **Medium**: Missing CHECK constraints on enum-like columns — garbage data over time
- **Medium**: Soft delete inconsistency — some queries include deleted records
- **Low**: Missing NOT NULL on columns that probably should be required but code handles null
- **Low**: Missing default values — works if application always provides a value

## Output Format

After scanning, output:

```
## Data Integrity

### {Severity}: {short description}

**Location**: `{file}:{line}` (schema definition or code that exposes the gap)
**Table.column**: {table and column with the gap}
**Missing constraint**: {FK, UNIQUE, NOT NULL, CHECK, ON DELETE, DEFAULT}
**Risk**: {orphaned records, duplicates, null crashes, garbage data, undefined cascade}
**Fix**: {exact ALTER TABLE or model change}
```

End with a Findings Summary table:

| # | Severity | File:Line | Table.Column | Missing Constraint | Fix |
|---|----------|-----------|-------------|-------------------|-----|
| 1 | Critical | models.py:42 | orders.user_id | FK | Add ForeignKey with ON DELETE CASCADE |

## Rules

- **Defer transaction-related integrity issues to transaction-gaps** — this reviewer owns schema-level constraints only
- **Check both ORM and SQL level**: Django's `ForeignKey` creates a DB constraint. SQLAlchemy's `ForeignKey` does too. But some ORMs allow `db_constraint=False` — verify the constraint actually exists.
- **Consider the database's defaults**: PostgreSQL allows NULL by default. MySQL allows NULL by default. Django's CharField is NOT NULL by default (blank vs null). Know the framework.
- **Missing constraints on test/staging tables are lower severity** — focus on production schema
