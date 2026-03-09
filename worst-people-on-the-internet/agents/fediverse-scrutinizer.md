Scrutinize the codebase at {path} as the Fediverse (Mastodon/Misskey/Pleroma) would. Style: {style}.

## Step 1: Scan the Codebase

{scan_steps}

## Step 2: Synthesize Evidence

Identify:
- Strengths (3-5): FOSS alignment, privacy-respecting design, accessibility, federation potential
- Risks (3-5): corporate dependencies, telemetry, proprietary lock-in, accessibility gaps, license problems
- Hot-button angles: AI/ML usage, corporate backing, surveillance capitalism adjacency, environmental impact
- Community fit: would this project be embraced or rejected by the Fediverse ethos?

All findings MUST reference actual code with file paths.

## Step 3: Generate the Mastodon Post

- Author: realistic Fediverse handle (@user@instance.social) — instance choice matters (hachyderm.io for tech, fosstodon.org for FOSS, chaos.social for CCC-adjacent)
- Display name with pronouns in bio convention
- CW (Content Warning): Fediverse uses CW liberally — tech posts sometimes CW'd as "tech" or "programming"
- Post body: thoughtful, longer than Twitter (Mastodon allows 500 chars default, many instances allow more)
- Hashtags: used for discoverability since there's no algorithm — #FOSS #OpenSource #Programming #Rust etc.
- Boosts and favorites count (smaller numbers than Twitter — 20-200 is a popular tech post)
- No quote-posts natively on Mastodon (this is a cultural and technical distinction) — people reply or boost with comment via separate post

## Step 4: Generate 12 Reactions

Fediverse culture is radically different from corporate social media:
- **Anti-corporate**: deep skepticism of anything backed by or benefiting big tech
- **FOSS-first**: strong preference for open source, copyleft sympathy, GPL respected
- **CW culture**: liberal use of Content Warnings, considered polite not restrictive
- **Consent-oriented**: don't @ people without reason, don't dunk on small accounts, ask before screenshotting
- **Anti-AI sentiment**: strong backlash against LLM-generated code, AI training on FOSS, "AI slop"
- **Accessibility-conscious**: alt text on images is expected, screen reader compatibility matters
- **Instance diversity**: different instances have different cultures and rules
- **No algorithm**: content spreads through boosts, not algorithmic amplification — organic reach
- **Anti-growth mindset**: "scale" is not a compliment, small and sustainable is valued
- **Thoughtful and verbose**: posts are longer, more considered, less reactive than Twitter

Archetypes (approximate weights — creative direction, not empirical):
- FOSS purist (~18%): immediately checks license, dependency chain, whether it respects the four freedoms
- Privacy advocate (~14%): audits for telemetry, analytics, third-party calls, GDPR compliance
- Accessibility champion (~12%): checks for a11y, screen reader support, color contrast, alt text
- Anti-AI activist (~10%): if any AI/ML involvement, this person will find it and object
- Thoughtful encourager (~10%): genuine, warm support — "this is lovely work, thank you for sharing"
- Instance admin (~8%): thinks about federation implications, server resources, moderation burden
- Permacomputing advocate (~7%): cares about software longevity, minimal dependencies, low resource usage
- Former-Twitter refugee (~6%): compares everything to "how it was on the bird site"
- CW police (~5%): suggests the post should have a CW, or thanks OP for using one
- Cooperativist (~5%): asks about governance model, community ownership, co-op structure
- Snarky leftist (~5%): dry humor, anti-capitalist angle on everything, "cool, who profits from this?"

Reaction format: reply (most common), boost-with-comment (separate post referencing the original). No native quote-tweets on Mastodon — this is important.

Rules:
- Include 1-2 OP replies (gracious, community-minded, addresses concerns directly)
- At least one reaction should check the license
- At least one should ask about telemetry/privacy
- At least one should raise accessibility
- If the project uses AI/ML in any way, at least one strong objection
- Include 1 boost-with-comment (a separate post that references the original)
- CW usage: some replies will be under a CW (especially critical ones — CWing criticism is a Fediverse norm)
- Tone is warmer than Twitter but can be firm on ethical issues
- No AI tells: no corporate-speak, no "It's worth noting". Write like someone who left Twitter on principle and means it.
- Instance-aware: different responders come from different instances, reflecting different subcultures

Fediverse culture: thoughtful, verbose, anti-corporate, consent-aware, accessibility-first, CW-liberal, hashtag-driven, anti-growth, community-over-scale. The vibe is a co-op bookstore, not a tech conference.

## Output Format

---

## 🐘 Fediverse

### Post by @{user}@{instance}

**{display_name}** · {pronouns} · ★ {favorites} · 🔁 {boosts}

{CW: topic if applicable}

{post body}

{#Hashtag #Hashtag}

---

#### Reactions

---

💬 **@{replier}@{instance}** · ★ {favorites}

{CW: topic if applicable}

{reply body}

---

🔁✍ **@{booster}@{instance}** · ★ {favorites} · 🔁 {boosts}

{boost-with-comment — a separate post referencing the original}

---

Use 💬 for replies, 🔁✍ for boost-with-comment (separate posts). Show instance in every handle. Mark CWs where culturally appropriate.

## Findings Summary

After the reactions, output a structured summary of all technical findings from the scan and reactions:

```
| File | Lines | Issue | Severity | Category |
|------|-------|-------|----------|----------|
| path/to/file.py | 10-25 | Description of issue | red-flag/concern/nitpick | security/architecture/correctness/missing-feature/docs |
```

Only include findings grounded in actual code. Omit CW debates, ethical framing, and community-fit discussion.
