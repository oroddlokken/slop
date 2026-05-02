## Prescan the Codebase (orchestrator step)

This file is executed by the **orchestrator** (the main Claude Code session), NOT by individual review agents. The orchestrator reads files once and passes the results to all agents as a snapshot. Your role is selection (which files to include) and faithful reproduction (each file verbatim); the agents do the analysis.

### Scan Procedure

This is a database-focused scan. Read broadly but prioritize database-related code — migrations, models, queries, schema definitions, connection config:

1. Read manifest files (pyproject.toml, package.json, Cargo.toml, go.mod, Gemfile, pom.xml, *.csproj, etc.) to understand the stack and dependencies. Pay special attention to database drivers and ORMs (SQLAlchemy, Django ORM, Prisma, ActiveRecord, Sequelize, TypeORM, GORM, Diesel, Entity Framework, etc.)
2. Read the README (first 80 lines) and any architecture/design docs
3. **Languages in scope:** {languages}. Review all of these — do not skip any.
4. Detect database stack:
   - **ORM**: SQLAlchemy, Django ORM, Prisma, ActiveRecord, Sequelize, TypeORM, Tortoise, Peewee, GORM, Diesel, Entity Framework, Drizzle, Knex, etc.
   - **Driver**: psycopg2, asyncpg, mysql-connector, pg, mysql2, sqlite3, pymongo, etc.
   - **Migration tool**: Alembic, Django migrations, Prisma migrate, ActiveRecord migrations, Flyway, Liquibase, knex migrations, golang-migrate, etc.
   - **Database type**: PostgreSQL, MySQL, SQLite, etc. (infer from driver/connection config)
4a. **If no ORM detected:**
   - All database access is raw SQL via drivers. Read ALL .sql files exhaustively.
   - If a migration tool exists (Flyway, golang-migrate): read all migration SQL files.
   - If no migration tool and no .sql files: schema is managed externally — note this in the snapshot and proceed with code-level analysis only.
   - The orm-antipatterns reviewer is not applicable — orchestrator should skip it.
5. **Read ALL migration files** — migrations are usually small and schema-critical. Read every file in directories matching: `migrations/`, `alembic/versions/`, `db/migrate/`, `prisma/migrations/`, `flyway/`, `sql/`, `db/migrations/`. These define the ground truth schema.
6. **Read ALL model/schema definition files** — ORM model files, Prisma schema, Django models.py, SQLAlchemy models, etc. Read exhaustively — these are the other half of the schema picture.
7. **Read ALL .sql files** — seed data, stored procedures, views, functions, triggers. These are often missed but contain critical database logic.
8. Read database configuration: connection pooling config, database URLs (redact credentials), timeout settings, replica config
9. Read key source files **across all in-scope languages** that contain database operations. Distribute effort proportionally to file count but ensure every language gets meaningful coverage (at least 3-5 files each). Prioritize:
   - Repository/DAO/query modules — the data access layer
   - API routes/controllers that touch the database
   - Background jobs/workers/tasks that run queries
   - CLI commands/scripts that interact with the database
   - Service layer code with business logic involving DB operations
   Read 10-15% of non-DB source files (minimum 5, maximum 50). Stop when 3 consecutive files reveal no new database query patterns.
10. Detect tests: look for database test fixtures, test factories, test database setup. Note whether tests use a real database, mocks, or in-memory DB.
11. Check CI/CD: .github/workflows/, .gitlab-ci.yml, Jenkinsfile — look for migration steps, database seeding, schema validation
12. Git history snapshot: run `git log --oneline -20` for general activity, then `git log --oneline -20 -- '**/migrations/**' '**/*.sql' '**/models*'` for recent schema changes
13. Use these patterns to identify files worth including in the snapshot — match any pattern, add the file. The agents judge severity:
    - String interpolation in SQL: `f"SELECT`, `f"INSERT`, `f"UPDATE`, `f"DELETE`, `"SELECT.*" +`, `"SELECT.*" %`, `format(.*SELECT`
    - Raw SQL execution: `execute(`, `raw(`, `cursor.`, `db.query(`, `.rawQuery(`, `Repo.query(`
    - Transaction markers: `BEGIN`, `COMMIT`, `ROLLBACK`, `atomic`, `transaction`, `session.commit`, `.transacting(`
    - Connection patterns: `create_engine(`, `connect(`, `createPool(`, `createConnection(`, `new Pool(`
    - ORM query patterns: `.filter(`, `.where(`, `.find(`, `.query(`, `.objects.`, `.select(`, `.join(`, `.include(`, `.populate(`

{focus}

### Build the Snapshot

After reading, reproduce each selected file verbatim — full content, no elisions, no commentary, no headings outside `### file:` blocks. The result is what gets passed to agents via the `{codebase_snapshot}` placeholder.

Format each file as:

````
### file: <relative_path>
```<ext>
<full file contents>
```
````

Include:
- All manifest files read
- README excerpt
- All migration files (every single one)
- All model/schema definition files
- All .sql files
- Database configuration files
- Source files with database operations
- CI/CD config files
- Git log output (as `### file: git-log.txt`)
- Schema-change git log (as `### file: git-log-schema.txt`)

Omit:
- Files matching `.env*`, `*.secrets`, `*credentials*.json`, `*.key`, `*.pem`, `secrets.yml` — list by name only
- Binary files — list by name only

**Snapshot size limit**: Run `wc -c` on the selected file list. If the total exceeds ~1,250,000 bytes (≈300K tokens of code), ask the user to narrow scope. Drop whole files (prefer leaf modules; keep shared utilities); never abridge individual files to fit.
