---
name: comment-cop
description: "Reviews what the comments and docs SAY, not what the code does. Use when asked to clean up comments, docstrings, or README prose; when a codebase feels buried under stale or self-indulgent explanation; when checking whether docstrings still match their signatures; or when hunting machine-written filler. Protects why-comments that carry a real gotcha and flags the rest. Spins up parallel agents (rambling, transient, contradicts-code, restates-code, missing-why, dead-comments, docstring-gaps, doc-drift, counting, settled-history, noise, llm-slop), then distills findings into prioritized action points. For user-facing strings use string-cop; for the logic itself use codehealth."
argument-hint: "[area]"
disable-model-invocation: true
---

# Comment Cop

Launch parallel reviewers, each analyzing the codebase's **comments, docstrings, and prose docs** through a different lens, then distill all findings into unified, prioritized action points.

This skill reviews the *documentation layer*, not the logic. It asks: does this comment earn its place? Does it tell the truth? Does it explain the non-obvious, or just narrate the obvious? A great codebase can still be buried under self-indulgent, rotting, or misleading prose — that is what Comment Cop hunts.

**The core judgment call:** a *why*-comment that carries a real fact (rationale, gotcha, ordering constraint, workaround) is worth its weight in gold and must be praised, not flagged. Self-indulgent narrative, transient anecdotes, machine-written filler, and restatements of the obvious are the targets. Reviewers must distinguish the two — flagging a good why-comment is a false positive and worse than missing a bad one.

## Who Does What

- **Orchestrator** (you, the main Claude Code session): Runs Steps 1-4 — asks user questions, prescans the codebase, launches reviewer agents, distills findings.
- **Reviewer agents** (spawned subagents): Receive a read-only snapshot, analyze the comments and docs through one lens, return findings. They do not scan independently, modify code, or interact with live systems.

## Rules

- **Ask the user for mode (Step 1) and launch strategy** (Sequential or 1+Rolling 5). Recommend Sequential — it spreads token spend across the run instead of bursting it. Both strategies run one agent alone first, so that agent writes the shared cache entry and every agent after it reads instead of writes. Never open with a simultaneous burst.
- **The orchestrator prescans the codebase once and passes the snapshot to all agents** — agents do NOT scan independently. The snapshot must reproduce files verbatim so comments survive intact.
- **Agents inherit the default model and the default agent type.** Pass no model override and no `subagent_type`. Either one changes the system prompt or the tool definitions, which invalidates the shared cache entry — the next agent writes it from cold instead of reading it.
- **Run distillation after all agents complete.** Raw output is overwhelming without deduplication and prioritization.
- **Never propose changes to the logic.** Every finding is about a comment, docstring, or doc — its accuracy, necessity, or clarity. If the code is wrong, that is out of scope (point the user at `/codehealth`).

## Workflow

### Step 1: Choose Mode

Ask the user which mode they want:

- **Full** — Run every reviewer, then distill (rambling, transient, contradicts-code, restates-code, missing-why, dead-comments, docstring-gaps, doc-drift, counting, settled-history, noise, llm-slop).
- **Quick** — Run the high-signal subset (contradicts-code, rambling, llm-slop, missing-why, dead-comments), then distill. Faster.
- **Pick** — Let the user choose which reviewers to run.

Skip the question only when the user's invocation already named a mode (e.g. "run comment-cop quick" → Quick). A bare `/comment-cop` names none: ask and wait for the answer. Silence is not a mode choice — never fall back to Full without one.

### Severity Definitions (all reviewers)

Comments rarely cause data loss directly, so severity is measured by **how badly the prose misleads or costs a maintainer**:

- **Critical**: A comment or doc that actively misdirects on a safety-critical property (thread-safety, locking, security, money handling, data integrity) such that trusting it causes a bug.
- **High**: A comment/docstring that contradicts the code, or a non-obvious hazard left unexplained — a maintainer will be misled or will reintroduce a bug. Also prose that only resolves through a system outside the repo (ticket ids carrying the rationale) once it spans more than a handful of files: the reader can never resolve it and the fix is a codebase-wide sweep.
- **Medium**: Rotting anecdotes, cross-layer redundancy, docstring gaps on public API, doc/README drift — real maintenance cost, no immediate trap.
- **Low**: Rambling prose, restatements of the obvious, decorative noise — clutter, fix-when-nearby.

Individual reviewers map their findings to these levels in their Severity Guide section. When the distill step resolves cross-reviewer conflicts, use these universal definitions as the baseline. During distillation, any reviewer-reported "Critical" that does not actively mislead on a safety-critical property is remapped to "High" before tier assignment. See distill.md for the full mapping algorithm.

Available reviewers:

