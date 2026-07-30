# Find Dead Comments & Cruft

Scan for comments that are not documentation at all: commented-out code, debug leftovers, and abandoned TODO/FIXME graveyards. Version control already remembers deleted code; a block of it living in comments is pure noise that rots and confuses. Markers that have sat untouched for years are lies about intent.

## What to Look For

### Commented-out code
- Blocks of real code disabled with `#`, `//`, `/* */`, or `<!-- -->` — old implementations, "keep just in case" snippets, alternative approaches
- A single commented-out line left mid-function (`# old_value = compute()`)
- Large commented regions that dwarf the live code

### Debug / scaffolding leftovers
- `# print(x)  # debug`, `console.log` left commented, `# breakpoint()`, temporary logging
- "Uncomment to enable verbose mode" style toggles left as commented code (a real config flag belongs in config, not a comment toggle)

### Stale task markers
- `TODO` / `FIXME` / `XXX` / `HACK` with no owner, no ticket, no date — especially ones describing work that looks long since done or abandoned
- Contradictory markers ("TODO: remove this" on code the system now depends on)
- `TODO`s that are actually feature wishlists parked in the wrong place

### Zombie documentation
- Docstrings for deleted parameters/functions left dangling
- Commented-out config keys, commented-out imports

## How to Scan

1. **Grep for comment markers wrapping code syntax** — a `#`/`//` immediately followed by things like `=`, `(`, `def`, `return`, `if`, `import`, a call. That's commented-out code, not prose.
2. **Grep for `TODO`, `FIXME`, `XXX`, `HACK`, `WIP`, `TEMP`, `DEBUG`, `NOCOMMIT`.** For each, judge: is it actionable and current, or abandoned?
3. **Cross-check TODOs against reality** — does the described work still make sense, or was it done?
4. **Look for commented imports and config keys** — often left after a refactor.
5. **Spot toggle-by-comment** — code commented out with an instruction to uncomment it; note this is a config smell.

## Report Findings

For each dead comment:

| Field | Content |
|-------|---------|
| **Location** | file:line (range for blocks) |
| **Type** | Commented-out code / debug leftover / stale marker / zombie doc |
| **Evidence** | Why it's dead (git has it, work looks done, no owner) |
| **Suggestion** | Delete (git remembers) — or convert a live TODO into a tracked issue |

### Severity Guide

- **Medium**: A large commented-out block, or a `HACK`/`FIXME` on important code that signals a real unresolved risk (surface it, don't just delete).
- **Low**: Small commented-out lines, debug leftovers, generic stale TODOs — delete on sight.
- Never demand keeping commented-out code "for reference" — that's what version control is for.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | Low | graph.py:120-138 | 18-line commented-out old layout implementation | Delete — recover from git if ever needed |

## Rules

- **Commented-out code → delete, always.** The recommendation is deletion; version control is the archive. Do not suggest keeping it.
- **A FIXME/HACK marking a genuine known risk is a signal, not just cruft.** Recommend converting it to a tracked issue (e.g. dcat) rather than silently deleting the warning.
- **Distinguish a real toggle from dead code.** A commented block that is a documented on/off switch should become a proper config flag — note that, don't just delete.
- **Don't flag legitimate directive comments** — `# noqa`, `# type: ignore`, `# pragma: no cover`, `eslint-disable` are functional pragmas, not dead comments.
