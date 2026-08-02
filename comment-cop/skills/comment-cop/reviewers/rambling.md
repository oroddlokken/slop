# Find Rambling Prose

Scan for comments and docstrings that say in five paragraphs what belongs in one line. The target is self-indulgent narrative: essays, storytelling, and over-explanation that bury the one fact a reader actually needs. A comment is prose that has to earn its length — most of it does not.

## What to Look For

### Essay-length module/class docstrings
- Module docstrings that read like a blog post or design-doc excerpt — multiple paragraphs of backstory before (or instead of) stating what the module does
- Narrative framing: "Today this carries only…", "An operator who accepts that state wants…", "The canonical case is…" — story about a hypothetical user or scenario where a spec would do
- The same point made two or three ways in one docstring ("so nothing is hidden, only de-escalated" restating "keep the raw signal")

### Over-explanation of the obvious mechanism
- Paragraphs explaining a standard-library idiom, a well-known pattern, or how a language feature works
- Walking through control flow line by line in prose when the code is already linear and readable
- Justifying a design at length where a one-line pointer ("resolved from the package, not CWD — see entra.py") suffices

### One rationale re-argued at every call site

A constraint gets explained where it is defined, and then explained again in every function, test and template that observes it — fifteen paragraphs of the same argument, each slightly reworded. The rationale is real; the repetition is the finding. Flag the copies, keep the canonical statement at the place the constraint lives, and leave the observers bare or with a bare pointer to the symbol.

The tell is a phrase that recurs across files: the same constraint named the same way in a dozen docstrings. Grep the distinctive noun phrase and count the sites.

### Prose that should be structure
- A wall of prose describing a resolution order / fallback chain that a 3-item numbered list would convey faster
- Long inline comments that would be clearer as a short docstring, or vice versa

### Throat-clearing
- Comments that restate the section they precede in florid terms before getting to the point
- "It is worth noting that…", "Importantly,…", "Note that it should be mentioned…" padding

## How to Scan

1. **Measure prose-to-signal ratio.** For each docstring/block comment, ask: what is the single fact a maintainer needs? How many sentences deliver it? If it is 1 fact in 6 sentences, flag the 5.
2. **Read the first sentence, then the rest.** If the first sentence already tells you what the thing does and the rest is backstory, the rest is the finding.
3. **Look for narrative verbs and framing** — "wants", "the canonical case", "today", "imagine", "you might think".
4. **Spot triple-explanation** — the same rationale appearing in a module docstring, a nearby comment, and a class docstring. (Cross-layer repetition is partly `restates-code`/`noise` territory — here, flag the *volume*, coordinate on the location.)
5. **Distinguish density from rambling.** A dense docstring packed with distinct facts a maintainer needs is NOT rambling — it is good. Rambling is *low information per word*.

## Report Findings

For each rambling comment/docstring:

| Field | Content |
|-------|---------|
| **Location** | file:line range of the prose |
| **Length** | Approx. sentences/lines of prose vs. the ~1 that carries the signal |
| **The one fact** | The single thing the reader actually needs |
| **Suggestion** | The tightened version, or "cut to: `<one line>`" |

### Severity Guide

- **Medium**: A module/class docstring so long the actual contract is buried — a reader has to mine paragraphs to learn what the thing does.
- **Low**: Ordinary verbose comments, throat-clearing, over-explained standard idioms.
- Never **High/Critical**: rambling wastes reading time; it does not mislead. If prose is *also* wrong, that is `contradicts-code`, not this lens.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | Medium | config.py:1-19 | 19-line module docstring; contract ("loads [diagnosis] suppression, best-effort, re-read per request") is 2 lines, rest is narrative | Cut to the 2-line contract plus the one gotcha (re-read per request); drop the backstory |

## Rules

- **Propose the tightened text, don't just say "too long."** Show the one-line replacement.
- **Never delete a fact — only cut words.** If the ramble contains a real gotcha, preserve the gotcha in the shortened version. When unsure whether a sentence carries a fact, keep it and flag only the clearly redundant parts.
- **Respect the project's own norm.** If every docstring in the codebase is a paragraph, a two-paragraph one is the outlier — calibrate to the house style, flag the excess above it.
- **A short comment is never rambling.** This lens is about volume; one-line redundancy belongs to `restates-code`.
- **Length is not proof of care.** Comment volume tracks how hard the decision felt to write, not how surprising the code is to read. A decision that took a day and a decision that took a minute get the same one line if they are equally non-obvious on the page.
