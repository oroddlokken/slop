---
name: fuzz-my-stuff-up
description: "Adversarial code exploration. Spins up ~20 parallel agents — each trying to break the code from a different angle (empty inputs, unicode chaos, race conditions, injection, state machine abuse, etc.) — then distills all findings into prioritized action points."
args:
  - name: area
    description: The directory, feature, or component to fuzz (optional)
    required: false
user-invokable: true
---

# Fuzz My Stuff Up

Launch ~20 parallel adversarial agents, each trying to break the codebase from a different angle — like fuzzing but with reasoning. Each agent thinks like an attacker, a confused user, a hostile environment, or an edge-case machine. Then distill all findings into prioritized action points.

## Workflow

### Step 1: Choose Mode

Ask the user which mode they want:

- **Full** — Run all 20 fuzzers in parallel, then distill. Maximum chaos.
- **Quick** — Run 7 high-impact fuzzers (empty-inputs, type-confusion, injection, state-machine, malformed-input, api-abuse, adversarial-user), then distill. Faster.
- **Pick** — Let the user choose which fuzzers to run.

Available fuzzers:

| Fuzzer | Attack Angle |
|--------|-------------|
| empty-inputs | Empty strings, null, None, zero, empty arrays, missing keys |
| boundary-values | INT_MAX, INT_MIN, huge strings, negative numbers, off-by-one |
| type-confusion | Wrong types where duck typing or loose validation allows it |
| unicode-chaos | Emoji, RTL text, zero-width chars, combining marks, mojibake |
| concurrency | Race conditions, parallel calls, shared mutable state, TOCTOU |
| path-traversal | `../` escape, symlinks, special paths, null bytes in filenames |
| injection | SQL, command, template, header injection vectors |
| state-machine | Out-of-order operations, double-submit, re-entry, partial completion |
| resource-exhaustion | Huge payloads, deeply nested structures, quadratic blowup, infinite loops |
| time-travel | Timezone edge cases, DST transitions, leap seconds, clock skew, far-future dates |
| permission-escalation | Accessing resources across privilege boundaries, role bypass, IDOR |
| malformed-input | Invalid JSON, truncated data, wrong encoding, BOM, mixed line endings |
| network-failure | Timeout handling, partial responses, DNS failure, retry storms |
| config-chaos | Missing config keys, wrong types in config, env var conflicts, defaults |
| dependency-failure | External service down, wrong version responses, missing optional deps |
| locale-chaos | Different number formats, date formats, currency symbols, RTL layouts |
| filesystem-edge | Read-only fs, full disk, long paths, special chars in filenames, case sensitivity |
| api-abuse | Missing required fields, extra unknown fields, wrong HTTP methods, huge headers |
| upgrade-path | Data from old versions, schema drift, backwards compat gaps, migration holes |
| adversarial-user | Intentionally hostile inputs, CSRF scenarios, replay attacks, parameter tampering |

Default to **Full** if the user doesn't specify.

### Scope Boundaries

Some fuzzers examine similar code from different angles. When findings overlap:
- **path-traversal** owns escape sequences (`../`, null bytes, symlink abuse). **filesystem-edge** owns OS-level limits (long paths, case sensitivity, full disk, read-only fs). Both may flag the same file-handling code — path-traversal focuses on malicious paths, filesystem-edge on environmental constraints.
- **injection** owns attacker-crafted payloads (SQL, command, template injection). **malformed-input** owns accidentally broken data (truncated JSON, wrong encoding). If input is both malformed AND injectable, injection takes precedence.
- **empty-inputs** and **type-confusion** both probe validation gaps. empty-inputs focuses on absence (null, zero, empty), type-confusion focuses on wrong-type presence. If the same validation function is missing both checks, empty-inputs takes the finding.
- **api-abuse** owns HTTP/API-level issues (wrong methods, missing fields). **adversarial-user** owns cross-request attacks (CSRF, replay, parameter tampering). If a finding spans both, adversarial-user takes precedence.

### Step 2: Determine Target

Ask the user (if not already clear):
- **Path**: Which directory to fuzz (default: current working directory)
- **Focus** (optional): A specific feature, endpoint, or module to concentrate on — e.g., `auth`, `api`, `file-upload`, `payments`, `user-input`. When set, fuzzers spend ~3x more attention on this area.

### Step 3: Language Prescan

Detect which languages are in scope so agents fuzz all of them:

1. Run `git ls-files` in the target path (or cwd) and group files by extension
2. Map extensions to languages
3. Skip binary/asset files: `*.png`, `*.jpg`, `*.gif`, `*.svg`, `*.ico`, `*.woff*`, `*.ttf`, `*.lock`, `*.min.js`, `*.min.css`, and directories `node_modules/`, `vendor/`, `dist/`, `build/`
4. Present the detected languages to the user sorted by file count
5. Ask: "These the right languages? Any that need extra attention despite low file count?"
6. Pass the confirmed list to each agent

### Step 4: Check for Existing Issue Tracker

Check if the project uses **dcat**. Run `which dcat`. If the command succeeds AND a `.dogcats/` directory exists at the target path, run `dcat list --agent-only` to get tracked issues. Pass this list to each agent so they skip already-known problems. If either check fails, skip this step.

### Step 5: Launch Agents

Read `fuzzer-agent.md` from this skill's directory. For each selected fuzzer:

1. Replace `{fuzzer}` with the fuzzer name (e.g., `empty-inputs`)
2. Replace `{attack_angle}` with the attack angle description from the table above
3. Replace `{path}` with the target path
4. Replace `{languages}` with the confirmed language list
5. If the user specified a focus area, replace `{focus}` with the focus block below, replacing `{area}` within it with the user's specified area. If no focus was specified, replace `{focus}` with empty string.
6. If dcat issues were found, replace `{known_issues}` with a `## Known Issues (skip these)` section listing them. Otherwise replace with empty string.
7. Launch all agents in parallel using the Agent tool

**Focus block** (inserted when focus is set — replace `{area}` with the user's focus area):
```
## Focus Area: {area}

Concentrate your fuzzing primarily on **{area}**. Go deeper on {area}-related code paths (read more files, try more attack patterns). {area}-related findings should be thoroughly explored — trace how deep the vulnerability or gap goes.

Other areas are still worth probing but give {area} roughly 3x the attention.
```

**Launch all selected fuzzers in a single parallel batch.** Sequential launching wastes time and prevents detection of timing-related issues.

### Step 6: Distill

After all agents complete, read `distill.md` from this skill's directory and follow the distillation algorithm.

### Error Handling

- If `git ls-files` fails (not a git repo, permissions), fall back to `find {path} -type f` and filter by extension.
- If an agent returns zero findings, that is a valid result — note "{fuzzer}: no issues found" in the distill summary.
- If some agents fail or timeout, distill with available results and note which fuzzers were skipped.

## Rules

- **Launch all selected fuzzers in a single parallel batch.** Sequential launching prevents timeout-related race condition detection and wastes time.
- **Each agent discovers the codebase from scratch and probes for vulnerabilities independently.** Pre-scan context (languages, path, known issues) is passed to all agents, but agents do not share findings mid-run — shared vulnerability data biases results and hides attack surfaces.
- **Agents analyze code without modifying files.** This preserves codebase integrity and lets the user review findings before acting.
- **Run distillation only after all agents complete.** Distillation needs the full picture to deduplicate and prioritize accurately.
