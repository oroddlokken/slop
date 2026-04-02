# Find Migration Safety Issues

Scan migration files for destructive operations, missing rollback logic, ordering issues, and operations that can cause downtime on large tables.

## What to Look For

### Destructive migrations without safeguards
```sql
-- BAD: Dropping a column with no feature flag or deprecation period
ALTER TABLE users DROP COLUMN legacy_status;
```

```python
# BAD: Django migration that drops a column
migrations.RemoveField(model_name='user', name='legacy_status')
```

### Large-table operations without batching
```sql
-- BAD: Adding a NOT NULL column with default to a million-row table locks it
ALTER TABLE orders ADD COLUMN priority INTEGER NOT NULL DEFAULT 0;
-- PostgreSQL: this is fast (since 11), MySQL: this locks the table
```

```sql
-- BAD: Backfilling data in a single UPDATE — locks the entire table
UPDATE orders SET priority = 0 WHERE priority IS NULL;
-- Should be: batched in chunks of 1000-10000
```

### Missing rollback/down migration
```python
# BAD: Alembic upgrade without downgrade
def upgrade():
    op.add_column('users', sa.Column('phone', sa.String(20)))

def downgrade():
    pass  # Empty — can't roll back
```

```ruby
# BAD: ActiveRecord migration without reversible
class AddPhoneToUsers < ActiveRecord::Migration
  def up
    add_column :users, :phone, :string
  end
  # No down method
end
```

### Irreversible operations
Some operations can't be reversed cleanly:
- Dropping a column (data is gone)
- Changing column type with data loss (VARCHAR -> INT)
- Dropping a table
- Removing an enum value

These should be explicitly marked as irreversible with a comment explaining why.

### Data migrations mixed with schema migrations
```python
# BAD: Schema change AND data backfill in the same migration
def upgrade():
    op.add_column('users', sa.Column('full_name', sa.String(200)))
    # Data migration in the same file — can't roll back schema without rolling back data
    op.execute("UPDATE users SET full_name = first_name || ' ' || last_name")
    op.drop_column('users', 'first_name')
    op.drop_column('users', 'last_name')
```

Should be: three separate migrations (add column, backfill data, drop old columns).

### Missing index creation for new foreign keys
```python
# BAD: Adding a FK column without an index (PostgreSQL doesn't auto-index FKs)
op.add_column('orders', sa.Column('warehouse_id', sa.Integer, sa.ForeignKey('warehouses.id')))
# No index on warehouse_id — JOINs will full-scan
```

### Concurrent index creation not used
```sql
-- BAD: CREATE INDEX on a large table locks writes
CREATE INDEX idx_orders_status ON orders(status);
-- Should be: CREATE INDEX CONCURRENTLY (PostgreSQL)
```

### Migration ordering dependencies
- Migration A adds a column, Migration B references it, but B runs before A in some environments
- Circular migration dependencies

### Renaming without aliases
```sql
-- BAD: Renaming a column while app code still references the old name
ALTER TABLE users RENAME COLUMN name TO full_name;
-- Deploy sequence: migration runs, then code deploys — window where app crashes
```

Should be: add new column, backfill, deploy code using new column, drop old column.

## How to Scan

1. **Read ALL migration files** — every file in migration directories
2. **Flag destructive operations**: `DROP TABLE`, `DROP COLUMN`, `RENAME COLUMN`, `RENAME TABLE`, removing enum values, changing column types to smaller types
3. **Check for rollback/down**: Every migration should have a reverse operation or be explicitly marked irreversible
4. **Identify large-table operations**: ALTER TABLE with NOT NULL + DEFAULT, UPDATE without WHERE or with broad WHERE, CREATE INDEX (non-concurrent)
5. **Check for data + schema mixing**: Migrations that both ALTER TABLE and UPDATE/INSERT data
6. **Check FK index creation**: New ForeignKey columns in PostgreSQL projects without corresponding CREATE INDEX
7. **Check migration order**: Dependencies between migrations, timestamps/ordering

## Severity Guide

- **Critical**: DROP TABLE or DROP COLUMN without a backup/deprecation strategy — permanent data loss
- **Critical**: Data migration mixed with irreversible schema change in one migration — can't partially roll back
- **High**: Large-table ALTER without batching strategy — downtime risk in production
- **High**: Missing rollback on a migration that changes column types — can't recover from bad deploy
- **Medium**: CREATE INDEX without CONCURRENTLY on large PostgreSQL tables — write locks during index build
- **Medium**: Missing FK indexes in PostgreSQL — performance degradation at scale
- **Low**: Missing rollback on additive-only migrations (ADD COLUMN) — low risk, but good practice
- **Low**: Rename without zero-downtime strategy — only matters for zero-downtime deploys

## Output Format

After scanning, output:

```
## Migration Safety

### {Severity}: {short description}

**Migration**: `{file}:{line}`
**Operation**: {what the migration does}
**Risk**: {data loss, downtime, lock contention, no rollback}
**Deploy impact**: {will this cause downtime? how long? for what table size?}
**Fix**: {add rollback, split into steps, use CONCURRENTLY, batch the backfill, etc.}
```

End with a Findings Summary table:

| # | Severity | File:Line | Operation | Risk | Fix |
|---|----------|-----------|-----------|------|-----|
| 1 | Critical | 0003_drop_legacy.py:8 | DROP COLUMN | Data loss | Add deprecation period, backup first |

## Rules

- **Know the database**: PostgreSQL 11+: `ADD COLUMN ... DEFAULT` is instant (no lock). MySQL 8.0.29+: instant `ADD COLUMN` for NULL defaults. Older MySQL/MariaDB: table lock required. Adjust severity by database version.
- **Don't flag old migrations** — focus on recent migrations (last 10-20) or unmigrated changes. Old migrations are already applied.
- **Data migrations are fine — just not mixed with schema changes**. A migration that ONLY backfills data is perfectly fine.
- **Irreversible is okay if documented** — dropping a column is sometimes the right call. The issue is doing it without acknowledging it's irreversible.
