## Distillation Algorithm

After all agents complete, analyze the combined output:

1. Read through every finding from every agent and classify:
   - **Bug risk**: Could cause incorrect behavior, data loss, or security issues
   - **Maintainability**: Makes code harder to understand, change, or debug
   - **Technical debt**: Functional but accumulating cost over time
   - **Hygiene**: Minor cleanliness issues worth fixing when nearby
   - **Noise**: Subjective preference or edge case not worth addressing — skip

2. Cross-reference with code: read only files explicitly referenced in findings (one per finding) to confirm line accuracy. Do not scan for additional patterns during distillation.

3. Deduplicate using the following algorithm:
   - **Pass 1 — File match**: Group findings that reference the same file and line range (within 10 lines). These are almost certainly the same issue.
   - **Pass 2 — Pattern match**: Within the same file, merge findings that describe the same type of problem (e.g., two agents both flagging "hardcoded URL" or "missing error handling" in the same module).
   - **Pass 3 — Semantic match**: Across different files, merge findings that describe the same systemic issue (e.g., "no error handling on HTTP calls" flagged by multiple agents pointing at different files).
   - After merging, mark cross-reviewer consensus with "flagged by N/{total}" where {total} is the number of reviewers run.
   - Extract the `## Findings Summary` table from each agent's output as the primary dedup input. Normalize across different table schemas by extracting the common columns: Severity, File:Line, Issue, Suggestion.
   - **Conflict resolution**: When two lenses disagree on the same code (e.g., simplify-code says "remove abstraction" but extract-logic says "extract more"), use this hierarchy: security > correctness > maintainability > style. Flag the disagreement explicitly: `[CONFLICT] {lens1} recommends X, {lens2} recommends Y — resolved by hierarchy.`

4. Output as:

```
## Code Health Results

### Red — Fix Now
Issues that affect correctness, security, or data integrity.

1. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change} | Lens: `{reviewer}`

### Yellow — Should Address
Real quality issues that affect maintainability or reliability.

2. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change} | Lens: `{reviewer}`

### Green — Consider
Valid improvements worth addressing but not urgent.

3. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change} | Lens: `{reviewer}`

### Skipped
{count} findings were subjective preference or noise — ignored.
```

Rules for distilling:
- **Number items sequentially across all sections** (1, 2, 3... not restarting per section) so the user can reference them by number
- If dcat issues were found earlier, exclude any action point that overlaps with an existing tracked issue
- Each item must have a file path — no vague suggestions
- Each item must note which lens found it
- One line per fix — say what to change concretely
- No duplicates — if multiple reviewers flagged the same thing, merge into one item with consensus count
- Severity is based on code impact, not how many reviewers mentioned it

After outputting, ask the user if they want to start working on any of the items.
