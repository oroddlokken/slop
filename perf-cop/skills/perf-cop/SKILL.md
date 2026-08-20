---
name: perf-cop
description: "Performance sweep over a whole codebase. Use when asked what's slow, for a performance review, to optimize or speed something up, to hunt latency, memory growth, or find hot spots — and after a feature lands, to catch the cost it added. Spins up parallel agents (hot-loops, allocations, io-batching, blocking, startup, payloads, caching-wins, tail-latency), each of which must name the workload a finding costs, then distills findings into prioritized action points. For maintainability use codehealth, for SQL depth use dba."
argument-hint: "[area]"
disable-model-invocation: true
---

# Perf Cop

Launch parallel performance agents, each analyzing the codebase through a different cost lens, then distill all findings into unified, prioritized action points.

Every finding here has to earn its place by naming the workload it costs — see **The Measurement Rule** below. That is the difference between this skill and a micro-optimization checklist.

## Who Does What

- **Orchestrator** (you, the main Claude Code session): Runs Steps 1-4 — asks user questions, prescans the codebase, launches reviewer agents, distills findings.
- **Reviewer agents** (spawned subagents): Receive a read-only snapshot, analyze through one lens, return findings. They do not scan independently, modify code, run benchmarks, or interact with live systems.

## Rules

- **THE MEASUREMENT RULE — every finding must name the workload under which it matters.** Which code path, triggered how often, over what data size, with evidence from the snapshot: a loop over a collection read from I/O, a per-request entry point, a cron or hook cadence, a table the query touches. "This allocates a list" is not a finding. "This allocates one list per record inside the read loop that runs over every JSONL line in `~/.claude/projects`, called once per statusline render" is. A finding that cannot name a plausible hot path is reported at **Low**, never higher, and distill demotes any that slipped through. This rule exists to kill speculative micro-optimization noise, which is the failure mode of every performance review.
- **Static reading only, no measurement theater.** Nothing here runs a benchmark or a profiler. Say what the evidence supports — "N queries per request where N is the page size" — and never invent a number ("saves 40ms") that no measurement produced. If the snapshot contains real benchmark or profiling artifacts, cite them.
- **Ask the user for mode (Step 1) and launch strategy** (Sequential or 1+Rolling 5). Recommend Sequential — it spreads token spend across the run instead of bursting it. Both strategies run one agent alone first, so that agent writes the shared cache entry and every agent after it reads instead of writes. Never open with a simultaneous burst.
- **The orchestrator prescans the codebase once and passes the snapshot to all agents** — agents do NOT scan independently.
- **Agents inherit the default model and the default agent type.** Pass no model override and no `subagent_type`. Either one changes the system prompt or the tool definitions, which invalidates the shared cache entry — the next agent writes it from cold instead of reading it.
- **Run distillation after all agents complete.** Raw output is overwhelming without deduplication, demotion, and prioritization.

## Workflow

### Step 1: Choose Mode

Ask the user which mode they want:

- **Full** — Run all 8 reviewers, then distill (hot-loops, allocations, io-batching, blocking, startup, payloads, caching-wins, tail-latency).
- **Quick** — Run 3 high-yield reviewers (hot-loops, io-batching, blocking), then distill. These three cover where measured time usually goes: CPU in the loop, round trips across a boundary, and waiting. Faster.
- **Pick** — Let the user choose which reviewers to run.

### Severity Definitions (all reviewers)

- **Critical**: Unbounded growth or degradation that will take the system down — a memory leak, a collection that never evicts, O(n²) over an input with no ceiling on a hot path. The system does not get slower, it stops.
- **High**: Measurable user-facing latency or cost on a known hot path — a path the snapshot shows is entered per request, per record, or per render.
- **Medium**: Real cost on a warm path, or on a hot path only at plausible scale the codebase has not reached yet.
- **Low**: Speculative, cold-path, or micro-optimization — including any finding that cannot name the workload it costs.

