# Find Query Scatter

Scan for raw SQL or ORM queries scattered outside a data access layer — queries in route handlers, CLI scripts, utilities, templates, or duplicated across multiple files.

## What to Look For

### Raw SQL in route handlers
```python
# BAD: SQL directly in the route handler
@app.route('/users')
def list_users():
    users = db.execute("SELECT id, name, email FROM users WHERE active = 1").fetchall()
    return jsonify(users)
```

Should be: a repository function, query module, or model method.

### Same query in multiple places
```python
# In routes/users.py
users = db.execute("SELECT * FROM users WHERE active = 1")

# In tasks/cleanup.py — same query, slightly different
active_users = db.execute("SELECT id, name FROM users WHERE active = true")

# In cli/export.py — same again
all_active = db.query("SELECT * FROM users WHERE active = 1 ORDER BY name")
```

Three places to update when the schema changes. Three chances to get it wrong.

### Queries in utility/helper functions
```python
# BAD: Database call in a "pure" utility module
# utils/formatting.py
def format_user_display(user_id):
    user = db.execute("SELECT name, title FROM users WHERE id = ?", (user_id,))
    return f"{user.title} {user.name}"
```

### Queries in templates
```python
# BAD: Jinja2 template making DB calls
{% for order in get_orders(user.id) %}  {# get_orders() runs a query #}
```

### Mixed query styles
Same table accessed via ORM in some places and raw SQL in others:

```python
# In views.py — uses ORM
users = User.objects.filter(active=True)

# In management/commands/export.py — uses raw SQL for the same thing
users = connection.cursor().execute("SELECT * FROM users WHERE active = 1")
```

### No repository/DAO pattern
All database access is inline — no dedicated module, class, or layer for data access. Every file that needs data writes its own queries.

## How to Scan

1. **Map query locations**: Grep for all SQL execution and ORM query calls. Group by file and directory.
2. **Identify the data access layer** (if one exists): Look for files/directories named `repository`, `dao`, `queries`, `db`, `data`, `store`, `services` that centralize database access
3. **Find queries outside the DAL**: Any SQL or ORM query in files that aren't part of the data access layer — route handlers, CLI commands, background tasks, utilities, templates
4. **Find duplicate queries**: Look for the same table being queried with similar WHERE clauses in multiple files
5. **Check for mixed styles**: Same table accessed via ORM in some places and raw SQL in others

## Severity Guide

- **High**: Same query logic duplicated in 3+ places — high maintenance burden, inconsistency risk
- **Medium**: Raw SQL in route handlers/controllers — mixing concerns, harder to test
- **Medium**: Queries in utility modules that should be "pure" — hidden side effects
- **Medium**: Mixed ORM + raw SQL for the same table — inconsistent abstractions
- **Low**: Queries in one-off scripts or management commands — lower maintenance burden
- **Low**: No DAL pattern but codebase is small (<10 files with queries) — pattern not yet needed

## Output Format

After scanning, output:

```
## Query Scatter

### {Severity}: {short description}

**Locations**: `{file1}:{line}`, `{file2}:{line}`, ...
**Pattern**: {duplication / wrong layer / mixed style}
**Table(s)**: {which tables are affected}
**Impact**: {maintenance burden, inconsistency risk, testability}
**Fix**: {extract to repository/service, consolidate queries, standardize on ORM or raw}
```

End with a Findings Summary table:

| # | Severity | Files | Pattern | Table | Fix |
|---|----------|-------|---------|-------|-----|
| 1 | High | routes/users.py:12, tasks/cleanup.py:34, cli/export.py:8 | Duplicate query | users | Extract to UserRepository |

## Rules

- **Don't flag one-off admin scripts** for lacking a DAL — focus on production code paths
- **Defer security findings to injection reviewer** — this lens focuses on DRY and maintainability only
- **A single file with all queries is a valid DAL** — don't insist on a specific pattern (repository, DAO, service). Any centralization counts.
- **Consider the project size** — a 5-file project doesn't need a formal repository pattern. Scale the recommendation to the codebase.
