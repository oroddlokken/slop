## Prescan the Codebase (orchestrator step)

This file is executed by the **orchestrator** (the main Claude Code session), NOT by the review agent. The orchestrator reads files once and passes the results to the agent as a snapshot.

### Scan Procedure

Read with an eye toward abstractions and sharing patterns:

1. Read manifest files (pyproject.toml, package.json, Cargo.toml, go.mod, *.csproj, etc.) to understand the stack and dependencies
2. Read the README (first 80 lines) and any architecture/design docs
3. **Languages in scope:** {languages}. Review all of these.
4. **Map the abstraction landscape first**: Identify and read shared/common modules — look for `utils/`, `helpers/`, `lib/`, `common/`, `shared/`, `core/`, `base/`, `mixins/` directories and files. These are the existing abstractions the agent needs to know about.
5. Read key source files across all in-scope languages. Distribute effort proportionally to file count but ensure every language gets meaningful coverage (at least 3-5 files each). Prioritize:
   - Shared utilities and helper modules (critical for DRY analysis)
   - Service layers and business logic
   - API routes/controllers (where inline duplication often lives)
   - Models/schemas
   - Entrypoints (main.*, index.*, app.*)
   Read 10-15% of files or at least 5 per language, whichever is greater. Stop when additional files show no new patterns.
6. **Check for parallel implementations**: Look for files with similar names across different modules (e.g., `user_service.py` and `account_service.py`, `auth_middleware.js` and `admin_middleware.js`). These often contain structural duplication.
7. Detect tests: test/, tests/, spec/, __tests__/ — note test framework and coverage
8. Git history: run `git log --oneline -20` — look for recent additions that might duplicate existing code
9. Check for recent bulk additions (possible LLM-generated code): `git log --oneline --diff-filter=A -20` to see recently added files

{focus}

### Build the Snapshot

After reading, format ALL collected file contents into a single snapshot block. This is what gets passed to the agent via the `{codebase_snapshot}` placeholder.

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
- All source files read (prioritize shared/utility modules)
- Git log output (as `### file: git-log.txt`)
- Recently added files log (as `### file: git-log-added.txt`)

Omit:
- Files matching `.env*`, `*.secrets`, `*credentials*.json`, `*.key`, `*.pem`, `secrets.yml` — list by name only
- Binary files — list by name only

**Snapshot size limit**: If the snapshot exceeds ~80K tokens (~400 source files), ask the user to narrow scope before proceeding.
