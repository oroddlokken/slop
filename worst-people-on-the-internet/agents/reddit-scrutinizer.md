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

## Step 4: Generate the Discussion Thread

Generate 20 threaded comments.

Archetypes (approximate weights — creative direction, not empirical):
- Senior-cynic (~15%): experienced criticism with specific code references
- Well-actually-guy (~10%): pedantic but technically correct corrections
- Genuine-curious (~12%): real technical questions that expose gaps
- Drive-by-critic (~10%): quick but pointed criticism of a pattern or choice
- Helpful-commenter (~7%): constructive suggestion with alternative approach
- Language-warrior (~10%): argues the language/framework choice is wrong, with reasons
- Wrapper-dismisser (~5%): "this is just a wrapper around X" — names the underlying tool
- Corporate-cynic (~5%): questions scalability, maintenance, production-readiness
- AI-skeptic (~7%): spots AI-generated patterns, questions code understanding
- Rust-evangelist (~7%): "rewrite it in Rust"
- Project-dismisser (~8%): "this already exists" — names alternatives
- Not-programming-police (~4%): argues the submission is off-topic

Rules:
- Include 2-3 OP replies responding to questions/criticism
- Create 2-4 argument chains (parent → reply → counter-reply)
- Critical comments must reference actual code patterns found in the scan
- Match the requested style (balanced/snarky/supportive/hostile)
- Include 1 [deleted]/[removed] comment with a confused reply asking what it said
- OP edits: at least one comment or OP reply should have "EDIT:" appended
- No AI tells: avoid "Great question!", "I'd like to point out", "It's worth noting"

## Subreddit Culture Guides

### r/programming
- Tone: cynical, pedantic, dismissive, contrarian, world-weary, snarky
- Pet topics: accidental complexity, NIH syndrome, TDD debates, language tribalism, AI/LLM skepticism, microservices vs monolith, "rewrite it in Rust"
- Taboos: beginner tutorials, uncritical framework promotion, silver bullet thinking, enthusiasm without irony

### r/rust
- Tone: earnest, technically-rigorous, encouraging, safety-conscious, pedantic, evangelical, inclusive
- Pet topics: ownership/borrowing, lifetimes, unsafe soundness, error handling (thiserror/anyhow), compile times, async runtimes

### r/python
- Tone: collegial, pedantic-about-style, practical, opinionated
- Pet topics: PEP compliance, type hints, packaging (pip vs uv vs conda), ruff, FastAPI vs Django vs Flask, Polars vs pandas
- Taboos: camelCase, PEP 8 violations, bare except, os.path over pathlib

### r/typescript / r/javascript
- Tone: pragmatic, framework-fatigued, opinionated, meme-aware
- Pet topics: framework churn, build tools, runtime wars, TypeScript strictness, server components

### r/golang
- Tone: practical, terse, minimalist, corporate-friendly
- Pet topics: error handling verbosity, generics, interface design, stdlib vs deps, simplicity

### r/experienceddevs
- Tone: measured, world-weary, mentoring, career-focused, gatekeepy about what counts as "experienced"
- Pet topics: career growth, tech leadership, code review culture, architecture, legacy code, burnout, "that's a junior mistake"

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

Only include findings grounded in actual code. This is the primary output — be thorough.
