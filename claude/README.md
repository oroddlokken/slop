# Claude Code Configuration

Custom Claude Code configuration managed via this repo and symlinked into `~/.claude/`.

## Setup on a new machine

If `~/.claude/` doesn't exist yet, run `claude` once first to initialize it.

### Skills

```bash
ln -s "$SETUP_DIR/claude/skills" ~/.claude/skills
```

### Status line

The status line script is shared across all profiles:

```bash
ln -sf "$SETUP_DIR/claude/statusline-command.py" ~/.claude/statusline-command.py
```

### Profile (settings)

Each profile directory (`sbnorge/`, `personal/`, etc.) contains a `settings.json`. Symlink the appropriate profile into `~/.claude/`:

**SB Norge (work):**

```bash
ln -sf "$SETUP_DIR/claude/sbnorge/settings.json" ~/.claude/settings.json
```

**Personal:**

```bash
ln -sf "$SETUP_DIR/claude/personal/settings.json" ~/.claude/settings.json
```

## Adding a new skill

Create a subdirectory under `skills/` with a `SKILL.md` file:

```
claude/skills/
  my-skill/
    SKILL.md
```

The skill will be available immediately via the symlink.

## Adding a new agent

Create a markdown file under `agents/`:

```
claude/agents/
  my-agent.md
```

Skills reference agents by reading `~/.claude/agents/<name>.md` and passing the contents as an agent prompt.
