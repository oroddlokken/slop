---
name: dba
description: "Deep database and SQL audit for relational codebases. Use when asked to review queries, schema, migrations, or indexes; when pages are slow and the database is the suspect; before shipping a migration; or when checking for SQL injection and missing constraints. Twelve specialized lenses instead of codehealth's single query-smells reviewer. Spins up parallel agents (injection, n-plus-one, schema-drift, index-coverage, transaction-gaps, query-scatter, connection-mgmt, migration-safety, orm-antipatterns, raw-perf, data-integrity, privilege-scope), then distills findings into prioritized action points. Relational only — NoSQL is out of scope."
argument-hint: "[area]"
disable-model-invocation: true
---

# SQL Health

Deep database audit for codebases with SQL/relational databases. Use this instead of codehealth's query-smells reviewer when you want 12 specialized database lenses rather than one. Use instead of fuzz-my-stuff-up's injection fuzzer when you want a full DBA-style review, not just adversarial probing.

Launch parallel database-focused agents, each analyzing the codebase through a different SQL/database lens, then distill all findings into unified, prioritized action points.

**Scope**: This skill reviews relational databases (PostgreSQL, MySQL, SQLite, SQL Server) only. NoSQL databases (MongoDB, Redis, DynamoDB, Cassandra) are out of scope. If the codebase uses both, run DBA on the SQL portions only.

## Who Does What

- **Orchestrator** (you, the main Claude Code session): Runs Steps 1-4 — asks user questions, prescans the codebase, launches reviewer agents, distills findings.
- **Reviewer agents** (spawned subagents): Receive a read-only snapshot, analyze through one lens, return findings. They do not scan independently, modify code, or interact with live systems.

## Rules

- **Ask the user for mode (Step 1) and launch strategy** (Sequential or Rolling 5). Recommend Sequential — it spreads token spend across the run instead of bursting it. Agents do not share prompt cache with each other, so launch order does not change cost.
- **The orchestrator prescans the codebase once and passes the snapshot to all agents** — agents do NOT scan independently.
- **Agents inherit the default model** — do not override with a specific model.
- **Run distillation after all agents complete.** Raw output is overwhelming without deduplication and prioritization.

## Workflow

### Step 1: Choose Mode

Ask the user which mode they want:

- **Full** — Run all 12 reviewers, then distill (injection, n-plus-one, schema-drift, index-coverage, transaction-gaps, query-scatter, connection-mgmt, migration-safety, orm-antipatterns, raw-perf, data-integrity, privilege-scope). Most thorough.
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

Skip the question only when the user's invocation already named a mode (e.g. "run dba quick" → Quick). A bare `/dba` names none: ask and wait for the answer. Silence is not a mode choice — never fall back to Full without one.

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

### Step 1.6: Auto-Skip Irrelevant Lenses

Drop reviewers whose target patterns aren't in the codebase. Note each drop in the final output's "Reviewers run / skipped" line.

- **No ORM detected** (raw-SQL-only codebase) → drop `orm-antipatterns`. Note: "Skipped orm-antipatterns (no ORM detected)."
- **No migration directory found** (no `alembic/`, `migrations/`, `prisma/migrations/`, `db/migrate/`, `flyway/`, `sql/`, `db/migrations/`) → drop `migration-safety` and `schema-drift`. Note: "Skipped migration-safety, schema-drift (no migrations directory)."
- **No GRANT/REVOKE statements, no row-level-security policies, and no DB-role configuration** → drop `privilege-scope`. Note: "Skipped privilege-scope (no permission code detected)."
- **No connection pool / engine config detected** (no `create_engine`, `createPool`, `new Pool`, etc., and no DB driver imports beyond a single point) → drop `connection-mgmt`. Note: "Skipped connection-mgmt (no connection lifecycle code detected)."

### Step 1.75: Check for Existing Issue Tracker

Check if the project uses **dcat** (a local CLI issue tracker that stores issues in a `.dogcats/` directory). Try running `dcat list --agent-only` directly. If it succeeds, pass the issue list to each agent so they can skip already-tracked concerns. If it errors (dcat not installed, no `.dogcats/` directory), skip this step.

### Step 2: Determine Target

Ask the user (if not already clear):
- **Path**: Which directory to review (default: current working directory)
- **Focus** (optional): A specific area to concentrate on — e.g., `auth`, `payments`, `user-data`, `reporting`, `api`, `migrations`. When set, agents spend ~3x more attention on this area.

