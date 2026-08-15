# Find Prose About Something Already Settled

Scan for comments, docstrings and docs that narrate the past: a thing that was removed, a bug that was fixed, a tool that was migrated away from, an alternative that was rejected. This prose is usually *accurate*, which is why every other lens leaves it alone — contradicts-code and doc-drift need a claim that is false, transient needs a phrase that will rot. A true sentence about a decision nobody has to make again passes both tests and still costs every future reader a paragraph.

The cost is attention, and it lands hardest on a reader working under pressure — including an agent, which will read a removed hazard as a live constraint and design around it. A warning about a problem that no longer exists is worse than no comment: it makes people defensive about nothing, or blocks a safe change.

## What to Look For

### A fixed problem still described as a hazard
- "Note: this double-counts on retry" above code that was fixed
- "The race condition here is handled by the caller — for now" when the lock landed two years ago
- "Careful, `parse()` blows up on empty input" against a `parse()` that returns `[]`

### Removals and migrations narrated
- "We no longer use Redis for this", "replaced the old batch job", "this module used to own the retry loop"
- A module docstring that opens with what the module *was* before saying what it is
- A README section describing a subsystem that was deleted, framed as history rather than as a feature claim

### Rejected alternatives re-litigated
- Paragraphs weighing an option nobody is choosing again: "We considered X, but X has problem Y, and Z would have meant…"
- Keep the clause that would stop someone walking back into the wall; delete the debate around it.

### Edit annotations left in the file
- "restored 2026-08-10", "moved here from `utils.py`", "renamed from `foo`", "(was: `bar`)", "added back after the revert", "kept in sync with the old version of this file"
- The diff and the commit message carry this. A reader opening the file cold cannot tell it was ever different, and should not need to.

### Changelog prose in a place that is not the changelog
- Version history narrated inside a module docstring or a README section while a `CHANGELOG` exists
- "Updated to handle the new format", "refactored for clarity" — what changed, with no why

### History that is still doing work — do not flag
- A removal note that prevents a re-introduction: "Do not add a retry here; retries duplicated charges." That is a present-tense constraint wearing a past-tense sentence. Keep it, tightened to the constraint.
- A workaround comment naming an *upstream* bug that is still open — verify the upstream state before flagging.
- A deprecation notice on an API that still ships: a contract with callers, not history.
- `CHANGELOG*`, ADRs, migration guides, release notes, upgrade docs. History has a home; a document doing that job is correct.

## How to Scan

1. **Grep the prose layer** for: `no longer`, `used to`, `previously`, `formerly`, `originally`, `historically`, `back when`, `at the time`, `since v`, `migrated`, `replaced`, `renamed from`, `moved from`, `restored`, `after the revert`, `legacy`, `we removed`, `we considered`, `instead of the old`, `(was`.
2. **Apply the acting test to every hit.** Does a maintainer do anything differently today because this sentence is here? If the answer is no, it is history. If the answer is yes, the answer *is* the finding — rewrite it as the rule and drop the chronicle.
3. **Check whether the subject still exists.** Grep the named module, flag, service, function. If it is gone, deletion is the suggestion and the evidence is the empty grep.
4. **Check whether the hazard still exists.** For every warning, read the code it sits above and decide whether the failure it describes can still happen. A dead warning is the highest-severity form of this finding.
5. **Look for the archive.** If the repo has a `CHANGELOG`, ADRs or a migration guide, say so in the suggestion — the history is not being destroyed, it is being filed.
6. **Note density per file.** A file carrying several settled-history paragraphs has a habit, not an incident; report it once and name the sites.

## Report Findings

For each passage:

| Field | Content |
|-------|---------|
| **Location** | file:line (range for paragraphs) |
| **History narrated** | What past event the prose is about |
| **Still actionable?** | What a maintainer would do differently today — "nothing" is the common answer and is the finding |
| **Live constraint inside it** | The rule worth keeping, if any, in present tense |
| **Suggestion** | Delete, or replace the passage with the constraint alone |

### Severity Guide

- **High**: A warning about a hazard the code no longer has, or history describing a design the code has since replaced. A reader defends against a dead problem, refuses a safe change, or implements the superseded shape.
- **Medium**: A removal, migration or rejected-alternative passage in a module docstring, README section or runbook — read on every visit, paid for every time, decaying further with each release.
- **Low**: A single edit annotation ("moved here from `utils.py`", "restored", "(was `bar`)") or a one-clause "we used to" aside.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | High | queue.py:14 | "Careful — this double-counts on retry" above a handler made idempotent by the dedupe key added below | Delete; the hazard is gone. If the dedupe key is the reason, say that instead: "Dedupe key makes redelivery safe" |
| 2 | Medium | README.md:88-104 | Section narrating the move off Redis, a store no longer referenced anywhere in the repo | Delete the section; `CHANGELOG.md` already records the migration |
| 3 | Low | loader.py:3 | Docstring ends "(moved here from `utils.py`, 2026-03)" | Delete — git blame owns the move |

## Rules

- **The acting test decides everything.** A past-tense sentence earns its place only if a maintainer would act differently today because of it. If it would, rewrite it as the present-tense rule and drop the story: "Retries duplicate charges — do not add one", not "we removed the retry in v2 because it duplicated charges".
- **Keep the constraint, cut the chronicle.** Never recommend deleting a passage whose only copy of a live rule is inside it. Extract first, then delete.
- **Do not treat deletion as data loss.** Git, the changelog and the ADRs hold the history. Say which one in the suggestion so the author can see nothing is being destroyed.
- **Never annotate instead of deleting.** The fix is removal, not "no longer applies" appended to the line — that leaves the dead prose on the page with a footnote.
- **Verify before flagging a warning.** Read the code and confirm the hazard is gone. A warning you *assume* is stale, and is not, is the worst false positive this skill can produce — flag it only with the line that removes the hazard cited.
- **Group a habit.** Several settled-history passages in one file is one finding naming the file and the sites, not one per paragraph.
- **Do not flag the archive** — `CHANGELOG*`, ADRs, migration and upgrade guides, release notes, deprecation notices on shipping APIs.
