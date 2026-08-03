## Prescan the Codebase (orchestrator step)

This file is executed by the **orchestrator** (the main Claude Code session), NOT by individual scrutinize agents. The orchestrator reads files once and passes the results to all agents as a snapshot.

### Scan Procedure

Build a project dossier by reading key files. Prioritize in this order — stop early if the codebase is large (>50 files):

1. Read manifest files (package.json, Cargo.toml, go.mod, pyproject.toml, *.csproj, etc.)
2. Read the README (first 80 lines)
3. Detect stack: framework configs, CI files, Dockerfiles, lockfiles
4. Detect languages from file extensions
5. Read up to 12 key files: prioritize entrypoints (main.*, index.*, app.*), API boundaries, config, then largest source files
6. Detect tests: test/, tests/, spec/, __tests__/
7. Check for risk patterns: eval(), innerHTML, dangerouslySetInnerHTML, hardcoded secrets, unwrap() without justification, bare except:, any types, TODO/FIXME density
8. Check license: LICENSE/COPYING file presence, SPDX identifier, compatibility concerns
9. Check contribution health: CONTRIBUTING.md, CODE_OF_CONDUCT.md, issue/PR templates
10. Check CI/CD: .github/workflows/, .gitlab-ci.yml, Jenkinsfile — are pipelines passing? Are there lint/test/build stages?
11. Git history snapshot: run `git log --oneline -20` and `git shortlog -sn --no-merges | head -5` — assess bus factor, commit quality (meaningful messages vs "fix" / "wip"), force-push patterns

### Thresholds

When assessing scan findings, use these rough thresholds:
- **TODO/FIXME density**: >5% of source lines is notable, >10% is a red flag
- **Test coverage**: no test directory at all is a red flag; test dir exists but <20% of source files have corresponding tests is a concern
- **Dependencies**: >30 direct deps for a small project (<5K LOC) is notable; any dep with known CVEs is a red flag
- **Risk patterns**: even 1 instance of eval()/innerHTML with user input is a red flag; bare except:/unwrap() are concerns at >5 occurrences
- **Bus factor**: single contributor with no recent activity (>6 months) is a concern
- **Commit quality**: >50% of recent commits being single-word messages ("fix", "update", "wip") is notable

### Prioritization

Focus findings on what matters most for the target community. Not every check needs equal weight:
- **Security/correctness issues** always take priority over style
- **Architecture concerns** matter more than individual code smells
- **Missing basics** (no tests, no CI, no license) matter more than advanced tooling gaps

{focus}

### Build the Snapshot

After reading, format ALL collected file contents into a single snapshot block. This is what gets passed to agents via the `{codebase_snapshot}` placeholder.

Format each file as:

````
### file: <relative_path>
```<ext>
<full file contents>
```
````

Include:
- All manifest and config files read
- README excerpt
- All source files read
- CI/CD config files
- License file
- Git log output (as `### file: git-log.txt`)
- Git shortlog output (as `### file: git-shortlog.txt`)

Omit:
- Files matching `.env*`, `*.secrets`, `*credentials*.json`, `*.key`, `*.pem`, `secrets.yml` — list by name only
- Binary files — list by name only
