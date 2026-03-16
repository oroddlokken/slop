Scrutinize the codebase at {path} as Stack Overflow would. Style: {style}.

## Step 1: Scan the Codebase

{scan_steps}

## Step 2: Synthesize Evidence

Identify:
- Strengths (2-3): clear structure, good naming, follows conventions — things SO wouldn't complain about
- Weaknesses (5+): anything that would get a question closed, downvoted, or edited by a 50k rep user
- Duplicate potential: what parts of this code ask questions that already have canonical answers
- Close-vote magnets: vague patterns, opinion-based choices, "too broad" architecture decisions

All findings MUST reference actual code with file paths and line ranges.

## Step 3: Generate the Stack Overflow Question

Write a question as if the developer posted about a problem in their own codebase:
- Title: specific, follows SO conventions (not "How do I...?" but a searchable problem statement)
- Tags: 3-5 appropriate tags (language, framework, specific topic)
- Author: realistic username with rep count and badges
- Vote count: -3 to 15 (most questions don't score high)
- Views: 50-2000
- Body: code dump that's slightly too long, not a minimal reproducible example, buries the actual question
- "Thanks in advance!" or "Any help appreciated" at the end (SO hates this)

## Step 4: Generate the Interaction (15 comments/answers)

Stack Overflow culture:
- **Hostile to beginners**: "what have you tried?", "show your research", "read the docs"
- **Close-vote obsessed**: everything is a duplicate, too broad, or opinion-based
- **Edit wars**: high-rep users rewrite your question without asking
- **Rep-driven**: answering fast matters more than answering well
- **Passive-aggressive**: weaponized politeness, "as clearly stated in the documentation..."
- **Necro-posting**: old answers suddenly get comments years later
- **Answer-in-comments**: crucial information buried in a comment, never posted as an answer
- **FGITW** (Fastest Gun in the West): race to post first, edit quality in later
- **Canonical obsession**: "this has been asked and answered 47 times"
- **Comment moderation**: "comments are not for extended discussion — this conversation has been moved to chat"

Mix of answers, comments on the question, and comments on answers. Include close votes and edit history.

Archetypes (approximate weights — creative direction, not empirical):
- Close-vote hammer (~12%): gold tag badge holder, immediately votes to close as duplicate, links canonical Q&A
- FGITW answerer (~10%): posts a one-liner first, edits 6 times in 3 minutes to add explanation
- Comprehensive answerer (~10%): 800-word answer with examples, benchmarks, and caveats — posted 45 minutes after the FGITW
- "Read the docs" commenter (~10%): links to documentation, implies OP didn't try
- Pedantic editor (~8%): edits the question to fix formatting, removes "thanks", changes title
- Comment-answerer (~8%): posts the actual solution as a comment, never writes an answer
- XY problem detective (~7%): "You're asking about X but your real problem is Y"
- Downvote-without-explaining (~6%): mysterious downvote, OP asks "why the downvote?", silence
- Outdated answer (~6%): correct for a 3-year-old version, dangerously wrong now, still has 200 upvotes
- "Possible duplicate" linker (~5%): finds a vaguely related question and hammers it
- Snarky one-liner (~5%): "Why would you ever do this?" — 47 upvotes
- Bounty desperation (~4%): OP adds a bounty after 3 days of no answers
- Moderator diamond (~4%): appears to lock, migrate, or add post notices
- Actually helpful new user (~5%): posts a good answer, gets no upvotes because they have 1 rep

Post format rules:
- Answers have vote counts, accepted checkmarks (✅), and timestamps
- Comments are under questions or answers, with upvote counts
- Include edit history markers: "edited 3 mins ago", "edited by {high_rep_user}"
- Include close-vote banner if applicable: "This question has been marked as a duplicate of..."
- Include at least one "This does not provide an answer to the question" flag on a comment-as-answer
- Use SO-style code formatting (indented blocks, backtick inline)
- Rep displayed as: `{username} ({rep})` with badge counts like `●1 ●5 ●12`
- Show "asked X ago" and "active X ago" timestamps
- At least one answer should start with "You should never do it this way" without explaining what way to use instead
- Include one "I know this is an old question, but..." answer
- No AI tells: no "Great question!", no "That's a really interesting approach". SO users are blunt, terse, and often rude-by-omission.

## Output Format

---

## 📋 Stack Overflow

### {question_title}

**{username}** ({rep} · ●{gold} ●{silver} ●{bronze}) · Asked {time_ago} · Modified {time_ago} · Viewed {views} times

{tags as inline code blocks}

⬆ {votes}

{question body with code blocks}

---

#### {answer_count} Answers

Sorted by: Highest score (default)

---

⬆ {votes} {✅ if accepted}

**{answerer}** ({rep} · ●{gold} ●{silver} ●{bronze}) · answered {time_ago}

{answer body}

> 💬 **{commenter}** ({rep}) · {comment text} — {upvotes} upvote(s)

---

Use `>` for comments under answers. Show vote counts on everything. Mark accepted answer with ✅.

#### Close Votes / Notices

{Any close vote banners, duplicate notices, or moderator actions}

## Findings Summary

After the thread, output a structured summary of all technical findings from the scan and discussion:

```
| File | Lines | Issue | Severity | Category |
|------|-------|-------|----------|----------|
| path/to/file.py | 10-25 | Description of issue | red-flag/concern/nitpick | security/architecture/correctness/missing-feature/docs |
```

Only include findings grounded in actual code. This is the primary output — be thorough.
