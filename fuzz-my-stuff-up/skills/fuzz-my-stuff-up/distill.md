## Distillation Algorithm

After all fuzzer agents complete, analyze the combined output:

1. Read through every finding from every fuzzer and classify by **impact** and **likelihood**:
   - **Critical impact + any likelihood** → Red (Exploitable Now)
   - **High impact + realistic likelihood** → Red or Orange (security issue → Red, product gap → Orange)
   - **Medium impact + unlikely trigger** → Yellow (Should Harden)
   - **Low impact or already partially mitigated** → Green (Consider)
   - **Implausible conditions, already fully mitigated, or not reproducible** → Noise (skip)

   **Severity → Tier mapping from agent output:**
   - Agent "Critical" → Red
   - Agent "High" → Red (if security/correctness) or Orange (if missing use case)
   - Agent "Medium" → Yellow
   - Agent "Low" → Green
   - Easy exploitability bumps a finding up one tier.

2. Cross-reference with code: confirm each finding by reading the exact file and line range cited. This ensures reported locations are accurate.
   - **Hallucinated findings**: If a finding doesn't exist at the reported file:line (wrong code, line doesn't exist, or different logic), discard it and note the count: "{N} findings discarded (reported code not found at referenced locations)."
   - **Zero findings from an agent** is a valid result — note it as "{fuzzer}: no issues found" so the user knows it ran successfully.

3. Deduplicate using the following algorithm:
   - **Pass 1 — File match**: Group findings that reference the same file and line range (within 10 lines). These are almost certainly the same issue seen from different attack angles.
   - **Pass 2 — Defense match**: Within the same module, merge findings that all point to the same missing defense (e.g., three fuzzers all finding that `parse_input()` has no validation — that's one fix, not three issues).
   - **Pass 3 — Systemic match**: Across different files, merge findings that describe the same systemic gap (e.g., "no input validation" flagged by empty-inputs, type-confusion, and malformed-input pointing at different endpoints — that's a pattern, not separate issues). Systemic issues are typically flagged by 3+ fuzzers from different angles. If only 1-2 agents flag it, keep findings separate unless the code path is identical.
   - After merging, mark cross-fuzzer consensus with "flagged by N/{total}" where {total} is the number of fuzzers run.
   - Extract the `## Findings Summary` table from each agent's output as the primary dedup input. If an agent's output lacks this table, extract findings from the prose and note reduced confidence.
   - **Conflict resolution**: When two fuzzers disagree on severity, use the higher severity. When they disagree on the fix, note both approaches.

4. Output as:

```
## Fuzz Results

**{total_findings} findings from {num_fuzzers} fuzzers, distilled to {distilled_count} action points.**

### Red — Exploitable Now
Issues where user-supplied input can cause security bypass, data loss, crash, or incorrect behavior.

1. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change} | Attack: `{fuzzer}` | Exploitability: {Easy/Medium/Hard}

### Orange — Missing Use Cases
Features a user could reasonably attempt that fail, produce wrong results, or error with unclear messages. These are product gaps, not bugs.

2. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change} | Attack: `{fuzzer}`

### Yellow — Should Harden
Real edge cases that could bite in production under realistic conditions.

3. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change} | Attack: `{fuzzer}`

### Green — Consider
Valid hardening opportunities worth adding but not urgent.

4. [ ] **{title}** — {one-line description}
   `{file_path}:{line}` — {what to change} | Attack: `{fuzzer}`

### Skipped
{count} findings were implausible, already mitigated, or noise — ignored.
{hallucinated_count} findings discarded (reported code not found at referenced locations).
```

**Exploitability levels** (for Red tier items):
- **Easy**: Normal user could trigger this accidentally
- **Medium**: Requires unusual but plausible input or timing
- **Hard**: Requires intentional adversarial action

### Attack Surface Summary

After the action points, add a brief **Attack Surface Summary** (5-8 lines):
- Which parts of the codebase are most exposed?
- What's the most dangerous attack path found?
- What systemic defense is missing (if any)?
- One-sentence overall assessment: how robust is this code against adversarial/unexpected input?

Rules for distilling:
- **Number items sequentially across all sections** (1, 2, 3... not restarting per section) so the user can reference them by number
- If dcat issues were found earlier, exclude action points that report the same file + line range as an existing dcat issue, or the same systemic gap in the same module
- Each item must have a file path — no vague suggestions
- Each item must note which fuzzer found it (or "flagged by N/{total}" if multiple)
- One line per fix — say what to change concretely
- Merge duplicates — if multiple fuzzers flagged the same thing, combine into one item with consensus count
- Severity is based on exploitability and impact, not how many fuzzers mentioned it
- A finding goes in exactly one section. If it's exploitable, Red trumps Orange. Orange is for non-exploitable product gaps only.

After outputting, ask the user if they want to start working on any of the items.
