# Perf Cop

Performance sweep over a whole codebase. Spins up parallel agents — each reviewing through a different cost lens — then distills all findings into prioritized action points.

The failure mode of every performance review is speculative micro-optimization: a wall of findings about list copies and string concatenation, none of which the program spends measurable time on. Perf Cop's answer is one rule.

## The Measurement Rule

Every finding must name the workload under which it matters — which code path, triggered how often, over what data size, with evidence from the snapshot.

> "This allocates a list" is not a finding.
>
> "This allocates one list per record inside the read loop that runs over every JSONL line in `~/.claude/projects`, called once per statusline render" is.

A finding that cannot name a plausible hot path is reported at **Low**, never higher, and the distill step demotes any that slipped through.

Nothing here runs a benchmark or a profiler — it is static reading. Reviewers say what the evidence supports ("N queries per request where N is the page size") and never invent a number ("saves 40ms") that no measurement produced.

## What you get

One agent per lens independently reviews the codebase. After all finish, findings are deduplicated and distilled into:

- **Fix Now** — unbounded growth, or measurable latency on a named hot path
- **Should Address** — real cost on a warm path, or a hot path at scale you haven't hit yet
- **Consider** — valid but non-urgent
- **Skipped Noise** — findings with no named workload (ignored)

Every action item includes a file path and line number.

## Lenses

| Lens | Focus |
|------|-------|
| hot-loops | Algorithmic cost in per-request/per-record code paths |
| allocations | Needless copies, string building in loops, unbounded collections |
| io-batching | Chatty I/O — per-item network/disk/DB calls that could batch |
| blocking | Sync calls on async paths, lock contention, serial work that could overlap |
| startup | Import-time work, eager loading, cold-start cost |
| payloads | Over-fetching, oversized responses, missing pagination or streaming |
| caching-wins | Hot recomputation that memoization would remove |

## Modes

| Mode | What runs |
|------|-----------|
| Full | Every lens |
| Quick | 3 high-yield lenses: hot-loops, io-batching, blocking — CPU in the loop, round trips across a boundary, and waiting |
| Pick | You choose which lenses to run |

Agents run sequentially by default — it spreads token spend across the run instead of bursting it. Either way one agent runs alone first: it writes the cache entry for the system prompt and tool definitions, and every agent after it reads that entry. The rolling window costs the same and finishes sooner.

## Against its siblings

[codehealth](../codehealth) owns the shape of the code, Perf Cop owns its runtime cost. An N+1 belongs here only as cost — how many round trips, per what request, over what row count; its shape and its fix as a query belong to codehealth's `query-smells`, and [dba](../dba) goes deeper. A cache with a broken key is codehealth's; a hot path with no cache at all is `caching-wins`.

## Installation

Tell your agent to read this repository and ask it to help you integrate it into your Claude Code setup as a skill.
