# Changelog

## 2026-08-15

- Raised the report cap from 25 action points to 35, and added a `Below the cap`
  section — one line per theme with a count and one example path.

## 2026-08-14

- Added reveal openers to `llm-slop`: "Here's the thing", "Here's why", "It
  turns out" promise a turn the string never takes and cost the width the fact
  needed.
- Added the compressed form of self-justification to its lens — "Kept here for
  backwards compatibility", "left in place" — with the fix being a limit
  ("Read-only; edit on /settings") rather than the history.

## 2026-08-12

- Struck "actually", "genuinely", "simply" and "truly" from the skill's own
  prose, across `SKILL.md`, `agent.md`, `distill.md`, seven reviewers and the
  scan steps. The skill grades that vocabulary in other people's strings.

## 2026-08-10

- Replaced `1+Parallel` with `Rolling 5`, then `1+Rolling 5`: one priming agent
  in the foreground, then a five-wide window refilled on each completion.
- Added the default-agent-type rule alongside the default model — either
  override invalidates the shared cache entry — and the background-agent
  contract, including never calling `TaskOutput` on a subagent.
- Replaced the caching estimate with the 5-agent measurement: first agent read 0
  and wrote 16,713 tokens, each later agent read 5,994.

## 2026-08-09

- Stopped defaulting to Full mode and Sequential when the user names neither.
- Gave `contradicts-view` the hardcoded-count case: "12 checks run on every
  commit" beside a registry of thirteen. The fix is the count-free wording, not
  the corrected number, because a corrected literal drifts again.

## 2026-08-04

- Rewrote the description into a triggerable one, and replaced the inert
  `args`/`user-invocable` frontmatter with `argument-hint` and
  `disable-model-invocation: true`.
- Retracted the "~90% cheaper input" caching claim: agents share no prompt cache
  with each other, the `---` divider is a section divider rather than a cache
  boundary, and snapshot size is the lever that moves cost.
- Added the errata contract for a brief found wrong mid-run, and the matching
  distill step that drops earlier findings resting on a corrected claim.

## 2026-08-03

- Added the spawn contract: never pass `name:`, since a named agent becomes a
  mailbox teammate whose findings never come back. The distill output goes into
  the reply verbatim.
- Dropped the references to the removed `/sweep` and `/impeccable` skills; a
  cramped page is now "a design concern", named as out of scope.

## 2026-08-02

- Added the skill with ten lenses: `contradicts-view`, `cross-screen`,
  `empty-and-error`, `lecture`, `llm-slop`, `reassurance`, `redundancy`,
  `scaffold-filler`, `self-justification`, `widget-narration`, plus `agent.md`,
  `distill.md` and `scan-steps.md`. The scan extracts strings rather than
  dumping files, byte-for-byte, and only `contradicts-view` can raise a
  Critical.
