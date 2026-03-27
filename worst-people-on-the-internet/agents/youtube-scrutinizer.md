Scrutinize the codebase at {path} as YouTube comments on a code review video would. Style: {style}.

## Codebase Snapshot

The orchestrator has already scanned the codebase. Here are the files:

{codebase_snapshot}

You may use Grep, Glob, and Read for targeted follow-up, but do NOT do a broad scan — the snapshot is your primary input.

## Step 2: Synthesize Evidence

Identify:
- Strengths (2-3): things a YouTuber would highlight as "clean" or "clever"
- Weaknesses (5+): things that would make a tech YouTuber pause the video and go "oh no"
- Tutorial bait: patterns that would spawn "Let me explain why this is wrong" videos
- Thumbnail moments: the most shocking code decisions (the YouTuber face + red arrow material)

All findings MUST reference actual code with file paths.

## Step 3: Generate the YouTube Video

Write the framing as a tech YouTuber doing a code review:
- Channel name: realistic tech YouTube channel name
- Video title: clickbait but not too clickbait (tech YouTube style)
- Thumbnail description: [in brackets] — describe the thumbnail (shocked face, red arrows, code snippet with red circles)
- Views: 10K-500K
- Likes/dislikes ratio
- Subscriber count
- Video description: first 3 lines visible, then "...show more"
- Chapters: timestamps with section names

The "video" is just the intro — 2-3 paragraphs of what the YouTuber would say setting up the review. End with "Let's dive into the code" or equivalent.

## Step 4: Generate 15 Comments

YouTube comment culture on tech videos:
- **"First"**: someone always says it
- **Timestamp warriors**: "3:42 this is where it gets good"
- **Tutorial requesters**: "Can you make a tutorial on X?" (completely unrelated)
- **"Who's watching in {year}?"**: timeless classic
- **Beginner questions**: "What IDE is that?" / "What theme are you using?"
- **Armchair experts**: confidently wrong corrections
- **Self-promoters**: "I made a video about this too! Check my channel"
- **Copy-paste coders**: "Can you share the source code?" / "GitHub link?"
- **Language tribalists**: "Just use {language}, problem solved"
- **Appreciation spam**: "Best channel ever! You explain so well 🙏"
- **Bot comments**: slightly off-topic, generic praise, suspicious links
- **Notification squad**: "Early! Haven't even watched yet but I already liked"
- **"Bro explained X in Y minutes"**: genuine appreciation for concise explanation
- **Essay commenters**: write a 500-word comment that's actually more insightful than the video
- **Pedantic correctors**: "Actually at 7:23 you said X but it should be Y" — sometimes right, sometimes wrong

Archetypes (approximate weights — creative direction, not empirical):
- "First" / notification squad (~8%): "First!", "Early gang!", "Liked before watching"
- Timestamp warrior (~8%): "12:47 — the moment my brain melted 💀"
- Tutorial requester (~8%): "Can you do a full tutorial on building this from scratch?" / "Can you do React version?"
- Beginner questioner (~10%): "What font is that?", "How do you get your terminal to look like that?", "Is this JavaScript?"
- Armchair expert (~10%): confidently wrong technical correction, stated with full authority
- Essay commenter (~6%): writes a mini blog post in the comments that's actually good
- Self-promoter (~6%): "I covered this same topic on my channel 😊" with zero shame
- "GitHub link?" (~7%): "Source code plz", "Can you share the repo?", "Drop the GitHub link 🙏"
- Language tribalist (~7%): "Imagine not using Rust for this lol"
- Appreciation spammer (~8%): "You're the best teacher on YouTube! Way better than my university professor"
- Pedantic corrector (~7%): "Actually at 5:31, that's O(n log n) not O(n²)" — may or may not be correct
- "Who's watching in {year}" (~4%): "Who's still watching this in 2026? 🖐️"
- Bot/spam comment (~4%): generic praise + suspicious profile, or completely off-topic
- Comeback requester (~4%): "You haven't posted in 2 weeks, are you okay? 😢"
- Indian tutorial commenter (~3%): "Sir please make video on MERN stack placement preparation 🙏"

Comment format rules:
- Show username, timestamp ("2 days ago", "3 hours ago"), like count
- Include 💙 (hearted by creator) on 2-3 comments — the creator's endorsement
- Include 📌 pinned comment (usually creator's own comment with links)
- Include reply threads (2-3 levels max)
- Some comments are edited: "(edited)" after timestamp
- Include one creator reply with the ❤️ heart icon
- Mix of proper grammar and YouTube-speak (no caps, abbreviations, emojis)
- At least one comment should be a reply to the wrong video ("wait this isn't the Minecraft video")
- One comment thread should devolve into an argument about something not in the video
- No AI tells: YouTube comments are chaotic, low-effort, and genuine. No structured arguments, no "I'd like to add", no paragraph breaks in most comments.

## Output Format

---

## ▶️ YouTube

### {video_title}

**{channel_name}** · {subscriber_count} subscribers

{view_count} views · {time_ago} · 👍 {likes} 👎

[Thumbnail: {thumbnail_description}]

{video description — first 3 lines}
...show more

**Chapters:**
0:00 {intro}
{timestamp} {section}
...

---

**Video intro:**
{2-3 paragraphs of what the YouTuber says setting up the code review}

---

#### {comment_count} Comments

---

📌 **{channel_name}** · {time_ago} 💙
{pinned creator comment — usually links, corrections, or "smash that subscribe button"}

👍 {likes}

---

**{username}** · {time_ago}
{comment body}

👍 {likes} {💙 if hearted}

> **{replier}** · {time_ago}
> {reply body}
> 👍 {likes}

---

Use `📌` for pinned, `💙` for hearted by creator. Use `>` for replies. Separate top-level comments with `---`.

## Findings Summary

After the comments, output a structured summary of all technical findings from the scan and comments:

```
| File | Lines | Issue | Severity | Category |
|------|-------|-------|----------|----------|
| path/to/file.py | 10-25 | Description of issue | red-flag/concern/nitpick | security/architecture/correctness/missing-feature/docs |
```

Only include findings grounded in actual code. This is the primary output — be thorough. Omit "first" comments, tutorial requests, self-promotion, and off-topic arguments.

## Style Adjustment

- **balanced**: mix of useful comments and YouTube chaos — the essay commenter and the pedantic corrector carry the signal
- **snarky**: the armchair experts dominate, the YouTuber is roasting the code, comments are brutal
- **supportive**: appreciation spam, "best tutorial ever", creator hearts everything
- **hostile**: "This is the worst code I've ever seen" video, comments are a bloodbath, everyone has a better way to do it
