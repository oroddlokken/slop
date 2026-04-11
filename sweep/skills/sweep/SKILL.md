---
name: sweep
description: "Meta design review skill. Spins up parallel agents — each reviewing through a different design lens (audit, critique, harden, optimize, polish, clarify, layout, typeset, colorize) — then distills all findings into prioritized action points."
args:
  - name: area
    description: The feature, component, or path to review (optional)
    required: false
user-invokable: true
---

# Sweep

Launch parallel design-review agents, each analyzing the codebase through a different lens, then distill all findings into unified, prioritized action points.

## Rules

- **Ask the user for launch strategy** (Sequential or 1+Parallel). Default to Sequential. Everything above `---` in the agent template is identical across agents and gets cached by the API after the first agent, reducing input cost by ~90%.
- **The orchestrator prescans the codebase once and passes the snapshot to all agents** — agents do NOT scan independently.
- **Agents inherit the default model** so severity ratings stay comparable across reviewers — mixing models produces inconsistent P0/P1/P2/P3 thresholds that make distillation and deduplication unreliable.
- **Agents perform read-only audits** — document findings for user review before any changes.
- **Run distillation after all agents complete.** Every finding must reference a file path and line.

## Workflow

### Step 1: Choose Mode

Ask the user which mode they want:

- **Full** — Run all 9 reviewers in parallel, then distill (audit, critique, harden, optimize, polish, clarify, layout, typeset, colorize). Most thorough.
- **Quick** — Run 3 core reviewers (audit, critique, polish), then distill. Faster.
- **Pick** — Let the user choose which reviewers to run.

Available reviewers:

| Reviewer | Lens | Fix skill |
|----------|------|-----------|
| audit | Accessibility, performance, theming, responsive, anti-patterns | `/polish`, `/optimize`, `/harden` |
| critique | Nielsen heuristics, cognitive load, emotional journey, personas, AI-slop | `/impeccable` |
| harden | Edge cases, error states, i18n, overflow | `/harden` |
| optimize | Loading, rendering, animations, bundle size | `/optimize` |
| polish | Alignment, spacing, states, transitions, consistency | `/polish` |
| clarify | UX copy, labels, error messages, microcopy | `/clarify` |
| layout | Layout, spacing, visual rhythm | `/layout` |
| typeset | Font choices, hierarchy, sizing, readability | `/typeset` |
| colorize | Palette cohesion, contrast, purposeful color use | `/colorize` |

Default to **Full** if the user doesn't specify.

### Step 1.5: Check for Existing Issue Tracker

Before scanning, check if the project uses **dcat** (dogcat) by running `which dcat`. If dcat is installed and a `.dogcats/` directory exists in the target path, run `dcat list --agent-only` to get existing issues. Pass this issue list to each agent so they can skip concerns that are already tracked.

### Step 2: Determine Target

Ask the user (if not already clear):
- **Path**: Which directory to review (default: current working directory)
- **Focus** (optional): A specific area to concentrate on — e.g., `accessibility`, `dark-mode`, `mobile`, `forms`, `navigation`, `typography`, `animations`. When set, agents spend ~3x more attention on this area.

### Step 2.5: Prescan the Codebase (orchestrator does this once)

Read `scan-steps.md` from this skill's directory and follow its scan procedure. The orchestrator (you) reads all files once, then builds a single `{codebase_snapshot}` block that gets passed to every agent. This avoids nine agents each independently scanning the same files.

1. Replace `{focus}` in `scan-steps.md`
2. Follow the scan procedure — read manifests, UI files, design system files, etc.
3. Format all collected file contents into the snapshot format specified in `scan-steps.md`
4. Store the result as `{codebase_snapshot}` for use in Step 3

### Step 3: Launch Agents

Use a single agent template (`sweep-agent.md`). The template places shared content (codebase snapshot, review checklist, output format) before the `---` divider to form a common prompt prefix for API caching.

**Launch strategy** — Ask the user:

- **Sequential** (default) — Launch agents one at a time, each after the previous completes. First agent primes the cache; every subsequent agent reads the shared prefix at ~90% cheaper input. Slowest, cheapest.
- **1+Parallel** — Launch one agent first to prime the cache, then launch remaining agents in parallel batches of at most 5. Anthropic rate-limits large simultaneous bursts, so batching past 5 triggers 429s mid-run and wastes the work of any agent that already completed. Nearly as cheap as Sequential, much faster.

**Cache structure** — The `---` divider in sweep-agent.md is the cache boundary. Everything above it is the shared prefix (identical for all agents). Everything below is per-agent. API prompt caching matches byte-for-byte prefixes, so:
- Shared prefix placeholders (`{codebase_snapshot}`, `{path}`, `{focus}`, `{known_issues}`) resolve to the **same value** for all agents. Resolve these once and reuse the identical string.
- Per-agent placeholders (`{reviewer}`, `{skill_path}`) differ per agent. Place them below the `---` line so the shared prefix stays byte-identical — any per-agent content above the divider breaks cache matching and each reviewer pays full input cost (~10x more expensive).

**Build the shared prefix once:**
1. Read `sweep-agent.md` from this skill's directory
2. Replace `{path}` with the target path
3. Replace `{codebase_snapshot}` with the snapshot from Step 2.5
4. Read `skills/impeccable/SKILL.md` and replace `{design_principles}` with its full contents. This gives every reviewer access to the absolute bans, AI-slop tells, typography/color/spatial principles, and DO/DON'T lists that their assigned skill file references but does not inline. The block lives in the shared prefix so it is cached across agents — each reviewer pays the cost once (first agent) and all subsequent agents read it at the cached rate.
5. If the user specified a focus area, replace `{focus}` with the focus block below. Otherwise replace with an empty string.
6. If dcat issues were found, replace `{known_issues}` with a `## Known Issues (skip these)` section listing them. Otherwise replace with an empty string.
7. Store this as the **resolved template** — the content above `---` is now fixed and identical for all agents.

**For each reviewer, resolve per-agent content:**
1. In the resolved template, replace `{reviewer}` with the reviewer name (e.g., `audit`)
2. Replace `{skill_path}` with the path to the existing skill's SKILL.md (e.g., `skills/audit/SKILL.md`)
3. Pass the result as the agent prompt

**Focus block** (inserted when focus is set):
```
## Focus Area: {area}

Concentrate your analysis primarily on **{area}**. During the scan, go deeper on {area}-related aspects (read more files, check more patterns). In your findings, {area}-related issues should be thoroughly covered — don't just flag them, explain the specific impact.

Other issues are still worth mentioning but give {area} roughly 3x the attention and depth.
```

**Reviewer → skill path mapping:**

| Reviewer | Reads criteria from |
|----------|-------------------|
| audit | `skills/audit/SKILL.md` |
| critique | `skills/critique/SKILL.md` |
| harden | `skills/harden/SKILL.md` |
| optimize | `skills/optimize/SKILL.md` |
| polish | `skills/polish/SKILL.md` |
| clarify | `skills/clarify/SKILL.md` |
| layout | `skills/layout/SKILL.md` |
| typeset | `skills/typeset/SKILL.md` |
| colorize | `skills/colorize/SKILL.md` |

All paths are relative to the skills directory.

### Step 4: Distill

After all agents complete, read `distill.md` from this skill's directory and follow the distillation algorithm.

