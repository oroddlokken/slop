# Find Writes That Do Not Survive Power Loss

Scan for settings that let the database acknowledge a write it can still lose. A commit that returns success and then vanishes when the machine loses power is the failure this lens owns.

## What to Look For

### PostgreSQL durability turned off

```ini
# BAD: postgresql.conf — the server acknowledges a commit before the WAL reaches the disk
fsync = off
synchronous_commit = off
full_page_writes = off
```

```yaml
# BAD: docker-compose.yml — the same settings, passed as flags
command: postgres -c fsync=off -c full_page_writes=off
```

`fsync = off` and `full_page_writes = off` risk an unreadable cluster, not just lost transactions. `synchronous_commit = off` loses commits from the last window — three times `wal_writer_delay`, 600 ms by default. Check `ALTER SYSTEM SET` in bootstrap SQL too; it outranks the config file.

### SQLite journal and sync pragmas

```python
# BAD: the write returns before the data reaches the disk
conn.execute("PRAGMA synchronous = OFF")
conn.execute("PRAGMA journal_mode = MEMORY")
```

`journal_mode = MEMORY` holds the rollback journal in RAM, so a crash mid-transaction leaves the file corrupt with nothing to roll back from. The same settings arrive through connection strings: `?_journal_mode=MEMORY`, `?_synchronous=OFF`.

### MySQL flush settings

```ini
# BAD: my.cnf — a commit is durable once a second, not at commit
innodb_flush_log_at_trx_commit = 2
sync_binlog = 0
```

`= 2` writes the redo log at commit and flushes it once a second, so power loss costs that second. `= 0` costs the same second on an mysqld crash alone. `sync_binlog = 0` loses binlog events that replicas and point-in-time recovery read.

### UNLOGGED tables holding data nobody reloads

```sql
-- BAD: not WAL-logged, not replicated, truncated after any unclean shutdown
CREATE UNLOGGED TABLE sessions (id uuid PRIMARY KEY, user_id bigint, expires_at timestamptz);
```

UNLOGGED is correct for a table a job rebuilds. Find the rebuild before accepting it; with no reload path the data is gone at the first crash.

### The data directory on ephemeral storage

```yaml
# BAD: the database lives in the pod, so a reschedule is a wipe
volumes:
  - name: pgdata
    emptyDir: {}
```

Same shape: a `tmpfs` mount over the data directory, a SQLite file under `/tmp`, a compose service whose `volumes:` list omits the data path. The container filesystem goes when the container does.

### An asynchronous replica read as committed

A write to the primary, then a read from a replica that has not caught up. Or failover promoting an async replica: transactions the primary acknowledged and had not shipped are gone.

Look for a reader/writer split with no lag check, `synchronous_commit = local` or `off` with a standby configured, MySQL asynchronous replication under automatic promotion, and a connection string naming a replica inside a write-then-read path.

## What NOT to Flag

- **Backup and restore policy.** Whether an operator holds a dump, a PITR window or an archive is out of scope. This lens reviews the durability settings the repo evidences.
- **A default you did not read.** PostgreSQL ships `synchronous_commit = on`, SQLite ships `synchronous = FULL`, MySQL ships `innodb_flush_log_at_trx_commit = 1`. An absent setting is the durable value.
- **Test and CI configuration.** `fsync = off` on a throwaway test database is a speed choice on data nobody keeps. The finding needs a path from that file to production — name the file and what loads it.
- **Derived data with a reload path.** An UNLOGGED cache table or a scratch database that a job rebuilds is the intended use of both.
- **A managed database whose storage config lives outside the repo.** RDS, Aurora and Cloud SQL set durability in the provider's console or in another repo. Say the evidence is not here, and do not grade it.
- **`synchronous = NORMAL` under SQLite WAL.** Recent commits can be lost; the file stays intact. Flag it only where a user is told the write is durable.
- **The process's own files after `kill -9`.** Those are outside this skill. This lens stops at the database's acknowledgement.

## How to Scan

1. **Find server configuration the repo carries**: `postgresql.conf`, `my.cnf`, `my.ini`, `*.conf` under `docker/`, `command:` and `args:` lines in compose files and Kubernetes manifests, `ALTER SYSTEM SET` in bootstrap SQL
2. **Grep the settings by name**: `fsync`, `synchronous_commit`, `full_page_writes`, `innodb_flush_log_at_trx_commit`, `sync_binlog`, `innodb_doublewrite`
3. **Grep the SQLite forms**: `PRAGMA synchronous`, `PRAGMA journal_mode`, `_journal_mode=`, `_synchronous=`
4. **Grep for `UNLOGGED`** in migrations and schema files. For each hit, find who writes the table and what rebuilds it
5. **Trace the data directory**: `PGDATA`, `datadir`, `/var/lib/postgresql/data`, `/var/lib/mysql`, the SQLite file path. Check each against `volumes:`, `volumeMounts:`, `emptyDir`, `tmpfs`, and `/tmp`
6. **Find replica configuration**: reader/writer connection strings, `standby`, `readonly`, `primary_conninfo`, proxy and load balancer config. Then find the write-then-read paths in the code
7. **Split production from test on every hit**: name the config file and name what loads it in each environment

## Severity Guide

- **Critical**: `fsync = off`, `full_page_writes = off`, or SQLite `journal_mode = MEMORY` on a production path — a power cut can leave the database unreadable, not merely short a few commits
- **Critical**: The data directory on `emptyDir`, `tmpfs` or the container filesystem — a restart or a reschedule destroys everything committed
- **High**: `synchronous_commit = off` or `innodb_flush_log_at_trx_commit = 2` — acknowledged commits inside the flush window are lost on power loss
- **High**: An UNLOGGED table holding data with no reload path — truncated by any unclean shutdown
- **High**: A write acknowledged, then read from or failed over to an asynchronous replica — the read misses it, the promotion loses it
- **Medium**: `sync_binlog = 0` where the binlog feeds replication or point-in-time recovery
- **Medium**: A durability setting in a config shared by test and production, where the production path is unclear
- **Low**: A durability setting confined to a test-only config with no production path — recorded, not a defect

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Setting | What power loss costs | Fix |
|---|----------|-----------|---------|----------------------|-----|
| 1 | Critical | docker/postgres.conf:14 | `fsync = off` | the whole cluster — corruption, not a bounded tail | delete the line; the default is `on` |

## Rules

- **Read the default before flagging an absence** — a setting nobody wrote sits at its shipped value, and every shipped default here is durable
- **Name the window, not the verdict** — "commits from the last 600 ms" is what the reader trades against; "not durable" is not
- **Separate corruption from loss** — `fsync = off` risks an unreadable cluster, `synchronous_commit = off` loses a bounded tail. Grade them apart
- **Find the reload path before accepting UNLOGGED or ephemeral storage** — a rebuild job makes it correct, and no rebuild makes it Critical
- **Name the environment and its loader** — a setting is a finding once you show which file production reads
- **Name the cost of the fix** — restoring `fsync` costs write latency, and a fix presented as free gets reverted under load
- **Backup and restore policy is out of scope** — this reviewer grades the settings, never whether someone holds a copy
- **transaction-gaps owns missing transaction boundaries.** This reviewer owns whether a committed transaction survives the machine. A multi-step write with no transaction is theirs, even where durability is also off
- **The process's own files after `kill -9` are outside this skill.** Name the gap in the finding rather than filing its row