Individual reviewers map their findings to these levels in their Severity Guide section. Reviewers may refine these levels for their domain — when the distill step resolves cross-reviewer conflicts, use these universal definitions as the baseline. During distillation, any reviewer-reported "Critical" that is not unbounded growth or outage-scale degradation is remapped to "High", and any finding with no named workload is remapped to "Low", before tier assignment. See distill.md for the full mapping algorithm.

Available reviewers:

| Reviewer | Lens |
|----------|------|
| hot-loops | Algorithmic cost in per-request/per-record code paths |
| allocations | Needless copies, string building in loops, unbounded collections |
| io-batching | Chatty I/O — per-item network/disk/DB calls that could batch |
| blocking | Sync calls on async paths, lock contention, serial work that could overlap |
| startup | Import-time work, eager loading, cold-start cost |
| payloads | Over-fetching, oversized responses, missing pagination or streaming |
| caching-wins | Hot recomputation that memoization would remove |
| tail-latency | The spread between median and p99 — per-caller size, miss paths, queueing |

Skip the question only when the user's invocation already named a mode (e.g. "run perf-cop quick" → Quick). A bare `/perf-cop` names none: ask and wait for the answer. Silence is not a mode choice — never fall back to Full without one.

### Scope Boundaries

**Against sibling skills.** `codehealth` owns the shape of the code, `perf-cop` owns its runtime cost:

- **codehealth's `query-smells` owns SQL shape and correctness** — injection, missing transactions, scattered queries, the structure of the N+1. This skill owns what those cost at runtime. An N+1 belongs to `io-batching` **here only as cost** (how many round trips, per what request, over what row count); its shape and its fix as a query belong to query-smells. For depth on the query itself, run `dba`.
- **codehealth's `caching` owns cache correctness** — key completeness, invalidation, cross-user leaks, unbounded cache growth as a *bug*. This skill's `caching-wins` owns the opposite question: work that is recomputed on a hot path with no cache at all. A correct cache that still misses a hot recomputation is a `caching-wins` finding.
- If a finding is really about maintainability, dead code, or naming, it is codehealth's. Do not report it here.

**Between reviewers in this skill:**

- **io-batching owns cross-boundary call volume** (network, disk, DB, subprocess, IPC — how many round trips). **hot-loops owns in-process CPU** (how much work per item, what complexity class). The same loop can produce one finding from each: hot-loops measures the arithmetic, io-batching counts the calls.
- **caching-wins defers to io-batching** when the right fix is batching rather than memoizing. Memoization helps when the same inputs recur; batching helps when different inputs are fetched one at a time. If it is the second, it is an io-batching finding.
- **startup owns anything that runs before the first request or first command** — import-time work, module-level initialization, eager loading, connection setup, cold-start cost. Every other reviewer owns steady state. A regex compiled at import is startup's; the same regex compiled inside a request handler is hot-loops'.
- **allocations owns memory volume and copies**; **payloads owns the size of data crossing a boundary** (rows fetched, bytes returned, pages not paginated). A copy of an over-fetched list is two findings only if both the fetch and the copy are separately fixable.
- **The other seven lenses cost the average call; tail-latency owns the spread around it.** `blocking` owns whether a wait exists and how the resource is sized — pool starvation, lock scope, missing timeouts. `tail-latency` owns what the distribution across that resource looks like under normal load: which callers sit at p99, and what the mean hides. One serialized path can produce a finding from each. A finding whose fix speeds up every request equally is not this lens's; hand it back to the lens that owns the work.

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

Drop or reweight reviewers whose target patterns aren't in the codebase. Note each change in the final output's "Reviewers run / skipped" line.

- **No async framework detected** (no `async def`/`await`, no asyncio/trio/tokio/goroutines, no promise-based runtime, no thread or process pool) → keep `blocking` but drop its async checks; instruct it to review lock contention and serial-work-that-could-overlap only. Note: "Ran blocking without async checks (no async framework detected)."
- **No network or API surface** (no HTTP server, no route handlers, no client library making outbound calls, no serialized response payloads) → drop `payloads`. Note: "Skipped payloads (no network/API surface)."
- **Short-lived CLI with no server mode** (entry points are one-shot commands, hooks, or scripts that exit) → **weight `startup` up, not down.** For a process that runs for 200 ms and exits, import-time work *is* the hot path, so startup findings there are High or Critical rather than Medium. Append to startup's per-agent half: "This codebase is a short-lived CLI. Startup cost is the dominant cost — a 300 ms import on a command that runs per shell prompt or per statusline render is a user-facing latency finding, not a cold-start footnote." Note: "Ran startup weighted up (short-lived CLI, no server mode)."
- **No SQL/ORM and no filesystem I/O in loops** → still run `io-batching`; network and subprocess calls remain in scope. Only drop it if the codebase makes no calls across any boundary at all.

