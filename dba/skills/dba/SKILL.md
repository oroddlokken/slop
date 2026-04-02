---
name: dba
description: "Database & SQL deep-dive. Spins up parallel agents — each reviewing through a different lens (injection, n-plus-one, schema-drift, index-coverage, transaction-gaps, query-scatter, connection-mgmt, migration-safety, orm-antipatterns, raw-perf, data-integrity, privilege-scope) — then distills all findings into prioritized action points."
args:
  - name: area
    description: The directory or area to review (optional)
    required: false
user-invokable: true
---

# SQL Health

Deep database audit for codebases with SQL/relational databases. Use this instead of codehealth's query-smells reviewer when you want 12 specialized database lenses rather than one. Use instead of fuzz-my-stuff-up's injection fuzzer when you want a full DBA-style review, not just adversarial probing.

Launch parallel database-focused agents, each analyzing the codebase through a different SQL/database lens, then distill all findings into unified, prioritized action points.

**Scope**: This skill reviews relational databases (PostgreSQL, MySQL, SQLite, SQL Server) only. NoSQL databases (MongoDB, Redis, DynamoDB, Cassandra) are out of scope. If the codebase uses both, run DBA on the SQL portions only.

## Who Does What

- **Orchestrator** (you, the main Claude Code session): Runs Steps 1-4 — asks user questions, prescans the codebase, launches reviewer agents, distills findings.
- **Reviewer agents** (spawned subagents): Receive a read-only snapshot, analyze through one lens, return findings. They do not scan independently, modify code, or interact with live systems.

## Rules

- **Ask the user for launch strategy** (Sequential or 1+Parallel). Default to Sequential. Everything above `---` in the agent template is identical across agents and gets cached by the API after the first agent, reducing input cost by ~90%.
- **The orchestrator prescans the codebase once and passes the snapshot to all agents** — agents do NOT scan independently.
- **Agents inherit the default model** — do not override with a specific model.
- **Run distillation after all agents complete.** Raw output is overwhelming without deduplication and prioritization.

## Workflow

### Step 1: Choose Mode

Ask the user which mode they want:

- **Full** — Run all 12 reviewers, then distill. Most thorough.
- **Quick** — Run 5 high-risk reviewers (injection, n-plus-one, transaction-gaps, schema-drift, data-integrity), then distill. Faster.
- **Pick** — Let the user choose which reviewers to run.

### Severity Definitions (all reviewers)

- **Critical**: SQL injection, data loss risk, data corruption, or security vulnerability
- **High**: Production bugs, significant performance degradation at scale, correctness risk
- **Medium**: Technical debt, scaling concerns, moderate maintenance burden
- **Low**: Minor improvements, optimization opportunities, nice-to-haves

Individual reviewers map their findings to these levels in their Severity Guide section. Reviewers may refine these levels for their domain — when the distill step resolves cross-reviewer conflicts, use these universal definitions as the baseline. During distillation, any reviewer-reported "Critical" that involves only performance or maintainability (not security, data loss, or corruption) is remapped to "High" before tier assignment. See distill.md for the full mapping algorithm.

Available reviewers:

| Reviewer | Lens |
|----------|------|
| injection | SQL injection vectors — string interpolation, f-strings, concatenation near queries |
| n-plus-one | N+1 queries — loops containing DB calls, lazy loading traps |
| schema-drift | Migration files vs model/schema definitions — orphaned columns, type mismatches, missing migrations |
| index-coverage | WHERE/ORDER BY/JOIN columns without corresponding indexes in migrations |
| transaction-gaps | Multi-step writes without transactions, missing rollback, lock contention |
| query-scatter | Raw SQL outside data access layer, same query written differently in multiple places |
| connection-mgmt | Pool config, unclosed cursors, connection-per-request anti-patterns |
| migration-safety | Destructive migrations without guards, large-table ALTERs without batching |
| orm-antipatterns | SELECT *, lazy loads in loops, excessive filter chaining, ORM for bulk ops |
| raw-perf | Full table scans, LIKE '%prefix', functions on indexed columns, implicit casts |
| data-integrity | Missing FK constraints, nullable columns that shouldn't be, orphan-producing deletes |
| privilege-scope | Queries running as superuser, overly broad GRANT, missing row-level security |

If the user does not specify a mode, run Full mode automatically.

### Scope Boundaries

