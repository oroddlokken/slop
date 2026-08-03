# Find the Assistant Vocabulary in Strings a User Reads

Scan the interface for the writing habits of AI chatbots: the vocabulary, sentence shapes, and formatting tics that assistants produce by default. The problem is not that a machine wrote the line. The problem is that machine defaults regress to the statistical middle, so specific facts get smoothed into generic filler and the user skims past having learned nothing.

`comment-cop` runs a version of this lens over comments. Yours is harder in one way and easier in another. Harder: a user cannot open the code to find out what the sentence was standing in for, so a vague string on a screen is a dead end rather than a detour. Easier: interface strings are short, so a single vague word is a larger fraction of the sentence and the fix is usually visible.

Judge the word by what it earns. "Sampled every 60 seconds" is a fact. "Updated in real time" is a mood.

Source for much of the pattern list: [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), adapted here for interface copy.

## What to Look For

### The overused vocabulary

Flag a use only when deleting the word costs the sentence nothing.

- Core AI-vocabulary set: `additionally` (sentence-initial), `align with`, `boasts`, `crucial`, `delve`, `enhance`, `fostering`, `highlight` (verb), `interplay`, `intricate`, `key` (adjective), `landscape` (abstract), `meticulous`, `pivotal`, `robust`, `showcase`, `tapestry`, `testament`, `underscore` (verb), `valuable`, `vibrant`
- Product-copy additions: `seamless`, `powerful`, `intuitive`, `effortless`, `smart`, `intelligent`, `comprehensive`, `rich`, `elegant`, `blazing fast`, `next-level`, `game-changing`, `first-class`, `enterprise-grade`
- Softeners applied to things the user may not find soft: `simply`, `just`, `easily`, `quickly`, `clearly`, `obviously`, `of course`, `straightforward`. In an interface these are worse than in prose: telling a user a step is simple, at the moment they are failing it, is an insult with no information in it
- Inflated verbs where a plain one fits: `leverage`, `utilize`, `orchestrate`, `harness`, `unlock`, `empower`, `facilitate`, `streamline`, `optimize` used vaguely
- Unearned intensity: `crucial`, `vital`, `essential`, `critical`, `important` as bare adjectives with no consequence stated
- `graceful`/`seamlessly` outside a precise technical sense

The set drifts by model generation; treat it as a sample, not a law. Weight a *cluster* far above any single hit. One of these words on a screen means nothing. Four in a paragraph is the tell.

### Copulative avoidance

Assistants dodge plain `is`/`are`/`has`: `serves as`, `stands as`, `functions as`, `represents`, `features`, `offers`, `provides`, `allows you to`, `enables you to`.

- "This page serves as your central hub for…" → say what is on the page
- "The dashboard offers a real-time view" → "Updated every 60 seconds"
- "Allows you to filter by label" → the filter is right there; delete

### Negative parallelism

- "Not just X, but Y" / "Not only X but also Y"
- "It's not X — it's Y"
- "no X, no Y, just Z"

The construction implies the user held a wrong belief the app is now correcting. On a screen, state Y and stop.

### Rule of three

Triads where one item carries the meaning: "fast, simple and reliable"; "track, analyse and improve". Assistants reach for the triad to make thin copy look thorough. In a heading it is almost always three words where one noun would do.

### Editorial and didactic filler

- "Note that…", "It's worth noting that…", "Keep in mind…", "Please be aware that…"
- "In other words,…" restating a sentence that was already clear
- "This ensures that…" / "This allows us to…" / "This means that…" opening a sentence that then restates the control
- Present-participle tails: "…, ensuring your data stays in sync", "…, giving you full visibility". These almost never carry a checkable claim
- Hedge stacking: "generally, in most cases, typically" in one sentence

### Promotional register

Marketing voice on a working screen: "your all-in-one solution", "a powerful and flexible way to", "designed to make your life easier", "commitment to your privacy". A screen should say what it shows and what the user can do.

Also puffed-up significance: "a smarter way to think about your data", "putting you in control". Overlaps `self-justification` — the praise is theirs, the vocabulary is yours.

### Formatting tells in rendered copy

- Em dashes at a rate no human sustains, especially several in one short string, or spaced (` — `) where the app's other copy does not space them
- Title Case On Every Heading where the app uses sentence case, or the reverse
- Emoji as structure (✅ ⚠️ 🚀) leading headings or empty states in an app that has none elsewhere
- Curly quotes and apostrophes in strings a user will copy — a command, a config snippet, an example key. Beyond being a tell, they break the paste
- Bold-lead vertical lists (`- **Thing**: description`) rendered in body copy where a sentence or a plain list fits

### Chat residue and placeholders in rendered strings

Close to proof rather than suspicion. Any of these on a screen is a High.

