---
name: string-cop
description: "Interface copy quality review. Spins up parallel agents — each reviewing through a different lens (contradicts-view, reassurance, self-justification, lecture, widget-narration, redundancy, scaffold-filler, cross-screen, empty-and-error, llm-slop) — then distills all findings into prioritized action points. Reviews what the screen SAYS, not how it looks."
args:
  - name: area
    description: The directory or area to review (optional)
    required: false
user-invocable: true
---

# String Cop

Launch parallel reviewers, each analyzing the application's **user-facing strings** through a different lens, then distill all findings into unified, prioritized action points.

This skill reviews the *rendered layer*. Every heading, hint, tooltip, button label, empty state, flash message and error string a user reads. `comment-cop` reviews the prose a maintainer reads; String Cop reviews the prose a user reads. The failures rhyme — reassurance nobody asked for, design rationale on the page, a paragraph where a number belongs — but the reader is different and so is the cost. A bad comment wastes a maintainer's minute. A bad hint makes a user distrust the number next to it.

**The core judgment call:** a hint that carries a **unit, a source, a limit, or a consequence the screen cannot show** earns its place and must be protected. A tooltip explaining that `poll` means the end time is accurate only to one interval is doing work no label can do. A paragraph explaining why the developer chose this layout is not. Reviewers must separate the two — flagging a hint that carries a fact is a false positive and worse than missing a bad string.

## Scope

**In scope:** every string that reaches a screen.
- Template text: headings, body copy, hints, tooltips (`title=`), `aria-label`, `placeholder`, `alt`, button and link labels, empty states
- View and domain code that supplies strings to templates: flash messages, error text, validation messages, enum display labels, remediation hints built in Python/Go/TS and rendered later. A check whose hint string lives in `drift.py` and never appears in a template still renders to the page, so template-only review misses it
- Anything in a translation catalogue (`.po`, `messages.json`, i18n JSON) that a screen renders

**Out of scope:** layout, spacing, color, markup structure, component hierarchy, accessibility beyond the *wording* of a label. String Cop grades what the words say, never how they look. An `aria-label` is in scope because it is a string a screen reader reads aloud; whether the element needed one at all is not.

## Who Does What

- **Orchestrator** (you, the main Claude Code session): Runs Steps 1-4 — asks user questions, extracts the string inventory, launches reviewer agents, distills findings.
- **Reviewer agents** (spawned subagents): Receive a read-only string inventory, analyze it through one lens, return findings. They do not scan independently, modify code, or interact with live systems.

## Rules

- **Ask the user for launch strategy** (Sequential or 1+Parallel). Default to Sequential — it spreads token spend across the run instead of bursting it. Agents do not share prompt cache with each other, so launch order does not change cost.
- **The orchestrator extracts the string inventory once and passes it to all agents** — agents do NOT scan independently. The inventory reproduces strings verbatim with file:line; it does not reproduce whole templates.
- **Agents inherit the default model** — do not override with a specific model.
- **Run distillation after all agents complete.** Raw output is overwhelming without deduplication and prioritization.
- **Never propose changes to the logic or the layout.** Every finding is about a string — its accuracy, necessity, or clarity. If the view is wrong, that is out of scope (point the user at `/codehealth`). If the page is ugly, that is a design concern, not a string finding.

## Workflow

### Step 1: Choose Mode

Ask the user which mode they want:

- **Full** — Run all 10 reviewers, then distill (contradicts-view, reassurance, self-justification, lecture, widget-narration, redundancy, scaffold-filler, cross-screen, empty-and-error, llm-slop).
- **Quick** — Run 5 high-signal reviewers (contradicts-view, reassurance, self-justification, widget-narration, scaffold-filler), then distill. Faster.
- **Pick** — Let the user choose which reviewers to run.

If the user does not specify a mode, run Full mode automatically.

### Severity Definitions (all reviewers)

Interface copy is read once, in the middle of a task, by someone who did not ask for it. Severity is measured by **what it costs the user who believes it**:

