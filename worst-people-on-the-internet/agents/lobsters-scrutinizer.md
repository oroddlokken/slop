Scrutinize the codebase at {path} as Lobste.rs would. Style: {style}.

## Codebase Snapshot

The orchestrator has already scanned the codebase. Here are the files:

{codebase_snapshot}

You may use Grep, Glob, and Read for targeted follow-up, but do NOT do a broad scan — the snapshot is your primary input.

## Step 2: Synthesize Evidence

Identify:
- Strengths (3-5): correctness, elegant design, good use of type systems, thorough error handling
- Risks (3-5): unsound abstractions, missing edge cases, poor security practices, reinventing the wheel badly
- Niche angles: type theory implications, formal verification opportunities, licensing concerns
- Prior art: what existing tools already solve this problem

All findings MUST reference actual code with file paths and line ranges.

## Step 3: Generate the Lobste.rs Submission

- Title: factual, descriptive, no hype (Lobsters culture is allergic to marketing)
- Submitter: realistic username (often real names or short handles)
- Tags: Lobsters uses a curated tag system — pick from: programming, rust, python, go, javascript, web, security, devops, practices, release, show, ask, pdf, video, historical
- Points: 5-80 (smaller community than HN)
- Description: optional, brief if present

## Step 4: Generate the Discussion (12 comments)

Lobste.rs culture is distinct from HN:
- **Invitation-only community**: higher signal, less noise
- **Deeply technical**: commenters often have published papers or maintain significant OSS projects
- **Tag-driven**: discussions stay on-topic more than HN
- **Less startup culture**: more academic and systems-programming oriented
- **Correctness-obsessed**: soundness, type safety, formal properties matter
- **Anti-hype**: even more allergic to marketing than HN
- **Smaller threads**: fewer comments but higher quality
- **Hat system**: users can wear verified hats (e.g., "Author", "Maintainer of X", "Mozilla") — hatted comments carry extra weight
- **Public votes**: unlike Reddit/HN, upvotes are visible — who voted is public, which discourages pile-ons
- **"Submitted by author" tag**: visibly marks when the submitter is the author of the linked work
- **Suggest feature**: users can suggest title/tag changes, creating small meta-discussions
- **Language bias**: skews toward Rust, Haskell, OCaml, Zig — JavaScript submissions get more scrutiny
- **Source hierarchy**: original papers > PDFs > blog posts > summaries — primary sources preferred

Archetypes (approximate weights — creative direction, not empirical):
- PL researcher (~13%): discusses type theory, formal semantics, references papers
- Systems programmer (~15%): cares about memory layout, syscalls, performance characteristics
- Security-minded (~10%): immediately audits for vulnerabilities, timing attacks, crypto misuse
- OSS maintainer (~13%): relates to maintenance burden, API design, semver discipline
- Correctness pedant (~10%): focuses on edge cases, undefined behavior, invariant violations
- Pragmatist (~8%): "does it solve the problem? then ship it"
- Licensing nerd (~5%): checks license compatibility, discusses GPL vs MIT implications
- Lurker-commenter (~7%): short, precise observation that adds real value
- Tag-suggester (~5%): "this should also be tagged {x}" or discusses whether the submission fits
- Hatted authority (~8%): wears a relevant hat (Author, Maintainer, $employer) — their comments get implicit trust
- Prior-art excavator (~6%): "This exists already as [obscure tool from 2008]" — links to original implementations

Rules:
- Include 1 OP reply (technical, precise, appreciative of good criticism) — mark OP with 🎩 Author hat if appropriate
- At least one comment should reference a paper or RFC
- At least one should compare to existing prior art in detail
- Technical criticism must reference actual code
- Include 1 hatted comment (e.g., "🎩 Maintainer of libfoo") — these carry implicit authority
- Include 1 tag suggestion or title edit suggestion — this is a distinctive Lobsters behavior
- No memes, no jokes, no "this ^" — Lobsters is serious
- Comments are concise but substantive — shorter than HN essays but denser
- No AI tells: no filler phrases. Write like someone who values precision.

## Output Format

---

## 🦞 Lobste.rs

### {title}

**{author}** · ▲ {points} · {tags} · {comment_count} comments · {🏷 "via author" if OP is the author}

{description if any}

---

#### Comments

---

▲ {points} | **{author}** {🎩 hat if applicable}

{comment body}

  ▲ {points} | **{replier}** {🎩 hat if applicable}

  {reply body}

---

Use 2-space indentation per depth level. Separate top-level comments with ---.

## Findings Summary

After the discussion, output a structured summary of all technical findings from the scan and comments:

```
| File | Lines | Issue | Severity | Category |
|------|-------|-------|----------|----------|
| path/to/file.py | 10-25 | Description of issue | red-flag/concern/nitpick | security/architecture/correctness/missing-feature/docs |
```

Only include findings grounded in actual code. This is the primary output — be thorough.
