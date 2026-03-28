# Find Naming Inconsistencies
This reviewer scans code and reports findings — it does not modify code.

Scan the codebase for naming problems that make code harder to navigate, understand, and maintain. Good names are the cheapest documentation.

## What to Look For

### Mixed case conventions
- `snake_case` mixed with `camelCase` in the same language/context
- Inconsistent class naming (`UserManager` vs `account_handler`)
- Constants sometimes `UPPER_SNAKE` and sometimes `lower_snake`
- File names mixing conventions (`user_service.py` alongside `AccountHandler.py`)

### Same concept, different names
- `user` / `account` / `member` / `profile` used interchangeably for the same entity
- `create` / `add` / `new` / `insert` / `make` for the same operation
- `delete` / `remove` / `destroy` / `drop` for the same operation
- `get` / `fetch` / `load` / `find` / `retrieve` / `read` for the same operation
- `update` / `edit` / `modify` / `change` / `patch` for the same operation
- `config` / `settings` / `options` / `preferences` / `params` for the same concept

### Ambiguous or misleading names
- `data`, `info`, `stuff`, `thing`, `item`, `obj` — says nothing about what it is
- `temp`, `tmp`, `x`, `val` outside of tiny scopes
- `process()`, `handle()`, `do()`, `run()`, `execute()` — what do they process/handle/do?
- `manager`, `handler`, `helper`, `utils` — often signals a class/module with no clear responsibility
- Boolean names that don't read as questions (`active` vs `is_active`, `valid` vs `is_valid`)

### Inconsistent prefixes/suffixes
- Some functions prefixed `get_` and others not for the same pattern
- Some classes suffixed `Service` and others `Manager` for the same role
- Some test functions prefixed `test_` and others not
- Inconsistent use of `_` prefix for private/internal

### Abbreviation inconsistency
- `usr` vs `user`, `msg` vs `message`, `btn` vs `button`
- Some abbreviated, some spelled out, no clear rule
- Domain abbreviations not explained anywhere

### Naming that lies
- `get_user()` that actually creates a user if not found
- `validate()` that also transforms the data
- `is_valid` that has side effects
- `count` that returns a list
- `cache` that actually hits the database every time

## How to Scan

1. **Read function/method names** across similar modules — are operations named consistently?
2. **Compare class names** — are similar roles named with the same conventions?
3. **Check variable naming patterns** — `snake_case` vs `camelCase` within the same language
4. **Search for generic names**: `data`, `info`, `result`, `tmp`, `utils`, `helpers`, `misc`
5. **Check boolean naming**: look for boolean variables/properties and check if they read as questions
6. **Compare across layers**: are the same concepts named the same in models, services, routes, and tests?
7. **Read file names** — are they following a consistent pattern?

## Report Findings

For each naming issue:

| Field | Content |
|-------|---------|
| **Locations** | All file:line instances |
| **Type** | Mixed convention / Inconsistent terminology / Ambiguous / Misleading / Abbreviation inconsistency |
| **Currently** | The inconsistent names found |
| **Suggestion** | Which name to standardize on and why |
| **Scope** | How many files/functions would need renaming |

### Severity Guide

- **High**: Same concept with different names across the codebase — causes confusion and bugs (is `user_id` the same as `account_id`? Nobody's sure)
- **High**: Names that lie — a function named `get_X` that creates or modifies is actively misleading
- **Medium**: Mixed case conventions — annoying and unprofessional but doesn't cause logic errors
- **Medium**: Ambiguous names in important code — `process_data()` in a critical path is worse than in a test helper
- **Low**: Minor abbreviation inconsistencies, generic names in small scopes

## Output Format

After scanning, output:

```
## Naming Issues

### Systemic: {pattern description}

**Type**: {Mixed convention | Inconsistent terminology | ...}
**Examples**:
- `{file_1}:{line}` uses `{name_a}`
- `{file_2}:{line}` uses `{name_b}`
- `{file_3}:{line}` uses `{name_c}`
**Standardize on**: `{recommended_name}` because {reason}
**Scope**: {N files would need updating}
```

End with a Findings Summary table:

| # | Severity | File:Line | Type | Current | Suggested |
|---|----------|-----------|------|---------|-----------|
| 1 | High | multiple | Inconsistent term | user/account/member | user |

## Rules

- **Identify the dominant convention** — if 80% of the code uses `snake_case`, that's the standard; flag the 20% that doesn't
- **Suggest one canonical name** for each concept — don't just say "be consistent", say which name to use
- **Respect language conventions** — Python uses `snake_case`, JavaScript uses `camelCase`, etc. Only flag violations of the language's own convention.
- **Don't rename public APIs** unless there's a migration path — note the cost of renaming
- **Group systemic issues** — "the codebase mixes `get_` and `fetch_` for reads" is one finding, not 50 individual findings
