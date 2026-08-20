# Changelog

## 2026-08-20

- Added a scope boundary against `should-i-abstract`, which rules on whether an
  abstraction should exist. `duplicates` and `extract-logic` were returning the
  same consolidation with no file naming the owner.
- The description now opens its neighbour clause with `should-i-abstract`, so a
  session choosing between the two reads the split before loading either.

## 2026-08-19

- Corrected the step numbers in the `test-my-tests` boundary: this skill runs
  at 11 and `test-my-tests` at 21, not 9 and 14.
- Added two lenses, taking the skill from thirteen to fifteen.
  `optional-discipline` covers absent values consumed unchecked, truthiness
  presence tests, boundary `Any` and type suppressions; `failure-cleanup`
  covers state left half-written when one call raises partway through.
- Drew the new boundaries: `error-gaps` owns the producer of an absence and
  `optional-discipline` the consumer; `type-structs` owns a value's shape and
  `optional-discipline` the type layer around it; a swallowed exception is
  `error-gaps` while a correct exception over half-written state is
  `failure-cleanup`. Against the wider failure lenses, `failure-cleanup` keeps
  the half-write one call leaves behind — one call raising over local state
  names no deploy shape.

## 2026-08-16

- Named the boundary against `test-my-tests`: when both skills run, `test-gaps`
  reports nothing and hands its list over, since the review order runs this
  skill at step 9 and `test-my-tests` at step 14. Run alone, `test-gaps` keeps
  the lens.

## 2026-08-15

- Raised the report cap from 25 action points to 35, and added a `Below the cap`
  section — one line per theme with a count and one example path.

## 2026-08-10

- Replaced `1+Parallel` with `Rolling 5`, then `1+Rolling 5`, and added the
  background-agent contract and the default-agent-type rule.

## 2026-08-09

- Stopped defaulting to Full mode and Sequential when the user names neither.

## 2026-08-04

- Rewrote the description into a triggerable one — technical debt, duplication,
  dead code, what to refactor, and what a structural change left behind — with
  the boundary against `dba`. Replaced the inert
  frontmatter with `argument-hint` and `disable-model-invocation`.
- Retracted the "~90% cheaper input" caching claim, and added the errata
  contract with its distill step.

## 2026-08-03

- Added the spawn contract: never pass `name:`, and paste the distill output
  into the reply verbatim.

## 2026-07-13

- Set the reviewers' reporting stance: coverage rather than pre-filtering, with
  honest severities, since distill validates every finding.

## 2026-07-03

- Collapsed every reviewer's bespoke prose block into the shared
  `## Findings Summary` table. Thirteen lenses had thirteen output formats.
- Added the who-does-what split between orchestrator and reviewer agents, and
  the severity remap: a "Critical" that is only maintainability or style becomes
  "High" before tiering.

## 2026-05-24

- Added the `caching` lens — stale or leaky caches, unbounded growth, missing
  invalidation or memoization — with the boundary that `query-smells` owns the
  query underneath and `caching` the cache around it.

## 2026-04-30

- Rewrote `distill.md` as a standalone two-pass agent prompt — mechanical
  validate, classify and dedupe, then judgment tiering — run by a fresh Sonnet
  agent that receives the findings tables and not the snapshot.
- Added auto-skip: no SQL or ORM drops `query-smells`, no manifest drops
  `dep-hygiene`, no test infrastructure drops `test-gaps`.
- Added the snapshot cache under `.claude-cache/`, capped each reviewer at 12
  findings, and replaced the token-count snapshot limit with `wc -c` at
  ~1,250,000 bytes.
- Retitled the scan's grep list: the patterns select files, the agents judge
  severity.
- Simplified the dcat probe to running `dcat list --agent-only`, and switched
  the non-git file fallback from `find` to Glob.

## 2026-04-11

- Fixed `1+Parallel` to batch at most five agents, since a 429 mid-run wastes
  the work already done.

## 2026-04-09

- Listed the twelve reviewer names in the Full-mode description instead of the
  count alone.

## 2026-04-02

- Split the agent template at the `---` divider into a shared prefix and a
  per-agent half, resolved once and reused. (The cache claim behind this was
  retracted on 2026-08-04.)

## 2026-03-30

- Added the launch-strategy question, replacing "run all twelve in parallel",
  and pointed `test-gaps` at `/test-my-tests` for deeper test-quality work.
- Added the risk-pattern grep to the scan and a snapshot size limit.

## 2026-03-28

- Absorbed twelve standalone skills as reviewer criteria files: `complexity`,
  `dead-code`, `dep-hygiene`, `duplicates`, `error-gaps`, `extract-logic`,
  `hardcoded`, `naming`, `query-smells`, `simplify-code`, `test-gaps` and
  `type-structs` each stopped being its own skill and became
  `reviewers/<name>.md`. The reviewer-to-skill-path table went with them.

## 2026-03-27

- Made the orchestrator prescan once and pass one snapshot to every agent,
  instead of twelve agents each scanning the same files. `scan-steps.md` became
  an orchestrator playbook, and the agent template a snapshot consumer.

## 2026-03-22

- Added the skill: `SKILL.md`, `agent.md` and `scan-steps.md`, then `distill.md`
  the same day.
- Added the language prescan — group `git ls-files` by extension, confirm the
  list with the user, pass it to every agent — so a repo's smaller languages do
  not get skipped, plus error handling for a missing reviewer file, a non-git
  target and agents that return nothing.
