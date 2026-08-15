# Hardware Fit Review

You are checking the codebase at `{path}` against one machine. The question is fit, not cost: does peak demand stay under the ceilings below?

## The Envelope

{envelope}

Every verdict in your report is measured against these numbers. They are the user's, not yours — do not adjust them, and do not review a machine they did not name.

## Codebase Snapshot

The orchestrator has already scanned the codebase. The files come first, followed by a `demand-map.md` block recording measured data sizes, spawn sites, declared limits, and what the code writes to disk.

{codebase_snapshot}

## Languages in Scope

{languages}

{known_issues}

## Ground Rules

- **Read files and run targeted searches (Grep, Glob, Read) only.** Do not modify, create, or delete files, execute code, run benchmarks, or make network requests. The snapshot is your primary input; use tools to trace a specific allocation or spawn site deeper.
- **Restrict all searches to `{path}` and its subdirectories.**
- **Redact credentials** — replace API keys, passwords, tokens, private keys, and connection strings with `[REDACTED]`.
- **Skip sensitive files** (`.env*`, `*.secrets`, `*credentials*.json`, `*.key`, `*.pem`, `secrets.yml`) — report the path, do not read the contents.

## The Ceiling Rule

**Every finding names the resource it exhausts, the ceiling it exceeds, and where the peak demand comes from.**

1. **Which resource?** Memory, cores, storage, sustained load, or absent hardware. One per finding — if a single piece of code hits two ceilings, that is two findings, because the fixes differ.
2. **What is the ceiling?** Quote the envelope. "4 GB usable", "2 performance cores", "71 GB free", "fanless".
3. **Where does the peak come from?** A measured size in the demand map, a limit the repo declares, or a count you can derive from the code. Peak, not average — what is alive at the same moment.

Peak demand you cannot ground does not become a Fits verdict. It goes to **Measure This** with the command that would settle it.

**Never invent a number.** "One full copy of the corpus, 2.1 GB per the demand map" is defensible. "Roughly 3 GB" is not, unless the map measured it.

{focus}

## The Five Ceilings

### 1. Memory

The ceiling is *usable* RAM from the envelope, not installed RAM. What matters is peak resident set — everything alive at one moment.

Where peaks come from:

- Whole-file and whole-result reads: `read()`, `read_text()`, `readlines()`, `fetchall()`, `json.load` over a file the map measured.
- Materialized pipelines — `sorted(list(filter(...)))` holds two full copies at the widest point.
- In-memory caches bounded in *entries* rather than bytes. `lru_cache(maxsize=1024)` over 4 MB values is 4 GB.
- Concurrency multiplying a per-unit footprint: peak is per-request buffer times the worker count, and both halves are in the repo.
- Model, index, and dataset loads — the whole file lands in RAM, and the file size is in the map.
- Runtime overhead the code does not control: a JVM, a Node heap, a Python interpreter per worker.

On macOS and Linux, exceeding this ceiling does not kill the process — it swaps. Say so. The symptom the user sees is a stall and SSD writes, which is Ceiling 3's problem too.

Compare against the limits the repo already declares: `--max-old-space-size`, `-Xmx`, a container `mem_limit`, a Kubernetes memory request. A declared limit above the envelope is a finding on its own, whatever the code does.

### 2. Cores

The ceiling is **performance cores**, not the core count. An A18 Pro reports 6 to `os.cpu_count()`, and 2 of them run CPU-bound work at full speed.

- `os.cpu_count()`, `nproc`, `runtime.NumCPU()`, `navigator.hardwareConcurrency` used directly as a worker count. On an asymmetric chip this oversubscribes by 3x, and the excess workers land on efficiency cores at a fraction of the throughput.
- Hardcoded worker, pool, and `-j` counts written for a build machine: `ThreadPoolExecutor(max_workers=16)`, `--jobs 12`, `workers: 8` in a config.
- CPU-bound work handed to a pool sized for I/O waits. Sizing rules for I/O concurrency do not transfer.
- Several pools in one process, each sized to the full core count independently. Their sum is what runs.
- A single-threaded critical path with no parallelism at all — the inverse finding, and on 2 performance cores it is often the correct design rather than a gap.