### Step 1.75: Check for Existing Issue Tracker

Check if the project uses **dcat** — a local issue tracker (CLI tool). Try running `dcat list --agent-only` directly. If it succeeds, pass the issue list to each agent so they can skip already-tracked concerns. If it errors (dcat not installed, no `.dogcats/` directory), skip this step.

### Step 2: Determine Target

Ask the user (if not already clear):
- **Path**: Which directory to review (default: current working directory)
- **Focus** (optional): A specific area to concentrate on — e.g., `api`, `ingest`, `render`, `report`, `startup`, `database`. When set, agents spend ~3x more attention on this area.

### Error Handling

- If `git ls-files` fails (not a git repo, permissions), use the Glob tool (`**/*.{py,ts,...}` patterns) to enumerate files.
- If a reviewer's criteria file does not exist at the expected path, skip that reviewer and warn the user.
- If all agents return zero findings, output "No issues found" and skip the distill step.
- If some agents fail or timeout, distill with available results and note which reviewers were skipped.

### Step 2.4: Check Snapshot Cache

A prior run of this skill may have already produced a snapshot of this codebase. Reuse it before re-reading ~200K of files.

**Build the cache key**:
1. `git_rev` = output of `git rev-parse HEAD` (or `no-git` if not a git repo)
2. `dirty` = output of `git status --porcelain` (any uncommitted change → different state)
3. `path` = absolute target path
4. `langs` = sorted, comma-joined language list from Step 1.5
5. `skill` = `perf-cop`

Concatenate as `{skill}|{path}|{git_rev}|{dirty}|{langs}` and take the first 12 hex chars of `sha256(...)` as `{hash}`.

**Cache file**: `.claude-cache/perf-cop-snapshot-{hash}.md` (relative to target path).

**Check the cache**:
- If the file exists and was modified within the last hour, read it and use its contents as `{codebase_snapshot}`. Skip Step 2.5.
- Otherwise, proceed to Step 2.5. After building the snapshot there, write it to `.claude-cache/perf-cop-snapshot-{hash}.md`. Create `.claude-cache/` if missing, and add `.claude-cache/` to `.gitignore` if not already listed.

The 1-hour TTL is a staleness backstop, not a prompt-cache window: editing a file that is already dirty leaves `git status --porcelain` unchanged, so the key alone can go stale. The cache is per-skill by design — every meta-skill scans for different things, and this skill's snapshot carries entry points and cadence that codehealth's does not, so nothing here is reused by another skill.

### Step 2.5: Prescan the Codebase (orchestrator does this once)

Read `scan-steps.md` from this skill's directory and follow its scan procedure. The orchestrator (you) reads all files once, then builds a single `{codebase_snapshot}` block that gets passed to every agent. This avoids 7 agents each independently scanning the same files.

1. Replace `{languages}` and `{focus}` in `scan-steps.md`
2. Follow the scan procedure — read manifests, entry points, source files, schedulers, CI/CD, git log, etc.
3. Format all collected file contents into the snapshot format specified in `scan-steps.md`
4. Store the result as `{codebase_snapshot}` for use in Step 3

The snapshot's **Workload Map** section is what makes the Measurement Rule enforceable — without it, agents have no evidence for how often a path runs and every finding collapses to Low. Do not omit it.

### Step 3: Launch Agents

Use the agent template (`agent.md`). The template places shared content (codebase snapshot, languages, ground rules, the measurement rule, severity guide, output format) before the `---` divider to form a common prompt prefix for API caching.

**Spawn contract** — how you call the Agent tool, in every launch mode:

