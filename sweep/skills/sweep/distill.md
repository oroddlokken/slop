## Distillation Algorithm

After all agents complete, analyze the combined output:

1. Read through every finding from every agent and classify:
   - **Critical defect**: Broken functionality, WCAG A violation, security issue
   - **Quality issue**: Poor UX, inconsistency, missing states, bad contrast
   - **Design debt**: Suboptimal but functional — worth improving
   - **Polish opportunity**: Small detail that separates good from great
   - **Noise**: Subjective preference or edge case not worth addressing — skip

   **Severity → Tier mapping from agent output:**
   - Agent "Critical" → Red
   - Agent "High" → Red (if accessibility/correctness) or Yellow (if design quality)
   - Agent "Medium" → Yellow
   - Agent "Low" → Green

2. Cross-reference with code: read referenced files to confirm issues exist

3. Deduplicate using the following algorithm:
   - **Pass 1 — File match**: Group findings that reference the same file and line range (within 10 lines). These are almost certainly the same issue.
   - **Pass 2 — Pattern match**: Within the same file, merge findings that share an issue category (e.g., two agents both flagging "missing hover state" in the same component).
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
- Include style-only feedback only when it affects usability or consistency

After outputting, ask the user if they want to start working on any of the items (or run the suggested `/skill` on specific items).
