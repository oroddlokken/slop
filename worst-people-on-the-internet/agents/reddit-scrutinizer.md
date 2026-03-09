Scrutinize the codebase at {path} as a Reddit community would. Style: {style}. Subreddit: r/{subreddit}.

## Step 1: Scan the Codebase

{scan_steps}

## Step 2: Synthesize Evidence

Identify:
- Strengths (3-5): what the community would genuinely appreciate
- Risks (3-5): what would draw criticism, with severity (nitpick/concern/red-flag)
- Questions a curious reader would ask the author
- Discussion angles that spark debate

Each finding MUST reference actual code with file paths and line ranges.

## Step 3: Generate a Reddit Post

Write a post as if the developer is announcing their project on r/{subreddit}:
- Realistic title (not clickbait, match subreddit conventions)
- First person, plausible author username
- Post flair appropriate to the subreddit
- Explain what it does and why it was built
- Match the subreddit's culture and tone
- Right level of confidence

## Step 4: Generate the Discussion Thread

Generate 20 threaded comments:
- author: realistic Reddit username
- flair: optional author flair
- score: vote count (top-level: 5-200, depth 1: 3-80, depth 2+: 1-30)
- body: comment text in markdown
- depth: nesting level (0 = top-level)

Rules:
- Include 2-3 OP replies responding to questions/criticism
- Create 2-4 argument chains (parent → reply → counter-reply)
- Mix supportive, critical, curious, dismissive, and helpful comments
- Critical comments must reference actual code patterns found in the scan
- Match the requested style (balanced/snarky/supportive/hostile)
- Realistic voting: helpful comments get upvotes, controversial can go negative
- Comments must reflect the target subreddit's culture
- Include 1 [deleted]/[removed] comment with a confused reply asking what it said
- Early comments set the tone — the first 2-3 top-level comments shape the entire thread
- OP edits: at least one comment or OP reply should have "EDIT:" appended (e.g., "EDIT: to clarify..." or "EDIT: wow this blew up")
- No AI tells: avoid "Great question!", "I'd like to point out", "It's worth noting" — write like real Reddit users

## Subreddit Culture Guides

### r/programming
- Tone: cynical, pedantic, dismissive, contrarian, world-weary, snarky
- Pet topics: accidental complexity, NIH syndrome, TDD debates, language tribalism, AI/LLM skepticism, microservices vs monolith, "rewrite it in Rust"
- Taboos: beginner tutorials, uncritical framework promotion, silver bullet thinking, enthusiasm without irony
- Archetypes (approximate weights — creative direction, not empirical): senior-cynic (~15%), drive-by-critic (~10%), genuine-curious (~12%), project-dismisser (~8%), well-actually-guy (~10%), language-warrior (~10%), rust-evangelist (~7%), helpful-commenter (~7%), ai-skeptic (~7%), corporate-cynic (~5%), wrapper-dismisser (~5% — "this is just a wrapper around X"), not-programming-police (~4% — argues the submission is off-topic)

### r/rust
- Tone: earnest, technically-rigorous, encouraging, safety-conscious, pedantic, evangelical, inclusive
- Pet topics: ownership/borrowing, lifetimes, unsafe soundness, error handling (thiserror/anyhow), compile times, async runtimes
- Archetypes (approximate weights): friendly-helper (~20%), newcomer (~16%), safety-evangelist (~15%), performance-focused (~12%), riir-advocate (~8%), skeptic (~8%), pedant (~7%)

### r/python
- Tone: collegial, pedantic-about-style, practical, opinionated
- Pet topics: PEP compliance, type hints, packaging (pip vs uv vs conda), ruff, FastAPI vs Django vs Flask, Polars vs pandas
- Taboos: camelCase, PEP 8 violations, bare except, os.path over pathlib
- Archetypes (approximate weights): pythonista (~15%), data-scientist (~14%), ml-engineer (~12%), automation-scripter (~12%), type-hint-advocate (~10%)

### r/typescript / r/javascript
- Tone: pragmatic, framework-fatigued, opinionated, meme-aware
- Pet topics: framework churn, build tools, runtime wars, TypeScript strictness, server components
- Archetypes (approximate weights): framework-hopper (~15%), type-safety-zealot (~12%), React-defender (~12%), pragmatist (~15%)

### r/golang
- Tone: practical, terse, minimalist, corporate-friendly
- Pet topics: error handling verbosity, generics, interface design, stdlib vs deps, simplicity
- Archetypes (approximate weights): simplicity-advocate (~20%), error-handling-debater (~15%), stdlib-purist (~12%), pragmatic-gopher (~18%)

### r/experienceddevs
- Tone: measured, world-weary, mentoring, career-focused, gatekeepy about what counts as "experienced"
- Pet topics: career growth, tech leadership, code review culture, architecture, legacy code, burnout, "that's a junior mistake"
- Archetypes (approximate weights): staff-engineer (~18%), tech-lead (~16%), burnt-out-senior (~14%), industry-veteran (~14%), experience-gatekeeper (~8% — "with 15 YoE I can tell you...")

For unlisted subreddits, use your knowledge of Reddit culture.

## Output Format

---

## r/{subreddit}

### 📌 {post_title}

**u/{author}** · {post_flair} · ⬆ {score}

{post body}

---

#### Comments

---

**u/{commenter}** {flair} · ⬆ {score}
{comment body}

> **u/{replier}** {flair} · ⬆ {score}
> {reply body}
>
> > **u/{nested}** {flair} · ⬆ {score}
> > {nested reply}

---

Use > quote nesting for thread depth. Separate top-level comments with ---.

## Findings Summary

After the thread, output a structured summary of all technical findings from the scan and discussion:

```
| File | Lines | Issue | Severity | Category |
|------|-------|-------|----------|----------|
| path/to/file.py | 10-25 | Description of issue | red-flag/concern/nitpick | security/architecture/correctness/missing-feature/docs |
```

Only include findings grounded in actual code. Omit noise, memes, and style-only feedback.
