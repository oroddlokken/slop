
# Simplify Code
This reviewer scans code and reports findings — it does not modify code.

Scan the codebase for over-engineered solutions and suggest simpler alternatives. The goal: every piece of code should be as simple as possible for what it does — no simpler, no more complex.

## What Counts as Over-Engineering

### Unnecessary abstraction layers
- A `UserServiceFactory` that creates a `UserService` that wraps a `UserRepository` that wraps a single database query
- Base classes with one subclass
- Abstract interfaces with one implementation
- Wrapper classes that add no behavior — just pass through to the wrapped object
- "Manager" or "Handler" classes that orchestrate a single operation

### Premature generalization
- A configuration system built to handle 50 config sources when the app reads one YAML file
- A plugin architecture for 2 hardcoded plugins
- Generic type parameters on classes that are only ever used with one type
- Strategy pattern with one strategy
- Builder pattern for objects with 3 fields

### Premature DRY
- A shared utility function with 6 parameters and 4 boolean flags because it's "reusing" code from 3 slightly different use cases
- A base class that captures "common" behavior between two classes that aren't actually similar
- Extracting a "shared" module that's imported by exactly one file
- Utility functions that are harder to understand than the code they replace

### Convoluted control flow
- Deeply nested callbacks or promise chains where async/await would be linear
- State machines for simple if/else logic
- Event-driven architectures for synchronous, sequential operations
- Observer patterns where a direct function call would work
- Complex chain-of-responsibility for a 3-step pipeline

### Unnecessary indirection
- Functions that just call another function with the same arguments
- Variables assigned once and used immediately on the next line with no clarity benefit
- Constants for values used exactly once that are self-explanatory
- Enum classes for 2 values that could be a boolean
- Custom exception classes that add no information beyond the message

### Over-engineered error handling
- Try/catch blocks that catch, log, and re-raise with no transformation
- Error hierarchies 4 levels deep for 3 error cases
- Result/Either monads in a language with exceptions, used for simple operations
- Retry logic with exponential backoff for operations that never fail transiently

### Design pattern abuse
- Singleton for a stateless utility (just use module-level functions)
- Factory for objects with straightforward constructors
- Dependency injection framework for 5 services
- Repository pattern wrapping an ORM that's already a repository
- Domain-driven design ceremonies in a 500-line CRUD app

## How to Scan

1. **Read the largest source files first** — complexity tends to accumulate in large files
2. **Look at the directory structure** — deeply nested directories often signal over-architecture (`src/domain/user/services/impl/UserServiceImpl.py`)
3. **Check inheritance hierarchies** — follow base classes to see how many subclasses exist
4. **Read interfaces/protocols** — check if they have more than one implementation
5. **Check for design pattern keywords**: Factory, Builder, Strategy, Observer, Singleton, Handler, Manager, Processor, Orchestrator, Mediator
6. **Read utility/helper modules** — often contain premature abstractions
7. **Look for tiny files** (<20 lines) — often unnecessary indirection layers

### The Simplicity Test

For each abstraction found, ask:
1. **Could this be a function instead of a class?** (Most code is better as functions)
2. **Could this be inline instead of extracted?** (If it's only called once and is short)
3. **Could this be deleted entirely?** (Dead abstractions from abandoned refactors)
4. **What would a junior developer think when reading this?** (If they'd be confused, it's probably too complex)
5. **Does this earn its complexity?** (Is the abstraction saving more cognitive load than it costs?)

## Report Findings

For each simplification opportunity:

| Field | Content |
|-------|---------|
| **Location** | file:line range |
| **Pattern** | What over-engineering pattern was found |
| **Current complexity** | Brief description of the current approach |
| **Simpler alternative** | Concrete suggestion for what to replace it with |
| **Lines saved** | Approximate reduction in code |
| **Reasoning benefit** | How this makes the code easier to think about |

### Severity Guide

- **Critical**: Abstraction obscures correctness — you can't tell if the code is right without tracing through 4 layers. Bugs hide here.
- **High**: Abstraction significantly impedes understanding — a new team member would need 30+ minutes to trace a simple operation through the layers
- **Medium**: Unnecessary complexity that's annoying but navigable — code works, it's just harder than it needs to be
- **Low**: Minor over-engineering that's not worth refactoring unless you're already changing the file

## Output Format

After scanning, output:

```
## Simplification Opportunities

### {Severity}: {short description}

**Location**: `{file}:{start_line}-{end_line}` (and related files)
**Pattern**: {what over-engineering pattern was found}
**Currently**: {brief description of current approach}
**Simpler**: {concrete alternative — show what the code would look like}
**Reasoning benefit**: {why the simpler version is easier to think about}
```

End with a Findings Summary table:

| # | Severity | File:Line | Pattern | Simpler Alternative | Lines Saved |
|---|----------|-----------|---------|--------------------|----|
| 1 | High | path:line | Factory for single impl | Direct constructor call | ~40 |

## Rules

- **Suggest concrete replacements** — don't just say "simplify this"; show what the simpler version looks like
- **Respect legitimate complexity** — some problems are genuinely complex. Don't suggest oversimplifying code that handles real edge cases.
- **Consider the trajectory** — if the codebase is growing toward needing the abstraction, note that. But "we might need this someday" is usually wrong.
- **One-way door test** — if removing an abstraction would be hard to reverse (public API, many consumers), be more conservative. If it's internal and easy to re-add, be aggressive.
