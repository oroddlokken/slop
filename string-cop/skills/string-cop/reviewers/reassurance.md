# Find Reassurance Nobody Asked For

Scan for strings that comfort the user about a risk the user never raised. The shape is a promise about what the app will *not* do — not delete, not write, not send, not read, not hide — offered unprompted on a screen where nobody was worried.

The failure is not politeness. It is that a denial introduces the fear it denies. A user who reads "No file has been deleted." now knows deletion was on the table, and starts wondering which screens delete. Naming the risk to dismiss it is how you plant it. The strings almost always originate with the developer, who has spent a week thinking about the deletion path and forgets that the user has spent zero seconds on it.

## What to Look For

### The unprompted denial

The signature form: a negated verb about a destructive or invasive action, on a screen where the user is doing something else.

- "No file has been deleted."
- "Nothing here ever writes to the infrastructure repo."
- "values, secret or not, are never read into colophon"
- "nothing is hidden"
- "Never auto-removed."
- "We never share your data." on a screen with no sharing control

Each one answers a question nobody typed.

### The safety adverb

Reassurance compressed into a modifier: "safely", "securely", "privately", "locally", "read-only" attached to an ordinary action.

- "Your data is safely stored locally"
- "This securely fetches the list"
- "safe to close this page"

Delete the adverb and check whether the sentence loses information. If the storage location is a fact the user needs, keep the fact — "stored in ~/.config/vekt" is a fact. "safely stored" is a mood.

### The comfort blanket on a reversible action

- "Don't worry, you can undo this."
- "This is completely reversible."
- "No permanent changes will be made."

An undo control is reassurance. A sentence describing the undo control is not. When a user can see the Restore button, the paragraph explaining that restore exists is the finding — and when they cannot see it, the fix is to show the control, not to write a paragraph.

### Pre-emptive apology and hedging

- "This may take a moment, but don't worry."
- "You might see a brief flicker — this is normal."
- "Some results may be missing, but that's expected."

The last one is worth separating: if results really can be missing, that is a **limit** and it stays — rewritten as a fact. "Sessions before 2025-03 have no viewer data" is a keeper. "Some results may be missing, but that's expected" is not.

### Reassurance about the app's own correctness

- "This number is accurate."
- "All values have been validated."
- "Calculations are performed correctly."

A claim of correctness is unfalsifiable to the reader and adds nothing. If accuracy has a bound, state the bound; that is the `lecture` lens's keeper case and yours to hand over.

## What NOT to Flag

The whole value of this lens depends on the distinction below. Get it wrong and you strip the app's honest warnings.

- **A consequence stated before a destructive action.** "Deleting this removes all 14 entries" on a confirm dialog is not reassurance, it is the disclosure that makes consent meaningful. Keep it. The difference: reassurance denies a risk, disclosure names one.
- **A scope statement the user cannot infer.** If a settings screen reads a config file and the user reasonably fears it writes back, "read-only — edit the file by hand" is a fact about the screen's capability. It survives if it names *what* is read-only and *what the user must do instead*; it fails if it is a bare "nothing is written here" with no next step.
- **A privacy or retention fact with a source.** "Photos are processed on this machine; nothing is uploaded" on a screen that visibly uploads elsewhere is a real distinction. A blanket "your privacy matters" is not.
- **A limit the screen cannot show.** "Only the last 90 days are kept" is a limit, not comfort. Protect it.
- **Regulatory or legal copy** that has to be there. Note it and move on.
- **A denial that is false.** That is `contradicts-view`'s Critical, not your Medium. Hand it over.

The test, applied to every candidate: **would a user have asked this question at this moment?** If yes, the answer is a fact and it stays. If the sentence is the first time the risk enters the user's head, it is reassurance.

## How to Scan

1. **Grep the inventory for negated capability**: `never`, `no file`, `nothing is`, `not be`, `won't`, `cannot`, `does not`, `isn't`, `no data`, `no changes`.
2. **Grep for the safety adverbs**: `safely`, `securely`, `privately`, `locally`, `automatically`, `read-only`, `don't worry`, `rest assured`, `no need to`.
3. **For each hit, find the control it sits near.** Reassurance clusters around destructive controls, settings screens, and anything touching files or credentials.
4. **Apply the would-they-have-asked test.** Ask what the user is doing on this screen and whether the risk was live in their head before they read the sentence.
5. **Check whether the denial is even true** before writing it up. A false denial belongs to `contradicts-view` at higher severity — verify, then route.
6. **Look for the fact hiding inside.** Most reassurance strings contain one real clause. Extract it; propose that as the replacement rather than deletion.
7. **Count per screen.** Three denials on one settings page is one systemic finding about that screen, not three rows.

## Report Findings

For each reassurance string:

| Field | Content |
|-------|---------|
| **Location** | file:line |
| **The comfort** | The string, quoted verbatim |
| **Risk it introduces** | The fear the sentence plants that the user did not have |
| **Fact inside it** | The one real clause worth keeping, or "none" |
| **Suggestion** | The extracted fact as a replacement line, or "delete" |

### Severity Guide

- **High**: Reassurance on a destructive or credential-handling screen that a user might rely on instead of checking — the comfort is doing the job a disclosure should do.
- **Medium**: An unprompted denial on an ordinary screen. The standard case.
- **Low**: A stray safety adverb, a single "don't worry".
- Never **Critical**: comfort wastes attention and plants doubt; it does not by itself destroy data. If the denial is false, that is `contradicts-view`.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | Medium | decisions.html:34 | "No file has been deleted." — the user had no deletion in mind until this sentence | Delete. The Restore control already says the decision is reversible |
| 2 | Medium | settings.html:121 | "Nothing here ever writes to the infrastructure repo." — denies a risk nobody raised | Cut to the capability fact: "Read-only. Edit `projects.json` by hand." |
| 3 | Low | index.html:83 | "nothing is hidden" — unfalsifiable comfort with no set named | Delete, or name the set: "every repo in the catalog is listed" |

## Rules

- **Would they have asked?** That is the whole lens. Run the test explicitly in every finding.
- **Extract the fact before proposing deletion.** Most of these strings carry one real clause. Deleting the paragraph and the clause together is a worse outcome than leaving it alone.
- **Disclosure is not reassurance.** A consequence stated before a destructive action stays. Never propose cutting a warning that precedes a real risk.
- **Verify a denial before you route it.** If the claim is false, `contradicts-view` owns it at Critical or High. Say so in your finding rather than reporting it as mere clutter.
- **Batch per screen.** Several denials on one screen is one action point listing the locations.
- **Do not moralize in the report.** Name the string, name the risk it plants, propose the line. No commentary on the developer's anxieties.