- **Critical**: The string tells the user something the view contradicts, and acting on it destroys data or misreads a number. A page promising "nothing is deleted" above a control that deletes. Only `contradicts-view` may issue a Critical.
- **High**: The string misleads about scope, state, or safety on an ordinary path — a claim about what the app touches that is not true, a stale caveat that no longer describes the render. Also: an error string a user cannot act on because it names no location, cause, or fix.
- **Medium**: Reassurance nobody asked for, design rationale on the page, a lecture where a number belongs, one fact copied to five screens that will drift apart, scaffold filler on an entry screen.
- **Low**: Widget narration for a control that already says it, a tail restating the head, an isolated slop word, scaffold filler on an interior screen.

Individual reviewers map their findings to these levels in their Severity Guide section. When the distill step resolves cross-reviewer conflicts, use these universal definitions as the baseline. During distillation, any reviewer-reported "Critical" from a lens other than `contradicts-view` is remapped to "High" before tier assignment. See distill.md for the full mapping algorithm.

Available reviewers:

| Reviewer | Lens |
|----------|------|
| contradicts-view | The string disagrees with what the view actually renders. The only lens that can produce a Critical |
| reassurance | Safety claims nobody asked for; comfort about a risk the user never raised |
| self-justification | Design rationale and self-praise on the page |
| lecture | Textbook paragraph where a number belongs |
| widget-narration | Instructions for a control that already says it |
| redundancy | A tail restating the head; the same paragraph twice on one screen |
| scaffold-filler | Unedited generator boilerplate shipped to users |
| cross-screen | One fact copied to N places, or one thing named two ways |
| empty-and-error | Empty states naming no next action; error strings opening on a mood instead of location, cause, fix |
| llm-slop | The assistant vocabulary, in strings a user reads |

### Scope Boundaries

Several reviewers examine the same string from different angles. When findings overlap:
- **contradicts-view outranks every other lens.** If a string is both wrong and wordy, the wrongness is the finding. A rewrite that only shortens a false claim ships a tidier lie. Other lenses hand their note to contradicts-view rather than filing a second row.
- **reassurance** owns claims about what the app *will not* do (never deletes, never writes, nothing is hidden). **self-justification** owns claims about why the app is *built* the way it is, and claims about its own quality. "No file has been deleted" → reassurance; "Two tools computing the same finding is how they end up disagreeing" → self-justification.
- **lecture** owns domain education — the equation, the algorithm, the physiology. **self-justification** owns product rationale. A paragraph teaching Katch-McArdle versus Mifflin-St Jeor → lecture; a paragraph on why this page withholds the editor → self-justification.
- **widget-narration** owns text describing how to operate a control. **lecture** owns text explaining the concept behind it. "Untick to bring one back" → widget-narration; "the trend is a time-aware moving average with a 6.6-day half-life" → lecture.
- **redundancy** owns repetition *within one screen*. **cross-screen** owns repetition *across screens*. Two paragraphs teaching the same lesson on one profile page → redundancy; one poll caveat on five tooltips in four templates → cross-screen.
- **cross-screen** also owns naming inconsistency — one concept called "weigh-in" here and "measurement" there. No other lens flags terminology drift.
- **scaffold-filler** owns generator boilerplate exclusively: strings that shipped from a template project and were never edited. No other lens flags these, even though they read as narration and slop too.
- **empty-and-error** owns the two states where a user is already stuck: nothing to show, and something went wrong. Any string on those paths is its finding first, regardless of which other lens also matches.
- **llm-slop ranks below contradicts-view.** Whether a string tells the truth matters more than whether it sounds machine-written, and the two are independent — a sentence can be flawlessly written and false. When the same string trips both, the truth finding leads and the style note rides along. A style rewrite must never make an unverified claim more convincing.
- **llm-slop** owns *word choice and sentence shape* in user-facing strings: the vocabulary tics, the antithesis flourish, the promotional register. **lecture** owns volume, **redundancy** owns repetition, **self-justification** owns self-praise. "Seamlessly syncs your data" → llm-slop; "we chose this because it is more conservative" → self-justification.