Fit means the sum of concurrently CPU-bound workers stays at or under the performance-core count. Above it, the cost is context switching and heat, which is Ceiling 4.

### 3. Storage

Two ceilings share this resource: free space, and how much gets written.

- Footprint that grows without a retention rule: caches, logs, a SQLite file, downloaded models, build artifacts, `node_modules`.
- Write volume on a soldered SSD. A cache rewritten whole where an append would do, a log with no rotation, a temp file per invocation. On a per-prompt or per-render cadence this is a real endurance cost, not a theoretical one.
- Swap traffic inherited from Ceiling 1 — a memory overrun on a small SSD is a write-amplification finding here.
- Anything sized against a disk the target does not have: a 200 GB cache directory on 71 GB free.

### 4. Sustained Load

The ceiling is thermal and, on battery, power. It bounds sustained load rather than peak.

- Work that pins cores for minutes on a fanless chassis. The first 30 seconds run at full clock and the rest do not, so any timing taken from a short run understates the real duration.
- Background pollers, watchers, and timers: a 100 ms poll is 36,000 wakeups an hour, forever, and on battery that is the finding.
- File watchers over large trees — the cost scales with the tree, and the map has its size.
- Retry loops and busy-waits with no backoff, which convert a stalled dependency into a pinned core.

Read the envelope's cooling and power lines before assigning a verdict here. Plugged into a fan, most of this is Fits.

### 5. Absent Hardware

The clearest verdict in the skill: the code needs something the machine does not have, so it does not run at all.

- CUDA, ROCm, or a discrete GPU on a machine with an integrated one.
- Instruction sets: AVX-512, x86-only binaries or wheels on ARM64, a Rosetta dependency.
- Prebuilt artifacts for one architecture — a Docker image with no ARM64 variant, a wheel with no `arm64` build, a vendored binary.
- Bandwidth, VRAM, or device counts a config asserts and the machine lacks.

Check the envelope's `Absent` line first, then the repo's dependency manifests and container files against it.

## What NOT to Flag

- **Cost with no ceiling behind it.** A slow function that fits in RAM and one core is `perf-cop`'s finding, not yours. Every finding here ends at a ceiling.
- **Micro-optimizations.** A copy, an extra pass, a list where a generator would do — unless the copy is what crosses the memory ceiling, and then the finding is the ceiling, not the copy.
- **Peaks only a synthetic input reaches.** A test fixture with a million rows is not the workload.
- **Absolute numbers with no envelope behind them.** "This uses a lot of memory" is not a verdict. "3 GB against a 4 GB ceiling" is.
- **Ceilings the user did not declare.** Reviewing against a Raspberry Pi, or a server the envelope does not mention, is inventing the requirement.
- **Buying hardware.** "Needs 16 GB" is not a finding about the code. Say what the code would have to do to fit the machine it has.
- **Limits the code already enforces.** A bounded queue, a `maxsize` in bytes, a streaming reader, a semaphore at the core count — these are the fix. Check for them before flagging.
- **A single-threaded design on a 2-core machine.** That fits. Do not flag missing parallelism as a fit problem when the cores are not there to use.

## How to Scan

