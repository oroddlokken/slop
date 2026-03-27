---
name: sweep
description: "Meta design review skill. Spins up parallel agents — each reviewing through a different design lens (audit, critique, harden, optimize, polish, clarify, arrange, typeset, colorize) — then distills all findings into prioritized action points."
args:
  - name: area
    description: The feature, component, or path to review (optional)
    required: false
user-invokable: true
---

# Sweep

Launch parallel design-review agents, each analyzing the codebase through a different lens, then distill all findings into unified, prioritized action points.

## Workflow

### Step 1: Choose Mode

Ask the user which mode they want:

- **Full** — Run all 10 reviewers in parallel, then distill. Most thorough.
- **Quick** — Run 3 core reviewers (audit, critique, polish), then distill. Faster.
- **Pick** — Let the user choose which reviewers to run.

Available reviewers:

| Reviewer | Lens | Fix skill |
|----------|------|-----------|
| audit | Accessibility, performance, theming, responsive | `/normalize`, `/optimize`, `/harden` |
| critique | Visual hierarchy, IA, emotional resonance, composition | `/frontend-design` |
| harden | Edge cases, error states, i18n, overflow | `/harden` |
| optimize | Loading, rendering, animations, bundle size | `/optimize` |
| polish | Alignment, spacing, states, transitions, consistency | `/polish` |
| clarify | UX copy, labels, error messages, microcopy | `/clarify` |
| arrange | Layout, spacing, visual rhythm | `/arrange` |
| typeset | Font choices, hierarchy, sizing, readability | `/typeset` |
| colorize | Palette cohesion, contrast, purposeful color use | `/colorize` |
| ux | Task flow friction, affordances, feedback loops, form UX, cognitive load | `/ux` |

Default to **Full** if the user doesn't specify.

### Step 1.5: Check for Existing Issue Tracker

Before scanning, check if the project uses **dcat** (dogcat) by running `which dcat`. If dcat is installed and a `.dogcats/` directory exists in the target path, run `dcat list --agent-only` to get existing issues. Pass this issue list to each agent so they can skip concerns that are already tracked.

### Step 2: Determine Target

Ask the user (if not already clear):
- **Path**: Which directory to review (default: current working directory)
- **Focus** (optional): A specific area to concentrate on — e.g., `accessibility`, `dark-mode`, `mobile`, `forms`, `navigation`, `typography`, `animations`. When set, agents spend ~3x more attention on this area.

### Step 2.5: Prescan the Codebase (orchestrator does this once)

Read `scan-steps.md` from this skill's directory and follow its scan procedure. The orchestrator (you) reads all files once, then builds a single `{codebase_snapshot}` block that gets passed to every agent. This avoids 10 agents each independently scanning the same files.

1. Replace `{focus}` in `scan-steps.md`
2. Follow the scan procedure — read manifests, UI files, design system files, etc.
3. Format all collected file contents into the snapshot format specified in `scan-steps.md`
4. Store the result as `{codebase_snapshot}` for use in Step 3

### Step 3: Launch Agents

Use a single agent template (`sweep-agent.md`). Launch agents using the Agent tool — all in parallel for Full mode.

For each reviewer:
1. Read `sweep-agent.md` from this skill's directory
2. Replace `{reviewer}` with the reviewer name (e.g., `audit`)
3. Replace `{path}` with the target path
4. Replace `{skill_path}` with the path to the existing skill's SKILL.md (e.g., `skills/audit/SKILL.md`)
5. Replace `{codebase_snapshot}` with the snapshot from Step 2.5
6. If the user specified a focus area, replace `{focus}` with the focus block below. If no focus was specified, replace `{focus}` with an empty string.
7. If dcat issues were found, append them to the agent prompt under a `## Known Issues (skip these)` section
8. Pass the result as the agent prompt

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
| arrange | `skills/arrange/SKILL.md` |
| typeset | `skills/typeset/SKILL.md` |
| colorize | `skills/colorize/SKILL.md` |
| ux | `skills/ux/SKILL.md` |

All paths are relative to the skills directory.

### Step 4: Distill

After all agents complete, analyze the combined output:

1. Read through every finding from every agent and classify:
   - **Critical defect**: Broken functionality, WCAG A violation, security issue
   - **Quality issue**: Poor UX, inconsistency, missing states, bad contrast
   - **Design debt**: Suboptimal but functional — worth improving
   - **Polish opportunity**: Small detail that separates good from great
   - **Noise**: Subjective preference or edge case not worth addressing — skip

2. Cross-reference with code: read referenced files to confirm issues exist

3. Deduplicate using the following algorithm:
   - **Pass 1 — File match**: Group findings that reference the same file and line range (within 10 lines). These are almost certainly the same issue.
   - **Pass 2 — Category match**: Within the same file, merge findings that share an issue category (e.g., two agents both flagging "missing hover state" in the same component).
   - **Pass 3 — Semantic match**: Across different files, merge findings that describe the same systemic issue (e.g., "inconsistent spacing" flagged by polish, arrange, and audit pointing at different components).
   - After merging, mark cross-reviewer consensus with "flagged by N/{total}" where {total} is the number of reviewers run.
   - Use the structured findings from each agent's `## Findings Summary` section as the primary dedup input.

4. Output as:

```
## Sweep Results

### Red — Fix Now
Issues that affect accessibility, correctness, or core usability.

1. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change} | Fix with: `/{skill}`

### Yellow — Should Address
Real quality issues that affect design consistency or user experience.

2. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change} | Fix with: `/{skill}`

### Green — Consider
Valid improvements worth thinking about but not urgent.

3. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change} | Fix with: `/{skill}`

### Skipped
{count} findings were subjective preference or noise — ignored.
```

Rules for distilling:
- **Number items sequentially across all sections** (1, 2, 3... not restarting per section) so the user can reference them by number
- If dcat issues were found earlier, exclude any action point that overlaps with an existing tracked issue
- Each item must have a file path — no vague suggestions
- Each item must recommend which `/skill` to use for the fix
- One line per fix — say what to change concretely
- No duplicates — if multiple reviewers flagged the same thing, merge into one item with consensus count
- Severity is based on user impact, not how many reviewers mentioned it
- Skip style-only feedback unless it affects usability or consistency significantly

After outputting, ask the user if they want to start working on any of the items (or run the suggested `/skill` on specific items).

## Rules

- **In Full mode, always run all 10 in parallel** — never sequentially
- **The orchestrator prescans the codebase once (Step 2.5) and passes the snapshot to all agents** — agents do NOT scan independently
- **Agents inherit the default model** — do not override with a specific model.
- **Agents ONLY audit — they never modify code**
- **Distill runs after all agents complete** — it needs the full picture
- **Don't skip the distill step** — the action points are the whole point
- **Every finding must reference a file path and line** — no hand-wavy suggestions
