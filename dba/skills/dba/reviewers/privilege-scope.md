# Find Privilege Scope Issues

Scan for overly broad database privileges, missing access controls, and patterns where the application connects with more permissions than it needs.

## What to Look For

### Application connecting as superuser/root
```python
# BAD: Application using the postgres/root superuser
DATABASE_URL = "postgresql://postgres:password@localhost/mydb"
# The postgres user can: drop any database, create roles, read pg_authid, access all schemas
```

```yaml
# BAD: Docker compose with root DB user for the app
services:
  app:
    environment:
      DB_USER: root
      DB_PASSWORD: rootpassword
```

### Overly broad GRANT statements
```sql
-- BAD: GRANT ALL on everything
GRANT ALL PRIVILEGES ON DATABASE mydb TO app_user;
GRANT ALL ON ALL TABLES IN SCHEMA public TO app_user;

-- Better: Grant only what's needed
GRANT SELECT, INSERT, UPDATE ON users, orders, products TO app_user;
GRANT SELECT ON audit_log TO app_user;  -- Read-only for audit
```

### No read-only user for reporting/analytics
```python
# BAD: Reporting queries run with the same user that has write access
# A bug in reporting code could accidentally UPDATE or DELETE
def generate_monthly_report():
    conn = get_db_connection()  # Same write-capable connection
    results = conn.execute("SELECT ...")
```

### Missing row-level security
```python
# BAD: Multi-tenant app filtering by tenant_id in application code only
def get_orders(tenant_id):
    return db.execute("SELECT * FROM orders WHERE tenant_id = ?", (tenant_id,))
    # If ANY query forgets the WHERE clause, it leaks other tenants' data
```

Should consider: PostgreSQL Row Level Security (RLS) policies, or at minimum, a mandatory base query/scope.

### Schema-level access not restricted
```sql
-- BAD: App user can access system schemas
-- No search_path restriction — app can query pg_catalog, information_schema
-- This exposes: table structure, user roles, connection info
```

### Migration user same as app user
```python
# BAD: Same credentials for migrations and runtime
# Migration user needs: CREATE TABLE, ALTER TABLE, DROP TABLE, CREATE INDEX
# App user needs: SELECT, INSERT, UPDATE, DELETE
# Using one user for both means the app can accidentally run DDL
```

### Hardcoded credentials (privilege aspect)
```python
# BAD: Credentials in code — but this reviewer focuses on the privilege level
# The connection uses admin credentials where app-level would suffice
engine = create_engine("postgresql://admin:adminpass@db/myapp")
```

### No connection-level restrictions
```python
# BAD: No statement timeout — a runaway query can hold locks indefinitely
# BAD: No connection limit per user — one service can exhaust all connections
```

### Direct table access instead of views/functions
```python
# BAD: App queries raw tables directly — any schema change breaks the app
# Better: Use views or stored functions as the API contract
db.execute("SELECT id, name, email, internal_notes FROM users")
# internal_notes shouldn't be accessible to the app layer
```

## How to Scan

1. **Check database connection config**: Look for the DB user in connection strings, environment variables, config files. What user does the app connect as?
2. **Check for multiple DB users**: Does the project define different users for different purposes (app, migration, reporting, admin)?
3. **Check SQL files for GRANT statements**: What privileges are granted? To whom?
4. **Check for RLS or tenant scoping**: In multi-tenant apps, is tenant isolation enforced at the DB level or only in application code?
5. **Check Docker/infrastructure files**: docker-compose.yml, Kubernetes secrets, Terraform — what DB users are provisioned?
6. **Check migration config**: Does the migration tool use a different user than the application?
7. **Look for statement timeouts**: `statement_timeout`, `lock_timeout` in connection config or SQL

## Severity Guide

- **Critical**: Application connects as superuser (postgres/root) in production config — full DB control including other databases
- **Critical**: Multi-tenant app with no DB-level tenant isolation and history of data leaks
- **High**: GRANT ALL to application user — app can DROP tables, TRUNCATE, modify schema
- **High**: No separate migration user — app can run DDL accidentally
- **Medium**: No read-only user for reporting — reporting bugs could mutate data
- **Medium**: No row-level security in multi-tenant app (application-level filtering only)
- **Medium**: No statement timeout — runaway queries can cause outages
- **Low**: App accesses tables directly instead of through views — coupling but not a security issue
- **Low**: Missing connection limits per user

## Output Format

After scanning, output:

```
## Privilege Scope

### {Severity}: {short description}

**Location**: `{file}:{line}`
**Current privilege**: {what the DB user can do}
**Needed privilege**: {what the app actually needs}
**Risk**: {what could go wrong — accidental DDL, data leak, full DB compromise}
**Fix**: {create restricted user, add RLS, separate migration user, etc.}
```

End with a Findings Summary table:

| # | Severity | File:Line | Issue | Current Privilege | Fix |
|---|----------|-----------|-------|------------------|-----|
| 1 | Critical | docker-compose.yml:12 | App as superuser | ALL | Create app_user with SELECT/INSERT/UPDATE/DELETE only |

## Rules

- **Don't flag dev/test configs** unless they're likely to leak into production (same config file, no environment separation)
- **Connection strings in .env files are expected** — flag the privilege level, not the existence of a .env file
- **RLS is a recommendation, not a requirement** — application-level filtering is acceptable for many apps, but note the risk for multi-tenant systems
- **Consider the deployment model**: A single-tenant self-hosted app has different privilege needs than a multi-tenant SaaS
