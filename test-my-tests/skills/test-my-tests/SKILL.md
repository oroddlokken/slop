---
name: test-my-tests
description: "Test quality deep-dive. Spins up parallel agents — each reviewing tests through a different lens (coverage gaps, user flows, mock debt, assertion quality, error paths, data realism, etc.) — then distills all findings into prioritized action points."
args:
  - name: area
    description: The directory or area to review (optional)
    required: false
user-invokable: true
---

# Test My Tests

Launch parallel test-quality agents, each analyzing the test suite through a different lens, then distill all findings into unified, prioritized action points. Goes beyond "do tests exist?" to ask "do these tests actually catch real bugs?"

## Rules

- **Ask the user for launch strategy** (Sequential or 1+Parallel). Default to Sequential. Everything above `---` in the agent template is identical across agents and gets cached by the API after the first agent, reducing input cost by ~90%.
- **The orchestrator prescans source AND test code once and passes the snapshot to all agents** — agents do NOT scan independently.
- **Agents inherit the default model** — do not override with a specific model.
- **Agents analyze tests without modifying files.** No running tests, no modifying code.
- **Run distillation after all agents complete.** Distillation needs the full picture to deduplicate and prioritize.

## Workflow

### Step 1: Choose Mode

Ask the user which mode they want:

- **Full** — Run all 10 reviewers, then distill. Most thorough.
- **Quick** — Run 5 high-impact reviewers (coverage-gaps, user-flows, happy-path-only, error-paths, assertion-quality), then distill. Faster.
- **Pick** — Let the user choose which reviewers to run.

### Severity Definitions (all reviewers)

- **Critical**: Untested path that could cause data loss, security bypass, or financial impact
- **High**: Missing test for a complex user flow or important error path
- **Medium**: Existing test with significant quality gaps (weak assertions, unrealistic data)
- **Low**: Minor test improvement that would increase confidence

Available reviewers:

| Reviewer | Lens |
|----------|------|
| coverage-gaps | Critical code paths with zero test coverage |
| happy-path-only | Tests that only verify the sunny-day scenario |
| user-flows | Multi-step real-world workflows not tested end-to-end |
| mock-debt | Mocks that diverge from reality, over-mocking |
| assertion-quality | Weak or missing assertions, no side-effect verification |
| fragile-tests | Tests coupled to implementation, break on harmless refactors |
| data-realism | Test data too simple for production scenarios |
| error-paths | Failure modes untested (network, permissions, timeouts) |
| boundary-values | Off-by-one, empty collections, limits, type boundaries |
| flaky-risks | Time-dependent, order-dependent, shared state, race conditions |

Default to **Full** if the user doesn't specify.

### Scope Boundaries

Some reviewers examine similar code from different angles. When findings overlap:
- **coverage-gaps** owns "no test exists at all". **happy-path-only** owns "test exists but only covers the good case".
- **error-paths** owns testing of failure modes. **boundary-values** owns testing of edge values. Both may flag the same function — error-paths focuses on what happens when things go wrong, boundary-values focuses on extreme-but-valid inputs.
- **assertion-quality** owns what tests check. **happy-path-only** owns which scenarios tests cover. If a test covers an error path but asserts poorly, assertion-quality takes it.
- **mock-debt** owns mock/stub concerns. **fragile-tests** owns coupling to implementation. If a mock is both unrealistic AND makes the test fragile, mock-debt takes it.
- **data-realism** owns fixture/factory data quality. **boundary-values** owns specific edge values. If test data is both simplistic AND misses boundaries, data-realism takes the systemic issue, boundary-values takes specific missing values.

### Step 1.5: Language Prescan

Detect which languages are in scope so agents review tests for all of them:

1. Run `git ls-files` in the target path (or cwd) and group files by extension
2. Map extensions to languages
3. Skip: `*.png`, `*.jpg`, `*.gif`, `*.svg`, `*.ico`, `*.woff*`, `*.ttf`, `*.lock`, `*.min.js`, `*.min.css`, and directories `node_modules/`, `vendor/`, `dist/`, `build/`
4. Present the detected languages sorted by file count
5. Ask: "Are these the languages to review? (Remove or add any)"
6. Pass the confirmed list to each agent via `{languages}`

### Step 1.75: Check for Existing Issue Tracker

