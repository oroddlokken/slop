## Prescan the Codebase (orchestrator step)

This file is executed by the **orchestrator** (the main Claude Code session), NOT by individual fuzzer agents. The orchestrator reads files once and passes the results to all agents as a snapshot. Your role is selection (which files to include) and faithful reproduction (each file verbatim); the agents do the analysis.

### Scan Procedure

Read broadly — the goal is to capture enough code across all languages so agents can find real vulnerabilities without re-reading files:

1. Read manifest files (pyproject.toml, package.json, Cargo.toml, go.mod, etc.)
2. Identify entry points: CLI parsers, API routes, event handlers, main functions, form handlers
3. Identify data boundaries: where external input enters the system (HTTP requests, file reads, env vars, stdin, database results, message queues)
4. **Languages in scope:** {languages}. Fuzz all of these.
5. Read key source files across all in-scope languages, focusing on: input parsing/validation, data transformation, error handling, config loading, external service integrations, auth/authz logic
6. Use these patterns to identify files worth including in the snapshot: `eval(`, `innerHTML`, `dangerouslySetInnerHTML`, `unwrap()`, bare `except:`, `subprocess` with `shell=True`, `os.system(`. The fuzzer agents evaluate attack surface.
7. Check for existing validation: schemas, validators, type guards, assert statements, middleware
8. Run `git log --oneline -15`

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
- All source files read
- Git log output (as `### file: git-log.txt`)

Omit:
- Files matching `.env*`, `*.secrets`, `*credentials*.json`, `*.key`, `*.pem`, `secrets.yml` — list by name only
- Binary files — list by name only

**Snapshot size limit**: Run `wc -c` on the selected file list. If the total exceeds ~1,250,000 bytes (≈300K tokens of code), ask the user to narrow scope. Drop whole files (prefer leaf modules; keep shared utilities); never abridge individual files to fit.
