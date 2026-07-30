# Find LLM-Generated Prose Tics

Scan comments, docstrings and markdown for the writing habits of AI chatbots: the vocabulary, sentence shapes, formatting quirks and leftover chat residue that assistants produce by default. The problem is not that a machine wrote the line. The problem is that machine defaults regress to the statistical middle, so specific facts get smoothed into generic filler, and a reader skims past it having learned nothing.

Judge the word by what it earns. "This lock is held across the retry" is a fact. "This lock is critical" is a mood.

Source for much of the pattern list: [Wikipedia:Signs of AI writing](https://en.wikipedia.org/wiki/Wikipedia:Signs_of_AI_writing), the most carefully evidenced catalogue available, adapted here for code comments and repo docs.

## What to Look For

### The overused vocabulary

Each of these is a real word that got mechanically repeated until it stopped carrying information. Flag a use only when deleting the word costs the sentence nothing.

- Wikipedia's core AI-vocabulary set: `additionally` (sentence-initial), `align with`, `boasts`, `bolstered`, `crucial`, `delve`, `emphasizing`, `enduring`, `enhance`, `fostering`, `garner`, `highlight` (verb), `interplay`, `intricate`/`intricacies`, `key` (adjective), `landscape` (abstract), `meticulous`, `pivotal`, `robust`, `showcase`, `tapestry`, `testament`, `underscore` (verb), `valuable`, `vibrant`
- Coding-assistant additions: `load-bearing`, `seam`, `surface area`, `blast radius`, `belt and suspenders`, `sharp edge`, `foot-gun`, `battle-tested`, `production-ready`, `enterprise-grade`, `first-class`, `comprehensive`, `seamless`, `powerful`, `elegant`, `sophisticated`
- Softeners applied to things the reader may not find soft: `simply`, `just`, `merely`, `easily`, `clearly`, `obviously`, `of course`, `straightforward`
- Inflated verbs where a plain one fits: `leverage`, `utilize`, `orchestrate`, `harness`, `unlock`, `empower`, `facilitate`, `ensure`, `dive deep`, `unpack`
- Unearned intensity: `crucial`, `vital`, `essential`, `critical`, `important` used as bare adjectives with no consequence stated
- Self-vouching: `honest take`, `genuinely`, `truly`, `actually`, `in essence`, `at its core`, `fundamentally`
- `graceful`/`gracefully` outside its precise sense (graceful shutdown, graceful degradation)

The set drifts by model generation. `delve` peaked in 2023–24 and collapsed afterward; `emphasizing`, `enhance`, `highlighting`, `showcasing` outlasted it. Treat the list as the current sample, not a fixed law, and weight a *cluster* of hits far above any single one. One of these words in a docstring means nothing. Six in a paragraph is the tell.

### Copulative avoidance

Assistants dodge plain `is`/`are`/`has`. Watch for `serves as`, `stands as`, `functions as`, `operates as`, `marks`, `represents`, `boasts`, `features`, `maintains`, `offers`, and `refers to` opening a definition.

- `This module serves as the entry point for…` → `This module is the entry point for…`
- `The cache offers a 30-second TTL` → `The cache TTL is 30 seconds`
- `Retry policy refers to the strategy used when…` → describe the policy, not the term

### Negative parallelism

- `Not just X, but also Y` / `Not only X but Y`
- `It's not X — it's Y` / `This isn't X. It's Y.`
- `no X, no Y, just Z`
- `X rather than Y` used as a rhetorical flourish rather than a real contrast

The construction implies the reader held a wrong belief that the writer is now correcting. In a comment, state Y and stop.

### Rule of three

Triads where one item carries the meaning: `fast, safe, and predictable`; `validates, normalizes, and persists`; three parallel bullet items where two are padding. Assistants reach for the triad to make thin analysis look thorough.

### Uniform rhythm

The strongest tell in the set, and the one a vocabulary grep will never find. Machines produce even rhythm; authors do not.

- Sentences of near-identical length through a whole paragraph or docstring
- Bullet lists where every item is bent into the same grammatical shape whether or not the content fits it — a list of four verbs-then-object clauses, one of which was really a caveat
- Sections padded or trimmed to match each other's length rather than their content
- In README and general markdown prose, bullet density around 60% or higher. Volume of bullets reads as machine-written regardless of how good the words are

**Scope carve-out:** the bullet-density rule applies to prose docs only. `CLAUDE.md`, `AGENTS.md`, `.claude/rules/`, and agent prompts are *supposed* to be dense bullets — a rule list is an enumeration, and rewriting it as paragraphs makes it worse for its reader. Never flag bullet density in agent-facing docs.

State the fix positively. The target is uneven sentence length, paragraphs sized to their content, and concrete specifics — not merely the absence of the flagged words.

### Elegant variation

Assistants carry a repetition penalty, so they rename the same thing mid-paragraph to avoid repeating a word. In prose this reads as fussy. In code documentation it is actively harmful: a docstring that calls the parameter `the payload`, then `the request body`, then `the incoming data` has broken the mapping between the prose and the identifier. Flag every synonym drift away from the actual symbol name.

Stated from the other side: repeating the technical term is the human move. Consistent terminology reads as authored; synonym rotation reads as generated. Say `body` four times.

### Editorial and didactic filler

- `Note that…`, `It's worth noting that…`, `It's important to note…`, `Importantly,…`, `Keep in mind…`, `Bear in mind…`
- `In other words,…` restating a sentence that was already clear
- `In summary,` / `In conclusion,` / `Overall,` closing a comment or a document under one screen long
- `This ensures that…` / `This allows us to…` / `This means that…` opening a sentence that then restates the code
- Present-participle tails bolted onto a sentence: `…, ensuring consistency across services`, `…, enabling faster lookups`, `…, contributing to overall reliability`. These are the single most common shape of assistant filler and almost never carry a checkable claim
- Hedge stacking: `generally, in most cases, typically` in one sentence
- Emphatic certainty about properties the code does not hold (`always`, `never`, `guaranteed`)

### Promotional register in technical prose

READMEs get the travel-brochure treatment: `blazing fast`, `powerful and flexible`, `rich set of features`, `diverse array of`, `commitment to quality`, `groundbreaking`, `renowned`. A README should say what the thing does and how to run it.

Also watch for puffed-up significance: `plays a crucial role in the overall architecture`, `represents a shift in how we handle…`, `sets the stage for future work`. A module has a job. It does not have a legacy.

### Formatting tells

- Em dashes at a rate no human sustains, especially several per paragraph, or spaced (` — `) in a file whose existing prose does not space them
- Title Case In Section Headings where the repo uses sentence case
- Bold-lead vertical lists: `- **Thing**: description` repeated down a docstring or README section where prose or a plain list fits
- Boldface sprayed on every instance of a chosen term
- Thematic breaks (`---`) inserted before every heading
- Emoji as structure (✅ ⚠️ 🚀 leading headings or bullets) in a repo that had none
- Curly quotes and apostrophes (`“ ” ‘ ’`) in comments, docstrings, and code fences. Beyond being a tell, these break grep, break copy-paste of example commands, and in some languages break the code outright
- Skipped heading levels (`##` straight to `####`)
- Small tables holding two facts that belong in a sentence

### Chat residue

Text that was never meant for the file at all. Any of these is close to proof rather than suspicion.

- `Would you like me to…`, `Let me know if…`, `I hope this helps`, `Certainly!`, `Here's the updated…`, `Feel free to…`
- Assurances of compliance: `This follows best practices`, `ensuring the code adheres to standards`, `I have preserved the existing behavior`
- Knowledge-cutoff and unavailability disclaimers: `As of my last update…`, `While specific details are limited…`, `not widely documented`, `based on available information`
- Unfilled placeholders: `[Add description here]`, `<your-api-key>` left in a real config example, `TODO: fill in`, `2025-XX-XX` dates
- Assistant-authored changelog voice in comments: `# Updated to handle the new format`, `# Refactored for clarity`, `# Changed from X to Y` with no reason. Git records what changed; a comment should say why the code is the way it is

### Tool artifacts (grep these; each is near-conclusive)

- ChatGPT: `contentReference`, `oaicite`, `oai_citation`, `turn0search0`, `attributableIndex`
- Gemini: `[cite: 1]`, `(start_span)`, `(end_span)`
- Grok: `grok_card`, `grok_render_citation_card_json`
- DeepSeek: lenticular brackets with daggers, `【85†L261-269】`
- Perplexity: `attached_file:`, `ppl-ai-file-upload`
- Tracking parameters on doc links: `utm_source=chatgpt.com`, `utm_source=openai`, `utm_source=copilot.com`, `referrer=grok.com`

### Narration comments in the assistant idiom

- `# Load the config`, `# Initialize the client`, `# Now we parse the response`, `# Finally, return the result`
- Numbered walkthroughs (`# Step 1: …`) tracking linear code
- `# Helper function to …` above something already named `_parse_helper`
- Docstrings opening `Main entry point for …` or `Utility function that …`

(This overlaps `restates-code`, which owns redundant narration in general. This lens owns the specific assistant phrasings above and defers when a comment is merely redundant in the author's own voice.)

## What NOT to Flag

Wikipedia's own list of ineffective indicators applies here, and false positives on this lens are expensive because the accusation is about authorship. There is a second cost too: over-correction takes the author's time and makes the text worse. A rewrite that strips a real fact to satisfy a style rule is a net loss, and the fifth cosmetic finding in a row teaches the reader to ignore the first four.

- **Plain, simple prose.** `is`, `are`, `has`, short sentences, and wordy-but-human constructions (`in order to`, `the fact that`, `as a result of`) point *away* from machine authorship, not toward it
- **Good grammar.** Many people write well
- **Formal or academic register.** The overuse is specific words, not long words in general
- **Superlatives and definite claims** (`the only caller`, `the first pass`). Assistants hedge; humans commit
- **Hedges and intensifiers** (`very`, `perhaps`, `tends to`) used sparingly. These read as human
- **Correct technical terms in their precise sense:** graceful shutdown, idempotent, blast radius in an ops runbook, first-class function in a language sense
- **Em dashes alone**, especially unspaced, especially in a repo whose pre-LLM prose already used them
- **Prose written before late 2022.** Check `git log` on the line before flagging style
- **House style the humans chose.** If the repo's own older docs are full of bold-lead lists, that is the convention here

Non-native English writers are also taught to avoid word repetition and to prefer formal register. Weigh clusters and residue over any single stylistic hit.

## How to Scan

1. **Grep the artifact list first.** Those hits need no judgment.
2. **Grep the vocabulary set** case-insensitively with word boundaries. Most hits will be legitimate. The grep produces candidates; the reading produces findings.
3. **For each candidate, delete the word mentally.** If the sentence loses nothing, that is the finding. If it loses a fact, keep it.
4. **Score density, not presence.** Count tells per paragraph. One is noise, five is a signal, and a paragraph with residue plus vocabulary plus a bold-lead list is settled.
5. **Grep for curly quotes and spaced em dashes** across source and markdown.
6. **Read docstring first lines as a set.** Assistant-written batches share an opening formula. Repetition across many files is one systemic finding, not twenty.
7. **Compare against the repo's pre-2023 prose** (`git log -S` or an old tag) to establish the house baseline before calling anything a deviation.
8. **Check symbol names against the prose that describes them** to catch elegant variation.
9. **Measure rhythm on the longest prose blocks.** Eyeball sentence lengths across a paragraph, check whether a bullet list forced one item into a shape it resists, and in prose docs estimate the bullet-to-paragraph ratio. Skip this step entirely for agent-facing docs.

## Report Findings

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **Tic** | Vocabulary / copulative / parallelism / rule-of-three / variation / filler / formatting / residue / artifact / narration |
| **The word or shape** | Quote the offending fragment |
| **What it hides** | The concrete fact the phrase stands in for, or "nothing — cut it" |
| **Suggestion** | The rewritten line, or "delete" |

### Severity Guide

- **Critical**: Only when the phrasing misstates a safety property, which usually means `contradicts-code` should own it too. Coordinate rather than double-report.
- **High**: A vague intensifier standing where a real property belongs (`# This is critical for thread safety` above an unsynchronized counter). Chat residue or an unfilled placeholder shipped in a public README or a config example a user will copy. Curly quotes inside a documented shell command.
- **Medium**: A systemic pattern across many files (shared docstring formula, sustained em-dash or bold-list density, batch narration). Report once with a file count. Also: elegant variation that breaks the prose-to-symbol mapping.
- **Low**: Isolated word choice, one throat-clearing opener, a single decorative flourish.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | High | pool.py:88 | "This is critical for correctness" above an unsynchronized counter; no property named | State it or cut it: `# Racy by design; callers tolerate a stale count` |
| 2 | High | README.md:42 | Curly apostrophe inside a copy-paste `curl` example; the command fails when pasted | Replace `’` with `'` |
| 3 | Medium | 14 files | Every public docstring opens "Helper function that…" | One systemic rewrite: open with the verb and the return value |
| 4 | Medium | client.py:30-44 | Docstring calls one argument "the payload", "the request body", and "the incoming data"; the parameter is `body` | Use `body` throughout |
| 5 | Low | cli.py:12 | "simply pass the flag" — the flag needs two env vars set | Drop "simply"; name the prerequisites |

## Rules

- **Word lists are candidates, not verdicts.** Every word here has a legitimate use. Flag the use, never the word. A finding must say what the phrase was standing in for.
- **Density decides.** Never open a finding on a single stylistic hit unless it is residue or a tool artifact.
- **Propose the replacement.** "Too AI-sounding" is not a finding. The rewritten line is.
- **Do not speculate about authorship in the report.** Write about the prose. "This docstring states no checkable fact" is useful; "this was written by ChatGPT" is an accusation you cannot support and it makes the finding easy to dismiss.
- **Batch systemic patterns.** Fifty narration comments from one generation pass is one Medium finding with a count, not fifty Lows. A wall of trivial findings buries the two that matter.
- **Content beats vocabulary.** A comment naming a real hazard is worth keeping even if it says "load-bearing" while doing it. Suggest tighter wording, keep the fact, rate it Low.
- **Style ranks below truth.** This lens sits under `contradicts-code` and `doc-drift`. Whether a comment tells the truth matters more than whether it sounds machine-written, and the two are independent: prose can be flawless and false. When the same text is both slop and wrong, the wrongness is the finding — hand it to the owning lens and let your note ride along with it.
- **Never launder a false claim.** A rewrite must improve readability, never make an unverified statement more convincing. If you cannot tell whether the claim under the bad prose is true, say so in the finding and leave the claim alone.
- **What this lens is not.** It improves readability. It is not detection-proofing, and a clean pass is no evidence that anything here was written by a human. Style cleanup is politeness, not defense.
- **Write the finding in plain prose.** A report about machine tics that is itself full of them is worthless. No em-dash strings, no negative parallelism, no bold-lead bullets, no closing summary in your own text.