Some reviewers examine similar code from different angles. When findings overlap:
- **injection** owns all SQL injection findings. query-scatter defers to injection for security issues — query-scatter focuses on DRY/maintenance only.
- **n-plus-one** owns loop-query patterns exclusively. orm-antipatterns owns non-loop ORM misuse (SELECT *, eager vs lazy config, bulk ops) and does not examine loops.
- **index-coverage** owns missing indexes. raw-perf owns query-shape inefficiencies (LIKE patterns, function-on-column, implicit casts). Both may flag the same slow query — index-coverage if adding an index fixes it, raw-perf if the query shape itself is the problem.
- **schema-drift** owns model-vs-migration divergence. migration-safety owns the migration files themselves (destructive ops, missing rollback, ordering).
- **transaction-gaps** owns missing transaction boundaries. data-integrity owns missing constraints at the schema level. If a multi-step write has no transaction AND no FK constraint, transaction-gaps takes the finding (the transaction is the immediate fix).
- **connection-mgmt** owns connection lifecycle issues. orm-antipatterns owns ORM-level query patterns. If an ORM misconfiguration causes connection leaks, connection-mgmt takes it.
- **data-integrity** owns missing constraints (FK, UNIQUE, NOT NULL, CHECK, ON DELETE). **privilege-scope** owns DB user permissions, GRANT scope, and RLS policies. If both could flag the same table access pattern, data-integrity takes schema constraints, privilege-scope takes access control.

### Step 1.5: Language & Database Stack Detection

Detect which languages have database operations and what DB stack is in use. This is a database audit — CSS, HTML templates, and image assets are irrelevant unless they contain queries.

**1. Gather files:**
Run `git ls-files` in the target path (or cwd). Skip: `*.png`, `*.jpg`, `*.gif`, `*.svg`, `*.ico`, `*.woff*`, `*.ttf`, `*.lock`, `*.min.js`, `*.min.css`, `.gitignore`, `.gitattributes`, and directories `node_modules/`, `vendor/`, `dist/`, `build/`.

**2. Detect the database stack** (run these greps on all files):
- **ORM**: grep for `from sqlalchemy`, `from django.db`, `from prisma`, `ActiveRecord`, `from tortoise`, `from peewee`, `TypeORM`, `Sequelize`, `from gorm`, `Entity Framework`, `Drizzle`, `Knex`
- **Driver**: grep for `psycopg2`, `asyncpg`, `mysql-connector`, `import pg`, `mysql2`, `sqlite3`, `pymongo`, `import sql` (Go), `diesel`, `sqlx`
- **Migration tool**: check for directories `alembic/`, `migrations/`, `prisma/migrations/`, `db/migrate/`, `flyway/`; grep for `Flyway`, `Liquibase`, `golang-migrate`
- **Database type**: infer from driver/ORM (e.g., psycopg2 = PostgreSQL, mysql2 = MySQL)

**3. Identify DB-active languages:**
For each language (grouped by extension), do a quick grep for DB operation patterns: `execute(`, `query(`, `.objects.`, `SELECT `, `INSERT `, `UPDATE `, `DELETE `, `CREATE TABLE`, `.filter(`, `.where(`, `.find(`, `cursor.`, `session.`, `transaction`, `migration`. Count files with at least one match.

**4. Present a two-tier summary:**
```
Database stack: SQLAlchemy + Alembic on PostgreSQL (psycopg2)

DB-active languages:
- Python — 334 files total, 42 with DB operations (models, queries, migrations)
- SQL — 258 files (migrations + raw queries)

Also in codebase (no DB operations detected):
- HTML — 65 files (templates)
- JavaScript — 46 files
- CSS — 19 files
```

**5. Ask**: "Review all DB-active languages? Add any others?"

DB-active languages are included by default. Non-DB languages are excluded unless the user adds them (e.g., JavaScript might have API client code that constructs queries). After confirmation, pass the final language list to each agent via the `{languages}` placeholder.

**Important:** Do not retain or pass the file list from `git ls-files` to agents. Only the language list, DB stack summary, and file counts are passed.

### Step 1.75: Check for Existing Issue Tracker

Check if the project uses **dcat** (a local CLI issue tracker that stores issues in a `.dogcats/` directory). Run `which dcat`. If the command succeeds (exit code 0) AND a `.dogcats/` directory exists at the target path, run `dcat list --agent-only` to get tracked issues. Pass this issue list to each agent so they can skip concerns that are already tracked. If either check fails, skip this step entirely.

### Step 2: Determine Target

Ask the user (if not already clear):
- **Path**: Which directory to review (default: current working directory)
- **Focus** (optional): A specific area to concentrate on — e.g., `auth`, `payments`, `user-data`, `reporting`, `api`, `migrations`. When set, agents spend ~3x more attention on this area.