| Reviewer | Lens |
|----------|------|
| rambling | Essay-length narrative, storytelling, over-explanation where a line would do |
| transient | Ticket/issue ids inlined in prose, live-instance anecdotes, dates, author names, "recently/new" notes that rot |
| contradicts-code | Comment/docstring that no longer matches the code — drifted or wrong from birth |
| restates-code | Comments that narrate what the code plainly says; docstrings echoing the signature |
| missing-why | Non-obvious code (magic numbers, workarounds, ordering constraints) with no rationale where one is warranted |
| dead-comments | Commented-out code, debug cruft, TODO/FIXME/XXX graveyards |
| docstring-gaps | Public API: missing docstrings, wrong/undocumented params, returns, raises; style violations |
| doc-drift | README / markdown / usage examples out of sync with actual signatures, flags, env vars |
| counting | Counts of a set the prose does not own, lead-ins numbering their own list, "step 5"-style positional references |
| settled-history | True prose about the past — removals, migrations, fixed hazards, rejected alternatives, edit annotations |
| noise | Banner comments, decorative dividers, redundant type restatements, section theater |
| llm-slop | Machine-written prose tics: "load-bearing", "robust", "simply", "it's not X — it's Y", em-dash spray, `# Load the config` narration |

### Scope Boundaries

Some reviewers examine the same comment from different angles. When findings overlap:
- **contradicts-code** owns all *in-source* comments and docstrings that disagree with code. **doc-drift** owns *external* prose (README, `.md`, docs sites). If a docstring is stale, contradicts-code owns it; if the README is stale, doc-drift owns it.
- **settled-history owns prose that is true and about the past; contradicts-code and doc-drift own prose that is false about the present.** "The old parser choked on tabs, so this pre-splits" is accurate and theirs to skip, settled-history's to cut. Where a removal note is also wrong — the thing came back, or never left — contradicts-code leads and settled-history rides along. **transient** owns a phrase that *will* rot ("recently", "for now", a live instance name); settled-history owns one that already has nothing to act on. **dead-comments** keeps commented-out code and TODO graveyards exclusively; a paragraph *about* deleted code is settled-history. **llm-slop** keeps `# Changed from X to Y` when the tell is the assistant's changelog voice; in the author's own voice it is settled-history. One action point either way.
- **counting owns count-shaped claims; doc-drift and contradicts-code own claims that are already false.** A doc promising "all 10 lenses" beside a directory of 11 trips both: doc-drift has the drift, counting has the number itself. Merge to one action point whose fix is the count-free rewrite, not the corrected number. A count that is still accurate today belongs to counting alone, in docs and in-source comments alike. Positional references ("step 5 of the protocol", "the second branch below") are counting's exclusively — no other lens flags them.
- **rambling** owns multi-sentence narrative regardless of content. **restates-code** owns short comments that mirror a single adjacent statement. A one-liner echoing the code → restates-code; a three-paragraph essay → rambling even if partly redundant.
- **transient** owns the rot-prone *specifics* (an instance name, a ticket id, a date). **rambling** owns the surrounding verbosity. In one bloated docstring, transient flags the anecdote, rambling flags the length — but coordinate so it is one action point in distill.
- **docstring-gaps** owns the *presence and structural quality* of API docstrings (missing, wrong params/returns/raises). **missing-why** owns inline rationale for non-obvious code that has no comment at all. A public function with no docstring → docstring-gaps; a magic constant with no explanation → missing-why.
- **noise** owns purely decorative/structural comments (banners, dividers, type restatements). **restates-code** owns prose that narrates logic. A `# ===== SECTION =====` divider → noise; a `# increment i` over `i += 1` → restates-code.
- **dead-comments** owns commented-out code and TODO/FIXME graveyards exclusively — no other reviewer flags these.
- **llm-slop ranks below contradicts-code and doc-drift.** Whether prose tells the truth matters more than whether it sounds machine-written, and the two are independent — a comment can be flawlessly written and false. When the same text trips both, the truth finding leads and the style note rides along. A style rewrite must never make an unverified claim more convincing.
- **llm-slop** owns *word choice and sentence shape*: the vocabulary tics, the antithesis flourish, em-dash density, and the specific assistant narration idioms (`# Load the config`, `Helper function that…`). **rambling** owns volume, **restates-code** owns redundancy, **noise** owns decoration. One narration comment in the assistant's idiom → llm-slop; a redundant one-liner in the author's own voice → restates-code. A three-paragraph docstring stuffed with "robust" and "seamless" → rambling flags the length, llm-slop flags the vocabulary; coordinate so distill emits one action point.

### Step 1.5: Language Prescan

Detect which languages are in scope so agents review comments across all of them, not just the largest.

