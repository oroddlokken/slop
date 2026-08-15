## Extract the String Inventory (orchestrator step)

This file is executed by the **orchestrator** (the main Claude Code session), NOT by individual review agents. The orchestrator extracts strings once and passes the inventory to all agents. Your role is extraction (find every string that reaches a screen) and faithful reproduction (each string verbatim, with the file:line and the element that carries it); the agents do the analysis.

**Do not reproduce whole files.** A sibling skill like `comment-cop` dumps source verbatim because it reviews prose *inside* files. String Cop reviews prose that *escapes* files onto a screen, and that is a small fraction of the bytes. Sixty templates reproduced whole will exhaust the context before the first agent runs and bury ten real strings under ten thousand lines of markup. Extract the strings, keep the markup that identifies them, drop everything else.

**Reproduce each extracted string byte-for-byte.** Do not reflow, re-wrap, correct, or summarize a string. The reviewers grade wording; a paraphrase corrupts the evidence. Preserve the curly quotes, the double spaces, the trailing period, the `&nbsp;`.

### Extraction Procedure

**Render layers in scope:** {render_layers}. Cover all of them — do not stop at the largest template directory.

#### 1. Enumerate the screens

List template files and map each to the route or view that renders it (`render_template("weight.html")`, a controller action, a component's route). Record the mapping — reviewers need it to check a string against what renders, and `cross-screen` needs to know which strings share a screen. Partials and includes (`_timeline.html`, `_forms.html`) are their own entries, with a note listing which screens include them: a string in a partial ships to every screen that pulls it in.

#### 2. Extract template strings

From each template, take every string a user can read:

- Text nodes between tags — headings, paragraphs, list items, table captions, cell text
- `title=` (tooltip text — a heavy source of hidden prose)
- `aria-label=`, `aria-description=`, and `<title>` inside SVG
- `placeholder=`, `alt=`, `label` element text, `value=` on buttons and submits
- Button, link and menu labels
- Text inside conditional branches, especially `{% else %}` arms — empty states hide there
- Flash/message rendering blocks and their fallback text
- `<title>` and any meta description a browser tab or preview shows

Skip: class names, ids, data attributes, `href`/`src` values, template variable names, and anything inside `{# #}` or `<!-- -->` comments. A developer comment in a template is `comment-cop` territory, not yours.

Keep interpolation markers in place (`{{ counts.ranked }}`, `{% if filtered %}`) — the surrounding sentence is only judgeable with them, and a hint that is 90% interpolated data is usually a fact, not filler.

#### 3. Extract view and domain strings

Grep the non-template source for string literals that reach a screen. This step is what makes the review complete: a remediation hint defined in `drift.py` and rendered through a generic loop never appears in any template, and template-only extraction misses it entirely.

Look for:

- Flash and message calls: `flash(...)`, `messages.add_message(...)`, `toast(...)`, `notify(...)`
- Error and validation text: `HTTPException(detail=...)`, `abort(400, "...")`, form validation messages, `raise ValueError("...")` where the message reaches a rendered error page
- Display labels on enums, dataclasses, and constants — fields named `label`, `title`, `hint`, `detail`, `message`, `description`, `summary`, `remediation`, `help_text`, `verbose_name`, `short_description`
- Any module whose whole job is copy: `strings.py`, `messages.ts`, `copy.js`
- Translation catalogues: `.po` msgids, `messages.json`, `locales/**`

The tell for a user-facing literal in domain code: it is a sentence, it is capitalized, and it is not a log line, an exception a developer sees only in a traceback, a SQL fragment, or a test fixture. When you are unsure whether a literal renders, trace one caller. If it renders, include it and say which screen shows it.

#### 4. Capture the context each string needs

For every string, record enough context to judge it and no more:

- The element or control it accompanies. A hint reading "Untick to bring one back" is only judgeable next to the checkbox labelled "Ignore"
- For a tooltip: what the tooltip is attached to
- For an empty state: the branch condition that produces it
- For a hint under a number: the number's label and unit

Two to five lines of surrounding markup, elided to the relevant part. Never the whole block.

#### 5. Note render-truth anchors

For strings that make a claim about behaviour ("nothing is deleted", "this only reads", "updates every 5 minutes"), record the file:line of the code that would confirm or refute it. The `contradicts-view` lens needs a starting point, and a lens that has to search from scratch produces vaguer findings and more false Criticals.

{focus}

### Build the Inventory

Group by screen, then by source file. Format:

````
### screen: <route or template name>  (rendered by <view file:line>; includes <partials>)

| file:line | element | string |
|-----------|---------|--------|
| weight.html:42 | tooltip on the trend metric | The trend is a smoothed average of your weigh-ins, not today's raw number. … |
| weight.html:58 | empty state, `{% if not entries %}` | Nothing logged yet. |
````

For any string longer than roughly 25 words, follow the table row with the full string in a fenced block, verbatim, so the reviewers grade the whole thing rather than a truncated row:

````
#### weight.html:42 — full text
```
The trend is a smoothed average of your weigh-ins, not today's raw number.
Each reading nudges it about 10% toward the scale (a time-aware moving
average, ~6.6-day half-life), so day-to-day water-weight noise is filtered
out and real change shows through. Several weigh-ins on the same day are
averaged first.
```
````

Close the inventory with two short sections:

````
### domain-supplied strings

| file:line | reaches | string |
|-----------|---------|--------|
| drift.py:340 | drift.html, every "dirty" finding | Commit or stash. |

### render-truth anchors

| claim (file:line) | code to check (file:line) |
|-------------------|---------------------------|
| decisions.html:34 "No file has been deleted." | decisions.py:88 restore handler |
````

Include:
- Every screen with at least one extracted string
- Every partial, with its includers listed
- All domain-supplied strings
- The render-truth anchor table

Omit:
- Whole-file reproductions of anything
- Markup carrying no strings
- Generated report directories (`htmlcov/`, `coverage/`, `dist/`), vendored assets, `node_modules/`, `.venv/`, `site-packages/`
- Files matching `.env*`, `*.secrets`, `*credentials*.json`, `*.key`, `*.pem`, `secrets.yml` — list by name only

**Inventory size limit**: if the inventory exceeds ~400,000 bytes (≈100K tokens), narrow it before asking the user to narrow scope — this inventory is strings, so that size means a large app. Drop whole screens rather than truncating strings; a truncated string cannot be graded. Prefer dropping screens with only labels and no prose. List every dropped screen in the inventory so the reviewers and the user both know coverage was bounded.
