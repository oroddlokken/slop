# Find Missing Rationale (the absent why)

Scan for code that *needs* a comment and doesn't have one. This is the inverse of the other lenses: instead of too much prose, too little where it counts. The best comments explain *why*, not *what* — and the highest-value missing comment is the one that would have stopped a future maintainer from "cleaning up" a deliberate quirk and reintroducing a bug.

## What to Look For

### Magic numbers and literals with no source
- A threshold, timeout, retry count, buffer size, or multiplier with no explanation of where it came from (`sleep(1.3)`, `if score > 0.87`, `chunk = data[:4096]`)
- A "walkback up to 10 days" style constant with no note on why 10
- Regexes with no example of what they match

### Non-obvious workarounds
- Code that looks wrong or redundant but is deliberate — a defensive re-check, a sleep, an ordering swap, a `# noqa`-worthy construct — with nothing saying why it must stay
- Compatibility shims for a specific dependency/OS/version bug with no reference to the bug
- Empty except / swallowed error where the *reason* it's safe to swallow is unstated

### Ordering and coupling constraints
- "This must run before X" relationships enforced by code position but never stated — prime candidate for a refactor to break them
- Mutations whose order matters, initialization that must precede use, with no warning

### Surprising choices
- Why *this* data structure / algorithm / library over the obvious one
- Why a value is cast, coerced, or copied defensively
- Why a seemingly redundant condition exists (it guards a real edge case)

### Deliberate deviations from convention
- Code that intentionally breaks the project's own pattern, with no note explaining the exception — a maintainer will "fix" it back

## How to Scan

1. **Hunt magic literals.** Grep for numeric/string literals in logic (comparisons, slices, timeouts, retries). For each, ask: is the *reason for this exact value* obvious? If not, and there's no comment, flag it.
2. **Find code that invites deletion.** Anything that looks removable but isn't — a re-check, a sleep, a copy, an odd order — needs a why. If a reader might delete it and break something, the missing why is a finding.
3. **Check swallowed errors.** Every bare/broad except or ignored return: is it stated *why* ignoring is correct?
4. **Look for ordering comments' absence** — sequential statements where reordering would break correctness.
5. **Compare against the house style.** Where code deviates from the codebase's own convention with no explanation, flag it.
6. **Do NOT demand a why for self-evident code.** A plain `for`, a clear guard, a well-named call needs no comment. Only flag genuinely non-obvious decisions — over-flagging here just recreates the noise problem.

## Report Findings

For each missing rationale:

| Field | Content |
|-------|---------|
| **Location** | file:line of the unexplained code |
| **What's unexplained** | The literal / workaround / ordering / deviation |
| **Risk if untouched** | How a maintainer gets burned (deletes it, changes the value, reorders) |
| **Suggestion** | The one-line why to add (state the fact needed, phrased as rationale not narration) |

### Severity Guide

- **High**: A non-obvious construct whose deletion or modification would reintroduce a bug, with nothing warning the reader (deliberate quirk, compatibility shim, ordering constraint).
- **Medium**: A magic number / threshold in important logic with no provenance — maintainers can't safely tune it.
- **Low**: A minor surprising choice where the cost of guessing wrong is small.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | High | retry.py:31 | `time.sleep(2)` between attempts, no note; a maintainer may remove it | Add: "# back off 2s — upstream returns 429 without it" |

## Rules

- **Suggest the actual why, not "add a comment."** If you can infer the rationale from the code/context, write the one-liner. If you genuinely cannot infer it, say "why unknown — ask the author" so the user knows to supply it.
- **Prefer why over what.** The comment you propose should explain the reason, not narrate the mechanism (that would just create `restates-code` clutter).
- **Be conservative.** The bar is "a competent maintainer would plausibly get this wrong without a note." Do not flag obvious code — a flood of trivial "add a comment" findings is itself noise.
- **This lens finds absence, not presence.** If a why-comment exists but is bad, that's another lens (rambling/contradicts-code). Here the finding is that nothing is there.