1. Run `git ls-files` in the target path (or cwd) and group files by extension
2. Map extensions to languages (e.g., `.py` → Python, `.ts`/`.tsx` → TypeScript, `.go` → Go, `.sh` → Shell, `.sql` → SQL, `.md` → Markdown docs, etc.)
3. Skip files matching: `*.png`, `*.jpg`, `*.gif`, `*.svg`, `*.ico`, `*.woff*`, `*.ttf`, `*.lock`, `*.min.js`, `*.min.css`, `.gitignore`, `.gitattributes`, and directories `node_modules/`, `vendor/`, `dist/`, `build/`
4. Present the detected languages to the user sorted by file count, e.g.:
   ```
   Detected languages:
   - Python (42 files)
   - Markdown (9 files)
   - Shell (12 files)
   ```
5. Ask: "Are these the languages to review? (Remove or add any)"
6. After confirmation, pass the final language list to each agent via the `{languages}` placeholder

**Important:** Do not retain or pass the raw file list from `git ls-files` to agents. It is only used here to identify languages. Markdown counts as an in-scope language whenever `.md`/`.mdx`/`.rst` files exist, because the doc-drift lens needs them.

### Step 1.6: Auto-Skip Irrelevant Lenses

Drop reviewers whose target patterns aren't in the codebase. Note each drop in the final output's "Reviewers run / skipped" line.

- **No prose docs** (no `.md`, `.mdx`, `.rst`, or docstring-embedded usage examples, and no `README*`) → drop `doc-drift`. Note: "Skipped doc-drift (no markdown/README docs found)."
- **No public API surface** (only scripts / internal glue, no exported/public functions, classes, or package `__init__` exports) → keep `docstring-gaps` but tell it to focus on any documented function whose docs are wrong rather than demanding docs everywhere.

### Step 1.75: Check for Existing Issue Tracker

Check if the project uses **dcat** — a local issue tracker (CLI tool). Try running `dcat list --agent-only` directly. If it succeeds, pass the issue list to each agent so they can skip already-tracked concerns. If it errors (dcat not installed, no `.dogcats/` directory), skip this step.

### Step 2: Determine Target

Ask the user (if not already clear):
- **Path**: Which directory to review (default: current working directory)
- **Focus** (optional): A specific area to concentrate on — e.g., a module, `public API`, `README`. When set, agents spend ~3x more attention on this area.

### Error Handling

- If `git ls-files` fails (not a git repo, permissions), use the Glob tool (`**/*.{py,ts,md,...}` patterns) to enumerate files.
- If a reviewer's criteria file does not exist at the expected path, skip that reviewer and warn the user.
- If all agents return zero findings, output "No issues found" and skip the distill step.
- If some agents fail or timeout, distill with available results and note which reviewers were skipped.

### Step 2.4: Check Snapshot Cache

A prior run of this skill may have already produced a snapshot of this codebase. Reuse it before re-reading files.

**Build the cache key**:
1. `git_rev` = output of `git rev-parse HEAD` (or `no-git` if not a git repo)
2. `dirty` = output of `git status --porcelain` (any uncommitted change → different state)
3. `path` = absolute target path
4. `langs` = sorted, comma-joined language list from Step 1.5
5. `skill` = `comment-cop`

Concatenate as `{skill}|{path}|{git_rev}|{dirty}|{langs}` and take the first 12 hex chars of `sha256(...)` as `{hash}`.

**Cache file**: `.claude-cache/comment-cop-snapshot-{hash}.md` (relative to target path).

**Check the cache**:
- If the file exists and was modified within the last hour, read it and use its contents as `{codebase_snapshot}`. Skip Step 2.5.
- Otherwise, proceed to Step 2.5. After building the snapshot there, write it to `.claude-cache/comment-cop-snapshot-{hash}.md`. Create `.claude-cache/` if missing, and add `.claude-cache/` to `.gitignore` if not already listed.

**Note:** Comment Cop needs comments preserved verbatim. Do not reuse a snapshot produced by a skill that strips comments — the cache key includes `{skill}`, so a comment-cop snapshot is distinct from a codehealth one and they will not collide.

The 1-hour TTL is a staleness backstop, not a prompt-cache window: editing a file that is already dirty leaves `git status --porcelain` unchanged, so the key alone can go stale. The cache is per-skill by design — every meta-skill scans for different things, so nothing here is reused by another skill.

### Step 2.5: Prescan the Codebase (orchestrator does this once)

Read `scan-steps.md` from this skill's directory and follow its scan procedure. The orchestrator (you) reads all files once, then builds a single `{codebase_snapshot}` block that gets passed to every agent. This avoids every agent independently scanning the same files.

