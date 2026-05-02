---
name: should-i-abstract
description: "Pragmatic DRY review. Finds both under-DRY (true knowledge duplication worth consolidating) and over-DRY (wrong abstractions worth inlining). A single focused agent that makes judgment calls — when to share, when to split, and when to leave it alone."
args:
  - name: area
    description: The directory or area to review (optional)
    required: false
user-invokable: true
---

# Should I Abstract?

Launch a single focused agent to review the codebase through a pragmatic DRY lens — evaluating both directions: code that should be shared AND abstractions that should be inlined back.

## Rules

- **The orchestrator prescans the codebase once and passes the snapshot to the agent.**
- **The agent inherits the default model** — do not override with a specific model.
- **Single agent, single pass.** This is a judgment-heavy review, not a mechanical scan. The agent needs the full picture to make good tradeoff calls.
## Workflow

### Step 1: Determine Target

Ask the user (if not already clear):
- **Path**: Which directory to review (default: current working directory)
- **Focus** (optional): A specific area to concentrate on — e.g., `api`, `models`, `auth`, `utils`, `services`. When set, the agent spends ~3x more attention on this area.

### Step 2: Language Prescan

Detect which languages are in scope:

1. Run `git ls-files` in the target path (or cwd) and group files by extension
2. Map extensions to languages (`.py` -> Python, `.ts`/`.tsx` -> TypeScript, `.go` -> Go, `.sql` -> SQL, `.sh` -> Shell, `.yml`/`.yaml` -> YAML, `.tf` -> Terraform, etc.)
3. Skip: `*.png`, `*.jpg`, `*.gif`, `*.svg`, `*.ico`, `*.woff*`, `*.ttf`, `*.lock`, `*.min.js`, `*.min.css`, `.gitignore`, `.gitattributes`, and directories `node_modules/`, `vendor/`, `dist/`, `build/`
4. Present detected languages sorted by file count
5. Ask: "Are these the languages to review?"
6. Pass confirmed list to the agent via `{languages}`

**Important:** Do not retain or pass the file list from `git ls-files` to the agent. Only use it to identify languages.

### Step 3: Check for Existing Issue Tracker

Check if the project uses **dcat**. Try running `dcat list --agent-only` directly. If it succeeds, pass the issue list to the agent so it can skip already-tracked concerns. If it errors (dcat not installed, no `.dogcats/` directory), skip this step.
### Step 3.5: Check Snapshot Cache

A prior run of this or another meta-skill may have already produced a snapshot of this codebase. Reuse it before re-reading files.

**Build the cache key**:
1. `git_rev` = output of `git rev-parse HEAD` (or `no-git` if not a git repo)
2. `dirty` = output of `git status --porcelain` (any uncommitted change → different state)
3. `path` = absolute target path
4. `langs` = sorted, comma-joined language list from Step 2
5. `skill` = `should-i-abstract`

Concatenate as `{skill}|{path}|{git_rev}|{dirty}|{langs}` and take the first 12 hex chars of `sha256(...)` as `{hash}`.

**Cache file**: `.claude-cache/should-i-abstract-snapshot-{hash}.md` (relative to target path).

**Check the cache**:
- If the file exists and was modified within the last hour, read it and use its contents as `{codebase_snapshot}`. Skip Step 4.
- Otherwise, proceed to Step 4. After building the snapshot there, write it to `.claude-cache/should-i-abstract-snapshot-{hash}.md`. Create `.claude-cache/` if missing, and add `.claude-cache/` to `.gitignore` if not already listed.

The 1-hour TTL matches Anthropic's prompt-cache window — `/codehealth` followed by `/should-i-abstract` 40 minutes later still hits both layers.

### Step 4: Prescan the Codebase

Read `scan-steps.md` from this skill's directory and follow its scan procedure. The orchestrator reads all files once and builds a `{codebase_snapshot}` block.

1. Replace `{languages}` and `{focus}` in `scan-steps.md`
2. Follow the scan procedure
3. Format collected file contents into the snapshot format
4. Store as `{codebase_snapshot}`

### Step 5: Launch Agent

Read `agent.md` from this skill's directory and resolve placeholders:

1. Replace `{path}` with the target path
2. Replace `{codebase_snapshot}` with the snapshot from Step 4
3. Replace `{languages}` with the confirmed language list
4. If the user specified a focus area, replace `{focus}` with the focus block below, replacing `{area}` with the user's specified area. Otherwise replace `{focus}` with an empty string.
5. If dcat issues were found, replace `{known_issues}` with a `## Known Issues (skip these)` section listing them. Otherwise replace with an empty string.
6. Pass the result as the agent prompt

**Focus block** (inserted when focus is set):
```
## Focus Area: {area}

Concentrate your analysis primarily on **{area}**. Go deeper on {area}-related code (read more files, trace more dependencies, check more call sites). {area}-related findings should be thoroughly covered.

Other areas are still worth reviewing but give {area} roughly 3x the attention.
```

### Step 6: Report

Return the agent's findings directly to the user. After presenting results, ask if they want to start working on any items.

### Error Handling

- If `git ls-files` fails (not a git repo, permissions), use the Glob tool (`**/*.{py,ts,...}` patterns) to enumerate files.
- If the agent returns zero findings in all three sections, output "No abstraction issues found — DRY balance looks good."
