---
name: fuzz-my-stuff-up
description: "Adversarial exploration: roughly 20 agents each trying to break the code from a different angle. Use when asked to stress-test, harden, or attack a codebase; to find edge cases and crash inputs; to answer what breaks this; or after a feature works on the happy path and needs the unhappy ones. Angles include empty inputs, boundary values, type confusion, unicode chaos, concurrency, path traversal, injection, state-machine abuse, resource exhaustion, clock skew, malformed input, network failure, locale chaos, filesystem edges, API abuse, and upgrade paths. Distills findings into prioritized action points."
argument-hint: "[area]"
disable-model-invocation: true
---

# Fuzz My Stuff Up

Launch ~20 parallel adversarial agents, each trying to break the codebase from a different angle — like fuzzing but with reasoning. Each agent thinks like an attacker, a confused user, a hostile environment, or an edge-case machine. Then distill all findings into prioritized action points.

## Who Does What

- **Orchestrator** (you, the main Claude Code session): Runs Steps 1-6 — asks user questions, prescans the codebase, launches fuzzer agents, distills findings.
- **Fuzzer agents** (spawned subagents): Receive a read-only snapshot, attack from one angle, return findings. They do not scan independently, modify code, or interact with live systems.

## Rules

- **Ask the user for mode (Step 1) and launch strategy** (Sequential or Rolling 5). Recommend Sequential — it spreads token spend across the run instead of bursting it. Agents do not share prompt cache with each other, so launch order does not change cost.
- **The orchestrator prescans the codebase once and passes the snapshot to all agents** — agents do NOT scan independently.
- **Agents inherit the default model** — do not override with a specific model.
- **Agents analyze code without modifying files.** Users review findings before acting.
- **Run distillation only after all agents complete.** Distillation needs the full picture to deduplicate and prioritize.

## Workflow

### Step 1: Choose Mode

Ask the user which mode they want:

- **Full** — Run all 20 fuzzers, then distill (empty-inputs, boundary-values, type-confusion, unicode-chaos, concurrency, path-traversal, injection, state-machine, resource-exhaustion, time-travel, permission-escalation, malformed-input, network-failure, config-chaos, dependency-failure, locale-chaos, filesystem-edge, api-abuse, upgrade-path, adversarial-user). Maximum chaos.
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

Skip the question only when the user's invocation already named a mode (e.g. "run fuzz-my-stuff-up quick" → Quick). A bare `/fuzz-my-stuff-up` names none: ask and wait for the answer. Silence is not a mode choice — never fall back to Full without one.

**Why fuzzers share one methodology:** Unlike the sibling review skills (dba, codehealth), which give each lens its own criteria file, the fuzzers intentionally share a single generic attack methodology defined in `fuzzer-agent.md` rather than per-fuzzer criteria files — fuzzing is open-ended, and a fixed checklist would narrow it. Each fuzzer differs only by its attack angle. Ground every finding in the actual snapshot code with a concrete, reproducible scenario — never a hypothetical.

### Severity Definitions (all fuzzers)

- **Critical**: Security vulnerability, data loss, or crash triggerable with user-supplied input
- **High**: Incorrect behavior, silent data corruption, or denial of service
- **Medium**: Edge case that produces wrong results or confusing errors
- **Low**: Unusual behavior that's unlikely but worth hardening against

Individual fuzzers report findings against these levels (see the severity guide in `fuzzer-agent.md`). When the distill step resolves cross-fuzzer conflicts, use these universal definitions as the baseline. During distillation, easy exploitability bumps a finding up one tier, and any fuzzer-reported "Critical" that requires implausible conditions or is already fully mitigated is remapped to "High" before tier assignment. See distill.md for the full mapping algorithm.

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

A prior run of this skill may have already produced a snapshot of this codebase. Reuse it before re-reading ~200K of files.

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

The 1-hour TTL is a staleness backstop, not a prompt-cache window: editing a file that is already dirty leaves `git status --porcelain` unchanged, so the key alone can go stale. The cache is per-skill by design — every meta-skill scans for different things, so nothing here is reused by another skill.

### Step 4.5: Prescan the Codebase (orchestrator does this once)

Read `scan-steps.md` from this skill's directory and follow its scan procedure. The orchestrator (you) reads the codebase once and builds a single `{codebase_snapshot}` block that gets passed to every agent. This avoids ~20 agents each independently scanning the same files.

1. Replace `{languages}` and `{focus}` in `scan-steps.md`
2. Follow the scan procedure — read manifests, source files, grep for risk patterns, git log
3. Format all collected file contents into the snapshot format specified in `scan-steps.md`
4. Store the result as `{codebase_snapshot}` for use in Step 5

### Step 5: Launch Agents

Use the agent template (`fuzzer-agent.md`). The template places shared content (codebase snapshot, languages, ground rules, output format) before the `---` divider to form a common prompt prefix for API caching.

**Spawn contract** — how you call the Agent tool, in every launch mode:

