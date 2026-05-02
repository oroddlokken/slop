---
name: codehealth
description: "Meta code quality review. Spins up parallel agents — each reviewing through a different lens (duplicates, extract-logic, simplify-code, hardcoded, error-gaps, complexity, query-smells, dead-code, naming, dep-hygiene, test-gaps, type-structs) — then distills all findings into prioritized action points."
args:
  - name: area
    description: The directory or area to review (optional)
    required: false
user-invokable: true
---

# Code Health

Launch parallel code-quality agents, each analyzing the codebase through a different lens, then distill all findings into unified, prioritized action points.

## Rules

- **Ask the user for launch strategy** (Sequential or 1+Parallel). Default to Sequential. Everything above `---` in the agent template is identical across agents and gets cached by the API after the first agent, reducing input cost by ~90%.
- **The orchestrator prescans the codebase once and passes the snapshot to all agents** — agents do NOT scan independently.
- **Agents inherit the default model** — do not override with a specific model.
- **Run distillation after all agents complete.** Raw output is overwhelming without deduplication and prioritization.
## Workflow

### Step 1: Choose Mode

Ask the user which mode they want:

- **Full** — Run all 12 reviewers in parallel, then distill (duplicates, extract-logic, simplify-code, hardcoded, error-gaps, complexity, query-smells, dead-code, naming, dep-hygiene, test-gaps, type-structs).
- **Quick** — Run 5 high-risk reviewers (duplicates, complexity, error-gaps, hardcoded, type-structs), then distill. Faster.
- **Pick** — Let the user choose which reviewers to run.

### Severity Definitions (all reviewers)

- **Critical**: Security vulnerability, data loss risk, or financial impact
- **High**: Production bugs, significant maintenance burden, correctness risk
- **Medium**: Technical debt, code clarity issues, moderate maintenance cost
- **Low**: Minor improvements, style consistency, nice-to-haves

Individual skills map their findings to these levels in their Severity Guide section. Reviewers may refine these levels for their domain — when the distill step resolves cross-reviewer conflicts, use these universal definitions as the baseline. A reviewer-specific "Critical" that doesn't involve security or data loss maps to "High" in the final output.

Available reviewers:

| Reviewer | Lens |
|----------|------|
| duplicates | Copy-pasted and near-identical code blocks |
| extract-logic | Inline operations that should be functions/methods |
| simplify-code | Over-engineered solutions, unnecessary abstractions |
| hardcoded | Magic strings, numbers, URLs, credentials in code |
| error-gaps | Missing, swallowed, or inconsistent error handling |
| complexity | Long functions, deep nesting, high branching |
| query-smells | N+1 queries, raw SQL in loops, missing parameterization |
| dead-code | Unused functions, unreachable branches, dead routes |
| naming | Inconsistent naming conventions, ambiguous identifiers |
| dep-hygiene | Unused imports, unnecessary dependencies, outdated deps |
| test-gaps | Critical code paths lacking test coverage |
| type-structs | Raw dicts/lists/tuples that should be dataclasses or typed structures |

If the user does not specify a mode, run Full mode automatically.

### Scope Boundaries

Some reviewers examine similar code from different angles. When findings overlap:
- **query-smells** owns all database findings (N+1, SQL injection, scattered queries). extract-logic defers to query-smells for database issues.
- **dep-hygiene** owns package-level dependency issues (unused entries in manifests). dead-code owns file-level unused imports.
- **complexity** targets mechanical metrics (length, nesting, branches). extract-logic targets logical boundaries (multi-step operations in wrong layer). Both may flag the same long function — complexity measures the shape, extract-logic measures responsibility.
- **duplicates** flags copied code. extract-logic flags inline operations. If code is both duplicated AND inline, duplicates takes precedence.

### Step 1.5: Language Prescan

Detect which languages are in scope so agents review all of them, not just the largest.

