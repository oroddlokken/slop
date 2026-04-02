## Distillation Algorithm

After all agents complete, analyze the combined output.

### Step 1: Classify

1. Read through every finding from every agent and classify:
   - **Security**: SQL injection, privilege escalation, credential exposure
   - **Data integrity**: Corruption risk, orphaned records, constraint gaps, transaction gaps
   - **Performance**: N+1, missing indexes, full table scans, connection issues
   - **Maintainability**: Scattered queries, schema drift, migration hazards
   - **Hygiene**: Minor ORM inefficiencies, naming, cleanup opportunities — skip if trivial

   **Severity -> Tier mapping from agent output:**
   - Agent "Critical" -> Red (if security/data loss/corruption) or Orange (if performance/maintainability only)
   - Agent "High" -> Red (if security/data integrity) or Orange (if performance at scale)
   - Agent "Medium" -> Yellow
   - Agent "Low" -> Green

### Step 2: Validate

2. Cross-reference with code: for each finding, read the specific file and line range mentioned to confirm line accuracy. Read only files already mentioned in findings — do not perform additional searches or pattern discovery during distillation.

2a. **Validate high-severity findings**: For each Red finding, verify:
   - N+1: Is the collection actually unbounded? (Check for LIMIT/pagination)
   - Index-coverage: Is the table queried on a hot path? (Check for admin-only, test-only)
   - Transaction-gaps: Does the framework auto-wrap transactions? (Check for ATOMIC_REQUESTS, etc.)
   Downgrade clearly false positives to Orange/Yellow.

### Step 3: Deduplicate

3. Deduplicate using the following algorithm:
   - **Pass 1 — File match**: Group findings that reference the same file and line range (within 10 lines). These are almost certainly the same issue.
   - **Pass 2 — Pattern match**: Within the same file, merge findings that describe the same type of problem (e.g., two agents both flagging "string interpolation in SQL" or "missing transaction" in the same module).
   - **Pass 3 — Systemic match**: Across different files, merge findings that describe the same systemic issue (e.g., "no parameterized queries" flagged by injection and query-scatter pointing at different files — that's a codebase-wide pattern).
   - After merging, mark cross-reviewer consensus with "flagged by N/{total}" where {total} is the number of reviewers run.
   - Extract the `## Findings Summary` table from each agent's output as the primary dedup input. Normalize across different table schemas by extracting the common columns: Severity, File:Line, Issue, Suggestion.
   - **Conflict resolution**: When two lenses disagree on the same code (e.g., raw-perf says "rewrite as raw SQL for performance" but query-scatter says "move to ORM for maintainability"), use this hierarchy: security > data integrity > performance > maintainability > style. Flag the disagreement explicitly: `[CONFLICT] {lens1} recommends X, {lens2} recommends Y — resolved by hierarchy.`

### Step 4: Output

4. Output as:

```
## SQL Health Results

### Red — Fix Now
Security vulnerabilities, data corruption risks, or integrity gaps that can cause data loss.

1. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change} | Lens: `{reviewer}`

### Orange — Should Address
Performance issues that degrade at scale, or schema/migration problems that accumulate risk.

2. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change} | Lens: `{reviewer}`

### Yellow — Improve
Real quality issues affecting maintainability, query organization, or minor performance.

3. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change} | Lens: `{reviewer}`

### Green — Consider
Valid improvements worth addressing but not urgent.

4. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change} | Lens: `{reviewer}`

### Skipped
{count} findings were subjective preference or noise — ignored.
```

### Database Health Summary

After the action points, add a brief **Database Health Summary** (5-8 lines):
- Which database stack is in use (ORM, driver, migration tool)?
- What's the most dangerous finding?
- Are there systemic patterns (e.g., "no parameterized queries anywhere", "no transaction discipline")?
- Is the schema well-maintained (migrations match models, indexes exist for queries)?
- One-sentence overall assessment: how healthy is this codebase's database layer?

Rules for distilling:
- **Number items sequentially across all sections** (1, 2, 3... not restarting per section) so the user can reference them by number
- If dcat issues were found earlier, exclude any action point that overlaps with an existing tracked issue
- Each item must have a file path — no vague suggestions
- Each item must note which lens found it
- One line per fix — say what to change concretely
- No duplicates — if multiple reviewers flagged the same thing, merge into one item with consensus count
- Severity is based on database impact (security > data integrity > performance > maintainability), not how many reviewers mentioned it

After outputting, ask the user if they want to start working on any of the items.
