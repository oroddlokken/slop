# Find Transient / Rot-Prone Prose

Scan for comments and docstrings engineered to go stale: they bake a *moment in time* into permanent prose. Live-instance names, ticket ids, dates, author names, and "recently/new" framing are all correct the day they are written and misleading soon after. The fix is almost always to generalize or delete the transient specific, keeping the durable point.

## What to Look For

### Live-instance anecdotes
- Naming a specific running resource as an example: "e.g. the live skybank-savings Deployment reporting `require-oci-author-label-minimal` / `error` … against `dokken.azurecr.io`"
- Specific customer/tenant/user names, environment hostnames, cluster names, IPs used as illustrative examples
- "As of the current prod state…", "currently the only workload that…" — snapshots of a mutable world

### Ticket / issue references inline in prose
- `chartroom-3x49`, `JIRA-1234`, `#4567` embedded in docstrings and comments as the *explanation* ("de-escalated (chartroom-3x49)")
- These belong in git history / the tracker, not as permanent code prose; they rot when the tracker changes and mean nothing to a future reader without access

### Temporal framing
- "recently added", "new in this version", "the old behaviour", "for now", "temporarily", "will be removed soon" with no date or version — permanently "recent"
- "matching the prior behaviour" — prior to what? unresolvable later

### Names and dates
- Author attributions in comments ("added by X", "per Y's request") — git blame owns this
- Hardcoded dates that will read as stale ("last checked 2024-…") unless the comment's whole purpose is a freshness marker

### Version/environment specifics that drift
- "on Python 3.11 this…", "the current LiteLLM schema…" stated as permanent when it tracks a moving dependency

## How to Scan

1. **Search for proper nouns in comments** — capitalized resource names, service names, registries, hostnames. Ask: will this name still exist / be relevant in a year?
2. **Grep for ticket patterns** in comments/docstrings: `[a-z]+-[0-9a-z]{3,}`, `#\d+`, `JIRA-`, project prefixes.
3. **Grep for temporal words**: `recently`, `currently`, `new`, `old`, `now`, `soon`, `temporarily`, `for now`, `as of`, `prior`, `used to`.
4. **Find dates and names** in comments.
5. **For each hit, separate the durable point from the transient carrier.** "A can't-evaluate is an infra problem, not a policy violation" is durable; "(chartroom-5dbt)" and "the live skybank-savings Deployment" are transient carriers of it.

## Report Findings

For each transient element:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Transient element** | The specific name / ticket / date / temporal phrase |
| **Rots when** | What change makes it wrong or meaningless (instance renamed, ticket closed, time passes) |
| **Durable point** | The lasting idea to keep |
| **Suggestion** | Generalize (e.g. "an image-policy evaluation error") or move the ticket to the commit / tracker |

### Severity Guide

- **Medium**: A concrete live-instance anecdote presented as a durable example — will actively mislead once that instance changes; and pervasive ticket-id litter across many docstrings (systemic).
- **Low**: A single stray ticket id, an author name, a "recently" with no other harm.
- Rarely **High**: only when a temporal claim ("this is safe *for now* because X holds") will read as a permanent guarantee after X stops holding.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | Medium | policy.py:4-8 | Docstring names a live workload ("skybank-savings Deployment … dokken.azurecr.io") as the example | Generalize to "a workload whose image-verification rule errors on registry auth"; drop the instance name |

## Rules

- **Keep the lesson, cut the timestamp.** Every fix preserves the durable point and removes only the rot-prone carrier.
- **Group systemic litter.** "Ticket ids inlined in 14 docstrings" is one finding listing locations, not 14 findings.
- **A dated freshness marker is legitimate** when the comment's job is to record when something was verified (e.g. a `LAST_CHECKED` pricing note). Don't flag those — flag dates masquerading as permanent facts.
- **Don't flag stable identifiers** — a public API name, an env var, a config key, a standardized annotation string are not transient. Transient = tied to a mutable instance or moment.