- "Would you like me to…", "Let me know if…", "I hope this helps", "Certainly!", "Here's the updated…"
- "As of my last update…", "based on available information", "not widely documented"
- Unfilled placeholders left in copy: `[Add description here]`, `<your-api-key>`, `2025-XX-XX`. Note the overlap with `scaffold-filler`, which owns generator boilerplate; residue from a chat session is yours
- Tool artifacts: `contentReference`, `oaicite`, `turn0search0`, `[cite: 1]`, `(start_span)`, `【85†L261-269】`, `utm_source=chatgpt.com` on a link the user clicks

### Elegant variation across a screen

Assistants rename the same thing mid-paragraph to avoid repetition. In an interface this breaks the mapping between the copy and the controls: a hint calling something "your entry", then "the record", then "this item", when the button says "Entry". Say `entry` three times.

## What NOT to Flag

False positives here are expensive, because the accusation is about authorship and because over-correction makes the text worse. A rewrite that strips a real fact to satisfy a style rule is a net loss.

- **Plain prose.** `is`, `are`, `has`, short sentences. These point away from machine authorship
- **Good grammar.** Many people write well
- **Superlatives and definite claims** ("the only source", "always local"). Assistants hedge; humans commit — though check the claim against the view, and route a false one to `contradicts-view`
- **Correct technical terms in their precise sense**: graceful shutdown, idempotent, real-time where the transport actually is
- **Em dashes alone**, especially unspaced, especially where the app's older copy already used them
- **House style the humans chose.** If the app's pre-existing copy is full of sentence-case headings and spaced dashes, that is the convention
- **Marketing copy on a marketing surface**, judged by specificity rather than by warmth. Flag "powerful and flexible"; leave "tracks 40 repos across 3 hosts"
- **Emoji the app uses consistently** as part of its established voice
- **A string that is slop *and* false.** The falsehood is the finding. Hand it to `contradicts-view`

Non-native English writers are also taught to avoid word repetition and to prefer formal register. Weigh clusters and residue over any single stylistic hit.

## How to Scan

1. **Grep the artifact and residue list first.** Those hits need no judgment.
2. **Grep for curly quotes and spaced em dashes** across the inventory, and check any copyable string (commands, keys, examples) for smart punctuation.
3. **Grep the vocabulary set** case-insensitively with word boundaries. The grep produces candidates; the reading produces findings.
4. **For each candidate, delete the word mentally.** If the sentence loses nothing, that is the finding. If it loses a fact, keep it.
5. **Score density per string, not per screen.** Interface strings are short, so two tells in one sentence is already a cluster.
6. **Read all headings as a set, and all button labels as a set.** Assistant-written batches share a formula; repetition across many screens is one systemic finding, not twenty.
7. **Check symbol-to-copy mapping**: does the hint call the thing what the button calls it?
8. **Compare against the app's older copy** (`git log -S` or an early tag) to establish the house baseline before calling anything a deviation.

## Report Findings

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Tic** | Vocabulary / copulative / parallelism / rule-of-three / filler / promotional / formatting / residue / artifact / variation |
| **The word or shape** | Quote the fragment |
| **What it hides** | The concrete fact the phrase stands in for, or "nothing — cut it" |
| **Suggestion** | The rewritten string, or "delete" |

### Severity Guide

- **High**: Chat residue or a tool artifact rendered to a user. A curly quote inside a string the user is meant to copy. A vague intensifier standing where a real property belongs on a screen the user makes a decision on.
- **Medium**: A systemic pattern across screens — a shared heading formula, sustained promotional register, batch-written hints. Report once with a count. Also elegant variation that breaks the copy-to-control mapping.
- **Low**: An isolated word, one throat-clearing opener, a single decorative flourish.
- Never **Critical**: style is not safety. Route falsehoods to `contradicts-view`.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | High | settings.html:64 | Curly apostrophe inside the copyable config example; the paste fails | Replace `’` with `'` |
| 2 | Medium | 9 templates | Every panel intro opens "This section allows you to…" | One systemic rewrite: open with the noun and the count |
| 3 | Low | index.html:229 | "powers the predicted path" — no mechanism, no source | "The projection uses your 14-day trend." |

## Rules

- **Word lists are candidates, not verdicts.** Every word here has a legitimate use. Flag the use, never the word. A finding must say what the phrase was standing in for.
- **Density decides.** Never open a finding on a single stylistic hit unless it is residue or a tool artifact.
- **Propose the replacement string.** "Too AI-sounding" is not a finding. The rewritten line is.
- **Do not speculate about authorship in the report.** Write about the string. "This hint states no checkable fact" is useful; "this was written by ChatGPT" is an accusation you cannot support and it makes the finding easy to dismiss.
- **Batch systemic patterns.** Twenty hints from one generation pass is one Medium with a count, not twenty Lows.
- **Content beats vocabulary.** A hint naming a real limit is worth keeping even if it says "seamless" while doing it. Suggest tighter wording, keep the fact, rate it Low.
- **Style ranks below truth.** When a string is both slop and false, the falsehood is the finding — hand it to `contradicts-view` and let your note ride along. Never launder a false claim into more convincing prose.
- **Write the finding in plain prose.** A report about machine tics that is itself full of them is worthless.
