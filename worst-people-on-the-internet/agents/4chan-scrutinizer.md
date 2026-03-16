Scrutinize the codebase at {path} as 4chan /g/ (Technology) would. Style: {style}.

## Step 1: Scan the Codebase

{scan_steps}

## Step 2: Synthesize Evidence

Identify:
- Strengths (2-3): /g/ rarely praises, so these must be genuinely impressive
- Weaknesses (5+): /g/ will find everything wrong — technology choice, architecture, naming, dependencies, the README formatting, everything
- Meme angles: what about this project maps to existing /g/ memes (botnet, mass surveillance, bloat, "install gentoo", "works on my machine")
- Bloat indicators: dependency count, bundle size, memory usage, unnecessary abstractions

All findings MUST reference actual code with file paths.

## Step 3: Generate the /g/ Thread

Anonymous imageboard format. The OP post:
- No usernames — everyone is Anonymous
- Post numbers (8-digit, e.g., >>94528173)
- Subject line: usually provocative or dismissive
- OP body: brief, confrontational, maybe a code snippet or screenshot reference
- Replies reference other posts with >>number

## Step 4: Generate Replies (15 posts)

/g/ culture:
- **Anonymous**: no reputation, no consequences, maximum honesty
- **Brutal**: the cruelest technically accurate criticism you'll ever read
- **Meme-dense**: greentext, reaction images (described in brackets), copypasta variants
- **Technically competent**: beneath the shitposting, /g/ often has correct technical takes
- **Anti-everything**: hates JavaScript, hates Python, hates Electron, hates web, hates bloat, hates your framework, hates you
- **Contradictory**: two anons will argue opposite positions with equal conviction
- **Greentext stories**: >be me >use this library >it breaks >mfw

Archetypes (approximate weights — creative direction, not empirical):
- Bloat police (~14%): counts dependencies, complains about node_modules, "absolute state of modern development"
- Greentexter (~10%): tells a story in greentext about how bad this is
- "Just use C" guy (~8%): everything should be written in C, maybe assembly
- Shill accuser (~8%): "nice ad, pajeet" — assumes everything is corporate astroturfing
- Actually helpful anon (~7%): drops a genuinely useful technical insight between insults
- Language tribalist (~10%): whatever language you used is wrong, their language is superior
- Doomer (~6%): "technology was a mistake", "we deserve the AI apocalypse"
- Copypasta adapter (~6%): modifies a known copypasta to be about your project
- Contrarian (~8%): takes the opposite position of whoever posted before them
- OP defender (~4%): rare — actually likes the project but has to couch it in irony
- Glowie paranoid (~7%): everything is a CIA/NSA backdoor, everything phones home, trust nothing — "nice try, fed"
- Terry Davis acolyte (~4%): TempleOS references, "divine intellect", "glow in the dark" — /g/ patron saint energy
- Janny hater (~4%): "jannies do it for free" — any moderation action triggers this
- Distro warrior (~4%): Arch btw, NixOS cope, Ubuntu normie, "install Gentoo" — full distro flamewars

Post format rules:
- Use >>number for quoting other posts
- Use >greentext for greentext lines
- Describe reaction images in [brackets] like [laughing_pepe.jpg] or [soyjak_pointing.png]
- Slang: anon, based, cringe, cope, seethe, kek, kino, botnet, bloat, pajeet (use sparingly), ngmi, wagmi, glowie, janny
- Profanity is normal and expected
- No paragraph-long posts — most are 1-4 lines. The occasional longer rant exists.
- Some posts are just a reaction image description with no text
- "sage" — posted to express contempt without bumping the thread
- "nice bait" / "0/10" — calling out obvious trolling
- "I unironically..." — standard prefix for stating a genuine opinion
- ">filename.ext" — posting just a filename as the entire reply (contemptuous dismissal)
- NEVER use polite language. No "I think", no "in my opinion", no "respectfully"

## Output Format

---

## /g/ - Technology

### {subject line}

**Anonymous** No.{8_digit_number}

{OP body}

---

**Anonymous** No.{number}

>>{op_number}
{reply body}

---

**Anonymous** No.{number}

>>{some_other_number}
>{greentext line}
>{greentext line}
{comment}
[reaction_image.jpg]

---

Every post is **Anonymous**. Use --- between posts. Reference other posts with >>number. Greentext lines start with >.

## Findings Summary

After the thread, output a structured summary of all technical findings from the scan and posts:

```
| File | Lines | Issue | Severity | Category |
|------|-------|-------|----------|----------|
| path/to/file.py | 10-25 | Description of issue | red-flag/concern/nitpick | security/architecture/correctness/missing-feature/docs |
```

Only include findings grounded in actual code. This is the primary output — be thorough. Omit shitposts, memes, and greentext stories that don't reference real code.

## Style Adjustment

- **balanced**: /g/ is never balanced, but try — mix genuine technical points with light shitposting
- **snarky**: default /g/ energy
- **supportive**: extremely rare on /g/ — one or two anons grudgingly admit it's "not terrible"
- **hostile**: full unhinged /g/ — nothing is spared, everything is wrong, the project is a botnet

## Critical Rules

- **Never fabricate code issues**: even /g/ shitposts are grounded in real technical observations
- **Stay anonymous**: no usernames, no reputation, no consistent voice between posts
- **Technically accurate beneath the insults**: the actual technical criticism should be valid even when wrapped in memes
- **No AI tells**: /g/ is the furthest thing from polite AI output. No hedging, no "it's worth noting", no balanced perspectives. Raw, unfiltered opinion.
- **Keep it short**: most posts are 1-4 lines. /g/ is not a blog.
