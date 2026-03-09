# Worst People on the Internet

Simulate how six online communities would tear apart your codebase, then distill the combined roasting into a prioritized list of things to actually fix.

## What you get

Six agents independently scan your code and generate realistic community discussions — Reddit threads, HN comment trees, Twitter dunks, Lobste.rs nitpicks, /g/ shitposts, and Fediverse CW-laden critique. After all six finish, findings are deduplicated across communities and distilled into:

- **Fix Now** — correctness, security, data integrity issues
- **Should Address** — quality and maintainability concerns
- **Consider** — valid but non-urgent suggestions
- **Skipped Noise** — memes, bikeshedding, and pure opinion (ignored)

Every action item includes a file path and line range. No vague suggestions.

## Communities

| Community | Vibe |
|-----------|------|
| Reddit | Cynical, pedantic, subreddit-aware |
| Hacker News | Long-winded, contrarian, tangent-prone |
| Tech Twitter/X | Punchy, memetic, casually cruel |
| Lobste.rs | Deeply technical, correctness-obsessed |
| 4chan /g/ | Brutal, anonymous, anti-everything |
| Fediverse | Anti-corporate, accessibility-first, CW-liberal |

## Options

| Option | Values | Default |
|--------|--------|---------|
| Mode | `full` (all six) or pick one community | `full` |
| Style | `balanced` / `snarky` / `supportive` / `hostile` | `balanced` |
| Focus | `testing`, `security`, `architecture`, `performance`, `error-handling`, `docs`, `dependencies`, `accessibility`, or blank | blank (general) |
| Subreddit | Any subreddit name (Reddit mode only) | Auto-detected from project language |

## Installation

Tell your agent to read this repository and ask it to help you integrate it into your Claude Code setup as a skill.

## Origin

Fork of [reddit-scrutinizer](https://github.com/HelgeSverre/reddit-scrutinizer) by Helge Sverre. The original is a TypeScript CLI that generates realistic Reddit threads (with theme skins for HN, Twitter, etc.) as the end product. This fork reimplements the idea as Claude Code skill + agent prompts, adds five more communities with genuinely distinct voices and cultures (not just reskinned Reddit), and — most importantly — adds a **distill step** that cross-references findings from all six communities and produces deduplicated, file-path-grounded action items. The simulated discussions are a means to an end; the prioritized fix list is the actual deliverable.

## License

MIT (same as the [original](https://github.com/HelgeSverre/reddit-scrutinizer)).
