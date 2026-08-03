# Find Unedited Generator Boilerplate

Scan for strings that shipped from a project template and were never rewritten. The archetype: an index page reading "This is the home page of the application." — a sentence written by a scaffolding tool for a screen that did not exist yet, still in production three years later.

This lens is narrow and mechanical, and you own these strings exclusively. Other lenses will see them as narration, slop, or redundancy. They are none of those: they are unfinished work. The finding is not "reword this", it is "this was never written".

The cost is trust. A user who reads a placeholder sentence on the landing page concludes, correctly, that nobody has looked at this screen. Everything else they read afterwards is discounted.

## What to Look For

### Template-project defaults

The exact strings that ship in starter projects, cookiecutters, and framework `new` commands:

- "This is the home page of the application."
- "Welcome to your new app."
- "Edit this file to get started."
- "Hello, World!" outside a demo
- "Lorem ipsum" and any of its continuations
- "My Application", "My Project", "App Name", "Untitled"
- "Page description goes here"
- "© 2024 Your Company"
- Framework signatures: "Welcome to Flask", "Create React App", "Vite + React", "Django: the Web framework for perfectionists with deadlines"

The tell for this class: the sentence describes the *category* of the screen rather than what this screen does. A real home page says what the app tracks. A scaffold home page says it is a home page.

### Unfilled placeholders

- `[Add description here]`, `TODO`, `TBD`, `FIXME`, `XXX` in rendered text
- `{{ title }}` or `%s` rendering literally because the variable was never wired
- `<your-api-key>`, `example.com`, `user@example.com`, `+1 555 0100` in copy the user reads as real
- Version strings frozen at `0.0.1` or `v0.0.0-dev` in a footer
- A date placeholder: `2025-XX-XX`, `January 1, 1970`

### The duplicated boilerplate across projects

The strongest evidence available to you. If the same sentence appears in two unrelated apps, neither author wrote it. When the review covers one repo you cannot see this directly, but a sentence that is generic enough to fit any app is the same signal.

### Copy for a screen that changed jobs

A page scaffolded as one thing and repurposed as another, with the original description left in place. The heading matches the current screen; the paragraph under it describes the old one.

### Stale "coming soon" and stub copy

- "This feature is coming soon." on a working feature
- "Under construction"
- "Content will be added here"

Check whether the feature works before flagging — if it genuinely does not exist yet, the string is honest and belongs to `empty-and-error` for its wording, not to you.

### Demo and seed data in copy

Example names, fake numbers, and sample rows described in prose as if they were the user's: "for example, John Smith's account". Also placeholder alt text: "image", "photo", "logo here".

## What NOT to Flag

- **Generic copy the author wrote deliberately.** A short "Home" heading is not filler; it is a heading. Filler *describes* the screen generically, it does not merely label it.
- **Example values in a genuine example.** "A package says, for example, 341 kcal per 100 g" is teaching a format with a concrete instance. That is a working hint. Placeholder-looking numbers inside a demonstration are fine.
- **`example.com` in documentation copy** where a real domain would be wrong.
- **Honest stub copy on a feature that truly is unbuilt.** Confirm before flagging; then hand the wording to `empty-and-error`.
- **Framework attribution the author chose to keep**, such as a deliberate "Built with X" footer.
- **A `TODO` in a code comment.** Comments are `comment-cop`'s. You own only strings that render.
- **Lorem ipsum in a design fixture, storybook, or test template.** Check the path before flagging; a fixture is not a screen.

The test: **does this sentence tell the user something specific to this app?** Scaffold filler never does — that is precisely why it survived, because it is never wrong enough to notice.

## How to Scan

1. **Grep the inventory for the known defaults** first, case-insensitively: `home page of the application`, `welcome to`, `lorem ipsum`, `hello, world`, `my app`, `your company`, `coming soon`, `under construction`, `get started by editing`, `goes here`, `placeholder`, `example.com`, `TODO`, `TBD`, `Untitled`.
2. **Grep for unrendered interpolation** in the extracted strings — literal `{{`, `%s`, `${`, `#{` appearing as text.
3. **Read every index, landing, base and error template's body copy.** Filler concentrates on screens nobody revisits after the first commit.
4. **Check `git log` on the file.** A string that has not been touched since the initial commit, on a screen the app has since grown around, is filler by evidence rather than by pattern-match.
5. **Compare the paragraph to the heading.** A mismatch between a specific heading and a generic paragraph is the repurposed-screen case.
6. **For each candidate, confirm the screen is live** — reachable from navigation, not a stub route. Filler on a dead route is worth one line, not a finding.
7. **Group identical strings.** The same sentence on three screens is one finding with three locations.

## Report Findings

For each filler string:

| Field | Content |
|-------|---------|
| **Location** | file:line (all of them, if repeated) |
| **The string** | Quoted verbatim |
| **Evidence** | Known scaffold default / unfilled placeholder / untouched since initial commit / generic to any app |
| **Screen** | What this screen actually does |
| **Suggestion** | The replacement written for this screen, or "delete" |

### Severity Guide

- **Medium**: Filler on an entry screen — landing page, index, first screen after login, error page. It is the first thing a user reads and it says nobody has been here.
- **Low**: Filler on an interior screen, a footer, or a rarely-reached route.
- **High**: Only when the placeholder is operationally misleading — a fake support address or phone number a user might contact, a `<your-api-key>` in a config example the user will copy, a version string that misidentifies the running build.
- Never **Critical**.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | Medium | index.html:26 | "This is the home page of the application." — scaffold default, untouched since the initial commit | Replace with what this app tracks: "Twitch channels this instance watches, and when they last went live." |
| 2 | Medium | index.html:32 | Second scaffold paragraph on the same landing screen | Delete |
| 3 | High | base.html:88 | Footer contact reads `support@example.com` | Replace with the real address or remove the line |

## Rules

- **Name the evidence.** Known default, unfilled placeholder, or untouched-since-scaffold from `git log`. A finding that just calls copy "generic" is a style opinion, not this lens.
- **Write the replacement for this specific app.** The whole failure is genericness; a generic suggestion repeats it. Read enough of the app to say what the screen is for.
- **Deleting is a valid fix.** A landing page with nothing to say should say nothing rather than say it generically.
- **Confirm the screen is live** before spending a finding on it.
- **Group repeats into one finding.** The same sentence in three templates is one action point.
- **You own this class exclusively.** Do not defer these to `llm-slop` or `widget-narration`; they will defer to you.
