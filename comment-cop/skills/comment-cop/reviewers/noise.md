# Find Comment Noise & Decoration

Scan for comments that exist for visual theater rather than information: banner blocks, ASCII dividers, section headers that substitute for real structure, and redundant type/label restatements. These add vertical noise, invite copy-paste inconsistency, and make files longer without making them clearer. Where a file needs sections, functions and modules — not comment art — are the tool.

## What to Look For

### Banner and divider theater
- `# ============================`, `# ----------------------------`, `#############################` separators
- ASCII-art headers, boxed titles (`# ┌──────┐`), figlet banners
- `# ===== SECTION: HELPERS =====` dividers carving one file into "sections" that should probably be separate modules or are already obvious

### Redundant labels
- `# CONSTANTS`, `# IMPORTS`, `# MAIN`, `# --- config ---` labeling things the language structure already makes obvious
- `# region` / `# endregion` folding markers used decoratively
- File-header comment blocks restating the filename, or a copyright/boilerplate banner duplicated in every file (note if it's mandated policy — then it's not a finding)

### Type/name restatement decoration
- `x: int  # int` / `name: str  # the name string` — the annotation already says it
- Aligned trailing comments that just echo the field name (`self.count = 0  # count`)
- Enum/constant blocks where each line's comment repeats the constant name

### Emoji / tone noise
- Decorative emoji or exclamation clutter in comments that add no meaning
- "Here be dragons" style flavor with no actual warning content (if there IS a real hazard, that's a legitimate `missing-why`/warning — flag only empty flavor)

### Over-sectioning
- Dozens of section-divider comments in a file — a signal the file should be split, expressed as comment decoration instead

## How to Scan

1. **Grep for divider runs** — lines that are mostly `=`, `-`, `#`, `*`, `/`, box-drawing chars.
2. **Grep for label-only comments** — a comment whose entire content is a single uppercase word matching a language construct (`# IMPORTS`, `# HELPERS`).
3. **Scan trailing comments** for ones that echo the variable/field/type they sit beside.
4. **Look for repeated boilerplate headers** across files — determine whether it's policy (keep) or accretion (flag).
5. **Count section dividers per file** — a high count is itself a finding (the file wants splitting).
6. **Leave real structure alone.** A `# --- public API ---` divider in a long module *can* aid navigation; only flag decoration that carries no navigational value or that papers over a file that should be split.

## Report Findings

For each noise item:

| Field | Content |
|-------|---------|
| **Location** | file:line (range for blocks) |
| **Type** | Banner/divider / redundant label / type restatement / emoji-flavor / over-sectioning |
| **Suggestion** | Delete — or, for over-sectioning, "split into modules instead of comment sections" |

### Severity Guide

- **Low**: Nearly all noise — cosmetic clutter, delete when nearby.
- **Medium**: Only pervasive over-sectioning where comment dividers are standing in for a module split that would materially improve the file — report as one systemic finding with the refactor suggestion.

## Output Format

After scanning, output your `## Findings Summary` table:

| # | Severity | File:Line | Issue | Suggestion |
|---|----------|-----------|-------|------------|
| 1 | Low | app.py:1-6 | ASCII banner box restating the module name | Delete; the module docstring already names it |

## Rules

- **Default to delete.** Decoration is subtractive-only — the fix is removal.
- **Respect mandated boilerplate.** Copyright/license headers required by policy are not findings — note the policy and move on.
- **Navigational dividers can earn their place** in a long file; flag only empty decoration or dividers substituting for a needed split.
- **Type restatement next to prose belongs here; prose narrating logic is `restates-code`.** Don't double-report — this lens owns the decorative/label/type-echo cases.
