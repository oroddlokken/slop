# Find the Textbook Where a Number Belongs

Scan for strings that teach the user a domain concept when the screen could show the value. The shape is a paragraph explaining an equation, a physiological mechanism, an algorithm, or a statistical method, sitting next to the number that method produced.

The developer wrote it while implementing the formula, when the formula was the interesting thing. To the user it is not interesting: they want the number, and at most they want to know how far to trust it. A lecture answers a question they did not ask, in a place where they cannot study.

This is the lens with the highest false-positive risk in the set, because a hint that names a **half-life, a source, a margin, or a bound** looks exactly like a lecture and is the opposite of one. Read the section on what not to flag before you file anything.

## What to Look For

### The derivation

Prose walking through how a value was computed, when the value is already on screen.

- A paragraph explaining Katch-McArdle against Mifflin-St Jeor, why one is blind to body composition, and which is therefore more conservative — printed under the TDEE number
- "We take your last seven readings, weight them by recency, and divide by the sum of the weights."
- "Percentile is computed by ranking all entries and interpolating between the two nearest."

The derivation is the developer's working. The user wants the number and a trust bound.

### The concept primer

Text teaching a domain term the interface uses.

- "Body fat percentage is the proportion of your total mass that is fat tissue, as opposed to lean mass, which includes muscle, bone and water."
- "A webhook is a callback that a service sends when an event occurs."
- "Compound interest means interest earned on previously earned interest."

If a term needs defining, define it in five words in a tooltip on the term, or rename the term. A primer paragraph in body copy is a textbook page nobody opened a textbook for.

### The comparative lesson

Two methods, two estimates, and an argument about which to prefer — where the app has already chosen one.

The app picked the anchor. The user cannot switch it from this screen. Telling them the tradeoff without giving them the control is a lecture; if they *can* switch it, the sentence should be one line on the control, not a paragraph under the result.

### The method footnote that grew

A caveat that started as "±1 interval" and became four sentences on sampling theory. The first version was a bound. The current one is a lecture that contains a bound.

### Units and physiology explained rather than shown

- "One kilogram of body fat is approximately 7,700 kcal, which is why a 500 kcal daily deficit produces roughly half a kilo of loss per week."

There is a real constant in there. The fix is to show the projection, not to teach the arithmetic that produced it.

## What NOT to Flag

Each of the following looks like a lecture and is a keeper. Getting these wrong is the expensive error on this lens: strip them and the numbers on the screen become uninterpretable.

- **A trust bound.** "Accurate to within one poll interval." "±2%." "Sampled hourly." The user acts differently on a number they know is approximate. Always keep.
- **A named source.** "From the GitHub API", "self-reported", "measured 2026-04-12". Provenance is what lets a user weigh a number against another number.
- **A named method where two would give different answers.** If the app computes TDEE by Katch-McArdle and another app on the user's phone says something else, the method *name* explains the discrepancy. Keep the name, cut the tutorial. "Katch-McArdle, from your lean mass" is the target shape.
- **A parameter the user can change.** If the half-life is configurable, the hint naming it belongs next to the control.
- **A limit on the data.** "Sessions before viewer tracking are excluded." "Only weigh-ins in the last 90 days count."
- **A consequence that changes behaviour.** "Weighing in twice a day skews the trend; the same-day readings are averaged." That last clause is a fact the user needs.
- **A definition inside a term's own tooltip**, five words or fewer, on a term the interface invented.
- **Deliberate educational surfaces.** A help page, a glossary, a docs route, a first-run explainer. These are where lectures are supposed to live. If the app has one, your suggestion for the lecture is usually "move it there and link".

The test: **strip every sentence that does not name a unit, a source, a limit, or a consequence.** What survives is the hint. Usually it is one clause of a five-sentence paragraph. If nothing survives, the whole thing goes.

## How to Scan

1. **Find the longest strings in the inventory first.** Sort by length and start at the top; lectures are almost always the largest strings on a screen.
2. **Grep for teaching verbs and framings**: `is computed`, `is calculated`, `means that`, `refers to`, `is defined as`, `which is why`, `in other words`, `is known as`, `equation`, `formula`, `algorithm`, `estimate` used as a noun phrase.
3. **Grep for domain-term primers** — a sentence whose subject is a term and whose verb is `is`, appearing in body copy rather than a tooltip.
4. **For every candidate, run the strip test clause by clause.** Write down what survives before you write the finding. The surviving text is your suggestion.
5. **Check whether the number the lecture explains is on the same screen.** If it is, the lecture is redundant to it. If the number is *not* shown, the finding may invert: the fix is to show the number.
6. **Check whether a help or docs surface exists.** If yes, propose moving rather than deleting.
7. **Look for the paired lecture** — the same lesson taught in two paragraphs on one screen. Note it and hand the duplication to `redundancy`; you own the length of each.

## Report Findings

For each lecture:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Length** | Sentence count, versus the clause that carries the fact |
| **Survives the strip test** | The unit / source / limit / consequence found inside, or "nothing" |
| **Where the number is** | The element on screen that already shows the value |
| **Suggestion** | The surviving clause as a one-line replacement, or "delete", or "move to /help and link" |

### Severity Guide

- **Medium**: A multi-sentence lecture in the primary reading path — under a headline number, at the top of a screen, in a form the user is filling in. The user has to mine the paragraph to find the bound.
- **Low**: A lecture in a tooltip or a collapsed panel the user opts into. It is still wrong, but it is not in the way.
- Never **High/Critical**: a lecture wastes attention; it does not mislead. If the lesson contradicts the computation, that is `contradicts-view`.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | Medium | profile.html:52 | 4-sentence lesson on Katch-McArdle vs Mifflin-St Jeor under the TDEE number; the only facts are the method name and the body-fat source | Cut to: "Katch-McArdle, from your lean mass (body fat {{ pct }}%, measured {{ date }})." |
| 2 | Low | weight.html:42 | 5 sentences on time-aware moving averages; the bound is "~6.6-day half-life" and the consequence is same-day averaging | Cut to: "Smoothed, ~6.6-day half-life. Same-day weigh-ins are averaged first." |

## Rules

- **Run the strip test and show your work.** Every finding names what survived. A finding that says "too long" without the surviving clause is not usable.
- **Never delete a bound, a source, or a unit.** This is the one way this lens does real damage. When you are unsure whether a clause is a bound, keep it.
- **Propose the replacement line verbatim.** Write the sentence you want on the page.
- **Length alone is not the finding.** A long string that is all facts is a good string. Count facts, not words.
- **A method name is not a method lecture.** Keep the name; cut the explanation of the name.
- **If the lesson is needed, move it.** Help page, docs route, or a disclosure the user opens. Deleting a real explanation because it is in the wrong place loses information; relocating it does not.
