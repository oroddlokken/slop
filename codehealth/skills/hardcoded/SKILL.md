---
name: hardcoded
description: "Find hardcoded values that should be configuration: magic strings, numbers, URLs, ports, credentials, thresholds, and feature flags buried in source code."
args:
  - name: path
    description: The directory to scan (optional, defaults to cwd)
    required: false
user-invokable: true
---

# Find Hardcoded Values
This skill scans code and reports findings — it does not modify code. It can run standalone or as part of `/codehealth`. Examples are Python; apply equivalent patterns for your target language.

Scan the codebase for magic strings, numbers, URLs, credentials, and thresholds that should be extracted to configuration, environment variables, or constants.

## What to Look For

### Credentials and secrets (CRITICAL)
- API keys, tokens, passwords in source code
- Database connection strings with credentials
- Private keys, certificates
- OAuth client secrets
- Webhook signing secrets

### URLs and endpoints
- Hardcoded API base URLs (`https://api.example.com/v2`)
- Service discovery URLs (`http://localhost:8080`)
- CDN URLs, asset paths
- Database hosts/ports
- External service endpoints
- Webhook callback URLs

### Magic numbers
- Timeout values (`time.sleep(30)`)
- Retry counts (`for i in range(3)`)
- Page sizes (`LIMIT 25`)
- Rate limits (`if count > 100`)
- Threshold values (`if score >= 0.85`)
- Port numbers (`app.run(port=5000)`)
- Buffer sizes, batch sizes

### Magic strings
- Email addresses used for notifications or defaults
- File paths (`/var/log/app.log`, `/tmp/uploads`)
- Template strings for external systems
- Status values that should be enums (`"active"`, `"pending"`, `"failed"`)
- Error messages that are checked by string comparison
- Feature flag names used as raw strings

### Environment-specific values
- Values that differ between dev/staging/production
- Region-specific settings (timezone, locale, currency)
- Feature toggles hardcoded as booleans

### NOT hardcoded (skip these)
- Mathematical constants (`PI`, `e`)
- Language-level constants (`True`, `None`, `0`, `1`, `-1` in obvious contexts)
- Test data in test files (expected values, fixtures)
- Default argument values that are sensible defaults
- HTTP status codes used correctly (`return 404`)
- Single-use string literals in log messages
- Standard ports in documentation/comments

## How to Scan

1. **Search for URL patterns**: `http://`, `https://`, `localhost`, IP addresses
2. **Search for credential patterns**: `password`, `secret`, `token`, `api_key`, `apikey`, `auth`, `credential`
3. **Search for numeric literals** in non-obvious contexts: numbers in conditionals, assignments to timeout/limit variables
4. **Search for string comparisons**: `== "active"`, `== "error"`, `status == "..."`
5. **Check configuration loading**: Is there a config module? Are all values flowing through it, or are some bypassed?
6. **Check .env / config files**: Are there values that SHOULD be in config but aren't?
7. **Compare environments**: Are there if/else blocks switching on environment name with different hardcoded values?

## Report Findings

For each hardcoded value:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Value** | The hardcoded value (redact credentials) |
| **Type** | Credential / URL / Magic number / Magic string / Env-specific |
| **Extract to** | Where it should live (env var, config file, constants module, enum) |
| **Suggested name** | What the config/constant should be called |
| **Risk** | What happens when this value needs to change |

### Severity Guide

- **Critical**: Credentials or secrets in source code — security incident waiting to happen
- **High**: Environment-specific values hardcoded — will break in different environments
- **Medium**: Magic numbers/strings that affect behavior — confusing and error-prone to change
- **Low**: Values that rarely change but would be cleaner as named constants

## Output Format

After scanning, output:

```
## Hardcoded Values Found

### {Severity}: {short description}

**Location**: `{file}:{line}`
**Value**: `{value or [REDACTED] for secrets}`
**Type**: {Credential | URL | Magic number | Magic string | Env-specific}
**Extract to**: {env var `FOO_BAR` | config `settings.timeout` | constant `MAX_RETRIES`}
**Risk**: {what happens when this needs to change}
```

End with a Findings Summary table:

| # | Severity | File:Line | Value | Type | Extract To |
|---|----------|-----------|-------|------|-----------|
| 1 | Critical | path:line | [REDACTED] | Credential | env var `DB_PASSWORD` |

## Rules

- **REDACT all credentials** in your output — never print secrets, tokens, or passwords
- **Suggest specific names** for extracted values — `MAX_RETRY_COUNT = 3` not "extract this number"
- **Suggest the right destination** — secrets go to env vars or secret managers, not config files; magic numbers go to constants or config depending on whether they change per environment
- **Consider the config architecture** — if the project already has a config module, suggest using it. If not, suggest creating one only if there are enough values to warrant it.
