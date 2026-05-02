## Prescan the Codebase (orchestrator step)

This file is executed by the **orchestrator** (the main Claude Code session), NOT by individual review agents. The orchestrator reads files once and passes the results to all agents as a snapshot. Your role is selection (which files to include) and faithful reproduction (each file verbatim); the agents do the analysis.

### Scan Procedure

Read both source and test code broadly. The goal is to capture enough for agents to assess test quality without re-reading files:

1. Read manifest files (pyproject.toml, package.json, Cargo.toml, go.mod, *.csproj, etc.) to understand the stack and test dependencies
2. Detect test framework: pytest, unittest, jest, vitest, mocha, RSpec, go test, cargo test, etc.
3. Detect test tooling: coverage tools, mocking libraries, fixture frameworks, factory libraries, test runners
4. Read test configuration: pytest.ini, jest.config.*, .nycrc, conftest.py, setup.cfg test sections, test helpers/setup files
5. **Languages in scope:** {languages}. Review tests for all of these.
6. Map source-to-test coverage:
   - List all source files (excluding tests, configs, assets)
   - List all test files (matching patterns: test_*, *_test.*, *.test.*, *.spec.*, tests/, __tests__/, spec/)
   - Note which source files have corresponding test files and which don't
   - Format this as a coverage map
7. Read key source files across all in-scope languages — prioritize: API routes/controllers, models/schemas, services/business logic, auth/authz, data mutations, utility functions with complex logic. Read 10-15% of source files or at least 5, whichever is greater.
8. Read ALL test files (or up to 30 if the test suite is large). For large test suites, prioritize: integration/e2e tests, tests for business-critical modules, recently modified tests (check git log), then unit tests.
9. Read test fixtures, factories, seed data, and test utility/helper files
10. Check CI/CD: .github/workflows/, .gitlab-ci.yml, Jenkinsfile — what tests run, which are required, any coverage thresholds?
11. Git history: run `git log --oneline -20` — look at recent changes and whether they came with test updates
12. Check for test quality tools: mutation testing (mutmut, stryker, pitest), property-based testing (hypothesis, fast-check, quickcheck), snapshot testing

{focus}

### Build the Snapshot

After reading, reproduce each selected file verbatim — full content, no elisions, no commentary, no headings outside `### file:` blocks. The result is what gets passed to agents via the `{codebase_snapshot}` placeholder.

Format each file as:

````
### file: <relative_path>
```<ext>
<full file contents>
```
````

Include:
- All manifest and config files read
- Test configuration files
- All source files read
- All test files read
- Test fixtures/factories/helpers
- CI/CD config files
- Git log output (as `### file: git-log.txt`)
- Source-to-test coverage map (as `### file: test-coverage-map.txt`)

Omit:
- Files matching `.env*`, `*.secrets`, `*credentials*.json`, `*.key`, `*.pem`, `secrets.yml` — list by name only
- Binary files — list by name only

**Snapshot size limit**: Run `wc -c` on the selected file list. If the total exceeds ~1,250,000 bytes (≈300K tokens of code), ask the user to narrow scope. Drop whole files (prefer leaf modules; keep shared utilities); never abridge individual files to fit.