### Error Handling

- If `git ls-files` fails (not a git repo, permissions), use the Glob tool (`**/*.{sql,py,ts,...}` patterns) to enumerate files.
- If a reviewer's criteria file does not exist at the expected path, skip that reviewer and warn the user.
- If all agents return zero findings, output "No issues found" and skip the distill step.
- If some agents fail or timeout, distill with available results and note which reviewers were skipped.

### Step 2.4: Check Snapshot Cache

A prior run of this skill may have already produced a snapshot of this codebase. Reuse it before re-reading ~200K of files.

**Build the cache key**:
1. `git_rev` = output of `git rev-parse HEAD` (or `no-git` if not a git repo)
2. `dirty` = output of `git status --porcelain` (any uncommitted change → different state)
3. `path` = absolute target path
4. `langs` = sorted, comma-joined language list from Step 1.5
5. `skill` = `dba`

Concatenate as `{skill}|{path}|{git_rev}|{dirty}|{langs}` and take the first 12 hex chars of `sha256(...)` as `{hash}`.

**Cache file**: `.claude-cache/dba-snapshot-{hash}.md` (relative to target path).

**Check the cache**:
- If the file exists and was modified within the last hour, read it and use its contents as `{codebase_snapshot}`. Skip Step 2.5.
- Otherwise, proceed to Step 2.5. After building the snapshot there, write it to `.claude-cache/dba-snapshot-{hash}.md`. Create `.claude-cache/` if missing, and add `.claude-cache/` to `.gitignore` if not already listed.

The 1-hour TTL is a staleness backstop, not a prompt-cache window: editing a file that is already dirty leaves `git status --porcelain` unchanged, so the key alone can go stale. The cache is per-skill by design — every meta-skill scans for different things, so nothing here is reused by another skill.

### Step 2.5: Prescan the Codebase (orchestrator does this once)

Read `scan-steps.md` from this skill's directory and follow its scan procedure. The orchestrator (you) reads all files once, then builds a single `{codebase_snapshot}` block that gets passed to every agent. This avoids 12 agents each independently scanning the same files.

1. Replace `{languages}` and `{focus}` in `scan-steps.md`
2. Follow the scan procedure — read manifests, source files, migrations, schema definitions, etc.
3. Format all collected file contents into the snapshot format specified in `scan-steps.md`
4. Store the result as `{codebase_snapshot}` for use in Step 3

### Step 3: Launch Agents

Use the agent template (`agent.md`). The template places shared content (codebase snapshot, languages, ground rules, output format) before the `---` divider to form a common prompt prefix for API caching.

**Spawn contract** — how you call the Agent tool, in every launch mode:

- **Never pass `name:`.** A named agent becomes an addressable mailbox teammate, not a subagent. The tool result is `Spawned successfully` plus an agent_id, the findings never come back, and `run_in_background: false` is ignored. `TaskList` and `TaskOutput` cannot see it either. Recovering costs a round of `SendMessage` to every agent asking it to resend.
- **Sequential passes `run_in_background: false`; Rolling 5 passes `run_in_background: true`.** Sequential needs the report in the tool result to know the agent is done. Rolling 5 needs the call to return at once, so the window can stay full.
- **Where the report arrives follows that flag.** Foreground: the Agent tool's return value is the findings — read them out of the tool result, and do not wait for a message or an idle ping. Background: the tool result carries an agent id, and the completion notification carries the findings.
- **Never call `TaskOutput` on a subagent, and never Read its `.output` file.** That path is a symlink to the agent's full JSONL transcript and will overflow your context.
- **Every launched agent must have reported before you distill.** Once the queue is empty, wait out the notifications still outstanding.

**Launch strategy** — Ask the user:

- **Sequential** (default) — Launch agents one at a time, each after the previous completes. Spreads token spend across the run instead of bursting it against the 5-hour quota. Slowest.
- **Rolling 5** — Keep five agents in flight from the first launch to the last. Spawn five with `run_in_background: true`, then spawn the next unlaunched reviewer the moment any completion notification arrives, until the queue is empty. Never let a sixth run: Anthropic rate-limits large simultaneous bursts, and a 429 mid-run wastes the work of every agent that already finished. Refilling per completion is what beats waves of five — a wave leaves each finished slot idle until its slowest agent returns. Same cost as Sequential, fastest.

