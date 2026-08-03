# Find Repetition Within One Screen

Scan for a screen saying the same thing twice: a tail restating its own head, two paragraphs teaching one lesson, a heading echoed by the sentence under it, a state announced in two places at once.

You own repetition *inside* a single screen. `cross-screen` owns the same fact copied to several screens. If the two strings render together, they are yours.

The cost is specific. A user reading the second copy is not learning; they are checking whether it differs from the first. Two sentences that say the same thing in different words are worse than one, because the difference in wording implies a difference in meaning that does not exist.

## What to Look For

### The tail that restates the head

One sentence, two halves, joined by `so`, `which means`, `in other words`, or a semicolon — where the second half is the first half again.

- "…so day-to-day noise is filtered out and real change shows through." (the two clauses after "so" are one idea)
- "The deficit is 500 kcal, which means you are eating 500 kcal below your budget."
- "This is read-only; you cannot edit it here."

Cut the weaker half. Usually the second.

### The lesson taught twice on one screen

Two separate paragraphs, often in different branches or different panels, making the same point in different words. A profile page that explains the Mifflin-versus-Katch tradeoff in the `{% if %}` arm and again in the `{% else %}` arm has one lesson in two places — and only one of them ever renders, so check whether they are alternatives before flagging.

The real finding is when both render: a lead paragraph and a tooltip on the same metric, both explaining the same thing.

### Heading echoed by its own body

- Heading "Git pins" / body "Dependencies pinned to an exact commit."  — this one is fine; the body defines the heading
- Heading "Ignored" / body "These are the items you have ignored."  — this one is not; the body restates the heading

The distinction: does the body add a definition, a count, a source, or a consequence? Or does it re-inflect the same words?

### The same state announced twice

- "Everything is ranked." next to "Nothing left to rank."
- An empty table with both a "No results" row and a "Nothing to show" paragraph above it
- A success flash plus a static "Saved!" line on the same render

Two announcements of one state make the user look for the difference.

### Count restated in prose

- A badge showing `14` and a sentence reading "There are 14 ignored items."
- "Showing 20 of 340" above a paginator that says "20 of 340"

### The label repeated in the value

- Field "Weight" showing "Weight: 82 kg"
- Column "Status" with cells reading "Status: active"

### Bilingual restatement

The same instruction in a formal register and then a plain one, because the writer was not sure which landed. Pick the plain one.

## What NOT to Flag

- **Alternative branches.** `{% if %}` and `{% else %}` copy never renders together. Read the condition before flagging. Two arms saying similar things is normal and correct; flagging it is a false positive that makes the report look careless.
- **A heading and a body that defines it.** Restating is bad; defining is good. "Git pins" / "Dependencies pinned to an exact commit" adds the definition.
- **An `aria-label` duplicating visible text.** That is its job. Screen-reader text is not a second copy for your purposes.
- **A summary followed by detail.** A total at the top and rows below is not repetition. A sentence saying "the total is below" is (`widget-narration` owns that one).
- **Legally or safety-required double confirmation**, and destructive-action copy that intentionally states the consequence twice — once in the warning, once on the confirm button.
- **A repeated *value* where the second instance has different precision or a different unit.** "82.4 kg" and "182 lb" is a conversion, not a copy.
- **Repetition across screens.** Hand it to `cross-screen`.

The test: **if the two strings render together, does deleting one lose a fact?** If no, the deletion is the finding. Name which one to keep.

## How to Scan

1. **Work screen by screen**, using the inventory's screen grouping. This lens is meaningless outside a single render.
2. **Within each screen, look for repeated content words** — the same noun phrase in two strings. Grep the distinctive term (`half-life`, `lean mass`, `ignored`) and count hits per screen.
3. **Check branch conditions before flagging any pair.** If they are the arms of one `{% if %}`, drop it.
4. **Read each long string for internal repetition** — the tail-restates-head shape lives inside one sentence and no cross-string comparison will find it.
5. **Compare every heading to the first sentence under it.**
6. **Compare every number rendered as a badge or metric to the prose near it.**
7. **List the empty and success states per screen** and check for doubled announcements.
8. **Prefer merging over deleting.** When two strings each carry half a fact, the finding is the merged sentence, written out.

## Report Findings

For each redundancy:

| Field | Content |
|-------|---------|
| **Location** | Both file:lines |
| **Renders together?** | Yes / No (name the branch if no — and then drop the finding) |
| **The repetition** | Both strings, quoted |
| **Unique to each** | The fact only the first carries; the fact only the second carries. Often one side has none |
| **Suggestion** | Which to keep, verbatim — or the merged replacement line |

### Severity Guide

- **Medium**: A whole paragraph duplicated on one screen, or a lesson taught twice in the primary reading path. The user reads both and gains nothing from the second.
- **Low**: A tail restating a head, a heading echoed by its body, a count in prose next to a badge.
- Never **High/Critical**: repetition wastes attention. If the two copies *disagree*, that is `contradicts-view` and it is serious — route it there.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | Medium | profile.html:52 and :54 | Both paragraphs teach the Mifflin-vs-Katch tradeoff; both render when body fat is set | Keep :52 cut to the method name and source; delete :54 |
| 2 | Low | calories.html:70 | Clause after "so" restates the clause before it | Cut to the first clause |
| 3 | Low | rank.html:41 | "Everything is ranked." and "Nothing left to rank." announce one state | Keep "Nothing left to rank." — it names the queue the user was working |

## Rules

- **Confirm both strings render together.** A finding on two `{% if %}` arms is a false positive and the most likely mistake on this lens. State the branch check in every finding.
- **Name which copy survives, verbatim.** "These are redundant" is not an action; "keep the first, delete the second" is.
- **Merge when each half carries something.** Write the merged line out.
- **Disagreement is not redundancy.** If the two copies say different things, you have found a `contradicts-view` finding — say so and route it.
- **Do not count a definition as a restatement.** A heading plus its definition is a working pattern.
- **One pair, one finding.** Do not file the same duplication twice from each side.