1. Replace `{languages}` and `{focus}` in `scan-steps.md`
2. Follow the scan procedure — read source files (comments intact), README, and markdown docs
3. Format all collected file contents into the snapshot format specified in `scan-steps.md`
4. Store the result as `{codebase_snapshot}` for use in Step 3

### Step 3: Launch Agents

Use the agent template (`agent.md`). The template places shared content (codebase snapshot, languages, ground rules, output format) before the `---` divider to form a common prompt prefix for API caching.

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
- **Snapshot size is the bigger lever.** Each agent writes the whole snapshot to cache once at 1.25× input price. An 11K-token snapshot across 16 agents is ~176K write-priced tokens every run. Trimming the snapshot saves more than launch order does, and both are worth taking.

**Build the shared prefix once:**
1. Read `agent.md` from this skill's directory
2. Replace `{path}` with the target path
3. Replace `{codebase_snapshot}` with the snapshot from Step 2.5
4. Replace `{languages}` with the confirmed language list (e.g., `Python, Markdown, Shell`)
5. If the user specified a focus area, replace `{focus}` with the focus block below. Otherwise replace with an empty string.
6. If dcat issues were found, replace `{known_issues}` with a `## Known Issues (skip these)` section listing them. Otherwise replace with an empty string.
7. Store this as the **resolved template** — the content above `---` is now fixed and identical for all agents.

**For each reviewer, resolve per-agent content:**
1. In the resolved template, replace `{reviewer}` with the reviewer name (e.g., `rambling`)
2. Read `reviewers/{reviewer}.md`. If the file does not exist, skip that reviewer and warn the user. Replace `{reviewer_criteria}` with the file contents.
3. For overlapping reviewers (see Scope Boundaries), append the relevant scope boundary rule from the Scope Boundaries section **after** `{reviewer_criteria}` (below `---`).
4. Pass the result as the agent prompt

**Focus block** (inserted when focus is set):
```
## Focus Area: {area}

Concentrate your analysis primarily on **{area}**. During the review, go deeper on {area}-related comments and docs (read more surrounding code to judge accuracy). In your findings, {area}-related issues should be thoroughly covered — don't just flag them, explain the specific cost to a maintainer.

Other issues are still worth mentioning but give {area} roughly 3x the attention and depth.
```

**Reviewer criteria files** are in this skill's `reviewers/` directory: `rambling.md`, `transient.md`, `contradicts-code.md`, `restates-code.md`, `missing-why.md`, `dead-comments.md`, `docstring-gaps.md`, `doc-drift.md`, `counting.md`, `settled-history.md`, `noise.md`, `llm-slop.md`.

### Amending the Brief Mid-Run

The resolved template is **frozen once the first agent launches** — do not edit it, and do not edit the snapshot file it was built from. Agents that already ran cannot see the change, so editing mid-run leaves two populations of findings built on different facts, with nothing recording which is which.

When you find the brief is wrong mid-run — a prescan claim an agent contradicts, a mis-stated invariant, a file that does not exist — record the correction instead of applying it:

1. **Append to an errata list** for this run. One entry per correction: what the brief claimed, what is true, and a `file:line` citation for the correction.
2. **Append the errata to the per-agent half** (below `---`) of every agent launched from then on, under a `## Errata` heading introduced by: "The brief contains errors. The entries below are authoritative wherever they contradict it."
3. **Pass the errata to distill**, noting which agents ran before each entry was added. Distill drops or annotates any earlier finding that rests on a corrected claim.

Agents surface corrections too — a lens that checks a prescan claim and finds it false. Treat those the same way: add an entry, and it binds every agent launched after it.

### Step 4: Distill

Spawn a fresh sub-agent for distillation:

- **Model**: `sonnet`. A fresh agent prevents the synthesis from anchoring on whichever reviewer wrote first or loudest, and Sonnet handles the structured-merge job competently at lower cost.
- **Subagent type**: `Explore`. The agent reads files referenced by findings during validation; no other tool access needed.
- **Instructions**: contents of `distill.md` from this skill's directory.
- **Input**: the `## Findings Summary` table from each completed reviewer, prefixed with `### Reviewer: {name}`. Strip surrounding prose — tables only. Also include which reviewers ran, which were skipped, the dcat issues list (if any), and the focus area (if any).
- **Do not pass the codebase snapshot.** Distill works on structured findings; the snapshot would inflate input for no gain (file references in findings already point at the code).

Paste the distill agent's output into your own reply, verbatim and in full.

Only your reply is rendered to the user — the agent's report is not. Never point at it with "the findings are above", "see the report", or similar. Length is not a reason to summarize instead: if the list is long, your reply is long.
