## Distillation Algorithm

After all agents complete, analyze the combined output:

1. Read through every finding from every agent and classify:
   - **Untested risk**: Critical code path with no test coverage at all
   - **Shallow coverage**: Tests exist but miss important scenarios
   - **Quality gap**: Tests cover the right scenarios but verify poorly
   - **Structural issue**: Test architecture problems (fragility, flakiness, unrealistic mocks)
   - **Noise**: Subjective preference or low-value test pedantry — skip

   **Severity → Tier mapping from agent output:**
   - Agent "Critical" → Red
   - Agent "High" → Red (if untested security/data path) or Orange (if missing user flow)
   - Agent "Medium" → Yellow
   - Agent "Low" → Green

2. Cross-reference with code: read only files explicitly referenced in findings to confirm line accuracy. Do not scan for additional patterns during distillation.
   - **Hallucinated findings**: If a finding doesn't exist at the reported file:line (wrong code, line doesn't exist, or different logic), discard it and note the count.
   - **Zero findings from an agent** is a valid result — note it as "{reviewer}: no issues found".

3. Deduplicate using the following algorithm:
   - **Pass 1 — File match**: Group findings that reference the same source file or test file and line range (within 10 lines). These are almost certainly the same gap seen from different angles.
   - **Pass 2 — Pattern match**: Within the same module, merge findings that describe the same untested scenario (e.g., "no error handling test" flagged by error-paths and happy-path-only for the same endpoint — that's one missing test, not two issues).
   - **Pass 3 — Systemic match**: Across different files, merge findings that describe the same systemic gap (e.g., "no integration tests for any API endpoint" flagged by multiple agents pointing at different routes). Systemic issues are typically flagged by 3+ reviewers. If only 1-2 flag it, keep findings separate unless the code path is identical.
   - After merging, mark cross-reviewer consensus with "flagged by N/{total}" where {total} is the number of reviewers run.
   - Extract the `## Findings Summary` table from each agent's output as the primary dedup input.
   - **Conflict resolution**: When two lenses disagree on severity, use the higher severity. When they disagree on the fix, note both approaches.

4. Output as:

```
## Test Quality Results

**{total_findings} findings from {num_reviewers} reviewers, distilled to {distilled_count} action points.**

### Red — Untested Risks
Critical code paths with no test coverage. A bug here could ship undetected.

1. [ ] **{title}** — {one-line description}
   `{source_file}:{line}` — {what scenario to test and what to assert} | Lens: `{reviewer}`

### Orange — Missing Scenarios
Tests exist but skip important user flows, error paths, or edge cases.

2. [ ] **{title}** — {one-line description}
   `{test_file}:{line}` — {what scenario to add} | Lens: `{reviewer}`

### Yellow — Weak Tests
Tests cover the right scenarios but verify poorly or use unrealistic data/mocks.

3. [ ] **{title}** — {one-line description}
   `{test_file}:{line}` — {what to strengthen} | Lens: `{reviewer}`

### Green — Consider
Valid improvements worth adding but not urgent.

4. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change} | Lens: `{reviewer}`

### Skipped
{count} findings were minor pedantry or noise — ignored.
{hallucinated_count} findings discarded (reported code not found at referenced locations).
```

Rules for distilling:
- **Number items sequentially across all sections** (1, 2, 3... not restarting per section) so the user can reference them by number
- If dcat issues were found earlier, exclude any action point that overlaps with an existing tracked issue
- Each item must have a file path — reference the source file for untested code, the test file for weak tests
- Each item must note which lens found it (or "flagged by N/{total}" if multiple)
- One line per action — say what scenario to test and what to assert, concretely
- Merge duplicates — if multiple reviewers flagged the same gap, combine into one item with consensus count
- Severity is based on production risk, not how many reviewers mentioned it
- A finding goes in exactly one section. Red = no tests. Orange = tests miss scenarios. Yellow = tests exist but are weak. Green = nice-to-have.

After outputting, ask the user if they want to start working on any of the items.
