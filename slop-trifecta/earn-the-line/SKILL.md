---
name: earn-the-line
description: 'Invoke only for the worked bad/good pairs in references/examples.md, or when this session has no earn-the-line rules in context. The rules — prose in comments, docstrings, doc files and prose-valued config fields, plus labels, hints, tooltips, empty states and error text — are normally injected at session start by inject-earn-the-line.sh.'
license: MIT
---

# earn-the-line

Two readers, neither of whom asked to read anything. First reader: the person
who opens the file months from now and cannot ask you a follow-up. Second
reader: the person using the thing mid-task who did not open it to read. A line
earns its place by carrying
what the code or the screen cannot show. Everything else is clutter someone
else maintains.

Word choice comes from `cut-the-crap`'s pre-send check: one name per thing,
active voice, simple tense, plus the vocabulary inventories — puffery,
self-vouching, coding-assistant tics, softeners, inflated verbs; where that
style is not loaded, delete the word and name the property or the consequence.
The two-sentence-per-unit cap is this file's own; the word numbers live with it
below. Cut words, never facts — if a rambling comment holds one real gotcha, the
short version keeps the gotcha.

## What you write into files

Comments, docstrings and doc prose are read by the first reader. The reply rules apply, plus the two-sentence cap below, and there is no follow-up turn in which to correct a comment. Config files are in scope — a `.gitignore` rule, a YAML key, a Dockerfile line, a shell rc export.

A field whose value is prose is a comment, whatever the syntax says: a manifest's
`summary`, a `notes` array, a `description` key. Every rule below applies to it.

These rules govern prose this task adds or changes. A comment already in the
file is out of scope unless your change makes it wrong or the user asked for a
prose pass — a bug fix that also strips six unrelated comments is a diff the
reviewer cannot read.

### Never in a file

**Write no issue id, ticket ref or PR number into a comment, docstring, test name or migration header.** Put it in the commit message, where the diff is attached and the tracker can be reached. In the file it resolves to nothing for a reader without access, and to a closed ticket about since-moved code for one with it. If deleting the id leaves a sentence that no longer says anything, the id was standing in for the fact — write the fact. The same holds for a plan's phase or step numbers: the plan is a session artifact, so the number resolves to nothing a week later.

**Write no line addressed to the session: "as requested", "per your request", "as we discussed".** The reader months from now was not in the conversation, and the request does not constrain the code. Write the constraint, or nothing.

**When a line you are already changing stops being true, delete it — do not annotate it.** A file states what is true now; the diff and the commit message state how it got there. "restored 2026-08-10", "no longer cut", "no longer needed", "this moved into X" leave the deleted line on the page, and the next reader spends a paragraph learning nothing about the current state. Renumber the list you deleted from, unless its numbers key to something outside the file — a checklist mirroring another document's items keeps its gaps, and closing them silently repoints every entry. A reader opening the file cold should not be able to tell it was ever different. Two passes of this leave a file whose headings describe its edit history instead of its contents.

Delete only a line you checked against the code or doc it describes this
session; a suspect line you did not verify stays, named in your reply. Stale
lines elsewhere in the file are a separate change: name them and get a go-ahead
before the sweep.

### Earning the line

Default to no comment. What earns the line is a rationale, a gotcha, an ordering constraint, where a magic number came from. Anything the next three lines of code already say is clutter.

Fresh vocabulary does not help: read the lines below the comment first, and if a
reader with them in front learns no fact, the comment is a rename. A vendor
label is a fact; repeated once per declaration it is a rename.

Paraphrasing the block is the same clutter without the names. "Commit the
receipts, ignore the transcripts", written above three ignore rules that do
exactly that, carries no name verbatim. It still tells the reader nothing the
lines below do not. What earns the line points somewhere the file cannot reach.

A correction the user makes about one comment applies to every file you write
after it. When the user asks for a comment "in the same shape" as an earlier
file and that file predates the correction, the correction wins. Reread what
they struck before writing.

Open on the fact. A comment that names what the line says before it adds the
gotcha still reads as the struck shape, and the fact lands after the reader has
stopped reading.

No narrative. "Today this carries only...", "imagine an operator who...", "you might think...", "the canonical case is..." — a hypothetical reader in a hypothetical scenario is a story where a fact belongs. Cut to the fact.

### Length

Two sentences per comment; 20 words for a sentence that instructs, 25 for one that explains. A sentence that does both takes the 20-word cap. Count sentences, not lines: a four-line gotcha above one dense line is right, and the code beneath it sets no budget.

The cap applies in each of these, measured alone: a run of comment lines, a docstring's prose below its summary, one parameter entry, and one rendered string. So a five-parameter Args block gets five separate two-sentence budgets. Past that it is a design doc filed in the wrong place. Doc prose in a `.md`, `.rst` or `.txt` file takes the word caps and the vocabulary rules, not the two-sentence cap: a paragraph there is the artifact, and its budget is the section it sits in.

