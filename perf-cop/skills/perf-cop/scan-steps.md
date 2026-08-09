## Prescan the Codebase (orchestrator step)

This file is executed by the **orchestrator** (the main Claude Code session), NOT by individual review agents. The orchestrator reads files once and passes the results to all agents as a snapshot. Your role is selection (which files to include), faithful reproduction (each file verbatim), and one piece of synthesis the agents cannot do for themselves: the **Workload Map**. The agents do the analysis.

The Workload Map is what makes this scan different from a code-quality scan. Every finding downstream has to name the workload it costs — which path, how often, over what data size — and the only evidence agents get is what you collect here.

### Scan Procedure

Read broadly — the goal is to capture enough code across all languages so agents can cost real paths without re-reading files:

1. Read manifest files (pyproject.toml, package.json, Cargo.toml, go.mod, *.csproj, etc.) to understand the stack, dependencies, and project structure
2. Read the README (first 80 lines) and any architecture/design docs
3. **Languages in scope:** {languages}. Review all of these — do not skip any.
4. Detect framework: Django, Flask, FastAPI, Express, Rails, Spring, etc.
5. Detect database: ORM config, migration files, raw SQL files, connection strings
6. **Enumerate entry points — every place execution begins.** This is the spine of the Workload Map:
   - CLI mains: `if __name__ == "__main__"`, `[project.scripts]` / `bin` entries in manifests, `argparse`/`click`/`cobra` command definitions
   - Request handlers: route decorators (`@app.get`, `@router.`, `app.use`), controller classes, gRPC service methods, GraphQL resolvers
   - Scheduled and event-driven work: cron entries, `crontab`, systemd timers, launchd plists, Celery beat schedules, GitHub Actions `schedule:`, queue consumers, webhooks
   - Hooks and shells-out: git hooks, Claude Code hooks and statusline commands, pre-commit config, editor integrations — anything invoked by another process on a cadence it controls
   - Long-running loops: `while True`, event loops, watchers, pollers
   For each, record **how often it runs**: per request, per record, per shell prompt, per statusline render, every N minutes, once at deploy. When the cadence is not in the repo (an external cron, a UI that polls), say so explicitly rather than guessing.
7. Read key source files **across all in-scope languages**. Distribute effort proportionally to file count but ensure every language gets meaningful coverage (at least 3–5 files each). For each language, read 10–15% of files or at least 5, whichever is greater. Prioritize by distance from an entry point: handlers and mains first, then what they call, then the leaf utilities those call. A leaf utility called from a per-request handler matters more than a large module nothing hot reaches.
8. **Find loops over collections that came from I/O.** These are the candidate hot spots — a loop over a hardcoded 3-element tuple is not, a loop over query results, `readlines()`, `glob()`, `os.walk()`, a paginated API response, or a parsed JSON array is. Note the nesting: a loop inside a loop over two I/O-sourced collections is the O(n·m) case agents need to see. Include those files whole.
9. **Collect dataset-size hints** — the evidence for "how big is n":
   - Table names and row-count expectations (schema comments, migrations, seed data, `LIMIT` clauses, pagination defaults)
   - File globs and directory walks — what tree is being walked, how many files it plausibly holds
   - Fan-out constants: batch sizes, page sizes, retry counts, worker counts, queue depths
   - Retention or windowing constants (how many days of data a query spans)
   - Any comment or doc stating a real magnitude ("~40K records", "one row per render")
