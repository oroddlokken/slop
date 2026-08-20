# Changelog

## 2026-08-19

- Added the `write-durability` lens — `fsync=off`, SQLite `synchronous=OFF`,
  UNLOGGED tables, a data directory on ephemeral storage, replicas read as
  committed — taking the skill from twelve lenses to thirteen and Quick mode
  from five to six. `transaction-gaps` owns whether a write is wrapped;
  `write-durability` owns whether the commit survives power loss, and stops at
  the database's acknowledgement.
- Widened the scan to server config the repo carries — `postgresql.conf`,
  `my.cnf`, `*.conf` under `docker/` — plus the compose and Kubernetes manifests
  that set the server's flags and mount its data directory.

## 2026-08-15

- Raised the report cap from 25 action points to 35, and added a `Below the cap`
  section — one line per theme with a count and one example path.

## 2026-08-10

- Replaced `1+Parallel` with `Rolling 5`, then `1+Rolling 5`, and added the
  background-agent contract and the default-agent-type rule.

## 2026-08-09

- Stopped defaulting to Full mode and Sequential when the user names neither.

## 2026-08-04

- Rewrote the description into a triggerable one, naming the boundary against
  `codehealth`'s single `query-smells` reviewer and stating that NoSQL is out of
  scope. Replaced the inert frontmatter with `argument-hint` and
  `disable-model-invocation`.
- Retracted the "~90% cheaper input" caching claim, and added the errata
  contract with its distill step.

## 2026-08-03

- Added the spawn contract: never pass `name:`, and paste the distill output
  into the reply verbatim.

## 2026-07-13

- Set the reviewers' reporting stance: coverage, not pre-filtering, with honest
  severities, since distill validates every finding.

## 2026-07-03

- Collapsed every reviewer's bespoke prose block into the shared
  `## Findings Summary` table. Twelve lenses had twelve output formats.

## 2026-04-30

- Rewrote `distill.md` as a standalone two-pass agent prompt — mechanical
  validate, classify and dedupe, then judgment tiering — run by a fresh Sonnet
  agent that receives the findings tables and not the snapshot.
- Added the high-severity validation checks: is the N+1 collection actually
  unbounded, is the table on a hot path, does the framework auto-wrap
  transactions.
- Added auto-skip: no ORM drops `orm-antipatterns`, no migrations directory
  drops `migration-safety` and `schema-drift`, no GRANT or RLS drops
  `privilege-scope`, no pool config drops `connection-mgmt`.
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

- Added the skill with twelve lenses: `connection-mgmt`, `data-integrity`,
  `index-coverage`, `injection`, `migration-safety`, `n-plus-one`,
  `orm-antipatterns`, `privilege-scope`, `query-scatter`, `raw-perf`,
  `schema-drift`, `transaction-gaps`, plus `agent.md`, `distill.md` and
  `scan-steps.md`.