- **Never pass `name:`.** A named agent becomes an addressable mailbox teammate, not a subagent. The tool result is `Spawned successfully` plus an agent_id, the findings never come back, and `run_in_background: false` is ignored. `TaskList` and `TaskOutput` cannot see it either. Recovering costs a round of `SendMessage` to every agent asking it to resend.
- **Sequential passes `run_in_background: false`. 1+Rolling 5 passes `false` for the priming agent and `true` for every agent after it.** Sequential needs the report in the tool result to know the agent is done. The rolling window needs the call to return at once, so the window can stay full. The priming agent runs alone and in the foreground: a cache entry becomes readable only once the request that writes it starts streaming, so agents launched at the same moment all miss it and all pay to write it.
- **Where the report arrives follows that flag.** Foreground: the Agent tool's return value is the findings — read them out of the tool result, and do not wait for a message or an idle ping. Background: the tool result carries an agent id, and the completion notification carries the findings.
- **Never call `TaskOutput` on a subagent, and never Read its `.output` file.** That path is a symlink to the agent's full JSONL transcript and will overflow your context.
- **Every launched agent must have reported before you distill.** Once the queue is empty, wait out the notifications still outstanding.

**Launch strategy** — Ask the user:

- **Sequential** (default) — Launch agents one at a time, each after the previous completes. Spreads token spend across the run instead of bursting it against the 5-hour quota. Slowest.
- **1+Rolling 5** — Launch one reviewer alone with `run_in_background: false` and wait for its report. That agent pays the cold write for the system prompt and tool definitions; every agent after it reads that entry. Then keep five agents in flight from the second launch to the last: spawn five with `run_in_background: true`, and spawn the next unlaunched reviewer the moment any completion notification arrives, until the queue is empty. Never let a sixth run: Anthropic rate-limits large simultaneous bursts, and a 429 mid-run wastes the work of every agent that already finished. Refilling per completion is what beats waves of five — a wave leaves each finished slot idle until its slowest agent returns. Keep the window full for the cache as well as the clock: a read refreshes the entry's five-minute life, so a gap longer than that sends the next agent back to a cold write. Same cost as Sequential, fastest.

Skip the question only when the user's invocation already named a strategy; otherwise ask and wait for the answer, recommending **Sequential**.

**Prompt caching** — The system prompt and tool definitions are the only part agents share; everything else each agent creates fresh, including a byte-identical snapshot, once per agent. Measured over a 16-agent run (2026-08-04): ~7K tokens read back per agent against an 11K-token snapshot written per agent. A 5-agent run (2026-08-10) shows what launch order does to that shareable part: the first agent read 0 and wrote 16,713 tokens, each later agent read 5,994 and wrote ~10.9K. Launch one agent alone and the 5,994 is read four times; open with five at once and it is written five times, at the 1.25× write rate.

The cause is breakpoint placement. Caching matches a byte prefix ending at a `cache_control` breakpoint, and the harness sets one after the system prompt and one at the end of each message. The Agent tool takes a single prompt string, so the shared snapshot and the per-agent assignment land inside the same cached unit and can never match across agents. Sharing would require the shared half in its own content block with a breakpoint at that boundary; the Agent tool exposes no way to ask for one.

- **The `---` divider is a section divider, not a cache boundary.** Shared placeholders (`{codebase_snapshot}`, `{path}`, `{languages}`, `{focus}`, `{known_issues}`) still resolve once and stay identical across agents, and per-agent placeholders still go below the line — that keeps the template readable and the resolve step cheap. No cost depends on it.
- **Snapshot size is the bigger lever.** Each agent writes the whole snapshot to cache once at 1.25× input price. An 11K-token snapshot across 7 agents is ~77K write-priced tokens every run. Trimming the snapshot saves more than launch order does, and both are worth taking.

