# Claude Code Configuration

Custom Claude Code configuration managed via this repo and symlinked into `~/.claude/`.

## Setup on a new machine

If `~/.claude/` doesn't exist yet, run `claude` once first to initialize it.

### Skills

```bash
ln -s "$SETUP_DIR/claude/skills" ~/.claude/skills
```

### Status line

Nothing to link. Both profiles' `settings.json` run
`bash $SETUP_DIR/claude/statusline-command_x.sh`, which exec's
`statusline-command.py` from its own directory in the repo. Every segment default
lives in the script, so the wrapper carries no exports — it stays as the seam
where a per-machine `CLAUDE_STATUSLINE_*` override would go.
The toggles and their defaults are listed in the script's module docstring.

### Hooks

The whole directory, so a new hook needs no second step on every machine:

```bash
ln -s "$SETUP_DIR/claude/hooks" ~/.claude/hooks
```

### Profile (settings)

Each profile directory (`mbp2022/`, `sbnorge/`) holds `settings.json`,
`settings.local.json` and `CLAUDE.md`. Profiles are named per config flavour,
not per machine, so `config.ini` carries a separate `claude_profile` key when
it differs from the machine profile.

```bash
for f in settings.json settings.local.json CLAUDE.md; do
  ln -sf "$SETUP_DIR/claude/<profile>/$f" ~/.claude/$f
done
```

## Adding a new skill

Create a subdirectory under `skills/` with a `SKILL.md` file:

```
claude/skills/
  my-skill/
    SKILL.md
```

The skill will be available immediately via the symlink.

## Project grouping (ccreport)

`ccreport` groups records into projects by a pure function over signals captured
at parse time, so regrouping never needs a re-parse:

1. **Git remote** — resolved from the session's `cwd` while the dir still exists
   (`git config remote.origin.url`, normalized to `host/path`). Grouped by the
   repo's *name* (last path segment), so moving a repo or changing its host/org
   (GitLab → GitHub) keeps history together. This is the durable identity: it
   survives the working dir being moved or deleted.
2. **Repo-root path** — for repos with no remote, the segment just under a
   repo root. `~/git` is always a repo root; per-machine extras (a config
   file can only add roots, never remove the baseline) live in
   `${XDG_CONFIG_HOME:-~/.config}/macsetup/claude/ccreport.toml`:

   ```toml
   repo_roots = ["~/dev", "~/dev/privat"]
   ```

   Matching is longest-prefix, so nested roots are fine in any order.
   Collapses subdirectories and worktrees. Editing the config invalidates the
   report cache, so records regroup on the next run.
3. **Dir-name / frozen label** — fallback for orphaned records whose source
   JSONL is already purged and whose dir can't be reconstructed.

### Manual merges and renames

The automatic rules can't know that a *renamed* repo (`ren.no` → `ren-platform`)
is the same project — that's human knowledge. Override rules live in the local
`project_overrides` table (never committed; snapshotted with the rest of the DB):

```bash
ccreport overrides                          # list active rules
ccreport merge <from-name> <into-name>      # group one name into another
ccreport merge <remote> <into> --kind remote
ccreport merge <cwd-prefix> <into> --kind cwd_prefix
ccreport unmerge <value>                    # remove a rule
```

A repo rename is one `ccreport merge <new-name> <old-name>` away. Rules apply at
report time, so the change shows up on the next run with no re-parse.

## Cache DB safety

The shared cache (`~/.cache/macsetup/claude/cache.db`) holds token/cost history
that can't always be reconstructed from JSONL — Claude Code purges its own
logs, and orphaned records in the cache are the only surviving record.

`cache_db.py` takes a daily online backup to
`~/.local/share/macsetup/claude/snapshots/YYYY-MM-DD.db` (UTC) before schema
work or migrations touch the live DB. Snapshots live outside `~/.cache` so a
cache sweep can't take the live DB and all its backups out in one pass.
Default retention is 14 snapshots.

After a migration that actually runs this invocation, a sanity check
compares `ccreport_records` against the most recent prior snapshot. If the
row count drops more than 10 %, a warning is printed with the restore
command (`cp <snapshot> <db>`). The check is gated to migration runs so
statusline renders don't pay the cost.

Overrides:

| Env var | Effect |
|---------|--------|
| `CLAUDE_CACHE_SNAPSHOT_DIR`     | Override snapshot directory |
| `CLAUDE_CACHE_SNAPSHOT_KEEP`    | Retention count (default 14) |
| `CLAUDE_CACHE_SNAPSHOT_DISABLE` | `=1` disables snapshots |
| `CLAUDE_CACHE_SANITY_DISABLE`   | `=1` disables the sanity check |
| `CLAUDE_CACHE_SANITY_ABORT`     | `=1` raises instead of warning on drop |
