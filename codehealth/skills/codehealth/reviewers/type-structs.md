# Find Missing Type Structures
This reviewer scans code and reports findings — it does not modify code.

Scan the codebase for raw dicts, lists, and tuples being passed between functions that should be proper typed data structures. Raw data structures provide no documentation, no validation, and no IDE support — they're the #1 source of "what keys does this dict have?" confusion.

## What to Look For

### Dict-as-object anti-pattern
```python
# BAD: What keys does this dict have? Nobody knows without reading every caller.
def create_user(data: dict) -> dict:
    return {
        "id": generate_id(),
        "name": data["name"],
        "email": data["email"],
        "created_at": datetime.now(),
    }

user = create_user({"name": "Alice", "email": "alice@example.com"})
print(user["name"])  # KeyError if typo: user["nane"]
```

Should be:
```python
@dataclass
class User:
    id: str
    name: str
    email: str
    created_at: datetime
```

### Tuple unpacking without structure
```python
# BAD: What is result[0]? result[1]? Hope you remember the order.
def get_user_stats(user_id: int) -> tuple:
    return (total_orders, total_spent, last_order_date)

total, spent, last = get_user_stats(42)  # swap two and you'll never know
```

Should be: `NamedTuple` or `dataclass`

### Functions returning dicts with implicit schemas
```python
# BAD: The "schema" lives only in the programmer's head
def get_report() -> dict:
    return {
        "title": "...",
        "rows": [...],
        "summary": {"total": 0, "average": 0},
        "metadata": {"generated_at": "...", "version": 2},
    }
```

Should be: nested dataclasses or Pydantic models

### Dict-of-dicts and list-of-dicts
```python
# BAD: What's in each dict? Different dicts might have different keys.
users: list[dict] = fetch_users()
for user in users:
    print(user["name"])  # hope every dict has "name"
```

### **kwargs used as a config bag
```python
# BAD: What options are valid? What types should they be?
def configure_service(**kwargs):
    timeout = kwargs.get("timeout", 30)
    retries = kwargs.get("retries", 3)
    base_url = kwargs.get("base_url", "http://localhost")
```

Should be: a `@dataclass` or Pydantic `BaseModel` for configuration

### JSON responses used as raw dicts
- API responses parsed to `dict` and accessed by string keys throughout the codebase
- No model classes representing API response shapes
- String key access scattered across multiple files

### Signals for missing structures
- `data["key"]` or `data.get("key")` patterns — accessing dicts by string keys
- Functions with `-> dict` or `-> list` return types
- Functions accepting `dict` or `**kwargs` as primary arguments
- Type annotations using `Any`, `dict`, `list` without generic parameters
- Comments explaining dict structure (`# {"name": str, "age": int, ...}`)
- `TypedDict` (sometimes OK but often better as a dataclass)

## What to Replace With (Python)

| Current | Replace With | When |
|---------|-------------|------|
| `dict` with known keys | `@dataclass` | Default choice — simple, built-in, type-checked |
| Immutable dict-like | `NamedTuple` | When you need immutability and tuple features (hashable, unpacking) |
| Dict you can't control (JSON API) | `TypedDict` | When you're typing a dict you don't own (external API response, legacy code) |
| Dict with validation needs | `pydantic.BaseModel` | When data comes from external input and needs validation |
| Enum-like string sets | `enum.Enum` or `StrEnum` | When a field has a fixed set of valid values |
| Config dicts | `@dataclass` with defaults | When passing configuration between functions |

### For other languages
- **TypeScript**: `interface` or `type` instead of untyped `object` / `Record<string, any>`
- **Go**: `struct` instead of `map[string]interface{}`
- **Rust**: `struct` instead of `HashMap<String, Value>`
- **JavaScript**: JSDoc `@typedef` or TypeScript conversion

## How to Scan

1. **Search for dict access patterns**: `["key"]`, `.get("key"`, `kwargs.get(`
2. **Search for untyped return annotations**: `-> dict`, `-> list`, `-> tuple`, `-> Any`
3. **Search for dict construction**: `{"key": value}` returned from functions
4. **Search for `**kwargs` in function signatures** (excluding decorators and framework methods)
5. **Read function signatures** — functions accepting or returning bare `dict`/`list`
6. **Check API client code** — are responses typed or raw dicts?
7. **Check config/settings code** — is configuration structured or dict-based?

## Report Findings

For each instance:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Pattern** | Dict-as-object / Unstructured tuple / kwargs bag / Untyped response / etc. |
| **Currently** | What the code passes around (show the dict keys or tuple structure) |
| **Replace with** | Concrete dataclass/model definition |
| **Benefits** | What you gain — IDE autocomplete, type checking, self-documentation, validation |
| **Scope** | How many files access this structure |

### Severity Guide

- **High**: Dicts representing core domain objects (User, Order, Transaction) passed across module boundaries — these WILL have key typos and missing fields
- **High**: API response dicts accessed by string keys in 5+ files — any API change breaks silently
- **Medium**: Function return dicts with 4+ keys — hard to remember the schema
- **Medium**: Config/settings as raw dicts — no validation, no defaults documentation
- **Low**: Small dicts used locally within one function — not worth extracting if scope is tiny

## Output Format

After scanning, output:

```
## Missing Type Structures

### {Severity}: {short description}

**Location**: `{file}:{line}` (and {N} other files that use this structure)
**Pattern**: {Dict-as-object | Unstructured tuple | kwargs bag | ...}
**Currently**: {show the dict keys/tuple structure being passed around}
**Replace with**:
```python
@dataclass
class SuggestedName:
    field_1: type
    field_2: type
    field_3: type = default
```
**Benefits**: {autocomplete, type checking, self-documenting, validation}
**Scope**: Used in {N} files — {list the key files}
```

End with a Findings Summary table:

| # | Severity | File:Line | Pattern | Keys/Fields | Suggested Structure |
|---|----------|-----------|---------|-------------|-------------------|
| 1 | High | path:line | Dict-as-object | name, email, role | `@dataclass User` |

## Rules

- **Suggest concrete dataclass definitions** — show the full class with field names, types, and defaults
- **Don't over-structure** — a dict used once in a 5-line function doesn't need a dataclass
- **Consider the boundary** — dicts at module boundaries (function signatures, API responses) matter more than dicts internal to a single function
- **Respect existing patterns** — if the project uses Pydantic, suggest Pydantic models; if it uses dataclasses, suggest dataclasses
- **Group related dicts** — if 5 functions all pass around the same dict shape, that's one finding (one dataclass), not 5