1. Run `git ls-files` in the target path (or cwd) and group files by extension
2. Map extensions to languages (e.g., `.py` → Python, `.ts`/`.tsx` → TypeScript, `.go` → Go, `.sql` → SQL, `.sh` → Shell, `.yml`/`.yaml` → YAML, `.tf` → Terraform, etc.)
3. Skip files matching: `*.png`, `*.jpg`, `*.gif`, `*.svg`, `*.ico`, `*.woff*`, `*.ttf`, `*.lock`, `*.min.js`, `*.min.css`, `.gitignore`, `.gitattributes`, and directories `node_modules/`, `vendor/`, `dist/`, `build/`
4. Present the detected languages to the user sorted by file count, e.g.:
   ```
   Detected languages:
   - Python (42 files)
   - Shell (12 files)
   - SQL (8 files)
   - YAML (5 files)
   ```
5. Ask: "Are these the languages to review? (Remove or add any)"
6. After confirmation, pass the final language list to each agent via the `{languages}` placeholder

**Important:** Do not retain or pass the file list from `git ls-files` to agents. It is only used here to identify languages.

### Step 1.6: Auto-Skip Irrelevant Lenses

Drop reviewers whose target patterns aren't in the codebase. Note each drop in the final output's "Reviewers run / skipped" line.

- **No SQL/ORM detected** (no SQL keywords, no ORM imports, no `.sql` files in any in-scope language) → drop `query-smells`. Note: "Skipped query-smells (no SQL/ORM detected)."
- **No external dependencies** (manifests are absent or empty — no `pyproject.toml`, no `package.json`, etc.) → drop `dep-hygiene`. Note: "Skipped dep-hygiene (no manifest files found)."
- **No tests directory and no test framework imports** → drop `test-gaps`. Note: "Skipped test-gaps (no test infrastructure detected)."

### Step 1.75: Check for Existing Issue Tracker

Check if the project uses **dcat** — a local issue tracker (CLI tool). Try running `dcat list --agent-only` directly. If it succeeds, pass the issue list to each agent so they can skip already-tracked concerns. If it errors (dcat not installed, no `.dogcats/` directory), skip this step.
### Step 2: Determine Target

Ask the user (if not already clear):
- **Path**: Which directory to review (default: current working directory)
- **Focus** (optional): A specific area to concentrate on — e.g., `api`, `models`, `auth`, `payments`, `database`, `tests`. When set, agents spend ~3x more attention on this area.

### Error Handling

- If `git ls-files` fails (not a git repo, permissions), use the Glob tool (`**/*.{py,ts,...}` patterns) to enumerate files.
- If a reviewer's criteria file does not exist at the expected path, skip that reviewer and warn the user.
- If all agents return zero findings, output "No issues found" and skip the distill step.
- If some agents fail or timeout, distill with available results and note which reviewers were skipped.

### Step 2.4: Check Snapshot Cache

A prior run of this or another meta-skill may have already produced a snapshot of this codebase. Reuse it before re-reading ~200K of files.

**Build the cache key**:
1. `git_rev` = output of `git rev-parse HEAD` (or `no-git` if not a git repo)
2. `dirty` = output of `git status --porcelain` (any uncommitted change → different state)
3. `path` = absolute target path
4. `langs` = sorted, comma-joined language list from Step 1.5
5. `skill` = `codehealth`

Concatenate as `{skill}|{path}|{git_rev}|{dirty}|{langs}` and take the first 12 hex chars of `sha256(...)` as `{hash}`.

**Cache file**: `.claude-cache/codehealth-snapshot-{hash}.md` (relative to target path).

**Check the cache**:
- If the file exists and was modified within the last hour, read it and use its contents as `{codebase_snapshot}`. Skip Step 2.5.
- Otherwise, proceed to Step 2.5. After building the snapshot there, write it to `.claude-cache/codehealth-snapshot-{hash}.md`. Create `.claude-cache/` if missing, and add `.claude-cache/` to `.gitignore` if not already listed.

