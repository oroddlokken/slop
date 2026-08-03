# Find Empty States and Errors the User Cannot Act On

Scan the two screens where the user is already stuck: nothing to show, and something went wrong. Every string on those paths is yours first, whatever other lens also matches it.

These strings are written last, tested least, and read at the worst moment. A user hits an empty state having just arrived, or an error having just failed. In both cases they need the same three things and usually get none of them: **where**, **why**, and **what now**.

The default failures are opposites. Empty states are too cheerful and name no next action. Errors open on a mood — an apology, an exclamation, a shrug — and bury the location, the cause, and the fix, or omit them entirely.

## What to Look For

### The empty state that names no next action

- "Nothing here yet."
- "No results."
- "You have no items."
- "Everything is ranked." at the end of a queue with no link onward

Each is accurate and useless. The user knows the list is empty; they are looking at it. What they do not know is how something gets into it.

The target shape: **what this list holds, and the one action that puts something in it.** "No weigh-ins yet. Log one from the Weight page." — with the page as a link.

### The empty state that cannot distinguish empty from filtered

The worst version, because the user's conclusion is wrong. "Nothing to show" under an active filter reads as "you have no data" when it means "no data matches these chips". If the screen has filters, the empty state must say which case it is.

### The cheerful empty state

- "All caught up! 🎉"
- "Nice work, nothing left to do!"
- "You're all set."

Celebration in place of information. If the state is genuinely terminal and there is nothing to do, one short line is fine — but it should still say what would appear here.

### The error that opens on a mood

- "Oops! Something went wrong."
- "Sorry, an error occurred."
- "Uh oh."
- "We couldn't complete your request. Please try again later."

The apology consumes the whole string. `Please try again later` is the tell for an error whose author did not know what the user should do — and telling a user to try later when the cause is a malformed input is a false instruction that wastes their afternoon.

### The error that names no location

An error string that does not say *what* failed: which field, which file, which record, which service. "Validation failed" on a twelve-field form makes the user check twelve fields.

### The error that names no cause

"Could not save." Why not — permission, conflict, a bad value, the disk? Each has a different fix.

### The error that names no fix

The cause is there, the remedy is not. "This name is already taken." — and? "The file is too large." — what is the limit?

The model to aim at: a short label naming the condition, and a short imperative naming the remedy. "Uncommitted changes. Commit or stash." Two fragments, four words of remedy, nothing else.

### The raw internal message shown to a user

- A stack trace, an exception class name, a SQL error, an HTTP status with no gloss
- `KeyError: 'user_id'` rendered on a page
- A message written for a log, shown on a screen: "failed to reconcile state for entity"

### Error text that blames the user

- "You entered an invalid value."
- "You must fill in all fields."

Name the field and the constraint instead. The second person plus a failure verb reads as an accusation and it is never necessary.

### The unhandled state with no string at all

An empty table with no empty state, a failed fetch with a blank panel, a `{% else %}` that renders nothing. Note it — a missing string is a finding on this lens even though there is no string to quote.

## What NOT to Flag

- **A one-word empty cell in a dense table.** A dash in a cell is correct; a paragraph in every empty cell is not.
- **An error that genuinely has one honest remedy of "retry".** Transient network failures exist. The finding is only when retry is offered as a substitute for diagnosis. If the string names the service and the transience, it is doing its job.
- **A short, plain empty state on a screen where the next action is a visible button.** "No items yet." above a large "Add item" button is complete. The action is on the screen.
- **Deliberately vague authentication errors.** "That username or password is wrong" is intentionally non-specific for security. Never propose narrowing it.
- **Error text constrained by a framework's format** where the app cannot supply the wording. Note the constraint rather than proposing an impossible fix.
- **Terse strings in an expert tool.** A CLI-adjacent admin panel may correctly say "409 conflict". Calibrate to the app's audience.
- **An error that is simply worded badly but is complete.** Hand register problems to `llm-slop`; you own missing information.

The test, for every string on these two paths: **can the user name their next action after reading it?** If not, say which of where/why/what-now is missing.

## How to Scan

1. **Enumerate every empty state.** Walk the inventory for `{% if not %}`, `{% else %}`, `|length == 0`, `is empty`, `{% for %}...{% empty %}` branches, and any string containing `no `, `nothing`, `empty`, `none`, `yet`.
2. **Enumerate every error surface**: error templates, flash and message calls, validation messages, `abort()`/`raise` text that renders, HTTP error pages, form field errors, toast failures.
3. **For each, score three fields: where, why, what now.** Write the score into the finding. A string missing all three is High.
4. **For every empty state on a screen with filters, check whether the string distinguishes filtered from empty.** This is the highest-value check in the lens.
5. **Check that the proposed next action exists** and that the screen can link to it. Do not propose an action the app does not offer.
6. **Look for the missing state** — branches that render nothing. Grep for `{% else %}` followed immediately by a close tag.
7. **Compare all empty states to each other and all errors to each other.** Wildly inconsistent shapes across the app is one finding; hand the consistency angle to `cross-screen` and keep the per-string gaps.
8. **Check whether any internal message escapes to a screen.** Grep for exception class names and log-register verbs in the inventory.

## Report Findings

For each string:

| Field | Content |
|-------|---------|
| **Location** | file:line, or the branch with no string |
| **Path** | Empty state / error / validation / missing state |
| **The string** | Quoted, or "none rendered" |
| **Missing** | Which of where / why / what now |
| **Suggestion** | The full replacement string, written out, with the link target named |

### Severity Guide

- **High**: An error that leaves a user with no path forward — no location, no cause, no fix, and no honest retry. Or an empty state under an active filter that reads as "you have no data", leading the user to a wrong conclusion about their own account. Or a raw internal message shown to a user.
- **Medium**: An empty state naming no next action on a screen where the action is not visible; an error naming the cause but no remedy.
- **Low**: A cheerful terminal state, a missing article, an apology that could be cut but where the information is complete.
- Never **Critical**: if the error text asserts something false about what happened, route it to `contradicts-view`.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Missing | Suggestion |
|---|----------|-----------|---------|------------|
| 1 | High | rank.html:44 | what now — under an active label filter, "Nothing left to rank." reads as "nothing left at all" | "Nothing left under these labels. Clear the filter to see the rest." |
| 2 | High | error.html:18 | where, why, what now — "Something went wrong." is the whole page | Render the failing operation and the cause; add "Go back" with the referring route |
| 3 | Medium | index.html:40 | what now — "No projects yet." with no route to add one | "No projects yet. Add one on Settings." |

## Rules

- **Score where/why/what-now in every finding.** That triple is the lens. A finding that does not say which is missing is an opinion about tone.
- **Write the full replacement string.** These are the strings most worth writing out, because the user is stuck when they read them.
- **Name the link target and confirm it exists.** A next action pointing at a route the app does not have is worse than no next action.
- **Filtered versus empty is the check to run first.** It is the one that changes what the user believes about their own data.
- **Never propose narrowing an auth error.** Vagueness there is deliberate.
- **Do not add cheer.** The fix for a bad empty state is information, not friendliness. Exclamation marks and emoji are not remedies.
- **A missing string is a finding.** Report branches that render nothing, with the branch location.
- **You own these two paths first.** When another lens also matches a string on an empty or error path, yours leads.