Skip the question only when the user's invocation already named a strategy; otherwise ask and wait for the answer, recommending **Sequential**.

**Prompt caching** — Agents do not share cached prompt content with each other. Measured over a 16-agent run (2026-08-04): every agent read back the same ~7K tokens of system prompt and tool definitions, then created everything else fresh — including a byte-identical 11K-token snapshot, once per agent.

The cause is breakpoint placement. Caching matches a byte prefix ending at a `cache_control` breakpoint, and the harness sets one after the system prompt and one at the end of each message. The Agent tool takes a single prompt string, so the shared snapshot and the per-agent assignment land inside the same cached unit and can never match across agents. Sharing would require the shared half in its own content block with a breakpoint at that boundary; the Agent tool exposes no way to ask for one.

- **The `---` divider is a section divider, not a cache boundary.** Shared placeholders (`{codebase_snapshot}`, `{path}`, `{languages}`, `{focus}`, `{known_issues}`) still resolve once and stay identical across agents, and per-agent placeholders still go below the line — that keeps the template readable and the resolve step cheap. No cost depends on it.
- **Snapshot size is the lever that does matter.** Each agent writes the whole snapshot to cache once at 1.25× input price. An 11K-token snapshot across 16 agents is ~176K write-priced tokens every run. Trimming the snapshot saves money; launch order does not.

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
3. For overlapping reviewers (see Scope Boundaries), append the relevant scope boundary rule from the Scope Boundaries section **after** `{reviewer_criteria}` (below `---`).
4. Pass the result as the agent prompt

**Focus block** (inserted when focus is set):
```
## Focus Area: {area}

Concentrate your analysis primarily on **{area}**. During the scan, go deeper on {area}-related aspects (read more files, check more patterns). In your findings, {area}-related issues should be thoroughly covered — don't just flag them, explain the specific impact.

Other issues are still worth mentioning but give {area} roughly 3x the attention and depth.
```

**Reviewer criteria files** are in this skill's `reviewers/` directory: `injection.md`, `n-plus-one.md`, `schema-drift.md`, `index-coverage.md`, `transaction-gaps.md`, `query-scatter.md`, `connection-mgmt.md`, `migration-safety.md`, `orm-antipatterns.md`, `raw-perf.md`, `data-integrity.md`, `privilege-scope.md`.

### Amending the Brief Mid-Run

The resolved template is **frozen once the first agent launches** — do not edit it, and do not edit the snapshot file it was built from. Agents that already ran cannot see the change, so editing mid-run leaves two populations of findings built on different facts, with nothing recording which is which.

When you find the brief is wrong mid-run — a prescan claim an agent contradicts, a mis-stated invariant, a file that does not exist — record the correction instead of applying it:

1. **Append to an errata list** for this run. One entry per correction: what the brief claimed, what is actually true, and a `file:line` citation for the correction.
2. **Append the errata to the per-agent half** (below `---`) of every agent launched from then on, under a `## Errata` heading introduced by: "The brief contains errors. The entries below are authoritative wherever they contradict it."
3. **Pass the errata to distill**, noting which agents ran before each entry was added. Distill drops or annotates any earlier finding that rests on a corrected claim.

Agents surface corrections too — a lens that checks a prescan claim and finds it false. Treat those the same way: add an entry, and it binds every agent launched after it.

### Step 4: Distill

Spawn a fresh sub-agent for distillation:

- **Model**: `sonnet`. A fresh agent prevents the synthesis from anchoring on whichever reviewer wrote first or loudest, and Sonnet handles the structured-merge job competently at lower cost.
- **Subagent type**: `Explore`. The agent reads files referenced by findings during validation; no other tool access needed.
- **Instructions**: contents of `distill.md` from this skill's directory.
- **Input**: the `## Findings Summary` table from each completed reviewer, prefixed with `### Reviewer: {name}`. Strip surrounding prose — tables only. Also include which reviewers ran, which were skipped, the dcat issues list (if any), and the focus area (if any).
- **Do not pass the codebase snapshot.** Distill works on structured findings; the snapshot would inflate input by ~200K tokens for no gain (file references in findings already point at the code).

Paste the distill agent's output into your own reply, verbatim and in full.

Only your reply is rendered to the user — the agent's report is not. Never point at it with "the findings are above", "see the report", or similar. Length is not a reason to summarize instead: if the list is long, your reply is long.