### Step 1.5: Render Layer Prescan

Detect what actually renders strings so agents cover every source, not just the largest template directory.

1. Run `git ls-files` in the target path (or cwd) and group files by extension
2. Identify template engines by extension and content: `.html`/`.jinja`/`.j2` (Jinja), `.html` with `{% %}` under a Django app, `.erb`, `.hbs`, `.mustache`, `.vue`, `.svelte`, `.tsx`/`.jsx` (JSX text nodes), `.templ`, `.gohtml`
3. Identify the view layer that feeds them: Flask/Django views, Rails controllers, Express routes, React components, Go handlers
4. Identify string catalogues: `.po`, `.pot`, `messages.json`, `locales/**`, any `strings.*` module
5. Skip: `htmlcov/`, `.venv/`, `node_modules/`, `vendor/`, `dist/`, `build/`, `site-packages/`, `coverage/`, and any generated report directory. Coverage HTML is not your interface
6. Present what you found, e.g.:
   ```
   Render layers detected:
   - Jinja templates (17 files, src/vekt/web/templates/)
   - Flask views (4 files, src/vekt/web/)
   - Domain string sources: drift.py (check hints)
   ```
7. Ask: "Are these the render layers to review? (Remove or add any)"
8. After confirmation, pass the final list to each agent via the `{render_layers}` placeholder

**Important:** Do not pass the raw file list to agents. It is used here to scope extraction only.

### Step 1.6: Auto-Skip Irrelevant Lenses

Drop reviewers whose target patterns aren't in the app. Note each drop in the final output's "Reviewers run / skipped" line.

- **Single screen only** (one template, no navigation) → drop `cross-screen`. Note: "Skipped cross-screen (single-screen app)."
- **No empty states and no error templates** (no `error.html`, no flash/message rendering, no "nothing here yet" branch) → drop `empty-and-error`. Note the reason. This is rare; check `{% if not %}` / `{% else %}` branches before dropping.
- **Project was not generated from a scaffold** (no `coming_soon`, no untouched `index` body, no cookiecutter/`create-*-app` traces in git history) → keep `scaffold-filler` but tell it to look for *stale* placeholder copy rather than generator output.

### Step 1.75: Check for Existing Issue Tracker

Check if the project uses **dcat** — a local issue tracker (CLI tool). Try running `dcat list --agent-only` directly. If it succeeds, pass the issue list to each agent so they can skip already-tracked concerns. If it errors (dcat not installed, no `.dogcats/` directory), skip this step.

### Step 2: Determine Target

Ask the user (if not already clear):
- **Path**: Which directory to review (default: current working directory)
- **Focus** (optional): A specific area to concentrate on — e.g., a screen, `onboarding`, `error states`. When set, agents spend ~3x more attention on this area.

### Error Handling

- If `git ls-files` fails (not a git repo, permissions), use the Glob tool (`**/*.{html,j2,jsx,vue,...}` patterns) to enumerate files.
- If a reviewer's criteria file does not exist at the expected path, skip that reviewer and warn the user.
- If all agents return zero findings, output "No issues found" and skip the distill step.
- If some agents fail or timeout, distill with available results and note which reviewers were skipped.

### Step 2.4: Check Inventory Cache

A prior run may have already produced a string inventory of this app. Reuse it before re-extracting.

**Build the cache key**:
1. `git_rev` = output of `git rev-parse HEAD` (or `no-git` if not a git repo)
2. `dirty` = output of `git status --porcelain` (any uncommitted change → different state)
3. `path` = absolute target path
4. `layers` = sorted, comma-joined render-layer list from Step 1.5
5. `skill` = `string-cop`

Concatenate as `{skill}|{path}|{git_rev}|{dirty}|{layers}` and take the first 12 hex chars of `sha256(...)` as `{hash}`.

**Cache file**: `.claude-cache/string-cop-inventory-{hash}.md` (relative to target path).

