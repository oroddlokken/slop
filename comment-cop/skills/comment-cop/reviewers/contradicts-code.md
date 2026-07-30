# Find Comments That Contradict the Code

Scan for in-source comments and docstrings that disagree with what the code actually does — whether they drifted over time or were wrong from birth. This is the most dangerous lens: a maintainer trusts the comment, and the comment lies. A stale comment is worse than no comment.

## What to Look For

### Docstring / signature drift
- A docstring documenting a parameter that no longer exists, or missing one that does
- Documented return type/shape that differs from what the function returns
- `:raises X:` for an exception the code no longer raises, or a raised exception the docstring omits
- A one-line summary describing an old behavior ("returns the first match") after the code changed ("returns all matches")

### Comment describes different logic than the code
- "// only runs when enabled" above code that runs unconditionally
- A comment claiming a default ("defaults to empty") that the code contradicts
- Off-by-one or boundary claims that don't match ("skips the header row" but the slice keeps it)
- A comment naming a value/threshold that differs from the literal in the code

### Behavioral guarantees that no longer hold
- "thread-safe" / "idempotent" / "no external calls" / "best-effort, never raises" comments contradicted by the code below them (a lock removed, a network call added, a bare `raise`)
- "resolved relative to the package, not CWD" when the path logic actually uses CWD
- Comments promising an invariant the code doesn't enforce

### Cross-reference lies
- "mirroring X" / "matching Y" where X and Y have since diverged
- A comment pointing at another module/function that was renamed or deleted

### Example code in docstrings that won't run
- Doctest-style examples with outdated function names, argument order, or output
- Usage snippets calling a signature that changed

## How to Scan

1. **Read every docstring against its signature.** Match documented params/returns/raises to the actual `def`. Any mismatch is a finding.
2. **For behavioral-claim comments** ("thread-safe", "never raises", "no I/O", "cached"), read the code and confirm the claim holds *right now*.
3. **Check every literal a comment cites** — a number, a default, a path, a name — against the code.
4. **Follow cross-references** ("see X", "matches Y", "mirrors Z") and confirm the target still exists and still matches.
5. **Trace example snippets** in docstrings against the current signature.
6. **Prioritize recently-changed files** (from git log) — that's where comments drift fastest.

## Report Findings

For each contradiction:

| Field | Content |
|-------|---------|
| **Location** | file:line of the comment/docstring |
| **Comment says** | The claim in the prose |
| **Code does** | What the code actually does |
| **Harm** | How a maintainer trusting the comment gets misled |
| **Suggestion** | Correct the prose to match the code (never change the code — that's out of scope) |

### Severity Guide

- **Critical**: The contradiction is on a safety-critical property (thread-safety, locking, security, money, data integrity) — trusting the comment causes a real bug.
- **High**: Docstring/comment materially misdescribes behavior, params, returns, or a default — a maintainer will be misled on an ordinary path.
- **Medium**: A stale cross-reference or an outdated example that a careful reader would catch but shouldn't have to.
- **Low**: Trivially stale wording where the intent is still clear.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | High | loader.py:42 | Docstring says "returns None on error"; code raises ValueError | Update docstring to document the raised ValueError |

## Rules

- **Verify before flagging.** Read the actual code path — do not flag a suspected contradiction you haven't confirmed against the code. A false contradiction claim is itself misleading.
- **Fix the prose, not the code.** Your suggestion always edits the comment to match reality. If you believe the *code* is wrong (the comment describes the correct intent), note it as "possible code bug — out of scope, see /codehealth" and do not propose a code change.
- **Distinguish aspiration from lie.** A `TODO: make this thread-safe` is not a contradiction (it's honest). "This is thread-safe" over non-thread-safe code is.
- **Owns in-source prose only.** Stale README/markdown belongs to `doc-drift`.
