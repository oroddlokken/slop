# Find Startup Cost

Scan the codebase for everything that runs before the first request is served or the first command does its work: import-time execution, module-level initialization, eager loading, and connection or client setup. You own **everything before steady state**. Once the process is serving, it belongs to the other lenses.

Two very different systems land in this lens, and the same finding gets a different severity in each:

- **Long-lived server or daemon** — startup is paid once per deploy or per scale-out. It matters for deploy speed, autoscaling responsiveness, serverless cold starts, and health-check timeouts.
- **Short-lived CLI, hook, or script** — the process starts, works, and exits. Import time *is* the latency the user feels, every single invocation. For a command invoked per shell prompt, per commit, or per statusline render, startup is the hot path and findings here are High or Critical, not footnotes.

Read the workload map's entry points before assigning any severity.

## What to Look For

### Work at import time

Anything at module scope that does more than define a name:

```python
# BAD: all of this runs on import, whether or not the caller needs it
import pandas as pd                       # heavy dependency, always paid
CONFIG = json.loads(Path("config.json").read_text())   # file I/O at import
RATES = fetch_exchange_rates()            # network call at import
MODEL = load_model("model.bin")           # 400MB read at import
DB = create_engine(DSN)                   # connection attempt at import
_CACHE = build_lookup_table()             # computation at import
```

Each is fine as a function called when needed, and expensive as a side effect of `import`. Network calls at import are the worst of the set: they make import failure depend on a remote service.

### Heavy imports on a cheap path

A CLI that prints `--help` in 900 ms because the top of the file imports `pandas`, `torch`, `boto3`, `requests`, or a web framework it needs only for one subcommand. The fix is a local import inside the function that needs it, or lazy module loading. This is the single highest-yield finding for short-lived commands.

Look also for transitive weight: a small local module whose own import pulls in the heavy one.

### Eager loading of what most invocations never touch

All plugins registered at boot when one is used; every route module imported to serve one endpoint; the full config schema validated when the command reads two keys; a whole dataset, index, or model loaded up front. Defer to first use.

### Connection and client setup before it is needed

Database engines, HTTP sessions, cloud SDK clients, and Redis connections created at import or at boot when the process may never use them — each costs a handshake, a DNS lookup, or credential resolution (cloud SDK credential chains are notoriously slow). Create them lazily, or explicitly at a lifecycle hook where the cost is accounted for.

### Blocking work in a startup hook

Sync I/O, schema checks, migrations, warmup queries, and cache priming in `on_startup`/`lifespan`/`main()` before the server binds. This delays readiness, can trip a health-check or deploy timeout, and in an autoscaling group it lengthens every scale-out. Note whether the work is required for correctness (a migration) or merely convenient (a warm cache) — the second can move to background.

### Repeated startup in a per-invocation process

A command re-doing setup that a longer-lived process would do once: re-reading and re-parsing the same config, recompiling the same regexes, re-opening the same database, re-resolving the same paths. In a hook that runs on every prompt, this is the whole runtime. Consider a persisted cache, a daemon, or simply less work.

### Side effects on import

Logging configuration, monkey patching, signal handlers, `atexit` registration, thread or task spawning, directory creation, and file writes at module scope. These cost time, and they make import order load-bearing — a maintainability problem `codehealth` owns and a startup cost you own.

## What NOT to Flag

- **The speculative version of this lens: import-time cost in a long-lived server that starts rarely.** A 200 ms import in a service that restarts on deploy is not worth a finding unless the map shows serverless cold starts, autoscaling, or a health-check timeout. Say the cadence, then decide.
- **Constant definitions and cheap module-level literals.** Dicts, tuples, dataclass definitions, enum classes, compiled regexes, and small precomputed tables at module scope are the correct place for that work. A compiled regex at import is a *fix*, not a finding.
- **Imports the module genuinely needs on every path.** Deferring an import that every code path uses buys nothing and costs clarity. Confirm the import is conditional in practice before proposing a lazy one.
- **Lazy-loading proposals with no measured weight.** "Consider deferring this import" for a small pure-Python module is noise. The finding needs a heavy dependency or real work behind it.
- **Migrations, schema checks, and warmups that must complete before serving.** Correctness first. Flag only if the work can genuinely move to background or to build time.
- **Test collection and fixture setup cost.** Slow tests are real, but not this skill's.
- **One-time build or deploy steps.** They run once and nobody waits at the keyboard.