- **Never pass `name:`.** A named agent becomes an addressable mailbox teammate, not a subagent. The tool result is `Spawned successfully` plus an agent_id, the findings never come back, and `run_in_background: false` is ignored. `TaskList` and `TaskOutput` cannot see it either. Recovering costs a round of `SendMessage` to every agent asking it to resend.
- **Sequential passes `run_in_background: false`; Rolling 5 passes `run_in_background: true`.** Sequential needs the report in the tool result to know the agent is done. Rolling 5 needs the call to return at once, so the window can stay full.
- **Where the report arrives follows that flag.** Foreground: the Agent tool's return value is the findings — read them out of the tool result, and do not wait for a message or an idle ping. Background: the tool result carries an agent id, and the completion notification carries the findings.
- **Never call `TaskOutput` on a subagent, and never Read its `.output` file.** That path is a symlink to the agent's full JSONL transcript and will overflow your context.
- **Every launched agent must have reported before you distill.** Once the queue is empty, wait out the notifications still outstanding.

**Launch strategy** — Ask the user:

- **Sequential** (default) — Launch agents one at a time, each after the previous completes. Spreads token spend across the run instead of bursting it against the 5-hour quota. Slowest.
- **Rolling 5** — Keep five agents in flight from the first launch to the last. Spawn five with `run_in_background: true`, then spawn the next unlaunched reviewer the moment any completion notification arrives, until the queue is empty. Never let a sixth run: Anthropic rate-limits large simultaneous bursts, and a 429 mid-run wastes the work of every agent that already finished. Refilling per completion is what beats waves of five — a wave leaves each finished slot idle until its slowest agent returns. Same cost as Sequential, fastest.

Skip the question only when the user's invocation already named a strategy; otherwise ask and wait for the answer, recommending **Sequential**.

**Prompt caching** — Agents do not share cached prompt content with each other. Measured over a 16-agent run (2026-08-04): every agent read back the same ~7K tokens of system prompt and tool definitions, then created everything else fresh — including a byte-identical 11K-token snapshot, once per agent.

The cause is breakpoint placement. Caching matches a byte prefix ending at a `cache_control` breakpoint, and the harness sets one after the system prompt and one at the end of each message. The Agent tool takes a single prompt string, so the shared snapshot and the per-agent assignment land inside the same cached unit and can never match across agents. Sharing would require the shared half in its own content block with a breakpoint at that boundary; the Agent tool exposes no way to ask for one.

- **The `---` divider is a section divider, not a cache boundary.** Shared placeholders (`{codebase_snapshot}`, `{path}`, `{languages}`, `{focus}`, `{known_issues}`) still resolve once and stay identical across agents, and per-agent placeholders still go below the line — that keeps the template readable and the resolve step cheap. No cost depends on it.
- **Snapshot size is the lever that does matter.** Each agent writes the whole snapshot to cache once at 1.25× input price. An 11K-token snapshot across 16 agents is ~176K write-priced tokens every run. Trimming the snapshot saves money; launch order does not.

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

### Amending the Brief Mid-Run

The resolved template is **frozen once the first agent launches** — do not edit it, and do not edit the snapshot file it was built from. Agents that already ran cannot see the change, so editing mid-run leaves two populations of findings built on different facts, with nothing recording which is which.

When you find the brief is wrong mid-run — a prescan claim an agent contradicts, a mis-stated invariant, a file that does not exist — record the correction instead of applying it:

1. **Append to an errata list** for this run. One entry per correction: what the brief claimed, what is actually true, and a `file:line` citation for the correction.
2. **Append the errata to the per-agent half** (below `---`) of every agent launched from then on, under a `## Errata` heading introduced by: "The brief contains errors. The entries below are authoritative wherever they contradict it."
3. **Pass the errata to distill**, noting which agents ran before each entry was added. Distill drops or annotates any earlier finding that rests on a corrected claim.

Agents surface corrections too — a lens that checks a prescan claim and finds it false. Treat those the same way: add an entry, and it binds every agent launched after it.

### Step 6: Distill

Spawn a fresh sub-agent for distillation:

- **Model**: `sonnet`. A fresh agent prevents the synthesis from anchoring on whichever fuzzer wrote first or loudest, and Sonnet handles the structured-merge job competently at lower cost.
- **Subagent type**: `Explore`. The agent reads files referenced by findings during validation; no other tool access needed.
- **Instructions**: contents of `distill.md` from this skill's directory.
- **Input**: the `## Findings Summary` table from each completed fuzzer, prefixed with `### Fuzzer: {name}`. Strip surrounding prose — tables only. Also include which fuzzers ran, which were skipped, the dcat issues list (if any), and the focus area (if any).
- **Do not pass the codebase snapshot.** Distill works on structured findings; the snapshot would inflate input by ~200K tokens for no gain (file references in findings already point at the code).

Paste the distill agent's output into your own reply, verbatim and in full.

Only your reply is rendered to the user — the agent's report is not. Never point at it with "the findings are above", "see the report", or similar. Length is not a reason to summarize instead: if the list is long, your reply is long.

### Error Handling

- If `git ls-files` fails (not a git repo, permissions), use the Glob tool (`**/*.{py,ts,...}` patterns) to enumerate files.
- If an agent returns zero findings, that is a valid result — note "{fuzzer}: no issues found" in the distill summary.
- If some agents fail or timeout, distill with available results and note which fuzzers were skipped.

