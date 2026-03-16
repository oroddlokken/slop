---
name: scrutinize
description: "Use when the user wants to stress-test code quality through simulated community reactions (Reddit, HN, Twitter, Lobsters, /g/, Fediverse, Stack Overflow, LinkedIn, GitHub Issues, YouTube) and distill into action points."
user_invocable: true
---

# Scrutinize

Spin up parallel agents to simulate how Reddit, Hacker News, Tech Twitter, Lobste.rs, 4chan /g/, the Fediverse, Stack Overflow, LinkedIn, GitHub Issues, and YouTube would react to a codebase. Then distill the combined feedback into prioritized action points.

## Workflow

### Step 1: Choose Mode

Ask the user which mode they want:

- **Full** — Run all ten in parallel, then distill. Most thorough.
- **Reddit** — Reddit community reaction only, then distill.
- **HN** — Hacker News reaction only, then distill.
- **Twitter** — Tech Twitter reaction only, then distill.
- **Lobsters** — Lobste.rs reaction only, then distill.
- **/g/** — 4chan /g/ reaction only, then distill.
- **Fediverse** — Mastodon/Fediverse reaction only, then distill.
- **Stack Overflow** — Stack Overflow reaction only, then distill.
- **LinkedIn** — LinkedIn tech influencer reaction only, then distill.
- **GitHub Issues** — GitHub Issues reaction only, then distill.
- **YouTube** — YouTube comment section reaction only, then distill.

Default to **Full** if the user doesn't specify. In Full mode, all ten agents run in parallel.

### Step 1.5: Check for Existing Issue Tracker

Before scanning, check if the project uses **dcat** (dogcat) by running `which dcat`. If dcat is installed and a `.dogcats/` directory exists in the target path, run `dcat list --agent-only` to get existing issues. Pass this issue list to each agent so they can skip concerns that are already tracked.

### Step 2: Determine Target

Ask the user (if not already clear):
- **Path**: Which directory to scrutinize (default: current working directory)
- **Style**: `balanced` | `snarky` | `supportive` | `hostile` (default: `balanced`) — applied to all agents
- **Focus** (optional): A specific area to concentrate on — e.g., `testing`, `security`, `architecture`, `performance`, `error-handling`, `docs`, `dependencies`, `accessibility`. When set, agents spend ~3x more attention on this area. Leave blank for general scrutiny.
- **Verbose**: `yes` | `no` (default: `no`) — When `yes`, show the full community discussions before the distilled action points. When `no`, skip straight to the action points (agent outputs are still used internally for distilling, just not shown to the user).
- **Subreddit** (Reddit mode only): Auto-detect from project language if not specified (e.g., Rust project → r/rust, Python → r/python, otherwise r/programming)

### Step 3: Launch Agents

Read the agent instruction files and spin up agents using the Agent tool. In Full mode, launch all ten in parallel. In single mode, launch just the one.

Before launching agents, read `agents/scan-steps.md` once — its contents will be injected into each agent prompt.

For each agent:
1. Read its instruction file from `agents/`
2. Replace `{path}`, `{style}`, `{subreddit}` (Reddit only), `{focus}` (with focus instruction or empty string), and `{scan_steps}` (with the contents of scan-steps.md) with actual values
3. For `{focus}`: if the user specified a focus area, replace with the focus block below. If no focus was specified, replace `{focus}` with an empty string.
4. If dcat issues were found, append them to the agent prompt under a `## Known Issues (skip these)` section
5. If **verbose=no**: append the compact mode block below to the agent prompt
6. Pass the result as the agent prompt

**Compact mode block** (appended when verbose=no):
```
## Compact Mode

The user will NOT read the discussion — only the Findings Summary matters. Optimize accordingly:
- Skip noise-only archetypes entirely (no "First!", no "+1", no "Congrats!", no meme-only posts, no greentext stories, no "Who's watching in 2026?", no bookmarkers, no engagement farmers, etc.)
- Every comment/post MUST contain at least one technical observation grounded in actual code
- Reduce comment count by ~40% — only generate comments that produce findings
- Keep the community voice and perspective (that's what shapes what you catch), but cut the theater
- The Findings Summary table is your primary output — make it thorough
```

**Focus block** (inserted when focus is set):
```
## Focus Area: {area}

Concentrate your analysis primarily on **{area}**. During the scan, go deeper on {area}-related aspects (read more files, check more patterns). In the discussion, ensure at least 40% of technical comments address {area} concerns. In the Findings Summary, {area}-related issues should be thoroughly covered — don't just flag them, explain the specific impact.

Other issues are still worth mentioning but give {area} roughly 3x the attention and depth.
```

**Reddit**: Read `agents/reddit-scrutinizer.md`
**Hacker News**: Read `agents/hn-scrutinizer.md`
**Twitter/X**: Read `agents/twitter-scrutinizer.md`
**Lobsters**: Read `agents/lobsters-scrutinizer.md`
**/g/**: Read `agents/4chan-scrutinizer.md`
**Fediverse**: Read `agents/fediverse-scrutinizer.md`
**Stack Overflow**: Read `agents/stackoverflow-scrutinizer.md`
**LinkedIn**: Read `agents/linkedin-scrutinizer.md`
**GitHub Issues**: Read `agents/github-issues-scrutinizer.md`
**YouTube**: Read `agents/youtube-scrutinizer.md`

### Step 4: Present Results

- **If verbose=yes**: Output full agent results. In Full mode, order: Reddit → HN → Twitter → Lobsters → /g/ → Fediverse → Stack Overflow → LinkedIn → GitHub Issues → YouTube.
- **If verbose=no** (default): Skip this step entirely — go straight to distilling. The agent outputs are still available internally, just not shown to the user.

### Step 5: Distill

After presenting all results, analyze the combined output:

1. Read through every generated comment/reply and classify feedback:
   - **Actionable criticism**: Points to a real code issue that can be fixed
   - **Architecture concern**: Suggests a structural change worth considering
   - **Missing feature**: Something users would expect but isn't there
   - **Documentation gap**: Something that confused commenters
   - **Security/risk flag**: Anything security-related
   - **Noise**: Memes, bikeshedding, language wars — skip these

2. Cross-reference with code: read referenced files to confirm issues exist

3. Deduplicate using the following algorithm:
   - **Pass 1 — File match**: Group findings that reference the same file and line range (within 10 lines). These are almost certainly the same issue.
   - **Pass 2 — Category match**: Within the same file, merge findings that share an issue category (e.g., two agents both flagging "missing error handling" in the same module).
   - **Pass 3 — Semantic match**: Across different files, merge findings that describe the same systemic issue (e.g., "no tests" flagged by multiple agents pointing at different code).
   - After merging, mark cross-community consensus with "⚡ flagged by N/{total}" where {total} is the number of communities run (e.g., "⚡ flagged by 6/10").
   - Use the structured findings from each agent's `## Findings Summary` section as the primary dedup input — fall back to parsing prose comments only if the summary is missing.

4. Output as:

```
## Action Points

### 🔴 Fix Now
Issues that affect correctness, security, or data integrity.

1. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change and why}
2. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change and why}

### 🟡 Should Address
Real quality issues that affect maintainability or user experience.

3. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change and why}
4. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change and why}

### 🟢 Consider
Valid suggestions worth thinking about but not urgent.

5. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change and why}

### 💨 Skipped Noise
{count} comments were memes, bikeshedding, or pure opinion — ignored.
```

Rules for distilling:
- **Number items sequentially across all sections** (1, 2, 3... not restarting per section) so the user can reference them by number (e.g., "fix 3 and 7")
- If dcat issues were found earlier, exclude any action point that overlaps with an existing tracked issue — it's already known
- Each item must have a file path — no vague suggestions
- One line per fix — say what to change, not why the community is upset
- No duplicates — if many comments said "add tests", that's one action point
- Severity is based on code impact, not how many commenters mentioned it
- Skip style-only feedback unless it affects readability significantly

After outputting, ask the user if they want to start working on any of the items.

## Rules

- **In Full mode, always run all ten in parallel** — never sequentially
- **Each agent scans independently** — don't pass pre-scanned data between them
- **Distill runs after all agents complete** — it needs the full picture
- **Don't skip the distill step** — the action points are the whole point
