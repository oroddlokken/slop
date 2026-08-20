# Find Absence That Nobody Handles

Scan the codebase for values that can be absent and the call sites that spend them anyway: a return used without a check, an `Optional` unwrapped on one branch and not its sibling, a truthiness test that reads `0` and `""` as missing, an `Any` that ends type checking at a boundary, and the suppression comment sitting on the line that would have caught it. This lens owns the consumer — where the absence lands, not where it was produced.

## What to Look For

### A possibly-absent return used without a check

The producer can return `None`/`nil`/`undefined`, and the next line dereferences it.

```python
# BAD: get_user returns None for an unknown id
user = get_user(user_id)
send_email(user.email)          # AttributeError on the miss
```

```typescript
// BAD: find returns undefined when nothing matches
const row = rows.find(r => r.id === id);
render(row.name);               // TypeError at runtime
```

Trace the producer before flagging: a signature saying `-> User | None`, a `return None` on an early branch, an `Optional[...]`, a `dict.get`, `.find`, `.first()`, `os.environ.get`, a regex `match`, or a Go function whose second return is an error.

### Checked on one branch, unwrapped on the other

The author knew the value could be absent — one path proves it. The sibling path is the finding.

```python
if config.timeout is not None:
    sock.settimeout(config.timeout)
retries = config.retries + 1    # same Optional shape, no check
```

Also flag: a check in the caller and none in the callee that receives the same value, and a check on the first use with the rest of the function assuming it held.

### Truthiness standing in for a presence check

`if value:` is false for `0`, `0.0`, `""`, `[]`, `{}` and `False`. Where those are real values, the test reports present data as missing.

```python
# BAD: a discount of 0 and a count of 0 take the default
discount = payload.get("discount") or DEFAULT_DISCOUNT
```

The fix is `is None` (Python), `?? `(JavaScript/TypeScript), or an explicit key-presence test. Flag `or`-fallbacks and `if not x` guards on numeric, string and collection fields where zero or empty is legal.

### A default that hides the absence

`dict.get(key, fallback)` and `getattr(obj, name, fallback)` turn a missing key into a plausible value, so the miss reaches storage or a decision unannounced. Flag defaults that are indistinguishable from real data — `0` for a balance, `""` for a name, `[]` for a permission list.

### `Any` that ends type checking at a boundary

One `Any` at an ingestion point — a request payload, a parsed JSON response, a config loader, a `**kwargs` bag — turns every downstream annotation into decoration. The checker stops there and reports nothing about the twenty call sites after it.

```python
# BAD: everything derived from `payload` is unchecked from here on
def handle(payload: Any) -> Response:
    return charge(payload["amount"], payload["currency"])
```

Flag `Any` (Python), `any` and `object` (TypeScript), `interface{}`/`any` (Go), and `Record<string, any>` at the seam where external data enters. Internal helpers matter less than boundaries.

### The suppression on the line that would have caught it

`# type: ignore`, `as any`, `!` (TypeScript non-null assertion), `.unwrap()`, `.get()` on an empty `Optional`, `@ts-expect-error` and `# noqa` sit exactly where the checker objected. Read what it objected to.

```python
value = cache.get(key)  # type: ignore[union-attr]
value.refresh()         # the ignore is the bug report
```

Flag a bare `# type: ignore` with no error code, a suppression with no adjacent reason, and `.unwrap()`/`!` on anything derived from I/O, user input or a lookup.

### Signals

- `Optional[`, `| None`, `?:`, `?.`, `??`, `*mut`/pointer returns, `sql.NullString`
- `.get(`, `.find(`, `.first(`, `.pop(`, `getenv`, `match(`, `head`
- `type: ignore`, `as any`, `@ts-expect-error`, `!.`, `.unwrap()`, `.expect(`
- `: Any`, `-> Any`, `: any`, `interface{}`, `Record<string, any>`
- An `if x:` guard on a field the schema types as a number or a string

### NOT a finding (skip these)

- A value a preceding line proves present — an assignment, an `assert`, an early `raise`, a narrowing `if` the checker follows
- `dict.get(key)` whose result is only tested, counted or passed to something that accepts absence
- A sentinel default that cannot collide with real data (`-1` for an index, a module-level `MISSING` object)
- `Any` in a decorator, a test double, or a `*args`/`**kwargs` pass-through that never reads the values
- `.unwrap()` in a test, a script, or immediately after a construction that cannot fail
- A dynamically typed codebase with no type checker configured — flag the absent check, not the missing annotation

## How to Scan

1. **Find the producers**: `-> Optional`, `| None`, `return None`, functions with a `not found` branch — list what each returns on the miss
2. **For each producer, search its call sites** — does the next line check, or dereference?
3. **Search for truthiness guards** on numeric and string fields: `if not `, ` or DEFAULT`, `if value:`
4. **Search for suppressions**: `type: ignore`, `as any`, `@ts-expect-error`, `!.`, `.unwrap()` — read the line under each one
5. **Search for `Any`/`any` in signatures** and mark which ones sit at an external boundary
6. **Check the two branches of every `is None` / `!= nil` test** — does the else path use the same value?
7. **Check the type-checker config** (`mypy.ini`, `pyproject.toml`, `tsconfig.json`) — `strict`, `strictNullChecks`, `no_implicit_optional`. A disabled flag makes the whole codebase one finding, not fifty
8. **Check external boundaries first**: request handlers, API clients, config loaders, env reads, deserializers

## Report Findings

For each instance:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Type** | Unchecked return / Asymmetric branch / Truthiness test / Hiding default / Boundary `Any` / Suppression |
| **Producer** | Where the absence comes from (file:line and what it returns on the miss) |
| **Consequence** | What the absent value does here — crash, wrong branch, value written, permission granted |
| **Fix** | The concrete check, the narrowed type, or the annotation that replaces the suppression |

### Severity Guide

- **Critical**: An absent value reaches a write, a payment or an authorization decision — `None` stored as data, or a missing permission read as allowed
- **High**: A possibly-absent return dereferenced on a production path; `Any` or a suppression at an external boundary, which ends checking for everything downstream
- **Medium**: Truthiness standing in for presence where `0` or `""` is legal; one branch checked and its sibling not; a default indistinguishable from real data
- **Low**: Suppressions on internal code whose absent case is unreachable; missing `Optional` annotations no caller depends on

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Type | Consequence | Fix |
|---|----------|-----------|------|-------------|-----|
| 1 | High | path:line | Unchecked return | AttributeError when the id is unknown | Return early on `None` before reading `.email` |

## Rules

- **Name the producer before flagging a consumer** — cite the file:line that can return absent. A call site with no absent case is not a finding.
- **`error-gaps` owns the producer; this lens owns the consumer.** A function that catches and returns `None` so callers cannot tell it failed is theirs. What the caller then does with that `None` is yours. When both are wrong, report the call site and name the producer in the finding.
- **`type-structs` owns the shape; this lens owns the checking around it.** A `-> dict` whose fields nobody names is theirs — the fix is a dataclass. An `Any` or a suppression that stops the checker is yours — the fix is a type or a check.
- **Judge by the language's idiom** — Go pairs a value with `ok`/`err` and ignoring the second is the finding; Rust has `Option` and `unwrap` is the finding; TypeScript needs `strictNullChecks` on before any of this is checkable.
- **A disabled checker is one finding, not fifty** — if `strictNullChecks` is off or `mypy` runs in permissive mode, report the config once at High and cite two or three consequences, rather than every unchecked site.
