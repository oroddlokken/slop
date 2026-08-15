# String Cop

Interface copy quality review. Spins up parallel agents — each reviewing through a different lens — then distills all findings into prioritized action points.

This one reviews what the screen **says**, not how it looks. The layout can be immaculate and the copy can still lecture, reassure, apologise, or narrate the button the user is already looking at. That is what String Cop hunts.

The core judgment call: a string carrying a fact the user cannot get from the screen — a real constraint, a real consequence, a real next step — earns its space. Comfort, rationale, tutorials, and restatements of the visible are the targets.

## What you get

One agent per lens independently reviews the interface's user-facing strings. After all finish, findings are deduplicated and distilled into:

- **Fix Now** — copy that actively misleads
- **Should Address** — filler, lectures, and prose that costs more than it gives
- **Consider** — valid but non-urgent cleanups
- **Skipped Noise** — subjective or trivial findings (ignored)

Every action item includes a file path and line number.

## Lenses

| Lens | Focus |
|------|-------|
| contradicts-view | Strings that disagree with what the app renders or does |
| reassurance | Comfort about a risk the user never raised |
| self-justification | The app explaining why it was built this way, or praising itself |
| lecture | Teaching a domain concept where showing the value would do |
| widget-narration | Explaining how to operate a control that is already labelled |
| redundancy | One screen saying the same thing twice |
| scaffold-filler | Template copy that shipped and was never rewritten |
| cross-screen | The same concept worded differently on different screens |
| empty-and-error | The two screens where the user is already stuck |
| llm-slop | AI-chatbot prose tics, filler vocabulary, statistical-middle writing |

## Modes

| Mode | What runs |
|------|-----------|
| Full | Every lens (default) |
| Quick | 5 high-signal lenses: contradicts-view, reassurance, self-justification, widget-narration, scaffold-filler |
| Pick | You choose which lenses to run |

Agents run sequentially by default — it spreads token spend across the run instead of bursting it. Either way one agent runs alone first: it writes the cache entry for the system prompt and tool definitions, and every agent after it reads that entry. The rolling window costs the same and finishes sooner.

## Installation

Tell your agent to read this repository and ask it to help you integrate it into your Claude Code setup as a skill.
