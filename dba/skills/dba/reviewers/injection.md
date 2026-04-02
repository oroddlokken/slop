# Find SQL Injection Vectors

Scan the codebase for SQL injection vulnerabilities: anywhere user-controlled input can reach a SQL query without parameterization.

## What to Look For

### String interpolation in SQL
The most common vector. Any SQL query built with string concatenation, f-strings, format(), or % formatting:

```python
# BAD: Direct interpolation
db.execute(f"SELECT * FROM users WHERE name = '{name}'")
db.execute("SELECT * FROM users WHERE id = " + str(user_id))
db.execute("SELECT * FROM users WHERE email = '%s'" % email)
db.execute("SELECT * FROM users WHERE name = '{}'".format(name))
```

```javascript
// BAD: Template literals or concatenation
db.query(`SELECT * FROM users WHERE name = '${name}'`)
db.query("SELECT * FROM users WHERE id = " + userId)
```

```ruby
# BAD: String interpolation
User.where("name = '#{params[:name]}'")
```

### ORM raw queries with interpolation
ORMs that allow raw SQL escape hatches:

```python
# BAD: Django raw() with interpolation
User.objects.raw(f"SELECT * FROM users WHERE name = '{name}'")
# BAD: SQLAlchemy text() with interpolation
db.execute(text(f"SELECT * FROM users WHERE id = {user_id}"))
```

### Dynamic table/column names
Even parameterized queries can't protect table or column names:

```python
# BAD: Dynamic table name from user input
db.execute(f"SELECT * FROM {table_name} WHERE id = ?", (id,))
# BAD: Dynamic column in ORDER BY
db.execute(f"SELECT * FROM users ORDER BY {sort_column}")
```

Should use: allowlists for table/column names

### LIKE pattern injection
```python
# BAD: User input in LIKE without escaping wildcards
db.execute("SELECT * FROM users WHERE name LIKE ?", (f"%{search}%",))
# The user can pass "%" or "_" to match everything
```

### Second-order injection
Data stored from one input and used unsafely in a later query:

```python
# Step 1: Safe insert
db.execute("INSERT INTO users (name) VALUES (?)", (user_input,))
# Step 2: UNSAFE — name retrieved from DB, used in new query without parameterization
user = db.execute("SELECT name FROM users WHERE id = ?", (id,)).fetchone()
db.execute(f"SELECT * FROM audit_log WHERE username = '{user.name}'")
```

### Stored procedures called with interpolation
```python
# BAD: Interpolation in stored procedure call
db.execute(f"CALL process_order('{order_id}', '{amount}')")
```

### IN clause construction
```python
# BAD: Building IN clause with string joining
ids = ",".join(user_ids)
db.execute(f"SELECT * FROM users WHERE id IN ({ids})")
```

Should use: parameterized IN with the correct number of placeholders

## How to Scan

1. **Grep for SQL keywords near interpolation**: `f"SELECT`, `f"INSERT`, `f"UPDATE`, `f"DELETE`, `f"CALL`, string concatenation (`+`) near SQL keywords, `.format(` near SQL, `%` formatting near SQL
2. **Grep for raw SQL execution methods**: `execute(`, `.raw(`, `text(`, `.rawQuery(`, `Repo.query(`, `cursor.execute(`, `db.query(`
3. **Check each SQL execution**: Is the query string built dynamically? Are all dynamic parts parameterized?
4. **Check ORM raw escape hatches**: `.raw()`, `.extra()`, `RawSQL()`, `text()`, `Arel.sql()`, `$queryRaw`
5. **Check for dynamic identifiers**: table names, column names, ORDER BY columns derived from input
6. **Trace input sources**: For each dynamic SQL, trace backwards — does the value come from user input (request params, form data, URL params, headers, file uploads)?

## Severity Guide

- **Critical**: User-controlled input reaches SQL without parameterization, regardless of current context. Injection is injection — even if "only admins use this endpoint," assume escalation.
- **Critical**: Dynamic table/column names from user input without allowlist validation
- **High**: Second-order injection — stored data used unsafely in later queries
- **High**: LIKE pattern injection on endpoints that return sensitive data
- **Medium**: Dynamic identifiers from internal (non-user) sources without validation
- **Low**: Theoretical injection in code that is clearly unreachable from user input (but still worth noting for defense in depth)

## Output Format

After scanning, output:

```
## SQL Injection Audit

### {Severity}: {short description}

**Location**: `{file}:{line}`
**Vector**: {interpolation type — f-string, concatenation, format, etc.}
**Input source**: {where the dynamic value comes from — request param, DB field, config, etc.}
**Current**: {the vulnerable code}
**Impact**: {what an attacker could do}
**Fix**: {parameterized version of the query}
```

End with a Findings Summary table:

| # | Severity | File:Line | Vector | Input Source | Fix |
|---|----------|-----------|--------|-------------|-----|
| 1 | Critical | path:line | f-string | request.args['name'] | Use parameterized query |

## Rules

- **SQL injection is always Critical when user input is involved** — no exceptions, even if validation exists elsewhere. Validation can be bypassed; parameterization cannot.
- **Show the fix**: For every finding, show what the parameterized version looks like for the specific ORM/driver in use.
- **Trace the input**: Don't just flag the query — show where the unsafe value enters the system.
- **Check the framework**: Django's ORM is safe by default, but `.raw()`, `.extra()`, and `RawSQL()` bypass protection. SQLAlchemy's `text()` is safe with `:param` syntax but not with f-strings. Note which framework protections exist and where they're bypassed.
