# Changelog

## 2026-08-16

- Renamed `test-agent.md` to `agent.md`, matching every other reviewer skill.
- Added the sibling boundaries to the description and the skill: the source
  under the tests is `codehealth`'s, and where both run, this skill owns the
  suite while `codehealth/test-gaps` steps back.

## 2026-08-15

- Raised the report cap from 25 action points to 35, and added a `Below the cap`
  section — one line per theme with a count and one example path.

## 2026-08-10

- Replaced `1+Parallel` with `Rolling 5`, then `1+Rolling 5`: one priming agent
  in the foreground, then a five-wide window refilled on each completion.
- Added the default-agent-type rule alongside the default model, the
  background-agent contract, and the 5-agent cache measurement.

## 2026-08-09

- Stopped defaulting to Full mode and Sequential when the user names neither.

## 2026-08-04

- Rewrote the description into a triggerable one — it grades whether the suite
  would catch a real bug, and it reads tests without running them — and replaced
  the inert frontmatter with `argument-hint` and `disable-model-invocation`.
- Retracted the "~90% cheaper input" caching claim; the `---` divider is a
  section divider, not a cache boundary.
- Added the errata contract and the matching distill step for findings resting
  on a corrected claim.

## 2026-08-03

- Added the spawn contract: never pass `name:`, and paste the distill output
  into the reply verbatim.

## 2026-07-13

- Set the reviewers' reporting stance: the distill step validates every finding,
  so report each genuine gap within the cap rather than pre-filtering, and mark
  severity honestly.

## 2026-07-03

- Added the who-does-what split between orchestrator and reviewer agents, and
  universal severity definitions — a reviewer's "Critical" that is only a
  test-quality gap is remapped to "High" before tiering.
- Normalized every reviewer file's headings from `##` to `#`.

## 2026-04-30

- Rewrote `distill.md` as a standalone agent prompt in two passes: validate,
  classify and dedupe mechanically, then tier and rank by judgment. Distillation
  moved to a fresh Sonnet agent that receives the findings tables and not the
  snapshot, which would have added ~200K tokens for nothing.
- Added auto-skip for lenses with no target patterns — no mocking library drops
  `mock-debt`, no clock or randomness drops `flaky-risks`, no tests at all stops
  the run.
- Added the snapshot cache under `.claude-cache/`, keyed on skill, path, HEAD,
  dirty state and languages.
- Capped each reviewer at 12 findings, and replaced the token-count snapshot
  limit with `wc -c` at ~1,250,000 bytes; drop whole files rather than abridging
  one.
- Simplified the dcat probe to running `dcat list --agent-only`, and switched
  the non-git file fallback from `find` to Glob.

## 2026-04-11

- Fixed `1+Parallel` to batch at most five agents: Anthropic rate-limits large
  simultaneous bursts, and a 429 mid-run wastes the work already done.

## 2026-04-09

- Listed the ten reviewer names in the Full-mode description instead of the
  count alone.

## 2026-04-02

- Split the agent template at the `---` divider into a shared prefix and a
  per-agent half, resolved once and reused, with a marker comment in the
  template. (The cache claim behind this was retracted on 2026-08-04.)

## 2026-03-30

- Added the skill with ten lenses: `assertion-quality`, `boundary-values`,
  `coverage-gaps`, `data-realism`, `error-paths`, `flaky-risks`,
  `fragile-tests`, `happy-path-only`, `mock-debt`, `user-flows`, plus
  `test-agent.md`, `distill.md` and `scan-steps.md`.
