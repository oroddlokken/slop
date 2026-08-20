# Comment Cop

Comment & documentation quality review. Spins up parallel agents — each reviewing through a different lens — then distills all findings into prioritized action points.

This one reviews what the comments **say**, not what the code does. A codebase can be perfectly sound and still be buried under self-indulgent, rotting, or machine-written prose. That is what Comment Cop hunts.

The core judgment call: a *why*-comment carrying a real fact (rationale, gotcha, ordering constraint, workaround) is worth its weight in gold and gets praised, not flagged. Narrative, anecdotes, filler, and restatements of the obvious are the targets.

## What you get

One agent per lens independently reviews the codebase's comments, docstrings and prose docs. After all finish, findings are deduplicated and distilled into:

- **Fix Now** — comments that actively mislead
- **Should Address** — rot, gaps, and prose that costs more than it gives
- **Consider** — valid but non-urgent cleanups
- **Skipped Noise** — subjective or trivial findings (ignored)

Every action item includes a file path and line number.

## Lenses

| Lens | Focus |
|------|-------|
| contradicts-code | Comments and docstrings that disagree with what the code does |
| rambling | Five paragraphs where one line belongs |
| machine-prose | Machine-written prose tics: "load-bearing", "robust", "simply", "it's not X — it's Y", em-dash spray, `# Load the config` narration |
| missing-why | Code that needs rationale and has none |
| dead-comments | Commented-out code, debug leftovers, abandoned TODO/FIXME |
| restates-code | Comments that narrate the line below them |
| transient | Dates, ticket ids, hostnames, "new/recently" — prose built to rot |
| docstring-gaps | Public API whose contract can't be read from its docstring |
| doc-drift | README and `docs/*.md` claims the code no longer matches |
| counting | "All 10 lenses" beside a directory of 11, and "step 5"-style positional references |
| settled-history | Prose about what was removed, migrated or rejected — true, and nothing to act on |
| noise | Banner blocks, ASCII dividers, decoration instead of structure |

## Modes

| Mode | What runs |
|------|-----------|
| Full | Every lens (default) |
| Quick | 5 high-signal lenses: contradicts-code, rambling, machine-prose, missing-why, dead-comments |
| Pick | You choose which lenses to run |

Agents run sequentially by default — it spreads token spend across the run instead of bursting it. Either way one agent runs alone first: it writes the cache entry for the system prompt and tool definitions, and every agent after it reads that entry. The rolling window costs the same and finishes sooner.

## Installation

Tell your agent to read this repository and ask it to help you integrate it into your Claude Code setup as a skill.
