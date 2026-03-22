---
name: extract-logic
description: "Find inline operations that should be extracted into functions, methods, or service layers. Detects raw SQL in handlers, scattered API calls, repeated multi-step operations, and business logic buried in the wrong layer."
args:
  - name: path
    description: The directory to scan (optional, defaults to cwd)
    required: false
user-invokable: true
---

# Find Code That Should Be Extracted
This skill scans code and reports findings — it does not modify code. It can run standalone or as part of `/codehealth`. Examples are Python; apply equivalent patterns for your target language.

Scan the codebase for inline operations that should be functions, methods, or services. The goal: business logic should be named, testable, and reusable — not scattered inline across handlers, views, and scripts.

## What to Look For

### Raw database operations inline
```python
# BAD: Raw SQL in a route handler
@app.route("/users")
def get_users():
    cursor.execute("SELECT * FROM users WHERE active = 1 ORDER BY created_at DESC")
    rows = cursor.fetchall()
    return jsonify([dict(r) for r in rows])
```
Should be: `user_repo.get_active_users()` or equivalent

**Note**: Raw SQL scattered in handlers is owned by `/query-smells`. Flag database operations here only if the extraction reveals a missing service layer beyond just moving SQL.

### Raw HTTP/API calls inline
```python
# BAD: HTTP call with retry/parse logic inline in business code
response = requests.get(f"https://api.example.com/users/{user_id}", headers={"Authorization": f"Bearer {token}"})
if response.status_code == 200:
    data = response.json()
    # 10 lines of response parsing...
```
Should be: `api_client.get_user(user_id)` with parsing encapsulated

### Multi-step operations without a name
```python
# BAD: Complex operation inline with no name
file_path = os.path.join(upload_dir, secure_filename(f.filename))
f.save(file_path)
thumbnail = Image.open(file_path).resize((200, 200))
thumbnail.save(file_path.replace('.', '_thumb.'))
db.execute("INSERT INTO uploads ...")
send_notification(user, "Upload complete")
```
Should be: `upload_service.process_upload(file, user)`

### Business rules buried in presentation/routing layer
- Validation logic in route handlers instead of model/service layer
- Price calculations in templates instead of business logic
- Permission checks scattered across views instead of a central auth layer
- Data transformation logic in API serializers instead of domain layer

### File/system operations inline
- Direct `os.path`, `shutil`, `subprocess` calls in business logic
- File parsing (CSV, JSON, XML) done inline instead of in a parser function
- Environment/config reading scattered throughout code instead of centralized

### Repeated multi-step patterns
The same sequence of steps appearing in multiple places, even if not identical:
1. Validate input
2. Check permissions
3. Perform operation
4. Log result
5. Send notification

If this pattern repeats for different operations, the skeleton should be a shared abstraction.

## How to Scan

1. **Read route handlers / controllers** — these are the #1 location for inline operations that should be extracted
2. **Read CLI commands / scripts** — often have inline operations that duplicate service logic
3. **Read test files** — tests that set up complex state inline often reveal missing service methods
4. **Check for long functions** (>30 lines) — length often signals inline operations
5. **Look for import clusters** — a file importing `os`, `json`, `requests`, `smtplib` is probably doing too many things inline

### Signals
- Functions longer than 30 lines
- Route handlers that do more than parse request → call service → format response
- Files with many diverse imports (database + HTTP + file system + email)
- Inline string formatting for SQL queries
- Raw `cursor.execute()`, `requests.get()`, `subprocess.run()` in business logic
- Multiple levels of nesting inside a single function

## Report Findings

For each extraction opportunity:

| Field | Content |
|-------|---------|
| **Location** | file:line range |
| **What** | What inline operation was found |
| **Layer violation** | Which layer is this in vs which layer should it be in |
| **Extract to** | Suggested function/method name and where it should live |
| **Interface** | What the extracted function's signature should look like |
| **Why** | What you gain — testability, reusability, readability |

### Severity Guide

- **Critical**: Business logic (money, permissions, data integrity) inline in wrong layer — untestable and likely to have bugs
- **High**: Data access inline in handlers — makes it impossible to change DB without touching every route
- **Medium**: Utility operations inline — readable but not reusable or testable in isolation
- **Low**: Simple operations that could be extracted but are clear enough inline — note but don't force

## Output Format

After scanning, output:

```
## Extraction Opportunities

### {Severity}: {short description}

**Location**: `{file}:{start_line}-{end_line}`
**Inline operation**: {what's happening inline}
**Layer violation**: {current layer} → should be in {correct layer}
**Extract to**: `{target_file}:{function_name}({params}) -> {return_type}`
**Why**: {testability, reusability, separation of concerns}
```

End with a Findings Summary table:

| # | Severity | File:Line | Inline Operation | Extract To | Why |
|---|----------|-----------|-----------------|------------|-----|
| 1 | Critical | path:line | Raw SQL in route handler | user_repo.get_active() | Testable, reusable |

## Rules

- **Focus on meaningful extractions** — don't suggest extracting a 2-line operation into its own function unless it's called from 3+ places
- **Suggest concrete names and locations** — "extract to a function" is useless; "extract to `services/billing.py:calculate_invoice_total(line_items, tax_rate)`" is actionable
- **Consider the layer architecture** — routes/controllers should be thin; services hold business logic; repositories handle data access
- **Don't force patterns** — if the codebase doesn't have a service layer, suggest creating one only if there are enough extraction targets to warrant it