## How to Scan

1. **Read the entry points from the workload map first.** Decide, before reading any code, whether this is a long-lived process or a per-invocation one. That decision sets every severity in your report.
2. **Read the top of every entry-point module** and everything it imports at module scope, one level down at least.
3. **Grep for module-scope execution**: assignments whose right side is a call, not a literal. `= json.load`, `= open(`, `= requests.`, `= create_engine`, `= boto3.client`, `= load(`, `= build(`, `= fetch`.
4. **List the heaviest third-party imports** — pandas, numpy, torch, scipy, boto3, requests, django, matplotlib, selenium — and for each, check which code path actually needs it and whether that path is common.
5. **Trace transitive import weight**: `from .utils import x` where `utils` imports the heavy library at its own module scope.
6. **Find startup hooks**: `on_startup`, `lifespan`, `@app.before_first_request`, `main()` prologue, `__init__.py` bodies, `AppConfig.ready`, `init()`.
7. **Check for a real measurement**: `python -X importtime` output, a startup benchmark, timing logs, a cold-start metric in the snapshot. If one exists, it outranks all inference — cite it.
8. **Count invocations from the map.** A 300 ms import at 1 invocation/day and at 1 invocation/prompt are different findings entirely.

## Report Findings

For each startup finding:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Kind** | Heavy import / Import-time I/O / Import-time computation / Eager load / Client setup / Blocking startup hook / Import side effect |
| **Workload** | Process kind (long-lived or per-invocation) + how often the process starts (cite the workload map) |
| **Cost** | What runs before first use, and what fraction of invocations need it |
| **Fix** | Concrete change — local import, lazy initializer, `functools.cache`d accessor, defer to first use, move to background or build time |

### Severity Guide

- **Critical**: Startup work that can fail or hang the process before it serves — a network call at import with no timeout, a startup hook that can exceed a health-check or deploy timeout, an unbounded eager load.
- **High**: In a per-invocation process, any substantial import or setup cost on a command that runs on a user-facing cadence (per prompt, per commit, per render). In a long-lived process, cold-start cost in a serverless or autoscaling deployment.
- **Medium**: Eager work most invocations do not need, in a process where the user does not directly wait for it; client and connection setup done up front in a long-lived service.
- **Low**: Small import-time work in a rarely started long-lived process, and anything whose weight or start cadence you could not establish.

**Weight up for short-lived processes.** If the workload map shows the entry points are one-shot commands or hooks, the ceiling is not Medium — a 400 ms import on a statusline command that renders on every prompt is a High, and the report should say so plainly.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Workload | Kind | Cost | Fix |
|---|----------|-----------|----------|------|------|-----|
| 1 | High | statusline_command.py:12 | per-invocation, ~1 render/s | Heavy import | pandas imported for one `--report` branch | Move the import inside that branch |

## Rules

- **Decide the process kind before the severity.** Same code, opposite verdict: import-time work is a footnote in a daemon and the entire latency budget in a per-prompt hook.
- **Name what fraction of invocations need the work.** "Imported always, used by one subcommand" is the finding; "imports pandas" is not.
- **A compiled regex or a literal table at module scope is correct.** Do not flag the fix as the bug.
- **Cite `-X importtime` or a startup benchmark when the snapshot has one** — it is a real measurement and it outranks your reading.
- **Never defer work a correctness invariant depends on.** A migration, a schema check, or a required credential load stays where it is.
- **Deferring an import is not free** — it moves the cost to first use, and inside a hot function that is worse. Say where the cost lands.
- **You own everything before first request or first command; the other lenses own steady state.** A regex compiled inside a request handler is `hot-loops`'; the same regex at import is yours, and it is fine.