**Build the shared prefix once:**
1. Read `agent.md` from this skill's directory
2. Replace `{path}` with the target path
3. Replace `{codebase_snapshot}` with the snapshot from Step 2.5
4. Replace `{languages}` with the confirmed language list (e.g., `Python, Shell, SQL, YAML`)
5. If the user specified a focus area, replace `{focus}` with the focus block below. Otherwise replace with an empty string.
6. If dcat issues were found, replace `{known_issues}` with a `## Known Issues (skip these)` section listing them. Otherwise replace with an empty string.
7. Store this as the **resolved template** — the content above `---` is now fixed and identical for all agents.

**For each reviewer, resolve per-agent content:**
1. In the resolved template, replace `{reviewer}` with the reviewer name (e.g., `hot-loops`)
2. Read `reviewers/{reviewer}.md`. If the file does not exist, skip that reviewer and warn the user. Replace `{reviewer_criteria}` with the file contents.
3. For overlapping reviewers (see Scope Boundaries), append the relevant scope boundary rule from the Scope Boundaries section **after** `{reviewer_criteria}` (below `---`).
4. Append any Step 1.6 reweighting note for this reviewer (the short-lived-CLI instruction for `startup`, the async-checks drop for `blocking`) below `---` as well.
5. Pass the result as the agent prompt

**Focus block** (inserted when focus is set):
```
## Focus Area: {area}

Concentrate your analysis primarily on **{area}**. During the scan, go deeper on {area}-related aspects (read more files, check more patterns). In your findings, {area}-related issues should be thoroughly covered — don't just flag them, name the workload and explain the specific cost.

Other issues are still worth mentioning but give {area} roughly 3x the attention and depth.
```

**Reviewer criteria files** are in this skill's `reviewers/` directory: `hot-loops.md`, `allocations.md`, `io-batching.md`, `blocking.md`, `startup.md`, `payloads.md`, `caching-wins.md`, `tail-latency.md`.

### Amending the Brief Mid-Run

The resolved template is **frozen once the first agent launches** — do not edit it, and do not edit the snapshot file it was built from. Agents that already ran cannot see the change, so editing mid-run leaves two populations of findings built on different facts, with nothing recording which is which.

When you find the brief is wrong mid-run — a prescan claim an agent contradicts, a mis-stated cadence, an entry point that is not actually reachable, a file that does not exist — record the correction instead of applying it:

1. **Append to an errata list** for this run. One entry per correction: what the brief claimed, what is actually true, and a `file:line` citation for the correction.
2. **Append the errata to the per-agent half** (below `---`) of every agent launched from then on, under a `## Errata` heading introduced by: "The brief contains errors. The entries below are authoritative wherever they contradict it."
3. **Pass the errata to distill**, noting which agents ran before each entry was added. Distill drops or annotates any earlier finding that rests on a corrected claim.

Cadence corrections matter more here than anywhere else: a finding's severity is built on how often its path runs, so an erratum that changes "per request" to "once at deploy" invalidates the severity of every finding that cited it. Distill demotes rather than drops those — the code is still as described, only the workload claim was wrong.

Agents surface corrections too — a lens that checks a prescan claim and finds it false. Treat those the same way: add an entry, and it binds every agent launched after it.

### Step 4: Distill

Spawn a fresh sub-agent for distillation:

- **Model**: `sonnet`. A fresh agent prevents the synthesis from anchoring on whichever reviewer wrote first or loudest, and Sonnet handles the structured-merge job competently at lower cost.
- **Subagent type**: `Explore`. The agent reads files referenced by findings during validation; no other tool access needed.
- **Instructions**: contents of `distill.md` from this skill's directory.
- **Input**: the `## Findings Summary` table from each completed reviewer, prefixed with `### Reviewer: {name}`. Strip surrounding prose — tables only. Also include which reviewers ran, which were skipped or reweighted, the dcat issues list (if any), and the focus area (if any).
- **Do not pass the codebase snapshot.** Distill works on structured findings; the snapshot would inflate input by ~200K tokens for no gain (file references in findings already point at the code). Distill validates a workload claim by reading the cited file, not by re-reading the snapshot.

Paste the distill agent's output into your own reply, verbatim and in full.

Only your reply is rendered to the user — the agent's report is not. Never point at it with "the findings are above", "see the report", or similar. Length is not a reason to summarize instead: if the list is long, your reply is long.
