# Changelog

## 2026-08-16

- Renamed the `llm-slop` lens to `machine-prose`, across the description, the
  mode lists, the boundaries and `distill.md`. The finding is about the prose,
  not about who wrote it.

## 2026-08-15

- Raised the report cap from 25 action points to 35, and added a `Below the cap`
  section — one line per theme with a count and one example path.

## 2026-08-14

- Added reveal openers to the slop lens: "Here's the thing", "It turns out" — the
  run-up implies the reader believed something else a moment ago.
- Gave `transient` the planning-artifact case: `per the M3 spec`, `see the
  migration plan`, `T12 covers the rest`. The document is written to be
  superseded, and `plan`, `spec` and `draft` have day jobs in a query planner or
  a parser, so the reference is flagged and never the noun.
- Made `rambling` sort candidates by size first — blocks over three content
  lines, comment lines over 100 characters — so the findings land before
  attention runs out.

## 2026-08-12

- Added two lenses: `counting` (a count of a set the prose does not own, a
  lead-in numbering its own list, "step 5"-style positional references) and
  `settled-history` (prose that is true and about the past — removals,
  migrations, fixed hazards, rejected alternatives, edit annotations). Both came
  with boundaries against `contradicts-code`, `doc-drift`, `transient`,
  `dead-comments` and the slop lens.
- Struck "actually", "genuinely" and "clearly" from the skill's own prose across
  `SKILL.md`, `distill.md`, seven reviewers and the scan steps.

## 2026-08-09

- Gave `doc-drift` the count case: a number mirroring a set that lives elsewhere
  is right when written and wrong the moment the set grows. The fix is deleting
  the number, not correcting it, unless the number itself is the rule.

## 2026-08-04

- Rewrote the description into a triggerable one, naming what the skill protects
  (why-comments carrying a gotcha) and where the boundaries are (`string-cop`
  for user-facing strings, `codehealth` for the logic).
- Retracted the "~90% cheaper input" caching claim, and added the errata
  contract with its distill step.

## 2026-08-03

- Added the spawn contract: never pass `name:`, and paste the distill output
  into the reply verbatim.

## 2026-07-31

- Rewrote `transient`'s ticket-id section: the id belongs in the commit message,
  and in the file it resolves to nothing without tracker access and to a closed
  ticket about moved code with it. Two shapes — a trailing citation to delete,
  and an id standing in for the fact, where the fact has to be recovered from
  the code. Grade the spread, not the instance: one stray id is Low, a house
  habit across dozens of files is one High naming the prefix and the count.
- Added "one rationale re-argued at every call site" to `rambling`, and the rule
  that length is not proof of care: comment volume tracks how hard the decision
  felt, not how surprising the code reads.

## 2026-07-30

- Added the `llm-slop` lens — vocabulary tics, the antithesis flourish, em-dash
  density, assistant narration idioms — and its boundaries: `rambling` owns
  volume, `restates-code` redundancy, `noise` decoration.
- Ranked style below truth, in the lens, in the boundaries and in `distill.md`:
  when the same prose trips `contradicts-code` or `doc-drift`, the truth finding
  leads and the style note becomes a clause inside it. A rewrite must never make
  an unverified claim more convincing.
- Added uniform rhythm as the strongest tell, with the carve-out that bullet
  density is correct form in agent-facing docs and never flagged there.
- Replaced "load-bearing" with "carries a fact" throughout, since the skill's
  own slop lens flags the phrase.

## 2026-07-03

- Added the who-does-what split between orchestrator and reviewer agents, and
  collapsed every reviewer's bespoke table into the shared `## Findings Summary`
  format.
- Added the severity remap: a reviewer's "Critical" that does not mislead on a
  safety-critical property becomes "High" before tiering.

## 2026-07-02

- Added the skill with nine lenses: `contradicts-code`, `dead-comments`,
  `doc-drift`, `docstring-gaps`, `missing-why`, `noise`, `rambling`,
  `restates-code`, `transient`, plus `agent.md`, `distill.md` and
  `scan-steps.md`. The scan reproduces files byte-for-byte with comments intact,
  and flagging a good why-comment counts as the worst error a reviewer can make.
