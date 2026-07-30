## Prescan the Codebase (orchestrator step)

This file is executed by the **orchestrator** (the main Claude Code session), NOT by individual review agents. The orchestrator reads files once and passes the results to all agents as a snapshot. Your role is selection (which files to include) and faithful reproduction (each file verbatim); the agents do the analysis.

**Critical for this skill:** reproduce files **byte-for-byte, comments and docstrings intact**. Comment Cop reviews the prose *in* the code — never strip, summarize, or reflow comments during the scan. A snapshot with comments removed is useless here.

### Scan Procedure

Read broadly — the goal is to capture enough code and docs across all languages so agents can judge comment quality against the surrounding code without re-reading files:

1. Read manifest files (pyproject.toml, package.json, Cargo.toml, go.mod, etc.) to understand the stack and what the public/exported surface is (entry points, package exports).
2. Read the README **in full** (not just the first N lines — doc-drift needs the whole thing) and any architecture/design docs, `docs/*.md`, `.rst` files.
3. **Languages in scope:** {languages}. Review comments in all of these — do not skip any. Markdown/rST docs count and must be included for the doc-drift lens.
4. Detect the framework and any conventions doc (CONTRIBUTING, a style guide) — these tell you the project's own comment/docstring norms.
5. Read key source files **across all in-scope languages**, comments intact. Distribute effort proportionally to file count but ensure every language gets meaningful coverage (at least 3–5 files each). Prioritize files most likely to carry heavy prose: module entry points, public API modules, config/loading modules, anything with a large module-level docstring. For each language, read 10–15% of files or at least 5, whichever is greater. Stop when additional files show no new comment patterns.
6. Prefer files with dense comment/docstring content — a file that is 40% prose is higher-value for this review than a 200-line file with no comments. When skimming to select, favor files where docstrings and block comments are visibly long.
7. Include prose docs: `README*`, `docs/**/*.md`, `*.rst`, `CHANGELOG*` (only if referenced as living docs), and any usage-example files. doc-drift compares these against actual signatures.
8. Git history snapshot: run `git log --oneline -20` — recent activity areas are where comments are most likely to have drifted from code.

{focus}

### Build the Snapshot

After reading, reproduce each selected file verbatim — full content, **all comments and docstrings preserved exactly**, no elisions, no commentary, no headings outside `### file:` blocks. The result is what gets passed to agents via the `{codebase_snapshot}` placeholder.

Format each file as:

````
### file: <relative_path>
```<ext>
<full file contents, comments intact>
```
````

Include:
- All manifest files read
- README (full) and all markdown/rST docs read
- All source files read (comments intact)
- Git log output (as `### file: git-log.txt`)

Omit:
- Files matching `.env*`, `*.secrets`, `*credentials*.json`, `*.key`, `*.pem`, `secrets.yml` — list by name only
- Binary and vendored/minified files — list by name only

**Snapshot size limit**: Run `wc -c` on the selected file list. If the total exceeds ~1,250,000 bytes (≈300K tokens of code), ask the user to narrow scope. Drop whole files (prefer leaf modules with sparse comments; keep prose-dense files and all docs); never abridge individual files to fit — abridging would corrupt the very comments under review.
