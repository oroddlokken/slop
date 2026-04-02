# DBA

Database & SQL deep-dive. Spins up parallel agents — each reviewing through a different lens — then distills all findings into prioritized action points.

## What you get

Up to 12 agents independently scan your codebase, each through a different database quality lens. After all finish, findings are deduplicated and distilled into:

- **Fix Now** — SQL injection, data corruption, missing transactions
- **Should Address** — N+1 queries, missing indexes, schema drift
- **Improve** — scattered queries, ORM misuse, connection config
- **Consider** — minor optimizations, privilege scope tuning
- **Skipped Noise** — false positives and trivial findings (ignored)

Every action item includes a file path, line number, and concrete fix.

## Lenses

| Lens | Focus |
|------|-------|
| injection | SQL injection vectors — string interpolation, f-strings, concatenation near queries |
| n-plus-one | N+1 queries — loops containing DB calls, lazy loading traps |
| schema-drift | Migration files vs model/schema definitions — orphaned columns, type mismatches |
| index-coverage | WHERE/ORDER BY/JOIN columns without corresponding indexes |
| transaction-gaps | Multi-step writes without transactions, missing rollback, deadlocks |
| query-scatter | Raw SQL outside data access layer, same query in multiple places |
| connection-mgmt | Pool config, unclosed cursors, pooling strategy, connection leaks |
| migration-safety | Destructive migrations without guards, large-table ALTERs without batching |
| orm-antipatterns | SELECT *, bulk ops in loops, count vs exists, get_or_create races |
| raw-perf | Full table scans, leading wildcard LIKE, offset pagination, functions on indexed columns |
| data-integrity | Missing FK constraints, nullable gaps, orphan-producing deletes, missing CHECK |
| privilege-scope | Superuser connections, overly broad GRANT, missing row-level security |

## Modes

| Mode | What runs |
|------|-----------|
| Full | All 12 lenses (default) |
| Quick | 5 high-risk: injection, n-plus-one, transaction-gaps, schema-drift, data-integrity |
| Pick | You choose which lenses to run |

## Scope

Reviews relational databases (PostgreSQL, MySQL, SQLite, SQL Server). NoSQL is out of scope.

Detects your DB stack automatically (ORM, driver, migration tool, database type) and tailors findings to your specific framework.

## Installation

Tell your agent to read this repository and ask it to help you integrate it into your Claude Code setup as a skill.
