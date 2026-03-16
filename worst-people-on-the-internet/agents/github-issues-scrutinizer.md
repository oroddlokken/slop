Scrutinize the codebase at {path} as GitHub Issues users would. Style: {style}.

## Step 1: Scan the Codebase

{scan_steps}

## Step 2: Synthesize Evidence

Identify:
- Strengths (2-3): things that work well enough that nobody would file an issue
- Weaknesses (5+): anything broken, confusing, undocumented, or annoying enough to warrant an issue
- Missing features: what users would expect but isn't there
- Documentation gaps: things that would cause confused issues
- Rage-inducing UX: anything that would cause a frustrated bug report at 2am

All findings MUST reference actual code with file paths and line ranges.

## Step 3: Generate the GitHub Issues

Generate 10-12 issues as if real users filed them against this repository. Mix of bug reports, feature requests, questions, and support requests.

Each issue has:
- Title: realistic issue title (some good, some terrible)
- Author: GitHub username with avatar description
- Labels: bug, enhancement, question, good first issue, help wanted, wontfix, duplicate, invalid
- State: open (most), closed (1-2)
- Reactions: 👍 👎 😄 🎉 ❤️ 🚀 👀 😕
- Timestamps: "opened 3 hours ago", "opened 2 days ago", etc.

## Step 4: Generate Issue Content and Discussions (across all issues)

GitHub Issues culture:
- **Entitled users**: treat maintainers like paid support staff, "when will this be fixed?"
- **Zero-effort reports**: "it doesn't work" with no reproduction steps, no environment info
- **+1 spam**: dozens of "+1" or 👍 comments instead of using reactions
- **Feature demands disguised as bugs**: "Bug: this project doesn't support X"
- **Drive-by closers**: maintainer closes with "not a bug" and locks the thread
- **Wall-of-text dumps**: full stack traces, entire config files, zero context
- **Cross-reference obsessed**: "Related to #47, #123, #891, possibly #12"
- **Stale bot warfare**: bot marks issues stale, users argue with the bot
- **"Me too" chains**: 30 comments that are just "I have this issue too" with different OS versions
- **Hostile forks**: "Since the maintainer clearly doesn't care, I've forked this at..."
- **Template ignorers**: issue template has 5 sections, user deletes all of them and writes one sentence

Issue types and their archetypes:

- Zero-effort bug report (~15%): "doesn't work on my machine" — no OS, no version, no steps
- Well-written bug report (~10%): proper reproduction steps, environment info, expected vs actual behavior
- Feature request as bug (~10%): "Bug: no dark mode" or "Bug: doesn't support Windows"
- Demanding feature request (~10%): "You NEED to add X, this is unusable without it"
- Polite feature request (~5%): reasonable ask with context and willingness to contribute
- Question-as-issue (~10%): should be on Stack Overflow or Discussions, not Issues
- "+1" pile-on issue (~5%): 20 comments that are just "+1" and "any update?"
- Stale bot victim (~5%): bot marks it stale, user protests, bot closes it anyway
- "Any update?" necro (~8%): comment on a 6-month-old issue asking if there's progress
- Hostile fork threat (~4%): frustrated user threatens to fork over a minor issue
- Security report in public (~3%): posts a vulnerability as a public issue instead of using security advisory
- Duplicate filer (~5%): exact same issue already exists, clearly didn't search
- Drive-by maintainer response (~5%): terse one-word close with no explanation
- Bot/CI noise (~5%): automated comments from bots cluttering the thread

Comment format rules:
- Show GitHub-style metadata: username, timestamp, member/contributor badges
- Include issue state changes: "X closed this as not planned", "X reopened this"
- Include label changes: "X added the bug label", "X removed the question label"
- Include cross-references: "X mentioned this issue in #Y"
- Include reactions on comments (👍 👎 😕 ❤️ 🚀 👀)
- At least one issue should have a `<!-- This is not a support forum -->` maintainer template
- At least one issue should have someone posting "I have the same issue" with completely different symptoms
- At least one issue should be closed by a bot with "This issue has been automatically closed due to inactivity"
- Include one issue where OP solves their own problem in the last comment and closes it without explaining the solution
- No AI tells: GitHub issues are terse, often frustrated, sometimes rude. No "I appreciate this project" preamble before complaints.

## Output Format

---

## 🐙 GitHub Issues

### Issues ({open_count} open · {closed_count} closed)

---

#### #{number} {issue_title}

**{username}** opened this issue {time_ago} · {comment_count} comments
{labels as colored badges}

{issue body}

👍 {count} 👎 {count} 😕 {count}

---

**{commenter}** commented {time_ago} {· Member/Contributor badge if applicable}

{comment body}

👍 {count}

---

*{bot_or_user} added the `{label}` label {time_ago}*

---

*{user} closed this as {completed/not planned} {time_ago}*

---

Separate issues with `---`. Show all metadata: labels, state changes, cross-references, reactions. Use `*italics*` for system events (label changes, closes, reopens).

## Findings Summary

After the issues, output a structured summary of all technical findings from the scan and issues:

```
| File | Lines | Issue | Severity | Category |
|------|-------|-------|----------|----------|
| path/to/file.py | 10-25 | Description of issue | red-flag/concern/nitpick | security/architecture/correctness/missing-feature/docs |
```

Only include findings grounded in actual code. This is the primary output — be thorough.

## Style Adjustment

- **balanced**: mix of well-written issues and typical GitHub noise
- **snarky**: maintainer responses are terse and dismissive, users are passive-aggressive
- **supportive**: issues are constructive, commenters offer PRs, maintainer is responsive
- **hostile**: every issue is a complaint, every response is "wontfix", someone threatens a fork
