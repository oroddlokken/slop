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

## Workflow

### Step 1: Choose Mode

Ask the user which mode they want:

- **Full** — Run all 12 reviewers in parallel, then distill.
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

**Important:** Do not retain or pass the file list from `git ls-files` to agents. It is only used here to identify languages. Agents discover files independently during their scan.

### Step 1.75: Check for Existing Issue Tracker

Check if the project uses **dcat** — a local issue tracker (CLI tool). Run `which dcat`. If the command succeeds (exit code 0) AND a `.dogcats/` directory exists at the target path, run `dcat list --agent-only` to get tracked issues. Pass this issue list to each agent so they can skip concerns that are already tracked. If either check fails, skip this step.

### Step 2: Determine Target

Ask the user (if not already clear):
- **Path**: Which directory to review (default: current working directory)
- **Focus** (optional): A specific area to concentrate on — e.g., `api`, `models`, `auth`, `payments`, `database`, `tests`. When set, agents spend ~3x more attention on this area.

### Error Handling

- If `git ls-files` fails (not a git repo, permissions), fall back to `find {path} -type f` and filter by extension.
- If a reviewer's SKILL.md does not exist at the expected path, skip that reviewer and warn the user.
- If all agents return zero findings, output "No issues found" and skip the distill step.
- If some agents fail or timeout, distill with available results and note which reviewers were skipped.

### Step 2.5: Prescan the Codebase (orchestrator does this once)

Read `scan-steps.md` from this skill's directory and follow its scan procedure. The orchestrator (you) reads all files once, then builds a single `{codebase_snapshot}` block that gets passed to every agent. This avoids 12 agents each independently scanning the same files.

1. Replace `{languages}` and `{focus}` in `scan-steps.md`
2. Follow the scan procedure — read manifests, source files, CI/CD, git log, etc.
3. Format all collected file contents into the snapshot format specified in `scan-steps.md`
4. Store the result as `{codebase_snapshot}` for use in Step 3

### Step 3: Launch Agents

Use the agent template (`agent.md`). Launch agents using the Agent tool — all in parallel for Full mode.

**Placeholder resolution order:**
1. In `agent.md`: replace `{codebase_snapshot}` with the snapshot built in Step 2.5
2. In `agent.md`: replace `{reviewer}`, `{path}`, `{skill_path}`, `{languages}`, `{focus}`, `{known_issues}`

For each reviewer:
1. Read `agent.md` from this skill's directory
2. Replace `{reviewer}` with the reviewer name (e.g., `duplicates`)
3. Replace `{path}` with the target path
4. Replace `{skill_path}` with the absolute path `~/.claude/skills/{reviewer}/SKILL.md`. If the file does not exist, skip that reviewer and warn the user.
5. Replace `{codebase_snapshot}` with the snapshot from Step 2.5
6. Replace `{languages}` with the confirmed language list from the prescan (e.g., `Python, Shell, SQL, YAML`)
7. If the user specified a focus area, replace `{focus}` with the focus block below. If no focus was specified, replace `{focus}` with an empty string.
8. If dcat issues were found, replace `{known_issues}` with a `## Known Issues (skip these)` section listing them. Otherwise replace with an empty string.
9. For overlapping reviewers (duplicates, extract-logic, complexity, query-smells, dep-hygiene, dead-code), append the relevant scope boundary rule from the Scope Boundaries section to the agent prompt.
10. Pass the result as the agent prompt

**Focus block** (inserted when focus is set):
```
## Focus Area: {area}

Concentrate your analysis primarily on **{area}**. During the scan, go deeper on {area}-related aspects (read more files, check more patterns). In your findings, {area}-related issues should be thoroughly covered — don't just flag them, explain the specific impact.

Other issues are still worth mentioning but give {area} roughly 3x the attention and depth.
```

**Reviewer to skill path mapping:**

| Reviewer | Reads criteria from |
|----------|-------------------|
| duplicates | `skills/duplicates/SKILL.md` |
| extract-logic | `skills/extract-logic/SKILL.md` |
| simplify-code | `skills/simplify-code/SKILL.md` |
| hardcoded | `skills/hardcoded/SKILL.md` |
| error-gaps | `skills/error-gaps/SKILL.md` |
| complexity | `skills/complexity/SKILL.md` |
| query-smells | `skills/query-smells/SKILL.md` |
| dead-code | `skills/dead-code/SKILL.md` |
| naming | `skills/naming/SKILL.md` |
| dep-hygiene | `skills/dep-hygiene/SKILL.md` |
| test-gaps | `skills/test-gaps/SKILL.md` |
| type-structs | `skills/type-structs/SKILL.md` |

All paths resolve to `~/.claude/skills/{reviewer}/SKILL.md`.

### Step 4: Distill

After all agents complete, read `distill.md` from this skill's directory and follow the distillation algorithm.

## Rules

- In Full mode, run all 12 agents in parallel for maximum throughput.
- The orchestrator prescans the codebase once (Step 2.5) and passes the snapshot to all agents — agents do NOT scan independently.
- Agents inherit the default model — do not override with a specific model.
- Always run the distill step after all agents complete — raw agent output is overwhelming without deduplication and prioritization.
