## Prescan the Codebase (orchestrator step)

This file is the playbook for the **orchestrator** — the main Claude Code session running `/will-it-run` — not for the review agent. You read the files once, reproduce them verbatim, and add one thing the agent cannot get for itself: the **Demand Map**, which carries the measured sizes of the data the code loads and the resource limits the repo already declares.

The agent judges fit. You supply the numbers it judges against.

### The Envelope

{envelope}

Two parts of the scan depend on it. Measure the data directories the code reads, because their size sets the memory peak. Collect every declared limit, because a limit written for a bigger machine is a finding before anyone reads the logic.

### Iron Law: Files Go In Verbatim, Verdicts Stay Out

Every file is reproduced byte-for-byte: full content, original order, no elisions, no commentary, no headings other than the `### file:` marker and the Demand Map. A snapshot that has already labelled something as too big for the machine gets ratified rather than reviewed.

This blocks, by name:

- **Digests** like `(108 lines, full)` or `(key parts)` that strip bodies to signatures.
- **Inline commentary** inside file blocks: "(this loads everything)", "(won't fit)", "(hot path)".
- **Thematic headings** grouping files by resource.
- **`...` or `# rest unchanged`** anywhere inside a file block.

The Demand Map is the one exception, and it records measurements rather than conclusions. A row says how large a directory is; whether that fits is the agent's call.

### Scan Procedure

1. Read the manifest files: `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `requirements.txt`, `*.csproj`. Dependency weight and platform markers both matter here.
2. Read the README's first 80 lines and any deployment or architecture doc.
3. **Languages in scope**: {languages}. Cover each — at least 3-5 files per language, or 10-15% of its files, whichever is greater.
4. **Read every entry point** — `if __name__ == "__main__"`, `[project.scripts]`, `bin` entries, route handlers, queue consumers, hooks, statusline commands, `while True` loops. Each one is a peak to size.
5. **Read the files that allocate**: whole-file reads, `fetchall`, model and index loads, materialized pipelines, in-memory caches. Include them whole.
6. **Read the files that spawn**: thread and process pools, worker configs, `cpu_count` call sites, `-j` flags in build scripts and CI.
7. **Read the files that write**: log configuration, cache directories, SQLite and database files, temp-file creation, export paths.
8. **Read container and runtime configuration**: `Dockerfile`, `docker-compose.yml`, Kubernetes manifests, `Procfile`, systemd units, launchd plists. Heap flags and memory limits live here.
9. Run `git log --oneline -20` and capture the output verbatim.

**Measure the data the code reads.** For every directory, corpus, database file, or model path the code opens, run `du -sh` on it and record the result. This is the single most valuable thing in the snapshot: it turns "loads the corpus" into a number the agent can put against the memory ceiling. Where a path does not exist on this machine, record `not present on this machine` rather than a guess.

{focus}

### Snapshot Format

A flat sequence of `### file:` blocks, then the Demand Map. Nothing precedes the first block.

````
### file: <relative_path>
```<ext>
<full file contents>
```
````

For sensitive files (`.env*`, `*.secrets`, `*credentials*.json`, `*.key`, `*.pem`, `secrets.yml`) and binaries, include a stub in place of the contents:

````
### file: .env
```
[redacted: sensitive file]
```
````

### Append the Demand Map

After the file blocks, append one section in exactly this form. Agents cite it as `demand-map`.

````
### file: demand-map.md
```md
## Measured data sizes
| What | Path | Read at | Size |
|------|------|---------|------|
| session corpus | ~/.claude/projects | reader.py:60 | 2.1 GB, 14,880 files (du -sh) |
| rollup database | ~/.claude/ccreport.db | db.py:22 | 340 MB (du -sh) |
| model weights | models/base.bin | infer.py:18 | not present on this machine |

## Declared limits
| Limit | Value | Where |
|-------|-------|-------|
| worker pool | os.cpu_count() | ingest.py:41 |
| node heap | --max-old-space-size=8192 | package.json:12 |
| container memory | 16g | docker-compose.yml:9 |
| cache bound | lru_cache(maxsize=1024) | rates.py:8 |

## Spawn sites
| Site | Concurrency | file:line |
|------|-------------|-----------|
| ingest pool | cpu_count() processes | ingest.py:41 |
| render threads | 8, hardcoded | render.py:77 |

## What the process writes
| Target | Cadence | Retention | file:line |
|--------|---------|-----------|-----------|
| ~/.cache/ccreport | per run | none found | cache.py:30 |
| logs/run.log | per invocation | no rotation found | logging.py:14 |

## Long-running and periodic work
- <poller, watcher, timer — interval and file:line, or "none found">

## Platform requirements
- <CUDA, AVX, architecture-specific wheels or images, and where declared — or "none found">
```
````

Rules for the map:

- **Cite a file:line for every row.** The agent builds a verdict on it.
- **Measure rather than estimate.** `du -sh` output goes in as printed. Where you cannot measure, write `not measured` and the agent moves that finding to Measure This — which is the correct outcome, and better than a number nobody can defend.
- **Write `none found` rather than leaving a section empty.** An absent retention rule and an unread section look identical otherwise, and they mean opposite things.
- **Record, do not judge.** Whether 2.1 GB fits is the agent's call.

### Size Limit

Run `wc -c` on the selected file list. If the total exceeds ~1,250,000 bytes (≈300K tokens of code), ask the user to narrow the scope. Drop whole files — prefer ones far from any entry point, keep everything that allocates, spawns, or writes — and never drop the Demand Map.

### Final Check

Before handing the snapshot over:

- Scan for text outside a `### file:` block or the Demand Map. Remove it.
- Scan for `...`, "key parts", "(N lines, full)". Restore the full file or drop it.
- Scan for parenthetical commentary inside file blocks. Remove it.
- Confirm every `du -sh` you ran is in the map. A measurement taken and left out is the one thing the agent cannot recover.
