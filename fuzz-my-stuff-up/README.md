# Fuzz My Stuff Up

Adversarial code exploration. Spins up ~20 parallel agents — each trying to break the code from a different angle — then distills all findings into prioritized action points.

## What you get

Up to 20 agents independently attack your codebase, each through a different adversarial lens. After all finish, findings are deduplicated and distilled into:

- **Red — Exploitable Now** — security bypass, data loss, crash with user input
- **Orange — Missing Use Cases** — product gaps, not bugs
- **Yellow — Should Harden** — real edge cases that could bite in production
- **Green — Consider** — valid but non-urgent hardening

Every action item includes a file path, line number, and exploitability rating.

## Fuzzers

| Fuzzer | Attack Angle |
|--------|-------------|
| empty-inputs | Empty strings, null, None, zero, empty arrays, missing keys |
| boundary-values | INT_MAX, INT_MIN, huge strings, negative numbers, off-by-one |
| type-confusion | Wrong types where duck typing or loose validation allows it |
| unicode-chaos | Emoji, RTL text, zero-width chars, combining marks, mojibake |
| concurrency | Race conditions, parallel calls, shared mutable state, TOCTOU |
| path-traversal | `../` escape, symlinks, special paths, null bytes in filenames |
| injection | SQL, command, template, header injection vectors |
| state-machine | Out-of-order operations, double-submit, re-entry, partial completion |
| resource-exhaustion | Huge payloads, deeply nested structures, quadratic blowup, infinite loops |
| time-travel | Timezone edge cases, DST transitions, leap seconds, clock skew, far-future dates |
| permission-escalation | Accessing resources across privilege boundaries, role bypass, IDOR |
| malformed-input | Invalid JSON, truncated data, wrong encoding, BOM, mixed line endings |
| network-failure | Timeout handling, partial responses, DNS failure, retry storms |
| config-chaos | Missing config keys, wrong types in config, env var conflicts, defaults |
| dependency-failure | External service down, wrong version responses, missing optional deps |
| locale-chaos | Different number formats, date formats, currency symbols, RTL layouts |
| filesystem-edge | Read-only fs, full disk, long paths, special chars in filenames, case sensitivity |
| api-abuse | Missing required fields, extra unknown fields, wrong HTTP methods, huge headers |
| upgrade-path | Data from old versions, schema drift, backwards compat gaps, migration holes |
| adversarial-user | Intentionally hostile inputs, CSRF scenarios, replay attacks, parameter tampering |

## Modes

| Mode | What runs |
|------|-----------|
| Full | All 20 fuzzers in parallel (default) |
| Quick | 7 high-impact fuzzers: empty-inputs, type-confusion, injection, state-machine, malformed-input, api-abuse, adversarial-user |
| Pick | You choose which fuzzers to run |

## Installation

Tell your agent to read this repository and ask it to help you integrate it into your Claude Code setup as a skill.
