# Will It Run?

Checks a codebase against the machine it has to run on. You declare a hardware
envelope — usable RAM, cores and their class, free disk, cooling, and what the
silicon lacks — and one agent checks peak demand against each ceiling.

[perf-cop](../perf-cop) scores what a code path costs and never asks what
machine it lands on. This one asks only that: does peak demand stay under the
ceiling on 8 GB and two performance cores?

## What you get

A fit summary table, then findings grouped by verdict:

- **Does not fit** — demand exceeds the ceiling on a path the normal workload
  reaches. The process swaps, fills the disk, throttles, or fails to start.
- **Tight** — demand lands inside the ceiling with little headroom, or crosses
  it only on an input larger than any the scan measured.
- **Fits** — demand is comfortably inside, or bounded by a limit the code
  enforces itself.
- **Measure This** — peaks that could not be grounded in the repo, each as a
  command that settles it.

Every finding names the resource it exhausts, the ceiling it exceeds, and where
the peak comes from. An ungrounded guess never becomes a Fits verdict; it goes
to Measure This instead, because the user buys the machine on that answer.

The five ceilings are checked in one pass by one agent, since they trade
against each other: memory pressure becomes swap, swap becomes disk writes,
disk writes become heat, heat becomes throttling.

## Installation

Tell your agent to read this repository and ask it to help you integrate it
into your Claude Code setup as a skill.
