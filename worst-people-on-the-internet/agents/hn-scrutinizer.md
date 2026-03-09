Scrutinize the codebase at {path} as Hacker News would. Style: {style}.

## Step 1: Scan the Codebase

{scan_steps}

## Step 2: Synthesize Evidence

Identify:
- Strengths (3-5): clever engineering, novel approach, good docs
- Risks (3-5): over-engineering, missing basics, questionable choices
- Tangent magnets: topics that would derail into classic HN debates
- Contrarian angles: ways someone could argue this is wrong

All findings MUST reference actual code with file paths and line ranges.

## Step 3: Generate the HN Submission

Write a Show HN submission:
- Title: "Show HN: {Project Name} – {concise description}" (factual, no hype)
- Author: realistic HN username (short, lowercase, often name-based)
- Points: 50-400
- Brief, technical, understated submission text. No marketing language.

## Step 4: Generate the Discussion (15 comments)

HN discussions differ from Reddit:
- Flatter threads: typically 2-3 levels deep
- Longer comments: well-reasoned, multi-paragraph
- More technical depth: deep domain expertise
- Less memetic: fewer jokes, more substance
- Tangent-prone: drift to PL theory, startup culture, ethics
- pg-essay-quoting: reference Paul Graham essays

Archetypes (approximate weights — creative direction, not empirical):
- Domain expert (~12%): deep knowledge, production experience
- Contrarian (~10%): "Actually, use X instead" with reasoning
- Startup founder (~8%): market fit, scaling, company building
- Security demolisher (~10%): multi-paragraph technical teardown of auth, crypto, injection issues — the tptacek archetype
- Systems thinker (~10%): architecture, trade-offs, distributed systems
- Skeptic (~8%): "This is a solution in search of a problem"
- Enthusiast (~8%): excited, asks about roadmap
- Tangent-starter (~6%): broader discussion jumping off point
- Standards-citer (~5%): RFCs, specs, papers
- Historian (~6%): "This reminds me of {obscure 90s project}..."
- Duplicate police (~5%): "This was discussed N months ago: [link]" — points out prior threads
- Privacy absolutist (~5%): immediately asks about telemetry, phone-home, data collection
- Self-hosting advocate (~4%): "Can I self-host this?" / "Does it work air-gapped?"
- Anonymous FAANG (~3%): "At my current employer we..." — can't name the company
- dang (rare): moderator voice

Rules:
- Include 1-2 OP replies (humble, technical, grateful)
- Create 1-2 tangent chains that drift
- At least one comment should question the fundamental premise
- Technical criticism must reference actual code
- Include one "I've been doing X for 20 years" authority appeal
- Include one duplicate police comment referencing a prior discussion
- Include 1 [flagged] or [dead] comment — a killed hot take that's still visible with showdead
- No AI tells: no "Great point!", "It's worth noting". Write like real HN — direct, sometimes terse, sometimes mini-essays
- HN voice, not Reddit voice: longer, more thoughtful, fewer memes

## Output Format

---

## Hacker News

### Show HN: {title}

**{author}** · ▲ {points} · {comment_count} comments

{submission text}

---

#### Discussion

---

▲ {points} | **{author}**

{comment body — can be multiple paragraphs}

  ▲ {points} | **{replier}**

  {reply body}

---

Use 2-space indentation per depth level. Separate top-level comments with ---.

## Findings Summary

After the discussion, output a structured summary of all technical findings from the scan and discussion:

```
| File | Lines | Issue | Severity | Category |
|------|-------|-------|----------|----------|
| path/to/file.py | 10-25 | Description of issue | red-flag/concern/nitpick | security/architecture/correctness/missing-feature/docs |
```

Only include findings grounded in actual code. Omit tangents and pure opinion.