**Check the cache**:
- If the file exists and was modified within the last hour, read it and use its contents as `{string_inventory}`. Skip Step 2.5.
- Otherwise, proceed to Step 2.5. After building the inventory there, write it to `.claude-cache/string-cop-inventory-{hash}.md`. Create `.claude-cache/` if missing, and add `.claude-cache/` to `.gitignore` if not already listed.

**Note:** String Cop needs strings extracted with file:line, not whole files. Never reuse a snapshot produced by `comment-cop` or `codehealth` — the cache key includes `{skill}`, so they will not collide.

The 1-hour TTL is a staleness backstop, not a prompt-cache window: editing a file that is already dirty leaves `git status --porcelain` unchanged, so the key alone can go stale. Both caches are per-skill by design — every meta-skill scans for different things, so nothing here is reused by another skill.

### Step 2.5: Extract the String Inventory (orchestrator does this once)

Read `scan-steps.md` from this skill's directory and follow its extraction procedure. This is where String Cop differs most from its sibling skills: the orchestrator does **not** reproduce whole files. It extracts rendered strings with file:line, grouped by screen, with just enough surrounding markup to show which element carries each string. Reproducing 60 templates verbatim would blow the context before the first agent runs.

1. Replace `{render_layers}` and `{focus}` in `scan-steps.md`
2. Follow the extraction procedure
3. Format the result into the inventory format specified in `scan-steps.md`
4. Store the result as `{string_inventory}` for use in Step 3

### Step 3: Launch Agents

Use the agent template (`agent.md`). The template places shared content (string inventory, render layers, ground rules, output format) before the `---` divider to form a common prompt prefix for API caching.

**Spawn contract** — how you call the Agent tool, in every launch mode:

- **Never pass `name:`.** A named agent becomes an addressable mailbox teammate, not a subagent. The tool result is `Spawned successfully` plus an agent_id, the findings never come back, and `run_in_background: false` is ignored. `TaskList` and `TaskOutput` cannot see it either. Recovering costs a round of `SendMessage` to every agent asking it to resend.
- **Pass `run_in_background: false`.** You need each agent's findings in hand before the distill step.
- **The Agent tool's return value is the findings.** Read them out of the tool result. Do not wait for a message, a notification, or an idle ping — none of those carry the report.

**Launch strategy** — Ask the user:

- **Sequential** (default) — Launch agents one at a time, each after the previous completes. Spreads token spend across the run instead of bursting it against the 5-hour quota. Slowest.
- **1+Parallel** — Launch one agent, then the remaining agents in parallel batches of at most 5. Anthropic rate-limits large simultaneous bursts, so batching past 5 triggers 429s mid-run and wastes the work of any agent that already completed. Same cost as Sequential, much faster.

If the user doesn't specify, use **Sequential**.

**Prompt caching** — Agents do not share cached prompt content with each other. Measured over a 16-agent run (2026-08-04): every agent read back the same ~7K tokens of system prompt and tool definitions, then created everything else fresh — including a byte-identical 11K-token snapshot, once per agent.

The cause is breakpoint placement. Caching matches a byte prefix ending at a `cache_control` breakpoint, and the harness sets one after the system prompt and one at the end of each message. The Agent tool takes a single prompt string, so the shared snapshot and the per-agent assignment land inside the same cached unit and can never match across agents. Sharing would require the shared half in its own content block with a breakpoint at that boundary; the Agent tool exposes no way to ask for one.

- **The `---` divider is a section divider, not a cache boundary.** Shared placeholders (`{codebase_snapshot}`, `{path}`, `{languages}`, `{focus}`, `{known_issues}`) still resolve once and stay identical across agents, and per-agent placeholders still go below the line — that keeps the template readable and the resolve step cheap. No cost depends on it.
- **Snapshot size is the lever that does matter.** Each agent writes the whole snapshot to cache once at 1.25× input price. An 11K-token snapshot across 16 agents is ~176K write-priced tokens every run. Trimming the snapshot saves money; launch order does not.