10. **Capture concurrency primitives**: `async`/`await`, event loops, `asyncio.gather`, threads, `ThreadPoolExecutor`/`ProcessPoolExecutor`, goroutines and channels, locks (`Lock`, `RLock`, `Semaphore`, mutexes), `subprocess` calls, connection pools and their sizes, transaction scopes. Note which functions are async and which sync calls appear inside them.
11. **Capture caching and memoization already present**: `lru_cache`, `cached_property`, `cachetools`, Redis/Memcached clients, module-level dicts used as caches, HTTP `Cache-Control` headers, precomputed rollup tables. `caching-wins` needs to know what is already cached so it flags only what is not.
12. **Look for existing benchmarks and profiling artifacts** — these are the only real measurements in the run and they outrank every inference: `benchmarks/`, `bench/`, `*_bench.py`, `pytest-benchmark` config, `timeit` usage, `cProfile`/`py-spy`/`pprof` output, flamegraphs, timing logs, `time.perf_counter()` instrumentation, APM or OpenTelemetry spans, `EXPLAIN` output checked into the repo. Include them verbatim.
13. Check CI/CD: .github/workflows/, .gitlab-ci.yml, Jenkinsfile — note job durations, timeouts, and any performance gate
14. Git history snapshot: run `git log --oneline -20` — recent activity areas are where new cost was most likely added
15. Use these patterns to identify files worth including: nested `for`, `while True`, `.append(` inside a loop, `+=` on strings, `sleep(`, `requests.`/`httpx.`/`fetch(` inside a loop, `SELECT` inside a loop, `open(`/`read()` inside a loop, `json.loads` on large inputs, `sort(` inside a loop, `in` against a list rather than a set. The agents evaluate cost and severity.
16. Check for config management: config modules, settings files, feature flags. Note whether `.env` or secrets files exist, but do not read their contents.

{focus}

### Build the Snapshot

After reading, reproduce each selected file verbatim — full content, no elisions, no commentary, no headings outside `### file:` blocks. Then append the Workload Map. The result is what gets passed to agents via the `{codebase_snapshot}` placeholder.

Format each file as:

````
### file: <relative_path>
```<ext>
<full file contents>
```
````

Include:
- All manifest files read
- README excerpt
- All source files read, entry points first
- Scheduler/hook/cron definitions
- Benchmark and profiling artifacts
- CI/CD config files
- Git log output (as `### file: git-log.txt`)

Omit:
- Files matching `.env*`, `*.secrets`, `*credentials*.json`, `*.key`, `*.pem`, `secrets.yml` — list by name only
- Binary files — list by name only

### Append the Workload Map

After the file blocks, append one section in exactly this form. It is not a file block — agents cite it as `workload-map`.

````
### file: workload-map.md
```md
## Entry points and cadence
| Entry point | file:line | Invoked by | Cadence |
|-------------|-----------|------------|---------|
| statusline render | statusline_command.py:412 | Claude Code, per render | every prompt, ~1/s while typing |
| ccreport (bare) | ccreport.py:88 | user, manually | a few times a day |
| unknown | poller.py:20 | external cron (not in repo) | UNKNOWN — cadence not in repo |

## Data sources and size hints
| Source | Where read | Size evidence |
|--------|-----------|---------------|
| ~/.claude/projects/**/*.jsonl | reader.py:60 | glob over all sessions, grows without bound |
| ccreport_records | db.py:140 | one row per API call, retention 14 days in rollups |

## Concurrency
- Async framework: none / asyncio / trio / goroutines / threads
- Pools: <name, size, where configured>
- Locks: <name, what it guards, file:line>

## Existing caching
- <mechanism, what it caches, file:line>

## Existing measurements
- <benchmark or profile artifact, what it reports, file:line — or "none found">
```
````

Rules for the map:

- **Cite a file:line for every row.** A cadence with no citation is a guess, and agents will build severity on it.
- **Write `UNKNOWN` rather than estimating.** An external cron, a UI poll interval, a user's habit — if the repo does not state it, the map says so. Agents treat an UNKNOWN cadence as a Low-severity workload, which is the correct default.
- **Do not analyze.** The map records what runs and how often. Whether that is too slow is the agents' job.

**Snapshot size limit**: Run `wc -c` on the selected file list. If the total exceeds ~1,250,000 bytes (≈300K tokens of code), ask the user to narrow scope. Drop whole files (prefer files far from any entry point; keep everything an entry point reaches); never abridge individual files to fit, and never drop the Workload Map.
