## Prescan the Codebase (orchestrator step)

This file is the playbook for the **orchestrator** — the main Claude Code session running `/should-i-abstract` — when it gathers raw input for the review agent. The output is a `{codebase_snapshot}` block: a flat sequence of file contents the agent will analyze. The orchestrator's contribution is selection (which files to include) and faithful reproduction (each file verbatim). The agent does the thinking.

### Iron Law: Files Go In Verbatim, Conclusions Stay Out

Every file you include is reproduced byte-for-byte: full content, original order, no commentary, no elisions, no surrounding headings other than the `### file:` marker. The agent cannot independently apply its DRY framework if the snapshot has already labeled code as duplicated, grouped files by theme, or stripped bodies to signatures — pre-cooked findings anchor the analysis and the snapshot becomes a self-confirming review instead of raw evidence.

This rule blocks, by name:
- **Layer maps and tree diagrams** that summarize architecture instead of providing files.
- **"Critical file excerpts" headings** that group files by topic or significance.
- **File digests** like `(108 lines, full)` or `(76 lines, key parts)` that strip bodies to signatures.
- **Inline commentary** between or inside file blocks: "(this is duplicated)", "(see also X)", "(bug)", "(parallel to Y)".
- **Counted findings** like "appears in 5 importers" or "duplicated 3 times".
- **Section headings for thematic grouping** ("Balance upsert duplication", "Notes domain — parallel implementations").
- **`...` or `# rest unchanged`** anywhere inside a file block.

| Excuse | Reality |
|---|---|
| "I'm just helping the agent see the duplication faster." | You're foreclosing its analysis. It will ratify what you wrote instead of reasoning from source. |
| "The codebase is too large to include in full." | Drop whole files (least-shared first); never abridge individual files. |
| "A layer map gives essential context." | The agent reconstructs structure from file paths and imports. The map adds nothing the files don't. |
| "Key signatures save tokens and still show the shape." | Signatures aren't enough to judge true vs. incidental duplication — the agent needs bodies. |
| "One short note won't hurt." | Each note shifts the agent's frame from independent reviewer toward confirmer. The effect compounds. |

Red flags — if you find yourself thinking any of these, stop and resume verbatim file-dumping:
- "Let me note that this is similar to..."
- "I'll add a layer map for orientation."
- "These two files are clearly parallel — I'll group them."
- "(this function is identical to the one in X)"
- "Showing key signatures only to keep size down."
- "I should flag that this looks like a bug."

### Reading Priorities (which files to include)

These guide selection. Do not let the framing leak into the snapshot as commentary.

1. Manifest files (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `*.csproj`, etc.).
2. README and any architecture or design docs.
3. **Languages in scope**: {languages}. Cover each.
4. Shared/common modules — anything under `utils/`, `helpers/`, `lib/`, `common/`, `shared/`, `core/`, `base/`, `mixins/`. The agent's analysis depends on seeing which abstractions already exist.
5. Source files across all in-scope languages, distributed proportionally to file count, with at least 3-5 files per language. Prioritize:
   - Shared utilities and helpers
   - Service layers and business logic
   - API routes and controllers
   - Models and schemas
   - Entrypoints (`main.*`, `index.*`, `app.*`)
   - Pairs of files with similar names across modules (e.g., `user_service.py` + `account_service.py`) — include both with no commentary on the pairing
   Read 10-15% of files or at least 5 per language, whichever is greater. Stop when further reading would only add files structurally similar to those already included.
6. A few representative test files (`test/`, `tests/`, `spec/`, `__tests__/`), included verbatim like any other source.
7. Run `git log --oneline -20` and capture verbatim output.
8. Run `git log --oneline --diff-filter=A -20` and capture verbatim output.

{focus}

### Snapshot Format

The snapshot is a flat sequence of `### file:` blocks. Nothing precedes the first block; nothing follows the last. No introduction, no summary, no closing notes.

Format every file:

````
### file: <relative_path>
```<ext>
<full file contents>
```
````

For READMEs longer than 80 lines, include the first 80 lines verbatim — that is the only allowed truncation, and it applies only to README and architecture-doc files.

For the git logs:

````
### file: git-log.txt
```
<verbatim git log --oneline -20 output>
```

### file: git-log-added.txt
```
<verbatim git log --oneline --diff-filter=A -20 output>
```
````

For sensitive files (`.env*`, `*.secrets`, `*credentials*.json`, `*.key`, `*.pem`, `secrets.yml`) and binary files, include a stub block in place of contents:

````
### file: .env
```
[redacted: sensitive file]
```
````

### Size Limit

Before assembling the snapshot, run `wc -c` on the selected file list. If the total exceeds ~1,250,000 bytes (≈300K tokens of code), stop and ask the user to narrow scope. Drop whole files (prefer dropping leaf modules like route handlers; keep shared utilities); never abridge individual files to fit.

### Final Check (mirrors the Iron Law)

Before handing the snapshot to the agent:
- Scan for text outside a `### file:` block. Remove it.
- Scan for `...`, "key parts", "key signatures", "(N lines, full)" markers. Restore the full file or drop it.
- Scan for headings other than `### file: <path>`. Remove them.
- Scan for parenthetical commentary inside file blocks. Remove it.

If any of these are present, the snapshot is not ready.
