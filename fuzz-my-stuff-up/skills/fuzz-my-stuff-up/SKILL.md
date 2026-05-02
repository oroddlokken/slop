---
name: fuzz-my-stuff-up
description: "Adversarial code exploration. Launches ~20 agents — sequentially (default, cheapest) or in parallel — each trying to break the code from a different angle (empty inputs, unicode chaos, race conditions, injection, state machine abuse, etc.) — then distills all findings into prioritized action points."
args:
  - name: area
    description: The directory, feature, or component to fuzz (optional)
    required: false
user-invokable: true
---

# Fuzz My Stuff Up

Launch ~20 parallel adversarial agents, each trying to break the codebase from a different angle — like fuzzing but with reasoning. Each agent thinks like an attacker, a confused user, a hostile environment, or an edge-case machine. Then distill all findings into prioritized action points.

## Rules

- **Ask the user for launch strategy** (Sequential or 1+Parallel). Default to Sequential. Everything above `---` in the agent template is identical across agents and gets cached by the API after the first agent, reducing input cost by ~90%.
- **The orchestrator prescans the codebase once and passes the snapshot to all agents** — agents do NOT scan independently.
- **Agents inherit the default model** — do not override with a specific model.
- **Agents analyze code without modifying files.** Users review findings before acting.
- **Run distillation only after all agents complete.** Distillation needs the full picture to deduplicate and prioritize.
## Workflow

### Step 1: Choose Mode

Ask the user which mode they want:

- **Full** — Run all 20 fuzzers in parallel, then distill (empty-inputs, boundary-values, type-confusion, unicode-chaos, concurrency, path-traversal, injection, state-machine, resource-exhaustion, time-travel, permission-escalation, malformed-input, network-failure, config-chaos, dependency-failure, locale-chaos, filesystem-edge, api-abuse, upgrade-path, adversarial-user). Maximum chaos.
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

### Step 3.5: Auto-Skip Irrelevant Fuzzers

Drop fuzzers whose target patterns aren't in the codebase. Note each drop in the final output's "Fuzzers run / skipped" line.

- **No async/threading/concurrency primitives** (no `async`, `await`, `threading`, `goroutine`, `Mutex`, `Lock`, `multiprocessing`, `Promise.all`) → drop `concurrency`. Note: "Skipped concurrency (no concurrent code detected)."
- **No HTTP/network/external-service code** (no `requests`, `fetch`, `axios`, `http.Client`, `urllib`, `httpx`, no TCP socket usage) → drop `network-failure`. Note: "Skipped network-failure (no network code detected)."
- **No locale/i18n code** (no `gettext`, `i18n`, `Intl`, `locale.`, no timezone libraries) → drop `locale-chaos`. Note: "Skipped locale-chaos (no locale-aware code detected)."
- **No file I/O beyond simple read/write** (no path manipulation, no symlink handling, no `os.path.join` with user input, no file uploads) → drop `filesystem-edge` and `path-traversal`. Note: "Skipped filesystem-edge, path-traversal (no path-handling code detected)."
- **No SQL queries or string-building of queries** → drop `injection`. Note: "Skipped injection (no query construction detected)."
- **No timezone/datetime arithmetic** (no `tzinfo`, `pytz`, `moment-timezone`, `Date.toISOString` with offsets, no DST-aware code) → drop `time-travel`. Note: "Skipped time-travel (no timezone-aware code detected)."

### Step 4: Check for Existing Issue Tracker

Check if the project uses **dcat**. Try running `dcat list --agent-only` directly. If it succeeds, pass the issue list to each agent so they can skip already-tracked concerns. If it errors (dcat not installed, no `.dogcats/` directory), skip this step.
### Step 4.4: Check Snapshot Cache

A prior run of this or another meta-skill may have already produced a snapshot of this codebase. Reuse it before re-reading ~200K of files.

**Build the cache key**:
1. `git_rev` = output of `git rev-parse HEAD` (or `no-git` if not a git repo)
2. `dirty` = output of `git status --porcelain` (any uncommitted change → different state)
3. `path` = absolute target path
4. `langs` = sorted, comma-joined language list from Step 3
5. `skill` = `fuzz-my-stuff-up`

Concatenate as `{skill}|{path}|{git_rev}|{dirty}|{langs}` and take the first 12 hex chars of `sha256(...)` as `{hash}`.

**Cache file**: `.claude-cache/fuzz-my-stuff-up-snapshot-{hash}.md` (relative to target path).

**Check the cache**:
- If the file exists and was modified within the last hour, read it and use its contents as `{codebase_snapshot}`. Skip Step 4.5.
- Otherwise, proceed to Step 4.5. After building the snapshot there, write it to `.claude-cache/fuzz-my-stuff-up-snapshot-{hash}.md`. Create `.claude-cache/` if missing, and add `.claude-cache/` to `.gitignore` if not already listed.

