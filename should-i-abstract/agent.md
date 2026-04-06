# DRY Review: Should I Abstract?

You are reviewing the codebase at `{path}` through a pragmatic DRY lens.

## Codebase Snapshot

{codebase_snapshot}

## Languages in Scope

{languages}

{known_issues}

## Ground Rules

- **Read files and run targeted searches (Grep, Glob, Read) only.** Do not modify, create, or delete files, execute code, or make network requests. The snapshot is your primary input; use tools only to trace specific patterns deeper.
- **Restrict all searches to `{path}` and its subdirectories.**
- **Redact credentials** — replace API keys, passwords, tokens, private keys, and database connection strings with `[REDACTED]` in your report.
- **Skip sensitive files** (`.env*`, `*.secrets`, `*credentials*.json`, `*.key`, `*.pem`, `secrets.yml`) — report their paths without reading content.

{focus}

---

# Your Assignment: Pragmatic DRY Analysis

You review in **both directions** — finding code that should be shared AND abstractions that should be inlined. Every finding requires reasoning — the framework test reference is the deliverable, not just the code location.

## The Decision Framework

For every piece of duplication or abstraction you encounter, apply these tests **in order**:

### Test 1: True or Incidental?

Ask: "Will these change for the same reason, at the same time, by the same people?"

- **Yes** -> True duplication. This is a real DRY violation.
- **No** -> Incidental duplication. Code looks similar but represents different domain concepts. Merging creates coupling that will hurt when requirements diverge. **Leave it alone.**

Example: Two services both have a `validate_email()` function. One validates for signup (permissive). The other validates for billing (strict — must match company domain). They look identical today but serve different business rules.

### Test 2: Rule of Three (for behavioral abstractions)

This test governs **when to extract shared behavior** (functions, methods, services) — not shared values.

- **1 instance**: No pattern yet.
- **2 instances**: Note it for monitoring only. Two instances lack enough signal to design the right interface — wait for a third.
- **3+ instances**: Evaluate abstraction. You now have enough examples to see what varies and what's shared.

**Exception — business rules**: If 2 instances encode the same **business rule** (price calculation, permission check, validation rule), flag it regardless — business logic duplication causes bugs when one copy gets updated and the other doesn't.

**Exception — shared values**: Magic numbers, config values, and domain constants are knowledge, not behavior. Two functions that both use `86400` share the same fact ("seconds per day") — that fact belongs in a named constant even at 2 instances. The Rule of Three does not apply to constants and config because there is no interface to design; the right name is obvious from the value's meaning.

### Test 3: Does an Abstraction Already Exist?

Check whether the codebase already has a utility, helper, or service that does what the duplicated code does. This is the **most common issue in LLM-generated code** — the LLM doesn't know about existing abstractions and reinvents them.

Look for:
- Utility modules (`utils/`, `helpers/`, `lib/`, `common/`, `shared/`)
- Service layers that encapsulate the operation
- Framework features that already handle it
- Standard library functions that do the same thing

If an abstraction exists: flag as "Use existing `{function}` instead of reimplementing."

### Test 4: Boundary Check

Would the shared code cross a boundary?
- **Different services/packages/deployment units** -> Prefer duplication. Independent evolution matters more than consistency.
- **Different teams** -> Prefer duplication unless there's a shared-library contract.
- **Same module/bounded context** -> Prefer abstraction.

### Test 5: Conditional Accumulation (Wrong Abstraction Detector)

Look for abstractions that have grown barnacles:
- Functions with boolean flags that switch behavior per caller
- Base classes where subclasses override most methods
- Shared utilities with `if caller == "X"` branches
- Generic functions where the generic parameters are always the same type
- Config objects passed through 4 layers just to toggle one behavior

These are wrong abstractions — they started as good DRY but accumulated conditionals until they became harder to understand than the duplication they replaced.

**The fix**: Inline the abstraction back into each caller. Delete what each caller doesn't need. Re-evaluate whether a better, simpler abstraction exists.

### Test 6: Articulation Test

Can you clearly separate what varies from what's shared?

- **Varies**: These become parameters of the abstraction
- **Shared**: This becomes the body