### Error Handling

- If `git ls-files` fails (not a git repo, permissions), fall back to `find {path} -type f` and filter by extension.
- If a reviewer's criteria file does not exist at the expected path, skip that reviewer and warn the user.
- If all agents return zero findings, output "No issues found" and skip the distill step.
- If some agents fail or timeout, distill with available results and note which reviewers were skipped.

### Step 2.5: Prescan the Codebase (orchestrator does this once)

Read `scan-steps.md` from this skill's directory and follow its scan procedure. The orchestrator (you) reads all files once, then builds a single `{codebase_snapshot}` block that gets passed to every agent. This avoids 12 agents each independently scanning the same files.

1. Replace `{languages}` and `{focus}` in `scan-steps.md`
2. Follow the scan procedure — read manifests, source files, migrations, schema definitions, etc.
3. Format all collected file contents into the snapshot format specified in `scan-steps.md`
4. Store the result as `{codebase_snapshot}` for use in Step 3

### Step 3: Launch Agents

Use the agent template (`agent.md`). The template places shared content (codebase snapshot, languages, ground rules, output format) before the `---` divider to form a common prompt prefix for API caching.

**Launch strategy** — Ask the user:

- **Sequential** (default) — Launch agents one at a time, each after the previous completes. First agent primes the cache; every subsequent agent reads the shared prefix at ~90% cheaper input. Slowest, cheapest.
- **1+Parallel** — Launch one agent first, wait for it to complete, then launch all remaining in parallel. Nearly as cheap, much faster.

If the user doesn't specify, use **Sequential**.

**Cache structure** — The `---` divider in agent.md is the cache boundary. Everything above it is the shared prefix (identical for all agents). Everything below is per-agent. API prompt caching matches byte-for-byte prefixes, so:
- Shared prefix placeholders (`{codebase_snapshot}`, `{path}`, `{languages}`, `{focus}`, `{known_issues}`) resolve to the **same value** for all agents. Resolve these once and reuse the identical string.
- Per-agent placeholders (`{reviewer}`, `{reviewer_criteria}`) differ per agent. These go below `---` and do not affect cache matching.
- **Never insert per-agent content above the `---` line.** This includes scope boundary rules — append those after `{reviewer_criteria}`, not in the shared prefix.

**Build the shared prefix once:**
1. Read `agent.md` from this skill's directory
2. Replace `{path}` with the target path
3. Replace `{codebase_snapshot}` with the snapshot from Step 2.5
4. Replace `{languages}` with the confirmed language list (e.g., `Python, Shell, SQL, YAML`)
5. If the user specified a focus area, replace `{focus}` with the focus block below. Otherwise replace with an empty string.
6. If dcat issues were found, replace `{known_issues}` with a `## Known Issues (skip these)` section. Otherwise replace with an empty string.
7. Store this as the **resolved template** — the content above `---` is now fixed and identical for all agents.

**For each reviewer, resolve per-agent content:**
1. In the resolved template, replace `{reviewer}` with the reviewer name (e.g., `injection`)
2. Read `reviewers/{reviewer}.md`. If the file does not exist, skip that reviewer and warn the user. Replace `{reviewer_criteria}` with the file contents.
3. For overlapping reviewers (injection/query-scatter, n-plus-one/orm-antipatterns, index-coverage/raw-perf, schema-drift/migration-safety, transaction-gaps/data-integrity, connection-mgmt/orm-antipatterns), append the relevant scope boundary rule from the Scope Boundaries section **after** `{reviewer_criteria}` (below `---`).
4. Pass the result as the agent prompt

**Focus block** (inserted when focus is set):
```
## Focus Area: {area}

Concentrate your analysis primarily on **{area}**. During the scan, go deeper on {area}-related aspects (read more files, check more patterns). In your findings, {area}-related issues should be thoroughly covered — don't just flag them, explain the specific impact.

Other issues are still worth mentioning but give {area} roughly 3x the attention and depth.
```

**Reviewer criteria files** are in this skill's `reviewers/` directory: `injection.md`, `n-plus-one.md`, `schema-drift.md`, `index-coverage.md`, `transaction-gaps.md`, `query-scatter.md`, `connection-mgmt.md`, `migration-safety.md`, `orm-antipatterns.md`, `raw-perf.md`, `data-integrity.md`, `privilege-scope.md`.

### Step 4: Distill

After all agents complete, read `distill.md` from this skill's directory and follow the distillation algorithm.