Check if the project uses **dcat**. Run `which dcat`. If the command succeeds AND a `.dogcats/` directory exists at the target path, run `dcat list --agent-only` to get tracked issues. Pass this list to each agent so they skip already-known problems. If either check fails, skip this step.

### Step 2: Determine Target

Ask the user (if not already clear):
- **Path**: Which directory to review (default: current working directory)
- **Focus** (optional): A specific area to concentrate on — e.g., `auth`, `api`, `payments`, `database`, `file-upload`. When set, agents spend ~3x more attention on tests for this area.

### Step 2.5: Prescan the Codebase (orchestrator does this once)

Read `scan-steps.md` from this skill's directory and follow its scan procedure. The orchestrator (you) reads both source and test files once, then builds a single `{codebase_snapshot}` block that gets passed to every agent.

1. Replace `{languages}` and `{focus}` in `scan-steps.md`
2. Follow the scan procedure — read manifests, source files, test files, fixtures, CI config
3. Format all collected file contents into the snapshot format specified in `scan-steps.md`
4. Store the result as `{codebase_snapshot}` for use in Step 3

### Step 3: Launch Agents

Use the agent template (`test-agent.md`). The template places shared content (codebase snapshot, languages, ground rules, output format) before the `---` divider to form a common prompt prefix for API caching.

**Launch strategy** — Ask the user:

- **Sequential** (default) — Launch agents one at a time, each after the previous completes. First agent primes the cache; every subsequent agent reads the shared prefix at ~90% cheaper input. Slowest, cheapest.
- **1+Parallel** — Launch one agent first, wait for it to complete, then launch all remaining in parallel. Nearly as cheap, much faster.

If the user doesn't specify, use **Sequential**.

**Cache structure** — The `---` divider in test-agent.md is the cache boundary. Everything above it is the shared prefix (identical for all agents). Everything below is per-agent. API prompt caching matches byte-for-byte prefixes, so:
- Shared prefix placeholders (`{codebase_snapshot}`, `{path}`, `{languages}`, `{focus}`, `{known_issues}`) resolve to the **same value** for all agents. Resolve these once and reuse the identical string.
- Per-agent placeholders (`{reviewer}`, `{reviewer_criteria}`) differ per agent. These go below `---` and do not affect cache matching.
- **Never insert per-agent content above the `---` line.** This includes scope boundary rules — append those after `{reviewer_criteria}`, not in the shared prefix.

**Build the shared prefix once:**
1. Read `test-agent.md` from this skill's directory
2. Replace `{path}` with the target path
3. Replace `{codebase_snapshot}` with the snapshot from Step 2.5
4. Replace `{languages}` with the confirmed language list
5. If the user specified a focus area, replace `{focus}` with the focus block below. Otherwise replace with an empty string.
6. If dcat issues were found, replace `{known_issues}` with a `## Known Issues (skip these)` section listing them. Otherwise replace with an empty string.
7. Store this as the **resolved template** — the content above `---` is now fixed and identical for all agents.

**For each reviewer, resolve per-agent content:**
1. In the resolved template, replace `{reviewer}` with the reviewer name (e.g., `coverage-gaps`)
2. Read `reviewers/{reviewer}.md`. If the file does not exist, skip that reviewer and warn the user. Replace `{reviewer_criteria}` with the file contents.
3. For overlapping reviewers (coverage-gaps/happy-path-only, error-paths/boundary-values, assertion-quality/happy-path-only, mock-debt/fragile-tests, data-realism/boundary-values), append the relevant scope boundary rule from the Scope Boundaries section **after** `{reviewer_criteria}` (below `---`).
4. Pass the result as the agent prompt

**Focus block** (inserted when focus is set — replace `{area}` with the user's focus area):
```
## Focus Area: {area}

Concentrate your analysis primarily on tests for **{area}**. Go deeper on {area}-related test files and the source code they cover. {area}-related findings should be thoroughly explored.

Other areas are still worth reviewing but give {area} roughly 3x the attention.
```

### Step 4: Distill

After all agents complete, read `distill.md` from this skill's directory and follow the distillation algorithm.

### Error Handling

- If `git ls-files` fails (not a git repo, permissions), fall back to `find {path} -type f` and filter by extension.
- If a reviewer's criteria file does not exist, skip that reviewer and warn the user.
- If all agents return zero findings, output "Test suite looks solid — no significant gaps found" and skip the distill step.
- If some agents fail or timeout, distill with available results and note which reviewers were skipped.

