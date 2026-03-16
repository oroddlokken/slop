Scrutinize the codebase at {path} as LinkedIn tech influencers would. Style: {style}.

## Step 1: Scan the Codebase

{scan_steps}

## Step 2: Synthesize Evidence

Identify:
- Strengths (3-5): anything that can be spun into a "leadership lesson" or "10x engineer" narrative
- Weaknesses (3-5): anything that would make a thought leader write a parable about why startups fail
- Humble-brag angles: how the author could frame technical debt as "lessons learned on my journey"
- Engagement-bait potential: controversial choices that could become "Agree? 👇" polls

All findings MUST reference actual code with file paths.

## Step 3: Generate the LinkedIn Post

Write a LinkedIn post announcing the project:
- Author: realistic LinkedIn profile (full name, title like "Engineering Leader | Ex-FAANG | Building the Future of X | Father of 2")
- Format: the dreaded LinkedIn post style — short paragraphs, each on its own line, dramatic pauses, a hook that has nothing to do with the project for the first 3 lines
- Start with an unrelated anecdote that eventually connects to the project
- "...see more" break point after the hook
- End with a call to action: "What do you think? Drop your thoughts below 👇"
- Reactions: 👍 Like, ❤️ Love, 💡 Insightful, 🎉 Celebrate — with counts
- Connection degree shown: 1st, 2nd, 3rd

## Step 4: Generate 15 Reactions

LinkedIn culture:
- **Performative positivity**: everything is amazing, inspiring, and a journey
- **Humble-bragging**: "I failed at X, and that's how I became VP at Google"
- **Corporate buzzwords**: synergy, leverage, north star, move the needle, thought leadership
- **Engagement farming**: "Agree? 👇", "Repost if you believe in...", "Comment YES if..."
- **Inspirational poverty**: "I was rejected from 200 jobs. Now I manage 500 engineers."
- **Broetry**: one. sentence. per. line. for. dramatic. effect.
- **Congratulations spam**: "Congrats! 🎉" on everything regardless of context
- **Hot takes disguised as advice**: "Unpopular opinion: you should write tests" — 50K likes
- **"I'm humbled"**: nobody on LinkedIn has ever not been humbled
- **Selfie with laptop**: [Photo: person at standing desk with MacBook and company hoodie]
- **Repost carousel**: the same post shared by 40 people in a network with "THIS 👆" added

Archetypes (approximate weights — creative direction, not empirical):
- Congratulator (~12%): "This is amazing! Congrats on shipping! 🎉🚀" — adds zero value
- Thought leader (~10%): writes 5 paragraphs tangentially related to the project about "what I learned building teams at scale"
- "Agree?" farmer (~8%): reposts with "This is why senior engineers matter. Agree? 👇"
- Humble bragger (~8%): "Reminds me of when I built something similar at {FAANG}. Of course we had 200 engineers..."
- Hot take artist (~8%): "Unpopular opinion:" followed by the most popular opinion possible
- Corporate buzzword machine (~7%): "This really moves the needle on developer velocity and synergizes the feedback loop"
- Recruiter (~8%): "Great project! Are you open to new opportunities? We have exciting roles at..."
- Emoji abuser (~6%): "🔥💯🚀 THIS is what innovation looks like 🙌👏✨"
- Counter-signaler (~5%): actually writes a substantive technical comment, wildly out of place
- Inspirational story teller (~6%): connects the project to overcoming adversity, 3 paragraphs of broetry
- Self-promoter (~7%): "Love this! I wrote about a similar approach in my newsletter → [link]"
- "Resharing for my network" (~5%): reposts verbatim, adds "Resharing because this deserves more visibility 👀"
- AI hype integrator (~5%): "Now imagine this with AI! 🤖 The possibilities are endless"
- Poll creator (~5%): creates a poll: "What matters most in open source? A) Code quality B) Documentation C) Community D) All of the above"

Comment format rules:
- Show name, title, connection degree (1st, 2nd, 3rd)
- Show reaction types (👍 ❤️ 💡 🎉) with counts
- Include "· Edited" on at least one comment
- At least one comment should be clearly AI-generated boilerplate
- One comment should tag 3-4 people: "@John Smith @Jane Doe thoughts?"
- One reply chain should devolve into people sharing their own unrelated projects
- One comment should be a recruiter DMing in public by accident
- Broetry format: one sentence per line, dramatic line breaks, build to a "lesson"
- No AI tells is ironic here — LinkedIn IS the AI tell. Lean into it. The more corporate-sanitized and hollow, the more authentic it sounds for LinkedIn.

## Output Format

---

## 💼 LinkedIn

### {author_name}

**{title}** · {connection_degree} · {time_ago}

{post body — broetry format, one sentence per paragraph}

{hashtags: #OpenSource #Engineering #Innovation #Leadership}

👍 {like_count} · ❤️ {love_count} · 💡 {insightful_count} · 🎉 {celebrate_count}

{comment_count} comments · {repost_count} reposts

---

#### Comments

---

**{commenter_name}** · {title} · {connection_degree}

{comment body}

👍 {reactions}

> **{replier_name}** · {title} · {connection_degree}
> {reply body}

---

Use `>` for reply nesting. Show professional titles on every commenter. Reaction emojis on comments.

## Findings Summary

After the comments, output a structured summary of all technical findings from the scan and comments:

```
| File | Lines | Issue | Severity | Category |
|------|-------|-------|----------|----------|
| path/to/file.py | 10-25 | Description of issue | red-flag/concern/nitpick | security/architecture/correctness/missing-feature/docs |
```

Only include findings grounded in actual code. This is the primary output — be thorough.

## Style Adjustment

- **balanced**: mix of genuine technical comments and LinkedIn cringe — maybe 30/70
- **snarky**: the counter-signalers dominate, mocking the LinkedIn format while using it
- **supportive**: full LinkedIn energy — everything is amazing, inspiring, and a journey
- **hostile**: "I've managed 500 engineers and this is the worst architecture I've ever seen. Here's why (a thread 🧵):"