The 1-hour TTL matches Anthropic's prompt-cache window — `/codehealth` followed by `/fuzz-my-stuff-up` 40 minutes later still hits both layers (this disk cache and the prompt cache when the next skill primes its first agent).

### Step 4.5: Prescan the Codebase (orchestrator does this once)

Read `scan-steps.md` from this skill's directory and follow its scan procedure. The orchestrator (you) reads the codebase once and builds a single `{codebase_snapshot}` block that gets passed to every agent. This avoids ~20 agents each independently scanning the same files.

1. Replace `{languages}` and `{focus}` in `scan-steps.md`
2. Follow the scan procedure — read manifests, source files, grep for risk patterns, git log
3. Format all collected file contents into the snapshot format specified in `scan-steps.md`
4. Store the result as `{codebase_snapshot}` for use in Step 5

### Step 5: Launch Agents

Use the agent template (`fuzzer-agent.md`). The template places shared content (codebase snapshot, languages, ground rules, output format) before the `---` divider to form a common prompt prefix for API caching.

**Launch strategy** — Ask the user:

- **Sequential** (default) — Launch agents one at a time, each after the previous completes. First agent primes the cache; every subsequent agent reads the shared prefix at ~90% cheaper input. Slowest, cheapest.
- **1+Parallel** — Launch one agent first to prime the cache, then launch remaining agents in parallel batches of at most 5. Anthropic rate-limits large simultaneous bursts, so batching past 5 triggers 429s mid-run and wastes the work of any agent that already completed. Nearly as cheap as Sequential, much faster.

If the user doesn't specify, use **Sequential**.

**Cache structure** — The `---` divider in fuzzer-agent.md is the cache boundary. Everything above it is the shared prefix (identical for all agents). Everything below is per-agent. API prompt caching matches byte-for-byte prefixes, so:
- Shared prefix placeholders (`{codebase_snapshot}`, `{path}`, `{languages}`, `{focus}`, `{known_issues}`) resolve to the **same value** for all agents. Resolve these once and reuse the identical string.
- Per-agent placeholders (`{fuzzer}`, `{attack_angle}`) differ per agent. These go below `---` and do not affect cache matching.
- **Never insert per-agent content above the `---` line.** This includes scope boundary rules — append those after per-agent content, not in the shared prefix.

**Build the shared prefix once:**
1. Read `fuzzer-agent.md` from this skill's directory
2. Replace `{path}` with the target path
3. Replace `{codebase_snapshot}` with the snapshot from Step 4.5
4. Replace `{languages}` with the confirmed language list
5. If the user specified a focus area, replace `{focus}` with the focus block below, replacing `{area}` within it with the user's specified area. Otherwise replace `{focus}` with an empty string.
6. If dcat issues were found, replace `{known_issues}` with a `## Known Issues (skip these)` section listing them. Otherwise replace with an empty string.
7. Store this as the **resolved template** — the content above `---` is now fixed and identical for all agents.

**For each fuzzer, resolve per-agent content:**
1. In the resolved template, replace `{fuzzer}` with the fuzzer name (e.g., `empty-inputs`)
2. Replace `{attack_angle}` with the attack angle description from the table above
3. For overlapping fuzzers (path-traversal/filesystem-edge, injection/malformed-input, empty-inputs/type-confusion, api-abuse/adversarial-user), append the relevant scope boundary rule from the Scope Boundaries section **after** the per-agent content (below `---`).
4. Pass the result as the agent prompt

**Focus block** (inserted when focus is set — replace `{area}` with the user's focus area):
```
## Focus Area: {area}

Concentrate your fuzzing primarily on **{area}**. Go deeper on {area}-related code paths (read more files, try more attack patterns). {area}-related findings should be thoroughly explored — trace how deep the vulnerability or gap goes.

Other areas are still worth probing but give {area} roughly 3x the attention.
```

### Step 6: Distill

Spawn a fresh sub-agent for distillation:

- **Model**: `sonnet`. A fresh agent prevents the synthesis from anchoring on whichever fuzzer wrote first or loudest, and Sonnet handles the structured-merge job competently at lower cost.
- **Subagent type**: `Explore`. The agent reads files referenced by findings during validation; no other tool access needed.
- **Instructions**: contents of `distill.md` from this skill's directory.
- **Input**: the `## Findings Summary` table from each completed fuzzer, prefixed with `### Fuzzer: {name}`. Strip surrounding prose — tables only. Also include which fuzzers ran, which were skipped, the dcat issues list (if any), and the focus area (if any).
- **Do not pass the codebase snapshot.** Distill works on structured findings; the snapshot would inflate input by ~200K tokens for no gain (file references in findings already point at the code).

Return the agent's output to the user.

### Error Handling

- If `git ls-files` fails (not a git repo, permissions), use the Glob tool (`**/*.{py,ts,...}` patterns) to enumerate files.
- If an agent returns zero findings, that is a valid result — note "{fuzzer}: no issues found" in the distill summary.
- If some agents fail or timeout, distill with available results and note which fuzzers were skipped.

