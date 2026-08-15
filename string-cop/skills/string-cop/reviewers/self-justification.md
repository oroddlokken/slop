# Find Design Rationale and Self-Praise on the Page

Scan for strings where the application explains why it was built this way, or tells the user how good it is. Both are the developer's voice leaking through the interface. The design rationale belongs in a commit message or an ADR; the self-praise belongs nowhere.

The user is not evaluating your architecture. They are trying to finish a task. A paragraph arguing for a design decision asks them to adjudicate a debate they did not know was happening, and the argument is unanswerable — there is no control on the page for disagreeing with it.

## What to Look For

### The design argument

A paragraph justifying a choice the user did not question, usually opening with a rule and ending with a principle.

- "Two tools computing the same finding is how they end up disagreeing." (why this page does not check something)
- "Not checked here — the deploy tool already owns it."
- "The editor is withheld on this screen because edits made here would race the file on disk."
- "We compute this server-side so the number is consistent for everyone."
- "Kept here for backwards compatibility." / "Kept here until the new flow ships."

The tell: a causal connective (`because`, `so`, `rather than`, `which is why`) joining a product decision to a principle. Nothing in the sentence tells the user what to do.

`Kept here` is the compressed form and gets the same treatment. It argues for the control's continued existence, which the user did not challenge and cannot change. Where the answer is "then don't use it", the fix is a limit — "Read-only; edit on /settings" — not the history of why it survived.

### The boundary essay

A close relative: prose explaining what this screen deliberately does *not* cover, and why that split exists.

- "Dependency freshness is not reported here; that is what /drift is for."
- "This view intentionally excludes archived items to keep the list actionable."

A pointer is useful: "Archived items are on /archive." The essay around it is not. Cut to the pointer and the link.

### Self-praise

The app complimenting itself, in the first person or the third.

- "nothing else reports that"
- "the actionable subset"
- "our smart ranking algorithm"
- "a comprehensive view of your data"
- "the fastest way to find drift"

Comparative claims against unnamed alternatives ("nothing else", "unlike other tools") are the sharpest version: unverifiable and irrelevant to the person already using this tool.

### Narrative framing of a finding

Prose that dramatizes what the screen already lists.

- "Find out where the source went — the fleet is running code nobody has."
- "Classified, committed, remoted and accounted for."
- "Your history, finally in one place."

These read as headings but carry no data. A user scanning for a repo name gets a sentence about the fleet's existential state instead.

### Meta-commentary on the interface

- "We've kept this page deliberately simple."
- "Only the fields that matter are shown."
- "This layout groups related settings together."

The layout is visible. Describing it is redundant, and describing the *intent* behind it is rationale.

### The apology for a limitation, argued

- "We don't support bulk edit here because it would make the undo model ambiguous."

The user needs "Bulk edit is not available." — and ideally where it is available. The reasoning is for the issue tracker.

## What NOT to Flag

- **A constraint the user must work within.** "Edits here apply on the next sync" is a fact about consequence and timing. It survives even though it explains a mechanism, because the user's next action depends on it.
- **A pointer to where the thing lives.** "Set the kind on /settings" is remediation, not rationale. Keep it.
- **A stated limit or scope with a boundary the user can act on.** "Only repos with a `.git` directory appear here" tells a user why theirs is missing and what to do. That is not a boundary essay; it is an explanation of an absence the user is looking at.
- **A source attribution.** "Sourced from the GitHub API" tells the user how much to trust the value. Keep it, and hand any wordiness to `llm-slop`.
- **Onboarding and marketing surfaces.** A landing page, a pricing page, or a first-run tour is *supposed* to make a case. Judge those by whether the claim is specific, not by whether it praises. Flag "powerful and flexible"; leave "tracks 40 repos across 3 hosts".
- **Legal, licensing, and attribution text.**
- **Rationale that is also false.** `contradicts-view` owns it.

The test: **does the sentence change what the user does next?** Rationale never does. A limit, a pointer, a consequence, or a source always can.

## How to Scan

1. **Grep the inventory for causal connectives** at sentence scale: `because`, `so that`, `which is why`, `rather than`, `the reason`, `by design`, `intentionally`, `deliberately`, `we chose`, `we decided`, `kept here`, `left in place`.
2. **Grep for comparative and promotional claims**: `nothing else`, `unlike`, `the only`, `best`, `smart`, `powerful`, `comprehensive`, `actionable`, `seamless`, `simply the`.
3. **Grep for first-person product voice**: `we `, `our `, `us `. In an interface, first person is almost always the developer explaining themselves.
4. **For each long paragraph in the inventory, delete every clause that does not change the user's next action.** What remains is the proposed replacement. Frequently it is nothing.
5. **Check headings and lead paragraphs** — narrative framing concentrates at the top of a screen, where it is most expensive.
6. **Separate rationale from limit.** For every "we do X because Y", ask whether Y contains a boundary the user hits. If it does, the fix is to state the boundary and cut the argument.
7. **Group by screen.** A screen with four rationale paragraphs has a voice problem, not four string problems.

## Report Findings

For each string:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Kind** | Design argument / boundary essay / self-praise / narrative framing / meta-commentary |
| **The claim** | Quote the string |
| **What the user does with it** | The action it enables, or "nothing" |
| **Suggestion** | The surviving fact as a replacement line, or "delete" |

### Severity Guide

- **High**: Rationale that displaces the instruction a stuck user needs — an argument for a design where the next step should be. A user reads the paragraph, learns why they cannot do the thing, and still does not know where to do it.
- **Medium**: The standard case. A rationale paragraph or a boundary essay on an ordinary screen, or self-praise in body copy.
- **Low**: A single self-congratulatory adjective, a short meta-comment on the layout.
- Never **Critical**: rationale wastes attention. If it also misstates behaviour, that is `contradicts-view`.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | Medium | drift.html:110-114 | Whole paragraph argues why this page skips a check, ending "Two tools computing the same finding is how they end up disagreeing" | Cut to the pointer: "Checked by the deploy tool." Drop the argument |
| 2 | Medium | deps.html:24 | "nothing else reports that" — a comparative claim against unnamed tools | Delete the clause; keep the sentence describing what the panel lists |
| 3 | Low | deps.html:108 | "the actionable subset" — self-assessment presented as a label | Name the filter instead: "pins behind upstream HEAD" |

## Rules

- **Does it change what the user does next?** Run that test in every finding and write the answer down.
- **Keep the limit, cut the argument.** When rationale contains a boundary the user can hit, the replacement states the boundary in one line. Never propose deleting both.
- **A pointer beats an explanation.** When a screen deliberately omits something, the fix is a link, not a paragraph about ownership boundaries.
- **Do not flag specificity as praise.** "Tracks 40 repos" is a fact even on a marketing page. "Powerful tracking" is not. The line is whether a number, a name, or a source appears.
- **Batch per screen.** Four rationale paragraphs on one screen is one action point.
- **Write your findings in the register you are asking for.** A report full of argument about argument is self-defeating. Name the string, name the surviving fact, stop.