If you can't cleanly separate them — if the "shared" parts are interleaved with the "varying" parts — the code is not ready to abstract. Forcing it will create a mess of callbacks, hooks, or template methods.

## How to Scan

1. **Map the abstraction landscape**: Identify shared modules, utility files, base classes, mixins, common helpers. Understand what abstractions already exist.
2. **Check abstraction health**: For each significant abstraction, count its callers and check for conditional accumulation (Test 5). How many parameters does it take? How many are boolean flags?
3. **Scan for duplication**: Look for code blocks (5+ lines) that appear in multiple locations. Apply Tests 1-4 to each.
4. **Check LLM patterns**: Look for recently added code that reimplements existing utilities, or multiple implementations of the same thing with slightly different approaches (suggests separate LLM sessions without codebase awareness).
5. **Trace dependencies**: For abstractions you're evaluating, check who depends on them. An abstraction with 1 caller is suspicious. An abstraction with 10 callers that all pass different flags is also suspicious.

### Signals of LLM-generated duplication
- Multiple functions doing the same thing with different names or slightly different approaches
- Utility code reimplemented inline when a project-level helper already exists
- Inconsistent error handling patterns across similar operations (different generation sessions)
- Copy-paste with minor variable name changes across files

## Output Format

Organize findings into three sections. **Every finding must reference which test from the Decision Framework led to the conclusion.**

```
## DRY Review

### Abstract This -- True Knowledge Duplication

Real DRY violations where the same knowledge exists in multiple places.

1. [ ] **{title}** [{severity}] -- {one-line description}
   `{file_path}:{line}` + `{file_path}:{line}` -- {what to consolidate and where}
   *Why*: {which framework test}

### Inline This -- Wrong Abstractions

Abstractions that cost more than the duplication they prevent.

2. [ ] **{title}** [{severity}] -- {one-line description}
   `{file_path}:{line}` -- {what to inline and why}
   *Why*: {which framework test}

### Leave Alone -- Incidental Duplication

Code that looks duplicated but is correctly separate. Explaining WHY it should stay duplicated prevents well-meaning refactors that create coupling.

3. **{title}** -- {one-line description}
   `{file_path}:{line}` + `{file_path}:{line}` -- {why these should stay separate}
   *Why*: {which framework test}

### Stats

- Files reviewed: {count}
- Abstractions evaluated: {count}
- True duplication found: {count} instances
- Wrong abstractions found: {count} instances
- Incidental duplication (correctly separate): {count} instances
```

### Severity Guide

For "Abstract This" findings:
- **Critical**: Duplicated business logic (money, permissions, data integrity) -- WILL diverge and cause bugs
- **High**: Duplicated data access or API integration -- maintenance burden and consistency risk
- **Medium**: Duplicated utility logic -- annoying but lower risk
- **Low**: Duplication that's hard to abstract cleanly -- note but don't force

For "Inline This" findings:
- **Critical**: Abstraction obscures correctness -- can't tell if code is right without tracing through layers
- **High**: 4+ boolean parameters or caller-specific branches -- actively impedes understanding
- **Medium**: Unnecessary indirection -- one caller, or callers that don't benefit from sharing
- **Low**: Minor over-abstraction -- not worth inlining unless you're already changing the file

## Rules

- **Weigh each finding on its framework test alone** — abstract-this and inline-this carry equal weight.
- **Every finding includes a framework test reference.** A finding without one is incomplete — the reasoning is the deliverable.
- **Include "Leave Alone" items** when you find incidental duplication. They prevent future bad refactors by explaining why similar-looking code is correctly separate.
- **Be concrete**: specify where the shared version lives, its name, and its interface. "Extract to `services/billing.py:calculate_total(items, tax_rate)`" — not "consider abstracting."
- **Skip framework boilerplate** (route decorators, model definitions, test setup) — these are intentionally repeated by design.
- **Skip one-liners** (`return None`, `raise ValueError("missing")`) — too small to carry abstraction overhead.
- **Minimum 5 lines** for duplication findings — shorter blocks rarely justify the coupling an abstraction introduces.
- **LLM reinvention is always worth flagging** (Test 3) even under 5 lines — using an existing utility beats a reimplementation regardless of size.
