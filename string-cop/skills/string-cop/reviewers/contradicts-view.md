# Find Strings That Contradict the View

Scan for user-facing strings that disagree with what the application actually renders or does. This is the most dangerous lens and the only one that can issue a **Critical**: a user reads the sentence, believes it, and acts. A stale hint is worse than no hint, because a missing hint makes the user check and a wrong hint makes them stop checking.

The other nine lenses ask whether a string deserves the space. You ask whether it is true.

## What to Look For

### The claim about what the app touches

Strings promising the app does not read, write, send, or delete something. Every one of these is a testable claim about code:

- "No file has been deleted." above a restore control — does the decision path unlink anything, now or on the next clustering run?
- "values, secret or not, are never read" — does the loader parse them?
- "Nothing here ever writes to the repo" — does any handler on this screen write?
- "nothing is hidden" — does the view filter the collection before rendering?

These read as reassurance, and `reassurance` will flag them as unasked-for. You own the separate question: is it true? When it is false, your finding leads and theirs rides along.

### The claim about what is on the screen

- A count described one way and computed another: "12 of 40 ranked" where the denominator is the filtered set, not the archive. If the sentence says "of your photos" and the number counts the filtered pass, the sentence is wrong
- A count written into the copy instead of interpolated: "12 checks run on every commit" beside a registry that now holds thirteen. The literal was true when typed and nothing recomputes it, so suggest the count-free wording ("every check in the registry") rather than the corrected number — a corrected literal drifts again on the next addition
- "Sorted by date" above a query ordering by id
- "Showing the last 30 days" above a query with no date bound, or a different bound
- A legend naming a series the chart does not draw, or naming it differently
- A tooltip describing a column that was moved or renamed

### The claim about freshness or timing

- "Updated every 5 minutes" where the scheduler runs at a different interval, or where the value is cached longer than the refresh
- "Live" on a value sampled at a poll interval
- "as of {{ timestamp }}" where the timestamp is the request time, not the data time. This one is common and it silently converts a stale reading into a fresh-looking one

### The claim about a unit, a source, or a method

- A hint naming an equation, a half-life, a multiplier or a threshold that differs from the constant in the code
- kg vs lbs, kcal vs kJ, MiB vs MB — a unit in the hint that the formatter does not produce
- "from the API" where the value comes from cache, or "cached" where it is fetched per request

### The stale caveat

A caveat that was true when written and is not now. The tell: it describes a limitation the code no longer has, or names a mechanism that was replaced.

- "Sessions from before viewer tracking are excluded" after backfill landed
- "approximate — sampled at the poll interval" on a value now delivered by webhook
- "not yet implemented" next to a working control

### The instruction that no longer works

- A hint naming a key, a menu item, a page, or a flag that does not exist: "press Esc to close" on a dialog with no key handler
- A remediation string pointing at a screen that was renamed or removed: "Give it a kind on /settings" where the control moved
- A link's text describing a destination different from its `href`

### Contradiction between a string and its own control

- Button labelled "Save" that discards, "Archive" that deletes, "Preview" that commits
- A confirm dialog describing a narrower action than the handler performs ("remove from this list" where the handler removes globally)
- A checkbox label whose sense is inverted relative to the field it binds

This class is where Critical lives. Read the handler.

## What NOT to Flag

- **A hint you have not checked.** An unverified contradiction claim is itself a false statement, and it costs the user a wasted investigation. If you cannot reach the code that would confirm it, either read further or drop the finding. Never file a suspicion.
- **A string that is imprecise but not wrong.** "About 10%" where the constant is 0.096 is fine. "10%" where the constant is 0.5 is not.
- **Aspiration in an obviously labelled place.** A roadmap page or a "coming soon" screen is not lying about the present.
- **A caveat that is conservative.** A hint saying a number is approximate when it is in fact exact costs the user nothing; a hint saying it is exact when it is approximate costs them a decision. Only the second direction is a finding.
- **Rounding and formatting differences** the user cannot act on.
- **A claim that is true on this screen but false elsewhere.** That is `cross-screen`'s finding about drift, not yours.
- **Code you believe is buggy where the string describes the intended behaviour.** Note it as "possible view bug — out of scope, see /codehealth" and do not propose a code change.

## How to Scan

1. **Start from the render-truth anchor table** in the inventory. Those claims were pre-identified as testable; work them first.
2. **Grep the inventory for absolutes** — `never`, `always`, `no `, `nothing`, `only`, `all`, `every`, `cannot`, `guaranteed`, `permanently`, `immediately`. Each is a claim with a code path behind it.
3. **Grep for numbers and units** in strings, then find the corresponding constant or formatter. A hint naming `~6.6-day half-life` should sit near a constant that produces 6.6 days.
4. **For every count or total described in prose**, read the view that computes it and confirm the described set matches the computed set. Where the number is a literal rather than an interpolation, count the set it names in the source and propose the count-free replacement.
5. **For every button, confirm, and destructive control**, read its handler. Label against behaviour. This is where Critical findings come from.
6. **Check freshness claims against the scheduler, the cache TTL, and the query.**
7. **Follow every instruction string** — the key, the page, the flag, the menu item. Confirm the target exists.
8. **Prioritize recently-changed views** (`git log`). Strings drift when the code beneath them moves and nobody opened the template.

## Report Findings

For each contradiction:

| Field | Content |
|-------|---------|
| **Location** | file:line of the string |
| **Screen says** | The claim, quoted verbatim |
| **View does** | What the code actually does, with the file:line that proves it |
| **Cost to the user** | What a user who believes the string does wrong |
| **Suggestion** | The corrected string, written out. Never a code change |

### Severity Guide

- **Critical**: A user who believes the string loses data, sends something irrecoverable, or misreads a number they act on. False safety claims above destructive controls; inverted labels on destructive buttons.
- **High**: The string materially misdescribes scope, state, freshness, or method on an ordinary path. A user is misled but recovers.
- **Medium**: A stale caveat or a broken instruction — the user is confused and has to check for themselves.
- **Low**: Trivially stale wording where the correct reading is still obvious.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Screen says | View does | Suggestion |
|---|----------|-----------|-------------|-----------|------------|
| 1 | Critical | decisions.html:34 | "No file has been deleted." | `decisions.py:88` unlinks the original on restore | Replace with the truth: "Restoring clears the decision. The original file is removed." |
| 2 | High | rank.html:41 | "{{ counts.ranked }} of {{ counts.visible }} ranked" reads as the whole archive | `counts.visible` is the label-filtered pass | Name the set: "ranked in this filter" |
| 3 | Medium | stats.html:209 | "first seen by the periodic poll" | webhook path added; poll is now the fallback | Update to "first seen by webhook, or by the poll when the webhook is missed" |

## Rules

- **Verify before flagging. Every time.** Cite the file:line of the code that proves the contradiction. A finding without that citation is not a finding.
- **Fix the string, not the code.** Your suggestion always edits the copy to match reality. If you believe the *code* is wrong and the string describes the correct intent, say so and hand it to `/codehealth`.
- **Write the replacement.** "This is inaccurate" is half a finding. The corrected sentence is the other half.
- **Distinguish stale from false.** A caveat that over-warns is stale and Medium. A claim that under-warns is false and starts at High.
- **You outrank every other lens.** If a string is both false and wordy, the falsehood is the finding and the other lens's note is a clause inside yours. Never let a merged action point read as "shorten this" when the sentence is wrong — a shorter lie is still a lie.
- **Do not manufacture Criticals.** Critical means data loss or a number acted on. A wrong tooltip on a dashboard tile is High. If you cannot name the specific harm, it is not Critical.
