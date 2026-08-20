# slop-trifecta

Three pieces split the anti-slop work. `cut-the-crap.md` shapes replies.
`earn-the-line` shapes prose written into files and screens. `lint-slop.py`
checks written prose after every write.

Each piece works on its own. Together they cover the three places slop
appears: what the model says, what it writes down, and what survives a write.

## The three layers

| Piece | Kind | Governs | Loads |
|---|---|---|---|
| `cut-the-crap.md` | Output style | Replies | Every session, as system-prompt text |
| `earn-the-line/SKILL.md` | Skill | Comments, docstrings, doc prose, prose-valued config fields, UI strings | Body injected at SessionStart by `hooks/inject-earn-the-line.sh` |
| `hooks/lint-slop.py` | PostToolUse hook | Prose added by Write, Edit, MultiEdit and NotebookEdit | Fires after each write; exit 2 returns the hits to the model |

Invoke the `earn-the-line` skill to reread its worked examples, or when a
session carries no injected rules — see the exit-0 path under Install.

## Install

Everything below assumes `~/.claude/`. The hook and the output style are
copies, so a clone anywhere works as long as the paths in `settings.json`
point at it.

```bash
mkdir -p ~/.claude/output-styles ~/.claude/skills ~/.claude/hooks
cp    slop-trifecta/cut-the-crap.md ~/.claude/output-styles/
cp -R slop-trifecta/earn-the-line   ~/.claude/skills/
cp -R slop-trifecta/hooks/.         ~/.claude/hooks/
```

Then pick the output style once per machine, with `/output-style cut-the-crap`.

Register both hooks in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash $HOME/.claude/hooks/inject-earn-the-line.sh",
            "statusMessage": "Loading earn-the-line..."
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit|MultiEdit|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 $HOME/.claude/hooks/lint-slop.py",
            "statusMessage": "Checking prose for banned vocabulary..."
          }
        ]
      }
    ]
  }
}
```

Requirements: `jq` for `inject-earn-the-line.sh`, `python3` for `lint-slop.py`.

`EARN_THE_LINE_SKILL` overrides where the inject hook reads the skill from,
which is how the test suite points it at a fixture.

## Wiring

`inject-earn-the-line.sh` strips the frontmatter and prefixes a preamble that
scopes the rules to artifact prose. An unreadable SKILL.md exits 0, so a
skipped install step means a session with no injection and no error.

`lint-slop.py` scans every line of a prose file, and in code files the
comment-shaped lines plus lines opening with a string literal. Paths in
`EXEMPT_PATHS` skip the scan; they quote the inventories.

Those exempt fragments are written for a `~/.claude/` install — `earn-the-line`
and `cut-the-crap.md` match there, and so do the two hooks. None of them match
this repo's own layout, so editing these files inside a clone of `slop` gets
flagged by the very words they list.

## Who owns which rule

- Vocabulary: the inventories live in `cut-the-crap.md`, "Before sending".
  `earn-the-line` applies them to file prose. `lint-slop.py` matches the
  regex-safe subset in `INVENTORY`; the rest stays prose-only because a regex
  cannot judge context.
- Sentence shapes: `cut-the-crap` owns corrective framing, the not-only pair
  and the validation opener; `earn-the-line` owns the rejected alternative, the
  unknown, one absence per unit, the line addressed to the session, and a plan's
  phase numbers. `lint-slop.py` matches the line-anchored four — the two pairs,
  a bullet whose payload is only a negation, a sentence-final dismissal — plus
  the session address and the plan reference.
- Caps: `earn-the-line` owns the artifact caps — two sentences per unit, 20
  words instructing, 25 explaining. `cut-the-crap` owns the reply caps.
- Priority: `cut-the-crap.md`, "Overrides", carries the order. Read it there; a
  copy here goes stale.

## Changing one piece

1. Banned word or sentence shape added or removed: edit the inventory in
   `cut-the-crap.md`, mirror the regex in `INVENTORY`, extend
   `hooks/lint-slop-tests/run-tests.sh`, run it.
2. `earn-the-line` body edited: the next SessionStart injects the new text.
   If the scope changed, update the preamble in `inject-earn-the-line.sh` and
   run `hooks/inject-earn-the-line-tests/run-tests.sh`.
3. New file quotes the inventories: add its path fragment to `EXEMPT_PATHS`
   and a case to the lint tests.

Both suites take a `HOOK_PATH` override and exit with the failure count.
