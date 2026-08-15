---
name: will-it-run
description: "Checks a codebase against the machine it has to run on. Declare a hardware envelope — RAM, cores and their class, storage, cooling, absent hardware — and a single agent checks peak demand against each ceiling: memory against usable RAM, worker counts against real performance cores, footprint and write volume against a small SSD, sustained load against a fanless chassis, CUDA and AVX against silicon that lacks them. The verdict is fits / tight / does not fit per resource. Use when asked whether something will run on a low-powered, small-memory, fanless, or shared machine. For where the time goes and what a path costs, use perf-cop."
argument-hint: "[area]"
disable-model-invocation: true
---

# Will It Run?

Launch one agent to check a codebase against a declared hardware envelope. The question is fit, not cost: does peak demand stay under the ceiling this machine has?

`perf-cop` scores every path as cadence times n and never asks what machine it lands on. This skill asks only that. Run `perf-cop` to find where the time goes; run this to find out whether the thing runs at all on 8 GB and two performance cores.

## Rules

- **The envelope is declared before the scan.** Every finding is measured against it — see The Ceiling Rule. Without one there is no ceiling, and this becomes a worse `perf-cop`.
- **The orchestrator prescans the codebase once and passes the snapshot to the agent.**
- **The agent inherits the default model.** Pass no model override and no `subagent_type`.
- **Single agent, single pass.** The four ceilings trade against each other: memory pressure becomes swap, swap becomes disk writes, disk writes become heat, heat becomes throttling. Per-resource agents each report a passing grade while the machine crawls.

## The Ceiling Rule

**Every finding names the resource it exhausts, the ceiling it exceeds, and where the peak demand comes from.**

```
WEAK:   "load_corpus() reads the whole file into memory — use a generator."
STRONG: "load_corpus() (reader.py:44) holds every parsed record at once. Peak is one
         full copy of ~/.claude/projects/**/*.jsonl, unbounded and 2.1 GB on this
         machine (demand-map: measured by du). Envelope: 8 GB total, ~4 GB usable
         with a browser and an editor open. Verdict: does not fit — macOS swaps
         rather than killing it, so the symptom is a stall plus SSD writes."
```

Peak demand you cannot ground goes to **Measure This**, never to Fits. An ungrounded guess that says "fits" is the one output of this skill that costs the user real money, because they buy the machine on it.

**Never invent a number.** No benchmark and no profiler runs here. Express demand in terms of the input — "one full copy of the corpus", "one buffer per concurrent request" — and where the input's size is not in the repo, name the command that measures it. The Measure This list is a deliverable, not an admission.

## Workflow

### Step 1: Declare the Envelope

Detect this machine first, then confirm it is the target — the code often has to run somewhere else.

macOS:
```
sysctl -n hw.memsize hw.ncpu hw.perflevel0.logicalcpu hw.perflevel1.logicalcpu machdep.cpu.brand_string
df -h /
```

Linux:
```
nproc; lscpu | grep -E 'Model name|^CPU\(s\)'; free -b; df -h /
```

Present what you found and ask the user for the four things detection cannot give:

1. **Is this the target machine?** If not, take the target's RAM, core count and core classes, free disk, and chip.
2. **What else runs on it?** A dedicated box gives nearly all its RAM to the process. A laptop shared with a browser and an editor gives roughly half. This number sets the memory ceiling and nothing else can supply it.
3. **Cooling** — fanless, fan, or a rack. Fanless caps sustained load, not peak.
4. **On battery, or plugged in?** Battery makes background wakeups a finding.

Record the result as `{envelope}`:

```
RAM: 8 GB total, ~4 GB usable (shared with browser + editor)
CPU: A18 Pro — 6 cores: 2 performance, 4 efficiency
Storage: 256 GB, 71 GB free
Cooling: fanless
Power: battery
Absent: no discrete GPU, no CUDA, ARM64 only
```

The `Absent` line is where GPU, instruction set, and architecture assumptions get caught, so fill it even when the answer is "nothing missing".

### Step 2: Determine Target

Ask the user, when it is not already clear:
- **Path**: which directory to review (default: current working directory)
- **Focus** (optional): one area to concentrate on — `ingest`, `render`, `build`, `workers`. When set, the agent gives it roughly 3x the attention.

