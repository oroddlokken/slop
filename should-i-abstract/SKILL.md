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

Check if the project uses **dcat**. Run `which dcat`. If the command succeeds (exit code 0) AND a `.dogcats/` directory exists at the target path, run `dcat list --agent-only` to get tracked issues. Pass this list to the agent so it can skip already-tracked concerns. If either check fails, skip this step.

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

- If `git ls-files` fails (not a git repo, permissions), fall back to `find {path} -type f` and filter by extension.
- If the agent returns zero findings in all three sections, output "No abstraction issues found — DRY balance looks good."