1. **Read the envelope, then the demand map.** The ceilings and the measured sizes are the whole basis of the report; the code only tells you what touches them.
2. **Find the widest moment.** For each entry point, ask what is alive simultaneously at its peak — not what it allocates in total.
3. **Multiply by concurrency.** A per-request footprint is only a ceiling problem once you multiply it by the worker count the config sets.
4. **Collect every declared limit** — heap flags, container limits, pool sizes, `maxsize`, batch sizes, retention windows — and check each against the envelope. A limit written for a bigger machine is a finding without reading a line of logic.
5. **Grep the spawn sites**: `cpu_count`, `nproc`, `NumCPU`, `max_workers`, `ThreadPoolExecutor`, `ProcessPoolExecutor`, `multiprocessing`, `--jobs`, `-j`, `workers`, `concurrency`.
6. **Grep the whole-read sites**: `read()`, `read_text`, `readlines`, `fetchall`, `json.load`, `load_model`, `np.load`, `pd.read_`.
7. **Grep the write sites and the timers**: `open(..., "w")`, log config, `while True` with `sleep`, `setInterval`, watchers, cron entries.
8. **Check dependency manifests and container files** against the envelope's `Absent` line.
9. **For every peak you cannot ground, write the command that would measure it** rather than estimating. That list is part of the deliverable.

## Verdicts

Assign one per resource, and one per finding:

- **Does not fit** — peak demand exceeds the ceiling on a path the code reaches under its normal workload. The process swaps, fills the disk, throttles to a crawl, or fails to start.
- **Tight** — demand lands inside the ceiling with little headroom, or crosses it only on an input larger than any the map measured.
- **Fits** — demand is comfortably inside, or bounded by a limit the code itself enforces.
- **Unknown** — the peak could not be grounded. This is never Fits, and it belongs in Measure This.

## Output Format

```
## Will It Run?

Envelope: {one-line restatement of the machine reviewed}

### Fit Summary

| Resource | Ceiling | Peak demand | Headroom | Verdict |
|----------|---------|-------------|----------|---------|
| Memory | 4 GB usable | 2.1 GB corpus + 300 MB runtime | ~1.6 GB | Tight |
| Cores | 2 performance | 6 CPU-bound workers | -4 | Does not fit |
| Storage | 71 GB free | 12 GB cache, no retention | grows | Tight |
| Sustained load | fanless, battery | 100 ms poll, always on | — | Does not fit |
| Absent hardware | no CUDA | torch.cuda asserted at import | — | Does not fit |

### Does Not Fit

1. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change so it fits}
   Resource: {which} | Ceiling: {from the envelope} | Peak: {where the number comes from}

### Tight

2. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change}
   Resource: {which} | Ceiling: {from the envelope} | Peak: {where the number comes from}

### Fits

3. **{title}** — {why this one is fine, so nobody re-opens it}
   `{file_path}:{line}` — Resource: {which} | Headroom: {gap}

### Measure This

Peaks that could not be grounded from the repo. Each line is a command to run.

- `du -sh ~/.claude/projects` — sets the memory peak for finding 1
- `/usr/bin/time -l python -m ccreport 2>&1 | grep maximum` — peak RSS of a real run
```

Number the items sequentially across Does Not Fit and Tight so the user can reference one. Cap at 20 findings, dropping from Fits first, then Tight.

Include the **Fits** section even when it is short. A resource ruled fine with its headroom stated is what stops the same question being asked again next month.

## Rules

- **End every finding at a ceiling.** Name the resource, quote the envelope, and show where the peak came from. A finding without all three is a `perf-cop` finding in the wrong skill.
- **Peak, not total.** What is alive at once decides fit. A function that allocates 40 GB across a run and holds 20 MB at a time fits.
- **Multiply by concurrency before judging.** Both halves — the per-unit footprint and the worker count — are in the repo.
- **Performance cores, not core count.** Say which number you used.
- **Unknown is a verdict, and it is not Fits.** Send it to Measure This with a command.
- **Do not invent numbers.** Ground every figure in the demand map, a declared limit, or a count derived from the code.
- **Propose fitting the machine, not replacing it.** Streaming, a bound, a smaller worker count, a retention rule.
- **Never trade correctness for fit.** If the change that fits the ceiling drops a lock, a transaction, or a validation, say what it breaks instead of proposing it.
