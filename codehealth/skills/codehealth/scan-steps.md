## Prescan the Codebase (orchestrator step)

This file is executed by the **orchestrator** (the main Claude Code session), NOT by individual review agents. The orchestrator reads files once and passes the results to all agents as a snapshot.

### Scan Procedure

Read broadly — the goal is to capture enough code across all languages so agents can catch real issues without re-reading files:

1. Read manifest files (pyproject.toml, package.json, Cargo.toml, go.mod, *.csproj, etc.) to understand the stack, dependencies, and project structure
2. Read the README (first 80 lines) and any architecture/design docs
3. **Languages in scope:** {languages}. Review all of these — do not skip any.
4. Detect framework: Django, Flask, FastAPI, Express, Rails, Spring, etc.
5. Detect database: ORM config, migration files, raw SQL files, connection strings
6. Read key source files **across all in-scope languages**. Distribute effort proportionally to file count but ensure every language gets meaningful coverage (at least 3–5 files each). Read files until you can identify patterns. For each language, read 10–15% of files or at least 5, whichever is greater. Stop when additional files show no new patterns. Prioritize entrypoints (main.*, index.*, app.*), API routes/controllers, models/schemas, services/business logic, then utility modules. Common file types to look for:
   - SQL migrations (`migrations/*.sql`, `alembic/versions/*.py`, `db/*.sql`) — schema changes, data migrations, stored procedures
   - JS/TS files in Python/Go/Ruby projects — build configs, frontend logic, API clients
   - Shell scripts (`.sh`, `.bash`) — deployment, setup, CI glue
   - Config-as-code (Terraform `.tf`, Ansible `.yml`, Docker `Dockerfile`)
7. Detect tests: test/, tests/, spec/, __tests__/ — note test framework and approximate coverage
8. Check CI/CD: .github/workflows/, .gitlab-ci.yml, Jenkinsfile — look at what's linted, tested, checked
9. Git history snapshot: run `git log --oneline -20` — assess commit quality and recent activity areas
10. Check for risk patterns: grep for `eval(`, `innerHTML`, `dangerouslySetInnerHTML`, `unwrap()` without justification, bare `except:`, `Any` type annotations. Even 1 instance of `eval()`/`innerHTML` with user input is a red flag; bare `except:`/`unwrap()` are concerns at >5 occurrences.
11. Check for config management: config modules, settings files, feature flags. Note whether `.env` or secrets files exist, but do not read their contents — scan for credential patterns by filename and grep instead.

{focus}

### Build the Snapshot

After reading, format ALL collected file contents into a single snapshot block. This is what gets passed to agents via the `{codebase_snapshot}` placeholder.

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
- All source files read
- CI/CD config files
- Git log output (as `### file: git-log.txt`)

Omit:
- Files matching `.env*`, `*.secrets`, `*credentials*.json`, `*.key`, `*.pem`, `secrets.yml` — list by name only
- Binary files — list by name only

**Snapshot size limit**: If the snapshot exceeds ~80K tokens (~400 source files), ask the user to narrow scope before proceeding.
