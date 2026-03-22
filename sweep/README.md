# Sweep

Meta design review. Spins up parallel agents — each reviewing through a different design lens — then distills all findings into prioritized action points.

## Prerequisites

This skill is an orchestrator only. It requires the [impeccable](https://github.com/helgesverre/impeccable) design skills to be installed (`audit`, `critique`, `harden`, `optimize`, `polish`, `clarify`, `arrange`, `typeset`, `colorize`, `ux`). Sweep dispatches agents that read each skill's SKILL.md for review criteria.

## What you get

Up to 10 agents independently scan your UI code, each through a different design lens. After all finish, findings are deduplicated and distilled into:

- **Fix Now** — accessibility violations, broken functionality, security issues
- **Should Address** — poor UX, inconsistency, missing states
- **Consider** — valid improvements, not urgent
- **Skipped Noise** — subjective preference (ignored)

Every action item includes a file path, line number, and which `/skill` to use for the fix.

## Lenses

| Lens | Focus | Fix with |
|------|-------|----------|
| audit | Accessibility, performance, theming, responsive | `/normalize`, `/optimize`, `/harden` |
| critique | Visual hierarchy, IA, emotional resonance | `/frontend-design` |
| harden | Edge cases, error states, i18n, overflow | `/harden` |
| optimize | Loading, rendering, animations, bundle size | `/optimize` |
| polish | Alignment, spacing, states, transitions | `/polish` |
| clarify | UX copy, labels, error messages, microcopy | `/clarify` |
| arrange | Layout, spacing, visual rhythm | `/arrange` |
| typeset | Font choices, hierarchy, sizing, readability | `/typeset` |
| colorize | Palette cohesion, contrast, purposeful color | `/colorize` |
| ux | Task flow friction, affordances, feedback loops | `/ux` |

## Modes

| Mode | What runs |
|------|-----------|
| Full | All 10 lenses in parallel (default) |
| Quick | 3 core lenses: audit, critique, polish |
| Pick | You choose which lenses to run |

## Installation

Tell your agent to read this repository and ask it to help you integrate it into your Claude Code setup as a skill.
