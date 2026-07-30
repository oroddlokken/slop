# Find Comments That Restate the Code

Scan for comments that narrate what the code already says plainly. These add reading time and maintenance burden (two things to keep in sync) while adding zero information. The test: if deleting the comment loses nothing a competent reader couldn't get from the line below it, the comment is a restatement.

## What to Look For

### Line-level narration
- `# increment counter` above `counter += 1`
- `# loop over users` above `for user in users:`
- `# return the result` above `return result`
- `# set x to 5` above `x = 5`

### Docstrings that echo the signature
- `"""Get the user by id."""` on `def get_user_by_id(id):` — the name already said it
- Param docs that restate the type: `:param path: the path` / `:param count: an integer count`
- `"""Constructor."""` / `"""Initialize the object."""` on `__init__`

### Comments that translate code to English 1:1
- `# if the list is empty, return early` above `if not items: return`
- Restating a well-named function call in words: `# call the validator` above `validate(x)`

### Redundant type/name restatement
- `# string` next to a value already annotated `: str`
- A comment repeating a constant's obvious name: `MAX_RETRIES = 3  # maximum retries`

## How to Scan

1. **For each comment, cover the code below it and ask: could I reconstruct this comment from the code alone?** If yes, it's a restatement.
2. **Read docstring summaries against the function name.** If the summary is the name with spaces, flag it (unless it adds a real constraint — "…, raising if the id is unknown" earns its place).
3. **Check param docs** — do they add anything beyond the name and type annotation?
4. **Watch for the anti-pattern of one comment per line** — a strong signal of narration.
5. **Spare the why.** `# +1 because the API is 1-indexed` is NOT a restatement of `i + 1` — it explains the *why*. Only flag comments that add no reason, constraint, or context.

## Report Findings

For each restatement:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **The comment** | The restating prose |
| **Why redundant** | What in the code already conveys it |
| **Suggestion** | Delete it — or, if there's a hidden *why*, replace the restatement with that why |

### Severity Guide

- **Low**: Nearly all restatements — harmless clutter, delete when nearby.
- **Medium**: Only when restatements are *pervasive* (one per line across a module) — the density itself obscures the few comments that matter, and syncing them all on refactor is a real cost. Report as one systemic finding.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | Low | app.py:88 | `# increment i` above `i += 1` adds nothing | Delete |

## Rules

- **Default to delete, but check for a buried why first.** If a restatement is the only place a rationale *could* have lived, suggest replacing it with the actual why rather than deleting.
- **Group per-file narration** into one systemic finding rather than 30 rows.
- **A one-line comment is this lens's territory; multi-paragraph narrative is `rambling`.** Don't double-report — flag the short redundant ones, let rambling handle the essays.
- **Respect deliberate teaching comments.** In an intentionally pedagogical file (a tutorial, an example), line-by-line narration may be the point — calibrate and don't flag those.