**Build the shared prefix once:**
1. Read `agent.md` from this skill's directory
2. Replace `{path}` with the target path
3. Replace `{string_inventory}` with the inventory from Step 2.5
4. Replace `{render_layers}` with the confirmed layer list (e.g., `Jinja templates, Flask views, drift.py check hints`)
5. If the user specified a focus area, replace `{focus}` with the focus block below. Otherwise replace with an empty string.
6. If dcat issues were found, replace `{known_issues}` with a `## Known Issues (skip these)` section listing them. Otherwise replace with an empty string.
7. Store this as the **resolved template** — the content above `---` is now fixed and identical for all agents.

**For each reviewer, resolve per-agent content:**
1. In the resolved template, replace `{reviewer}` with the reviewer name (e.g., `reassurance`)
2. Read `reviewers/{reviewer}.md`. If the file does not exist, skip that reviewer and warn the user. Replace `{reviewer_criteria}` with the file contents.
3. For overlapping reviewers (see Scope Boundaries), append the relevant scope boundary rule from the Scope Boundaries section **after** `{reviewer_criteria}` (below `---`).
4. Pass the result as the agent prompt

**Focus block** (inserted when focus is set):
```
## Focus Area: {area}

Concentrate your analysis primarily on **{area}**. During the review, go deeper on {area}-related strings (read the surrounding template and view code to judge accuracy). In your findings, {area}-related issues should be thoroughly covered — don't just flag them, explain the specific cost to a user.

Other issues are still worth mentioning but give {area} roughly 3x the attention and depth.
```

**Reviewer criteria files** are in this skill's `reviewers/` directory: `contradicts-view.md`, `reassurance.md`, `self-justification.md`, `lecture.md`, `widget-narration.md`, `redundancy.md`, `scaffold-filler.md`, `cross-screen.md`, `empty-and-error.md`, `llm-slop.md`.

### Amending the Brief Mid-Run

The resolved template is **frozen once the first agent launches** — do not edit it, and do not edit the snapshot file it was built from. Agents that already ran cannot see the change, so editing mid-run leaves two populations of findings built on different facts, with nothing recording which is which.

When you find the brief is wrong mid-run — a prescan claim an agent contradicts, a mis-stated invariant, a file that does not exist — record the correction instead of applying it:

1. **Append to an errata list** for this run. One entry per correction: what the brief claimed, what is actually true, and a `file:line` citation for the correction.
2. **Append the errata to the per-agent half** (below `---`) of every agent launched from then on, under a `## Errata` heading introduced by: "The brief contains errors. The entries below are authoritative wherever they contradict it."
3. **Pass the errata to distill**, noting which agents ran before each entry was added. Distill drops or annotates any earlier finding that rests on a corrected claim.

Agents surface corrections too — a lens that checks a prescan claim and finds it false. Treat those the same way: add an entry, and it binds every agent launched after it.

### Step 4: Distill

Spawn a fresh sub-agent for distillation:

- **Model**: `sonnet`. A fresh agent prevents the synthesis from anchoring on whichever reviewer wrote first or loudest, and Sonnet handles the structured-merge job competently at lower cost.
- **Subagent type**: `Explore`. The agent reads files referenced by findings during validation; no other tool access needed.
- **Instructions**: contents of `distill.md` from this skill's directory.
- **Input**: the `## Findings Summary` table from each completed reviewer, prefixed with `### Reviewer: {name}`. Strip surrounding prose — tables only. Also include which reviewers ran, which were skipped, the dcat issues list (if any), and the focus area (if any).
- **Do not pass the string inventory.** Distill works on structured findings; the inventory would inflate input for no gain (file references in findings already point at the strings).

Paste the distill agent's output into your own reply, verbatim and in full.

Only your reply is rendered to the user — the agent's report is not. Never point at it with "the findings are above", "see the report", or similar. Length is not a reason to summarize instead: if the list is long, your reply is long.
