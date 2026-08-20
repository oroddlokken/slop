# Changelog

## 2026-08-18

- Extended the no-issue-id rule to a plan's phase and step numbers: the plan is a
  session artifact, so the number resolves to nothing a week later.
- Banned lines addressed to the session — "as requested", "per your request",
  "as we discussed". The reader months from now was not in the conversation.
- Narrowed the rejected-alternative rule to alternatives the tree carried or the
  user weighed; a design nobody proposed is a story the reader cannot check.
- Required a pointer's path to resolve in the repo, checked that session. A
  scratch file or a deleted plan is a dead end, so write the fact instead.

## 2026-08-14

- Rewrote the description to say when to invoke: for the worked pairs in
  `references/examples.md`, or when the session has no injected rules.
- Numbered the two readers so the rest of the file can refer to them.
- Added three rules: a rejected alternative earns the property that killed it,
  an unknown earns one line naming it, and an absence is stated once in the unit
  where the reader looks for the thing.
- Set the tie-break on the word caps — a sentence that instructs and explains
  takes the 20-word cap — and moved the pointer to the examples file to the end.
- Added three worked pairs: an unknown as one line, a convention-required Go doc
  comment, and a comment the user asked for anyway.

## 2026-08-12

- Rewrote the file into sections: never in a file, earning the line, length,
  what belongs in the file, when the convention requires it. Moved the worked
  pairs out to `references/examples.md`, since the rules are injected at session
  start and the pairs are not.
- Scoped the rules to prose this task adds or changes: a bug fix that also
  strips six unrelated comments is a diff the reviewer cannot read. Deleting a
  stale line needs it checked this session; a wider sweep needs a go-ahead.
- Added the convention carve-out — a Go doc comment, a Terraform `description`,
  a `pydocstyle` docstring, a rendered JSON Schema `description` — write the
  shortest form the convention accepts and name the convention in one clause.
  A file whose subject is change history keeps its history.
- Added the grep-before-writing step for a reason a doc already carries, and let
  a pointer quote a heading when the doc runs longer than a screen.
- Gave doc prose in `.md`, `.rst` and `.txt` the word caps but not the
  two-sentence cap: a paragraph there is the artifact.
- Said what to do when the user asks for a specific string: write it, then name
  in one clause what the rules would have cut.

## 2026-08-11

- Put prose-valued config fields in scope — a manifest's `summary`, a `notes`
  array, a `description` key are comments whatever the syntax says.
- Added the generated-copy count: one manifest paragraph reaches the compose
  file, the host vars, a generated doc and another repo's deploy config, and
  most land under a GENERATED header the reader cannot fix in place.
- Added "write the fix, not the hunt": the symptom, the rejected hypothesis and
  the order of discovery belong in the commit message.

## 2026-08-10

- Adopted the ASD-STE100 word rules by reference from `cut-the-crap` — one name
  per thing, active voice, simple tense — alongside the vocabulary list.
- Added the delete-don't-annotate rule: "restored 2026-08-10", "no longer cut",
  "this moved into X" leave the deleted line on the page. Renumber the list
  unless its numbers key to something outside the file.
- Added the safe-action pattern for UI copy: name the totals that move and what
  stays, instead of reassuring the reader that nothing is deleted.

## 2026-08-05

- Ruled that a comment listing names that appear verbatim below is restating the
  code, and that paraphrasing the block is the same clutter without the names.
- Ruled that shortening a copied reason is still a copy: "cut words, never
  facts" does not apply when the fact is already kept in the doc.

## 2026-08-04

- Extracted the skill from `cut-the-crap` as its own `SKILL.md`, covering
  comments, docstrings, doc prose and rendered strings.
- Put config files in scope — `.gitignore`, YAML, TOML, Dockerfile, shell rc —
  and added the pointer rule: where a repo doc already carries the reason, write
  one path or nothing.
- Added the carry-forward rule for a reader's correction: it holds for every
  file after it, including the next one asked for "in the same shape" as a file
  that predates it.
