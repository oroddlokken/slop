# Changelog

## 2026-08-04

- Replaced the inert `args` and `user-invocable` frontmatter with
  `argument-hint: "[area]"` and `disable-model-invocation: true`. The skill runs
  only when the user asks for it.
- Corrected what the 1-hour snapshot TTL is for: a staleness backstop, not a
  match to the prompt-cache window. Editing an already-dirty file leaves
  `git status --porcelain` unchanged, so the cache key alone goes stale. The
  cache is per-skill, and with one agent there is no shared prefix to prime.

## 2026-08-03

- Pinned the spawn contract: `run_in_background: false` and no `name:` — a named
  agent becomes a mailbox teammate and the findings never come back. The
  findings now go into the reply verbatim, since only the reply is rendered.

## 2026-07-13

- Tightened the agent's deliverable from "reasoning" to a cited framework test:
  a finding that names no rule is incomplete.

## 2026-07-03

- Fixed the `user-invokable` typo in the frontmatter.

## 2026-04-30

- Added the Iron Law to the scan: files go into the snapshot byte-for-byte and
  conclusions stay out. It names what it blocks — layer maps, "key excerpts"
  headings, `(76 lines, key parts)` digests, inline commentary, counted
  findings, thematic grouping, `...` elisions — with an excuse-versus-reality
  table and a red-flag list. A snapshot that has already labeled code as
  duplicated turns the review into a ratification of the orchestrator's guess.
- Added the snapshot cache: key from skill, path, `git rev-parse HEAD`,
  `git status --porcelain` and the language list, stored under
  `.claude-cache/`, reused for an hour.
- Replaced the token-count size limit with `wc -c` over the selected files at
  ~1,250,000 bytes, and said how to fit: drop whole leaf modules, never abridge
  a file. Added redaction stubs for `.env*`, key and credential files, and a
  final check that re-reads the snapshot for anything outside a `### file:`
  block.
- Simplified the dcat probe to running `dcat list --agent-only` and reading the
  error, and switched the non-git file fallback from `find` to Glob.

## 2026-04-06

- Added the skill: `SKILL.md`, `agent.md` and `scan-steps.md`, one agent
  reviewing in both directions — code that should be shared, and abstractions
  that should be inlined.
