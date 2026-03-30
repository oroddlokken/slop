## Prescan the Codebase (orchestrator step)

This file is executed by the **orchestrator** (the main Claude Code session), NOT by individual fuzzer agents. The orchestrator reads files once and passes the results to all agents as a snapshot.

### Scan Procedure

Read broadly — the goal is to capture enough code across all languages so agents can find real vulnerabilities without re-reading files:

1. Read manifest files (pyproject.toml, package.json, Cargo.toml, go.mod, etc.)
2. Identify entry points: CLI parsers, API routes, event handlers, main functions, form handlers
3. Identify data boundaries: where external input enters the system (HTTP requests, file reads, env vars, stdin, database results, message queues)
4. **Languages in scope:** {languages}. Fuzz all of these.
5. Read key source files across all in-scope languages, focusing on: input parsing/validation, data transformation, error handling, config loading, external service integrations, auth/authz logic
6. Grep for risk patterns: `eval(`, `innerHTML`, `dangerouslySetInnerHTML`, `unwrap()` without justification, bare `except:`, `subprocess` with `shell=True`, `os.system(`. Even 1 instance with user input is a high-priority attack surface for fuzzer agents.
7. Check for existing validation: schemas, validators, type guards, assert statements, middleware
8. Run `git log --oneline -15`

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
- All source files read
- Git log output (as `### file: git-log.txt`)

Omit:
- Files matching `.env*`, `*.secrets`, `*credentials*.json`, `*.key`, `*.pem`, `secrets.yml` — list by name only
- Binary files — list by name only

**Snapshot size limit**: If the snapshot exceeds ~80K tokens (~400 source files), ask the user to narrow scope before proceeding.
