Scrutinize the codebase at {path} as Tech Twitter/X would. Style: {style}.

## Step 1: Scan the Codebase

{scan_steps}

## Step 2: Synthesize Evidence

Identify:
- Strengths (3-5): what would get genuine praise
- Risks (3-5): what would get dunked on
- Hot take angles: controversial opinions this project could trigger
- Ratio potential: what could cause the announcement to get ratioed

All findings MUST reference actual code with file paths.

## Step 3: Generate the Announcement Tweet Thread (1-4 tweets)

- Author: realistic Twitter handle and display name
- Verified: blue check or not
- Thread format with 🧵
- Excited but not cringe — proud but slightly nervous
- Content: what it does, why they built it, CTA
- Metrics: likes, retweets, replies, views

## Step 4: Generate 15 Reactions

Tweet length rules:
- Free accounts: 280 characters max
- Premium/Blue accounts: up to 4,000 characters — long-form posts are common in tech Twitter now
- Most reactions are short (1-3 sentences), but thread-bros and senior dev flexes often use premium-length posts
- Mark long posts with ✦ (Premium indicator) next to the handle

Reaction types: reply, quote_tweet. Each needs author handle, display name, body, likes, retweets.

Archetypes (approximate weights — creative direction, not empirical):
- Hype beast (~10%): "This is incredible 🔥🔥🔥 shipping this to prod TODAY"
- Dunker (~12%): one-line devastating takedown
- Thread-bro (~8%): unsolicited advice thread (often premium-length)
- "Just use X" (~8%): recommends their preferred alternative
- Genuine questioner (~8%): real technical question
- Self-promoter (~7%): "Cool! I built something similar →"
- Framework warrior (~7%): "Imagine not using {framework} in [current year]"
- Meme replier (~7%): meme reference or copypasta
- Senior dev flex (~6%): "We solved this at {FAANG} in 2019..."
- Supportive indie (~6%): genuine encouragement
- Ratio king (~4%): more likes than the original
- AI accuser (~7%): "This was 100% vibe coded lmao" / "ChatGPT wrote this right"
- Engagement farmer (~5%): "What's your stack? Reply below 👇🧵" — turns everything into engagement bait
- Bookmarker (~3%): "Bookmarked 🔖" — announces they saved it instead of engaging
- Subtweeter (~2%): vagues about the project without directly replying

Rules:
- Brevity is king: 1-3 sentences max
- Emoji usage: heavy (🔥💀😤🫡👀💯🚀)
- Reference specific files ("that index.ts is wild")
- Hot takes get more likes, dunks get retweets
- Only ratio if genuinely warranted
- Include 2-3 mini-debates (reply chains)
- No AI tells: no "I think it's worth mentioning" — snappy, opinionated, sometimes mean

Twitter culture: punchy, memetic, hyperbolic, clout-aware, casually cruel. Short fragmented sentences. Emoji as punctuation. "ratio" as a standalone reply. Subtweets. Accusing everything of being AI-generated. Builder/shipper one-upmanship.

## Output Format

---

## 𝕏 Tech Twitter

### Thread by @{handle}

**{display_name}** {✓ if verified} {✦ if premium} · {likes} ♥ · {retweets} 🔁 · {views} views

**1/** {tweet text}

**2/** {tweet text}

---

#### Reactions

---

💬 **@{replier}** {✓} {✦} · {likes} ♥
{reply text}

---

🔁 **@{quoter}** · {likes} ♥ · {retweets} 🔁
{quote tweet}
> QT: @{handle}: "{snippet}..."

---

💬 🔥 **@{ratio_replier}** · {likes} ♥ ← ratio
{devastating reply}

---

Mark ratio replies with 🔥 and "← ratio". Use 💬 for replies, 🔁 for quote tweets.

## Findings Summary

After the reactions, output a structured summary of all technical findings from the scan and reactions:

```
| File | Lines | Issue | Severity | Category |
|------|-------|-------|----------|----------|
| path/to/file.py | 10-25 | Description of issue | red-flag/concern/nitpick | security/architecture/correctness/missing-feature/docs |
```

Only include findings grounded in actual code. This is the primary output — be thorough.
