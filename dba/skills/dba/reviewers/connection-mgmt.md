# Find Connection Management Issues

Scan for database connection lifecycle issues: missing pooling, unclosed connections, connection-per-request anti-patterns, and misconfigured pool settings.

## What to Look For

### No connection pooling
```python
# BAD: New connection per request
def get_user(user_id):
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result
```

Should use: a connection pool (`create_engine` with pool, `pg.Pool`, connection pool middleware).

### Unclosed connections/cursors
```python
# BAD: Connection opened but not closed on all paths
conn = sqlite3.connect('app.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM users")
results = cursor.fetchall()
# conn.close() missing — or only on happy path, not on exception
```

```python
# BAD: No context manager — cursor not closed on exception
cursor = db.cursor()
cursor.execute("SELECT * FROM users")
# If an exception occurs here, cursor stays open
return cursor.fetchall()
```

### Connection leaks in error paths
```python
# BAD: Connection closed in try but not in except
try:
    conn = pool.getconn()
    conn.cursor().execute("INSERT ...")
    conn.commit()
    pool.putconn(conn)
except Exception:
    log.error("Failed")
    # conn never returned to pool — leak!
```

### Pool exhaustion risks
```python
# BAD: Pool size too small for concurrent load
engine = create_engine(DATABASE_URL, pool_size=2, max_overflow=0)
# With 50 concurrent requests, 48 will block waiting for a connection
```

### Connection per import / module level
```python
# BAD: Connection created at import time — shared across threads, never refreshed
# db.py
conn = psycopg2.connect(DATABASE_URL)

def query(sql):
    return conn.execute(sql)
```

### No pooling strategy
Application pooling (SQLAlchemy pool, HikariCP) vs external pooling (PgBouncer, ProxySQL) have different characteristics. PgBouncer in transaction mode doesn't support prepared statements or SET commands. Application pooling doesn't survive process restarts.

Flag: projects with >50 concurrent connections and no explicit pooling strategy. Note which approach is in use and whether it fits the deployment model.

### Missing connection timeout/retry
```python
# BAD: No timeout — hangs forever if DB is unreachable
conn = psycopg2.connect(DATABASE_URL)
# No connect_timeout, no retry logic
```

### Connection string in code
```python
# BAD: Hardcoded connection string (also a security issue, but connection-mgmt owns the lifecycle aspect)
engine = create_engine("postgresql://user:password@localhost/mydb")
```

## How to Scan

1. **Find connection creation**: `connect(`, `create_engine(`, `createPool(`, `createConnection(`, `new Pool(`, `pg.connect(`, `mysql.createConnection(`
2. **Check for pooling**: Is a pool configured? What library? What settings (pool_size, max_overflow, timeout)?
3. **Check connection lifecycle**: For each connection creation, trace whether it's properly closed/returned on all code paths (happy path + exception path)
4. **Check for context managers**: `with conn:`, `with pool.connection() as conn:`, `using` statements — these handle cleanup automatically
5. **Check for module-level connections**: Connections created at import time, stored as globals
6. **Check pool settings**: pool_size vs expected concurrency, timeout settings, max_overflow

## Severity Guide

- **Critical**: Connection leaks in error paths — pool exhaustion under load, eventually all connections consumed
- **High**: No connection pooling with concurrent access — connection storms can overwhelm the database
- **High**: Module-level connections shared across threads — thread safety issues, stale connections
- **Medium**: Pool sized too small for expected concurrency — intermittent connection timeouts under load
- **Medium**: Missing connection timeout — hangs if database is unreachable
- **Low**: Hardcoded connection strings (lifecycle aspect — security aspect deferred to injection reviewer)
- **Low**: Cursor not explicitly closed (if using context manager on connection)

## Output Format

After scanning, output:

```
## Connection Management

### {Severity}: {short description}

**Location**: `{file}:{line}`
**Issue**: {no pool / leak / wrong pool size / module-level / no timeout}
**Current**: {what the code does now}
**Risk**: {pool exhaustion, connection storm, thread safety, hang}
**Fix**: {use pool, add context manager, increase pool_size, add timeout, etc.}
```

End with a Findings Summary table:

| # | Severity | File:Line | Issue | Risk | Fix |
|---|----------|-----------|-------|------|-----|
| 1 | Critical | db.py:12 | No close in except block | Pool leak | Use context manager |

## Rules

- **Check the framework's connection handling** — many frameworks (Django, Rails, Express with Knex) manage connections automatically. Don't flag what the framework handles.
- **Context managers count as proper cleanup** — `with conn:` is sufficient, don't also require explicit `.close()`
- **ORMs usually pool by default** — SQLAlchemy's `create_engine` uses a pool. Django uses persistent connections. Check the actual config before flagging.
- **If an ORM misconfiguration causes connection leaks, this reviewer takes it** (not orm-antipatterns)