### Step 3: Language Prescan

1. Run `git ls-files` in the target path and group files by extension
2. Map extensions to languages (`.py` → Python, `.ts`/`.tsx` → TypeScript, `.go` → Go, `.rs` → Rust, `.sh` → Shell, `.sql` → SQL, `.yml`/`.yaml` → YAML)
3. Skip `*.png`, `*.jpg`, `*.gif`, `*.svg`, `*.ico`, `*.woff*`, `*.ttf`, `*.lock`, `*.min.js`, `*.min.css`, and the directories `node_modules/`, `vendor/`, `dist/`, `build/`
4. Present the languages sorted by file count and ask: "Are these the languages to review?"
5. Pass the confirmed list to the agent via `{languages}`

Do not pass the `git ls-files` output to the agent. It identifies languages here and is then dropped.

### Step 4: Check for Existing Issue Tracker

Run `dcat list --agent-only`. If it succeeds, pass the issues to the agent so it skips what is already tracked. If it errors, skip this step.

### Step 5: Check Snapshot Cache

**Build the cache key**:
1. `git_rev` = `git rev-parse HEAD` (or `no-git`)
2. `dirty` = `git status --porcelain`
3. `path` = absolute target path
4. `langs` = sorted, comma-joined language list from Step 3
5. `envelope_hash` = first 8 hex chars of `sha256({envelope})`
6. `skill` = `will-it-run`

Concatenate as `{skill}|{path}|{git_rev}|{dirty}|{langs}|{envelope_hash}` and take the first 12 hex chars of `sha256(...)` as `{hash}`.

**Cache file**: `.claude-cache/will-it-run-snapshot-{hash}.md`, relative to the target path.

- If it exists and was modified within the last hour, read it and use it as `{codebase_snapshot}`. Skip Step 6.
- Otherwise build the snapshot in Step 6 and write it there. Create `.claude-cache/` if missing, and add `.claude-cache/` to `.gitignore` if it is not listed.

The envelope is in the key because the demand map records sizes measured on the machine being reviewed — a snapshot taken against a different target reports that machine's numbers. The 1-hour TTL is a staleness backstop: editing a file that is already dirty leaves `git status --porcelain` unchanged.

### Step 6: Prescan the Codebase

Read `scan-steps.md` from this skill's directory and follow it.

1. Replace `{languages}`, `{focus}` and `{envelope}` in `scan-steps.md`
2. Follow the scan procedure
3. Format the collected files into the snapshot format, then append the Demand Map
4. Store the result as `{codebase_snapshot}`

The Demand Map is what makes the Ceiling Rule enforceable: it carries the measured sizes of the data the code loads and the limits the repo already declares. Without it every finding lands in Measure This.

### Step 7: Launch the Agent

Read `agent.md` from this skill's directory and resolve its placeholders:

1. `{path}` → the target path
2. `{codebase_snapshot}` → the snapshot from Step 6
3. `{languages}` → the confirmed language list
4. `{envelope}` → the envelope from Step 1
5. `{focus}` → the focus block below when the user set one, otherwise an empty string
6. `{known_issues}` → a `## Known Issues (skip these)` section when dcat returned any, otherwise an empty string
7. Pass the result as the agent prompt, with `run_in_background: false` and **no `name:`**. A named agent becomes a mailbox teammate rather than a subagent: the tool result is `Spawned successfully` and the findings never come back.

**Focus block** (inserted when focus is set):
```
## Focus Area: {area}

Concentrate on **{area}**. Go deeper there — read more files, trace more allocations, check more spawn sites. Cover other areas, and give {area} roughly 3x the attention.
```

### Step 8: Report

Paste the agent's report into your own reply, verbatim and in full. Only your reply is rendered to the user, so never point at the agent's output with "see above". A long report makes a long reply.

Then ask whether to start on any item, and offer to run the Measure This commands.

### Error Handling

- `git ls-files` fails → enumerate with Glob (`**/*.{py,ts,go}`).
- Detection commands fail (unknown platform, no permission) → ask the user for the envelope outright. The scan does not proceed without one.
- The agent returns no findings → report "Fits on every ceiling", then the Measure This list, which is usually the real output in that case.
