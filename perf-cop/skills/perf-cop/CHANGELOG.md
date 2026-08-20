# Changelog

## 2026-08-19

- Added the `tail-latency` lens — the spread between median and p99, per-caller
  size, miss paths, queueing — taking the skill from seven reviewers to eight.
  The boundary against `blocking`: `blocking` owns whether a wait exists and how
  the resource is sized, `tail-latency` owns the distribution across it. A fix
  that speeds up every request equally belongs to neither.

## 2026-08-15

- Raised the report cap from 25 action points to 35, and added a `Below the cap`
  section — one line per theme with a count and one example path, omitted when
  nothing was dropped.

## 2026-08-10

- Replaced `1+Parallel` with `Rolling 5`, then with `1+Rolling 5`. The window
  refills on each completion notification instead of running waves, because a
  wave leaves every finished slot idle until its slowest agent returns; a sixth
  concurrent agent is never allowed, since a 429 mid-run wastes the work of
  every agent that already finished.
- Made the first agent run alone in the foreground. A cache entry becomes
  readable only once the request writing it starts streaming, so five agents
  launched together all miss it and all pay the 1.25× write. Agents now inherit
  the default model *and* the default agent type — either override changes the
  system prompt or the tool definitions and invalidates the shared entry.
- Replaced the "agents share nothing" measurement with numbers from a 5-agent
  run: first agent read 0 and wrote 16,713 tokens, each later agent read 5,994
  and wrote ~10.9K.
- Split the background-agent contract out: foreground agents return findings in
  the tool result, background agents return an id and deliver findings in the
  completion notification. Never call `TaskOutput` on a subagent and never read
  its `.output` file — that symlink is the full transcript.

## 2026-08-09

- Stopped defaulting to Full mode and Sequential when the user names neither.
  Silence is not a choice: the skill asks and waits unless the invocation
  already named a mode or strategy.
- Renamed `statusline-command.py` to `statusline_command.py` in the worked
  examples.
- Added the skill with seven lenses: `allocations`, `blocking`, `caching-wins`,
  `hot-loops`, `io-batching`, `payloads`, `startup`, plus `agent.md`,
  `distill.md` and `scan-steps.md`. Every finding must name the workload it
  costs.
