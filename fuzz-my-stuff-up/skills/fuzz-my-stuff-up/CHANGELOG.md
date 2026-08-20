# Changelog

## 2026-08-16

- Renamed `fuzzer-agent.md` to `agent.md`, matching every other reviewer skill.

## 2026-08-10

- Replaced `1+Parallel` with `Rolling 5`, then `1+Rolling 5`, and added the
  background-agent contract and the default-agent-type rule.

## 2026-08-09

- Stopped defaulting to Full mode and Sequential when the user names neither.

## 2026-08-04

- Rewrote the description into a triggerable one — stress-test, harden, find
  crash inputs, run after the happy path works — and replaced the inert
  frontmatter with `argument-hint` and `disable-model-invocation`.
- Retracted the "~90% cheaper input" caching claim; the `---` divider is a
  section divider, not a cache boundary.
- Added the errata contract with its distill step.

## 2026-08-03

- Added the spawn contract: never pass `name:`, and paste the distill output
  into the reply verbatim.

## 2026-07-13

- Reframed the agent from attacker to defender: this is a hardening review of
  our own code, so a finding names the weakness, a concrete triggering input,
  and the fix — no working exploits, weaponized payloads or attack tooling. The
  "Attack" step became "Probe the defenses" and the "Attack Narrative" became an
  "Exposure Summary".
- Set the reporting stance: coverage rather than pre-filtering, honest
  severities, since distill validates every finding.

## 2026-07-03

- Wrote down why the fuzzers share one methodology instead of per-lens criteria
  files: fuzzing is open-ended, and a fixed checklist would narrow it. Each
  fuzzer differs only by its attack angle.
- Added universal severity definitions as the distill baseline: easy
  exploitability bumps a finding up a tier, and a "Critical" needing implausible
  conditions drops to "High".
- Added the who-does-what split between orchestrator and fuzzer agents, and
  widened the scan's git log from 15 commits to 20.

## 2026-04-30

- Rewrote `distill.md` as a standalone two-pass agent prompt, run by a fresh
  Sonnet agent that receives the findings tables and not the snapshot.
- Added auto-skip for six fuzzers with no target patterns: no concurrency
  primitives, no network code, no locale code, no path handling (drops both
  `filesystem-edge` and `path-traversal`), no query construction, no
  timezone arithmetic.
- Added the snapshot cache under `.claude-cache/`, capped each fuzzer at 12
  findings, and replaced the token-count snapshot limit with `wc -c` at
  ~1,250,000 bytes.
- Simplified the dcat probe to running `dcat list --agent-only`, and switched
  the non-git file fallback from `find` to Glob.

## 2026-04-11

- Fixed `1+Parallel` to batch at most five agents, since a 429 mid-run wastes
  the work already done.

## 2026-04-09

- Listed the twenty fuzzer names in the Full-mode description instead of the
  count alone.

## 2026-04-02

- Split the agent template at the `---` divider into a shared prefix and a
  per-agent half, resolved once and reused. (The cache claim behind this was
  retracted on 2026-08-04.)

## 2026-03-30

- Moved the prescan out to `scan-steps.md`, and replaced "launch all twenty in
  one parallel batch" with a launch strategy the user picks. The old rule
  claimed parallel launching was needed to catch timing bugs; the agents read a
  static snapshot, so it was not.
- Restructured `fuzzer-agent.md` so the shared half — snapshot, languages,
  ground rules, output format — precedes the per-fuzzer assignment.

## 2026-03-27

- Made the orchestrator prescan once and pass one snapshot to every fuzzer,
  instead of twenty agents each scanning the same files. Agents keep Grep, Glob
  and Read for tracing a specific path, but no longer scan broadly.

## 2026-03-25

- Added the skill: `SKILL.md`, `fuzzer-agent.md` and `distill.md`, with twenty
  attack angles from empty inputs and unicode chaos to state-machine abuse and
  adversarial users.
