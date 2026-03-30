## Prescan the Codebase (orchestrator step)

This file is executed by the **orchestrator** (the main Claude Code session), NOT by individual review agents. The orchestrator reads files once and passes the results to all agents as a snapshot.

### Scan Procedure

Focus on frontend/UI code. Read broadly to capture enough for agents to catch real issues. Prioritize in this order — stop early if the codebase is large (>50 files):

1. Read manifest files (package.json, composer.json, Gemfile, etc.) to understand the stack
2. Detect framework: React, Vue, Svelte, Angular, Next.js, Nuxt, Astro, etc.
3. Detect CSS approach: Tailwind, CSS Modules, styled-components, Sass, vanilla CSS, etc.
4. Detect component library: shadcn, MUI, Chakra, Radix, Headless UI, etc.
5. Read design system files: theme config, token files, tailwind.config, CSS custom properties
6. Read up to 15 UI files: prioritize layout components, page components, shared components, then feature components
7. Check for design context files: `.impeccable`, `design-context.md`, or similar
8. Check for accessibility setup: eslint-plugin-jsx-a11y, axe-core, pa11y, etc.
9. Check for i18n setup: i18next, react-intl, FormatJS, etc.

{focus}

### Build the Snapshot

After reading, format ALL collected file contents into a single snapshot block. This is what gets passed to agents via the `{codebase_snapshot}` placeholder.

Format each file as:

````
### file: <relative_path>
```<ext>
<full file contents>
```
````

Include:
- All manifest and config files read
- Design system / theme files
- All UI source files read
- Design context files

Omit:
- Files matching `.env*`, `*.secrets`, `*credentials*.json`, `*.key`, `*.pem`, `secrets.yml` — list by name only
- Binary files — list by name only

**Snapshot size limit**: If the snapshot exceeds ~80K tokens (~400 source files), ask the user to narrow scope before proceeding.
