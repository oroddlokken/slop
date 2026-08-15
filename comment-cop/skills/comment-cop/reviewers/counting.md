# Find Counts and Positional References That Rot

Scan for prose that pins a number, or a position in a list, to a set the prose does not own — files in a directory, rows in the table below, branches in a function, steps in a procedure, entries in a registry. The number is right the day it is written and wrong the moment the set changes, and nothing fails when it does: no test covers it, no linter reads it, and the reader who trusts it stops looking once they have found the count they were promised.

This lens is the inverse of a drift check. It does not ask whether the number is wrong today. It asks whether the sentence needed a number at all — because a corrected count drifts again on the next addition, and a count-free sentence cannot.

## What to Look For

### Counts of a set that lives elsewhere
- "All 10 lenses", "the seven checks", "supports 4 output formats" beside a directory, a registry or a parser you can list
- In code comments and docstrings: "one of the two callers", "the three retry paths below", "both of the guards in this module"
- An intro paragraph's count contradicting the table under it, because the table grew and the paragraph did not

### Counts of a list the reader can already see
- A heading or lead-in that numbers the list directly beneath it: "Two mechanisms, both measured on `pulse`:", "Five steps that no playbook performs:". The list carries its own length; the number adds nothing and has to be maintained. Inserting one item makes the sentence a lie.

### Positional references into a list
- "Step 5 of the root protocol", "see item 3 above", "the second branch below", ":returns: the first of the four fields"
- These point at a *position*, not a thing. Insert a step anywhere earlier and every later reference is silently off by one. Renumbering is invisible work that nobody is prompted to do.

### Arithmetic and multiples asserted about the code
- "roughly three times the necessary number of steps", "which brings the total to 12 tasks", "half the callers do X"
- A ratio compounds the problem: it goes stale when *either* side moves.

### Numbers that are the point — do not flag
- A limit, quota, timeout, retry budget, buffer size, protocol constant, version requirement, port
- A measurement with the run and date attached ("`ok=100 changed=0` on `juice`, 2026-08-11") — that is evidence, not a description of a set
- A benchmark result, a price, a rate, an off-by-one boundary being explained
- Verify these against the constant or the recorded run and cite the source; do not delete them.

## How to Scan

1. **Grep the prose layer for numerals and number words**: `\b\d+\b` and `\b(one|two|three|four|five|six|seven|eight|nine|ten|dozen|both|several)\b` across comments, docstrings, `README*` and `docs/**/*.md`.
2. **For each hit, name the set it mirrors.** Then list that set for real — glob the directory, count the table rows, read the parser or the registry, grep the callers. A count you cannot tie to a set is usually a limit; leave it.
3. **Check every ordinal and positional pointer** — "step N", "the first/second X", "item N above", "the three listed below" — against the list it points into. Record that nothing enforces the link.
4. **Read the sentence immediately above every list**, in docs and in block comments alike. A lead-in that counts its own list is the cheapest finding in this lens and the most common.
5. **Write the count-free phrasing as the suggestion, never the corrected number.** If you cannot phrase it without the number, that is the signal the number is the point — drop the finding.

## Report Findings

For each count or positional reference:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Claim** | The number or position as written |
| **Set it mirrors** | The directory, table, list, registry or call site it silently tracks — and its size right now |
| **Breaks when** | The ordinary change that falsifies it (a lens is added, a step is inserted, a caller appears) |
| **Suggestion** | The count-free rewrite, in full |

### Severity Guide

- **High**: A count or position in a *procedure a reader follows* — a runbook step reference, an ordering claim, "one of the two callers" above code being edited. Acting on the stale number means doing the wrong step or missing a call site.
- **Medium**: A count describing a set that grows on ordinary work (lenses, subcommands, supported formats, reviewers, config keys). Certain to drift, no immediate trap.
- **Low**: A lead-in counting the list directly below it, or a count in prose nobody navigates by. Clutter that will quietly become false.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | High | docs/new-server.md:112 | "Step 5 of the root protocol" points at a position in a list that renumbers whenever a step is inserted | Name the step: "the lint-and-doctor step" |
| 2 | Medium | SKILL.md:35 | "Run all 10 reviewers" mirrors `reviewers/`, which now holds 11 | "Run every reviewer" — the list below it already names them |
| 3 | Low | pool.py:8 | Docstring opens "Three things happen on acquire:" above a three-item list | Drop the number; the list shows its own length |

## Rules

- **Delete the number, do not correct it.** A corrected count is a finding you will write again next quarter. "One agent per lens", "every lens", "each supported format", "the `command` tasks".
- **Reference by name, not by position.** "The lint-and-doctor step", not "step 5". Names survive insertion; positions do not.
- **Keep the number where the number is the point** — a limit, a quota, a constant, a version, a dated measurement. Then verify it against its source and cite that source in the finding.
- **Group a house habit into one finding.** Counting lead-ins across twenty docstrings is one Medium naming the pattern and the site count, not twenty Lows. The site count in *your finding* is a measurement and belongs there.
- **Do not flag numbers outside the prose layer** — constants, test fixtures, sample data, quoted command output, a changelog entry describing a released version. This lens reads comments, docstrings and docs only.
- **Do not flag a number the sentence cannot survive without.** "Retries three times, then gives up" describes behaviour the code enforces; check it against the code and leave it alone if it matches.