The 1-hour TTL matches Anthropic's prompt-cache window — `/dba` followed by `/codehealth` 40 minutes later still hits both layers (this disk cache and the prompt cache when the next skill primes its first agent).

### Step 2.5: Prescan the Codebase (orchestrator does this once)

Read `scan-steps.md` from this skill's directory and follow its scan procedure. The orchestrator (you) reads all files once, then builds a single `{codebase_snapshot}` block that gets passed to every agent. This avoids 12 agents each independently scanning the same files.

1. Replace `{languages}` and `{focus}` in `scan-steps.md`
2. Follow the scan procedure — read manifests, source files, CI/CD, git log, etc.
3. Format all collected file contents into the snapshot format specified in `scan-steps.md`
4. Store the result as `{codebase_snapshot}` for use in Step 3

### Step 3: Launch Agents

Use the agent template (`agent.md`). The template places shared content (codebase snapshot, languages, ground rules, output format) before the `---` divider to form a common prompt prefix for API caching.

**Launch strategy** — Ask the user:

- **Sequential** (default) — Launch agents one at a time, each after the previous completes. First agent primes the cache; every subsequent agent reads the shared prefix at ~90% cheaper input. Slowest, cheapest.
- **1+Parallel** — Launch one agent first to prime the cache, then launch remaining agents in parallel batches of at most 5. Anthropic rate-limits large simultaneous bursts, so batching past 5 triggers 429s mid-run and wastes the work of any agent that already completed. Nearly as cheap as Sequential, much faster.

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
6. If dcat issues were found, replace `{known_issues}` with a `## Known Issues (skip these)` section listing them. Otherwise replace with an empty string.
7. Store this as the **resolved template** — the content above `---` is now fixed and identical for all agents.

**For each reviewer, resolve per-agent content:**
1. In the resolved template, replace `{reviewer}` with the reviewer name (e.g., `duplicates`)
2. Read `reviewers/{reviewer}.md`. If the file does not exist, skip that reviewer and warn the user. Replace `{reviewer_criteria}` with the file contents.
3. For overlapping reviewers (duplicates/extract-logic, complexity/extract-logic, query-smells/extract-logic, dep-hygiene/dead-code), append the relevant scope boundary rule from the Scope Boundaries section **after** `{reviewer_criteria}` (below `---`).
4. Pass the result as the agent prompt

**Focus block** (inserted when focus is set):
```
## Focus Area: {area}

Concentrate your analysis primarily on **{area}**. During the scan, go deeper on {area}-related aspects (read more files, check more patterns). In your findings, {area}-related issues should be thoroughly covered — don't just flag them, explain the specific impact.

Other issues are still worth mentioning but give {area} roughly 3x the attention and depth.
```

**Reviewer criteria files** are in this skill's `reviewers/` directory: `duplicates.md`, `extract-logic.md`, `simplify-code.md`, `hardcoded.md`, `error-gaps.md`, `complexity.md`, `query-smells.md`, `dead-code.md`, `naming.md`, `dep-hygiene.md`, `test-gaps.md`, `type-structs.md`.

### Step 4: Distill

Spawn a fresh sub-agent for distillation:

- **Model**: `sonnet`. A fresh agent prevents the synthesis from anchoring on whichever reviewer wrote first or loudest, and Sonnet handles the structured-merge job competently at lower cost.
- **Subagent type**: `Explore`. The agent reads files referenced by findings during validation; no other tool access needed.
- **Instructions**: contents of `distill.md` from this skill's directory.
- **Input**: the `## Findings Summary` table from each completed reviewer, prefixed with `### Reviewer: {name}`. Strip surrounding prose — tables only. Also include which reviewers ran, which were skipped, the dcat issues list (if any), and the focus area (if any).
- **Do not pass the codebase snapshot.** Distill works on structured findings; the snapshot would inflate input by ~200K tokens for no gain (file references in findings already point at the code).

Return the agent's output to the user.

