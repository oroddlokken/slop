## Scan the Codebase

Build a project dossier by reading key files. Focus on frontend/UI code. Prioritize in this order — stop early if the codebase is large (>50 files):

1. Read manifest files (package.json, composer.json, Gemfile, etc.) to understand the stack
2. Detect framework: React, Vue, Svelte, Angular, Next.js, Nuxt, Astro, etc.
3. Detect CSS approach: Tailwind, CSS Modules, styled-components, Sass, vanilla CSS, etc.
4. Detect component library: shadcn, MUI, Chakra, Radix, Headless UI, etc.
5. Read design system files: theme config, token files, tailwind.config, CSS custom properties
6. Read up to 15 UI files: prioritize layout components, page components, shared components, then feature components
7. Check for design context files: `.impeccable`, `design-context.md`, or similar
8. Check for accessibility setup: eslint-plugin-jsx-a11y, axe-core, pa11y, etc.
9. Check for i18n setup: i18next, react-intl, FormatJS, etc.

### What to Look For

When reading each UI file, note:
- Component structure and nesting depth
- How styles are applied (inline, classes, tokens, hardcoded values)
- Interactive element states (hover, focus, active, disabled, loading, error)
- Responsive handling (breakpoints, media queries, container queries)
- Accessibility (semantic HTML, ARIA, alt text, labels, keyboard handling)
- Typography usage (font families, sizes, weights, line heights)
- Color usage (tokens vs hardcoded, contrast, consistency)
- Spacing patterns (consistent scale vs arbitrary values)
- Animation/transition usage
- Error and empty states
- Loading states

{focus}

All findings MUST reference actual code with file paths and line numbers.