A file header is a run of comment lines and takes the same cap — a box-drawn
frame or an architecture overview above the first declaration. Sitting at the
top and reading like documentation buys it nothing. The overview goes in the
design doc or the commit message.

Comment length tracks how non-obvious the code is on the page, not how long the decision took.

### What belongs in the file

Write the fix, not the hunt. The symptom you measured, the hypothesis you
rejected and the order you found things in belong in the commit message.

A measurement earns its line when it pins a fact that is still true — which port
answers, what a probe returned. The wrong guess that preceded the fix does not,
and a file that keeps it teaches the next reader the diagnosis you threw away.

**A rejected alternative earns the property that killed it.** Under a heading
that already says rejected, "not chosen" repeats the heading; write "a single
/32 splits only by port range" instead. Only an alternative the tree carried or
the user weighed earns the line. A design nobody proposed is a story about your
reasoning; the reader cannot check it against the file.

**An unknown earns one line naming it.** One unverified fact turns into a
fallback, then a fallback for that fallback; the reader plans the follow-up, so
name the gap and stop.

**State an absence once, in the unit where the reader looks for the thing.** A
heading, a status line and a body sentence on one missing piece are three edits
when it lands.

A comment scopes to what the file can be changed to say. A fact about a
neighbouring system, a manual step, or a sibling repo passes the earning test on
a quick read — a real constraint the code cannot show — and still fails: the
reader cannot check it against anything on the page, and nobody owns keeping it
true, so it rots silently. Those belong in the design doc or the runbook. In the
file, the legitimate form is the constraint the local code must satisfy.

When the comment describes an order — a fallback chain, a retry ladder — write the numbered list, not the paragraph. Prose describing structure is the slowest way to convey it. Each item carries its own two-sentence budget.

State a rationale once, at the place the constraint lives. Repeating it in every function, test and template that observes it is one copy per observer to update, and each one can drift.

Prose in a generator's field is not one line. One manifest paragraph reaches the
compose file, the host vars, a generated doc and a deploy config in another repo.

Count the copies where they land, not where you type them. Most land under a
GENERATED header, so a wrong line there is one the reader cannot fix in place.

If a doc in the repo already carries the reason, the comment is a copy. Grep the
repo's markdown for the constraint's key term before writing the reason inline: a
hit means the pointer, no hit means the reason. Point at the doc — one path, plus
a quoted heading when the doc runs longer than a screen (`# why:
evals/README.md, "The receipt"`) — or write nothing. A pointer followed by the
reasoning is not a pointer.

A pointer earns its line only when the path resolves in the repo — check it this
session. A scratch file, a deleted plan, or a doc in another system is a dead
end. Write the fact instead.

A one-line paraphrase of the doc's reason is the same copy in fewer words, so
shortening does not fix it. "Cut words, never facts" does not apply: the fact is
already kept, in the doc, so cut it here too.

## When the convention requires the line

Where a language convention or a linter requires the line — an exported Go
identifier's doc comment, a Terraform `variable` `description`, a public API
docstring under `pydocstyle`, a JSON Schema `description` a consumer renders —
write the shortest form the convention accepts, opening on the non-obvious fact
if there is one, and stop. Say in one clause which convention required it: "Go
doc comment, required for the exported name."

A file whose subject is change history keeps its history: a CHANGELOG, release
notes, an ADR's superseded-by line, a migration note, a deprecation marker the
language defines. Write the entry in the file's own form.

## What renders on a screen

Labels, hints, tooltips, empty states and error strings are read by the second reader.

A string earns its place by carrying a unit, a source, a limit or a consequence. Restating the control's own label is none of those.

Cut these:

- Reassurance about a risk nobody raised. "No file has been deleted." The reader was not worried until you wrote it.
- The design's rationale. Why one tool owns a check, why an editor is withheld. That belongs in the commit.
- Praise for the feature: "the actionable subset", "nothing else reports that".
- The derivation. A formula's justification where the number belongs. Print the number and its unit.
- Narration of a control. "Untick to bring one back" — the checkbox is the instruction.
- A tail restating the head. "Nothing left to rank. Everything is ranked."

One caveat, one place. The same sentence on five tooltips is five strings to fix when the thing it describes changes.

An empty state names the one action that fills the screen. An error names location, then cause, then fix, with no mood.

Where the control does something the reader could mistake for deletion, name the
totals that move and what stays. That does the reassurance's work without
raising the risk, and it opens on the fact instead of arriving at it.

When the user asks for a specific comment or string, write it. Say once, in one
clause, what the rules here would have cut, then move on.

Worked bad/good pairs for some of these rules: `references/examples.md`.
