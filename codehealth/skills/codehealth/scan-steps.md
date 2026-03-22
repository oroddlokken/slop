## Scan the Codebase

Build a project dossier by reading key files. Read broadly — the goal is to see enough code across all languages to catch real issues:

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
8. Detect tests: test/, tests/, spec/, __tests__/ — note test framework and approximate coverage
9. Check CI/CD: .github/workflows/, .gitlab-ci.yml, Jenkinsfile — look at what's linted, tested, checked
10. Git history snapshot: run `git log --oneline -20` — assess commit quality and recent activity areas
11. Check for config management: config modules, settings files, feature flags. Note whether `.env` or secrets files exist, but do not read their contents — scan for credential patterns by filename and grep instead.

### What to Look For

When reading each source file, note:
- Function/method length and nesting depth
- Repeated code patterns (similar blocks across files)
- Inline operations that bypass abstraction layers (raw SQL in handlers, raw HTTP in business logic)
- Error handling patterns (or lack thereof)
- Hardcoded values (URLs, ports, credentials, magic numbers)
- Naming conventions and consistency
- Import patterns and dependency usage
- Test coverage indicators (corresponding test files exist?)

### Prioritization

Focus findings on what matters most for code maintainability:
- **Correctness/security issues** always take priority over style
- **Structural problems** (duplication, missing abstractions) matter more than individual code smells
- **High-traffic code** (routes, core business logic) matters more than utilities or scripts

{focus}

All findings MUST reference actual code with file paths and line ranges.
