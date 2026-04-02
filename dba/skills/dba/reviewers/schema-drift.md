# Find Schema Drift

Compare ORM models/schema definitions against migration files to find divergences — places where the code's view of the schema doesn't match what the migrations actually create.

## What to Look For

### Model fields without migrations
A field exists in the ORM model but no migration creates or alters that column:

```python
# In models.py
class User(Model):
    name = CharField(max_length=100)
    phone = CharField(max_length=20)  # Added but no migration for this

# Migration only has: name VARCHAR(100) — phone is missing
```

### Migrations without model fields (orphaned columns)
A migration adds a column, but the model doesn't define it. The column exists in the DB but the code never uses it:

```python
# Migration: ALTER TABLE users ADD COLUMN legacy_flag BOOLEAN DEFAULT false
# But User model has no legacy_flag field — dead column
```

### Type mismatches
The model declares one type, but the migration creates a different one:

```python
# Model says: price = DecimalField(max_digits=10, decimal_places=2)
# Migration says: price INTEGER  — lost the decimal
```

### Constraint mismatches
- Model says `nullable=False` but migration doesn't add `NOT NULL`
- Model says `unique=True` but migration has no unique constraint
- Model defines a foreign key but migration doesn't create the FK constraint
- Model has `max_length=100` but migration creates `VARCHAR(255)`

### Missing migrations for model changes
```python
# models.py has been edited (git log shows changes)
# But no new migration file exists — someone changed the model without running makemigrations/alembic revision
```

### Index mismatches
- Model declares `db_index=True` or `index=True` but no migration creates the index
- Migration creates an index but it references a column that no longer exists in the model

### Default value mismatches
- Model defines `default=0` but migration has no DEFAULT clause (or vice versa)
- Defaults differ between model and migration

### Migration ordering issues
- Migrations reference columns/tables that don't exist yet at that point in the migration sequence
- Circular dependencies between migrations

## How to Scan

1. **Map model fields to migrations**: For each ORM model, list all fields with their types, constraints, and options. For each migration, list all column additions, alterations, and drops. Cross-reference.
2. **Detect the ORM**: Django (models.py + migrations/), SQLAlchemy + Alembic (models.py + alembic/versions/), Prisma (schema.prisma + prisma/migrations/), ActiveRecord (app/models/ + db/migrate/), TypeORM (entities/ + migrations/), Sequelize (models/ + migrations/)
3. **For Django**: Compare `models.py` fields against the latest state implied by applying all migrations in order
4. **For Alembic**: Compare SQLAlchemy model definitions against `upgrade()` functions in version files
5. **For Prisma**: Compare `schema.prisma` against generated migration SQL files
6. **Check git log**: `git log --oneline -10 -- '**/models*'` vs `git log --oneline -10 -- '**/migrations/**'` — if models changed recently without a corresponding migration, flag it
7. **Look for manual SQL**: `.sql` files that ALTER tables outside the migration framework

## Severity Guide

- **Critical**: Model field exists but no migration creates the column — the app will crash with a "column does not exist" error on any query touching that field
- **Critical**: Migration drops a column that the model still references — same crash risk
- **High**: Type mismatch between model and migration — silent data truncation or conversion errors
- **High**: Missing NOT NULL constraint — model assumes non-null but DB allows null, causing NoneType errors
- **Medium**: Orphaned columns (migration creates, model doesn't reference) — dead data, maintenance burden
- **Medium**: Missing foreign key constraints — orphaned rows possible
- **Low**: Minor default value differences, index mismatches

## Output Format

After scanning, output:

```
## Schema Drift

### {Severity}: {short description}

**Model**: `{file}:{line}` — {field definition}
**Migration**: `{file}:{line}` — {column definition, or "missing"}
**Drift**: {what doesn't match — type, constraint, existence, default}
**Impact**: {crash, data loss, silent corruption, dead data}
**Fix**: {generate migration, update model, add constraint, etc.}
```

End with a Findings Summary table:

| # | Severity | Model File:Line | Migration File:Line | Drift | Fix |
|---|----------|----------------|--------------------|----|-----|
| 1 | Critical | models.py:42 | (missing) | No migration for phone field | Run makemigrations |

## Rules

- **Only compare within the same migration framework** — don't compare Django models against raw SQL files unless the project uses both
- **Account for migration squashing** — some projects squash migrations; check for squash files before flagging "missing migration"
- **Check abstract models and mixins** — fields defined in base classes still need migrations in the concrete model's table
- **Note the migration tool's auto-detection** — Django's `makemigrations` and Prisma's `prisma migrate` can detect drift automatically; note if the project could just run these tools to fix the issue
