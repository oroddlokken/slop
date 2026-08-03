# Find Instructions for Controls That Already Say It

Scan for strings that explain how to operate a control the user is looking at. The checkbox is labelled. The button says "Add item". The form has a submit. A sentence describing what happens when you click it is narration of the visible.

This is the interface equivalent of `# increment i` above `i += 1`. It is rarely harmful and it is everywhere, because it is written by someone looking at the code rather than at the screen. Its cost is cumulative: a screen with six of these teaches the user that the hint text is not worth reading, and then they skip the one hint that carried a limit.

## What to Look For

### Operating instructions for a self-describing control

- "Untick to bring one back" under a list of ticked checkboxes labelled "Ignored"
- "Add a row per item; the total adds up below." above an "Add item" button and a total row
- "Click Save to save your changes."
- "Use the dropdown to select a category."
- "Press the button to start."

### Narration of what a form is

- "Fill in the fields below."
- "Enter your details in the form."
- "Complete all required fields to continue."

Required fields mark themselves. Validation says which one is missing. The sentence at the top does neither, and it is read before the user knows which field will fail.

### Restating the control's own label

- A button "Export CSV" with a hint "Exports your data as a CSV file."
- A toggle "Dark mode" with a hint "Switches the interface to dark mode."
- A field "Email" with placeholder "Enter your email"

### Describing the result the screen is about to show

- "The results will appear below."
- "Your total is shown at the bottom."
- "Once saved, the change appears in the list."

The user will see the results appear. They do not need advance notice of the layout.

### Step lists for a one-step interaction

- "1. Choose a file. 2. Click Upload. 3. Wait for the upload to finish."

Three steps for a control with one button and a file input.

### Sequencing narration

- "Pick the day, then the timer begins."
- "Select an option and the page will update."

These sit between narration and a real state fact. Apply the test below carefully: if the *ordering* is non-obvious or has a consequence (starting the timer writes a record that cannot be edited), the sentence is carrying something. If it just describes cause and effect the user will observe within a second, it is narration.

## What NOT to Flag

- **A hint naming a consequence the user cannot see coming.** "Unticking republishes the entry to every subscriber" is a consequence, not narration. Keep.
- **A hint naming a constraint on input.** "Max 20 MB", "one URL per line", "numbers only", "kcal per 100 g". Format and limit hints are the reason placeholder text exists. Protect them.
- **A hint that resolves an ambiguous control.** If a toggle's two states are not obvious from the label ("Strict" — strict about what?), a clarifying sentence is doing real work. The finding, if any, is that the label should be better; say so rather than proposing deletion.
- **Keyboard shortcuts and non-obvious affordances.** "Shift-click to select a range", "drag to reorder". These are invisible without the hint.
- **Instructions for a genuinely multi-step flow** with state between steps, where the user needs to know what comes after this screen.
- **First-run and onboarding surfaces** where nothing on screen has context yet.
- **Accessibility text that duplicates a visual label on purpose.** An `aria-label` restating a button's icon is correct; that is what it is for. Only flag an `aria-label` whose *wording* is wrong for a screen reader, and even then say so precisely.

The test: **cover the sentence and look at the control. Can the user proceed?** If yes, the sentence is narration. If they would hesitate, guess wrong, or hit a limit they did not know about, it is a hint and it stays.

## How to Scan

1. **Grep the inventory for imperative verbs aimed at controls**: `click`, `press`, `tap`, `select`, `choose`, `use the`, `untick`, `tick`, `check the box`, `toggle`, `enter`, `fill in`, `pick`, `drag`.
2. **Grep for result-narration**: `will appear`, `is shown below`, `adds up below`, `you will see`, `then the`, `once you`.
3. **For every hit, read the surrounding markup in the inventory** to identify the control. The finding depends on what the control says about itself — a hint is only narration relative to a specific label.
4. **Apply the cover test explicitly.** Write down what the control alone communicates and what the sentence adds.
5. **Look for the constraint hiding in the narration.** "Add a row per item; the total adds up below" — is there a row limit? If the sentence carries one, keep that half.
6. **Count per screen.** A settings page with six of these has one problem. File it once with all locations; six Low rows will be dropped by the cap and the pattern will be lost.

## Report Findings

For each narration string:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **The control** | What the control says about itself (label, button text, field name) |
| **The narration** | The string, quoted |
| **Adds** | What the sentence tells the user beyond the control, or "nothing" |
| **Suggestion** | "Delete", or the constraint clause to keep, or "move the fact onto the label" |

### Severity Guide

- **Medium**: A screen carrying four or more narration strings — the hint layer as a whole has become unreadable, so a real hint on that screen will be skipped. Report as one finding with the count.
- **Low**: The standard case. One narrated control.
- Never **High/Critical**: narration wastes a second. If it describes the control *incorrectly*, that is `contradicts-view`.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | Medium | settings.html:138,160,211 | Three hints narrate their own checkboxes ("Untick to bring one back"); the hint layer on this screen is all narration | Delete all three. The tick state and the "Ignored" heading carry it |
| 2 | Low | tools.html:24 | "Add a row per item; the total adds up below." next to an "Add item" button and a visible total | Cut to the format fact: "kcal per 100 g, then the amount you had." |
| 3 | Low | index.html:119 | "Pick the day, then the timer begins." — cause and effect the user sees immediately | Delete unless starting the timer writes an uneditable record; if it does, say that instead |

## Rules

- **Judge the string against its control, never alone.** A finding that does not quote the control's label has not done the work.
- **Cover test in every finding.** State what the control communicates without the sentence.
- **Keep constraints and consequences.** Format limits, size caps, irreversibility, and hidden affordances are hints, not narration. When a narration string contains one, propose keeping that clause alone.
- **Batch per screen at four or more.** One Medium finding with locations beats six Lows that the cap will discard.
- **Do not propose adding text.** If a control is genuinely unclear, the fix is a better label — say that in one clause and move on. This lens removes; it does not commission copy.
- **A better label is not a code change.** Renaming a button's text is copy. Adding, removing, or rewiring a control is not — that is out of scope.
